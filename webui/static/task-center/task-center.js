import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, V as u, X as d, Z as f, _ as p, a as m, c as h, d as g, dt as _, et as v, f as y, ft as b, g as x, h as S, j as C, k as w, l as T, lt as E, m as D, n as O, nt as k, s as A, st as j, v as M, x as N } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { n as P, r as F, t as I } from "./client-B5R_MNgP.js";
import { a as L, i as ee, n as te, r as ne } from "./taskIds-BlchWwUp.js";
import { A as R, C as z, D as B, E as V, M as H, N as U, O as W, P as G, S as re, T as ie, _ as ae, a as oe, b as se, c as ce, d as le, f as ue, g as de, h as fe, i as K, j as q, k as pe, l as J, m as me, n as he, o as ge, p as _e, r as ve, s as ye, t as be, u as xe, v as Se, w as Ce, x as we, y as Te } from "./StepEvidence-DaQPwBY1.js";
import { n as Ee } from "./time-DOD6oyhP.js";
import { n as De, r as Oe, t as ke } from "./ListFilterSummary-0POqp2Om.js";
import { t as Ae } from "./useColumnWidths-CUEzVga1.js";
import { t as je } from "./ListResult-ChGvCNvJ.js";
import { t as Y } from "./errorLabels-BWpfwuWJ.js";
import { t as Me } from "./ListPagination-DDdERjeb.js";
// src/api/tasks.ts
var X = (e, t = {}) => F(e, t, ne);
function Ne() {
	return {
		task_id: "",
		type: "",
		target: "",
		status: "",
		target_status: "",
		batch: "",
		run_count: "",
		stage: "",
		created_from: "",
		created_to: "",
		result: ""
	};
}
function Pe(e) {
	return new URLSearchParams(Object.entries(e).filter(([, e]) => e !== void 0 && e !== "").map(([e, t]) => [e, String(t)])).toString();
}
function Fe(e) {
	let t = new URLSearchParams();
	for (let n of e) {
		let e = L(n.task_id), r = te(n.run_id);
		t.append("ref", r === null ? String(e) : `${e}:${r}`);
	}
	return t.toString();
}
async function Ie(e, t, n) {
	let r = `turb_operation_intent:${e}:${JSON.stringify({
		path: t,
		body: n || null
	})}`, i = null, a = !1, o = `turb_operation_intent:${e}`;
	try {
		i = sessionStorage.getItem(r);
		let e = JSON.parse(sessionStorage.getItem(o) || "null");
		e?.key && e.signature === JSON.stringify({
			url: t,
			body: n || null
		}) && (i ||= String(e.key), a = !0);
	} catch {}
	i ||= globalThis.crypto?.randomUUID?.() || `operation-${Date.now()}-${Math.random().toString(36).slice(2)}`;
	try {
		sessionStorage.setItem(r, i);
	} catch {}
	let s = () => {
		try {
			sessionStorage.removeItem(r), a && sessionStorage.removeItem(o);
		} catch {}
	};
	try {
		let e = await X(t, {
			method: "POST",
			headers: {
				"Idempotency-Key": i,
				...n ? { "Content-Type": "application/json" } : {}
			},
			...n ? { body: Le(t, n) } : {}
		});
		return s(), e;
	} catch (e) {
		throw e instanceof I && [
			400,
			403,
			404,
			409,
			410,
			422,
			429
		].includes(e.status) && s(), e;
	}
}
function Le(e, t) {
	if (e !== "/api/operations/bulk") return JSON.stringify(t);
	let { task_ids: n, ...r } = t;
	if (!Array.isArray(n)) return JSON.stringify(t);
	let i = JSON.stringify(r).slice(0, -1);
	return `${i}${i.length > 1 ? "," : ""}"task_ids":[${n.map((e) => String(L(e))).join(",")}]}`;
}
var Re = {
	list: (e, t) => X(`/api/operations?${Pe(e)}`, { signal: t }),
	detail: (e, t) => X(`/api/operations/${L(e)}?include_events=0`, { signal: t }),
	receipts: (e, t) => X(`/api/operations/receipts?${Fe(e)}`, { signal: t }),
	progress: (e, t, n) => X(`/api/operations/${L(e)}/runs/${L(t)}/progress`, { signal: n }),
	events: (e, t, n = {}, r) => X(`/api/operations/${L(e)}/runs/${L(t)}/events?${Pe({
		limit: 500,
		...n
	})}`, { signal: r }),
	logs: (e, t, n = {}, r) => X(`/api/operations/${L(e)}/runs/${L(t)}/logs?${Pe({
		limit: 500,
		...n
	})}`, { signal: r }),
	action: (e, t) => t === "retry" ? Ie(`retry:${L(e)}`, `/api/operations/${L(e)}/retry`) : X(`/api/operations/${L(e)}/${t}`, { method: "POST" }),
	bulk: (e, t) => e === "retry" ? Ie("bulk:retry", "/api/operations/bulk", {
		action: e,
		task_ids: t
	}) : X("/api/operations/bulk", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: Le("/api/operations/bulk", {
			action: e,
			task_ids: t
		})
	})
}, ze = (e) => e instanceof Error ? e.message : "读取失败，请重试";
function Be(e = Re, t = () => {}) {
	let n = v(!1), r = v(!0), i = v(null), a = v(null), o = k(null), s = k(null), c = k([]), l = k([]), u = v("events"), d = v(null), p = v(""), m = v(""), h = v(""), g = v(""), _ = v(!1), y = v(!1), b = v(!1), x = v(null), S = v(null), C = v("tail"), w = v("tail"), T = v(!1), E = v(!1), O = v(!1), A = v(!1), j = v(!0), M = D(() => o.value?.runs || []), N = D(() => M.value.find((e) => ee(e.id, a.value))), P = 0, F = 0, I = 0, ne = 0, R = null, z, B = new AbortController(), V = !1;
	function H() {
		z !== void 0 && clearTimeout(z), z = void 0;
	}
	function U() {
		P += 1, B.abort(), B = new AbortController(), R = null, _.value = y.value = b.value = !1, H();
	}
	let W = (e) => e === P && n.value, G = () => n.value && r.value && !!i.value;
	function re() {
		H(), G() && (!o.value || pe(o.value)) && (z = setTimeout(() => void le(!0), 2e3));
	}
	function ie() {
		F += 1, I += 1, y.value = b.value = !1, s.value = null, m.value = h.value = g.value = "", c.value = [], l.value = [], x.value = S.value = null, T.value = E.value = O.value = A.value = !1, C.value = w.value = "tail", j.value = !0;
	}
	async function ae(t = "incremental") {
		if (!G() || !a.value || !i.value || t === "incremental" && y.value || t === "incremental" && C.value === "start" && E.value || t === "next" && !E.value) return;
		let n = P, r = ++F, o = t === "tail" || t === "start" || x.value === null, s = {
			limit: 500,
			...t === "start" ? { after_id: 0 } : t !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		y.value = !0;
		try {
			let l = await e.events(i.value, a.value, s, B.signal);
			if (!W(n) || r !== F) return;
			c.value = o ? l.items : ue(c.value, l.items), x.value = l.next_after_id, (t === "tail" || t === "start") && (C.value = t), o && C.value === "tail" ? (T.value = l.has_more, E.value = !1) : (E.value = l.has_more, C.value === "start" && (T.value = !1)), h.value = "";
		} catch (e) {
			W(n) && r === F && (h.value = ze(e));
		} finally {
			W(n) && r === F && (y.value = !1);
		}
	}
	async function oe(t = "incremental") {
		if (!G() || !a.value || !i.value || t === "incremental" && b.value || t === "incremental" && w.value === "start" && A.value || t === "next" && !A.value) return;
		let n = P, r = ++I, o = t === "tail" || t === "start" || S.value === null, s = {
			limit: 500,
			...t === "start" ? { cursor: 0 } : t !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		b.value = !0;
		try {
			let c = await e.logs(i.value, a.value, s, B.signal);
			if (!W(n) || r !== I) return;
			l.value = o ? c.items : [...l.value, ...c.items], S.value = c.next_cursor, (t === "tail" || t === "start") && (w.value = t), A.value = c.has_more, O.value = w.value === "tail" && c.available, j.value = c.available, g.value = "";
		} catch (e) {
			W(n) && r === I && (g.value = ze(e));
		} finally {
			W(n) && r === I && (b.value = !1);
		}
	}
	async function se(t) {
		if (i.value && a.value) try {
			let n = await e.progress(i.value, a.value, B.signal);
			if (!W(t)) return;
			s.value = n.progress, m.value = "";
		} catch (e) {
			W(t) && (m.value = ze(e));
		}
	}
	function ce() {
		return le(!1);
	}
	function le(e) {
		if (!G() || !i.value) return Promise.resolve();
		if (e || (_.value = !0), R) return R;
		let t = P, n = ++ne;
		return R = de(t, n).finally(() => {
			W(t) && n === ne && (R = null, _.value = !1, re());
		}), R;
	}
	async function de(n, r) {
		if (i.value) {
			H();
			try {
				let s = await e.detail(i.value, B.signal);
				if (!W(n) || r !== ne) return;
				o.value = s.task;
				let c = s.task.runs || [];
				if (a.value && !c.some((e) => ee(e.id, a.value))) {
					ie(), p.value = `所选运行 #${a.value} 不存在或已不可用，请选择其他运行。`;
					return;
				}
				let l = a.value || s.task.last_run_id || c.at(-1)?.id || null, d = c.some((e) => ee(e.id, l)) ? l : c.at(-1)?.id || null;
				if (d !== a.value && (ie(), a.value = d), p.value = "", a.value && await Promise.allSettled([
					se(n),
					ae(),
					...u.value === "logs" ? [oe()] : []
				]), !W(n)) return;
				!pe(s.task) && !V && (V = !0, t());
			} catch (e) {
				W(n) && (p.value = ze(e));
			}
		}
	}
	function fe(e, t, r) {
		return U(), n.value = !0, i.value = L(e), a.value = te(t), o.value = null, p.value = "", u.value = "events", d.value = r || null, V = !1, ie(), ce();
	}
	function K() {
		n.value = !1, U();
	}
	function q(e) {
		if (e = L(e), !ee(e, a.value)) return U(), a.value = e, d.value = null, ie(), ce();
	}
	function J(e) {
		if (u.value = e, e === "logs") return oe();
	}
	function me(e) {
		r.value !== e && (r.value = e, e ? n.value && ce() : U());
	}
	return f(K), {
		opened: n,
		taskId: i,
		runId: a,
		task: o,
		runs: M,
		selectedRun: N,
		progress: s,
		events: c,
		logs: l,
		tab: u,
		stepFilter: d,
		error: p,
		progressError: m,
		eventsError: h,
		logsError: g,
		loading: _,
		eventsLoading: y,
		logsLoading: b,
		eventsMode: C,
		logsMode: w,
		eventsEarlier: T,
		eventsMore: E,
		logsEarlier: O,
		logsMore: A,
		logsAvailable: j,
		open: fe,
		close: K,
		selectRun: q,
		selectTab: J,
		setVisible: me,
		refresh: ce,
		loadEvents: ae,
		loadLogs: oe
	};
}
// src/features/tasks/detail/TaskFailure.vue?vue&type=script&setup=true&lang.ts
var Ve = {
	key: 0,
	class: "tc-progress-failure tc-task-failure"
}, He = { key: 0 }, Ue = { key: 1 }, We = {
	key: 2,
	class: "tc-failure-secondary"
}, Ge = { key: 3 }, Ke = { key: 0 }, qe = { key: 1 }, Je = { key: 2 }, Ye = /* @__PURE__ */ t({
	__name: "TaskFailure",
	props: {
		failure: {},
		execution: {},
		status: {}
	},
	setup(e) {
		let t = e, r = D(() => !!(t.execution?.error_message || t.execution?.error_info)), i = D(() => (t.failure?.country_failures || []).filter((e) => we(e.country).trim())), a = D(() => {
			let e = t.failure;
			return e ? i.value.length && !e.error_info?.auto_refresh_at_failed ? `${i.value.length} 个国家查询失败，展开查看具体原因` : J(e) : "";
		}), s = D(() => {
			let e = t.failure;
			if (!e) return "";
			let n = e.error_info?.stage?.replace(/_result$/, "");
			return n && ![
				"unknown",
				"complete",
				"result",
				"event",
				"queued"
			].includes(n) && n !== e.stage ? R("stage", n) : [e.label || e.step_id || "阶段记录缺失", e.stage].filter(Boolean).join(" · ");
		}), c = D(() => r.value ? V(t.execution?.error_info, t.execution?.error_message) : ""), l = D(() => {
			if (!t.failure || !r.value) return !1;
			let e = (e) => we(e).replace(/\s+/g, " ").trim(), n = t.failure, i = n.error_info, a = t.execution?.error_info, o = e(n.message), s = e(t.execution?.error_message);
			if (o && s && o !== s) return !1;
			if (i?.cause_summary && a?.cause_summary) return e(i.cause_summary) === e(a.cause_summary);
			if (o && s) return o === s;
			let c = e(i?.cause_summary || i?.summary || n.message);
			return !!c && c === e(a?.cause_summary || a?.summary || t.execution?.error_message);
		}), u = D(() => ({
			...t.failure ? { failure: t.failure } : {},
			...r.value ? { execution: {
				error_message: t.execution?.error_message,
				error_info: t.execution?.error_info
			} } : {}
		}));
		return (t, d) => e.failure || r.value ? (n(), M("details", Ve, [
			S("summary", null, [
				e.failure ? (n(), M("strong", He, b(j(ce)(e.failure) ? "历史失败位置" : "失败位置") + "：" + b(s.value), 1)) : (n(), M("strong", Ue, "执行失败")),
				S("span", null, b(a.value || c.value), 1),
				e.failure && r.value && !l.value ? (n(), M("span", We, "执行错误：" + b(c.value), 1)) : p("", !0),
				e.execution?.error_info?.display_code ? (n(), M("small", Ge, b(e.execution.error_info.display_code), 1)) : p("", !0)
			]),
			i.value.length ? (n(), M("ul", Ke, [(n(!0), M(g, null, o(i.value, (e, t) => (n(), M("li", { key: t }, b(e.country) + "：" + b(e.summary || "诊断记录不完整"), 1))), 128))])) : p("", !0),
			e.failure?.event_id ? (n(), M("p", qe, "关联事件 " + b(e.failure.event_id), 1)) : p("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(j(we)(e.status)) ? (n(), M("p", Je, "原请求证据已保留")) : p("", !0),
			S("pre", null, b(JSON.stringify(u.value, null, 2)), 1)
		])) : p("", !0);
	}
}), Xe = {
	key: 0,
	class: "tc-progress",
	"aria-label": "执行进度"
}, Ze = { class: "tc-progress-heading" }, Qe = { key: 0 }, $e = [
	"aria-pressed",
	"title",
	"onClick"
], et = {
	key: 0,
	class: "tc-step-dot",
	"aria-hidden": "true"
}, tt = {
	key: 1,
	class: "tc-step-meta"
}, nt = { key: 0 }, rt = {
	key: 2,
	class: "tc-step-meta"
}, it = { key: 0 }, at = ["aria-label", "onClick"], ot = {
	key: 1,
	class: "tc-detail-muted"
}, st = {
	key: 2,
	class: "tc-flow-relations"
}, ct = { key: 0 }, lt = {
	key: 3,
	class: "tc-child-tasks"
}, ut = ["onClick"], dt = { id: "tc-step-title" }, ft = { class: "tc-step-dialog-body" }, pt = /* @__PURE__ */ t({
	__name: "TaskProgress",
	props: {
		progress: {},
		filter: {},
		active: { type: Boolean },
		context: {},
		taskType: {},
		execution: {}
	},
	emits: ["filter", "child"],
	setup(t, { emit: r }) {
		let a = t, s = r, c = D(() => a.taskType === "codex_retry"), u = D(() => c.value ? a.progress?.main_steps || [] : oe(a.progress?.main_steps)), d = D(() => c.value ? u.value.filter((e) => e.observed_order != null || e.evidence === "run_status") : u.value), f = {
			success: "tc-badge--success",
			recovered: "tc-badge--success",
			failed: "tc-badge--danger",
			running: "tc-badge--active",
			stopped: "tc-badge--warning",
			interrupted: "tc-badge--warning",
			debug_paused: "tc-badge--warning"
		};
		function m(e) {
			let t = se(e);
			return [
				"success",
				"failed",
				"skipped",
				"running"
			].includes(t) ? fe(t) : K(e);
		}
		let h = v(null), _ = D(() => u.value.find((e) => Se(e) === h.value)), y = v(), w = null, O = D(() => de(a.progress?.outcome?.child_tasks).flatMap((e) => {
			try {
				return [{
					...e,
					task_id: L(e.task_id),
					run_id: te(e.run_id),
					task_type: e.task_type,
					status: e.status
				}];
			} catch {
				return [];
			}
		})), k = D(() => {
			let e = _e(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${Ee(we(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			return t ? `当前：${t.label || t.step_id || "执行中"}${t.child_label ? ` · ${t.child_label}` : ""}` : "执行阶段";
		});
		function A(e) {
			return [
				Te(e),
				K(e),
				...ve(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function P(e) {
			return Se(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function F(t) {
			w = document.activeElement instanceof HTMLElement ? document.activeElement : null, h.value = Se(t), await e(), y.value?.open || y.value?.showModal();
		}
		function I() {
			y.value?.close(), h.value = null, w?.isConnected && w.focus({ preventScroll: !0 }), w = null;
		}
		function ee(e) {
			let t = y.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i(() => [a.context, a.active], I), C(() => y.value?.close()), (e, r) => t.progress ? (n(), M("section", Xe, [
			S("div", Ze, [S("strong", null, b(k.value), 1), !c.value || t.progress.source !== "explicit" ? (n(), M("small", Qe, b(t.progress.source === "legacy_derived" ? "历史记录还原" : t.progress.source === "insufficient_evidence" ? "步骤记录缺失" : "按首次记录排列，可含分支与重试"), 1)) : p("", !0)]),
			d.value.length ? (n(), M("ul", {
				key: 0,
				class: E(["tc-progress-track", { "tc-progress-track--codex": c.value }]),
				"aria-label": "执行阶段，排列不代表固定顺序"
			}, [(n(!0), M(g, null, o(d.value, (e) => (n(), M("li", {
				key: j(Se)(e),
				class: E([
					"tc-step",
					`tc-step--${j(se)(e)}`,
					{ "tc-step--selected": P(e) }
				])
			}, [S("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": P(e),
				title: A(e),
				onClick: (t) => s("filter", P(e) ? null : j(Se)(e))
			}, [
				c.value ? p("", !0) : (n(), M("span", et)),
				S("strong", null, b(j(Te)(e)), 1),
				c.value ? (n(), M("span", tt, [S("span", { class: E(["tc-badge tc-step-status", f[j(se)(e)]]) }, b(m(e)), 3), j(se)(e) !== "skipped" && j(ae)(e) != null ? (n(), M("small", nt, b(j(W)(j(ae)(e))), 1)) : p("", !0)])) : (n(), M("span", rt, [
					N(b(j(K)(e)), 1),
					j(ae)(e) == null ? p("", !0) : (n(), M("small", it, " · " + b(j(W)(j(ae)(e))), 1)),
					(n(!0), M(g, null, o(j(ve)(e), (e) => (n(), M("small", { key: e }, " · " + b(e), 1))), 128))
				]))
			], 8, $e), S("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${j(Te)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => F(e)
			}, [...r[2] ||= [S("svg", {
				viewBox: "0 0 16 16",
				width: "14",
				height: "14",
				"aria-hidden": "true"
			}, [S("circle", {
				cx: "8",
				cy: "8",
				r: "5.5",
				fill: "none",
				stroke: "currentColor"
			}), S("path", {
				d: "M8 7v4M8 4.5v1",
				stroke: "currentColor",
				"stroke-width": "1.5"
			})], -1)]], 8, at)], 2))), 128))], 2)) : (n(), M("p", ot, b(c.value ? "此运行暂无阶段记录。" : "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。"), 1)),
			u.value.length ? (n(), M("details", st, [
				r[3] ||= S("summary", null, "依赖与执行记录", -1),
				S("p", null, b(t.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1),
				(n(!0), M(g, null, o(u.value, (e) => (n(), M("div", {
					key: j(Se)(e),
					class: "tc-flow-relation"
				}, [
					S("strong", null, b(j(Te)(e)), 1),
					c.value ? (n(), M("span", ct, b(m(e)), 1)) : p("", !0),
					l(he, {
						step: e,
						siblings: u.value
					}, null, 8, ["step", "siblings"])
				]))), 128))
			])) : p("", !0),
			l(Ye, {
				failure: t.progress.failure,
				execution: t.execution,
				status: t.progress.outcome.status
			}, null, 8, [
				"failure",
				"execution",
				"status"
			]),
			O.value.length ? (n(), M("div", lt, [r[4] ||= S("strong", null, "独立子任务", -1), (n(!0), M(g, null, o(O.value, (e) => (n(), M("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, b(j(R)("task_type", j(we)(e.task_type))) + " #" + b(e.task_id) + " · " + b(j(fe)(e.status)), 9, ut))), 128))])) : p("", !0),
			S("dialog", {
				ref_key: "inspector",
				ref: y,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: T(I, ["prevent"]),
				onClose: r[0] ||= (e) => h.value = null,
				onWheel: T(ee, ["stop"]),
				onClick: r[1] ||= (e) => {
					e.target === y.value && I();
				}
			}, [S("header", null, [S("h3", dt, b(_.value ? j(Te)(_.value) : "步骤详情"), 1), S("button", {
				type: "button",
				autofocus: "",
				onClick: I
			}, "关闭")]), S("div", ft, [_.value ? (n(), x(be, {
				key: 0,
				step: _.value,
				siblings: u.value
			}, null, 8, ["step", "siblings"])) : p("", !0)])], 544)
		])) : p("", !0);
	}
}), mt = { class: "tc-detail-header" }, ht = { id: "tc-detail-title" }, gt = { key: 0 }, _t = ["title"], vt = {
	key: 0,
	class: "tc-detail-status"
}, yt = {
	key: 1,
	class: "tc-detail-run"
}, bt = ["value", "disabled"], xt = ["value"], St = {
	key: 1,
	value: ""
}, Ct = ["value"], wt = { class: "tc-detail-header-actions" }, Tt = ["disabled"], Et = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Dt = { key: 0 }, Ot = ["disabled"], kt = {
	key: 1,
	class: "tc-detail-empty",
	role: "status"
}, At = {
	key: 0,
	class: "tc-detail-notice"
}, jt = {
	key: 1,
	class: "tc-detail-notice"
}, Mt = {
	key: 3,
	class: "tc-detail-error",
	role: "status"
}, Nt = { class: "tc-detail-view-toolbar" }, Pt = [
	"id",
	"data-detail-tab",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], Ft = { class: "tc-detail-filter" }, It = {
	key: 0,
	class: "tc-detail-read-toolbar"
}, Lt = ["aria-pressed", "disabled"], Rt = ["aria-pressed", "disabled"], zt = {
	id: "tc-detail-panel-events",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-events",
	tabindex: "0"
}, Bt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Vt = ["disabled"], Ht = {
	key: 1,
	class: "tc-detail-notice"
}, Ut = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, Wt = { class: "tc-event-meta" }, Gt = { key: 0 }, Kt = {
	key: 0,
	class: "tc-technical"
}, qt = ["disabled"], Jt = {
	id: "tc-detail-panel-logs",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-logs",
	tabindex: "0"
}, Yt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Xt = ["disabled"], Zt = {
	key: 1,
	class: "tc-detail-notice"
}, Qt = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, $t = { class: "tc-event-meta" }, en = {
	key: 0,
	class: "tc-technical"
}, tn = ["disabled"], nn = {
	id: "tc-detail-panel-artifacts",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-artifacts",
	tabindex: "0"
}, rn = {
	key: 0,
	class: "tc-artifact"
}, an = { key: 0 }, on = { class: "tc-artifact-links" }, sn = ["href"], cn = ["href"], ln = ["href"], un = {
	key: 1,
	class: "tc-detail-empty"
}, dn = {
	key: 2,
	class: "tc-technical"
}, fn = { class: "tc-detail-footer" }, pn = {
	key: 1,
	role: "status"
}, mn = /* @__PURE__ */ t({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(t, { expose: r, emit: c }) {
		let u = c, d = Be(void 0, () => u("refresh")), { opened: f, taskId: m, runId: h, task: _, runs: w, selectedRun: O, progress: k, events: P, logs: F, tab: I, stepFilter: L, error: te, progressError: ne, eventsError: z, logsError: B, loading: V, eventsLoading: H, logsLoading: U, eventsMode: G, logsMode: ie, eventsEarlier: ae, eventsMore: oe, logsEarlier: se, logsMore: ce, logsAvailable: ue } = d, de = v(), K = v(), q = v(0), pe = Intl.DateTimeFormat().resolvedOptions().timeZone, J = [
			{
				id: "events",
				label: "事件时间线"
			},
			{
				id: "logs",
				label: "运行日志"
			},
			{
				id: "artifacts",
				label: "诊断资源"
			}
		], he = D(() => k.value?.main_steps || []), ve = D(() => he.value.find((e) => Se(e) === L.value || !!(L.value && e.raw_stages?.includes(L.value)))), be = D(() => me(P.value.filter((e) => xe(e, L.value, he.value)))), Ce = D(() => F.value.filter((e) => xe(e, L.value, he.value, !0))), De = D(() => be.value.map((e) => {
			let t = ye(e), n = le(e.detail);
			return {
				event: e,
				state: t,
				timestamp: Ee(e.created_at),
				stageLabel: e.stage_label || R("stage", e.stage),
				association: Pe(e),
				stateLabel: t ? fe(t) : "记录",
				detailJson: n ? JSON.stringify(n, null, 2) : null
			};
		})), Oe = D(() => Ce.value.map((e) => {
			let t = le(e.fields);
			return {
				item: e,
				timestamp: e.ts ? Ee(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), ke = D(() => h.value ? O.value : _.value), Ae = D(() => _.value?.email_snapshot || _.value?.email || (_.value?.account_id ? `账号 #${_.value.account_id}` : _.value?.target_id || "执行记录与诊断")), je = D(() => (_.value?.resources || []).filter((e) => !h.value || ee(e.run_id, h.value))), Y = D(() => O.value?.debug_artifacts), Me = D(() => _e(O.value?.debug_pause || k.value?.debug_pause)), X = null, Ne = !1;
		function Pe(e) {
			let t = _e(e.detail), n = we(e.main_step_id || t.main_step_id), r = we(e.raw_stage || t.raw_stage || e.stage), i = he.value.filter((e) => n ? e.id === n : e.raw_stages?.includes(r));
			return i.length === 1 ? Te(i[0]) : "未关联步骤";
		}
		function Fe() {
			f.value && (d.close(), X?.isConnected && X.focus({ preventScroll: !0 }), X = null, u("close"));
		}
		function Ie() {
			de.value?.close(), Fe();
		}
		async function Le(t, n, r) {
			f.value || (X = document.activeElement instanceof HTMLElement ? document.activeElement : null), q.value = 0, d.setVisible(!document.hidden);
			let i = d.open(t, n, r);
			return await e(), !de.value?.open && f.value && de.value?.showModal(), i;
		}
		function Re(e) {
			d.setVisible(e);
		}
		function ze() {
			Re(!document.hidden);
		}
		function Ve(e) {
			q.value = 0, d.selectRun(e.target.value);
		}
		async function He(t) {
			q.value = 0, await d.selectTab(t), await e(), K.value && (K.value.scrollTop = 0);
		}
		function Ue(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			let t = J.findIndex((e) => e.id === I.value), n = e.key === "Home" ? 0 : e.key === "End" ? J.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + J.length) % J.length;
			e.preventDefault(), He(J[n].id), e.currentTarget.querySelector(`[data-detail-tab="${J[n].id}"]`)?.focus();
		}
		async function We(t) {
			Ne = !0, I.value === "events" ? await d.loadEvents(t) : await d.loadLogs(t), await e(), K.value && t !== "next" && (K.value.scrollTop = t === "tail" ? K.value.scrollHeight : 0), q.value = 0, Ne = !1;
		}
		function Ge() {
			K.value && (K.value.scrollTop = K.value.scrollHeight), q.value = 0;
		}
		function Ke(e) {
			let t = K.value;
			de.value && de.value.scrollHeight > de.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i([P, F], async ([t, n], [r, i]) => {
			if (Ne) return;
			let a = K.value, o = !a || a.scrollTop + a.clientHeight >= a.scrollHeight - 40, s = I.value === "events" ? t.length - r.length : I.value === "logs" ? n.length - i.length : 0;
			s <= 0 || (await e(), o ? Ge() : q.value += s);
		}), i(L, () => {
			q.value = 0, K.value && (K.value.scrollTop = 0);
		}), s(() => {
			ze(), document.addEventListener("visibilitychange", ze);
		}), C(() => {
			document.removeEventListener("visibilitychange", ze), de.value?.close();
		}), r({
			open: Le,
			close: Ie,
			setVisible: Re
		}), (e, t) => (n(), x(y, { to: "body" }, [S("dialog", {
			ref_key: "dialog",
			ref: de,
			class: "tc-detail-dialog",
			"aria-labelledby": "tc-detail-title",
			onCancel: T(Ie, ["prevent"]),
			onClose: Fe,
			onWheel: Ke
		}, [
			S("header", mt, [
				S("h2", ht, [N("任务 #" + b(j(m)) + " ", 1), j(_) ? (n(), M("span", gt, b(j(R)("task_type", j(_).task_type)), 1)) : p("", !0)]),
				S("span", {
					class: "tc-detail-target",
					title: String(Ae.value),
					tabindex: "0"
				}, b(Ae.value), 9, _t),
				ke.value ? (n(), M("div", vt, [S("strong", null, b(j(R)("status", ke.value.status)), 1), S("span", null, "耗时 " + b(j(W)(ke.value.duration_ms)), 1)])) : p("", !0),
				j(_) ? (n(), M("label", yt, [t[10] ||= S("span", null, "运行", -1), S("select", {
					value: j(h) || "",
					"aria-label": "选择执行实例",
					disabled: j(w).length < 2 && (!j(h) || !!j(O)),
					onChange: Ve
				}, [j(h) && !j(O) ? (n(), M("option", {
					key: 0,
					value: j(h),
					disabled: ""
				}, "运行 #" + b(j(h)) + " 不可用", 9, xt)) : j(w).length ? p("", !0) : (n(), M("option", St, "暂无运行")), (n(!0), M(g, null, o(j(w), (e) => (n(), M("option", {
					key: e.id,
					value: e.id
				}, "第 " + b(e.run_no || "—") + " 次 · " + b(j(R)("status", e.status)), 9, Ct))), 128))], 40, bt)])) : p("", !0),
				S("div", wt, [S("button", {
					type: "button",
					disabled: j(V),
					onClick: t[0] ||= (...e) => j(d).refresh && j(d).refresh(...e)
				}, b(j(V) ? "刷新中…" : "刷新"), 9, Tt), S("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Ie
				}, "关闭")])
			]),
			j(te) ? (n(), M("div", Et, [
				N("读取任务失败：" + b(j(te)), 1),
				j(_) ? (n(), M("span", Dt, "。保留上次已读取的记录。")) : p("", !0),
				S("button", {
					type: "button",
					disabled: j(V),
					onClick: t[1] ||= (...e) => j(d).refresh && j(d).refresh(...e)
				}, "重试", 8, Ot)
			])) : p("", !0),
			j(V) && !j(_) ? (n(), M("div", kt, "正在读取任务详情…")) : p("", !0),
			j(_) ? (n(), M(g, { key: 2 }, [
				ke.value?.status === "queued" ? (n(), M("p", At, b(j(re)(ke.value)), 1)) : p("", !0),
				Me.value.state === "paused" ? (n(), M("p", jt, [t[11] ||= N("调试暂停，等待结束调试。", -1), Me.value.hold_until ? (n(), M(g, { key: 0 }, [N("保留至 " + b(j(Ee)(Me.value.hold_until)) + "。", 1)], 64)) : p("", !0)])) : p("", !0),
				j(k) ? p("", !0) : (n(), x(Ye, {
					key: 2,
					execution: ke.value,
					status: ke.value?.status
				}, null, 8, ["execution", "status"])),
				l(pt, {
					progress: j(k),
					"task-type": j(_)?.task_type,
					execution: ke.value,
					filter: j(L),
					active: j(f),
					context: `${j(m)}:${j(h)}`,
					onFilter: t[2] ||= (e) => L.value = e,
					onChild: Le
				}, null, 8, [
					"progress",
					"task-type",
					"execution",
					"filter",
					"active",
					"context"
				]),
				j(ne) ? (n(), M("p", Mt, [N("进度读取失败：" + b(j(ne)), 1), j(k) ? (n(), M(g, { key: 0 }, [N("；保留上次快照")], 64)) : p("", !0)])) : p("", !0),
				S("div", Nt, [
					S("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: Ue
					}, [(n(), M(g, null, o(J, (e) => S("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": j(I) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: j(I) === e.id ? 0 : -1,
						onClick: (t) => He(e.id)
					}, b(e.label), 9, Pt)), 64))], 32),
					S("div", Ft, [S("span", null, [t[12] ||= N("当前查看：", -1), S("strong", null, b(ve.value ? j(Te)(ve.value) : j(L) || "全流程"), 1)]), j(L) ? (n(), M("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => L.value = null
					}, "清除步骤筛选")) : p("", !0)]),
					j(I) === "artifacts" ? p("", !0) : (n(), M("div", It, [S("button", {
						type: "button",
						"aria-pressed": (j(I) === "events" ? j(G) : j(ie)) === "start",
						disabled: j(H) || j(U) || !j(h),
						onClick: t[4] ||= (e) => We("start")
					}, "从头加载", 8, Lt), S("button", {
						type: "button",
						"aria-pressed": (j(I) === "events" ? j(G) : j(ie)) === "tail",
						disabled: j(H) || j(U) || !j(h),
						onClick: t[5] ||= (e) => We("tail")
					}, "最近记录", 8, Rt)]))
				]),
				S("div", {
					ref_key: "scroller",
					ref: K,
					class: "tc-detail-content"
				}, [
					a(S("section", zt, [
						j(z) ? (n(), M("p", Bt, [N("事件读取失败：" + b(j(z)), 1), S("button", {
							type: "button",
							disabled: j(H),
							onClick: t[6] ||= (e) => j(d).loadEvents()
						}, "重试", 8, Vt)])) : p("", !0),
						j(ae) ? (n(), M("p", Ht, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : p("", !0),
						be.value.length ? p("", !0) : (n(), M("div", Ut, b(j(H) ? "正在读取事件…" : j(L) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(n(!0), M(g, null, o(De.value, (e) => (n(), M("article", {
							key: e.event.id,
							class: E(["tc-event", { "tc-event--error": e.state === "failed" }])
						}, [
							S("div", Wt, [
								S("time", null, b(e.timestamp), 1),
								S("span", null, b(e.event.level || "INFO"), 1),
								S("strong", null, b(e.stageLabel), 1),
								e.association ? (n(), M("span", Gt, b(e.association), 1)) : p("", !0),
								S("span", null, b(e.stateLabel), 1),
								S("small", null, "事件 " + b(e.event.event_id || e.event.id), 1)
							]),
							S("p", null, b(e.event.message || "—"), 1),
							e.detailJson ? (n(), M("details", Kt, [t[13] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 2))), 128)),
						j(oe) ? (n(), M("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: j(H),
							onClick: t[7] ||= (e) => We("next")
						}, b(j(H) ? "正在读取…" : "继续加载后续事件"), 9, qt)) : p("", !0)
					], 512), [[A, j(I) === "events"]]),
					a(S("section", Jt, [
						j(B) ? (n(), M("p", Yt, [N("日志读取失败：" + b(j(B)), 1), S("button", {
							type: "button",
							disabled: j(U),
							onClick: t[8] ||= (e) => j(d).loadLogs()
						}, "重试", 8, Xt)])) : p("", !0),
						j(se) ? (n(), M("p", Zt, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : p("", !0),
						Ce.value.length ? p("", !0) : (n(), M("div", Qt, b(j(U) ? "正在读取运行日志…" : j(ue) ? j(L) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(n(!0), M(g, null, o(Oe.value, (e, r) => (n(), M("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${r}`,
							class: "tc-log-line"
						}, [
							S("div", $t, [
								S("time", null, b(e.timestamp), 1),
								S("strong", null, b(e.item.level || "INFO"), 1),
								S("span", null, b(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							S("p", null, b(e.item.message), 1),
							e.detailJson ? (n(), M("details", en, [t[14] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						]))), 128)),
						j(ce) ? (n(), M("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: j(U),
							onClick: t[9] ||= (e) => We("next")
						}, b(j(U) ? "正在读取…" : "继续加载后续日志"), 9, tn)) : p("", !0)
					], 512), [[A, j(I) === "logs"]]),
					a(S("section", nn, [
						Y.value?.available ? (n(), M("article", rn, [
							t[15] ||= S("h3", null, "Roxy 刷新调试", -1),
							S("p", null, b(Y.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + b(j(_e)(Y.value.summary).request_count || 0) + " 条", 1),
							j(O)?.result_summary?.debug_browser_kept === !0 ? (n(), M("p", an, "失败窗口已保留，可在 Roxy 中查看。")) : p("", !0),
							S("div", on, [
								j(ge)(Y.value.har_url) ? (n(), M("a", {
									key: 0,
									href: j(ge)(Y.value.har_url),
									download: ""
								}, "下载 HAR", 8, sn)) : p("", !0),
								j(ge)(Y.value.page_state_url) ? (n(), M("a", {
									key: 1,
									href: j(ge)(Y.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, cn)) : p("", !0),
								j(ge)(Y.value.screenshot_url) ? (n(), M("a", {
									key: 2,
									href: j(ge)(Y.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, ln)) : p("", !0)
							])
						])) : p("", !0),
						(n(!0), M(g, null, o(je.value, (e, t) => (n(), M("article", {
							key: j(we)(e.id) || t,
							class: "tc-artifact"
						}, [
							S("h3", null, b(e.resource_type || "运行资源"), 1),
							S("p", null, b(e.provider || e.state || "—"), 1),
							S("small", null, b(j(Ee)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!Y.value?.available && !je.value.length ? (n(), M("div", un, "当前 Run 没有诊断资源或产物")) : p("", !0),
						ke.value?.result_summary ? (n(), M("details", dn, [t[16] ||= S("summary", null, "执行结果字段", -1), S("pre", null, b(JSON.stringify(ke.value.result_summary, null, 2)), 1)])) : p("", !0)
					], 512), [[A, j(I) === "artifacts"]])
				], 512),
				S("footer", fn, [S("small", null, "时间按浏览器时区显示 · " + b(j(pe)), 1), q.value && j(I) !== "artifacts" ? (n(), M("button", {
					key: 0,
					type: "button",
					onClick: Ge
				}, "有 " + b(q.value) + " 条新记录，回到底部", 1)) : j(V) || j(H) || j(U) ? (n(), M("small", pn, "正在同步记录…")) : p("", !0)])
			], 64)) : p("", !0)
		], 544)]));
	}
}), hn = [
	{
		key: "task_id",
		label: "ID",
		fields: ["task_id"],
		kind: "search",
		placeholder: "任务 ID"
	},
	{
		key: "type",
		label: "类型",
		fields: ["type"],
		kind: "select",
		group: "task_type"
	},
	{
		key: "target",
		label: "目标",
		fields: ["target"],
		kind: "search",
		placeholder: "账号、邮箱或注册尝试"
	},
	{
		key: "status",
		label: "执行状态",
		fields: ["status"],
		kind: "select",
		group: "status"
	},
	{
		key: "target_status",
		label: "目标状态",
		fields: ["target_status"],
		kind: "select",
		group: "target_status"
	},
	{
		key: "batch",
		label: "批次 / 触发",
		fields: ["batch"],
		kind: "search",
		placeholder: "批次或触发方式"
	},
	{
		key: "run_count",
		label: "运行次数",
		fields: ["run_count"],
		kind: "select",
		group: "run_count"
	},
	{
		key: "stage",
		label: "当前步骤",
		fields: ["stage"],
		kind: "select",
		group: "stage"
	},
	{
		key: "created",
		label: "创建 / 完成",
		fields: ["created_from", "created_to"],
		kind: "date-range"
	},
	{
		key: "result",
		label: "结果 / 错误",
		fields: ["result"],
		kind: "search",
		placeholder: "结果或错误关键词"
	}
];
function gn(e, t) {
	return e.fields.some((e) => !!t[e]);
}
function _n(e, t, n) {
	if (e.kind === "date-range") {
		let e = t.created_from, n = t.created_to;
		return e && n ? `创建日期 ${e} 至 ${n}` : e ? `创建日期自 ${e}` : n ? `创建日期截至 ${n}` : "";
	}
	let r = t[e.fields[0]];
	if (!r || e.kind !== "select") return r;
	let i = e.group || "", a = n[i] || [];
	return a.find((e) => e.value === r)?.label || r.split(",").map((e) => {
		let t = e.trim();
		return a.find((e) => e.value === t)?.label || R(i, t);
	}).join("、");
}
function vn(e, t) {
	let n = { ...t };
	for (let t of e.fields) n[t] = "";
	return n;
}
// src/features/tasks/TaskFilterFields.vue?vue&type=script&setup=true&lang.ts
var yn = {
	key: 0,
	class: "tc-filter-field"
}, bn = ["for"], xn = [
	"id",
	"value",
	"inputmode",
	"placeholder"
], Sn = ["aria-label"], Cn = ["name", "checked"], wn = { class: "tc-filter-option-label" }, Tn = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], En = { class: "tc-filter-option-label" }, Dn = {
	key: 0,
	class: "tc-filter-option-count"
}, On = {
	key: 2,
	class: "tc-filter-date-range"
}, kn = { class: "tc-filter-field" }, An = ["for"], jn = ["id", "value"], Mn = { class: "tc-filter-field" }, Nn = ["for"], Pn = ["id", "value"], Fn = { class: "tc-filter-footer" }, In = ["disabled"], Ln = /* @__PURE__ */ t({
	__name: "TaskFilterFields",
	props: {
		column: {},
		modelValue: {},
		facets: {}
	},
	emits: ["update:modelValue", "done"],
	setup(e, { emit: t }) {
		let r = e, i = t, a = u(), s = D(() => r.column.fields[0]), c = D(() => r.modelValue[s.value]), l = {
			task_type: "全部类型",
			status: "全部状态",
			target_status: "全部目标状态",
			run_count: "全部次数",
			stage: "全部步骤"
		}, d = {
			stopping: "请求停止",
			cancelling: "请求取消"
		}, f = D(() => {
			let e = r.column.group || "", t = r.facets[e] || [], n = new Map(t.map((e) => [e.value, e])), i = /* @__PURE__ */ new Set([
				...Object.keys(q[e] || {}),
				...t.map((e) => e.value),
				...c.value ? [c.value] : []
			]), a = [
				"queued",
				"running",
				"waiting",
				"stopping",
				"cancelling",
				"settling",
				"success",
				"partial_success",
				"failed",
				"deactivated",
				"unsupported",
				"interrupted",
				"stopped",
				"cancelled"
			];
			return [...i].filter((t) => !!t && (e !== "status" || a.includes(t) || t === c.value)).map((t) => ({
				value: t,
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? _n(r.column, {
					...r.modelValue,
					[s.value]: t
				}, r.facets) : R(e, t)),
				count: n.get(t)?.count
			}));
		});
		function m(e, t) {
			i("update:modelValue", {
				...r.modelValue,
				[e]: t
			});
		}
		function h(e, t) {
			m(s.value, e), t.detail > 0 && i("done");
		}
		function _() {
			i("update:modelValue", vn(r.column, r.modelValue)), i("done");
		}
		return (t, r) => (n(), M("form", {
			class: "tc-filter-fields",
			onSubmit: r[5] ||= T((e) => i("done"), ["prevent"])
		}, [e.column.kind === "search" ? (n(), M("div", yn, [S("label", { for: `${j(a)}-search` }, b(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, bn), S("input", {
			id: `${j(a)}-search`,
			value: c.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: r[0] ||= (e) => m(s.value, e.target.value)
		}, null, 40, xn)])) : e.column.kind === "select" ? (n(), M("div", {
			key: 1,
			class: "tc-filter-options",
			role: "radiogroup",
			"aria-label": e.column.label
		}, [S("label", { class: E(["tc-filter-option", { "is-selected": !c.value }]) }, [S("input", {
			type: "radio",
			name: j(a),
			value: "",
			checked: !c.value,
			onChange: r[1] ||= (e) => m(s.value, ""),
			onClick: r[2] ||= (e) => h("", e)
		}, null, 40, Cn), S("span", wn, b(l[e.column.group || ""] || "全部"), 1)], 2), (n(!0), M(g, null, o(f.value, (e) => (n(), M("label", {
			key: e.value,
			class: E(["tc-filter-option", { "is-selected": c.value === e.value }])
		}, [
			S("input", {
				type: "radio",
				name: j(a),
				value: e.value,
				checked: c.value === e.value,
				onChange: (t) => m(s.value, e.value),
				onClick: (t) => h(e.value, t)
			}, null, 40, Tn),
			S("span", En, b(e.text), 1),
			e.count == null ? p("", !0) : (n(), M("span", Dn, b(e.count), 1))
		], 2))), 128))], 8, Sn)) : (n(), M("div", On, [
			r[6] ||= S("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			S("div", kn, [S("label", { for: `${j(a)}-from` }, "创建日期起", 8, An), S("input", {
				id: `${j(a)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: r[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, jn)]),
			S("div", Mn, [S("label", { for: `${j(a)}-to` }, "创建日期止", 8, Nn), S("input", {
				id: `${j(a)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: r[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, Pn)])
		])), S("div", Fn, [S("button", {
			type: "button",
			class: "tc-link",
			disabled: !j(gn)(e.column, e.modelValue),
			onClick: _
		}, "清除此列", 8, In), r[7] ||= S("button", {
			type: "submit",
			class: "tc-button"
		}, "完成", -1)])], 32));
	}
}), Rn = { class: "tc-mobile-filters" }, zn = { class: "tc-filter-column-picker" }, Bn = ["value"], Vn = /* @__PURE__ */ t({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = v(hn[0].key), u = D(() => hn.find((e) => e.key === c.value)), d = D(() => hn.filter((e) => gn(e, i.modelValue)).length);
		return (t, i) => (n(), M("div", Rn, [l(Oe, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: e.open,
			"onUpdate:open": i[3] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [S("label", zn, [i[4] ||= N("筛选列", -1), a(S("select", { "onUpdate:modelValue": i[0] ||= (e) => c.value = e }, [(n(!0), M(g, null, o(j(hn), (t) => (n(), M("option", {
				key: t.key,
				value: t.key
			}, b(t.label) + b(j(gn)(t, e.modelValue) ? " · 已筛选" : ""), 9, Bn))), 128))], 512), [[m, c.value]])]), (n(), x(Ln, {
				key: c.value,
				column: u.value,
				"model-value": e.modelValue,
				facets: e.facets,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:modelValue", e),
				onDone: i[2] ||= (e) => s("update:open", !1)
			}, null, 8, [
				"column",
				"model-value",
				"facets"
			]))]),
			_: 1
		}, 8, [
			"trigger-label",
			"active",
			"open"
		])]));
	}
}), Hn = /* @__PURE__ */ t({
	__name: "TaskColumnFilter",
	props: {
		column: {},
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = t;
		return (t, a) => (n(), x(Oe, {
			label: e.column.label,
			active: j(gn)(e.column, e.modelValue),
			summary: j(_n)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": a[2] ||= (e) => i("update:open", e)
		}, {
			default: r(() => [l(Ln, {
				column: e.column,
				"model-value": e.modelValue,
				facets: e.facets,
				"onUpdate:modelValue": a[0] ||= (e) => i("update:modelValue", e),
				onDone: a[1] ||= (e) => i("update:open", !1)
			}, null, 8, [
				"column",
				"model-value",
				"facets"
			])]),
			_: 1
		}, 8, [
			"label",
			"active",
			"summary",
			"open"
		]));
	}
}), Un = /* @__PURE__ */ new Set([
	"failed",
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"password_confirmation_pending"
]), Wn = /* @__PURE__ */ new Set([
	"running",
	"waiting",
	"stopping",
	"cancelling",
	"settling"
]), Gn = /* @__PURE__ */ new Set([
	"cancelled",
	"stopped",
	"interrupted"
]), Kn = {
	email_verification_pending: "待验证或补全",
	credential_pending_confirmation: "凭证待核验"
};
function qn(e, t, n) {
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${R(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function Jn(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function Yn(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: R("status", t),
		tone: G(t),
		title: qn("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = re(e) || void 0) : Wn.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = re(e) || Jn(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : Un.has(t) ? (r.label = "失败", r.tone = "danger") : Gn.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (Un.has(n) && Un.has(t) || n === "completed" && t === "success" || n === "in_progress" && Wn.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: Kn[n] || R("target_status", n),
			tone: G(n),
			title: qn("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Z = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), Xn = (e) => Array.isArray(e) ? e.map(H) : [], Q = (e) => String(e || "").toLowerCase(), $ = /* @__PURE__ */ new Set([
	"unknown",
	"request_unknown",
	"attention_required",
	"manual_reconcile",
	"unconfirmed",
	"password_confirmation_pending",
	"credential_pending_confirmation"
]), Zn = /* @__PURE__ */ new Set([
	"failed",
	"error",
	"deactivated"
]);
function Qn(e) {
	let t = e.error_info;
	if (!t) return !1;
	for (let e of ["cause_code", "code"]) {
		let n = Q(t[e]).trim();
		if (n) {
			if ($.has(n) || ["unknown.unclassified", "task.pending"].includes(n) || /(?:_receipt_missing|_failure_diagnostics_missing|_evidence_missing|_unconfirmed|_request_unknown|\.confirmation|\.safety)$/.test(n)) return !1;
			if (Y({ [e]: n }) !== Y()) return !0;
		}
	}
	return !1;
}
var $n = {
	executor_capacity: "等待执行空位",
	resource_capacity: "等待资源空位",
	global_capacity: "等待全局空位",
	type_capacity: "等待本类空位",
	batch_paused: "等待批次继续",
	batch_capacity: "等待批次空位",
	provider_capacity: "等待平台空位",
	account_busy: "等待账号空闲",
	remote_order_capacity: "等待订单名额",
	not_due: "等待下次查询",
	execution_active: "等待执行退出",
	fairness_turn: "等待调度轮次",
	concurrency_policy_migration_required: "并发配置待迁移",
	scheduler_store_unavailable: "调度存储异常",
	permit_owner_lost: "执行许可变更"
}, er = {
	registration: "注册完成",
	registration_resume: "续注册完成",
	twofa_retry: "验证配置完成",
	account_setup_retry: "账号配置完成",
	password_setup: "密码已补齐",
	password_change: "密码已修改",
	twofa_setup: "双重验证已设",
	twofa_change: "双重验证已改",
	account_completion: "账号已补全",
	email_change: "换绑已完成",
	codex_retry: "授权已完成",
	codex_token_refresh: "令牌刷新完成",
	sub2api_sync: "凭证同步完成",
	sub2api_manual_upload: "凭证上传完成",
	sub2api_scan: "异常扫描完成",
	live_check: "查活完成",
	token_refresh: "刷新完成",
	plan_check: "套餐查询完成",
	deactivation_mail: "邮件检查完成",
	extract_link: "提链流程完成",
	account_inspection: "账号巡检完成",
	account_inspection_batch: "批次巡检完成",
	c2a_session_reimport: "令牌导入完成",
	c2a_scan: "异常扫描完成",
	sentinel_maintenance_check: "维护检查完成"
};
function tr(e, t) {
	let n = H(e.result_summary), r = Q(e.status), i = Q(n.extraction_status), a = Q(n.payment_status);
	return ["succeeded", "success"].includes(i) || !i && n.ok === !0 && n.has_link === !0 ? ["failed", "error"].includes(a) ? Z("提链成功", "danger", "支付失败") : [
		"succeeded",
		"success",
		"paid"
	].includes(a) ? Z("提链成功", "success", "支付成功") : $.has(a) ? Z("提链成功", "warning", "支付待确认") : [
		"pending",
		"pending_payment",
		"processing"
	].includes(a) || n.mode === "manual_payment" && a === "not_started" ? Z("提链成功", "warning", n.mode === "manual_payment" ? "待手动支付" : "支付处理中") : [
		"cancelled",
		"stopped",
		"interrupted"
	].includes(r) ? Z("提链成功", "warning", "后续已中断") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Z("提链成功", "danger", "后续失败") : Z("提链成功", "success") : Zn.has(i) || Qn(e) ? Z(t, "danger") : $.has(i) ? Z("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Z("等待提链", "warning") : i === "running" ? Z("提链中", "active") : r === "cancelled" ? Z("已取消") : ["stopped", "interrupted"].includes(r) ? Z("执行已中断", "warning") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Z(t, "danger") : n.ok === !0 ? Z("提链流程完成", "success") : Z("提链结果缺失", "warning");
}
function nr(e, t) {
	let n = H(e.result_summary), r = Q(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : Xn(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes(Q(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = H(e.result);
		return !t && !e.last_success_at ? [] : Xn(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : Xn(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(H(e.result)).length > 0);
	if (s > 0 && o > 0 || !i && n.plan_check_partial === !0) return Z("部分失败", "warning", u ? "含历史数据" : void 0);
	if (c > 0 && s >= c) return u ? Z("查询失败", "danger", "含历史数据") : Z(t, "danger");
	if (Qn(e)) return Z(t, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("查询待确认", "warning", u ? "含历史数据" : void 0);
	if (e.error_message || e.error_info || r === "failed" || n.ok === !1) return u ? Z("查询失败", "danger", "含历史数据") : Z(t, "danger");
	if (r === "partial_success") return Z("部分完成", "warning", u ? "含历史数据" : void 0);
	if (a.some((e) => ["queued", "running"].includes(Q(e.status)))) return Z("部分仍待查询", "warning");
	if (!Object.keys(n).length) return Z("套餐结果缺失", "warning");
	let d = {
		free: "免费套餐",
		plus: "Plus",
		go: "Go",
		pro: "Pro",
		team: "团队套餐",
		business: "商业套餐",
		enterprise: "企业套餐"
	}[Q(n.current_plan_type || n.plan_type)] || "已查询";
	if (u) return Z(d, "warning", "含历史数据");
	let f = {
		free_trial: 0,
		discount: 1,
		other_promo: 2,
		unknown: 3,
		pending: 4,
		failed: 5,
		cancelled: 5,
		none: 6,
		not_applicable: 7
	}, p = [...l].sort((e, t) => (f[Q(e.kind)] ?? 3) - (f[Q(t.kind)] ?? 3) || Number(t.plan === "plus") - Number(e.plan === "plus"))[0];
	if (p) {
		let e = p.plan === "plus" ? "Plus" : p.plan === "go" ? "Go" : "", t = {
			free_trial: `${e}免费`,
			discount: `${e}折扣`,
			other_promo: "其他优惠",
			none: "无优惠",
			not_applicable: "优惠不适用",
			unknown: "优惠待复查",
			pending: "优惠待查询",
			failed: "优惠查询失败",
			cancelled: "优惠已取消"
		}[Q(p.kind)] || "优惠待复查";
		return Z(d, [
			"unknown",
			"pending",
			"failed",
			"cancelled"
		].includes(Q(p.kind)) ? "warning" : "success", t);
	}
	return n.plus_trial_eligible === !0 || n.plus_promo_kind === "free_trial" ? Z(d, "success", "Plus免费") : n.plus_discount_eligible === !0 || n.plus_promo_kind === "discount" ? Z(d, "success", "Plus折扣") : n.plus_promo_kind === "none" || n.plus_promo_eligible === !1 ? Z(d, "success", "无优惠") : Z(d, "neutral", "优惠待复查");
}
function rr(e, t = "执行异常") {
	let n = H(e.result_summary), r = Q(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
	if (e.debug_pause) return Z("调试已暂停", "warning");
	if (["queued", "pending"].includes(r)) {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z($n[String(t)] || "等待执行", "warning");
	}
	if (r === "waiting") {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z($n[String(t)] || Jn(e), "warning");
	}
	if (r === "running") return Z("执行中", "active");
	if (["stopping", "cancelling"].includes(r)) return Z("正在停止", "warning");
	if (r === "settling") return Z("正在收尾", "active");
	if (i === "extract_link") return tr(e, a);
	if (i === "email_change" && n.email_change_confirmed === !0) return Z("邮箱已换绑", "success", H(n.post_change_live_check).accepted ? "刷新已排队" : "刷新待处理");
	if (i === "codex_retry" && n.ok === !0) {
		let e = Q(H(n.sub2api_sync).status);
		return e === "failed" ? Z("授权成功", "warning", "同步失败") : e === "cancelled" ? Z("授权成功", "warning", "同步已停止") : e === "success" ? Z("授权成功", "success", "同步已完成") : Z("授权成功", "success", n.credential_confirmed === !0 ? "凭证已确认" : void 0);
	}
	if (i === "codex_token_refresh" && n.ok === !0) return Z("令牌已刷新", n.sub2_sync === "failed" ? "warning" : "success", n.sub2_sync === "failed" ? "同步失败" : void 0);
	if (i === "sub2api_manual_upload" && n.uploaded === !0 && (r !== "success" || n.ok === !1)) return Z("上传已完成", "warning", "回写待确认");
	if (i === "sub2api_sync" && n.superseded === !0) return Z("新凭证已接续");
	if (i === "account_inspection") {
		if (n.inspection_outcome === "deactivated_skipped") return Z("已废账号跳过");
		if (n.inspection_outcome === "deleted_skipped") return Z("已删账号跳过");
		if (n.inspection_outcome === "valid") return Z("令牌本地有效", "success");
		if (n.inspection_outcome === "refreshed") return Z("令牌已刷新", n.plan_ok === !1 ? "warning" : "success", n.plan_ok === !1 ? "查套餐失败" : void 0);
	}
	if (i === "plan_check") return nr(e, a);
	if (r === "cancelled") return Z("已取消");
	if (["stopped", "interrupted"].includes(r)) return Z("执行已中断", "warning");
	if (Qn(e)) return Z(a, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes(Q(e.target_status)) || r === "deactivated") return Z("账号已停用", "danger");
	let o = i === "sub2api_scan" || i === "c2a_scan";
	if (e.error_message || e.error_info || Zn.has(r) || !o && n.ok === !1) return Z(a, "danger");
	if (r === "partial_success") return Z("部分完成", "warning");
	if (o) return r === "success" ? Z(i === "c2a_scan" && n.continuation_only === !0 ? "接续检查完成" : er[i], "success") : Z("扫描未完成", "warning");
	if (i === "registration" || i === "registration_resume") {
		let t = {
			account_available: "账号可用",
			email_verification_pending: "邮箱待验证",
			credential_valid: "凭证有效",
			credential_pending_confirmation: "凭证待确认",
			not_created: "账号未创建",
			in_progress: "账号处理中"
		}[Q(e.target_status)];
		if (t) return Z(t, ["account_available", "credential_valid"].includes(Q(e.target_status)) ? "success" : "warning");
	}
	return i === "deactivation_mail" && typeof n.detected == "boolean" ? Z(n.detected ? "发现封号邮件" : "未见封号邮件", n.detected ? "warning" : "neutral") : i === "live_check" && n.ok === !0 ? Z("账号正常", "success") : i === "token_refresh" && n.ok === !0 ? Z("令牌已刷新", "success") : i === "account_inspection_batch" && Number(n.failed_count) > 0 ? Z("巡检已完成", "warning", "存在失败") : r === "success" || n.ok === !0 ? Z(er[i] || "任务已完成", "success") : Z("结果未记录");
}
// src/features/tasks/TaskResultCell.vue
var ir = /* @__PURE__ */ t({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, i = D(() => rr(t.task, Y(t.task.error_info))), a = D(() => [...new Set([
			U(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? V(t.task.error_info, t.task.error_message) : "",
			t.task.error_message,
			t.task.error_code,
			t.task.error_info?.code,
			t.task.error_info?.cause_code
		].filter((e) => !!e))]);
		return (e, t) => (n(), x(je, w(i.value, { title: a.value.join("\n") }), {
			details: r(() => [(n(!0), M(g, null, o(a.value, (e, t) => (n(), M("p", { key: t }, b(e), 1))), 128))]),
			_: 1
		}, 16, ["title"]));
	}
}), ar = ["aria-busy"], or = [
	"checked",
	"indeterminate",
	"disabled"
], sr = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], cr = { "data-label": "选择" }, lr = [
	"checked",
	"aria-label",
	"onChange"
], ur = { "data-label": "ID" }, dr = ["onClick"], fr = { "data-label": "类型" }, pr = { "data-label": "目标" }, mr = { "data-label": "执行状态" }, hr = ["title"], gr = ["title"], _r = { "data-label": "目标状态" }, vr = ["title"], yr = {
	key: 1,
	class: "tc-cell-line",
	"aria-label": "无额外目标状态"
}, br = { "data-label": "批次 / 触发" }, xr = ["onClick"], Sr = { "data-label": "运行次数" }, Cr = { "data-label": "当前步骤" }, wr = {
	"data-label": "创建 / 完成",
	class: "tc-time"
}, Tr = { "data-label": "结果 / 错误" }, Er = { "data-label": "操作" }, Dr = { class: "tc-row-actions" }, Or = ["onClick"], kr = ["disabled", "onClick"], Ar = ["disabled", "onClick"], jr = ["disabled", "onClick"], Mr = {
	key: 0,
	class: "tc-empty-row"
}, Nr = ["colspan"], Pr = ["role"], Fr = {
	key: 0,
	class: "tc-spinner",
	"aria-hidden": "true"
}, Ir = /* @__PURE__ */ t({
	__name: "TaskTable",
	props: {
		items: {},
		selected: {},
		loading: { type: Boolean },
		error: {},
		busy: { type: Boolean },
		filters: { default: Ne },
		facets: { default: () => ({}) },
		openFilter: { default: null }
	},
	emits: [
		"select",
		"selectPage",
		"detail",
		"action",
		"batch",
		"retry",
		"update:filters",
		"update:openFilter"
	],
	setup(e, { expose: t, emit: i }) {
		let a = e, s = i, c = D(() => a.items.length > 0 && a.items.every((e) => a.selected.has(e.id))), u = D(() => !c.value && a.items.some((e) => a.selected.has(e.id))), d = D(() => a.items.map((e) => ({
			task: e,
			...Yn(e)
		}))), f = [
			"选择",
			"ID",
			"类型",
			"目标",
			"执行状态",
			"目标状态",
			"批次 / 触发",
			"运行次数",
			"当前步骤",
			"创建 / 完成",
			"结果 / 错误",
			"操作"
		], { widths: m, resize: v, resizeWithKeyboard: y, resetColumns: C } = Ae({
			defaults: [
				40,
				72,
				118,
				198,
				108,
				112,
				145,
				88,
				128,
				168,
				170,
				145
			],
			storageKey: "turb_task_center_columns",
			min: 65,
			max: 800,
			savedMin: 40
		});
		function w(e) {
			return B(e) || e.current_stage_label || R("stage", e.current_stage);
		}
		function O(e) {
			return [
				e.current_stage_label || R("stage", e.current_stage),
				B(e),
				W(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function k(e) {
			return String(e.bulk_batch_id || H(e.bulk_context).batch_id || "");
		}
		function A(e) {
			return String(e.bulk_round_id || H(e.bulk_context).round_id || "");
		}
		return t({ resetColumns: C }), (t, i) => (n(), M("div", {
			class: "tc-table-scroll",
			tabindex: "0",
			"aria-label": "任务列表，可横向滚动",
			"aria-busy": e.loading
		}, [S("table", {
			class: "tc-table",
			style: _({ "--tc-table-width": `${j(m).reduce((e, t) => e + t, 0)}px` })
		}, [
			i[3] ||= S("caption", { class: "tc-sr-only" }, "任务中心列表，选择任务可批量操作", -1),
			S("colgroup", null, [(n(!0), M(g, null, o(j(m), (e, t) => (n(), M("col", {
				key: t,
				style: _({ width: `${e}px` })
			}, null, 4))), 128))]),
			S("thead", null, [S("tr", null, [(n(), M(g, null, o(f, (t, r) => S("th", {
				key: t,
				scope: "col"
			}, [r === 0 ? (n(), M("input", {
				key: 0,
				type: "checkbox",
				"aria-label": "全选当前页任务",
				checked: c.value,
				indeterminate: u.value,
				disabled: !e.items.length,
				onChange: i[0] ||= (e) => s("selectPage", e.target.checked)
			}, null, 40, or)) : (n(), M(g, { key: 1 }, [j(hn)[r - 1] ? (n(), x(Hn, {
				key: 0,
				column: j(hn)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === j(hn)[r - 1].key,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:filters", e),
				"onUpdate:open": (e) => s("update:openFilter", e ? j(hn)[r - 1].key : null)
			}, null, 8, [
				"column",
				"model-value",
				"facets",
				"open",
				"onUpdate:open"
			])) : (n(), M(g, { key: 1 }, [N(b(t), 1)], 64)), r < f.length - 1 ? (n(), M("button", {
				key: 2,
				type: "button",
				class: "tc-column-resize",
				"aria-label": `调整${t}列宽，方向键调整`,
				onPointerdown: T((e) => j(v)(r, e), ["prevent"]),
				onKeydown: [h(T((e) => j(y)(r, -10), ["prevent"]), ["left"]), h(T((e) => j(y)(r, 10), ["prevent"]), ["right"])]
			}, null, 40, sr)) : p("", !0)], 64))])), 64))])]),
			S("tbody", null, [(n(!0), M(g, null, o(d.value, ({ task: t, execution: i, target: a }) => (n(), M("tr", {
				key: t.id,
				class: E({ "tc-row-selected": e.selected.has(t.id) })
			}, [
				S("td", cr, [S("input", {
					type: "checkbox",
					checked: e.selected.has(t.id),
					"aria-label": `选择任务 #${t.id}`,
					onChange: (e) => s("select", t.id, e.target.checked)
				}, null, 40, lr)]),
				S("td", ur, [S("button", {
					type: "button",
					class: "tc-link tc-task-id",
					onClick: (e) => s("detail", t.id)
				}, "#" + b(t.id), 9, dr)]),
				S("td", fr, [l(De, { text: j(R)("task_type", t.task_type) }, null, 8, ["text"])]),
				S("td", pr, [l(De, {
					text: t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—",
					secondary: t.email_snapshot || t.email || "—"
				}, {
					default: r(() => [S("strong", null, b(t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—"), 1)]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				S("td", mr, [S("span", {
					class: E(["tc-badge", `tc-badge--${i.tone}`]),
					title: i.title
				}, b(i.label), 11, hr), i.secondary ? (n(), M("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: i.secondary
				}, b(i.secondary), 9, gr)) : p("", !0)]),
				S("td", _r, [a ? (n(), M("span", {
					key: 0,
					class: E(["tc-badge", `tc-badge--${a.tone}`]),
					title: a.title
				}, b(a.label), 11, vr)) : (n(), M("span", yr, "—"))]),
				S("td", br, [l(De, {
					text: t.batch_title || t.batch_uuid || (k(t) ? "查看批次" : "单任务"),
					secondary: j(R)("trigger", t.trigger)
				}, {
					default: r(() => [k(t) ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						onClick: (e) => s("batch", k(t), A(t))
					}, b(t.batch_title || t.batch_uuid || "查看批次"), 9, xr)) : (n(), M(g, { key: 1 }, [N(b(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				S("td", Sr, [l(De, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				S("td", Cr, [l(De, {
					text: w(t),
					secondary: j(W)(t.duration_ms),
					title: O(t),
					tone: j(B)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				S("td", wr, [l(De, {
					text: j(Ee)(t.created_at),
					secondary: j(Ee)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				S("td", Tr, [l(ir, { task: t }, null, 8, ["task"])]),
				S("td", Er, [S("div", Dr, [
					S("button", {
						type: "button",
						class: "tc-link",
						onClick: (e) => s("detail", t.id)
					}, "详情", 8, Or),
					j(z)(t) ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						disabled: e.busy,
						onClick: (e) => s("action", t, "retry")
					}, "重跑", 8, kr)) : p("", !0),
					j(Ce)(t) ? (n(), M("button", {
						key: 1,
						type: "button",
						class: "tc-link tc-text-danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "terminate")
					}, b(t.status === "queued" ? "取消" : "终止"), 9, Ar)) : p("", !0),
					j(pe)(t) ? p("", !0) : (n(), M("button", {
						key: 2,
						type: "button",
						class: "tc-link tc-text-danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "delete")
					}, "删除", 8, jr))
				])])
			], 2))), 128)), e.items.length ? p("", !0) : (n(), M("tr", Mr, [S("td", { colspan: f.length }, [S("div", {
				class: "tc-empty",
				role: e.error ? "alert" : "status"
			}, [
				e.loading ? (n(), M("span", Fr)) : p("", !0),
				S("strong", null, b(e.loading ? "正在加载任务记录" : e.error ? "任务列表加载失败" : "没有匹配的任务"), 1),
				S("p", null, b(e.error || (e.loading ? "正在同步任务状态" : "可调整筛选条件，或清除全部筛选。")), 1),
				e.error ? (n(), M("button", {
					key: 1,
					type: "button",
					class: "tc-button",
					onClick: i[2] ||= (e) => s("retry")
				}, "重新加载")) : p("", !0)
			], 8, Pr)], 8, Nr)]))])
		], 4)], 8, ar));
	}
}), Lr = /* @__PURE__ */ t({
	__name: "StatusBadge",
	props: {
		value: {},
		group: { default: "status" }
	},
	setup(e) {
		return (t, r) => (n(), M("span", { class: E(["tc-badge", `tc-badge--${j(G)(e.value)}`]) }, b(j(R)(e.group, e.value)), 3));
	}
});
// src/features/tasks/useTaskList.ts
function Rr() {
	let t = c(Ne()), n = v(1), r = v(20), a = v(0), o = v([]), s = v({}), l = v(/* @__PURE__ */ new Set()), u = v(!1), d = v(""), p = v(!1), m = D(() => Math.max(1, Math.ceil(a.value / r.value))), h = 0, g = null, _, y, b = 0, x = 0, S = "", C = "", w = !1, T = /* @__PURE__ */ new Set([
		"task_id",
		"target",
		"batch",
		"result"
	]), E, O = () => JSON.stringify({ ...t }), k = (e = O()) => w && (S !== e || Date.now() - x >= 3e4);
	function A(t = 0) {
		clearTimeout(y);
		let n = ++b, r = () => {
			n === b && p.value && !document.hidden && M();
		};
		t ? y = setTimeout(r, t) : e(r);
	}
	let j = () => {
		clearTimeout(_), p.value && !document.hidden && (_ = setTimeout(() => void M(), 5e3));
	};
	async function M(e = {}) {
		clearTimeout(_), clearTimeout(y), ++b;
		let i = {
			...t,
			page: n.value,
			page_size: r.value
		}, c = JSON.stringify(i), f = O(), p = !!(e.metadata || k(f)), v = ++h;
		g?.abort(), g = new AbortController(), u.value = !0;
		try {
			let e = await Re.list({
				...i,
				include_facets: +!!p,
				include_batches: 0
			}, g.signal);
			if (v !== h) return;
			if (a.value = Number(e.total || 0), n.value > m.value) {
				n.value = m.value;
				return;
			}
			let t = c + (e.revision || JSON.stringify(e.items));
			if (C !== t) {
				o.value = e.items || [], C = t;
				let n = new Set(o.value.map((e) => e.id));
				l.value = new Set([...l.value].filter((e) => n.has(e)));
			}
			e.facets && (s.value = e.facets), p && (x = Date.now(), S = f), d.value = "";
		} catch (e) {
			v === h && !P(e) && (d.value = e instanceof Error ? e.message : "任务列表加载失败");
		} finally {
			v === h && (u.value = !1, g = null, !p && k() ? A() : j());
		}
	}
	function N(e) {
		e !== p.value && (p.value = e, clearTimeout(_), clearTimeout(y), e && !document.hidden ? A() : (++b, g?.abort(), ++h, u.value = !1));
	}
	function F(e) {
		e !== w && (w = e, !u.value && k() && p.value && !document.hidden && A());
	}
	function I(e, r = !0) {
		Object.assign(t, r ? {
			...Ne(),
			...e
		} : e), n.value = 1, l.value = /* @__PURE__ */ new Set();
	}
	function L(e, t) {
		let n = new Set(l.value);
		t ? n.add(e) : n.delete(e), l.value = n;
	}
	function ee(e) {
		l.value = new Set(e ? o.value.map((e) => e.id) : []);
	}
	i(() => ({
		...t,
		page: n.value,
		page_size: r.value
	}), (e, r) => {
		l.value = /* @__PURE__ */ new Set(), clearTimeout(_);
		let i = Object.keys(t).filter((t) => e[t] !== r[t]);
		if (i.length && (s.value = {}, S = "", E = i.every((e) => T.has(e)) && e.page_size === r.page_size ? 260 : 0, n.value !== 1)) {
			n.value = 1;
			return;
		}
		let a = E ?? 0;
		E = void 0, ++h, g?.abort(), A(a);
	});
	let te = () => {
		clearTimeout(_), document.hidden ? (++b, clearTimeout(y), g?.abort(), ++h, u.value = !1) : p.value && A();
	};
	return document.addEventListener("visibilitychange", te), f(() => {
		++h, ++b, g?.abort(), clearTimeout(_), clearTimeout(y), document.removeEventListener("visibilitychange", te);
	}), {
		filters: t,
		page: n,
		size: r,
		pages: m,
		total: a,
		items: o,
		facets: s,
		selected: l,
		loading: u,
		error: d,
		visible: p,
		refresh: M,
		setVisible: N,
		setFacetsVisible: F,
		applyFilters: I,
		toggle: L,
		togglePage: ee
	};
}
// src/features/tasks/useReceipts.ts
var zr = ({ task_id: e, run_id: t }) => `${e}:${t ?? ""}`;
function Br() {
	let e = v([]), t = v(!1), n = v(!1), r = v(""), i = /* @__PURE__ */ new Set([
		"success",
		"partial_success",
		"failed",
		"cancelled",
		"stopped",
		"interrupted",
		"attention_required",
		"deactivated",
		"unsupported",
		"request_unknown",
		"manual_reconcile"
	]), a = D(() => e.value.filter((e) => !i.has(e.status))), o, s = 0, c = 0, l = null, u = () => {
		clearTimeout(o), t.value && !document.hidden && a.value.length && (o = setTimeout(() => void d(), 2e3));
	};
	async function d() {
		if (n.value || !t.value || document.hidden || !a.value.length) return;
		let e = s % a.value.length, i = [...a.value.slice(e), ...a.value.slice(0, e)].slice(0, 20);
		s = e + i.length;
		let o = ++c;
		l = new AbortController(), n.value = !0, r.value = "";
		try {
			let e = await Re.receipts(i, l.signal);
			if (o !== c) return;
			let t = new Map(e.items.map((e) => [zr(e), e]));
			for (let e of i) {
				let n = t.get(zr(e));
				n ? (e.status = n.status || "queued", e.message = n.message || (n.status === "success" ? "已确认完成" : "")) : r.value = e.run_id === null ? "部分回执暂未读到，请稍后刷新。" : "部分执行记录暂未读到，请稍后刷新。";
			}
		} catch (e) {
			o === c && !P(e) && (r.value = "回执暂未读到，请稍后刷新。");
		} finally {
			o === c && (n.value = !1, l = null, u());
		}
	}
	function p(t, n) {
		for (let i of t) if (i.accepted) try {
			let t = L(i.task_id), r = te(i.run_id), a = zr({
				task_id: t,
				run_id: r
			});
			if (e.value.some((e) => zr(e) === a)) continue;
			e.value.push({
				task_id: t,
				run_id: r,
				label: n,
				status: i.status || "queued",
				message: ""
			});
		} catch {
			r.value = "任务回执标识无效，无法读取原任务。";
		}
		d();
	}
	function m(e) {
		t.value = e, clearTimeout(o), e && !document.hidden ? d() : (++c, l?.abort(), n.value = !1);
	}
	let h = () => m(t.value);
	return document.addEventListener("visibilitychange", h), f(() => {
		++c, l?.abort(), clearTimeout(o), document.removeEventListener("visibilitychange", h);
	}), {
		items: e,
		pending: a,
		error: r,
		loading: n,
		track: p,
		refresh: d,
		setVisible: m
	};
}
// src/features/tasks/TaskCenter.vue?vue&type=script&setup=true&lang.ts
var Vr = {
	class: "tc-root",
	"aria-label": "统一任务中心"
}, Hr = {
	key: 0,
	class: "tc-receipts",
	"aria-label": "本次提交的任务回执"
}, Ur = { class: "tc-receipts-header" }, Wr = { role: "status" }, Gr = ["disabled"], Kr = {
	key: 0,
	class: "tc-text-danger",
	role: "alert"
}, qr = { class: "tc-receipt-list" }, Jr = ["onClick"], Yr = { class: "tc-workspace" }, Xr = { class: "tc-toolbar-main" }, Zr = {
	class: "tc-selection",
	role: "status"
}, Qr = {
	key: 0,
	class: "tc-bulk-actions"
}, $r = ["disabled", "onClick"], ei = { class: "tc-toolbar-end" }, ti = ["title"], ni = ["role"], ri = { key: 1 }, ii = /* @__PURE__ */ t({
	__name: "TaskCenter",
	emits: [
		"navigate",
		"batch",
		"changed"
	],
	setup(t, { expose: r, emit: s }) {
		let c = s, u = Rr(), f = Br(), { filters: m, page: h, size: _, pages: y, total: x, items: C, facets: w, selected: T, loading: O, error: k, visible: P } = u, { items: F, pending: I, error: L, loading: ee } = f, te = v(null), ne = v(null), R = v(!1), z = v(""), B = v(""), V = v(null);
		i(V, (e) => {
			u.setFacetsVisible(e === "mobile" || hn.some((t) => t.key === e && t.kind === "select"));
		});
		let U = D(() => hn.filter((e) => gn(e, m))), W = D(() => U.value.map((e) => ({
			key: e.key,
			label: `${e.label}：${_n(e, m, w.value)}`,
			removeLabel: `清除${e.label}筛选`
		}))), G = v([]), re = D(() => C.value.filter((e) => T.value.has(e.id))), ae = D(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, re.value.filter((t) => ie(t, e)).length]))), oe = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, se = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function ce(e) {
			Object.assign(m, e);
		}
		function le(e) {
			let t = hn.find((t) => t.key === e);
			t && ce(vn(t, m));
		}
		function ue(e, t, n) {
			te.value?.open(e, t, n);
		}
		async function de(t = {}) {
			t.filters && u.applyFilters(t.filters), t.taskId && (await e(), ue(t.taskId, t.runId, t.stepId));
		}
		function fe(e) {
			e || (V.value = null), u.setVisible(e), f.setVisible(e);
		}
		function K() {
			te.value?.close();
		}
		function q(e, t = "任务", n = {}) {
			f.track(e, t), n.navigate !== !1 && c("navigate");
		}
		async function J(e = {}) {
			P.value && await u.refresh(e);
		}
		function me() {
			J(), c("changed");
		}
		async function he(e, t) {
			if (!R.value && !(t === "delete" && pe(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				R.value = !0, B.value = "", G.value = [], z.value = "";
				try {
					let n = await Re.action(e.id, t), r = H(n.data || n);
					z.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", T.value.delete(e.id), await J(), c("changed");
				} catch (e) {
					B.value = `${oe[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					R.value = !1;
				}
			}
		}
		async function ge(e) {
			if (R.value) return;
			let t = re.value.filter((t) => ie(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${oe[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				R.value = !0, B.value = "", z.value = "", G.value = [];
				try {
					let n = await Re.bulk(e, t.map((e) => e.id)), r = Array.isArray(n.accepted) ? n.accepted : [];
					G.value = (n.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let i = Number(n.accepted_count ?? r.length);
					if (e === "cancel") {
						let e = r.filter((e) => e.state === "cancelled").length, t = r.filter((e) => e.state === "cancelling").length;
						z.value = `已取消 ${e} 个，取消中 ${t} 个${i - e - t > 0 ? `，已受理 ${i - e - t} 个` : ""}`;
						let n = new Set(r.map((e) => String(e.task_id)));
						T.value = new Set([...T.value].filter((e) => !n.has(String(e))));
					} else z.value = `已${oe[e]} ${i} 个`, T.value = /* @__PURE__ */ new Set();
					G.value.length && (z.value += `，跳过 ${G.value.length} 个`), await J(), c("changed");
				} catch (t) {
					B.value = `${oe[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					R.value = !1;
				}
			}
		}
		return r({
			open: de,
			refresh: J,
			track: q,
			closeDetail: K,
			setVisible: fe
		}), (e, t) => (n(), M(g, null, [a(S("section", Vr, [j(F).length ? (n(), M("section", Hr, [
			S("div", Ur, [S("div", null, [t[10] ||= S("strong", null, "本次提交", -1), S("span", Wr, "共 " + b(j(F).length) + " 项 · 等待/执行 " + b(j(I).length) + " · 成功 " + b(j(F).filter((e) => e.status === "success").length) + " · 失败或待处理 " + b(j(F).length - j(I).length - j(F).filter((e) => e.status === "success").length), 1)]), S("button", {
				type: "button",
				class: "tc-button",
				disabled: j(ee) || !j(I).length,
				onClick: t[0] ||= (e) => j(f).refresh()
			}, "刷新回执", 8, Gr)]),
			j(L) ? (n(), M("p", Kr, b(j(L)), 1)) : p("", !0),
			S("details", null, [t[11] ||= S("summary", null, "查看任务与最终结果", -1), S("ul", qr, [(n(!0), M(g, null, o(j(F), (e) => (n(), M("li", { key: `${e.task_id}:${e.run_id}` }, [
				S("button", {
					type: "button",
					class: "tc-link",
					onClick: (t) => ue(e.task_id, e.run_id)
				}, b(e.label) + " #" + b(e.task_id), 9, Jr),
				l(Lr, { value: e.status }, null, 8, ["value"]),
				S("span", null, b(e.message), 1)
			]))), 128))])])
		])) : p("", !0), S("div", Yr, [
			S("div", { class: E(["tc-toolbar", { "tc-toolbar--filtered": U.value.length }]) }, [
				S("div", Xr, [S("div", Zr, b(re.value.length ? `已选 ${re.value.length} 项` : `${j(x).toLocaleString()} 个任务`), 1), l(ke, {
					items: W.value,
					onRemove: le
				}, null, 8, ["items"])]),
				re.value.length ? (n(), M("div", Qr, [(n(), M(g, null, o([
					"retry",
					"cancel",
					"terminate",
					"delete"
				], (e) => S("button", {
					key: e,
					type: "button",
					class: E(["tc-button", { "tc-button-danger": e === "delete" || e === "terminate" }]),
					disabled: R.value || !ae.value[e],
					onClick: (t) => ge(e)
				}, b(oe[e]) + b(ae.value[e] ? `（${ae.value[e]}）` : ""), 11, $r)), 64))])) : p("", !0),
				S("div", ei, [
					l(Vn, {
						"model-value": j(m),
						facets: j(w),
						open: V.value === "mobile",
						"onUpdate:modelValue": ce,
						"onUpdate:open": t[1] ||= (e) => V.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					U.value.length ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						onClick: t[2] ||= (e) => j(u).applyFilters({})
					}, "清除全部筛选")) : p("", !0),
					S("span", {
						class: "tc-timezone",
						title: j(se)
					}, "时间按 " + b(j(se)) + " 显示", 9, ti),
					S("button", {
						type: "button",
						class: "tc-link",
						onClick: t[3] ||= (e) => ne.value?.resetColumns()
					}, "恢复列宽")
				])
			], 2),
			z.value || B.value || j(k) && j(C).length ? (n(), M("div", {
				key: 0,
				class: E(["tc-feedback", { "tc-feedback-error": B.value || j(k) }]),
				role: B.value || j(k) ? "alert" : "status"
			}, [
				N(b(B.value || j(k) || z.value), 1),
				j(k) ? (n(), M("button", {
					key: 0,
					type: "button",
					class: "tc-link",
					onClick: t[4] ||= (e) => j(u).refresh()
				}, "重试")) : p("", !0),
				G.value.length ? (n(), M("details", ri, [t[12] ||= S("summary", null, "查看跳过原因", -1), S("ul", null, [(n(!0), M(g, null, o(G.value, (e) => (n(), M("li", { key: e.id }, "#" + b(e.id) + "：" + b(e.message), 1))), 128))])])) : p("", !0)
			], 10, ni)) : p("", !0),
			l(Ir, {
				ref_key: "table",
				ref: ne,
				filters: j(m),
				facets: j(w),
				"open-filter": V.value,
				"onUpdate:openFilter": t[5] ||= (e) => V.value = e,
				"onUpdate:filters": ce,
				items: j(C),
				selected: j(T),
				loading: j(O),
				error: j(k),
				busy: R.value,
				onSelect: j(u).toggle,
				onSelectPage: j(u).togglePage,
				onDetail: ue,
				onAction: he,
				onBatch: t[6] ||= (e, t) => c("batch", e, t),
				onRetry: t[7] ||= (e) => j(u).refresh()
			}, null, 8, [
				"filters",
				"facets",
				"open-filter",
				"items",
				"selected",
				"loading",
				"error",
				"busy",
				"onSelect",
				"onSelectPage"
			]),
			l(Me, {
				page: j(h),
				"onUpdate:page": t[8] ||= (e) => d(h) ? h.value = e : null,
				size: j(_),
				"onUpdate:size": t[9] ||= (e) => d(_) ? _.value = e : null,
				pages: j(y),
				total: j(x),
				busy: j(O)
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy"
			])
		])], 512), [[A, j(P)]]), l(mn, {
			ref_key: "detail",
			ref: te,
			onRefresh: me
		}, null, 512)], 64));
	}
});
// src/main.ts
function ai(e, t = {}) {
	return O(ii, t).mount(e);
}
export { ai as mountTaskCenter };
