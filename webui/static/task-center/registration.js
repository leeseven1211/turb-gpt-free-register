import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, S as c, _ as l, a as u, c as d, d as f, dt as p, et as m, ft as h, g, h as _, i as v, j as y, l as b, lt as x, m as S, n as C, o as w, s as T, st as E, t as D, v as O, w as ee, x as k } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { i as A, n as j, r as M, t as te } from "./ListFilterSummary-C7d1AuNG.js";
import { n as ne, t as re } from "./ColumnResizer-C9MIqUB3.js";
import { t as ie } from "./ListResult-DyZgA5Vb.js";
import { n as N, r as ae } from "./client-B5R_MNgP.js";
import { t as oe } from "./errorLabels-Co3XCR-i.js";
import { n as P, t as F } from "./time-DOD6oyhP.js";
import { A as se, C as I, _ as L, a as R, b as z, g as ce, i as B, m as V, n as H, o as U, t as W, v as G, x as K, y as q } from "./StepEvidence-BMpneWSv.js";
import { t as J } from "./useNativeDialog-DWisXYg9.js";
import { t as le } from "./ListPagination-DkDYBtdx.js";
import { a as Y, r as ue } from "./taskIds-BlchWwUp.js";
// src/features/registration/RegistrationFilters.vue?vue&type=script&setup=true&lang.ts
var de = { class: "registration-filter-fields" }, fe = { key: 0 }, X = ["value"], pe = ["value", "aria-label"], me = ["value"], he = ["value"], Z = ["value"], ge = [
	"type",
	"value",
	"aria-label"
], _e = { class: "list-filter-actions" }, ve = /*#__PURE__*/ D(/* @__PURE__ */ e({
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
		return (r, s) => (t(), g(A, {
			label: e.column ? o[e.column] : "注册任务",
			"trigger-label": e.column ? o[e.column] : "筛选",
			active: e.column ? !!e.values[e.column] : Object.values(e.values).some(Boolean),
			summary: y.value,
			open: e.open,
			"onUpdate:open": s[7] ||= (e) => c("update:open", e)
		}, {
			default: n(() => [_("div", de, [
				e.column ? l("", !0) : (t(), O("label", fe, [s[8] ||= k("筛选列", -1), i(_("select", {
					"onUpdate:modelValue": s[0] ||= (e) => p.value = e,
					"aria-label": "选择注册任务筛选列"
				}, [(t(), O(f, null, a(o, (e, t) => _("option", {
					key: t,
					value: t
				}, h(e), 9, X)), 64))], 512), [[u, p.value]])])),
				_("label", null, [k(h(o[v.value]) + " ", 1), v.value === "email_source" ? (t(), O("select", {
					key: 0,
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[1] ||= (e) => C(e.target.value)
				}, [s[9] ||= _("option", { value: "" }, "全部邮箱来源", -1), (t(!0), O(f, null, a(e.sources, (e) => (t(), O("option", {
					key: e.value,
					value: e.value
				}, h(e.label || e.value), 9, me))), 128))], 40, pe)) : v.value === "status" ? (t(), O("select", {
					key: 1,
					value: y.value,
					"aria-label": "筛选状态值",
					onChange: s[2] ||= (e) => C(e.target.value)
				}, [s[10] ||= _("option", { value: "" }, "全部状态", -1), (t(!0), O(f, null, a(b.value, (e) => (t(), O("option", {
					key: e,
					value: e
				}, h(x(e)), 9, Z))), 128))], 40, he)) : (t(), O("input", {
					key: 2,
					type: v.value.startsWith("date_") ? "date" : "search",
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[3] ||= (e) => C(e.target.value),
					onKeydown: s[4] ||= d((e) => c("update:open", !1), ["enter"])
				}, null, 40, ge))]),
				_("div", _e, [_("button", {
					type: "button",
					onClick: s[5] ||= (e) => C("")
				}, "清除此列"), _("button", {
					type: "button",
					class: "list-filter-primary",
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
}), [["__scopeId", "data-v-e4a53bb8"]]), ye = { class: "registration-progress" }, be = {
	key: 0,
	class: "registration-stage-heading"
}, xe = { key: 0 }, Se = [
	"title",
	"aria-pressed",
	"onClick"
], Ce = { class: "registration-step-title" }, we = {
	key: 0,
	class: "registration-step-mark",
	"aria-hidden": "true"
}, Te = {
	key: 1,
	class: "registration-step-mark",
	"aria-hidden": "true"
}, Ee = {
	key: 2,
	class: "registration-step-dot is-pulse",
	"aria-hidden": "true"
}, De = {
	key: 3,
	class: "registration-step-dot is-warning",
	"aria-hidden": "true"
}, Oe = {
	key: 4,
	class: "registration-step-dot is-muted",
	"aria-hidden": "true"
}, ke = { class: "registration-step-name" }, Ae = { class: "registration-step-meta" }, je = { class: "registration-step-state" }, Me = { "data-registration-step-duration": "" }, Ne = {
	key: 0,
	class: "registration-step-pause"
}, Pe = {
	key: 1,
	class: "registration-step-dep"
}, Fe = ["aria-label", "onClick"], Ie = ["data-tone"], Le = {
	class: "registration-stage-selected-info",
	"aria-live": "polite"
}, Q = { class: "registration-stage-selected-head" }, Re = { class: "registration-stage-selected-state" }, ze = { key: 0 }, Be = { key: 1 }, Ve = { class: "registration-batch-actions registration-stage-selected-actions" }, He = ["aria-label"], Ue = {
	key: 3,
	class: "registration-step-note"
}, We = {
	key: 4,
	class: "registration-relations-details"
}, Ge = { class: "registration-relations-list" }, Ke = { class: "registration-relations-head" }, qe = { class: "registration-relations-state" }, Je = { class: "registration-dialog-title" }, Ye = ["data-tone"], Xe = { class: "registration-dialog-body" }, Ze = {
	key: 0,
	class: "registration-dialog-pause"
}, Qe = /* @__PURE__ */ e({
	__name: "RegistrationProgress",
	props: {
		job: {},
		active: { type: Boolean },
		inline: { type: Boolean },
		focusFailure: { type: Boolean }
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
			return U(e.map((e, t) => ({
				...e,
				id: String(e.id || e.step_id || e.key || `step-${t + 1}`),
				label: e.label || e.name || e.id || e.step_id
			})));
		}), s = m(), u = m(), d = m(), v = S(() => {
			if (!r.inline) return;
			if (d.value) return o.value.find((e) => q(e) === d.value);
			if (!r.focusFailure) return;
			let e = String(V(r.job?.progress?.failure).step_id || "");
			return o.value.find((t) => q(t) === e) || o.value.find((e) => K(e) === "failed");
		});
		function y(e) {
			r.inline ? d.value = q(e) : i("log", q(e));
		}
		J(u, () => !!s.value && r.active, () => r.active);
		let C = (e) => se(G(e)), w = S(() => {
			let e = o.value.length;
			return e <= 1 ? 1 : e === 2 ? 2 : e === 3 || e === 6 ? 3 : e === 4 || e === 7 || e === 8 ? 4 : 5;
		});
		function T(e) {
			let t = [];
			return e.depends_on?.length && t.push("前置：" + e.depends_on.map((e) => {
				let t = o.value.find((t) => t.id === e || q(t) === e);
				return t ? z(t) : e;
			}).join("、")), e.execution?.condition?.label && t.push("条件：" + e.execution.condition.label), e.execution?.parallel_group && t.push("并行：" + e.execution.parallel_group), t.join(" · ");
		}
		function D(e) {
			let t = u.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && (s.value = void 0);
		}
		function ee(e) {
			let t = V(e.debug_pause);
			return t.state === "paused" ? `调试暂停 · 等待结束调试${t.paused_at ? ` · 暂停于 ${P(t.paused_at)}` : " · 暂停时间未记录"}${t.hold_until ? ` · 保留至 ${P(t.hold_until)}` : ""}` : "";
		}
		function k(e) {
			let t = e.attempts || [], n = e.children || [], i = (e) => e.raw_stage_label || n.find((t) => t.id === e.raw_stage)?.label || e.raw_stage || "阶段", a = [...new Set(t.map(i))];
			return [
				`${z(e)} · ${R(e)}`,
				ee(e),
				e.reason || e.message || "",
				`开始：${P(e.started_at)}`,
				`结束：${P(e.completed_at)}`,
				`耗时：${C(e)}`,
				a.length ? `已记录阶段：${a.join("、")}` : "",
				n.length ? `子步骤（${n.length}）` : "",
				...n.map((e) => `${z(e)} · ${R(e)} · ${C(e)}${e.reason || e.message ? `\n${e.reason || e.message}` : ""}`),
				t.length ? `阶段事件（${t.length} 条）` : "",
				...t.map((e, t) => `${t + 1}. ${i(e)} · ${ce(e.display_status || e.state)}${e.created_at ? ` · ${P(e.created_at)}` : e.event_time_known === !1 ? " · 发生时间未记录" : ""}${e.message ? `\n${e.message}` : ""}`),
				r.inline ? "点击步骤查看阶段摘要" : "点击步骤查看对应日志"
			].filter(Boolean).join("\n");
		}
		return (n, r) => (t(), O("div", ye, [
			o.value.length ? (t(), O("div", be, [e.inline ? (t(), O("h3", xe, "执行阶段")) : l("", !0), r[5] ||= _("p", { class: "registration-step-note" }, "按首次记录排列，不代表固定执行顺序", -1)])) : l("", !0),
			o.value.length ? (t(), O("ul", {
				key: 1,
				class: x(["registration-steps", `is-count-${o.value.length === 1 ? "1" : o.value.length === 2 ? "2" : "many"}`]),
				style: p({ "--reg-step-cols": w.value }),
				"aria-label": "注册执行阶段，排列不代表固定顺序"
			}, [(t(!0), O(f, null, a(o.value, (n) => (t(), O("li", {
				key: E(q)(n),
				class: x([`is-${E(K)(n)}`, { "is-inspected": v.value === n }])
			}, [_("button", {
				type: "button",
				title: k(n),
				"aria-pressed": e.inline ? v.value === n : void 0,
				onClick: (e) => y(n)
			}, [
				_("strong", Ce, [E(K)(n) === "success" || E(K)(n) === "recovered" ? (t(), O("span", we, "✓")) : [
					"failed",
					"request_unknown",
					"manual_reconcile",
					"password_confirmation_pending"
				].includes(E(K)(n)) ? (t(), O("span", Te, "!")) : [
					"running",
					"active",
					"queued",
					"waiting",
					"awaiting_confirmation"
				].includes(E(K)(n)) ? (t(), O("span", Ee)) : [
					"stopped",
					"interrupted",
					"debug_paused",
					"attention_required",
					"partial_success",
					"unconfirmed",
					"record_incomplete",
					"deferred"
				].includes(E(K)(n)) ? (t(), O("span", De)) : (t(), O("span", Oe)), _("span", ke, h(E(z)(n)), 1)]),
				_("span", Ae, [_("small", je, h(E(R)(n)), 1), _("small", Me, "耗时 " + h(C(n)), 1)]),
				(t(!0), O(f, null, a(E(B)(n), (e) => (t(), O("small", {
					key: e,
					class: "registration-step-marker"
				}, h(e), 1))), 128)),
				ee(n) ? (t(), O("small", Ne, h(ee(n)), 1)) : l("", !0),
				T(n) ? (t(), O("span", Pe, h(T(n)), 1)) : l("", !0)
			], 8, Se), e.inline ? l("", !0) : (t(), O("button", {
				key: 0,
				type: "button",
				"aria-label": `查看${E(z)(n)}的关系与证据`,
				onClick: (e) => s.value = n
			}, "详情", 8, Fe))], 2))), 128))], 6)) : l("", !0),
			v.value ? (t(), O("div", {
				key: 2,
				class: "registration-stage-selected",
				"data-tone": E(K)(v.value)
			}, [_("div", Le, [_("div", Q, [_("strong", null, h(E(z)(v.value)), 1), _("span", Re, " · " + h(E(R)(v.value)), 1)]), v.value.reason || v.value.message ? (t(), O("p", ze, h(v.value.reason || v.value.message), 1)) : e.focusFailure && E(q)(v.value) === E(V)(e.job.progress?.failure).step_id && E(V)(e.job.progress?.failure).message ? (t(), O("p", Be, h(E(V)(e.job.progress?.failure).message), 1)) : l("", !0)]), _("div", Ve, [_("button", {
				type: "button",
				class: "registration-stage-btn-detail",
				"aria-label": `查看${E(z)(v.value)}的关系与证据`,
				onClick: r[0] ||= (e) => s.value = v.value
			}, "阶段详情", 8, He), _("button", {
				type: "button",
				class: "registration-stage-btn-log",
				onClick: r[1] ||= (e) => i("log", E(q)(v.value))
			}, "阶段日志")])], 8, Ie)) : o.value.length ? l("", !0) : (t(), O("p", Ue, "暂无阶段记录，可查看任务日志。")),
			o.value.length ? (t(), O("details", We, [r[6] ||= _("summary", null, "依赖与执行记录", -1), _("div", Ge, [(t(!0), O(f, null, a(o.value, (e) => (t(), O("div", {
				key: E(q)(e),
				class: "registration-relations-item"
			}, [_("div", Ke, [_("strong", null, h(E(z)(e)), 1), _("span", qe, h(E(R)(e)), 1)]), c(H, {
				step: e,
				siblings: o.value
			}, null, 8, ["step", "siblings"])]))), 128))])])) : l("", !0),
			_("dialog", {
				ref_key: "dialog",
				ref: u,
				class: "registration-dialog registration-step-dialog",
				"aria-label": "注册步骤关系与证据",
				onCancel: r[3] ||= b((e) => s.value = void 0, ["prevent"]),
				onClose: r[4] ||= (e) => s.value = void 0,
				onClick: D
			}, [_("header", null, [_("div", Je, [_("h3", null, h(s.value ? E(z)(s.value) : "步骤详情"), 1), s.value ? (t(), O("span", {
				key: 0,
				class: "registration-dialog-pill",
				"data-tone": E(K)(s.value)
			}, h(E(R)(s.value)), 9, Ye)) : l("", !0)]), _("button", {
				type: "button",
				class: "ui-button registration-dialog-close",
				onClick: r[2] ||= (e) => s.value = void 0
			}, "关闭")]), _("div", Xe, [s.value && ee(s.value) ? (t(), O("p", Ze, h(ee(s.value)), 1)) : l("", !0), s.value ? (t(), g(W, {
				key: 1,
				step: s.value,
				siblings: o.value
			}, null, 8, ["step", "siblings"])) : l("", !0)])], 544)
		]));
	}
}), $e = ["aria-busy"], et = { class: "registration-batch-header" }, tt = { class: "registration-batch-title" }, nt = ["data-tone"], rt = {
	key: 1,
	class: "registration-hint"
}, it = {
	key: 0,
	class: "registration-hint registration-batch-meta"
}, at = { key: 0 }, ot = { key: 1 }, st = {
	key: 0,
	class: "registration-batch-actions"
}, ct = ["value"], lt = ["value"], ut = ["disabled"], dt = ["disabled"], ft = ["disabled"], pt = {
	key: 0,
	class: "registration-batch-notice",
	role: "alert"
}, mt = {
	key: 1,
	class: "registration-batch-notice"
}, ht = {
	class: "registration-batch-meter",
	"aria-hidden": "true"
}, gt = ["data-tone"], _t = {
	class: "registration-batch-filters",
	role: "group",
	"aria-label": "按批次任务状态筛选"
}, vt = [
	"data-batch-filter",
	"aria-pressed",
	"onClick"
], yt = ["data-tone"], bt = ["data-tone"], xt = { class: "registration-batch-row" }, St = { class: "registration-batch-identity" }, Ct = { class: "registration-batch-result" }, wt = ["data-tone"], Tt = { key: 0 }, Et = {
	key: 0,
	class: "registration-batch-timing"
}, Dt = { key: 0 }, Ot = { class: "registration-batch-dates" }, kt = { key: 0 }, At = ["datetime", "title"], jt = { key: 1 }, Mt = ["datetime", "title"], Nt = { class: "registration-batch-actions registration-batch-row-actions" }, Pt = [
	"aria-label",
	"aria-expanded",
	"aria-controls",
	"onClick"
], Ft = ["aria-label", "onClick"], It = ["disabled", "onClick"], Lt = [
	"id",
	"hidden",
	"data-progress-state"
], Rt = {
	key: 0,
	class: "registration-step-note",
	role: "alert"
}, zt = ["onClick"], Bt = {
	key: 1,
	class: "registration-step-note",
	role: "status"
}, Vt = { key: 0 }, Ht = { class: "registration-diagnostic-code" }, Ut = { key: 1 }, Wt = { class: "registration-attempt-head" }, Gt = {
	key: 0,
	class: "registration-diagnostic-code"
}, Kt = { key: 1 }, qt = { class: "registration-attempt-head" }, Jt = {
	key: 0,
	class: "registration-diagnostic-code"
}, Yt = { key: 1 }, Xt = {
	key: 0,
	class: "registration-batch-notice"
}, Zt = {
	class: "registration-batch-footer registration-hint",
	"aria-live": "polite"
}, Qt = /* @__PURE__ */ e({
	__name: "RegistrationBatchPanel",
	props: {
		batch: {},
		batches: {},
		batchId: {},
		refreshGeneration: {},
		active: { type: Boolean },
		loading: { type: Boolean },
		error: {},
		actions: {},
		mutating: { type: Boolean },
		statusLabel: { type: Function },
		sourceLabel: { type: Function },
		driverLabel: { type: Function },
		readProgress: { type: Function }
	},
	emits: [
		"select",
		"refresh",
		"batchAction",
		"retry",
		"log"
	],
	setup(e, { emit: n }) {
		let i = e, o = n, s = [
			{
				key: "all",
				label: "全部"
			},
			{
				key: "success",
				label: "成功"
			},
			{
				key: "failed",
				label: "失败"
			},
			{
				key: "running",
				label: "运行"
			},
			{
				key: "queued",
				label: "排队"
			},
			{
				key: "other",
				label: "其他"
			}
		], u = m("all"), d = m(null), g = m(!1), v = S(() => i.batch?.items || []), b = S(() => i.batch && !i.batches.some((e) => String(e.batch_id) === String(i.batch?.batch_id)) ? [i.batch, ...i.batches] : i.batches), x = (e) => e.display_status || e.status || "";
		function C(e) {
			let t = x(e);
			return t === "success" || t === "failed" ? t : ["running", "stopping"].includes(t) ? "running" : [
				"pending",
				"queued",
				"waiting"
			].includes(t) ? "queued" : "other";
		}
		let w = S(() => {
			let e = {
				all: v.value.length,
				success: 0,
				failed: 0,
				running: 0,
				queued: 0,
				other: 0
			};
			for (let t of v.value) e[C(t)]++;
			return e;
		}), T = S(() => s.filter((e) => e.key !== "other" || w.value.other || u.value === "other")), D = S(() => u.value === "all" ? v.value : v.value.filter((e) => C(e) === u.value)), ee = S(() => D.value.find((e) => String(e.id) === d.value)), A = m(), j = m(""), M, te = S(() => {
			let e = w.value;
			return e.all ? e.running ? {
				label: "运行中",
				tone: "running"
			} : e.queued ? {
				label: "排队中",
				tone: "queued"
			} : e.failed ? {
				label: e.failed === e.all ? "失败" : "部分失败",
				tone: "failed"
			} : e.success === e.all ? {
				label: "已完成",
				tone: "success"
			} : {
				label: "已结束",
				tone: "other"
			} : {
				label: "暂无任务",
				tone: "other"
			};
		}), ne = (e, t, n) => {
			let r = (t ? Date.parse(I(t)) : n ?? NaN) - Date.parse(I(e));
			return Number.isFinite(r) && r >= 0 ? se(r) : "";
		}, re = S(() => ne(i.batch?.started_at, i.batch?.completed_at)), ie = (e) => e.toLocaleString("zh-CN"), ae = (e) => V(V(e.progress).failure), R = S(() => {
			let e = Date.now();
			return D.value.map((t) => {
				let n = C(t), r = n === "running";
				return {
					job: t,
					tone: n,
					result: ce(t, n),
					identity: [
						`#${t.id}`,
						t.email_source && i.sourceLabel(t.email_source),
						t.registration_driver && i.driverLabel(t.registration_driver),
						typeof t.retry_count == "number" && `人工重试 ${t.retry_count} 次`
					].filter(Boolean).join(" · "),
					elapsed: ne(t.started_at, t.completed_at, r ? e : void 0),
					started: z(t.started_at),
					completed: z(t.completed_at)
				};
			});
		});
		function z(e) {
			if (!e || !Number.isFinite(Date.parse(e))) return null;
			let { text: t, secondary: n } = F(e);
			return {
				label: n ? `${t.slice(5)} ${n}` : t,
				full: n ? `${t} ${n}` : t
			};
		}
		function ce(e, t) {
			if (t === "failed" || x(e) === "partial_success") {
				let t = e.error_info ? oe(V(e.error_info)) : "", n = I(ae(e).label);
				return t && t !== "执行异常" ? t : n && Array.from(n).length <= 10 ? n : t || "执行异常";
			}
			return t === "running" || t === "queued" ? I(V(V(e.progress).current).label) : "";
		}
		function B(e) {
			return e.debug_state === "paused" ? "调试暂停" : i.statusLabel(e.display_status || x(e));
		}
		function H(e) {
			if (e && typeof e == "object") return !0;
			if (typeof e != "string") return !1;
			let t = e.trim();
			return t.startsWith("{") && t.endsWith("}") || t.startsWith("[") && t.endsWith("]") || t.length > 140 || t.includes("\n");
		}
		function U(e) {
			if (e == null) return "";
			if (typeof e == "object") try {
				return JSON.stringify(e, null, 2);
			} catch {
				return String(e);
			}
			let t = String(e), n = t.trim();
			if (n.startsWith("{") && n.endsWith("}") || n.startsWith("[") && n.endsWith("]")) try {
				return JSON.stringify(JSON.parse(n), null, 2);
			} catch {
				return t;
			}
			return t;
		}
		function W(e) {
			let t = e.status_counts || {}, n = Number(t.running || 0) + Number(t.stopping || 0), r = Number(t.pending || 0), i = e.created_at ? P(e.created_at).replace(/:\d{2}$/, "") : String(e.batch_id), a = Number(t.partial_success || 0);
			return `${i} · ${n || r ? `运行 ${n} / 等待 ${r}` : [
				`成功 ${t.success || 0}`,
				...a ? [`部分 ${a}`] : [],
				`失败 ${t.failed || 0}`
			].join(" / ")}`;
		}
		function G(e) {
			u.value = e, d.value = null, g.value = !1, e === "failed" && D.value.length === 1 && (d.value = String(D.value[0].id), g.value = !0);
		}
		function K(e) {
			let t = String(e.id);
			d.value = d.value === t ? null : t, g.value = d.value !== null && C(e) === "failed";
		}
		function q() {
			M?.abort(), M = void 0, A.value = void 0, j.value = "";
		}
		let J = (e) => String(e?.operation_run_id ?? "");
		async function le(e) {
			if (M || !i.active) return;
			let t = new AbortController();
			M = t, j.value = "";
			try {
				let n = await i.readProgress(e.id, t.signal);
				if (t.signal.aborted) return;
				if (!n.ok || !n.job || String(n.job.id) !== String(e.id) || !Array.isArray(V(n.job.progress).main_steps)) throw Error("阶段详情读取失败，请重试");
				if (J(e) && J(e) !== J(n.job)) throw Error("当前执行已更新，请刷新批次后重试");
				A.value = n.job;
			} catch (e) {
				!t.signal.aborted && !N(e) && (j.value = e instanceof Error ? e.message : "阶段详情读取失败，请重试");
			} finally {
				M === t && (M = void 0);
			}
		}
		return r(() => i.batchId, () => G("all")), r([
			() => i.active,
			() => i.batchId,
			ee,
			() => i.refreshGeneration
		], ([e, t, n, r], [, a, o, s]) => {
			if (!e || !n) {
				q(), e && i.batch && d.value !== null && (d.value = null, g.value = !1);
				return;
			}
			let c = t !== a || String(n.id) !== String(o?.id) || J(n) !== J(o) || x(n) !== (o && x(o)), l = r !== s;
			(c || l) && q(), (c || l || !A.value && !j.value || C(n) === "running") && le(n);
		}), y(q), (n, r) => (t(), O("section", {
			class: "registration-batch",
			"aria-labelledby": "registration-batch-title",
			"aria-busy": e.loading
		}, [
			_("header", et, [_("div", null, [_("div", tt, [
				r[5] ||= _("h2", { id: "registration-batch-title" }, "任务批次进度", -1),
				e.batch ? (t(), O("span", {
					key: 0,
					class: "registration-state",
					"data-tone": te.value.tone
				}, h(te.value.label), 9, nt)) : l("", !0),
				e.batch?.projection_delayed ? (t(), O("span", rt, "进度同步中")) : l("", !0)
			]), e.batch ? (t(), O("p", it, [
				_("span", null, h(ie(e.batch.total ?? w.value.all)) + " 个任务", 1),
				e.batch.workers ? (t(), O("span", at, "并发 " + h(e.batch.workers), 1)) : l("", !0),
				re.value ? (t(), O("span", ot, "批次耗时 " + h(re.value), 1)) : l("", !0)
			])) : l("", !0)]), b.value.length ? (t(), O("div", st, [
				_("select", {
					value: e.batchId,
					"aria-label": "选择任务批次",
					onChange: r[0] ||= (e) => o("select", e.target.value)
				}, [(t(!0), O(f, null, a(b.value, (e) => (t(), O("option", {
					key: String(e.batch_id),
					value: String(e.batch_id)
				}, h(W(e)), 9, lt))), 128))], 40, ct),
				e.actions.stopBatch ? (t(), O("button", {
					key: 0,
					type: "button",
					disabled: e.mutating,
					onClick: r[1] ||= (e) => o("batchAction", "stopBatch")
				}, "停止运行", 8, ut)) : l("", !0),
				e.actions.cancelBatch ? (t(), O("button", {
					key: 1,
					type: "button",
					disabled: e.mutating,
					onClick: r[2] ||= (e) => o("batchAction", "cancelBatch")
				}, "取消排队", 8, dt)) : l("", !0),
				e.actions.retryBatch ? (t(), O("button", {
					key: 2,
					type: "button",
					disabled: e.mutating,
					onClick: r[3] ||= (e) => o("batchAction", "retryBatch")
				}, "重跑失败", 8, ft)) : l("", !0)
			])) : l("", !0)]),
			e.error ? (t(), O("div", pt, [k(h(e.error) + " ", 1), _("button", {
				type: "button",
				onClick: r[4] ||= (e) => o("refresh")
			}, "刷新批次")])) : !e.batch || !v.value.length ? (t(), O("p", mt, h(e.loading ? "正在读取任务批次…" : "暂无注册任务批次"), 1)) : l("", !0),
			e.batch && w.value.all ? (t(), O(f, { key: 2 }, [
				_("div", ht, [(t(!0), O(f, null, a(T.value.slice(1), (e) => (t(), O("span", {
					key: e.key,
					"data-tone": e.key,
					style: p({ flexGrow: w.value[e.key] })
				}, null, 12, gt))), 128))]),
				_("div", _t, [(t(!0), O(f, null, a(T.value, (e) => (t(), O("button", {
					key: e.key,
					type: "button",
					"data-batch-filter": e.key,
					"aria-pressed": u.value === e.key,
					onClick: (t) => G(e.key)
				}, [e.key === "all" ? l("", !0) : (t(), O("span", {
					key: 0,
					class: "registration-status-dot",
					"data-tone": e.key,
					"aria-hidden": "true"
				}, null, 8, yt)), k(h(e.label) + " " + h(ie(w.value[e.key])), 1)], 8, vt))), 128))]),
				(t(!0), O(f, null, a(R.value, ({ job: n, tone: i, result: s, identity: u, elapsed: p, started: m, completed: v }) => (t(), O("article", {
					key: String(n.id),
					class: "registration-batch-card",
					"data-tone": i
				}, [_("div", xt, [
					_("div", St, [_("strong", null, h(n.email || ([
						"pending",
						"queued",
						"waiting"
					].includes(x(n)) ? "等待执行…" : "准备邮箱中…")), 1), _("small", null, h(u), 1)]),
					_("div", Ct, [_("span", {
						class: "registration-state",
						"data-tone": i
					}, h(B(n)), 9, wt), s ? (t(), O("small", Tt, h(s), 1)) : l("", !0)]),
					p || m || v ? (t(), O("div", Et, [p ? (t(), O("strong", Dt, "运行耗时 " + h(p), 1)) : l("", !0), _("div", Ot, [m ? (t(), O("small", kt, [r[6] ||= k("开始 ", -1), _("time", {
						datetime: n.started_at || void 0,
						title: m.full
					}, h(m.label), 9, At)])) : l("", !0), v ? (t(), O("small", jt, [r[7] ||= k("结束 ", -1), _("time", {
						datetime: n.completed_at || void 0,
						title: v.full
					}, h(v.label), 9, Mt)])) : l("", !0)])])) : l("", !0),
					_("div", Nt, [
						_("button", {
							type: "button",
							"aria-label": `查看阶段 · ${n.email || `任务 #${n.id}`}`,
							"aria-expanded": d.value === String(n.id),
							"aria-controls": `registration-stages-${n.id}`,
							onClick: (e) => K(n)
						}, "阶段", 8, Pt),
						_("button", {
							type: "button",
							"aria-label": `查看日志 · ${n.email || `任务 #${n.id}`}`,
							onClick: (e) => o("log", n.id)
						}, "日志", 8, Ft),
						n.retryable ? (t(), O("button", {
							key: 0,
							type: "button",
							disabled: e.mutating,
							onClick: (e) => o("retry", n)
						}, h(n.retry_label || "重试"), 9, It)) : l("", !0)
					])
				]), _("div", {
					id: `registration-stages-${n.id}`,
					class: "registration-batch-evidence",
					hidden: d.value !== String(n.id),
					"data-progress-state": d.value === String(n.id) ? j.value ? "error" : A.value ? "ready" : "loading" : void 0
				}, [d.value === String(n.id) ? (t(), O(f, { key: 0 }, [j.value ? (t(), O("p", Rt, [k(h(j.value) + " ", 1), _("button", {
					type: "button",
					onClick: (e) => le(n)
				}, "重试读取", 8, zt)])) : A.value ? l("", !0) : (t(), O("p", Bt, "正在读取阶段详情…")), A.value ? (t(), O(f, { key: 2 }, [
					c(Qe, {
						job: A.value,
						active: e.active,
						inline: "",
						"focus-failure": g.value,
						onLog: (e) => o("log", n.id, e)
					}, null, 8, [
						"job",
						"active",
						"focus-failure",
						"onLog"
					]),
					A.value.error_message ? (t(), O("details", Vt, [r[8] ||= _("summary", null, "原始错误摘要", -1), _("pre", Ht, h(U(A.value.error_message)), 1)])) : l("", !0),
					E(L)(A.value.attempts).length || E(L)(A.value.route_attempts).length ? (t(), O("details", Ut, [
						r[9] ||= _("summary", null, "尝试与线路记录", -1),
						(t(!0), O(f, null, a(E(L)(A.value.attempts), (n) => (t(), O("div", {
							key: E(I)(n.id || n.attempt_id),
							class: "registration-attempt-item"
						}, [_("span", Wt, h(e.statusLabel(n.status)), 1), H(n.error_message) ? (t(), O("pre", Gt, h(U(n.error_message)), 1)) : (t(), O("p", Kt, h(n.error_message || "已记录"), 1))]))), 128)),
						(t(!0), O(f, null, a(E(L)(A.value.route_attempts), (n) => (t(), O("div", {
							key: E(I)(n.route_attempt_no),
							class: "registration-attempt-item"
						}, [_("span", qt, "线路尝试 " + h(n.route_attempt_no || 1), 1), H(n.retry_reason) ? (t(), O("pre", Jt, h(U(n.retry_reason)), 1)) : (t(), O("p", Yt, h(n.retry_reason || e.statusLabel(n.status)), 1))]))), 128))
					])) : l("", !0)
				], 64)) : l("", !0)], 64)) : l("", !0)], 8, Lt)], 8, bt))), 128)),
				D.value.length ? l("", !0) : (t(), O("p", Xt, "没有符合条件的任务")),
				_("p", Zt, "显示 " + h(ie(D.value.length)) + " 条任务", 1)
			], 64)) : l("", !0)
		], 8, $e));
	}
}), $ = (e, t = {}) => ae(e, t, ue), $t = (e) => ({
	method: "POST",
	headers: { "Content-Type": "application/json" },
	body: JSON.stringify(e ?? {})
});
function en() {
	return {
		metadata: (e) => $("/api/email-sources", { signal: e }),
		summary: (e) => $("/api/summary", { signal: e }),
		jobs: (e, t) => $(`/api/jobs?${new URLSearchParams(Object.entries(e).map(([e, t]) => [e, String(t)]))}`, { signal: t }),
		progress: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/progress`, { signal: t }),
		create: (e, t) => $("/api/jobs", {
			...$t(e),
			signal: t
		}),
		action: (e, t = {}, n) => $(e, {
			...$t(t),
			signal: n
		}),
		log: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/log`, { signal: t }),
		debug: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/debug?limit=300`, { signal: t }),
		diagnostics: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/diagnostics?limit=100`, { signal: t }),
		compare: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/debug/compare`, { signal: t })
	};
}
// src/features/registration/useRegistration.ts
var tn = [
	"pending",
	"queued",
	"waiting"
], nn = ["running", "stopping"], rn = [...tn, ...nn], an = [
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
], on = [
	"failed",
	"partial_success",
	"interrupted",
	"request_unknown",
	"manual_reconcile",
	"attention_required"
], sn = 1e4, cn = () => ({
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
}), ln = (e) => e instanceof Error ? e.message : "请求失败", un = (e) => e == null ? "" : String(e).trim(), dn = (e) => encodeURIComponent(String(Y(e))), fn = () => ({
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
function pn(e) {
	let t = e.api || en(), n = m(!!e.visible), r = m(!document.hidden), i = !1, a = S(() => n.value && r.value && !i), o = s({
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
		query: cn(),
		batchId: "",
		batchRefreshGeneration: 0,
		statusCounts: {},
		facets: {},
		creating: !1,
		pendingActions: {},
		lastCreate: null,
		lastAction: null,
		detail: fn(),
		metaError: ""
	}), c = S(() => o.creating), l = S(() => {
		let e = o.meta?.capabilities?.features?.register;
		return o.metaError ? o.metaError : o.meta ? e?.enabled === !0 ? "" : String(e?.reason || "注册资格未确认，请刷新后重试") : o.metaError || "注册资格未确认，请刷新后重试";
	}), u = (t) => e.notify?.(t), d = 0, f = 0, p = 0, h = 0, g = 0, _ = "", v, b, x, C = !1, w, T, E, D, O, k = "", A = 0, j = 0, M = !0, te, ne = /* @__PURE__ */ new Map(), re = 0, ie = () => !i && r.value && o.detail.id !== null, ae = (e, t) => ie() && e === g && String(o.detail.id) === String(t);
	function oe() {
		d++, w?.controller.abort(), w = void 0, o.loading = !1;
	}
	function P() {
		oe(), p++, T?.controller.abort(), T = void 0, h++, E?.controller.abort(), E = void 0;
	}
	function F() {
		window.clearInterval(v), window.clearInterval(b), v = b = void 0;
	}
	function se() {
		if (!a.value || re > 0) return !1;
		if (o.view === "tasks") return !0;
		let e = o.batch;
		return !e || String(e.batch_id) !== o.batchId || e.projection_delayed ? !0 : rn.some((t) => Number(e.status_counts?.[t] || 0) > 0) || e.items.some((e) => rn.includes(String(e.status || "")));
	}
	function I(e) {
		for (let t of Object.keys(cn())) {
			let n = e[t];
			if (n !== void 0) {
				if (t === "page" || t === "page_size") {
					let e = Number(n);
					Number.isSafeInteger(e) && e > 0 && (o.query[t] = t === "page_size" ? Math.min(e, 500) : e);
				} else o.query[t] = String(n);
			}
		}
		if (e.progress_batch_id !== void 0) {
			let t = un(e.progress_batch_id);
			t !== o.batchId && (o.batchId = t, o.batch = null);
		}
	}
	function L(e = {}, n = !1) {
		if (I(e), !a.value || e.automatic && !se()) return Promise.resolve();
		let r = JSON.stringify({
			view: o.view,
			batchId: o.batchId,
			...o.query
		});
		if ((e.automatic || e.coalesce) && w?.signature === r) return w.promise;
		w?.controller.abort();
		let i = ++d, s = new AbortController(), c = o.view;
		e.automatic || f++;
		let l = f, u = !(!e.automatic && !n || _ !== r);
		o.loading = !u, !e.automatic && !n && (o.error = "");
		let p = () => a.value && i === d && c === o.view, m = (async () => {
			try {
				for (let n = 0; n < 2; n++) {
					let i = {
						paged: 1,
						...o.query,
						view: c === "tasks" ? "table" : "batch",
						progress_batch_id: o.batchId,
						refresh_generation: l
					};
					(c === "launch" || e.automatic) && (i.progress_detail = 0), c === "tasks" && e.automatic && k === r && Date.now() - A < 3e4 && (i.include_facets = 0);
					let a = await t.jobs(i, s.signal);
					if (!p()) return;
					if (Object.prototype.hasOwnProperty.call(a, "status_counts") && (o.statusCounts = a.status_counts || {}), c === "launch") {
						o.batches = a.progress_batches || [];
						let e = a.progress_batch || null;
						if (!e && o.batchId) {
							let e = un(o.batches[0]?.batch_id);
							if (e !== o.batchId && (o.batchId = e, o.batch = null, e && !n)) continue;
						}
						!o.batchId && e?.batch_id && (o.batchId = un(e.batch_id)), o.batch = e, o.batchRefreshGeneration = l;
					} else {
						o.total = Math.max(0, Number(a.total ?? a.items?.length ?? 0) || 0), Object.prototype.hasOwnProperty.call(a, "facets") && (o.facets = a.facets || {}, k = r, A = Date.now());
						let e = Math.max(1, Math.ceil(o.total / o.query.page_size));
						if (o.query.page > e) {
							if (o.query.page = e, !n) continue;
							throw Error("列表范围已变化，请刷新后重试");
						}
						o.jobs = a.items || [];
					}
					o.error = "", _ = JSON.stringify({
						view: c,
						batchId: o.batchId,
						...o.query
					});
					return;
				}
			} catch (e) {
				p() && !N(e) && (o.error = ln(e));
			} finally {
				i === d && (o.loading = !1, w = void 0);
			}
		})();
		return w = {
			version: i,
			signature: r,
			promise: m,
			controller: s
		}, m;
	}
	function R(e) {
		return L({ progress_batch_id: un(e) });
	}
	function z(e, n) {
		return t.progress(Y(e), n);
	}
	function ce(e) {
		return L({
			...e,
			page: e.page ?? 1
		});
	}
	function B(e) {
		return L({ page: e });
	}
	function V(e) {
		return L({
			page: 1,
			page_size: e
		});
	}
	function H(e) {
		o.summary = e;
	}
	function U(e) {
		o.summary = {
			...o.summary || {},
			email_supply: e || {}
		};
	}
	function W() {
		if (!a.value) return Promise.resolve();
		T?.controller.abort();
		let e = ++p, n = new AbortController(), r = (async () => {
			try {
				let r = await t.summary(n.signal);
				e === p && a.value && H(r);
			} catch (t) {
				e === p && a.value && !N(t) && U({
					status: "error",
					reason: "本地库存读取失败，请稍后重试"
				});
			} finally {
				e === p && (T = void 0);
			}
		})();
		return T = {
			version: e,
			promise: r,
			controller: n
		}, r;
	}
	function G(e = !1) {
		if (E) return E.promise;
		if (e && (M = !0), !a.value || !M && o.meta && Date.now() - j < sn) return Promise.resolve();
		let n = ++h, r = new AbortController(), i = (async () => {
			try {
				let e = await t.metadata(r.signal);
				if (n !== h || !a.value) return;
				o.meta = {
					...e,
					sources: Array.isArray(e.sources) ? e.sources : []
				}, o.metaError = "", j = Date.now(), M = !1;
			} catch (e) {
				if (n === h && a.value && !N(e)) {
					let t = ln(e);
					o.metaError = /[\u3400-\u9fff]/.test(t) ? t : `邮箱来源读取失败，请稍后重试${t ? `（${t}）` : ""}`;
				}
			} finally {
				n === h && (E = void 0);
			}
		})();
		return E = {
			version: n,
			promise: i,
			controller: r
		}, i;
	}
	function K(e = !1) {
		F(), a.value && (G(e), L({ coalesce: !0 }, !0), W(), v = window.setInterval(() => {
			L({ automatic: !0 });
		}, 5e3), b = window.setInterval(() => {
			T || W(), G(!0);
		}, 1e4));
	}
	function q(e) {
		n.value !== e && (n.value = e, e ? K(!0) : (F(), P()));
	}
	function J(e) {
		["launch", "tasks"].includes(e) && o.view !== e && (o.view = e, oe(), L({ coalesce: !0 }));
	}
	function le(e, t = "已受理") {
		let n = e.message || e.warning || (e.started_count == null ? e.deleted_count == null ? e.cancelled == null ? t : `已取消 ${e.cancelled} 个排队任务` : `已删除 ${e.deleted_count} 个任务` : `已提交 ${e.started_count} 个失败任务`), r = Array.isArray(e.skipped) ? e.skipped.length : 0;
		o.receipt = {
			tone: e.warning ? "warning" : "success",
			message: String(n) + (r ? `，跳过 ${r} 个` : "")
		}, u(o.receipt.message);
	}
	function ue(e) {
		let t = un(e.jobs?.[0]?.batch_id || e.job?.batch_id || e.batch_id);
		t && (o.batchId = t, o.batch = null);
	}
	function de(e, n = {}) {
		let r = JSON.stringify([e, n]), i = ne.get(r);
		if (i) return i;
		o.pendingActions[r] = !0, re += 1, P();
		let a = (async () => {
			try {
				let r = await t.action(e, n);
				return o.lastAction = r, ue(r), le(r), /\/delete(?:-bulk)?$/.test(e) && o.detail.id !== null && (Array.isArray(r.deleted) ? r.deleted : r.deleted === !0 ? [e.split("/").at(-2)] : []).some((e) => String(e) === String(o.detail.id)) && _e(), L(), o.detail.id !== null && Z(), r;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: ln(e)
				}, u(o.receipt.message), e;
			} finally {
				ne.delete(r), delete o.pendingActions[r];
			}
		})();
		return ne.set(r, a), a;
	}
	function fe(e) {
		if (te) return te;
		if (l.value) {
			let e = l.value;
			return o.receipt = {
				tone: "warning",
				message: e
			}, u(e), Promise.reject(Error(e));
		}
		return !Number.isSafeInteger(e.count) || e.count < 1 || !Number.isSafeInteger(e.workers) || e.workers < 1 ? Promise.reject(/* @__PURE__ */ Error("注册数量与并发线程数必须为有效的正整数")) : (o.creating = !0, te = (async () => {
			try {
				let n = await t.create({ ...e });
				return o.lastCreate = n, ue(n), le(n, `已提交 ${n.submitted || 0} 个任务`), L(), n;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: ln(e)
				}, u(o.receipt.message), e;
			} finally {
				o.creating = !1, te = void 0;
			}
		})(), te);
	}
	function X(e) {
		let t = o.batch?.items || [], n = (e) => String(e.display_status || e.status || "");
		return e === "stopBatch" ? t.filter((e) => nn.includes(n(e))) : e === "cancelBatch" ? t.filter((e) => tn.includes(n(e))) : t.filter((e) => {
			let t = String(e.status || "");
			return t === "cancelled" || t === "stopped" ? !1 : on.includes(n(e)) && e.retryable;
		});
	}
	let pe = S(() => ({
		stopBatch: !!o.batchId && X("stopBatch").length > 0,
		cancelBatch: !!o.batchId && X("cancelBatch").length > 0,
		retryBatch: X("retryBatch").length > 0
	}));
	async function me(t, n, r = [], i = !1) {
		let a = t === "stopBatch" || t === "cancelBatch" || t === "retryBatch" ? X(t) : [], s = t === "retryBulk" || t === "deleteBulk" ? r.map((e) => Y(e)) : a.map((e) => Y(e.id));
		if ([
			"stopBatch",
			"cancelBatch",
			"retryBatch",
			"retryBulk",
			"deleteBulk"
		].includes(t) && !s.length) return u("当前没有可操作的任务"), null;
		if (["stopBatch", "cancelBatch"].includes(t) && !o.batchId) return null;
		if (t === "retry" && !n?.retryable) return u("该任务当前不可重试"), null;
		if ([
			"stop",
			"delete",
			"retry"
		].includes(t) && !n) throw Error("任务不存在");
		let c = {
			cancelAll: "取消所有排队任务",
			stopBatch: `停止当前批次的 ${s.length} 个运行中任务`,
			cancelBatch: `取消当前批次的 ${s.length} 个排队任务`,
			retryBatch: `重跑当前批次的 ${s.length} 个失败任务`,
			stop: `停止任务 #${n?.id}`,
			delete: `删除任务 #${n?.id} 与对应日志`,
			retry: `${n?.retry_label || "重试"}任务 #${n?.id}`,
			deleteBulk: `删除选中的 ${s.length} 个任务与对应日志`,
			retryBulk: `重试选中的 ${s.length} 个任务`
		}, l = t === "retry" && n?.retry_action === "codex" ? "仅补跑 Codex 授权" : t === "retry" && n?.retry_action === "twofa" ? "重新登录检查并补齐 Authenticator 2FA" : t === "retry" && n?.retry_action === "registration_resume" ? "使用已保存账号密码继续邮箱验证" : "有原邮箱则复用，没有原邮箱则重新领取；已创建账号的任务按缺失步骤补跑，不能重试的由后端校验", d = t === "retry" || t === "retryBulk" || t === "retryBatch" ? `\n${l}。原任务记录和日志会保留。` : t === "stop" || t === "stopBatch" ? "\n任务会在当前步骤检查点退出。" : t === "cancelAll" || t === "cancelBatch" ? "\n运行中的任务不受影响。" : "", f = encodeURIComponent(o.batchId), p = n ? dn(n.id) : "";
		return await (e.confirm ? e.confirm(`确定${c[t]}吗？${d}`) : window.confirm(`确定${c[t]}吗？${d}`)) ? de(...{
			cancelAll: ["/api/jobs/cancel-pending", {}],
			stopBatch: [`/api/jobs/batches/${f}/stop`, {}],
			cancelBatch: [`/api/jobs/batches/${f}/cancel`, {}],
			retryBatch: ["/api/jobs/retry-bulk", {
				job_ids: s,
				debug_enabled: i
			}],
			stop: [`/api/jobs/${p}/stop`, {}],
			delete: [`/api/jobs/${p}/delete`, {}],
			retry: [`/api/jobs/${p}/retry`, { debug_enabled: i }],
			deleteBulk: ["/api/jobs/delete-bulk", { job_ids: s }],
			retryBulk: ["/api/jobs/retry-bulk", {
				job_ids: s,
				debug_enabled: i
			}]
		}[t]) : null;
	}
	function he() {
		g++, D?.abort(), O?.abort(), D = O = void 0, window.clearTimeout(x), x = void 0, o.detail.loading = !1, o.detail.comparing = !1;
	}
	async function Z(e = C, n = !1) {
		if (!ie()) return;
		D?.abort(), window.clearTimeout(x);
		let r = o.detail.id, i = ++g, a = new AbortController();
		D = a, e || (o.detail.loading = !0), n && (o.detail.error = "");
		let s = () => ae(i, r);
		try {
			let e = await t.log(r, a.signal);
			if (!s()) return;
			o.detail.job = e.job || null, o.detail.log = String(e.log || "");
			let n = await t.debug(r, a.signal);
			if (!s()) return;
			if (o.detail.debug = n?.enabled ? n : null, n?.enabled) o.detail.diagnostics = null;
			else {
				let e = await t.diagnostics(r, a.signal);
				if (!s()) return;
				o.detail.diagnostics = e;
			}
			C = !0, o.detail.error = "";
		} catch (e) {
			s() && !N(e) && (o.detail.error = ln(e));
		} finally {
			s() && (o.detail.loading = !1, an.includes(String(o.detail.job?.status || "")) || (x = window.setTimeout(() => void Z(), 2e3)));
		}
	}
	function ge(t, n) {
		let r = Y(t), i = [...o.jobs, ...o.batch?.items || []].find((e) => String(e.id) === String(r));
		i?.operation_task_id && e.openTask ? e.openTask(i.operation_task_id, i.operation_run_id || null, n || null) : (he(), C = !1, o.detail = {
			...fn(),
			id: r
		}, Z(!1, !0));
	}
	function _e() {
		he(), C = !1, o.detail = fn();
	}
	async function ve(e) {
		let n = Y(e);
		if (!ae(g, n)) return null;
		O?.abort();
		let r = new AbortController();
		O = r;
		let i = () => ie() && O === r && !r.signal.aborted && String(o.detail.id) === String(n);
		o.detail.comparing = !0, o.detail.compareError = "";
		try {
			let e = await t.compare(n, r.signal);
			return i() ? (o.detail.comparison = e, e) : null;
		} catch (e) {
			if (i() && !N(e)) throw o.detail.compareError = ln(e), e;
			return null;
		} finally {
			i() && (o.detail.comparing = !1, O = void 0);
		}
	}
	function ye() {
		r.value = !document.hidden, r.value ? (K(!0), o.detail.id !== null && Z()) : (F(), P(), he());
	}
	function be() {
		i = !0, F(), P(), he(), document.removeEventListener("visibilitychange", ye);
	}
	return document.addEventListener("visibilitychange", ye), ee() && y(be), {
		state: o,
		active: a,
		creating: c,
		registrationUnavailable: l,
		ensureMeta: G,
		load: L,
		loadSummary: W,
		renderEmailSupply: U,
		applySummary: H,
		setVisible: q,
		setView: J,
		setBatch: R,
		updateQuery: ce,
		setPage: B,
		setSize: V,
		shouldPollJobs: se,
		create: fe,
		action: de,
		executeAction: me,
		compare: ve,
		openLog: ge,
		refreshDetail: Z,
		closeDetail: _e,
		notify: u,
		terminalStatuses: an,
		activeStatuses: rn,
		batchActions: pe,
		readBatchProgress: z,
		dispose: be
	};
}
// src/features/registration/RegistrationPage.vue?vue&type=script&setup=true&lang.ts
var mn = ["data-view"], hn = { class: "registration-launch" }, gn = {
	class: "registration-summary",
	"aria-label": "注册与本地邮箱概览"
}, _n = {
	class: "registration-launch-panel",
	"aria-labelledby": "registration-launch-title"
}, vn = { class: "registration-launcher" }, yn = ["disabled", "aria-describedby"], bn = ["value"], xn = { class: "registration-debug" }, Sn = ["disabled", "title"], Cn = { class: "registration-hint registration-hint-bar" }, wn = {
	id: "registrationEmailSupplyHint",
	class: "registration-supply-note"
}, Tn = { class: "ui-list registration-tasks" }, En = {
	class: "ui-list-toolbar registration-count-row",
	"data-registration-count-row": ""
}, Dn = { class: "ui-list-toolbar__main registration-count-main" }, On = { class: "ui-list-count registration-count" }, kn = {
	key: 0,
	class: "registration-selection",
	role: "status"
}, An = { class: "ui-list-toolbar__actions registration-count-actions" }, jn = {
	class: "registration-toolbar",
	role: "group",
	"aria-label": "注册任务操作"
}, Mn = ["disabled"], Nn = ["disabled"], Pn = { class: "registration-mobile-filter" }, Fn = {
	key: 0,
	class: "ui-list-feedback is-error registration-list-error",
	role: "alert"
}, In = {
	class: "ui-table-scroll registration-table-wrap",
	tabindex: "0",
	"aria-label": "注册任务列表，可横向滚动"
}, Ln = { key: 2 }, Rn = { class: "ui-col-check" }, zn = [
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], Bn = { class: "registration-col-email" }, Vn = ["title"], Hn = { key: 0 }, Un = { class: "registration-row-actions" }, Wn = { class: "ui-row-actions registration-row-actions-inner" }, Gn = ["onClick"], Kn = ["onUpdate:modelValue"], qn = ["onClick"], Jn = ["onClick"], Yn = ["onClick"], Xn = ["disabled", "onClick"], Zn = { class: "registration-dialog-title" }, Qn = { id: "registration-log-title" }, $n = ["title"], er = { class: "registration-dialog-body" }, tr = {
	key: 0,
	class: "registration-dialog-status"
}, nr = {
	key: 1,
	class: "registration-dialog-error",
	role: "alert"
}, rr = { class: "registration-dialog-log" }, ir = {
	key: 2,
	class: "registration-dialog-section"
}, ar = { class: "registration-dialog-actions" }, or = ["disabled"], sr = ["href"], cr = { key: 0 }, lr = {
	key: 1,
	class: "registration-dialog-error",
	role: "alert"
}, ur = {
	key: 3,
	class: "registration-dialog-section"
}, dr = ["href"], fr = { class: "registration-dialog-details" }, pr = /* @__PURE__ */ e({
	__name: "RegistrationPage",
	props: { deps: {} },
	setup(e, { expose: s }) {
		let d = e, y = pn(d.deps), { state: C } = y, D = ne({
			defaults: [
				38,
				100,
				220,
				156,
				136,
				170,
				104,
				116,
				116,
				148,
				132
			],
			storageKey: "gpt_console_table_widths_jobs",
			totalStorageKey: "gpt_console_table_total_jobs",
			min: 28,
			max: 2e3
		});
		function ee() {
			D.resetColumns(), d.deps.notify?.("已恢复默认列宽");
		}
		let A = [
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
		], N = m();
		J(N, () => C.detail.id !== null, () => y.active.value);
		let ae = m(1), se = m(3), I = m(""), L = m(!1), R = m(""), z = m(""), ce = m(""), B = m(""), V = m(""), H = m(""), U = m(""), W = m(""), G = m(1), K = m(20), q = m(/* @__PURE__ */ new Set()), Y = m({}), ue = S(() => C.view === "launch"), de = S(() => C.view === "tasks"), fe = S(() => C.jobs), X = m(null), pe = S(() => ({
			id: z.value,
			email: ce.value,
			email_source: B.value,
			status: R.value,
			proxy: V.value,
			error: H.value,
			date_from: U.value,
			date_to: W.value
		})), me = {
			id: "ID",
			email: "邮箱",
			email_source: "邮箱来源",
			status: "状态",
			proxy: "代理",
			error: "错误",
			date_from: "开始日期",
			date_to: "截止日期"
		}, he = S(() => Object.entries(pe.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${me[e]}：${e === "status" ? je(t) : e === "email_source" ? Ae(t) : t}`,
			removeLabel: `清除${me[e]}筛选`
		})));
		function Z(e, t) {
			let n = {
				id: z,
				email: ce,
				email_source: B,
				status: R,
				proxy: V,
				error: H,
				date_from: U,
				date_to: W
			};
			n[e].value = t, X.value = null, ze();
		}
		let ge = (e) => e.error_info ? oe(e.error_info) : e.error_message ? "执行异常" : "—", _e = S(() => C.statusCounts.active ?? [
			"pending",
			"running",
			"stopping"
		].reduce((e, t) => e + Number((Object.keys(C.statusCounts).length ? C.statusCounts : C.batch?.status_counts || {})[t] || 0), 0)), ye = S(() => !!C.meta?.manual_mode), be = m(!1), xe = S(() => {
			let e = new Map((C.meta?.sources || []).map((e) => [String(e.value), {
				value: String(e.value),
				label: e.label || String(e.value)
			}])), t = C.facets.email_source;
			for (let n of Array.isArray(t) ? t : []) {
				let t = String(typeof n == "object" ? n.value : n);
				e.has(t) || e.set(t, {
					value: t,
					label: typeof n == "object" && n.label || t
				});
			}
			return B.value && !e.has(B.value) && e.set(B.value, {
				value: B.value,
				label: B.value
			}), [...e.values()];
		}), Se = S(() => ye.value ? [{
			value: "manual",
			label: "手动配置邮箱"
		}] : C.meta?.sources?.filter((e) => e.enabled === !0) || []), Ce = S(() => C.metaError || C.meta && (y.registrationUnavailable.value || (Se.value.length ? "" : "没有可用的邮箱来源。请先导入本地邮箱，再重新选择。")) || ""), we = S(() => Ce.value || C.metaError || (C.meta ? ye.value ? "使用手动配置的邮箱来源。" : I.value ? "" : "请选择本批使用的邮箱来源。" : "正在读取邮箱来源…")), Te = S(() => C.summary?.email_supply || {}), Ee = (e) => {
			let t = Te.value[e];
			return Number.isInteger(t) && Number(t) >= 0 ? t : Te.value.status === "error" ? "读取失败" : "未知";
		}, De = S(() => `仅统计本地库存；用完后请手动导入；邮箱由 Email Butler 等邮箱服务准备${Te.value.reason ? `；${Te.value.reason}` : ""}`), Oe = S(() => [
			{
				label: "已注册",
				value: C.summary?.accounts ?? "—"
			},
			{
				label: "本地邮箱总数",
				value: Ee("total")
			},
			{
				label: "本地可用",
				value: Ee("available")
			},
			{
				label: "本地已用",
				value: Ee("used")
			},
			{
				label: "本地失败",
				value: Ee("failed")
			}
		]), ke = (e) => C.meta?.registration_drivers?.find((t) => String(t.value) === String(e))?.label || {
			protocol: "本地优化 Protocol（历史）",
			protocol_oss: "开源 Protocol（历史）",
			protocol_oss_2: "开源protocol-2",
			sentinel_rs: "Rust sentinel-rs",
			roxy: "本地 Roxy",
			roxy_oss: "开源 Roxy（历史）"
		}[String(e || "")] || String(e || "未知"), Ae = (e) => xe.value.find((t) => String(t.value) === String(e))?.label || String(e || "-"), je = (e) => ({
			pending: "排队中",
			queued: "排队中",
			waiting: "等待中",
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
			debug_paused: "调试暂停",
			password_confirmation_pending: "失败·密码响应缺失"
		})[String(e)] || String(e || "等待中");
		function Me(e) {
			let t = String(e?.debug_state === "paused" ? "debug_paused" : e?.display_status || e?.status || "");
			return t === "success" ? "success" : [
				"partial_success",
				"debug_paused",
				"stopping"
			].includes(t) ? "warning" : [
				"running",
				"pending",
				"queued",
				"waiting"
			].includes(t) ? "active" : [
				"failed",
				"interrupted",
				"request_unknown",
				"manual_reconcile",
				"attention_required",
				"unsupported",
				"deactivated",
				"password_confirmation_pending"
			].includes(t) ? "danger" : "neutral";
		}
		let Ne = async (e) => d.deps.confirm ? await d.deps.confirm(e) : window.confirm(e);
		function Pe(e) {
			e || (X.value = null), y.setVisible(e);
		}
		function Fe(e) {
			X.value = null, y.setView(e);
		}
		function Ie(e) {
			let t = N.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && y.closeDetail();
		}
		async function Le() {
			if (C.creating || be.value) return;
			if (Ce.value) {
				C.receipt = {
					tone: "warning",
					message: Ce.value
				};
				return;
			}
			let e = Number(ae.value), t = Number(se.value);
			if (!Number.isSafeInteger(e) || e < 1) {
				C.receipt = {
					tone: "warning",
					message: "注册数量必须为有效的正整数"
				};
				return;
			}
			if (!Number.isSafeInteger(t) || t < 1) {
				C.receipt = {
					tone: "warning",
					message: "并发线程数必须为有效的正整数"
				};
				return;
			}
			if (!Se.value.some((e) => e.value === I.value)) {
				C.receipt = {
					tone: "warning",
					message: "请选择本次注册使用的邮箱来源"
				};
				return;
			}
			let n = {
				count: e,
				workers: t,
				email_source: I.value,
				debug_enabled: L.value
			};
			be.value = !0;
			try {
				if (_e.value > 0 && !await Ne(`当前任务表里已有 ${_e.value} 个任务在跑或排队，这次会再加 ${e} 个，确定继续？`)) return;
				let t = await y.create(n);
				Number.isSafeInteger(t?.workers) && t.workers > 0 && (se.value = t.workers);
			} catch {} finally {
				be.value = !1;
			}
		}
		async function Q(e, t) {
			let n = Array.from(q.value);
			try {
				await y.executeAction(e, t, n, L.value), (e === "deleteBulk" || e === "retryBulk") && (q.value = /* @__PURE__ */ new Set());
			} catch {}
		}
		function Re() {
			R.value = z.value = ce.value = B.value = V.value = H.value = U.value = W.value = "", G.value = 1, y.load(We());
		}
		function ze() {
			G.value = 1, y.load(We());
		}
		function Be(e) {
			let t = e.target.checked;
			fe.value.filter((e) => !["running", "stopping"].includes(String(e.status))).forEach((e) => t ? q.value.add(String(e.id)) : q.value.delete(String(e.id))), q.value = new Set(q.value);
		}
		function Ve(e, t) {
			let n = new Set(q.value);
			t.target.checked ? n.add(String(e)) : n.delete(String(e)), q.value = n;
		}
		function He(e) {
			return [
				e.proxy_provider,
				e.proxy_endpoint && e.proxy_endpoint !== "-" ? e.proxy_endpoint : "",
				e.proxy_region && e.proxy_region !== "-" ? e.proxy_region : ""
			].filter(Boolean).join(" · ") || "-";
		}
		function Ue(e) {
			G.value = 1, y.setBatch(e);
		}
		function We() {
			return {
				status: R.value,
				id: z.value,
				email: ce.value,
				email_source: B.value,
				proxy: V.value,
				error: H.value,
				date_from: U.value,
				date_to: W.value,
				page: G.value,
				page_size: K.value
			};
		}
		function Ge(e) {
			let t = String(Y.value[String(e.id)] || "").trim();
			t ? y.action("/api/manual-otp", {
				email: e.email,
				code: t,
				job_id: e.id
			}).then(() => {
				Y.value = {
					...Y.value,
					[String(e.id)]: ""
				};
			}).catch(() => {}) : C.receipt = {
				tone: "warning",
				message: "请先填写邮箱验证码"
			};
		}
		async function Ke() {
			if (C.detail.id != null) try {
				await y.compare(C.detail.id);
			} catch {}
		}
		return s({
			create: y.create,
			runAction: y.executeAction,
			setBatch: y.setBatch,
			loadSources: () => y.ensureMeta(!0),
			load: y.load,
			ensureMeta: y.ensureMeta,
			setVisible: Pe,
			setView: Fe,
			loadSummary: y.loadSummary,
			renderEmailSupply: y.renderEmailSupply,
			applySummary: y.applySummary,
			action: y.action,
			openLog: y.openLog,
			closeDetail: y.closeDetail
		}), r(() => ({ ...C.query }), (e) => {
			G.value = e.page, K.value = e.page_size, z.value = e.id, ce.value = e.email, B.value = e.email_source, R.value = e.status, V.value = e.proxy, H.value = e.error, U.value = e.date_from, W.value = e.date_to;
		}, { immediate: !0 }), r([ye, Se], () => {
			ye.value ? I.value = "manual" : Se.value.some((e) => e.value === I.value) || (I.value = "");
		}, { immediate: !0 }), o(() => {
			y.ensureMeta();
		}), (e, r) => (t(), O("div", {
			class: "registration-vue-page",
			"data-view": E(C).view
		}, [
			i(_("section", hn, [
				_("dl", gn, [(t(!0), O(f, null, a(Oe.value, (e) => (t(), O("div", { key: e.label }, [_("dt", null, h(e.label), 1), _("dd", null, h(typeof e.value == "number" ? e.value.toLocaleString("zh-CN") : e.value), 1)]))), 128))]),
				_("section", _n, [r[24] ||= _("h2", { id: "registration-launch-title" }, "新建注册批次", -1), _("form", {
					novalidate: "",
					onSubmit: b(Le, ["prevent"])
				}, [_("div", vn, [
					_("label", null, [r[20] ||= k("邮箱来源 ", -1), i(_("select", {
						"onUpdate:modelValue": r[0] ||= (e) => I.value = e,
						disabled: !E(C).meta || ye.value || !Se.value.length,
						"aria-describedby": we.value ? "registration-launch-hint registrationEmailSupplyHint" : "registrationEmailSupplyHint"
					}, [r[19] ||= _("option", { value: "" }, "请选择本次邮箱来源", -1), (t(!0), O(f, null, a(Se.value, (e) => (t(), O("option", {
						key: String(e.value),
						value: String(e.value)
					}, h(e.label || e.value), 9, bn))), 128))], 8, yn), [[u, I.value]])]),
					_("label", null, [r[21] ||= k("注册数量", -1), i(_("input", {
						"onUpdate:modelValue": r[1] ||= (e) => ae.value = e,
						min: "1",
						type: "number",
						inputmode: "numeric"
					}, null, 512), [[
						w,
						ae.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", null, [r[22] ||= k("并发线程", -1), i(_("input", {
						"onUpdate:modelValue": r[2] ||= (e) => se.value = e,
						min: "1",
						step: "1",
						type: "number",
						inputmode: "numeric"
					}, null, 512), [[
						w,
						se.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", xn, [i(_("input", {
						"onUpdate:modelValue": r[3] ||= (e) => L.value = e,
						type: "checkbox"
					}, null, 512), [[v, L.value]]), r[23] ||= k(" 调试模式", -1)]),
					_("button", {
						type: "submit",
						class: "registration-start",
						disabled: E(C).creating || be.value || !I.value || !!Ce.value,
						title: Ce.value || void 0
					}, h(E(C).creating ? "提交中…" : "开始注册"), 9, Sn)
				]), _("p", Cn, [
					we.value ? (t(), O("span", {
						key: 0,
						id: "registration-launch-hint",
						class: x(["registration-hint-badge", { "registration-warning": Ce.value }]),
						role: "status"
					}, h(we.value), 3)) : l("", !0),
					E(C).metaError ? (t(), O("button", {
						key: 1,
						type: "button",
						class: "ui-link",
						"data-registration-source-retry": "",
						onClick: r[4] ||= (e) => E(y).ensureMeta(!0)
					}, "重试")) : l("", !0),
					_("span", wn, h(De.value), 1)
				])], 32)]),
				ue.value ? (t(), g(Qt, {
					key: 0,
					batch: E(C).batch,
					batches: E(C).batches,
					"batch-id": E(C).batchId,
					"refresh-generation": E(C).batchRefreshGeneration,
					active: E(y).active.value,
					loading: E(C).loading,
					error: E(C).error,
					actions: E(y).batchActions.value,
					mutating: Object.keys(E(C).pendingActions).length > 0,
					"status-label": je,
					"source-label": Ae,
					"driver-label": ke,
					"read-progress": E(y).readBatchProgress,
					onSelect: Ue,
					onRefresh: r[5] ||= (e) => E(y).load(),
					onBatchAction: r[6] ||= (e) => Q(e),
					onRetry: r[7] ||= (e) => Q("retry", e),
					onLog: E(y).openLog
				}, null, 8, [
					"batch",
					"batches",
					"batch-id",
					"refresh-generation",
					"active",
					"loading",
					"error",
					"actions",
					"mutating",
					"read-progress",
					"onLog"
				])) : l("", !0)
			], 512), [[T, ue.value]]),
			i(_("section", Tn, [
				_("div", En, [_("div", Dn, [
					_("span", On, "共 " + h(E(C).total.toLocaleString()) + " 条任务", 1),
					q.value.size ? (t(), O("span", kn, "已选 " + h(q.value.size) + " 项", 1)) : l("", !0),
					c(te, {
						items: he.value,
						onRemove: r[8] ||= (e) => Z(e, "")
					}, null, 8, ["items"])
				]), _("div", An, [
					_("div", jn, [
						_("button", {
							type: "button",
							class: x(["ui-button registration-toolbar-bulk", { "is-idle": !q.value.size }]),
							onClick: r[9] ||= (e) => Q("retryBulk"),
							disabled: !q.value.size
						}, "重试", 10, Mn),
						_("button", {
							type: "button",
							class: x(["ui-button ui-button--danger registration-toolbar-bulk", { "is-idle": !q.value.size }]),
							onClick: r[10] ||= (e) => Q("deleteBulk"),
							disabled: !q.value.size
						}, "删除", 10, Nn),
						_("button", {
							type: "button",
							class: "ui-button",
							onClick: r[11] ||= (e) => Q("cancelAll")
						}, "取消排队"),
						_("button", {
							type: "button",
							class: "ui-button",
							onClick: ze
						}, "刷新")
					]),
					_("button", {
						type: "button",
						class: "ui-link",
						"aria-label": "恢复注册任务列宽",
						onClick: ee
					}, "恢复列宽"),
					_("span", Pn, [c(ve, {
						values: pe.value,
						sources: xe.value,
						open: X.value === "all",
						"onUpdate:open": r[12] ||= (e) => X.value = e ? "all" : null,
						onChange: Z
					}, null, 8, [
						"values",
						"sources",
						"open"
					])]),
					he.value.length ? (t(), O("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: Re
					}, "清筛")) : l("", !0)
				])]),
				E(C).error ? (t(), O("div", Fn, [k(h(E(C).error) + " ", 1), _("button", {
					type: "button",
					class: "ui-link",
					onClick: ze
				}, "重试")])) : l("", !0),
				_("div", In, [_("table", {
					class: "ui-table ui-table--sticky-end registration-table",
					style: p({ "--ui-table-width": `${E(D).total.value}px` })
				}, [
					_("colgroup", null, [(t(!0), O(f, null, a(E(D).widths.value, (e, n) => (t(), O("col", {
						key: n,
						style: p({ width: `${e}px` })
					}, null, 4))), 128))]),
					_("thead", null, [_("tr", null, [(t(), O(f, null, a(A, (e, n) => _("th", {
						key: e.label,
						class: x({ "ui-col-check": n === 0 })
					}, [n === 0 ? (t(), O("input", {
						key: 0,
						type: "checkbox",
						"aria-label": "选择本页可操作任务",
						onChange: Be
					}, null, 32)) : e.filter ? (t(), g(ve, {
						key: 1,
						column: e.filter,
						values: pe.value,
						sources: xe.value,
						open: X.value === e.filter,
						"onUpdate:open": (t) => X.value = t ? e.filter : null,
						onChange: Z
					}, null, 8, [
						"column",
						"values",
						"sources",
						"open",
						"onUpdate:open"
					])) : (t(), O("span", Ln, h(e.label), 1)), n < A.length - 1 ? (t(), g(re, {
						key: 3,
						label: e.label,
						onStart: (e) => E(D).resize(n, e),
						onNudge: (e) => E(D).resizeWithKeyboard(n, e)
					}, null, 8, [
						"label",
						"onStart",
						"onNudge"
					])) : l("", !0)], 2)), 64))])]),
					_("tbody", null, [fe.value.length ? l("", !0) : (t(), g(j, {
						key: 0,
						colspan: 11,
						loading: E(C).loading,
						"loading-title": "正在加载任务…",
						title: "暂无匹配任务"
					}, null, 8, ["loading"])), (t(!0), O(f, null, a(fe.value, (e) => (t(), O("tr", {
						key: String(e.id),
						class: x({ "is-selected": q.value.has(String(e.id)) })
					}, [
						_("td", Rn, [_("input", {
							type: "checkbox",
							"aria-label": `选择任务 ${e.id}`,
							checked: q.value.has(String(e.id)),
							disabled: ["running", "stopping"].includes(String(e.status)),
							onChange: (t) => Ve(e.id, t)
						}, null, 40, zn)]),
						_("td", null, [c(M, {
							text: `#${e.id}`,
							secondary: e.parent_job_id ? `↳ #${e.parent_job_id}` : void 0
						}, null, 8, ["text", "secondary"])]),
						_("td", Bn, [c(M, {
							text: String(e.email || "—"),
							title: e.email ? String(e.email) : void 0
						}, null, 8, ["text", "title"])]),
						_("td", null, [c(M, { text: Ae(e.email_source) }, null, 8, ["text"])]),
						_("td", null, [c(M, { text: ke(e.registration_driver) }, null, 8, ["text"])]),
						_("td", null, [c(M, {
							text: He(e),
							secondary: String(e.proxy_status || "")
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [_("span", {
							class: x(["ui-badge registration-status-badge", `ui-badge--${Me(e)}`]),
							title: je(e.debug_state === "paused" ? "debug_paused" : e.display_status || e.status)
						}, h(je(e.debug_state === "paused" ? "debug_paused" : e.display_status || e.status)), 11, Vn)]),
						_("td", null, [c(M, {
							class: "ui-time",
							text: E(F)(e.started_at).text,
							secondary: E(F)(e.started_at).secondary,
							title: E(P)(e.started_at)
						}, null, 8, [
							"text",
							"secondary",
							"title"
						])]),
						_("td", null, [c(M, {
							class: "ui-time",
							text: E(F)(e.completed_at).text,
							secondary: E(F)(e.completed_at).secondary,
							title: E(P)(e.completed_at)
						}, null, 8, [
							"text",
							"secondary",
							"title"
						])]),
						_("td", null, [e.error_message || e.error_info ? (t(), g(ie, {
							key: 0,
							"data-registration-result": "",
							label: ge(e),
							title: String(e.error_message || ge(e)),
							tone: "danger"
						}, {
							details: n(() => [_("p", null, h(e.error_message || ge(e)), 1), e.error_info ? (t(), O("p", Hn, h(e.error_info), 1)) : l("", !0)]),
							_: 2
						}, 1032, ["label", "title"])) : (t(), g(M, {
							key: 1,
							text: "—"
						}))]),
						_("td", Un, [_("div", Wn, [
							_("button", {
								type: "button",
								class: "ui-link",
								onClick: (t) => E(y).openLog(e.id)
							}, "日志", 8, Gn),
							e.manual_otp_required && e.status === "running" ? (t(), O(f, { key: 0 }, [i(_("input", {
								"onUpdate:modelValue": (t) => Y.value[String(e.id)] = t,
								class: "registration-otp-input",
								placeholder: "邮箱验证码"
							}, null, 8, Kn), [[w, Y.value[String(e.id)]]]), _("button", {
								type: "button",
								class: "ui-button registration-otp-btn",
								onClick: (t) => Ge(e)
							}, "提交验证码", 8, qn)], 64)) : l("", !0),
							[
								"pending",
								"running",
								"stopping"
							].includes(String(e.status)) ? (t(), O("button", {
								key: 1,
								type: "button",
								class: "ui-link ui-link--danger",
								onClick: (t) => Q("stop", e)
							}, "停止", 8, Jn)) : l("", !0),
							e.retryable ? (t(), O("button", {
								key: 2,
								type: "button",
								class: "ui-link",
								onClick: (t) => Q("retry", e)
							}, "重试", 8, Yn)) : l("", !0),
							_("button", {
								type: "button",
								class: "ui-link ui-link--danger",
								disabled: ["running", "stopping"].includes(String(e.status)),
								onClick: (t) => Q("delete", e)
							}, "删除", 8, Xn)
						])])
					], 2))), 128))])
				], 4)]),
				c(le, {
					label: "注册任务分页",
					page: G.value,
					size: K.value,
					total: E(C).total,
					busy: E(C).loading,
					"onUpdate:page": r[13] ||= (e) => {
						G.value = e, E(y).load(We());
					},
					"onUpdate:size": r[14] ||= (e) => {
						K.value = e, G.value = 1, E(y).load(We());
					}
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			], 512), [[T, de.value]]),
			E(C).receipt ? (t(), O("div", {
				key: 0,
				class: x(["registration-receipt", `is-${E(C).receipt.tone}`]),
				role: "status"
			}, h(E(C).receipt.message), 3)) : l("", !0),
			_("dialog", {
				ref_key: "logDialog",
				ref: N,
				class: "registration-dialog registration-log-dialog",
				"aria-labelledby": "registration-log-title",
				onCancel: r[17] ||= b((...e) => E(y).closeDetail && E(y).closeDetail(...e), ["prevent"]),
				onClose: r[18] ||= (...e) => E(y).closeDetail && E(y).closeDetail(...e),
				onClick: Ie
			}, [_("header", null, [_("div", Zn, [_("h2", Qn, "任务 #" + h(E(C).detail.id) + " 日志", 1), E(C).detail.job ? (t(), O(f, { key: 0 }, [E(C).detail.job.email ? (t(), O("span", {
				key: 0,
				class: "registration-dialog-email",
				title: String(E(C).detail.job.email)
			}, h(E(C).detail.job.email), 9, $n)) : l("", !0), _("span", { class: x(["ui-badge registration-status-badge", `ui-badge--${Me(E(C).detail.job)}`]) }, h(je(E(C).detail.job.debug_state === "paused" ? "debug_paused" : E(C).detail.job.display_status || E(C).detail.job.status)), 3)], 64)) : l("", !0)]), _("button", {
				type: "button",
				class: "ui-button registration-dialog-close",
				onClick: r[15] ||= (...e) => E(y).closeDetail && E(y).closeDetail(...e)
			}, "关闭")]), _("div", er, [
				E(C).detail.loading ? (t(), O("p", tr, "加载中…")) : l("", !0),
				E(C).detail.error ? (t(), O("p", nr, h(E(C).detail.error), 1)) : l("", !0),
				_("pre", rr, h(E(C).detail.log || "（暂无日志）"), 1),
				E(C).detail.debug?.enabled ? (t(), O("div", ir, [
					r[25] ||= _("strong", null, "网络调试", -1),
					_("div", ar, [
						_("button", {
							type: "button",
							class: "ui-button",
							disabled: E(C).detail.comparing,
							onClick: Ke
						}, "与同批成功任务对比", 8, or),
						_("a", {
							class: "ui-link",
							href: `/api/jobs/${E(C).detail.id}/debug/har`,
							download: ""
						}, "下载脱敏 HAR", 8, sr),
						_("button", {
							type: "button",
							class: "ui-button ui-button--primary",
							onClick: r[16] ||= (e) => E(y).action(`/api/jobs/${E(C).detail.id}/debug/release`, { action: "finish" })
						}, "结束调试并收口")
					]),
					E(C).detail.comparison ? (t(), O("pre", cr, h(typeof E(C).detail.comparison == "object" ? JSON.stringify(E(C).detail.comparison, null, 2) : E(C).detail.comparison), 1)) : l("", !0),
					E(C).detail.compareError ? (t(), O("p", lr, h(E(C).detail.compareError), 1)) : l("", !0)
				])) : l("", !0),
				E(C).detail.diagnostics?.captured ? (t(), O("div", ur, [
					r[27] ||= _("strong", null, "失败诊断", -1),
					E(C).detail.diagnostics.screenshot_url ? (t(), O("a", {
						key: 0,
						class: "ui-link",
						href: String(E(C).detail.diagnostics.screenshot_url),
						target: "_blank",
						rel: "noopener"
					}, "打开失败截图", 8, dr)) : l("", !0),
					_("details", fr, [r[26] ||= _("summary", null, "完整诊断证据", -1), _("pre", null, h(typeof E(C).detail.diagnostics == "object" ? JSON.stringify(E(C).detail.diagnostics, null, 2) : E(C).detail.diagnostics), 1)])
				])) : l("", !0)
			])], 544)
		], 8, mn));
	}
});
// src/registration.ts
function mr(e, t = {}) {
	let n = C(pr, { deps: {
		...t,
		api: t.api || en()
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
export { mr as mountRegistration };
