"""任务中心统一重试 wave 的注册领域适配，规划与事实写入分离。"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from core.operations import task_gateway
from core.registration import service
from core.storage.registration.bulk_retry import RetryAdmission
from core.storage.registration.retry_followups import RetryFollowup


@dataclass
class RetryWave:
    sources: dict[int, int]
    admissions: list[RetryAdmission]
    followups: list[RetryFollowup]
    results: dict[int, dict]


def select_sources(tasks: Mapping[int, Mapping], *, excluded=()) -> dict[int, int]:
    """使用单项动作的相同来源优先级，只选择历史注册执行入口。"""
    from core.operations import action_service

    selected = {}
    for task_id, task in tasks.items():
        if task_id in excluded or task.get("_managed_target_round_id"):
            continue
        if task_gateway.operation_is_deactivated(task) or task.get("status") in action_service.active_operation_statuses:
            continue
        task_type, source_system = str(task.get("task_type") or "").strip(), str(task.get("source_system") or "").strip()
        if task_gateway.operation_action(task_type, "retry", source_system=source_system) is not None:
            continue
        if source_system == "native_operations" and task_type == "codex_retry":
            continue
        source_id = action_service._registration_retry_job_id(task)
        if source_id is not None:
            selected[int(task_id)] = source_id
    return selected


def prepare(sources: Mapping[int, int], *, workers: int = 1, debug_enabled: bool | None = None) -> RetryWave:
    """集合读取身份后只生成冻结计划；不入队或保留账号执行名额。"""
    unique = list(dict.fromkeys(int(value) for value in sources.values()))
    facts = service._prefetch_retry_facts(unique)
    admissions, followups, results = [], [], {}
    options = {} if debug_enabled is None else {"debug_enabled": debug_enabled}
    for source_id in unique:
        result = service.retry_job(
            source_id, workers=workers, _facts=facts[source_id],
            _admissions=admissions, _followups=followups, **options,
        )
        if result is not None:
            results[source_id] = result
    return RetryWave(dict(sources), admissions, followups, results)


def followup_result(spec: RetryFollowup, receipt: Mapping) -> dict:
    return service._followup_retry_result(spec, dict(receipt))


def task_replies(wave: RetryWave, results: Mapping[int, Mapping]) -> dict[int, tuple[dict, int]]:
    output = {}
    for task_id, source_id in wave.sources.items():
        if source_id not in results:
            continue
        payload = dict(results[source_id])
        raw_status = payload.pop("status", None)
        status = raw_status if isinstance(raw_status, int) and not isinstance(raw_status, bool) else (
            409 if payload.get("busy") else 200 if payload.get("ok") else 400
        )
        if isinstance(raw_status, str) and raw_status.isdigit():
            status = int(raw_status)
        output[task_id] = payload, status
    return output


def admit_registration(wave: RetryWave) -> dict[int, dict]:
    """普通注册 Run 使用原集合存储边界；提交后只通知 Worker。"""
    from core.storage.registration.bulk_retry import admit

    pending, results = [], {}
    for plan in wave.admissions:
        if service.is_job_worker_active(plan.source_id):
            results[plan.source_id] = {"ok": False, "error": "原任务仍在收口，暂不能重跑", "status": 409}
        else:
            pending.append(plan)
    outcomes = admit(pending)
    started = []
    for plan in pending:
        outcome = outcomes[plan.source_id]
        if isinstance(outcome, dict):
            results[plan.source_id] = outcome
        else:
            job, created = outcome
            if created:
                started.append(plan)
                results[plan.source_id] = service._created_retry_result(plan.source_id, plan.action, job)
            else:
                results[plan.source_id] = service._reused_retry_result(
                    plan.source_id, plan.action, job, debug_enabled=None,
                )
    if started:
        service.configure_submission_workers(started[-1].workers)
        service.notify_dispatch()
    return results
