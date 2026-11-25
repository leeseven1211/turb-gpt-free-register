import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, V as u, X as d, Z as f, _ as p, a as m, c as h, d as g, dt as _, et as v, f as y, ft as b, g as x, h as S, j as C, k as w, l as T, lt as E, m as D, n as O, nt as k, s as A, st as j, v as M, x as N } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { n as P, r as F, t as I } from "./client-B5R_MNgP.js";
import { a as L, i as ee, n as te, r as R } from "./taskIds-BlchWwUp.js";
import { a as z, n as B, t as ne } from "./bulkMutations-3wwPI3-H.js";
import { A as re, C as ie, D as V, E as ae, F as H, M as U, N as W, O as oe, P as se, S as G, T as ce, _ as le, a as K, b as ue, c as de, d as fe, f as pe, g as me, h as he, i as q, j as J, k as ge, l as _e, m as ve, n as ye, o as be, p as xe, r as Se, s as Ce, t as we, u as Te, v as Ee, w as De, x as Y, y as Oe } from "./StepEvidence-lbLgrLzP.js";
import { n as ke } from "./time-DOD6oyhP.js";
import { i as Ae, n as je, r as X, t as Me } from "./ListFilterSummary-DsJDWIjH.js";
import { n as Ne, t as Pe } from "./ColumnResizer-C2889-lj.js";
import { t as Fe } from "./ListResult-BADeMxD2.js";
import { t as Ie } from "./errorLabels-fdGNkTBr.js";
import { t as Le } from "./ListPagination-CSFkV2Gz.js";
import { t as Re } from "./ListToolbar-Dl7q1T_K.js";
// src/api/tasks.ts
var ze = (e, t = {}) => F(e, t, R);
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
async function He(e, t, n) {
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
			...n ? { body: Ue(t, n) } : {}
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
function Ue(e, t) {
	if (e !== "/api/operations/bulk") return JSON.stringify(t);
	let { task_ids: n, ...r } = t;
	if (!Array.isArray(n)) return JSON.stringify(t);
	let i = JSON.stringify(r).slice(0, -1);
	return `${i}${i.length > 1 ? "," : ""}"task_ids":[${n.map((e) => String(L(e))).join(",")}]}`;
}
async function We(e, t = {}) {
	let n = await z((t, n) => n?.method === "POST" ? B(t, {
		...n,
		body: Ue(t, {
			action: "terminate",
			task_ids: e
		})
	}) : B(t, n), "/api/operations/bulk", {
		action: "terminate",
		task_ids: e
	}, t);
	if (!Array.isArray(n.items)) return n;
	let r = n.items.filter((e) => e.status === "updated").map((e) => ({
		task_id: L(e.key),
		state: String(e.data?.state || "stopped"),
		message: String(e.data?.message || "")
	})), i = n.items.filter((e) => e.status !== "updated").map((e) => ({
		task_id: L(e.key),
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
var Ge = {
	list: (e, t) => ze(`/api/operations?${Ve(e)}`, { signal: t }),
	detail: (e, t) => ze(`/api/operations/${L(e)}?include_events=0`, { signal: t }),
	progress: (e, t, n) => ze(`/api/operations/${L(e)}/runs/${L(t)}/progress`, { signal: n }),
	events: (e, t, n = {}, r) => ze(`/api/operations/${L(e)}/runs/${L(t)}/events?${Ve({
		limit: 500,
		...n
	})}`, { signal: r }),
	logs: (e, t, n = {}, r) => ze(`/api/operations/${L(e)}/runs/${L(t)}/logs?${Ve({
		limit: 500,
		...n
	})}`, { signal: r }),
	action: (e, t) => t === "retry" ? He(`retry:${L(e)}`, `/api/operations/${L(e)}/retry`) : ze(`/api/operations/${L(e)}/${t}`, { method: "POST" }),
	bulk: (e, t, n) => e === "terminate" ? We(t, n) : e === "retry" ? He("bulk:retry", "/api/operations/bulk", {
		action: e,
		task_ids: t
	}) : ze("/api/operations/bulk", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: Ue("/api/operations/bulk", {
			action: e,
			task_ids: t
		})
	})
}, Ke = (e) => e instanceof Error ? e.message : "读取失败，请重试";
function qe(e = Ge, t = () => {}) {
	let n = v(!1), r = v(!0), i = v(null), a = v(null), o = k(null), s = k(null), c = k([]), l = k([]), u = v("events"), d = v(null), p = v(""), m = v(""), h = v(""), g = v(""), _ = v(!1), y = v(!1), b = v(!1), x = v(null), S = v(null), C = v("tail"), w = v("tail"), T = v(!1), E = v(!1), O = v(!1), A = v(!1), j = v(!0), M = D(() => o.value?.runs || []), N = D(() => M.value.find((e) => ee(e.id, a.value))), P = 0, F = 0, I = 0, R = 0, z = null, B, ne = new AbortController(), ie = !1;
	function V() {
		B !== void 0 && clearTimeout(B), B = void 0;
	}
	function ae() {
		P += 1, ne.abort(), ne = new AbortController(), z = null, _.value = y.value = b.value = !1, V();
	}
	let H = (e) => e === P && n.value, U = () => n.value && r.value && !!i.value;
	function W() {
		V(), U() && (!o.value || re(o.value)) && (B = setTimeout(() => void K(!0), 2e3));
	}
	function oe() {
		F += 1, I += 1, y.value = b.value = !1, s.value = null, m.value = h.value = g.value = "", c.value = [], l.value = [], x.value = S.value = null, T.value = E.value = O.value = A.value = !1, C.value = w.value = "tail", j.value = !0;
	}
	async function se(t = "incremental") {
		if (!U() || !a.value || !i.value || t === "incremental" && y.value || t === "incremental" && C.value === "start" && E.value || t === "next" && !E.value) return;
		let n = P, r = ++F, o = t === "tail" || t === "start" || x.value === null, s = {
			limit: 500,
			...t === "start" ? { after_id: 0 } : t !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		y.value = !0;
		try {
			let l = await e.events(i.value, a.value, s, ne.signal);
			if (!H(n) || r !== F) return;
			c.value = o ? l.items : xe(c.value, l.items), x.value = l.next_after_id, (t === "tail" || t === "start") && (C.value = t), o && C.value === "tail" ? (T.value = l.has_more, E.value = !1) : (E.value = l.has_more, C.value === "start" && (T.value = !1)), h.value = "";
		} catch (e) {
			H(n) && r === F && (h.value = Ke(e));
		} finally {
			H(n) && r === F && (y.value = !1);
		}
	}
	async function G(t = "incremental") {
		if (!U() || !a.value || !i.value || t === "incremental" && b.value || t === "incremental" && w.value === "start" && A.value || t === "next" && !A.value) return;
		let n = P, r = ++I, o = t === "tail" || t === "start" || S.value === null, s = {
			limit: 500,
			...t === "start" ? { cursor: 0 } : t !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		b.value = !0;
		try {
			let c = await e.logs(i.value, a.value, s, ne.signal);
			if (!H(n) || r !== I) return;
			l.value = o ? c.items : [...l.value, ...c.items], S.value = c.next_cursor, (t === "tail" || t === "start") && (w.value = t), A.value = c.has_more, O.value = w.value === "tail" && c.available, j.value = c.available, g.value = "";
		} catch (e) {
			H(n) && r === I && (g.value = Ke(e));
		} finally {
			H(n) && r === I && (b.value = !1);
		}
	}
	async function ce(t) {
		if (i.value && a.value) try {
			let n = await e.progress(i.value, a.value, ne.signal);
			if (!H(t)) return;
			s.value = n.progress, m.value = "";
		} catch (e) {
			H(t) && (m.value = Ke(e));
		}
	}
	function le() {
		return K(!1);
	}
	function K(e) {
		if (!U() || !i.value) return Promise.resolve();
		if (e || (_.value = !0), z) return z;
		let t = P, n = ++R;
		return z = ue(t, n).finally(() => {
			H(t) && n === R && (z = null, _.value = !1, W());
		}), z;
	}
	async function ue(n, r) {
		if (i.value) {
			V();
			try {
				let s = await e.detail(i.value, ne.signal);
				if (!H(n) || r !== R) return;
				o.value = s.task;
				let c = s.task.runs || [];
				if (a.value && !c.some((e) => ee(e.id, a.value))) {
					oe(), p.value = `所选运行 #${a.value} 不存在或已不可用，请选择其他运行。`;
					return;
				}
				let l = a.value || s.task.last_run_id || c.at(-1)?.id || null, d = c.some((e) => ee(e.id, l)) ? l : c.at(-1)?.id || null;
				if (d !== a.value && (oe(), a.value = d), p.value = "", a.value && await Promise.allSettled([
					ce(n),
					se(),
					...u.value === "logs" ? [G()] : []
				]), !H(n)) return;
				!re(s.task) && !ie && (ie = !0, t());
			} catch (e) {
				H(n) && (p.value = Ke(e));
			}
		}
	}
	function de(e, t, r) {
		return ae(), n.value = !0, i.value = L(e), a.value = te(t), o.value = null, p.value = "", u.value = "events", d.value = r || null, ie = !1, oe(), le();
	}
	function fe() {
		n.value = !1, ae();
	}
	function pe(e) {
		if (e = L(e), !ee(e, a.value)) return ae(), a.value = e, d.value = null, oe(), le();
	}
	function me(e) {
		if (u.value = e, e === "logs") return G();
	}
	function he(e) {
		r.value !== e && (r.value = e, e ? n.value && le() : ae());
	}
	return f(fe), {
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
var Je = {
	key: 0,
	class: "tc-progress-failure tc-task-failure"
}, Ye = { key: 0 }, Xe = { key: 1 }, Ze = {
	key: 2,
	class: "tc-failure-secondary"
}, Qe = { key: 3 }, $e = { key: 0 }, et = { key: 1 }, tt = { key: 2 }, nt = /* @__PURE__ */ t({
	__name: "TaskFailure",
	props: {
		failure: {},
		execution: {},
		status: {}
	},
	setup(e) {
		let t = e, r = D(() => !!(t.execution?.error_message || t.execution?.error_info)), i = D(() => (t.failure?.country_failures || []).filter((e) => G(e.country).trim())), a = D(() => {
			let e = t.failure;
			return e ? i.value.length && !e.error_info?.auto_refresh_at_failed ? `${i.value.length} 个国家查询失败，展开查看具体原因` : Te(e) : "";
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
			].includes(n) && n !== e.stage ? J("stage", n) : [e.label || e.step_id || "阶段记录缺失", e.stage].filter(Boolean).join(" · ");
		}), c = D(() => r.value ? V(t.execution?.error_info, t.execution?.error_message) : ""), l = D(() => {
			if (!t.failure || !r.value) return !1;
			let e = (e) => G(e).replace(/\s+/g, " ").trim(), n = t.failure, i = n.error_info, a = t.execution?.error_info, o = e(n.message), s = e(t.execution?.error_message);
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
		return (t, d) => e.failure || r.value ? (n(), M("details", Je, [
			S("summary", null, [
				e.failure ? (n(), M("strong", Ye, b(j(_e)(e.failure) ? "历史失败位置" : "失败位置") + "：" + b(s.value), 1)) : (n(), M("strong", Xe, "执行失败")),
				S("span", null, b(a.value || c.value), 1),
				e.failure && r.value && !l.value ? (n(), M("span", Ze, "执行错误：" + b(c.value), 1)) : p("", !0),
				e.execution?.error_info?.display_code ? (n(), M("small", Qe, b(e.execution.error_info.display_code), 1)) : p("", !0)
			]),
			i.value.length ? (n(), M("ul", $e, [(n(!0), M(g, null, o(i.value, (e, t) => (n(), M("li", { key: t }, b(e.country) + "：" + b(e.summary || "诊断记录不完整"), 1))), 128))])) : p("", !0),
			e.failure?.event_id ? (n(), M("p", et, "关联事件 " + b(e.failure.event_id), 1)) : p("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(j(G)(e.status)) ? (n(), M("p", tt, "原请求证据已保留")) : p("", !0),
			S("pre", null, b(JSON.stringify(u.value, null, 2)), 1)
		])) : p("", !0);
	}
}), rt = {
	key: 0,
	class: "tc-progress",
	"aria-label": "执行进度"
}, it = { class: "tc-progress-heading" }, at = { key: 0 }, ot = ["data-step-count"], st = [
	"aria-pressed",
	"title",
	"onClick"
], ct = {
	key: 0,
	class: "tc-step-dot",
	"aria-hidden": "true"
}, lt = {
	key: 1,
	class: "tc-step-meta"
}, ut = { key: 0 }, dt = {
	key: 2,
	class: "tc-step-meta"
}, ft = { key: 0 }, pt = {
	key: 3,
	class: "tc-step-deps"
}, mt = ["aria-label", "onClick"], ht = {
	key: 1,
	class: "tc-detail-muted"
}, gt = {
	key: 2,
	class: "tc-flow-relations"
}, _t = { class: "tc-flow-relations__count" }, vt = { class: "tc-flow-relations__panel" }, yt = { class: "tc-flow-relations__hint" }, bt = { class: "tc-flow-relations__grid" }, xt = { class: "tc-flow-relation__head" }, St = {
	key: 0,
	class: "tc-flow-relation__status"
}, Ct = {
	key: 3,
	class: "tc-child-tasks"
}, wt = ["onClick"], Tt = { id: "tc-step-title" }, Et = { class: "tc-step-dialog-body" }, Dt = /* @__PURE__ */ t({
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
		let a = t, s = r, c = D(() => a.taskType === "codex_retry"), u = D(() => c.value ? a.progress?.main_steps || [] : be(a.progress?.main_steps)), d = D(() => c.value ? u.value.filter((e) => e.observed_order != null || e.evidence === "run_status") : u.value), f = D(() => {
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
		let y = v(null), w = D(() => u.value.find((e) => Oe(e) === y.value)), O = v(), k = null, A = D(() => le(a.progress?.outcome?.child_tasks).flatMap((e) => {
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
		})), P = D(() => {
			let e = ve(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${ke(G(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			return t ? `当前：${t.label || t.step_id || "执行中"}${t.child_label ? ` · ${t.child_label}` : ""}` : "执行阶段";
		});
		function F(e) {
			return [
				ue(e),
				K(e),
				...q(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function I(e) {
			return Oe(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function ee(t) {
			k = document.activeElement instanceof HTMLElement ? document.activeElement : null, y.value = Oe(t), await e(), O.value?.open || O.value?.showModal();
		}
		function R() {
			O.value?.close(), y.value = null, k?.isConnected && k.focus({ preventScroll: !0 }), k = null;
		}
		function z(e) {
			let t = O.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i(() => [a.context, a.active], R), C(() => O.value?.close()), (e, r) => t.progress ? (n(), M("section", rt, [
			S("div", it, [S("strong", null, b(P.value), 1), !c.value || t.progress.source !== "explicit" ? (n(), M("small", at, b(t.progress.source === "legacy_derived" ? "历史记录还原" : t.progress.source === "insufficient_evidence" ? "步骤记录缺失" : "按首次记录排列，可含分支与重试"), 1)) : p("", !0)]),
			d.value.length ? (n(), M("ul", {
				key: 0,
				class: E(["tc-progress-track", { "tc-progress-track--codex": c.value }]),
				"data-step-count": d.value.length,
				style: _({ "--tc-step-cols": String(f.value) }),
				"aria-label": "执行阶段，排列不代表固定顺序"
			}, [(n(!0), M(g, null, o(d.value, (e) => (n(), M("li", {
				key: j(Oe)(e),
				class: E([
					"tc-step",
					`tc-step--${j(Y)(e)}`,
					{ "tc-step--selected": I(e) }
				])
			}, [S("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": I(e),
				title: F(e),
				onClick: (t) => s("filter", I(e) ? null : j(Oe)(e))
			}, [
				c.value ? p("", !0) : (n(), M("span", ct)),
				S("strong", null, b(j(ue)(e)), 1),
				c.value ? (n(), M("span", lt, [S("span", { class: E(["tc-badge tc-step-status", m[j(Y)(e)]]) }, b(h(e)), 3), j(Y)(e) !== "skipped" && j(Ee)(e) != null ? (n(), M("small", ut, b(j(ge)(j(Ee)(e))), 1)) : p("", !0)])) : (n(), M("span", dt, [
					N(b(j(K)(e)), 1),
					j(Ee)(e) == null ? p("", !0) : (n(), M("small", ft, " · " + b(j(ge)(j(Ee)(e))), 1)),
					(n(!0), M(g, null, o(j(q)(e), (e) => (n(), M("small", { key: e }, " · " + b(e), 1))), 128))
				])),
				j(Se)(e, u.value).length ? (n(), M("span", pt, [(n(!0), M(g, null, o(j(Se)(e, u.value), (e) => (n(), M("em", {
					key: e,
					class: "tc-step-dep-chip"
				}, b(e), 1))), 128))])) : p("", !0)
			], 8, st), S("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${j(ue)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => ee(e)
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
			})], -1)]], 8, mt)], 2))), 128))], 14, ot)) : (n(), M("p", ht, b(c.value ? "此运行暂无阶段记录。" : "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。"), 1)),
			u.value.length ? (n(), M("details", gt, [S("summary", null, [r[3] ||= S("span", { class: "tc-flow-relations__title" }, "依赖与完整阶段记录", -1), S("span", _t, b(u.value.length) + " 个阶段", 1)]), S("div", vt, [S("p", yt, b(t.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1), S("div", bt, [(n(!0), M(g, null, o(u.value, (e) => (n(), M("div", {
				key: j(Oe)(e),
				class: "tc-flow-relation"
			}, [S("div", xt, [S("strong", null, b(j(ue)(e)), 1), c.value ? (n(), M("span", St, b(h(e)), 1)) : p("", !0)]), l(ye, {
				step: e,
				siblings: u.value
			}, null, 8, ["step", "siblings"])]))), 128))])])])) : p("", !0),
			l(nt, {
				failure: t.progress.failure,
				execution: t.execution,
				status: t.progress.outcome.status
			}, null, 8, [
				"failure",
				"execution",
				"status"
			]),
			A.value.length ? (n(), M("div", Ct, [r[4] ||= S("strong", null, "独立子任务", -1), (n(!0), M(g, null, o(A.value, (e) => (n(), M("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, b(j(J)("task_type", j(G)(e.task_type))) + " #" + b(e.task_id) + " · " + b(j(me)(e.status)), 9, wt))), 128))])) : p("", !0),
			S("dialog", {
				ref_key: "inspector",
				ref: O,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: T(R, ["prevent"]),
				onClose: r[0] ||= (e) => y.value = null,
				onWheel: T(z, ["stop"]),
				onClick: r[1] ||= (e) => {
					e.target === O.value && R();
				}
			}, [S("header", null, [S("h3", Tt, b(w.value ? j(ue)(w.value) : "步骤详情"), 1), S("button", {
				type: "button",
				autofocus: "",
				onClick: R
			}, "关闭")]), S("div", Et, [w.value ? (n(), x(we, {
				key: 0,
				step: w.value,
				siblings: u.value
			}, null, 8, ["step", "siblings"])) : p("", !0)])], 544)
		])) : p("", !0);
	}
}), Ot = { class: "tc-detail-header" }, kt = { id: "tc-detail-title" }, At = { key: 0 }, jt = ["title"], Mt = {
	key: 1,
	class: "tc-detail-run"
}, Nt = ["value", "disabled"], Pt = ["value"], Ft = {
	key: 1,
	value: ""
}, It = ["value"], Lt = { class: "tc-detail-header-actions" }, Rt = ["disabled"], zt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Bt = { key: 0 }, Vt = ["disabled"], Ht = {
	key: 1,
	class: "tc-detail-empty",
	role: "status"
}, Ut = {
	key: 0,
	class: "tc-detail-notice"
}, Wt = {
	key: 1,
	class: "tc-detail-notice"
}, Gt = {
	key: 3,
	class: "tc-detail-error",
	role: "status"
}, Kt = { class: "tc-detail-view-toolbar" }, qt = [
	"id",
	"data-detail-tab",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], Jt = {
	key: 0,
	class: "tc-detail-read-toolbar"
}, Yt = ["aria-pressed", "disabled"], Xt = ["aria-pressed", "disabled"], Zt = {
	id: "tc-detail-panel-events",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-events",
	tabindex: "0"
}, Qt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, $t = ["disabled"], en = {
	key: 1,
	class: "tc-detail-notice"
}, tn = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, nn = { class: "tc-event-meta" }, rn = ["data-level"], an = { class: "tc-event-stage" }, on = {
	key: 0,
	class: "tc-event-step"
}, sn = ["data-state"], cn = { class: "tc-event-id" }, ln = {
	key: 0,
	class: "tc-technical"
}, un = ["disabled"], dn = {
	id: "tc-detail-panel-logs",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-logs",
	tabindex: "0"
}, fn = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, pn = ["disabled"], mn = {
	key: 1,
	class: "tc-detail-notice"
}, hn = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, gn = ["data-level"], _n = { class: "tc-event-meta" }, vn = ["data-level"], yn = { class: "tc-log-stage" }, bn = {
	key: 0,
	class: "tc-technical"
}, xn = ["disabled"], Sn = {
	id: "tc-detail-panel-artifacts",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-artifacts",
	tabindex: "0"
}, Cn = {
	key: 0,
	class: "tc-artifact"
}, wn = { key: 0 }, Tn = { class: "tc-artifact-links" }, En = ["href"], Dn = ["href"], On = ["href"], kn = {
	key: 1,
	class: "tc-detail-empty"
}, An = {
	key: 2,
	class: "tc-technical"
}, jn = { class: "tc-detail-footer" }, Mn = {
	key: 1,
	role: "status"
}, Nn = /* @__PURE__ */ t({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(t, { expose: r, emit: c }) {
		let u = c, d = qe(void 0, () => u("refresh")), { opened: f, taskId: m, runId: h, task: _, runs: w, selectedRun: O, progress: k, events: P, logs: F, tab: I, stepFilter: L, error: te, progressError: R, eventsError: z, logsError: B, loading: ne, eventsLoading: re, logsLoading: V, eventsMode: ae, logsMode: U, eventsEarlier: W, eventsMore: oe, logsEarlier: se, logsMore: ce, logsAvailable: le } = d, K = v(), q = v(), _e = v(0), ye = Intl.DateTimeFormat().resolvedOptions().timeZone, be = [
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
		], xe = D(() => k.value?.main_steps || []), Se = D(() => xe.value.find((e) => Oe(e) === L.value || !!(L.value && e.raw_stages?.includes(L.value)))), we = D(() => he(P.value.filter((e) => fe(e, L.value, xe.value)))), Te = D(() => F.value.filter((e) => fe(e, L.value, xe.value, !0))), Ee = D(() => we.value.map((e) => {
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
		})), De = D(() => Te.value.map((e) => {
			let t = pe(e.fields);
			return {
				item: e,
				timestamp: e.ts ? ke(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), Y = D(() => h.value ? O.value : _.value), Ae = D(() => _.value?.email_snapshot || _.value?.email || (_.value?.account_id ? `账号 #${_.value.account_id}` : _.value?.target_id || "执行记录与诊断")), je = D(() => (_.value?.resources || []).filter((e) => !h.value || ee(e.run_id, h.value))), X = D(() => O.value?.debug_artifacts), Me = D(() => ve(O.value?.debug_pause || k.value?.debug_pause)), Ne = null, Pe = !1;
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
			let t = be.findIndex((e) => e.id === I.value), n = e.key === "Home" ? 0 : e.key === "End" ? be.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + be.length) % be.length;
			e.preventDefault(), He(be[n].id), e.currentTarget.querySelector(`[data-detail-tab="${be[n].id}"]`)?.focus();
		}
		async function We(t) {
			Pe = !0, I.value === "events" ? await d.loadEvents(t) : await d.loadLogs(t), await e(), q.value && t !== "next" && (q.value.scrollTop = t === "tail" ? q.value.scrollHeight : 0), _e.value = 0, Pe = !1;
		}
		function Ge() {
			q.value && (q.value.scrollTop = q.value.scrollHeight), _e.value = 0;
		}
		function Ke(e) {
			let t = q.value;
			K.value && K.value.scrollHeight > K.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i([P, F], async ([t, n], [r, i]) => {
			if (Pe) return;
			let a = q.value, o = !a || a.scrollTop + a.clientHeight >= a.scrollHeight - 40, s = I.value === "events" ? t.length - r.length : I.value === "logs" ? n.length - i.length : 0;
			s <= 0 || (await e(), o ? Ge() : _e.value += s);
		}), i(L, () => {
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
			onCancel: T(Le, ["prevent"]),
			onClose: Ie,
			onWheel: Ke
		}, [
			S("header", Ot, [
				S("h2", kt, [N("任务 #" + b(j(m)) + " ", 1), j(_) ? (n(), M("span", At, b(j(J)("task_type", j(_).task_type)), 1)) : p("", !0)]),
				S("span", {
					class: "tc-detail-target",
					title: String(Ae.value),
					tabindex: "0"
				}, b(Ae.value), 9, jt),
				Y.value ? (n(), M("div", {
					key: 0,
					class: E(["tc-detail-status", `tc-detail-status--${j(H)(Y.value.status)}`])
				}, [S("strong", null, b(j(J)("status", Y.value.status)), 1), S("span", null, "耗时 " + b(j(ge)(Y.value.duration_ms)), 1)], 2)) : p("", !0),
				j(_) ? (n(), M("label", Mt, [t[10] ||= S("span", null, "运行", -1), S("select", {
					value: j(h) || "",
					"aria-label": "选择执行实例",
					disabled: j(w).length < 2 && (!j(h) || !!j(O)),
					onChange: Ve
				}, [j(h) && !j(O) ? (n(), M("option", {
					key: 0,
					value: j(h),
					disabled: ""
				}, "运行 #" + b(j(h)) + " 不可用", 9, Pt)) : j(w).length ? p("", !0) : (n(), M("option", Ft, "暂无运行")), (n(!0), M(g, null, o(j(w), (e) => (n(), M("option", {
					key: e.id,
					value: e.id
				}, "第 " + b(e.run_no || "—") + " 次 · " + b(j(J)("status", e.status)), 9, It))), 128))], 40, Nt)])) : p("", !0),
				S("div", Lt, [S("button", {
					type: "button",
					disabled: j(ne),
					onClick: t[0] ||= (...e) => j(d).refresh && j(d).refresh(...e)
				}, b(j(ne) ? "刷新中…" : "刷新"), 9, Rt), S("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Le
				}, "关闭")])
			]),
			j(te) ? (n(), M("div", zt, [
				N("读取任务失败：" + b(j(te)), 1),
				j(_) ? (n(), M("span", Bt, "。保留上次已读取的记录。")) : p("", !0),
				S("button", {
					type: "button",
					disabled: j(ne),
					onClick: t[1] ||= (...e) => j(d).refresh && j(d).refresh(...e)
				}, "重试", 8, Vt)
			])) : p("", !0),
			j(ne) && !j(_) ? (n(), M("div", Ht, "正在读取任务详情…")) : p("", !0),
			j(_) ? (n(), M(g, { key: 2 }, [
				Y.value?.status === "queued" ? (n(), M("p", Ut, b(j(ie)(Y.value)), 1)) : p("", !0),
				Me.value.state === "paused" ? (n(), M("p", Wt, [t[11] ||= N("调试暂停，等待结束调试。", -1), Me.value.hold_until ? (n(), M(g, { key: 0 }, [N("保留至 " + b(j(ke)(Me.value.hold_until)) + "。", 1)], 64)) : p("", !0)])) : p("", !0),
				j(k) ? p("", !0) : (n(), x(nt, {
					key: 2,
					execution: Y.value,
					status: Y.value?.status
				}, null, 8, ["execution", "status"])),
				l(Dt, {
					progress: j(k),
					"task-type": j(_)?.task_type,
					execution: Y.value,
					filter: j(L),
					active: j(f),
					context: `${j(m)}:${j(h)}`,
					onFilter: t[2] ||= (e) => L.value = e,
					onChild: Re
				}, null, 8, [
					"progress",
					"task-type",
					"execution",
					"filter",
					"active",
					"context"
				]),
				j(R) ? (n(), M("p", Gt, [N("进度读取失败：" + b(j(R)), 1), j(k) ? (n(), M(g, { key: 0 }, [N("；保留上次快照")], 64)) : p("", !0)])) : p("", !0),
				S("div", Kt, [
					S("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: Ue
					}, [(n(), M(g, null, o(be, (e) => S("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": j(I) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: j(I) === e.id ? 0 : -1,
						onClick: (t) => He(e.id)
					}, b(e.label), 9, qt)), 64))], 32),
					S("div", { class: E(["tc-detail-filter", { "is-active": !!j(L) }]) }, [S("span", null, [t[12] ||= N("当前查看：", -1), S("strong", null, b(Se.value ? j(ue)(Se.value) : j(L) || "全流程"), 1)]), j(L) ? (n(), M("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => L.value = null
					}, "清除步骤筛选")) : p("", !0)], 2),
					j(I) === "artifacts" ? p("", !0) : (n(), M("div", Jt, [S("button", {
						type: "button",
						"aria-pressed": (j(I) === "events" ? j(ae) : j(U)) === "start",
						disabled: j(re) || j(V) || !j(h),
						onClick: t[4] ||= (e) => We("start")
					}, "从头加载", 8, Yt), S("button", {
						type: "button",
						"aria-pressed": (j(I) === "events" ? j(ae) : j(U)) === "tail",
						disabled: j(re) || j(V) || !j(h),
						onClick: t[5] ||= (e) => We("tail")
					}, "最近记录", 8, Xt)]))
				]),
				S("div", {
					ref_key: "scroller",
					ref: q,
					class: "tc-detail-content"
				}, [
					a(S("section", Zt, [
						j(z) ? (n(), M("p", Qt, [N("事件读取失败：" + b(j(z)), 1), S("button", {
							type: "button",
							disabled: j(re),
							onClick: t[6] ||= (e) => j(d).loadEvents()
						}, "重试", 8, $t)])) : p("", !0),
						j(W) ? (n(), M("p", en, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : p("", !0),
						we.value.length ? p("", !0) : (n(), M("div", tn, b(j(re) ? "正在读取事件…" : j(L) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(n(!0), M(g, null, o(Ee.value, (e) => (n(), M("article", {
							key: e.event.id,
							class: E(["tc-event", {
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
							S("div", nn, [
								S("time", null, b(e.timestamp), 1),
								S("span", {
									class: "tc-event-level",
									"data-level": (e.event.level || "INFO").toUpperCase()
								}, b(e.event.level || "INFO"), 9, rn),
								S("strong", an, b(e.stageLabel), 1),
								e.association ? (n(), M("span", on, b(e.association), 1)) : p("", !0),
								S("span", {
									class: "tc-event-state",
									"data-state": e.state || "info"
								}, b(e.stateLabel), 9, sn),
								S("small", cn, "事件 " + b(e.event.event_id || e.event.id), 1)
							]),
							S("p", null, b(e.event.message || "—"), 1),
							e.detailJson ? (n(), M("details", ln, [t[13] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 2))), 128)),
						j(oe) ? (n(), M("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: j(re),
							onClick: t[7] ||= (e) => We("next")
						}, b(j(re) ? "正在读取…" : "继续加载后续事件"), 9, un)) : p("", !0)
					], 512), [[A, j(I) === "events"]]),
					a(S("section", dn, [
						j(B) ? (n(), M("p", fn, [N("日志读取失败：" + b(j(B)), 1), S("button", {
							type: "button",
							disabled: j(V),
							onClick: t[8] ||= (e) => j(d).loadLogs()
						}, "重试", 8, pn)])) : p("", !0),
						j(se) ? (n(), M("p", mn, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : p("", !0),
						Te.value.length ? p("", !0) : (n(), M("div", hn, b(j(V) ? "正在读取运行日志…" : j(le) ? j(L) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(n(!0), M(g, null, o(De.value, (e, r) => (n(), M("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${r}`,
							class: "tc-log-line",
							"data-level": (e.item.level || "INFO").toUpperCase()
						}, [
							S("div", _n, [
								S("time", null, b(e.timestamp), 1),
								S("strong", {
									class: "tc-log-level",
									"data-level": (e.item.level || "INFO").toUpperCase()
								}, b(e.item.level || "INFO"), 9, vn),
								S("span", yn, b(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							S("p", null, b(e.item.message), 1),
							e.detailJson ? (n(), M("details", bn, [t[14] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 8, gn))), 128)),
						j(ce) ? (n(), M("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: j(V),
							onClick: t[9] ||= (e) => We("next")
						}, b(j(V) ? "正在读取…" : "继续加载后续日志"), 9, xn)) : p("", !0)
					], 512), [[A, j(I) === "logs"]]),
					a(S("section", Sn, [
						X.value?.available ? (n(), M("article", Cn, [
							t[15] ||= S("h3", null, "Roxy 刷新调试", -1),
							S("p", null, b(X.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + b(j(ve)(X.value.summary).request_count || 0) + " 条", 1),
							j(O)?.result_summary?.debug_browser_kept === !0 ? (n(), M("p", wn, "失败窗口已保留，可在 Roxy 中查看。")) : p("", !0),
							S("div", Tn, [
								j(Ce)(X.value.har_url) ? (n(), M("a", {
									key: 0,
									href: j(Ce)(X.value.har_url),
									download: ""
								}, "下载 HAR", 8, En)) : p("", !0),
								j(Ce)(X.value.page_state_url) ? (n(), M("a", {
									key: 1,
									href: j(Ce)(X.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, Dn)) : p("", !0),
								j(Ce)(X.value.screenshot_url) ? (n(), M("a", {
									key: 2,
									href: j(Ce)(X.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, On)) : p("", !0)
							])
						])) : p("", !0),
						(n(!0), M(g, null, o(je.value, (e, t) => (n(), M("article", {
							key: j(G)(e.id) || t,
							class: "tc-artifact"
						}, [
							S("h3", null, b(e.resource_type || "运行资源"), 1),
							S("p", null, b(e.provider || e.state || "—"), 1),
							S("small", null, b(j(ke)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!X.value?.available && !je.value.length ? (n(), M("div", kn, "当前 Run 没有诊断资源或产物")) : p("", !0),
						Y.value?.result_summary ? (n(), M("details", An, [t[16] ||= S("summary", null, "执行结果字段", -1), S("pre", null, b(JSON.stringify(Y.value.result_summary, null, 2)), 1)])) : p("", !0)
					], 512), [[A, j(I) === "artifacts"]])
				], 512),
				S("footer", jn, [S("small", null, "时间按浏览器时区显示 · " + b(j(ye)), 1), _e.value && j(I) !== "artifacts" ? (n(), M("button", {
					key: 0,
					type: "button",
					onClick: Ge
				}, "有 " + b(_e.value) + " 条新记录，回到底部", 1)) : j(ne) || j(re) || j(V) ? (n(), M("small", Mn, "正在同步记录…")) : p("", !0)])
			], 64)) : p("", !0)
		], 544)]));
	}
}), Pn = [
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
function Fn(e, t) {
	return e.fields.some((e) => !!t[e]);
}
function In(e, t, n) {
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
function Ln(e, t) {
	let n = { ...t };
	for (let t of e.fields) n[t] = "";
	return n;
}
// src/features/tasks/TaskFilterFields.vue?vue&type=script&setup=true&lang.ts
var Rn = {
	key: 0,
	class: "tc-filter-field"
}, zn = ["for"], Bn = [
	"id",
	"value",
	"inputmode",
	"placeholder"
], Vn = ["aria-label"], Hn = ["name", "checked"], Un = { class: "tc-filter-option-label" }, Wn = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], Gn = { class: "tc-filter-option-label" }, Kn = {
	key: 0,
	class: "tc-filter-option-count"
}, qn = {
	key: 2,
	class: "tc-filter-date-range"
}, Jn = { class: "tc-filter-field" }, Yn = ["for"], Xn = ["id", "value"], Zn = { class: "tc-filter-field" }, Qn = ["for"], $n = ["id", "value"], er = { class: "tc-filter-footer" }, tr = ["disabled"], nr = /* @__PURE__ */ t({
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
				...Object.keys(U[e] || {}),
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
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? In(r.column, {
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
			i("update:modelValue", Ln(r.column, r.modelValue)), i("done");
		}
		return (t, r) => (n(), M("form", {
			class: "tc-filter-fields",
			onSubmit: r[5] ||= T((e) => i("done"), ["prevent"])
		}, [e.column.kind === "search" ? (n(), M("div", Rn, [S("label", { for: `${j(a)}-search` }, b(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, zn), S("input", {
			id: `${j(a)}-search`,
			value: c.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: r[0] ||= (e) => m(s.value, e.target.value)
		}, null, 40, Bn)])) : e.column.kind === "select" ? (n(), M("div", {
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
		}, null, 40, Hn), S("span", Un, b(l[e.column.group || ""] || "全部"), 1)], 2), (n(!0), M(g, null, o(f.value, (e) => (n(), M("label", {
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
			}, null, 40, Wn),
			S("span", Gn, b(e.text), 1),
			e.count == null ? p("", !0) : (n(), M("span", Kn, b(e.count), 1))
		], 2))), 128))], 8, Vn)) : (n(), M("div", qn, [
			r[6] ||= S("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			S("div", Jn, [S("label", { for: `${j(a)}-from` }, "创建日期起", 8, Yn), S("input", {
				id: `${j(a)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: r[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, Xn)]),
			S("div", Zn, [S("label", { for: `${j(a)}-to` }, "创建日期止", 8, Qn), S("input", {
				id: `${j(a)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: r[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, $n)])
		])), S("div", er, [S("button", {
			type: "button",
			class: "ui-link",
			disabled: !j(Fn)(e.column, e.modelValue),
			onClick: _
		}, "清除此列", 8, tr), r[7] ||= S("button", {
			type: "submit",
			class: "ui-button"
		}, "完成", -1)])], 32));
	}
}), rr = { class: "tc-mobile-filters" }, ir = { class: "tc-filter-column-picker" }, ar = ["value"], or = /* @__PURE__ */ t({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = v(Pn[0].key), u = D(() => Pn.find((e) => e.key === c.value)), d = D(() => Pn.filter((e) => Fn(e, i.modelValue)).length);
		return (t, i) => (n(), M("div", rr, [l(Ae, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: e.open,
			"onUpdate:open": i[3] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [S("label", ir, [i[4] ||= N("筛选列", -1), a(S("select", { "onUpdate:modelValue": i[0] ||= (e) => c.value = e }, [(n(!0), M(g, null, o(j(Pn), (t) => (n(), M("option", {
				key: t.key,
				value: t.key
			}, b(t.label) + b(j(Fn)(t, e.modelValue) ? " · 已筛选" : ""), 9, ar))), 128))], 512), [[m, c.value]])]), (n(), x(nr, {
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
}), sr = /* @__PURE__ */ t({
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
			active: j(Fn)(e.column, e.modelValue),
			summary: j(In)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": a[2] ||= (e) => i("update:open", e)
		}, {
			default: r(() => [l(nr, {
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
}), cr = /* @__PURE__ */ new Set([
	"failed",
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"password_confirmation_pending"
]), lr = /* @__PURE__ */ new Set([
	"running",
	"waiting",
	"stopping",
	"cancelling",
	"settling"
]), ur = /* @__PURE__ */ new Set([
	"cancelled",
	"stopped",
	"interrupted"
]), dr = {
	email_verification_pending: "待验证或补全",
	credential_pending_confirmation: "凭证待核验"
};
function fr(e, t, n) {
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${J(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function pr(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function mr(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: J("status", t),
		tone: H(t),
		title: fr("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = ie(e) || void 0) : lr.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = ie(e) || pr(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : cr.has(t) ? (r.label = "失败", r.tone = "danger") : ur.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (cr.has(n) && cr.has(t) || n === "completed" && t === "success" || n === "in_progress" && lr.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: dr[n] || J("target_status", n),
			tone: H(n),
			title: fr("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Z = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), hr = (e) => Array.isArray(e) ? e.map(W) : [], Q = (e) => String(e || "").toLowerCase(), $ = /* @__PURE__ */ new Set([
	"unknown",
	"request_unknown",
	"attention_required",
	"manual_reconcile",
	"unconfirmed",
	"password_confirmation_pending",
	"credential_pending_confirmation"
]), gr = /* @__PURE__ */ new Set([
	"failed",
	"error",
	"deactivated"
]);
function _r(e) {
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
var vr = {
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
}, yr = {
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
function br(e, t) {
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
	].includes(r) ? Z("提链成功", "warning", "后续已中断") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Z("提链成功", "danger", "后续失败") : Z("提链成功", "success") : gr.has(i) || _r(e) ? Z(t, "danger") : $.has(i) ? Z("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Z("等待提链", "warning") : i === "running" ? Z("提链中", "active") : r === "cancelled" ? Z("已取消") : ["stopped", "interrupted"].includes(r) ? Z("执行已中断", "warning") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Z(t, "danger") : n.ok === !0 ? Z("提链流程完成", "success") : Z("提链结果缺失", "warning");
}
function xr(e, t) {
	let n = W(e.result_summary), r = Q(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : hr(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes(Q(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = W(e.result);
		return !t && !e.last_success_at ? [] : hr(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : hr(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(W(e.result)).length > 0);
	if (s > 0 && o > 0 || !i && n.plan_check_partial === !0) return Z("部分失败", "warning", u ? "含历史数据" : void 0);
	if (c > 0 && s >= c) return u ? Z("查询失败", "danger", "含历史数据") : Z(t, "danger");
	if (_r(e)) return Z(t, "danger");
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
function Sr(e, t = "执行异常") {
	let n = W(e.result_summary), r = Q(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
	if (e.debug_pause) return Z("调试已暂停", "warning");
	if (["queued", "pending"].includes(r)) {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(vr[String(t)] || "等待执行", "warning");
	}
	if (r === "waiting") {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(vr[String(t)] || pr(e), "warning");
	}
	if (r === "running") return Z("执行中", "active");
	if (["stopping", "cancelling"].includes(r)) return Z("正在停止", "warning");
	if (r === "settling") return Z("正在收尾", "active");
	if (i === "extract_link") return br(e, a);
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
	if (i === "plan_check") return xr(e, a);
	if (r === "cancelled") return Z("已取消");
	if (["stopped", "interrupted"].includes(r)) return Z("执行已中断", "warning");
	if (_r(e)) return Z(a, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes(Q(e.target_status)) || r === "deactivated") return Z("账号已停用", "danger");
	let o = i === "sub2api_scan" || i === "c2a_scan";
	if (e.error_message || e.error_info || gr.has(r) || !o && n.ok === !1) return Z(a, "danger");
	if (r === "partial_success") return Z("部分完成", "warning");
	if (o) return r === "success" ? Z(i === "c2a_scan" && n.continuation_only === !0 ? "接续检查完成" : yr[i], "success") : Z("扫描未完成", "warning");
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
	return i === "deactivation_mail" && typeof n.detected == "boolean" ? Z(n.detected ? "发现封号邮件" : "未见封号邮件", n.detected ? "warning" : "neutral") : i === "live_check" && n.ok === !0 ? Z("账号正常", "success") : i === "token_refresh" && n.ok === !0 ? Z("令牌已刷新", "success") : i === "account_inspection_batch" && Number(n.failed_count) > 0 ? Z("巡检已完成", "warning", "存在失败") : r === "success" || n.ok === !0 ? Z(yr[i] || "任务已完成", "success") : Z("结果未记录");
}
// src/features/tasks/TaskResultCell.vue
var Cr = /* @__PURE__ */ t({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, i = D(() => Sr(t.task, Ie(t.task.error_info))), a = D(() => [...new Set([
			se(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? V(t.task.error_info, t.task.error_message) : "",
			t.task.error_message,
			t.task.error_code,
			t.task.error_info?.code,
			t.task.error_info?.cause_code
		].filter((e) => !!e))]);
		return (e, t) => (n(), x(Fe, w(i.value, { title: a.value.join("\n") }), {
			details: r(() => [(n(!0), M(g, null, o(a.value, (e, t) => (n(), M("p", { key: t }, b(e), 1))), 128))]),
			_: 1
		}, 16, ["title"]));
	}
}), wr = ["aria-busy"], Tr = [
	"checked",
	"indeterminate",
	"disabled"
], Er = {
	"data-label": "选择",
	class: "ui-col-check"
}, Dr = [
	"checked",
	"aria-label",
	"onChange"
], Or = { "data-label": "ID" }, kr = ["onClick"], Ar = { "data-label": "类型" }, jr = { "data-label": "目标" }, Mr = { key: 0 }, Nr = {
	key: 1,
	class: "tc-muted-placeholder"
}, Pr = {
	key: 1,
	class: "tc-muted-placeholder",
	"aria-label": "无目标"
}, Fr = { "data-label": "执行状态" }, Ir = ["title"], Lr = ["title"], Rr = { "data-label": "目标状态" }, zr = ["title"], Br = {
	key: 1,
	class: "tc-cell-line tc-muted-placeholder",
	"aria-label": "无额外目标状态"
}, Vr = { "data-label": "批次 / 触发" }, Hr = ["onClick"], Ur = { "data-label": "运行次数" }, Wr = { "data-label": "当前步骤" }, Gr = {
	"data-label": "创建 / 完成",
	class: "ui-time"
}, Kr = { "data-label": "结果 / 错误" }, qr = { "data-label": "操作" }, Jr = { class: "ui-row-actions tc-row-actions" }, Yr = ["onClick"], Xr = ["disabled", "onClick"], Zr = ["disabled", "onClick"], Qr = ["disabled", "onClick"], $r = /* @__PURE__ */ t({
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
		let a = e, s = i, c = D(() => a.items.length > 0 && a.items.every((e) => a.selected.has(e.id))), u = D(() => !c.value && a.items.some((e) => a.selected.has(e.id))), d = D(() => a.items.map((e) => ({
			task: e,
			...mr(e)
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
		function T(e) {
			return oe(e) || e.current_stage_label || J("stage", e.current_stage);
		}
		function O(e) {
			return [
				e.current_stage_label || J("stage", e.current_stage),
				oe(e),
				ge(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function k(e) {
			return String(e.bulk_batch_id || W(e.bulk_context).batch_id || "");
		}
		function A(e) {
			return String(e.bulk_round_id || W(e.bulk_context).round_id || "");
		}
		return t({ resetColumns: y }), (t, i) => (n(), M("div", {
			class: "ui-table-scroll tc-table-scroll",
			tabindex: "0",
			"aria-label": "任务列表，可横向滚动",
			"aria-busy": e.loading
		}, [S("table", {
			class: "ui-table ui-table--sticky-end ui-table--cards tc-table",
			style: _({ "--ui-table-width": `${j(m).reduce((e, t) => e + t, 0)}px` })
		}, [
			i[3] ||= S("caption", { class: "ui-sr-only" }, "任务中心列表，选择任务可批量操作", -1),
			S("colgroup", null, [(n(!0), M(g, null, o(j(m), (e, t) => (n(), M("col", {
				key: t,
				style: _({ width: `${e}px` })
			}, null, 4))), 128))]),
			S("thead", null, [S("tr", null, [(n(), M(g, null, o(f, (t, r) => S("th", {
				key: t,
				scope: "col",
				class: E({ "ui-col-check": r === 0 })
			}, [r === 0 ? (n(), M("input", {
				key: 0,
				type: "checkbox",
				"aria-label": "全选当前页任务",
				checked: c.value,
				indeterminate: u.value,
				disabled: !e.items.length,
				onChange: i[0] ||= (e) => s("selectPage", e.target.checked)
			}, null, 40, Tr)) : (n(), M(g, { key: 1 }, [j(Pn)[r - 1] ? (n(), x(sr, {
				key: 0,
				column: j(Pn)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === j(Pn)[r - 1].key,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:filters", e),
				"onUpdate:open": (e) => s("update:openFilter", e ? j(Pn)[r - 1].key : null)
			}, null, 8, [
				"column",
				"model-value",
				"facets",
				"open",
				"onUpdate:open"
			])) : (n(), M(g, { key: 1 }, [N(b(t), 1)], 64)), r < f.length - 1 ? (n(), x(Pe, {
				key: 2,
				label: t,
				onStart: (e) => j(h)(r, e),
				onNudge: (e) => j(v)(r, e)
			}, null, 8, [
				"label",
				"onStart",
				"onNudge"
			])) : p("", !0)], 64))], 2)), 64))])]),
			S("tbody", null, [(n(!0), M(g, null, o(d.value, ({ task: t, execution: i, target: a }) => (n(), M("tr", {
				key: t.id,
				class: E({ "is-selected": e.selected.has(t.id) })
			}, [
				S("td", Er, [S("input", {
					type: "checkbox",
					checked: e.selected.has(t.id),
					"aria-label": `选择任务 #${t.id}`,
					onChange: (e) => s("select", t.id, e.target.checked)
				}, null, 40, Dr)]),
				S("td", Or, [S("button", {
					type: "button",
					class: "ui-link tc-task-id",
					onClick: (e) => s("detail", t.id)
				}, "#" + b(t.id), 9, kr)]),
				S("td", Ar, [l(X, { text: j(J)("task_type", t.task_type) }, null, 8, ["text"])]),
				S("td", jr, [C(t) || w(t) ? (n(), x(X, {
					key: 0,
					text: C(t) || "—",
					secondary: w(t) || void 0
				}, {
					default: r(() => [C(t) ? (n(), M("strong", Mr, b(C(t)), 1)) : (n(), M("span", Nr, "—"))]),
					_: 2
				}, 1032, ["text", "secondary"])) : (n(), M("span", Pr, "—"))]),
				S("td", Fr, [S("span", {
					class: E(["ui-badge tc-badge", `ui-badge--${i.tone}`]),
					title: i.title
				}, b(i.label), 11, Ir), i.secondary ? (n(), M("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: i.secondary
				}, b(i.secondary), 9, Lr)) : p("", !0)]),
				S("td", Rr, [a ? (n(), M("span", {
					key: 0,
					class: E(["ui-badge tc-badge", `ui-badge--${a.tone}`]),
					title: a.title
				}, b(a.label), 11, zr)) : (n(), M("span", Br, "—"))]),
				S("td", Vr, [l(X, {
					text: t.batch_title || t.batch_uuid || (k(t) ? "查看批次" : "单任务"),
					secondary: j(J)("trigger", t.trigger)
				}, {
					default: r(() => [k(t) ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: (e) => s("batch", k(t), A(t))
					}, b(t.batch_title || t.batch_uuid || "查看批次"), 9, Hr)) : (n(), M(g, { key: 1 }, [N(b(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				S("td", Ur, [l(X, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				S("td", Wr, [l(X, {
					text: T(t),
					secondary: j(ge)(t.duration_ms),
					title: O(t),
					tone: j(oe)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				S("td", Gr, [l(X, {
					text: j(ke)(t.created_at),
					secondary: j(ke)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				S("td", Kr, [l(Cr, { task: t }, null, 8, ["task"])]),
				S("td", qr, [S("div", Jr, [
					S("button", {
						type: "button",
						class: "ui-link",
						onClick: (e) => s("detail", t.id)
					}, "详情", 8, Yr),
					j(De)(t) ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						disabled: e.busy,
						onClick: (e) => s("action", t, "retry")
					}, "重跑", 8, Xr)) : p("", !0),
					j(ce)(t) ? (n(), M("button", {
						key: 1,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "terminate")
					}, b(t.status === "queued" ? "取消" : "终止"), 9, Zr)) : p("", !0),
					j(re)(t) ? p("", !0) : (n(), M("button", {
						key: 2,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "delete")
					}, "删除", 8, Qr))
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
		], 4)], 8, wr));
	}
});
// src/features/tasks/useTaskList.ts
function ei() {
	let t = c(Be()), n = v(1), r = v(20), a = v(0), o = v([]), s = v({}), l = v(/* @__PURE__ */ new Set()), u = v(!1), d = v(""), p = v(!1), m = D(() => Math.max(1, Math.ceil(a.value / r.value))), h = 0, g = null, _, y, b = 0, x = 0, S = "", C = "", w = !1, T = /* @__PURE__ */ new Set([
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
			let e = await Ge.list({
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
			...Be(),
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
// src/features/tasks/TaskCenter.vue?vue&type=script&setup=true&lang.ts
var ti = {
	class: "tc-root",
	"aria-label": "统一任务中心"
}, ni = { class: "ui-list tc-workspace" }, ri = {
	class: "ui-list-count tc-count",
	role: "status"
}, ii = {
	class: "tc-target-search",
	role: "search"
}, ai = ["value", "onKeydown"], oi = {
	key: 0,
	class: "tc-selection",
	role: "status"
}, si = {
	key: 1,
	class: "tc-bulk-actions",
	role: "group",
	"aria-label": "选中任务批量操作"
}, ci = ["disabled", "onClick"], li = ["title"], ui = ["disabled"], di = ["role"], fi = { key: 1 }, pi = /* @__PURE__ */ t({
	__name: "TaskCenter",
	emits: ["batch", "changed"],
	setup(t, { expose: s, emit: c }) {
		let u = c, f = ei(), { filters: m, page: _, size: y, pages: x, total: w, items: O, facets: k, selected: P, loading: F, error: I, visible: L } = f, ee = v(null), te = v(null), R = v(!1), z = v(""), B = v(""), ie = v(null), V = v(null), H = v(m.target || ""), U;
		i(() => m.target, (e) => {
			clearTimeout(U), H.value = e || "";
		}), C(() => clearTimeout(U)), i(ie, (e) => {
			f.setFacetsVisible(e === "mobile" || Pn.some((t) => t.key === e && t.kind === "select"));
		});
		let oe = D(() => Pn.filter((e) => Fn(e, m))), se = D(() => oe.value.map((e) => ({
			key: e.key,
			label: `${e.label}：${In(e, m, k.value)}`,
			removeLabel: `清除${e.label}筛选`
		}))), G = v([]), ce = D(() => O.value.filter((e) => P.value.has(e.id))), le = D(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, ce.value.filter((t) => ae(t, e)).length]))), K = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, ue = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function de(e) {
			Object.assign(m, e);
		}
		function fe(e) {
			clearTimeout(U);
			let t = e.trim();
			t !== (m.target || "") && de({
				...m,
				target: t
			});
		}
		function pe(e) {
			H.value = e, clearTimeout(U), U = setTimeout(() => fe(e), 250);
		}
		function me() {
			clearTimeout(U), H.value = "", fe(""), V.value?.focus();
		}
		function he(e) {
			let t = Pn.find((t) => t.key === e);
			t && de(Ln(t, m));
		}
		function q(e, t, n) {
			ee.value?.open(e, t, n);
		}
		async function J(t = {}) {
			t.filters && f.applyFilters(t.filters), t.taskId && (await e(), q(t.taskId, t.runId, t.stepId));
		}
		function ge(e) {
			e || (ie.value = null), f.setVisible(e);
		}
		function _e() {
			ee.value?.close();
		}
		async function ve(e = {}) {
			L.value && await f.refresh(e);
		}
		function ye() {
			ve(), u("changed");
		}
		async function be(e, t) {
			if (!R.value && !(t === "delete" && re(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				R.value = !0, B.value = "", G.value = [], z.value = "";
				try {
					let n = await Ge.action(e.id, t), r = W(n.data || n);
					z.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", P.value.delete(e.id), await ve(), u("changed");
				} catch (e) {
					B.value = `${K[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					R.value = !1;
				}
			}
		}
		async function xe(e) {
			if (R.value) return;
			let t = ce.value.filter((t) => ae(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${K[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				R.value = !0, B.value = "", z.value = "", G.value = [];
				try {
					let n = t.map((e) => e.id), r = e === "terminate" ? await Ge.bulk(e, n, { onAccepted: (e) => {
						z.value = `终止请求已受理，正在等待结果（命令 ${e.command_id}）`;
					} }) : await Ge.bulk(e, n), i = Array.isArray(r.accepted) ? r.accepted : [];
					G.value = (r.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let a = Number(r.accepted_count ?? i.length);
					if (e === "cancel") {
						let e = i.filter((e) => e.state === "cancelled").length, t = i.filter((e) => e.state === "cancelling").length;
						z.value = `已取消 ${e} 个，取消中 ${t} 个${a - e - t > 0 ? `，已受理 ${a - e - t} 个` : ""}`;
					} else z.value = `已${K[e]} ${a} 个`;
					let o = new Set(i.map((e) => String(e.task_id)));
					P.value = new Set([...P.value].filter((e) => !o.has(String(e)))), G.value.length && (z.value += `，跳过 ${G.value.length} 个`), await ve(), u("changed");
				} catch (t) {
					B.value = t instanceof ne ? t.message : `${K[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					R.value = !1;
				}
			}
		}
		return s({
			open: J,
			refresh: ve,
			closeDetail: _e,
			setVisible: ge
		}), (e, t) => (n(), M(g, null, [a(S("section", ti, [S("div", ni, [
			l(Re, { filtered: oe.value.length > 0 }, {
				actions: r(() => [
					l(or, {
						"model-value": j(m),
						facets: j(k),
						open: ie.value === "mobile",
						"onUpdate:modelValue": de,
						"onUpdate:open": t[2] ||= (e) => ie.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					oe.value.length ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: t[3] ||= (e) => j(f).applyFilters({})
					}, "清除全部筛选")) : p("", !0),
					S("span", {
						class: "tc-timezone",
						title: j(ue)
					}, "时间按 " + b(j(ue)) + " 显示", 9, li),
					S("button", {
						type: "button",
						class: "ui-link",
						onClick: t[4] ||= (e) => te.value?.resetColumns()
					}, "恢复列宽"),
					S("button", {
						id: "btnRefreshTasksV2",
						type: "button",
						class: "ui-button",
						disabled: j(F),
						onClick: t[5] ||= (e) => j(f).refresh()
					}, b(j(F) ? "刷新中…" : "刷新"), 9, ui)
				]),
				default: r(() => [
					S("span", ri, b(j(w).toLocaleString()) + " 个任务", 1),
					S("div", ii, [S("input", {
						ref_key: "targetInput",
						ref: V,
						type: "search",
						value: H.value,
						placeholder: "搜索目标邮箱 / 账号...",
						"aria-label": "搜索任务目标",
						autocomplete: "off",
						onInput: t[0] ||= (e) => pe(e.target.value),
						onKeydown: [t[1] ||= h(T((e) => fe(H.value), ["prevent"]), ["enter"]), h(T(me, ["prevent"]), ["esc"])]
					}, null, 40, ai), H.value ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "tc-target-search__clear",
						"aria-label": "清空目标搜索",
						title: "清空目标搜索",
						onClick: me
					}, "×")) : p("", !0)]),
					ce.value.length ? (n(), M("span", oi, "已选 " + b(ce.value.length) + " 项", 1)) : p("", !0),
					ce.value.length ? (n(), M("div", si, [(n(), M(g, null, o([
						"retry",
						"cancel",
						"terminate",
						"delete"
					], (e) => S("button", {
						key: e,
						type: "button",
						class: E(["ui-button", { "ui-button--danger": e === "delete" || e === "terminate" }]),
						disabled: R.value || !le.value[e],
						onClick: (t) => xe(e)
					}, b(K[e]) + b(le.value[e] ? `（${le.value[e]}）` : ""), 11, ci)), 64))])) : p("", !0),
					l(Me, {
						items: se.value,
						onRemove: he
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			z.value || B.value || j(I) && j(O).length ? (n(), M("div", {
				key: 0,
				class: E(["ui-list-feedback tc-feedback", { "is-error": B.value || j(I) }]),
				role: B.value || j(I) ? "alert" : "status"
			}, [
				N(b(B.value || j(I) || z.value), 1),
				j(I) ? (n(), M("button", {
					key: 0,
					type: "button",
					class: "ui-link",
					onClick: t[6] ||= (e) => j(f).refresh()
				}, "重试")) : p("", !0),
				G.value.length ? (n(), M("details", fi, [t[12] ||= S("summary", null, "查看跳过原因", -1), S("ul", null, [(n(!0), M(g, null, o(G.value, (e) => (n(), M("li", { key: e.id }, "#" + b(e.id) + "：" + b(e.message), 1))), 128))])])) : p("", !0)
			], 10, di)) : p("", !0),
			l($r, {
				ref_key: "table",
				ref: te,
				filters: j(m),
				facets: j(k),
				"open-filter": ie.value,
				"onUpdate:openFilter": t[7] ||= (e) => ie.value = e,
				"onUpdate:filters": de,
				items: j(O),
				selected: j(P),
				loading: j(F),
				error: j(I),
				busy: R.value,
				onSelect: j(f).toggle,
				onSelectPage: j(f).togglePage,
				onDetail: q,
				onAction: be,
				onBatch: t[8] ||= (e, t) => u("batch", e, t),
				onRetry: t[9] ||= (e) => j(f).refresh()
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
				page: j(_),
				"onUpdate:page": t[10] ||= (e) => d(_) ? _.value = e : null,
				size: j(y),
				"onUpdate:size": t[11] ||= (e) => d(y) ? y.value = e : null,
				pages: j(x),
				total: j(w),
				busy: j(F)
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy"
			])
		])], 512), [[A, j(L)]]), l(Nn, {
			ref_key: "detail",
			ref: ee,
			onRefresh: ye
		}, null, 512)], 64));
	}
});
// src/main.ts
function mi(e, t = {}) {
	return O(pi, t).mount(e);
}
export { mi as mountTaskCenter };
