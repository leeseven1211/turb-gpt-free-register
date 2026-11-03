"""Explicit, credential-free Sentinel candidate maintenance.

This module does not execute JavaScript or select an SDK for authentication.
Only ``check(refresh=True)`` performs network I/O. The caller owns the cache
directory; no active SDK, runner cache, runtime configuration or account state
is read or written. Static marker checks are maintenance hints, not proof that
either runner can execute the candidate.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


LOADER_URL = "https://sentinel.openai.com/backend-api/sentinel/sdk.js"
_VERSION = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
_SDK_PATH = re.compile(rf"/sentinel/({_VERSION})/sdk\.js\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RECORD = re.compile(rf"{_VERSION}-[0-9a-f]{{64}}-[0-9a-f]{{64}}\.json\Z")
_SDK_LITERAL = re.compile(r'''(["'`])([^"'`\r\n]*/sentinel/[^"'`\r\n]*/sdk\.js[^"'`\r\n]*)\1''')
_GENERIC_MARKERS = (("SDK_GLOBAL", "var SentinelSDK="), ("TOKEN", "t.token="))
_PROTO2_HOOKS = (
    ("SDK_GLOBAL", "var SentinelSDK="),
    ("INSTANCE", "var E=new O;"),
    ("EXPOSE", ",t.token=je,t}({});"),
)
_JS_TYPES = {"application/javascript", "text/javascript", "application/x-javascript", "text/ecmascript"}
_SDK_DECLARATION = re.compile(r"(?:\b(?:var|let|const)\s+|(?:globalThis|window)\.)SentinelSDK\s*=")


class AssetError(ValueError):
    """A stable, safe reason code, without response bodies or remote errors."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class StaticCompatibility:
    generic_status: str
    proto2_status: str
    generic_markers: tuple[tuple[str, int], ...]
    proto2_hooks: tuple[tuple[str, int], ...]
    runtime_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "generic_status": self.generic_status,
            "proto2_status": self.proto2_status,
            "generic_markers": dict(self.generic_markers),
            "proto2_hooks": dict(self.proto2_hooks),
            "runtime_verified": False,
        }


@dataclass(frozen=True)
class SdkArtifact:
    version: str
    sdk_url: str
    sha256: str
    loader_sha256: str
    path: Path
    fetched_at: float
    compatibility: StaticCompatibility

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["path"] = str(self.path)
        result["compatibility"] = self.compatibility.to_dict()
        return result


@dataclass(frozen=True)
class AssetCheck:
    status: str
    reason: str | None = None
    artifact: SdkArtifact | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "artifact": self.artifact.to_dict() if self.artifact else None,
        }


def _official_url(url: str, *, loader: bool = False) -> str | None:
    """Return an SDK version (or None for the loader), rejecting ambiguity."""
    if not isinstance(url, str) or not url or any(ord(char) <= 32 or ord(char) >= 127 for char in url):
        raise AssetError("invalid_resource_url")
    try:
        parsed = urlsplit(url)
        valid_origin = (
            parsed.scheme == "https"
            and parsed.netloc.lower() in {"sentinel.openai.com", "sentinel.openai.com:443"}
            and not parsed.query and not parsed.fragment
        )
    except ValueError:
        raise AssetError("invalid_resource_url") from None
    if not valid_origin or "?" in url or "#" in url:
        raise AssetError("invalid_resource_url")
    if loader:
        if parsed.path != "/backend-api/sentinel/sdk.js":
            raise AssetError("invalid_resource_url")
        return None
    match = _SDK_PATH.fullmatch(parsed.path)
    if not match:
        raise AssetError("invalid_resource_url")
    return match.group(1)


def _script_text(content: bytes) -> str:
    if not content or not content.strip():
        raise AssetError("empty_script")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AssetError("invalid_script_encoding") from None
    # Reject challenge/error documents even when their MIME type is wrong.
    if re.search(r"<(?:!doctype\s+html|html|head|body|script)(?:\s|>)", text, re.I) or "\x00" in text:
        raise AssetError("invalid_script_content")
    return text


def discover_sdk(loader: bytes) -> tuple[str, str]:
    """Parse exactly one versioned official SDK string literal; never eval JS."""
    text = _script_text(loader).replace("\\/", "/")
    candidates = [match.group(2) for match in _SDK_LITERAL.finditer(text)]
    if len(candidates) != 1:
        raise AssetError("ambiguous_loader" if candidates else "sdk_url_not_found")
    url = candidates[0]
    version = _official_url(url)
    return str(version), url


def _validate_sdk(content: bytes) -> None:
    if not _SDK_DECLARATION.search(_script_text(content)):
        raise AssetError("sdk_marker_missing")


def static_compatibility(content: bytes) -> StaticCompatibility:
    text = _script_text(content)
    generic = tuple((name, text.count(marker)) for name, marker in _GENERIC_MARKERS)
    hooks = tuple((name, text.count(marker)) for name, marker in _PROTO2_HOOKS)
    return StaticCompatibility(
        generic_status="static_markers_present" if all(hits == 1 for _, hits in generic) else "needs_adaptation",
        proto2_status="static_markers_present" if all(hits == 1 for _, hits in hooks) else "needs_adaptation",
        generic_markers=generic,
        proto2_hooks=hooks,
    )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _header(headers, name: str) -> str:
    return next((str(value) for key, value in headers.items() if str(key).lower() == name.lower()), "")


class SentinelAssetManager:
    """Content-addressed candidate cache, serialized across threads/processes.

    ``opener`` optionally supplies urllib's ``open(Request, timeout=...)``
    contract for offline diagnostics/tests. It must not follow redirects;
    unexpected effective URLs are rejected as a second line of defense.
    """

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        opener=None,
        ttl_seconds: float = 86400,
        timeout_seconds: float = 15,
        max_loader_bytes: int = 128 * 1024,
        max_sdk_bytes: int = 2 * 1024 * 1024,
        max_redirects: int = 3,
    ):
        if not math.isfinite(ttl_seconds) or ttl_seconds < 0:
            raise ValueError("ttl_seconds must be finite and nonnegative")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if not 1 <= max_loader_bytes <= 1024 * 1024 or not 1 <= max_sdk_bytes <= 16 * 1024 * 1024:
            raise ValueError("invalid script byte limit")
        if not isinstance(max_redirects, int) or not 0 <= max_redirects <= 10:
            raise ValueError("invalid redirect limit")
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        self.opener = opener if opener is not None else build_opener(_NoRedirect())
        self.ttl_seconds = ttl_seconds
        self.timeout_seconds = timeout_seconds
        self.max_loader_bytes = max_loader_bytes
        self.max_sdk_bytes = max_sdk_bytes
        self.max_redirects = max_redirects

    def _path(self, relative: str) -> Path:
        path = self.cache_dir / relative
        if not path.resolve().is_relative_to(self.cache_dir):
            raise AssetError("corrupt_cache")
        return path

    @contextmanager
    def _lock(self):
        # A single advisory lock covers readers and atomic multi-file updates.
        try:
            import fcntl
        except ImportError:
            raise AssetError("cache_lock_unsupported") from None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with self._path(".lock").open("a+b") as handle:
            deadline = time.monotonic() + self.timeout_seconds
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise AssetError("cache_lock_timeout") from None
                    time.sleep(0.02)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _read_json(self, relative: str, *, limit: int = 1024 * 1024):
        with self._path(relative).open("rb") as handle:
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise AssetError("corrupt_cache")
        try:
            return json.loads(data)
        except (ValueError, UnicodeDecodeError):
            raise AssetError("corrupt_cache") from None

    def _load(self) -> tuple[SdkArtifact | None, dict]:
        if not self._path("index.json").exists():
            return None, {"schema": 1, "versions": {}}
        try:
            index = self._read_json("index.json")
            if index["schema"] != 1 or not _RECORD.fullmatch(index["latest"]):
                raise ValueError
            checked_at = index["checked_at"]
            if not isinstance(checked_at, (int, float)) or not math.isfinite(checked_at) or checked_at > time.time() + 60:
                raise ValueError
            versions = index["versions"]
            if not isinstance(versions, dict) or not all(
                re.fullmatch(_VERSION, version) and isinstance(hashes, list)
                and hashes and all(isinstance(digest, str) and _SHA.fullmatch(digest) for digest in hashes)
                for version, hashes in versions.items()
            ):
                raise ValueError
            record = self._read_json("records/" + index["latest"], limit=65536)
            version, sdk_url = record["version"], record["sdk_url"]
            sha256, loader_sha256 = record["sha256"], record["loader_sha256"]
            if not _SHA.fullmatch(sha256) or not _SHA.fullmatch(loader_sha256):
                raise ValueError
            if _official_url(sdk_url) != version or sha256 not in versions.get(version, []):
                raise ValueError
            if index["latest"] != f"{version}-{sha256}-{loader_sha256}.json":
                raise ValueError
            expected_path = "blobs/" + sha256 + ".js"
            if record["path"] != expected_path:
                raise ValueError
            fetched_at = record["fetched_at"]
            if not isinstance(fetched_at, (int, float)) or not math.isfinite(fetched_at) or not 0 < fetched_at <= checked_at:
                raise ValueError
            path = self._path(expected_path)
            with path.open("rb") as handle:
                content = handle.read(self.max_sdk_bytes + 1)
            if len(content) > self.max_sdk_bytes or hashlib.sha256(content).hexdigest() != sha256:
                raise ValueError
            _validate_sdk(content)
            compatibility = static_compatibility(content)
            if record["compatibility"] != compatibility.to_dict():
                raise ValueError
            return SdkArtifact(version, sdk_url, sha256, loader_sha256, path, fetched_at, compatibility), index
        except (KeyError, TypeError, ValueError, OSError):
            raise AssetError("corrupt_cache") from None

    def _write(self, relative: str, content: bytes):
        target = self._path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Creating the temporary file beside its target makes replace atomic.
        descriptor, temporary = tempfile.mkstemp(prefix=".candidate-", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _write_json(self, relative: str, value):
        self._write(relative, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())

    def _download(self, url: str, *, loader: bool, limit: int, deadline: float) -> bytes:
        version = _official_url(url, loader=loader)
        for hop in range(self.max_redirects + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssetError("download_timeout")
            request = Request(url, headers={"Accept": "application/javascript", "User-Agent": "Turb-Sentinel-Assets/1"})
            try:
                response = self.opener.open(request, timeout=remaining)
            except HTTPError as error:
                response = error
            with response:
                effective_url = response.geturl()
                if effective_url and effective_url != url:
                    raise AssetError("unexpected_transport_redirect")
                status = response.status if hasattr(response, "status") else response.code
                if status in {301, 302, 303, 307, 308}:
                    if hop == self.max_redirects:
                        raise AssetError("too_many_redirects")
                    location = _header(response.headers, "Location")
                    if not location or any(ord(char) <= 32 or ord(char) >= 127 for char in location):
                        raise AssetError("invalid_redirect")
                    redirected = urljoin(url, location)
                    target_version = _official_url(redirected, loader=loader)
                    if target_version != version:
                        raise AssetError("invalid_redirect")
                    url = redirected
                    continue
                if status != 200:
                    raise AssetError("unexpected_http_status")
                content_type = _header(response.headers, "Content-Type").split(";", 1)[0].strip().lower()
                if content_type and content_type not in _JS_TYPES:
                    raise AssetError("invalid_content_type")
                encoding = _header(response.headers, "Content-Encoding").strip().lower()
                if encoding not in {"", "identity"}:
                    raise AssetError("unsupported_content_encoding")
                length = _header(response.headers, "Content-Length")
                if length:
                    if not length.isascii() or not length.isdigit():
                        raise AssetError("invalid_content_length")
                    if int(length) > limit:
                        raise AssetError("response_too_large")
                content = bytearray()
                read = getattr(response, "read1", response.read)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AssetError("download_timeout")
                    # urllib's HTTPResponse exposes its socket here. Updating
                    # its timeout bounds each read by the shared deadline.
                    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                    if sock is not None:
                        sock.settimeout(remaining)
                    chunk = read(min(65536, limit + 1 - len(content)))
                    content.extend(chunk)
                    if len(content) > limit:
                        raise AssetError("response_too_large")
                    if not chunk:
                        break
                if time.monotonic() > deadline:
                    raise AssetError("download_timeout")
                if length and len(content) != int(length):
                    raise AssetError("content_length_mismatch")
                return bytes(content)
        raise AssetError("too_many_redirects")

    def _store(self, loader: bytes, sdk_url: str, content: bytes, index: dict) -> SdkArtifact:
        version = str(_official_url(sdk_url))
        sha256 = hashlib.sha256(content).hexdigest()
        loader_sha256 = hashlib.sha256(loader).hexdigest()
        relative = "blobs/" + sha256 + ".js"
        path = self._path(relative)
        compatibility = static_compatibility(content)
        name = f"{version}-{sha256}-{loader_sha256}.json"
        record_path = "records/" + name
        now = time.time()
        fetched_at = now
        if self._path(record_path).exists():
            # Re-observing identical resources preserves first-fetch metadata.
            try:
                previous = self._read_json(record_path, limit=65536)
                previous_time = previous.get("fetched_at")
                if isinstance(previous_time, (int, float)) and math.isfinite(previous_time) and 0 < previous_time <= now:
                    fetched_at = previous_time
            except (AssetError, OSError, AttributeError):
                pass
        artifact = SdkArtifact(version, sdk_url, sha256, loader_sha256, path, fetched_at, compatibility)
        # Published blobs are never changed to another candidate's bytes.
        existing_matches = False
        if path.exists():
            with path.open("rb") as handle:
                existing_matches = handle.read(len(content) + 1) == content
        if not existing_matches:
            self._write(relative, content)
        record = artifact.to_dict()
        record["path"] = relative
        if not self._path(record_path).exists():
            self._write_json(record_path, record)
        else:
            try:
                unchanged = self._read_json(record_path, limit=65536) == record
            except (AssetError, OSError):
                unchanged = False
            if not unchanged:
                self._write_json(record_path, record)
        versions = index.get("versions", {})
        hashes = versions.setdefault(version, [])
        if sha256 not in hashes:
            hashes.append(sha256)
        self._write_json("index.json", {"schema": 1, "latest": name, "checked_at": now, "versions": versions})
        return artifact

    def check(self, *, refresh: bool = False) -> AssetCheck:
        """Inspect local cache, or explicitly fetch and publish a candidate.

        Missing/stale/corrupt local state never starts a network request. A
        refresh failure returns the previous validated artifact, if available,
        while persisting only a safe reason code in ``last_check.json``.
        """
        try:
            with self._lock():
                corrupt = False
                try:
                    artifact, index = self._load()
                except AssetError:
                    artifact, index = None, {"schema": 1, "versions": {}}
                    corrupt = True
                if not refresh:
                    if artifact is None:
                        return AssetCheck("corrupt" if corrupt else "missing", "corrupt_cache" if corrupt else None)
                    stale = time.time() - index["checked_at"] >= self.ttl_seconds
                    return AssetCheck("stale" if stale else "cached", artifact=artifact)
                try:
                    deadline = time.monotonic() + self.timeout_seconds
                    loader = self._download(LOADER_URL, loader=True, limit=self.max_loader_bytes, deadline=deadline)
                    _, sdk_url = discover_sdk(loader)
                    content = self._download(sdk_url, loader=False, limit=self.max_sdk_bytes, deadline=deadline)
                    _validate_sdk(content)
                    artifact = self._store(loader, sdk_url, content, index)
                    result = AssetCheck("refreshed", artifact=artifact)
                except AssetError as error:
                    result = AssetCheck("failed", error.reason, artifact)
                except TimeoutError:
                    result = AssetCheck("failed", "download_timeout", artifact)
                except (OSError, ValueError, HTTPException):
                    result = AssetCheck("failed", "fetch_or_cache_failed", artifact)
                self._write_json("last_check.json", {
                    "status": result.status, "reason": result.reason, "checked_at": time.time(),
                })
                return result
        except AssetError as error:
            return AssetCheck("failed", error.reason)
        except OSError:
            return AssetCheck("failed", "cache_io_failed")
