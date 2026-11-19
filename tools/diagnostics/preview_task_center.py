#!/usr/bin/env python3
"""任务中心合成预览：仅内存数据，不导入业务服务、不连接数据库。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request


ROOT = Path(__file__).resolve().parents[2]
TYPES = {"plan_check": "查套餐", "token_refresh": "AT 刷新", "codex_retry": "Codex 补跑", "live_check": "查活"}
STATES = ("success", "failed", "running", "queued", "partial_success", "interrupted")


def create_preview(*, task_count: int = 125, now: datetime | None = None, event_page_size: int = 30) -> Flask:
    """构建内存预览；性能对照可固定时间、规模和证据页大小。"""
    if task_count < 125 or not 1 <= event_page_size <= 500:
        raise ValueError("预览至少需要125个任务，证据页大小需在1至500之间")
    app = Flask(__name__, static_folder=str(ROOT / "webui/static"), template_folder=str(ROOT / "webui/templates"))
    now = now or datetime.now(timezone.utc)
    tasks = []
    for index in range(1, task_count + 1):
        status = STATES[index % len(STATES)]
        task_type = list(TYPES)[index % len(TYPES)]
        failed = status in {"failed", "interrupted"}
        created = (now - timedelta(minutes=index * 3)).isoformat()
        task = {
            "id": index, "task_type": task_type, "status": status, "target_status": "failed" if failed else "account_available",
            "account_id": 2000 + index, "email_snapshot": f"demo-{index:03}@example.test", "source_system": "native_operations",
            "created_at": created, "completed_at": None if status in {"running", "queued"} else now.isoformat(),
            "duration_ms": index * 1300, "run_count": 2, "last_run_no": 2, "last_run_id": index * 10 + 2,
            "current_stage": "email_otp" if failed else "complete", "current_stage_label": "邮箱验证" if failed else "完成",
            "failure_stage": "email_otp" if failed else "", "trigger": "manual_bulk", "batch_title": "合成验收批次",
            "batch_uuid": "preview-batch-01", "error_message": "等待邮箱验证码超时（合成场景）" if failed else "",
            "error_info": {"code": "email_otp_timeout", "display_code": "E-OTP", "summary": "验证码邮件未在时限内到达", "stage": "email_otp", "category": "email", "retryable": True} if failed else None,
            "result_summary": {"message": "合成任务已完成", "current_plan_type": "free", "account_promotions": [], "plan_check_countries": []},
            "admission_wait_reasons": [{"code": "global_capacity"}] if status == "queued" else [],
            "runs": [], "resources": [], "next_actions": [{"action": "retry"}],
        }
        for number in (1, 2):
            task["runs"].append({"id": index * 10 + number, "run_no": number, "task_id": index,
                "status": "failed" if number == 1 else status, "created_at": created, "completed_at": task["completed_at"],
                "duration_ms": task["duration_ms"], "error_message": task["error_message"] if number == 2 else "上一轮代理连接超时（合成场景）",
                "error_info": task["error_info"], "result_summary": task["result_summary"], "source_system": "native_operations"})
        tasks.append(task)

    # 两个当前 Run 提供完整关系证据；第一轮及其他任务继续覆盖旧快照回退。
    waiting = tasks[121]
    child_targets = [{"task_id": 117, "run_id": 1172, "task_type": "token_refresh", "status": "queued", "evidence": "result_summary"},
                     {"task_id": 114, "run_id": 1142, "task_type": "codex_retry", "status": "success", "evidence": "result_summary"}]
    waiting_summary = {"message": "等待 AT 刷新子任务完成（合成场景）", "child_tasks": child_targets,
                       "planned_steps": ["refresh_at", "codex"], "awaiting_steps": ["refresh_at"]}
    waiting.update(task_type="account_completion", status="waiting", current_stage="refresh_dispatch",
                   current_stage_label="等待 AT 刷新子任务", completed_at=None, result_summary=waiting_summary,
                   next_actions=[{"action": "await_child", "task_id": 117}])
    waiting["runs"][-1].update(status="waiting", completed_at=None, result_summary=waiting_summary)

    def sample_time(seconds):
        return (now - timedelta(seconds=120 - seconds)).isoformat()

    def sample_execution(*, kind="stage", dependency="unknown", condition=None, waits_for=None,
                         parallel=None, retry=None):
        return {"kind": kind, "condition": condition, "dependency_state": dependency,
                "waits_for": waits_for or [], "parallel_group": parallel,
                "retry": retry or {"state": "unknown", "attempt_count": None, "event_ids": []}, "source": "event"}

    def sample_phase(name, title, state, order, seconds, *, dependencies=(), stages=None, execution=None, attempts=None):
        observed = order is not None
        return {"id": name, "label": title, "state": state, "display_status": state, "observed_order": order,
                "raw_stages": stages or [name], "depends_on": list(dependencies), "children": [],
                "started_at": sample_time(seconds) if observed else None,
                "completed_at": sample_time(seconds + 2) if observed and state in {"success", "failed"} else None,
                "duration_ms": 2000 if observed and state in {"success", "failed"} else None,
                "attempts": attempts or [], "execution": execution or sample_execution()}

    def sample_event(run_id, number, stage, state, message, seconds, **fields):
        return {"id": number, "event_id": f"preview-{run_id}-{number}", "created_at": sample_time(seconds),
                "level": "ERROR" if state == "failed" else "INFO", "stage": stage,
                "message": message, "detail": {"sample": True, "step_state": state, **fields}}

    def structured_sample(task, run):
        if run["run_no"] != 2 or (task["id"], run["status"]) not in {(121, "failed"), (122, "waiting")}:
            return None
        run_id = run["id"]
        if task["id"] == 121:
            events = [sample_event(run_id, 516, "preflight", "success", "配置预检完成（合成场景）", 0),
                      sample_event(run_id, 517, "network", "success", "网络连接已建立（合成场景）", 4),
                      sample_event(run_id, 518, "email_otp", "running", "开始等待邮箱验证码（合成场景）", 8),
                      sample_event(run_id, 519, "email_otp", "failed", run["error_message"], 70),
                      sample_event(run_id, 520, "result", "failed", "登录阶段失败，未进入 AT 刷新（合成场景）", 72)]
            steps = [sample_phase("preflight", "配置预检", "success", 1, 0),
                     sample_phase("network", "分配网络", "success", 2, 4, dependencies=["preflight"],
                                  execution=sample_execution(dependency="satisfied")),
                     sample_phase("authenticate", "登录验证", "failed", 3, 8, dependencies=["network"], stages=["email_otp"],
                                  execution=sample_execution(dependency="satisfied")),
                     sample_phase("result", "结果收口", "failed", 4, 72, dependencies=["authenticate"],
                                  execution=sample_execution(kind="result", dependency="blocked")),
                     sample_phase("refresh_token", "刷新 AT", "pending", None, 0, dependencies=["authenticate"],
                                  execution=sample_execution(dependency="blocked"))]
            steps[2].update(completed_at=sample_time(70), duration_ms=62000)
            failure = {"step_id": "authenticate", "stage": "email_otp", "label": "登录验证", "event_id": events[3]["event_id"],
                       "message": run["error_message"], "error_info": run["error_info"], "evidence": {"source": "preview_event"}}
            current, children = None, []
        else:
            events = [sample_event(run_id, 1, "preflight", "success", "补全计划已读取（合成场景）", 0),
                      sample_event(run_id, 2, "network", "running", "开始第 1 次连接（合成场景）", 4, attempt=1),
                      sample_event(run_id, 3, "network", "failed", "第 1 次连接超时（合成场景）", 7, attempt=1),
                      sample_event(run_id, 4, "network", "running", "开始第 2 次连接（合成场景）", 9, attempt=2),
                      sample_event(run_id, 5, "network", "success", "第 2 次连接成功（合成场景）", 11, attempt=2),
                      sample_event(run_id, 6, "refresh_dispatch", "running", "等待 AT 刷新子任务 #117（合成场景）", 14, parallel_group="preview-completion-branches", child_task_id=117, child_run_id=1172),
                      sample_event(run_id, 7, "codex_dispatch", "success", "Codex 子任务 #114 已完成（合成场景）", 14, parallel_group="preview-completion-branches", child_task_id=114, child_run_id=1142)]
            retry = {"state": "recovered", "attempt_count": 2, "event_ids": [event["event_id"] for event in events[1:5]]}
            steps = [sample_phase("preflight", "配置预检", "success", 1, 0),
                     sample_phase("network", "分配网络", "success", 2, 4, dependencies=["preflight"],
                                  execution=sample_execution(dependency="satisfied", retry=retry)),
                     sample_phase("refresh_dispatch", "AT 刷新子任务", "running", 3, 14, dependencies=["network"],
                                  execution=sample_execution(kind="child_task", dependency="waiting", waits_for=[child_targets[0]], parallel="preview-completion-branches")),
                     sample_phase("codex_dispatch", "Codex 子任务", "success", 4, 14, dependencies=["network"],
                                  execution=sample_execution(kind="child_task", dependency="satisfied", waits_for=[child_targets[1]], parallel="preview-completion-branches")),
                     sample_phase("account_setup_dispatch", "配置密码与 2FA", "skipped", None, 0, dependencies=["preflight"],
                                  execution=sample_execution(kind="conditional", dependency="satisfied",
                                      condition={"label": "补全计划包含密码或 2FA 配置", "state": "not_met", "evidence": "planned_steps"})),
                     sample_phase("result", "结果收口", "pending", None, 0, dependencies=["refresh_dispatch", "codex_dispatch"],
                                  execution=sample_execution(kind="result", dependency="waiting", waits_for=child_targets))]
            steps[1].update(completed_at=sample_time(11), duration_ms=7000)
            failure, current, children = None, {"step_id": "refresh_dispatch", "label": "等待 AT 刷新子任务"}, child_targets
        for step in steps:
            step["attempts"] = [{"event_id": event["event_id"], "state": event["detail"]["step_state"],
                                  "created_at": event["created_at"], "message": event["message"], "raw_stage": event["stage"],
                                  "evidence": "explicit", **event["detail"]}
                                 for event in events if event["stage"] in step["raw_stages"]]
        return {"progress": {"task_id": task["id"], "run_id": run_id, "source": "runtime", "revision": f"preview-structured-{run_id}",
                             "main_steps": steps, "current": current, "failure": failure,
                             "outcome": {"status": run["status"], "child_tasks": children},
                             "structure": {"version": 1, "order_basis": "observed_events", "parallelism": "explicit" if children else "unknown",
                                           "note": "内存合成证据：仅明确标注的组表示并行；排列顺序不代表严格执行顺序。"}}, "events": events}

    @app.get("/")
    def index():
        bundle = ROOT / "webui/static/task-center/task-center.js"
        return render_template("index.html", task_center_version=str(bundle.stat().st_mtime_ns))

    @app.get("/api/operations")
    def listing():
        values = list(reversed(tasks))
        for key, field in (("type", "task_type"), ("stage", "current_stage")):
            selected = request.args.get(key, "").split(",")
            if selected != [""]: values = [row for row in values if row[field] in selected]
        for key in ("status", "target_status"):
            if request.args.get(key): values = [row for row in values if row[key] == request.args[key]]
        for key, field in (("target", "email_snapshot"), ("result", "error_message"), ("batch", "batch_title")):
            if request.args.get(key): values = [row for row in values if request.args[key].lower() in row[field].lower()]
        if request.args.get("task_id"): values = [row for row in values if str(row["id"]) == request.args["task_id"]]
        if request.args.get("run_count"): values = [row for row in values if str(row["run_count"]) == request.args["run_count"]]
        if request.args.get("created_from"): values = [row for row in values if row["created_at"][:10] >= request.args["created_from"]]
        if request.args.get("created_to"): values = [row for row in values if row["created_at"][:10] <= request.args["created_to"]]
        page, size = max(1, int(request.args.get("page", 1))), min(100, max(1, int(request.args.get("page_size", 20))))
        data = {"ok": True, "items": [{k: v for k, v in row.items() if k not in {"runs", "resources"}} for row in values[(page-1)*size:page*size]],
            "total": len(values), "page": page, "page_size": size, "revision": str([(row["id"], row["status"]) for row in values])}
        if request.args.get("include_facets", "1") != "0":
            data["facets"] = {key: [{"value": value, "count": sum(row[field] == value for row in tasks)} for value in sorted({row[field] for row in tasks})]
                for key, field in (("task_type", "task_type"), ("status", "status"), ("target_status", "target_status"), ("stage", "current_stage"))}
        return jsonify(data)

    def find(task_id):
        return next((row for row in tasks if row["id"] == task_id), None)

    @app.get("/api/operations/<int:task_id>")
    def detail(task_id):
        task = find(task_id)
        return (jsonify(ok=True, task=task) if task else (jsonify(ok=False, error="任务不存在"), 404))

    @app.get("/api/operations/<int:task_id>/runs/<int:run_id>/<kind>")
    def run_data(task_id, run_id, kind):
        task = find(task_id)
        run = next((row for row in (task or {}).get("runs", []) if row["id"] == run_id), None)
        if not run: return jsonify(ok=False, error="运行不存在"), 404
        sample = structured_sample(task, run)
        if kind == "progress":
            if sample: return jsonify(ok=True, progress=sample["progress"])
            steps = [{"id": name, "label": title, "state": state, "display_status": state, "raw_stages": [name],
                "duration_ms": 1500, "started_at": task["created_at"], "completed_at": task["completed_at"],
                "attempts": [{"attempt": 1, "state": state, "display_status": state, "created_at": task["created_at"], "message": "合成步骤证据"}], "children": []}
                for name, title, state in (("preflight", "配置预检", "success"), ("network", "分配网络", "success"),
                    ("email_otp", "邮箱验证", "failed" if run["status"] == "failed" else "success"), ("complete", "结果收口", "pending" if run["status"] == "failed" else "success"))]
            return jsonify(ok=True, progress={"task_id": task_id, "run_id": run_id, "source": "runtime", "revision": f"preview-{run_id}", "main_steps": steps,
                "current": None, "outcome": {"status": run["status"], "child_tasks": []},
                "failure": {"stage": "email_otp", "label": "邮箱验证", "message": run["error_message"], "error_info": run["error_info"]} if run["status"] == "failed" else None})
        if kind == "events":
            rows = [{"id": number, "event_id": f"preview-{run_id}-{number}", "created_at": task["created_at"], "level": "info",
                "stage": "email_otp" if number % 2 else "network", "message": f"第 {number} 条合成事件：正在核对执行结果", "detail": {"sample": True}}
                for number in range(1, 521)]
            if sample: rows = rows[:-5] + sample["events"] if task_id == 121 else sample["events"]
            after = request.args.get("after_id")
            limit = min(event_page_size, max(1, int(request.args.get("limit", event_page_size))))
            selected = [row for row in rows if row["id"] > int(after)] if after is not None else rows[-limit:]
            more = len(selected) > limit if after is not None else len(rows) > limit
            selected = selected[:limit]
            return jsonify(ok=True, items=selected, next_after_id=selected[-1]["id"] if selected else int(after or 0), has_more=more if after is not None else len(rows) > 30)
        if kind == "logs":
            limit = min(event_page_size, max(1, int(request.args.get("limit", event_page_size))))
            cursor = int(request.args.get("cursor", 520 - limit))
            rows = [{"ts": task["created_at"], "level": "INFO", "stage": "email_otp", "message": f"合成运行日志 {number}", "fields": {"preview": True}}
                for number in range(cursor + 1, min(cursor + limit + 1, 521))]
            return jsonify(ok=True, items=rows, next_cursor=cursor+len(rows), has_more=cursor+len(rows)<520, available=True, run_terminal=run["status"] not in {"queued", "running", "waiting"})
        return jsonify(ok=False, error="预览接口不存在"), 404

    def apply_action(task_id, action):
        task = find(task_id)
        if not task: return {"task_id": task_id, "ok": False, "error": "任务不存在"}
        if action == "delete": tasks.remove(task)
        else:
            task["status"] = {"retry": "queued", "cancel": "cancelled", "terminate": "stopped"}[action]
            if action == "retry":
                run = deepcopy(task["runs"][-1]); run.update(id=task["last_run_id"]+1, run_no=task["run_count"]+1, status="queued")
                task["runs"].append(run); task.update(run_count=run["run_no"], last_run_id=run["id"])
            else: task["runs"][-1]["status"] = task["status"]
        return {"ok": True, "task_id": task_id, "state": "deleted" if action == "delete" else task["status"]}

    @app.post("/api/operations/bulk")
    def bulk_action():
        body = request.get_json() or {}
        accepted = [apply_action(int(task_id), body["action"]) for task_id in body.get("task_ids", [])]
        return jsonify(ok=True, accepted=accepted, accepted_count=len(accepted), skipped=[])

    @app.post("/api/operations/<int:task_id>/<action>")
    def action(task_id, action):
        if action not in {"retry", "cancel", "terminate", "delete"}: return jsonify(ok=False, error="不支持的预览操作"), 400
        return jsonify(apply_action(task_id, action))

    @app.get("/api/<path:unused>")
    def shell_data(unused):
        if unused == "summary": return jsonify(accounts=task_count, outlook_total=0, outlook_available=0, email_supply={"sources": []})
        if unused == "capabilities": return jsonify(capabilities={}, deployment={})
        return jsonify(ok=True, items=[], total=0, fields=[], sections=[], accounts=[], jobs=[], sources=[], data={})

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8017)
    args = parser.parse_args()
    create_preview().run(host="127.0.0.1", port=args.port, debug=False, threaded=True)
