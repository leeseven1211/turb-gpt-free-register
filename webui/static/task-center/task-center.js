import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, V as u, X as d, Z as f, _ as p, a as m, d as h, dt as g, et as _, f as v, ft as y, g as b, h as x, j as S, k as C, l as w, lt as T, m as E, n as D, nt as O, s as k, st as A, v as j, x as M } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { n as ee, r as N, t as P } from "./client-B5R_MNgP.js";
import { a as F, i as I, n as L, r as R } from "./taskIds-BlchWwUp.js";
import { a as te, n as z, t as ne } from "./bulkMutations-3wwPI3-H.js";
import { A as B, C as V, D as H, E as U, M as W, N as re, O as ie, P as G, S as ae, T as oe, _ as se, a as K, b as ce, c as q, d as le, f as J, g as Y, h as ue, i as de, j as fe, k as pe, l as me, m as he, n as ge, o as _e, p as ve, r as ye, s as be, t as xe, u as Se, v as Ce, w as we, x as Te, y as Ee } from "./StepEvidence-CTr0jl4E.js";
import { n as De } from "./time-DOD6oyhP.js";
import { i as X, n as Oe, r as ke, t as Ae } from "./ListFilterSummary-C8h8bMwn.js";
import { n as je, t as Me } from "./ColumnResizer-CPJ9UuoZ.js";
import { t as Ne } from "./ListResult-CPVXnLlZ.js";
import { t as Pe } from "./errorLabels-fdGNkTBr.js";
import { t as Fe } from "./ListPagination-DURVj-Kj.js";
import { t as Ie } from "./ListToolbar-DwVj9ZQa.js";
// src/api/tasks.ts
var Le = (e, t = {}) => N(e, t, R);
function Re() {
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
function ze(e) {
	return new URLSearchParams(Object.entries(e).filter(([, e]) => e !== void 0 && e !== "").map(([e, t]) => [e, String(t)])).toString();
}
function Be(e) {
	let t = new URLSearchParams();
	for (let n of e) {
		let e = F(n.task_id), r = L(n.run_id);
		t.append("ref", r === null ? String(e) : `${e}:${r}`);
	}
	return t.toString();
}
async function Ve(e, t, n) {
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
		let e = await Le(t, {
			method: "POST",
			headers: {
				"Idempotency-Key": i,
				...n ? { "Content-Type": "application/json" } : {}
			},
			...n ? { body: He(t, n) } : {}
		});
		return s(), e;
	} catch (e) {
		throw e instanceof P && [
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
function He(e, t) {
	if (e !== "/api/operations/bulk") return JSON.stringify(t);
	let { task_ids: n, ...r } = t;
	if (!Array.isArray(n)) return JSON.stringify(t);
	let i = JSON.stringify(r).slice(0, -1);
	return `${i}${i.length > 1 ? "," : ""}"task_ids":[${n.map((e) => String(F(e))).join(",")}]}`;
}
async function Ue(e, t = {}) {
	let n = await te((t, n) => n?.method === "POST" ? z(t, {
		...n,
		body: He(t, {
			action: "terminate",
			task_ids: e
		})
	}) : z(t, n), "/api/operations/bulk", {
		action: "terminate",
		task_ids: e
	}, t);
	if (!Array.isArray(n.items)) return n;
	let r = n.items.filter((e) => e.status === "updated").map((e) => ({
		task_id: F(e.key),
		state: String(e.data?.state || "stopped"),
		message: String(e.data?.message || "")
	})), i = n.items.filter((e) => e.status !== "updated").map((e) => ({
		task_id: F(e.key),
		error: e.reason || "操作未接受"
	}));
	return {
		...n,
		ok: !0,
		accepted: r,
		accepted_count: r.length,
		skipped: i,
		skipped_count: i.length
	};
}
var We = {
	list: (e, t) => Le(`/api/operations?${ze(e)}`, { signal: t }),
	detail: (e, t) => Le(`/api/operations/${F(e)}?include_events=0`, { signal: t }),
	receipts: (e, t) => Le(`/api/operations/receipts?${Be(e)}`, { signal: t }),
	progress: (e, t, n) => Le(`/api/operations/${F(e)}/runs/${F(t)}/progress`, { signal: n }),
	events: (e, t, n = {}, r) => Le(`/api/operations/${F(e)}/runs/${F(t)}/events?${ze({
		limit: 500,
		...n
	})}`, { signal: r }),
	logs: (e, t, n = {}, r) => Le(`/api/operations/${F(e)}/runs/${F(t)}/logs?${ze({
		limit: 500,
		...n
	})}`, { signal: r }),
	action: (e, t) => t === "retry" ? Ve(`retry:${F(e)}`, `/api/operations/${F(e)}/retry`) : Le(`/api/operations/${F(e)}/${t}`, { method: "POST" }),
	bulk: (e, t, n) => e === "terminate" ? Ue(t, n) : e === "retry" ? Ve("bulk:retry", "/api/operations/bulk", {
		action: e,
		task_ids: t
	}) : Le("/api/operations/bulk", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: He("/api/operations/bulk", {
			action: e,
			task_ids: t
		})
	})
}, Ge = (e) => e instanceof Error ? e.message : "读取失败，请重试";
function Ke(e = We, t = () => {}) {
	let n = _(!1), r = _(!0), i = _(null), a = _(null), o = O(null), s = O(null), c = O([]), l = O([]), u = _("events"), d = _(null), p = _(""), m = _(""), h = _(""), g = _(""), v = _(!1), y = _(!1), b = _(!1), x = _(null), S = _(null), C = _("tail"), w = _("tail"), T = _(!1), D = _(!1), k = _(!1), A = _(!1), j = _(!0), M = E(() => o.value?.runs || []), ee = E(() => M.value.find((e) => I(e.id, a.value))), N = 0, P = 0, R = 0, te = 0, z = null, ne, B = new AbortController(), V = !1;
	function H() {
		ne !== void 0 && clearTimeout(ne), ne = void 0;
	}
	function U() {
		N += 1, B.abort(), B = new AbortController(), z = null, v.value = y.value = b.value = !1, H();
	}
	let W = (e) => e === N && n.value, re = () => n.value && r.value && !!i.value;
	function ie() {
		H(), re() && (!o.value || pe(o.value)) && (ne = setTimeout(() => void ce(!0), 2e3));
	}
	function G() {
		P += 1, R += 1, y.value = b.value = !1, s.value = null, m.value = h.value = g.value = "", c.value = [], l.value = [], x.value = S.value = null, T.value = D.value = k.value = A.value = !1, C.value = w.value = "tail", j.value = !0;
	}
	async function ae(t = "incremental") {
		if (!re() || !a.value || !i.value || t === "incremental" && y.value || t === "incremental" && C.value === "start" && D.value || t === "next" && !D.value) return;
		let n = N, r = ++P, o = t === "tail" || t === "start" || x.value === null, s = {
			limit: 500,
			...t === "start" ? { after_id: 0 } : t !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		y.value = !0;
		try {
			let l = await e.events(i.value, a.value, s, B.signal);
			if (!W(n) || r !== P) return;
			c.value = o ? l.items : J(c.value, l.items), x.value = l.next_after_id, (t === "tail" || t === "start") && (C.value = t), o && C.value === "tail" ? (T.value = l.has_more, D.value = !1) : (D.value = l.has_more, C.value === "start" && (T.value = !1)), h.value = "";
		} catch (e) {
			W(n) && r === P && (h.value = Ge(e));
		} finally {
			W(n) && r === P && (y.value = !1);
		}
	}
	async function oe(t = "incremental") {
		if (!re() || !a.value || !i.value || t === "incremental" && b.value || t === "incremental" && w.value === "start" && A.value || t === "next" && !A.value) return;
		let n = N, r = ++R, o = t === "tail" || t === "start" || S.value === null, s = {
			limit: 500,
			...t === "start" ? { cursor: 0 } : t !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		b.value = !0;
		try {
			let c = await e.logs(i.value, a.value, s, B.signal);
			if (!W(n) || r !== R) return;
			l.value = o ? c.items : [...l.value, ...c.items], S.value = c.next_cursor, (t === "tail" || t === "start") && (w.value = t), A.value = c.has_more, k.value = w.value === "tail" && c.available, j.value = c.available, g.value = "";
		} catch (e) {
			W(n) && r === R && (g.value = Ge(e));
		} finally {
			W(n) && r === R && (b.value = !1);
		}
	}
	async function se(t) {
		if (i.value && a.value) try {
			let n = await e.progress(i.value, a.value, B.signal);
			if (!W(t)) return;
			s.value = n.progress, m.value = "";
		} catch (e) {
			W(t) && (m.value = Ge(e));
		}
	}
	function K() {
		return ce(!1);
	}
	function ce(e) {
		if (!re() || !i.value) return Promise.resolve();
		if (e || (v.value = !0), z) return z;
		let t = N, n = ++te;
		return z = q(t, n).finally(() => {
			W(t) && n === te && (z = null, v.value = !1, ie());
		}), z;
	}
	async function q(n, r) {
		if (i.value) {
			H();
			try {
				let s = await e.detail(i.value, B.signal);
				if (!W(n) || r !== te) return;
				o.value = s.task;
				let c = s.task.runs || [];
				if (a.value && !c.some((e) => I(e.id, a.value))) {
					G(), p.value = `所选运行 #${a.value} 不存在或已不可用，请选择其他运行。`;
					return;
				}
				let l = a.value || s.task.last_run_id || c.at(-1)?.id || null, d = c.some((e) => I(e.id, l)) ? l : c.at(-1)?.id || null;
				if (d !== a.value && (G(), a.value = d), p.value = "", a.value && await Promise.allSettled([
					se(n),
					ae(),
					...u.value === "logs" ? [oe()] : []
				]), !W(n)) return;
				!pe(s.task) && !V && (V = !0, t());
			} catch (e) {
				W(n) && (p.value = Ge(e));
			}
		}
	}
	function le(e, t, r) {
		return U(), n.value = !0, i.value = F(e), a.value = L(t), o.value = null, p.value = "", u.value = "events", d.value = r || null, V = !1, G(), K();
	}
	function Y() {
		n.value = !1, U();
	}
	function ue(e) {
		if (e = F(e), !I(e, a.value)) return U(), a.value = e, d.value = null, G(), K();
	}
	function de(e) {
		if (u.value = e, e === "logs") return oe();
	}
	function fe(e) {
		r.value !== e && (r.value = e, e ? n.value && K() : U());
	}
	return f(Y), {
		opened: n,
		taskId: i,
		runId: a,
		task: o,
		runs: M,
		selectedRun: ee,
		progress: s,
		events: c,
		logs: l,
		tab: u,
		stepFilter: d,
		error: p,
		progressError: m,
		eventsError: h,
		logsError: g,
		loading: v,
		eventsLoading: y,
		logsLoading: b,
		eventsMode: C,
		logsMode: w,
		eventsEarlier: T,
		eventsMore: D,
		logsEarlier: k,
		logsMore: A,
		logsAvailable: j,
		open: le,
		close: Y,
		selectRun: ue,
		selectTab: de,
		setVisible: fe,
		refresh: K,
		loadEvents: ae,
		loadLogs: oe
	};
}
// src/features/tasks/detail/TaskFailure.vue?vue&type=script&setup=true&lang.ts
var qe = {
	key: 0,
	class: "tc-progress-failure tc-task-failure"
}, Je = { key: 0 }, Ye = { key: 1 }, Xe = {
	key: 2,
	class: "tc-failure-secondary"
}, Ze = { key: 3 }, Qe = { key: 0 }, $e = { key: 1 }, et = { key: 2 }, tt = /* @__PURE__ */ t({
	__name: "TaskFailure",
	props: {
		failure: {},
		execution: {},
		status: {}
	},
	setup(e) {
		let t = e, r = E(() => !!(t.execution?.error_message || t.execution?.error_info)), i = E(() => (t.failure?.country_failures || []).filter((e) => Te(e.country).trim())), a = E(() => {
			let e = t.failure;
			return e ? i.value.length && !e.error_info?.auto_refresh_at_failed ? `${i.value.length} 个国家查询失败，展开查看具体原因` : me(e) : "";
		}), s = E(() => {
			let e = t.failure;
			if (!e) return "";
			let n = e.error_info?.stage?.replace(/_result$/, "");
			return n && ![
				"unknown",
				"complete",
				"result",
				"event",
				"queued"
			].includes(n) && n !== e.stage ? B("stage", n) : [e.label || e.step_id || "阶段记录缺失", e.stage].filter(Boolean).join(" · ");
		}), c = E(() => r.value ? U(t.execution?.error_info, t.execution?.error_message) : ""), l = E(() => {
			if (!t.failure || !r.value) return !1;
			let e = (e) => Te(e).replace(/\s+/g, " ").trim(), n = t.failure, i = n.error_info, a = t.execution?.error_info, o = e(n.message), s = e(t.execution?.error_message);
			if (o && s && o !== s) return !1;
			if (i?.cause_summary && a?.cause_summary) return e(i.cause_summary) === e(a.cause_summary);
			if (o && s) return o === s;
			let c = e(i?.cause_summary || i?.summary || n.message);
			return !!c && c === e(a?.cause_summary || a?.summary || t.execution?.error_message);
		}), u = E(() => ({
			...t.failure ? { failure: t.failure } : {},
			...r.value ? { execution: {
				error_message: t.execution?.error_message,
				error_info: t.execution?.error_info
			} } : {}
		}));
		return (t, d) => e.failure || r.value ? (n(), j("details", qe, [
			x("summary", null, [
				e.failure ? (n(), j("strong", Je, y(A(q)(e.failure) ? "历史失败位置" : "失败位置") + "：" + y(s.value), 1)) : (n(), j("strong", Ye, "执行失败")),
				x("span", null, y(a.value || c.value), 1),
				e.failure && r.value && !l.value ? (n(), j("span", Xe, "执行错误：" + y(c.value), 1)) : p("", !0),
				e.execution?.error_info?.display_code ? (n(), j("small", Ze, y(e.execution.error_info.display_code), 1)) : p("", !0)
			]),
			i.value.length ? (n(), j("ul", Qe, [(n(!0), j(h, null, o(i.value, (e, t) => (n(), j("li", { key: t }, y(e.country) + "：" + y(e.summary || "诊断记录不完整"), 1))), 128))])) : p("", !0),
			e.failure?.event_id ? (n(), j("p", $e, "关联事件 " + y(e.failure.event_id), 1)) : p("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(A(Te)(e.status)) ? (n(), j("p", et, "原请求证据已保留")) : p("", !0),
			x("pre", null, y(JSON.stringify(u.value, null, 2)), 1)
		])) : p("", !0);
	}
}), nt = {
	key: 0,
	class: "tc-progress",
	"aria-label": "执行进度"
}, rt = { class: "tc-progress-heading" }, it = { key: 0 }, at = [
	"aria-pressed",
	"title",
	"onClick"
], ot = {
	key: 0,
	class: "tc-step-dot",
	"aria-hidden": "true"
}, st = {
	key: 1,
	class: "tc-step-meta"
}, ct = { key: 0 }, lt = {
	key: 2,
	class: "tc-step-meta"
}, ut = { key: 0 }, dt = ["aria-label", "onClick"], ft = {
	key: 1,
	class: "tc-detail-muted"
}, pt = {
	key: 2,
	class: "tc-flow-relations"
}, mt = { key: 0 }, ht = {
	key: 3,
	class: "tc-child-tasks"
}, gt = ["onClick"], _t = { id: "tc-step-title" }, vt = { class: "tc-step-dialog-body" }, yt = /* @__PURE__ */ t({
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
		let a = t, s = r, c = E(() => a.taskType === "codex_retry"), u = E(() => c.value ? a.progress?.main_steps || [] : K(a.progress?.main_steps)), d = E(() => c.value ? u.value.filter((e) => e.observed_order != null || e.evidence === "run_status") : u.value), f = {
			success: "tc-badge--success",
			recovered: "tc-badge--success",
			failed: "tc-badge--danger",
			running: "tc-badge--active",
			stopped: "tc-badge--warning",
			interrupted: "tc-badge--warning",
			debug_paused: "tc-badge--warning"
		};
		function m(e) {
			let t = ce(e);
			return [
				"success",
				"failed",
				"skipped",
				"running"
			].includes(t) ? ue(t) : de(e);
		}
		let g = _(null), v = E(() => u.value.find((e) => Ce(e) === g.value)), C = _(), D = null, O = E(() => Y(a.progress?.outcome?.child_tasks).flatMap((e) => {
			try {
				return [{
					...e,
					task_id: F(e.task_id),
					run_id: L(e.run_id),
					task_type: e.task_type,
					status: e.status
				}];
			} catch {
				return [];
			}
		})), k = E(() => {
			let e = ve(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${De(Te(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			return t ? `当前：${t.label || t.step_id || "执行中"}${t.child_label ? ` · ${t.child_label}` : ""}` : "执行阶段";
		});
		function ee(e) {
			return [
				Ee(e),
				de(e),
				...ye(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function N(e) {
			return Ce(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function P(t) {
			D = document.activeElement instanceof HTMLElement ? document.activeElement : null, g.value = Ce(t), await e(), C.value?.open || C.value?.showModal();
		}
		function I() {
			C.value?.close(), g.value = null, D?.isConnected && D.focus({ preventScroll: !0 }), D = null;
		}
		function R(e) {
			let t = C.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i(() => [a.context, a.active], I), S(() => C.value?.close()), (e, r) => t.progress ? (n(), j("section", nt, [
			x("div", rt, [x("strong", null, y(k.value), 1), !c.value || t.progress.source !== "explicit" ? (n(), j("small", it, y(t.progress.source === "legacy_derived" ? "历史记录还原" : t.progress.source === "insufficient_evidence" ? "步骤记录缺失" : "按首次记录排列，可含分支与重试"), 1)) : p("", !0)]),
			d.value.length ? (n(), j("ul", {
				key: 0,
				class: T(["tc-progress-track", { "tc-progress-track--codex": c.value }]),
				"aria-label": "执行阶段，排列不代表固定顺序"
			}, [(n(!0), j(h, null, o(d.value, (e) => (n(), j("li", {
				key: A(Ce)(e),
				class: T([
					"tc-step",
					`tc-step--${A(ce)(e)}`,
					{ "tc-step--selected": N(e) }
				])
			}, [x("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": N(e),
				title: ee(e),
				onClick: (t) => s("filter", N(e) ? null : A(Ce)(e))
			}, [
				c.value ? p("", !0) : (n(), j("span", ot)),
				x("strong", null, y(A(Ee)(e)), 1),
				c.value ? (n(), j("span", st, [x("span", { class: T(["tc-badge tc-step-status", f[A(ce)(e)]]) }, y(m(e)), 3), A(ce)(e) !== "skipped" && A(se)(e) != null ? (n(), j("small", ct, y(A(ie)(A(se)(e))), 1)) : p("", !0)])) : (n(), j("span", lt, [
					M(y(A(de)(e)), 1),
					A(se)(e) == null ? p("", !0) : (n(), j("small", ut, " · " + y(A(ie)(A(se)(e))), 1)),
					(n(!0), j(h, null, o(A(ye)(e), (e) => (n(), j("small", { key: e }, " · " + y(e), 1))), 128))
				]))
			], 8, at), x("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${A(Ee)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => P(e)
			}, [...r[2] ||= [x("svg", {
				viewBox: "0 0 16 16",
				width: "14",
				height: "14",
				"aria-hidden": "true"
			}, [x("circle", {
				cx: "8",
				cy: "8",
				r: "5.5",
				fill: "none",
				stroke: "currentColor"
			}), x("path", {
				d: "M8 7v4M8 4.5v1",
				stroke: "currentColor",
				"stroke-width": "1.5"
			})], -1)]], 8, dt)], 2))), 128))], 2)) : (n(), j("p", ft, y(c.value ? "此运行暂无阶段记录。" : "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。"), 1)),
			u.value.length ? (n(), j("details", pt, [
				r[3] ||= x("summary", null, "依赖与执行记录", -1),
				x("p", null, y(t.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1),
				(n(!0), j(h, null, o(u.value, (e) => (n(), j("div", {
					key: A(Ce)(e),
					class: "tc-flow-relation"
				}, [
					x("strong", null, y(A(Ee)(e)), 1),
					c.value ? (n(), j("span", mt, y(m(e)), 1)) : p("", !0),
					l(ge, {
						step: e,
						siblings: u.value
					}, null, 8, ["step", "siblings"])
				]))), 128))
			])) : p("", !0),
			l(tt, {
				failure: t.progress.failure,
				execution: t.execution,
				status: t.progress.outcome.status
			}, null, 8, [
				"failure",
				"execution",
				"status"
			]),
			O.value.length ? (n(), j("div", ht, [r[4] ||= x("strong", null, "独立子任务", -1), (n(!0), j(h, null, o(O.value, (e) => (n(), j("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, y(A(B)("task_type", A(Te)(e.task_type))) + " #" + y(e.task_id) + " · " + y(A(ue)(e.status)), 9, gt))), 128))])) : p("", !0),
			x("dialog", {
				ref_key: "inspector",
				ref: C,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: w(I, ["prevent"]),
				onClose: r[0] ||= (e) => g.value = null,
				onWheel: w(R, ["stop"]),
				onClick: r[1] ||= (e) => {
					e.target === C.value && I();
				}
			}, [x("header", null, [x("h3", _t, y(v.value ? A(Ee)(v.value) : "步骤详情"), 1), x("button", {
				type: "button",
				autofocus: "",
				onClick: I
			}, "关闭")]), x("div", vt, [v.value ? (n(), b(xe, {
				key: 0,
				step: v.value,
				siblings: u.value
			}, null, 8, ["step", "siblings"])) : p("", !0)])], 544)
		])) : p("", !0);
	}
}), bt = { class: "tc-detail-header" }, xt = { id: "tc-detail-title" }, St = { key: 0 }, Ct = ["title"], wt = {
	key: 0,
	class: "tc-detail-status"
}, Tt = {
	key: 1,
	class: "tc-detail-run"
}, Et = ["value", "disabled"], Dt = ["value"], Ot = {
	key: 1,
	value: ""
}, kt = ["value"], At = { class: "tc-detail-header-actions" }, jt = ["disabled"], Mt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Nt = { key: 0 }, Pt = ["disabled"], Ft = {
	key: 1,
	class: "tc-detail-empty",
	role: "status"
}, It = {
	key: 0,
	class: "tc-detail-notice"
}, Lt = {
	key: 1,
	class: "tc-detail-notice"
}, Rt = {
	key: 3,
	class: "tc-detail-error",
	role: "status"
}, zt = { class: "tc-detail-view-toolbar" }, Bt = [
	"id",
	"data-detail-tab",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], Vt = { class: "tc-detail-filter" }, Ht = {
	key: 0,
	class: "tc-detail-read-toolbar"
}, Ut = ["aria-pressed", "disabled"], Wt = ["aria-pressed", "disabled"], Gt = {
	id: "tc-detail-panel-events",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-events",
	tabindex: "0"
}, Kt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, qt = ["disabled"], Jt = {
	key: 1,
	class: "tc-detail-notice"
}, Yt = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, Xt = { class: "tc-event-meta" }, Zt = { key: 0 }, Qt = {
	key: 0,
	class: "tc-technical"
}, $t = ["disabled"], en = {
	id: "tc-detail-panel-logs",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-logs",
	tabindex: "0"
}, tn = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, nn = ["disabled"], rn = {
	key: 1,
	class: "tc-detail-notice"
}, an = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, on = { class: "tc-event-meta" }, sn = {
	key: 0,
	class: "tc-technical"
}, cn = ["disabled"], ln = {
	id: "tc-detail-panel-artifacts",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-artifacts",
	tabindex: "0"
}, un = {
	key: 0,
	class: "tc-artifact"
}, dn = { key: 0 }, fn = { class: "tc-artifact-links" }, pn = ["href"], mn = ["href"], hn = ["href"], gn = {
	key: 1,
	class: "tc-detail-empty"
}, _n = {
	key: 2,
	class: "tc-technical"
}, vn = { class: "tc-detail-footer" }, yn = {
	key: 1,
	role: "status"
}, bn = /* @__PURE__ */ t({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(t, { expose: r, emit: c }) {
		let u = c, d = Ke(void 0, () => u("refresh")), { opened: f, taskId: m, runId: g, task: C, runs: D, selectedRun: O, progress: ee, events: N, logs: P, tab: F, stepFilter: L, error: R, progressError: te, eventsError: z, logsError: ne, loading: V, eventsLoading: H, logsLoading: U, eventsMode: W, logsMode: re, eventsEarlier: G, eventsMore: oe, logsEarlier: se, logsMore: K, logsAvailable: ce } = d, q = _(), J = _(), Y = _(0), de = Intl.DateTimeFormat().resolvedOptions().timeZone, fe = [
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
		], pe = E(() => ee.value?.main_steps || []), me = E(() => pe.value.find((e) => Ce(e) === L.value || !!(L.value && e.raw_stages?.includes(L.value)))), ge = E(() => he(N.value.filter((e) => Se(e, L.value, pe.value)))), ye = E(() => P.value.filter((e) => Se(e, L.value, pe.value, !0))), xe = E(() => ge.value.map((e) => {
			let t = be(e), n = le(e.detail);
			return {
				event: e,
				state: t,
				timestamp: De(e.created_at),
				stageLabel: e.stage_label || B("stage", e.stage),
				association: Pe(e),
				stateLabel: t ? ue(t) : "记录",
				detailJson: n ? JSON.stringify(n, null, 2) : null
			};
		})), we = E(() => ye.value.map((e) => {
			let t = le(e.fields);
			return {
				item: e,
				timestamp: e.ts ? De(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), X = E(() => g.value ? O.value : C.value), Oe = E(() => C.value?.email_snapshot || C.value?.email || (C.value?.account_id ? `账号 #${C.value.account_id}` : C.value?.target_id || "执行记录与诊断")), ke = E(() => (C.value?.resources || []).filter((e) => !g.value || I(e.run_id, g.value))), Ae = E(() => O.value?.debug_artifacts), je = E(() => ve(O.value?.debug_pause || ee.value?.debug_pause)), Me = null, Ne = !1;
		function Pe(e) {
			let t = ve(e.detail), n = Te(e.main_step_id || t.main_step_id), r = Te(e.raw_stage || t.raw_stage || e.stage), i = pe.value.filter((e) => n ? e.id === n : e.raw_stages?.includes(r));
			return i.length === 1 ? Ee(i[0]) : "未关联步骤";
		}
		function Fe() {
			f.value && (d.close(), Me?.isConnected && Me.focus({ preventScroll: !0 }), Me = null, u("close"));
		}
		function Ie() {
			q.value?.close(), Fe();
		}
		async function Le(t, n, r) {
			f.value || (Me = document.activeElement instanceof HTMLElement ? document.activeElement : null), Y.value = 0, d.setVisible(!document.hidden);
			let i = d.open(t, n, r);
			return await e(), !q.value?.open && f.value && q.value?.showModal(), i;
		}
		function Re(e) {
			d.setVisible(e);
		}
		function ze() {
			Re(!document.hidden);
		}
		function Be(e) {
			Y.value = 0, d.selectRun(e.target.value);
		}
		async function Ve(t) {
			Y.value = 0, await d.selectTab(t), await e(), J.value && (J.value.scrollTop = 0);
		}
		function He(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			let t = fe.findIndex((e) => e.id === F.value), n = e.key === "Home" ? 0 : e.key === "End" ? fe.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + fe.length) % fe.length;
			e.preventDefault(), Ve(fe[n].id), e.currentTarget.querySelector(`[data-detail-tab="${fe[n].id}"]`)?.focus();
		}
		async function Ue(t) {
			Ne = !0, F.value === "events" ? await d.loadEvents(t) : await d.loadLogs(t), await e(), J.value && t !== "next" && (J.value.scrollTop = t === "tail" ? J.value.scrollHeight : 0), Y.value = 0, Ne = !1;
		}
		function We() {
			J.value && (J.value.scrollTop = J.value.scrollHeight), Y.value = 0;
		}
		function Ge(e) {
			let t = J.value;
			q.value && q.value.scrollHeight > q.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i([N, P], async ([t, n], [r, i]) => {
			if (Ne) return;
			let a = J.value, o = !a || a.scrollTop + a.clientHeight >= a.scrollHeight - 40, s = F.value === "events" ? t.length - r.length : F.value === "logs" ? n.length - i.length : 0;
			s <= 0 || (await e(), o ? We() : Y.value += s);
		}), i(L, () => {
			Y.value = 0, J.value && (J.value.scrollTop = 0);
		}), s(() => {
			ze(), document.addEventListener("visibilitychange", ze);
		}), S(() => {
			document.removeEventListener("visibilitychange", ze), q.value?.close();
		}), r({
			open: Le,
			close: Ie,
			setVisible: Re
		}), (e, t) => (n(), b(v, { to: "body" }, [x("dialog", {
			ref_key: "dialog",
			ref: q,
			class: "tc-detail-dialog",
			"aria-labelledby": "tc-detail-title",
			onCancel: w(Ie, ["prevent"]),
			onClose: Fe,
			onWheel: Ge
		}, [
			x("header", bt, [
				x("h2", xt, [M("任务 #" + y(A(m)) + " ", 1), A(C) ? (n(), j("span", St, y(A(B)("task_type", A(C).task_type)), 1)) : p("", !0)]),
				x("span", {
					class: "tc-detail-target",
					title: String(Oe.value),
					tabindex: "0"
				}, y(Oe.value), 9, Ct),
				X.value ? (n(), j("div", wt, [x("strong", null, y(A(B)("status", X.value.status)), 1), x("span", null, "耗时 " + y(A(ie)(X.value.duration_ms)), 1)])) : p("", !0),
				A(C) ? (n(), j("label", Tt, [t[10] ||= x("span", null, "运行", -1), x("select", {
					value: A(g) || "",
					"aria-label": "选择执行实例",
					disabled: A(D).length < 2 && (!A(g) || !!A(O)),
					onChange: Be
				}, [A(g) && !A(O) ? (n(), j("option", {
					key: 0,
					value: A(g),
					disabled: ""
				}, "运行 #" + y(A(g)) + " 不可用", 9, Dt)) : A(D).length ? p("", !0) : (n(), j("option", Ot, "暂无运行")), (n(!0), j(h, null, o(A(D), (e) => (n(), j("option", {
					key: e.id,
					value: e.id
				}, "第 " + y(e.run_no || "—") + " 次 · " + y(A(B)("status", e.status)), 9, kt))), 128))], 40, Et)])) : p("", !0),
				x("div", At, [x("button", {
					type: "button",
					disabled: A(V),
					onClick: t[0] ||= (...e) => A(d).refresh && A(d).refresh(...e)
				}, y(A(V) ? "刷新中…" : "刷新"), 9, jt), x("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Ie
				}, "关闭")])
			]),
			A(R) ? (n(), j("div", Mt, [
				M("读取任务失败：" + y(A(R)), 1),
				A(C) ? (n(), j("span", Nt, "。保留上次已读取的记录。")) : p("", !0),
				x("button", {
					type: "button",
					disabled: A(V),
					onClick: t[1] ||= (...e) => A(d).refresh && A(d).refresh(...e)
				}, "重试", 8, Pt)
			])) : p("", !0),
			A(V) && !A(C) ? (n(), j("div", Ft, "正在读取任务详情…")) : p("", !0),
			A(C) ? (n(), j(h, { key: 2 }, [
				X.value?.status === "queued" ? (n(), j("p", It, y(A(ae)(X.value)), 1)) : p("", !0),
				je.value.state === "paused" ? (n(), j("p", Lt, [t[11] ||= M("调试暂停，等待结束调试。", -1), je.value.hold_until ? (n(), j(h, { key: 0 }, [M("保留至 " + y(A(De)(je.value.hold_until)) + "。", 1)], 64)) : p("", !0)])) : p("", !0),
				A(ee) ? p("", !0) : (n(), b(tt, {
					key: 2,
					execution: X.value,
					status: X.value?.status
				}, null, 8, ["execution", "status"])),
				l(yt, {
					progress: A(ee),
					"task-type": A(C)?.task_type,
					execution: X.value,
					filter: A(L),
					active: A(f),
					context: `${A(m)}:${A(g)}`,
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
				A(te) ? (n(), j("p", Rt, [M("进度读取失败：" + y(A(te)), 1), A(ee) ? (n(), j(h, { key: 0 }, [M("；保留上次快照")], 64)) : p("", !0)])) : p("", !0),
				x("div", zt, [
					x("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: He
					}, [(n(), j(h, null, o(fe, (e) => x("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": A(F) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: A(F) === e.id ? 0 : -1,
						onClick: (t) => Ve(e.id)
					}, y(e.label), 9, Bt)), 64))], 32),
					x("div", Vt, [x("span", null, [t[12] ||= M("当前查看：", -1), x("strong", null, y(me.value ? A(Ee)(me.value) : A(L) || "全流程"), 1)]), A(L) ? (n(), j("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => L.value = null
					}, "清除步骤筛选")) : p("", !0)]),
					A(F) === "artifacts" ? p("", !0) : (n(), j("div", Ht, [x("button", {
						type: "button",
						"aria-pressed": (A(F) === "events" ? A(W) : A(re)) === "start",
						disabled: A(H) || A(U) || !A(g),
						onClick: t[4] ||= (e) => Ue("start")
					}, "从头加载", 8, Ut), x("button", {
						type: "button",
						"aria-pressed": (A(F) === "events" ? A(W) : A(re)) === "tail",
						disabled: A(H) || A(U) || !A(g),
						onClick: t[5] ||= (e) => Ue("tail")
					}, "最近记录", 8, Wt)]))
				]),
				x("div", {
					ref_key: "scroller",
					ref: J,
					class: "tc-detail-content"
				}, [
					a(x("section", Gt, [
						A(z) ? (n(), j("p", Kt, [M("事件读取失败：" + y(A(z)), 1), x("button", {
							type: "button",
							disabled: A(H),
							onClick: t[6] ||= (e) => A(d).loadEvents()
						}, "重试", 8, qt)])) : p("", !0),
						A(G) ? (n(), j("p", Jt, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : p("", !0),
						ge.value.length ? p("", !0) : (n(), j("div", Yt, y(A(H) ? "正在读取事件…" : A(L) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(n(!0), j(h, null, o(xe.value, (e) => (n(), j("article", {
							key: e.event.id,
							class: T(["tc-event", { "tc-event--error": e.state === "failed" }])
						}, [
							x("div", Xt, [
								x("time", null, y(e.timestamp), 1),
								x("span", null, y(e.event.level || "INFO"), 1),
								x("strong", null, y(e.stageLabel), 1),
								e.association ? (n(), j("span", Zt, y(e.association), 1)) : p("", !0),
								x("span", null, y(e.stateLabel), 1),
								x("small", null, "事件 " + y(e.event.event_id || e.event.id), 1)
							]),
							x("p", null, y(e.event.message || "—"), 1),
							e.detailJson ? (n(), j("details", Qt, [t[13] ||= x("summary", null, "技术详情", -1), x("pre", null, y(e.detailJson), 1)])) : p("", !0)
						], 2))), 128)),
						A(oe) ? (n(), j("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: A(H),
							onClick: t[7] ||= (e) => Ue("next")
						}, y(A(H) ? "正在读取…" : "继续加载后续事件"), 9, $t)) : p("", !0)
					], 512), [[k, A(F) === "events"]]),
					a(x("section", en, [
						A(ne) ? (n(), j("p", tn, [M("日志读取失败：" + y(A(ne)), 1), x("button", {
							type: "button",
							disabled: A(U),
							onClick: t[8] ||= (e) => A(d).loadLogs()
						}, "重试", 8, nn)])) : p("", !0),
						A(se) ? (n(), j("p", rn, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : p("", !0),
						ye.value.length ? p("", !0) : (n(), j("div", an, y(A(U) ? "正在读取运行日志…" : A(ce) ? A(L) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(n(!0), j(h, null, o(we.value, (e, r) => (n(), j("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${r}`,
							class: "tc-log-line"
						}, [
							x("div", on, [
								x("time", null, y(e.timestamp), 1),
								x("strong", null, y(e.item.level || "INFO"), 1),
								x("span", null, y(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							x("p", null, y(e.item.message), 1),
							e.detailJson ? (n(), j("details", sn, [t[14] ||= x("summary", null, "技术详情", -1), x("pre", null, y(e.detailJson), 1)])) : p("", !0)
						]))), 128)),
						A(K) ? (n(), j("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: A(U),
							onClick: t[9] ||= (e) => Ue("next")
						}, y(A(U) ? "正在读取…" : "继续加载后续日志"), 9, cn)) : p("", !0)
					], 512), [[k, A(F) === "logs"]]),
					a(x("section", ln, [
						Ae.value?.available ? (n(), j("article", un, [
							t[15] ||= x("h3", null, "Roxy 刷新调试", -1),
							x("p", null, y(Ae.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + y(A(ve)(Ae.value.summary).request_count || 0) + " 条", 1),
							A(O)?.result_summary?.debug_browser_kept === !0 ? (n(), j("p", dn, "失败窗口已保留，可在 Roxy 中查看。")) : p("", !0),
							x("div", fn, [
								A(_e)(Ae.value.har_url) ? (n(), j("a", {
									key: 0,
									href: A(_e)(Ae.value.har_url),
									download: ""
								}, "下载 HAR", 8, pn)) : p("", !0),
								A(_e)(Ae.value.page_state_url) ? (n(), j("a", {
									key: 1,
									href: A(_e)(Ae.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, mn)) : p("", !0),
								A(_e)(Ae.value.screenshot_url) ? (n(), j("a", {
									key: 2,
									href: A(_e)(Ae.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, hn)) : p("", !0)
							])
						])) : p("", !0),
						(n(!0), j(h, null, o(ke.value, (e, t) => (n(), j("article", {
							key: A(Te)(e.id) || t,
							class: "tc-artifact"
						}, [
							x("h3", null, y(e.resource_type || "运行资源"), 1),
							x("p", null, y(e.provider || e.state || "—"), 1),
							x("small", null, y(A(De)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!Ae.value?.available && !ke.value.length ? (n(), j("div", gn, "当前 Run 没有诊断资源或产物")) : p("", !0),
						X.value?.result_summary ? (n(), j("details", _n, [t[16] ||= x("summary", null, "执行结果字段", -1), x("pre", null, y(JSON.stringify(X.value.result_summary, null, 2)), 1)])) : p("", !0)
					], 512), [[k, A(F) === "artifacts"]])
				], 512),
				x("footer", vn, [x("small", null, "时间按浏览器时区显示 · " + y(A(de)), 1), Y.value && A(F) !== "artifacts" ? (n(), j("button", {
					key: 0,
					type: "button",
					onClick: We
				}, "有 " + y(Y.value) + " 条新记录，回到底部", 1)) : A(V) || A(H) || A(U) ? (n(), j("small", yn, "正在同步记录…")) : p("", !0)])
			], 64)) : p("", !0)
		], 544)]));
	}
}), xn = [
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
function Sn(e, t) {
	return e.fields.some((e) => !!t[e]);
}
function Cn(e, t, n) {
	if (e.kind === "date-range") {
		let e = t.created_from, n = t.created_to;
		return e && n ? `创建日期 ${e} 至 ${n}` : e ? `创建日期自 ${e}` : n ? `创建日期截至 ${n}` : "";
	}
	let r = t[e.fields[0]];
	if (!r || e.kind !== "select") return r;
	let i = e.group || "", a = n[i] || [];
	return a.find((e) => e.value === r)?.label || r.split(",").map((e) => {
		let t = e.trim();
		return a.find((e) => e.value === t)?.label || B(i, t);
	}).join("、");
}
function wn(e, t) {
	let n = { ...t };
	for (let t of e.fields) n[t] = "";
	return n;
}
// src/features/tasks/TaskFilterFields.vue?vue&type=script&setup=true&lang.ts
var Tn = {
	key: 0,
	class: "tc-filter-field"
}, En = ["for"], Dn = [
	"id",
	"value",
	"inputmode",
	"placeholder"
], On = ["aria-label"], kn = ["name", "checked"], An = { class: "tc-filter-option-label" }, jn = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], Mn = { class: "tc-filter-option-label" }, Nn = {
	key: 0,
	class: "tc-filter-option-count"
}, Pn = {
	key: 2,
	class: "tc-filter-date-range"
}, Fn = { class: "tc-filter-field" }, In = ["for"], Ln = ["id", "value"], Rn = { class: "tc-filter-field" }, zn = ["for"], Bn = ["id", "value"], Vn = { class: "tc-filter-footer" }, Hn = ["disabled"], Un = /* @__PURE__ */ t({
	__name: "TaskFilterFields",
	props: {
		column: {},
		modelValue: {},
		facets: {}
	},
	emits: ["update:modelValue", "done"],
	setup(e, { emit: t }) {
		let r = e, i = t, a = u(), s = E(() => r.column.fields[0]), c = E(() => r.modelValue[s.value]), l = {
			task_type: "全部类型",
			status: "全部状态",
			target_status: "全部目标状态",
			run_count: "全部次数",
			stage: "全部步骤"
		}, d = {
			stopping: "请求停止",
			cancelling: "请求取消"
		}, f = E(() => {
			let e = r.column.group || "", t = r.facets[e] || [], n = new Map(t.map((e) => [e.value, e])), i = /* @__PURE__ */ new Set([
				...Object.keys(fe[e] || {}),
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
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? Cn(r.column, {
					...r.modelValue,
					[s.value]: t
				}, r.facets) : B(e, t)),
				count: n.get(t)?.count
			}));
		});
		function m(e, t) {
			i("update:modelValue", {
				...r.modelValue,
				[e]: t
			});
		}
		function g(e, t) {
			m(s.value, e), t.detail > 0 && i("done");
		}
		function _() {
			i("update:modelValue", wn(r.column, r.modelValue)), i("done");
		}
		return (t, r) => (n(), j("form", {
			class: "tc-filter-fields",
			onSubmit: r[5] ||= w((e) => i("done"), ["prevent"])
		}, [e.column.kind === "search" ? (n(), j("div", Tn, [x("label", { for: `${A(a)}-search` }, y(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, En), x("input", {
			id: `${A(a)}-search`,
			value: c.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: r[0] ||= (e) => m(s.value, e.target.value)
		}, null, 40, Dn)])) : e.column.kind === "select" ? (n(), j("div", {
			key: 1,
			class: "tc-filter-options",
			role: "radiogroup",
			"aria-label": e.column.label
		}, [x("label", { class: T(["tc-filter-option", { "is-selected": !c.value }]) }, [x("input", {
			type: "radio",
			name: A(a),
			value: "",
			checked: !c.value,
			onChange: r[1] ||= (e) => m(s.value, ""),
			onClick: r[2] ||= (e) => g("", e)
		}, null, 40, kn), x("span", An, y(l[e.column.group || ""] || "全部"), 1)], 2), (n(!0), j(h, null, o(f.value, (e) => (n(), j("label", {
			key: e.value,
			class: T(["tc-filter-option", { "is-selected": c.value === e.value }])
		}, [
			x("input", {
				type: "radio",
				name: A(a),
				value: e.value,
				checked: c.value === e.value,
				onChange: (t) => m(s.value, e.value),
				onClick: (t) => g(e.value, t)
			}, null, 40, jn),
			x("span", Mn, y(e.text), 1),
			e.count == null ? p("", !0) : (n(), j("span", Nn, y(e.count), 1))
		], 2))), 128))], 8, On)) : (n(), j("div", Pn, [
			r[6] ||= x("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			x("div", Fn, [x("label", { for: `${A(a)}-from` }, "创建日期起", 8, In), x("input", {
				id: `${A(a)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: r[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, Ln)]),
			x("div", Rn, [x("label", { for: `${A(a)}-to` }, "创建日期止", 8, zn), x("input", {
				id: `${A(a)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: r[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, Bn)])
		])), x("div", Vn, [x("button", {
			type: "button",
			class: "ui-link",
			disabled: !A(Sn)(e.column, e.modelValue),
			onClick: _
		}, "清除此列", 8, Hn), r[7] ||= x("button", {
			type: "submit",
			class: "ui-button"
		}, "完成", -1)])], 32));
	}
}), Wn = { class: "tc-mobile-filters" }, Gn = { class: "tc-filter-column-picker" }, Kn = ["value"], qn = /* @__PURE__ */ t({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = _(xn[0].key), u = E(() => xn.find((e) => e.key === c.value)), d = E(() => xn.filter((e) => Sn(e, i.modelValue)).length);
		return (t, i) => (n(), j("div", Wn, [l(X, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: e.open,
			"onUpdate:open": i[3] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [x("label", Gn, [i[4] ||= M("筛选列", -1), a(x("select", { "onUpdate:modelValue": i[0] ||= (e) => c.value = e }, [(n(!0), j(h, null, o(A(xn), (t) => (n(), j("option", {
				key: t.key,
				value: t.key
			}, y(t.label) + y(A(Sn)(t, e.modelValue) ? " · 已筛选" : ""), 9, Kn))), 128))], 512), [[m, c.value]])]), (n(), b(Un, {
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
}), Jn = /* @__PURE__ */ t({
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
		return (t, a) => (n(), b(X, {
			label: e.column.label,
			active: A(Sn)(e.column, e.modelValue),
			summary: A(Cn)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": a[2] ||= (e) => i("update:open", e)
		}, {
			default: r(() => [l(Un, {
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
}), Yn = /* @__PURE__ */ new Set([
	"failed",
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"password_confirmation_pending"
]), Xn = /* @__PURE__ */ new Set([
	"running",
	"waiting",
	"stopping",
	"cancelling",
	"settling"
]), Zn = /* @__PURE__ */ new Set([
	"cancelled",
	"stopped",
	"interrupted"
]), Qn = {
	email_verification_pending: "待验证或补全",
	credential_pending_confirmation: "凭证待核验"
};
function $n(e, t, n) {
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${B(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function er(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function tr(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: B("status", t),
		tone: G(t),
		title: $n("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = ae(e) || void 0) : Xn.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = ae(e) || er(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : Yn.has(t) ? (r.label = "失败", r.tone = "danger") : Zn.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (Yn.has(n) && Yn.has(t) || n === "completed" && t === "success" || n === "in_progress" && Xn.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: Qn[n] || B("target_status", n),
			tone: G(n),
			title: $n("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Z = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), nr = (e) => Array.isArray(e) ? e.map(W) : [], Q = (e) => String(e || "").toLowerCase(), $ = /* @__PURE__ */ new Set([
	"unknown",
	"request_unknown",
	"attention_required",
	"manual_reconcile",
	"unconfirmed",
	"password_confirmation_pending",
	"credential_pending_confirmation"
]), rr = /* @__PURE__ */ new Set([
	"failed",
	"error",
	"deactivated"
]);
function ir(e) {
	let t = e.error_info;
	if (!t) return !1;
	for (let e of ["cause_code", "code"]) {
		let n = Q(t[e]).trim();
		if (n) {
			if ($.has(n) || ["unknown.unclassified", "task.pending"].includes(n) || /(?:_receipt_missing|_failure_diagnostics_missing|_evidence_missing|_unconfirmed|_request_unknown|\.confirmation|\.safety)$/.test(n)) return !1;
			if (Pe({ [e]: n }) !== Pe()) return !0;
		}
	}
	return !1;
}
var ar = {
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
}, or = {
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
	sentinel_maintenance_check: "维护检查完成",
	bulk_mutation: "批量操作完成",
	task_terminate_bulk: "批量终止完成"
};
function sr(e, t) {
	let n = W(e.result_summary), r = Q(e.status), i = Q(n.extraction_status), a = Q(n.payment_status);
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
	].includes(r) ? Z("提链成功", "warning", "后续已中断") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Z("提链成功", "danger", "后续失败") : Z("提链成功", "success") : rr.has(i) || ir(e) ? Z(t, "danger") : $.has(i) ? Z("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Z("等待提链", "warning") : i === "running" ? Z("提链中", "active") : r === "cancelled" ? Z("已取消") : ["stopped", "interrupted"].includes(r) ? Z("执行已中断", "warning") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Z(t, "danger") : n.ok === !0 ? Z("提链流程完成", "success") : Z("提链结果缺失", "warning");
}
function cr(e, t) {
	let n = W(e.result_summary), r = Q(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : nr(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes(Q(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = W(e.result);
		return !t && !e.last_success_at ? [] : nr(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : nr(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(W(e.result)).length > 0);
	if (s > 0 && o > 0 || !i && n.plan_check_partial === !0) return Z("部分失败", "warning", u ? "含历史数据" : void 0);
	if (c > 0 && s >= c) return u ? Z("查询失败", "danger", "含历史数据") : Z(t, "danger");
	if (ir(e)) return Z(t, "danger");
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
function lr(e, t = "执行异常") {
	let n = W(e.result_summary), r = Q(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
	if (e.debug_pause) return Z("调试已暂停", "warning");
	if (["queued", "pending"].includes(r)) {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(ar[String(t)] || "等待执行", "warning");
	}
	if (r === "waiting") {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(ar[String(t)] || er(e), "warning");
	}
	if (r === "running") return Z("执行中", "active");
	if (["stopping", "cancelling"].includes(r)) return Z("正在停止", "warning");
	if (r === "settling") return Z("正在收尾", "active");
	if (i === "extract_link") return sr(e, a);
	if (i === "email_change" && n.email_change_confirmed === !0) return Z("邮箱已换绑", "success", W(n.post_change_live_check).accepted ? "刷新已排队" : "刷新待处理");
	if (i === "codex_retry" && n.ok === !0) {
		let e = Q(W(n.sub2api_sync).status);
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
	if (i === "plan_check") return cr(e, a);
	if (r === "cancelled") return Z("已取消");
	if (["stopped", "interrupted"].includes(r)) return Z("执行已中断", "warning");
	if (ir(e)) return Z(a, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes(Q(e.target_status)) || r === "deactivated") return Z("账号已停用", "danger");
	let o = i === "sub2api_scan" || i === "c2a_scan";
	if (e.error_message || e.error_info || rr.has(r) || !o && n.ok === !1) return Z(a, "danger");
	if (r === "partial_success") return Z("部分完成", "warning");
	if (o) return r === "success" ? Z(i === "c2a_scan" && n.continuation_only === !0 ? "接续检查完成" : or[i], "success") : Z("扫描未完成", "warning");
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
	return i === "deactivation_mail" && typeof n.detected == "boolean" ? Z(n.detected ? "发现封号邮件" : "未见封号邮件", n.detected ? "warning" : "neutral") : i === "live_check" && n.ok === !0 ? Z("账号正常", "success") : i === "token_refresh" && n.ok === !0 ? Z("令牌已刷新", "success") : i === "account_inspection_batch" && Number(n.failed_count) > 0 ? Z("巡检已完成", "warning", "存在失败") : r === "success" || n.ok === !0 ? Z(or[i] || "任务已完成", "success") : Z("结果未记录");
}
// src/features/tasks/TaskResultCell.vue
var ur = /* @__PURE__ */ t({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, i = E(() => lr(t.task, Pe(t.task.error_info))), a = E(() => [...new Set([
			re(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? U(t.task.error_info, t.task.error_message) : "",
			t.task.error_message,
			t.task.error_code,
			t.task.error_info?.code,
			t.task.error_info?.cause_code
		].filter((e) => !!e))]);
		return (e, t) => (n(), b(Ne, C(i.value, { title: a.value.join("\n") }), {
			details: r(() => [(n(!0), j(h, null, o(a.value, (e, t) => (n(), j("p", { key: t }, y(e), 1))), 128))]),
			_: 1
		}, 16, ["title"]));
	}
}), dr = ["aria-busy"], fr = [
	"checked",
	"indeterminate",
	"disabled"
], pr = {
	"data-label": "选择",
	class: "ui-col-check"
}, mr = [
	"checked",
	"aria-label",
	"onChange"
], hr = { "data-label": "ID" }, gr = ["onClick"], _r = { "data-label": "类型" }, vr = { "data-label": "目标" }, yr = { "data-label": "执行状态" }, br = ["title"], xr = ["title"], Sr = { "data-label": "目标状态" }, Cr = ["title"], wr = {
	key: 1,
	class: "tc-cell-line",
	"aria-label": "无额外目标状态"
}, Tr = { "data-label": "批次 / 触发" }, Er = ["onClick"], Dr = { "data-label": "运行次数" }, Or = { "data-label": "当前步骤" }, kr = {
	"data-label": "创建 / 完成",
	class: "ui-time"
}, Ar = { "data-label": "结果 / 错误" }, jr = { "data-label": "操作" }, Mr = { class: "ui-row-actions tc-row-actions" }, Nr = ["onClick"], Pr = ["disabled", "onClick"], Fr = ["disabled", "onClick"], Ir = ["disabled", "onClick"], Lr = /* @__PURE__ */ t({
	__name: "TaskTable",
	props: {
		items: {},
		selected: {},
		loading: { type: Boolean },
		error: {},
		busy: { type: Boolean },
		filters: { default: Re },
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
		let a = e, s = i, c = E(() => a.items.length > 0 && a.items.every((e) => a.selected.has(e.id))), u = E(() => !c.value && a.items.some((e) => a.selected.has(e.id))), d = E(() => a.items.map((e) => ({
			task: e,
			...tr(e)
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
		], { widths: m, resize: _, resizeWithKeyboard: v, resetColumns: S } = je({
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
		function C(e) {
			return H(e) || e.current_stage_label || B("stage", e.current_stage);
		}
		function w(e) {
			return [
				e.current_stage_label || B("stage", e.current_stage),
				H(e),
				ie(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function D(e) {
			return String(e.bulk_batch_id || W(e.bulk_context).batch_id || "");
		}
		function O(e) {
			return String(e.bulk_round_id || W(e.bulk_context).round_id || "");
		}
		return t({ resetColumns: S }), (t, i) => (n(), j("div", {
			class: "ui-table-scroll tc-table-scroll",
			tabindex: "0",
			"aria-label": "任务列表，可横向滚动",
			"aria-busy": e.loading
		}, [x("table", {
			class: "ui-table ui-table--sticky-end ui-table--cards tc-table",
			style: g({ "--ui-table-width": `${A(m).reduce((e, t) => e + t, 0)}px` })
		}, [
			i[3] ||= x("caption", { class: "ui-sr-only" }, "任务中心列表，选择任务可批量操作", -1),
			x("colgroup", null, [(n(!0), j(h, null, o(A(m), (e, t) => (n(), j("col", {
				key: t,
				style: g({ width: `${e}px` })
			}, null, 4))), 128))]),
			x("thead", null, [x("tr", null, [(n(), j(h, null, o(f, (t, r) => x("th", {
				key: t,
				scope: "col",
				class: T({ "ui-col-check": r === 0 })
			}, [r === 0 ? (n(), j("input", {
				key: 0,
				type: "checkbox",
				"aria-label": "全选当前页任务",
				checked: c.value,
				indeterminate: u.value,
				disabled: !e.items.length,
				onChange: i[0] ||= (e) => s("selectPage", e.target.checked)
			}, null, 40, fr)) : (n(), j(h, { key: 1 }, [A(xn)[r - 1] ? (n(), b(Jn, {
				key: 0,
				column: A(xn)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === A(xn)[r - 1].key,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:filters", e),
				"onUpdate:open": (e) => s("update:openFilter", e ? A(xn)[r - 1].key : null)
			}, null, 8, [
				"column",
				"model-value",
				"facets",
				"open",
				"onUpdate:open"
			])) : (n(), j(h, { key: 1 }, [M(y(t), 1)], 64)), r < f.length - 1 ? (n(), b(Me, {
				key: 2,
				label: t,
				onStart: (e) => A(_)(r, e),
				onNudge: (e) => A(v)(r, e)
			}, null, 8, [
				"label",
				"onStart",
				"onNudge"
			])) : p("", !0)], 64))], 2)), 64))])]),
			x("tbody", null, [(n(!0), j(h, null, o(d.value, ({ task: t, execution: i, target: a }) => (n(), j("tr", {
				key: t.id,
				class: T({ "is-selected": e.selected.has(t.id) })
			}, [
				x("td", pr, [x("input", {
					type: "checkbox",
					checked: e.selected.has(t.id),
					"aria-label": `选择任务 #${t.id}`,
					onChange: (e) => s("select", t.id, e.target.checked)
				}, null, 40, mr)]),
				x("td", hr, [x("button", {
					type: "button",
					class: "ui-link tc-task-id",
					onClick: (e) => s("detail", t.id)
				}, "#" + y(t.id), 9, gr)]),
				x("td", _r, [l(ke, { text: A(B)("task_type", t.task_type) }, null, 8, ["text"])]),
				x("td", vr, [l(ke, {
					text: t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—",
					secondary: t.email_snapshot || t.email || "—"
				}, {
					default: r(() => [x("strong", null, y(t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—"), 1)]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				x("td", yr, [x("span", {
					class: T(["ui-badge tc-badge", `ui-badge--${i.tone}`]),
					title: i.title
				}, y(i.label), 11, br), i.secondary ? (n(), j("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: i.secondary
				}, y(i.secondary), 9, xr)) : p("", !0)]),
				x("td", Sr, [a ? (n(), j("span", {
					key: 0,
					class: T(["ui-badge tc-badge", `ui-badge--${a.tone}`]),
					title: a.title
				}, y(a.label), 11, Cr)) : (n(), j("span", wr, "—"))]),
				x("td", Tr, [l(ke, {
					text: t.batch_title || t.batch_uuid || (D(t) ? "查看批次" : "单任务"),
					secondary: A(B)("trigger", t.trigger)
				}, {
					default: r(() => [D(t) ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: (e) => s("batch", D(t), O(t))
					}, y(t.batch_title || t.batch_uuid || "查看批次"), 9, Er)) : (n(), j(h, { key: 1 }, [M(y(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				x("td", Dr, [l(ke, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				x("td", Or, [l(ke, {
					text: C(t),
					secondary: A(ie)(t.duration_ms),
					title: w(t),
					tone: A(H)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				x("td", kr, [l(ke, {
					text: A(De)(t.created_at),
					secondary: A(De)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				x("td", Ar, [l(ur, { task: t }, null, 8, ["task"])]),
				x("td", jr, [x("div", Mr, [
					x("button", {
						type: "button",
						class: "ui-link",
						onClick: (e) => s("detail", t.id)
					}, "详情", 8, Nr),
					A(V)(t) ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						disabled: e.busy,
						onClick: (e) => s("action", t, "retry")
					}, "重跑", 8, Pr)) : p("", !0),
					A(we)(t) ? (n(), j("button", {
						key: 1,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "terminate")
					}, y(t.status === "queued" ? "取消" : "终止"), 9, Fr)) : p("", !0),
					A(pe)(t) ? p("", !0) : (n(), j("button", {
						key: 2,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "delete")
					}, "删除", 8, Ir))
				])])
			], 2))), 128)), e.items.length ? p("", !0) : (n(), b(Oe, {
				key: 0,
				colspan: f.length,
				loading: e.loading,
				error: e.error,
				"loading-title": "正在加载任务记录",
				"loading-text": "正在同步任务状态",
				"error-title": "任务列表加载失败",
				title: "没有匹配的任务",
				text: "可调整筛选条件，或清除全部筛选。",
				"retry-label": "重新加载",
				onRetry: i[2] ||= (e) => s("retry")
			}, null, 8, [
				"colspan",
				"loading",
				"error"
			]))])
		], 4)], 8, dr));
	}
}), Rr = /* @__PURE__ */ t({
	__name: "StatusBadge",
	props: {
		value: {},
		group: { default: "status" }
	},
	setup(e) {
		return (t, r) => (n(), j("span", { class: T(["ui-badge tc-badge", `ui-badge--${A(G)(e.value)}`]) }, y(A(B)(e.group, e.value)), 3));
	}
});
// src/features/tasks/useTaskList.ts
function zr() {
	let t = c(Re()), n = _(1), r = _(20), a = _(0), o = _([]), s = _({}), l = _(/* @__PURE__ */ new Set()), u = _(!1), d = _(""), p = _(!1), m = E(() => Math.max(1, Math.ceil(a.value / r.value))), h = 0, g = null, v, y, b = 0, x = 0, S = "", C = "", w = !1, T = /* @__PURE__ */ new Set([
		"task_id",
		"target",
		"batch",
		"result"
	]), D, O = () => JSON.stringify({ ...t }), k = (e = O()) => w && (S !== e || Date.now() - x >= 3e4);
	function A(t = 0) {
		clearTimeout(y);
		let n = ++b, r = () => {
			n === b && p.value && !document.hidden && M();
		};
		t ? y = setTimeout(r, t) : e(r);
	}
	let j = () => {
		clearTimeout(v), p.value && !document.hidden && (v = setTimeout(() => void M(), 5e3));
	};
	async function M(e = {}) {
		clearTimeout(v), clearTimeout(y), ++b;
		let i = {
			...t,
			page: n.value,
			page_size: r.value
		}, c = JSON.stringify(i), f = O(), p = !!(e.metadata || k(f)), _ = ++h;
		g?.abort(), g = new AbortController(), u.value = !0;
		try {
			let e = await We.list({
				...i,
				include_facets: +!!p,
				include_batches: 0
			}, g.signal);
			if (_ !== h) return;
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
			_ === h && !ee(e) && (d.value = e instanceof Error ? e.message : "任务列表加载失败");
		} finally {
			_ === h && (u.value = !1, g = null, !p && k() ? A() : j());
		}
	}
	function N(e) {
		e !== p.value && (p.value = e, clearTimeout(v), clearTimeout(y), e && !document.hidden ? A() : (++b, g?.abort(), ++h, u.value = !1));
	}
	function P(e) {
		e !== w && (w = e, !u.value && k() && p.value && !document.hidden && A());
	}
	function F(e, r = !0) {
		Object.assign(t, r ? {
			...Re(),
			...e
		} : e), n.value = 1, l.value = /* @__PURE__ */ new Set();
	}
	function I(e, t) {
		let n = new Set(l.value);
		t ? n.add(e) : n.delete(e), l.value = n;
	}
	function L(e) {
		l.value = new Set(e ? o.value.map((e) => e.id) : []);
	}
	i(() => ({
		...t,
		page: n.value,
		page_size: r.value
	}), (e, r) => {
		l.value = /* @__PURE__ */ new Set(), clearTimeout(v);
		let i = Object.keys(t).filter((t) => e[t] !== r[t]);
		if (i.length && (s.value = {}, S = "", D = i.every((e) => T.has(e)) && e.page_size === r.page_size ? 260 : 0, n.value !== 1)) {
			n.value = 1;
			return;
		}
		let a = D ?? 0;
		D = void 0, ++h, g?.abort(), A(a);
	});
	let R = () => {
		clearTimeout(v), document.hidden ? (++b, clearTimeout(y), g?.abort(), ++h, u.value = !1) : p.value && A();
	};
	return document.addEventListener("visibilitychange", R), f(() => {
		++h, ++b, g?.abort(), clearTimeout(v), clearTimeout(y), document.removeEventListener("visibilitychange", R);
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
		setFacetsVisible: P,
		applyFilters: F,
		toggle: I,
		togglePage: L
	};
}
// src/features/tasks/useReceipts.ts
var Br = ({ task_id: e, run_id: t }) => `${e}:${t ?? ""}`;
function Vr() {
	let e = _([]), t = _(!1), n = _(!1), r = _(""), i = /* @__PURE__ */ new Set([
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
	]), a = E(() => e.value.filter((e) => !i.has(e.status))), o, s = 0, c = 0, l = null, u = () => {
		clearTimeout(o), t.value && !document.hidden && a.value.length && (o = setTimeout(() => void d(), 2e3));
	};
	async function d() {
		if (n.value || !t.value || document.hidden || !a.value.length) return;
		let e = s % a.value.length, i = [...a.value.slice(e), ...a.value.slice(0, e)].slice(0, 20);
		s = e + i.length;
		let o = ++c;
		l = new AbortController(), n.value = !0, r.value = "";
		try {
			let e = await We.receipts(i, l.signal);
			if (o !== c) return;
			let t = new Map(e.items.map((e) => [Br(e), e]));
			for (let e of i) {
				let n = t.get(Br(e));
				n ? (e.status = n.status || "queued", e.message = n.message || (n.status === "success" ? "已确认完成" : "")) : r.value = e.run_id === null ? "部分回执暂未读到，请稍后刷新。" : "部分执行记录暂未读到，请稍后刷新。";
			}
		} catch (e) {
			o === c && !ee(e) && (r.value = "回执暂未读到，请稍后刷新。");
		} finally {
			o === c && (n.value = !1, l = null, u());
		}
	}
	function p(t, n) {
		for (let i of t) if (i.accepted) try {
			let t = F(i.task_id), r = L(i.run_id), a = Br({
				task_id: t,
				run_id: r
			});
			if (e.value.some((e) => Br(e) === a)) continue;
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
var Hr = {
	class: "tc-root",
	"aria-label": "统一任务中心"
}, Ur = {
	key: 0,
	class: "tc-receipts",
	"aria-label": "本次提交的任务回执"
}, Wr = { class: "tc-receipts-header" }, Gr = { role: "status" }, Kr = ["disabled"], qr = {
	key: 0,
	class: "tc-text-danger",
	role: "alert"
}, Jr = { class: "tc-receipt-list" }, Yr = ["onClick"], Xr = { class: "ui-list tc-workspace" }, Zr = {
	class: "ui-list-count tc-selection",
	role: "status"
}, Qr = ["title"], $r = {
	key: 0,
	class: "ui-list-bulkbar tc-bulk-actions",
	role: "group",
	"aria-label": "选中任务批量操作"
}, ei = ["disabled", "onClick"], ti = ["role"], ni = { key: 1 }, ri = /* @__PURE__ */ t({
	__name: "TaskCenter",
	emits: [
		"navigate",
		"batch",
		"changed"
	],
	setup(t, { expose: s, emit: c }) {
		let u = c, f = zr(), m = Vr(), { filters: g, page: v, size: b, pages: S, total: C, items: w, facets: D, selected: O, loading: ee, error: N, visible: P } = f, { items: F, pending: I, error: L, loading: R } = m, te = _(null), z = _(null), B = _(!1), V = _(""), H = _(""), U = _(null);
		i(U, (e) => {
			f.setFacetsVisible(e === "mobile" || xn.some((t) => t.key === e && t.kind === "select"));
		});
		let re = E(() => xn.filter((e) => Sn(e, g))), ie = E(() => re.value.map((e) => ({
			key: e.key,
			label: `${e.label}：${Cn(e, g, D.value)}`,
			removeLabel: `清除${e.label}筛选`
		}))), G = _([]), ae = E(() => w.value.filter((e) => O.value.has(e.id))), se = E(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, ae.value.filter((t) => oe(t, e)).length]))), K = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, ce = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function q(e) {
			Object.assign(g, e);
		}
		function le(e) {
			let t = xn.find((t) => t.key === e);
			t && q(wn(t, g));
		}
		function J(e, t, n) {
			te.value?.open(e, t, n);
		}
		async function Y(t = {}) {
			t.filters && f.applyFilters(t.filters), t.taskId && (await e(), J(t.taskId, t.runId, t.stepId));
		}
		function ue(e) {
			e || (U.value = null), f.setVisible(e), m.setVisible(e);
		}
		function de() {
			te.value?.close();
		}
		function fe(e, t = "任务", n = {}) {
			m.track(e, t), n.navigate !== !1 && u("navigate");
		}
		async function me(e = {}) {
			P.value && await f.refresh(e);
		}
		function he() {
			me(), u("changed");
		}
		async function ge(e, t) {
			if (!B.value && !(t === "delete" && pe(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				B.value = !0, H.value = "", G.value = [], V.value = "";
				try {
					let n = await We.action(e.id, t), r = W(n.data || n);
					V.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", O.value.delete(e.id), await me(), u("changed");
				} catch (e) {
					H.value = `${K[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					B.value = !1;
				}
			}
		}
		async function _e(e) {
			if (B.value) return;
			let t = ae.value.filter((t) => oe(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${K[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				B.value = !0, H.value = "", V.value = "", G.value = [];
				try {
					let n = t.map((e) => e.id), r = e === "terminate" ? await We.bulk(e, n, { onAccepted: (e) => {
						V.value = `终止请求已受理，正在等待结果（命令 ${e.command_id}）`;
					} }) : await We.bulk(e, n), i = Array.isArray(r.accepted) ? r.accepted : [];
					G.value = (r.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let a = Number(r.accepted_count ?? i.length);
					if (e === "cancel") {
						let e = i.filter((e) => e.state === "cancelled").length, t = i.filter((e) => e.state === "cancelling").length;
						V.value = `已取消 ${e} 个，取消中 ${t} 个${a - e - t > 0 ? `，已受理 ${a - e - t} 个` : ""}`;
					} else V.value = `已${K[e]} ${a} 个`;
					let o = new Set(i.map((e) => String(e.task_id)));
					O.value = new Set([...O.value].filter((e) => !o.has(String(e)))), G.value.length && (V.value += `，跳过 ${G.value.length} 个`), await me(), u("changed");
				} catch (t) {
					H.value = t instanceof ne ? t.message : `${K[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					B.value = !1;
				}
			}
		}
		return s({
			open: Y,
			refresh: me,
			track: fe,
			closeDetail: de,
			setVisible: ue
		}), (e, t) => (n(), j(h, null, [a(x("section", Hr, [A(F).length ? (n(), j("section", Ur, [
			x("div", Wr, [x("div", null, [t[10] ||= x("strong", null, "本次提交", -1), x("span", Gr, "共 " + y(A(F).length) + " 项 · 等待/执行 " + y(A(I).length) + " · 成功 " + y(A(F).filter((e) => e.status === "success").length) + " · 失败或待处理 " + y(A(F).length - A(I).length - A(F).filter((e) => e.status === "success").length), 1)]), x("button", {
				type: "button",
				class: "ui-button",
				disabled: A(R) || !A(I).length,
				onClick: t[0] ||= (e) => A(m).refresh()
			}, "刷新回执", 8, Kr)]),
			A(L) ? (n(), j("p", qr, y(A(L)), 1)) : p("", !0),
			x("details", null, [t[11] ||= x("summary", null, "查看任务与最终结果", -1), x("ul", Jr, [(n(!0), j(h, null, o(A(F), (e) => (n(), j("li", { key: `${e.task_id}:${e.run_id}` }, [
				x("button", {
					type: "button",
					class: "ui-link",
					onClick: (t) => J(e.task_id, e.run_id)
				}, y(e.label) + " #" + y(e.task_id), 9, Yr),
				l(Rr, { value: e.status }, null, 8, ["value"]),
				x("span", null, y(e.message), 1)
			]))), 128))])])
		])) : p("", !0), x("div", Xr, [
			l(Ie, { filtered: re.value.length > 0 }, {
				actions: r(() => [
					l(qn, {
						"model-value": A(g),
						facets: A(D),
						open: U.value === "mobile",
						"onUpdate:modelValue": q,
						"onUpdate:open": t[1] ||= (e) => U.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					re.value.length ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: t[2] ||= (e) => A(f).applyFilters({})
					}, "清除全部筛选")) : p("", !0),
					x("span", {
						class: "tc-timezone",
						title: A(ce)
					}, "时间按 " + y(A(ce)) + " 显示", 9, Qr),
					x("button", {
						type: "button",
						class: "ui-link",
						onClick: t[3] ||= (e) => z.value?.resetColumns()
					}, "恢复列宽")
				]),
				default: r(() => [x("div", Zr, y(ae.value.length ? `已选 ${ae.value.length} 项` : `${A(C).toLocaleString()} 个任务`), 1), l(Ae, {
					items: ie.value,
					onRemove: le
				}, null, 8, ["items"])]),
				_: 1
			}, 8, ["filtered"]),
			ae.value.length ? (n(), j("div", $r, [(n(), j(h, null, o([
				"retry",
				"cancel",
				"terminate",
				"delete"
			], (e) => x("button", {
				key: e,
				type: "button",
				class: T(["ui-button", { "ui-button--danger": e === "delete" || e === "terminate" }]),
				disabled: B.value || !se.value[e],
				onClick: (t) => _e(e)
			}, y(K[e]) + y(se.value[e] ? `（${se.value[e]}）` : ""), 11, ei)), 64))])) : p("", !0),
			V.value || H.value || A(N) && A(w).length ? (n(), j("div", {
				key: 1,
				class: T(["ui-list-feedback tc-feedback", { "is-error": H.value || A(N) }]),
				role: H.value || A(N) ? "alert" : "status"
			}, [
				M(y(H.value || A(N) || V.value), 1),
				A(N) ? (n(), j("button", {
					key: 0,
					type: "button",
					class: "ui-link",
					onClick: t[4] ||= (e) => A(f).refresh()
				}, "重试")) : p("", !0),
				G.value.length ? (n(), j("details", ni, [t[12] ||= x("summary", null, "查看跳过原因", -1), x("ul", null, [(n(!0), j(h, null, o(G.value, (e) => (n(), j("li", { key: e.id }, "#" + y(e.id) + "：" + y(e.message), 1))), 128))])])) : p("", !0)
			], 10, ti)) : p("", !0),
			l(Lr, {
				ref_key: "table",
				ref: z,
				filters: A(g),
				facets: A(D),
				"open-filter": U.value,
				"onUpdate:openFilter": t[5] ||= (e) => U.value = e,
				"onUpdate:filters": q,
				items: A(w),
				selected: A(O),
				loading: A(ee),
				error: A(N),
				busy: B.value,
				onSelect: A(f).toggle,
				onSelectPage: A(f).togglePage,
				onDetail: J,
				onAction: ge,
				onBatch: t[6] ||= (e, t) => u("batch", e, t),
				onRetry: t[7] ||= (e) => A(f).refresh()
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
			l(Fe, {
				page: A(v),
				"onUpdate:page": t[8] ||= (e) => d(v) ? v.value = e : null,
				size: A(b),
				"onUpdate:size": t[9] ||= (e) => d(b) ? b.value = e : null,
				pages: A(S),
				total: A(C),
				busy: A(ee)
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy"
			])
		])], 512), [[k, A(P)]]), l(bn, {
			ref_key: "detail",
			ref: te,
			onRefresh: he
		}, null, 512)], 64));
	}
});
// src/main.ts
function ii(e, t = {}) {
	return D(ri, t).mount(e);
}
export { ii as mountTaskCenter };
