import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, V as u, X as d, Z as f, _ as p, a as m, c as h, d as g, dt as _, et as v, f as y, ft as b, g as x, h as S, j as C, k as w, l as ee, lt as T, m as E, n as D, nt as O, s as k, st as A, v as j, x as M } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { n as N, r as P, t as F } from "./client-B5R_MNgP.js";
import { a as I, i as te, n as ne, r as L } from "./taskIds-BlchWwUp.js";
import { a as R, n as z, t as re } from "./bulkMutations-3wwPI3-H.js";
import { A as B, C as V, D as H, E as U, F as W, I as ie, M as G, N as ae, O as oe, P as K, S as se, T as ce, _ as le, a as ue, b as q, c as de, d as fe, f as pe, g as me, h as he, i as ge, j as J, k as Y, l as _e, m as ve, n as ye, o as be, p as xe, r as Se, s as Ce, t as we, u as Te, v as Ee, w as De, x as Oe, y as ke } from "./StepEvidence-CUNe31gl.js";
import { n as Ae } from "./time-DOD6oyhP.js";
import { i as je, n as Me, r as X, t as Ne } from "./ListFilterSummary-DsJDWIjH.js";
import { n as Pe, t as Fe } from "./ColumnResizer-C2889-lj.js";
import { t as Ie } from "./ListResult-BADeMxD2.js";
import { t as Le } from "./errorLabels-fdGNkTBr.js";
import { t as Re } from "./ListPagination-CSFkV2Gz.js";
import { t as ze } from "./ListToolbar-Dl7q1T_K.js";
// src/api/tasks.ts
var Be = (e, t = {}) => P(e, t, L);
function Ve() {
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
function He(e) {
	return new URLSearchParams(Object.entries(e).filter(([, e]) => e !== void 0 && e !== "").map(([e, t]) => [e, String(t)])).toString();
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
		let e = await Be(t, {
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
	let n = await R((t, n) => n?.method === "POST" ? z(t, {
		...n,
		body: We(t, {
			action: "terminate",
			task_ids: e
		})
	}) : z(t, n), "/api/operations/bulk", {
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
	list: (e, t) => Be(`/api/operations?${He(e)}`, { signal: t }),
	detail: (e, t) => Be(`/api/operations/${I(e)}?include_events=0`, { signal: t }),
	progress: (e, t, n) => Be(`/api/operations/${I(e)}/runs/${I(t)}/progress`, { signal: n }),
	events: (e, t, n = {}, r) => Be(`/api/operations/${I(e)}/runs/${I(t)}/events?${He({
		limit: 500,
		...n
	})}`, { signal: r }),
	logs: (e, t, n = {}, r) => Be(`/api/operations/${I(e)}/runs/${I(t)}/logs?${He({
		limit: 500,
		...n
	})}`, { signal: r }),
	action: (e, t) => t === "retry" ? Ue(`retry:${I(e)}`, `/api/operations/${I(e)}/retry`) : Be(`/api/operations/${I(e)}/${t}`, { method: "POST" }),
	bulk: (e, t, n) => e === "terminate" ? Ge(t, n) : e === "retry" ? Ue("bulk:retry", "/api/operations/bulk", {
		action: e,
		task_ids: t
	}) : Be("/api/operations/bulk", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: We("/api/operations/bulk", {
			action: e,
			task_ids: t
		})
	})
}, qe = (e) => e instanceof Error ? e.message : "读取失败，请重试";
function Je(e = Ke, t = () => {}) {
	let n = v(!1), r = v(!0), i = v(null), a = v(null), o = O(null), s = O(null), c = O([]), l = O([]), u = v("events"), d = v(null), p = v(""), m = v(""), h = v(""), g = v(""), _ = v(!1), y = v(!1), b = v(!1), x = v(null), S = v(null), C = v("tail"), w = v("tail"), ee = v(!1), T = v(!1), D = v(!1), k = v(!1), A = v(!0), j = E(() => o.value?.runs || []), M = E(() => j.value.find((e) => te(e.id, a.value))), N = 0, P = 0, F = 0, L = 0, R = null, z, re = new AbortController(), B = !1;
	function V() {
		z !== void 0 && clearTimeout(z), z = void 0;
	}
	function H() {
		N += 1, re.abort(), re = new AbortController(), R = null, _.value = y.value = b.value = !1, V();
	}
	let U = (e) => e === N && n.value, W = () => n.value && r.value && !!i.value;
	function ie() {
		V(), W() && (!o.value || J(o.value)) && (z = setTimeout(() => void ce(!0), 2e3));
	}
	function G() {
		P += 1, F += 1, y.value = b.value = !1, s.value = null, m.value = h.value = g.value = "", c.value = [], l.value = [], x.value = S.value = null, ee.value = T.value = D.value = k.value = !1, C.value = w.value = "tail", A.value = !0;
	}
	async function ae(t = "incremental") {
		if (!W() || !a.value || !i.value || t === "incremental" && y.value || t === "incremental" && C.value === "start" && T.value || t === "next" && !T.value) return;
		let n = N, r = ++P, o = t === "tail" || t === "start" || x.value === null, s = {
			limit: 500,
			...t === "start" ? { after_id: 0 } : t !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		y.value = !0;
		try {
			let l = await e.events(i.value, a.value, s, re.signal);
			if (!U(n) || r !== P) return;
			c.value = o ? l.items : xe(c.value, l.items), x.value = l.next_after_id, (t === "tail" || t === "start") && (C.value = t), o && C.value === "tail" ? (ee.value = l.has_more, T.value = !1) : (T.value = l.has_more, C.value === "start" && (ee.value = !1)), h.value = "";
		} catch (e) {
			U(n) && r === P && (h.value = qe(e));
		} finally {
			U(n) && r === P && (y.value = !1);
		}
	}
	async function oe(t = "incremental") {
		if (!W() || !a.value || !i.value || t === "incremental" && b.value || t === "incremental" && w.value === "start" && k.value || t === "next" && !k.value) return;
		let n = N, r = ++F, o = t === "tail" || t === "start" || S.value === null, s = {
			limit: 500,
			...t === "start" ? { cursor: 0 } : t !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		b.value = !0;
		try {
			let c = await e.logs(i.value, a.value, s, re.signal);
			if (!U(n) || r !== F) return;
			l.value = o ? c.items : [...l.value, ...c.items], S.value = c.next_cursor, (t === "tail" || t === "start") && (w.value = t), k.value = c.has_more, D.value = w.value === "tail" && c.available, A.value = c.available, g.value = "";
		} catch (e) {
			U(n) && r === F && (g.value = qe(e));
		} finally {
			U(n) && r === F && (b.value = !1);
		}
	}
	async function K(t) {
		if (i.value && a.value) try {
			let n = await e.progress(i.value, a.value, re.signal);
			if (!U(t)) return;
			s.value = n.progress, m.value = "";
		} catch (e) {
			U(t) && (m.value = qe(e));
		}
	}
	function se() {
		return ce(!1);
	}
	function ce(e) {
		if (!W() || !i.value) return Promise.resolve();
		if (e || (_.value = !0), R) return R;
		let t = N, n = ++L;
		return R = le(t, n).finally(() => {
			U(t) && n === L && (R = null, _.value = !1, ie());
		}), R;
	}
	async function le(n, r) {
		if (i.value) {
			V();
			try {
				let s = await e.detail(i.value, re.signal);
				if (!U(n) || r !== L) return;
				o.value = s.task;
				let c = s.task.runs || [];
				if (a.value && !c.some((e) => te(e.id, a.value))) {
					G(), p.value = `所选运行 #${a.value} 不存在或已不可用，请选择其他运行。`;
					return;
				}
				let l = a.value || s.task.last_run_id || c.at(-1)?.id || null, d = c.some((e) => te(e.id, l)) ? l : c.at(-1)?.id || null;
				if (d !== a.value && (G(), a.value = d), p.value = "", a.value && await Promise.allSettled([
					K(n),
					ae(),
					...u.value === "logs" ? [oe()] : []
				]), !U(n)) return;
				!J(s.task) && !B && (B = !0, t());
			} catch (e) {
				U(n) && (p.value = qe(e));
			}
		}
	}
	function ue(e, t, r) {
		return H(), n.value = !0, i.value = I(e), a.value = ne(t), o.value = null, p.value = "", u.value = "events", d.value = r || null, B = !1, G(), se();
	}
	function q() {
		n.value = !1, H();
	}
	function de(e) {
		if (e = I(e), !te(e, a.value)) return H(), a.value = e, d.value = null, G(), se();
	}
	function fe(e) {
		if (u.value = e, e === "logs") return oe();
	}
	function pe(e) {
		r.value !== e && (r.value = e, e ? n.value && se() : H());
	}
	return f(q), {
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
		open: ue,
		close: q,
		selectRun: de,
		selectTab: fe,
		setVisible: pe,
		refresh: se,
		loadEvents: ae,
		loadLogs: oe
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
		let t = e, r = E(() => !!(t.execution?.error_message || t.execution?.error_info)), i = E(() => (t.failure?.country_failures || []).filter((e) => V(e.country).trim())), a = E(() => {
			let e = t.failure;
			return e ? i.value.length && !e.error_info?.auto_refresh_at_failed ? `${i.value.length} 个国家查询失败，展开查看具体原因` : Te(e) : "";
		}), s = [
			"unknown",
			"complete",
			"result",
			"event",
			"queued"
		], c = E(() => {
			let e = t.failure;
			if (!e) return "";
			let n = e.stage?.replace(/_result$/, ""), r = e.error_info?.stage?.replace(/_result$/, ""), i = e.error_info?.auto_refresh_at_failed === !0, a = r === "preflight" && !!e.step_id && e.step_id !== "preflight";
			if (!i && !a && r && !s.includes(r) && r !== n) return G("stage", r);
			let o = e.label ? G("stage", e.label) || e.label : e.step_id ? G("stage", e.step_id) : "阶段记录缺失", c = i ? n && !s.includes(n) && n !== "refresh_token" ? n : r : n, l = c && !s.includes(c) && !(i && [
				"refresh_token",
				"plan_check",
				"plan_request",
				"extract_link",
				"extraction"
			].includes(c)) ? G("stage", c) : "";
			return l && l !== o ? `${o} · ${l}` : o;
		}), l = E(() => r.value ? oe(t.execution?.error_info, t.execution?.error_message) : ""), u = E(() => {
			if (!t.failure || !r.value) return !1;
			let e = (e) => V(e).replace(/\s+/g, " ").trim(), n = t.failure, i = n.error_info, a = t.execution?.error_info, o = e(n.message), s = e(t.execution?.error_message);
			if (o && s && o !== s) return !1;
			if (i?.cause_summary && a?.cause_summary) return e(i.cause_summary) === e(a.cause_summary);
			if (o && s) return o === s;
			let c = e(i?.cause_summary || i?.summary || n.message);
			return !!c && c === e(a?.cause_summary || a?.summary || t.execution?.error_message);
		}), d = E(() => ({
			...t.failure ? { failure: t.failure } : {},
			...r.value ? { execution: {
				error_message: t.execution?.error_message,
				error_info: t.execution?.error_info
			} } : {}
		}));
		return (t, s) => e.failure || r.value ? (n(), j("details", Ye, [
			S("summary", null, [
				e.failure ? (n(), j("strong", Xe, b(A(_e)(e.failure) ? "历史失败位置" : "失败位置") + "：" + b(c.value), 1)) : (n(), j("strong", Ze, "执行失败")),
				S("span", null, b(a.value || l.value), 1),
				e.failure && r.value && !u.value ? (n(), j("span", Qe, "执行错误：" + b(l.value), 1)) : p("", !0),
				e.execution?.error_info?.display_code ? (n(), j("small", $e, b(e.execution.error_info.display_code), 1)) : p("", !0)
			]),
			i.value.length ? (n(), j("ul", et, [(n(!0), j(g, null, o(i.value, (e, t) => (n(), j("li", { key: t }, b(e.country) + "：" + b(e.summary || "诊断记录不完整"), 1))), 128))])) : p("", !0),
			e.failure?.event_id ? (n(), j("p", tt, "关联事件 " + b(e.failure.event_id), 1)) : p("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(A(V)(e.status)) ? (n(), j("p", nt, "原请求证据已保留")) : p("", !0),
			S("pre", null, b(JSON.stringify(d.value, null, 2)), 1)
		])) : p("", !0);
	}
}), it = {
	key: 0,
	class: "tc-progress",
	"aria-label": "执行进度"
}, at = { class: "tc-progress-heading" }, ot = ["data-step-count"], st = [
	"aria-pressed",
	"title",
	"onClick"
], ct = { class: "tc-step-meta" }, lt = { key: 0 }, ut = {
	key: 0,
	class: "tc-step-deps"
}, dt = ["aria-label", "onClick"], ft = {
	key: 1,
	class: "tc-detail-muted"
}, pt = {
	key: 2,
	class: "tc-flow-relations"
}, mt = { class: "tc-flow-relations__count" }, ht = { class: "tc-flow-relations__panel" }, gt = { class: "tc-flow-relations__hint" }, _t = { class: "tc-flow-relations__grid" }, vt = { class: "tc-flow-relation__head" }, yt = { class: "tc-flow-relation__status" }, bt = {
	key: 3,
	class: "tc-child-tasks"
}, xt = ["onClick"], St = { id: "tc-step-title" }, Ct = { class: "tc-step-dialog-body" }, wt = /* @__PURE__ */ t({
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
		let a = t, s = r, c = E(() => a.progress?.main_steps || []), u = E(() => be(a.progress?.main_steps)), d = E(() => {
			let e = u.value.length;
			return e <= 1 ? 1 : e === 2 ? 2 : e === 3 ? 3 : e === 4 ? 4 : e === 5 ? 5 : e === 6 ? 3 : e <= 8 ? 4 : 5;
		}), f = v(null), m = E(() => c.value.find((e) => ke(e) === f.value)), h = v(), y = null, w = E(() => le(a.progress?.outcome?.child_tasks).flatMap((e) => {
			try {
				return [{
					...e,
					task_id: I(e.task_id),
					run_id: ne(e.run_id),
					task_type: e.task_type,
					status: e.status
				}];
			} catch {
				return [];
			}
		})), D = E(() => {
			let e = ve(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${Ae(V(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			if (!t) return "执行阶段";
			let n = t, r = V(n.label || n.step_id), i = V(n.state).toLowerCase();
			if (i === "success" || i === "skipped") {
				let e = V(n.next_label);
				return e ? `当前：已完成${r} · 正在进入${e}` : `当前：已完成${r} · 正在进入下一阶段`;
			}
			let o = V(n.child_label);
			return `当前：${r || "执行中"}${o ? ` · ${o}` : ""}`;
		}), O = E(() => a.progress?.source === "legacy_derived" ? "历史记录还原" : a.progress?.source === "insufficient_evidence" ? "无细分阶段记录" : "按实际执行顺序与依赖排列");
		function k(e) {
			return [
				q(e),
				ue(e),
				...ge(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function N(e) {
			return ke(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function P(t) {
			y = document.activeElement instanceof HTMLElement ? document.activeElement : null, f.value = ke(t), await e(), h.value?.open || h.value?.showModal();
		}
		function F() {
			h.value?.close(), f.value = null, y?.isConnected && y.focus({ preventScroll: !0 }), y = null;
		}
		function te(e) {
			let t = h.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i(() => [a.context, a.active], F), C(() => h.value?.close()), (e, r) => t.progress ? (n(), j("section", it, [
			S("div", at, [S("strong", null, b(D.value), 1), S("small", null, b(O.value), 1)]),
			u.value.length ? (n(), j("ul", {
				key: 0,
				class: "tc-progress-track",
				"data-step-count": u.value.length,
				style: _({ "--tc-step-cols": String(d.value) }),
				"aria-label": "执行阶段，排列不代表固定顺序"
			}, [(n(!0), j(g, null, o(u.value, (e) => (n(), j("li", {
				key: A(ke)(e),
				class: T([
					"tc-step",
					`tc-step--${A(Oe)(e)}`,
					{ "tc-step--selected": N(e) }
				])
			}, [S("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": N(e),
				title: k(e),
				onClick: (t) => s("filter", N(e) ? null : A(ke)(e))
			}, [
				r[2] ||= S("span", {
					class: "tc-step-dot",
					"aria-hidden": "true"
				}, null, -1),
				S("strong", null, b(A(q)(e)), 1),
				S("span", ct, [
					M(b(A(ue)(e)), 1),
					A(Ee)(e) == null ? p("", !0) : (n(), j("small", lt, " · " + b(A(B)(A(Ee)(e))), 1)),
					(n(!0), j(g, null, o(A(ge)(e), (e) => (n(), j("small", { key: e }, " · " + b(e), 1))), 128))
				]),
				A(Se)(e, c.value).length ? (n(), j("span", ut, [(n(!0), j(g, null, o(A(Se)(e, c.value), (e) => (n(), j("em", {
					key: e,
					class: "tc-step-dep-chip"
				}, b(e), 1))), 128))])) : p("", !0)
			], 8, st), S("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${A(q)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => P(e)
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
			})], -1)]], 8, dt)], 2))), 128))], 12, ot)) : (n(), j("p", ft, "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。")),
			c.value.length ? (n(), j("details", pt, [S("summary", null, [r[4] ||= S("span", { class: "tc-flow-relations__title" }, "依赖与完整阶段记录", -1), S("span", mt, b(c.value.length) + " 个阶段", 1)]), S("div", ht, [S("p", gt, b(t.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1), S("div", _t, [(n(!0), j(g, null, o(c.value, (e) => (n(), j("div", {
				key: A(ke)(e),
				class: "tc-flow-relation"
			}, [S("div", vt, [S("strong", null, b(A(q)(e)), 1), S("span", yt, b(A(ue)(e)), 1)]), l(ye, {
				step: e,
				siblings: c.value
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
			w.value.length ? (n(), j("div", bt, [r[5] ||= S("strong", null, "独立子任务", -1), (n(!0), j(g, null, o(w.value, (e) => (n(), j("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, b(A(G)("task_type", A(V)(e.task_type))) + " #" + b(e.task_id) + " · " + b(A(me)(e.status)), 9, xt))), 128))])) : p("", !0),
			S("dialog", {
				ref_key: "inspector",
				ref: h,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: ee(F, ["prevent"]),
				onClose: r[0] ||= (e) => f.value = null,
				onWheel: ee(te, ["stop"]),
				onClick: r[1] ||= (e) => {
					e.target === h.value && F();
				}
			}, [S("header", null, [S("h3", St, b(m.value ? A(q)(m.value) : "步骤详情"), 1), S("button", {
				type: "button",
				autofocus: "",
				onClick: F
			}, "关闭")]), S("div", Ct, [m.value ? (n(), x(we, {
				key: 0,
				step: m.value,
				siblings: c.value
			}, null, 8, ["step", "siblings"])) : p("", !0)])], 544)
		])) : p("", !0);
	}
}), Tt = { class: "tc-detail-header" }, Et = { id: "tc-detail-title" }, Dt = { key: 0 }, Ot = ["title"], kt = {
	key: 1,
	class: "tc-detail-run"
}, At = ["value", "disabled"], jt = ["value"], Mt = {
	key: 1,
	value: ""
}, Nt = ["value"], Pt = { class: "tc-detail-header-actions" }, Ft = ["disabled"], It = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Lt = { key: 0 }, Rt = ["disabled"], zt = {
	key: 1,
	class: "tc-detail-empty",
	role: "status"
}, Bt = {
	key: 0,
	class: "tc-detail-notice"
}, Vt = {
	key: 1,
	class: "tc-detail-notice"
}, Ht = {
	key: 3,
	class: "tc-detail-error",
	role: "status"
}, Ut = { class: "tc-detail-view-toolbar" }, Wt = [
	"id",
	"data-detail-tab",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], Gt = {
	key: 0,
	class: "tc-detail-read-toolbar"
}, Kt = ["aria-pressed", "disabled"], qt = ["aria-pressed", "disabled"], Jt = {
	id: "tc-detail-panel-events",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-events",
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
}, $t = { class: "tc-event-meta" }, en = ["data-level"], tn = { class: "tc-event-stage" }, nn = {
	key: 0,
	class: "tc-event-step"
}, rn = ["data-state"], an = { class: "tc-event-id" }, on = {
	key: 0,
	class: "tc-technical"
}, sn = ["disabled"], cn = {
	id: "tc-detail-panel-logs",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-logs",
	tabindex: "0"
}, ln = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, un = ["disabled"], dn = {
	key: 1,
	class: "tc-detail-notice"
}, fn = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, pn = ["data-level"], mn = { class: "tc-event-meta" }, hn = ["data-level"], gn = { class: "tc-log-stage" }, _n = {
	key: 0,
	class: "tc-technical"
}, vn = ["disabled"], yn = {
	id: "tc-detail-panel-artifacts",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-artifacts",
	tabindex: "0"
}, bn = {
	key: 0,
	class: "tc-artifact"
}, xn = { key: 0 }, Sn = { class: "tc-artifact-links" }, Cn = ["href"], wn = ["href"], Tn = ["href"], En = {
	key: 1,
	class: "tc-detail-empty"
}, Dn = {
	key: 2,
	class: "tc-technical"
}, On = { class: "tc-detail-footer" }, kn = {
	key: 1,
	role: "status"
}, An = /* @__PURE__ */ t({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(t, { expose: r, emit: c }) {
		let u = c, d = Je(void 0, () => u("refresh")), { opened: f, taskId: m, runId: h, task: _, runs: w, selectedRun: D, progress: O, events: N, logs: P, tab: F, stepFilter: I, error: ne, progressError: L, eventsError: R, logsError: z, loading: re, eventsLoading: H, logsLoading: U, eventsMode: W, logsMode: ae, eventsEarlier: oe, eventsMore: K, logsEarlier: ce, logsMore: le, logsAvailable: ue } = d, ge = v(), J = v(), Y = v(0), _e = Intl.DateTimeFormat().resolvedOptions().timeZone, ye = [
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
		], be = E(() => O.value?.main_steps || []), xe = E(() => be.value.find((e) => ke(e) === I.value || !!(I.value && e.raw_stages?.includes(I.value)))), Se = E(() => he(N.value.filter((e) => fe(e, I.value, be.value)))), we = E(() => P.value.filter((e) => fe(e, I.value, be.value, !0))), Te = E(() => Se.value.map((e) => {
			let t = de(e), n = pe(e.detail);
			return {
				event: e,
				state: t,
				timestamp: Ae(e.created_at),
				stageLabel: e.stage_label || G("stage", e.stage),
				association: Ie(e),
				stateLabel: t ? me(t) : "记录",
				detailJson: n ? JSON.stringify(n, null, 2) : null
			};
		})), Ee = E(() => we.value.map((e) => {
			let t = pe(e.fields);
			return {
				item: e,
				timestamp: e.ts ? Ae(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), Oe = E(() => h.value ? D.value : _.value), je = E(() => _.value?.email_snapshot || _.value?.email || (_.value?.account_id ? `账号 #${_.value.account_id}` : _.value?.target_id || "执行记录与诊断")), Me = E(() => (_.value?.resources || []).filter((e) => !h.value || te(e.run_id, h.value))), X = E(() => D.value?.debug_artifacts), Ne = E(() => ve(D.value?.debug_pause || O.value?.debug_pause)), Pe = null, Fe = !1;
		function Ie(e) {
			let t = ve(e.detail), n = V(e.main_step_id || t.main_step_id), r = V(e.raw_stage || t.raw_stage || e.stage), i = be.value.filter((e) => n ? ke(e) === n : e.raw_stages?.includes(r));
			if (i.length !== 1) {
				let t = V(e.event_id || e.id);
				if (t) {
					let e = be.value.filter((e) => se(e.event_ids).includes(t));
					e.length === 1 && (i = e);
				}
			}
			if (i.length !== 1 && (r === "nested_live_check" || (r === "remote_request" || r === "reconcile") && V(t.action) === "token_refresh")) {
				let e = be.value.find((e) => ke(e) === "refresh_token") || be.value.find((e) => ke(e) === "access_token") || be.value.find((e) => ke(e) === "authenticate");
				if (e) return q(e);
			}
			return i.length !== 1 && (r === "queued" || V(e.event_type).startsWith("run.")) ? "运行状态" : i.length === 1 ? q(i[0]) : "未关联步骤";
		}
		function Le() {
			f.value && (d.close(), Pe?.isConnected && Pe.focus({ preventScroll: !0 }), Pe = null, u("close"));
		}
		function Re() {
			ge.value?.close(), Le();
		}
		async function ze(t, n, r) {
			f.value || (Pe = document.activeElement instanceof HTMLElement ? document.activeElement : null), Y.value = 0, d.setVisible(!document.hidden);
			let i = d.open(t, n, r);
			return await e(), !ge.value?.open && f.value && ge.value?.showModal(), i;
		}
		function Be(e) {
			d.setVisible(e);
		}
		function Ve() {
			Be(!document.hidden);
		}
		function He(e) {
			Y.value = 0, d.selectRun(e.target.value);
		}
		async function Ue(t) {
			Y.value = 0, await d.selectTab(t), await e(), J.value && (J.value.scrollTop = 0);
		}
		function We(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			let t = ye.findIndex((e) => e.id === F.value), n = e.key === "Home" ? 0 : e.key === "End" ? ye.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + ye.length) % ye.length;
			e.preventDefault(), Ue(ye[n].id), e.currentTarget.querySelector(`[data-detail-tab="${ye[n].id}"]`)?.focus();
		}
		async function Ge(t) {
			Fe = !0, F.value === "events" ? await d.loadEvents(t) : await d.loadLogs(t), await e(), J.value && t !== "next" && (J.value.scrollTop = t === "tail" ? J.value.scrollHeight : 0), Y.value = 0, Fe = !1;
		}
		function Ke() {
			J.value && (J.value.scrollTop = J.value.scrollHeight), Y.value = 0;
		}
		function qe(e) {
			let t = J.value;
			ge.value && ge.value.scrollHeight > ge.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i([N, P], async ([t, n], [r, i]) => {
			if (Fe) return;
			let a = J.value, o = !a || a.scrollTop + a.clientHeight >= a.scrollHeight - 40, s = F.value === "events" ? t.length - r.length : F.value === "logs" ? n.length - i.length : 0;
			s <= 0 || (await e(), o ? Ke() : Y.value += s);
		}), i(I, () => {
			Y.value = 0, J.value && (J.value.scrollTop = 0);
		}), s(() => {
			Ve(), document.addEventListener("visibilitychange", Ve);
		}), C(() => {
			document.removeEventListener("visibilitychange", Ve), ge.value?.close();
		}), r({
			open: ze,
			close: Re,
			setVisible: Be
		}), (e, t) => (n(), x(y, { to: "body" }, [S("dialog", {
			ref_key: "dialog",
			ref: ge,
			class: "tc-detail-dialog",
			"aria-labelledby": "tc-detail-title",
			onCancel: ee(Re, ["prevent"]),
			onClose: Le,
			onWheel: qe
		}, [
			S("header", Tt, [
				S("h2", Et, [M("任务 #" + b(A(m)) + " ", 1), A(_) ? (n(), j("span", Dt, b(A(G)("task_type", A(_).task_type)), 1)) : p("", !0)]),
				S("span", {
					class: "tc-detail-target",
					title: String(je.value),
					tabindex: "0"
				}, b(je.value), 9, Ot),
				Oe.value ? (n(), j("div", {
					key: 0,
					class: T(["tc-detail-status", `tc-detail-status--${A(ie)(Oe.value.status)}`])
				}, [S("strong", null, b(A(G)("status", Oe.value.status)), 1), S("span", null, "耗时 " + b(A(B)(Oe.value.duration_ms)), 1)], 2)) : p("", !0),
				A(_) ? (n(), j("label", kt, [t[10] ||= S("span", null, "运行", -1), S("select", {
					value: A(h) || "",
					"aria-label": "选择执行实例",
					disabled: A(w).length < 2 && (!A(h) || !!A(D)),
					onChange: He
				}, [A(h) && !A(D) ? (n(), j("option", {
					key: 0,
					value: A(h),
					disabled: ""
				}, "运行 #" + b(A(h)) + " 不可用", 9, jt)) : A(w).length ? p("", !0) : (n(), j("option", Mt, "暂无运行")), (n(!0), j(g, null, o(A(w), (e) => (n(), j("option", {
					key: e.id,
					value: e.id
				}, "第 " + b(e.run_no || "—") + " 次 · " + b(A(G)("status", e.status)), 9, Nt))), 128))], 40, At)])) : p("", !0),
				S("div", Pt, [S("button", {
					type: "button",
					disabled: A(re),
					onClick: t[0] ||= (...e) => A(d).refresh && A(d).refresh(...e)
				}, b(A(re) ? "刷新中…" : "刷新"), 9, Ft), S("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Re
				}, "关闭")])
			]),
			A(ne) ? (n(), j("div", It, [
				M("读取任务失败：" + b(A(ne)), 1),
				A(_) ? (n(), j("span", Lt, "。保留上次已读取的记录。")) : p("", !0),
				S("button", {
					type: "button",
					disabled: A(re),
					onClick: t[1] ||= (...e) => A(d).refresh && A(d).refresh(...e)
				}, "重试", 8, Rt)
			])) : p("", !0),
			A(re) && !A(_) ? (n(), j("div", zt, "正在读取任务详情…")) : p("", !0),
			A(_) ? (n(), j(g, { key: 2 }, [
				Oe.value?.status === "queued" ? (n(), j("p", Bt, b(A(De)(Oe.value)), 1)) : p("", !0),
				Ne.value.state === "paused" ? (n(), j("p", Vt, [t[11] ||= M("调试暂停，等待结束调试。", -1), Ne.value.hold_until ? (n(), j(g, { key: 0 }, [M("保留至 " + b(A(Ae)(Ne.value.hold_until)) + "。", 1)], 64)) : p("", !0)])) : p("", !0),
				A(O) ? p("", !0) : (n(), x(rt, {
					key: 2,
					execution: Oe.value,
					status: Oe.value?.status
				}, null, 8, ["execution", "status"])),
				l(wt, {
					progress: A(O),
					"task-type": A(_)?.task_type,
					execution: Oe.value,
					filter: A(I),
					active: A(f),
					context: `${A(m)}:${A(h)}`,
					onFilter: t[2] ||= (e) => I.value = e,
					onChild: ze
				}, null, 8, [
					"progress",
					"task-type",
					"execution",
					"filter",
					"active",
					"context"
				]),
				A(L) ? (n(), j("p", Ht, [M("进度读取失败：" + b(A(L)), 1), A(O) ? (n(), j(g, { key: 0 }, [M("；保留上次快照")], 64)) : p("", !0)])) : p("", !0),
				S("div", Ut, [
					S("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: We
					}, [(n(), j(g, null, o(ye, (e) => S("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": A(F) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: A(F) === e.id ? 0 : -1,
						onClick: (t) => Ue(e.id)
					}, b(e.label), 9, Wt)), 64))], 32),
					S("div", { class: T(["tc-detail-filter", { "is-active": !!A(I) }]) }, [S("span", null, [t[12] ||= M("当前查看：", -1), S("strong", null, b(xe.value ? A(q)(xe.value) : A(I) || "全流程"), 1)]), A(I) ? (n(), j("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => I.value = null
					}, "清除步骤筛选")) : p("", !0)], 2),
					A(F) === "artifacts" ? p("", !0) : (n(), j("div", Gt, [S("button", {
						type: "button",
						"aria-pressed": (A(F) === "events" ? A(W) : A(ae)) === "start",
						disabled: A(H) || A(U) || !A(h),
						onClick: t[4] ||= (e) => Ge("start")
					}, "从头加载", 8, Kt), S("button", {
						type: "button",
						"aria-pressed": (A(F) === "events" ? A(W) : A(ae)) === "tail",
						disabled: A(H) || A(U) || !A(h),
						onClick: t[5] ||= (e) => Ge("tail")
					}, "最近记录", 8, qt)]))
				]),
				S("div", {
					ref_key: "scroller",
					ref: J,
					class: "tc-detail-content"
				}, [
					a(S("section", Jt, [
						A(R) ? (n(), j("p", Yt, [M("事件读取失败：" + b(A(R)), 1), S("button", {
							type: "button",
							disabled: A(H),
							onClick: t[6] ||= (e) => A(d).loadEvents()
						}, "重试", 8, Xt)])) : p("", !0),
						A(oe) ? (n(), j("p", Zt, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : p("", !0),
						Se.value.length ? p("", !0) : (n(), j("div", Qt, b(A(H) ? "正在读取事件…" : A(I) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(n(!0), j(g, null, o(Te.value, (e) => (n(), j("article", {
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
							S("div", $t, [
								S("time", null, b(e.timestamp), 1),
								S("span", {
									class: "tc-event-level",
									"data-level": (e.event.level || "INFO").toUpperCase()
								}, b(e.event.level || "INFO"), 9, en),
								S("strong", tn, b(e.stageLabel), 1),
								e.association ? (n(), j("span", nn, b(e.association), 1)) : p("", !0),
								S("span", {
									class: "tc-event-state",
									"data-state": e.state || "info"
								}, b(e.stateLabel), 9, rn),
								S("small", an, "事件 " + b(e.event.event_id || e.event.id), 1)
							]),
							S("p", null, b(e.event.message || "—"), 1),
							e.detailJson ? (n(), j("details", on, [t[13] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 2))), 128)),
						A(K) ? (n(), j("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: A(H),
							onClick: t[7] ||= (e) => Ge("next")
						}, b(A(H) ? "正在读取…" : "继续加载后续事件"), 9, sn)) : p("", !0)
					], 512), [[k, A(F) === "events"]]),
					a(S("section", cn, [
						A(z) ? (n(), j("p", ln, [M("日志读取失败：" + b(A(z)), 1), S("button", {
							type: "button",
							disabled: A(U),
							onClick: t[8] ||= (e) => A(d).loadLogs()
						}, "重试", 8, un)])) : p("", !0),
						A(ce) ? (n(), j("p", dn, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : p("", !0),
						we.value.length ? p("", !0) : (n(), j("div", fn, b(A(U) ? "正在读取运行日志…" : A(ue) ? A(I) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(n(!0), j(g, null, o(Ee.value, (e, r) => (n(), j("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${r}`,
							class: "tc-log-line",
							"data-level": (e.item.level || "INFO").toUpperCase()
						}, [
							S("div", mn, [
								S("time", null, b(e.timestamp), 1),
								S("strong", {
									class: "tc-log-level",
									"data-level": (e.item.level || "INFO").toUpperCase()
								}, b(e.item.level || "INFO"), 9, hn),
								S("span", gn, b(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							S("p", null, b(e.item.message), 1),
							e.detailJson ? (n(), j("details", _n, [t[14] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 8, pn))), 128)),
						A(le) ? (n(), j("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: A(U),
							onClick: t[9] ||= (e) => Ge("next")
						}, b(A(U) ? "正在读取…" : "继续加载后续日志"), 9, vn)) : p("", !0)
					], 512), [[k, A(F) === "logs"]]),
					a(S("section", yn, [
						X.value?.available ? (n(), j("article", bn, [
							t[15] ||= S("h3", null, "Roxy 刷新调试", -1),
							S("p", null, b(X.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + b(A(ve)(X.value.summary).request_count || 0) + " 条", 1),
							A(D)?.result_summary?.debug_browser_kept === !0 ? (n(), j("p", xn, "失败窗口已保留，可在 Roxy 中查看。")) : p("", !0),
							S("div", Sn, [
								A(Ce)(X.value.har_url) ? (n(), j("a", {
									key: 0,
									href: A(Ce)(X.value.har_url),
									download: ""
								}, "下载 HAR", 8, Cn)) : p("", !0),
								A(Ce)(X.value.page_state_url) ? (n(), j("a", {
									key: 1,
									href: A(Ce)(X.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, wn)) : p("", !0),
								A(Ce)(X.value.screenshot_url) ? (n(), j("a", {
									key: 2,
									href: A(Ce)(X.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, Tn)) : p("", !0)
							])
						])) : p("", !0),
						(n(!0), j(g, null, o(Me.value, (e, t) => (n(), j("article", {
							key: A(V)(e.id) || t,
							class: "tc-artifact"
						}, [
							S("h3", null, b(e.resource_type || "运行资源"), 1),
							S("p", null, b(e.provider || e.state || "—"), 1),
							S("small", null, b(A(Ae)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!X.value?.available && !Me.value.length ? (n(), j("div", En, "当前 Run 没有诊断资源或产物")) : p("", !0),
						Oe.value?.result_summary ? (n(), j("details", Dn, [t[16] ||= S("summary", null, "执行结果字段", -1), S("pre", null, b(JSON.stringify(Oe.value.result_summary, null, 2)), 1)])) : p("", !0)
					], 512), [[k, A(F) === "artifacts"]])
				], 512),
				S("footer", On, [S("small", null, "时间按浏览器时区显示 · " + b(A(_e)), 1), Y.value && A(F) !== "artifacts" ? (n(), j("button", {
					key: 0,
					type: "button",
					onClick: Ke
				}, "有 " + b(Y.value) + " 条新记录，回到底部", 1)) : A(re) || A(H) || A(U) ? (n(), j("small", kn, "正在同步记录…")) : p("", !0)])
			], 64)) : p("", !0)
		], 544)]));
	}
}), jn = [
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
function Mn(e, t) {
	return e.fields.some((e) => !!t[e]);
}
function Nn(e, t, n) {
	if (e.kind === "date-range") {
		let e = t.created_from, n = t.created_to;
		return e && n ? `创建日期 ${e} 至 ${n}` : e ? `创建日期自 ${e}` : n ? `创建日期截至 ${n}` : "";
	}
	let r = t[e.fields[0]];
	if (!r || e.kind !== "select") return r;
	let i = e.group || "", a = n[i] || [];
	return a.find((e) => e.value === r)?.label || r.split(",").map((e) => {
		let t = e.trim();
		return a.find((e) => e.value === t)?.label || G(i, t);
	}).join("、");
}
function Pn(e, t) {
	let n = { ...t };
	for (let t of e.fields) n[t] = "";
	return n;
}
// src/features/tasks/TaskFilterFields.vue?vue&type=script&setup=true&lang.ts
var Fn = {
	key: 0,
	class: "tc-filter-field"
}, In = ["for"], Ln = [
	"id",
	"value",
	"inputmode",
	"placeholder"
], Rn = ["aria-label"], zn = ["name", "checked"], Bn = { class: "tc-filter-option-label" }, Vn = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], Hn = { class: "tc-filter-option-label" }, Un = {
	key: 0,
	class: "tc-filter-option-count"
}, Wn = {
	key: 2,
	class: "tc-filter-date-range"
}, Gn = { class: "tc-filter-field" }, Kn = ["for"], qn = ["id", "value"], Jn = { class: "tc-filter-field" }, Yn = ["for"], Xn = ["id", "value"], Zn = { class: "tc-filter-footer" }, Qn = ["disabled"], $n = /* @__PURE__ */ t({
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
				...Object.keys(ae[e] || {}),
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
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? Nn(r.column, {
					...r.modelValue,
					[s.value]: t
				}, r.facets) : G(e, t)),
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
			i("update:modelValue", Pn(r.column, r.modelValue)), i("done");
		}
		return (t, r) => (n(), j("form", {
			class: "tc-filter-fields",
			onSubmit: r[5] ||= ee((e) => i("done"), ["prevent"])
		}, [e.column.kind === "search" ? (n(), j("div", Fn, [S("label", { for: `${A(a)}-search` }, b(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, In), S("input", {
			id: `${A(a)}-search`,
			value: c.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: r[0] ||= (e) => m(s.value, e.target.value)
		}, null, 40, Ln)])) : e.column.kind === "select" ? (n(), j("div", {
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
		}, null, 40, zn), S("span", Bn, b(l[e.column.group || ""] || "全部"), 1)], 2), (n(!0), j(g, null, o(f.value, (e) => (n(), j("label", {
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
			}, null, 40, Vn),
			S("span", Hn, b(e.text), 1),
			e.count == null ? p("", !0) : (n(), j("span", Un, b(e.count), 1))
		], 2))), 128))], 8, Rn)) : (n(), j("div", Wn, [
			r[6] ||= S("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			S("div", Gn, [S("label", { for: `${A(a)}-from` }, "创建日期起", 8, Kn), S("input", {
				id: `${A(a)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: r[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, qn)]),
			S("div", Jn, [S("label", { for: `${A(a)}-to` }, "创建日期止", 8, Yn), S("input", {
				id: `${A(a)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: r[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, Xn)])
		])), S("div", Zn, [S("button", {
			type: "button",
			class: "ui-link",
			disabled: !A(Mn)(e.column, e.modelValue),
			onClick: _
		}, "清除此列", 8, Qn), r[7] ||= S("button", {
			type: "submit",
			class: "ui-button"
		}, "完成", -1)])], 32));
	}
}), er = { class: "tc-mobile-filters" }, tr = { class: "tc-filter-column-picker" }, nr = ["value"], rr = /* @__PURE__ */ t({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = v(jn[0].key), u = E(() => jn.find((e) => e.key === c.value)), d = E(() => jn.filter((e) => Mn(e, i.modelValue)).length);
		return (t, i) => (n(), j("div", er, [l(je, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: e.open,
			"onUpdate:open": i[3] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [S("label", tr, [i[4] ||= M("筛选列", -1), a(S("select", { "onUpdate:modelValue": i[0] ||= (e) => c.value = e }, [(n(!0), j(g, null, o(A(jn), (t) => (n(), j("option", {
				key: t.key,
				value: t.key
			}, b(t.label) + b(A(Mn)(t, e.modelValue) ? " · 已筛选" : ""), 9, nr))), 128))], 512), [[m, c.value]])]), (n(), x($n, {
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
}), ir = /* @__PURE__ */ t({
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
		return (t, a) => (n(), x(je, {
			label: e.column.label,
			active: A(Mn)(e.column, e.modelValue),
			summary: A(Nn)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": a[2] ||= (e) => i("update:open", e)
		}, {
			default: r(() => [l($n, {
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
}), ar = /* @__PURE__ */ new Set([
	"failed",
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"password_confirmation_pending"
]), or = /* @__PURE__ */ new Set([
	"running",
	"waiting",
	"stopping",
	"cancelling",
	"settling"
]), sr = /* @__PURE__ */ new Set([
	"cancelled",
	"stopped",
	"interrupted"
]), cr = {
	email_verification_pending: "待验证或补全",
	credential_pending_confirmation: "凭证待核验"
};
function lr(e, t, n) {
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${G(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function ur(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function dr(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: G("status", t),
		tone: ie(t),
		title: lr("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = De(e) || void 0) : or.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = De(e) || ur(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : ar.has(t) ? (r.label = "失败", r.tone = "danger") : sr.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (ar.has(n) && ar.has(t) || n === "completed" && t === "success" || n === "in_progress" && or.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: cr[n] || G("target_status", n),
			tone: ie(n),
			title: lr("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Z = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), fr = (e) => Array.isArray(e) ? e.map(K) : [], Q = (e) => String(e || "").toLowerCase(), $ = /* @__PURE__ */ new Set([
	"unknown",
	"request_unknown",
	"attention_required",
	"manual_reconcile",
	"unconfirmed",
	"password_confirmation_pending",
	"credential_pending_confirmation"
]), pr = /* @__PURE__ */ new Set([
	"failed",
	"error",
	"deactivated"
]);
function mr(e) {
	let t = e.error_info;
	if (!t) return !1;
	for (let e of ["cause_code", "code"]) {
		let n = Q(t[e]).trim();
		if (n) {
			if ($.has(n) || ["unknown.unclassified", "task.pending"].includes(n) || /(?:_receipt_missing|_failure_diagnostics_missing|_evidence_missing|_unconfirmed|_request_unknown|\.confirmation|\.safety)$/.test(n)) return !1;
			if (Le({ [e]: n }) !== Le()) return !0;
		}
	}
	return !1;
}
var hr = {
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
}, gr = {
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
function _r(e, t) {
	let n = K(e.result_summary), r = Q(e.status), i = Q(n.extraction_status), a = Q(n.payment_status);
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
	].includes(r) ? Z("提链成功", "warning", "后续已中断") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Z("提链成功", "danger", "后续失败") : Z("提链成功", "success") : pr.has(i) || mr(e) ? Z(t, "danger") : $.has(i) ? Z("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Z("等待提链", "warning") : i === "running" ? Z("提链中", "active") : r === "cancelled" ? Z("已取消") : ["stopped", "interrupted"].includes(r) ? Z("执行已中断", "warning") : $.has(r) || $.has(Q(e.internal_status)) ? Z("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Z(t, "danger") : n.ok === !0 ? Z("提链流程完成", "success") : Z("提链结果缺失", "warning");
}
function vr(e, t) {
	let n = K(e.result_summary), r = Q(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : fr(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes(Q(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = K(e.result);
		return !t && !e.last_success_at ? [] : fr(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : fr(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(K(e.result)).length > 0);
	if (s > 0 && o > 0 || !i && n.plan_check_partial === !0) return Z("部分失败", "warning", u ? "含历史数据" : void 0);
	if (c > 0 && s >= c) return u ? Z("查询失败", "danger", "含历史数据") : Z(t, "danger");
	if (mr(e)) return Z(t, "danger");
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
		let e = p.plan === "plus" ? "Plus" : p.plan === "go" ? "Go" : p.plan === "team" ? "Team" : "", t = {
			free_trial: `${e}${p.plan === "team" ? "试用" : "免费"}`,
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
function yr(e, t = "执行异常") {
	let n = K(e.result_summary), r = Q(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
	if (e.debug_pause) return Z("调试已暂停", "warning");
	if (["queued", "pending"].includes(r)) {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(hr[String(t)] || "等待执行", "warning");
	}
	if (r === "waiting") {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Z(hr[String(t)] || ur(e), "warning");
	}
	if (r === "running") return Z("执行中", "active");
	if (["stopping", "cancelling"].includes(r)) return Z("正在停止", "warning");
	if (r === "settling") return Z("正在收尾", "active");
	if (i === "extract_link") return _r(e, a);
	if (i === "email_change" && n.email_change_confirmed === !0) return Z("邮箱已换绑", "success", K(n.post_change_live_check).accepted ? "刷新已排队" : "刷新待处理");
	if (i === "codex_retry" && n.ok === !0) {
		let e = Q(K(n.sub2api_sync).status);
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
	if (i === "plan_check") return vr(e, a);
	if (r === "cancelled") return Z("已取消");
	if (["stopped", "interrupted"].includes(r)) return Z("执行已中断", "warning");
	if (mr(e)) return Z(a, "danger");
	if ($.has(r) || $.has(Q(e.internal_status)) || $.has(Q(n.status))) return Z("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes(Q(e.target_status)) || r === "deactivated") return Z("账号已停用", "danger");
	let o = i === "sub2api_scan" || i === "c2a_scan";
	if (e.error_message || e.error_info || pr.has(r) || !o && n.ok === !1) return Z(a, "danger");
	if (r === "partial_success") return Z("部分完成", "warning");
	if (o) return r === "success" ? Z(i === "c2a_scan" && n.continuation_only === !0 ? "接续检查完成" : gr[i], "success") : Z("扫描未完成", "warning");
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
	return i === "deactivation_mail" && typeof n.detected == "boolean" ? Z(n.detected ? "发现封号邮件" : "未见封号邮件", n.detected ? "warning" : "neutral") : i === "live_check" && n.ok === !0 ? Z("账号正常", "success") : i === "token_refresh" && n.ok === !0 ? Z("令牌已刷新", "success") : i === "account_inspection_batch" && Number(n.failed_count) > 0 ? Z("巡检已完成", "warning", "存在失败") : r === "success" || n.ok === !0 ? Z(gr[i] || "任务已完成", "success") : Z("结果未记录");
}
// src/features/tasks/TaskResultCell.vue
var br = /* @__PURE__ */ t({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, i = E(() => yr(t.task, Le(t.task.error_info))), a = E(() => [...new Set([
			W(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? oe(t.task.error_info, t.task.error_message) : "",
			t.task.error_message,
			t.task.error_code,
			t.task.error_info?.code,
			t.task.error_info?.cause_code
		].filter((e) => !!e))]);
		return (e, t) => (n(), x(Ie, w(i.value, { title: a.value.join("\n") }), {
			details: r(() => [(n(!0), j(g, null, o(a.value, (e, t) => (n(), j("p", { key: t }, b(e), 1))), 128))]),
			_: 1
		}, 16, ["title"]));
	}
}), xr = ["aria-busy"], Sr = [
	"checked",
	"indeterminate",
	"disabled"
], Cr = {
	"data-label": "选择",
	class: "ui-col-check"
}, wr = [
	"checked",
	"aria-label",
	"onChange"
], Tr = { "data-label": "ID" }, Er = ["onClick"], Dr = { "data-label": "类型" }, Or = { "data-label": "目标" }, kr = { key: 0 }, Ar = {
	key: 1,
	class: "tc-muted-placeholder"
}, jr = {
	key: 1,
	class: "tc-muted-placeholder",
	"aria-label": "无目标"
}, Mr = { "data-label": "执行状态" }, Nr = ["title"], Pr = ["title"], Fr = { "data-label": "目标状态" }, Ir = ["title"], Lr = {
	key: 1,
	class: "tc-cell-line tc-muted-placeholder",
	"aria-label": "无额外目标状态"
}, Rr = { "data-label": "批次 / 触发" }, zr = ["onClick"], Br = { "data-label": "运行次数" }, Vr = { "data-label": "当前步骤" }, Hr = {
	"data-label": "创建 / 完成",
	class: "ui-time"
}, Ur = { "data-label": "结果 / 错误" }, Wr = { "data-label": "操作" }, Gr = { class: "ui-row-actions tc-row-actions" }, Kr = ["onClick"], qr = ["disabled", "onClick"], Jr = ["disabled", "onClick"], Yr = ["disabled", "onClick"], Xr = /* @__PURE__ */ t({
	__name: "TaskTable",
	props: {
		items: {},
		selected: {},
		loading: { type: Boolean },
		error: {},
		busy: { type: Boolean },
		filters: { default: Ve },
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
			...dr(e)
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
		], { widths: m, resize: h, resizeWithKeyboard: v, resetColumns: y } = Pe({
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
			return Y(e) || e.current_stage_label || G("stage", e.current_stage);
		}
		function D(e) {
			return [
				e.current_stage_label || G("stage", e.current_stage),
				Y(e),
				B(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function O(e) {
			return String(e.bulk_batch_id || K(e.bulk_context).batch_id || "");
		}
		function k(e) {
			return String(e.bulk_round_id || K(e.bulk_context).round_id || "");
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
			}, null, 40, Sr)) : (n(), j(g, { key: 1 }, [A(jn)[r - 1] ? (n(), x(ir, {
				key: 0,
				column: A(jn)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === A(jn)[r - 1].key,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:filters", e),
				"onUpdate:open": (e) => s("update:openFilter", e ? A(jn)[r - 1].key : null)
			}, null, 8, [
				"column",
				"model-value",
				"facets",
				"open",
				"onUpdate:open"
			])) : (n(), j(g, { key: 1 }, [M(b(t), 1)], 64)), r < f.length - 1 ? (n(), x(Fe, {
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
				S("td", Cr, [S("input", {
					type: "checkbox",
					checked: e.selected.has(t.id),
					"aria-label": `选择任务 #${t.id}`,
					onChange: (e) => s("select", t.id, e.target.checked)
				}, null, 40, wr)]),
				S("td", Tr, [S("button", {
					type: "button",
					class: "ui-link tc-task-id",
					onClick: (e) => s("detail", t.id)
				}, "#" + b(t.id), 9, Er)]),
				S("td", Dr, [l(X, { text: A(G)("task_type", t.task_type) }, null, 8, ["text"])]),
				S("td", Or, [C(t) || w(t) ? (n(), x(X, {
					key: 0,
					text: C(t) || "—",
					secondary: w(t) || void 0
				}, {
					default: r(() => [C(t) ? (n(), j("strong", kr, b(C(t)), 1)) : (n(), j("span", Ar, "—"))]),
					_: 2
				}, 1032, ["text", "secondary"])) : (n(), j("span", jr, "—"))]),
				S("td", Mr, [S("span", {
					class: T(["ui-badge tc-badge", `ui-badge--${i.tone}`]),
					title: i.title
				}, b(i.label), 11, Nr), i.secondary ? (n(), j("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: i.secondary
				}, b(i.secondary), 9, Pr)) : p("", !0)]),
				S("td", Fr, [a ? (n(), j("span", {
					key: 0,
					class: T(["ui-badge tc-badge", `ui-badge--${a.tone}`]),
					title: a.title
				}, b(a.label), 11, Ir)) : (n(), j("span", Lr, "—"))]),
				S("td", Rr, [l(X, {
					text: t.batch_title || t.batch_uuid || (O(t) ? "查看批次" : "单任务"),
					secondary: A(G)("trigger", t.trigger)
				}, {
					default: r(() => [O(t) ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: (e) => s("batch", O(t), k(t))
					}, b(t.batch_title || t.batch_uuid || "查看批次"), 9, zr)) : (n(), j(g, { key: 1 }, [M(b(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				S("td", Br, [l(X, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				S("td", Vr, [l(X, {
					text: ee(t),
					secondary: A(B)(t.duration_ms),
					title: D(t),
					tone: A(Y)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				S("td", Hr, [l(X, {
					text: A(Ae)(t.created_at),
					secondary: A(Ae)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				S("td", Ur, [l(br, { task: t }, null, 8, ["task"])]),
				S("td", Wr, [S("div", Gr, [
					S("button", {
						type: "button",
						class: "ui-link",
						onClick: (e) => s("detail", t.id)
					}, "详情", 8, Kr),
					A(ce)(t) ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						disabled: e.busy,
						onClick: (e) => s("action", t, "retry")
					}, "重跑", 8, qr)) : p("", !0),
					A(U)(t) ? (n(), j("button", {
						key: 1,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "terminate")
					}, b(t.status === "queued" ? "取消" : "终止"), 9, Jr)) : p("", !0),
					A(J)(t) ? p("", !0) : (n(), j("button", {
						key: 2,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "delete")
					}, "删除", 8, Yr))
				])])
			], 2))), 128)), e.items.length ? p("", !0) : (n(), x(Me, {
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
		], 4)], 8, xr));
	}
});
// src/features/tasks/useTaskList.ts
function Zr() {
	let t = c(Ve()), n = v(1), r = v(20), a = v(0), o = v([]), s = v({}), l = v(/* @__PURE__ */ new Set()), u = v(!1), d = v(""), p = v(!1), m = E(() => Math.max(1, Math.ceil(a.value / r.value))), h = 0, g = null, _, y, b = 0, x = 0, S = "", C = "", w = !1, ee = /* @__PURE__ */ new Set([
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
			...Ve(),
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
	let ne = () => {
		clearTimeout(_), document.hidden ? (++b, clearTimeout(y), g?.abort(), ++h, u.value = !1) : p.value && k();
	};
	return document.addEventListener("visibilitychange", ne), f(() => {
		++h, ++b, g?.abort(), clearTimeout(_), clearTimeout(y), document.removeEventListener("visibilitychange", ne);
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
// src/features/tasks/TaskCenter.vue?vue&type=script&setup=true&lang.ts
var Qr = {
	class: "tc-root",
	"aria-label": "统一任务中心"
}, $r = { class: "ui-list tc-workspace" }, ei = {
	class: "ui-list-count tc-count",
	role: "status"
}, ti = {
	class: "tc-target-search",
	role: "search"
}, ni = ["value", "onKeydown"], ri = {
	key: 0,
	class: "tc-selection",
	role: "status"
}, ii = {
	key: 1,
	class: "tc-bulk-actions",
	role: "group",
	"aria-label": "选中任务批量操作"
}, ai = ["disabled", "onClick"], oi = ["title"], si = ["disabled"], ci = ["role"], li = { key: 1 }, ui = /* @__PURE__ */ t({
	__name: "TaskCenter",
	emits: ["batch", "changed"],
	setup(t, { expose: s, emit: c }) {
		let u = c, f = Zr(), { filters: m, page: _, size: y, pages: x, total: w, items: D, facets: O, selected: N, loading: P, error: F, visible: I } = f, te = v(null), ne = v(null), L = v(!1), R = v(""), z = v(""), B = v(null), V = v(null), U = v(m.target || ""), W;
		i(() => m.target, (e) => {
			clearTimeout(W), U.value = e || "";
		}), C(() => clearTimeout(W)), i(B, (e) => {
			f.setFacetsVisible(e === "mobile" || jn.some((t) => t.key === e && t.kind === "select"));
		});
		let ie = E(() => jn.filter((e) => Mn(e, m))), G = E(() => ie.value.map((e) => ({
			key: e.key,
			label: `${e.label}：${Nn(e, m, O.value)}`,
			removeLabel: `清除${e.label}筛选`
		}))), ae = v([]), oe = E(() => D.value.filter((e) => N.value.has(e.id))), se = E(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, oe.value.filter((t) => H(t, e)).length]))), ce = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, le = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function ue(e) {
			Object.assign(m, e);
		}
		function q(e) {
			clearTimeout(W);
			let t = e.trim();
			t !== (m.target || "") && ue({
				...m,
				target: t
			});
		}
		function de(e) {
			U.value = e, clearTimeout(W), W = setTimeout(() => q(e), 250);
		}
		function fe() {
			clearTimeout(W), U.value = "", q(""), V.value?.focus();
		}
		function pe(e) {
			let t = jn.find((t) => t.key === e);
			t && ue(Pn(t, m));
		}
		function me(e, t, n) {
			te.value?.open(e, t, n);
		}
		async function he(t = {}) {
			t.filters && (t.taskId || te.value?.close?.(), f.applyFilters(t.filters)), t.taskId && (await e(), me(t.taskId, t.runId, t.stepId));
		}
		function ge(e) {
			e || (B.value = null), f.setVisible(e);
		}
		function Y() {
			te.value?.close();
		}
		async function _e(e = {}) {
			I.value && await f.refresh(e);
		}
		function ve() {
			_e(), u("changed");
		}
		async function ye(e, t) {
			if (!L.value && !(t === "delete" && J(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				L.value = !0, z.value = "", ae.value = [], R.value = "";
				try {
					let n = await Ke.action(e.id, t), r = K(n.data || n);
					R.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", N.value.delete(e.id), await _e(), u("changed");
				} catch (e) {
					z.value = `${ce[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					L.value = !1;
				}
			}
		}
		async function be(e) {
			if (L.value) return;
			let t = oe.value.filter((t) => H(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${ce[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				L.value = !0, z.value = "", R.value = "", ae.value = [];
				try {
					let n = t.map((e) => e.id), r = e === "terminate" ? await Ke.bulk(e, n, { onAccepted: (e) => {
						R.value = `终止请求已受理，正在等待结果（命令 ${e.command_id}）`;
					} }) : await Ke.bulk(e, n), i = Array.isArray(r.accepted) ? r.accepted : [];
					ae.value = (r.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let a = Number(r.accepted_count ?? i.length);
					if (e === "cancel") {
						let e = i.filter((e) => e.state === "cancelled").length, t = i.filter((e) => e.state === "cancelling").length;
						R.value = `已取消 ${e} 个，取消中 ${t} 个${a - e - t > 0 ? `，已受理 ${a - e - t} 个` : ""}`;
					} else R.value = `已${ce[e]} ${a} 个`;
					let o = new Set(i.map((e) => String(e.task_id)));
					N.value = new Set([...N.value].filter((e) => !o.has(String(e)))), ae.value.length && (R.value += `，跳过 ${ae.value.length} 个`), await _e(), u("changed");
				} catch (t) {
					z.value = t instanceof re ? t.message : `${ce[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					L.value = !1;
				}
			}
		}
		return s({
			open: he,
			refresh: _e,
			closeDetail: Y,
			setVisible: ge
		}), (e, t) => (n(), j(g, null, [a(S("section", Qr, [S("div", $r, [
			l(ze, { filtered: ie.value.length > 0 }, {
				actions: r(() => [
					l(rr, {
						"model-value": A(m),
						facets: A(O),
						open: B.value === "mobile",
						"onUpdate:modelValue": ue,
						"onUpdate:open": t[2] ||= (e) => B.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					ie.value.length ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: t[3] ||= (e) => A(f).applyFilters({})
					}, "清除全部筛选")) : p("", !0),
					S("span", {
						class: "tc-timezone",
						title: A(le)
					}, "时间按 " + b(A(le)) + " 显示", 9, oi),
					S("button", {
						type: "button",
						class: "ui-link",
						onClick: t[4] ||= (e) => ne.value?.resetColumns()
					}, "恢复列宽"),
					S("button", {
						id: "btnRefreshTasksV2",
						type: "button",
						class: "ui-button",
						disabled: A(P),
						onClick: t[5] ||= (e) => A(f).refresh()
					}, b(A(P) ? "刷新中…" : "刷新"), 9, si)
				]),
				default: r(() => [
					S("span", ei, b(A(w).toLocaleString()) + " 个任务", 1),
					S("div", ti, [S("input", {
						ref_key: "targetInput",
						ref: V,
						type: "search",
						value: U.value,
						placeholder: "搜索目标邮箱 / 账号...",
						"aria-label": "搜索任务目标",
						autocomplete: "off",
						onInput: t[0] ||= (e) => de(e.target.value),
						onKeydown: [t[1] ||= h(ee((e) => q(U.value), ["prevent"]), ["enter"]), h(ee(fe, ["prevent"]), ["esc"])]
					}, null, 40, ni), U.value ? (n(), j("button", {
						key: 0,
						type: "button",
						class: "tc-target-search__clear",
						"aria-label": "清空目标搜索",
						title: "清空目标搜索",
						onClick: fe
					}, "×")) : p("", !0)]),
					oe.value.length ? (n(), j("span", ri, "已选 " + b(oe.value.length) + " 项", 1)) : p("", !0),
					oe.value.length ? (n(), j("div", ii, [(n(), j(g, null, o([
						"retry",
						"cancel",
						"terminate",
						"delete"
					], (e) => S("button", {
						key: e,
						type: "button",
						class: T(["ui-button", { "ui-button--danger": e === "delete" || e === "terminate" }]),
						disabled: L.value || !se.value[e],
						onClick: (t) => be(e)
					}, b(ce[e]) + b(se.value[e] ? `（${se.value[e]}）` : ""), 11, ai)), 64))])) : p("", !0),
					l(Ne, {
						items: G.value,
						onRemove: pe
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			R.value || z.value || A(F) && A(D).length ? (n(), j("div", {
				key: 0,
				class: T(["ui-list-feedback tc-feedback", { "is-error": z.value || A(F) }]),
				role: z.value || A(F) ? "alert" : "status"
			}, [
				M(b(z.value || A(F) || R.value), 1),
				A(F) ? (n(), j("button", {
					key: 0,
					type: "button",
					class: "ui-link",
					onClick: t[6] ||= (e) => A(f).refresh()
				}, "重试")) : p("", !0),
				ae.value.length ? (n(), j("details", li, [t[12] ||= S("summary", null, "查看跳过原因", -1), S("ul", null, [(n(!0), j(g, null, o(ae.value, (e) => (n(), j("li", { key: e.id }, "#" + b(e.id) + "：" + b(e.message), 1))), 128))])])) : p("", !0)
			], 10, ci)) : p("", !0),
			l(Xr, {
				ref_key: "table",
				ref: ne,
				filters: A(m),
				facets: A(O),
				"open-filter": B.value,
				"onUpdate:openFilter": t[7] ||= (e) => B.value = e,
				"onUpdate:filters": ue,
				items: A(D),
				selected: A(N),
				loading: A(P),
				error: A(F),
				busy: L.value,
				onSelect: A(f).toggle,
				onSelectPage: A(f).togglePage,
				onDetail: me,
				onAction: ye,
				onBatch: t[8] ||= (e, t) => u("batch", e, t),
				onRetry: t[9] ||= (e) => A(f).refresh()
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
			l(Re, {
				page: A(_),
				"onUpdate:page": t[10] ||= (e) => d(_) ? _.value = e : null,
				size: A(y),
				"onUpdate:size": t[11] ||= (e) => d(y) ? y.value = e : null,
				pages: A(x),
				total: A(w),
				busy: A(P)
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy"
			])
		])], 512), [[k, A(I)]]), l(An, {
			ref_key: "detail",
			ref: te,
			onRefresh: ve
		}, null, 512)], 64));
	}
});
// src/main.ts
function di(e, t = {}) {
	return D(ui, t).mount(e);
}
export { di as mountTaskCenter };
