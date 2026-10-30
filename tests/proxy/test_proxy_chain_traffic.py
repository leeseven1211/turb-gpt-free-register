# -*- coding: utf-8 -*-
import socket
import threading
import unittest
from unittest.mock import patch
from core.proxy.chain import ProxyChainRelay, browser_blocked_proxy_hosts, _read_exact


class ProxyChainTrafficTests(unittest.TestCase):
    def test_counting_relay_does_not_require_upstream_or_pysocks(self):
        with patch("core.proxy.chain.socks", None), patch("core.proxy.chain.socket.create_connection") as connect:
            relay = ProxyChainRelay("http://127.0.0.1:8888")
            relay._connect_target_through_upstream("127.0.0.1", 8888)
        connect.assert_called_once_with(("127.0.0.1", 8888), timeout=15.0)

    def test_browser_host_rules_require_data_saver_and_support_empty_override(self):
        with patch("config.browser.BROWSER_DATA_SAVER_MODE", False):
            self.assertEqual(browser_blocked_proxy_hosts(), ())
        with patch("config.browser.BROWSER_DATA_SAVER_MODE", True), patch(
            "config.browser.BROWSER_DATA_SAVER_BLOCKED_PROXY_HOSTS", ["dl.google.com", "gvt1.com"]
        ):
            self.assertEqual(browser_blocked_proxy_hosts(), ("dl.google.com", "gvt1.com"))
        with patch("config.browser.BROWSER_DATA_SAVER_MODE", True), patch(
            "config.browser.BROWSER_DATA_SAVER_BLOCKED_PROXY_HOSTS", []
        ):
            self.assertEqual(browser_blocked_proxy_hosts(), ())

    def test_blocks_google_downloads_and_retries_before_any_upstream_connection(self):
        relay = ProxyChainRelay("socks5://127.0.0.1:8888", blocked_hosts=("dl.google.com", "gvt1.com"))
        for target in ("dl.google.com", "dl.google.com", "GVT1.COM.", "rr8---sn-example.gvt1.com", "redirector.gvt1.com"):
            browser, client = socket.socketpair()
            browser.settimeout(2)
            try:
                browser.sendall(f"CONNECT {target}:443 HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
                with patch.object(relay, "_connect_target_through_upstream") as connect:
                    relay._handle_client(client)
                    connect.assert_not_called()
                self.assertIn(b"403 Forbidden", browser.recv(4096))
            finally:
                browser.close()
        snapshot = relay.traffic_snapshot()
        self.assertEqual(snapshot["total_bytes"], 0)
        self.assertEqual(snapshot["blocked_connection_count"], 5)
        self.assertEqual(sum(item["failed_connection_count"] for item in snapshot["destinations"]), 0)
        dl = next(item for item in snapshot["destinations"] if item["host"] == "dl.google.com")
        self.assertEqual(dl["blocked_connection_count"], 2)
        self.assertEqual(relay.last_error, "")


    def test_host_block_also_applies_to_plain_http(self):
        relay = ProxyChainRelay("http://127.0.0.1:8888", blocked_hosts=("gvt1.com",))
        browser, client = socket.socketpair()
        try:
            browser.sendall(b"GET http://redirector.gvt1.com/download HTTP/1.1\r\nHost: redirector.gvt1.com\r\n\r\n")
            with patch.object(relay, "_connect_target_through_upstream") as connect:
                relay._handle_client(client)
                connect.assert_not_called()
            self.assertIn(b"403 Forbidden", browser.recv(4096))
            self.assertEqual(relay.traffic_snapshot()["destinations"][0]["port"], 80)
        finally:
            browser.close()

    def test_unrelated_hosts_are_not_blocked_by_substring(self):
        relay = ProxyChainRelay("http://127.0.0.1:8888", blocked_hosts=("dl.google.com", "gvt1.com"))
        for target in ("chatgpt.com", "auth.openai.com", "auth-cdn.oaistatic.com", "sentinel.openai.com", "notgvt1.com", "gvt1.com.example.org", "notdl.google.com"):
            browser, client = socket.socketpair()
            try:
                browser.sendall(f"CONNECT {target}:443 HTTP/1.1\r\n\r\n".encode())
                with patch.object(relay, "_connect_target_through_upstream", side_effect=ConnectionError("test")) as connect:
                    with self.assertLogs('core.proxy_chain', level="WARNING"):
                        relay._handle_client(client)
                    connect.assert_called_once()
            finally:
                browser.close()
        self.assertEqual(relay.traffic_snapshot()["blocked_connection_count"], 0)

    def test_plain_http_keeps_body_and_counts_wire_bytes(self):
        relay = ProxyChainRelay("socks5://127.0.0.1:8888")
        browser, client = socket.socketpair()
        remote, server = socket.socketpair()
        server.settimeout(2)
        browser.settimeout(2)
        request = b"POST http://example.test/test?q=1 HTTP/1.1\r\nHost: example.test\r\nContent-Length: 4\r\nProxy-Authorization: secret\r\n\r\nbody"
        expected = b"POST /test?q=1 HTTP/1.1\r\nHost: example.test\r\nContent-Length: 4\r\nConnection: close\r\n\r\nbody"
        response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
        with patch.object(relay, "_connect_target_through_upstream", return_value=remote), patch.object(relay, "_target_socks_connect") as tunnel:
            thread = threading.Thread(target=relay._handle_client, args=(client,))
            thread.start()
            try:
                browser.sendall(request)
                self.assertEqual(server.recv(4096), expected)
                server.sendall(response)
                self.assertEqual(browser.recv(4096), response)
                tunnel.assert_called_once_with(remote, "example.test", 80)
            finally:
                relay._stop.set()
                browser.close()
                thread.join(timeout=3)
                server.close()
        self.assertEqual(relay.traffic_snapshot()["total_bytes"], len(expected) + len(response))
        destination = relay.traffic_snapshot()["destinations"][0]
        self.assertEqual(destination["host"], "example.test")
        self.assertEqual(destination["port"], 80)
        self.assertEqual(destination["connection_count"], 1)
        self.assertEqual(destination["upload_bytes"], len(expected))
        self.assertEqual(destination["download_bytes"], len(response))

    def test_relay_counts_both_directions(self):
        relay = ProxyChainRelay("http://127.0.0.1:8888")

        browser, relay_client = socket.socketpair()
        relay_remote, upstream = socket.socketpair()
        thread = threading.Thread(target=relay._relay, args=(relay_client, relay_remote))
        thread.start()
        try:
            browser.sendall(b"upload")
            self.assertEqual(upstream.recv(6), b"upload")
            upstream.sendall(b"download")
            self.assertEqual(browser.recv(8), b"download")
        finally:
            relay._stop.set()
            browser.close()
            upstream.close()
            thread.join(timeout=2)
            relay_client.close()
            relay_remote.close()

        snapshot = relay.traffic_snapshot()
        self.assertEqual({key: snapshot[key] for key in ("available", "upload_bytes", "download_bytes", "total_bytes")}, {
            "available": True,
            "upload_bytes": 6,
            "download_bytes": 8,
            "total_bytes": 14,
        })
        self.assertEqual(snapshot["destinations"][0]["host"], "<unknown>")
        self.assertEqual(snapshot["destinations"][0]["total_bytes"], 14)

    def test_connect_attributes_tls_and_early_data_before_connection_closes(self):
        relay = ProxyChainRelay("socks5://127.0.0.1:8888")
        browser, client = socket.socketpair()
        remote, server = socket.socketpair()
        browser.settimeout(2)
        server.settimeout(2)
        early = b"early-tls-data"
        browser.sendall(b"CONNECT ChatGPT.COM:443 HTTP/1.1\r\nHost: chatgpt.com\r\n\r\n" + early)
        with patch.object(relay, "_connect_target_through_upstream", return_value=remote), patch.object(relay, "_target_socks_connect"):
            thread = threading.Thread(target=relay._handle_client, args=(client,))
            thread.start()
            try:
                self.assertIn(b"200 Connection Established", browser.recv(4096))
                self.assertEqual(_read_exact(server, len(early)), early)
                server.sendall(b"tls-response")
                self.assertEqual(_read_exact(browser, 12), b"tls-response")
                # 用锁确保转发后的计数写入已经完成，不要求关闭长连接才拿到明细。
                import time
                deadline = time.monotonic() + 2
                while relay.traffic_snapshot()["download_bytes"] != 12 and time.monotonic() < deadline:
                    time.sleep(0.001)
                snapshot = relay.traffic_snapshot()
                item = snapshot["destinations"][0]
                self.assertEqual((item["host"], item["port"]), ("chatgpt.com", 443))
                self.assertEqual(item["upload_bytes"], len(early))
                self.assertEqual(item["download_bytes"], 12)
                self.assertEqual(item["total_bytes"], snapshot["total_bytes"])
            finally:
                relay._stop.set()
                browser.close()
                thread.join(timeout=3)
                server.close()

    def test_destination_totals_are_atomic_sorted_and_snapshot_is_independent(self):
        relay = ProxyChainRelay("http://127.0.0.1:8888")
        def transfer():
            for _ in range(300):
                relay._record_transfer(("chatgpt.com", 443), upload=2, download=3)
                relay._record_transfer(("auth.openai.com", 443), upload=1, download=2)
        threads = [threading.Thread(target=transfer) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        result = relay.traffic_snapshot()
        self.assertEqual(result["destinations"][0]["host"], "chatgpt.com")
        for field in ("upload_bytes", "download_bytes", "total_bytes"):
            self.assertEqual(result[field], sum(item[field] for item in result["destinations"]))
        result["destinations"][0]["upload_bytes"] = -1
        self.assertEqual(relay.traffic_snapshot()["destinations"][0]["upload_bytes"], 2400)

    def test_failed_connection_records_target_without_fabricating_bytes(self):
        relay = ProxyChainRelay("socks5://127.0.0.1:8888")
        browser, client = socket.socketpair()
        browser.sendall(b"CONNECT AUTH.OPENAI.COM.:443 HTTP/1.1\r\nHost: auth.openai.com\r\n\r\n")
        try:
            with patch.object(relay, "_connect_target_through_upstream", side_effect=ConnectionError("test")):
                with self.assertLogs('core.proxy_chain', level="WARNING") as captured:
                    relay._handle_client(client)
            self.assertIn("destination=auth.openai.com:443", captured.output[0])
            result = relay.traffic_snapshot()
            self.assertEqual(result["total_bytes"], 0)
            self.assertEqual(result["destinations"][0]["failed_connection_count"], 1)
            self.assertEqual(result["destinations"][0]["connection_count"], 1)
        finally:
            browser.close()

    def test_destination_validation_rejects_credentials_and_log_injection(self):
        self.assertEqual(ProxyChainRelay._destination_key("Example.COM.", 443), ("example.com", 443))
        for host in ("user:secret@example.com", "example.com\nforged", "example.com/path", ""):
            with self.assertRaises(ValueError):
                ProxyChainRelay._destination_key(host, 443)
