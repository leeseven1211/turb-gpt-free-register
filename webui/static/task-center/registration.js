import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, S as c, _ as l, a as u, c as d, d as f, dt as p, et as m, ft as h, g, h as _, i as v, j as y, l as b, lt as x, m as S, n as C, o as w, s as T, st as E, t as D, v as O, w as k, x as A } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { n as j, r as M, t as ee } from "./ListFilterSummary-Bc1S5NP4.js";
import { t as te } from "./useColumnWidths-D1sKP53m.js";
import { n as N } from "./time-DOD6oyhP.js";
import { t as ne } from "./ListResult-BkPTMQVQ.js";
import { t as re } from "./errorLabels-B-XqaTSM.js";
import { O as P, _ as ie, a as ae, b as F, g as I, h as L, i as R, n as oe, p as z, r as B, t as V, v as H, x as U, y as W } from "./StepEvidence-CNs3ZCIS.js";
import { t as se } from "./useNativeDialog-DWisXYg9.js";
import { t as ce } from "./ListPagination-BjETSj81.js";
import { n as G, r as K } from "./client-B5R_MNgP.js";
import { a as q, r as le } from "./taskIds-BlchWwUp.js";
// src/features/registration/RegistrationFilters.vue?vue&type=script&setup=true&lang.ts
var ue = { class: "registration-filter-fields" }, J = { key: 0 }, Y = ["value"], de = ["value", "aria-label"], fe = ["value"], X = ["value"], pe = ["value"], me = [
	"type",
	"value",
	"aria-label"
], he = { class: "list-filter-actions" }, ge = /*#__PURE__*/ D(/* @__PURE__ */ e({
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
		return (r, s) => (t(), g(M, {
			label: e.column ? o[e.column] : "注册任务",
			"trigger-label": e.column ? o[e.column] : "筛选",
			active: e.column ? !!e.values[e.column] : Object.values(e.values).some(Boolean),
			summary: y.value,
			open: e.open,
			"onUpdate:open": s[7] ||= (e) => c("update:open", e)
		}, {
			default: n(() => [_("div", ue, [
				e.column ? l("", !0) : (t(), O("label", J, [s[8] ||= A("筛选列", -1), i(_("select", {
					"onUpdate:modelValue": s[0] ||= (e) => p.value = e,
					"aria-label": "选择注册任务筛选列"
				}, [(t(), O(f, null, a(o, (e, t) => _("option", {
					key: t,
					value: t
				}, h(e), 9, Y)), 64))], 512), [[u, p.value]])])),
				_("label", null, [A(h(o[v.value]) + " ", 1), v.value === "email_source" ? (t(), O("select", {
					key: 0,
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[1] ||= (e) => C(e.target.value)
				}, [s[9] ||= _("option", { value: "" }, "全部邮箱来源", -1), (t(!0), O(f, null, a(e.sources, (e) => (t(), O("option", {
					key: e.value,
					value: e.value
				}, h(e.label || e.value), 9, fe))), 128))], 40, de)) : v.value === "status" ? (t(), O("select", {
					key: 1,
					value: y.value,
					"aria-label": "筛选状态值",
					onChange: s[2] ||= (e) => C(e.target.value)
				}, [s[10] ||= _("option", { value: "" }, "全部状态", -1), (t(!0), O(f, null, a(b.value, (e) => (t(), O("option", {
					key: e,
					value: e
				}, h(x(e)), 9, pe))), 128))], 40, X)) : (t(), O("input", {
					key: 2,
					type: v.value.startsWith("date_") ? "date" : "search",
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[3] ||= (e) => C(e.target.value),
					onKeydown: s[4] ||= d((e) => c("update:open", !1), ["enter"])
				}, null, 40, me))]),
				_("div", he, [_("button", {
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
}), [["__scopeId", "data-v-e4a53bb8"]]), Z = { class: "registration-progress" }, _e = {
	key: 0,
	class: "registration-stage-heading"
}, ve = { key: 0 }, ye = {
	key: 1,
	class: "registration-steps",
	"aria-label": "注册执行阶段，排列不代表固定顺序"
}, be = [
	"title",
	"aria-pressed",
	"onClick"
], xe = {
	key: 0,
	class: "registration-step-mark",
	"aria-hidden": "true"
}, Se = {
	key: 1,
	class: "registration-step-mark",
	"aria-hidden": "true"
}, Ce = { "data-registration-step-duration": "" }, we = { key: 0 }, Te = ["aria-label", "onClick"], Ee = {
	key: 2,
	class: "registration-stage-selected"
}, De = { "aria-live": "polite" }, Oe = { key: 0 }, ke = { key: 1 }, Ae = { class: "registration-batch-actions" }, je = ["aria-label"], Me = {
	key: 3,
	class: "registration-step-note"
}, Ne = { key: 4 }, Q = { key: 0 }, Pe = /* @__PURE__ */ e({
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
			return ae(e.map((e, t) => ({
				...e,
				id: String(e.id || e.step_id || e.key || `step-${t + 1}`),
				label: e.label || e.name || e.id || e.step_id
			})));
		}), s = m(), u = m(), d = m(), p = S(() => {
			if (!r.inline) return;
			if (d.value) return o.value.find((e) => H(e) === d.value);
			if (!r.focusFailure) return;
			let e = String(z(r.job?.progress?.failure).step_id || "");
			return o.value.find((t) => H(t) === e) || o.value.find((e) => F(e) === "failed");
		});
		function v(e) {
			r.inline ? d.value = H(e) : i("log", H(e));
		}
		se(u, () => !!s.value && r.active, () => r.active);
		let y = (e) => P(ie(e));
		function C(e) {
			let t = z(e.debug_pause);
			return t.state === "paused" ? `调试暂停 · 等待结束调试${t.paused_at ? ` · 暂停于 ${N(t.paused_at)}` : " · 暂停时间未记录"}${t.hold_until ? ` · 保留至 ${N(t.hold_until)}` : ""}` : "";
		}
		function w(e) {
			let t = e.attempts || [], n = e.children || [], i = (e) => e.raw_stage_label || n.find((t) => t.id === e.raw_stage)?.label || e.raw_stage || "阶段", a = [...new Set(t.map(i))];
			return [
				`${W(e)} · ${R(e)}`,
				C(e),
				e.reason || e.message || "",
				`开始：${N(e.started_at)}`,
				`结束：${N(e.completed_at)}`,
				`耗时：${y(e)}`,
				a.length ? `已记录阶段：${a.join("、")}` : "",
				n.length ? `子步骤（${n.length}）` : "",
				...n.map((e) => `${W(e)} · ${R(e)} · ${y(e)}${e.reason || e.message ? `\n${e.reason || e.message}` : ""}`),
				t.length ? `阶段事件（${t.length} 条）` : "",
				...t.map((e, t) => `${t + 1}. ${i(e)} · ${L(e.display_status || e.state)}${e.created_at ? ` · ${N(e.created_at)}` : e.event_time_known === !1 ? " · 发生时间未记录" : ""}${e.message ? `\n${e.message}` : ""}`),
				r.inline ? "点击步骤查看阶段摘要" : "点击步骤查看对应日志"
			].filter(Boolean).join("\n");
		}
		return (n, r) => (t(), O("div", Z, [
			o.value.length ? (t(), O("div", _e, [e.inline ? (t(), O("h3", ve, "执行阶段")) : l("", !0), r[5] ||= _("p", { class: "registration-step-note" }, "按首次记录排列，不代表固定执行顺序", -1)])) : l("", !0),
			o.value.length ? (t(), O("ul", ye, [(t(!0), O(f, null, a(o.value, (n) => (t(), O("li", {
				key: E(H)(n),
				class: x([`is-${E(F)(n)}`, { "is-inspected": p.value === n }])
			}, [_("button", {
				type: "button",
				title: w(n),
				"aria-pressed": e.inline ? p.value === n : void 0,
				onClick: (e) => v(n)
			}, [
				_("strong", null, [E(F)(n) === "success" ? (t(), O("span", xe, "✓")) : E(F)(n) === "failed" ? (t(), O("span", Se, "!")) : l("", !0), A(" " + h(E(W)(n)), 1)]),
				_("small", null, h(E(R)(n)), 1),
				_("small", Ce, "耗时 " + h(y(n)), 1),
				(t(!0), O(f, null, a(E(B)(n), (e) => (t(), O("small", { key: e }, h(e), 1))), 128)),
				C(n) ? (t(), O("small", we, h(C(n)), 1)) : l("", !0)
			], 8, be), e.inline ? l("", !0) : (t(), O("button", {
				key: 0,
				type: "button",
				"aria-label": `查看${E(W)(n)}的关系与证据`,
				onClick: (e) => s.value = n
			}, "详情", 8, Te))], 2))), 128))])) : l("", !0),
			p.value ? (t(), O("div", Ee, [_("div", De, [
				_("strong", null, h(E(W)(p.value)), 1),
				_("span", null, " · " + h(E(R)(p.value)), 1),
				p.value.reason || p.value.message ? (t(), O("p", Oe, h(p.value.reason || p.value.message), 1)) : e.focusFailure && E(H)(p.value) === E(z)(e.job.progress?.failure).step_id && E(z)(e.job.progress?.failure).message ? (t(), O("p", ke, h(E(z)(e.job.progress?.failure).message), 1)) : l("", !0)
			]), _("div", Ae, [_("button", {
				type: "button",
				"aria-label": `查看${E(W)(p.value)}的关系与证据`,
				onClick: r[0] ||= (e) => s.value = p.value
			}, "阶段详情", 8, je), _("button", {
				type: "button",
				onClick: r[1] ||= (e) => i("log", E(H)(p.value))
			}, "阶段日志")])])) : o.value.length ? l("", !0) : (t(), O("p", Me, "暂无阶段记录，可查看任务日志。")),
			o.value.length ? (t(), O("details", Ne, [r[6] ||= _("summary", null, "依赖与执行记录", -1), (t(!0), O(f, null, a(o.value, (e) => (t(), O("div", { key: E(H)(e) }, [_("strong", null, h(E(W)(e)), 1), c(oe, {
				step: e,
				siblings: o.value
			}, null, 8, ["step", "siblings"])]))), 128))])) : l("", !0),
			_("dialog", {
				ref_key: "dialog",
				ref: u,
				class: "registration-dialog",
				"aria-label": "注册步骤关系与证据",
				onCancel: r[3] ||= b((e) => s.value = void 0, ["prevent"]),
				onClose: r[4] ||= (e) => s.value = void 0
			}, [
				_("header", null, [_("h3", null, h(s.value ? E(W)(s.value) : "步骤详情"), 1), _("button", {
					type: "button",
					onClick: r[2] ||= (e) => s.value = void 0
				}, "关闭")]),
				s.value && C(s.value) ? (t(), O("p", Q, h(C(s.value)), 1)) : l("", !0),
				s.value ? (t(), g(V, {
					key: 1,
					step: s.value,
					siblings: o.value
				}, null, 8, ["step", "siblings"])) : l("", !0)
			], 544)
		]));
	}
}), Fe = ["aria-busy"], Ie = { class: "registration-batch-header" }, Le = { class: "registration-batch-title" }, Re = ["data-tone"], ze = {
	key: 1,
	class: "registration-hint"
}, Be = {
	key: 0,
	class: "registration-hint registration-batch-meta"
}, Ve = { key: 0 }, He = { key: 1 }, Ue = {
	key: 0,
	class: "registration-batch-actions"
}, We = ["value"], Ge = ["value"], Ke = ["disabled"], qe = ["disabled"], Je = ["disabled"], Ye = {
	key: 0,
	class: "registration-batch-notice",
	role: "alert"
}, Xe = {
	key: 1,
	class: "registration-batch-notice"
}, Ze = {
	class: "registration-batch-meter",
	"aria-hidden": "true"
}, Qe = ["data-tone"], $e = {
	class: "registration-batch-filters",
	role: "group",
	"aria-label": "按批次任务状态筛选"
}, et = [
	"data-batch-filter",
	"aria-pressed",
	"onClick"
], tt = ["data-tone"], nt = ["data-tone"], rt = { class: "registration-batch-row" }, it = { class: "registration-batch-identity" }, at = { class: "registration-batch-result" }, ot = ["data-tone"], st = { key: 0 }, ct = { class: "registration-batch-actions registration-batch-row-actions" }, lt = [
	"aria-label",
	"aria-expanded",
	"aria-controls",
	"onClick"
], ut = ["aria-label", "onClick"], dt = ["disabled", "onClick"], ft = ["id", "hidden"], pt = { key: 0 }, mt = { key: 1 }, ht = {
	key: 0,
	class: "registration-batch-notice"
}, gt = {
	class: "registration-batch-footer registration-hint",
	"aria-live": "polite"
}, _t = /* @__PURE__ */ e({
	__name: "RegistrationBatchPanel",
	props: {
		batch: {},
		batches: {},
		batchId: {},
		active: { type: Boolean },
		loading: { type: Boolean },
		error: {},
		actions: {},
		mutating: { type: Boolean },
		statusLabel: { type: Function },
		sourceLabel: { type: Function },
		driverLabel: { type: Function }
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
				key: "active",
				label: "运行 / 排队"
			},
			{
				key: "other",
				label: "其他"
			}
		], u = m("all"), d = m(null), g = m(!1), v = S(() => i.batch?.items || []), y = S(() => i.batch && !i.batches.some((e) => String(e.batch_id) === String(i.batch?.batch_id)) ? [i.batch, ...i.batches] : i.batches), b = (e) => e.status || e.display_status || "";
		function x(e) {
			let t = b(e);
			return t === "success" || t === "failed" ? t : [
				"running",
				"pending",
				"stopping"
			].includes(t) ? "active" : "other";
		}
		let C = S(() => {
			let e = {
				all: v.value.length,
				success: 0,
				failed: 0,
				active: 0,
				other: 0
			};
			for (let t of v.value) e[x(t)]++;
			return e;
		}), w = S(() => s.filter((e) => e.key !== "other" || C.value.other || u.value === "other")), T = S(() => u.value === "all" ? v.value : v.value.filter((e) => x(e) === u.value)), D = S(() => T.value.map((e) => ({
			job: e,
			tone: x(e),
			result: ne(e)
		}))), k = S(() => {
			let e = C.value;
			return e.all ? e.active ? {
				label: v.value.some((e) => b(e) !== "pending" && x(e) === "active") ? "运行中" : "排队中",
				tone: "active"
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
		}), j = (e, t) => {
			let n = Date.parse(U(t)) - Date.parse(U(e));
			return Number.isFinite(n) && n >= 0 ? P(n) : "";
		}, M = S(() => j(i.batch?.started_at, i.batch?.completed_at)), ee = (e) => e.toLocaleString("zh-CN"), te = (e) => z(z(e.progress).failure);
		function ne(e) {
			if (x(e) === "failed" || b(e) === "partial_success") {
				let t = e.error_info ? re(z(e.error_info)) : "", n = U(te(e).label);
				return t && t !== "执行异常" ? t : n && Array.from(n).length <= 10 ? n : t || "执行异常";
			}
			return x(e) === "active" ? U(z(z(e.progress).current).label) : j(e.started_at, e.completed_at);
		}
		function ie(e) {
			return e.debug_state === "paused" ? "调试暂停" : i.statusLabel(e.display_status || b(e));
		}
		function ae(e) {
			let t = e.status_counts || {}, n = Number(t.running || 0) + Number(t.stopping || 0), r = Number(t.pending || 0);
			return `${e.created_at ? N(e.created_at).replace(/:\d{2}$/, "") : String(e.batch_id)} · ${n || r ? `运行 ${n} / 等待 ${r}` : `成功 ${t.success || 0} / 失败 ${t.failed || 0}`}`;
		}
		function F(e) {
			u.value = e, d.value = null, g.value = !1, e === "failed" && T.value.length === 1 && (d.value = String(T.value[0].id), g.value = !0);
		}
		function L(e) {
			let t = String(e.id);
			d.value = d.value === t ? null : t, g.value = d.value !== null && x(e) === "failed";
		}
		return r(() => i.batchId, () => F("all")), (n, r) => (t(), O("section", {
			class: "registration-batch",
			"aria-labelledby": "registration-batch-title",
			"aria-busy": e.loading
		}, [
			_("header", Ie, [_("div", null, [_("div", Le, [
				r[5] ||= _("h2", { id: "registration-batch-title" }, "任务批次进度", -1),
				e.batch ? (t(), O("span", {
					key: 0,
					class: "registration-state",
					"data-tone": k.value.tone
				}, h(k.value.label), 9, Re)) : l("", !0),
				e.batch?.projection_delayed ? (t(), O("span", ze, "进度同步中")) : l("", !0)
			]), e.batch ? (t(), O("p", Be, [
				_("span", null, h(ee(e.batch.total ?? C.value.all)) + " 个任务", 1),
				e.batch.workers ? (t(), O("span", Ve, "并发 " + h(e.batch.workers), 1)) : l("", !0),
				M.value ? (t(), O("span", He, "批次耗时 " + h(M.value), 1)) : l("", !0)
			])) : l("", !0)]), y.value.length ? (t(), O("div", Ue, [
				_("select", {
					value: e.batchId,
					"aria-label": "选择任务批次",
					onChange: r[0] ||= (e) => o("select", e.target.value)
				}, [(t(!0), O(f, null, a(y.value, (e) => (t(), O("option", {
					key: String(e.batch_id),
					value: String(e.batch_id)
				}, h(ae(e)), 9, Ge))), 128))], 40, We),
				e.actions.stopBatch ? (t(), O("button", {
					key: 0,
					type: "button",
					disabled: e.mutating,
					onClick: r[1] ||= (e) => o("batchAction", "stopBatch")
				}, "停止运行", 8, Ke)) : l("", !0),
				e.actions.cancelBatch ? (t(), O("button", {
					key: 1,
					type: "button",
					disabled: e.mutating,
					onClick: r[2] ||= (e) => o("batchAction", "cancelBatch")
				}, "取消排队", 8, qe)) : l("", !0),
				e.actions.retryBatch ? (t(), O("button", {
					key: 2,
					type: "button",
					disabled: e.mutating,
					onClick: r[3] ||= (e) => o("batchAction", "retryBatch")
				}, "重跑失败", 8, Je)) : l("", !0)
			])) : l("", !0)]),
			e.error ? (t(), O("div", Ye, [A(h(e.error) + " ", 1), _("button", {
				type: "button",
				onClick: r[4] ||= (e) => o("refresh")
			}, "刷新批次")])) : !e.batch || !v.value.length ? (t(), O("p", Xe, h(e.loading ? "正在读取任务批次…" : "暂无注册任务批次"), 1)) : l("", !0),
			e.batch && C.value.all ? (t(), O(f, { key: 2 }, [
				_("div", Ze, [(t(!0), O(f, null, a(w.value.slice(1), (e) => (t(), O("span", {
					key: e.key,
					"data-tone": e.key,
					style: p({ flexGrow: C.value[e.key] })
				}, null, 12, Qe))), 128))]),
				_("div", $e, [(t(!0), O(f, null, a(w.value, (e) => (t(), O("button", {
					key: e.key,
					type: "button",
					"data-batch-filter": e.key,
					"aria-pressed": u.value === e.key,
					onClick: (t) => F(e.key)
				}, [e.key === "all" ? l("", !0) : (t(), O("span", {
					key: 0,
					class: "registration-status-dot",
					"data-tone": e.key,
					"aria-hidden": "true"
				}, null, 8, tt)), A(h(e.label) + " " + h(ee(C.value[e.key])), 1)], 8, et))), 128))]),
				(t(!0), O(f, null, a(D.value, ({ job: n, tone: i, result: s }) => (t(), O("article", {
					key: String(n.id),
					class: "registration-batch-card",
					"data-tone": i
				}, [_("div", rt, [
					_("div", it, [_("strong", null, h(n.email || "准备邮箱中…"), 1), _("small", null, h([n.email_source && e.sourceLabel(n.email_source), n.registration_driver && e.driverLabel(n.registration_driver)].filter(Boolean).join(" · ") || `#${n.id}`), 1)]),
					_("div", at, [_("span", {
						class: "registration-state",
						"data-tone": i
					}, h(ie(n)), 9, ot), s ? (t(), O("small", st, h(s), 1)) : l("", !0)]),
					_("div", ct, [
						_("button", {
							type: "button",
							"aria-label": `查看阶段 · ${n.email || `任务 #${n.id}`}`,
							"aria-expanded": d.value === String(n.id),
							"aria-controls": `registration-stages-${n.id}`,
							onClick: (e) => L(n)
						}, "阶段", 8, lt),
						_("button", {
							type: "button",
							"aria-label": `查看日志 · ${n.email || `任务 #${n.id}`}`,
							onClick: (e) => o("log", n.id)
						}, "日志", 8, ut),
						n.retryable ? (t(), O("button", {
							key: 0,
							type: "button",
							disabled: e.mutating,
							onClick: (e) => o("retry", n)
						}, h(n.retry_label || "重试"), 9, dt)) : l("", !0)
					])
				]), _("div", {
					id: `registration-stages-${n.id}`,
					class: "registration-batch-evidence",
					hidden: d.value !== String(n.id)
				}, [d.value === String(n.id) ? (t(), O(f, { key: 0 }, [
					c(Pe, {
						job: n,
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
					n.error_message ? (t(), O("details", pt, [r[6] ||= _("summary", null, "原始错误摘要", -1), _("p", null, h(n.error_message), 1)])) : l("", !0),
					E(I)(n.attempts).length || E(I)(n.route_attempts).length ? (t(), O("details", mt, [
						r[7] ||= _("summary", null, "尝试与线路记录", -1),
						(t(!0), O(f, null, a(E(I)(n.attempts), (n) => (t(), O("p", { key: E(U)(n.id || n.attempt_id) }, h(e.statusLabel(n.status)) + " · " + h(n.error_message || "已记录"), 1))), 128)),
						(t(!0), O(f, null, a(E(I)(n.route_attempts), (n) => (t(), O("p", { key: E(U)(n.route_attempt_no) }, " 线路尝试 " + h(n.route_attempt_no || 1) + " · " + h(n.retry_reason || e.statusLabel(n.status)), 1))), 128))
					])) : l("", !0)
				], 64)) : l("", !0)], 8, ft)], 8, nt))), 128)),
				T.value.length ? l("", !0) : (t(), O("p", ht, "没有符合条件的任务")),
				_("p", gt, "显示 " + h(ee(T.value.length)) + " 条任务", 1)
			], 64)) : l("", !0)
		], 8, Fe));
	}
}), $ = (e, t = {}) => K(e, t, le), vt = (e) => ({
	method: "POST",
	headers: { "Content-Type": "application/json" },
	body: JSON.stringify(e ?? {})
});
function yt() {
	return {
		metadata: (e) => Promise.all([$("/api/email-sources", { signal: e }), $("/api/capabilities", { signal: e })]).then(([e, t]) => ({
			...e,
			capabilities: t
		})),
		summary: (e) => $("/api/summary", { signal: e }),
		jobs: (e, t) => $(`/api/jobs?${new URLSearchParams(Object.entries(e).map(([e, t]) => [e, String(t)]))}`, { signal: t }),
		create: (e, t) => $("/api/jobs", {
			...vt(e),
			signal: t
		}),
		action: (e, t = {}, n) => $(e, {
			...vt(t),
			signal: n
		}),
		log: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/log`, { signal: t }),
		debug: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/debug?limit=300`, { signal: t }),
		diagnostics: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/diagnostics?limit=100`, { signal: t }),
		compare: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/debug/compare`, { signal: t })
	};
}
// src/features/registration/useRegistration.ts
var bt = [
	"pending",
	"running",
	"stopping"
], xt = [
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
], St = [
	"failed",
	"partial_success",
	"stopped",
	"cancelled",
	"interrupted",
	"request_unknown",
	"manual_reconcile",
	"attention_required"
], Ct = () => ({
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
}), wt = (e) => e instanceof Error ? e.message : "请求失败", Tt = (e) => e == null ? "" : String(e).trim(), Et = (e) => encodeURIComponent(String(q(e))), Dt = () => ({
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
function Ot(e) {
	let t = e.api || yt(), n = m(!!e.visible), r = m(!document.hidden), i = !1, a = S(() => n.value && r.value && !i), o = s({
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
		query: Ct(),
		batchId: "",
		statusCounts: {},
		facets: {},
		creating: !1,
		pendingActions: {},
		lastCreate: null,
		lastAction: null,
		detail: Dt()
	}), c = S(() => o.creating), l = S(() => {
		let e = o.meta?.capabilities?.features?.register;
		return e?.enabled === !1 ? String(e.reason || "功能缺少必要配置") : "";
	}), u = (t) => e.notify?.(t), d = 0, f = 0, p = 0, h = 0, g = 0, _, v, b, x, C, w, T, E, D = "", O = 0, A = 0, j = !0, M, ee = /* @__PURE__ */ new Map(), te = () => !i && r.value && o.detail.id !== null, N = (e, t) => te() && e === g && String(o.detail.id) === String(t);
	function ne() {
		d++, x?.controller.abort(), x = void 0, o.loading = !1;
	}
	function re() {
		ne(), p++, C?.controller.abort(), C = void 0, h++, w?.controller.abort(), w = void 0;
	}
	function P() {
		window.clearInterval(_), window.clearInterval(v), _ = v = void 0;
	}
	function ie() {
		if (!a.value) return !1;
		if (o.view === "tasks") return !0;
		let e = o.batch;
		return !e || String(e.batch_id) !== o.batchId || e.projection_delayed ? !0 : bt.some((t) => Number(e.status_counts?.[t] || 0) > 0) || e.items.some((e) => bt.includes(String(e.status || "")));
	}
	function ae(e) {
		for (let t of Object.keys(Ct())) {
			let n = e[t];
			if (n !== void 0) {
				if (t === "page" || t === "page_size") {
					let e = Number(n);
					Number.isSafeInteger(e) && e > 0 && (o.query[t] = t === "page_size" ? Math.min(e, 500) : e);
				} else o.query[t] = String(n);
			}
		}
		if (e.progress_batch_id !== void 0) {
			let t = Tt(e.progress_batch_id);
			t !== o.batchId && (o.batchId = t, o.batch = null);
		}
	}
	function F(e = {}) {
		if (ae(e), !a.value || e.automatic && !ie()) return Promise.resolve();
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
					s === "tasks" && e.automatic && D === n && Date.now() - O < 3e4 && (a.include_facets = 0);
					let u = await t.jobs(a, i.signal);
					if (!l()) return;
					if (Object.prototype.hasOwnProperty.call(u, "status_counts") && (o.statusCounts = u.status_counts || {}), s === "launch") {
						o.batches = u.progress_batches || [];
						let e = u.progress_batch || null;
						if (!e && o.batchId) {
							let e = Tt(o.batches[0]?.batch_id);
							if (e !== o.batchId && (o.batchId = e, o.batch = null, e && !r)) continue;
						}
						!o.batchId && e?.batch_id && (o.batchId = Tt(e.batch_id)), o.batch = e;
					} else {
						o.total = Math.max(0, Number(u.total ?? u.items?.length ?? 0) || 0), Object.prototype.hasOwnProperty.call(u, "facets") && (o.facets = u.facets || {}, D = n, O = Date.now());
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
				l() && !G(e) && (o.error = wt(e));
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
	function I(e) {
		return F({ progress_batch_id: Tt(e) });
	}
	function L(e) {
		return F({
			...e,
			page: e.page ?? 1
		});
	}
	function R(e) {
		return F({ page: e });
	}
	function oe(e) {
		return F({
			page: 1,
			page_size: e
		});
	}
	function z(e) {
		o.summary = e;
	}
	function B(e) {
		o.summary = {
			...o.summary || {},
			email_supply: e || {}
		};
	}
	function V() {
		if (!a.value) return Promise.resolve();
		C?.controller.abort();
		let e = ++p, n = new AbortController(), r = (async () => {
			try {
				let r = await t.summary(n.signal);
				e === p && a.value && z(r);
			} catch (t) {
				e === p && a.value && !G(t) && B({
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
	function H(e = !1) {
		if (e && (j = !0), !a.value || !j && o.meta && Date.now() - A < 3e4) return Promise.resolve();
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
				}, A = Date.now(), j = !1;
			} catch (e) {
				n === h && a.value && !G(e) && (o.error = wt(e));
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
	function U() {
		P(), a.value && (H(), F({ coalesce: !0 }), V(), _ = window.setInterval(() => {
			F({ automatic: !0 });
		}, 5e3), v = window.setInterval(() => {
			C || V();
		}, 1e4));
	}
	function W(e) {
		n.value !== e && (n.value = e, e ? U() : (P(), re()));
	}
	function se(e) {
		["launch", "tasks"].includes(e) && o.view !== e && (o.view = e, ne(), F({ coalesce: !0 }));
	}
	function ce(e, t = "已受理") {
		let n = e.message || e.warning || (e.started_count == null ? e.deleted_count == null ? e.cancelled == null ? t : `已取消 ${e.cancelled} 个排队任务` : `已删除 ${e.deleted_count} 个任务` : `已提交 ${e.started_count} 个失败任务`), r = Array.isArray(e.skipped) ? e.skipped.length : 0;
		o.receipt = {
			tone: e.warning ? "warning" : "success",
			message: String(n) + (r ? `，跳过 ${r} 个` : "")
		}, u(o.receipt.message);
	}
	function K(e) {
		let t = Tt(e.jobs?.[0]?.batch_id || e.job?.batch_id || e.batch_id);
		t && (o.batchId = t, o.batch = null);
	}
	function le(e, n = {}) {
		let r = JSON.stringify([e, n]), i = ee.get(r);
		if (i) return i;
		o.pendingActions[r] = !0;
		let a = (async () => {
			try {
				let r = await t.action(e, n);
				return o.lastAction = r, K(r), ce(r), /\/delete(?:-bulk)?$/.test(e) && o.detail.id !== null && (Array.isArray(r.deleted) ? r.deleted : r.deleted === !0 ? [e.split("/").at(-2)] : []).some((e) => String(e) === String(o.detail.id)) && me(), F(), o.detail.id !== null && X(), r;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: wt(e)
				}, u(o.receipt.message), e;
			} finally {
				ee.delete(r), delete o.pendingActions[r];
			}
		})();
		return ee.set(r, a), a;
	}
	function ue(e) {
		if (M) return M;
		if (l.value) {
			let e = l.value;
			return o.receipt = {
				tone: "warning",
				message: e
			}, u(e), Promise.reject(Error(e));
		}
		return !Number.isSafeInteger(e.count) || e.count < 1 || !Number.isSafeInteger(e.workers) || e.workers < 1 ? Promise.reject(/* @__PURE__ */ Error("注册数量与并发线程数必须为有效的正整数")) : (o.creating = !0, M = (async () => {
			try {
				let n = await t.create({ ...e });
				return o.lastCreate = n, K(n), ce(n, `已提交 ${n.submitted || 0} 个任务`), F(), n;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: wt(e)
				}, u(o.receipt.message), e;
			} finally {
				o.creating = !1, M = void 0;
			}
		})(), M);
	}
	function J(e) {
		let t = o.batch?.items || [];
		return e === "stopBatch" ? t.filter((e) => e.status === "running" || e.status === "stopping") : e === "cancelBatch" ? t.filter((e) => e.status === "pending") : t.filter((e) => St.includes(String(e.status)) && e.retryable);
	}
	let Y = S(() => ({
		stopBatch: !!o.batchId && J("stopBatch").length > 0,
		cancelBatch: !!o.batchId && J("cancelBatch").length > 0,
		retryBatch: J("retryBatch").length > 0
	}));
	async function de(t, n, r = [], i = !1) {
		let a = t === "stopBatch" || t === "cancelBatch" || t === "retryBatch" ? J(t) : [], s = t === "retryBulk" || t === "deleteBulk" ? r.map((e) => q(e)) : a.map((e) => q(e.id));
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
		}, l = t === "retry" && n?.retry_action === "codex" ? "仅补跑 Codex 授权" : t === "retry" && n?.retry_action === "twofa" ? "重新登录检查并补齐 Authenticator 2FA" : t === "retry" && n?.retry_action === "registration_resume" ? "使用已保存账号密码继续邮箱验证" : "有原邮箱则复用，没有原邮箱则重新领取；已创建账号的任务按缺失步骤补跑，不能重试的由后端校验", d = t === "retry" || t === "retryBulk" || t === "retryBatch" ? `\n${l}。原任务记录和日志会保留。` : t === "stop" || t === "stopBatch" ? "\n任务会在当前步骤检查点退出。" : t === "cancelAll" || t === "cancelBatch" ? "\n运行中的任务不受影响。" : "", f = encodeURIComponent(o.batchId), p = n ? Et(n.id) : "";
		return await (e.confirm ? e.confirm(`确定${c[t]}吗？${d}`) : window.confirm(`确定${c[t]}吗？${d}`)) ? le(...{
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
	function fe() {
		g++, T?.abort(), E?.abort(), T = E = void 0, window.clearTimeout(b), b = void 0, o.detail.loading = !1, o.detail.comparing = !1;
	}
	async function X() {
		if (!te()) return;
		T?.abort(), window.clearTimeout(b);
		let e = o.detail.id, n = ++g, r = new AbortController();
		T = r, o.detail.loading = !0, o.detail.error = "";
		let i = () => N(n, e);
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
			i() && !G(e) && (o.detail.error = wt(e));
		} finally {
			i() && (o.detail.loading = !1, xt.includes(String(o.detail.job?.status || "")) || (b = window.setTimeout(() => void X(), 2e3)));
		}
	}
	function pe(t, n) {
		let r = q(t), i = [...o.jobs, ...o.batch?.items || []].find((e) => String(e.id) === String(r));
		i?.operation_task_id && e.openTask ? e.openTask(i.operation_task_id, i.operation_run_id || null, n || null) : (fe(), o.detail = {
			...Dt(),
			id: r
		}, X());
	}
	function me() {
		fe(), o.detail = Dt();
	}
	async function he(e) {
		let n = q(e);
		if (!N(g, n)) return null;
		E?.abort();
		let r = new AbortController();
		E = r;
		let i = () => te() && E === r && !r.signal.aborted && String(o.detail.id) === String(n);
		o.detail.comparing = !0, o.detail.compareError = "";
		try {
			let e = await t.compare(n, r.signal);
			return i() ? (o.detail.comparison = e, e) : null;
		} catch (e) {
			if (i() && !G(e)) throw o.detail.compareError = wt(e), e;
			return null;
		} finally {
			i() && (o.detail.comparing = !1, E = void 0);
		}
	}
	function ge() {
		r.value = !document.hidden, r.value ? (U(), o.detail.id !== null && X()) : (P(), re(), fe());
	}
	function Z() {
		i = !0, P(), re(), fe(), document.removeEventListener("visibilitychange", ge);
	}
	return document.addEventListener("visibilitychange", ge), k() && y(Z), {
		state: o,
		active: a,
		creating: c,
		registrationUnavailable: l,
		ensureMeta: H,
		load: F,
		loadSummary: V,
		renderEmailSupply: B,
		applySummary: z,
		setVisible: W,
		setView: se,
		setBatch: I,
		updateQuery: L,
		setPage: R,
		setSize: oe,
		shouldPollJobs: ie,
		create: ue,
		action: le,
		executeAction: de,
		compare: he,
		openLog: pe,
		refreshDetail: X,
		closeDetail: me,
		notify: u,
		terminalStatuses: xt,
		activeStatuses: bt,
		batchActions: Y,
		dispose: Z
	};
}
// src/features/registration/RegistrationPage.vue?vue&type=script&setup=true&lang.ts
var kt = ["data-view"], At = { class: "registration-launch" }, jt = {
	class: "registration-summary",
	"aria-label": "注册与本地邮箱概览"
}, Mt = {
	class: "registration-launch-panel",
	"aria-labelledby": "registration-launch-title"
}, Nt = { class: "registration-launcher" }, Pt = ["disabled", "aria-describedby"], Ft = ["value"], It = { class: "registration-debug" }, Lt = ["disabled", "title"], Rt = { class: "registration-hint" }, zt = { id: "registrationEmailSupplyHint" }, Bt = { class: "registration-tasks" }, Vt = { class: "registration-toolbar" }, Ht = ["disabled"], Ut = ["disabled"], Wt = {
	class: "registration-count-row",
	"data-registration-count-row": ""
}, Gt = { class: "registration-count-main" }, Kt = { class: "registration-count" }, qt = { class: "registration-count-actions" }, Jt = { class: "registration-mobile-filter" }, Yt = {
	key: 0,
	class: "registration-list-error",
	role: "alert"
}, Xt = { class: "registration-table-wrap" }, Zt = { key: 2 }, Qt = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], $t = { key: 0 }, en = { key: 1 }, tn = [
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], nn = { key: 0 }, rn = { class: "registration-row-actions" }, an = ["onClick"], on = ["onUpdate:modelValue"], sn = ["onClick"], cn = ["onClick"], ln = ["onClick"], un = ["disabled", "onClick"], dn = { id: "registration-log-title" }, fn = { key: 0 }, pn = {
	key: 1,
	role: "alert"
}, mn = { key: 2 }, hn = ["disabled"], gn = ["href"], _n = { key: 0 }, vn = {
	key: 1,
	role: "alert"
}, yn = { key: 3 }, bn = ["href"], xn = /* @__PURE__ */ e({
	__name: "RegistrationPage",
	props: { deps: {} },
	setup(e, { expose: s }) {
		let y = e, C = Ot(y.deps), { state: D } = C, k = te({
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
		function M() {
			k.resetColumns(), y.deps.notify?.("已恢复默认列宽");
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
		], P = m();
		se(P, () => D.detail.id !== null, () => C.active.value);
		let ie = m(1), ae = m(3), F = m(""), I = m(!1), L = m(""), R = m(""), oe = m(""), z = m(""), B = m(""), V = m(""), H = m(""), U = m(""), W = m(1), G = m(20), K = m(/* @__PURE__ */ new Set()), q = m({}), le = S(() => D.view === "launch"), ue = S(() => D.view === "tasks"), J = S(() => D.jobs), Y = m(null), de = S(() => ({
			id: R.value,
			email: oe.value,
			email_source: z.value,
			status: L.value,
			proxy: B.value,
			error: V.value,
			date_from: H.value,
			date_to: U.value
		})), fe = {
			id: "ID",
			email: "邮箱",
			email_source: "邮箱来源",
			status: "状态",
			proxy: "代理",
			error: "错误",
			date_from: "开始日期",
			date_to: "截止日期"
		}, X = S(() => Object.entries(de.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${fe[e]}：${e === "status" ? Oe(t) : e === "email_source" ? De(t) : t}`,
			removeLabel: `清除${fe[e]}筛选`
		})));
		function pe(e, t) {
			let n = {
				id: R,
				email: oe,
				email_source: z,
				status: L,
				proxy: B,
				error: V,
				date_from: H,
				date_to: U
			};
			n[e].value = t, Y.value = null, Fe();
		}
		let me = (e) => e.error_info ? re(e.error_info) : e.error_message ? "执行异常" : "—", he = S(() => D.statusCounts.active ?? [
			"pending",
			"running",
			"stopping"
		].reduce((e, t) => e + Number((Object.keys(D.statusCounts).length ? D.statusCounts : D.batch?.status_counts || {})[t] || 0), 0)), Z = S(() => !!D.meta?.manual_mode), _e = m(!1), ve = S(() => {
			let e = new Map((D.meta?.sources || []).map((e) => [String(e.value), {
				value: String(e.value),
				label: e.label || String(e.value)
			}])), t = D.facets.email_source;
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
		}), ye = S(() => Z.value ? [{
			value: "manual",
			label: "手动配置邮箱"
		}] : D.meta?.sources?.filter((e) => e.enabled === !0) || []), be = S(() => C.registrationUnavailable.value || (D.meta && !ye.value.length ? "没有可用的邮箱来源。请先导入本地邮箱，再重新选择。" : "")), xe = S(() => be.value || (D.meta ? Z.value ? "使用手动配置的邮箱来源。" : F.value ? "" : "请选择本批使用的邮箱来源。" : "正在读取邮箱来源…")), Se = S(() => D.summary?.email_supply || {}), Ce = (e) => {
			let t = Se.value[e];
			return Number.isInteger(t) && Number(t) >= 0 ? t : Se.value.status === "error" ? "读取失败" : "未知";
		}, we = S(() => `仅统计本地库存；用完后请手动导入；邮箱由 Email Butler 等邮箱服务准备${Se.value.reason ? `；${Se.value.reason}` : ""}`), Te = S(() => [
			{
				label: "已注册",
				value: D.summary?.accounts ?? "—"
			},
			{
				label: "本地邮箱总数",
				value: Ce("total")
			},
			{
				label: "本地可用",
				value: Ce("available")
			},
			{
				label: "本地已用",
				value: Ce("used")
			},
			{
				label: "本地失败",
				value: Ce("failed")
			}
		]), Ee = (e) => D.meta?.registration_drivers?.find((t) => String(t.value) === String(e))?.label || {
			protocol: "本地优化 Protocol（历史）",
			protocol_oss: "开源 Protocol（历史）",
			protocol_oss_2: "开源protocol-2",
			roxy: "本地 Roxy",
			roxy_oss: "开源 Roxy（历史）"
		}[String(e || "")] || String(e || "未知"), De = (e) => ve.value.find((t) => String(t.value) === String(e))?.label || String(e || "-"), Oe = (e) => ({
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
		})[String(e)] || String(e || "等待中"), ke = async (e) => y.deps.confirm ? await y.deps.confirm(e) : window.confirm(e);
		function Ae(e) {
			e || (Y.value = null), C.setVisible(e);
		}
		function je(e) {
			Y.value = null, C.setView(e);
		}
		function Me(e) {
			let t = P.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && C.closeDetail();
		}
		async function Ne() {
			if (D.creating || _e.value) return;
			if (be.value) {
				D.receipt = {
					tone: "warning",
					message: be.value
				};
				return;
			}
			let e = Number(ie.value), t = Number(ae.value);
			if (!Number.isSafeInteger(e) || e < 1) {
				D.receipt = {
					tone: "warning",
					message: "注册数量必须为有效的正整数"
				};
				return;
			}
			if (!Number.isSafeInteger(t) || t < 1) {
				D.receipt = {
					tone: "warning",
					message: "并发线程数必须为有效的正整数"
				};
				return;
			}
			if (!ye.value.some((e) => e.value === F.value)) {
				D.receipt = {
					tone: "warning",
					message: "请选择本次注册使用的邮箱来源"
				};
				return;
			}
			let n = {
				count: e,
				workers: t,
				email_source: F.value,
				debug_enabled: I.value
			};
			_e.value = !0;
			try {
				if (he.value > 0 && !await ke(`当前任务表里已有 ${he.value} 个任务在跑或排队，这次会再加 ${e} 个，确定继续？`)) return;
				let t = await C.create(n);
				Number.isSafeInteger(t?.workers) && t.workers > 0 && (ae.value = t.workers);
			} catch {} finally {
				_e.value = !1;
			}
		}
		async function Q(e, t) {
			let n = Array.from(K.value);
			try {
				await C.executeAction(e, t, n, I.value), (e === "deleteBulk" || e === "retryBulk") && (K.value = /* @__PURE__ */ new Set());
			} catch {}
		}
		function Pe() {
			L.value = R.value = oe.value = z.value = B.value = V.value = H.value = U.value = "", W.value = 1, C.load(Be());
		}
		function Fe() {
			W.value = 1, C.load(Be());
		}
		function Ie(e) {
			let t = e.target.checked;
			J.value.filter((e) => !["running", "stopping"].includes(String(e.status))).forEach((e) => t ? K.value.add(String(e.id)) : K.value.delete(String(e.id))), K.value = new Set(K.value);
		}
		function Le(e, t) {
			let n = new Set(K.value);
			t.target.checked ? n.add(String(e)) : n.delete(String(e)), K.value = n;
		}
		function Re(e) {
			return [
				e.proxy_provider,
				e.proxy_endpoint && e.proxy_endpoint !== "-" ? e.proxy_endpoint : "",
				e.proxy_region && e.proxy_region !== "-" ? e.proxy_region : ""
			].filter(Boolean).join(" · ") || "-";
		}
		function ze(e) {
			W.value = 1, C.setBatch(e);
		}
		function Be() {
			return {
				status: L.value,
				id: R.value,
				email: oe.value,
				email_source: z.value,
				proxy: B.value,
				error: V.value,
				date_from: H.value,
				date_to: U.value,
				page: W.value,
				page_size: G.value
			};
		}
		function Ve(e) {
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
			}).catch(() => {}) : D.receipt = {
				tone: "warning",
				message: "请先填写邮箱验证码"
			};
		}
		async function He() {
			if (D.detail.id != null) try {
				await C.compare(D.detail.id);
			} catch {}
		}
		return s({
			create: C.create,
			runAction: C.executeAction,
			setBatch: C.setBatch,
			loadSources: () => C.ensureMeta(!0),
			load: C.load,
			ensureMeta: C.ensureMeta,
			setVisible: Ae,
			setView: je,
			loadSummary: C.loadSummary,
			renderEmailSupply: C.renderEmailSupply,
			applySummary: C.applySummary,
			action: C.action,
			openLog: C.openLog,
			closeDetail: C.closeDetail
		}), r(() => ({ ...D.query }), (e) => {
			W.value = e.page, G.value = e.page_size, R.value = e.id, oe.value = e.email, z.value = e.email_source, L.value = e.status, B.value = e.proxy, V.value = e.error, H.value = e.date_from, U.value = e.date_to;
		}, { immediate: !0 }), r([Z, ye], () => {
			Z.value ? F.value = "manual" : ye.value.some((e) => e.value === F.value) || (F.value = "");
		}, { immediate: !0 }), o(() => {
			C.ensureMeta();
		}), (e, r) => (t(), O("div", {
			class: "registration-vue-page",
			"data-view": E(D).view
		}, [
			i(_("section", At, [
				_("dl", jt, [(t(!0), O(f, null, a(Te.value, (e) => (t(), O("div", { key: e.label }, [_("dt", null, h(e.label), 1), _("dd", null, h(typeof e.value == "number" ? e.value.toLocaleString("zh-CN") : e.value), 1)]))), 128))]),
				_("section", Mt, [r[23] ||= _("h2", { id: "registration-launch-title" }, "新建注册批次", -1), _("form", {
					novalidate: "",
					onSubmit: b(Ne, ["prevent"])
				}, [_("div", Nt, [
					_("label", null, [r[19] ||= A("邮箱来源 ", -1), i(_("select", {
						"onUpdate:modelValue": r[0] ||= (e) => F.value = e,
						disabled: !E(D).meta || Z.value || !ye.value.length,
						"aria-describedby": xe.value ? "registration-launch-hint registrationEmailSupplyHint" : "registrationEmailSupplyHint"
					}, [r[18] ||= _("option", { value: "" }, "请选择本次邮箱来源", -1), (t(!0), O(f, null, a(ye.value, (e) => (t(), O("option", {
						key: String(e.value),
						value: String(e.value)
					}, h(e.label || e.value), 9, Ft))), 128))], 8, Pt), [[u, F.value]])]),
					_("label", null, [r[20] ||= A("注册数量", -1), i(_("input", {
						"onUpdate:modelValue": r[1] ||= (e) => ie.value = e,
						min: "1",
						type: "number",
						inputmode: "numeric"
					}, null, 512), [[
						w,
						ie.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", null, [r[21] ||= A("并发线程", -1), i(_("input", {
						"onUpdate:modelValue": r[2] ||= (e) => ae.value = e,
						min: "1",
						step: "1",
						type: "number",
						inputmode: "numeric"
					}, null, 512), [[
						w,
						ae.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", It, [i(_("input", {
						"onUpdate:modelValue": r[3] ||= (e) => I.value = e,
						type: "checkbox"
					}, null, 512), [[v, I.value]]), r[22] ||= A(" 调试模式", -1)]),
					_("button", {
						type: "submit",
						class: "registration-start",
						disabled: E(D).creating || _e.value || !F.value || !!be.value,
						title: be.value || void 0
					}, h(E(D).creating ? "提交中…" : "开始注册"), 9, Lt)
				]), _("p", Rt, [xe.value ? (t(), O("span", {
					key: 0,
					id: "registration-launch-hint",
					class: x({ "registration-warning": be.value }),
					role: "status"
				}, h(xe.value), 3)) : l("", !0), _("span", zt, h(we.value), 1)])], 32)]),
				le.value ? (t(), g(_t, {
					key: 0,
					batch: E(D).batch,
					batches: E(D).batches,
					"batch-id": E(D).batchId,
					active: E(C).active.value,
					loading: E(D).loading,
					error: E(D).error,
					actions: E(C).batchActions.value,
					mutating: Object.keys(E(D).pendingActions).length > 0,
					"status-label": Oe,
					"source-label": De,
					"driver-label": Ee,
					onSelect: ze,
					onRefresh: r[4] ||= (e) => E(C).load(),
					onBatchAction: r[5] ||= (e) => Q(e),
					onRetry: r[6] ||= (e) => Q("retry", e),
					onLog: E(C).openLog
				}, null, 8, [
					"batch",
					"batches",
					"batch-id",
					"active",
					"loading",
					"error",
					"actions",
					"mutating",
					"onLog"
				])) : l("", !0)
			], 512), [[T, le.value]]),
			i(_("section", Bt, [
				_("div", Vt, [
					_("button", {
						type: "button",
						onClick: r[7] ||= (e) => Q("retryBulk"),
						disabled: !K.value.size
					}, "重试", 8, Ht),
					_("button", {
						type: "button",
						onClick: r[8] ||= (e) => Q("deleteBulk"),
						disabled: !K.value.size
					}, "删除", 8, Ut),
					_("button", {
						type: "button",
						onClick: r[9] ||= (e) => Q("cancelAll")
					}, "取消排队"),
					_("button", {
						type: "button",
						onClick: Fe
					}, "刷新")
				]),
				_("div", Wt, [_("div", Gt, [_("span", Kt, "共 " + h(E(D).total.toLocaleString()) + " 条任务", 1), c(ee, {
					items: X.value,
					onRemove: r[10] ||= (e) => pe(e, "")
				}, null, 8, ["items"])]), _("div", qt, [
					_("button", {
						type: "button",
						"aria-label": "恢复注册任务列宽",
						onClick: M
					}, "恢复列宽"),
					_("span", Jt, [c(ge, {
						values: de.value,
						sources: ve.value,
						open: Y.value === "all",
						"onUpdate:open": r[11] ||= (e) => Y.value = e ? "all" : null,
						onChange: pe
					}, null, 8, [
						"values",
						"sources",
						"open"
					])]),
					X.value.length ? (t(), O("button", {
						key: 0,
						type: "button",
						onClick: Pe
					}, "清筛")) : l("", !0)
				])]),
				E(D).error ? (t(), O("div", Yt, [A(h(E(D).error) + " ", 1), _("button", {
					type: "button",
					onClick: Fe
				}, "重试")])) : l("", !0),
				_("div", Xt, [_("table", {
					class: "jobs-table-v2",
					style: p({ width: `${E(k).total.value}px` })
				}, [
					_("colgroup", null, [(t(!0), O(f, null, a(E(k).widths.value, (e, n) => (t(), O("col", {
						key: n,
						style: p({ width: `${e}px` })
					}, null, 4))), 128))]),
					_("thead", null, [_("tr", null, [(t(), O(f, null, a(N, (e, n) => _("th", { key: e.label }, [n === 0 ? (t(), O("input", {
						key: 0,
						type: "checkbox",
						"aria-label": "选择本页可操作任务",
						onChange: Ie
					}, null, 32)) : e.filter ? (t(), g(ge, {
						key: 1,
						column: e.filter,
						values: de.value,
						sources: ve.value,
						open: Y.value === e.filter,
						"onUpdate:open": (t) => Y.value = t ? e.filter : null,
						onChange: pe
					}, null, 8, [
						"column",
						"values",
						"sources",
						"open",
						"onUpdate:open"
					])) : (t(), O("span", Zt, h(e.label), 1)), n < N.length - 1 ? (t(), O("button", {
						key: 3,
						type: "button",
						class: "registration-column-resize",
						"aria-label": `调整${e.label}列宽，方向键调整`,
						onPointerdown: b((e) => E(k).resize(n, e), ["prevent"]),
						onKeydown: [d(b((e) => E(k).resizeWithKeyboard(n, -10), ["prevent"]), ["left"]), d(b((e) => E(k).resizeWithKeyboard(n, 10), ["prevent"]), ["right"])]
					}, null, 40, Qt)) : l("", !0)])), 64))])]),
					_("tbody", null, [E(D).loading ? (t(), O("tr", $t, [...r[24] ||= [_("td", { colspan: "11" }, "正在加载任务…", -1)]])) : J.value.length ? l("", !0) : (t(), O("tr", en, [...r[25] ||= [_("td", { colspan: "11" }, "暂无匹配任务", -1)]])), (t(!0), O(f, null, a(J.value, (e) => (t(), O("tr", { key: String(e.id) }, [
						_("td", null, [_("input", {
							type: "checkbox",
							"aria-label": `选择任务 ${e.id}`,
							checked: K.value.has(String(e.id)),
							disabled: ["running", "stopping"].includes(String(e.status)),
							onChange: (t) => Le(e.id, t)
						}, null, 40, tn)]),
						_("td", null, [c(j, {
							text: `#${e.id}`,
							secondary: e.parent_job_id ? `↳ #${e.parent_job_id}` : void 0
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(j, { text: String(e.email || "-") }, null, 8, ["text"])]),
						_("td", null, [c(j, { text: De(e.email_source) }, null, 8, ["text"])]),
						_("td", null, [c(j, { text: Ee(e.registration_driver) }, null, 8, ["text"])]),
						_("td", null, [c(j, {
							text: Re(e),
							secondary: String(e.proxy_status || "")
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(j, { text: Oe(e.debug_state === "paused" ? "debug_paused" : e.display_status || e.status) }, null, 8, ["text"])]),
						_("td", null, [c(j, { text: String(e.started_at || "-") }, null, 8, ["text"])]),
						_("td", null, [c(j, { text: String(e.completed_at || "-") }, null, 8, ["text"])]),
						_("td", null, [e.error_message || e.error_info ? (t(), g(ne, {
							key: 0,
							"data-registration-result": "",
							label: me(e),
							title: String(e.error_message || me(e)),
							tone: "danger"
						}, {
							details: n(() => [_("p", null, h(e.error_message || me(e)), 1), e.error_info ? (t(), O("p", nn, h(e.error_info), 1)) : l("", !0)]),
							_: 2
						}, 1032, ["label", "title"])) : (t(), g(j, {
							key: 1,
							text: "—"
						}))]),
						_("td", rn, [
							_("button", {
								type: "button",
								onClick: (t) => E(C).openLog(e.id)
							}, "日志", 8, an),
							e.manual_otp_required && e.status === "running" ? (t(), O(f, { key: 0 }, [i(_("input", {
								"onUpdate:modelValue": (t) => q.value[String(e.id)] = t,
								placeholder: "邮箱验证码"
							}, null, 8, on), [[w, q.value[String(e.id)]]]), _("button", {
								type: "button",
								onClick: (t) => Ve(e)
							}, "提交验证码", 8, sn)], 64)) : l("", !0),
							[
								"pending",
								"running",
								"stopping"
							].includes(String(e.status)) ? (t(), O("button", {
								key: 1,
								type: "button",
								onClick: (t) => Q("stop", e)
							}, "停止", 8, cn)) : l("", !0),
							e.retryable ? (t(), O("button", {
								key: 2,
								type: "button",
								onClick: (t) => Q("retry", e)
							}, "重试", 8, ln)) : l("", !0),
							_("button", {
								type: "button",
								disabled: ["running", "stopping"].includes(String(e.status)),
								onClick: (t) => Q("delete", e)
							}, "删除", 8, un)
						])
					]))), 128))])
				], 4)]),
				c(ce, {
					label: "注册任务分页",
					page: W.value,
					size: G.value,
					total: E(D).total,
					busy: E(D).loading,
					"onUpdate:page": r[12] ||= (e) => {
						W.value = e, E(C).load(Be());
					},
					"onUpdate:size": r[13] ||= (e) => {
						G.value = e, W.value = 1, E(C).load(Be());
					}
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			], 512), [[T, ue.value]]),
			E(D).receipt ? (t(), O("div", {
				key: 0,
				class: x(["registration-receipt", `is-${E(D).receipt.tone}`]),
				role: "status"
			}, h(E(D).receipt.message), 3)) : l("", !0),
			_("dialog", {
				ref_key: "logDialog",
				ref: P,
				class: "registration-dialog",
				"aria-labelledby": "registration-log-title",
				onCancel: r[16] ||= b((...e) => E(C).closeDetail && E(C).closeDetail(...e), ["prevent"]),
				onClose: r[17] ||= (...e) => E(C).closeDetail && E(C).closeDetail(...e),
				onClick: Me
			}, [
				_("header", null, [_("h2", dn, "任务 #" + h(E(D).detail.id) + " 日志", 1), _("button", {
					type: "button",
					onClick: r[14] ||= (...e) => E(C).closeDetail && E(C).closeDetail(...e)
				}, "关闭")]),
				E(D).detail.loading ? (t(), O("p", fn, "加载中…")) : l("", !0),
				E(D).detail.error ? (t(), O("p", pn, h(E(D).detail.error), 1)) : l("", !0),
				_("pre", null, h(E(D).detail.log || "（暂无日志）"), 1),
				E(D).detail.debug?.enabled ? (t(), O("div", mn, [
					r[26] ||= _("strong", null, "网络调试", -1),
					_("button", {
						type: "button",
						disabled: E(D).detail.comparing,
						onClick: He
					}, "与同批成功任务对比", 8, hn),
					_("a", {
						href: `/api/jobs/${E(D).detail.id}/debug/har`,
						download: ""
					}, "下载脱敏 HAR", 8, gn),
					_("button", {
						type: "button",
						onClick: r[15] ||= (e) => E(C).action(`/api/jobs/${E(D).detail.id}/debug/release`, { action: "finish" })
					}, "结束调试并收口"),
					E(D).detail.comparison ? (t(), O("pre", _n, h(E(D).detail.comparison), 1)) : l("", !0),
					E(D).detail.compareError ? (t(), O("p", vn, h(E(D).detail.compareError), 1)) : l("", !0)
				])) : l("", !0),
				E(D).detail.diagnostics?.captured ? (t(), O("div", yn, [
					r[28] ||= _("strong", null, "失败诊断", -1),
					E(D).detail.diagnostics.screenshot_url ? (t(), O("a", {
						key: 0,
						href: String(E(D).detail.diagnostics.screenshot_url),
						target: "_blank",
						rel: "noopener"
					}, "打开失败截图", 8, bn)) : l("", !0),
					_("details", null, [r[27] ||= _("summary", null, "完整诊断证据", -1), _("pre", null, h(E(D).detail.diagnostics), 1)])
				])) : l("", !0)
			], 544)
		], 8, kt));
	}
});
// src/registration.ts
function Sn(e, t = {}) {
	let n = C(xn, { deps: {
		...t,
		api: t.api || yt()
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
export { Sn as mountRegistration };
