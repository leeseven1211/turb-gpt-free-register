import { $ as e, A as t, G as n, I as r, O as i, P as a, S as o, V as s, W as c, X as l, Z as u, _ as d, b as f, c as p, ct as m, dt as h, g, h as _, i as v, k as y, m as b, n as x, o as S, ot as C, p as w, s as T, tt as E, u as D, ut as O, v as k, x as A } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { n as j, r as M, t as N } from "./ListFilterSummary-NiVwXoAn.js";
import { t as ee } from "./ListPagination-CFFXEHba.js";
import { t as P } from "./ListResult-3o6cJKgT.js";
import { n as F, t as I } from "./time-DOD6oyhP.js";
import { t as L } from "./useColumnWidths-DKwoq5eG.js";
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
function ie(e, t, n) {
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
		["状态族", t.status_families ? Object.entries(V(t.status_families)).map(([e, t]) => `${e}: ${B(t)}`).join(" / ") : null],
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
var ae = {
	class: "pt-workspace",
	"data-proxy-module-panel": "pool"
}, oe = {
	class: "pt-summary",
	"aria-label": "代理池库存摘要"
}, se = { "data-proxy-summary": "poolCapacity" }, ce = ["data-proxy-summary"], le = {
	class: "pt-panel",
	"aria-label": "独立代理池库存"
}, ue = { class: "pt-pool-header" }, de = {
	key: 0,
	role: "status"
}, fe = {
	key: 1,
	role: "status"
}, pe = {
	key: 0,
	class: "pt-country-summary",
	"aria-label": "分国家代理池统计"
}, me = { class: "pt-country-cards" }, he = { key: 1 }, ge = {
	class: "pt-table-scroll",
	tabindex: "0",
	"aria-label": "代理池库存，可横向滚动"
}, _e = {
	class: "pt-table pt-pool-table",
	"data-proxy-table": "pool"
}, ve = { key: 0 }, ye = { colspan: "7" }, be = {
	class: "pt-empty",
	role: "status"
}, xe = /* @__PURE__ */ o({
	__name: "ProxyPool",
	props: {
		pool: {},
		loading: { type: Boolean }
	},
	setup(e) {
		let t = e, n = w(() => t.pool?.counts ?? {}), i = w(() => t.pool?.country_pools ?? []), o = w(() => `${[
			"fetching",
			"checking",
			"ready",
			"leased",
			"shared",
			"rotation_wait"
		].reduce((e, t) => e + (U(n.value[t]) ?? 0), 0)} / ${t.pool?.policy.max_size || "—"}`), s = [
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
		], l = [
			["ready", "可领取"],
			["fetching", "补货中"],
			["checking", "复检中"],
			["leased", "独占使用"],
			["shared", "共享使用"],
			["rotation_wait", "等待轮换"],
			["quarantine", "故障隔离"]
		], u = (e) => U(e) ?? "—";
		return (t, p) => (a(), d("div", ae, [b("div", oe, [b("div", null, [p[0] ||= b("span", null, "代理池容量", -1), b("strong", se, h(e.pool ? o.value : "—"), 1)]), (a(), d(D, null, r(s, ([t, r, i]) => b("div", { key: t }, [b("span", null, h(i), 1), b("strong", { "data-proxy-summary": t }, h(e.pool ? n.value[r] || 0 : "—"), 9, ce)])), 64))]), b("section", le, [
			b("header", ue, [p[1] ||= b("h3", null, "代理池库存", -1), e.pool ? (a(), d("span", de, [
				f("显示最近 " + h(e.pool.items?.length || 0) + " 条库存 · 最小可用 " + h(e.pool.policy.min_ready || 0) + " · 本进程等待 " + h(e.pool.waiting_local || 0) + " / 维护线程 " + h(e.pool.workers_local || 0), 1),
				i.value.length ? (a(), d(D, { key: 0 }, [f(" · 分国家 " + h(i.value.length) + " 组", 1)], 64)) : g("", !0),
				e.pool.capacity_warning ? (a(), d(D, { key: 1 }, [f(" · " + h(e.pool.capacity_warning), 1)], 64)) : g("", !0)
			])) : (a(), d("span", fe, h(e.loading ? "正在加载代理池库存" : "代理池快照暂不可用"), 1))]),
			i.value.length ? (a(), d("div", pe, [p[2] ||= b("strong", null, "分国家库存", -1), b("div", me, [(a(!0), d(D, null, r(i.value, (e, t) => (a(), d("div", {
				key: String(e.provider) + ":" + String(e.region) + ":" + t,
				class: "pt-country-card"
			}, [
				A(j, {
					text: C(B)(e.region || e.country, "未标注"),
					secondary: C(B)(e.provider, "未标注")
				}, null, 8, ["text", "secondary"]),
				b("p", null, h(l.map(([t, n]) => `${n} ${u(C(V)(e.counts)[t])}`).join(" · ")), 1),
				b("small", null, "等待 " + h(u(e.waiting_local)) + " · 目标 " + h(u(e.target_ready)), 1),
				e.last_supply_error ? (a(), _(P, {
					key: 0,
					label: C(q)(e.last_supply_error).label,
					title: C(q)(e.last_supply_error).evidence,
					tone: "warning"
				}, {
					details: c(() => [f(h(C(q)(e.last_supply_error).evidence), 1)]),
					_: 2
				}, 1032, ["label", "title"])) : g("", !0),
				e.last_supply_error && Number(e.retry_after_seconds) ? (a(), d("small", he, h(e.retry_after_seconds) + " 秒后补货", 1)) : g("", !0)
			]))), 128))])])) : g("", !0),
			b("div", ge, [b("table", _e, [b("thead", null, [b("tr", null, [(a(), d(D, null, r([
				"资源",
				"状态",
				"来源 / 国家",
				"脱敏端点",
				"脱敏出口",
				"校验 / 到期",
				"最近错误"
			], (e) => b("th", {
				key: e,
				scope: "col"
			}, h(e), 1)), 64))])]), b("tbody", null, [(a(!0), d(D, null, r(e.pool?.items || [], (e, t) => (a(), d("tr", { key: String(e.resource_id || t) }, [
				b("td", null, [A(j, { text: C(B)(e.resource_id) }, null, 8, ["text"])]),
				b("td", null, [A(P, {
					label: C(K)(e.state).label,
					title: C(K)(e.state).title,
					tone: C(K)(e.state).tone
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				b("td", null, [A(j, {
					text: C(B)(e.provider),
					secondary: C(B)(e.region)
				}, null, 8, ["text", "secondary"])]),
				b("td", null, [A(j, { text: C(B)(e.endpoint) }, null, 8, ["text"])]),
				b("td", null, [A(j, { text: C(B)(e.exit_ip) }, null, 8, ["text"])]),
				b("td", null, [A(j, {
					text: `校验 ${C(F)(e.checked_at)}`,
					secondary: `到期 ${C(F)(e.expires_at)}`
				}, null, 8, ["text", "secondary"])]),
				b("td", null, [A(P, {
					label: C(q)(e.last_error_code).label,
					title: C(q)(e.last_error_code).evidence,
					tone: e.last_error_code ? "warning" : "neutral"
				}, k({ _: 2 }, [e.last_error_code ? {
					name: "details",
					fn: c(() => [f(h(C(q)(e.last_error_code).evidence), 1)]),
					key: "0"
				} : void 0]), 1032, [
					"label",
					"title",
					"tone"
				])])
			]))), 128)), e.pool?.items?.length ? g("", !0) : (a(), d("tr", ve, [b("td", ye, [b("div", be, [b("strong", null, h(e.loading && !e.pool ? "正在加载代理池库存" : e.pool ? "暂无脱敏库存" : "暂时没有代理池快照"), 1), b("p", null, h(e.pool ? "等待后台补货或复检" : "代理池服务或旧版本接口暂未返回脱敏库存"), 1)])])]))])])])
		])]));
	}
}), Z = {
	search: "搜索",
	state: "状态",
	purpose: "用途",
	window: "时间"
}, Se = [
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
], Ce = [
	"pending",
	"leased",
	"shared_pending",
	"shared_leased",
	"pool_leased"
];
function we(e, t, n, r) {
	if (e === "window") return Se;
	let i = e === "purpose" ? n?.purposes ?? [] : t === "traffic" ? ["available"] : (n?.lease_states ?? []).filter((e) => t === "current" ? Ce.includes(e) : !Ce.includes(e)), a = [...new Set(i.filter((e) => typeof e == "string" && e !== "all"))];
	return r && r !== "all" && !a.includes(r) && a.push(r), [{
		value: "all",
		label: e === "state" ? "全部状态" : "全部用途"
	}, ...a.map((t) => ({
		value: t,
		label: e === "state" ? K(t).label : t
	}))];
}
function Te(e, t) {
	let n = [], r = (e, t, r) => n.push({
		key: e,
		label: `${t}：${r}`,
		title: `${t}：${r}`,
		removeLabel: `清除${t}筛选`
	});
	e.search && r("search", "搜索", e.search), e.window !== "all" && r("window", "时间", Se.find((t) => t.value === e.window)?.label || e.window), e.purpose !== "all" && r("purpose", "用途", e.purpose);
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
var Ee = { class: "pt-filter-fields" }, De = {
	key: 0,
	class: "pt-filter-field"
}, Oe = ["value"], ke = {
	key: 1,
	class: "pt-filter-field"
}, Ae = ["value", "placeholder"], je = ["aria-label"], Me = [
	"data-proxy-filter-option",
	"aria-pressed",
	"onClick"
], Ne = { class: "pt-filter-actions" }, Pe = /* @__PURE__ */ o({
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
	setup(t, { emit: i }) {
		let o = t, s = i, l = e("search"), u = w(() => [
			"search",
			"state",
			...o.view === "traffic" ? [] : ["purpose"],
			"window"
		]), m = w(() => o.column ?? (u.value.includes(l.value) ? l.value : "search")), y = w(() => m.value === "state" ? o.state : o.filters[m.value]), x = w(() => o.column ? y.value !== (m.value === "search" ? "" : "all") : u.value.some((e) => (e === "state" ? o.state : o.filters[e]) !== (e === "search" ? "" : "all")));
		function S(e) {
			s("change", m.value, e), m.value !== "search" && s("update:open", !1);
		}
		return (e, i) => (a(), _(M, {
			label: t.column ? C(Z)[t.column] : "代理记录",
			"trigger-label": t.triggerLabel || (t.column ? C(Z)[t.column] : "筛选"),
			active: x.value,
			summary: y.value,
			open: t.open,
			"onUpdate:open": i[5] ||= (e) => s("update:open", e)
		}, {
			default: c(() => [b("div", Ee, [
				t.column ? g("", !0) : (a(), d("label", De, [i[6] ||= f("筛选列", -1), n(b("select", {
					"onUpdate:modelValue": i[0] ||= (e) => l.value = e,
					"aria-label": "选择代理记录筛选列"
				}, [(a(!0), d(D, null, r(u.value, (e) => (a(), d("option", {
					key: e,
					value: e
				}, h(C(Z)[e]), 9, Oe))), 128))], 512), [[v, l.value]])])),
				m.value === "search" ? (a(), d("label", ke, [i[7] ||= f("搜索", -1), b("input", {
					value: y.value,
					type: "search",
					placeholder: t.view === "traffic" ? "来源、方法或关联 ID" : "账号、任务、租约或 IP",
					"aria-label": "搜索代理记录",
					autocomplete: "off",
					onInput: i[1] ||= (e) => S(e.target.value),
					onKeydown: i[2] ||= T(p((e) => s("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, Ae)])) : (a(), d("div", {
					key: 2,
					class: "pt-filter-options",
					role: "group",
					"aria-label": C(Z)[m.value]
				}, [(a(!0), d(D, null, r(C(we)(m.value, t.view, t.summary, y.value), (e) => (a(), d("button", {
					key: e.value,
					type: "button",
					"data-proxy-filter-option": e.value,
					"aria-pressed": e.value === y.value,
					onClick: (t) => S(e.value)
				}, h(e.label), 9, Me))), 128))], 8, je)),
				b("div", Ne, [b("button", {
					type: "button",
					class: "pt-link",
					onClick: i[3] ||= (e) => S(m.value === "search" ? "" : "all")
				}, "清除此列"), b("button", {
					type: "button",
					class: "pt-button",
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
}), Fe = ["aria-label", "aria-busy"], Ie = ["data-proxy-table"], Le = { class: "pt-sr-only" }, Re = { key: 1 }, ze = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], Be = ["onClick"], Ve = { key: 1 }, He = ["onClick"], Ue = { key: 1 }, We = { key: 0 }, Ge = { colspan: "8" }, Ke = ["role"], qe = /* @__PURE__ */ o({
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
	setup(t, { expose: n, emit: o }) {
		let c = t, l = o, u = {
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
		}, f = {
			current: "proxyCurrent",
			history: "proxyHistory",
			traffic: "proxyTraffic"
		}[c.view], m = L({
			defaults: u[c.view],
			storageKey: "gpt_console_table_widths_" + f,
			totalStorageKey: "gpt_console_table_total_" + f,
			min: 28,
			max: 2e3
		}), v = e(), x = c.scrollRevision;
		s(() => [c.items, c.scrollRevision], async () => {
			c.scrollRevision !== x && (x = c.scrollRevision, await y(), v.value && (v.value.scrollTop = 0));
		});
		let S = w(() => c.view === "traffic" ? [
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
			{ label: c.view === "history" ? "任务 / 运行 / 注册 job" : "任务 / 运行" },
			...c.view === "history" ? [{
				label: "租约时间",
				filter: "window"
			}, { label: "详情" }] : [{ label: "重试序号" }, {
				label: "时间",
				filter: "window"
			}]
		]), E = w(() => ({
			current: "当前租约",
			history: "线路历史",
			traffic: "请求流量"
		})[c.view]);
		function k(e) {
			let t = F(e.acquired_at), n = e[c.view === "history" ? "released_at" : "expires_at"];
			return {
				text: t,
				secondary: n ? `至 ${F(n)}` : "进行中",
				title: `${t} · ${n ? F(n) : "进行中"}`
			};
		}
		function M(e, t) {
			c.view !== "current" && l("detail", c.view, e, t.currentTarget);
		}
		return n({ resetColumns: m.resetColumns }), (e, n) => (a(), d("div", {
			ref_key: "scroll",
			ref: v,
			class: "pt-table-scroll",
			tabindex: "0",
			"aria-label": `${E.value}列表，可横向滚动`,
			"aria-busy": t.loading
		}, [b("table", {
			class: "pt-table pt-records-table",
			"data-proxy-table": t.view,
			style: O({ "--pt-table-width": `${C(m).total.value}px` })
		}, [
			b("caption", Le, h(E.value), 1),
			b("colgroup", null, [(a(!0), d(D, null, r(C(m).widths.value, (e, t) => (a(), d("col", {
				key: t,
				style: O({ width: `${e}px` })
			}, null, 4))), 128))]),
			b("thead", null, [b("tr", null, [(a(!0), d(D, null, r(S.value, (e, r) => (a(), d("th", {
				key: e.label,
				scope: "col"
			}, [e.filter ? (a(), _(Pe, {
				key: 0,
				column: e.filter,
				"trigger-label": e.label,
				view: t.view,
				filters: t.filters,
				state: t.state,
				summary: t.summary,
				open: t.visible && t.openFilter === `${t.view}:${e.filter}`,
				onChange: n[0] ||= (e, t) => l("filter", e, t),
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
			])) : (a(), d("span", Re, h(e.label), 1)), r < S.value.length - 1 ? (a(), d("button", {
				key: 2,
				type: "button",
				class: "pt-column-resize",
				"aria-label": `调整${e.label}列宽，方向键调整`,
				onPointerdown: p((e) => C(m).resize(r, e), ["prevent"]),
				onKeydown: [T(p((e) => C(m).resizeWithKeyboard(r, -10), ["prevent"]), ["left"]), T(p((e) => C(m).resizeWithKeyboard(r, 10), ["prevent"]), ["right"])]
			}, null, 40, ze)) : g("", !0)]))), 128))])]),
			b("tbody", null, [(a(!0), d(D, null, r(t.items, (e, n) => (a(), d("tr", { key: `${t.view}:${e.id ?? n}` }, [t.view === "traffic" ? (a(), d(D, { key: 0 }, [
				b("td", null, [A(j, { text: C(B)(e.source) }, null, 8, ["text"])]),
				b("td", null, [A(j, { text: C(B)(e.method) }, null, 8, ["text"])]),
				b("td", null, [A(P, {
					label: C(X)(e).text === "未采集" ? "未采集" : "可观测",
					title: C(B)(e.availability),
					tone: C(X)(e).text === "未采集" ? "neutral" : "success"
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				b("td", null, [A(j, i({ ref_for: !0 }, C(X)(e)), null, 16)]),
				b("td", null, [A(j, {
					text: [
						e.request_count,
						e.failed_count,
						e.unfinished_count,
						e.unknown_count
					].map((e) => C(U)(e) ?? "—").join(" / "),
					title: "请求 / 失败 / 未完成 / 未知"
				}, null, 8, ["text"])]),
				b("td", null, [A(j, i({ ref_for: !0 }, C(re)(e, t.facetLabel)), null, 16)]),
				b("td", null, [A(j, i({ ref_for: !0 }, C(I)(e.started_at), { title: C(F)(e.started_at) }), null, 16, ["title"])]),
				b("td", null, [e.id == null ? (a(), d("span", Ve, "—")) : (a(), d("button", {
					key: 0,
					type: "button",
					class: "pt-link",
					"data-proxy-detail": "traffic",
					"aria-label": "查看请求流量详情",
					onClick: (t) => M(e, t)
				}, "详情", 8, Be))])
			], 64)) : (a(), d(D, { key: 1 }, [
				b("td", null, [A(j, {
					text: C(B)(e.lease_id, "未提供租约 ID"),
					secondary: C(B)(e.provider)
				}, null, 8, ["text", "secondary"])]),
				b("td", null, [A(j, { text: C(B)(e.exit_ip) }, null, 8, ["text"])]),
				b("td", null, [A(P, {
					label: C(K)(e.state).label,
					title: C(K)(e.state).title,
					tone: C(K)(e.state).tone
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				b("td", null, [A(j, { text: C(B)(e.account_id) }, null, 8, ["text"])]),
				b("td", null, [A(j, { text: C(B)(e.purpose) }, null, 8, ["text"])]),
				b("td", null, [A(j, { text: C(Y)(e, t.view === "history") }, null, 8, ["text"])]),
				t.view === "current" ? (a(), d(D, { key: 0 }, [b("td", null, [A(j, { text: C(B)(e.route_attempt_no) }, null, 8, ["text"])]), b("td", null, [A(j, i({ ref_for: !0 }, k(e)), null, 16)])], 64)) : (a(), d(D, { key: 1 }, [b("td", null, [A(j, i({ ref_for: !0 }, k(e)), null, 16)]), b("td", null, [e.id == null ? (a(), d("span", Ue, "—")) : (a(), d("button", {
					key: 0,
					type: "button",
					class: "pt-link",
					"data-proxy-detail": "history",
					"aria-label": "查看线路历史详情",
					onClick: (t) => M(e, t)
				}, "详情", 8, He))])], 64))
			], 64))]))), 128)), t.items.length ? g("", !0) : (a(), d("tr", We, [b("td", Ge, [b("div", {
				class: "pt-empty",
				role: t.error ? "alert" : "status"
			}, [
				b("strong", null, h(t.loading ? `正在加载${E.value}` : t.error ? "代理与流量数据暂不可用" : `暂无${E.value}`), 1),
				b("p", null, h(t.error || (t.loading ? "正在同步代理与流量 API" : "当前没有可显示的持久化记录。")), 1),
				t.error ? (a(), d("button", {
					key: 0,
					type: "button",
					class: "pt-button",
					onClick: n[1] ||= (e) => l("retry")
				}, "重新加载")) : g("", !0)
			], 8, Ke)])]))])
		], 12, Ie)], 8, Fe));
	}
}), Je = { class: "pt-detail-head" }, Ye = { id: "proxyTrafficDetailTitle" }, Xe = { class: "pt-detail-fields" }, Ze = /* @__PURE__ */ o({
	__name: "ProxyDetail",
	props: {
		snapshot: {},
		facetLabel: { type: Function }
	},
	emits: ["close"],
	setup(n, { emit: i }) {
		let o = n, c = i, l = e(), u = e(), f = w(() => o.snapshot ? ie(o.snapshot.view, o.snapshot.row, o.facetLabel) : []), m = null, g = !1;
		function _() {
			m !== null && (document.body.style.overflow = m, m = null);
		}
		return s(() => o.snapshot, async (e) => {
			await y(), g || (e ? l.value?.open || (m = document.body.style.overflow, document.body.style.overflow = "hidden", l.value?.showModal(), l.value?.scrollTo?.({ top: 0 }), u.value?.focus({ preventScroll: !0 })) : (l.value?.close(), _()));
		}, { immediate: !0 }), t(() => {
			g = !0, l.value?.close(), _();
		}), (e, t) => (a(), d("dialog", {
			ref_key: "dialog",
			ref: l,
			class: "pt-detail-dialog",
			"aria-labelledby": "proxyTrafficDetailTitle",
			onCancel: t[1] ||= p((e) => c("close"), ["prevent"]),
			onClick: t[2] ||= p((e) => c("close"), ["self"]),
			onClose: t[3] ||= (e) => n.snapshot && c("close")
		}, [b("div", Je, [b("h3", Ye, h(n.snapshot?.view === "history" ? "线路历史详情" : "请求流量详情"), 1), b("button", {
			ref_key: "closeButton",
			ref: u,
			type: "button",
			class: "pt-button",
			"data-proxy-close-detail": "",
			"aria-label": "关闭详情",
			onClick: t[0] ||= (e) => c("close")
		}, "关闭", 512)]), b("dl", Xe, [(a(!0), d(D, null, r(f.value, (e, t) => (a(), d("div", { key: `${t}:${e.label}` }, [b("dt", null, h(e.label), 1), b("dd", null, h(e.value), 1)]))), 128))])], 544));
	}
}), Qe = {
	current: "/api/proxy-traffic/current",
	history: "/api/proxy-traffic/history",
	traffic: "/api/proxy-traffic/traffic"
};
function $e(e, t) {
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
function et() {
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
			return $e(e, await z(Qe[e] + "?" + r, { signal: n }, te));
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
function tt(t = {}) {
	let n = t.api ?? et(), r = e(!1), i = e(t.view ?? "pool"), a = e("current"), o = u({
		window: "all",
		purpose: "all",
		search: ""
	}), s = u({
		current: $(),
		history: $(),
		traffic: $()
	}), c = E(null), d = E(null), f = E(null), p = e(!1), m = e(""), h = e(null), g = u({
		current: 0,
		history: 0,
		traffic: 0
	}), _ = e(!document.hidden), v = w(() => r.value && _.value), b = 0, x = 0, S = !1, C = null, T, D, O = null, k = /* @__PURE__ */ new Set(), A = () => !S && r.value && !document.hidden;
	function j() {
		b++, x++, C?.abort(), C = null, clearTimeout(T), clearTimeout(D), T = D = void 0, O = null, p.value = !1;
	}
	function M() {
		clearTimeout(D), A() && (D = setTimeout(() => {
			D = void 0, I();
		}, 3e4));
	}
	function N(e = null, t = 0) {
		j();
		let n = x;
		if (!A()) return;
		let r = () => {
			T = void 0, n === x && A() && I(e);
		};
		t ? T = setTimeout(r, t) : y(r);
	}
	function ee(e) {
		let t = s[e];
		return {
			page: t.page,
			size: t.size,
			window: o.window,
			purpose: e === "traffic" ? "all" : o.purpose,
			state: t.state,
			search: o.search
		};
	}
	async function P(e, t, r) {
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
	function F(e, t) {
		Object.assign(s[e], {
			items: t.result.items,
			total: t.result.total,
			page: t.page,
			aggregate: t.result.aggregate
		});
	}
	async function I(e = null) {
		if (!A()) return;
		c.value || (e = null);
		let r = e ? [e] : Q, i = Object.fromEntries(r.map((e) => [e, ee(e)])), a = JSON.stringify([e, i]);
		if (O?.key === a) return O.promise;
		j();
		let o = b, l = new AbortController();
		C = l, p.value = !0;
		let u = (async () => {
			try {
				let a = n.pool(l.signal).catch((e) => {
					if (R(e)) throw e;
					return null;
				}), [s, u, f] = await Promise.all([
					Promise.all(r.map(async (e) => ({
						name: e,
						...await P(e, i[e], l.signal)
					}))),
					e ? Promise.resolve(null) : n.summary(l.signal),
					a
				]);
				if (o !== b || !A()) return;
				s.forEach((e) => {
					F(e.name, e), k.delete(e.name) && g[e.name]++;
				}), u && (c.value = u), d.value = f, m.value = "", t.onReady?.();
			} catch (e) {
				if (o !== b || !A() || R(e)) return;
				Q.forEach((e) => {
					s[e].items = [], s[e].total = 0;
				}), c.value = null, d.value = null, m.value = e instanceof Error ? e.message : String(e);
			} finally {
				o === b && (p.value = !1, C = null, O = null, M());
			}
		})();
		return O = {
			key: a,
			promise: u
		}, u;
	}
	function L(e = {}) {
		let t = f.value?.opener;
		f.value = null, e.restoreFocus !== !1 && t?.isConnected && y(() => t.focus({ preventScroll: !0 }));
	}
	function z(e) {
		S || r.value === e || (r.value = e, e ? N() : (j(), h.value = null, L({ restoreFocus: !1 })));
	}
	function te(e) {
		!S && ["pool", "records"].includes(e) && i.value !== e && (i.value = e, h.value = null, L({ restoreFocus: !1 }));
	}
	function B(e) {
		!S && Q.includes(e) && a.value !== e && (a.value = e, h.value = null, L({ restoreFocus: !1 }));
	}
	function V(e) {
		let t = Object.keys(e).filter((t) => e[t] !== void 0 && e[t] !== o[t]);
		t.length && !S && (t.forEach((t) => {
			o[t] = e[t];
		}), Q.forEach((e) => {
			s[e].page = 1, k.add(e);
		}), N(null, t.every((e) => e === "search") ? 260 : 0));
	}
	function H(e, t) {
		S || s[e].state === t || (s[e].state = t, s[e].page = 1, k.add(e), N(e));
	}
	function U(e, t) {
		if (S || !Number.isFinite(t)) return;
		let n = s[e], r = Math.min(Math.max(1, Math.ceil(n.total / n.size)), Math.max(1, Math.floor(t)));
		r !== n.page && (n.page = r, k.add(e), N(e));
	}
	function W(e, t) {
		!S && [
			20,
			50,
			100
		].includes(t) && s[e].size !== t && (s[e].size = t, s[e].page = 1, k.add(e), N(e));
	}
	function G() {
		Object.assign(o, {
			window: "all",
			purpose: "all",
			search: ""
		}), Q.forEach((e) => {
			s[e].state = "all", s[e].page = 1, k.add(e);
		}), N();
	}
	function K(e) {
		e.startsWith("state:") ? H(e.slice(6), "all") : e === "search" ? V({ search: "" }) : (e === "window" || e === "purpose") && V({ [e]: "all" });
	}
	function ne(e, t, n = null) {
		!S && A() && (f.value = {
			view: e,
			row: JSON.parse(JSON.stringify(t)),
			opener: n
		});
	}
	function q() {
		_.value = !document.hidden, document.hidden ? (j(), h.value = null, L({ restoreFocus: !1 })) : r.value && N();
	}
	document.addEventListener("visibilitychange", q);
	function J() {
		S || (S = !0, j(), L({ restoreFocus: !1 }), document.removeEventListener("visibilitychange", q));
	}
	return l(J), t.visible && z(!0), {
		visible: r,
		active: v,
		documentVisible: _,
		view: i,
		recordView: a,
		filters: o,
		pages: s,
		summary: c,
		pool: d,
		detail: f,
		loading: p,
		error: m,
		openFilter: h,
		scrollRevision: g,
		load: I,
		setVisible: z,
		setView: te,
		setRecordView: B,
		updateFilters: V,
		setState: H,
		setPage: U,
		setSize: W,
		resetFilters: G,
		removeFilter: K,
		openDetail: ne,
		closeDetail: L,
		dispose: J
	};
}
// src/features/proxy/ProxyTrafficPage.vue?vue&type=script&setup=true&lang.ts
var nt = {
	class: "pt-root",
	"data-proxy-vue": ""
}, rt = {
	class: "pt-workspace",
	"data-proxy-module-panel": "records"
}, it = {
	class: "pt-summary",
	"aria-label": "租约与流量摘要"
}, at = { "data-proxy-summary": "totalBytes" }, ot = { "data-proxy-summary": "todayBytes" }, st = { "data-proxy-summary": "todayRequestCount" }, ct = { "data-proxy-summary": "todayRouteCount" }, lt = { class: "pt-tabs-row" }, ut = [
	"data-proxy-view",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], dt = { class: "pt-toolbar" }, ft = { class: "pt-toolbar-main" }, pt = {
	class: "pt-count",
	role: "status"
}, mt = { class: "pt-toolbar-actions" }, ht = { class: "pt-mobile-filter" }, gt = [
	"id",
	"aria-label",
	"aria-hidden",
	"data-proxy-panel"
], _t = /* @__PURE__ */ o({
	__name: "ProxyTrafficPage",
	props: { deps: {} },
	setup(t, { expose: i }) {
		let o = t, s = tt(o.deps), { view: c, recordView: l, filters: u, pages: p, summary: _, pool: v, detail: y, loading: x, error: T, active: E, openFilter: O } = s, k = e({}), j = [
			"current",
			"history",
			"traffic"
		], M = {
			current: "当前租约",
			history: "线路历史",
			traffic: "请求流量"
		}, P = w(() => Te(u, {
			current: p.current.state,
			history: p.history.state,
			traffic: p.traffic.state
		})), F = w(() => p[l.value]);
		function I(e, t, n) {
			t === "state" ? s.setState(e, n) : s.updateFilters({ [t]: n });
		}
		function L() {
			k.value[l.value]?.resetColumns(), o.deps.notify?.("已恢复默认列宽");
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
			s.setRecordView(j[n]), e.currentTarget.querySelector(`[data-proxy-view="${j[n]}"]`)?.focus({ preventScroll: !0 });
		}
		return i({
			load: s.load,
			setVisible: s.setVisible,
			setView: s.setView,
			closeDetail: s.closeDetail
		}), (e, i) => (a(), d("div", nt, [
			n(A(xe, {
				pool: C(v),
				loading: C(x)
			}, null, 8, ["pool", "loading"]), [[S, C(c) === "pool"]]),
			n(b("div", rt, [
				b("div", it, [
					b("div", null, [i[6] ||= b("span", null, "累计可观测流量", -1), b("strong", at, h(C(_) ? C(W)(C(_).total_bytes) : "—"), 1)]),
					b("div", null, [i[7] ||= b("span", null, "今日可观测流量", -1), b("strong", ot, h(C(_) ? C(W)(C(_).today_bytes) : "—"), 1)]),
					b("div", null, [i[8] ||= b("span", null, "今日请求记录", -1), b("strong", st, h(C(_) ? C(_).today_request_count ?? C(_).today_browser_count ?? "—" : "—"), 1)]),
					b("div", null, [i[9] ||= b("span", null, "今日新建线路", -1), b("strong", ct, h(C(_)?.today_route_count ?? "—"), 1)])
				]),
				b("div", lt, [b("div", {
					class: "pt-view-tabs",
					role: "tablist",
					"aria-label": "代理与流量视图",
					onKeydown: R
				}, [(a(), d(D, null, r(j, (e) => b("button", {
					key: e,
					type: "button",
					role: "tab",
					"data-proxy-view": e,
					"aria-selected": C(l) === e,
					"aria-controls": `proxy-panel-${e}`,
					tabindex: C(l) === e ? 0 : -1,
					class: m({ "is-active": C(l) === e }),
					onClick: (t) => C(s).setRecordView(e)
				}, [f(h(M[e]) + " ", 1), b("span", null, h(C(T) ? "—" : C(p)[e].total), 1)], 10, ut)), 64))], 32)]),
				b("div", dt, [b("div", ft, [b("span", pt, h(C(T) ? "数据暂不可用" : `${F.value.total.toLocaleString()} 条记录`), 1), A(N, {
					items: P.value,
					onRemove: C(s).removeFilter
				}, null, 8, ["items", "onRemove"])]), b("div", mt, [
					b("span", ht, [A(Pe, {
						view: C(l),
						filters: C(u),
						state: F.value.state,
						summary: C(_),
						open: C(E) && C(O) === "all",
						onChange: i[0] ||= (e, t) => I(C(l), e, t),
						"onUpdate:open": i[1] ||= (e) => O.value = e ? "all" : null
					}, null, 8, [
						"view",
						"filters",
						"state",
						"summary",
						"open"
					])]),
					P.value.length ? (a(), d("button", {
						key: 0,
						type: "button",
						class: "pt-link",
						onClick: i[2] ||= (...e) => C(s).resetFilters && C(s).resetFilters(...e)
					}, "清筛")) : g("", !0),
					b("button", {
						type: "button",
						class: "pt-link",
						"aria-label": "恢复当前列表列宽",
						onClick: L
					}, "恢复列宽")
				])]),
				(a(), d(D, null, r(j, (e) => n(b("section", {
					id: `proxy-panel-${e}`,
					key: e,
					role: "tabpanel",
					"aria-label": M[e],
					"aria-hidden": C(l) !== e,
					"data-proxy-panel": e,
					class: "pt-panel"
				}, [A(qe, {
					ref_for: !0,
					ref: (t) => {
						t && (k.value[e] = t);
					},
					view: e,
					items: C(p)[e].items,
					filters: C(u),
					state: C(p)[e].state,
					summary: C(_),
					loading: C(x),
					error: C(T),
					visible: C(E) && C(c) === "records" && C(l) === e,
					"open-filter": C(O),
					"scroll-revision": C(s).scrollRevision[e],
					"facet-label": t.deps.facetLabel,
					onFilter: (t, n) => I(e, t, n),
					"onUpdate:openFilter": i[3] ||= (e) => O.value = e,
					onDetail: C(s).openDetail,
					onRetry: i[4] ||= (e) => C(s).load()
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
				]), A(ee, {
					page: C(p)[e].page,
					size: C(p)[e].size,
					total: C(p)[e].total,
					busy: C(x),
					"page-sizes": [
						20,
						50,
						100
					],
					label: `${M[e]}分页`,
					"onUpdate:page": (t) => C(s).setPage(e, t),
					"onUpdate:size": (t) => C(s).setSize(e, t)
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy",
					"label",
					"onUpdate:page",
					"onUpdate:size"
				])], 8, gt), [[S, C(l) === e]])), 64))
			], 512), [[S, C(c) === "records"]]),
			A(Ze, {
				snapshot: C(y),
				"facet-label": t.deps.facetLabel,
				onClose: i[5] ||= (e) => C(s).closeDetail()
			}, null, 8, ["snapshot", "facet-label"])
		]));
	}
});
// src/proxy.ts
function vt(e, t = {}) {
	let n = x(_t, { deps: t }), r = n.mount(e);
	return {
		load: r.load,
		setVisible: r.setVisible,
		setView: r.setView,
		closeDetail: r.closeDetail,
		destroy: () => n.unmount()
	};
}
export { vt as mountProxyTraffic };
