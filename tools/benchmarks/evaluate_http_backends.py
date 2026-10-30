#!/usr/bin/env python3
"""仅在 loopback 合成服务上评估 HTTP 后端，不导入业务配置或接受远程 URL。

使用独立环境安装 tools/benchmarks/http_backend_eval_requirements.txt 后运行；JSON 结果仅含
契约断言、版本、数值和异常类型。这个工具不安装或替换生产 HTTP 后端。
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import os
import socket
import threading
import time
from contextlib import contextmanager
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class LocalHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def handle(self):
        # 合成断连/超时以及客户端资源关闭可能主动复位本地连接。
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def dispatch(self):
        self.server.hits += 1
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/disconnect":
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        if path == "/slow":
            time.sleep(0.5)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        content_type = self.headers.get("Content-Type", "")
        result = {"server": self.server.role, "cookie": self.headers.get("Cookie", ""),
                  "content_type": content_type, "raw": body.decode("utf-8"),
                  "absolute_proxy_target": parsed.scheme == "http"}
        status, headers = 200, {"Content-Type": "application/json; charset=utf-8"}
        if "application/json" in content_type:
            result["json"] = json.loads(body)
        if "application/x-www-form-urlencoded" in content_type:
            result["form"] = parse_qs(body.decode())
        if path == "/cookie":
            headers["Set-Cookie"] = "local_session=one; Path=/; HttpOnly"
        elif path == "/redirect":
            status, headers["Location"] = 302, "/echo"
            headers["Set-Cookie"] = "local_redirect=two; Path=/"
        elif path == "/status":
            status = 500
        payload = json.dumps(result).encode()
        if path == "/gzip":
            payload = gzip.compress(payload)
            headers["Content-Encoding"] = "gzip"
        elif path == "/latin":
            payload = b"caf\xe9"
            headers["Content-Type"] = "text/plain; charset=iso-8859-1"
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass


@contextmanager
def local_server(role):
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
    server.role, server.hits = role, 0
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextmanager
def without_proxy_environment():
    names = [key for key in os.environ if key.lower() in {
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    }]
    saved = {key: os.environ.pop(key) for key in names}
    try:
        yield
    finally:
        os.environ.update(saved)


class Backend:
    """只作契约参数映射；不隐藏状态、异常和关闭语义差异。"""

    def __init__(self, name, proxy=None):
        self.name = name
        if name == "curl_cffi":
            from curl_cffi.requests import Session
            self.client = Session(proxy=proxy, trust_env=False, timeout=2)
        else:
            import wreq
            self.wreq = wreq
            options = {"cookie_store": True, "timeout": timedelta(seconds=2)}
            options.update({"proxies": [wreq.Proxy.all(proxy)]} if proxy else {"no_proxy": True})
            self.client = wreq.blocking.Client(**options)

    def request(self, url, *, method="GET", follow=True, timeout=2, form=None, raw=None, json_body=None):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
            raise ValueError("评估工具仅允许固定 loopback HTTP 服务")
        if self.name == "curl_cffi":
            options = {"allow_redirects": follow, "timeout": timeout}
            if form is not None or raw is not None:
                options["data"] = form if form is not None else raw
        else:
            options = {"redirect": self.wreq.Policy.limited(5) if follow else self.wreq.Policy.none(),
                       "timeout": timedelta(seconds=timeout)}
            if form is not None:
                options["form"] = form
            if raw is not None:
                options["body"] = raw
        if json_body is not None:
            options["json"] = json_body
        return getattr(self.client, method.lower())(url, **options)

    def status(self, response):
        return response.status_code if self.name == "curl_cffi" else response.status.as_int()

    def text(self, response):
        return response.text if self.name == "curl_cffi" else response.text()

    def release(self, response):
        response.close()


def evaluate(name, origin, base, proxy_base):
    backend = Backend(name)
    cases = {}

    def check(label, operation):
        started = time.monotonic()
        try:
            detail = operation()
            cases[label] = {"passed": bool(detail.pop("passed", True)), **detail}
        except (Exception, asyncio.CancelledError) as exc:
            cases[label] = {"passed": False, "exception_type": type(exc).__name__}
        cases[label]["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)

    def exchange(path, **kwargs):
        response = backend.request(base + path, **kwargs)
        try:
            return backend.status(response), response.json()
        finally:
            backend.release(response)

    check("cookie_store", lambda: {
        "passed": exchange("/cookie")[0] == 200 and "local_session=one" in exchange("/echo")[1]["cookie"],
    })
    check("redirect_disabled", lambda: {"passed": exchange("/redirect", follow=False)[0] == 302})
    check("redirect_and_cookie_merge", lambda: {
        "passed": all(value in exchange("/redirect")[1]["cookie"] for value in ("local_session=one", "local_redirect=two")),
    })
    check("form_encoding", lambda: {"passed": exchange("/echo", method="POST", form={"text": "中文 + &"})[1]["form"] == {"text": ["中文 + &"]}})
    check("json_encoding", lambda: {"passed": exchange("/echo", method="POST", json_body={"text": "中文"})[1]["json"] == {"text": "中文"}})
    check("raw_encoding", lambda: {"passed": exchange("/echo", method="POST", raw=b"raw-body")[1]["raw"] == "raw-body"})
    check("gzip_decoding", lambda: {"passed": exchange("/gzip")[1]["server"] == "origin"})

    def latin():
        response = backend.request(base + "/latin")
        try:
            return {"passed": backend.text(response) == "café"}
        finally:
            backend.release(response)
    check("charset_header", latin)

    def expected_error(path, **kwargs):
        started = time.monotonic()
        try:
            response = backend.request(base + path, **kwargs)
            try:
                if path == "/status":
                    response.raise_for_status()
                else:
                    backend.text(response)  # wreq 的读取正文也在请求预算内。
            finally:
                backend.release(response)
        except (Exception, asyncio.CancelledError) as exc:
            elapsed = time.monotonic() - started
            return {"passed": path != "/slow" or elapsed < 0.4, "exception_type": type(exc).__name__}
        return {"passed": False, "exception_type": None}
    check("http_status_error", lambda: expected_error("/status"))
    check("connection_error", lambda: expected_error("/disconnect"))
    check("timeout", lambda: expected_error("/slow", timeout=0.12))

    def proxy_case():
        proxied = Backend(name, proxy=proxy_base)
        before = origin.hits
        response = None
        try:
            response = proxied.request(base + "/echo")
            data = response.json()
            return {"passed": data["server"] == "proxy" and data["absolute_proxy_target"] and origin.hits == before,
                    "origin_hit_delta": origin.hits - before}
        finally:
            if response is not None:
                proxied.release(response)
            proxied.client.close()
    check("explicit_http_proxy_without_direct_fallback", proxy_case)
    backend.client.close()
    check("closed_client_rejects_new_requests", lambda: expected_error("/echo"))
    return {"version": version(name.replace("_", "-")), "cases": cases,
            "passed": all(case["passed"] for case in cases.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="可选的 JSON 输出文件；不接受自定义请求地址")
    args = parser.parse_args()
    with without_proxy_environment(), local_server("origin") as (origin, base), local_server("proxy") as (_, proxy_base):
        results = {name: evaluate(name, origin, base, proxy_base) for name in ("curl_cffi", "wreq")}
    report = {"scope": "loopback_http_synthetic_only", "backends": results,
              "not_evaluated": ["TLS 与 HTTP/2 指纹", "HTTPS CONNECT", "SOCKS 与远程 DNS",
                                "进行中的请求取消", "远端注册与风控兼容性", "代理商账单字节"],
              "production_backend_changed": False}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if all(result["passed"] for result in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
