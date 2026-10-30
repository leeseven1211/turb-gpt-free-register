"""仅复用已证明公开的版本化静态资源；缓存失败始终回到浏览器正常网络。"""
from __future__ import annotations

import base64
import collections
import contextlib
import email.utils
import fcntl
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import queue
import re
import stat
import threading
import time
from urllib.parse import urlsplit
import uuid
import zlib

import requests
import websocket

logger = logging.getLogger('core.public_asset_cache')
_PUBLIC_ASSET_PREFIXES = (
    "https://chatgpt.com/cdn/assets/",
    "https://auth-cdn.oaistatic.com/assets/",
)
_DENIED_NAMES = ("sentinel", "challenge", "captcha", "turnstile", "arkose", "recaptcha")
_VERSIONED_FILE = re.compile(r"^[A-Za-z0-9_.-]+[-.][A-Za-z0-9_-]{8,64}\.(js|css)$")
_HEADER_NAMES = frozenset({
    "content-type", "cache-control", "vary", "date", "age", "expires", "etag",
    "last-modified", "content-encoding", "content-security-policy",
    "content-security-policy-report-only", "access-control-allow-origin",
    "access-control-allow-credentials", "access-control-expose-headers",
    "cross-origin-resource-policy", "cross-origin-embedder-policy",
    "x-content-type-options", "timing-allow-origin",
})


def _asset_type(url: str) -> str | None:
    """只接受两个确定目录下不含查询或身份参数的版本化 JS/CSS。"""
    try:
        p = urlsplit(url)
        if p.scheme != "https" or p.username or p.password or p.query or p.fragment:
            return None
        prefix = next((x for x in _PUBLIC_ASSET_PREFIXES if url.startswith(x)), None)
        if not prefix:
            return None
        name = url[len(prefix):]
        if not _VERSIONED_FILE.fullmatch(name) or any(x in name.lower() for x in _DENIED_NAMES):
            return None
        return "Script" if name.endswith(".js") else "Stylesheet"
    except (TypeError, ValueError):
        return None


def _headers(headers: dict) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in (headers or {}).items()}


def _request_bypasses_cache(headers: dict) -> bool:
    h = _headers(headers)
    directives = {part.strip().lower().replace(" ", "") for part in h.get("cache-control", "").split(",")}
    return bool({"range", "if-range", "if-match", "if-none-match", "if-modified-since", "if-unmodified-since"} & h.keys()
                or {"no-cache", "no-store", "max-age=0"} & directives or "no-cache" in h.get("pragma", "").lower())


def _request_has_credentials(headers: dict) -> bool:
    """带凭据请求不做本地回放；注册匿名验证仍遵循独立线路边界。"""
    return bool({"cookie", "authorization", "proxy-authorization"} & _headers(headers).keys())


def _unsafe_headers(headers: dict) -> bool:
    return any(k in _HEADER_NAMES and (len(v) > 4096 or "\n" in v or "\r" in v) for k, v in _headers(headers).items())


def _safe_headers(headers: dict) -> dict[str, str]:
    return {k: v for k, v in _headers(headers).items() if k in _HEADER_NAMES and len(v) <= 4096}


def _expiry(url: str, headers: dict, now: float, max_age: float) -> float | None:
    kind = _asset_type(url)
    h = _headers(headers)
    if not kind or _unsafe_headers(h) or any(k in h for k in ("set-cookie", "set-cookie2", "www-authenticate")):
        return None
    content_type = h.get("content-type", "").lower()
    mime = content_type.split(";", 1)[0].strip()
    if (kind == "Script" and mime not in {"application/javascript", "text/javascript"}) or (kind == "Stylesheet" and mime != "text/css"):
        return None
    if "charset=" in content_type and content_type.split("charset=", 1)[1].strip(' \"') not in {"utf-8", "utf8", "us-ascii"}:
        return None
    vary = {v.strip().lower() for v in h.get("vary", "").split(",") if v.strip()}
    if vary - {"accept-encoding"}:
        return None
    directives: dict[str, str] = {}
    for part in h.get("cache-control", "").split(","):
        key, _, value = part.strip().partition("=")
        key = key.lower()
        if key in directives:
            return None
        directives[key] = value.strip(' \"')
    if "public" not in directives or {"private", "no-store", "no-cache", "no-transform"} & directives.keys():
        return None
    age_value = directives.get("s-maxage", directives.get("max-age", ""))
    if not re.fullmatch(r"[0-9]{1,10}", age_value):
        return None
    try:
        if not re.fullmatch(r"[0-9]{1,12}", h.get("age", "0")):
            return None
        age = float(h.get("age", "0"))
        if "date" in h:
            date = email.utils.parsedate_to_datetime(h["date"]).timestamp()
            age = max(age, max(0.0, now - date))
        remaining = min(float(max_age), float(age_value) - age)
        return now + remaining if remaining > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _replay_headers(headers: dict, length: int, expires_at=None) -> list[dict[str, str]]:
    h = _safe_headers(headers)
    # CDP 正文已经解码，不能沿用压缩传输长度或原压缩表示的强校验器。
    for key in ("content-encoding", "etag"):
        h.pop(key, None)
    h["content-length"] = str(length)
    if expires_at is not None:
        # 重新回放不能把服务端原来的 max-age 再延长一个周期。
        remaining = max(0, int(expires_at - time.time()))
        h["cache-control"] = f"public, max-age={remaining}"
        h["date"] = email.utils.formatdate(usegmt=True)
        h["age"] = "0"
        h.pop("expires", None)
    return [{"name": k, "value": v} for k, v in h.items()]


class _AssetStore:
    """一个条目一个原子文件；进程锁只尝试一次，繁忙时按未命中处理。"""

    def __init__(self, directory, *, max_total_bytes, max_entry_bytes, max_entries, max_age_seconds):
        self.directory = Path(directory)
        if self.directory.is_symlink():
            raise ValueError("缓存目录不能是符号链接")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_total_bytes = max(1024, int(max_total_bytes))
        self.max_entry_bytes = max(1, int(max_entry_bytes))
        self.max_entries = max(1, int(max_entries))
        self.max_age = max(1, float(max_age_seconds))
        self._thread_lock = threading.Lock()
        self._known_lock = threading.Lock()
        self._known: set[str] = set()
        self.refresh()

    @staticmethod
    def key(url):
        return hashlib.sha256(("public-asset-v1:" + url).encode()).hexdigest()

    def refresh(self):
        with self._locked() as locked:
            if not locked:
                return
            names = {p.stem for p in self.directory.glob("*.asset") if re.fullmatch(r"[0-9a-f]{64}", p.stem) and not p.is_symlink()}
            with self._known_lock:
                self._known = names

    def knows(self, url):
        with self._known_lock:
            return self.key(url) in self._known

    @contextlib.contextmanager
    def _locked(self):
        if not self._thread_lock.acquire(blocking=False):
            yield False
            return
        fd = None
        try:
            fd = os.open(self.directory / ".lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            yield True
        finally:
            if fd is not None:
                os.close(fd)
            self._thread_lock.release()

    @contextlib.contextmanager
    def fill_claim(self, url):
        # 固定分片锁避免多进程下载同一文件；碰撞时跳过，不等待也不堆积锁文件。
        shard = int(self.key(url)[:2], 16) % 64
        fd = os.open(self.directory / f".fill-{shard:02x}.lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            yield True
        finally:
            os.close(fd)

    def _forget(self, path):
        with self._known_lock:
            self._known.discard(path.stem)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def get(self, url):
        path = self.directory / (self.key(url) + ".asset")
        with self._locked() as locked:
            if not locked:
                return None
            try:
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(fd, "rb") as f:
                    info = os.fstat(f.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size > self.max_entry_bytes * 4 // 3 + 32768:
                        raise ValueError("缓存条目尺寸不合法")
                    item = json.loads(f.read())
                now = time.time()
                if not isinstance(item, dict) or not isinstance(item.get("headers"), dict) or item.get("version") != 1 or item.get("url") != url or not math.isfinite(float(item.get("expires_at", 0))) or float(item.get("expires_at", 0)) <= now:
                    raise ValueError("缓存条目已失效")
                if _expiry(url, item.get("headers", {}), now, self.max_age) is None:
                    raise ValueError("缓存条目不符合公开规则")
                body = base64.b64decode(item["body"], validate=True)
                if len(body) > self.max_entry_bytes or hashlib.sha256(body).hexdigest() != item.get("sha256"):
                    raise ValueError("缓存正文校验不通过")
                item["body"] = body
                os.utime(path, None)
                return item
            except (OSError, ValueError, TypeError, KeyError):
                self._forget(path)
                return None

    def put(self, url, headers, body: bytes, upstream_bytes=0):
        now = time.time()
        expires = _expiry(url, headers, now, self.max_age)
        if not expires or not body or len(body) > self.max_entry_bytes:
            return False
        item = {"version": 1, "url": url, "headers": _safe_headers(headers), "expires_at": expires,
                "sha256": hashlib.sha256(body).hexdigest(), "body": base64.b64encode(body).decode("ascii"),
                "upstream_bytes": max(0, int(upstream_bytes)), "stored_at": now}
        content = json.dumps(item, ensure_ascii=True, separators=(",", ":")).encode()
        if len(content) > self.max_total_bytes:
            return False
        path = self.directory / (self.key(url) + ".asset")
        temp = self.directory / (uuid.uuid4().hex + ".tmp")
        with self._locked() as locked:
            if not locked:
                return False
            try:
                fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp, path)
                entries = sorted((p for p in self.directory.glob("*.asset") if re.fullmatch(r"[0-9a-f]{64}", p.stem) and not p.is_symlink()), key=lambda p: p.stat().st_mtime)
                total = sum(p.stat().st_size for p in entries)
                while len(entries) > self.max_entries or total > self.max_total_bytes:
                    old = entries.pop(0)
                    total -= old.stat().st_size
                    self._forget(old)
                with self._known_lock:
                    if path.exists():
                        self._known.add(path.stem)
                return path.exists()
            finally:
                temp.unlink(missing_ok=True)


class PublicAssetCache:
    """为当前 Roxy 页面提供公共 JS/CSS 缓存，默认关闭。

    proxy_url=None 不启用匿名下载；无代理任务必须额外显式传 allow_direct=True。
    anonymous_fetcher 是受信任的内部测试/接入点，契约为无凭据、无重定向、有限尺寸。
    它接受 (url, max_bytes, stop_event)，返回 status/headers/body/url/encoded_bytes。
    """

    def __init__(self, debugger_address, cache_dir, *, mode="off", max_total_bytes=256 * 1024 * 1024,
                 max_entry_bytes=10 * 1024 * 1024, max_entries=1000, max_age_seconds=86400,
                 proxy_url=None, allow_direct=False, anonymous_fetcher=None, ready_timeout=3.0,
                 request_budget=0.10, metadata_timeout=0.25, target_id=None):
        self.debugger_address = str(debugger_address or "")
        self.mode = mode if mode in {"off", "observe", "enabled"} else "off"
        self.cache_dir = cache_dir
        self._store_options = dict(max_total_bytes=max_total_bytes, max_entry_bytes=max_entry_bytes,
                                   max_entries=max_entries, max_age_seconds=max_age_seconds)
        self._max_entry = max(1, int(max_entry_bytes))
        self._max_age = max(1, float(max_age_seconds))
        self._proxy_url = proxy_url
        self._allow_direct = bool(allow_direct)
        self._anonymous_fetcher = anonymous_fetcher
        self._ready_timeout = max(.1, min(float(ready_timeout), 10))
        self._request_budget = max(.01, min(float(request_budget), .5))
        self._metadata_timeout = max(.01, min(float(metadata_timeout), 2.0))
        self.target_id = target_id
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = None
        self._workers = []
        self._ws = None
        self._store = None
        self._lock = threading.Lock()
        self._stats = collections.Counter()
        self._sources = collections.OrderedDict()
        self._requests = collections.OrderedDict()
        self._pending = {}
        self._paused = {}
        self._lookup_queue = queue.Queue(maxsize=32)
        self._background_queue = queue.Queue(maxsize=32)
        self._results = queue.Queue(maxsize=64)
        self._fill_pending = set()
        self._fill_seen = set()
        self._counter = 0
        self._running = False
        self._stats_frozen = False
        self._anonymous_active = 0

    def _count(self, key, amount=1):
        with self._lock:
            if not self._stats_frozen:
                self._stats[key] += amount

    def _source(self, rid, source):
        if rid:
            with self._lock:
                self._sources[rid] = source
                self._sources.move_to_end(rid)
                while len(self._sources) > 4096:
                    self._sources.popitem(last=False)

    def request_source(self, network_id, target_id=None):
        if target_id and self.target_id and target_id != self.target_id:
            return "network"
        with self._lock:
            source = self._sources.get(str(network_id or ""), "network")
            return "unknown" if source == "pending" else source

    def snapshot(self):
        with self._lock:
            result = dict(self._stats)
        for key in ("hits", "misses", "stores", "rejected", "errors", "local_served_bytes",
                    "avoided_upstream_bytes", "anonymous_fill_bytes", "anonymous_requests", "native_hits"):
            result.setdefault(key, 0)
        result.setdefault("anonymous_accounting_complete", True)
        result.setdefault("replay_accounting_complete", True)
        return {"mode": self.mode, "running": self._running, "ready": self._ready.is_set() and self._running, **result}

    def start(self):
        if self.mode == "off":
            return False
        if self._thread is not None:
            return self._running
        try:
            self._store = _AssetStore(self.cache_dir, **self._store_options)
            for name, queue_ in (("lookup", self._lookup_queue), ("background", self._background_queue)):
                worker = threading.Thread(target=self._work, args=(name, queue_), daemon=True, name="公共资源缓存-" + name)
                worker.start()
                self._workers.append(worker)
            self._thread = threading.Thread(target=self._run, daemon=True, name="公共资源缓存-CDP")
            self._thread.start()
            if not self._ready.wait(self._ready_timeout) or not self._running:
                self.stop()
                return False
            return True
        except Exception:
            self._count("errors")
            self.stop()
            logger.warning("[公共资源缓存] 启动失败，继续浏览器正常加载")
            return False

    def stop(self):
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        if self._thread is not None and self._thread.is_alive() and self._ws is not None:
            try:
                self._ws.close(timeout=.1)
            except Exception:
                pass
        deadline = time.monotonic() + 2.5
        for worker in self._workers:
            worker.join(timeout=max(0, deadline - time.monotonic()))
        self._running = False
        self._invalidate_pending_fulfills()
        with self._lock:
            if not self._stats_frozen:
                # 无法终止的下载只保留已读取字节下界，禁止事后继续改变任务计量。
                self._stats["anonymous_accounting_complete"] = self._anonymous_active == 0
                self._stats_frozen = True
        return self.snapshot()

    def _send(self, method, params=None, tag=None):
        self._counter += 1
        ident = self._counter
        if tag is not None:
            self._pending[ident] = (tag, time.monotonic() + 2.0)
        try:
            self._ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        except Exception:
            if tag and tag[0] == "fulfill":
                self._invalidate_fulfill(tag)
            raise
        return ident

    def _invalidate_fulfill(self, tag):
        with self._lock:
            if self._sources.get(tag[2]) == "pending":
                self._sources[tag[2]] = "unknown"
                if not self._stats_frozen:
                    self._stats["unconfirmed_fulfills"] += 1
                    self._stats["replay_accounting_complete"] = False

    def _invalidate_pending_fulfills(self):
        for tag, _ in list(self._pending.values()):
            if tag[0] == "fulfill":
                self._invalidate_fulfill(tag)

    def _connect(self):
        address = self.debugger_address
        p = urlsplit("http://" + address)
        if p.hostname not in {"127.0.0.1", "localhost", "::1"} or p.username or p.password or not p.port or p.path:
            raise ValueError("只连接本机浏览器调试端口")
        with requests.Session() as session:
            session.trust_env = False
            response = session.get("http://" + address + "/json/list", timeout=(1, 1))
            response.raise_for_status()
            pages = response.json()
        page = next(x for x in pages if x.get("type") == "page" and not x.get("url", "").startswith("chrome-extension:")
                    and (not self.target_id or x.get("id") == self.target_id))
        self.target_id = page["id"]
        endpoint = page["webSocketDebuggerUrl"]
        wp = urlsplit(endpoint)
        if wp.scheme != "ws" or wp.hostname not in {"127.0.0.1", "localhost", "::1"} or wp.port != p.port:
            raise ValueError("浏览器调试连接地址不匹配")
        self._ws = websocket.create_connection(endpoint, timeout=.05, suppress_origin=True, http_proxy_host=None)

    def _run(self):
        try:
            self._connect()
            self._send("Network.enable", {"maxPostDataSize": 0, "maxResourceBufferSize": self._max_entry,
                                           "maxTotalBufferSize": self._max_entry * 2}, ("network_ready",))
            while not self._stop.is_set():
                self._drain_results()
                self._expire_paused()
                self._expire_commands()
                self._expire_metadata_waits()
                try:
                    raw = self._ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not raw:
                    break
                self._event(json.loads(raw))
        except Exception:
            self._count("errors")
            logger.warning("[公共资源缓存] 连接结束，缓存已停止，浏览器继续正常加载")
        finally:
            self._running = False
            self._stop.set()
            self._invalidate_pending_fulfills()
            if self._ws is not None:
                try:
                    for rid in list(self._paused):
                        self._continue(rid)
                    self._send("Fetch.disable")
                except Exception:
                    pass
                try:
                    self._ws.close(timeout=.1)
                except Exception:
                    pass
            self._ready.set()

    def _record(self, rid):
        rec = self._requests.setdefault(rid, {})
        self._requests.move_to_end(rid)
        while len(self._requests) > 2048:
            self._requests.popitem(last=False)
        return rec

    def _continue(self, rid):
        self._paused.pop(rid, None)
        self._send("Fetch.continueRequest", {"requestId": rid})

    def _event(self, msg):
        if "id" in msg:
            item = self._pending.pop(msg["id"], None)
            if item:
                self._reply(item[0], msg)
            return
        method = msg.get("method")
        p = msg.get("params") or {}
        rid = str(p.get("requestId") or "")
        if method == "Fetch.requestPaused":
            request = p.get("request") or {}
            url = request.get("url", "")
            if self.mode != "enabled" or request.get("method") != "GET" or _request_has_credentials(request.get("headers") or {}) or _request_bypasses_cache(request.get("headers") or {}) or _asset_type(url) != p.get("resourceType") or not p.get("networkId"):
                self._continue(rid)
                return
            # 冷请求不等待磁盘或下载；其它进程新增条目由后台周期刷新索引。
            if not self._store.knows(url):
                self._count("misses")
                self._continue(rid)
                return
            self._paused[rid] = {"deadline": time.monotonic() + self._request_budget, "network_id": p["networkId"], "url": url}
            try:
                self._lookup_queue.put_nowait((rid, url))
            except queue.Full:
                self._count("misses")
                self._continue(rid)
            return
        if not rid:
            return
        if method == "Network.requestServedFromCache":
            self._source(rid, "native")
            self._count("native_hits")
            return
        rec = self._record(rid)
        if method == "Network.requestWillBeSent":
            r = p.get("request") or {}
            rec.update(url=r.get("url", ""), method=r.get("method"), resource_type=p.get("type"))
            rec["bypass"] = bool(rec.get("bypass") or _request_bypasses_cache(r.get("headers") or {}))
            rec["credentialed"] = bool(rec.get("credentialed") or _request_has_credentials(r.get("headers") or {}))
            rec["redirected"] = bool(rec.get("redirected") or p.get("redirectResponse"))
        elif method == "Network.requestWillBeSentExtraInfo":
            h = _headers(p.get("headers") or {})
            cookies = p.get("associatedCookies") or []
            rec["request_extra"] = True
            rec["bypass"] = bool(rec.get("bypass") or _request_bypasses_cache(h))
            rec["credentialed"] = bool(rec.get("credentialed") or _request_has_credentials(h) or any(not x.get("blockedReasons") for x in cookies))
        elif method == "Network.responseReceivedExtraInfo":
            h = _headers(p.get("headers") or {})
            rec["response_extra"] = True
            rec["unsafe_headers"] = bool(rec.get("unsafe_headers") or _unsafe_headers(h))
            rec["response_cookie"] = bool(rec.get("response_cookie") or any(k in h for k in ("set-cookie", "set-cookie2", "www-authenticate")))
            rec["extra_headers"] = _safe_headers(h)
        elif method == "Network.responseReceived":
            r = p.get("response") or {}
            h = _headers(r.get("headers") or {})
            rec["unsafe_headers"] = bool(rec.get("unsafe_headers") or _unsafe_headers(h))
            old_url = rec.get("url")
            rec.update(url=r.get("url", ""), resource_type=p.get("type"), status=r.get("status"), headers=_safe_headers(h))
            rec["redirected"] = bool(rec.get("redirected") or (old_url and old_url != rec["url"]))
            rec["response_cookie"] = bool(rec.get("response_cookie") or "set-cookie" in h or "set-cookie2" in h or "www-authenticate" in h)
            rec["service_worker"] = bool(r.get("fromServiceWorker"))
            if r.get("fromDiskCache") or r.get("fromPrefetchCache"):
                self._source(rid, "native")
                self._count("native_hits")
        elif method == "Network.loadingFinished":
            rec["complete"] = True
            rec["upstream_bytes"] = max(0, int(p.get("encodedDataLength") or 0))
        elif method == "Network.loadingFailed":
            rec["done"] = True
        else:
            return
        self._maybe_store(rid, rec)

    def _maybe_store(self, rid, rec):
        if not rec.get("complete") or rec.get("done"):
            return
        url = rec.get("url", "")
        if rec.get("method") != "GET" or rec.get("bypass") or rec.get("unsafe_headers") or not _asset_type(url) or rec.get("resource_type") != _asset_type(url) or rec.get("status") != 200 or rec.get("redirected") or rec.get("service_worker") or rec.get("response_cookie"):
            rec["done"] = True
            return
        headers = {**rec.get("headers", {}), **rec.get("extra_headers", {})}
        if _expiry(url, headers, time.time(), self._max_age) is None:
            rec["done"] = True
            self._count("rejected")
            return
        if self.mode == "observe":
            rec["done"] = True
            self._count("eligible")
            return
        if self.request_source(rid) == "local" or self._store.knows(url):
            rec["done"] = True
            return
        if rec.get("credentialed"):
            # 同类带凭据请求不会本地回放，再匿名下载一份也无法减少后续流量。
            rec.pop("metadata_deadline", None)
            rec["done"] = True
            self._count("credentialed_skipped")
            return
        metadata_complete = rec.get("request_extra") and rec.get("response_extra")
        if not metadata_complete:
            # ExtraInfo 可能晚于 loadingFinished；只等待元数据，绝不暂停业务请求。
            deadline = rec.setdefault("metadata_deadline", time.monotonic() + self._metadata_timeout)
            if time.monotonic() < deadline:
                return
            self._count("metadata_timeouts")
        rec.pop("metadata_deadline", None)
        rec["done"] = True
        if self.request_source(rid) == "network" and metadata_complete:
            self._send("Network.getResponseBody", {"requestId": rid}, ("body", url, headers, rec.get("upstream_bytes", 0)))
        elif self._anonymous_fetcher or self._proxy_url or self._allow_direct:
            # 不带身份的独立校验下载只在浏览器完成资源后排队，绝不延长 paused 请求。
            if url not in self._fill_seen:
                self._fill_seen.add(url)
                if len(self._fill_seen) > 2048:
                    self._fill_seen.pop()
                self._queue_background(("anonymous", url, rec.get("upstream_bytes", 0)))

    def _expire_metadata_waits(self):
        """用 CDP 事件循环收口已完成资源的元数据等待，不增加后台下载线程。"""
        now = time.monotonic()
        for rid, rec in list(self._requests.items()):
            deadline = rec.get("metadata_deadline")
            if not rec.get("done") and deadline is not None and now >= deadline:
                self._maybe_store(rid, rec)

    def _reply(self, tag, msg):
        kind = tag[0]
        if "error" in msg:
            self._count("errors")
            if kind in {"network_ready", "fetch_ready"}:
                self._stop.set()
            elif kind == "fulfill":
                self._source(tag[2], "network")
                self._continue(tag[1])
            return
        if kind == "network_ready":
            if self.mode == "enabled":
                patterns = [{"urlPattern": prefix + "*" + ext, "resourceType": typ, "requestStage": "Request"}
                            for prefix in _PUBLIC_ASSET_PREFIXES for ext, typ in ((".js", "Script"), (".css", "Stylesheet"))]
                self._send("Fetch.enable", {"patterns": patterns}, ("fetch_ready",))
            else:
                self._running = True
                self._ready.set()
        elif kind == "fetch_ready":
            self._running = True
            self._ready.set()
        elif kind == "body":
            try:
                r = msg.get("result") or {}
                text = r.get("body", "")
                if len(text) > self._max_entry * 4 // 3 + 8:
                    raise ValueError("资源超过单项限制")
                body = base64.b64decode(text, validate=True) if r.get("base64Encoded") else text.encode("utf-8")
                if len(body) > self._max_entry:
                    raise ValueError("资源超过单项限制")
                self._queue_background(("store", tag[1], tag[2], body, tag[3]))
            except (ValueError, TypeError):
                self._count("rejected")
        elif kind == "fulfill":
            if self._stop.is_set():
                self._invalidate_fulfill(tag)
                return
            self._source(tag[2], "local")
            self._count("hits")
            self._count("local_served_bytes", tag[3])
            self._count("avoided_upstream_bytes", tag[4])

    def _queue_background(self, item):
        try:
            self._background_queue.put_nowait(item)
        except queue.Full:
            self._count("queue_skipped")

    def _drain_results(self):
        while True:
            try:
                rid, item = self._results.get_nowait()
            except queue.Empty:
                return
            paused = self._paused.pop(rid, None)
            if not paused:
                continue
            if not item or time.monotonic() >= paused["deadline"]:
                self._count("misses")
                self._continue(rid)
                continue
            body = item["body"]
            self._source(paused["network_id"], "pending")
            self._send("Fetch.fulfillRequest", {"requestId": rid, "responseCode": 200,
                       "responseHeaders": _replay_headers(item["headers"], len(body), item.get("expires_at")), "body": base64.b64encode(body).decode("ascii")},
                       ("fulfill", rid, paused["network_id"], len(body), item.get("upstream_bytes", 0)))

    def _expire_paused(self):
        now = time.monotonic()
        for rid, item in list(self._paused.items()):
            if now >= item["deadline"]:
                self._count("lookup_timeouts")
                self._count("misses")
                self._continue(rid)

    def _expire_commands(self):
        now = time.monotonic()
        for ident, (tag, deadline) in list(self._pending.items()):
            if now >= deadline:
                self._pending.pop(ident, None)
                if tag[0] == "fulfill":
                    self._invalidate_fulfill(tag)
                if tag[0] in {"network_ready", "fetch_ready", "fulfill"}:
                    # fulfill 结果未知时解除整个本连接拦截，避免重复完成请求。
                    self._stop.set()
                self._count("command_timeouts")

    def _work(self, name, queue_):
        last_refresh = 0.0
        while not self._stop.is_set():
            try:
                if name == "background" and time.monotonic() - last_refresh > 1:
                    self._store.refresh()
                    last_refresh = time.monotonic()
                item = queue_.get(timeout=.1)
            except queue.Empty:
                continue
            except Exception:
                self._count("errors")
                continue
            try:
                if name == "lookup":
                    result = self._store.get(item[1])
                    try:
                        self._results.put_nowait((item[0], result))
                    except queue.Full:
                        pass
                elif item[0] == "store":
                    if not self._stop.is_set() and self._store.put(*item[1:]):
                        self._count("stores")
                elif item[0] == "anonymous" and not self._stop.is_set():
                    with self._store.fill_claim(item[1]) as claimed:
                        if not claimed or self._store.get(item[1]) is not None:
                            self._count("coalesced_fills")
                            continue
                        with self._lock:
                            if self._stop.is_set():
                                continue
                            self._anonymous_active += 1
                        try:
                            result = self._anonymous_download(item[1])
                            if result and not self._stop.is_set() and self._store.put(item[1], result["headers"], result["body"], item[2]):
                                self._count("stores")
                        finally:
                            with self._lock:
                                self._anonymous_active -= 1
            except Exception:
                self._count("errors")
            finally:
                queue_.task_done()

    def _anonymous_download(self, url):
        if not _asset_type(url) or self._stop.is_set() or not (self._anonymous_fetcher or self._proxy_url or self._allow_direct):
            return None
        self._count("anonymous_requests")
        if self._anonymous_fetcher:
            result = self._anonymous_fetcher(url, self._max_entry, self._stop)
            if result:
                self._count("anonymous_fill_bytes", max(0, int(result.get("encoded_bytes", 0))))
                if result.get("url") == url and result.get("status") == 200 and isinstance(result.get("body"), bytes) and len(result["body"]) <= self._max_entry:
                    return result
            return None
        if not self._proxy_url and not self._allow_direct:
            return None
        deadline = time.monotonic() + 8
        with requests.Session() as session:
            session.trust_env = False
            session.auth = None
            session.cookies.clear()
            session.headers.update({"Accept": "*/*", "Accept-Encoding": "gzip, identity"})
            if self._proxy_url:
                session.proxies.update({"https": self._proxy_url, "http": self._proxy_url})
            with session.get(url, timeout=(2, 2), allow_redirects=False, stream=True) as response:
                if response.status_code != 200 or response.url != url or _expiry(url, response.headers, time.time(), self._max_age) is None:
                    self._count("rejected")
                    return None
                encoding = response.headers.get("Content-Encoding", "identity").lower()
                if encoding not in {"", "identity", "gzip"}:
                    self._count("rejected")
                    return None
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
                length = response.headers.get("Content-Length", "")
                if length.isdigit() and int(length) > self._max_entry:
                    self._count("rejected")
                    return None
                body = bytearray()
                encoded_bytes = 0
                while not self._stop.is_set() and time.monotonic() < deadline:
                    # read1 不等待凑满整块；总预算加最多一次2秒socket等待即返回。
                    chunk = response.raw.read1(16384, decode_content=False)
                    if not chunk:
                        if decoder is not None and (not decoder.eof or decoder.unused_data):
                            self._count("rejected")
                            return None
                        return {"status": 200, "url": url, "headers": dict(response.headers), "body": bytes(body), "encoded_bytes": encoded_bytes}
                    self._count("anonymous_fill_bytes", len(chunk))
                    encoded_bytes += len(chunk)
                    if encoded_bytes > self._max_entry:
                        self._count("rejected")
                        return None
                    body.extend(decoder.decompress(chunk, self._max_entry - len(body) + 1) if decoder else chunk)
                    if len(body) > self._max_entry or (decoder is not None and decoder.unused_data):
                        self._count("rejected")
                        return None
        self._count("anonymous_timeouts")
        return None
