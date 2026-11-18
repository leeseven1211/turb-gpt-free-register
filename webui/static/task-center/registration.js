import { $ as e, A as t, C as n, G as r, I as i, P as a, S as o, V as s, W as c, Z as l, _ as u, a as d, b as f, c as p, ct as m, dt as h, g, h as _, i as v, j as ee, m as y, n as b, o as x, ot as S, p as C, r as w, s as T, t as E, u as D, ut as te, x as O } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { n as k, r as A, t as ne } from "./ListFilterSummary-NiVwXoAn.js";
import { t as re } from "./useColumnWidths-DKwoq5eG.js";
import { n as j } from "./time-DOD6oyhP.js";
import { t as ie } from "./ListResult-3o6cJKgT.js";
import { t as ae } from "./useNativeDialog-Ba95V1OP.js";
import { O as M, _ as oe, a as se, b as N, h as P, i as F, n as I, p as L, r as R, t as z, v as B, y as V } from "./StepEvidence-CM91D2vn.js";
import { t as ce } from "./errorLabels-6tZmqsp4.js";
import { t as le } from "./ListPagination-CFFXEHba.js";
import { n as H, r as U } from "./client-BBEPwkQG.js";
import { a as W, r as G } from "./taskIds-BlchWwUp.js";
// src/features/registration/RegistrationFilters.vue?vue&type=script&setup=true&lang.ts
var K = { class: "registration-filter-fields" }, q = { key: 0 }, ue = ["value"], de = ["value", "aria-label"], J = ["value"], Y = ["value"], fe = ["value"], pe = [
	"type",
	"value",
	"aria-label"
], me = { class: "registration-filter-actions" }, he = /*#__PURE__*/ E(/* @__PURE__ */ o({
	__name: "RegistrationFilters",
	props: {
		column: {},
		values: {},
		sources: {},
		open: { type: Boolean }
	},
	emits: ["update:open", "change"],
	setup(t, { emit: n }) {
		let o = {
			id: "ID",
			email: "邮箱",
			email_source: "邮箱来源",
			status: "状态",
			proxy: "代理",
			error: "错误",
			date_from: "开始日期",
			date_to: "截止日期"
		}, s = t, l = n, d = e("email"), p = C(() => s.column || d.value), m = C(() => s.values[p.value]), ee = C(() => [.../* @__PURE__ */ new Set([
			"pending",
			"running",
			"stopping",
			"success",
			"partial_success",
			"failed",
			"stopped",
			"cancelled",
			"interrupted",
			"request_unknown",
			"attention_required",
			...s.values.status ? [s.values.status] : []
		])]), b = (e) => ({
			pending: "排队中",
			running: "运行中",
			stopping: "停止中",
			success: "成功",
			partial_success: "部分成功",
			failed: "失败",
			stopped: "已停止",
			cancelled: "已取消",
			interrupted: "执行中断",
			request_unknown: "待核对",
			attention_required: "待核对"
		})[e] || e;
		function x(e) {
			l("change", p.value, e);
		}
		return (e, n) => (a(), _(A, {
			label: t.column ? o[t.column] : "注册任务",
			"trigger-label": t.column ? o[t.column] : "筛选",
			active: t.column ? !!t.values[t.column] : Object.values(t.values).some(Boolean),
			summary: m.value,
			open: t.open,
			"onUpdate:open": n[7] ||= (e) => l("update:open", e)
		}, {
			default: c(() => [y("div", K, [
				t.column ? g("", !0) : (a(), u("label", q, [n[8] ||= f("筛选列", -1), r(y("select", {
					"onUpdate:modelValue": n[0] ||= (e) => d.value = e,
					"aria-label": "选择注册任务筛选列"
				}, [(a(), u(D, null, i(o, (e, t) => y("option", {
					key: t,
					value: t
				}, h(e), 9, ue)), 64))], 512), [[v, d.value]])])),
				y("label", null, [f(h(o[p.value]) + " ", 1), p.value === "email_source" ? (a(), u("select", {
					key: 0,
					value: m.value,
					"aria-label": `筛选${o[p.value]}值`,
					onChange: n[1] ||= (e) => x(e.target.value)
				}, [n[9] ||= y("option", { value: "" }, "全部邮箱来源", -1), (a(!0), u(D, null, i(t.sources, (e) => (a(), u("option", {
					key: e.value,
					value: e.value
				}, h(e.label || e.value), 9, J))), 128))], 40, de)) : p.value === "status" ? (a(), u("select", {
					key: 1,
					value: m.value,
					"aria-label": "筛选状态值",
					onChange: n[2] ||= (e) => x(e.target.value)
				}, [n[10] ||= y("option", { value: "" }, "全部状态", -1), (a(!0), u(D, null, i(ee.value, (e) => (a(), u("option", {
					key: e,
					value: e
				}, h(b(e)), 9, fe))), 128))], 40, Y)) : (a(), u("input", {
					key: 2,
					type: p.value.startsWith("date_") ? "date" : "search",
					value: m.value,
					"aria-label": `筛选${o[p.value]}值`,
					onChange: n[3] ||= (e) => x(e.target.value),
					onKeydown: n[4] ||= T((e) => l("update:open", !1), ["enter"])
				}, null, 40, pe))]),
				y("div", me, [y("button", {
					type: "button",
					onClick: n[5] ||= (e) => x("")
				}, "清除此列"), y("button", {
					type: "button",
					onClick: n[6] ||= (e) => l("update:open", !1)
				}, "完成")])
			])]),
			_: 1
		}, 8, [
			"label",
			"trigger-label",
			"active",
			"summary",
			"open"
		]));
	}
}), [["__scopeId", "data-v-0bb12339"]]), ge = { class: "registration-progress" }, _e = {
	key: 0,
	class: "registration-step-note"
}, ve = {
	class: "registration-steps",
	"aria-label": "注册执行阶段，排列不代表固定顺序"
}, ye = ["title", "onClick"], be = { "data-registration-step-duration": "" }, xe = { key: 0 }, Se = ["aria-label", "onClick"], Ce = { key: 1 }, we = { key: 0 }, Te = /* @__PURE__ */ o({
	__name: "RegistrationProgress",
	props: {
		job: {},
		active: { type: Boolean }
	},
	emits: ["log"],
	setup(t, { emit: n }) {
		let r = t, o = n, s = C(() => {
			let e = [
				r.job?.progress,
				r.job?.progress_snapshot,
				r.job?.progress_v2
			].find((e) => Array.isArray(e?.main_steps))?.main_steps || Object.entries(r.job?.progress_steps || {}).map(([e, t]) => ({
				id: e,
				...t
			}));
			return se(e.map((e, t) => ({
				...e,
				id: String(e.id || e.step_id || e.key || `step-${t + 1}`),
				label: e.label || e.name || e.id || e.step_id
			})));
		}), c = e(), l = e();
		ae(l, () => !!c.value && r.active, () => r.active);
		let d = (e) => M(oe(e));
		function f(e) {
			let t = L(e.debug_pause);
			return t.state === "paused" ? `调试暂停 · 等待结束调试${t.paused_at ? ` · 暂停于 ${j(t.paused_at)}` : " · 暂停时间未记录"}${t.hold_until ? ` · 保留至 ${j(t.hold_until)}` : ""}` : "";
		}
		function v(e) {
			let t = e.attempts || [], n = e.children || [], r = (e) => e.raw_stage_label || n.find((t) => t.id === e.raw_stage)?.label || e.raw_stage || "阶段", i = [...new Set(t.map(r))];
			return [
				`${V(e)} · ${F(e)}`,
				f(e),
				e.reason || e.message || "",
				`开始：${j(e.started_at)}`,
				`结束：${j(e.completed_at)}`,
				`耗时：${d(e)}`,
				i.length ? `已记录阶段：${i.join("、")}` : "",
				n.length ? `子步骤（${n.length}）` : "",
				...n.map((e) => `${V(e)} · ${F(e)} · ${d(e)}${e.reason || e.message ? `\n${e.reason || e.message}` : ""}`),
				t.length ? `阶段事件（${t.length} 条）` : "",
				...t.map((e, t) => `${t + 1}. ${r(e)} · ${P(e.display_status || e.state)}${e.created_at ? ` · ${j(e.created_at)}` : e.event_time_known === !1 ? " · 发生时间未记录" : ""}${e.message ? `\n${e.message}` : ""}`),
				"点击步骤查看对应日志"
			].filter(Boolean).join("\n");
		}
		return (e, t) => (a(), u("div", ge, [
			s.value.length ? (a(), u("p", _e, "阶段按首次记录排列，位置相邻不代表固定执行顺序。")) : g("", !0),
			y("ul", ve, [(a(!0), u(D, null, i(s.value, (e) => (a(), u("li", {
				key: S(B)(e),
				class: m(`is-${S(N)(e)}`)
			}, [y("button", {
				type: "button",
				title: v(e),
				onClick: (t) => o("log", S(B)(e))
			}, [
				y("strong", null, h(S(V)(e)), 1),
				y("small", null, h(S(F)(e)), 1),
				y("small", be, "耗时 " + h(d(e)), 1),
				(a(!0), u(D, null, i(S(R)(e), (e) => (a(), u("small", { key: e }, h(e), 1))), 128)),
				f(e) ? (a(), u("small", xe, h(f(e)), 1)) : g("", !0)
			], 8, ye), y("button", {
				type: "button",
				"aria-label": `查看${S(V)(e)}的关系与证据`,
				onClick: (t) => c.value = e
			}, "详情", 8, Se)], 2))), 128))]),
			s.value.length ? (a(), u("details", Ce, [t[3] ||= y("summary", null, "依赖与执行记录", -1), (a(!0), u(D, null, i(s.value, (e) => (a(), u("div", { key: S(B)(e) }, [y("strong", null, h(S(V)(e)), 1), O(I, {
				step: e,
				siblings: s.value
			}, null, 8, ["step", "siblings"])]))), 128))])) : g("", !0),
			y("dialog", {
				ref_key: "dialog",
				ref: l,
				class: "registration-dialog",
				"aria-label": "注册步骤关系与证据",
				onCancel: t[1] ||= p((e) => c.value = void 0, ["prevent"]),
				onClose: t[2] ||= (e) => c.value = void 0
			}, [
				y("header", null, [y("h3", null, h(c.value ? S(V)(c.value) : "步骤详情"), 1), y("button", {
					type: "button",
					onClick: t[0] ||= (e) => c.value = void 0
				}, "关闭")]),
				c.value && f(c.value) ? (a(), u("p", we, h(f(c.value)), 1)) : g("", !0),
				c.value ? (a(), _(z, {
					key: 1,
					step: c.value,
					siblings: s.value
				}, null, 8, ["step", "siblings"])) : g("", !0)
			], 544)
		]));
	}
}), X = (e, t = {}) => U(e, t, G), Ee = (e) => ({
	method: "POST",
	headers: { "Content-Type": "application/json" },
	body: JSON.stringify(e ?? {})
});
function De() {
	return {
		metadata: (e) => Promise.all([X("/api/email-sources", { signal: e }), X("/api/capabilities", { signal: e })]).then(([e, t]) => ({
			...e,
			capabilities: t
		})),
		summary: (e) => X("/api/summary", { signal: e }),
		jobs: (e, t) => X(`/api/jobs?${new URLSearchParams(Object.entries(e).map(([e, t]) => [e, String(t)]))}`, { signal: t }),
		create: (e, t) => X("/api/jobs", {
			...Ee(e),
			signal: t
		}),
		action: (e, t = {}, n) => X(e, {
			...Ee(t),
			signal: n
		}),
		log: (e, t) => X(`/api/jobs/${encodeURIComponent(String(e))}/log`, { signal: t }),
		debug: (e, t) => X(`/api/jobs/${encodeURIComponent(String(e))}/debug?limit=300`, { signal: t }),
		diagnostics: (e, t) => X(`/api/jobs/${encodeURIComponent(String(e))}/diagnostics?limit=100`, { signal: t }),
		compare: (e, t) => X(`/api/jobs/${encodeURIComponent(String(e))}/debug/compare`, { signal: t })
	};
}
// src/features/registration/useRegistration.ts
var Z = [
	"pending",
	"running",
	"stopping"
], Oe = [
	"success",
	"partial_success",
	"failed",
	"stopped",
	"cancelled",
	"interrupted",
	"request_unknown",
	"manual_reconcile",
	"attention_required",
	"password_confirmation_pending",
	"unsupported",
	"deactivated"
], ke = [
	"failed",
	"partial_success",
	"stopped",
	"cancelled",
	"interrupted",
	"request_unknown",
	"manual_reconcile",
	"attention_required"
], Ae = () => ({
	page: 1,
	page_size: 20,
	status: "",
	id: "",
	email: "",
	email_source: "",
	proxy: "",
	error: "",
	date_from: "",
	date_to: ""
}), Q = (e) => e instanceof Error ? e.message : "请求失败", je = (e) => e == null ? "" : String(e).trim(), $ = (e) => encodeURIComponent(String(W(e))), Me = () => ({
	id: null,
	job: null,
	log: "",
	debug: null,
	diagnostics: null,
	loading: !1,
	error: "",
	comparison: null,
	compareError: "",
	comparing: !1
});
function Ne(r) {
	let i = r.api || De(), a = e(!!r.visible), o = e(!document.hidden), s = !1, c = C(() => a.value && o.value && !s), u = l({
		jobs: [],
		total: 0,
		batch: null,
		batches: [],
		meta: null,
		summary: null,
		view: r.view || "launch",
		loading: !1,
		error: "",
		receipt: null,
		query: Ae(),
		batchId: "",
		statusCounts: {},
		facets: {},
		creating: !1,
		pendingActions: {},
		lastCreate: null,
		lastAction: null,
		detail: Me()
	}), d = C(() => u.creating), f = C(() => {
		let e = u.meta?.capabilities?.features?.register;
		return e?.enabled === !1 ? String(e.reason || "功能缺少必要配置") : "";
	}), p = (e) => r.notify?.(e), m = 0, h = 0, g = 0, _ = 0, v = 0, ee, y, b, x, S, w, T, E, D = "", te = 0, O = 0, k = !0, A, ne = /* @__PURE__ */ new Map(), re = () => !s && o.value && u.detail.id !== null, j = (e, t) => re() && e === v && String(u.detail.id) === String(t);
	function ie() {
		m++, x?.controller.abort(), x = void 0, u.loading = !1;
	}
	function ae() {
		ie(), g++, S?.controller.abort(), S = void 0, _++, w?.controller.abort(), w = void 0;
	}
	function M() {
		window.clearInterval(ee), window.clearInterval(y), ee = y = void 0;
	}
	function oe() {
		if (!c.value) return !1;
		if (u.view === "tasks") return !0;
		let e = u.batch;
		return !e || String(e.batch_id) !== u.batchId || e.projection_delayed ? !0 : Z.some((t) => Number(e.status_counts?.[t] || 0) > 0) || e.items.some((e) => Z.includes(String(e.status || "")));
	}
	function se(e) {
		for (let t of Object.keys(Ae())) {
			let n = e[t];
			if (n !== void 0) {
				if (t === "page" || t === "page_size") {
					let e = Number(n);
					Number.isSafeInteger(e) && e > 0 && (u.query[t] = t === "page_size" ? Math.min(e, 500) : e);
				} else u.query[t] = String(n);
			}
		}
		if (e.progress_batch_id !== void 0) {
			let t = je(e.progress_batch_id);
			t !== u.batchId && (u.batchId = t, u.batch = null);
		}
	}
	function N(e = {}) {
		if (se(e), !c.value || e.automatic && !oe()) return Promise.resolve();
		let t = JSON.stringify({
			view: u.view,
			batchId: u.batchId,
			...u.query
		});
		if ((e.automatic || e.coalesce) && x?.signature === t) return x.promise;
		x?.controller.abort();
		let n = ++m, r = new AbortController(), a = u.view;
		e.automatic || h++;
		let o = h;
		u.loading = !0, u.error = "";
		let s = () => c.value && n === m && a === u.view, l = (async () => {
			try {
				for (let n = 0; n < 2; n++) {
					let c = {
						paged: 1,
						...u.query,
						view: a === "tasks" ? "table" : "batch",
						progress_batch_id: u.batchId,
						refresh_generation: o
					};
					a === "tasks" && e.automatic && D === t && Date.now() - te < 3e4 && (c.include_facets = 0);
					let l = await i.jobs(c, r.signal);
					if (!s()) return;
					if (Object.prototype.hasOwnProperty.call(l, "status_counts") && (u.statusCounts = l.status_counts || {}), a === "launch") {
						u.batches = l.progress_batches || [];
						let e = l.progress_batch || null;
						if (!e && u.batchId) {
							let e = je(u.batches[0]?.batch_id);
							if (e !== u.batchId && (u.batchId = e, u.batch = null, e && !n)) continue;
						}
						!u.batchId && e?.batch_id && (u.batchId = je(e.batch_id)), u.batch = e;
					} else {
						u.total = Math.max(0, Number(l.total ?? l.items?.length ?? 0) || 0), Object.prototype.hasOwnProperty.call(l, "facets") && (u.facets = l.facets || {}, D = t, te = Date.now());
						let e = Math.max(1, Math.ceil(u.total / u.query.page_size));
						if (u.query.page > e) {
							if (u.query.page = e, !n) continue;
							throw Error("列表范围已变化，请刷新后重试");
						}
						u.jobs = l.items || [];
					}
					return;
				}
			} catch (e) {
				s() && !H(e) && (u.error = Q(e));
			} finally {
				n === m && (u.loading = !1, x = void 0);
			}
		})();
		return x = {
			version: n,
			signature: t,
			promise: l,
			controller: r
		}, l;
	}
	function P(e) {
		return N({ progress_batch_id: je(e) });
	}
	function F(e) {
		return N({
			...e,
			page: e.page ?? 1
		});
	}
	function I(e) {
		return N({ page: e });
	}
	function L(e) {
		return N({
			page: 1,
			page_size: e
		});
	}
	function R(e) {
		u.summary = e;
	}
	function z(e) {
		u.summary = {
			...u.summary || {},
			email_supply: e || {}
		};
	}
	function B() {
		if (!c.value) return Promise.resolve();
		S?.controller.abort();
		let e = ++g, t = new AbortController(), n = (async () => {
			try {
				let n = await i.summary(t.signal);
				e === g && c.value && R(n);
			} catch (t) {
				e === g && c.value && !H(t) && z({
					status: "error",
					reason: "本地库存读取失败，请稍后重试"
				});
			} finally {
				e === g && (S = void 0);
			}
		})();
		return S = {
			version: e,
			promise: n,
			controller: t
		}, n;
	}
	function V(e = !1) {
		if (e && (k = !0), !c.value || !k && u.meta && Date.now() - O < 3e4) return Promise.resolve();
		if (w && !e) return w.promise;
		w?.controller.abort();
		let t = ++_, n = new AbortController(), r = (async () => {
			try {
				let e = await i.metadata(n.signal);
				if (t !== _ || !c.value) return;
				let r = e.capabilities?.email_sources || {};
				u.meta = {
					...e,
					sources: (e.sources || []).map((e) => ({
						...e,
						...r[e.value] || {}
					}))
				}, O = Date.now(), k = !1;
			} catch (e) {
				t === _ && c.value && !H(e) && (u.error = Q(e));
			} finally {
				t === _ && (w = void 0);
			}
		})();
		return w = {
			version: t,
			promise: r,
			controller: n
		}, r;
	}
	function ce() {
		M(), c.value && (V(), N({ coalesce: !0 }), B(), ee = window.setInterval(() => {
			N({ automatic: !0 });
		}, 5e3), y = window.setInterval(() => {
			S || B();
		}, 1e4));
	}
	function le(e) {
		a.value !== e && (a.value = e, e ? ce() : (M(), ae()));
	}
	function U(e) {
		["launch", "tasks"].includes(e) && u.view !== e && (u.view = e, ie(), N({ coalesce: !0 }));
	}
	function G(e, t = "已受理") {
		let n = e.message || e.warning || (e.started_count == null ? e.deleted_count == null ? e.cancelled == null ? t : `已取消 ${e.cancelled} 个排队任务` : `已删除 ${e.deleted_count} 个任务` : `已提交 ${e.started_count} 个失败任务`), r = Array.isArray(e.skipped) ? e.skipped.length : 0;
		u.receipt = {
			tone: e.warning ? "warning" : "success",
			message: String(n) + (r ? `，跳过 ${r} 个` : "")
		}, p(u.receipt.message);
	}
	function K(e) {
		let t = je(e.jobs?.[0]?.batch_id || e.job?.batch_id || e.batch_id);
		t && (u.batchId = t, u.batch = null);
	}
	function q(e, t = {}) {
		let n = JSON.stringify([e, t]), r = ne.get(n);
		if (r) return r;
		u.pendingActions[n] = !0;
		let a = (async () => {
			try {
				let n = await i.action(e, t);
				return u.lastAction = n, K(n), G(n), /\/delete(?:-bulk)?$/.test(e) && u.detail.id !== null && (Array.isArray(n.deleted) ? n.deleted : n.deleted === !0 ? [e.split("/").at(-2)] : []).some((e) => String(e) === String(u.detail.id)) && pe(), N(), u.detail.id !== null && Y(), n;
			} catch (e) {
				throw u.receipt = {
					tone: "danger",
					message: Q(e)
				}, p(u.receipt.message), e;
			} finally {
				ne.delete(n), delete u.pendingActions[n];
			}
		})();
		return ne.set(n, a), a;
	}
	function ue(e) {
		if (A) return A;
		if (f.value) {
			let e = f.value;
			return u.receipt = {
				tone: "warning",
				message: e
			}, p(e), Promise.reject(Error(e));
		}
		return !Number.isSafeInteger(e.count) || e.count < 1 || !Number.isSafeInteger(e.workers) || e.workers < 1 ? Promise.reject(/* @__PURE__ */ Error("注册数量与并发线程数必须为有效的正整数")) : (u.creating = !0, A = (async () => {
			try {
				let t = await i.create({ ...e });
				return u.lastCreate = t, K(t), G(t, `已提交 ${t.submitted || 0} 个任务`), N(), t;
			} catch (e) {
				throw u.receipt = {
					tone: "danger",
					message: Q(e)
				}, p(u.receipt.message), e;
			} finally {
				u.creating = !1, A = void 0;
			}
		})(), A);
	}
	async function de(e, t, n = [], i = !1) {
		let a = u.batch?.items || [], o = e === "stopBatch" ? a.filter((e) => ["running", "stopping"].includes(String(e.status))) : e === "cancelBatch" ? a.filter((e) => e.status === "pending") : e === "retryBatch" ? a.filter((e) => ke.includes(String(e.status)) && e.retryable) : [], s = e === "retryBulk" || e === "deleteBulk" ? n.map((e) => W(e)) : o.map((e) => W(e.id));
		if ([
			"stopBatch",
			"cancelBatch",
			"retryBatch",
			"retryBulk",
			"deleteBulk"
		].includes(e) && !s.length) return p("当前没有可操作的任务"), null;
		if (["stopBatch", "cancelBatch"].includes(e) && !u.batchId) return null;
		if (e === "retry" && !t?.retryable) return p("该任务当前不可重试"), null;
		if ([
			"stop",
			"delete",
			"retry"
		].includes(e) && !t) throw Error("任务不存在");
		let c = {
			cancelAll: "取消所有排队任务",
			stopBatch: `停止当前批次的 ${s.length} 个运行中任务`,
			cancelBatch: `取消当前批次的 ${s.length} 个排队任务`,
			retryBatch: `重跑当前批次的 ${s.length} 个失败任务`,
			stop: `停止任务 #${t?.id}`,
			delete: `删除任务 #${t?.id} 与对应日志`,
			retry: `${t?.retry_label || "重试"}任务 #${t?.id}`,
			deleteBulk: `删除选中的 ${s.length} 个任务与对应日志`,
			retryBulk: `重试选中的 ${s.length} 个任务`
		}, l = e === "retry" && t?.retry_action === "codex" ? "仅补跑 Codex 授权" : e === "retry" && t?.retry_action === "twofa" ? "重新登录检查并补齐 Authenticator 2FA" : e === "retry" && t?.retry_action === "registration_resume" ? "使用已保存账号密码继续邮箱验证" : "有原邮箱则复用，没有原邮箱则重新领取；已创建账号的任务按缺失步骤补跑，不能重试的由后端校验", d = e === "retry" || e === "retryBulk" || e === "retryBatch" ? `\n${l}。原任务记录和日志会保留。` : e === "stop" || e === "stopBatch" ? "\n任务会在当前步骤检查点退出。" : e === "cancelAll" || e === "cancelBatch" ? "\n运行中的任务不受影响。" : "", f = encodeURIComponent(u.batchId), m = t ? $(t.id) : "";
		return await (r.confirm ? r.confirm(`确定${c[e]}吗？${d}`) : window.confirm(`确定${c[e]}吗？${d}`)) ? q(...{
			cancelAll: ["/api/jobs/cancel-pending", {}],
			stopBatch: [`/api/jobs/batches/${f}/stop`, {}],
			cancelBatch: [`/api/jobs/batches/${f}/cancel`, {}],
			retryBatch: ["/api/jobs/retry-bulk", {
				job_ids: s,
				debug_enabled: i
			}],
			stop: [`/api/jobs/${m}/stop`, {}],
			delete: [`/api/jobs/${m}/delete`, {}],
			retry: [`/api/jobs/${m}/retry`, { debug_enabled: i }],
			deleteBulk: ["/api/jobs/delete-bulk", { job_ids: s }],
			retryBulk: ["/api/jobs/retry-bulk", {
				job_ids: s,
				debug_enabled: i
			}]
		}[e]) : null;
	}
	function J() {
		v++, T?.abort(), E?.abort(), T = E = void 0, window.clearTimeout(b), b = void 0, u.detail.loading = !1, u.detail.comparing = !1;
	}
	async function Y() {
		if (!re()) return;
		T?.abort(), window.clearTimeout(b);
		let e = u.detail.id, t = ++v, n = new AbortController();
		T = n, u.detail.loading = !0, u.detail.error = "";
		let r = () => j(t, e);
		try {
			let t = await i.log(e, n.signal);
			if (!r()) return;
			u.detail.job = t.job || null, u.detail.log = String(t.log || "");
			let a = await i.debug(e, n.signal);
			if (!r()) return;
			if (u.detail.debug = a?.enabled ? a : null, a?.enabled) u.detail.diagnostics = null;
			else {
				let t = await i.diagnostics(e, n.signal);
				if (!r()) return;
				u.detail.diagnostics = t;
			}
		} catch (e) {
			r() && !H(e) && (u.detail.error = Q(e));
		} finally {
			r() && (u.detail.loading = !1, Oe.includes(String(u.detail.job?.status || "")) || (b = window.setTimeout(() => void Y(), 2e3)));
		}
	}
	function fe(e, t) {
		let n = W(e), i = [...u.jobs, ...u.batch?.items || []].find((e) => String(e.id) === String(n));
		i?.operation_task_id && r.openTask ? r.openTask(i.operation_task_id, i.operation_run_id || null, t || null) : (J(), u.detail = {
			...Me(),
			id: n
		}, Y());
	}
	function pe() {
		J(), u.detail = Me();
	}
	async function me(e) {
		let t = W(e);
		if (!j(v, t)) return null;
		E?.abort();
		let n = new AbortController();
		E = n;
		let r = () => re() && E === n && !n.signal.aborted && String(u.detail.id) === String(t);
		u.detail.comparing = !0, u.detail.compareError = "";
		try {
			let e = await i.compare(t, n.signal);
			return r() ? (u.detail.comparison = e, e) : null;
		} catch (e) {
			if (r() && !H(e)) throw u.detail.compareError = Q(e), e;
			return null;
		} finally {
			r() && (u.detail.comparing = !1, E = void 0);
		}
	}
	function he() {
		o.value = !document.hidden, o.value ? (ce(), u.detail.id !== null && Y()) : (M(), ae(), J());
	}
	function ge() {
		s = !0, M(), ae(), J(), document.removeEventListener("visibilitychange", he);
	}
	return document.addEventListener("visibilitychange", he), n() && t(ge), {
		state: u,
		active: c,
		creating: d,
		registrationUnavailable: f,
		ensureMeta: V,
		load: N,
		loadSummary: B,
		renderEmailSupply: z,
		applySummary: R,
		setVisible: le,
		setView: U,
		setBatch: P,
		updateQuery: F,
		setPage: I,
		setSize: L,
		shouldPollJobs: oe,
		create: ue,
		action: q,
		executeAction: de,
		compare: me,
		openLog: fe,
		refreshDetail: Y,
		closeDetail: pe,
		notify: p,
		terminalStatuses: Oe,
		activeStatuses: Z,
		dispose: ge
	};
}
// src/features/registration/RegistrationPage.vue?vue&type=script&setup=true&lang.ts
var Pe = ["data-view"], Fe = { class: "registration-launch" }, Ie = { class: "registration-summary" }, Le = {
	id: "registrationEmailSupplyHint",
	class: "registration-hint"
}, Re = { class: "registration-launcher" }, ze = ["disabled"], Be = ["value"], Ve = { class: "registration-debug" }, He = ["disabled", "title"], Ue = {
	key: 0,
	class: "registration-hint",
	role: "status"
}, We = {
	key: 1,
	class: "registration-batch"
}, Ge = ["value"], Ke = ["onClick"], qe = ["onClick"], Je = { key: 0 }, Ye = { class: "registration-tasks" }, Xe = { class: "registration-toolbar" }, Ze = ["disabled"], Qe = ["disabled"], $e = {
	class: "registration-count-row",
	"data-registration-count-row": ""
}, et = { class: "registration-count-main" }, tt = { class: "registration-count" }, nt = { class: "registration-count-actions" }, rt = { class: "registration-mobile-filter" }, it = {
	key: 0,
	class: "registration-list-error",
	role: "alert"
}, at = { class: "registration-table-wrap" }, ot = { key: 2 }, st = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], ct = { key: 0 }, lt = { key: 1 }, ut = [
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], dt = { key: 0 }, ft = { class: "registration-row-actions" }, pt = ["onClick"], mt = ["onUpdate:modelValue"], ht = ["onClick"], gt = ["onClick"], _t = ["onClick"], vt = ["disabled", "onClick"], yt = { id: "registration-log-title" }, bt = { key: 0 }, xt = {
	key: 1,
	role: "alert"
}, St = { key: 2 }, Ct = ["disabled"], wt = ["href"], Tt = { key: 0 }, Et = {
	key: 1,
	role: "alert"
}, Dt = { key: 3 }, Ot = ["href"], kt = /* @__PURE__ */ o({
	__name: "RegistrationPage",
	props: { deps: {} },
	setup(t, { expose: n }) {
		let o = t, l = Ne(o.deps), { state: b } = l, E = re({
			defaults: [
				40,
				120,
				190,
				120,
				150,
				180,
				100,
				150,
				150,
				150,
				170
			],
			storageKey: "gpt_console_table_widths_jobs",
			totalStorageKey: "gpt_console_table_total_jobs",
			min: 28,
			max: 2e3
		});
		function A() {
			E.resetColumns(), o.deps.notify?.("已恢复默认列宽");
		}
		function j(e) {
			let t = e.status_counts || {}, n = Number(t.running || 0) + Number(t.stopping || 0), r = Number(t.pending || 0);
			return n + r > 0 ? `未完成 ${n + r}（运行 ${n} / 等待 ${r}）` : `成功 ${t.success || 0} · 失败 ${t.failed || 0}`;
		}
		let M = [
			{ label: "选择" },
			{
				label: "ID",
				filter: "id"
			},
			{
				label: "邮箱",
				filter: "email"
			},
			{
				label: "邮箱来源",
				filter: "email_source"
			},
			{ label: "注册协议" },
			{
				label: "代理",
				filter: "proxy"
			},
			{
				label: "状态",
				filter: "status"
			},
			{
				label: "开始日期",
				filter: "date_from"
			},
			{
				label: "截止日期",
				filter: "date_to"
			},
			{
				label: "错误",
				filter: "error"
			},
			{ label: "操作" }
		], oe = e();
		ae(oe, () => b.detail.id !== null, () => l.active.value);
		let se = e(1), N = e(3), P = e(""), F = e(!1), I = e(""), L = e(""), R = e(""), z = e(""), B = e(""), V = e(""), H = e(""), U = e(""), W = e(1), G = e(20), K = e(/* @__PURE__ */ new Set()), q = e({}), ue = C(() => b.view === "launch"), de = C(() => b.view === "tasks"), J = C(() => b.jobs), Y = e(null), fe = C(() => ({
			id: L.value,
			email: R.value,
			email_source: z.value,
			status: I.value,
			proxy: B.value,
			error: V.value,
			date_from: H.value,
			date_to: U.value
		})), pe = {
			id: "ID",
			email: "邮箱",
			email_source: "邮箱来源",
			status: "状态",
			proxy: "代理",
			error: "错误",
			date_from: "开始日期",
			date_to: "截止日期"
		}, me = C(() => Object.entries(fe.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${pe[e]}：${e === "status" ? Z(t) : e === "email_source" ? De(t) : t}`,
			removeLabel: `清除${pe[e]}筛选`
		})));
		function ge(e, t) {
			let n = {
				id: L,
				email: R,
				email_source: z,
				status: I,
				proxy: B,
				error: V,
				date_from: H,
				date_to: U
			};
			n[e].value = t, Y.value = null, kt();
		}
		let _e = (e) => e.error_info ? ce(e.error_info) : e.error_message ? "执行异常" : "—", ve = e(""), ye = C(() => b.statusCounts.active ?? [
			"pending",
			"running",
			"stopping"
		].reduce((e, t) => e + Number((Object.keys(b.statusCounts).length ? b.statusCounts : b.batch?.status_counts || {})[t] || 0), 0)), be = C(() => !!b.meta?.manual_mode), xe = C(() => {
			let e = new Map((b.meta?.sources || []).map((e) => [String(e.value), {
				value: String(e.value),
				label: e.label || String(e.value)
			}])), t = b.facets.email_source;
			for (let n of Array.isArray(t) ? t : []) {
				let t = String(typeof n == "object" ? n.value : n);
				e.has(t) || e.set(t, {
					value: t,
					label: typeof n == "object" && n.label || t
				});
			}
			return z.value && !e.has(z.value) && e.set(z.value, {
				value: z.value,
				label: z.value
			}), [...e.values()];
		}), Se = C(() => be.value ? [{
			value: "manual",
			label: "手动配置邮箱"
		}] : b.meta?.sources?.filter((e) => e.enabled === !0) || []), Ce = C(() => b.summary?.email_supply || {}), we = (e) => {
			let t = Ce.value[e];
			return Number.isInteger(t) && Number(t) >= 0 ? t : Ce.value.status === "error" ? "读取失败" : "未知";
		}, X = C(() => `仅统计本地库存；用完后请手动导入；邮箱由 Email Butler 等邮箱服务准备${Ce.value.reason ? `；${Ce.value.reason}` : ""}`), Ee = (e) => b.meta?.registration_drivers?.find((t) => String(t.value) === String(e))?.label || {
			protocol: "本地优化 Protocol（历史）",
			protocol_oss: "开源 Protocol（历史）",
			protocol_oss_2: "开源protocol-2",
			roxy: "本地 Roxy",
			roxy_oss: "开源 Roxy（历史）"
		}[String(e || "")] || String(e || "未知"), De = (e) => xe.value.find((t) => String(t.value) === String(e))?.label || String(e || "-"), Z = (e) => ({
			pending: "排队中",
			running: "运行中",
			stopping: "停止中",
			success: "成功",
			failed: "失败",
			partial_success: "部分成功",
			cancelled: "已取消",
			stopped: "已停止",
			interrupted: "执行中断",
			request_unknown: "失败",
			manual_reconcile: "失败",
			attention_required: "失败",
			unsupported: "不支持",
			deactivated: "已停用",
			password_confirmation_pending: "失败·密码响应缺失"
		})[String(e)] || String(e || "等待中"), Oe = async (e) => o.deps.confirm ? await o.deps.confirm(e) : window.confirm(e);
		function ke(e) {
			e || (Y.value = null), l.setVisible(e);
		}
		function Ae(e) {
			Y.value = null, l.setView(e);
		}
		function Q(e) {
			let t = oe.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && l.closeDetail();
		}
		async function je() {
			if (l.registrationUnavailable.value) {
				b.receipt = {
					tone: "warning",
					message: l.registrationUnavailable.value
				};
				return;
			}
			let e = Number(se.value), t = Number(N.value);
			if (!Number.isSafeInteger(e) || e < 1) b.receipt = {
				tone: "warning",
				message: "注册数量必须为有效的正整数"
			};
			else if (!Number.isSafeInteger(t) || t < 1) b.receipt = {
				tone: "warning",
				message: "并发线程数必须为有效的正整数"
			};
			else if (!P.value) b.receipt = {
				tone: "warning",
				message: "请选择本次注册使用的邮箱来源"
			};
			else if (!(ye.value > 0 && !await Oe(`当前任务表里已有 ${ye.value} 个任务在跑或排队，这次会再加 ${e} 个，确定继续？`))) try {
				let n = await l.create({
					count: e,
					workers: t,
					email_source: P.value,
					debug_enabled: F.value
				});
				Number.isSafeInteger(n?.workers) && n.workers > 0 && (N.value = n.workers);
			} catch {}
		}
		async function $(e, t) {
			let n = Array.from(K.value);
			try {
				await l.executeAction(e, t, n, F.value), (e === "deleteBulk" || e === "retryBulk") && (K.value = /* @__PURE__ */ new Set());
			} catch {}
		}
		function Me() {
			I.value = L.value = R.value = z.value = B.value = V.value = H.value = U.value = "", W.value = 1, l.load(It());
		}
		function kt() {
			W.value = 1, l.load(It());
		}
		function At(e) {
			let t = e.target.checked;
			J.value.filter((e) => !["running", "stopping"].includes(String(e.status))).forEach((e) => t ? K.value.add(String(e.id)) : K.value.delete(String(e.id))), K.value = new Set(K.value);
		}
		function jt(e, t) {
			let n = new Set(K.value);
			t.target.checked ? n.add(String(e)) : n.delete(String(e)), K.value = n;
		}
		function Mt(e) {
			return [
				e.proxy_provider,
				e.proxy_endpoint && e.proxy_endpoint !== "-" ? e.proxy_endpoint : "",
				e.proxy_region && e.proxy_region !== "-" ? e.proxy_region : ""
			].filter(Boolean).join(" · ") || "-";
		}
		let Nt = (e) => Array.isArray(e?.attempts) ? e.attempts : [], Pt = (e) => Array.isArray(e?.route_attempts) ? e.route_attempts : [];
		function Ft(e) {
			ve.value = e, W.value = 1, l.setBatch(e);
		}
		function It() {
			return {
				status: I.value,
				id: L.value,
				email: R.value,
				email_source: z.value,
				proxy: B.value,
				error: V.value,
				date_from: H.value,
				date_to: U.value,
				page: W.value,
				page_size: G.value
			};
		}
		function Lt(e) {
			let t = String(q.value[String(e.id)] || "").trim();
			t ? l.action("/api/manual-otp", {
				email: e.email,
				code: t,
				job_id: e.id
			}).then(() => {
				q.value = {
					...q.value,
					[String(e.id)]: ""
				};
			}).catch(() => {}) : b.receipt = {
				tone: "warning",
				message: "请先填写邮箱验证码"
			};
		}
		async function Rt() {
			if (b.detail.id != null) try {
				await l.compare(b.detail.id);
			} catch {}
		}
		return n({
			create: l.create,
			runAction: l.executeAction,
			setBatch: l.setBatch,
			loadSources: () => l.ensureMeta(!0),
			load: l.load,
			ensureMeta: l.ensureMeta,
			setVisible: ke,
			setView: Ae,
			loadSummary: l.loadSummary,
			renderEmailSupply: l.renderEmailSupply,
			applySummary: l.applySummary,
			action: l.action,
			openLog: l.openLog,
			closeDetail: l.closeDetail
		}), s(() => ({ ...b.query }), (e) => {
			W.value = e.page, G.value = e.page_size, L.value = e.id, R.value = e.email, z.value = e.email_source, I.value = e.status, B.value = e.proxy, V.value = e.error, H.value = e.date_from, U.value = e.date_to;
		}, { immediate: !0 }), s(() => b.batchId, (e) => {
			ve.value = e;
		}, { immediate: !0 }), s([be, Se], () => {
			be.value ? P.value = "manual" : Se.value.some((e) => e.value === P.value) || (P.value = "");
		}, { immediate: !0 }), ee(() => {
			l.ensureMeta();
		}), (e, t) => (a(), u("div", {
			class: "registration-vue-page",
			"data-view": S(b).view
		}, [
			r(y("section", Fe, [
				y("div", Ie, [
					y("div", null, [t[20] ||= y("span", null, "已注册", -1), y("strong", null, h(S(b).summary?.accounts ?? 0), 1)]),
					y("div", null, [t[21] ||= y("span", null, "本地邮箱总数", -1), y("strong", null, h(we("total")), 1)]),
					y("div", null, [t[22] ||= y("span", null, "本地可用", -1), y("strong", null, h(we("available")), 1)]),
					y("div", null, [t[23] ||= y("span", null, "已用", -1), y("strong", null, h(we("used")), 1)]),
					y("div", null, [t[24] ||= y("span", null, "失败", -1), y("strong", null, h(we("failed")), 1)])
				]),
				y("p", Le, h(X.value), 1),
				y("div", Re, [
					y("label", null, [t[26] ||= f("邮箱来源", -1), r(y("select", {
						"onUpdate:modelValue": t[0] ||= (e) => P.value = e,
						disabled: !S(b).meta || be.value
					}, [t[25] ||= y("option", { value: "" }, "请选择本次邮箱来源", -1), (a(!0), u(D, null, i(Se.value, (e) => (a(), u("option", {
						key: String(e.value),
						value: String(e.value)
					}, h(e.label || e.value), 9, Be))), 128))], 8, ze), [[v, P.value]])]),
					y("label", null, [t[27] ||= f("注册数量", -1), r(y("input", {
						"onUpdate:modelValue": t[1] ||= (e) => se.value = e,
						min: "1",
						type: "number"
					}, null, 512), [[
						d,
						se.value,
						void 0,
						{ number: !0 }
					]])]),
					y("label", null, [t[28] ||= f("并发线程", -1), r(y("input", {
						"onUpdate:modelValue": t[2] ||= (e) => N.value = e,
						min: "1",
						step: "1",
						type: "number"
					}, null, 512), [[
						d,
						N.value,
						void 0,
						{ number: !0 }
					]])]),
					y("label", Ve, [r(y("input", {
						"onUpdate:modelValue": t[3] ||= (e) => F.value = e,
						type: "checkbox"
					}, null, 512), [[w, F.value]]), t[29] ||= f(" 调试模式", -1)]),
					y("button", {
						type: "button",
						class: "jobs-tb-btn jobs-tb-btn--primary",
						disabled: S(b).creating || !!S(l).registrationUnavailable.value,
						title: S(l).registrationUnavailable.value || void 0,
						onClick: je
					}, "开始注册", 8, He)
				]),
				S(l).registrationUnavailable.value ? (a(), u("p", Ue, h(S(l).registrationUnavailable.value), 1)) : g("", !0),
				S(b).batch || S(b).batches.length ? (a(), u("div", We, [y("header", null, [
					t[30] ||= y("strong", null, "任务批次进度", -1),
					y("span", null, h(S(b).batch?.items?.length || 0) + " / " + h(S(b).batch?.total || S(b).batch?.items?.length || 0), 1),
					S(b).batches.length ? r((a(), u("select", {
						key: 0,
						"onUpdate:modelValue": t[4] ||= (e) => ve.value = e,
						onChange: t[5] ||= (e) => Ft(ve.value),
						"aria-label": "选择任务批次"
					}, [(a(!0), u(D, null, i(S(b).batches, (e) => (a(), u("option", {
						key: String(e.batch_id),
						value: String(e.batch_id)
					}, h(e.batch_id) + " · " + h(j(e)) + " · " + h(e.total || e.items?.length || 0) + " 个", 9, Ge))), 128))], 544)), [[v, ve.value]]) : g("", !0),
					y("button", {
						type: "button",
						onClick: t[6] ||= (e) => $("stopBatch")
					}, "停止"),
					y("button", {
						type: "button",
						onClick: t[7] ||= (e) => $("cancelBatch")
					}, "取消"),
					y("button", {
						type: "button",
						onClick: t[8] ||= (e) => $("retryBatch")
					}, "重跑失败")
				]), (a(!0), u(D, null, i(S(b).batch?.items || [], (e, n) => (a(), u("article", {
					key: String(e.id),
					class: "registration-batch-card"
				}, [
					y("div", null, [
						y("strong", null, "#" + h(n + 1) + " " + h(e.email || "准备邮箱中…"), 1),
						y("span", null, h(Z(e.display_status || e.status)), 1),
						y("button", {
							type: "button",
							onClick: (t) => S(l).openLog(e.id)
						}, "查看日志", 8, Ke),
						e.retryable ? (a(), u("button", {
							key: 0,
							type: "button",
							onClick: (t) => $("retry", e)
						}, "重试", 8, qe)) : g("", !0)
					]),
					y("small", null, h(De(e.email_source)) + " · " + h(Ee(e.registration_driver)) + " · " + h(e.error_message || ""), 1),
					O(Te, {
						job: e,
						active: S(l).active.value,
						onLog: (t) => S(l).openLog(e.id, t)
					}, null, 8, [
						"job",
						"active",
						"onLog"
					]),
					Nt(e).length || Pt(e).length ? (a(), u("details", Je, [
						t[31] ||= y("summary", null, "尝试与线路记录", -1),
						(a(!0), u(D, null, i(Nt(e), (e) => (a(), u("div", { key: String(e.id || e.attempt_id) }, h(Z(e.status)) + " · " + h(e.error_message || "已记录"), 1))), 128)),
						(a(!0), u(D, null, i(Pt(e), (e) => (a(), u("div", { key: String(e.route_attempt_no) }, h(`线路尝试 ${e.route_attempt_no || 1}`) + " · " + h(e.retry_reason || Z(e.status)), 1))), 128))
					])) : g("", !0)
				]))), 128))])) : g("", !0)
			], 512), [[x, ue.value]]),
			r(y("section", Ye, [
				y("div", Xe, [
					y("button", {
						type: "button",
						onClick: t[9] ||= (e) => $("retryBulk"),
						disabled: !K.value.size
					}, "重试", 8, Ze),
					y("button", {
						type: "button",
						onClick: t[10] ||= (e) => $("deleteBulk"),
						disabled: !K.value.size
					}, "删除", 8, Qe),
					y("button", {
						type: "button",
						onClick: t[11] ||= (e) => $("cancelAll")
					}, "取消排队"),
					y("button", {
						type: "button",
						onClick: kt
					}, "刷新")
				]),
				y("div", $e, [y("div", et, [y("span", tt, "共 " + h(S(b).total.toLocaleString()) + " 条任务", 1), O(ne, {
					items: me.value,
					onRemove: t[12] ||= (e) => ge(e, "")
				}, null, 8, ["items"])]), y("div", nt, [
					y("button", {
						type: "button",
						"aria-label": "恢复注册任务列宽",
						onClick: A
					}, "恢复列宽"),
					y("span", rt, [O(he, {
						values: fe.value,
						sources: xe.value,
						open: Y.value === "all",
						"onUpdate:open": t[13] ||= (e) => Y.value = e ? "all" : null,
						onChange: ge
					}, null, 8, [
						"values",
						"sources",
						"open"
					])]),
					me.value.length ? (a(), u("button", {
						key: 0,
						type: "button",
						onClick: Me
					}, "清筛")) : g("", !0)
				])]),
				S(b).error ? (a(), u("div", it, [f(h(S(b).error) + " ", 1), y("button", {
					type: "button",
					onClick: kt
				}, "重试")])) : g("", !0),
				y("div", at, [y("table", {
					class: "jobs-table-v2",
					style: te({ width: `${S(E).total.value}px` })
				}, [
					y("colgroup", null, [(a(!0), u(D, null, i(S(E).widths.value, (e, t) => (a(), u("col", {
						key: t,
						style: te({ width: `${e}px` })
					}, null, 4))), 128))]),
					y("thead", null, [y("tr", null, [(a(), u(D, null, i(M, (e, t) => y("th", { key: e.label }, [t === 0 ? (a(), u("input", {
						key: 0,
						type: "checkbox",
						"aria-label": "选择本页可操作任务",
						onChange: At
					}, null, 32)) : e.filter ? (a(), _(he, {
						key: 1,
						column: e.filter,
						values: fe.value,
						sources: xe.value,
						open: Y.value === e.filter,
						"onUpdate:open": (t) => Y.value = t ? e.filter : null,
						onChange: ge
					}, null, 8, [
						"column",
						"values",
						"sources",
						"open",
						"onUpdate:open"
					])) : (a(), u("span", ot, h(e.label), 1)), t < M.length - 1 ? (a(), u("button", {
						key: 3,
						type: "button",
						class: "registration-column-resize",
						"aria-label": `调整${e.label}列宽，方向键调整`,
						onPointerdown: p((e) => S(E).resize(t, e), ["prevent"]),
						onKeydown: [T(p((e) => S(E).resizeWithKeyboard(t, -10), ["prevent"]), ["left"]), T(p((e) => S(E).resizeWithKeyboard(t, 10), ["prevent"]), ["right"])]
					}, null, 40, st)) : g("", !0)])), 64))])]),
					y("tbody", null, [S(b).loading ? (a(), u("tr", ct, [...t[32] ||= [y("td", { colspan: "11" }, "正在加载任务…", -1)]])) : J.value.length ? g("", !0) : (a(), u("tr", lt, [...t[33] ||= [y("td", { colspan: "11" }, "暂无匹配任务", -1)]])), (a(!0), u(D, null, i(J.value, (e) => (a(), u("tr", { key: String(e.id) }, [
						y("td", null, [y("input", {
							type: "checkbox",
							"aria-label": `选择任务 ${e.id}`,
							checked: K.value.has(String(e.id)),
							disabled: ["running", "stopping"].includes(String(e.status)),
							onChange: (t) => jt(e.id, t)
						}, null, 40, ut)]),
						y("td", null, [O(k, {
							text: `#${e.id}`,
							secondary: e.parent_job_id ? `↳ #${e.parent_job_id}` : void 0
						}, null, 8, ["text", "secondary"])]),
						y("td", null, [O(k, { text: String(e.email || "-") }, null, 8, ["text"])]),
						y("td", null, [O(k, { text: De(e.email_source) }, null, 8, ["text"])]),
						y("td", null, [O(k, { text: Ee(e.registration_driver) }, null, 8, ["text"])]),
						y("td", null, [O(k, {
							text: Mt(e),
							secondary: String(e.proxy_status || "")
						}, null, 8, ["text", "secondary"])]),
						y("td", null, [O(k, { text: Z(e.debug_state === "paused" ? "debug_paused" : e.display_status || e.status) }, null, 8, ["text"])]),
						y("td", null, [O(k, { text: String(e.started_at || "-") }, null, 8, ["text"])]),
						y("td", null, [O(k, { text: String(e.completed_at || "-") }, null, 8, ["text"])]),
						y("td", null, [e.error_message || e.error_info ? (a(), _(ie, {
							key: 0,
							"data-registration-result": "",
							label: _e(e),
							title: String(e.error_message || _e(e)),
							tone: "danger"
						}, {
							details: c(() => [y("p", null, h(e.error_message || _e(e)), 1), e.error_info ? (a(), u("p", dt, h(e.error_info), 1)) : g("", !0)]),
							_: 2
						}, 1032, ["label", "title"])) : (a(), _(k, {
							key: 1,
							text: "—"
						}))]),
						y("td", ft, [
							y("button", {
								type: "button",
								onClick: (t) => S(l).openLog(e.id)
							}, "日志", 8, pt),
							e.manual_otp_required && e.status === "running" ? (a(), u(D, { key: 0 }, [r(y("input", {
								"onUpdate:modelValue": (t) => q.value[String(e.id)] = t,
								placeholder: "邮箱验证码"
							}, null, 8, mt), [[d, q.value[String(e.id)]]]), y("button", {
								type: "button",
								onClick: (t) => Lt(e)
							}, "提交验证码", 8, ht)], 64)) : g("", !0),
							[
								"pending",
								"running",
								"stopping"
							].includes(String(e.status)) ? (a(), u("button", {
								key: 1,
								type: "button",
								onClick: (t) => $("stop", e)
							}, "停止", 8, gt)) : g("", !0),
							e.retryable ? (a(), u("button", {
								key: 2,
								type: "button",
								onClick: (t) => $("retry", e)
							}, "重试", 8, _t)) : g("", !0),
							y("button", {
								type: "button",
								disabled: ["running", "stopping"].includes(String(e.status)),
								onClick: (t) => $("delete", e)
							}, "删除", 8, vt)
						])
					]))), 128))])
				], 4)]),
				O(le, {
					label: "注册任务分页",
					page: W.value,
					size: G.value,
					total: S(b).total,
					busy: S(b).loading,
					"onUpdate:page": t[14] ||= (e) => {
						W.value = e, S(l).load(It());
					},
					"onUpdate:size": t[15] ||= (e) => {
						G.value = e, W.value = 1, S(l).load(It());
					}
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			], 512), [[x, de.value]]),
			S(b).receipt ? (a(), u("div", {
				key: 0,
				class: m(["registration-receipt", `is-${S(b).receipt.tone}`]),
				role: "status"
			}, h(S(b).receipt.message), 3)) : g("", !0),
			y("dialog", {
				ref_key: "logDialog",
				ref: oe,
				class: "registration-dialog",
				"aria-labelledby": "registration-log-title",
				onCancel: t[18] ||= p((...e) => S(l).closeDetail && S(l).closeDetail(...e), ["prevent"]),
				onClose: t[19] ||= (...e) => S(l).closeDetail && S(l).closeDetail(...e),
				onClick: Q
			}, [
				y("header", null, [y("h2", yt, "任务 #" + h(S(b).detail.id) + " 日志", 1), y("button", {
					type: "button",
					onClick: t[16] ||= (...e) => S(l).closeDetail && S(l).closeDetail(...e)
				}, "关闭")]),
				S(b).detail.loading ? (a(), u("p", bt, "加载中…")) : g("", !0),
				S(b).detail.error ? (a(), u("p", xt, h(S(b).detail.error), 1)) : g("", !0),
				y("pre", null, h(S(b).detail.log || "（暂无日志）"), 1),
				S(b).detail.debug?.enabled ? (a(), u("div", St, [
					t[34] ||= y("strong", null, "网络调试", -1),
					y("button", {
						type: "button",
						disabled: S(b).detail.comparing,
						onClick: Rt
					}, "与同批成功任务对比", 8, Ct),
					y("a", {
						href: `/api/jobs/${S(b).detail.id}/debug/har`,
						download: ""
					}, "下载脱敏 HAR", 8, wt),
					y("button", {
						type: "button",
						onClick: t[17] ||= (e) => S(l).action(`/api/jobs/${S(b).detail.id}/debug/release`, { action: "finish" })
					}, "结束调试并收口"),
					S(b).detail.comparison ? (a(), u("pre", Tt, h(S(b).detail.comparison), 1)) : g("", !0),
					S(b).detail.compareError ? (a(), u("p", Et, h(S(b).detail.compareError), 1)) : g("", !0)
				])) : g("", !0),
				S(b).detail.diagnostics?.captured ? (a(), u("div", Dt, [
					t[36] ||= y("strong", null, "失败诊断", -1),
					S(b).detail.diagnostics.screenshot_url ? (a(), u("a", {
						key: 0,
						href: String(S(b).detail.diagnostics.screenshot_url),
						target: "_blank",
						rel: "noopener"
					}, "打开失败截图", 8, Ot)) : g("", !0),
					y("details", null, [t[35] ||= y("summary", null, "完整诊断证据", -1), y("pre", null, h(S(b).detail.diagnostics), 1)])
				])) : g("", !0)
			], 544)
		], 8, Pe));
	}
});
// src/registration.ts
function At(e, t = {}) {
	let n = b(kt, { deps: {
		...t,
		api: t.api || De()
	} }), r = n.mount(e);
	return {
		load: r.load,
		ensureMeta: r.ensureMeta,
		loadSources: r.loadSources,
		setBatch: r.setBatch,
		create: r.create,
		runAction: r.runAction,
		setVisible: r.setVisible,
		setView: r.setView,
		loadSummary: r.loadSummary,
		renderEmailSupply: r.renderEmailSupply,
		applySummary: r.applySummary,
		action: r.action,
		openLog: r.openLog,
		closeDetail: r.closeDetail,
		destroy: () => n.unmount()
	};
}
export { At as mountRegistration };
