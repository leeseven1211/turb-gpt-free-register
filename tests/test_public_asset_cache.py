"""公共资源缓存的准入、并发、故障回源与下载隔离测试。"""
import base64
import concurrent.futures
import email.utils
import gzip
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

import websocket
from unittest.mock import patch

import requests

from core import public_asset_cache as cache_module
from core.public_asset_cache import PublicAssetCache, _AssetStore, _asset_type, _expiry, _replay_headers

URL = "https://chatgpt.com/cdn/assets/entry.client-1234abcd.js"
CSS_URL = "https://auth-cdn.oaistatic.com/assets/root-1234abcd.css"
PUBLIC = {"content-type": "application/javascript", "cache-control": "public, max-age=3600",
          "access-control-allow-origin": "*", "x-content-type-options": "nosniff"}
BODY = b"window.publicAsset = 42;"


class _TempFiles(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="turb-public-cache-test-"))

    def tearDown(self):
        # 精确清理测试创建的文件，禁止递归删除。
        for path in self.directory.glob("*"):
            if path.is_file() or path.is_symlink():
                path.unlink()
        self.directory.rmdir()

    def store(self, **overrides):
        return _AssetStore(self.directory, **{
            "max_total_bytes": 1024 * 1024, "max_entry_bytes": 4096,
            "max_entries": 10, "max_age_seconds": 120, **overrides,
        })


class PublicAssetAdmissionTests(unittest.TestCase):
    def test_only_versioned_public_js_and_css_urls_are_candidates(self):
        self.assertEqual(_asset_type(URL), "Script")
        self.assertEqual(_asset_type(CSS_URL), "Stylesheet")
        for url in (
            "http://chatgpt.com/cdn/assets/root-1234abcd.js",
            URL + "?session=private", URL + "#fragment",
            URL.replace("chatgpt.com", "chatgpt.com.invalid"),
            URL.replace("/cdn/assets/", "/api/auth/"),
            URL.replace("entry.client-1234abcd.js", "entry.js"),
            URL.replace("entry.client-1234abcd.js", "sentinel-1234abcd.js"),
            URL.replace("entry.client-1234abcd.js", "../entry.client-1234abcd.js"),
            URL.replace(".js", ".woff2"),
            "https://auth.openai.com/assets/root-1234abcd.js",
        ):
            with self.subTest(url=url):
                self.assertIsNone(_asset_type(url))

    def test_rejects_private_sensitive_vary_and_non_script_representations(self):
        self.assertEqual(_expiry(URL, PUBLIC, 1000, 120), 1120)
        for extra in (
            {"cache-control": "max-age=3600"}, {"cache-control": "public, no-store, max-age=3600"},
            {"cache-control": "public, private, max-age=3600"}, {"cache-control": "public, no-cache, max-age=3600"},
            {"cache-control": "public, max-age=3600, max-age=7200"},
            {"vary": "Cookie"}, {"vary": "Origin"}, {"vary": "*"}, {"vary": "User-Agent"},
            {"set-cookie": "private=redacted"}, {"www-authenticate": "Bearer"},
            {"content-type": "text/html"}, {"content-type": "application/javascript; charset=shift_jis"},
            {"cache-control": "public, max-age=0"}, {"age": "3600"},
        ):
            with self.subTest(extra=extra):
                self.assertIsNone(_expiry(URL, {**PUBLIC, **extra}, 1000, 120))
        self.assertEqual(_expiry(URL, {**PUBLIC, "vary": "Accept-Encoding", "age": "3550"}, 1000, 120), 1050)

    def test_age_and_date_cannot_extend_remaining_freshness(self):
        headers = {**PUBLIC, "date": email.utils.formatdate(1000, usegmt=True), "age": "10"}
        self.assertEqual(_expiry(URL, headers, 4550, 120), 4600)
        self.assertIsNone(_expiry(URL, headers, 4600, 120))
        for age in ("NaN", "inf", "-3", "garbage"):
            with self.subTest(age=age):
                self.assertIsNone(_expiry(URL, {**PUBLIC, "age": age}, 1000, 120))


class PublicAssetStoreTests(_TempFiles):
    def test_same_url_round_trip_and_different_version_is_a_miss(self):
        store = self.store()
        self.assertTrue(store.put(URL, PUBLIC, BODY, 123))
        self.assertEqual(store.get(URL)["body"], BODY)
        self.assertEqual(store.get(URL)["upstream_bytes"], 123)
        self.assertIsNone(store.get(URL.replace("1234abcd", "1234abce")))

    def test_corrupt_body_and_expired_metadata_are_removed(self):
        store = self.store()
        path = self.directory / (store.key(URL) + ".asset")
        for mutate in (lambda v: v.update(body=base64.b64encode(b"altered").decode()),
                       lambda v: v.update(expires_at=0), lambda v: v.update(expires_at=float("nan"))):
            self.assertTrue(store.put(URL, PUBLIC, BODY))
            data = json.loads(path.read_text())
            mutate(data)
            path.write_text(json.dumps(data))
            self.assertIsNone(store.get(URL))
            self.assertFalse(path.exists())

    def test_malformed_metadata_is_a_miss_not_a_crash(self):
        store = self.store()
        path = self.directory / (store.key(URL) + ".asset")
        for invalid in ([], {"expires_at": float("nan")}, {"version": 1, "url": URL, "expires_at": time.time() + 60, "headers": []}):
            path.write_text(json.dumps(invalid))
            self.assertIsNone(store.get(URL))
            self.assertFalse(path.exists())

    def test_lru_limit_never_deletes_unrelated_files(self):
        store = self.store(max_entries=1)
        unrelated = self.directory / "keep-me.asset"
        unrelated.write_text("用户文件")
        self.assertTrue(store.put(URL, PUBLIC, BODY))
        newer = URL.replace("1234abcd", "2234abcd")
        self.assertTrue(store.put(newer, PUBLIC, BODY))
        self.assertEqual(unrelated.read_text(), "用户文件")
        self.assertIsNone(store.get(URL))
        self.assertEqual(store.get(newer)["body"], BODY)

    def test_parallel_store_instances_only_expose_complete_valid_entries(self):
        stores = [self.store() for _ in range(4)]
        urls = [URL.replace("1234abcd", f"{i:08x}") for i in range(8)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            outcomes = list(executor.map(lambda pair: stores[pair[0] % 4].put(pair[1], PUBLIC, BODY), enumerate(urls)))
        self.assertTrue(any(outcomes))
        for ok, url in zip(outcomes, urls):
            if ok:
                item = stores[0].get(url)
                self.assertEqual(item["body"], BODY)
        self.assertFalse(list(self.directory.glob("*.tmp")))

    def test_entry_size_and_symlink_do_not_overwrite_external_data(self):
        store = self.store(max_entry_bytes=8)
        self.assertFalse(store.put(URL, PUBLIC, BODY))
        other = self.directory / "outside.txt"
        other.write_text("保留")
        link = self.directory / (store.key(URL) + ".asset")
        link.symlink_to(other)
        self.assertIsNone(store.get(URL))
        self.assertEqual(other.read_text(), "保留")


class _Wire:
    def __init__(self):
        self.commands = []

    def send(self, text):
        self.commands.append(json.loads(text))

    def close(self, **kwargs):
        pass


class PublicAssetEventTests(_TempFiles):
    def client(self, **kwargs):
        c = PublicAssetCache("127.0.0.1:9222", self.directory, mode="enabled", **kwargs)
        c._store = self.store()
        c._ws = _Wire()
        return c

    def event(self, c, method, **params):
        c._event({"method": method, "params": params})

    def complete(self, c, *, request_headers=None, response_headers=None, actual_headers=True, method="GET"):
        self.event(c, "Network.requestWillBeSent", requestId="net-1", type="Script", request={"url": URL, "method": method, "headers": {}})
        if actual_headers:
            self.event(c, "Network.requestWillBeSentExtraInfo", requestId="net-1", headers=request_headers or {}, associatedCookies=[])
        self.event(c, "Network.responseReceived", requestId="net-1", type="Script", response={"url": URL, "status": 200, "headers": response_headers or PUBLIC})
        if actual_headers:
            self.event(c, "Network.responseReceivedExtraInfo", requestId="net-1", headers=response_headers or PUBLIC, statusCode=200)
        self.event(c, "Network.loadingFinished", requestId="net-1", encodedDataLength=321)

    def test_observe_never_captures_body_or_starts_anonymous_download(self):
        c = PublicAssetCache("127.0.0.1:9222", self.directory, mode="observe", allow_direct=True)
        c._store = self.store()
        c._ws = _Wire()
        self.complete(c)
        self.assertEqual(c.snapshot()["eligible"], 1)
        self.assertFalse(c._ws.commands)
        self.assertTrue(c._background_queue.empty())
        self.assertFalse(list(self.directory.glob("*.asset")))

    def test_only_actual_extra_headers_prove_body_is_uncredentialed(self):
        c = self.client()
        self.complete(c)
        self.assertEqual(c._ws.commands[-1]["method"], "Network.getResponseBody")
        for headers in ({"Cookie": "private=hidden"}, {"Authorization": "Bearer hidden"}):
            c = self.client()
            self.complete(c, request_headers=headers)
            self.assertFalse(c._ws.commands)
        c = self.client()
        self.complete(c, actual_headers=False)
        self.assertFalse(c._ws.commands)

    def test_credentialed_resources_never_add_anonymous_downloads(self):
        for headers in ({"Cookie": "private=hidden"}, {"Authorization": "Bearer hidden"}, {"Proxy-Authorization": "Basic hidden"}):
            with self.subTest(headers=headers):
                c = self.client(proxy_url="http://127.0.0.1:55555")
                self.complete(c, request_headers=headers)
                self.assertFalse(c._ws.commands)
                self.assertTrue(c._background_queue.empty())
                self.assertEqual(c.snapshot()["credentialed_skipped"], 1)

    def test_initial_credential_headers_cannot_be_erased_by_late_extra_info(self):
        c = self.client(proxy_url="http://127.0.0.1:55555")
        self.event(c, "Network.requestWillBeSent", requestId="net-1", type="Script", request={"url": URL, "method": "GET", "headers": {"Cookie": "private=hidden"}})
        self.event(c, "Network.requestWillBeSentExtraInfo", requestId="net-1", headers={}, associatedCookies=[])
        self.event(c, "Network.responseReceived", requestId="net-1", type="Script", response={"url": URL, "status": 200, "headers": PUBLIC})
        self.event(c, "Network.loadingFinished", requestId="net-1", encodedDataLength=321)
        self.assertFalse(c._ws.commands)
        self.assertTrue(c._background_queue.empty())
        self.assertEqual(c.snapshot()["credentialed_skipped"], 1)

    def test_late_extra_info_reuses_completed_body_without_anonymous_copy(self):
        for order in (("request", "response"), ("response", "request")):
            with self.subTest(order=order):
                c = self.client(proxy_url="http://127.0.0.1:55555")
                self.complete(c, actual_headers=False)
                self.assertFalse(c._ws.commands)
                self.assertTrue(c._background_queue.empty())
                for event in order:
                    if event == "request":
                        self.event(c, "Network.requestWillBeSentExtraInfo", requestId="net-1", headers={}, associatedCookies=[])
                    else:
                        self.event(c, "Network.responseReceivedExtraInfo", requestId="net-1", headers=PUBLIC, statusCode=200)
                self.assertEqual([command["method"] for command in c._ws.commands], ["Network.getResponseBody"])
                self.assertTrue(c._background_queue.empty())
                self.assertNotIn("metadata_deadline", c._requests["net-1"])

    def test_late_cookie_info_cancels_metadata_wait_without_anonymous_copy(self):
        c = self.client(proxy_url="http://127.0.0.1:55555")
        self.complete(c, actual_headers=False)
        self.event(c, "Network.requestWillBeSentExtraInfo", requestId="net-1", headers={"Cookie": "private=hidden"}, associatedCookies=[])
        c._expire_metadata_waits()
        self.assertTrue(c._requests["net-1"]["done"])
        self.assertNotIn("metadata_deadline", c._requests["net-1"])
        self.assertFalse(c._ws.commands)
        self.assertTrue(c._background_queue.empty())

    def test_missing_extra_info_times_out_once_and_keeps_anonymous_fallback(self):
        c = self.client(proxy_url="http://127.0.0.1:55555")
        self.complete(c, actual_headers=False)
        deadline = c._requests["net-1"]["metadata_deadline"]
        with patch.object(cache_module.time, "monotonic", return_value=deadline - .001):
            c._expire_metadata_waits()
        self.assertTrue(c._background_queue.empty())
        with patch.object(cache_module.time, "monotonic", return_value=deadline + .001):
            c._expire_metadata_waits()
            c._expire_metadata_waits()
        self.assertEqual(c._background_queue.get_nowait(), ("anonymous", URL, 321))
        self.assertTrue(c._background_queue.empty())
        self.assertEqual(c.snapshot()["metadata_timeouts"], 1)
        self.event(c, "Network.requestWillBeSentExtraInfo", requestId="net-1", headers={}, associatedCookies=[])
        self.event(c, "Network.responseReceivedExtraInfo", requestId="net-1", headers=PUBLIC, statusCode=200)
        self.assertFalse(c._ws.commands)

    def test_missing_extra_info_without_fill_route_finishes_without_network(self):
        c = self.client()
        self.complete(c, actual_headers=False)
        deadline = c._requests["net-1"]["metadata_deadline"]
        with patch.object(cache_module.time, "monotonic", return_value=deadline + .001):
            c._expire_metadata_waits()
        self.assertTrue(c._requests["net-1"]["done"])
        self.assertNotIn("metadata_deadline", c._requests["net-1"])
        self.assertTrue(c._background_queue.empty())
        self.assertFalse(c._ws.commands)

    def test_set_cookie_and_partial_or_non_get_responses_never_fill(self):
        for method, request_headers, response_headers in (
            ("GET", {}, {**PUBLIC, "Set-Cookie": "private=hidden"}),
            ("POST", {}, PUBLIC),
            ("GET", {"Range": "bytes=0-10"}, PUBLIC),
            ("GET", {"Cache-Control": "no-store"}, PUBLIC),
        ):
            with self.subTest(method=method, request_headers=request_headers):
                c = self.client(allow_direct=True)
                self.complete(c, method=method, request_headers=request_headers, response_headers=response_headers)
                self.assertFalse(c._ws.commands)
                self.assertTrue(c._background_queue.empty())

    def test_cold_and_forbidden_requests_are_continued_immediately(self):
        for url in (URL, URL + "?private=value", URL.replace("entry.client", "sentinel")):
            c = self.client()
            self.event(c, "Fetch.requestPaused", requestId="fetch-1", networkId="net-1", resourceType="Script", request={"method": "GET", "url": url, "headers": {}})
            self.assertEqual(c._ws.commands[-1]["method"], "Fetch.continueRequest")
            self.assertFalse(c._paused)

    def test_forced_reload_and_range_bypass_warm_cache(self):
        for header in ({"Range": "bytes=0-10"}, {"Cache-Control": "no-cache"}, {"Cache-Control": "no-store"}):
            c = self.client()
            c._store.put(URL, PUBLIC, BODY)
            self.event(c, "Fetch.requestPaused", requestId="fetch-1", networkId="net-1", resourceType="Script", request={"method": "GET", "url": URL, "headers": header})
            self.assertEqual(c._ws.commands[-1]["method"], "Fetch.continueRequest")

    def test_credentialed_requests_bypass_warm_public_cache(self):
        for headers in ({"Cookie": "test=private"}, {"authorization": "Bearer test"}, {"Proxy-Authorization": "Basic test"}):
            with self.subTest(headers=headers):
                c = self.client()
                c._store.put(URL, PUBLIC, BODY)
                self.event(c, "Fetch.requestPaused", requestId="fetch-1", networkId="net-1", resourceType="Script", request={"method": "GET", "url": URL, "headers": headers})
                self.assertEqual(c._ws.commands[-1]["method"], "Fetch.continueRequest")
                self.assertFalse(c._paused)
                self.assertTrue(c._lookup_queue.empty())

    def test_late_lookup_cannot_leave_request_paused_or_double_fulfill(self):
        c = self.client()
        c._store.put(URL, PUBLIC, BODY)
        self.event(c, "Fetch.requestPaused", requestId="fetch-1", networkId="net-1", resourceType="Script", request={"method": "GET", "url": URL, "headers": {}})
        c._paused["fetch-1"]["deadline"] = 0
        c._expire_paused()
        c._results.put(("fetch-1", c._store.get(URL)))
        c._drain_results()
        self.assertEqual([x["method"] for x in c._ws.commands], ["Fetch.continueRequest"])
        self.assertFalse(c._paused)

    def test_unconfirmed_fulfill_is_unknown_then_confirmed_local_survives_stop(self):
        c = self.client()
        c.target_id = "target-a"
        c._paused["fetch-1"] = {"url": URL, "network_id": "net-1", "deadline": time.monotonic() + 1}
        c._results.put(("fetch-1", {"body": BODY, "headers": PUBLIC, "upstream_bytes": 123}))
        c._drain_results()
        self.assertEqual(c.request_source("net-1", "target-a"), "unknown")
        self.assertEqual(c.request_source("net-1", "target-b"), "network")
        command = c._ws.commands[-1]
        self.assertEqual(command["method"], "Fetch.fulfillRequest")
        c._event({"id": command["id"], "result": {}})
        self.assertEqual(c.request_source("net-1"), "local")
        self.assertEqual(c.snapshot()["local_served_bytes"], len(BODY))
        self.assertEqual(c.snapshot()["avoided_upstream_bytes"], 123)
        c.stop()
        self.assertEqual(c.request_source("net-1"), "local")
        c._reply(("fulfill", "fetch-1", "net-1", len(BODY), 123), {"error": {"message": "closed"}})
        self.assertEqual(c.request_source("net-1"), "network")


    def test_fulfill_timeout_or_stop_never_claims_local_delivery(self):
        for action in ("stop", "timeout"):
            with self.subTest(action=action):
                c = self.client()
                c._paused["fetch-1"] = {"url": URL, "network_id": "net-1", "deadline": time.monotonic() + 1}
                c._results.put(("fetch-1", {"body": BODY, "headers": PUBLIC, "upstream_bytes": 123}))
                c._drain_results()
                command = c._ws.commands[-1]
                if action == "stop":
                    c.stop()
                else:
                    tag, _ = c._pending[command["id"]]
                    c._pending[command["id"]] = (tag, 0)
                    c._expire_commands()
                self.assertEqual(c.request_source("net-1"), "unknown")
                self.assertEqual(c.snapshot()["hits"], 0)
                self.assertFalse(c.snapshot()["replay_accounting_complete"])
                c._event({"id": command["id"], "result": {}})
                self.assertEqual(c.request_source("net-1"), "unknown")

class PublicAssetTargetTests(_TempFiles):
    def test_explicit_target_selects_current_page_in_multi_page_profile(self):
        client = PublicAssetCache("127.0.0.1:9222", self.directory, target_id="current-page")
        pages = [
            {"id": "other-page", "type": "page", "url": "https://example.org/", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/other-page"},
            {"id": "current-page", "type": "page", "url": "https://chatgpt.com/", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/current-page"},
        ]
        with patch.object(cache_module.requests, "Session") as session, patch.object(cache_module.websocket, "create_connection") as connect:
            session.return_value.__enter__.return_value.get.return_value.json.return_value = pages
            client._connect()
        self.assertEqual(client.target_id, "current-page")
        self.assertEqual(connect.call_args.args[0], pages[1]["webSocketDebuggerUrl"])

    def test_missing_explicit_target_never_falls_back_to_another_page(self):
        client = PublicAssetCache("127.0.0.1:9222", self.directory, target_id="closed-page")
        pages = [{"id": "other-page", "type": "page", "url": "https://example.org/", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/other-page"}]
        with patch.object(cache_module.requests, "Session") as session, patch.object(cache_module.websocket, "create_connection") as connect:
            session.return_value.__enter__.return_value.get.return_value.json.return_value = pages
            with self.assertRaises(StopIteration):
                client._connect()
        connect.assert_not_called()


class _Raw:
    def __init__(self, body, fail_after=None):
        self.data = io.BytesIO(body)
        self.fail_after = fail_after
        self.calls = 0

    def read1(self, amount, decode_content=False):
        self.calls += 1
        if self.fail_after and self.calls >= self.fail_after:
            raise requests.exceptions.ReadTimeout()
        return self.data.read(min(amount, 8))


class _Response:
    def __init__(self, body, *, headers=None, status=200, url=URL, fail_after=None):
        self.status_code = status
        self.url = url
        self.headers = requests.structures.CaseInsensitiveDict(headers or PUBLIC)
        self.raw = _Raw(body, fail_after)
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class PublicAssetAnonymousDownloadTests(_TempFiles):
    def download(self, response, **kwargs):
        client = PublicAssetCache("127.0.0.1:9222", self.directory, mode="enabled", **kwargs)
        captured = {}

        def send(session, request, **options):
            captured.update(headers=dict(request.headers), url=request.url, options=options, trust_env=session.trust_env)
            return response

        with patch.object(requests.Session, "send", send):
            result = client._anonymous_download(URL)
        return client, result, captured

    def test_anonymous_request_has_explicit_proxy_and_no_environment_or_credentials(self):
        compressed = gzip.compress(BODY)
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://environment.invalid:9999"}):
            c, result, request = self.download(_Response(compressed, headers={**PUBLIC, "content-encoding": "gzip"}), proxy_url="http://127.0.0.1:8888")
        self.assertEqual(result["body"], BODY)
        self.assertEqual(c.snapshot()["anonymous_fill_bytes"], len(compressed))
        self.assertFalse(request["trust_env"])
        self.assertNotIn("Cookie", request["headers"])
        self.assertNotIn("Authorization", request["headers"])
        self.assertEqual(request["options"]["proxies"]["https"], "http://127.0.0.1:8888")
        self.assertFalse(request["options"]["allow_redirects"])
        self.assertTrue(request["options"]["stream"])

    def test_no_implicit_direct_network_and_no_redirect_follow(self):
        c, result, request = self.download(_Response(BODY))
        self.assertEqual(c.snapshot()["anonymous_requests"], 0)
        self.assertIsNone(result)
        self.assertFalse(request)
        c, result, request = self.download(_Response(b"redirect", status=302), allow_direct=True)
        self.assertIsNone(result)
        self.assertEqual(c.snapshot()["anonymous_requests"], 1)
        self.assertFalse(request["options"]["allow_redirects"])

    def test_gzip_bomb_and_truncated_stream_are_not_cached(self):
        for wire in (gzip.compress(b"x" * 1000), gzip.compress(BODY)[:-4]):
            c, result, _ = self.download(_Response(wire, headers={**PUBLIC, "content-encoding": "gzip"}), allow_direct=True, max_entry_bytes=100)
            self.assertIsNone(result)
            self.assertGreater(c.snapshot()["anonymous_fill_bytes"], 0)

    def test_failed_download_still_counts_received_compressed_bytes(self):
        compressed = gzip.compress(BODY)
        client = PublicAssetCache("127.0.0.1:9222", self.directory, mode="enabled", allow_direct=True)
        with patch.object(requests.Session, "send", return_value=_Response(compressed, headers={**PUBLIC, "content-encoding": "gzip"}, fail_after=2)):
            with self.assertRaises(requests.exceptions.ReadTimeout):
                client._anonymous_download(URL)
        self.assertEqual(client.snapshot()["anonymous_fill_bytes"], 8)


class PublicAssetShutdownAndSharingTests(_TempFiles):
    def client(self, fetcher):
        client = PublicAssetCache("127.0.0.1:9222", self.directory, mode="enabled", anonymous_fetcher=fetcher)
        client._store = self.store()
        worker = threading.Thread(target=client._work, args=("background", client._background_queue), daemon=True)
        client._workers.append(worker)
        worker.start()
        return client

    def test_overlapping_profiles_download_once_and_next_profile_reuses_disk(self):
        entered, release = threading.Event(), threading.Event()
        calls = []

        def fetch(url, maximum, stop):
            calls.append(url)
            entered.set()
            release.wait(2)
            return {"url": url, "status": 200, "headers": PUBLIC, "body": BODY, "encoded_bytes": 77}

        first = self.client(fetch)
        second = self.client(fetch)
        try:
            first._queue_background(("anonymous", URL, 321))
            self.assertTrue(entered.wait(1))
            second._queue_background(("anonymous", URL, 321))
            second._background_queue.join()
            self.assertEqual(second.snapshot()["coalesced_fills"], 1)
            release.set()
            first._background_queue.join()
            second._queue_background(("anonymous", URL, 321))
            second._background_queue.join()
            self.assertEqual(calls, [URL])
            self.assertEqual(first.snapshot()["anonymous_fill_bytes"], 77)
            self.assertEqual(second.snapshot()["anonymous_requests"], 0)
            self.assertEqual(second._store.get(URL)["body"], BODY)
        finally:
            release.set()
            first.stop()
            second.stop()

    def test_stop_waits_for_cooperative_download_and_never_stores_after_stop(self):
        entered = threading.Event()

        def fetch(url, maximum, stop):
            entered.set()
            stop.wait(2)
            return {"url": url, "status": 200, "headers": PUBLIC, "body": BODY, "encoded_bytes": 77}

        client = self.client(fetch)
        client._queue_background(("anonymous", URL, 321))
        self.assertTrue(entered.wait(1))
        final = client.stop()
        self.assertTrue(final["anonymous_accounting_complete"])
        self.assertEqual(final["anonymous_fill_bytes"], 77)
        self.assertEqual(final["stores"], 0)
        self.assertFalse(list(self.directory.glob("*.asset")))
        self.assertEqual(final, client.snapshot())

    def test_uncooperative_download_marks_unknown_and_freezes_final_counters(self):
        entered, release = threading.Event(), threading.Event()

        def fetch(url, maximum, stop):
            entered.set()
            release.wait(5)
            return {"url": url, "status": 200, "headers": PUBLIC, "body": BODY, "encoded_bytes": 77}

        client = self.client(fetch)
        try:
            client._queue_background(("anonymous", URL, 321))
            self.assertTrue(entered.wait(1))
            final = client.stop()
            self.assertFalse(final["anonymous_accounting_complete"])
            release.set()
            client._workers[0].join(1)
            self.assertEqual(final, client.snapshot())
            self.assertFalse(list(self.directory.glob("*.asset")))
        finally:
            release.set()
            client._workers[0].join(1)

    def test_stop_during_disk_recheck_cannot_start_late_anonymous_network(self):
        entered, release = threading.Event(), threading.Event()
        downloads = []
        client = self.client(lambda *args: downloads.append(args))
        def blocked_get(url):
            entered.set()
            release.wait(5)
            return None
        client._store.get = blocked_get
        try:
            client._queue_background(("anonymous", URL, 321))
            self.assertTrue(entered.wait(1))
            final = client.stop()
            self.assertTrue(final["anonymous_accounting_complete"])
            release.set()
            client._workers[0].join(1)
            self.assertFalse(downloads)
            self.assertEqual(final, client.snapshot())
        finally:
            release.set()
            client._workers[0].join(1)

    def test_stop_releases_paused_requests_and_only_disables_own_connection(self):
        class Wire(_Wire):
            def recv(self):
                time.sleep(.005)
                raise websocket.WebSocketTimeoutException()

        client = PublicAssetCache("127.0.0.1:9222", self.directory, mode="enabled", ready_timeout=.1)
        wire = Wire()
        client._paused["paused"] = {"deadline": time.monotonic() + 10}
        with patch.object(client, "_connect", side_effect=lambda: setattr(client, "_ws", wire)):
            started = time.monotonic()
            self.assertFalse(client.start())
            self.assertLess(time.monotonic() - started, 1)
        commands = [x["method"] for x in wire.commands]
        self.assertIn("Fetch.continueRequest", commands)
        self.assertIn("Fetch.disable", commands)
        self.assertNotIn("Browser.close", commands)
        self.assertFalse(client._paused)

    def test_replay_preserves_security_headers_without_extending_freshness(self):
        headers = {**PUBLIC, "content-encoding": "gzip", "etag": '"compressed"',
                   "content-security-policy": "script-src 'self'", "cross-origin-resource-policy": "cross-origin"}
        with patch.object(cache_module.time, "time", return_value=1000):
            replay = {h["name"]: h["value"] for h in _replay_headers(headers, len(BODY), 1030)}
        self.assertEqual(replay["cache-control"], "public, max-age=30")
        self.assertEqual(replay["content-length"], str(len(BODY)))
        self.assertEqual(replay["access-control-allow-origin"], "*")
        self.assertEqual(replay["content-security-policy"], "script-src 'self'")
        self.assertNotIn("etag", replay)
        self.assertNotIn("content-encoding", replay)


if __name__ == "__main__":
    unittest.main()
