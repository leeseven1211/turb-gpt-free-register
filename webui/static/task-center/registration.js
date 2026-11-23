import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, S as c, _ as l, a as u, c as d, d as f, dt as p, et as m, ft as h, g, h as _, i as v, j as y, l as b, lt as x, m as S, n as C, o as w, s as ee, st as T, t as E, v as D, w as te, x as O } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { i as k, n as A, r as j, t as ne } from "./ListFilterSummary-C8h8bMwn.js";
import { n as re, t as ie } from "./ColumnResizer-CPJ9UuoZ.js";
import { t as ae } from "./ListResult-CPVXnLlZ.js";
import { n as M, r as N } from "./client-B5R_MNgP.js";
import { t as oe } from "./errorLabels-PB-ct2iU.js";
import { n as P, t as F } from "./time-DOD6oyhP.js";
import { O as I, _ as L, a as R, b as z, g as B, h as V, i as H, n as U, p as W, r as G, t as K, v as q, x as J, y as Y } from "./StepEvidence-pWRmuzGv.js";
import { t as se } from "./useNativeDialog-DWisXYg9.js";
import { t as ce } from "./ListPagination-DURVj-Kj.js";
import { a as le, r as ue } from "./taskIds-BlchWwUp.js";
// src/features/registration/RegistrationFilters.vue?vue&type=script&setup=true&lang.ts
var X = { class: "registration-filter-fields" }, de = { key: 0 }, fe = ["value"], pe = ["value", "aria-label"], Z = ["value"], me = ["value"], he = ["value"], ge = [
	"type",
	"value",
	"aria-label"
], _e = { class: "list-filter-actions" }, ve = /*#__PURE__*/ E(/* @__PURE__ */ e({
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
		return (r, s) => (t(), g(k, {
			label: e.column ? o[e.column] : "注册任务",
			"trigger-label": e.column ? o[e.column] : "筛选",
			active: e.column ? !!e.values[e.column] : Object.values(e.values).some(Boolean),
			summary: y.value,
			open: e.open,
			"onUpdate:open": s[7] ||= (e) => c("update:open", e)
		}, {
			default: n(() => [_("div", X, [
				e.column ? l("", !0) : (t(), D("label", de, [s[8] ||= O("筛选列", -1), i(_("select", {
					"onUpdate:modelValue": s[0] ||= (e) => p.value = e,
					"aria-label": "选择注册任务筛选列"
				}, [(t(), D(f, null, a(o, (e, t) => _("option", {
					key: t,
					value: t
				}, h(e), 9, fe)), 64))], 512), [[u, p.value]])])),
				_("label", null, [O(h(o[v.value]) + " ", 1), v.value === "email_source" ? (t(), D("select", {
					key: 0,
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[1] ||= (e) => C(e.target.value)
				}, [s[9] ||= _("option", { value: "" }, "全部邮箱来源", -1), (t(!0), D(f, null, a(e.sources, (e) => (t(), D("option", {
					key: e.value,
					value: e.value
				}, h(e.label || e.value), 9, Z))), 128))], 40, pe)) : v.value === "status" ? (t(), D("select", {
					key: 1,
					value: y.value,
					"aria-label": "筛选状态值",
					onChange: s[2] ||= (e) => C(e.target.value)
				}, [s[10] ||= _("option", { value: "" }, "全部状态", -1), (t(!0), D(f, null, a(b.value, (e) => (t(), D("option", {
					key: e,
					value: e
				}, h(x(e)), 9, he))), 128))], 40, me)) : (t(), D("input", {
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
			return R(e.map((e, t) => ({
				...e,
				id: String(e.id || e.step_id || e.key || `step-${t + 1}`),
				label: e.label || e.name || e.id || e.step_id
			})));
		}), s = m(), u = m(), d = m(), p = S(() => {
			if (!r.inline) return;
			if (d.value) return o.value.find((e) => q(e) === d.value);
			if (!r.focusFailure) return;
			let e = String(W(r.job?.progress?.failure).step_id || "");
			return o.value.find((t) => q(t) === e) || o.value.find((e) => z(e) === "failed");
		});
		function v(e) {
			r.inline ? d.value = q(e) : i("log", q(e));
		}
		se(u, () => !!s.value && r.active, () => r.active);
		let y = (e) => I(L(e));
		function C(e) {
			let t = W(e.debug_pause);
			return t.state === "paused" ? `调试暂停 · 等待结束调试${t.paused_at ? ` · 暂停于 ${P(t.paused_at)}` : " · 暂停时间未记录"}${t.hold_until ? ` · 保留至 ${P(t.hold_until)}` : ""}` : "";
		}
		function w(e) {
			let t = e.attempts || [], n = e.children || [], i = (e) => e.raw_stage_label || n.find((t) => t.id === e.raw_stage)?.label || e.raw_stage || "阶段", a = [...new Set(t.map(i))];
			return [
				`${Y(e)} · ${H(e)}`,
				C(e),
				e.reason || e.message || "",
				`开始：${P(e.started_at)}`,
				`结束：${P(e.completed_at)}`,
				`耗时：${y(e)}`,
				a.length ? `已记录阶段：${a.join("、")}` : "",
				n.length ? `子步骤（${n.length}）` : "",
				...n.map((e) => `${Y(e)} · ${H(e)} · ${y(e)}${e.reason || e.message ? `\n${e.reason || e.message}` : ""}`),
				t.length ? `阶段事件（${t.length} 条）` : "",
				...t.map((e, t) => `${t + 1}. ${i(e)} · ${V(e.display_status || e.state)}${e.created_at ? ` · ${P(e.created_at)}` : e.event_time_known === !1 ? " · 发生时间未记录" : ""}${e.message ? `\n${e.message}` : ""}`),
				r.inline ? "点击步骤查看阶段摘要" : "点击步骤查看对应日志"
			].filter(Boolean).join("\n");
		}
		return (n, r) => (t(), D("div", ye, [
			o.value.length ? (t(), D("div", be, [e.inline ? (t(), D("h3", xe, "执行阶段")) : l("", !0), r[5] ||= _("p", { class: "registration-step-note" }, "按首次记录排列，不代表固定执行顺序", -1)])) : l("", !0),
			o.value.length ? (t(), D("ul", Se, [(t(!0), D(f, null, a(o.value, (n) => (t(), D("li", {
				key: T(q)(n),
				class: x([`is-${T(z)(n)}`, { "is-inspected": p.value === n }])
			}, [_("button", {
				type: "button",
				title: w(n),
				"aria-pressed": e.inline ? p.value === n : void 0,
				onClick: (e) => v(n)
			}, [
				_("strong", null, [T(z)(n) === "success" ? (t(), D("span", we, "✓")) : T(z)(n) === "failed" ? (t(), D("span", Te, "!")) : l("", !0), O(" " + h(T(Y)(n)), 1)]),
				_("small", null, h(T(H)(n)), 1),
				_("small", Ee, "耗时 " + h(y(n)), 1),
				(t(!0), D(f, null, a(T(G)(n), (e) => (t(), D("small", { key: e }, h(e), 1))), 128)),
				C(n) ? (t(), D("small", De, h(C(n)), 1)) : l("", !0)
			], 8, Ce), e.inline ? l("", !0) : (t(), D("button", {
				key: 0,
				type: "button",
				"aria-label": `查看${T(Y)(n)}的关系与证据`,
				onClick: (e) => s.value = n
			}, "详情", 8, Oe))], 2))), 128))])) : l("", !0),
			p.value ? (t(), D("div", ke, [_("div", Ae, [
				_("strong", null, h(T(Y)(p.value)), 1),
				_("span", null, " · " + h(T(H)(p.value)), 1),
				p.value.reason || p.value.message ? (t(), D("p", je, h(p.value.reason || p.value.message), 1)) : e.focusFailure && T(q)(p.value) === T(W)(e.job.progress?.failure).step_id && T(W)(e.job.progress?.failure).message ? (t(), D("p", Me, h(T(W)(e.job.progress?.failure).message), 1)) : l("", !0)
			]), _("div", Ne, [_("button", {
				type: "button",
				"aria-label": `查看${T(Y)(p.value)}的关系与证据`,
				onClick: r[0] ||= (e) => s.value = p.value
			}, "阶段详情", 8, Pe), _("button", {
				type: "button",
				onClick: r[1] ||= (e) => i("log", T(q)(p.value))
			}, "阶段日志")])])) : o.value.length ? l("", !0) : (t(), D("p", Q, "暂无阶段记录，可查看任务日志。")),
			o.value.length ? (t(), D("details", Fe, [r[6] ||= _("summary", null, "依赖与执行记录", -1), (t(!0), D(f, null, a(o.value, (e) => (t(), D("div", { key: T(q)(e) }, [_("strong", null, h(T(Y)(e)), 1), c(U, {
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
				_("header", null, [_("h3", null, h(s.value ? T(Y)(s.value) : "步骤详情"), 1), _("button", {
					type: "button",
					onClick: r[2] ||= (e) => s.value = void 0
				}, "关闭")]),
				s.value && C(s.value) ? (t(), D("p", Ie, h(C(s.value)), 1)) : l("", !0),
				s.value ? (t(), g(K, {
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
		}), ee = S(() => s.filter((e) => e.key !== "other" || w.value.other || u.value === "other")), E = S(() => u.value === "all" ? v.value : v.value.filter((e) => C(e) === u.value)), te = S(() => E.value.find((e) => String(e.id) === d.value)), k = m(), A = m(""), j, ne = S(() => {
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
		}), re = (e, t, n) => {
			let r = (t ? Date.parse(J(t)) : n ?? NaN) - Date.parse(J(e));
			return Number.isFinite(r) && r >= 0 ? I(r) : "";
		}, ie = S(() => re(i.batch?.started_at, i.batch?.completed_at)), ae = (e) => e.toLocaleString("zh-CN"), N = (e) => W(W(e.progress).failure), L = S(() => {
			let e = Date.now();
			return E.value.map((t) => {
				let n = C(t), r = n === "active" && x(t) !== "pending";
				return {
					job: t,
					tone: n,
					result: z(t, n),
					identity: [
						`#${t.id}`,
						t.email_source && i.sourceLabel(t.email_source),
						t.registration_driver && i.driverLabel(t.registration_driver),
						typeof t.retry_count == "number" && `人工重试 ${t.retry_count} 次`
					].filter(Boolean).join(" · "),
					elapsed: re(t.started_at, t.completed_at, r ? e : void 0),
					started: R(t.started_at),
					completed: R(t.completed_at)
				};
			});
		});
		function R(e) {
			if (!e || !Number.isFinite(Date.parse(e))) return null;
			let { text: t, secondary: n } = F(e);
			return {
				label: n ? `${t.slice(5)} ${n}` : t,
				full: n ? `${t} ${n}` : t
			};
		}
		function z(e, t) {
			if (t === "failed" || x(e) === "partial_success") {
				let t = e.error_info ? oe(W(e.error_info)) : "", n = J(N(e).label);
				return t && t !== "执行异常" ? t : n && Array.from(n).length <= 10 ? n : t || "执行异常";
			}
			return t === "active" ? J(W(W(e.progress).current).label) : "";
		}
		function V(e) {
			return e.debug_state === "paused" ? "调试暂停" : i.statusLabel(e.display_status || x(e));
		}
		function H(e) {
			let t = e.status_counts || {}, n = Number(t.running || 0) + Number(t.stopping || 0), r = Number(t.pending || 0), i = e.created_at ? P(e.created_at).replace(/:\d{2}$/, "") : String(e.batch_id), a = Number(t.partial_success || 0);
			return `${i} · ${n || r ? `运行 ${n} / 等待 ${r}` : [
				`成功 ${t.success || 0}`,
				...a ? [`部分 ${a}`] : [],
				`失败 ${t.failed || 0}`
			].join(" / ")}`;
		}
		function U(e) {
			u.value = e, d.value = null, g.value = !1, e === "failed" && E.value.length === 1 && (d.value = String(E.value[0].id), g.value = !0);
		}
		function G(e) {
			let t = String(e.id);
			d.value = d.value === t ? null : t, g.value = d.value !== null && C(e) === "failed";
		}
		function K() {
			j?.abort(), j = void 0, k.value = void 0, A.value = "";
		}
		let q = (e) => String(e?.operation_run_id ?? "");
		async function Y(e) {
			if (j || !i.active) return;
			let t = new AbortController();
			j = t, A.value = "";
			try {
				let n = await i.readProgress(e.id, t.signal);
				if (t.signal.aborted) return;
				if (!n.ok || !n.job || String(n.job.id) !== String(e.id) || !Array.isArray(W(n.job.progress).main_steps)) throw Error("阶段详情读取失败，请重试");
				if (q(e) && q(e) !== q(n.job)) throw Error("当前执行已更新，请刷新批次后重试");
				k.value = n.job;
			} catch (e) {
				!t.signal.aborted && !M(e) && (A.value = e instanceof Error ? e.message : "阶段详情读取失败，请重试");
			} finally {
				j === t && (j = void 0);
			}
		}
		return r(() => i.batchId, () => U("all")), r([
			() => i.active,
			() => i.batchId,
			te,
			() => i.refreshGeneration
		], ([e, t, n, r], [, a, o, s]) => {
			if (!e || !n) {
				K(), e && i.batch && d.value !== null && (d.value = null, g.value = !1);
				return;
			}
			let c = t !== a || String(n.id) !== String(o?.id) || q(n) !== q(o) || x(n) !== (o && x(o)), l = r !== s;
			(c || l) && K(), (c || l || !k.value && !A.value || C(n) === "active") && Y(n);
		}), y(K), (n, r) => (t(), D("section", {
			class: "registration-batch",
			"aria-labelledby": "registration-batch-title",
			"aria-busy": e.loading
		}, [
			_("header", ze, [_("div", null, [_("div", Be, [
				r[5] ||= _("h2", { id: "registration-batch-title" }, "任务批次进度", -1),
				e.batch ? (t(), D("span", {
					key: 0,
					class: "registration-state",
					"data-tone": ne.value.tone
				}, h(ne.value.label), 9, Ve)) : l("", !0),
				e.batch?.projection_delayed ? (t(), D("span", He, "进度同步中")) : l("", !0)
			]), e.batch ? (t(), D("p", Ue, [
				_("span", null, h(ae(e.batch.total ?? w.value.all)) + " 个任务", 1),
				e.batch.workers ? (t(), D("span", We, "并发 " + h(e.batch.workers), 1)) : l("", !0),
				ie.value ? (t(), D("span", Ge, "批次耗时 " + h(ie.value), 1)) : l("", !0)
			])) : l("", !0)]), b.value.length ? (t(), D("div", Ke, [
				_("select", {
					value: e.batchId,
					"aria-label": "选择任务批次",
					onChange: r[0] ||= (e) => o("select", e.target.value)
				}, [(t(!0), D(f, null, a(b.value, (e) => (t(), D("option", {
					key: String(e.batch_id),
					value: String(e.batch_id)
				}, h(H(e)), 9, Je))), 128))], 40, qe),
				e.actions.stopBatch ? (t(), D("button", {
					key: 0,
					type: "button",
					disabled: e.mutating,
					onClick: r[1] ||= (e) => o("batchAction", "stopBatch")
				}, "停止运行", 8, Ye)) : l("", !0),
				e.actions.cancelBatch ? (t(), D("button", {
					key: 1,
					type: "button",
					disabled: e.mutating,
					onClick: r[2] ||= (e) => o("batchAction", "cancelBatch")
				}, "取消排队", 8, Xe)) : l("", !0),
				e.actions.retryBatch ? (t(), D("button", {
					key: 2,
					type: "button",
					disabled: e.mutating,
					onClick: r[3] ||= (e) => o("batchAction", "retryBatch")
				}, "重跑失败", 8, Ze)) : l("", !0)
			])) : l("", !0)]),
			e.error ? (t(), D("div", Qe, [O(h(e.error) + " ", 1), _("button", {
				type: "button",
				onClick: r[4] ||= (e) => o("refresh")
			}, "刷新批次")])) : !e.batch || !v.value.length ? (t(), D("p", $e, h(e.loading ? "正在读取任务批次…" : "暂无注册任务批次"), 1)) : l("", !0),
			e.batch && w.value.all ? (t(), D(f, { key: 2 }, [
				_("div", et, [(t(!0), D(f, null, a(ee.value.slice(1), (e) => (t(), D("span", {
					key: e.key,
					"data-tone": e.key,
					style: p({ flexGrow: w.value[e.key] })
				}, null, 12, tt))), 128))]),
				_("div", nt, [(t(!0), D(f, null, a(ee.value, (e) => (t(), D("button", {
					key: e.key,
					type: "button",
					"data-batch-filter": e.key,
					"aria-pressed": u.value === e.key,
					onClick: (t) => U(e.key)
				}, [e.key === "all" ? l("", !0) : (t(), D("span", {
					key: 0,
					class: "registration-status-dot",
					"data-tone": e.key,
					"aria-hidden": "true"
				}, null, 8, it)), O(h(e.label) + " " + h(ae(w.value[e.key])), 1)], 8, rt))), 128))]),
				(t(!0), D(f, null, a(L.value, ({ job: n, tone: i, result: s, identity: u, elapsed: p, started: m, completed: v }) => (t(), D("article", {
					key: String(n.id),
					class: "registration-batch-card",
					"data-tone": i
				}, [_("div", ot, [
					_("div", st, [_("strong", null, h(n.email || (n.status === "pending" ? "等待执行…" : "准备邮箱中…")), 1), _("small", null, h(u), 1)]),
					_("div", ct, [_("span", {
						class: "registration-state",
						"data-tone": i
					}, h(V(n)), 9, lt), s ? (t(), D("small", ut, h(s), 1)) : l("", !0)]),
					p || m || v ? (t(), D("div", dt, [p ? (t(), D("strong", ft, "运行耗时 " + h(p), 1)) : l("", !0), _("div", pt, [m ? (t(), D("small", mt, [r[6] ||= O("开始 ", -1), _("time", {
						datetime: n.started_at || void 0,
						title: m.full
					}, h(m.label), 9, ht)])) : l("", !0), v ? (t(), D("small", gt, [r[7] ||= O("结束 ", -1), _("time", {
						datetime: n.completed_at || void 0,
						title: v.full
					}, h(v.label), 9, _t)])) : l("", !0)])])) : l("", !0),
					_("div", vt, [
						_("button", {
							type: "button",
							"aria-label": `查看阶段 · ${n.email || `任务 #${n.id}`}`,
							"aria-expanded": d.value === String(n.id),
							"aria-controls": `registration-stages-${n.id}`,
							onClick: (e) => G(n)
						}, "阶段", 8, yt),
						_("button", {
							type: "button",
							"aria-label": `查看日志 · ${n.email || `任务 #${n.id}`}`,
							onClick: (e) => o("log", n.id)
						}, "日志", 8, bt),
						n.retryable ? (t(), D("button", {
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
					"data-progress-state": d.value === String(n.id) ? A.value ? "error" : k.value ? "ready" : "loading" : void 0
				}, [d.value === String(n.id) ? (t(), D(f, { key: 0 }, [A.value ? (t(), D("p", Ct, [O(h(A.value) + " ", 1), _("button", {
					type: "button",
					onClick: (e) => Y(n)
				}, "重试读取", 8, wt)])) : k.value ? l("", !0) : (t(), D("p", Tt, "正在读取阶段详情…")), k.value ? (t(), D(f, { key: 2 }, [
					c(Le, {
						job: k.value,
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
					k.value.error_message ? (t(), D("details", Et, [r[8] ||= _("summary", null, "原始错误摘要", -1), _("p", null, h(k.value.error_message), 1)])) : l("", !0),
					T(B)(k.value.attempts).length || T(B)(k.value.route_attempts).length ? (t(), D("details", Dt, [
						r[9] ||= _("summary", null, "尝试与线路记录", -1),
						(t(!0), D(f, null, a(T(B)(k.value.attempts), (n) => (t(), D("p", { key: T(J)(n.id || n.attempt_id) }, h(e.statusLabel(n.status)) + " · " + h(n.error_message || "已记录"), 1))), 128)),
						(t(!0), D(f, null, a(T(B)(k.value.route_attempts), (n) => (t(), D("p", { key: T(J)(n.route_attempt_no) }, " 线路尝试 " + h(n.route_attempt_no || 1) + " · " + h(n.retry_reason || e.statusLabel(n.status)), 1))), 128))
					])) : l("", !0)
				], 64)) : l("", !0)], 64)) : l("", !0)], 8, St)], 8, at))), 128)),
				E.value.length ? l("", !0) : (t(), D("p", Ot, "没有符合条件的任务")),
				_("p", kt, "显示 " + h(ae(E.value.length)) + " 条任务", 1)
			], 64)) : l("", !0)
		], 8, Re));
	}
}), $ = (e, t = {}) => N(e, t, ue), jt = (e) => ({
	method: "POST",
	headers: { "Content-Type": "application/json" },
	body: JSON.stringify(e ?? {})
});
function Mt() {
	return {
		metadata: (e) => $("/api/email-sources", { signal: e }),
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
], It = 1e4, Lt = () => ({
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
}), Rt = (e) => e instanceof Error ? e.message : "请求失败", zt = (e) => e == null ? "" : String(e).trim(), Bt = (e) => encodeURIComponent(String(le(e))), Vt = () => ({
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
function Ht(e) {
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
		query: Lt(),
		batchId: "",
		batchRefreshGeneration: 0,
		statusCounts: {},
		facets: {},
		creating: !1,
		pendingActions: {},
		lastCreate: null,
		lastAction: null,
		detail: Vt(),
		metaError: ""
	}), c = S(() => o.creating), l = S(() => {
		let e = o.meta?.capabilities?.features?.register;
		return o.metaError ? o.metaError : o.meta ? e?.enabled === !0 ? "" : String(e?.reason || "注册资格未确认，请刷新后重试") : o.metaError || "注册资格未确认，请刷新后重试";
	}), u = (t) => e.notify?.(t), d = 0, f = 0, p = 0, h = 0, g = 0, _, v, b, x, C, w, ee, T, E = "", D = 0, O = 0, k = !0, A, j = /* @__PURE__ */ new Map(), ne = 0, re = () => !i && r.value && o.detail.id !== null, ie = (e, t) => re() && e === g && String(o.detail.id) === String(t);
	function ae() {
		d++, x?.controller.abort(), x = void 0, o.loading = !1;
	}
	function N() {
		ae(), p++, C?.controller.abort(), C = void 0, h++, w?.controller.abort(), w = void 0;
	}
	function oe() {
		window.clearInterval(_), window.clearInterval(v), _ = v = void 0;
	}
	function P() {
		if (!a.value || ne > 0) return !1;
		if (o.view === "tasks") return !0;
		let e = o.batch;
		return !e || String(e.batch_id) !== o.batchId || e.projection_delayed ? !0 : Nt.some((t) => Number(e.status_counts?.[t] || 0) > 0) || e.items.some((e) => Nt.includes(String(e.status || "")));
	}
	function F(e) {
		for (let t of Object.keys(Lt())) {
			let n = e[t];
			if (n !== void 0) {
				if (t === "page" || t === "page_size") {
					let e = Number(n);
					Number.isSafeInteger(e) && e > 0 && (o.query[t] = t === "page_size" ? Math.min(e, 500) : e);
				} else o.query[t] = String(n);
			}
		}
		if (e.progress_batch_id !== void 0) {
			let t = zt(e.progress_batch_id);
			t !== o.batchId && (o.batchId = t, o.batch = null);
		}
	}
	function I(e = {}) {
		if (F(e), !a.value || e.automatic && !P()) return Promise.resolve();
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
					s === "launch" && (a.progress_detail = 0), s === "tasks" && e.automatic && E === n && Date.now() - D < 3e4 && (a.include_facets = 0);
					let u = await t.jobs(a, i.signal);
					if (!l()) return;
					if (Object.prototype.hasOwnProperty.call(u, "status_counts") && (o.statusCounts = u.status_counts || {}), s === "launch") {
						o.batches = u.progress_batches || [];
						let e = u.progress_batch || null;
						if (!e && o.batchId) {
							let e = zt(o.batches[0]?.batch_id);
							if (e !== o.batchId && (o.batchId = e, o.batch = null, e && !r)) continue;
						}
						!o.batchId && e?.batch_id && (o.batchId = zt(e.batch_id)), o.batch = e, o.batchRefreshGeneration = c;
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
				l() && !M(e) && (o.error = Rt(e));
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
	function L(e) {
		return I({ progress_batch_id: zt(e) });
	}
	function R(e, n) {
		return t.progress(le(e), n);
	}
	function z(e) {
		return I({
			...e,
			page: e.page ?? 1
		});
	}
	function B(e) {
		return I({ page: e });
	}
	function V(e) {
		return I({
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
		C?.controller.abort();
		let e = ++p, n = new AbortController(), r = (async () => {
			try {
				let r = await t.summary(n.signal);
				e === p && a.value && H(r);
			} catch (t) {
				e === p && a.value && !M(t) && U({
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
	function G(e = !1) {
		if (w) return w.promise;
		if (e && (k = !0), !a.value || !k && o.meta && Date.now() - O < It) return Promise.resolve();
		let n = ++h, r = new AbortController(), i = (async () => {
			try {
				let e = await t.metadata(r.signal);
				if (n !== h || !a.value) return;
				o.meta = {
					...e,
					sources: Array.isArray(e.sources) ? e.sources : []
				}, o.metaError = "", O = Date.now(), k = !1;
			} catch (e) {
				if (n === h && a.value && !M(e)) {
					let t = Rt(e);
					o.metaError = /[\u3400-\u9fff]/.test(t) ? t : `邮箱来源读取失败，请稍后重试${t ? `（${t}）` : ""}`;
				}
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
	function K(e = !1) {
		oe(), a.value && (G(e), I({ coalesce: !0 }), W(), _ = window.setInterval(() => {
			I({ automatic: !0 });
		}, 5e3), v = window.setInterval(() => {
			C || W(), G(!0);
		}, 1e4));
	}
	function q(e) {
		n.value !== e && (n.value = e, e ? K(!0) : (oe(), N()));
	}
	function J(e) {
		["launch", "tasks"].includes(e) && o.view !== e && (o.view = e, ae(), I({ coalesce: !0 }));
	}
	function Y(e, t = "已受理") {
		let n = e.message || e.warning || (e.started_count == null ? e.deleted_count == null ? e.cancelled == null ? t : `已取消 ${e.cancelled} 个排队任务` : `已删除 ${e.deleted_count} 个任务` : `已提交 ${e.started_count} 个失败任务`), r = Array.isArray(e.skipped) ? e.skipped.length : 0;
		o.receipt = {
			tone: e.warning ? "warning" : "success",
			message: String(n) + (r ? `，跳过 ${r} 个` : "")
		}, u(o.receipt.message);
	}
	function se(e) {
		let t = zt(e.jobs?.[0]?.batch_id || e.job?.batch_id || e.batch_id);
		t && (o.batchId = t, o.batch = null);
	}
	function ce(e, n = {}) {
		let r = JSON.stringify([e, n]), i = j.get(r);
		if (i) return i;
		o.pendingActions[r] = !0, ne += 1, N();
		let a = (async () => {
			try {
				let r = await t.action(e, n);
				return o.lastAction = r, se(r), Y(r), /\/delete(?:-bulk)?$/.test(e) && o.detail.id !== null && (Array.isArray(r.deleted) ? r.deleted : r.deleted === !0 ? [e.split("/").at(-2)] : []).some((e) => String(e) === String(o.detail.id)) && he(), I(), o.detail.id !== null && Z(), r;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: Rt(e)
				}, u(o.receipt.message), e;
			} finally {
				j.delete(r), delete o.pendingActions[r];
			}
		})();
		return j.set(r, a), a;
	}
	function ue(e) {
		if (A) return A;
		if (l.value) {
			let e = l.value;
			return o.receipt = {
				tone: "warning",
				message: e
			}, u(e), Promise.reject(Error(e));
		}
		return !Number.isSafeInteger(e.count) || e.count < 1 || !Number.isSafeInteger(e.workers) || e.workers < 1 ? Promise.reject(/* @__PURE__ */ Error("注册数量与并发线程数必须为有效的正整数")) : (o.creating = !0, A = (async () => {
			try {
				let n = await t.create({ ...e });
				return o.lastCreate = n, se(n), Y(n, `已提交 ${n.submitted || 0} 个任务`), I(), n;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: Rt(e)
				}, u(o.receipt.message), e;
			} finally {
				o.creating = !1, A = void 0;
			}
		})(), A);
	}
	function X(e) {
		let t = o.batch?.items || [];
		return e === "stopBatch" ? t.filter((e) => e.status === "running" || e.status === "stopping") : e === "cancelBatch" ? t.filter((e) => e.status === "pending") : t.filter((e) => Ft.includes(String(e.status)) && e.retryable);
	}
	let de = S(() => ({
		stopBatch: !!o.batchId && X("stopBatch").length > 0,
		cancelBatch: !!o.batchId && X("cancelBatch").length > 0,
		retryBatch: X("retryBatch").length > 0
	}));
	async function fe(t, n, r = [], i = !1) {
		let a = t === "stopBatch" || t === "cancelBatch" || t === "retryBatch" ? X(t) : [], s = t === "retryBulk" || t === "deleteBulk" ? r.map((e) => le(e)) : a.map((e) => le(e.id));
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
		}, l = t === "retry" && n?.retry_action === "codex" ? "仅补跑 Codex 授权" : t === "retry" && n?.retry_action === "twofa" ? "重新登录检查并补齐 Authenticator 2FA" : t === "retry" && n?.retry_action === "registration_resume" ? "使用已保存账号密码继续邮箱验证" : "有原邮箱则复用，没有原邮箱则重新领取；已创建账号的任务按缺失步骤补跑，不能重试的由后端校验", d = t === "retry" || t === "retryBulk" || t === "retryBatch" ? `\n${l}。原任务记录和日志会保留。` : t === "stop" || t === "stopBatch" ? "\n任务会在当前步骤检查点退出。" : t === "cancelAll" || t === "cancelBatch" ? "\n运行中的任务不受影响。" : "", f = encodeURIComponent(o.batchId), p = n ? Bt(n.id) : "";
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
	function pe() {
		g++, ee?.abort(), T?.abort(), ee = T = void 0, window.clearTimeout(b), b = void 0, o.detail.loading = !1, o.detail.comparing = !1;
	}
	async function Z() {
		if (!re()) return;
		ee?.abort(), window.clearTimeout(b);
		let e = o.detail.id, n = ++g, r = new AbortController();
		ee = r, o.detail.loading = !0, o.detail.error = "";
		let i = () => ie(n, e);
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
			i() && !M(e) && (o.detail.error = Rt(e));
		} finally {
			i() && (o.detail.loading = !1, Pt.includes(String(o.detail.job?.status || "")) || (b = window.setTimeout(() => void Z(), 2e3)));
		}
	}
	function me(t, n) {
		let r = le(t), i = [...o.jobs, ...o.batch?.items || []].find((e) => String(e.id) === String(r));
		i?.operation_task_id && e.openTask ? e.openTask(i.operation_task_id, i.operation_run_id || null, n || null) : (pe(), o.detail = {
			...Vt(),
			id: r
		}, Z());
	}
	function he() {
		pe(), o.detail = Vt();
	}
	async function ge(e) {
		let n = le(e);
		if (!ie(g, n)) return null;
		T?.abort();
		let r = new AbortController();
		T = r;
		let i = () => re() && T === r && !r.signal.aborted && String(o.detail.id) === String(n);
		o.detail.comparing = !0, o.detail.compareError = "";
		try {
			let e = await t.compare(n, r.signal);
			return i() ? (o.detail.comparison = e, e) : null;
		} catch (e) {
			if (i() && !M(e)) throw o.detail.compareError = Rt(e), e;
			return null;
		} finally {
			i() && (o.detail.comparing = !1, T = void 0);
		}
	}
	function _e() {
		r.value = !document.hidden, r.value ? (K(!0), o.detail.id !== null && Z()) : (oe(), N(), pe());
	}
	function ve() {
		i = !0, oe(), N(), pe(), document.removeEventListener("visibilitychange", _e);
	}
	return document.addEventListener("visibilitychange", _e), te() && y(ve), {
		state: o,
		active: a,
		creating: c,
		registrationUnavailable: l,
		ensureMeta: G,
		load: I,
		loadSummary: W,
		renderEmailSupply: U,
		applySummary: H,
		setVisible: q,
		setView: J,
		setBatch: L,
		updateQuery: z,
		setPage: B,
		setSize: V,
		shouldPollJobs: P,
		create: ue,
		action: ce,
		executeAction: fe,
		compare: ge,
		openLog: me,
		refreshDetail: Z,
		closeDetail: he,
		notify: u,
		terminalStatuses: Pt,
		activeStatuses: Nt,
		batchActions: de,
		readBatchProgress: R,
		dispose: ve
	};
}
// src/features/registration/RegistrationPage.vue?vue&type=script&setup=true&lang.ts
var Ut = ["data-view"], Wt = { class: "registration-launch" }, Gt = {
	class: "registration-summary",
	"aria-label": "注册与本地邮箱概览"
}, Kt = {
	class: "registration-launch-panel",
	"aria-labelledby": "registration-launch-title"
}, qt = { class: "registration-launcher" }, Jt = ["disabled", "aria-describedby"], Yt = ["value"], Xt = { class: "registration-debug" }, Zt = ["disabled", "title"], Qt = { class: "registration-hint" }, $t = { id: "registrationEmailSupplyHint" }, en = { class: "ui-list registration-tasks" }, tn = { class: "ui-list-bulkbar registration-toolbar" }, nn = ["disabled"], rn = ["disabled"], an = {
	class: "ui-list-toolbar registration-count-row",
	"data-registration-count-row": ""
}, on = { class: "ui-list-toolbar__main registration-count-main" }, sn = { class: "ui-list-count registration-count" }, cn = { class: "ui-list-toolbar__actions registration-count-actions" }, ln = { class: "registration-mobile-filter" }, un = {
	key: 0,
	class: "ui-list-feedback is-error registration-list-error",
	role: "alert"
}, dn = {
	class: "ui-table-scroll registration-table-wrap",
	tabindex: "0",
	"aria-label": "注册任务列表，可横向滚动"
}, fn = { key: 2 }, pn = { class: "ui-col-check" }, mn = [
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], hn = { key: 0 }, gn = { class: "registration-row-actions" }, _n = ["onClick"], vn = ["onUpdate:modelValue"], yn = ["onClick"], bn = ["onClick"], xn = ["onClick"], Sn = ["disabled", "onClick"], Cn = { id: "registration-log-title" }, wn = { key: 0 }, Tn = {
	key: 1,
	role: "alert"
}, En = { key: 2 }, Dn = ["disabled"], On = ["href"], kn = { key: 0 }, An = {
	key: 1,
	role: "alert"
}, jn = { key: 3 }, Mn = ["href"], Nn = /* @__PURE__ */ e({
	__name: "RegistrationPage",
	props: { deps: {} },
	setup(e, { expose: s }) {
		let d = e, y = Ht(d.deps), { state: C } = y, E = re({
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
		function te() {
			E.resetColumns(), d.deps.notify?.("已恢复默认列宽");
		}
		let k = [
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
		], M = m();
		se(M, () => C.detail.id !== null, () => y.active.value);
		let N = m(1), P = m(3), F = m(""), I = m(!1), L = m(""), R = m(""), z = m(""), B = m(""), V = m(""), H = m(""), U = m(""), W = m(""), G = m(1), K = m(20), q = m(/* @__PURE__ */ new Set()), J = m({}), Y = S(() => C.view === "launch"), le = S(() => C.view === "tasks"), ue = S(() => C.jobs), X = m(null), de = S(() => ({
			id: R.value,
			email: z.value,
			email_source: B.value,
			status: L.value,
			proxy: V.value,
			error: H.value,
			date_from: U.value,
			date_to: W.value
		})), fe = {
			id: "ID",
			email: "邮箱",
			email_source: "邮箱来源",
			status: "状态",
			proxy: "代理",
			error: "错误",
			date_from: "开始日期",
			date_to: "截止日期"
		}, pe = S(() => Object.entries(de.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${fe[e]}：${e === "status" ? ke(t) : e === "email_source" ? Oe(t) : t}`,
			removeLabel: `清除${fe[e]}筛选`
		})));
		function Z(e, t) {
			let n = {
				id: R,
				email: z,
				email_source: B,
				status: L,
				proxy: V,
				error: H,
				date_from: U,
				date_to: W
			};
			n[e].value = t, X.value = null, Ie();
		}
		let me = (e) => e.error_info ? oe(e.error_info) : e.error_message ? "执行异常" : "—", he = S(() => C.statusCounts.active ?? [
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
			return B.value && !e.has(B.value) && e.set(B.value, {
				value: B.value,
				label: B.value
			}), [...e.values()];
		}), be = S(() => ge.value ? [{
			value: "manual",
			label: "手动配置邮箱"
		}] : C.meta?.sources?.filter((e) => e.enabled === !0) || []), xe = S(() => C.metaError || C.meta && (y.registrationUnavailable.value || (be.value.length ? "" : "没有可用的邮箱来源。请先导入本地邮箱，再重新选择。")) || ""), Se = S(() => xe.value || C.metaError || (C.meta ? ge.value ? "使用手动配置的邮箱来源。" : F.value ? "" : "请选择本批使用的邮箱来源。" : "正在读取邮箱来源…")), Ce = S(() => C.summary?.email_supply || {}), we = (e) => {
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
			let t = M.value;
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
			let e = Number(N.value), t = Number(P.value);
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
			if (!be.value.some((e) => e.value === F.value)) {
				C.receipt = {
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
				if (he.value > 0 && !await Ae(`当前任务表里已有 ${he.value} 个任务在跑或排队，这次会再加 ${e} 个，确定继续？`)) return;
				let t = await y.create(n);
				Number.isSafeInteger(t?.workers) && t.workers > 0 && (P.value = t.workers);
			} catch {} finally {
				_e.value = !1;
			}
		}
		async function Q(e, t) {
			let n = Array.from(q.value);
			try {
				await y.executeAction(e, t, n, I.value), (e === "deleteBulk" || e === "retryBulk") && (q.value = /* @__PURE__ */ new Set());
			} catch {}
		}
		function Fe() {
			L.value = R.value = z.value = B.value = V.value = H.value = U.value = W.value = "", G.value = 1, y.load(Ve());
		}
		function Ie() {
			G.value = 1, y.load(Ve());
		}
		function Le(e) {
			let t = e.target.checked;
			ue.value.filter((e) => !["running", "stopping"].includes(String(e.status))).forEach((e) => t ? q.value.add(String(e.id)) : q.value.delete(String(e.id))), q.value = new Set(q.value);
		}
		function Re(e, t) {
			let n = new Set(q.value);
			t.target.checked ? n.add(String(e)) : n.delete(String(e)), q.value = n;
		}
		function ze(e) {
			return [
				e.proxy_provider,
				e.proxy_endpoint && e.proxy_endpoint !== "-" ? e.proxy_endpoint : "",
				e.proxy_region && e.proxy_region !== "-" ? e.proxy_region : ""
			].filter(Boolean).join(" · ") || "-";
		}
		function Be(e) {
			G.value = 1, y.setBatch(e);
		}
		function Ve() {
			return {
				status: L.value,
				id: R.value,
				email: z.value,
				email_source: B.value,
				proxy: V.value,
				error: H.value,
				date_from: U.value,
				date_to: W.value,
				page: G.value,
				page_size: K.value
			};
		}
		function He(e) {
			let t = String(J.value[String(e.id)] || "").trim();
			t ? y.action("/api/manual-otp", {
				email: e.email,
				code: t,
				job_id: e.id
			}).then(() => {
				J.value = {
					...J.value,
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
			G.value = e.page, K.value = e.page_size, R.value = e.id, z.value = e.email, B.value = e.email_source, L.value = e.status, V.value = e.proxy, H.value = e.error, U.value = e.date_from, W.value = e.date_to;
		}, { immediate: !0 }), r([ge, be], () => {
			ge.value ? F.value = "manual" : be.value.some((e) => e.value === F.value) || (F.value = "");
		}, { immediate: !0 }), o(() => {
			y.ensureMeta();
		}), (e, r) => (t(), D("div", {
			class: "registration-vue-page",
			"data-view": T(C).view
		}, [
			i(_("section", Wt, [
				_("dl", Gt, [(t(!0), D(f, null, a(Ee.value, (e) => (t(), D("div", { key: e.label }, [_("dt", null, h(e.label), 1), _("dd", null, h(typeof e.value == "number" ? e.value.toLocaleString("zh-CN") : e.value), 1)]))), 128))]),
				_("section", Kt, [r[24] ||= _("h2", { id: "registration-launch-title" }, "新建注册批次", -1), _("form", {
					novalidate: "",
					onSubmit: b(Pe, ["prevent"])
				}, [_("div", qt, [
					_("label", null, [r[20] ||= O("邮箱来源 ", -1), i(_("select", {
						"onUpdate:modelValue": r[0] ||= (e) => F.value = e,
						disabled: !T(C).meta || ge.value || !be.value.length,
						"aria-describedby": Se.value ? "registration-launch-hint registrationEmailSupplyHint" : "registrationEmailSupplyHint"
					}, [r[19] ||= _("option", { value: "" }, "请选择本次邮箱来源", -1), (t(!0), D(f, null, a(be.value, (e) => (t(), D("option", {
						key: String(e.value),
						value: String(e.value)
					}, h(e.label || e.value), 9, Yt))), 128))], 8, Jt), [[u, F.value]])]),
					_("label", null, [r[21] ||= O("注册数量", -1), i(_("input", {
						"onUpdate:modelValue": r[1] ||= (e) => N.value = e,
						min: "1",
						type: "number",
						inputmode: "numeric"
					}, null, 512), [[
						w,
						N.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", null, [r[22] ||= O("并发线程", -1), i(_("input", {
						"onUpdate:modelValue": r[2] ||= (e) => P.value = e,
						min: "1",
						step: "1",
						type: "number",
						inputmode: "numeric"
					}, null, 512), [[
						w,
						P.value,
						void 0,
						{ number: !0 }
					]])]),
					_("label", Xt, [i(_("input", {
						"onUpdate:modelValue": r[3] ||= (e) => I.value = e,
						type: "checkbox"
					}, null, 512), [[v, I.value]]), r[23] ||= O(" 调试模式", -1)]),
					_("button", {
						type: "submit",
						class: "registration-start",
						disabled: T(C).creating || _e.value || !F.value || !!xe.value,
						title: xe.value || void 0
					}, h(T(C).creating ? "提交中…" : "开始注册"), 9, Zt)
				]), _("p", Qt, [
					Se.value ? (t(), D("span", {
						key: 0,
						id: "registration-launch-hint",
						class: x({ "registration-warning": xe.value }),
						role: "status"
					}, h(Se.value), 3)) : l("", !0),
					T(C).metaError ? (t(), D("button", {
						key: 1,
						type: "button",
						class: "ui-link",
						"data-registration-source-retry": "",
						onClick: r[4] ||= (e) => T(y).ensureMeta(!0)
					}, "重试")) : l("", !0),
					_("span", $t, h(Te.value), 1)
				])], 32)]),
				Y.value ? (t(), g(At, {
					key: 0,
					batch: T(C).batch,
					batches: T(C).batches,
					"batch-id": T(C).batchId,
					"refresh-generation": T(C).batchRefreshGeneration,
					active: T(y).active.value,
					loading: T(C).loading,
					error: T(C).error,
					actions: T(y).batchActions.value,
					mutating: Object.keys(T(C).pendingActions).length > 0,
					"status-label": ke,
					"source-label": Oe,
					"driver-label": De,
					"read-progress": T(y).readBatchProgress,
					onSelect: Be,
					onRefresh: r[5] ||= (e) => T(y).load(),
					onBatchAction: r[6] ||= (e) => Q(e),
					onRetry: r[7] ||= (e) => Q("retry", e),
					onLog: T(y).openLog
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
			], 512), [[ee, Y.value]]),
			i(_("section", en, [
				_("div", tn, [
					_("button", {
						type: "button",
						class: "ui-button",
						onClick: r[8] ||= (e) => Q("retryBulk"),
						disabled: !q.value.size
					}, "重试", 8, nn),
					_("button", {
						type: "button",
						class: "ui-button ui-button--danger",
						onClick: r[9] ||= (e) => Q("deleteBulk"),
						disabled: !q.value.size
					}, "删除", 8, rn),
					_("button", {
						type: "button",
						class: "ui-button",
						onClick: r[10] ||= (e) => Q("cancelAll")
					}, "取消排队"),
					_("button", {
						type: "button",
						class: "ui-button",
						onClick: Ie
					}, "刷新")
				]),
				_("div", an, [_("div", on, [_("span", sn, "共 " + h(T(C).total.toLocaleString()) + " 条任务", 1), c(ne, {
					items: pe.value,
					onRemove: r[11] ||= (e) => Z(e, "")
				}, null, 8, ["items"])]), _("div", cn, [
					_("button", {
						type: "button",
						class: "ui-link",
						"aria-label": "恢复注册任务列宽",
						onClick: te
					}, "恢复列宽"),
					_("span", ln, [c(ve, {
						values: de.value,
						sources: ye.value,
						open: X.value === "all",
						"onUpdate:open": r[12] ||= (e) => X.value = e ? "all" : null,
						onChange: Z
					}, null, 8, [
						"values",
						"sources",
						"open"
					])]),
					pe.value.length ? (t(), D("button", {
						key: 0,
						type: "button",
						onClick: Fe
					}, "清筛")) : l("", !0)
				])]),
				T(C).error ? (t(), D("div", un, [O(h(T(C).error) + " ", 1), _("button", {
					type: "button",
					class: "ui-link",
					onClick: Ie
				}, "重试")])) : l("", !0),
				_("div", dn, [_("table", {
					class: "ui-table ui-table--sticky-end registration-table",
					style: p({ "--ui-table-width": `${T(E).total.value}px` })
				}, [
					_("colgroup", null, [(t(!0), D(f, null, a(T(E).widths.value, (e, n) => (t(), D("col", {
						key: n,
						style: p({ width: `${e}px` })
					}, null, 4))), 128))]),
					_("thead", null, [_("tr", null, [(t(), D(f, null, a(k, (e, n) => _("th", {
						key: e.label,
						class: x({ "ui-col-check": n === 0 })
					}, [n === 0 ? (t(), D("input", {
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
						onChange: Z
					}, null, 8, [
						"column",
						"values",
						"sources",
						"open",
						"onUpdate:open"
					])) : (t(), D("span", fn, h(e.label), 1)), n < k.length - 1 ? (t(), g(ie, {
						key: 3,
						label: e.label,
						onStart: (e) => T(E).resize(n, e),
						onNudge: (e) => T(E).resizeWithKeyboard(n, e)
					}, null, 8, [
						"label",
						"onStart",
						"onNudge"
					])) : l("", !0)], 2)), 64))])]),
					_("tbody", null, [T(C).loading || !ue.value.length ? (t(), g(A, {
						key: 0,
						colspan: 11,
						loading: T(C).loading,
						"loading-title": "正在加载任务…",
						title: "暂无匹配任务"
					}, null, 8, ["loading"])) : l("", !0), (t(!0), D(f, null, a(ue.value, (e) => (t(), D("tr", {
						key: String(e.id),
						class: x({ "is-selected": q.value.has(String(e.id)) })
					}, [
						_("td", pn, [_("input", {
							type: "checkbox",
							"aria-label": `选择任务 ${e.id}`,
							checked: q.value.has(String(e.id)),
							disabled: ["running", "stopping"].includes(String(e.status)),
							onChange: (t) => Re(e.id, t)
						}, null, 40, mn)]),
						_("td", null, [c(j, {
							text: `#${e.id}`,
							secondary: e.parent_job_id ? `↳ #${e.parent_job_id}` : void 0
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(j, { text: String(e.email || "-") }, null, 8, ["text"])]),
						_("td", null, [c(j, { text: Oe(e.email_source) }, null, 8, ["text"])]),
						_("td", null, [c(j, { text: De(e.registration_driver) }, null, 8, ["text"])]),
						_("td", null, [c(j, {
							text: ze(e),
							secondary: String(e.proxy_status || "")
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(j, { text: ke(e.debug_state === "paused" ? "debug_paused" : e.display_status || e.status) }, null, 8, ["text"])]),
						_("td", null, [c(j, { text: String(e.started_at || "-") }, null, 8, ["text"])]),
						_("td", null, [c(j, { text: String(e.completed_at || "-") }, null, 8, ["text"])]),
						_("td", null, [e.error_message || e.error_info ? (t(), g(ae, {
							key: 0,
							"data-registration-result": "",
							label: me(e),
							title: String(e.error_message || me(e)),
							tone: "danger"
						}, {
							details: n(() => [_("p", null, h(e.error_message || me(e)), 1), e.error_info ? (t(), D("p", hn, h(e.error_info), 1)) : l("", !0)]),
							_: 2
						}, 1032, ["label", "title"])) : (t(), g(j, {
							key: 1,
							text: "—"
						}))]),
						_("td", gn, [
							_("button", {
								type: "button",
								class: "ui-link",
								onClick: (t) => T(y).openLog(e.id)
							}, "日志", 8, _n),
							e.manual_otp_required && e.status === "running" ? (t(), D(f, { key: 0 }, [i(_("input", {
								"onUpdate:modelValue": (t) => J.value[String(e.id)] = t,
								placeholder: "邮箱验证码"
							}, null, 8, vn), [[w, J.value[String(e.id)]]]), _("button", {
								type: "button",
								onClick: (t) => He(e)
							}, "提交验证码", 8, yn)], 64)) : l("", !0),
							[
								"pending",
								"running",
								"stopping"
							].includes(String(e.status)) ? (t(), D("button", {
								key: 1,
								type: "button",
								onClick: (t) => Q("stop", e)
							}, "停止", 8, bn)) : l("", !0),
							e.retryable ? (t(), D("button", {
								key: 2,
								type: "button",
								onClick: (t) => Q("retry", e)
							}, "重试", 8, xn)) : l("", !0),
							_("button", {
								type: "button",
								disabled: ["running", "stopping"].includes(String(e.status)),
								onClick: (t) => Q("delete", e)
							}, "删除", 8, Sn)
						])
					], 2))), 128))])
				], 4)]),
				c(ce, {
					label: "注册任务分页",
					page: G.value,
					size: K.value,
					total: T(C).total,
					busy: T(C).loading,
					"onUpdate:page": r[13] ||= (e) => {
						G.value = e, T(y).load(Ve());
					},
					"onUpdate:size": r[14] ||= (e) => {
						K.value = e, G.value = 1, T(y).load(Ve());
					}
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			], 512), [[ee, le.value]]),
			T(C).receipt ? (t(), D("div", {
				key: 0,
				class: x(["registration-receipt", `is-${T(C).receipt.tone}`]),
				role: "status"
			}, h(T(C).receipt.message), 3)) : l("", !0),
			_("dialog", {
				ref_key: "logDialog",
				ref: M,
				class: "registration-dialog",
				"aria-labelledby": "registration-log-title",
				onCancel: r[17] ||= b((...e) => T(y).closeDetail && T(y).closeDetail(...e), ["prevent"]),
				onClose: r[18] ||= (...e) => T(y).closeDetail && T(y).closeDetail(...e),
				onClick: Ne
			}, [
				_("header", null, [_("h2", Cn, "任务 #" + h(T(C).detail.id) + " 日志", 1), _("button", {
					type: "button",
					onClick: r[15] ||= (...e) => T(y).closeDetail && T(y).closeDetail(...e)
				}, "关闭")]),
				T(C).detail.loading ? (t(), D("p", wn, "加载中…")) : l("", !0),
				T(C).detail.error ? (t(), D("p", Tn, h(T(C).detail.error), 1)) : l("", !0),
				_("pre", null, h(T(C).detail.log || "（暂无日志）"), 1),
				T(C).detail.debug?.enabled ? (t(), D("div", En, [
					r[25] ||= _("strong", null, "网络调试", -1),
					_("button", {
						type: "button",
						disabled: T(C).detail.comparing,
						onClick: Ue
					}, "与同批成功任务对比", 8, Dn),
					_("a", {
						href: `/api/jobs/${T(C).detail.id}/debug/har`,
						download: ""
					}, "下载脱敏 HAR", 8, On),
					_("button", {
						type: "button",
						onClick: r[16] ||= (e) => T(y).action(`/api/jobs/${T(C).detail.id}/debug/release`, { action: "finish" })
					}, "结束调试并收口"),
					T(C).detail.comparison ? (t(), D("pre", kn, h(T(C).detail.comparison), 1)) : l("", !0),
					T(C).detail.compareError ? (t(), D("p", An, h(T(C).detail.compareError), 1)) : l("", !0)
				])) : l("", !0),
				T(C).detail.diagnostics?.captured ? (t(), D("div", jn, [
					r[27] ||= _("strong", null, "失败诊断", -1),
					T(C).detail.diagnostics.screenshot_url ? (t(), D("a", {
						key: 0,
						href: String(T(C).detail.diagnostics.screenshot_url),
						target: "_blank",
						rel: "noopener"
					}, "打开失败截图", 8, Mn)) : l("", !0),
					_("details", null, [r[26] ||= _("summary", null, "完整诊断证据", -1), _("pre", null, h(T(C).detail.diagnostics), 1)])
				])) : l("", !0)
			], 544)
		], 8, Ut));
	}
});
// src/registration.ts
function Pn(e, t = {}) {
	let n = C(Nn, { deps: {
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
export { Pn as mountRegistration };
