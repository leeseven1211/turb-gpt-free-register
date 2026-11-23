import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, S as c, _ as l, a as u, c as d, d as f, dt as p, et as m, ft as h, g, h as _, i as v, j as y, l as b, lt as x, m as S, n as C, o as w, s as T, st as E, t as D, v as O, w as ee, x as k } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { i as A, n as j, r as M, t as te } from "./ListFilterSummary-C8h8bMwn.js";
import { n as ne, t as re } from "./ColumnResizer-CPJ9UuoZ.js";
import { t as ie } from "./ListResult-CPVXnLlZ.js";
import { n as N, r as P } from "./client-B5R_MNgP.js";
import { t as ae } from "./errorLabels-BWpfwuWJ.js";
import { n as F, t as I } from "./time-DOD6oyhP.js";
import { O as oe, _ as se, a as L, b as R, g as z, h as B, i as V, n as H, p as U, r as W, t as G, v as K, x as q, y as J } from "./StepEvidence-Dn4u9gqa.js";
import { t as ce } from "./useNativeDialog-DWisXYg9.js";
import { t as le } from "./ListPagination-DURVj-Kj.js";
import { a as ue, r as Y } from "./taskIds-BlchWwUp.js";
// src/features/registration/RegistrationFilters.vue?vue&type=script&setup=true&lang.ts
var X = { class: "registration-filter-fields" }, de = { key: 0 }, fe = ["value"], Z = ["value", "aria-label"], pe = ["value"], me = ["value"], he = ["value"], ge = [
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
			default: n(() => [_("div", X, [
				e.column ? l("", !0) : (t(), O("label", de, [s[8] ||= k("筛选列", -1), i(_("select", {
					"onUpdate:modelValue": s[0] ||= (e) => p.value = e,
					"aria-label": "选择注册任务筛选列"
				}, [(t(), O(f, null, a(o, (e, t) => _("option", {
					key: t,
					value: t
				}, h(e), 9, fe)), 64))], 512), [[u, p.value]])])),
				_("label", null, [k(h(o[v.value]) + " ", 1), v.value === "email_source" ? (t(), O("select", {
					key: 0,
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[1] ||= (e) => C(e.target.value)
				}, [s[9] ||= _("option", { value: "" }, "全部邮箱来源", -1), (t(!0), O(f, null, a(e.sources, (e) => (t(), O("option", {
					key: e.value,
					value: e.value
				}, h(e.label || e.value), 9, pe))), 128))], 40, Z)) : v.value === "status" ? (t(), O("select", {
					key: 1,
					value: y.value,
					"aria-label": "筛选状态值",
					onChange: s[2] ||= (e) => C(e.target.value)
				}, [s[10] ||= _("option", { value: "" }, "全部状态", -1), (t(!0), O(f, null, a(b.value, (e) => (t(), O("option", {
					key: e,
					value: e
				}, h(x(e)), 9, he))), 128))], 40, me)) : (t(), O("input", {
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
}, xe = { key: 0 }, Se = {
	key: 1,
	class: "registration-steps",
	"aria-label": "注册执行阶段，排列不代表固定顺序"
}, Ce = [
	"title",
	"aria-pressed",
	"onClick"
], we = {
	key: 0,
	class: "registration-step-mark",
	"aria-hidden": "true"
}, Te = {
	key: 1,
	class: "registration-step-mark",
	"aria-hidden": "true"
}, Ee = { "data-registration-step-duration": "" }, De = { key: 0 }, Oe = ["aria-label", "onClick"], ke = {
	key: 2,
	class: "registration-stage-selected"
}, Ae = { "aria-live": "polite" }, je = { key: 0 }, Me = { key: 1 }, Ne = { class: "registration-batch-actions" }, Pe = ["aria-label"], Q = {
	key: 3,
	class: "registration-step-note"
}, Fe = { key: 4 }, Ie = { key: 0 }, Le = /* @__PURE__ */ e({
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
			return L(e.map((e, t) => ({
				...e,
				id: String(e.id || e.step_id || e.key || `step-${t + 1}`),
				label: e.label || e.name || e.id || e.step_id
			})));
		}), s = m(), u = m(), d = m(), p = S(() => {
			if (!r.inline) return;
			if (d.value) return o.value.find((e) => K(e) === d.value);
			if (!r.focusFailure) return;
			let e = String(U(r.job?.progress?.failure).step_id || "");
			return o.value.find((t) => K(t) === e) || o.value.find((e) => R(e) === "failed");
		});
		function v(e) {
			r.inline ? d.value = K(e) : i("log", K(e));
		}
		ce(u, () => !!s.value && r.active, () => r.active);
		let y = (e) => oe(se(e));
		function C(e) {
			let t = U(e.debug_pause);
			return t.state === "paused" ? `调试暂停 · 等待结束调试${t.paused_at ? ` · 暂停于 ${F(t.paused_at)}` : " · 暂停时间未记录"}${t.hold_until ? ` · 保留至 ${F(t.hold_until)}` : ""}` : "";
		}
		function w(e) {
			let t = e.attempts || [], n = e.children || [], i = (e) => e.raw_stage_label || n.find((t) => t.id === e.raw_stage)?.label || e.raw_stage || "阶段", a = [...new Set(t.map(i))];
			return [
				`${J(e)} · ${V(e)}`,
				C(e),
				e.reason || e.message || "",
				`开始：${F(e.started_at)}`,
				`结束：${F(e.completed_at)}`,
				`耗时：${y(e)}`,
				a.length ? `已记录阶段：${a.join("、")}` : "",
				n.length ? `子步骤（${n.length}）` : "",
				...n.map((e) => `${J(e)} · ${V(e)} · ${y(e)}${e.reason || e.message ? `\n${e.reason || e.message}` : ""}`),
				t.length ? `阶段事件（${t.length} 条）` : "",
				...t.map((e, t) => `${t + 1}. ${i(e)} · ${B(e.display_status || e.state)}${e.created_at ? ` · ${F(e.created_at)}` : e.event_time_known === !1 ? " · 发生时间未记录" : ""}${e.message ? `\n${e.message}` : ""}`),
				r.inline ? "点击步骤查看阶段摘要" : "点击步骤查看对应日志"
			].filter(Boolean).join("\n");
		}
		return (n, r) => (t(), O("div", ye, [
			o.value.length ? (t(), O("div", be, [e.inline ? (t(), O("h3", xe, "执行阶段")) : l("", !0), r[5] ||= _("p", { class: "registration-step-note" }, "按首次记录排列，不代表固定执行顺序", -1)])) : l("", !0),
			o.value.length ? (t(), O("ul", Se, [(t(!0), O(f, null, a(o.value, (n) => (t(), O("li", {
				key: E(K)(n),
				class: x([`is-${E(R)(n)}`, { "is-inspected": p.value === n }])
			}, [_("button", {
				type: "button",
				title: w(n),
				"aria-pressed": e.inline ? p.value === n : void 0,
				onClick: (e) => v(n)
			}, [
				_("strong", null, [E(R)(n) === "success" ? (t(), O("span", we, "✓")) : E(R)(n) === "failed" ? (t(), O("span", Te, "!")) : l("", !0), k(" " + h(E(J)(n)), 1)]),
				_("small", null, h(E(V)(n)), 1),
				_("small", Ee, "耗时 " + h(y(n)), 1),
				(t(!0), O(f, null, a(E(W)(n), (e) => (t(), O("small", { key: e }, h(e), 1))), 128)),
				C(n) ? (t(), O("small", De, h(C(n)), 1)) : l("", !0)
			], 8, Ce), e.inline ? l("", !0) : (t(), O("button", {
				key: 0,
				type: "button",
				"aria-label": `查看${E(J)(n)}的关系与证据`,
				onClick: (e) => s.value = n
			}, "详情", 8, Oe))], 2))), 128))])) : l("", !0),
			p.value ? (t(), O("div", ke, [_("div", Ae, [
				_("strong", null, h(E(J)(p.value)), 1),
				_("span", null, " · " + h(E(V)(p.value)), 1),
				p.value.reason || p.value.message ? (t(), O("p", je, h(p.value.reason || p.value.message), 1)) : e.focusFailure && E(K)(p.value) === E(U)(e.job.progress?.failure).step_id && E(U)(e.job.progress?.failure).message ? (t(), O("p", Me, h(E(U)(e.job.progress?.failure).message), 1)) : l("", !0)
			]), _("div", Ne, [_("button", {
				type: "button",
				"aria-label": `查看${E(J)(p.value)}的关系与证据`,
				onClick: r[0] ||= (e) => s.value = p.value
			}, "阶段详情", 8, Pe), _("button", {
				type: "button",
				onClick: r[1] ||= (e) => i("log", E(K)(p.value))
			}, "阶段日志")])])) : o.value.length ? l("", !0) : (t(), O("p", Q, "暂无阶段记录，可查看任务日志。")),
			o.value.length ? (t(), O("details", Fe, [r[6] ||= _("summary", null, "依赖与执行记录", -1), (t(!0), O(f, null, a(o.value, (e) => (t(), O("div", { key: E(K)(e) }, [_("strong", null, h(E(J)(e)), 1), c(H, {
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
				_("header", null, [_("h3", null, h(s.value ? E(J)(s.value) : "步骤详情"), 1), _("button", {
					type: "button",
					onClick: r[2] ||= (e) => s.value = void 0
				}, "关闭")]),
				s.value && C(s.value) ? (t(), O("p", Ie, h(C(s.value)), 1)) : l("", !0),
				s.value ? (t(), g(G, {
					key: 1,
					step: s.value,
					siblings: o.value
				}, null, 8, ["step", "siblings"])) : l("", !0)
			], 544)
		]));
	}
}), Re = ["aria-busy"], ze = { class: "registration-batch-header" }, Be = { class: "registration-batch-title" }, Ve = ["data-tone"], He = {
	key: 1,
	class: "registration-hint"
}, Ue = {
	key: 0,
	class: "registration-hint registration-batch-meta"
}, We = { key: 0 }, Ge = { key: 1 }, Ke = {
	key: 0,
	class: "registration-batch-actions"
}, qe = ["value"], Je = ["value"], Ye = ["disabled"], Xe = ["disabled"], Ze = ["disabled"], Qe = {
	key: 0,
	class: "registration-batch-notice",
	role: "alert"
}, $e = {
	key: 1,
	class: "registration-batch-notice"
}, et = {
	class: "registration-batch-meter",
	"aria-hidden": "true"
}, tt = ["data-tone"], nt = {
	class: "registration-batch-filters",
	role: "group",
	"aria-label": "按批次任务状态筛选"
}, rt = [
	"data-batch-filter",
	"aria-pressed",
	"onClick"
], it = ["data-tone"], at = ["data-tone"], ot = { class: "registration-batch-row" }, st = { class: "registration-batch-identity" }, ct = { class: "registration-batch-result" }, lt = ["data-tone"], ut = { key: 0 }, dt = {
	key: 0,
	class: "registration-batch-timing"
}, ft = { key: 0 }, pt = { class: "registration-batch-dates" }, mt = { key: 0 }, ht = ["datetime", "title"], gt = { key: 1 }, _t = ["datetime", "title"], vt = { class: "registration-batch-actions registration-batch-row-actions" }, yt = [
	"aria-label",
	"aria-expanded",
	"aria-controls",
	"onClick"
], bt = ["aria-label", "onClick"], xt = ["disabled", "onClick"], St = [
	"id",
	"hidden",
	"data-progress-state"
], Ct = {
	key: 0,
	class: "registration-step-note",
	role: "alert"
}, wt = ["onClick"], Tt = {
	key: 1,
	class: "registration-step-note",
	role: "status"
}, Et = { key: 0 }, Dt = { key: 1 }, Ot = {
	key: 0,
	class: "registration-batch-notice"
}, kt = {
	class: "registration-batch-footer registration-hint",
	"aria-live": "polite"
}, At = /* @__PURE__ */ e({
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
				key: "active",
				label: "运行 / 排队"
			},
			{
				key: "other",
				label: "其他"
			}
		], u = m("all"), d = m(null), g = m(!1), v = S(() => i.batch?.items || []), b = S(() => i.batch && !i.batches.some((e) => String(e.batch_id) === String(i.batch?.batch_id)) ? [i.batch, ...i.batches] : i.batches), x = (e) => e.status || e.display_status || "";
		function C(e) {
			let t = x(e);
			return t === "success" || t === "failed" ? t : [
				"running",
				"pending",
				"stopping"
			].includes(t) ? "active" : "other";
		}
		let w = S(() => {
			let e = {
				all: v.value.length,
				success: 0,
				failed: 0,
				active: 0,
				other: 0
			};
			for (let t of v.value) e[C(t)]++;
			return e;
		}), T = S(() => s.filter((e) => e.key !== "other" || w.value.other || u.value === "other")), D = S(() => u.value === "all" ? v.value : v.value.filter((e) => C(e) === u.value)), ee = S(() => D.value.find((e) => String(e.id) === d.value)), A = m(), j = m(""), M, te = S(() => {
			let e = w.value;
			return e.all ? e.active ? {
				label: v.value.some((e) => x(e) !== "pending" && C(e) === "active") ? "运行中" : "排队中",
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
		}), ne = (e, t, n) => {
			let r = (t ? Date.parse(q(t)) : n ?? NaN) - Date.parse(q(e));
			return Number.isFinite(r) && r >= 0 ? oe(r) : "";
		}, re = S(() => ne(i.batch?.started_at, i.batch?.completed_at)), ie = (e) => e.toLocaleString("zh-CN"), P = (e) => U(U(e.progress).failure), se = S(() => {
			let e = Date.now();
			return D.value.map((t) => {
				let n = C(t), r = n === "active" && x(t) !== "pending";
				return {
					job: t,
					tone: n,
					result: R(t, n),
					identity: [
						`#${t.id}`,
						t.email_source && i.sourceLabel(t.email_source),
						t.registration_driver && i.driverLabel(t.registration_driver),
						typeof t.retry_count == "number" && `人工重试 ${t.retry_count} 次`
					].filter(Boolean).join(" · "),
					elapsed: ne(t.started_at, t.completed_at, r ? e : void 0),
					started: L(t.started_at),
					completed: L(t.completed_at)
				};
			});
		});
		function L(e) {
			if (!e || !Number.isFinite(Date.parse(e))) return null;
			let { text: t, secondary: n } = I(e);
			return {
				label: n ? `${t.slice(5)} ${n}` : t,
				full: n ? `${t} ${n}` : t
			};
		}
		function R(e, t) {
			if (t === "failed" || x(e) === "partial_success") {
				let t = e.error_info ? ae(U(e.error_info)) : "", n = q(P(e).label);
				return t && t !== "执行异常" ? t : n && Array.from(n).length <= 10 ? n : t || "执行异常";
			}
			return t === "active" ? q(U(U(e.progress).current).label) : "";
		}
		function B(e) {
			return e.debug_state === "paused" ? "调试暂停" : i.statusLabel(e.display_status || x(e));
		}
		function V(e) {
			let t = e.status_counts || {}, n = Number(t.running || 0) + Number(t.stopping || 0), r = Number(t.pending || 0);
			return `${e.created_at ? F(e.created_at).replace(/:\d{2}$/, "") : String(e.batch_id)} · ${n || r ? `运行 ${n} / 等待 ${r}` : `成功 ${t.success || 0} / 失败 ${t.failed || 0}`}`;
		}
		function H(e) {
			u.value = e, d.value = null, g.value = !1, e === "failed" && D.value.length === 1 && (d.value = String(D.value[0].id), g.value = !0);
		}
		function W(e) {
			let t = String(e.id);
			d.value = d.value === t ? null : t, g.value = d.value !== null && C(e) === "failed";
		}
		function G() {
			M?.abort(), M = void 0, A.value = void 0, j.value = "";
		}
		let K = (e) => String(e?.operation_run_id ?? "");
		async function J(e) {
			if (M || !i.active) return;
			let t = new AbortController();
			M = t, j.value = "";
			try {
				let n = await i.readProgress(e.id, t.signal);
				if (t.signal.aborted) return;
				if (!n.ok || !n.job || String(n.job.id) !== String(e.id) || !Array.isArray(U(n.job.progress).main_steps)) throw Error("阶段详情读取失败，请重试");
				if (K(e) && K(e) !== K(n.job)) throw Error("当前执行已更新，请刷新批次后重试");
				A.value = n.job;
			} catch (e) {
				!t.signal.aborted && !N(e) && (j.value = e instanceof Error ? e.message : "阶段详情读取失败，请重试");
			} finally {
				M === t && (M = void 0);
			}
		}
		return r(() => i.batchId, () => H("all")), r([
			() => i.active,
			() => i.batchId,
			ee,
			() => i.refreshGeneration
		], ([e, t, n, r], [, a, o, s]) => {
			if (!e || !n) {
				G(), e && i.batch && d.value !== null && (d.value = null, g.value = !1);
				return;
			}
			let c = t !== a || String(n.id) !== String(o?.id) || K(n) !== K(o) || x(n) !== (o && x(o)), l = r !== s;
			(c || l) && G(), (c || l || !A.value && !j.value || C(n) === "active") && J(n);
		}), y(G), (n, r) => (t(), O("section", {
			class: "registration-batch",
			"aria-labelledby": "registration-batch-title",
			"aria-busy": e.loading
		}, [
			_("header", ze, [_("div", null, [_("div", Be, [
				r[5] ||= _("h2", { id: "registration-batch-title" }, "任务批次进度", -1),
				e.batch ? (t(), O("span", {
					key: 0,
					class: "registration-state",
					"data-tone": te.value.tone
				}, h(te.value.label), 9, Ve)) : l("", !0),
				e.batch?.projection_delayed ? (t(), O("span", He, "进度同步中")) : l("", !0)
			]), e.batch ? (t(), O("p", Ue, [
				_("span", null, h(ie(e.batch.total ?? w.value.all)) + " 个任务", 1),
				e.batch.workers ? (t(), O("span", We, "并发 " + h(e.batch.workers), 1)) : l("", !0),
				re.value ? (t(), O("span", Ge, "批次耗时 " + h(re.value), 1)) : l("", !0)
			])) : l("", !0)]), b.value.length ? (t(), O("div", Ke, [
				_("select", {
					value: e.batchId,
					"aria-label": "选择任务批次",
					onChange: r[0] ||= (e) => o("select", e.target.value)
				}, [(t(!0), O(f, null, a(b.value, (e) => (t(), O("option", {
					key: String(e.batch_id),
					value: String(e.batch_id)
				}, h(V(e)), 9, Je))), 128))], 40, qe),
				e.actions.stopBatch ? (t(), O("button", {
					key: 0,
					type: "button",
					disabled: e.mutating,
					onClick: r[1] ||= (e) => o("batchAction", "stopBatch")
				}, "停止运行", 8, Ye)) : l("", !0),
				e.actions.cancelBatch ? (t(), O("button", {
					key: 1,
					type: "button",
					disabled: e.mutating,
					onClick: r[2] ||= (e) => o("batchAction", "cancelBatch")
				}, "取消排队", 8, Xe)) : l("", !0),
				e.actions.retryBatch ? (t(), O("button", {
					key: 2,
					type: "button",
					disabled: e.mutating,
					onClick: r[3] ||= (e) => o("batchAction", "retryBatch")
				}, "重跑失败", 8, Ze)) : l("", !0)
			])) : l("", !0)]),
			e.error ? (t(), O("div", Qe, [k(h(e.error) + " ", 1), _("button", {
				type: "button",
				onClick: r[4] ||= (e) => o("refresh")
			}, "刷新批次")])) : !e.batch || !v.value.length ? (t(), O("p", $e, h(e.loading ? "正在读取任务批次…" : "暂无注册任务批次"), 1)) : l("", !0),
			e.batch && w.value.all ? (t(), O(f, { key: 2 }, [
				_("div", et, [(t(!0), O(f, null, a(T.value.slice(1), (e) => (t(), O("span", {
					key: e.key,
					"data-tone": e.key,
					style: p({ flexGrow: w.value[e.key] })
				}, null, 12, tt))), 128))]),
				_("div", nt, [(t(!0), O(f, null, a(T.value, (e) => (t(), O("button", {
					key: e.key,
					type: "button",
					"data-batch-filter": e.key,
					"aria-pressed": u.value === e.key,
					onClick: (t) => H(e.key)
				}, [e.key === "all" ? l("", !0) : (t(), O("span", {
					key: 0,
					class: "registration-status-dot",
					"data-tone": e.key,
					"aria-hidden": "true"
				}, null, 8, it)), k(h(e.label) + " " + h(ie(w.value[e.key])), 1)], 8, rt))), 128))]),
				(t(!0), O(f, null, a(se.value, ({ job: n, tone: i, result: s, identity: u, elapsed: p, started: m, completed: v }) => (t(), O("article", {
					key: String(n.id),
					class: "registration-batch-card",
					"data-tone": i
				}, [_("div", ot, [
					_("div", st, [_("strong", null, h(n.email || "准备邮箱中…"), 1), _("small", null, h(u), 1)]),
					_("div", ct, [_("span", {
						class: "registration-state",
						"data-tone": i
					}, h(B(n)), 9, lt), s ? (t(), O("small", ut, h(s), 1)) : l("", !0)]),
					p || m || v ? (t(), O("div", dt, [p ? (t(), O("strong", ft, "运行耗时 " + h(p), 1)) : l("", !0), _("div", pt, [m ? (t(), O("small", mt, [r[6] ||= k("开始 ", -1), _("time", {
						datetime: n.started_at || void 0,
						title: m.full
					}, h(m.label), 9, ht)])) : l("", !0), v ? (t(), O("small", gt, [r[7] ||= k("结束 ", -1), _("time", {
						datetime: n.completed_at || void 0,
						title: v.full
					}, h(v.label), 9, _t)])) : l("", !0)])])) : l("", !0),
					_("div", vt, [
						_("button", {
							type: "button",
							"aria-label": `查看阶段 · ${n.email || `任务 #${n.id}`}`,
							"aria-expanded": d.value === String(n.id),
							"aria-controls": `registration-stages-${n.id}`,
							onClick: (e) => W(n)
						}, "阶段", 8, yt),
						_("button", {
							type: "button",
							"aria-label": `查看日志 · ${n.email || `任务 #${n.id}`}`,
							onClick: (e) => o("log", n.id)
						}, "日志", 8, bt),
						n.retryable ? (t(), O("button", {
							key: 0,
							type: "button",
							disabled: e.mutating,
							onClick: (e) => o("retry", n)
						}, h(n.retry_label || "重试"), 9, xt)) : l("", !0)
					])
				]), _("div", {
					id: `registration-stages-${n.id}`,
					class: "registration-batch-evidence",
					hidden: d.value !== String(n.id),
					"data-progress-state": d.value === String(n.id) ? j.value ? "error" : A.value ? "ready" : "loading" : void 0
				}, [d.value === String(n.id) ? (t(), O(f, { key: 0 }, [j.value ? (t(), O("p", Ct, [k(h(j.value) + " ", 1), _("button", {
					type: "button",
					onClick: (e) => J(n)
				}, "重试读取", 8, wt)])) : A.value ? l("", !0) : (t(), O("p", Tt, "正在读取阶段详情…")), A.value ? (t(), O(f, { key: 2 }, [
					c(Le, {
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
					A.value.error_message ? (t(), O("details", Et, [r[8] ||= _("summary", null, "原始错误摘要", -1), _("p", null, h(A.value.error_message), 1)])) : l("", !0),
					E(z)(A.value.attempts).length || E(z)(A.value.route_attempts).length ? (t(), O("details", Dt, [
						r[9] ||= _("summary", null, "尝试与线路记录", -1),
						(t(!0), O(f, null, a(E(z)(A.value.attempts), (n) => (t(), O("p", { key: E(q)(n.id || n.attempt_id) }, h(e.statusLabel(n.status)) + " · " + h(n.error_message || "已记录"), 1))), 128)),
						(t(!0), O(f, null, a(E(z)(A.value.route_attempts), (n) => (t(), O("p", { key: E(q)(n.route_attempt_no) }, " 线路尝试 " + h(n.route_attempt_no || 1) + " · " + h(n.retry_reason || e.statusLabel(n.status)), 1))), 128))
					])) : l("", !0)
				], 64)) : l("", !0)], 64)) : l("", !0)], 8, St)], 8, at))), 128)),
				D.value.length ? l("", !0) : (t(), O("p", Ot, "没有符合条件的任务")),
				_("p", kt, "显示 " + h(ie(D.value.length)) + " 条任务", 1)
			], 64)) : l("", !0)
		], 8, Re));
	}
}), $ = (e, t = {}) => P(e, t, Y), jt = (e) => ({
	method: "POST",
	headers: { "Content-Type": "application/json" },
	body: JSON.stringify(e ?? {})
});
function Mt() {
	return {
		metadata: (e) => Promise.all([$("/api/email-sources", { signal: e }), $("/api/capabilities", { signal: e })]).then(([e, t]) => ({
			...e,
			capabilities: t
		})),
		summary: (e) => $("/api/summary", { signal: e }),
		jobs: (e, t) => $(`/api/jobs?${new URLSearchParams(Object.entries(e).map(([e, t]) => [e, String(t)]))}`, { signal: t }),
		progress: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/progress`, { signal: t }),
		create: (e, t) => $("/api/jobs", {
			...jt(e),
			signal: t
		}),
		action: (e, t = {}, n) => $(e, {
			...jt(t),
			signal: n
		}),
		log: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/log`, { signal: t }),
		debug: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/debug?limit=300`, { signal: t }),
		diagnostics: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/diagnostics?limit=100`, { signal: t }),
		compare: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/debug/compare`, { signal: t })
	};
}
// src/features/registration/useRegistration.ts
var Nt = [
	"pending",
	"running",
	"stopping"
], Pt = [
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
], Ft = [
	"failed",
	"partial_success",
	"stopped",
	"cancelled",
	"interrupted",
	"request_unknown",
	"manual_reconcile",
	"attention_required"
], It = () => ({
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
}), Lt = (e) => e instanceof Error ? e.message : "请求失败", Rt = (e) => e == null ? "" : String(e).trim(), zt = (e) => encodeURIComponent(String(ue(e))), Bt = () => ({
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
function Vt(e) {
	let t = e.api || Mt(), n = m(!!e.visible), r = m(!document.hidden), i = !1, a = S(() => n.value && r.value && !i), o = s({
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
		query: It(),
		batchId: "",
		batchRefreshGeneration: 0,
		statusCounts: {},
		facets: {},
		creating: !1,
		pendingActions: {},
		lastCreate: null,
		lastAction: null,
		detail: Bt()
	}), c = S(() => o.creating), l = S(() => {
		let e = o.meta?.capabilities?.features?.register;
		return e?.enabled === !1 ? String(e.reason || "功能缺少必要配置") : "";
	}), u = (t) => e.notify?.(t), d = 0, f = 0, p = 0, h = 0, g = 0, _, v, b, x, C, w, T, E, D = "", O = 0, k = 0, A = !0, j, M = /* @__PURE__ */ new Map(), te = () => !i && r.value && o.detail.id !== null, ne = (e, t) => te() && e === g && String(o.detail.id) === String(t);
	function re() {
		d++, x?.controller.abort(), x = void 0, o.loading = !1;
	}
	function ie() {
		re(), p++, C?.controller.abort(), C = void 0, h++, w?.controller.abort(), w = void 0;
	}
	function P() {
		window.clearInterval(_), window.clearInterval(v), _ = v = void 0;
	}
	function ae() {
		if (!a.value) return !1;
		if (o.view === "tasks") return !0;
		let e = o.batch;
		return !e || String(e.batch_id) !== o.batchId || e.projection_delayed ? !0 : Nt.some((t) => Number(e.status_counts?.[t] || 0) > 0) || e.items.some((e) => Nt.includes(String(e.status || "")));
	}
	function F(e) {
		for (let t of Object.keys(It())) {
			let n = e[t];
			if (n !== void 0) {
				if (t === "page" || t === "page_size") {
					let e = Number(n);
					Number.isSafeInteger(e) && e > 0 && (o.query[t] = t === "page_size" ? Math.min(e, 500) : e);
				} else o.query[t] = String(n);
			}
		}
		if (e.progress_batch_id !== void 0) {
			let t = Rt(e.progress_batch_id);
			t !== o.batchId && (o.batchId = t, o.batch = null);
		}
	}
	function I(e = {}) {
		if (F(e), !a.value || e.automatic && !ae()) return Promise.resolve();
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
					s === "launch" && (a.progress_detail = 0), s === "tasks" && e.automatic && D === n && Date.now() - O < 3e4 && (a.include_facets = 0);
					let u = await t.jobs(a, i.signal);
					if (!l()) return;
					if (Object.prototype.hasOwnProperty.call(u, "status_counts") && (o.statusCounts = u.status_counts || {}), s === "launch") {
						o.batches = u.progress_batches || [];
						let e = u.progress_batch || null;
						if (!e && o.batchId) {
							let e = Rt(o.batches[0]?.batch_id);
							if (e !== o.batchId && (o.batchId = e, o.batch = null, e && !r)) continue;
						}
						!o.batchId && e?.batch_id && (o.batchId = Rt(e.batch_id)), o.batch = e, o.batchRefreshGeneration = c;
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
				l() && !N(e) && (o.error = Lt(e));
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
	function oe(e) {
		return I({ progress_batch_id: Rt(e) });
	}
	function se(e, n) {
		return t.progress(ue(e), n);
	}
	function L(e) {
		return I({
			...e,
			page: e.page ?? 1
		});
	}
	function R(e) {
		return I({ page: e });
	}
	function z(e) {
		return I({
			page: 1,
			page_size: e
		});
	}
	function B(e) {
		o.summary = e;
	}
	function V(e) {
		o.summary = {
			...o.summary || {},
			email_supply: e || {}
		};
	}
	function H() {
		if (!a.value) return Promise.resolve();
		C?.controller.abort();
		let e = ++p, n = new AbortController(), r = (async () => {
			try {
				let r = await t.summary(n.signal);
				e === p && a.value && B(r);
			} catch (t) {
				e === p && a.value && !N(t) && V({
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
	function U(e = !1) {
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
				n === h && a.value && !N(e) && (o.error = Lt(e));
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
	function W() {
		P(), a.value && (U(), I({ coalesce: !0 }), H(), _ = window.setInterval(() => {
			I({ automatic: !0 });
		}, 5e3), v = window.setInterval(() => {
			C || H();
		}, 1e4));
	}
	function G(e) {
		n.value !== e && (n.value = e, e ? W() : (P(), ie()));
	}
	function K(e) {
		["launch", "tasks"].includes(e) && o.view !== e && (o.view = e, re(), I({ coalesce: !0 }));
	}
	function q(e, t = "已受理") {
		let n = e.message || e.warning || (e.started_count == null ? e.deleted_count == null ? e.cancelled == null ? t : `已取消 ${e.cancelled} 个排队任务` : `已删除 ${e.deleted_count} 个任务` : `已提交 ${e.started_count} 个失败任务`), r = Array.isArray(e.skipped) ? e.skipped.length : 0;
		o.receipt = {
			tone: e.warning ? "warning" : "success",
			message: String(n) + (r ? `，跳过 ${r} 个` : "")
		}, u(o.receipt.message);
	}
	function J(e) {
		let t = Rt(e.jobs?.[0]?.batch_id || e.job?.batch_id || e.batch_id);
		t && (o.batchId = t, o.batch = null);
	}
	function ce(e, n = {}) {
		let r = JSON.stringify([e, n]), i = M.get(r);
		if (i) return i;
		o.pendingActions[r] = !0;
		let a = (async () => {
			try {
				let r = await t.action(e, n);
				return o.lastAction = r, J(r), q(r), /\/delete(?:-bulk)?$/.test(e) && o.detail.id !== null && (Array.isArray(r.deleted) ? r.deleted : r.deleted === !0 ? [e.split("/").at(-2)] : []).some((e) => String(e) === String(o.detail.id)) && me(), I(), o.detail.id !== null && Z(), r;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: Lt(e)
				}, u(o.receipt.message), e;
			} finally {
				M.delete(r), delete o.pendingActions[r];
			}
		})();
		return M.set(r, a), a;
	}
	function le(e) {
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
				return o.lastCreate = n, J(n), q(n, `已提交 ${n.submitted || 0} 个任务`), I(), n;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: Lt(e)
				}, u(o.receipt.message), e;
			} finally {
				o.creating = !1, j = void 0;
			}
		})(), j);
	}
	function Y(e) {
		let t = o.batch?.items || [];
		return e === "stopBatch" ? t.filter((e) => e.status === "running" || e.status === "stopping") : e === "cancelBatch" ? t.filter((e) => e.status === "pending") : t.filter((e) => Ft.includes(String(e.status)) && e.retryable);
	}
	let X = S(() => ({
		stopBatch: !!o.batchId && Y("stopBatch").length > 0,
		cancelBatch: !!o.batchId && Y("cancelBatch").length > 0,
		retryBatch: Y("retryBatch").length > 0
	}));
	async function de(t, n, r = [], i = !1) {
		let a = t === "stopBatch" || t === "cancelBatch" || t === "retryBatch" ? Y(t) : [], s = t === "retryBulk" || t === "deleteBulk" ? r.map((e) => ue(e)) : a.map((e) => ue(e.id));
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
		}, l = t === "retry" && n?.retry_action === "codex" ? "仅补跑 Codex 授权" : t === "retry" && n?.retry_action === "twofa" ? "重新登录检查并补齐 Authenticator 2FA" : t === "retry" && n?.retry_action === "registration_resume" ? "使用已保存账号密码继续邮箱验证" : "有原邮箱则复用，没有原邮箱则重新领取；已创建账号的任务按缺失步骤补跑，不能重试的由后端校验", d = t === "retry" || t === "retryBulk" || t === "retryBatch" ? `\n${l}。原任务记录和日志会保留。` : t === "stop" || t === "stopBatch" ? "\n任务会在当前步骤检查点退出。" : t === "cancelAll" || t === "cancelBatch" ? "\n运行中的任务不受影响。" : "", f = encodeURIComponent(o.batchId), p = n ? zt(n.id) : "";
		return await (e.confirm ? e.confirm(`确定${c[t]}吗？${d}`) : window.confirm(`确定${c[t]}吗？${d}`)) ? ce(...{
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
	async function Z() {
		if (!te()) return;
		T?.abort(), window.clearTimeout(b);
		let e = o.detail.id, n = ++g, r = new AbortController();
		T = r, o.detail.loading = !0, o.detail.error = "";
		let i = () => ne(n, e);
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
			i() && !N(e) && (o.detail.error = Lt(e));
		} finally {
			i() && (o.detail.loading = !1, Pt.includes(String(o.detail.job?.status || "")) || (b = window.setTimeout(() => void Z(), 2e3)));
		}
	}
	function pe(t, n) {
		let r = ue(t), i = [...o.jobs, ...o.batch?.items || []].find((e) => String(e.id) === String(r));
		i?.operation_task_id && e.openTask ? e.openTask(i.operation_task_id, i.operation_run_id || null, n || null) : (fe(), o.detail = {
			...Bt(),
			id: r
		}, Z());
	}
	function me() {
		fe(), o.detail = Bt();
	}
	async function he(e) {
		let n = ue(e);
		if (!ne(g, n)) return null;
		E?.abort();
		let r = new AbortController();
		E = r;
		let i = () => te() && E === r && !r.signal.aborted && String(o.detail.id) === String(n);
		o.detail.comparing = !0, o.detail.compareError = "";
		try {
			let e = await t.compare(n, r.signal);
			return i() ? (o.detail.comparison = e, e) : null;
		} catch (e) {
			if (i() && !N(e)) throw o.detail.compareError = Lt(e), e;
			return null;
		} finally {
			i() && (o.detail.comparing = !1, E = void 0);
		}
	}
	function ge() {
		r.value = !document.hidden, r.value ? (W(), o.detail.id !== null && Z()) : (P(), ie(), fe());
	}
	function _e() {
		i = !0, P(), ie(), fe(), document.removeEventListener("visibilitychange", ge);
	}
	return document.addEventListener("visibilitychange", ge), ee() && y(_e), {
		state: o,
		active: a,
		creating: c,
		registrationUnavailable: l,
		ensureMeta: U,
		load: I,
		loadSummary: H,
		renderEmailSupply: V,
		applySummary: B,
		setVisible: G,
		setView: K,
		setBatch: oe,
		updateQuery: L,
		setPage: R,
		setSize: z,
		shouldPollJobs: ae,
		create: le,
		action: ce,
		executeAction: de,
		compare: he,
		openLog: pe,
		refreshDetail: Z,
		closeDetail: me,
		notify: u,
		terminalStatuses: Pt,
		activeStatuses: Nt,
		batchActions: X,
		readBatchProgress: se,
		dispose: _e
	};
}
// src/features/registration/RegistrationPage.vue?vue&type=script&setup=true&lang.ts
var Ht = ["data-view"], Ut = { class: "registration-launch" }, Wt = {
	class: "registration-summary",
	"aria-label": "注册与本地邮箱概览"
}, Gt = {
	class: "registration-launch-panel",
	"aria-labelledby": "registration-launch-title"
}, Kt = { class: "registration-launcher" }, qt = ["disabled", "aria-describedby"], Jt = ["value"], Yt = { class: "registration-debug" }, Xt = ["disabled", "title"], Zt = { class: "registration-hint" }, Qt = { id: "registrationEmailSupplyHint" }, $t = { class: "ui-list registration-tasks" }, en = { class: "ui-list-bulkbar registration-toolbar" }, tn = ["disabled"], nn = ["disabled"], rn = {
	class: "ui-list-toolbar registration-count-row",
	"data-registration-count-row": ""
}, an = { class: "ui-list-toolbar__main registration-count-main" }, on = { class: "ui-list-count registration-count" }, sn = { class: "ui-list-toolbar__actions registration-count-actions" }, cn = { class: "registration-mobile-filter" }, ln = {
	key: 0,
	class: "ui-list-feedback is-error registration-list-error",
	role: "alert"
}, un = {
	class: "ui-table-scroll registration-table-wrap",
	tabindex: "0",
	"aria-label": "注册任务列表，可横向滚动"
}, dn = { key: 2 }, fn = { class: "ui-col-check" }, pn = [
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], mn = { key: 0 }, hn = { class: "registration-row-actions" }, gn = ["onClick"], _n = ["onUpdate:modelValue"], vn = ["onClick"], yn = ["onClick"], bn = ["onClick"], xn = ["disabled", "onClick"], Sn = { id: "registration-log-title" }, Cn = { key: 0 }, wn = {
	key: 1,
	role: "alert"
}, Tn = { key: 2 }, En = ["disabled"], Dn = ["href"], On = { key: 0 }, kn = {
	key: 1,
	role: "alert"
}, An = { key: 3 }, jn = ["href"], Mn = /* @__PURE__ */ e({
	__name: "RegistrationPage",
	props: { deps: {} },
	setup(e, { expose: s }) {
		let d = e, y = Vt(d.deps), { state: C } = y, D = ne({
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
		ce(N, () => C.detail.id !== null, () => y.active.value);
		let P = m(1), F = m(3), I = m(""), oe = m(!1), se = m(""), L = m(""), R = m(""), z = m(""), B = m(""), V = m(""), H = m(""), U = m(""), W = m(1), G = m(20), K = m(/* @__PURE__ */ new Set()), q = m({}), J = S(() => C.view === "launch"), ue = S(() => C.view === "tasks"), Y = S(() => C.jobs), X = m(null), de = S(() => ({
			id: L.value,
			email: R.value,
			email_source: z.value,
			status: se.value,
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
		}, Z = S(() => Object.entries(de.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${fe[e]}：${e === "status" ? ke(t) : e === "email_source" ? Oe(t) : t}`,
			removeLabel: `清除${fe[e]}筛选`
		})));
		function pe(e, t) {
			let n = {
				id: L,
				email: R,
				email_source: z,
				status: se,
				proxy: B,
				error: V,
				date_from: H,
				date_to: U
			};
			n[e].value = t, X.value = null, Ie();
		}
		let me = (e) => e.error_info ? ae(e.error_info) : e.error_message ? "执行异常" : "—", he = S(() => C.statusCounts.active ?? [
			"pending",
			"running",
			"stopping"
		].reduce((e, t) => e + Number((Object.keys(C.statusCounts).length ? C.statusCounts : C.batch?.status_counts || {})[t] || 0), 0)), ge = S(() => !!C.meta?.manual_mode), _e = m(!1), ye = S(() => {
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
			return z.value && !e.has(z.value) && e.set(z.value, {
				value: z.value,
				label: z.value
			}), [...e.values()];
		}), be = S(() => ge.value ? [{
			value: "manual",
			label: "手动配置邮箱"
		}] : C.meta?.sources?.filter((e) => e.enabled === !0) || []), xe = S(() => y.registrationUnavailable.value || (C.meta && !be.value.length ? "没有可用的邮箱来源。请先导入本地邮箱，再重新选择。" : "")), Se = S(() => xe.value || (C.meta ? ge.value ? "使用手动配置的邮箱来源。" : I.value ? "" : "请选择本批使用的邮箱来源。" : "正在读取邮箱来源…")), Ce = S(() => C.summary?.email_supply || {}), we = (e) => {
			let t = Ce.value[e];
			return Number.isInteger(t) && Number(t) >= 0 ? t : Ce.value.status === "error" ? "读取失败" : "未知";
		}, Te = S(() => `仅统计本地库存；用完后请手动导入；邮箱由 Email Butler 等邮箱服务准备${Ce.value.reason ? `；${Ce.value.reason}` : ""}`), Ee = S(() => [
			{
				label: "已注册",
				value: C.summary?.accounts ?? "—"
			},
			{
				label: "本地邮箱总数",
				value: we("total")
			},
			{
				label: "本地可用",
				value: we("available")
			},
			{
				label: "本地已用",
				value: we("used")
			},
			{
				label: "本地失败",
				value: we("failed")
			}
		]), De = (e) => C.meta?.registration_drivers?.find((t) => String(t.value) === String(e))?.label || {
			protocol: "本地优化 Protocol（历史）",
			protocol_oss: "开源 Protocol（历史）",
			protocol_oss_2: "开源protocol-2",
			sentinel_rs: "Rust sentinel-rs",
			roxy: "本地 Roxy",
			roxy_oss: "开源 Roxy（历史）"
		}[String(e || "")] || String(e || "未知"), Oe = (e) => ye.value.find((t) => String(t.value) === String(e))?.label || String(e || "-"), ke = (e) => ({
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
		})[String(e)] || String(e || "等待中"), Ae = async (e) => d.deps.confirm ? await d.deps.confirm(e) : window.confirm(e);
		function je(e) {
			e || (X.value = null), y.setVisible(e);
		}
		function Me(e) {
			X.value = null, y.setView(e);
		}
		function Ne(e) {
			let t = N.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && y.closeDetail();
		}
		async function Pe() {
			if (C.creating || _e.value) return;
			if (xe.value) {
				C.receipt = {
					tone: "warning",
					message: xe.value
				};
				return;
			}
			let e = Number(P.value), t = Number(F.value);
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
			if (!be.value.some((e) => e.value === I.value)) {
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
				debug_enabled: oe.value
			};
			_e.value = !0;
			try {
				if (he.value > 0 && !await Ae(`当前任务表里已有 ${he.value} 个任务在跑或排队，这次会再加 ${e} 个，确定继续？`)) return;
				let t = await y.create(n);
				Number.isSafeInteger(t?.workers) && t.workers > 0 && (F.value = t.workers);
			} catch {} finally {
				_e.value = !1;
			}
		}
		async function Q(e, t) {
			let n = Array.from(K.value);
			try {
				await y.executeAction(e, t, n, oe.value), (e === "deleteBulk" || e === "retryBulk") && (K.value = /* @__PURE__ */ new Set());
			} catch {}
		}
		function Fe() {
			se.value = L.value = R.value = z.value = B.value = V.value = H.value = U.value = "", W.value = 1, y.load(Ve());
		}
		function Ie() {
			W.value = 1, y.load(Ve());
		}
		function Le(e) {
			let t = e.target.checked;
			Y.value.filter((e) => !["running", "stopping"].includes(String(e.status))).forEach((e) => t ? K.value.add(String(e.id)) : K.value.delete(String(e.id))), K.value = new Set(K.value);
		}
		function Re(e, t) {
			let n = new Set(K.value);
			t.target.checked ? n.add(String(e)) : n.delete(String(e)), K.value = n;
		}
		function ze(e) {
			return [
				e.proxy_provider,
				e.proxy_endpoint && e.proxy_endpoint !== "-" ? e.proxy_endpoint : "",
				e.proxy_region && e.proxy_region !== "-" ? e.proxy_region : ""
			].filter(Boolean).join(" · ") || "-";
		}
		function Be(e) {
			W.value = 1, y.setBatch(e);
		}
		function Ve() {
			return {
				status: se.value,
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
		function He(e) {
			let t = String(q.value[String(e.id)] || "").trim();
			t ? y.action("/api/manual-otp", {
				email: e.email,
				code: t,
				job_id: e.id
			}).then(() => {
				q.value = {
					...q.value,
					[String(e.id)]: ""
				};
			}).catch(() => {}) : C.receipt = {
				tone: "warning",
				message: "请先填写邮箱验证码"
			};
		}
		async function Ue() {
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
			setVisible: je,
			setView: Me,
			loadSummary: y.loadSummary,
			renderEmailSupply: y.renderEmailSupply,
			applySummary: y.applySummary,
			action: y.action,
			openLog: y.openLog,
			closeDetail: y.closeDetail
		}), r(() => ({ ...C.query }), (e) => {
			W.value = e.page, G.value = e.page_size, L.value = e.id, R.value = e.email, z.value = e.email_source, se.value = e.status, B.value = e.proxy, V.value = e.error, H.value = e.date_from, U.value = e.date_to;
		}, { immediate: !0 }), r([ge, be], () => {
			ge.value ? I.value = "manual" : be.value.some((e) => e.value === I.value) || (I.value = "");
		}, { immediate: !0 }), o(() => {
			y.ensureMeta();
		}), (e, r) => (t(), O("div", {
			class: "registration-vue-page",
			"data-view": E(C).view
		}, [
			i(_("section", Ut, [
				_("dl", Wt, [(t(!0), O(f, null, a(Ee.value, (e) => (t(), O("div", { key: e.label }, [_("dt", null, h(e.label), 1), _("dd", null, h(typeof e.value == "number" ? e.value.toLocaleString("zh-CN") : e.value), 1)]))), 128))]),
				_("section", Gt, [r[23] ||= _("h2", { id: "registration-launch-title" }, "新建注册批次", -1), _("form", {
					novalidate: "",
					onSubmit: b(Pe, ["prevent"])
				}, [_("div", Kt, [
					_("label", null, [r[19] ||= k("邮箱来源 ", -1), i(_("select", {
						"onUpdate:modelValue": r[0] ||= (e) => I.value = e,
						disabled: !E(C).meta || ge.value || !be.value.length,
						"aria-describedby": Se.value ? "registration-launch-hint registrationEmailSupplyHint" : "registrationEmailSupplyHint"
					}, [r[18] ||= _("option", { value: "" }, "请选择本次邮箱来源", -1), (t(!0), O(f, null, a(be.value, (e) => (t(), O("option", {
						key: String(e.value),
						value: String(e.value)
					}, h(e.label || e.value), 9, Jt))), 128))], 8, qt), [[u, I.value]])]),
					_("label", null, [r[20] ||= k("注册数量", -1), i(_("input", {
						"onUpdate:modelValue": r[1] ||= (e) => P.value = e,
						min: "1",
						type: "number",
						inputmode: "numeric"
					}, null, 512), [[
						w,
						P.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", null, [r[21] ||= k("并发线程", -1), i(_("input", {
						"onUpdate:modelValue": r[2] ||= (e) => F.value = e,
						min: "1",
						step: "1",
						type: "number",
						inputmode: "numeric"
					}, null, 512), [[
						w,
						F.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", Yt, [i(_("input", {
						"onUpdate:modelValue": r[3] ||= (e) => oe.value = e,
						type: "checkbox"
					}, null, 512), [[v, oe.value]]), r[22] ||= k(" 调试模式", -1)]),
					_("button", {
						type: "submit",
						class: "registration-start",
						disabled: E(C).creating || _e.value || !I.value || !!xe.value,
						title: xe.value || void 0
					}, h(E(C).creating ? "提交中…" : "开始注册"), 9, Xt)
				]), _("p", Zt, [Se.value ? (t(), O("span", {
					key: 0,
					id: "registration-launch-hint",
					class: x({ "registration-warning": xe.value }),
					role: "status"
				}, h(Se.value), 3)) : l("", !0), _("span", Qt, h(Te.value), 1)])], 32)]),
				J.value ? (t(), g(At, {
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
					"status-label": ke,
					"source-label": Oe,
					"driver-label": De,
					"read-progress": E(y).readBatchProgress,
					onSelect: Be,
					onRefresh: r[4] ||= (e) => E(y).load(),
					onBatchAction: r[5] ||= (e) => Q(e),
					onRetry: r[6] ||= (e) => Q("retry", e),
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
			], 512), [[T, J.value]]),
			i(_("section", $t, [
				_("div", en, [
					_("button", {
						type: "button",
						class: "ui-button",
						onClick: r[7] ||= (e) => Q("retryBulk"),
						disabled: !K.value.size
					}, "重试", 8, tn),
					_("button", {
						type: "button",
						class: "ui-button ui-button--danger",
						onClick: r[8] ||= (e) => Q("deleteBulk"),
						disabled: !K.value.size
					}, "删除", 8, nn),
					_("button", {
						type: "button",
						class: "ui-button",
						onClick: r[9] ||= (e) => Q("cancelAll")
					}, "取消排队"),
					_("button", {
						type: "button",
						class: "ui-button",
						onClick: Ie
					}, "刷新")
				]),
				_("div", rn, [_("div", an, [_("span", on, "共 " + h(E(C).total.toLocaleString()) + " 条任务", 1), c(te, {
					items: Z.value,
					onRemove: r[10] ||= (e) => pe(e, "")
				}, null, 8, ["items"])]), _("div", sn, [
					_("button", {
						type: "button",
						class: "ui-link",
						"aria-label": "恢复注册任务列宽",
						onClick: ee
					}, "恢复列宽"),
					_("span", cn, [c(ve, {
						values: de.value,
						sources: ye.value,
						open: X.value === "all",
						"onUpdate:open": r[11] ||= (e) => X.value = e ? "all" : null,
						onChange: pe
					}, null, 8, [
						"values",
						"sources",
						"open"
					])]),
					Z.value.length ? (t(), O("button", {
						key: 0,
						type: "button",
						onClick: Fe
					}, "清筛")) : l("", !0)
				])]),
				E(C).error ? (t(), O("div", ln, [k(h(E(C).error) + " ", 1), _("button", {
					type: "button",
					class: "ui-link",
					onClick: Ie
				}, "重试")])) : l("", !0),
				_("div", un, [_("table", {
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
						onChange: Le
					}, null, 32)) : e.filter ? (t(), g(ve, {
						key: 1,
						column: e.filter,
						values: de.value,
						sources: ye.value,
						open: X.value === e.filter,
						"onUpdate:open": (t) => X.value = t ? e.filter : null,
						onChange: pe
					}, null, 8, [
						"column",
						"values",
						"sources",
						"open",
						"onUpdate:open"
					])) : (t(), O("span", dn, h(e.label), 1)), n < A.length - 1 ? (t(), g(re, {
						key: 3,
						label: e.label,
						onStart: (e) => E(D).resize(n, e),
						onNudge: (e) => E(D).resizeWithKeyboard(n, e)
					}, null, 8, [
						"label",
						"onStart",
						"onNudge"
					])) : l("", !0)], 2)), 64))])]),
					_("tbody", null, [E(C).loading || !Y.value.length ? (t(), g(j, {
						key: 0,
						colspan: 11,
						loading: E(C).loading,
						"loading-title": "正在加载任务…",
						title: "暂无匹配任务"
					}, null, 8, ["loading"])) : l("", !0), (t(!0), O(f, null, a(Y.value, (e) => (t(), O("tr", {
						key: String(e.id),
						class: x({ "is-selected": K.value.has(String(e.id)) })
					}, [
						_("td", fn, [_("input", {
							type: "checkbox",
							"aria-label": `选择任务 ${e.id}`,
							checked: K.value.has(String(e.id)),
							disabled: ["running", "stopping"].includes(String(e.status)),
							onChange: (t) => Re(e.id, t)
						}, null, 40, pn)]),
						_("td", null, [c(M, {
							text: `#${e.id}`,
							secondary: e.parent_job_id ? `↳ #${e.parent_job_id}` : void 0
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(M, { text: String(e.email || "-") }, null, 8, ["text"])]),
						_("td", null, [c(M, { text: Oe(e.email_source) }, null, 8, ["text"])]),
						_("td", null, [c(M, { text: De(e.registration_driver) }, null, 8, ["text"])]),
						_("td", null, [c(M, {
							text: ze(e),
							secondary: String(e.proxy_status || "")
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(M, { text: ke(e.debug_state === "paused" ? "debug_paused" : e.display_status || e.status) }, null, 8, ["text"])]),
						_("td", null, [c(M, { text: String(e.started_at || "-") }, null, 8, ["text"])]),
						_("td", null, [c(M, { text: String(e.completed_at || "-") }, null, 8, ["text"])]),
						_("td", null, [e.error_message || e.error_info ? (t(), g(ie, {
							key: 0,
							"data-registration-result": "",
							label: me(e),
							title: String(e.error_message || me(e)),
							tone: "danger"
						}, {
							details: n(() => [_("p", null, h(e.error_message || me(e)), 1), e.error_info ? (t(), O("p", mn, h(e.error_info), 1)) : l("", !0)]),
							_: 2
						}, 1032, ["label", "title"])) : (t(), g(M, {
							key: 1,
							text: "—"
						}))]),
						_("td", hn, [
							_("button", {
								type: "button",
								class: "ui-link",
								onClick: (t) => E(y).openLog(e.id)
							}, "日志", 8, gn),
							e.manual_otp_required && e.status === "running" ? (t(), O(f, { key: 0 }, [i(_("input", {
								"onUpdate:modelValue": (t) => q.value[String(e.id)] = t,
								placeholder: "邮箱验证码"
							}, null, 8, _n), [[w, q.value[String(e.id)]]]), _("button", {
								type: "button",
								onClick: (t) => He(e)
							}, "提交验证码", 8, vn)], 64)) : l("", !0),
							[
								"pending",
								"running",
								"stopping"
							].includes(String(e.status)) ? (t(), O("button", {
								key: 1,
								type: "button",
								onClick: (t) => Q("stop", e)
							}, "停止", 8, yn)) : l("", !0),
							e.retryable ? (t(), O("button", {
								key: 2,
								type: "button",
								onClick: (t) => Q("retry", e)
							}, "重试", 8, bn)) : l("", !0),
							_("button", {
								type: "button",
								disabled: ["running", "stopping"].includes(String(e.status)),
								onClick: (t) => Q("delete", e)
							}, "删除", 8, xn)
						])
					], 2))), 128))])
				], 4)]),
				c(le, {
					label: "注册任务分页",
					page: W.value,
					size: G.value,
					total: E(C).total,
					busy: E(C).loading,
					"onUpdate:page": r[12] ||= (e) => {
						W.value = e, E(y).load(Ve());
					},
					"onUpdate:size": r[13] ||= (e) => {
						G.value = e, W.value = 1, E(y).load(Ve());
					}
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			], 512), [[T, ue.value]]),
			E(C).receipt ? (t(), O("div", {
				key: 0,
				class: x(["registration-receipt", `is-${E(C).receipt.tone}`]),
				role: "status"
			}, h(E(C).receipt.message), 3)) : l("", !0),
			_("dialog", {
				ref_key: "logDialog",
				ref: N,
				class: "registration-dialog",
				"aria-labelledby": "registration-log-title",
				onCancel: r[16] ||= b((...e) => E(y).closeDetail && E(y).closeDetail(...e), ["prevent"]),
				onClose: r[17] ||= (...e) => E(y).closeDetail && E(y).closeDetail(...e),
				onClick: Ne
			}, [
				_("header", null, [_("h2", Sn, "任务 #" + h(E(C).detail.id) + " 日志", 1), _("button", {
					type: "button",
					onClick: r[14] ||= (...e) => E(y).closeDetail && E(y).closeDetail(...e)
				}, "关闭")]),
				E(C).detail.loading ? (t(), O("p", Cn, "加载中…")) : l("", !0),
				E(C).detail.error ? (t(), O("p", wn, h(E(C).detail.error), 1)) : l("", !0),
				_("pre", null, h(E(C).detail.log || "（暂无日志）"), 1),
				E(C).detail.debug?.enabled ? (t(), O("div", Tn, [
					r[24] ||= _("strong", null, "网络调试", -1),
					_("button", {
						type: "button",
						disabled: E(C).detail.comparing,
						onClick: Ue
					}, "与同批成功任务对比", 8, En),
					_("a", {
						href: `/api/jobs/${E(C).detail.id}/debug/har`,
						download: ""
					}, "下载脱敏 HAR", 8, Dn),
					_("button", {
						type: "button",
						onClick: r[15] ||= (e) => E(y).action(`/api/jobs/${E(C).detail.id}/debug/release`, { action: "finish" })
					}, "结束调试并收口"),
					E(C).detail.comparison ? (t(), O("pre", On, h(E(C).detail.comparison), 1)) : l("", !0),
					E(C).detail.compareError ? (t(), O("p", kn, h(E(C).detail.compareError), 1)) : l("", !0)
				])) : l("", !0),
				E(C).detail.diagnostics?.captured ? (t(), O("div", An, [
					r[26] ||= _("strong", null, "失败诊断", -1),
					E(C).detail.diagnostics.screenshot_url ? (t(), O("a", {
						key: 0,
						href: String(E(C).detail.diagnostics.screenshot_url),
						target: "_blank",
						rel: "noopener"
					}, "打开失败截图", 8, jn)) : l("", !0),
					_("details", null, [r[25] ||= _("summary", null, "完整诊断证据", -1), _("pre", null, h(E(C).detail.diagnostics), 1)])
				])) : l("", !0)
			], 544)
		], 8, Ht));
	}
});
// src/registration.ts
function Nn(e, t = {}) {
	let n = C(Mn, { deps: {
		...t,
		api: t.api || Mt()
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
export { Nn as mountRegistration };
