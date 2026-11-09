"""仅由独立套餐 handler 使用的有界 AT 恢复编排。"""
from __future__ import annotations

from core.accounts.plans.client import token_claims
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost
from core.operations import run_log
from core.storage import accounts
from core.storage.accounts import plan_refresh


class PlanAtRecovery:
    def __init__(self, context, *, account_id, email, config_snapshot):
        self.context = context
        self.account_id = account_id
        self.email = email
        self.config_snapshot = config_snapshot
        self.summary = {}
        self.budget_seconds = max(30, float(config_snapshot.get("network_timeout_seconds", 900))) + 120

    @staticmethod
    def needs_refresh(token):
        return not str(token or "").strip() or token_claims(token).get("token_expired") is True

    def refresh(self, token, *, reason):
        """先保存额度及新 AT，再让调用方继续套餐请求。"""
        from core.accounts.liveness import service
        self.context.checkpoint()
        self.summary, started = plan_refresh.begin(
            self.account_id, fence=self.context.execution_fence, reason=reason,
            budget_seconds=self.budget_seconds,
        )
        if not started:
            self.summary.setdefault("error", "本次执行已使用自动刷新 AT 额度，请手动重跑")
            return None
        self.context.report(stage="refresh_token", state="running", message="套餐查询发现 AT 不可用，开始自动刷新")
        expected = {"token": token}
        saved_token = {"value": None}

        def write_result(result):
            saved = plan_refresh.save_liveness(
                self.account_id, result, fence=self.context.execution_fence,
                expected_email=self.email, expected_token=expected["token"],
            )
            if saved and result.get("ok") and result.get("access_token"):
                expected["token"] = str(result["access_token"])
                saved_token["value"] = expected["token"]
            return saved

        try:
            queued = service.run_account_live_check_inline(
                account_id=self.account_id, email=self.email, trigger="plan_check_auto_refresh",
                force_refresh=True, allow_missing_token=True, operation_context=self.context,
                config_snapshot=self.config_snapshot, result_writer=write_result,
            )
            result = queued.get("result") or {"ok": False, "error": queued.get("error") or "AT 刷新未执行"}
        except (OperationCancelled, OperationLeaseLost):
            raise
        except Exception as exc:
            result = {"ok": False, "error": f"AT 刷新执行异常：{type(exc).__name__}: {exc}"}
        self.context.checkpoint()
        account = accounts.get_account(self.account_id) or {}
        refreshed = str(account.get("access_token") or "")
        ok = bool(result.get("ok") and saved_token["value"] and refreshed == saved_token["value"]
                  and account.get("email") == self.email
                  and not result.get("reconcile_required"))
        summary = {"attempted": True, "ok": ok, "status": "success" if ok else "failed"}
        cause = service._safe_refresh_cause_code(result)
        if cause:
            summary["cause_code"] = cause
        for key in ("error_code", "cause_code", "auth_diagnostics", "network_recovery", "reconcile_required", "live_check_driver"):
            if key in result:
                summary[key] = run_log.scrub(result[key])
        if not ok:
            summary["error"] = run_log.redact_text(result.get("error") or "AT 刷新未确认保存成功", 1000)
        self.summary = plan_refresh.finish(self.account_id, fence=self.context.execution_fence, summary=summary)
        self.context.report(stage="refresh_token", state="success" if ok else "failed",
                            message="新 AT 已保存，继续查询套餐" if ok else "套餐自动刷新 AT 失败",
                            detail={"auto_refresh_at": self.summary})
        return refreshed if ok else None
