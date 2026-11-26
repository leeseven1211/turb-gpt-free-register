import { C as e, F as t, H as n, K as r, L as i, M as a, S as o, V as s, _ as c, b as l, d as u, dt as d, et as f, ft as p, h as m, j as h, lt as g, m as _, n as v, o as y, st as b, t as x, v as S, x as C } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { r as w, t as T } from "./client-B5R_MNgP.js";
// src/features/dashboard/useDashboard.ts
var ee = 2e4, E = (e) => Number(e || 0);
function te(e) {
	return !e || typeof e != "object" || e.ok !== !0 ? null : {
		today_extracted: E(e.today_extracted),
		today_plus_confirmed: E(e.today_plus_confirmed),
		awaiting_payment: E(e.awaiting_payment),
		processing: E(e.processing),
		all: E(e.all),
		providers: Array.isArray(e.providers) ? e.providers.filter((e) => e && typeof e == "object") : []
	};
}
function D(e) {
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
function O(e, t = {}) {
	let r = f(null), i = f(null), o = f({}), s = f(null), c = f(!1), l = f(""), u = f(null), d = f(null), p = f(null), m = f(!1), g = f(""), v = f(null), y = f(!!t.visible), b = f(!1), x, S, C, w, T, E = "", D = !1, O = !1, k = 0, A = 0, j = {};
	function M(t, n) {
		if (O || !y.value || document.hidden || !e.registrationDaily) return Promise.resolve();
		let r = t !== void 0 || n !== void 0, i = r ? t || void 0 : j.from, a = r ? n || void 0 : j.to, o = JSON.stringify([i || "", a || ""]);
		if (T && E === o) return T;
		j = {
			from: i,
			to: a
		}, r && (d.value = {
			from: i,
			to: a
		});
		let f = ++A;
		C?.abort(), C = new AbortController(), c.value = !0, l.value = "";
		let m = C.signal, h = (async () => {
			try {
				let t = await e.registrationDaily?.(i, a, m);
				if (f !== A || !y.value || document.hidden) return;
				if (!t || t.ok === !1) throw Error(t?.message || "每日注册统计读取失败");
				s.value = t, p.value = {
					from: typeof t.date_from == "string" ? t.date_from : i,
					to: typeof t.date_to == "string" ? t.date_to : a
				}, u.value = typeof t.updated_at == "string" ? t.updated_at : (/* @__PURE__ */ new Date()).toISOString();
			} catch (e) {
				f === A && !String(e?.name || "").includes("Abort") && (l.value = e?.message || "每日注册统计读取失败");
			} finally {
				f === A && (c.value = !1, T = void 0);
			}
		})();
		return T = h, E = o, h;
	}
	function N(e) {
		O || y.value === !!e || (y.value = !!e, k++, A++, S?.abort(), C?.abort(), w = void 0, T = void 0, D = !1, y.value ? (P(), F(!0)) : (x && window.clearInterval(x), x = void 0, m.value = !1, c.value = !1, E = ""));
	}
	function P() {
		x && window.clearInterval(x), x = window.setInterval(() => void F(!0), ee);
	}
	function F(n = !1) {
		if (O || !y.value || document.hidden) return Promise.resolve();
		let a = n && b.value;
		if (w) return !a && D && (m.value = !0), w;
		M(j.from, j.to);
		let s = ++k;
		S?.abort(), S = new AbortController(), D = !0, a || (m.value = !0), n || (g.value = "");
		let c = S.signal, l = () => s === k && y.value && !document.hidden, u = (async () => {
			try {
				let n = await e.dashboard(c);
				if (!l()) return;
				r.value = n, b.value = !0, g.value = "", v.value = Date.now(), t.onReady?.();
			} catch (e) {
				l() && !String(e?.name || "").includes("Abort") && (g.value = e?.message || "总览加载失败", t.notify?.(`总览加载失败：${g.value}`));
			} finally {
				s === k && (D = !1, m.value = !1);
			}
		})(), d = (async () => {
			try {
				let n = await e.capabilities(c);
				if (!l() || n == null) return;
				o.value = n || {}, t.onCapabilities?.(o.value);
			} catch {}
		})(), f = (async () => {
			try {
				let t = await e.extractSummary?.(c);
				l() && (i.value = te(t));
			} catch {
				l() && (i.value = null);
			}
		})(), p = Promise.allSettled([
			u,
			d,
			f
		]).then(() => {
			s === k && (w = void 0);
		});
		return w = p, p;
	}
	let I = () => {
		!document.hidden && y.value ? F(!0) : (k++, A++, S?.abort(), C?.abort(), w = void 0, T = void 0, E = "", D = !1, m.value = !1, c.value = !1);
	};
	a(() => {
		document.addEventListener("visibilitychange", I), y.value && (P(), F());
	}), h(() => {
		O = !0, y.value = !1, k++, A++, w = void 0, T = void 0, E = "", D = !1, m.value = !1, c.value = !1, document.removeEventListener("visibilitychange", I), S?.abort(), C?.abort(), x && window.clearInterval(x), x = void 0;
	}), n(() => t.visible, (e) => N(!!e));
	let ne = _(() => !!r.value);
	return {
		data: r,
		extract: i,
		caps: o,
		daily: s,
		dailyLoading: c,
		dailyError: l,
		dailyUpdatedAt: u,
		dailyRequestedRange: d,
		dailyDisplayedRange: p,
		dailyScopeCurrent: _(() => !s.value || !d.value || d.value.from === p.value?.from && d.value.to === p.value?.to),
		loading: m,
		error: g,
		updatedAt: v,
		visible: y,
		hasData: ne,
		load: F,
		loadDaily: M,
		setVisible: N
	};
}
// src/features/dashboard/DailyRegistrationStats.vue?vue&type=script&setup=true&lang.ts
var k = {
	class: "daily-stats",
	"aria-labelledby": "daily-registration-title"
}, A = { class: "daily-stats-head" }, j = { class: "daily-stats-meta" }, M = { "data-daily-range": "" }, N = {
	class: "daily-stats-controls",
	role: "group",
	"aria-label": "统计日期范围"
}, P = {
	key: 0,
	class: "daily-stats-error",
	"data-daily-error": "",
	role: "alert"
}, F = ["disabled"], I = {
	key: 1,
	class: "daily-stats-stale",
	"data-daily-stale": "",
	role: "status"
}, ne = {
	key: 2,
	class: "daily-stats-loading",
	"aria-live": "polite"
}, L = {
	key: 0,
	class: "daily-chart"
}, R = {
	class: "daily-chart-legend",
	"data-daily-legend": "",
	"aria-label": "套餐优惠图例"
}, re = { key: 0 }, ie = { key: 1 }, ae = {
	class: "daily-stats-chart",
	role: "group",
	"aria-label": "每日账号套餐优惠覆盖堆叠柱状图"
}, oe = {
	class: "daily-chart-axis",
	"data-daily-axis": ""
}, se = {
	class: "daily-axis-ticks",
	"aria-hidden": "true"
}, z = { class: "daily-chart-scroll" }, ce = {
	class: "daily-chart-grid",
	"aria-hidden": "true"
}, le = [
	"data-daily-bar",
	"aria-label",
	"title",
	"aria-pressed",
	"tabindex",
	"onClick",
	"onFocus",
	"onKeydown"
], B = {
	class: "daily-bar-value",
	"aria-hidden": "true"
}, ue = { "data-daily-account-total": "" }, V = { "data-daily-coverage-total": "" }, de = {
	class: "daily-bar-stack",
	"aria-hidden": "true"
}, H = ["data-daily-segment", "title"], fe = { "aria-hidden": "true" }, pe = ["data-daily-row"], U = { class: "daily-row-heading" }, me = ["disabled", "onClick"], W = { class: "daily-row-metrics" }, G = { class: "daily-row-offers" }, K = ["data-daily-offer-group"], q = { class: "daily-offer-items" }, he = ["data-daily-offer"], J = { class: "daily-offer-name" }, Y = { class: "daily-offer-count" }, ge = {
	key: 0,
	class: "daily-offer-stale"
}, _e = {
	key: 0,
	class: "daily-offers-empty"
}, ve = {
	key: 1,
	class: "daily-offers-empty"
}, X = {
	key: 2,
	class: "daily-stats-empty"
}, ye = {
	key: 3,
	class: "daily-stats-summary"
}, be = ["disabled"], xe = /*#__PURE__*/ x(/* @__PURE__ */ e({
	__name: "DailyRegistrationStats",
	props: {
		state: {},
		onBulkPlanCreate: { type: Function }
	},
	setup(e) {
		let a = e, o = f("7"), l = f(""), h = f(""), v = f(!1), b = f(""), x = `daily-registration-detail-${s()}`, w = _(() => Array.isArray(a.state.data?.rows) ? a.state.data.rows : []), T = _(() => ({
			from: a.state.data?.date_from || w.value[0]?.date || "",
			to: a.state.data?.date_to || w.value[w.value.length - 1]?.date || ""
		})), ee = _(() => T.value.from && T.value.to ? `${T.value.from} 至 ${T.value.to}` : "日期范围待返回"), E = _(() => a.state.updatedAt ? `更新于 ${new Date(a.state.updatedAt).toLocaleString("zh-CN", {
			hour12: !1,
			timeZone: "Asia/Shanghai"
		})}` : a.state.loading ? "正在读取…" : "尚未读取"), te = _(() => a.state.error && a.state.data && a.state.scopeCurrent ? `${a.state.error}，当前成功范围仍可使用。` : a.state.error), D = _(() => w.value.find((e) => e.date === b.value)), O = {
			team: "Team",
			plus: "Plus",
			go: "Go"
		}, xe = [
			"team",
			"plus",
			"go"
		];
		function Se(e, t) {
			let n = (e) => {
				let t = xe.indexOf(e);
				return t < 0 ? xe.length : t;
			};
			return n(e.plan) - n(t.plan) || e.label.localeCompare(t.label, "zh-CN") || e.key.localeCompare(t.key);
		}
		function Ce(e) {
			let t = 0;
			for (let n of e.key) t = t * 31 + n.charCodeAt(0) >>> 0;
			return `hsl(${({
				team: 156,
				plus: 250,
				go: 35
			}[e.plan] ?? 210) + t % 25 - 12} ${52 + (t >>> 5) % 20}% ${39 + (t >>> 10) % 18}%)`;
		}
		function Z(e) {
			return Array.isArray(e.offers) ? e.offers.map((e) => ({
				...e,
				count: Math.max(0, Pe(e.count)),
				stale_count: Math.max(0, Pe(e.stale_count))
			})).sort(Se) : null;
		}
		function we(e) {
			let t = /* @__PURE__ */ new Map();
			for (let n of Z(e) ?? []) t.set(n.plan, [...t.get(n.plan) ?? [], n]);
			return [...t].map(([e, t]) => ({
				plan: e,
				label: O[e] || e,
				offers: t
			}));
		}
		let Te = _(() => w.value.map((e) => {
			let t = Z(e), n = (t ?? []).filter((e) => e.count > 0).map((e) => ({
				...e,
				color: Ce(e)
			}));
			return {
				row: e,
				unavailable: t === null,
				segments: n,
				total: t === null ? null : n.reduce((e, t) => e + t.count, 0)
			};
		})), Ee = _(() => Math.max(1, Math.ceil(Math.max(0, ...Te.value.map((e) => e.total ?? 0)) / 4))), De = _(() => Ee.value * 4), Oe = _(() => [
			4,
			3,
			2,
			1,
			0
		].map((e) => e * Ee.value)), ke = _(() => {
			let e = /* @__PURE__ */ new Map();
			for (let t of Te.value) for (let n of t.segments) e.has(n.key) || e.set(n.key, n);
			return [...e.values()].sort(Se);
		}), Ae = _(() => Te.value.some((e) => e.unavailable));
		function je(e) {
			let t = e.unavailable ? "优惠数据待查" : e.segments.map((t) => Le(e.row, t)).join("，");
			return `${e.row.date}，优惠覆盖数 ${Q(e.total)}，账号总数 ${Q(e.row.accounts_total)}，有优惠账号 ${Q(e.row.promoted_accounts_total)}${t ? `，${t}` : ""}，点击查看当日详情`;
		}
		function Me(e) {
			b.value = e;
		}
		function Ne(e, t) {
			let n = t;
			if (e.key === "ArrowRight") n = Math.min(w.value.length - 1, t + 1);
			else if (e.key === "ArrowLeft") n = Math.max(0, t - 1);
			else if (e.key === "Home") n = 0;
			else if (e.key === "End") n = w.value.length - 1;
			else return;
			e.preventDefault();
			let r = w.value[n];
			if (!r) return;
			Me(r.date);
			let i = e.currentTarget.parentElement?.querySelectorAll("[data-daily-bar]");
			i?.[n]?.focus({ preventScroll: !0 }), i?.[n]?.scrollIntoView?.({
				block: "nearest",
				inline: "nearest"
			});
		}
		function Pe(e) {
			let t = Number(e);
			return Number.isFinite(t) ? t : 0;
		}
		function Fe(e) {
			if (e == null) return null;
			let t = Number(e);
			return Number.isFinite(t) ? t : null;
		}
		function Ie(e, t) {
			let n = Fe(e.accounts_total);
			if (!n || n < 0 || t < 0) return "—";
			let r = t / n * 100;
			return r > 0 && r < .01 ? "<0.01%" : `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(r)}%`;
		}
		function Le(e, t) {
			return `${t.label} ${Q(t.count)}个账号 · ${Ie(e, t.count)}（占当日账号）`;
		}
		function Q(e) {
			let t = Fe(e);
			return t === null ? "—" : new Intl.NumberFormat("zh-CN").format(t);
		}
		function Re(e) {
			let t = Fe(e);
			return t === null ? "待查" : new Intl.NumberFormat("zh-CN").format(t);
		}
		function ze(e) {
			return Fe(e.unpromoted_count);
		}
		function Be(e) {
			return a.state.scopeCurrent && ze(e) !== null && ze(e) > 0 && !!e.query;
		}
		function Ve(e, t) {
			Be(e) && e.query && a.onBulkPlanCreate?.({
				name: t,
				query: e.query
			});
		}
		function He(e, t) {
			let n = /* @__PURE__ */ new Date(`${e}T00:00:00Z`);
			return n.setUTCDate(n.getUTCDate() + t), n.toISOString().slice(0, 10);
		}
		function Ue() {
			let e = new Intl.DateTimeFormat("en-US", {
				timeZone: "Asia/Shanghai",
				year: "numeric",
				month: "2-digit",
				day: "2-digit"
			}).formatToParts(/* @__PURE__ */ new Date()), t = Object.fromEntries(e.filter((e) => e.type !== "literal").map((e) => [e.type, e.value]));
			return `${t.year}-${t.month}-${t.day}`;
		}
		function We(e) {
			let t = Ue();
			return [He(t, -(e - 1)), t];
		}
		function Ge(e) {
			o.value = e;
			let [t, n] = We(Number(e));
			a.state.load(t, n);
		}
		function Ke() {
			o.value = "custom", l.value = a.state.displayedRange?.from || T.value.from, h.value = a.state.displayedRange?.to || T.value.to;
		}
		function qe() {
			o.value !== "custom" || !l.value || !h.value || l.value > h.value || a.state.load(l.value, h.value);
		}
		return n(w, (e) => {
			e.some((e) => e.date === b.value) || (b.value = e[0]?.date || "");
		}, { immediate: !0 }), n(() => [a.state.data?.date_from, a.state.data?.date_to], ([e, t]) => {
			!v.value && (e || t) && (l.value = e || "", h.value = t || "", v.value = !0);
		}, { immediate: !0 }), (n, a) => (t(), S("section", k, [
			m("header", A, [a[6] ||= m("div", null, [m("h2", { id: "daily-registration-title" }, "每日账号套餐优惠"), m("p", null, "北京时间 · 按注册任务创建日期关联账号 · 优惠以最近成功查询为准，并非注册当日历史 · 含归档账号")], -1), m("div", j, [m("span", M, p(ee.value), 1), m("span", null, p(E.value), 1)])]),
			m("div", N, [
				m("button", {
					type: "button",
					"data-daily-range-7": "",
					class: g({ active: o.value === "7" }),
					onClick: a[0] ||= (e) => Ge("7")
				}, "近 7 天", 2),
				m("button", {
					type: "button",
					"data-daily-range-30": "",
					class: g({ active: o.value === "30" }),
					onClick: a[1] ||= (e) => Ge("30")
				}, "近 30 天", 2),
				m("button", {
					type: "button",
					class: g({ active: o.value === "custom" }),
					onClick: Ke
				}, "自定义", 2),
				o.value === "custom" ? (t(), S(u, { key: 0 }, [m("label", null, [a[7] ||= C("开始日期", -1), r(m("input", {
					"onUpdate:modelValue": a[2] ||= (e) => l.value = e,
					type: "date",
					onChange: qe
				}, null, 544), [[y, l.value]])]), m("label", null, [a[8] ||= C("结束日期", -1), r(m("input", {
					"onUpdate:modelValue": a[3] ||= (e) => h.value = e,
					type: "date",
					onChange: qe
				}, null, 544), [[y, h.value]])])], 64)) : c("", !0)
			]),
			e.state.error ? (t(), S("div", P, [m("span", null, p(te.value), 1), m("button", {
				type: "button",
				"data-daily-retry": "",
				disabled: e.state.loading,
				onClick: a[4] ||= (t) => e.state.load()
			}, "重试", 8, F)])) : c("", !0),
			e.state.data && !e.state.scopeCurrent ? (t(), S("div", I, p(e.state.loading ? "正在读取新日期范围，当前仍显示上一成功范围；完成前不能新建查套餐批量。" : "新日期范围读取失败，当前仍显示上一成功范围；请重试后再新建查套餐批量。"), 1)) : c("", !0),
			e.state.loading && !e.state.data ? (t(), S("div", ne, "正在读取每日套餐优惠…")) : e.state.data ? (t(), S(u, { key: 3 }, [
				w.value.length ? (t(), S("div", L, [
					a[10] ||= m("div", { class: "daily-chart-heading" }, [m("strong", null, "每日套餐优惠分布"), m("p", null, "点选日期查看详情 · 方向键切换日期")], -1),
					a[11] ||= m("p", { class: "daily-chart-note" }, "同一账号有多项优惠时分别计数；每项按账号去重。占比 = 优惠账号数 ÷ 当日账号总数，多项占比合计可超过100%。", -1),
					m("div", R, [(t(!0), S(u, null, i(ke.value, (e) => (t(), S("span", { key: e.key }, [m("i", {
						style: d({ backgroundColor: e.color }),
						"aria-hidden": "true"
					}, null, 4), C(p(e.label), 1)]))), 128)), Ae.value ? (t(), S("span", re, "优惠数据待查")) : ke.value.length ? c("", !0) : (t(), S("span", ie, "暂无可用优惠记录"))]),
					m("div", ae, [m("div", oe, [a[9] ||= m("span", { class: "daily-axis-unit" }, "优惠覆盖数", -1), m("div", se, [(t(!0), S(u, null, i(Oe.value, (e) => (t(), S("span", {
						key: e,
						"data-daily-axis-tick": ""
					}, p(Q(e)), 1))), 128))])]), m("div", z, [m("div", {
						class: "daily-chart-plot",
						style: d({
							gridTemplateColumns: `repeat(${w.value.length},minmax(64px,1fr))`,
							minWidth: `${w.value.length * 68}px`
						})
					}, [m("div", ce, [(t(!0), S(u, null, i(Oe.value, (e) => (t(), S("i", { key: e }))), 128))]), (t(!0), S(u, null, i(Te.value, (e, n) => (t(), S("button", {
						key: e.row.date,
						type: "button",
						class: g(["daily-bar-column", { selected: e.row.date === b.value }]),
						"data-daily-bar": e.row.date,
						"aria-label": je(e),
						title: je(e),
						"aria-pressed": e.row.date === b.value,
						"aria-controls": x,
						tabindex: e.row.date === b.value ? 0 : -1,
						onClick: (t) => Me(e.row.date),
						onFocus: (t) => Me(e.row.date),
						onKeydown: (e) => Ne(e, n)
					}, [
						m("span", B, [m("span", ue, "账号 " + p(Q(e.row.accounts_total)), 1), m("span", V, "覆盖 " + p(e.unavailable ? "待查" : Q(e.total)), 1)]),
						m("span", de, [(t(!0), S(u, null, i(e.segments, (n) => (t(), S("span", {
							key: n.key,
							class: "daily-bar-segment",
							"data-daily-segment": n.key,
							title: Le(e.row, n),
							style: d({
								height: `${n.count / De.value * 100}%`,
								backgroundColor: n.color
							})
						}, null, 12, H))), 128))]),
						m("small", fe, p(e.row.date.slice(5)), 1)
					], 42, le))), 128))], 4)])])
				])) : c("", !0),
				D.value ? (t(), S("div", {
					key: 1,
					id: x,
					class: "daily-selected-detail",
					"aria-live": "polite",
					"aria-atomic": "true"
				}, [(t(!0), S(u, null, i([D.value], (e) => (t(), S("article", {
					key: e.date,
					class: "daily-stats-row",
					"data-daily-row": e.date
				}, [
					m("div", U, [m("div", null, [m("strong", null, p(e.date), 1), m("span", null, "注册任务总数 " + p(Q(e.total)), 1)]), m("button", {
						type: "button",
						"data-daily-bulk": "",
						disabled: !Be(e),
						onClick: (t) => Ve(e, `${e.date} 无优惠账号查套餐`)
					}, " 新建查套餐批量（" + p(Re(e.unpromoted_count)) + "） ", 9, me)]),
					m("div", W, [
						m("span", null, "账号总数（含归档） " + p(Q(e.accounts_total)), 1),
						m("span", null, "有优惠账号 " + p(Q(e.promoted_accounts_total)), 1),
						m("span", null, "未归档 Plus 无优惠 " + p(Re(e.unpromoted_count)), 1)
					]),
					m("div", G, [Z(e) ? (t(), S(u, { key: 0 }, [(t(!0), S(u, null, i(we(e), (n) => (t(), S("div", {
						key: n.plan,
						class: "daily-offer-group",
						"data-daily-offer-group": n.plan
					}, [m("strong", null, p(n.label), 1), m("div", q, [(t(!0), S(u, null, i(n.offers, (n) => (t(), S("div", {
						key: n.key,
						class: "daily-offer-item",
						"data-daily-offer": n.key
					}, [
						m("span", J, [m("i", {
							style: d({ backgroundColor: Ce(n) }),
							"aria-hidden": "true"
						}, null, 4), C(p(n.label), 1)]),
						m("span", Y, p(Q(n.count)) + " 个账号 · " + p(Ie(e, n.count)), 1),
						n.stale_count > 0 ? (t(), S("span", ge, p(Q(n.stale_count)) + " 个待复查", 1)) : c("", !0)
					], 8, he))), 128))])], 8, K))), 128)), Z(e).length ? c("", !0) : (t(), S("span", _e, "暂无可用优惠记录（含无优惠或未查询账号）。"))], 64)) : (t(), S("span", ve, "优惠数据待查"))])
				], 8, pe))), 128))])) : (t(), S("p", X, "所选日期暂无统计。")),
				e.state.data.summary ? (t(), S("div", ye, [m("div", null, [a[12] ||= m("strong", null, "区间汇总", -1), m("span", null, "注册任务总数 " + p(Q(e.state.data.summary.total)) + " · 账号总数（含归档，区间去重） " + p(Q(e.state.data.summary.accounts_total)) + " · 有优惠账号 " + p(Q(e.state.data.summary.promoted_accounts_total)) + " · 未归档 Plus 无优惠 " + p(Re(e.state.data.summary.unpromoted_count)), 1)]), m("button", {
					type: "button",
					"data-daily-summary-bulk": "",
					disabled: !Be(e.state.data.summary),
					onClick: a[5] ||= (t) => Ve(e.state.data.summary, `${T.value.from}..${T.value.to} 无优惠账号查套餐`)
				}, " 新建区间查套餐批量（" + p(Re(e.state.data.summary.unpromoted_count)) + "） ", 9, be)])) : c("", !0)
			], 64)) : c("", !0)
		]));
	}
}), [["__scopeId", "data-v-ca170564"]]), Se = { class: "ov-section-head" }, Ce = { class: "ov-section-actions" }, Z = { class: "ov-updated" }, we = ["disabled"], Te = {
	key: 0,
	class: "ov-error",
	role: "alert"
}, Ee = {
	key: 1,
	class: "ov-alerts",
	"aria-label": "需要关注"
}, De = ["onClick"], Oe = {
	key: 2,
	class: "ov-skeleton",
	"aria-label": "正在读取总览"
}, ke = {
	key: 3,
	class: "ov-pulse",
	"aria-label": "服务脉搏"
}, Ae = ["title", "onClick"], je = { class: "ov-pulse-top" }, Me = { class: "ov-pulse-badge" }, Ne = {
	key: 4,
	class: "ov-grid"
}, Pe = {
	class: "ov-card ov-card--email",
	"data-overview-card": "email",
	style: {
		"--accent": "#1f9d75",
		"--accent-soft": "#e7f6f0"
	}
}, Fe = { class: "ov-card-head" }, Ie = { class: "ov-figure" }, Le = { class: "ov-mini-grid ov-mini-grid--3" }, Q = {
	key: 0,
	class: "ov-bars"
}, Re = { class: "ov-bar-label" }, ze = {
	key: 1,
	class: "ov-empty"
}, Be = {
	key: 2,
	class: "ov-foot"
}, Ve = {
	key: 3,
	class: "ov-foot"
}, He = {
	class: "ov-card ov-card--accounts",
	"data-overview-card": "accounts",
	style: {
		"--accent": "#5b5ce2",
		"--accent-soft": "#eeeefe"
	}
}, Ue = { class: "ov-card-head" }, We = { class: "ov-figure" }, Ge = {
	class: "ov-split",
	"aria-hidden": "true"
}, Ke = { class: "ov-legend" }, qe = { class: "ov-mini-grid ov-mini-grid--2" }, Je = { class: "ov-meter" }, Ye = { class: "ov-bar" }, Xe = {
	class: "ov-card ov-card--codex",
	"data-overview-card": "codex",
	style: {
		"--accent": "#377dff",
		"--accent-soft": "#e9f1ff"
	}
}, Ze = { class: "ov-card-head" }, Qe = { class: "ov-figure" }, $e = {
	key: 0,
	class: "ov-chip is-warn"
}, et = { class: "ov-bar-label" }, tt = { class: "ov-bar ov-bar--thick" }, nt = { class: "ov-mini-grid ov-mini-grid--3" }, rt = { class: "ov-foot" }, it = {
	class: "ov-card ov-card--extract",
	"data-overview-card": "extract",
	style: {
		"--accent": "#d97706",
		"--accent-soft": "#fdf3e3"
	}
}, at = { class: "ov-card-head" }, ot = { class: "ov-figure" }, st = {
	key: 0,
	class: "ov-mini-grid ov-mini-grid--3"
}, ct = {
	key: 1,
	class: "ov-empty"
}, lt = { class: "ov-foot" }, ut = {
	class: "ov-card ov-card--plans",
	"data-overview-card": "plans",
	style: {
		"--accent": "#8b5cf6",
		"--accent-soft": "#f3edff"
	}
}, dt = { class: "ov-card-head" }, ft = { class: "ov-figure ov-figure--small" }, pt = { class: "ov-bars" }, mt = { class: "ov-bar-label" }, ht = { class: "ov-bar" }, gt = {
	key: 1,
	class: "ov-empty"
}, _t = {
	class: "ov-card ov-card--proxy",
	"data-overview-card": "proxy",
	style: {
		"--accent": "#0e9aa7",
		"--accent-soft": "#e6f6f7"
	}
}, vt = { class: "ov-card-head" }, yt = { class: "ov-figure" }, bt = { class: "ov-chip" }, xt = {
	key: 0,
	class: "ov-lease-list"
}, St = {
	key: 1,
	class: "ov-empty"
}, Ct = {
	key: 2,
	class: "ov-foot"
}, wt = {
	class: "ov-card ov-card--jobs",
	"data-overview-card": "jobs",
	style: {
		"--accent": "#475569",
		"--accent-soft": "#eef1f5"
	}
}, Tt = { class: "ov-card-head" }, Et = { class: "ov-task-columns" }, Dt = { class: "ov-task-block" }, Ot = { class: "ov-mini-grid ov-mini-grid--3" }, kt = { class: "ov-task-block" }, At = { class: "ov-mini-grid ov-mini-grid--3" }, jt = { class: "is-ok" }, Mt = { class: "is-warn" }, Nt = { class: "is-danger" }, Pt = { class: "ov-task-block ov-task-block--wide" }, Ft = {
	key: 0,
	class: "ov-stack",
	"aria-hidden": "true"
}, It = {
	key: 1,
	class: "ov-stack ov-stack--empty",
	"aria-hidden": "true"
}, Lt = { class: "ov-stack-legend" }, Rt = {
	key: 0,
	class: "ov-stack-empty-text"
}, zt = {
	key: 0,
	class: "ov-foot"
}, Bt = /*#__PURE__*/ x(/* @__PURE__ */ e({
	__name: "DashboardPage",
	props: {
		api: {},
		deps: {}
	},
	setup(e, { expose: n }) {
		let r = e, s = O(r.api, r.deps), { data: h, extract: v, caps: y, daily: x, dailyLoading: w, dailyError: T, dailyUpdatedAt: ee, dailyRequestedRange: E, dailyDisplayedRange: te, dailyScopeCurrent: k, loading: A, error: j, updatedAt: M } = s, N = f(!1);
		a(() => {
			N.value = !0;
		});
		let P = (e) => new Intl.NumberFormat("zh-CN").format(Number(e || 0)), F = (e) => Number(e || 0), I = (e, t) => {
			let n = F(t);
			return n > 0 ? Math.max(0, Math.min(100, Math.round(F(e) / n * 100))) : 0;
		}, ne = (e) => ({
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
		})[e] || e, L = _(() => h.value?.accounts || {}), R = _(() => h.value?.email?.supply || {}), re = _(() => (Array.isArray(R.value?.sources) ? R.value.sources : Array.isArray(h.value?.email?.sources) ? h.value.email.sources : []).filter((e) => e?.kind === "local_pool")), ie = _(() => re.value.filter((e) => F(e.total) > 0 || F(e.available) > 0)), ae = _(() => Math.max(0, re.value.length - ie.value.length)), oe = _(() => R.value?.status === "error" ? "读取失败" : F(R.value?.available)), se = _(() => R.value?.status === "error" ? "—" : P(oe.value)), z = _(() => F(R.value?.total)), ce = _(() => F(R.value?.used)), le = _(() => F(R.value?.failed) + F(R.value?.disabled)), B = _(() => R.value?.status === "error" ? "danger" : z.value > 0 && F(R.value?.available) === 0 ? "warn" : F(R.value?.available) > 0 ? "ok" : "idle"), ue = _(() => R.value?.status === "error" ? "读取失败" : z.value === 0 ? "未配置" : F(R.value?.available) === 0 ? "库存耗尽" : "库存正常"), V = _(() => h.value?.codex || {}), de = _(() => F(V.value.pending) > 0 ? "warn" : F(V.value.total) > 0 ? "ok" : "idle"), H = _(() => Object.entries(L.value?.plans || {}).map(([e, t]) => ({
			key: e,
			label: ne(e),
			count: F(t)
		})).sort((e, t) => t.count - e.count)), fe = _(() => Math.max(1, ...H.value.map((e) => e.count))), pe = _(() => H.value.reduce((e, t) => e + t.count, 0)), U = _(() => h.value?.jobs || {}), me = _(() => y.value?.features?.register?.enabled === !1), W = _(() => ({ ...U.value?.counts || {} })), G = _(() => ({ ...U.value?.today_counts || {} })), K = _(() => F(W.value.pending) + F(W.value.running) + F(W.value.stopping));
		_(() => F(G.value.success) + F(G.value.partial_success) + F(G.value.failed));
		let q = _(() => [
			{
				key: "success",
				label: "成功",
				value: F(W.value.success),
				color: "#1f9d75"
			},
			{
				key: "partial_success",
				label: "部分成功",
				value: F(W.value.partial_success),
				color: "#d99a2b"
			},
			{
				key: "failed",
				label: "失败",
				value: F(W.value.failed),
				color: "#d9534f"
			},
			{
				key: "cancelled",
				label: "停止/取消",
				value: F(W.value.stopped) + F(W.value.cancelled),
				color: "#98a2b3"
			}
		].filter((e) => e.value > 0)), he = _(() => K.value > 0 ? "active" : F(G.value.failed) > 0 ? "warn" : "idle"), J = _(() => h.value?.proxy || {}), Y = _(() => Array.isArray(J.value.leases) ? J.value.leases.slice(0, 3) : []), ge = _(() => Math.max(0, F(J.value.active_leases) - Y.value.length)), _e = _(() => y.value?.proxy?.registration?.enabled === !1), ve = _(() => F(J.value.active_leases) > 0 ? "ok" : "idle"), X = _(() => v.value || {}), ye = _(() => F(X.value.processing) > 0 ? "active" : "idle"), be = _(() => F(X.value.all) === 0 && F(X.value.today_extracted) === 0 && F(X.value.processing) === 0 && F(X.value.awaiting_payment) === 0), Bt = _(() => [
			{
				id: "email",
				label: "邮箱",
				value: se.value,
				badge: R.value?.status === "error" ? "读取失败" : F(R.value?.available) === 0 ? "库存耗尽" : `${se.value} 可用`,
				hint: F(R.value?.available) === 0 ? "库存耗尽" : `邮箱总量 ${P(z.value)}`,
				tone: B.value,
				tab: "outlook"
			},
			{
				id: "accounts",
				label: "账号",
				value: P(L.value.active),
				badge: `${P(L.value.active)} 活跃`,
				hint: `归档 ${P(L.value.archived)}`,
				tone: "ok",
				tab: "accounts"
			},
			{
				id: "codex",
				label: "Codex",
				value: P(V.value.total),
				badge: F(V.value.pending) > 0 ? `待导 ${P(V.value.pending)}` : `${P(V.value.total)} 凭证`,
				hint: `待导出 ${P(V.value.pending)}`,
				tone: de.value,
				tab: "codex"
			},
			{
				id: "plans",
				label: "套餐",
				value: P(H.value.length),
				badge: `${P(H.value.length)} 类`,
				hint: `${P(pe.value)} 个已归类`,
				tone: "ok",
				tab: "accounts"
			},
			{
				id: "extract",
				label: "提炼",
				value: P(X.value.today_extracted),
				badge: F(X.value.processing) > 0 ? `进行 ${P(X.value.processing)}` : `今日 ${P(X.value.today_extracted)}`,
				hint: "今日已提炼",
				tone: ye.value,
				tab: "extract-workbench"
			},
			{
				id: "proxy",
				label: "代理",
				value: P(J.value.active_leases),
				badge: F(J.value.active_leases) > 0 ? `${P(J.value.active_leases)} 出口` : D(J.value.platform),
				hint: D(J.value.platform),
				tone: ve.value,
				tab: "proxy-traffic"
			},
			{
				id: "jobs",
				label: "任务",
				value: P(K.value),
				badge: K.value > 0 ? `运行 ${P(K.value)}` : F(G.value.failed) > 0 ? `异常 ${P(G.value.failed)}` : "空闲",
				hint: `累计 ${P(U.value.total)}`,
				tone: he.value,
				tab: "tasks"
			}
		]), Vt = _(() => {
			let e = [];
			return R.value?.status === "error" ? e.push({
				tone: "danger",
				text: "邮箱池统计读取失败，暂时无法判断可用库存。",
				tab: "outlook",
				label: "检查邮箱池"
			}) : z.value > 0 && F(R.value?.available) === 0 && e.push({
				tone: "warning",
				text: `邮箱池已用完（已用 ${P(ce.value)} / 邮箱总量 ${P(z.value)}），新的注册任务取不到邮箱。`,
				tab: "outlook",
				label: "添加邮箱库存"
			}), e.slice(0, 2);
		}), Ht = _(() => M.value ? `数据更新 ${new Date(M.value).toLocaleTimeString("zh-CN", { hour12: !1 })}` : A.value ? "正在读取…" : "尚未读取"), $ = (e) => r.deps.onNavigate?.(e), Ut = _(() => ({
			data: x.value,
			loading: w.value,
			error: T.value,
			updatedAt: ee.value,
			requestedRange: E.value,
			displayedRange: te.value,
			scopeCurrent: k.value,
			load: s.loadDaily
		}));
		return n({
			load: s.load,
			setVisible: s.setVisible,
			openCustomizer: () => {},
			closeCustomizer: () => {},
			resetLayout: () => {}
		}), (e, n) => (t(), S("div", { class: g(["ov-page", { "is-mounted": N.value }]) }, [
			m("div", Se, [n[11] ||= m("div", { class: "ov-section-title" }, [m("h2", null, "服务脉搏"), m("p", null, "邮箱 · 账号 · Codex · 套餐 · 提炼 · 代理 · 任务")], -1), m("div", Ce, [m("span", Z, [n[9] ||= m("i", { "aria-hidden": "true" }, null, -1), C(p(Ht.value), 1)]), m("button", {
				type: "button",
				class: "ov-refresh ui-refresh-button",
				disabled: b(A),
				onClick: n[0] ||= (e) => b(s).load()
			}, [n[10] ||= m("svg", {
				viewBox: "0 0 24 24",
				"aria-hidden": "true"
			}, [m("path", { d: "M20 11a8 8 0 1 0-2.3 6.7" }), m("path", { d: "M20 4v7h-7" })], -1), C(" " + p(b(A) ? "刷新中" : "刷新"), 1)], 8, we)])]),
			b(j) ? (t(), S("div", Te, [m("div", null, [n[12] ||= m("strong", null, "总览加载失败", -1), m("span", null, p(b(j)), 1)]), m("button", {
				type: "button",
				onClick: n[1] ||= (e) => b(s).load()
			}, "重试")])) : c("", !0),
			Vt.value.length ? (t(), S("section", Ee, [(t(!0), S(u, null, i(Vt.value, (e) => (t(), S("article", {
				key: e.text,
				class: g(["ov-alert", `is-${e.tone}`])
			}, [
				n[13] ||= m("svg", {
					viewBox: "0 0 24 24",
					"aria-hidden": "true"
				}, [
					m("path", { d: "M12 9v4" }),
					m("path", { d: "M12 17h.01" }),
					m("path", { d: "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" })
				], -1),
				m("p", null, p(e.text), 1),
				m("button", {
					type: "button",
					onClick: (t) => $(e.tab)
				}, p(e.label), 9, De)
			], 2))), 128))])) : c("", !0),
			!b(h) && b(A) ? (t(), S("section", Oe, [...n[14] ||= [m("div", { class: "ov-skeleton-pulse" }, null, -1), m("div", { class: "ov-skeleton-grid" }, [
				m("i"),
				m("i"),
				m("i"),
				m("i")
			], -1)]])) : c("", !0),
			b(h) ? (t(), S("nav", ke, [(t(!0), S(u, null, i(Bt.value, (e) => (t(), S("button", {
				key: e.id,
				type: "button",
				class: g(["ov-pulse-item", [`is-${e.tone}`, { "is-zero": e.value === "0" }]]),
				title: `${e.label} · ${e.hint}`,
				onClick: (t) => $(e.tab)
			}, [m("span", je, [n[15] ||= m("i", { "aria-hidden": "true" }, null, -1), C(p(e.label), 1)]), m("span", Me, [m("strong", null, p(e.badge), 1)])], 10, Ae))), 128))])) : c("", !0),
			o(xe, {
				state: Ut.value,
				"on-bulk-plan-create": r.deps.onBulkPlanCreate
			}, null, 8, ["state", "on-bulk-plan-create"]),
			b(h) ? (t(), S("div", Ne, [
				m("article", Pe, [
					m("header", Fe, [n[17] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><rect x=\"3\" y=\"5\" width=\"18\" height=\"14\" rx=\"2\" data-v-aefc1e2e></rect><path d=\"m3 7 9 6 9-6\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>邮箱池</h3><p data-v-aefc1e2e>本地库存与来源</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "email",
						onClick: n[2] ||= (e) => $("outlook")
					}, [...n[16] ||= [C("管理", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", Ie, [
						m("strong", { class: g({ "is-danger": B.value === "warn" }) }, p(se.value), 3),
						n[18] ||= m("span", null, "可用", -1),
						B.value === "ok" ? c("", !0) : (t(), S("em", {
							key: 0,
							class: g(["ov-chip", `is-${B.value}`])
						}, p(ue.value), 3))
					]),
					m("div", Le, [
						m("div", null, [n[19] ||= m("span", null, "邮箱总量", -1), m("strong", null, p(P(z.value)), 1)]),
						m("div", null, [n[20] ||= m("span", null, "已使用", -1), m("strong", null, p(P(ce.value)), 1)]),
						m("div", null, [n[21] ||= m("span", null, "停用 / 失败", -1), m("strong", null, p(P(le.value)), 1)])
					]),
					ie.value.length ? (t(), S("ul", Q, [(t(!0), S(u, null, i(ie.value, (e) => (t(), S("li", { key: e.source }, [m("div", Re, [m("span", null, p(e.label), 1), m("small", null, p(F(e.available) === 0 ? "已用尽" : `可用 ${P(e.available)}`) + " / " + p(P(e.total)), 1)]), m("div", { class: g(["ov-bar", { "is-spent": F(e.available) === 0 && F(e.total) > 0 }]) }, [m("i", { style: d({ width: I(e.available, e.total) + "%" }) }, null, 4)], 2)]))), 128))])) : (t(), S("p", ze, "还没有可统计的邮箱库存。")),
					ae.value ? (t(), S("p", Be, "另有 " + p(ae.value) + " 个来源暂无库存 · 仅统计本地库存", 1)) : (t(), S("p", Ve, "仅统计本地库存，用完后需手动导入"))
				]),
				m("article", He, [
					m("header", Ue, [n[23] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\" data-v-aefc1e2e></path><circle cx=\"9\" cy=\"7\" r=\"4\" data-v-aefc1e2e></circle><path d=\"M22 21v-2a4 4 0 0 0-3-3.9\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>账号</h3><p data-v-aefc1e2e>账号资产</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "accounts",
						onClick: n[3] ||= (e) => $("accounts")
					}, [...n[22] ||= [C("管理", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", We, [m("strong", null, p(P(L.value.active)), 1), n[24] ||= m("span", null, "活跃账号", -1)]),
					m("div", Ge, [m("i", {
						class: "is-active",
						style: d({ width: I(L.value.active, L.value.total) + "%" })
					}, null, 4), m("i", {
						class: "is-idle",
						style: d({ width: I(L.value.archived, L.value.total) + "%" })
					}, null, 4)]),
					m("div", Ke, [m("span", null, [n[25] ||= m("i", { style: { background: "#5b5ce2" } }, null, -1), C("活跃 " + p(P(L.value.active)), 1)]), m("span", null, [n[26] ||= m("i", { style: { background: "#d7dbe5" } }, null, -1), C("归档 " + p(P(L.value.archived)), 1)])]),
					m("div", qe, [m("div", null, [n[27] ||= m("span", null, "账号总数", -1), m("strong", null, p(P(L.value.total)), 1)]), m("div", null, [n[28] ||= m("span", null, "Codex 就绪", -1), m("strong", null, p(P(L.value.codex_ready)), 1)])]),
					m("div", Je, [
						n[29] ||= m("span", null, "Codex 就绪率", -1),
						m("div", Ye, [m("i", { style: d({ width: I(L.value.codex_ready, L.value.active) + "%" }) }, null, 4)]),
						m("strong", null, p(I(L.value.codex_ready, L.value.active)) + "%", 1)
					])
				]),
				m("article", Xe, [
					m("header", Ze, [n[31] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><rect x=\"3\" y=\"11\" width=\"18\" height=\"10\" rx=\"2\" data-v-aefc1e2e></rect><path d=\"M7 11V7a5 5 0 0 1 10 0v4\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>Codex</h3><p data-v-aefc1e2e>授权凭证</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "codex",
						onClick: n[4] ||= (e) => $("codex")
					}, [...n[30] ||= [C("查看", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", Qe, [
						m("strong", null, p(P(V.value.total)), 1),
						n[32] ||= m("span", null, "已导出凭证", -1),
						de.value === "warn" ? (t(), S("em", $e, "待导出")) : c("", !0)
					]),
					m("div", et, [n[33] ||= m("span", null, "导出进度", -1), m("small", null, p(P(V.value.exported)) + " / " + p(P(V.value.total)), 1)]),
					m("div", tt, [m("i", { style: d({ width: I(V.value.exported, V.value.total) + "%" }) }, null, 4)]),
					m("div", nt, [
						m("div", null, [n[34] ||= m("span", null, "已导出", -1), m("strong", null, p(P(V.value.exported)), 1)]),
						m("div", null, [n[35] ||= m("span", null, "待导出", -1), m("strong", null, p(P(V.value.pending)), 1)]),
						m("div", null, [n[36] ||= m("span", null, "账号就绪", -1), m("strong", null, p(P(L.value.codex_ready)), 1)])
					]),
					m("p", rt, "账号 Codex 就绪 " + p(P(L.value.codex_ready)) + " · 覆盖 " + p(I(L.value.codex_ready, L.value.active)) + "% 活跃账号", 1)
				]),
				m("article", it, [
					m("header", at, [n[38] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z\" data-v-aefc1e2e></path><path d=\"M19 15.5 20 18l2.5 1-2.5 1L19 22l-1-2-2.5-1 2.5-1 1-2.5Z\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>提炼</h3><p data-v-aefc1e2e>提链工作台</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "extract",
						onClick: n[5] ||= (e) => $("extract-workbench")
					}, [...n[37] ||= [C("工作台", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", ot, [
						m("strong", null, p(P(X.value.today_extracted)), 1),
						n[39] ||= m("span", null, "今日已提炼", -1),
						m("em", { class: g(["ov-chip", `is-${ye.value}`]) }, p(ye.value === "idle" ? "空闲" : "处理中"), 3)
					]),
					be.value ? c("", !0) : (t(), S("div", st, [
						m("div", null, [n[40] ||= m("span", null, "Plus 已确认", -1), m("strong", null, p(P(X.value.today_plus_confirmed)), 1)]),
						m("div", null, [n[41] ||= m("span", null, "处理中", -1), m("strong", null, p(P(X.value.processing)), 1)]),
						m("div", null, [n[42] ||= m("span", null, "待支付", -1), m("strong", null, p(P(X.value.awaiting_payment)), 1)])
					])),
					be.value ? (t(), S("p", ct, "今日还没有提炼任务，进入工作台即可发起。")) : c("", !0),
					m("p", lt, p(be.value ? "提链工作台空闲" : `累计 ${P(X.value.all)} 个提炼任务`), 1)
				]),
				m("article", ut, [m("header", dt, [n[44] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M12 2 2 7l10 5 10-5-10-5Z\" data-v-aefc1e2e></path><path d=\"m2 12 10 5 10-5\" data-v-aefc1e2e></path><path d=\"m2 17 10 5 10-5\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>套餐</h3><p data-v-aefc1e2e>账号套餐分布</p></div></div>", 1), m("button", {
					type: "button",
					class: "ov-link",
					"data-overview-action": "plans",
					onClick: n[6] ||= (e) => $("accounts")
				}, [...n[43] ||= [C("账号", -1), m("svg", {
					viewBox: "0 0 24 24",
					"aria-hidden": "true"
				}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]), H.value.length ? (t(), S(u, { key: 0 }, [m("div", ft, [m("strong", null, p(P(H.value.length)), 1), m("span", null, "种套餐 · " + p(P(pe.value)) + " 个账号", 1)]), m("ul", pt, [(t(!0), S(u, null, i(H.value, (e) => (t(), S("li", { key: e.key }, [m("div", mt, [m("span", null, p(e.label), 1), m("small", null, p(P(e.count)) + " · " + p(I(e.count, pe.value)) + "%", 1)]), m("div", ht, [m("i", { style: d({ width: Math.max(4, Math.round(e.count / fe.value * 100)) + "%" }) }, null, 4)])]))), 128))])], 64)) : (t(), S("p", gt, "还没有可用的套餐数据。"))]),
				m("article", _t, [
					m("header", vt, [n[46] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><circle cx=\"12\" cy=\"12\" r=\"9\" data-v-aefc1e2e></circle><path d=\"M3 12h18\" data-v-aefc1e2e></path><path d=\"M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3Z\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>代理</h3><p data-v-aefc1e2e>网络出口</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "proxy",
						onClick: n[7] ||= (e) => $("proxy-traffic")
					}, [...n[45] ||= [C("查看", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", yt, [
						m("strong", null, p(P(J.value.active_leases)), 1),
						n[47] ||= m("span", null, "活跃出口", -1),
						m("em", bt, p(b(D)(J.value.platform)), 1)
					]),
					Y.value.length ? (t(), S("ul", xt, [(t(!0), S(u, null, i(Y.value, (e, r) => (t(), S("li", { key: r }, [
						n[48] ||= m("i", { "aria-hidden": "true" }, null, -1),
						m("span", null, p(e.endpoint || e.exit_ip || "活跃出口"), 1),
						m("small", null, p(e.region || e.provider || ""), 1)
					]))), 128))])) : (t(), S("p", St, p(_e.value ? "注册代理未启用，当前没有活跃租约。" : `当前没有活跃的代理租约，新任务会走 ${b(D)(J.value.platform)}。`), 1)),
					Y.value.length ? (t(), S("p", Ct, [C(p(_e.value ? "注册代理未启用，已有租约仍保留" : `代理平台 ${b(D)(J.value.platform)}`), 1), ge.value ? (t(), S(u, { key: 0 }, [C(" · 另有 " + p(ge.value) + " 个活跃出口", 1)], 64)) : c("", !0)])) : c("", !0)
				]),
				m("article", wt, [
					m("header", Tt, [n[50] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M9 5h11\" data-v-aefc1e2e></path><path d=\"M9 12h11\" data-v-aefc1e2e></path><path d=\"M9 19h11\" data-v-aefc1e2e></path><circle cx=\"4\" cy=\"5\" r=\"1\" data-v-aefc1e2e></circle><circle cx=\"4\" cy=\"12\" r=\"1\" data-v-aefc1e2e></circle><circle cx=\"4\" cy=\"19\" r=\"1\" data-v-aefc1e2e></circle></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>任务</h3><p data-v-aefc1e2e>注册流水线与队列</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "jobs",
						onClick: n[8] ||= (e) => $("tasks")
					}, [...n[49] ||= [C("任务中心", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", Et, [
						m("section", Dt, [n[54] ||= m("h4", null, "当前队列", -1), m("div", Ot, [
							m("div", null, [n[51] ||= m("span", null, "运行中", -1), m("strong", null, p(P(W.value.running)), 1)]),
							m("div", null, [n[52] ||= m("span", null, "待处理", -1), m("strong", null, p(P(W.value.pending)), 1)]),
							m("div", null, [n[53] ||= m("span", null, "停止中", -1), m("strong", null, p(P(W.value.stopping)), 1)])
						])]),
						m("section", kt, [m("h4", null, [n[55] ||= C("今日结果 ", -1), m("small", null, p(U.value.today), 1)]), m("div", At, [
							m("div", null, [n[56] ||= m("span", null, "成功", -1), m("strong", jt, p(P(G.value.success)), 1)]),
							m("div", null, [n[57] ||= m("span", null, "部分成功", -1), m("strong", Mt, p(P(G.value.partial_success)), 1)]),
							m("div", null, [n[58] ||= m("span", null, "失败", -1), m("strong", Nt, p(P(G.value.failed)), 1)])
						])]),
						m("section", Pt, [
							m("h4", null, [n[59] ||= C("累计结果 ", -1), m("small", null, p(P(U.value.total)) + " 个任务", 1)]),
							q.value.length ? (t(), S("div", Ft, [(t(!0), S(u, null, i(q.value, (e) => (t(), S("i", {
								key: e.key,
								style: d({
									width: e.value / Math.max(1, U.value.total) * 100 + "%",
									background: e.color
								})
							}, null, 4))), 128))])) : (t(), S("div", It)),
							m("div", Lt, [(t(!0), S(u, null, i(q.value, (e) => (t(), S("span", { key: e.key }, [m("i", { style: d({ background: e.color }) }, null, 4), C(p(e.label) + " " + p(P(e.value)), 1)]))), 128)), q.value.length ? c("", !0) : (t(), S("span", Rt, "暂无累计结果"))])
						])
					]),
					me.value ? (t(), S("p", zt, "注册功能未启用，历史任务仍可查看。")) : c("", !0)
				])
			])) : c("", !0)
		], 2));
	}
}), [["__scopeId", "data-v-aefc1e2e"]]);
// src/api/dashboard.ts
async function Vt(e, t) {
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
function Ht(e = (e, t) => w(e, t), t) {
	let n = (t, n) => e(t, n ? { signal: n } : void 0);
	return {
		dashboard: (e) => n("/api/dashboard", e),
		extractSummary: (e) => n("/api/extract-workbench/summary", e),
		registrationDaily: (e, t, r) => {
			let i = new URLSearchParams();
			e && i.set("date_from", e), t && i.set("date_to", t);
			let a = i.toString() ? `?${i.toString()}` : "";
			return n(`/api/dashboard/registration-daily${a}`, r);
		},
		async capabilities(e) {
			let r = t?.();
			if (!r) return n("/api/capabilities", e);
			let i = await Vt(r, e);
			if (typeof i != "object" || !i || !("ok" in i) || i.ok !== !0) throw new T("能力检查返回无效数据", 200);
			return i;
		}
	};
}
// src/dashboard.ts
function $(e, t = {}) {
	let n = v(Bt, {
		api: t.api || Ht(void 0, t.pendingCapabilities),
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
export { $ as mountDashboard };
