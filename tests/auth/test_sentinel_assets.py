"""Offline candidate discovery and real filesystem cache tests."""
from __future__ import annotations

import hashlib
import http.client
import io
import json
import multiprocessing
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.auth.protocol import sentinel_assets
from core.auth.protocol.sentinel_assets import (
    LOADER_URL,
    AssetError,
    SentinelAssetManager,
    discover_sdk,
    static_compatibility,
)


SDK_URL = "https://sentinel.openai.com/sentinel/20260810913b/sdk.js"
LOADER = f'(function(){{var s=document.createElement("script");s.src="{SDK_URL}";}})();'.encode()
SDK = b"var SentinelSDK=function(t){var E=new O;t.init=init;t.sessionObserverToken=so,t.token=je,t}({});"


class Response(io.BytesIO):
    def __init__(self, body=b"", *, status=200, headers=None, url=None):
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Type": "application/javascript", **(headers or {})}
        self.url = url

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.full_url, dict(request.header_items()), timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def manager(cache, sdk=SDK, **kwargs):
    return SentinelAssetManager(cache, opener=Opener([Response(LOADER), Response(sdk)]), **kwargs)


def _refresh_process(cache, start, output):
    start.wait(10)
    result = manager(cache).check(refresh=True)
    output.put((result.status, result.artifact.sha256 if result.artifact else None))


def test_official_loader_is_parsed_without_execution():
    assert discover_sdk(LOADER) == ("20260810913b", SDK_URL)


def test_a_second_template_literal_url_is_not_ignored():
    with pytest.raises(AssetError):
        discover_sdk(LOADER + b"other.src=`https://evil.test/sentinel/v2/sdk.js`;")


@pytest.mark.parametrize("url", [
    SDK_URL.replace("https:", "http:"),
    SDK_URL.replace("sentinel.openai.com", "sentinel.openai.com.evil.test"),
    SDK_URL.replace("sentinel.openai.com", "sentinel.openai.com@evil.test"),
    SDK_URL.replace("sentinel.openai.com", "user@sentinel.openai.com"),
    SDK_URL.replace("sentinel.openai.com", "sentinel.openai.com:8443"),
    SDK_URL.replace("20260810913b", "a/b"),
    SDK_URL.replace("20260810913b", "%2e%2e"),
    SDK_URL + "?token=do-not-log",
    SDK_URL + "#fragment",
])
def test_hostile_loader_urls_are_rejected(url):
    with pytest.raises(AssetError):
        discover_sdk(f's.src="{url}";'.encode())


@pytest.mark.parametrize("loader", [
    b"console.log('changed loader')",
    LOADER + LOADER,
    LOADER + b'other.src="https://evil.test/sentinel/v2/sdk.js";',
    b"<!doctype html><html>challenge</html>",
])
def test_missing_multiple_or_html_loader_is_rejected(loader):
    with pytest.raises(AssetError):
        discover_sdk(loader)


def test_static_reports_distinguish_runners_and_never_claim_runtime_success():
    report = static_compatibility(SDK)
    assert report.generic_status == "static_markers_present"
    assert report.proto2_status == "static_markers_present"
    assert dict(report.proto2_hooks) == {"SDK_GLOBAL": 1, "INSTANCE": 1, "EXPOSE": 1}
    changed = static_compatibility(SDK.replace(b"var E=new O;", b"var X=new Y;"))
    assert changed.generic_status == "static_markers_present"
    assert changed.proto2_status == "needs_adaptation"
    assert static_compatibility(SDK + b"var E=new O;").proto2_status == "needs_adaptation"
    assert report.runtime_verified is False


def test_content_addressed_artifact_is_immutable_and_reusable_without_network(tmp_path):
    first = manager(tmp_path).check(refresh=True)
    assert first.status == "refreshed"
    artifact = first.artifact
    assert artifact.sha256 == hashlib.sha256(SDK).hexdigest()
    assert artifact.loader_sha256 == hashlib.sha256(LOADER).hexdigest()
    assert artifact.path.read_bytes() == SDK
    assert artifact.path.name == artifact.sha256 + ".js"
    with pytest.raises(FrozenInstanceError):
        artifact.version = "new"
    reused = SentinelAssetManager(tmp_path, opener=Opener([])).check()
    assert reused.status == "cached"
    assert reused.artifact == artifact


def test_no_implicit_fetch_for_missing_or_stale_cache(tmp_path):
    assets = SentinelAssetManager(tmp_path, opener=Opener([]), ttl_seconds=0)
    assert assets.check().status == "missing"
    manager(tmp_path).check(refresh=True)
    result = assets.check()
    assert result.status == "stale"
    assert result.artifact.path.read_bytes() == SDK


def test_same_version_changed_bytes_preserves_both_candidates(tmp_path):
    old = manager(tmp_path).check(refresh=True).artifact
    new = manager(tmp_path, sdk=SDK + b"\n// rebuilt").check(refresh=True).artifact
    assert old.version == new.version
    assert old.sha256 != new.sha256
    assert old.path.read_bytes() == SDK
    assert new.path.read_bytes() == SDK + b"\n// rebuilt"
    index = json.loads((tmp_path / "index.json").read_text())
    assert set(index["versions"][old.version]) == {old.sha256, new.sha256}


@pytest.mark.parametrize("body,headers", [
    (b"", {}),
    (b"<!doctype html><html>SentinelSDK</html>", {}),
    (b"console.log('not the sdk')", {}),
    (SDK, {"Content-Type": "text/html"}),
    (SDK, {"Content-Length": "99999999"}),
])
def test_failed_fetch_preserves_good_artifact_and_persists_safe_failure(tmp_path, body, headers):
    good = manager(tmp_path).check(refresh=True).artifact
    assets = SentinelAssetManager(tmp_path, opener=Opener([Response(LOADER), Response(body, headers=headers)]))
    result = assets.check(refresh=True)
    assert result.status == "failed"
    assert result.artifact == good
    assert good.path.read_bytes() == SDK
    assert SentinelAssetManager(tmp_path, opener=Opener([])).check().artifact == good
    failure = json.loads((tmp_path / "last_check.json").read_text())
    assert failure["status"] == "failed"
    assert "SentinelSDK" not in json.dumps(failure)


def test_network_error_message_and_credentials_are_never_persisted(tmp_path):
    result = SentinelAssetManager(tmp_path, opener=Opener([OSError("secret-token-123")])).check(refresh=True)
    assert result.status == "failed"
    assert "secret-token-123" not in json.dumps(result.to_dict())
    assert "secret-token-123" not in (tmp_path / "last_check.json").read_text()


def test_malformed_http_response_is_a_safe_failure_preserving_candidate(tmp_path):
    good = manager(tmp_path).check(refresh=True).artifact
    assets = SentinelAssetManager(tmp_path, opener=Opener([http.client.IncompleteRead(b"secret-body", 10)]))
    result = assets.check(refresh=True)
    assert result.status == "failed"
    assert result.artifact == good
    assert "secret-body" not in json.dumps(result.to_dict())


def test_sdk_name_in_unrelated_script_is_not_a_valid_candidate(tmp_path):
    result = manager(tmp_path, sdk=b"console.log('SentinelSDK');").check(refresh=True)
    assert result.status == "failed"
    assert result.artifact is None


def test_download_deadline_bounds_slow_stream(tmp_path, monkeypatch):
    current = [0.0]
    monkeypatch.setattr(sentinel_assets.time, "monotonic", lambda: current[0])

    class SlowResponse(Response):
        def read1(self, size):
            current[0] += 2
            return super().read1(size)

    opener = Opener([SlowResponse(LOADER)])
    result = SentinelAssetManager(tmp_path, opener=opener, timeout_seconds=1).check(refresh=True)
    assert result.reason == "download_timeout"
    assert result.artifact is None
    assert len(opener.requests) == 1


def test_keyboard_cancellation_propagates_without_overwriting_good_cache(tmp_path):
    good = manager(tmp_path).check(refresh=True).artifact

    class CancelledOpener:
        def open(self, request, timeout):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        SentinelAssetManager(tmp_path, opener=CancelledOpener()).check(refresh=True)
    assert SentinelAssetManager(tmp_path, opener=Opener([])).check().artifact == good


@pytest.mark.parametrize("headers", [
    {"Content-Encoding": "gzip"},
    {"Content-Length": "2"},
    {"Content-Length": "invalid"},
    {"Content-Type": "application/json"},
])
def test_malformed_or_encoded_response_is_rejected_before_publication(tmp_path, headers):
    result = SentinelAssetManager(tmp_path, opener=Opener([
        Response(LOADER), Response(SDK, headers=headers),
    ])).check(refresh=True)
    assert result.status == "failed"
    assert not list(tmp_path.rglob("*.js"))


def test_explicit_refresh_repairs_corrupt_content_by_its_expected_hash(tmp_path):
    good = manager(tmp_path).check(refresh=True).artifact
    good.path.write_bytes(b"corrupt")
    repaired = manager(tmp_path).check(refresh=True)
    assert repaired.status == "refreshed"
    assert repaired.artifact.sha256 == good.sha256
    assert good.path.read_bytes() == SDK
    assert SentinelAssetManager(tmp_path, opener=Opener([])).check().artifact == repaired.artifact


@pytest.mark.parametrize("mutation", ["body", "metadata", "traversal"])
def test_corrupt_cache_is_not_returned_or_fetched_implicitly(tmp_path, mutation):
    artifact = manager(tmp_path).check(refresh=True).artifact
    if mutation == "body":
        artifact.path.write_bytes(b"corrupted")
    elif mutation == "metadata":
        (tmp_path / "index.json").write_text("{invalid")
    else:
        index = json.loads((tmp_path / "index.json").read_text())
        index["latest"] = "../../outside.json"
        (tmp_path / "index.json").write_text(json.dumps(index))
    result = SentinelAssetManager(tmp_path, opener=Opener([])).check()
    assert result.status == "corrupt"
    assert result.artifact is None


def test_download_size_bound_also_covers_stream_without_content_length(tmp_path):
    result = manager(tmp_path, sdk=SDK + b"x" * 500, max_sdk_bytes=200).check(refresh=True)
    assert result.status == "failed"
    assert result.reason == "response_too_large"
    assert not list(tmp_path.rglob("*.js"))


@pytest.mark.parametrize("location", [
    "https://evil.test/sentinel/20260810913b/sdk.js",
    "https://sentinel.openai.com/backend-api/sentinel/req",
    "https://sentinel.openai.com/sentinel/another/sdk.js",
    "http://sentinel.openai.com/sentinel/20260810913b/sdk.js",
])
def test_sdk_redirects_cannot_escape_discovered_resource(tmp_path, location):
    opener = Opener([Response(LOADER), Response(status=302, headers={"Location": location})])
    result = SentinelAssetManager(tmp_path, opener=opener).check(refresh=True)
    assert result.status == "failed"
    assert len(opener.requests) == 2


def test_redirect_url_with_control_characters_is_rejected_before_normalization(tmp_path):
    opener = Opener([
        Response(LOADER),
        Response(status=302, headers={"Location": "\n" + SDK_URL}),
        Response(SDK),
    ])
    result = SentinelAssetManager(tmp_path, opener=opener).check(refresh=True)
    assert result.status == "failed"
    assert len(opener.requests) == 2


def test_official_default_port_redirect_is_checked_and_allowed(tmp_path):
    target = SDK_URL.replace("sentinel.openai.com", "sentinel.openai.com:443")
    opener = Opener([Response(LOADER), Response(status=302, headers={"Location": target}), Response(SDK)])
    result = SentinelAssetManager(tmp_path, opener=opener).check(refresh=True)
    assert result.status == "refreshed"
    for _url, headers, timeout in opener.requests:
        assert not {key.lower() for key in headers} & {"cookie", "authorization"}
        assert 0 < timeout <= 15


def test_redirect_loop_is_bounded(tmp_path):
    opener = Opener([Response(status=302, headers={"Location": LOADER_URL}) for _ in range(4)])
    result = SentinelAssetManager(tmp_path, opener=opener, max_redirects=2).check(refresh=True)
    assert result.reason == "too_many_redirects"
    assert len(opener.requests) == 3


def test_implicit_redirect_by_transport_is_rejected(tmp_path):
    result = SentinelAssetManager(tmp_path, opener=Opener([
        Response(LOADER, url="https://evil.test/loader.js"),
    ])).check(refresh=True)
    assert result.status == "failed"


def test_atomic_cache_access_across_processes(tmp_path):
    # Spawn is safe when the surrounding suite already has background threads.
    # The barrier keeps independently imported workers in real lock contention.
    context = multiprocessing.get_context("spawn")
    start, output = context.Barrier(4), context.Queue()
    processes = [context.Process(target=_refresh_process, args=(str(tmp_path), start, output)) for _ in range(4)]
    for process in processes:
        process.start()
    try:
        results = [output.get(timeout=10) for _ in processes]
    finally:
        for process in processes:
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(5)
    assert results == [("refreshed", hashlib.sha256(SDK).hexdigest())] * 4
    assert all(process.exitcode == 0 for process in processes)
    result = SentinelAssetManager(tmp_path, opener=Opener([])).check()
    assert result.status == "cached"
    assert result.artifact.path.read_bytes() == SDK
    assert not list(tmp_path.rglob("*.tmp"))


def test_standalone_cli_reports_missing_cache_without_account_dependencies(tmp_path):
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run([
        sys.executable, str(root / "tools/diagnostics/check_sentinel_assets.py"),
        "--cache-dir", str(tmp_path), "--json",
    ], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["status"] == "missing"
    assert result["artifact"] is None
    assert not completed.stderr
