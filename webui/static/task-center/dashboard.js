import { $ as e, A as t, I as n, P as r, S as i, V as a, Z as o, _ as s, c, ct as l, dt as u, g as d, j as f, k as p, m, n as h, ot as g, p as _, s as v, t as y, u as b, ut as x, y as S } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { t as C } from "./useNativeDialog-Ba95V1OP.js";
import { r as w } from "./client-BBEPwkQG.js";
// src/features/dashboard/useDashboard.ts
var T = "gpt_console_overview_preferences_v1", E = ["metrics", "panels"], D = (e) => Number(e || 0);
function O(e) {
	let t = e?.statistics_updated_at, n = t ? `；统计于 ${new Date(t).toLocaleTimeString()} 更新` : "";
	return `仅统计本地库存；用完后请手动导入邮箱。邮箱由 Email Butler 等邮箱服务准备${e?.reason ? `；${e.reason}` : ""}${n}`;
}
function k(e) {
	return e?.status === "error" ? "读取失败" : Number.isInteger(e?.available) && e.available >= 0 ? e.available : Array.isArray(e?.sources) ? e.sources.reduce((e, t) => e + D(t?.available), 0) : 0;
}
function A(e, ...t) {
	let n = e;
	for (let e of t) {
		if (!n || typeof n != "object") return null;
		n = n[e];
	}
	return typeof n?.enabled == "boolean" ? n.enabled : null;
}
function j(e, t) {
	let n = e?.email?.supply?.sources;
	return Array.isArray(n) ? n.filter((e) => e?.kind === "local_pool") : (Array.isArray(e?.email?.sources) ? e.email.sources : []).filter((e) => e?.enabled === !0 && (A(t, "email_sources", e.source) ?? !0));
}
function M(e, t) {
	return j(e, t).filter((e) => e?.kind === "local_pool");
}
function N(e, t) {
	let n = String(e?.proxy?.platform || "none").trim().toLowerCase();
	return !n || n === "none" || n === "direct" ? !1 : A(t, "proxy", "registration") ?? !0;
}
function P(e, t) {
	let n = e?.jobs?.counts || {}, r = D(n.running) + D(n.pending) + D(n.stopping);
	return D(e?.jobs?.total) <= 0 && r <= 0 ? !1 : A(t, "features", "register") ?? !0;
}
function F(e) {
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
function I(e, t) {
	let n = e && typeof e == "object" ? e : {}, r = new Set(E.flatMap((e) => t[e] || [])), i = Array.isArray(n.hidden) ? Array.from(new Set(n.hidden.filter((e) => typeof e == "string" && r.has(e)))) : [], a = {};
	for (let e of E) {
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
function L(e) {
	try {
		return I(JSON.parse(localStorage.getItem("gpt_console_overview_preferences_v1") || "{}"), e);
	} catch {
		return I({}, e);
	}
}
function R(e) {
	try {
		localStorage.setItem(T, JSON.stringify(e));
	} catch {}
}
var z = [
	{
		id: "metric-accounts",
		region: "metrics",
		label: "有效账号",
		available: (e) => D(e?.accounts?.total) > 0
	},
	{
		id: "metric-email",
		region: "metrics",
		label: "本地可用邮箱",
		available: (e, t) => j(e, t).length > 0
	},
	{
		id: "metric-jobs",
		region: "metrics",
		label: "运行任务",
		available: (e, t) => P(e, t)
	},
	{
		id: "metric-codex",
		region: "metrics",
		label: "Codex 凭证",
		available: (e) => D(e?.codex?.total) > 0
	},
	{
		id: "metric-proxy",
		region: "metrics",
		label: "活跃出口",
		available: (e, t) => N(e, t)
	},
	{
		id: "panel-email",
		region: "panels",
		label: "邮箱资源 · 本地库存",
		available: (e, t) => j(e, t).length > 0
	},
	{
		id: "panel-proxy",
		region: "panels",
		label: "网络出口 · 代理与网络",
		available: (e, t) => N(e, t)
	},
	{
		id: "panel-jobs",
		region: "panels",
		label: "注册流水线 · 今日任务结果",
		available: (e, t) => P(e, t)
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
		available: (e, t) => P(e, t) && [
			"pending",
			"running",
			"stopping"
		].some((t) => D(e?.jobs?.counts?.[t]) > 0)
	},
	{
		id: "panel-job-history",
		region: "panels",
		label: "注册流水线 · 累计任务结果",
		available: (e, t) => P(e, t) && [
			"success",
			"partial_success",
			"failed",
			"stopped",
			"cancelled"
		].some((t) => D(e?.jobs?.counts?.[t]) > 0)
	},
	{
		id: "panel-email-health",
		region: "panels",
		label: "邮箱资源 · 邮箱池状态",
		available: (e, t) => M(e, t).some((e) => D(e.total) > 0)
	},
	{
		id: "panel-codex-progress",
		region: "panels",
		label: "Codex 授权 · 凭证处理进度",
		available: (e) => D(e?.codex?.total) > 0
	}
];
function B(e, t) {
	return Object.fromEntries(E.map((n) => [n, z.filter((r) => r.region === n && r.available(e, t)).map((e) => e.id)]));
}
function V(e) {
	return e ? e < 220 ? "minimal" : e < 300 ? "compact" : "normal" : "normal";
}
function H(e, t) {
	return e > 0 ? `另有 ${e} ${t}` : "";
}
function U(e, t, n, r) {
	let i = t?.accounts || {}, a = t?.email || {}, o = t?.jobs || {}, s = t?.proxy || {}, c = t?.codex || {};
	if (e === "metric-accounts") return {
		value: D(i.active),
		hint: `归档 ${D(i.archived)}`,
		color: "#5b5ce2"
	};
	if (e === "metric-email") return {
		value: k(a.supply),
		hint: O(a.supply),
		color: "#2dbb8a"
	};
	if (e === "metric-jobs") {
		let e = o.counts || {};
		return {
			value: D(e.running) + D(e.pending) + D(e.stopping),
			hint: `累计任务 ${D(o.total)}`,
			color: "#e6a23c"
		};
	}
	if (e === "metric-codex") return {
		value: D(c.total),
		hint: `待导出 ${D(c.pending)}`,
		color: "#377dff"
	};
	if (e === "metric-proxy") return {
		value: D(s.active_leases),
		hint: `代理平台 ${F(s.platform)}`,
		color: "#a855f7"
	};
	if (e === "panel-email") return {
		kind: "email",
		action: ["outlook", "管理邮箱"],
		sources: j(t, n)
	};
	if (e === "panel-proxy") {
		let e = (s.leases || []).slice(0, 3), t = Math.max(D(s.active_leases), (s.leases || []).length);
		return {
			kind: "proxy",
			action: ["config", "配置"],
			platform: F(s.platform),
			active: D(s.active_leases),
			leases: e,
			more: H(t - 1, "个出口")
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
					D(e.success)
				],
				[
					"partial_success",
					"部分成功",
					D(e.partial_success)
				],
				[
					"failed",
					"失败",
					D(e.failed)
				]
			]
		};
	}
	if (e === "panel-accounts") return {
		kind: "plans",
		action: ["accounts", "管理账号"],
		plans: Object.entries(i.plans || {}).sort((e, t) => D(t[1]) - D(e[1]))
	};
	if (e === "panel-task-queue") {
		let e = o.counts || {};
		return {
			kind: "queue",
			action: ["register", "查看任务"],
			rows: [
				["待处理", D(e.pending)],
				["运行中", D(e.running)],
				["停止中", D(e.stopping)]
			]
		};
	}
	if (e === "panel-job-history") {
		let e = o.counts || {};
		return {
			kind: "history",
			action: ["register", "查看任务"],
			rows: [
				["成功", D(e.success)],
				["失败", D(e.failed)],
				["部分成功", D(e.partial_success)],
				["已停止或取消", D(e.stopped) + D(e.cancelled)]
			]
		};
	}
	if (e === "panel-email-health") {
		let e = M(t, n), r = (t) => e.reduce((e, n) => e + D(n[t]), 0);
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
			["已导出", D(c.exported)],
			["待导出", D(c.pending)],
			["账号 Codex 就绪", D(i.codex_ready)]
		]
	};
}
function ee(n, r = {}) {
	let i = e(null), s = e({}), c = e(!1), l = e(""), u = e(!!r.visible), d = e(!1), p = e(0), m, h, g, v = !1, y = o({
		order: {
			metrics: [],
			panels: []
		},
		hidden: [],
		sizes: {},
		heights: {}
	});
	function b() {
		if (!i.value) return;
		let e = L(B(i.value, s.value));
		y.order = e.order, y.hidden = e.hidden, y.sizes = e.sizes, y.heights = e.heights;
	}
	let x = _(() => i.value ? B(i.value, s.value) : {
		metrics: [],
		panels: []
	}), S = _(() => E.flatMap((e) => (y.order[e] || []).filter((e) => !y.hidden.includes(e)).map((e) => z.find((t) => t.id === e)).filter((e) => e && e.available(i.value, s.value)).map((e) => ({
		card: e,
		payload: U(e.id, i.value, s.value, y),
		size: y.sizes[e.id] || "normal",
		height: y.heights[e.id],
		density: V(y.heights[e.id])
	}))));
	function C() {
		R(I(y, x.value));
	}
	function w(e) {
		e(y);
		let t = I(y, x.value);
		y.order = t.order, y.hidden = t.hidden, y.sizes = t.sizes, y.heights = t.heights, C();
	}
	function D(e, t, n) {
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
			localStorage.removeItem(T);
		} catch {}
		i.value && b(), r.notify?.("已恢复默认布局");
	}
	function M() {
		if (v || !u.value || document.hidden) return Promise.resolve();
		if (g) return g;
		let e = ++p.value;
		h?.abort(), h = new AbortController(), c.value = !0, l.value = "";
		let t = (async () => {
			try {
				let [t, a] = await Promise.all([n.dashboard(h.signal), n.capabilities(h.signal).catch(() => null)]);
				if (e !== p.value || !u.value || document.hidden) return;
				i.value = t, a !== null && (s.value = a || {}, r.onCapabilities?.(s.value)), b(), r.onReady?.();
			} catch (t) {
				e === p.value && !String(t?.name || "").includes("Abort") && (l.value = t?.message || "总览加载失败", r.notify?.(`总览加载失败：${l.value}`));
			} finally {
				e === p.value && (c.value = !1, g = void 0);
			}
		})();
		return g = t, t;
	}
	function N() {
		m && window.clearInterval(m), m = window.setInterval(() => void M(), 15e3);
	}
	function P(e) {
		v || u.value === !!e || (u.value = !!e, p.value++, h?.abort(), g = void 0, u.value ? (N(), M()) : (m && window.clearInterval(m), m = void 0, c.value = !1, d.value = !1));
	}
	function F(e) {
		d.value = e;
	}
	let H = () => {
		!document.hidden && u.value ? M() : (p.value++, h?.abort(), g = void 0, c.value = !1, d.value = !1);
	};
	return f(() => {
		document.addEventListener("visibilitychange", H), u.value && (N(), M());
	}), t(() => {
		v = !0, u.value = !1, p.value++, g = void 0, c.value = !1, d.value = !1, document.removeEventListener("visibilitychange", H), h?.abort(), m && window.clearInterval(m), m = void 0;
	}), a(() => r.visible, (e) => P(!!e)), {
		data: i,
		caps: s,
		loading: c,
		error: l,
		visible: u,
		customizerOpen: d,
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
		move: D,
		reorder: k,
		resize: A,
		cardPayload: U
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
}, Xe = {
	key: 1,
	class: "overview-more-summary overview-more-summary--compact"
}, W = {
	key: 2,
	class: "overview-more-summary overview-more-summary--compact"
}, Ze = {
	key: 3,
	class: "overview-more-summary overview-more-summary--compact"
}, Qe = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], G = /*#__PURE__*/ y(/* @__PURE__ */ i({
	__name: "DashboardPage",
	props: {
		api: {},
		deps: {}
	},
	setup(i, { expose: o }) {
		let h = i, _ = ee(h.api, h.deps), { cards: y, ids: w, prefs: T, customizerOpen: E, loading: D, error: O } = _, k = e(), A = e();
		C(A, () => E.value, () => _.visible.value);
		let j = (e) => z.find((t) => t.id === e)?.label || e, M = e(null);
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
		let I = (e) => e?.sources || [], L = (e) => e?.leases || [], R = (e) => e?.plans || [], B = (e) => e?.rows || [];
		function V() {
			_.closeCustomizer();
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
		f(() => document.addEventListener("keydown", U)), t(() => document.removeEventListener("keydown", U));
		function G(e) {
			e && (e[0] === "config" ? h.deps.onConfig?.("代理与网络") : h.deps.onNavigate?.(e[0]));
		}
		function K(e) {
			return _.ids.value.metrics.includes(e) ? "metrics" : "panels";
		}
		function q(e) {
			M.value = e;
		}
		function J(e) {
			M.value &&= (_.reorder(K(e), M.value, e), null);
		}
		function Y(e, t) {
			if (![
				"ArrowLeft",
				"ArrowUp",
				"ArrowRight",
				"ArrowDown"
			].includes(t.key)) return;
			t.preventDefault(), _.move(K(e), e, ["ArrowLeft", "ArrowUp"].includes(t.key) ? "up" : "down");
			let n = t.currentTarget;
			p(() => n.focus({ preventScroll: !0 }));
		}
		let X;
		function Z(e = !0) {
			X?.(e);
		}
		function Q(e, t) {
			if (t.button !== 0 || X) return;
			let n = t.currentTarget, r = n.closest("[data-dashboard-card]"), i = r?.parentElement;
			if (!r || !i) return;
			let a = K(e), o = [..._.prefs.order[a]], s = t.clientX, c = t.clientY, l = r.getBoundingClientRect(), u, d, f = s, m = c;
			n.setPointerCapture?.(t.pointerId);
			let h = () => {
				let t = document.elementFromPoint?.(f, m)?.closest("[data-dashboard-card]");
				if (!t || t === r || t.parentElement !== i) return;
				let n = t.getBoundingClientRect(), o = r.getBoundingClientRect(), s = getComputedStyle(i).gridTemplateColumns.trim().split(/\s+/).length === 1 || Math.abs(o.top - n.top) > 8 || t.dataset.overviewSize === "full" ? m >= n.top + n.height / 2 : f >= n.left + n.width / 2, c = new Map(Array.from(i.children).map((e) => [e, e.getBoundingClientRect()]));
				_.reorder(a, e, t.dataset.dashboardCard, s), p(() => {
					if (!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) for (let [e, t] of c) {
						if (e === r) continue;
						let n = e.getBoundingClientRect(), i = t.left - n.left, a = t.top - n.top;
						(i || a) && e.animate?.([{ transform: `translate(${i}px,${a}px)` }, { transform: "translate(0,0)" }], {
							duration: 180,
							easing: "cubic-bezier(.2,.75,.2,1)"
						});
					}
				});
			}, g = () => {
				if (d = void 0, !u) return;
				let e = m, t = e >= 0 && e < 64 ? -Math.ceil((64 - e) / 4) : e <= window.innerHeight && e > window.innerHeight - 64 ? Math.ceil((e - window.innerHeight + 64) / 4) : 0;
				if (!t) return;
				let n = document.scrollingElement?.scrollTop;
				window.scrollBy(0, t), document.scrollingElement?.scrollTop !== n && (h(), d = requestAnimationFrame(g));
			}, v = (e) => {
				if (e.pointerId !== t.pointerId) return;
				f = e.clientX, m = e.clientY;
				let n = f - s, i = m - c;
				!u && Math.hypot(n, i) < 5 || (u || (u = r.cloneNode(!0), u.classList.add("overview-drag-ghost"), u.setAttribute("aria-hidden", "true"), Object.assign(u.style, {
					left: `${l.left}px`,
					top: `${l.top}px`,
					width: `${l.width}px`,
					height: `${l.height}px`
				}), document.body.append(u), r.classList.add("is-drag-placeholder")), u.style.transform = `translate3d(${n}px,${i}px,0)`, h(), d ||= requestAnimationFrame(g));
			}, y = (e) => {
				e.pointerId === t.pointerId && Z(e.type === "pointercancel");
			};
			X = (e = !1) => {
				X = void 0, window.removeEventListener("pointermove", v), window.removeEventListener("pointerup", y), window.removeEventListener("pointercancel", y), d && cancelAnimationFrame(d), n.hasPointerCapture?.(t.pointerId) && n.releasePointerCapture(t.pointerId), u?.remove(), r.classList.remove("is-drag-placeholder"), e && _.mutate((e) => {
					e.order[a] = o;
				});
			}, window.addEventListener("pointermove", v), window.addEventListener("pointerup", y), window.addEventListener("pointercancel", y), t.preventDefault();
		}
		function $(e, t) {
			if (t.button !== 0 || X) return;
			let n = t.currentTarget, r = n.closest("[data-dashboard-card]"), i = r?.parentElement;
			if (!r || !i) return;
			let a = getComputedStyle(i), o = Math.max(1, a.gridTemplateColumns.trim().split(/\s+/).length), s = parseFloat(a.columnGap) || 0, c = r.getBoundingClientRect(), l = (i.getBoundingClientRect().width - s * (o - 1)) / o, u = K(e), d = _.prefs.sizes[e] || "normal", f = r.style.minHeight, p = d, m = _.prefs.heights[e], h = !1;
			n.setPointerCapture?.(t.pointerId), r.classList.add("is-resizing");
			let g = (e) => {
				if (e.pointerId !== t.pointerId) return;
				let n = e.clientX - t.clientX, i = e.clientY - t.clientY;
				if (Math.abs(n) > 4 && l > 0) {
					let e = Math.max(1, Math.min(o, Math.round((c.width + n + s) / (l + s))));
					p = e <= 1 ? "normal" : e >= Math.min(o, u === "metrics" ? 4 : 3) && o >= 3 ? "full" : "wide", r.dataset.overviewSize = p, h = !0;
				}
				Math.abs(i) > 4 && (m = Math.max(160, Math.min(800, Math.round(c.height + i))), r.style.minHeight = `${m}px`, u === "panels" && (r.dataset.overviewDensity = m < 220 ? "minimal" : m < 300 ? "compact" : "normal"), h = !0);
			}, v = (e) => {
				e.pointerId === t.pointerId && Z(e.type === "pointercancel");
			};
			X = (i = !1) => {
				if (X = void 0, window.removeEventListener("pointermove", g), window.removeEventListener("pointerup", v), window.removeEventListener("pointercancel", v), r.classList.remove("is-resizing"), n.hasPointerCapture?.(t.pointerId) && n.releasePointerCapture(t.pointerId), !i && h) _.mutate((t) => {
					t.sizes[e] = p, m !== void 0 && (t.heights[e] = m);
				});
				else {
					r.dataset.overviewSize = d, r.style.minHeight = f;
					let t = _.prefs.heights[e];
					u === "panels" && (r.dataset.overviewDensity = t ? t < 220 ? "minimal" : t < 300 ? "compact" : "normal" : "normal");
				}
			}, window.addEventListener("pointermove", g), window.addEventListener("pointerup", v), window.addEventListener("pointercancel", v), t.preventDefault();
		}
		return a(_.visible, (e) => {
			e || Z();
		}), a(_.data, () => Z()), t(() => Z()), o({
			load: _.load,
			setVisible: _.setVisible,
			openCustomizer: _.openCustomizer,
			closeCustomizer: _.closeCustomizer,
			resetLayout: _.resetLayout
		}), (e, t) => (r(), s("div", te, [
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
				"aria-expanded": g(E),
				onClick: t[0] ||= (...e) => g(_).openCustomizer && g(_).openCustomizer(...e)
			}, "自定义总览", 8, ie), m("button", {
				type: "button",
				class: "overview-refresh",
				disabled: g(D),
				onClick: t[1] ||= (...e) => g(_).load && g(_).load(...e)
			}, "刷新数据", 8, ae)])]),
			g(O) ? (r(), s("div", oe, [
				t[10] ||= m("strong", null, "总览加载失败", -1),
				m("span", null, u(g(O)), 1),
				m("button", {
					type: "button",
					onClick: t[2] ||= (...e) => g(_).load && g(_).load(...e)
				}, "重试")
			])) : d("", !0),
			m("dialog", {
				ref_key: "customizer",
				ref: A,
				class: "overview-customizer",
				role: "dialog",
				"aria-modal": "true",
				"aria-labelledby": "dashboard-customizer-title",
				"aria-hidden": !g(E),
				onCancel: c(V, ["prevent"]),
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
				m("div", ce, [(r(), s(b, null, n(["metrics", "panels"], (e) => m("section", {
					key: e,
					class: "overview-customizer-group"
				}, [m("div", le, [m("strong", null, u(e === "metrics" ? "指标卡片" : "详细卡片"), 1), m("small", null, u((g(w)[e] || []).length) + " 张可用卡片", 1)]), m("div", ue, [(r(!0), s(b, null, n(g(T).order[e] || [], (n) => (r(), s("div", {
					key: n,
					class: "overview-customizer-item",
					draggable: "true",
					"data-dashboard-custom-card": n,
					onDragstart: (e) => q(n),
					onDragover: t[3] ||= c(() => {}, ["prevent"]),
					onDrop: (e) => J(n)
				}, [
					t[12] ||= m("span", {
						class: "overview-drag-handle",
						"aria-hidden": "true"
					}, "拖动", -1),
					m("label", null, [m("input", {
						type: "checkbox",
						checked: !g(T).hidden.includes(n),
						onChange: (e) => g(_).toggle(n, e.target.checked)
					}, null, 40, fe), m("span", null, u(j(n)), 1)]),
					m("div", {
						class: "overview-customizer-move",
						role: "group",
						"aria-label": `调整 ${n} 顺序`
					}, [m("button", {
						type: "button",
						onClick: (t) => g(_).move(e, n, "up")
					}, "上移", 8, me), m("button", {
						type: "button",
						onClick: (t) => g(_).move(e, n, "down")
					}, "下移", 8, he)], 8, pe)
				], 40, de))), 128))])])), 64))]),
				m("div", ge, [m("button", {
					type: "button",
					class: "overview-reset-layout",
					"data-dashboard-reset-layout": "",
					onClick: t[4] ||= (...e) => g(_).resetLayout && g(_).resetLayout(...e)
				}, "恢复默认布局")])
			], 40, se),
			m("div", _e, [(r(!0), s(b, null, n(g(y).filter((e) => e.card.region === "metrics"), (e) => (r(), s("article", {
				key: e.card.id,
				class: "overview-metric",
				"data-dashboard-card": e.card.id,
				"data-overview-card": e.card.id,
				"data-overview-size": e.size,
				style: x({
					"--metric-color": e.payload.color,
					minHeight: e.height ? `${e.height}px` : void 0
				}),
				onDragstart: t[5] ||= c(() => {}, ["prevent"]),
				onDragover: t[6] ||= c(() => {}, ["prevent"]),
				onDrop: (t) => J(e.card.id)
			}, [
				m("div", ye, [m("span", null, u(e.card.label), 1), m("div", be, [t[14] ||= m("i", {
					class: "overview-metric-dot",
					"aria-hidden": "true"
				}, null, -1), m("span", {
					class: "overview-card-drag",
					role: "button",
					tabindex: "0",
					"aria-label": `拖动${e.card.label}卡片排序，或使用方向键调整顺序`,
					onKeydown: (t) => Y(e.card.id, t),
					onPointerdown: (t) => Q(e.card.id, t)
				}, [...t[13] ||= [S("<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" data-v-43bd5ce5><circle cx=\"5\" cy=\"3\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"11\" cy=\"3\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"5\" cy=\"8\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"11\" cy=\"8\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"5\" cy=\"13\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"11\" cy=\"13\" r=\"1\" data-v-43bd5ce5></circle></svg>", 1)]], 40, xe)])]),
				m("strong", null, u(e.payload.value), 1),
				m("small", null, u(e.payload.hint), 1),
				m("button", {
					type: "button",
					class: "overview-resize-handle",
					"data-overview-resize": "",
					"aria-label": `拖动调整${e.card.label}卡片宽高；方向键可调整`,
					onPointerdown: (t) => $(e.card.id, t),
					onKeydown: [
						v(c((t) => g(_).resize(e.card.id, "width", -1), ["prevent"]), ["left"]),
						v(c((t) => g(_).resize(e.card.id, "width", 1), ["prevent"]), ["right"]),
						v(c((t) => g(_).resize(e.card.id, "height", -40), ["prevent"]), ["up"]),
						v(c((t) => g(_).resize(e.card.id, "height", 40), ["prevent"]), ["down"])
					]
				}, [...t[15] ||= [m("svg", {
					viewBox: "0 0 16 16",
					"aria-hidden": "true"
				}, [m("path", { d: "M6 14l8-8M10 14l4-4" })], -1)]], 40, Se)
			], 44, ve))), 128))]),
			m("div", Ce, [(r(!0), s(b, null, n(g(y).filter((e) => e.card.region === "panels"), (e) => (r(), s("section", {
				key: e.card.id,
				class: "overview-panel",
				"data-dashboard-card": e.card.id,
				"data-overview-card": e.card.id,
				"data-overview-size": e.size,
				"data-overview-density": e.density,
				style: x(e.height ? { minHeight: `${e.height}px` } : void 0),
				onDragstart: t[7] ||= c(() => {}, ["prevent"]),
				onDragover: t[8] ||= c(() => {}, ["prevent"]),
				onDrop: (t) => J(e.card.id)
			}, [
				m("div", Te, [m("div", null, [m("span", null, u(e.card.label.split(" · ")[0]), 1), m("h3", null, u(e.card.label.split(" · ").slice(1).join(" · ")), 1)]), m("div", Ee, [e.payload.action ? (r(), s("button", {
					key: 0,
					type: "button",
					onClick: (t) => G(e.payload.action)
				}, u(e.payload.action[1]), 9, De)) : d("", !0), m("span", {
					class: "overview-card-drag",
					role: "button",
					tabindex: "0",
					"aria-label": `拖动${e.card.label}卡片排序，或使用方向键调整顺序`,
					onKeydown: (t) => Y(e.card.id, t),
					onPointerdown: (t) => Q(e.card.id, t)
				}, [...t[16] ||= [S("<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" data-v-43bd5ce5><circle cx=\"5\" cy=\"3\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"11\" cy=\"3\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"5\" cy=\"8\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"11\" cy=\"8\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"5\" cy=\"13\" r=\"1\" data-v-43bd5ce5></circle><circle cx=\"11\" cy=\"13\" r=\"1\" data-v-43bd5ce5></circle></svg>", 1)]], 40, Oe)])]),
				e.payload.kind === "email" ? (r(), s("div", ke, [
					(r(!0), s(b, null, n(I(e.payload), (e, n) => (r(), s("article", {
						key: e.source,
						class: l(["overview-source", {
							"overview-density-secondary": Number(n) >= 2,
							"overview-density-minimal-extra": Number(n) >= 1
						}])
					}, [
						m("div", Ae, [m("span", {
							class: "overview-source-name",
							title: e.label
						}, u(e.label), 9, je), t[17] ||= m("i", {
							class: "overview-source-state is-on",
							"aria-hidden": "true"
						}, null, -1)]),
						m("strong", null, u(N(e, "available")), 1),
						m("small", null, "本地总数 " + u(N(e, "total")) + " · 已用 " + u(N(e, "used")) + " · 失败 " + u(N(e, "failed")), 1)
					], 2))), 128)),
					I(e.payload).length > 2 ? (r(), s("div", Me, "另有 " + u(I(e.payload).length - 2) + " 个来源，进入详情查看", 1)) : d("", !0),
					I(e.payload).length > 1 ? (r(), s("div", Ne, "另有 " + u(I(e.payload).length - 1) + " 个来源，进入详情查看", 1)) : d("", !0)
				])) : e.payload.kind === "proxy" ? (r(), s("div", Pe, [
					m("div", Fe, [m("div", Ie, [t[18] ||= m("span", null, "系统代理平台", -1), m("strong", null, u(e.payload.platform), 1)]), m("div", Le, [t[19] ||= m("span", null, "活跃出口", -1), m("strong", null, u(e.payload.active) + " 个", 1)])]),
					m("div", Re, [(r(!0), s(b, null, n(L(e.payload), (e, n) => (r(), s("div", {
						key: n,
						class: l(["overview-exit-row", { "overview-density-secondary": Number(n) >= 1 }])
					}, [
						t[20] ||= m("i", { "aria-hidden": "true" }, null, -1),
						m("span", null, u(e.endpoint || e.exit_ip || "活跃出口"), 1),
						m("small", null, u(e.region || e.provider || ""), 1)
					], 2))), 128)), L(e.payload).length ? d("", !0) : (r(), s("div", ze, "当前没有活跃代理出口"))]),
					e.payload.more ? (r(), s("div", Be, u(e.payload.more), 1)) : d("", !0)
				])) : e.payload.kind === "plans" ? (r(), s("div", Ve, [
					(r(!0), s(b, null, n(R(e.payload), ([t, n], i) => (r(), s("div", {
						key: t,
						class: l(["overview-plan-row", {
							"overview-density-secondary": Number(i) >= 3,
							"overview-density-minimal-extra": Number(i) >= 2
						}])
					}, [
						m("span", null, u(P(t)), 1),
						m("div", He, [m("i", { style: x({ width: `${Math.max(4, Math.round(Number(n) / Math.max(1, ...R(e.payload).map((e) => Number(e[1]))) * 100))}%` }) }, null, 4)]),
						m("strong", null, u(n), 1)
					], 2))), 128)),
					R(e.payload).length > 3 ? (r(), s("div", Ue, "另有 " + u(R(e.payload).length - 3) + " 种套餐，进入详情查看", 1)) : d("", !0),
					R(e.payload).length > 2 ? (r(), s("div", We, "另有 " + u(R(e.payload).length - 2) + " 种套餐，进入详情查看", 1)) : d("", !0)
				])) : e.payload.kind === "today" ? (r(), s("div", Ge, [(r(!0), s(b, null, n(B(e.payload), ([t, n, i], a) => (r(), s("div", {
					key: t,
					class: l(["overview-job-row", { "overview-density-secondary": t === "partial_success" || Number(a) > 0 && !i }])
				}, [m("span", { class: l(["pill", `status-${t}`]) }, u(F(t)), 3), m("div", Ke, [m("strong", null, u(i) + " 个任务", 1), m("small", null, u(e.payload.today) + " · " + u(n), 1)])], 2))), 128)), B(e.payload)[1]?.[2] ? (r(), s("div", qe, "部分成功 " + u(B(e.payload)[1]?.[2]), 1)) : d("", !0)])) : e.payload.kind === "queue" || e.payload.kind === "history" || e.payload.kind === "health" || e.payload.kind === "codex" ? (r(), s("div", Je, [
					(r(!0), s(b, null, n(B(e.payload), ([t, n], i) => (r(), s("div", {
						key: t,
						class: l(["overview-status-item", { "overview-density-secondary": e.payload.kind === "health" ? [1, 3].includes(Number(i)) : Number(i) > 1 }])
					}, [m("span", null, u(t), 1), m("strong", null, u(n), 1)], 2))), 128)),
					e.payload.kind === "queue" && B(e.payload)[2]?.[1] ? (r(), s("div", Ye, "停止中 " + u(B(e.payload)[2]?.[1]), 1)) : d("", !0),
					e.payload.kind === "history" && (B(e.payload)[2]?.[1] || B(e.payload)[3]?.[1]) ? (r(), s("div", Xe, "部分成功 " + u(B(e.payload)[2]?.[1] || 0) + " · 已停止或取消 " + u(B(e.payload)[3]?.[1] || 0), 1)) : d("", !0),
					e.payload.kind === "health" ? (r(), s("div", W, "已用 " + u(B(e.payload)[1]?.[1] || 0) + " · 停用 " + u(B(e.payload)[3]?.[1] || 0), 1)) : d("", !0),
					e.payload.kind === "codex" ? (r(), s("div", Ze, "账号 Codex 就绪 " + u(B(e.payload)[2]?.[1] || 0), 1)) : d("", !0)
				])) : d("", !0),
				m("button", {
					type: "button",
					class: "overview-resize-handle",
					"data-overview-resize": "",
					"aria-label": `拖动调整${e.card.label}卡片宽高；方向键可调整`,
					onPointerdown: (t) => $(e.card.id, t),
					onKeydown: [
						v(c((t) => g(_).resize(e.card.id, "width", -1), ["prevent"]), ["left"]),
						v(c((t) => g(_).resize(e.card.id, "width", 1), ["prevent"]), ["right"]),
						v(c((t) => g(_).resize(e.card.id, "height", -40), ["prevent"]), ["up"]),
						v(c((t) => g(_).resize(e.card.id, "height", 40), ["prevent"]), ["down"])
					]
				}, [...t[21] ||= [m("svg", {
					viewBox: "0 0 16 16",
					"aria-hidden": "true"
				}, [m("path", { d: "M6 14l8-8M10 14l4-4" })], -1)]], 40, Qe)
			], 44, we))), 128))])
		]));
	}
}), [["__scopeId", "data-v-43bd5ce5"]]);
// src/api/dashboard.ts
function K(e = (e, t) => w(e, t)) {
	let t = (t, n) => e(t, n ? { signal: n } : void 0);
	return {
		dashboard: (e) => t("/api/dashboard", e),
		capabilities: (e) => t("/api/capabilities", e)
	};
}
// src/dashboard.ts
function q(e, t = {}) {
	let n = h(G, {
		api: t.api || K(),
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
export { q as mountDashboard };
