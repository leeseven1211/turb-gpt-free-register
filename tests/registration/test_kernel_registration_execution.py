"""Registration execution ownership and compatibility at the kernel boundary."""
import importlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


def kernel_module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name.startswith("core.kernels"):
            pytest.fail(f"registration execution has no kernel owner: {name}")
        raise


def test_kernel_otp_preparation_records_no_dispatch_before_rejecting_form():
    otp = kernel_module("core.kernels.browser.roxy.registration.otp")
    recorded = []
    driver = SimpleNamespace(execute_script=lambda *_: False)
    callbacks = otp.OtpFormCallbacks(
        record_submission=lambda _driver, phase, **changes: recorded.append((phase, changes)),
        install_validate_hook=lambda *_args, **_kwargs: None,
        dispatch_trusted_click=lambda *_: pytest.fail("unready form cannot click"),
        logger=Mock(),
    )
    with pytest.raises(RuntimeError, match="otp_form_not_ready"):
        otp.prepare_email_otp_current_form(driver, [], callbacks=callbacks)
    assert recorded == [("not_dispatched", {"result": "cancelled"})]


def test_kernel_otp_does_not_click_again_after_a_request_was_observed():
    otp = kernel_module("core.kernels.browser.roxy.registration.otp")
    driver = SimpleNamespace(
        _browser_submission_receipt=SimpleNamespace(endpoint_kind="otp_submit", phase="request_observed"),
        execute_script=lambda *_: pytest.fail("already dispatched request cannot click again"),
    )
    callbacks = otp.OtpFormCallbacks(
        record_submission=lambda *_args, **_kwargs: None,
        install_validate_hook=lambda *_args, **_kwargs: None,
        dispatch_trusted_click=lambda *_: pytest.fail("already dispatched request cannot click again"),
        logger=Mock(),
    )
    assert otp.submit_email_otp_current_form(driver, callbacks=callbacks) == {
        "clicked": False, "reason": "request_observed",
    }


def test_kernel_session_rejects_wrong_identity_without_storage():
    session = kernel_module("core.kernels.browser.roxy.registration.session")
    with pytest.raises(RuntimeError, match="session_identity_mismatch"):
        session.validate_registration_session_identity(
            {"user": {"email": "other@example.test"}}, "target@example.test",
        )


def test_kernel_profile_rejects_untrusted_origin_before_looking_at_fields():
    profile = kernel_module("core.kernels.browser.roxy.registration.profile")
    assert not profile.registration_profile_form_ready(
        object(), snapshot=lambda _: {
            "url": "https://auth.openai.com.evil.test/about-you",
            "inputs": [{"visible": True, "type": "text", "name": "name"},
                       {"visible": True, "type": "number", "name": "age"}],
        },
    )


@pytest.mark.parametrize("name", [
    "auth_flow", "config", "environment", "fingerprint", "http_client", "http_client_wreq",
    "mail_provider", "sentinel", "sentinel_quickjs", "tls_fingerprint",
])
def test_legacy_upstream_modules_share_the_kernel_module_and_patch_identity(name):
    current = kernel_module(f"core.kernels.protocol.protocol_oss_2.upstream.{name}")
    legacy = importlib.import_module(f"core.registration.protocol_oss_2.upstream.{name}")
    assert legacy is current
    assert Path(current.__file__).parts[-5:-2] == ("kernels", "protocol", "protocol_oss_2")


def test_upstream_auth_flow_can_create_an_explicit_session_without_domain_runtime():
    upstream = kernel_module("core.kernels.protocol.protocol_oss_2.upstream.auth_flow")
    fingerprint = importlib.import_module(
        "core.kernels.protocol.protocol_oss_2.upstream.fingerprint"
    ).generate_fingerprint(country_code="US", browser_family="chrome")
    config = importlib.import_module(
        "core.kernels.protocol.protocol_oss_2.upstream.config"
    ).Config(proxy="http://fixture.invalid:8080")
    sessions = []

    def create(**kwargs):
        session = SimpleNamespace(headers={}, cookies={})
        sessions.append((session, kwargs))
        return session

    with patch("core.registration.protocol_oss_2.runtime.create_http_session",
               side_effect=AssertionError("kernel cannot import a domain session factory")):
        flow = upstream.AuthFlow(config, fingerprint=fingerprint, session_factory=create)
    assert flow.session is sessions[0][0]
    assert sessions[0][1]["proxy"] == "http://fixture.invalid:8080"


def test_registration_kernel_runner_is_a_real_execution_owner():
    runner = kernel_module("core.kernels.protocol.protocol_oss_2.registration.runner")
    assert callable(runner.execute_upstream_protocol)
    assert runner.execute_upstream_protocol.__module__.startswith("core.kernels.")


def test_roxy_authentication_kernel_owns_the_page_flow():
    runner = kernel_module("core.kernels.browser.roxy.registration.runner")
    assert callable(runner.execute_registration_auth)
    assert runner.execute_registration_auth.__module__.startswith("core.kernels.")


@pytest.mark.parametrize("guarded_member", ["resume", "checkpoint"])
def test_roxy_kernel_uses_domain_recovery_callbacks_without_reading_private_state(guarded_member):
    from core.registration import roxy
    from tests.registration.test_registration_resume_session import RetainedWindowFlowTests

    runner = kernel_module("core.kernels.browser.roxy.registration.runner")
    execute = runner.execute_registration_auth
    events = []

    class Recovery:
        def resume(self):
            if guarded_member == "resume":
                raise AssertionError("kernel cannot resume a durable recovery object directly")
            return False

        @property
        def checkpoint(self):
            if guarded_member == "checkpoint":
                raise AssertionError("kernel cannot read a private password checkpoint")
            return None

    recovery = Recovery()

    def resume_in_domain(current):
        assert current is recovery
        events.append("resume")
        return False

    def confirmed_in_domain(current, password, already_confirmed):
        assert current is recovery
        assert password == "unit-original-password"
        events.append("confirmed")
        return True

    def with_domain_callbacks(*args, callbacks, **kwargs):
        injected = SimpleNamespace(**{
            **vars(callbacks),
            "resume_password_recovery": resume_in_domain,
            "password_recovery_confirms": confirmed_in_domain,
        })
        return execute(*args, callbacks=injected, **kwargs)

    flow = RetainedWindowFlowTests()
    with (
        flow.retained_context(page=roxy.PageState.PROFILE) as (_driver, mocks),
        patch.object(roxy, "_registration_password_recovery_session", return_value=recovery),
        patch.object(runner, "execute_registration_auth", side_effect=with_domain_callbacks),
    ):
        result = flow.run_registration()
    assert result["success"], result.get("error")
    assert events == ["resume", "confirmed"]
    assert mocks["persist"].call_args.kwargs["extra"]["account_password_state"] == "confirmed"


def test_protocol_transport_kernel_does_not_read_streaming_response_body():
    transport = kernel_module("core.kernels.protocol.protocol_oss_2.registration.transport")

    class Response:
        status_code = 200

        @property
        def content(self):
            raise AssertionError("streaming navigation body cannot be consumed")

        @property
        def text(self):
            raise AssertionError("streaming navigation body cannot be consumed")

    response = Response()
    observations = []
    callbacks = transport.ProtocolTransportCallbacks(
        check_stop=lambda: None, is_cancelled=lambda _: False,
        context_active=lambda: False, current_route_recovery=lambda: None,
        replace_route_capture=lambda *_args: None,
        record_protocol_exchange=lambda **fact: observations.append(fact["response"].content),
        vendor_cancelled=BaseException, vendor_route_recovery=BaseException,
        perf_counter=lambda: 100.0,
    )
    session = transport.ObservedSession(
        SimpleNamespace(request=lambda *_args, **_kwargs: response),
        {"capture": None}, callbacks=callbacks,
    )
    assert session.get("https://chatgpt.com/", stream=True) is response
    assert observations == [b""]


def test_cold_upstream_import_avoids_domain_initialization_and_private_log_output():
    result = subprocess.run(
        [sys.executable, "-c", """
import logging
import sys
from core.kernels.protocol.protocol_oss_2.upstream.auth_flow import AuthFlow
assert "core.registration.protocol_oss_2.runtime" not in sys.modules
assert "core.registration.service" not in sys.modules
assert "core.storage" not in sys.modules
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger(AuthFlow.__module__).warning("private-upstream-response-fixture")
"""],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
