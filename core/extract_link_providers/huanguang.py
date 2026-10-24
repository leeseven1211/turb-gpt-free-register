from __future__ import annotations

import re
import secrets as secure_secrets
import time
from dataclasses import replace
from urllib.parse import urlencode

from core.task_run_log import redact_text

from .contracts import (
    ExtractRequest,
    ProviderError,
    ProviderJob,
    ProviderUnsupported,
    normalize_state,
    request,
    response_dict,
    require_capability,
    safe_links,
    safe_payment_artifact,
)


_EXTRACTION = {"QUEUED": "queued", "RUNNING": "running", "DONE": "failed", "ERROR": "failed", "FAILED": "failed", "CANCELLED": "failed", "CANCELED": "failed"}
_PAYMENT = {
    "AWAITING_PAYMENT": "pending", "ACTIVATION_PENDING": "pending",
    "COMPLETED": "unknown", "FAILED": "failed", "EXPIRED": "failed",
    "PAYMENT_TIMEOUT": "unknown", "PAYMENT_CHECK_ERROR": "unknown",
    "VERIFICATION_UNAVAILABLE": "unknown",
}
_PAYMENT_CHECK_STATUSES = {"running", "completed", "failed", "expired", "timeout", "error"}
_SCAN_STATUSES = {"submitting", "active", "unknown", "completed", "refunded", "rejected", "manual_review"}
_SCAN_ORDER_STATUSES = {"WAITING_ACCEPTANCE", "WAITING_SCAN", "SCANNED_PENDING_CONFIRMATION", "COMPLETED", "FAILED_REFUNDED", "UNKNOWN"}
_XXSYUN_STATUSES = {"submitting", "awaiting_worker", "claimed", "verifying", "completed", "failed", "expired", "cancelled", "rejected", "manual_review", "credentials_required"}
_FALLBACK_STATUSES = {"checking", "submitting", "submitted", "existing", "unavailable", "skipped", "manual_review"}
_CDK_STATES = {"queued", "reserved", "consumed", "free_reserved", "reused", "refunded", "pending", "review", "bypassed"}
_PRE_ACCEPTANCE_REJECTIONS = {400, 402, 403, 413, 429}
_AUTO_RELINK_ACTIVE = {"checking_payment", "starting"}
_AUTO_RELINK_STATUSES = _AUTO_RELINK_ACTIVE | {"started", "submitted", "failed", "skipped", "completed", "unavailable"}
_MAX_CHAIN_JOBS = 20
_MISSING_MATERIAL_MESSAGE = "幻光任务已结束，但未返回有效支付材料"
_CHILD_JOB_ID = re.compile(r"^[a-f0-9]{16}$", re.IGNORECASE)
_URL_RE = re.compile(r"(?i)\b(?:https?|wss?|upi|socks5h?)://[^\s<>\"']+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CREDENTIAL_RE = re.compile(
    r"(?i)\b(cdk|(?:access|refresh)[_ -]?token|token|at|(?:job[_ -]?)?secret|password|authorization|cookie|(?:fallback[_ -]?)?(?:xxsyun[_ -]?)?api[_ -]?key)"
    r"[\"']?\s*[:=：]\s*(?:\"[^\"]*\"|'[^']*'|(?:Bearer\s+)?[^\s,;\"'}]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;\"'}]+")
_CDK_RE = re.compile(r"(?i)\b(?:CDK(?:-[A-Z0-9]{4}){4}|[A-Z]{3}-[A-F0-9]{32})\b")
_GENERIC_FAILURE_MESSAGES = {
    "任务处理失败", "任务失败", "处理失败", "提链失败", "平台提链失败", "请求失败",
    "error", "failed", "task failed", "task processing failed", "unknown error",
}
_FAILURE_TEXT_RE = re.compile(r"失败|错误|异常|无效|不足|已用完|用尽|耗尽|未执行|取消|拒绝|超时|不可用|无法|\b(?:error|failed|invalid|exhausted|insufficient|timeout|denied|cancelled|canceled)\b", re.IGNORECASE)


def _safe_message(value: object, *, secrets: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        return ""
    text = value
    for secret in secrets:
        if isinstance(secret, str) and secret:
            text = text.replace(secret, "[REDACTED]")
    text = _CREDENTIAL_RE.sub(r"\1=[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = redact_text(text, len(text))
    text = _URL_RE.sub("[REDACTED_URL]", text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _CDK_RE.sub("[REDACTED_CDK]", text)
    return " ".join(text.split())[:300]


def _progress_summary(data: dict, *, secrets: tuple[str, ...]) -> dict:
    summary = {}
    for source, target, maximum in (
        ("percent", "percent", 100), ("queue_position", "queue_position", 1000000),
        ("attempt", "step_attempt", 1000000), ("max_attempts", "max_attempts", 1000000),
    ):
        value = data.get(source)
        if type(value) is int and 0 <= value <= maximum:
            summary[target] = value
    text = _safe_message(data.get("text"), secrets=secrets)
    if text:
        summary["current_step"] = text
    cdk_state = data.get("cdk_state")
    if isinstance(cdk_state, str) and cdk_state in _CDK_STATES:
        summary["cdk_state"] = cdk_state
    return summary


def _failure_message(data: dict, result: dict, remote_status: str, *, secrets: tuple[str, ...]) -> str:
    def generic(value: str) -> bool:
        return value.rstrip("。.!！:： ").lower() in _GENERIC_FAILURE_MESSAGES

    messages = [
        (name, _safe_message(source.get(name), secrets=secrets))
        for source in (data, result) for name in ("error", "message", "detail", "text")
    ]
    field, message = next(((name, value) for name, value in messages if value), ("", ""))
    running_message = field != "error" and message.startswith(("正在", "等待", "排队", "准备"))
    # DONE 缺材料的合成失败保留原契约；真实失败终态跳过通用错误和旧运行进度。
    if remote_status not in {"ERROR", "FAILED", "CANCELLED", "CANCELED"} or not (generic(message) or running_message):
        return message
    for name in ("error", "detail", "message", "text"):
        for source in (result, data):
            detail = _safe_message(source.get(name), secrets=secrets)
            if not detail or generic(detail) or (name != "error" and detail.startswith(("正在", "等待", "排队", "准备"))):
                continue
            if name != "text" or _FAILURE_TEXT_RE.search(detail):
                return detail
    return message


class HuanguangProvider:
    provider_id = "huanguang"

    def __init__(self, config, transport):
        self.config, self.transport = config, transport
        self._secrets: dict[str, str] = {}

    def create_job(self, request_data: ExtractRequest) -> ProviderJob:
        require_capability(self.config, "extract")
        if request_data.link_type != "upi":
            raise ProviderError("幻光提链仅支持 UPI")
        entry_proxies = request_data.entry_proxies or ((request_data.entry_proxy,) if request_data.entry_proxy else ())
        exit_proxies = request_data.exit_proxies or ((request_data.exit_proxy,) if request_data.exit_proxy else ())
        if not entry_proxies or not exit_proxies:
            raise ProviderError("幻光提链需要已分配的入口和出口代理")
        if request_data.mode == "auto_payment":
            require_capability(self.config, "payment")
            require_capability(self.config, "auto_payment")
            if not self.config.payment_cdk:
                raise ProviderError("幻光自动扫码缺少支付扫码 CDK")
        body = {
            "token": request_data.access_token,
            "cdk": self.config.cdk,
            "link_type": request_data.link_type,
            "entry_proxies": list(entry_proxies),
            "exit_proxies": list(exit_proxies),
        }
        if "retry_count" in request_data.options:
            count = request_data.options["retry_count"]
            if type(count) is not int or not 1 <= count <= 10:
                raise ProviderError("幻光单任务尝试次数必须是 1 至 10 的整数")
            body["retry_count"] = count
        if request_data.mode == "auto_payment":
            body["scan_provider"] = "chongyun"
            body["chongyun_auto_submit"] = True
            body["chongyun_cdk"] = self.config.payment_cdk
            if self.config.scan_fallback_enabled is True and self.config.xxsyun_api_key.strip():
                body["scan_fallback_enabled"] = True
                body["fallback_xxsyun_api_key"] = self.config.xxsyun_api_key.strip()
        checkpoint = getattr(request_data, "submission_checkpoint", None)
        if callable(checkpoint):
            try:
                remote_config = request(self.transport, "GET", "/api/config", timeout=self.config.timeout)
            except ProviderError:
                remote_config = {}
            if remote_config.get("batch_receipts") is True:
                private = {"batch_receipt_secret": secure_secrets.token_hex(32), "batch_receipt_pending": True}
                # 必须先持久化查询凭据；保存失败时不得发送远端创建请求。
                checkpoint(dict(private))
                batch_body = {key: value for key, value in body.items() if key != "token"}
                batch_body["sessions"] = [request_data.access_token]
                try:
                    status, data = self._response(
                        "POST", "/api/checkout-batch", body=batch_body,
                        headers={"Content-Type": "application/json", "X-Pay153-Batch-Secret": private["batch_receipt_secret"]},
                    )
                    job = self._batch_result(status, data, private, extra_secrets=(request_data.access_token,))
                except ProviderError:
                    job = None
                # 接收不明时只查原提交回执，不重复创建。
                return job if job is not None else self._recover_receipt(private)
        data = request(self.transport, "POST", "/api/checkout", body=body,
                       headers={"Content-Type": "application/json"}, timeout=self.config.timeout)
        return self._queued_job(data, extra_secrets=(request_data.access_token,))

    def _queued_job(self, data, private=None, *, extra_secrets=()):
        job_id = data.get("job_id")
        secret = data.get("job_secret")
        if not isinstance(job_id, (str, int)) or not str(job_id).strip() or not isinstance(secret, str) or not secret:
            return ProviderJob(extraction_state="unknown", summary={"outcome": "UNKNOWN"})
        job_id = str(job_id)
        self._secrets[job_id] = secret
        summary = _progress_summary(data, secrets=(
            self.config.cdk, self.config.payment_cdk, self.config.xxsyun_api_key,
            self.config.xxsyun_api_key.strip(), secret, (private or {}).get("batch_receipt_secret", ""), *extra_secrets,
        ))
        summary.update({"remote_status": "QUEUED", "remote_polling": True})
        details = {**(private or {}), "job_secret": secret}
        if "batch_receipt_pending" in details:
            details["batch_receipt_pending"] = False
            summary["submission_receipt_pending"] = False
        return ProviderJob(job_id=job_id, extraction_state="queued", private_data=details, summary=summary)

    def _response(self, method, path, *, body=None, headers=None):
        """保留回执所需 HTTP 状态，异常不携带远端正文或请求凭据。"""
        try:
            response = self.transport.request(method, path, json=body, headers=headers or {}, timeout=self.config.timeout)
            status = int(getattr(response, "status_code", 200))
            return status, response_dict(response)
        except Exception:
            raise ProviderError("Provider 请求失败") from None

    @staticmethod
    def _pending_receipt(private):
        return ProviderJob(private_data=dict(private), summary={
            "outcome": "UNKNOWN", "submission_receipt_pending": True,
            "remote_polling": True, "automatic_payment_terminal": False,
            "automatic_payment_requires_reconcile": False,
        })

    def _batch_result(self, status, data, private, *, extra_secrets=()):
        rejection = None
        if status in _PRE_ACCEPTANCE_REJECTIONS:
            rejection = data.get("error")
        elif 200 <= status < 300:
            jobs, rejected = data.get("jobs", []), data.get("rejected", [])
            if not isinstance(jobs, list) or not isinstance(rejected, list) or len(jobs) + len(rejected) != 1:
                return None
            row = (jobs or rejected)[0]
            if not isinstance(row, dict) or type(row.get("row")) is not int or row["row"] != 1:
                return None
            if jobs:
                job_id, secret = row.get("job_id"), row.get("job_secret")
                if not isinstance(job_id, str) or not job_id.strip() or not isinstance(secret, str) or not secret:
                    return None
                return self._queued_job(row, private, extra_secrets=extra_secrets)
            rejection = row.get("error")
        else:
            return None
        details = {**private, "batch_receipt_pending": False}
        message = _safe_message(rejection, secrets=(
            self.config.cdk, self.config.payment_cdk, self.config.xxsyun_api_key,
            private.get("batch_receipt_secret", ""), *extra_secrets,
        ))
        return ProviderJob(extraction_state="failed", private_data=details, summary={
            "outcome": "REJECTED", "failure_message": message or "幻光平台已明确拒绝提链请求",
            "submission_receipt_pending": False, "remote_polling": False,
        })

    def _recover_receipt(self, private):
        try:
            status, receipt = self._response("GET", "/api/checkout-batch-receipt", headers={
                "X-Pay153-Batch-Secret": private["batch_receipt_secret"], "Cache-Control": "no-store",
            })
            if 200 <= status < 300 and receipt.get("state") == "complete" and type(receipt.get("status")) is int:
                body = receipt.get("body")
                if isinstance(body, dict):
                    job = self._batch_result(receipt["status"], body, private)
                    if job is not None:
                        return job
        except ProviderError:
            pass
        return self._pending_receipt(private)

    def get_status(self, job_ref: str, *, private_data: dict | None = None) -> ProviderJob:
        original_deadline = getattr(self.transport, "deadline", None)
        had_deadline = hasattr(self.transport, "deadline")
        deadline = time.monotonic() + float(self.config.timeout)
        if isinstance(original_deadline, (int, float)):
            deadline = min(deadline, original_deadline)
        self.transport.deadline = deadline
        try:
            return self._get_status(job_ref, private_data=private_data)
        finally:
            if had_deadline:
                self.transport.deadline = original_deadline
            else:
                del self.transport.deadline

    def _get_status(self, job_ref: str, *, private_data: dict | None = None) -> ProviderJob:
        require_capability(self.config, "extract")
        job_id = str(job_ref)
        if not job_id and isinstance(private_data, dict) and private_data.get("batch_receipt_pending") is True:
            if isinstance(private_data.get("batch_receipt_secret"), str) and private_data["batch_receipt_secret"]:
                return self._recover_receipt(private_data)
        secret = private_data.get("job_secret") if isinstance(private_data, dict) else None
        secret = secret if isinstance(secret, str) and secret else self._secrets.get(job_id)
        if not secret:
            raise ProviderError("幻光任务凭证不可用")
        private = dict(private_data or {})
        private["job_secret"] = secret
        previous_public_state = private.pop("previous_public_state", None)
        chain = private.get("job_chain")
        chain = [dict(node) for node in chain] if isinstance(chain, list) and all(isinstance(node, dict) for node in chain) else []
        if not chain:
            chain = [{"job_id": job_id, "parent_job_id": None}]
            if isinstance(previous_public_state, dict):
                chain[0]["state"] = self._seed_job_snapshot(previous_public_state)
        chain_error = self._chain_error(chain, job_id)
        if chain_error:
            return self._chain_job(job_id, private, chain[:_MAX_CHAIN_JOBS], error=chain_error)

        # 先读最新子单；尚在查询的父单继续独立收敛，不把父单退款继承给子单。
        parent_indices = [
            index for index, node in enumerate(chain[:-1])
            if self._node_job(node).summary.get("remote_polling") is True
        ]
        indices = [len(chain) - 1]
        cursor = private.get("chain_parent_cursor", 0)
        cursor = cursor if type(cursor) is int and cursor >= 0 else 0
        if parent_indices:
            indices.append(parent_indices[cursor % len(parent_indices)])
        discovered = False
        query_failed = False
        remaining_gets = 2
        for index in indices:
            if not remaining_gets:
                break
            if index != indices[0]:
                private["chain_parent_cursor"] = (cursor + 1) % len(parent_indices)
            node = chain[index]
            remaining_gets -= 1
            try:
                data, extra_get = self._get_job_data(node["job_id"], secret, requery=remaining_gets > 0)
            except ProviderError:
                if len(chain) == 1 and not isinstance(node.get("state"), dict):
                    raise
                query_failed = True
                continue
            remaining_gets -= extra_get
            result = data.get("result") if isinstance(data.get("result"), dict) else {}
            child_id = result.get("auto_relink_job_id")
            job = self._job(data, node["job_id"], secret, secrets=(
                self.config.cdk, self.config.payment_cdk, self.config.xxsyun_api_key,
                self.config.xxsyun_api_key.strip(), private.get("batch_receipt_secret", ""),
                *(item["job_id"] for item in chain), child_id if isinstance(child_id, str) else "",
            ))
            previous = self._node_job(node)
            previous_artifact = safe_payment_artifact(previous.payment_artifact)
            retained_material = previous.extraction_state == "succeeded" and self._has_material(previous)
            summary = dict(job.summary)
            if (retained_material and summary.get("remote_status") == "DONE" and job.payment_state != "failed"
                    and summary.get("failure_message") == _MISSING_MATERIAL_MESSAGE):
                # 同单已有材料时，省略材料的完成响应不能再产生“未出链”的合成失败。
                summary.pop("remote_terminal_failure", None)
                summary.pop("failure_message", None)
            job = replace(
                job, extraction_state="succeeded" if retained_material else job.extraction_state,
                links=tuple(dict.fromkeys((*previous.links, *job.links))),
                payment_links=tuple(dict.fromkeys((*previous.payment_links, *job.payment_links))),
                payment_artifact={**previous_artifact, **job.payment_artifact}, summary=summary,
            )
            node["state"] = self._job_snapshot(job)
            if child_id in (None, ""):
                continue
            if not isinstance(child_id, str) or not _CHILD_JOB_ID.fullmatch(child_id):
                chain_error = "invalid_child_id"
                break
            existing = next((position for position, item in enumerate(chain) if item["job_id"] == child_id), None)
            if existing is not None:
                if existing != index + 1 or chain[existing].get("parent_job_id") != node["job_id"]:
                    chain_error = "cycle"
                    break
                continue
            if len(chain) >= _MAX_CHAIN_JOBS:
                chain_error = "chain_limit"
                break
            if index != len(chain) - 1:
                chain_error = "invalid_chain"
                break
            if not discovered:
                chain.append({"job_id": child_id, "parent_job_id": node["job_id"], "state": {
                    "extraction_state": "queued", "payment_state": "not_started",
                    "summary": {"remote_status": "QUEUED", "remote_polling": True},
                }})
                discovered = True
        return self._chain_job(job_id, private, chain, error=chain_error, query_failed=query_failed)

    @staticmethod
    def _chain_error(chain, root_id):
        if len(chain) > _MAX_CHAIN_JOBS:
            return "chain_limit"
        seen = set()
        for index, node in enumerate(chain):
            job_id = node.get("job_id")
            if not isinstance(job_id, str) or not job_id or (index == 0 and job_id != root_id):
                return "invalid_chain"
            if index and not _CHILD_JOB_ID.fullmatch(job_id):
                return "invalid_child_id"
            if job_id in seen:
                return "cycle"
            if index and node.get("parent_job_id") != chain[index - 1]["job_id"]:
                return "invalid_chain"
            seen.add(job_id)
        return ""

    @staticmethod
    def _job_snapshot(job):
        return {
            "extraction_state": job.extraction_state, "payment_state": job.payment_state,
            "links": list(job.links), "payment_links": list(job.payment_links),
            "payment_artifact": dict(job.payment_artifact), "summary": dict(job.summary),
        }

    @classmethod
    def _seed_job_snapshot(cls, value):
        """旧单首查只恢复公开材料与规范状态，不保存任意响应字段。"""
        extraction = value.get("extraction_state")
        payment = value.get("payment_state")
        extraction = extraction if isinstance(extraction, str) and extraction in {
            "queued", "running", "succeeded", "failed", "pending", "unknown", "not_started",
        } else "unknown"
        payment = payment if isinstance(payment, str) and payment in {
            "not_started", "pending", "succeeded", "failed", "unknown",
        } else "not_started"
        raw_summary = value.get("summary") if isinstance(value.get("summary"), dict) else {}
        summary = {}
        for key in ("remote_polling", "automatic_payment_terminal", "automatic_payment_requires_reconcile",
                    "entitlement_active", "entitlement_inferred", "xxsyun_polling", "scan_fallback_polling"):
            if type(raw_summary.get(key)) is bool:
                summary[key] = raw_summary[key]
        for key, allowed in {
            "remote_status": set(_EXTRACTION) | {"UNKNOWN"},
            "platform_plus_status": {"verified", "inferred", "unknown"},
            "payment_check_status": _PAYMENT_CHECK_STATUSES,
            "auto_relink_status": _AUTO_RELINK_STATUSES,
            "xxsyun_status": _XXSYUN_STATUSES,
            "scan_fallback_status": _FALLBACK_STATUSES,
            "scan_fallback_provider": {"xxsyun", "chongyun", "seashore"},
            "automatic_payment_status": _SCAN_ORDER_STATUSES | {status.upper() for status in _SCAN_STATUSES}
                | {"XXSYUN_" + status.upper() for status in _XXSYUN_STATUSES}
                | {"SCAN_FALLBACK_" + status.upper() for status in _FALLBACK_STATUSES | {"pending"}},
        }.items():
            item = raw_summary.get(key)
            if isinstance(item, str) and item in allowed:
                summary[key] = item
        links = value.get("links")
        payment_links = value.get("payment_links")
        return cls._job_snapshot(ProviderJob(
            extraction_state=extraction, payment_state=payment,
            links=safe_links(*links) if isinstance(links, (list, tuple)) else (),
            payment_links=safe_links(*payment_links) if isinstance(payment_links, (list, tuple)) else (),
            payment_artifact=safe_payment_artifact(value.get("payment_artifact")), summary=summary,
        ))

    @staticmethod
    def _has_material(job):
        artifact = safe_payment_artifact(job.payment_artifact)
        return bool(safe_links(*job.links, *job.payment_links) or any(artifact.get(key) for key in (
            "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
        )))

    @staticmethod
    def _node_job(node):
        state = node.get("state") if isinstance(node.get("state"), dict) else {}
        links = state.get("links")
        payment_links = state.get("payment_links")
        return ProviderJob(
            job_id=node.get("job_id"),
            extraction_state=state.get("extraction_state", "unknown"),
            payment_state=state.get("payment_state", "not_started"),
            links=tuple(links) if isinstance(links, (list, tuple)) else (),
            payment_links=tuple(payment_links) if isinstance(payment_links, (list, tuple)) else (),
            payment_artifact=safe_payment_artifact(state.get("payment_artifact")),
            summary=dict(state["summary"]) if isinstance(state.get("summary"), dict) else {},
        )

    def _chain_job(self, root_id, private, chain, *, error="", query_failed=False):
        states = [self._node_job(node) for node in chain]
        leaf = states[-1] if states else ProviderJob()
        verified = next((state for state in states if state.payment_state == "succeeded"
                         and state.summary.get("platform_plus_status") == "verified"), None)
        selected = verified or leaf
        polling = query_failed or any(state.summary.get("remote_polling") is True for state in states)
        payment = selected.payment_state
        if verified is None and len(states) > 1:
            if any(state.payment_state == "unknown" for state in states):
                payment = "unknown"
            elif polling and any(state.payment_state in {"not_started", "pending"} for state in states):
                payment = "pending"
            elif all(state.payment_state == "failed" for state in states):
                payment = "failed"
            elif not polling and any(state.payment_state == "pending" for state in states):
                payment = "unknown"
        summary = {
            **selected.summary, "remote_chain_length": len(chain),
            "extraction_ever_succeeded": any(state.extraction_state == "succeeded" and self._has_material(state) for state in states),
        }
        for key in ("auto_relink_status", "auto_relink_attempt"):
            value = next((state.summary[key] for state in reversed(states) if key in state.summary), None)
            if value is not None:
                summary[key] = value
        if error:
            summary["remote_chain_error"] = error
            polling = False
            if verified is None:
                payment = "unknown"
        summary.update({
            "remote_polling": polling, "automatic_payment_terminal": not polling,
            "automatic_payment_requires_reconcile": not polling and payment in {"pending", "unknown"},
        })
        details = {**private, "root_job_id": root_id, "active_job_id": chain[-1]["job_id"] if chain else root_id,
                   "material_job_id": selected.job_id or root_id,
                   "job_chain": chain}
        return replace(selected, job_id=root_id, payment_state=payment, private_data=details, summary=summary)

    def _get_job_data(self, job_id, secret, *, requery=True):
        headers = {"X-Pay153-Job-Secret": secret}
        path = "/api/checkout-progress?" + urlencode({"job_id": job_id})
        data = request(self.transport, "GET", path, headers=headers, timeout=self.config.timeout)
        extra_get = 0
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        if result.get("xxsyun_status") == "credentials_required" and self.config.xxsyun_api_key.strip():
            try:
                resumed = request(self.transport, "POST", "/api/xxsyun-resume",
                                  headers={**headers, "Content-Type": "application/json"},
                                  body={"job_id": job_id, "api_key": self.config.xxsyun_api_key.strip()},
                                  timeout=self.config.timeout)
            except ProviderError:
                pass
            else:
                # 恢复只查询同一订单；本次最多补查一次，失败时保留已收到的进度。
                resumed_result = resumed.get("result") if isinstance(resumed.get("result"), dict) else resumed
                data = {**data, "result": {**result, **resumed_result}}
                if requery:
                    extra_get = 1
                    try:
                        data = request(self.transport, "GET", path, headers=headers, timeout=self.config.timeout)
                    except ProviderError:
                        pass
        return data, extra_get

    def start_payment(self, job_ref: str, options: dict) -> ProviderJob:
        require_capability(self.config, "payment")
        raise ProviderUnsupported()

    @staticmethod
    def _job(data, fallback_id, secret, *, secrets=()):
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        secrets = (*secrets, secret)
        raw_status = data.get("status")
        remote_status = raw_status.strip().upper() if isinstance(raw_status, str) else "UNKNOWN"
        remote_status = remote_status if remote_status in _EXTRACTION else "UNKNOWN"
        status = normalize_state(remote_status, _EXTRACTION)
        links = safe_links(result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url"), result.get("qr_data"))
        payment_links = safe_links(result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url"))
        artifact = safe_payment_artifact({
            "payment_page_url": next(iter(payment_links), None),
            "payment_url": next(iter(safe_links(result.get("payment_url"), result.get("hosted_instructions_url"))), None),
            "qr_data": result.get("qr_data"),
            "amount": result.get("amount"), "currency": result.get("currency"),
            "expires_at": result.get("expires_at"),
        })
        for target, sources in (
            ("qr_image_url_png", ("qr_image_png", "image_url_png", "qr_image_url_png")),
            ("qr_image_url_svg", ("qr_image_svg", "image_url_svg", "qr_image_url_svg")),
        ):
            for source in sources:
                image = safe_payment_artifact({target: result.get(source)})
                if image:
                    artifact.update(image)
                    break
        if any(artifact.get(name) for name in (
            "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
        )):
            status = "succeeded"

        summary = _progress_summary(data, secrets=secrets)
        summary["remote_status"] = remote_status
        payment_status = result.get("payment_status")
        payment_status = payment_status.strip().lower() if isinstance(payment_status, str) else ""
        payment_state = normalize_state(payment_status, _PAYMENT) if payment_status else "not_started"
        if payment_status.upper() in _PAYMENT:
            summary["payment_status"] = payment_status
            artifact["payment_status"] = payment_status
        for name in ("entitlement_active", "entitlement_inferred"):
            if type(result.get(name)) is bool:
                summary[name] = result[name]
        directly_verified = (
            payment_status == "completed" and result.get("entitlement_active") is True
            and result.get("plan_type") == "plus" and result.get("has_active_subscription") is True
            and ("entitlement_inferred" not in result or result["entitlement_inferred"] is False)
        )
        if directly_verified:
            payment_state = "succeeded"
            summary["platform_plus_status"] = artifact["platform_plus_status"] = "verified"
        elif result.get("entitlement_inferred") is True:
            if payment_state != "failed":
                payment_state = "unknown"
            summary["platform_plus_status"] = artifact["platform_plus_status"] = "inferred"
        elif payment_status == "completed":
            summary["platform_plus_status"] = artifact["platform_plus_status"] = "unknown"
        check_status = result.get("payment_check_status")
        if isinstance(check_status, str) and check_status in _PAYMENT_CHECK_STATUSES:
            summary["payment_check_status"] = check_status
        relink_status = result.get("auto_relink_status")
        relink_status = relink_status if isinstance(relink_status, str) else ""
        if relink_status in _AUTO_RELINK_STATUSES:
            summary["auto_relink_status"] = relink_status
        relink_attempt = result.get("auto_relink_attempt")
        if type(relink_attempt) is int and 0 <= relink_attempt <= 1000000:
            summary["auto_relink_attempt"] = relink_attempt
        summary["remote_polling"] = (
            remote_status in {"QUEUED", "RUNNING"}
            or any(result.get(name) is True for name in ("chongyun_polling", "xxsyun_polling", "seashore_polling", "scan_fallback_polling"))
            or (check_status == "running" and remote_status not in {"CANCELLED", "CANCELED"})
            or relink_status in _AUTO_RELINK_ACTIVE
        )
        scan_status = result.get("chongyun_status")
        scan_status = scan_status.strip().lower() if isinstance(scan_status, str) else ""
        scan_status = scan_status if scan_status in _SCAN_STATUSES else ""
        order_status = result.get("chongyun_order_status")
        order_status = order_status.strip().upper() if isinstance(order_status, str) else ""
        order_status = order_status if order_status in _SCAN_ORDER_STATUSES else ""
        xxsyun_status = result.get("xxsyun_status")
        xxsyun_status = xxsyun_status.strip().lower() if isinstance(xxsyun_status, str) else ""
        xxsyun_status = xxsyun_status if xxsyun_status in _XXSYUN_STATUSES else ""
        fallback_status = result.get("scan_fallback_status")
        fallback_status = fallback_status.strip().lower() if isinstance(fallback_status, str) else ""
        fallback_status = fallback_status if fallback_status in _FALLBACK_STATUSES else ""
        if xxsyun_status:
            summary["xxsyun_status"] = xxsyun_status
        if fallback_status:
            summary["scan_fallback_status"] = fallback_status
        fallback_provider = result.get("scan_fallback_provider")
        if isinstance(fallback_provider, str) and fallback_provider in {"xxsyun", "seashore"}:
            summary["scan_fallback_provider"] = fallback_provider
        for name in ("xxsyun_polling", "scan_fallback_polling"):
            if type(result.get(name)) is bool:
                summary[name] = result[name]
        fallback_active = (
            bool(xxsyun_status) or fallback_status in {"checking", "submitting", "submitted", "existing", "manual_review"}
            or result.get("xxsyun_polling") is True or result.get("scan_fallback_polling") is True
        )
        if fallback_active:
            summary["automatic_payment_status"] = (
                "XXSYUN_" + xxsyun_status.upper() if xxsyun_status
                else "SCAN_FALLBACK_" + (fallback_status.upper() or "PENDING")
            )
            if not directly_verified and payment_state != "failed":
                if xxsyun_status in {"failed", "expired", "cancelled", "rejected"}:
                    payment_state = "failed"
                elif xxsyun_status in {"completed", "manual_review", "credentials_required"} or fallback_status == "manual_review":
                    payment_state = "unknown"
                elif payment_state == "not_started":
                    payment_state = "pending"
                if not summary["remote_polling"] and payment_state == "pending":
                    payment_state = "unknown"
        elif scan_status or order_status:
            summary["automatic_payment_status"] = order_status or scan_status.upper()
            if not directly_verified:
                if scan_status in {"refunded", "rejected"} or order_status == "FAILED_REFUNDED":
                    payment_state = "failed"
                elif payment_state != "failed" and (
                    scan_status in {"unknown", "manual_review", "completed"} or order_status in {"UNKNOWN", "COMPLETED"}
                ):
                    payment_state = "unknown"
                elif payment_state == "not_started":
                    payment_state = "pending"
                if not summary["remote_polling"] and payment_state in {"pending", "not_started"}:
                    payment_state = "unknown"
        # 平台扫码结束不等于 Plus 到账；后台仍在查询时保留持续监控。
        summary["automatic_payment_terminal"] = not summary["remote_polling"]
        summary["automatic_payment_requires_reconcile"] = (
            not summary["remote_polling"] and payment_state in {"pending", "unknown"}
        )
        if status == "failed":
            summary["remote_terminal_failure"] = True
            message = _failure_message(data, result, remote_status, secrets=secrets)
            summary["failure_message"] = message or _MISSING_MATERIAL_MESSAGE
        return ProviderJob(
            job_id=str(data.get("id") or fallback_id),
            extraction_state=status,
            payment_state=payment_state,
            links=links,
            payment_links=payment_links,
            payment_artifact=artifact,
            private_data={"job_secret": secret},
            summary=summary,
        )
