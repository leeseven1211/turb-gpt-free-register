import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, V as u, X as d, Z as f, _ as p, a as m, d as h, dt as g, et as _, f as v, ft as y, g as b, h as x, j as S, k as C, l as w, lt as T, m as E, n as D, nt as O, s as ee, st as k, v as A, x as j } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { n as te, r as M, t as N } from "./client-B5R_MNgP.js";
import { a as P, i as F, n as I, r as L } from "./taskIds-BlchWwUp.js";
import { A as R, C as z, D as B, E as V, M as H, N as U, O as W, P as G, S as ne, T as re, _ as K, a as ie, b as ae, c as oe, d as se, f as ce, g as le, h as ue, i as q, j as J, k as Y, l as de, m as fe, n as X, o as pe, p as me, r as he, s as ge, t as _e, u as ve, v as ye, w as be, x as xe, y as Se } from "./StepEvidence-No0pxD3W.js";
import { n as Ce } from "./time-DOD6oyhP.js";
import { i as we, n as Te, r as Ee, t as De } from "./ListFilterSummary-C8h8bMwn.js";
import { n as Oe, t as ke } from "./ColumnResizer-CPJ9UuoZ.js";
import { t as Ae } from "./ListResult-CPVXnLlZ.js";
import { t as je } from "./errorLabels-Byl2EONI.js";
import { t as Me } from "./ListPagination-DURVj-Kj.js";
import { t as Ne } from "./ListToolbar-DwVj9ZQa.js";
// src/api/tasks.ts
var Pe = (e, t = {}) => M(e, t, L);
function Fe() {
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
function Ie(e) {
	return new URLSearchParams(Object.entries(e).filter(([, e]) => e !== void 0 && e !== "").map(([e, t]) => [e, String(t)])).toString();
}
function Le(e) {
	let t = new URLSearchParams();
	for (let n of e) {
		let e = P(n.task_id), r = I(n.run_id);
		t.append("ref", r === null ? String(e) : `${e}:${r}`);
	}
	return t.toString();
}
async function Re(e, t, n) {
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
		let e = await Pe(t, {
			method: "POST",
			headers: {
				"Idempotency-Key": i,
				...n ? { "Content-Type": "application/json" } : {}
			},
			...n ? { body: ze(t, n) } : {}
		});
		return s(), e;
	} catch (e) {
		throw e instanceof N && [
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
function ze(e, t) {
	if (e !== "/api/operations/bulk") return JSON.stringify(t);
	let { task_ids: n, ...r } = t;
	if (!Array.isArray(n)) return JSON.stringify(t);
	let i = JSON.stringify(r).slice(0, -1);
	return `${i}${i.length > 1 ? "," : ""}"task_ids":[${n.map((e) => String(P(e))).join(",")}]}`;
}
var Be = {
	list: (e, t) => Pe(`/api/operations?${Ie(e)}`, { signal: t }),
	detail: (e, t) => Pe(`/api/operations/${P(e)}?include_events=0`, { signal: t }),
	receipts: (e, t) => Pe(`/api/operations/receipts?${Le(e)}`, { signal: t }),
	progress: (e, t, n) => Pe(`/api/operations/${P(e)}/runs/${P(t)}/progress`, { signal: n }),
	events: (e, t, n = {}, r) => Pe(`/api/operations/${P(e)}/runs/${P(t)}/events?${Ie({
		limit: 500,
		...n
	})}`, { signal: r }),
	logs: (e, t, n = {}, r) => Pe(`/api/operations/${P(e)}/runs/${P(t)}/logs?${Ie({
		limit: 500,
		...n
	})}`, { signal: r }),
	action: (e, t) => t === "retry" ? Re(`retry:${P(e)}`, `/api/operations/${P(e)}/retry`) : Pe(`/api/operations/${P(e)}/${t}`, { method: "POST" }),
	bulk: (e, t) => e === "retry" ? Re("bulk:retry", "/api/operations/bulk", {
		action: e,
		task_ids: t
	}) : Pe("/api/operations/bulk", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: ze("/api/operations/bulk", {
			action: e,
			task_ids: t
		})
	})
}, Ve = (e) => e instanceof Error ? e.message : "读取失败，请重试";
function He(e = Be, t = () => {}) {
	let n = _(!1), r = _(!0), i = _(null), a = _(null), o = O(null), s = O(null), c = O([]), l = O([]), u = _("events"), d = _(null), p = _(""), m = _(""), h = _(""), g = _(""), v = _(!1), y = _(!1), b = _(!1), x = _(null), S = _(null), C = _("tail"), w = _("tail"), T = _(!1), D = _(!1), ee = _(!1), k = _(!1), A = _(!0), j = E(() => o.value?.runs || []), te = E(() => j.value.find((e) => F(e.id, a.value))), M = 0, N = 0, L = 0, R = 0, z = null, B, V = new AbortController(), H = !1;
	function U() {
		B !== void 0 && clearTimeout(B), B = void 0;
	}
	function W() {
		M += 1, V.abort(), V = new AbortController(), z = null, v.value = y.value = b.value = !1, U();
	}
	let G = (e) => e === M && n.value, ne = () => n.value && r.value && !!i.value;
	function re() {
		U(), ne() && (!o.value || Y(o.value)) && (B = setTimeout(() => void le(!0), 2e3));
	}
	function K() {
		N += 1, L += 1, y.value = b.value = !1, s.value = null, m.value = h.value = g.value = "", c.value = [], l.value = [], x.value = S.value = null, T.value = D.value = ee.value = k.value = !1, C.value = w.value = "tail", A.value = !0;
	}
	async function ie(t = "incremental") {
		if (!ne() || !a.value || !i.value || t === "incremental" && y.value || t === "incremental" && C.value === "start" && D.value || t === "next" && !D.value) return;
		let n = M, r = ++N, o = t === "tail" || t === "start" || x.value === null, s = {
			limit: 500,
			...t === "start" ? { after_id: 0 } : t !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		y.value = !0;
		try {
			let l = await e.events(i.value, a.value, s, V.signal);
			if (!G(n) || r !== N) return;
			c.value = o ? l.items : ce(c.value, l.items), x.value = l.next_after_id, (t === "tail" || t === "start") && (C.value = t), o && C.value === "tail" ? (T.value = l.has_more, D.value = !1) : (D.value = l.has_more, C.value === "start" && (T.value = !1)), h.value = "";
		} catch (e) {
			G(n) && r === N && (h.value = Ve(e));
		} finally {
			G(n) && r === N && (y.value = !1);
		}
	}
	async function ae(t = "incremental") {
		if (!ne() || !a.value || !i.value || t === "incremental" && b.value || t === "incremental" && w.value === "start" && k.value || t === "next" && !k.value) return;
		let n = M, r = ++L, o = t === "tail" || t === "start" || S.value === null, s = {
			limit: 500,
			...t === "start" ? { cursor: 0 } : t !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		b.value = !0;
		try {
			let c = await e.logs(i.value, a.value, s, V.signal);
			if (!G(n) || r !== L) return;
			l.value = o ? c.items : [...l.value, ...c.items], S.value = c.next_cursor, (t === "tail" || t === "start") && (w.value = t), k.value = c.has_more, ee.value = w.value === "tail" && c.available, A.value = c.available, g.value = "";
		} catch (e) {
			G(n) && r === L && (g.value = Ve(e));
		} finally {
			G(n) && r === L && (b.value = !1);
		}
	}
	async function oe(t) {
		if (i.value && a.value) try {
			let n = await e.progress(i.value, a.value, V.signal);
			if (!G(t)) return;
			s.value = n.progress, m.value = "";
		} catch (e) {
			G(t) && (m.value = Ve(e));
		}
	}
	function se() {
		return le(!1);
	}
	function le(e) {
		if (!ne() || !i.value) return Promise.resolve();
		if (e || (v.value = !0), z) return z;
		let t = M, n = ++R;
		return z = ue(t, n).finally(() => {
			G(t) && n === R && (z = null, v.value = !1, re());
		}), z;
	}
	async function ue(n, r) {
		if (i.value) {
			U();
			try {
				let s = await e.detail(i.value, V.signal);
				if (!G(n) || r !== R) return;
				o.value = s.task;
				let c = s.task.runs || [];
				if (a.value && !c.some((e) => F(e.id, a.value))) {
					K(), p.value = `所选运行 #${a.value} 不存在或已不可用，请选择其他运行。`;
					return;
				}
				let l = a.value || s.task.last_run_id || c.at(-1)?.id || null, d = c.some((e) => F(e.id, l)) ? l : c.at(-1)?.id || null;
				if (d !== a.value && (K(), a.value = d), p.value = "", a.value && await Promise.allSettled([
					oe(n),
					ie(),
					...u.value === "logs" ? [ae()] : []
				]), !G(n)) return;
				!Y(s.task) && !H && (H = !0, t());
			} catch (e) {
				G(n) && (p.value = Ve(e));
			}
		}
	}
	function q(e, t, r) {
		return W(), n.value = !0, i.value = P(e), a.value = I(t), o.value = null, p.value = "", u.value = "events", d.value = r || null, H = !1, K(), se();
	}
	function J() {
		n.value = !1, W();
	}
	function de(e) {
		if (e = P(e), !F(e, a.value)) return W(), a.value = e, d.value = null, K(), se();
	}
	function fe(e) {
		if (u.value = e, e === "logs") return ae();
	}
	function X(e) {
		r.value !== e && (r.value = e, e ? n.value && se() : W());
	}
	return f(J), {
		opened: n,
		taskId: i,
		runId: a,
		task: o,
		runs: j,
		selectedRun: te,
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
		logsEarlier: ee,
		logsMore: k,
		logsAvailable: A,
		open: q,
		close: J,
		selectRun: de,
		selectTab: fe,
		setVisible: X,
		refresh: se,
		loadEvents: ie,
		loadLogs: ae
	};
}
// src/features/tasks/detail/TaskFailure.vue?vue&type=script&setup=true&lang.ts
var Ue = {
	key: 0,
	class: "tc-progress-failure tc-task-failure"
}, We = { key: 0 }, Ge = { key: 1 }, Ke = {
	key: 2,
	class: "tc-failure-secondary"
}, qe = { key: 3 }, Je = { key: 0 }, Ye = { key: 1 }, Xe = { key: 2 }, Ze = /* @__PURE__ */ t({
	__name: "TaskFailure",
	props: {
		failure: {},
		execution: {},
		status: {}
	},
	setup(e) {
		let t = e, r = E(() => !!(t.execution?.error_message || t.execution?.error_info)), i = E(() => (t.failure?.country_failures || []).filter((e) => xe(e.country).trim())), a = E(() => {
			let e = t.failure;
			return e ? i.value.length && !e.error_info?.auto_refresh_at_failed ? `${i.value.length} 个国家查询失败，展开查看具体原因` : de(e) : "";
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
			].includes(n) && n !== e.stage ? R("stage", n) : [e.label || e.step_id || "阶段记录缺失", e.stage].filter(Boolean).join(" · ");
		}), c = E(() => r.value ? V(t.execution?.error_info, t.execution?.error_message) : ""), l = E(() => {
			if (!t.failure || !r.value) return !1;
			let e = (e) => xe(e).replace(/\s+/g, " ").trim(), n = t.failure, i = n.error_info, a = t.execution?.error_info, o = e(n.message), s = e(t.execution?.error_message);
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
		return (t, d) => e.failure || r.value ? (n(), A("details", Ue, [
			x("summary", null, [
				e.failure ? (n(), A("strong", We, y(k(oe)(e.failure) ? "历史失败位置" : "失败位置") + "：" + y(s.value), 1)) : (n(), A("strong", Ge, "执行失败")),
				x("span", null, y(a.value || c.value), 1),
				e.failure && r.value && !l.value ? (n(), A("span", Ke, "执行错误：" + y(c.value), 1)) : p("", !0),
				e.execution?.error_info?.display_code ? (n(), A("small", qe, y(e.execution.error_info.display_code), 1)) : p("", !0)
			]),
			i.value.length ? (n(), A("ul", Je, [(n(!0), A(h, null, o(i.value, (e, t) => (n(), A("li", { key: t }, y(e.country) + "：" + y(e.summary || "诊断记录不完整"), 1))), 128))])) : p("", !0),
			e.failure?.event_id ? (n(), A("p", Ye, "关联事件 " + y(e.failure.event_id), 1)) : p("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(k(xe)(e.status)) ? (n(), A("p", Xe, "原请求证据已保留")) : p("", !0),
			x("pre", null, y(JSON.stringify(u.value, null, 2)), 1)
		])) : p("", !0);
	}
}), Qe = {
	key: 0,
	class: "tc-progress",
	"aria-label": "执行进度"
}, $e = { class: "tc-progress-heading" }, et = { key: 0 }, tt = [
	"aria-pressed",
	"title",
	"onClick"
], nt = {
	key: 0,
	class: "tc-step-dot",
	"aria-hidden": "true"
}, rt = {
	key: 1,
	class: "tc-step-meta"
}, it = { key: 0 }, at = {
	key: 2,
	class: "tc-step-meta"
}, ot = { key: 0 }, st = ["aria-label", "onClick"], ct = {
	key: 1,
	class: "tc-detail-muted"
}, lt = {
	key: 2,
	class: "tc-flow-relations"
}, ut = { key: 0 }, dt = {
	key: 3,
	class: "tc-child-tasks"
}, ft = ["onClick"], pt = { id: "tc-step-title" }, mt = { class: "tc-step-dialog-body" }, ht = /* @__PURE__ */ t({
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
		let a = t, s = r, c = E(() => a.taskType === "codex_retry"), u = E(() => c.value ? a.progress?.main_steps || [] : ie(a.progress?.main_steps)), d = E(() => c.value ? u.value.filter((e) => e.observed_order != null || e.evidence === "run_status") : u.value), f = {
			success: "tc-badge--success",
			recovered: "tc-badge--success",
			failed: "tc-badge--danger",
			running: "tc-badge--active",
			stopped: "tc-badge--warning",
			interrupted: "tc-badge--warning",
			debug_paused: "tc-badge--warning"
		};
		function m(e) {
			let t = ae(e);
			return [
				"success",
				"failed",
				"skipped",
				"running"
			].includes(t) ? ue(t) : q(e);
		}
		let g = _(null), v = E(() => u.value.find((e) => ye(e) === g.value)), C = _(), D = null, O = E(() => le(a.progress?.outcome?.child_tasks).flatMap((e) => {
			try {
				return [{
					...e,
					task_id: P(e.task_id),
					run_id: I(e.run_id),
					task_type: e.task_type,
					status: e.status
				}];
			} catch {
				return [];
			}
		})), ee = E(() => {
			let e = me(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${Ce(xe(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			return t ? `当前：${t.label || t.step_id || "执行中"}${t.child_label ? ` · ${t.child_label}` : ""}` : "执行阶段";
		});
		function te(e) {
			return [
				Se(e),
				q(e),
				...he(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function M(e) {
			return ye(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function N(t) {
			D = document.activeElement instanceof HTMLElement ? document.activeElement : null, g.value = ye(t), await e(), C.value?.open || C.value?.showModal();
		}
		function F() {
			C.value?.close(), g.value = null, D?.isConnected && D.focus({ preventScroll: !0 }), D = null;
		}
		function L(e) {
			let t = C.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i(() => [a.context, a.active], F), S(() => C.value?.close()), (e, r) => t.progress ? (n(), A("section", Qe, [
			x("div", $e, [x("strong", null, y(ee.value), 1), !c.value || t.progress.source !== "explicit" ? (n(), A("small", et, y(t.progress.source === "legacy_derived" ? "历史记录还原" : t.progress.source === "insufficient_evidence" ? "步骤记录缺失" : "按首次记录排列，可含分支与重试"), 1)) : p("", !0)]),
			d.value.length ? (n(), A("ul", {
				key: 0,
				class: T(["tc-progress-track", { "tc-progress-track--codex": c.value }]),
				"aria-label": "执行阶段，排列不代表固定顺序"
			}, [(n(!0), A(h, null, o(d.value, (e) => (n(), A("li", {
				key: k(ye)(e),
				class: T([
					"tc-step",
					`tc-step--${k(ae)(e)}`,
					{ "tc-step--selected": M(e) }
				])
			}, [x("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": M(e),
				title: te(e),
				onClick: (t) => s("filter", M(e) ? null : k(ye)(e))
			}, [
				c.value ? p("", !0) : (n(), A("span", nt)),
				x("strong", null, y(k(Se)(e)), 1),
				c.value ? (n(), A("span", rt, [x("span", { class: T(["tc-badge tc-step-status", f[k(ae)(e)]]) }, y(m(e)), 3), k(ae)(e) !== "skipped" && k(K)(e) != null ? (n(), A("small", it, y(k(W)(k(K)(e))), 1)) : p("", !0)])) : (n(), A("span", at, [
					j(y(k(q)(e)), 1),
					k(K)(e) == null ? p("", !0) : (n(), A("small", ot, " · " + y(k(W)(k(K)(e))), 1)),
					(n(!0), A(h, null, o(k(he)(e), (e) => (n(), A("small", { key: e }, " · " + y(e), 1))), 128))
				]))
			], 8, tt), x("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${k(Se)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => N(e)
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
			})], -1)]], 8, st)], 2))), 128))], 2)) : (n(), A("p", ct, y(c.value ? "此运行暂无阶段记录。" : "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。"), 1)),
			u.value.length ? (n(), A("details", lt, [
				r[3] ||= x("summary", null, "依赖与执行记录", -1),
				x("p", null, y(t.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1),
				(n(!0), A(h, null, o(u.value, (e) => (n(), A("div", {
					key: k(ye)(e),
					class: "tc-flow-relation"
				}, [
					x("strong", null, y(k(Se)(e)), 1),
					c.value ? (n(), A("span", ut, y(m(e)), 1)) : p("", !0),
					l(X, {
						step: e,
						siblings: u.value
					}, null, 8, ["step", "siblings"])
				]))), 128))
			])) : p("", !0),
			l(Ze, {
				failure: t.progress.failure,
				execution: t.execution,
				status: t.progress.outcome.status
			}, null, 8, [
				"failure",
				"execution",
				"status"
			]),
			O.value.length ? (n(), A("div", dt, [r[4] ||= x("strong", null, "独立子任务", -1), (n(!0), A(h, null, o(O.value, (e) => (n(), A("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, y(k(R)("task_type", k(xe)(e.task_type))) + " #" + y(e.task_id) + " · " + y(k(ue)(e.status)), 9, ft))), 128))])) : p("", !0),
			x("dialog", {
				ref_key: "inspector",
				ref: C,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: w(F, ["prevent"]),
				onClose: r[0] ||= (e) => g.value = null,
				onWheel: w(L, ["stop"]),
				onClick: r[1] ||= (e) => {
					e.target === C.value && F();
				}
			}, [x("header", null, [x("h3", pt, y(v.value ? k(Se)(v.value) : "步骤详情"), 1), x("button", {
				type: "button",
				autofocus: "",
				onClick: F
			}, "关闭")]), x("div", mt, [v.value ? (n(), b(_e, {
				key: 0,
				step: v.value,
				siblings: u.value
			}, null, 8, ["step", "siblings"])) : p("", !0)])], 544)
		])) : p("", !0);
	}
}), gt = { class: "tc-detail-header" }, _t = { id: "tc-detail-title" }, vt = { key: 0 }, yt = ["title"], bt = {
	key: 0,
	class: "tc-detail-status"
}, xt = {
	key: 1,
	class: "tc-detail-run"
}, St = ["value", "disabled"], Ct = ["value"], wt = {
	key: 1,
	value: ""
}, Tt = ["value"], Et = { class: "tc-detail-header-actions" }, Dt = ["disabled"], Ot = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, kt = { key: 0 }, At = ["disabled"], jt = {
	key: 1,
	class: "tc-detail-empty",
	role: "status"
}, Mt = {
	key: 0,
	class: "tc-detail-notice"
}, Nt = {
	key: 1,
	class: "tc-detail-notice"
}, Pt = {
	key: 3,
	class: "tc-detail-error",
	role: "status"
}, Ft = { class: "tc-detail-view-toolbar" }, It = [
	"id",
	"data-detail-tab",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], Lt = { class: "tc-detail-filter" }, Rt = {
	key: 0,
	class: "tc-detail-read-toolbar"
}, zt = ["aria-pressed", "disabled"], Bt = ["aria-pressed", "disabled"], Vt = {
	id: "tc-detail-panel-events",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-events",
	tabindex: "0"
}, Ht = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Ut = ["disabled"], Wt = {
	key: 1,
	class: "tc-detail-notice"
}, Gt = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, Kt = { class: "tc-event-meta" }, qt = { key: 0 }, Jt = {
	key: 0,
	class: "tc-technical"
}, Yt = ["disabled"], Xt = {
	id: "tc-detail-panel-logs",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-logs",
	tabindex: "0"
}, Zt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Qt = ["disabled"], $t = {
	key: 1,
	class: "tc-detail-notice"
}, en = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, tn = { class: "tc-event-meta" }, nn = {
	key: 0,
	class: "tc-technical"
}, rn = ["disabled"], an = {
	id: "tc-detail-panel-artifacts",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-artifacts",
	tabindex: "0"
}, on = {
	key: 0,
	class: "tc-artifact"
}, sn = { key: 0 }, cn = { class: "tc-artifact-links" }, ln = ["href"], un = ["href"], dn = ["href"], fn = {
	key: 1,
	class: "tc-detail-empty"
}, pn = {
	key: 2,
	class: "tc-technical"
}, mn = { class: "tc-detail-footer" }, hn = {
	key: 1,
	role: "status"
}, gn = /* @__PURE__ */ t({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(t, { expose: r, emit: c }) {
		let u = c, d = He(void 0, () => u("refresh")), { opened: f, taskId: m, runId: g, task: C, runs: D, selectedRun: O, progress: te, events: M, logs: N, tab: P, stepFilter: I, error: L, progressError: z, eventsError: B, logsError: V, loading: H, eventsLoading: U, logsLoading: G, eventsMode: re, logsMode: K, eventsEarlier: ie, eventsMore: ae, logsEarlier: oe, logsMore: ce, logsAvailable: le } = d, q = _(), J = _(), Y = _(0), de = Intl.DateTimeFormat().resolvedOptions().timeZone, X = [
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
		], he = E(() => te.value?.main_steps || []), _e = E(() => he.value.find((e) => ye(e) === I.value || !!(I.value && e.raw_stages?.includes(I.value)))), be = E(() => fe(M.value.filter((e) => ve(e, I.value, he.value)))), we = E(() => N.value.filter((e) => ve(e, I.value, he.value, !0))), Te = E(() => be.value.map((e) => {
			let t = ge(e), n = se(e.detail);
			return {
				event: e,
				state: t,
				timestamp: Ce(e.created_at),
				stageLabel: e.stage_label || R("stage", e.stage),
				association: Pe(e),
				stateLabel: t ? ue(t) : "记录",
				detailJson: n ? JSON.stringify(n, null, 2) : null
			};
		})), Ee = E(() => we.value.map((e) => {
			let t = se(e.fields);
			return {
				item: e,
				timestamp: e.ts ? Ce(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), De = E(() => g.value ? O.value : C.value), Oe = E(() => C.value?.email_snapshot || C.value?.email || (C.value?.account_id ? `账号 #${C.value.account_id}` : C.value?.target_id || "执行记录与诊断")), ke = E(() => (C.value?.resources || []).filter((e) => !g.value || F(e.run_id, g.value))), Ae = E(() => O.value?.debug_artifacts), je = E(() => me(O.value?.debug_pause || te.value?.debug_pause)), Me = null, Ne = !1;
		function Pe(e) {
			let t = me(e.detail), n = xe(e.main_step_id || t.main_step_id), r = xe(e.raw_stage || t.raw_stage || e.stage), i = he.value.filter((e) => n ? e.id === n : e.raw_stages?.includes(r));
			return i.length === 1 ? Se(i[0]) : "未关联步骤";
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
		function Ue(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			let t = X.findIndex((e) => e.id === P.value), n = e.key === "Home" ? 0 : e.key === "End" ? X.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + X.length) % X.length;
			e.preventDefault(), Ve(X[n].id), e.currentTarget.querySelector(`[data-detail-tab="${X[n].id}"]`)?.focus();
		}
		async function We(t) {
			Ne = !0, P.value === "events" ? await d.loadEvents(t) : await d.loadLogs(t), await e(), J.value && t !== "next" && (J.value.scrollTop = t === "tail" ? J.value.scrollHeight : 0), Y.value = 0, Ne = !1;
		}
		function Ge() {
			J.value && (J.value.scrollTop = J.value.scrollHeight), Y.value = 0;
		}
		function Ke(e) {
			let t = J.value;
			q.value && q.value.scrollHeight > q.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i([M, N], async ([t, n], [r, i]) => {
			if (Ne) return;
			let a = J.value, o = !a || a.scrollTop + a.clientHeight >= a.scrollHeight - 40, s = P.value === "events" ? t.length - r.length : P.value === "logs" ? n.length - i.length : 0;
			s <= 0 || (await e(), o ? Ge() : Y.value += s);
		}), i(I, () => {
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
			onWheel: Ke
		}, [
			x("header", gt, [
				x("h2", _t, [j("任务 #" + y(k(m)) + " ", 1), k(C) ? (n(), A("span", vt, y(k(R)("task_type", k(C).task_type)), 1)) : p("", !0)]),
				x("span", {
					class: "tc-detail-target",
					title: String(Oe.value),
					tabindex: "0"
				}, y(Oe.value), 9, yt),
				De.value ? (n(), A("div", bt, [x("strong", null, y(k(R)("status", De.value.status)), 1), x("span", null, "耗时 " + y(k(W)(De.value.duration_ms)), 1)])) : p("", !0),
				k(C) ? (n(), A("label", xt, [t[10] ||= x("span", null, "运行", -1), x("select", {
					value: k(g) || "",
					"aria-label": "选择执行实例",
					disabled: k(D).length < 2 && (!k(g) || !!k(O)),
					onChange: Be
				}, [k(g) && !k(O) ? (n(), A("option", {
					key: 0,
					value: k(g),
					disabled: ""
				}, "运行 #" + y(k(g)) + " 不可用", 9, Ct)) : k(D).length ? p("", !0) : (n(), A("option", wt, "暂无运行")), (n(!0), A(h, null, o(k(D), (e) => (n(), A("option", {
					key: e.id,
					value: e.id
				}, "第 " + y(e.run_no || "—") + " 次 · " + y(k(R)("status", e.status)), 9, Tt))), 128))], 40, St)])) : p("", !0),
				x("div", Et, [x("button", {
					type: "button",
					disabled: k(H),
					onClick: t[0] ||= (...e) => k(d).refresh && k(d).refresh(...e)
				}, y(k(H) ? "刷新中…" : "刷新"), 9, Dt), x("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Ie
				}, "关闭")])
			]),
			k(L) ? (n(), A("div", Ot, [
				j("读取任务失败：" + y(k(L)), 1),
				k(C) ? (n(), A("span", kt, "。保留上次已读取的记录。")) : p("", !0),
				x("button", {
					type: "button",
					disabled: k(H),
					onClick: t[1] ||= (...e) => k(d).refresh && k(d).refresh(...e)
				}, "重试", 8, At)
			])) : p("", !0),
			k(H) && !k(C) ? (n(), A("div", jt, "正在读取任务详情…")) : p("", !0),
			k(C) ? (n(), A(h, { key: 2 }, [
				De.value?.status === "queued" ? (n(), A("p", Mt, y(k(ne)(De.value)), 1)) : p("", !0),
				je.value.state === "paused" ? (n(), A("p", Nt, [t[11] ||= j("调试暂停，等待结束调试。", -1), je.value.hold_until ? (n(), A(h, { key: 0 }, [j("保留至 " + y(k(Ce)(je.value.hold_until)) + "。", 1)], 64)) : p("", !0)])) : p("", !0),
				k(te) ? p("", !0) : (n(), b(Ze, {
					key: 2,
					execution: De.value,
					status: De.value?.status
				}, null, 8, ["execution", "status"])),
				l(ht, {
					progress: k(te),
					"task-type": k(C)?.task_type,
					execution: De.value,
					filter: k(I),
					active: k(f),
					context: `${k(m)}:${k(g)}`,
					onFilter: t[2] ||= (e) => I.value = e,
					onChild: Le
				}, null, 8, [
					"progress",
					"task-type",
					"execution",
					"filter",
					"active",
					"context"
				]),
				k(z) ? (n(), A("p", Pt, [j("进度读取失败：" + y(k(z)), 1), k(te) ? (n(), A(h, { key: 0 }, [j("；保留上次快照")], 64)) : p("", !0)])) : p("", !0),
				x("div", Ft, [
					x("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: Ue
					}, [(n(), A(h, null, o(X, (e) => x("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": k(P) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: k(P) === e.id ? 0 : -1,
						onClick: (t) => Ve(e.id)
					}, y(e.label), 9, It)), 64))], 32),
					x("div", Lt, [x("span", null, [t[12] ||= j("当前查看：", -1), x("strong", null, y(_e.value ? k(Se)(_e.value) : k(I) || "全流程"), 1)]), k(I) ? (n(), A("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => I.value = null
					}, "清除步骤筛选")) : p("", !0)]),
					k(P) === "artifacts" ? p("", !0) : (n(), A("div", Rt, [x("button", {
						type: "button",
						"aria-pressed": (k(P) === "events" ? k(re) : k(K)) === "start",
						disabled: k(U) || k(G) || !k(g),
						onClick: t[4] ||= (e) => We("start")
					}, "从头加载", 8, zt), x("button", {
						type: "button",
						"aria-pressed": (k(P) === "events" ? k(re) : k(K)) === "tail",
						disabled: k(U) || k(G) || !k(g),
						onClick: t[5] ||= (e) => We("tail")
					}, "最近记录", 8, Bt)]))
				]),
				x("div", {
					ref_key: "scroller",
					ref: J,
					class: "tc-detail-content"
				}, [
					a(x("section", Vt, [
						k(B) ? (n(), A("p", Ht, [j("事件读取失败：" + y(k(B)), 1), x("button", {
							type: "button",
							disabled: k(U),
							onClick: t[6] ||= (e) => k(d).loadEvents()
						}, "重试", 8, Ut)])) : p("", !0),
						k(ie) ? (n(), A("p", Wt, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : p("", !0),
						be.value.length ? p("", !0) : (n(), A("div", Gt, y(k(U) ? "正在读取事件…" : k(I) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(n(!0), A(h, null, o(Te.value, (e) => (n(), A("article", {
							key: e.event.id,
							class: T(["tc-event", { "tc-event--error": e.state === "failed" }])
						}, [
							x("div", Kt, [
								x("time", null, y(e.timestamp), 1),
								x("span", null, y(e.event.level || "INFO"), 1),
								x("strong", null, y(e.stageLabel), 1),
								e.association ? (n(), A("span", qt, y(e.association), 1)) : p("", !0),
								x("span", null, y(e.stateLabel), 1),
								x("small", null, "事件 " + y(e.event.event_id || e.event.id), 1)
							]),
							x("p", null, y(e.event.message || "—"), 1),
							e.detailJson ? (n(), A("details", Jt, [t[13] ||= x("summary", null, "技术详情", -1), x("pre", null, y(e.detailJson), 1)])) : p("", !0)
						], 2))), 128)),
						k(ae) ? (n(), A("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: k(U),
							onClick: t[7] ||= (e) => We("next")
						}, y(k(U) ? "正在读取…" : "继续加载后续事件"), 9, Yt)) : p("", !0)
					], 512), [[ee, k(P) === "events"]]),
					a(x("section", Xt, [
						k(V) ? (n(), A("p", Zt, [j("日志读取失败：" + y(k(V)), 1), x("button", {
							type: "button",
							disabled: k(G),
							onClick: t[8] ||= (e) => k(d).loadLogs()
						}, "重试", 8, Qt)])) : p("", !0),
						k(oe) ? (n(), A("p", $t, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : p("", !0),
						we.value.length ? p("", !0) : (n(), A("div", en, y(k(G) ? "正在读取运行日志…" : k(le) ? k(I) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(n(!0), A(h, null, o(Ee.value, (e, r) => (n(), A("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${r}`,
							class: "tc-log-line"
						}, [
							x("div", tn, [
								x("time", null, y(e.timestamp), 1),
								x("strong", null, y(e.item.level || "INFO"), 1),
								x("span", null, y(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							x("p", null, y(e.item.message), 1),
							e.detailJson ? (n(), A("details", nn, [t[14] ||= x("summary", null, "技术详情", -1), x("pre", null, y(e.detailJson), 1)])) : p("", !0)
						]))), 128)),
						k(ce) ? (n(), A("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: k(G),
							onClick: t[9] ||= (e) => We("next")
						}, y(k(G) ? "正在读取…" : "继续加载后续日志"), 9, rn)) : p("", !0)
					], 512), [[ee, k(P) === "logs"]]),
					a(x("section", an, [
						Ae.value?.available ? (n(), A("article", on, [
							t[15] ||= x("h3", null, "Roxy 刷新调试", -1),
							x("p", null, y(Ae.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + y(k(me)(Ae.value.summary).request_count || 0) + " 条", 1),
							k(O)?.result_summary?.debug_browser_kept === !0 ? (n(), A("p", sn, "失败窗口已保留，可在 Roxy 中查看。")) : p("", !0),
							x("div", cn, [
								k(pe)(Ae.value.har_url) ? (n(), A("a", {
									key: 0,
									href: k(pe)(Ae.value.har_url),
									download: ""
								}, "下载 HAR", 8, ln)) : p("", !0),
								k(pe)(Ae.value.page_state_url) ? (n(), A("a", {
									key: 1,
									href: k(pe)(Ae.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, un)) : p("", !0),
								k(pe)(Ae.value.screenshot_url) ? (n(), A("a", {
									key: 2,
									href: k(pe)(Ae.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, dn)) : p("", !0)
							])
						])) : p("", !0),
						(n(!0), A(h, null, o(ke.value, (e, t) => (n(), A("article", {
							key: k(xe)(e.id) || t,
							class: "tc-artifact"
						}, [
							x("h3", null, y(e.resource_type || "运行资源"), 1),
							x("p", null, y(e.provider || e.state || "—"), 1),
							x("small", null, y(k(Ce)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!Ae.value?.available && !ke.value.length ? (n(), A("div", fn, "当前 Run 没有诊断资源或产物")) : p("", !0),
						De.value?.result_summary ? (n(), A("details", pn, [t[16] ||= x("summary", null, "执行结果字段", -1), x("pre", null, y(JSON.stringify(De.value.result_summary, null, 2)), 1)])) : p("", !0)
					], 512), [[ee, k(P) === "artifacts"]])
				], 512),
				x("footer", mn, [x("small", null, "时间按浏览器时区显示 · " + y(k(de)), 1), Y.value && k(P) !== "artifacts" ? (n(), A("button", {
					key: 0,
					type: "button",
					onClick: Ge
				}, "有 " + y(Y.value) + " 条新记录，回到底部", 1)) : k(H) || k(U) || k(G) ? (n(), A("small", hn, "正在同步记录…")) : p("", !0)])
			], 64)) : p("", !0)
		], 544)]));
	}
}), _n = [
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
function vn(e, t) {
	return e.fields.some((e) => !!t[e]);
}
function yn(e, t, n) {
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
function bn(e, t) {
	let n = { ...t };
	for (let t of e.fields) n[t] = "";
	return n;
}
// src/features/tasks/TaskFilterFields.vue?vue&type=script&setup=true&lang.ts
var xn = {
	key: 0,
	class: "tc-filter-field"
}, Sn = ["for"], Cn = [
	"id",
	"value",
	"inputmode",
	"placeholder"
], wn = ["aria-label"], Tn = ["name", "checked"], En = { class: "tc-filter-option-label" }, Dn = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], On = { class: "tc-filter-option-label" }, kn = {
	key: 0,
	class: "tc-filter-option-count"
}, An = {
	key: 2,
	class: "tc-filter-date-range"
}, jn = { class: "tc-filter-field" }, Mn = ["for"], Nn = ["id", "value"], Pn = { class: "tc-filter-field" }, Fn = ["for"], In = ["id", "value"], Ln = { class: "tc-filter-footer" }, Rn = ["disabled"], zn = /* @__PURE__ */ t({
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
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? yn(r.column, {
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
		function g(e, t) {
			m(s.value, e), t.detail > 0 && i("done");
		}
		function _() {
			i("update:modelValue", bn(r.column, r.modelValue)), i("done");
		}
		return (t, r) => (n(), A("form", {
			class: "tc-filter-fields",
			onSubmit: r[5] ||= w((e) => i("done"), ["prevent"])
		}, [e.column.kind === "search" ? (n(), A("div", xn, [x("label", { for: `${k(a)}-search` }, y(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, Sn), x("input", {
			id: `${k(a)}-search`,
			value: c.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: r[0] ||= (e) => m(s.value, e.target.value)
		}, null, 40, Cn)])) : e.column.kind === "select" ? (n(), A("div", {
			key: 1,
			class: "tc-filter-options",
			role: "radiogroup",
			"aria-label": e.column.label
		}, [x("label", { class: T(["tc-filter-option", { "is-selected": !c.value }]) }, [x("input", {
			type: "radio",
			name: k(a),
			value: "",
			checked: !c.value,
			onChange: r[1] ||= (e) => m(s.value, ""),
			onClick: r[2] ||= (e) => g("", e)
		}, null, 40, Tn), x("span", En, y(l[e.column.group || ""] || "全部"), 1)], 2), (n(!0), A(h, null, o(f.value, (e) => (n(), A("label", {
			key: e.value,
			class: T(["tc-filter-option", { "is-selected": c.value === e.value }])
		}, [
			x("input", {
				type: "radio",
				name: k(a),
				value: e.value,
				checked: c.value === e.value,
				onChange: (t) => m(s.value, e.value),
				onClick: (t) => g(e.value, t)
			}, null, 40, Dn),
			x("span", On, y(e.text), 1),
			e.count == null ? p("", !0) : (n(), A("span", kn, y(e.count), 1))
		], 2))), 128))], 8, wn)) : (n(), A("div", An, [
			r[6] ||= x("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			x("div", jn, [x("label", { for: `${k(a)}-from` }, "创建日期起", 8, Mn), x("input", {
				id: `${k(a)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: r[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, Nn)]),
			x("div", Pn, [x("label", { for: `${k(a)}-to` }, "创建日期止", 8, Fn), x("input", {
				id: `${k(a)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: r[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, In)])
		])), x("div", Ln, [x("button", {
			type: "button",
			class: "ui-link",
			disabled: !k(vn)(e.column, e.modelValue),
			onClick: _
		}, "清除此列", 8, Rn), r[7] ||= x("button", {
			type: "submit",
			class: "ui-button"
		}, "完成", -1)])], 32));
	}
}), Bn = { class: "tc-mobile-filters" }, Vn = { class: "tc-filter-column-picker" }, Hn = ["value"], Un = /* @__PURE__ */ t({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = _(_n[0].key), u = E(() => _n.find((e) => e.key === c.value)), d = E(() => _n.filter((e) => vn(e, i.modelValue)).length);
		return (t, i) => (n(), A("div", Bn, [l(we, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: e.open,
			"onUpdate:open": i[3] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [x("label", Vn, [i[4] ||= j("筛选列", -1), a(x("select", { "onUpdate:modelValue": i[0] ||= (e) => c.value = e }, [(n(!0), A(h, null, o(k(_n), (t) => (n(), A("option", {
				key: t.key,
				value: t.key
			}, y(t.label) + y(k(vn)(t, e.modelValue) ? " · 已筛选" : ""), 9, Hn))), 128))], 512), [[m, c.value]])]), (n(), b(zn, {
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
}), Wn = /* @__PURE__ */ t({
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
		return (t, a) => (n(), b(we, {
			label: e.column.label,
			active: k(vn)(e.column, e.modelValue),
			summary: k(yn)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": a[2] ||= (e) => i("update:open", e)
		}, {
			default: r(() => [l(zn, {
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
}), Gn = /* @__PURE__ */ new Set([
	"failed",
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"password_confirmation_pending"
]), Kn = /* @__PURE__ */ new Set([
	"running",
	"waiting",
	"stopping",
	"cancelling",
	"settling"
]), qn = /* @__PURE__ */ new Set([
	"cancelled",
	"stopped",
	"interrupted"
]), Jn = {
	email_verification_pending: "待验证或补全",
	credential_pending_confirmation: "凭证待核验"
};
function Yn(e, t, n) {
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${R(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function Xn(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function Zn(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: R("status", t),
		tone: G(t),
		title: Yn("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = ne(e) || void 0) : Kn.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = ne(e) || Xn(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : Gn.has(t) ? (r.label = "失败", r.tone = "danger") : qn.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (Gn.has(n) && Gn.has(t) || n === "completed" && t === "success" || n === "in_progress" && Kn.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: Jn[n] || R("target_status", n),
			tone: G(n),
			title: Yn("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Z = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), Qn = (e) => Array.isArray(e) ? e.map(H) : [], Q = (e) => String(e || "").toLowerCase(), $ = /* @__PURE__ */ new Set([
	"unknown",
	"request_unknown",
	"attention_required",
	"manual_reconcile",
	"unconfirmed",
	"password_confirmation_pending",
	"credential_pending_confirmation"
]), $n = /* @__PURE__ */ new Set([
	"failed",
	"error",
	"deactivated"
]);
function er(e) {
	let t = e.error_info;
	if (!t) return !1;
	for (let e of ["cause_code", "code"]) {
		let n = Q(t[e]).trim();
		if (n) {
			if ($.has(n) || ["unknown.unclassified", "task.pending"].includes(n) || /(?:_receipt_missing|_failure_diagnostics_missing|_evidence_missing|_unconfirmed|_request_unknown|\.confirmation|\.safety)$/.test(n)) return !1;
			if (je({ [e]: n }) !== je()) return !0;
		}
	}
	return !1;
}
var tr = {
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
}, nr = {
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
function rr(e, t) {
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
	].includes(r) ? Z("提链成功", "warning", "后续已中断") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Z("提链成功", "danger", "后续失败") : Z("提链成功", "success") : $n.has(i) || er(e) ? Z(t, "danger") : $.has(i) ? Z("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Z("等待提链", "warning") : i === "running" ? Z("提链中", "active") : r === "cancelled" ? Z("已取消") : ["stopped", "interrupted"].includes(r) ? Z("执行已中断", "warning") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Z(t, "danger") : n.ok === !0 ? Z("提链流程完成", "success") : Z("提链结果缺失", "warning");
}
function ir(e, t) {
	let n = H(e.result_summary), r = Q(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : Qn(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes(Q(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = H(e.result);
		return !t && !e.last_success_at ? [] : Qn(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : Qn(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(H(e.result)).length > 0);
	if (s > 0 && o > 0 || !i && n.plan_check_partial === !0) return Z("部分失败", "warning", u ? "含历史数据" : void 0);
	if (c > 0 && s >= c) return u ? Z("查询失败", "danger", "含历史数据") : Z(t, "danger");
	if (er(e)) return Z(t, "danger");
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
function ar(e, t = "执行异常") {
	let n = H(e.result_summary), r = Q(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
	if (e.debug_pause) return Z("调试已暂停", "warning");
	if (["queued", "pending"].includes(r)) {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(tr[String(t)] || "等待执行", "warning");
	}
	if (r === "waiting") {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(tr[String(t)] || Xn(e), "warning");
	}
	if (r === "running") return Z("执行中", "active");
	if (["stopping", "cancelling"].includes(r)) return Z("正在停止", "warning");
	if (r === "settling") return Z("正在收尾", "active");
	if (i === "extract_link") return rr(e, a);
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
	if (i === "plan_check") return ir(e, a);
	if (r === "cancelled") return Z("已取消");
	if (["stopped", "interrupted"].includes(r)) return Z("执行已中断", "warning");
	if (er(e)) return Z(a, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes(Q(e.target_status)) || r === "deactivated") return Z("账号已停用", "danger");
	let o = i === "sub2api_scan" || i === "c2a_scan";
	if (e.error_message || e.error_info || $n.has(r) || !o && n.ok === !1) return Z(a, "danger");
	if (r === "partial_success") return Z("部分完成", "warning");
	if (o) return r === "success" ? Z(i === "c2a_scan" && n.continuation_only === !0 ? "接续检查完成" : nr[i], "success") : Z("扫描未完成", "warning");
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
	return i === "deactivation_mail" && typeof n.detected == "boolean" ? Z(n.detected ? "发现封号邮件" : "未见封号邮件", n.detected ? "warning" : "neutral") : i === "live_check" && n.ok === !0 ? Z("账号正常", "success") : i === "token_refresh" && n.ok === !0 ? Z("令牌已刷新", "success") : i === "account_inspection_batch" && Number(n.failed_count) > 0 ? Z("巡检已完成", "warning", "存在失败") : r === "success" || n.ok === !0 ? Z(nr[i] || "任务已完成", "success") : Z("结果未记录");
}
// src/features/tasks/TaskResultCell.vue
var or = /* @__PURE__ */ t({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, i = E(() => ar(t.task, je(t.task.error_info))), a = E(() => [...new Set([
			U(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? V(t.task.error_info, t.task.error_message) : "",
			t.task.error_message,
			t.task.error_code,
			t.task.error_info?.code,
			t.task.error_info?.cause_code
		].filter((e) => !!e))]);
		return (e, t) => (n(), b(Ae, C(i.value, { title: a.value.join("\n") }), {
			details: r(() => [(n(!0), A(h, null, o(a.value, (e, t) => (n(), A("p", { key: t }, y(e), 1))), 128))]),
			_: 1
		}, 16, ["title"]));
	}
}), sr = ["aria-busy"], cr = [
	"checked",
	"indeterminate",
	"disabled"
], lr = {
	"data-label": "选择",
	class: "ui-col-check"
}, ur = [
	"checked",
	"aria-label",
	"onChange"
], dr = { "data-label": "ID" }, fr = ["onClick"], pr = { "data-label": "类型" }, mr = { "data-label": "目标" }, hr = { "data-label": "执行状态" }, gr = ["title"], _r = ["title"], vr = { "data-label": "目标状态" }, yr = ["title"], br = {
	key: 1,
	class: "tc-cell-line",
	"aria-label": "无额外目标状态"
}, xr = { "data-label": "批次 / 触发" }, Sr = ["onClick"], Cr = { "data-label": "运行次数" }, wr = { "data-label": "当前步骤" }, Tr = {
	"data-label": "创建 / 完成",
	class: "ui-time"
}, Er = { "data-label": "结果 / 错误" }, Dr = { "data-label": "操作" }, Or = { class: "ui-row-actions tc-row-actions" }, kr = ["onClick"], Ar = ["disabled", "onClick"], jr = ["disabled", "onClick"], Mr = ["disabled", "onClick"], Nr = /* @__PURE__ */ t({
	__name: "TaskTable",
	props: {
		items: {},
		selected: {},
		loading: { type: Boolean },
		error: {},
		busy: { type: Boolean },
		filters: { default: Fe },
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
			...Zn(e)
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
		], { widths: m, resize: _, resizeWithKeyboard: v, resetColumns: S } = Oe({
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
			return B(e) || e.current_stage_label || R("stage", e.current_stage);
		}
		function w(e) {
			return [
				e.current_stage_label || R("stage", e.current_stage),
				B(e),
				W(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function D(e) {
			return String(e.bulk_batch_id || H(e.bulk_context).batch_id || "");
		}
		function O(e) {
			return String(e.bulk_round_id || H(e.bulk_context).round_id || "");
		}
		return t({ resetColumns: S }), (t, i) => (n(), A("div", {
			class: "ui-table-scroll tc-table-scroll",
			tabindex: "0",
			"aria-label": "任务列表，可横向滚动",
			"aria-busy": e.loading
		}, [x("table", {
			class: "ui-table ui-table--sticky-end ui-table--cards tc-table",
			style: g({ "--ui-table-width": `${k(m).reduce((e, t) => e + t, 0)}px` })
		}, [
			i[3] ||= x("caption", { class: "ui-sr-only" }, "任务中心列表，选择任务可批量操作", -1),
			x("colgroup", null, [(n(!0), A(h, null, o(k(m), (e, t) => (n(), A("col", {
				key: t,
				style: g({ width: `${e}px` })
			}, null, 4))), 128))]),
			x("thead", null, [x("tr", null, [(n(), A(h, null, o(f, (t, r) => x("th", {
				key: t,
				scope: "col",
				class: T({ "ui-col-check": r === 0 })
			}, [r === 0 ? (n(), A("input", {
				key: 0,
				type: "checkbox",
				"aria-label": "全选当前页任务",
				checked: c.value,
				indeterminate: u.value,
				disabled: !e.items.length,
				onChange: i[0] ||= (e) => s("selectPage", e.target.checked)
			}, null, 40, cr)) : (n(), A(h, { key: 1 }, [k(_n)[r - 1] ? (n(), b(Wn, {
				key: 0,
				column: k(_n)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === k(_n)[r - 1].key,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:filters", e),
				"onUpdate:open": (e) => s("update:openFilter", e ? k(_n)[r - 1].key : null)
			}, null, 8, [
				"column",
				"model-value",
				"facets",
				"open",
				"onUpdate:open"
			])) : (n(), A(h, { key: 1 }, [j(y(t), 1)], 64)), r < f.length - 1 ? (n(), b(ke, {
				key: 2,
				label: t,
				onStart: (e) => k(_)(r, e),
				onNudge: (e) => k(v)(r, e)
			}, null, 8, [
				"label",
				"onStart",
				"onNudge"
			])) : p("", !0)], 64))], 2)), 64))])]),
			x("tbody", null, [(n(!0), A(h, null, o(d.value, ({ task: t, execution: i, target: a }) => (n(), A("tr", {
				key: t.id,
				class: T({ "is-selected": e.selected.has(t.id) })
			}, [
				x("td", lr, [x("input", {
					type: "checkbox",
					checked: e.selected.has(t.id),
					"aria-label": `选择任务 #${t.id}`,
					onChange: (e) => s("select", t.id, e.target.checked)
				}, null, 40, ur)]),
				x("td", dr, [x("button", {
					type: "button",
					class: "ui-link tc-task-id",
					onClick: (e) => s("detail", t.id)
				}, "#" + y(t.id), 9, fr)]),
				x("td", pr, [l(Ee, { text: k(R)("task_type", t.task_type) }, null, 8, ["text"])]),
				x("td", mr, [l(Ee, {
					text: t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—",
					secondary: t.email_snapshot || t.email || "—"
				}, {
					default: r(() => [x("strong", null, y(t.account_id ? `账号 #${t.account_id}` : t.attempt_id ? `注册尝试 #${t.attempt_id}` : "—"), 1)]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				x("td", hr, [x("span", {
					class: T(["ui-badge tc-badge", `ui-badge--${i.tone}`]),
					title: i.title
				}, y(i.label), 11, gr), i.secondary ? (n(), A("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: i.secondary
				}, y(i.secondary), 9, _r)) : p("", !0)]),
				x("td", vr, [a ? (n(), A("span", {
					key: 0,
					class: T(["ui-badge tc-badge", `ui-badge--${a.tone}`]),
					title: a.title
				}, y(a.label), 11, yr)) : (n(), A("span", br, "—"))]),
				x("td", xr, [l(Ee, {
					text: t.batch_title || t.batch_uuid || (D(t) ? "查看批次" : "单任务"),
					secondary: k(R)("trigger", t.trigger)
				}, {
					default: r(() => [D(t) ? (n(), A("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: (e) => s("batch", D(t), O(t))
					}, y(t.batch_title || t.batch_uuid || "查看批次"), 9, Sr)) : (n(), A(h, { key: 1 }, [j(y(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				x("td", Cr, [l(Ee, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				x("td", wr, [l(Ee, {
					text: C(t),
					secondary: k(W)(t.duration_ms),
					title: w(t),
					tone: k(B)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				x("td", Tr, [l(Ee, {
					text: k(Ce)(t.created_at),
					secondary: k(Ce)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				x("td", Er, [l(or, { task: t }, null, 8, ["task"])]),
				x("td", Dr, [x("div", Or, [
					x("button", {
						type: "button",
						class: "ui-link",
						onClick: (e) => s("detail", t.id)
					}, "详情", 8, kr),
					k(z)(t) ? (n(), A("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						disabled: e.busy,
						onClick: (e) => s("action", t, "retry")
					}, "重跑", 8, Ar)) : p("", !0),
					k(be)(t) ? (n(), A("button", {
						key: 1,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "terminate")
					}, y(t.status === "queued" ? "取消" : "终止"), 9, jr)) : p("", !0),
					k(Y)(t) ? p("", !0) : (n(), A("button", {
						key: 2,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "delete")
					}, "删除", 8, Mr))
				])])
			], 2))), 128)), e.items.length ? p("", !0) : (n(), b(Te, {
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
		], 4)], 8, sr));
	}
}), Pr = /* @__PURE__ */ t({
	__name: "StatusBadge",
	props: {
		value: {},
		group: { default: "status" }
	},
	setup(e) {
		return (t, r) => (n(), A("span", { class: T(["ui-badge tc-badge", `ui-badge--${k(G)(e.value)}`]) }, y(k(R)(e.group, e.value)), 3));
	}
});
// src/features/tasks/useTaskList.ts
function Fr() {
	let t = c(Fe()), n = _(1), r = _(20), a = _(0), o = _([]), s = _({}), l = _(/* @__PURE__ */ new Set()), u = _(!1), d = _(""), p = _(!1), m = E(() => Math.max(1, Math.ceil(a.value / r.value))), h = 0, g = null, v, y, b = 0, x = 0, S = "", C = "", w = !1, T = /* @__PURE__ */ new Set([
		"task_id",
		"target",
		"batch",
		"result"
	]), D, O = () => JSON.stringify({ ...t }), ee = (e = O()) => w && (S !== e || Date.now() - x >= 3e4);
	function k(t = 0) {
		clearTimeout(y);
		let n = ++b, r = () => {
			n === b && p.value && !document.hidden && j();
		};
		t ? y = setTimeout(r, t) : e(r);
	}
	let A = () => {
		clearTimeout(v), p.value && !document.hidden && (v = setTimeout(() => void j(), 5e3));
	};
	async function j(e = {}) {
		clearTimeout(v), clearTimeout(y), ++b;
		let i = {
			...t,
			page: n.value,
			page_size: r.value
		}, c = JSON.stringify(i), f = O(), p = !!(e.metadata || ee(f)), _ = ++h;
		g?.abort(), g = new AbortController(), u.value = !0;
		try {
			let e = await Be.list({
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
			_ === h && !te(e) && (d.value = e instanceof Error ? e.message : "任务列表加载失败");
		} finally {
			_ === h && (u.value = !1, g = null, !p && ee() ? k() : A());
		}
	}
	function M(e) {
		e !== p.value && (p.value = e, clearTimeout(v), clearTimeout(y), e && !document.hidden ? k() : (++b, g?.abort(), ++h, u.value = !1));
	}
	function N(e) {
		e !== w && (w = e, !u.value && ee() && p.value && !document.hidden && k());
	}
	function P(e, r = !0) {
		Object.assign(t, r ? {
			...Fe(),
			...e
		} : e), n.value = 1, l.value = /* @__PURE__ */ new Set();
	}
	function F(e, t) {
		let n = new Set(l.value);
		t ? n.add(e) : n.delete(e), l.value = n;
	}
	function I(e) {
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
		D = void 0, ++h, g?.abort(), k(a);
	});
	let L = () => {
		clearTimeout(v), document.hidden ? (++b, clearTimeout(y), g?.abort(), ++h, u.value = !1) : p.value && k();
	};
	return document.addEventListener("visibilitychange", L), f(() => {
		++h, ++b, g?.abort(), clearTimeout(v), clearTimeout(y), document.removeEventListener("visibilitychange", L);
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
		setFacetsVisible: N,
		applyFilters: P,
		toggle: F,
		togglePage: I
	};
}
// src/features/tasks/useReceipts.ts
var Ir = ({ task_id: e, run_id: t }) => `${e}:${t ?? ""}`;
function Lr() {
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
			let e = await Be.receipts(i, l.signal);
			if (o !== c) return;
			let t = new Map(e.items.map((e) => [Ir(e), e]));
			for (let e of i) {
				let n = t.get(Ir(e));
				n ? (e.status = n.status || "queued", e.message = n.message || (n.status === "success" ? "已确认完成" : "")) : r.value = e.run_id === null ? "部分回执暂未读到，请稍后刷新。" : "部分执行记录暂未读到，请稍后刷新。";
			}
		} catch (e) {
			o === c && !te(e) && (r.value = "回执暂未读到，请稍后刷新。");
		} finally {
			o === c && (n.value = !1, l = null, u());
		}
	}
	function p(t, n) {
		for (let i of t) if (i.accepted) try {
			let t = P(i.task_id), r = I(i.run_id), a = Ir({
				task_id: t,
				run_id: r
			});
			if (e.value.some((e) => Ir(e) === a)) continue;
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
var Rr = {
	class: "tc-root",
	"aria-label": "统一任务中心"
}, zr = {
	key: 0,
	class: "tc-receipts",
	"aria-label": "本次提交的任务回执"
}, Br = { class: "tc-receipts-header" }, Vr = { role: "status" }, Hr = ["disabled"], Ur = {
	key: 0,
	class: "tc-text-danger",
	role: "alert"
}, Wr = { class: "tc-receipt-list" }, Gr = ["onClick"], Kr = { class: "ui-list tc-workspace" }, qr = {
	class: "ui-list-count tc-selection",
	role: "status"
}, Jr = ["title"], Yr = {
	key: 0,
	class: "ui-list-bulkbar tc-bulk-actions",
	role: "group",
	"aria-label": "选中任务批量操作"
}, Xr = ["disabled", "onClick"], Zr = ["role"], Qr = { key: 1 }, $r = /* @__PURE__ */ t({
	__name: "TaskCenter",
	emits: [
		"navigate",
		"batch",
		"changed"
	],
	setup(t, { expose: s, emit: c }) {
		let u = c, f = Fr(), m = Lr(), { filters: g, page: v, size: b, pages: S, total: C, items: w, facets: D, selected: O, loading: te, error: M, visible: N } = f, { items: P, pending: F, error: I, loading: L } = m, R = _(null), z = _(null), B = _(!1), V = _(""), U = _(""), W = _(null);
		i(W, (e) => {
			f.setFacetsVisible(e === "mobile" || _n.some((t) => t.key === e && t.kind === "select"));
		});
		let G = E(() => _n.filter((e) => vn(e, g))), ne = E(() => G.value.map((e) => ({
			key: e.key,
			label: `${e.label}：${yn(e, g, D.value)}`,
			removeLabel: `清除${e.label}筛选`
		}))), K = _([]), ie = E(() => w.value.filter((e) => O.value.has(e.id))), ae = E(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, ie.value.filter((t) => re(t, e)).length]))), oe = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, se = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function ce(e) {
			Object.assign(g, e);
		}
		function le(e) {
			let t = _n.find((t) => t.key === e);
			t && ce(bn(t, g));
		}
		function ue(e, t, n) {
			R.value?.open(e, t, n);
		}
		async function q(t = {}) {
			t.filters && f.applyFilters(t.filters), t.taskId && (await e(), ue(t.taskId, t.runId, t.stepId));
		}
		function J(e) {
			e || (W.value = null), f.setVisible(e), m.setVisible(e);
		}
		function de() {
			R.value?.close();
		}
		function fe(e, t = "任务", n = {}) {
			m.track(e, t), n.navigate !== !1 && u("navigate");
		}
		async function X(e = {}) {
			N.value && await f.refresh(e);
		}
		function pe() {
			X(), u("changed");
		}
		async function me(e, t) {
			if (!B.value && !(t === "delete" && Y(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				B.value = !0, U.value = "", K.value = [], V.value = "";
				try {
					let n = await Be.action(e.id, t), r = H(n.data || n);
					V.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", O.value.delete(e.id), await X(), u("changed");
				} catch (e) {
					U.value = `${oe[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					B.value = !1;
				}
			}
		}
		async function he(e) {
			if (B.value) return;
			let t = ie.value.filter((t) => re(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${oe[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				B.value = !0, U.value = "", V.value = "", K.value = [];
				try {
					let n = await Be.bulk(e, t.map((e) => e.id)), r = Array.isArray(n.accepted) ? n.accepted : [];
					K.value = (n.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let i = Number(n.accepted_count ?? r.length);
					if (e === "cancel") {
						let e = r.filter((e) => e.state === "cancelled").length, t = r.filter((e) => e.state === "cancelling").length;
						V.value = `已取消 ${e} 个，取消中 ${t} 个${i - e - t > 0 ? `，已受理 ${i - e - t} 个` : ""}`;
						let n = new Set(r.map((e) => String(e.task_id)));
						O.value = new Set([...O.value].filter((e) => !n.has(String(e))));
					} else V.value = `已${oe[e]} ${i} 个`, O.value = /* @__PURE__ */ new Set();
					K.value.length && (V.value += `，跳过 ${K.value.length} 个`), await X(), u("changed");
				} catch (t) {
					U.value = `${oe[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					B.value = !1;
				}
			}
		}
		return s({
			open: q,
			refresh: X,
			track: fe,
			closeDetail: de,
			setVisible: J
		}), (e, t) => (n(), A(h, null, [a(x("section", Rr, [k(P).length ? (n(), A("section", zr, [
			x("div", Br, [x("div", null, [t[10] ||= x("strong", null, "本次提交", -1), x("span", Vr, "共 " + y(k(P).length) + " 项 · 等待/执行 " + y(k(F).length) + " · 成功 " + y(k(P).filter((e) => e.status === "success").length) + " · 失败或待处理 " + y(k(P).length - k(F).length - k(P).filter((e) => e.status === "success").length), 1)]), x("button", {
				type: "button",
				class: "ui-button",
				disabled: k(L) || !k(F).length,
				onClick: t[0] ||= (e) => k(m).refresh()
			}, "刷新回执", 8, Hr)]),
			k(I) ? (n(), A("p", Ur, y(k(I)), 1)) : p("", !0),
			x("details", null, [t[11] ||= x("summary", null, "查看任务与最终结果", -1), x("ul", Wr, [(n(!0), A(h, null, o(k(P), (e) => (n(), A("li", { key: `${e.task_id}:${e.run_id}` }, [
				x("button", {
					type: "button",
					class: "ui-link",
					onClick: (t) => ue(e.task_id, e.run_id)
				}, y(e.label) + " #" + y(e.task_id), 9, Gr),
				l(Pr, { value: e.status }, null, 8, ["value"]),
				x("span", null, y(e.message), 1)
			]))), 128))])])
		])) : p("", !0), x("div", Kr, [
			l(Ne, { filtered: G.value.length > 0 }, {
				actions: r(() => [
					l(Un, {
						"model-value": k(g),
						facets: k(D),
						open: W.value === "mobile",
						"onUpdate:modelValue": ce,
						"onUpdate:open": t[1] ||= (e) => W.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					G.value.length ? (n(), A("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: t[2] ||= (e) => k(f).applyFilters({})
					}, "清除全部筛选")) : p("", !0),
					x("span", {
						class: "tc-timezone",
						title: k(se)
					}, "时间按 " + y(k(se)) + " 显示", 9, Jr),
					x("button", {
						type: "button",
						class: "ui-link",
						onClick: t[3] ||= (e) => z.value?.resetColumns()
					}, "恢复列宽")
				]),
				default: r(() => [x("div", qr, y(ie.value.length ? `已选 ${ie.value.length} 项` : `${k(C).toLocaleString()} 个任务`), 1), l(De, {
					items: ne.value,
					onRemove: le
				}, null, 8, ["items"])]),
				_: 1
			}, 8, ["filtered"]),
			ie.value.length ? (n(), A("div", Yr, [(n(), A(h, null, o([
				"retry",
				"cancel",
				"terminate",
				"delete"
			], (e) => x("button", {
				key: e,
				type: "button",
				class: T(["ui-button", { "ui-button--danger": e === "delete" || e === "terminate" }]),
				disabled: B.value || !ae.value[e],
				onClick: (t) => he(e)
			}, y(oe[e]) + y(ae.value[e] ? `（${ae.value[e]}）` : ""), 11, Xr)), 64))])) : p("", !0),
			V.value || U.value || k(M) && k(w).length ? (n(), A("div", {
				key: 1,
				class: T(["ui-list-feedback tc-feedback", { "is-error": U.value || k(M) }]),
				role: U.value || k(M) ? "alert" : "status"
			}, [
				j(y(U.value || k(M) || V.value), 1),
				k(M) ? (n(), A("button", {
					key: 0,
					type: "button",
					class: "ui-link",
					onClick: t[4] ||= (e) => k(f).refresh()
				}, "重试")) : p("", !0),
				K.value.length ? (n(), A("details", Qr, [t[12] ||= x("summary", null, "查看跳过原因", -1), x("ul", null, [(n(!0), A(h, null, o(K.value, (e) => (n(), A("li", { key: e.id }, "#" + y(e.id) + "：" + y(e.message), 1))), 128))])])) : p("", !0)
			], 10, Zr)) : p("", !0),
			l(Nr, {
				ref_key: "table",
				ref: z,
				filters: k(g),
				facets: k(D),
				"open-filter": W.value,
				"onUpdate:openFilter": t[5] ||= (e) => W.value = e,
				"onUpdate:filters": ce,
				items: k(w),
				selected: k(O),
				loading: k(te),
				error: k(M),
				busy: B.value,
				onSelect: k(f).toggle,
				onSelectPage: k(f).togglePage,
				onDetail: ue,
				onAction: me,
				onBatch: t[6] ||= (e, t) => u("batch", e, t),
				onRetry: t[7] ||= (e) => k(f).refresh()
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
				page: k(v),
				"onUpdate:page": t[8] ||= (e) => d(v) ? v.value = e : null,
				size: k(b),
				"onUpdate:size": t[9] ||= (e) => d(b) ? b.value = e : null,
				pages: k(S),
				total: k(C),
				busy: k(te)
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy"
			])
		])], 512), [[ee, k(N)]]), l(gn, {
			ref_key: "detail",
			ref: R,
			onRefresh: pe
		}, null, 512)], 64));
	}
});
// src/main.ts
function ei(e, t = {}) {
	return D($r, t).mount(e);
}
export { ei as mountTaskCenter };
