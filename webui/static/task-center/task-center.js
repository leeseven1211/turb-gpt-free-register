import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, V as u, X as d, Z as f, _ as p, a as m, c as h, d as g, dt as _, et as v, f as y, ft as b, g as x, h as S, j as C, k as w, l as ee, lt as T, m as E, n as D, nt as O, s as k, st as A, v as j, x as M } from "./_plugin-vue_export-helper-Btipf5Px.js";
import { n as N, r as P, t as F } from "./client-B5R_MNgP.js";
import { a as I, i as te, n as L, r as R } from "./taskIds-BlchWwUp.js";
import { a as z, n as ne, t as re } from "./bulkMutations-3wwPI3-H.js";
import { A as ie, C as ae, D as B, E as oe, F as V, M as H, N as U, O as W, P as se, S as G, T as ce, _ as le, a as K, b as ue, c as de, d as fe, f as pe, g as me, h as he, i as q, j as J, k as ge, l as _e, m as ve, n as ye, o as be, p as xe, r as Se, s as Ce, t as we, u as Te, v as Ee, w as De, x as Y, y as Oe } from "./StepEvidence-DQe06uCz.js";
import { n as ke } from "./time-DOD6oyhP.js";
import { i as Ae, n as je, r as X, t as Me } from "./ListFilterSummary-M6f9Z7EF.js";
import { n as Ne, t as Pe } from "./ColumnResizer-D3GCD-87.js";
import { t as Fe } from "./ListResult-RnSAyLEO.js";
import { t as Ie } from "./errorLabels-fdGNkTBr.js";
import { t as Le } from "./ListPagination-CmqtjjEX.js";
import { t as Re } from "./ListToolbar-CtMQ0-oI.js";
// src/api/tasks.ts
var ze = (e, t = {}) => P(e, t, R);
function Be() {
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
function Ve(e) {
	return new URLSearchParams(Object.entries(e).filter(([, e]) => e !== void 0 && e !== "").map(([e, t]) => [e, String(t)])).toString();
}
function He(e) {
	let t = new URLSearchParams();
	for (let n of e) {
		let e = I(n.task_id), r = L(n.run_id);
		t.append("ref", r === null ? String(e) : `${e}:${r}`);
	}
	return t.toString();
}
async function Ue(e, t, n) {
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
		let e = await ze(t, {
			method: "POST",
			headers: {
				"Idempotency-Key": i,
				...n ? { "Content-Type": "application/json" } : {}
			},
			...n ? { body: We(t, n) } : {}
		});
		return s(), e;
	} catch (e) {
		throw e instanceof F && [
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
function We(e, t) {
	if (e !== "/api/operations/bulk") return JSON.stringify(t);
	let { task_ids: n, ...r } = t;
	if (!Array.isArray(n)) return JSON.stringify(t);
	let i = JSON.stringify(r).slice(0, -1);
	return `${i}${i.length > 1 ? "," : ""}"task_ids":[${n.map((e) => String(I(e))).join(",")}]}`;
}
async function Ge(e, t = {}) {
	let n = await z((t, n) => n?.method === "POST" ? ne(t, {
		...n,
		body: We(t, {
			action: "terminate",
			task_ids: e
		})
	}) : ne(t, n), "/api/operations/bulk", {
		action: "terminate",
		task_ids: e
	}, t);
	if (!Array.isArray(n.items)) return n;
	let r = n.items.filter((e) => e.status === "updated").map((e) => ({
		task_id: I(e.key),
		state: String(e.data?.state || "stopped"),
		message: String(e.data?.message || "")
	})), i = n.items.filter((e) => e.status !== "updated").map((e) => ({
		task_id: I(e.key),
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
var Ke = {
	list: (e, t) => ze(`/api/operations?${Ve(e)}`, { signal: t }),
	detail: (e, t) => ze(`/api/operations/${I(e)}?include_events=0`, { signal: t }),
	receipts: (e, t) => ze(`/api/operations/receipts?${He(e)}`, { signal: t }),
	progress: (e, t, n) => ze(`/api/operations/${I(e)}/runs/${I(t)}/progress`, { signal: n }),
	events: (e, t, n = {}, r) => ze(`/api/operations/${I(e)}/runs/${I(t)}/events?${Ve({
		limit: 500,
		...n
	})}`, { signal: r }),
	logs: (e, t, n = {}, r) => ze(`/api/operations/${I(e)}/runs/${I(t)}/logs?${Ve({
		limit: 500,
		...n
	})}`, { signal: r }),
	action: (e, t) => t === "retry" ? Ue(`retry:${I(e)}`, `/api/operations/${I(e)}/retry`) : ze(`/api/operations/${I(e)}/${t}`, { method: "POST" }),
	bulk: (e, t, n) => e === "terminate" ? Ge(t, n) : e === "retry" ? Ue("bulk:retry", "/api/operations/bulk", {
		action: e,
		task_ids: t
	}) : ze("/api/operations/bulk", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: We("/api/operations/bulk", {
			action: e,
			task_ids: t
		})
	})
}, qe = (e) => e instanceof Error ? e.message : "读取失败，请重试";
function Je(e = Ke, t = () => {}) {
	let n = v(!1), r = v(!0), i = v(null), a = v(null), o = O(null), s = O(null), c = O([]), l = O([]), u = v("events"), d = v(null), p = v(""), m = v(""), h = v(""), g = v(""), _ = v(!1), y = v(!1), b = v(!1), x = v(null), S = v(null), C = v("tail"), w = v("tail"), ee = v(!1), T = v(!1), D = v(!1), k = v(!1), A = v(!0), j = E(() => o.value?.runs || []), M = E(() => j.value.find((e) => te(e.id, a.value))), N = 0, P = 0, F = 0, R = 0, z = null, ne, re = new AbortController(), ae = !1;
	function B() {
		ne !== void 0 && clearTimeout(ne), ne = void 0;
	}
	function oe() {
		N += 1, re.abort(), re = new AbortController(), z = null, _.value = y.value = b.value = !1, B();
	}
	let V = (e) => e === N && n.value, H = () => n.value && r.value && !!i.value;
	function U() {
		B(), H() && (!o.value || ie(o.value)) && (ne = setTimeout(() => void K(!0), 2e3));
	}
	function W() {
		P += 1, F += 1, y.value = b.value = !1, s.value = null, m.value = h.value = g.value = "", c.value = [], l.value = [], x.value = S.value = null, ee.value = T.value = D.value = k.value = !1, C.value = w.value = "tail", A.value = !0;
	}
	async function se(t = "incremental") {
		if (!H() || !a.value || !i.value || t === "incremental" && y.value || t === "incremental" && C.value === "start" && T.value || t === "next" && !T.value) return;
		let n = N, r = ++P, o = t === "tail" || t === "start" || x.value === null, s = {
			limit: 500,
			...t === "start" ? { after_id: 0 } : t !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		y.value = !0;
		try {
			let l = await e.events(i.value, a.value, s, re.signal);
			if (!V(n) || r !== P) return;
			c.value = o ? l.items : xe(c.value, l.items), x.value = l.next_after_id, (t === "tail" || t === "start") && (C.value = t), o && C.value === "tail" ? (ee.value = l.has_more, T.value = !1) : (T.value = l.has_more, C.value === "start" && (ee.value = !1)), h.value = "";
		} catch (e) {
			V(n) && r === P && (h.value = qe(e));
		} finally {
			V(n) && r === P && (y.value = !1);
		}
	}
	async function G(t = "incremental") {
		if (!H() || !a.value || !i.value || t === "incremental" && b.value || t === "incremental" && w.value === "start" && k.value || t === "next" && !k.value) return;
		let n = N, r = ++F, o = t === "tail" || t === "start" || S.value === null, s = {
			limit: 500,
			...t === "start" ? { cursor: 0 } : t !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		b.value = !0;
		try {
			let c = await e.logs(i.value, a.value, s, re.signal);
			if (!V(n) || r !== F) return;
			l.value = o ? c.items : [...l.value, ...c.items], S.value = c.next_cursor, (t === "tail" || t === "start") && (w.value = t), k.value = c.has_more, D.value = w.value === "tail" && c.available, A.value = c.available, g.value = "";
		} catch (e) {
			V(n) && r === F && (g.value = qe(e));
		} finally {
			V(n) && r === F && (b.value = !1);
		}
	}
	async function ce(t) {
		if (i.value && a.value) try {
			let n = await e.progress(i.value, a.value, re.signal);
			if (!V(t)) return;
			s.value = n.progress, m.value = "";
		} catch (e) {
			V(t) && (m.value = qe(e));
		}
	}
	function le() {
		return K(!1);
	}
	function K(e) {
		if (!H() || !i.value) return Promise.resolve();
		if (e || (_.value = !0), z) return z;
		let t = N, n = ++R;
		return z = ue(t, n).finally(() => {
			V(t) && n === R && (z = null, _.value = !1, U());
		}), z;
	}
	async function ue(n, r) {
		if (i.value) {
			B();
			try {
				let s = await e.detail(i.value, re.signal);
				if (!V(n) || r !== R) return;
				o.value = s.task;
				let c = s.task.runs || [];
				if (a.value && !c.some((e) => te(e.id, a.value))) {
					W(), p.value = `所选运行 #${a.value} 不存在或已不可用，请选择其他运行。`;
					return;
				}
				let l = a.value || s.task.last_run_id || c.at(-1)?.id || null, d = c.some((e) => te(e.id, l)) ? l : c.at(-1)?.id || null;
				if (d !== a.value && (W(), a.value = d), p.value = "", a.value && await Promise.allSettled([
					ce(n),
					se(),
					...u.value === "logs" ? [G()] : []
				]), !V(n)) return;
				!ie(s.task) && !ae && (ae = !0, t());
			} catch (e) {
				V(n) && (p.value = qe(e));
			}
		}
	}
	function de(e, t, r) {
		return oe(), n.value = !0, i.value = I(e), a.value = L(t), o.value = null, p.value = "", u.value = "events", d.value = r || null, ae = !1, W(), le();
	}
	function fe() {
		n.value = !1, oe();
	}
	function pe(e) {
		if (e = I(e), !te(e, a.value)) return oe(), a.value = e, d.value = null, W(), le();
	}
	function me(e) {
		if (u.value = e, e === "logs") return G();
	}
	function he(e) {
		r.value !== e && (r.value = e, e ? n.value && le() : oe());
	}
	return f(fe), {
		opened: n,
		taskId: i,
		runId: a,
		task: o,
		runs: j,
		selectedRun: M,
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
		eventsEarlier: ee,
		eventsMore: T,
		logsEarlier: D,
		logsMore: k,
		logsAvailable: A,
		open: de,
		close: fe,
		selectRun: pe,
		selectTab: me,
		setVisible: he,
		refresh: le,
		loadEvents: se,
		loadLogs: G
	};
}
// src/features/tasks/detail/TaskFailure.vue?vue&type=script&setup=true&lang.ts
var Ye = {
	key: 0,
	class: "tc-progress-failure tc-task-failure"
}, Xe = { key: 0 }, Ze = { key: 1 }, Qe = {
	key: 2,
	class: "tc-failure-secondary"
}, $e = { key: 3 }, et = { key: 0 }, tt = { key: 1 }, nt = { key: 2 }, rt = /* @__PURE__ */ t({
	__name: "TaskFailure",
	props: {
		failure: {},
		execution: {},
		status: {}
	},
	setup(e) {
		let t = e, r = E(() => !!(t.execution?.error_message || t.execution?.error_info)), i = E(() => (t.failure?.country_failures || []).filter((e) => G(e.country).trim())), a = E(() => {
			let e = t.failure;
			return e ? i.value.length && !e.error_info?.auto_refresh_at_failed ? `${i.value.length} 个国家查询失败，展开查看具体原因` : Te(e) : "";
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
			].includes(n) && n !== e.stage ? J("stage", n) : [e.label || e.step_id || "阶段记录缺失", e.stage].filter(Boolean).join(" · ");
		}), c = E(() => r.value ? B(t.execution?.error_info, t.execution?.error_message) : ""), l = E(() => {
			if (!t.failure || !r.value) return !1;
			let e = (e) => G(e).replace(/\s+/g, " ").trim(), n = t.failure, i = n.error_info, a = t.execution?.error_info, o = e(n.message), s = e(t.execution?.error_message);
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
		return (t, d) => e.failure || r.value ? (n(), j("details", Ye, [
			S("summary", null, [
				e.failure ? (n(), j("strong", Xe, b(A(_e)(e.failure) ? "历史失败位置" : "失败位置") + "：" + b(s.value), 1)) : (n(), j("strong", Ze, "执行失败")),
				S("span", null, b(a.value || c.value), 1),
				e.failure && r.value && !l.value ? (n(), j("span", Qe, "执行错误：" + b(c.value), 1)) : p("", !0),
				e.execution?.error_info?.display_code ? (n(), j("small", $e, b(e.execution.error_info.display_code), 1)) : p("", !0)
			]),
			i.value.length ? (n(), j("ul", et, [(n(!0), j(g, null, o(i.value, (e, t) => (n(), j("li", { key: t }, b(e.country) + "：" + b(e.summary || "诊断记录不完整"), 1))), 128))])) : p("", !0),
			e.failure?.event_id ? (n(), j("p", tt, "关联事件 " + b(e.failure.event_id), 1)) : p("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(A(G)(e.status)) ? (n(), j("p", nt, "原请求证据已保留")) : p("", !0),
			S("pre", null, b(JSON.stringify(u.value, null, 2)), 1)
		])) : p("", !0);
	}
}), it = {
	key: 0,
	class: "tc-progress",
	"aria-label": "执行进度"
}, at = { class: "tc-progress-heading" }, ot = { key: 0 }, st = ["data-step-count"], ct = [
	"aria-pressed",
	"title",
	"onClick"
], lt = {
	key: 0,
	class: "tc-step-dot",
	"aria-hidden": "true"
}, ut = {
	key: 1,
	class: "tc-step-meta"
}, dt = { key: 0 }, ft = {
	key: 2,
	class: "tc-step-meta"
}, pt = { key: 0 }, mt = {
	key: 3,
	class: "tc-step-deps"
}, ht = ["aria-label", "onClick"], gt = {
	key: 1,
	class: "tc-detail-muted"
}, _t = {
	key: 2,
	class: "tc-flow-relations"
}, vt = { class: "tc-flow-relations__count" }, yt = { class: "tc-flow-relations__panel" }, bt = { class: "tc-flow-relations__hint" }, xt = { class: "tc-flow-relations__grid" }, St = { class: "tc-flow-relation__head" }, Ct = {
	key: 0,
	class: "tc-flow-relation__status"
}, wt = {
	key: 3,
	class: "tc-child-tasks"
}, Tt = ["onClick"], Et = { id: "tc-step-title" }, Dt = { class: "tc-step-dialog-body" }, Ot = /* @__PURE__ */ t({
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
		let a = t, s = r, c = E(() => a.taskType === "codex_retry"), u = E(() => c.value ? a.progress?.main_steps || [] : be(a.progress?.main_steps)), d = E(() => c.value ? u.value.filter((e) => e.observed_order != null || e.evidence === "run_status") : u.value), f = E(() => {
			let e = d.value.length;
			return e <= 1 ? 1 : e === 2 ? 2 : e === 3 ? 3 : e === 4 ? 4 : e === 5 ? 5 : e === 6 ? 3 : e <= 8 ? 4 : 5;
		}), m = {
			success: "tc-badge--success",
			recovered: "tc-badge--success",
			failed: "tc-badge--danger",
			running: "tc-badge--active",
			stopped: "tc-badge--warning",
			interrupted: "tc-badge--warning",
			debug_paused: "tc-badge--warning"
		};
		function h(e) {
			let t = Y(e);
			return [
				"success",
				"failed",
				"skipped",
				"running"
			].includes(t) ? me(t) : K(e);
		}
		let y = v(null), w = E(() => u.value.find((e) => Oe(e) === y.value)), D = v(), O = null, k = E(() => le(a.progress?.outcome?.child_tasks).flatMap((e) => {
			try {
				return [{
					...e,
					task_id: I(e.task_id),
					run_id: L(e.run_id),
					task_type: e.task_type,
					status: e.status
				}];
			} catch {
				return [];
			}
		})), N = E(() => {
			let e = ve(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${ke(G(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			return t ? `当前：${t.label || t.step_id || "执行中"}${t.child_label ? ` · ${t.child_label}` : ""}` : "执行阶段";
		});
		function P(e) {
			return [
				ue(e),
				K(e),
				...q(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function F(e) {
			return Oe(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function te(t) {
			O = document.activeElement instanceof HTMLElement ? document.activeElement : null, y.value = Oe(t), await e(), D.value?.open || D.value?.showModal();
		}
		function R() {
			D.value?.close(), y.value = null, O?.isConnected && O.focus({ preventScroll: !0 }), O = null;
		}
		function z(e) {
			let t = D.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i(() => [a.context, a.active], R), C(() => D.value?.close()), (e, r) => t.progress ? (n(), j("section", it, [
			S("div", at, [S("strong", null, b(N.value), 1), !c.value || t.progress.source !== "explicit" ? (n(), j("small", ot, b(t.progress.source === "legacy_derived" ? "历史记录还原" : t.progress.source === "insufficient_evidence" ? "步骤记录缺失" : "按首次记录排列，可含分支与重试"), 1)) : p("", !0)]),
			d.value.length ? (n(), j("ul", {
				key: 0,
				class: T(["tc-progress-track", { "tc-progress-track--codex": c.value }]),
				"data-step-count": d.value.length,
				style: _({ "--tc-step-cols": String(f.value) }),
				"aria-label": "执行阶段，排列不代表固定顺序"
			}, [(n(!0), j(g, null, o(d.value, (e) => (n(), j("li", {
				key: A(Oe)(e),
				class: T([
					"tc-step",
					`tc-step--${A(Y)(e)}`,
					{ "tc-step--selected": F(e) }
				])
			}, [S("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": F(e),
				title: P(e),
				onClick: (t) => s("filter", F(e) ? null : A(Oe)(e))
			}, [
				c.value ? p("", !0) : (n(), j("span", lt)),
				S("strong", null, b(A(ue)(e)), 1),
				c.value ? (n(), j("span", ut, [S("span", { class: T(["tc-badge tc-step-status", m[A(Y)(e)]]) }, b(h(e)), 3), A(Y)(e) !== "skipped" && A(Ee)(e) != null ? (n(), j("small", dt, b(A(ge)(A(Ee)(e))), 1)) : p("", !0)])) : (n(), j("span", ft, [
					M(b(A(K)(e)), 1),
					A(Ee)(e) == null ? p("", !0) : (n(), j("small", pt, " · " + b(A(ge)(A(Ee)(e))), 1)),
					(n(!0), j(g, null, o(A(q)(e), (e) => (n(), j("small", { key: e }, " · " + b(e), 1))), 128))
				])),
				A(Se)(e, u.value).length ? (n(), j("span", mt, [(n(!0), j(g, null, o(A(Se)(e, u.value), (e) => (n(), j("em", {
					key: e,
					class: "tc-step-dep-chip"
				}, b(e), 1))), 128))])) : p("", !0)
			], 8, ct), S("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${A(ue)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => te(e)
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
			})], -1)]], 8, ht)], 2))), 128))], 14, st)) : (n(), j("p", gt, b(c.value ? "此运行暂无阶段记录。" : "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。"), 1)),
			u.value.length ? (n(), j("details", _t, [S("summary", null, [r[3] ||= S("span", { class: "tc-flow-relations__title" }, "依赖与完整阶段记录", -1), S("span", vt, b(u.value.length) + " 个阶段", 1)]), S("div", yt, [S("p", bt, b(t.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1), S("div", xt, [(n(!0), j(g, null, o(u.value, (e) => (n(), j("div", {
				key: A(Oe)(e),
				class: "tc-flow-relation"
			}, [S("div", St, [S("strong", null, b(A(ue)(e)), 1), c.value ? (n(), j("span", Ct, b(h(e)), 1)) : p("", !0)]), l(ye, {
				step: e,
				siblings: u.value
			}, null, 8, ["step", "siblings"])]))), 128))])])])) : p("", !0),
			l(rt, {
				failure: t.progress.failure,
				execution: t.execution,
				status: t.progress.outcome.status
			}, null, 8, [
				"failure",
				"execution",
				"status"
			]),
			k.value.length ? (n(), j("div", wt, [r[4] ||= S("strong", null, "独立子任务", -1), (n(!0), j(g, null, o(k.value, (e) => (n(), j("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, b(A(J)("task_type", A(G)(e.task_type))) + " #" + b(e.task_id) + " · " + b(A(me)(e.status)), 9, Tt))), 128))])) : p("", !0),
			S("dialog", {
				ref_key: "inspector",
				ref: D,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: ee(R, ["prevent"]),
				onClose: r[0] ||= (e) => y.value = null,
				onWheel: ee(z, ["stop"]),
				onClick: r[1] ||= (e) => {
					e.target === D.value && R();
				}
			}, [S("header", null, [S("h3", Et, b(w.value ? A(ue)(w.value) : "步骤详情"), 1), S("button", {
				type: "button",
				autofocus: "",
				onClick: R
			}, "关闭")]), S("div", Dt, [w.value ? (n(), x(we, {
				key: 0,
				step: w.value,
				siblings: u.value
			}, null, 8, ["step", "siblings"])) : p("", !0)])], 544)
		])) : p("", !0);
	}
}), kt = { class: "tc-detail-header" }, At = { id: "tc-detail-title" }, jt = { key: 0 }, Mt = ["title"], Nt = {
	key: 1,
	class: "tc-detail-run"
}, Pt = ["value", "disabled"], Ft = ["value"], It = {
	key: 1,
	value: ""
}, Lt = ["value"], Rt = { class: "tc-detail-header-actions" }, zt = ["disabled"], Bt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Vt = { key: 0 }, Ht = ["disabled"], Ut = {
	key: 1,
	class: "tc-detail-empty",
	role: "status"
}, Wt = {
	key: 0,
	class: "tc-detail-notice"
}, Gt = {
	key: 1,
	class: "tc-detail-notice"
}, Kt = {
	key: 3,
	class: "tc-detail-error",
	role: "status"
}, qt = { class: "tc-detail-view-toolbar" }, Jt = [
	"id",
	"data-detail-tab",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], Yt = {
	key: 0,
	class: "tc-detail-read-toolbar"
}, Xt = ["aria-pressed", "disabled"], Zt = ["aria-pressed", "disabled"], Qt = {
	id: "tc-detail-panel-events",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-events",
	tabindex: "0"
}, $t = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, en = ["disabled"], tn = {
	key: 1,
	class: "tc-detail-notice"
}, nn = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, rn = { class: "tc-event-meta" }, an = ["data-level"], on = { class: "tc-event-stage" }, sn = {
	key: 0,
	class: "tc-event-step"
}, cn = ["data-state"], ln = { class: "tc-event-id" }, un = {
	key: 0,
	class: "tc-technical"
}, dn = ["disabled"], fn = {
	id: "tc-detail-panel-logs",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-logs",
	tabindex: "0"
}, pn = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, mn = ["disabled"], hn = {
	key: 1,
	class: "tc-detail-notice"
}, gn = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, _n = ["data-level"], vn = { class: "tc-event-meta" }, yn = ["data-level"], bn = { class: "tc-log-stage" }, xn = {
	key: 0,
	class: "tc-technical"
}, Sn = ["disabled"], Cn = {
	id: "tc-detail-panel-artifacts",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-artifacts",
	tabindex: "0"
}, wn = {
	key: 0,
	class: "tc-artifact"
}, Tn = { key: 0 }, En = { class: "tc-artifact-links" }, Dn = ["href"], On = ["href"], kn = ["href"], An = {
	key: 1,
	class: "tc-detail-empty"
}, jn = {
	key: 2,
	class: "tc-technical"
}, Mn = { class: "tc-detail-footer" }, Nn = {
	key: 1,
	role: "status"
}, Pn = /* @__PURE__ */ t({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(t, { expose: r, emit: c }) {
		let u = c, d = Je(void 0, () => u("refresh")), { opened: f, taskId: m, runId: h, task: _, runs: w, selectedRun: D, progress: O, events: N, logs: P, tab: F, stepFilter: I, error: L, progressError: R, eventsError: z, logsError: ne, loading: re, eventsLoading: ie, logsLoading: B, eventsMode: oe, logsMode: H, eventsEarlier: U, eventsMore: W, logsEarlier: se, logsMore: ce, logsAvailable: le } = d, K = v(), q = v(), _e = v(0), ye = Intl.DateTimeFormat().resolvedOptions().timeZone, be = [
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
		], xe = E(() => O.value?.main_steps || []), Se = E(() => xe.value.find((e) => Oe(e) === I.value || !!(I.value && e.raw_stages?.includes(I.value)))), we = E(() => he(N.value.filter((e) => fe(e, I.value, xe.value)))), Te = E(() => P.value.filter((e) => fe(e, I.value, xe.value, !0))), Ee = E(() => we.value.map((e) => {
			let t = de(e), n = pe(e.detail);
			return {
				event: e,
				state: t,
				timestamp: ke(e.created_at),
				stageLabel: e.stage_label || J("stage", e.stage),
				association: Fe(e),
				stateLabel: t ? me(t) : "记录",
				detailJson: n ? JSON.stringify(n, null, 2) : null
			};
		})), De = E(() => Te.value.map((e) => {
			let t = pe(e.fields);
			return {
				item: e,
				timestamp: e.ts ? ke(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), Y = E(() => h.value ? D.value : _.value), Ae = E(() => _.value?.email_snapshot || _.value?.email || (_.value?.account_id ? `账号 #${_.value.account_id}` : _.value?.target_id || "执行记录与诊断")), je = E(() => (_.value?.resources || []).filter((e) => !h.value || te(e.run_id, h.value))), X = E(() => D.value?.debug_artifacts), Me = E(() => ve(D.value?.debug_pause || O.value?.debug_pause)), Ne = null, Pe = !1;
		function Fe(e) {
			let t = ve(e.detail), n = G(e.main_step_id || t.main_step_id), r = G(e.raw_stage || t.raw_stage || e.stage), i = xe.value.filter((e) => n ? e.id === n : e.raw_stages?.includes(r));
			return i.length === 1 ? ue(i[0]) : "未关联步骤";
		}
		function Ie() {
			f.value && (d.close(), Ne?.isConnected && Ne.focus({ preventScroll: !0 }), Ne = null, u("close"));
		}
		function Le() {
			K.value?.close(), Ie();
		}
		async function Re(t, n, r) {
			f.value || (Ne = document.activeElement instanceof HTMLElement ? document.activeElement : null), _e.value = 0, d.setVisible(!document.hidden);
			let i = d.open(t, n, r);
			return await e(), !K.value?.open && f.value && K.value?.showModal(), i;
		}
		function ze(e) {
			d.setVisible(e);
		}
		function Be() {
			ze(!document.hidden);
		}
		function Ve(e) {
			_e.value = 0, d.selectRun(e.target.value);
		}
		async function He(t) {
			_e.value = 0, await d.selectTab(t), await e(), q.value && (q.value.scrollTop = 0);
		}
		function Ue(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			let t = be.findIndex((e) => e.id === F.value), n = e.key === "Home" ? 0 : e.key === "End" ? be.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + be.length) % be.length;
			e.preventDefault(), He(be[n].id), e.currentTarget.querySelector(`[data-detail-tab="${be[n].id}"]`)?.focus();
		}
		async function We(t) {
			Pe = !0, F.value === "events" ? await d.loadEvents(t) : await d.loadLogs(t), await e(), q.value && t !== "next" && (q.value.scrollTop = t === "tail" ? q.value.scrollHeight : 0), _e.value = 0, Pe = !1;
		}
		function Ge() {
			q.value && (q.value.scrollTop = q.value.scrollHeight), _e.value = 0;
		}
		function Ke(e) {
			let t = q.value;
			K.value && K.value.scrollHeight > K.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i([N, P], async ([t, n], [r, i]) => {
			if (Pe) return;
			let a = q.value, o = !a || a.scrollTop + a.clientHeight >= a.scrollHeight - 40, s = F.value === "events" ? t.length - r.length : F.value === "logs" ? n.length - i.length : 0;
			s <= 0 || (await e(), o ? Ge() : _e.value += s);
		}), i(I, () => {
			_e.value = 0, q.value && (q.value.scrollTop = 0);
		}), s(() => {
			Be(), document.addEventListener("visibilitychange", Be);
		}), C(() => {
			document.removeEventListener("visibilitychange", Be), K.value?.close();
		}), r({
			open: Re,
			close: Le,
			setVisible: ze
		}), (e, t) => (n(), x(y, { to: "body" }, [S("dialog", {
			ref_key: "dialog",
			ref: K,
			class: "tc-detail-dialog",
			"aria-labelledby": "tc-detail-title",
			onCancel: ee(Le, ["prevent"]),
			onClose: Ie,
			onWheel: Ke
		}, [
			S("header", kt, [
				S("h2", At, [M("任务 #" + b(A(m)) + " ", 1), A(_) ? (n(), j("span", jt, b(A(J)("task_type", A(_).task_type)), 1)) : p("", !0)]),
				S("span", {
					class: "tc-detail-target",
					title: String(Ae.value),
					tabindex: "0"
				}, b(Ae.value), 9, Mt),
				Y.value ? (n(), j("div", {
					key: 0,
					class: T(["tc-detail-status", `tc-detail-status--${A(V)(Y.value.status)}`])
				}, [S("strong", null, b(A(J)("status", Y.value.status)), 1), S("span", null, "耗时 " + b(A(ge)(Y.value.duration_ms)), 1)], 2)) : p("", !0),
				A(_) ? (n(), j("label", Nt, [t[10] ||= S("span", null, "运行", -1), S("select", {
					value: A(h) || "",
					"aria-label": "选择执行实例",
					disabled: A(w).length < 2 && (!A(h) || !!A(D)),
					onChange: Ve
				}, [A(h) && !A(D) ? (n(), j("option", {
					key: 0,
					value: A(h),
					disabled: ""
				}, "运行 #" + b(A(h)) + " 不可用", 9, Ft)) : A(w).length ? p("", !0) : (n(), j("option", It, "暂无运行")), (n(!0), j(g, null, o(A(w), (e) => (n(), j("option", {
					key: e.id,
					value: e.id
				}, "第 " + b(e.run_no || "—") + " 次 · " + b(A(J)("status", e.status)), 9, Lt))), 128))], 40, Pt)])) : p("", !0),
				S("div", Rt, [S("button", {
					type: "button",
					disabled: A(re),
					onClick: t[0] ||= (...e) => A(d).refresh && A(d).refresh(...e)
				}, b(A(re) ? "刷新中…" : "刷新"), 9, zt), S("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Le
				}, "关闭")])
			]),
			A(L) ? (n(), j("div", Bt, [
				M("读取任务失败：" + b(A(L)), 1),
				A(_) ? (n(), j("span", Vt, "。保留上次已读取的记录。")) : p("", !0),
				S("button", {
					type: "button",
					disabled: A(re),
					onClick: t[1] ||= (...e) => A(d).refresh && A(d).refresh(...e)
				}, "重试", 8, Ht)
			])) : p("", !0),
			A(re) && !A(_) ? (n(), j("div", Ut, "正在读取任务详情…")) : p("", !0),
			A(_) ? (n(), j(g, { key: 2 }, [
				Y.value?.status === "queued" ? (n(), j("p", Wt, b(A(ae)(Y.value)), 1)) : p("", !0),
				Me.value.state === "paused" ? (n(), j("p", Gt, [t[11] ||= M("调试暂停，等待结束调试。", -1), Me.value.hold_until ? (n(), j(g, { key: 0 }, [M("保留至 " + b(A(ke)(Me.value.hold_until)) + "。", 1)], 64)) : p("", !0)])) : p("", !0),
				A(O) ? p("", !0) : (n(), x(rt, {
					key: 2,
					execution: Y.value,
					status: Y.value?.status
				}, null, 8, ["execution", "status"])),
				l(Ot, {
					progress: A(O),
					"task-type": A(_)?.task_type,
					execution: Y.value,
					filter: A(I),
					active: A(f),
					context: `${A(m)}:${A(h)}`,
					onFilter: t[2] ||= (e) => I.value = e,
					onChild: Re
				}, null, 8, [
					"progress",
					"task-type",
					"execution",
					"filter",
					"active",
					"context"
				]),
				A(R) ? (n(), j("p", Kt, [M("进度读取失败：" + b(A(R)), 1), A(O) ? (n(), j(g, { key: 0 }, [M("；保留上次快照")], 64)) : p("", !0)])) : p("", !0),
				S("div", qt, [
					S("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: Ue
					}, [(n(), j(g, null, o(be, (e) => S("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": A(F) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: A(F) === e.id ? 0 : -1,
						onClick: (t) => He(e.id)
					}, b(e.label), 9, Jt)), 64))], 32),
					S("div", { class: T(["tc-detail-filter", { "is-active": !!A(I) }]) }, [S("span", null, [t[12] ||= M("当前查看：", -1), S("strong", null, b(Se.value ? A(ue)(Se.value) : A(I) || "全流程"), 1)]), A(I) ? (n(), j("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => I.value = null
					}, "清除步骤筛选")) : p("", !0)], 2),
					A(F) === "artifacts" ? p("", !0) : (n(), j("div", Yt, [S("button", {
						type: "button",
						"aria-pressed": (A(F) === "events" ? A(oe) : A(H)) === "start",
						disabled: A(ie) || A(B) || !A(h),
						onClick: t[4] ||= (e) => We("start")
					}, "从头加载", 8, Xt), S("button", {
						type: "button",
						"aria-pressed": (A(F) === "events" ? A(oe) : A(H)) === "tail",
						disabled: A(ie) || A(B) || !A(h),
						onClick: t[5] ||= (e) => We("tail")
					}, "最近记录", 8, Zt)]))
				]),
				S("div", {
					ref_key: "scroller",
					ref: q,
					class: "tc-detail-content"
				}, [
					a(S("section", Qt, [
						A(z) ? (n(), j("p", $t, [M("事件读取失败：" + b(A(z)), 1), S("button", {
							type: "button",
							disabled: A(ie),
							onClick: t[6] ||= (e) => A(d).loadEvents()
						}, "重试", 8, en)])) : p("", !0),
						A(U) ? (n(), j("p", tn, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : p("", !0),
						we.value.length ? p("", !0) : (n(), j("div", nn, b(A(ie) ? "正在读取事件…" : A(I) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(n(!0), j(g, null, o(Ee.value, (e) => (n(), j("article", {
							key: e.event.id,
							class: T(["tc-event", {
								"tc-event--error": e.state === "failed",
								"tc-event--success": e.state === "success" || e.state === "recovered",
								"tc-event--running": e.state === "running",
								"tc-event--warning": [
									"stopped",
									"interrupted",
									"debug_paused",
									"attention_required",
									"queued"
								].includes(e.state)
							}])
						}, [
							S("div", rn, [
								S("time", null, b(e.timestamp), 1),
								S("span", {
									class: "tc-event-level",
									"data-level": (e.event.level || "INFO").toUpperCase()
								}, b(e.event.level || "INFO"), 9, an),
								S("strong", on, b(e.stageLabel), 1),
								e.association ? (n(), j("span", sn, b(e.association), 1)) : p("", !0),
								S("span", {
									class: "tc-event-state",
									"data-state": e.state || "info"
								}, b(e.stateLabel), 9, cn),
								S("small", ln, "事件 " + b(e.event.event_id || e.event.id), 1)
							]),
							S("p", null, b(e.event.message || "—"), 1),
							e.detailJson ? (n(), j("details", un, [t[13] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 2))), 128)),
						A(W) ? (n(), j("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: A(ie),
							onClick: t[7] ||= (e) => We("next")
						}, b(A(ie) ? "正在读取…" : "继续加载后续事件"), 9, dn)) : p("", !0)
					], 512), [[k, A(F) === "events"]]),
					a(S("section", fn, [
						A(ne) ? (n(), j("p", pn, [M("日志读取失败：" + b(A(ne)), 1), S("button", {
							type: "button",
							disabled: A(B),
							onClick: t[8] ||= (e) => A(d).loadLogs()
						}, "重试", 8, mn)])) : p("", !0),
						A(se) ? (n(), j("p", hn, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : p("", !0),
						Te.value.length ? p("", !0) : (n(), j("div", gn, b(A(B) ? "正在读取运行日志…" : A(le) ? A(I) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(n(!0), j(g, null, o(De.value, (e, r) => (n(), j("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${r}`,
							class: "tc-log-line",
							"data-level": (e.item.level || "INFO").toUpperCase()
						}, [
							S("div", vn, [
								S("time", null, b(e.timestamp), 1),
								S("strong", {
									class: "tc-log-level",
									"data-level": (e.item.level || "INFO").toUpperCase()
								}, b(e.item.level || "INFO"), 9, yn),
								S("span", bn, b(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							S("p", null, b(e.item.message), 1),
							e.detailJson ? (n(), j("details", xn, [t[14] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 8, _n))), 128)),
						A(ce) ? (n(), j("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: A(B),
							onClick: t[9] ||= (e) => We("next")
						}, b(A(B) ? "正在读取…" : "继续加载后续日志"), 9, Sn)) : p("", !0)
					], 512), [[k, A(F) === "logs"]]),
					a(S("section", Cn, [
						X.value?.available ? (n(), j("article", wn, [
							t[15] ||= S("h3", null, "Roxy 刷新调试", -1),
							S("p", null, b(X.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + b(A(ve)(X.value.summary).request_count || 0) + " 条", 1),
							A(D)?.result_summary?.debug_browser_kept === !0 ? (n(), j("p", Tn, "失败窗口已保留，可在 Roxy 中查看。")) : p("", !0),
							S("div", En, [
								A(Ce)(X.value.har_url) ? (n(), j("a", {
									key: 0,
									href: A(Ce)(X.value.har_url),
									download: ""
								}, "下载 HAR", 8, Dn)) : p("", !0),
								A(Ce)(X.value.page_state_url) ? (n(), j("a", {
									key: 1,
									href: A(Ce)(X.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, On)) : p("", !0),
								A(Ce)(X.value.screenshot_url) ? (n(), j("a", {
									key: 2,
									href: A(Ce)(X.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, kn)) : p("", !0)
							])
						])) : p("", !0),
						(n(!0), j(g, null, o(je.value, (e, t) => (n(), j("article", {
							key: A(G)(e.id) || t,
							class: "tc-artifact"
						}, [
							S("h3", null, b(e.resource_type || "运行资源"), 1),
							S("p", null, b(e.provider || e.state || "—"), 1),
							S("small", null, b(A(ke)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!X.value?.available && !je.value.length ? (n(), j("div", An, "当前 Run 没有诊断资源或产物")) : p("", !0),
						Y.value?.result_summary ? (n(), j("details", jn, [t[16] ||= S("summary", null, "执行结果字段", -1), S("pre", null, b(JSON.stringify(Y.value.result_summary, null, 2)), 1)])) : p("", !0)
					], 512), [[k, A(F) === "artifacts"]])
				], 512),
				S("footer", Mn, [S("small", null, "时间按浏览器时区显示 · " + b(A(ye)), 1), _e.value && A(F) !== "artifacts" ? (n(), j("button", {
					key: 0,
					type: "button",
					onClick: Ge
				}, "有 " + b(_e.value) + " 条新记录，回到底部", 1)) : A(re) || A(ie) || A(B) ? (n(), j("small", Nn, "正在同步记录…")) : p("", !0)])
			], 64)) : p("", !0)
		], 544)]));
	}
}), Fn = [
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
function In(e, t) {
	return e.fields.some((e) => !!t[e]);
}
function Ln(e, t, n) {
	if (e.kind === "date-range") {
		let e = t.created_from, n = t.created_to;
		return e && n ? `创建日期 ${e} 至 ${n}` : e ? `创建日期自 ${e}` : n ? `创建日期截至 ${n}` : "";
	}
	let r = t[e.fields[0]];
	if (!r || e.kind !== "select") return r;
	let i = e.group || "", a = n[i] || [];
	return a.find((e) => e.value === r)?.label || r.split(",").map((e) => {
		let t = e.trim();
		return a.find((e) => e.value === t)?.label || J(i, t);
	}).join("、");
}
function Rn(e, t) {
	let n = { ...t };
	for (let t of e.fields) n[t] = "";
	return n;
}
// src/features/tasks/TaskFilterFields.vue?vue&type=script&setup=true&lang.ts
var zn = {
	key: 0,
	class: "tc-filter-field"
}, Bn = ["for"], Vn = [
	"id",
	"value",
	"inputmode",
	"placeholder"
], Hn = ["aria-label"], Un = ["name", "checked"], Wn = { class: "tc-filter-option-label" }, Gn = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], Kn = { class: "tc-filter-option-label" }, qn = {
	key: 0,
	class: "tc-filter-option-count"
}, Jn = {
	key: 2,
	class: "tc-filter-date-range"
}, Yn = { class: "tc-filter-field" }, Xn = ["for"], Zn = ["id", "value"], Qn = { class: "tc-filter-field" }, $n = ["for"], er = ["id", "value"], tr = { class: "tc-filter-footer" }, nr = ["disabled"], rr = /* @__PURE__ */ t({
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
				...Object.keys(H[e] || {}),
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
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? Ln(r.column, {
					...r.modelValue,
					[s.value]: t
				}, r.facets) : J(e, t)),
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
			i("update:modelValue", Rn(r.column, r.modelValue)), i("done");
		}
		return (t, r) => (n(), j("form", {
			class: "tc-filter-fields",
			onSubmit: r[5] ||= ee((e) => i("done"), ["prevent"])
		}, [e.column.kind === "search" ? (n(), j("div", zn, [S("label", { for: `${A(a)}-search` }, b(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, Bn), S("input", {
			id: `${A(a)}-search`,
			value: c.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: r[0] ||= (e) => m(s.value, e.target.value)
		}, null, 40, Vn)])) : e.column.kind === "select" ? (n(), j("div", {
			key: 1,
			class: "tc-filter-options",
			role: "radiogroup",
			"aria-label": e.column.label
		}, [S("label", { class: T(["tc-filter-option", { "is-selected": !c.value }]) }, [S("input", {
			type: "radio",
			name: A(a),
			value: "",
			checked: !c.value,
			onChange: r[1] ||= (e) => m(s.value, ""),
			onClick: r[2] ||= (e) => h("", e)
		}, null, 40, Un), S("span", Wn, b(l[e.column.group || ""] || "全部"), 1)], 2), (n(!0), j(g, null, o(f.value, (e) => (n(), j("label", {
			key: e.value,
			class: T(["tc-filter-option", { "is-selected": c.value === e.value }])
		}, [
			S("input", {
				type: "radio",
				name: A(a),
				value: e.value,
				checked: c.value === e.value,
				onChange: (t) => m(s.value, e.value),
				onClick: (t) => h(e.value, t)
			}, null, 40, Gn),
			S("span", Kn, b(e.text), 1),
			e.count == null ? p("", !0) : (n(), j("span", qn, b(e.count), 1))
		], 2))), 128))], 8, Hn)) : (n(), j("div", Jn, [
			r[6] ||= S("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			S("div", Yn, [S("label", { for: `${A(a)}-from` }, "创建日期起", 8, Xn), S("input", {
				id: `${A(a)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: r[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, Zn)]),
			S("div", Qn, [S("label", { for: `${A(a)}-to` }, "创建日期止", 8, $n), S("input", {
				id: `${A(a)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: r[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, er)])
		])), S("div", tr, [S("button", {
			type: "button",
			class: "ui-link",
			disabled: !A(In)(e.column, e.modelValue),
			onClick: _
		}, "清除此列", 8, nr), r[7] ||= S("button", {
			type: "submit",
			class: "ui-button"
		}, "完成", -1)])], 32));
	}
}), ir = { class: "tc-mobile-filters" }, ar = { class: "tc-filter-column-picker" }, or = ["value"], sr = /* @__PURE__ */ t({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = v(Fn[0].key), u = E(() => Fn.find((e) => e.key === c.value)), d = E(() => Fn.filter((e) => In(e, i.modelValue)).length);
		return (t, i) => (n(), j("div", ir, [l(Ae, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: e.open,
			"onUpdate:open": i[3] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [S("label", ar, [i[4] ||= M("筛选列", -1), a(S("select", { "onUpdate:modelValue": i[0] ||= (e) => c.value = e }, [(n(!0), j(g, null, o(A(Fn), (t) => (n(), j("option", {
				key: t.key,
				value: t.key
			}, b(t.label) + b(A(In)(t, e.modelValue) ? " · 已筛选" : ""), 9, or))), 128))], 512), [[m, c.value]])]), (n(), x(rr, {
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
}), cr = /* @__PURE__ */ t({
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
		return (t, a) => (n(), x(Ae, {
			label: e.column.label,
			active: A(In)(e.column, e.modelValue),
			summary: A(Ln)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": a[2] ||= (e) => i("update:open", e)
		}, {
			default: r(() => [l(rr, {
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
}), lr = /* @__PURE__ */ new Set([
	"failed",
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"password_confirmation_pending"
]), ur = /* @__PURE__ */ new Set([
	"running",
	"waiting",
	"stopping",
	"cancelling",
	"settling"
]), dr = /* @__PURE__ */ new Set([
	"cancelled",
	"stopped",
	"interrupted"
]), fr = {
	email_verification_pending: "待验证或补全",
	credential_pending_confirmation: "凭证待核验"
};
function pr(e, t, n) {
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${J(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function mr(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function hr(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: J("status", t),
		tone: V(t),
		title: pr("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = ae(e) || void 0) : ur.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = ae(e) || mr(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : lr.has(t) ? (r.label = "失败", r.tone = "danger") : dr.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (lr.has(n) && lr.has(t) || n === "completed" && t === "success" || n === "in_progress" && ur.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: fr[n] || J("target_status", n),
			tone: V(n),
			title: pr("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Z = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), gr = (e) => Array.isArray(e) ? e.map(U) : [], Q = (e) => String(e || "").toLowerCase(), $ = /* @__PURE__ */ new Set([
	"unknown",
	"request_unknown",
	"attention_required",
	"manual_reconcile",
	"unconfirmed",
	"password_confirmation_pending",
	"credential_pending_confirmation"
]), _r = /* @__PURE__ */ new Set([
	"failed",
	"error",
	"deactivated"
]);
function vr(e) {
	let t = e.error_info;
	if (!t) return !1;
	for (let e of ["cause_code", "code"]) {
		let n = Q(t[e]).trim();
		if (n) {
			if ($.has(n) || ["unknown.unclassified", "task.pending"].includes(n) || /(?:_receipt_missing|_failure_diagnostics_missing|_evidence_missing|_unconfirmed|_request_unknown|\.confirmation|\.safety)$/.test(n)) return !1;
			if (Ie({ [e]: n }) !== Ie()) return !0;
		}
	}
	return !1;
}
var yr = {
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
}, br = {
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
function xr(e, t) {
	let n = U(e.result_summary), r = Q(e.status), i = Q(n.extraction_status), a = Q(n.payment_status);
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
	].includes(r) ? Z("提链成功", "warning", "后续已中断") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Z("提链成功", "danger", "后续失败") : Z("提链成功", "success") : _r.has(i) || vr(e) ? Z(t, "danger") : $.has(i) ? Z("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Z("等待提链", "warning") : i === "running" ? Z("提链中", "active") : r === "cancelled" ? Z("已取消") : ["stopped", "interrupted"].includes(r) ? Z("执行已中断", "warning") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Z(t, "danger") : n.ok === !0 ? Z("提链流程完成", "success") : Z("提链结果缺失", "warning");
}
function Sr(e, t) {
	let n = U(e.result_summary), r = Q(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : gr(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes(Q(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = U(e.result);
		return !t && !e.last_success_at ? [] : gr(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : gr(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(U(e.result)).length > 0);
	if (s > 0 && o > 0 || !i && n.plan_check_partial === !0) return Z("部分失败", "warning", u ? "含历史数据" : void 0);
	if (c > 0 && s >= c) return u ? Z("查询失败", "danger", "含历史数据") : Z(t, "danger");
	if (vr(e)) return Z(t, "danger");
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
function Cr(e, t = "执行异常") {
	let n = U(e.result_summary), r = Q(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
	if (e.debug_pause) return Z("调试已暂停", "warning");
	if (["queued", "pending"].includes(r)) {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(yr[String(t)] || "等待执行", "warning");
	}
	if (r === "waiting") {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(yr[String(t)] || mr(e), "warning");
	}
	if (r === "running") return Z("执行中", "active");
	if (["stopping", "cancelling"].includes(r)) return Z("正在停止", "warning");
	if (r === "settling") return Z("正在收尾", "active");
	if (i === "extract_link") return xr(e, a);
	if (i === "email_change" && n.email_change_confirmed === !0) return Z("邮箱已换绑", "success", U(n.post_change_live_check).accepted ? "刷新已排队" : "刷新待处理");
	if (i === "codex_retry" && n.ok === !0) {
		let e = Q(U(n.sub2api_sync).status);
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
	if (i === "plan_check") return Sr(e, a);
	if (r === "cancelled") return Z("已取消");
	if (["stopped", "interrupted"].includes(r)) return Z("执行已中断", "warning");
	if (vr(e)) return Z(a, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes(Q(e.target_status)) || r === "deactivated") return Z("账号已停用", "danger");
	let o = i === "sub2api_scan" || i === "c2a_scan";
	if (e.error_message || e.error_info || _r.has(r) || !o && n.ok === !1) return Z(a, "danger");
	if (r === "partial_success") return Z("部分完成", "warning");
	if (o) return r === "success" ? Z(i === "c2a_scan" && n.continuation_only === !0 ? "接续检查完成" : br[i], "success") : Z("扫描未完成", "warning");
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
	return i === "deactivation_mail" && typeof n.detected == "boolean" ? Z(n.detected ? "发现封号邮件" : "未见封号邮件", n.detected ? "warning" : "neutral") : i === "live_check" && n.ok === !0 ? Z("账号正常", "success") : i === "token_refresh" && n.ok === !0 ? Z("令牌已刷新", "success") : i === "account_inspection_batch" && Number(n.failed_count) > 0 ? Z("巡检已完成", "warning", "存在失败") : r === "success" || n.ok === !0 ? Z(br[i] || "任务已完成", "success") : Z("结果未记录");
}
// src/features/tasks/TaskResultCell.vue
var wr = /* @__PURE__ */ t({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, i = E(() => Cr(t.task, Ie(t.task.error_info))), a = E(() => [...new Set([
			se(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? B(t.task.error_info, t.task.error_message) : "",
			t.task.error_message,
			t.task.error_code,
			t.task.error_info?.code,
			t.task.error_info?.cause_code
		].filter((e) => !!e))]);
		return (e, t) => (n(), x(Fe, w(i.value, { title: a.value.join("\n") }), {
			details: r(() => [(n(!0), j(g, null, o(a.value, (e, t) => (n(), j("p", { key: t }, b(e), 1))), 128))]),
			_: 1
		}, 16, ["title"]));
	}
}), Tr = ["aria-busy"], Er = [
	"checked",
	"indeterminate",
	"disabled"
], Dr = {
	"data-label": "选择",
	class: "ui-col-check"
}, Or = [
	"checked",
	"aria-label",
	"onChange"
], kr = { "data-label": "ID" }, Ar = ["onClick"], jr = { "data-label": "类型" }, Mr = { "data-label": "目标" }, Nr = { key: 0 }, Pr = {
	key: 1,
	class: "tc-muted-placeholder"
}, Fr = {
	key: 1,
	class: "tc-muted-placeholder",
	"aria-label": "无目标"
}, Ir = { "data-label": "执行状态" }, Lr = ["title"], Rr = ["title"], zr = { "data-label": "目标状态" }, Br = ["title"], Vr = {
	key: 1,
	class: "tc-cell-line tc-muted-placeholder",
	"aria-label": "无额外目标状态"
}, Hr = { "data-label": "批次 / 触发" }, Ur = ["onClick"], Wr = { "data-label": "运行次数" }, Gr = { "data-label": "当前步骤" }, Kr = {
	"data-label": "创建 / 完成",
	class: "ui-time"
}, qr = { "data-label": "结果 / 错误" }, Jr = { "data-label": "操作" }, Yr = { class: "ui-row-actions tc-row-actions" }, Xr = ["onClick"], Zr = ["disabled", "onClick"], Qr = ["disabled", "onClick"], $r = ["disabled", "onClick"], ei = /* @__PURE__ */ t({
	__name: "TaskTable",
	props: {
		items: {},
		selected: {},
		loading: { type: Boolean },
		error: {},
		busy: { type: Boolean },
		filters: { default: Be },
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
			...hr(e)
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
		], { widths: m, resize: h, resizeWithKeyboard: v, resetColumns: y } = Ne({
			defaults: [
				40,
				72,
				148,
				198,
				108,
				112,
				145,
				88,
				204,
				176,
				170,
				145
			],
			storageKey: "turb_task_center_columns",
			min: 65,
			max: 800,
			savedMin: 40
		});
		function C(e) {
			return e.account_id ? `账号 #${e.account_id}` : e.attempt_id ? `注册尝试 #${e.attempt_id}` : "";
		}
		function w(e) {
			return String(e.email_snapshot || e.email || "").trim();
		}
		function ee(e) {
			return W(e) || e.current_stage_label || J("stage", e.current_stage);
		}
		function D(e) {
			return [
				e.current_stage_label || J("stage", e.current_stage),
				W(e),
				ge(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function O(e) {
			return String(e.bulk_batch_id || U(e.bulk_context).batch_id || "");
		}
		function k(e) {
			return String(e.bulk_round_id || U(e.bulk_context).round_id || "");
		}
		return t({ resetColumns: y }), (t, i) => (n(), j("div", {
			class: "ui-table-scroll tc-table-scroll",
			tabindex: "0",
			"aria-label": "任务列表，可横向滚动",
			"aria-busy": e.loading
		}, [S("table", {
			class: "ui-table ui-table--sticky-end ui-table--cards tc-table",
			style: _({ "--ui-table-width": `${A(m).reduce((e, t) => e + t, 0)}px` })
		}, [
			i[3] ||= S("caption", { class: "ui-sr-only" }, "任务中心列表，选择任务可批量操作", -1),
			S("colgroup", null, [(n(!0), j(g, null, o(A(m), (e, t) => (n(), j("col", {
				key: t,
				style: _({ width: `${e}px` })
			}, null, 4))), 128))]),
			S("thead", null, [S("tr", null, [(n(), j(g, null, o(f, (t, r) => S("th", {
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
			}, null, 40, Er)) : (n(), j(g, { key: 1 }, [A(Fn)[r - 1] ? (n(), x(cr, {
				key: 0,
				column: A(Fn)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === A(Fn)[r - 1].key,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:filters", e),
				"onUpdate:open": (e) => s("update:openFilter", e ? A(Fn)[r - 1].key : null)
			}, null, 8, [
				"column",
				"model-value",
				"facets",
				"open",
				"onUpdate:open"
			])) : (n(), j(g, { key: 1 }, [M(b(t), 1)], 64)), r < f.length - 1 ? (n(), x(Pe, {
				key: 2,
				label: t,
				onStart: (e) => A(h)(r, e),
				onNudge: (e) => A(v)(r, e)
			}, null, 8, [
				"label",
				"onStart",
				"onNudge"
			])) : p("", !0)], 64))], 2)), 64))])]),
			S("tbody", null, [(n(!0), j(g, null, o(d.value, ({ task: t, execution: i, target: a }) => (n(), j("tr", {
				key: t.id,
				class: T({ "is-selected": e.selected.has(t.id) })
			}, [
				S("td", Dr, [S("input", {
					type: "checkbox",
					checked: e.selected.has(t.id),
					"aria-label": `选择任务 #${t.id}`,
					onChange: (e) => s("select", t.id, e.target.checked)
				}, null, 40, Or)]),
				S("td", kr, [S("button", {
					type: "button",
					class: "ui-link tc-task-id",
					onClick: (e) => s("detail", t.id)
				}, "#" + b(t.id), 9, Ar)]),
				S("td", jr, [l(X, { text: A(J)("task_type", t.task_type) }, null, 8, ["text"])]),
				S("td", Mr, [C(t) || w(t) ? (n(), x(X, {
					key: 0,
					text: C(t) || "—",
					secondary: w(t) || void 0
				}, {
					default: r(() => [C(t) ? (n(), j("strong", Nr, b(C(t)), 1)) : (n(), j("span", Pr, "—"))]),
					_: 2
				}, 1032, ["text", "secondary"])) : (n(), j("span", Fr, "—"))]),
				S("td", Ir, [S("span", {
					class: T(["ui-badge tc-badge", `ui-badge--${i.tone}`]),
					title: i.title
				}, b(i.label), 11, Lr), i.secondary ? (n(), j("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: i.secondary
				}, b(i.secondary), 9, Rr)) : p("", !0)]),
				S("td", zr, [a ? (n(), j("span", {
					key: 0,
					class: T(["ui-badge tc-badge", `ui-badge--${a.tone}`]),
					title: a.title
				}, b(a.label), 11, Br)) : (n(), j("span", Vr, "—"))]),
				S("td", Hr, [l(X, {
					text: t.batch_title || t.batch_uuid || (O(t) ? "查看批次" : "单任务"),
					secondary: A(J)("trigger", t.trigger)
				}, {
					default: r(() => [O(t) ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: (e) => s("batch", O(t), k(t))
					}, b(t.batch_title || t.batch_uuid || "查看批次"), 9, Ur)) : (n(), j(g, { key: 1 }, [M(b(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				S("td", Wr, [l(X, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				S("td", Gr, [l(X, {
					text: ee(t),
					secondary: A(ge)(t.duration_ms),
					title: D(t),
					tone: A(W)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				S("td", Kr, [l(X, {
					text: A(ke)(t.created_at),
					secondary: A(ke)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				S("td", qr, [l(wr, { task: t }, null, 8, ["task"])]),
				S("td", Jr, [S("div", Yr, [
					S("button", {
						type: "button",
						class: "ui-link",
						onClick: (e) => s("detail", t.id)
					}, "详情", 8, Xr),
					A(De)(t) ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						disabled: e.busy,
						onClick: (e) => s("action", t, "retry")
					}, "重跑", 8, Zr)) : p("", !0),
					A(ce)(t) ? (n(), j("button", {
						key: 1,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "terminate")
					}, b(t.status === "queued" ? "取消" : "终止"), 9, Qr)) : p("", !0),
					A(ie)(t) ? p("", !0) : (n(), j("button", {
						key: 2,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "delete")
					}, "删除", 8, $r))
				])])
			], 2))), 128)), e.items.length ? p("", !0) : (n(), x(je, {
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
		], 4)], 8, Tr));
	}
}), ti = /* @__PURE__ */ t({
	__name: "StatusBadge",
	props: {
		value: {},
		group: { default: "status" }
	},
	setup(e) {
		return (t, r) => (n(), j("span", { class: T(["ui-badge tc-badge", `ui-badge--${A(V)(e.value)}`]) }, b(A(J)(e.group, e.value)), 3));
	}
});
// src/features/tasks/useTaskList.ts
function ni() {
	let t = c(Be()), n = v(1), r = v(20), a = v(0), o = v([]), s = v({}), l = v(/* @__PURE__ */ new Set()), u = v(!1), d = v(""), p = v(!1), m = E(() => Math.max(1, Math.ceil(a.value / r.value))), h = 0, g = null, _, y, b = 0, x = 0, S = "", C = "", w = !1, ee = /* @__PURE__ */ new Set([
		"task_id",
		"target",
		"batch",
		"result"
	]), T, D = () => JSON.stringify({ ...t }), O = (e = D()) => w && (S !== e || Date.now() - x >= 3e4);
	function k(t = 0) {
		clearTimeout(y);
		let n = ++b, r = () => {
			n === b && p.value && !document.hidden && j();
		};
		t ? y = setTimeout(r, t) : e(r);
	}
	let A = () => {
		clearTimeout(_), p.value && !document.hidden && (_ = setTimeout(() => void j(), 5e3));
	};
	async function j(e = {}) {
		clearTimeout(_), clearTimeout(y), ++b;
		let i = {
			...t,
			page: n.value,
			page_size: r.value
		}, c = JSON.stringify(i), f = D(), p = !!(e.metadata || O(f)), v = ++h;
		g?.abort(), g = new AbortController(), u.value = !0;
		try {
			let e = await Ke.list({
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
			v === h && !N(e) && (d.value = e instanceof Error ? e.message : "任务列表加载失败");
		} finally {
			v === h && (u.value = !1, g = null, !p && O() ? k() : A());
		}
	}
	function M(e) {
		e !== p.value && (p.value = e, clearTimeout(_), clearTimeout(y), e && !document.hidden ? k() : (++b, g?.abort(), ++h, u.value = !1));
	}
	function P(e) {
		e !== w && (w = e, !u.value && O() && p.value && !document.hidden && k());
	}
	function F(e, r = !0) {
		Object.assign(t, r ? {
			...Be(),
			...e
		} : e), n.value = 1, l.value = /* @__PURE__ */ new Set();
	}
	function I(e, t) {
		let n = new Set(l.value);
		t ? n.add(e) : n.delete(e), l.value = n;
	}
	function te(e) {
		l.value = new Set(e ? o.value.map((e) => e.id) : []);
	}
	i(() => ({
		...t,
		page: n.value,
		page_size: r.value
	}), (e, r) => {
		l.value = /* @__PURE__ */ new Set(), clearTimeout(_);
		let i = Object.keys(t).filter((t) => e[t] !== r[t]);
		if (i.length && (s.value = {}, S = "", T = i.every((e) => ee.has(e)) && e.page_size === r.page_size ? 260 : 0, n.value !== 1)) {
			n.value = 1;
			return;
		}
		let a = T ?? 0;
		T = void 0, ++h, g?.abort(), k(a);
	});
	let L = () => {
		clearTimeout(_), document.hidden ? (++b, clearTimeout(y), g?.abort(), ++h, u.value = !1) : p.value && k();
	};
	return document.addEventListener("visibilitychange", L), f(() => {
		++h, ++b, g?.abort(), clearTimeout(_), clearTimeout(y), document.removeEventListener("visibilitychange", L);
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
		refresh: j,
		setVisible: M,
		setFacetsVisible: P,
		applyFilters: F,
		toggle: I,
		togglePage: te
	};
}
// src/features/tasks/useReceipts.ts
var ri = ({ task_id: e, run_id: t }) => `${e}:${t ?? ""}`;
function ii() {
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
			let e = await Ke.receipts(i, l.signal);
			if (o !== c) return;
			let t = new Map(e.items.map((e) => [ri(e), e]));
			for (let e of i) {
				let n = t.get(ri(e));
				n ? (e.status = n.status || "queued", e.message = n.message || (n.status === "success" ? "已确认完成" : "")) : r.value = e.run_id === null ? "部分回执暂未读到，请稍后刷新。" : "部分执行记录暂未读到，请稍后刷新。";
			}
		} catch (e) {
			o === c && !N(e) && (r.value = "回执暂未读到，请稍后刷新。");
		} finally {
			o === c && (n.value = !1, l = null, u());
		}
	}
	function p(t, n) {
		for (let i of t) if (i.accepted) try {
			let t = I(i.task_id), r = L(i.run_id), a = ri({
				task_id: t,
				run_id: r
			});
			if (e.value.some((e) => ri(e) === a)) continue;
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
var ai = {
	class: "tc-root",
	"aria-label": "统一任务中心"
}, oi = {
	key: 0,
	class: "tc-receipts",
	"aria-label": "本次提交的任务回执"
}, si = { class: "tc-receipts-header" }, ci = { role: "status" }, li = ["disabled"], ui = {
	key: 0,
	class: "tc-text-danger",
	role: "alert"
}, di = { class: "tc-receipt-list" }, fi = ["onClick"], pi = { class: "ui-list tc-workspace" }, mi = {
	class: "ui-list-count tc-count",
	role: "status"
}, hi = {
	class: "tc-target-search",
	role: "search"
}, gi = ["value", "onKeydown"], _i = {
	key: 0,
	class: "tc-selection",
	role: "status"
}, vi = {
	key: 1,
	class: "tc-bulk-actions",
	role: "group",
	"aria-label": "选中任务批量操作"
}, yi = ["disabled", "onClick"], bi = ["title"], xi = ["disabled"], Si = ["role"], Ci = { key: 1 }, wi = /* @__PURE__ */ t({
	__name: "TaskCenter",
	emits: [
		"navigate",
		"batch",
		"changed"
	],
	setup(t, { expose: s, emit: c }) {
		let u = c, f = ni(), m = ii(), { filters: _, page: y, size: x, pages: w, total: D, items: O, facets: N, selected: P, loading: F, error: I, visible: te } = f, { items: L, pending: R, error: z, loading: ne } = m, ae = v(null), B = v(null), V = v(!1), H = v(""), W = v(""), se = v(null), G = v(null), ce = v(_.target || ""), le;
		i(() => _.target, (e) => {
			clearTimeout(le), ce.value = e || "";
		}), C(() => clearTimeout(le)), i(se, (e) => {
			f.setFacetsVisible(e === "mobile" || Fn.some((t) => t.key === e && t.kind === "select"));
		});
		let K = E(() => Fn.filter((e) => In(e, _))), ue = E(() => K.value.map((e) => ({
			key: e.key,
			label: `${e.label}：${Ln(e, _, N.value)}`,
			removeLabel: `清除${e.label}筛选`
		}))), de = v([]), fe = E(() => O.value.filter((e) => P.value.has(e.id))), pe = E(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, fe.value.filter((t) => oe(t, e)).length]))), me = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, he = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function q(e) {
			Object.assign(_, e);
		}
		function J(e) {
			clearTimeout(le);
			let t = e.trim();
			t !== (_.target || "") && q({
				..._,
				target: t
			});
		}
		function ge(e) {
			ce.value = e, clearTimeout(le), le = setTimeout(() => J(e), 250);
		}
		function _e() {
			clearTimeout(le), ce.value = "", J(""), G.value?.focus();
		}
		function ve(e) {
			let t = Fn.find((t) => t.key === e);
			t && q(Rn(t, _));
		}
		function ye(e, t, n) {
			ae.value?.open(e, t, n);
		}
		async function be(t = {}) {
			t.filters && f.applyFilters(t.filters), t.taskId && (await e(), ye(t.taskId, t.runId, t.stepId));
		}
		function xe(e) {
			e || (se.value = null), f.setVisible(e), m.setVisible(e);
		}
		function Se() {
			ae.value?.close();
		}
		function Ce(e, t = "任务", n = {}) {
			m.track(e, t), n.navigate !== !1 && u("navigate");
		}
		async function we(e = {}) {
			te.value && await f.refresh(e);
		}
		function Te() {
			we(), u("changed");
		}
		async function Ee(e, t) {
			if (!V.value && !(t === "delete" && ie(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				V.value = !0, W.value = "", de.value = [], H.value = "";
				try {
					let n = await Ke.action(e.id, t), r = U(n.data || n);
					H.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", P.value.delete(e.id), await we(), u("changed");
				} catch (e) {
					W.value = `${me[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					V.value = !1;
				}
			}
		}
		async function De(e) {
			if (V.value) return;
			let t = fe.value.filter((t) => oe(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${me[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				V.value = !0, W.value = "", H.value = "", de.value = [];
				try {
					let n = t.map((e) => e.id), r = e === "terminate" ? await Ke.bulk(e, n, { onAccepted: (e) => {
						H.value = `终止请求已受理，正在等待结果（命令 ${e.command_id}）`;
					} }) : await Ke.bulk(e, n), i = Array.isArray(r.accepted) ? r.accepted : [];
					de.value = (r.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let a = Number(r.accepted_count ?? i.length);
					if (e === "cancel") {
						let e = i.filter((e) => e.state === "cancelled").length, t = i.filter((e) => e.state === "cancelling").length;
						H.value = `已取消 ${e} 个，取消中 ${t} 个${a - e - t > 0 ? `，已受理 ${a - e - t} 个` : ""}`;
					} else H.value = `已${me[e]} ${a} 个`;
					let o = new Set(i.map((e) => String(e.task_id)));
					P.value = new Set([...P.value].filter((e) => !o.has(String(e)))), de.value.length && (H.value += `，跳过 ${de.value.length} 个`), await we(), u("changed");
				} catch (t) {
					W.value = t instanceof re ? t.message : `${me[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					V.value = !1;
				}
			}
		}
		return s({
			open: be,
			refresh: we,
			track: Ce,
			closeDetail: Se,
			setVisible: xe
		}), (e, t) => (n(), j(g, null, [a(S("section", ai, [A(L).length ? (n(), j("section", oi, [
			S("div", si, [S("div", null, [t[13] ||= S("strong", null, "本次提交", -1), S("span", ci, "共 " + b(A(L).length) + " 项 · 等待/执行 " + b(A(R).length) + " · 成功 " + b(A(L).filter((e) => e.status === "success").length) + " · 失败或待处理 " + b(A(L).length - A(R).length - A(L).filter((e) => e.status === "success").length), 1)]), S("button", {
				type: "button",
				class: "ui-button",
				disabled: A(ne) || !A(R).length,
				onClick: t[0] ||= (e) => A(m).refresh()
			}, "刷新回执", 8, li)]),
			A(z) ? (n(), j("p", ui, b(A(z)), 1)) : p("", !0),
			S("details", null, [t[14] ||= S("summary", null, "查看任务与最终结果", -1), S("ul", di, [(n(!0), j(g, null, o(A(L), (e) => (n(), j("li", { key: `${e.task_id}:${e.run_id}` }, [
				S("button", {
					type: "button",
					class: "ui-link",
					onClick: (t) => ye(e.task_id, e.run_id)
				}, b(e.label) + " #" + b(e.task_id), 9, fi),
				l(ti, { value: e.status }, null, 8, ["value"]),
				S("span", null, b(e.message), 1)
			]))), 128))])])
		])) : p("", !0), S("div", pi, [
			l(Re, { filtered: K.value.length > 0 }, {
				actions: r(() => [
					l(sr, {
						"model-value": A(_),
						facets: A(N),
						open: se.value === "mobile",
						"onUpdate:modelValue": q,
						"onUpdate:open": t[3] ||= (e) => se.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					K.value.length ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: t[4] ||= (e) => A(f).applyFilters({})
					}, "清除全部筛选")) : p("", !0),
					S("span", {
						class: "tc-timezone",
						title: A(he)
					}, "时间按 " + b(A(he)) + " 显示", 9, bi),
					S("button", {
						type: "button",
						class: "ui-link",
						onClick: t[5] ||= (e) => B.value?.resetColumns()
					}, "恢复列宽"),
					S("button", {
						id: "btnRefreshTasksV2",
						type: "button",
						class: "ui-button",
						disabled: A(F),
						onClick: t[6] ||= (e) => A(f).refresh()
					}, b(A(F) ? "刷新中…" : "刷新"), 9, xi)
				]),
				default: r(() => [
					S("span", mi, b(A(D).toLocaleString()) + " 个任务", 1),
					S("div", hi, [S("input", {
						ref_key: "targetInput",
						ref: G,
						type: "search",
						value: ce.value,
						placeholder: "搜索目标邮箱 / 账号...",
						"aria-label": "搜索任务目标",
						autocomplete: "off",
						onInput: t[1] ||= (e) => ge(e.target.value),
						onKeydown: [t[2] ||= h(ee((e) => J(ce.value), ["prevent"]), ["enter"]), h(ee(_e, ["prevent"]), ["esc"])]
					}, null, 40, gi), ce.value ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "tc-target-search__clear",
						"aria-label": "清空目标搜索",
						title: "清空目标搜索",
						onClick: _e
					}, "×")) : p("", !0)]),
					fe.value.length ? (n(), j("span", _i, "已选 " + b(fe.value.length) + " 项", 1)) : p("", !0),
					fe.value.length ? (n(), j("div", vi, [(n(), j(g, null, o([
						"retry",
						"cancel",
						"terminate",
						"delete"
					], (e) => S("button", {
						key: e,
						type: "button",
						class: T(["ui-button", { "ui-button--danger": e === "delete" || e === "terminate" }]),
						disabled: V.value || !pe.value[e],
						onClick: (t) => De(e)
					}, b(me[e]) + b(pe.value[e] ? `（${pe.value[e]}）` : ""), 11, yi)), 64))])) : p("", !0),
					l(Me, {
						items: ue.value,
						onRemove: ve
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			H.value || W.value || A(I) && A(O).length ? (n(), j("div", {
				key: 0,
				class: T(["ui-list-feedback tc-feedback", { "is-error": W.value || A(I) }]),
				role: W.value || A(I) ? "alert" : "status"
			}, [
				M(b(W.value || A(I) || H.value), 1),
				A(I) ? (n(), j("button", {
					key: 0,
					type: "button",
					class: "ui-link",
					onClick: t[7] ||= (e) => A(f).refresh()
				}, "重试")) : p("", !0),
				de.value.length ? (n(), j("details", Ci, [t[15] ||= S("summary", null, "查看跳过原因", -1), S("ul", null, [(n(!0), j(g, null, o(de.value, (e) => (n(), j("li", { key: e.id }, "#" + b(e.id) + "：" + b(e.message), 1))), 128))])])) : p("", !0)
			], 10, Si)) : p("", !0),
			l(ei, {
				ref_key: "table",
				ref: B,
				filters: A(_),
				facets: A(N),
				"open-filter": se.value,
				"onUpdate:openFilter": t[8] ||= (e) => se.value = e,
				"onUpdate:filters": q,
				items: A(O),
				selected: A(P),
				loading: A(F),
				error: A(I),
				busy: V.value,
				onSelect: A(f).toggle,
				onSelectPage: A(f).togglePage,
				onDetail: ye,
				onAction: Ee,
				onBatch: t[9] ||= (e, t) => u("batch", e, t),
				onRetry: t[10] ||= (e) => A(f).refresh()
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
			l(Le, {
				page: A(y),
				"onUpdate:page": t[11] ||= (e) => d(y) ? y.value = e : null,
				size: A(x),
				"onUpdate:size": t[12] ||= (e) => d(x) ? x.value = e : null,
				pages: A(w),
				total: A(D),
				busy: A(F)
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy"
			])
		])], 512), [[k, A(te)]]), l(Pn, {
			ref_key: "detail",
			ref: ae,
			onRefresh: Te
		}, null, 512)], 64));
	}
});
// src/main.ts
function Ti(e, t = {}) {
	return D(wi, t).mount(e);
}
export { Ti as mountTaskCenter };
