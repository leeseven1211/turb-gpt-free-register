import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, S as c, _ as l, a as u, c as d, d as f, dt as p, et as m, ft as h, g, h as _, i as v, j as y, l as b, lt as x, m as S, n as C, o as w, s as ee, st as T, t as E, v as D, w as te, x as O } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { n as k, r as A, t as j } from "./ListFilterSummary-0POqp2Om.js";
import { t as ne } from "./useColumnWidths-CUEzVga1.js";
import { t as re } from "./ListResult-ChGvCNvJ.js";
import { n as M, r as N } from "./client-B5R_MNgP.js";
import { t as ie } from "./errorLabels-C0VIFLD8.js";
import { n as P, t as ae } from "./time-DOD6oyhP.js";
import { O as F, _ as I, a as L, b as R, g as z, h as B, i as V, n as H, p as U, r as W, t as G, v as K, x as q, y as J } from "./StepEvidence-7ocHKXmA.js";
import { t as Y } from "./useNativeDialog-BgHdu813.js";
import { t as oe } from "./ListPagination-DDdERjeb.js";
import { a as se, r as ce } from "./taskIds-BlchWwUp.js";
// src/features/registration/RegistrationFilters.vue?vue&type=script&setup=true&lang.ts
var le = { class: "registration-filter-fields" }, X = { key: 0 }, ue = ["value"], de = ["value", "aria-label"], fe = ["value"], Z = ["value"], pe = ["value"], me = [
	"type",
	"value",
	"aria-label"
], he = { class: "list-filter-actions" }, ge = /*#__PURE__*/ E(/* @__PURE__ */ e({
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
			default: n(() => [_("div", le, [
				e.column ? l("", !0) : (t(), D("label", X, [s[8] ||= O("筛选列", -1), i(_("select", {
					"onUpdate:modelValue": s[0] ||= (e) => p.value = e,
					"aria-label": "选择注册任务筛选列"
				}, [(t(), D(f, null, a(o, (e, t) => _("option", {
					key: t,
					value: t
				}, h(e), 9, ue)), 64))], 512), [[u, p.value]])])),
				_("label", null, [O(h(o[v.value]) + " ", 1), v.value === "email_source" ? (t(), D("select", {
					key: 0,
					value: y.value,
					"aria-label": `筛选${o[v.value]}值`,
					onChange: s[1] ||= (e) => C(e.target.value)
				}, [s[9] ||= _("option", { value: "" }, "全部邮箱来源", -1), (t(!0), D(f, null, a(e.sources, (e) => (t(), D("option", {
					key: e.value,
					value: e.value
				}, h(e.label || e.value), 9, fe))), 128))], 40, de)) : v.value === "status" ? (t(), D("select", {
					key: 1,
					value: y.value,
					"aria-label": "筛选状态值",
					onChange: s[2] ||= (e) => C(e.target.value)
				}, [s[10] ||= _("option", { value: "" }, "全部状态", -1), (t(!0), D(f, null, a(b.value, (e) => (t(), D("option", {
					key: e,
					value: e
				}, h(x(e)), 9, pe))), 128))], 40, Z)) : (t(), D("input", {
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
}), [["__scopeId", "data-v-e4a53bb8"]]), _e = { class: "registration-progress" }, ve = {
	key: 0,
	class: "registration-stage-heading"
}, ye = { key: 0 }, be = {
	key: 1,
	class: "registration-steps",
	"aria-label": "注册执行阶段，排列不代表固定顺序"
}, xe = [
	"title",
	"aria-pressed",
	"onClick"
], Se = {
	key: 0,
	class: "registration-step-mark",
	"aria-hidden": "true"
}, Ce = {
	key: 1,
	class: "registration-step-mark",
	"aria-hidden": "true"
}, we = { "data-registration-step-duration": "" }, Te = { key: 0 }, Ee = ["aria-label", "onClick"], De = {
	key: 2,
	class: "registration-stage-selected"
}, Oe = { "aria-live": "polite" }, ke = { key: 0 }, Ae = { key: 1 }, je = { class: "registration-batch-actions" }, Me = ["aria-label"], Ne = {
	key: 3,
	class: "registration-step-note"
}, Q = { key: 4 }, Pe = { key: 0 }, Fe = /* @__PURE__ */ e({
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
		Y(u, () => !!s.value && r.active, () => r.active);
		let y = (e) => F(I(e));
		function C(e) {
			let t = U(e.debug_pause);
			return t.state === "paused" ? `调试暂停 · 等待结束调试${t.paused_at ? ` · 暂停于 ${P(t.paused_at)}` : " · 暂停时间未记录"}${t.hold_until ? ` · 保留至 ${P(t.hold_until)}` : ""}` : "";
		}
		function w(e) {
			let t = e.attempts || [], n = e.children || [], i = (e) => e.raw_stage_label || n.find((t) => t.id === e.raw_stage)?.label || e.raw_stage || "阶段", a = [...new Set(t.map(i))];
			return [
				`${J(e)} · ${V(e)}`,
				C(e),
				e.reason || e.message || "",
				`开始：${P(e.started_at)}`,
				`结束：${P(e.completed_at)}`,
				`耗时：${y(e)}`,
				a.length ? `已记录阶段：${a.join("、")}` : "",
				n.length ? `子步骤（${n.length}）` : "",
				...n.map((e) => `${J(e)} · ${V(e)} · ${y(e)}${e.reason || e.message ? `\n${e.reason || e.message}` : ""}`),
				t.length ? `阶段事件（${t.length} 条）` : "",
				...t.map((e, t) => `${t + 1}. ${i(e)} · ${B(e.display_status || e.state)}${e.created_at ? ` · ${P(e.created_at)}` : e.event_time_known === !1 ? " · 发生时间未记录" : ""}${e.message ? `\n${e.message}` : ""}`),
				r.inline ? "点击步骤查看阶段摘要" : "点击步骤查看对应日志"
			].filter(Boolean).join("\n");
		}
		return (n, r) => (t(), D("div", _e, [
			o.value.length ? (t(), D("div", ve, [e.inline ? (t(), D("h3", ye, "执行阶段")) : l("", !0), r[5] ||= _("p", { class: "registration-step-note" }, "按首次记录排列，不代表固定执行顺序", -1)])) : l("", !0),
			o.value.length ? (t(), D("ul", be, [(t(!0), D(f, null, a(o.value, (n) => (t(), D("li", {
				key: T(K)(n),
				class: x([`is-${T(R)(n)}`, { "is-inspected": p.value === n }])
			}, [_("button", {
				type: "button",
				title: w(n),
				"aria-pressed": e.inline ? p.value === n : void 0,
				onClick: (e) => v(n)
			}, [
				_("strong", null, [T(R)(n) === "success" ? (t(), D("span", Se, "✓")) : T(R)(n) === "failed" ? (t(), D("span", Ce, "!")) : l("", !0), O(" " + h(T(J)(n)), 1)]),
				_("small", null, h(T(V)(n)), 1),
				_("small", we, "耗时 " + h(y(n)), 1),
				(t(!0), D(f, null, a(T(W)(n), (e) => (t(), D("small", { key: e }, h(e), 1))), 128)),
				C(n) ? (t(), D("small", Te, h(C(n)), 1)) : l("", !0)
			], 8, xe), e.inline ? l("", !0) : (t(), D("button", {
				key: 0,
				type: "button",
				"aria-label": `查看${T(J)(n)}的关系与证据`,
				onClick: (e) => s.value = n
			}, "详情", 8, Ee))], 2))), 128))])) : l("", !0),
			p.value ? (t(), D("div", De, [_("div", Oe, [
				_("strong", null, h(T(J)(p.value)), 1),
				_("span", null, " · " + h(T(V)(p.value)), 1),
				p.value.reason || p.value.message ? (t(), D("p", ke, h(p.value.reason || p.value.message), 1)) : e.focusFailure && T(K)(p.value) === T(U)(e.job.progress?.failure).step_id && T(U)(e.job.progress?.failure).message ? (t(), D("p", Ae, h(T(U)(e.job.progress?.failure).message), 1)) : l("", !0)
			]), _("div", je, [_("button", {
				type: "button",
				"aria-label": `查看${T(J)(p.value)}的关系与证据`,
				onClick: r[0] ||= (e) => s.value = p.value
			}, "阶段详情", 8, Me), _("button", {
				type: "button",
				onClick: r[1] ||= (e) => i("log", T(K)(p.value))
			}, "阶段日志")])])) : o.value.length ? l("", !0) : (t(), D("p", Ne, "暂无阶段记录，可查看任务日志。")),
			o.value.length ? (t(), D("details", Q, [r[6] ||= _("summary", null, "依赖与执行记录", -1), (t(!0), D(f, null, a(o.value, (e) => (t(), D("div", { key: T(K)(e) }, [_("strong", null, h(T(J)(e)), 1), c(H, {
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
				_("header", null, [_("h3", null, h(s.value ? T(J)(s.value) : "步骤详情"), 1), _("button", {
					type: "button",
					onClick: r[2] ||= (e) => s.value = void 0
				}, "关闭")]),
				s.value && C(s.value) ? (t(), D("p", Pe, h(C(s.value)), 1)) : l("", !0),
				s.value ? (t(), g(G, {
					key: 1,
					step: s.value,
					siblings: o.value
				}, null, 8, ["step", "siblings"])) : l("", !0)
			], 544)
		]));
	}
}), Ie = ["aria-busy"], Le = { class: "registration-batch-header" }, Re = { class: "registration-batch-title" }, ze = ["data-tone"], Be = {
	key: 1,
	class: "registration-hint"
}, Ve = {
	key: 0,
	class: "registration-hint registration-batch-meta"
}, He = { key: 0 }, Ue = { key: 1 }, We = {
	key: 0,
	class: "registration-batch-actions"
}, Ge = ["value"], Ke = ["value"], qe = ["disabled"], Je = ["disabled"], Ye = ["disabled"], Xe = {
	key: 0,
	class: "registration-batch-notice",
	role: "alert"
}, Ze = {
	key: 1,
	class: "registration-batch-notice"
}, Qe = {
	class: "registration-batch-meter",
	"aria-hidden": "true"
}, $e = ["data-tone"], et = {
	class: "registration-batch-filters",
	role: "group",
	"aria-label": "按批次任务状态筛选"
}, tt = [
	"data-batch-filter",
	"aria-pressed",
	"onClick"
], nt = ["data-tone"], rt = ["data-tone"], it = { class: "registration-batch-row" }, at = { class: "registration-batch-identity" }, ot = { class: "registration-batch-result" }, st = ["data-tone"], ct = { key: 0 }, lt = {
	key: 0,
	class: "registration-batch-timing"
}, ut = { key: 0 }, dt = { class: "registration-batch-dates" }, ft = { key: 0 }, pt = ["datetime", "title"], mt = { key: 1 }, ht = ["datetime", "title"], gt = { class: "registration-batch-actions registration-batch-row-actions" }, _t = [
	"aria-label",
	"aria-expanded",
	"aria-controls",
	"onClick"
], vt = ["aria-label", "onClick"], yt = ["disabled", "onClick"], bt = [
	"id",
	"hidden",
	"data-progress-state"
], xt = {
	key: 0,
	class: "registration-step-note",
	role: "alert"
}, St = ["onClick"], Ct = {
	key: 1,
	class: "registration-step-note",
	role: "status"
}, wt = { key: 0 }, Tt = { key: 1 }, Et = {
	key: 0,
	class: "registration-batch-notice"
}, Dt = {
	class: "registration-batch-footer registration-hint",
	"aria-live": "polite"
}, Ot = /* @__PURE__ */ e({
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
			let r = (t ? Date.parse(q(t)) : n ?? NaN) - Date.parse(q(e));
			return Number.isFinite(r) && r >= 0 ? F(r) : "";
		}, N = S(() => re(i.batch?.started_at, i.batch?.completed_at)), I = (e) => e.toLocaleString("zh-CN"), L = (e) => U(U(e.progress).failure), R = S(() => {
			let e = Date.now();
			return E.value.map((t) => {
				let n = C(t), r = n === "active" && x(t) !== "pending";
				return {
					job: t,
					tone: n,
					result: V(t, n),
					identity: [
						`#${t.id}`,
						t.email_source && i.sourceLabel(t.email_source),
						t.registration_driver && i.driverLabel(t.registration_driver),
						typeof t.retry_count == "number" && `人工重试 ${t.retry_count} 次`
					].filter(Boolean).join(" · "),
					elapsed: re(t.started_at, t.completed_at, r ? e : void 0),
					started: B(t.started_at),
					completed: B(t.completed_at)
				};
			});
		});
		function B(e) {
			if (!e || !Number.isFinite(Date.parse(e))) return null;
			let { text: t, secondary: n } = ae(e);
			return {
				label: n ? `${t.slice(5)} ${n}` : t,
				full: n ? `${t} ${n}` : t
			};
		}
		function V(e, t) {
			if (t === "failed" || x(e) === "partial_success") {
				let t = e.error_info ? ie(U(e.error_info)) : "", n = q(L(e).label);
				return t && t !== "执行异常" ? t : n && Array.from(n).length <= 10 ? n : t || "执行异常";
			}
			return t === "active" ? q(U(U(e.progress).current).label) : "";
		}
		function H(e) {
			return e.debug_state === "paused" ? "调试暂停" : i.statusLabel(e.display_status || x(e));
		}
		function W(e) {
			let t = e.status_counts || {}, n = Number(t.running || 0) + Number(t.stopping || 0), r = Number(t.pending || 0);
			return `${e.created_at ? P(e.created_at).replace(/:\d{2}$/, "") : String(e.batch_id)} · ${n || r ? `运行 ${n} / 等待 ${r}` : `成功 ${t.success || 0} / 失败 ${t.failed || 0}`}`;
		}
		function G(e) {
			u.value = e, d.value = null, g.value = !1, e === "failed" && E.value.length === 1 && (d.value = String(E.value[0].id), g.value = !0);
		}
		function K(e) {
			let t = String(e.id);
			d.value = d.value === t ? null : t, g.value = d.value !== null && C(e) === "failed";
		}
		function J() {
			j?.abort(), j = void 0, k.value = void 0, A.value = "";
		}
		let Y = (e) => String(e?.operation_run_id ?? "");
		async function oe(e) {
			if (j || !i.active) return;
			let t = new AbortController();
			j = t, A.value = "";
			try {
				let n = await i.readProgress(e.id, t.signal);
				if (t.signal.aborted) return;
				if (!n.ok || !n.job || String(n.job.id) !== String(e.id) || !Array.isArray(U(n.job.progress).main_steps)) throw Error("阶段详情读取失败，请重试");
				if (Y(e) && Y(e) !== Y(n.job)) throw Error("当前执行已更新，请刷新批次后重试");
				k.value = n.job;
			} catch (e) {
				!t.signal.aborted && !M(e) && (A.value = e instanceof Error ? e.message : "阶段详情读取失败，请重试");
			} finally {
				j === t && (j = void 0);
			}
		}
		return r(() => i.batchId, () => G("all")), r([
			() => i.active,
			() => i.batchId,
			te,
			() => i.refreshGeneration
		], ([e, t, n, r], [, a, o, s]) => {
			if (!e || !n) {
				J(), e && i.batch && d.value !== null && (d.value = null, g.value = !1);
				return;
			}
			let c = t !== a || String(n.id) !== String(o?.id) || Y(n) !== Y(o) || x(n) !== (o && x(o)), l = r !== s;
			(c || l) && J(), (c || l || !k.value && !A.value || C(n) === "active") && oe(n);
		}), y(J), (n, r) => (t(), D("section", {
			class: "registration-batch",
			"aria-labelledby": "registration-batch-title",
			"aria-busy": e.loading
		}, [
			_("header", Le, [_("div", null, [_("div", Re, [
				r[5] ||= _("h2", { id: "registration-batch-title" }, "任务批次进度", -1),
				e.batch ? (t(), D("span", {
					key: 0,
					class: "registration-state",
					"data-tone": ne.value.tone
				}, h(ne.value.label), 9, ze)) : l("", !0),
				e.batch?.projection_delayed ? (t(), D("span", Be, "进度同步中")) : l("", !0)
			]), e.batch ? (t(), D("p", Ve, [
				_("span", null, h(I(e.batch.total ?? w.value.all)) + " 个任务", 1),
				e.batch.workers ? (t(), D("span", He, "并发 " + h(e.batch.workers), 1)) : l("", !0),
				N.value ? (t(), D("span", Ue, "批次耗时 " + h(N.value), 1)) : l("", !0)
			])) : l("", !0)]), b.value.length ? (t(), D("div", We, [
				_("select", {
					value: e.batchId,
					"aria-label": "选择任务批次",
					onChange: r[0] ||= (e) => o("select", e.target.value)
				}, [(t(!0), D(f, null, a(b.value, (e) => (t(), D("option", {
					key: String(e.batch_id),
					value: String(e.batch_id)
				}, h(W(e)), 9, Ke))), 128))], 40, Ge),
				e.actions.stopBatch ? (t(), D("button", {
					key: 0,
					type: "button",
					disabled: e.mutating,
					onClick: r[1] ||= (e) => o("batchAction", "stopBatch")
				}, "停止运行", 8, qe)) : l("", !0),
				e.actions.cancelBatch ? (t(), D("button", {
					key: 1,
					type: "button",
					disabled: e.mutating,
					onClick: r[2] ||= (e) => o("batchAction", "cancelBatch")
				}, "取消排队", 8, Je)) : l("", !0),
				e.actions.retryBatch ? (t(), D("button", {
					key: 2,
					type: "button",
					disabled: e.mutating,
					onClick: r[3] ||= (e) => o("batchAction", "retryBatch")
				}, "重跑失败", 8, Ye)) : l("", !0)
			])) : l("", !0)]),
			e.error ? (t(), D("div", Xe, [O(h(e.error) + " ", 1), _("button", {
				type: "button",
				onClick: r[4] ||= (e) => o("refresh")
			}, "刷新批次")])) : !e.batch || !v.value.length ? (t(), D("p", Ze, h(e.loading ? "正在读取任务批次…" : "暂无注册任务批次"), 1)) : l("", !0),
			e.batch && w.value.all ? (t(), D(f, { key: 2 }, [
				_("div", Qe, [(t(!0), D(f, null, a(ee.value.slice(1), (e) => (t(), D("span", {
					key: e.key,
					"data-tone": e.key,
					style: p({ flexGrow: w.value[e.key] })
				}, null, 12, $e))), 128))]),
				_("div", et, [(t(!0), D(f, null, a(ee.value, (e) => (t(), D("button", {
					key: e.key,
					type: "button",
					"data-batch-filter": e.key,
					"aria-pressed": u.value === e.key,
					onClick: (t) => G(e.key)
				}, [e.key === "all" ? l("", !0) : (t(), D("span", {
					key: 0,
					class: "registration-status-dot",
					"data-tone": e.key,
					"aria-hidden": "true"
				}, null, 8, nt)), O(h(e.label) + " " + h(I(w.value[e.key])), 1)], 8, tt))), 128))]),
				(t(!0), D(f, null, a(R.value, ({ job: n, tone: i, result: s, identity: u, elapsed: p, started: m, completed: v }) => (t(), D("article", {
					key: String(n.id),
					class: "registration-batch-card",
					"data-tone": i
				}, [_("div", it, [
					_("div", at, [_("strong", null, h(n.email || "准备邮箱中…"), 1), _("small", null, h(u), 1)]),
					_("div", ot, [_("span", {
						class: "registration-state",
						"data-tone": i
					}, h(H(n)), 9, st), s ? (t(), D("small", ct, h(s), 1)) : l("", !0)]),
					p || m || v ? (t(), D("div", lt, [p ? (t(), D("strong", ut, "运行耗时 " + h(p), 1)) : l("", !0), _("div", dt, [m ? (t(), D("small", ft, [r[6] ||= O("开始 ", -1), _("time", {
						datetime: n.started_at || void 0,
						title: m.full
					}, h(m.label), 9, pt)])) : l("", !0), v ? (t(), D("small", mt, [r[7] ||= O("结束 ", -1), _("time", {
						datetime: n.completed_at || void 0,
						title: v.full
					}, h(v.label), 9, ht)])) : l("", !0)])])) : l("", !0),
					_("div", gt, [
						_("button", {
							type: "button",
							"aria-label": `查看阶段 · ${n.email || `任务 #${n.id}`}`,
							"aria-expanded": d.value === String(n.id),
							"aria-controls": `registration-stages-${n.id}`,
							onClick: (e) => K(n)
						}, "阶段", 8, _t),
						_("button", {
							type: "button",
							"aria-label": `查看日志 · ${n.email || `任务 #${n.id}`}`,
							onClick: (e) => o("log", n.id)
						}, "日志", 8, vt),
						n.retryable ? (t(), D("button", {
							key: 0,
							type: "button",
							disabled: e.mutating,
							onClick: (e) => o("retry", n)
						}, h(n.retry_label || "重试"), 9, yt)) : l("", !0)
					])
				]), _("div", {
					id: `registration-stages-${n.id}`,
					class: "registration-batch-evidence",
					hidden: d.value !== String(n.id),
					"data-progress-state": d.value === String(n.id) ? A.value ? "error" : k.value ? "ready" : "loading" : void 0
				}, [d.value === String(n.id) ? (t(), D(f, { key: 0 }, [A.value ? (t(), D("p", xt, [O(h(A.value) + " ", 1), _("button", {
					type: "button",
					onClick: (e) => oe(n)
				}, "重试读取", 8, St)])) : k.value ? l("", !0) : (t(), D("p", Ct, "正在读取阶段详情…")), k.value ? (t(), D(f, { key: 2 }, [
					c(Fe, {
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
					k.value.error_message ? (t(), D("details", wt, [r[8] ||= _("summary", null, "原始错误摘要", -1), _("p", null, h(k.value.error_message), 1)])) : l("", !0),
					T(z)(k.value.attempts).length || T(z)(k.value.route_attempts).length ? (t(), D("details", Tt, [
						r[9] ||= _("summary", null, "尝试与线路记录", -1),
						(t(!0), D(f, null, a(T(z)(k.value.attempts), (n) => (t(), D("p", { key: T(q)(n.id || n.attempt_id) }, h(e.statusLabel(n.status)) + " · " + h(n.error_message || "已记录"), 1))), 128)),
						(t(!0), D(f, null, a(T(z)(k.value.route_attempts), (n) => (t(), D("p", { key: T(q)(n.route_attempt_no) }, " 线路尝试 " + h(n.route_attempt_no || 1) + " · " + h(n.retry_reason || e.statusLabel(n.status)), 1))), 128))
					])) : l("", !0)
				], 64)) : l("", !0)], 64)) : l("", !0)], 8, bt)], 8, rt))), 128)),
				E.value.length ? l("", !0) : (t(), D("p", Et, "没有符合条件的任务")),
				_("p", Dt, "显示 " + h(I(E.value.length)) + " 条任务", 1)
			], 64)) : l("", !0)
		], 8, Ie));
	}
}), $ = (e, t = {}) => N(e, t, ce), kt = (e) => ({
	method: "POST",
	headers: { "Content-Type": "application/json" },
	body: JSON.stringify(e ?? {})
});
function At() {
	return {
		metadata: (e) => Promise.all([$("/api/email-sources", { signal: e }), $("/api/capabilities", { signal: e })]).then(([e, t]) => ({
			...e,
			capabilities: t
		})),
		summary: (e) => $("/api/summary", { signal: e }),
		jobs: (e, t) => $(`/api/jobs?${new URLSearchParams(Object.entries(e).map(([e, t]) => [e, String(t)]))}`, { signal: t }),
		progress: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/progress`, { signal: t }),
		create: (e, t) => $("/api/jobs", {
			...kt(e),
			signal: t
		}),
		action: (e, t = {}, n) => $(e, {
			...kt(t),
			signal: n
		}),
		log: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/log`, { signal: t }),
		debug: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/debug?limit=300`, { signal: t }),
		diagnostics: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/diagnostics?limit=100`, { signal: t }),
		compare: (e, t) => $(`/api/jobs/${encodeURIComponent(String(e))}/debug/compare`, { signal: t })
	};
}
// src/features/registration/useRegistration.ts
var jt = [
	"pending",
	"running",
	"stopping"
], Mt = [
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
], Nt = [
	"failed",
	"partial_success",
	"stopped",
	"cancelled",
	"interrupted",
	"request_unknown",
	"manual_reconcile",
	"attention_required"
], Pt = () => ({
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
}), Ft = (e) => e instanceof Error ? e.message : "请求失败", It = (e) => e == null ? "" : String(e).trim(), Lt = (e) => encodeURIComponent(String(se(e))), Rt = () => ({
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
function zt(e) {
	let t = e.api || At(), n = m(!!e.visible), r = m(!document.hidden), i = !1, a = S(() => n.value && r.value && !i), o = s({
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
		query: Pt(),
		batchId: "",
		batchRefreshGeneration: 0,
		statusCounts: {},
		facets: {},
		creating: !1,
		pendingActions: {},
		lastCreate: null,
		lastAction: null,
		detail: Rt()
	}), c = S(() => o.creating), l = S(() => {
		let e = o.meta?.capabilities?.features?.register;
		return e?.enabled === !1 ? String(e.reason || "功能缺少必要配置") : "";
	}), u = (t) => e.notify?.(t), d = 0, f = 0, p = 0, h = 0, g = 0, _, v, b, x, C, w, ee, T, E = "", D = 0, O = 0, k = !0, A, j = /* @__PURE__ */ new Map(), ne = () => !i && r.value && o.detail.id !== null, re = (e, t) => ne() && e === g && String(o.detail.id) === String(t);
	function N() {
		d++, x?.controller.abort(), x = void 0, o.loading = !1;
	}
	function ie() {
		N(), p++, C?.controller.abort(), C = void 0, h++, w?.controller.abort(), w = void 0;
	}
	function P() {
		window.clearInterval(_), window.clearInterval(v), _ = v = void 0;
	}
	function ae() {
		if (!a.value) return !1;
		if (o.view === "tasks") return !0;
		let e = o.batch;
		return !e || String(e.batch_id) !== o.batchId || e.projection_delayed ? !0 : jt.some((t) => Number(e.status_counts?.[t] || 0) > 0) || e.items.some((e) => jt.includes(String(e.status || "")));
	}
	function F(e) {
		for (let t of Object.keys(Pt())) {
			let n = e[t];
			if (n !== void 0) {
				if (t === "page" || t === "page_size") {
					let e = Number(n);
					Number.isSafeInteger(e) && e > 0 && (o.query[t] = t === "page_size" ? Math.min(e, 500) : e);
				} else o.query[t] = String(n);
			}
		}
		if (e.progress_batch_id !== void 0) {
			let t = It(e.progress_batch_id);
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
					s === "launch" && (a.progress_detail = 0), s === "tasks" && e.automatic && E === n && Date.now() - D < 3e4 && (a.include_facets = 0);
					let u = await t.jobs(a, i.signal);
					if (!l()) return;
					if (Object.prototype.hasOwnProperty.call(u, "status_counts") && (o.statusCounts = u.status_counts || {}), s === "launch") {
						o.batches = u.progress_batches || [];
						let e = u.progress_batch || null;
						if (!e && o.batchId) {
							let e = It(o.batches[0]?.batch_id);
							if (e !== o.batchId && (o.batchId = e, o.batch = null, e && !r)) continue;
						}
						!o.batchId && e?.batch_id && (o.batchId = It(e.batch_id)), o.batch = e, o.batchRefreshGeneration = c;
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
				l() && !M(e) && (o.error = Ft(e));
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
		return I({ progress_batch_id: It(e) });
	}
	function R(e, n) {
		return t.progress(se(e), n);
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
		if (e && (k = !0), !a.value || !k && o.meta && Date.now() - O < 3e4) return Promise.resolve();
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
				}, O = Date.now(), k = !1;
			} catch (e) {
				n === h && a.value && !M(e) && (o.error = Ft(e));
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
	function K() {
		P(), a.value && (G(), I({ coalesce: !0 }), W(), _ = window.setInterval(() => {
			I({ automatic: !0 });
		}, 5e3), v = window.setInterval(() => {
			C || W();
		}, 1e4));
	}
	function q(e) {
		n.value !== e && (n.value = e, e ? K() : (P(), ie()));
	}
	function J(e) {
		["launch", "tasks"].includes(e) && o.view !== e && (o.view = e, N(), I({ coalesce: !0 }));
	}
	function Y(e, t = "已受理") {
		let n = e.message || e.warning || (e.started_count == null ? e.deleted_count == null ? e.cancelled == null ? t : `已取消 ${e.cancelled} 个排队任务` : `已删除 ${e.deleted_count} 个任务` : `已提交 ${e.started_count} 个失败任务`), r = Array.isArray(e.skipped) ? e.skipped.length : 0;
		o.receipt = {
			tone: e.warning ? "warning" : "success",
			message: String(n) + (r ? `，跳过 ${r} 个` : "")
		}, u(o.receipt.message);
	}
	function oe(e) {
		let t = It(e.jobs?.[0]?.batch_id || e.job?.batch_id || e.batch_id);
		t && (o.batchId = t, o.batch = null);
	}
	function ce(e, n = {}) {
		let r = JSON.stringify([e, n]), i = j.get(r);
		if (i) return i;
		o.pendingActions[r] = !0;
		let a = (async () => {
			try {
				let r = await t.action(e, n);
				return o.lastAction = r, oe(r), Y(r), /\/delete(?:-bulk)?$/.test(e) && o.detail.id !== null && (Array.isArray(r.deleted) ? r.deleted : r.deleted === !0 ? [e.split("/").at(-2)] : []).some((e) => String(e) === String(o.detail.id)) && me(), I(), o.detail.id !== null && Z(), r;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: Ft(e)
				}, u(o.receipt.message), e;
			} finally {
				j.delete(r), delete o.pendingActions[r];
			}
		})();
		return j.set(r, a), a;
	}
	function le(e) {
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
				return o.lastCreate = n, oe(n), Y(n, `已提交 ${n.submitted || 0} 个任务`), I(), n;
			} catch (e) {
				throw o.receipt = {
					tone: "danger",
					message: Ft(e)
				}, u(o.receipt.message), e;
			} finally {
				o.creating = !1, A = void 0;
			}
		})(), A);
	}
	function X(e) {
		let t = o.batch?.items || [];
		return e === "stopBatch" ? t.filter((e) => e.status === "running" || e.status === "stopping") : e === "cancelBatch" ? t.filter((e) => e.status === "pending") : t.filter((e) => Nt.includes(String(e.status)) && e.retryable);
	}
	let ue = S(() => ({
		stopBatch: !!o.batchId && X("stopBatch").length > 0,
		cancelBatch: !!o.batchId && X("cancelBatch").length > 0,
		retryBatch: X("retryBatch").length > 0
	}));
	async function de(t, n, r = [], i = !1) {
		let a = t === "stopBatch" || t === "cancelBatch" || t === "retryBatch" ? X(t) : [], s = t === "retryBulk" || t === "deleteBulk" ? r.map((e) => se(e)) : a.map((e) => se(e.id));
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
		}, l = t === "retry" && n?.retry_action === "codex" ? "仅补跑 Codex 授权" : t === "retry" && n?.retry_action === "twofa" ? "重新登录检查并补齐 Authenticator 2FA" : t === "retry" && n?.retry_action === "registration_resume" ? "使用已保存账号密码继续邮箱验证" : "有原邮箱则复用，没有原邮箱则重新领取；已创建账号的任务按缺失步骤补跑，不能重试的由后端校验", d = t === "retry" || t === "retryBulk" || t === "retryBatch" ? `\n${l}。原任务记录和日志会保留。` : t === "stop" || t === "stopBatch" ? "\n任务会在当前步骤检查点退出。" : t === "cancelAll" || t === "cancelBatch" ? "\n运行中的任务不受影响。" : "", f = encodeURIComponent(o.batchId), p = n ? Lt(n.id) : "";
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
		g++, ee?.abort(), T?.abort(), ee = T = void 0, window.clearTimeout(b), b = void 0, o.detail.loading = !1, o.detail.comparing = !1;
	}
	async function Z() {
		if (!ne()) return;
		ee?.abort(), window.clearTimeout(b);
		let e = o.detail.id, n = ++g, r = new AbortController();
		ee = r, o.detail.loading = !0, o.detail.error = "";
		let i = () => re(n, e);
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
			i() && !M(e) && (o.detail.error = Ft(e));
		} finally {
			i() && (o.detail.loading = !1, Mt.includes(String(o.detail.job?.status || "")) || (b = window.setTimeout(() => void Z(), 2e3)));
		}
	}
	function pe(t, n) {
		let r = se(t), i = [...o.jobs, ...o.batch?.items || []].find((e) => String(e.id) === String(r));
		i?.operation_task_id && e.openTask ? e.openTask(i.operation_task_id, i.operation_run_id || null, n || null) : (fe(), o.detail = {
			...Rt(),
			id: r
		}, Z());
	}
	function me() {
		fe(), o.detail = Rt();
	}
	async function he(e) {
		let n = se(e);
		if (!re(g, n)) return null;
		T?.abort();
		let r = new AbortController();
		T = r;
		let i = () => ne() && T === r && !r.signal.aborted && String(o.detail.id) === String(n);
		o.detail.comparing = !0, o.detail.compareError = "";
		try {
			let e = await t.compare(n, r.signal);
			return i() ? (o.detail.comparison = e, e) : null;
		} catch (e) {
			if (i() && !M(e)) throw o.detail.compareError = Ft(e), e;
			return null;
		} finally {
			i() && (o.detail.comparing = !1, T = void 0);
		}
	}
	function ge() {
		r.value = !document.hidden, r.value ? (K(), o.detail.id !== null && Z()) : (P(), ie(), fe());
	}
	function _e() {
		i = !0, P(), ie(), fe(), document.removeEventListener("visibilitychange", ge);
	}
	return document.addEventListener("visibilitychange", ge), te() && y(_e), {
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
		shouldPollJobs: ae,
		create: le,
		action: ce,
		executeAction: de,
		compare: he,
		openLog: pe,
		refreshDetail: Z,
		closeDetail: me,
		notify: u,
		terminalStatuses: Mt,
		activeStatuses: jt,
		batchActions: ue,
		readBatchProgress: R,
		dispose: _e
	};
}
// src/features/registration/RegistrationPage.vue?vue&type=script&setup=true&lang.ts
var Bt = ["data-view"], Vt = { class: "registration-launch" }, Ht = {
	class: "registration-summary",
	"aria-label": "注册与本地邮箱概览"
}, Ut = {
	class: "registration-launch-panel",
	"aria-labelledby": "registration-launch-title"
}, Wt = { class: "registration-launcher" }, Gt = ["disabled", "aria-describedby"], Kt = ["value"], qt = { class: "registration-debug" }, Jt = ["disabled", "title"], Yt = { class: "registration-hint" }, Xt = { id: "registrationEmailSupplyHint" }, Zt = { class: "registration-tasks" }, Qt = { class: "registration-toolbar" }, $t = ["disabled"], en = ["disabled"], tn = {
	class: "registration-count-row",
	"data-registration-count-row": ""
}, nn = { class: "registration-count-main" }, rn = { class: "registration-count" }, an = { class: "registration-count-actions" }, on = { class: "registration-mobile-filter" }, sn = {
	key: 0,
	class: "registration-list-error",
	role: "alert"
}, cn = { class: "registration-table-wrap" }, ln = { key: 2 }, un = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], dn = { key: 0 }, fn = { key: 1 }, pn = [
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
		let y = e, C = zt(y.deps), { state: E } = C, te = ne({
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
			te.resetColumns(), y.deps.notify?.("已恢复默认列宽");
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
		], N = m();
		Y(N, () => E.detail.id !== null, () => C.active.value);
		let P = m(1), ae = m(3), F = m(""), I = m(!1), L = m(""), R = m(""), z = m(""), B = m(""), V = m(""), H = m(""), U = m(""), W = m(""), G = m(1), K = m(20), q = m(/* @__PURE__ */ new Set()), J = m({}), se = S(() => E.view === "launch"), ce = S(() => E.view === "tasks"), le = S(() => E.jobs), X = m(null), ue = S(() => ({
			id: R.value,
			email: z.value,
			email_source: B.value,
			status: L.value,
			proxy: V.value,
			error: H.value,
			date_from: U.value,
			date_to: W.value
		})), de = {
			id: "ID",
			email: "邮箱",
			email_source: "邮箱来源",
			status: "状态",
			proxy: "代理",
			error: "错误",
			date_from: "开始日期",
			date_to: "截止日期"
		}, fe = S(() => Object.entries(ue.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${de[e]}：${e === "status" ? Oe(t) : e === "email_source" ? De(t) : t}`,
			removeLabel: `清除${de[e]}筛选`
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
			n[e].value = t, X.value = null, Fe();
		}
		let pe = (e) => e.error_info ? ie(e.error_info) : e.error_message ? "执行异常" : "—", me = S(() => E.statusCounts.active ?? [
			"pending",
			"running",
			"stopping"
		].reduce((e, t) => e + Number((Object.keys(E.statusCounts).length ? E.statusCounts : E.batch?.status_counts || {})[t] || 0), 0)), he = S(() => !!E.meta?.manual_mode), _e = m(!1), ve = S(() => {
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
			return B.value && !e.has(B.value) && e.set(B.value, {
				value: B.value,
				label: B.value
			}), [...e.values()];
		}), ye = S(() => he.value ? [{
			value: "manual",
			label: "手动配置邮箱"
		}] : E.meta?.sources?.filter((e) => e.enabled === !0) || []), be = S(() => C.registrationUnavailable.value || (E.meta && !ye.value.length ? "没有可用的邮箱来源。请先导入本地邮箱，再重新选择。" : "")), xe = S(() => be.value || (E.meta ? he.value ? "使用手动配置的邮箱来源。" : F.value ? "" : "请选择本批使用的邮箱来源。" : "正在读取邮箱来源…")), Se = S(() => E.summary?.email_supply || {}), Ce = (e) => {
			let t = Se.value[e];
			return Number.isInteger(t) && Number(t) >= 0 ? t : Se.value.status === "error" ? "读取失败" : "未知";
		}, we = S(() => `仅统计本地库存；用完后请手动导入；邮箱由 Email Butler 等邮箱服务准备${Se.value.reason ? `；${Se.value.reason}` : ""}`), Te = S(() => [
			{
				label: "已注册",
				value: E.summary?.accounts ?? "—"
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
		]), Ee = (e) => E.meta?.registration_drivers?.find((t) => String(t.value) === String(e))?.label || {
			protocol: "本地优化 Protocol（历史）",
			protocol_oss: "开源 Protocol（历史）",
			protocol_oss_2: "开源protocol-2",
			sentinel_rs: "Rust sentinel-rs",
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
			e || (X.value = null), C.setVisible(e);
		}
		function je(e) {
			X.value = null, C.setView(e);
		}
		function Me(e) {
			let t = N.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && C.closeDetail();
		}
		async function Ne() {
			if (E.creating || _e.value) return;
			if (be.value) {
				E.receipt = {
					tone: "warning",
					message: be.value
				};
				return;
			}
			let e = Number(P.value), t = Number(ae.value);
			if (!Number.isSafeInteger(e) || e < 1) {
				E.receipt = {
					tone: "warning",
					message: "注册数量必须为有效的正整数"
				};
				return;
			}
			if (!Number.isSafeInteger(t) || t < 1) {
				E.receipt = {
					tone: "warning",
					message: "并发线程数必须为有效的正整数"
				};
				return;
			}
			if (!ye.value.some((e) => e.value === F.value)) {
				E.receipt = {
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
				if (me.value > 0 && !await ke(`当前任务表里已有 ${me.value} 个任务在跑或排队，这次会再加 ${e} 个，确定继续？`)) return;
				let t = await C.create(n);
				Number.isSafeInteger(t?.workers) && t.workers > 0 && (ae.value = t.workers);
			} catch {} finally {
				_e.value = !1;
			}
		}
		async function Q(e, t) {
			let n = Array.from(q.value);
			try {
				await C.executeAction(e, t, n, I.value), (e === "deleteBulk" || e === "retryBulk") && (q.value = /* @__PURE__ */ new Set());
			} catch {}
		}
		function Pe() {
			L.value = R.value = z.value = B.value = V.value = H.value = U.value = W.value = "", G.value = 1, C.load(Be());
		}
		function Fe() {
			G.value = 1, C.load(Be());
		}
		function Ie(e) {
			let t = e.target.checked;
			le.value.filter((e) => !["running", "stopping"].includes(String(e.status))).forEach((e) => t ? q.value.add(String(e.id)) : q.value.delete(String(e.id))), q.value = new Set(q.value);
		}
		function Le(e, t) {
			let n = new Set(q.value);
			t.target.checked ? n.add(String(e)) : n.delete(String(e)), q.value = n;
		}
		function Re(e) {
			return [
				e.proxy_provider,
				e.proxy_endpoint && e.proxy_endpoint !== "-" ? e.proxy_endpoint : "",
				e.proxy_region && e.proxy_region !== "-" ? e.proxy_region : ""
			].filter(Boolean).join(" · ") || "-";
		}
		function ze(e) {
			G.value = 1, C.setBatch(e);
		}
		function Be() {
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
		function Ve(e) {
			let t = String(J.value[String(e.id)] || "").trim();
			t ? C.action("/api/manual-otp", {
				email: e.email,
				code: t,
				job_id: e.id
			}).then(() => {
				J.value = {
					...J.value,
					[String(e.id)]: ""
				};
			}).catch(() => {}) : E.receipt = {
				tone: "warning",
				message: "请先填写邮箱验证码"
			};
		}
		async function He() {
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
			setVisible: Ae,
			setView: je,
			loadSummary: C.loadSummary,
			renderEmailSupply: C.renderEmailSupply,
			applySummary: C.applySummary,
			action: C.action,
			openLog: C.openLog,
			closeDetail: C.closeDetail
		}), r(() => ({ ...E.query }), (e) => {
			G.value = e.page, K.value = e.page_size, R.value = e.id, z.value = e.email, B.value = e.email_source, L.value = e.status, V.value = e.proxy, H.value = e.error, U.value = e.date_from, W.value = e.date_to;
		}, { immediate: !0 }), r([he, ye], () => {
			he.value ? F.value = "manual" : ye.value.some((e) => e.value === F.value) || (F.value = "");
		}, { immediate: !0 }), o(() => {
			C.ensureMeta();
		}), (e, r) => (t(), D("div", {
			class: "registration-vue-page",
			"data-view": T(E).view
		}, [
			i(_("section", Vt, [
				_("dl", Ht, [(t(!0), D(f, null, a(Te.value, (e) => (t(), D("div", { key: e.label }, [_("dt", null, h(e.label), 1), _("dd", null, h(typeof e.value == "number" ? e.value.toLocaleString("zh-CN") : e.value), 1)]))), 128))]),
				_("section", Ut, [r[23] ||= _("h2", { id: "registration-launch-title" }, "新建注册批次", -1), _("form", {
					novalidate: "",
					onSubmit: b(Ne, ["prevent"])
				}, [_("div", Wt, [
					_("label", null, [r[19] ||= O("邮箱来源 ", -1), i(_("select", {
						"onUpdate:modelValue": r[0] ||= (e) => F.value = e,
						disabled: !T(E).meta || he.value || !ye.value.length,
						"aria-describedby": xe.value ? "registration-launch-hint registrationEmailSupplyHint" : "registrationEmailSupplyHint"
					}, [r[18] ||= _("option", { value: "" }, "请选择本次邮箱来源", -1), (t(!0), D(f, null, a(ye.value, (e) => (t(), D("option", {
						key: String(e.value),
						value: String(e.value)
					}, h(e.label || e.value), 9, Kt))), 128))], 8, Gt), [[u, F.value]])]),
					_("label", null, [r[20] ||= O("注册数量", -1), i(_("input", {
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
					_("label", null, [r[21] ||= O("并发线程", -1), i(_("input", {
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
					_("label", qt, [i(_("input", {
						"onUpdate:modelValue": r[3] ||= (e) => I.value = e,
						type: "checkbox"
					}, null, 512), [[v, I.value]]), r[22] ||= O(" 调试模式", -1)]),
					_("button", {
						type: "submit",
						class: "registration-start",
						disabled: T(E).creating || _e.value || !F.value || !!be.value,
						title: be.value || void 0
					}, h(T(E).creating ? "提交中…" : "开始注册"), 9, Jt)
				]), _("p", Yt, [xe.value ? (t(), D("span", {
					key: 0,
					id: "registration-launch-hint",
					class: x({ "registration-warning": be.value }),
					role: "status"
				}, h(xe.value), 3)) : l("", !0), _("span", Xt, h(we.value), 1)])], 32)]),
				se.value ? (t(), g(Ot, {
					key: 0,
					batch: T(E).batch,
					batches: T(E).batches,
					"batch-id": T(E).batchId,
					"refresh-generation": T(E).batchRefreshGeneration,
					active: T(C).active.value,
					loading: T(E).loading,
					error: T(E).error,
					actions: T(C).batchActions.value,
					mutating: Object.keys(T(E).pendingActions).length > 0,
					"status-label": Oe,
					"source-label": De,
					"driver-label": Ee,
					"read-progress": T(C).readBatchProgress,
					onSelect: ze,
					onRefresh: r[4] ||= (e) => T(C).load(),
					onBatchAction: r[5] ||= (e) => Q(e),
					onRetry: r[6] ||= (e) => Q("retry", e),
					onLog: T(C).openLog
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
			], 512), [[ee, se.value]]),
			i(_("section", Zt, [
				_("div", Qt, [
					_("button", {
						type: "button",
						onClick: r[7] ||= (e) => Q("retryBulk"),
						disabled: !q.value.size
					}, "重试", 8, $t),
					_("button", {
						type: "button",
						onClick: r[8] ||= (e) => Q("deleteBulk"),
						disabled: !q.value.size
					}, "删除", 8, en),
					_("button", {
						type: "button",
						onClick: r[9] ||= (e) => Q("cancelAll")
					}, "取消排队"),
					_("button", {
						type: "button",
						onClick: Fe
					}, "刷新")
				]),
				_("div", tn, [_("div", nn, [_("span", rn, "共 " + h(T(E).total.toLocaleString()) + " 条任务", 1), c(j, {
					items: fe.value,
					onRemove: r[10] ||= (e) => Z(e, "")
				}, null, 8, ["items"])]), _("div", an, [
					_("button", {
						type: "button",
						"aria-label": "恢复注册任务列宽",
						onClick: A
					}, "恢复列宽"),
					_("span", on, [c(ge, {
						values: ue.value,
						sources: ve.value,
						open: X.value === "all",
						"onUpdate:open": r[11] ||= (e) => X.value = e ? "all" : null,
						onChange: Z
					}, null, 8, [
						"values",
						"sources",
						"open"
					])]),
					fe.value.length ? (t(), D("button", {
						key: 0,
						type: "button",
						onClick: Pe
					}, "清筛")) : l("", !0)
				])]),
				T(E).error ? (t(), D("div", sn, [O(h(T(E).error) + " ", 1), _("button", {
					type: "button",
					onClick: Fe
				}, "重试")])) : l("", !0),
				_("div", cn, [_("table", {
					class: "jobs-table-v2",
					style: p({ width: `${T(te).total.value}px` })
				}, [
					_("colgroup", null, [(t(!0), D(f, null, a(T(te).widths.value, (e, n) => (t(), D("col", {
						key: n,
						style: p({ width: `${e}px` })
					}, null, 4))), 128))]),
					_("thead", null, [_("tr", null, [(t(), D(f, null, a(M, (e, n) => _("th", { key: e.label }, [n === 0 ? (t(), D("input", {
						key: 0,
						type: "checkbox",
						"aria-label": "选择本页可操作任务",
						onChange: Ie
					}, null, 32)) : e.filter ? (t(), g(ge, {
						key: 1,
						column: e.filter,
						values: ue.value,
						sources: ve.value,
						open: X.value === e.filter,
						"onUpdate:open": (t) => X.value = t ? e.filter : null,
						onChange: Z
					}, null, 8, [
						"column",
						"values",
						"sources",
						"open",
						"onUpdate:open"
					])) : (t(), D("span", ln, h(e.label), 1)), n < M.length - 1 ? (t(), D("button", {
						key: 3,
						type: "button",
						class: "registration-column-resize",
						"aria-label": `调整${e.label}列宽，方向键调整`,
						onPointerdown: b((e) => T(te).resize(n, e), ["prevent"]),
						onKeydown: [d(b((e) => T(te).resizeWithKeyboard(n, -10), ["prevent"]), ["left"]), d(b((e) => T(te).resizeWithKeyboard(n, 10), ["prevent"]), ["right"])]
					}, null, 40, un)) : l("", !0)])), 64))])]),
					_("tbody", null, [T(E).loading ? (t(), D("tr", dn, [...r[24] ||= [_("td", { colspan: "11" }, "正在加载任务…", -1)]])) : le.value.length ? l("", !0) : (t(), D("tr", fn, [...r[25] ||= [_("td", { colspan: "11" }, "暂无匹配任务", -1)]])), (t(!0), D(f, null, a(le.value, (e) => (t(), D("tr", { key: String(e.id) }, [
						_("td", null, [_("input", {
							type: "checkbox",
							"aria-label": `选择任务 ${e.id}`,
							checked: q.value.has(String(e.id)),
							disabled: ["running", "stopping"].includes(String(e.status)),
							onChange: (t) => Le(e.id, t)
						}, null, 40, pn)]),
						_("td", null, [c(k, {
							text: `#${e.id}`,
							secondary: e.parent_job_id ? `↳ #${e.parent_job_id}` : void 0
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(k, { text: String(e.email || "-") }, null, 8, ["text"])]),
						_("td", null, [c(k, { text: De(e.email_source) }, null, 8, ["text"])]),
						_("td", null, [c(k, { text: Ee(e.registration_driver) }, null, 8, ["text"])]),
						_("td", null, [c(k, {
							text: Re(e),
							secondary: String(e.proxy_status || "")
						}, null, 8, ["text", "secondary"])]),
						_("td", null, [c(k, { text: Oe(e.debug_state === "paused" ? "debug_paused" : e.display_status || e.status) }, null, 8, ["text"])]),
						_("td", null, [c(k, { text: String(e.started_at || "-") }, null, 8, ["text"])]),
						_("td", null, [c(k, { text: String(e.completed_at || "-") }, null, 8, ["text"])]),
						_("td", null, [e.error_message || e.error_info ? (t(), g(re, {
							key: 0,
							"data-registration-result": "",
							label: pe(e),
							title: String(e.error_message || pe(e)),
							tone: "danger"
						}, {
							details: n(() => [_("p", null, h(e.error_message || pe(e)), 1), e.error_info ? (t(), D("p", mn, h(e.error_info), 1)) : l("", !0)]),
							_: 2
						}, 1032, ["label", "title"])) : (t(), g(k, {
							key: 1,
							text: "—"
						}))]),
						_("td", hn, [
							_("button", {
								type: "button",
								onClick: (t) => T(C).openLog(e.id)
							}, "日志", 8, gn),
							e.manual_otp_required && e.status === "running" ? (t(), D(f, { key: 0 }, [i(_("input", {
								"onUpdate:modelValue": (t) => J.value[String(e.id)] = t,
								placeholder: "邮箱验证码"
							}, null, 8, _n), [[w, J.value[String(e.id)]]]), _("button", {
								type: "button",
								onClick: (t) => Ve(e)
							}, "提交验证码", 8, vn)], 64)) : l("", !0),
							[
								"pending",
								"running",
								"stopping"
							].includes(String(e.status)) ? (t(), D("button", {
								key: 1,
								type: "button",
								onClick: (t) => Q("stop", e)
							}, "停止", 8, yn)) : l("", !0),
							e.retryable ? (t(), D("button", {
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
					]))), 128))])
				], 4)]),
				c(oe, {
					label: "注册任务分页",
					page: G.value,
					size: K.value,
					total: T(E).total,
					busy: T(E).loading,
					"onUpdate:page": r[12] ||= (e) => {
						G.value = e, T(C).load(Be());
					},
					"onUpdate:size": r[13] ||= (e) => {
						K.value = e, G.value = 1, T(C).load(Be());
					}
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			], 512), [[ee, ce.value]]),
			T(E).receipt ? (t(), D("div", {
				key: 0,
				class: x(["registration-receipt", `is-${T(E).receipt.tone}`]),
				role: "status"
			}, h(T(E).receipt.message), 3)) : l("", !0),
			_("dialog", {
				ref_key: "logDialog",
				ref: N,
				class: "registration-dialog",
				"aria-labelledby": "registration-log-title",
				onCancel: r[16] ||= b((...e) => T(C).closeDetail && T(C).closeDetail(...e), ["prevent"]),
				onClose: r[17] ||= (...e) => T(C).closeDetail && T(C).closeDetail(...e),
				onClick: Me
			}, [
				_("header", null, [_("h2", Sn, "任务 #" + h(T(E).detail.id) + " 日志", 1), _("button", {
					type: "button",
					onClick: r[14] ||= (...e) => T(C).closeDetail && T(C).closeDetail(...e)
				}, "关闭")]),
				T(E).detail.loading ? (t(), D("p", Cn, "加载中…")) : l("", !0),
				T(E).detail.error ? (t(), D("p", wn, h(T(E).detail.error), 1)) : l("", !0),
				_("pre", null, h(T(E).detail.log || "（暂无日志）"), 1),
				T(E).detail.debug?.enabled ? (t(), D("div", Tn, [
					r[26] ||= _("strong", null, "网络调试", -1),
					_("button", {
						type: "button",
						disabled: T(E).detail.comparing,
						onClick: He
					}, "与同批成功任务对比", 8, En),
					_("a", {
						href: `/api/jobs/${T(E).detail.id}/debug/har`,
						download: ""
					}, "下载脱敏 HAR", 8, Dn),
					_("button", {
						type: "button",
						onClick: r[15] ||= (e) => T(C).action(`/api/jobs/${T(E).detail.id}/debug/release`, { action: "finish" })
					}, "结束调试并收口"),
					T(E).detail.comparison ? (t(), D("pre", On, h(T(E).detail.comparison), 1)) : l("", !0),
					T(E).detail.compareError ? (t(), D("p", kn, h(T(E).detail.compareError), 1)) : l("", !0)
				])) : l("", !0),
				T(E).detail.diagnostics?.captured ? (t(), D("div", An, [
					r[28] ||= _("strong", null, "失败诊断", -1),
					T(E).detail.diagnostics.screenshot_url ? (t(), D("a", {
						key: 0,
						href: String(T(E).detail.diagnostics.screenshot_url),
						target: "_blank",
						rel: "noopener"
					}, "打开失败截图", 8, jn)) : l("", !0),
					_("details", null, [r[27] ||= _("summary", null, "完整诊断证据", -1), _("pre", null, h(T(E).detail.diagnostics), 1)])
				])) : l("", !0)
			], 544)
		], 8, Bt));
	}
});
// src/registration.ts
function Nn(e, t = {}) {
	let n = C(Mn, { deps: {
		...t,
		api: t.api || At()
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
