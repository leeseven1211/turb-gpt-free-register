import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, R as c, S as l, _ as u, a as d, b as f, c as p, d as m, dt as h, et as g, ft as _, g as v, h as y, j as b, l as x, lt as S, m as C, n as w, o as T, st as E, t as D, v as O, x as k } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { r as A, t as j } from "./client-B5R_MNgP.js";
import { a as M, i as N, r as P } from "./taskIds-BlchWwUp.js";
import { t as ee } from "./useNativeDialog-DWisXYg9.js";
import { t as te } from "./ListPagination-BjETSj81.js";
import { n as F, r as I, t as ne } from "./ListFilterSummary-Bc1S5NP4.js";
import { t as re } from "./ListResult-BkPTMQVQ.js";
// src/api/extract.ts
var L = "/api/extract-workbench";
function R(e) {
	let t = new URLSearchParams({
		provider_id: e.provider,
		mode: e.mode,
		status: e.status,
		query: e.query,
		page: String(e.page),
		page_size: String(e.size)
	});
	return e.batch && t.set("batch_id", String(M(e.batch))), t;
}
function z(e = {}) {
	async function t(t, n = {}, r = !1) {
		let i = r && e.statsDataSource || e.dataSource, a = i ? await i(t, n) : await A(t, n, P);
		if (!a || typeof a != "object" || a.ok === !1) throw Error("提链接口响应无效");
		return a;
	}
	let n = (e, n = {}, r) => t(e, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(n),
		signal: r
	}), r = (e) => `${L}/tasks/${encodeURIComponent(M(e))}`;
	function i(e) {
		if (!Array.isArray(e.items) || !Number.isSafeInteger(e.total) || e.total < 0 || !Number.isSafeInteger(e.page) || e.page < 1) throw Error("提链分页响应无效");
		return e;
	}
	return {
		async config(e) {
			let n = await t(`${L}/config`, { signal: e });
			if (!Array.isArray(n.providers)) throw Error("提链配置响应无效");
			return n;
		},
		summary: (e) => t(`${L}/summary`, { signal: e }),
		async batches(e, n) {
			let r = i(await t(`${L}/batches?page=${e}&page_size=20`, { signal: n }));
			for (let e of r.items) M(e.batch_id);
			return r;
		},
		async batch(e, n) {
			let r = await t(`${L}/batches/${encodeURIComponent(M(e))}`, { signal: n });
			if (!r.item || String(M(r.item.batch_id)) !== String(M(e))) throw Error("提链批次响应不匹配");
			return r;
		},
		async tasks(e, n) {
			let r = i(await t(`${L}/tasks?${R(e)}`, { signal: n }));
			for (let e of r.items) M(e.task_id);
			return r;
		},
		async candidates(e, n, r) {
			let i = await t(`${L}/candidates?${new URLSearchParams({
				...e,
				limit: String(n)
			})}`, { signal: r });
			if (!Number.isSafeInteger(i.total) || !Number.isSafeInteger(i.selected_count) || i.total < 0 || i.selected_count < 0 || i.selected_count > Math.min(i.total, n)) throw Error("候选统计响应无效");
			for (let e of i.items || []) M(e.account_id);
			return i;
		},
		create: (e) => n(`${L}/batches`, e),
		cancel: (e) => n(`${L}/batches/${encodeURIComponent(M(e))}/cancel`),
		detail: async (e, n) => {
			let i = await t(r(e), { signal: n });
			if (!i.item || String(i.item.task_id) !== String(e)) throw Error("提链详情响应不匹配");
			return i;
		},
		action: (e, t) => n(`${r(e)}/actions`, { action: t }),
		async paymentEntry(e, t) {
			let i = await n(`${r(e)}/payment-entry`, {}, t);
			if (!i.entry || ![
				"payment_page_url",
				"payment_url",
				"qr_data",
				"qr_image_url_png",
				"qr_image_url_svg"
			].some((e) => typeof i.entry[e] == "string" && i.entry[e])) throw Error("当前任务没有已保存的支付入口");
			return i;
		},
		links: (e, t) => n(`${r(e)}/links`, { kind: t }),
		secret: (e) => t(`/api/accounts/${encodeURIComponent(M(e))}/secret?field=access_token`),
		async analytics(e, n, r) {
			let i = new URLSearchParams({ days: String(e) });
			n && i.set("provider_id", n);
			let a = await t(`${L}/analytics?${i}`, { signal: r }, !0);
			if (!a.totals || !Array.isArray(a.daily)) throw Error("统计响应格式不完整");
			return a;
		},
		async export(e) {
			let t = R(e);
			t.delete("page"), t.delete("page_size");
			let n = await fetch(`${L}/export?${t}`, { credentials: "same-origin" });
			if (!n.ok || n.redirected || !/(text\/csv|application\/octet-stream)/i.test(n.headers.get("content-type") || "")) throw new j("导出失败，请重新登录或重试", n.status);
			return n.blob();
		}
	};
}
// src/features/extract/presentation.ts
var ie = {
	legacy: "虾扯蛋链",
	lumen: "Lumen Flow",
	lumen_flow: "Lumen Flow",
	huanguang: "幻光提链",
	anguang: "暗光（XXSYUN 一条龙）"
}, B = {
	extract_only: "仅提链",
	manual_payment: "手动支付",
	auto_payment: "自动支付"
}, ae = {
	pix: "PIX",
	upi: "UPI",
	gopay: "GoPay",
	momo: "MOMO",
	gcash: "GCash",
	paypal: "PayPal",
	ideal: "iDEAL",
	ideal_short: "iDEAL Short",
	kakao_pay: "Kakao Pay",
	ph_short: "PH Short"
}, oe = {
	eligible: "全部可提链优惠",
	all: "全部（有无优惠）",
	free_trial: "免费试用",
	half_price: "半价",
	other_discount: "其他折扣",
	other_promo: "其他优惠",
	none: "无优惠"
}, se = [
	["", "全部"],
	["queued", "排队中"],
	["extracting", "进行中"],
	["scanning", "扫码中"],
	["paused", "已暂停"],
	["cancelled", "已停止"],
	["extraction_succeeded", "已出链"],
	["payment_succeeded", "扫码完成"],
	["failed", "失败"],
	["needs_review", "待核对"]
], V = {
	pending: "等待执行",
	queued: "排队中",
	running: "运行中",
	success: "已完成",
	failed: "失败",
	passed: "预检通过",
	succeeded: "已完成",
	waiting: "等待中",
	settling: "收尾中",
	cancelling: "取消中",
	cancelled: "已取消",
	skipped: "已跳过",
	paid: "支付成功",
	unpaid: "未支付",
	pending_payment: "待支付",
	confirmed: "Plus 已确认",
	plus: "Plus 已确认",
	not_confirmed: "Plus 未到账",
	unknown: "响应记录缺失",
	request_unknown: "待核对",
	attention_required: "待核对",
	unavailable: "无法确认",
	not_applicable: "不适用",
	query_stopped: "已停止查询",
	waiting_sync: "等待平台同步",
	awaiting_payment: "待支付",
	processing_payment: "支付中",
	expired: "已过期",
	not_started: "未开始",
	checking: "核验中",
	partial_success: "部分成功",
	partial: "部分完成",
	partial_submission: "部分入队",
	completed: "已完成"
}, H = (e, t = "状态记录缺失") => V[String(e || "").toLowerCase()] || String(e || "") || t, U = (e) => ie[e || ""] || e || "未记录平台", ce = (e) => B[e || ""] || e || "未记录模式", W = (e) => {
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? Math.floor(t) : 0;
}, G = (e) => W(e).toLocaleString("zh-CN");
function K(e) {
	if (e == null || e === "") return "—";
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 && t <= 1 ? `${(t * 100).toFixed(1)}%` : "—";
}
function q(e) {
	if (e == null || e === "" || !Number.isFinite(Number(e)) || Number(e) < 0) return "—";
	let t = Math.round(Number(e));
	return t < 60 ? `${t} 秒` : t < 3600 ? `${Math.floor(t / 60)} 分 ${t % 60} 秒` : `${Math.floor(t / 3600)} 小时 ${Math.floor(t % 3600 / 60)} 分`;
}
function le(e) {
	if (!e) return "—";
	let t = new Date(e);
	return Number.isFinite(t.getTime()) ? new Intl.DateTimeFormat("zh-CN", {
		timeZone: "Asia/Shanghai",
		year: "numeric",
		month: "2-digit",
		day: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
		hour12: !1
	}).format(t).replaceAll("/", "-") : "—";
}
var ue = (e) => Array.isArray(e?.modes) ? e.modes : [], de = (e) => e?.link_types?.length ? [...new Set(e.link_types)] : e?.default_type ? [e.default_type] : [];
function fe(e) {
	return e.payment_source ? e.payment_source_label || {
		native: "平台自带",
		xxsyun: "XXSYUN"
	}[e.payment_source] || "未知来源" : "";
}
var pe = (e) => e.mode === "auto_payment" && fe(e) ? ` · 自动支付来源：${fe(e)}` : "", me = (e) => [
	"queued",
	"running",
	"waiting",
	"settling",
	"cancelling",
	"stopping"
].includes(e.task_status || "");
function he(e) {
	return [
		"request_unknown",
		"attention_required",
		"manual_reconcile",
		"unknown",
		"unconfirmed"
	].includes(e.internal_task_status || e.task_status || "") || ["unknown", "request_unknown"].includes(e.internal_extraction_status || e.extraction_status || "") || [
		"unknown",
		"request_unknown",
		"pending",
		"pending_payment",
		"succeeded",
		"paid"
	].includes(e.internal_payment_status || e.payment_status || "") || e.payment_order?.submission_state === "unknown" || e.local_reconcile_halted === !0 || e.reconcile_halt?.halted === !0;
}
var ge = (e) => !me(e) && !he(e);
function _e(e) {
	return e.local_reconcile_halted || e.reconcile_halt?.halted || ["request_unknown", "attention_required"].includes(e.task_status || "") && ["queued", "running"].includes(e.extraction_status || "") ? "query_stopped" : ["queued", "waiting"].includes(e.task_status || "") && [
		"passed",
		"success",
		"skipped"
	].includes(e.preflight_status || "") && [
		"pending",
		"queued",
		"running",
		"unknown"
	].includes(e.extraction_status || "") ? "waiting_sync" : "";
}
function J(e) {
	let t = ["success", "succeeded"].includes(e.extraction_status || ""), n = e.payment_status === "paid", r = ["confirmed", "plus"].includes(e.plus_status || "");
	return n && r ? {
		label: "支付成功 · Plus 已到账",
		tone: "success",
		detail: e.payment_confirmation_source === "local_plan_check" ? "独立套餐查询已确认 Plus 到账" : e.payment_confirmation_source === "platform_order_check" ? "支付平台已核验 Plus 到账" : "平台状态与本地套餐核实分别记录"
	} : n ? {
		label: "支付成功 · 待核验",
		tone: "warning",
		detail: "已记录支付成功，等待本地 Plus 到账核验"
	} : t && r && e.mode !== "extract_only" ? {
		label: "Plus 已到账 · 支付响应缺失",
		tone: "success",
		detail: "本地套餐已核实，平台支付响应记录缺失"
	} : t ? {
		label: e.payment_status === "failed" ? "已出链 · 支付失败" : [
			"failed",
			"cancelled",
			"stopped",
			"request_unknown",
			"attention_required"
		].includes(e.task_status || "") ? "已出链 · 后续待处理" : "已出链",
		tone: e.payment_status === "failed" || he(e) ? "warning" : "success",
		detail: e.error_info?.summary || e.error || e.message || (e.mode === "extract_only" ? "仅提链已完成，未发起支付" : "支付链接已生成，支付与套餐结果分别记录")
	} : _e(e) ? {
		label: H(_e(e)),
		tone: "warning",
		detail: "原远端任务已保留，可同步原任务状态"
	} : he(e) ? {
		label: "待核对",
		tone: "warning",
		detail: e.error_info?.summary || "平台响应记录缺失，请同步原任务状态"
	} : [
		"failed",
		"cancelled",
		"stopped"
	].includes(e.task_status || "") || e.extraction_status === "failed" ? {
		label: e.task_status === "cancelled" ? "已取消" : "提链未完成",
		tone: "danger",
		detail: e.error_info?.summary || e.error || e.message || "可查看详情确认原因"
	} : {
		label: e.task_status === "running" ? "运行中" : "排队中",
		tone: e.task_status === "running" ? "active" : "neutral",
		detail: e.progress?.label || e.message || "等待开始提链"
	};
}
function Y(e, t = !1) {
	let n = String(e || "").trim();
	if (t && /^data:image\/(?:png|svg\+xml);base64,[a-z0-9+/=\s]+$/i.test(n)) return n;
	try {
		let e = new URL(n);
		return ["http:", "https:"].includes(e.protocol) && !e.username && !e.password ? e.href : "";
	} catch {
		return "";
	}
}
var ve = (e) => [...new Set([e.qr_image_url_png, e.qr_image_url_svg].map((e) => Y(e, !0)).filter(Boolean))];
function ye(e, t = !1) {
	let n = String(e ?? "").toLowerCase();
	return (t ? {
		true: "平台显示已开通",
		confirmed: "平台显示已开通",
		plus: "平台显示已开通",
		active: "平台显示已开通",
		activated: "平台显示已开通",
		success: "平台显示已开通",
		succeeded: "平台显示已开通",
		false: "平台未返回开通结果",
		waiting_for_payment: "等待支付后核验",
		pending: "等待平台核验",
		unknown: "平台核验结果缺失",
		not_started: "平台尚未核验",
		not_confirmed: "平台未返回开通结果",
		failed: "平台核验失败",
		not_applicable: "不适用"
	} : {
		paid: "支付成功",
		succeeded: "支付成功",
		success: "支付成功",
		pending: "待支付",
		unpaid: "未支付",
		not_started: "未发起支付",
		pending_payment: "待支付",
		requires_action: "等待扫码或付款",
		requires_confirmation: "等待支付确认",
		requires_payment_method: "需要支付方式",
		running: "支付处理中",
		processing: "支付处理中",
		failed: "支付失败",
		canceled: "已取消",
		cancelled: "已取消",
		expired: "已过期",
		unknown: "支付响应缺失"
	})[n] || String(e || "平台未返回");
}
var X = (e) => e instanceof Error ? e.message : "请求失败，请重试";
function be(e) {
	return e === "all" ? "匹配套餐优惠已查明（有或无）的活跃、未归档 free 账号；套餐待查及状态未知的账号不包含，提交前仍会在线查活。" : e === "none" ? "仅匹配活跃、未归档且上次查询无优惠的 free 账号；当前优惠由提链平台判断，提交前仍会在线查活。" : `仅匹配活跃、未归档且具备${e === "eligible" ? "任一可提链" : `「${oe[e] || e}」`}优惠的 free 账号；提交前仍会在线查活。`;
}
function xe(e) {
	let t = [
		"任务号",
		"邮箱",
		"平台",
		"模式",
		"任务状态",
		"提链状态",
		"支付阶段",
		"Plus 核验",
		"消息",
		"创建时间",
		"更新时间"
	], n = (e) => `"${String(e ?? "").replaceAll("\"", "\"\"")}"`;
	return "﻿" + [t, ...e.map((e) => [
		e.task_id,
		e.email,
		e.provider_id,
		e.mode,
		e.task_status,
		e.extraction_status,
		e.payment_phase,
		e.plus_state,
		e.error || e.message,
		e.created_at,
		e.updated_at
	])].map((e) => e.map(n).join(",")).join("\r\n");
}
function Se(e, t) {
	let n = URL.createObjectURL(e), r = document.createElement("a");
	r.href = n, r.download = t, document.body.append(r), r.click(), r.remove(), setTimeout(() => URL.revokeObjectURL(n), 2e3);
}
function Ce(e) {
	let t = J(e), n = e.payment_status === "paid", r = ["confirmed", "plus"].includes(e.plus_status || ""), i = n && r ? "支付与Plus确认" : n ? "已支付待核验" : r ? "Plus已到账" : _e(e) ? "等待原单同步" : he(e) ? "待核对" : ["success", "succeeded"].includes(e.extraction_status || "") ? e.payment_status === "failed" ? "已出链支付失败" : "已出链" : [
		"failed",
		"cancelled",
		"stopped"
	].includes(e.task_status || "") ? e.task_status === "cancelled" ? "已取消" : "提链未完成" : me(e) ? "执行中" : "排队中";
	return {
		...t,
		label: i,
		detail: t.detail
	};
}
function we(e) {
	if (e == null || e === "") return null;
	let t = Number(e);
	if (Number.isFinite(t) && t > 1e11) return t;
	let n = Date.parse(String(e));
	return Number.isFinite(n) ? n : null;
}
function Te(e, t = Date.now()) {
	let n = we(e);
	if (n == null) return "—";
	let r = Math.floor((n - t) / 1e3);
	return r <= 0 ? "已过期" : `${String(Math.floor(r / 60)).padStart(2, "0")}:${String(r % 60).padStart(2, "0")}`;
}
// src/features/extract/useExtractWorkbench.ts
var Z = () => ({
	page: 1,
	size: 20,
	provider: "",
	mode: "",
	status: "",
	query: "",
	batch: ""
}), Ee = 3e4;
function De(e = {}) {
	let t = e.api || z(e), n = s({
		query: Z(),
		items: [],
		total: 0,
		counts: {},
		batches: [],
		batchTotal: 0,
		batchPage: 1,
		batchLoading: !1,
		batchDetail: null,
		config: null,
		summary: null,
		loading: !1,
		error: "",
		auxErrors: {
			config: "",
			summary: "",
			batches: "",
			detail: ""
		},
		visible: e.visible !== !1,
		selected: /* @__PURE__ */ new Set(),
		cancellingBatch: "",
		bulkBusy: !1,
		receipt: null
	}), r = !1, i = 0, a = 0, o = 0, c = 0, l = 0, u = 0, d = 0, f = 0, p, m, h, g, _ = /* @__PURE__ */ new Map(), v = /* @__PURE__ */ new Map(), y = /* @__PURE__ */ new Set(), b = () => !r && n.visible && !document.hidden, x = (e) => e === i && b(), S = (t) => e.notify?.(t);
	function C() {
		let e = new AbortController();
		return y.add(e), e;
	}
	function w() {
		p && clearTimeout(p), p = void 0;
	}
	function T() {
		let e = n.config?.poll || {}, t = (e, t, n) => Number.isFinite(Number(e)) && Number(e) > 0 ? Math.min(n, Number(e)) * 1e3 : t;
		return {
			active: t(e.active_seconds, 3e3, 60),
			idle: t(e.idle_seconds, 15e3, 300),
			backoff: t(e.backoff_max_seconds, 3e5, 1800)
		};
	}
	function E(e = !1) {
		if (w(), !b()) return;
		let t = T(), r = n.counts, i = n.batchDetail?.counts || {}, a = Number(r.processing || i.processing || 0) > 0, o = Number(r.awaiting_payment || i.awaiting_payment || 0) > 0, s = e ? Math.min(t.backoff, t.idle * 2 ** Math.min(10, Math.max(0, f - 1))) : a ? t.active : o ? t.idle : 0;
		s && (p = setTimeout(() => void P({ quiet: !0 }), s));
	}
	function D(e, r) {
		if (!e && n.config && Date.now() - l < Ee) return Promise.resolve(n.config);
		if (m) return m.promise;
		let i = ++o, a = C(), s = t.config(a.signal).then((e) => (x(r) && m?.version === i && (n.config = e, n.auxErrors.config = "", l = Date.now(), E(f > 0)), e)).catch((e) => {
			throw x(r) && (n.auxErrors.config = X(e)), e;
		}).finally(() => {
			y.delete(a), m?.version === i && (m = void 0);
		});
		return m = {
			version: i,
			promise: s
		}, s;
	}
	function O(e) {
		if (h) return h.promise;
		let r = ++o, i = C(), a = t.summary(i.signal).then((t) => (x(e) && (n.summary = t, n.auxErrors.summary = ""), t)).catch((t) => {
			throw x(e) && (n.auxErrors.summary = X(t)), t;
		}).finally(() => {
			y.delete(i), h?.version === r && (h = void 0);
		});
		return h = {
			version: r,
			promise: a
		}, a;
	}
	function k(e, r) {
		let i = _.get(e);
		if (i) return i.promise;
		let a = ++o, s = C();
		n.batchLoading = !0, n.auxErrors.batches = "";
		let c = () => x(r) && e === n.batchPage && _.get(e)?.version === a, l = t.batches(e, s.signal).then((t) => (c() && (n.batches = t.items, n.batchTotal = t.total, d = e, u = Date.now()), t)).catch((e) => {
			throw c() && (n.auxErrors.batches = X(e)), e;
		}).finally(() => {
			y.delete(s), c() && (n.batchLoading = !1), _.get(e)?.version === a && _.delete(e);
		});
		return _.set(e, {
			version: a,
			promise: l
		}), l;
	}
	async function A(e) {
		if (!b() || n.batchLoading) return;
		let t = n.batchPage, r = i;
		n.batchPage = e;
		try {
			await k(e, r);
		} catch {
			x(r) && n.batchPage === e && (n.batchPage = t);
		}
	}
	function j(e, n) {
		let r = v.get(e);
		if (r) return r.promise;
		let i = ++o, a = C(), s = t.batch(e, a.signal).finally(() => {
			y.delete(a), v.get(e)?.version === i && v.delete(e);
		});
		return v.set(e, {
			version: i,
			promise: s
		}), s;
	}
	async function N(e, t) {
		D(!!e.force, t).catch(() => {}), O(t).catch(() => {});
		let r = n.batchPage, i = n.query.batch, a = ++c, o = !!e.force || d !== r || Date.now() - u >= Ee;
		try {
			let s = o ? (await k(r, t)).items : n.batches;
			if (!x(t) || r !== n.batchPage || i !== n.query.batch || a !== c) return;
			if (!i) {
				n.batchDetail = null;
				return;
			}
			let l = (!e.quiet || o ? s.find((e) => String(e.batch_id) === i) : null) || (await j(i, t)).item;
			x(t) && i === n.query.batch && a === c && (n.batchDetail = l, n.auxErrors.detail = "", E(f > 0));
		} catch (e) {
			x(t) && i === n.query.batch && r === n.batchPage && (n.auxErrors.detail = X(e));
		}
	}
	async function P(r = {}) {
		if (!b()) return;
		w();
		let o = ++a, s = i, c = { ...n.query };
		g?.abort();
		let l = C();
		g = l, n.loading = !0, n.error = "", N(r, s);
		try {
			let r = await t.tasks(c, l.signal);
			if (!x(s) || o !== a) return;
			n.items = r.items, n.total = r.total, n.counts = r.counts || {}, n.query.page = r.page;
			for (let e of [...n.selected]) r.items.some((t) => String(t.task_id) === e) || n.selected.delete(e);
			f = 0, e.onReady?.(), E();
		} catch (e) {
			x(s) && o === a && (n.error = X(e), f++, E(!0));
		} finally {
			y.delete(l), x(s) && o === a && (n.loading = !1);
		}
	}
	async function ee(e) {
		Object.assign(n.query, Z(), { batch: e ? String(M(e)) : "" }), n.batchDetail = null, n.selected.clear(), c++, await P();
	}
	async function te(r) {
		if (r === "clear") {
			n.selected.clear();
			return;
		}
		if (r === "export") {
			await I(!1);
			return;
		}
		if (n.bulkBusy) return;
		let i = n.items.filter((e) => n.selected.has(String(e.task_id))), a = i.map((e) => e.task_id);
		if (a.length) {
			n.bulkBusy = !0;
			try {
				if (r === "links") {
					let n = [], r = 0;
					for (let e of i) if (!e.has_payment_entry && !e.has_payment_link && !e.has_qr) r++;
					else try {
						let { entry: i } = await t.paymentEntry(e.task_id), a = Y(i.payment_page_url) || Y(i.payment_url) || i.qr_data;
						a ? n.push(`${e.email || ""}\t${a}`) : r++;
					} catch {
						r++;
					}
					n.length ? (await (e.copyText ? e.copyText(n.join("\n")) : navigator.clipboard.writeText(n.join("\n"))), S(`已复制 ${n.length} 条支付链接${r ? `，跳过 ${r} 个` : ""}`)) : S("所选任务没有可复制的支付入口");
					return;
				}
				if (r !== "sync" && r !== "sync_status") throw Error("不支持的批量操作");
				let o = 0, s = 0;
				for (let e of a) try {
					let r = await t.action(e, "sync_status");
					r.accepted === !0 ? (o++, n.receipt = r) : s++;
				} catch {
					s++;
				}
				S(`已提交同步：${o} 个${s ? `，失败 ${s} 个` : ""}`), await P({ force: !0 });
			} catch (e) {
				n.error = X(e);
			} finally {
				n.bulkBusy = !1;
			}
		}
	}
	async function F(r = {}) {
		let i = n.query.batch;
		if (i && !n.cancellingBatch) {
			n.cancellingBatch = i;
			try {
				if (!r.confirmed && !await (e.confirm ? e.confirm("确认取消当前整批尚未开始的排队任务？运行中与已完成任务保留，不受当前筛选和分页限制。") : window.confirm("确认取消当前整批尚未开始的排队任务？运行中与已完成任务保留。"))) return;
				let a = await t.cancel(i);
				if (a.ok === !1) throw Error(a.error || "取消批次失败");
				n.receipt = a, S(`批次 #${i}：已取消 ${a.cancelled || 0} 个排队任务，跳过 ${a.skipped || 0} 个${a.failed ? `，失败 ${a.failed} 个，可再次处理剩余任务` : ""}。`), await P({ force: !0 });
			} catch (e) {
				n.error = X(e);
			} finally {
				n.cancellingBatch = "";
			}
		}
	}
	async function I(e = !0) {
		try {
			if (e) {
				Se(await t.export({ ...n.query }), "extract-workbench.csv"), S("已导出当前筛选结果（最多 5000 条）");
				return;
			}
			let r = n.items.filter((e) => n.selected.has(String(e.task_id)));
			Se(new Blob([xe(r)], { type: "text/csv;charset=utf-8" }), "extract-workbench-selected.csv");
		} catch (e) {
			n.error = X(e);
		}
	}
	function ne() {
		i++, a++, c++, w(), y.forEach((e) => e.abort()), y.clear(), g = void 0, m = void 0, h = void 0, _.clear(), v.clear(), n.batchPage = d || 1, n.batchLoading = !1, n.loading = !1;
	}
	function re(e) {
		n.visible === e ? e && !n.loading && P() : (n.visible = e, e ? P() : ne());
	}
	function L() {
		document.hidden ? ne() : n.visible && P();
	}
	document.addEventListener("visibilitychange", L);
	function R() {
		r = !0, ne(), document.removeEventListener("visibilitychange", L);
	}
	return {
		state: n,
		load: P,
		loadBatchPage: A,
		setVisible: re,
		switchBatch: ee,
		bulkAction: te,
		cancelBatch: F,
		exportRows: I,
		destroy: R
	};
}
// src/features/extract/useExtractBatch.ts
function Oe(e = {}, t = async () => {}) {
	let n = e.api || z(e), i = s({
		config: null,
		filters: {
			query: "",
			source: "",
			date_from: "",
			date_to: "",
			extract_status: "not_succeeded",
			promotion: "eligible"
		},
		limit: 100,
		workers: 1,
		title: "",
		provider: "",
		mode: "",
		type: "",
		preview: null,
		previewSignature: "",
		receipt: null,
		submissionSignature: "",
		error: "",
		feedback: "",
		creating: !1,
		loading: !1,
		opened: !1
	}), a = !1, o = 0, c = 0, l, u = !1, d = null, f = () => JSON.stringify({
		filters: { ...i.filters },
		limit: Number(i.limit)
	});
	function p() {
		o++, l?.abort(), i.preview = null, i.previewSignature = "", i.loading = !1, i.feedback = "筛选条件已变更，请刷新匹配数量。";
	}
	let m = r(() => f(), p, { flush: "sync" });
	function h(e) {
		i.provider = e;
		let t = i.config?.providers.find((t) => t.id === e), n = ue(t), r = de(t);
		i.mode = n.includes(i.mode) ? i.mode : n.includes("extract_only") ? "extract_only" : n.includes("manual_payment") ? "manual_payment" : "", i.type = r.includes(i.type) ? i.type : r.includes(t?.default_type || "") ? t.default_type : r[0] || "";
	}
	async function g(e) {
		i.opened = !0, i.error = "";
		let t = ++c, r = e || await n.config();
		if (!a && t === c && i.opened) {
			if (i.config = r, !u) {
				let e = _(), t = r.batch_workers_default;
				i.workers = Number.isInteger(t) && Number(t) >= 1 && Number(t) <= e ? t : 1, u = !0;
			}
			h(r.providers.some((e) => e.id === i.provider) ? i.provider : r.providers.some((e) => e.id === r.default_provider) ? r.default_provider : r.providers[0]?.id || "");
		}
	}
	function _() {
		let e = i.config?.batch_workers_max;
		return Number.isInteger(e) && Number(e) >= 1 && Number(e) <= 50 ? e : 50;
	}
	async function v() {
		if (a || !i.opened) return;
		l?.abort(), l = new AbortController();
		let e = ++o, t = f(), r = { ...i.filters }, s = Number(i.limit);
		i.preview = null, i.previewSignature = "", i.loading = !0, i.error = "";
		try {
			if (!Number.isInteger(s) || s < 1 || s > 5e3) throw Error("本批运行数量须为 1 至 5000 的整数");
			let c = await n.candidates(r, s, l.signal);
			if (a || e !== o || !i.opened || t !== f()) return;
			if (!Number.isSafeInteger(c.total) || !Number.isSafeInteger(c.selected_count) || c.selected_count < 0 || c.selected_count > s) throw Error("候选统计响应无效");
			i.preview = c, i.previewSignature = t, i.feedback = `匹配 ${c.total.toLocaleString("zh-CN")} 个可用账号，本批计划运行 ${c.selected_count.toLocaleString("zh-CN")} 个。`;
		} catch (t) {
			!a && e === o && i.opened && (i.error = `匹配数量统计失败：${X(t)}`, i.feedback = "请检查筛选条件后重试。");
		} finally {
			e === o && (i.loading = !1);
		}
	}
	async function y() {
		if (!a && !i.creating && i.opened && i.preview?.selected_count && i.previewSignature === f()) {
			i.creating = !0, i.error = "";
			try {
				let r = i.config?.providers.find((e) => e.id === i.provider), o = ue(r), s = de(r), c = Number(i.workers), l = Number(i.limit);
				if (!r || !o.includes(i.mode) || !s.includes(i.type)) throw Error("请选择平台公布的运行模式和提链类型");
				if (!Number.isInteger(c) || c < 1 || c > _()) throw Error(`批次并发请输入 1 到 ${_()} 的整数`);
				let u = {
					workers: c,
					title: i.title.trim(),
					provider_id: i.provider,
					mode: i.mode,
					type: i.type,
					filters: { ...i.filters },
					limit: l
				}, f = JSON.stringify(u);
				if (u.mode === "auto_payment" && !await (e.confirm ? e.confirm(`将为本批约 ${i.preview.selected_count} 个账号启用自动支付任务${pe({
					...r,
					mode: u.mode
				})}，确认继续？`) : window.confirm("确认继续此批自动支付任务？")) || a || !i.opened || f !== JSON.stringify({
					workers: Number(i.workers),
					title: i.title.trim(),
					provider_id: i.provider,
					mode: i.mode,
					type: i.type,
					filters: { ...i.filters },
					limit: Number(i.limit)
				})) return;
				d && d.signature === f || (d = {
					signature: f,
					id: globalThis.crypto.randomUUID()
				}, i.receipt = null), i.submissionSignature = f;
				let p = {
					...u,
					submission_id: d.id
				}, m = await n.create(p), h = {
					...m,
					submission_id: d.id
				};
				i.receipt = h, i.preview = null, i.previewSignature = "", d = null, i.feedback = `已创建批次，入队 ${m.started || 0} 个任务，跳过 ${m.skipped || 0} 个，提交失败 ${m.failed || 0} 个。`, i.error = "";
				try {
					await t();
				} catch {}
				return h;
			} catch (e) {
				i.error = `${X(e)}；可重试获取同一批次的提交结果。`;
			} finally {
				i.creating = !1;
			}
		}
	}
	function b() {
		i.opened = !1, c++, p();
	}
	function x() {
		a = !0, b(), m();
	}
	return {
		state: i,
		open: g,
		setProvider: h,
		workersMax: _,
		preview: v,
		invalidate: p,
		submit: y,
		close: b,
		destroy: x
	};
}
// src/features/extract/useExtractArtifacts.ts
function ke(e = {}, t = async () => {}) {
	let n = e.api || z(e), r = s({
		detail: null,
		detailLoading: !1,
		detailError: "",
		drawer: !1,
		nodeA: {
			entry: null,
			taskId: null,
			loading: !1,
			error: ""
		},
		payment: {
			entry: null,
			taskId: null,
			loading: !1,
			error: "",
			open: !1
		},
		receipt: null,
		error: "",
		busy: /* @__PURE__ */ new Set()
	}), i = !1, a = 0, o = 0, c = 0, l, u, d, f = (t) => e.notify?.(t);
	async function p(t) {
		if (!t) throw Error("没有可复制内容");
		await (e.copyText ? e.copyText(t) : navigator.clipboard.writeText(t)), f("已复制");
	}
	async function m(e) {
		e = M(e);
		let t = ++a;
		l?.abort(), S(), l = new AbortController(), r.drawer = !0, r.detail = null, r.detailLoading = !0, r.detailError = "";
		try {
			let o = await n.detail(e, l.signal);
			!i && t === a && r.drawer && (r.detail = o, (o.item.has_payment_entry || o.item.has_payment_link || o.item.has_qr) && h(e));
		} catch (e) {
			!i && t === a && (r.detailError = X(e));
		} finally {
			t === a && (r.detailLoading = !1);
		}
	}
	async function h(e) {
		e = M(e);
		let t = ++c;
		d?.abort(), d = new AbortController(), r.nodeA = {
			entry: null,
			taskId: e,
			loading: !0,
			error: ""
		};
		try {
			let a = await n.paymentEntry(e, d.signal);
			if (!a.entry) throw Error("当前任务没有已保存的支付入口");
			!i && r.drawer && t === c && N(r.detail?.item.task_id, e) && (r.nodeA.entry = a.entry);
		} catch (e) {
			!i && r.drawer && t === c && (r.nodeA.error = X(e));
		} finally {
			t === c && (r.nodeA.loading = !1);
		}
	}
	async function g(e) {
		e = M(e);
		let t = ++o;
		u?.abort(), u = new AbortController(), r.payment = {
			entry: null,
			taskId: e,
			loading: !0,
			error: "",
			open: !0
		};
		try {
			let a = await n.paymentEntry(e, u.signal);
			if (!a.entry) throw Error("当前任务没有已保存的支付入口");
			!i && t === o && r.payment.open && (r.payment.entry = a.entry);
		} catch (e) {
			!i && t === o && (r.payment.error = X(e));
		} finally {
			t === o && (r.payment.loading = !1);
		}
	}
	async function _(a, o) {
		a = M(a);
		let s = String(a);
		if (!(i || r.busy.has(s))) {
			r.busy.add(s), r.error = "";
			try {
				if (![
					"sync_status",
					"retry",
					"manual_payment",
					"auto_payment"
				].includes(o)) throw Error("不支持的任务操作");
				let i = N(r.detail?.item.task_id, a) ? r.detail.item : (await n.detail(a)).item;
				if (me(i)) throw Error("任务正在执行，请等待当前运行结束");
				if (o !== "sync_status" && !ge(i)) throw Error("远端结果尚未确认，请同步原任务状态，不能重新提交");
				if (o === "auto_payment" && !await (e.confirm ? e.confirm("确认查询并继续此任务已保存的自动支付原单？") : window.confirm("确认继续此任务的自动支付？"))) return;
				let s = await n.action(a, o);
				if (s.accepted !== !0) throw Error(s.error || "操作未接受");
				r.receipt = s, f("任务操作已提交");
				try {
					await t();
				} catch {}
			} catch (e) {
				r.error = X(e), f(r.error);
			} finally {
				r.busy.delete(s);
			}
		}
	}
	async function v(e, t) {
		let i = `link:${e}:${t}`;
		if (!r.busy.has(i)) {
			r.busy.add(i), r.error = "";
			try {
				if (!["extract", "payment"].includes(t)) throw Error("不支持的链接类型");
				let r = await n.links(M(e), t), i = Y(r.url || r.link);
				if (!i) throw Error("服务端未返回有效链接");
				t === "extract" ? await p(i) : window.open(i, "_blank", "noopener,noreferrer");
			} catch (e) {
				r.error = X(e), f(r.error);
			} finally {
				r.busy.delete(i);
			}
		}
	}
	async function y(e, t) {
		let i = `copy:${e}:${t}`;
		if (!r.busy.has(i)) {
			r.busy.add(i);
			try {
				if (t === "at") {
					let t = N(r.detail?.item.task_id, e) ? r.detail : await n.detail(e);
					if (!t.item.account_id) throw Error("任务未记录账号");
					await p((await n.secret(t.item.account_id)).value || "");
				} else if (t === "email") await p((N(r.detail?.item.task_id, e) ? r.detail : await n.detail(e)).item.email || "");
				else throw Error("不支持的复制类型");
			} catch (e) {
				r.error = X(e), f(r.error);
			} finally {
				r.busy.delete(i);
			}
		}
	}
	async function b(e) {
		try {
			await p(e === "qr_data" ? String(r.payment.entry?.qr_data || "") : Y(r.payment.entry?.[e]));
		} catch (e) {
			r.payment.error = X(e);
		}
	}
	async function x(e) {
		try {
			await p(e === "qr_data" ? String(r.nodeA.entry?.qr_data || "") : Y(r.nodeA.entry?.[e]));
		} catch (e) {
			r.nodeA.error = X(e);
		}
	}
	function S() {
		c++, d?.abort(), r.nodeA = {
			entry: null,
			taskId: null,
			loading: !1,
			error: ""
		};
	}
	function C() {
		a++, l?.abort(), S(), r.drawer = !1, r.detail = null, r.detailLoading = !1, r.detailError = "";
	}
	function w() {
		o++, u?.abort(), r.payment = {
			entry: null,
			taskId: null,
			loading: !1,
			error: "",
			open: !1
		};
	}
	function T() {
		C(), w();
	}
	function E() {
		i = !0, T();
	}
	return {
		state: r,
		openDetail: m,
		loadNodeA: h,
		showPaymentEntry: g,
		taskAction: _,
		showLink: v,
		copy: y,
		copyPayment: b,
		copyNodeA: x,
		closeDetail: C,
		closePayment: w,
		closeDialogs: T,
		destroy: E
	};
}
// src/features/extract/ExtractFilters.vue?vue&type=script&setup=true&lang.ts
var Ae = { class: "extract-filter-fields" }, je = { key: 0 }, Me = ["value"], Ne = ["value"], Pe = ["value"], Fe = ["value"], Ie = ["value"], Le = ["value"], Q = ["value"], Re = ["value"], ze = ["value", "disabled"], Be = ["value"], Ve = ["value"], He = { class: "list-filter-actions" }, Ue = /*#__PURE__*/ D(/* @__PURE__ */ e({
	__name: "ExtractFilters",
	props: {
		column: {},
		values: {},
		providers: {},
		batches: {},
		counts: {},
		batchBusy: { type: Boolean },
		omitBatch: { type: Boolean },
		open: { type: Boolean }
	},
	emits: ["update:open", "change"],
	setup(e, { emit: r }) {
		let o = {
			query: "账号",
			provider: "平台",
			mode: "模式",
			status: "提链状态",
			batch: "批次"
		}, s = e, l = r, f = g("query"), h = C(() => s.column || f.value), b = C(() => s.values[h.value]);
		function x(e) {
			l("change", h.value, e);
		}
		return (r, s) => (t(), v(I, {
			label: e.column ? o[e.column] : "提链任务",
			"trigger-label": e.column ? o[e.column] : "筛选",
			active: e.column ? !!e.values[e.column] : Object.values(e.values).some(Boolean),
			summary: b.value,
			open: e.open,
			"onUpdate:open": s[9] ||= (e) => l("update:open", e)
		}, {
			default: n(() => [y("div", Ae, [
				e.column ? u("", !0) : (t(), O("label", je, [s[10] ||= k("筛选列", -1), i(y("select", {
					"onUpdate:modelValue": s[0] ||= (e) => f.value = e,
					"aria-label": "选择提链任务筛选列"
				}, [(t(), O(m, null, a(o, (n, r) => (t(), O(m, { key: r }, [r !== "batch" || !e.omitBatch ? (t(), O("option", {
					key: 0,
					value: r
				}, _(n), 9, Me)) : u("", !0)], 64))), 64))], 512), [[d, f.value]])])),
				y("label", null, [k(_(o[h.value]) + " ", 1), h.value === "query" ? (t(), O("input", {
					key: 0,
					type: "search",
					value: b.value,
					"aria-label": "筛选账号值",
					placeholder: "邮箱或任务号",
					onChange: s[1] ||= (e) => x(e.target.value),
					onKeydown: s[2] ||= p((e) => l("update:open", !1), ["enter"])
				}, null, 40, Ne)) : h.value === "provider" ? (t(), O("select", {
					key: 1,
					value: b.value,
					"aria-label": "筛选平台值",
					onChange: s[3] ||= (e) => x(e.target.value)
				}, [s[11] ||= y("option", { value: "" }, "全部平台", -1), (t(!0), O(m, null, a(e.providers, (e) => (t(), O("option", {
					key: e.id,
					value: e.id
				}, _(e.label || e.id), 9, Fe))), 128))], 40, Pe)) : h.value === "mode" ? (t(), O("select", {
					key: 2,
					value: b.value,
					"aria-label": "筛选模式值",
					onChange: s[4] ||= (e) => x(e.target.value)
				}, [s[12] ||= y("option", { value: "" }, "全部模式", -1), (t(), O(m, null, a([
					"extract_only",
					"manual_payment",
					"auto_payment"
				], (e) => y("option", {
					key: e,
					value: e
				}, _(E(ce)(e)), 9, Le)), 64))], 40, Ie)) : h.value === "status" ? (t(), O("select", {
					key: 3,
					value: b.value,
					"aria-label": "筛选提链状态值",
					onChange: s[5] ||= (e) => x(e.target.value)
				}, [(t(!0), O(m, null, a(E(se), (n) => (t(), O("option", {
					key: n[0],
					value: n[0]
				}, _(n[1]) + _(e.counts && e.counts[n[0] || "all"] !== void 0 ? ` (${e.counts[n[0] || "all"]})` : ""), 9, Re))), 128))], 40, Q)) : (t(), O("select", {
					key: 4,
					value: b.value,
					disabled: e.batchBusy,
					"aria-label": "筛选批次值",
					onChange: s[6] ||= (e) => x(e.target.value)
				}, [
					s[13] ||= y("option", { value: "" }, "全部任务", -1),
					b.value && !e.batches.some((e) => String(e.batch_id) === b.value) ? (t(), O("option", {
						key: 0,
						value: b.value
					}, "批次 #" + _(b.value), 9, Be)) : u("", !0),
					(t(!0), O(m, null, a(e.batches, (e) => (t(), O("option", {
						key: String(e.batch_id),
						value: String(e.batch_id)
					}, _(e.title || `批次 #${e.batch_id}`), 9, Ve))), 128))
				], 40, ze))]),
				h.value === "batch" ? c(r.$slots, "default", {}, void 0, !0, 1) : u("", !0),
				y("div", He, [y("button", {
					type: "button",
					onClick: s[7] ||= (e) => x("")
				}, "清除此列"), y("button", {
					type: "button",
					class: "list-filter-primary",
					onClick: s[8] ||= (e) => l("update:open", !1)
				}, "完成")])
			])]),
			_: 3
		}, 8, [
			"label",
			"trigger-label",
			"active",
			"summary",
			"open"
		]));
	}
}), [["__scopeId", "data-v-b1b60c82"]]), We = ["aria-busy"], Ge = { class: "extract-toolbar" }, Ke = { class: "extract-title" }, qe = {
	key: 0,
	class: "extract-metrics",
	"aria-label": "提链概况"
}, Je = { class: "extract-toolbar-actions" }, Ye = { class: "extract-list-panel" }, Xe = {
	class: "extract-count-row",
	"data-extract-count-row": ""
}, Ze = { class: "extract-count-main" }, Qe = { class: "extract-count" }, $e = { class: "extract-count-actions" }, et = {
	key: 0,
	class: "extract-batch-message",
	role: "status"
}, tt = {
	key: 1,
	class: "extract-batch-message",
	role: "alert"
}, nt = { class: "extract-mobile-filter" }, rt = ["title", "disabled"], it = {
	key: 0,
	class: "notice error",
	role: "alert"
}, at = {
	key: 1,
	class: "notice error",
	role: "alert"
}, ot = {
	key: 2,
	class: "extract-bulk"
}, st = ["disabled"], ct = { "aria-label": "提链任务" }, lt = ["checked"], ut = [
	"aria-label",
	"checked",
	"onChange"
], dt = { key: 0 }, ft = { key: 1 }, pt = { key: 2 }, mt = { class: "extract-row-actions" }, ht = ["onClick"], gt = ["disabled", "onClick"], _t = {
	key: 0,
	class: "empty",
	role: "status"
}, vt = { class: "extract-form-grid" }, yt = ["value"], bt = ["value"], xt = ["value"], St = ["value"], Ct = ["value"], wt = ["value"], Tt = ["max"], Et = { class: "extract-hint" }, Dt = { role: "status" }, Ot = {
	key: 0,
	class: "error",
	role: "alert"
}, kt = ["disabled"], At = ["disabled"], jt = {
	key: 0,
	role: "status"
}, Mt = {
	key: 1,
	class: "error",
	role: "alert"
}, Nt = {
	class: "extract-detail-actions",
	role: "group",
	"aria-label": "任务操作"
}, Pt = ["disabled"], Ft = ["disabled"], It = ["disabled"], Lt = { class: "extract-facts" }, Rt = {
	key: 0,
	"aria-label": "阶段证据"
}, zt = {
	key: 1,
	class: "extract-facts"
}, Bt = {
	key: 2,
	class: "notice"
}, Vt = {
	class: "extract-node-a",
	"data-extract-node-a": ""
}, Ht = {
	key: 0,
	role: "status"
}, Ut = {
	key: 1,
	role: "alert"
}, Wt = { class: "extract-detail-actions" }, Gt = ["href"], Kt = ["onClick"], qt = ["src"], Jt = { key: 1 }, Yt = { key: 2 }, Xt = { key: 3 }, Zt = { key: 3 }, Qt = { class: "extract-timeline" }, $t = { key: 0 }, en = { key: 0 }, tn = {
	key: 4,
	"data-extract-history": ""
}, nn = { "data-extract-run-outcome": "" }, rn = {
	key: 0,
	role: "status"
}, an = {
	key: 0,
	class: "error",
	role: "alert"
}, on = { class: "extract-facts" }, sn = ["href"], cn = ["onClick"], ln = { key: 1 }, un = ["src"], dn = { key: 1 }, fn = { key: 1 }, pn = /*#__PURE__*/ D(/* @__PURE__ */ e({
	__name: "ExtractWorkbench",
	props: { deps: {} },
	setup(e, { expose: s }) {
		let c = e.deps || {}, p = De(c), h = Oe(c, () => p.load({ force: !0 })), w = ke(c, () => p.load({ force: !0 })), D = g(c.visible !== !1), A = g(!1), j = g(), M = g(), N = g(), P = p.state.query, I = C(() => p.state.selected);
		C(() => Math.max(1, Math.ceil(p.state.total / P.size)));
		let L = C(() => p.state.config?.providers || h.state.config?.providers || []), R = g(), z = 0, ie = C(() => p.state.items.length > 0 && p.state.items.every((e) => I.value.has(String(e.task_id))));
		ee(j, () => A.value, () => D.value), ee(M, () => !!w.state.drawer, () => D.value), ee(N, () => !!w.state.payment.open, () => D.value);
		let B = g(null), V = C(() => ({
			query: P.query,
			provider: P.provider,
			mode: P.mode,
			status: P.status,
			batch: P.batch
		})), W = {
			query: "账号",
			provider: "平台",
			mode: "模式",
			status: "提链状态",
			batch: "批次"
		}, K = C(() => Object.entries(V.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${W[e]}：${e === "provider" ? L.value.find((e) => e.id === t)?.label || U(t) : e === "mode" ? ce(t) : e === "status" ? se.find((e) => e[0] === t)?.[1] || t : e === "batch" ? p.state.batchDetail?.title || `#${t}` : t}`,
			removeLabel: `清除${W[e]}筛选`
		})));
		function q(e, t) {
			B.value = null, e === "batch" ? gn(t) : (P[e] = t, P.page = 1, hn());
		}
		function fe() {
			Object.assign(P, {
				query: "",
				provider: "",
				mode: "",
				status: "",
				page: 1
			}), gn("");
		}
		function he(e) {
			P.page = e, hn();
		}
		function _e(e) {
			P.page = 1, P.size = e, hn();
		}
		let X = C(() => p.state.batchDetail?.title || `批次 #${P.batch}`);
		function xe(e) {
			p.loadBatchPage(e);
		}
		let Se = C(() => [...L.value, ...(p.state.config?.unavailable_providers || []).filter((e) => !L.value.some((t) => t.id === e.id)).map((e) => ({
			...e,
			label: `${e.label || U(e.id)}（已停用）`
		}))]), we = C(() => L.value.find((e) => e.id === h.state.provider)), Z = C(() => w.state.detail?.item), Ee = C(() => Y(w.state.payment.entry?.payment_page_url)), Ae = C(() => Y(w.state.payment.entry?.payment_url)), je = g(0), Me = g(!1), Ne = C(() => ve(w.state.nodeA.entry || {}));
		r(() => w.state.nodeA.entry, () => {
			je.value = 0, Me.value = !1;
		});
		function Pe() {
			je.value + 1 < Ne.value.length ? je.value++ : Me.value = !0;
		}
		let Fe = g(0), Ie = g(!1), Le = g(Date.now()), Q;
		r(() => w.state.payment.open, (e) => {
			Q && clearInterval(Q), Q = void 0, e && (Le.value = Date.now(), Q = setInterval(() => {
				Le.value = Date.now();
			}, 1e3));
		}), b(() => {
			Q && clearInterval(Q);
		});
		let Re = C(() => ve(w.state.payment.entry || {}));
		function ze() {
			Fe.value + 1 < Re.value.length ? Fe.value++ : Ie.value = !0;
		}
		async function Be(e) {
			Fe.value = 0, Ie.value = !1, await w.showPaymentEntry(e);
		}
		let Ve = Ce;
		function He(e) {
			let t = H(e.status || e.task_status, "状态未记录"), n = e.error_info?.summary || e.error_message || e.error || e.message || "";
			return n ? `${t} · ${n}` : t;
		}
		function pn() {
			h.setProvider(h.state.provider);
		}
		function mn() {
			R.value && (R.value.scrollTop = 0, R.value.scrollLeft = 0);
		}
		async function hn(e = {}) {
			let t = e.quiet ? z : ++z;
			await p.load(e), !e.quiet && t === z && D.value && !p.state.error && mn();
		}
		async function gn(e) {
			let t = ++z;
			await p.switchBatch(e), t === z && D.value && !p.state.error && mn();
		}
		function _n(e, t, n) {
			if (e.target !== t || !t) return;
			let r = t.getBoundingClientRect();
			(e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) && n();
		}
		function $() {
			A.value = !1, h.close();
		}
		function vn() {
			$(), w.closeDialogs();
		}
		function yn(e) {
			D.value = e, p.setVisible(e), e || (B.value = null, $(), w.closeDialogs());
		}
		function bn(e) {
			I.value.has(e) ? I.value.delete(e) : I.value.add(e);
		}
		function xn(e) {
			p.state.items.forEach((t) => e ? I.value.add(String(t.task_id)) : I.value.delete(String(t.task_id)));
		}
		async function Sn() {
			A.value = !0, await h.open(p.state.config || void 0), await h.preview();
		}
		async function Cn() {
			let e = await h.submit();
			e?.batch_id && ($(), await gn(e.batch_id));
		}
		async function wn() {
			await hn({ force: !0 });
		}
		return o(() => p.load()), b(() => {
			p.destroy(), h.destroy(), w.destroy();
		}), s({
			load: hn,
			setVisible: yn,
			openCreate: Sn,
			switchBatch: gn,
			openDetail: w.openDetail,
			showPaymentEntry: Be,
			taskAction: w.taskAction,
			showLink: w.showLink,
			copy: w.copy,
			copyPayment: w.copyPayment,
			bulkAction: p.bulkAction,
			cancelBatch: p.cancelBatch,
			exportRows: p.exportRows,
			closeDialogs: vn
		}), (e, r) => (t(), O("section", {
			class: "extract-page",
			"aria-busy": E(p).state.loading
		}, [
			y("header", Ge, [y("div", Ke, [r[53] ||= y("h1", null, "提链工作台", -1), E(p).state.summary ? (t(), O("div", qe, [
				y("span", null, [r[50] ||= k("今日出链 ", -1), y("strong", null, _(E(G)(E(p).state.summary.today_extracted)), 1)]),
				y("span", null, [r[51] ||= k("待支付 ", -1), y("strong", null, _(E(G)(E(p).state.summary.awaiting_payment)), 1)]),
				y("span", null, [r[52] ||= k("待核对 ", -1), y("strong", null, _(E(G)(E(p).state.summary.needs_review)), 1)])
			])) : u("", !0)]), y("div", Je, [
				y("button", {
					type: "button",
					class: "extract-button",
					onClick: wn
				}, "刷新"),
				y("button", {
					type: "button",
					class: "extract-button",
					onClick: r[0] ||= (e) => E(p).exportRows(!0)
				}, "导出当前筛选"),
				y("button", {
					type: "button",
					class: "extract-button primary",
					onClick: Sn
				}, "新建批次")
			])]),
			y("div", Ye, [
				y("div", Xe, [y("div", Ze, [y("span", Qe, "共 " + _(E(G)(E(p).state.total)) + " 条任务", 1), l(ne, {
					items: K.value,
					onRemove: r[1] ||= (e) => q(e, "")
				}, null, 8, ["items"])]), y("div", $e, [
					K.value.length ? (t(), O("button", {
						key: 0,
						type: "button",
						class: "extract-inline-button",
						onClick: fe
					}, "清除筛选")) : u("", !0),
					l(Ue, {
						column: "batch",
						values: V.value,
						providers: Se.value,
						batches: E(p).state.batches,
						"batch-busy": E(p).state.batchLoading,
						open: B.value === "batch",
						"onUpdate:open": r[3] ||= (e) => B.value = e ? "batch" : null,
						onChange: q
					}, {
						default: n(() => [
							E(p).state.batchLoading ? (t(), O("p", et, "正在读取批次…")) : u("", !0),
							E(p).state.auxErrors.batches ? (t(), O("div", tt, [r[54] ||= k(" 批次读取失败 ", -1), y("button", {
								type: "button",
								class: "extract-inline-button",
								onClick: r[2] ||= (e) => xe(E(p).state.batchPage)
							}, "重试")])) : u("", !0),
							E(p).state.batchTotal > 20 ? (t(), v(te, {
								key: 2,
								class: "extract-batch-pager",
								label: "提链批次分页",
								page: E(p).state.batchPage,
								size: 20,
								"page-sizes": [20],
								total: E(p).state.batchTotal,
								busy: E(p).state.batchLoading,
								"onUpdate:page": xe
							}, null, 8, [
								"page",
								"total",
								"busy"
							])) : u("", !0)
						]),
						_: 1
					}, 8, [
						"values",
						"providers",
						"batches",
						"batch-busy",
						"open"
					]),
					y("span", nt, [l(Ue, {
						"omit-batch": "",
						values: V.value,
						providers: Se.value,
						batches: E(p).state.batches,
						counts: E(p).state.counts,
						open: B.value === "all",
						"onUpdate:open": r[4] ||= (e) => B.value = e ? "all" : null,
						onChange: q
					}, null, 8, [
						"values",
						"providers",
						"batches",
						"counts",
						"open"
					])]),
					E(P).batch ? (t(), O("button", {
						key: 1,
						type: "button",
						class: "extract-inline-button extract-cancel",
						title: X.value,
						disabled: !!E(p).state.cancellingBatch,
						onClick: r[5] ||= (e) => E(p).cancelBatch()
					}, "取消当前批次", 8, rt)) : u("", !0)
				])]),
				E(p).state.error ? (t(), O("p", it, [k(_(E(p).state.error) + " ", 1), y("button", {
					type: "button",
					class: "extract-inline-button",
					onClick: wn
				}, "重试")])) : u("", !0),
				E(w).state.error ? (t(), O("p", at, _(E(w).state.error), 1)) : u("", !0),
				I.value.size ? (t(), O("div", ot, [
					y("strong", null, "已选 " + _(I.value.size) + " 项", 1),
					y("button", {
						type: "button",
						class: "extract-button",
						disabled: E(p).state.bulkBusy,
						onClick: r[6] ||= (e) => E(p).bulkAction("sync_status")
					}, "同步原单", 8, st),
					y("button", {
						type: "button",
						class: "extract-button",
						onClick: r[7] ||= (e) => E(p).bulkAction("links")
					}, "复制支付链接"),
					y("button", {
						type: "button",
						class: "extract-button",
						onClick: r[8] ||= (e) => E(p).exportRows(!1)
					}, "导出选中"),
					y("button", {
						type: "button",
						class: "extract-inline-button",
						onClick: r[9] ||= (e) => E(p).bulkAction("clear")
					}, "清除选择")
				])) : u("", !0),
				y("div", {
					ref_key: "tableScroll",
					ref: R,
					class: "extract-table-wrap",
					role: "region",
					"aria-label": "提链任务表格",
					tabindex: "0"
				}, [y("table", ct, [y("thead", null, [y("tr", null, [
					y("th", null, [y("input", {
						type: "checkbox",
						"aria-label": "选择本页提链任务",
						checked: ie.value,
						onChange: r[10] ||= (e) => xn(e.target.checked)
					}, null, 40, lt)]),
					(t(), O(m, null, a([
						"query",
						"provider",
						"mode"
					], (e) => y("th", { key: e }, [l(Ue, {
						column: e,
						values: V.value,
						providers: Se.value,
						batches: E(p).state.batches,
						counts: E(p).state.counts,
						open: B.value === e,
						"onUpdate:open": (t) => B.value = t ? e : null,
						onChange: q
					}, null, 8, [
						"column",
						"values",
						"providers",
						"batches",
						"counts",
						"open",
						"onUpdate:open"
					])])), 64)),
					r[55] ||= y("th", null, "准备", -1),
					y("th", null, [l(Ue, {
						column: "status",
						values: V.value,
						providers: Se.value,
						batches: E(p).state.batches,
						counts: E(p).state.counts,
						open: B.value === "status",
						"onUpdate:open": r[11] ||= (e) => B.value = e ? "status" : null,
						onChange: q
					}, null, 8, [
						"values",
						"providers",
						"batches",
						"counts",
						"open"
					])]),
					r[56] ||= y("th", null, "支付", -1),
					r[57] ||= y("th", null, "Plus", -1),
					r[58] ||= y("th", null, "更新时间", -1),
					r[59] ||= y("th", null, "操作", -1)
				])]), y("tbody", null, [(t(!0), O(m, null, a(E(p).state.items, (e) => (t(), O("tr", {
					key: String(e.task_id),
					class: S({ "is-selected": I.value.has(String(e.task_id)) })
				}, [
					y("td", null, [y("input", {
						type: "checkbox",
						"aria-label": `选择提链任务 ${e.task_id}`,
						checked: I.value.has(String(e.task_id)),
						onChange: (t) => bn(String(e.task_id))
					}, null, 40, ut)]),
					y("td", null, [l(F, {
						text: e.email || "账号未记录",
						secondary: `#${e.task_id}`
					}, null, 8, ["text", "secondary"])]),
					y("td", null, [l(F, {
						text: E(U)(e.provider_id),
						secondary: e.link_type || void 0
					}, null, 8, ["text", "secondary"])]),
					y("td", null, [l(F, {
						text: E(ce)(e.mode),
						secondary: E(pe)(e) || void 0
					}, null, 8, ["text", "secondary"])]),
					y("td", null, [l(F, { text: E(H)(e.preflight_status, "未开始") }, null, 8, ["text"])]),
					y("td", null, [l(re, {
						"data-extract-result": "",
						label: E(Ve)(e).label,
						tone: E(Ve)(e).tone,
						title: E(J)(e).detail
					}, {
						details: n(() => [
							y("p", null, _(E(J)(e).label), 1),
							y("p", null, _(E(J)(e).detail), 1),
							e.message ? (t(), O("p", dt, _(e.message), 1)) : u("", !0),
							e.error ? (t(), O("p", ft, _(e.error), 1)) : u("", !0),
							e.progress?.label ? (t(), O("p", pt, _(e.progress.label), 1)) : u("", !0)
						]),
						_: 2
					}, 1032, [
						"label",
						"tone",
						"title"
					])]),
					y("td", null, [l(F, { text: E(H)(e.payment_phase || e.payment_status, "—") }, null, 8, ["text"])]),
					y("td", null, [l(F, { text: E(H)(e.plus_state || e.plus_status, "未核验") }, null, 8, ["text"])]),
					y("td", null, [l(F, { text: E(le)(e.updated_at || e.created_at) }, null, 8, ["text"])]),
					y("td", mt, [y("button", {
						type: "button",
						class: "extract-inline-button",
						onClick: (t) => E(w).openDetail(e.task_id)
					}, "详情", 8, ht), y("button", {
						type: "button",
						class: "extract-button",
						disabled: !(e.has_payment_entry || e.has_payment_link || e.has_qr),
						onClick: (t) => Be(e.task_id)
					}, "支付入口", 8, gt)])
				], 2))), 128))])]), E(p).state.items.length ? u("", !0) : (t(), O("p", _t, _(E(p).state.loading ? "正在读取任务…" : E(p).state.error ? "任务读取失败" : K.value.length ? "没有符合筛选条件的任务" : "暂无提链任务"), 1))], 512),
				l(te, {
					class: "extract-task-pager",
					label: "提链任务分页",
					page: E(P).page,
					size: E(P).size,
					total: E(p).state.total,
					busy: E(p).state.loading,
					"onUpdate:page": he,
					"onUpdate:size": _e
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			]),
			y("dialog", {
				ref_key: "createDialog",
				ref: j,
				class: "extract-dialog",
				"aria-labelledby": "extract-create-title",
				onCancel: x($, ["prevent"]),
				onClose: $,
				onClick: r[32] ||= (e) => _n(e, j.value, $)
			}, [
				y("header", null, [r[60] ||= y("h2", { id: "extract-create-title" }, "新建提链批次", -1), y("button", {
					type: "button",
					onClick: $
				}, "关闭")]),
				y("div", vt, [
					y("label", null, [r[61] ||= k("批次名称", -1), i(y("input", { "onUpdate:modelValue": r[12] ||= (e) => E(h).state.title = e }, null, 512), [[T, E(h).state.title]])]),
					y("label", null, [r[62] ||= k("账号搜索", -1), i(y("input", {
						"onUpdate:modelValue": r[13] ||= (e) => E(h).state.filters.query = e,
						onInput: r[14] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, null, 544), [[T, E(h).state.filters.query]])]),
					y("label", null, [r[64] ||= k("来源", -1), i(y("select", {
						"onUpdate:modelValue": r[15] ||= (e) => E(h).state.filters.source = e,
						onChange: r[16] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, [r[63] ||= y("option", { value: "" }, "全部来源", -1), (t(!0), O(m, null, a(E(c).accountSources || {}, (e, n) => (t(), O("option", {
						key: n,
						value: n
					}, _(e), 9, yt))), 128))], 544), [[d, E(h).state.filters.source]])]),
					y("label", null, [r[65] ||= k("注册日期从", -1), i(y("input", {
						"onUpdate:modelValue": r[17] ||= (e) => E(h).state.filters.date_from = e,
						type: "date",
						onChange: r[18] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, null, 544), [[T, E(h).state.filters.date_from]])]),
					y("label", null, [r[66] ||= k("注册日期至", -1), i(y("input", {
						"onUpdate:modelValue": r[19] ||= (e) => E(h).state.filters.date_to = e,
						type: "date",
						onChange: r[20] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, null, 544), [[T, E(h).state.filters.date_to]])]),
					y("label", null, [r[68] ||= k("提链状态", -1), i(y("select", {
						"onUpdate:modelValue": r[21] ||= (e) => E(h).state.filters.extract_status = e,
						onChange: r[22] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, [...r[67] ||= [f("<option value=\"not_succeeded\" data-v-21cc7a36>未成功提链</option><option value=\"all\" data-v-21cc7a36>全部可用账号</option><option value=\"failed\" data-v-21cc7a36>失败</option><option value=\"never\" data-v-21cc7a36>从未提链</option><option value=\"success\" data-v-21cc7a36>已成功提链</option>", 5)]], 544), [[d, E(h).state.filters.extract_status]])]),
					y("label", null, [r[69] ||= k("套餐优惠", -1), i(y("select", {
						"onUpdate:modelValue": r[23] ||= (e) => E(h).state.filters.promotion = e,
						onChange: r[24] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, [(t(!0), O(m, null, a(E(oe), (e, n) => (t(), O("option", {
						key: n,
						value: n
					}, _(e), 9, bt))), 128))], 544), [[d, E(h).state.filters.promotion]])]),
					y("label", null, [r[70] ||= k("本批运行数量", -1), i(y("input", {
						"onUpdate:modelValue": r[25] ||= (e) => E(h).state.limit = e,
						type: "number",
						min: "1",
						max: "5000",
						step: "1",
						onInput: r[26] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, null, 544), [[
						T,
						E(h).state.limit,
						void 0,
						{ number: !0 }
					]])]),
					y("label", null, [r[71] ||= k("平台", -1), i(y("select", {
						"onUpdate:modelValue": r[27] ||= (e) => E(h).state.provider = e,
						onChange: pn
					}, [(t(!0), O(m, null, a(L.value, (e) => (t(), O("option", {
						key: e.id,
						value: e.id
					}, _(e.label || E(U)(e.id)), 9, xt))), 128)), (t(!0), O(m, null, a(E(h).state.config?.unavailable_providers || [], (e) => (t(), O("option", {
						key: e.id,
						value: e.id,
						disabled: ""
					}, _(e.label || E(U)(e.id)) + "（" + _(e.unavailable_reason || "已停用") + "）", 9, St))), 128))], 544), [[d, E(h).state.provider]])]),
					y("label", null, [r[72] ||= k("模式", -1), i(y("select", { "onUpdate:modelValue": r[28] ||= (e) => E(h).state.mode = e }, [(t(!0), O(m, null, a(E(ue)(we.value), (e) => (t(), O("option", {
						key: e,
						value: e
					}, _(E(ce)(e)), 9, Ct))), 128))], 512), [[d, E(h).state.mode]])]),
					y("label", null, [r[73] ||= k("链接类型", -1), i(y("select", { "onUpdate:modelValue": r[29] ||= (e) => E(h).state.type = e }, [(t(!0), O(m, null, a(E(de)(we.value), (e) => (t(), O("option", {
						key: e,
						value: e
					}, _(E(ae)[e] || e), 9, wt))), 128))], 512), [[d, E(h).state.type]])]),
					y("label", null, [r[74] ||= k("并发", -1), i(y("input", {
						"onUpdate:modelValue": r[30] ||= (e) => E(h).state.workers = e,
						type: "number",
						min: "1",
						max: E(h).workersMax(),
						step: "1"
					}, null, 8, Tt), [[
						T,
						E(h).state.workers,
						void 0,
						{ number: !0 }
					]])])
				]),
				y("p", Et, _(E(be)(E(h).state.filters.promotion)), 1),
				y("p", Dt, _(E(h).state.feedback), 1),
				E(h).state.error ? (t(), O("p", Ot, _(E(h).state.error), 1)) : u("", !0),
				y("footer", null, [
					y("button", {
						type: "button",
						disabled: E(h).state.loading || E(h).state.creating,
						onClick: r[31] ||= (...e) => E(h).preview && E(h).preview(...e)
					}, "刷新匹配数量", 8, kt),
					y("button", {
						type: "button",
						class: "primary",
						disabled: E(h).state.creating || !E(h).state.preview?.selected_count,
						onClick: Cn
					}, "创建并运行（" + _(E(h).state.preview?.selected_count || 0) + "）", 9, At),
					y("button", {
						type: "button",
						onClick: $
					}, "取消")
				])
			], 544),
			y("dialog", {
				ref_key: "detailDialog",
				ref: M,
				class: "extract-dialog",
				"aria-labelledby": "extract-detail-title",
				onCancel: r[43] ||= x((...e) => E(w).closeDetail && E(w).closeDetail(...e), ["prevent"]),
				onClick: r[44] ||= (e) => _n(e, M.value, E(w).closeDetail)
			}, [
				y("header", null, [r[75] ||= y("h2", { id: "extract-detail-title" }, "任务详情", -1), y("button", {
					type: "button",
					onClick: r[33] ||= (...e) => E(w).closeDetail && E(w).closeDetail(...e)
				}, "关闭")]),
				E(w).state.detailLoading ? (t(), O("p", jt, "正在读取任务详情…")) : u("", !0),
				E(w).state.detailError ? (t(), O("p", Mt, _(E(w).state.detailError), 1)) : u("", !0),
				Z.value ? (t(), O(m, { key: 2 }, [
					y("h3", null, _(Z.value.email || "账号未记录") + " · #" + _(Z.value.task_id), 1),
					y("div", Nt, [
						y("button", {
							type: "button",
							disabled: E(me)(Z.value),
							onClick: r[34] ||= (e) => E(w).taskAction(Z.value.task_id, "sync_status")
						}, "同步状态", 8, Pt),
						y("button", {
							type: "button",
							disabled: !E(ge)(Z.value),
							onClick: r[35] ||= (e) => E(w).taskAction(Z.value.task_id, "retry")
						}, "重跑", 8, Ft),
						Z.value.mode === "auto_payment" && Z.value.payment_status !== "paid" ? (t(), O("button", {
							key: 0,
							type: "button",
							disabled: E(me)(Z.value),
							onClick: r[36] ||= (e) => E(w).taskAction(Z.value.task_id, "auto_payment")
						}, "查询自动支付", 8, It)) : u("", !0),
						y("button", {
							type: "button",
							onClick: r[37] ||= (e) => E(w).copy(Z.value.task_id, "email")
						}, "复制邮箱"),
						Z.value.account_id ? (t(), O("button", {
							key: 1,
							type: "button",
							onClick: r[38] ||= (e) => E(w).copy(Z.value.task_id, "at")
						}, "复制 AT")) : u("", !0),
						Z.value.has_extract_link ? (t(), O("button", {
							key: 2,
							type: "button",
							onClick: r[39] ||= (e) => E(w).showLink(Z.value.task_id, "extract")
						}, "复制提链链接")) : u("", !0),
						Z.value.has_payment_entry || Z.value.has_payment_link || Z.value.has_qr ? (t(), O("button", {
							key: 3,
							type: "button",
							onClick: r[40] ||= (e) => Be(Z.value.task_id)
						}, "读取支付入口")) : u("", !0)
					]),
					y("p", null, _(E(U)(Z.value.provider_id)) + " · " + _(E(ce)(Z.value.mode)) + _(E(pe)(Z.value)), 1),
					y("p", null, _(E(J)(Z.value).label) + " · " + _(E(J)(Z.value).detail), 1),
					y("dl", Lt, [
						y("div", null, [r[76] ||= y("dt", null, "准备", -1), y("dd", null, _(E(H)(Z.value.preflight_status, "未开始")), 1)]),
						y("div", null, [r[77] ||= y("dt", null, "提链", -1), y("dd", null, _(E(H)(Z.value.extraction_status)), 1)]),
						y("div", null, [r[78] ||= y("dt", null, "支付", -1), y("dd", null, _(E(H)(Z.value.payment_status)), 1)]),
						y("div", null, [r[79] ||= y("dt", null, "本地 Plus 到账核验", -1), y("dd", null, _(E(H)(Z.value.plus_status, "未核验")), 1)])
					]),
					Z.value.stages ? (t(), O("section", Rt, [r[80] ||= y("h3", null, "执行阶段", -1), (t(!0), O(m, null, a(Z.value.stages, (e, n) => (t(), O("div", {
						key: n,
						class: "extract-stage"
					}, [
						y("strong", null, _({
							prepare: "准备",
							run: "运行",
							verify: "核验"
						}[n] || n), 1),
						k(" · " + _(E(H)(e?.state || e?.status)) + " ", 1),
						y("span", null, _(e?.step), 1)
					]))), 128))])) : u("", !0),
					Z.value.payment_order ? (t(), O("dl", zt, [
						y("div", null, [r[81] ||= y("dt", null, "支付订单", -1), y("dd", null, _(Z.value.payment_order.remote_order_id || "等待平台回执"), 1)]),
						y("div", null, [r[82] ||= y("dt", null, "支付提交", -1), y("dd", null, _(Z.value.payment_order.submission_state || "响应缺失"), 1)]),
						y("div", null, [r[83] ||= y("dt", null, "支付状态", -1), y("dd", null, _(E(H)(Z.value.payment_order.payment_state, "支付响应缺失")), 1)])
					])) : u("", !0),
					Z.value.reconcile_halt?.halted ? (t(), O("p", Bt, _(Z.value.reconcile_halt.label || "已停止自动续查，待核对") + " · " + _(Z.value.reconcile_halt.reason), 1)) : u("", !0),
					y("section", Vt, [r[84] ||= y("h3", null, "节点 A · 出手的东西", -1), E(w).state.nodeA.loading ? (t(), O("p", Ht, "读取支付入口中…")) : E(w).state.nodeA.error ? (t(), O("div", Ut, [y("p", null, _(E(w).state.nodeA.error), 1), y("button", {
						type: "button",
						onClick: r[41] ||= (e) => E(w).loadNodeA(Z.value.task_id)
					}, "重新读取节点 A")])) : E(w).state.nodeA.entry ? (t(), O(m, { key: 2 }, [
						y("p", null, "金额 " + _(E(w).state.nodeA.entry.amount ?? "平台未返回") + " " + _(E(w).state.nodeA.entry.currency || "") + " · 有效期 " + _(E(w).state.nodeA.entry.expires_at ? E(le)(E(w).state.nodeA.entry.expires_at) : "平台未返回"), 1),
						y("div", Wt, [(t(), O(m, null, a(["payment_page_url", "payment_url"], (e) => (t(), O(m, { key: e }, [E(Y)(E(w).state.nodeA.entry[e]) ? (t(), O(m, { key: 0 }, [y("a", {
							href: E(Y)(E(w).state.nodeA.entry[e]),
							target: "_blank",
							rel: "noopener noreferrer"
						}, "打开" + _(e === "payment_page_url" ? "支付页面" : "支付入口"), 9, Gt), y("button", {
							type: "button",
							onClick: (t) => E(w).copyNodeA(e)
						}, "复制" + _(e === "payment_page_url" ? "支付页面" : "支付入口"), 9, Kt)], 64)) : u("", !0)], 64))), 64)), E(w).state.nodeA.entry.qr_data ? (t(), O("button", {
							key: 0,
							type: "button",
							onClick: r[42] ||= (e) => E(w).copyNodeA("qr_data")
						}, "复制节点 A 二维码")) : u("", !0)]),
						Ne.value.length && !Me.value ? (t(), O("img", {
							key: 0,
							src: Ne.value[je.value],
							width: "208",
							height: "208",
							alt: "节点 A 支付二维码",
							referrerpolicy: "no-referrer",
							onError: Pe
						}, null, 40, qt)) : Me.value ? (t(), O("p", Jt, "二维码图片加载失败，可使用支付链接或二维码原文。")) : u("", !0),
						E(w).state.nodeA.entry.qr_data ? (t(), O("pre", Yt, _(E(w).state.nodeA.entry.qr_data), 1)) : u("", !0)
					], 64)) : (t(), O("p", Xt, "这一步还没有支付入口"))]),
					Z.value.remote_raw ? (t(), O("details", Zt, [r[85] ||= y("summary", null, "平台原文", -1), y("pre", null, _(Z.value.remote_raw), 1)])) : u("", !0),
					y("section", null, [
						r[86] ||= y("h3", null, "执行时间线", -1),
						y("ol", Qt, [(t(!0), O(m, null, a(E(w).state.detail?.events || [], (e, n) => (t(), O("li", { key: n }, [
							y("strong", null, _(e.label || e.stage || "事件"), 1),
							k(" · " + _(E(H)(e.status, "")) + " · " + _(E(le)(e.at || e.created_at || e.time)), 1),
							e.message ? (t(), O("p", $t, _(e.message), 1)) : u("", !0)
						]))), 128))]),
						E(w).state.detail?.events?.length ? u("", !0) : (t(), O("p", en, "暂无阶段事件"))
					]),
					E(w).state.detail?.history?.length ? (t(), O("details", tn, [y("summary", null, "历史运行 " + _(E(w).state.detail.history.length) + " 次", 1), (t(!0), O(m, null, a(E(w).state.detail.history, (e, n) => (t(), O("article", { key: String(e.run_id || n) }, [
						y("h4", null, "运行 #" + _(e.run_id || n + 1), 1),
						y("p", nn, _(He(e)), 1),
						y("pre", null, _(e), 1)
					]))), 128))])) : u("", !0),
					y("details", null, [r[87] ||= y("summary", null, "完整任务记录", -1), y("pre", null, _(Z.value), 1)])
				], 64)) : u("", !0)
			], 544),
			y("dialog", {
				ref_key: "paymentDialog",
				ref: N,
				class: "extract-dialog",
				"aria-labelledby": "extract-payment-title",
				onCancel: r[48] ||= x((...e) => E(w).closePayment && E(w).closePayment(...e), ["prevent"]),
				onClick: r[49] ||= (e) => _n(e, N.value, E(w).closePayment)
			}, [y("header", null, [r[88] ||= y("h2", { id: "extract-payment-title" }, "支付入口", -1), y("button", {
				type: "button",
				onClick: r[45] ||= (...e) => E(w).closePayment && E(w).closePayment(...e)
			}, "关闭")]), E(w).state.payment.loading ? (t(), O("p", rn, "读取中…")) : (t(), O(m, { key: 1 }, [E(w).state.payment.error ? (t(), O("div", an, [y("p", null, _(E(w).state.payment.error), 1), y("button", {
				type: "button",
				onClick: r[46] ||= (e) => Be(E(w).state.payment.taskId)
			}, "重新读取")])) : u("", !0), E(w).state.payment.entry ? (t(), O(m, { key: 1 }, [
				y("dl", on, [
					y("div", null, [r[89] ||= y("dt", null, "金额", -1), y("dd", null, _(E(w).state.payment.entry.amount ?? "平台未返回") + " " + _(E(w).state.payment.entry.currency || ""), 1)]),
					y("div", null, [r[90] ||= y("dt", null, "平台支付状态", -1), y("dd", null, _(E(ye)(E(w).state.payment.entry.payment_status)), 1)]),
					y("div", null, [r[91] ||= y("dt", null, "平台 Plus 核验", -1), y("dd", null, _(E(ye)(E(w).state.payment.entry.platform_plus_status, !0)), 1)]),
					y("div", null, [r[92] ||= y("dt", null, "有效期至", -1), y("dd", null, _(E(w).state.payment.entry.expires_at ? `${E(le)(E(w).state.payment.entry.expires_at)} · ${E(Te)(E(w).state.payment.entry.expires_at, Le.value)}` : "平台未返回"), 1)])
				]),
				r[95] ||= y("p", { class: "extract-hint" }, "平台 Plus 状态供参考，本地到账以任务中的“Plus 到账核验”为准。", -1),
				(t(), O(m, null, a(["payment_page_url", "payment_url"], (e) => y("section", { key: e }, [y("h3", null, _(e === "payment_page_url" ? "支付页面" : "支付入口"), 1), (e === "payment_page_url" ? Ee.value : Ae.value) ? (t(), O(m, { key: 0 }, [
					y("a", {
						href: e === "payment_page_url" ? Ee.value : Ae.value,
						target: "_blank",
						rel: "noopener noreferrer"
					}, "打开", 8, sn),
					y("button", {
						type: "button",
						onClick: (t) => E(w).copyPayment(e)
					}, "复制", 8, cn),
					y("pre", null, _(e === "payment_page_url" ? Ee.value : Ae.value), 1)
				], 64)) : (t(), O("p", ln, "平台未返回"))])), 64)),
				y("section", null, [r[93] ||= y("h3", null, "支付二维码", -1), Re.value.length && !Ie.value ? (t(), O("img", {
					key: 0,
					src: Re.value[Fe.value],
					width: "208",
					height: "208",
					alt: "平台返回的支付二维码",
					referrerpolicy: "no-referrer",
					onError: ze
				}, null, 40, un)) : (t(), O("p", dn, _(Ie.value ? "二维码图片加载失败。" : "平台未返回二维码图片。") + "可使用支付链接或复制下方二维码原文。", 1))]),
				y("section", null, [r[94] ||= y("h3", null, "二维码原文", -1), E(w).state.payment.entry.qr_data ? (t(), O(m, { key: 0 }, [y("button", {
					type: "button",
					onClick: r[47] ||= (e) => E(w).copyPayment("qr_data")
				}, "复制二维码内容"), y("pre", null, _(E(w).state.payment.entry.qr_data), 1)], 64)) : (t(), O("p", fn, "平台未返回"))])
			], 64)) : u("", !0)], 64))], 544)
		], 8, We));
	}
}), [["__scopeId", "data-v-21cc7a36"]]);
// src/features/extract/useExtractStats.ts
function mn(e = {}) {
	let t = e.api || z(e), n = s({
		days: 30,
		provider: "",
		data: null,
		scope: "",
		error: "",
		loading: !1,
		visible: e.visible !== !1,
		providers: { ...ie }
	}), r = !1, i = 0, a, o = null, c = () => !r && n.visible && !document.hidden;
	async function l() {
		if (!c()) return;
		let r = ++i, s = `${n.days}:${n.provider}`, l = o?.scope === s ? o.data : null;
		a?.abort(), a = new AbortController(), n.loading = !0, n.error = "", n.data = l;
		try {
			let l = await t.analytics(n.days, n.provider, a.signal);
			if (r !== i || !c()) return;
			n.data = l, n.scope = s, o = {
				scope: s,
				data: l
			};
			for (let e of l.providers || []) e.provider_id && (n.providers[e.provider_id] = ie[e.provider_id] || e.provider_id);
			e.onReady?.();
		} catch (e) {
			r === i && c() && (n.error = X(e), n.data = l);
		} finally {
			r === i && (n.loading = !1);
		}
	}
	function u() {
		i++, a?.abort(), n.loading = !1;
	}
	function d(e) {
		n.visible = e, e ? l() : u();
	}
	function f() {
		document.hidden ? u() : n.visible && l();
	}
	document.addEventListener("visibilitychange", f);
	function p() {
		r = !0, u(), document.removeEventListener("visibilitychange", f);
	}
	return {
		state: n,
		load: l,
		setVisible: d,
		destroy: p
	};
}
// src/features/extract/ExtractStats.vue?vue&type=script&setup=true&lang.ts
var hn = ["aria-busy"], gn = { class: "es-heading" }, _n = ["disabled"], $ = { class: "es-controls" }, vn = {
	class: "es-periods",
	role: "group",
	"aria-label": "统计时间范围"
}, yn = [
	"data-extract-stats-days",
	"aria-pressed",
	"onClick"
], bn = ["value"], xn = {
	class: "es-updated",
	role: "status"
}, Sn = {
	key: 0,
	class: "es-notice",
	role: "alert"
}, Cn = {
	key: 1,
	class: "es-empty",
	role: "status"
}, wn = {
	class: "es-today",
	"aria-label": "今日与当前"
}, Tn = { class: "es-scope" }, En = { class: "es-metrics" }, Dn = { class: "es-summary-grid" }, On = { class: "es-panel" }, kn = { class: "es-conversion" }, An = { class: "es-panel" }, jn = { class: "es-state-grid" }, Mn = { class: "es-current" }, Nn = { class: "es-chart-grid" }, Pn = { class: "es-panel es-trend" }, Fn = { class: "es-legend" }, In = {
	viewBox: "0 0 880 242",
	role: "img",
	"aria-label": "每日提链任务、出链和支付趋势"
}, Ln = ["y1", "y2"], Rn = ["y"], zn = ["x"], Bn = ["d"], Vn = {
	key: 1,
	class: "es-empty"
}, Hn = {
	key: 2,
	class: "es-daily-data"
}, Un = { class: "es-table-scroll" }, Wn = { "aria-label": "每日趋势数据" }, Gn = { class: "es-panel" }, Kn = { class: "es-panel-header" }, qn = {
	key: 0,
	class: "es-failures"
}, Jn = {
	class: "es-failure-track",
	"aria-hidden": "true"
}, Yn = {
	key: 1,
	class: "es-empty"
}, Xn = { class: "es-panel" }, Zn = {
	key: 0,
	class: "es-table-scroll",
	tabindex: "0",
	"aria-label": "平台统计，可左右滚动"
}, Qn = { class: "es-provider-table" }, $n = ["title"], er = ["title"], tr = {
	key: 1,
	class: "es-empty"
}, nr = { class: "es-panel" }, rr = {
	key: 0,
	class: "es-modes"
}, ir = {
	class: "es-mode-track",
	"aria-hidden": "true"
}, ar = {
	key: 1,
	class: "es-empty"
}, or = /*#__PURE__*/ D(/* @__PURE__ */ e({
	__name: "ExtractStats",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let r = mn(e.deps || {}), { state: s } = r, c = C(() => s.data), l = C(() => c.value?.totals || {}), f = C(() => c.value?.current || {}), p = C(() => c.value?.daily || []), g = C(() => p.value.at(-1) || {}), v = C(() => Object.entries(s.providers).filter(([e]) => e !== "lumen")), x = C(() => (c.value?.failures || []).filter((e) => W(e.count) > 0).slice().sort((e, t) => W(t.count) - W(e.count))), w = C(() => Math.max(1, ...x.value.map((e) => W(e.count)))), T = [
			{
				key: "total",
				label: "任务总数",
				tone: "total"
			},
			{
				key: "extracted",
				label: "已出链",
				tone: "extracted"
			},
			{
				key: "paid",
				label: "已支付",
				tone: "paid"
			}
		], D = C(() => p.value.some((e) => W(e.total) > 0)), A = C(() => {
			let e = Math.max(1, ...p.value.flatMap((e) => T.map((t) => W(e[t.key]))));
			return e <= 4 ? 4 : Math.ceil(e / 4) * 4;
		}), j = (e) => 48 + (p.value.length === 1 ? 406 : e * 812 / Math.max(1, p.value.length - 1)), M = (e) => 22 + 184 * (1 - W(e) / A.value), N = C(() => [.../* @__PURE__ */ new Set([
			0,
			...p.value.map((e, t) => t).filter((e) => e % Math.max(1, Math.ceil(p.value.length / 7)) === 0),
			p.value.length - 1
		])].filter((e) => e >= 0)), P = (e) => p.value.map((t, n) => `${n ? "L" : "M"}${j(n).toFixed(2)},${M(t[e]).toFixed(2)}`).join(" "), ee = (e) => W(l.value.total) ? Math.min(100, W(e.total) / W(l.value.total) * 100) : 0;
		function te(e) {
			r.setVisible(e);
		}
		return o(() => void r.load()), b(r.destroy), n({
			load: r.load,
			setVisible: te
		}), (e, n) => (t(), O("section", {
			class: "extract-stats-page",
			"aria-busy": E(s).loading
		}, [
			y("header", gn, [n[4] ||= y("div", null, [y("h1", null, "提链统计"), y("p", null, "按任务创建日统计 · 同一任务仅计一次")], -1), y("button", {
				type: "button",
				"data-extract-stats-refresh": "",
				disabled: E(s).loading,
				onClick: n[0] ||= (...e) => E(r).load && E(r).load(...e)
			}, "刷新", 8, _n)]),
			y("div", $, [
				y("div", vn, [(t(), O(m, null, a([
					7,
					30,
					90
				], (e) => y("button", {
					key: e,
					type: "button",
					"data-extract-stats-days": e,
					"aria-pressed": E(s).days === e,
					onClick: (t) => {
						E(s).days = e, E(r).load();
					}
				}, "近 " + _(e) + " 天", 9, yn)), 64))]),
				y("label", null, [n[6] ||= k("平台", -1), i(y("select", {
					"onUpdate:modelValue": n[1] ||= (e) => E(s).provider = e,
					"data-extract-stats-provider": "",
					onChange: n[2] ||= (...e) => E(r).load && E(r).load(...e)
				}, [n[5] ||= y("option", { value: "" }, "全部平台", -1), (t(!0), O(m, null, a(v.value, ([e, n]) => (t(), O("option", {
					key: e,
					value: e
				}, _(n), 9, bn))), 128))], 544), [[d, E(s).provider]])]),
				y("span", xn, _(E(s).loading ? "正在汇总提链任务…" : c.value?.generated_at ? `更新于 ${E(le)(c.value.generated_at)}` : ""), 1)
			]),
			E(s).error ? (t(), O("div", Sn, [y("span", null, _(E(s).data ? "刷新失败，以下保留上次统计。" : "未取得所选范围的统计。") + _(E(s).error), 1), y("button", {
				type: "button",
				"data-extract-stats-retry": "",
				onClick: n[3] ||= (...e) => E(r).load && E(r).load(...e)
			}, "重试")])) : u("", !0),
			!c.value && E(s).loading ? (t(), O("div", Cn, "正在汇总提链任务…")) : u("", !0),
			c.value ? (t(), O(m, { key: 2 }, [
				y("section", wn, [n[11] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "今日与当前"), y("span", null, "今日任务按北京时间创建日归属")], -1), y("dl", null, [
					y("div", null, [n[7] ||= y("dt", null, "今日任务出链", -1), y("dd", null, _(E(G)(g.value.extracted)), 1)]),
					y("div", null, [n[8] ||= y("dt", null, "今日任务 Plus", -1), y("dd", null, _(E(G)(g.value.plus_confirmed)), 1)]),
					y("div", null, [n[9] ||= y("dt", null, [k("当前待支付"), y("small", null, "全部日期")], -1), y("dd", null, _(E(G)(f.value.awaiting_payment)), 1)]),
					y("div", null, [n[10] ||= y("dt", null, [k("当前待核对"), y("small", null, "全部日期")], -1), y("dd", null, _(E(G)(f.value.needs_review)), 1)])
				])]),
				y("div", Tn, [y("span", null, _(c.value.date_from || "—") + " — " + _(c.value.date_to || "—"), 1), n[12] ||= y("span", null, "按北京时间任务创建日归属", -1)]),
				y("div", En, [(t(), O(m, null, a([
					{
						key: "total",
						label: "任务总数",
						hint: "所选时间内创建的任务"
					},
					{
						key: "extracted",
						label: "已出链",
						hint: "已获得支付链接"
					},
					{
						key: "paid",
						label: "已支付",
						hint: "支付结果已确认"
					},
					{
						key: "plus_confirmed",
						label: "Plus 已确认",
						hint: "套餐到账已核验"
					}
				], (e) => y("article", {
					key: e.key,
					class: S(["es-metric", `es-metric--${e.key}`])
				}, [
					y("span", null, _(e.label), 1),
					y("strong", null, _(E(G)(l.value[e.key])), 1),
					y("small", null, _(e.hint), 1)
				], 2)), 64))]),
				y("div", Dn, [y("section", On, [n[19] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "转化与耗时"), y("span", null, "未结束任务不进入成功率分母")], -1), y("dl", kn, [
					y("div", null, [
						n[13] ||= y("dt", null, "提链成功率", -1),
						y("dd", null, _(E(K)(l.value.extraction_rate)), 1),
						n[14] ||= y("span", null, "已出链 /（已出链 + 提链失败）", -1),
						y("small", null, "出链 " + _(E(G)(l.value.extracted)) + " · 失败 " + _(E(G)(l.value.extraction_failed)), 1)
					]),
					y("div", null, [
						n[15] ||= y("dt", null, "支付成功率", -1),
						y("dd", null, _(E(K)(l.value.payment_rate)), 1),
						n[16] ||= y("span", null, "已支付 /（已支付 + 支付失败）", -1),
						y("small", null, "支付 " + _(E(G)(l.value.paid)) + " · 失败 " + _(E(G)(l.value.payment_failed)), 1)
					]),
					y("div", null, [
						n[17] ||= y("dt", null, "平均耗时", -1),
						y("dd", null, _(E(q)(l.value.avg_seconds)), 1),
						n[18] ||= y("span", null, "最新成功运行的总耗时", -1)
					])
				])]), y("section", An, [
					n[20] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "区间任务状态"), y("span", null, "所选范围的最新结果")], -1),
					y("dl", jn, [(t(), O(m, null, a([
						{
							key: "failed",
							label: "失败"
						},
						{
							key: "processing",
							label: "处理中"
						},
						{
							key: "awaiting_payment",
							label: "待支付"
						},
						{
							key: "needs_review",
							label: "待核对"
						}
					], (e) => y("div", { key: e.key }, [y("dt", null, _(e.label), 1), y("dd", null, _(E(G)(l.value[e.key])), 1)])), 64))]),
					y("p", Mn, _(E(s).provider ? "当前所选平台" : "当前全部平台") + "，全部日期：处理中 " + _(E(G)(f.value.processing)) + " · 待支付 " + _(E(G)(f.value.awaiting_payment)) + " · 待核对 " + _(E(G)(f.value.needs_review)), 1)
				])]),
				y("div", Nn, [y("section", Pn, [
					n[25] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "每日趋势"), y("span", null, "按北京时间任务创建日归属")], -1),
					D.value ? (t(), O(m, { key: 0 }, [y("div", Fn, [(t(), O(m, null, a(T, (e) => y("span", {
						key: e.key,
						class: S(`es-series--${e.tone}`)
					}, _(e.label), 3)), 64))]), (t(), O("svg", In, [
						n[21] ||= y("title", null, "每日提链趋势，完整数据见下方表格", -1),
						(t(), O(m, null, a([
							0,
							1,
							2,
							3,
							4
						], (e) => y("g", { key: e }, [y("line", {
							x1: "48",
							x2: "860",
							y1: M(A.value * e / 4),
							y2: M(A.value * e / 4),
							class: "es-chart-gridline"
						}, null, 8, Ln), y("text", {
							x: "38",
							y: M(A.value * e / 4) + 4,
							"text-anchor": "end",
							class: "es-chart-label"
						}, _(E(G)(A.value * e / 4)), 9, Rn)])), 64)),
						(t(!0), O(m, null, a(N.value, (e) => (t(), O("text", {
							key: e,
							x: j(e),
							y: "232",
							"text-anchor": "middle",
							class: "es-chart-label"
						}, _(String(p.value[e]?.date || "").slice(5)), 9, zn))), 128)),
						(t(), O(m, null, a(T, (e) => y("path", {
							key: e.key,
							d: P(e.key),
							class: S(["es-chart-line", `es-series--${e.tone}`])
						}, null, 10, Bn)), 64))
					]))], 64)) : (t(), O("div", Vn, [...n[22] ||= [y("strong", null, "这个时间段还没有提链任务", -1), y("p", null, "选择其他时间范围，或在提链工作台新建批次。", -1)]])),
					p.value.length ? (t(), O("details", Hn, [n[24] ||= y("summary", null, "查看每日明细数据", -1), y("div", Un, [y("table", Wn, [n[23] ||= y("thead", null, [y("tr", null, [
						y("th", null, "日期（北京时间）"),
						y("th", null, "任务总数"),
						y("th", null, "已出链"),
						y("th", null, "已支付"),
						y("th", null, "Plus 已确认")
					])], -1), y("tbody", null, [(t(!0), O(m, null, a(p.value, (e) => (t(), O("tr", { key: e.date }, [
						y("th", null, _(e.date), 1),
						y("td", null, _(E(G)(e.total)), 1),
						y("td", null, _(E(G)(e.extracted)), 1),
						y("td", null, _(E(G)(e.paid)), 1),
						y("td", null, _(E(G)(e.plus_confirmed)), 1)
					]))), 128))])])])])) : u("", !0)
				]), y("section", Gn, [y("div", Kn, [n[26] ||= y("h2", null, "失败分类", -1), y("span", null, _(E(G)(l.value.failed)) + " 个失败任务", 1)]), x.value.length ? (t(), O("ol", qn, [(t(!0), O(m, null, a(x.value, (e) => (t(), O("li", { key: e.code || e.label }, [
					y("div", null, [y("span", null, _(e.label || e.code || "原因未记录"), 1), y("strong", null, _(E(G)(e.count)), 1)]),
					y("div", Jn, [y("span", { style: h({ width: `${E(W)(e.count) / w.value * 100}%` }) }, null, 4)]),
					y("code", null, _(e.code || "未记录错误码"), 1)
				]))), 128))])) : (t(), O("div", Yn, [...n[27] ||= [y("strong", null, "暂无失败记录", -1), y("p", null, "所选范围没有失败任务。", -1)]]))])]),
				y("section", Xn, [n[30] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "平台对比"), y("span", null, "支付成功与 Plus 到账分别统计")], -1), c.value.providers?.length ? (t(), O("div", Zn, [y("table", Qn, [n[28] ||= y("thead", null, [y("tr", null, [
					y("th", null, "平台"),
					y("th", null, "任务数"),
					y("th", null, "已出链"),
					y("th", { title: "已出链 /（已出链 + 提链失败）" }, "提链成功率"),
					y("th", null, "已支付"),
					y("th", { title: "已支付 /（已支付 + 支付失败）" }, "支付成功率"),
					y("th", null, "Plus 已确认"),
					y("th", null, "失败"),
					y("th", null, "处理中"),
					y("th", { title: "最新成功运行的平均总耗时" }, "平均耗时")
				])], -1), y("tbody", null, [(t(!0), O(m, null, a(c.value.providers, (e) => (t(), O("tr", { key: e.provider_id }, [
					y("th", null, _(E(U)(e.provider_id)), 1),
					y("td", null, _(E(G)(e.total)), 1),
					y("td", null, _(E(G)(e.extracted)), 1),
					y("td", { title: `已出链 ${E(G)(e.extracted)}，提链失败 ${E(G)(e.extraction_failed)}` }, _(E(K)(e.extraction_rate)), 9, $n),
					y("td", null, _(E(G)(e.paid)), 1),
					y("td", { title: `已支付 ${E(G)(e.paid)}，支付失败 ${E(G)(e.payment_failed)}` }, _(E(K)(e.payment_rate)), 9, er),
					y("td", null, _(E(G)(e.plus_confirmed)), 1),
					y("td", null, _(E(G)(e.failed)), 1),
					y("td", null, _(E(G)(e.processing)), 1),
					y("td", null, _(E(q)(e.avg_seconds)), 1)
				]))), 128))])])])) : (t(), O("div", tr, [...n[29] ||= [y("strong", null, "暂无平台数据", -1), y("p", null, "所选范围没有提链任务。", -1)]]))]),
				y("section", nr, [n[32] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "模式分布"), y("span", null, "所选范围内的任务组成")], -1), c.value.modes?.length ? (t(), O("div", rr, [(t(!0), O(m, null, a(c.value.modes, (e) => (t(), O("article", {
					key: e.mode,
					class: "es-mode"
				}, [
					y("div", null, [y("h3", null, _(E(ce)(e.mode)), 1), y("span", null, _(E(W)(l.value.total) ? E(K)(ee(e) / 100) : "—"), 1)]),
					y("strong", null, [k(_(E(G)(e.total)), 1), n[31] ||= y("small", null, " 个任务", -1)]),
					y("div", ir, [y("span", { style: h({ width: `${ee(e)}%` }) }, null, 4)]),
					y("dl", null, [(t(), O(m, null, a([
						{
							key: "extracted",
							label: "出链"
						},
						{
							key: "paid",
							label: "支付"
						},
						{
							key: "plus_confirmed",
							label: "Plus"
						},
						{
							key: "failed",
							label: "失败"
						}
					], (t) => y("div", { key: t.key }, [y("dt", null, _(t.label), 1), y("dd", null, _(E(G)(e[t.key])), 1)])), 64))])
				]))), 128))])) : (t(), O("div", ar, "暂无模式数据"))])
			], 64)) : u("", !0)
		], 8, hn));
	}
}), [["__scopeId", "data-v-1d114568"]]);
// src/extract.ts
function sr(e, t = {}) {
	let n = w(pn, { deps: t }), r = n.mount(e);
	return {
		load: r.load,
		setVisible: r.setVisible,
		openCreate: r.openCreate,
		switchBatch: r.switchBatch,
		openDetail: r.openDetail,
		showPaymentEntry: r.showPaymentEntry,
		taskAction: r.taskAction,
		showLink: r.showLink,
		copy: r.copy,
		copyPayment: r.copyPayment,
		bulkAction: r.bulkAction,
		cancelBatch: r.cancelBatch,
		exportRows: r.exportRows,
		closeDialogs: r.closeDialogs,
		destroy: () => n.unmount()
	};
}
function cr(e, t = {}) {
	let n = w(or, { deps: t }), r = n.mount(e);
	return {
		load: r.load,
		setVisible: r.setVisible,
		destroy: () => n.unmount()
	};
}
export { cr as mountExtractStats, sr as mountExtractWorkbench };
