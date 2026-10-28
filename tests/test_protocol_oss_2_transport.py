"""验证实际 wreq 兼容性，以及停止和流式导航边界。"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

import pytest

from core.registration.protocol_oss_2.runtime import _ObservedSession


@pytest.mark.parametrize("stream_navigation", [False, True])
def test_observed_wreq_posts_json_and_preserves_cookies_through_the_allocated_proxy(stream_navigation):
    pytest.importorskip("wreq")
    from core.registration.protocol_oss_2.upstream.http_client_wreq import create_http_session

    requests = []

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Set-Cookie", "protocol2=fixture; Path=/")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            requests.append({"url": self.path, "cookie": self.headers.get("Cookie"), "body": json.loads(body)})
            self.send_response(200)
            self.send_header("Content-Length", "11")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    transport = create_http_session(proxy=f"http://127.0.0.1:{server.server_port}", impersonate="chrome152")
    session = _ObservedSession(transport, {"capture": None})
    try:
        with patch("core.registration_service.check_stop_requested"), patch("core.registration_debug.record_protocol_exchange"):
            navigation = session.get("http://protocol2.fixture.invalid/init", timeout=3, stream=stream_navigation)
            assert navigation._protocol2_streaming is stream_navigation
            response = session.post("http://protocol2.fixture.invalid/submit", params={"q": "a b"}, json={"fixture": "body"}, timeout=3)
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert requests == [{
            "url": "http://protocol2.fixture.invalid/submit?q=a+b",
            "cookie": "protocol2=fixture", "body": {"fixture": "body"},
        }]
    finally:
        transport.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_streaming_navigation_diagnostics_do_not_read_the_body():
    class StreamingResponse:
        status_code = 200

        @property
        def content(self):
            raise AssertionError("不应下载流式导航正文")

        @property
        def text(self):
            raise AssertionError("不应下载流式导航正文")

    response = StreamingResponse()
    transport = Mock()
    transport.request.return_value = response
    seen = []

    def record(**kwargs):
        seen.append(kwargs["response"].content)

    session = _ObservedSession(transport, {"capture": Mock(record=record)})
    with patch("core.registration_service.check_stop_requested"), patch("core.registration_debug.record_protocol_exchange", side_effect=record):
        assert session.get("https://chatgpt.com/", stream=True) is response
    assert seen == [b"", b""]


def test_stopping_prevents_another_network_write():
    from core.registration_service import StopRequested

    transport = Mock()
    session = _ObservedSession(transport, {"capture": None})
    with patch("core.registration_service.check_stop_requested", side_effect=StopRequested("测试停止")):
        with pytest.raises(StopRequested):
            session.post("https://auth.openai.com/api/accounts/user/register", json={})
    transport.request.assert_not_called()


@pytest.mark.parametrize("method,url,stream,expected", [
    ("POST", "https://auth.openai.com/api/accounts/create_account", False, True),
    ("GET", "https://auth.openai.com/api/accounts/create_account", False, False),
    ("POST", "https://auth.openai.com/api/accounts/create_account", True, False),
    ("POST", "https://auth.openai.com.evil.test/api/accounts/create_account", False, False),
    ("POST", "https://private@auth.openai.com/api/accounts/create_account", False, False),
    ("POST", "https://auth.openai.com/api/accounts/password/verify", False, False),
])
def test_profile_error_diagnostic_reads_only_trusted_nonstreaming_submit(method, url, stream, expected):
    class Response:
        status_code = 409

        @property
        def text(self):
            assert expected, "非目标资料响应不得读取正文"
            return '{"error":{"code":"invalid_state","type":"private-type","message":"private-body"}}'

    transport = Mock()
    transport.request.return_value = Response()
    context = {"capture": None}
    session = _ObservedSession(transport, context)
    with patch("core.registration_service.check_stop_requested"), patch("core.registration_debug.record_protocol_exchange"):
        session.request(method, url, stream=stream)
    if expected:
        assert context["profile_diagnostics"] == {
            "operation": "profile_submit", "http_status": 409,
            "auth_error": {"code": "invalid_state", "type": "unknown", "category": "auth_state"},
        }
        assert "private" not in json.dumps(context)
    else:
        assert "profile_diagnostics" not in context


def test_successful_profile_does_not_read_response_body_for_error_diagnostics():
    class Response:
        status_code = 200

        @property
        def text(self):
            raise AssertionError("成功资料响应不应读取错误正文")

    transport = Mock()
    transport.request.return_value = Response()
    context = {"capture": None}
    with patch("core.registration_service.check_stop_requested"), patch("core.registration_debug.record_protocol_exchange"):
        _ObservedSession(transport, context).post("https://auth.openai.com/api/accounts/create_account")
    assert "profile_diagnostics" not in context


def test_upstream_trace_also_avoids_reading_streamed_navigation():
    from core.registration.protocol_oss_2.upstream.auth_flow import AuthFlow

    class Stream:
        _protocol2_streaming = True

        @property
        def text(self):
            raise AssertionError("上游 trace 不应读取导航正文")

    AuthFlow.__new__(AuthFlow)._trace_http("navigation", Stream())
