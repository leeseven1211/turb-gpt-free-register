import { $ as e, A as t, C as n, E as r, F as i, H as a, J as o, K as s, L as c, M as l, Q as u, S as d, Z as f, _ as p, d as m, et as h, ft as g, g as _, h as v, j as y, lt as b, m as x, n as S, nt as C, o as w, st as T, t as E, v as D, x as O } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { n as k } from "./time-DOD6oyhP.js";
import { r as A } from "./client-BBEPwkQG.js";
import { a as j, n as M, r as N } from "./taskIds-BlchWwUp.js";
// src/features/config/navigation.ts
var P = {
	注册与账号: [
		"注册主链路",
		"账号补全",
		"注册与账号",
		"查活",
		"刷新 AT",
		"补密码",
		"补 2FA",
		"邮箱换绑"
	],
	代理与网络: ["代理与网络"],
	邮箱与验证码: ["邮箱 / OTP", "接码平台"],
	浏览器: [
		"RoxyBrowser",
		"浏览器画像",
		"人工节奏"
	],
	服务集成: ["Codex", "C2A"],
	提链: ["提链"],
	系统与维护: [
		"并发控制",
		"通用配置",
		"WebUI 授权",
		"定时任务",
		"任务中心",
		"注册调试"
	]
}, F = {
	注册设置: "注册主链路",
	账号设置: "账号补全",
	注册与账号: "注册主链路",
	执行方式: "注册主链路",
	"邮箱 / OTP": "邮箱 / OTP",
	接码平台: "接码平台",
	邮箱: "邮箱 / OTP",
	浏览器设置: "RoxyBrowser",
	Codex: "Codex",
	提链: "提链",
	系统设置: "通用配置",
	网站配置: "WebUI 授权"
}, I = [
	"ACCOUNT_PLAN_CHECK_DRIVER",
	"PLAN_CHECK_AUTO_REFRESH_AT_ENABLED",
	"PLAN_CHECK_PAYMENT_METHODS_ENABLED",
	"PLAN_CHECK_COUNTRIES",
	"PLAN_CHECK_COUNTRY_WAIT_TIMEOUT",
	"PLAN_CHECK_TIMEOUT",
	"PLAN_CHECK_MAX_ATTEMPTS",
	"PLAN_CHECK_RETRY_DELAY",
	"PLAN_CHECK_REGISTRATION_RECHECK_DELAY",
	"PLAN_CHECK_MIN_INTERVAL",
	"PLAN_CHECK_JITTER"
], L = {
	查活: [["查活策略", ["ACCOUNT_LIVE_CHECK_DRIVER", "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED"]]],
	"刷新 AT": [
		["刷新 AT 策略", [
			"ACCOUNT_AT_REFRESH_DRIVER",
			"ACCOUNT_AT_REFRESH_COUNTRY",
			"OPENAI_PROTOCOL_VERSION",
			"ACCOUNT_AT_REFRESH_NETWORK_RETRIES",
			"ACCOUNT_AT_REFRESH_NETWORK_TIMEOUT_SECONDS",
			"LIVE_CHECK_ROXY_FALLBACK_ENABLED",
			"ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED"
		]],
		["协议认证策略", ["ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", "ACCOUNT_AUTH_PROFILE_MODE"]],
		["自动刷新", [
			"AT_AUTO_REFRESH_ENABLED",
			"AT_REFRESH_SCAN_INTERVAL_SECONDS",
			"AT_REFRESH_BEFORE_HOURS",
			"AT_REFRESH_INITIAL_DELAY_SECONDS",
			"AT_REFRESH_MAX_PER_CYCLE"
		]]
	],
	补密码: [["密码补全策略", ["ACCOUNT_PASSWORD_DRIVER", "ACCOUNT_PASSWORD_RESET_ENABLED"]]],
	"补 2FA": [["2FA 补全策略", [
		"ACCOUNT_2FA_DRIVER",
		"ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED",
		"ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED"
	]], ["2FA 重认证参数", ["TWOFA_REAUTH_MAX_ATTEMPTS", "TWOFA_REAUTH_RETRY_DELAY"]]],
	邮箱换绑: [["邮箱换绑策略", ["ACCOUNT_EMAIL_CHANGE_ENABLED", "ACCOUNT_EMAIL_CHANGE_MIN_ACCOUNT_AGE_HOURS"]]]
}, R = [
	["REGISTRATION_PROXY_RETRIES", "注册主链路"],
	["REGISTRATION_PROXY_RETRY_DELAY", "注册主链路"],
	["ACCOUNT_ACTION_PROXY_RETRIES", "账号补全"],
	["ACCOUNT_ACTION_PROXY_RETRY_DELAY", "账号补全"],
	["ACCOUNT_LIVE_CHECK_DRIVER", "查活"],
	["ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", "查活"],
	["ACCOUNT_AT_REFRESH_DRIVER", "刷新 AT"],
	["ACCOUNT_AT_REFRESH_COUNTRY", "刷新 AT"],
	["OPENAI_PROTOCOL_VERSION", "刷新 AT"],
	["ACCOUNT_AT_REFRESH_NETWORK_RETRIES", "刷新 AT"],
	["ACCOUNT_AT_REFRESH_NETWORK_TIMEOUT_SECONDS", "刷新 AT"],
	["LIVE_CHECK_ROXY_FALLBACK_ENABLED", "刷新 AT"],
	["ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED", "刷新 AT"],
	["ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", "刷新 AT"],
	["ACCOUNT_AUTH_PROFILE_MODE", "刷新 AT"],
	["AT_AUTO_REFRESH_ENABLED", "刷新 AT"],
	["AT_REFRESH_SCAN_INTERVAL_SECONDS", "刷新 AT"],
	["AT_REFRESH_BEFORE_HOURS", "刷新 AT"],
	["AT_REFRESH_INITIAL_DELAY_SECONDS", "刷新 AT"],
	["AT_REFRESH_MAX_PER_CYCLE", "刷新 AT"],
	["ACCOUNT_PASSWORD_DRIVER", "补密码"],
	["ACCOUNT_PASSWORD_RESET_ENABLED", "补密码"],
	["ACCOUNT_2FA_DRIVER", "补 2FA"],
	["ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", "补 2FA"],
	["ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED", "补 2FA"],
	["TWOFA_REAUTH_MAX_ATTEMPTS", "补 2FA"],
	["TWOFA_REAUTH_RETRY_DELAY", "补 2FA"],
	["ACCOUNT_EMAIL_CHANGE_ENABLED", "邮箱换绑"],
	["ACCOUNT_EMAIL_CHANGE_MIN_ACCOUNT_AGE_HOURS", "邮箱换绑"]
], z = {
	"1024proxy": { prefix: "PROXY_1024_" },
	"711proxy": { prefix: "PROXY_711_" }
};
function B(e) {
	return [
		"USE_EMAIL_SERVICE",
		"REGISTER_EMAIL",
		"OTP_MAX_WAIT",
		"OTP_POLL_INTERVAL",
		"EMAIL_SOURCE"
	].includes(e) ? ["通用邮箱 / OTP", "邮箱来源选择、OTP 等待参数、手动邮箱等通用设置"] : e.startsWith("EMAIL_BUTLER_") ? ["Email Butler", "已导入邮箱的租约连接与取码权限"] : e.startsWith("GPTMAIL_") ? ["GPTMail", "GPTMail 临时邮箱 API 配置"] : e.startsWith("MAIL_NEST_") ? ["MailNest", "MailNest / 迈巢临时邮箱 API 配置"] : e.startsWith("REMAIL_") ? ["Remail", "历史 Remail 原订单收码连接；新邮箱请在邮箱服务中准备后导入"] : e.startsWith("MAILCODE_") ? ["域名邮箱 MailCode", "历史 MailCode 原订单收码连接"] : e.startsWith("XIGUA_") ? ["西瓜邮箱", "历史原订单的固定收码连接与轮询参数"] : e.startsWith("CLOUDMAIL_") ? ["CloudMail", "历史邮箱收信 API 连接及已有 Token"] : e.startsWith("ICLOUD_HME_") ? ["iCloud 隐藏邮箱", "已导入与历史隐藏邮箱的固定收件连接；邮箱管理在邮箱服务完成"] : e.startsWith("OUTLOOK_") ? ["Outlook 邮箱池", "Outlook 邮箱池和取件模式配置"] : e.startsWith("CLOUDFLARE_") ? ["Cloudflare 临时邮箱", "Cloudflare Worker 临时邮箱 API、鉴权与路径配置"] : [
		"EMAIL_DOMAIN",
		"QQ_EMAIL",
		"QQ_IMAP_PASSWORD"
	].includes(e) ? ["Cloudflare 域名邮箱", "Cloudflare 转发到 QQ 邮箱后的 IMAP 收信配置"] : ["其他邮箱配置", ""];
}
function ee(e) {
	return ["REGISTRATION_PROXY_RETRIES", "REGISTRATION_PROXY_RETRY_DELAY"].includes(e) ? ["注册主链路", "注册任务重试参数已归入注册主链路；线路本身由统一代理池按国家需求领取。"] : ["ACCOUNT_ACTION_PROXY_RETRIES", "ACCOUNT_ACTION_PROXY_RETRY_DELAY"].includes(e) ? ["账号补全", "账号动作重试参数已归入账号补全；新任务不在这里选择代理供应商。"] : [
		"PROXY_1024_REGION",
		"PROXY_1024_ROTATE_SESSION_TIME",
		"PROXY_1024_VALIDATE",
		"PROXY_1024_MAX_ATTEMPTS"
	].includes(e) ? ["高级兼容", "1024Proxy 的历史区域值仅用于读取旧配置；新任务按各自业务国家向代理池申请。"] : [
		"PROXY_POOL_SOURCE",
		"PROXY_POOL_DEFAULT_COUNTRY",
		"PROXY_POOL"
	].includes(e) ? ["代理来源", "统一代理池的当前供给来源与默认国家。业务任务只提出国家和用途需求。"] : e === "PROXY_POOL_WAIT_TIMEOUT" ? ["库存策略", "库存不足时持续等待或按配置时限等待，不在业务线程直接调用供应商。"] : ["PLAN_CHECK_PROXY_ALLOW_REUSE", "PLAN_CHECK_PROXY_REUSE_LIMIT"].includes(e) ? ["库存策略", "仅套餐查询用途允许按策略复用已检测出口，其他认证链路仍保持租约隔离。"] : e.startsWith("PROXY_POOL_") ? ["库存策略", "统一代理池的容量、预热、领取和回收策略。"] : (/* @__PURE__ */ new Set([
		"REGISTRATION_PROXY_MODE",
		"ACCOUNT_PASSWORD_PROXY_MODE",
		"ACCOUNT_2FA_PROXY_MODE",
		"ACCOUNT_PLAN_CHECK_PROXY_MODE",
		"ACCOUNT_LIVE_CHECK_PROXY_MODE",
		"ACCOUNT_REFRESH_AT_PROXY_MODE",
		"ACCOUNT_CODEX_PROXY_MODE",
		"ACCOUNT_EMAIL_CHANGE_PROXY_MODE",
		"PLAN_CHECK_PROXY_MODE",
		"PLAN_CHECK_PROXY",
		"REGISTRATION_PROXY_PROVIDER",
		"REGISTRATION_PROXY_REGION",
		"ACCOUNT_PLAN_CHECK_PROVIDER",
		"ACCOUNT_PLAN_CHECK_REGION"
	])).has(e) || e.endsWith("_PROXY_MODE") ? ["高级兼容", "旧版逐动作来源字段仅用于读取历史快照，不参与新任务的代理池选择。"] : [
		"ACCOUNT_PASSWORD_PROXY_MODE",
		"ACCOUNT_2FA_PROXY_MODE",
		"ACCOUNT_PLAN_CHECK_PROXY_MODE",
		"PLAN_CHECK_PROXY_ALLOW_REUSE",
		"PLAN_CHECK_PROXY_REUSE_LIMIT",
		"PLAN_CHECK_PAYMENT_METHODS_ENABLED",
		"PLAN_CHECK_COUNTRIES",
		"PLAN_CHECK_COUNTRY_WAIT_TIMEOUT",
		"ACCOUNT_LIVE_CHECK_PROXY_MODE",
		"ACCOUNT_REFRESH_AT_PROXY_MODE",
		"ACCOUNT_CODEX_PROXY_MODE",
		"ACCOUNT_EMAIL_CHANGE_PROXY_MODE",
		"PLAN_CHECK_TIMEOUT",
		"PLAN_CHECK_MAX_ATTEMPTS",
		"PLAN_CHECK_RETRY_DELAY",
		"PLAN_CHECK_REGISTRATION_RECHECK_DELAY",
		"PLAN_CHECK_MIN_INTERVAL",
		"PLAN_CHECK_JITTER"
	].includes(e) ? ["高级兼容", "旧版逐动作来源字段仅用于读取历史快照；新任务按账号国家和业务用途从统一代理池领取线路。"] : Object.values(z).some((t) => e.startsWith(t.prefix)) || e.startsWith("REGISTRATION_PROXY_") ? ["代理来源", "当前供应商的提取、检测和粘性参数；切换来源会保留各供应商配置。"] : ["高级兼容", "历史代理配置保留供兼容读取；新任务统一向代理池申请线路。"];
}
function te(e) {
	return [
		"CODEX_PHONE_ENABLED",
		"SMS_PROVIDER",
		"SMS_COUNTRY",
		"SMS_SERVICE",
		"SMS_MAX_PRICE",
		"SMS_AUTO_SELECT_COUNTRY",
		"SMS_AUTO_COUNTRY_MIN_RATIO",
		"SMS_MAX_RETRIES",
		"SMS_CODE_WAIT",
		"CODEX_PHONE_TOTAL_TIMEOUT"
	].includes(e) ? ["通用接码", "手机接码关闭时，Codex OAuth 遇到手机验证会报错退出；接码配置只在开启且实际需要时检查。H 通道可复用 SMS_SERVICE/SMS_COUNTRY 作为 projectId/country"] : e === "SMS_API_KEY" ? ["GrizzlySMS", "GrizzlySMS 平台 API Key 配置"] : e.startsWith("H_") ? ["H 接码", "H_API.md 本地 H 取号服务配置；项目ID/国家留空时复用通用字段"] : e.startsWith("L_") ? ["L 接码", "本地 L 取号服务配置，接口约定见 README"] : ["其他接码配置", ""];
}
function ne(e) {
	return ["CODEX_OAUTH_DRIVER", "CODEX_AUTH_URL_SOURCE"].includes(e) ? ["基础配置", "Codex 授权驱动和授权地址来源配置"] : e.startsWith("CODEX_TOKEN_") ? ["Token 自动刷新", "使用 refresh_token 提前换新 Codex access token，不重新登录、不消耗邮箱 OTP 或短信"] : e.startsWith("CPA_") ? ["CPA配置", "CPA 授权链接生成、回调上传和管理接口配置"] : e.startsWith("SUB2API_") || e === "CODEX_OAUTH_AUTO_UPLOAD_SUB2API" ? ["sub2api", "sub2api 的 API 基址、鉴权和超时配置；用于 Codex OAuth 授权和凭证上传"] : ["基础配置", ""];
}
var re = new Map(R), V = new Set(I), ie = "gpt_console_config_group", ae = {
	legacy: "虾扯蛋链",
	lumen_flow: "流光",
	huanguang: "幻光",
	anguang: "暗光（XXSYUN 一条龙）"
}, oe = /* @__PURE__ */ new Set([
	"EXTRACT_LINK_API_BASE",
	"EXTRACT_LINK_CDK",
	"EXTRACT_LINK_TYPE",
	"EXTRACT_LINK_REQUEST_TIMEOUT",
	"EXTRACT_LINK_EVENT_TIMEOUT"
]), se = {
	"1024proxy": "PROXY_1024_",
	"711proxy": "PROXY_711_"
};
function H(e) {
	return V.has(e.key) ? "注册与账号" : re.get(e.key) || e.group || "其他";
}
function U(e) {
	if (P[e]) return e;
	let t = F[e] || e || "其他";
	return Object.keys(P).find((e) => P[e].includes(t)) || t;
}
function W(e) {
	let t = /* @__PURE__ */ new Set();
	return e.filter((e) => !e.hidden && !t.has(e.key) && !!t.add(e.key)).map((e) => ({
		...e,
		group: H(e)
	}));
}
function ce(e) {
	let t = [...new Set(W(e).map((e) => U(e.group)))];
	return [...Object.keys(P).filter((e) => t.includes(e)), ...t.filter((e) => !P[e])];
}
function le(e, t) {
	let n = [...new Set(W(t).filter((t) => U(t.group) === e).map((e) => e.group))];
	return [...(P[e] || []).filter((e) => n.includes(e)), ...n.filter((t) => !(P[e] || []).includes(t))];
}
function G(e) {
	return (e?.options || []).flatMap((e) => typeof e == "string" ? [{
		value: e,
		label: e
	}] : e && e.value != null ? [{
		...e,
		value: String(e.value),
		label: String(e.label ?? e.value)
	}] : []);
}
function ue(e) {
	let t = String(e ?? "roxy").trim().toLowerCase() || "roxy";
	return {
		protocol: "protocol_oss_2",
		protocol_oss: "protocol_oss_2",
		roxy_oss: "roxy"
	}[t] || t;
}
function de(e) {
	return G(e.find((e) => e.key === "EXTRACT_LINK_DEFAULT_PROVIDER")).map((e) => ({
		...e,
		value: e.value.toLowerCase(),
		label: ae[e.value.toLowerCase()] || e.label,
		enabledKey: `EXTRACT_LINK_${e.value.toUpperCase()}_ENABLED`
	})).filter((t) => e.some((e) => e.key === t.enabledKey));
}
function fe(e, t) {
	let n = H(e), r = e.key;
	if (n === "邮箱 / OTP") return B(r)[0];
	if (n === "代理与网络") return ee(r)[0];
	if (n === "接码平台") return te(r)[0];
	if (n === "Codex") return ne(r)[0];
	if (n === "提链") {
		if (r.startsWith("EXTRACT_LINK_PAYMENT_")) return "独立支付";
		let e = de(t);
		return e.some((e) => e.enabledKey === r) ? "通用配置" : e.find((e) => e.value === "legacy" ? oe.has(r) || r.startsWith("EXTRACT_LINK_LEGACY_") : r.startsWith(`EXTRACT_LINK_${e.value.toUpperCase()}_`))?.label || "通用配置";
	}
	return "";
}
var pe = {
	"邮箱 / OTP": [
		"通用邮箱 / OTP",
		"iCloud 隐藏邮箱",
		"Email Butler",
		"GPTMail",
		"MailNest",
		"Remail",
		"域名邮箱 MailCode",
		"西瓜邮箱",
		"CloudMail",
		"Outlook 邮箱池",
		"Cloudflare 临时邮箱",
		"Cloudflare 域名邮箱",
		"其他邮箱配置"
	],
	接码平台: [
		"通用接码",
		"GrizzlySMS",
		"H 接码",
		"L 接码",
		"其他接码配置"
	],
	代理与网络: [
		"任务用池",
		"代理来源",
		"库存策略",
		"高级兼容"
	],
	Codex: [
		"基础配置",
		"CPA配置",
		"sub2api",
		"Token 自动刷新"
	]
};
function me(e, t) {
	if (e === "提链") return [
		"通用配置",
		...de(t).map((e) => e.label),
		"独立支付"
	];
	let n = [...new Set(W(t).filter((t) => t.group === e).map((e) => fe(e, t)))].filter(Boolean), r = pe[e] || [];
	return e === "代理与网络" && n.unshift("任务用池"), [...r.filter((e) => n.includes(e)), ...n.filter((e) => !r.includes(e))];
}
function he(e, t) {
	let n = U(e), r = P[e] ? le(n, t)[0] || e : F[e] || e;
	return {
		menu: n,
		domain: r,
		section: me(r, t)[0] || ""
	};
}
function ge(e, t) {
	let n = H(e);
	return {
		menu: U(n),
		domain: n,
		section: fe(e, t)
	};
}
function _e(e, t) {
	let n = H(e);
	return [
		e.key,
		e.label,
		e.help,
		e.group,
		n,
		U(n),
		fe(e, t),
		...Object.keys(F).filter((e) => F[e] === n)
	].join(" ").toLowerCase();
}
function ve(e, t, n = "") {
	let r = e.trim().toLowerCase();
	if (!r) return null;
	let i = W(t), a = i.find((e) => e.key.toLowerCase() === r), o = i.filter((e) => _e(e, t).includes(r)), s = a || o.find((e) => U(e.group) === n) || o[0];
	if (s) return ge(s, t);
	let c = ce(t).find((e) => e.toLowerCase().includes(r));
	return c ? he(c, t) : null;
}
function ye(e, t, n) {
	let r = W(e.fields.value).filter((n) => n.group === t.domain && (!t.section || fe(n, e.fields.value) === t.section));
	if (t.domain === "提链" && t.section === "通用配置") {
		let t = new Set(de(e.fields.value).map((e) => e.enabledKey));
		r = r.filter((e) => !t.has(e.key));
	}
	if (t.domain === "代理与网络" && t.section === "代理来源" && !n) {
		let t = String(e.readField("PROXY_POOL_SOURCE") || "1024proxy");
		r = r.filter((e) => {
			if (e.key === "PROXY_POOL") return t === "manual";
			let n = Object.keys(se).find((t) => e.key.startsWith(se[t]));
			return !n || t === n;
		});
	}
	return r.filter((e) => e.key !== "CONCURRENCY_POLICY_REVISION");
}
var be = {
	...L,
	注册主链路: [["注册基础流程", [
		"REGISTRATION_DRIVER",
		"REGISTRATION_COUNTRY",
		"REGISTRATION_AUTH_MODE",
		"REGISTER_NAME",
		"REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS"
	]], ["注册后能力", [
		"REGISTRATION_PLAN_CHECK_ENABLED",
		"ENABLE_2FA",
		"TWOFA_DRIVER",
		"ENABLE_CODEX_AUTO",
		"CODEX_OAUTH_DRIVER",
		"ENABLE_FLOW_TRIGGER"
	]]],
	账号补全: [["补全项目", [
		"ACCOUNT_COMPLETION_PASSWORD_ENABLED",
		"ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED",
		"ACCOUNT_COMPLETION_2FA_ENABLED",
		"ACCOUNT_COMPLETION_CODEX_ENABLED",
		"ACCOUNT_COMPLETION_REFRESH_AT_ENABLED"
	]], ["账号处理策略", [
		"ACCOUNT_AUTH_V2_ENABLED",
		"ACCOUNT_AUTH_RAW_CONTEXT_ENABLED",
		"ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS",
		"ACCOUNT_CODEX_DRIVER"
	]]],
	注册调试: [
		["失败诊断", [
			"REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED",
			"REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT",
			"REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB"
		]],
		["失败现场运行", ["REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS", "REGISTRATION_DEBUG_MAX_HELD_SESSIONS"]],
		["抓包存储与清理", [
			"REGISTRATION_DEBUG_BODY_MAX_KB",
			"REGISTRATION_DEBUG_BODY_BUDGET_MB",
			"REGISTRATION_DEBUG_GLOBAL_BUDGET_MB",
			"REGISTRATION_DEBUG_RETENTION_DAYS",
			"REGISTRATION_DEBUG_QUEUE_SIZE"
		]]
	]
};
function xe(e, t) {
	if (e === "注册与账号") return [{
		title: "查询套餐",
		fields: t
	}];
	let n = be[e];
	if (e === "定时任务" && (n = [
		["Email Butler 风险扫描", ["EMAIL_BUTLER_"]],
		["ChatGPT AT 自动刷新", ["AT_"]],
		["Codex Token 自动刷新", ["CODEX_TOKEN_"]],
		["sub2api 同步与异常巡检", ["SUB2API_"]]
	].map(([e, n]) => [e, t.filter((e) => n.some((t) => e.key.startsWith(t))).map((e) => e.key)])), !n) return [{
		title: "",
		fields: t
	}];
	let r = new Set(n.flatMap(([, e]) => e));
	return [...n.map(([e, n]) => ({
		title: e,
		fields: n.flatMap((e) => t.find((t) => t.key === e) || [])
	})), {
		title: "其他参数",
		fields: t.filter((e) => !r.has(e.key))
	}].filter((e) => e.fields.length);
}
function Se(e) {
	return ["注册与账号", "邮箱与验证码"].includes(e) ? "业务流程" : [
		"代理与网络",
		"浏览器",
		"服务集成",
		"提链"
	].includes(e) ? "资源与服务" : "系统";
}
// src/features/config/ConfigNavigation.vue?vue&type=script&setup=true&lang.ts
var Ce = {
	class: "config-vue-navigation",
	"aria-label": "配置分类"
}, we = ["value"], Te = {
	key: 0,
	class: "hint"
}, Ee = [
	"data-config-nav",
	"aria-current",
	"onClick"
], De = { key: 0 }, Oe = {
	key: 0,
	role: "status"
}, ke = /* @__PURE__ */ n({
	__name: "ConfigNavigation",
	props: {
		owner: {},
		active: {},
		query: {}
	},
	emits: ["select", "search"],
	setup(e, { emit: t }) {
		let n = e, r = t, a = x(() => ce(n.owner.fields.value).map((e) => {
			let t = W(n.owner.fields.value).filter((t) => U(t.group) === e);
			return {
				name: e,
				category: Se(e),
				count: t.length,
				dirty: t.filter((e) => n.owner.isDirty(e.key)).length,
				matches: !n.query.trim() || e.toLowerCase().includes(n.query.toLowerCase()) || t.some((e) => _e(e, n.owner.fields.value).includes(n.query.trim().toLowerCase()))
			};
		}));
		return (t, n) => (i(), D("nav", Ce, [
			n[1] ||= v("label", { for: "config-vue-search" }, "搜索配置", -1),
			v("input", {
				id: "config-vue-search",
				type: "search",
				value: e.query,
				placeholder: "名称、配置键或帮助",
				onInput: n[0] ||= (e) => r("search", e.target.value)
			}, null, 40, we),
			(i(), D(m, null, c([
				"业务流程",
				"资源与服务",
				"系统"
			], (t) => v("div", {
				key: t,
				class: "config-vue-nav-group"
			}, [a.value.some((e) => e.category === t && e.matches) ? (i(), D("p", Te, g(t), 1)) : p("", !0), (i(!0), D(m, null, c(a.value.filter((e) => e.category === t && e.matches), (t) => (i(), D("button", {
				key: t.name,
				type: "button",
				"data-config-nav": t.name,
				"aria-current": e.active === t.name ? "page" : void 0,
				onClick: (e) => r("select", t.name)
			}, [v("span", null, g(t.name), 1), v("small", null, [O(g(t.count) + " 项", 1), t.dirty ? (i(), D("span", De, " · " + g(t.dirty) + " 待保存", 1)) : p("", !0)])], 8, Ee))), 128))])), 64)),
			a.value.some((e) => e.matches) ? p("", !0) : (i(), D("p", Oe, "未找到匹配配置"))
		]));
	}
}), Ae = ["aria-label", "title"], je = { class: "config-vue-picker-menu" }, Me = ["aria-label"], Ne = {
	key: 0,
	class: "config-vue-chips",
	"aria-label": "已选国家，可点击移除"
}, Pe = ["aria-label", "onClick"], Fe = ["aria-label"], Ie = [
	"disabled",
	"aria-pressed",
	"title",
	"onClick"
], Le = { "aria-hidden": "true" }, Re = {
	key: 1,
	role: "status"
}, ze = /* @__PURE__ */ n({
	__name: "ConfigChoicePicker",
	props: {
		label: {},
		values: {},
		options: {},
		country: { type: Boolean },
		emptyLabel: { default: "未选择" }
	},
	emits: ["change"],
	setup(e, { emit: t }) {
		let n = e, r = t, a = h(""), o = h(), l = x(() => [...n.values.filter((e) => !n.options.some((t) => t.value === e)).map((e) => ({
			value: e,
			label: `当前值（${e}）`
		})), ...n.options]), u = x(() => l.value.filter((e) => `${e.value} ${e.label}`.toLowerCase().includes(a.value.trim().toLowerCase()))), d = x(() => n.values.map((e) => l.value.find((t) => t.value === e)?.label || e).join("、") || n.emptyLabel);
		function f(e) {
			r("change", n.values.includes(e) ? n.values.filter((t) => t !== e) : [...n.values, e]);
		}
		function _(e) {
			if (e.key === "Escape") {
				o.value && (o.value.open = !1, o.value.querySelector("summary")?.focus());
				return;
			}
			if (![
				"ArrowDown",
				"ArrowUp",
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			let t = Array.from(o.value?.querySelectorAll("[data-choice]") || []), n = t.indexOf(e.target);
			n < 0 || !t.length || (e.preventDefault(), t[e.key === "Home" ? 0 : e.key === "End" ? t.length - 1 : (n + (["ArrowUp", "ArrowLeft"].includes(e.key) ? -1 : 1) + t.length) % t.length]?.focus());
		}
		return (t, n) => (i(), D("details", {
			ref_key: "root",
			ref: o,
			class: "config-vue-picker",
			onKeydown: _
		}, [v("summary", {
			"aria-label": `${e.label}：${d.value}`,
			title: d.value
		}, g(d.value), 9, Ae), v("div", je, [
			s(v("input", {
				"onUpdate:modelValue": n[0] ||= (e) => a.value = e,
				type: "search",
				"aria-label": `搜索${e.label}`,
				placeholder: "搜索并选择"
			}, null, 8, Me), [[w, a.value]]),
			e.country ? (i(), D("div", Ne, [(i(!0), D(m, null, c(e.values, (e) => (i(), D("button", {
				key: e,
				type: "button",
				"aria-label": `移除 ${e}`,
				onClick: (t) => f(e)
			}, g(l.value.find((t) => t.value === e)?.label || e) + " ×", 9, Pe))), 128))])) : p("", !0),
			v("div", {
				class: "config-vue-picker-options",
				"aria-label": e.label,
				role: "group"
			}, [(i(!0), D(m, null, c(u.value, (t) => (i(), D("button", {
				key: t.value,
				type: "button",
				"data-choice": "",
				disabled: t.disabled,
				"aria-pressed": e.values.includes(t.value),
				title: t.reason,
				onClick: (e) => f(t.value)
			}, [v("span", Le, g(e.values.includes(t.value) ? "✓" : "○"), 1), O(" " + g(t.label), 1)], 8, Ie))), 128))], 8, Fe),
			u.value.length ? p("", !0) : (i(), D("p", Re, "未找到匹配选项"))
		])], 544));
	}
}), Be = ["aria-busy"], Ve = [
	"aria-label",
	"disabled",
	"data-config-field-action"
], He = /*#__PURE__*/ E(/* @__PURE__ */ n({
	__name: "ConfigFieldActions",
	props: {
		actions: {},
		fieldKey: {}
	},
	setup(e) {
		let t = e, n = {
			EXTRACT_LINK_HUANGUANG_CDK: {
				name: "huanguangExtraction",
				label: "查询剩余次数",
				accessibleLabel: "查询幻光提链 CDK 剩余次数",
				run: () => t.actions.queryHuanguangQuota("extraction")
			},
			EXTRACT_LINK_HUANGUANG_PAYMENT_CDK: {
				name: "huanguangPayment",
				label: "查询剩余次数",
				accessibleLabel: "查询幻光支付扫码 CDK 剩余次数",
				run: () => t.actions.queryHuanguangQuota("payment")
			},
			EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY: {
				name: "huanguangXxsyun",
				label: "查询剩余次数",
				accessibleLabel: "查询幻光 XXSYUN API Key 剩余次数",
				run: () => t.actions.queryHuanguangXxsyun()
			},
			EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY: {
				name: "xxsyunBalance",
				label: "查询积分",
				accessibleLabel: "查询独立支付 XXSYUN 积分",
				run: () => t.actions.queryXxsyunBalance()
			}
		}, r = x(() => n[t.fieldKey]), a = x(() => r.value ? t.actions.states[r.value.name] : null);
		return (t, n) => r.value && a.value ? (i(), D("div", {
			key: 0,
			class: "config-field-actions",
			"aria-busy": a.value.loading || a.value.posting
		}, [v("button", {
			type: "button",
			class: "btn",
			"aria-label": r.value.accessibleLabel,
			disabled: a.value.loading || a.value.posting,
			"data-config-field-action": e.fieldKey,
			onClick: n[0] ||= (e) => r.value.run()
		}, g(a.value.loading || a.value.posting ? "正在查询…" : r.value.label), 9, Ve), v("p", {
			class: b(["config-setting-short-help-v2", { "config-action-error": a.value.error }]),
			role: "status",
			"aria-live": "polite"
		}, g(a.value.error || a.value.text), 3)], 8, Be)) : p("", !0);
	}
}), [["__scopeId", "data-v-667794e0"]]), Ue = ["aria-busy"], We = [
	"id",
	"value",
	"aria-label",
	"aria-describedby"
], Ge = ["disabled"], Ke = ["id"], qe = {
	class: "config-multi-options-v2",
	"data-sub2api-monitor-group-options": "",
	role: "group",
	"aria-label": "选择异常巡检分组"
}, Je = [
	"data-sub2api-monitor-group-id",
	"checked",
	"onChange"
], Ye = ["id"], Xe = /* @__PURE__ */ n({
	__name: "ConfigSub2ApiGroups",
	props: {
		id: {},
		label: {},
		value: {},
		actions: {}
	},
	emits: ["change"],
	setup(e, { emit: t }) {
		let n = e, r = t, a = x(() => [...new Set(n.value.split(/[,，\s]+/).filter(Boolean))]), o = x(() => n.actions.states.sub2apiGroups), s = x(() => [...n.actions.sub2apiGroups.value, ...a.value.filter((e) => !n.actions.sub2apiGroups.value.some((t) => t.value === e)).map((e) => ({
			value: e,
			label: `已配置分组（ID ${e}）`
		}))]), l = x(() => `${o.value.error || o.value.text || (o.value.snapshot === null ? "可查询分组后勾选，也可直接填写 ID" : `已查询 ${n.actions.sub2apiGroups.value.length} 个分组`)}；${a.value.length ? `当前选择分组 ID：${a.value.join("、")}` : "当前选择全部分组"}。`);
		function u(e, t) {
			r("change", (t ? [...a.value, e] : a.value.filter((t) => t !== e)).join(","));
		}
		return (t, n) => (i(), D("div", {
			class: "config-sub2api-groups-v2",
			"data-sub2api-monitor-groups": "",
			"aria-busy": o.value.loading
		}, [
			v("input", {
				id: e.id,
				type: "text",
				"data-key": "SUB2API_MONITOR_GROUP_IDS",
				value: e.value,
				placeholder: "例如：17,18；留空扫描全部",
				"aria-label": e.label,
				"aria-describedby": `${e.id}-groups-help ${e.id}-groups-status`,
				autocomplete: "off",
				spellcheck: "false",
				onInput: n[0] ||= (e) => r("change", e.target.value)
			}, null, 40, We),
			v("button", {
				type: "button",
				class: "btn",
				"data-query-sub2api-groups": "",
				disabled: o.value.loading,
				onClick: n[1] ||= (t) => e.actions.querySub2ApiGroups()
			}, g(o.value.loading ? "正在查询…" : "查询分组"), 9, Ge),
			v("p", {
				id: `${e.id}-groups-help`,
				class: "config-setting-short-help-v2"
			}, "使用已保存的 Sub2API 连接查询；可多选，不选时扫描全部分组，修改后点击保存生效。", 8, Ke),
			v("div", qe, [(i(!0), D(m, null, c(s.value, (e) => (i(), D("label", {
				key: e.value,
				class: b(["config-multi-option-v2", { "is-selected": a.value.includes(e.value) }])
			}, [v("input", {
				type: "checkbox",
				"data-sub2api-monitor-group-id": e.value,
				checked: a.value.includes(e.value),
				onChange: (t) => u(e.value, t.target.checked)
			}, null, 40, Je), v("span", null, g(e.label), 1)], 2))), 128))]),
			v("p", {
				id: `${e.id}-groups-status`,
				class: "config-setting-short-help-v2",
				"data-sub2api-monitor-groups-status": "",
				role: "status",
				"aria-live": "polite"
			}, g(l.value), 9, Ye)
		], 8, Ue));
	}
}), Ze = ["data-config-setting"], Qe = { class: "config-vue-field-copy" }, $e = ["for"], et = ["id"], tt = {
	key: 1,
	class: "config-vue-field-status",
	role: "status"
}, nt = { class: "config-vue-field-control" }, rt = { key: 0 }, it = { key: 1 }, at = ["disabled"], ot = {
	key: 1,
	class: "config-vue-composite"
}, st = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid"
], ct = [
	"value",
	"min",
	"step",
	"aria-label",
	"aria-invalid"
], lt = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid",
	"aria-describedby",
	"disabled"
], ut = [
	"value",
	"disabled",
	"title"
], dt = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid",
	"aria-describedby",
	"placeholder"
], ft = [
	"id",
	"data-key",
	"type",
	"role",
	"checked",
	"value",
	"min",
	"max",
	"step",
	"placeholder",
	"aria-label",
	"aria-invalid",
	"aria-describedby"
], pt = ["aria-label"], mt = {
	key: 3,
	class: "hint"
}, ht = {
	key: 4,
	class: "hint",
	role: "status"
}, gt = ["id"], _t = /* @__PURE__ */ n({
	__name: "ConfigField",
	props: {
		owner: {},
		field: {},
		actions: {},
		legacy: { type: Boolean }
	},
	setup(e) {
		let t = e, n = x(() => t.owner.readField(t.field.key)), r = x(() => `config-field-${t.field.key}`), a = x(() => t.owner.fieldErrors[t.field.key] || ""), o = x(() => !!t.field.readonly || t.field.editable === !1 || !!t.field.disable_enable && !n.value), s = x(() => ["PROXY_POOL_COUNTRIES", "PLAN_CHECK_COUNTRIES"].includes(t.field.key)), l = x(() => s.value && !!t.field.country_codes?.length), u = x(() => [
			"PROXY_POOL_DEFAULT_COUNTRY",
			"REGISTRATION_COUNTRY",
			"ACCOUNT_AT_REFRESH_COUNTRY"
		].includes(t.field.key) && !!t.field.country_codes?.length), d = x(() => [
			"EMAIL_SOURCE",
			"ROXY_RANDOM_OS_CHOICES",
			"BROWSER_DATA_SAVER_AUTH_FLOWS",
			"BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES"
		].includes(t.field.key) || t.field.type === "list_str_multiline" && !!(t.field.options?.length || t.field.csv_options?.length)), f = x(() => {
			let e = ["EMAIL_SOURCE", "ROXY_RANDOM_OS_CHOICES"].includes(t.field.key) ? /[,\n]+/ : l.value || d.value ? /[,\n\s]+/ : /\n/, r = (Array.isArray(n.value) ? n.value : String(n.value ?? "").split(e)).map((e) => e.trim()).filter(Boolean), i = s.value ? [...new Set(r.map((e) => e.toUpperCase()))] : r;
			return t.field.key === "EMAIL_SOURCE" && Array.isArray(t.field.options) ? i.filter((e) => G(t.field).some((t) => t.value === e)) : i;
		});
		function h(e) {
			let n = t.field.country_names?.[e];
			try {
				return `${n || new Intl.DisplayNames(["zh-CN"], { type: "region" }).of(e) || e} · ${e}`;
			} catch {
				return n ? `${n} · ${e}` : e;
			}
		}
		let y = x(() => {
			let e = l.value || u.value ? (t.field.country_codes || []).map((e) => ({
				value: e,
				label: h(e)
			})) : G(t.field);
			return !e.length && t.field.csv_options && (e = t.field.csv_options.map((e) => ({
				value: e,
				label: e
			}))), t.field.key === "EXTRACT_LINK_TYPE" && t.actions?.extractTypeOptions.value.length && (e = t.actions.extractTypeOptions.value), t.field.key === "ACCOUNT_LIVE_CHECK_DRIVER" && !t.owner.readField("ACCOUNT_LIVE_CHECK_BROWSER_ENABLED") && (e = e.filter((e) => e.value !== "browser_roxy" || e.disabled)), t.field.key === "ACCOUNT_AT_REFRESH_COUNTRY" && (e = [{
				value: "",
				label: "跟随注册国家"
			}, ...e]), e;
		}), S = x(() => {
			let e = t.field.key === "REGISTRATION_DRIVER" ? ue(n.value) : String(n.value ?? "");
			return y.value.find((t) => t.value.toLowerCase() === e.trim().toLowerCase())?.value ?? e;
		}), C = x(() => {
			let e = y.value, t = S.value;
			return !d.value && !l.value && t && !e.some((e) => e.value === t) ? [{
				value: t,
				label: `当前配置（${t}）`
			}, ...e] : e;
		}), w = x(() => u.value || !!t.field.options?.length || t.field.key === "EXTRACT_LINK_TYPE" && C.value.length > 0), E = x(() => t.owner.readComposite(t.field.key) || (t.field.key === "PROXY_POOL_WAIT_TIMEOUT" ? {
			mode: Number(n.value) > 0 ? "timed" : "continuous",
			raw: Number(n.value) > 0 ? String(n.value) : ""
		} : {
			mode: String(n.value ?? "").trim() ? "limited" : "unlimited",
			raw: String(n.value ?? "")
		})), O = x(() => ["timed", "limited"].includes(E.value.mode));
		function k(e) {
			t.owner.setComposite(t.field.key, {
				mode: e,
				raw: E.value.raw || (["timed", "limited"].includes(e) ? t.field.key === "SMS_MAX_PRICE" ? "0.1" : "60" : "")
			});
		}
		function A(e) {
			t.owner.setField(t.field.key, e), t.field.key === "CODEX_OAUTH_DRIVER" && t.owner.field("ACCOUNT_CODEX_DRIVER") && t.owner.setField("ACCOUNT_CODEX_DRIVER", e);
		}
		function j(e) {
			let n = e.target, r = t.field.type;
			if (r === "bool") A(n.checked);
			else if (r === "list_str_multiline") {
				let e = n.value.split(s.value ? /[,\n\s]+/ : /\n/).map((e) => e.trim()).filter(Boolean);
				A(s.value ? [...new Set(e.map((e) => e.toUpperCase()))] : e);
			} else A(r === "int" || r === "float" ? t.field.group === "并发控制" ? n.value : n.value === "" ? null : Number(n.value) : n.value);
		}
		function M(e) {
			if (t.field.type !== "str" || t.field.secret) return;
			let n = e.target.value.trim();
			A([
				"",
				"-",
				"—",
				"无",
				"空",
				"none",
				"null",
				"n/a",
				"na",
				"未设置",
				"未配置"
			].includes(n.toLowerCase()) ? "" : n);
		}
		function N(e) {
			A(["EMAIL_SOURCE", "ROXY_RANDOM_OS_CHOICES"].includes(t.field.key) ? e.join(",") : e);
		}
		let P = x(() => t.owner.isDirty(t.field.key) ? t.field.secret && t.owner.secretDraft(t.field.key).mode === "clear" ? "待清除" : "待保存" : t.field.invalid_env ? "配置值无效，未生效" : t.field.secret ? t.field.configured ? "密钥已配置" : "未配置" : t.field.restart ? "已配置 · 需重启" : ""), F = x(() => t.field.key === "ACCOUNT_CODEX_DRIVER"), I = [
			"EXTRACT_LINK_HUANGUANG_CDK",
			"EXTRACT_LINK_HUANGUANG_PAYMENT_CDK",
			"EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY",
			"EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"
		];
		return (t, s) => (i(), D("div", {
			class: b(["config-vue-field", { "is-invalid": a.value }]),
			"data-config-setting": e.field.key
		}, [v("div", Qe, [
			v("label", { for: r.value }, g(e.field.label || e.field.key), 9, $e),
			v("code", null, g(e.field.key), 1),
			e.field.help ? (i(), D("p", {
				key: 0,
				id: `${r.value}-help`,
				class: "hint"
			}, g(e.field.help), 9, et)) : p("", !0),
			P.value ? (i(), D("span", tt, g(P.value), 1)) : p("", !0)
		]), v("div", nt, [
			e.legacy ? (i(), D("p", rt, "兼容保留")) : F.value ? (i(), D("p", it, g(T(G)(e.owner.field("CODEX_OAUTH_DRIVER")).find((t) => t.value === e.owner.readField("CODEX_OAUTH_DRIVER"))?.label || e.owner.readField("CODEX_OAUTH_DRIVER")) + " · 由注册主链路统一维护", 1)) : (i(), D("fieldset", {
				key: 2,
				disabled: o.value,
				class: "config-vue-control-group"
			}, [e.field.key === "SUB2API_MONITOR_GROUP_IDS" && e.actions ? (i(), _(Xe, {
				key: 0,
				id: r.value,
				label: e.field.label,
				value: String(n.value ?? ""),
				actions: e.actions,
				onChange: A
			}, null, 8, [
				"id",
				"label",
				"value",
				"actions"
			])) : ["PROXY_POOL_WAIT_TIMEOUT", "SMS_MAX_PRICE"].includes(e.field.key) ? (i(), D("div", ot, [v("select", {
				id: r.value,
				"data-key": e.field.key,
				value: E.value.mode,
				"aria-label": e.field.key === "SMS_MAX_PRICE" ? "价格上限模式" : "领取等待模式",
				"aria-invalid": !!a.value,
				onChange: s[0] ||= (e) => k(e.target.value)
			}, [e.field.key === "PROXY_POOL_WAIT_TIMEOUT" ? (i(), D(m, { key: 0 }, [s[5] ||= v("option", { value: "continuous" }, "持续等待", -1), s[6] ||= v("option", { value: "timed" }, "限时等待", -1)], 64)) : (i(), D(m, { key: 1 }, [s[7] ||= v("option", { value: "unlimited" }, "不设上限", -1), s[8] ||= v("option", { value: "limited" }, "设上限", -1)], 64))], 40, st), O.value ? (i(), D("input", {
				key: 0,
				type: "number",
				value: E.value.raw,
				min: e.field.key === "SMS_MAX_PRICE" ? 0 : 1,
				step: e.field.key === "SMS_MAX_PRICE" ? "0.001" : "1",
				"aria-label": e.field.key === "SMS_MAX_PRICE" ? "短信价格上限" : "限时等待秒数",
				"aria-invalid": !!a.value,
				onInput: s[1] ||= (t) => e.owner.setComposite(e.field.key, {
					mode: E.value.mode,
					raw: t.target.value
				})
			}, null, 40, ct)) : p("", !0)])) : l.value || d.value ? (i(), _(ze, {
				key: 2,
				id: r.value,
				"data-key": e.field.key,
				label: e.field.label,
				country: l.value,
				values: f.value,
				options: C.value,
				"empty-label": e.field.key === "PLAN_CHECK_COUNTRIES" ? "沿用账号注册国家" : e.field.key === "PROXY_POOL_COUNTRIES" ? "未选择额外预热国家" : "未选择",
				onChange: N
			}, null, 8, [
				"id",
				"data-key",
				"label",
				"country",
				"values",
				"options",
				"empty-label"
			])) : w.value ? (i(), D("select", {
				key: 3,
				id: r.value,
				"data-key": e.field.key,
				value: S.value,
				"aria-label": e.field.label,
				"aria-invalid": !!a.value,
				"aria-describedby": `${r.value}-help ${r.value}-error`,
				disabled: C.value.length === 1 || C.value.every((e) => e.disabled),
				onChange: s[2] ||= (e) => A(e.target.value)
			}, [(i(!0), D(m, null, c(C.value, (e) => (i(), D("option", {
				key: e.value,
				value: e.value,
				disabled: e.disabled,
				title: e.reason
			}, g(e.label) + g(e.disabled && e.reason ? `（${e.reason}）` : ""), 9, ut))), 128))], 40, lt)) : e.field.type === "list_str_multiline" ? (i(), D("textarea", {
				key: 4,
				id: r.value,
				"data-key": e.field.key,
				value: f.value.join("\n"),
				"aria-label": e.field.label,
				"aria-invalid": !!a.value,
				"aria-describedby": `${r.value}-help ${r.value}-error`,
				placeholder: e.field.secret ? "留空保留已有值" : "每行一条，可留空",
				onInput: j
			}, null, 40, dt)) : (i(), D("input", {
				key: 5,
				id: r.value,
				"data-key": e.field.key,
				type: e.field.type === "bool" ? "checkbox" : ["int", "float"].includes(e.field.type) ? "number" : e.field.secret ? "password" : "text",
				role: e.field.type === "bool" ? "switch" : void 0,
				checked: !!n.value,
				value: n.value ?? "",
				min: e.field.range?.min ?? e.field.min,
				max: e.field.range?.max ?? e.field.max,
				step: e.field.type === "int" ? "1" : e.field.type === "float" ? "0.1" : void 0,
				placeholder: e.field.secret ? "留空保留已有值" : "可留空",
				autocomplete: "off",
				"aria-label": e.field.label,
				"aria-invalid": !!a.value,
				"aria-describedby": `${r.value}-help ${r.value}-error`,
				onInput: j,
				onChange: M
			}, null, 40, ft)), e.field.secret ? (i(), D("button", {
				key: 6,
				type: "button",
				"aria-label": `明确清除${e.field.label}`,
				onClick: s[3] ||= (t) => e.owner.clearSecret(e.field.key)
			}, "清除", 8, pt)) : p("", !0)], 8, at)),
			F.value ? (i(), D("p", mt, "注册和账号补全共用同一套 Codex OAuth 执行方式，请到注册主链路修改。")) : p("", !0),
			e.field.reason ? (i(), D("p", ht, g(e.field.reason), 1)) : p("", !0),
			a.value ? (i(), D("p", {
				key: 5,
				id: `${r.value}-error`,
				class: "config-vue-error",
				role: "alert"
			}, g(a.value), 9, gt)) : p("", !0),
			e.actions && I.includes(e.field.key) ? (i(), _(He, {
				key: 6,
				actions: e.actions,
				"field-key": e.field.key
			}, null, 8, ["actions", "field-key"])) : p("", !0),
			e.actions && e.field.group === "并发控制" && e.field.key !== "GLOBAL_TASK_WORKERS" ? (i(), D("button", {
				key: 7,
				type: "button",
				onClick: s[4] ||= (t) => e.actions.locateConcurrencyTasks(e.field.key)
			}, "定位任务")) : p("", !0)
		])], 10, Ze));
	}
}), vt = ["data-config-tool", "aria-busy"], yt = { class: "config-tool-controls" }, bt = ["value", "disabled"], xt = ["value"], St = ["value"], Ct = ["disabled"], wt = ["disabled"], Tt = {
	key: 0,
	role: "status"
}, Et = ["disabled"], Dt = ["disabled"], Ot = { class: "config-tool-controls" }, kt = ["disabled"], At = ["disabled"], jt = { class: "config-tool-facts" }, Mt = { class: "config-tool-controls" }, Nt = ["disabled"], Pt = ["disabled"], Ft = { class: "config-tool-controls" }, It = ["disabled"], Lt = ["disabled"], Rt = {
	key: 0,
	class: "hint"
}, zt = {
	key: 1,
	class: "config-migration-preview"
}, Bt = ["disabled"], Vt = ["disabled"], Ht = {
	key: 2,
	class: "config-concurrency-types"
}, Ut = { key: 0 }, Wt = { key: 1 }, Gt = ["onClick"], Kt = { key: 3 }, qt = {
	key: 4,
	role: "status"
}, Jt = /*#__PURE__*/ E(/* @__PURE__ */ n({
	__name: "ConfigActionTools",
	props: {
		owner: {},
		actions: {},
		tool: {},
		active: {
			type: Boolean,
			default: !0
		}
	},
	setup(e) {
		let t = e, n = x(() => t.actions.states[t.tool]), r = x(() => n.value.loading || n.value.posting), o = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {}, s = (e, t = "—") => typeof e == "string" || typeof e == "number" ? String(e) : t, l = (e) => Array.isArray(e) ? e.map(o) : [], u = x(() => `${t.owner.readField("ROXY_WORKSPACE_ID") || ""}::${t.owner.readField("ROXY_PROJECT_ID") || ""}`);
		function d(e) {
			let n = t.actions.roxyWorkspaces.value.find((t) => `${t.id}::${t.projectId}` === e.target.value);
			n && (t.owner.setField("ROXY_WORKSPACE_ID", n.id), t.owner.setField("ROXY_PROJECT_ID", n.projectId));
		}
		function f() {
			return t.actions.saveRoxySelection(String(t.owner.readField("ROXY_WORKSPACE_ID") || ""), String(t.owner.readField("ROXY_PROJECT_ID") || ""));
		}
		let h = x(() => t.actions.roxyWorkspaces.value.some((e) => `${e.id}::${e.projectId}` === u.value)), _ = x(() => t.tool === "roxy" ? ["ROXY_WORKSPACE_ID", "ROXY_PROJECT_ID"].map((e) => t.owner.field(e)).find((e) => e?.readonly || e?.editable === !1) : void 0), S = x(() => _.value ? _.value.reason || "当前部署不可编辑 Roxy 团队与项目。" : ""), C;
		a(() => [t.tool, t.active], ([e, n]) => {
			C && t.actions.setVisible(C, !1), C = e === "sentinel" || e === "concurrency" ? e : void 0, C && t.actions.setVisible(C, n);
		}, { immediate: !0 }), y(() => {
			C && t.actions.setVisible(C, !1);
		});
		let w = x(() => o(n.value.snapshot?.candidate)), E = x(() => o(n.value.snapshot?.builtin)), A = x(() => ({
			not_checked: "尚未检查",
			same: "同当前一致",
			version_changed: "发现新版本",
			content_changed: "同版本内容变化",
			unknown: "暂无法比较"
		})[s(n.value.snapshot?.comparison)] || "暂无法比较"), j = (e) => e === "static_markers_present" ? "通过（未运行验证）" : e === "needs_adaptation" ? "需要适配" : "尚未检查", M = x(() => {
			let e = Number(n.value.snapshot?.last_checked_at);
			return e > 0 && Number.isFinite(e) ? (/* @__PURE__ */ new Date(e * 1e3)).toLocaleString("zh-CN", { hour12: !1 }) : "尚未检查";
		}), N = x(() => l(n.value.snapshot?.types)), P = x(() => [
			"providers",
			"batches",
			"remote_orders"
		].flatMap((e) => l(n.value.snapshot?.[e]).map((e) => ({
			label: s(e.label || e.key || e.id || e.batch_id, "当前"),
			occupied: e.occupied ?? e.active ?? 0,
			limit: e.limit ?? "—"
		})))), F = x(() => t.actions.states.concurrencyPreview), I = (e) => {
			let t = o(e), n = s(t.code || t.reason || e), r = t.occupied != null && t.limit != null ? `（${t.occupied}/${t.limit}）` : "", i = {
				global_capacity: "等待全局空位",
				type_capacity: "等待本类空位",
				batch_capacity: "等待当前批次空位",
				provider_capacity: "等待平台空位",
				account_busy: "账号正由其他任务使用",
				email_busy: "邮箱资源忙碌",
				runtime_not_ready: "执行服务尚未就绪",
				concurrency_policy_migration_required: "等待配置并发迁移策略",
				remote_order_capacity: "等待远端订单名额",
				not_due: "等待下次平台查询",
				fairness_turn: "等待公平调度轮次",
				executor_capacity: "等待执行承载空位",
				resource_capacity: "等待业务资源空位",
				scheduler_store_unavailable: "调度存储暂不可用",
				permit_owner_lost: "执行许可归属已变化",
				execution_active: "上一执行仍在退出或清理"
			};
			return i[n] ? i[n] + r : `调度等待原因未登记（${n || "缺少原因代码"}）`;
		};
		return (t, a) => (i(), D("div", {
			class: "config-tool-panel-v2 config-action-tools",
			"data-config-tool": e.tool,
			"aria-busy": r.value
		}, [e.tool === "roxy" ? (i(), D(m, { key: 0 }, [
			a[12] ||= v("strong", null, "团队 / 项目选择", -1),
			a[13] ||= v("p", { class: "hint" }, "获取已保存连接中的团队与项目，选择后单独保存。", -1),
			v("div", yt, [
				v("label", null, [a[11] ||= O("团队 / 项目", -1), v("select", {
					"aria-label": "团队 / 项目",
					value: u.value,
					disabled: r.value || !!S.value,
					onChange: d
				}, [h.value ? p("", !0) : (i(), D("option", {
					key: 0,
					value: u.value
				}, "当前团队：" + g(e.owner.readField("ROXY_WORKSPACE_ID") || "未设置"), 9, xt)), (i(!0), D(m, null, c(e.actions.roxyWorkspaces.value, (e) => (i(), D("option", {
					key: `${e.id}::${e.projectId}`,
					value: `${e.id}::${e.projectId}`
				}, g(e.label), 9, St))), 128))], 40, bt)]),
				v("button", {
					type: "button",
					class: "btn",
					"data-config-action": "load-roxy",
					disabled: r.value || !!S.value,
					onClick: a[0] ||= (t) => e.actions.loadRoxyWorkspaces()
				}, g(n.value.loading ? "正在获取…" : "获取团队"), 9, Ct),
				v("button", {
					type: "button",
					class: "btn primary",
					"data-config-action": "save-roxy",
					disabled: r.value || !h.value || !!S.value,
					onClick: f
				}, g(n.value.posting ? "正在保存…" : "保存选择"), 9, wt)
			]),
			S.value ? (i(), D("p", Tt, g(S.value), 1)) : p("", !0)
		], 64)) : e.tool === "proxy" ? (i(), D(m, { key: 1 }, [
			a[14] ||= v("strong", null, "代理供应商本地联调", -1),
			a[15] ||= v("p", { class: "hint" }, "会实际提取并检测 1 个 IP，可能产生少量流量或配额消耗。API 请求会绕过系统代理。", -1),
			v("button", {
				type: "button",
				class: "btn",
				"data-config-action": "test-proxy",
				disabled: r.value,
				onClick: a[1] ||= (t) => e.actions.testProxy()
			}, g(r.value ? "正在测试…" : "提取并测试 1 个 IP"), 9, Et)
		], 64)) : e.tool === "butler" ? (i(), D(m, { key: 2 }, [a[16] ||= v("strong", null, "Email Butler 连接与权限", -1), v("button", {
			type: "button",
			class: "btn",
			"data-config-action": "test-butler",
			disabled: r.value,
			onClick: a[2] ||= (t) => e.actions.testButler()
		}, g(r.value ? "正在检测…" : "测试连接与权限"), 9, Dt)], 64)) : e.tool === "sentinel" ? (i(), D(m, { key: 3 }, [
			a[23] ||= v("strong", null, "Sentinel 检查", -1),
			a[24] ||= v("p", { class: "hint" }, "手动获取候选资源；不自动切换现用版本。", -1),
			v("div", Ot, [v("button", {
				type: "button",
				class: "btn",
				"data-config-action": "check-sentinel",
				disabled: r.value || !!n.value.snapshot?.running,
				onClick: a[3] ||= (t) => e.actions.checkSentinel()
			}, g(n.value.posting || n.value.snapshot?.running ? "检查中…" : "检查 Sentinel 更新"), 9, kt), v("button", {
				type: "button",
				class: "btn",
				disabled: r.value,
				onClick: a[4] ||= (t) => e.actions.refreshSentinel()
			}, "刷新状态", 8, At)]),
			v("dl", jt, [
				a[17] ||= v("dt", null, "当前内置版本", -1),
				v("dd", null, g(s(E.value.version, "读取后显示")), 1),
				a[18] ||= v("dt", null, "发现版本", -1),
				v("dd", null, g(s(w.value.version, "尚未发现")), 1),
				a[19] ||= v("dt", null, "上次检查时间", -1),
				v("dd", null, g(M.value), 1),
				a[20] ||= v("dt", null, "版本比较", -1),
				v("dd", null, g(A.value), 1),
				a[21] ||= v("dt", null, "generic 静态检查", -1),
				v("dd", null, g(j(w.value.generic_status)), 1),
				a[22] ||= v("dt", null, "Proto2 静态检查", -1),
				v("dd", null, g(j(w.value.proto2_status)), 1)
			])
		], 64)) : e.tool === "sub2api" ? (i(), D(m, { key: 4 }, [
			a[25] ||= v("strong", null, "同步与异常巡检", -1),
			a[26] ||= v("p", { class: "hint" }, "使用已保存配置检查远端异常账号，修复进度可在任务中心查看。", -1),
			v("div", Mt, [v("button", {
				type: "button",
				class: "btn",
				disabled: r.value,
				onClick: a[5] ||= (t) => e.actions.refreshSub2Api()
			}, "查看状态", 8, Nt), v("button", {
				type: "button",
				class: "btn",
				"data-config-action": "check-sub2api",
				disabled: r.value,
				onClick: a[6] ||= (t) => e.actions.checkSub2Api()
			}, "立即巡检", 8, Pt)])
		], 64)) : e.tool === "concurrency" ? (i(), D(m, { key: 5 }, [
			a[27] ||= v("strong", null, "并发运行状态", -1),
			v("div", Ft, [v("button", {
				type: "button",
				class: "btn",
				disabled: r.value,
				onClick: a[7] ||= (t) => e.actions.refreshConcurrency()
			}, "刷新状态", 8, It), v("button", {
				type: "button",
				class: "btn",
				disabled: r.value,
				onClick: a[8] ||= (t) => e.actions.refreshConcurrency({ details: !0 })
			}, "查看附加限制", 8, Lt)]),
			n.value.snapshot ? (i(), D("p", Rt, "部署范围 " + g(s(o(n.value.snapshot.scope).label || n.value.snapshot.scope, "当前部署")) + " · 策略版本 " + g(s(n.value.snapshot.policy_revision)) + " · 观察时间 " + g(T(k)(n.value.snapshot.observed_at)), 1)) : p("", !0),
			a[28] ||= v("p", { class: "config-section-v2-subhelp" }, "各类型上限是上限，不预留配额，合计可以超过全局。内部同步刷新 AT、查套餐与后处理归属巡检、提链或注册父任务，复用父任务许可；独立子任务按实际动作重新排队。", -1),
			F.value.snapshot?.migration_required || n.value.snapshot?.migration_required ? (i(), D("div", zt, [
				v("p", null, "新策略需要完整保存。历史账号池上限：" + g(s(F.value.snapshot?.legacy_account_workers, "未记录")), 1),
				(i(!0), D(m, null, c(Array.isArray(F.value.snapshot?.notes) ? F.value.snapshot.notes : [], (e, t) => (i(), D("p", { key: t }, g(s(e, "")), 1))), 128)),
				v("button", {
					type: "button",
					class: "btn",
					disabled: !F.value.snapshot,
					onClick: a[9] ||= (t) => e.actions.applyConcurrencyPreview()
				}, "填入迁移建议", 8, Bt),
				F.value.error ? (i(), D("button", {
					key: 0,
					type: "button",
					class: "btn",
					disabled: F.value.loading,
					onClick: a[10] ||= (t) => e.actions.loadConcurrencyPreview()
				}, "重试迁移预览", 8, Vt)) : p("", !0)
			])) : p("", !0),
			N.value.length ? (i(), D("ul", Ht, [(i(!0), D(m, null, c(N.value, (t) => (i(), D("li", { key: s(t.key) }, [v("div", null, [
				v("strong", null, g(s(t.label || t.key)), 1),
				v("span", null, "占用 " + g(t.occupied ?? 0) + " / " + g(t.limit ?? "—") + " · 排队 " + g(t.queued ?? 0) + g(t.draining ? " · 等待现有任务结束" : ""), 1),
				Number(e.owner.readField(s(t.config_key))) > Number(o(n.value.snapshot?.global).limit) ? (i(), D("small", Ut, "当前实际最多受全局 " + g(o(n.value.snapshot?.global).limit) + " 限制；保存后的类型值仍会保留。", 1)) : p("", !0),
				Array.isArray(t.blocked_by) && t.blocked_by.length ? (i(), D("small", Wt, g(t.blocked_by.map(I).join("；")), 1)) : p("", !0)
			]), v("button", {
				type: "button",
				class: "btn",
				onClick: (n) => e.actions.locateConcurrencyTasks(s(t.config_key || t.key))
			}, "定位任务", 8, Gt)]))), 128))])) : p("", !0),
			P.value.length ? (i(), D("ul", Kt, [(i(!0), D(m, null, c(P.value, (e, t) => (i(), D("li", { key: t }, g(e.label) + "：" + g(e.occupied) + " / " + g(e.limit), 1))), 128))])) : p("", !0),
			a[29] ||= v("details", { class: "config-concurrency-details-v2" }, [
				v("summary", null, "业务附加限制与计量说明"),
				v("p", { class: "hint" }, "注册批次并发填写正整数，提链批次与平台保留 1–50；它们与全局、类型限制同时生效。XXSYUN 未结束订单名额在远端等待时仍占用，本地查询间隔不占执行槽。调试保留、停止清理和已预约执行仍计入占用。"),
				v("p", { class: "hint" }, "账号补全等待独立子任务时不重复占全局槽；HME 合并扫描按一个扫描 Run 计数；邮箱导入按实际远端交接调用计数。Sub2API 远端账号并发属性在服务集成中维护。")
			], -1),
			F.value.text || F.value.error ? (i(), D("p", qt, g(F.value.error || F.value.text), 1)) : p("", !0)
		], 64)) : p("", !0), v("p", {
			class: b(["config-action-status", { "config-action-error": n.value.error }]),
			role: "status",
			"aria-live": "polite"
		}, g(n.value.error || n.value.text || (r.value ? "正在请求…" : "尚未查询")), 3)], 8, vt));
	}
}), [["__scopeId", "data-v-ecc7ba70"]]), Yt = {
	class: "config-vue-overview",
	"aria-label": "当前配置概览"
}, Xt = {
	key: 0,
	role: "status"
}, Zt = {
	key: 1,
	class: "config-vue-error",
	role: "alert"
}, Qt = {
	key: 2,
	class: "config-vue-error",
	role: "status"
}, $t = {
	key: 3,
	class: "config-vue-error-summary",
	role: "alert",
	tabindex: "-1"
}, en = ["onClick"], tn = { class: "config-vue-layout" }, nn = { class: "config-vue-content" }, rn = ["aria-label"], an = [
	"data-config-domain-v2",
	"aria-pressed",
	"onClick"
], on = ["data-config-section"], sn = ["aria-label"], cn = [
	"data-config-subsection",
	"aria-pressed",
	"onClick"
], ln = {
	key: 1,
	class: "config-vue-pool-rules"
}, un = {
	key: 2,
	class: "config-vue-field"
}, dn = ["open"], fn = { key: 0 }, pn = {
	key: 5,
	class: "hint"
}, mn = {
	key: 6,
	class: "hint"
}, hn = {
	key: 4,
	class: "config-vue-savebar"
}, gn = {
	role: "status",
	"aria-live": "polite"
}, _n = { key: 0 }, vn = { key: 1 }, yn = { key: 2 }, bn = { key: 3 }, xn = ["disabled"], Sn = ["disabled"], Cn = /* @__PURE__ */ n({
	__name: "ConfigPage",
	props: {
		owner: {},
		actions: {},
		active: {
			type: Boolean,
			default: !0
		}
	},
	setup(e, { expose: n }) {
		let r = e, o = h(""), s = u({
			menu: "",
			domain: "",
			section: ""
		}), f = h(), b = {}, S = {}, C = x(() => le(s.menu, r.owner.fields.value)), w = x(() => me(s.domain, r.owner.fields.value)), E = x(() => ye(r.owner, s, !!o.value.trim())), k = x(() => xe(s.domain, E.value)), A = /* @__PURE__ */ new Set([
			"PROXY_POOL_SOURCE",
			"PROXY_POOL_DEFAULT_COUNTRY",
			"PROXY_POOL",
			...["PROXY_1024_", "PROXY_711_"].flatMap((e) => [
				"API_URL",
				"PROTOCOL",
				"SESSION_MINUTES"
			].map((t) => `${e}${t}`))
		]), j = x(() => E.value.filter((e) => A.has(e.key))), M = x(() => E.value.filter((e) => !A.has(e.key))), N = x(() => de(r.owner.fields.value)), F = x(() => N.value.filter((e) => r.owner.readField(e.enabledKey) === !0).map((e) => e.value)), I = x(() => Object.entries(r.owner.fieldErrors)), L = x(() => s.domain === "RoxyBrowser" ? "roxy" : s.domain === "代理与网络" && s.section === "代理来源" && r.owner.readField("PROXY_POOL_SOURCE") !== "manual" ? "proxy" : s.domain === "邮箱 / OTP" && s.section === "Email Butler" ? "butler" : s.domain === "通用配置" ? "sentinel" : s.domain === "Codex" && s.section === "sub2api" ? "sub2api" : s.domain === "并发控制" ? "concurrency" : null);
		function R() {
			try {
				localStorage.setItem(ie, s.domain || s.menu);
			} catch {}
		}
		function z() {
			t(() => {
				let e = f.value?.querySelector("main"), t = !!(e?.scrollTop || e?.scrollLeft || window.scrollY || window.scrollX || document.documentElement.scrollTop);
				e && (e.scrollTop = 0, e.scrollLeft = 0), t && window.scrollTo({
					top: 0,
					left: 0,
					behavior: "auto"
				});
			});
		}
		function B(e) {
			let t = he(e, r.owner.fields.value);
			P[e] && b[t.menu] && (t.domain = b[t.menu]), t.section = S[t.domain] || me(t.domain, r.owner.fields.value)[0] || "", Object.assign(s, t), R(), z();
		}
		function ee(e) {
			s.domain = e, b[s.menu] = e, s.section = S[e] || me(e, r.owner.fields.value)[0] || "", R(), z();
		}
		function te(e) {
			s.section = e, S[s.domain] = e, z();
		}
		function ne(e) {
			o.value = e;
			let t = ve(e, r.owner.fields.value, s.menu);
			t && Object.assign(s, t);
		}
		function re(e) {
			for (let t of N.value) r.owner.setField(t.enabledKey, e.includes(t.value));
		}
		async function V(e) {
			let n = r.owner.field(e);
			if (!n) return;
			o.value.trim() && !_e(n, r.owner.fields.value).includes(o.value.trim().toLowerCase()) && (o.value = ""), Object.assign(s, ge(n, r.owner.fields.value)), R(), await t();
			let i = Array.from(f.value?.querySelectorAll("[data-config-setting]") || []).find((t) => t.dataset.configSetting === e);
			i?.querySelectorAll("details").forEach((e) => e.open = !0);
			let a = i?.closest("details");
			a && (a.open = !0);
			let c = i?.querySelector("input:not([type=hidden]),select,textarea,summary,button");
			c?.focus(), c?.scrollIntoView?.({ block: "nearest" });
		}
		function ae() {
			r.owner.dirtyCount.value && window.confirm("确定撤销全部未保存的配置修改？") && r.owner.reset();
		}
		function oe(e) {
			r.owner.dirtyCount.value && (e.preventDefault(), e.returnValue = "");
		}
		async function se() {
			let e = await r.owner.saveAll();
			if (e.status === "validation-error") {
				let t = Object.keys(e.fields || {})[0];
				t && r.owner.navigateField(t);
			}
		}
		function H(e) {
			let t = r.owner.readField(e);
			return t == null || t === "" ? "—" : G(r.owner.field(e)).find((e) => e.value === t)?.label || (Array.isArray(t) ? t.join("、") : String(t));
		}
		a(() => r.owner.navigationTarget.value, (e) => {
			e && V(e.key);
		}), a(() => r.active, (e) => r.actions.setPageActive(e), { immediate: !0 }), y(() => {
			r.actions.setPageActive(!1), window.removeEventListener("beforeunload", oe);
		}), a(() => r.owner.fields.value, () => {
			let e = ce(r.owner.fields.value);
			if (e.length) {
				if (!s.menu) {
					let t = "";
					try {
						t = localStorage.getItem("gpt_console_config_group") || "";
					} catch {}
					Object.assign(s, he(t || e[0], r.owner.fields.value));
				}
				e.includes(s.menu) || Object.assign(s, he(e[0], r.owner.fields.value)), C.value.includes(s.domain) || (s.domain = C.value[0] || s.menu), w.value.includes(s.section) || (s.section = w.value[0] || "");
			}
		}, { immediate: !0 }), l(() => {
			window.addEventListener("beforeunload", oe), r.owner.initialize().catch(() => {}), r.actions.loadExtractTypes();
		}), n({
			open: B,
			focusField: V
		});
		let U = [
			[
				"注册与账号认证",
				"注册主链路的注册国家；账号认证沿用账号历史国家",
				"独占租约"
			],
			[
				"查询套餐",
				"业务国家顺序（逐国申请）",
				"按池用途策略复用"
			],
			[
				"查活",
				"账号历史国家；缺失时使用池默认国家",
				"认证链路保持同一线路"
			],
			[
				"刷新 AT",
				"优先使用独立的 AT 刷新国家；留空时跟随账号注册国家",
				"单次登录保持同线；网络故障换线重新登录"
			],
			[
				"补密码 / 2FA / 换绑 / Codex",
				"账号历史国家；缺失时使用池默认国家",
				"独占租约"
			]
		];
		return (t, n) => (i(), D("div", {
			ref_key: "root",
			ref: f,
			class: "config-vue-page"
		}, [
			v("div", Yt, [
				v("span", null, [n[1] ||= O("注册主链路 ", -1), v("strong", null, g(T(ue)(e.owner.readField("REGISTRATION_DRIVER"))), 1)]),
				v("span", null, [n[2] ||= O("邮箱来源 ", -1), v("strong", null, g(H("EMAIL_SOURCE")), 1)]),
				v("span", null, [
					n[3] ||= O("Codex OAuth ", -1),
					v("strong", null, g(H("CODEX_OAUTH_DRIVER")), 1),
					v("small", null, "自动授权：" + g(e.owner.readField("ENABLE_CODEX_AUTO") ? "已开启" : "已关闭"), 1)
				]),
				v("span", null, [n[4] ||= O("代理模式 ", -1), v("strong", null, g(H("REGISTRATION_PROXY_MODE")), 1)])
			]),
			e.owner.loading.value ? (i(), D("p", Xt, "正在读取配置…")) : p("", !0),
			e.owner.error.value ? (i(), D("p", Zt, g(e.owner.error.value), 1)) : p("", !0),
			e.owner.refreshError.value ? (i(), D("p", Qt, [O(g(e.owner.refreshError.value) + " ", 1), v("button", {
				type: "button",
				onClick: n[0] ||= (t) => e.owner.refresh({ force: !0 })
			}, "重新读取配置")])) : p("", !0),
			I.value.length ? (i(), D("div", $t, [v("strong", null, "请检查 " + g(I.value.length) + " 项配置，草稿已保留", 1), v("ul", null, [(i(!0), D(m, null, c(I.value, ([t, n]) => (i(), D("li", { key: t }, [v("button", {
				type: "button",
				onClick: (n) => e.owner.navigateField(t)
			}, g(e.owner.field(t)?.label || t) + "：" + g(n), 9, en)]))), 128))])])) : p("", !0),
			v("div", tn, [d(ke, {
				owner: e.owner,
				active: s.menu,
				query: o.value,
				onSelect: B,
				onSearch: ne
			}, null, 8, [
				"owner",
				"active",
				"query"
			]), v("main", nn, [v("div", {
				class: "config-vue-tabs",
				role: "group",
				"aria-label": `${s.menu}配置领域`
			}, [(i(!0), D(m, null, c(C.value, (e) => (i(), D("button", {
				key: e,
				type: "button",
				"data-config-domain-v2": e,
				"aria-pressed": s.domain === e,
				onClick: (t) => ee(e)
			}, g(e === "注册与账号" ? "查询套餐" : e), 9, an))), 128))], 8, rn), v("section", { "data-config-section": s.domain }, [
				v("h2", null, g(s.domain === "注册与账号" ? "查询套餐" : s.domain), 1),
				w.value.length ? (i(), D("div", {
					key: 0,
					class: "config-vue-tabs",
					role: "group",
					"aria-label": `${s.domain}配置分类`
				}, [(i(!0), D(m, null, c(w.value, (e) => (i(), D("button", {
					key: e,
					type: "button",
					"data-config-subsection": e,
					"aria-pressed": s.section === e,
					onClick: (t) => te(e)
				}, g(e), 9, cn))), 128))], 8, sn)) : p("", !0),
				s.domain === "代理与网络" && s.section === "任务用池" ? (i(), D("table", ln, [
					n[5] ||= v("caption", null, "任务用池规则", -1),
					n[6] ||= v("thead", null, [v("tr", null, [
						v("th", null, "任务"),
						v("th", null, "国家需求"),
						v("th", null, "领取规则")
					])], -1),
					v("tbody", null, [(i(), D(m, null, c(U, (e) => v("tr", { key: e[0] }, [(i(!0), D(m, null, c(e, (e) => (i(), D("td", { key: e }, g(e), 1))), 128))])), 64))])
				])) : p("", !0),
				s.domain === "提链" && s.section === "通用配置" ? (i(), D("div", un, [n[7] ||= v("div", { class: "config-vue-field-copy" }, [v("label", null, "启用平台"), v("p", { class: "hint" }, "选择允许在提链工作台中使用的平台；取消选择不会清除该平台的地址或 CDK。")], -1), d(ze, {
					label: "启用平台",
					values: F.value,
					options: N.value,
					onChange: re
				}, null, 8, ["values", "options"])])) : p("", !0),
				s.domain === "代理与网络" && s.section === "代理来源" ? (i(), D(m, { key: 3 }, [(i(!0), D(m, null, c(j.value, (t) => (i(), _(_t, {
					key: t.key,
					owner: e.owner,
					field: t,
					actions: e.actions
				}, null, 8, [
					"owner",
					"field",
					"actions"
				]))), 128)), M.value.length ? (i(), D("details", {
					key: 0,
					class: "config-vue-source-advanced",
					open: !!o.value.trim()
				}, [n[8] ||= v("summary", null, "高级提取与检测参数", -1), (i(!0), D(m, null, c(M.value, (t) => (i(), _(_t, {
					key: t.key,
					owner: e.owner,
					field: t,
					actions: e.actions
				}, null, 8, [
					"owner",
					"field",
					"actions"
				]))), 128))], 8, dn)) : p("", !0)], 64)) : (i(!0), D(m, { key: 4 }, c(k.value, (t) => (i(), D("div", {
					key: t.title,
					class: "config-vue-setting-group"
				}, [t.title ? (i(), D("h3", fn, g(t.title), 1)) : p("", !0), (i(!0), D(m, null, c(t.fields, (t) => (i(), _(_t, {
					key: t.key,
					owner: e.owner,
					field: t,
					actions: e.actions,
					legacy: s.domain === "代理与网络" && s.section === "高级兼容"
				}, null, 8, [
					"owner",
					"field",
					"actions",
					"legacy"
				]))), 128))]))), 128)),
				s.domain === "邮箱 / OTP" && s.section === "iCloud 隐藏邮箱" ? (i(), D("p", pn, "隐藏邮箱的创建、状态与管理请在邮箱服务（Email Butler）中完成。本页只维护已导入与历史邮箱的固定收件连接。")) : p("", !0),
				s.domain === "注册调试" ? (i(), D("p", mn, "“调试模式”仍是单个注册批次的现场保留开关，本页只控制失败诊断、保留时长和抓包预算。")) : p("", !0),
				L.value ? (i(), _(Jt, {
					key: L.value,
					owner: e.owner,
					actions: e.actions,
					tool: L.value,
					active: e.active
				}, null, 8, [
					"owner",
					"actions",
					"tool",
					"active"
				])) : p("", !0)
			], 8, on)])]),
			e.owner.dirtyCount.value || e.owner.receipt.value ? (i(), D("div", hn, [
				v("div", gn, [
					v("strong", null, g(I.value.length ? "请检查标记的配置项" : e.owner.error.value ? "保存失败，请重试" : e.owner.dirtyCount.value ? `${e.owner.dirtyCount.value} 项待保存` : "配置已保存"), 1),
					I.value.length ? (i(), D("span", _n, "请检查标记的配置项后再保存")) : e.owner.error.value ? (i(), D("span", vn, "请检查网络或服务状态后重试")) : p("", !0),
					e.owner.receipt.value ? (i(), D("span", yn, "数据库保存" + g(e.owner.receipt.value.persistedDbRevision === null ? "成功" : `版本 ${e.owner.receipt.value.persistedDbRevision}`) + " · Worker " + g(e.owner.receipt.value.workerApplication.state === "applied" ? "已应用" : e.owner.receipt.value.workerApplication.state === "error" ? "应用异常" : e.owner.receipt.value.workerApplication.state === "pending" ? "等待应用" : "应用状态待确认"), 1)) : p("", !0),
					e.owner.receipt.value?.restartRequired.length ? (i(), D("span", bn, "需重启：" + g(e.owner.receipt.value.restartRequired.join("、")), 1)) : p("", !0)
				]),
				v("button", {
					type: "button",
					disabled: !e.owner.dirtyCount.value || e.owner.saving.value,
					onClick: ae
				}, "撤销修改", 8, xn),
				v("button", {
					type: "button",
					class: "primary",
					disabled: !e.owner.dirtyCount.value || e.owner.saving.value,
					onClick: se
				}, g(e.owner.saving.value ? "正在保存…" : "保存全部配置"), 9, Sn)
			])) : p("", !0)
		], 512));
	}
}), K = class extends Error {
	status;
	code;
	fields;
	constructor(e, t, n = "", r = {}) {
		super(e), this.status = t, this.code = n, this.fields = r, this.name = "ConfigApiError";
	}
}, q = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {}, wn = (e) => JSON.parse(JSON.stringify(e));
function Tn(e) {
	if (!Array.isArray(e)) throw new K("配置字段响应格式无效", 0, "config_schema_invalid");
	let t = /* @__PURE__ */ new Set();
	return e.map((e) => {
		let n = q(e);
		if (typeof n.key != "string" || !n.key || typeof n.type != "string" || t.has(n.key)) throw new K("配置字段响应格式无效", 0, "config_schema_invalid");
		t.add(n.key);
		let r = wn({
			...n,
			group: String(n.group || "其他"),
			label: String(n.label || n.key)
		});
		return r.secret && (r.value = "", "configured_value" in r && (r.configured_value = ""), "published_effective_value" in r && (r.published_effective_value = ""), delete r.default), r;
	});
}
function En(e = fetch) {
	let t = 0, n = null, r = null;
	async function i(t, n) {
		let r = await e(t, {
			credentials: "same-origin",
			...n
		});
		if (!(r.headers.get("content-type") || "").includes("application/json")) throw new K(r.status === 401 || r.redirected ? "登录已失效，请重新登录后刷新。" : "配置接口返回了非 JSON 响应", r.status);
		let i;
		try {
			i = await r.json();
		} catch {
			throw new K("配置接口返回了无效 JSON", r.status);
		}
		let a = q(i);
		if (!r.ok || a.ok === !1) {
			let e = q(a.error), t = {};
			for (let [n, r] of Object.entries(q(a.fields || e.fields))) typeof r == "string" && (t[n] = r);
			throw new K(typeof a.error == "string" ? a.error : String(e.message || a.message || `请求失败（HTTP ${r.status}）`), r.status, String(e.code || a.code || a.error_code || ""), t);
		}
		return i;
	}
	function a() {
		t++, n = null, r = null;
	}
	return {
		async getSchema(e = {}) {
			if (e.signal?.aborted) throw new DOMException("读取已取消", "AbortError");
			if (r?.generation === t) return wn(await r.promise);
			if (!e.force && n && Date.now() - n.at < 3e4) return wn(n.fields);
			let a = t, o = i("/api/config", { signal: e.signal }).then((e) => {
				let r = Tn(e);
				return t === a && (n = {
					fields: r,
					at: Date.now()
				}), r;
			});
			r = {
				generation: a,
				promise: o
			};
			try {
				return wn(await o);
			} finally {
				r?.promise === o && (r = null);
			}
		},
		async save(e) {
			let t = await i("/api/config", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ updates: e })
			});
			if (!t || typeof t != "object" || Array.isArray(t) || !Array.isArray(q(t).updated) || !q(t).updated.every((e) => typeof e == "string")) throw new K("配置保存响应格式无效", 0, "config_save_response_invalid");
			return a(), t;
		},
		invalidate: a
	};
}
// src/features/config/configState.ts
function Dn(e, t) {
	let n = e.ignored || [];
	return {
		savedKeys: [...e.updated ?? t.filter((e) => !n.includes(e))],
		ignoredKeys: [...n],
		persistedDbRevision: e.persisted_db_revision ?? null,
		localSnapshotRevision: e.local_snapshot_revision ?? e.config_revision ?? null,
		webReloaded: e.web_reloaded ?? e.reloaded ?? null,
		workerApplication: e.worker_application ? { ...e.worker_application } : {
			state: "unknown",
			applied_db_revision: null
		},
		restartRequired: [...e.restart_required || []],
		refreshFailed: !1
	};
}
function On(e, t) {
	let n = {}, r = new Map(t.map((e) => [e.key, e]));
	for (let [t, i] of Object.entries(e)) {
		let e = r.get(t);
		if (e?.group === "并发控制" && e.type === "int" && t !== "CONCURRENCY_POLICY_REVISION") {
			let e = String(i ?? "").trim();
			/^\d+$/.test(e) && /[1-9]/.test(e) || (n[t] = "请填写不小于 1 的整数；暂停请使用任务暂停或取消。");
		}
	}
	return n;
}
// src/features/config/useConfigDraft.ts
var J = (e) => e === void 0 ? e : JSON.parse(JSON.stringify(e)), kn = (e, t) => JSON.stringify(e) === JSON.stringify(t);
function An(t) {
	let n = C(Tn(t.initialFields || [])), r = u({}), i = u({}), a = h(!1), o = h(!1), s = h(""), c = h(""), l = h(null), d = h(null), f = /* @__PURE__ */ new Map(), p = /* @__PURE__ */ new Set(), m = /* @__PURE__ */ new Set(), g = !1, _ = 0, v = 0, y = null, b = /* @__PURE__ */ new Set(), S = x(() => new Map(n.value.map((e) => [e.key, e]))), w = x(() => Object.keys(r)), T = x(() => w.value.length), E = (e) => S.value.get(e), D = (e) => {
		let t = (f.get(e) || 0) + 1;
		return f.set(e, t), t;
	};
	function O(e, t = "effective") {
		return J(t === "effective" && r[e] ? r[e].value : E(e)?.value);
	}
	function k(e) {
		let t = E(e);
		if (!t) throw Error(`未知配置字段：${e}`);
		return t;
	}
	function A(e) {
		return J(r[e]?.secret || { mode: "retain" });
	}
	function j(e, t) {
		if (g) return;
		let n = k(e);
		if (!n.secret) throw Error(`字段不是密钥：${e}`);
		let a = D(e);
		if (n.group !== "并发控制" && Object.keys(i).forEach((e) => delete i[e]), delete i[e], t.mode === "retain") {
			delete r[e];
			return;
		}
		let o = t.mode === "clear" ? n.type === "list_str_multiline" ? [] : "" : J(t.value);
		r[e] = {
			value: o,
			generation: a,
			secret: J(t)
		};
	}
	function M(e, t, n = {}) {
		if (g) return;
		let a = k(e);
		if (a.group !== "并发控制" && Object.keys(i).forEach((e) => delete i[e]), a.secret) {
			j(e, t === null || typeof t == "string" && t.trim() === "" || Array.isArray(t) && !t.length ? { mode: "retain" } : {
				mode: "set",
				value: J(t)
			});
			return;
		}
		let o = D(e);
		delete i[e];
		let s = !!n.force || !!r[e]?.forced;
		!s && !b.has(e) && kn(t, a.value) ? delete r[e] : r[e] = {
			value: J(t),
			generation: o,
			forced: s
		};
	}
	function N(e, t) {
		if (g) return;
		k(e);
		let n;
		n = e === "PROXY_POOL_WAIT_TIMEOUT" ? t.mode === "timed" ? t.raw.trim() === "" ? null : Number(t.raw) : 0 : e === "SMS_MAX_PRICE" ? t.mode === "limited" ? t.raw : "" : t.raw;
		let a = D(e);
		k(e).group !== "并发控制" && Object.keys(i).forEach((e) => delete i[e]), delete i[e], r[e] = {
			value: n,
			generation: a,
			composite: J(t)
		};
	}
	function P(e = w.value) {
		for (let t of e) D(t), delete r[t], delete i[t];
		s.value = "";
	}
	function F(e) {
		d.value = {
			key: e,
			generation: ++v
		}, t.onNavigateField?.(e);
	}
	async function I(e = {}) {
		if (g) return;
		let r = ++_, i = new AbortController();
		m.add(i), a.value = !0;
		try {
			let a = await t.api.getSchema({
				...e,
				signal: i.signal
			});
			if (g || r !== _ || i.signal.aborted) return;
			n.value = Tn(a), c.value = "";
		} catch (e) {
			if (!g && r === _ && !i.signal.aborted) throw c.value = "配置读取失败，当前草稿已保留", e;
		} finally {
			m.delete(i), r === _ && (a.value = !1);
		}
	}
	async function L() {
		if (!(g || n.value.length)) return y ||= I().finally(() => {
			y = null;
		}), y;
	}
	function R(e) {
		let i = {
			...On(e, n.value),
			...t.validate?.(e, n.value)
		};
		for (let t of Object.keys(e)) {
			let e = r[t]?.composite;
			e && (t === "PROXY_POOL_WAIT_TIMEOUT" && e.mode === "timed" && (!e.raw.trim() || !Number.isFinite(Number(e.raw)) || Number(e.raw) <= 0) && (i[t] = "请填写限时等待秒数，或切换为持续等待"), t === "SMS_MAX_PRICE" && e.mode === "limited" && (!e.raw.trim() || !Number.isFinite(Number(e.raw)) || Number(e.raw) < 0) && (i[t] = "请填写短信价格上限，或切换为不设上限"));
		}
		return i;
	}
	function z(e) {
		Object.assign(i, e);
		let t = Object.keys(e)[0];
		t && F(t);
	}
	async function B(e) {
		if (g) return { status: "disposed" };
		if (o.value) return { status: "busy" };
		let a = /* @__PURE__ */ new Map(), c = {};
		for (let t of e) r[t] && (a.set(t, J(r[t])), c[t] = J(r[t].value));
		if (!a.size) return { status: "noop" };
		let u = R(c);
		if (Object.keys(u).length) return z(u), {
			status: "validation-error",
			fields: u
		};
		o.value = !0, s.value = "", b = new Set(a.keys());
		try {
			let e = await t.api.save(c);
			if (g) return { status: "disposed" };
			_++;
			let o = Dn(e, [...a.keys()]), s = new Set(o.savedKeys);
			n.value = n.value.map((e) => {
				let t = a.get(e.key);
				return !t || !s.has(e.key) ? e : e.secret ? {
					...e,
					value: "",
					configured: t.secret?.mode !== "clear",
					configured_value: "",
					published_effective_value: ""
				} : {
					...e,
					value: J(t.value),
					configured_value: J(t.value)
				};
			});
			for (let [e, t] of a) s.has(e) && f.get(e) === t.generation && (delete r[e], delete i[e]);
			t.api.invalidate(), l.value = o;
			try {
				await I({ force: !0 });
			} catch {
				o.refreshFailed = !0, l.value = { ...o };
			}
			if (!g) {
				let e = {
					keys: o.savedKeys,
					receipt: J(o),
					fields: J(n.value)
				};
				for (let t of p) try {
					t(e);
				} catch {}
			}
			return {
				status: "saved",
				receipt: J(o)
			};
		} catch (e) {
			if (g) return { status: "disposed" };
			let t = e instanceof K ? e.fields : {};
			if (Object.keys(t).length) {
				let e = Object.fromEntries(Object.entries(t).filter(([e]) => {
					let t = a.get(e);
					return !t || f.get(e) === t.generation;
				}));
				return z(e), {
					status: "validation-error",
					fields: J(e)
				};
			}
			return s.value = e instanceof K ? e.message : "配置保存失败，草稿已保留", { status: "error" };
		} finally {
			o.value = !1, b = /* @__PURE__ */ new Set();
		}
	}
	async function ee(e) {
		if (g) return { status: "disposed" };
		if (o.value) return { status: "busy" };
		if (Array.isArray(e)) return B(e);
		for (let [t, n] of Object.entries(e)) M(t, n, { force: !0 });
		return B(Object.keys(e));
	}
	function te() {
		g = !0, _++;
		for (let e of m) e.abort();
		m.clear(), p.clear();
		for (let e of Object.keys(r)) delete r[e];
		a.value = !1;
	}
	return {
		fields: n,
		dirtyKeys: w,
		dirtyCount: T,
		fieldErrors: e(i),
		loading: a,
		saving: o,
		error: s,
		refreshError: c,
		receipt: l,
		navigationTarget: d,
		field: E,
		readField: O,
		isDirty: (e) => !!r[e],
		secretDraft: A,
		readComposite: (e) => J(r[e]?.composite),
		setField: M,
		setSecret: j,
		clearSecret: (e) => j(e, { mode: "clear" }),
		setComposite: N,
		reset: P,
		initialize: L,
		refresh: I,
		saveAll: () => B(w.value),
		saveSubset: ee,
		navigateField: F,
		subscribeSaved(e) {
			return p.add(e), () => p.delete(e);
		},
		dispose: te
	};
}
// src/features/config/configActions.ts
var jn = [
	"extractTypes",
	"roxy",
	"proxy",
	"butler",
	"huanguangExtraction",
	"huanguangPayment",
	"huanguangXxsyun",
	"xxsyunBalance",
	"sentinel",
	"sub2api",
	"concurrency",
	"concurrencyPreview",
	"sub2apiGroups"
], Mn = {
	roxy: ["ROXY_API_BASE", "ROXY_API_TOKEN"],
	proxy: [
		"PROXY_POOL_SOURCE",
		"PROXY_POOL_DEFAULT_COUNTRY",
		"PROXY_1024_API_URL",
		"PROXY_1024_PROTOCOL",
		"PROXY_1024_SESSION_MINUTES",
		"PROXY_1024_VALIDATE",
		"PROXY_711_API_URL",
		"PROXY_711_PROTOCOL",
		"PROXY_711_SESSION_MINUTES"
	],
	butler: ["EMAIL_BUTLER_API_BASE", "EMAIL_BUTLER_API_KEY"],
	huanguangExtraction: ["EXTRACT_LINK_HUANGUANG_CDK", "EXTRACT_LINK_HUANGUANG_API_BASE"],
	huanguangPayment: ["EXTRACT_LINK_HUANGUANG_PAYMENT_CDK", "EXTRACT_LINK_HUANGUANG_API_BASE"],
	huanguangXxsyun: ["EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY", "EXTRACT_LINK_HUANGUANG_API_BASE"],
	xxsyunBalance: ["EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY", "EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE"]
};
function Y(e) {
	return e && typeof e == "object" && !Array.isArray(e) ? e : {};
}
function X(e, t = "") {
	return typeof e == "string" || typeof e == "number" ? String(e).slice(0, 1e3) : t;
}
function Nn(e) {
	return typeof e == "string" ? e.trim() : "";
}
function Z(e) {
	return Array.isArray(e) ? e : [];
}
function Pn(e) {
	return typeof e == "number" && Number.isFinite(e) && e >= 0;
}
function Q(e) {
	return Number.isSafeInteger(e) && Number(e) >= 0;
}
function Fn() {
	throw { code: "invalid_response" };
}
function $(e) {
	return {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(e)
	};
}
function In(e, t = !1, n = "CDK") {
	let r = X(Y(e).code || Y(e).error_code).toLowerCase();
	return {
		key_missing: "未配置 XXSYUN API Key，请填写后重试",
		api_key_missing: "未配置 XXSYUN API Key，请填写后重试",
		key_invalid: "XXSYUN API Key 无效或已失效，请更新后重试",
		api_key_invalid: "XXSYUN API Key 无效或已失效，请更新后重试",
		unauthorized: "XXSYUN API Key 无效或已失效，请更新后重试",
		unauthenticated: "XXSYUN API Key 无效或已失效，请更新后重试",
		forbidden: "当前 XXSYUN API Key 无权查询积分",
		cdk_invalid: `${n} 无效或已失效，请更新并保存后重试`,
		cdk_missing: `未配置${n}，请填写并保存后重试`,
		config_invalid: "查询配置无效，请检查服务地址并保存后重试",
		network_error: "查询遇到网络连接异常，请稍后重试",
		transport_error: "查询遇到网络连接异常，请稍后重试",
		upstream_http_error: "上游服务暂时无法完成查询，请稍后重试",
		rate_limited: "查询过于频繁，请稍后重试",
		invalid_response: t ? "XXSYUN 积分响应无效，请稍后重试" : "上游查询响应无效，请稍后重试",
		request_timeout: "查询超时，请稍后重试",
		employer_pending: "XXSYUN 平台账号尚未就绪，请在平台检查账号状态",
		password_change_required: "XXSYUN 平台要求先修改密码，请在平台处理后重试",
		insufficient_quota: "XXSYUN 积分不足，请在平台检查积分余额"
	}[r] || (t ? "查询积分失败，请检查 XXSYUN 配置或稍后重试" : "查询失败，请稍后重试");
}
function Ln(e, t = {}) {
	let n = t.request || ((e, t) => A(e, t, N)), r = u(Object.fromEntries(jn.map((e) => [e, {
		loading: !1,
		posting: !1,
		text: "",
		error: "",
		snapshot: null,
		receipt: null
	}]))), i = Object.fromEntries(jn.map((e) => [e, 0])), o = /* @__PURE__ */ new Map(), s = /* @__PURE__ */ new Map(), c = {
		sentinel: !1,
		concurrency: !1
	}, l = /* @__PURE__ */ new Map(), d = !0, f = !0, p = !1, m = [], h = (t, n = "") => e.readField(t) ?? n;
	function g(t) {
		let n = e.secretDraft(t);
		return n.mode === "set" ? Nn(n.value) : n.mode === "clear" ? "" : Nn(h(t));
	}
	function _(t) {
		let n = e.secretDraft(t);
		return n.mode === "clear" ? { api_key: "" } : n.mode === "set" ? { api_key: Nn(n.value) } : e.isDirty(t) ? { api_key: Nn(h(t)) } : {};
	}
	function v(e) {
		let t = l.get(e);
		t !== void 0 && clearTimeout(t), l.delete(e);
	}
	function y(e, t = !1) {
		i[e]++;
		let n = o.get(e);
		n?.posting || n?.controller?.abort(), r[e].loading = !1, r[e].posting = !1, r[e].error = "", r[e].text = "", t || (r[e].snapshot = null, r[e].receipt = null);
	}
	for (let [t, n] of Object.entries(Mn)) m.push(a(() => n.map((t) => [
		e.readField(t),
		e.isDirty(t),
		e.secretDraft(t)
	]), () => y(t), {
		deep: !0,
		flush: "sync"
	}));
	m.push(e.subscribeSaved((t) => {
		for (let [e, n] of Object.entries(Mn)) n.some((e) => t.keys.includes(e)) && y(e);
		t.keys.some((e) => [
			"SUB2API_API_BASE",
			"SUB2API_API_KEY",
			"SUB2API_API_TIMEOUT"
		].includes(e)) && y("sub2apiGroups"), t.keys.some((t) => e.field(t)?.group === "并发控制") && y("concurrencyPreview");
	}));
	function b(e, n) {
		if (e.accepted !== !0) return null;
		let r = {
			accepted: !0,
			task_id: j(e.task_id)
		};
		e.run_id != null && (r.run_id = M(e.run_id));
		try {
			t.onTaskReceipt?.(r, n);
		} catch {}
		return r;
	}
	function S(e) {
		v(e), !p && d && f && c[e] && !r[e].loading && !r[e].posting && (e !== "sentinel" || r.sentinel.snapshot?.running && !r.sentinel.error) && l.set(e, setTimeout(() => {
			l.delete(e), e === "sentinel" ? R() : V();
		}, e === "sentinel" ? 1500 : 3e3));
	}
	function C(e, t, a, c) {
		if (p) return Promise.resolve();
		let l = c.posting && [
			"sentinel",
			"sub2api",
			"proxy"
		].includes(e), u = l ? s.get(e) : void 0;
		if (u) return u;
		let d = o.get(e);
		if (d?.generation === i[e] || d?.posting && c.posting && [
			"sentinel",
			"sub2api",
			"proxy"
		].includes(e)) return d.promise;
		let f = ++i[e], m = c.posting ? void 0 : new AbortController();
		r[e].loading = !c.posting, r[e].posting = !!c.posting, r[e].error = "", (e === "sentinel" || e === "concurrency") && v(e);
		let h = () => !p && i[e] === f, g = (async () => {
			try {
				if (d && await d.promise, !h()) return;
				let i = Y(await Promise.resolve().then(() => n(t, {
					...a,
					...m ? { signal: m.signal } : {}
				})));
				if (i.ok === !1) throw i;
				let o = c.label ? b(i, c.label) : null;
				if (!h()) return;
				r[e].receipt = o, c.apply(i, o);
			} catch (t) {
				if (!h()) return;
				r[e].error = c.error?.(t) || "请求未完成，请稍后重试。", r[e].text = r[e].error;
			} finally {
				l && s.delete(e), o.get(e)?.generation === f && o.delete(e), h() && (r[e].loading = !1, r[e].posting = !1, (e === "sentinel" || e === "concurrency") && S(e));
			}
		})();
		return o.set(e, {
			generation: f,
			promise: g,
			controller: m,
			posting: !!c.posting
		}), l && s.set(e, g), g;
	}
	function w(e, t) {
		return r[e].text = t, r[e].error = "", Promise.resolve();
	}
	function T() {
		return C("extractTypes", "/api/extract-link/types", { method: "GET" }, {
			apply: (e) => {
				let t = /* @__PURE__ */ new Set(), n = [];
				for (let r of Z(e.items)) {
					let e = Y(r), i = X(e.type).trim().toLowerCase();
					i && !t.has(i) && e.visible !== !1 && e.enabled !== !1 && (t.add(i), n.push({
						value: i,
						label: X(e.label, i) || i
					}));
				}
				n.length || Fn(), r.extractTypes.snapshot = { options: n };
			},
			error: () => "提链类型读取失败，保留当前选择。"
		});
	}
	function E() {
		return C("roxy", "/api/roxy/workspaces", { method: "GET" }, {
			apply: (e) => {
				let t = Z(e.items).map((e) => {
					let t = Y(e);
					return {
						id: X(t.id),
						projectId: X(t.projectId),
						label: X(t.label) || `${X(t.name)} (${X(t.id)})`
					};
				}).filter((e) => e.id);
				t.length || Fn(), r.roxy.snapshot = { items: t }, r.roxy.text = `已获取 ${t.length} 个团队/项目`;
			},
			error: () => "获取团队/项目失败，请检查已保存的 Roxy 连接配置后重试。"
		});
	}
	async function D(t, n) {
		if (!(p || !t || r.roxy.posting || r.roxy.loading)) {
			r.roxy.posting = !0;
			try {
				let i = await e.saveSubset({
					ROXY_WORKSPACE_ID: t,
					ROXY_PROJECT_ID: n
				});
				return p || (r.roxy.text = i.status === "saved" ? "Roxy 团队/项目已保存。" : i.status === "busy" ? "配置正在保存，请稍后重试。" : "保存未完成，请检查配置反馈。"), i;
			} catch {
				p || (r.roxy.error = "保存未完成，请稍后重试。");
			} finally {
				p || (r.roxy.posting = !1);
			}
		}
	}
	function O() {
		let e = X(h("PROXY_POOL_SOURCE")), t = e === "1024proxy" ? "PROXY_1024_" : e === "711proxy" ? "PROXY_711_" : "";
		return t ? C("proxy", "/api/proxy-provider/test", $({
			provider: e,
			api_url: h(`${t}API_URL`),
			region: h("PROXY_POOL_DEFAULT_COUNTRY", "JP"),
			protocol: h(`${t}PROTOCOL`, "http"),
			session_minutes: h(`${t}SESSION_MINUTES`, 30),
			...e === "1024proxy" ? { validate: h("PROXY_1024_VALIDATE", !0) } : {}
		}), {
			posting: !0,
			label: "代理提取测试",
			apply: (t, n) => {
				if (n) {
					r.proxy.text = `测试已入队 · 任务 #${n.task_id}`;
					return;
				}
				let i = Y(t.lease), a = X(i.endpoint, "—").replace(/\/\/[^/]*@/, "//").replace(/^[^/]*@/, "");
				r.proxy.snapshot = {
					provider: X(i.provider, e),
					endpoint: a,
					exit_ip: X(i.exit_ip, "—"),
					region: X(i.region, "—"),
					expires_at: X(i.expires_at, "—")
				}, r.proxy.text = `测试成功 · ${X(i.provider, e)} · ${a} · 出口 ${X(i.exit_ip, "—")} · ${X(i.region, "—")} · 有效至 ${X(i.expires_at, "—")}`;
			},
			error: () => "代理提取测试失败，请检查供应商配置后重试。"
		}) : w("proxy", "请选择支持提取测试的代理供应商。");
	}
	function k() {
		return C("butler", "/api/email-butler/test-connection", $({
			api_base: Nn(h("EMAIL_BUTLER_API_BASE")),
			api_key: g("EMAIL_BUTLER_API_KEY")
		}), {
			posting: !0,
			apply: (e) => {
				let t = Z(e.missing_permissions).map((e) => X(e)).filter(Boolean);
				r.butler.snapshot = {
					name: X(e.name, "Email Butler"),
					consumer: X(e.consumer),
					service: X(e.service),
					missing_permissions: t
				};
				let n = [X(e.consumer), X(e.service)].filter(Boolean).join(" / ") || "未绑定策略";
				r.butler.text = t.length ? `连接成功，权限尚未齐全：${t.join("、")}。请在 Butler 为原客户端补充权限。` : `连接成功：${X(e.name, "Email Butler")} · ${n}`;
			},
			error: () => "Email Butler 连接失败，请检查地址和客户端权限后重试。"
		});
	}
	function P(t) {
		let n = t === "extraction" ? "huanguangExtraction" : "huanguangPayment", i = t === "extraction" ? "EXTRACT_LINK_HUANGUANG_CDK" : "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK";
		return e.isDirty(i) || e.isDirty("EXTRACT_LINK_HUANGUANG_API_BASE") ? w(n, "请先保存此 CDK 或服务地址的更改，再查询剩余次数") : C(n, `/api/extract-link/huanguang/cdk-quota/${t}`, { method: "GET" }, {
			apply: (e) => {
				let t = Y(e.quota);
				(typeof t.required != "boolean" || !(t.remaining === null || Q(t.remaining)) || !(t.reserved === null || Q(t.reserved)) || t.active !== null && typeof t.active != "boolean") && Fn(), r[n].snapshot = {
					required: t.required,
					remaining: t.remaining,
					reserved: t.reserved,
					active: t.active
				}, r[n].text = t.required ? `剩余 ${t.remaining ?? "未知"} 次 · 占用 ${t.reserved ?? "未知"} · ${t.active === !1 ? "已停用" : t.active === !0 ? "已启用" : "可用状态未知"}` : "平台免计次";
			},
			error: (e) => In(e, !1, t === "extraction" ? "幻光提链 CDK" : "幻光支付扫码 CDK")
		});
	}
	function F() {
		return e.isDirty("EXTRACT_LINK_HUANGUANG_API_BASE") ? w("huanguangXxsyun", "请先保存服务地址的更改，再查询剩余次数") : C("huanguangXxsyun", "/api/extract-link/huanguang/xxsyun-quota", $(_("EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY")), {
			posting: !0,
			apply: (e) => {
				Q(e.remainingUses) && (e.totalUses == null || Q(e.totalUses)) && (e.reservedUses == null || Q(e.reservedUses)) || Fn(), r.huanguangXxsyun.snapshot = {
					remainingUses: e.remainingUses,
					totalUses: e.totalUses ?? null,
					reservedUses: e.reservedUses ?? null
				}, r.huanguangXxsyun.text = `剩余 ${e.remainingUses} 次 · 总次数 ${e.totalUses ?? "未知"} · 占用 ${e.reservedUses ?? "未知"}`;
			},
			error: (e) => In(e)
		});
	}
	function I() {
		return e.isDirty("EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE") ? w("xxsyunBalance", "请先保存服务地址的更改，再查询积分") : C("xxsyunBalance", "/api/extract-link/payments/xxsyun/balance", $(_("EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY")), {
			posting: !0,
			apply: (e) => {
				let t = Y(e.balance), n = [
					"available_points",
					"pending_points",
					"used_points",
					"cost_points"
				];
				e.balance && !Array.isArray(e.balance) && n.every((e) => t[e] == null || Pn(t[e])) || Fn(), r.xxsyunBalance.snapshot = Object.fromEntries(n.map((e) => [e, t[e] ?? null]));
				let i = (e) => e == null ? "未知" : `${e} 积分`;
				r.xxsyunBalance.text = `可用 ${i(t.available_points)} · 预占 ${i(t.pending_points)} · 已用 ${i(t.used_points)} · 每单 ${i(t.cost_points)}`;
			},
			error: (e) => In(e, !0)
		});
	}
	function L(e) {
		return e && r.sentinel.snapshot?.running ? Promise.resolve() : C("sentinel", e ? "/api/maintenance/sentinel/check" : "/api/maintenance/sentinel", e ? $({}) : { method: "GET" }, {
			posting: e,
			label: e ? "Sentinel 检查" : void 0,
			apply: (e, t) => {
				let n = r.sentinel.snapshot;
				r.sentinel.snapshot = {
					...e,
					candidate: e.candidate || n?.candidate || null,
					comparison: !e.candidate && n?.candidate ? n.comparison : e.comparison
				}, r.sentinel.text = t ? `检查已入队 · 任务 #${t.task_id}` : e.running ? "正在检查 Sentinel 更新…" : "已读取 Sentinel 检查状态。", !e.running && (["failed", "corrupt"].includes(X(e.last_status)) || e.error_code) && (r.sentinel.error = e.last_status === "corrupt" ? "候选资源不可用，请重试。" : "检查失败，请重试。");
			},
			error: () => e ? "检查请求未完成，请重试。" : "状态读取失败，请重试。"
		});
	}
	function R() {
		return L(!1);
	}
	function z() {
		return L(!0);
	}
	function B(e) {
		return C("sub2api", e ? "/api/sub2api/automation/check" : "/api/sub2api/automation", e ? $({}) : { method: "GET" }, {
			posting: e,
			label: e ? "Sub2API 异常扫描" : void 0,
			apply: (t, n) => {
				if (r.sub2api.snapshot = t, n) r.sub2api.text = `异常扫描已入队 · 任务 #${n.task_id}，最终结果在任务回执中更新。`;
				else if (e) {
					let e = Y(t.result), n = {
						account_busy: "账号忙碌",
						cooldown: "冷却中",
						account_archived: "账号已归档",
						account_deactivated: "账号已停用",
						automatic_login_material_missing: "自动登录资料不足",
						unrecognized_remote_error: "远端错误原因未识别",
						remote_transient_error: "远端网络或限流错误",
						needs_reconciliation: "上次请求结果待核实",
						repair_in_progress: "修复进行中"
					}, i = Object.entries(Y(e.reasons)).filter(([, e]) => Q(e)).map(([e, t]) => `${n[e] || "其他原因"} ${t}`).join("，");
					r.sub2api.text = `本轮检查 ${e.remote_errors ?? 0} 条异常记录，已调度同步 ${e.sync_queued ?? 0}、刷新 ${e.refresh_queued ?? 0}、重授权 ${e.reauth_queued ?? 0}。${i ? `处理说明：${i}。` : ""}`;
				} else {
					let e = Y(t.sync), n = Y(t.monitor), i = Y(e.counts), a = Z(n.group_ids).map((e) => X(e)).filter(Boolean), o = a.length ? `分组 ID ${a.join("、")}` : "全部分组";
					r.sub2api.text = `自动补传${e.enabled ? "已开启" : "已关闭"}；异常巡检${n.enabled ? "已开启" : "已关闭"}；巡检范围：${o}。待同步 ${i.pending ?? 0}，排队 ${i.queued ?? 0}，执行 ${i.running ?? 0}。`;
				}
			},
			error: () => "Sub2API 状态或巡检请求未完成，请稍后重试。"
		});
	}
	function ee() {
		return C("sub2apiGroups", "/api/sub2api/groups", { method: "GET" }, {
			apply: (e) => {
				if (e.ok !== !0 || !Array.isArray(e.groups) || e.groups.some((e) => {
					let t = Y(e);
					return !Number.isSafeInteger(t.id) || Number(t.id) <= 0 || typeof t.name != "string";
				})) throw Error("分组响应格式无效，请重试");
				let t = [...new Map(e.groups.map((e) => {
					let t = Y(e);
					return [t.id, t];
				})).values()];
				r.sub2apiGroups.snapshot = { options: t.map((e) => ({
					value: String(e.id),
					label: `${e.name}（ID ${e.id}）`
				})) }, r.sub2apiGroups.text = `已查询 ${t.length} 个分组`;
			},
			error: (e) => {
				let t = e instanceof Error ? e.message : X(Y(e).error);
				return t === "分组响应格式无效，请重试" ? t : `查询分组失败：${t || "请检查已保存的连接配置后重试"}`;
			}
		});
	}
	function te() {
		return B(!1);
	}
	function ne() {
		return B(!0);
	}
	function re() {
		return C("concurrencyPreview", "/api/config/concurrency-preview", { method: "GET" }, {
			apply: (e) => {
				r.concurrencyPreview.snapshot = e;
			},
			error: () => "迁移预览暂不可用，请刷新重试。"
		});
	}
	async function V(e = {}) {
		let t = r.concurrencyPreview.snapshot ? Promise.resolve() : re();
		await Promise.all([t, C("concurrency", `/api/operations/concurrency${e.details ? "?details=1" : ""}`, { method: "GET" }, {
			apply: (e) => {
				r.concurrency.snapshot = e;
				let t = Y(e.global);
				r.concurrency.text = `当前占用 ${t.occupied ?? 0} / ${t.limit ?? "—"}${t.draining ? "，等待现有任务结束" : ""}；预约 ${t.reserved ?? 0} · 执行 ${t.executing ?? 0} · 清理 ${t.cleaning ?? 0} · 调试保留 ${t.debug_hold ?? 0}；排队 ${e.queued ?? 0} · 远端等待 ${e.remote_waiting ?? "—"}`;
			},
			error: () => "状态读取失败，请重试；显示的数据为上次观察结果。"
		})]);
	}
	function ie() {
		if (p) return [];
		let t = [];
		for (let [n, i] of Object.entries(Y(r.concurrencyPreview.snapshot?.proposed_values))) {
			let r = e.field(n);
			!r || r.group !== "并发控制" || r.type !== "int" || e.isDirty(n) || !Q(i) || Number(i) <= 0 || (e.setField(n, Number(i), { force: !0 }), t.push(n));
		}
		return r.concurrencyPreview.text = "迁移建议已填入草稿；核对全局和各类型上限后点击保存。", t;
	}
	function ae(e) {
		if (p) return;
		if (e.startsWith("REGISTRATION_")) {
			t.onNavigateTasks?.({ registration: !0 });
			return;
		}
		let n = Z(r.concurrency.snapshot?.types).map(Y).find((t) => t.config_key === e || t.key === e), i = n ? Z(n.task_types).length ? Z(n.task_types).map((e) => X(e)) : [X(n.key)] : [];
		t.onNavigateTasks?.({ types: [...new Set(i.filter(Boolean))] });
	}
	function oe(e, t) {
		p || c[e] === t || (c[e] = t, t ? d && f && (e === "sentinel" ? R() : V()) : (v(e), y(e, !0), e === "concurrency" && y("concurrencyPreview", !0)));
	}
	function se(e) {
		if (!(p || d === e)) {
			d = e;
			for (let t of ["sentinel", "concurrency"]) v(t), e ? f && c[t] && (t === "sentinel" ? R() : V()) : (y(t, !0), t === "concurrency" && y("concurrencyPreview", !0));
		}
	}
	function H(e) {
		if (!(p || f === e)) {
			if (f = e, v("sentinel"), v("concurrency"), e) d && (c.sentinel && R(), c.concurrency && V());
			else for (let e of jn) y(e, !0);
		}
	}
	function U() {
		if (!p) {
			p = !0, m.forEach((e) => e()), v("sentinel"), v("concurrency");
			for (let e of jn) y(e, !0);
		}
	}
	return {
		states: r,
		sub2apiGroups: x(() => r.sub2apiGroups.snapshot?.options || []),
		querySub2ApiGroups: ee,
		extractTypeOptions: x(() => r.extractTypes.snapshot?.options || []),
		roxyWorkspaces: x(() => r.roxy.snapshot?.items || []),
		loadExtractTypes: T,
		loadRoxyWorkspaces: E,
		saveRoxySelection: D,
		testProxy: O,
		testButler: k,
		queryHuanguangQuota: P,
		queryHuanguangXxsyun: F,
		queryXxsyunBalance: I,
		refreshSentinel: R,
		checkSentinel: z,
		refreshSub2Api: te,
		checkSub2Api: ne,
		refreshConcurrency: V,
		loadConcurrencyPreview: re,
		applyConcurrencyPreview: ie,
		locateConcurrencyTasks: ae,
		setVisible: oe,
		setForeground: se,
		setPageActive: H,
		dispose: U
	};
}
// src/features/config/useConfigActions.ts
function Rn(e, t = {}) {
	let n = Ln(e, t), r = () => n.setForeground(!document.hidden);
	return typeof document < "u" && (r(), document.addEventListener("visibilitychange", r)), f(() => {
		typeof document < "u" && document.removeEventListener("visibilitychange", r), n.dispose();
	}), n;
}
// src/config.ts
function zn(e, t) {
	let n = An({ api: En() }), i = o(), s = i.run(() => Rn(n, {
		onTaskReceipt: t.onTaskReceipt,
		onNavigateTasks: t.onNavigateTasks
	})), c = h(t.visible !== !1), l = null, u = a(n.fields, (e) => t.onSavedFields(e), { immediate: !0 }), d = n.subscribeSaved(() => t.onSaved?.()), f = S({ render: () => r(Cn, {
		owner: n,
		actions: s,
		active: c.value,
		ref: (e) => {
			l = e;
		}
	}) });
	return f.mount(e), {
		load: () => n.initialize(),
		refresh: () => n.refresh({ force: !0 }),
		open: (e) => l?.open(e),
		setVisible: (e) => {
			c.value = e, s.setPageActive(e);
		},
		destroy: () => {
			u(), d(), f.unmount(), i.stop(), n.dispose();
		}
	};
}
export { zn as mountConfig };
