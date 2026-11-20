import { A as e, C as t, F as n, H as r, L as i, M as a, Q as o, _ as s, b as c, c as l, d as u, dt as d, et as f, ft as p, h as m, j as h, l as g, lt as _, m as v, n as y, st as b, t as x, v as S } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { t as C } from "./useNativeDialog-BgHdu813.js";
import { r as w, t as T } from "./client-B5R_MNgP.js";
// src/features/dashboard/useDashboard.ts
var E = "gpt_console_overview_preferences_v1", D = ["metrics", "panels"], O = (e) => Number(e || 0);
function k(e) {
	let t = e?.statistics_updated_at, n = t ? `；统计于 ${new Date(t).toLocaleTimeString()} 更新` : "";
	return `仅统计本地库存；用完后请手动导入邮箱。邮箱由 Email Butler 等邮箱服务准备${e?.reason ? `；${e.reason}` : ""}${n}`;
}
function A(e) {
	return e?.status === "error" ? "读取失败" : Number.isInteger(e?.available) && e.available >= 0 ? e.available : Array.isArray(e?.sources) ? e.sources.reduce((e, t) => e + O(t?.available), 0) : 0;
}
function j(e, ...t) {
	let n = e;
	for (let e of t) {
		if (!n || typeof n != "object") return null;
		n = n[e];
	}
	return typeof n?.enabled == "boolean" ? n.enabled : null;
}
function M(e, t) {
	let n = e?.email?.supply?.sources;
	return Array.isArray(n) ? n.filter((e) => e?.kind === "local_pool") : (Array.isArray(e?.email?.sources) ? e.email.sources : []).filter((e) => e?.enabled === !0 && (j(t, "email_sources", e.source) ?? !0));
}
function N(e, t) {
	return M(e, t).filter((e) => e?.kind === "local_pool");
}
function P(e, t) {
	let n = String(e?.proxy?.platform || "none").trim().toLowerCase();
	return !n || n === "none" || n === "direct" ? !1 : j(t, "proxy", "registration") ?? !0;
}
function F(e, t) {
	let n = e?.jobs?.counts || {}, r = O(n.running) + O(n.pending) + O(n.stopping);
	return O(e?.jobs?.total) <= 0 && r <= 0 ? !1 : j(t, "features", "register") ?? !0;
}
function I(e) {
	let t = String(e || "").trim();
	return {
		"1024proxy": "1024Proxy",
		"711proxy": "711Proxy",
		manual: "手动代理池",
		1024: "1024Proxy",
		pool: "静态代理池",
		none: "直连",
		direct: "直连"
	}[t.toLowerCase()] || t || "未配置";
}
function L(e, t) {
	let n = e && typeof e == "object" ? e : {}, r = new Set(D.flatMap((e) => t[e] || [])), i = Array.isArray(n.hidden) ? Array.from(new Set(n.hidden.filter((e) => typeof e == "string" && r.has(e)))) : [], a = {};
	for (let e of D) {
		let r = t[e] || [], i = Array.isArray(n.order?.[e]) ? n.order[e].filter((e) => typeof e == "string") : [];
		a[e] = Array.from(/* @__PURE__ */ new Set([...i.filter((e) => r.includes(e)), ...r.filter((e) => !i.includes(e))]));
	}
	let o = {}, s = {};
	for (let e of r) {
		o[e] = [
			"normal",
			"wide",
			"full"
		].includes(n.sizes?.[e]) ? n.sizes[e] : "normal";
		let t = Number(n.heights?.[e]);
		Number.isFinite(t) && t >= 100 && t <= 800 && (s[e] = Math.round(t));
	}
	return {
		order: a,
		hidden: i,
		sizes: o,
		heights: s
	};
}
function R(e) {
	try {
		return L(JSON.parse(localStorage.getItem("gpt_console_overview_preferences_v1") || "{}"), e);
	} catch {
		return L({}, e);
	}
}
function z(e) {
	try {
		localStorage.setItem(E, JSON.stringify(e));
	} catch {}
}
var B = [
	{
		id: "metric-accounts",
		region: "metrics",
		label: "有效账号",
		available: (e) => O(e?.accounts?.total) > 0
	},
	{
		id: "metric-email",
		region: "metrics",
		label: "本地可用邮箱",
		available: (e, t) => M(e, t).length > 0
	},
	{
		id: "metric-jobs",
		region: "metrics",
		label: "运行任务",
		available: (e, t) => F(e, t)
	},
	{
		id: "metric-codex",
		region: "metrics",
		label: "Codex 凭证",
		available: (e) => O(e?.codex?.total) > 0
	},
	{
		id: "metric-proxy",
		region: "metrics",
		label: "活跃出口",
		available: (e, t) => P(e, t)
	},
	{
		id: "panel-email",
		region: "panels",
		label: "邮箱资源 · 本地库存",
		available: (e, t) => M(e, t).length > 0
	},
	{
		id: "panel-proxy",
		region: "panels",
		label: "网络出口 · 代理与网络",
		available: (e, t) => P(e, t)
	},
	{
		id: "panel-jobs",
		region: "panels",
		label: "注册流水线 · 今日任务结果",
		available: (e, t) => F(e, t)
	},
	{
		id: "panel-accounts",
		region: "panels",
		label: "账号资产 · 套餐分布",
		available: (e) => Object.keys(e?.accounts?.plans || {}).length > 0
	},
	{
		id: "panel-task-queue",
		region: "panels",
		label: "注册流水线 · 当前任务队列",
		available: (e, t) => F(e, t) && [
			"pending",
			"running",
			"stopping"
		].some((t) => O(e?.jobs?.counts?.[t]) > 0)
	},
	{
		id: "panel-job-history",
		region: "panels",
		label: "注册流水线 · 累计任务结果",
		available: (e, t) => F(e, t) && [
			"success",
			"partial_success",
			"failed",
			"stopped",
			"cancelled"
		].some((t) => O(e?.jobs?.counts?.[t]) > 0)
	},
	{
		id: "panel-email-health",
		region: "panels",
		label: "邮箱资源 · 邮箱池状态",
		available: (e, t) => N(e, t).some((e) => O(e.total) > 0)
	},
	{
		id: "panel-codex-progress",
		region: "panels",
		label: "Codex 授权 · 凭证处理进度",
		available: (e) => O(e?.codex?.total) > 0
	}
];
function V(e, t) {
	return Object.fromEntries(D.map((n) => [n, B.filter((r) => r.region === n && r.available(e, t)).map((e) => e.id)]));
}
function H(e) {
	return e ? e < 220 ? "minimal" : e < 300 ? "compact" : "normal" : "normal";
}
function U(e, t) {
	return e > 0 ? `另有 ${e} ${t}` : "";
}
function W(e, t, n, r) {
	let i = t?.accounts || {}, a = t?.email || {}, o = t?.jobs || {}, s = t?.proxy || {}, c = t?.codex || {};
	if (e === "metric-accounts") return {
		value: O(i.active),
		hint: `归档 ${O(i.archived)}`,
		color: "#5b5ce2"
	};
	if (e === "metric-email") return {
		value: A(a.supply),
		hint: k(a.supply),
		color: "#2dbb8a"
	};
	if (e === "metric-jobs") {
		let e = o.counts || {};
		return {
			value: O(e.running) + O(e.pending) + O(e.stopping),
			hint: `累计任务 ${O(o.total)}`,
			color: "#e6a23c"
		};
	}
	if (e === "metric-codex") return {
		value: O(c.total),
		hint: `待导出 ${O(c.pending)}`,
		color: "#377dff"
	};
	if (e === "metric-proxy") return {
		value: O(s.active_leases),
		hint: `代理平台 ${I(s.platform)}`,
		color: "#a855f7"
	};
	if (e === "panel-email") return {
		kind: "email",
		action: ["outlook", "管理邮箱"],
		sources: M(t, n)
	};
	if (e === "panel-proxy") {
		let e = (s.leases || []).slice(0, 3), t = Math.max(O(s.active_leases), (s.leases || []).length);
		return {
			kind: "proxy",
			action: ["config", "配置"],
			platform: I(s.platform),
			active: O(s.active_leases),
			leases: e,
			more: U(t - 1, "个出口")
		};
	}
	if (e === "panel-jobs") {
		let e = o.today_counts || {};
		return {
			kind: "today",
			action: ["register", "查看全部"],
			today: o.today || "今天",
			rows: [
				[
					"success",
					"成功",
					O(e.success)
				],
				[
					"partial_success",
					"部分成功",
					O(e.partial_success)
				],
				[
					"failed",
					"失败",
					O(e.failed)
				]
			]
		};
	}
	if (e === "panel-accounts") return {
		kind: "plans",
		action: ["accounts", "管理账号"],
		plans: Object.entries(i.plans || {}).sort((e, t) => O(t[1]) - O(e[1]))
	};
	if (e === "panel-task-queue") {
		let e = o.counts || {};
		return {
			kind: "queue",
			action: ["register", "查看任务"],
			rows: [
				["待处理", O(e.pending)],
				["运行中", O(e.running)],
				["停止中", O(e.stopping)]
			]
		};
	}
	if (e === "panel-job-history") {
		let e = o.counts || {};
		return {
			kind: "history",
			action: ["register", "查看任务"],
			rows: [
				["成功", O(e.success)],
				["失败", O(e.failed)],
				["部分成功", O(e.partial_success)],
				["已停止或取消", O(e.stopped) + O(e.cancelled)]
			]
		};
	}
	if (e === "panel-email-health") {
		let e = N(t, n), r = (t) => e.reduce((e, n) => e + O(n[t]), 0);
		return {
			kind: "health",
			action: ["outlook", "查看邮箱"],
			rows: [
				["可用邮箱", r("available")],
				["已用邮箱", r("used")],
				["失败邮箱", r("failed")],
				["停用邮箱", r("disabled")]
			]
		};
	}
	return {
		kind: "codex",
		action: ["codex", "查看凭证"],
		rows: [
			["已导出", O(c.exported)],
			["待导出", O(c.pending)],
			["账号 Codex 就绪", O(i.codex_ready)]
		]
	};
}
function ee(e, t = {}) {
	let n = f(null), i = f({}), s = f(!1), c = f(""), l = f(!!t.visible), u = f(!1), d = f(0), p, m, g, _ = !1, y = o({
		order: {
			metrics: [],
			panels: []
		},
		hidden: [],
		sizes: {},
		heights: {}
	});
	function b() {
		if (!n.value) return;
		let e = R(V(n.value, i.value));
		y.order = e.order, y.hidden = e.hidden, y.sizes = e.sizes, y.heights = e.heights;
	}
	let x = v(() => n.value ? V(n.value, i.value) : {
		metrics: [],
		panels: []
	}), S = v(() => D.flatMap((e) => (y.order[e] || []).filter((e) => !y.hidden.includes(e)).map((e) => B.find((t) => t.id === e)).filter((e) => e && e.available(n.value, i.value)).map((e) => ({
		card: e,
		payload: W(e.id, n.value, i.value, y),
		size: y.sizes[e.id] || "normal",
		height: y.heights[e.id],
		density: H(y.heights[e.id])
	}))));
	function C() {
		z(L(y, x.value));
	}
	function w(e) {
		e(y);
		let t = L(y, x.value);
		y.order = t.order, y.hidden = t.hidden, y.sizes = t.sizes, y.heights = t.heights, C();
	}
	function T(e, t, n) {
		w((r) => {
			let i = r.order[e] || [], a = i.indexOf(t), o = n === "up" ? a - 1 : a + 1;
			a < 0 || o < 0 || o >= i.length || ([i[a], i[o]] = [i[o], i[a]]);
		});
	}
	function O(e, t) {
		w((n) => {
			n.hidden = n.hidden.filter((t) => t !== e), t || n.hidden.push(e);
		});
	}
	function k(e, t, n, r = !1) {
		x.value[e].includes(t) && x.value[e].includes(n) && w((i) => {
			let a = i.order[e] || [], o = a.indexOf(t);
			if (o < 0 || t === n) return;
			a.splice(o, 1);
			let s = a.indexOf(n);
			a.splice(s + +!!r, 0, t);
		});
	}
	function A(e, t, n) {
		w((r) => {
			if (t === "width") {
				let t = [
					"normal",
					"wide",
					"full"
				], i = Math.max(0, Math.min(2, t.indexOf(r.sizes[e] || "normal") + n));
				r.sizes[e] = t[i];
			} else r.heights[e] = Math.max(160, Math.min(800, (r.heights[e] || 220) + n));
		});
	}
	function j() {
		try {
			localStorage.removeItem(E);
		} catch {}
		n.value && b(), t.notify?.("已恢复默认布局");
	}
	function M() {
		if (_ || !l.value || document.hidden) return Promise.resolve();
		if (g) return g;
		let r = ++d.value;
		m?.abort(), m = new AbortController(), s.value = !0, c.value = "";
		let a = (async () => {
			try {
				let [a, o] = await Promise.all([e.dashboard(m.signal), e.capabilities(m.signal).catch(() => null)]);
				if (r !== d.value || !l.value || document.hidden) return;
				n.value = a, o !== null && (i.value = o || {}, t.onCapabilities?.(i.value)), b(), t.onReady?.();
			} catch (e) {
				r === d.value && !String(e?.name || "").includes("Abort") && (c.value = e?.message || "总览加载失败", t.notify?.(`总览加载失败：${c.value}`));
			} finally {
				r === d.value && (s.value = !1, g = void 0);
			}
		})();
		return g = a, a;
	}
	function N() {
		p && window.clearInterval(p), p = window.setInterval(() => void M(), 15e3);
	}
	function P(e) {
		_ || l.value === !!e || (l.value = !!e, d.value++, m?.abort(), g = void 0, l.value ? (N(), M()) : (p && window.clearInterval(p), p = void 0, s.value = !1, u.value = !1));
	}
	function F(e) {
		u.value = e;
	}
	let I = () => {
		!document.hidden && l.value ? M() : (d.value++, m?.abort(), g = void 0, s.value = !1, u.value = !1);
	};
	return a(() => {
		document.addEventListener("visibilitychange", I), l.value && (N(), M());
	}), h(() => {
		_ = !0, l.value = !1, d.value++, g = void 0, s.value = !1, u.value = !1, document.removeEventListener("visibilitychange", I), m?.abort(), p && window.clearInterval(p), p = void 0;
	}), r(() => t.visible, (e) => P(!!e)), {
		data: n,
		caps: i,
		loading: s,
		error: c,
		visible: l,
		customizerOpen: u,
		cards: S,
		ids: x,
		prefs: y,
		mutate: w,
		load: M,
		setVisible: P,
		openCustomizer: () => F(!0),
		closeCustomizer: () => F(!1),
		resetLayout: j,
		toggle: O,
		move: T,
		reorder: k,
		resize: A,
		cardPayload: W
	};
}
// src/features/dashboard/DashboardPage.vue?vue&type=script&setup=true&lang.ts
var te = {
	class: "dashboard-vue-root",
	"data-dashboard-vue": ""
}, ne = {
	class: "overview-hero",
	"aria-label": "平台状态总览"
}, re = { class: "overview-hero-actions" }, ie = ["aria-expanded"], ae = ["disabled"], oe = {
	key: 0,
	class: "list-result list-result--danger",
	role: "alert"
}, se = ["aria-hidden"], ce = { class: "overview-customizer-list" }, le = { class: "overview-customizer-group-head" }, ue = { class: "overview-customizer-items" }, de = [
	"data-dashboard-custom-card",
	"onDragstart",
	"onDrop"
], fe = ["checked", "onChange"], pe = ["aria-label"], me = ["onClick"], he = ["onClick"], ge = { class: "overview-customizer-foot" }, _e = { class: "overview-metrics" }, ve = [
	"data-dashboard-card",
	"data-overview-card",
	"data-overview-size",
	"onDrop"
], ye = { class: "overview-metric-top" }, be = { class: "overview-card-tools" }, xe = [
	"aria-label",
	"onKeydown",
	"onPointerdown"
], Se = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], Ce = { class: "overview-grid" }, we = [
	"data-dashboard-card",
	"data-overview-card",
	"data-overview-size",
	"data-overview-density",
	"onDrop"
], Te = { class: "overview-panel-head" }, Ee = { class: "overview-card-tools" }, De = ["onClick"], Oe = [
	"aria-label",
	"onKeydown",
	"onPointerdown"
], ke = {
	key: 0,
	class: "overview-source-grid"
}, Ae = { class: "overview-source-top" }, je = ["title"], Me = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact overview-more-summary--paired"
}, Ne = {
	key: 1,
	class: "overview-more-summary overview-more-summary--minimal"
}, Pe = { key: 1 }, Fe = { class: "overview-proxy-grid" }, Ie = { class: "overview-proxy-item" }, Le = { class: "overview-proxy-item" }, Re = { class: "overview-exit-list" }, ze = {
	key: 0,
	class: "muted"
}, Be = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact"
}, Ve = {
	key: 2,
	class: "overview-plan-list"
}, He = { class: "overview-plan-bar" }, Ue = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact overview-more-summary--paired"
}, We = {
	key: 1,
	class: "overview-more-summary overview-more-summary--minimal"
}, Ge = {
	key: 3,
	class: "overview-job-list"
}, Ke = { class: "overview-job-main" }, qe = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact"
}, Je = {
	key: 4,
	class: "overview-status-grid"
}, Ye = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact"
}, G = {
	key: 1,
	class: "overview-more-summary overview-more-summary--compact"
}, Xe = {
	key: 2,
	class: "overview-more-summary overview-more-summary--compact"
}, Ze = {
	key: 3,
	class: "overview-more-summary overview-more-summary--compact"
}, Qe = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], K = /*#__PURE__*/ x(/* @__PURE__ */ t({
	__name: "DashboardPage",
	props: {
		api: {},
		deps: {}
	},
	setup(t, { expose: o }) {
		let v = t, y = ee(v.api, v.deps), { cards: x, ids: w, prefs: T, customizerOpen: E, loading: D, error: O } = y, k = f(), A = f();
		C(A, () => E.value, () => y.visible.value);
		let j = (e) => B.find((t) => t.id === e)?.label || e, M = f(null);
		function N(e, t) {
			let n = e?.[t];
			return Number.isInteger(n) && n >= 0 ? String(n) : e?.status === "error" ? "读取失败" : "未知";
		}
		function P(e) {
			return {
				free: "Free",
				free_trial_eligible: "Free · Plus 免费试用",
				free_half_price_eligible: "Free · Plus 半价",
				free_discount_eligible: "Free · Plus 其他折扣",
				free_promo_unknown: "Free · 优惠待复查",
				plus: "Plus",
				pro: "Pro",
				team: "Team",
				go: "Go",
				unknown: "未检测"
			}[e] || e;
		}
		function F(e) {
			return {
				success: "成功",
				partial_success: "部分成功",
				failed: "失败"
			}[e] || e;
		}
		let I = (e) => e?.sources || [], L = (e) => e?.leases || [], R = (e) => e?.plans || [], z = (e) => e?.rows || [];
		function V() {
			y.closeCustomizer();
		}
		function H(e) {
			let t = A.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && V();
		}
		function U(e) {
			e.key === "Escape" && (Z(), E.value && V());
		}
		a(() => document.addEventListener("keydown", U)), h(() => document.removeEventListener("keydown", U));
		function W(e) {
			e && (e[0] === "config" ? v.deps.onConfig?.("代理与网络") : v.deps.onNavigate?.(e[0]));
		}
		function K(e) {
			return y.ids.value.metrics.includes(e) ? "metrics" : "panels";
		}
		function q(e) {
			M.value = e;
		}
		function J(e) {
			M.value &&= (y.reorder(K(e), M.value, e), null);
		}
		function Y(t, n) {
			if (![
				"ArrowLeft",
				"ArrowUp",
				"ArrowRight",
				"ArrowDown"
			].includes(n.key)) return;
			n.preventDefault(), y.move(K(t), t, ["ArrowLeft", "ArrowUp"].includes(n.key) ? "up" : "down");
			let r = n.currentTarget;
			e(() => r.focus({ preventScroll: !0 }));
		}
		let X;
		function Z(e = !0) {
			X?.(e);
		}
		function Q(t, n) {
			if (n.button !== 0 || X) return;
			let r = n.currentTarget, i = r.closest("[data-dashboard-card]"), a = i?.parentElement;
			if (!i || !a) return;
			let o = K(t), s = [...y.prefs.order[o]], c = n.clientX, l = n.clientY, u = i.getBoundingClientRect(), d, f, p = c, m = l;
			r.setPointerCapture?.(n.pointerId);
			let h = () => {
				let n = document.elementFromPoint?.(p, m)?.closest("[data-dashboard-card]");
				if (!n || n === i || n.parentElement !== a) return;
				let r = n.getBoundingClientRect(), s = i.getBoundingClientRect(), c = getComputedStyle(a).gridTemplateColumns.trim().split(/\s+/).length === 1 || Math.abs(s.top - r.top) > 8 || n.dataset.overviewSize === "full" ? m >= r.top + r.height / 2 : p >= r.left + r.width / 2, l = new Map(Array.from(a.children).map((e) => [e, e.getBoundingClientRect()]));
				y.reorder(o, t, n.dataset.dashboardCard, c), e(() => {
					if (!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) for (let [e, t] of l) {
						if (e === i) continue;
						let n = e.getBoundingClientRect(), r = t.left - n.left, a = t.top - n.top;
						(r || a) && e.animate?.([{ transform: `translate(${r}px,${a}px)` }, { transform: "translate(0,0)" }], {
							duration: 180,
							easing: "cubic-bezier(.2,.75,.2,1)"
						});
					}
				});
			}, g = () => {
				if (f = void 0, !d) return;
				let e = m, t = e >= 0 && e < 64 ? -Math.ceil((64 - e) / 4) : e <= window.innerHeight && e > window.innerHeight - 64 ? Math.ceil((e - window.innerHeight + 64) / 4) : 0;
				if (!t) return;
				let n = document.scrollingElement?.scrollTop;
				window.scrollBy(0, t), document.scrollingElement?.scrollTop !== n && (h(), f = requestAnimationFrame(g));
			}, _ = (e) => {
				if (e.pointerId !== n.pointerId) return;
				p = e.clientX, m = e.clientY;
				let t = p - c, r = m - l;
				!d && Math.hypot(t, r) < 5 || (d || (d = i.cloneNode(!0), d.classList.add("overview-drag-ghost"), d.setAttribute("aria-hidden", "true"), Object.assign(d.style, {
					left: `${u.left}px`,
					top: `${u.top}px`,
					width: `${u.width}px`,
					height: `${u.height}px`
				}), document.body.append(d), i.classList.add("is-drag-placeholder")), d.style.transform = `translate3d(${t}px,${r}px,0)`, h(), f ||= requestAnimationFrame(g));
			}, v = (e) => {
				e.pointerId === n.pointerId && Z(e.type === "pointercancel");
			};
			X = (e = !1) => {
				X = void 0, window.removeEventListener("pointermove", _), window.removeEventListener("pointerup", v), window.removeEventListener("pointercancel", v), f && cancelAnimationFrame(f), r.hasPointerCapture?.(n.pointerId) && r.releasePointerCapture(n.pointerId), d?.remove(), i.classList.remove("is-drag-placeholder"), e && y.mutate((e) => {
					e.order[o] = s;
				});
			}, window.addEventListener("pointermove", _), window.addEventListener("pointerup", v), window.addEventListener("pointercancel", v), n.preventDefault();
		}
		function $(e, t) {
			if (t.button !== 0 || X) return;
			let n = t.currentTarget, r = n.closest("[data-dashboard-card]"), i = r?.parentElement;
			if (!r || !i) return;
			let a = getComputedStyle(i), o = Math.max(1, a.gridTemplateColumns.trim().split(/\s+/).length), s = parseFloat(a.columnGap) || 0, c = r.getBoundingClientRect(), l = (i.getBoundingClientRect().width - s * (o - 1)) / o, u = K(e), d = y.prefs.sizes[e] || "normal", f = r.style.minHeight, p = d, m = y.prefs.heights[e], h = !1;
			n.setPointerCapture?.(t.pointerId), r.classList.add("is-resizing");
			let g = (e) => {
				if (e.pointerId !== t.pointerId) return;
				let n = e.clientX - t.clientX, i = e.clientY - t.clientY;
				if (Math.abs(n) > 4 && l > 0) {
					let e = Math.max(1, Math.min(o, Math.round((c.width + n + s) / (l + s))));
					p = e <= 1 ? "normal" : e >= Math.min(o, u === "metrics" ? 4 : 3) && o >= 3 ? "full" : "wide", r.dataset.overviewSize = p, h = !0;
				}
				Math.abs(i) > 4 && (m = Math.max(160, Math.min(800, Math.round(c.height + i))), r.style.minHeight = `${m}px`, u === "panels" && (r.dataset.overviewDensity = m < 220 ? "minimal" : m < 300 ? "compact" : "normal"), h = !0);
			}, _ = (e) => {
				e.pointerId === t.pointerId && Z(e.type === "pointercancel");
			};
			X = (i = !1) => {
				if (X = void 0, window.removeEventListener("pointermove", g), window.removeEventListener("pointerup", _), window.removeEventListener("pointercancel", _), r.classList.remove("is-resizing"), n.hasPointerCapture?.(t.pointerId) && n.releasePointerCapture(t.pointerId), !i && h) y.mutate((t) => {
					t.sizes[e] = p, m !== void 0 && (t.heights[e] = m);
				});
				else {
					r.dataset.overviewSize = d, r.style.minHeight = f;
					let t = y.prefs.heights[e];
					u === "panels" && (r.dataset.overviewDensity = t ? t < 220 ? "minimal" : t < 300 ? "compact" : "normal" : "normal");
				}
			}, window.addEventListener("pointermove", g), window.addEventListener("pointerup", _), window.addEventListener("pointercancel", _), t.preventDefault();
		}
		return r(y.visible, (e) => {
			e || Z();
		}), r(y.data, () => Z()), h(() => Z()), o({
			load: y.load,
			setVisible: y.setVisible,
			openCustomizer: y.openCustomizer,
			closeCustomizer: y.closeCustomizer,
			resetLayout: y.resetLayout
		}), (e, t) => (n(), S("div", te, [
			m("section", ne, [t[9] ||= m("div", null, [
				m("div", { class: "data-panel-kicker" }, "Operations overview"),
				m("h2", null, "整个平台，一屏看清"),
				m("p", null, "拖动卡片标题旁的把手调整位置，拖动右下角调整大小；显示内容可按需设置。")
			], -1), m("div", re, [m("button", {
				ref_key: "customizeButton",
				ref: k,
				type: "button",
				class: "overview-customize-trigger",
				"data-dashboard-open-customizer": "",
				"aria-expanded": b(E),
				onClick: t[0] ||= (...e) => b(y).openCustomizer && b(y).openCustomizer(...e)
			}, "自定义总览", 8, ie), m("button", {
				type: "button",
				class: "overview-refresh",
				disabled: b(D),
				onClick: t[1] ||= (...e) => b(y).load && b(y).load(...e)
			}, "刷新数据", 8, ae)])]),
			b(O) ? (n(), S("div", oe, [
				t[10] ||= m("strong", null, "总览加载失败", -1),
				m("span", null, p(b(O)), 1),
				m("button", {
					type: "button",
					onClick: t[2] ||= (...e) => b(y).load && b(y).load(...e)
				}, "重试")
			])) : s("", !0),
			m("dialog", {
				ref_key: "customizer",
				ref: A,
				class: "overview-customizer",
				role: "dialog",
				"aria-modal": "true",
				"aria-labelledby": "dashboard-customizer-title",
				"aria-hidden": !b(E),
				onCancel: g(V, ["prevent"]),
				onClick: H
			}, [
				m("div", { class: "overview-customizer-head" }, [t[11] ||= m("div", null, [
					m("div", { class: "data-panel-kicker" }, "Customize overview"),
					m("h3", { id: "dashboard-customizer-title" }, "显示与排序"),
					m("p", null, "拖动卡片排序，也可以用上移/下移调整。未启用或未配置的功能不会出现在这里。")
				], -1), m("button", {
					type: "button",
					class: "overview-customizer-close",
					"data-dashboard-close-customizer": "",
					onClick: V
				}, "关闭")]),
				m("div", ce, [(n(), S(u, null, i(["metrics", "panels"], (e) => m("section", {
					key: e,
					class: "overview-customizer-group"
				}, [m("div", le, [m("strong", null, p(e === "metrics" ? "指标卡片" : "详细卡片"), 1), m("small", null, p((b(w)[e] || []).length) + " 张可用卡片", 1)]), m("div", ue, [(n(!0), S(u, null, i(b(T).order[e] || [], (r) => (n(), S("div", {
					key: r,
					class: "overview-customizer-item",
					draggable: "true",
					"data-dashboard-custom-card": r,
					onDragstart: (e) => q(r),
					onDragover: t[3] ||= g(() => {}, ["prevent"]),
					onDrop: (e) => J(r)
				}, [
					t[12] ||= m("span", {
						class: "overview-drag-handle",
						"aria-hidden": "true"
					}, "拖动", -1),
					m("label", null, [m("input", {
						type: "checkbox",
						checked: !b(T).hidden.includes(r),
						onChange: (e) => b(y).toggle(r, e.target.checked)
					}, null, 40, fe), m("span", null, p(j(r)), 1)]),
					m("div", {
						class: "overview-customizer-move",
						role: "group",
						"aria-label": `调整 ${r} 顺序`
					}, [m("button", {
						type: "button",
						onClick: (t) => b(y).move(e, r, "up")
					}, "上移", 8, me), m("button", {
						type: "button",
						onClick: (t) => b(y).move(e, r, "down")
					}, "下移", 8, he)], 8, pe)
				], 40, de))), 128))])])), 64))]),
				m("div", ge, [m("button", {
					type: "button",
					class: "overview-reset-layout",
					"data-dashboard-reset-layout": "",
					onClick: t[4] ||= (...e) => b(y).resetLayout && b(y).resetLayout(...e)
				}, "恢复默认布局")])
			], 40, se),
			m("div", _e, [(n(!0), S(u, null, i(b(x).filter((e) => e.card.region === "metrics"), (e) => (n(), S("article", {
				key: e.card.id,
				class: "overview-metric",
				"data-dashboard-card": e.card.id,
				"data-overview-card": e.card.id,
				"data-overview-size": e.size,
				style: d({
					"--metric-color": e.payload.color,
					minHeight: e.height ? `${e.height}px` : void 0
				}),
				onDragstart: t[5] ||= g(() => {}, ["prevent"]),
				onDragover: t[6] ||= g(() => {}, ["prevent"]),
				onDrop: (t) => J(e.card.id)
			}, [
				m("div", ye, [m("span", null, p(e.card.label), 1), m("div", be, [t[14] ||= m("i", {
					class: "overview-metric-dot",
					"aria-hidden": "true"
				}, null, -1), m("span", {
					class: "overview-card-drag",
					role: "button",
					tabindex: "0",
					"aria-label": `拖动${e.card.label}卡片排序，或使用方向键调整顺序`,
					onKeydown: (t) => Y(e.card.id, t),
					onPointerdown: (t) => Q(e.card.id, t)
				}, [...t[13] ||= [c("<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" data-v-56b51968><circle cx=\"5\" cy=\"3\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"3\" r=\"1\" data-v-56b51968></circle><circle cx=\"5\" cy=\"8\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"8\" r=\"1\" data-v-56b51968></circle><circle cx=\"5\" cy=\"13\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"13\" r=\"1\" data-v-56b51968></circle></svg>", 1)]], 40, xe)])]),
				m("strong", null, p(e.payload.value), 1),
				m("small", null, p(e.payload.hint), 1),
				m("button", {
					type: "button",
					class: "overview-resize-handle",
					"data-overview-resize": "",
					"aria-label": `拖动调整${e.card.label}卡片宽高；方向键可调整`,
					onPointerdown: (t) => $(e.card.id, t),
					onKeydown: [
						l(g((t) => b(y).resize(e.card.id, "width", -1), ["prevent"]), ["left"]),
						l(g((t) => b(y).resize(e.card.id, "width", 1), ["prevent"]), ["right"]),
						l(g((t) => b(y).resize(e.card.id, "height", -40), ["prevent"]), ["up"]),
						l(g((t) => b(y).resize(e.card.id, "height", 40), ["prevent"]), ["down"])
					]
				}, [...t[15] ||= [m("svg", {
					viewBox: "0 0 16 16",
					"aria-hidden": "true"
				}, [m("path", { d: "M6 14l8-8M10 14l4-4" })], -1)]], 40, Se)
			], 44, ve))), 128))]),
			m("div", Ce, [(n(!0), S(u, null, i(b(x).filter((e) => e.card.region === "panels"), (e) => (n(), S("section", {
				key: e.card.id,
				class: "overview-panel",
				"data-dashboard-card": e.card.id,
				"data-overview-card": e.card.id,
				"data-overview-size": e.size,
				"data-overview-density": e.density,
				style: d(e.height ? { minHeight: `${e.height}px` } : void 0),
				onDragstart: t[7] ||= g(() => {}, ["prevent"]),
				onDragover: t[8] ||= g(() => {}, ["prevent"]),
				onDrop: (t) => J(e.card.id)
			}, [
				m("div", Te, [m("div", null, [m("span", null, p(e.card.label.split(" · ")[0]), 1), m("h3", null, p(e.card.label.split(" · ").slice(1).join(" · ")), 1)]), m("div", Ee, [e.payload.action ? (n(), S("button", {
					key: 0,
					type: "button",
					onClick: (t) => W(e.payload.action)
				}, p(e.payload.action[1]), 9, De)) : s("", !0), m("span", {
					class: "overview-card-drag",
					role: "button",
					tabindex: "0",
					"aria-label": `拖动${e.card.label}卡片排序，或使用方向键调整顺序`,
					onKeydown: (t) => Y(e.card.id, t),
					onPointerdown: (t) => Q(e.card.id, t)
				}, [...t[16] ||= [c("<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" data-v-56b51968><circle cx=\"5\" cy=\"3\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"3\" r=\"1\" data-v-56b51968></circle><circle cx=\"5\" cy=\"8\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"8\" r=\"1\" data-v-56b51968></circle><circle cx=\"5\" cy=\"13\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"13\" r=\"1\" data-v-56b51968></circle></svg>", 1)]], 40, Oe)])]),
				e.payload.kind === "email" ? (n(), S("div", ke, [
					(n(!0), S(u, null, i(I(e.payload), (e, r) => (n(), S("article", {
						key: e.source,
						class: _(["overview-source", {
							"overview-density-secondary": Number(r) >= 2,
							"overview-density-minimal-extra": Number(r) >= 1
						}])
					}, [
						m("div", Ae, [m("span", {
							class: "overview-source-name",
							title: e.label
						}, p(e.label), 9, je), t[17] ||= m("i", {
							class: "overview-source-state is-on",
							"aria-hidden": "true"
						}, null, -1)]),
						m("strong", null, p(N(e, "available")), 1),
						m("small", null, "本地总数 " + p(N(e, "total")) + " · 已用 " + p(N(e, "used")) + " · 失败 " + p(N(e, "failed")), 1)
					], 2))), 128)),
					I(e.payload).length > 2 ? (n(), S("div", Me, "另有 " + p(I(e.payload).length - 2) + " 个来源，进入详情查看", 1)) : s("", !0),
					I(e.payload).length > 1 ? (n(), S("div", Ne, "另有 " + p(I(e.payload).length - 1) + " 个来源，进入详情查看", 1)) : s("", !0)
				])) : e.payload.kind === "proxy" ? (n(), S("div", Pe, [
					m("div", Fe, [m("div", Ie, [t[18] ||= m("span", null, "系统代理平台", -1), m("strong", null, p(e.payload.platform), 1)]), m("div", Le, [t[19] ||= m("span", null, "活跃出口", -1), m("strong", null, p(e.payload.active) + " 个", 1)])]),
					m("div", Re, [(n(!0), S(u, null, i(L(e.payload), (e, r) => (n(), S("div", {
						key: r,
						class: _(["overview-exit-row", { "overview-density-secondary": Number(r) >= 1 }])
					}, [
						t[20] ||= m("i", { "aria-hidden": "true" }, null, -1),
						m("span", null, p(e.endpoint || e.exit_ip || "活跃出口"), 1),
						m("small", null, p(e.region || e.provider || ""), 1)
					], 2))), 128)), L(e.payload).length ? s("", !0) : (n(), S("div", ze, "当前没有活跃代理出口"))]),
					e.payload.more ? (n(), S("div", Be, p(e.payload.more), 1)) : s("", !0)
				])) : e.payload.kind === "plans" ? (n(), S("div", Ve, [
					(n(!0), S(u, null, i(R(e.payload), ([t, r], i) => (n(), S("div", {
						key: t,
						class: _(["overview-plan-row", {
							"overview-density-secondary": Number(i) >= 3,
							"overview-density-minimal-extra": Number(i) >= 2
						}])
					}, [
						m("span", null, p(P(t)), 1),
						m("div", He, [m("i", { style: d({ width: `${Math.max(4, Math.round(Number(r) / Math.max(1, ...R(e.payload).map((e) => Number(e[1]))) * 100))}%` }) }, null, 4)]),
						m("strong", null, p(r), 1)
					], 2))), 128)),
					R(e.payload).length > 3 ? (n(), S("div", Ue, "另有 " + p(R(e.payload).length - 3) + " 种套餐，进入详情查看", 1)) : s("", !0),
					R(e.payload).length > 2 ? (n(), S("div", We, "另有 " + p(R(e.payload).length - 2) + " 种套餐，进入详情查看", 1)) : s("", !0)
				])) : e.payload.kind === "today" ? (n(), S("div", Ge, [(n(!0), S(u, null, i(z(e.payload), ([t, r, i], a) => (n(), S("div", {
					key: t,
					class: _(["overview-job-row", { "overview-density-secondary": t === "partial_success" || Number(a) > 0 && !i }])
				}, [m("span", { class: _(["pill", `status-${t}`]) }, p(F(t)), 3), m("div", Ke, [m("strong", null, p(i) + " 个任务", 1), m("small", null, p(e.payload.today) + " · " + p(r), 1)])], 2))), 128)), z(e.payload)[1]?.[2] ? (n(), S("div", qe, "部分成功 " + p(z(e.payload)[1]?.[2]), 1)) : s("", !0)])) : e.payload.kind === "queue" || e.payload.kind === "history" || e.payload.kind === "health" || e.payload.kind === "codex" ? (n(), S("div", Je, [
					(n(!0), S(u, null, i(z(e.payload), ([t, r], i) => (n(), S("div", {
						key: t,
						class: _(["overview-status-item", { "overview-density-secondary": e.payload.kind === "health" ? [1, 3].includes(Number(i)) : Number(i) > 1 }])
					}, [m("span", null, p(t), 1), m("strong", null, p(r), 1)], 2))), 128)),
					e.payload.kind === "queue" && z(e.payload)[2]?.[1] ? (n(), S("div", Ye, "停止中 " + p(z(e.payload)[2]?.[1]), 1)) : s("", !0),
					e.payload.kind === "history" && (z(e.payload)[2]?.[1] || z(e.payload)[3]?.[1]) ? (n(), S("div", G, "部分成功 " + p(z(e.payload)[2]?.[1] || 0) + " · 已停止或取消 " + p(z(e.payload)[3]?.[1] || 0), 1)) : s("", !0),
					e.payload.kind === "health" ? (n(), S("div", Xe, "已用 " + p(z(e.payload)[1]?.[1] || 0) + " · 停用 " + p(z(e.payload)[3]?.[1] || 0), 1)) : s("", !0),
					e.payload.kind === "codex" ? (n(), S("div", Ze, "账号 Codex 就绪 " + p(z(e.payload)[2]?.[1] || 0), 1)) : s("", !0)
				])) : s("", !0),
				m("button", {
					type: "button",
					class: "overview-resize-handle",
					"data-overview-resize": "",
					"aria-label": `拖动调整${e.card.label}卡片宽高；方向键可调整`,
					onPointerdown: (t) => $(e.card.id, t),
					onKeydown: [
						l(g((t) => b(y).resize(e.card.id, "width", -1), ["prevent"]), ["left"]),
						l(g((t) => b(y).resize(e.card.id, "width", 1), ["prevent"]), ["right"]),
						l(g((t) => b(y).resize(e.card.id, "height", -40), ["prevent"]), ["up"]),
						l(g((t) => b(y).resize(e.card.id, "height", 40), ["prevent"]), ["down"])
					]
				}, [...t[21] ||= [m("svg", {
					viewBox: "0 0 16 16",
					"aria-hidden": "true"
				}, [m("path", { d: "M6 14l8-8M10 14l4-4" })], -1)]], 40, Qe)
			], 44, we))), 128))])
		]));
	}
}), [["__scopeId", "data-v-56b51968"]]);
// src/api/dashboard.ts
async function q(e, t) {
	if (!t) return e;
	t.throwIfAborted();
	let n, r = new Promise((e, r) => {
		n = () => r(t.reason), t.addEventListener("abort", n, { once: !0 });
	});
	try {
		return await Promise.race([e, r]);
	} finally {
		t.removeEventListener("abort", n);
	}
}
function J(e = (e, t) => w(e, t), t) {
	let n = (t, n) => e(t, n ? { signal: n } : void 0);
	return {
		dashboard: (e) => n("/api/dashboard", e),
		async capabilities(e) {
			let r = t?.();
			if (!r) return n("/api/capabilities", e);
			let i = await q(r, e);
			if (typeof i != "object" || !i || !("ok" in i) || i.ok !== !0) throw new T("能力检查返回无效数据", 200);
			return i;
		}
	};
}
// src/dashboard.ts
function Y(e, t = {}) {
	let n = y(K, {
		api: t.api || J(void 0, t.pendingCapabilities),
		deps: t
	}), r = n.mount(e);
	return {
		setVisible: r.setVisible,
		load: r.load,
		openCustomizer: r.openCustomizer,
		closeCustomizer: r.closeCustomizer,
		resetLayout: r.resetLayout,
		destroy: () => n.unmount()
	};
}
export { Y as mountDashboard };
