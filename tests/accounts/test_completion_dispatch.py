# -*- coding: utf-8 -*-
import json
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core import account_task_store
from core.accounts.liveness import service as live_check_service
from core.storage import postgres as postgres_store, records as record_store
from core.operations import run_log as task_run_log
from core.operations import task_gateway
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase
from tests.support_settlement import install_native_settlement_fixture
from webui import runtime


class CompletionDispatchTests(PostgresTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        log_root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(task_run_log, "_LOG_ROOT", log_root))
        self.stack.enter_context(patch.object(task_run_log, "_TASK_LOG_ROOT", log_root / "tasks"))
        self.stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        # 只执行本用例显式派发的父任务，子任务保持在持久队列中。
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        # 这些用例验证协调器派发，不验证本机是否装了浏览器：按“有浏览器”部署固定能力位。
        self.stack.enter_context(patch("core.runtime.capabilities.browser_enabled", return_value=True))
        self.setup_worker = self.stack.enter_context(
            patch.object(runtime.codex_retry_service, "run_twofa_worker"),
        )
        account_task_store.init()
        operation.reset_ready()
        operation.init()
        # 注册会更新多个全局字典，测试结束后完整恢复之前的注册内容。
        for registry_name in (
            "_OPERATION_HANDLERS", "_OPERATION_HANDLER_ALLOWLISTS",
            "_OPERATION_ACTIONS", "_OPERATION_ACTION_SOURCES",
            "_DISPATCH_HANDLERS", "_DISPATCH_CAPACITY_HANDLERS",
        ):
                self.stack.enter_context(patch.dict(getattr(task_gateway, registry_name), {}))
        # 部署能力校验会读运行配置快照；测试 schema 不迁移配置库，按“未启用数据库配置”
        # 走文件/环境默认值，避免 config_not_migrated 打断派发用例。
        self.stack.enter_context(patch("config.runtime.load_values", return_value=None))
        task_gateway.register_operation_handler(
            "account_completion",
            runtime._handle_native_account_completion,
            source_systems=("webui_runtime",),
            config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST,
        )
        self.settlement_fixture = install_native_settlement_fixture(self, timeout=10)

    def tearDown(self):
        self.settlement_fixture.close()

    def test_native_setup_passes_valid_country_and_real_execution_fence(self):
        email = "country-fence@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": email, "access_token": "synthetic-at", "plan_check_status": "success",
        })
        task_gateway.register_operation_handler(
            "account_setup_retry", runtime._handle_native_account_setup,
            source_systems=("webui_runtime",), config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST,
        )
        for country, expected in (("JP", True), ("invalid", False)):
            with self.subTest(country=country):
                queued = task_gateway.submit_durable_operation(
                    task_type="account_setup_retry", account_id=account_id, email=email,
                    source_system="webui_runtime", source_id=f"country-fence:{country}",
                    data={"steps": ["plan_check"], "proxy_country_override": country},
                    config_snapshot={}, config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST), dispatch=False,
                )
                self.setup_worker.reset_mock()
                self.setup_worker.return_value = {"ok": True, "status": "success"}
                task_gateway._execute_operation_handler("account_setup_retry", int(queued["run_id"]))
                if expected:
                    options = self.setup_worker.call_args.kwargs
                    self.assertEqual("JP", options["proxy_country_override"])
                    fence = options["execution_fence"]
                    self.assertEqual(int(queued["run_id"]), fence["run_id"])
                    self.assertTrue(fence["execution_id"])
                    self.assertTrue(fence["lease_token"])
                else:
                    self.setup_worker.assert_not_called()

    def test_persisted_password_change_recovers_reset_intent_without_changing_setup(self):
        for task_type, completion_auth, expected_reset in (
            ("password_change", False, True),
            ("password_setup", False, False),
            ("account_setup_retry", True, False),
        ):
            with self.subTest(task_type=task_type):
                email = f"{task_type}@example.test"
                account_id = record_store.insert_row(record_store.ACCOUNTS, {
                    "email": email,
                    "access_token": "synthetic-at",
                    "extra_json": {"account_password": "synthetic-password", "account_password_state": "confirmed"},
                })
                task_gateway.register_operation_handler(
                    task_type, runtime._handle_native_account_setup,
                    source_systems=("webui_runtime",),
                    config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST,
                )
                queued = task_gateway.submit_durable_operation(
                    task_type=task_type, account_id=account_id, email=email,
                    source_system="webui_runtime", source_id=f"reset-intent:{task_type}",
                    data={
                        "steps": ["password"],
                        "completion_auth": completion_auth,
                        "force_password_reset": expected_reset,
                    },
                    config_snapshot={}, config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST),
                    dispatch=False,
                )
                persisted = operation.get_run(int(queued["run_id"]))
                # 真实持久化会去掉含 password 的键，改密意图仍须从任务类型恢复。
                self.assertNotIn("force_password_reset", persisted["data"])
                self.setup_worker.reset_mock()
                self.setup_worker.return_value = {"ok": True, "status": "success"}

                result = task_gateway._execute_operation_handler(task_type, int(queued["run_id"]))

                self.assertEqual("success", result["status"])
                self.assertEqual(expected_reset, self.setup_worker.call_args.kwargs["force_password_reset"])

    def test_coordinator_dispatches_setup_child_with_real_storage(self):
        email = "completion-dispatch@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": email,
            "access_token": "synthetic-access-token",
            "codex_status": "failed",
            "created_at": "2026-10-30T10:00:00",
            "updated_at": "2026-10-30T10:00:00",
        })
        snapshot = {
            "twofa_driver": "browser",
            "codex_driver": "browser",
            "config_snapshot_revision": 37,
        }
        queued = task_gateway.submit_durable_operation(
            task_type="account_completion",
            account_id=account_id,
            email=email,
            source_system="webui_runtime",
            source_id="completion-dispatch-parent",
            trigger="manual_account_completion",
            resource_family="completion_coordinator",
            data={"planned_steps": ["password", "twofa", "codex"]},
            config_snapshot=snapshot,
            config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST),
            dispatch=False,
        )
        self.assertTrue(queued["accepted"])

        result = task_gateway._execute_operation_handler(
            "account_completion", int(queued["run_id"]),
        )
        self.settlement_fixture.wait_for_run_released(int(queued["run_id"]))

        self.assertEqual("partial_success", result["status"])
        parent = operation.get_run(int(queued["run_id"]))
        self.assertEqual("partial_success", parent["status"])
        self.assertEqual("completion_coordinator", parent["resource_family"])
        child_id = int(parent["result_summary"]["account_setup"]["task_id"])
        child = operation.get_task(child_id, include_events=False)
        self.assertEqual("account_setup_retry", child["task_type"])
        self.assertEqual("queued", child["status"])
        child_run = operation.get_run(int(child["last_run_id"]))
        self.assertEqual("queued", child_run["status"])
        self.assertEqual("openai_interactive", child_run["resource_family"])
        self.assertEqual(["password", "twofa"], child_run["data"]["steps"])
        self.assertTrue(child_run["data"]["completion_auth"])
        self.assertEqual(parent["data"]["config_snapshot"], child_run["data"]["config_snapshot"])
        self.assertEqual("browser", child_run["data"]["config_snapshot"]["twofa_driver"])
        self.assertEqual("browser", child_run["data"]["config_snapshot"]["codex_driver"])
        self.setup_worker.assert_not_called()
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT child_source_system, child_source_id, status, payload "
                f"FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            dependencies = cur.fetchall()
            cur.execute(
                f"SELECT COUNT(*) FROM {postgres_store.qualified('account_operation_leases')} "
                "WHERE run_id=%s",
                (int(queued["run_id"]),),
            )
            self.assertEqual(0, cur.fetchone()[0])
        self.assertEqual(1, len(dependencies))
        child_system, child_source, status, payload = dependencies[0]
        self.assertEqual("webui_runtime", child_system)
        self.assertEqual(str(child_id), child_source)
        self.assertEqual("waiting", status)
        self.assertEqual(["codex"], payload["remaining_steps"])

        # 子任务排队期间开始注册时，实际远端操作前仍须退队等待。
        record_store.insert_row(record_store.JOBS, {
            "job_type": "registration", "status": "running",
            "account_id": account_id, "email": email,
        })
        task_gateway.register_operation_handler(
            "account_setup_retry", runtime._handle_native_account_setup,
            source_systems=("webui_runtime",),
            config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST,
        )
        blocked = task_gateway._execute_operation_handler("account_setup_retry", int(child["last_run_id"]))
        self.assertEqual("deferred", blocked["status"])
        self.assertEqual("queued", operation.get_run(int(child["last_run_id"]))["status"])
        self.setup_worker.assert_not_called()
        operation.finish_run(int(child["last_run_id"]), status="success", result_summary={"ok": True})
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            self.assertEqual("ready", cur.fetchone()[0])

    def test_registration_starting_during_refresh_handoff_requeues_parent(self):
        email = "completion-race@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {"email": email, "access_token": ""})
        queued = task_gateway.submit_durable_operation(
            task_type="account_completion", account_id=account_id, email=email,
            source_system="webui_runtime", source_id="completion-refresh-race",
            trigger="manual_account_completion", resource_family="completion_coordinator",
            data={"planned_steps": ["refresh_at"]},
            config_snapshot={"refresh_at_enabled": True},
            config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST), dispatch=False,
        )
        with patch("core.accounts.completion.active_registration_job", side_effect=[None, {"id": 836, "status": "running"}]):
            result = task_gateway._execute_operation_handler("account_completion", int(queued["run_id"]))
        self.assertEqual("deferred", result["status"])
        parent = operation.get_run(int(queued["run_id"]))
        self.assertEqual("queued", parent["status"])
        self.assertFalse((parent.get("result_summary") or {}).get("awaiting_steps"))
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            self.assertEqual(0, cur.fetchone()[0])

    def _complete_setup_behind_native_blocker(self, *, finish_before=None, legacy_collision=False):
        """真实约束冲突、依赖和 Run 续接；远端写入只用明确的合成完成事实。"""
        email = "completion-blocker@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": email, "access_token": "synthetic-at", "plan_check_status": "failed",
        })
        snapshot = {
            "password_enabled": False, "password_reset_enabled": False,
            "plan_check_enabled": True, "twofa_enabled": False,
            "codex_enabled": False, "refresh_at_enabled": False,
        }
        blocker = task_gateway.submit_durable_operation(
            task_type="token_refresh", account_id=account_id, email=email,
            source_system="native_operations", source_id="unrelated-native-blocker",
            resource_family="openai_interactive", dispatch=False,
        )
        self.assertTrue(blocker["accepted"])
        if legacy_collision:
            # 直接构造旧记录，避免旧 create_task 的自动 native 投影污染此模型碰撞用例。
            with postgres_store.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {postgres_store.qualified('account_action_tasks')} "
                    "(id, task_uuid, task_type, email_snapshot, trigger, status, queued_at) "
                    "VALUES (%s, %s, 'codex_retry', 'different-legacy@example.test', 'manual', 'failed', %s)",
                    (blocker["task_id"], "legacy-id-collision", "2026-11-15T00:00:00+00:00"),
                )
            legacy = account_task_store.get_task(int(blocker["task_id"]))
            self.assertEqual("codex_retry", legacy["task_type"])
            self.assertEqual("failed", legacy["status"])
        parent = task_gateway.submit_durable_operation(
            task_type="account_completion", account_id=account_id, email=email,
            source_system="webui_runtime", source_id="completion-behind-native-blocker",
            resource_family="completion_coordinator", data={"planned_steps": ["plan_check"]},
            config_snapshot=snapshot, config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST),
            dispatch=False,
        )
        self.assertTrue(parent["accepted"])
        original_submit = task_gateway.submit_durable_operation
        original_read = operation.get_task
        original_register = operation.register_task_dependency
        submissions = []
        finished_early = False

        def observe_real_submit(**kwargs):
            result = original_submit(**kwargs)
            submissions.append(dict(result))
            return result

        def finish_blocker_once():
            nonlocal finished_early
            if not finished_early:
                operation.finish_run(int(blocker["run_id"]), status="success", result_summary={"ok": True})
                finished_early = True

        def read_with_race(task_id, *, include_events=True):
            if finish_before == "lookup" and task_id == blocker["task_id"] and submissions:
                finish_blocker_once()
            return original_read(task_id, include_events=include_events)

        def register_with_race(**kwargs):
            if finish_before == "dependency":
                finish_blocker_once()
            return original_register(**kwargs)

        with (
            patch.object(task_gateway, "submit_durable_operation", side_effect=observe_real_submit),
            patch.object(operation, "get_task", autospec=True, side_effect=read_with_race),
            patch.object(operation, "register_task_dependency", side_effect=register_with_race),
            patch.object(task_gateway, "get_task", autospec=True,
                         side_effect=AssertionError("native IDs must not read the legacy table")),
            patch.object(task_gateway, "notify_dependency_ready"),
        ):
            result = task_gateway._execute_operation_handler("account_completion", int(parent["run_id"]))
            self.settlement_fixture.wait_for_run_released(int(parent["run_id"]))

        # 真正 create_runtime_task 的唯一约束冲突必须产生缺 source 的 busy 回执。
        self.assertEqual(1, len(submissions))
        self.assertFalse(submissions[0]["accepted"])
        self.assertTrue(submissions[0]["busy"])
        self.assertEqual(blocker["task_id"], submissions[0]["task_id"])
        self.assertNotIn("source_id", submissions[0])
        self.assertEqual("partial_success", result["status"])
        first_run = operation.get_run(int(parent["run_id"]))
        self.assertEqual(["plan_check"], first_run["result_summary"]["continuation_steps"])
        self.assertEqual(blocker["task_id"], first_run["result_summary"]["account_setup"]["task_id"])
        self.setup_worker.assert_not_called()
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT child_source_system, child_source_id, status, payload "
                f"FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system='webui_runtime' AND parent_source_id=%s",
                (str(parent["task_id"]),),
            )
            edges = cur.fetchall()
        self.assertEqual(1, len(edges))
        system, child_id, state, payload = edges[0]
        self.assertEqual(("native_operations", str(blocker["task_id"])), (system, child_id))
        self.assertEqual("ready" if finish_before else "waiting", state)
        self.assertEqual(["plan_check"], payload["remaining_steps"])
        self.assertEqual(parent["run_id"], payload["parent_run_id"])
        if finish_before:
            self.assertTrue(finished_early)
        else:
            finish_blocker_once()

        ready = operation.list_ready_task_dependencies()
        self.assertEqual(1, len(ready))
        runtime._handle_ready_completion_dependency(operation.claim_task_dependency(ready[0]["id"]))
        resumed = operation.get_task(int(parent["task_id"]), include_events=False)
        self.assertEqual(2, len(resumed["runs"]))
        self.assertNotEqual(parent["run_id"], resumed["last_run_id"])
        setup_result = task_gateway._execute_operation_handler("account_completion", int(resumed["last_run_id"]))
        self.settlement_fixture.wait_for_run_released(int(resumed["last_run_id"]))
        self.assertEqual("partial_success", setup_result["status"])
        setup_id = operation.get_run(int(resumed["last_run_id"]))["result_summary"]["account_setup"]["task_id"]
        self.assertNotEqual(blocker["task_id"], setup_id)
        setup = operation.get_task(int(setup_id), include_events=False)
        setup_run = operation.get_run(int(setup["last_run_id"]))
        self.assertEqual("account_setup_retry", setup["task_type"])
        self.assertEqual(["plan_check"], setup_run["data"]["steps"])
        self.assertEqual("openai_interactive", setup_run["resource_family"])

        record_store.patch_row(record_store.ACCOUNTS, account_id, {"plan_check_status": "success"})
        operation.finish_run(int(setup["last_run_id"]), status="success", result_summary={"ok": True})
        ready = operation.list_ready_task_dependencies()
        self.assertEqual(1, len(ready))
        runtime._handle_ready_completion_dependency(operation.claim_task_dependency(ready[0]["id"]))
        closing = operation.get_task(int(parent["task_id"]), include_events=False)
        self.assertEqual(3, len(closing["runs"]))
        final = task_gateway._execute_operation_handler("account_completion", int(closing["last_run_id"]))
        self.assertEqual("success", final["status"])
        completed = operation.get_task(int(parent["task_id"]), include_events=False)
        self.assertEqual("success", completed["status"])
        self.assertFalse(completed["result_summary"].get("awaiting_steps"))
        self.assertEqual([], completed["result_summary"]["pending_steps"])
        self.assertEqual([], operation.list_ready_task_dependencies())
        self.setup_worker.assert_not_called()
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {postgres_store.qualified('operation_tasks')} "
                "WHERE account_id=%s AND task_type='account_setup_retry'",
                (account_id,),
            )
            self.assertEqual(1, cur.fetchone()[0])

    def test_native_setup_family_conflict_ignores_colliding_legacy_id_and_resumes_to_success(self):
        self._complete_setup_behind_native_blocker(legacy_collision=True)

    def test_native_setup_blocker_finishing_before_lookup_still_resumes_to_success(self):
        self._complete_setup_behind_native_blocker(finish_before="lookup")

    def test_native_setup_blocker_finishing_before_dependency_still_resumes_to_success(self):
        self._complete_setup_behind_native_blocker(finish_before="dependency")

    def test_setup_child_finishing_before_handoff_still_wakes_parent(self):
        email = "completion-fast@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {"email": email, "access_token": "synthetic-at"})
        parent = task_gateway.submit_durable_operation(
            task_type="account_completion", account_id=account_id, email=email,
            source_system="webui_runtime", source_id="completion-fast-parent",
            resource_family="completion_coordinator", data={"planned_steps": ["twofa"]},
            config_snapshot={}, config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST), dispatch=False,
        )
        original_submit = runtime.account_task_store.submit_durable_operation

        def fast_setup(**kwargs):
            child = original_submit(**kwargs)
            operation.finish_run(int(child["run_id"]), status="success", result_summary={"ok": True})
            return child

        with patch.object(runtime.account_task_store, "submit_durable_operation", side_effect=fast_setup):
            result = task_gateway._execute_operation_handler("account_completion", int(parent["run_id"]))
            self.settlement_fixture.wait_for_run_released(int(parent["run_id"]))
        self.assertEqual("partial_success", result["status"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(parent["task_id"])),
            )
            self.assertEqual("ready", cur.fetchone()[0])

    def test_historical_incomplete_account_dispatches_refresh_child_with_real_storage(self):
        email = "completion-refresh@example.test"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": email,
            "access_token": "",
            "extra_json": json.dumps({
                "registration_checkpoint": "email_verification_pending",
                "account_password": "synthetic-password",
            }),
            "created_at": "2026-10-30T10:00:00",
            "updated_at": "2026-10-30T10:00:00",
        })
        settings = {
            "refresh_at_enabled": True,
            "password_enabled": False,
            "plan_check_enabled": True,
            "twofa_enabled": False,
            "codex_enabled": False,
        }
        snapshot = {**settings, "at_refresh_driver": "roxy"}
        queued = task_gateway.submit_durable_operation(
            task_type="account_completion",
            account_id=account_id,
            email=email,
            source_system="webui_runtime",
            source_id="completion-refresh-parent",
            trigger="manual_account_completion",
            resource_family="completion_coordinator",
            data={"planned_steps": ["refresh_at", "plan_check"]},
            config_snapshot=snapshot,
            config_allowlist=tuple(runtime._RUNTIME_CONFIG_ALLOWLIST),
            dispatch=False,
        )
        self.assertTrue(queued["accepted"])

        with (
            patch("config.account.completion_settings", return_value=settings),
            patch.object(live_check_service, "get_config_snapshot", return_value={"ACCOUNT_AT_REFRESH_DRIVER": "roxy"}),
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_run_live_check") as remote_worker,
            patch("core.registration.service.retry_job") as registration_retry,
        ):
            result = task_gateway._execute_operation_handler(
                "account_completion", int(queued["run_id"]),
            )
            self.settlement_fixture.wait_for_run_released(int(queued["run_id"]))

        self.assertEqual("partial_success", result["status"])
        parent = operation.get_run(int(queued["run_id"]))
        self.assertEqual("partial_success", parent["status"])
        child_id = int(parent["result_summary"]["refresh_at"]["task_id"])
        child = operation.get_task(child_id, include_events=False)
        self.assertEqual("token_refresh", child["task_type"])
        self.assertEqual("queued", child["status"])
        child_run = operation.get_run(int(child["last_run_id"]))
        self.assertEqual("queued", child_run["status"])
        self.assertEqual("openai_interactive", child_run["resource_family"])
        # 用真实存储验证补全认证标记经过统一脱敏后仍保留。
        self.assertTrue(child_run["data"]["completion_auth"])
        self.assertTrue(child_run["data"]["force_refresh"])
        registration_retry.assert_not_called()
        remote_worker.assert_not_called()
        self.setup_worker.assert_not_called()

        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT child_source_system, child_source_id, status, payload "
                f"FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            dependencies = cur.fetchall()
        self.assertEqual(1, len(dependencies))
        child_system, child_source, status, payload = dependencies[0]
        self.assertEqual("native_operations", child_system)
        self.assertEqual(str(child_id), child_source)
        self.assertEqual("waiting", status)
        self.assertEqual(["plan_check"], payload["remaining_steps"])
        record_store.patch_row(record_store.ACCOUNTS, account_id, {"access_token": "synthetic-refreshed-at"})
        operation.finish_run(int(child["last_run_id"]), status="success", result_summary={"ok": True})
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {postgres_store.qualified('operation_task_dependencies')} "
                "WHERE parent_source_system=%s AND parent_source_id=%s",
                ("webui_runtime", str(queued["task_id"])),
            )
            self.assertEqual("ready", cur.fetchone()[0])

        # 逐次消费真实依赖，刷新、配置、空计划收口形成完整的持久续接链。
        refresh_dependency = operation.list_ready_task_dependencies()[0]
        runtime._handle_ready_completion_dependency(operation.claim_task_dependency(refresh_dependency["id"]))
        resumed = operation.get_task(int(queued["task_id"]), include_events=False)
        setup_result = task_gateway._execute_operation_handler("account_completion", int(resumed["last_run_id"]))
        self.settlement_fixture.wait_for_run_released(int(resumed["last_run_id"]))
        self.assertEqual("partial_success", setup_result["status"])
        setup_id = int(operation.get_run(int(resumed["last_run_id"]))["result_summary"]["account_setup"]["task_id"])
        setup = operation.get_task(setup_id, include_events=False)
        self.assertEqual(["plan_check"], operation.get_run(int(setup["last_run_id"]))["data"]["steps"])
        record_store.patch_row(record_store.ACCOUNTS, account_id, {"plan_check_status": "success"})
        operation.finish_run(int(setup["last_run_id"]), status="success", result_summary={"ok": True})
        setup_dependency = operation.list_ready_task_dependencies()[0]
        runtime._handle_ready_completion_dependency(operation.claim_task_dependency(setup_dependency["id"]))
        closing = operation.get_task(int(queued["task_id"]), include_events=False)
        finished = task_gateway._execute_operation_handler("account_completion", int(closing["last_run_id"]))
        self.assertEqual("success", finished["status"])
        final_parent = operation.get_task(int(queued["task_id"]), include_events=False)
        self.assertEqual("success", final_parent["status"])
        self.assertFalse(final_parent["result_summary"].get("awaiting_steps"))
        self.assertEqual([], operation.list_ready_task_dependencies())
