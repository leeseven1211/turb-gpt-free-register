"""统一步骤、事件与日志的存储回归。"""
from pathlib import Path
import tempfile
from unittest.mock import patch

from core import db, operation_task_store, task_run_log
from core.operations import legacy_task_store
from tests.support_pg import PostgresTestCase


class TaskObservationStoreTests(PostgresTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.patches = [
            patch.object(task_run_log, "_LOG_ROOT", root),
            patch.object(task_run_log, "_TASK_LOG_ROOT", root / "tasks"),
            patch.object(legacy_task_store, "_SCHEMA", self.schema),
        ]
        for item in self.patches:
            item.start()
        legacy_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()

    def tearDown(self):
        task_run_log.clear_current_context()
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_native_event_and_log_share_identity_and_failure_location(self):
        task = operation_task_store.create_runtime_task(task_type="token_refresh", account_id=4001, email="native@example.test", trigger="test")
        task_id, run_id = int(task["id"]), int(task["run"]["id"])
        operation_task_store.append_runtime_event(run_id, stage="network", state="success", message="网络已就绪")
        failed = operation_task_store.append_runtime_event(run_id, stage="email_otp", state="failed", message="邮箱验证码等待超时")
        operation_task_store.finish_run(run_id, status="failed", error="邮箱验证码等待超时")

        logs = operation_task_store.read_task_run_log(task_id, run_id, cursor=0)["items"]
        line = next(item for item in logs if item.get("event_uuid") == failed["event_uuid"])
        self.assertEqual(failed["id"], line["event_id"])
        self.assertEqual("authenticate", line["main_step_id"])
        self.assertEqual(task_id, line["task_id"])
        self.assertEqual(run_id, line["run_id"])
        run = operation_task_store.get_run(run_id)
        self.assertEqual("complete", run["progress_stage"])
        self.assertEqual("email_otp", run["result_summary"]["failure_stage"])
        progress = operation_task_store.get_run_progress(task_id, run_id)
        self.assertEqual("email_otp", progress["failure"]["stage"])
        self.assertEqual(str(failed["id"]), str(progress["failure"]["event_id"]))
        self.assertEqual("explicit", progress["failure"]["evidence"])
        projected_task = operation_task_store.get_task(task_id)
        self.assertEqual("邮箱验证", projected_task["failure_stage_label"])
        listing = operation_task_store.list_tasks(task_id=str(task_id))
        self.assertTrue(all(item.get("label") for item in listing["facets"]["stage"]))

    def test_terminal_registration_progress_snapshot_is_cached_between_polls(self):
        """注册页 5 秒轮询不能反复重放终态 Run 的全部事件。"""
        from unittest.mock import patch
        from core.storage import operation

        job = db.create_job("icloud_hide")
        db.update_job_progress(job["id"], "email_otp", "success", "验证码已确认")
        db.update_job(job["id"], status="success")
        db.finish_job_progress(job["id"], success=True)
        operation.clear_progress_snapshot_cache()
        with patch(
            "core.storage.operation.build_progress_snapshot",
            wraps=operation.build_progress_snapshot,
        ) as build:
            first = operation.get_registration_progress([job["id"]])[job["id"]]
            second = operation.get_registration_progress([job["id"]])[job["id"]]
        self.assertEqual(1, build.call_count)
        self.assertEqual(first["progress"], second["progress"])

    def test_registration_transitions_survive_retry_and_share_log_uuid(self):
        job = db.create_job("icloud_hide", batch_id="observation-batch")
        for state in ("running", "failed", "running", "success"):
            db.update_job_progress(job["id"], "email_otp", state, "阶段转换")
        mapping = operation_task_store.get_registration_progress([job["id"]])[job["id"]]
        task_id, run_id = mapping["operation_task_id"], mapping["operation_run_id"]
        events = operation_task_store.list_task_events(task_id, run_id=run_id, after_id=0)["items"]
        transitions = [event for event in events if event["stage"] == "email_otp" and event["source_system"] == "registration_progress_events"]
        self.assertEqual(["stage.running", "stage.failed", "stage.running", "stage.success"], [event["event_type"] for event in transitions])
        self.assertEqual(4, len({event["event_uuid"] for event in transitions}))
        logs = operation_task_store.read_task_run_log(task_id, run_id, cursor=0)["items"]
        for event in transitions:
            line = next(item for item in logs if item.get("event_uuid") == event["event_uuid"])
            self.assertEqual(event["id"], line["event_id"])
        self.assertIsNone(mapping["progress"]["failure"])

    def test_later_registration_step_does_not_confirm_previous_running_step(self):
        job = db.create_job("icloud_hide")
        db.update_job_progress(job["id"], "email", "running", "准备邮箱")
        db.update_job_progress(job["id"], "browser", "running", "启动浏览器")
        self.assertEqual("running", db.get_job(job["id"])["progress_steps"]["email"]["state"])
        db.finish_job_progress(job["id"], success=True)
        step = db.get_job(job["id"])["progress_steps"]["email"]
        self.assertEqual("pending", step["state"])
        self.assertEqual("unconfirmed", step["evidence"])

    def test_registration_transition_history_survives_projection_failure(self):
        job = db.create_job("icloud_hide")
        from core.storage import db_legacy
        with patch.object(db_legacy, "_sync_operation_job"):
            for state in ("running", "failed", "running", "success"):
                db.update_job_progress(job["id"], "email_otp", state, "持久阶段证据")
        operation_task_store.sync_registration_job(job["id"])
        mapping = operation_task_store.get_registration_progress([job["id"]])[job["id"]]
        events = operation_task_store.list_task_events(mapping["operation_task_id"], run_id=mapping["operation_run_id"], after_id=0)["items"]
        transitions = [event for event in events if event["stage"] == "email_otp" and event["source_system"] == "registration_progress_events"]
        self.assertEqual(["stage.running", "stage.failed", "stage.running", "stage.success"], [event["event_type"] for event in transitions])

    def test_new_registration_stage_survives_template_extension(self):
        job = db.create_job("icloud_hide")
        db.update_job_progress(job["id"], "custom_driver_step", "running", "新增阶段")
        db.update_job_progress(job["id"], "custom_driver_step", "failed", "新增阶段失败")
        db.finish_job_progress(job["id"], success=False)
        progress = operation_task_store.get_registration_progress([job["id"]])[job["id"]]["progress"]
        self.assertEqual("custom_driver_step", progress["failure"]["stage"])
        self.assertTrue(any(step["id"] == "unknown:custom_driver_step" for step in progress["main_steps"]))

    def test_run_failure_does_not_overwrite_confirmed_stage_success(self):
        job = db.create_job("icloud_hide")
        db.update_job_progress(job["id"], "plan_check", "success", "查询成功")
        db.finish_job_progress(job["id"], success=False, detail="后续收口异常，位置待确认")
        self.assertEqual("success", db.get_job(job["id"])["progress_steps"]["plan_check"]["state"])

    def test_batch_distribution_uses_current_run_of_every_slot(self):
        from webui.route_helpers import _latest_progress_batch
        rows = [
            {"id": 1, "batch_id": "all-slots", "batch_index": 1, "status": "failed", "progress": {"failure": {"step_id": "authenticate", "label": "身份验证"}}},
            {"id": 2, "batch_id": "all-slots", "batch_index": 2, "status": "running", "progress": {"current": {"step_id": "network", "label": "分配网络"}}},
            {"id": 3, "batch_id": "all-slots", "batch_index": 3, "status": "failed", "progress": {"failure": {"step_id": "browser", "label": "启动浏览器"}}},
            {"id": 4, "root_job_id": 1, "retry_attempt": 1, "batch_id": "all-slots", "batch_index": 1, "status": "success", "progress": {"outcome": {"status": "success"}}},
        ]
        batch = _latest_progress_batch(rows)
        self.assertEqual(3, batch["total"])
        self.assertEqual([{"step_id": "network", "label": "分配网络", "count": 1}], batch["current_stage_counts"])
        self.assertEqual([{"step_id": "browser", "label": "启动浏览器", "count": 1}], batch["failure_stage_counts"])

    def test_public_gateway_captures_logger_once_with_current_stage(self):
        import logging
        from core.operations import task_gateway
        from core.account_operation_executor import operation_log_context

        def handler(context):
            event = context.report(stage="network", state="success", message="阶段事件")
            with operation_log_context(context):
                logging.getLogger("task-observation-test").warning("普通日志已归属当前阶段")
            return task_gateway.OperationResult.success({"event_id": event["id"]})

        task_type = "test_observation_handler"
        task_gateway.register_operation_handler(task_type, handler)
        try:
            created = operation_task_store.create_runtime_task(task_type=task_type, account_id=4999, email="gateway@example.test", trigger="test")
            task_id, run_id = created["id"], created["run"]["id"]
            task_gateway._execute_operation_handler(task_type, run_id)
            logs = operation_task_store.read_task_run_log(task_id, run_id, cursor=0)["items"]
            ordinary = [line for line in logs if line["message"] == "普通日志已归属当前阶段"]
            self.assertEqual(1, len(ordinary))
            self.assertEqual("network", ordinary[0]["stage"])
            self.assertEqual(task_id, ordinary[0]["task_id"])
            self.assertIsNotNone(ordinary[0].get("event_id"))
        finally:
            task_gateway.unregister_operation_handler(task_type)

    def test_legacy_event_log_correlation_uses_projected_identity(self):
        legacy_id = legacy_task_store.create_task(task_type="plan_check", account_id=4002, email="legacy@example.test", trigger="test")
        legacy_task_store.append_event(legacy_id, stage="plan_check", state="failed", message="查询套餐超时")
        task = operation_task_store.find_task_by_source("account_action_tasks", str(legacy_id))
        task_id, run_id = int(task["id"]), int(task["last_run_id"])
        event = next(event for event in operation_task_store.list_task_events(task_id, run_id=run_id)["items"] if event["event_type"] == "stage.failed")
        line = next(line for line in operation_task_store.read_task_run_log(task_id, run_id, cursor=0)["items"] if line.get("event_uuid") == event["event_uuid"])
        self.assertEqual(event["id"], line["event_id"])
        self.assertEqual("plan_check", line["main_step_id"])

    def test_legacy_lifecycle_events_keep_source_event_identity(self):
        legacy_id = legacy_task_store.create_task(task_type="live_check", account_id=4003, email="legacy-live@example.test", trigger="test")
        legacy_task_store.start_task(legacy_id, message="开始检查")
        legacy_task_store.finish_task(legacy_id, status="success", message="检查完成", result_summary={"ok": True})

        task = operation_task_store.find_task_by_source("account_action_tasks", str(legacy_id))
        task_id, run_id = int(task["id"]), int(task["last_run_id"])
        events = operation_task_store.list_task_events(task_id, run_id=run_id, after_id=0)["items"]
        lifecycle = [
            event for event in events
            if event["event_type"] in {"run.queued", "run.running", "run.success"}
        ]
        self.assertEqual(3, len(lifecycle))
        logs = operation_task_store.read_task_run_log(task_id, run_id, cursor=0)["items"]
        for event in lifecycle:
            self.assertEqual("account_action_events", event["source_system"])
            self.assertIsNotNone(event["source_event_id"])
            line = next(line for line in logs if line.get("event_uuid") == event["event_uuid"])
            self.assertEqual(event["id"], line["event_id"])
            self.assertEqual(event["source_event_id"], line["source_event_id"])
