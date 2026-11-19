import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, S as c, _ as l, a as u, c as d, d as f, dt as p, et as m, ft as h, g, h as _, i as v, j as y, l as b, lt as x, m as S, n as C, o as w, s as ee, st as T, t as E, v as D, w as O, x as k } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { n as A, r as j, t as te } from "./ListFilterSummary-_oaD8AlZ.js";
import { t as ne } from "./useColumnWidths-D1sKP53m.js";
import { n as M } from "./time-DOD6oyhP.js";
import { t as re } from "./ListResult-BtznEB_S.js";
import { t as ie } from "./useNativeDialog-DWisXYg9.js";
import { O as N, _ as ae, a as oe, b as P, h as F, i as I, n as L, p as se, r as R, t as z, v as B, y as V } from "./StepEvidence-CNs3ZCIS.js";
import { t as ce } from "./errorLabels-B-XqaTSM.js";
import { t as le } from "./ListPagination-BjETSj81.js";
import { n as H, r as U } from "./client-BBEPwkQG.js";
import { a as W, r as G } from "./taskIds-BlchWwUp.js";
// src/features/registration/RegistrationFilters.vue?vue&type=script&setup=true&lang.ts
var K = { class: "registration-filter-fields" }, q = { key: 0 }, ue = ["value"], de = ["value", "aria-label"], J = ["value"], Y = ["value"], fe = ["value"], pe = [
	"type",
	"value",
	"aria-label"
], me = { class: "registration-filter-actions" }, he = /*#__PURE__*/ E(/* @__PURE__ */ e({
	__name: "RegistrationFilters",
	props: {
		column: {},
		values: {},
		sources: {},
		open: { type: Boolean }
	},
	emits: ["update:open", "change"],
	setup(e, { emit: r }) {
		let o = {
			id: "ID",
			email: "邮箱",
			email_source: "邮箱来源",
			status: "状态",
			proxy: "代理",
			error: "错误",
			date_from: "开始日期",
			date_to: "截止日期"
		}, s = e, c = r, p = m("email"), v = S(() => s.column || p.value), y = S(() => s.values[v.value]), b = S(() => [.../* @__PURE__ */ new Set([
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
		])]), x = (e) => ({
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
		function C(e) {
			c("change", v.value, e);
		}
		return (r, s) => (t(), g(j, {
			label: e.column ? o[e.column] : "注册任务",
			"trigger-label": e.column ? o[e.column] : "筛选",
			active: e.column ? !!e.values[e.column] : Object.values(e.values).some(Boolean),
			summary: y.value,
			open: e.open,
			"onUpdate:open": s[7] ||= (e) => c("update:open", e)
		}, {
			default: n(() => [_("div", K, [
				e.column ? l("", !0) : (t(), D("label", q, [s[8] ||= k("筛选列", -1), i(_("select", {
					"onUpdate:modelValue": s[0] ||= (e) => p.value = e,
					"aria-label": "选择注册任务筛选列"
				}, [(t(), D(f, null, a(o, (e, t) => _("option", {
					key: t,
					value: t
				}, h(e), 9, ue)), 64))], 512), [[u, p.value]])])),
				_("label", null, [k(h(o[v.value]) + " ", 1), v.value === "email_source" ? (t(), D("select", {
					key: 0,
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[1] ||= (e) => C(e.target.value)
				}, [s[9] ||= _("option", { value: "" }, "全部邮箱来源", -1), (t(!0), D(f, null, a(e.sources, (e) => (t(), D("option", {
					key: e.value,
					value: e.value
				}, h(e.label || e.value), 9, J))), 128))], 40, de)) : v.value === "status" ? (t(), D("select", {
					key: 1,
					value: y.value,
					"aria-label": "筛选状态值",
					onChange: s[2] ||= (e) => C(e.target.value)
				}, [s[10] ||= _("option", { value: "" }, "全部状态", -1), (t(!0), D(f, null, a(b.value, (e) => (t(), D("option", {
					key: e,
					value: e
				}, h(x(e)), 9, fe))), 128))], 40, Y)) : (t(), D("input", {
					key: 2,
					type: v.value.startsWith("date_") ? "date" : "search",
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[3] ||= (e) => C(e.target.value),
					onKeydown: s[4] ||= d((e) => c("update:open", !1), ["enter"])
				}, null, 40, pe))]),
				_("div", me, [_("button", {
					type: "button",
					onClick: s[5] ||= (e) => C("")
				}, "清除此列"), _("button", {
					type: "button",
					onClick: s[6] ||= (e) => c("update:open", !1)
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
}, ye = ["title", "onClick"], be = { "data-registration-step-duration": "" }, xe = { key: 0 }, Se = ["aria-label", "onClick"], Ce = { key: 1 }, we = { key: 0 }, Te = /* @__PURE__ */ e({
	__name: "RegistrationProgress",
	props: {
		job: {},
		active: { type: Boolean }
	},
	emits: ["log"],
	setup(e, { emit: n }) {
		let r = e, i = n, o = S(() => {
			let e = [
				r.job?.progress,
				r.job?.progress_snapshot,
				r.job?.progress_v2
			].find((e) => Array.isArray(e?.main_steps))?.main_steps || Object.entries(r.job?.progress_steps || {}).map(([e, t]) => ({
				id: e,
				...t
			}));
			return oe(e.map((e, t) => ({
				...e,
				id: String(e.id || e.step_id || e.key || `step-${t + 1}`),
				label: e.label || e.name || e.id || e.step_id
			})));
		}), s = m(), u = m();
		ie(u, () => !!s.value && r.active, () => r.active);
		let d = (e) => N(ae(e));
		function p(e) {
			let t = se(e.debug_pause);
			return t.state === "paused" ? `调试暂停 · 等待结束调试${t.paused_at ? ` · 暂停于 ${M(t.paused_at)}` : " · 暂停时间未记录"}${t.hold_until ? ` · 保留至 ${M(t.hold_until)}` : ""}` : "";
		}
		function v(e) {
			let t = e.attempts || [], n = e.children || [], r = (e) => e.raw_stage_label || n.find((t) => t.id === e.raw_stage)?.label || e.raw_stage || "阶段", i = [...new Set(t.map(r))];
			return [
				`${V(e)} · ${I(e)}`,
				p(e),
				e.reason || e.message || "",
				`开始：${M(e.started_at)}`,
				`结束：${M(e.completed_at)}`,
				`耗时：${d(e)}`,
				i.length ? `已记录阶段：${i.join("、")}` : "",
				n.length ? `子步骤（${n.length}）` : "",
				...n.map((e) => `${V(e)} · ${I(e)} · ${d(e)}${e.reason || e.message ? `\n${e.reason || e.message}` : ""}`),
				t.length ? `阶段事件（${t.length} 条）` : "",
				...t.map((e, t) => `${t + 1}. ${r(e)} · ${F(e.display_status || e.state)}${e.created_at ? ` · ${M(e.created_at)}` : e.event_time_known === !1 ? " · 发生时间未记录" : ""}${e.message ? `\n${e.message}` : ""}`),
				"点击步骤查看对应日志"
			].filter(Boolean).join("\n");
		}
		return (e, n) => (t(), D("div", ge, [
			o.value.length ? (t(), D("p", _e, "阶段按首次记录排列，位置相邻不代表固定执行顺序。")) : l("", !0),
			_("ul", ve, [(t(!0), D(f, null, a(o.value, (e) => (t(), D("li", {
				key: T(B)(e),
				class: x(`is-${T(P)(e)}`)
			}, [_("button", {
				type: "button",
				title: v(e),
				onClick: (t) => i("log", T(B)(e))
			}, [
				_("strong", null, h(T(V)(e)), 1),
				_("small", null, h(T(I)(e)), 1),
				_("small", be, "耗时 " + h(d(e)), 1),
				(t(!0), D(f, null, a(T(R)(e), (e) => (t(), D("small", { key: e }, h(e), 1))), 128)),
				p(e) ? (t(), D("small", xe, h(p(e)), 1)) : l("", !0)
			], 8, ye), _("button", {
				type: "button",
				"aria-label": `查看${T(V)(e)}的关系与证据`,
				onClick: (t) => s.value = e
			}, "详情", 8, Se)], 2))), 128))]),
			o.value.length ? (t(), D("details", Ce, [n[3] ||= _("summary", null, "依赖与执行记录", -1), (t(!0), D(f, null, a(o.value, (e) => (t(), D("div", { key: T(B)(e) }, [_("strong", null, h(T(V)(e)), 1), c(L, {
				step: e,
				siblings: o.value
			}, null, 8, ["step", "siblings"])]))), 128))])) : l("", !0),
			_("dialog", {
				ref_key: "dialog",
				ref: u,
				class: "registration-dialog",
				"aria-label": "注册步骤关系与证据",
				onCancel: n[1] ||= b((e) => s.value = void 0, ["prevent"]),
				onClose: n[2] ||= (e) => s.value = void 0
			}, [
				_("header", null, [_("h3", null, h(s.value ? T(V)(s.value) : "步骤详情"), 1), _("button", {
					type: "button",
					onClick: n[0] ||= (e) => s.value = void 0
				}, "关闭")]),
				s.value && p(s.value) ? (t(), D("p", we, h(p(s.value)), 1)) : l("", !0),
				s.value ? (t(), g(z, {
					key: 1,
					step: s.value,
					siblings: o.value
				}, null, 8, ["step", "siblings"])) : l("", !0)
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
function Ne(e) {
	let t = e.api || De(), n = m(!!e.visible), r = m(!document.hidden), i = !1, a = S(() => n.value && r.value && !i), o = s({
		jobs: [],
		total: 0,
		batch: null,
		batches: [],
		meta: null,
		summary: null,
		view: e.view || "launch",
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
	}), c = S(() => o.creating), l = S(() => {
		let e = o.meta?.capabilities?.features?.register;
		return e?.enabled === !1 ? String(e.reason || "功能缺少必要配置") : "";
	}), u = (t) => e.notify?.(t), d = 0, f = 0, p = 0, h = 0, g = 0, _, v, b, x, C, w, ee, T, E = "", D = 0, k = 0, A = !0, j, te = /* @__PURE__ */ new Map(), ne = () => !i && r.value && o.detail.id !== null, M = (e, t) => ne() && e === g && String(o.detail.id) === String(t);
	function re() {
		d++, x?.controller.abort(), x = void 0, o.loading = !1;
	}
	function ie() {
		re(), p++, C?.controller.abort(), C = void 0, h++, w?.controller.abort(), w = void 0;
	}
	function N() {
		window.clearInterval(_), window.clearInterval(v), _ = v = void 0;
	}
	function ae() {
		if (!a.value) return !1;
		if (o.view === "tasks") return !0;
		let e = o.batch;
		return !e || String(e.batch_id) !== o.batchId || e.projection_delayed ? !0 : Z.some((t) => Number(e.status_counts?.[t] || 0) > 0) || e.items.some((e) => Z.includes(String(e.status || "")));
	}
	function oe(e) {
		for (let t of Object.keys(Ae())) {
			let n = e[t];
			if (n !== void 0) {
				if (t === "page" || t === "page_size") {
					let e = Number(n);
					Number.isSafeInteger(e) && e > 0 && (o.query[t] = t === "page_size" ? Math.min(e, 500) : e);
				} else o.query[t] = String(n);
			}
		}
		if (e.progress_batch_id !== void 0) {
			let t = je(e.progress_batch_id);
			t !== o.batchId && (o.batchId = t, o.batch = null);
		}
	}
	function P(e = {}) {
		if (oe(e), !a.value || e.automatic && !ae()) return Promise.resolve();
		let n = JSON.stringify({
			view: o.view,
			batchId: o.batchId,
			...o.query
		});
		if ((e.automatic || e.coalesce) && x?.signature === n) return x.promise;
		x?.controller.abort();
		let r = ++d, i = new AbortController(), s = o.view;
		e.automatic || f++;
		let c = f;
		o.loading = !0, o.error = "";
		let l = () => a.value && r === d && s === o.view, u = (async () => {
			try {
				for (let r = 0; r < 2; r++) {
					let a = {
						paged: 1,
						...o.query,
						view: s === "tasks" ? "table" : "batch",
						progress_batch_id: o.batchId,
						refresh_generation: c
					};
					s === "tasks" && e.automatic && E === n && Date.now() - D < 3e4 && (a.include_facets = 0);
					let u = await t.jobs(a, i.signal);
					if (!l()) return;
					if (Object.prototype.hasOwnProperty.call(u, "status_counts") && (o.statusCounts = u.status_counts || {}), s === "launch") {
						o.batches = u.progress_batches || [];
						let e = u.progress_batch || null;
						if (!e && o.batchId) {
							let e = je(o.batches[0]?.batch_id);
							if (e !== o.batchId && (o.batchId = e, o.batch = null, e && !r)) continue;
						}
						!o.batchId && e?.batch_id && (o.batchId = je(e.batch_id)), o.batch = e;
					} else {
						o.total = Math.max(0, Number(u.total ?? u.items?.length ?? 0) || 0), Object.prototype.hasOwnProperty.call(u, "facets") && (o.facets = u.facets || {}, E = n, D = Date.now());
						let e = Math.max(1, Math.ceil(o.total / o.query.page_size));
						if (o.query.page > e) {
							if (o.query.page = e, !r) continue;
							throw Error("列表范围已变化，请刷新后重试");
						}
						o.jobs = u.items || [];
					}
					return;
				}
			} catch (e) {
				l() && !H(e) && (o.error = Q(e));
			} finally {
				r === d && (o.loading = !1, x = void 0);
			}
		})();
		return x = {
			version: r,
			signature: n,
			promise: u,
			controller: i
		}, u;
	}
	function F(e) {
		return P({ progress_batch_id: je(e) });
	}
	function I(e) {
		return P({
			...e,
			page: e.page ?? 1
		});
	}
	function L(e) {
		return P({ page: e });
	}
	function se(e) {
		return P({
			page: 1,
			page_size: e
		});
	}
	function R(e) {
		o.summary = e;
	}
	function z(e) {
		o.summary = {
			...o.summary || {},
			email_supply: e || {}
		};
	}
	function B() {
		if (!a.value) return Promise.resolve();
		C?.controller.abort();
		let e = ++p, n = new AbortController(), r = (async () => {
			try {
				let r = await t.summary(n.signal);
				e === p && a.value && R(r);
			} catch (t) {
				e === p && a.value && !H(t) && z({
					status: "error",
					reason: "本地库存读取失败，请稍后重试"
				});
			} finally {
				e === p && (C = void 0);
			}
		})();
		return C = {
			version: e,
			promise: r,
			controller: n
		}, r;
	}
	function V(e = !1) {
		if (e && (A = !0), !a.value || !A && o.meta && Date.now() - k < 3e4) return Promise.resolve();
		if (w && !e) return w.promise;
		w?.controller.abort();
		let n = ++h, r = new AbortController(), i = (async () => {
			try {
				let e = await t.metadata(r.signal);
				if (n !== h || !a.value) return;
				let i = e.capabilities?.email_sources || {};
				o.meta = {
					...e,
					sources: (e.sources || []).map((e) => ({
						...e,
						...i[e.value] || {}
					}))
				}, k = Date.now(), A = !1;
			} catch (e) {
				n === h && a.value && !H(e) && (o.error = Q(e));
			} finally {
				n === h && (w = void 0);
			}
		})();
		return w = {
			version: n,
			promise: i,
			controller: r
		}, i;
	}
	function ce() {
		N(), a.value && (V(), P({ coalesce: !0 }), B(), _ = window.setInterval(() => {
			P({ automatic: !0 });
		}, 5e3), v = window.setInterval(() => {
			C || B();
		}, 1e4));
	}
	function le(e) {
		n.value !== e && (n.value = e, e ? ce() : (N(), ie()));
	}
	function U(e) {
		["launch", "tasks"].includes(e) && o.view !== e && (o.view = e, re(), P({ coalesce: !0 }));
	}
	function G(e, t = "已受理") {
		let n = e.message || e.warning || (e.started_count == null ? e.deleted_count == null ? e.cancelled == null ? t : `已取消 ${e.cancelled} 个排队任务` : `已删除 ${e.deleted_count} 个任务` : `已提交 ${e.started_count} 个失败任务`), r = Array.isArray(e.skipped) ? e.skipped.length : 0;
		o.receipt = {
			tone: e.warning ? "warning" : "success",
			message: String(n) + (r ? `，跳过 ${r} 个` : "")
		}, u(o.receipt.message);
	}
	function K(e) {
		let t = je(e.jobs?.[0]?.batch_id || e.job?.batch_id || e.batch_id);
		t && (o.batchId = t, o.batch = null);
	}
	function q(e, n = {}) {
		let r = JSON.stringify([e, n]), i = te.get(r);
		if (i) return i;
		o.pendingActions[r] = !0;
		let a = (async () => {
			try {
				let r = await t.action(e, n);
				return o.lastAction = r, K(r), G(r), /\/delete(?:-bulk)?$/.test(e) && o.detail.id !== null && (Array.isArray(r.deleted) ? r.deleted : r.deleted === !0 ? [e.split("/").at(-2)] : []).some((e) => String(e) === String(o.detail.id)) && pe(), P(), o.detail.id !== null && Y(), r;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: Q(e)
				}, u(o.receipt.message), e;
			} finally {
				te.delete(r), delete o.pendingActions[r];
			}
		})();
		return te.set(r, a), a;
	}
	function ue(e) {
		if (j) return j;
		if (l.value) {
			let e = l.value;
			return o.receipt = {
				tone: "warning",
				message: e
			}, u(e), Promise.reject(Error(e));
		}
		return !Number.isSafeInteger(e.count) || e.count < 1 || !Number.isSafeInteger(e.workers) || e.workers < 1 ? Promise.reject(/* @__PURE__ */ Error("注册数量与并发线程数必须为有效的正整数")) : (o.creating = !0, j = (async () => {
			try {
				let n = await t.create({ ...e });
				return o.lastCreate = n, K(n), G(n, `已提交 ${n.submitted || 0} 个任务`), P(), n;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: Q(e)
				}, u(o.receipt.message), e;
			} finally {
				o.creating = !1, j = void 0;
			}
		})(), j);
	}
	async function de(t, n, r = [], i = !1) {
		let a = o.batch?.items || [], s = t === "stopBatch" ? a.filter((e) => ["running", "stopping"].includes(String(e.status))) : t === "cancelBatch" ? a.filter((e) => e.status === "pending") : t === "retryBatch" ? a.filter((e) => ke.includes(String(e.status)) && e.retryable) : [], c = t === "retryBulk" || t === "deleteBulk" ? r.map((e) => W(e)) : s.map((e) => W(e.id));
		if ([
			"stopBatch",
			"cancelBatch",
			"retryBatch",
			"retryBulk",
			"deleteBulk"
		].includes(t) && !c.length) return u("当前没有可操作的任务"), null;
		if (["stopBatch", "cancelBatch"].includes(t) && !o.batchId) return null;
		if (t === "retry" && !n?.retryable) return u("该任务当前不可重试"), null;
		if ([
			"stop",
			"delete",
			"retry"
		].includes(t) && !n) throw Error("任务不存在");
		let l = {
			cancelAll: "取消所有排队任务",
			stopBatch: `停止当前批次的 ${c.length} 个运行中任务`,
			cancelBatch: `取消当前批次的 ${c.length} 个排队任务`,
			retryBatch: `重跑当前批次的 ${c.length} 个失败任务`,
			stop: `停止任务 #${n?.id}`,
			delete: `删除任务 #${n?.id} 与对应日志`,
			retry: `${n?.retry_label || "重试"}任务 #${n?.id}`,
			deleteBulk: `删除选中的 ${c.length} 个任务与对应日志`,
			retryBulk: `重试选中的 ${c.length} 个任务`
		}, d = t === "retry" && n?.retry_action === "codex" ? "仅补跑 Codex 授权" : t === "retry" && n?.retry_action === "twofa" ? "重新登录检查并补齐 Authenticator 2FA" : t === "retry" && n?.retry_action === "registration_resume" ? "使用已保存账号密码继续邮箱验证" : "有原邮箱则复用，没有原邮箱则重新领取；已创建账号的任务按缺失步骤补跑，不能重试的由后端校验", f = t === "retry" || t === "retryBulk" || t === "retryBatch" ? `\n${d}。原任务记录和日志会保留。` : t === "stop" || t === "stopBatch" ? "\n任务会在当前步骤检查点退出。" : t === "cancelAll" || t === "cancelBatch" ? "\n运行中的任务不受影响。" : "", p = encodeURIComponent(o.batchId), m = n ? $(n.id) : "";
		return await (e.confirm ? e.confirm(`确定${l[t]}吗？${f}`) : window.confirm(`确定${l[t]}吗？${f}`)) ? q(...{
			cancelAll: ["/api/jobs/cancel-pending", {}],
			stopBatch: [`/api/jobs/batches/${p}/stop`, {}],
			cancelBatch: [`/api/jobs/batches/${p}/cancel`, {}],
			retryBatch: ["/api/jobs/retry-bulk", {
				job_ids: c,
				debug_enabled: i
			}],
			stop: [`/api/jobs/${m}/stop`, {}],
			delete: [`/api/jobs/${m}/delete`, {}],
			retry: [`/api/jobs/${m}/retry`, { debug_enabled: i }],
			deleteBulk: ["/api/jobs/delete-bulk", { job_ids: c }],
			retryBulk: ["/api/jobs/retry-bulk", {
				job_ids: c,
				debug_enabled: i
			}]
		}[t]) : null;
	}
	function J() {
		g++, ee?.abort(), T?.abort(), ee = T = void 0, window.clearTimeout(b), b = void 0, o.detail.loading = !1, o.detail.comparing = !1;
	}
	async function Y() {
		if (!ne()) return;
		ee?.abort(), window.clearTimeout(b);
		let e = o.detail.id, n = ++g, r = new AbortController();
		ee = r, o.detail.loading = !0, o.detail.error = "";
		let i = () => M(n, e);
		try {
			let n = await t.log(e, r.signal);
			if (!i()) return;
			o.detail.job = n.job || null, o.detail.log = String(n.log || "");
			let a = await t.debug(e, r.signal);
			if (!i()) return;
			if (o.detail.debug = a?.enabled ? a : null, a?.enabled) o.detail.diagnostics = null;
			else {
				let n = await t.diagnostics(e, r.signal);
				if (!i()) return;
				o.detail.diagnostics = n;
			}
		} catch (e) {
			i() && !H(e) && (o.detail.error = Q(e));
		} finally {
			i() && (o.detail.loading = !1, Oe.includes(String(o.detail.job?.status || "")) || (b = window.setTimeout(() => void Y(), 2e3)));
		}
	}
	function fe(t, n) {
		let r = W(t), i = [...o.jobs, ...o.batch?.items || []].find((e) => String(e.id) === String(r));
		i?.operation_task_id && e.openTask ? e.openTask(i.operation_task_id, i.operation_run_id || null, n || null) : (J(), o.detail = {
			...Me(),
			id: r
		}, Y());
	}
	function pe() {
		J(), o.detail = Me();
	}
	async function me(e) {
		let n = W(e);
		if (!M(g, n)) return null;
		T?.abort();
		let r = new AbortController();
		T = r;
		let i = () => ne() && T === r && !r.signal.aborted && String(o.detail.id) === String(n);
		o.detail.comparing = !0, o.detail.compareError = "";
		try {
			let e = await t.compare(n, r.signal);
			return i() ? (o.detail.comparison = e, e) : null;
		} catch (e) {
			if (i() && !H(e)) throw o.detail.compareError = Q(e), e;
			return null;
		} finally {
			i() && (o.detail.comparing = !1, T = void 0);
		}
	}
	function he() {
		r.value = !document.hidden, r.value ? (ce(), o.detail.id !== null && Y()) : (N(), ie(), J());
	}
	function ge() {
		i = !0, N(), ie(), J(), document.removeEventListener("visibilitychange", he);
	}
	return document.addEventListener("visibilitychange", he), O() && y(ge), {
		state: o,
		active: a,
		creating: c,
		registrationUnavailable: l,
		ensureMeta: V,
		load: P,
		loadSummary: B,
		renderEmailSupply: z,
		applySummary: R,
		setVisible: le,
		setView: U,
		setBatch: F,
		updateQuery: I,
		setPage: L,
		setSize: se,
		shouldPollJobs: ae,
		create: ue,
		action: q,
		executeAction: de,
		compare: me,
		openLog: fe,
		refreshDetail: Y,
		closeDetail: pe,
		notify: u,
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
}, Dt = { key: 3 }, Ot = ["href"], kt = /* @__PURE__ */ e({
	__name: "RegistrationPage",
	props: { deps: {} },
	setup(e, { expose: s }) {
		let y = e, C = Ne(y.deps), { state: E } = C, O = ne({
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
		function j() {
			O.resetColumns(), y.deps.notify?.("已恢复默认列宽");
		}
		function M(e) {
			let t = e.status_counts || {}, n = Number(t.running || 0) + Number(t.stopping || 0), r = Number(t.pending || 0);
			return n + r > 0 ? `未完成 ${n + r}（运行 ${n} / 等待 ${r}）` : `成功 ${t.success || 0} · 失败 ${t.failed || 0}`;
		}
		let N = [
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
		], ae = m();
		ie(ae, () => E.detail.id !== null, () => C.active.value);
		let oe = m(1), P = m(3), F = m(""), I = m(!1), L = m(""), se = m(""), R = m(""), z = m(""), B = m(""), V = m(""), H = m(""), U = m(""), W = m(1), G = m(20), K = m(/* @__PURE__ */ new Set()), q = m({}), ue = S(() => E.view === "launch"), de = S(() => E.view === "tasks"), J = S(() => E.jobs), Y = m(null), fe = S(() => ({
			id: se.value,
			email: R.value,
			email_source: z.value,
			status: L.value,
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
		}, me = S(() => Object.entries(fe.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${pe[e]}：${e === "status" ? Z(t) : e === "email_source" ? De(t) : t}`,
			removeLabel: `清除${pe[e]}筛选`
		})));
		function ge(e, t) {
			let n = {
				id: se,
				email: R,
				email_source: z,
				status: L,
				proxy: B,
				error: V,
				date_from: H,
				date_to: U
			};
			n[e].value = t, Y.value = null, kt();
		}
		let _e = (e) => e.error_info ? ce(e.error_info) : e.error_message ? "执行异常" : "—", ve = m(""), ye = S(() => E.statusCounts.active ?? [
			"pending",
			"running",
			"stopping"
		].reduce((e, t) => e + Number((Object.keys(E.statusCounts).length ? E.statusCounts : E.batch?.status_counts || {})[t] || 0), 0)), be = S(() => !!E.meta?.manual_mode), xe = S(() => {
			let e = new Map((E.meta?.sources || []).map((e) => [String(e.value), {
				value: String(e.value),
				label: e.label || String(e.value)
			}])), t = E.facets.email_source;
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
		}), Se = S(() => be.value ? [{
			value: "manual",
			label: "手动配置邮箱"
		}] : E.meta?.sources?.filter((e) => e.enabled === !0) || []), Ce = S(() => E.summary?.email_supply || {}), we = (e) => {
			let t = Ce.value[e];
			return Number.isInteger(t) && Number(t) >= 0 ? t : Ce.value.status === "error" ? "读取失败" : "未知";
		}, X = S(() => `仅统计本地库存；用完后请手动导入；邮箱由 Email Butler 等邮箱服务准备${Ce.value.reason ? `；${Ce.value.reason}` : ""}`), Ee = (e) => E.meta?.registration_drivers?.find((t) => String(t.value) === String(e))?.label || {
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
		})[String(e)] || String(e || "等待中"), Oe = async (e) => y.deps.confirm ? await y.deps.confirm(e) : window.confirm(e);
		function ke(e) {
			e || (Y.value = null), C.setVisible(e);
		}
		function Ae(e) {
			Y.value = null, C.setView(e);
		}
		function Q(e) {
			let t = ae.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && C.closeDetail();
		}
		async function je() {
			if (C.registrationUnavailable.value) {
				E.receipt = {
					tone: "warning",
					message: C.registrationUnavailable.value
				};
				return;
			}
			let e = Number(oe.value), t = Number(P.value);
			if (!Number.isSafeInteger(e) || e < 1) E.receipt = {
				tone: "warning",
				message: "注册数量必须为有效的正整数"
			};
			else if (!Number.isSafeInteger(t) || t < 1) E.receipt = {
				tone: "warning",
				message: "并发线程数必须为有效的正整数"
			};
			else if (!F.value) E.receipt = {
				tone: "warning",
				message: "请选择本次注册使用的邮箱来源"
			};
			else if (!(ye.value > 0 && !await Oe(`当前任务表里已有 ${ye.value} 个任务在跑或排队，这次会再加 ${e} 个，确定继续？`))) try {
				let n = await C.create({
					count: e,
					workers: t,
					email_source: F.value,
					debug_enabled: I.value
				});
				Number.isSafeInteger(n?.workers) && n.workers > 0 && (P.value = n.workers);
			} catch {}
		}
		async function $(e, t) {
			let n = Array.from(K.value);
			try {
				await C.executeAction(e, t, n, I.value), (e === "deleteBulk" || e === "retryBulk") && (K.value = /* @__PURE__ */ new Set());
			} catch {}
		}
		function Me() {
			L.value = se.value = R.value = z.value = B.value = V.value = H.value = U.value = "", W.value = 1, C.load(It());
		}
		function kt() {
			W.value = 1, C.load(It());
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
			ve.value = e, W.value = 1, C.setBatch(e);
		}
		function It() {
			return {
				status: L.value,
				id: se.value,
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
			t ? C.action("/api/manual-otp", {
				email: e.email,
				code: t,
				job_id: e.id
			}).then(() => {
				q.value = {
					...q.value,
					[String(e.id)]: ""
				};
			}).catch(() => {}) : E.receipt = {
				tone: "warning",
				message: "请先填写邮箱验证码"
			};
		}
		async function Rt() {
			if (E.detail.id != null) try {
				await C.compare(E.detail.id);
			} catch {}
		}
		return s({
			create: C.create,
			runAction: C.executeAction,
			setBatch: C.setBatch,
			loadSources: () => C.ensureMeta(!0),
			load: C.load,
			ensureMeta: C.ensureMeta,
			setVisible: ke,
			setView: Ae,
			loadSummary: C.loadSummary,
			renderEmailSupply: C.renderEmailSupply,
			applySummary: C.applySummary,
			action: C.action,
			openLog: C.openLog,
			closeDetail: C.closeDetail
		}), r(() => ({ ...E.query }), (e) => {
			W.value = e.page, G.value = e.page_size, se.value = e.id, R.value = e.email, z.value = e.email_source, L.value = e.status, B.value = e.proxy, V.value = e.error, H.value = e.date_from, U.value = e.date_to;
		}, { immediate: !0 }), r(() => E.batchId, (e) => {
			ve.value = e;
		}, { immediate: !0 }), r([be, Se], () => {
			be.value ? F.value = "manual" : Se.value.some((e) => e.value === F.value) || (F.value = "");
		}, { immediate: !0 }), o(() => {
			C.ensureMeta();
		}), (e, r) => (t(), D("div", {
			class: "registration-vue-page",
			"data-view": T(E).view
		}, [
			i(_("section", Fe, [
				_("div", Ie, [
					_("div", null, [r[20] ||= _("span", null, "已注册", -1), _("strong", null, h(T(E).summary?.accounts ?? 0), 1)]),
					_("div", null, [r[21] ||= _("span", null, "本地邮箱总数", -1), _("strong", null, h(we("total")), 1)]),
					_("div", null, [r[22] ||= _("span", null, "本地可用", -1), _("strong", null, h(we("available")), 1)]),
					_("div", null, [r[23] ||= _("span", null, "已用", -1), _("strong", null, h(we("used")), 1)]),
					_("div", null, [r[24] ||= _("span", null, "失败", -1), _("strong", null, h(we("failed")), 1)])
				]),
				_("p", Le, h(X.value), 1),
				_("div", Re, [
					_("label", null, [r[26] ||= k("邮箱来源", -1), i(_("select", {
						"onUpdate:modelValue": r[0] ||= (e) => F.value = e,
						disabled: !T(E).meta || be.value
					}, [r[25] ||= _("option", { value: "" }, "请选择本次邮箱来源", -1), (t(!0), D(f, null, a(Se.value, (e) => (t(), D("option", {
						key: String(e.value),
						value: String(e.value)
					}, h(e.label || e.value), 9, Be))), 128))], 8, ze), [[u, F.value]])]),
					_("label", null, [r[27] ||= k("注册数量", -1), i(_("input", {
						"onUpdate:modelValue": r[1] ||= (e) => oe.value = e,
						min: "1",
						type: "number"
					}, null, 512), [[
						w,
						oe.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", null, [r[28] ||= k("并发线程", -1), i(_("input", {
						"onUpdate:modelValue": r[2] ||= (e) => P.value = e,
						min: "1",
						step: "1",
						type: "number"
					}, null, 512), [[
						w,
						P.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", Ve, [i(_("input", {
						"onUpdate:modelValue": r[3] ||= (e) => I.value = e,
						type: "checkbox"
					}, null, 512), [[v, I.value]]), r[29] ||= k(" 调试模式", -1)]),
					_("button", {
						type: "button",
						class: "jobs-tb-btn jobs-tb-btn--primary",
						disabled: T(E).creating || !!T(C).registrationUnavailable.value,
						title: T(C).registrationUnavailable.value || void 0,
						onClick: je
					}, "开始注册", 8, He)
				]),
				T(C).registrationUnavailable.value ? (t(), D("p", Ue, h(T(C).registrationUnavailable.value), 1)) : l("", !0),
				T(E).batch || T(E).batches.length ? (t(), D("div", We, [_("header", null, [
					r[30] ||= _("strong", null, "任务批次进度", -1),
					_("span", null, h(T(E).batch?.items?.length || 0) + " / " + h(T(E).batch?.total || T(E).batch?.items?.length || 0), 1),
					T(E).batches.length ? i((t(), D("select", {
						key: 0,
						"onUpdate:modelValue": r[4] ||= (e) => ve.value = e,
						onChange: r[5] ||= (e) => Ft(ve.value),
						"aria-label": "选择任务批次"
					}, [(t(!0), D(f, null, a(T(E).batches, (e) => (t(), D("option", {
						key: String(e.batch_id),
						value: String(e.batch_id)
					}, h(e.batch_id) + " · " + h(M(e)) + " · " + h(e.total || e.items?.length || 0) + " 个", 9, Ge))), 128))], 544)), [[u, ve.value]]) : l("", !0),
					_("button", {
						type: "button",
						onClick: r[6] ||= (e) => $("stopBatch")
					}, "停止"),
					_("button", {
						type: "button",
						onClick: r[7] ||= (e) => $("cancelBatch")
					}, "取消"),
					_("button", {
						type: "button",
						onClick: r[8] ||= (e) => $("retryBatch")
					}, "重跑失败")
				]), (t(!0), D(f, null, a(T(E).batch?.items || [], (e, n) => (t(), D("article", {
					key: String(e.id),
					class: "registration-batch-card"
				}, [
					_("div", null, [
						_("strong", null, "#" + h(n + 1) + " " + h(e.email || "准备邮箱中…"), 1),
						_("span", null, h(Z(e.display_status || e.status)), 1),
						_("button", {
							type: "button",
							onClick: (t) => T(C).openLog(e.id)
						}, "查看日志", 8, Ke),
						e.retryable ? (t(), D("button", {
							key: 0,
							type: "button",
							onClick: (t) => $("retry", e)
						}, "重试", 8, qe)) : l("", !0)
					]),
					_("small", null, h(De(e.email_source)) + " · " + h(Ee(e.registration_driver)) + " · " + h(e.error_message || ""), 1),
					c(Te, {
						job: e,
						active: T(C).active.value,
						onLog: (t) => T(C).openLog(e.id, t)
					}, null, 8, [
						"job",
						"active",
						"onLog"
					]),
					Nt(e).length || Pt(e).length ? (t(), D("details", Je, [
						r[31] ||= _("summary", null, "尝试与线路记录", -1),
						(t(!0), D(f, null, a(Nt(e), (e) => (t(), D("div", { key: String(e.id || e.attempt_id) }, h(Z(e.status)) + " · " + h(e.error_message || "已记录"), 1))), 128)),
						(t(!0), D(f, null, a(Pt(e), (e) => (t(), D("div", { key: String(e.route_attempt_no) }, h(`线路尝试 ${e.route_attempt_no || 1}`) + " · " + h(e.retry_reason || Z(e.status)), 1))), 128))
					])) : l("", !0)
				]))), 128))])) : l("", !0)
			], 512), [[ee, ue.value]]),
			i(_("section", Ye, [
				_("div", Xe, [
					_("button", {
						type: "button",
						onClick: r[9] ||= (e) => $("retryBulk"),
						disabled: !K.value.size
					}, "重试", 8, Ze),
					_("button", {
						type: "button",
						onClick: r[10] ||= (e) => $("deleteBulk"),
						disabled: !K.value.size
					}, "删除", 8, Qe),
					_("button", {
						type: "button",
						onClick: r[11] ||= (e) => $("cancelAll")
					}, "取消排队"),
					_("button", {
						type: "button",
						onClick: kt
					}, "刷新")
				]),
				_("div", $e, [_("div", et, [_("span", tt, "共 " + h(T(E).total.toLocaleString()) + " 条任务", 1), c(te, {
					items: me.value,
					onRemove: r[12] ||= (e) => ge(e, "")
				}, null, 8, ["items"])]), _("div", nt, [
					_("button", {
						type: "button",
						"aria-label": "恢复注册任务列宽",
						onClick: j
					}, "恢复列宽"),
					_("span", rt, [c(he, {
						values: fe.value,
						sources: xe.value,
						open: Y.value === "all",
						"onUpdate:open": r[13] ||= (e) => Y.value = e ? "all" : null,
						onChange: ge
					}, null, 8, [
						"values",
						"sources",
						"open"
					])]),
					me.value.length ? (t(), D("button", {
						key: 0,
						type: "button",
						onClick: Me
					}, "清筛")) : l("", !0)
				])]),
				T(E).error ? (t(), D("div", it, [k(h(T(E).error) + " ", 1), _("button", {
					type: "button",
					onClick: kt
				}, "重试")])) : l("", !0),
				_("div", at, [_("table", {
					class: "jobs-table-v2",
					style: p({ width: `${T(O).total.value}px` })
				}, [
					_("colgroup", null, [(t(!0), D(f, null, a(T(O).widths.value, (e, n) => (t(), D("col", {
						key: n,
						style: p({ width: `${e}px` })
					}, null, 4))), 128))]),
					_("thead", null, [_("tr", null, [(t(), D(f, null, a(N, (e, n) => _("th", { key: e.label }, [n === 0 ? (t(), D("input", {
						key: 0,
						type: "checkbox",
						"aria-label": "选择本页可操作任务",
						onChange: At
					}, null, 32)) : e.filter ? (t(), g(he, {
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
					])) : (t(), D("span", ot, h(e.label), 1)), n < N.length - 1 ? (t(), D("button", {
						key: 3,
						type: "button",
						class: "registration-column-resize",
						"aria-label": `调整${e.label}列宽，方向键调整`,
						onPointerdown: b((e) => T(O).resize(n, e), ["prevent"]),
						onKeydown: [d(b((e) => T(O).resizeWithKeyboard(n, -10), ["prevent"]), ["left"]), d(b((e) => T(O).resizeWithKeyboard(n, 10), ["prevent"]), ["right"])]
					}, null, 40, st)) : l("", !0)])), 64))])]),
					_("tbody", null, [T(E).loading ? (t(), D("tr", ct, [...r[32] ||= [_("td", { colspan: "11" }, "正在加载任务…", -1)]])) : J.value.length ? l("", !0) : (t(), D("tr", lt, [...r[33] ||= [_("td", { colspan: "11" }, "暂无匹配任务", -1)]])), (t(!0), D(f, null, a(J.value, (e) => (t(), D("tr", { key: String(e.id) }, [
						_("td", null, [_("input", {
							type: "checkbox",
							"aria-label": `选择任务 ${e.id}`,
							checked: K.value.has(String(e.id)),
							disabled: ["running", "stopping"].includes(String(e.status)),
							onChange: (t) => jt(e.id, t)
						}, null, 40, ut)]),
						_("td", null, [c(A, {
							text: `#${e.id}`,
							secondary: e.parent_job_id ? `↳ #${e.parent_job_id}` : void 0
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(A, { text: String(e.email || "-") }, null, 8, ["text"])]),
						_("td", null, [c(A, { text: De(e.email_source) }, null, 8, ["text"])]),
						_("td", null, [c(A, { text: Ee(e.registration_driver) }, null, 8, ["text"])]),
						_("td", null, [c(A, {
							text: Mt(e),
							secondary: String(e.proxy_status || "")
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(A, { text: Z(e.debug_state === "paused" ? "debug_paused" : e.display_status || e.status) }, null, 8, ["text"])]),
						_("td", null, [c(A, { text: String(e.started_at || "-") }, null, 8, ["text"])]),
						_("td", null, [c(A, { text: String(e.completed_at || "-") }, null, 8, ["text"])]),
						_("td", null, [e.error_message || e.error_info ? (t(), g(re, {
							key: 0,
							"data-registration-result": "",
							label: _e(e),
							title: String(e.error_message || _e(e)),
							tone: "danger"
						}, {
							details: n(() => [_("p", null, h(e.error_message || _e(e)), 1), e.error_info ? (t(), D("p", dt, h(e.error_info), 1)) : l("", !0)]),
							_: 2
						}, 1032, ["label", "title"])) : (t(), g(A, {
							key: 1,
							text: "—"
						}))]),
						_("td", ft, [
							_("button", {
								type: "button",
								onClick: (t) => T(C).openLog(e.id)
							}, "日志", 8, pt),
							e.manual_otp_required && e.status === "running" ? (t(), D(f, { key: 0 }, [i(_("input", {
								"onUpdate:modelValue": (t) => q.value[String(e.id)] = t,
								placeholder: "邮箱验证码"
							}, null, 8, mt), [[w, q.value[String(e.id)]]]), _("button", {
								type: "button",
								onClick: (t) => Lt(e)
							}, "提交验证码", 8, ht)], 64)) : l("", !0),
							[
								"pending",
								"running",
								"stopping"
							].includes(String(e.status)) ? (t(), D("button", {
								key: 1,
								type: "button",
								onClick: (t) => $("stop", e)
							}, "停止", 8, gt)) : l("", !0),
							e.retryable ? (t(), D("button", {
								key: 2,
								type: "button",
								onClick: (t) => $("retry", e)
							}, "重试", 8, _t)) : l("", !0),
							_("button", {
								type: "button",
								disabled: ["running", "stopping"].includes(String(e.status)),
								onClick: (t) => $("delete", e)
							}, "删除", 8, vt)
						])
					]))), 128))])
				], 4)]),
				c(le, {
					label: "注册任务分页",
					page: W.value,
					size: G.value,
					total: T(E).total,
					busy: T(E).loading,
					"onUpdate:page": r[14] ||= (e) => {
						W.value = e, T(C).load(It());
					},
					"onUpdate:size": r[15] ||= (e) => {
						G.value = e, W.value = 1, T(C).load(It());
					}
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			], 512), [[ee, de.value]]),
			T(E).receipt ? (t(), D("div", {
				key: 0,
				class: x(["registration-receipt", `is-${T(E).receipt.tone}`]),
				role: "status"
			}, h(T(E).receipt.message), 3)) : l("", !0),
			_("dialog", {
				ref_key: "logDialog",
				ref: ae,
				class: "registration-dialog",
				"aria-labelledby": "registration-log-title",
				onCancel: r[18] ||= b((...e) => T(C).closeDetail && T(C).closeDetail(...e), ["prevent"]),
				onClose: r[19] ||= (...e) => T(C).closeDetail && T(C).closeDetail(...e),
				onClick: Q
			}, [
				_("header", null, [_("h2", yt, "任务 #" + h(T(E).detail.id) + " 日志", 1), _("button", {
					type: "button",
					onClick: r[16] ||= (...e) => T(C).closeDetail && T(C).closeDetail(...e)
				}, "关闭")]),
				T(E).detail.loading ? (t(), D("p", bt, "加载中…")) : l("", !0),
				T(E).detail.error ? (t(), D("p", xt, h(T(E).detail.error), 1)) : l("", !0),
				_("pre", null, h(T(E).detail.log || "（暂无日志）"), 1),
				T(E).detail.debug?.enabled ? (t(), D("div", St, [
					r[34] ||= _("strong", null, "网络调试", -1),
					_("button", {
						type: "button",
						disabled: T(E).detail.comparing,
						onClick: Rt
					}, "与同批成功任务对比", 8, Ct),
					_("a", {
						href: `/api/jobs/${T(E).detail.id}/debug/har`,
						download: ""
					}, "下载脱敏 HAR", 8, wt),
					_("button", {
						type: "button",
						onClick: r[17] ||= (e) => T(C).action(`/api/jobs/${T(E).detail.id}/debug/release`, { action: "finish" })
					}, "结束调试并收口"),
					T(E).detail.comparison ? (t(), D("pre", Tt, h(T(E).detail.comparison), 1)) : l("", !0),
					T(E).detail.compareError ? (t(), D("p", Et, h(T(E).detail.compareError), 1)) : l("", !0)
				])) : l("", !0),
				T(E).detail.diagnostics?.captured ? (t(), D("div", Dt, [
					r[36] ||= _("strong", null, "失败诊断", -1),
					T(E).detail.diagnostics.screenshot_url ? (t(), D("a", {
						key: 0,
						href: String(T(E).detail.diagnostics.screenshot_url),
						target: "_blank",
						rel: "noopener"
					}, "打开失败截图", 8, Ot)) : l("", !0),
					_("details", null, [r[35] ||= _("summary", null, "完整诊断证据", -1), _("pre", null, h(T(E).detail.diagnostics), 1)])
				])) : l("", !0)
			], 544)
		], 8, Pe));
	}
});
// src/registration.ts
function At(e, t = {}) {
	let n = C(kt, { deps: {
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
