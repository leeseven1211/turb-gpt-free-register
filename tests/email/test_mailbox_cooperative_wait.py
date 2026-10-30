"""只有显式MFA调用域才裁剪收码请求并调用原线程检查点。"""
from unittest.mock import Mock, patch

import pytest

from core.auth.state_machine import CancellationRequested
from core.auth.state_machine import StageBudget, StageTimeout
from core.email import mailbox_wait, provider
from core.email.email_butler import client
from core.email import forward_imap
import threading
import time


def test_cooperative_timeout_and_context_restore_without_global_change():
    seen = []
    assert mailbox_wait.bounded_timeout(30) == 30
    with mailbox_wait.use_cooperative_wait(lambda: seen.append("检查")):
        assert mailbox_wait.bounded_timeout(30) == 2
        assert mailbox_wait.request_kwargs(30) == {"timeout": 2}
    assert seen
    assert mailbox_wait.bounded_timeout(30) == 30
    assert mailbox_wait.request_kwargs(30) == {}


def test_control_signal_escapes_provider_generic_retry_then_restores_original_error():
    error = CancellationRequested("停止")
    swallowed = []
    with pytest.raises(CancellationRequested) as raised:
        with mailbox_wait.use_cooperative_wait(lambda: (_ for _ in ()).throw(error)):
            try:
                mailbox_wait.bounded_timeout(30)
            except Exception:
                swallowed.append(True)
    assert raised.value is error
    assert not swallowed


def test_email_butler_shortens_only_explicit_cooperative_long_poll():
    calls = []

    def request(*_args, **kwargs):
        calls.append(kwargs["json"])
        return {"verification_code": "123456"}

    with patch.object(client, "_request", side_effect=request):
        with mailbox_wait.use_cooperative_wait(lambda: None):
            assert client.fetch_inbound_otp("unit@example.test", after_ts=123.0, max_wait=240) == "123456"
        assert client.fetch_inbound_otp("unit@example.test", after_ts=123.0, max_wait=240) == "123456"
    assert calls[0]["timeout_seconds"] == 1
    assert calls[1]["timeout_seconds"] == 75
    assert calls[0]["since"] == calls[1]["since"]


def test_provider_checks_page_before_returning_candidate_without_new_generation():
    checks = []
    with patch.object(provider, "resolve_email_source", return_value="email_butler"), \
            patch("core.email.derivation.find_binding", return_value=None), \
            patch.object(client, "fetch_latest_otp", return_value="123456"), \
            patch("core.auth.email_guard.begin_generation") as generation:
        assert provider.wait_for_otp("unit@example.test", after_ts=123.0,
            page_checkpoint=lambda: checks.append("检查"), force_service=True) == "123456"
    assert len(checks) >= 2
    generation.assert_called_once_with(123.0)


def test_nested_contexts_restore_callbacks_after_inner_error():
    calls = []
    with mailbox_wait.use_cooperative_wait(lambda: calls.append("外层"), request_timeout=1.5):
        with pytest.raises(ValueError, match="页面错误"):
            with mailbox_wait.use_cooperative_wait(lambda: None, request_timeout=0.5):
                assert mailbox_wait.bounded_timeout(30) == 0.5
                raise ValueError("页面错误")
        before = len(calls)
        assert mailbox_wait.bounded_timeout(30) == 1.5
        assert len(calls) == before + 1
    assert mailbox_wait.bounded_timeout(30) == 30


def test_cooperative_sleep_preserves_original_deadline_and_cancellation():
    now = [0.0]
    checks = []
    budget = StageBudget.start(1.5, clock=lambda: now[0])
    with pytest.raises(StageTimeout):
        with mailbox_wait.use_budget(budget), mailbox_wait.use_cooperative_wait(lambda: checks.append(now[0])):
            with patch("core.auth.state_machine.time.sleep", side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds)):
                mailbox_wait.bounded_sleep(5)
    assert now[0] <= 1.5
    assert budget.deadline == 1.5
    assert checks
    assert mailbox_wait.current_budget() is None
    assert mailbox_wait.bounded_timeout(30) == 30


def test_forward_imap_blocking_command_observes_page_on_owner_thread_and_aborts_socket():
    owner = threading.get_ident()
    started = threading.Event()
    release = threading.Event()
    checked = []
    mail = Mock()
    error = RuntimeError("页面已转入TOTP")

    def checkpoint():
        checked.append(threading.get_ident())
        if started.is_set():
            raise error

    def command():
        started.set()
        release.wait(0.8)

    began = time.monotonic()
    try:
        with pytest.raises(RuntimeError) as raised:
            with mailbox_wait.use_budget(StageBudget.start(2)), mailbox_wait.use_cooperative_wait(checkpoint):
                forward_imap._IMAPBudget(2).call("读取", command, mail=mail)
        assert raised.value is error
        assert time.monotonic() - began < 0.6
        assert set(checked) == {owner}
        mail.sock.shutdown.assert_called_once()
    finally:
        release.set()


def test_forward_imap_socket_timeout_uses_only_explicit_request_cap():
    with mailbox_wait.use_cooperative_wait(lambda: None, request_timeout=0.5):
        assert forward_imap._IMAPBudget(10).socket_timeout() <= 0.5
    assert forward_imap._IMAPBudget(10).socket_timeout() > 0.5


@pytest.mark.parametrize("kind", ["qq", "forward"])
def test_control_signal_closes_half_open_imap_connection(kind):
    from core.email.cloudflare_domain import client as qq

    mail = Mock()
    created = [False]
    error = RuntimeError("页面已变化")

    def factory(*_args, **_kwargs):
        created[0] = True
        return mail

    def checkpoint():
        if created[0]:
            raise error

    with pytest.raises(RuntimeError) as raised:
        with mailbox_wait.use_cooperative_wait(checkpoint):
            if kind == "qq":
                with patch.object(qq._email_cfg, "QQ_EMAIL", "unit@example.test"), \
                        patch.object(qq._email_cfg, "QQ_IMAP_PASSWORD", "fixture"), \
                        patch.object(qq.imaplib, "IMAP4_SSL", side_effect=factory):
                    qq._connect_imap()
            else:
                with patch.object(forward_imap, "_settings", return_value=("localhost", 993, "unit", "fixture")), \
                        patch.object(forward_imap.imaplib, "IMAP4_SSL", side_effect=factory):
                    forward_imap._connect()
    assert raised.value is error
    mail.sock.close.assert_called_once()
    mail.file.close.assert_called_once()
    mail.login.assert_not_called()


def test_outlook_lock_wait_is_cooperative_only_inside_explicit_call():
    from core.email.outlook import client as outlook

    held = threading.Lock()
    held.acquire()
    checks = []
    error = RuntimeError("页面已切换")
    owner = threading.get_ident()
    release = threading.Timer(0.8, held.release)
    release.start()

    def checkpoint():
        checks.append(threading.get_ident())
        if len(checks) >= 3:
            raise error

    began = time.monotonic()
    try:
        with patch.object(outlook, '_sec_session_lock', held), \
                patch.object(outlook, '_sec_session', {'expiresAtMs': int(time.time() * 1000) + 120000}):
            with pytest.raises(RuntimeError) as raised:
                with mailbox_wait.use_cooperative_wait(checkpoint, poll_seconds=0.01):
                    outlook._get_security_session(None)
        assert raised.value is error
        assert time.monotonic() - began < 0.6
        assert set(checks) == {owner}
    finally:
        release.cancel()
        if held.locked():
            held.release()
