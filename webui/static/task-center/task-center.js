import { $ as e, A as t, B as n, G as r, I as i, O as a, P as o, S as s, V as c, W as l, X as u, Y as d, Z as f, _ as p, b as m, c as h, ct as g, d as _, dt as v, g as y, h as b, i as x, j as S, k as C, m as w, n as T, o as E, ot as D, p as O, s as k, tt as A, u as j, ut as M, x as N } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { n as P, r as F, t as I } from "./client-BBEPwkQG.js";
import { a as L, i as R, n as ee, r as z } from "./taskIds-BlchWwUp.js";
import { n as B } from "./time-DOD6oyhP.js";
import { A as V, C as H, D as U, E as W, M as G, N as K, O as te, P as q, S as ne, T as re, _ as ie, a as ae, b as oe, c as se, d as ce, f as le, g as ue, h as de, i as J, j as fe, k as pe, l as me, m as he, n as ge, o as _e, p as ve, r as ye, s as be, t as xe, u as Se, v as Ce, w as we, x as Te, y as Ee } from "./StepEvidence-CM91D2vn.js";
import { n as De, r as Oe, t as ke } from "./ListFilterSummary-NiVwXoAn.js";
import { t as Ae } from "./useColumnWidths-DKwoq5eG.js";
import { t as je } from "./ListResult-3o6cJKgT.js";
import { t as Y } from "./errorLabels-6tZmqsp4.js";
import { t as Me } from "./ListPagination-CFFXEHba.js";
// src/api/tasks.ts
var X = (e, t = {}) => F(e, t, z);
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
async function Fe(e, t, n) {
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
			...n ? { body: Ie(t, n) } : {}
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
function Ie(e, t) {
	if (e !== "/api/operations/bulk") return JSON.stringify(t);
	let { task_ids: n, ...r } = t;
	if (!Array.isArray(n)) return JSON.stringify(t);
	let i = JSON.stringify(r).slice(0, -1);
	return `${i}${i.length > 1 ? "," : ""}"task_ids":[${n.map((e) => String(L(e))).join(",")}]}`;
}
var Le = {
	list: (e, t) => X(`/api/operations?${Pe(e)}`, { signal: t }),
	detail: (e, t) => X(`/api/operations/${L(e)}?include_events=0`, { signal: t }),
	progress: (e, t, n) => X(`/api/operations/${L(e)}/runs/${L(t)}/progress`, { signal: n }),
	events: (e, t, n = {}, r) => X(`/api/operations/${L(e)}/runs/${L(t)}/events?${Pe({
		limit: 500,
		...n
	})}`, { signal: r }),
	logs: (e, t, n = {}, r) => X(`/api/operations/${L(e)}/runs/${L(t)}/logs?${Pe({
		limit: 500,
		...n
	})}`, { signal: r }),
	action: (e, t) => t === "retry" ? Fe(`retry:${L(e)}`, `/api/operations/${L(e)}/retry`) : X(`/api/operations/${L(e)}/${t}`, { method: "POST" }),
	bulk: (e, t) => e === "retry" ? Fe("bulk:retry", "/api/operations/bulk", {
		action: e,
		task_ids: t
	}) : X("/api/operations/bulk", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: Ie("/api/operations/bulk", {
			action: e,
			task_ids: t
		})
	})
}, Re = (e) => e instanceof Error ? e.message : "读取失败，请重试";
function ze(t = Le, n = () => {}) {
	let r = e(!1), i = e(!0), a = e(null), o = e(null), s = A(null), c = A(null), l = A([]), d = A([]), f = e("events"), p = e(null), m = e(""), h = e(""), g = e(""), _ = e(""), v = e(!1), y = e(!1), b = e(!1), x = e(null), S = e(null), C = e("tail"), w = e("tail"), T = e(!1), E = e(!1), D = e(!1), k = e(!1), j = e(!0), M = O(() => s.value?.runs || []), N = O(() => M.value.find((e) => R(e.id, o.value))), P = 0, F = 0, I = 0, z = 0, B, V = new AbortController(), H = !1;
	function U() {
		B !== void 0 && clearTimeout(B), B = void 0;
	}
	function W() {
		P += 1, V.abort(), V = new AbortController(), v.value = y.value = b.value = !1, U();
	}
	let G = (e) => e === P && r.value, K = () => r.value && i.value && !!a.value;
	function te() {
		U(), K() && (!s.value || pe(s.value)) && (B = setTimeout(() => void ae(), 2e3));
	}
	function q() {
		F += 1, I += 1, y.value = b.value = !1, c.value = null, h.value = g.value = _.value = "", l.value = [], d.value = [], x.value = S.value = null, T.value = E.value = D.value = k.value = !1, C.value = w.value = "tail", j.value = !0;
	}
	async function ne(e = "incremental") {
		if (!K() || !o.value || !a.value || e === "incremental" && y.value || e === "incremental" && C.value === "start" && E.value || e === "next" && !E.value) return;
		let n = P, r = ++F, i = e === "tail" || e === "start" || x.value === null, s = {
			limit: 500,
			...e === "start" ? { after_id: 0 } : e !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		y.value = !0;
		try {
			let c = await t.events(a.value, o.value, s, V.signal);
			if (!G(n) || r !== F) return;
			l.value = i ? c.items : le(l.value, c.items), x.value = c.next_after_id, (e === "tail" || e === "start") && (C.value = e), i && C.value === "tail" ? (T.value = c.has_more, E.value = !1) : (E.value = c.has_more, C.value === "start" && (T.value = !1)), g.value = "";
		} catch (e) {
			G(n) && r === F && (g.value = Re(e));
		} finally {
			G(n) && r === F && (y.value = !1);
		}
	}
	async function re(e = "incremental") {
		if (!K() || !o.value || !a.value || e === "incremental" && b.value || e === "incremental" && w.value === "start" && k.value || e === "next" && !k.value) return;
		let n = P, r = ++I, i = e === "tail" || e === "start" || S.value === null, s = {
			limit: 500,
			...e === "start" ? { cursor: 0 } : e !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		b.value = !0;
		try {
			let c = await t.logs(a.value, o.value, s, V.signal);
			if (!G(n) || r !== I) return;
			d.value = i ? c.items : [...d.value, ...c.items], S.value = c.next_cursor, (e === "tail" || e === "start") && (w.value = e), k.value = c.has_more, D.value = w.value === "tail" && c.available, j.value = c.available, _.value = "";
		} catch (e) {
			G(n) && r === I && (_.value = Re(e));
		} finally {
			G(n) && r === I && (b.value = !1);
		}
	}
	async function ie(e) {
		if (a.value && o.value) try {
			let n = await t.progress(a.value, o.value, V.signal);
			if (!G(e)) return;
			c.value = n.progress, h.value = "";
		} catch (t) {
			G(e) && (h.value = Re(t));
		}
	}
	async function ae() {
		if (!K() || !a.value || v.value) return;
		let e = P, r = ++z;
		v.value = !0, U();
		try {
			let i = await t.detail(a.value, V.signal);
			if (!G(e) || r !== z) return;
			s.value = i.task;
			let c = i.task.runs || [];
			if (o.value && !c.some((e) => R(e.id, o.value))) {
				q(), m.value = `所选运行 #${o.value} 不存在或已不可用，请选择其他运行。`;
				return;
			}
			let l = o.value || i.task.last_run_id || c.at(-1)?.id || null, u = c.some((e) => R(e.id, l)) ? l : c.at(-1)?.id || null;
			if (u !== o.value && (q(), o.value = u), m.value = "", o.value && await Promise.allSettled([
				ie(e),
				ne(),
				...f.value === "logs" ? [re()] : []
			]), !G(e)) return;
			!pe(i.task) && !H && (H = !0, n());
		} catch (t) {
			G(e) && (m.value = Re(t));
		} finally {
			G(e) && r === z && (v.value = !1, te());
		}
	}
	function oe(e, t, n) {
		return W(), r.value = !0, a.value = L(e), o.value = ee(t), s.value = null, m.value = "", f.value = "events", p.value = n || null, H = !1, q(), ae();
	}
	function se() {
		r.value = !1, W();
	}
	function ce(e) {
		if (e = L(e), !R(e, o.value)) return W(), o.value = e, p.value = null, q(), ae();
	}
	function ue(e) {
		if (f.value = e, e === "logs") return re();
	}
	function de(e) {
		i.value !== e && (i.value = e, e ? r.value && ae() : W());
	}
	return u(se), {
		opened: r,
		taskId: a,
		runId: o,
		task: s,
		runs: M,
		selectedRun: N,
		progress: c,
		events: l,
		logs: d,
		tab: f,
		stepFilter: p,
		error: m,
		progressError: h,
		eventsError: g,
		logsError: _,
		loading: v,
		eventsLoading: y,
		logsLoading: b,
		eventsMode: C,
		logsMode: w,
		eventsEarlier: T,
		eventsMore: E,
		logsEarlier: D,
		logsMore: k,
		logsAvailable: j,
		open: oe,
		close: se,
		selectRun: ce,
		selectTab: ue,
		setVisible: de,
		refresh: ae,
		loadEvents: ne,
		loadLogs: re
	};
}
// src/features/tasks/detail/TaskFailure.vue?vue&type=script&setup=true&lang.ts
var Be = {
	key: 0,
	class: "tc-progress-failure tc-task-failure"
}, Ve = { key: 0 }, He = { key: 1 }, Ue = {
	key: 2,
	class: "tc-failure-secondary"
}, We = { key: 3 }, Ge = { key: 0 }, Ke = { key: 1 }, qe = { key: 2 }, Je = /* @__PURE__ */ s({
	__name: "TaskFailure",
	props: {
		failure: {},
		execution: {},
		status: {}
	},
	setup(e) {
		let t = e, n = O(() => !!(t.execution?.error_message || t.execution?.error_info)), r = O(() => (t.failure?.country_failures || []).filter((e) => Te(e.country).trim())), a = O(() => {
			let e = t.failure;
			return e ? r.value.length && !e.error_info?.auto_refresh_at_failed ? `${r.value.length} 个国家查询失败，展开查看具体原因` : me(e) : "";
		}), s = O(() => {
			let e = t.failure;
			if (!e) return "";
			let n = e.error_info?.stage?.replace(/_result$/, "");
			return n && ![
				"unknown",
				"complete",
				"result",
				"event",
				"queued"
			].includes(n) && n !== e.stage ? V("stage", n) : [e.label || e.step_id || "阶段记录缺失", e.stage].filter(Boolean).join(" · ");
		}), c = O(() => n.value ? W(t.execution?.error_info, t.execution?.error_message) : ""), l = O(() => {
			if (!t.failure || !n.value) return !1;
			let e = (e) => Te(e).replace(/\s+/g, " ").trim(), r = t.failure, i = r.error_info, a = t.execution?.error_info, o = e(r.message), s = e(t.execution?.error_message);
			if (o && s && o !== s) return !1;
			if (i?.cause_summary && a?.cause_summary) return e(i.cause_summary) === e(a.cause_summary);
			if (o && s) return o === s;
			let c = e(i?.cause_summary || i?.summary || r.message);
			return !!c && c === e(a?.cause_summary || a?.summary || t.execution?.error_message);
		}), u = O(() => ({
			...t.failure ? { failure: t.failure } : {},
			...n.value ? { execution: {
				error_message: t.execution?.error_message,
				error_info: t.execution?.error_info
			} } : {}
		}));
		return (t, d) => e.failure || n.value ? (o(), p("details", Be, [
			w("summary", null, [
				e.failure ? (o(), p("strong", Ve, v(D(se)(e.failure) ? "历史失败位置" : "失败位置") + "：" + v(s.value), 1)) : (o(), p("strong", He, "执行失败")),
				w("span", null, v(a.value || c.value), 1),
				e.failure && n.value && !l.value ? (o(), p("span", Ue, "执行错误：" + v(c.value), 1)) : y("", !0),
				e.execution?.error_info?.display_code ? (o(), p("small", We, v(e.execution.error_info.display_code), 1)) : y("", !0)
			]),
			r.value.length ? (o(), p("ul", Ge, [(o(!0), p(j, null, i(r.value, (e, t) => (o(), p("li", { key: t }, v(e.country) + "：" + v(e.summary || "诊断记录不完整"), 1))), 128))])) : y("", !0),
			e.failure?.event_id ? (o(), p("p", Ke, "关联事件 " + v(e.failure.event_id), 1)) : y("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(D(Te)(e.status)) ? (o(), p("p", qe, "原请求证据已保留")) : y("", !0),
			w("pre", null, v(JSON.stringify(u.value, null, 2)), 1)
		])) : y("", !0);
	}
}), Ye = {
	key: 0,
	class: "tc-progress",
	"aria-label": "执行进度"
}, Xe = { class: "tc-progress-heading" }, Ze = {
	key: 0,
	class: "tc-progress-track",
	"aria-label": "执行阶段，排列不代表固定顺序"
}, Qe = [
	"aria-pressed",
	"title",
	"onClick"
], $e = { class: "tc-step-meta" }, et = { key: 0 }, tt = ["aria-label", "onClick"], nt = {
	key: 1,
	class: "tc-detail-muted"
}, rt = {
	key: 2,
	class: "tc-flow-relations"
}, it = {
	key: 3,
	class: "tc-child-tasks"
}, at = ["onClick"], ot = { id: "tc-step-title" }, st = { class: "tc-step-dialog-body" }, ct = /* @__PURE__ */ s({
	__name: "TaskProgress",
	props: {
		progress: {},
		filter: {},
		active: { type: Boolean },
		context: {},
		execution: {}
	},
	emits: ["filter", "child"],
	setup(n, { emit: r }) {
		let a = n, s = r, l = O(() => ae(a.progress?.main_steps)), u = e(null), d = O(() => l.value.find((e) => Ce(e) === u.value)), f = e(), _ = null, x = O(() => ue(a.progress?.outcome?.child_tasks).flatMap((e) => {
			try {
				return [{
					...e,
					task_id: L(e.task_id),
					run_id: ee(e.run_id),
					task_type: e.task_type,
					status: e.status
				}];
			} catch {
				return [];
			}
		})), S = O(() => {
			let e = ve(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${B(Te(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			return t ? `当前：${t.label || t.step_id || "执行中"}${t.child_label ? ` · ${t.child_label}` : ""}` : "执行阶段";
		});
		function T(e) {
			return [
				Ee(e),
				J(e),
				...ye(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function E(e) {
			return Ce(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function k(e) {
			_ = document.activeElement instanceof HTMLElement ? document.activeElement : null, u.value = Ce(e), await C(), f.value?.open || f.value?.showModal();
		}
		function A() {
			f.value?.close(), u.value = null, _?.isConnected && _.focus({ preventScroll: !0 }), _ = null;
		}
		function M(e) {
			let t = f.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return c(() => [a.context, a.active], A), t(() => f.value?.close()), (e, t) => n.progress ? (o(), p("section", Ye, [
			w("div", Xe, [w("strong", null, v(S.value), 1), w("small", null, v(n.progress.source === "legacy_derived" ? "历史记录还原" : n.progress.source === "insufficient_evidence" ? "步骤记录缺失" : "按首次记录排列，可含分支与重试"), 1)]),
			l.value.length ? (o(), p("ul", Ze, [(o(!0), p(j, null, i(l.value, (e) => (o(), p("li", {
				key: D(Ce)(e),
				class: g([
					"tc-step",
					`tc-step--${D(oe)(e)}`,
					{ "tc-step--selected": E(e) }
				])
			}, [w("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": E(e),
				title: T(e),
				onClick: (t) => s("filter", E(e) ? null : D(Ce)(e))
			}, [
				t[2] ||= w("span", {
					class: "tc-step-dot",
					"aria-hidden": "true"
				}, null, -1),
				w("strong", null, v(D(Ee)(e)), 1),
				w("span", $e, [
					m(v(D(J)(e)), 1),
					D(ie)(e) == null ? y("", !0) : (o(), p("small", et, " · " + v(D(te)(D(ie)(e))), 1)),
					(o(!0), p(j, null, i(D(ye)(e), (e) => (o(), p("small", { key: e }, " · " + v(e), 1))), 128))
				])
			], 8, Qe), w("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${D(Ee)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => k(e)
			}, [...t[3] ||= [w("svg", {
				viewBox: "0 0 16 16",
				width: "14",
				height: "14",
				"aria-hidden": "true"
			}, [w("circle", {
				cx: "8",
				cy: "8",
				r: "5.5",
				fill: "none",
				stroke: "currentColor"
			}), w("path", {
				d: "M8 7v4M8 4.5v1",
				stroke: "currentColor",
				"stroke-width": "1.5"
			})], -1)]], 8, tt)], 2))), 128))])) : (o(), p("p", nt, "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。")),
			l.value.length ? (o(), p("details", rt, [
				t[4] ||= w("summary", null, "依赖与执行记录", -1),
				w("p", null, v(n.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1),
				(o(!0), p(j, null, i(l.value, (e) => (o(), p("div", {
					key: D(Ce)(e),
					class: "tc-flow-relation"
				}, [w("strong", null, v(D(Ee)(e)), 1), N(ge, {
					step: e,
					siblings: l.value
				}, null, 8, ["step", "siblings"])]))), 128))
			])) : y("", !0),
			N(Je, {
				failure: n.progress.failure,
				execution: n.execution,
				status: n.progress.outcome.status
			}, null, 8, [
				"failure",
				"execution",
				"status"
			]),
			x.value.length ? (o(), p("div", it, [t[5] ||= w("strong", null, "独立子任务", -1), (o(!0), p(j, null, i(x.value, (e) => (o(), p("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, v(D(V)("task_type", D(Te)(e.task_type))) + " #" + v(e.task_id) + " · " + v(D(de)(e.status)), 9, at))), 128))])) : y("", !0),
			w("dialog", {
				ref_key: "inspector",
				ref: f,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: h(A, ["prevent"]),
				onClose: t[0] ||= (e) => u.value = null,
				onWheel: h(M, ["stop"]),
				onClick: t[1] ||= (e) => {
					e.target === f.value && A();
				}
			}, [w("header", null, [w("h3", ot, v(d.value ? D(Ee)(d.value) : "步骤详情"), 1), w("button", {
				type: "button",
				autofocus: "",
				onClick: A
			}, "关闭")]), w("div", st, [d.value ? (o(), b(xe, {
				key: 0,
				step: d.value,
				siblings: l.value
			}, null, 8, ["step", "siblings"])) : y("", !0)])], 544)
		])) : y("", !0);
	}
}), lt = { class: "tc-detail-header" }, ut = { id: "tc-detail-title" }, dt = { key: 0 }, ft = ["title"], pt = {
	key: 0,
	class: "tc-detail-status"
}, mt = {
	key: 1,
	class: "tc-detail-run"
}, ht = ["value", "disabled"], gt = ["value"], _t = {
	key: 1,
	value: ""
}, vt = ["value"], yt = { class: "tc-detail-header-actions" }, bt = ["disabled"], xt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, St = { key: 0 }, Ct = ["disabled"], wt = {
	key: 1,
	class: "tc-detail-empty",
	role: "status"
}, Tt = {
	key: 0,
	class: "tc-detail-notice"
}, Et = {
	key: 1,
	class: "tc-detail-notice"
}, Dt = {
	key: 3,
	class: "tc-detail-error",
	role: "status"
}, Ot = { class: "tc-detail-view-toolbar" }, kt = [
	"id",
	"data-detail-tab",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], At = { class: "tc-detail-filter" }, jt = {
	key: 0,
	class: "tc-detail-read-toolbar"
}, Mt = ["aria-pressed", "disabled"], Nt = ["aria-pressed", "disabled"], Pt = {
	id: "tc-detail-panel-events",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-events",
	tabindex: "0"
}, Ft = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, It = ["disabled"], Lt = {
	key: 1,
	class: "tc-detail-notice"
}, Rt = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, zt = { class: "tc-event-meta" }, Bt = { key: 0 }, Vt = {
	key: 0,
	class: "tc-technical"
}, Ht = ["disabled"], Ut = {
	id: "tc-detail-panel-logs",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-logs",
	tabindex: "0"
}, Wt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Gt = ["disabled"], Kt = {
	key: 1,
	class: "tc-detail-notice"
}, qt = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, Jt = { class: "tc-event-meta" }, Yt = {
	key: 0,
	class: "tc-technical"
}, Xt = ["disabled"], Zt = {
	id: "tc-detail-panel-artifacts",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-artifacts",
	tabindex: "0"
}, Qt = {
	key: 0,
	class: "tc-artifact"
}, $t = { key: 0 }, en = { class: "tc-artifact-links" }, tn = ["href"], nn = ["href"], rn = ["href"], an = {
	key: 1,
	class: "tc-detail-empty"
}, on = {
	key: 2,
	class: "tc-technical"
}, sn = { class: "tc-detail-footer" }, cn = {
	key: 1,
	role: "status"
}, ln = /* @__PURE__ */ s({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(n, { expose: a, emit: s }) {
		let l = s, u = ze(void 0, () => l("refresh")), { opened: d, taskId: f, runId: x, task: T, runs: k, selectedRun: A, progress: M, events: P, logs: F, tab: I, stepFilter: L, error: ee, progressError: z, eventsError: H, logsError: U, loading: W, eventsLoading: G, logsLoading: K, eventsMode: q, logsMode: re, eventsEarlier: ie, eventsMore: ae, logsEarlier: oe, logsMore: se, logsAvailable: le } = u, ue = e(), J = e(), fe = e(0), pe = Intl.DateTimeFormat().resolvedOptions().timeZone, me = [
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
		], ge = O(() => M.value?.main_steps || []), ye = O(() => ge.value.find((e) => Ce(e) === L.value || !!(L.value && e.raw_stages?.includes(L.value)))), xe = O(() => he(P.value.filter((e) => Se(e, L.value, ge.value)))), we = O(() => F.value.filter((e) => Se(e, L.value, ge.value, !0))), De = O(() => xe.value.map((e) => {
			let t = be(e), n = ce(e.detail);
			return {
				event: e,
				state: t,
				timestamp: B(e.created_at),
				stageLabel: e.stage_label || V("stage", e.stage),
				association: Pe(e),
				stateLabel: t ? de(t) : "记录",
				detailJson: n ? JSON.stringify(n, null, 2) : null
			};
		})), Oe = O(() => we.value.map((e) => {
			let t = ce(e.fields);
			return {
				item: e,
				timestamp: e.ts ? B(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), ke = O(() => x.value ? A.value : T.value), Ae = O(() => T.value?.email_snapshot || T.value?.email || (T.value?.account_id ? `账号 #${T.value.account_id}` : T.value?.target_id || "执行记录与诊断")), je = O(() => (T.value?.resources || []).filter((e) => !x.value || R(e.run_id, x.value))), Y = O(() => A.value?.debug_artifacts), Me = O(() => ve(A.value?.debug_pause || M.value?.debug_pause)), X = null, Ne = !1;
		function Pe(e) {
			let t = ve(e.detail), n = Te(e.main_step_id || t.main_step_id), r = Te(e.raw_stage || t.raw_stage || e.stage), i = ge.value.filter((e) => n ? e.id === n : e.raw_stages?.includes(r));
			return i.length === 1 ? Ee(i[0]) : "未关联步骤";
		}
		function Fe() {
			d.value && (u.close(), X?.isConnected && X.focus({ preventScroll: !0 }), X = null, l("close"));
		}
		function Ie() {
			ue.value?.close(), Fe();
		}
		async function Le(e, t, n) {
			d.value || (X = document.activeElement instanceof HTMLElement ? document.activeElement : null), fe.value = 0, u.setVisible(!document.hidden);
			let r = u.open(e, t, n);
			return await C(), !ue.value?.open && d.value && ue.value?.showModal(), r;
		}
		function Re(e) {
			u.setVisible(e);
		}
		function Be() {
			Re(!document.hidden);
		}
		function Ve(e) {
			fe.value = 0, u.selectRun(e.target.value);
		}
		async function He(e) {
			fe.value = 0, await u.selectTab(e), await C(), J.value && (J.value.scrollTop = 0);
		}
		function Ue(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			let t = me.findIndex((e) => e.id === I.value), n = e.key === "Home" ? 0 : e.key === "End" ? me.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + me.length) % me.length;
			e.preventDefault(), He(me[n].id), e.currentTarget.querySelector(`[data-detail-tab="${me[n].id}"]`)?.focus();
		}
		async function We(e) {
			Ne = !0, I.value === "events" ? await u.loadEvents(e) : await u.loadLogs(e), await C(), J.value && e !== "next" && (J.value.scrollTop = e === "tail" ? J.value.scrollHeight : 0), fe.value = 0, Ne = !1;
		}
		function Ge() {
			J.value && (J.value.scrollTop = J.value.scrollHeight), fe.value = 0;
		}
		function Ke(e) {
			let t = J.value;
			ue.value && ue.value.scrollHeight > ue.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return c([P, F], async ([e, t], [n, r]) => {
			if (Ne) return;
			let i = J.value, a = !i || i.scrollTop + i.clientHeight >= i.scrollHeight - 40, o = I.value === "events" ? e.length - n.length : I.value === "logs" ? t.length - r.length : 0;
			o <= 0 || (await C(), a ? Ge() : fe.value += o);
		}), c(L, () => {
			fe.value = 0, J.value && (J.value.scrollTop = 0);
		}), S(() => {
			Be(), document.addEventListener("visibilitychange", Be);
		}), t(() => {
			document.removeEventListener("visibilitychange", Be), ue.value?.close();
		}), a({
			open: Le,
			close: Ie,
			setVisible: Re
		}), (e, t) => (o(), b(_, { to: "body" }, [w("dialog", {
			ref_key: "dialog",
			ref: ue,
			class: "tc-detail-dialog",
			"aria-labelledby": "tc-detail-title",
			onCancel: h(Ie, ["prevent"]),
			onClose: Fe,
			onWheel: Ke
		}, [
			w("header", lt, [
				w("h2", ut, [m("任务 #" + v(D(f)) + " ", 1), D(T) ? (o(), p("span", dt, v(D(V)("task_type", D(T).task_type)), 1)) : y("", !0)]),
				w("span", {
					class: "tc-detail-target",
					title: String(Ae.value),
					tabindex: "0"
				}, v(Ae.value), 9, ft),
				ke.value ? (o(), p("div", pt, [w("strong", null, v(D(V)("status", ke.value.status)), 1), w("span", null, "耗时 " + v(D(te)(ke.value.duration_ms)), 1)])) : y("", !0),
				D(T) ? (o(), p("label", mt, [t[10] ||= w("span", null, "运行", -1), w("select", {
					value: D(x) || "",
					"aria-label": "选择执行实例",
					disabled: D(k).length < 2 && (!D(x) || !!D(A)),
					onChange: Ve
				}, [D(x) && !D(A) ? (o(), p("option", {
					key: 0,
					value: D(x),
					disabled: ""
				}, "运行 #" + v(D(x)) + " 不可用", 9, gt)) : D(k).length ? y("", !0) : (o(), p("option", _t, "暂无运行")), (o(!0), p(j, null, i(D(k), (e) => (o(), p("option", {
					key: e.id,
					value: e.id
				}, "第 " + v(e.run_no || "—") + " 次 · " + v(D(V)("status", e.status)), 9, vt))), 128))], 40, ht)])) : y("", !0),
				w("div", yt, [w("button", {
					type: "button",
					disabled: D(W),
					onClick: t[0] ||= (...e) => D(u).refresh && D(u).refresh(...e)
				}, v(D(W) ? "刷新中…" : "刷新"), 9, bt), w("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Ie
				}, "关闭")])
			]),
			D(ee) ? (o(), p("div", xt, [
				m("读取任务失败：" + v(D(ee)), 1),
				D(T) ? (o(), p("span", St, "。保留上次已读取的记录。")) : y("", !0),
				w("button", {
					type: "button",
					disabled: D(W),
					onClick: t[1] ||= (...e) => D(u).refresh && D(u).refresh(...e)
				}, "重试", 8, Ct)
			])) : y("", !0),
			D(W) && !D(T) ? (o(), p("div", wt, "正在读取任务详情…")) : y("", !0),
			D(T) ? (o(), p(j, { key: 2 }, [
				ke.value?.status === "queued" ? (o(), p("p", Tt, v(D(ne)(ke.value)), 1)) : y("", !0),
				Me.value.state === "paused" ? (o(), p("p", Et, [t[11] ||= m("调试暂停，等待结束调试。", -1), Me.value.hold_until ? (o(), p(j, { key: 0 }, [m("保留至 " + v(D(B)(Me.value.hold_until)) + "。", 1)], 64)) : y("", !0)])) : y("", !0),
				D(M) ? y("", !0) : (o(), b(Je, {
					key: 2,
					execution: ke.value,
					status: ke.value?.status
				}, null, 8, ["execution", "status"])),
				N(ct, {
					progress: D(M),
					execution: ke.value,
					filter: D(L),
					active: D(d),
					context: `${D(f)}:${D(x)}`,
					onFilter: t[2] ||= (e) => L.value = e,
					onChild: Le
				}, null, 8, [
					"progress",
					"execution",
					"filter",
					"active",
					"context"
				]),
				D(z) ? (o(), p("p", Dt, [m("进度读取失败：" + v(D(z)), 1), D(M) ? (o(), p(j, { key: 0 }, [m("；保留上次快照")], 64)) : y("", !0)])) : y("", !0),
				w("div", Ot, [
					w("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: Ue
					}, [(o(), p(j, null, i(me, (e) => w("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": D(I) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: D(I) === e.id ? 0 : -1,
						onClick: (t) => He(e.id)
					}, v(e.label), 9, kt)), 64))], 32),
					w("div", At, [w("span", null, [t[12] ||= m("当前查看：", -1), w("strong", null, v(ye.value ? D(Ee)(ye.value) : D(L) || "全流程"), 1)]), D(L) ? (o(), p("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => L.value = null
					}, "清除步骤筛选")) : y("", !0)]),
					D(I) === "artifacts" ? y("", !0) : (o(), p("div", jt, [w("button", {
						type: "button",
						"aria-pressed": (D(I) === "events" ? D(q) : D(re)) === "start",
						disabled: D(G) || D(K) || !D(x),
						onClick: t[4] ||= (e) => We("start")
					}, "从头加载", 8, Mt), w("button", {
						type: "button",
						"aria-pressed": (D(I) === "events" ? D(q) : D(re)) === "tail",
						disabled: D(G) || D(K) || !D(x),
						onClick: t[5] ||= (e) => We("tail")
					}, "最近记录", 8, Nt)]))
				]),
				w("div", {
					ref_key: "scroller",
					ref: J,
					class: "tc-detail-content"
				}, [
					r(w("section", Pt, [
						D(H) ? (o(), p("p", Ft, [m("事件读取失败：" + v(D(H)), 1), w("button", {
							type: "button",
							disabled: D(G),
							onClick: t[6] ||= (e) => D(u).loadEvents()
						}, "重试", 8, It)])) : y("", !0),
						D(ie) ? (o(), p("p", Lt, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : y("", !0),
						xe.value.length ? y("", !0) : (o(), p("div", Rt, v(D(G) ? "正在读取事件…" : D(L) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(o(!0), p(j, null, i(De.value, (e) => (o(), p("article", {
							key: e.event.id,
							class: g(["tc-event", { "tc-event--error": e.state === "failed" }])
						}, [
							w("div", zt, [
								w("time", null, v(e.timestamp), 1),
								w("span", null, v(e.event.level || "INFO"), 1),
								w("strong", null, v(e.stageLabel), 1),
								e.association ? (o(), p("span", Bt, v(e.association), 1)) : y("", !0),
								w("span", null, v(e.stateLabel), 1),
								w("small", null, "事件 " + v(e.event.event_id || e.event.id), 1)
							]),
							w("p", null, v(e.event.message || "—"), 1),
							e.detailJson ? (o(), p("details", Vt, [t[13] ||= w("summary", null, "技术详情", -1), w("pre", null, v(e.detailJson), 1)])) : y("", !0)
						], 2))), 128)),
						D(ae) ? (o(), p("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: D(G),
							onClick: t[7] ||= (e) => We("next")
						}, v(D(G) ? "正在读取…" : "继续加载后续事件"), 9, Ht)) : y("", !0)
					], 512), [[E, D(I) === "events"]]),
					r(w("section", Ut, [
						D(U) ? (o(), p("p", Wt, [m("日志读取失败：" + v(D(U)), 1), w("button", {
							type: "button",
							disabled: D(K),
							onClick: t[8] ||= (e) => D(u).loadLogs()
						}, "重试", 8, Gt)])) : y("", !0),
						D(oe) ? (o(), p("p", Kt, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : y("", !0),
						we.value.length ? y("", !0) : (o(), p("div", qt, v(D(K) ? "正在读取运行日志…" : D(le) ? D(L) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(o(!0), p(j, null, i(Oe.value, (e, n) => (o(), p("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${n}`,
							class: "tc-log-line"
						}, [
							w("div", Jt, [
								w("time", null, v(e.timestamp), 1),
								w("strong", null, v(e.item.level || "INFO"), 1),
								w("span", null, v(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							w("p", null, v(e.item.message), 1),
							e.detailJson ? (o(), p("details", Yt, [t[14] ||= w("summary", null, "技术详情", -1), w("pre", null, v(e.detailJson), 1)])) : y("", !0)
						]))), 128)),
						D(se) ? (o(), p("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: D(K),
							onClick: t[9] ||= (e) => We("next")
						}, v(D(K) ? "正在读取…" : "继续加载后续日志"), 9, Xt)) : y("", !0)
					], 512), [[E, D(I) === "logs"]]),
					r(w("section", Zt, [
						Y.value?.available ? (o(), p("article", Qt, [
							t[15] ||= w("h3", null, "Roxy 刷新调试", -1),
							w("p", null, v(Y.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + v(D(ve)(Y.value.summary).request_count || 0) + " 条", 1),
							D(A)?.result_summary?.debug_browser_kept === !0 ? (o(), p("p", $t, "失败窗口已保留，可在 Roxy 中查看。")) : y("", !0),
							w("div", en, [
								D(_e)(Y.value.har_url) ? (o(), p("a", {
									key: 0,
									href: D(_e)(Y.value.har_url),
									download: ""
								}, "下载 HAR", 8, tn)) : y("", !0),
								D(_e)(Y.value.page_state_url) ? (o(), p("a", {
									key: 1,
									href: D(_e)(Y.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, nn)) : y("", !0),
								D(_e)(Y.value.screenshot_url) ? (o(), p("a", {
									key: 2,
									href: D(_e)(Y.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, rn)) : y("", !0)
							])
						])) : y("", !0),
						(o(!0), p(j, null, i(je.value, (e, t) => (o(), p("article", {
							key: D(Te)(e.id) || t,
							class: "tc-artifact"
						}, [
							w("h3", null, v(e.resource_type || "运行资源"), 1),
							w("p", null, v(e.provider || e.state || "—"), 1),
							w("small", null, v(D(B)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!Y.value?.available && !je.value.length ? (o(), p("div", an, "当前 Run 没有诊断资源或产物")) : y("", !0),
						ke.value?.result_summary ? (o(), p("details", on, [t[16] ||= w("summary", null, "执行结果字段", -1), w("pre", null, v(JSON.stringify(ke.value.result_summary, null, 2)), 1)])) : y("", !0)
					], 512), [[E, D(I) === "artifacts"]])
				], 512),
				w("footer", sn, [w("small", null, "时间按浏览器时区显示 · " + v(D(pe)), 1), fe.value && D(I) !== "artifacts" ? (o(), p("button", {
					key: 0,
					type: "button",
					onClick: Ge
				}, "有 " + v(fe.value) + " 条新记录，回到底部", 1)) : D(W) || D(G) || D(K) ? (o(), p("small", cn, "正在同步记录…")) : y("", !0)])
			], 64)) : y("", !0)
		], 544)]));
	}
}), un = [
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
function dn(e, t) {
	return e.fields.some((e) => !!t[e]);
}
function fn(e, t, n) {
	if (e.kind === "date-range") {
		let e = t.created_from, n = t.created_to;
		return e && n ? `创建日期 ${e} 至 ${n}` : e ? `创建日期自 ${e}` : n ? `创建日期截至 ${n}` : "";
	}
	let r = t[e.fields[0]];
	if (!r || e.kind !== "select") return r;
	let i = e.group || "", a = n[i] || [];
	return a.find((e) => e.value === r)?.label || r.split(",").map((e) => {
		let t = e.trim();
		return a.find((e) => e.value === t)?.label || V(i, t);
	}).join("、");
}
function pn(e, t) {
	let n = { ...t };
	for (let t of e.fields) n[t] = "";
	return n;
}
// src/features/tasks/TaskFilterFields.vue?vue&type=script&setup=true&lang.ts
var mn = {
	key: 0,
	class: "tc-filter-field"
}, hn = ["for"], gn = [
	"id",
	"value",
	"inputmode",
	"placeholder"
], _n = ["aria-label"], vn = ["name", "checked"], yn = { class: "tc-filter-option-label" }, bn = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], xn = { class: "tc-filter-option-label" }, Sn = {
	key: 0,
	class: "tc-filter-option-count"
}, Cn = {
	key: 2,
	class: "tc-filter-date-range"
}, wn = { class: "tc-filter-field" }, Tn = ["for"], En = ["id", "value"], Dn = { class: "tc-filter-field" }, On = ["for"], kn = ["id", "value"], An = { class: "tc-filter-footer" }, jn = ["disabled"], Mn = /* @__PURE__ */ s({
	__name: "TaskFilterFields",
	props: {
		column: {},
		modelValue: {},
		facets: {}
	},
	emits: ["update:modelValue", "done"],
	setup(e, { emit: t }) {
		let r = e, a = t, s = n(), c = O(() => r.column.fields[0]), l = O(() => r.modelValue[c.value]), u = {
			task_type: "全部类型",
			status: "全部状态",
			target_status: "全部目标状态",
			run_count: "全部次数",
			stage: "全部步骤"
		}, d = {
			stopping: "请求停止",
			cancelling: "请求取消"
		}, f = O(() => {
			let e = r.column.group || "", t = r.facets[e] || [], n = new Map(t.map((e) => [e.value, e])), i = /* @__PURE__ */ new Set([
				...Object.keys(fe[e] || {}),
				...t.map((e) => e.value),
				...l.value ? [l.value] : []
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
			return [...i].filter((t) => !!t && (e !== "status" || a.includes(t) || t === l.value)).map((t) => ({
				value: t,
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? fn(r.column, {
					...r.modelValue,
					[c.value]: t
				}, r.facets) : V(e, t)),
				count: n.get(t)?.count
			}));
		});
		function m(e, t) {
			a("update:modelValue", {
				...r.modelValue,
				[e]: t
			});
		}
		function _(e, t) {
			m(c.value, e), t.detail > 0 && a("done");
		}
		function b() {
			a("update:modelValue", pn(r.column, r.modelValue)), a("done");
		}
		return (t, n) => (o(), p("form", {
			class: "tc-filter-fields",
			onSubmit: n[5] ||= h((e) => a("done"), ["prevent"])
		}, [e.column.kind === "search" ? (o(), p("div", mn, [w("label", { for: `${D(s)}-search` }, v(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, hn), w("input", {
			id: `${D(s)}-search`,
			value: l.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: n[0] ||= (e) => m(c.value, e.target.value)
		}, null, 40, gn)])) : e.column.kind === "select" ? (o(), p("div", {
			key: 1,
			class: "tc-filter-options",
			role: "radiogroup",
			"aria-label": e.column.label
		}, [w("label", { class: g(["tc-filter-option", { "is-selected": !l.value }]) }, [w("input", {
			type: "radio",
			name: D(s),
			value: "",
			checked: !l.value,
			onChange: n[1] ||= (e) => m(c.value, ""),
			onClick: n[2] ||= (e) => _("", e)
		}, null, 40, vn), w("span", yn, v(u[e.column.group || ""] || "全部"), 1)], 2), (o(!0), p(j, null, i(f.value, (e) => (o(), p("label", {
			key: e.value,
			class: g(["tc-filter-option", { "is-selected": l.value === e.value }])
		}, [
			w("input", {
				type: "radio",
				name: D(s),
				value: e.value,
				checked: l.value === e.value,
				onChange: (t) => m(c.value, e.value),
				onClick: (t) => _(e.value, t)
			}, null, 40, bn),
			w("span", xn, v(e.text), 1),
			e.count == null ? y("", !0) : (o(), p("span", Sn, v(e.count), 1))
		], 2))), 128))], 8, _n)) : (o(), p("div", Cn, [
			n[6] ||= w("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			w("div", wn, [w("label", { for: `${D(s)}-from` }, "创建日期起", 8, Tn), w("input", {
				id: `${D(s)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: n[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, En)]),
			w("div", Dn, [w("label", { for: `${D(s)}-to` }, "创建日期止", 8, On), w("input", {
				id: `${D(s)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: n[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, kn)])
		])), w("div", An, [w("button", {
			type: "button",
			class: "tc-link",
			disabled: !D(dn)(e.column, e.modelValue),
			onClick: b
		}, "清除此列", 8, jn), n[7] ||= w("button", {
			type: "submit",
			class: "tc-button"
		}, "完成", -1)])], 32));
	}
}), Nn = { class: "tc-mobile-filters" }, Pn = { class: "tc-filter-column-picker" }, Fn = ["value"], In = /* @__PURE__ */ s({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(t, { emit: n }) {
		let a = t, s = n, c = e(un[0].key), u = O(() => un.find((e) => e.key === c.value)), d = O(() => un.filter((e) => dn(e, a.modelValue)).length);
		return (e, n) => (o(), p("div", Nn, [N(Oe, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: t.open,
			"onUpdate:open": n[3] ||= (e) => s("update:open", e)
		}, {
			default: l(() => [w("label", Pn, [n[4] ||= m("筛选列", -1), r(w("select", { "onUpdate:modelValue": n[0] ||= (e) => c.value = e }, [(o(!0), p(j, null, i(D(un), (e) => (o(), p("option", {
				key: e.key,
				value: e.key
			}, v(e.label) + v(D(dn)(e, t.modelValue) ? " · 已筛选" : ""), 9, Fn))), 128))], 512), [[x, c.value]])]), (o(), b(Mn, {
				key: c.value,
				column: u.value,
				"model-value": t.modelValue,
				facets: t.facets,
				"onUpdate:modelValue": n[1] ||= (e) => s("update:modelValue", e),
				onDone: n[2] ||= (e) => s("update:open", !1)
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
}), Ln = /* @__PURE__ */ s({
	__name: "TaskColumnFilter",
	props: {
		column: {},
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let n = t;
		return (t, r) => (o(), b(Oe, {
			label: e.column.label,
			active: D(dn)(e.column, e.modelValue),
			summary: D(fn)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": r[2] ||= (e) => n("update:open", e)
		}, {
			default: l(() => [N(Mn, {
				column: e.column,
				"model-value": e.modelValue,
				facets: e.facets,
				"onUpdate:modelValue": r[0] ||= (e) => n("update:modelValue", e),
				onDone: r[1] ||= (e) => n("update:open", !1)
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
}), Rn = /* @__PURE__ */ new Set([
	"failed",
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"password_confirmation_pending"
]), zn = /* @__PURE__ */ new Set([
	"running",
	"waiting",
	"stopping",
	"cancelling",
	"settling"
]), Bn = /* @__PURE__ */ new Set([
	"cancelled",
	"stopped",
	"interrupted"
]), Vn = {
	email_verification_pending: "待验证或补全",
	credential_pending_confirmation: "凭证待核验"
};
function Hn(e, t, n) {
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${V(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function Un(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function Wn(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: V("status", t),
		tone: q(t),
		title: Hn("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = ne(e) || void 0) : zn.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = ne(e) || Un(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : Rn.has(t) ? (r.label = "失败", r.tone = "danger") : Bn.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (Rn.has(n) && Rn.has(t) || n === "completed" && t === "success" || n === "in_progress" && zn.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: Vn[n] || V("target_status", n),
			tone: q(n),
			title: Hn("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Z = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), Gn = (e) => Array.isArray(e) ? e.map(G) : [], Q = (e) => String(e || "").toLowerCase(), $ = /* @__PURE__ */ new Set([
	"unknown",
	"request_unknown",
	"attention_required",
	"manual_reconcile",
	"unconfirmed",
	"password_confirmation_pending",
	"credential_pending_confirmation"
]), Kn = /* @__PURE__ */ new Set([
	"failed",
	"error",
	"deactivated"
]);
function qn(e) {
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
var Jn = {
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
}, Yn = {
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
	sentinel_maintenance_check: "维护检查完成"
};
function Xn(e, t) {
	let n = G(e.result_summary), r = Q(e.status), i = Q(n.extraction_status), a = Q(n.payment_status);
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
	].includes(r) ? Z("提链成功", "warning", "后续已中断") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Z("提链成功", "danger", "后续失败") : Z("提链成功", "success") : Kn.has(i) || qn(e) ? Z(t, "danger") : $.has(i) ? Z("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Z("等待提链", "warning") : i === "running" ? Z("提链中", "active") : r === "cancelled" ? Z("已取消") : ["stopped", "interrupted"].includes(r) ? Z("执行已中断", "warning") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Z(t, "danger") : n.ok === !0 ? Z("提链流程完成", "success") : Z("提链结果缺失", "warning");
}
function Zn(e, t) {
	let n = G(e.result_summary), r = Q(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : Gn(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes(Q(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = G(e.result);
		return !t && !e.last_success_at ? [] : Gn(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : Gn(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(G(e.result)).length > 0);
	if (s > 0 && o > 0 || !i && n.plan_check_partial === !0) return Z("部分失败", "warning", u ? "含历史数据" : void 0);
	if (c > 0 && s >= c) return u ? Z("查询失败", "danger", "含历史数据") : Z(t, "danger");
	if (qn(e)) return Z(t, "danger");
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
function Qn(e, t = "执行异常") {
	let n = G(e.result_summary), r = Q(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
	if (e.debug_pause) return Z("调试已暂停", "warning");
	if (["queued", "pending"].includes(r)) {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(Jn[String(t)] || "等待执行", "warning");
	}
	if (r === "waiting") {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(Jn[String(t)] || Un(e), "warning");
	}
	if (r === "running") return Z("执行中", "active");
	if (["stopping", "cancelling"].includes(r)) return Z("正在停止", "warning");
	if (r === "settling") return Z("正在收尾", "active");
	if (i === "extract_link") return Xn(e, a);
	if (i === "email_change" && n.email_change_confirmed === !0) return Z("邮箱已换绑", "success", G(n.post_change_live_check).accepted ? "刷新已排队" : "刷新待处理");
	if (i === "codex_retry" && n.ok === !0) {
		let e = Q(G(n.sub2api_sync).status);
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
	if (i === "plan_check") return Zn(e, a);
	if (r === "cancelled") return Z("已取消");
	if (["stopped", "interrupted"].includes(r)) return Z("执行已中断", "warning");
	if (qn(e)) return Z(a, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes(Q(e.target_status)) || r === "deactivated") return Z("账号已停用", "danger");
	if (e.error_message || e.error_info || n.ok === !1 || Kn.has(r)) return Z(a, "danger");
	if (r === "partial_success") return Z("部分完成", "warning");
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
	return i === "deactivation_mail" && typeof n.detected == "boolean" ? Z(n.detected ? "发现封号邮件" : "未见封号邮件", n.detected ? "warning" : "neutral") : i === "live_check" && n.ok === !0 ? Z("账号正常", "success") : i === "token_refresh" && n.ok === !0 ? Z("令牌已刷新", "success") : i === "account_inspection_batch" && Number(n.failed_count) > 0 ? Z("巡检已完成", "warning", "存在失败") : r === "success" || n.ok === !0 ? Z(Yn[i] || "任务已完成", "success") : Z("结果未记录");
}
// src/features/tasks/TaskResultCell.vue
var $n = /* @__PURE__ */ s({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, n = O(() => Qn(t.task, Y(t.task.error_info))), r = O(() => [...new Set([
			K(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? W(t.task.error_info, t.task.error_message) : "",
			t.task.error_message
		].filter((e) => !!e))]);
		return (e, t) => (o(), b(je, a(n.value, { title: r.value.join("\n") }), {
			details: l(() => [(o(!0), p(j, null, i(r.value, (e, t) => (o(), p("p", { key: t }, v(e), 1))), 128))]),
			_: 1
		}, 16, ["title"]));
	}
}), er = ["aria-busy"], tr = [
	"checked",
	"indeterminate",
	"disabled"
], nr = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], rr = { "data-label": "选择" }, ir = [
	"checked",
	"aria-label",
	"onChange"
], ar = { "data-label": "ID" }, or = ["onClick"], sr = { "data-label": "类型" }, cr = { "data-label": "目标" }, lr = { "data-label": "执行状态" }, ur = ["title"], dr = ["title"], fr = { "data-label": "目标状态" }, pr = ["title"], mr = {
	key: 1,
	class: "tc-cell-line",
	"aria-label": "无额外目标状态"
}, hr = { "data-label": "批次 / 触发" }, gr = ["onClick"], _r = { "data-label": "运行次数" }, vr = { "data-label": "当前步骤" }, yr = {
	"data-label": "创建 / 完成",
	class: "tc-time"
}, br = { "data-label": "结果 / 错误" }, xr = { "data-label": "操作" }, Sr = { class: "tc-row-actions" }, Cr = ["onClick"], wr = ["disabled", "onClick"], Tr = ["disabled", "onClick"], Er = ["disabled", "onClick"], Dr = {
	key: 0,
	class: "tc-empty-row"
}, Or = ["colspan"], kr = ["role"], Ar = {
	key: 0,
	class: "tc-spinner",
	"aria-hidden": "true"
}, jr = /* @__PURE__ */ s({
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
	setup(e, { expose: t, emit: n }) {
		let r = e, a = n, s = O(() => r.items.length > 0 && r.items.every((e) => r.selected.has(e.id))), c = O(() => !s.value && r.items.some((e) => r.selected.has(e.id))), u = O(() => r.items.map((e) => ({
			task: e,
			...Wn(e)
		}))), d = [
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
		], { widths: f, resize: _, resizeWithKeyboard: x, resetColumns: S } = Ae({
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
			return U(e) || e.current_stage_label || V("stage", e.current_stage);
		}
		function T(e) {
			return [
				e.current_stage_label || V("stage", e.current_stage),
				U(e),
				te(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function E(e) {
			return String(e.bulk_batch_id || G(e.bulk_context).batch_id || "");
		}
		function A(e) {
			return String(e.bulk_round_id || G(e.bulk_context).round_id || "");
		}
		return t({ resetColumns: S }), (t, n) => (o(), p("div", {
			class: "tc-table-scroll",
			tabindex: "0",
			"aria-label": "任务列表，可横向滚动",
			"aria-busy": e.loading
		}, [w("table", {
			class: "tc-table",
			style: M({ "--tc-table-width": `${D(f).reduce((e, t) => e + t, 0)}px` })
		}, [
			n[3] ||= w("caption", { class: "tc-sr-only" }, "任务中心列表，选择任务可批量操作", -1),
			w("colgroup", null, [(o(!0), p(j, null, i(D(f), (e, t) => (o(), p("col", {
				key: t,
				style: M({ width: `${e}px` })
			}, null, 4))), 128))]),
			w("thead", null, [w("tr", null, [(o(), p(j, null, i(d, (t, r) => w("th", {
				key: t,
				scope: "col"
			}, [r === 0 ? (o(), p("input", {
				key: 0,
				type: "checkbox",
				"aria-label": "全选当前页任务",
				checked: s.value,
				indeterminate: c.value,
				disabled: !e.items.length,
				onChange: n[0] ||= (e) => a("selectPage", e.target.checked)
			}, null, 40, tr)) : (o(), p(j, { key: 1 }, [D(un)[r - 1] ? (o(), b(Ln, {
				key: 0,
				column: D(un)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === D(un)[r - 1].key,
				"onUpdate:modelValue": n[1] ||= (e) => a("update:filters", e),
				"onUpdate:open": (e) => a("update:openFilter", e ? D(un)[r - 1].key : null)
			}, null, 8, [
				"column",
				"model-value",
				"facets",
				"open",
				"onUpdate:open"
			])) : (o(), p(j, { key: 1 }, [m(v(t), 1)], 64)), r < d.length - 1 ? (o(), p("button", {
				key: 2,
				type: "button",
				class: "tc-column-resize",
				"aria-label": `调整${t}列宽，方向键调整`,
				onPointerdown: h((e) => D(_)(r, e), ["prevent"]),
				onKeydown: [k(h((e) => D(x)(r, -10), ["prevent"]), ["left"]), k(h((e) => D(x)(r, 10), ["prevent"]), ["right"])]
			}, null, 40, nr)) : y("", !0)], 64))])), 64))])]),
			w("tbody", null, [(o(!0), p(j, null, i(u.value, ({ task: t, execution: n, target: r }) => (o(), p("tr", {
				key: t.id,
				class: g({ "tc-row-selected": e.selected.has(t.id) })
			}, [
				w("td", rr, [w("input", {
					type: "checkbox",
					checked: e.selected.has(t.id),
					"aria-label": `选择任务 #${t.id}`,
					onChange: (e) => a("select", t.id, e.target.checked)
				}, null, 40, ir)]),
				w("td", ar, [w("button", {
					type: "button",
					class: "tc-link tc-task-id",
					onClick: (e) => a("detail", t.id)
				}, "#" + v(t.id), 9, or)]),
				w("td", sr, [N(De, { text: D(V)("task_type", t.task_type) }, null, 8, ["text"])]),
				w("td", cr, [N(De, {
					text: t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—",
					secondary: t.email_snapshot || t.email || "—"
				}, {
					default: l(() => [w("strong", null, v(t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—"), 1)]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				w("td", lr, [w("span", {
					class: g(["tc-badge", `tc-badge--${n.tone}`]),
					title: n.title
				}, v(n.label), 11, ur), n.secondary ? (o(), p("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: n.secondary
				}, v(n.secondary), 9, dr)) : y("", !0)]),
				w("td", fr, [r ? (o(), p("span", {
					key: 0,
					class: g(["tc-badge", `tc-badge--${r.tone}`]),
					title: r.title
				}, v(r.label), 11, pr)) : (o(), p("span", mr, "—"))]),
				w("td", hr, [N(De, {
					text: t.batch_title || t.batch_uuid || (E(t) ? "查看批次" : "单任务"),
					secondary: D(V)("trigger", t.trigger)
				}, {
					default: l(() => [E(t) ? (o(), p("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						onClick: (e) => a("batch", E(t), A(t))
					}, v(t.batch_title || t.batch_uuid || "查看批次"), 9, gr)) : (o(), p(j, { key: 1 }, [m(v(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				w("td", _r, [N(De, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				w("td", vr, [N(De, {
					text: C(t),
					secondary: D(te)(t.duration_ms),
					title: T(t),
					tone: D(U)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				w("td", yr, [N(De, {
					text: D(B)(t.created_at),
					secondary: D(B)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				w("td", br, [N($n, { task: t }, null, 8, ["task"])]),
				w("td", xr, [w("div", Sr, [
					w("button", {
						type: "button",
						class: "tc-link",
						onClick: (e) => a("detail", t.id)
					}, "详情", 8, Cr),
					D(H)(t) ? (o(), p("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						disabled: e.busy,
						onClick: (e) => a("action", t, "retry")
					}, "重跑", 8, wr)) : y("", !0),
					D(we)(t) ? (o(), p("button", {
						key: 1,
						type: "button",
						class: "tc-link tc-text-danger",
						disabled: e.busy,
						onClick: (e) => a("action", t, "terminate")
					}, v(t.status === "queued" ? "取消" : "终止"), 9, Tr)) : y("", !0),
					D(pe)(t) ? y("", !0) : (o(), p("button", {
						key: 2,
						type: "button",
						class: "tc-link tc-text-danger",
						disabled: e.busy,
						onClick: (e) => a("action", t, "delete")
					}, "删除", 8, Er))
				])])
			], 2))), 128)), e.items.length ? y("", !0) : (o(), p("tr", Dr, [w("td", { colspan: d.length }, [w("div", {
				class: "tc-empty",
				role: e.error ? "alert" : "status"
			}, [
				e.loading ? (o(), p("span", Ar)) : y("", !0),
				w("strong", null, v(e.loading ? "正在加载任务记录" : e.error ? "任务列表加载失败" : "没有匹配的任务"), 1),
				w("p", null, v(e.error || (e.loading ? "正在同步任务状态" : "可调整筛选条件，或清除全部筛选。")), 1),
				e.error ? (o(), p("button", {
					key: 1,
					type: "button",
					class: "tc-button",
					onClick: n[2] ||= (e) => a("retry")
				}, "重新加载")) : y("", !0)
			], 8, kr)], 8, Or)]))])
		], 4)], 8, er));
	}
}), Mr = /* @__PURE__ */ s({
	__name: "StatusBadge",
	props: {
		value: {},
		group: { default: "status" }
	},
	setup(e) {
		return (t, n) => (o(), p("span", { class: g(["tc-badge", `tc-badge--${D(q)(e.value)}`]) }, v(D(V)(e.group, e.value)), 3));
	}
});
// src/features/tasks/useTaskList.ts
function Nr() {
	let t = f(Ne()), n = e(1), r = e(20), i = e(0), a = e([]), o = e({}), s = e(/* @__PURE__ */ new Set()), l = e(!1), d = e(""), p = e(!1), m = O(() => Math.max(1, Math.ceil(i.value / r.value))), h = 0, g = null, _, v, y = 0, b = 0, x = "", S = "", w = /* @__PURE__ */ new Set([
		"task_id",
		"target",
		"batch",
		"result"
	]), T = null;
	function E(e = {}, t = 0) {
		clearTimeout(v);
		let n = ++y, r = () => {
			n === y && p.value && !document.hidden && k(e);
		};
		t ? v = setTimeout(r, t) : C(r);
	}
	let D = () => {
		clearTimeout(_), p.value && !document.hidden && (_ = setTimeout(() => void k(), 5e3));
	};
	async function k(e = {}) {
		clearTimeout(_), clearTimeout(v), ++y;
		let c = {
			...t,
			page: n.value,
			page_size: r.value
		}, u = JSON.stringify(c), f = e.metadata || x !== u || Date.now() - b >= 3e4, p = ++h;
		g?.abort(), g = new AbortController(), l.value = !0;
		try {
			let e = await Le.list({
				...c,
				include_facets: +!!f,
				include_batches: 0
			}, g.signal);
			if (p !== h) return;
			if (i.value = Number(e.total || 0), n.value > m.value) {
				n.value = m.value;
				return;
			}
			let t = u + (e.revision || JSON.stringify(e.items));
			if (S !== t) {
				a.value = e.items || [], S = t;
				let n = new Set(a.value.map((e) => e.id));
				s.value = new Set([...s.value].filter((e) => n.has(e)));
			}
			e.facets && (o.value = e.facets), f && (b = Date.now(), x = u), d.value = "";
		} catch (e) {
			p === h && !P(e) && (d.value = e instanceof Error ? e.message : "任务列表加载失败");
		} finally {
			p === h && (l.value = !1, g = null, D());
		}
	}
	function A(e) {
		e !== p.value && (p.value = e, clearTimeout(_), clearTimeout(v), e && !document.hidden ? E() : (++y, g?.abort(), ++h, l.value = !1));
	}
	function j(e, r = !0) {
		Object.assign(t, r ? {
			...Ne(),
			...e
		} : e), n.value = 1, s.value = /* @__PURE__ */ new Set();
	}
	function M(e, t) {
		let n = new Set(s.value);
		t ? n.add(e) : n.delete(e), s.value = n;
	}
	function N(e) {
		s.value = new Set(e ? a.value.map((e) => e.id) : []);
	}
	c(() => ({
		...t,
		page: n.value,
		page_size: r.value
	}), (e, r) => {
		s.value = /* @__PURE__ */ new Set(), clearTimeout(_);
		let i = Object.keys(t).filter((t) => e[t] !== r[t]);
		if (i.length && (T = {
			metadata: !0,
			delay: i.every((e) => w.has(e)) && e.page_size === r.page_size ? 260 : 0
		}, n.value !== 1)) {
			n.value = 1;
			return;
		}
		let a = T || {
			metadata: !1,
			delay: 0
		};
		T = null, ++h, g?.abort(), E({ metadata: a.metadata }, a.delay);
	});
	let F = () => {
		clearTimeout(_), document.hidden ? (++y, clearTimeout(v), g?.abort(), ++h, l.value = !1) : p.value && E();
	};
	return document.addEventListener("visibilitychange", F), u(() => {
		++h, ++y, g?.abort(), clearTimeout(_), clearTimeout(v), document.removeEventListener("visibilitychange", F);
	}), {
		filters: t,
		page: n,
		size: r,
		pages: m,
		total: i,
		items: a,
		facets: o,
		selected: s,
		loading: l,
		error: d,
		visible: p,
		refresh: k,
		setVisible: A,
		applyFilters: j,
		toggle: M,
		togglePage: N
	};
}
// src/features/tasks/useReceipts.ts
function Pr() {
	let t = e([]), n = e(!1), r = e(!1), i = e(""), a = /* @__PURE__ */ new Set([
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
	]), o = O(() => t.value.filter((e) => !a.has(e.status))), s, c = 0, l = 0, d = null, f = () => {
		clearTimeout(s), n.value && !document.hidden && o.value.length && (s = setTimeout(() => void p(), 2e3));
	};
	async function p() {
		if (r.value || !n.value || document.hidden || !o.value.length) return;
		let e = c % o.value.length, t = [...o.value.slice(e), ...o.value.slice(0, e)].slice(0, 20);
		c = e + t.length;
		let a = ++l;
		d = new AbortController(), r.value = !0, i.value = "";
		let s = await Promise.allSettled(t.map((e) => Le.detail(e.task_id, d.signal)));
		a === l && (s.forEach((e, n) => {
			let r = t[n];
			if (e.status === "rejected") {
				P(e.reason) || (i.value = "部分回执暂未读到，请稍后刷新。");
				return;
			}
			let a = e.value.task, o = a.runs?.find((e) => R(e.id, r.run_id));
			if (r.run_id && !o) {
				i.value = "部分执行记录暂未读到，请稍后刷新。";
				return;
			}
			let s = o || a, c = G(s.result_summary);
			r.status = s.status || "queued", r.message = s.error_message || String(c.message || (s.status === "success" ? "已确认完成" : ""));
		}), r.value = !1, d = null, f());
	}
	function m(e, n) {
		for (let r of e) if (r.accepted) try {
			let e = L(r.task_id), i = ee(r.run_id);
			if (t.value.some((t) => R(t.task_id, e) && (i === null ? t.run_id === null : R(t.run_id, i)))) continue;
			t.value.push({
				task_id: e,
				run_id: i,
				label: n,
				status: r.status || "queued",
				message: ""
			});
		} catch {
			i.value = "任务回执标识无效，无法读取原任务。";
		}
		p();
	}
	function h(e) {
		n.value = e, clearTimeout(s), e && !document.hidden ? p() : (++l, d?.abort(), r.value = !1);
	}
	let g = () => h(n.value);
	return document.addEventListener("visibilitychange", g), u(() => {
		++l, d?.abort(), clearTimeout(s), document.removeEventListener("visibilitychange", g);
	}), {
		items: t,
		pending: o,
		error: i,
		loading: r,
		track: m,
		refresh: p,
		setVisible: h
	};
}
// src/features/tasks/TaskCenter.vue?vue&type=script&setup=true&lang.ts
var Fr = {
	class: "tc-root",
	"aria-label": "统一任务中心"
}, Ir = {
	key: 0,
	class: "tc-receipts",
	"aria-label": "本次提交的任务回执"
}, Lr = { class: "tc-receipts-header" }, Rr = { role: "status" }, zr = ["disabled"], Br = {
	key: 0,
	class: "tc-text-danger",
	role: "alert"
}, Vr = { class: "tc-receipt-list" }, Hr = ["onClick"], Ur = { class: "tc-workspace" }, Wr = { class: "tc-toolbar-main" }, Gr = {
	class: "tc-selection",
	role: "status"
}, Kr = {
	key: 0,
	class: "tc-bulk-actions"
}, qr = ["disabled", "onClick"], Jr = { class: "tc-toolbar-end" }, Yr = ["title"], Xr = ["role"], Zr = { key: 1 }, Qr = /* @__PURE__ */ s({
	__name: "TaskCenter",
	emits: [
		"navigate",
		"batch",
		"changed"
	],
	setup(t, { expose: n, emit: a }) {
		let s = a, c = Nr(), l = Pr(), { filters: u, page: f, size: h, pages: _, total: b, items: x, facets: S, selected: T, loading: k, error: A, visible: M } = c, { items: P, pending: F, error: I, loading: L } = l, R = e(null), ee = e(null), z = e(!1), B = e(""), V = e(""), H = e(null), U = O(() => un.filter((e) => dn(e, u))), W = O(() => U.value.map((e) => ({
			key: e.key,
			label: `${e.label}：${fn(e, u, S.value)}`,
			removeLabel: `清除${e.label}筛选`
		}))), K = e([]), te = O(() => x.value.filter((e) => T.value.has(e.id))), q = O(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, te.value.filter((t) => re(t, e)).length]))), ne = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, ie = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function ae(e) {
			Object.assign(u, e);
		}
		function oe(e) {
			let t = un.find((t) => t.key === e);
			t && ae(pn(t, u));
		}
		function se(e, t, n) {
			R.value?.open(e, t, n);
		}
		async function ce(e = {}) {
			e.filters && c.applyFilters(e.filters), e.taskId && (await C(), se(e.taskId, e.runId, e.stepId));
		}
		function le(e) {
			e || (H.value = null), c.setVisible(e), l.setVisible(e);
		}
		function ue() {
			R.value?.close();
		}
		function de(e, t = "任务", n = {}) {
			l.track(e, t), n.navigate !== !1 && s("navigate");
		}
		async function J(e = {}) {
			M.value && await c.refresh(e);
		}
		function fe() {
			J(), s("changed");
		}
		async function me(e, t) {
			if (!z.value && !(t === "delete" && pe(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				z.value = !0, V.value = "", K.value = [], B.value = "";
				try {
					let n = await Le.action(e.id, t), r = G(n.data || n);
					B.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", T.value.delete(e.id), await J(), s("changed");
				} catch (e) {
					V.value = `${ne[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					z.value = !1;
				}
			}
		}
		async function he(e) {
			if (z.value) return;
			let t = te.value.filter((t) => re(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${ne[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				z.value = !0, V.value = "", B.value = "", K.value = [];
				try {
					let n = await Le.bulk(e, t.map((e) => e.id)), r = Array.isArray(n.accepted) ? n.accepted : [];
					K.value = (n.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let i = Number(n.accepted_count ?? r.length);
					if (e === "cancel") {
						let e = r.filter((e) => e.state === "cancelled").length, t = r.filter((e) => e.state === "cancelling").length;
						B.value = `已取消 ${e} 个，取消中 ${t} 个${i - e - t > 0 ? `，已受理 ${i - e - t} 个` : ""}`;
						let n = new Set(r.map((e) => String(e.task_id)));
						T.value = new Set([...T.value].filter((e) => !n.has(String(e))));
					} else B.value = `已${ne[e]} ${i} 个`, T.value = /* @__PURE__ */ new Set();
					K.value.length && (B.value += `，跳过 ${K.value.length} 个`), await J(), s("changed");
				} catch (t) {
					V.value = `${ne[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					z.value = !1;
				}
			}
		}
		return n({
			open: ce,
			refresh: J,
			track: de,
			closeDetail: ue,
			setVisible: le
		}), (e, t) => (o(), p(j, null, [r(w("section", Fr, [D(P).length ? (o(), p("section", Ir, [
			w("div", Lr, [w("div", null, [t[10] ||= w("strong", null, "本次提交", -1), w("span", Rr, "共 " + v(D(P).length) + " 项 · 等待/执行 " + v(D(F).length) + " · 成功 " + v(D(P).filter((e) => e.status === "success").length) + " · 失败或待处理 " + v(D(P).length - D(F).length - D(P).filter((e) => e.status === "success").length), 1)]), w("button", {
				type: "button",
				class: "tc-button",
				disabled: D(L) || !D(F).length,
				onClick: t[0] ||= (e) => D(l).refresh()
			}, "刷新回执", 8, zr)]),
			D(I) ? (o(), p("p", Br, v(D(I)), 1)) : y("", !0),
			w("details", null, [t[11] ||= w("summary", null, "查看任务与最终结果", -1), w("ul", Vr, [(o(!0), p(j, null, i(D(P), (e) => (o(), p("li", { key: `${e.task_id}:${e.run_id}` }, [
				w("button", {
					type: "button",
					class: "tc-link",
					onClick: (t) => se(e.task_id, e.run_id)
				}, v(e.label) + " #" + v(e.task_id), 9, Hr),
				N(Mr, { value: e.status }, null, 8, ["value"]),
				w("span", null, v(e.message), 1)
			]))), 128))])])
		])) : y("", !0), w("div", Ur, [
			w("div", { class: g(["tc-toolbar", { "tc-toolbar--filtered": U.value.length }]) }, [
				w("div", Wr, [w("div", Gr, v(te.value.length ? `已选 ${te.value.length} 项` : `${D(b).toLocaleString()} 个任务`), 1), N(ke, {
					items: W.value,
					onRemove: oe
				}, null, 8, ["items"])]),
				te.value.length ? (o(), p("div", Kr, [(o(), p(j, null, i([
					"retry",
					"cancel",
					"terminate",
					"delete"
				], (e) => w("button", {
					key: e,
					type: "button",
					class: g(["tc-button", { "tc-button-danger": e === "delete" || e === "terminate" }]),
					disabled: z.value || !q.value[e],
					onClick: (t) => he(e)
				}, v(ne[e]) + v(q.value[e] ? `（${q.value[e]}）` : ""), 11, qr)), 64))])) : y("", !0),
				w("div", Jr, [
					N(In, {
						"model-value": D(u),
						facets: D(S),
						open: H.value === "mobile",
						"onUpdate:modelValue": ae,
						"onUpdate:open": t[1] ||= (e) => H.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					U.value.length ? (o(), p("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						onClick: t[2] ||= (e) => D(c).applyFilters({})
					}, "清除全部筛选")) : y("", !0),
					w("span", {
						class: "tc-timezone",
						title: D(ie)
					}, "时间按 " + v(D(ie)) + " 显示", 9, Yr),
					w("button", {
						type: "button",
						class: "tc-link",
						onClick: t[3] ||= (e) => ee.value?.resetColumns()
					}, "恢复列宽")
				])
			], 2),
			B.value || V.value || D(A) && D(x).length ? (o(), p("div", {
				key: 0,
				class: g(["tc-feedback", { "tc-feedback-error": V.value || D(A) }]),
				role: V.value || D(A) ? "alert" : "status"
			}, [
				m(v(V.value || D(A) || B.value), 1),
				D(A) ? (o(), p("button", {
					key: 0,
					type: "button",
					class: "tc-link",
					onClick: t[4] ||= (e) => D(c).refresh()
				}, "重试")) : y("", !0),
				K.value.length ? (o(), p("details", Zr, [t[12] ||= w("summary", null, "查看跳过原因", -1), w("ul", null, [(o(!0), p(j, null, i(K.value, (e) => (o(), p("li", { key: e.id }, "#" + v(e.id) + "：" + v(e.message), 1))), 128))])])) : y("", !0)
			], 10, Xr)) : y("", !0),
			N(jr, {
				ref_key: "table",
				ref: ee,
				filters: D(u),
				facets: D(S),
				"open-filter": H.value,
				"onUpdate:openFilter": t[5] ||= (e) => H.value = e,
				"onUpdate:filters": ae,
				items: D(x),
				selected: D(T),
				loading: D(k),
				error: D(A),
				busy: z.value,
				onSelect: D(c).toggle,
				onSelectPage: D(c).togglePage,
				onDetail: se,
				onAction: me,
				onBatch: t[6] ||= (e, t) => s("batch", e, t),
				onRetry: t[7] ||= (e) => D(c).refresh()
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
			N(Me, {
				page: D(f),
				"onUpdate:page": t[8] ||= (e) => d(f) ? f.value = e : null,
				size: D(h),
				"onUpdate:size": t[9] ||= (e) => d(h) ? h.value = e : null,
				pages: D(_),
				total: D(b),
				busy: D(k)
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy"
			])
		])], 512), [[E, D(M)]]), N(ln, {
			ref_key: "detail",
			ref: R,
			onRefresh: fe
		}, null, 512)], 64));
	}
});
// src/main.ts
function $r(e, t = {}) {
	return T(Qr, t).mount(e);
}
export { $r as mountTaskCenter };
