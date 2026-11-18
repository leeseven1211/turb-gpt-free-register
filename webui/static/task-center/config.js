import { $ as e, A as t, G as n, I as r, P as i, Q as a, S as o, T as s, V as c, X as l, Z as u, _ as d, a as f, b as p, ct as m, dt as h, g, h as _, j as v, k as y, m as b, n as x, ot as S, p as C, q as w, t as T, tt as E, u as D, x as O } from "./_plugin-vue_export-helper-C1AvIlVn.js";
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
var V = new Map(R), re = new Set(I), ie = "gpt_console_config_group", ae = {
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
	return re.has(e.key) ? "注册与账号" : V.get(e.key) || e.group || "其他";
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
}, ke = /* @__PURE__ */ o({
	__name: "ConfigNavigation",
	props: {
		owner: {},
		active: {},
		query: {}
	},
	emits: ["select", "search"],
	setup(e, { emit: t }) {
		let n = e, a = t, o = C(() => ce(n.owner.fields.value).map((e) => {
			let t = W(n.owner.fields.value).filter((t) => U(t.group) === e);
			return {
				name: e,
				category: Se(e),
				count: t.length,
				dirty: t.filter((e) => n.owner.isDirty(e.key)).length,
				matches: !n.query.trim() || e.toLowerCase().includes(n.query.toLowerCase()) || t.some((e) => _e(e, n.owner.fields.value).includes(n.query.trim().toLowerCase()))
			};
		}));
		return (t, n) => (i(), d("nav", Ce, [
			n[1] ||= b("label", { for: "config-vue-search" }, "搜索配置", -1),
			b("input", {
				id: "config-vue-search",
				type: "search",
				value: e.query,
				placeholder: "名称、配置键或帮助",
				onInput: n[0] ||= (e) => a("search", e.target.value)
			}, null, 40, we),
			(i(), d(D, null, r([
				"业务流程",
				"资源与服务",
				"系统"
			], (t) => b("div", {
				key: t,
				class: "config-vue-nav-group"
			}, [o.value.some((e) => e.category === t && e.matches) ? (i(), d("p", Te, h(t), 1)) : g("", !0), (i(!0), d(D, null, r(o.value.filter((e) => e.category === t && e.matches), (t) => (i(), d("button", {
				key: t.name,
				type: "button",
				"data-config-nav": t.name,
				"aria-current": e.active === t.name ? "page" : void 0,
				onClick: (e) => a("select", t.name)
			}, [b("span", null, h(t.name), 1), b("small", null, [p(h(t.count) + " 项", 1), t.dirty ? (i(), d("span", De, " · " + h(t.dirty) + " 待保存", 1)) : g("", !0)])], 8, Ee))), 128))])), 64)),
			o.value.some((e) => e.matches) ? g("", !0) : (i(), d("p", Oe, "未找到匹配配置"))
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
}, ze = /* @__PURE__ */ o({
	__name: "ConfigChoicePicker",
	props: {
		label: {},
		values: {},
		options: {},
		country: { type: Boolean },
		emptyLabel: { default: "未选择" }
	},
	emits: ["change"],
	setup(t, { emit: a }) {
		let o = t, s = a, c = e(""), l = e(), u = C(() => [...o.values.filter((e) => !o.options.some((t) => t.value === e)).map((e) => ({
			value: e,
			label: `当前值（${e}）`
		})), ...o.options]), m = C(() => u.value.filter((e) => `${e.value} ${e.label}`.toLowerCase().includes(c.value.trim().toLowerCase()))), _ = C(() => o.values.map((e) => u.value.find((t) => t.value === e)?.label || e).join("、") || o.emptyLabel);
		function v(e) {
			s("change", o.values.includes(e) ? o.values.filter((t) => t !== e) : [...o.values, e]);
		}
		function y(e) {
			if (e.key === "Escape") {
				l.value && (l.value.open = !1, l.value.querySelector("summary")?.focus());
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
			let t = Array.from(l.value?.querySelectorAll("[data-choice]") || []), n = t.indexOf(e.target);
			n < 0 || !t.length || (e.preventDefault(), t[e.key === "Home" ? 0 : e.key === "End" ? t.length - 1 : (n + (["ArrowUp", "ArrowLeft"].includes(e.key) ? -1 : 1) + t.length) % t.length]?.focus());
		}
		return (e, a) => (i(), d("details", {
			ref_key: "root",
			ref: l,
			class: "config-vue-picker",
			onKeydown: y
		}, [b("summary", {
			"aria-label": `${t.label}：${_.value}`,
			title: _.value
		}, h(_.value), 9, Ae), b("div", je, [
			n(b("input", {
				"onUpdate:modelValue": a[0] ||= (e) => c.value = e,
				type: "search",
				"aria-label": `搜索${t.label}`,
				placeholder: "搜索并选择"
			}, null, 8, Me), [[f, c.value]]),
			t.country ? (i(), d("div", Ne, [(i(!0), d(D, null, r(t.values, (e) => (i(), d("button", {
				key: e,
				type: "button",
				"aria-label": `移除 ${e}`,
				onClick: (t) => v(e)
			}, h(u.value.find((t) => t.value === e)?.label || e) + " ×", 9, Pe))), 128))])) : g("", !0),
			b("div", {
				class: "config-vue-picker-options",
				"aria-label": t.label,
				role: "group"
			}, [(i(!0), d(D, null, r(m.value, (e) => (i(), d("button", {
				key: e.value,
				type: "button",
				"data-choice": "",
				disabled: e.disabled,
				"aria-pressed": t.values.includes(e.value),
				title: e.reason,
				onClick: (t) => v(e.value)
			}, [b("span", Le, h(t.values.includes(e.value) ? "✓" : "○"), 1), p(" " + h(e.label), 1)], 8, Ie))), 128))], 8, Fe),
			m.value.length ? g("", !0) : (i(), d("p", Re, "未找到匹配选项"))
		])], 544));
	}
}), Be = ["aria-busy"], Ve = [
	"aria-label",
	"disabled",
	"data-config-field-action"
], He = /*#__PURE__*/ T(/* @__PURE__ */ o({
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
		}, r = C(() => n[t.fieldKey]), a = C(() => r.value ? t.actions.states[r.value.name] : null);
		return (t, n) => r.value && a.value ? (i(), d("div", {
			key: 0,
			class: "config-field-actions",
			"aria-busy": a.value.loading || a.value.posting
		}, [b("button", {
			type: "button",
			class: "btn",
			"aria-label": r.value.accessibleLabel,
			disabled: a.value.loading || a.value.posting,
			"data-config-field-action": e.fieldKey,
			onClick: n[0] ||= (e) => r.value.run()
		}, h(a.value.loading || a.value.posting ? "正在查询…" : r.value.label), 9, Ve), b("p", {
			class: m(["config-setting-short-help-v2", { "config-action-error": a.value.error }]),
			role: "status",
			"aria-live": "polite"
		}, h(a.value.error || a.value.text), 3)], 8, Be)) : g("", !0);
	}
}), [["__scopeId", "data-v-667794e0"]]), Ue = ["data-config-setting"], We = { class: "config-vue-field-copy" }, Ge = ["for"], Ke = ["id"], qe = {
	key: 1,
	class: "config-vue-field-status",
	role: "status"
}, Je = { class: "config-vue-field-control" }, Ye = { key: 0 }, Xe = { key: 1 }, Ze = ["disabled"], Qe = {
	key: 0,
	class: "config-vue-composite"
}, $e = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid"
], et = [
	"value",
	"min",
	"step",
	"aria-label",
	"aria-invalid"
], tt = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid",
	"aria-describedby",
	"disabled"
], nt = [
	"value",
	"disabled",
	"title"
], rt = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid",
	"aria-describedby",
	"placeholder"
], it = [
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
], at = ["aria-label"], ot = {
	key: 3,
	class: "hint"
}, st = {
	key: 4,
	class: "hint",
	role: "status"
}, ct = ["id"], lt = /* @__PURE__ */ o({
	__name: "ConfigField",
	props: {
		owner: {},
		field: {},
		actions: {},
		legacy: { type: Boolean }
	},
	setup(e) {
		let t = e, n = C(() => t.owner.readField(t.field.key)), a = C(() => `config-field-${t.field.key}`), o = C(() => t.owner.fieldErrors[t.field.key] || ""), s = C(() => !!t.field.readonly || t.field.editable === !1 || !!t.field.disable_enable && !n.value), c = C(() => ["PROXY_POOL_COUNTRIES", "PLAN_CHECK_COUNTRIES"].includes(t.field.key)), l = C(() => c.value && !!t.field.country_codes?.length), u = C(() => [
			"PROXY_POOL_DEFAULT_COUNTRY",
			"REGISTRATION_COUNTRY",
			"ACCOUNT_AT_REFRESH_COUNTRY"
		].includes(t.field.key) && !!t.field.country_codes?.length), f = C(() => [
			"EMAIL_SOURCE",
			"ROXY_RANDOM_OS_CHOICES",
			"BROWSER_DATA_SAVER_AUTH_FLOWS",
			"BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES"
		].includes(t.field.key) || t.field.type === "list_str_multiline" && !!(t.field.options?.length || t.field.csv_options?.length)), p = C(() => {
			let e = ["EMAIL_SOURCE", "ROXY_RANDOM_OS_CHOICES"].includes(t.field.key) ? /[,\n]+/ : l.value || f.value ? /[,\n\s]+/ : /\n/, r = (Array.isArray(n.value) ? n.value : String(n.value ?? "").split(e)).map((e) => e.trim()).filter(Boolean), i = c.value ? [...new Set(r.map((e) => e.toUpperCase()))] : r;
			return t.field.key === "EMAIL_SOURCE" && Array.isArray(t.field.options) ? i.filter((e) => G(t.field).some((t) => t.value === e)) : i;
		});
		function v(e) {
			let n = t.field.country_names?.[e];
			try {
				return `${n || new Intl.DisplayNames(["zh-CN"], { type: "region" }).of(e) || e} · ${e}`;
			} catch {
				return n ? `${n} · ${e}` : e;
			}
		}
		let y = C(() => {
			let e = l.value || u.value ? (t.field.country_codes || []).map((e) => ({
				value: e,
				label: v(e)
			})) : G(t.field);
			return !e.length && t.field.csv_options && (e = t.field.csv_options.map((e) => ({
				value: e,
				label: e
			}))), t.field.key === "EXTRACT_LINK_TYPE" && t.actions?.extractTypeOptions.value.length && (e = t.actions.extractTypeOptions.value), t.field.key === "ACCOUNT_LIVE_CHECK_DRIVER" && !t.owner.readField("ACCOUNT_LIVE_CHECK_BROWSER_ENABLED") && (e = e.filter((e) => e.value !== "browser_roxy" || e.disabled)), t.field.key === "ACCOUNT_AT_REFRESH_COUNTRY" && (e = [{
				value: "",
				label: "跟随注册国家"
			}, ...e]), e;
		}), x = C(() => {
			let e = t.field.key === "REGISTRATION_DRIVER" ? ue(n.value) : String(n.value ?? "");
			return y.value.find((t) => t.value.toLowerCase() === e.trim().toLowerCase())?.value ?? e;
		}), w = C(() => {
			let e = y.value, t = x.value;
			return !f.value && !l.value && t && !e.some((e) => e.value === t) ? [{
				value: t,
				label: `当前配置（${t}）`
			}, ...e] : e;
		}), T = C(() => u.value || !!t.field.options?.length || t.field.key === "EXTRACT_LINK_TYPE" && w.value.length > 0), E = C(() => t.owner.readComposite(t.field.key) || (t.field.key === "PROXY_POOL_WAIT_TIMEOUT" ? {
			mode: Number(n.value) > 0 ? "timed" : "continuous",
			raw: Number(n.value) > 0 ? String(n.value) : ""
		} : {
			mode: String(n.value ?? "").trim() ? "limited" : "unlimited",
			raw: String(n.value ?? "")
		})), O = C(() => ["timed", "limited"].includes(E.value.mode));
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
				let e = n.value.split(c.value ? /[,\n\s]+/ : /\n/).map((e) => e.trim()).filter(Boolean);
				A(c.value ? [...new Set(e.map((e) => e.toUpperCase()))] : e);
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
		let P = C(() => t.owner.isDirty(t.field.key) ? t.field.secret && t.owner.secretDraft(t.field.key).mode === "clear" ? "待清除" : "待保存" : t.field.invalid_env ? "配置值无效，未生效" : t.field.secret ? t.field.configured ? "密钥已配置" : "未配置" : t.field.restart ? "已配置 · 需重启" : ""), F = C(() => t.field.key === "ACCOUNT_CODEX_DRIVER"), I = [
			"EXTRACT_LINK_HUANGUANG_CDK",
			"EXTRACT_LINK_HUANGUANG_PAYMENT_CDK",
			"EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY",
			"EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"
		];
		return (t, c) => (i(), d("div", {
			class: m(["config-vue-field", { "is-invalid": o.value }]),
			"data-config-setting": e.field.key
		}, [b("div", We, [
			b("label", { for: a.value }, h(e.field.label || e.field.key), 9, Ge),
			b("code", null, h(e.field.key), 1),
			e.field.help ? (i(), d("p", {
				key: 0,
				id: `${a.value}-help`,
				class: "hint"
			}, h(e.field.help), 9, Ke)) : g("", !0),
			P.value ? (i(), d("span", qe, h(P.value), 1)) : g("", !0)
		]), b("div", Je, [
			e.legacy ? (i(), d("p", Ye, "兼容保留")) : F.value ? (i(), d("p", Xe, h(S(G)(e.owner.field("CODEX_OAUTH_DRIVER")).find((t) => t.value === e.owner.readField("CODEX_OAUTH_DRIVER"))?.label || e.owner.readField("CODEX_OAUTH_DRIVER")) + " · 由注册主链路统一维护", 1)) : (i(), d("fieldset", {
				key: 2,
				disabled: s.value,
				class: "config-vue-control-group"
			}, [["PROXY_POOL_WAIT_TIMEOUT", "SMS_MAX_PRICE"].includes(e.field.key) ? (i(), d("div", Qe, [b("select", {
				id: a.value,
				"data-key": e.field.key,
				value: E.value.mode,
				"aria-label": e.field.key === "SMS_MAX_PRICE" ? "价格上限模式" : "领取等待模式",
				"aria-invalid": !!o.value,
				onChange: c[0] ||= (e) => k(e.target.value)
			}, [e.field.key === "PROXY_POOL_WAIT_TIMEOUT" ? (i(), d(D, { key: 0 }, [c[5] ||= b("option", { value: "continuous" }, "持续等待", -1), c[6] ||= b("option", { value: "timed" }, "限时等待", -1)], 64)) : (i(), d(D, { key: 1 }, [c[7] ||= b("option", { value: "unlimited" }, "不设上限", -1), c[8] ||= b("option", { value: "limited" }, "设上限", -1)], 64))], 40, $e), O.value ? (i(), d("input", {
				key: 0,
				type: "number",
				value: E.value.raw,
				min: e.field.key === "SMS_MAX_PRICE" ? 0 : 1,
				step: e.field.key === "SMS_MAX_PRICE" ? "0.001" : "1",
				"aria-label": e.field.key === "SMS_MAX_PRICE" ? "短信价格上限" : "限时等待秒数",
				"aria-invalid": !!o.value,
				onInput: c[1] ||= (t) => e.owner.setComposite(e.field.key, {
					mode: E.value.mode,
					raw: t.target.value
				})
			}, null, 40, et)) : g("", !0)])) : l.value || f.value ? (i(), _(ze, {
				key: 1,
				id: a.value,
				"data-key": e.field.key,
				label: e.field.label,
				country: l.value,
				values: p.value,
				options: w.value,
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
			])) : T.value ? (i(), d("select", {
				key: 2,
				id: a.value,
				"data-key": e.field.key,
				value: x.value,
				"aria-label": e.field.label,
				"aria-invalid": !!o.value,
				"aria-describedby": `${a.value}-help ${a.value}-error`,
				disabled: w.value.length === 1 || w.value.every((e) => e.disabled),
				onChange: c[2] ||= (e) => A(e.target.value)
			}, [(i(!0), d(D, null, r(w.value, (e) => (i(), d("option", {
				key: e.value,
				value: e.value,
				disabled: e.disabled,
				title: e.reason
			}, h(e.label) + h(e.disabled && e.reason ? `（${e.reason}）` : ""), 9, nt))), 128))], 40, tt)) : e.field.type === "list_str_multiline" ? (i(), d("textarea", {
				key: 3,
				id: a.value,
				"data-key": e.field.key,
				value: p.value.join("\n"),
				"aria-label": e.field.label,
				"aria-invalid": !!o.value,
				"aria-describedby": `${a.value}-help ${a.value}-error`,
				placeholder: e.field.secret ? "留空保留已有值" : "每行一条，可留空",
				onInput: j
			}, null, 40, rt)) : (i(), d("input", {
				key: 4,
				id: a.value,
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
				"aria-invalid": !!o.value,
				"aria-describedby": `${a.value}-help ${a.value}-error`,
				onInput: j,
				onChange: M
			}, null, 40, it)), e.field.secret ? (i(), d("button", {
				key: 5,
				type: "button",
				"aria-label": `明确清除${e.field.label}`,
				onClick: c[3] ||= (t) => e.owner.clearSecret(e.field.key)
			}, "清除", 8, at)) : g("", !0)], 8, Ze)),
			F.value ? (i(), d("p", ot, "注册和账号补全共用同一套 Codex OAuth 执行方式，请到注册主链路修改。")) : g("", !0),
			e.field.reason ? (i(), d("p", st, h(e.field.reason), 1)) : g("", !0),
			o.value ? (i(), d("p", {
				key: 5,
				id: `${a.value}-error`,
				class: "config-vue-error",
				role: "alert"
			}, h(o.value), 9, ct)) : g("", !0),
			e.actions && I.includes(e.field.key) ? (i(), _(He, {
				key: 6,
				actions: e.actions,
				"field-key": e.field.key
			}, null, 8, ["actions", "field-key"])) : g("", !0),
			e.actions && e.field.group === "并发控制" && e.field.key !== "GLOBAL_TASK_WORKERS" ? (i(), d("button", {
				key: 7,
				type: "button",
				onClick: c[4] ||= (t) => e.actions.locateConcurrencyTasks(e.field.key)
			}, "定位任务")) : g("", !0)
		])], 10, Ue));
	}
}), ut = ["data-config-tool", "aria-busy"], dt = { class: "config-tool-controls" }, ft = ["value", "disabled"], pt = ["value"], mt = ["value"], ht = ["disabled"], gt = ["disabled"], _t = {
	key: 0,
	role: "status"
}, vt = ["disabled"], yt = ["disabled"], bt = { class: "config-tool-controls" }, xt = ["disabled"], St = ["disabled"], Ct = { class: "config-tool-facts" }, wt = { class: "config-tool-controls" }, Tt = ["disabled"], Et = ["disabled"], Dt = { class: "config-tool-controls" }, Ot = ["disabled"], kt = ["disabled"], At = {
	key: 0,
	class: "hint"
}, jt = {
	key: 1,
	class: "config-migration-preview"
}, Mt = ["disabled"], Nt = ["disabled"], Pt = {
	key: 2,
	class: "config-concurrency-types"
}, Ft = { key: 0 }, It = { key: 1 }, Lt = ["onClick"], Rt = { key: 3 }, zt = {
	key: 4,
	role: "status"
}, Bt = /*#__PURE__*/ T(/* @__PURE__ */ o({
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
		let n = e, a = C(() => n.actions.states[n.tool]), o = C(() => a.value.loading || a.value.posting), s = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {}, l = (e, t = "—") => typeof e == "string" || typeof e == "number" ? String(e) : t, u = (e) => Array.isArray(e) ? e.map(s) : [], f = C(() => `${n.owner.readField("ROXY_WORKSPACE_ID") || ""}::${n.owner.readField("ROXY_PROJECT_ID") || ""}`);
		function _(e) {
			let t = n.actions.roxyWorkspaces.value.find((t) => `${t.id}::${t.projectId}` === e.target.value);
			t && (n.owner.setField("ROXY_WORKSPACE_ID", t.id), n.owner.setField("ROXY_PROJECT_ID", t.projectId));
		}
		function v() {
			return n.actions.saveRoxySelection(String(n.owner.readField("ROXY_WORKSPACE_ID") || ""), String(n.owner.readField("ROXY_PROJECT_ID") || ""));
		}
		let y = C(() => n.actions.roxyWorkspaces.value.some((e) => `${e.id}::${e.projectId}` === f.value)), x = C(() => n.tool === "roxy" ? ["ROXY_WORKSPACE_ID", "ROXY_PROJECT_ID"].map((e) => n.owner.field(e)).find((e) => e?.readonly || e?.editable === !1) : void 0), w = C(() => x.value ? x.value.reason || "当前部署不可编辑 Roxy 团队与项目。" : ""), T;
		c(() => [n.tool, n.active], ([e, t]) => {
			T && n.actions.setVisible(T, !1), T = e === "sentinel" || e === "concurrency" ? e : void 0, T && n.actions.setVisible(T, t);
		}, { immediate: !0 }), t(() => {
			T && n.actions.setVisible(T, !1);
		});
		let E = C(() => s(a.value.snapshot?.candidate)), O = C(() => s(a.value.snapshot?.builtin)), A = C(() => ({
			not_checked: "尚未检查",
			same: "同当前一致",
			version_changed: "发现新版本",
			content_changed: "同版本内容变化",
			unknown: "暂无法比较"
		})[l(a.value.snapshot?.comparison)] || "暂无法比较"), j = (e) => e === "static_markers_present" ? "通过（未运行验证）" : e === "needs_adaptation" ? "需要适配" : "尚未检查", M = C(() => {
			let e = Number(a.value.snapshot?.last_checked_at);
			return e > 0 && Number.isFinite(e) ? (/* @__PURE__ */ new Date(e * 1e3)).toLocaleString("zh-CN", { hour12: !1 }) : "尚未检查";
		}), N = C(() => u(a.value.snapshot?.types)), P = C(() => [
			"providers",
			"batches",
			"remote_orders"
		].flatMap((e) => u(a.value.snapshot?.[e]).map((e) => ({
			label: l(e.label || e.key || e.id || e.batch_id, "当前"),
			occupied: e.occupied ?? e.active ?? 0,
			limit: e.limit ?? "—"
		})))), F = C(() => n.actions.states.concurrencyPreview), I = (e) => {
			let t = s(e), n = l(t.code || t.reason || e), r = t.occupied != null && t.limit != null ? `（${t.occupied}/${t.limit}）` : "", i = {
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
		return (t, n) => (i(), d("div", {
			class: "config-tool-panel-v2 config-action-tools",
			"data-config-tool": e.tool,
			"aria-busy": o.value
		}, [e.tool === "roxy" ? (i(), d(D, { key: 0 }, [
			n[12] ||= b("strong", null, "团队 / 项目选择", -1),
			n[13] ||= b("p", { class: "hint" }, "获取已保存连接中的团队与项目，选择后单独保存。", -1),
			b("div", dt, [
				b("label", null, [n[11] ||= p("团队 / 项目", -1), b("select", {
					"aria-label": "团队 / 项目",
					value: f.value,
					disabled: o.value || !!w.value,
					onChange: _
				}, [y.value ? g("", !0) : (i(), d("option", {
					key: 0,
					value: f.value
				}, "当前团队：" + h(e.owner.readField("ROXY_WORKSPACE_ID") || "未设置"), 9, pt)), (i(!0), d(D, null, r(e.actions.roxyWorkspaces.value, (e) => (i(), d("option", {
					key: `${e.id}::${e.projectId}`,
					value: `${e.id}::${e.projectId}`
				}, h(e.label), 9, mt))), 128))], 40, ft)]),
				b("button", {
					type: "button",
					class: "btn",
					"data-config-action": "load-roxy",
					disabled: o.value || !!w.value,
					onClick: n[0] ||= (t) => e.actions.loadRoxyWorkspaces()
				}, h(a.value.loading ? "正在获取…" : "获取团队"), 9, ht),
				b("button", {
					type: "button",
					class: "btn primary",
					"data-config-action": "save-roxy",
					disabled: o.value || !y.value || !!w.value,
					onClick: v
				}, h(a.value.posting ? "正在保存…" : "保存选择"), 9, gt)
			]),
			w.value ? (i(), d("p", _t, h(w.value), 1)) : g("", !0)
		], 64)) : e.tool === "proxy" ? (i(), d(D, { key: 1 }, [
			n[14] ||= b("strong", null, "代理供应商本地联调", -1),
			n[15] ||= b("p", { class: "hint" }, "会实际提取并检测 1 个 IP，可能产生少量流量或配额消耗。API 请求会绕过系统代理。", -1),
			b("button", {
				type: "button",
				class: "btn",
				"data-config-action": "test-proxy",
				disabled: o.value,
				onClick: n[1] ||= (t) => e.actions.testProxy()
			}, h(o.value ? "正在测试…" : "提取并测试 1 个 IP"), 9, vt)
		], 64)) : e.tool === "butler" ? (i(), d(D, { key: 2 }, [n[16] ||= b("strong", null, "Email Butler 连接与权限", -1), b("button", {
			type: "button",
			class: "btn",
			"data-config-action": "test-butler",
			disabled: o.value,
			onClick: n[2] ||= (t) => e.actions.testButler()
		}, h(o.value ? "正在检测…" : "测试连接与权限"), 9, yt)], 64)) : e.tool === "sentinel" ? (i(), d(D, { key: 3 }, [
			n[23] ||= b("strong", null, "Sentinel 检查", -1),
			n[24] ||= b("p", { class: "hint" }, "手动获取候选资源；不自动切换现用版本。", -1),
			b("div", bt, [b("button", {
				type: "button",
				class: "btn",
				"data-config-action": "check-sentinel",
				disabled: o.value || !!a.value.snapshot?.running,
				onClick: n[3] ||= (t) => e.actions.checkSentinel()
			}, h(a.value.posting || a.value.snapshot?.running ? "检查中…" : "检查 Sentinel 更新"), 9, xt), b("button", {
				type: "button",
				class: "btn",
				disabled: o.value,
				onClick: n[4] ||= (t) => e.actions.refreshSentinel()
			}, "刷新状态", 8, St)]),
			b("dl", Ct, [
				n[17] ||= b("dt", null, "当前内置版本", -1),
				b("dd", null, h(l(O.value.version, "读取后显示")), 1),
				n[18] ||= b("dt", null, "发现版本", -1),
				b("dd", null, h(l(E.value.version, "尚未发现")), 1),
				n[19] ||= b("dt", null, "上次检查时间", -1),
				b("dd", null, h(M.value), 1),
				n[20] ||= b("dt", null, "版本比较", -1),
				b("dd", null, h(A.value), 1),
				n[21] ||= b("dt", null, "generic 静态检查", -1),
				b("dd", null, h(j(E.value.generic_status)), 1),
				n[22] ||= b("dt", null, "Proto2 静态检查", -1),
				b("dd", null, h(j(E.value.proto2_status)), 1)
			])
		], 64)) : e.tool === "sub2api" ? (i(), d(D, { key: 4 }, [
			n[25] ||= b("strong", null, "同步与异常巡检", -1),
			n[26] ||= b("p", { class: "hint" }, "使用已保存配置检查远端异常账号，修复进度可在任务中心查看。", -1),
			b("div", wt, [b("button", {
				type: "button",
				class: "btn",
				disabled: o.value,
				onClick: n[5] ||= (t) => e.actions.refreshSub2Api()
			}, "查看状态", 8, Tt), b("button", {
				type: "button",
				class: "btn",
				"data-config-action": "check-sub2api",
				disabled: o.value,
				onClick: n[6] ||= (t) => e.actions.checkSub2Api()
			}, "立即巡检", 8, Et)])
		], 64)) : e.tool === "concurrency" ? (i(), d(D, { key: 5 }, [
			n[27] ||= b("strong", null, "并发运行状态", -1),
			b("div", Dt, [b("button", {
				type: "button",
				class: "btn",
				disabled: o.value,
				onClick: n[7] ||= (t) => e.actions.refreshConcurrency()
			}, "刷新状态", 8, Ot), b("button", {
				type: "button",
				class: "btn",
				disabled: o.value,
				onClick: n[8] ||= (t) => e.actions.refreshConcurrency({ details: !0 })
			}, "查看附加限制", 8, kt)]),
			a.value.snapshot ? (i(), d("p", At, "部署范围 " + h(l(s(a.value.snapshot.scope).label || a.value.snapshot.scope, "当前部署")) + " · 策略版本 " + h(l(a.value.snapshot.policy_revision)) + " · 观察时间 " + h(S(k)(a.value.snapshot.observed_at)), 1)) : g("", !0),
			n[28] ||= b("p", { class: "config-section-v2-subhelp" }, "各类型上限是上限，不预留配额，合计可以超过全局。内部同步刷新 AT、查套餐与后处理归属巡检、提链或注册父任务，复用父任务许可；独立子任务按实际动作重新排队。", -1),
			F.value.snapshot?.migration_required || a.value.snapshot?.migration_required ? (i(), d("div", jt, [
				b("p", null, "新策略需要完整保存。历史账号池上限：" + h(l(F.value.snapshot?.legacy_account_workers, "未记录")), 1),
				(i(!0), d(D, null, r(Array.isArray(F.value.snapshot?.notes) ? F.value.snapshot.notes : [], (e, t) => (i(), d("p", { key: t }, h(l(e, "")), 1))), 128)),
				b("button", {
					type: "button",
					class: "btn",
					disabled: !F.value.snapshot,
					onClick: n[9] ||= (t) => e.actions.applyConcurrencyPreview()
				}, "填入迁移建议", 8, Mt),
				F.value.error ? (i(), d("button", {
					key: 0,
					type: "button",
					class: "btn",
					disabled: F.value.loading,
					onClick: n[10] ||= (t) => e.actions.loadConcurrencyPreview()
				}, "重试迁移预览", 8, Nt)) : g("", !0)
			])) : g("", !0),
			N.value.length ? (i(), d("ul", Pt, [(i(!0), d(D, null, r(N.value, (t) => (i(), d("li", { key: l(t.key) }, [b("div", null, [
				b("strong", null, h(l(t.label || t.key)), 1),
				b("span", null, "占用 " + h(t.occupied ?? 0) + " / " + h(t.limit ?? "—") + " · 排队 " + h(t.queued ?? 0) + h(t.draining ? " · 等待现有任务结束" : ""), 1),
				Number(e.owner.readField(l(t.config_key))) > Number(s(a.value.snapshot?.global).limit) ? (i(), d("small", Ft, "当前实际最多受全局 " + h(s(a.value.snapshot?.global).limit) + " 限制；保存后的类型值仍会保留。", 1)) : g("", !0),
				Array.isArray(t.blocked_by) && t.blocked_by.length ? (i(), d("small", It, h(t.blocked_by.map(I).join("；")), 1)) : g("", !0)
			]), b("button", {
				type: "button",
				class: "btn",
				onClick: (n) => e.actions.locateConcurrencyTasks(l(t.config_key || t.key))
			}, "定位任务", 8, Lt)]))), 128))])) : g("", !0),
			P.value.length ? (i(), d("ul", Rt, [(i(!0), d(D, null, r(P.value, (e, t) => (i(), d("li", { key: t }, h(e.label) + "：" + h(e.occupied) + " / " + h(e.limit), 1))), 128))])) : g("", !0),
			n[29] ||= b("details", { class: "config-concurrency-details-v2" }, [
				b("summary", null, "业务附加限制与计量说明"),
				b("p", { class: "hint" }, "注册批次并发填写正整数，提链批次与平台保留 1–50；它们与全局、类型限制同时生效。XXSYUN 未结束订单名额在远端等待时仍占用，本地查询间隔不占执行槽。调试保留、停止清理和已预约执行仍计入占用。"),
				b("p", { class: "hint" }, "账号补全等待独立子任务时不重复占全局槽；HME 合并扫描按一个扫描 Run 计数；邮箱导入按实际远端交接调用计数。Sub2API 远端账号并发属性在服务集成中维护。")
			], -1),
			F.value.text || F.value.error ? (i(), d("p", zt, h(F.value.error || F.value.text), 1)) : g("", !0)
		], 64)) : g("", !0), b("p", {
			class: m(["config-action-status", { "config-action-error": a.value.error }]),
			role: "status",
			"aria-live": "polite"
		}, h(a.value.error || a.value.text || (o.value ? "正在请求…" : "尚未查询")), 3)], 8, ut));
	}
}), [["__scopeId", "data-v-ecc7ba70"]]), Vt = {
	class: "config-vue-overview",
	"aria-label": "当前配置概览"
}, Ht = {
	key: 0,
	role: "status"
}, Ut = {
	key: 1,
	class: "config-vue-error",
	role: "alert"
}, Wt = {
	key: 2,
	class: "config-vue-error",
	role: "status"
}, Gt = {
	key: 3,
	class: "config-vue-error-summary",
	role: "alert",
	tabindex: "-1"
}, Kt = ["onClick"], qt = { class: "config-vue-layout" }, Jt = { class: "config-vue-content" }, Yt = ["aria-label"], Xt = [
	"data-config-domain-v2",
	"aria-pressed",
	"onClick"
], Zt = ["data-config-section"], Qt = ["aria-label"], $t = [
	"data-config-subsection",
	"aria-pressed",
	"onClick"
], en = {
	key: 1,
	class: "config-vue-pool-rules"
}, tn = {
	key: 2,
	class: "config-vue-field"
}, nn = ["open"], rn = { key: 0 }, an = {
	key: 5,
	class: "hint"
}, on = {
	key: 6,
	class: "hint"
}, sn = {
	key: 4,
	class: "config-vue-savebar"
}, cn = {
	role: "status",
	"aria-live": "polite"
}, ln = { key: 0 }, un = { key: 1 }, dn = { key: 2 }, fn = { key: 3 }, pn = ["disabled"], mn = ["disabled"], hn = /* @__PURE__ */ o({
	__name: "ConfigPage",
	props: {
		owner: {},
		actions: {},
		active: {
			type: Boolean,
			default: !0
		}
	},
	setup(n, { expose: a }) {
		let o = n, s = e(""), l = u({
			menu: "",
			domain: "",
			section: ""
		}), f = e(), m = {}, x = {}, w = C(() => le(l.menu, o.owner.fields.value)), T = C(() => me(l.domain, o.owner.fields.value)), E = C(() => ye(o.owner, l, !!s.value.trim())), k = C(() => xe(l.domain, E.value)), A = /* @__PURE__ */ new Set([
			"PROXY_POOL_SOURCE",
			"PROXY_POOL_DEFAULT_COUNTRY",
			"PROXY_POOL",
			...["PROXY_1024_", "PROXY_711_"].flatMap((e) => [
				"API_URL",
				"PROTOCOL",
				"SESSION_MINUTES"
			].map((t) => `${e}${t}`))
		]), j = C(() => E.value.filter((e) => A.has(e.key))), M = C(() => E.value.filter((e) => !A.has(e.key))), N = C(() => de(o.owner.fields.value)), F = C(() => N.value.filter((e) => o.owner.readField(e.enabledKey) === !0).map((e) => e.value)), I = C(() => Object.entries(o.owner.fieldErrors)), L = C(() => l.domain === "RoxyBrowser" ? "roxy" : l.domain === "代理与网络" && l.section === "代理来源" && o.owner.readField("PROXY_POOL_SOURCE") !== "manual" ? "proxy" : l.domain === "邮箱 / OTP" && l.section === "Email Butler" ? "butler" : l.domain === "通用配置" ? "sentinel" : l.domain === "Codex" && l.section === "sub2api" ? "sub2api" : l.domain === "并发控制" ? "concurrency" : null);
		function R() {
			try {
				localStorage.setItem(ie, l.domain || l.menu);
			} catch {}
		}
		function z() {
			y(() => {
				let e = f.value?.querySelector("main"), t = !!(e?.scrollTop || e?.scrollLeft || window.scrollY || window.scrollX || document.documentElement.scrollTop);
				e && (e.scrollTop = 0, e.scrollLeft = 0), t && window.scrollTo({
					top: 0,
					left: 0,
					behavior: "auto"
				});
			});
		}
		function B(e) {
			let t = he(e, o.owner.fields.value);
			P[e] && m[t.menu] && (t.domain = m[t.menu]), t.section = x[t.domain] || me(t.domain, o.owner.fields.value)[0] || "", Object.assign(l, t), R(), z();
		}
		function ee(e) {
			l.domain = e, m[l.menu] = e, l.section = x[e] || me(e, o.owner.fields.value)[0] || "", R(), z();
		}
		function te(e) {
			l.section = e, x[l.domain] = e, z();
		}
		function ne(e) {
			s.value = e;
			let t = ve(e, o.owner.fields.value, l.menu);
			t && Object.assign(l, t);
		}
		function V(e) {
			for (let t of N.value) o.owner.setField(t.enabledKey, e.includes(t.value));
		}
		async function re(e) {
			let t = o.owner.field(e);
			if (!t) return;
			s.value.trim() && !_e(t, o.owner.fields.value).includes(s.value.trim().toLowerCase()) && (s.value = ""), Object.assign(l, ge(t, o.owner.fields.value)), R(), await y();
			let n = Array.from(f.value?.querySelectorAll("[data-config-setting]") || []).find((t) => t.dataset.configSetting === e);
			n?.querySelectorAll("details").forEach((e) => e.open = !0);
			let r = n?.closest("details");
			r && (r.open = !0);
			let i = n?.querySelector("input:not([type=hidden]),select,textarea,summary,button");
			i?.focus(), i?.scrollIntoView?.({ block: "nearest" });
		}
		function ae() {
			o.owner.dirtyCount.value && window.confirm("确定撤销全部未保存的配置修改？") && o.owner.reset();
		}
		function oe(e) {
			o.owner.dirtyCount.value && (e.preventDefault(), e.returnValue = "");
		}
		async function se() {
			let e = await o.owner.saveAll();
			if (e.status === "validation-error") {
				let t = Object.keys(e.fields || {})[0];
				t && o.owner.navigateField(t);
			}
		}
		function H(e) {
			let t = o.owner.readField(e);
			return t == null || t === "" ? "—" : G(o.owner.field(e)).find((e) => e.value === t)?.label || (Array.isArray(t) ? t.join("、") : String(t));
		}
		c(() => o.owner.navigationTarget.value, (e) => {
			e && re(e.key);
		}), c(() => o.active, (e) => o.actions.setPageActive(e), { immediate: !0 }), t(() => {
			o.actions.setPageActive(!1), window.removeEventListener("beforeunload", oe);
		}), c(() => o.owner.fields.value, () => {
			let e = ce(o.owner.fields.value);
			if (e.length) {
				if (!l.menu) {
					let t = "";
					try {
						t = localStorage.getItem("gpt_console_config_group") || "";
					} catch {}
					Object.assign(l, he(t || e[0], o.owner.fields.value));
				}
				e.includes(l.menu) || Object.assign(l, he(e[0], o.owner.fields.value)), w.value.includes(l.domain) || (l.domain = w.value[0] || l.menu), T.value.includes(l.section) || (l.section = T.value[0] || "");
			}
		}, { immediate: !0 }), v(() => {
			window.addEventListener("beforeunload", oe), o.owner.initialize().catch(() => {}), o.actions.loadExtractTypes();
		}), a({
			open: B,
			focusField: re
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
		return (e, t) => (i(), d("div", {
			ref_key: "root",
			ref: f,
			class: "config-vue-page"
		}, [
			b("div", Vt, [
				b("span", null, [t[1] ||= p("注册主链路 ", -1), b("strong", null, h(S(ue)(n.owner.readField("REGISTRATION_DRIVER"))), 1)]),
				b("span", null, [t[2] ||= p("邮箱来源 ", -1), b("strong", null, h(H("EMAIL_SOURCE")), 1)]),
				b("span", null, [
					t[3] ||= p("Codex OAuth ", -1),
					b("strong", null, h(H("CODEX_OAUTH_DRIVER")), 1),
					b("small", null, "自动授权：" + h(n.owner.readField("ENABLE_CODEX_AUTO") ? "已开启" : "已关闭"), 1)
				]),
				b("span", null, [t[4] ||= p("代理模式 ", -1), b("strong", null, h(H("REGISTRATION_PROXY_MODE")), 1)])
			]),
			n.owner.loading.value ? (i(), d("p", Ht, "正在读取配置…")) : g("", !0),
			n.owner.error.value ? (i(), d("p", Ut, h(n.owner.error.value), 1)) : g("", !0),
			n.owner.refreshError.value ? (i(), d("p", Wt, [p(h(n.owner.refreshError.value) + " ", 1), b("button", {
				type: "button",
				onClick: t[0] ||= (e) => n.owner.refresh({ force: !0 })
			}, "重新读取配置")])) : g("", !0),
			I.value.length ? (i(), d("div", Gt, [b("strong", null, "请检查 " + h(I.value.length) + " 项配置，草稿已保留", 1), b("ul", null, [(i(!0), d(D, null, r(I.value, ([e, t]) => (i(), d("li", { key: e }, [b("button", {
				type: "button",
				onClick: (t) => n.owner.navigateField(e)
			}, h(n.owner.field(e)?.label || e) + "：" + h(t), 9, Kt)]))), 128))])])) : g("", !0),
			b("div", qt, [O(ke, {
				owner: n.owner,
				active: l.menu,
				query: s.value,
				onSelect: B,
				onSearch: ne
			}, null, 8, [
				"owner",
				"active",
				"query"
			]), b("main", Jt, [b("div", {
				class: "config-vue-tabs",
				role: "group",
				"aria-label": `${l.menu}配置领域`
			}, [(i(!0), d(D, null, r(w.value, (e) => (i(), d("button", {
				key: e,
				type: "button",
				"data-config-domain-v2": e,
				"aria-pressed": l.domain === e,
				onClick: (t) => ee(e)
			}, h(e === "注册与账号" ? "查询套餐" : e), 9, Xt))), 128))], 8, Yt), b("section", { "data-config-section": l.domain }, [
				b("h2", null, h(l.domain === "注册与账号" ? "查询套餐" : l.domain), 1),
				T.value.length ? (i(), d("div", {
					key: 0,
					class: "config-vue-tabs",
					role: "group",
					"aria-label": `${l.domain}配置分类`
				}, [(i(!0), d(D, null, r(T.value, (e) => (i(), d("button", {
					key: e,
					type: "button",
					"data-config-subsection": e,
					"aria-pressed": l.section === e,
					onClick: (t) => te(e)
				}, h(e), 9, $t))), 128))], 8, Qt)) : g("", !0),
				l.domain === "代理与网络" && l.section === "任务用池" ? (i(), d("table", en, [
					t[5] ||= b("caption", null, "任务用池规则", -1),
					t[6] ||= b("thead", null, [b("tr", null, [
						b("th", null, "任务"),
						b("th", null, "国家需求"),
						b("th", null, "领取规则")
					])], -1),
					b("tbody", null, [(i(), d(D, null, r(U, (e) => b("tr", { key: e[0] }, [(i(!0), d(D, null, r(e, (e) => (i(), d("td", { key: e }, h(e), 1))), 128))])), 64))])
				])) : g("", !0),
				l.domain === "提链" && l.section === "通用配置" ? (i(), d("div", tn, [t[7] ||= b("div", { class: "config-vue-field-copy" }, [b("label", null, "启用平台"), b("p", { class: "hint" }, "选择允许在提链工作台中使用的平台；取消选择不会清除该平台的地址或 CDK。")], -1), O(ze, {
					label: "启用平台",
					values: F.value,
					options: N.value,
					onChange: V
				}, null, 8, ["values", "options"])])) : g("", !0),
				l.domain === "代理与网络" && l.section === "代理来源" ? (i(), d(D, { key: 3 }, [(i(!0), d(D, null, r(j.value, (e) => (i(), _(lt, {
					key: e.key,
					owner: n.owner,
					field: e,
					actions: n.actions
				}, null, 8, [
					"owner",
					"field",
					"actions"
				]))), 128)), M.value.length ? (i(), d("details", {
					key: 0,
					class: "config-vue-source-advanced",
					open: !!s.value.trim()
				}, [t[8] ||= b("summary", null, "高级提取与检测参数", -1), (i(!0), d(D, null, r(M.value, (e) => (i(), _(lt, {
					key: e.key,
					owner: n.owner,
					field: e,
					actions: n.actions
				}, null, 8, [
					"owner",
					"field",
					"actions"
				]))), 128))], 8, nn)) : g("", !0)], 64)) : (i(!0), d(D, { key: 4 }, r(k.value, (e) => (i(), d("div", {
					key: e.title,
					class: "config-vue-setting-group"
				}, [e.title ? (i(), d("h3", rn, h(e.title), 1)) : g("", !0), (i(!0), d(D, null, r(e.fields, (e) => (i(), _(lt, {
					key: e.key,
					owner: n.owner,
					field: e,
					actions: n.actions,
					legacy: l.domain === "代理与网络" && l.section === "高级兼容"
				}, null, 8, [
					"owner",
					"field",
					"actions",
					"legacy"
				]))), 128))]))), 128)),
				l.domain === "邮箱 / OTP" && l.section === "iCloud 隐藏邮箱" ? (i(), d("p", an, "隐藏邮箱的创建、状态与管理请在邮箱服务（Email Butler）中完成。本页只维护已导入与历史邮箱的固定收件连接。")) : g("", !0),
				l.domain === "注册调试" ? (i(), d("p", on, "“调试模式”仍是单个注册批次的现场保留开关，本页只控制失败诊断、保留时长和抓包预算。")) : g("", !0),
				L.value ? (i(), _(Bt, {
					key: L.value,
					owner: n.owner,
					actions: n.actions,
					tool: L.value,
					active: n.active
				}, null, 8, [
					"owner",
					"actions",
					"tool",
					"active"
				])) : g("", !0)
			], 8, Zt)])]),
			n.owner.dirtyCount.value || n.owner.receipt.value ? (i(), d("div", sn, [
				b("div", cn, [
					b("strong", null, h(I.value.length ? "请检查标记的配置项" : n.owner.error.value ? "保存失败，请重试" : n.owner.dirtyCount.value ? `${n.owner.dirtyCount.value} 项待保存` : "配置已保存"), 1),
					I.value.length ? (i(), d("span", ln, "请检查标记的配置项后再保存")) : n.owner.error.value ? (i(), d("span", un, "请检查网络或服务状态后重试")) : g("", !0),
					n.owner.receipt.value ? (i(), d("span", dn, "数据库保存" + h(n.owner.receipt.value.persistedDbRevision === null ? "成功" : `版本 ${n.owner.receipt.value.persistedDbRevision}`) + " · Worker " + h(n.owner.receipt.value.workerApplication.state === "applied" ? "已应用" : n.owner.receipt.value.workerApplication.state === "error" ? "应用异常" : n.owner.receipt.value.workerApplication.state === "pending" ? "等待应用" : "应用状态待确认"), 1)) : g("", !0),
					n.owner.receipt.value?.restartRequired.length ? (i(), d("span", fn, "需重启：" + h(n.owner.receipt.value.restartRequired.join("、")), 1)) : g("", !0)
				]),
				b("button", {
					type: "button",
					disabled: !n.owner.dirtyCount.value || n.owner.saving.value,
					onClick: ae
				}, "撤销修改", 8, pn),
				b("button", {
					type: "button",
					class: "primary",
					disabled: !n.owner.dirtyCount.value || n.owner.saving.value,
					onClick: se
				}, h(n.owner.saving.value ? "正在保存…" : "保存全部配置"), 9, mn)
			])) : g("", !0)
		], 512));
	}
}), K = class extends Error {
	status;
	code;
	fields;
	constructor(e, t, n = "", r = {}) {
		super(e), this.status = t, this.code = n, this.fields = r, this.name = "ConfigApiError";
	}
}, q = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {}, gn = (e) => JSON.parse(JSON.stringify(e));
function _n(e) {
	if (!Array.isArray(e)) throw new K("配置字段响应格式无效", 0, "config_schema_invalid");
	let t = /* @__PURE__ */ new Set();
	return e.map((e) => {
		let n = q(e);
		if (typeof n.key != "string" || !n.key || typeof n.type != "string" || t.has(n.key)) throw new K("配置字段响应格式无效", 0, "config_schema_invalid");
		t.add(n.key);
		let r = gn({
			...n,
			group: String(n.group || "其他"),
			label: String(n.label || n.key)
		});
		return r.secret && (r.value = "", "configured_value" in r && (r.configured_value = ""), "published_effective_value" in r && (r.published_effective_value = ""), delete r.default), r;
	});
}
function vn(e = fetch) {
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
			if (r?.generation === t) return gn(await r.promise);
			if (!e.force && n && Date.now() - n.at < 3e4) return gn(n.fields);
			let a = t, o = i("/api/config", { signal: e.signal }).then((e) => {
				let r = _n(e);
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
				return gn(await o);
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
function yn(e, t) {
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
function bn(e, t) {
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
var J = (e) => e === void 0 ? e : JSON.parse(JSON.stringify(e)), xn = (e, t) => JSON.stringify(e) === JSON.stringify(t);
function Sn(t) {
	let n = E(_n(t.initialFields || [])), r = u({}), i = u({}), o = e(!1), s = e(!1), c = e(""), l = e(""), d = e(null), f = e(null), p = /* @__PURE__ */ new Map(), m = /* @__PURE__ */ new Set(), h = /* @__PURE__ */ new Set(), g = !1, _ = 0, v = 0, y = null, b = /* @__PURE__ */ new Set(), x = C(() => new Map(n.value.map((e) => [e.key, e]))), S = C(() => Object.keys(r)), w = C(() => S.value.length), T = (e) => x.value.get(e), D = (e) => {
		let t = (p.get(e) || 0) + 1;
		return p.set(e, t), t;
	};
	function O(e, t = "effective") {
		return J(t === "effective" && r[e] ? r[e].value : T(e)?.value);
	}
	function k(e) {
		let t = T(e);
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
		!s && !b.has(e) && xn(t, a.value) ? delete r[e] : r[e] = {
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
	function P(e = S.value) {
		for (let t of e) D(t), delete r[t], delete i[t];
		c.value = "";
	}
	function F(e) {
		f.value = {
			key: e,
			generation: ++v
		}, t.onNavigateField?.(e);
	}
	async function I(e = {}) {
		if (g) return;
		let r = ++_, i = new AbortController();
		h.add(i), o.value = !0;
		try {
			let a = await t.api.getSchema({
				...e,
				signal: i.signal
			});
			if (g || r !== _ || i.signal.aborted) return;
			n.value = _n(a), l.value = "";
		} catch (e) {
			if (!g && r === _ && !i.signal.aborted) throw l.value = "配置读取失败，当前草稿已保留", e;
		} finally {
			h.delete(i), r === _ && (o.value = !1);
		}
	}
	async function L() {
		if (!(g || n.value.length)) return y ||= I().finally(() => {
			y = null;
		}), y;
	}
	function R(e) {
		let i = {
			...bn(e, n.value),
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
		if (s.value) return { status: "busy" };
		let a = /* @__PURE__ */ new Map(), o = {};
		for (let t of e) r[t] && (a.set(t, J(r[t])), o[t] = J(r[t].value));
		if (!a.size) return { status: "noop" };
		let l = R(o);
		if (Object.keys(l).length) return z(l), {
			status: "validation-error",
			fields: l
		};
		s.value = !0, c.value = "", b = new Set(a.keys());
		try {
			let e = await t.api.save(o);
			if (g) return { status: "disposed" };
			_++;
			let s = yn(e, [...a.keys()]), c = new Set(s.savedKeys);
			n.value = n.value.map((e) => {
				let t = a.get(e.key);
				return !t || !c.has(e.key) ? e : e.secret ? {
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
			for (let [e, t] of a) c.has(e) && p.get(e) === t.generation && (delete r[e], delete i[e]);
			t.api.invalidate(), d.value = s;
			try {
				await I({ force: !0 });
			} catch {
				s.refreshFailed = !0, d.value = { ...s };
			}
			if (!g) {
				let e = {
					keys: s.savedKeys,
					receipt: J(s),
					fields: J(n.value)
				};
				for (let t of m) try {
					t(e);
				} catch {}
			}
			return {
				status: "saved",
				receipt: J(s)
			};
		} catch (e) {
			if (g) return { status: "disposed" };
			let t = e instanceof K ? e.fields : {};
			if (Object.keys(t).length) {
				let e = Object.fromEntries(Object.entries(t).filter(([e]) => {
					let t = a.get(e);
					return !t || p.get(e) === t.generation;
				}));
				return z(e), {
					status: "validation-error",
					fields: J(e)
				};
			}
			return c.value = e instanceof K ? e.message : "配置保存失败，草稿已保留", { status: "error" };
		} finally {
			s.value = !1, b = /* @__PURE__ */ new Set();
		}
	}
	async function ee(e) {
		if (g) return { status: "disposed" };
		if (s.value) return { status: "busy" };
		if (Array.isArray(e)) return B(e);
		for (let [t, n] of Object.entries(e)) M(t, n, { force: !0 });
		return B(Object.keys(e));
	}
	function te() {
		g = !0, _++;
		for (let e of h) e.abort();
		h.clear(), m.clear();
		for (let e of Object.keys(r)) delete r[e];
		o.value = !1;
	}
	return {
		fields: n,
		dirtyKeys: S,
		dirtyCount: w,
		fieldErrors: a(i),
		loading: o,
		saving: s,
		error: c,
		refreshError: l,
		receipt: d,
		navigationTarget: f,
		field: T,
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
		saveAll: () => B(S.value),
		saveSubset: ee,
		navigateField: F,
		subscribeSaved(e) {
			return m.add(e), () => m.delete(e);
		},
		dispose: te
	};
}
// src/features/config/configActions.ts
var Cn = [
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
	"concurrencyPreview"
], wn = {
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
function Tn(e) {
	return typeof e == "string" ? e.trim() : "";
}
function Z(e) {
	return Array.isArray(e) ? e : [];
}
function En(e) {
	return typeof e == "number" && Number.isFinite(e) && e >= 0;
}
function Q(e) {
	return Number.isSafeInteger(e) && Number(e) >= 0;
}
function Dn() {
	throw { code: "invalid_response" };
}
function $(e) {
	return {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(e)
	};
}
function On(e, t = !1, n = "CDK") {
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
function kn(e, t = {}) {
	let n = t.request || ((e, t) => A(e, t, N)), r = u(Object.fromEntries(Cn.map((e) => [e, {
		loading: !1,
		posting: !1,
		text: "",
		error: "",
		snapshot: null,
		receipt: null
	}]))), i = Object.fromEntries(Cn.map((e) => [e, 0])), a = /* @__PURE__ */ new Map(), o = /* @__PURE__ */ new Map(), s = {
		sentinel: !1,
		concurrency: !1
	}, l = /* @__PURE__ */ new Map(), d = !0, f = !0, p = !1, m = [], h = (t, n = "") => e.readField(t) ?? n;
	function g(t) {
		let n = e.secretDraft(t);
		return n.mode === "set" ? Tn(n.value) : n.mode === "clear" ? "" : Tn(h(t));
	}
	function _(t) {
		let n = e.secretDraft(t);
		return n.mode === "clear" ? { api_key: "" } : n.mode === "set" ? { api_key: Tn(n.value) } : e.isDirty(t) ? { api_key: Tn(h(t)) } : {};
	}
	function v(e) {
		let t = l.get(e);
		t !== void 0 && clearTimeout(t), l.delete(e);
	}
	function y(e, t = !1) {
		i[e]++;
		let n = a.get(e);
		n?.posting || n?.controller?.abort(), r[e].loading = !1, r[e].posting = !1, r[e].error = "", r[e].text = "", t || (r[e].snapshot = null, r[e].receipt = null);
	}
	for (let [t, n] of Object.entries(wn)) m.push(c(() => n.map((t) => [
		e.readField(t),
		e.isDirty(t),
		e.secretDraft(t)
	]), () => y(t), {
		deep: !0,
		flush: "sync"
	}));
	m.push(e.subscribeSaved((t) => {
		for (let [e, n] of Object.entries(wn)) n.some((e) => t.keys.includes(e)) && y(e);
		t.keys.some((t) => e.field(t)?.group === "并发控制") && y("concurrencyPreview");
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
	function x(e) {
		v(e), !p && d && f && s[e] && !r[e].loading && !r[e].posting && (e !== "sentinel" || r.sentinel.snapshot?.running && !r.sentinel.error) && l.set(e, setTimeout(() => {
			l.delete(e), e === "sentinel" ? R() : V();
		}, e === "sentinel" ? 1500 : 3e3));
	}
	function S(e, t, s, c) {
		if (p) return Promise.resolve();
		let l = c.posting && [
			"sentinel",
			"sub2api",
			"proxy"
		].includes(e), u = l ? o.get(e) : void 0;
		if (u) return u;
		let d = a.get(e);
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
					...s,
					...m ? { signal: m.signal } : {}
				})));
				if (i.ok === !1) throw i;
				let a = c.label ? b(i, c.label) : null;
				if (!h()) return;
				r[e].receipt = a, c.apply(i, a);
			} catch (t) {
				if (!h()) return;
				r[e].error = c.error?.(t) || "请求未完成，请稍后重试。", r[e].text = r[e].error;
			} finally {
				l && o.delete(e), a.get(e)?.generation === f && a.delete(e), h() && (r[e].loading = !1, r[e].posting = !1, (e === "sentinel" || e === "concurrency") && x(e));
			}
		})();
		return a.set(e, {
			generation: f,
			promise: g,
			controller: m,
			posting: !!c.posting
		}), l && o.set(e, g), g;
	}
	function w(e, t) {
		return r[e].text = t, r[e].error = "", Promise.resolve();
	}
	function T() {
		return S("extractTypes", "/api/extract-link/types", { method: "GET" }, {
			apply: (e) => {
				let t = /* @__PURE__ */ new Set(), n = [];
				for (let r of Z(e.items)) {
					let e = Y(r), i = X(e.type).trim().toLowerCase();
					i && !t.has(i) && e.visible !== !1 && e.enabled !== !1 && (t.add(i), n.push({
						value: i,
						label: X(e.label, i) || i
					}));
				}
				n.length || Dn(), r.extractTypes.snapshot = { options: n };
			},
			error: () => "提链类型读取失败，保留当前选择。"
		});
	}
	function E() {
		return S("roxy", "/api/roxy/workspaces", { method: "GET" }, {
			apply: (e) => {
				let t = Z(e.items).map((e) => {
					let t = Y(e);
					return {
						id: X(t.id),
						projectId: X(t.projectId),
						label: X(t.label) || `${X(t.name)} (${X(t.id)})`
					};
				}).filter((e) => e.id);
				t.length || Dn(), r.roxy.snapshot = { items: t }, r.roxy.text = `已获取 ${t.length} 个团队/项目`;
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
		return t ? S("proxy", "/api/proxy-provider/test", $({
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
		return S("butler", "/api/email-butler/test-connection", $({
			api_base: Tn(h("EMAIL_BUTLER_API_BASE")),
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
		return e.isDirty(i) || e.isDirty("EXTRACT_LINK_HUANGUANG_API_BASE") ? w(n, "请先保存此 CDK 或服务地址的更改，再查询剩余次数") : S(n, `/api/extract-link/huanguang/cdk-quota/${t}`, { method: "GET" }, {
			apply: (e) => {
				let t = Y(e.quota);
				(typeof t.required != "boolean" || !(t.remaining === null || Q(t.remaining)) || !(t.reserved === null || Q(t.reserved)) || t.active !== null && typeof t.active != "boolean") && Dn(), r[n].snapshot = {
					required: t.required,
					remaining: t.remaining,
					reserved: t.reserved,
					active: t.active
				}, r[n].text = t.required ? `剩余 ${t.remaining ?? "未知"} 次 · 占用 ${t.reserved ?? "未知"} · ${t.active === !1 ? "已停用" : t.active === !0 ? "已启用" : "可用状态未知"}` : "平台免计次";
			},
			error: (e) => On(e, !1, t === "extraction" ? "幻光提链 CDK" : "幻光支付扫码 CDK")
		});
	}
	function F() {
		return e.isDirty("EXTRACT_LINK_HUANGUANG_API_BASE") ? w("huanguangXxsyun", "请先保存服务地址的更改，再查询剩余次数") : S("huanguangXxsyun", "/api/extract-link/huanguang/xxsyun-quota", $(_("EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY")), {
			posting: !0,
			apply: (e) => {
				Q(e.remainingUses) && (e.totalUses == null || Q(e.totalUses)) && (e.reservedUses == null || Q(e.reservedUses)) || Dn(), r.huanguangXxsyun.snapshot = {
					remainingUses: e.remainingUses,
					totalUses: e.totalUses ?? null,
					reservedUses: e.reservedUses ?? null
				}, r.huanguangXxsyun.text = `剩余 ${e.remainingUses} 次 · 总次数 ${e.totalUses ?? "未知"} · 占用 ${e.reservedUses ?? "未知"}`;
			},
			error: (e) => On(e)
		});
	}
	function I() {
		return e.isDirty("EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE") ? w("xxsyunBalance", "请先保存服务地址的更改，再查询积分") : S("xxsyunBalance", "/api/extract-link/payments/xxsyun/balance", $(_("EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY")), {
			posting: !0,
			apply: (e) => {
				let t = Y(e.balance), n = [
					"available_points",
					"pending_points",
					"used_points",
					"cost_points"
				];
				e.balance && !Array.isArray(e.balance) && n.every((e) => t[e] == null || En(t[e])) || Dn(), r.xxsyunBalance.snapshot = Object.fromEntries(n.map((e) => [e, t[e] ?? null]));
				let i = (e) => e == null ? "未知" : `${e} 积分`;
				r.xxsyunBalance.text = `可用 ${i(t.available_points)} · 预占 ${i(t.pending_points)} · 已用 ${i(t.used_points)} · 每单 ${i(t.cost_points)}`;
			},
			error: (e) => On(e, !0)
		});
	}
	function L(e) {
		return e && r.sentinel.snapshot?.running ? Promise.resolve() : S("sentinel", e ? "/api/maintenance/sentinel/check" : "/api/maintenance/sentinel", e ? $({}) : { method: "GET" }, {
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
		return S("sub2api", e ? "/api/sub2api/automation/check" : "/api/sub2api/automation", e ? $({}) : { method: "GET" }, {
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
					let e = Y(t.sync), n = Y(t.monitor), i = Y(e.counts);
					r.sub2api.text = `自动补传${e.enabled ? "已开启" : "已关闭"}；异常巡检${n.enabled ? "已开启" : "已关闭"}。待同步 ${i.pending ?? 0}，排队 ${i.queued ?? 0}，执行 ${i.running ?? 0}。`;
				}
			},
			error: () => "Sub2API 状态或巡检请求未完成，请稍后重试。"
		});
	}
	function ee() {
		return B(!1);
	}
	function te() {
		return B(!0);
	}
	function ne() {
		return S("concurrencyPreview", "/api/config/concurrency-preview", { method: "GET" }, {
			apply: (e) => {
				r.concurrencyPreview.snapshot = e;
			},
			error: () => "迁移预览暂不可用，请刷新重试。"
		});
	}
	async function V(e = {}) {
		let t = r.concurrencyPreview.snapshot ? Promise.resolve() : ne();
		await Promise.all([t, S("concurrency", `/api/operations/concurrency${e.details ? "?details=1" : ""}`, { method: "GET" }, {
			apply: (e) => {
				r.concurrency.snapshot = e;
				let t = Y(e.global);
				r.concurrency.text = `当前占用 ${t.occupied ?? 0} / ${t.limit ?? "—"}${t.draining ? "，等待现有任务结束" : ""}；预约 ${t.reserved ?? 0} · 执行 ${t.executing ?? 0} · 清理 ${t.cleaning ?? 0} · 调试保留 ${t.debug_hold ?? 0}；排队 ${e.queued ?? 0} · 远端等待 ${e.remote_waiting ?? "—"}`;
			},
			error: () => "状态读取失败，请重试；显示的数据为上次观察结果。"
		})]);
	}
	function re() {
		if (p) return [];
		let t = [];
		for (let [n, i] of Object.entries(Y(r.concurrencyPreview.snapshot?.proposed_values))) {
			let r = e.field(n);
			!r || r.group !== "并发控制" || r.type !== "int" || e.isDirty(n) || !Q(i) || Number(i) <= 0 || (e.setField(n, Number(i), { force: !0 }), t.push(n));
		}
		return r.concurrencyPreview.text = "迁移建议已填入草稿；核对全局和各类型上限后点击保存。", t;
	}
	function ie(e) {
		if (p) return;
		if (e.startsWith("REGISTRATION_")) {
			t.onNavigateTasks?.({ registration: !0 });
			return;
		}
		let n = Z(r.concurrency.snapshot?.types).map(Y).find((t) => t.config_key === e || t.key === e), i = n ? Z(n.task_types).length ? Z(n.task_types).map((e) => X(e)) : [X(n.key)] : [];
		t.onNavigateTasks?.({ types: [...new Set(i.filter(Boolean))] });
	}
	function ae(e, t) {
		p || s[e] === t || (s[e] = t, t ? d && f && (e === "sentinel" ? R() : V()) : (v(e), y(e, !0), e === "concurrency" && y("concurrencyPreview", !0)));
	}
	function oe(e) {
		if (!(p || d === e)) {
			d = e;
			for (let t of ["sentinel", "concurrency"]) v(t), e ? f && s[t] && (t === "sentinel" ? R() : V()) : (y(t, !0), t === "concurrency" && y("concurrencyPreview", !0));
		}
	}
	function se(e) {
		if (!(p || f === e)) {
			if (f = e, v("sentinel"), v("concurrency"), e) d && (s.sentinel && R(), s.concurrency && V());
			else for (let e of Cn) y(e, !0);
		}
	}
	function H() {
		if (!p) {
			p = !0, m.forEach((e) => e()), v("sentinel"), v("concurrency");
			for (let e of Cn) y(e, !0);
		}
	}
	return {
		states: r,
		extractTypeOptions: C(() => r.extractTypes.snapshot?.options || []),
		roxyWorkspaces: C(() => r.roxy.snapshot?.items || []),
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
		refreshSub2Api: ee,
		checkSub2Api: te,
		refreshConcurrency: V,
		loadConcurrencyPreview: ne,
		applyConcurrencyPreview: re,
		locateConcurrencyTasks: ie,
		setVisible: ae,
		setForeground: oe,
		setPageActive: se,
		dispose: H
	};
}
// src/features/config/useConfigActions.ts
function An(e, t = {}) {
	let n = kn(e, t), r = () => n.setForeground(!document.hidden);
	return typeof document < "u" && (r(), document.addEventListener("visibilitychange", r)), l(() => {
		typeof document < "u" && document.removeEventListener("visibilitychange", r), n.dispose();
	}), n;
}
// src/config.ts
function jn(t, n) {
	let r = Sn({ api: vn() }), i = w(), a = i.run(() => An(r, {
		onTaskReceipt: n.onTaskReceipt,
		onNavigateTasks: n.onNavigateTasks
	})), o = e(n.visible !== !1), l = null, u = c(r.fields, (e) => n.onSavedFields(e), { immediate: !0 }), d = r.subscribeSaved(() => n.onSaved?.()), f = x({ render: () => s(hn, {
		owner: r,
		actions: a,
		active: o.value,
		ref: (e) => {
			l = e;
		}
	}) });
	return f.mount(t), {
		load: () => r.initialize(),
		refresh: () => r.refresh({ force: !0 }),
		open: (e) => l?.open(e),
		setVisible: (e) => {
			o.value = e, a.setPageActive(e);
		},
		destroy: () => {
			u(), d(), f.unmount(), i.stop(), r.dispose();
		}
	};
}
export { jn as mountConfig };
