import { $ as e, A as t, C as n, E as r, F as i, H as a, J as o, K as s, L as c, M as l, Q as u, S as d, Z as f, _ as p, d as m, et as h, ft as g, g as _, h as v, j as y, lt as b, m as x, n as S, nt as C, o as w, s as T, st as E, t as D, v as O, x as k } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { n as ee } from "./time-DOD6oyhP.js";
import { r as A } from "./client-B5R_MNgP.js";
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
	补密码: [["密码补全策略", [
		"ACCOUNT_PASSWORD_DRIVER",
		"ACCOUNT_PASSWORD_RESET_ENABLED",
		"ACCOUNT_PASSWORD_CHANGE_REFRESH_BEFORE_RESET"
	]]],
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
	["ACCOUNT_PASSWORD_CHANGE_REFRESH_BEFORE_RESET", "补密码"],
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
function te(e) {
	return [
		"USE_EMAIL_SERVICE",
		"REGISTER_EMAIL",
		"OTP_MAX_WAIT",
		"OTP_RESEND_COUNT",
		"OTP_POLL_INTERVAL",
		"EMAIL_SOURCE"
	].includes(e) ? ["通用邮箱 / OTP", "邮箱来源选择、OTP 等待参数、手动邮箱等通用设置"] : e.startsWith("EMAIL_BUTLER_") ? ["Email Butler", "已导入邮箱的租约连接与取码权限"] : e.startsWith("REMAIL_") ? ["Remail", "历史 Remail 原订单收码连接；新邮箱请在邮箱服务中准备后导入"] : e.startsWith("ICLOUD_HME_") ? ["iCloud 隐藏邮箱", "已导入与历史隐藏邮箱的固定收件连接；邮箱管理在邮箱服务完成"] : ["其他邮箱配置", ""];
}
function B(e) {
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
function ne(e) {
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
function re(e) {
	return ["CODEX_OAUTH_DRIVER", "CODEX_AUTH_URL_SOURCE"].includes(e) ? ["基础配置", "Codex 授权驱动和授权地址来源配置"] : e.startsWith("CODEX_TOKEN_") ? ["Token 自动刷新", "使用 refresh_token 提前换新 Codex access token，不重新登录、不消耗邮箱 OTP 或短信"] : e.startsWith("CPA_") ? ["CPA配置", "CPA 授权链接生成、回调上传和管理接口配置"] : e.startsWith("SUB2API_") || e === "CODEX_OAUTH_AUTO_UPLOAD_SUB2API" ? ["sub2api", "sub2api 的 API 基址、鉴权和超时配置；用于 Codex OAuth 授权和凭证上传"] : ["基础配置", ""];
}
var V = new Map(R), ie = new Set(I), H = /* @__PURE__ */ new Map();
for (let [e, t] of Object.entries(F)) {
	let n = H.get(t);
	n ? n.push(e) : H.set(t, [e]);
}
var ae = /* @__PURE__ */ new WeakMap(), oe = /* @__PURE__ */ new WeakMap(), se = /* @__PURE__ */ new WeakMap(), ce = "gpt_console_config_group", le = {
	legacy: "虾扯蛋链",
	lumen_flow: "流光",
	huanguang: "幻光",
	anguang: "暗光（XXSYUN 一条龙）"
}, ue = /* @__PURE__ */ new Set([
	"EXTRACT_LINK_API_BASE",
	"EXTRACT_LINK_CDK",
	"EXTRACT_LINK_TYPE",
	"EXTRACT_LINK_REQUEST_TIMEOUT",
	"EXTRACT_LINK_EVENT_TIMEOUT"
]), de = {
	"1024proxy": "PROXY_1024_",
	"711proxy": "PROXY_711_"
};
function fe(e) {
	return ie.has(e.key) ? "注册与账号" : V.get(e.key) || e.group || "其他";
}
function U(e) {
	if (P[e]) return e;
	let t = F[e] || e || "其他";
	return Object.keys(P).find((e) => P[e].includes(t)) || t;
}
function W(e) {
	let t = ae.get(e);
	if (!t) {
		let n = /* @__PURE__ */ new Set();
		t = e.filter((e) => !e.hidden && !n.has(e.key) && !!n.add(e.key)).map((e) => ({
			...e,
			group: fe(e)
		})), ae.set(e, t);
	}
	return t;
}
function pe(e) {
	return W(e).slice();
}
function me(e) {
	let t = [...new Set(W(e).map((e) => U(e.group)))];
	return [...Object.keys(P).filter((e) => t.includes(e)), ...t.filter((e) => !P[e])];
}
function he(e, t) {
	let n = [...new Set(W(t).filter((t) => U(t.group) === e).map((e) => e.group))];
	return [...(P[e] || []).filter((e) => n.includes(e)), ...n.filter((t) => !(P[e] || []).includes(t))];
}
function ge(e) {
	return (e?.options || []).flatMap((e) => typeof e == "string" ? [{
		value: e,
		label: e
	}] : e && e.value != null ? [{
		...e,
		value: String(e.value),
		label: String(e.label ?? e.value)
	}] : []);
}
function _e(e) {
	let t = String(e ?? "roxy").trim().toLowerCase() || "roxy";
	return {
		protocol: "protocol_oss_2",
		protocol_oss: "protocol_oss_2",
		roxy_oss: "roxy"
	}[t] || t;
}
function ve(e) {
	let t = oe.get(e);
	if (!t) {
		let n = new Set(e.map((e) => e.key));
		t = ge(e.find((e) => e.key === "EXTRACT_LINK_DEFAULT_PROVIDER")).map((e) => ({
			...e,
			value: e.value.toLowerCase(),
			label: le[e.value.toLowerCase()] || e.label,
			enabledKey: `EXTRACT_LINK_${e.value.toUpperCase()}_ENABLED`
		})).filter((e) => n.has(e.enabledKey)), oe.set(e, t);
	}
	return t;
}
function ye(e) {
	return ve(e).slice();
}
function be(e, t) {
	let n = fe(e), r = e.key;
	if (n === "邮箱 / OTP") return te(r)[0];
	if (n === "代理与网络") return B(r)[0];
	if (n === "接码平台") return ne(r)[0];
	if (n === "Codex") return re(r)[0];
	if (n === "提链") {
		if (r.startsWith("EXTRACT_LINK_PAYMENT_")) return "独立支付";
		let e = ve(t);
		return e.some((e) => e.enabledKey === r) ? "通用配置" : e.find((e) => e.value === "legacy" ? ue.has(r) || r.startsWith("EXTRACT_LINK_LEGACY_") : r.startsWith(`EXTRACT_LINK_${e.value.toUpperCase()}_`))?.label || "通用配置";
	}
	return "";
}
var xe = {
	"邮箱 / OTP": [
		"通用邮箱 / OTP",
		"iCloud 隐藏邮箱",
		"Email Butler",
		"Remail",
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
function Se(e, t) {
	if (e === "提链") return [
		"通用配置",
		...ve(t).map((e) => e.label),
		"独立支付"
	];
	let n = [...new Set(W(t).filter((t) => t.group === e).map((e) => be(e, t)))].filter(Boolean), r = xe[e] || [];
	return e === "代理与网络" && n.unshift("任务用池"), [...r.filter((e) => n.includes(e)), ...n.filter((e) => !r.includes(e))];
}
function Ce(e, t) {
	let n = U(e), r = P[e] ? he(n, t)[0] || e : F[e] || e;
	return {
		menu: n,
		domain: r,
		section: Se(r, t)[0] || ""
	};
}
function we(e, t) {
	let n = fe(e);
	return {
		menu: U(n),
		domain: n,
		section: be(e, t)
	};
}
function Te(e, t) {
	let n = se.get(t);
	n || (n = /* @__PURE__ */ new Map(), se.set(t, n));
	let r = n.get(e.key);
	if (r && r.label === e.label && r.help === e.help && r.group === e.group) return r.text;
	let i = fe(e), a = [
		e.key,
		e.label,
		e.help,
		e.group,
		i,
		U(i),
		be(e, t),
		...H.get(i) || []
	].join(" ").toLowerCase();
	return n.set(e.key, {
		label: e.label,
		help: e.help,
		group: e.group,
		text: a
	}), a;
}
function Ee(e, t, n = "") {
	let r = e.trim().toLowerCase();
	if (!r) return null;
	let i = W(t), a = i.find((e) => e.key.toLowerCase() === r), o = i.filter((e) => Te(e, t).includes(r)), s = a || o.find((e) => U(e.group) === n) || o[0];
	if (s) return we(s, t);
	let c = me(t).find((e) => e.toLowerCase().includes(r));
	return c ? Ce(c, t) : null;
}
function De(e, t, n) {
	let r = W(e.fields.value).filter((n) => n.group === t.domain && (!t.section || be(n, e.fields.value) === t.section));
	if (t.domain === "提链" && t.section === "通用配置") {
		let t = new Set(ve(e.fields.value).map((e) => e.enabledKey));
		r = r.filter((e) => !t.has(e.key));
	}
	if (t.domain === "代理与网络" && t.section === "代理来源" && !n) {
		let t = String(e.readField("PROXY_POOL_SOURCE") || "1024proxy");
		r = r.filter((e) => {
			if (e.key === "PROXY_POOL") return t === "manual";
			let n = Object.keys(de).find((t) => e.key.startsWith(de[t]));
			return !n || t === n;
		});
	}
	return r.filter((e) => e.key !== "CONCURRENCY_POLICY_REVISION");
}
var Oe = {
	...L,
	C2A: [["C2A 连接", [
		"C2A_API_BASE",
		"C2A_API_KEY",
		"C2A_API_TIMEOUT"
	]], ["异常巡检", [
		"C2A_MONITOR_ENABLED",
		"C2A_MONITOR_INTERVAL_SECONDS",
		"C2A_MONITOR_COOLDOWN_SECONDS",
		"C2A_MONITOR_MAX_PER_CYCLE"
	]]],
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
function ke(e, t) {
	if (e === "注册与账号") return [{
		title: "查询套餐",
		fields: t
	}];
	let n = Oe[e];
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
function Ae(e) {
	return ["注册与账号", "邮箱与验证码"].includes(e) ? "业务流程" : [
		"代理与网络",
		"浏览器",
		"服务集成",
		"提链"
	].includes(e) ? "资源与服务" : "系统";
}
// src/features/config/ConfigNavigation.vue?vue&type=script&setup=true&lang.ts
var je = {
	class: "config-vue-navigation",
	"aria-label": "配置分类"
}, Me = { class: "config-vue-navigation-head" }, Ne = { class: "config-vue-search-box" }, Pe = ["value"], Fe = ["aria-expanded"], Ie = [
	"data-config-nav",
	"aria-current",
	"onClick"
], Le = { class: "config-vue-nav-label" }, Re = {
	key: 0,
	class: "config-vue-pending"
}, ze = {
	key: 0,
	class: "hint config-vue-no-match",
	role: "status"
}, Be = /* @__PURE__ */ n({
	__name: "ConfigNavigation",
	props: {
		owner: {},
		active: {},
		query: {}
	},
	emits: ["select", "search"],
	setup(e, { emit: n }) {
		let r = e, o = n, s = h(!1), l = h(), u = x(() => r.query.trim().toLowerCase()), d = x(() => me(r.owner.fields.value)), f = x(() => {
			let e = /* @__PURE__ */ new Map();
			for (let t of pe(r.owner.fields.value)) {
				let n = U(t.group), r = e.get(n) || [];
				r.push(t), e.set(n, r);
			}
			return e;
		}), _ = x(() => {
			let e = /* @__PURE__ */ new Map();
			for (let [t, n] of f.value) for (let r of n) e.set(r.key, t);
			return e;
		}), y = x(() => {
			let e = /* @__PURE__ */ new Map();
			for (let t of r.owner.dirtyKeys.value) {
				let n = _.value.get(t);
				n && e.set(n, (e.get(n) || 0) + 1);
			}
			return e;
		}), S = x(() => {
			let e = u.value, t = r.owner.fields.value, n = d.value.flatMap((n) => {
				let r = f.value.get(n) || [];
				return e && !n.toLowerCase().includes(e) && !r.some((n) => Te(n, t).includes(e)) ? [] : [{
					name: n,
					category: Ae(n),
					dirty: y.value.get(n) || 0
				}];
			});
			return [
				"业务流程",
				"资源与服务",
				"系统"
			].map((e) => ({
				name: e,
				items: n.filter((t) => t.category === e)
			})).filter((e) => e.items.length);
		});
		function C(e) {
			s.value = !1, o("select", e), t(() => {
				l.value?.getClientRects().length && l.value.focus({ preventScroll: !0 });
			});
		}
		return a(u, (e) => {
			s.value = !!e;
		}), (t, n) => (i(), O("nav", je, [v("div", Me, [
			n[4] ||= v("label", { for: "config-vue-search" }, "搜索配置", -1),
			v("div", Ne, [n[2] ||= v("svg", {
				class: "config-vue-search-icon",
				viewBox: "0 0 16 16",
				fill: "none",
				"aria-hidden": "true"
			}, [v("circle", {
				cx: "7",
				cy: "7",
				r: "4.5",
				stroke: "currentColor",
				"stroke-width": "1.4"
			}), v("path", {
				d: "M10.5 10.5L13.5 13.5",
				stroke: "currentColor",
				"stroke-width": "1.4",
				"stroke-linecap": "round"
			})], -1), v("input", {
				id: "config-vue-search",
				type: "search",
				value: e.query,
				placeholder: "搜索名称或配置键",
				onInput: n[0] ||= (e) => o("search", e.target.value)
			}, null, 40, Pe)]),
			v("button", {
				ref_key: "toggle",
				ref: l,
				type: "button",
				class: "config-vue-nav-toggle",
				"aria-expanded": s.value,
				"aria-controls": "config-vue-menu",
				"aria-label": "切换配置分类",
				onClick: n[1] ||= (e) => s.value = !s.value
			}, [v("span", null, g(e.active || "选择配置分类"), 1), n[3] ||= v("span", {
				class: "config-vue-chevron",
				"aria-hidden": "true"
			}, null, -1)], 8, Fe)
		]), v("div", {
			id: "config-vue-menu",
			class: b(["config-vue-menu", { "is-expanded": s.value }])
		}, [(i(!0), O(m, null, c(S.value, (t) => (i(), O("div", {
			key: t.name,
			class: "config-vue-nav-group"
		}, [v("p", null, g(t.name), 1), (i(!0), O(m, null, c(t.items, (t) => (i(), O("button", {
			key: t.name,
			type: "button",
			"data-config-nav": t.name,
			"aria-current": e.active === t.name ? "page" : void 0,
			onClick: (e) => C(t.name)
		}, [v("span", Le, g(t.name), 1), t.dirty ? (i(), O("small", Re, g(t.dirty) + " 待保存", 1)) : p("", !0)], 8, Ie))), 128))]))), 128)), u.value && !S.value.length ? (i(), O("p", ze, "未找到匹配配置")) : p("", !0)], 2)]));
	}
}), Ve = ["aria-label", "title"], He = { class: "config-vue-picker-menu" }, Ue = ["aria-label"], We = {
	key: 0,
	class: "config-vue-chips",
	"aria-label": "已选国家，可点击移除"
}, Ge = ["aria-label", "onClick"], Ke = ["aria-label"], qe = [
	"disabled",
	"aria-pressed",
	"title",
	"onClick"
], Je = {
	class: "config-vue-choice-mark",
	"aria-hidden": "true"
}, Ye = { class: "config-vue-choice-label" }, Xe = {
	key: 1,
	class: "hint config-vue-picker-empty",
	role: "status"
}, Ze = /* @__PURE__ */ n({
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
		return (t, n) => (i(), O("details", {
			ref_key: "root",
			ref: o,
			class: "config-vue-picker",
			onKeydown: _
		}, [v("summary", {
			"aria-label": `${e.label}：${d.value}`,
			title: d.value
		}, g(d.value), 9, Ve), v("div", He, [
			s(v("input", {
				"onUpdate:modelValue": n[0] ||= (e) => a.value = e,
				type: "search",
				"aria-label": `搜索${e.label}`,
				placeholder: "搜索并选择"
			}, null, 8, Ue), [[w, a.value]]),
			e.country && e.values.length ? (i(), O("div", We, [(i(!0), O(m, null, c(e.values, (e) => (i(), O("button", {
				key: e,
				type: "button",
				class: "config-vue-chip",
				"aria-label": `移除 ${e}`,
				onClick: (t) => f(e)
			}, g(l.value.find((t) => t.value === e)?.label || e) + " × ", 9, Ge))), 128))])) : p("", !0),
			v("div", {
				class: "config-vue-picker-options",
				"aria-label": e.label,
				role: "group"
			}, [(i(!0), O(m, null, c(u.value, (t) => (i(), O("button", {
				key: t.value,
				type: "button",
				"data-choice": "",
				disabled: t.disabled,
				"aria-pressed": e.values.includes(t.value),
				title: t.reason,
				onClick: (e) => f(t.value)
			}, [v("span", Je, g(e.values.includes(t.value) ? "✓" : "○"), 1), v("span", Ye, g(t.label), 1)], 8, qe))), 128))], 8, Ke),
			u.value.length ? p("", !0) : (i(), O("p", Xe, "未找到匹配选项"))
		])], 544));
	}
}), Qe = ["aria-busy"], $e = [
	"aria-label",
	"disabled",
	"data-config-field-action"
], et = /*#__PURE__*/ D(/* @__PURE__ */ n({
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
		return (t, n) => r.value && a.value ? (i(), O("div", {
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
		}, g(a.value.loading || a.value.posting ? "正在查询…" : r.value.label), 9, $e), a.value.error || a.value.text ? (i(), O("p", {
			key: 0,
			class: b(["config-setting-short-help-v2", { "config-action-error": a.value.error }]),
			role: "status",
			"aria-live": "polite"
		}, g(a.value.error || a.value.text), 3)) : p("", !0)], 8, Qe)) : p("", !0);
	}
}), [["__scopeId", "data-v-63c3ff8d"]]), tt = ["aria-busy"], nt = { class: "config-sub2api-input-row" }, rt = [
	"id",
	"value",
	"aria-label",
	"aria-describedby"
], it = ["disabled"], at = ["id"], ot = {
	class: "config-multi-options-v2",
	"data-sub2api-monitor-group-options": "",
	role: "group",
	"aria-label": "选择异常巡检分组"
}, st = [
	"data-sub2api-monitor-group-id",
	"checked",
	"onChange"
], ct = ["id"], lt = /* @__PURE__ */ n({
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
		return (t, n) => (i(), O("div", {
			class: "config-sub2api-groups-v2",
			"data-sub2api-monitor-groups": "",
			"aria-busy": o.value.loading
		}, [
			v("div", nt, [v("input", {
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
			}, null, 40, rt), v("button", {
				type: "button",
				class: "btn",
				"data-query-sub2api-groups": "",
				disabled: o.value.loading,
				onClick: n[1] ||= (t) => e.actions.querySub2ApiGroups()
			}, g(o.value.loading ? "正在查询…" : "查询分组"), 9, it)]),
			v("p", {
				id: `${e.id}-groups-help`,
				class: "config-setting-short-help-v2"
			}, " 使用已保存的 Sub2API 连接查询；可多选，不选时扫描全部分组，修改后点击保存生效。 ", 8, at),
			v("div", ot, [(i(!0), O(m, null, c(s.value, (e) => (i(), O("label", {
				key: e.value,
				class: b(["config-multi-option-v2", { "is-selected": a.value.includes(e.value) }])
			}, [v("input", {
				type: "checkbox",
				"data-sub2api-monitor-group-id": e.value,
				checked: a.value.includes(e.value),
				onChange: (t) => u(e.value, t.target.checked)
			}, null, 40, st), v("span", null, g(e.label), 1)], 2))), 128))]),
			v("p", {
				id: `${e.id}-groups-status`,
				class: "config-setting-short-help-v2 config-sub2api-status",
				"data-sub2api-monitor-groups-status": "",
				role: "status",
				"aria-live": "polite"
			}, g(l.value), 9, ct)
		], 8, tt));
	}
}), ut = ["data-config-setting"], dt = { class: "config-vue-field-copy" }, ft = { class: "config-vue-field-name" }, pt = ["for", "title"], mt = ["id"], ht = {
	key: 0,
	class: "config-hint-sep"
}, gt = { class: "config-hint-key" }, _t = { class: "config-hint-val" }, vt = {
	key: 2,
	class: "config-hint-sep"
}, yt = { key: 1 }, bt = { class: "config-vue-field-control" }, xt = {
	key: 0,
	class: "config-vue-readonly-note"
}, St = {
	key: 1,
	class: "config-vue-readonly-note"
}, Ct = ["disabled"], wt = {
	key: 1,
	class: "config-vue-composite"
}, Tt = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid"
], Et = [
	"value",
	"min",
	"step",
	"aria-label",
	"aria-invalid"
], Dt = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid",
	"aria-describedby",
	"disabled"
], Ot = [
	"value",
	"disabled",
	"title"
], kt = [
	"id",
	"data-key",
	"value",
	"aria-label",
	"aria-invalid",
	"aria-describedby",
	"placeholder"
], At = [
	"id",
	"data-key",
	"checked",
	"aria-label",
	"aria-invalid",
	"aria-describedby"
], jt = {
	class: "config-vue-switch-text",
	"aria-hidden": "true"
}, Mt = [
	"id",
	"data-key",
	"type",
	"value",
	"min",
	"max",
	"step",
	"placeholder",
	"aria-label",
	"aria-invalid",
	"aria-describedby"
], Nt = ["aria-label"], Pt = {
	key: 3,
	class: "hint"
}, Ft = {
	key: 4,
	class: "hint",
	role: "status"
}, It = ["id"], Lt, Rt = /* @__PURE__ */ new Map(), zt = /* @__PURE__ */ new Map();
function Bt(e) {
	let t = Rt.get(e);
	if (t !== void 0) return t;
	let n;
	try {
		Lt ??= new Intl.DisplayNames(["zh-CN"], { type: "region" }), n = `${Lt.of(e) || e} · ${e}`;
	} catch {
		n = e;
	}
	return Rt.set(e, n), n;
}
function Vt(e, t) {
	if (t && Object.keys(t).length > 0) return e.map((e) => {
		let n = t[e];
		return {
			value: e,
			label: n ? `${n} · ${e}` : Bt(e)
		};
	});
	let n = e.join(","), r = zt.get(n);
	return r || (zt.size >= 16 && zt.clear(), r = e.map((e) => ({
		value: e,
		label: Bt(e)
	})), zt.set(n, r)), r;
}
// src/features/config/ConfigField.vue
var G = /* @__PURE__ */ n({
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
		].includes(t.field.key) || t.field.type === "list_str_multiline" && !!(t.field.options?.length || t.field.csv_options?.length)), f = x(() => ge(t.field)), h = x(() => {
			let e = ["EMAIL_SOURCE", "ROXY_RANDOM_OS_CHOICES"].includes(t.field.key) ? /[,\n]+/ : l.value || d.value ? /[,\n\s]+/ : /\n/, r = (Array.isArray(n.value) ? n.value : String(n.value ?? "").split(e)).map((e) => e.trim()).filter(Boolean), i = s.value ? [...new Set(r.map((e) => e.toUpperCase()))] : r;
			return t.field.key === "EMAIL_SOURCE" && Array.isArray(t.field.options) ? i.filter((e) => f.value.some((t) => t.value === e)) : i;
		}), y = x(() => {
			let e = l.value || u.value ? Vt(t.field.country_codes || [], t.field.country_names) : f.value;
			return !e.length && t.field.csv_options && (e = t.field.csv_options.map((e) => ({
				value: e,
				label: e
			}))), t.field.key === "EXTRACT_LINK_TYPE" && t.actions?.extractTypeOptions.value.length && (e = t.actions.extractTypeOptions.value), t.field.key === "ACCOUNT_LIVE_CHECK_DRIVER" && !t.owner.readField("ACCOUNT_LIVE_CHECK_BROWSER_ENABLED") && (e = e.filter((e) => e.value !== "browser_roxy" || e.disabled)), t.field.key === "ACCOUNT_AT_REFRESH_COUNTRY" && (e = [{
				value: "",
				label: "跟随注册国家"
			}, ...e]), e;
		}), S = x(() => {
			let e = t.field.key === "REGISTRATION_DRIVER" ? _e(n.value) : String(n.value ?? "");
			return y.value.find((t) => t.value.toLowerCase() === e.trim().toLowerCase())?.value ?? e;
		}), C = x(() => {
			let e = y.value, t = S.value;
			return !d.value && !l.value && t && !e.some((e) => e.value === t) ? [{
				value: t,
				label: `当前配置（${t}）`
			}, ...e] : e;
		}), w = x(() => u.value || !!t.field.options?.length || t.field.key === "EXTRACT_LINK_TYPE" && C.value.length > 0), T = x(() => t.owner.readComposite(t.field.key) || (t.field.key === "PROXY_POOL_WAIT_TIMEOUT" ? {
			mode: Number(n.value) > 0 ? "timed" : "continuous",
			raw: Number(n.value) > 0 ? String(n.value) : ""
		} : {
			mode: String(n.value ?? "").trim() ? "limited" : "unlimited",
			raw: String(n.value ?? "")
		})), D = x(() => ["timed", "limited"].includes(T.value.mode));
		function ee(e) {
			t.owner.setComposite(t.field.key, {
				mode: e,
				raw: T.value.raw || (["timed", "limited"].includes(e) ? t.field.key === "SMS_MAX_PRICE" ? "0.1" : "60" : "")
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
		let P = x(() => t.owner.isDirty(t.field.key) ? t.field.secret && t.owner.secretDraft(t.field.key).mode === "clear" ? "待清除" : "待保存" : t.field.invalid_env ? "配置值无效，未生效" : t.field.secret ? t.field.configured ? "密钥已配置" : "未配置" : t.field.restart ? "已配置 · 需重启" : ""), F = x(() => t.owner.isDirty(t.field.key) ? t.field.secret && t.owner.secretDraft(t.field.key).mode === "clear" ? "is-clear" : "is-pending" : t.field.invalid_env ? "is-error" : t.field.secret ? t.field.configured ? "is-configured" : "is-unconfigured" : t.field.restart ? "is-restart" : ""), I = x(() => t.field.key === "ACCOUNT_CODEX_DRIVER"), L = x(() => t.field.type === "bool" && !t.legacy && !I.value), R = x(() => {
			let e = t.field.help;
			if (!e || !/[;；]/.test(e) || !/[A-Za-z0-9_]+=/.test(e)) return null;
			let n = e.split(/([;；])/), r = [], i = 0;
			for (let e = 0; e < n.length; e += 2) {
				let t = n[e] ?? "", a = n[e + 1] ?? "", o = t.match(/^(\s*)([A-Za-z0-9_.-]+)=([\s\S]*)$/);
				o ? (i++, r.push({
					leading: o[1] ?? "",
					key: o[2] ?? "",
					val: o[3] ?? "",
					raw: "",
					sep: a
				})) : (t || a) && r.push({
					leading: "",
					key: "",
					val: "",
					raw: t,
					sep: a
				});
			}
			return i >= 2 ? r : null;
		}), z = [
			"EXTRACT_LINK_HUANGUANG_CDK",
			"EXTRACT_LINK_HUANGUANG_PAYMENT_CDK",
			"EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY",
			"EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"
		];
		return (t, s) => (i(), O("div", {
			class: b(["config-vue-field", {
				"is-invalid": a.value,
				"is-dirty": e.owner.isDirty(e.field.key),
				"is-switch": L.value,
				"is-readonly": o.value || e.legacy || I.value,
				"is-secret": !!e.field.secret
			}]),
			"data-config-setting": e.field.key
		}, [v("div", dt, [
			v("div", ft, [v("label", {
				for: r.value,
				title: e.field.key
			}, g(e.field.label || e.field.key), 9, pt), P.value ? (i(), O("span", {
				key: 0,
				class: b(["config-vue-field-status", F.value]),
				role: "status"
			}, g(P.value), 3)) : p("", !0)]),
			e.field.help ? (i(), O("p", {
				key: 0,
				id: `${r.value}-help`,
				class: b(["hint", { "is-structured-hint": !!R.value }])
			}, [R.value ? (i(!0), O(m, { key: 0 }, c(R.value, (e, t) => (i(), O("span", {
				key: t,
				class: b(["config-hint-segment", { "is-plain": !e.key }])
			}, [e.key ? (i(), O(m, { key: 0 }, [
				e.leading ? (i(), O("span", ht, g(e.leading), 1)) : p("", !0),
				v("span", gt, g(e.key), 1),
				s[5] ||= v("span", { class: "config-hint-eq" }, "=", -1),
				v("span", _t, g(e.val), 1)
			], 64)) : (i(), O(m, { key: 1 }, [k(g(e.raw), 1)], 64)), e.sep ? (i(), O("span", vt, g(e.sep), 1)) : p("", !0)], 2))), 128)) : (i(), O(m, { key: 1 }, [k(g(e.field.help), 1)], 64))], 10, mt)) : p("", !0),
			e.field.label && e.field.label !== e.field.key ? (i(), O("code", yt, g(e.field.key), 1)) : p("", !0)
		]), v("div", bt, [
			e.legacy ? (i(), O("p", xt, "兼容保留")) : I.value ? (i(), O("p", St, g(E(ge)(e.owner.field("CODEX_OAUTH_DRIVER")).find((t) => t.value === e.owner.readField("CODEX_OAUTH_DRIVER"))?.label || e.owner.readField("CODEX_OAUTH_DRIVER")) + " · 由注册主链路统一维护 ", 1)) : (i(), O("fieldset", {
				key: 2,
				disabled: o.value,
				class: b(["config-vue-control-group", {
					"has-multiline": e.field.type === "list_str_multiline",
					"has-secret": !!e.field.secret
				}])
			}, [e.field.key === "SUB2API_MONITOR_GROUP_IDS" && e.actions ? (i(), _(lt, {
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
			])) : ["PROXY_POOL_WAIT_TIMEOUT", "SMS_MAX_PRICE"].includes(e.field.key) ? (i(), O("div", wt, [v("select", {
				id: r.value,
				"data-key": e.field.key,
				value: T.value.mode,
				"aria-label": e.field.key === "SMS_MAX_PRICE" ? "价格上限模式" : "领取等待模式",
				"aria-invalid": !!a.value,
				onChange: s[0] ||= (e) => ee(e.target.value)
			}, [e.field.key === "PROXY_POOL_WAIT_TIMEOUT" ? (i(), O(m, { key: 0 }, [s[6] ||= v("option", { value: "continuous" }, "持续等待", -1), s[7] ||= v("option", { value: "timed" }, "限时等待", -1)], 64)) : (i(), O(m, { key: 1 }, [s[8] ||= v("option", { value: "unlimited" }, "不设上限", -1), s[9] ||= v("option", { value: "limited" }, "设上限", -1)], 64))], 40, Tt), D.value ? (i(), O("input", {
				key: 0,
				type: "number",
				value: T.value.raw,
				min: e.field.key === "SMS_MAX_PRICE" ? 0 : 1,
				step: e.field.key === "SMS_MAX_PRICE" ? "0.001" : "1",
				"aria-label": e.field.key === "SMS_MAX_PRICE" ? "短信价格上限" : "限时等待秒数",
				"aria-invalid": !!a.value,
				onInput: s[1] ||= (t) => e.owner.setComposite(e.field.key, {
					mode: T.value.mode,
					raw: t.target.value
				})
			}, null, 40, Et)) : p("", !0)])) : l.value || d.value ? (i(), _(Ze, {
				key: 2,
				id: r.value,
				"data-key": e.field.key,
				label: e.field.label,
				country: l.value,
				values: h.value,
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
			])) : w.value ? (i(), O("select", {
				key: 3,
				id: r.value,
				"data-key": e.field.key,
				value: S.value,
				"aria-label": e.field.label,
				"aria-invalid": !!a.value,
				"aria-describedby": `${r.value}-help ${r.value}-error`,
				disabled: C.value.length === 1 || C.value.every((e) => e.disabled),
				onChange: s[2] ||= (e) => A(e.target.value)
			}, [(i(!0), O(m, null, c(C.value, (e) => (i(), O("option", {
				key: e.value,
				value: e.value,
				disabled: e.disabled,
				title: e.reason
			}, g(e.label) + g(e.disabled && e.reason ? `（${e.reason}）` : ""), 9, Ot))), 128))], 40, Dt)) : e.field.type === "list_str_multiline" ? (i(), O("textarea", {
				key: 4,
				id: r.value,
				"data-key": e.field.key,
				value: h.value.join("\n"),
				"aria-label": e.field.label,
				"aria-invalid": !!a.value,
				"aria-describedby": `${r.value}-help ${r.value}-error`,
				placeholder: e.field.secret ? "留空保留已有值" : "每行一条，可留空",
				onInput: j
			}, null, 40, kt)) : e.field.type === "bool" ? (i(), O("label", {
				key: 5,
				class: b(["config-vue-switch", { "is-checked": !!n.value }])
			}, [v("input", {
				id: r.value,
				"data-key": e.field.key,
				type: "checkbox",
				role: "switch",
				checked: !!n.value,
				"aria-label": e.field.label,
				"aria-invalid": !!a.value,
				"aria-describedby": `${r.value}-help ${r.value}-error`,
				onInput: j
			}, null, 40, At), v("span", jt, g(n.value ? "已开启" : "已关闭"), 1)], 2)) : (i(), O("input", {
				key: 6,
				id: r.value,
				"data-key": e.field.key,
				type: ["int", "float"].includes(e.field.type) ? "number" : e.field.secret ? "password" : "text",
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
			}, null, 40, Mt)), e.field.secret ? (i(), O("button", {
				key: 7,
				type: "button",
				class: "config-vue-secret-clear",
				"aria-label": `明确清除${e.field.label}`,
				onClick: s[3] ||= (t) => e.owner.clearSecret(e.field.key)
			}, " 清除 ", 8, Nt)) : p("", !0)], 10, Ct)),
			I.value ? (i(), O("p", Pt, "注册和账号补全共用同一套 Codex OAuth 执行方式，请到注册主链路修改。")) : p("", !0),
			e.field.reason ? (i(), O("p", Ft, g(e.field.reason), 1)) : p("", !0),
			a.value ? (i(), O("p", {
				key: 5,
				id: `${r.value}-error`,
				class: "config-vue-error",
				role: "alert"
			}, g(a.value), 9, It)) : p("", !0),
			e.actions && z.includes(e.field.key) ? (i(), _(et, {
				key: 6,
				actions: e.actions,
				"field-key": e.field.key
			}, null, 8, ["actions", "field-key"])) : p("", !0),
			e.actions && e.field.group === "并发控制" && e.field.key !== "GLOBAL_TASK_WORKERS" ? (i(), O("button", {
				key: 7,
				type: "button",
				class: "config-vue-locate-btn",
				onClick: s[4] ||= (t) => e.actions.locateConcurrencyTasks(e.field.key)
			}, " 定位任务 ")) : p("", !0)
		])], 10, ut));
	}
}), Ht = ["data-config-tool", "aria-busy"], Ut = { class: "config-tool-controls" }, Wt = ["value", "disabled"], Gt = ["value"], Kt = ["value"], qt = ["disabled"], Jt = ["disabled"], Yt = {
	key: 0,
	class: "config-tool-notice",
	role: "status"
}, Xt = { class: "config-tool-controls" }, Zt = ["disabled"], Qt = {
	key: 2,
	class: "config-tool-head config-tool-head--inline"
}, $t = ["disabled"], en = { class: "config-tool-controls" }, tn = ["disabled"], nn = ["disabled"], rn = { class: "config-tool-facts" }, an = { class: "config-tool-controls" }, on = ["disabled"], sn = ["disabled"], cn = { class: "config-tool-controls" }, ln = ["disabled"], un = ["disabled"], dn = { class: "config-tool-head config-tool-head--inline" }, fn = { class: "config-tool-controls" }, pn = ["disabled"], mn = ["disabled"], hn = {
	key: 0,
	class: "hint"
}, gn = {
	key: 1,
	class: "config-migration-preview"
}, _n = { class: "config-tool-controls" }, vn = ["disabled"], yn = ["disabled"], bn = {
	key: 2,
	class: "config-concurrency-types"
}, xn = { class: "config-concurrency-metrics" }, Sn = { key: 0 }, Cn = { key: 1 }, wn = ["onClick"], Tn = {
	key: 3,
	class: "config-concurrency-extra"
}, En = {
	key: 4,
	class: "config-tool-notice",
	role: "status"
}, Dn = /*#__PURE__*/ D(/* @__PURE__ */ n({
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
		let w = x(() => o(n.value.snapshot?.candidate)), T = x(() => o(n.value.snapshot?.builtin)), D = x(() => ({
			not_checked: "尚未检查",
			same: "同当前一致",
			version_changed: "发现新版本",
			content_changed: "同版本内容变化",
			unknown: "暂无法比较"
		})[s(n.value.snapshot?.comparison)] || "暂无法比较"), k = (e) => e === "static_markers_present" ? "通过（未运行验证）" : e === "needs_adaptation" ? "需要适配" : "尚未检查", A = x(() => {
			let e = Number(n.value.snapshot?.last_checked_at);
			return e > 0 && Number.isFinite(e) ? (/* @__PURE__ */ new Date(e * 1e3)).toLocaleString("zh-CN", { hour12: !1 }) : "尚未检查";
		}), j = x(() => l(n.value.snapshot?.types)), M = x(() => [
			"providers",
			"batches",
			"remote_orders"
		].flatMap((e) => l(n.value.snapshot?.[e]).map((e) => ({
			label: s(e.label || e.key || e.id || e.batch_id, "当前"),
			occupied: e.occupied ?? e.active ?? 0,
			limit: e.limit ?? "—"
		})))), N = x(() => t.actions.states.concurrencyPreview), P = (e) => {
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
		return (t, a) => (i(), O("div", {
			class: "config-tool-panel-v2 config-action-tools",
			"data-config-tool": e.tool,
			"aria-busy": r.value
		}, [e.tool === "roxy" ? (i(), O(m, { key: 0 }, [
			a[14] ||= v("div", { class: "config-tool-head" }, [v("strong", null, "团队 / 项目选择"), v("p", { class: "hint" }, "获取已保存连接中的团队与项目，选择后单独保存。")], -1),
			v("div", Ut, [
				v("label", null, [a[13] ||= v("span", null, "团队 / 项目", -1), v("select", {
					"aria-label": "团队 / 项目",
					value: u.value,
					disabled: r.value || !!S.value,
					onChange: d
				}, [h.value ? p("", !0) : (i(), O("option", {
					key: 0,
					value: u.value
				}, " 当前团队：" + g(e.owner.readField("ROXY_WORKSPACE_ID") || "未设置"), 9, Gt)), (i(!0), O(m, null, c(e.actions.roxyWorkspaces.value, (e) => (i(), O("option", {
					key: `${e.id}::${e.projectId}`,
					value: `${e.id}::${e.projectId}`
				}, g(e.label), 9, Kt))), 128))], 40, Wt)]),
				v("button", {
					type: "button",
					class: "btn",
					"data-config-action": "load-roxy",
					disabled: r.value || !!S.value,
					onClick: a[0] ||= (t) => e.actions.loadRoxyWorkspaces()
				}, g(n.value.loading ? "正在获取…" : "获取团队"), 9, qt),
				v("button", {
					type: "button",
					class: "btn primary",
					"data-config-action": "save-roxy",
					disabled: r.value || !h.value || !!S.value,
					onClick: f
				}, g(n.value.posting ? "正在保存…" : "保存选择"), 9, Jt)
			]),
			S.value ? (i(), O("p", Yt, g(S.value), 1)) : p("", !0)
		], 64)) : e.tool === "proxy" ? (i(), O(m, { key: 1 }, [a[15] ||= v("div", { class: "config-tool-head" }, [v("strong", null, "代理供应商本地联调"), v("p", { class: "hint" }, "会实际提取并检测 1 个 IP，可能产生少量流量或配额消耗。API 请求会绕过系统代理。")], -1), v("div", Xt, [v("button", {
			type: "button",
			class: "btn",
			"data-config-action": "test-proxy",
			disabled: r.value,
			onClick: a[1] ||= (t) => e.actions.testProxy()
		}, g(r.value ? "正在测试…" : "提取并测试 1 个 IP"), 9, Zt)])], 64)) : e.tool === "butler" ? (i(), O("div", Qt, [a[16] ||= v("strong", null, "Email Butler 连接与权限", -1), v("button", {
			type: "button",
			class: "btn",
			"data-config-action": "test-butler",
			disabled: r.value,
			onClick: a[2] ||= (t) => e.actions.testButler()
		}, g(r.value ? "正在检测…" : "测试连接与权限"), 9, $t)])) : e.tool === "sentinel" ? (i(), O(m, { key: 3 }, [
			a[23] ||= v("div", { class: "config-tool-head" }, [v("strong", null, "Sentinel 检查"), v("p", { class: "hint" }, "手动获取候选资源；不自动切换现用版本。")], -1),
			v("div", en, [v("button", {
				type: "button",
				class: "btn",
				"data-config-action": "check-sentinel",
				disabled: r.value || !!n.value.snapshot?.running,
				onClick: a[3] ||= (t) => e.actions.checkSentinel()
			}, g(n.value.posting || n.value.snapshot?.running ? "检查中…" : "检查 Sentinel 更新"), 9, tn), v("button", {
				type: "button",
				class: "btn",
				disabled: r.value,
				onClick: a[4] ||= (t) => e.actions.refreshSentinel()
			}, "刷新状态", 8, nn)]),
			v("dl", rn, [
				v("div", null, [a[17] ||= v("dt", null, "当前内置版本", -1), v("dd", null, g(s(T.value.version, "读取后显示")), 1)]),
				v("div", null, [a[18] ||= v("dt", null, "发现版本", -1), v("dd", null, g(s(w.value.version, "尚未发现")), 1)]),
				v("div", null, [a[19] ||= v("dt", null, "上次检查时间", -1), v("dd", null, g(A.value), 1)]),
				v("div", null, [a[20] ||= v("dt", null, "版本比较", -1), v("dd", null, g(D.value), 1)]),
				v("div", null, [a[21] ||= v("dt", null, "generic 静态检查", -1), v("dd", null, g(k(w.value.generic_status)), 1)]),
				v("div", null, [a[22] ||= v("dt", null, "Proto2 静态检查", -1), v("dd", null, g(k(w.value.proto2_status)), 1)])
			])
		], 64)) : e.tool === "sub2api" ? (i(), O(m, { key: 4 }, [a[24] ||= v("div", { class: "config-tool-head" }, [v("strong", null, "同步与异常巡检"), v("p", { class: "hint" }, "使用已保存配置检查远端异常账号，修复进度可在任务中心查看。")], -1), v("div", an, [v("button", {
			type: "button",
			class: "btn",
			disabled: r.value,
			onClick: a[5] ||= (t) => e.actions.refreshSub2Api()
		}, "查看状态", 8, on), v("button", {
			type: "button",
			class: "btn",
			"data-config-action": "check-sub2api",
			disabled: r.value,
			onClick: a[6] ||= (t) => e.actions.checkSub2Api()
		}, " 立即巡检 ", 8, sn)])], 64)) : e.tool === "c2a" ? (i(), O(m, { key: 5 }, [a[25] ||= v("div", { class: "config-tool-head" }, [v("strong", null, "C2A 同步与异常巡检"), v("p", { class: "hint" }, "立即巡检使用已保存的 C2A 配置，扫描和修复任务可在任务中心查看。")], -1), v("div", cn, [v("button", {
			type: "button",
			class: "btn",
			disabled: r.value,
			onClick: a[7] ||= (t) => e.actions.refreshC2a()
		}, "查看状态", 8, ln), v("button", {
			type: "button",
			class: "btn",
			"data-config-action": "check-c2a",
			disabled: r.value,
			onClick: a[8] ||= (t) => e.actions.checkC2a()
		}, " 立即巡检 ", 8, un)])], 64)) : e.tool === "concurrency" ? (i(), O(m, { key: 6 }, [
			v("div", dn, [a[26] ||= v("strong", null, "并发运行状态", -1), v("div", fn, [v("button", {
				type: "button",
				class: "btn",
				disabled: r.value,
				onClick: a[9] ||= (t) => e.actions.refreshConcurrency()
			}, "刷新状态", 8, pn), v("button", {
				type: "button",
				class: "btn",
				disabled: r.value,
				onClick: a[10] ||= (t) => e.actions.refreshConcurrency({ details: !0 })
			}, " 查看附加限制 ", 8, mn)])]),
			n.value.snapshot ? (i(), O("p", hn, " 部署范围 " + g(s(o(n.value.snapshot.scope).label || n.value.snapshot.scope, "当前部署")) + " · 策略版本 " + g(s(n.value.snapshot.policy_revision)) + " · 观察时间 " + g(E(ee)(n.value.snapshot.observed_at)), 1)) : p("", !0),
			a[27] ||= v("p", { class: "config-section-v2-subhelp" }, " 各类型上限是上限，不预留配额，合计可以超过全局。内部同步刷新 AT、查套餐与后处理归属巡检、提链或注册父任务，复用父任务许可；独立子任务按实际动作重新排队。 ", -1),
			N.value.snapshot?.migration_required || n.value.snapshot?.migration_required ? (i(), O("div", gn, [
				v("p", null, "新策略需要完整保存。历史账号池上限：" + g(s(N.value.snapshot?.legacy_account_workers, "未记录")), 1),
				(i(!0), O(m, null, c(Array.isArray(N.value.snapshot?.notes) ? N.value.snapshot.notes : [], (e, t) => (i(), O("p", { key: t }, g(s(e, "")), 1))), 128)),
				v("div", _n, [v("button", {
					type: "button",
					class: "btn",
					disabled: !N.value.snapshot,
					onClick: a[11] ||= (t) => e.actions.applyConcurrencyPreview()
				}, " 填入迁移建议 ", 8, vn), N.value.error ? (i(), O("button", {
					key: 0,
					type: "button",
					class: "btn",
					disabled: N.value.loading,
					onClick: a[12] ||= (t) => e.actions.loadConcurrencyPreview()
				}, " 重试迁移预览 ", 8, yn)) : p("", !0)])
			])) : p("", !0),
			j.value.length ? (i(), O("ul", bn, [(i(!0), O(m, null, c(j.value, (t) => (i(), O("li", { key: s(t.key) }, [v("div", null, [
				v("strong", null, g(s(t.label || t.key)), 1),
				v("span", xn, " 占用 " + g(t.occupied ?? 0) + " / " + g(t.limit ?? "—") + " · 排队 " + g(t.queued ?? 0) + g(t.draining ? " · 等待现有任务结束" : ""), 1),
				Number(e.owner.readField(s(t.config_key))) > Number(o(n.value.snapshot?.global).limit) ? (i(), O("small", Sn, " 当前实际最多受全局 " + g(o(n.value.snapshot?.global).limit) + " 限制；保存后的类型值仍会保留。 ", 1)) : p("", !0),
				Array.isArray(t.blocked_by) && t.blocked_by.length ? (i(), O("small", Cn, g(t.blocked_by.map(P).join("；")), 1)) : p("", !0)
			]), v("button", {
				type: "button",
				class: "btn",
				onClick: (n) => e.actions.locateConcurrencyTasks(s(t.config_key || t.key))
			}, " 定位任务 ", 8, wn)]))), 128))])) : p("", !0),
			M.value.length ? (i(), O("ul", Tn, [(i(!0), O(m, null, c(M.value, (e, t) => (i(), O("li", { key: t }, g(e.label) + "：" + g(e.occupied) + " / " + g(e.limit), 1))), 128))])) : p("", !0),
			a[28] ||= v("details", { class: "config-concurrency-details-v2" }, [
				v("summary", null, "业务附加限制与计量说明"),
				v("p", { class: "hint" }, " 注册批次并发填写正整数，提链批次与平台保留 1–50；它们与全局、类型限制同时生效。XXSYUN 未结束订单名额在远端等待时仍占用，本地查询间隔不占执行槽。调试保留、停止清理和已预约执行仍计入占用。 "),
				v("p", { class: "hint" }, " 账号补全等待独立子任务时不重复占全局槽；HME 合并扫描按一个扫描 Run 计数；邮箱导入按实际远端交接调用计数。Sub2API 远端账号并发属性在服务集成中维护。 ")
			], -1),
			N.value.text || N.value.error ? (i(), O("p", En, g(N.value.error || N.value.text), 1)) : p("", !0)
		], 64)) : p("", !0), v("p", {
			class: b(["config-action-status", { "config-action-error": n.value.error }]),
			role: "status",
			"aria-live": "polite"
		}, g(n.value.error || n.value.text || (r.value ? "正在请求…" : "尚未查询")), 3)], 8, Ht));
	}
}), [["__scopeId", "data-v-6b33ece4"]]), On = {
	key: 0,
	class: "config-vue-banner",
	role: "status"
}, kn = {
	key: 1,
	class: "config-vue-banner config-vue-error",
	role: "alert"
}, An = {
	key: 2,
	class: "config-vue-banner config-vue-error",
	role: "status"
}, jn = {
	key: 3,
	class: "config-vue-error-summary",
	role: "alert",
	tabindex: "-1"
}, Mn = ["onClick"], Nn = { class: "config-vue-layout" }, Pn = {
	key: 0,
	class: "config-vue-content"
}, Fn = { class: "config-vue-content-header" }, In = ["aria-label"], Ln = [
	"data-config-domain-v2",
	"aria-pressed",
	"onClick"
], Rn = ["aria-label"], zn = [
	"data-config-subsection",
	"aria-pressed",
	"onClick"
], Bn = ["data-config-section"], Vn = {
	key: 0,
	class: "config-vue-table-card"
}, Hn = { class: "config-vue-pool-rules" }, Un = {
	key: 1,
	class: "config-vue-subblock config-vue-subblock--inputs"
}, Wn = { class: "config-vue-input-card" }, Gn = { class: "config-vue-field" }, Kn = { class: "config-vue-field-control" }, qn = {
	key: 0,
	class: "config-vue-subblock config-vue-subblock--switches"
}, Jn = { class: "config-vue-switch-grid" }, Yn = {
	key: 1,
	class: "config-vue-subblock config-vue-subblock--inputs"
}, Xn = { class: "config-vue-input-card" }, Zn = ["open"], Qn = { class: "config-vue-advanced-body" }, $n = {
	key: 0,
	class: "config-vue-subblock config-vue-subblock--switches"
}, er = { class: "config-vue-switch-grid" }, tr = {
	key: 1,
	class: "config-vue-subblock config-vue-subblock--inputs"
}, nr = { class: "config-vue-input-card" }, rr = { key: 0 }, ir = {
	key: 1,
	class: "config-vue-subblock config-vue-subblock--switches"
}, ar = { class: "config-vue-switch-grid" }, or = {
	key: 2,
	class: "config-vue-subblock config-vue-subblock--inputs"
}, sr = { class: "config-vue-input-card" }, cr = {
	key: 4,
	class: "hint config-vue-section-note"
}, lr = {
	key: 5,
	class: "hint config-vue-section-note"
}, ur = {
	key: 4,
	class: "config-vue-savebar"
}, dr = {
	class: "config-vue-save-state",
	role: "status",
	"aria-live": "polite"
}, fr = { key: 0 }, pr = { key: 1 }, mr = { key: 2 }, hr = { class: "config-vue-save-actions" }, gr = ["disabled"], _r = ["disabled"], vr = /* @__PURE__ */ n({
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
		let r = e, o = h(""), f = u({
			menu: "",
			domain: "",
			section: ""
		}), b = h(), S = {}, C = {}, w = x(() => !!o.value.trim()), E = x(() => he(f.menu, r.owner.fields.value)), D = x(() => Se(f.domain, r.owner.fields.value)), k = x(() => De(r.owner, f, w.value)), ee = x(() => ke(f.domain, k.value)), A = /* @__PURE__ */ new Set([
			"PROXY_POOL_SOURCE",
			"PROXY_POOL_DEFAULT_COUNTRY",
			"PROXY_POOL",
			...["PROXY_1024_", "PROXY_711_"].flatMap((e) => [
				"API_URL",
				"PROTOCOL",
				"SESSION_MINUTES"
			].map((t) => `${e}${t}`))
		]), j = x(() => k.value.filter((e) => A.has(e.key))), M = x(() => k.value.filter((e) => !A.has(e.key)));
		function N(e, t = !1) {
			return e.type === "bool" && !t && e.key !== "ACCOUNT_CODEX_DRIVER";
		}
		function F(e, t = !1) {
			let n = [], r = [];
			for (let i of e) N(i, t) ? n.push(i) : r.push(i);
			return {
				switches: n,
				inputs: r
			};
		}
		let I = x(() => F(j.value)), L = x(() => F(M.value)), R = x(() => {
			let e = f.domain === "代理与网络" && f.section === "高级兼容";
			return ee.value.map((t) => ({
				title: t.title,
				legacy: e,
				...F(t.fields, e)
			}));
		}), z = x(() => ye(r.owner.fields.value)), te = x(() => z.value.filter((e) => r.owner.readField(e.enabledKey) === !0).map((e) => e.value)), B = x(() => Object.entries(r.owner.fieldErrors)), ne = x(() => f.domain === "RoxyBrowser" ? "roxy" : f.domain === "代理与网络" && f.section === "代理来源" && r.owner.readField("PROXY_POOL_SOURCE") !== "manual" ? "proxy" : f.domain === "邮箱 / OTP" && f.section === "Email Butler" ? "butler" : f.domain === "通用配置" ? "sentinel" : f.domain === "Codex" && f.section === "sub2api" ? "sub2api" : f.domain === "C2A" ? "c2a" : f.domain === "并发控制" ? "concurrency" : null);
		function re() {
			try {
				localStorage.setItem(ce, f.domain || f.menu);
			} catch {}
		}
		function V() {
			t(() => {
				let e = b.value?.querySelector(".config-vue-content"), t = !!(e?.scrollTop || e?.scrollLeft || window.scrollY || window.scrollX || document.documentElement.scrollTop);
				e && (e.scrollTop = 0, e.scrollLeft = 0), t && window.scrollTo({
					top: 0,
					left: 0,
					behavior: "auto"
				});
			});
		}
		function ie(e) {
			let t = Ce(e, r.owner.fields.value);
			P[e] && S[t.menu] && (t.domain = S[t.menu]), t.section = C[t.domain] || Se(t.domain, r.owner.fields.value)[0] || "", Object.assign(f, t), re(), V();
		}
		function H(e) {
			f.domain = e, S[f.menu] = e, f.section = C[e] || Se(e, r.owner.fields.value)[0] || "", re(), V();
		}
		function ae(e) {
			f.section = e, C[f.domain] = e, V();
		}
		function oe(e) {
			o.value = e;
			let t = Ee(e, r.owner.fields.value, f.menu);
			!t || f.menu === t.menu && f.domain === t.domain && f.section === t.section || (Object.assign(f, t), V());
		}
		function se(e) {
			for (let t of z.value) r.owner.setField(t.enabledKey, e.includes(t.value));
		}
		async function le(e) {
			let n = r.owner.field(e);
			if (!n) return;
			o.value.trim() && !Te(n, r.owner.fields.value).includes(o.value.trim().toLowerCase()) && (o.value = ""), Object.assign(f, we(n, r.owner.fields.value)), re(), await t();
			let i = Array.from(b.value?.querySelectorAll("[data-config-setting]") || []).find((t) => t.dataset.configSetting === e);
			i?.querySelectorAll("details").forEach((e) => {
				e.open = !0;
			});
			let a = i?.closest("details");
			a && (a.open = !0);
			let s = i?.querySelector("input:not([type=hidden]),select,textarea,summary,button");
			s?.focus(), s?.scrollIntoView?.({ block: "nearest" });
		}
		function ue() {
			r.owner.dirtyCount.value && window.confirm("确定撤销全部未保存的配置修改？") && r.owner.reset();
		}
		function de(e) {
			r.owner.dirtyCount.value && (e.preventDefault(), e.returnValue = "");
		}
		async function fe() {
			let e = await r.owner.saveAll();
			if (e.status === "validation-error") {
				let t = Object.keys(e.fields || {})[0];
				t && r.owner.navigateField(t);
			}
		}
		a(() => r.owner.navigationTarget.value, (e) => {
			e && le(e.key);
		}), a(() => r.active, (e) => r.actions.setPageActive(e), { immediate: !0 }), y(() => {
			r.actions.setPageActive(!1), window.removeEventListener("beforeunload", de);
		}), a(() => r.owner.fields.value, () => {
			let e = me(r.owner.fields.value);
			if (e.length) {
				if (!f.menu) {
					let t = "";
					try {
						t = localStorage.getItem("gpt_console_config_group") || "";
					} catch {}
					Object.assign(f, Ce(t || e[0], r.owner.fields.value));
				}
				e.includes(f.menu) || Object.assign(f, Ce(e[0], r.owner.fields.value)), E.value.includes(f.domain) || (f.domain = E.value[0] || f.menu), D.value.includes(f.section) || (f.section = D.value[0] || "");
			}
		}, { immediate: !0 }), l(() => {
			window.addEventListener("beforeunload", de), r.owner.initialize().catch(() => {}), r.actions.loadExtractTypes();
		}), n({
			open: ie,
			focusField: le
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
		return (t, n) => (i(), O("div", {
			ref_key: "root",
			ref: b,
			class: "config-vue-page"
		}, [
			e.owner.loading.value ? (i(), O("p", On, "正在读取配置…")) : p("", !0),
			e.owner.error.value ? (i(), O("p", kn, g(e.owner.error.value), 1)) : p("", !0),
			e.owner.refreshError.value ? (i(), O("p", An, [v("span", null, g(e.owner.refreshError.value), 1), v("button", {
				type: "button",
				onClick: n[0] ||= (t) => e.owner.refresh({ force: !0 })
			}, "重新读取配置")])) : p("", !0),
			B.value.length ? (i(), O("div", jn, [v("strong", null, "请检查 " + g(B.value.length) + " 项配置，草稿已保留", 1), v("ul", null, [(i(!0), O(m, null, c(B.value, ([t, n]) => (i(), O("li", { key: t }, [v("button", {
				type: "button",
				onClick: (n) => e.owner.navigateField(t)
			}, g(e.owner.field(t)?.label || t) + "：" + g(n), 9, Mn)]))), 128))])])) : p("", !0),
			v("div", Nn, [d(Be, {
				owner: e.owner,
				active: f.menu,
				query: o.value,
				onSelect: ie,
				onSearch: oe
			}, null, 8, [
				"owner",
				"active",
				"query"
			]), f.domain ? (i(), O("div", Pn, [v("header", Fn, [
				v("h2", null, g(E.value.length > 1 ? f.menu : f.domain === "注册与账号" ? "查询套餐" : f.domain), 1),
				s(v("div", {
					class: "config-vue-tabs config-vue-domains",
					role: "group",
					"aria-label": `${f.menu}配置领域`
				}, [(i(!0), O(m, null, c(E.value, (e) => (i(), O("button", {
					key: e,
					type: "button",
					"data-config-domain-v2": e,
					"aria-pressed": f.domain === e,
					onClick: (t) => H(e)
				}, g(e === "注册与账号" ? "查询套餐" : e), 9, Ln))), 128))], 8, In), [[T, E.value.length > 1]]),
				D.value.length ? (i(), O("div", {
					key: 0,
					class: "config-vue-tabs config-vue-subsections",
					role: "group",
					"aria-label": `${f.domain}配置分类`
				}, [(i(!0), O(m, null, c(D.value, (e) => (i(), O("button", {
					key: e,
					type: "button",
					"data-config-subsection": e,
					"aria-pressed": f.section === e,
					onClick: (t) => ae(e)
				}, g(e), 9, zn))), 128))], 8, Rn)) : p("", !0)
			]), v("section", {
				class: "config-vue-editor",
				"data-config-section": f.domain
			}, [
				f.domain === "代理与网络" && f.section === "任务用池" ? (i(), O("div", Vn, [v("table", Hn, [
					n[1] ||= v("caption", null, "任务用池规则", -1),
					n[2] ||= v("thead", null, [v("tr", null, [
						v("th", null, "任务"),
						v("th", null, "国家需求"),
						v("th", null, "领取规则")
					])], -1),
					v("tbody", null, [(i(), O(m, null, c(U, (e) => v("tr", { key: e[0] }, [(i(!0), O(m, null, c(e, (e) => (i(), O("td", { key: e }, g(e), 1))), 128))])), 64))])
				])])) : p("", !0),
				f.domain === "提链" && f.section === "通用配置" ? (i(), O("div", Un, [v("div", Wn, [v("div", Gn, [n[3] ||= v("div", { class: "config-vue-field-copy" }, [v("div", { class: "config-vue-field-name" }, [v("label", null, "启用平台")]), v("p", { class: "hint" }, "选择允许在提链工作台中使用的平台；取消选择不会清除该平台的地址或 CDK。")], -1), v("div", Kn, [d(Ze, {
					label: "启用平台",
					values: te.value,
					options: z.value,
					onChange: se
				}, null, 8, ["values", "options"])])])])])) : p("", !0),
				f.domain === "代理与网络" && f.section === "代理来源" ? (i(), O(m, { key: 2 }, [
					I.value.switches.length ? (i(), O("div", qn, [v("div", Jn, [(i(!0), O(m, null, c(I.value.switches, (t) => (i(), _(G, {
						key: t.key,
						owner: e.owner,
						field: t,
						actions: e.actions
					}, null, 8, [
						"owner",
						"field",
						"actions"
					]))), 128))])])) : p("", !0),
					I.value.inputs.length ? (i(), O("div", Yn, [v("div", Xn, [(i(!0), O(m, null, c(I.value.inputs, (t) => (i(), _(G, {
						key: t.key,
						owner: e.owner,
						field: t,
						actions: e.actions
					}, null, 8, [
						"owner",
						"field",
						"actions"
					]))), 128))])])) : p("", !0),
					M.value.length ? (i(), O("details", {
						key: 2,
						class: "config-vue-source-advanced",
						open: w.value
					}, [n[4] ||= v("summary", null, "高级提取与检测参数", -1), v("div", Qn, [L.value.switches.length ? (i(), O("div", $n, [v("div", er, [(i(!0), O(m, null, c(L.value.switches, (t) => (i(), _(G, {
						key: t.key,
						owner: e.owner,
						field: t,
						actions: e.actions
					}, null, 8, [
						"owner",
						"field",
						"actions"
					]))), 128))])])) : p("", !0), L.value.inputs.length ? (i(), O("div", tr, [v("div", nr, [(i(!0), O(m, null, c(L.value.inputs, (t) => (i(), _(G, {
						key: t.key,
						owner: e.owner,
						field: t,
						actions: e.actions
					}, null, 8, [
						"owner",
						"field",
						"actions"
					]))), 128))])])) : p("", !0)])], 8, Zn)) : p("", !0)
				], 64)) : (i(!0), O(m, { key: 3 }, c(R.value, (t) => (i(), O("div", {
					key: t.title,
					class: "config-vue-setting-group"
				}, [
					t.title ? (i(), O("h3", rr, g(t.title), 1)) : p("", !0),
					t.switches.length ? (i(), O("div", ir, [v("div", ar, [(i(!0), O(m, null, c(t.switches, (n) => (i(), _(G, {
						key: n.key,
						owner: e.owner,
						field: n,
						actions: e.actions,
						legacy: t.legacy
					}, null, 8, [
						"owner",
						"field",
						"actions",
						"legacy"
					]))), 128))])])) : p("", !0),
					t.inputs.length ? (i(), O("div", or, [v("div", sr, [(i(!0), O(m, null, c(t.inputs, (n) => (i(), _(G, {
						key: n.key,
						owner: e.owner,
						field: n,
						actions: e.actions,
						legacy: t.legacy
					}, null, 8, [
						"owner",
						"field",
						"actions",
						"legacy"
					]))), 128))])])) : p("", !0)
				]))), 128)),
				f.domain === "邮箱 / OTP" && f.section === "iCloud 隐藏邮箱" ? (i(), O("p", cr, " 隐藏邮箱的创建、状态与管理请在邮箱服务（Email Butler）中完成。本页只维护已导入与历史邮箱的固定收件连接。 ")) : p("", !0),
				f.domain === "注册调试" ? (i(), O("p", lr, " “调试模式”仍是单个注册批次的现场保留开关，本页只控制失败诊断、保留时长和抓包预算。 ")) : p("", !0),
				ne.value ? (i(), _(Dn, {
					key: ne.value,
					owner: e.owner,
					actions: e.actions,
					tool: ne.value,
					active: e.active
				}, null, 8, [
					"owner",
					"actions",
					"tool",
					"active"
				])) : p("", !0)
			], 8, Bn)])) : p("", !0)]),
			e.owner.dirtyCount.value || e.owner.receipt.value ? (i(), O("div", ur, [v("div", dr, [
				v("strong", null, g(B.value.length ? "请检查标记的配置项" : e.owner.error.value ? "保存失败，请重试" : e.owner.dirtyCount.value ? `${e.owner.dirtyCount.value} 项待保存` : "配置已保存"), 1),
				e.owner.error.value && !B.value.length ? (i(), O("span", fr, "请检查网络或服务状态后重试")) : p("", !0),
				e.owner.receipt.value ? (i(), O("span", pr, " 数据库保存" + g(e.owner.receipt.value.persistedDbRevision === null ? "成功" : `版本 ${e.owner.receipt.value.persistedDbRevision}`) + " · Worker " + g(e.owner.receipt.value.workerApplication.state === "applied" ? "已应用" : e.owner.receipt.value.workerApplication.state === "error" ? "应用异常" : e.owner.receipt.value.workerApplication.state === "pending" ? "等待应用" : "应用状态待确认"), 1)) : p("", !0),
				e.owner.receipt.value?.restartRequired.length ? (i(), O("span", mr, " 需重启：" + g(e.owner.receipt.value.restartRequired.join("、")), 1)) : p("", !0)
			]), v("div", hr, [v("button", {
				type: "button",
				disabled: !e.owner.dirtyCount.value || e.owner.saving.value,
				onClick: ue
			}, "撤销修改", 8, gr), v("button", {
				type: "button",
				class: "primary",
				disabled: !e.owner.dirtyCount.value || e.owner.saving.value,
				onClick: fe
			}, g(e.owner.saving.value ? "正在保存…" : "保存全部配置"), 9, _r)])])) : p("", !0)
		], 512));
	}
}), K = class extends Error {
	status;
	code;
	fields;
	constructor(e, t, n = "", r = {}) {
		super(e), this.status = t, this.code = n, this.fields = r, this.name = "ConfigApiError";
	}
}, yr = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {}, br = (e) => JSON.parse(JSON.stringify(e));
function xr(e) {
	if (!Array.isArray(e)) throw new K("配置字段响应格式无效", 0, "config_schema_invalid");
	let t = /* @__PURE__ */ new Set();
	return e.map((e) => {
		let n = yr(e);
		if (typeof n.key != "string" || !n.key || typeof n.type != "string" || t.has(n.key)) throw new K("配置字段响应格式无效", 0, "config_schema_invalid");
		t.add(n.key);
		let r = br({
			...n,
			group: String(n.group || "其他"),
			label: String(n.label || n.key)
		});
		return r.secret && (r.value = "", "configured_value" in r && (r.configured_value = ""), "published_effective_value" in r && (r.published_effective_value = ""), delete r.default), r;
	});
}
function Sr(e = fetch) {
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
		let a = yr(i);
		if (!r.ok || a.ok === !1) {
			let e = yr(a.error), t = {};
			for (let [n, r] of Object.entries(yr(a.fields || e.fields))) typeof r == "string" && (t[n] = r);
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
			if (r?.generation === t) return br(await r.promise);
			if (!e.force && n && Date.now() - n.at < 3e4) return br(n.fields);
			let a = t, o = i("/api/config", { signal: e.signal }).then((e) => {
				let r = xr(e);
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
				return br(await o);
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
			if (!t || typeof t != "object" || Array.isArray(t) || !Array.isArray(yr(t).updated) || !yr(t).updated.every((e) => typeof e == "string")) throw new K("配置保存响应格式无效", 0, "config_save_response_invalid");
			return a(), t;
		},
		invalidate: a
	};
}
// src/features/config/configState.ts
function Cr(e, t) {
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
function wr(e, t) {
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
var q = (e) => e === void 0 ? e : JSON.parse(JSON.stringify(e)), Tr = (e, t) => JSON.stringify(e) === JSON.stringify(t);
function Er(t) {
	let n = C(xr(t.initialFields || [])), r = u({}), i = u({}), a = h(!1), o = h(!1), s = h(""), c = h(""), l = h(null), d = h(null), f = /* @__PURE__ */ new Map(), p = /* @__PURE__ */ new Set(), m = /* @__PURE__ */ new Set(), g = !1, _ = 0, v = 0, y = null, b = /* @__PURE__ */ new Set(), S = x(() => new Map(n.value.map((e) => [e.key, e]))), w = x(() => Object.keys(r)), T = x(() => w.value.length), E = (e) => S.value.get(e), D = (e) => {
		let t = (f.get(e) || 0) + 1;
		return f.set(e, t), t;
	};
	function O(e, t = "effective") {
		return q(t === "effective" && r[e] ? r[e].value : E(e)?.value);
	}
	function k(e) {
		let t = E(e);
		if (!t) throw Error(`未知配置字段：${e}`);
		return t;
	}
	function ee(e) {
		return q(r[e]?.secret || { mode: "retain" });
	}
	function A(e, t) {
		if (g) return;
		let n = k(e);
		if (!n.secret) throw Error(`字段不是密钥：${e}`);
		let a = D(e);
		if (n.group !== "并发控制" && Object.keys(i).forEach((e) => delete i[e]), delete i[e], t.mode === "retain") {
			delete r[e];
			return;
		}
		let o = t.mode === "clear" ? n.type === "list_str_multiline" ? [] : "" : q(t.value);
		r[e] = {
			value: o,
			generation: a,
			secret: q(t)
		};
	}
	function j(e, t, n = {}) {
		if (g) return;
		let a = k(e);
		if (a.group !== "并发控制" && Object.keys(i).forEach((e) => delete i[e]), a.secret) {
			A(e, t === null || typeof t == "string" && t.trim() === "" || Array.isArray(t) && !t.length ? { mode: "retain" } : {
				mode: "set",
				value: q(t)
			});
			return;
		}
		let o = D(e);
		delete i[e];
		let s = !!n.force || !!r[e]?.forced;
		!s && !b.has(e) && Tr(t, a.value) ? delete r[e] : r[e] = {
			value: q(t),
			generation: o,
			forced: s
		};
	}
	function M(e, t) {
		if (g) return;
		k(e);
		let n;
		n = e === "PROXY_POOL_WAIT_TIMEOUT" ? t.mode === "timed" ? t.raw.trim() === "" ? null : Number(t.raw) : 0 : e === "SMS_MAX_PRICE" ? t.mode === "limited" ? t.raw : "" : t.raw;
		let a = D(e);
		k(e).group !== "并发控制" && Object.keys(i).forEach((e) => delete i[e]), delete i[e], r[e] = {
			value: n,
			generation: a,
			composite: q(t)
		};
	}
	function N(e = w.value) {
		for (let t of e) D(t), delete r[t], delete i[t];
		s.value = "";
	}
	function P(e) {
		d.value = {
			key: e,
			generation: ++v
		}, t.onNavigateField?.(e);
	}
	async function F(e = {}) {
		if (g) return;
		let r = ++_, i = new AbortController();
		m.add(i), a.value = !0;
		try {
			let a = await t.api.getSchema({
				...e,
				signal: i.signal
			});
			if (g || r !== _ || i.signal.aborted) return;
			n.value = xr(a), c.value = "";
		} catch (e) {
			if (!g && r === _ && !i.signal.aborted) throw c.value = "配置读取失败，当前草稿已保留", e;
		} finally {
			m.delete(i), r === _ && (a.value = !1);
		}
	}
	async function I() {
		if (!(g || n.value.length)) return y ||= F().finally(() => {
			y = null;
		}), y;
	}
	function L(e) {
		let i = {
			...wr(e, n.value),
			...t.validate?.(e, n.value)
		};
		for (let t of Object.keys(e)) {
			let e = r[t]?.composite;
			e && (t === "PROXY_POOL_WAIT_TIMEOUT" && e.mode === "timed" && (!e.raw.trim() || !Number.isFinite(Number(e.raw)) || Number(e.raw) <= 0) && (i[t] = "请填写限时等待秒数，或切换为持续等待"), t === "SMS_MAX_PRICE" && e.mode === "limited" && (!e.raw.trim() || !Number.isFinite(Number(e.raw)) || Number(e.raw) < 0) && (i[t] = "请填写短信价格上限，或切换为不设上限"));
		}
		return i;
	}
	function R(e) {
		Object.assign(i, e);
		let t = Object.keys(e)[0];
		t && P(t);
	}
	async function z(e) {
		if (g) return { status: "disposed" };
		if (o.value) return { status: "busy" };
		let a = /* @__PURE__ */ new Map(), c = {};
		for (let t of e) r[t] && (a.set(t, q(r[t])), c[t] = q(r[t].value));
		if (!a.size) return { status: "noop" };
		let u = L(c);
		if (Object.keys(u).length) return R(u), {
			status: "validation-error",
			fields: u
		};
		o.value = !0, s.value = "", b = new Set(a.keys());
		try {
			let e = await t.api.save(c);
			if (g) return { status: "disposed" };
			_++;
			let o = Cr(e, [...a.keys()]), s = new Set(o.savedKeys);
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
					value: q(t.value),
					configured_value: q(t.value)
				};
			});
			for (let [e, t] of a) s.has(e) && f.get(e) === t.generation && (delete r[e], delete i[e]);
			t.api.invalidate(), l.value = o;
			try {
				await F({ force: !0 });
			} catch {
				o.refreshFailed = !0, l.value = { ...o };
			}
			if (!g) {
				let e = {
					keys: o.savedKeys,
					receipt: q(o),
					fields: q(n.value)
				};
				for (let t of p) try {
					t(e);
				} catch {}
			}
			return {
				status: "saved",
				receipt: q(o)
			};
		} catch (e) {
			if (g) return { status: "disposed" };
			let t = e instanceof K ? e.fields : {};
			if (Object.keys(t).length) {
				let e = Object.fromEntries(Object.entries(t).filter(([e]) => {
					let t = a.get(e);
					return !t || f.get(e) === t.generation;
				}));
				return R(e), {
					status: "validation-error",
					fields: q(e)
				};
			}
			return s.value = e instanceof K ? e.message : "配置保存失败，草稿已保留", { status: "error" };
		} finally {
			o.value = !1, b = /* @__PURE__ */ new Set();
		}
	}
	async function te(e) {
		if (g) return { status: "disposed" };
		if (o.value) return { status: "busy" };
		if (Array.isArray(e)) return z(e);
		for (let [t, n] of Object.entries(e)) j(t, n, { force: !0 });
		return z(Object.keys(e));
	}
	function B() {
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
		secretDraft: ee,
		readComposite: (e) => q(r[e]?.composite),
		setField: j,
		setSecret: A,
		clearSecret: (e) => A(e, { mode: "clear" }),
		setComposite: M,
		reset: N,
		initialize: I,
		refresh: F,
		saveAll: () => z(w.value),
		saveSubset: te,
		navigateField: P,
		subscribeSaved(e) {
			return p.add(e), () => p.delete(e);
		},
		dispose: B
	};
}
// src/features/config/configActions.ts
var Dr = [
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
	"c2a",
	"concurrency",
	"concurrencyPreview",
	"sub2apiGroups"
], Or = /* @__PURE__ */ new Set([
	"sentinel",
	"sub2api",
	"c2a",
	"proxy"
]), kr = {
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
function J(e) {
	return e && typeof e == "object" && !Array.isArray(e) ? e : {};
}
function Y(e, t = "") {
	return typeof e == "string" || typeof e == "number" ? String(e).slice(0, 1e3) : t;
}
function Ar(e) {
	return typeof e == "string" ? e.trim() : "";
}
function X(e) {
	return Array.isArray(e) ? e : [];
}
function jr(e) {
	return typeof e == "number" && Number.isFinite(e) && e >= 0;
}
function Z(e) {
	return Number.isSafeInteger(e) && Number(e) >= 0;
}
function Q() {
	throw { code: "invalid_response" };
}
function $(e) {
	return {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(e)
	};
}
function Mr(e, t = !1, n = "CDK") {
	let r = Y(J(e).code || J(e).error_code).toLowerCase();
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
function Nr(e, t = {}) {
	let n = t.request || ((e, t) => A(e, t, N)), r = u(Object.fromEntries(Dr.map((e) => [e, {
		loading: !1,
		posting: !1,
		text: "",
		error: "",
		snapshot: null,
		receipt: null
	}]))), i = Object.fromEntries(Dr.map((e) => [e, 0])), o = /* @__PURE__ */ new Map(), s = /* @__PURE__ */ new Map(), c = {
		sentinel: !1,
		concurrency: !1
	}, l = /* @__PURE__ */ new Map(), d = !0, f = !0, p = !1, m = [], h = (t, n = "") => e.readField(t) ?? n;
	function g(t) {
		let n = e.secretDraft(t);
		return n.mode === "set" ? Ar(n.value) : n.mode === "clear" ? "" : Ar(h(t));
	}
	function _(t) {
		let n = e.secretDraft(t);
		return n.mode === "clear" ? { api_key: "" } : n.mode === "set" ? { api_key: Ar(n.value) } : e.isDirty(t) ? { api_key: Ar(h(t)) } : {};
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
	for (let [t, n] of Object.entries(kr)) m.push(a(() => n.map((t) => [
		e.readField(t),
		e.isDirty(t),
		e.secretDraft(t)
	]), () => y(t), {
		deep: !0,
		flush: "sync"
	}));
	m.push(e.subscribeSaved((t) => {
		for (let [e, n] of Object.entries(kr)) n.some((e) => t.keys.includes(e)) && y(e);
		t.keys.some((e) => [
			"SUB2API_API_BASE",
			"SUB2API_API_KEY",
			"SUB2API_API_TIMEOUT"
		].includes(e)) && y("sub2apiGroups"), t.keys.some((e) => e.startsWith("C2A_API_") || e.startsWith("C2A_MONITOR_")) && y("c2a"), t.keys.some((t) => e.field(t)?.group === "并发控制") && y("concurrencyPreview");
	}));
	function b(e) {
		if (e.accepted !== !0) return null;
		let t = {
			accepted: !0,
			task_id: j(e.task_id)
		};
		return e.run_id != null && (t.run_id = M(e.run_id)), t;
	}
	function S(e) {
		v(e), !p && d && f && c[e] && !r[e].loading && !r[e].posting && (e !== "sentinel" || r.sentinel.snapshot?.running && !r.sentinel.error) && l.set(e, setTimeout(() => {
			l.delete(e), e === "sentinel" ? L() : H();
		}, e === "sentinel" ? 1500 : 3e3));
	}
	function C(e, t, a, c) {
		if (p) return Promise.resolve();
		let l = c.posting && Or.has(e), u = l ? s.get(e) : void 0;
		if (u) return u;
		let d = o.get(e);
		if (d?.generation === i[e] || d?.posting && l) return d.promise;
		let f = ++i[e], m = c.posting ? void 0 : new AbortController();
		r[e].loading = !c.posting, r[e].posting = !!c.posting, r[e].error = "", (e === "sentinel" || e === "concurrency") && v(e);
		let h = () => !p && i[e] === f, g = (async () => {
			try {
				if (d && await d.promise, !h()) return;
				let i = J(await Promise.resolve().then(() => n(t, {
					...a,
					...m ? { signal: m.signal } : {}
				})));
				if (i.ok === !1) throw i;
				let o = c.label ? b(i) : null;
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
				for (let r of X(e.items)) {
					let e = J(r), i = Y(e.type).trim().toLowerCase();
					i && !t.has(i) && e.visible !== !1 && e.enabled !== !1 && (t.add(i), n.push({
						value: i,
						label: Y(e.label, i) || i
					}));
				}
				n.length || Q(), r.extractTypes.snapshot = { options: n };
			},
			error: () => "提链类型读取失败，保留当前选择。"
		});
	}
	function E() {
		return C("roxy", "/api/roxy/workspaces", { method: "GET" }, {
			apply: (e) => {
				let t = X(e.items).map((e) => {
					let t = J(e);
					return {
						id: Y(t.id),
						projectId: Y(t.projectId),
						label: Y(t.label) || `${Y(t.name)} (${Y(t.id)})`
					};
				}).filter((e) => e.id);
				t.length || Q(), r.roxy.snapshot = { items: t }, r.roxy.text = `已获取 ${t.length} 个团队/项目`;
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
		let e = Y(h("PROXY_POOL_SOURCE")), t = e === "1024proxy" ? "PROXY_1024_" : e === "711proxy" ? "PROXY_711_" : "";
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
				let i = J(t.lease), a = Y(i.endpoint, "—").replace(/\/\/[^/]*@/, "//").replace(/^[^/]*@/, "");
				r.proxy.snapshot = {
					provider: Y(i.provider, e),
					endpoint: a,
					exit_ip: Y(i.exit_ip, "—"),
					region: Y(i.region, "—"),
					expires_at: Y(i.expires_at, "—")
				}, r.proxy.text = `测试成功 · ${Y(i.provider, e)} · ${a} · 出口 ${Y(i.exit_ip, "—")} · ${Y(i.region, "—")} · 有效至 ${Y(i.expires_at, "—")}`;
			},
			error: () => "代理提取测试失败，请检查供应商配置后重试。"
		}) : w("proxy", "请选择支持提取测试的代理供应商。");
	}
	function k() {
		return C("butler", "/api/email-butler/test-connection", $({
			api_base: Ar(h("EMAIL_BUTLER_API_BASE")),
			api_key: g("EMAIL_BUTLER_API_KEY")
		}), {
			posting: !0,
			apply: (e) => {
				let t = X(e.missing_permissions).map((e) => Y(e)).filter(Boolean);
				r.butler.snapshot = {
					name: Y(e.name, "Email Butler"),
					consumer: Y(e.consumer),
					service: Y(e.service),
					missing_permissions: t
				};
				let n = [Y(e.consumer), Y(e.service)].filter(Boolean).join(" / ") || "未绑定策略";
				r.butler.text = t.length ? `连接成功，权限尚未齐全：${t.join("、")}。请在 Butler 为原客户端补充权限。` : `连接成功：${Y(e.name, "Email Butler")} · ${n}`;
			},
			error: () => "Email Butler 连接失败，请检查地址和客户端权限后重试。"
		});
	}
	function ee(t) {
		let n = t === "extraction" ? "huanguangExtraction" : "huanguangPayment", i = t === "extraction" ? "EXTRACT_LINK_HUANGUANG_CDK" : "EXTRACT_LINK_HUANGUANG_PAYMENT_CDK";
		return e.isDirty(i) || e.isDirty("EXTRACT_LINK_HUANGUANG_API_BASE") ? w(n, "请先保存此 CDK 或服务地址的更改，再查询剩余次数") : C(n, `/api/extract-link/huanguang/cdk-quota/${t}`, { method: "GET" }, {
			apply: (e) => {
				let t = J(e.quota);
				(typeof t.required != "boolean" || !(t.remaining === null || Z(t.remaining)) || !(t.reserved === null || Z(t.reserved)) || t.active !== null && typeof t.active != "boolean") && Q(), r[n].snapshot = {
					required: t.required,
					remaining: t.remaining,
					reserved: t.reserved,
					active: t.active
				}, r[n].text = t.required ? `剩余 ${t.remaining ?? "未知"} 次 · 占用 ${t.reserved ?? "未知"} · ${t.active === !1 ? "已停用" : t.active === !0 ? "已启用" : "可用状态未知"}` : "平台免计次";
			},
			error: (e) => Mr(e, !1, t === "extraction" ? "幻光提链 CDK" : "幻光支付扫码 CDK")
		});
	}
	function P() {
		return e.isDirty("EXTRACT_LINK_HUANGUANG_API_BASE") ? w("huanguangXxsyun", "请先保存服务地址的更改，再查询剩余次数") : C("huanguangXxsyun", "/api/extract-link/huanguang/xxsyun-quota", $(_("EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY")), {
			posting: !0,
			apply: (e) => {
				Z(e.remainingUses) && (e.totalUses == null || Z(e.totalUses)) && (e.reservedUses == null || Z(e.reservedUses)) || Q(), r.huanguangXxsyun.snapshot = {
					remainingUses: e.remainingUses,
					totalUses: e.totalUses ?? null,
					reservedUses: e.reservedUses ?? null
				}, r.huanguangXxsyun.text = `剩余 ${e.remainingUses} 次 · 总次数 ${e.totalUses ?? "未知"} · 占用 ${e.reservedUses ?? "未知"}`;
			},
			error: (e) => Mr(e)
		});
	}
	function F() {
		return e.isDirty("EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE") ? w("xxsyunBalance", "请先保存服务地址的更改，再查询积分") : C("xxsyunBalance", "/api/extract-link/payments/xxsyun/balance", $(_("EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY")), {
			posting: !0,
			apply: (e) => {
				let t = J(e.balance), n = [
					"available_points",
					"pending_points",
					"used_points",
					"cost_points"
				];
				e.balance && !Array.isArray(e.balance) && n.every((e) => t[e] == null || jr(t[e])) || Q(), r.xxsyunBalance.snapshot = Object.fromEntries(n.map((e) => [e, t[e] ?? null]));
				let i = (e) => e == null ? "未知" : `${e} 积分`;
				r.xxsyunBalance.text = `可用 ${i(t.available_points)} · 预占 ${i(t.pending_points)} · 已用 ${i(t.used_points)} · 每单 ${i(t.cost_points)}`;
			},
			error: (e) => Mr(e, !0)
		});
	}
	function I(e) {
		return e && r.sentinel.snapshot?.running ? Promise.resolve() : C("sentinel", e ? "/api/maintenance/sentinel/check" : "/api/maintenance/sentinel", e ? $({}) : { method: "GET" }, {
			posting: e,
			label: e ? "Sentinel 检查" : void 0,
			apply: (e, t) => {
				let n = r.sentinel.snapshot;
				r.sentinel.snapshot = {
					...e,
					candidate: e.candidate || n?.candidate || null,
					comparison: !e.candidate && n?.candidate ? n.comparison : e.comparison
				}, r.sentinel.text = t ? `检查已入队 · 任务 #${t.task_id}` : e.running ? "正在检查 Sentinel 更新…" : "已读取 Sentinel 检查状态。", !e.running && (["failed", "corrupt"].includes(Y(e.last_status)) || e.error_code) && (r.sentinel.error = e.last_status === "corrupt" ? "候选资源不可用，请重试。" : "检查失败，请重试。");
			},
			error: () => e ? "检查请求未完成，请重试。" : "状态读取失败，请重试。"
		});
	}
	function L() {
		return I(!1);
	}
	function R() {
		return I(!0);
	}
	function z(e) {
		return C("sub2api", e ? "/api/sub2api/automation/check" : "/api/sub2api/automation", e ? $({}) : { method: "GET" }, {
			posting: e,
			label: e ? "Sub2API 异常扫描" : void 0,
			apply: (t, n) => {
				if (r.sub2api.snapshot = t, n) r.sub2api.text = `异常扫描已入队 · 任务 #${n.task_id}，最终结果在任务回执中更新。`;
				else if (e) {
					let e = J(t.result), n = {
						account_busy: "账号忙碌",
						cooldown: "冷却中",
						account_archived: "账号已归档",
						account_deactivated: "账号已停用",
						automatic_login_material_missing: "自动登录资料不足",
						unrecognized_remote_error: "远端错误原因未识别",
						remote_transient_error: "远端网络或限流错误",
						needs_reconciliation: "上次请求结果待核实",
						repair_in_progress: "修复进行中"
					}, i = Object.entries(J(e.reasons)).filter(([, e]) => Z(e)).map(([e, t]) => `${n[e] || "其他原因"} ${t}`).join("，");
					r.sub2api.text = `本轮检查 ${e.remote_errors ?? 0} 条异常记录，已调度同步 ${e.sync_queued ?? 0}、刷新 ${e.refresh_queued ?? 0}、重授权 ${e.reauth_queued ?? 0}。${i ? `处理说明：${i}。` : ""}`;
				} else {
					let e = J(t.sync), n = J(t.monitor), i = J(e.counts), a = X(n.group_ids).map((e) => Y(e)).filter(Boolean), o = a.length ? `分组 ID ${a.join("、")}` : "全部分组";
					r.sub2api.text = `自动补传${e.enabled ? "已开启" : "已关闭"}；异常巡检${n.enabled ? "已开启" : "已关闭"}；巡检范围：${o}。待同步 ${i.pending ?? 0}，排队 ${i.queued ?? 0}，执行 ${i.running ?? 0}。`;
				}
			},
			error: () => "Sub2API 状态或巡检请求未完成，请稍后重试。"
		});
	}
	function te() {
		return C("sub2apiGroups", "/api/sub2api/groups", { method: "GET" }, {
			apply: (e) => {
				if (e.ok !== !0 || !Array.isArray(e.groups) || e.groups.some((e) => {
					let t = J(e);
					return !Number.isSafeInteger(t.id) || Number(t.id) <= 0 || typeof t.name != "string";
				})) throw Error("分组响应格式无效，请重试");
				let t = [...new Map(e.groups.map((e) => {
					let t = J(e);
					return [t.id, t];
				})).values()];
				r.sub2apiGroups.snapshot = { options: t.map((e) => ({
					value: String(e.id),
					label: `${e.name}（ID ${e.id}）`
				})) }, r.sub2apiGroups.text = `已查询 ${t.length} 个分组`;
			},
			error: (e) => {
				let t = e instanceof Error ? e.message : Y(J(e).error);
				return t === "分组响应格式无效，请重试" ? t : `查询分组失败：${t || "请检查已保存的连接配置后重试"}`;
			}
		});
	}
	function B() {
		return z(!1);
	}
	function ne() {
		return z(!0);
	}
	function re() {
		return C("c2a", "/api/c2a/automation", { method: "GET" }, {
			apply: (e) => {
				let t = J(e.monitor);
				typeof t.enabled != "boolean" && Q(), r.c2a.snapshot = t;
				let n = `自动巡检${t.enabled ? "已开启" : "已关闭"}`;
				if (t.error_code === "c2a_config_invalid") {
					r.c2a.text = `${n}。请检查并保存 C2A 连接配置。`;
					return;
				}
				if (!t.state_available) {
					r.c2a.text = `${n}。修复状态暂不可用，请稍后重试。`;
					return;
				}
				let i = J(t.repair_stages), a = (e) => Z(i[e]) ? i[e] : 0;
				r.c2a.text = `${n}。待提交刷新 ${a("refresh_pending")}，等待刷新 ${a("refresh_wait")}，刷新冷却 ${a("refresh_retry")}，刷新失败已跳过 ${a("refresh_exhausted")}，同步待完成 ${a("sync_wait")}，已结束 ${a("done")}，已取消 ${a("cancelled")}。`;
			},
			error: () => "暂时无法读取 C2A 巡检状态，请稍后重试。"
		});
	}
	function V() {
		return C("c2a", "/api/c2a/automation/check", $({}), {
			posting: !0,
			label: "C2A 异常巡检",
			apply: (e, t) => {
				t || Q(), r.c2a.text = `C2A 异常巡检已入队 · 任务 #${t.task_id}。扫描结果在任务回执中更新。`;
			},
			error: (e) => J(e).code === "c2a_config_invalid" || J(e).error_code === "c2a_config_invalid" ? "C2A 连接配置无效，请检查并保存 API 基址和管理员 Key。" : "C2A 巡检暂时无法入队，请稍后重试。"
		});
	}
	function ie() {
		return C("concurrencyPreview", "/api/config/concurrency-preview", { method: "GET" }, {
			apply: (e) => {
				r.concurrencyPreview.snapshot = e;
			},
			error: () => "迁移预览暂不可用，请刷新重试。"
		});
	}
	async function H(e = {}) {
		let t = r.concurrencyPreview.snapshot ? Promise.resolve() : ie();
		await Promise.all([t, C("concurrency", `/api/operations/concurrency${e.details ? "?details=1" : ""}`, { method: "GET" }, {
			apply: (e) => {
				r.concurrency.snapshot = e;
				let t = J(e.global);
				r.concurrency.text = `当前占用 ${t.occupied ?? 0} / ${t.limit ?? "—"}${t.draining ? "，等待现有任务结束" : ""}；预约 ${t.reserved ?? 0} · 执行 ${t.executing ?? 0} · 清理 ${t.cleaning ?? 0} · 调试保留 ${t.debug_hold ?? 0}；排队 ${e.queued ?? 0} · 远端等待 ${e.remote_waiting ?? "—"}`;
			},
			error: () => "状态读取失败，请重试；显示的数据为上次观察结果。"
		})]);
	}
	function ae() {
		if (p) return [];
		let t = [];
		for (let [n, i] of Object.entries(J(r.concurrencyPreview.snapshot?.proposed_values))) {
			let r = e.field(n);
			!r || r.group !== "并发控制" || r.type !== "int" || e.isDirty(n) || !Z(i) || Number(i) <= 0 || (e.setField(n, Number(i), { force: !0 }), t.push(n));
		}
		return r.concurrencyPreview.text = "迁移建议已填入草稿；核对全局和各类型上限后点击保存。", t;
	}
	function oe(e) {
		if (p) return;
		if (e.startsWith("REGISTRATION_")) {
			t.onNavigateTasks?.({ registration: !0 });
			return;
		}
		let n = X(r.concurrency.snapshot?.types).map(J).find((t) => t.config_key === e || t.key === e), i = n ? X(n.task_types).length ? X(n.task_types).map((e) => Y(e)) : [Y(n.key)] : [];
		t.onNavigateTasks?.({ types: [...new Set(i.filter(Boolean))] });
	}
	function se(e, t) {
		p || c[e] === t || (c[e] = t, t ? d && f && (e === "sentinel" ? L() : H()) : (v(e), y(e, !0), e === "concurrency" && y("concurrencyPreview", !0)));
	}
	function ce(e) {
		if (!(p || d === e)) {
			d = e;
			for (let t of ["sentinel", "concurrency"]) v(t), e ? f && c[t] && (t === "sentinel" ? L() : H()) : (y(t, !0), t === "concurrency" && y("concurrencyPreview", !0));
		}
	}
	function le(e) {
		if (!(p || f === e)) {
			if (f = e, v("sentinel"), v("concurrency"), e) d && (c.sentinel && L(), c.concurrency && H());
			else for (let e of Dr) y(e, !0);
		}
	}
	function ue() {
		if (!p) {
			p = !0, m.forEach((e) => e()), v("sentinel"), v("concurrency");
			for (let e of Dr) y(e, !0);
		}
	}
	return {
		states: r,
		sub2apiGroups: x(() => r.sub2apiGroups.snapshot?.options || []),
		querySub2ApiGroups: te,
		extractTypeOptions: x(() => r.extractTypes.snapshot?.options || []),
		roxyWorkspaces: x(() => r.roxy.snapshot?.items || []),
		loadExtractTypes: T,
		loadRoxyWorkspaces: E,
		saveRoxySelection: D,
		testProxy: O,
		testButler: k,
		queryHuanguangQuota: ee,
		queryHuanguangXxsyun: P,
		queryXxsyunBalance: F,
		refreshSentinel: L,
		checkSentinel: R,
		refreshSub2Api: B,
		checkSub2Api: ne,
		refreshC2a: re,
		checkC2a: V,
		refreshConcurrency: H,
		loadConcurrencyPreview: ie,
		applyConcurrencyPreview: ae,
		locateConcurrencyTasks: oe,
		setVisible: se,
		setForeground: ce,
		setPageActive: le,
		dispose: ue
	};
}
// src/features/config/useConfigActions.ts
function Pr(e, t = {}) {
	let n = Nr(e, t), r = () => n.setForeground(!document.hidden);
	return typeof document < "u" && (r(), document.addEventListener("visibilitychange", r)), f(() => {
		typeof document < "u" && document.removeEventListener("visibilitychange", r), n.dispose();
	}), n;
}
// src/config.ts
function Fr(e, t) {
	let n = Er({ api: Sr() }), i = o(), s = i.run(() => Pr(n, { onNavigateTasks: t.onNavigateTasks })), c = h(t.visible !== !1), l = null, u = a(n.fields, (e) => t.onSavedFields(e), { immediate: !0 }), d = n.subscribeSaved(() => t.onSaved?.()), f = S({ render: () => r(vr, {
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
export { Fr as mountConfig };
