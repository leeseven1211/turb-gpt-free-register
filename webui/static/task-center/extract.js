import { $ as e, A as t, G as n, I as r, L as i, P as a, S as o, V as s, W as c, Z as l, _ as u, a as d, b as f, c as p, ct as m, dt as h, g, h as _, i as v, j as y, m as b, n as x, ot as S, p as C, s as w, t as T, u as E, ut as D, x as O, y as ee } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { r as k, t as A } from "./client-BBEPwkQG.js";
import { a as j, i as M, r as N } from "./taskIds-BlchWwUp.js";
import { t as P } from "./useNativeDialog-Ba95V1OP.js";
import { t as te } from "./ListPagination-CFFXEHba.js";
import { n as F, r as I, t as ne } from "./ListFilterSummary-NiVwXoAn.js";
import { t as re } from "./ListResult-3o6cJKgT.js";
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
	return e.batch && t.set("batch_id", String(j(e.batch))), t;
}
function R(e = {}) {
	async function t(t, n = {}, r = !1) {
		let i = r && e.statsDataSource || e.dataSource, a = i ? await i(t, n) : await k(t, n, N);
		if (!a || typeof a != "object" || a.ok === !1) throw Error("提链接口响应无效");
		return a;
	}
	let n = (e, n = {}, r) => t(e, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(n),
		signal: r
	}), r = (e) => `${L}/tasks/${encodeURIComponent(j(e))}`;
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
			for (let e of r.items) j(e.batch_id);
			return r;
		},
		async batch(e, n) {
			let r = await t(`${L}/batches/${encodeURIComponent(j(e))}`, { signal: n });
			if (!r.item || String(j(r.item.batch_id)) !== String(j(e))) throw Error("提链批次响应不匹配");
			return r;
		},
		async tasks(e, n) {
			let r = i(await t(`${L}/tasks?${ie(e)}`, { signal: n }));
			for (let e of r.items) j(e.task_id);
			return r;
		},
		async candidates(e, n, r) {
			let i = await t(`${L}/candidates?${new URLSearchParams({
				...e,
				limit: String(n)
			})}`, { signal: r });
			if (!Number.isSafeInteger(i.total) || !Number.isSafeInteger(i.selected_count) || i.total < 0 || i.selected_count < 0 || i.selected_count > Math.min(i.total, n)) throw Error("候选统计响应无效");
			for (let e of i.items || []) j(e.account_id);
			return i;
		},
		create: (e) => n(`${L}/batches`, e),
		cancel: (e) => n(`${L}/batches/${encodeURIComponent(j(e))}/cancel`),
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
		secret: (e) => t(`/api/accounts/${encodeURIComponent(j(e))}/secret?field=access_token`),
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
			if (!n.ok || n.redirected || !/(text\/csv|application\/octet-stream)/i.test(n.headers.get("content-type") || "")) throw new A("导出失败，请重新登录或重试", n.status);
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
	let t = e.api || R(e), n = l({
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
	}), r = !1, i = 0, a = 0, o = 0, s = 0, c = 0, u = 0, d = 0, f = 0, p, m, h, g, _ = /* @__PURE__ */ new Map(), v = /* @__PURE__ */ new Map(), y = /* @__PURE__ */ new Set(), b = () => !r && n.visible && !document.hidden, x = (e) => e === i && b(), S = (t) => e.notify?.(t);
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
		s && (p = setTimeout(() => void M({ quiet: !0 }), s));
	}
	function D(e, r) {
		if (!e && n.config && Date.now() - c < De) return Promise.resolve(n.config);
		if (m) return m.promise;
		let i = ++o, a = C(), s = t.config(a.signal).then((e) => (x(r) && m?.version === i && (n.config = e, n.auxErrors.config = "", c = Date.now(), E(f > 0)), e)).catch((e) => {
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
	function ee(e, r) {
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
	function k(e, n) {
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
	async function A(e, t) {
		D(!!e.force, t).catch(() => {}), O(t).catch(() => {});
		let r = n.batchPage, i = n.query.batch, a = ++s, o = !!e.force || d !== r || Date.now() - u >= De;
		try {
			let c = o ? (await ee(r, t)).items : n.batches;
			if (!x(t) || r !== n.batchPage || i !== n.query.batch || a !== s) return;
			if (!i) {
				n.batchDetail = null;
				return;
			}
			let l = (!e.quiet || o ? c.find((e) => String(e.batch_id) === i) : null) || (await k(i, t)).item;
			x(t) && i === n.query.batch && a === s && (n.batchDetail = l, n.auxErrors.detail = "", E(f > 0));
		} catch (e) {
			x(t) && i === n.query.batch && r === n.batchPage && (n.auxErrors.detail = J(e));
		}
	}
	async function M(r = {}) {
		if (!b()) return;
		w();
		let o = ++a, s = i, c = { ...n.query };
		g?.abort();
		let l = C();
		g = l, n.loading = !0, n.error = "", A(r, s);
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
	async function N(e) {
		Object.assign(n.query, X(), { batch: e ? String(j(e)) : "" }), n.batchDetail = null, n.selected.clear(), s++, await M();
	}
	async function P(r) {
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
				S(`已提交同步：${o} 个${s ? `，失败 ${s} 个` : ""}`), await M({ force: !0 });
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
				n.receipt = a, S(`批次 #${i}：已取消 ${a.cancelled || 0} 个排队任务，跳过 ${a.skipped || 0} 个${a.failed ? `，失败 ${a.failed} 个，可再次处理剩余任务` : ""}。`), await M({ force: !0 });
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
		i++, a++, s++, w(), y.forEach((e) => e.abort()), y.clear(), g = void 0, m = void 0, h = void 0, _.clear(), v.clear(), n.loading = !1;
	}
	function ne(e) {
		n.visible === e ? e && !n.loading && M() : (n.visible = e, e ? M() : I());
	}
	function re() {
		document.hidden ? I() : n.visible && M();
	}
	document.addEventListener("visibilitychange", re);
	function L() {
		r = !0, I(), document.removeEventListener("visibilitychange", re);
	}
	return {
		state: n,
		load: M,
		setVisible: ne,
		switchBatch: N,
		bulkAction: P,
		cancelBatch: te,
		exportRows: F,
		destroy: L
	};
}
// src/features/extract/useExtractBatch.ts
function ke(e = {}, t = async () => {}) {
	let n = e.api || R(e), r = l({
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
	}), i = !1, a = 0, o = 0, c, u = !1, d = null, f = () => JSON.stringify({
		filters: { ...r.filters },
		limit: Number(r.limit)
	});
	function p() {
		a++, c?.abort(), r.preview = null, r.previewSignature = "", r.loading = !1, r.feedback = "筛选条件已变更，请刷新匹配数量。";
	}
	let m = s(() => f(), p, { flush: "sync" });
	function h(e) {
		r.provider = e;
		let t = r.config?.providers.find((t) => t.id === e), n = pe(t), i = me(t);
		r.mode = n.includes(r.mode) ? r.mode : n.includes("extract_only") ? "extract_only" : n.includes("manual_payment") ? "manual_payment" : "", r.type = i.includes(r.type) ? r.type : i.includes(t?.default_type || "") ? t.default_type : i[0] || "";
	}
	async function g(e) {
		r.opened = !0, r.error = "";
		let t = ++o, a = e || await n.config();
		if (!i && t === o && r.opened) {
			if (r.config = a, !u) {
				let e = _(), t = a.batch_workers_default;
				r.workers = Number.isInteger(t) && Number(t) >= 1 && Number(t) <= e ? t : 1, u = !0;
			}
			h(a.providers.some((e) => e.id === r.provider) ? r.provider : a.providers.some((e) => e.id === a.default_provider) ? a.default_provider : a.providers[0]?.id || "");
		}
	}
	function _() {
		let e = r.config?.batch_workers_max;
		return Number.isInteger(e) && Number(e) >= 1 && Number(e) <= 50 ? e : 50;
	}
	async function v() {
		if (i || !r.opened) return;
		c?.abort(), c = new AbortController();
		let e = ++a, t = f(), o = { ...r.filters }, s = Number(r.limit);
		r.preview = null, r.previewSignature = "", r.loading = !0, r.error = "";
		try {
			if (!Number.isInteger(s) || s < 1 || s > 5e3) throw Error("本批运行数量须为 1 至 5000 的整数");
			let l = await n.candidates(o, s, c.signal);
			if (i || e !== a || !r.opened || t !== f()) return;
			if (!Number.isSafeInteger(l.total) || !Number.isSafeInteger(l.selected_count) || l.selected_count < 0 || l.selected_count > s) throw Error("候选统计响应无效");
			r.preview = l, r.previewSignature = t, r.feedback = `匹配 ${l.total.toLocaleString("zh-CN")} 个可用账号，本批计划运行 ${l.selected_count.toLocaleString("zh-CN")} 个。`;
		} catch (t) {
			!i && e === a && r.opened && (r.error = `匹配数量统计失败：${J(t)}`, r.feedback = "请检查筛选条件后重试。");
		} finally {
			e === a && (r.loading = !1);
		}
	}
	async function y() {
		if (!i && !r.creating && r.opened && r.preview?.selected_count && r.previewSignature === f()) {
			r.creating = !0, r.error = "";
			try {
				let a = r.config?.providers.find((e) => e.id === r.provider), o = pe(a), s = me(a), c = Number(r.workers), l = Number(r.limit);
				if (!a || !o.includes(r.mode) || !s.includes(r.type)) throw Error("请选择平台公布的运行模式和提链类型");
				if (!Number.isInteger(c) || c < 1 || c > _()) throw Error(`批次并发请输入 1 到 ${_()} 的整数`);
				let u = {
					workers: c,
					title: r.title.trim(),
					provider_id: r.provider,
					mode: r.mode,
					type: r.type,
					filters: { ...r.filters },
					limit: l
				}, f = JSON.stringify(u);
				if (u.mode === "auto_payment" && !await (e.confirm ? e.confirm(`将为本批约 ${r.preview.selected_count} 个账号启用自动支付任务${ge({
					...a,
					mode: u.mode
				})}，确认继续？`) : window.confirm("确认继续此批自动支付任务？")) || i || !r.opened || f !== JSON.stringify({
					workers: Number(r.workers),
					title: r.title.trim(),
					provider_id: r.provider,
					mode: r.mode,
					type: r.type,
					filters: { ...r.filters },
					limit: Number(r.limit)
				})) return;
				d && d.signature === f || (d = {
					signature: f,
					id: globalThis.crypto.randomUUID()
				}, r.receipt = null), r.submissionSignature = f;
				let p = {
					...u,
					submission_id: d.id
				}, m = await n.create(p), h = {
					...m,
					submission_id: d.id
				};
				r.receipt = h, r.preview = null, r.previewSignature = "", d = null, r.feedback = `已创建批次，入队 ${m.started || 0} 个任务，跳过 ${m.skipped || 0} 个，提交失败 ${m.failed || 0} 个。`, r.error = "";
				try {
					await t();
				} catch {}
				return h;
			} catch (e) {
				r.error = `${J(e)}；可重试获取同一批次的提交结果。`;
			} finally {
				r.creating = !1;
			}
		}
	}
	function b() {
		r.opened = !1, o++, p();
	}
	function x() {
		i = !0, b(), m();
	}
	return {
		state: r,
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
	let n = e.api || R(e), r = l({
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
	}), i = !1, a = 0, o = 0, s = 0, c, u, d, f = (t) => e.notify?.(t);
	async function p(t) {
		if (!t) throw Error("没有可复制内容");
		await (e.copyText ? e.copyText(t) : navigator.clipboard.writeText(t)), f("已复制");
	}
	async function m(e) {
		e = j(e);
		let t = ++a;
		c?.abort(), S(), c = new AbortController(), r.drawer = !0, r.detail = null, r.detailLoading = !0, r.detailError = "";
		try {
			let o = await n.detail(e, c.signal);
			!i && t === a && r.drawer && (r.detail = o, (o.item.has_payment_entry || o.item.has_payment_link || o.item.has_qr) && h(e));
		} catch (e) {
			!i && t === a && (r.detailError = J(e));
		} finally {
			t === a && (r.detailLoading = !1);
		}
	}
	async function h(e) {
		e = j(e);
		let t = ++s;
		d?.abort(), d = new AbortController(), r.nodeA = {
			entry: null,
			taskId: e,
			loading: !0,
			error: ""
		};
		try {
			let a = await n.paymentEntry(e, d.signal);
			if (!a.entry) throw Error("当前任务没有已保存的支付入口");
			!i && r.drawer && t === s && M(r.detail?.item.task_id, e) && (r.nodeA.entry = a.entry);
		} catch (e) {
			!i && r.drawer && t === s && (r.nodeA.error = J(e));
		} finally {
			t === s && (r.nodeA.loading = !1);
		}
	}
	async function g(e) {
		e = j(e);
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
		a = j(a);
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
				let i = M(r.detail?.item.task_id, a) ? r.detail.item : (await n.detail(a)).item;
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
				let r = await n.links(j(e), t), i = q(r.url || r.link);
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
					let t = M(r.detail?.item.task_id, e) ? r.detail : await n.detail(e);
					if (!t.item.account_id) throw Error("任务未记录账号");
					await p((await n.secret(t.item.account_id)).value || "");
				} else if (t === "email") await p((M(r.detail?.item.task_id, e) ? r.detail : await n.detail(e)).item.email || "");
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
		s++, d?.abort(), r.nodeA = {
			entry: null,
			taskId: null,
			loading: !1,
			error: ""
		};
	}
	function C() {
		a++, c?.abort(), S(), r.drawer = !1, r.detail = null, r.detailLoading = !1, r.detailError = "";
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
var je = { class: "extract-filter-fields" }, Me = { key: 0 }, Ne = ["value"], Pe = ["value"], Fe = ["value"], Z = ["value"], Ie = ["value"], Le = ["value"], Re = ["value"], ze = ["value"], Be = ["value"], Ve = ["value"], He = ["value"], Q = { class: "extract-filter-actions" }, Ue = /*#__PURE__*/ T(/* @__PURE__ */ o({
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
	setup(t, { emit: o }) {
		let s = {
			query: "账号",
			provider: "平台",
			mode: "模式",
			status: "提链状态",
			batch: "批次"
		}, l = t, d = o, p = e("query"), m = C(() => l.column || p.value), y = C(() => l.values[m.value]);
		function x(e) {
			d("change", m.value, e);
		}
		return (e, o) => (a(), _(I, {
			label: t.column ? s[t.column] : "提链任务",
			"trigger-label": t.column ? s[t.column] : "筛选",
			active: t.column ? !!t.values[t.column] : Object.values(t.values).some(Boolean),
			summary: y.value,
			open: t.open,
			"onUpdate:open": o[9] ||= (e) => d("update:open", e)
		}, {
			default: c(() => [b("div", je, [
				t.column ? g("", !0) : (a(), u("label", Me, [o[10] ||= f("筛选列", -1), n(b("select", {
					"onUpdate:modelValue": o[0] ||= (e) => p.value = e,
					"aria-label": "选择提链任务筛选列"
				}, [(a(), u(E, null, r(s, (e, t) => b("option", {
					key: t,
					value: t
				}, h(e), 9, Ne)), 64))], 512), [[v, p.value]])])),
				b("label", null, [f(h(s[m.value]) + " ", 1), m.value === "query" ? (a(), u("input", {
					key: 0,
					type: "search",
					value: y.value,
					"aria-label": "筛选账号值",
					placeholder: "邮箱或任务号",
					onChange: o[1] ||= (e) => x(e.target.value),
					onKeydown: o[2] ||= w((e) => d("update:open", !1), ["enter"])
				}, null, 40, Pe)) : m.value === "provider" ? (a(), u("select", {
					key: 1,
					value: y.value,
					"aria-label": "筛选平台值",
					onChange: o[3] ||= (e) => x(e.target.value)
				}, [o[11] ||= b("option", { value: "" }, "全部平台", -1), (a(!0), u(E, null, r(t.providers, (e) => (a(), u("option", {
					key: e.id,
					value: e.id
				}, h(e.label || e.id), 9, Z))), 128))], 40, Fe)) : m.value === "mode" ? (a(), u("select", {
					key: 2,
					value: y.value,
					"aria-label": "筛选模式值",
					onChange: o[4] ||= (e) => x(e.target.value)
				}, [o[12] ||= b("option", { value: "" }, "全部模式", -1), (a(), u(E, null, r([
					"extract_only",
					"manual_payment",
					"auto_payment"
				], (e) => b("option", {
					key: e,
					value: e
				}, h(S(ue)(e)), 9, Le)), 64))], 40, Ie)) : m.value === "status" ? (a(), u("select", {
					key: 3,
					value: y.value,
					"aria-label": "筛选提链状态值",
					onChange: o[5] ||= (e) => x(e.target.value)
				}, [(a(!0), u(E, null, r(S(ce), (e) => (a(), u("option", {
					key: e[0],
					value: e[0]
				}, h(e[1]) + h(t.counts && t.counts[e[0] || "all"] !== void 0 ? ` (${t.counts[e[0] || "all"]})` : ""), 9, ze))), 128))], 40, Re)) : (a(), u("select", {
					key: 4,
					value: y.value,
					"aria-label": "筛选批次值",
					onChange: o[6] ||= (e) => x(e.target.value)
				}, [
					o[13] ||= b("option", { value: "" }, "全部任务", -1),
					y.value && !t.batches.some((e) => String(e.batch_id) === y.value) ? (a(), u("option", {
						key: 0,
						value: y.value
					}, "批次 #" + h(y.value), 9, Ve)) : g("", !0),
					(a(!0), u(E, null, r(t.batches, (e) => (a(), u("option", {
						key: String(e.batch_id),
						value: String(e.batch_id)
					}, h(e.title || `批次 #${e.batch_id}`), 9, He))), 128))
				], 40, Be))]),
				m.value === "batch" ? i(e.$slots, "default", {}, void 0, !0, 1) : g("", !0),
				b("div", Q, [b("button", {
					type: "button",
					onClick: o[7] ||= (e) => x("")
				}, "清除此列"), b("button", {
					type: "button",
					onClick: o[8] ||= (e) => d("update:open", !1)
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
}, tn = { class: "extract-facts" }, nn = ["href"], rn = ["onClick"], an = { key: 1 }, on = ["src"], sn = { key: 1 }, cn = { key: 1 }, ln = /*#__PURE__*/ T(/* @__PURE__ */ o({
	__name: "ExtractWorkbench",
	props: { deps: {} },
	setup(i, { expose: o }) {
		let l = i.deps || {}, m = Oe(l), _ = ke(l, () => m.load({ force: !0 })), x = Ae(l, () => m.load({ force: !0 })), w = e(l.visible !== !1), T = e(!1), D = e(), k = e(), A = e(), j = m.state.query, M = C(() => m.state.selected);
		C(() => Math.max(1, Math.ceil(m.state.total / j.size)));
		let N = C(() => m.state.config?.providers || _.state.config?.providers || []), I = e(), L = 0, ie = C(() => m.state.items.length > 0 && m.state.items.every((e) => M.value.has(String(e.task_id))));
		P(D, () => T.value, () => w.value), P(k, () => !!x.state.drawer, () => w.value), P(A, () => !!x.state.payment.open, () => w.value);
		let R = e(null), z = C(() => ({
			query: j.query,
			provider: j.provider,
			mode: j.mode,
			status: j.status,
			batch: j.batch
		})), ae = {
			query: "账号",
			provider: "平台",
			mode: "模式",
			status: "提链状态",
			batch: "批次"
		}, le = C(() => Object.entries(z.value).filter(([, e]) => e).map(([e, t]) => ({
			key: e,
			label: `${ae[e]}：${e === "provider" ? N.value.find((e) => e.id === t)?.label || V(t) : e === "mode" ? ue(t) : e === "status" ? ce.find((e) => e[0] === t)?.[1] || t : e === "batch" ? m.state.batchDetail?.title || `#${t}` : t}`,
			removeLabel: `清除${ae[e]}筛选`
		})));
		function H(e, t) {
			R.value = null, e === "batch" ? ln(t) : (j[e] = t, j.page = 1, Q());
		}
		function W() {
			Object.assign(j, {
				query: "",
				provider: "",
				mode: "",
				status: "",
				page: 1
			}), ln("");
		}
		function de(e) {
			j.page = e, Q();
		}
		function he(e) {
			j.page = 1, j.size = e, Q();
		}
		function ve(e) {
			m.state.batchPage = e, Q();
		}
		let G = C(() => [...N.value, ...(m.state.config?.unavailable_providers || []).filter((e) => !N.value.some((t) => t.id === e.id)).map((e) => ({
			...e,
			label: `${e.label || V(e.id)}（已停用）`
		}))]), J = C(() => N.value.find((e) => e.id === _.state.provider)), Y = C(() => x.state.detail?.item), Ce = C(() => q(x.state.payment.entry?.payment_page_url)), Te = C(() => q(x.state.payment.entry?.payment_url)), X = e(0), De = e(!1), je = C(() => be(x.state.nodeA.entry || {}));
		s(() => x.state.nodeA.entry, () => {
			X.value = 0, De.value = !1;
		});
		function Me() {
			X.value + 1 < je.value.length ? X.value++ : De.value = !0;
		}
		let Ne = e(0), Pe = e(!1), Fe = e(Date.now()), Z;
		s(() => x.state.payment.open, (e) => {
			Z && clearInterval(Z), Z = void 0, e && (Fe.value = Date.now(), Z = setInterval(() => {
				Fe.value = Date.now();
			}, 1e3));
		}), t(() => {
			Z && clearInterval(Z);
		});
		let Ie = C(() => be(x.state.payment.entry || {}));
		function Le() {
			Ne.value + 1 < Ie.value.length ? Ne.value++ : Pe.value = !0;
		}
		async function Re(e) {
			Ne.value = 0, Pe.value = !1, await x.showPaymentEntry(e);
		}
		let ze = we;
		function Be(e) {
			let t = B(e.status || e.task_status, "状态未记录"), n = e.error_info?.summary || e.error_message || e.error || e.message || "";
			return n ? `${t} · ${n}` : t;
		}
		function Ve() {
			_.setProvider(_.state.provider);
		}
		function He() {
			I.value && (I.value.scrollTop = 0, I.value.scrollLeft = 0);
		}
		async function Q(e = {}) {
			let t = e.quiet ? L : ++L;
			await m.load(e), !e.quiet && t === L && w.value && !m.state.error && He();
		}
		async function ln(e) {
			let t = ++L;
			await m.switchBatch(e), t === L && w.value && !m.state.error && He();
		}
		function un(e, t, n) {
			if (e.target !== t || !t) return;
			let r = t.getBoundingClientRect();
			(e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) && n();
		}
		function $() {
			T.value = !1, _.close();
		}
		function dn() {
			$(), x.closeDialogs();
		}
		function fn(e) {
			w.value = e, m.setVisible(e), e || (R.value = null, $(), x.closeDialogs());
		}
		function pn(e) {
			M.value.has(e) ? M.value.delete(e) : M.value.add(e);
		}
		function mn(e) {
			m.state.items.forEach((t) => e ? M.value.add(String(t.task_id)) : M.value.delete(String(t.task_id)));
		}
		async function hn() {
			T.value = !0, await _.open(m.state.config || void 0), await _.preview();
		}
		async function gn() {
			let e = await _.submit();
			e?.batch_id && ($(), await ln(e.batch_id));
		}
		async function _n() {
			await Q({ force: !0 });
		}
		return y(() => m.load()), t(() => {
			m.destroy(), _.destroy(), x.destroy();
		}), o({
			load: Q,
			setVisible: fn,
			openCreate: hn,
			switchBatch: ln,
			openDetail: x.openDetail,
			showPaymentEntry: Re,
			taskAction: x.taskAction,
			showLink: x.showLink,
			copy: x.copy,
			copyPayment: x.copyPayment,
			bulkAction: m.bulkAction,
			cancelBatch: m.cancelBatch,
			exportRows: m.exportRows,
			closeDialogs: dn
		}), (e, t) => (a(), u("section", {
			class: "extract-page",
			"aria-busy": S(m).state.loading
		}, [
			b("header", Ge, [t[50] ||= b("h1", null, "提链工作台", -1), b("div", Ke, [
				b("button", {
					type: "button",
					onClick: _n
				}, "刷新"),
				b("button", {
					type: "button",
					onClick: t[0] ||= (e) => S(m).exportRows(!0)
				}, "导出当前筛选"),
				S(j).batch ? (a(), u("button", {
					key: 0,
					type: "button",
					disabled: !!S(m).state.cancellingBatch,
					onClick: t[1] ||= (e) => S(m).cancelBatch()
				}, "取消当前批次", 8, qe)) : g("", !0),
				b("button", {
					type: "button",
					class: "primary",
					onClick: hn
				}, "新建批次")
			])]),
			S(m).state.summary ? (a(), u("p", Je, "今日出链 " + h(S(U)(S(m).state.summary.today_extracted)) + " · 待支付 " + h(S(U)(S(m).state.summary.awaiting_payment)) + " · 待核对 " + h(S(U)(S(m).state.summary.needs_review)), 1)) : g("", !0),
			b("div", Ye, [b("div", Xe, [b("span", Ze, "共 " + h(S(U)(S(m).state.total)) + " 条任务", 1), O(ne, {
				items: le.value,
				onRemove: t[2] ||= (e) => H(e, "")
			}, null, 8, ["items"])]), b("div", Qe, [
				O(Ue, {
					column: "batch",
					values: z.value,
					providers: G.value,
					batches: S(m).state.batches,
					counts: S(m).state.counts,
					open: R.value === "batch",
					"onUpdate:open": t[3] ||= (e) => R.value = e ? "batch" : null,
					onChange: H
				}, null, 8, [
					"values",
					"providers",
					"batches",
					"counts",
					"open"
				]),
				b("span", $e, [O(Ue, {
					values: z.value,
					providers: G.value,
					batches: S(m).state.batches,
					counts: S(m).state.counts,
					open: R.value === "all",
					"onUpdate:open": t[4] ||= (e) => R.value = e ? "all" : null,
					onChange: H
				}, null, 8, [
					"values",
					"providers",
					"batches",
					"counts",
					"open"
				])]),
				le.value.length ? (a(), u("button", {
					key: 0,
					type: "button",
					onClick: W
				}, "清筛")) : g("", !0)
			])]),
			S(m).state.batchTotal > 20 ? (a(), u("details", et, [b("summary", null, "批次列表分页 · 共 " + h(S(U)(S(m).state.batchTotal)) + " 个批次", 1), O(te, {
				label: "提链批次分页",
				page: S(m).state.batchPage,
				size: 20,
				"page-sizes": [20],
				total: S(m).state.batchTotal,
				busy: S(m).state.loading,
				"onUpdate:page": ve
			}, null, 8, [
				"page",
				"total",
				"busy"
			])])) : g("", !0),
			S(m).state.error ? (a(), u("p", tt, [f(h(S(m).state.error) + " ", 1), b("button", {
				type: "button",
				onClick: t[5] ||= (e) => S(m).load({ force: !0 })
			}, "重试")])) : g("", !0),
			S(x).state.error ? (a(), u("p", nt, h(S(x).state.error), 1)) : g("", !0),
			M.value.size ? (a(), u("div", rt, [
				b("span", null, "已选 " + h(M.value.size) + " 项", 1),
				b("button", {
					type: "button",
					disabled: S(m).state.bulkBusy,
					onClick: t[6] ||= (e) => S(m).bulkAction("sync_status")
				}, "同步原单", 8, it),
				b("button", {
					type: "button",
					onClick: t[7] ||= (e) => S(m).bulkAction("links")
				}, "复制支付链接"),
				b("button", {
					type: "button",
					onClick: t[8] ||= (e) => S(m).exportRows(!1)
				}, "导出选中"),
				b("button", {
					type: "button",
					onClick: t[9] ||= (e) => S(m).bulkAction("clear")
				}, "清除选择")
			])) : g("", !0),
			b("div", {
				ref_key: "tableScroll",
				ref: I,
				class: "extract-table-wrap"
			}, [b("table", null, [b("thead", null, [b("tr", null, [
				b("th", null, [b("input", {
					type: "checkbox",
					"aria-label": "选择本页提链任务",
					checked: ie.value,
					onChange: t[10] ||= (e) => mn(e.target.checked)
				}, null, 40, at)]),
				(a(), u(E, null, r([
					"query",
					"provider",
					"mode"
				], (e) => b("th", { key: e }, [O(Ue, {
					column: e,
					values: z.value,
					providers: G.value,
					batches: S(m).state.batches,
					counts: S(m).state.counts,
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
				t[51] ||= b("th", null, "准备", -1),
				b("th", null, [O(Ue, {
					column: "status",
					values: z.value,
					providers: G.value,
					batches: S(m).state.batches,
					counts: S(m).state.counts,
					open: R.value === "status",
					"onUpdate:open": t[11] ||= (e) => R.value = e ? "status" : null,
					onChange: H
				}, null, 8, [
					"values",
					"providers",
					"batches",
					"counts",
					"open"
				])]),
				t[52] ||= b("th", null, "支付", -1),
				t[53] ||= b("th", null, "Plus", -1),
				t[54] ||= b("th", null, "更新时间", -1),
				t[55] ||= b("th", null, "操作", -1)
			])]), b("tbody", null, [(a(!0), u(E, null, r(S(m).state.items, (e) => (a(), u("tr", { key: String(e.task_id) }, [
				b("td", null, [b("input", {
					type: "checkbox",
					"aria-label": `选择提链任务 ${e.task_id}`,
					checked: M.value.has(String(e.task_id)),
					onChange: (t) => pn(String(e.task_id))
				}, null, 40, ot)]),
				b("td", null, [O(F, {
					text: e.email || "账号未记录",
					secondary: `#${e.task_id}`
				}, null, 8, ["text", "secondary"])]),
				b("td", null, [O(F, {
					text: S(V)(e.provider_id),
					secondary: e.link_type || void 0
				}, null, 8, ["text", "secondary"])]),
				b("td", null, [O(F, {
					text: S(ue)(e.mode),
					secondary: S(ge)(e) || void 0
				}, null, 8, ["text", "secondary"])]),
				b("td", null, [O(F, { text: S(B)(e.preflight_status, "未开始") }, null, 8, ["text"])]),
				b("td", null, [O(re, {
					"data-extract-result": "",
					label: S(ze)(e).label,
					tone: S(ze)(e).tone,
					title: S(K)(e).detail
				}, {
					details: c(() => [
						b("p", null, h(S(K)(e).label), 1),
						b("p", null, h(S(K)(e).detail), 1),
						e.message ? (a(), u("p", st, h(e.message), 1)) : g("", !0),
						e.error ? (a(), u("p", ct, h(e.error), 1)) : g("", !0),
						e.progress?.label ? (a(), u("p", lt, h(e.progress.label), 1)) : g("", !0)
					]),
					_: 2
				}, 1032, [
					"label",
					"tone",
					"title"
				])]),
				b("td", null, [O(F, { text: S(B)(e.payment_phase || e.payment_status, "—") }, null, 8, ["text"])]),
				b("td", null, [O(F, { text: S(B)(e.plus_state || e.plus_status, "未核验") }, null, 8, ["text"])]),
				b("td", null, [O(F, { text: S(fe)(e.updated_at || e.created_at) }, null, 8, ["text"])]),
				b("td", ut, [b("button", {
					type: "button",
					onClick: (t) => S(x).openDetail(e.task_id)
				}, "详情", 8, dt), b("button", {
					type: "button",
					disabled: !(e.has_payment_entry || e.has_payment_link || e.has_qr),
					onClick: (t) => Re(e.task_id)
				}, "支付入口", 8, ft)])
			]))), 128)), !S(m).state.loading && !S(m).state.items.length ? (a(), u("tr", pt, [...t[56] ||= [b("td", {
				colspan: "10",
				class: "empty"
			}, "暂无任务", -1)]])) : g("", !0)])])], 512),
			O(te, {
				label: "提链任务分页",
				page: S(j).page,
				size: S(j).size,
				total: S(m).state.total,
				busy: S(m).state.loading,
				"onUpdate:page": de,
				"onUpdate:size": he
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy"
			]),
			b("dialog", {
				ref_key: "createDialog",
				ref: D,
				class: "extract-dialog",
				"aria-labelledby": "extract-create-title",
				onCancel: p($, ["prevent"]),
				onClose: $,
				onClick: t[32] ||= (e) => un(e, D.value, $)
			}, [
				b("header", null, [t[57] ||= b("h2", { id: "extract-create-title" }, "新建提链批次", -1), b("button", {
					type: "button",
					onClick: $
				}, "关闭")]),
				b("div", mt, [
					b("label", null, [t[58] ||= f("批次名称", -1), n(b("input", { "onUpdate:modelValue": t[12] ||= (e) => S(_).state.title = e }, null, 512), [[d, S(_).state.title]])]),
					b("label", null, [t[59] ||= f("账号搜索", -1), n(b("input", {
						"onUpdate:modelValue": t[13] ||= (e) => S(_).state.filters.query = e,
						onInput: t[14] ||= (...e) => S(_).invalidate && S(_).invalidate(...e)
					}, null, 544), [[d, S(_).state.filters.query]])]),
					b("label", null, [t[61] ||= f("来源", -1), n(b("select", {
						"onUpdate:modelValue": t[15] ||= (e) => S(_).state.filters.source = e,
						onChange: t[16] ||= (...e) => S(_).invalidate && S(_).invalidate(...e)
					}, [t[60] ||= b("option", { value: "" }, "全部来源", -1), (a(!0), u(E, null, r(S(l).accountSources || {}, (e, t) => (a(), u("option", {
						key: t,
						value: t
					}, h(e), 9, ht))), 128))], 544), [[v, S(_).state.filters.source]])]),
					b("label", null, [t[62] ||= f("注册日期从", -1), n(b("input", {
						"onUpdate:modelValue": t[17] ||= (e) => S(_).state.filters.date_from = e,
						type: "date",
						onChange: t[18] ||= (...e) => S(_).invalidate && S(_).invalidate(...e)
					}, null, 544), [[d, S(_).state.filters.date_from]])]),
					b("label", null, [t[63] ||= f("注册日期至", -1), n(b("input", {
						"onUpdate:modelValue": t[19] ||= (e) => S(_).state.filters.date_to = e,
						type: "date",
						onChange: t[20] ||= (...e) => S(_).invalidate && S(_).invalidate(...e)
					}, null, 544), [[d, S(_).state.filters.date_to]])]),
					b("label", null, [t[65] ||= f("提链状态", -1), n(b("select", {
						"onUpdate:modelValue": t[21] ||= (e) => S(_).state.filters.extract_status = e,
						onChange: t[22] ||= (...e) => S(_).invalidate && S(_).invalidate(...e)
					}, [...t[64] ||= [ee("<option value=\"not_succeeded\" data-v-b42215b8>未成功提链</option><option value=\"all\" data-v-b42215b8>全部可用账号</option><option value=\"failed\" data-v-b42215b8>失败</option><option value=\"never\" data-v-b42215b8>从未提链</option><option value=\"success\" data-v-b42215b8>已成功提链</option>", 5)]], 544), [[v, S(_).state.filters.extract_status]])]),
					b("label", null, [t[66] ||= f("套餐优惠", -1), n(b("select", {
						"onUpdate:modelValue": t[23] ||= (e) => S(_).state.filters.promotion = e,
						onChange: t[24] ||= (...e) => S(_).invalidate && S(_).invalidate(...e)
					}, [(a(!0), u(E, null, r(S(se), (e, t) => (a(), u("option", {
						key: t,
						value: t
					}, h(e), 9, gt))), 128))], 544), [[v, S(_).state.filters.promotion]])]),
					b("label", null, [t[67] ||= f("本批运行数量", -1), n(b("input", {
						"onUpdate:modelValue": t[25] ||= (e) => S(_).state.limit = e,
						type: "number",
						min: "1",
						max: "5000",
						step: "1",
						onInput: t[26] ||= (...e) => S(_).invalidate && S(_).invalidate(...e)
					}, null, 544), [[
						d,
						S(_).state.limit,
						void 0,
						{ number: !0 }
					]])]),
					b("label", null, [t[68] ||= f("平台", -1), n(b("select", {
						"onUpdate:modelValue": t[27] ||= (e) => S(_).state.provider = e,
						onChange: Ve
					}, [(a(!0), u(E, null, r(N.value, (e) => (a(), u("option", {
						key: e.id,
						value: e.id
					}, h(e.label || S(V)(e.id)), 9, _t))), 128)), (a(!0), u(E, null, r(S(_).state.config?.unavailable_providers || [], (e) => (a(), u("option", {
						key: e.id,
						value: e.id,
						disabled: ""
					}, h(e.label || S(V)(e.id)) + "（" + h(e.unavailable_reason || "已停用") + "）", 9, vt))), 128))], 544), [[v, S(_).state.provider]])]),
					b("label", null, [t[69] ||= f("模式", -1), n(b("select", { "onUpdate:modelValue": t[28] ||= (e) => S(_).state.mode = e }, [(a(!0), u(E, null, r(S(pe)(J.value), (e) => (a(), u("option", {
						key: e,
						value: e
					}, h(S(ue)(e)), 9, yt))), 128))], 512), [[v, S(_).state.mode]])]),
					b("label", null, [t[70] ||= f("链接类型", -1), n(b("select", { "onUpdate:modelValue": t[29] ||= (e) => S(_).state.type = e }, [(a(!0), u(E, null, r(S(me)(J.value), (e) => (a(), u("option", {
						key: e,
						value: e
					}, h(S(oe)[e] || e), 9, bt))), 128))], 512), [[v, S(_).state.type]])]),
					b("label", null, [t[71] ||= f("并发", -1), n(b("input", {
						"onUpdate:modelValue": t[30] ||= (e) => S(_).state.workers = e,
						type: "number",
						min: "1",
						max: S(_).workersMax(),
						step: "1"
					}, null, 8, xt), [[
						d,
						S(_).state.workers,
						void 0,
						{ number: !0 }
					]])])
				]),
				b("p", St, h(S(Se)(S(_).state.filters.promotion)), 1),
				b("p", Ct, h(S(_).state.feedback), 1),
				S(_).state.error ? (a(), u("p", wt, h(S(_).state.error), 1)) : g("", !0),
				b("footer", null, [
					b("button", {
						type: "button",
						disabled: S(_).state.loading || S(_).state.creating,
						onClick: t[31] ||= (...e) => S(_).preview && S(_).preview(...e)
					}, "刷新匹配数量", 8, Tt),
					b("button", {
						type: "button",
						class: "primary",
						disabled: S(_).state.creating || !S(_).state.preview?.selected_count,
						onClick: gn
					}, "创建并运行（" + h(S(_).state.preview?.selected_count || 0) + "）", 9, Et),
					b("button", {
						type: "button",
						onClick: $
					}, "取消")
				])
			], 544),
			b("dialog", {
				ref_key: "detailDialog",
				ref: k,
				class: "extract-dialog",
				"aria-labelledby": "extract-detail-title",
				onCancel: t[43] ||= p((...e) => S(x).closeDetail && S(x).closeDetail(...e), ["prevent"]),
				onClick: t[44] ||= (e) => un(e, k.value, S(x).closeDetail)
			}, [
				b("header", null, [t[72] ||= b("h2", { id: "extract-detail-title" }, "任务详情", -1), b("button", {
					type: "button",
					onClick: t[33] ||= (...e) => S(x).closeDetail && S(x).closeDetail(...e)
				}, "关闭")]),
				S(x).state.detailLoading ? (a(), u("p", Dt, "正在读取任务详情…")) : g("", !0),
				S(x).state.detailError ? (a(), u("p", Ot, h(S(x).state.detailError), 1)) : g("", !0),
				Y.value ? (a(), u(E, { key: 2 }, [
					b("h3", null, h(Y.value.email || "账号未记录") + " · #" + h(Y.value.task_id), 1),
					b("div", kt, [
						b("button", {
							type: "button",
							disabled: S(_e)(Y.value),
							onClick: t[34] ||= (e) => S(x).taskAction(Y.value.task_id, "sync_status")
						}, "同步状态", 8, At),
						b("button", {
							type: "button",
							disabled: !S(ye)(Y.value),
							onClick: t[35] ||= (e) => S(x).taskAction(Y.value.task_id, "retry")
						}, "重跑", 8, jt),
						Y.value.mode === "auto_payment" && Y.value.payment_status !== "paid" ? (a(), u("button", {
							key: 0,
							type: "button",
							disabled: S(_e)(Y.value),
							onClick: t[36] ||= (e) => S(x).taskAction(Y.value.task_id, "auto_payment")
						}, "查询自动支付", 8, Mt)) : g("", !0),
						b("button", {
							type: "button",
							onClick: t[37] ||= (e) => S(x).copy(Y.value.task_id, "email")
						}, "复制邮箱"),
						Y.value.account_id ? (a(), u("button", {
							key: 1,
							type: "button",
							onClick: t[38] ||= (e) => S(x).copy(Y.value.task_id, "at")
						}, "复制 AT")) : g("", !0),
						Y.value.has_extract_link ? (a(), u("button", {
							key: 2,
							type: "button",
							onClick: t[39] ||= (e) => S(x).showLink(Y.value.task_id, "extract")
						}, "复制提链链接")) : g("", !0),
						Y.value.has_payment_entry || Y.value.has_payment_link || Y.value.has_qr ? (a(), u("button", {
							key: 3,
							type: "button",
							onClick: t[40] ||= (e) => Re(Y.value.task_id)
						}, "读取支付入口")) : g("", !0)
					]),
					b("p", null, h(S(V)(Y.value.provider_id)) + " · " + h(S(ue)(Y.value.mode)) + h(S(ge)(Y.value)), 1),
					b("p", null, h(S(K)(Y.value).label) + " · " + h(S(K)(Y.value).detail), 1),
					b("dl", Nt, [
						b("div", null, [t[73] ||= b("dt", null, "准备", -1), b("dd", null, h(S(B)(Y.value.preflight_status, "未开始")), 1)]),
						b("div", null, [t[74] ||= b("dt", null, "提链", -1), b("dd", null, h(S(B)(Y.value.extraction_status)), 1)]),
						b("div", null, [t[75] ||= b("dt", null, "支付", -1), b("dd", null, h(S(B)(Y.value.payment_status)), 1)]),
						b("div", null, [t[76] ||= b("dt", null, "本地 Plus 到账核验", -1), b("dd", null, h(S(B)(Y.value.plus_status, "未核验")), 1)])
					]),
					Y.value.stages ? (a(), u("section", Pt, [t[77] ||= b("h3", null, "执行阶段", -1), (a(!0), u(E, null, r(Y.value.stages, (e, t) => (a(), u("div", {
						key: t,
						class: "extract-stage"
					}, [
						b("strong", null, h({
							prepare: "准备",
							run: "运行",
							verify: "核验"
						}[t] || t), 1),
						f(" · " + h(S(B)(e?.state || e?.status)) + " ", 1),
						b("span", null, h(e?.step), 1)
					]))), 128))])) : g("", !0),
					Y.value.payment_order ? (a(), u("dl", Ft, [
						b("div", null, [t[78] ||= b("dt", null, "支付订单", -1), b("dd", null, h(Y.value.payment_order.remote_order_id || "等待平台回执"), 1)]),
						b("div", null, [t[79] ||= b("dt", null, "支付提交", -1), b("dd", null, h(Y.value.payment_order.submission_state || "响应缺失"), 1)]),
						b("div", null, [t[80] ||= b("dt", null, "支付状态", -1), b("dd", null, h(S(B)(Y.value.payment_order.payment_state, "支付响应缺失")), 1)])
					])) : g("", !0),
					Y.value.reconcile_halt?.halted ? (a(), u("p", It, h(Y.value.reconcile_halt.label || "已停止自动续查，待核对") + " · " + h(Y.value.reconcile_halt.reason), 1)) : g("", !0),
					b("section", Lt, [t[81] ||= b("h3", null, "节点 A · 出手的东西", -1), S(x).state.nodeA.loading ? (a(), u("p", Rt, "读取支付入口中…")) : S(x).state.nodeA.error ? (a(), u("div", zt, [b("p", null, h(S(x).state.nodeA.error), 1), b("button", {
						type: "button",
						onClick: t[41] ||= (e) => S(x).loadNodeA(Y.value.task_id)
					}, "重新读取节点 A")])) : S(x).state.nodeA.entry ? (a(), u(E, { key: 2 }, [
						b("p", null, "金额 " + h(S(x).state.nodeA.entry.amount ?? "平台未返回") + " " + h(S(x).state.nodeA.entry.currency || "") + " · 有效期 " + h(S(x).state.nodeA.entry.expires_at ? S(fe)(S(x).state.nodeA.entry.expires_at) : "平台未返回"), 1),
						b("div", Bt, [(a(), u(E, null, r(["payment_page_url", "payment_url"], (e) => (a(), u(E, { key: e }, [S(q)(S(x).state.nodeA.entry[e]) ? (a(), u(E, { key: 0 }, [b("a", {
							href: S(q)(S(x).state.nodeA.entry[e]),
							target: "_blank",
							rel: "noopener noreferrer"
						}, "打开" + h(e === "payment_page_url" ? "支付页面" : "支付入口"), 9, Vt), b("button", {
							type: "button",
							onClick: (t) => S(x).copyNodeA(e)
						}, "复制" + h(e === "payment_page_url" ? "支付页面" : "支付入口"), 9, Ht)], 64)) : g("", !0)], 64))), 64)), S(x).state.nodeA.entry.qr_data ? (a(), u("button", {
							key: 0,
							type: "button",
							onClick: t[42] ||= (e) => S(x).copyNodeA("qr_data")
						}, "复制节点 A 二维码")) : g("", !0)]),
						je.value.length && !De.value ? (a(), u("img", {
							key: 0,
							src: je.value[X.value],
							width: "208",
							height: "208",
							alt: "节点 A 支付二维码",
							referrerpolicy: "no-referrer",
							onError: Me
						}, null, 40, Ut)) : De.value ? (a(), u("p", Wt, "二维码图片加载失败，可使用支付链接或二维码原文。")) : g("", !0),
						S(x).state.nodeA.entry.qr_data ? (a(), u("pre", Gt, h(S(x).state.nodeA.entry.qr_data), 1)) : g("", !0)
					], 64)) : (a(), u("p", Kt, "这一步还没有支付入口"))]),
					Y.value.remote_raw ? (a(), u("details", qt, [t[82] ||= b("summary", null, "平台原文", -1), b("pre", null, h(Y.value.remote_raw), 1)])) : g("", !0),
					b("section", null, [
						t[83] ||= b("h3", null, "执行时间线", -1),
						b("ol", Jt, [(a(!0), u(E, null, r(S(x).state.detail?.events || [], (e, t) => (a(), u("li", { key: t }, [
							b("strong", null, h(e.label || e.stage || "事件"), 1),
							f(" · " + h(S(B)(e.status, "")) + " · " + h(S(fe)(e.at || e.created_at || e.time)), 1),
							e.message ? (a(), u("p", Yt, h(e.message), 1)) : g("", !0)
						]))), 128))]),
						S(x).state.detail?.events?.length ? g("", !0) : (a(), u("p", Xt, "暂无阶段事件"))
					]),
					S(x).state.detail?.history?.length ? (a(), u("details", Zt, [b("summary", null, "历史运行 " + h(S(x).state.detail.history.length) + " 次", 1), (a(!0), u(E, null, r(S(x).state.detail.history, (e, t) => (a(), u("article", { key: String(e.run_id || t) }, [
						b("h4", null, "运行 #" + h(e.run_id || t + 1), 1),
						b("p", Qt, h(Be(e)), 1),
						b("pre", null, h(e), 1)
					]))), 128))])) : g("", !0),
					b("details", null, [t[84] ||= b("summary", null, "完整任务记录", -1), b("pre", null, h(Y.value), 1)])
				], 64)) : g("", !0)
			], 544),
			b("dialog", {
				ref_key: "paymentDialog",
				ref: A,
				class: "extract-dialog",
				"aria-labelledby": "extract-payment-title",
				onCancel: t[48] ||= p((...e) => S(x).closePayment && S(x).closePayment(...e), ["prevent"]),
				onClick: t[49] ||= (e) => un(e, A.value, S(x).closePayment)
			}, [b("header", null, [t[85] ||= b("h2", { id: "extract-payment-title" }, "支付入口", -1), b("button", {
				type: "button",
				onClick: t[45] ||= (...e) => S(x).closePayment && S(x).closePayment(...e)
			}, "关闭")]), S(x).state.payment.loading ? (a(), u("p", $t, "读取中…")) : (a(), u(E, { key: 1 }, [S(x).state.payment.error ? (a(), u("div", en, [b("p", null, h(S(x).state.payment.error), 1), b("button", {
				type: "button",
				onClick: t[46] ||= (e) => Re(S(x).state.payment.taskId)
			}, "重新读取")])) : g("", !0), S(x).state.payment.entry ? (a(), u(E, { key: 1 }, [
				b("dl", tn, [
					b("div", null, [t[86] ||= b("dt", null, "金额", -1), b("dd", null, h(S(x).state.payment.entry.amount ?? "平台未返回") + " " + h(S(x).state.payment.entry.currency || ""), 1)]),
					b("div", null, [t[87] ||= b("dt", null, "平台支付状态", -1), b("dd", null, h(S(xe)(S(x).state.payment.entry.payment_status)), 1)]),
					b("div", null, [t[88] ||= b("dt", null, "平台 Plus 核验", -1), b("dd", null, h(S(xe)(S(x).state.payment.entry.platform_plus_status, !0)), 1)]),
					b("div", null, [t[89] ||= b("dt", null, "有效期至", -1), b("dd", null, h(S(x).state.payment.entry.expires_at ? `${S(fe)(S(x).state.payment.entry.expires_at)} · ${S(Ee)(S(x).state.payment.entry.expires_at, Fe.value)}` : "平台未返回"), 1)])
				]),
				t[92] ||= b("p", { class: "extract-hint" }, "平台 Plus 状态供参考，本地到账以任务中的“Plus 到账核验”为准。", -1),
				(a(), u(E, null, r(["payment_page_url", "payment_url"], (e) => b("section", { key: e }, [b("h3", null, h(e === "payment_page_url" ? "支付页面" : "支付入口"), 1), (e === "payment_page_url" ? Ce.value : Te.value) ? (a(), u(E, { key: 0 }, [
					b("a", {
						href: e === "payment_page_url" ? Ce.value : Te.value,
						target: "_blank",
						rel: "noopener noreferrer"
					}, "打开", 8, nn),
					b("button", {
						type: "button",
						onClick: (t) => S(x).copyPayment(e)
					}, "复制", 8, rn),
					b("pre", null, h(e === "payment_page_url" ? Ce.value : Te.value), 1)
				], 64)) : (a(), u("p", an, "平台未返回"))])), 64)),
				b("section", null, [t[90] ||= b("h3", null, "支付二维码", -1), Ie.value.length && !Pe.value ? (a(), u("img", {
					key: 0,
					src: Ie.value[Ne.value],
					width: "208",
					height: "208",
					alt: "平台返回的支付二维码",
					referrerpolicy: "no-referrer",
					onError: Le
				}, null, 40, on)) : (a(), u("p", sn, h(Pe.value ? "二维码图片加载失败。" : "平台未返回二维码图片。") + "可使用支付链接或复制下方二维码原文。", 1))]),
				b("section", null, [t[91] ||= b("h3", null, "二维码原文", -1), S(x).state.payment.entry.qr_data ? (a(), u(E, { key: 0 }, [b("button", {
					type: "button",
					onClick: t[47] ||= (e) => S(x).copyPayment("qr_data")
				}, "复制二维码内容"), b("pre", null, h(S(x).state.payment.entry.qr_data), 1)], 64)) : (a(), u("p", cn, "平台未返回"))])
			], 64)) : g("", !0)], 64))], 544)
		], 8, We));
	}
}), [["__scopeId", "data-v-b42215b8"]]);
// src/features/extract/useExtractStats.ts
function un(e = {}) {
	let t = e.api || R(e), n = l({
		days: 30,
		provider: "",
		data: null,
		scope: "",
		error: "",
		loading: !1,
		visible: e.visible !== !1,
		providers: { ...z }
	}), r = !1, i = 0, a, o = () => !r && n.visible && !document.hidden;
	async function s() {
		if (!o()) return;
		let r = ++i, s = `${n.days}:${n.provider}`, c = n.scope === s ? n.data : null;
		a?.abort(), a = new AbortController(), n.loading = !0, n.error = "", n.data = c;
		try {
			let c = await t.analytics(n.days, n.provider, a.signal);
			if (r !== i || !o()) return;
			n.data = c, n.scope = s;
			for (let e of c.providers || []) e.provider_id && (n.providers[e.provider_id] = z[e.provider_id] || e.provider_id);
			e.onReady?.();
		} catch (e) {
			r === i && o() && (n.error = J(e), n.data = c);
		} finally {
			r === i && (n.loading = !1);
		}
	}
	function c() {
		i++, a?.abort(), n.loading = !1;
	}
	function u(e) {
		n.visible = e, e ? s() : c();
	}
	function d() {
		document.hidden ? c() : n.visible && s();
	}
	document.addEventListener("visibilitychange", d);
	function f() {
		r = !0, c(), document.removeEventListener("visibilitychange", d);
	}
	return {
		state: n,
		load: s,
		setVisible: u,
		destroy: f
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
}, nr = /*#__PURE__*/ T(/* @__PURE__ */ o({
	__name: "ExtractStats",
	props: { deps: {} },
	setup(e, { expose: i }) {
		let o = un(e.deps || {}), { state: s } = o, c = C(() => s.data), l = C(() => c.value?.totals || {}), d = C(() => c.value?.current || {}), p = C(() => c.value?.daily || []), _ = C(() => p.value.at(-1) || {}), x = C(() => Object.entries(s.providers).filter(([e]) => e !== "lumen")), w = C(() => (c.value?.failures || []).filter((e) => H(e.count) > 0).slice().sort((e, t) => H(t.count) - H(e.count))), T = C(() => Math.max(1, ...w.value.map((e) => H(e.count)))), O = [
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
		], ee = C(() => p.value.some((e) => H(e.total) > 0)), k = C(() => {
			let e = Math.max(1, ...p.value.flatMap((e) => O.map((t) => H(e[t.key]))));
			return e <= 4 ? 4 : Math.ceil(e / 4) * 4;
		}), A = (e) => 48 + (p.value.length === 1 ? 406 : e * 812 / Math.max(1, p.value.length - 1)), j = (e) => 22 + 184 * (1 - H(e) / k.value), M = C(() => [.../* @__PURE__ */ new Set([
			0,
			...p.value.map((e, t) => t).filter((e) => e % Math.max(1, Math.ceil(p.value.length / 7)) === 0),
			p.value.length - 1
		])].filter((e) => e >= 0)), N = (e) => p.value.map((t, n) => `${n ? "L" : "M"}${A(n).toFixed(2)},${j(t[e]).toFixed(2)}`).join(" "), P = (e) => H(l.value.total) ? Math.min(100, H(e.total) / H(l.value.total) * 100) : 0;
		function te(e) {
			o.setVisible(e);
		}
		return y(() => void o.load()), t(o.destroy), i({
			load: o.load,
			setVisible: te
		}), (e, t) => (a(), u("section", {
			class: "extract-stats-page",
			"aria-busy": S(s).loading
		}, [
			b("header", dn, [t[4] ||= b("div", null, [b("h1", null, "提链统计"), b("p", null, "按任务创建日统计 · 同一任务仅计一次")], -1), b("button", {
				type: "button",
				"data-extract-stats-refresh": "",
				disabled: S(s).loading,
				onClick: t[0] ||= (...e) => S(o).load && S(o).load(...e)
			}, "刷新", 8, fn)]),
			b("div", pn, [
				b("div", mn, [(a(), u(E, null, r([
					7,
					30,
					90
				], (e) => b("button", {
					key: e,
					type: "button",
					"data-extract-stats-days": e,
					"aria-pressed": S(s).days === e,
					onClick: (t) => {
						S(s).days = e, S(o).load();
					}
				}, "近 " + h(e) + " 天", 9, hn)), 64))]),
				b("label", null, [t[6] ||= f("平台", -1), n(b("select", {
					"onUpdate:modelValue": t[1] ||= (e) => S(s).provider = e,
					"data-extract-stats-provider": "",
					onChange: t[2] ||= (...e) => S(o).load && S(o).load(...e)
				}, [t[5] ||= b("option", { value: "" }, "全部平台", -1), (a(!0), u(E, null, r(x.value, ([e, t]) => (a(), u("option", {
					key: e,
					value: e
				}, h(t), 9, gn))), 128))], 544), [[v, S(s).provider]])]),
				b("span", _n, h(S(s).loading ? "正在汇总提链任务…" : c.value?.generated_at ? `更新于 ${S(fe)(c.value.generated_at)}` : ""), 1)
			]),
			S(s).error ? (a(), u("div", vn, [b("span", null, h(S(s).data ? "刷新失败，以下保留上次统计。" : "未取得所选范围的统计。") + h(S(s).error), 1), b("button", {
				type: "button",
				"data-extract-stats-retry": "",
				onClick: t[3] ||= (...e) => S(o).load && S(o).load(...e)
			}, "重试")])) : g("", !0),
			!c.value && S(s).loading ? (a(), u("div", yn, "正在汇总提链任务…")) : g("", !0),
			c.value ? (a(), u(E, { key: 2 }, [
				b("section", bn, [t[11] ||= b("div", { class: "es-panel-header" }, [b("h2", null, "今日与当前"), b("span", null, "今日任务按北京时间创建日归属")], -1), b("dl", null, [
					b("div", null, [t[7] ||= b("dt", null, "今日任务出链", -1), b("dd", null, h(S(U)(_.value.extracted)), 1)]),
					b("div", null, [t[8] ||= b("dt", null, "今日任务 Plus", -1), b("dd", null, h(S(U)(_.value.plus_confirmed)), 1)]),
					b("div", null, [t[9] ||= b("dt", null, [f("当前待支付"), b("small", null, "全部日期")], -1), b("dd", null, h(S(U)(d.value.awaiting_payment)), 1)]),
					b("div", null, [t[10] ||= b("dt", null, [f("当前待核对"), b("small", null, "全部日期")], -1), b("dd", null, h(S(U)(d.value.needs_review)), 1)])
				])]),
				b("div", xn, [b("span", null, h(c.value.date_from || "—") + " — " + h(c.value.date_to || "—"), 1), t[12] ||= b("span", null, "按北京时间任务创建日归属", -1)]),
				b("div", Sn, [(a(), u(E, null, r([
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
				], (e) => b("article", {
					key: e.key,
					class: m(["es-metric", `es-metric--${e.key}`])
				}, [
					b("span", null, h(e.label), 1),
					b("strong", null, h(S(U)(l.value[e.key])), 1),
					b("small", null, h(e.hint), 1)
				], 2)), 64))]),
				b("div", Cn, [b("section", wn, [t[19] ||= b("div", { class: "es-panel-header" }, [b("h2", null, "转化与耗时"), b("span", null, "未结束任务不进入成功率分母")], -1), b("dl", Tn, [
					b("div", null, [
						t[13] ||= b("dt", null, "提链成功率", -1),
						b("dd", null, h(S(W)(l.value.extraction_rate)), 1),
						t[14] ||= b("span", null, "已出链 /（已出链 + 提链失败）", -1),
						b("small", null, "出链 " + h(S(U)(l.value.extracted)) + " · 失败 " + h(S(U)(l.value.extraction_failed)), 1)
					]),
					b("div", null, [
						t[15] ||= b("dt", null, "支付成功率", -1),
						b("dd", null, h(S(W)(l.value.payment_rate)), 1),
						t[16] ||= b("span", null, "已支付 /（已支付 + 支付失败）", -1),
						b("small", null, "支付 " + h(S(U)(l.value.paid)) + " · 失败 " + h(S(U)(l.value.payment_failed)), 1)
					]),
					b("div", null, [
						t[17] ||= b("dt", null, "平均耗时", -1),
						b("dd", null, h(S(de)(l.value.avg_seconds)), 1),
						t[18] ||= b("span", null, "最新成功运行的总耗时", -1)
					])
				])]), b("section", En, [
					t[20] ||= b("div", { class: "es-panel-header" }, [b("h2", null, "区间任务状态"), b("span", null, "所选范围的最新结果")], -1),
					b("dl", Dn, [(a(), u(E, null, r([
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
					], (e) => b("div", { key: e.key }, [b("dt", null, h(e.label), 1), b("dd", null, h(S(U)(l.value[e.key])), 1)])), 64))]),
					b("p", On, h(S(s).provider ? "当前所选平台" : "当前全部平台") + "，全部日期：处理中 " + h(S(U)(d.value.processing)) + " · 待支付 " + h(S(U)(d.value.awaiting_payment)) + " · 待核对 " + h(S(U)(d.value.needs_review)), 1)
				])]),
				b("div", kn, [b("section", An, [
					t[25] ||= b("div", { class: "es-panel-header" }, [b("h2", null, "每日趋势"), b("span", null, "按北京时间任务创建日归属")], -1),
					ee.value ? (a(), u(E, { key: 0 }, [b("div", jn, [(a(), u(E, null, r(O, (e) => b("span", {
						key: e.key,
						class: m(`es-series--${e.tone}`)
					}, h(e.label), 3)), 64))]), (a(), u("svg", Mn, [
						t[21] ||= b("title", null, "每日提链趋势，完整数据见下方表格", -1),
						(a(), u(E, null, r([
							0,
							1,
							2,
							3,
							4
						], (e) => b("g", { key: e }, [b("line", {
							x1: "48",
							x2: "860",
							y1: j(k.value * e / 4),
							y2: j(k.value * e / 4),
							class: "es-chart-gridline"
						}, null, 8, Nn), b("text", {
							x: "38",
							y: j(k.value * e / 4) + 4,
							"text-anchor": "end",
							class: "es-chart-label"
						}, h(S(U)(k.value * e / 4)), 9, Pn)])), 64)),
						(a(!0), u(E, null, r(M.value, (e) => (a(), u("text", {
							key: e,
							x: A(e),
							y: "232",
							"text-anchor": "middle",
							class: "es-chart-label"
						}, h(String(p.value[e]?.date || "").slice(5)), 9, Fn))), 128)),
						(a(), u(E, null, r(O, (e) => b("path", {
							key: e.key,
							d: N(e.key),
							class: m(["es-chart-line", `es-series--${e.tone}`])
						}, null, 10, In)), 64))
					]))], 64)) : (a(), u("div", Ln, [...t[22] ||= [b("strong", null, "这个时间段还没有提链任务", -1), b("p", null, "选择其他时间范围，或在提链工作台新建批次。", -1)]])),
					p.value.length ? (a(), u("details", Rn, [t[24] ||= b("summary", null, "查看每日明细数据", -1), b("div", zn, [b("table", Bn, [t[23] ||= b("thead", null, [b("tr", null, [
						b("th", null, "日期（北京时间）"),
						b("th", null, "任务总数"),
						b("th", null, "已出链"),
						b("th", null, "已支付"),
						b("th", null, "Plus 已确认")
					])], -1), b("tbody", null, [(a(!0), u(E, null, r(p.value, (e) => (a(), u("tr", { key: e.date }, [
						b("th", null, h(e.date), 1),
						b("td", null, h(S(U)(e.total)), 1),
						b("td", null, h(S(U)(e.extracted)), 1),
						b("td", null, h(S(U)(e.paid)), 1),
						b("td", null, h(S(U)(e.plus_confirmed)), 1)
					]))), 128))])])])])) : g("", !0)
				]), b("section", Vn, [b("div", Hn, [t[26] ||= b("h2", null, "失败分类", -1), b("span", null, h(S(U)(l.value.failed)) + " 个失败任务", 1)]), w.value.length ? (a(), u("ol", Un, [(a(!0), u(E, null, r(w.value, (e) => (a(), u("li", { key: e.code || e.label }, [
					b("div", null, [b("span", null, h(e.label || e.code || "原因未记录"), 1), b("strong", null, h(S(U)(e.count)), 1)]),
					b("div", Wn, [b("span", { style: D({ width: `${S(H)(e.count) / T.value * 100}%` }) }, null, 4)]),
					b("code", null, h(e.code || "未记录错误码"), 1)
				]))), 128))])) : (a(), u("div", Gn, [...t[27] ||= [b("strong", null, "暂无失败记录", -1), b("p", null, "所选范围没有失败任务。", -1)]]))])]),
				b("section", Kn, [t[30] ||= b("div", { class: "es-panel-header" }, [b("h2", null, "平台对比"), b("span", null, "支付成功与 Plus 到账分别统计")], -1), c.value.providers?.length ? (a(), u("div", qn, [b("table", Jn, [t[28] ||= b("thead", null, [b("tr", null, [
					b("th", null, "平台"),
					b("th", null, "任务数"),
					b("th", null, "已出链"),
					b("th", { title: "已出链 /（已出链 + 提链失败）" }, "提链成功率"),
					b("th", null, "已支付"),
					b("th", { title: "已支付 /（已支付 + 支付失败）" }, "支付成功率"),
					b("th", null, "Plus 已确认"),
					b("th", null, "失败"),
					b("th", null, "处理中"),
					b("th", { title: "最新成功运行的平均总耗时" }, "平均耗时")
				])], -1), b("tbody", null, [(a(!0), u(E, null, r(c.value.providers, (e) => (a(), u("tr", { key: e.provider_id }, [
					b("th", null, h(S(V)(e.provider_id)), 1),
					b("td", null, h(S(U)(e.total)), 1),
					b("td", null, h(S(U)(e.extracted)), 1),
					b("td", { title: `已出链 ${S(U)(e.extracted)}，提链失败 ${S(U)(e.extraction_failed)}` }, h(S(W)(e.extraction_rate)), 9, Yn),
					b("td", null, h(S(U)(e.paid)), 1),
					b("td", { title: `已支付 ${S(U)(e.paid)}，支付失败 ${S(U)(e.payment_failed)}` }, h(S(W)(e.payment_rate)), 9, Xn),
					b("td", null, h(S(U)(e.plus_confirmed)), 1),
					b("td", null, h(S(U)(e.failed)), 1),
					b("td", null, h(S(U)(e.processing)), 1),
					b("td", null, h(S(de)(e.avg_seconds)), 1)
				]))), 128))])])])) : (a(), u("div", Zn, [...t[29] ||= [b("strong", null, "暂无平台数据", -1), b("p", null, "所选范围没有提链任务。", -1)]]))]),
				b("section", Qn, [t[32] ||= b("div", { class: "es-panel-header" }, [b("h2", null, "模式分布"), b("span", null, "所选范围内的任务组成")], -1), c.value.modes?.length ? (a(), u("div", $n, [(a(!0), u(E, null, r(c.value.modes, (e) => (a(), u("article", {
					key: e.mode,
					class: "es-mode"
				}, [
					b("div", null, [b("h3", null, h(S(ue)(e.mode)), 1), b("span", null, h(S(H)(l.value.total) ? S(W)(P(e) / 100) : "—"), 1)]),
					b("strong", null, [f(h(S(U)(e.total)), 1), t[31] ||= b("small", null, " 个任务", -1)]),
					b("div", er, [b("span", { style: D({ width: `${P(e)}%` }) }, null, 4)]),
					b("dl", null, [(a(), u(E, null, r([
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
					], (t) => b("div", { key: t.key }, [b("dt", null, h(t.label), 1), b("dd", null, h(S(U)(e[t.key])), 1)])), 64))])
				]))), 128))])) : (a(), u("div", tr, "暂无模式数据"))])
			], 64)) : g("", !0)
		], 8, $));
	}
}), [["__scopeId", "data-v-1d114568"]]);
// src/extract.ts
function rr(e, t = {}) {
	let n = x(ln, { deps: t }), r = n.mount(e);
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
	let n = x(nr, { deps: t }), r = n.mount(e);
	return {
		load: r.load,
		setVisible: r.setVisible,
		destroy: () => n.unmount()
	};
}
export { ir as mountExtractStats, rr as mountExtractWorkbench };
