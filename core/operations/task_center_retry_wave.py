"""任务中心直接重试统一预检，按用户选择顺序集合受理账号资源。"""
from __future__ import annotations

from psycopg.errors import SerializationFailure

from core.operations import task_center_legacy_retry as legacy
from core.operations import task_center_retry as native
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import bulk_retry_tasks, store


def _busy(winner=None):
    return {"accepted": False, "busy": True, "error": "该账号已有排队或运行中的账号操作",
        **({key: winner.get(key) for key in ("task_id", "run_id")} if winner else {}),
        **({"status": winner.get("state") or (winner.get("status") if isinstance(winner.get("status"), str)
            else "queued")} if winner else {})}


def accept_retries(tasks, *, excluded=(), request_key=None, operation_logger=None, include_native=True):
    """所有资格先完成，再按真实账号和资源族挑选本波首个有效候选。"""
    from core.operations import action_service
    from core.operations import task_center_legacy_codex_refresh as refresh
    from core.registration import retry_wave as registration_wave
    from core.storage.registration import retry_followups

    if request_key and len(request_key) > 128:
        return {}
    logger = operation_logger or action_service.action_logger
    selected_registration = registration_wave.select_sources(tasks, excluded=excluded)
    try:
        registration = registration_wave.prepare(selected_registration)
    except Exception:
        logger.exception("任务中心注册重试集合规划失败")
        registration = registration_wave.RetryWave(selected_registration, [], [], {})
        registration.results.update({source_id: {"ok": False, "status": 503,
            "error": "原注册任务入队失败，请刷新任务状态后重试"} for source_id in selected_registration.values()})
    selected_native = native.select_retries(tasks, excluded=excluded) if include_native else {}
    selected_legacy = legacy.select_retries(tasks, excluded=set(excluded) | set(selected_native))
    # 普通原生波次沿用既有 SKIP LOCKED 资格和最低事务开销。
    if not selected_legacy and not registration.followups:
        replies = native.accept_retries(tasks, excluded=excluded, request_key=request_key,
            operation_logger=operation_logger) if include_native else {}
        return _finish_registration(registration, replies, logger)
    selected = set(selected_native) | set(selected_legacy) | set(selected_registration)
    for attempt in range(3):
        try:
            with store._connect() as conn:
                sources = legacy.read_sources(conn, selected_legacy)
                refresh_sources = {task_id: row for task_id, row in sources.items()
                    if row and row["task_type"] == "codex_token_refresh"}
                account_ids = {int(task.get("account_id") or 0) for task, _ in selected_native.values()}
                account_ids.update(int(row.get("account_id") or 0) for row in sources.values() if row)
                account_ids.update(refresh.resolve_account_ids(conn, refresh_sources) if refresh_sources else ())
                account_ids.update(int(plan.account["id"]) for plan in registration.followups)
                # 所有父上下文锁必须先于账号和子 Task 锁。
                registration_contexts = retry_followups.resolve_followup_context_task_ids(conn, registration.followups)
                parent_versions = bulk_retry_tasks.lock_retry_parents_many(conn, selected_native,
                    additional_parent_task_ids=registration_contexts)
                retry_followups.prelock_followup_sources(conn, registration.followups)
                with conn.cursor() as cur:
                    cur.execute(f"""SELECT * FROM {records._qualified(records.ACCOUNTS)}
                        WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED""", (sorted(account_ids - {0}),))
                    accounts = {int(row["id"]): records.merge_row(records.ACCOUNTS, row) for row in cur.fetchall()}
                    unlocked = account_ids - {0} - accounts.keys()
                    if unlocked:
                        cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=ANY(%s)",
                            (sorted(unlocked),))
                        if cur.fetchone():
                            # 旧单项可能先持账号再收口父 Run；不能持父锁等待账号。
                            # 整波退出并释放父锁后重读，不把临时锁占用冒充账号缺失。
                            raise SerializationFailure("账号正在变更，请刷新后重试")
                groups = legacy.classify_sources(sources, accounts)
                prepared_native = native.prepare_retries(conn, selected_native,
                    operation_logger=logger, accounts=accounts)
                native_facts = bulk_retry_tasks.prepare_retry_tasks_many(conn, prepared_native["specs"],
                    selected_parents=parent_versions)
                prepared_regular = legacy.prepare_regular(conn, groups["regular"], accounts, logger)
                prepared_refresh = refresh.prepare_legacy(conn, groups["refresh"], accounts,
                    locked_account_ids=set(accounts))
                prepared_registration = retry_followups.prepare_followups(conn, registration.followups,
                    locked_parent_contexts=parent_versions)
                registration_results = {}
                replies = {**groups["replies"], **prepared_native["replies"],
                    **{task_id: native._reply(value) for task_id, value in native_facts["replies"].items()},
                    **prepared_regular["replies"], **prepared_refresh["replies"]}
                candidates = {
                    **{row["task_id"]: ("native", row) for row in native_facts["rows"]},
                    **{task_id: ("regular", spec) for task_id, spec in prepared_regular["specs"].items()},
                    **{task_id: ("refresh", spec) for task_id, spec in prepared_refresh["specs"].items()},
                }
                registration_tasks = {}
                for task_id, source_id in selected_registration.items():
                    registration_tasks.setdefault(source_id, task_id)
                for row in prepared_registration.rows:
                    task_id = registration_tasks[row["source_job_id"]]
                    candidates[task_id] = ("registration", row)
                winners, pending, duplicates = {}, {}, {}
                for task_id in tasks:
                    if task_id not in candidates:
                        continue
                    kind, spec = candidates[task_id]
                    identity = (int(spec.get("account_id") or 0), spec["resource_family"])
                    # 无账号的原生任务不参与 PostgreSQL 账号资源族唯一约束。
                    if identity[0] and identity in pending:
                        duplicates[task_id] = pending[identity]
                    else:
                        winners[task_id] = (kind, spec)
                        if identity[0]:
                            pending[identity] = task_id
                native_rows = [spec for kind, spec in winners.values() if kind == "native"]
                created = bulk_retry_tasks.commit_retry_tasks_many(conn, native_rows)
                regular_specs = {task_id: spec for task_id, (kind, spec) in winners.items() if kind == "regular"}
                regular_created, logs = legacy.commit_regular(conn, regular_specs, accounts)
                created.update(regular_created)
                refresh_specs = {task_id: spec for task_id, (kind, spec) in winners.items() if kind == "refresh"}
                refresh_rows = legacy.create_specs_many(conn, refresh_specs.values())
                refresh.project_prepared(conn, list(refresh_specs.values()), refresh_rows)
                created.update(dict(zip(refresh_specs, refresh_rows, strict=True)))
                registration_ids = [spec["source_job_id"] for kind, spec in winners.values() if kind == "registration"]
                registration_receipts = retry_followups.commit_followups(conn, prepared_registration,
                    winner_source_ids=registration_ids)
                for source_id, receipt in registration_receipts.items():
                    created[registration_tasks[source_id]] = receipt
                for task_id, winner in duplicates.items():
                    created[task_id] = _busy(created.get(winner))
                for plan in registration.followups:
                    source_id = int(plan.source["id"])
                    receipt = created.get(registration_tasks[source_id])
                    if receipt is not None:
                        registration_results[source_id] = registration_wave.followup_result(plan,
                            {**receipt, **({"status": 409} if receipt.get("busy") else {})})
                refresh_replies = refresh.format_prepared(prepared_refresh, {
                    task_id: created[task_id] for task_id in prepared_refresh["specs"] if task_id in created})
                replies.update(refresh_replies)
                native_replies = {task_id: created[task_id] for task_id in selected_native if task_id in created}
                for task_id in prepared_regular["specs"]:
                    if task_id in created:
                        replies[task_id] = legacy._reply(created[task_id])
            # 文件日志和调度通知只在整波事实提交后发生。
            registration.results.update(registration_results)
            replies.update(native.finish_retries(native_replies, prepared_native["kinds"], notify=False))
            legacy.finish_regular(logs)
            if any(value.get("accepted") and not value.get("reused") for value in created.values()):
                task_gateway.notify_dispatch()
            try:
                replies.update(legacy.accept_mail(groups["mail"]))
            except Exception:
                logger.exception("任务中心邮件扫描批量受理失败")
                replies.update({task_id: ({"ok": False, "error": "邮件扫描重跑入队失败，请刷新后重试"}, 503)
                    for task_id in groups["mail"]})
            return _finish_registration(registration, replies, logger)
        except (refresh.ResolvedAccountsChanged, SerializationFailure):
            if attempt < 2:
                continue
            logger.exception("任务中心重试来源在锁定期间变化")
        except Exception:
            logger.exception("任务中心直接重试集合事务失败")
        break
    return {task_id: ({"ok": False, "unavailable": True, "error_code": "retry_admission_unavailable",
        "error": "重试入口暂不可用，请刷新任务状态后重试"}, 503)
        for task_id in selected}


def _finish_registration(wave, replies, logger):
    """直接账号事实提交后再提交普通注册任务，避免后台执行抢先改变本波赢家。"""
    from core.registration import retry_wave

    try:
        wave.results.update(retry_wave.admit_registration(wave))
    except Exception:
        logger.exception("任务中心普通注册集合受理失败")
        wave.results.update({plan.source_id: {"ok": False, "status": 503,
            "error": "原注册任务入队失败，请刷新任务状态后重试"} for plan in wave.admissions})
    replies.update(retry_wave.task_replies(wave, wave.results))
    return replies
