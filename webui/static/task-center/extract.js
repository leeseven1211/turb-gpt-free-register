import { C as e, F as t, G as n, H as r, K as i, L as a, M as o, Q as s, R as c, S as l, _ as u, a as d, b as f, c as p, d as m, dt as h, et as g, ft as _, g as v, h as y, j as b, l as x, lt as S, m as C, n as w, o as T, st as E, t as D, v as O, x as k } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { r as A, t as j } from "./client-BBEPwkQG.js";
import { a as M, i as N, r as P } from "./taskIds-BlchWwUp.js";
import { t as ee } from "./useNativeDialog-DWisXYg9.js";
import { t as te } from "./ListPagination-BjETSj81.js";
import { n as F, r as I, t as ne } from "./ListFilterSummary-_oaD8AlZ.js";
import { t as re } from "./ListResult-BtznEB_S.js";
// src/api/extract.ts
var L = "/api/extract-workbench";
function ie(e) {
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
function R(e = {}) {
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
			let r = i(await t(`${L}/tasks?${ie(e)}`, { signal: n }));
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
			let t = ie(e);
			t.delete("page"), t.delete("page_size");
			let n = await fetch(`${L}/export?${t}`, { credentials: "same-origin" });
			if (!n.ok || n.redirected || !/(text\/csv|application\/octet-stream)/i.test(n.headers.get("content-type") || "")) throw new j("导出失败，请重新登录或重试", n.status);
			return n.blob();
		}
	};
}
// src/features/extract/presentation.ts
var z = {
	legacy: "虾扯蛋链",
	lumen: "Lumen Flow",
	lumen_flow: "Lumen Flow",
	huanguang: "幻光提链",
	anguang: "暗光（XXSYUN 一条龙）"
}, ae = {
	extract_only: "仅提链",
	manual_payment: "手动支付",
	auto_payment: "自动支付"
}, oe = {
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
}, se = {
	eligible: "全部可提链优惠",
	all: "全部（有无优惠）",
	free_trial: "免费试用",
	half_price: "半价",
	other_discount: "其他折扣",
	other_promo: "其他优惠",
	none: "无优惠"
}, ce = [
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
], le = {
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
}, B = (e, t = "状态记录缺失") => le[String(e || "").toLowerCase()] || String(e || "") || t, V = (e) => z[e || ""] || e || "未记录平台", ue = (e) => ae[e || ""] || e || "未记录模式", H = (e) => {
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? Math.floor(t) : 0;
}, U = (e) => H(e).toLocaleString("zh-CN");
function W(e) {
	if (e == null || e === "") return "—";
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 && t <= 1 ? `${(t * 100).toFixed(1)}%` : "—";
}
function de(e) {
	if (e == null || e === "" || !Number.isFinite(Number(e)) || Number(e) < 0) return "—";
	let t = Math.round(Number(e));
	return t < 60 ? `${t} 秒` : t < 3600 ? `${Math.floor(t / 60)} 分 ${t % 60} 秒` : `${Math.floor(t / 3600)} 小时 ${Math.floor(t % 3600 / 60)} 分`;
}
function fe(e) {
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
var pe = (e) => Array.isArray(e?.modes) ? e.modes : [], me = (e) => e?.link_types?.length ? [...new Set(e.link_types)] : e?.default_type ? [e.default_type] : [];
function he(e) {
	return e.payment_source ? e.payment_source_label || {
		native: "平台自带",
		xxsyun: "XXSYUN"
	}[e.payment_source] || "未知来源" : "";
}
var ge = (e) => e.mode === "auto_payment" && he(e) ? ` · 自动支付来源：${he(e)}` : "", _e = (e) => [
	"queued",
	"running",
	"waiting",
	"settling",
	"cancelling",
	"stopping"
].includes(e.task_status || "");
function ve(e) {
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
var ye = (e) => !_e(e) && !ve(e);
function G(e) {
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
function K(e) {
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
		tone: e.payment_status === "failed" || ve(e) ? "warning" : "success",
		detail: e.error_info?.summary || e.error || e.message || (e.mode === "extract_only" ? "仅提链已完成，未发起支付" : "支付链接已生成，支付与套餐结果分别记录")
	} : G(e) ? {
		label: B(G(e)),
		tone: "warning",
		detail: "原远端任务已保留，可同步原任务状态"
	} : ve(e) ? {
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
function q(e, t = !1) {
	let n = String(e || "").trim();
	if (t && /^data:image\/(?:png|svg\+xml);base64,[a-z0-9+/=\s]+$/i.test(n)) return n;
	try {
		let e = new URL(n);
		return ["http:", "https:"].includes(e.protocol) && !e.username && !e.password ? e.href : "";
	} catch {
		return "";
	}
}
var be = (e) => [...new Set([e.qr_image_url_png, e.qr_image_url_svg].map((e) => q(e, !0)).filter(Boolean))];
function xe(e, t = !1) {
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
var J = (e) => e instanceof Error ? e.message : "请求失败，请重试";
function Se(e) {
	return e === "all" ? "匹配套餐优惠已查明（有或无）的活跃、未归档 free 账号；套餐待查及状态未知的账号不包含，提交前仍会在线查活。" : e === "none" ? "仅匹配活跃、未归档且上次查询无优惠的 free 账号；当前优惠由提链平台判断，提交前仍会在线查活。" : `仅匹配活跃、未归档且具备${e === "eligible" ? "任一可提链" : `「${se[e] || e}」`}优惠的 free 账号；提交前仍会在线查活。`;
}
function Y(e) {
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
function Ce(e, t) {
	let n = URL.createObjectURL(e), r = document.createElement("a");
	r.href = n, r.download = t, document.body.append(r), r.click(), r.remove(), setTimeout(() => URL.revokeObjectURL(n), 2e3);
}
function we(e) {
	let t = K(e), n = e.payment_status === "paid", r = ["confirmed", "plus"].includes(e.plus_status || ""), i = n && r ? "支付与Plus确认" : n ? "已支付待核验" : r ? "Plus已到账" : G(e) ? "等待原单同步" : ve(e) ? "待核对" : ["success", "succeeded"].includes(e.extraction_status || "") ? e.payment_status === "failed" ? "已出链支付失败" : "已出链" : [
		"failed",
		"cancelled",
		"stopped"
	].includes(e.task_status || "") ? e.task_status === "cancelled" ? "已取消" : "提链未完成" : _e(e) ? "执行中" : "排队中";
	return {
		...t,
		label: i,
		detail: t.detail
	};
}
function Te(e) {
	if (e == null || e === "") return null;
	let t = Number(e);
	if (Number.isFinite(t) && t > 1e11) return t;
	let n = Date.parse(String(e));
	return Number.isFinite(n) ? n : null;
}
function Ee(e, t = Date.now()) {
	let n = Te(e);
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
}), De = 3e4;
function Oe(e = {}) {
	let t = e.api || R(e), n = s({
		query: X(),
		items: [],
		total: 0,
		counts: {},
		batches: [],
		batchTotal: 0,
		batchPage: 1,
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
		s && (p = setTimeout(() => void N({ quiet: !0 }), s));
	}
	function D(e, r) {
		if (!e && n.config && Date.now() - l < De) return Promise.resolve(n.config);
		if (m) return m.promise;
		let i = ++o, a = C(), s = t.config(a.signal).then((e) => (x(r) && m?.version === i && (n.config = e, n.auxErrors.config = "", l = Date.now(), E(f > 0)), e)).catch((e) => {
			throw x(r) && (n.auxErrors.config = J(e)), e;
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
			throw x(e) && (n.auxErrors.summary = J(t)), t;
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
		let a = ++o, s = C(), c = t.batches(e, s.signal).then((t) => (x(r) && e === n.batchPage && _.get(e)?.version === a && (n.batches = t.items, n.batchTotal = t.total, d = e, u = Date.now(), n.auxErrors.batches = ""), t)).catch((t) => {
			throw x(r) && e === n.batchPage && (n.auxErrors.batches = J(t)), t;
		}).finally(() => {
			y.delete(s), _.get(e)?.version === a && _.delete(e);
		});
		return _.set(e, {
			version: a,
			promise: c
		}), c;
	}
	function A(e, n) {
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
	async function j(e, t) {
		D(!!e.force, t).catch(() => {}), O(t).catch(() => {});
		let r = n.batchPage, i = n.query.batch, a = ++c, o = !!e.force || d !== r || Date.now() - u >= De;
		try {
			let s = o ? (await k(r, t)).items : n.batches;
			if (!x(t) || r !== n.batchPage || i !== n.query.batch || a !== c) return;
			if (!i) {
				n.batchDetail = null;
				return;
			}
			let l = (!e.quiet || o ? s.find((e) => String(e.batch_id) === i) : null) || (await A(i, t)).item;
			x(t) && i === n.query.batch && a === c && (n.batchDetail = l, n.auxErrors.detail = "", E(f > 0));
		} catch (e) {
			x(t) && i === n.query.batch && r === n.batchPage && (n.auxErrors.detail = J(e));
		}
	}
	async function N(r = {}) {
		if (!b()) return;
		w();
		let o = ++a, s = i, c = { ...n.query };
		g?.abort();
		let l = C();
		g = l, n.loading = !0, n.error = "", j(r, s);
		try {
			let r = await t.tasks(c, l.signal);
			if (!x(s) || o !== a) return;
			n.items = r.items, n.total = r.total, n.counts = r.counts || {}, n.query.page = r.page;
			for (let e of [...n.selected]) r.items.some((t) => String(t.task_id) === e) || n.selected.delete(e);
			f = 0, e.onReady?.(), E();
		} catch (e) {
			x(s) && o === a && (n.error = J(e), f++, E(!0));
		} finally {
			y.delete(l), x(s) && o === a && (n.loading = !1);
		}
	}
	async function P(e) {
		Object.assign(n.query, X(), { batch: e ? String(M(e)) : "" }), n.batchDetail = null, n.selected.clear(), c++, await N();
	}
	async function ee(r) {
		if (r === "clear") {
			n.selected.clear();
			return;
		}
		if (r === "export") {
			await F(!1);
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
						let { entry: i } = await t.paymentEntry(e.task_id), a = q(i.payment_page_url) || q(i.payment_url) || i.qr_data;
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
				S(`已提交同步：${o} 个${s ? `，失败 ${s} 个` : ""}`), await N({ force: !0 });
			} catch (e) {
				n.error = J(e);
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
				n.receipt = a, S(`批次 #${i}：已取消 ${a.cancelled || 0} 个排队任务，跳过 ${a.skipped || 0} 个${a.failed ? `，失败 ${a.failed} 个，可再次处理剩余任务` : ""}。`), await N({ force: !0 });
			} catch (e) {
				n.error = J(e);
			} finally {
				n.cancellingBatch = "";
			}
		}
	}
	async function F(e = !0) {
		try {
			if (e) {
				Ce(await t.export({ ...n.query }), "extract-workbench.csv"), S("已导出当前筛选结果（最多 5000 条）");
				return;
			}
			let r = n.items.filter((e) => n.selected.has(String(e.task_id)));
			Ce(new Blob([Y(r)], { type: "text/csv;charset=utf-8" }), "extract-workbench-selected.csv");
		} catch (e) {
			n.error = J(e);
		}
	}
	function I() {
		i++, a++, c++, w(), y.forEach((e) => e.abort()), y.clear(), g = void 0, m = void 0, h = void 0, _.clear(), v.clear(), n.loading = !1;
	}
	function ne(e) {
		n.visible === e ? e && !n.loading && N() : (n.visible = e, e ? N() : I());
	}
	function re() {
		document.hidden ? I() : n.visible && N();
	}
	document.addEventListener("visibilitychange", re);
	function L() {
		r = !0, I(), document.removeEventListener("visibilitychange", re);
	}
	return {
		state: n,
		load: N,
		setVisible: ne,
		switchBatch: P,
		bulkAction: ee,
		cancelBatch: te,
		exportRows: F,
		destroy: L
	};
}
// src/features/extract/useExtractBatch.ts
function ke(e = {}, t = async () => {}) {
	let n = e.api || R(e), i = s({
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
		let t = i.config?.providers.find((t) => t.id === e), n = pe(t), r = me(t);
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
			!a && e === o && i.opened && (i.error = `匹配数量统计失败：${J(t)}`, i.feedback = "请检查筛选条件后重试。");
		} finally {
			e === o && (i.loading = !1);
		}
	}
	async function y() {
		if (!a && !i.creating && i.opened && i.preview?.selected_count && i.previewSignature === f()) {
			i.creating = !0, i.error = "";
			try {
				let r = i.config?.providers.find((e) => e.id === i.provider), o = pe(r), s = me(r), c = Number(i.workers), l = Number(i.limit);
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
				if (u.mode === "auto_payment" && !await (e.confirm ? e.confirm(`将为本批约 ${i.preview.selected_count} 个账号启用自动支付任务${ge({
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
				i.error = `${J(e)}；可重试获取同一批次的提交结果。`;
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
function Ae(e = {}, t = async () => {}) {
	let n = e.api || R(e), r = s({
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
			!i && t === a && (r.detailError = J(e));
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
			!i && r.drawer && t === c && (r.nodeA.error = J(e));
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
			!i && t === o && (r.payment.error = J(e));
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
				if (_e(i)) throw Error("任务正在执行，请等待当前运行结束");
				if (o !== "sync_status" && !ye(i)) throw Error("远端结果尚未确认，请同步原任务状态，不能重新提交");
				if (o === "auto_payment" && !await (e.confirm ? e.confirm("确认查询并继续此任务已保存的自动支付原单？") : window.confirm("确认继续此任务的自动支付？"))) return;
				let s = await n.action(a, o);
				if (s.accepted !== !0) throw Error(s.error || "操作未接受");
				r.receipt = s, f("任务操作已提交");
				try {
					await t();
				} catch {}
			} catch (e) {
				r.error = J(e), f(r.error);
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
				let r = await n.links(M(e), t), i = q(r.url || r.link);
				if (!i) throw Error("服务端未返回有效链接");
				t === "extract" ? await p(i) : window.open(i, "_blank", "noopener,noreferrer");
			} catch (e) {
				r.error = J(e), f(r.error);
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
				r.error = J(e), f(r.error);
			} finally {
				r.busy.delete(i);
			}
		}
	}
	async function b(e) {
		try {
			await p(e === "qr_data" ? String(r.payment.entry?.qr_data || "") : q(r.payment.entry?.[e]));
		} catch (e) {
			r.payment.error = J(e);
		}
	}
	async function x(e) {
		try {
			await p(e === "qr_data" ? String(r.nodeA.entry?.qr_data || "") : q(r.nodeA.entry?.[e]));
		} catch (e) {
			r.nodeA.error = J(e);
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
var je = { class: "extract-filter-fields" }, Me = { key: 0 }, Ne = ["value"], Pe = ["value"], Fe = ["value"], Z = ["value"], Ie = ["value"], Le = ["value"], Re = ["value"], ze = ["value"], Be = ["value"], Ve = ["value"], He = ["value"], Q = { class: "extract-filter-actions" }, Ue = /*#__PURE__*/ D(/* @__PURE__ */ e({
	__name: "ExtractFilters",
	props: {
		column: {},
		values: {},
		providers: {},
		batches: {},
		counts: {},
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
			default: n(() => [y("div", je, [
				e.column ? u("", !0) : (t(), O("label", Me, [s[10] ||= k("筛选列", -1), i(y("select", {
					"onUpdate:modelValue": s[0] ||= (e) => f.value = e,
					"aria-label": "选择提链任务筛选列"
				}, [(t(), O(m, null, a(o, (e, t) => y("option", {
					key: t,
					value: t
				}, _(e), 9, Ne)), 64))], 512), [[d, f.value]])])),
				y("label", null, [k(_(o[h.value]) + " ", 1), h.value === "query" ? (t(), O("input", {
					key: 0,
					type: "search",
					value: b.value,
					"aria-label": "筛选账号值",
					placeholder: "邮箱或任务号",
					onChange: s[1] ||= (e) => x(e.target.value),
					onKeydown: s[2] ||= p((e) => l("update:open", !1), ["enter"])
				}, null, 40, Pe)) : h.value === "provider" ? (t(), O("select", {
					key: 1,
					value: b.value,
					"aria-label": "筛选平台值",
					onChange: s[3] ||= (e) => x(e.target.value)
				}, [s[11] ||= y("option", { value: "" }, "全部平台", -1), (t(!0), O(m, null, a(e.providers, (e) => (t(), O("option", {
					key: e.id,
					value: e.id
				}, _(e.label || e.id), 9, Z))), 128))], 40, Fe)) : h.value === "mode" ? (t(), O("select", {
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
				}, _(E(ue)(e)), 9, Le)), 64))], 40, Ie)) : h.value === "status" ? (t(), O("select", {
					key: 3,
					value: b.value,
					"aria-label": "筛选提链状态值",
					onChange: s[5] ||= (e) => x(e.target.value)
				}, [(t(!0), O(m, null, a(E(ce), (n) => (t(), O("option", {
					key: n[0],
					value: n[0]
				}, _(n[1]) + _(e.counts && e.counts[n[0] || "all"] !== void 0 ? ` (${e.counts[n[0] || "all"]})` : ""), 9, ze))), 128))], 40, Re)) : (t(), O("select", {
					key: 4,
					value: b.value,
					"aria-label": "筛选批次值",
					onChange: s[6] ||= (e) => x(e.target.value)
				}, [
					s[13] ||= y("option", { value: "" }, "全部任务", -1),
					b.value && !e.batches.some((e) => String(e.batch_id) === b.value) ? (t(), O("option", {
						key: 0,
						value: b.value
					}, "批次 #" + _(b.value), 9, Ve)) : u("", !0),
					(t(!0), O(m, null, a(e.batches, (e) => (t(), O("option", {
						key: String(e.batch_id),
						value: String(e.batch_id)
					}, _(e.title || `批次 #${e.batch_id}`), 9, He))), 128))
				], 40, Be))]),
				h.value === "batch" ? c(r.$slots, "default", {}, void 0, !0, 1) : u("", !0),
				y("div", Q, [y("button", {
					type: "button",
					onClick: s[7] ||= (e) => x("")
				}, "清除此列"), y("button", {
					type: "button",
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
}), [["__scopeId", "data-v-e44aaa2a"]]), We = ["aria-busy"], Ge = { class: "extract-toolbar" }, Ke = { class: "extract-toolbar-actions" }, qe = ["disabled"], Je = {
	key: 0,
	class: "extract-metrics"
}, Ye = {
	class: "extract-count-row",
	"data-extract-count-row": ""
}, Xe = { class: "extract-count-main" }, Ze = { class: "extract-count" }, Qe = { class: "extract-count-actions" }, $e = { class: "extract-mobile-filter" }, et = {
	key: 1,
	class: "extract-batch-pages"
}, tt = {
	key: 2,
	class: "notice error",
	role: "alert"
}, nt = {
	key: 3,
	class: "notice error",
	role: "alert"
}, rt = {
	key: 4,
	class: "extract-bulk"
}, it = ["disabled"], at = ["checked"], ot = [
	"aria-label",
	"checked",
	"onChange"
], st = { key: 0 }, ct = { key: 1 }, lt = { key: 2 }, ut = { class: "extract-row-actions" }, dt = ["onClick"], ft = ["disabled", "onClick"], pt = { key: 0 }, mt = { class: "extract-form-grid" }, ht = ["value"], gt = ["value"], _t = ["value"], vt = ["value"], yt = ["value"], bt = ["value"], xt = ["max"], St = { class: "extract-hint" }, Ct = { role: "status" }, wt = {
	key: 0,
	class: "error",
	role: "alert"
}, Tt = ["disabled"], Et = ["disabled"], Dt = {
	key: 0,
	role: "status"
}, Ot = {
	key: 1,
	class: "error",
	role: "alert"
}, kt = {
	class: "extract-detail-actions",
	role: "group",
	"aria-label": "任务操作"
}, At = ["disabled"], jt = ["disabled"], Mt = ["disabled"], Nt = { class: "extract-facts" }, Pt = {
	key: 0,
	"aria-label": "阶段证据"
}, Ft = {
	key: 1,
	class: "extract-facts"
}, It = {
	key: 2,
	class: "notice"
}, Lt = {
	class: "extract-node-a",
	"data-extract-node-a": ""
}, Rt = {
	key: 0,
	role: "status"
}, zt = {
	key: 1,
	role: "alert"
}, Bt = { class: "extract-detail-actions" }, Vt = ["href"], Ht = ["onClick"], Ut = ["src"], Wt = { key: 1 }, Gt = { key: 2 }, Kt = { key: 3 }, qt = { key: 3 }, Jt = { class: "extract-timeline" }, Yt = { key: 0 }, Xt = { key: 0 }, Zt = {
	key: 4,
	"data-extract-history": ""
}, Qt = { "data-extract-run-outcome": "" }, $t = {
	key: 0,
	role: "status"
}, en = {
	key: 0,
	class: "error",
	role: "alert"
}, tn = { class: "extract-facts" }, nn = ["href"], rn = ["onClick"], an = { key: 1 }, on = ["src"], sn = { key: 1 }, cn = { key: 1 }, ln = /*#__PURE__*/ D(/* @__PURE__ */ e({
	__name: "ExtractWorkbench",
	props: { deps: {} },
	setup(e, { expose: s }) {
		let c = e.deps || {}, p = Oe(c), h = ke(c, () => p.load({ force: !0 })), v = Ae(c, () => p.load({ force: !0 })), S = g(c.visible !== !1), w = g(!1), D = g(), A = g(), j = g(), M = p.state.query, N = C(() => p.state.selected);
		C(() => Math.max(1, Math.ceil(p.state.total / M.size)));
		let P = C(() => p.state.config?.providers || h.state.config?.providers || []), I = g(), L = 0, ie = C(() => p.state.items.length > 0 && p.state.items.every((e) => N.value.has(String(e.task_id))));
		ee(D, () => w.value, () => S.value), ee(A, () => !!v.state.drawer, () => S.value), ee(j, () => !!v.state.payment.open, () => S.value);
		let R = g(null), z = C(() => ({
			query: M.query,
			provider: M.provider,
			mode: M.mode,
			status: M.status,
			batch: M.batch
		})), ae = {
			query: "账号",
			provider: "平台",
			mode: "模式",
			status: "提链状态",
			batch: "批次"
		}, le = C(() => Object.entries(z.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${ae[e]}：${e === "provider" ? P.value.find((e) => e.id === t)?.label || V(t) : e === "mode" ? ue(t) : e === "status" ? ce.find((e) => e[0] === t)?.[1] || t : e === "batch" ? p.state.batchDetail?.title || `#${t}` : t}`,
			removeLabel: `清除${ae[e]}筛选`
		})));
		function H(e, t) {
			R.value = null, e === "batch" ? ln(t) : (M[e] = t, M.page = 1, Q());
		}
		function W() {
			Object.assign(M, {
				query: "",
				provider: "",
				mode: "",
				status: "",
				page: 1
			}), ln("");
		}
		function de(e) {
			M.page = e, Q();
		}
		function he(e) {
			M.page = 1, M.size = e, Q();
		}
		function ve(e) {
			p.state.batchPage = e, Q();
		}
		let G = C(() => [...P.value, ...(p.state.config?.unavailable_providers || []).filter((e) => !P.value.some((t) => t.id === e.id)).map((e) => ({
			...e,
			label: `${e.label || V(e.id)}（已停用）`
		}))]), J = C(() => P.value.find((e) => e.id === h.state.provider)), Y = C(() => v.state.detail?.item), Ce = C(() => q(v.state.payment.entry?.payment_page_url)), Te = C(() => q(v.state.payment.entry?.payment_url)), X = g(0), De = g(!1), je = C(() => be(v.state.nodeA.entry || {}));
		r(() => v.state.nodeA.entry, () => {
			X.value = 0, De.value = !1;
		});
		function Me() {
			X.value + 1 < je.value.length ? X.value++ : De.value = !0;
		}
		let Ne = g(0), Pe = g(!1), Fe = g(Date.now()), Z;
		r(() => v.state.payment.open, (e) => {
			Z && clearInterval(Z), Z = void 0, e && (Fe.value = Date.now(), Z = setInterval(() => {
				Fe.value = Date.now();
			}, 1e3));
		}), b(() => {
			Z && clearInterval(Z);
		});
		let Ie = C(() => be(v.state.payment.entry || {}));
		function Le() {
			Ne.value + 1 < Ie.value.length ? Ne.value++ : Pe.value = !0;
		}
		async function Re(e) {
			Ne.value = 0, Pe.value = !1, await v.showPaymentEntry(e);
		}
		let ze = we;
		function Be(e) {
			let t = B(e.status || e.task_status, "状态未记录"), n = e.error_info?.summary || e.error_message || e.error || e.message || "";
			return n ? `${t} · ${n}` : t;
		}
		function Ve() {
			h.setProvider(h.state.provider);
		}
		function He() {
			I.value && (I.value.scrollTop = 0, I.value.scrollLeft = 0);
		}
		async function Q(e = {}) {
			let t = e.quiet ? L : ++L;
			await p.load(e), !e.quiet && t === L && S.value && !p.state.error && He();
		}
		async function ln(e) {
			let t = ++L;
			await p.switchBatch(e), t === L && S.value && !p.state.error && He();
		}
		function un(e, t, n) {
			if (e.target !== t || !t) return;
			let r = t.getBoundingClientRect();
			(e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) && n();
		}
		function $() {
			w.value = !1, h.close();
		}
		function dn() {
			$(), v.closeDialogs();
		}
		function fn(e) {
			S.value = e, p.setVisible(e), e || (R.value = null, $(), v.closeDialogs());
		}
		function pn(e) {
			N.value.has(e) ? N.value.delete(e) : N.value.add(e);
		}
		function mn(e) {
			p.state.items.forEach((t) => e ? N.value.add(String(t.task_id)) : N.value.delete(String(t.task_id)));
		}
		async function hn() {
			w.value = !0, await h.open(p.state.config || void 0), await h.preview();
		}
		async function gn() {
			let e = await h.submit();
			e?.batch_id && ($(), await ln(e.batch_id));
		}
		async function _n() {
			await Q({ force: !0 });
		}
		return o(() => p.load()), b(() => {
			p.destroy(), h.destroy(), v.destroy();
		}), s({
			load: Q,
			setVisible: fn,
			openCreate: hn,
			switchBatch: ln,
			openDetail: v.openDetail,
			showPaymentEntry: Re,
			taskAction: v.taskAction,
			showLink: v.showLink,
			copy: v.copy,
			copyPayment: v.copyPayment,
			bulkAction: p.bulkAction,
			cancelBatch: p.cancelBatch,
			exportRows: p.exportRows,
			closeDialogs: dn
		}), (e, r) => (t(), O("section", {
			class: "extract-page",
			"aria-busy": E(p).state.loading
		}, [
			y("header", Ge, [r[50] ||= y("h1", null, "提链工作台", -1), y("div", Ke, [
				y("button", {
					type: "button",
					onClick: _n
				}, "刷新"),
				y("button", {
					type: "button",
					onClick: r[0] ||= (e) => E(p).exportRows(!0)
				}, "导出当前筛选"),
				E(M).batch ? (t(), O("button", {
					key: 0,
					type: "button",
					disabled: !!E(p).state.cancellingBatch,
					onClick: r[1] ||= (e) => E(p).cancelBatch()
				}, "取消当前批次", 8, qe)) : u("", !0),
				y("button", {
					type: "button",
					class: "primary",
					onClick: hn
				}, "新建批次")
			])]),
			E(p).state.summary ? (t(), O("p", Je, "今日出链 " + _(E(U)(E(p).state.summary.today_extracted)) + " · 待支付 " + _(E(U)(E(p).state.summary.awaiting_payment)) + " · 待核对 " + _(E(U)(E(p).state.summary.needs_review)), 1)) : u("", !0),
			y("div", Ye, [y("div", Xe, [y("span", Ze, "共 " + _(E(U)(E(p).state.total)) + " 条任务", 1), l(ne, {
				items: le.value,
				onRemove: r[2] ||= (e) => H(e, "")
			}, null, 8, ["items"])]), y("div", Qe, [
				l(Ue, {
					column: "batch",
					values: z.value,
					providers: G.value,
					batches: E(p).state.batches,
					counts: E(p).state.counts,
					open: R.value === "batch",
					"onUpdate:open": r[3] ||= (e) => R.value = e ? "batch" : null,
					onChange: H
				}, null, 8, [
					"values",
					"providers",
					"batches",
					"counts",
					"open"
				]),
				y("span", $e, [l(Ue, {
					values: z.value,
					providers: G.value,
					batches: E(p).state.batches,
					counts: E(p).state.counts,
					open: R.value === "all",
					"onUpdate:open": r[4] ||= (e) => R.value = e ? "all" : null,
					onChange: H
				}, null, 8, [
					"values",
					"providers",
					"batches",
					"counts",
					"open"
				])]),
				le.value.length ? (t(), O("button", {
					key: 0,
					type: "button",
					onClick: W
				}, "清筛")) : u("", !0)
			])]),
			E(p).state.batchTotal > 20 ? (t(), O("details", et, [y("summary", null, "批次列表分页 · 共 " + _(E(U)(E(p).state.batchTotal)) + " 个批次", 1), l(te, {
				label: "提链批次分页",
				page: E(p).state.batchPage,
				size: 20,
				"page-sizes": [20],
				total: E(p).state.batchTotal,
				busy: E(p).state.loading,
				"onUpdate:page": ve
			}, null, 8, [
				"page",
				"total",
				"busy"
			])])) : u("", !0),
			E(p).state.error ? (t(), O("p", tt, [k(_(E(p).state.error) + " ", 1), y("button", {
				type: "button",
				onClick: r[5] ||= (e) => E(p).load({ force: !0 })
			}, "重试")])) : u("", !0),
			E(v).state.error ? (t(), O("p", nt, _(E(v).state.error), 1)) : u("", !0),
			N.value.size ? (t(), O("div", rt, [
				y("span", null, "已选 " + _(N.value.size) + " 项", 1),
				y("button", {
					type: "button",
					disabled: E(p).state.bulkBusy,
					onClick: r[6] ||= (e) => E(p).bulkAction("sync_status")
				}, "同步原单", 8, it),
				y("button", {
					type: "button",
					onClick: r[7] ||= (e) => E(p).bulkAction("links")
				}, "复制支付链接"),
				y("button", {
					type: "button",
					onClick: r[8] ||= (e) => E(p).exportRows(!1)
				}, "导出选中"),
				y("button", {
					type: "button",
					onClick: r[9] ||= (e) => E(p).bulkAction("clear")
				}, "清除选择")
			])) : u("", !0),
			y("div", {
				ref_key: "tableScroll",
				ref: I,
				class: "extract-table-wrap"
			}, [y("table", null, [y("thead", null, [y("tr", null, [
				y("th", null, [y("input", {
					type: "checkbox",
					"aria-label": "选择本页提链任务",
					checked: ie.value,
					onChange: r[10] ||= (e) => mn(e.target.checked)
				}, null, 40, at)]),
				(t(), O(m, null, a([
					"query",
					"provider",
					"mode"
				], (e) => y("th", { key: e }, [l(Ue, {
					column: e,
					values: z.value,
					providers: G.value,
					batches: E(p).state.batches,
					counts: E(p).state.counts,
					open: R.value === e,
					"onUpdate:open": (t) => R.value = t ? e : null,
					onChange: H
				}, null, 8, [
					"column",
					"values",
					"providers",
					"batches",
					"counts",
					"open",
					"onUpdate:open"
				])])), 64)),
				r[51] ||= y("th", null, "准备", -1),
				y("th", null, [l(Ue, {
					column: "status",
					values: z.value,
					providers: G.value,
					batches: E(p).state.batches,
					counts: E(p).state.counts,
					open: R.value === "status",
					"onUpdate:open": r[11] ||= (e) => R.value = e ? "status" : null,
					onChange: H
				}, null, 8, [
					"values",
					"providers",
					"batches",
					"counts",
					"open"
				])]),
				r[52] ||= y("th", null, "支付", -1),
				r[53] ||= y("th", null, "Plus", -1),
				r[54] ||= y("th", null, "更新时间", -1),
				r[55] ||= y("th", null, "操作", -1)
			])]), y("tbody", null, [(t(!0), O(m, null, a(E(p).state.items, (e) => (t(), O("tr", { key: String(e.task_id) }, [
				y("td", null, [y("input", {
					type: "checkbox",
					"aria-label": `选择提链任务 ${e.task_id}`,
					checked: N.value.has(String(e.task_id)),
					onChange: (t) => pn(String(e.task_id))
				}, null, 40, ot)]),
				y("td", null, [l(F, {
					text: e.email || "账号未记录",
					secondary: `#${e.task_id}`
				}, null, 8, ["text", "secondary"])]),
				y("td", null, [l(F, {
					text: E(V)(e.provider_id),
					secondary: e.link_type || void 0
				}, null, 8, ["text", "secondary"])]),
				y("td", null, [l(F, {
					text: E(ue)(e.mode),
					secondary: E(ge)(e) || void 0
				}, null, 8, ["text", "secondary"])]),
				y("td", null, [l(F, { text: E(B)(e.preflight_status, "未开始") }, null, 8, ["text"])]),
				y("td", null, [l(re, {
					"data-extract-result": "",
					label: E(ze)(e).label,
					tone: E(ze)(e).tone,
					title: E(K)(e).detail
				}, {
					details: n(() => [
						y("p", null, _(E(K)(e).label), 1),
						y("p", null, _(E(K)(e).detail), 1),
						e.message ? (t(), O("p", st, _(e.message), 1)) : u("", !0),
						e.error ? (t(), O("p", ct, _(e.error), 1)) : u("", !0),
						e.progress?.label ? (t(), O("p", lt, _(e.progress.label), 1)) : u("", !0)
					]),
					_: 2
				}, 1032, [
					"label",
					"tone",
					"title"
				])]),
				y("td", null, [l(F, { text: E(B)(e.payment_phase || e.payment_status, "—") }, null, 8, ["text"])]),
				y("td", null, [l(F, { text: E(B)(e.plus_state || e.plus_status, "未核验") }, null, 8, ["text"])]),
				y("td", null, [l(F, { text: E(fe)(e.updated_at || e.created_at) }, null, 8, ["text"])]),
				y("td", ut, [y("button", {
					type: "button",
					onClick: (t) => E(v).openDetail(e.task_id)
				}, "详情", 8, dt), y("button", {
					type: "button",
					disabled: !(e.has_payment_entry || e.has_payment_link || e.has_qr),
					onClick: (t) => Re(e.task_id)
				}, "支付入口", 8, ft)])
			]))), 128)), !E(p).state.loading && !E(p).state.items.length ? (t(), O("tr", pt, [...r[56] ||= [y("td", {
				colspan: "10",
				class: "empty"
			}, "暂无任务", -1)]])) : u("", !0)])])], 512),
			l(te, {
				label: "提链任务分页",
				page: E(M).page,
				size: E(M).size,
				total: E(p).state.total,
				busy: E(p).state.loading,
				"onUpdate:page": de,
				"onUpdate:size": he
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy"
			]),
			y("dialog", {
				ref_key: "createDialog",
				ref: D,
				class: "extract-dialog",
				"aria-labelledby": "extract-create-title",
				onCancel: x($, ["prevent"]),
				onClose: $,
				onClick: r[32] ||= (e) => un(e, D.value, $)
			}, [
				y("header", null, [r[57] ||= y("h2", { id: "extract-create-title" }, "新建提链批次", -1), y("button", {
					type: "button",
					onClick: $
				}, "关闭")]),
				y("div", mt, [
					y("label", null, [r[58] ||= k("批次名称", -1), i(y("input", { "onUpdate:modelValue": r[12] ||= (e) => E(h).state.title = e }, null, 512), [[T, E(h).state.title]])]),
					y("label", null, [r[59] ||= k("账号搜索", -1), i(y("input", {
						"onUpdate:modelValue": r[13] ||= (e) => E(h).state.filters.query = e,
						onInput: r[14] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, null, 544), [[T, E(h).state.filters.query]])]),
					y("label", null, [r[61] ||= k("来源", -1), i(y("select", {
						"onUpdate:modelValue": r[15] ||= (e) => E(h).state.filters.source = e,
						onChange: r[16] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, [r[60] ||= y("option", { value: "" }, "全部来源", -1), (t(!0), O(m, null, a(E(c).accountSources || {}, (e, n) => (t(), O("option", {
						key: n,
						value: n
					}, _(e), 9, ht))), 128))], 544), [[d, E(h).state.filters.source]])]),
					y("label", null, [r[62] ||= k("注册日期从", -1), i(y("input", {
						"onUpdate:modelValue": r[17] ||= (e) => E(h).state.filters.date_from = e,
						type: "date",
						onChange: r[18] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, null, 544), [[T, E(h).state.filters.date_from]])]),
					y("label", null, [r[63] ||= k("注册日期至", -1), i(y("input", {
						"onUpdate:modelValue": r[19] ||= (e) => E(h).state.filters.date_to = e,
						type: "date",
						onChange: r[20] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, null, 544), [[T, E(h).state.filters.date_to]])]),
					y("label", null, [r[65] ||= k("提链状态", -1), i(y("select", {
						"onUpdate:modelValue": r[21] ||= (e) => E(h).state.filters.extract_status = e,
						onChange: r[22] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, [...r[64] ||= [f("<option value=\"not_succeeded\" data-v-b42215b8>未成功提链</option><option value=\"all\" data-v-b42215b8>全部可用账号</option><option value=\"failed\" data-v-b42215b8>失败</option><option value=\"never\" data-v-b42215b8>从未提链</option><option value=\"success\" data-v-b42215b8>已成功提链</option>", 5)]], 544), [[d, E(h).state.filters.extract_status]])]),
					y("label", null, [r[66] ||= k("套餐优惠", -1), i(y("select", {
						"onUpdate:modelValue": r[23] ||= (e) => E(h).state.filters.promotion = e,
						onChange: r[24] ||= (...e) => E(h).invalidate && E(h).invalidate(...e)
					}, [(t(!0), O(m, null, a(E(se), (e, n) => (t(), O("option", {
						key: n,
						value: n
					}, _(e), 9, gt))), 128))], 544), [[d, E(h).state.filters.promotion]])]),
					y("label", null, [r[67] ||= k("本批运行数量", -1), i(y("input", {
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
					y("label", null, [r[68] ||= k("平台", -1), i(y("select", {
						"onUpdate:modelValue": r[27] ||= (e) => E(h).state.provider = e,
						onChange: Ve
					}, [(t(!0), O(m, null, a(P.value, (e) => (t(), O("option", {
						key: e.id,
						value: e.id
					}, _(e.label || E(V)(e.id)), 9, _t))), 128)), (t(!0), O(m, null, a(E(h).state.config?.unavailable_providers || [], (e) => (t(), O("option", {
						key: e.id,
						value: e.id,
						disabled: ""
					}, _(e.label || E(V)(e.id)) + "（" + _(e.unavailable_reason || "已停用") + "）", 9, vt))), 128))], 544), [[d, E(h).state.provider]])]),
					y("label", null, [r[69] ||= k("模式", -1), i(y("select", { "onUpdate:modelValue": r[28] ||= (e) => E(h).state.mode = e }, [(t(!0), O(m, null, a(E(pe)(J.value), (e) => (t(), O("option", {
						key: e,
						value: e
					}, _(E(ue)(e)), 9, yt))), 128))], 512), [[d, E(h).state.mode]])]),
					y("label", null, [r[70] ||= k("链接类型", -1), i(y("select", { "onUpdate:modelValue": r[29] ||= (e) => E(h).state.type = e }, [(t(!0), O(m, null, a(E(me)(J.value), (e) => (t(), O("option", {
						key: e,
						value: e
					}, _(E(oe)[e] || e), 9, bt))), 128))], 512), [[d, E(h).state.type]])]),
					y("label", null, [r[71] ||= k("并发", -1), i(y("input", {
						"onUpdate:modelValue": r[30] ||= (e) => E(h).state.workers = e,
						type: "number",
						min: "1",
						max: E(h).workersMax(),
						step: "1"
					}, null, 8, xt), [[
						T,
						E(h).state.workers,
						void 0,
						{ number: !0 }
					]])])
				]),
				y("p", St, _(E(Se)(E(h).state.filters.promotion)), 1),
				y("p", Ct, _(E(h).state.feedback), 1),
				E(h).state.error ? (t(), O("p", wt, _(E(h).state.error), 1)) : u("", !0),
				y("footer", null, [
					y("button", {
						type: "button",
						disabled: E(h).state.loading || E(h).state.creating,
						onClick: r[31] ||= (...e) => E(h).preview && E(h).preview(...e)
					}, "刷新匹配数量", 8, Tt),
					y("button", {
						type: "button",
						class: "primary",
						disabled: E(h).state.creating || !E(h).state.preview?.selected_count,
						onClick: gn
					}, "创建并运行（" + _(E(h).state.preview?.selected_count || 0) + "）", 9, Et),
					y("button", {
						type: "button",
						onClick: $
					}, "取消")
				])
			], 544),
			y("dialog", {
				ref_key: "detailDialog",
				ref: A,
				class: "extract-dialog",
				"aria-labelledby": "extract-detail-title",
				onCancel: r[43] ||= x((...e) => E(v).closeDetail && E(v).closeDetail(...e), ["prevent"]),
				onClick: r[44] ||= (e) => un(e, A.value, E(v).closeDetail)
			}, [
				y("header", null, [r[72] ||= y("h2", { id: "extract-detail-title" }, "任务详情", -1), y("button", {
					type: "button",
					onClick: r[33] ||= (...e) => E(v).closeDetail && E(v).closeDetail(...e)
				}, "关闭")]),
				E(v).state.detailLoading ? (t(), O("p", Dt, "正在读取任务详情…")) : u("", !0),
				E(v).state.detailError ? (t(), O("p", Ot, _(E(v).state.detailError), 1)) : u("", !0),
				Y.value ? (t(), O(m, { key: 2 }, [
					y("h3", null, _(Y.value.email || "账号未记录") + " · #" + _(Y.value.task_id), 1),
					y("div", kt, [
						y("button", {
							type: "button",
							disabled: E(_e)(Y.value),
							onClick: r[34] ||= (e) => E(v).taskAction(Y.value.task_id, "sync_status")
						}, "同步状态", 8, At),
						y("button", {
							type: "button",
							disabled: !E(ye)(Y.value),
							onClick: r[35] ||= (e) => E(v).taskAction(Y.value.task_id, "retry")
						}, "重跑", 8, jt),
						Y.value.mode === "auto_payment" && Y.value.payment_status !== "paid" ? (t(), O("button", {
							key: 0,
							type: "button",
							disabled: E(_e)(Y.value),
							onClick: r[36] ||= (e) => E(v).taskAction(Y.value.task_id, "auto_payment")
						}, "查询自动支付", 8, Mt)) : u("", !0),
						y("button", {
							type: "button",
							onClick: r[37] ||= (e) => E(v).copy(Y.value.task_id, "email")
						}, "复制邮箱"),
						Y.value.account_id ? (t(), O("button", {
							key: 1,
							type: "button",
							onClick: r[38] ||= (e) => E(v).copy(Y.value.task_id, "at")
						}, "复制 AT")) : u("", !0),
						Y.value.has_extract_link ? (t(), O("button", {
							key: 2,
							type: "button",
							onClick: r[39] ||= (e) => E(v).showLink(Y.value.task_id, "extract")
						}, "复制提链链接")) : u("", !0),
						Y.value.has_payment_entry || Y.value.has_payment_link || Y.value.has_qr ? (t(), O("button", {
							key: 3,
							type: "button",
							onClick: r[40] ||= (e) => Re(Y.value.task_id)
						}, "读取支付入口")) : u("", !0)
					]),
					y("p", null, _(E(V)(Y.value.provider_id)) + " · " + _(E(ue)(Y.value.mode)) + _(E(ge)(Y.value)), 1),
					y("p", null, _(E(K)(Y.value).label) + " · " + _(E(K)(Y.value).detail), 1),
					y("dl", Nt, [
						y("div", null, [r[73] ||= y("dt", null, "准备", -1), y("dd", null, _(E(B)(Y.value.preflight_status, "未开始")), 1)]),
						y("div", null, [r[74] ||= y("dt", null, "提链", -1), y("dd", null, _(E(B)(Y.value.extraction_status)), 1)]),
						y("div", null, [r[75] ||= y("dt", null, "支付", -1), y("dd", null, _(E(B)(Y.value.payment_status)), 1)]),
						y("div", null, [r[76] ||= y("dt", null, "本地 Plus 到账核验", -1), y("dd", null, _(E(B)(Y.value.plus_status, "未核验")), 1)])
					]),
					Y.value.stages ? (t(), O("section", Pt, [r[77] ||= y("h3", null, "执行阶段", -1), (t(!0), O(m, null, a(Y.value.stages, (e, n) => (t(), O("div", {
						key: n,
						class: "extract-stage"
					}, [
						y("strong", null, _({
							prepare: "准备",
							run: "运行",
							verify: "核验"
						}[n] || n), 1),
						k(" · " + _(E(B)(e?.state || e?.status)) + " ", 1),
						y("span", null, _(e?.step), 1)
					]))), 128))])) : u("", !0),
					Y.value.payment_order ? (t(), O("dl", Ft, [
						y("div", null, [r[78] ||= y("dt", null, "支付订单", -1), y("dd", null, _(Y.value.payment_order.remote_order_id || "等待平台回执"), 1)]),
						y("div", null, [r[79] ||= y("dt", null, "支付提交", -1), y("dd", null, _(Y.value.payment_order.submission_state || "响应缺失"), 1)]),
						y("div", null, [r[80] ||= y("dt", null, "支付状态", -1), y("dd", null, _(E(B)(Y.value.payment_order.payment_state, "支付响应缺失")), 1)])
					])) : u("", !0),
					Y.value.reconcile_halt?.halted ? (t(), O("p", It, _(Y.value.reconcile_halt.label || "已停止自动续查，待核对") + " · " + _(Y.value.reconcile_halt.reason), 1)) : u("", !0),
					y("section", Lt, [r[81] ||= y("h3", null, "节点 A · 出手的东西", -1), E(v).state.nodeA.loading ? (t(), O("p", Rt, "读取支付入口中…")) : E(v).state.nodeA.error ? (t(), O("div", zt, [y("p", null, _(E(v).state.nodeA.error), 1), y("button", {
						type: "button",
						onClick: r[41] ||= (e) => E(v).loadNodeA(Y.value.task_id)
					}, "重新读取节点 A")])) : E(v).state.nodeA.entry ? (t(), O(m, { key: 2 }, [
						y("p", null, "金额 " + _(E(v).state.nodeA.entry.amount ?? "平台未返回") + " " + _(E(v).state.nodeA.entry.currency || "") + " · 有效期 " + _(E(v).state.nodeA.entry.expires_at ? E(fe)(E(v).state.nodeA.entry.expires_at) : "平台未返回"), 1),
						y("div", Bt, [(t(), O(m, null, a(["payment_page_url", "payment_url"], (e) => (t(), O(m, { key: e }, [E(q)(E(v).state.nodeA.entry[e]) ? (t(), O(m, { key: 0 }, [y("a", {
							href: E(q)(E(v).state.nodeA.entry[e]),
							target: "_blank",
							rel: "noopener noreferrer"
						}, "打开" + _(e === "payment_page_url" ? "支付页面" : "支付入口"), 9, Vt), y("button", {
							type: "button",
							onClick: (t) => E(v).copyNodeA(e)
						}, "复制" + _(e === "payment_page_url" ? "支付页面" : "支付入口"), 9, Ht)], 64)) : u("", !0)], 64))), 64)), E(v).state.nodeA.entry.qr_data ? (t(), O("button", {
							key: 0,
							type: "button",
							onClick: r[42] ||= (e) => E(v).copyNodeA("qr_data")
						}, "复制节点 A 二维码")) : u("", !0)]),
						je.value.length && !De.value ? (t(), O("img", {
							key: 0,
							src: je.value[X.value],
							width: "208",
							height: "208",
							alt: "节点 A 支付二维码",
							referrerpolicy: "no-referrer",
							onError: Me
						}, null, 40, Ut)) : De.value ? (t(), O("p", Wt, "二维码图片加载失败，可使用支付链接或二维码原文。")) : u("", !0),
						E(v).state.nodeA.entry.qr_data ? (t(), O("pre", Gt, _(E(v).state.nodeA.entry.qr_data), 1)) : u("", !0)
					], 64)) : (t(), O("p", Kt, "这一步还没有支付入口"))]),
					Y.value.remote_raw ? (t(), O("details", qt, [r[82] ||= y("summary", null, "平台原文", -1), y("pre", null, _(Y.value.remote_raw), 1)])) : u("", !0),
					y("section", null, [
						r[83] ||= y("h3", null, "执行时间线", -1),
						y("ol", Jt, [(t(!0), O(m, null, a(E(v).state.detail?.events || [], (e, n) => (t(), O("li", { key: n }, [
							y("strong", null, _(e.label || e.stage || "事件"), 1),
							k(" · " + _(E(B)(e.status, "")) + " · " + _(E(fe)(e.at || e.created_at || e.time)), 1),
							e.message ? (t(), O("p", Yt, _(e.message), 1)) : u("", !0)
						]))), 128))]),
						E(v).state.detail?.events?.length ? u("", !0) : (t(), O("p", Xt, "暂无阶段事件"))
					]),
					E(v).state.detail?.history?.length ? (t(), O("details", Zt, [y("summary", null, "历史运行 " + _(E(v).state.detail.history.length) + " 次", 1), (t(!0), O(m, null, a(E(v).state.detail.history, (e, n) => (t(), O("article", { key: String(e.run_id || n) }, [
						y("h4", null, "运行 #" + _(e.run_id || n + 1), 1),
						y("p", Qt, _(Be(e)), 1),
						y("pre", null, _(e), 1)
					]))), 128))])) : u("", !0),
					y("details", null, [r[84] ||= y("summary", null, "完整任务记录", -1), y("pre", null, _(Y.value), 1)])
				], 64)) : u("", !0)
			], 544),
			y("dialog", {
				ref_key: "paymentDialog",
				ref: j,
				class: "extract-dialog",
				"aria-labelledby": "extract-payment-title",
				onCancel: r[48] ||= x((...e) => E(v).closePayment && E(v).closePayment(...e), ["prevent"]),
				onClick: r[49] ||= (e) => un(e, j.value, E(v).closePayment)
			}, [y("header", null, [r[85] ||= y("h2", { id: "extract-payment-title" }, "支付入口", -1), y("button", {
				type: "button",
				onClick: r[45] ||= (...e) => E(v).closePayment && E(v).closePayment(...e)
			}, "关闭")]), E(v).state.payment.loading ? (t(), O("p", $t, "读取中…")) : (t(), O(m, { key: 1 }, [E(v).state.payment.error ? (t(), O("div", en, [y("p", null, _(E(v).state.payment.error), 1), y("button", {
				type: "button",
				onClick: r[46] ||= (e) => Re(E(v).state.payment.taskId)
			}, "重新读取")])) : u("", !0), E(v).state.payment.entry ? (t(), O(m, { key: 1 }, [
				y("dl", tn, [
					y("div", null, [r[86] ||= y("dt", null, "金额", -1), y("dd", null, _(E(v).state.payment.entry.amount ?? "平台未返回") + " " + _(E(v).state.payment.entry.currency || ""), 1)]),
					y("div", null, [r[87] ||= y("dt", null, "平台支付状态", -1), y("dd", null, _(E(xe)(E(v).state.payment.entry.payment_status)), 1)]),
					y("div", null, [r[88] ||= y("dt", null, "平台 Plus 核验", -1), y("dd", null, _(E(xe)(E(v).state.payment.entry.platform_plus_status, !0)), 1)]),
					y("div", null, [r[89] ||= y("dt", null, "有效期至", -1), y("dd", null, _(E(v).state.payment.entry.expires_at ? `${E(fe)(E(v).state.payment.entry.expires_at)} · ${E(Ee)(E(v).state.payment.entry.expires_at, Fe.value)}` : "平台未返回"), 1)])
				]),
				r[92] ||= y("p", { class: "extract-hint" }, "平台 Plus 状态供参考，本地到账以任务中的“Plus 到账核验”为准。", -1),
				(t(), O(m, null, a(["payment_page_url", "payment_url"], (e) => y("section", { key: e }, [y("h3", null, _(e === "payment_page_url" ? "支付页面" : "支付入口"), 1), (e === "payment_page_url" ? Ce.value : Te.value) ? (t(), O(m, { key: 0 }, [
					y("a", {
						href: e === "payment_page_url" ? Ce.value : Te.value,
						target: "_blank",
						rel: "noopener noreferrer"
					}, "打开", 8, nn),
					y("button", {
						type: "button",
						onClick: (t) => E(v).copyPayment(e)
					}, "复制", 8, rn),
					y("pre", null, _(e === "payment_page_url" ? Ce.value : Te.value), 1)
				], 64)) : (t(), O("p", an, "平台未返回"))])), 64)),
				y("section", null, [r[90] ||= y("h3", null, "支付二维码", -1), Ie.value.length && !Pe.value ? (t(), O("img", {
					key: 0,
					src: Ie.value[Ne.value],
					width: "208",
					height: "208",
					alt: "平台返回的支付二维码",
					referrerpolicy: "no-referrer",
					onError: Le
				}, null, 40, on)) : (t(), O("p", sn, _(Pe.value ? "二维码图片加载失败。" : "平台未返回二维码图片。") + "可使用支付链接或复制下方二维码原文。", 1))]),
				y("section", null, [r[91] ||= y("h3", null, "二维码原文", -1), E(v).state.payment.entry.qr_data ? (t(), O(m, { key: 0 }, [y("button", {
					type: "button",
					onClick: r[47] ||= (e) => E(v).copyPayment("qr_data")
				}, "复制二维码内容"), y("pre", null, _(E(v).state.payment.entry.qr_data), 1)], 64)) : (t(), O("p", cn, "平台未返回"))])
			], 64)) : u("", !0)], 64))], 544)
		], 8, We));
	}
}), [["__scopeId", "data-v-b42215b8"]]);
// src/features/extract/useExtractStats.ts
function un(e = {}) {
	let t = e.api || R(e), n = s({
		days: 30,
		provider: "",
		data: null,
		scope: "",
		error: "",
		loading: !1,
		visible: e.visible !== !1,
		providers: { ...z }
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
			for (let e of l.providers || []) e.provider_id && (n.providers[e.provider_id] = z[e.provider_id] || e.provider_id);
			e.onReady?.();
		} catch (e) {
			r === i && c() && (n.error = J(e), n.data = l);
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
var $ = ["aria-busy"], dn = { class: "es-heading" }, fn = ["disabled"], pn = { class: "es-controls" }, mn = {
	class: "es-periods",
	role: "group",
	"aria-label": "统计时间范围"
}, hn = [
	"data-extract-stats-days",
	"aria-pressed",
	"onClick"
], gn = ["value"], _n = {
	class: "es-updated",
	role: "status"
}, vn = {
	key: 0,
	class: "es-notice",
	role: "alert"
}, yn = {
	key: 1,
	class: "es-empty",
	role: "status"
}, bn = {
	class: "es-today",
	"aria-label": "今日与当前"
}, xn = { class: "es-scope" }, Sn = { class: "es-metrics" }, Cn = { class: "es-summary-grid" }, wn = { class: "es-panel" }, Tn = { class: "es-conversion" }, En = { class: "es-panel" }, Dn = { class: "es-state-grid" }, On = { class: "es-current" }, kn = { class: "es-chart-grid" }, An = { class: "es-panel es-trend" }, jn = { class: "es-legend" }, Mn = {
	viewBox: "0 0 880 242",
	role: "img",
	"aria-label": "每日提链任务、出链和支付趋势"
}, Nn = ["y1", "y2"], Pn = ["y"], Fn = ["x"], In = ["d"], Ln = {
	key: 1,
	class: "es-empty"
}, Rn = {
	key: 2,
	class: "es-daily-data"
}, zn = { class: "es-table-scroll" }, Bn = { "aria-label": "每日趋势数据" }, Vn = { class: "es-panel" }, Hn = { class: "es-panel-header" }, Un = {
	key: 0,
	class: "es-failures"
}, Wn = {
	class: "es-failure-track",
	"aria-hidden": "true"
}, Gn = {
	key: 1,
	class: "es-empty"
}, Kn = { class: "es-panel" }, qn = {
	key: 0,
	class: "es-table-scroll",
	tabindex: "0",
	"aria-label": "平台统计，可左右滚动"
}, Jn = { class: "es-provider-table" }, Yn = ["title"], Xn = ["title"], Zn = {
	key: 1,
	class: "es-empty"
}, Qn = { class: "es-panel" }, $n = {
	key: 0,
	class: "es-modes"
}, er = {
	class: "es-mode-track",
	"aria-hidden": "true"
}, tr = {
	key: 1,
	class: "es-empty"
}, nr = /*#__PURE__*/ D(/* @__PURE__ */ e({
	__name: "ExtractStats",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let r = un(e.deps || {}), { state: s } = r, c = C(() => s.data), l = C(() => c.value?.totals || {}), f = C(() => c.value?.current || {}), p = C(() => c.value?.daily || []), g = C(() => p.value.at(-1) || {}), v = C(() => Object.entries(s.providers).filter(([e]) => e !== "lumen")), x = C(() => (c.value?.failures || []).filter((e) => H(e.count) > 0).slice().sort((e, t) => H(t.count) - H(e.count))), w = C(() => Math.max(1, ...x.value.map((e) => H(e.count)))), T = [
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
		], D = C(() => p.value.some((e) => H(e.total) > 0)), A = C(() => {
			let e = Math.max(1, ...p.value.flatMap((e) => T.map((t) => H(e[t.key]))));
			return e <= 4 ? 4 : Math.ceil(e / 4) * 4;
		}), j = (e) => 48 + (p.value.length === 1 ? 406 : e * 812 / Math.max(1, p.value.length - 1)), M = (e) => 22 + 184 * (1 - H(e) / A.value), N = C(() => [.../* @__PURE__ */ new Set([
			0,
			...p.value.map((e, t) => t).filter((e) => e % Math.max(1, Math.ceil(p.value.length / 7)) === 0),
			p.value.length - 1
		])].filter((e) => e >= 0)), P = (e) => p.value.map((t, n) => `${n ? "L" : "M"}${j(n).toFixed(2)},${M(t[e]).toFixed(2)}`).join(" "), ee = (e) => H(l.value.total) ? Math.min(100, H(e.total) / H(l.value.total) * 100) : 0;
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
			y("header", dn, [n[4] ||= y("div", null, [y("h1", null, "提链统计"), y("p", null, "按任务创建日统计 · 同一任务仅计一次")], -1), y("button", {
				type: "button",
				"data-extract-stats-refresh": "",
				disabled: E(s).loading,
				onClick: n[0] ||= (...e) => E(r).load && E(r).load(...e)
			}, "刷新", 8, fn)]),
			y("div", pn, [
				y("div", mn, [(t(), O(m, null, a([
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
				}, "近 " + _(e) + " 天", 9, hn)), 64))]),
				y("label", null, [n[6] ||= k("平台", -1), i(y("select", {
					"onUpdate:modelValue": n[1] ||= (e) => E(s).provider = e,
					"data-extract-stats-provider": "",
					onChange: n[2] ||= (...e) => E(r).load && E(r).load(...e)
				}, [n[5] ||= y("option", { value: "" }, "全部平台", -1), (t(!0), O(m, null, a(v.value, ([e, n]) => (t(), O("option", {
					key: e,
					value: e
				}, _(n), 9, gn))), 128))], 544), [[d, E(s).provider]])]),
				y("span", _n, _(E(s).loading ? "正在汇总提链任务…" : c.value?.generated_at ? `更新于 ${E(fe)(c.value.generated_at)}` : ""), 1)
			]),
			E(s).error ? (t(), O("div", vn, [y("span", null, _(E(s).data ? "刷新失败，以下保留上次统计。" : "未取得所选范围的统计。") + _(E(s).error), 1), y("button", {
				type: "button",
				"data-extract-stats-retry": "",
				onClick: n[3] ||= (...e) => E(r).load && E(r).load(...e)
			}, "重试")])) : u("", !0),
			!c.value && E(s).loading ? (t(), O("div", yn, "正在汇总提链任务…")) : u("", !0),
			c.value ? (t(), O(m, { key: 2 }, [
				y("section", bn, [n[11] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "今日与当前"), y("span", null, "今日任务按北京时间创建日归属")], -1), y("dl", null, [
					y("div", null, [n[7] ||= y("dt", null, "今日任务出链", -1), y("dd", null, _(E(U)(g.value.extracted)), 1)]),
					y("div", null, [n[8] ||= y("dt", null, "今日任务 Plus", -1), y("dd", null, _(E(U)(g.value.plus_confirmed)), 1)]),
					y("div", null, [n[9] ||= y("dt", null, [k("当前待支付"), y("small", null, "全部日期")], -1), y("dd", null, _(E(U)(f.value.awaiting_payment)), 1)]),
					y("div", null, [n[10] ||= y("dt", null, [k("当前待核对"), y("small", null, "全部日期")], -1), y("dd", null, _(E(U)(f.value.needs_review)), 1)])
				])]),
				y("div", xn, [y("span", null, _(c.value.date_from || "—") + " — " + _(c.value.date_to || "—"), 1), n[12] ||= y("span", null, "按北京时间任务创建日归属", -1)]),
				y("div", Sn, [(t(), O(m, null, a([
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
					y("strong", null, _(E(U)(l.value[e.key])), 1),
					y("small", null, _(e.hint), 1)
				], 2)), 64))]),
				y("div", Cn, [y("section", wn, [n[19] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "转化与耗时"), y("span", null, "未结束任务不进入成功率分母")], -1), y("dl", Tn, [
					y("div", null, [
						n[13] ||= y("dt", null, "提链成功率", -1),
						y("dd", null, _(E(W)(l.value.extraction_rate)), 1),
						n[14] ||= y("span", null, "已出链 /（已出链 + 提链失败）", -1),
						y("small", null, "出链 " + _(E(U)(l.value.extracted)) + " · 失败 " + _(E(U)(l.value.extraction_failed)), 1)
					]),
					y("div", null, [
						n[15] ||= y("dt", null, "支付成功率", -1),
						y("dd", null, _(E(W)(l.value.payment_rate)), 1),
						n[16] ||= y("span", null, "已支付 /（已支付 + 支付失败）", -1),
						y("small", null, "支付 " + _(E(U)(l.value.paid)) + " · 失败 " + _(E(U)(l.value.payment_failed)), 1)
					]),
					y("div", null, [
						n[17] ||= y("dt", null, "平均耗时", -1),
						y("dd", null, _(E(de)(l.value.avg_seconds)), 1),
						n[18] ||= y("span", null, "最新成功运行的总耗时", -1)
					])
				])]), y("section", En, [
					n[20] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "区间任务状态"), y("span", null, "所选范围的最新结果")], -1),
					y("dl", Dn, [(t(), O(m, null, a([
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
					], (e) => y("div", { key: e.key }, [y("dt", null, _(e.label), 1), y("dd", null, _(E(U)(l.value[e.key])), 1)])), 64))]),
					y("p", On, _(E(s).provider ? "当前所选平台" : "当前全部平台") + "，全部日期：处理中 " + _(E(U)(f.value.processing)) + " · 待支付 " + _(E(U)(f.value.awaiting_payment)) + " · 待核对 " + _(E(U)(f.value.needs_review)), 1)
				])]),
				y("div", kn, [y("section", An, [
					n[25] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "每日趋势"), y("span", null, "按北京时间任务创建日归属")], -1),
					D.value ? (t(), O(m, { key: 0 }, [y("div", jn, [(t(), O(m, null, a(T, (e) => y("span", {
						key: e.key,
						class: S(`es-series--${e.tone}`)
					}, _(e.label), 3)), 64))]), (t(), O("svg", Mn, [
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
						}, null, 8, Nn), y("text", {
							x: "38",
							y: M(A.value * e / 4) + 4,
							"text-anchor": "end",
							class: "es-chart-label"
						}, _(E(U)(A.value * e / 4)), 9, Pn)])), 64)),
						(t(!0), O(m, null, a(N.value, (e) => (t(), O("text", {
							key: e,
							x: j(e),
							y: "232",
							"text-anchor": "middle",
							class: "es-chart-label"
						}, _(String(p.value[e]?.date || "").slice(5)), 9, Fn))), 128)),
						(t(), O(m, null, a(T, (e) => y("path", {
							key: e.key,
							d: P(e.key),
							class: S(["es-chart-line", `es-series--${e.tone}`])
						}, null, 10, In)), 64))
					]))], 64)) : (t(), O("div", Ln, [...n[22] ||= [y("strong", null, "这个时间段还没有提链任务", -1), y("p", null, "选择其他时间范围，或在提链工作台新建批次。", -1)]])),
					p.value.length ? (t(), O("details", Rn, [n[24] ||= y("summary", null, "查看每日明细数据", -1), y("div", zn, [y("table", Bn, [n[23] ||= y("thead", null, [y("tr", null, [
						y("th", null, "日期（北京时间）"),
						y("th", null, "任务总数"),
						y("th", null, "已出链"),
						y("th", null, "已支付"),
						y("th", null, "Plus 已确认")
					])], -1), y("tbody", null, [(t(!0), O(m, null, a(p.value, (e) => (t(), O("tr", { key: e.date }, [
						y("th", null, _(e.date), 1),
						y("td", null, _(E(U)(e.total)), 1),
						y("td", null, _(E(U)(e.extracted)), 1),
						y("td", null, _(E(U)(e.paid)), 1),
						y("td", null, _(E(U)(e.plus_confirmed)), 1)
					]))), 128))])])])])) : u("", !0)
				]), y("section", Vn, [y("div", Hn, [n[26] ||= y("h2", null, "失败分类", -1), y("span", null, _(E(U)(l.value.failed)) + " 个失败任务", 1)]), x.value.length ? (t(), O("ol", Un, [(t(!0), O(m, null, a(x.value, (e) => (t(), O("li", { key: e.code || e.label }, [
					y("div", null, [y("span", null, _(e.label || e.code || "原因未记录"), 1), y("strong", null, _(E(U)(e.count)), 1)]),
					y("div", Wn, [y("span", { style: h({ width: `${E(H)(e.count) / w.value * 100}%` }) }, null, 4)]),
					y("code", null, _(e.code || "未记录错误码"), 1)
				]))), 128))])) : (t(), O("div", Gn, [...n[27] ||= [y("strong", null, "暂无失败记录", -1), y("p", null, "所选范围没有失败任务。", -1)]]))])]),
				y("section", Kn, [n[30] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "平台对比"), y("span", null, "支付成功与 Plus 到账分别统计")], -1), c.value.providers?.length ? (t(), O("div", qn, [y("table", Jn, [n[28] ||= y("thead", null, [y("tr", null, [
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
					y("th", null, _(E(V)(e.provider_id)), 1),
					y("td", null, _(E(U)(e.total)), 1),
					y("td", null, _(E(U)(e.extracted)), 1),
					y("td", { title: `已出链 ${E(U)(e.extracted)}，提链失败 ${E(U)(e.extraction_failed)}` }, _(E(W)(e.extraction_rate)), 9, Yn),
					y("td", null, _(E(U)(e.paid)), 1),
					y("td", { title: `已支付 ${E(U)(e.paid)}，支付失败 ${E(U)(e.payment_failed)}` }, _(E(W)(e.payment_rate)), 9, Xn),
					y("td", null, _(E(U)(e.plus_confirmed)), 1),
					y("td", null, _(E(U)(e.failed)), 1),
					y("td", null, _(E(U)(e.processing)), 1),
					y("td", null, _(E(de)(e.avg_seconds)), 1)
				]))), 128))])])])) : (t(), O("div", Zn, [...n[29] ||= [y("strong", null, "暂无平台数据", -1), y("p", null, "所选范围没有提链任务。", -1)]]))]),
				y("section", Qn, [n[32] ||= y("div", { class: "es-panel-header" }, [y("h2", null, "模式分布"), y("span", null, "所选范围内的任务组成")], -1), c.value.modes?.length ? (t(), O("div", $n, [(t(!0), O(m, null, a(c.value.modes, (e) => (t(), O("article", {
					key: e.mode,
					class: "es-mode"
				}, [
					y("div", null, [y("h3", null, _(E(ue)(e.mode)), 1), y("span", null, _(E(H)(l.value.total) ? E(W)(ee(e) / 100) : "—"), 1)]),
					y("strong", null, [k(_(E(U)(e.total)), 1), n[31] ||= y("small", null, " 个任务", -1)]),
					y("div", er, [y("span", { style: h({ width: `${ee(e)}%` }) }, null, 4)]),
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
					], (t) => y("div", { key: t.key }, [y("dt", null, _(t.label), 1), y("dd", null, _(E(U)(e[t.key])), 1)])), 64))])
				]))), 128))])) : (t(), O("div", tr, "暂无模式数据"))])
			], 64)) : u("", !0)
		], 8, $));
	}
}), [["__scopeId", "data-v-1d114568"]]);
// src/extract.ts
function rr(e, t = {}) {
	let n = w(ln, { deps: t }), r = n.mount(e);
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
function ir(e, t = {}) {
	let n = w(nr, { deps: t }), r = n.mount(e);
	return {
		load: r.load,
		setVisible: r.setVisible,
		destroy: () => n.unmount()
	};
}
export { ir as mountExtractStats, rr as mountExtractWorkbench };
