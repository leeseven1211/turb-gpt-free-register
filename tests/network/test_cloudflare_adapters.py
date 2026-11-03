"""Optional recovery never changes ordinary requests or business submissions."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from requests.cookies import RequestsCookieJar

from core.auth.challenge import AuthCancelledError
from core.auth.state_machine import StageBudget


def response(status=403, headers=None):
    return SimpleNamespace(status_code=status, headers=headers or {"cf-mitigated": "challenge"},
                           url="https://chatgpt.com/auth/login", content=b"<html>challenge</html>")


def owner():
    raw = SimpleNamespace(headers={}, auth=None, cookies=RequestsCookieJar(), request=Mock())
    return SimpleNamespace(session=raw, blocked_until=100.0, blocked_reason="original challenge",
                           browser_profile={}, _record_traffic=Mock(),
                           _observe_response_for_circuit_breaker=Mock())


def test_browser_bridge_uses_existing_transport_and_records_traffic():
    from core.network.cloudflare_adapters import BrowserChallengeTransport
    session = owner()
    expected = response(200)
    session.session.request.return_value = expected
    transport = BrowserChallengeTransport(session)
    assert transport.cookies is session.session.cookies
    assert transport.request("GET", "https://chatgpt.com/cdn-cgi/challenge-platform/x",
                             timeout=1, allow_redirects=False) is expected
    session.session.request.assert_called_once()
    session._record_traffic.assert_called_once()
    assert session.blocked_until == 100


@pytest.mark.parametrize("status", [403, 429])
def test_bridge_preserves_original_challenge_circuit_but_observes_new_rate_limit(status):
    from core.network.cloudflare_adapters import BrowserChallengeTransport
    session = owner()
    session.session.request.return_value = response(status)
    BrowserChallengeTransport(session).request("GET", "https://chatgpt.com/cdn-cgi/challenge-platform/x",
                                               timeout=1, allow_redirects=False)
    assert session._observe_response_for_circuit_breaker.call_count == (1 if status == 429 else 0)


@pytest.mark.parametrize("status,headers", [(200, {}), (403, {"server": "cloudflare"}),
                                         (429, {"cf-mitigated": "challenge"})])
def test_ordinary_responses_do_not_start_recovery(status, headers):
    from core.network.cloudflare_adapters import recover_browser_preflight
    session = owner()
    original = response(status, headers)
    with patch("core.network.cloudflare.solve_challenge") as solve:
        assert recover_browser_preflight(session, original, headers={}, budget=StageBudget.start(1)) is original
    solve.assert_not_called()
    session.session.request.assert_not_called()


def test_failed_optional_recovery_keeps_original_response_and_circuit():
    from core.network.cloudflare_adapters import recover_browser_preflight
    session = owner()
    original = response()
    with patch("core.network.cloudflare.solve_challenge", side_effect=RuntimeError("private-runtime-error")) as solve:
        assert recover_browser_preflight(session, original, headers={}, budget=StageBudget.start(1)) is original
        assert recover_browser_preflight(session, original, headers={}, budget=StageBudget.start(1)) is original
    assert solve.call_count == 1
    assert session.blocked_until == 100
    assert session.blocked_reason == "original challenge"


def test_verified_recovery_clears_only_its_original_challenge_circuit():
    from core.network.cloudflare_adapters import recover_browser_preflight
    session = owner()
    original, verified = response(), response(200)
    with patch("core.network.cloudflare.solve_challenge", return_value=SimpleNamespace(
        status="verified", response=verified, request_count=2, reason="verified")):
        assert recover_browser_preflight(session, original, headers={}, budget=StageBudget.start(1)) is verified
    assert session.blocked_until == 0


def test_verified_recovery_does_not_clear_new_rate_limit_circuit():
    from core.network.cloudflare_adapters import recover_browser_preflight
    session = owner()
    original = response()

    def solve(*args, **kwargs):
        session.blocked_until, session.blocked_reason = 200, "HTTP 429"
        return SimpleNamespace(status="verified", response=response(200), request_count=2, reason="verified")

    with patch("core.network.cloudflare.solve_challenge", side_effect=solve):
        assert recover_browser_preflight(session, original, headers={}, budget=StageBudget.start(1)) is original
    assert session.blocked_until == 200


def test_cancellation_is_not_swallowed_by_optional_recovery():
    from core.network.cloudflare_adapters import recover_browser_preflight
    session = owner()
    with patch("core.network.cloudflare.solve_challenge", side_effect=AuthCancelledError("stop")):
        with pytest.raises(AuthCancelledError):
            recover_browser_preflight(session, response(), headers={}, budget=StageBudget.start(1))


@pytest.mark.parametrize("header", ["Authorization", "Cookie", "Host", "X-Api-Key"])
def test_bridge_rejects_persistent_auth_headers(header):
    from core.network.cloudflare_adapters import BrowserChallengeTransport
    session = owner()
    session.session.headers[header] = "private-value"
    with pytest.raises(ValueError):
        BrowserChallengeTransport(session)
    session.session.request.assert_not_called()


def test_wreq_bridge_has_no_transport_retry_and_reads_real_cookie_jar():
    from core.network.cloudflare_adapters import WreqChallengeTransport
    real_cookies = [SimpleNamespace(name="cf_clearance", value="private", domain="chatgpt.com", path="/")]
    client = SimpleNamespace(get=Mock(side_effect=TimeoutError("timed out")))
    raw = SimpleNamespace(headers={}, _headers={}, _client=client, _proxy_obj=object(),
                          _prepare=Mock(return_value=("https://chatgpt.com/auth/login", {}, None)),
                          _jar=lambda: SimpleNamespace(get_all=lambda: real_cookies))
    bridge = WreqChallengeTransport(raw, {})
    assert bridge.cookies.jar == real_cookies
    with pytest.raises(TimeoutError):
        bridge.request("GET", "https://chatgpt.com/auth/login", timeout=1, allow_redirects=False)
    assert client.get.call_count == 1
    assert client.get.call_args.kwargs["proxy"] is raw._proxy_obj


def test_bridge_debug_capture_receives_only_safe_summary_even_in_raw_capture_mode():
    from core.network.cloudflare_adapters import BrowserChallengeTransport
    session = owner()
    private = SimpleNamespace(status_code=200, headers={"Set-Cookie": "cf_clearance=private-cookie",
                              "content-type": "text/javascript"},
                              content=b"private-script", text="private-script")
    session.session.request.return_value = private
    with patch("core.registration.debug.record_protocol_exchange") as capture:
        BrowserChallengeTransport(session).request(
            "POST", "https://chatgpt.com/cdn-cgi/challenge-platform/flow/private-path?secret=private-query",
            headers={"content-type": "text/plain"}, data="private-proof", timeout=1, allow_redirects=False,
        )
    event = capture.call_args.kwargs
    assert "private" not in str(event)
    assert event["request_body"] is None
    assert event["response"].content == b""
    assert event["response"].text == ""
    assert "set-cookie" not in {name.lower() for name in event["response"].headers}
    assert session._record_traffic.call_args.kwargs["response"] is private


def test_optional_stream_cleanup_cannot_mask_task_cancellation():
    from core.network.cloudflare_adapters import _StreamResponse

    def chunks(size):
        raise AuthCancelledError("stop")
        yield b""

    raw = SimpleNamespace(close=Mock(side_effect=RuntimeError("cleanup")))
    wrapped = _StreamResponse(raw, chunks, Mock())
    with pytest.raises(AuthCancelledError):
        list(wrapped.iter_content())


@pytest.mark.parametrize("method,url,stream", [
    ("GET", "https://chatgpt.com/auth/login", False),
    ("GET", "https://chatgpt.com/api/auth/csrf", False),
    ("POST", "https://chatgpt.com/auth/login", False),
    ("GET", "https://auth.openai.com/api/accounts/email-otp/send", False),
    ("GET", "https://chatgpt.com/auth/login?state=private", False),
    ("GET", "https://chatgpt.com/auth/login", True),
])
def test_proto2_passes_challenges_through_without_automatic_recovery(method, url, stream):
    from core.registration.protocol_oss_2.runtime import _ObservedSession
    original, verified = response(), response(200)
    raw = SimpleNamespace(headers={}, auth=None, request=Mock(return_value=original))
    # A stale caller context must not re-enable the removed registration hook.
    session = _ObservedSession(raw, {"capture": None, "cf_preflight_enabled": True})
    with patch("core.registration.service.check_stop_requested"), \
            patch("core.registration.debug.record_protocol_exchange"), \
            patch("core.network.cloudflare.solve_challenge", return_value=SimpleNamespace(
                status="verified", response=verified)) as solve:
        actual = session.request(method, url, stream=stream)
    solve.assert_not_called()
    assert actual is original
    assert raw.request.call_count == 1
    assert raw.request.call_args.args == (method, url)
    assert raw.request.call_args.kwargs == {"stream": stream}


def test_proto2_records_the_original_response_and_wire_start_time():
    from core.registration.protocol_oss_2.runtime import _ObservedSession
    clock = [0.0]
    original = response()

    def initial(*args, **kwargs):
        clock[0] += 1
        return original

    capture = Mock()
    session = _ObservedSession(SimpleNamespace(request=initial), {"capture": capture})
    with patch("core.registration.service.check_stop_requested"), \
            patch("core.registration.debug.record_protocol_exchange"), \
            patch("core.registration.protocol_oss_2.runtime.time.perf_counter", side_effect=lambda: clock[0]):
        assert session.get("https://chatgpt.com/auth/login", timeout=12) is original
    assert capture.record.call_args.kwargs["response"] is original
    assert clock[0] - capture.record.call_args.kwargs["started_at"] == 1


def test_wreq_challenge_stream_remains_readable_and_uses_the_same_proxy():
    pytest.importorskip("wreq")
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from core.network.cloudflare_adapters import WreqChallengeTransport
    from core.registration.protocol_oss_2.upstream.http_client_wreq import create_http_session

    seen = []

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append(self.path)
            body = b"fixture-stream"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Set-Cookie", "cf_clearance=fixture; Path=/")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    raw = create_http_session(proxy=f"http://127.0.0.1:{server.server_port}", impersonate="chrome152")
    try:
        bridge = WreqChallengeTransport(raw, {"capture": None})
        with patch("core.registration.debug.record_protocol_exchange"):
            result = bridge.request("GET", "http://challenge.fixture.invalid/document", stream=True,
                                    timeout=1, allow_redirects=False)
            assert b"".join(result.iter_content()) == b"fixture-stream"
        assert result.content == b"fixture-stream"
        assert result.text == "fixture-stream"
        assert seen == ["http://challenge.fixture.invalid/document"]
        assert any(cookie.name == "cf_clearance" for cookie in bridge.cookies.jar)
    finally:
        raw.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
