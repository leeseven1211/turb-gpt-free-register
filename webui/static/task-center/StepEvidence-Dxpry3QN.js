import { C as e, F as t, L as n, S as r, _ as i, d as a, ft as o, h as s, m as c, st as l, t as u, v as d, x as f, z as p } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { t as m } from "./errorLabels-AzKJgbuj.js";
import { n as h } from "./time-DOD6oyhP.js";
import { t as ee } from "./taskIds-BlchWwUp.js";
// src/features/tasks/presentation.ts
var g = {
	status: {
		queued: "排队中",
		pending: "排队中",
		running: "运行中",
		waiting: "等待中",
		stopping: "停止中",
		cancelling: "停止中",
		settling: "收尾中",
		failed: "失败",
		partial_success: "部分成功",
		password_confirmation_pending: "失败",
		success: "成功",
		stopped: "已停止",
		cancelled: "已取消",
		interrupted: "执行中断",
		debug_paused: "调试暂停",
		deactivated: "已停用",
		unsupported: "不支持",
		attention_required: "失败",
		request_unknown: "失败",
		manual_reconcile: "失败",
		available: "可用",
		used: "已使用",
		pending_sync: "导入处理中",
		tombstone: "本地已删除",
		replaced: "换绑后邮箱",
		disabled: "停用",
		exported: "已导出",
		unexported: "未导出",
		archived: "已归档"
	},
	source: {
		outlook: "Outlook",
		generic_api: "通用 API",
		cloudflare_domain: "域名邮箱",
		cloudflare_temp: "Cloudflare 临时邮箱",
		icloud_hide: "iCloud 隐藏邮箱",
		email_butler: "Email Butler",
		gptmail: "GPTMail",
		mailnest: "MailNest",
		remail: "Remail",
		cloudmail: "CloudMail",
		mailcode: "域名邮箱 MailCode",
		xigua: "西瓜邮箱"
	},
	registration_driver: {
		roxy: "roxy",
		roxy_oss: "roxy-public",
		protocol: "proto-local",
		protocol_oss: "proto-public",
		protocol_oss_2: "proto-sso",
		sentinel_rs: "rust-kernel",
		cloakbrowser: "CloakBrowser（历史）",
		unknown: "未记录"
	},
	token: {
		has: "有 Token",
		none: "无 Token"
	},
	account_token: {
		has: "正常",
		expired: "过期",
		invalid_401: "失效 · 401",
		invalid_403: "失效 · 403",
		invalid_other: "失效 · 其他",
		none: "无 Token"
	},
	password: {
		has: "本地已保存",
		none: "本地未保存"
	},
	totp: {
		enabled: "已启用",
		disabled: "未启用"
	},
	risk: {
		detected: "已收到",
		clear: "未发现",
		pending: "待处理"
	},
	promotion: {
		free_trial: "免费试用",
		half_price: "半价优惠",
		other_discount: "其他折扣",
		discount: "折扣优惠",
		other_promo: "其他优惠",
		none: "无优惠",
		unknown: "历史优惠待复查",
		pending: "待查询",
		failed: "查询失败",
		not_applicable: "不适用"
	},
	codex: {
		success: "已通过",
		retrying: "进行中",
		failed: "失败",
		stopped: "已停止",
		deactivated: "已停用",
		skipped: "已跳过",
		missing: "缺失"
	},
	account_status: {
		active: "未废号",
		deactivated: "已废号",
		unknown: "未查活"
	},
	task_type: {
		registration: "注册",
		registration_resume: "继续邮箱验证",
		twofa_retry: "2FA 配置补跑",
		account_setup_retry: "账号配置补跑",
		password_setup: "补密码",
		twofa_setup: "补 2FA",
		account_completion: "补全账号",
		email_change: "换绑邮箱",
		password_change: "修改密码",
		twofa_change: "修改 2FA",
		codex_retry: "Codex 补跑",
		codex_token_refresh: "Codex Token 刷新",
		sub2api_sync: "sub2api 凭据同步",
		live_check: "查活",
		token_refresh: "AT 刷新",
		plan_check: "查套餐",
		deactivation_mail: "查封号邮件",
		extract_link: "提炼",
		bulk_mutation: "批量数据操作",
		task_terminate_bulk: "批量终止任务"
	},
	trigger: {
		manual: "手动",
		manual_bulk: "手动批量",
		manual_retry: "失败重跑",
		scheduled: "定时",
		registration_auto: "注册后自动",
		registration_job_retry: "注册任务重试",
		token_refresh_scheduled: "AT 定时刷新",
		c2a_monitor: "C2A 异常巡检",
		codex_token_refresh_scheduled: "Codex 定时刷新",
		sub2api_monitor: "sub2api 异常巡检",
		sub2api_sync_retry: "sub2api 自动补传"
	},
	target_status: {
		not_created: "尚未创建",
		in_progress: "处理中",
		email_verification_pending: "待邮箱验证或资料补全",
		account_available: "账号可用",
		credential_valid: "凭证有效",
		credential_pending_confirmation: "凭据核验缺失",
		attention_required: "失败",
		deactivated: "账号已停用",
		account_deactivated: "账号已停用",
		cancelled: "已取消",
		failed: "失败",
		pending: "等待执行",
		request_unknown: "失败",
		manual_reconcile: "失败",
		completed: "已完成",
		unknown: "状态记录缺失"
	},
	stage: {
		queued: "进入队列",
		running: "执行中",
		preflight: "配置预检",
		network: "分配网络",
		network_route: "分配网络",
		driver: "启动浏览器",
		email: "准备邮箱",
		browser: "启动浏览器",
		page: "打开页面",
		submit_email: "提交邮箱",
		auth_redirect: "进入认证",
		email_otp: "邮箱验证",
		profile: "账号资料",
		token: "获取 Token",
		codex: "Codex 授权",
		login_password: "账号密码",
		mfa_challenge: "TOTP 验证",
		account_setup: "账号配置",
		access_token: "校验 Token",
		reauth: "重新登录",
		roxy_fallback: "浏览器回退",
		oauth: "Codex 授权",
		auth_url: "获取授权地址",
		login: "登录 OpenAI",
		phone_check: "检查手机验证",
		phone_acquire: "申请接码号码",
		phone_otp: "短信验证",
		consent: "确认授权",
		callback: "接收 OAuth 回调",
		credential_confirm: "确认远端凭证",
		credential_persist: "保存凭证",
		c2a_safety: "确认 C2A 安全策略",
		c2a_resolve: "定位 C2A 账号",
		c2a_update: "更新 C2A AT",
		cancelling: "正在停止",
		c2a_scan: "读取 C2A 异常账号",
		c2a_repair: "调度 C2A 修复",
		twofa: "设置 2FA",
		plan: "套餐信息",
		plan_check: "查询套餐",
		plan_request: "请求套餐",
		refresh_token: "刷新 Token",
		mailbox_scan: "扫描邮件",
		extract_link: "提炼",
		extraction: "平台提链",
		remote_sync: "原单状态查询",
		payment: "支付处理",
		login_mfa: "TOTP 验证",
		complete: "完成",
		interrupted: "执行中断",
		event: "事件"
	},
	run_count: {
		0: "0 次",
		1: "1 次",
		2: "2 次",
		3: "3 次",
		"4+": "4 次及以上"
	}
};
Object.assign(g.task_type, {
	account_inspection: "账号巡检",
	account_inspection_batch: "巡检批次",
	sub2api_manual_upload: "Sub2API 手动上传",
	sub2api_scan: "Sub2API 异常扫描",
	c2a_session_reimport: "C2A 重新导入",
	c2a_scan: "C2A 异常巡检"
});
function _(e, t) {
	let n = String(t || "");
	return g[e]?.[n] || n || "—";
}
function v(e) {
	if (e == null || !Number.isFinite(Number(e))) return "—";
	let t = Math.max(0, Number(e));
	if (t < 1e3) return `${Math.round(t)} 毫秒`;
	if (t < 6e4) return `${(t / 1e3).toFixed(1)} 秒`;
	let n = Math.floor(t / 1e3);
	return n < 3600 ? `${Math.floor(n / 60)} 分 ${n % 60} 秒` : `${Math.floor(n / 3600)} 小时 ${Math.floor(n % 3600 / 60)} 分`;
}
function y(e, t = "") {
	let n = String(e?.summary || t || "错误原因未记录"), r = String(e?.cause_summary || "").trim();
	return r && !n.includes(r) ? `${n} · ${r}` : n;
}
function b(e) {
	return [
		"queued",
		"running",
		"stopping",
		"cancelling",
		"settling",
		"waiting"
	].includes(String(e.status));
}
function x(e) {
	let t = T(e.result_summary), n = e.status === "deactivated" || ["deactivated", "account_deactivated"].includes(String(e.target_status)) || ["status", "requested_status"].some((e) => t[e] === "deactivated");
	return !b(e) && !n && !!e.next_actions?.length;
}
function S(e) {
	return e.source_system === "native_operations" && b(e) && e.status !== "queued";
}
function te(e) {
	return e.source_system === "native_operations" && (e.status === "queued" || S(e));
}
function C(e, t) {
	return t === "retry" ? x(e) : t === "cancel" ? e.status === "queued" : t === "delete" ? !b(e) : S(e);
}
function w(e) {
	let t = String(e);
	return [
		"success",
		"completed",
		"account_available",
		"credential_valid"
	].includes(t) ? "success" : [
		"failed",
		"attention_required",
		"request_unknown",
		"manual_reconcile",
		"deactivated",
		"account_deactivated"
	].includes(t) ? "danger" : ["running", "in_progress"].includes(t) ? "active" : [
		"queued",
		"waiting",
		"partial_success",
		"stopping",
		"cancelling",
		"settling"
	].includes(t) ? "warning" : "neutral";
}
function T(e) {
	return e && typeof e == "object" && !Array.isArray(e) ? e : {};
}
var E = (e) => Array.isArray(e) ? e.map(T) : [];
function D(e) {
	let t = e.admission_wait_reasons?.length ? e.admission_wait_reasons : e.admission_wait_reason ? [{ code: e.admission_wait_reason }] : [], n = {
		executor_capacity: "等待执行承载空位",
		resource_capacity: "等待业务资源空位",
		global_capacity: "等待全局空位",
		type_capacity: "等待本类空位",
		batch_paused: "等待批次继续",
		batch_capacity: "等待当前批次空位",
		provider_capacity: "等待平台空位",
		account_busy: "账号正由其他任务使用",
		remote_order_capacity: "等待远端订单名额",
		not_due: "等待下次平台查询",
		execution_active: "上一执行仍在退出或清理",
		fairness_turn: "等待公平调度轮次",
		concurrency_policy_migration_required: "等待配置并发迁移策略",
		scheduler_store_unavailable: "调度存储暂不可用",
		permit_owner_lost: "执行许可归属已变化"
	};
	return t.map((e) => {
		let t = n[String(e.code)], r = T(e).occupied, i = T(e).limit;
		return t ? t + (r != null && i != null ? `（${r}/${i}）` : "") : `调度等待原因未登记（${e.code || "缺少原因代码"}）`;
	}).join("；");
}
function O(e) {
	let t = String(e.plus_promo_kind || "").toLowerCase();
	if ([
		"free_trial",
		"discount",
		"other_promo",
		"none",
		"unknown"
	].includes(t)) return t;
	let n = Number(e.plus_promo_discount_percentage ?? e.plus_trial_discount_percentage), r = String(e.plus_promo_campaign_id || e.plus_trial_campaign_id || "").toLowerCase(), i = [
		r,
		e.plus_promo_title || e.plus_trial_title,
		e.plus_promo_promotion_type,
		e.plus_promo_promotion_type_label || e.plus_trial_promotion_type_label
	].join(" ").toLowerCase();
	return n === 100 ? "free_trial" : n > 0 && n < 100 || /pct-off|discount|% off/.test(i) ? "discount" : i.includes("free trial") || r.includes("-free") || r.includes("trial") ? "free_trial" : i.trim() ? "other_promo" : e.plus_discount_eligible === !0 ? "discount" : e.plus_promo_eligible === !0 || e.plus_trial_eligible === !0 ? "unknown" : "none";
}
function k(e) {
	return {
		go: "Go",
		plus: "Plus",
		team: "Team（Business）"
	}[String(e)] || "Plus";
}
function A(e) {
	if (Array.isArray(e.account_promotions)) return [
		"go",
		"plus",
		"team"
	].flatMap((t) => {
		let n = E(e.account_promotions).filter((e) => String(e.plan).toLowerCase() === t);
		return n.length ? n.map((e) => ({
			...e,
			plan: t
		})) : t === "team" ? [] : [{
			plan: t,
			kind: "unknown"
		}];
	});
	let t = String(e.current_plan_type || e.plan_type || "").toLowerCase();
	return [{
		plan: "go",
		kind: "pending"
	}, {
		plan: "plus",
		kind: t && t !== "free" ? "not_applicable" : O(e),
		discount_percentage: e.plus_promo_discount_percentage ?? e.plus_trial_discount_percentage,
		duration_num_periods: e.plus_promo_duration_num_periods ?? e.plus_trial_duration_num_periods,
		duration_period: e.plus_promo_duration_period || e.plus_trial_duration_period
	}];
}
function j(e) {
	let t = {
		month: "个月",
		year: "年",
		week: "周",
		day: "天"
	}, n = Number(e.duration_num_periods), r = t[String(e.duration_period)], i = n > 0 && r ? ` ${n}${r}` : "";
	if (e.kind === "free_trial") return `${e.plan === "team" ? "免费试用" : "免费"}${i}`;
	if (e.kind === "discount") {
		let t = Number(e.discount_percentage);
		return `${t === 50 ? "五折" : t > 0 && t < 100 ? `减 ${t}%` : "折扣"}${i}`;
	}
	return {
		other_promo: "其他优惠",
		none: "无优惠",
		unknown: "待复查",
		pending: "待查询",
		failed: "查询失败",
		cancelled: "已取消",
		not_applicable: "不适用"
	}[String(e.kind)] || "待复查";
}
function ne(e) {
	let t = {
		free_trial: 0,
		discount: 1,
		other_promo: 2,
		unknown: 3,
		pending: 4,
		failed: 5,
		cancelled: 5,
		none: 6,
		not_applicable: 7
	}, n = (e) => Number(e.duration_num_periods || 0) * ({
		day: 1,
		week: 7,
		month: 30,
		year: 365
	}[String(e.duration_period)] || 0);
	return [...e].sort((e, r) => (t[String(e.kind)] ?? 3) - (t[String(r.kind)] ?? 3) || (e.kind === "discount" ? Number(r.discount_percentage || 0) - Number(e.discount_percentage || 0) : 0) || (["free_trial", "discount"].includes(String(e.kind)) ? n(r) - n(e) : 0) || Number(r.plan === "plus") - Number(e.plan === "plus") || Number(!!e.stale) - Number(!!r.stale))[0] || { kind: "pending" };
}
function M(e, t) {
	return t ? ((e) => `${[
		"free_trial",
		"discount",
		"other_promo"
	].includes(String(e.kind)) ? `${k(e.plan)} ` : ""}${j(e)}${e.stale ? " · 历史" : ""}`)(ne(e)) : e.map((e) => `${k(e.plan)}: ${j(e)}${e.stale ? "（历史）" : ""}`).join("；");
}
function N(e) {
	if (Array.isArray(e.plan_check_countries) && !e.plan_check_countries.length) return [];
	let t = /* @__PURE__ */ new Map();
	for (let n of E(e.account_promotions)) {
		let e = String(n.country || "").trim().toUpperCase();
		e && (t.has(e) || t.set(e, []), t.get(e).push({
			...n,
			country: e
		}));
	}
	return [...t].map(([e, t]) => ({
		country: e,
		items: A({ account_promotions: t })
	}));
}
function P(e, t, n = !1) {
	let r = e.current_plan_type ? `${n ? "" : "套餐 "}${e.current_plan_type} · ` : "", i = Array.isArray(e.plan_check_countries) && !e.plan_check_countries.length, a = i ? [] : E(e.plan_check_country_results).filter((e) => e.country);
	if (a.length) {
		let e = a.filter((e) => e.status === "success").length, i = a.filter((e) => ["failed", "cancelled"].includes(String(e.status))).length, o = a.some((e) => ["queued", "running"].includes(String(e.status))) || ["queued", "running"].includes(t), s = i === a.length ? "全部失败" : ["failed", "cancelled"].includes(t) && o ? t === "cancelled" ? "已取消" : "查询中断" : i && e ? "部分失败" : o ? "查询中" : "", c = a.map((e) => {
			let n = T(e.result), r = !!Object.keys(n).length && !!e.last_success_at, i = ["queued", "running"].includes(String(e.status)), a = ["failed", "cancelled"].includes(t), o = e.status === "success" ? A(n).map((e) => ({
				...e,
				stale: ["queued", "running"].includes(t)
			})) : i && !a ? [{ kind: "pending" }] : r ? A(n).map((e) => ({
				...e,
				stale: !0
			})) : [{ kind: e.status === "cancelled" || t === "cancelled" ? "cancelled" : "failed" }];
			return {
				country: String(e.country).toUpperCase(),
				items: o
			};
		});
		return r + [s, n ? M(c.flatMap((e) => e.items), !0) : c.map((e) => `${e.country} ${M(e.items, !0)}`).join(" · ")].filter(Boolean).join(" · ");
	}
	let o = Number(e.country_total_count || (Array.isArray(e.plan_check_countries) ? e.plan_check_countries.length : 0));
	if (!i && o > 0) {
		let i = Array.isArray(e.failed_countries) ? e.failed_countries.map((e) => String(typeof e == "object" ? T(e).country || "" : e || "").trim().toUpperCase()).filter(Boolean) : [], a = Number(e.country_success_count || 0), s = i.length >= o && !a ? "全部失败" : i.length && a ? "部分失败" : ["queued", "running"].includes(t) ? "查询中" : "", c = N(e), l = c.length ? n ? M(c.flatMap((e) => e.items), !0) : c.map((e) => `${e.country} ${M(e.items, !0)}`).join(" · ") : Array.isArray(e.account_promotions) ? M(A(e), n) : "", u = [
			s,
			!n && i.length ? `失败国家：${i.join("、")}` : "",
			l
		].filter(Boolean).join(" · ");
		if (u) return r + u;
	}
	if (!Array.isArray(e.account_promotions)) {
		let t = String(e.current_plan_type || "");
		return t ? t.toLowerCase() === "free" ? `${r}Plus ${j(A(e)[1])}` : `${n ? "" : "套餐 "}${t}` : "查询完成";
	}
	return r + M(A(e), n);
}
function F(e, t = !1) {
	let n = String(e.status || "");
	if (n === "queued") return D(e) ? D(e) : "等待执行";
	if (n === "running") return "执行中";
	let r = T(e.result_summary);
	if (e.task_type === "extract_link") {
		let t = String(r.extraction_status || "").toLowerCase(), i = String(r.payment_status || "").toLowerCase();
		if (["succeeded", "success"].includes(t) || !t && r.ok === !0 && r.has_link === !0) {
			let e = `提链成功${r.link_type ? ` · ${String(r.link_type).toUpperCase()}` : ""}`;
			return ["failed", "error"].includes(i) ? `${e} · 支付失败` : [
				"succeeded",
				"success",
				"paid"
			].includes(i) ? `${e} · 支付成功` : [
				"unknown",
				"request_unknown",
				"attention_required"
			].includes(i) ? `${e} · 支付响应缺失` : [
				"pending",
				"pending_payment",
				"processing"
			].includes(i) ? `${e} · ${r.mode === "manual_payment" ? "等待手动支付" : "支付处理中"}` : r.mode === "manual_payment" && i === "not_started" ? `${e} · 等待手动支付` : [
				"request_unknown",
				"attention_required",
				"partial_success"
			].includes(n) ? `${e} · 后续处理失败` : [
				"cancelled",
				"stopped",
				"interrupted"
			].includes(n) ? `${e} · 任务已中断` : n === "failed" ? `${e} · 后续处理失败` : e;
		}
		return ["failed", "error"].includes(t) ? "提链失败" : [
			"unknown",
			"request_unknown",
			"attention_required"
		].includes(t) ? e.error_info?.summary || "提链失败 · 平台响应记录缺失" : ["pending", "queued"].includes(t) ? "等待提链" : t === "running" ? "提链中" : n === "cancelled" ? "任务已取消" : ["stopped", "interrupted"].includes(n) ? "任务已中断" : [
			"request_unknown",
			"attention_required",
			"partial_success",
			"unknown"
		].includes(n) ? e.error_info?.summary || "提链失败 · 平台响应记录缺失" : e.error_message ? y(e.error_info, e.error_message) : Object.prototype.hasOwnProperty.call(r, "ok") ? r.message || r.status || (r.ok ? "提炼完成" : "提炼失败") : r.message || (n === "failed" ? "提链失败" : "提链结果未记录");
	}
	if (e.error_message) return y(e.error_info, e.error_message);
	if (e.task_type === "registration" || e.task_type === "registration_resume") return _("target_status", e.target_status) || "注册执行已结束";
	if (e.task_type === "plan_check") return P(r, n, t);
	if (e.task_type === "deactivation_mail") return Object.prototype.hasOwnProperty.call(r, "detected") ? r.detected ? "发现封号邮件" : "未发现封号邮件" : "-";
	if (e.task_type === "live_check" || e.task_type === "token_refresh") return r.ok ? "账号正常" : e.task_type === "token_refresh" ? "AT 刷新失败" : "查活失败";
	if (e.task_type === "email_change") return r.email_change_confirmed ? T(r.post_change_live_check).accepted ? "邮箱已换绑 · AT 刷新已排队" : "邮箱已换绑 · AT 刷新待处理" : r.message || r.status || "邮箱换绑未完成";
	if ([
		"account_setup_retry",
		"password_setup",
		"password_change",
		"twofa_setup",
		"twofa_change",
		"account_completion"
	].includes(e.task_type)) return r.ok ? r.message || "账号配置操作已完成" : r.message || "账号配置操作失败";
	if (e.task_type === "codex_retry") {
		if (r.ok) {
			let e = T(r.sub2api_sync).status;
			return e === "success" ? "授权成功 · sub2api 已启用" : e === "failed" ? "授权成功 · sub2api 同步失败" : e === "cancelled" ? "授权成功 · sub2api 同步已停止" : r.credential_confirmed ? "授权成功 · 凭证已确认" : "授权成功";
		}
		return ["attention_required", "request_unknown"].includes(String(r.status)) ? "授权失败 · 未取得有效凭据" : r.message || r.status || "补跑失败";
	}
	if (e.task_type === "codex_token_refresh") return r.ok ? r.sub2_sync === "failed" ? "Token 已刷新 · sub2 同步失败" : "OAuth Token 已刷新" : "OAuth Token 刷新失败";
	if (e.task_type === "c2a_session_reimport") return r.ok ? r.message || "C2A AT 已从本地重新导入" : r.error_code || r.message || "C2A 重新导入失败，请查看任务日志";
	if (e.task_type === "sub2api_manual_upload") return r.ok ? "手动上传 Sub2API 已完成" : r.error_code || r.message || "手动上传失败，请查看任务日志";
	if (e.task_type === "c2a_scan") {
		if (n !== "success") return y(e.error_info, r.error_code || r.message || "C2A 异常扫描未完成，请查看任务日志");
		let t = r.continuation_only ? ["C2A 修复接续检查已完成"] : ["C2A 异常扫描已完成", `异常 ${r.remote_errors ?? 0} 条`];
		t.push(`刷新入队 ${r.refresh_queued ?? 0}`, `同步入队 ${r.sync_queued ?? 0}`);
		let i = (Array.isArray(r.reasons) ? E(r.reasons) : Object.entries(T(r.reasons)).map(([e, t]) => ({
			code: e,
			count: t
		}))).flatMap(({ code: e, count: t }) => {
			if (typeof e != "string" || !/^[a-z0-9_.-]{1,100}$/i.test(e) || !Number.isSafeInteger(t) || Number(t) <= 0) return [];
			let n = m({ cause_code: e });
			return [`${n === m() ? e : n} ${t}`];
		});
		return i.length && t.push(i.join("、")), t.join(" · ");
	}
	return e.task_type === "sub2api_scan" ? n === "success" ? "Sub2API 异常扫描已完成" : r.error_code || r.message || "扫描未完成，请查看任务日志" : Object.keys(r).length ? JSON.stringify(r) : "-";
}
function I(e, t = !1) {
	return String(F(e, t));
}
function re(e) {
	if (b(e)) return "";
	let t = T(e.result_summary), n = T(t.auth_diagnostics), r = String(e.failure_stage || t.failure_stage || ""), i = n.operation === "password_email_fallback" ? n.cause_operation : n.operation, a = ["token_refresh", "live_check"].includes(e.task_type) && e.status !== "success" && ["login_password", "email_otp"].includes(r) && ["mfa_verify", "mfa_issue_challenge"].includes(String(i)), o = e.error_info?.stage, s = a ? "mfa_challenge" : o && ![
		"unknown",
		"complete",
		"result",
		"event",
		"queued"
	].includes(o) ? o : r;
	return s ? `失败于 ${s === r && e.failure_stage_label ? e.failure_stage_label : _("stage", s.replace(/_result$/, ""))}` : "";
}
function L(e) {
	let t = [`${k(e.plan)}: ${j(e)}`];
	if (![
		"free_trial",
		"discount",
		"other_promo"
	].includes(String(e.kind))) return t.join("；");
	let n = String(e.checkout_status || ""), r = String(e.country || "").toUpperCase(), i = String(e.checkout_country || "").toUpperCase();
	if (r && i && r !== i) return `${t[0]}；支付方式: 待查询`;
	if (["failed", "skipped"].includes(n)) {
		let r = String(e.checkout_error || "").replace(/https?:\/\/[^\s；，]+/gi, "[链接已隐藏]").replace(/\b(?:cs_(?:live|test)|oaics|(?:pk|sk)_(?:live|test))_[a-z0-9_-]+\b/gi, "[结账标识已隐藏]").replace(/\b[^\s；，]*secret[^\s；，]*\b/gi, "[凭据已隐藏]").slice(0, 240).trim(), i = Number(e.checkout_http_status);
		return t.push(n === "failed" ? "支付方式查询失败" : "支付方式待查询"), (r || i >= 100 && i <= 599) && t.push(r || `HTTP ${i}`), t.join("；");
	}
	let a = Array.isArray(e.payment_method_types) ? e.payment_method_types : [], o = {
		card: "银行卡",
		link: "Link",
		upi: "UPI"
	}, s = [...new Set(a.filter((e) => typeof e == "string").map((e) => e.trim().toLowerCase()).filter((e) => /^[a-z][a-z0-9_-]{0,63}$/.test(e) && !/^(?:cs_(?:live|test)|oaics|(?:pk|sk)_(?:live|test))(?:_|$)/.test(e) && !e.includes("secret")).map((e) => o[e] || e))], c = e.checkout_amount_due_minor, l = e.checkout_currency_exponent, u = String(e.checkout_currency || "").toUpperCase();
	if (n === "success" && typeof c == "number" && Number.isSafeInteger(c) && c >= 0 && typeof l == "number" && Number.isInteger(l) && l >= 0 && l <= 3 && /^[A-Z]{3}$/.test(u)) {
		let e = String(c).padStart(l + 1, "0");
		t.push(`实际应付: ${l ? `${e.slice(0, -l)}.${e.slice(-l)}`.replace(/\.?0+$/, "") : e} ${u}`);
	}
	return n === "success" && ["cs_live", "oaics"].includes(String(e.session_type)) && t.push(`结账会话: ${e.session_type}`), t.push(`支付方式: ${s.join(" ") || (n === "success" ? "未返回" : "待查询")}`), t.join("；");
}
function ie(e) {
	if (e.task_type !== "plan_check") return I(e);
	let t = T(e.result_summary), n = [I(e), ...E(t.country_failures).map((e) => `${e.country}：${e.summary || "诊断记录不完整"}`)], r = Array.isArray(t.plan_check_countries) && !t.plan_check_countries.length ? [] : E(t.plan_check_country_results).filter((e) => e.country);
	if (!r.length) {
		let e = N(t);
		e.length ? n.push(...e.map((e) => [`${e.country}${e.items.some((e) => e.stale) ? "（历史）" : ""}`, ...e.items.map(L)].join("\n"))) : n.push(...A(t).map(L));
	}
	for (let t of r) {
		let r = T(t.result), i = Object.keys(r).length > 0 && !!t.last_success_at, a = t.status !== "success" && i || ["queued", "running"].includes(String(e.status)), o = [`${String(t.country).toUpperCase()}${a ? "（历史）" : ""}`];
		t.status === "success" || i ? o.push(...A(r).map((e) => L({
			...e,
			country: t.country
		}))) : o.push(_("status", t.status)), (t.error || t.http_status) && o.push(`本次查询${t.status === "cancelled" ? "取消" : "失败"}: ${t.error || `HTTP ${t.http_status}`}`), t.checked_at && o.push(`查询于 ${h(t.checked_at)}`), i && a && o.push(`显示上次成功快照；上次成功查询: ${h(t.last_success_at)}`), n.push(o.join("\n"));
	}
	return n.filter(Boolean).join("\n");
}
// src/features/tasks/detail/model.ts
function R(e) {
	return typeof e == "object" && e && !Array.isArray(e) ? e : {};
}
var z = (e) => e == null ? "" : String(e), ae = (e) => Array.isArray(e) ? e.map(R) : [], B = (e) => Array.isArray(e) ? e.map(z) : [], V = {
	pending: "未开始",
	queued: "排队中",
	waiting: "等待中",
	running: "执行中",
	success: "已完成",
	skipped: "已跳过",
	failed: "失败",
	recovered: "重试已恢复",
	unconfirmed: "响应记录缺失",
	not_executed: "未执行",
	request_unknown: "失败",
	record_incomplete: "记录不完整",
	debug_paused: "调试暂停",
	stopped: "已中断",
	cancelled: "已取消",
	interrupted: "已中断",
	attention_required: "失败",
	partial_success: "部分完成",
	deferred: "已延后",
	awaiting_confirmation: "等待响应",
	manual_reconcile: "失败",
	unsupported: "不支持",
	deactivated: "已停用"
}, H = (e) => z(e.display_status || e.state || "pending").toLowerCase(), U = (e) => V[z(e)] || z(e) || "状态记录缺失", W = (e) => z(e.id || e.step_id), G = (e) => ({
	authenticate: "登录验证",
	set_twofa: "配置 2FA"
})[W(e)] || e.label || e.name || W(e);
function K(e, t, n, r = !1) {
	if (!t) return !0;
	let i = R(r ? e.fields : e.detail), a = n.find((e) => W(e) === t || e.raw_stages?.includes(t)), o = a?.raw_stages || [], s = z(e.main_step_id || i.main_step_id), c = z(e.stage || i.stage), l = r ? "" : z(e.stage_label || i.stage_label), u = z(e.event_id || (r ? i.event_id : e.id));
	if (s) return s === (a?.id || t) || u === t;
	if (u === t || a && B(a.event_ids).includes(u)) return !0;
	let d = [z(e.raw_stage || i.raw_stage), ...B(e.raw_stages || i.raw_stages)], f = [
		c,
		l,
		...d
	].filter(Boolean), p = n.filter((e) => f.some((t) => e.raw_stages?.includes(t)));
	return a && p.length > 1 ? !1 : [
		c,
		l,
		...d
	].includes(t) || f.some((e) => o.includes(e));
}
function q(e, t) {
	let n = new Set(e.map((e) => String(e.id)));
	return [...e, ...t.filter((e) => !n.has(String(e.id)))];
}
function J(e) {
	return [...e].sort((e, t) => (Date.parse(e.created_at || "") || 0) - (Date.parse(t.created_at || "") || 0) || ee(e.id, t.id));
}
function oe(e) {
	let t = Object.entries(R(e)).filter(([e, t]) => e !== "step_state" && t != null && t !== "" && (!Array.isArray(t) || t.length > 0) && (typeof t != "object" || Array.isArray(t) || Object.keys(R(t)).length > 0));
	return t.length ? Object.fromEntries(t) : null;
}
function se(e) {
	let t = z(R(e.detail).step_state || (e.event_type || "").replace(/^stage\./, "")).toLowerCase();
	return [
		"pending",
		"running",
		"success",
		"skipped",
		"failed"
	].includes(t) ? t : z(e.level).toUpperCase() === "ERROR" ? "failed" : "";
}
function ce(e) {
	let t = e.error_info?.cause_summary || e.error_info?.summary || e.message || "";
	return !t || /^(?:远端)?(?:结果)?(?:待确认|未确认|待核验|未知)$/.test(t) ? "失败诊断记录缺失" : t;
}
function le(e) {
	let t = R(e.evidence);
	return e.inferred === !0 || t.inferred === !0 || [
		"inferred",
		"legacy",
		"unobserved"
	].includes(z(e.evidence)) || t.source === "inferred" || t.kind === "inferred";
}
function Y(e, t = Date.now()) {
	let n = Date.parse(e.started_at || ""), r = Date.parse(e.completed_at || ""), i = Date.parse(z(R(e.debug_pause).paused_at)), a = H(e), o = a === "debug_paused" ? i - n : a === "running" && Number.isFinite(n) ? t - n : e.duration_ms ?? r - n;
	return Number.isFinite(o) && o >= 0 ? o : null;
}
function ue(e) {
	let t = z(e);
	return /^\/api\/operations\/\d+\/runs\/\d+\/debug\/(har|page-state|screenshot)(?:\?.*)?$/.test(t) ? t : null;
}
// src/features/tasks/detail/flowPresentation.ts
var X = (e) => (e || []).filter((e) => H(e) !== "skipped" || !!e.execution?.condition || e.execution?.kind === "conditional");
function Z(e) {
	let t = e.execution;
	return t?.condition?.state === "not_met" ? "条件未满足" : t?.dependency_state === "blocked" ? t.waits_for?.length ? "子任务未完成" : "前置阶段失败" : t?.dependency_state === "waiting" ? t.waits_for?.length ? "等待子任务" : "等待前置阶段" : t?.retry?.state === "recovered" ? "重试已恢复" : U(H(e));
}
function de(e) {
	let t = e.execution;
	return t ? [
		t.kind === "conditional" ? "条件阶段" : t.kind === "child_task" ? "子任务" : "",
		t.parallel_group ? "并行分支" : "",
		t.retry?.state === "observed" ? "有重试记录" : ""
	].filter(Boolean) : [];
}
function fe(e, t = []) {
	let n = e.execution, r = [], i = e.depends_on || [];
	if (i.length && r.push({
		label: "依赖阶段",
		value: i.map((e) => {
			let n = t.find((t) => t.id === e);
			return n ? G(n) : e;
		}).join("、")
	}), n?.condition) {
		let e = {
			met: "已满足",
			not_met: "未满足",
			unknown: "未确认"
		}[n.condition.state];
		r.push({
			label: "触发条件",
			value: `${n.condition.label} · ${e}`
		});
	}
	return n?.dependency_state && n.dependency_state !== "unknown" && r.push({
		label: "依赖状态",
		value: {
			waiting: n.waits_for?.length ? "等待子任务完成" : "等待前置完成",
			blocked: n.waits_for?.length ? "子任务未成功完成" : "前置阶段失败",
			satisfied: "已满足"
		}[n.dependency_state]
	}), n?.parallel_group && r.push({
		label: "并行分组",
		value: n.parallel_group
	}), n?.retry && n.retry.state !== "unknown" && r.push({
		label: "重试",
		value: `${n.retry.state === "recovered" ? "重试已恢复" : "有重试记录"}${n.retry.attempt_count ? ` · ${n.retry.attempt_count} 次尝试` : ""}`
	}), n && (r.length || n.waits_for?.length) || r.push({
		label: "关系记录",
		value: "没有足够证据确定依赖或并行关系"
	}), e.observed_order != null && r.push({
		label: "首次记录",
		value: `第 ${e.observed_order} 个被记录的阶段`
	}), r;
}
function pe(e, t = []) {
	let n = [];
	e.depends_on?.length && n.push("前置：" + e.depends_on.map((e) => t.find((t) => t.id === e)?.label || e).join("、"));
	let r = e.execution?.waits_for;
	if (r?.length) {
		let e = r.filter((e) => e.task_id).map((e) => "#" + e.task_id);
		n.push(e.length ? "等待子任务 " + e.join("、") : "等待关联子任务");
	}
	return e.execution?.condition?.label && n.push("条件：" + e.execution.condition.label), e.execution?.parallel_group && n.push("并行：" + e.execution.parallel_group), n;
}
// src/features/tasks/detail/StepRelations.vue?vue&type=script&setup=true&lang.ts
var me = { class: "tc-step-relations" }, Q = /*#__PURE__*/ u(/* @__PURE__ */ e({
	__name: "StepRelations",
	props: {
		step: {},
		siblings: {}
	},
	setup(e) {
		let r = e, u = c(() => fe(r.step, r.siblings));
		return (r, c) => (t(), d("dl", me, [(t(!0), d(a, null, n(u.value, (e) => (t(), d("div", { key: e.label }, [s("dt", null, o(e.label), 1), s("dd", null, o(e.value), 1)]))), 128)), (t(!0), d(a, null, n(e.step.execution?.waits_for || [], (e, n) => (t(), d("div", { key: `${e.task_id}:${e.run_id}:${n}` }, [c[1] ||= s("dt", null, "关联子任务", -1), s("dd", null, [e.task_id ? (t(), d(a, { key: 0 }, [
			f(o(l(_)("task_type", e.task_type)) + " #" + o(e.task_id), 1),
			e.run_id ? (t(), d(a, { key: 0 }, [f(" · 运行 #" + o(e.run_id), 1)], 64)) : i("", !0),
			e.status ? (t(), d(a, { key: 1 }, [f(" · " + o(l(U)(e.status)), 1)], 64)) : i("", !0)
		], 64)) : (t(), d(a, { key: 1 }, [c[0] ||= f("子任务关联标识未记录", -1), e.status ? (t(), d(a, { key: 0 }, [f(" · " + o(l(U)(e.status)), 1)], 64)) : i("", !0)], 64))])]))), 128))]));
	}
}), [["__scopeId", "data-v-69d878fd"]]), he = { class: "tc-step-evidence" }, ge = {
	key: 0,
	class: "tc-step-evidence__summary"
}, _e = { class: "tc-detail-facts" }, ve = { key: 0 }, ye = {
	key: 1,
	class: "tc-technical"
}, be = { class: "tc-attempt-list" }, $ = { key: 0 }, xe = {
	key: 2,
	class: "tc-technical"
}, Se = { class: "tc-attempt-list" }, Ce = { class: "tc-event-meta" }, we = {
	key: 3,
	class: "tc-technical"
}, Te = {
	key: 4,
	class: "tc-technical"
}, Ee = /* @__PURE__ */ e({
	__name: "StepEvidence",
	props: {
		step: {},
		siblings: {}
	},
	setup(e) {
		return (c, u) => {
			let m = p("StepEvidence", !0);
			return t(), d("section", he, [
				e.step.reason || e.step.message ? (t(), d("p", ge, o(e.step.reason || e.step.message), 1)) : i("", !0),
				s("dl", _e, [
					s("div", null, [u[0] ||= s("dt", null, "状态", -1), s("dd", null, o(l(Z)(e.step)), 1)]),
					s("div", null, [u[1] ||= s("dt", null, "开始", -1), s("dd", null, o(l(h)(e.step.started_at)), 1)]),
					s("div", null, [u[2] ||= s("dt", null, "结束", -1), s("dd", null, o(l(h)(e.step.completed_at)), 1)]),
					s("div", null, [u[3] ||= s("dt", null, "耗时", -1), s("dd", null, o(l(v)(l(Y)(e.step))), 1)]),
					e.step.raw_stages?.length ? (t(), d("div", ve, [u[4] ||= s("dt", null, "原始阶段", -1), s("dd", null, o(e.step.raw_stages.join("、")), 1)])) : i("", !0)
				]),
				r(Q, {
					step: e.step,
					siblings: e.siblings
				}, null, 8, ["step", "siblings"]),
				e.step.step_instances?.length ? (t(), d("details", ye, [s("summary", null, "阶段实例（" + o(e.step.step_instances.length) + "）", 1), s("ol", be, [(t(!0), d(a, null, n(e.step.step_instances, (e, n) => (t(), d("li", { key: l(z)(e.step_instance_id) || n }, [
					s("strong", null, "记录 " + o(n + 1) + " · " + o(l(U)(e.state)), 1),
					s("p", null, o(l(h)(e.started_at)) + " → " + o(l(h)(e.completed_at)), 1),
					e.message ? (t(), d("p", $, o(e.message), 1)) : i("", !0)
				]))), 128))])])) : i("", !0),
				e.step.attempts?.length ? (t(), d("details", xe, [s("summary", null, "阶段事件（" + o(e.step.attempts.length) + "）", 1), s("ol", Se, [(t(!0), d(a, null, n(e.step.attempts, (e, n) => (t(), d("li", { key: l(z)(e.event_id) || n }, [
					s("div", Ce, [s("strong", null, "记录 " + o(n + 1) + " · " + o(l(U)(e.display_status || e.state)), 1), s("time", null, o(!e.created_at && e.event_time_known === !1 ? "发生时间未记录" : l(h)(l(z)(e.created_at))), 1)]),
					s("p", null, o(e.message || "无补充说明"), 1),
					s("small", null, [f(o(e.raw_stage_label || e.raw_stage), 1), e.event_id ? (t(), d(a, { key: 0 }, [f(" · 事件 " + o(e.event_id), 1)], 64)) : i("", !0)]),
					s("details", null, [u[5] ||= s("summary", null, "技术字段", -1), s("pre", null, o(JSON.stringify(e, null, 2)), 1)])
				]))), 128))])])) : i("", !0),
				l(X)(e.step.children).length ? (t(), d("details", we, [s("summary", null, "子步骤（" + o(l(X)(e.step.children).length) + "）", 1), (t(!0), d(a, null, n(l(X)(e.step.children), (n) => (t(), d("section", {
					key: n.id,
					class: "tc-child-step"
				}, [s("h4", null, [f(o(l(G)(n)) + " ", 1), s("span", null, o(l(U)(l(H)(n))), 1)]), r(m, {
					step: n,
					siblings: e.step.children
				}, null, 8, ["step", "siblings"])]))), 128))])) : i("", !0),
				e.step.evidence && Object.keys(l(R)(e.step.evidence)).length ? (t(), d("details", Te, [u[6] ||= s("summary", null, "步骤证据", -1), s("pre", null, o(JSON.stringify(e.step.evidence, null, 2)), 1)])) : i("", !0)
			]);
		};
	}
});
export { b as A, D as C, y as D, C as E, w as F, g as M, T as N, re as O, ie as P, z as S, te as T, ae as _, Z as a, G as b, se as c, K as d, oe as f, U as g, J as h, de as i, _ as j, v as k, le as l, R as m, Q as n, X as o, q as p, pe as r, ue as s, Ee as t, ce as u, Y as v, x as w, H as x, W as y };
