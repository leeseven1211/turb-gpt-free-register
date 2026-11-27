"""P1 改密收尾中间态在原生运行时中的持久化契约。"""
from __future__ import annotations

import uuid

from core.storage import records
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class PasswordChangePendingReceiptTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        operation.reset_ready()
        operation.init()

    def make_run(self):
        email = f"p1-runtime-{uuid.uuid4().hex}@example.test"
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": email,
            "access_token": "fresh-at",
            "extra_json": {
                "account_password": "candidate-password",
                "account_password_state": "confirmed",
            },
        })
        created = operation.create_runtime_task(
            task_type="password_change",
            account_id=account_id,
            email=email,
            source_system="webui_runtime",
            resource_family="openai_interactive",
            data={"steps": ["password"]},
        )
        run_id = int(created["run"]["id"])
        operation.claim_run(run_id, execution_id="p1-worker", worker_pid=101)
        lease_token = operation.acquire_account_lease(
            account_id=account_id,
            run_id=run_id,
            resource_family="openai_interactive",
        )
        fence = {"execution_id": "p1-worker", "lease_token": lease_token}
        operation.record_remote_intent(
            run_id,
            **fence,
            action="account_setup",
            request_id=f"account-setup:{run_id}",
        )
        return run_id, fence

    def pending_summary(self, *, writeback=False):
        return {
            "status": "failed",
            "ok": False,
            "password_reset": "confirmed",
            "password_confirmed": True,
            "remote_password_confirmed": True,
            "completion_pending": True,
            "stage": "business_verification",
            "cause_code": "token_revoked",
            "credentials_saved": writeback,
            "business_verified": False,
        }

    def test_pending_receipt_uses_local_commit_required_and_keeps_failed_cause(self):
        run_id, fence = self.make_run()
        summary = self.pending_summary(writeback=False)

        operation.record_remote_receipt(
            run_id,
            **fence,
            outcome="local_commit_required",
            action="account_setup",
            request_id=f"account-setup:{run_id}",
            detail={
                **summary,
                "remote_result_confirmed": True,
                "local_business_writeback_confirmed": False,
                "local_readback_confirmed": False,
            },
        )
        persisted = operation.get_run(run_id)
        assert persisted["data"]["remote_intent"]["receipt_state"] == "local_commit_required"
        persisted_detail = persisted["data"]["remote_receipt"]["detail"]
        assert persisted_detail["remote_password_confirmed"] is True
        assert persisted_detail["password_reset"] == "confirmed"
        assert persisted_detail["password_confirmed"] is True
        assert persisted_detail["completion_pending"] is True
        assert persisted_detail["credentials_saved"] is False
        assert persisted_detail["business_verified"] is False
        finished = operation.finish_run(
            run_id,
            **fence,
            status="failed",
            message="业务核验失败",
            error="token_revoked",
            result_summary=summary,
        )

        assert finished["status"] == "failed"
        assert finished["result_summary"]["cause_code"] == "token_revoked"
        assert finished["result_summary"]["completion_pending"] is True
        assert finished["result_summary"].get("outcome") != "request_unknown"
        persisted = operation.get_run(run_id)
        assert persisted["status"] == "failed"
        assert persisted["result_summary"]["cause_code"] == "token_revoked"
        assert persisted["result_summary"].get("outcome") != "request_unknown"
        assert persisted["data"]["remote_receipt"]["receipt_state"] == "local_commit_required"

    def test_confirmed_pending_closeout_keeps_failed_cause_after_writeback_readback(self):
        run_id, fence = self.make_run()
        summary = self.pending_summary(writeback=True)

        operation.record_remote_receipt(
            run_id,
            **fence,
            outcome="confirmed",
            action="account_setup",
            request_id=f"account-setup:{run_id}",
            detail={
                **summary,
                "remote_result_confirmed": True,
                "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True,
            },
        )
        persisted = operation.get_run(run_id)
        assert persisted["data"]["remote_intent"]["receipt_state"] == "confirmed"
        persisted_detail = persisted["data"]["remote_receipt"]["detail"]
        assert persisted_detail["remote_password_confirmed"] is True
        assert persisted_detail["password_reset"] == "confirmed"
        assert persisted_detail["password_confirmed"] is True
        assert persisted_detail["completion_pending"] is True
        assert persisted_detail["credentials_saved"] is True
        assert persisted_detail["business_verified"] is False
        finished = operation.finish_run(
            run_id,
            **fence,
            status="failed",
            message="业务核验失败",
            error="token_revoked",
            result_summary=summary,
        )

        assert finished["status"] == "failed"
        assert finished["error_code"] == "token_revoked"
        assert finished["result_summary"]["completion_pending"] is True
        assert finished["result_summary"].get("outcome") != "request_unknown"
        persisted = operation.get_run(run_id)
        assert persisted["status"] == "failed"
        assert persisted["error_code"] == "token_revoked"
        assert persisted["result_summary"].get("outcome") != "request_unknown"

    def test_summary_only_pending_does_not_bypass_unknown_receipt_protection(self):
        run_id, fence = self.make_run()
        summary = self.pending_summary(writeback=False)

        finished = operation.finish_run(
            run_id,
            **fence,
            status="failed",
            message="回执尚未确认",
            error="token_revoked",
            result_summary=summary,
        )

        assert finished["status"] == "attention_required"
        assert finished["result_summary"]["outcome"] == "request_unknown"
        assert finished["result_summary"]["reconcile_required"] is True
