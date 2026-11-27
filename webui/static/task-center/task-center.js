import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, V as u, X as d, Z as f, _ as p, a as m, c as h, d as g, dt as _, et as v, f as y, ft as b, g as x, h as S, j as C, k as w, l as T, lt as E, m as D, n as O, nt as k, s as A, st as j, v as M, x as N } from "./_plugin-vue_export-helper-Btipf5Px.js";
import { n as P, r as F, t as I } from "./client-B5R_MNgP.js";
import { a as L, i as ee, n as te, r as R } from "./taskIds-BlchWwUp.js";
import { a as z, n as B, t as ne } from "./bulkMutations-3wwPI3-H.js";
import { A as V, C as H, D as U, E as W, F as re, I as ie, M as G, N as ae, O as oe, P as K, S as se, T as q, _ as ce, a as le, b as J, c as ue, d as de, f as fe, g as pe, h as me, i as he, j as Y, k as X, l as ge, m as _e, n as ve, o as ye, p as be, r as xe, s as Se, t as Ce, u as we, v as Te, w as Ee, x as De, y as Oe } from "./StepEvidence-iuzJIq8p.js";
import { n as ke } from "./time-DOD6oyhP.js";
import { i as Ae, n as je, r as Z, t as Me } from "./ListFilterSummary-41hWatme.js";
import { n as Ne, t as Pe } from "./ColumnResizer-Cxm2jUGa.js";
import { t as Fe } from "./ListResult-C60lPQ3j.js";
import { t as Ie } from "./errorLabels-Co3XCR-i.js";
import { t as Le } from "./ListPagination-CmqtjjEX.js";
import { t as Re } from "./ListToolbar-Bs-KwjyH.js";
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
		result: "",
		team_id: ""
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
	let n = v(!1), r = v(!0), i = v(null), a = v(null), o = k(null), s = k(null), c = k([]), l = k([]), u = v("events"), d = v(null), p = v(""), m = v(""), h = v(""), g = v(""), _ = v(!1), y = v(!1), b = v(!1), x = v(null), S = v(null), C = v("tail"), w = v("tail"), T = v(!1), E = v(!1), O = v(!1), A = v(!1), j = v(!0), M = D(() => o.value?.runs || []), N = D(() => M.value.find((e) => ee(e.id, a.value))), P = 0, F = 0, I = 0, R = 0, z = !1, B = !1, ne = !1, V = !1, H = null, U = null, W = null, re = null, ie = null, G, ae = new AbortController(), oe = !1;
	function K() {
		G !== void 0 && clearTimeout(G), G = void 0;
	}
	function se() {
		P += 1, ae.abort(), ae = new AbortController(), ie = null, z = B = !1, ne = V = !1, H = U = null, _.value = y.value = b.value = !1, K();
	}
	let q = (e) => e === P && n.value, ce = () => n.value && r.value && !!i.value;
	function le() {
		K(), ce() && (!o.value || Y(o.value)) && (G = setTimeout(() => void me(!0), 2e3));
	}
	function J() {
		F += 1, I += 1, z = B = !1, ne = V = !1, H = U = null, W = re = null, y.value = b.value = !1, s.value = null, m.value = h.value = g.value = "", c.value = [], l.value = [], x.value = S.value = null, T.value = E.value = O.value = A.value = !1, C.value = w.value = "tail", j.value = !0;
	}
	function ue(t = "incremental", n = !1) {
		if (!ce() || !a.value || !i.value) return;
		if (t === "incremental" && z) return ne ? (n || (y.value = !0), H || Promise.resolve()) : void 0;
		if (t === "incremental" && C.value === "start" && E.value || t === "next" && !E.value) return;
		let r = P, o = ++F, s = t === "tail" || t === "start" || x.value === null, l = {
			limit: 500,
			...t === "start" ? { after_id: 0 } : t !== "tail" && x.value !== null ? { after_id: x.value } : {}
		};
		return z = !0, ne = n, n || (y.value = !0), H = (async () => {
			try {
				let n = await e.events(i.value, a.value, l, ae.signal);
				if (!q(r) || o !== F) return;
				c.value = s ? n.items : be(c.value, n.items), x.value = n.next_after_id, W = a.value, (t === "tail" || t === "start") && (C.value = t), s && C.value === "tail" ? (T.value = n.has_more, E.value = !1) : (E.value = n.has_more, C.value === "start" && (T.value = !1)), h.value = "";
			} catch (e) {
				q(r) && o === F && (h.value = Ke(e));
			} finally {
				q(r) && o === F && (z = !1, ne = !1, H = null, y.value = !1);
			}
		})(), H;
	}
	function de(t = "incremental", n = !1) {
		if (!ce() || !a.value || !i.value) return;
		if (t === "incremental" && B) return V ? (n || (b.value = !0), U || Promise.resolve()) : void 0;
		if (t === "incremental" && w.value === "start" && A.value || t === "next" && !A.value) return;
		let r = P, o = ++I, s = t === "tail" || t === "start" || S.value === null, c = {
			limit: 500,
			...t === "start" ? { cursor: 0 } : t !== "tail" && S.value !== null ? { cursor: S.value } : {}
		};
		return B = !0, V = n, n || (b.value = !0), U = (async () => {
			try {
				let n = await e.logs(i.value, a.value, c, ae.signal);
				if (!q(r) || o !== I) return;
				l.value = s ? n.items : [...l.value, ...n.items], S.value = n.next_cursor, re = a.value, (t === "tail" || t === "start") && (w.value = t), A.value = n.has_more, O.value = w.value === "tail" && n.available, j.value = n.available, g.value = "";
			} catch (e) {
				q(r) && o === I && (g.value = Ke(e));
			} finally {
				q(r) && o === I && (B = !1, V = !1, U = null, b.value = !1);
			}
		})(), U;
	}
	async function fe(t) {
		if (i.value && a.value) try {
			let n = await e.progress(i.value, a.value, ae.signal);
			if (!q(t)) return;
			s.value = n.progress, m.value = "";
		} catch (e) {
			q(t) && (m.value = Ke(e));
		}
	}
	function pe() {
		return me(!1);
	}
	function me(e) {
		if (!ce() || !i.value) return Promise.resolve();
		if (e && o.value || (_.value = !0), ie) return ie;
		let t = P, n = ++R;
		return ie = he(t, n, e).finally(() => {
			q(t) && n === R && (ie = null, _.value = !1, le());
		}), ie;
	}
	async function he(n, r, s) {
		if (i.value) {
			K();
			try {
				let c = await e.detail(i.value, ae.signal);
				if (!q(n) || r !== R) return;
				o.value = c.task;
				let l = c.task.runs || [];
				if (a.value && !l.some((e) => ee(e.id, a.value))) {
					J(), p.value = `所选运行 #${a.value} 不存在或已不可用，请选择其他运行。`;
					return;
				}
				let d = a.value || c.task.last_run_id || l.at(-1)?.id || null, f = l.some((e) => ee(e.id, d)) ? d : l.at(-1)?.id || null;
				if (f !== a.value && (J(), a.value = f), p.value = "", a.value) {
					let e = s && ee(W, a.value), t = s && ee(re, a.value);
					await Promise.allSettled([
						fe(n),
						ue("incremental", e),
						...u.value === "logs" ? [de("incremental", t)] : []
					]);
				}
				if (!q(n)) return;
				!Y(c.task) && !oe && (oe = !0, t());
			} catch (e) {
				q(n) && (p.value = Ke(e));
			}
		}
	}
	function X(e, t, r) {
		return se(), n.value = !0, i.value = L(e), a.value = te(t), o.value = null, p.value = "", u.value = "events", d.value = r || null, oe = !1, J(), pe();
	}
	function ge() {
		n.value = !1, se();
	}
	function _e(e) {
		if (e = L(e), !ee(e, a.value)) return se(), a.value = e, d.value = null, J(), pe();
	}
	function ve(e) {
		if (u.value = e, e === "logs") return de();
	}
	function ye(e) {
		r.value !== e && (r.value = e, e ? n.value && me(!0) : se());
	}
	return f(ge), {
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
		open: X,
		close: ge,
		selectRun: _e,
		selectTab: ve,
		setVisible: ye,
		refresh: pe,
		loadEvents: ue,
		loadLogs: de
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
		let t = e, r = D(() => !!(t.execution?.error_message || t.execution?.error_info)), i = D(() => (t.failure?.country_failures || []).filter((e) => H(e.country).trim())), a = D(() => {
			let e = t.failure;
			return e ? i.value.length && !e.error_info?.auto_refresh_at_failed ? `${i.value.length} 个国家查询失败，展开查看具体原因` : we(e) : "";
		}), s = [
			"unknown",
			"complete",
			"result",
			"event",
			"queued"
		], c = D(() => {
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
		}), l = D(() => r.value ? oe(t.execution?.error_info, t.execution?.error_message) : ""), u = D(() => {
			if (!t.failure || !r.value) return !1;
			let e = (e) => H(e).replace(/\s+/g, " ").trim(), n = t.failure, i = n.error_info, a = t.execution?.error_info, o = e(n.message), s = e(t.execution?.error_message);
			if (o && s && o !== s) return !1;
			if (i?.cause_summary && a?.cause_summary) return e(i.cause_summary) === e(a.cause_summary);
			if (o && s) return o === s;
			let c = e(i?.cause_summary || i?.summary || n.message);
			return !!c && c === e(a?.cause_summary || a?.summary || t.execution?.error_message);
		}), d = D(() => ({
			...t.failure ? { failure: t.failure } : {},
			...r.value ? { execution: {
				error_message: t.execution?.error_message,
				error_info: t.execution?.error_info
			} } : {}
		}));
		return (t, s) => e.failure || r.value ? (n(), M("details", Je, [
			S("summary", null, [
				e.failure ? (n(), M("strong", Ye, b(j(ge)(e.failure) ? "历史失败位置" : "失败位置") + "：" + b(c.value), 1)) : (n(), M("strong", Xe, "执行失败")),
				S("span", null, b(a.value || l.value), 1),
				e.failure && r.value && !u.value ? (n(), M("span", Ze, "执行错误：" + b(l.value), 1)) : p("", !0),
				e.execution?.error_info?.display_code ? (n(), M("small", Qe, b(e.execution.error_info.display_code), 1)) : p("", !0)
			]),
			i.value.length ? (n(), M("ul", $e, [(n(!0), M(g, null, o(i.value, (e, t) => (n(), M("li", { key: t }, b(e.country) + "：" + b(e.summary || "诊断记录不完整"), 1))), 128))])) : p("", !0),
			e.failure?.event_id ? (n(), M("p", et, "关联事件 " + b(e.failure.event_id), 1)) : p("", !0),
			e.failure?.reconcile_required || ["request_unknown", "attention_required"].includes(j(H)(e.status)) ? (n(), M("p", tt, "原请求证据已保留")) : p("", !0),
			S("pre", null, b(JSON.stringify(d.value, null, 2)), 1)
		])) : p("", !0);
	}
}), rt = {
	key: 0,
	class: "tc-progress",
	"aria-label": "执行进度"
}, it = { class: "tc-progress-heading" }, at = ["data-step-count"], ot = [
	"aria-pressed",
	"title",
	"onClick"
], st = { class: "tc-step-meta" }, ct = { key: 0 }, lt = {
	key: 0,
	class: "tc-step-deps"
}, ut = ["aria-label", "onClick"], dt = {
	key: 1,
	class: "tc-detail-muted"
}, ft = {
	key: 2,
	class: "tc-flow-relations"
}, pt = { class: "tc-flow-relations__count" }, mt = { class: "tc-flow-relations__panel" }, ht = { class: "tc-flow-relations__hint" }, gt = { class: "tc-flow-relations__grid" }, _t = { class: "tc-flow-relation__head" }, vt = { class: "tc-flow-relation__status" }, yt = {
	key: 3,
	class: "tc-child-tasks"
}, bt = ["onClick"], xt = { id: "tc-step-title" }, St = { class: "tc-step-dialog-body" }, Ct = /* @__PURE__ */ t({
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
		let a = t, s = r, c = D(() => a.progress?.main_steps || []), u = D(() => ye(a.progress?.main_steps)), d = D(() => {
			let e = u.value.length;
			return e <= 1 ? 1 : e === 2 ? 2 : e === 3 ? 3 : e === 4 ? 4 : e === 5 ? 5 : e === 6 ? 3 : e <= 8 ? 4 : 5;
		}), f = v(null), m = D(() => c.value.find((e) => Oe(e) === f.value)), h = v(), y = null, w = D(() => ce(a.progress?.outcome?.child_tasks).flatMap((e) => {
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
		})), O = D(() => {
			let e = _e(a.progress?.debug_pause);
			if (e.state === "paused") return `调试暂停 · 等待结束调试${e.paused_at ? ` · ${ke(H(e.paused_at))}` : ""}`;
			let t = a.progress?.current;
			if (!t) return "执行阶段";
			let n = t, r = H(n.label || n.step_id), i = H(n.state).toLowerCase();
			if (i === "success" || i === "skipped") {
				let e = H(n.next_label);
				return e ? `当前：已完成${r} · 正在进入${e}` : `当前：已完成${r} · 正在进入下一阶段`;
			}
			let o = H(n.child_label);
			return `当前：${r || "执行中"}${o ? ` · ${o}` : ""}`;
		}), k = D(() => a.progress?.source === "legacy_derived" ? "历史记录还原" : a.progress?.source === "insufficient_evidence" ? "无细分阶段记录" : "按实际执行顺序与依赖排列");
		function A(e) {
			return [
				J(e),
				le(e),
				...he(e),
				e.reason || e.message,
				"点击筛选事件和日志"
			].filter(Boolean).join(" · ");
		}
		function P(e) {
			return Oe(e) === a.filter || !!(a.filter && e.raw_stages?.includes(a.filter));
		}
		async function F(t) {
			y = document.activeElement instanceof HTMLElement ? document.activeElement : null, f.value = Oe(t), await e(), h.value?.open || h.value?.showModal();
		}
		function I() {
			h.value?.close(), f.value = null, y?.isConnected && y.focus({ preventScroll: !0 }), y = null;
		}
		function ee(e) {
			let t = h.value?.querySelector(".tc-step-dialog-body");
			!t || e.ctrlKey || e.shiftKey || !e.deltaY || t.contains(e.target) || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i(() => [a.context, a.active], I), C(() => h.value?.close()), (e, r) => t.progress ? (n(), M("section", rt, [
			S("div", it, [S("strong", null, b(O.value), 1), S("small", null, b(k.value), 1)]),
			u.value.length ? (n(), M("ul", {
				key: 0,
				class: "tc-progress-track",
				"data-step-count": u.value.length,
				style: _({ "--tc-step-cols": String(d.value) }),
				"aria-label": "执行阶段，排列不代表固定顺序"
			}, [(n(!0), M(g, null, o(u.value, (e) => (n(), M("li", {
				key: j(Oe)(e),
				class: E([
					"tc-step",
					`tc-step--${j(De)(e)}`,
					{ "tc-step--selected": P(e) }
				])
			}, [S("button", {
				type: "button",
				class: "tc-step-select",
				"aria-pressed": P(e),
				title: A(e),
				onClick: (t) => s("filter", P(e) ? null : j(Oe)(e))
			}, [
				r[2] ||= S("span", {
					class: "tc-step-dot",
					"aria-hidden": "true"
				}, null, -1),
				S("strong", null, b(j(J)(e)), 1),
				S("span", st, [
					N(b(j(le)(e)), 1),
					j(Te)(e) == null ? p("", !0) : (n(), M("small", ct, " · " + b(j(V)(j(Te)(e))), 1)),
					(n(!0), M(g, null, o(j(he)(e), (e) => (n(), M("small", { key: e }, " · " + b(e), 1))), 128))
				]),
				j(xe)(e, c.value).length ? (n(), M("span", lt, [(n(!0), M(g, null, o(j(xe)(e, c.value), (e) => (n(), M("em", {
					key: e,
					class: "tc-step-dep-chip"
				}, b(e), 1))), 128))])) : p("", !0)
			], 8, ot), S("button", {
				type: "button",
				class: "tc-step-inspect",
				"aria-label": `查看${j(J)(e)}的时间、阶段事件与子步骤`,
				title: "查看阶段关系与证据",
				"aria-haspopup": "dialog",
				onClick: (t) => F(e)
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
			})], -1)]], 8, ut)], 2))), 128))], 12, at)) : (n(), M("p", dt, "此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。")),
			c.value.length ? (n(), M("details", ft, [S("summary", null, [r[4] ||= S("span", { class: "tc-flow-relations__title" }, "依赖与完整阶段记录", -1), S("span", pt, b(c.value.length) + " 个阶段", 1)]), S("div", mt, [S("p", ht, b(t.progress.structure?.parallelism === "explicit" ? "并行分组来自执行记录；依赖关系单独显示。" : "已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。"), 1), S("div", gt, [(n(!0), M(g, null, o(c.value, (e) => (n(), M("div", {
				key: j(Oe)(e),
				class: "tc-flow-relation"
			}, [S("div", _t, [S("strong", null, b(j(J)(e)), 1), S("span", vt, b(j(le)(e)), 1)]), l(ve, {
				step: e,
				siblings: c.value
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
			w.value.length ? (n(), M("div", yt, [r[5] ||= S("strong", null, "独立子任务", -1), (n(!0), M(g, null, o(w.value, (e) => (n(), M("button", {
				key: e.task_id,
				type: "button",
				onClick: (t) => s("child", e.task_id, e.run_id)
			}, b(j(G)("task_type", j(H)(e.task_type))) + " #" + b(e.task_id) + " · " + b(j(pe)(e.status)), 9, bt))), 128))])) : p("", !0),
			S("dialog", {
				ref_key: "inspector",
				ref: h,
				class: "tc-step-dialog",
				"aria-labelledby": "tc-step-title",
				onCancel: T(I, ["prevent"]),
				onClose: r[0] ||= (e) => f.value = null,
				onWheel: T(ee, ["stop"]),
				onClick: r[1] ||= (e) => {
					e.target === h.value && I();
				}
			}, [S("header", null, [S("h3", xt, b(m.value ? j(J)(m.value) : "步骤详情"), 1), S("button", {
				type: "button",
				autofocus: "",
				onClick: I
			}, "关闭")]), S("div", St, [m.value ? (n(), x(Ce, {
				key: 0,
				step: m.value,
				siblings: c.value
			}, null, 8, ["step", "siblings"])) : p("", !0)])], 544)
		])) : p("", !0);
	}
}), wt = { class: "tc-detail-header" }, Tt = { id: "tc-detail-title" }, Et = { key: 0 }, Dt = ["title"], Ot = {
	key: 1,
	class: "tc-detail-run"
}, kt = ["value", "disabled"], At = ["value"], jt = {
	key: 1,
	value: ""
}, Mt = ["value"], Nt = { class: "tc-detail-header-actions" }, Pt = ["disabled"], Ft = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, It = { key: 0 }, Lt = ["disabled"], Rt = {
	key: 1,
	class: "tc-detail-empty",
	role: "status"
}, zt = {
	key: 0,
	class: "tc-detail-notice"
}, Bt = {
	key: 1,
	class: "tc-detail-notice"
}, Vt = {
	key: 3,
	class: "tc-detail-error",
	role: "status"
}, Ht = { class: "tc-detail-view-toolbar" }, Ut = [
	"id",
	"data-detail-tab",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], Wt = {
	key: 0,
	class: "tc-detail-read-toolbar"
}, Gt = ["aria-pressed", "disabled"], Kt = ["aria-pressed", "disabled"], qt = {
	id: "tc-detail-panel-events",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-events",
	tabindex: "0"
}, Jt = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, Yt = ["disabled"], Xt = {
	key: 1,
	class: "tc-detail-notice"
}, Zt = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, Qt = { class: "tc-event-meta" }, $t = ["data-level"], en = { class: "tc-event-stage" }, tn = {
	key: 0,
	class: "tc-event-step"
}, nn = ["data-state"], rn = { class: "tc-event-id" }, an = {
	key: 0,
	class: "tc-technical"
}, on = ["disabled"], sn = {
	id: "tc-detail-panel-logs",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-logs",
	tabindex: "0"
}, cn = {
	key: 0,
	class: "tc-detail-error",
	role: "alert"
}, ln = ["disabled"], un = {
	key: 1,
	class: "tc-detail-notice"
}, dn = {
	key: 2,
	class: "tc-detail-empty",
	role: "status"
}, fn = ["data-level"], pn = { class: "tc-event-meta" }, mn = ["data-level"], hn = { class: "tc-log-stage" }, gn = {
	key: 0,
	class: "tc-technical"
}, _n = ["disabled"], vn = {
	id: "tc-detail-panel-artifacts",
	role: "tabpanel",
	"aria-labelledby": "tc-detail-tab-artifacts",
	tabindex: "0"
}, yn = {
	key: 0,
	class: "tc-artifact"
}, bn = { key: 0 }, xn = { class: "tc-artifact-links" }, Sn = ["href"], Cn = ["href"], wn = ["href"], Tn = {
	key: 1,
	class: "tc-detail-empty"
}, En = {
	key: 2,
	class: "tc-technical"
}, Dn = { class: "tc-detail-footer" }, On = {
	key: 1,
	role: "status"
}, kn = /* @__PURE__ */ t({
	__name: "TaskDetail",
	emits: ["close", "refresh"],
	setup(t, { expose: r, emit: c }) {
		let u = c, d = qe(void 0, () => u("refresh")), { opened: f, taskId: m, runId: h, task: _, runs: w, selectedRun: O, progress: k, events: P, logs: F, tab: I, stepFilter: L, error: te, progressError: R, eventsError: z, logsError: B, loading: ne, eventsLoading: U, logsLoading: W, eventsMode: re, logsMode: ae, eventsEarlier: oe, eventsMore: K, logsEarlier: q, logsMore: ce, logsAvailable: le } = d, he = v(), Y = v(), X = v(0), ge = Intl.DateTimeFormat().resolvedOptions().timeZone, ve = [
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
		], ye = D(() => k.value?.main_steps || []), be = D(() => ye.value.find((e) => Oe(e) === L.value || !!(L.value && e.raw_stages?.includes(L.value)))), xe = D(() => me(P.value.filter((e) => de(e, L.value, ye.value)))), Ce = D(() => F.value.filter((e) => de(e, L.value, ye.value, !0))), we = D(() => xe.value.map((e) => {
			let t = ue(e), n = fe(e.detail);
			return {
				event: e,
				state: t,
				timestamp: ke(e.created_at),
				stageLabel: e.stage_label || G("stage", e.stage),
				association: Fe(e),
				stateLabel: t ? pe(t) : "记录",
				detailJson: n ? JSON.stringify(n, null, 2) : null
			};
		})), Te = D(() => Ce.value.map((e) => {
			let t = fe(e.fields);
			return {
				item: e,
				timestamp: e.ts ? ke(e.ts) : "时间缺失",
				detailJson: t ? JSON.stringify(t, null, 2) : null
			};
		})), De = D(() => h.value ? O.value : _.value), Ae = D(() => _.value?.email_snapshot || _.value?.email || (_.value?.account_id ? `账号 #${_.value.account_id}` : _.value?.target_id || "执行记录与诊断")), je = D(() => (_.value?.resources || []).filter((e) => !h.value || ee(e.run_id, h.value))), Z = D(() => O.value?.debug_artifacts), Me = D(() => _e(O.value?.debug_pause || k.value?.debug_pause)), Ne = null, Pe = !1;
		function Fe(e) {
			let t = _e(e.detail), n = H(e.main_step_id || t.main_step_id), r = H(e.raw_stage || t.raw_stage || e.stage), i = ye.value.filter((e) => n ? Oe(e) === n : e.raw_stages?.includes(r));
			if (i.length !== 1) {
				let t = H(e.event_id || e.id);
				if (t) {
					let e = ye.value.filter((e) => se(e.event_ids).includes(t));
					e.length === 1 && (i = e);
				}
			}
			if (i.length !== 1 && (r === "nested_live_check" || (r === "remote_request" || r === "reconcile") && H(t.action) === "token_refresh")) {
				let e = ye.value.find((e) => Oe(e) === "refresh_token") || ye.value.find((e) => Oe(e) === "access_token") || ye.value.find((e) => Oe(e) === "authenticate");
				if (e) return J(e);
			}
			return i.length !== 1 && (r === "queued" || H(e.event_type).startsWith("run.")) ? "运行状态" : i.length === 1 ? J(i[0]) : "未关联步骤";
		}
		function Ie() {
			f.value && (d.close(), Ne?.isConnected && Ne.focus({ preventScroll: !0 }), Ne = null, u("close"));
		}
		function Le() {
			he.value?.close(), Ie();
		}
		async function Re(t, n, r) {
			f.value || (Ne = document.activeElement instanceof HTMLElement ? document.activeElement : null), X.value = 0, d.setVisible(!document.hidden);
			let i = d.open(t, n, r);
			return await e(), !he.value?.open && f.value && he.value?.showModal(), i;
		}
		function ze(e) {
			d.setVisible(e);
		}
		function Be() {
			ze(!document.hidden);
		}
		function Ve(e) {
			X.value = 0, d.selectRun(e.target.value);
		}
		async function He(t) {
			X.value = 0, await d.selectTab(t), await e(), Y.value && (Y.value.scrollTop = 0);
		}
		function Ue(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			let t = ve.findIndex((e) => e.id === I.value), n = e.key === "Home" ? 0 : e.key === "End" ? ve.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + ve.length) % ve.length;
			e.preventDefault(), He(ve[n].id), e.currentTarget.querySelector(`[data-detail-tab="${ve[n].id}"]`)?.focus();
		}
		async function We(t) {
			Pe = !0, I.value === "events" ? await d.loadEvents(t) : await d.loadLogs(t), await e(), Y.value && t !== "next" && (Y.value.scrollTop = t === "tail" ? Y.value.scrollHeight : 0), X.value = 0, Pe = !1;
		}
		function Ge() {
			Y.value && (Y.value.scrollTop = Y.value.scrollHeight), X.value = 0;
		}
		function Ke(e) {
			let t = Y.value;
			he.value && he.value.scrollHeight > he.value.clientHeight + 1 || e.defaultPrevented || e.target instanceof Element && e.target.closest(".tc-step-dialog") || !t || e.ctrlKey || e.shiftKey || t.contains(e.target) || !e.deltaY || t.scrollHeight <= t.clientHeight || (e.preventDefault(), t.scrollTop += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? t.clientHeight : 1));
		}
		return i([P, F], async ([t, n], [r, i]) => {
			if (Pe) return;
			let a = Y.value, o = !a || a.scrollTop + a.clientHeight >= a.scrollHeight - 40, s = I.value === "events" ? t.length - r.length : I.value === "logs" ? n.length - i.length : 0;
			s <= 0 || (await e(), o ? Ge() : X.value += s);
		}), i(L, () => {
			X.value = 0, Y.value && (Y.value.scrollTop = 0);
		}), s(() => {
			Be(), document.addEventListener("visibilitychange", Be);
		}), C(() => {
			document.removeEventListener("visibilitychange", Be), he.value?.close();
		}), r({
			open: Re,
			close: Le,
			setVisible: ze
		}), (e, t) => (n(), x(y, { to: "body" }, [S("dialog", {
			ref_key: "dialog",
			ref: he,
			class: "tc-detail-dialog",
			"aria-labelledby": "tc-detail-title",
			onCancel: T(Le, ["prevent"]),
			onClose: Ie,
			onWheel: Ke
		}, [
			S("header", wt, [
				S("h2", Tt, [N("任务 #" + b(j(m)) + " ", 1), j(_) ? (n(), M("span", Et, b(j(G)("task_type", j(_).task_type)), 1)) : p("", !0)]),
				S("span", {
					class: "tc-detail-target",
					title: String(Ae.value),
					tabindex: "0"
				}, b(Ae.value), 9, Dt),
				De.value ? (n(), M("div", {
					key: 0,
					class: E(["tc-detail-status", `tc-detail-status--${j(ie)(De.value.status)}`])
				}, [S("strong", null, b(j(G)("status", De.value.status)), 1), S("span", null, "耗时 " + b(j(V)(De.value.duration_ms)), 1)], 2)) : p("", !0),
				j(_) ? (n(), M("label", Ot, [t[10] ||= S("span", null, "运行", -1), S("select", {
					value: j(h) || "",
					"aria-label": "选择执行实例",
					disabled: j(w).length < 2 && (!j(h) || !!j(O)),
					onChange: Ve
				}, [j(h) && !j(O) ? (n(), M("option", {
					key: 0,
					value: j(h),
					disabled: ""
				}, "运行 #" + b(j(h)) + " 不可用", 9, At)) : j(w).length ? p("", !0) : (n(), M("option", jt, "暂无运行")), (n(!0), M(g, null, o(j(w), (e) => (n(), M("option", {
					key: e.id,
					value: e.id
				}, "第 " + b(e.run_no || "—") + " 次 · " + b(j(G)("status", e.status)), 9, Mt))), 128))], 40, kt)])) : p("", !0),
				S("div", Nt, [S("button", {
					type: "button",
					class: "ui-refresh-button",
					disabled: j(ne),
					onClick: t[0] ||= (...e) => j(d).refresh && j(d).refresh(...e)
				}, b(j(ne) ? "刷新中…" : "刷新"), 9, Pt), S("button", {
					type: "button",
					autofocus: "",
					"aria-label": "关闭任务详情",
					onClick: Le
				}, "关闭")])
			]),
			j(te) ? (n(), M("div", Ft, [
				N("读取任务失败：" + b(j(te)), 1),
				j(_) ? (n(), M("span", It, "。保留上次已读取的记录。")) : p("", !0),
				S("button", {
					type: "button",
					disabled: j(ne),
					onClick: t[1] ||= (...e) => j(d).refresh && j(d).refresh(...e)
				}, "重试", 8, Lt)
			])) : p("", !0),
			j(ne) && !j(_) ? (n(), M("div", Rt, "正在读取任务详情…")) : p("", !0),
			j(_) ? (n(), M(g, { key: 2 }, [
				De.value?.status === "queued" ? (n(), M("p", zt, b(j(Ee)(De.value)), 1)) : p("", !0),
				Me.value.state === "paused" ? (n(), M("p", Bt, [t[11] ||= N("调试暂停，等待结束调试。", -1), Me.value.hold_until ? (n(), M(g, { key: 0 }, [N("保留至 " + b(j(ke)(Me.value.hold_until)) + "。", 1)], 64)) : p("", !0)])) : p("", !0),
				j(k) ? p("", !0) : (n(), x(nt, {
					key: 2,
					execution: De.value,
					status: De.value?.status
				}, null, 8, ["execution", "status"])),
				l(Ct, {
					progress: j(k),
					"task-type": j(_)?.task_type,
					execution: De.value,
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
				j(R) ? (n(), M("p", Vt, [N("进度读取失败：" + b(j(R)), 1), j(k) ? (n(), M(g, { key: 0 }, [N("；保留上次快照")], 64)) : p("", !0)])) : p("", !0),
				S("div", Ht, [
					S("div", {
						class: "tc-detail-tabs",
						role: "tablist",
						"aria-label": "任务详情视图",
						onKeydown: Ue
					}, [(n(), M(g, null, o(ve, (e) => S("button", {
						id: `tc-detail-tab-${e.id}`,
						key: e.id,
						type: "button",
						role: "tab",
						"data-detail-tab": e.id,
						"aria-selected": j(I) === e.id,
						"aria-controls": `tc-detail-panel-${e.id}`,
						tabindex: j(I) === e.id ? 0 : -1,
						onClick: (t) => He(e.id)
					}, b(e.label), 9, Ut)), 64))], 32),
					S("div", { class: E(["tc-detail-filter", { "is-active": !!j(L) }]) }, [S("span", null, [t[12] ||= N("当前查看：", -1), S("strong", null, b(be.value ? j(J)(be.value) : j(L) || "全流程"), 1)]), j(L) ? (n(), M("button", {
						key: 0,
						type: "button",
						onClick: t[3] ||= (e) => L.value = null
					}, "清除步骤筛选")) : p("", !0)], 2),
					j(I) === "artifacts" ? p("", !0) : (n(), M("div", Wt, [S("button", {
						type: "button",
						"aria-pressed": (j(I) === "events" ? j(re) : j(ae)) === "start",
						disabled: j(U) || j(W) || !j(h),
						onClick: t[4] ||= (e) => We("start")
					}, "从头加载", 8, Gt), S("button", {
						type: "button",
						"aria-pressed": (j(I) === "events" ? j(re) : j(ae)) === "tail",
						disabled: j(U) || j(W) || !j(h),
						onClick: t[5] ||= (e) => We("tail")
					}, "最近记录", 8, Kt)]))
				]),
				S("div", {
					ref_key: "scroller",
					ref: Y,
					class: "tc-detail-content"
				}, [
					a(S("section", qt, [
						j(z) ? (n(), M("p", Jt, [N("事件读取失败：" + b(j(z)), 1), S("button", {
							type: "button",
							disabled: j(U),
							onClick: t[6] ||= (e) => j(d).loadEvents()
						}, "重试", 8, Yt)])) : p("", !0),
						j(oe) ? (n(), M("p", Xt, "当前展示最近记录；更早历史可通过“从头加载”读取。")) : p("", !0),
						xe.value.length ? p("", !0) : (n(), M("div", Zt, b(j(U) ? "正在读取事件…" : j(L) ? "当前步骤暂无关联事件" : "此运行暂无事件"), 1)),
						(n(!0), M(g, null, o(we.value, (e) => (n(), M("article", {
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
							S("div", Qt, [
								S("time", null, b(e.timestamp), 1),
								S("span", {
									class: "tc-event-level",
									"data-level": (e.event.level || "INFO").toUpperCase()
								}, b(e.event.level || "INFO"), 9, $t),
								S("strong", en, b(e.stageLabel), 1),
								e.association ? (n(), M("span", tn, b(e.association), 1)) : p("", !0),
								S("span", {
									class: "tc-event-state",
									"data-state": e.state || "info"
								}, b(e.stateLabel), 9, nn),
								S("small", rn, "事件 " + b(e.event.event_id || e.event.id), 1)
							]),
							S("p", null, b(e.event.message || "—"), 1),
							e.detailJson ? (n(), M("details", an, [t[13] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 2))), 128)),
						j(K) ? (n(), M("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: j(U),
							onClick: t[7] ||= (e) => We("next")
						}, b(j(U) ? "正在读取…" : "继续加载后续事件"), 9, on)) : p("", !0)
					], 512), [[A, j(I) === "events"]]),
					a(S("section", sn, [
						j(B) ? (n(), M("p", cn, [N("日志读取失败：" + b(j(B)), 1), S("button", {
							type: "button",
							disabled: j(W),
							onClick: t[8] ||= (e) => j(d).loadLogs()
						}, "重试", 8, ln)])) : p("", !0),
						j(q) ? (n(), M("p", un, "正在查看文件尾部；“从头加载”将按顺序分页读取。")) : p("", !0),
						Ce.value.length ? p("", !0) : (n(), M("div", dn, b(j(W) ? "正在读取运行日志…" : j(le) ? j(L) ? "当前步骤暂无关联运行日志" : "此运行暂无日志" : "当前 Run 暂无技术日志，历史任务可能只有事件时间线"), 1)),
						(n(!0), M(g, null, o(Te.value, (e, r) => (n(), M("article", {
							key: `${e.item.event_uuid || e.item.event_id || ""}:${e.item.ts}:${r}`,
							class: "tc-log-line",
							"data-level": (e.item.level || "INFO").toUpperCase()
						}, [
							S("div", pn, [
								S("time", null, b(e.timestamp), 1),
								S("strong", {
									class: "tc-log-level",
									"data-level": (e.item.level || "INFO").toUpperCase()
								}, b(e.item.level || "INFO"), 9, mn),
								S("span", hn, b(e.item.stage_label || e.item.stage || "未关联步骤"), 1)
							]),
							S("p", null, b(e.item.message), 1),
							e.detailJson ? (n(), M("details", gn, [t[14] ||= S("summary", null, "技术详情", -1), S("pre", null, b(e.detailJson), 1)])) : p("", !0)
						], 8, fn))), 128)),
						j(ce) ? (n(), M("button", {
							key: 3,
							class: "tc-load-more",
							type: "button",
							disabled: j(W),
							onClick: t[9] ||= (e) => We("next")
						}, b(j(W) ? "正在读取…" : "继续加载后续日志"), 9, _n)) : p("", !0)
					], 512), [[A, j(I) === "logs"]]),
					a(S("section", vn, [
						Z.value?.available ? (n(), M("article", yn, [
							t[15] ||= S("h3", null, "Roxy 刷新调试", -1),
							S("p", null, b(Z.value.state === "recording" ? "正在抓包" : "诊断已保存") + " · 请求 " + b(j(_e)(Z.value.summary).request_count || 0) + " 条", 1),
							j(O)?.result_summary?.debug_browser_kept === !0 ? (n(), M("p", bn, "失败窗口已保留，可在 Roxy 中查看。")) : p("", !0),
							S("div", xn, [
								j(Se)(Z.value.har_url) ? (n(), M("a", {
									key: 0,
									href: j(Se)(Z.value.har_url),
									download: ""
								}, "下载 HAR", 8, Sn)) : p("", !0),
								j(Se)(Z.value.page_state_url) ? (n(), M("a", {
									key: 1,
									href: j(Se)(Z.value.page_state_url),
									download: ""
								}, "下载页面现场", 8, Cn)) : p("", !0),
								j(Se)(Z.value.screenshot_url) ? (n(), M("a", {
									key: 2,
									href: j(Se)(Z.value.screenshot_url),
									target: "_blank",
									rel: "noopener"
								}, "查看失败截图", 8, wn)) : p("", !0)
							])
						])) : p("", !0),
						(n(!0), M(g, null, o(je.value, (e, t) => (n(), M("article", {
							key: j(H)(e.id) || t,
							class: "tc-artifact"
						}, [
							S("h3", null, b(e.resource_type || "运行资源"), 1),
							S("p", null, b(e.provider || e.state || "—"), 1),
							S("small", null, b(j(ke)(e.acquired_at || e.created_at)), 1)
						]))), 128)),
						!Z.value?.available && !je.value.length ? (n(), M("div", Tn, "当前 Run 没有诊断资源或产物")) : p("", !0),
						De.value?.result_summary ? (n(), M("details", En, [t[16] ||= S("summary", null, "执行结果字段", -1), S("pre", null, b(JSON.stringify(De.value.result_summary, null, 2)), 1)])) : p("", !0)
					], 512), [[A, j(I) === "artifacts"]])
				], 512),
				S("footer", Dn, [S("small", null, "时间按浏览器时区显示 · " + b(j(ge)), 1), X.value && j(I) !== "artifacts" ? (n(), M("button", {
					key: 0,
					type: "button",
					onClick: Ge
				}, "有 " + b(X.value) + " 条新记录，回到底部", 1)) : j(ne) || j(U) || j(W) ? (n(), M("small", On, "正在同步记录…")) : p("", !0)])
			], 64)) : p("", !0)
		], 544)]));
	}
}), An = [
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
function jn(e, t) {
	return e.fields.some((e) => !!t[e]);
}
function Mn(e, t, n) {
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
function Nn(e, t) {
	let n = { ...t };
	for (let t of e.fields) n[t] = "";
	return n;
}
// src/features/tasks/TaskFilterFields.vue?vue&type=script&setup=true&lang.ts
var Pn = {
	key: 0,
	class: "tc-filter-field"
}, Fn = ["for"], In = [
	"id",
	"value",
	"inputmode",
	"placeholder"
], Ln = ["aria-label"], Rn = ["name", "checked"], zn = { class: "tc-filter-option-label" }, Bn = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], Vn = { class: "tc-filter-option-label" }, Hn = {
	key: 0,
	class: "tc-filter-option-count"
}, Un = {
	key: 2,
	class: "tc-filter-date-range"
}, Wn = { class: "tc-filter-field" }, Gn = ["for"], Kn = ["id", "value"], qn = { class: "tc-filter-field" }, Jn = ["for"], Yn = ["id", "value"], Xn = { class: "tc-filter-footer" }, Zn = ["disabled"], Qn = /* @__PURE__ */ t({
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
				text: e === "status" && d[t] || n.get(t)?.label || (t.includes(",") ? Mn(r.column, {
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
			i("update:modelValue", Nn(r.column, r.modelValue)), i("done");
		}
		return (t, r) => (n(), M("form", {
			class: "tc-filter-fields",
			onSubmit: r[5] ||= T((e) => i("done"), ["prevent"])
		}, [e.column.kind === "search" ? (n(), M("div", Pn, [S("label", { for: `${j(a)}-search` }, b(e.column.key === "task_id" ? "任务 ID" : e.column.label), 9, Fn), S("input", {
			id: `${j(a)}-search`,
			value: c.value,
			type: "search",
			inputmode: e.column.key === "task_id" ? "numeric" : void 0,
			placeholder: e.column.placeholder,
			onInput: r[0] ||= (e) => m(s.value, e.target.value)
		}, null, 40, In)])) : e.column.kind === "select" ? (n(), M("div", {
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
		}, null, 40, Rn), S("span", zn, b(l[e.column.group || ""] || "全部"), 1)], 2), (n(!0), M(g, null, o(f.value, (e) => (n(), M("label", {
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
			}, null, 40, Bn),
			S("span", Vn, b(e.text), 1),
			e.count == null ? p("", !0) : (n(), M("span", Hn, b(e.count), 1))
		], 2))), 128))], 8, Ln)) : (n(), M("div", Un, [
			r[6] ||= S("p", { class: "tc-filter-hint" }, "按创建日期筛选任务。", -1),
			S("div", Wn, [S("label", { for: `${j(a)}-from` }, "创建日期起", 8, Gn), S("input", {
				id: `${j(a)}-from`,
				value: e.modelValue.created_from,
				type: "date",
				onInput: r[3] ||= (e) => m("created_from", e.target.value)
			}, null, 40, Kn)]),
			S("div", qn, [S("label", { for: `${j(a)}-to` }, "创建日期止", 8, Jn), S("input", {
				id: `${j(a)}-to`,
				value: e.modelValue.created_to,
				type: "date",
				onInput: r[4] ||= (e) => m("created_to", e.target.value)
			}, null, 40, Yn)])
		])), S("div", Xn, [S("button", {
			type: "button",
			class: "ui-link",
			disabled: !j(jn)(e.column, e.modelValue),
			onClick: _
		}, "清除此列", 8, Zn), r[7] ||= S("button", {
			type: "submit",
			class: "ui-button"
		}, "完成", -1)])], 32));
	}
}), $n = { class: "tc-mobile-filters" }, er = { class: "tc-filter-column-picker" }, tr = ["value"], nr = /* @__PURE__ */ t({
	__name: "TaskFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean }
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = v(An[0].key), u = D(() => An.find((e) => e.key === c.value)), d = D(() => An.filter((e) => jn(e, i.modelValue)).length);
		return (t, i) => (n(), M("div", $n, [l(Ae, {
			label: "任务条件",
			"trigger-label": d.value ? `筛选（${d.value}）` : "筛选",
			active: d.value > 0,
			open: e.open,
			"onUpdate:open": i[3] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [S("label", er, [i[4] ||= N("筛选列", -1), a(S("select", { "onUpdate:modelValue": i[0] ||= (e) => c.value = e }, [(n(!0), M(g, null, o(j(An), (t) => (n(), M("option", {
				key: t.key,
				value: t.key
			}, b(t.label) + b(j(jn)(t, e.modelValue) ? " · 已筛选" : ""), 9, tr))), 128))], 512), [[m, c.value]])]), (n(), x(Qn, {
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
}), rr = /* @__PURE__ */ t({
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
			active: j(jn)(e.column, e.modelValue),
			summary: j(Mn)(e.column, e.modelValue, e.facets),
			open: e.open,
			"onUpdate:open": a[2] ||= (e) => i("update:open", e)
		}, {
			default: r(() => [l(Qn, {
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
}), ir = /* @__PURE__ */ new Set([
	"failed",
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"password_confirmation_pending"
]), ar = /* @__PURE__ */ new Set([
	"running",
	"waiting",
	"stopping",
	"cancelling",
	"settling"
]), or = /* @__PURE__ */ new Set([
	"cancelled",
	"stopped",
	"interrupted"
]), sr = {
	email_verification_pending: "待验证或补全",
	credential_pending_confirmation: "凭证待核验"
};
function cr(e, t, n) {
	let r = `${e === "status" ? "执行状态" : "目标状态"}：${G(e, t)}${t ? `（${t}）` : ""}`;
	return n && n !== t ? `${r} · 原始状态：${n}` : r;
}
function lr(e) {
	return e.next_actions?.some((e) => e.action === "await_child") ? "等待子任务" : "等待中";
}
function ur(e) {
	let t = String(e.status || ""), n = String(e.target_status || ""), r = {
		label: G("status", t),
		tone: ie(t),
		title: cr("status", t, e.internal_status)
	};
	e.debug_pause ? (r.label = "已暂停", r.tone = "warning", r.secondary = "等待结束调试", r.title = `调试暂停 · ${r.title}`) : ["queued", "pending"].includes(t) ? (r.label = "排队中", r.tone = "warning", r.secondary = Ee(e) || void 0) : ar.has(t) ? (r.label = "进行中", t === "waiting" && (r.secondary = Ee(e) || lr(e)), ["stopping", "cancelling"].includes(t) && (r.secondary = "停止中"), t === "settling" && (r.secondary = "收尾中")) : t === "success" ? r.label = "已完成" : t === "partial_success" ? r.label = "部分完成" : ir.has(t) ? (r.label = "失败", r.tone = "danger") : or.has(t) && (r.label = "已停止");
	let i = !e.debug_pause && (ir.has(n) && ir.has(t) || n === "completed" && t === "success" || n === "in_progress" && ar.has(t) || n === "pending" && [
		"queued",
		"pending",
		"waiting"
	].includes(t) || n === "cancelled" && ["cancelled", "stopped"].includes(t));
	return {
		execution: r,
		target: !n || i ? null : {
			label: sr[n] || G("target_status", n),
			tone: ie(n),
			title: cr("target_status", n, e.internal_target_status)
		}
	};
}
// src/features/tasks/resultSummary.ts
var Q = (e, t = "neutral", n) => ({
	label: e,
	...n ? { secondary: n } : {},
	tone: t
}), dr = (e) => Array.isArray(e) ? e.map(K) : [], $ = (e) => String(e || "").toLowerCase(), fr = /* @__PURE__ */ new Set([
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
		let n = $(t[e]).trim();
		if (n) {
			if (fr.has(n) || ["unknown.unclassified", "task.pending"].includes(n) || /(?:_receipt_missing|_failure_diagnostics_missing|_evidence_missing|_unconfirmed|_request_unknown|\.confirmation|\.safety)$/.test(n)) return !1;
			if (Ie({ [e]: n }) !== Ie()) return !0;
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
	let n = K(e.result_summary), r = $(e.status), i = $(n.extraction_status), a = $(n.payment_status);
	return ["succeeded", "success"].includes(i) || !i && n.ok === !0 && n.has_link === !0 ? ["failed", "error"].includes(a) ? Q("提链成功", "danger", "支付失败") : [
		"succeeded",
		"success",
		"paid"
	].includes(a) ? Q("提链成功", "success", "支付成功") : fr.has(a) ? Q("提链成功", "warning", "支付待确认") : [
		"pending",
		"pending_payment",
		"processing"
	].includes(a) || n.mode === "manual_payment" && a === "not_started" ? Q("提链成功", "warning", n.mode === "manual_payment" ? "待手动支付" : "支付处理中") : [
		"cancelled",
		"stopped",
		"interrupted"
	].includes(r) ? Q("提链成功", "warning", "后续已中断") : fr.has(r) || fr.has($(e.internal_status)) ? Q("提链成功", "warning", "后续待确认") : ["failed", "partial_success"].includes(r) ? Q("提链成功", "danger", "后续失败") : Q("提链成功", "success") : pr.has(i) || mr(e) ? Q(t, "danger") : fr.has(i) ? Q("提链待确认", "warning") : ["pending", "queued"].includes(i) ? Q("等待提链", "warning") : i === "running" ? Q("提链中", "active") : r === "cancelled" ? Q("已取消") : ["stopped", "interrupted"].includes(r) ? Q("执行已中断", "warning") : fr.has(r) || fr.has($(e.internal_status)) ? Q("提链待确认", "warning") : e.error_message || e.error_info || n.ok === !1 || r === "failed" ? Q(t, "danger") : n.ok === !0 ? Q("提链流程完成", "success") : Q("提链结果缺失", "warning");
}
function vr(e, t) {
	let n = K(e.result_summary), r = $(e.status), i = Array.isArray(n.plan_check_countries) && n.plan_check_countries.length === 0, a = i ? [] : dr(n.plan_check_country_results).filter((e) => e.country), o = a.length ? a.filter((e) => e.status === "success").length : Number(n.country_success_count || 0), s = a.length ? a.filter((e) => ["failed", "cancelled"].includes($(e.status))).length : !i && Array.isArray(n.failed_countries) ? n.failed_countries.length : 0, c = a.length || (i ? 0 : Number(n.country_total_count || 0)), l = a.length ? a.flatMap((e) => {
		let t = e.status === "success", n = K(e.result);
		return !t && !e.last_success_at ? [] : dr(n.account_promotions).map((e) => ({
			...e,
			stale: !t || e.stale === !0
		}));
	}) : dr(n.account_promotions), u = l.some((e) => e.stale === !0) || a.some((e) => e.status !== "success" && e.last_success_at && Object.keys(K(e.result)).length > 0);
	if (s > 0 && o > 0 || !i && n.plan_check_partial === !0) return Q("部分失败", "warning", u ? "含历史数据" : void 0);
	if (c > 0 && s >= c) return u ? Q("查询失败", "danger", "含历史数据") : Q(t, "danger");
	if (mr(e)) return Q(t, "danger");
	if (fr.has(r) || fr.has($(e.internal_status)) || fr.has($(n.status))) return Q("查询待确认", "warning", u ? "含历史数据" : void 0);
	if (e.error_message || e.error_info || r === "failed" || n.ok === !1) return u ? Q("查询失败", "danger", "含历史数据") : Q(t, "danger");
	if (r === "partial_success") return Q("部分完成", "warning", u ? "含历史数据" : void 0);
	if (a.some((e) => ["queued", "running"].includes($(e.status)))) return Q("部分仍待查询", "warning");
	if (!Object.keys(n).length) return Q("套餐结果缺失", "warning");
	let d = {
		free: "免费套餐",
		plus: "Plus",
		go: "Go",
		pro: "Pro",
		team: "团队套餐",
		business: "商业套餐",
		enterprise: "企业套餐"
	}[$(n.current_plan_type || n.plan_type)] || "已查询";
	if (u) return Q(d, "warning", "含历史数据");
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
	}, p = [...l].sort((e, t) => (f[$(e.kind)] ?? 3) - (f[$(t.kind)] ?? 3) || Number(t.plan === "plus") - Number(e.plan === "plus"))[0];
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
		}[$(p.kind)] || "优惠待复查";
		return Q(d, [
			"unknown",
			"pending",
			"failed",
			"cancelled"
		].includes($(p.kind)) ? "warning" : "success", t);
	}
	return n.plus_trial_eligible === !0 || n.plus_promo_kind === "free_trial" ? Q(d, "success", "Plus免费") : n.plus_discount_eligible === !0 || n.plus_promo_kind === "discount" ? Q(d, "success", "Plus折扣") : n.plus_promo_kind === "none" || n.plus_promo_eligible === !1 ? Q(d, "success", "无优惠") : Q(d, "neutral", "优惠待复查");
}
function yr(e, t = "执行异常") {
	let n = K(e.result_summary), r = $(e.status), i = e.task_type, a = t && [...t].length <= 10 ? t : "执行异常";
	if (e.debug_pause) return Q("调试已暂停", "warning");
	if (["queued", "pending"].includes(r)) {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Q(hr[String(t)] || "等待执行", "warning");
	}
	if (r === "waiting") {
		let t = e.admission_wait_reasons?.[0]?.code || e.admission_wait_reason || "";
		return Q(hr[String(t)] || lr(e), "warning");
	}
	if (r === "running") return Q("执行中", "active");
	if (["stopping", "cancelling"].includes(r)) return Q("正在停止", "warning");
	if (r === "settling") return Q("正在收尾", "active");
	if (i === "extract_link") return _r(e, a);
	if (i === "email_change" && n.email_change_confirmed === !0) return Q("邮箱已换绑", "success", K(n.post_change_live_check).accepted ? "刷新已排队" : "刷新待处理");
	if (i === "codex_retry" && n.ok === !0) {
		let e = $(K(n.sub2api_sync).status);
		return e === "failed" ? Q("授权成功", "warning", "同步失败") : e === "cancelled" ? Q("授权成功", "warning", "同步已停止") : e === "success" ? Q("授权成功", "success", "同步已完成") : Q("授权成功", "success", n.credential_confirmed === !0 ? "凭证已确认" : void 0);
	}
	if (i === "codex_token_refresh" && n.ok === !0) return Q("令牌已刷新", n.sub2_sync === "failed" ? "warning" : "success", n.sub2_sync === "failed" ? "同步失败" : void 0);
	if (i === "sub2api_manual_upload" && n.uploaded === !0 && (r !== "success" || n.ok === !1)) return Q("上传已完成", "warning", "回写待确认");
	if (i === "sub2api_sync" && n.superseded === !0) return Q("新凭证已接续");
	if (i === "account_inspection") {
		if (n.inspection_outcome === "deactivated_skipped") return Q("已废账号跳过");
		if (n.inspection_outcome === "deleted_skipped") return Q("已删账号跳过");
		if (n.inspection_outcome === "valid") return Q("令牌本地有效", "success");
		if (n.inspection_outcome === "refreshed") return Q("令牌已刷新", n.plan_ok === !1 ? "warning" : "success", n.plan_ok === !1 ? "查套餐失败" : void 0);
	}
	if (i === "plan_check") return vr(e, a);
	if (r === "cancelled") return Q("已取消");
	if (["stopped", "interrupted"].includes(r)) return Q("执行已中断", "warning");
	if (mr(e)) return Q(a, "danger");
	if (fr.has(r) || fr.has($(e.internal_status)) || fr.has($(n.status))) return Q("结果待确认", "warning");
	if (["deactivated", "account_deactivated"].includes($(e.target_status)) || r === "deactivated") return Q("账号已停用", "danger");
	let o = i === "sub2api_scan" || i === "c2a_scan";
	if (e.error_message || e.error_info || pr.has(r) || !o && n.ok === !1) return Q(a, "danger");
	if (r === "partial_success") return Q("部分完成", "warning");
	if (o) return r === "success" ? Q(i === "c2a_scan" && n.continuation_only === !0 ? "接续检查完成" : gr[i], "success") : Q("扫描未完成", "warning");
	if (i === "registration" || i === "registration_resume") {
		let t = {
			account_available: "账号可用",
			email_verification_pending: "邮箱待验证",
			credential_valid: "凭证有效",
			credential_pending_confirmation: "凭证待确认",
			not_created: "账号未创建",
			in_progress: "账号处理中"
		}[$(e.target_status)];
		if (t) return Q(t, ["account_available", "credential_valid"].includes($(e.target_status)) ? "success" : "warning");
	}
	return i === "deactivation_mail" && typeof n.detected == "boolean" ? Q(n.detected ? "发现封号邮件" : "未见封号邮件", n.detected ? "warning" : "neutral") : i === "live_check" && n.ok === !0 ? Q("账号正常", "success") : i === "token_refresh" && n.ok === !0 ? Q("令牌已刷新", "success") : i === "account_inspection_batch" && Number(n.failed_count) > 0 ? Q("巡检已完成", "warning", "存在失败") : r === "success" || n.ok === !0 ? Q(gr[i] || "任务已完成", "success") : Q("结果未记录");
}
// src/features/tasks/TaskResultCell.vue
var br = /* @__PURE__ */ t({
	__name: "TaskResultCell",
	props: { task: {} },
	setup(e) {
		let t = e, i = D(() => yr(t.task, Ie(t.task.error_info))), a = D(() => [...new Set([
			re(t.task),
			t.task.error_info?.display_code,
			t.task.error_info?.cause_display_code,
			t.task.error_info || t.task.error_message ? oe(t.task.error_info, t.task.error_message) : "",
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
			...ur(e)
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
			return X(e) || e.current_stage_label || G("stage", e.current_stage);
		}
		function O(e) {
			return [
				e.current_stage_label || G("stage", e.current_stage),
				X(e),
				V(e.duration_ms)
			].filter(Boolean).join(" · ");
		}
		function k(e) {
			return String(e.bulk_batch_id || K(e.bulk_context).batch_id || "");
		}
		function A(e) {
			return String(e.bulk_round_id || K(e.bulk_context).round_id || "");
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
			}, null, 40, Sr)) : (n(), M(g, { key: 1 }, [j(An)[r - 1] ? (n(), x(rr, {
				key: 0,
				column: j(An)[r - 1],
				"model-value": e.filters,
				facets: e.facets,
				open: e.openFilter === j(An)[r - 1].key,
				"onUpdate:modelValue": i[1] ||= (e) => s("update:filters", e),
				"onUpdate:open": (e) => s("update:openFilter", e ? j(An)[r - 1].key : null)
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
				S("td", Dr, [l(Z, { text: j(G)("task_type", t.task_type) }, null, 8, ["text"])]),
				S("td", Or, [C(t) || w(t) ? (n(), x(Z, {
					key: 0,
					text: C(t) || "—",
					secondary: w(t) || void 0
				}, {
					default: r(() => [C(t) ? (n(), M("strong", kr, b(C(t)), 1)) : (n(), M("span", Ar, "—"))]),
					_: 2
				}, 1032, ["text", "secondary"])) : (n(), M("span", jr, "—"))]),
				S("td", Mr, [S("span", {
					class: E(["ui-badge tc-badge", `ui-badge--${i.tone}`]),
					title: i.title
				}, b(i.label), 11, Nr), i.secondary ? (n(), M("span", {
					key: 0,
					class: "tc-subline tc-cell-line",
					title: i.secondary
				}, b(i.secondary), 9, Pr)) : p("", !0)]),
				S("td", Fr, [a ? (n(), M("span", {
					key: 0,
					class: E(["ui-badge tc-badge", `ui-badge--${a.tone}`]),
					title: a.title
				}, b(a.label), 11, Ir)) : (n(), M("span", Lr, "—"))]),
				S("td", Rr, [l(Z, {
					text: t.batch_title || t.batch_uuid || (k(t) ? "查看批次" : "单任务"),
					secondary: j(G)("trigger", t.trigger)
				}, {
					default: r(() => [k(t) ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: (e) => s("batch", k(t), A(t))
					}, b(t.batch_title || t.batch_uuid || "查看批次"), 9, zr)) : (n(), M(g, { key: 1 }, [N(b(t.batch_title || t.batch_uuid || "单任务"), 1)], 64))]),
					_: 2
				}, 1032, ["text", "secondary"])]),
				S("td", Br, [l(Z, {
					text: `${t.run_count || 0} 次`,
					secondary: `最近 #${t.last_run_no || "—"}`
				}, null, 8, ["text", "secondary"])]),
				S("td", Vr, [l(Z, {
					text: T(t),
					secondary: j(V)(t.duration_ms),
					title: O(t),
					tone: j(X)(t) ? "danger" : "neutral"
				}, null, 8, [
					"text",
					"secondary",
					"title",
					"tone"
				])]),
				S("td", Hr, [l(Z, {
					text: j(ke)(t.created_at),
					secondary: j(ke)(t.completed_at)
				}, null, 8, ["text", "secondary"])]),
				S("td", Ur, [l(br, { task: t }, null, 8, ["task"])]),
				S("td", Wr, [S("div", Gr, [
					S("button", {
						type: "button",
						class: "ui-link",
						onClick: (e) => s("detail", t.id)
					}, "详情", 8, Kr),
					j(q)(t) ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						disabled: e.busy,
						onClick: (e) => s("action", t, "retry")
					}, "重跑", 8, qr)) : p("", !0),
					j(W)(t) ? (n(), M("button", {
						key: 1,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "terminate")
					}, b(t.status === "queued" ? "取消" : "终止"), 9, Jr)) : p("", !0),
					j(Y)(t) ? p("", !0) : (n(), M("button", {
						key: 2,
						type: "button",
						class: "ui-link ui-link--danger",
						disabled: e.busy,
						onClick: (e) => s("action", t, "delete")
					}, "删除", 8, Yr))
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
		], 4)], 8, xr));
	}
});
// src/features/tasks/useTaskList.ts
function Zr() {
	let t = c(Be()), n = v(1), r = v(20), a = v(0), o = v([]), s = v({}), l = v(/* @__PURE__ */ new Set()), u = v(!1), d = v(""), p = v(!1), m = D(() => Math.max(1, Math.ceil(a.value / r.value))), h = 0, g = null, _, y, b = 0, x = 0, S = "", C = "", w = "", T = !1, E = /* @__PURE__ */ new Set([
		"task_id",
		"target",
		"batch",
		"result"
	]), O, k = () => JSON.stringify({ ...t }), A = (e = k()) => T && (S !== e || Date.now() - x >= 3e4);
	function j(t = 0, n = !1) {
		clearTimeout(y);
		let r = ++b, i = () => {
			r === b && p.value && !document.hidden && N({ background: n });
		};
		t ? y = setTimeout(i, t) : e(i);
	}
	let M = () => {
		clearTimeout(_), p.value && !document.hidden && (_ = setTimeout(() => void N({ background: !0 }), 5e3));
	};
	async function N(e = {}) {
		clearTimeout(_), clearTimeout(y), ++b;
		let i = {
			...t,
			page: n.value,
			page_size: r.value
		}, c = JSON.stringify(i), f = k(), p = !!(e.metadata || A(f)), v = ++h;
		g?.abort(), g = new AbortController(), u.value = !e.background || w !== c;
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
			e.facets && (s.value = e.facets), p && (x = Date.now(), S = f), w = c, d.value = "";
		} catch (e) {
			v === h && !P(e) && (d.value = e instanceof Error ? e.message : "任务列表加载失败");
		} finally {
			v === h && (u.value = !1, g = null, !p && A() ? j(0, !0) : M());
		}
	}
	function F(e) {
		e !== p.value && (p.value = e, clearTimeout(_), clearTimeout(y), e && !document.hidden ? j(0, !0) : (++b, g?.abort(), ++h, u.value = !1));
	}
	function I(e) {
		e !== T && (T = e, !g && A() && p.value && !document.hidden && j(0, !0));
	}
	function L(e, r = !0) {
		Object.assign(t, r ? {
			...Be(),
			...e
		} : e), n.value = 1, l.value = /* @__PURE__ */ new Set();
	}
	function ee(e, t) {
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
		if (i.length && (s.value = {}, S = "", O = i.every((e) => E.has(e)) && e.page_size === r.page_size ? 260 : 0, n.value !== 1)) {
			n.value = 1;
			return;
		}
		let a = O ?? 0;
		O = void 0, ++h, g?.abort(), j(a);
	});
	let R = () => {
		clearTimeout(_), document.hidden ? (++b, clearTimeout(y), g?.abort(), ++h, u.value = !1) : p.value && j(0, !0);
	};
	return document.addEventListener("visibilitychange", R), f(() => {
		++h, ++b, g?.abort(), clearTimeout(_), clearTimeout(y), document.removeEventListener("visibilitychange", R);
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
		refresh: N,
		setVisible: F,
		setFacetsVisible: I,
		applyFilters: L,
		toggle: ee,
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
		let u = c, f = Zr(), { filters: m, page: _, size: y, pages: x, total: w, items: O, facets: k, selected: P, loading: F, error: I, visible: L } = f, ee = v(null), te = v(null), R = v(!1), z = v(""), B = v(""), V = v(null), H = v(null), W = v(m.target || ""), re;
		i(() => m.target, (e) => {
			clearTimeout(re), W.value = e || "";
		}), C(() => clearTimeout(re)), i(V, (e) => {
			f.setFacetsVisible(e === "mobile" || An.some((t) => t.key === e && t.kind === "select"));
		});
		let ie = D(() => An.filter((e) => jn(e, m))), G = D(() => !!m.team_id), ae = D(() => {
			let e = ie.value.map((e) => ({
				key: e.key,
				label: `${e.label}：${Mn(e, m, k.value)}`,
				removeLabel: `清除${e.label}筛选`
			}));
			return m.team_id && e.push({
				key: "team_id",
				label: `Team：#${m.team_id}`,
				removeLabel: "清除 Team 筛选"
			}), e;
		}), oe = v([]), se = D(() => O.value.filter((e) => P.value.has(e.id))), q = D(() => Object.fromEntries([
			"retry",
			"cancel",
			"terminate",
			"delete"
		].map((e) => [e, se.value.filter((t) => U(t, e)).length]))), ce = {
			retry: "重跑",
			cancel: "取消排队",
			terminate: "终止运行",
			delete: "删除"
		}, le = Intl.DateTimeFormat().resolvedOptions().timeZone;
		function J(e) {
			Object.assign(m, e);
		}
		function ue(e) {
			clearTimeout(re);
			let t = e.trim();
			t !== (m.target || "") && J({
				...m,
				target: t
			});
		}
		function de(e) {
			W.value = e, clearTimeout(re), re = setTimeout(() => ue(e), 250);
		}
		function fe() {
			clearTimeout(re), W.value = "", ue(""), H.value?.focus();
		}
		function pe(e) {
			if (e === "team_id") {
				J({
					...m,
					team_id: ""
				});
				return;
			}
			let t = An.find((t) => t.key === e);
			t && J(Nn(t, m));
		}
		function me() {
			m.team_id && window.TeamsPage?.navigate?.({
				view: "detail",
				team_id: m.team_id,
				section: "invitations"
			});
		}
		function he(e, t, n) {
			ee.value?.open(e, t, n);
		}
		async function X(t = {}) {
			t.filters && (t.taskId || ee.value?.close?.(), f.applyFilters(t.filters)), t.taskId && (await e(), he(t.taskId, t.runId, t.stepId));
		}
		function ge(e) {
			e || (V.value = null), f.setVisible(e);
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
			if (!R.value && !(t === "delete" && Y(e))) {
				if (t !== "retry") {
					let n = t === "delete" ? `确定删除任务 #${e.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。` : e.status === "queued" ? `确定取消排队中的任务 #${e.id}？` : `确定终止任务 #${e.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
					if (!window.confirm(n)) return;
				}
				R.value = !0, B.value = "", oe.value = [], z.value = "";
				try {
					let n = await Ge.action(e.id, t), r = K(n.data || n);
					z.value = t === "retry" ? r.round_id || r.bulk_round_id ? "重跑已受理，已创建所属批次的新轮次" : "任务已重新入队" : t === "delete" ? "任务已删除" : n.state === "cancelled" ? "任务已取消" : "任务已终止，原请求证据已保留", P.value.delete(e.id), await ve(), u("changed");
				} catch (e) {
					B.value = `${ce[t]}失败：${e instanceof Error ? e.message : String(e)}`;
				} finally {
					R.value = !1;
				}
			}
		}
		async function xe(e) {
			if (R.value) return;
			let t = se.value.filter((t) => U(t, e));
			if (!t.length) return;
			let n = e === "retry" ? "原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。" : e === "cancel" ? "只取消尚未开始的排队任务。" : e === "delete" ? "任务会从任务中心隐藏，历史审计记录仍会保留。" : "运行中的任务会立即收口，已发出的远端请求证据会保留。";
			if (window.confirm(`确定${ce[e]}选中的 ${t.length} 个任务吗？\n\n${n}`)) {
				R.value = !0, B.value = "", z.value = "", oe.value = [];
				try {
					let n = t.map((e) => e.id), r = e === "terminate" ? await Ge.bulk(e, n, { onAccepted: (e) => {
						z.value = `终止请求已受理，正在等待结果（命令 ${e.command_id}）`;
					} }) : await Ge.bulk(e, n), i = Array.isArray(r.accepted) ? r.accepted : [];
					oe.value = (r.skipped || []).map((e) => ({
						id: e.task_id,
						message: e.error || e.message || "操作未接受"
					}));
					let a = Number(r.accepted_count ?? i.length);
					if (e === "cancel") {
						let e = i.filter((e) => e.state === "cancelled").length, t = i.filter((e) => e.state === "cancelling").length;
						z.value = `已取消 ${e} 个，取消中 ${t} 个${a - e - t > 0 ? `，已受理 ${a - e - t} 个` : ""}`;
					} else z.value = `已${ce[e]} ${a} 个`;
					let o = new Set(i.map((e) => String(e.task_id)));
					P.value = new Set([...P.value].filter((e) => !o.has(String(e)))), oe.value.length && (z.value += `，跳过 ${oe.value.length} 个`), await ve(), u("changed");
				} catch (t) {
					B.value = t instanceof ne ? t.message : `${ce[e]}失败：${t instanceof Error ? t.message : String(t)}`;
				} finally {
					R.value = !1;
				}
			}
		}
		return s({
			open: X,
			refresh: ve,
			closeDetail: _e,
			setVisible: ge
		}), (e, t) => (n(), M(g, null, [a(S("section", Qr, [S("div", $r, [
			l(Re, { filtered: ie.value.length > 0 || G.value }, {
				actions: r(() => [
					j(m).team_id ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "ui-button",
						onClick: me
					}, "返回该 Team")) : p("", !0),
					l(nr, {
						"model-value": j(m),
						facets: j(k),
						open: V.value === "mobile",
						"onUpdate:modelValue": J,
						"onUpdate:open": t[2] ||= (e) => V.value = e ? "mobile" : null
					}, null, 8, [
						"model-value",
						"facets",
						"open"
					]),
					ie.value.length || G.value ? (n(), M("button", {
						key: 1,
						type: "button",
						class: "ui-link",
						onClick: t[3] ||= (e) => j(f).applyFilters({})
					}, "清除全部筛选")) : p("", !0),
					S("span", {
						class: "tc-timezone",
						title: j(le)
					}, "时间按 " + b(j(le)) + " 显示", 9, oi),
					S("button", {
						type: "button",
						class: "ui-link",
						onClick: t[4] ||= (e) => te.value?.resetColumns()
					}, "恢复列宽"),
					S("button", {
						id: "btnRefreshTasksV2",
						type: "button",
						class: "ui-button ui-refresh-button",
						disabled: j(F),
						onClick: t[5] ||= (e) => j(f).refresh()
					}, b(j(F) ? "刷新中…" : "刷新"), 9, si)
				]),
				default: r(() => [
					S("span", ei, b(j(w).toLocaleString()) + " 个任务", 1),
					S("div", ti, [S("input", {
						ref_key: "targetInput",
						ref: H,
						type: "search",
						value: W.value,
						placeholder: "搜索目标邮箱 / 账号...",
						"aria-label": "搜索任务目标",
						autocomplete: "off",
						onInput: t[0] ||= (e) => de(e.target.value),
						onKeydown: [t[1] ||= h(T((e) => ue(W.value), ["prevent"]), ["enter"]), h(T(fe, ["prevent"]), ["esc"])]
					}, null, 40, ni), W.value ? (n(), M("button", {
						key: 0,
						type: "button",
						class: "tc-target-search__clear",
						"aria-label": "清空目标搜索",
						title: "清空目标搜索",
						onClick: fe
					}, "×")) : p("", !0)]),
					se.value.length ? (n(), M("span", ri, "已选 " + b(se.value.length) + " 项", 1)) : p("", !0),
					se.value.length ? (n(), M("div", ii, [(n(), M(g, null, o([
						"retry",
						"cancel",
						"terminate",
						"delete"
					], (e) => S("button", {
						key: e,
						type: "button",
						class: E(["ui-button", { "ui-button--danger": e === "delete" || e === "terminate" }]),
						disabled: R.value || !q.value[e],
						onClick: (t) => xe(e)
					}, b(ce[e]) + b(q.value[e] ? `（${q.value[e]}）` : ""), 11, ai)), 64))])) : p("", !0),
					l(Me, {
						items: ae.value,
						onRemove: pe
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
				oe.value.length ? (n(), M("details", li, [t[12] ||= S("summary", null, "查看跳过原因", -1), S("ul", null, [(n(!0), M(g, null, o(oe.value, (e) => (n(), M("li", { key: e.id }, "#" + b(e.id) + "：" + b(e.message), 1))), 128))])])) : p("", !0)
			], 10, ci)) : p("", !0),
			l(Xr, {
				ref_key: "table",
				ref: te,
				filters: j(m),
				facets: j(k),
				"open-filter": V.value,
				"onUpdate:openFilter": t[7] ||= (e) => V.value = e,
				"onUpdate:filters": J,
				items: j(O),
				selected: j(P),
				loading: j(F),
				error: j(I),
				busy: R.value,
				onSelect: j(f).toggle,
				onSelectPage: j(f).togglePage,
				onDetail: he,
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
		])], 512), [[A, j(L)]]), l(kn, {
			ref_key: "detail",
			ref: ee,
			onRefresh: ye
		}, null, 512)], 64));
	}
});
// src/main.ts
function di(e, t = {}) {
	return O(ui, t).mount(e);
}
export { di as mountTaskCenter };
