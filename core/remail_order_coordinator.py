# -*- coding: utf-8 -*-
"""Remail 订单协调器：持久意图、唯一 POST 和原订单恢复。"""
from __future__ import annotations

import hashlib
import time
import uuid
from urllib.parse import quote

from core import remail_client
from core.remail_client import RemailAccount, RemailError, RemailOrderUncertain
from core.storage import remail_orders


class RemailOrderCoordinator:
    """把供应商协议与本地可恢复的领取意图连接起来。"""

    def __init__(self, client=remail_client, store=remail_orders):
        self.client = client
        self.store = store

    def _config(self, project_id=None, email_suffix=None, service_mode=None, supply_policy=None):
        self.client.validate_configuration()
        return {
            "project_id": int(project_id if project_id is not None else self.client._project_id()),
            "email_suffix": str(email_suffix if email_suffix is not None else self.client._email_suffix()),
            "service_mode": str(service_mode if service_mode is not None else self.client._service_mode()),
            "supply_policy": str(supply_policy if supply_policy is not None else self.client._supply_policy()),
        }

    def _supplier_ref(self) -> str:
        # 只保存“同一供应商连接”的不可逆引用；API Key 不进入订单行。
        import config.email as cfg
        base = str(getattr(cfg, "REMAIL_API_BASE", "") or "").strip().lower()
        key = str(getattr(cfg, "REMAIL_API_KEY", "") or "")
        return hashlib.sha256(f"{base}\0{key}".encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _account_from_private(data: dict) -> RemailAccount | None:
        email = str(data.get("email") or "").strip()
        token = str(data.get("service_token") or "").strip()
        order_no = str(data.get("order_no") or "").strip()
        if not email or "@" not in email or not token or not order_no:
            return None
        return RemailAccount(email=email, service_token=token, order_no=order_no,
                             project_id=int(data.get("project_id") or 0),
                             email_suffix=str(data.get("email_suffix") or ""),
                             acquisition_id=str(data.get("acquisition_id") or ""))

    def _account_from_intent(self, intent: dict) -> RemailAccount | None:
        return self._account_from_private(intent.get("private_json") or {})

    def prepare(self, *, owner_kind: str, owner_id: str | int, acquisition_id: str | None = None,
                project_id=None, email_suffix=None, service_mode=None, supply_policy=None) -> dict:
        cfg = self._config(project_id, email_suffix, service_mode, supply_policy)
        aid = str(acquisition_id or "").strip()
        if not aid:
            raise ValueError("Remail 领取意图缺少稳定 acquisition_id，已停止下单")
        # 该 key 在意图内固定；Idempotency-Key 不是未知 POST 的重放授权，只是原请求事实。
        idem = f"turb-remail-{aid}"
        return self.store.create_intent(
            acquisition_id=aid, owner_kind=str(owner_kind), owner_id=str(owner_id),
            supplier_identity_ref=self._supplier_ref(), idempotency_key=idem,
            request_json={"project_id": cfg["project_id"], "email_suffix": cfg["email_suffix"],
                          "service_mode": cfg["service_mode"], "supply_policy": cfg["supply_policy"]}, **cfg,
        )

    def acquire(self, *, owner_kind: str, owner_id: str | int, acquisition_id: str | None = None,
                project_id=None, email_suffix=None, service_mode=None, supply_policy=None) -> RemailAccount:
        # 进程重启后先读已有私有交付凭据。已确认交付不需要重新校验当前
        # 供应商配置，也不应因为 API Key 暂时不可用而退回按邮箱猜测订单。
        aid = str(acquisition_id or "").strip()
        if aid:
            existing = self.store.get_intent(aid, private=True)
            if isinstance(existing, dict) and existing:
                if (
                    str(existing.get("owner_kind") or "") != str(owner_kind)
                    or str(existing.get("owner_id") or "") != str(owner_id)
                ):
                    raise RemailError("Remail 领取意图 owner 与当前任务不匹配，已停止恢复", operation_phase="reconcile", cause_code="remail_owner_mismatch")
                account = self._account_from_intent(existing)
                if account:
                    self._cache(account)
                    return account
        intent = self.prepare(owner_kind=owner_kind, owner_id=owner_id, acquisition_id=acquisition_id,
                              project_id=project_id, email_suffix=email_suffix, service_mode=service_mode,
                              supply_policy=supply_policy)
        account = self._account_from_intent(intent)
        if account:
            self._cache(account)
            return account

        status = str(intent.get("status") or "prepared")
        if status in {"submitting", "request_unknown", "read_blocked", "order_created"}:
            if intent.get("order_no"):
                return self.verify_original_order(intent["acquisition_id"])
            raise RemailOrderUncertain(
                "Remail 原订单提交结果待核验，请先核对原订单，禁止重复下单",
                cause_code="remail_submission_in_progress" if status == "submitting" else "remail_order_request_unknown",
                operation_phase="reconcile",
            )

        token = uuid.uuid4().hex
        claimed = self.store.claim_submitting(intent["acquisition_id"], token)
        if not claimed:
            latest = self.store.get_intent(intent["acquisition_id"], private=True) or intent
            if latest.get("order_no"):
                return self.verify_original_order(latest["acquisition_id"])
            raise RemailOrderUncertain("Remail 领取意图已被其他执行接管，请先核对原订单，禁止重试下单", operation_phase="reconcile", cause_code="remail_submission_claim_lost")

        request = claimed.get("request_json") or {}
        started = time.monotonic()
        try:
            payload = self.client._request(
                "POST", "/v1/open/orders",
                params={"serviceMode": request["service_mode"], "supply": request["supply_policy"]},
                json_body={"projectId": int(request["project_id"]), "emailSuffix": request["email_suffix"]},
                headers={"Idempotency-Key": claimed["idempotency_key"]},
            )
            order = self.client._unwrap_order(payload)
        except RemailError as exc:
            details = exc.safe_details()
            self.store.mark_status(claimed["acquisition_id"], "request_unknown" if exc.request_unknown else "rejected",
                                   safe_details=details, expected_statuses=("submitting",), execution_token=token)
            raise
        except Exception as exc:
            details = {"unknown_scope": "mailbox_order", "operation_phase": "post", "cause_code": "remail_post_parse_error", "http_status": None, "allowed_error": None, "missing_fields": [], "elapsed_ms": max(0, int((time.monotonic()-started)*1000)), "order_known": False}
            self.store.mark_status(claimed["acquisition_id"], "request_unknown", safe_details=details,
                                   expected_statuses=("submitting",), execution_token=token)
            raise RemailOrderUncertain("Remail 下单响应无法安全解析，结果不明；请先核对原订单，勿重复下单", elapsed_ms=details["elapsed_ms"]) from None

        order_no = str(self.client._first_value(order, "orderNo", "order_no") or "").strip()
        if order_no:
            persisted = self.store.mark_status(
                claimed["acquisition_id"], "order_created", order_no=order_no,
                expected_statuses=("submitting",), execution_token=token,
            )
            if not persisted:
                latest = self.store.get_intent(claimed["acquisition_id"], private=True) or {}
                stored_order = str(latest.get("order_no") or "").strip()
                stored_account = self._account_from_intent(latest)
                if str(latest.get("status") or "") == "delivered" and stored_order == order_no and stored_account:
                    self._cache(stored_account)
                    return stored_account
                raise RemailOrderUncertain(
                    "Remail 订单号已创建但本地状态竞争失败，请核验原订单，禁止重复下单",
                    operation_phase="persist",
                    cause_code="remail_order_persist_conflict",
                    order_known=True,
                )
            intent_for_completion = persisted
            if not intent_for_completion.get("order_no"):
                intent_for_completion = {**claimed, "order_no": order_no, "status": "order_created"}
            # 订单号已经持久化；凭据未随 POST 返回时，只复用原订单做有界 GET 轮询。
            if not self.client._order_credentials(order):
                email, service_token, polled_order_no = self.client._wait_for_order_credentials(order)
                order = {
                    **order,
                    "deliveryEmail": email,
                    "serviceToken": service_token,
                    "orderNo": polled_order_no or order_no,
                }
            # POST 响应属于本次已提交的原请求，供应商可能只返回订单号和凭据；
            # 后续 GET 恢复则必须经过严格的项目/模式关联校验。
            return self._complete_from_order(
                intent_for_completion, order, execution_token=token, require_identity=False,
            )
        else:
            details = {"unknown_scope": "mailbox_order", "operation_phase": "post", "cause_code": "remail_missing_order_no", "http_status": None, "allowed_error": None, "missing_fields": ["order_no"], "elapsed_ms": max(0, int((time.monotonic()-started)*1000)), "order_known": False}
            self.store.mark_status(claimed["acquisition_id"], "request_unknown", safe_details=details,
                                   expected_statuses=("submitting",), execution_token=token)
            raise RemailOrderUncertain("Remail 下单响应缺少订单号，结果不明；请先核对原订单，勿重复下单", missing_fields=("order_no",), elapsed_ms=details["elapsed_ms"]) from None
    def _cache(self, account: RemailAccount) -> None:
        self.client._cache_context(account)

    def _complete_from_order(self, intent: dict, order: dict, *, execution_token: str | None = None,
                             safe_details: dict | None = None, require_identity: bool = True) -> RemailAccount:
        target = intent.get("request_json") or {}
        raw_project = self.client._first_value(order, "projectId", "project_id")
        if require_identity and raw_project is None:
            raise RemailError(
                "原订单缺少项目关联字段，已停止交付",
                operation_phase="get", cause_code="remail_order_project_missing",
                missing_fields=("project_id",), order_known=True,
            )
        try:
            project_mismatch = raw_project is not None and int(raw_project) != int(target.get("project_id"))
        except (TypeError, ValueError):
            project_mismatch = True
        if project_mismatch:
            raise RemailError("Remail 原订单项目与领取意图不匹配", operation_phase="get", cause_code="remail_order_project_mismatch", order_known=True)
        mode = self.client._first_value(order, "serviceMode", "service_mode")
        if require_identity and mode is None:
            raise RemailError(
                "原订单缺少服务模式关联字段，已停止交付",
                operation_phase="get", cause_code="remail_order_mode_missing",
                missing_fields=("service_mode",), order_known=True,
            )
        if mode is not None and str(mode).strip().lower() != str(target.get("service_mode")).strip().lower():
            raise RemailError("Remail 原订单服务模式与领取意图不匹配", operation_phase="get", cause_code="remail_order_mode_mismatch", order_known=True)
        email, service_token, order_no = self.client._order_credentials(order) or ("", "", "")
        if not email or not service_token or not order_no:
            raise RemailOrderUncertain("Remail 订单号已保存，但取件凭证尚未到达；请核验原订单，勿重复下单", operation_phase="get", cause_code="remail_order_credentials_pending", order_known=True, missing_fields=("delivery_email", "service_token"))
        expected_order_no = str(intent.get("order_no") or "").strip()
        if expected_order_no and order_no != expected_order_no:
            raise RemailError(
                "供应商返回的订单与原订单不匹配，已停止交付",
                operation_phase="get",
                cause_code="remail_order_number_mismatch",
                order_known=True,
            )
        account = RemailAccount(email=email, service_token=service_token, order_no=order_no,
                                project_id=int(target.get("project_id") or 0), email_suffix=str(target.get("email_suffix") or ""),
                                acquisition_id=str(intent.get("acquisition_id") or ""))
        private = {"email": email, "service_token": service_token, "order_no": order_no,
                   "project_id": account.project_id, "email_suffix": account.email_suffix,
                   "acquisition_id": str(intent.get("acquisition_id") or "")}
        done = self.store.mark_status(
            intent["acquisition_id"], "delivered", order_no=order_no,
            private_json=private, safe_details=safe_details,
            expected_statuses=("order_created", "submitting", "request_unknown", "read_blocked"),
            execution_token=execution_token,
        )
        persisted = done or self.store.get_intent(intent["acquisition_id"], private=True) or {}
        stored_order = str(persisted.get("order_no") or "").strip()
        stored_account = self._account_from_intent(persisted)
        if (
            str(persisted.get("status") or "") != "delivered"
            or stored_order != order_no
            or stored_account is None
        ):
            raise RemailOrderUncertain(
                "Remail 凭据已取得但本地交付状态未确认，请核验原订单，禁止重复下单",
                operation_phase="persist",
                cause_code="remail_delivery_persist_conflict",
                order_known=True,
            )
        self._cache(stored_account)
        return stored_account

    def verify_original_order(self, acquisition_id: str) -> RemailAccount:
        intent = self.store.get_intent(str(acquisition_id), private=True)
        if not intent:
            raise RemailError("找不到原 Remail 领取意图", operation_phase="reconcile", cause_code="remail_intent_not_found")
        if str(intent.get("supplier_identity_ref") or "") != self._supplier_ref():
            raise RemailError("原订单供应商身份与当前配置不匹配，已停止核验", operation_phase="reconcile", cause_code="remail_supplier_mismatch")
        order_no = str(intent.get("order_no") or "").strip()
        if not order_no:
            raise RemailOrderUncertain("原意图没有订单号，无法安全核验；禁止自动重购", operation_phase="reconcile", cause_code="legacy_missing_correlation")
        try:
            order = self.client._unwrap_order(self.client._request("GET", f"/v1/open/orders/{quote(order_no, safe='')}"))
            returned_order_no = str(self.client._first_value(order, "orderNo", "order_no") or "").strip()
            if returned_order_no and returned_order_no != order_no:
                raise RemailError(
                    "供应商返回的订单与原订单不匹配，已停止核验",
                    operation_phase="get",
                    cause_code="remail_order_number_mismatch",
                    order_known=True,
                )
            target = intent.get("request_json") or {}
            raw_project = self.client._first_value(order, "projectId", "project_id")
            supply = self.client._first_value(order, "supply", "supplyPolicy", "supply_policy")
            if supply is not None and str(supply).strip().lower() != str(target.get("supply_policy") or "").strip().lower():
                raise RemailError("原订单供货策略与领取意图不匹配", operation_phase="get", cause_code="remail_order_supply_mismatch", order_known=True)
            return self._complete_from_order(
                intent,
                order,
                safe_details={"cause_code": "remail_order_verified", "operation_phase": "get", "order_known": True},
            )
        except RemailError as exc:
            details = exc.safe_details()
            status = "read_blocked" if exc.error_code == "remail_order_read_blocked" else ("request_unknown" if exc.request_unknown else "read_blocked")
            # 已交付是本地已私有保存凭据后的终态；一次失败的重复核验不能
            # 把它降级成 read_blocked，也不能覆盖原交付事实。
            self.store.mark_status(
                str(acquisition_id), status, safe_details=details,
                expected_statuses=("submitting", "request_unknown", "read_blocked", "order_created"),
            )
            raise


__all__ = ["RemailOrderCoordinator", "acquire_order", "verify_original_order"]


def acquire_order(**kwargs) -> RemailAccount:
    """显式 owner 入口，供注册/换绑/CLI 共享。"""
    return RemailOrderCoordinator().acquire(**kwargs)


def verify_original_order(acquisition_id: str) -> RemailAccount:
    return RemailOrderCoordinator().verify_original_order(acquisition_id)
