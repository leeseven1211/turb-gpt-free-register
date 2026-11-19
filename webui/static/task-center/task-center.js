import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, V as u, X as d, Z as f, _ as p, a as m, c as h, d as g, dt as _, et as v, f as y, ft as b, g as x, h as S, j as C, k as w, l as T, lt as E, m as D, n as O, nt as k, s as A, st as j, v as M, x as N } from "./_plugin-vue_export-helper-B9RV9BFd.js";
import { n as P, r as F, t as I } from "./client-BBEPwkQG.js";
import { a as L, i as ee, n as te, r as R } from "./taskIds-BlchWwUp.js";
import { n as z } from "./time-DOD6oyhP.js";
import { A as B, C as ne, D as V, E as H, M as U, N as W, O as re, P as G, S as ie, T as ae, _ as oe, a as se, b as ce, c as le, d as ue, f as de, g as K, h as fe, i as q, j as J, k as pe, l as me, m as he, n as ge, o as _e, p as ve, r as ye, s as be, t as xe, u as Se, v as Ce, w as we, x as Te, y as Ee } from "./StepEvidence-BN_jNgz9.js";
import { n as De, r as Oe, t as ke } from "./ListFilterSummary-BG5Tu2p5.js";
import { t as Ae } from "./useColumnWidths-BPlqSIGT.js";
import { t as je } from "./ListResult-bYxNy-51.js";
import { t as Y } from "./errorLabels-B-XqaTSM.js";
import { t as Me } from "./ListPagination-C9YIC0H7.js";
// src/api/tasks.ts
var X = (e, t = {}) => F(e, t, R);
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
function ze(e = Le, t = () => {}) {
	let n = v(!1), r = v(!0), i = v(null), a = v(null), o = k(null), s = k(null), c = k([]), l = k([]), u = v("events"), d = v(null), p = v(""), m = v(""), h = v(""), g = v(""), _ = v(!1), y = v(!1), b = v(!1), x = v(null), S = v(null), C = v("tail"), w = v("tail"), T = v(!1), E = v(!1), O = v(!1), A = v(!1), j = v(!0), M = D(() => o.value?.runs || []), N = D(() => M.value.find((e) => ee(e.id, a.value))), P = 0, F = 0, I = 0, R = 0, z, B = new AbortController(), ne = !1;
	function V() {
		z !== void 0 && clearTimeout(z), z = void 0;
	}
	function H() {
		P += 1, B.abort(), B = new AbortController(), _.value = y.value = b.value = !1, V();
	}
	let U = (e) => e === P && n.value, W = () => n.value && r.value && !!i.value;
	function re() {
		V(), W() && (!o.value || pe(o.value)) && (z = setTimeout(() => void se(), 2e3));
	}
	function G() {
		F += 1, I += 1, y.value = b.value = !1, s.value = null, m.value = h.value = g.value = "", c.value = [], l.value = [], x.value = S.value = null, T.value = E.value = O.value = A.value = !1, C.value = w.value = "tail", j.value = !0;
	}
	async function ie(t = "incremental") {
		if (!W() || !a.value || !i.value || t === "incremental" && y.value || t === "incremental" && C.value === "start" && E.value || t === "next" && !E.value) return;
		let n = P, r = ++F, o = t === "tail" || t === "start" || x.value === null, s = {
			limit: 500,
			...t === "start" ? { after_id: 0 } : t !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		y.value = !0;
		try {
			let l = await e.events(i.value, a.value, s, B.signal);
			if (!U(n) || r !== F) return;
			c.value = o ? l.items : de(c.value, l.items), x.value = l.next_after_id, (t === "tail" || t === "start") && (C.value = t), o && C.value === "tail" ? (T.value = l.has_more, E.value = !1) : (E.value = l.has_more, C.value === "start" && (T.value = !1)), h.value = "";
		} catch (e) {
			U(n) && r === F && (h.value = Re(e));
		} finally {
			U(n) && r === F && (y.value = !1);
		}
	}
	async function ae(t = "incremental") {
		if (!W() || !a.value || !i.value || t === "incremental" && b.value || t === "incremental" && w.value === "start" && A.value || t === "next" && !A.value) return;
		let n = P, r = ++I, o = t === "tail" || t === "start" || S.value === null, s = {
			limit: 500,
			...t === "start" ? { cursor: 0 } : t !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		b.value = !0;
		try {
			let c = await e.logs(i.value, a.value, s, B.signal);
			if (!U(n) || r !== I) return;
			l.value = o ? c.items : [...l.value, ...c.items], S.value = c.next_cursor, (t === "tail" || t === "start") && (w.value = t), A.value = c.has_more, O.value = w.value === "tail" && c.available, j.value = c.available, g.value = "";
		} catch (e) {
			U(n) && r === I && (g.value = Re(e));
		} finally {
			U(n) && r === I && (b.value = !1);
		}
	}
	async function oe(t) {
		if (i.value && a.value) try {
			let n = await e.progress(i.value, a.value, B.signal);
			if (!U(t)) return;
			s.value = n.progress, m.value = "";
		} catch (e) {
			U(t) && (m.value = Re(e));
		}
	}
	async function se() {
		if (!W() || !i.value || _.value) return;
		let n = P, r = ++R;
		_.value = !0, V();
		try {
			let s = await e.detail(i.value, B.signal);
			if (!U(n) || r !== R) return;
			o.value = s.task;
			let c = s.task.runs || [];
			if (a.value && !c.some((e) => ee(e.id, a.value))) {
				G(), p.value = `所选运行 #${a.value} 不存在或已不可用，请选择其他运行。`;
				return;
			}
			let l = a.value || s.task.last_run_id || c.at(-1)?.id || null, d = c.some((e) => ee(e.id, l)) ? l : c.at(-1)?.id || null;
			if (d !== a.value && (G(), a.value = d), p.value = "", a.value && await Promise.allSettled([
				oe(n),
				ie(),
				...u.value === "logs" ? [ae()] : []
			]), !U(n)) return;
			!pe(s.task) && !ne && (ne = !0, t());
		} catch (e) {
			U(n) && (p.value = Re(e));
		} finally {
			U(n) && r === R && (_.value = !1, re());
		}
	}
	function ce(e, t, r) {
		return H(), n.value = !0, i.value = L(e), a.value = te(t), o.value = null, p.value = "", u.value = "events", d.value = r || null, ne = !1, G(), se();
	}
	function le() {
		n.value = !1, H();
	}
	function ue(e) {
		if (e = L(e), !ee(e, a.value)) return H(), a.value = e, d.value = null, G(), se();
	}
	function K(e) {
		if (u.value = e, e === "logs") return ae();
	}
	function fe(e) {
		r.value !== e && (r.value = e, e ? n.value && se() : H());
	}
	return f(le), {
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
		open: ce,
		close: le,
		selectRun: ue,
		selectTab: K,
		setVisible: fe,
		refresh: se,
		loadEvents: ie,
		loadLogs: ae
	};
}
// src/features/tasks/detail/TaskFailure.vue?vue&type=script&setup=true&lang.ts
var Be = {
	key: 0,
	class: "tc-progress-failure tc-task-failure"
}, Ve = { key: 0 }, He = { key: 1 }, Ue = {
	key: 2,
	class: "tc-failure-secondary"
}, We = { key: 3 }, Ge = { key: 0 }, Ke = { key: 1 }, qe = { key: 2 }, Je = /* @__PURE__ */ t({
	__name: "TaskFailure",
	props: {
		failure: {},
		execution: {},
		status: {}
	},
	setup(e) {
		let t = e, r = D(() => !!(t.execution?.error_message || t.execution?.error_info)), i = D(() => (t.failure?.country_failures || []).filter((e) => Te(e.country).trim())), a = D(() => {
			let e = t.failure;
			return e ? i.value.length && !e.error_info?.auto_refresh_at_failed ? `${i.value.length} 个国家查询失败，展开查看具体原因` : me(e) : "";
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
			].includes(n) && n !== e.stage ? B("stage", n) : [e.label || e.step_id || "阶段记录缺失", e.stage].filter(Boolean).join(" · ");
		}), c = D(() => r.value ? H(t.execution?.error_info, t.execution?.error_message) : ""), l = D(() => {
			if (!t.failure || !r.value) return !1;
			let e = (e) => Te(e).replace(/\s+/g, " ").trim(), n = t.failure, i = n.error_info, a = t.execution?.error_info, o = e(n.message), s = e(t.execution?.error_message);
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
		return (t, d) => e.failure || r.value ? (n(), M("details", Be, [
			S("summary", null, [
				e.failure ? (n(), M("strong", Ve, b(j(le)(e.failure) ? "历史失败位置" : "失败位置") + "：" + b(s.value), 1)) : (n(), M("strong", He, "执行失败")),
				S("span", null, b(a.value || c.value), 1),
				e.failure && r.value && !l.value ? (n(), M("span", Ue, "执行错误：" + b(c.value), 1)) : p("", !0),
				e.execution?.error_info?.display_code ? (n(), M("small", We, b(e.execution.error_info.display_code), 1)) : p("", !0)
			]),
			i.value.length ? (n(), M("ul", Ge, [(n(!0), M(g, null, o(i.value, (e, t) => (n(), M("li", { key: t }, b(e.country) + "：" + b(e.summary || "诊断记录不完整"), 1))), 128))])) : p("", !0),
			e.failure?.event_id ? (n(), M("p", Ke, "关联事件 " + b(e.failure.event_id), 1)) : p("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(j(Te)(e.status)) ? (n(), M("p", qe, "原请求证据已保留")) : p("", !0),
			S("pre", null, b(JSON.stringify(u.value, null, 2)), 1)
		])) : p("", !0);
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
}, at = ["onClick"], ot = { id: "tc-step-title" }, st = { class: "tc-step-dialog-body" }, ct = /* @__PURE__ */ t({
	__name: "TaskProgress",
	props: {
		progress: {},
		filter: {},
		active: { type: Boolean },
		context: {},
		execution: {}
	},
	emits: ["filter", "child"],
	setup(t, { emit: r }) {
		let a = t, s = r, c = D(() => se(a.progress?.main_steps)), u = v(null), d = D(() => c.value.find((e) => Ce(e) === u.value)), f = v(), m = null, h = D(() => K(a.progress?.outcome?.child_tasks).flatMap((e) => {
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
		})), _ = D(() => {
			let e = ve(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${z(Te(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			return t ? `当前：${t.label || t.step_id || "执行中"}${t.child_label ? ` · ${t.child_label}` : ""}` : "执行阶段";
		});
		function y(e) {
			return [
				Ee(e),
				q(e),
				...ye(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function w(e) {
			return Ce(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function O(t) {
			m = document.activeElement instanceof HTMLElement ? document.activeElement : null, u.value = Ce(t), await e(), f.value?.open || f.value?.showModal();
		}
		function k() {
			f.value?.close(), u.value = null, m?.isConnected && m.focus({ preventScroll: !0 }), m = null;
		}
		function A(e) {
			let t = f.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i(() => [a.context, a.active], k), C(() => f.value?.close()), (e, r) => t.progress ? (n(), M("section", Ye, [
			S("div", Xe, [S("strong", null, b(_.value), 1), S("small", null, b(t.progress.source === "legacy_derived" ? "历史记录还原" : t.progress.source === "insufficient_evidence" ? "步骤记录缺失" : "按首次记录排列，可含分支与重试"), 1)]),
			c.value.length ? (n(), M("ul", Ze, [(n(!0), M(g, null, o(c.value, (e) => (n(), M("li", {
				key: j(Ce)(e),
				class: E([
					"tc-step",
					`tc-step--${j(ce)(e)}`,
					{ "tc-step--selected": w(e) }
				])
			}, [S("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": w(e),
				title: y(e),
				onClick: (t) => s("filter", w(e) ? null : j(Ce)(e))
			}, [
				r[2] ||= S("span", {
					class: "tc-step-dot",
					"aria-hidden": "true"
				}, null, -1),
				S("strong", null, b(j(Ee)(e)), 1),
				S("span", $e, [
					N(b(j(q)(e)), 1),
					j(oe)(e) == null ? p("", !0) : (n(), M("small", et, " · " + b(j(re)(j(oe)(e))), 1)),
					(n(!0), M(g, null, o(j(ye)(e), (e) => (n(), M("small", { key: e }, " · " + b(e), 1))), 128))
				])
			], 8, Qe), S("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${j(Ee)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => O(e)
			}, [...r[3] ||= [S("svg", {
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
			})], -1)]], 8, tt)], 2))), 128))])) : (n(), M("p", nt, "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。")),
			c.value.length ? (n(), M("details", rt, [
				r[4] ||= S("summary", null, "依赖与执行记录", -1),
				S("p", null, b(t.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1),
				(n(!0), M(g, null, o(c.value, (e) => (n(), M("div", {
					key: j(Ce)(e),
					class: "tc-flow-relation"
				}, [S("strong", null, b(j(Ee)(e)), 1), l(ge, {
					step: e,
					siblings: c.value
				}, null, 8, ["step", "siblings"])]))), 128))
			])) : p("", !0),
			l(Je, {
				failure: t.progress.failure,
				execution: t.execution,
				status: t.progress.outcome.status
			}, null, 8, [
				"failure",
				"execution",
				"status"
			]),
			h.value.length ? (n(), M("div", it, [r[5] ||= S("strong", null, "独立子任务", -1), (n(!0), M(g, null, o(h.value, (e) => (n(), M("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, b(j(B)("task_type", j(Te)(e.task_type))) + " #" + b(e.task_id) + " · " + b(j(fe)(e.status)), 9, at))), 128))])) : p("", !0),
			S("dialog", {
				ref_key: "inspector",
				ref: f,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: T(k, ["prevent"]),
				onClose: r[0] ||= (e) => u.value = null,
				onWheel: T(A, ["stop"]),
				onClick: r[1] ||= (e) => {
					e.target === f.value && k();
				}
			}, [S("header", null, [S("h3", ot, b(d.value ? j(Ee)(d.value) : "步骤详情"), 1), S("button", {
				type: "button",
				autofocus: "",
				onClick: k
			}, "关闭")]), S("div", st, [d.value ? (n(), x(xe, {
				key: 0,
				step: d.value,
				siblings: c.value
			}, null, 8, ["step", "siblings"])) : p("", !0)])], 544)
		])) : p("", !0);
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
}, ln = /* @__PURE__ */ t({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(t, { expose: r, emit: c }) {
		let u = c, d = ze(void 0, () => u("refresh")), { opened: f, taskId: m, runId: h, task: _, runs: w, selectedRun: O, progress: k, events: P, logs: F, tab: I, stepFilter: L, error: te, progressError: R, eventsError: ne, logsError: V, loading: H, eventsLoading: U, logsLoading: W, eventsMode: G, logsMode: ae, eventsEarlier: oe, eventsMore: se, logsEarlier: ce, logsMore: le, logsAvailable: de } = d, K = v(), q = v(), J = v(0), pe = Intl.DateTimeFormat().resolvedOptions().timeZone, me = [
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
		], ge = D(() => k.value?.main_steps || []), ye = D(() => ge.value.find((e) => Ce(e) === L.value || !!(L.value && e.raw_stages?.includes(L.value)))), xe = D(() => he(P.value.filter((e) => Se(e, L.value, ge.value)))), we = D(() => F.value.filter((e) => Se(e, L.value, ge.value, !0))), De = D(() => xe.value.map((e) => {
			let t = be(e), n = ue(e.detail);
			return {
				event: e,
				state: t,
				timestamp: z(e.created_at),
				stageLabel: e.stage_label || B("stage", e.stage),
				association: Pe(e),
				stateLabel: t ? fe(t) : "记录",
				detailJson: n ? JSON.stringify(n, null, 2) : null
			};
		})), Oe = D(() => we.value.map((e) => {
			let t = ue(e.fields);
			return {
				item: e,
				timestamp: e.ts ? z(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), ke = D(() => h.value ? O.value : _.value), Ae = D(() => _.value?.email_snapshot || _.value?.email || (_.value?.account_id ? `账号 #${_.value.account_id}` : _.value?.target_id || "执行记录与诊断")), je = D(() => (_.value?.resources || []).filter((e) => !h.value || ee(e.run_id, h.value))), Y = D(() => O.value?.debug_artifacts), Me = D(() => ve(O.value?.debug_pause || k.value?.debug_pause)), X = null, Ne = !1;
		function Pe(e) {
			let t = ve(e.detail), n = Te(e.main_step_id || t.main_step_id), r = Te(e.raw_stage || t.raw_stage || e.stage), i = ge.value.filter((e) => n ? e.id === n : e.raw_stages?.includes(r));
			return i.length === 1 ? Ee(i[0]) : "未关联步骤";
		}
		function Fe() {
			f.value && (d.close(), X?.isConnected && X.focus({ preventScroll: !0 }), X = null, u("close"));
		}
		function Ie() {
			K.value?.close(), Fe();
		}
		async function Le(t, n, r) {
			f.value || (X = document.activeElement instanceof HTMLElement ? document.activeElement : null), J.value = 0, d.setVisible(!document.hidden);
			let i = d.open(t, n, r);
			return await e(), !K.value?.open && f.value && K.value?.showModal(), i;
		}
		function Re(e) {
			d.setVisible(e);
		}
		function Be() {
			Re(!document.hidden);
		}
		function Ve(e) {
			J.value = 0, d.selectRun(e.target.value);
		}
		async function He(t) {
			J.value = 0, await d.selectTab(t), await e(), q.value && (q.value.scrollTop = 0);
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
		async function We(t) {
			Ne = !0, I.value === "events" ? await d.loadEvents(t) : await d.loadLogs(t), await e(), q.value && t !== "next" && (q.value.scrollTop = t === "tail" ? q.value.scrollHeight : 0), J.value = 0, Ne = !1;
		}
		function Ge() {
			q.value && (q.value.scrollTop = q.value.scrollHeight), J.value = 0;
		}
		function Ke(e) {
			let t = q.value;
			K.value && K.value.scrollHeight > K.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i([P, F], async ([t, n], [r, i]) => {
			if (Ne) return;
			let a = q.value, o = !a || a.scrollTop + a.clientHeight >= a.scrollHeight - 40, s = I.value === "events" ? t.length - r.length : I.value === "logs" ? n.length - i.length : 0;
			s <= 0 || (await e(), o ? Ge() : J.value += s);
		}), i(L, () => {
			J.value = 0, q.value && (q.value.scrollTop = 0);
		}), s(() => {
			Be(), document.addEventListener("visibilitychange", Be);
		}), C(() => {
			document.removeEventListener("visibilitychange", Be), K.value?.close();
		}), r({
			open: Le,
			close: Ie,
			setVisible: Re
		}), (e, t) => (n(), x(y, { to: "body" }, [S("dialog", {
			ref_key: "dialog",
			ref: K,
			class: "tc-detail-dialog",
			"aria-labelledby": "tc-detail-title",
			onCancel: T(Ie, ["prevent"]),
			onClose: Fe,
			onWheel: Ke
		}, [
			S("header", lt, [
				S("h2", ut, [N("任务 #" + b(j(m)) + " ", 1), j(_) ? (n(), M("span", dt, b(j(B)("task_type", j(_).task_type)), 1)) : p("", !0)]),
				S("span", {
					class: "tc-detail-target",
					title: String(Ae.value),
					tabindex: "0"
				}, b(Ae.value), 9, ft),
				ke.value ? (n(), M("div", pt, [S("strong", null, b(j(B)("status", ke.value.status)), 1), S("span", null, "耗时 " + b(j(re)(ke.value.duration_ms)), 1)])) : p("", !0),
				j(_) ? (n(), M("label", mt, [t[10] ||= S("span", null, "运行", -1), S("select", {
					value: j(h) || "",
					"aria-label": "选择执行实例",
					disabled: j(w).length < 2 && (!j(h) || !!j(O)),
					onChange: Ve
				}, [j(h) && !j(O) ? (n(), M("option", {
					key: 0,
					value: j(h),
					disabled: ""
				}, "运行 #" + b(j(h)) + " 不可用", 9, gt)) : j(w).length ? p("", !0) : (n(), M("option", _t, "暂无运行")), (n(!0), M(g, null, o(j(w), (e) => (n(), M("option", {
					key: e.id,
					value: e.id
				}, "第 " + b(e.run_no || "—") + " 次 · " + b(j(B)("status", e.status)), 9, vt))), 128))], 40, ht)])) : p("", !0),
				S("div", yt, [S("button", {
					type: "button",
					disabled: j(H),
					onClick: t[0] ||= (...e) => j(d).refresh && j(d).refresh(...e)
				}, b(j(H) ? "刷新中…" : "刷新"), 9, bt), S("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Ie
				}, "关闭")])
			]),
			j(te) ? (n(), M("div", xt, [
				N("读取任务失败：" + b(j(te)), 1),
				j(_) ? (n(), M("span", St, "。保留上次已读取的记录。")) : p("", !0),
				S("button", {
					type: "button",
					disabled: j(H),
					onClick: t[1] ||= (...e) => j(d).refresh && j(d).refresh(...e)
				}, "重试", 8, Ct)
			])) : p("", !0),
			j(H) && !j(_) ? (n(), M("div", wt, "正在读取任务详情…")) : p("", !0),
			j(_) ? (n(), M(g, { key: 2 }, [
				ke.value?.status === "queued" ? (n(), M("p", Tt, b(j(ie)(ke.value)), 1)) : p("", !0),
				Me.value.state === "paused" ? (n(), M("p", Et, [t[11] ||= N("调试暂停，等待结束调试。", -1), Me.value.hold_until ? (n(), M(g, { key: 0 }, [N("保留至 " + b(j(z)(Me.value.hold_until)) + "。", 1)], 64)) : p("", !0)])) : p("", !0),
				j(k) ? p("", !0) : (n(), x(Je, {
					key: 2,
					execution: ke.value,
					status: ke.value?.status
				}, null, 8, ["execution", "status"])),
				l(ct, {
					progress: j(k),
					execution: ke.value,
					filter: j(L),
					active: j(f),
					context: `${j(m)}:${j(h)}`,
					onFilter: t[2] ||= (e) => L.value = e,
					onChild: Le
				}, null, 8, [
					"progress",
					"execution",
					"filter",
					"active",
					"context"
				]),
				j(R) ? (n(), M("p", Dt, [N("进度读取失败：" + b(j(R)), 1), j(k) ? (n(), M(g, { key: 0 }, [N("；保留上次快照")], 64)) : p("", !0)])) : p("", !0),
				S("div", Ot, [
					S("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: Ue
					}, [(n(), M(g, null, o(me, (e) => S("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": j(I) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: j(I) === e.id ? 0 : -1,
						onClick: (t) => He(e.id)
					}, b(e.label), 9, kt)), 64))], 32),
					S("div", At, [S("span", null, [t[12] ||= N("当前查看：", -1), S("strong", null, b(ye.value ? j(Ee)(ye.value) : j(L) || "全流程"), 1)]), j(L) ? (n(), M("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => L.value = null
					}, "清除步骤筛选")) : p("", !0)]),
					j(I) === "artifacts" ? p("", !0) : (n(), M("div", jt, [S("button", {
						type: "button",
						"aria-pressed": (j(I) === "events" ? j(G) : j(ae)) === "start",
						disabled: j(U) || j(W) || !j(h),
						onClick: t[4] ||= (e) => We("start")
					}, "从头加载", 8, Mt), S("button", {
						type: "button",
						"aria-pressed": (j(I) === "events" ? j(G) : j(ae)) === "tail",
						disabled: j(U) || j(W) || !j(h),
						onClick: t[5] ||= (e) => We("tail")
					}, "最近记录", 8, Nt)]))
				]),
				S("div", {
					ref_key: "scroller",
					ref: q,
					class: "tc-detail-content"
				}, [
					a(S("section", Pt, [
						j(ne) ? (n(), M("p", Ft, [N("事件读取失败：" + b(j(ne)), 1), S("button", {
							type: "button",
							disabled: j(U),
							onClick: t[6] ||= (e) => j(d).loadEvents()
						}, "重试", 8, It)])) : p("", !0),
						j(oe) ? (n(), M("p", Lt, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : p("", !0),
						xe.value.length ? p("", !0) : (n(), M("div", Rt, b(j(U) ? "正在读取事件…" : j(L) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(n(!0), M(g, null, o(De.value, (e) => (n(), M("article", {
							key: e.event.id,
							class: E(["tc-event", { "tc-event--error": e.state === "failed" }])
						}, [
							S("div", zt, [
								S("time", null, b(e.timestamp), 1),
								S("span", null, b(e.event.level || "INFO"), 1),
								S("strong", null, b(e.stageLabel), 1),
								e.association ? (n(), M("span", Bt, b(e.association), 1)) : p("", !0),
								S("span", null, b(e.stateLabel), 1),
								S("small", null, "事件 " + b(e.event.event_id || e.event.id), 1)
							]),
							S("p", null, b(e.event.message || "—"), 1),
							e.detailJson ? (n(), M("details", Vt, [t[13] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 2))), 128)),
						j(se) ? (n(), M("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: j(U),
							onClick: t[7] ||= (e) => We("next")
						}, b(j(U) ? "正在读取…" : "继续加载后续事件"), 9, Ht)) : p("", !0)
					], 512), [[A, j(I) === "events"]]),
					a(S("section", Ut, [
						j(V) ? (n(), M("p", Wt, [N("日志读取失败：" + b(j(V)), 1), S("button", {
							type: "button",
							disabled: j(W),
							onClick: t[8] ||= (e) => j(d).loadLogs()
						}, "重试", 8, Gt)])) : p("", !0),
						j(ce) ? (n(), M("p", Kt, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : p("", !0),
						we.value.length ? p("", !0) : (n(), M("div", qt, b(j(W) ? "正在读取运行日志…" : j(de) ? j(L) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(n(!0), M(g, null, o(Oe.value, (e, r) => (n(), M("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${r}`,
							class: "tc-log-line"
						}, [
							S("div", Jt, [
								S("time", null, b(e.timestamp), 1),
								S("strong", null, b(e.item.level || "INFO"), 1),
								S("span", null, b(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							S("p", null, b(e.item.message), 1),
							e.detailJson ? (n(), M("details", Yt, [t[14] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						]))), 128)),
						j(le) ? (n(), M("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: j(W),
							onClick: t[9] ||= (e) => We("next")
						}, b(j(W) ? "正在读取…" : "继续加载后续日志"), 9, Xt)) : p("", !0)
					], 512), [[A, j(I) === "logs"]]),
					a(S("section", Zt, [
						Y.value?.available ? (n(), M("article", Qt, [
							t[15] ||= S("h3", null, "Roxy 刷新调试", -1),
							S("p", null, b(Y.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + b(j(ve)(Y.value.summary).request_count || 0) + " 条", 1),
							j(O)?.result_summary?.debug_browser_kept === !0 ? (n(), M("p", $t, "失败窗口已保留，可在 Roxy 中查看。")) : p("", !0),
							S("div", en, [
								j(_e)(Y.value.har_url) ? (n(), M("a", {
									key: 0,
									href: j(_e)(Y.value.har_url),
									download: ""
								}, "下载 HAR", 8, tn)) : p("", !0),
								j(_e)(Y.value.page_state_url) ? (n(), M("a", {
									key: 1,
									href: j(_e)(Y.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, nn)) : p("", !0),
								j(_e)(Y.value.screenshot_url) ? (n(), M("a", {
									key: 2,
									href: j(_e)(Y.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, rn)) : p("", !0)
							])
						])) : p("", !0),
						(n(!0), M(g, null, o(je.value, (e, t) => (n(), M("article", {
							key: j(Te)(e.id) || t,
							class: "tc-artifact"
						}, [
							S("h3", null, b(e.resource_type || "运行资源"), 1),
							S("p", null, b(e.provider || e.state || "—"), 1),
							S("small", null, b(j(z)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!Y.value?.available && !je.value.length ? (n(), M("div", an, "当前 Run 没有诊断资源或产物")) : p("", !0),
						ke.value?.result_summary ? (n(), M("details", on, [t[16] ||= S("summary", null, "执行结果字段", -1), S("pre", null, b(JSON.stringify(ke.value.result_summary, null, 2)), 1)])) : p("", !0)
					], 512), [[A, j(I) === "artifacts"]])
				], 512),
				S("footer", sn, [S("small", null, "时间按浏览器时区显示 · " + b(j(pe)), 1), J.value && j(I) !== "artifacts" ? (n(), M("button", {
					key: 0,
					type: "button",
					onClick: Ge
				}, "有 " + b(J.value) + " 条新记录，回到底部", 1)) : j(H) || j(U) || j(W) ? (n(), M("small", cn, "正在同步记录…")) : p("", !0)])
			], 64)) : p("", !0)
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
		return a.find((e) => e.value === t)?.label || B(i, t);
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
}, wn = { class: "tc-filter-field" }, Tn = ["for"], En = ["id", "value"], Dn = { class: "tc-filter-field" }, On = ["for"], kn = ["id", "value"], An = { class: "tc-filter-footer" }, jn = ["disabled"], Mn = /* @__PURE__ */ t({
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
				...Object.keys(J[e] || {}),
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
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? fn(r.column, {
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
		function h(e, t) {
			m(s.value, e), t.detail > 0 && i("done");
		}
		function _() {
			i("update:modelValue", pn(r.column, r.modelValue)), i("done");
		}
		return (t, r) => (n(), M("form", {
			class: "tc-filter-fields",
			onSubmit: r[5] ||= T((e) => i("done"), ["prevent"])
		}, [e.column.kind === "search" ? (n(), M("div", mn, [S("label", { for: `${j(a)}-search` }, b(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, hn), S("input", {
			id: `${j(a)}-search`,
			value: c.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: r[0] ||= (e) => m(s.value, e.target.value)
		}, null, 40, gn)])) : e.column.kind === "select" ? (n(), M("div", {
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
		}, null, 40, vn), S("span", yn, b(l[e.column.group || ""] || "全部"), 1)], 2), (n(!0), M(g, null, o(f.value, (e) => (n(), M("label", {
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
			}, null, 40, bn),
			S("span", xn, b(e.text), 1),
			e.count == null ? p("", !0) : (n(), M("span", Sn, b(e.count), 1))
		], 2))), 128))], 8, _n)) : (n(), M("div", Cn, [
			r[6] ||= S("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			S("div", wn, [S("label", { for: `${j(a)}-from` }, "创建日期起", 8, Tn), S("input", {
				id: `${j(a)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: r[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, En)]),
			S("div", Dn, [S("label", { for: `${j(a)}-to` }, "创建日期止", 8, On), S("input", {
				id: `${j(a)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: r[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, kn)])
		])), S("div", An, [S("button", {
			type: "button",
			class: "tc-link",
			disabled: !j(dn)(e.column, e.modelValue),
			onClick: _
		}, "清除此列", 8, jn), r[7] ||= S("button", {
			type: "submit",
			class: "tc-button"
		}, "完成", -1)])], 32));
	}
}), Nn = { class: "tc-mobile-filters" }, Pn = { class: "tc-filter-column-picker" }, Fn = ["value"], In = /* @__PURE__ */ t({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = v(un[0].key), u = D(() => un.find((e) => e.key === c.value)), d = D(() => un.filter((e) => dn(e, i.modelValue)).length);
		return (t, i) => (n(), M("div", Nn, [l(Oe, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: e.open,
			"onUpdate:open": i[3] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [S("label", Pn, [i[4] ||= N("筛选列", -1), a(S("select", { "onUpdate:modelValue": i[0] ||= (e) => c.value = e }, [(n(!0), M(g, null, o(j(un), (t) => (n(), M("option", {
				key: t.key,
				value: t.key
			}, b(t.label) + b(j(dn)(t, e.modelValue) ? " · 已筛选" : ""), 9, Fn))), 128))], 512), [[m, c.value]])]), (n(), x(Mn, {
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
}), Ln = /* @__PURE__ */ t({
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
			active: j(dn)(e.column, e.modelValue),
			summary: j(fn)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": a[2] ||= (e) => i("update:open", e)
		}, {
			default: r(() => [l(Mn, {
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
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${B(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function Un(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function Wn(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: B("status", t),
		tone: G(t),
		title: Hn("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = ie(e) || void 0) : zn.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = ie(e) || Un(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : Rn.has(t) ? (r.label = "失败", r.tone = "danger") : Bn.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (Rn.has(n) && Rn.has(t) || n === "completed" && t === "success" || n === "in_progress" && zn.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: Vn[n] || B("target_status", n),
			tone: G(n),
			title: Hn("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Z = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), Gn = (e) => Array.isArray(e) ? e.map(U) : [], Q = (e) => String(e || "").toLowerCase(), $ = /* @__PURE__ */ new Set([
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
	].includes(r) ? Z("提链成功", "warning", "后续已中断") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Z("提链成功", "danger", "后续失败") : Z("提链成功", "success") : Kn.has(i) || qn(e) ? Z(t, "danger") : $.has(i) ? Z("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Z("等待提链", "warning") : i === "running" ? Z("提链中", "active") : r === "cancelled" ? Z("已取消") : ["stopped", "interrupted"].includes(r) ? Z("执行已中断", "warning") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Z(t, "danger") : n.ok === !0 ? Z("提链流程完成", "success") : Z("提链结果缺失", "warning");
}
function Zn(e, t) {
	let n = U(e.result_summary), r = Q(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : Gn(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes(Q(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = U(e.result);
		return !t && !e.last_success_at ? [] : Gn(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : Gn(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(U(e.result)).length > 0);
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
	let n = U(e.result_summary), r = Q(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
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
	if (i === "plan_check") return Zn(e, a);
	if (r === "cancelled") return Z("已取消");
	if (["stopped", "interrupted"].includes(r)) return Z("执行已中断", "warning");
	if (qn(e)) return Z(a, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes(Q(e.target_status)) || r === "deactivated") return Z("账号已停用", "danger");
	if (e.error_message || e.error_info || Kn.has(r) || i !== "sub2api_scan" && n.ok === !1) return Z(a, "danger");
	if (r === "partial_success") return Z("部分完成", "warning");
	if (i === "sub2api_scan") return r === "success" ? Z(Yn[i], "success") : Z("扫描未完成", "warning");
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
var $n = /* @__PURE__ */ t({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, i = D(() => Qn(t.task, Y(t.task.error_info))), a = D(() => [...new Set([
			W(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? H(t.task.error_info, t.task.error_message) : "",
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
}, jr = /* @__PURE__ */ t({
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
			...Wn(e)
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
			return V(e) || e.current_stage_label || B("stage", e.current_stage);
		}
		function O(e) {
			return [
				e.current_stage_label || B("stage", e.current_stage),
				V(e),
				re(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function k(e) {
			return String(e.bulk_batch_id || U(e.bulk_context).batch_id || "");
		}
		function A(e) {
			return String(e.bulk_round_id || U(e.bulk_context).round_id || "");
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
			}, null, 40, tr)) : (n(), M(g, { key: 1 }, [j(un)[r - 1] ? (n(), x(Ln, {
				key: 0,
				column: j(un)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === j(un)[r - 1].key,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:filters", e),
				"onUpdate:open": (e) => s("update:openFilter", e ? j(un)[r - 1].key : null)
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
			}, null, 40, nr)) : p("", !0)], 64))])), 64))])]),
			S("tbody", null, [(n(!0), M(g, null, o(d.value, ({ task: t, execution: i, target: a }) => (n(), M("tr", {
				key: t.id,
				class: E({ "tc-row-selected": e.selected.has(t.id) })
			}, [
				S("td", rr, [S("input", {
					type: "checkbox",
					checked: e.selected.has(t.id),
					"aria-label": `选择任务 #${t.id}`,
					onChange: (e) => s("select", t.id, e.target.checked)
				}, null, 40, ir)]),
				S("td", ar, [S("button", {
					type: "button",
					class: "tc-link tc-task-id",
					onClick: (e) => s("detail", t.id)
				}, "#" + b(t.id), 9, or)]),
				S("td", sr, [l(De, { text: j(B)("task_type", t.task_type) }, null, 8, ["text"])]),
				S("td", cr, [l(De, {
					text: t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—",
					secondary: t.email_snapshot || t.email || "—"
				}, {
					default: r(() => [S("strong", null, b(t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—"), 1)]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				S("td", lr, [S("span", {
					class: E(["tc-badge", `tc-badge--${i.tone}`]),
					title: i.title
				}, b(i.label), 11, ur), i.secondary ? (n(), M("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: i.secondary
				}, b(i.secondary), 9, dr)) : p("", !0)]),
				S("td", fr, [a ? (n(), M("span", {
					key: 0,
					class: E(["tc-badge", `tc-badge--${a.tone}`]),
					title: a.title
				}, b(a.label), 11, pr)) : (n(), M("span", mr, "—"))]),
				S("td", hr, [l(De, {
					text: t.batch_title || t.batch_uuid || (k(t) ? "查看批次" : "单任务"),
					secondary: j(B)("trigger", t.trigger)
				}, {
					default: r(() => [k(t) ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						onClick: (e) => s("batch", k(t), A(t))
					}, b(t.batch_title || t.batch_uuid || "查看批次"), 9, gr)) : (n(), M(g, { key: 1 }, [N(b(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				S("td", _r, [l(De, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				S("td", vr, [l(De, {
					text: w(t),
					secondary: j(re)(t.duration_ms),
					title: O(t),
					tone: j(V)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				S("td", yr, [l(De, {
					text: j(z)(t.created_at),
					secondary: j(z)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				S("td", br, [l($n, { task: t }, null, 8, ["task"])]),
				S("td", xr, [S("div", Sr, [
					S("button", {
						type: "button",
						class: "tc-link",
						onClick: (e) => s("detail", t.id)
					}, "详情", 8, Cr),
					j(ne)(t) ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						disabled: e.busy,
						onClick: (e) => s("action", t, "retry")
					}, "重跑", 8, wr)) : p("", !0),
					j(we)(t) ? (n(), M("button", {
						key: 1,
						type: "button",
						class: "tc-link tc-text-danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "terminate")
					}, b(t.status === "queued" ? "取消" : "终止"), 9, Tr)) : p("", !0),
					j(pe)(t) ? p("", !0) : (n(), M("button", {
						key: 2,
						type: "button",
						class: "tc-link tc-text-danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "delete")
					}, "删除", 8, Er))
				])])
			], 2))), 128)), e.items.length ? p("", !0) : (n(), M("tr", Dr, [S("td", { colspan: f.length }, [S("div", {
				class: "tc-empty",
				role: e.error ? "alert" : "status"
			}, [
				e.loading ? (n(), M("span", Ar)) : p("", !0),
				S("strong", null, b(e.loading ? "正在加载任务记录" : e.error ? "任务列表加载失败" : "没有匹配的任务"), 1),
				S("p", null, b(e.error || (e.loading ? "正在同步任务状态" : "可调整筛选条件，或清除全部筛选。")), 1),
				e.error ? (n(), M("button", {
					key: 1,
					type: "button",
					class: "tc-button",
					onClick: i[2] ||= (e) => s("retry")
				}, "重新加载")) : p("", !0)
			], 8, kr)], 8, Or)]))])
		], 4)], 8, er));
	}
}), Mr = /* @__PURE__ */ t({
	__name: "StatusBadge",
	props: {
		value: {},
		group: { default: "status" }
	},
	setup(e) {
		return (t, r) => (n(), M("span", { class: E(["tc-badge", `tc-badge--${j(G)(e.value)}`]) }, b(j(B)(e.group, e.value)), 3));
	}
});
// src/features/tasks/useTaskList.ts
function Nr() {
	let t = c(Ne()), n = v(1), r = v(20), a = v(0), o = v([]), s = v({}), l = v(/* @__PURE__ */ new Set()), u = v(!1), d = v(""), p = v(!1), m = D(() => Math.max(1, Math.ceil(a.value / r.value))), h = 0, g = null, _, y, b = 0, x = 0, S = "", C = "", w = /* @__PURE__ */ new Set([
		"task_id",
		"target",
		"batch",
		"result"
	]), T = null;
	function E(t = {}, n = 0) {
		clearTimeout(y);
		let r = ++b, i = () => {
			r === b && p.value && !document.hidden && k(t);
		};
		n ? y = setTimeout(i, n) : e(i);
	}
	let O = () => {
		clearTimeout(_), p.value && !document.hidden && (_ = setTimeout(() => void k(), 5e3));
	};
	async function k(e = {}) {
		clearTimeout(_), clearTimeout(y), ++b;
		let i = {
			...t,
			page: n.value,
			page_size: r.value
		}, c = JSON.stringify(i), f = e.metadata || S !== c || Date.now() - x >= 3e4, p = ++h;
		g?.abort(), g = new AbortController(), u.value = !0;
		try {
			let e = await Le.list({
				...i,
				include_facets: +!!f,
				include_batches: 0
			}, g.signal);
			if (p !== h) return;
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
			e.facets && (s.value = e.facets), f && (x = Date.now(), S = c), d.value = "";
		} catch (e) {
			p === h && !P(e) && (d.value = e instanceof Error ? e.message : "任务列表加载失败");
		} finally {
			p === h && (u.value = !1, g = null, O());
		}
	}
	function A(e) {
		e !== p.value && (p.value = e, clearTimeout(_), clearTimeout(y), e && !document.hidden ? E() : (++b, g?.abort(), ++h, u.value = !1));
	}
	function j(e, r = !0) {
		Object.assign(t, r ? {
			...Ne(),
			...e
		} : e), n.value = 1, l.value = /* @__PURE__ */ new Set();
	}
	function M(e, t) {
		let n = new Set(l.value);
		t ? n.add(e) : n.delete(e), l.value = n;
	}
	function N(e) {
		l.value = new Set(e ? o.value.map((e) => e.id) : []);
	}
	i(() => ({
		...t,
		page: n.value,
		page_size: r.value
	}), (e, r) => {
		l.value = /* @__PURE__ */ new Set(), clearTimeout(_);
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
		clearTimeout(_), document.hidden ? (++b, clearTimeout(y), g?.abort(), ++h, u.value = !1) : p.value && E();
	};
	return document.addEventListener("visibilitychange", F), f(() => {
		++h, ++b, g?.abort(), clearTimeout(_), clearTimeout(y), document.removeEventListener("visibilitychange", F);
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
		refresh: k,
		setVisible: A,
		applyFilters: j,
		toggle: M,
		togglePage: N
	};
}
// src/features/tasks/useReceipts.ts
function Pr() {
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
		let d = await Promise.allSettled(i.map((e) => Le.detail(e.task_id, l.signal)));
		o === c && (d.forEach((e, t) => {
			let n = i[t];
			if (e.status === "rejected") {
				P(e.reason) || (r.value = "部分回执暂未读到，请稍后刷新。");
				return;
			}
			let a = e.value.task, o = a.runs?.find((e) => ee(e.id, n.run_id));
			if (n.run_id && !o) {
				r.value = "部分执行记录暂未读到，请稍后刷新。";
				return;
			}
			let s = o || a, c = U(s.result_summary);
			n.status = s.status || "queued", n.message = s.error_message || String(c.message || (s.status === "success" ? "已确认完成" : ""));
		}), n.value = !1, l = null, u());
	}
	function p(t, n) {
		for (let i of t) if (i.accepted) try {
			let t = L(i.task_id), r = te(i.run_id);
			if (e.value.some((e) => ee(e.task_id, t) && (r === null ? e.run_id === null : ee(e.run_id, r)))) continue;
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
}, qr = ["disabled", "onClick"], Jr = { class: "tc-toolbar-end" }, Yr = ["title"], Xr = ["role"], Zr = { key: 1 }, Qr = /* @__PURE__ */ t({
	__name: "TaskCenter",
	emits: [
		"navigate",
		"batch",
		"changed"
	],
	setup(t, { expose: r, emit: i }) {
		let s = i, c = Nr(), u = Pr(), { filters: f, page: m, size: h, pages: _, total: y, items: x, facets: C, selected: w, loading: T, error: O, visible: k } = c, { items: P, pending: F, error: I, loading: L } = u, ee = v(null), te = v(null), R = v(!1), z = v(""), B = v(""), ne = v(null), V = D(() => un.filter((e) => dn(e, f))), H = D(() => V.value.map((e) => ({
			key: e.key,
			label: `${e.label}：${fn(e, f, C.value)}`,
			removeLabel: `清除${e.label}筛选`
		}))), W = v([]), re = D(() => x.value.filter((e) => w.value.has(e.id))), G = D(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, re.value.filter((t) => ae(t, e)).length]))), ie = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, oe = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function se(e) {
			Object.assign(f, e);
		}
		function ce(e) {
			let t = un.find((t) => t.key === e);
			t && se(pn(t, f));
		}
		function le(e, t, n) {
			ee.value?.open(e, t, n);
		}
		async function ue(t = {}) {
			t.filters && c.applyFilters(t.filters), t.taskId && (await e(), le(t.taskId, t.runId, t.stepId));
		}
		function de(e) {
			e || (ne.value = null), c.setVisible(e), u.setVisible(e);
		}
		function K() {
			ee.value?.close();
		}
		function fe(e, t = "任务", n = {}) {
			u.track(e, t), n.navigate !== !1 && s("navigate");
		}
		async function q(e = {}) {
			k.value && await c.refresh(e);
		}
		function J() {
			q(), s("changed");
		}
		async function me(e, t) {
			if (!R.value && !(t === "delete" && pe(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				R.value = !0, B.value = "", W.value = [], z.value = "";
				try {
					let n = await Le.action(e.id, t), r = U(n.data || n);
					z.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", w.value.delete(e.id), await q(), s("changed");
				} catch (e) {
					B.value = `${ie[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					R.value = !1;
				}
			}
		}
		async function he(e) {
			if (R.value) return;
			let t = re.value.filter((t) => ae(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${ie[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				R.value = !0, B.value = "", z.value = "", W.value = [];
				try {
					let n = await Le.bulk(e, t.map((e) => e.id)), r = Array.isArray(n.accepted) ? n.accepted : [];
					W.value = (n.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let i = Number(n.accepted_count ?? r.length);
					if (e === "cancel") {
						let e = r.filter((e) => e.state === "cancelled").length, t = r.filter((e) => e.state === "cancelling").length;
						z.value = `已取消 ${e} 个，取消中 ${t} 个${i - e - t > 0 ? `，已受理 ${i - e - t} 个` : ""}`;
						let n = new Set(r.map((e) => String(e.task_id)));
						w.value = new Set([...w.value].filter((e) => !n.has(String(e))));
					} else z.value = `已${ie[e]} ${i} 个`, w.value = /* @__PURE__ */ new Set();
					W.value.length && (z.value += `，跳过 ${W.value.length} 个`), await q(), s("changed");
				} catch (t) {
					B.value = `${ie[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					R.value = !1;
				}
			}
		}
		return r({
			open: ue,
			refresh: q,
			track: fe,
			closeDetail: K,
			setVisible: de
		}), (e, t) => (n(), M(g, null, [a(S("section", Fr, [j(P).length ? (n(), M("section", Ir, [
			S("div", Lr, [S("div", null, [t[10] ||= S("strong", null, "本次提交", -1), S("span", Rr, "共 " + b(j(P).length) + " 项 · 等待/执行 " + b(j(F).length) + " · 成功 " + b(j(P).filter((e) => e.status === "success").length) + " · 失败或待处理 " + b(j(P).length - j(F).length - j(P).filter((e) => e.status === "success").length), 1)]), S("button", {
				type: "button",
				class: "tc-button",
				disabled: j(L) || !j(F).length,
				onClick: t[0] ||= (e) => j(u).refresh()
			}, "刷新回执", 8, zr)]),
			j(I) ? (n(), M("p", Br, b(j(I)), 1)) : p("", !0),
			S("details", null, [t[11] ||= S("summary", null, "查看任务与最终结果", -1), S("ul", Vr, [(n(!0), M(g, null, o(j(P), (e) => (n(), M("li", { key: `${e.task_id}:${e.run_id}` }, [
				S("button", {
					type: "button",
					class: "tc-link",
					onClick: (t) => le(e.task_id, e.run_id)
				}, b(e.label) + " #" + b(e.task_id), 9, Hr),
				l(Mr, { value: e.status }, null, 8, ["value"]),
				S("span", null, b(e.message), 1)
			]))), 128))])])
		])) : p("", !0), S("div", Ur, [
			S("div", { class: E(["tc-toolbar", { "tc-toolbar--filtered": V.value.length }]) }, [
				S("div", Wr, [S("div", Gr, b(re.value.length ? `已选 ${re.value.length} 项` : `${j(y).toLocaleString()} 个任务`), 1), l(ke, {
					items: H.value,
					onRemove: ce
				}, null, 8, ["items"])]),
				re.value.length ? (n(), M("div", Kr, [(n(), M(g, null, o([
					"retry",
					"cancel",
					"terminate",
					"delete"
				], (e) => S("button", {
					key: e,
					type: "button",
					class: E(["tc-button", { "tc-button-danger": e === "delete" || e === "terminate" }]),
					disabled: R.value || !G.value[e],
					onClick: (t) => he(e)
				}, b(ie[e]) + b(G.value[e] ? `（${G.value[e]}）` : ""), 11, qr)), 64))])) : p("", !0),
				S("div", Jr, [
					l(In, {
						"model-value": j(f),
						facets: j(C),
						open: ne.value === "mobile",
						"onUpdate:modelValue": se,
						"onUpdate:open": t[1] ||= (e) => ne.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					V.value.length ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "tc-link",
						onClick: t[2] ||= (e) => j(c).applyFilters({})
					}, "清除全部筛选")) : p("", !0),
					S("span", {
						class: "tc-timezone",
						title: j(oe)
					}, "时间按 " + b(j(oe)) + " 显示", 9, Yr),
					S("button", {
						type: "button",
						class: "tc-link",
						onClick: t[3] ||= (e) => te.value?.resetColumns()
					}, "恢复列宽")
				])
			], 2),
			z.value || B.value || j(O) && j(x).length ? (n(), M("div", {
				key: 0,
				class: E(["tc-feedback", { "tc-feedback-error": B.value || j(O) }]),
				role: B.value || j(O) ? "alert" : "status"
			}, [
				N(b(B.value || j(O) || z.value), 1),
				j(O) ? (n(), M("button", {
					key: 0,
					type: "button",
					class: "tc-link",
					onClick: t[4] ||= (e) => j(c).refresh()
				}, "重试")) : p("", !0),
				W.value.length ? (n(), M("details", Zr, [t[12] ||= S("summary", null, "查看跳过原因", -1), S("ul", null, [(n(!0), M(g, null, o(W.value, (e) => (n(), M("li", { key: e.id }, "#" + b(e.id) + "：" + b(e.message), 1))), 128))])])) : p("", !0)
			], 10, Xr)) : p("", !0),
			l(jr, {
				ref_key: "table",
				ref: te,
				filters: j(f),
				facets: j(C),
				"open-filter": ne.value,
				"onUpdate:openFilter": t[5] ||= (e) => ne.value = e,
				"onUpdate:filters": se,
				items: j(x),
				selected: j(w),
				loading: j(T),
				error: j(O),
				busy: R.value,
				onSelect: j(c).toggle,
				onSelectPage: j(c).togglePage,
				onDetail: le,
				onAction: me,
				onBatch: t[6] ||= (e, t) => s("batch", e, t),
				onRetry: t[7] ||= (e) => j(c).refresh()
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
				page: j(m),
				"onUpdate:page": t[8] ||= (e) => d(m) ? m.value = e : null,
				size: j(h),
				"onUpdate:size": t[9] ||= (e) => d(h) ? h.value = e : null,
				pages: j(_),
				total: j(y),
				busy: j(T)
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy"
			])
		])], 512), [[A, j(k)]]), l(ln, {
			ref_key: "detail",
			ref: ee,
			onRefresh: J
		}, null, 512)], 64));
	}
});
// src/main.ts
function $r(e, t = {}) {
	return O(Qr, t).mount(e);
}
export { $r as mountTaskCenter };
