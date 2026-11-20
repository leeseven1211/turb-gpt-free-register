import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, Q as s, S as c, Z as l, _ as u, a as d, c as f, d as p, dt as m, et as h, ft as g, g as _, h as v, j as y, k as b, l as x, lt as S, m as C, n as w, nt as T, s as E, st as D, v as O, x as k, y as A } from "./_plugin-vue_export-helper-CtnyMOwL.js";
import { n as j, r as M, t as ee } from "./ListFilterSummary-wgXrzXbr.js";
import { t as N } from "./ListPagination-CrkNIuCM.js";
import { t as P } from "./ListResult-DTuWvy8M.js";
import { n as F, t as I } from "./time-DOD6oyhP.js";
import { t as L } from "./useColumnWidths-DZSfaGuI.js";
import { n as R, r as z } from "./client-BBEPwkQG.js";
import { r as te } from "./taskIds-BlchWwUp.js";
// src/features/proxy/presentation.ts
function B(e, t = "—") {
	return e == null || e === "" ? t : typeof e == "string" || typeof e == "number" ? String(e) : t;
}
function V(e) {
	return e && typeof e == "object" && !Array.isArray(e) ? e : {};
}
function H(e) {
	return Array.isArray(e) ? e.filter((e) => e && typeof e == "object" && !Array.isArray(e)) : [];
}
function U(e) {
	if (e == null || e === "") return null;
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? t : null;
}
function W(e) {
	let t = U(e);
	if (t == null) return "—";
	if (t < 1024) return `${t} B`;
	let n = [
		"KB",
		"MB",
		"GB",
		"TB"
	], r = t, i = -1;
	for (; r >= 1024 && i < n.length - 1;) r /= 1024, i++;
	return `${r >= 100 ? r.toFixed(0) : r >= 10 ? r.toFixed(1) : r.toFixed(2)} ${n[i]}`;
}
var G = {
	pending: "待验证",
	fetching: "提取中",
	checking: "复检中",
	ready: "可领取",
	shared: "共享库存",
	shared_pending: "共享线路检测中",
	shared_leased: "共享查询中",
	pool_leased: "任务独占中",
	cooldown: "冷却中",
	quarantine: "故障隔离",
	rotation_wait: "等待轮换",
	retired: "已退役",
	leased: "租约中",
	recent: "最近释放",
	released: "已释放",
	expired: "已过期",
	failed: "失败",
	unavailable: "未采集",
	observed: "可观测",
	complete: "已完成",
	running: "运行中",
	available: "可观测"
};
function K(e) {
	let t = B(e, "");
	return {
		label: G[t] || "未知状态",
		title: t || "未提供状态",
		tone: ["failed", "quarantine"].includes(t) ? "danger" : [
			"leased",
			"shared_leased",
			"pool_leased",
			"running"
		].includes(t) ? "active" : [
			"ready",
			"available",
			"observed",
			"released"
		].includes(t) ? "success" : "neutral"
	};
}
var ne = {
	supply_unavailable: {
		label: "补货暂不可用",
		evidence: "补货暂不可用"
	},
	supply_candidates_duplicate: {
		label: "候选已占用",
		evidence: "供应商返回的候选均已占用或处于冷却期"
	},
	transport_failure: {
		label: "线路连接失败",
		evidence: "线路连接失败"
	},
	check_interrupted: {
		label: "复检中断",
		evidence: "复检中断"
	},
	health_check_failed: {
		label: "健康检查失败",
		evidence: "健康检查失败"
	}
};
function q(e) {
	let t = B(e, ""), n = ne[t];
	return n ? {
		...n,
		evidence: `${n.evidence}（${t}）`
	} : {
		label: t ? "库存异常" : "—",
		evidence: t
	};
}
function J(e, t) {
	let n = e.registration_job_id != null && e.registration_job_id !== "";
	if ((e.operation_task_id == null || e.operation_task_id === "") && !n) return "未关联任务";
	let r = B(e.operation_task_type, n ? "registration" : "");
	return r ? t?.("task_type", r) || {
		registration: "注册",
		plan_check: "查套餐",
		token_refresh: "刷新 Token",
		live_check: "查活"
	}[r] || r : "未关联任务";
}
function Y(e, t = !1) {
	return [
		["任务", e.operation_task_id],
		["运行", e.operation_run_id],
		...t ? [["注册 job", e.registration_job_id]] : []
	].filter(([, e]) => e != null && e !== "").map(([e, t]) => `${e} #${B(t)}`).join(" · ") || "—";
}
function re(e, t) {
	return {
		text: J(e, t),
		secondary: Y(e, e.operation_task_id == null || e.operation_task_id === ""),
		title: [J(e, t), Y(e, !0)].join(" · ")
	};
}
function X(e) {
	if (e.availability !== "available" || U(e.total_bytes) == null) return {
		text: "未采集",
		title: "未采集"
	};
	let t = `${W(e.upload_bytes)} / ${W(e.download_bytes)} / ${W(e.total_bytes)}`, n = e.source === "protocol_http" && (U(e.byte_unknown_count) || 0) > 0;
	return {
		text: t,
		secondary: n ? "部分字节未知" : void 0,
		title: t + (n ? "（部分字节未知）" : "")
	};
}
function ie(e) {
	let t = V(e);
	return [
		"1xx",
		"2xx",
		"3xx",
		"4xx",
		"5xx",
		"unknown"
	].flatMap((e) => {
		let n = t[e];
		return typeof n == "number" && Number.isSafeInteger(n) && n >= 0 ? [`${e}: ${n}`] : [];
	}).join(" / ");
}
function ae(e, t, n) {
	let r = [], i = (e, t) => {
		t != null && t !== "" && r.push({
			label: e,
			value: B(t)
		});
	}, a = (e) => e ? F(e) : null;
	if (e === "history") return [
		["租约 ID", t.lease_id],
		["线路来源", t.provider],
		["出口 IP", t.exit_ip],
		["状态", G[B(t.state)] || t.state],
		["账号", t.account_id],
		["用途", t.purpose],
		["任务", t.operation_task_id],
		["运行", t.operation_run_id],
		["注册 job", t.registration_job_id],
		["重试序号", t.route_attempt_no],
		["获取时间", a(t.acquired_at)],
		["到期时间", a(t.expires_at)],
		["释放时间", a(t.released_at)]
	].forEach(([e, t]) => i(String(e), t)), r;
	[
		["来源", t.source],
		["字节口径", t.source === "protocol_http" ? "HTTP 传输正文；不含请求/响应头、TLS、隧道或代理商账单" : "浏览器可观测字节；不等同代理商账单"],
		["总请求耗时", t.duration_ms == null ? null : `${B(t.duration_ms)} 毫秒`],
		["状态族", ie(t.status_families)],
		["重定向次数", t.redirect_count],
		["解压后响应正文", t.decoded_response_bytes == null ? null : W(t.decoded_response_bytes)],
		["字节未知请求数", t.byte_unknown_count],
		["注册 Attempt", t.registration_attempt_id],
		["注册 Run", t.registration_run_id],
		["方法", t.method],
		["上传流量", W(t.upload_bytes)],
		["下载流量", W(t.download_bytes)],
		["总流量", W(t.total_bytes)],
		["请求数", t.request_count],
		["失败数", t.failed_count],
		["未完成数", t.unfinished_count],
		["未知数", t.unknown_count],
		["线路租约", t.proxy_lease_id],
		["账号", t.account_id],
		["任务类型", J(t, n)],
		["注册 job", t.registration_job_id],
		["任务", t.operation_task_id],
		["运行", t.operation_run_id],
		["开始时间", a(t.started_at)],
		["完成时间", a(t.ended_at)]
	].forEach(([e, t]) => i(String(e), t));
	let o = V(t.proxy_transport);
	if (o.available) {
		i("代理隧道传输", W(o.total_bytes)), i("隧道口径", "含 TLS、启动和后台请求；与页面字节重叠，不相加；不含 TCP/IP 开销、缓存匿名填充和代理商账单"), i("连接前已拦截", `${U(o.blocked_connection_count) ?? 0} 次；没有估算节省字节`);
		for (let e of H(o.destinations).slice(0, 50)) i(`目标 ${B(e.host)}:${B(e.port)}`, `${W(e.total_bytes)} · 连接 ${B(e.connection_count)} · 失败 ${B(e.failed_connection_count)} · 拦截 ${B(e.blocked_connection_count)} · 重试 ${B(e.connect_retry_count)} · 恢复 ${B(e.recovered_connection_count)}`);
	}
	let s = H(t.resource_details);
	if (s.length) {
		i("资源明细", `页面可观测口径；以下显示前 ${Math.min(50, s.length)} 项，完整有界明细见任务日志`);
		for (let e of s.slice(0, 50)) i(B(e.url), `${B(e.resource_type)} · ${W(e.total_bytes)}`);
	}
	let c = V(t.js_coverage);
	if (c.enabled) {
		i("JS 覆盖率", `target ${B(c.target_count)} · 已采集 ${B(c.collected_target_count)} · 不支持/失败 ${B(c.unsupported_target_count)}；未观察到执行不能证明资源可安全拦截`);
		for (let e of H(c.scripts).slice(0, 50)) i(B(e.url), `函数 ${B(e.function_count)} · 观察到执行 ${B(e.executed_function_count)}`);
	}
	return r;
}
// src/features/proxy/ProxyPool.vue?vue&type=script&setup=true&lang.ts
var oe = {
	class: "pt-workspace",
	"data-proxy-module-panel": "pool"
}, se = {
	class: "pt-summary",
	"aria-label": "代理池库存摘要"
}, ce = { "data-proxy-summary": "poolCapacity" }, le = ["data-proxy-summary"], ue = {
	class: "pt-panel",
	"aria-label": "独立代理池库存"
}, de = { class: "pt-pool-header" }, fe = {
	key: 0,
	role: "status"
}, pe = {
	key: 1,
	role: "status"
}, me = {
	key: 0,
	class: "pt-country-summary",
	"aria-label": "分国家代理池统计"
}, he = { class: "pt-country-cards" }, ge = { key: 1 }, _e = {
	class: "pt-table-scroll",
	tabindex: "0",
	"aria-label": "代理池库存，可横向滚动"
}, ve = {
	class: "pt-table pt-pool-table",
	"data-proxy-table": "pool"
}, ye = { key: 0 }, be = { colspan: "7" }, xe = {
	class: "pt-empty",
	role: "status"
}, Se = /* @__PURE__ */ t({
	__name: "ProxyPool",
	props: {
		pool: {},
		loading: { type: Boolean }
	},
	setup(e) {
		let t = e, i = C(() => t.pool?.counts ?? {}), a = C(() => t.pool?.country_pools ?? []), s = C(() => `${[
			"fetching",
			"checking",
			"ready",
			"leased",
			"shared",
			"rotation_wait"
		].reduce((e, t) => e + (U(i.value[t]) ?? 0), 0)} / ${t.pool?.policy.max_size || "—"}`), l = [
			[
				"poolReady",
				"ready",
				"可领取"
			],
			[
				"poolFetching",
				"fetching",
				"补货中"
			],
			[
				"poolChecking",
				"checking",
				"复检中"
			],
			[
				"poolLeased",
				"leased",
				"独占使用"
			],
			[
				"poolShared",
				"shared",
				"共享使用"
			]
		], d = [
			["ready", "可领取"],
			["fetching", "补货中"],
			["checking", "复检中"],
			["leased", "独占使用"],
			["shared", "共享使用"],
			["rotation_wait", "等待轮换"],
			["quarantine", "故障隔离"]
		], f = (e) => U(e) ?? "—";
		return (t, m) => (n(), O("div", oe, [v("div", se, [v("div", null, [m[0] ||= v("span", null, "代理池容量", -1), v("strong", ce, g(e.pool ? s.value : "—"), 1)]), (n(), O(p, null, o(l, ([t, n, r]) => v("div", { key: t }, [v("span", null, g(r), 1), v("strong", { "data-proxy-summary": t }, g(e.pool ? i.value[n] || 0 : "—"), 9, le)])), 64))]), v("section", ue, [
			v("header", de, [m[1] ||= v("h3", null, "代理池库存", -1), e.pool ? (n(), O("span", fe, [
				k("显示最近 " + g(e.pool.items?.length || 0) + " 条库存 · 最小可用 " + g(e.pool.policy.min_ready || 0) + " · 本进程等待 " + g(e.pool.waiting_local || 0) + " / 维护线程 " + g(e.pool.workers_local || 0), 1),
				a.value.length ? (n(), O(p, { key: 0 }, [k(" · 分国家 " + g(a.value.length) + " 组", 1)], 64)) : u("", !0),
				e.pool.capacity_warning ? (n(), O(p, { key: 1 }, [k(" · " + g(e.pool.capacity_warning), 1)], 64)) : u("", !0)
			])) : (n(), O("span", pe, g(e.loading ? "正在加载代理池库存" : "代理池快照暂不可用"), 1))]),
			a.value.length ? (n(), O("div", me, [m[2] ||= v("strong", null, "分国家库存", -1), v("div", he, [(n(!0), O(p, null, o(a.value, (e, t) => (n(), O("div", {
				key: String(e.provider) + ":" + String(e.region) + ":" + t,
				class: "pt-country-card"
			}, [
				c(j, {
					text: D(B)(e.region || e.country, "未标注"),
					secondary: D(B)(e.provider, "未标注")
				}, null, 8, ["text", "secondary"]),
				v("p", null, g(d.map(([t, n]) => `${n} ${f(D(V)(e.counts)[t])}`).join(" · ")), 1),
				v("small", null, "等待 " + g(f(e.waiting_local)) + " · 目标 " + g(f(e.target_ready)), 1),
				e.last_supply_error ? (n(), _(P, {
					key: 0,
					label: D(q)(e.last_supply_error).label,
					title: D(q)(e.last_supply_error).evidence,
					tone: "warning"
				}, {
					details: r(() => [k(g(D(q)(e.last_supply_error).evidence), 1)]),
					_: 2
				}, 1032, ["label", "title"])) : u("", !0),
				e.last_supply_error && Number(e.retry_after_seconds) ? (n(), O("small", ge, g(e.retry_after_seconds) + " 秒后补货", 1)) : u("", !0)
			]))), 128))])])) : u("", !0),
			v("div", _e, [v("table", ve, [v("thead", null, [v("tr", null, [(n(), O(p, null, o([
				"资源",
				"状态",
				"来源 / 国家",
				"脱敏端点",
				"脱敏出口",
				"校验 / 到期",
				"最近错误"
			], (e) => v("th", {
				key: e,
				scope: "col"
			}, g(e), 1)), 64))])]), v("tbody", null, [(n(!0), O(p, null, o(e.pool?.items || [], (e, t) => (n(), O("tr", { key: String(e.resource_id || t) }, [
				v("td", null, [c(j, { text: D(B)(e.resource_id) }, null, 8, ["text"])]),
				v("td", null, [c(P, {
					label: D(K)(e.state).label,
					title: D(K)(e.state).title,
					tone: D(K)(e.state).tone
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				v("td", null, [c(j, {
					text: D(B)(e.provider),
					secondary: D(B)(e.region)
				}, null, 8, ["text", "secondary"])]),
				v("td", null, [c(j, { text: D(B)(e.endpoint) }, null, 8, ["text"])]),
				v("td", null, [c(j, { text: D(B)(e.exit_ip) }, null, 8, ["text"])]),
				v("td", null, [c(j, {
					text: `校验 ${D(F)(e.checked_at)}`,
					secondary: `到期 ${D(F)(e.expires_at)}`
				}, null, 8, ["text", "secondary"])]),
				v("td", null, [c(P, {
					label: D(q)(e.last_error_code).label,
					title: D(q)(e.last_error_code).evidence,
					tone: e.last_error_code ? "warning" : "neutral"
				}, A({ _: 2 }, [e.last_error_code ? {
					name: "details",
					fn: r(() => [k(g(D(q)(e.last_error_code).evidence), 1)]),
					key: "0"
				} : void 0]), 1032, [
					"label",
					"title",
					"tone"
				])])
			]))), 128)), e.pool?.items?.length ? u("", !0) : (n(), O("tr", ye, [v("td", be, [v("div", xe, [v("strong", null, g(e.loading && !e.pool ? "正在加载代理池库存" : e.pool ? "暂无脱敏库存" : "暂时没有代理池快照"), 1), v("p", null, g(e.pool ? "等待后台补货或复检" : "代理池服务或旧版本接口暂未返回脱敏库存"), 1)])])]))])])])
		])]));
	}
}), Z = {
	search: "搜索",
	state: "状态",
	purpose: "用途",
	window: "时间"
}, Ce = [
	{
		value: "all",
		label: "全部时间"
	},
	{
		value: "1h",
		label: "最近 1 小时"
	},
	{
		value: "24h",
		label: "最近 24 小时"
	},
	{
		value: "7d",
		label: "最近 7 天"
	}
], we = [
	"pending",
	"leased",
	"shared_pending",
	"shared_leased",
	"pool_leased"
];
function Te(e, t, n, r) {
	if (e === "window") return Ce;
	let i = e === "purpose" ? n?.purposes ?? [] : t === "traffic" ? ["available"] : (n?.lease_states ?? []).filter((e) => t === "current" ? we.includes(e) : !we.includes(e)), a = [...new Set(i.filter((e) => typeof e == "string" && e !== "all"))];
	return r && r !== "all" && !a.includes(r) && a.push(r), [{
		value: "all",
		label: e === "state" ? "全部状态" : "全部用途"
	}, ...a.map((t) => ({
		value: t,
		label: e === "state" ? K(t).label : t
	}))];
}
function Ee(e, t) {
	let n = [], r = (e, t, r) => n.push({
		key: e,
		label: `${t}：${r}`,
		title: `${t}：${r}`,
		removeLabel: `清除${t}筛选`
	});
	e.search && r("search", "搜索", e.search), e.window !== "all" && r("window", "时间", Ce.find((t) => t.value === e.window)?.label || e.window), e.purpose !== "all" && r("purpose", "用途", e.purpose);
	for (let e of [
		"current",
		"history",
		"traffic"
	]) t[e] !== "all" && r("state:" + e, {
		current: "当前状态",
		history: "历史状态",
		traffic: "采集状态"
	}[e], K(t[e]).label);
	return n;
}
// src/features/proxy/ProxyFilters.vue?vue&type=script&setup=true&lang.ts
var De = { class: "pt-filter-fields" }, Oe = {
	key: 0,
	class: "pt-filter-field"
}, ke = ["value"], Ae = {
	key: 1,
	class: "pt-filter-field"
}, je = ["value", "placeholder"], Me = ["aria-label"], Ne = [
	"data-proxy-filter-option",
	"aria-pressed",
	"onClick"
], Pe = { class: "list-filter-actions" }, Fe = /* @__PURE__ */ t({
	__name: "ProxyFilters",
	props: {
		column: {},
		triggerLabel: {},
		view: {},
		filters: {},
		state: {},
		summary: {},
		open: { type: Boolean }
	},
	emits: ["update:open", "change"],
	setup(e, { emit: t }) {
		let i = e, s = t, c = h("search"), l = C(() => [
			"search",
			"state",
			...i.view === "traffic" ? [] : ["purpose"],
			"window"
		]), m = C(() => i.column ?? (l.value.includes(c.value) ? c.value : "search")), y = C(() => m.value === "state" ? i.state : i.filters[m.value]), b = C(() => i.column ? y.value !== (m.value === "search" ? "" : "all") : l.value.some((e) => (e === "state" ? i.state : i.filters[e]) !== (e === "search" ? "" : "all")));
		function S(e) {
			s("change", m.value, e), m.value !== "search" && s("update:open", !1);
		}
		return (t, i) => (n(), _(M, {
			label: e.column ? D(Z)[e.column] : "代理记录",
			"trigger-label": e.triggerLabel || (e.column ? D(Z)[e.column] : "筛选"),
			active: b.value,
			summary: y.value,
			open: e.open,
			"onUpdate:open": i[5] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [v("div", De, [
				e.column ? u("", !0) : (n(), O("label", Oe, [i[6] ||= k("筛选列", -1), a(v("select", {
					"onUpdate:modelValue": i[0] ||= (e) => c.value = e,
					"aria-label": "选择代理记录筛选列"
				}, [(n(!0), O(p, null, o(l.value, (e) => (n(), O("option", {
					key: e,
					value: e
				}, g(D(Z)[e]), 9, ke))), 128))], 512), [[d, c.value]])])),
				m.value === "search" ? (n(), O("label", Ae, [i[7] ||= k("搜索", -1), v("input", {
					value: y.value,
					type: "search",
					placeholder: e.view === "traffic" ? "来源、方法或关联 ID" : "账号、任务、租约或 IP",
					"aria-label": "搜索代理记录",
					autocomplete: "off",
					onInput: i[1] ||= (e) => S(e.target.value),
					onKeydown: i[2] ||= f(x((e) => s("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, je)])) : (n(), O("div", {
					key: 2,
					class: "pt-filter-options",
					role: "group",
					"aria-label": D(Z)[m.value]
				}, [(n(!0), O(p, null, o(D(Te)(m.value, e.view, e.summary, y.value), (e) => (n(), O("button", {
					key: e.value,
					type: "button",
					"data-proxy-filter-option": e.value,
					"aria-pressed": e.value === y.value,
					onClick: (t) => S(e.value)
				}, g(e.label), 9, Ne))), 128))], 8, Me)),
				v("div", Pe, [v("button", {
					type: "button",
					onClick: i[3] ||= (e) => S(m.value === "search" ? "" : "all")
				}, " 清除此列"), v("button", {
					type: "button",
					class: "list-filter-primary",
					onClick: i[4] ||= (e) => s("update:open", !1)
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
}), Ie = ["aria-label", "aria-busy"], Le = ["data-proxy-table"], Re = { class: "pt-sr-only" }, ze = { key: 1 }, Be = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], Ve = ["onClick"], He = { key: 1 }, Ue = ["onClick"], We = { key: 1 }, Ge = { key: 0 }, Ke = { colspan: "8" }, qe = ["role"], Je = /* @__PURE__ */ t({
	__name: "ProxyRecordsTable",
	props: {
		view: {},
		items: {},
		filters: {},
		state: {},
		summary: {},
		loading: { type: Boolean },
		error: {},
		visible: { type: Boolean },
		openFilter: {},
		scrollRevision: {},
		facetLabel: { type: Function }
	},
	emits: [
		"filter",
		"update:openFilter",
		"detail",
		"retry"
	],
	setup(t, { expose: r, emit: a }) {
		let s = t, l = a, d = {
			current: [
				145,
				144,
				108,
				156,
				126,
				220,
				88,
				188
			],
			history: [
				145,
				144,
				108,
				156,
				126,
				220,
				188,
				92
			],
			traffic: [
				132,
				92,
				108,
				170,
				188,
				220,
				188,
				92
			]
		}, y = {
			current: "proxyCurrent",
			history: "proxyHistory",
			traffic: "proxyTraffic"
		}[s.view], S = L({
			defaults: d[s.view],
			storageKey: "gpt_console_table_widths_" + y,
			totalStorageKey: "gpt_console_table_total_" + y,
			min: 28,
			max: 2e3
		}), w = h(), T = s.scrollRevision;
		i(() => [s.items, s.scrollRevision], async () => {
			s.scrollRevision !== T && (T = s.scrollRevision, await e(), w.value && (w.value.scrollTop = 0));
		});
		let E = C(() => s.view === "traffic" ? [
			{
				label: "来源",
				filter: "search"
			},
			{ label: "方法" },
			{
				label: "采集状态",
				filter: "state"
			},
			{ label: "上传 / 下载 / 总计" },
			{ label: "请求 / 失败 / 未完成 / 未知" },
			{ label: "任务" },
			{
				label: "采集时间",
				filter: "window"
			},
			{ label: "详情" }
		] : [
			{
				label: "租约",
				filter: "search"
			},
			{ label: "出口 IP" },
			{
				label: "状态",
				filter: "state"
			},
			{ label: "账号" },
			{
				label: "用途",
				filter: "purpose"
			},
			{ label: s.view === "history" ? "任务 / 运行 / 注册 job" : "任务 / 运行" },
			...s.view === "history" ? [{
				label: "租约时间",
				filter: "window"
			}, { label: "详情" }] : [{ label: "重试序号" }, {
				label: "时间",
				filter: "window"
			}]
		]), k = C(() => ({
			current: "当前租约",
			history: "线路历史",
			traffic: "请求流量"
		})[s.view]);
		function A(e) {
			let t = F(e.acquired_at), n = e[s.view === "history" ? "released_at" : "expires_at"];
			return {
				text: t,
				secondary: n ? `至 ${F(n)}` : "进行中",
				title: `${t} · ${n ? F(n) : "进行中"}`
			};
		}
		function M(e, t) {
			s.view !== "current" && l("detail", s.view, e, t.currentTarget);
		}
		return r({ resetColumns: S.resetColumns }), (e, r) => (n(), O("div", {
			ref_key: "scroll",
			ref: w,
			class: "pt-table-scroll",
			tabindex: "0",
			"aria-label": `${k.value}列表，可横向滚动`,
			"aria-busy": t.loading
		}, [v("table", {
			class: "pt-table pt-records-table",
			"data-proxy-table": t.view,
			style: m({ "--pt-table-width": `${D(S).total.value}px` })
		}, [
			v("caption", Re, g(k.value), 1),
			v("colgroup", null, [(n(!0), O(p, null, o(D(S).widths.value, (e, t) => (n(), O("col", {
				key: t,
				style: m({ width: `${e}px` })
			}, null, 4))), 128))]),
			v("thead", null, [v("tr", null, [(n(!0), O(p, null, o(E.value, (e, i) => (n(), O("th", {
				key: e.label,
				scope: "col"
			}, [e.filter ? (n(), _(Fe, {
				key: 0,
				column: e.filter,
				"trigger-label": e.label,
				view: t.view,
				filters: t.filters,
				state: t.state,
				summary: t.summary,
				open: t.visible && t.openFilter === `${t.view}:${e.filter}`,
				onChange: r[0] ||= (e, t) => l("filter", e, t),
				"onUpdate:open": (n) => l("update:openFilter", n ? `${t.view}:${e.filter}` : null)
			}, null, 8, [
				"column",
				"trigger-label",
				"view",
				"filters",
				"state",
				"summary",
				"open",
				"onUpdate:open"
			])) : (n(), O("span", ze, g(e.label), 1)), i < E.value.length - 1 ? (n(), O("button", {
				key: 2,
				type: "button",
				class: "pt-column-resize",
				"aria-label": `调整${e.label}列宽，方向键调整`,
				onPointerdown: x((e) => D(S).resize(i, e), ["prevent"]),
				onKeydown: [f(x((e) => D(S).resizeWithKeyboard(i, -10), ["prevent"]), ["left"]), f(x((e) => D(S).resizeWithKeyboard(i, 10), ["prevent"]), ["right"])]
			}, null, 40, Be)) : u("", !0)]))), 128))])]),
			v("tbody", null, [(n(!0), O(p, null, o(t.items, (e, r) => (n(), O("tr", { key: `${t.view}:${e.id ?? r}` }, [t.view === "traffic" ? (n(), O(p, { key: 0 }, [
				v("td", null, [c(j, { text: D(B)(e.source) }, null, 8, ["text"])]),
				v("td", null, [c(j, { text: D(B)(e.method) }, null, 8, ["text"])]),
				v("td", null, [c(P, {
					label: D(X)(e).text === "未采集" ? "未采集" : "可观测",
					title: D(B)(e.availability),
					tone: D(X)(e).text === "未采集" ? "neutral" : "success"
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				v("td", null, [c(j, b({ ref_for: !0 }, D(X)(e)), null, 16)]),
				v("td", null, [c(j, {
					text: [
						e.request_count,
						e.failed_count,
						e.unfinished_count,
						e.unknown_count
					].map((e) => D(U)(e) ?? "—").join(" / "),
					title: "请求 / 失败 / 未完成 / 未知"
				}, null, 8, ["text"])]),
				v("td", null, [c(j, b({ ref_for: !0 }, D(re)(e, t.facetLabel)), null, 16)]),
				v("td", null, [c(j, b({ ref_for: !0 }, D(I)(e.started_at), { title: D(F)(e.started_at) }), null, 16, ["title"])]),
				v("td", null, [e.id == null ? (n(), O("span", He, "—")) : (n(), O("button", {
					key: 0,
					type: "button",
					class: "pt-link",
					"data-proxy-detail": "traffic",
					"aria-label": "查看请求流量详情",
					onClick: (t) => M(e, t)
				}, " 详情", 8, Ve))])
			], 64)) : (n(), O(p, { key: 1 }, [
				v("td", null, [c(j, {
					text: D(B)(e.lease_id, "未提供租约 ID"),
					secondary: D(B)(e.provider)
				}, null, 8, ["text", "secondary"])]),
				v("td", null, [c(j, { text: D(B)(e.exit_ip) }, null, 8, ["text"])]),
				v("td", null, [c(P, {
					label: D(K)(e.state).label,
					title: D(K)(e.state).title,
					tone: D(K)(e.state).tone
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				v("td", null, [c(j, { text: D(B)(e.account_id) }, null, 8, ["text"])]),
				v("td", null, [c(j, { text: D(B)(e.purpose) }, null, 8, ["text"])]),
				v("td", null, [c(j, { text: D(Y)(e, t.view === "history") }, null, 8, ["text"])]),
				t.view === "current" ? (n(), O(p, { key: 0 }, [v("td", null, [c(j, { text: D(B)(e.route_attempt_no) }, null, 8, ["text"])]), v("td", null, [c(j, b({ ref_for: !0 }, A(e)), null, 16)])], 64)) : (n(), O(p, { key: 1 }, [v("td", null, [c(j, b({ ref_for: !0 }, A(e)), null, 16)]), v("td", null, [e.id == null ? (n(), O("span", We, "—")) : (n(), O("button", {
					key: 0,
					type: "button",
					class: "pt-link",
					"data-proxy-detail": "history",
					"aria-label": "查看线路历史详情",
					onClick: (t) => M(e, t)
				}, " 详情", 8, Ue))])], 64))
			], 64))]))), 128)), t.items.length ? u("", !0) : (n(), O("tr", Ge, [v("td", Ke, [v("div", {
				class: "pt-empty",
				role: t.error ? "alert" : "status"
			}, [
				v("strong", null, g(t.loading ? `正在加载${k.value}` : t.error ? "代理与流量数据暂不可用" : `暂无${k.value}`), 1),
				v("p", null, g(t.error || (t.loading ? "正在同步代理与流量 API" : "当前没有可显示的持久化记录。")), 1),
				t.error ? (n(), O("button", {
					key: 0,
					type: "button",
					class: "pt-button",
					onClick: r[1] ||= (e) => l("retry")
				}, "重新加载")) : u("", !0)
			], 8, qe)])]))])
		], 12, Le)], 8, Ie));
	}
}), Ye = { class: "pt-detail-head" }, Xe = { id: "proxyTrafficDetailTitle" }, Ze = { class: "pt-detail-fields" }, Qe = /* @__PURE__ */ t({
	__name: "ProxyDetail",
	props: {
		snapshot: {},
		facetLabel: { type: Function }
	},
	emits: ["close"],
	setup(t, { emit: r }) {
		let a = t, s = r, c = h(), l = h(), u = C(() => a.snapshot ? ae(a.snapshot.view, a.snapshot.row, a.facetLabel) : []), d = null, f = !1;
		function m() {
			d !== null && (document.body.style.overflow = d, d = null);
		}
		return i(() => a.snapshot, async (t) => {
			await e(), f || (t ? c.value?.open || (d = document.body.style.overflow, document.body.style.overflow = "hidden", c.value?.showModal(), c.value?.scrollTo?.({ top: 0 }), l.value?.focus({ preventScroll: !0 })) : (c.value?.close(), m()));
		}, { immediate: !0 }), y(() => {
			f = !0, c.value?.close(), m();
		}), (e, r) => (n(), O("dialog", {
			ref_key: "dialog",
			ref: c,
			class: "pt-detail-dialog",
			"aria-labelledby": "proxyTrafficDetailTitle",
			onCancel: r[1] ||= x((e) => s("close"), ["prevent"]),
			onClick: r[2] ||= x((e) => s("close"), ["self"]),
			onClose: r[3] ||= (e) => t.snapshot && s("close")
		}, [v("div", Ye, [v("h3", Xe, g(t.snapshot?.view === "history" ? "线路历史详情" : "请求流量详情"), 1), v("button", {
			ref_key: "closeButton",
			ref: l,
			type: "button",
			class: "pt-button",
			"data-proxy-close-detail": "",
			"aria-label": "关闭详情",
			onClick: r[0] ||= (e) => s("close")
		}, " 关闭 ", 512)]), v("dl", Ze, [(n(!0), O(p, null, o(u.value, (e, t) => (n(), O("div", { key: `${t}:${e.label}` }, [v("dt", null, g(e.label), 1), v("dd", null, g(e.value), 1)]))), 128))])], 544));
	}
}), $e = {
	current: "/api/proxy-traffic/current",
	history: "/api/proxy-traffic/history",
	traffic: "/api/proxy-traffic/traffic"
};
function et(e, t) {
	let n = t;
	if (!n || typeof n != "object" || n.ok !== !0) throw Error("代理列表接口响应无效");
	if (n.view != null && n.view !== e) throw Error("代理列表接口视图不匹配");
	if (!Array.isArray(n.items)) throw Error("代理列表接口缺少 items");
	let r = Number(n.count), i = Number(n.total), a = Number(n.limit), o = Number(n.offset);
	if (!Number.isInteger(r) || r < 0 || r !== n.items.length || !Number.isInteger(i) || i < r || !Number.isInteger(a) || a < 1 || !Number.isInteger(o) || o < 0) throw Error("代理列表分页字段无效");
	return {
		items: n.items,
		count: r,
		total: i,
		limit: a,
		offset: o,
		has_more: typeof n.has_more == "boolean" ? n.has_more : o + r < i,
		aggregate: n.aggregate
	};
}
function tt() {
	return {
		async page(e, t, n) {
			let r = new URLSearchParams({
				limit: String(t.size),
				offset: String((t.page - 1) * t.size),
				window: t.window,
				purpose: e === "traffic" ? "all" : t.purpose,
				state: t.state,
				search: t.search.trim()
			});
			return et(e, await z($e[e] + "?" + r, { signal: n }, te));
		},
		async summary(e) {
			let t = await z("/api/proxy-traffic/summary", { signal: e });
			if (t?.ok !== !0 || !Number.isFinite(Number(t.total_bytes)) || !Number.isFinite(Number(t.today_bytes))) throw Error("流量统计接口响应无效");
			return t;
		},
		async pool(e) {
			try {
				let t = await z("/api/proxy-pool", { signal: e });
				return t?.ok === !0 && t.policy && t.counts && typeof t.counts == "object" ? {
					...t,
					items: Array.isArray(t.items) ? t.items : [],
					country_pools: Array.isArray(t.country_pools) ? t.country_pools : []
				} : null;
			} catch (e) {
				if (R(e)) throw e;
				return null;
			}
		}
	};
}
// src/features/proxy/useProxyTraffic.ts
var Q = [
	"current",
	"history",
	"traffic"
], $ = () => ({
	page: 1,
	size: 20,
	total: 0,
	state: "all",
	items: [],
	aggregate: void 0
});
function nt(t = {}) {
	let n = t.api ?? tt(), r = h(!1), i = h(t.view ?? "pool"), a = h("current"), o = s({
		window: "all",
		purpose: "all",
		search: ""
	}), c = s({
		current: $(),
		history: $(),
		traffic: $()
	}), u = T(null), d = T(null), f = T(null), p = h(!1), m = h(""), g = h(null), _ = s({
		current: 0,
		history: 0,
		traffic: 0
	}), v = h(!document.hidden), y = C(() => r.value && v.value), b = 0, x = 0, S = !1, w = null, E, D, O = null, k = !1, A = /* @__PURE__ */ new Set(), j = () => !S && r.value && !document.hidden;
	function M() {
		b++, x++, w?.abort(), w = null, clearTimeout(E), clearTimeout(D), E = D = void 0, O = null, p.value = !1;
	}
	function ee() {
		clearTimeout(D), j() && (D = setTimeout(() => {
			D = void 0, L();
		}, 3e4));
	}
	function N(t = null, n = 0) {
		t || (k = !0), M();
		let r = x;
		if (!j()) return;
		let i = () => {
			E = void 0, r === x && j() && L(t);
		};
		n ? E = setTimeout(i, n) : e(i);
	}
	function P(e) {
		let t = c[e];
		return {
			page: t.page,
			size: t.size,
			window: o.window,
			purpose: e === "traffic" ? "all" : o.purpose,
			state: t.state,
			search: o.search
		};
	}
	async function F(e, t, r) {
		let i = await n.page(e, t, r), a = t.page;
		if (r.aborted) throw new DOMException("Aborted", "AbortError");
		return i.total === 0 ? {
			result: i,
			page: 1
		} : (i.offset >= i.total && (a = Math.max(1, Math.ceil(i.total / t.size)), i = await n.page(e, {
			...t,
			page: a
		}, r), i.total === 0 && (a = 1)), {
			result: i,
			page: a
		});
	}
	function I(e, t) {
		Object.assign(c[e], {
			items: t.result.items,
			total: t.result.total,
			page: t.page,
			aggregate: t.result.aggregate
		});
	}
	async function L(e = null) {
		if (!j()) return;
		let r = !e || !u.value || k, i = r || d.value === null, a = r ? Q : Q.filter((t) => t === e || A.has(t)), o = Object.fromEntries(a.map((e) => [e, P(e)])), s = JSON.stringify([r, o]);
		if (O?.key === s) return O.promise;
		M(), r && (k = !0);
		let l = b, f = new AbortController();
		w = f, p.value = !0;
		let h = (async () => {
			try {
				let e = i ? n.pool(f.signal).catch((e) => {
					if (R(e)) throw e;
					return null;
				}) : null, [s, c, p] = await Promise.all([
					Promise.all(a.map(async (e) => ({
						name: e,
						...await F(e, o[e], f.signal)
					}))),
					r ? n.summary(f.signal) : null,
					e
				]);
				if (l !== b || !j()) return;
				s.forEach((e) => {
					I(e.name, e), A.delete(e.name) && _[e.name]++;
				}), r && (c && (u.value = c), k = !1), i && (d.value = p), m.value = "", t.onReady?.();
			} catch (e) {
				if (l !== b || !j() || R(e)) return;
				a.forEach((e) => {
					c[e].items = [], c[e].total = 0;
				}), r && (u.value = null, d.value = null), m.value = e instanceof Error ? e.message : String(e);
			} finally {
				l === b && (p.value = !1, w = null, O = null, ee());
			}
		})();
		return O = {
			key: s,
			promise: h
		}, h;
	}
	function z(t = {}) {
		let n = f.value?.opener;
		f.value = null, t.restoreFocus !== !1 && n?.isConnected && e(() => n.focus({ preventScroll: !0 }));
	}
	function te(e) {
		S || r.value === e || (r.value = e, e ? N() : (M(), g.value = null, z({ restoreFocus: !1 })));
	}
	function B(e) {
		!S && ["pool", "records"].includes(e) && i.value !== e && (i.value = e, g.value = null, z({ restoreFocus: !1 }));
	}
	function V(e) {
		!S && Q.includes(e) && a.value !== e && (a.value = e, g.value = null, z({ restoreFocus: !1 }));
	}
	function H(e) {
		let t = Object.keys(e).filter((t) => e[t] !== void 0 && e[t] !== o[t]);
		t.length && !S && (t.forEach((t) => {
			o[t] = e[t];
		}), Q.forEach((e) => {
			c[e].page = 1, A.add(e);
		}), N(null, t.every((e) => e === "search") ? 260 : 0));
	}
	function U(e, t) {
		S || c[e].state === t || (c[e].state = t, c[e].page = 1, A.add(e), N(e));
	}
	function W(e, t) {
		if (S || !Number.isFinite(t)) return;
		let n = c[e], r = Math.min(Math.max(1, Math.ceil(n.total / n.size)), Math.max(1, Math.floor(t)));
		r !== n.page && (n.page = r, A.add(e), N(e));
	}
	function G(e, t) {
		!S && [
			20,
			50,
			100
		].includes(t) && c[e].size !== t && (c[e].size = t, c[e].page = 1, A.add(e), N(e));
	}
	function K() {
		Object.assign(o, {
			window: "all",
			purpose: "all",
			search: ""
		}), Q.forEach((e) => {
			c[e].state = "all", c[e].page = 1, A.add(e);
		}), N();
	}
	function ne(e) {
		e.startsWith("state:") ? U(e.slice(6), "all") : e === "search" ? H({ search: "" }) : (e === "window" || e === "purpose") && H({ [e]: "all" });
	}
	function q(e, t, n = null) {
		!S && j() && (f.value = {
			view: e,
			row: JSON.parse(JSON.stringify(t)),
			opener: n
		});
	}
	function J() {
		v.value = !document.hidden, document.hidden ? (M(), g.value = null, z({ restoreFocus: !1 })) : r.value && N();
	}
	document.addEventListener("visibilitychange", J);
	function Y() {
		S || (S = !0, M(), z({ restoreFocus: !1 }), document.removeEventListener("visibilitychange", J));
	}
	return l(Y), t.visible && te(!0), {
		visible: r,
		active: y,
		documentVisible: v,
		view: i,
		recordView: a,
		filters: o,
		pages: c,
		summary: u,
		pool: d,
		detail: f,
		loading: p,
		error: m,
		openFilter: g,
		scrollRevision: _,
		load: L,
		setVisible: te,
		setView: B,
		setRecordView: V,
		updateFilters: H,
		setState: U,
		setPage: W,
		setSize: G,
		resetFilters: K,
		removeFilter: ne,
		openDetail: q,
		closeDetail: z,
		dispose: Y
	};
}
// src/features/proxy/ProxyTrafficPage.vue?vue&type=script&setup=true&lang.ts
var rt = {
	class: "pt-root",
	"data-proxy-vue": ""
}, it = {
	class: "pt-workspace",
	"data-proxy-module-panel": "records"
}, at = {
	class: "pt-summary",
	"aria-label": "租约与流量摘要"
}, ot = { "data-proxy-summary": "totalBytes" }, st = { "data-proxy-summary": "todayBytes" }, ct = { "data-proxy-summary": "todayRequestCount" }, lt = { "data-proxy-summary": "todayRouteCount" }, ut = { class: "pt-tabs-row" }, dt = [
	"data-proxy-view",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], ft = { class: "pt-toolbar" }, pt = { class: "pt-toolbar-main" }, mt = {
	class: "pt-count",
	role: "status"
}, ht = { class: "pt-toolbar-actions" }, gt = { class: "pt-mobile-filter" }, _t = [
	"id",
	"aria-label",
	"aria-hidden",
	"data-proxy-panel"
], vt = /* @__PURE__ */ t({
	__name: "ProxyTrafficPage",
	props: { deps: {} },
	setup(e, { expose: t }) {
		let r = e, i = nt(r.deps), { view: s, recordView: l, filters: d, pages: f, summary: m, pool: _, detail: y, loading: b, error: x, active: w, openFilter: T } = i, A = h({}), j = [
			"current",
			"history",
			"traffic"
		], M = {
			current: "当前租约",
			history: "线路历史",
			traffic: "请求流量"
		}, P = C(() => Ee(d, {
			current: f.current.state,
			history: f.history.state,
			traffic: f.traffic.state
		})), F = C(() => f[l.value]);
		function I(e, t, n) {
			t === "state" ? i.setState(e, n) : i.updateFilters({ [t]: n });
		}
		function L() {
			A.value[l.value]?.resetColumns(), r.deps.notify?.("已恢复默认列宽");
		}
		function R(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			e.preventDefault();
			let t = j.indexOf(l.value), n = e.key === "Home" ? 0 : e.key === "End" ? j.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + j.length) % j.length;
			i.setRecordView(j[n]), e.currentTarget.querySelector(`[data-proxy-view="${j[n]}"]`)?.focus({ preventScroll: !0 });
		}
		return t({
			load: i.load,
			setVisible: i.setVisible,
			setView: i.setView,
			closeDetail: i.closeDetail
		}), (t, r) => (n(), O("div", rt, [
			a(c(Se, {
				pool: D(_),
				loading: D(b)
			}, null, 8, ["pool", "loading"]), [[E, D(s) === "pool"]]),
			a(v("div", it, [
				v("div", at, [
					v("div", null, [r[6] ||= v("span", null, "累计可观测流量", -1), v("strong", ot, g(D(m) ? D(W)(D(m).total_bytes) : "—"), 1)]),
					v("div", null, [r[7] ||= v("span", null, "今日可观测流量", -1), v("strong", st, g(D(m) ? D(W)(D(m).today_bytes) : "—"), 1)]),
					v("div", null, [r[8] ||= v("span", null, "今日请求记录", -1), v("strong", ct, g(D(m) ? D(m).today_request_count ?? D(m).today_browser_count ?? "—" : "—"), 1)]),
					v("div", null, [r[9] ||= v("span", null, "今日新建线路", -1), v("strong", lt, g(D(m)?.today_route_count ?? "—"), 1)])
				]),
				v("div", ut, [v("div", {
					class: "pt-view-tabs",
					role: "tablist",
					"aria-label": "代理与流量视图",
					onKeydown: R
				}, [(n(), O(p, null, o(j, (e) => v("button", {
					key: e,
					type: "button",
					role: "tab",
					"data-proxy-view": e,
					"aria-selected": D(l) === e,
					"aria-controls": `proxy-panel-${e}`,
					tabindex: D(l) === e ? 0 : -1,
					class: S({ "is-active": D(l) === e }),
					onClick: (t) => D(i).setRecordView(e)
				}, [k(g(M[e]) + " ", 1), v("span", null, g(D(x) ? "—" : D(f)[e].total), 1)], 10, dt)), 64))], 32)]),
				v("div", ft, [v("div", pt, [v("span", mt, g(D(x) ? "数据暂不可用" : `${F.value.total.toLocaleString()} 条记录`), 1), c(ee, {
					items: P.value,
					onRemove: D(i).removeFilter
				}, null, 8, ["items", "onRemove"])]), v("div", ht, [
					v("span", gt, [c(Fe, {
						view: D(l),
						filters: D(d),
						state: F.value.state,
						summary: D(m),
						open: D(w) && D(T) === "all",
						onChange: r[0] ||= (e, t) => I(D(l), e, t),
						"onUpdate:open": r[1] ||= (e) => T.value = e ? "all" : null
					}, null, 8, [
						"view",
						"filters",
						"state",
						"summary",
						"open"
					])]),
					P.value.length ? (n(), O("button", {
						key: 0,
						type: "button",
						class: "pt-link",
						onClick: r[2] ||= (...e) => D(i).resetFilters && D(i).resetFilters(...e)
					}, " 清筛")) : u("", !0),
					v("button", {
						type: "button",
						class: "pt-link",
						"aria-label": "恢复当前列表列宽",
						onClick: L
					}, " 恢复列宽 ")
				])]),
				(n(), O(p, null, o(j, (t) => a(v("section", {
					id: `proxy-panel-${t}`,
					key: t,
					role: "tabpanel",
					"aria-label": M[t],
					"aria-hidden": D(l) !== t,
					"data-proxy-panel": t,
					class: "pt-panel"
				}, [c(Je, {
					ref_for: !0,
					ref: (e) => {
						e && (A.value[t] = e);
					},
					view: t,
					items: D(f)[t].items,
					filters: D(d),
					state: D(f)[t].state,
					summary: D(m),
					loading: D(b),
					error: D(x),
					visible: D(w) && D(s) === "records" && D(l) === t,
					"open-filter": D(T),
					"scroll-revision": D(i).scrollRevision[t],
					"facet-label": e.deps.facetLabel,
					onFilter: (e, n) => I(t, e, n),
					"onUpdate:openFilter": r[3] ||= (e) => T.value = e,
					onDetail: D(i).openDetail,
					onRetry: r[4] ||= (e) => D(i).load()
				}, null, 8, [
					"view",
					"items",
					"filters",
					"state",
					"summary",
					"loading",
					"error",
					"visible",
					"open-filter",
					"scroll-revision",
					"facet-label",
					"onFilter",
					"onDetail"
				]), c(N, {
					page: D(f)[t].page,
					size: D(f)[t].size,
					total: D(f)[t].total,
					busy: D(b),
					"page-sizes": [
						20,
						50,
						100
					],
					label: `${M[t]}分页`,
					"onUpdate:page": (e) => D(i).setPage(t, e),
					"onUpdate:size": (e) => D(i).setSize(t, e)
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy",
					"label",
					"onUpdate:page",
					"onUpdate:size"
				])], 8, _t), [[E, D(l) === t]])), 64))
			], 512), [[E, D(s) === "records"]]),
			c(Qe, {
				snapshot: D(y),
				"facet-label": e.deps.facetLabel,
				onClose: r[5] ||= (e) => D(i).closeDetail()
			}, null, 8, ["snapshot", "facet-label"])
		]));
	}
});
// src/proxy.ts
function yt(e, t = {}) {
	let n = w(vt, { deps: t }), r = n.mount(e);
	return {
		load: r.load,
		setVisible: r.setVisible,
		setView: r.setView,
		closeDetail: r.closeDetail,
		destroy: () => n.unmount()
	};
}
export { yt as mountProxyTraffic };
