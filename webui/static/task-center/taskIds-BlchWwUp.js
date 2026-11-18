// src/api/taskIds.ts
var e = /* @__PURE__ */ "id.task_id.job_id.run_id.last_run_id.current_run_id.codex_active_run_id.parent_task_id.parent_job_id.parent_id.root_task_id.root_job_id.baseline_job_id.child_task_id.blocker_task_id.owned_task_id.registered_account_id.account_id.sub2api_account_id.related_task_id.related_run_id.owner_task_id.owner_run_id.operation_task_id.operation_run_id.registration_job_id.registration_attempt_id.registration_run_id.event_id.next_after_id.attempt_id.batch_id.existing_batch_id.bulk_batch_id.source_job_id.latest_legacy_job_id.target_id.canonical_target_id".split(".");
function t(e) {
	if (typeof e == "number") {
		if (Number.isSafeInteger(e) && e > 0) return e;
		throw Error("任务或运行标识无效");
	}
	if (typeof e != "string" || !/^[1-9]\d*$/.test(e)) throw Error("任务或运行标识无效");
	let t = Number(e);
	return Number.isSafeInteger(t) ? t : e;
}
function n(e) {
	return e == null || e === "" || e === 0 || e === "0" ? null : t(e);
}
function r(e, t) {
	return e != null && t != null && String(e) === String(t);
}
function i(e, t) {
	let n = String(e), r = String(t);
	return n.length - r.length || (n < r ? -1 : +(n > r));
}
function a(t) {
	let n = new Set(e), r = /* @__PURE__ */ new Set([
		"event_ids",
		"job_ids",
		"task_ids",
		"run_ids",
		"attempt_ids",
		"account_ids",
		"target_ids",
		"child_task_ids",
		"parent_task_ids",
		"deleted"
	]), i = /* @__PURE__ */ new Set([
		"task",
		"tasks",
		"run",
		"runs",
		"job",
		"jobs",
		"attempt",
		"attempts",
		"parent",
		"parents",
		"batch",
		"batches",
		"items",
		"event",
		"events",
		"account",
		"accounts",
		"target",
		"targets",
		"resource",
		"resources",
		"related_task",
		"related_run",
		"owned_task",
		"owned_run"
	]), a = [], o = 0, s = () => {
		throw SyntaxError("任务响应 JSON 格式无效");
	}, c = () => {
		for (; /[\t\n\r ]/.test(t[o] || "\0");) o++;
	};
	function l() {
		let e = o;
		if (t[o++] !== "\"") return s();
		for (; o < t.length;) {
			let n = t[o++];
			if (n === "\\") o++;
			else if (n === "\"") return JSON.parse(t.slice(e, o));
		}
		return s();
	}
	function u(e = "", d = 0, f = []) {
		if (d > 256) throw SyntaxError("任务响应嵌套过深");
		c();
		let p = t[o];
		if (p === "{") {
			if (o++, c(), t[o] === "}") {
				o++;
				return;
			}
			for (;;) {
				c();
				let e = l();
				c(), t[o++] !== ":" && s(), u(e, d + 1, [...f, e]), c();
				let n = t[o++];
				if (n === "}") return;
				n !== "," && s();
			}
		}
		if (p === "[") {
			if (o++, c(), t[o] === "]") {
				o++;
				return;
			}
			for (;;) {
				u(r.has(e) ? "array_id" : "", d + 1, [...f, "[]"]), c();
				let n = t[o++];
				if (n === "]") return;
				n !== "," && s();
			}
		}
		if (p === "\"") {
			l();
			return;
		}
		for (let e of [
			"true",
			"false",
			"null"
		]) if (t.startsWith(e, o)) {
			o += e.length;
			return;
		}
		let m = t.slice(o).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
		if (!m) return s();
		let h = m[0], g = o;
		o += h.length;
		let _ = f.filter((e) => e !== "[]").at(-2);
		if (e === "array_id" || n.has(e) && (e !== "id" || !_ || i.has(_))) {
			if (!/^\d+$/.test(h)) throw SyntaxError("任务响应中的标识必须为非负整数");
			Number.isSafeInteger(Number(h)) || a.push({
				start: g,
				end: o,
				text: JSON.stringify(h)
			});
		}
	}
	u(), c(), o !== t.length && s();
	let d = "", f = 0;
	for (let e of a) d += t.slice(f, e.start) + e.text, f = e.end;
	return JSON.parse(d + t.slice(f));
}
export { t as a, r as i, n, a as r, i as t };
