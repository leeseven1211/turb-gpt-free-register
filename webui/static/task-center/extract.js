import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, R as c, S as l, _ as u, a as d, b as f, c as p, d as m, dt as h, et as g, ft as _, g as v, h as y, j as b, l as x, lt as S, m as C, n as w, o as T, s as E, st as D, t as O, v as k, x as A } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { r as j, t as M } from "./client-B5R_MNgP.js";
import { a as N, i as P, r as F } from "./taskIds-BlchWwUp.js";
import { t as ee } from "./useNativeDialog-DWisXYg9.js";
import { t as te } from "./ListPagination-DURVj-Kj.js";
import { i as I, n as ne, r as L, t as re } from "./ListFilterSummary-C8h8bMwn.js";
import { t as ie } from "./ListResult-CPVXnLlZ.js";
// src/api/extract.ts
var R = "/api/extract-workbench";
function ae(e) {
	let t = new URLSearchParams({
		provider_id: e.provider,
		mode: e.mode,
		status: e.status,
		query: e.query,
		page: String(e.page),
		page_size: String(e.size)
	});
	return e.batch && t.set("batch_id", String(N(e.batch))), t;
}
function z(e = {}) {
	async function t(t, n = {}, r = !1) {
		let i = r && e.statsDataSource || e.dataSource, a = i ? await i(t, n) : await j(t, n, F);
		if (!a || typeof a != "object" || a.ok === !1) throw Error("提链接口响应无效");
		return a;
	}
	let n = (e, n = {}, r) => t(e, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(n),
		signal: r
	}), r = (e) => `${R}/tasks/${encodeURIComponent(N(e))}`;
	function i(e) {
		if (!Array.isArray(e.items) || !Number.isSafeInteger(e.total) || e.total < 0 || !Number.isSafeInteger(e.page) || e.page < 1) throw Error("提链分页响应无效");
		return e;
	}
	return {
		async config(e) {
			let n = await t(`${R}/config`, { signal: e });
			if (!Array.isArray(n.providers)) throw Error("提链配置响应无效");
			return n;
		},
		summary: (e) => t(`${R}/summary`, { signal: e }),
		async batches(e, n) {
			let r = i(await t(`${R}/batches?page=${e}&page_size=20`, { signal: n }));
			for (let e of r.items) N(e.batch_id);
			return r;
		},
		async batch(e, n) {
			let r = await t(`${R}/batches/${encodeURIComponent(N(e))}`, { signal: n });
			if (!r.item || String(N(r.item.batch_id)) !== String(N(e))) throw Error("提链批次响应不匹配");
			return r;
		},
		async tasks(e, n) {
			let r = i(await t(`${R}/tasks?${ae(e)}`, { signal: n }));
			for (let e of r.items) N(e.task_id);
			return r;
		},
		async candidates(e, n, r) {
			let i = await t(`${R}/candidates?${new URLSearchParams({
				...e,
				limit: String(n)
			})}`, { signal: r });
			if (!Number.isSafeInteger(i.total) || !Number.isSafeInteger(i.selected_count) || i.total < 0 || i.selected_count < 0 || i.selected_count > Math.min(i.total, n)) throw Error("候选统计响应无效");
			for (let e of i.items || []) N(e.account_id);
			return i;
		},
		create: (e) => n(`${R}/batches`, e),
		cancel: (e) => n(`${R}/batches/${encodeURIComponent(N(e))}/cancel`),
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
		secret: (e) => t(`/api/accounts/${encodeURIComponent(N(e))}/secret?field=access_token`),
		async analytics(e, n, r) {
			let i = new URLSearchParams({ days: String(e) });
			n && i.set("provider_id", n);
			let a = await t(`${R}/analytics?${i}`, { signal: r }, !0);
			if (!a.totals || !Array.isArray(a.daily)) throw Error("统计响应格式不完整");
			return a;
		},
		async export(e) {
			let t = ae(e);
			t.delete("page"), t.delete("page_size");
			let n = await fetch(`${R}/export?${t}`, { credentials: "same-origin" });
			if (!n.ok || n.redirected || !/(text\/csv|application\/octet-stream)/i.test(n.headers.get("content-type") || "")) throw new M("导出失败，请重新登录或重试", n.status);
			return n.blob();
		}
	};
}
// src/features/extract/presentation.ts
var oe = {
	legacy: "虾扯蛋链",
	lumen: "Lumen Flow",
	lumen_flow: "Lumen Flow",
	huanguang: "幻光提链",
	anguang: "暗光（XXSYUN 一条龙）"
}, B = {
	extract_only: "仅提链",
	manual_payment: "手动支付",
	auto_payment: "自动支付"
}, se = {
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
}, ce = {
	eligible: "全部可提链优惠",
	all: "全部（有无优惠）",
	free_trial: "免费试用",
	half_price: "半价",
	other_discount: "其他折扣",
	other_promo: "其他优惠",
	none: "无优惠"
}, le = [
	["", "全部"],
	["queued", "排队中"],
	["extracting", "进行中"],
	["scanning", "扫码中"],
	["paused", "已暂停"],
	["cancelled", "已停止"],
	["extraction_succeeded", "已出链"],
	["payment_succeeded", "扫码完成"],
	["failed", "失败"]
], ue = {
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
	request_unknown: "响应记录缺失",
	attention_required: "响应记录缺失",
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
}, V = (e, t = "状态记录缺失") => ue[String(e || "").toLowerCase()] || String(e || "") || t, H = (e) => oe[e || ""] || e || "未记录平台", U = (e) => B[e || ""] || e || "未记录模式", W = (e) => {
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
function de(e) {
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
var fe = (e) => Array.isArray(e?.modes) ? e.modes : [], pe = (e) => e?.link_types?.length ? [...new Set(e.link_types)] : e?.default_type ? [e.default_type] : [];
function me(e) {
	return e.payment_source ? e.payment_source_label || {
		native: "平台自带",
		xxsyun: "XXSYUN"
	}[e.payment_source] || "未知来源" : "";
}
var he = (e) => e.mode === "auto_payment" && me(e) ? ` · 自动支付来源：${me(e)}` : "", ge = (e) => [
	"queued",
	"running",
	"waiting",
	"settling",
	"cancelling",
	"stopping"
].includes(e.task_status || "");
function _e(e) {
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
var ve = (e) => !ge(e) && !_e(e);
function ye(e) {
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
function be(e) {
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
		label: e.payment_status === "failed" ? "已出链 · 支付失败" : ye(e) === "query_stopped" ? "已出链 · 已停止查询" : [
			"failed",
			"cancelled",
			"stopped",
			"request_unknown",
			"attention_required"
		].includes(e.task_status || "") ? "已出链 · 后续未完成" : "已出链",
		tone: e.payment_status === "failed" || _e(e) ? "warning" : "success",
		detail: e.error_info?.summary || e.error || e.message || (e.mode === "extract_only" ? "仅提链已完成，未发起支付" : "支付链接已生成，支付与套餐结果分别记录")
	} : ye(e) ? {
		label: V(ye(e)),
		tone: "warning",
		detail: e.reconcile_halt?.label || e.error_info?.summary || e.error || e.message || "原远端任务记录已保留"
	} : _e(e) ? {
		label: "结果记录缺失",
		tone: "warning",
		detail: e.error_info?.summary || e.error || e.message || "未取得平台有效响应"
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
function J(e, t = !1) {
	let n = String(e || "").trim();
	if (t && /^data:image\/(?:png|svg\+xml);base64,[a-z0-9+/=\s]+$/i.test(n)) return n;
	try {
		let e = new URL(n);
		return ["http:", "https:"].includes(e.protocol) && !e.username && !e.password ? e.href : "";
	} catch {
		return "";
	}
}
var xe = (e) => [...new Set([e.qr_image_url_png, e.qr_image_url_svg].map((e) => J(e, !0)).filter(Boolean))];
function Se(e, t = !1) {
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
var Y = (e) => e instanceof Error ? e.message : "请求失败，请重试";
function Ce(e) {
	return e === "all" ? "匹配套餐优惠已查明（有或无）的活跃、未归档 free 账号；套餐待查及状态未知的账号不包含，提交前仍会在线查活。" : e === "none" ? "仅匹配活跃、未归档且上次查询无优惠的 free 账号；当前优惠由提链平台判断，提交前仍会在线查活。" : `仅匹配活跃、未归档且具备${e === "eligible" ? "任一可提链" : `「${ce[e] || e}」`}优惠的 free 账号；提交前仍会在线查活。`;
}
function we(e) {
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
function Te(e, t) {
	let n = URL.createObjectURL(e), r = document.createElement("a");
	r.href = n, r.download = t, document.body.append(r), r.click(), r.remove(), setTimeout(() => URL.revokeObjectURL(n), 2e3);
}
function Ee(e) {
	let t = be(e), n = e.payment_status === "paid", r = ["confirmed", "plus"].includes(e.plus_status || ""), i = n && r ? "支付与Plus确认" : n ? "已支付待核验" : r ? "Plus已到账" : ye(e) ? V(ye(e)) : _e(e) ? "结果记录缺失" : ["success", "succeeded"].includes(e.extraction_status || "") ? e.payment_status === "failed" ? "已出链支付失败" : "已出链" : [
		"failed",
		"cancelled",
		"stopped"
	].includes(e.task_status || "") ? e.task_status === "cancelled" ? "已取消" : "提链未完成" : ge(e) ? "执行中" : "排队中";
	return {
		...t,
		label: i,
		detail: t.detail
	};
}
function De(e) {
	if (e == null || e === "") return null;
	let t = Number(e);
	if (Number.isFinite(t) && t > 1e11) return t;
	let n = Date.parse(String(e));
	return Number.isFinite(n) ? n : null;
}
function Oe(e, t = Date.now()) {
	let n = De(e);
	if (n == null) return "—";
	let r = Math.floor((n - t) / 1e3);
	return r <= 0 ? "已过期" : `${String(Math.floor(r / 60)).padStart(2, "0")}:${String(r % 60).padStart(2, "0")}`;
}
// src/features/extract/useExtractWorkbench.ts
var X = () => ({
	page: 1,
	size: 20,
	provider: "",
	mode: "",
	status: "",
	query: "",
	batch: ""
}), ke = 3e4;
function Ae(e = {}) {
	let t = e.api || z(e), n = s({
		query: X(),
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
		if (!e && n.config && Date.now() - l < ke) return Promise.resolve(n.config);
		if (m) return m.promise;
		let i = ++o, a = C(), s = t.config(a.signal).then((e) => (x(r) && m?.version === i && (n.config = e, n.auxErrors.config = "", l = Date.now(), E(f > 0)), e)).catch((e) => {
			throw x(r) && (n.auxErrors.config = Y(e)), e;
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
			throw x(e) && (n.auxErrors.summary = Y(t)), t;
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
			throw c() && (n.auxErrors.batches = Y(e)), e;
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
	async function M(e, t) {
		D(!!e.force, t).catch(() => {}), O(t).catch(() => {});
		let r = n.batchPage, i = n.query.batch, a = ++c, o = !!e.force || d !== r || Date.now() - u >= ke;
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
			x(t) && i === n.query.batch && r === n.batchPage && (n.auxErrors.detail = Y(e));
		}
	}
	async function P(r = {}) {
		if (!b()) return;
		w();
		let o = ++a, s = i, c = { ...n.query };
		g?.abort();
		let l = C();
		g = l, n.loading = !0, n.error = "", M(r, s);
		try {
			let r = await t.tasks(c, l.signal);
			if (!x(s) || o !== a) return;
			n.items = r.items, n.total = r.total, n.counts = r.counts || {}, n.query.page = r.page;
			for (let e of [...n.selected]) r.items.some((t) => String(t.task_id) === e) || n.selected.delete(e);
			f = 0, e.onReady?.(), E();
		} catch (e) {
			x(s) && o === a && (n.error = Y(e), f++, E(!0));
		} finally {
			y.delete(l), x(s) && o === a && (n.loading = !1);
		}
	}
	async function F(e) {
		Object.assign(n.query, X(), { batch: e ? String(N(e)) : "" }), n.batchDetail = null, n.selected.clear(), c++, await P();
	}
	async function ee(r) {
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
						let { entry: i } = await t.paymentEntry(e.task_id), a = J(i.payment_page_url) || J(i.payment_url) || i.qr_data;
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
				n.error = Y(e);
			} finally {
				n.bulkBusy = !1;
			}
		}
	}
	async function te(r = {}) {
		let i = n.query.batch;
		if (i && !n.cancellingBatch) {
			n.cancellingBatch = i;
			try {
				if (!r.confirmed && !await (e.confirm ? e.confirm("确认取消当前整批尚未开始的排队任务？运行中与已完成任务保留，不受当前筛选和分页限制。") : window.confirm("确认取消当前整批尚未开始的排队任务？运行中与已完成任务保留。"))) return;
				let a = await t.cancel(i);
				if (a.ok === !1) throw Error(a.error || "取消批次失败");
				n.receipt = a, S(`批次 #${i}：已取消 ${a.cancelled || 0} 个排队任务，跳过 ${a.skipped || 0} 个${a.failed ? `，失败 ${a.failed} 个，可再次处理剩余任务` : ""}。`), await P({ force: !0 });
			} catch (e) {
				n.error = Y(e);
			} finally {
				n.cancellingBatch = "";
			}
		}
	}
	async function I(e = !0) {
		try {
			if (e) {
				Te(await t.export({ ...n.query }), "extract-workbench.csv"), S("已导出当前筛选结果（最多 5000 条）");
				return;
			}
			let r = n.items.filter((e) => n.selected.has(String(e.task_id)));
			Te(new Blob([we(r)], { type: "text/csv;charset=utf-8" }), "extract-workbench-selected.csv");
		} catch (e) {
			n.error = Y(e);
		}
	}
	function ne() {
		i++, a++, c++, w(), y.forEach((e) => e.abort()), y.clear(), g = void 0, m = void 0, h = void 0, _.clear(), v.clear(), n.batchPage = d || 1, n.batchLoading = !1, n.loading = !1;
	}
	function L(e) {
		n.visible === e ? e && !n.loading && P() : (n.visible = e, e ? P() : ne());
	}
	function re() {
		document.hidden ? ne() : n.visible && P();
	}
	document.addEventListener("visibilitychange", re);
	function ie() {
		r = !0, ne(), document.removeEventListener("visibilitychange", re);
	}
	return {
		state: n,
		load: P,
		loadBatchPage: A,
		setVisible: L,
		switchBatch: F,
		bulkAction: ee,
		cancelBatch: te,
		exportRows: I,
		destroy: ie
	};
}
// src/features/extract/useExtractBatch.ts
function je(e = {}, t = async () => {}) {
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
		let t = i.config?.providers.find((t) => t.id === e), n = fe(t), r = pe(t);
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
			!a && e === o && i.opened && (i.error = `匹配数量统计失败：${Y(t)}`, i.feedback = "请检查筛选条件后重试。");
		} finally {
			e === o && (i.loading = !1);
		}
	}
	async function y() {
		if (!a && !i.creating && i.opened && i.preview?.selected_count && i.previewSignature === f()) {
			i.creating = !0, i.error = "";
			try {
				let r = i.config?.providers.find((e) => e.id === i.provider), o = fe(r), s = pe(r), c = Number(i.workers), l = Number(i.limit);
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
				if (u.mode === "auto_payment" && !await (e.confirm ? e.confirm(`将为本批约 ${i.preview.selected_count} 个账号启用自动支付任务${he({
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
				i.error = `${Y(e)}；可重试获取同一批次的提交结果。`;
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
function Me(e = {}, t = async () => {}) {
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
		e = N(e);
		let t = ++a;
		l?.abort(), S(), l = new AbortController(), r.drawer = !0, r.detail = null, r.detailLoading = !0, r.detailError = "";
		try {
			let o = await n.detail(e, l.signal);
			!i && t === a && r.drawer && (r.detail = o, (o.item.has_payment_entry || o.item.has_payment_link || o.item.has_qr) && h(e));
		} catch (e) {
			!i && t === a && (r.detailError = Y(e));
		} finally {
			t === a && (r.detailLoading = !1);
		}
	}
	async function h(e) {
		e = N(e);
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
			!i && r.drawer && t === c && P(r.detail?.item.task_id, e) && (r.nodeA.entry = a.entry);
		} catch (e) {
			!i && r.drawer && t === c && (r.nodeA.error = Y(e));
		} finally {
			t === c && (r.nodeA.loading = !1);
		}
	}
	async function g(e) {
		e = N(e);
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
			!i && t === o && (r.payment.error = Y(e));
		} finally {
			t === o && (r.payment.loading = !1);
		}
	}
	async function _(a, o) {
		a = N(a);
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
				let i = P(r.detail?.item.task_id, a) ? r.detail.item : (await n.detail(a)).item;
				if (ge(i)) throw Error("任务正在执行，请等待当前运行结束");
				if (o !== "sync_status" && !ve(i)) throw Error("远端结果尚未确认，请同步原任务状态，不能重新提交");
				if (o === "auto_payment" && !await (e.confirm ? e.confirm("确认查询并继续此任务已保存的自动支付原单？") : window.confirm("确认继续此任务的自动支付？"))) return;
				let s = await n.action(a, o);
				if (s.accepted !== !0) throw Error(s.error || "操作未接受");
				r.receipt = s, f("任务操作已提交");
				try {
					await t();
				} catch {}
			} catch (e) {
				r.error = Y(e), f(r.error);
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
				let r = await n.links(N(e), t), i = J(r.url || r.link);
				if (!i) throw Error("服务端未返回有效链接");
				t === "extract" ? await p(i) : window.open(i, "_blank", "noopener,noreferrer");
			} catch (e) {
				r.error = Y(e), f(r.error);
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
					let t = P(r.detail?.item.task_id, e) ? r.detail : await n.detail(e);
					if (!t.item.account_id) throw Error("任务未记录账号");
					await p((await n.secret(t.item.account_id)).value || "");
				} else if (t === "email") await p((P(r.detail?.item.task_id, e) ? r.detail : await n.detail(e)).item.email || "");
				else throw Error("不支持的复制类型");
			} catch (e) {
				r.error = Y(e), f(r.error);
			} finally {
				r.busy.delete(i);
			}
		}
	}
	async function b(e) {
		try {
			await p(e === "qr_data" ? String(r.payment.entry?.qr_data || "") : J(r.payment.entry?.[e]));
		} catch (e) {
			r.payment.error = Y(e);
		}
	}
	async function x(e) {
		try {
			await p(e === "qr_data" ? String(r.nodeA.entry?.qr_data || "") : J(r.nodeA.entry?.[e]));
		} catch (e) {
			r.nodeA.error = Y(e);
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
var Ne = { class: "extract-filter-fields" }, Pe = {
	key: 0,
	class: "extract-filter-field"
}, Fe = {
	class: "list-filter-options",
	role: "radiogroup",
	"aria-label": "选择提链任务筛选列"
}, Ie = [
	"name",
	"value",
	"checked",
	"onChange"
], Le = { class: "extract-filter-field" }, Re = ["value"], ze = ["aria-label"], Be = ["data-extract-option"], Z = [
	"name",
	"value",
	"checked",
	"disabled",
	"onChange"
], Ve = { key: 0 }, He = { class: "list-filter-actions" }, Ue = /*#__PURE__*/ O(/* @__PURE__ */ e({
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
		}, s = e, l = r, d = g("query"), f = C(() => s.column || d.value), h = C(() => s.values[f.value]);
		function b(e) {
			l("change", f.value, e);
		}
		function x(e) {
			d.value = e;
		}
		let w = C(() => f.value === "provider" ? [{
			value: "",
			label: "全部平台"
		}, ...s.providers.map((e) => ({
			value: e.id,
			label: e.label || e.id
		}))] : f.value === "mode" ? [{
			value: "",
			label: "全部模式"
		}, ...[
			"extract_only",
			"manual_payment",
			"auto_payment"
		].map((e) => ({
			value: e,
			label: U(e)
		}))] : f.value === "status" ? le.filter(([e]) => {
			let t = s.counts?.[e || "all"];
			return t === void 0 || t > 0 || e === h.value;
		}).map(([e, t]) => ({
			value: e,
			label: t,
			count: s.counts?.[e || "all"]
		})) : f.value === "batch" ? [
			{
				value: "",
				label: "全部任务"
			},
			...h.value && !s.batches.some((e) => String(e.batch_id) === h.value) ? [{
				value: h.value,
				label: `批次 #${h.value}`
			}] : [],
			...s.batches.map((e) => ({
				value: String(e.batch_id),
				label: e.title || `批次 #${e.batch_id}`
			}))
		] : []);
		return (r, s) => (t(), v(I, {
			label: e.column ? o[e.column] : "提链任务",
			"trigger-label": e.column ? o[e.column] : "筛选",
			active: e.column ? !!e.values[e.column] : Object.values(e.values).some(Boolean),
			summary: h.value,
			open: e.open,
			"onUpdate:open": s[4] ||= (e) => l("update:open", e)
		}, {
			default: n(() => [y("div", Ne, [
				e.column ? u("", !0) : (t(), k("div", Pe, [s[5] ||= A("筛选列", -1), y("div", Fe, [(t(), k(m, null, a(o, (t, n) => i(y("label", {
					key: n,
					class: "list-filter-option"
				}, [y("input", {
					type: "radio",
					name: `extract-column-${t}`,
					value: n,
					checked: d.value === n,
					onChange: (e) => x(n)
				}, null, 40, Ie), y("span", null, _(t), 1)], 512), [[E, n !== "batch" || !e.omitBatch]])), 64))])])),
				y("div", Le, [A(_(o[f.value]) + " ", 1), f.value === "query" ? (t(), k("input", {
					key: 0,
					type: "search",
					value: h.value,
					"aria-label": "筛选账号值",
					placeholder: "邮箱或任务号",
					onChange: s[0] ||= (e) => b(e.target.value),
					onKeydown: s[1] ||= p((e) => l("update:open", !1), ["enter"])
				}, null, 40, Re)) : (t(), k("div", {
					key: 1,
					class: "list-filter-options",
					role: "radiogroup",
					"aria-label": `筛选${o[f.value]}值`
				}, [(t(!0), k(m, null, a(w.value, (n) => (t(), k("label", {
					key: n.value,
					class: S(["list-filter-option", { "is-disabled": e.batchBusy && f.value === "batch" }]),
					"data-extract-option": n.value
				}, [
					y("input", {
						type: "radio",
						name: `extract-${f.value}`,
						value: n.value,
						checked: h.value === n.value,
						disabled: e.batchBusy && f.value === "batch",
						onChange: (e) => b(n.value)
					}, null, 40, Z),
					y("span", null, _(n.label), 1),
					n.count === void 0 ? u("", !0) : (t(), k("small", Ve, _(n.count), 1))
				], 10, Be))), 128))], 8, ze))]),
				f.value === "batch" ? c(r.$slots, "default", {}, void 0, !0, 1) : u("", !0),
				y("div", He, [y("button", {
					type: "button",
					onClick: s[2] ||= (e) => b("")
				}, "清除此列"), y("button", {
					type: "button",
					class: "list-filter-primary",
					onClick: s[3] ||= (e) => l("update:open", !1)
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
}), [["__scopeId", "data-v-afa1ea5e"]]), We = ["aria-busy"], Ge = { class: "extract-toolbar" }, Ke = { class: "extract-title" }, qe = {
	key: 0,
	class: "extract-metrics",
	"aria-label": "提链概况"
}, Je = { class: "extract-toolbar-actions" }, Ye = { class: "ui-list extract-list-panel" }, Xe = {
	class: "ui-list-toolbar extract-count-row",
	"data-extract-count-row": ""
}, Ze = { class: "ui-list-toolbar__main extract-count-main" }, Qe = { class: "ui-list-count extract-count" }, $e = {
	key: 0,
	class: "extract-bulk-actions",
	role: "group",
	"aria-label": "选中提链任务批量操作"
}, et = { class: "ui-list-bulkbar__count" }, tt = ["disabled"], nt = { class: "ui-list-toolbar__actions extract-count-actions" }, rt = {
	key: 0,
	class: "extract-batch-message",
	role: "status"
}, it = {
	key: 1,
	class: "extract-batch-message",
	role: "alert"
}, at = { class: "extract-mobile-filter" }, ot = ["title", "disabled"], st = {
	key: 0,
	class: "ui-list-feedback is-error",
	role: "alert"
}, ct = {
	key: 1,
	class: "ui-list-feedback is-error",
	role: "alert"
}, lt = {
	class: "ui-table ui-table--sticky-end extract-table",
	"aria-label": "提链任务"
}, ut = { class: "ui-col-check" }, dt = ["checked"], ft = { class: "ui-col-check" }, pt = [
	"aria-label",
	"checked",
	"onChange"
], mt = { class: "extract-tone" }, ht = { key: 0 }, gt = { key: 1 }, _t = { key: 2 }, vt = { class: "ui-row-actions extract-row-actions" }, yt = ["onClick"], bt = ["disabled", "onClick"], xt = { class: "extract-form-grid" }, St = ["value"], Ct = ["value"], wt = ["value"], Tt = ["value"], Et = ["value"], Dt = ["value"], Ot = ["max"], kt = { class: "extract-hint" }, At = { role: "status" }, jt = {
	key: 0,
	class: "error",
	role: "alert"
}, Mt = ["disabled"], Nt = ["disabled"], Pt = {
	key: 0,
	role: "status"
}, Ft = {
	key: 1,
	class: "error",
	role: "alert"
}, It = {
	class: "extract-detail-actions",
	role: "group",
	"aria-label": "任务操作"
}, Lt = ["disabled"], Rt = ["disabled"], zt = ["disabled"], Bt = { class: "extract-facts" }, Vt = {
	key: 0,
	"aria-label": "阶段证据"
}, Ht = {
	key: 1,
	class: "extract-facts"
}, Ut = {
	key: 2,
	class: "notice"
}, Wt = {
	class: "extract-node-a",
	"data-extract-node-a": ""
}, Gt = {
	key: 0,
	role: "status"
}, Kt = {
	key: 1,
	role: "alert"
}, qt = { class: "extract-detail-actions" }, Jt = ["href"], Yt = ["onClick"], Xt = ["src"], Zt = { key: 1 }, Qt = { key: 2 }, $t = { key: 3 }, en = { key: 3 }, tn = { class: "extract-timeline" }, nn = { key: 0 }, rn = { key: 0 }, an = {
	key: 4,
	"data-extract-history": ""
}, on = { "data-extract-run-outcome": "" }, sn = {
	key: 0,
	role: "status"
}, cn = {
	key: 0,
	class: "error",
	role: "alert"
}, ln = { class: "extract-facts" }, un = ["href"], dn = ["onClick"], fn = { key: 1 }, pn = ["src"], mn = { key: 1 }, hn = { key: 1 }, gn = /*#__PURE__*/ O(/* @__PURE__ */ e({
	__name: "ExtractWorkbench",
	props: { deps: {} },
	setup(e, { expose: s }) {
		let c = e.deps || {}, p = Ae(c), w = je(c, () => p.load({ force: !0 })), E = Me(c, () => p.load({ force: !0 })), O = g(c.visible !== !1), j = g(!1), M = g(), N = g(), P = g(), F = p.state.query, I = C(() => p.state.selected);
		C(() => Math.max(1, Math.ceil(p.state.total / F.size)));
		let R = C(() => p.state.config?.providers || w.state.config?.providers || []), ae = g(), z = 0, oe = C(() => p.state.items.length > 0 && p.state.items.every((e) => I.value.has(String(e.task_id))));
		ee(M, () => j.value, () => O.value), ee(N, () => !!E.state.drawer, () => O.value), ee(P, () => !!E.state.payment.open, () => O.value);
		let B = g(null), ue = C(() => ({
			query: F.query,
			provider: F.provider,
			mode: F.mode,
			status: F.status,
			batch: F.batch
		})), W = {
			query: "账号",
			provider: "平台",
			mode: "模式",
			status: "提链状态",
			batch: "批次"
		}, K = C(() => Object.entries(ue.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${W[e]}：${e === "provider" ? R.value.find((e) => e.id === t)?.label || H(t) : e === "mode" ? U(t) : e === "status" ? le.find((e) => e[0] === t)?.[1] || t : e === "batch" ? p.state.batchDetail?.title || `#${t}` : t}`,
			removeLabel: `清除${W[e]}筛选`
		})));
		function q(e, t) {
			B.value = null, e === "batch" ? Tn(t) : (F[e] = t, F.page = 1, Q());
		}
		function me() {
			Object.assign(F, {
				query: "",
				provider: "",
				mode: "",
				status: "",
				page: 1
			}), Tn("");
		}
		function _e(e) {
			F.page = e, Q();
		}
		function ye(e) {
			F.page = 1, F.size = e, Q();
		}
		let Y = C(() => p.state.batchDetail?.title || `批次 #${F.batch}`);
		function we(e) {
			p.loadBatchPage(e);
		}
		let Te = C(() => [...R.value, ...(p.state.config?.unavailable_providers || []).filter((e) => !R.value.some((t) => t.id === e.id)).map((e) => ({
			...e,
			label: `${e.label || H(e.id)}（已停用）`
		}))]), De = C(() => R.value.find((e) => e.id === w.state.provider)), X = C(() => E.state.detail?.item), ke = C(() => J(E.state.payment.entry?.payment_page_url)), Ne = C(() => J(E.state.payment.entry?.payment_url)), Pe = g(0), Fe = g(!1), Ie = C(() => xe(E.state.nodeA.entry || {}));
		r(() => E.state.nodeA.entry, () => {
			Pe.value = 0, Fe.value = !1;
		});
		function Le() {
			Pe.value + 1 < Ie.value.length ? Pe.value++ : Fe.value = !0;
		}
		let Re = g(0), ze = g(!1), Be = g(Date.now()), Z;
		r(() => E.state.payment.open, (e) => {
			Z && clearInterval(Z), Z = void 0, e && (Be.value = Date.now(), Z = setInterval(() => {
				Be.value = Date.now();
			}, 1e3));
		}), b(() => {
			Z && clearInterval(Z);
		});
		let Ve = C(() => xe(E.state.payment.entry || {}));
		function He() {
			Re.value + 1 < Ve.value.length ? Re.value++ : ze.value = !0;
		}
		async function gn(e) {
			Re.value = 0, ze.value = !1, await E.showPaymentEntry(e);
		}
		let _n = Ee;
		function vn(e) {
			return {
				legacy: "#64748b",
				huanguang: "#7c5cf0",
				anguang: "#0e9aa7",
				lumen: "#377dff",
				lumen_flow: "#377dff"
			}[e || ""] || "#98a2b3";
		}
		function yn(e) {
			return {
				passed: "success",
				success: "success",
				failed: "danger",
				running: "active",
				queued: "active",
				waiting: "active"
			}[e || ""] || "neutral";
		}
		function bn(e) {
			return {
				paid: "success",
				succeeded: "success",
				success: "success",
				awaiting_payment: "warning",
				pending: "warning",
				unpaid: "warning",
				pending_payment: "warning",
				processing: "active",
				running: "active",
				failed: "danger",
				expired: "danger",
				cancelled: "danger",
				canceled: "danger"
			}[e || ""] || "neutral";
		}
		function xn(e) {
			return {
				confirmed: "success",
				plus: "success",
				not_confirmed: "danger",
				checking: "active",
				unavailable: "warning"
			}[e || ""] || "neutral";
		}
		function Sn(e) {
			let t = V(e.status || e.task_status, "状态未记录"), n = e.error_info?.summary || e.error_message || e.error || e.message || "";
			return n ? `${t} · ${n}` : t;
		}
		function Cn() {
			w.setProvider(w.state.provider);
		}
		function wn() {
			ae.value && (ae.value.scrollTop = 0, ae.value.scrollLeft = 0);
		}
		async function Q(e = {}) {
			let t = e.quiet ? z : ++z;
			await p.load(e), !e.quiet && t === z && O.value && !p.state.error && wn();
		}
		async function Tn(e) {
			let t = ++z;
			await p.switchBatch(e), t === z && O.value && !p.state.error && wn();
		}
		function En(e, t, n) {
			if (e.target !== t || !t) return;
			let r = t.getBoundingClientRect();
			(e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) && n();
		}
		function $() {
			j.value = !1, w.close();
		}
		function Dn() {
			$(), E.closeDialogs();
		}
		function On(e) {
			O.value = e, p.setVisible(e), e || (B.value = null, $(), E.closeDialogs());
		}
		function kn(e) {
			I.value.has(e) ? I.value.delete(e) : I.value.add(e);
		}
		function An(e) {
			p.state.items.forEach((t) => e ? I.value.add(String(t.task_id)) : I.value.delete(String(t.task_id)));
		}
		async function jn() {
			j.value = !0, await w.open(p.state.config || void 0), await w.preview();
		}
		async function Mn() {
			let e = await w.submit();
			e?.batch_id && ($(), await Tn(e.batch_id));
		}
		async function Nn() {
			await Q({ force: !0 });
		}
		return o(() => p.load()), b(() => {
			p.destroy(), w.destroy(), E.destroy();
		}), s({
			load: Q,
			setVisible: On,
			openCreate: jn,
			switchBatch: Tn,
			openDetail: E.openDetail,
			showPaymentEntry: gn,
			taskAction: E.taskAction,
			showLink: E.showLink,
			copy: E.copy,
			copyPayment: E.copyPayment,
			bulkAction: p.bulkAction,
			cancelBatch: p.cancelBatch,
			exportRows: p.exportRows,
			closeDialogs: Dn
		}), (e, r) => (t(), k("section", {
			class: "extract-page",
			"aria-busy": D(p).state.loading
		}, [
			y("header", Ge, [y("div", Ke, [r[52] ||= y("h1", { class: "ui-sr-only" }, "提链工作台", -1), D(p).state.summary ? (t(), k("div", qe, [y("span", null, [r[50] ||= A("今日出链 ", -1), y("strong", null, _(D(G)(D(p).state.summary.today_extracted)), 1)]), y("span", null, [r[51] ||= A("待支付 ", -1), y("strong", null, _(D(G)(D(p).state.summary.awaiting_payment)), 1)])])) : u("", !0)]), y("div", Je, [
				y("button", {
					type: "button",
					class: "ui-button",
					onClick: Nn
				}, "刷新"),
				y("button", {
					type: "button",
					class: "ui-button",
					onClick: r[0] ||= (e) => D(p).exportRows(!0)
				}, "导出当前筛选"),
				y("button", {
					type: "button",
					class: "ui-button ui-button--primary",
					onClick: jn
				}, "新建批次")
			])]),
			y("div", Ye, [
				y("div", Xe, [y("div", Ze, [
					y("span", Qe, "共 " + _(D(G)(D(p).state.total)) + " 条任务", 1),
					I.value.size ? (t(), k("div", $e, [
						y("strong", et, "已选 " + _(I.value.size) + " 项", 1),
						y("button", {
							type: "button",
							class: "ui-button",
							disabled: D(p).state.bulkBusy,
							onClick: r[1] ||= (e) => D(p).bulkAction("sync_status")
						}, "同步原单", 8, tt),
						y("button", {
							type: "button",
							class: "ui-button",
							onClick: r[2] ||= (e) => D(p).bulkAction("links")
						}, "复制支付链接"),
						y("button", {
							type: "button",
							class: "ui-button",
							onClick: r[3] ||= (e) => D(p).exportRows(!1)
						}, "导出选中"),
						y("button", {
							type: "button",
							class: "ui-link",
							onClick: r[4] ||= (e) => D(p).bulkAction("clear")
						}, "清除选择")
					])) : u("", !0),
					l(re, {
						items: K.value,
						onRemove: r[5] ||= (e) => q(e, "")
					}, null, 8, ["items"])
				]), y("div", nt, [
					K.value.length ? (t(), k("button", {
						key: 0,
						type: "button",
						class: "ui-link",
						onClick: me
					}, "清除筛选")) : u("", !0),
					l(Ue, {
						column: "batch",
						values: ue.value,
						providers: Te.value,
						batches: D(p).state.batches,
						"batch-busy": D(p).state.batchLoading,
						open: B.value === "batch",
						"onUpdate:open": r[7] ||= (e) => B.value = e ? "batch" : null,
						onChange: q
					}, {
						default: n(() => [
							D(p).state.batchLoading ? (t(), k("p", rt, "正在读取批次…")) : u("", !0),
							D(p).state.auxErrors.batches ? (t(), k("div", it, [r[53] ||= A(" 批次读取失败 ", -1), y("button", {
								type: "button",
								class: "ui-link",
								onClick: r[6] ||= (e) => we(D(p).state.batchPage)
							}, "重试")])) : u("", !0),
							D(p).state.batchTotal > 20 ? (t(), v(te, {
								key: 2,
								class: "extract-batch-pager",
								label: "提链批次分页",
								page: D(p).state.batchPage,
								size: 20,
								"page-sizes": [20],
								total: D(p).state.batchTotal,
								busy: D(p).state.batchLoading,
								"onUpdate:page": we
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
					y("span", at, [l(Ue, {
						"omit-batch": "",
						values: ue.value,
						providers: Te.value,
						batches: D(p).state.batches,
						counts: D(p).state.counts,
						open: B.value === "all",
						"onUpdate:open": r[8] ||= (e) => B.value = e ? "all" : null,
						onChange: q
					}, null, 8, [
						"values",
						"providers",
						"batches",
						"counts",
						"open"
					])]),
					D(F).batch ? (t(), k("button", {
						key: 1,
						type: "button",
						class: "ui-link ui-link--danger extract-cancel",
						title: Y.value,
						disabled: !!D(p).state.cancellingBatch,
						onClick: r[9] ||= (e) => D(p).cancelBatch()
					}, "取消当前批次", 8, ot)) : u("", !0)
				])]),
				D(p).state.error ? (t(), k("p", st, [A(_(D(p).state.error) + " ", 1), y("button", {
					type: "button",
					class: "ui-link",
					onClick: Nn
				}, "重试")])) : u("", !0),
				D(E).state.error ? (t(), k("p", ct, _(D(E).state.error), 1)) : u("", !0),
				y("div", {
					ref_key: "tableScroll",
					ref: ae,
					class: "ui-table-scroll extract-table-wrap",
					role: "region",
					"aria-label": "提链任务表格",
					tabindex: "0"
				}, [y("table", lt, [y("thead", null, [y("tr", null, [
					y("th", ut, [y("input", {
						type: "checkbox",
						"aria-label": "选择本页提链任务",
						checked: oe.value,
						onChange: r[10] ||= (e) => An(e.target.checked)
					}, null, 40, dt)]),
					(t(), k(m, null, a([
						"query",
						"provider",
						"mode"
					], (e) => y("th", { key: e }, [l(Ue, {
						column: e,
						values: ue.value,
						providers: Te.value,
						batches: D(p).state.batches,
						counts: D(p).state.counts,
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
					r[54] ||= y("th", null, "准备", -1),
					y("th", null, [l(Ue, {
						column: "status",
						values: ue.value,
						providers: Te.value,
						batches: D(p).state.batches,
						counts: D(p).state.counts,
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
					r[55] ||= y("th", null, "支付", -1),
					r[56] ||= y("th", null, "Plus", -1),
					r[57] ||= y("th", null, "更新时间", -1),
					r[58] ||= y("th", null, "操作", -1)
				])]), y("tbody", null, [(t(!0), k(m, null, a(D(p).state.items, (e) => (t(), k("tr", {
					key: String(e.task_id),
					class: S({ "is-selected": I.value.has(String(e.task_id)) })
				}, [
					y("td", ft, [y("input", {
						type: "checkbox",
						"aria-label": `选择提链任务 ${e.task_id}`,
						checked: I.value.has(String(e.task_id)),
						onChange: (t) => kn(String(e.task_id))
					}, null, 40, pt)]),
					y("td", null, [l(L, {
						text: e.email || "账号未记录",
						secondary: `#${e.task_id}`
					}, null, 8, ["text", "secondary"])]),
					y("td", null, [l(L, {
						text: D(H)(e.provider_id),
						secondary: e.link_type || void 0
					}, {
						default: n(() => [y("span", mt, [y("i", {
							style: h({ background: vn(e.provider_id) }),
							"aria-hidden": "true"
						}, null, 4), A(_(D(H)(e.provider_id)), 1)])]),
						_: 2
					}, 1032, ["text", "secondary"])]),
					y("td", null, [l(L, {
						text: D(U)(e.mode),
						secondary: D(he)(e) || void 0
					}, null, 8, ["text", "secondary"])]),
					y("td", null, [l(L, {
						text: D(V)(e.preflight_status, "未开始"),
						tone: yn(e.preflight_status)
					}, null, 8, ["text", "tone"])]),
					y("td", null, [l(ie, {
						"data-extract-result": "",
						label: D(_n)(e).label,
						tone: D(_n)(e).tone,
						title: D(be)(e).detail
					}, {
						details: n(() => [
							y("p", null, _(D(be)(e).label), 1),
							y("p", null, _(D(be)(e).detail), 1),
							e.message ? (t(), k("p", ht, _(e.message), 1)) : u("", !0),
							e.error ? (t(), k("p", gt, _(e.error), 1)) : u("", !0),
							e.progress?.label ? (t(), k("p", _t, _(e.progress.label), 1)) : u("", !0)
						]),
						_: 2
					}, 1032, [
						"label",
						"tone",
						"title"
					])]),
					y("td", null, [l(L, {
						text: D(V)(e.payment_phase || e.payment_status, "—"),
						tone: bn(e.payment_phase || e.payment_status)
					}, null, 8, ["text", "tone"])]),
					y("td", null, [l(L, {
						text: D(V)(e.plus_state || e.plus_status, "未核验"),
						tone: xn(e.plus_state || e.plus_status)
					}, null, 8, ["text", "tone"])]),
					y("td", null, [l(L, { text: D(de)(e.updated_at || e.created_at) }, null, 8, ["text"])]),
					y("td", null, [y("div", vt, [y("button", {
						type: "button",
						class: "ui-link",
						onClick: (t) => D(E).openDetail(e.task_id)
					}, "详情", 8, yt), y("button", {
						type: "button",
						class: "ui-link",
						disabled: !(e.has_payment_entry || e.has_payment_link || e.has_qr),
						onClick: (t) => gn(e.task_id)
					}, "支付入口", 8, bt)])])
				], 2))), 128)), D(p).state.items.length ? u("", !0) : (t(), v(ne, {
					key: 0,
					colspan: 10,
					loading: D(p).state.loading,
					error: D(p).state.error ? " " : "",
					"loading-title": "正在读取任务…",
					"error-title": "任务读取失败",
					title: K.value.length ? "没有符合筛选条件的任务" : "暂无提链任务"
				}, null, 8, [
					"loading",
					"error",
					"title"
				]))])])], 512),
				l(te, {
					class: "extract-task-pager",
					label: "提链任务分页",
					page: D(F).page,
					size: D(F).size,
					total: D(p).state.total,
					busy: D(p).state.loading,
					"onUpdate:page": _e,
					"onUpdate:size": ye
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy"
				])
			]),
			y("dialog", {
				ref_key: "createDialog",
				ref: M,
				class: "extract-dialog",
				"aria-labelledby": "extract-create-title",
				onCancel: x($, ["prevent"]),
				onClose: $,
				onClick: r[32] ||= (e) => En(e, M.value, $)
			}, [
				y("header", null, [r[59] ||= y("h2", { id: "extract-create-title" }, "新建提链批次", -1), y("button", {
					type: "button",
					onClick: $
				}, "关闭")]),
				y("div", xt, [
					y("label", null, [r[60] ||= A("批次名称", -1), i(y("input", { "onUpdate:modelValue": r[12] ||= (e) => D(w).state.title = e }, null, 512), [[T, D(w).state.title]])]),
					y("label", null, [r[61] ||= A("账号搜索", -1), i(y("input", {
						"onUpdate:modelValue": r[13] ||= (e) => D(w).state.filters.query = e,
						onInput: r[14] ||= (...e) => D(w).invalidate && D(w).invalidate(...e)
					}, null, 544), [[T, D(w).state.filters.query]])]),
					y("label", null, [r[63] ||= A("来源", -1), i(y("select", {
						"onUpdate:modelValue": r[15] ||= (e) => D(w).state.filters.source = e,
						onChange: r[16] ||= (...e) => D(w).invalidate && D(w).invalidate(...e)
					}, [r[62] ||= y("option", { value: "" }, "全部来源", -1), (t(!0), k(m, null, a(D(c).accountSources || {}, (e, n) => (t(), k("option", {
						key: n,
						value: n
					}, _(e), 9, St))), 128))], 544), [[d, D(w).state.filters.source]])]),
					y("label", null, [r[64] ||= A("注册日期从", -1), i(y("input", {
						"onUpdate:modelValue": r[17] ||= (e) => D(w).state.filters.date_from = e,
						type: "date",
						onChange: r[18] ||= (...e) => D(w).invalidate && D(w).invalidate(...e)
					}, null, 544), [[T, D(w).state.filters.date_from]])]),
					y("label", null, [r[65] ||= A("注册日期至", -1), i(y("input", {
						"onUpdate:modelValue": r[19] ||= (e) => D(w).state.filters.date_to = e,
						type: "date",
						onChange: r[20] ||= (...e) => D(w).invalidate && D(w).invalidate(...e)
					}, null, 544), [[T, D(w).state.filters.date_to]])]),
					y("label", null, [r[67] ||= A("提链状态", -1), i(y("select", {
						"onUpdate:modelValue": r[21] ||= (e) => D(w).state.filters.extract_status = e,
						onChange: r[22] ||= (...e) => D(w).invalidate && D(w).invalidate(...e)
					}, [...r[66] ||= [f("<option value=\"not_succeeded\" data-v-012af3c7>未成功提链</option><option value=\"all\" data-v-012af3c7>全部可用账号</option><option value=\"failed\" data-v-012af3c7>失败</option><option value=\"never\" data-v-012af3c7>从未提链</option><option value=\"success\" data-v-012af3c7>已成功提链</option>", 5)]], 544), [[d, D(w).state.filters.extract_status]])]),
					y("label", null, [r[68] ||= A("套餐优惠", -1), i(y("select", {
						"onUpdate:modelValue": r[23] ||= (e) => D(w).state.filters.promotion = e,
						onChange: r[24] ||= (...e) => D(w).invalidate && D(w).invalidate(...e)
					}, [(t(!0), k(m, null, a(D(ce), (e, n) => (t(), k("option", {
						key: n,
						value: n
					}, _(e), 9, Ct))), 128))], 544), [[d, D(w).state.filters.promotion]])]),
					y("label", null, [r[69] ||= A("本批运行数量", -1), i(y("input", {
						"onUpdate:modelValue": r[25] ||= (e) => D(w).state.limit = e,
						type: "number",
						min: "1",
						max: "5000",
						step: "1",
						onInput: r[26] ||= (...e) => D(w).invalidate && D(w).invalidate(...e)
					}, null, 544), [[
						T,
						D(w).state.limit,
						void 0,
						{ number: !0 }
					]])]),
					y("label", null, [r[70] ||= A("平台", -1), i(y("select", {
						"onUpdate:modelValue": r[27] ||= (e) => D(w).state.provider = e,
						onChange: Cn
					}, [(t(!0), k(m, null, a(R.value, (e) => (t(), k("option", {
						key: e.id,
						value: e.id
					}, _(e.label || D(H)(e.id)), 9, wt))), 128)), (t(!0), k(m, null, a(D(w).state.config?.unavailable_providers || [], (e) => (t(), k("option", {
						key: e.id,
						value: e.id,
						disabled: ""
					}, _(e.label || D(H)(e.id)) + "（" + _(e.unavailable_reason || "已停用") + "）", 9, Tt))), 128))], 544), [[d, D(w).state.provider]])]),
					y("label", null, [r[71] ||= A("模式", -1), i(y("select", { "onUpdate:modelValue": r[28] ||= (e) => D(w).state.mode = e }, [(t(!0), k(m, null, a(D(fe)(De.value), (e) => (t(), k("option", {
						key: e,
						value: e
					}, _(D(U)(e)), 9, Et))), 128))], 512), [[d, D(w).state.mode]])]),
					y("label", null, [r[72] ||= A("链接类型", -1), i(y("select", { "onUpdate:modelValue": r[29] ||= (e) => D(w).state.type = e }, [(t(!0), k(m, null, a(D(pe)(De.value), (e) => (t(), k("option", {
						key: e,
						value: e
					}, _(D(se)[e] || e), 9, Dt))), 128))], 512), [[d, D(w).state.type]])]),
					y("label", null, [r[73] ||= A("并发", -1), i(y("input", {
						"onUpdate:modelValue": r[30] ||= (e) => D(w).state.workers = e,
						type: "number",
						min: "1",
						max: D(w).workersMax(),
						step: "1"
					}, null, 8, Ot), [[
						T,
						D(w).state.workers,
						void 0,
						{ number: !0 }
					]])])
				]),
				y("p", kt, _(D(Ce)(D(w).state.filters.promotion)), 1),
				y("p", At, _(D(w).state.feedback), 1),
				D(w).state.error ? (t(), k("p", jt, _(D(w).state.error), 1)) : u("", !0),
				y("footer", null, [
					y("button", {
						type: "button",
						disabled: D(w).state.loading || D(w).state.creating,
						onClick: r[31] ||= (...e) => D(w).preview && D(w).preview(...e)
					}, "刷新匹配数量", 8, Mt),
					y("button", {
						type: "button",
						class: "primary",
						disabled: D(w).state.creating || !D(w).state.preview?.selected_count,
						onClick: Mn
					}, "创建并运行（" + _(D(w).state.preview?.selected_count || 0) + "）", 9, Nt),
					y("button", {
						type: "button",
						onClick: $
					}, "取消")
				])
			], 544),
			y("dialog", {
				ref_key: "detailDialog",
				ref: N,
				class: "extract-dialog",
				"aria-labelledby": "extract-detail-title",
				onCancel: r[43] ||= x((...e) => D(E).closeDetail && D(E).closeDetail(...e), ["prevent"]),
				onClick: r[44] ||= (e) => En(e, N.value, D(E).closeDetail)
			}, [
				y("header", null, [r[74] ||= y("h2", { id: "extract-detail-title" }, "任务详情", -1), y("button", {
					type: "button",
					onClick: r[33] ||= (...e) => D(E).closeDetail && D(E).closeDetail(...e)
				}, "关闭")]),
				D(E).state.detailLoading ? (t(), k("p", Pt, "正在读取任务详情…")) : u("", !0),
				D(E).state.detailError ? (t(), k("p", Ft, _(D(E).state.detailError), 1)) : u("", !0),
				X.value ? (t(), k(m, { key: 2 }, [
					y("h3", null, _(X.value.email || "账号未记录") + " · #" + _(X.value.task_id), 1),
					y("div", It, [
						y("button", {
							type: "button",
							disabled: D(ge)(X.value),
							onClick: r[34] ||= (e) => D(E).taskAction(X.value.task_id, "sync_status")
						}, "同步状态", 8, Lt),
						y("button", {
							type: "button",
							disabled: !D(ve)(X.value),
							onClick: r[35] ||= (e) => D(E).taskAction(X.value.task_id, "retry")
						}, "重跑", 8, Rt),
						X.value.mode === "auto_payment" && X.value.payment_status !== "paid" ? (t(), k("button", {
							key: 0,
							type: "button",
							disabled: D(ge)(X.value),
							onClick: r[36] ||= (e) => D(E).taskAction(X.value.task_id, "auto_payment")
						}, "查询自动支付", 8, zt)) : u("", !0),
						y("button", {
							type: "button",
							onClick: r[37] ||= (e) => D(E).copy(X.value.task_id, "email")
						}, "复制邮箱"),
						X.value.account_id ? (t(), k("button", {
							key: 1,
							type: "button",
							onClick: r[38] ||= (e) => D(E).copy(X.value.task_id, "at")
						}, "复制 AT")) : u("", !0),
						X.value.has_extract_link ? (t(), k("button", {
							key: 2,
							type: "button",
							onClick: r[39] ||= (e) => D(E).showLink(X.value.task_id, "extract")
						}, "复制提链链接")) : u("", !0),
						X.value.has_payment_entry || X.value.has_payment_link || X.value.has_qr ? (t(), k("button", {
							key: 3,
							type: "button",
							onClick: r[40] ||= (e) => gn(X.value.task_id)
						}, "读取支付入口")) : u("", !0)
					]),
					y("p", null, _(D(H)(X.value.provider_id)) + " · " + _(D(U)(X.value.mode)) + _(D(he)(X.value)), 1),
					y("p", null, _(D(be)(X.value).label) + " · " + _(D(be)(X.value).detail), 1),
					y("dl", Bt, [
						y("div", null, [r[75] ||= y("dt", null, "准备", -1), y("dd", null, _(D(V)(X.value.preflight_status, "未开始")), 1)]),
						y("div", null, [r[76] ||= y("dt", null, "提链", -1), y("dd", null, _(D(V)(X.value.extraction_status)), 1)]),
						y("div", null, [r[77] ||= y("dt", null, "支付", -1), y("dd", null, _(D(V)(X.value.payment_status)), 1)]),
						y("div", null, [r[78] ||= y("dt", null, "本地 Plus 到账核验", -1), y("dd", null, _(D(V)(X.value.plus_status, "未核验")), 1)])
					]),
					X.value.stages ? (t(), k("section", Vt, [r[79] ||= y("h3", null, "执行阶段", -1), (t(!0), k(m, null, a(X.value.stages, (e, n) => (t(), k("div", {
						key: n,
						class: "extract-stage"
					}, [
						y("strong", null, _({
							prepare: "准备",
							run: "运行",
							verify: "核验"
						}[n] || n), 1),
						A(" · " + _(D(V)(e?.state || e?.status)) + " ", 1),
						y("span", null, _(e?.step), 1)
					]))), 128))])) : u("", !0),
					X.value.payment_order ? (t(), k("dl", Ht, [
						y("div", null, [r[80] ||= y("dt", null, "支付订单", -1), y("dd", null, _(X.value.payment_order.remote_order_id || "等待平台回执"), 1)]),
						y("div", null, [r[81] ||= y("dt", null, "支付提交", -1), y("dd", null, _(X.value.payment_order.submission_state || "响应缺失"), 1)]),
						y("div", null, [r[82] ||= y("dt", null, "支付状态", -1), y("dd", null, _(D(V)(X.value.payment_order.payment_state, "支付响应缺失")), 1)])
					])) : u("", !0),
					X.value.reconcile_halt?.halted ? (t(), k("p", Ut, _(X.value.reconcile_halt.label || "已停止自动续查") + " · " + _(X.value.reconcile_halt.reason), 1)) : u("", !0),
					y("section", Wt, [r[83] ||= y("h3", null, "节点 A · 出手的东西", -1), D(E).state.nodeA.loading ? (t(), k("p", Gt, "读取支付入口中…")) : D(E).state.nodeA.error ? (t(), k("div", Kt, [y("p", null, _(D(E).state.nodeA.error), 1), y("button", {
						type: "button",
						onClick: r[41] ||= (e) => D(E).loadNodeA(X.value.task_id)
					}, "重新读取节点 A")])) : D(E).state.nodeA.entry ? (t(), k(m, { key: 2 }, [
						y("p", null, "金额 " + _(D(E).state.nodeA.entry.amount ?? "平台未返回") + " " + _(D(E).state.nodeA.entry.currency || "") + " · 有效期 " + _(D(E).state.nodeA.entry.expires_at ? D(de)(D(E).state.nodeA.entry.expires_at) : "平台未返回"), 1),
						y("div", qt, [(t(), k(m, null, a(["payment_page_url", "payment_url"], (e) => (t(), k(m, { key: e }, [D(J)(D(E).state.nodeA.entry[e]) ? (t(), k(m, { key: 0 }, [y("a", {
							href: D(J)(D(E).state.nodeA.entry[e]),
							target: "_blank",
							rel: "noopener noreferrer"
						}, "打开" + _(e === "payment_page_url" ? "支付页面" : "支付入口"), 9, Jt), y("button", {
							type: "button",
							onClick: (t) => D(E).copyNodeA(e)
						}, "复制" + _(e === "payment_page_url" ? "支付页面" : "支付入口"), 9, Yt)], 64)) : u("", !0)], 64))), 64)), D(E).state.nodeA.entry.qr_data ? (t(), k("button", {
							key: 0,
							type: "button",
							onClick: r[42] ||= (e) => D(E).copyNodeA("qr_data")
						}, "复制节点 A 二维码")) : u("", !0)]),
						Ie.value.length && !Fe.value ? (t(), k("img", {
							key: 0,
							src: Ie.value[Pe.value],
							width: "208",
							height: "208",
							alt: "节点 A 支付二维码",
							referrerpolicy: "no-referrer",
							onError: Le
						}, null, 40, Xt)) : Fe.value ? (t(), k("p", Zt, "二维码图片加载失败，可使用支付链接或二维码原文。")) : u("", !0),
						D(E).state.nodeA.entry.qr_data ? (t(), k("pre", Qt, _(D(E).state.nodeA.entry.qr_data), 1)) : u("", !0)
					], 64)) : (t(), k("p", $t, "这一步还没有支付入口"))]),
					X.value.remote_raw ? (t(), k("details", en, [r[84] ||= y("summary", null, "平台原文", -1), y("pre", null, _(X.value.remote_raw), 1)])) : u("", !0),
					y("section", null, [
						r[85] ||= y("h3", null, "执行时间线", -1),
						y("ol", tn, [(t(!0), k(m, null, a(D(E).state.detail?.events || [], (e, n) => (t(), k("li", { key: n }, [
							y("strong", null, _(e.label || e.stage || "事件"), 1),
							A(" · " + _(D(V)(e.status, "")) + " · " + _(D(de)(e.at || e.created_at || e.time)), 1),
							e.message ? (t(), k("p", nn, _(e.message), 1)) : u("", !0)
						]))), 128))]),
						D(E).state.detail?.events?.length ? u("", !0) : (t(), k("p", rn, "暂无阶段事件"))
					]),
					D(E).state.detail?.history?.length ? (t(), k("details", an, [y("summary", null, "历史运行 " + _(D(E).state.detail.history.length) + " 次", 1), (t(!0), k(m, null, a(D(E).state.detail.history, (e, n) => (t(), k("article", { key: String(e.run_id || n) }, [
						y("h4", null, "运行 #" + _(e.run_id || n + 1), 1),
						y("p", on, _(Sn(e)), 1),
						y("pre", null, _(e), 1)
					]))), 128))])) : u("", !0),
					y("details", null, [r[86] ||= y("summary", null, "完整任务记录", -1), y("pre", null, _(X.value), 1)])
				], 64)) : u("", !0)
			], 544),
			y("dialog", {
				ref_key: "paymentDialog",
				ref: P,
				class: "extract-dialog",
				"aria-labelledby": "extract-payment-title",
				onCancel: r[48] ||= x((...e) => D(E).closePayment && D(E).closePayment(...e), ["prevent"]),
				onClick: r[49] ||= (e) => En(e, P.value, D(E).closePayment)
			}, [y("header", null, [r[87] ||= y("h2", { id: "extract-payment-title" }, "支付入口", -1), y("button", {
				type: "button",
				onClick: r[45] ||= (...e) => D(E).closePayment && D(E).closePayment(...e)
			}, "关闭")]), D(E).state.payment.loading ? (t(), k("p", sn, "读取中…")) : (t(), k(m, { key: 1 }, [D(E).state.payment.error ? (t(), k("div", cn, [y("p", null, _(D(E).state.payment.error), 1), y("button", {
				type: "button",
				onClick: r[46] ||= (e) => gn(D(E).state.payment.taskId)
			}, "重新读取")])) : u("", !0), D(E).state.payment.entry ? (t(), k(m, { key: 1 }, [
				y("dl", ln, [
					y("div", null, [r[88] ||= y("dt", null, "金额", -1), y("dd", null, _(D(E).state.payment.entry.amount ?? "平台未返回") + " " + _(D(E).state.payment.entry.currency || ""), 1)]),
					y("div", null, [r[89] ||= y("dt", null, "平台支付状态", -1), y("dd", null, _(D(Se)(D(E).state.payment.entry.payment_status)), 1)]),
					y("div", null, [r[90] ||= y("dt", null, "平台 Plus 核验", -1), y("dd", null, _(D(Se)(D(E).state.payment.entry.platform_plus_status, !0)), 1)]),
					y("div", null, [r[91] ||= y("dt", null, "有效期至", -1), y("dd", null, _(D(E).state.payment.entry.expires_at ? `${D(de)(D(E).state.payment.entry.expires_at)} · ${D(Oe)(D(E).state.payment.entry.expires_at, Be.value)}` : "平台未返回"), 1)])
				]),
				r[94] ||= y("p", { class: "extract-hint" }, "平台 Plus 状态供参考，本地到账以任务中的“Plus 到账核验”为准。", -1),
				(t(), k(m, null, a(["payment_page_url", "payment_url"], (e) => y("section", { key: e }, [y("h3", null, _(e === "payment_page_url" ? "支付页面" : "支付入口"), 1), (e === "payment_page_url" ? ke.value : Ne.value) ? (t(), k(m, { key: 0 }, [
					y("a", {
						href: e === "payment_page_url" ? ke.value : Ne.value,
						target: "_blank",
						rel: "noopener noreferrer"
					}, "打开", 8, un),
					y("button", {
						type: "button",
						onClick: (t) => D(E).copyPayment(e)
					}, "复制", 8, dn),
					y("pre", null, _(e === "payment_page_url" ? ke.value : Ne.value), 1)
				], 64)) : (t(), k("p", fn, "平台未返回"))])), 64)),
				y("section", null, [r[92] ||= y("h3", null, "支付二维码", -1), Ve.value.length && !ze.value ? (t(), k("img", {
					key: 0,
					src: Ve.value[Re.value],
					width: "208",
					height: "208",
					alt: "平台返回的支付二维码",
					referrerpolicy: "no-referrer",
					onError: He
				}, null, 40, pn)) : (t(), k("p", mn, _(ze.value ? "二维码图片加载失败。" : "平台未返回二维码图片。") + "可使用支付链接或复制下方二维码原文。", 1))]),
				y("section", null, [r[93] ||= y("h3", null, "二维码原文", -1), D(E).state.payment.entry.qr_data ? (t(), k(m, { key: 0 }, [y("button", {
					type: "button",
					onClick: r[47] ||= (e) => D(E).copyPayment("qr_data")
				}, "复制二维码内容"), y("pre", null, _(D(E).state.payment.entry.qr_data), 1)], 64)) : (t(), k("p", hn, "平台未返回"))])
			], 64)) : u("", !0)], 64))], 544)
		], 8, We));
	}
}), [["__scopeId", "data-v-012af3c7"]]);
// src/features/extract/useExtractStats.ts
function _n(e = {}) {
	let t = e.api || z(e), n = s({
		days: 30,
		provider: "",
		data: null,
		scope: "",
		error: "",
		loading: !1,
		visible: e.visible !== !1,
		providers: { ...oe }
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
			for (let e of l.providers || []) e.provider_id && (n.providers[e.provider_id] = oe[e.provider_id] || e.provider_id);
			e.onReady?.();
		} catch (e) {
			r === i && c() && (n.error = Y(e), n.data = l);
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
var vn = ["aria-busy"], yn = { class: "es-controls" }, bn = {
	class: "es-periods",
	role: "group",
	"aria-label": "统计时间范围"
}, xn = [
	"data-extract-stats-days",
	"aria-pressed",
	"onClick"
], Sn = ["value"], Cn = ["disabled"], wn = {
	class: "es-updated",
	role: "status"
}, Q = {
	key: 0,
	class: "es-notice",
	role: "alert"
}, Tn = {
	key: 1,
	class: "es-empty",
	role: "status"
}, En = {
	class: "es-today",
	"aria-label": "今日与当前"
}, $ = { class: "es-scope" }, Dn = { class: "es-metrics" }, On = { class: "es-summary-grid" }, kn = { class: "es-panel" }, An = { class: "es-conversion" }, jn = { class: "es-panel" }, Mn = { class: "es-state-grid" }, Nn = { class: "es-current" }, Pn = { class: "es-chart-grid" }, Fn = { class: "es-panel es-trend" }, In = { class: "es-legend" }, Ln = {
	viewBox: "0 0 880 242",
	role: "img",
	"aria-label": "每日提链任务、出链和支付趋势"
}, Rn = ["y1", "y2"], zn = ["y"], Bn = ["x"], Vn = ["d"], Hn = {
	key: 1,
	class: "es-empty"
}, Un = {
	key: 2,
	class: "es-daily-data"
}, Wn = { class: "es-table-scroll" }, Gn = { "aria-label": "每日趋势数据" }, Kn = { class: "es-panel" }, qn = { class: "es-panel-header" }, Jn = {
	key: 0,
	class: "es-failures"
}, Yn = {
	class: "es-failure-track",
	"aria-hidden": "true"
}, Xn = {
	key: 1,
	class: "es-empty"
}, Zn = { class: "es-panel" }, Qn = {
	key: 0,
	class: "es-table-scroll",
	tabindex: "0",
	"aria-label": "平台统计，可左右滚动"
}, $n = { class: "es-provider-table" }, er = ["title"], tr = ["title"], nr = {
	key: 1,
	class: "es-empty"
}, rr = { class: "es-panel" }, ir = {
	key: 0,
	class: "es-modes"
}, ar = {
	class: "es-mode-track",
	"aria-hidden": "true"
}, or = {
	key: 1,
	class: "es-empty"
}, sr = /*#__PURE__*/ O(/* @__PURE__ */ e({
	__name: "ExtractStats",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let r = _n(e.deps || {}), { state: s } = r, c = C(() => s.data), l = C(() => c.value?.totals || {}), f = C(() => c.value?.current || {}), p = C(() => c.value?.daily || []), g = C(() => p.value.at(-1) || {}), v = C(() => Object.entries(s.providers).filter(([e]) => e !== "lumen")), x = C(() => (c.value?.failures || []).filter((e) => W(e.count) > 0).sort((e, t) => W(t.count) - W(e.count)).slice(0, 5)), w = C(() => Math.max(1, ...x.value.map((e) => W(e.count)))), T = [
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
		], E = C(() => p.value.some((e) => W(e.total) > 0)), O = C(() => {
			let e = Math.max(1, ...p.value.flatMap((e) => T.map((t) => W(e[t.key]))));
			return e <= 4 ? 4 : Math.ceil(e / 4) * 4;
		}), j = (e) => 48 + (p.value.length === 1 ? 406 : e * 812 / Math.max(1, p.value.length - 1)), M = (e) => 22 + 184 * (1 - W(e) / O.value), N = C(() => [.../* @__PURE__ */ new Set([
			0,
			...p.value.map((e, t) => t).filter((e) => e % Math.max(1, Math.ceil(p.value.length / 7)) === 0),
			p.value.length - 1
		])].filter((e) => e >= 0)), P = (e) => p.value.map((t, n) => `${n ? "L" : "M"}${j(n).toFixed(2)},${M(t[e]).toFixed(2)}`).join(" "), F = (e) => W(l.value.total) ? Math.min(100, W(e.total) / W(l.value.total) * 100) : 0;
		function ee(e) {
			r.setVisible(e);
		}
		return o(() => void r.load()), b(r.destroy), n({
			load: r.load,
			setVisible: ee
		}), (e, n) => (t(), k("section", {
			class: "extract-stats-page",
			"aria-busy": D(s).loading
		}, [
			y("div", yn, [
				y("div", bn, [(t(), k(m, null, a([
					7,
					30,
					90
				], (e) => y("button", {
					key: e,
					type: "button",
					"data-extract-stats-days": e,
					"aria-pressed": D(s).days === e,
					onClick: (t) => {
						D(s).days = e, D(r).load();
					}
				}, "近 " + _(e) + " 天", 9, xn)), 64))]),
				y("label", null, [n[5] ||= A("平台", -1), i(y("select", {
					"onUpdate:modelValue": n[0] ||= (e) => D(s).provider = e,
					"data-extract-stats-provider": "",
					onChange: n[1] ||= (...e) => D(r).load && D(r).load(...e)
				}, [n[4] ||= y("option", { value: "" }, "全部平台", -1), (t(!0), k(m, null, a(v.value, ([e, n]) => (t(), k("option", {
					key: e,
					value: e
				}, _(n), 9, Sn))), 128))], 544), [[d, D(s).provider]])]),
				y("button", {
					type: "button",
					"data-extract-stats-refresh": "",
					disabled: D(s).loading,
					onClick: n[2] ||= (...e) => D(r).load && D(r).load(...e)
				}, "刷新", 8, Cn),
				y("span", wn, _(D(s).loading ? "正在汇总提链任务…" : c.value?.generated_at ? `更新于 ${D(de)(c.value.generated_at)}` : ""), 1)
			]),
			D(s).error ? (t(), k("div", Q, [y("span", null, _(D(s).data ? "刷新失败，以下保留上次统计。" : "未取得所选范围的统计。") + _(D(s).error), 1), y("button", {
				type: "button",
				"data-extract-stats-retry": "",
				onClick: n[3] ||= (...e) => D(r).load && D(r).load(...e)
			}, "重试")])) : u("", !0),
			!c.value && D(s).loading ? (t(), k("div", Tn, "正在汇总提链任务…")) : u("", !0),
			c.value ? (t(), k(m, { key: 2 }, [
				y("section", En, [n[9] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "今日与当前"), y("span", null, "今日任务按北京时间创建日归属")], -1), y("dl", null, [
					y("div", null, [n[6] ||= y("dt", null, "今日任务出链", -1), y("dd", null, _(D(G)(g.value.extracted)), 1)]),
					y("div", null, [n[7] ||= y("dt", null, "今日任务 Plus", -1), y("dd", null, _(D(G)(g.value.plus_confirmed)), 1)]),
					y("div", null, [n[8] ||= y("dt", null, [A("当前待支付"), y("small", null, "全部日期")], -1), y("dd", null, _(D(G)(f.value.awaiting_payment)), 1)])
				])]),
				y("div", $, [y("span", null, _(c.value.date_from || "—") + " — " + _(c.value.date_to || "—"), 1), n[10] ||= y("span", null, "按北京时间任务创建日归属", -1)]),
				y("div", Dn, [(t(), k(m, null, a([
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
					y("strong", null, _(D(G)(l.value[e.key])), 1),
					y("small", null, _(e.hint), 1)
				], 2)), 64))]),
				y("div", On, [y("section", kn, [n[17] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "转化与耗时"), y("span", null, "未结束任务不进入成功率分母")], -1), y("dl", An, [
					y("div", null, [
						n[11] ||= y("dt", null, "提链成功率", -1),
						y("dd", null, _(D(K)(l.value.extraction_rate)), 1),
						n[12] ||= y("span", null, "已出链 /（已出链 + 提链失败）", -1),
						y("small", null, "出链 " + _(D(G)(l.value.extracted)) + " · 失败 " + _(D(G)(l.value.extraction_failed)), 1)
					]),
					y("div", null, [
						n[13] ||= y("dt", null, "支付成功率", -1),
						y("dd", null, _(D(K)(l.value.payment_rate)), 1),
						n[14] ||= y("span", null, "已支付 /（已支付 + 支付失败）", -1),
						y("small", null, "支付 " + _(D(G)(l.value.paid)) + " · 失败 " + _(D(G)(l.value.payment_failed)), 1)
					]),
					y("div", null, [
						n[15] ||= y("dt", null, "平均耗时", -1),
						y("dd", null, _(D(q)(l.value.avg_seconds)), 1),
						n[16] ||= y("span", null, "最新成功运行的总耗时", -1)
					])
				])]), y("section", jn, [
					n[18] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "区间任务状态"), y("span", null, "所选范围的最新结果")], -1),
					y("dl", Mn, [(t(), k(m, null, a([
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
						}
					], (e) => y("div", { key: e.key }, [y("dt", null, _(e.label), 1), y("dd", null, _(D(G)(l.value[e.key])), 1)])), 64))]),
					y("p", Nn, _(D(s).provider ? "当前所选平台" : "当前全部平台") + "，全部日期：处理中 " + _(D(G)(f.value.processing)) + " · 待支付 " + _(D(G)(f.value.awaiting_payment)), 1)
				])]),
				y("div", Pn, [y("section", Fn, [
					n[23] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "每日趋势"), y("span", null, "按北京时间任务创建日归属")], -1),
					E.value ? (t(), k(m, { key: 0 }, [y("div", In, [(t(), k(m, null, a(T, (e) => y("span", {
						key: e.key,
						class: S(`es-series--${e.tone}`)
					}, _(e.label), 3)), 64))]), (t(), k("svg", Ln, [
						n[19] ||= y("title", null, "每日提链趋势，完整数据见下方表格", -1),
						(t(), k(m, null, a([
							0,
							1,
							2,
							3,
							4
						], (e) => y("g", { key: e }, [y("line", {
							x1: "48",
							x2: "860",
							y1: M(O.value * e / 4),
							y2: M(O.value * e / 4),
							class: "es-chart-gridline"
						}, null, 8, Rn), y("text", {
							x: "38",
							y: M(O.value * e / 4) + 4,
							"text-anchor": "end",
							class: "es-chart-label"
						}, _(D(G)(O.value * e / 4)), 9, zn)])), 64)),
						(t(!0), k(m, null, a(N.value, (e) => (t(), k("text", {
							key: e,
							x: j(e),
							y: "232",
							"text-anchor": "middle",
							class: "es-chart-label"
						}, _(String(p.value[e]?.date || "").slice(5)), 9, Bn))), 128)),
						(t(), k(m, null, a(T, (e) => y("path", {
							key: e.key,
							d: P(e.key),
							class: S(["es-chart-line", `es-series--${e.tone}`])
						}, null, 10, Vn)), 64))
					]))], 64)) : (t(), k("div", Hn, [...n[20] ||= [y("strong", null, "这个时间段还没有提链任务", -1), y("p", null, "选择其他时间范围，或在提链工作台新建批次。", -1)]])),
					p.value.length ? (t(), k("details", Un, [n[22] ||= y("summary", null, "查看每日明细数据", -1), y("div", Wn, [y("table", Gn, [n[21] ||= y("thead", null, [y("tr", null, [
						y("th", null, "日期（北京时间）"),
						y("th", null, "任务总数"),
						y("th", null, "已出链"),
						y("th", null, "已支付"),
						y("th", null, "Plus 已确认")
					])], -1), y("tbody", null, [(t(!0), k(m, null, a(p.value, (e) => (t(), k("tr", { key: e.date }, [
						y("th", null, _(e.date), 1),
						y("td", null, _(D(G)(e.total)), 1),
						y("td", null, _(D(G)(e.extracted)), 1),
						y("td", null, _(D(G)(e.paid)), 1),
						y("td", null, _(D(G)(e.plus_confirmed)), 1)
					]))), 128))])])])])) : u("", !0)
				]), y("section", Kn, [y("div", qn, [n[24] ||= y("h2", null, "失败分类", -1), y("span", null, _(D(G)(l.value.failed)) + " 个失败任务", 1)]), x.value.length ? (t(), k("ol", Jn, [(t(!0), k(m, null, a(x.value, (e) => (t(), k("li", { key: e.code || e.label }, [
					y("div", null, [y("span", null, _(e.label || e.code || "原因未记录"), 1), y("strong", null, _(D(G)(e.count)), 1)]),
					y("div", Yn, [y("span", { style: h({ width: `${D(W)(e.count) / w.value * 100}%` }) }, null, 4)]),
					y("code", null, _(e.code || "未记录错误码"), 1)
				]))), 128))])) : (t(), k("div", Xn, [...n[25] ||= [y("strong", null, "暂无失败记录", -1), y("p", null, "所选范围没有失败任务。", -1)]]))])]),
				y("section", Zn, [n[28] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "平台对比"), y("span", null, "支付成功与 Plus 到账分别统计")], -1), c.value.providers?.length ? (t(), k("div", Qn, [y("table", $n, [n[26] ||= y("thead", null, [y("tr", null, [
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
				])], -1), y("tbody", null, [(t(!0), k(m, null, a(c.value.providers, (e) => (t(), k("tr", { key: e.provider_id }, [
					y("th", null, _(D(H)(e.provider_id)), 1),
					y("td", null, _(D(G)(e.total)), 1),
					y("td", null, _(D(G)(e.extracted)), 1),
					y("td", { title: `已出链 ${D(G)(e.extracted)}，提链失败 ${D(G)(e.extraction_failed)}` }, _(D(K)(e.extraction_rate)), 9, er),
					y("td", null, _(D(G)(e.paid)), 1),
					y("td", { title: `已支付 ${D(G)(e.paid)}，支付失败 ${D(G)(e.payment_failed)}` }, _(D(K)(e.payment_rate)), 9, tr),
					y("td", null, _(D(G)(e.plus_confirmed)), 1),
					y("td", null, _(D(G)(e.failed)), 1),
					y("td", null, _(D(G)(e.processing)), 1),
					y("td", null, _(D(q)(e.avg_seconds)), 1)
				]))), 128))])])])) : (t(), k("div", nr, [...n[27] ||= [y("strong", null, "暂无平台数据", -1), y("p", null, "所选范围没有提链任务。", -1)]]))]),
				y("section", rr, [n[30] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "模式分布"), y("span", null, "所选范围内的任务组成")], -1), c.value.modes?.length ? (t(), k("div", ir, [(t(!0), k(m, null, a(c.value.modes, (e) => (t(), k("article", {
					key: e.mode,
					class: "es-mode"
				}, [
					y("div", null, [y("h3", null, _(D(U)(e.mode)), 1), y("span", null, _(D(W)(l.value.total) ? D(K)(F(e) / 100) : "—"), 1)]),
					y("strong", null, [A(_(D(G)(e.total)), 1), n[29] ||= y("small", null, " 个任务", -1)]),
					y("div", ar, [y("span", { style: h({ width: `${F(e)}%` }) }, null, 4)]),
					y("dl", null, [(t(), k(m, null, a([
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
					], (t) => y("div", { key: t.key }, [y("dt", null, _(t.label), 1), y("dd", null, _(D(G)(e[t.key])), 1)])), 64))])
				]))), 128))])) : (t(), k("div", or, "暂无模式数据"))])
			], 64)) : u("", !0)
		], 8, vn));
	}
}), [["__scopeId", "data-v-b7c02bd0"]]);
// src/extract.ts
function cr(e, t = {}) {
	let n = w(gn, { deps: t }), r = n.mount(e);
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
function lr(e, t = {}) {
	let n = w(sr, { deps: t }), r = n.mount(e);
	return {
		load: r.load,
		setVisible: r.setVisible,
		destroy: () => n.unmount()
	};
}
export { lr as mountExtractStats, cr as mountExtractWorkbench };
