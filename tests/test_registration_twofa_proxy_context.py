"""注册链补跑账号配置时使用真实操作归属及本轮代理租约。"""
from contextlib import ExitStack
import json
import logging
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import codex_retry_service, protocol_traffic, registration_service, task_run_log
from core.proxy_chain import ProxyChainRelay
from core import roxybrowser_client


class RegistrationTwofaProxyContextTests(unittest.TestCase):
    def test_registration_retry_uses_resolved_operation_context_and_restores_parent(self):
        job = {"id": 31, "root_job_id": 21, "attempt_id": 41, "account_id": 44, "status": "running"}
        observed = []

        def worker(*_args, **_kwargs):
            observed.append((task_run_log.current_context(), protocol_traffic.current_correlation()))
            return {"ok": True, "status": "success"}

        with ExitStack() as stack:
            for name in ("_activate_job", "_deactivate_job", "_ensure_registration_run_context",
                         "_bind_progress_route_context", "_persist_job_progress", "_finish_registration_run"):
                stack.enter_context(patch.object(registration_service, name))
            stack.enter_context(patch.object(registration_service.db, "get_job", side_effect=lambda _id: dict(job)))
            stack.enter_context(patch.object(registration_service.db, "claim_job_for_execution", return_value=True))
            stack.enter_context(patch.object(registration_service.db, "finish_job_progress"))
            stack.enter_context(patch.object(registration_service.db, "update_job", side_effect=lambda _id, **fields: job.update(fields)))
            stack.enter_context(patch.object(registration_service, "is_stop_requested", return_value=False))
            resolve = stack.enter_context(patch.object(registration_service, "_registration_proxy_correlation", return_value={
                "account_id": 44, "operation_task_id": 501, "operation_run_id": 601,
            }))
            stack.enter_context(patch.object(codex_retry_service, "run_twofa_worker", side_effect=worker))
            stack.enter_context(patch.object(codex_retry_service, "release"))
            stack.enter_context(patch.object(registration_service.account_task_store, "finish_task"))
            stack.enter_context(task_run_log.stage_context(
                "twofa", task_id=31, run_id=71, identifier_namespace="registration", inherit=False,
            ))
            stack.enter_context(protocol_traffic.correlation_context(
                inherit=False, proxy_lease_id="previous-registration-lease", registration_job_id=31,
            ))
            before_log = task_run_log.current_context()
            before_proxy = protocol_traffic.current_correlation()
            registration_service._run_twofa_retry_job(31, "/tmp/unit-twofa.log", "unit@example.test", 44)
            self.assertEqual(task_run_log.current_context(), before_log)
            self.assertEqual(protocol_traffic.current_correlation(), before_proxy)

        resolve.assert_called_once()
        self.assertEqual(resolve.call_args.args[0], 31)
        self.assertEqual(resolve.call_args.args[1]["id"], 31)
        self.assertEqual(len(observed), 1)
        log_context, proxy_context = observed[0]
        self.assertEqual(log_context["identifier_namespace"], "operation")
        self.assertEqual((log_context["task_id"], log_context["run_id"]), (501, 601))
        self.assertNotIn("proxy_lease_id", proxy_context)

    def test_twofa_browser_retries_bind_current_lease_without_inheriting_registration_lease(self):
        def route(lease_id):
            value = SimpleNamespace(
                proxy_url="http://route.example:8080", provider="unit", mode="pool", region="JP",
                lease=SimpleNamespace(lease_id=lease_id), release=Mock(),
            )
            value.public_dict = Mock(return_value={"proxy_mode": "pool", "network_route": "proxy"})
            return value

        routes = [route("account-lease-1"), route("account-lease-2")]
        observed = []
        persisted = []

        def browser(*_args, **_kwargs):
            correlation = protocol_traffic.current_correlation()
            observed.append(correlation)
            expected = routes[len(observed) - 1].lease.lease_id
            relay = ProxyChainRelay("http://route.example:8080", listen_port=31280)
            with patch("core.proxy_lease_store.bind_browser_relay", side_effect=lambda **fields: (
                expected if fields.get("lease_id") == expected else None
            )) as bind:
                roxybrowser_client._remember_profile_relay("unit-profile", relay)
                persisted.append(bind.call_args.kwargs if bind.called else {})
            if len(observed) == 1:
                raise RuntimeError("net::ERR_TUNNEL_CONNECTION_FAILED")

        with tempfile.TemporaryDirectory() as tempdir, ExitStack() as stack:
            stack.enter_context(patch.object(codex_retry_service.db, "get_account_by_email", return_value={"id": 44}))
            stack.enter_context(patch.object(codex_retry_service.account_task_store, "get_task", return_value={}))
            stack.enter_context(patch.object(codex_retry_service.account_task_store, "append_event"))
            stack.enter_context(patch.object(task_run_log, "TaskRunLogHandler", return_value=logging.NullHandler()))
            stack.enter_context(patch("config.reload_all"))
            stack.enter_context(patch("core.account_proxy.acquire_account_proxy", side_effect=routes))
            stack.enter_context(patch.object(codex_retry_service, "check_stop_requested"))
            stack.enter_context(patch.object(codex_retry_service, "_build_roxy_account_setup", return_value=Mock()))
            stack.enter_context(patch.object(codex_retry_service.time, "sleep"))
            stack.enter_context(patch.object(codex_retry_service, "_RUNNING_THREADS", {}))
            stack.enter_context(patch.object(codex_retry_service, "_RESERVED_AT", {}))
            stack.enter_context(patch.object(codex_retry_service, "_STOP_REQUESTED", set()))
            stack.enter_context(patch.object(roxybrowser_client, "_PROFILE_RELAYS", {}))
            stack.enter_context(patch.object(roxybrowser_client._cfg, "ROXY_KEEP_BROWSER_OPEN", True))
            stack.enter_context(patch("core.roxy_codex_oauth.run_roxy_chatgpt_account_action", side_effect=browser))
            stack.enter_context(task_run_log.stage_context(
                "twofa", task_id=501, run_id=601, identifier_namespace="operation", inherit=False,
            ))
            stack.enter_context(protocol_traffic.correlation_context(
                inherit=False, proxy_lease_id="previous-registration-lease", registration_job_id=31,
            ))
            before = protocol_traffic.current_correlation()
            result = codex_retry_service.run_twofa_worker(
                "unit@example.test", task_id=81, target_log_path=Path(tempdir) / "twofa.log",
                clear_log=False, manage_task=False, steps={"password"}, password_driver_override="roxy",
            )
            self.assertEqual(protocol_traffic.current_correlation(), before)

        self.assertTrue(result["ok"], result.get("message"))
        self.assertEqual([value["proxy_lease_id"] for value in observed], ["account-lease-1", "account-lease-2"])
        self.assertTrue(all("registration_job_id" not in value for value in observed))
        self.assertEqual([value["lease_id"] for value in persisted], ["account-lease-1", "account-lease-2"])
        self.assertEqual([value["operation_task_id"] for value in persisted], [501, 501])

    def test_twofa_worker_writes_internal_logs_in_native_and_legacy_contexts(self):
        for native in (True, False):
            with self.subTest(native=native), tempfile.TemporaryDirectory() as tempdir, ExitStack() as stack:
                path = Path(tempdir) / "twofa.jsonl"
                route = SimpleNamespace(
                    proxy_url="http://route.example:8080", provider="unit", mode="pool", region="JP",
                    lease=SimpleNamespace(lease_id="account-lease"), release=Mock(),
                    public_dict=Mock(return_value={"proxy_mode": "pool", "network_route": "proxy"}),
                )
                stack.enter_context(patch.object(task_run_log, "_LOG_ROOT", Path(tempdir)))
                stack.enter_context(patch.object(codex_retry_service.db, "get_account_by_email", return_value={"id": 44}))
                stack.enter_context(patch.object(codex_retry_service.account_task_store, "get_task", return_value={}))
                stack.enter_context(patch.object(codex_retry_service.account_task_store, "append_event"))
                stack.enter_context(patch("config.reload_all"))
                stack.enter_context(patch("core.account_proxy.acquire_account_proxy", return_value=route))
                stack.enter_context(patch.object(codex_retry_service, "check_stop_requested"))
                stack.enter_context(patch.object(codex_retry_service, "_build_roxy_account_setup", return_value=Mock()))
                stack.enter_context(patch.object(codex_retry_service, "_RUNNING_THREADS", {}))
                stack.enter_context(patch.object(codex_retry_service, "_RESERVED_AT", {}))
                stack.enter_context(patch.object(codex_retry_service, "_STOP_REQUESTED", set()))
                stack.enter_context(patch("core.roxy_codex_oauth.run_roxy_chatgpt_account_action", side_effect=lambda *_args, **_kwargs: (
                    codex_retry_service.logger.warning("账号配置内部日志回归")
                )))
                context = {"task_id": 501, "run_id": 601, "identifier_namespace": "operation"} if native else {}
                stack.enter_context(task_run_log.stage_context("account_setup", inherit=False, **context))
                result = codex_retry_service.run_twofa_worker(
                    "unit@example.test", task_id=81, target_log_path=path, clear_log=False,
                    manage_task=False, steps={"password"}, password_driver_override="roxy",
                )
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

            self.assertTrue(result["ok"], result.get("message"))
            internal = [row for row in rows if row["message"] == "账号配置内部日志回归"]
            self.assertEqual(len(internal), 1)
            self.assertEqual(internal[0]["event_type"], "log.record")
            self.assertEqual(internal[0]["task_id"], 501 if native else 81)
            self.assertEqual(internal[0]["run_id"], 601 if native else None)


if __name__ == "__main__":
    unittest.main()
