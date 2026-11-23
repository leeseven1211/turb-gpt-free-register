import { C as e, F as t, H as n, L as r, M as i, _ as a, b as o, d as s, dt as c, et as l, ft as u, h as d, j as f, lt as p, m, n as h, st as g, t as _, v, x as y } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { r as b, t as x } from "./client-B5R_MNgP.js";
// src/features/dashboard/useDashboard.ts
var S = 2e4, C = (e) => Number(e || 0);
function w(e) {
	return !e || typeof e != "object" || e.ok !== !0 ? null : {
		today_extracted: C(e.today_extracted),
		today_plus_confirmed: C(e.today_plus_confirmed),
		awaiting_payment: C(e.awaiting_payment),
		needs_review: C(e.needs_review),
		processing: C(e.processing),
		all: C(e.all),
		providers: Array.isArray(e.providers) ? e.providers.filter((e) => e && typeof e == "object") : []
	};
}
function T(e) {
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
function ee(e, t = {}) {
	let r = l(null), a = l(null), o = l({}), s = l(!1), c = l(""), u = l(null), d = l(!!t.visible), p, h, g, _ = !1, v = 0;
	function y(e) {
		_ || d.value === !!e || (d.value = !!e, v++, h?.abort(), g = void 0, d.value ? (b(), x()) : (p && window.clearInterval(p), p = void 0, s.value = !1));
	}
	function b() {
		p && window.clearInterval(p), p = window.setInterval(() => void x(), S);
	}
	function x() {
		if (_ || !d.value || document.hidden) return Promise.resolve();
		if (g) return g;
		let n = ++v;
		h?.abort(), h = new AbortController(), s.value = !0, c.value = "";
		let i = h.signal, l = (async () => {
			try {
				let [s, c, l] = await Promise.allSettled([
					e.dashboard(i),
					e.capabilities(i),
					e.extractSummary ? e.extractSummary(i) : Promise.resolve(null)
				]);
				if (n !== v || !d.value || document.hidden) return;
				if (s.status === "rejected") throw s.reason;
				r.value = s.value, a.value = l.status === "fulfilled" ? w(l.value) : null, c.status === "fulfilled" && c.value != null && (o.value = c.value || {}, t.onCapabilities?.(o.value)), u.value = Date.now(), t.onReady?.();
			} catch (e) {
				n === v && !String(e?.name || "").includes("Abort") && (c.value = e?.message || "总览加载失败", t.notify?.(`总览加载失败：${c.value}`));
			} finally {
				n === v && (s.value = !1, g = void 0);
			}
		})();
		return g = l, l;
	}
	let C = () => {
		!document.hidden && d.value ? x() : (v++, h?.abort(), g = void 0, s.value = !1);
	};
	return i(() => {
		document.addEventListener("visibilitychange", C), d.value && (b(), x());
	}), f(() => {
		_ = !0, d.value = !1, v++, g = void 0, s.value = !1, document.removeEventListener("visibilitychange", C), h?.abort(), p && window.clearInterval(p), p = void 0;
	}), n(() => t.visible, (e) => y(!!e)), {
		data: r,
		extract: a,
		caps: o,
		loading: s,
		error: c,
		updatedAt: u,
		visible: d,
		hasData: m(() => !!r.value),
		load: x,
		setVisible: y
	};
}
// src/features/dashboard/DashboardPage.vue?vue&type=script&setup=true&lang.ts
var te = { class: "ov-section-head" }, ne = { class: "ov-section-actions" }, re = { class: "ov-updated" }, ie = ["disabled"], ae = {
	key: 0,
	class: "ov-error",
	role: "alert"
}, oe = {
	key: 1,
	class: "ov-alerts",
	"aria-label": "需要关注"
}, se = ["onClick"], ce = {
	key: 2,
	class: "ov-skeleton",
	"aria-label": "正在读取总览"
}, le = {
	class: "ov-pulse",
	"aria-label": "服务脉搏"
}, ue = ["title", "onClick"], de = { class: "ov-pulse-top" }, fe = { class: "ov-grid" }, pe = {
	class: "ov-card ov-card--email",
	"data-overview-card": "email",
	style: {
		"--accent": "#1f9d75",
		"--accent-soft": "#e7f6f0"
	}
}, me = { class: "ov-card-head" }, he = { class: "ov-figure" }, ge = { class: "ov-mini-grid ov-mini-grid--3" }, _e = {
	key: 0,
	class: "ov-bars"
}, ve = { class: "ov-bar-label" }, ye = {
	key: 1,
	class: "ov-empty"
}, be = {
	key: 2,
	class: "ov-foot"
}, xe = {
	key: 3,
	class: "ov-foot"
}, Se = {
	class: "ov-card ov-card--accounts",
	"data-overview-card": "accounts",
	style: {
		"--accent": "#5b5ce2",
		"--accent-soft": "#eeeefe"
	}
}, Ce = { class: "ov-card-head" }, we = { class: "ov-figure" }, Te = {
	class: "ov-split",
	"aria-hidden": "true"
}, Ee = { class: "ov-legend" }, De = { class: "ov-mini-grid ov-mini-grid--2" }, Oe = { class: "ov-meter" }, ke = { class: "ov-bar" }, Ae = {
	class: "ov-card ov-card--codex",
	"data-overview-card": "codex",
	style: {
		"--accent": "#377dff",
		"--accent-soft": "#e9f1ff"
	}
}, je = { class: "ov-card-head" }, Me = { class: "ov-figure" }, Ne = {
	key: 0,
	class: "ov-chip is-warn"
}, Pe = { class: "ov-bar-label" }, Fe = { class: "ov-bar ov-bar--thick" }, Ie = { class: "ov-mini-grid ov-mini-grid--3" }, Le = { class: "ov-foot" }, Re = {
	class: "ov-card ov-card--extract",
	"data-overview-card": "extract",
	style: {
		"--accent": "#d97706",
		"--accent-soft": "#fdf3e3"
	}
}, ze = { class: "ov-card-head" }, Be = { class: "ov-figure" }, Ve = {
	key: 0,
	class: "ov-mini-grid ov-mini-grid--4"
}, He = { class: "is-warn" }, Ue = {
	key: 1,
	class: "ov-empty"
}, We = { class: "ov-foot" }, Ge = {
	class: "ov-card ov-card--plans",
	"data-overview-card": "plans",
	style: {
		"--accent": "#8b5cf6",
		"--accent-soft": "#f3edff"
	}
}, Ke = { class: "ov-card-head" }, qe = { class: "ov-figure ov-figure--small" }, Je = { class: "ov-bars" }, Ye = { class: "ov-bar-label" }, Xe = { class: "ov-bar" }, Ze = {
	key: 1,
	class: "ov-empty"
}, Qe = {
	class: "ov-card ov-card--proxy",
	"data-overview-card": "proxy",
	style: {
		"--accent": "#0e9aa7",
		"--accent-soft": "#e6f6f7"
	}
}, $e = { class: "ov-card-head" }, et = { class: "ov-figure" }, tt = { class: "ov-chip" }, nt = {
	key: 0,
	class: "ov-lease-list"
}, rt = {
	key: 1,
	class: "ov-empty"
}, it = {
	key: 2,
	class: "ov-foot"
}, at = {
	class: "ov-card ov-card--jobs",
	"data-overview-card": "jobs",
	style: {
		"--accent": "#475569",
		"--accent-soft": "#eef1f5"
	}
}, ot = { class: "ov-card-head" }, st = { class: "ov-task-columns" }, ct = { class: "ov-task-block" }, lt = { class: "ov-mini-grid ov-mini-grid--3" }, ut = { class: "ov-task-block" }, dt = { class: "ov-mini-grid ov-mini-grid--3" }, ft = { class: "is-ok" }, pt = { class: "is-warn" }, mt = { class: "is-danger" }, ht = { class: "ov-task-block ov-task-block--wide" }, gt = {
	key: 0,
	class: "ov-stack",
	"aria-hidden": "true"
}, _t = { class: "ov-stack-legend" }, vt = { key: 0 }, yt = {
	key: 0,
	class: "ov-foot"
}, E = /*#__PURE__*/ _(/* @__PURE__ */ e({
	__name: "DashboardPage",
	props: {
		api: {},
		deps: {}
	},
	setup(e, { expose: n }) {
		let f = e, h = ee(f.api, f.deps), { data: _, extract: b, caps: x, loading: S, error: C, updatedAt: w } = h, E = l(!1);
		i(() => {
			E.value = !0;
		});
		let D = (e) => new Intl.NumberFormat("zh-CN").format(Number(e || 0)), O = (e) => Number(e || 0), k = (e, t) => {
			let n = O(t);
			return n > 0 ? Math.max(0, Math.min(100, Math.round(O(e) / n * 100))) : 0;
		}, bt = (e) => ({
			free: "Free",
			free_trial_eligible: "Free · 试用资格",
			free_half_price_eligible: "Free · 半价资格",
			free_discount_eligible: "Free · 折扣资格",
			free_promo_unknown: "Free · 优惠待查",
			plus: "Plus",
			pro: "Pro",
			team: "Team",
			go: "Go",
			unknown: "未检测"
		})[e] || e, A = m(() => _.value?.accounts || {}), j = m(() => _.value?.email?.supply || {}), M = m(() => (Array.isArray(j.value?.sources) ? j.value.sources : Array.isArray(_.value?.email?.sources) ? _.value.email.sources : []).filter((e) => e?.kind === "local_pool")), N = m(() => M.value.filter((e) => O(e.total) > 0 || O(e.available) > 0)), P = m(() => Math.max(0, M.value.length - N.value.length)), xt = m(() => j.value?.status === "error" ? "读取失败" : O(j.value?.available)), F = m(() => j.value?.status === "error" ? "—" : D(xt.value)), I = m(() => O(j.value?.total)), L = m(() => O(j.value?.used)), St = m(() => O(j.value?.failed) + O(j.value?.disabled)), R = m(() => j.value?.status === "error" ? "danger" : I.value > 0 && O(j.value?.available) === 0 ? "warn" : O(j.value?.available) > 0 ? "ok" : "idle"), Ct = m(() => j.value?.status === "error" ? "读取失败" : I.value === 0 ? "未配置" : O(j.value?.available) === 0 ? "库存耗尽" : "库存正常"), z = m(() => _.value?.codex || {}), B = m(() => O(z.value.pending) > 0 ? "warn" : O(z.value.total) > 0 ? "ok" : "idle"), V = m(() => Object.entries(A.value?.plans || {}).map(([e, t]) => ({
			key: e,
			label: bt(e),
			count: O(t)
		})).sort((e, t) => t.count - e.count)), wt = m(() => Math.max(1, ...V.value.map((e) => e.count))), H = m(() => V.value.reduce((e, t) => e + t.count, 0)), U = m(() => _.value?.jobs || {}), Tt = m(() => x.value?.features?.register?.enabled === !1), W = m(() => ({ ...U.value?.counts || {} })), G = m(() => ({ ...U.value?.today_counts || {} })), Et = m(() => O(W.value.pending) + O(W.value.running) + O(W.value.stopping));
		m(() => O(G.value.success) + O(G.value.partial_success) + O(G.value.failed));
		let K = m(() => [
			{
				key: "success",
				label: "成功",
				value: O(W.value.success),
				color: "#1f9d75"
			},
			{
				key: "partial_success",
				label: "部分成功",
				value: O(W.value.partial_success),
				color: "#d99a2b"
			},
			{
				key: "failed",
				label: "失败",
				value: O(W.value.failed),
				color: "#d9534f"
			},
			{
				key: "cancelled",
				label: "停止/取消",
				value: O(W.value.stopped) + O(W.value.cancelled),
				color: "#98a2b3"
			}
		].filter((e) => e.value > 0)), Dt = m(() => Et.value > 0 ? "active" : O(G.value.failed) > 0 ? "warn" : "idle"), q = m(() => _.value?.proxy || {}), J = m(() => Array.isArray(q.value.leases) ? q.value.leases.slice(0, 3) : []), Ot = m(() => Math.max(0, O(q.value.active_leases) - J.value.length)), kt = m(() => x.value?.proxy?.registration?.enabled === !1), At = m(() => O(q.value.active_leases) > 0 ? "ok" : "idle"), Y = m(() => b.value || {}), X = m(() => O(Y.value.needs_review) > 0 ? "warn" : O(Y.value.processing) > 0 ? "active" : "idle"), Z = m(() => O(Y.value.all) === 0 && O(Y.value.today_extracted) === 0 && O(Y.value.processing) === 0 && O(Y.value.needs_review) === 0 && O(Y.value.awaiting_payment) === 0), jt = m(() => [
			{
				id: "email",
				label: "邮箱",
				value: F.value,
				hint: O(j.value?.available) === 0 ? "库存耗尽" : `邮箱总量 ${D(I.value)}`,
				tone: R.value,
				tab: "outlook"
			},
			{
				id: "accounts",
				label: "账号",
				value: D(A.value.active),
				hint: `归档 ${D(A.value.archived)}`,
				tone: "ok",
				tab: "accounts"
			},
			{
				id: "codex",
				label: "Codex",
				value: D(z.value.total),
				hint: `待导出 ${D(z.value.pending)}`,
				tone: B.value,
				tab: "codex"
			},
			{
				id: "plans",
				label: "套餐",
				value: D(V.value.length),
				hint: `${D(H.value)} 个已归类`,
				tone: "ok",
				tab: "accounts"
			},
			{
				id: "extract",
				label: "提炼",
				value: D(Y.value.today_extracted),
				hint: O(Y.value.needs_review) > 0 ? `待核对 ${D(Y.value.needs_review)}` : "今日已提炼",
				tone: X.value,
				tab: "extract-workbench"
			},
			{
				id: "proxy",
				label: "代理",
				value: D(q.value.active_leases),
				hint: T(q.value.platform),
				tone: At.value,
				tab: "proxy-traffic"
			},
			{
				id: "jobs",
				label: "任务",
				value: D(Et.value),
				hint: `累计 ${D(U.value.total)}`,
				tone: Dt.value,
				tab: "tasks"
			}
		]), Q = m(() => {
			let e = [];
			return j.value?.status === "error" ? e.push({
				tone: "danger",
				text: "邮箱池统计读取失败，暂时无法判断可用库存。",
				tab: "outlook",
				label: "检查邮箱池"
			}) : I.value > 0 && O(j.value?.available) === 0 && e.push({
				tone: "warning",
				text: `邮箱池已用完（已用 ${D(L.value)} / 邮箱总量 ${D(I.value)}），新的注册任务取不到邮箱。`,
				tab: "outlook",
				label: "添加邮箱库存"
			}), O(Y.value.needs_review) > 0 && e.push({
				tone: "warning",
				text: `提炼工作台有 ${D(Y.value.needs_review)} 个任务待核对。`,
				tab: "extract-workbench",
				label: "去核对"
			}), e.slice(0, 2);
		}), Mt = m(() => w.value ? `数据更新 ${new Date(w.value).toLocaleTimeString("zh-CN", { hour12: !1 })}` : S.value ? "正在读取…" : "尚未读取"), $ = (e) => f.deps.onNavigate?.(e);
		return n({
			load: h.load,
			setVisible: h.setVisible,
			openCustomizer: () => {},
			closeCustomizer: () => {},
			resetLayout: () => {}
		}), (e, n) => (t(), v("div", { class: p(["ov-page", { "is-mounted": E.value }]) }, [
			d("div", te, [n[11] ||= d("div", { class: "ov-section-title" }, [d("h2", null, "服务脉搏"), d("p", null, "邮箱 · 账号 · Codex · 套餐 · 提炼 · 代理 · 任务")], -1), d("div", ne, [d("span", re, [n[9] ||= d("i", { "aria-hidden": "true" }, null, -1), y(u(Mt.value), 1)]), d("button", {
				type: "button",
				class: "ov-refresh",
				disabled: g(S),
				onClick: n[0] ||= (...e) => g(h).load && g(h).load(...e)
			}, [n[10] ||= d("svg", {
				viewBox: "0 0 24 24",
				"aria-hidden": "true"
			}, [d("path", { d: "M20 11a8 8 0 1 0-2.3 6.7" }), d("path", { d: "M20 4v7h-7" })], -1), y(" " + u(g(S) ? "刷新中" : "刷新"), 1)], 8, ie)])]),
			g(C) ? (t(), v("div", ae, [d("div", null, [n[12] ||= d("strong", null, "总览加载失败", -1), d("span", null, u(g(C)), 1)]), d("button", {
				type: "button",
				onClick: n[1] ||= (...e) => g(h).load && g(h).load(...e)
			}, "重试")])) : a("", !0),
			Q.value.length ? (t(), v("section", oe, [(t(!0), v(s, null, r(Q.value, (e) => (t(), v("article", {
				key: e.text,
				class: p(["ov-alert", `is-${e.tone}`])
			}, [
				n[13] ||= d("svg", {
					viewBox: "0 0 24 24",
					"aria-hidden": "true"
				}, [
					d("path", { d: "M12 9v4" }),
					d("path", { d: "M12 17h.01" }),
					d("path", { d: "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" })
				], -1),
				d("p", null, u(e.text), 1),
				d("button", {
					type: "button",
					onClick: (t) => $(e.tab)
				}, u(e.label), 9, se)
			], 2))), 128))])) : a("", !0),
			!g(_) && g(S) ? (t(), v("section", ce, [...n[14] ||= [d("div", { class: "ov-skeleton-pulse" }, null, -1), d("div", { class: "ov-skeleton-grid" }, [
				d("i"),
				d("i"),
				d("i"),
				d("i")
			], -1)]])) : a("", !0),
			g(_) ? (t(), v(s, { key: 3 }, [d("nav", le, [(t(!0), v(s, null, r(jt.value, (e) => (t(), v("button", {
				key: e.id,
				type: "button",
				class: p(["ov-pulse-item", [`is-${e.tone}`, { "is-zero": e.value === "0" }]]),
				title: `${e.label} · ${e.hint}`,
				onClick: (t) => $(e.tab)
			}, [d("span", de, [n[15] ||= d("i", { "aria-hidden": "true" }, null, -1), y(u(e.label), 1)]), d("strong", null, u(e.value), 1)], 10, ue))), 128))]), d("div", fe, [
				d("article", pe, [
					d("header", me, [n[17] ||= o("<div class=\"ov-card-title\" data-v-481e7e08><span class=\"ov-icon\" data-v-481e7e08><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-481e7e08><rect x=\"3\" y=\"5\" width=\"18\" height=\"14\" rx=\"2\" data-v-481e7e08></rect><path d=\"m3 7 9 6 9-6\" data-v-481e7e08></path></svg></span><div data-v-481e7e08><h3 data-v-481e7e08>邮箱池</h3><p data-v-481e7e08>本地库存与来源</p></div></div>", 1), d("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "email",
						onClick: n[2] ||= (e) => $("outlook")
					}, [...n[16] ||= [y("管理", -1), d("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [d("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					d("div", he, [
						d("strong", { class: p({ "is-danger": R.value === "warn" }) }, u(F.value), 3),
						n[18] ||= d("span", null, "可用", -1),
						R.value === "ok" ? a("", !0) : (t(), v("em", {
							key: 0,
							class: p(["ov-chip", `is-${R.value}`])
						}, u(Ct.value), 3))
					]),
					d("div", ge, [
						d("div", null, [n[19] ||= d("span", null, "邮箱总量", -1), d("strong", null, u(D(I.value)), 1)]),
						d("div", null, [n[20] ||= d("span", null, "已使用", -1), d("strong", null, u(D(L.value)), 1)]),
						d("div", null, [n[21] ||= d("span", null, "停用 / 失败", -1), d("strong", null, u(D(St.value)), 1)])
					]),
					N.value.length ? (t(), v("ul", _e, [(t(!0), v(s, null, r(N.value, (e) => (t(), v("li", { key: e.source }, [d("div", ve, [d("span", null, u(e.label), 1), d("small", null, u(O(e.available) === 0 ? "已用尽" : `可用 ${D(e.available)}`) + " / " + u(D(e.total)), 1)]), d("div", { class: p(["ov-bar", { "is-spent": O(e.available) === 0 && O(e.total) > 0 }]) }, [d("i", { style: c({ width: k(e.available, e.total) + "%" }) }, null, 4)], 2)]))), 128))])) : (t(), v("p", ye, "还没有可统计的邮箱库存。")),
					P.value ? (t(), v("p", be, "另有 " + u(P.value) + " 个来源暂无库存 · 仅统计本地库存", 1)) : (t(), v("p", xe, "仅统计本地库存，用完后需手动导入"))
				]),
				d("article", Se, [
					d("header", Ce, [n[23] ||= o("<div class=\"ov-card-title\" data-v-481e7e08><span class=\"ov-icon\" data-v-481e7e08><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-481e7e08><path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\" data-v-481e7e08></path><circle cx=\"9\" cy=\"7\" r=\"4\" data-v-481e7e08></circle><path d=\"M22 21v-2a4 4 0 0 0-3-3.9\" data-v-481e7e08></path></svg></span><div data-v-481e7e08><h3 data-v-481e7e08>账号</h3><p data-v-481e7e08>账号资产</p></div></div>", 1), d("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "accounts",
						onClick: n[3] ||= (e) => $("accounts")
					}, [...n[22] ||= [y("管理", -1), d("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [d("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					d("div", we, [d("strong", null, u(D(A.value.active)), 1), n[24] ||= d("span", null, "活跃账号", -1)]),
					d("div", Te, [d("i", {
						class: "is-active",
						style: c({ width: k(A.value.active, A.value.total) + "%" })
					}, null, 4), d("i", {
						class: "is-idle",
						style: c({ width: k(A.value.archived, A.value.total) + "%" })
					}, null, 4)]),
					d("div", Ee, [d("span", null, [n[25] ||= d("i", { style: { background: "#5b5ce2" } }, null, -1), y("活跃 " + u(D(A.value.active)), 1)]), d("span", null, [n[26] ||= d("i", { style: { background: "#d7dbe5" } }, null, -1), y("归档 " + u(D(A.value.archived)), 1)])]),
					d("div", De, [d("div", null, [n[27] ||= d("span", null, "账号总数", -1), d("strong", null, u(D(A.value.total)), 1)]), d("div", null, [n[28] ||= d("span", null, "Codex 就绪", -1), d("strong", null, u(D(A.value.codex_ready)), 1)])]),
					d("div", Oe, [
						n[29] ||= d("span", null, "Codex 就绪率", -1),
						d("div", ke, [d("i", { style: c({ width: k(A.value.codex_ready, A.value.active) + "%" }) }, null, 4)]),
						d("strong", null, u(k(A.value.codex_ready, A.value.active)) + "%", 1)
					])
				]),
				d("article", Ae, [
					d("header", je, [n[31] ||= o("<div class=\"ov-card-title\" data-v-481e7e08><span class=\"ov-icon\" data-v-481e7e08><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-481e7e08><rect x=\"3\" y=\"11\" width=\"18\" height=\"10\" rx=\"2\" data-v-481e7e08></rect><path d=\"M7 11V7a5 5 0 0 1 10 0v4\" data-v-481e7e08></path></svg></span><div data-v-481e7e08><h3 data-v-481e7e08>Codex</h3><p data-v-481e7e08>授权凭证</p></div></div>", 1), d("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "codex",
						onClick: n[4] ||= (e) => $("codex")
					}, [...n[30] ||= [y("查看", -1), d("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [d("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					d("div", Me, [
						d("strong", null, u(D(z.value.total)), 1),
						n[32] ||= d("span", null, "已导出凭证", -1),
						B.value === "warn" ? (t(), v("em", Ne, "待导出")) : a("", !0)
					]),
					d("div", Pe, [n[33] ||= d("span", null, "导出进度", -1), d("small", null, u(D(z.value.exported)) + " / " + u(D(z.value.total)), 1)]),
					d("div", Fe, [d("i", { style: c({ width: k(z.value.exported, z.value.total) + "%" }) }, null, 4)]),
					d("div", Ie, [
						d("div", null, [n[34] ||= d("span", null, "已导出", -1), d("strong", null, u(D(z.value.exported)), 1)]),
						d("div", null, [n[35] ||= d("span", null, "待导出", -1), d("strong", null, u(D(z.value.pending)), 1)]),
						d("div", null, [n[36] ||= d("span", null, "账号就绪", -1), d("strong", null, u(D(A.value.codex_ready)), 1)])
					]),
					d("p", Le, "账号 Codex 就绪 " + u(D(A.value.codex_ready)) + " · 覆盖 " + u(k(A.value.codex_ready, A.value.active)) + "% 活跃账号", 1)
				]),
				d("article", Re, [
					d("header", ze, [n[38] ||= o("<div class=\"ov-card-title\" data-v-481e7e08><span class=\"ov-icon\" data-v-481e7e08><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-481e7e08><path d=\"m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z\" data-v-481e7e08></path><path d=\"M19 15.5 20 18l2.5 1-2.5 1L19 22l-1-2-2.5-1 2.5-1 1-2.5Z\" data-v-481e7e08></path></svg></span><div data-v-481e7e08><h3 data-v-481e7e08>提炼</h3><p data-v-481e7e08>提链工作台</p></div></div>", 1), d("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "extract",
						onClick: n[5] ||= (e) => $("extract-workbench")
					}, [...n[37] ||= [y("工作台", -1), d("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [d("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					d("div", Be, [
						d("strong", null, u(D(Y.value.today_extracted)), 1),
						n[39] ||= d("span", null, "今日已提炼", -1),
						d("em", { class: p(["ov-chip", `is-${X.value}`]) }, u(X.value === "idle" ? "空闲" : X.value === "warn" ? "待核对" : "处理中"), 3)
					]),
					Z.value ? a("", !0) : (t(), v("div", Ve, [
						d("div", null, [n[40] ||= d("span", null, "Plus 已确认", -1), d("strong", null, u(D(Y.value.today_plus_confirmed)), 1)]),
						d("div", null, [n[41] ||= d("span", null, "处理中", -1), d("strong", null, u(D(Y.value.processing)), 1)]),
						d("div", null, [n[42] ||= d("span", null, "待支付", -1), d("strong", null, u(D(Y.value.awaiting_payment)), 1)]),
						d("div", null, [n[43] ||= d("span", null, "待核对", -1), d("strong", He, u(D(Y.value.needs_review)), 1)])
					])),
					Z.value ? (t(), v("p", Ue, "今日还没有提炼任务，进入工作台即可发起。")) : a("", !0),
					d("p", We, u(Z.value ? "提链工作台空闲" : `累计 ${D(Y.value.all)} 个提炼任务`), 1)
				]),
				d("article", Ge, [d("header", Ke, [n[45] ||= o("<div class=\"ov-card-title\" data-v-481e7e08><span class=\"ov-icon\" data-v-481e7e08><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-481e7e08><path d=\"M12 2 2 7l10 5 10-5-10-5Z\" data-v-481e7e08></path><path d=\"m2 12 10 5 10-5\" data-v-481e7e08></path><path d=\"m2 17 10 5 10-5\" data-v-481e7e08></path></svg></span><div data-v-481e7e08><h3 data-v-481e7e08>套餐</h3><p data-v-481e7e08>账号套餐分布</p></div></div>", 1), d("button", {
					type: "button",
					class: "ov-link",
					"data-overview-action": "plans",
					onClick: n[6] ||= (e) => $("accounts")
				}, [...n[44] ||= [y("账号", -1), d("svg", {
					viewBox: "0 0 24 24",
					"aria-hidden": "true"
				}, [d("path", { d: "m9 6 6 6-6 6" })], -1)]])]), V.value.length ? (t(), v(s, { key: 0 }, [d("div", qe, [d("strong", null, u(D(V.value.length)), 1), d("span", null, "种套餐 · " + u(D(H.value)) + " 个账号", 1)]), d("ul", Je, [(t(!0), v(s, null, r(V.value, (e) => (t(), v("li", { key: e.key }, [d("div", Ye, [d("span", null, u(e.label), 1), d("small", null, u(D(e.count)) + " · " + u(k(e.count, H.value)) + "%", 1)]), d("div", Xe, [d("i", { style: c({ width: Math.max(4, Math.round(e.count / wt.value * 100)) + "%" }) }, null, 4)])]))), 128))])], 64)) : (t(), v("p", Ze, "还没有可用的套餐数据。"))]),
				d("article", Qe, [
					d("header", $e, [n[47] ||= o("<div class=\"ov-card-title\" data-v-481e7e08><span class=\"ov-icon\" data-v-481e7e08><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-481e7e08><circle cx=\"12\" cy=\"12\" r=\"9\" data-v-481e7e08></circle><path d=\"M3 12h18\" data-v-481e7e08></path><path d=\"M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3Z\" data-v-481e7e08></path></svg></span><div data-v-481e7e08><h3 data-v-481e7e08>代理</h3><p data-v-481e7e08>网络出口</p></div></div>", 1), d("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "proxy",
						onClick: n[7] ||= (e) => $("proxy-traffic")
					}, [...n[46] ||= [y("查看", -1), d("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [d("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					d("div", et, [
						d("strong", null, u(D(q.value.active_leases)), 1),
						n[48] ||= d("span", null, "活跃出口", -1),
						d("em", tt, u(g(T)(q.value.platform)), 1)
					]),
					J.value.length ? (t(), v("ul", nt, [(t(!0), v(s, null, r(J.value, (e, r) => (t(), v("li", { key: r }, [
						n[49] ||= d("i", { "aria-hidden": "true" }, null, -1),
						d("span", null, u(e.endpoint || e.exit_ip || "活跃出口"), 1),
						d("small", null, u(e.region || e.provider || ""), 1)
					]))), 128))])) : (t(), v("p", rt, u(kt.value ? "注册代理未启用，当前没有活跃租约。" : `当前没有活跃的代理租约，新任务会走 ${g(T)(q.value.platform)}。`), 1)),
					J.value.length ? (t(), v("p", it, [y(u(kt.value ? "注册代理未启用，已有租约仍保留" : `代理平台 ${g(T)(q.value.platform)}`), 1), Ot.value ? (t(), v(s, { key: 0 }, [y(" · 另有 " + u(Ot.value) + " 个活跃出口", 1)], 64)) : a("", !0)])) : a("", !0)
				]),
				d("article", at, [
					d("header", ot, [n[51] ||= o("<div class=\"ov-card-title\" data-v-481e7e08><span class=\"ov-icon\" data-v-481e7e08><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-481e7e08><path d=\"M9 5h11\" data-v-481e7e08></path><path d=\"M9 12h11\" data-v-481e7e08></path><path d=\"M9 19h11\" data-v-481e7e08></path><circle cx=\"4\" cy=\"5\" r=\"1\" data-v-481e7e08></circle><circle cx=\"4\" cy=\"12\" r=\"1\" data-v-481e7e08></circle><circle cx=\"4\" cy=\"19\" r=\"1\" data-v-481e7e08></circle></svg></span><div data-v-481e7e08><h3 data-v-481e7e08>任务</h3><p data-v-481e7e08>注册流水线与队列</p></div></div>", 1), d("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "jobs",
						onClick: n[8] ||= (e) => $("tasks")
					}, [...n[50] ||= [y("任务中心", -1), d("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [d("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					d("div", st, [
						d("section", ct, [n[55] ||= d("h4", null, "当前队列", -1), d("div", lt, [
							d("div", null, [n[52] ||= d("span", null, "运行中", -1), d("strong", null, u(D(W.value.running)), 1)]),
							d("div", null, [n[53] ||= d("span", null, "待处理", -1), d("strong", null, u(D(W.value.pending)), 1)]),
							d("div", null, [n[54] ||= d("span", null, "停止中", -1), d("strong", null, u(D(W.value.stopping)), 1)])
						])]),
						d("section", ut, [d("h4", null, [n[56] ||= y("今日结果 ", -1), d("small", null, u(U.value.today), 1)]), d("div", dt, [
							d("div", null, [n[57] ||= d("span", null, "成功", -1), d("strong", ft, u(D(G.value.success)), 1)]),
							d("div", null, [n[58] ||= d("span", null, "部分成功", -1), d("strong", pt, u(D(G.value.partial_success)), 1)]),
							d("div", null, [n[59] ||= d("span", null, "失败", -1), d("strong", mt, u(D(G.value.failed)), 1)])
						])]),
						d("section", ht, [
							d("h4", null, [n[60] ||= y("累计结果 ", -1), d("small", null, u(D(U.value.total)) + " 个任务", 1)]),
							K.value.length ? (t(), v("div", gt, [(t(!0), v(s, null, r(K.value, (e) => (t(), v("i", {
								key: e.key,
								style: c({
									width: e.value / Math.max(1, U.value.total) * 100 + "%",
									background: e.color
								})
							}, null, 4))), 128))])) : a("", !0),
							d("div", _t, [(t(!0), v(s, null, r(K.value, (e) => (t(), v("span", { key: e.key }, [d("i", { style: c({ background: e.color }) }, null, 4), y(u(e.label) + " " + u(D(e.value)), 1)]))), 128)), K.value.length ? a("", !0) : (t(), v("span", vt, "暂无累计结果"))])
						])
					]),
					Tt.value ? (t(), v("p", yt, "注册功能未启用，历史任务仍可查看。")) : a("", !0)
				])
			])], 64)) : a("", !0)
		], 2));
	}
}), [["__scopeId", "data-v-481e7e08"]]);
// src/api/dashboard.ts
async function D(e, t) {
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
function O(e = (e, t) => b(e, t), t) {
	let n = (t, n) => e(t, n ? { signal: n } : void 0);
	return {
		dashboard: (e) => n("/api/dashboard", e),
		extractSummary: (e) => n("/api/extract-workbench/summary", e),
		async capabilities(e) {
			let r = t?.();
			if (!r) return n("/api/capabilities", e);
			let i = await D(r, e);
			if (typeof i != "object" || !i || !("ok" in i) || i.ok !== !0) throw new x("能力检查返回无效数据", 200);
			return i;
		}
	};
}
// src/dashboard.ts
function k(e, t = {}) {
	let n = h(E, {
		api: t.api || O(void 0, t.pendingCapabilities),
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
export { k as mountDashboard };
