import { C as e, F as t, H as n, K as r, L as i, M as a, S as o, V as s, _ as c, b as l, d as u, dt as d, et as f, ft as p, h as m, j as h, lt as g, m as _, n as v, o as y, st as b, t as x, v as S, x as C } from "./_plugin-vue_export-helper-BSZsFlS8.js";
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
}, P = [
	"data-daily-range-3",
	"data-daily-range-7",
	"data-daily-range-30",
	"aria-pressed",
	"onClick"
], F = ["aria-pressed"], I = {
	key: 0,
	class: "daily-stats-error",
	"data-daily-error": "",
	role: "alert"
}, ne = ["disabled"], L = {
	key: 1,
	class: "daily-stats-stale",
	"data-daily-stale": "",
	role: "status"
}, R = {
	key: 2,
	class: "daily-stats-loading",
	"aria-live": "polite"
}, re = {
	class: "daily-section",
	"aria-labelledby": "daily-total-title"
}, ie = {
	class: "daily-quantity-chart",
	role: "group",
	"aria-label": "每日账号总数柱形图"
}, ae = {
	class: "daily-chart-axis",
	"data-daily-axis": ""
}, oe = { "aria-hidden": "true" }, se = { class: "daily-chart-scroll" }, z = {
	class: "daily-chart-grid",
	"aria-hidden": "true"
}, ce = [
	"data-daily-bar",
	"aria-label",
	"aria-pressed",
	"tabindex",
	"onClick",
	"onFocus",
	"onKeydown"
], le = { "data-daily-account-total": "" }, B = {
	class: "daily-quantity-track",
	"aria-hidden": "true"
}, ue = { class: "daily-date-label" }, V = {
	class: "daily-section",
	"aria-labelledby": "daily-presence-title"
}, de = { class: "daily-presence-list" }, H = ["data-daily-presence"], fe = { class: "daily-presence-date" }, pe = ["aria-label"], U = ["data-presence-segment"], me = { class: "daily-presence-values" }, W = {
	key: 1,
	class: "daily-data-pending"
}, G = {
	key: 1,
	class: "daily-data-pending"
}, he = {
	class: "daily-section",
	"aria-labelledby": "daily-offers-title"
}, ge = {
	key: 0,
	class: "daily-offer-scroll",
	role: "region",
	"aria-label": "各日期优惠种类账号数与占比",
	tabindex: "0"
}, _e = ["data-daily-offer-row"], K = { scope: "row" }, q = ["data-daily-offer-cell"], ve = { class: "daily-offer-numbers" }, ye = {
	class: "daily-offer-track",
	"aria-hidden": "true"
}, be = {
	key: 0,
	class: "daily-offer-stale"
}, J = {
	key: 1,
	class: "daily-data-pending"
}, xe = {
	key: 1,
	class: "daily-data-pending"
}, Se = ["data-daily-row"], Ce = ["disabled"], we = {
	key: 1,
	class: "daily-stats-empty"
}, Te = {
	key: 2,
	class: "daily-stats-summary"
}, Y = ["disabled"], Ee = /*#__PURE__*/ x(/* @__PURE__ */ e({
	__name: "DailyRegistrationStats",
	props: {
		state: {},
		onBulkPlanCreate: { type: Function }
	},
	setup(e) {
		let a = e, o = f("3"), l = f(""), h = f(""), v = f(""), b = `daily-registration-detail-${s()}`, x = _(() => Array.isArray(a.state.data?.rows) ? a.state.data.rows : []), w = _(() => ({
			from: a.state.data?.date_from || x.value[0]?.date || "",
			to: a.state.data?.date_to || x.value[x.value.length - 1]?.date || ""
		})), T = _(() => w.value.from && w.value.to ? `${w.value.from} 至 ${w.value.to}` : "日期范围待返回"), ee = _(() => a.state.data?.cohort_basis_label || "按账号首次入库日期统计"), E = _(() => a.state.updatedAt ? `更新于 ${new Date(a.state.updatedAt).toLocaleString("zh-CN", {
			hour12: !1,
			timeZone: "Asia/Shanghai"
		})}` : a.state.loading ? "正在读取…" : "尚未读取"), te = _(() => a.state.error && a.state.data && a.state.scopeCurrent ? `${a.state.error}，当前成功范围仍可使用。` : a.state.error), D = _(() => x.value.find((e) => e.date === v.value)), O = _(() => x.value.map((e) => ({
			row: e,
			total: X(e.accounts_total)
		}))), Ee = _(() => Math.max(1, Math.ceil(Math.max(0, ...O.value.map((e) => e.total ?? 0)) / 4))), De = _(() => Ee.value * 4), Oe = _(() => [
			4,
			3,
			2,
			1,
			0
		].map((e) => e * Ee.value)), ke = [
			{
				key: "eligible",
				label: "有优惠",
				color: "#5b5ce2"
			},
			{
				key: "none",
				label: "无优惠",
				color: "#a2aabc"
			},
			{
				key: "unknown",
				label: "待确认",
				color: "#dbaf52"
			}
		], Ae = [
			"team",
			"plus",
			"go"
		];
		function je(e, t) {
			let n = (e) => {
				let t = Ae.indexOf(e);
				return t < 0 ? Ae.length : t;
			};
			return n(e.plan) - n(t.plan) || e.label.localeCompare(t.label, "zh-CN") || e.key.localeCompare(t.key);
		}
		let Me = _(() => {
			let e = /* @__PURE__ */ new Map();
			for (let t of x.value) for (let n of Re(t) ?? []) e.has(n.key) || e.set(n.key, n);
			return [...e.values()].sort(je);
		}), Ne = _(() => x.value.some((e) => Re(e) === null)), Pe = _(() => ({
			"--daily-date-count": x.value.length,
			minWidth: `${180 + x.value.length * 138}px`
		}));
		function Fe(e) {
			let t = Number(e);
			return Number.isFinite(t) ? t : 0;
		}
		function X(e) {
			if (e == null) return null;
			let t = Number(e);
			return Number.isFinite(t) ? t : null;
		}
		function Z(e) {
			let t = X(e);
			return t === null ? "—" : new Intl.NumberFormat("zh-CN").format(t);
		}
		function Ie(e, t) {
			let n = X(e.accounts_total);
			if (!n || n < 0 || t < 0) return "—";
			let r = t / n * 100;
			return r > 0 && r < .01 ? "<0.01%" : `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(r)}%`;
		}
		function Le(e, t) {
			let n = X(e.accounts_total);
			return n && n > 0 ? Math.max(0, Math.min(100, t / n * 100)) : 0;
		}
		function Q(e) {
			let t = e.promotion_presence, n = X(e.accounts_total);
			if (!t || n === null || n < 0) return null;
			let r = ke.map((e) => X(t[e.key]));
			return r.some((e) => e === null || e < 0) || r.reduce((e, t) => e + (t ?? 0), 0) !== n ? null : ke.map((e, t) => ({
				...e,
				count: r[t]
			}));
		}
		function Re(e) {
			return Array.isArray(e.offers) ? e.offers.map((e) => ({
				...e,
				count: Math.max(0, Fe(e.count)),
				stale_count: Math.max(0, Fe(e.stale_count))
			})).sort(je) : null;
		}
		function $(e, t) {
			let n = Re(e);
			return n === null ? null : n.find((e) => e.key === t) || {
				key: t,
				plan: "",
				label: "",
				count: 0,
				stale_count: 0
			};
		}
		function ze(e) {
			return `${e.date}，账号总数 ${Z(e.accounts_total)}，点击选择日期`;
		}
		function Be(e) {
			v.value = e;
		}
		function Ve(e, t) {
			let n = t;
			if (e.key === "ArrowRight") n = Math.min(x.value.length - 1, t + 1);
			else if (e.key === "ArrowLeft") n = Math.max(0, t - 1);
			else if (e.key === "Home") n = 0;
			else if (e.key === "End") n = x.value.length - 1;
			else return;
			e.preventDefault();
			let r = x.value[n];
			if (!r) return;
			Be(r.date);
			let i = e.currentTarget.parentElement?.querySelectorAll("[data-daily-bar]");
			i?.[n]?.focus({ preventScroll: !0 }), i?.[n]?.scrollIntoView?.({
				block: "nearest",
				inline: "nearest"
			});
		}
		function He(e) {
			return X(e.unpromoted_count);
		}
		function Ue(e) {
			return X(e) === null ? "待查" : Z(e);
		}
		function We(e) {
			return a.state.scopeCurrent && He(e) !== null && He(e) > 0 && !!e.query;
		}
		function Ge(e, t) {
			We(e) && e.query && a.onBulkPlanCreate?.({
				name: t,
				query: e.query
			});
		}
		function Ke(e, t) {
			let n = /* @__PURE__ */ new Date(`${e}T00:00:00Z`);
			return n.setUTCDate(n.getUTCDate() + t), n.toISOString().slice(0, 10);
		}
		function qe() {
			let e = new Intl.DateTimeFormat("en-US", {
				timeZone: "Asia/Shanghai",
				year: "numeric",
				month: "2-digit",
				day: "2-digit"
			}).formatToParts(/* @__PURE__ */ new Date()), t = Object.fromEntries(e.filter((e) => e.type !== "literal").map((e) => [e.type, e.value]));
			return `${t.year}-${t.month}-${t.day}`;
		}
		function Je(e) {
			o.value = e;
			let t = qe();
			a.state.load(Ke(t, -(Number(e) - 1)), t);
		}
		function Ye() {
			o.value = "custom", l.value = a.state.displayedRange?.from || w.value.from, h.value = a.state.displayedRange?.to || w.value.to;
		}
		function Xe() {
			o.value === "custom" && l.value && h.value && l.value <= h.value && a.state.load(l.value, h.value);
		}
		return n(x, (e) => {
			e.some((e) => e.date === v.value) || (v.value = e[0]?.date || "");
		}, { immediate: !0 }), (n, a) => (t(), S("section", k, [
			m("header", A, [m("div", null, [a[5] ||= m("h2", { id: "daily-registration-title" }, "每日账号注册与优惠", -1), m("p", null, "北京时间 · " + p(ee.value) + " · 包含归档账号", 1)]), m("div", j, [m("span", M, p(T.value), 1), m("span", null, p(E.value), 1)])]),
			m("div", N, [
				(t(), S(u, null, i([
					"3",
					"7",
					"30"
				], (e) => m("button", {
					key: e,
					type: "button",
					"data-daily-range-3": e === "3" ? "" : void 0,
					"data-daily-range-7": e === "7" ? "" : void 0,
					"data-daily-range-30": e === "30" ? "" : void 0,
					class: g({ active: o.value === e }),
					"aria-pressed": o.value === e,
					onClick: (t) => Je(e)
				}, "近 " + p(e) + " 天", 11, P)), 64)),
				m("button", {
					type: "button",
					"data-daily-range-custom": "",
					class: g({ active: o.value === "custom" }),
					"aria-pressed": o.value === "custom",
					onClick: Ye
				}, "自定义", 10, F),
				o.value === "custom" ? (t(), S(u, { key: 0 }, [m("label", null, [a[6] ||= C("开始日期", -1), r(m("input", {
					"onUpdate:modelValue": a[0] ||= (e) => l.value = e,
					"aria-label": "开始日期",
					type: "date",
					onChange: Xe
				}, null, 544), [[y, l.value]])]), m("label", null, [a[7] ||= C("结束日期", -1), r(m("input", {
					"onUpdate:modelValue": a[1] ||= (e) => h.value = e,
					"aria-label": "结束日期",
					type: "date",
					onChange: Xe
				}, null, 544), [[y, h.value]])])], 64)) : c("", !0)
			]),
			e.state.error ? (t(), S("div", I, [m("span", null, p(te.value), 1), m("button", {
				type: "button",
				"data-daily-retry": "",
				disabled: e.state.loading,
				onClick: a[2] ||= (t) => e.state.load()
			}, "重试", 8, ne)])) : c("", !0),
			e.state.data && !e.state.scopeCurrent ? (t(), S("div", L, p(e.state.loading ? "正在读取新日期范围，当前仍显示上一成功范围；完成前不能新建查套餐批量。" : "新日期范围读取失败，当前仍显示上一成功范围；请重试后再新建查套餐批量。"), 1)) : c("", !0),
			e.state.loading && !e.state.data ? (t(), S("div", R, "正在读取每日账号与优惠统计…")) : e.state.data ? (t(), S(u, { key: 3 }, [x.value.length ? (t(), S(u, { key: 0 }, [
				m("section", re, [a[9] ||= m("div", { class: "daily-section-heading" }, [m("h3", { id: "daily-total-title" }, "每日账号总数"), m("p", null, "每个账号只归属首次入库的一天")], -1), m("div", ie, [m("div", ae, [a[8] ||= m("span", null, "账号数", -1), m("div", oe, [(t(!0), S(u, null, i(Oe.value, (e) => (t(), S("span", {
					key: e,
					"data-daily-axis-tick": ""
				}, p(Z(e)), 1))), 128))])]), m("div", se, [m("div", {
					class: "daily-quantity-plot",
					style: d({
						gridTemplateColumns: `repeat(${x.value.length},minmax(76px,1fr))`,
						minWidth: `${x.value.length * 80}px`
					})
				}, [m("div", z, [(t(!0), S(u, null, i(Oe.value, (e) => (t(), S("i", { key: e }))), 128))]), (t(!0), S(u, null, i(O.value, (e, n) => (t(), S("button", {
					key: e.row.date,
					type: "button",
					class: g(["daily-bar-column", { selected: e.row.date === v.value }]),
					"data-daily-bar": e.row.date,
					"aria-label": ze(e.row),
					"aria-pressed": e.row.date === v.value,
					"aria-controls": b,
					tabindex: e.row.date === v.value ? 0 : -1,
					onClick: (t) => Be(e.row.date),
					onFocus: (t) => Be(e.row.date),
					onKeydown: (e) => Ve(e, n)
				}, [
					m("strong", le, p(Z(e.total)), 1),
					m("span", B, [m("i", {
						"data-daily-quantity": "",
						style: d({ height: `${(e.total ?? 0) / De.value * 100}%` })
					}, null, 4)]),
					m("span", ue, p(e.row.date.slice(5)), 1)
				], 42, ce))), 128))], 4)])])]),
				m("section", V, [a[10] ||= m("div", { class: "daily-section-heading" }, [m("h3", { id: "daily-presence-title" }, "每日有无优惠占比"), m("p", null, "按账号去重；未查询或结果不完整的账号列为待确认")], -1), m("div", de, [(t(!0), S(u, null, i(x.value, (e) => (t(), S("article", {
					key: e.date,
					class: "daily-presence-row",
					"data-daily-presence": e.date
				}, [m("div", fe, [m("strong", null, p(e.date), 1), m("span", null, p(Z(e.accounts_total)) + " 个账号", 1)]), Q(e) ? (t(), S(u, { key: 0 }, [e.accounts_total > 0 ? (t(), S(u, { key: 0 }, [m("div", {
					class: "daily-presence-track",
					role: "img",
					"aria-label": Q(e).map((t) => `${t.label} ${Z(t.count)}个，${Ie(e, t.count)}`).join("，")
				}, [(t(!0), S(u, null, i(Q(e).filter((e) => e.count > 0), (n) => (t(), S("i", {
					key: n.key,
					"data-presence-segment": n.key,
					style: d({
						width: `${Le(e, n.count)}%`,
						backgroundColor: n.color
					})
				}, null, 12, U))), 128))], 8, pe), m("div", me, [(t(!0), S(u, null, i(Q(e), (n) => (t(), S("span", { key: n.key }, [
					m("i", {
						style: d({ backgroundColor: n.color }),
						"aria-hidden": "true"
					}, null, 4),
					C(p(n.label) + " " + p(Z(n.count)) + " 个 · ", 1),
					m("strong", null, p(Ie(e, n.count)), 1)
				]))), 128))])], 64)) : (t(), S("p", W, "暂无账号 · 占比 —"))], 64)) : (t(), S("p", G, "有无优惠数据待查"))], 8, H))), 128))])]),
				m("section", he, [
					a[12] ||= m("div", { class: "daily-section-heading" }, [m("h3", { id: "daily-offers-title" }, "每日优惠种类占比"), m("p", null, "每项占比均以当天账号总数为分母；同一账号可有多种优惠，各项不相加")], -1),
					Me.value.length ? (t(), S("div", ge, [m("table", {
						class: "daily-offer-table",
						style: d(Pe.value)
					}, [m("thead", null, [m("tr", null, [a[11] ||= m("th", { scope: "col" }, "优惠种类", -1), (t(!0), S(u, null, i(x.value, (e) => (t(), S("th", {
						key: e.date,
						scope: "col"
					}, [C(p(e.date), 1), m("small", null, p(Z(e.accounts_total)) + " 个账号", 1)]))), 128))])]), m("tbody", null, [(t(!0), S(u, null, i(Me.value, (e) => (t(), S("tr", {
						key: e.key,
						"data-daily-offer-row": e.key
					}, [m("th", K, p(e.label), 1), (t(!0), S(u, null, i(x.value, (n) => (t(), S("td", {
						key: n.date,
						"data-daily-offer-cell": `${e.key}:${n.date}`
					}, [$(n, e.key) ? (t(), S(u, { key: 0 }, [
						m("div", ve, [m("strong", null, p(Ie(n, $(n, e.key).count)), 1), m("span", null, p(Z($(n, e.key).count)) + " 个", 1)]),
						m("div", ye, [m("i", {
							"data-daily-offer-fill": "",
							style: d({ width: `${Le(n, $(n, e.key).count)}%` })
						}, null, 4)]),
						$(n, e.key).stale_count > 0 ? (t(), S("small", be, p(Z($(n, e.key).stale_count)) + " 个待复查", 1)) : c("", !0)
					], 64)) : (t(), S("span", J, "待查"))], 8, q))), 128))], 8, _e))), 128))])], 4)])) : (t(), S("p", xe, p(Ne.value ? "优惠种类数据待查" : "所选日期暂无已确认优惠记录。"), 1)),
					a[13] ||= m("p", { class: "daily-snapshot-note" }, "优惠采用最近查询结果，并非注册当日的历史优惠；历史优惠待复查后才计入已确认优惠。", -1)
				]),
				D.value ? (t(), S("div", {
					key: 0,
					id: b,
					class: "daily-selected-action",
					"aria-live": "polite",
					"aria-atomic": "true",
					"data-daily-row": D.value.date
				}, [m("div", null, [m("strong", null, p(D.value.date), 1), m("span", null, "Plus 无优惠账号查套餐 · 未归档 " + p(Ue(D.value.unpromoted_count)) + " 个", 1)]), m("button", {
					type: "button",
					"data-daily-bulk": "",
					disabled: !We(D.value),
					onClick: a[3] ||= (e) => Ge(D.value, `${D.value.date} 无优惠账号查套餐`)
				}, "新建查套餐批量（" + p(Ue(D.value.unpromoted_count)) + "）", 9, Ce)], 8, Se)) : c("", !0)
			], 64)) : (t(), S("p", we, "所选日期暂无账号统计。")), e.state.data.summary ? (t(), S("div", Te, [m("div", null, [a[14] ||= m("strong", null, "区间汇总", -1), m("span", null, "账号总数 " + p(Z(e.state.data.summary.accounts_total)) + " · 包含归档账号", 1)]), m("button", {
				type: "button",
				"data-daily-summary-bulk": "",
				disabled: !We(e.state.data.summary),
				onClick: a[4] ||= (t) => Ge(e.state.data.summary, `${w.value.from}..${w.value.to} 无优惠账号查套餐`)
			}, "新建区间查套餐批量（" + p(Ue(e.state.data.summary.unpromoted_count)) + "）", 9, Y)])) : c("", !0)], 64)) : c("", !0)
		]));
	}
}), [["__scopeId", "data-v-471eaa20"]]), De = { class: "ov-section-head" }, Oe = { class: "ov-section-actions" }, ke = { class: "ov-updated" }, Ae = ["disabled"], je = {
	key: 0,
	class: "ov-error",
	role: "alert"
}, Me = {
	key: 1,
	class: "ov-alerts",
	"aria-label": "需要关注"
}, Ne = ["onClick"], Pe = {
	key: 2,
	class: "ov-skeleton",
	"aria-label": "正在读取总览"
}, Fe = {
	key: 3,
	class: "ov-pulse",
	"aria-label": "服务脉搏"
}, X = ["title", "onClick"], Z = { class: "ov-pulse-top" }, Ie = { class: "ov-pulse-badge" }, Le = {
	key: 4,
	class: "ov-grid"
}, Q = {
	class: "ov-card ov-card--email",
	"data-overview-card": "email",
	style: {
		"--accent": "#1f9d75",
		"--accent-soft": "#e7f6f0"
	}
}, Re = { class: "ov-card-head" }, $ = { class: "ov-figure" }, ze = { class: "ov-mini-grid ov-mini-grid--3" }, Be = {
	key: 0,
	class: "ov-bars"
}, Ve = { class: "ov-bar-label" }, He = {
	key: 1,
	class: "ov-empty"
}, Ue = {
	key: 2,
	class: "ov-foot"
}, We = {
	key: 3,
	class: "ov-foot"
}, Ge = {
	class: "ov-card ov-card--accounts",
	"data-overview-card": "accounts",
	style: {
		"--accent": "#5b5ce2",
		"--accent-soft": "#eeeefe"
	}
}, Ke = { class: "ov-card-head" }, qe = { class: "ov-figure" }, Je = {
	class: "ov-split",
	"aria-hidden": "true"
}, Ye = { class: "ov-legend" }, Xe = { class: "ov-mini-grid ov-mini-grid--2" }, Ze = { class: "ov-meter" }, Qe = { class: "ov-bar" }, $e = {
	class: "ov-card ov-card--codex",
	"data-overview-card": "codex",
	style: {
		"--accent": "#377dff",
		"--accent-soft": "#e9f1ff"
	}
}, et = { class: "ov-card-head" }, tt = { class: "ov-figure" }, nt = {
	key: 0,
	class: "ov-chip is-warn"
}, rt = { class: "ov-bar-label" }, it = { class: "ov-bar ov-bar--thick" }, at = { class: "ov-mini-grid ov-mini-grid--3" }, ot = { class: "ov-foot" }, st = {
	class: "ov-card ov-card--extract",
	"data-overview-card": "extract",
	style: {
		"--accent": "#d97706",
		"--accent-soft": "#fdf3e3"
	}
}, ct = { class: "ov-card-head" }, lt = { class: "ov-figure" }, ut = {
	key: 0,
	class: "ov-mini-grid ov-mini-grid--3"
}, dt = {
	key: 1,
	class: "ov-empty"
}, ft = { class: "ov-foot" }, pt = {
	class: "ov-card ov-card--plans",
	"data-overview-card": "plans",
	style: {
		"--accent": "#8b5cf6",
		"--accent-soft": "#f3edff"
	}
}, mt = { class: "ov-card-head" }, ht = { class: "ov-figure ov-figure--small" }, gt = { class: "ov-bars" }, _t = { class: "ov-bar-label" }, vt = { class: "ov-bar" }, yt = {
	key: 1,
	class: "ov-empty"
}, bt = {
	class: "ov-card ov-card--proxy",
	"data-overview-card": "proxy",
	style: {
		"--accent": "#0e9aa7",
		"--accent-soft": "#e6f6f7"
	}
}, xt = { class: "ov-card-head" }, St = { class: "ov-figure" }, Ct = { class: "ov-chip" }, wt = {
	key: 0,
	class: "ov-lease-list"
}, Tt = {
	key: 1,
	class: "ov-empty"
}, Et = {
	key: 2,
	class: "ov-foot"
}, Dt = {
	class: "ov-card ov-card--jobs",
	"data-overview-card": "jobs",
	style: {
		"--accent": "#475569",
		"--accent-soft": "#eef1f5"
	}
}, Ot = { class: "ov-card-head" }, kt = { class: "ov-task-columns" }, At = { class: "ov-task-block" }, jt = { class: "ov-mini-grid ov-mini-grid--3" }, Mt = { class: "ov-task-block" }, Nt = { class: "ov-mini-grid ov-mini-grid--3" }, Pt = { class: "is-ok" }, Ft = { class: "is-warn" }, It = { class: "is-danger" }, Lt = { class: "ov-task-block ov-task-block--wide" }, Rt = {
	key: 0,
	class: "ov-stack",
	"aria-hidden": "true"
}, zt = {
	key: 1,
	class: "ov-stack ov-stack--empty",
	"aria-hidden": "true"
}, Bt = { class: "ov-stack-legend" }, Vt = {
	key: 0,
	class: "ov-stack-empty-text"
}, Ht = {
	key: 0,
	class: "ov-foot"
}, Ut = /*#__PURE__*/ x(/* @__PURE__ */ e({
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
		})).sort((e, t) => t.count - e.count)), fe = _(() => Math.max(1, ...H.value.map((e) => e.count))), pe = _(() => H.value.reduce((e, t) => e + t.count, 0)), U = _(() => h.value?.jobs || {}), me = _(() => y.value?.features?.register?.enabled === !1), W = _(() => ({ ...U.value?.counts || {} })), G = _(() => ({ ...U.value?.today_counts || {} })), he = _(() => F(W.value.pending) + F(W.value.running) + F(W.value.stopping));
		_(() => F(G.value.success) + F(G.value.partial_success) + F(G.value.failed));
		let ge = _(() => [
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
		].filter((e) => e.value > 0)), _e = _(() => he.value > 0 ? "active" : F(G.value.failed) > 0 ? "warn" : "idle"), K = _(() => h.value?.proxy || {}), q = _(() => Array.isArray(K.value.leases) ? K.value.leases.slice(0, 3) : []), ve = _(() => Math.max(0, F(K.value.active_leases) - q.value.length)), ye = _(() => y.value?.proxy?.registration?.enabled === !1), be = _(() => F(K.value.active_leases) > 0 ? "ok" : "idle"), J = _(() => v.value || {}), xe = _(() => F(J.value.processing) > 0 ? "active" : "idle"), Se = _(() => F(J.value.all) === 0 && F(J.value.today_extracted) === 0 && F(J.value.processing) === 0 && F(J.value.awaiting_payment) === 0), Ce = _(() => [
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
				value: P(J.value.today_extracted),
				badge: F(J.value.processing) > 0 ? `进行 ${P(J.value.processing)}` : `今日 ${P(J.value.today_extracted)}`,
				hint: "今日已提炼",
				tone: xe.value,
				tab: "extract-workbench"
			},
			{
				id: "proxy",
				label: "代理",
				value: P(K.value.active_leases),
				badge: F(K.value.active_leases) > 0 ? `${P(K.value.active_leases)} 出口` : D(K.value.platform),
				hint: D(K.value.platform),
				tone: be.value,
				tab: "proxy-traffic"
			},
			{
				id: "jobs",
				label: "任务",
				value: P(he.value),
				badge: he.value > 0 ? `运行 ${P(he.value)}` : F(G.value.failed) > 0 ? `异常 ${P(G.value.failed)}` : "空闲",
				hint: `累计 ${P(U.value.total)}`,
				tone: _e.value,
				tab: "tasks"
			}
		]), we = _(() => {
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
		}), Te = _(() => M.value ? `数据更新 ${new Date(M.value).toLocaleTimeString("zh-CN", { hour12: !1 })}` : A.value ? "正在读取…" : "尚未读取"), Y = (e) => r.deps.onNavigate?.(e), Ut = _(() => ({
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
			m("div", De, [n[11] ||= m("div", { class: "ov-section-title" }, [m("h2", null, "服务脉搏"), m("p", null, "邮箱 · 账号 · Codex · 套餐 · 提炼 · 代理 · 任务")], -1), m("div", Oe, [m("span", ke, [n[9] ||= m("i", { "aria-hidden": "true" }, null, -1), C(p(Te.value), 1)]), m("button", {
				type: "button",
				class: "ov-refresh ui-refresh-button",
				disabled: b(A),
				onClick: n[0] ||= (e) => b(s).load()
			}, [n[10] ||= m("svg", {
				viewBox: "0 0 24 24",
				"aria-hidden": "true"
			}, [m("path", { d: "M20 11a8 8 0 1 0-2.3 6.7" }), m("path", { d: "M20 4v7h-7" })], -1), C(" " + p(b(A) ? "刷新中" : "刷新"), 1)], 8, Ae)])]),
			b(j) ? (t(), S("div", je, [m("div", null, [n[12] ||= m("strong", null, "总览加载失败", -1), m("span", null, p(b(j)), 1)]), m("button", {
				type: "button",
				onClick: n[1] ||= (e) => b(s).load()
			}, "重试")])) : c("", !0),
			we.value.length ? (t(), S("section", Me, [(t(!0), S(u, null, i(we.value, (e) => (t(), S("article", {
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
					onClick: (t) => Y(e.tab)
				}, p(e.label), 9, Ne)
			], 2))), 128))])) : c("", !0),
			!b(h) && b(A) ? (t(), S("section", Pe, [...n[14] ||= [m("div", { class: "ov-skeleton-pulse" }, null, -1), m("div", { class: "ov-skeleton-grid" }, [
				m("i"),
				m("i"),
				m("i"),
				m("i")
			], -1)]])) : c("", !0),
			b(h) ? (t(), S("nav", Fe, [(t(!0), S(u, null, i(Ce.value, (e) => (t(), S("button", {
				key: e.id,
				type: "button",
				class: g(["ov-pulse-item", [`is-${e.tone}`, { "is-zero": e.value === "0" }]]),
				title: `${e.label} · ${e.hint}`,
				onClick: (t) => Y(e.tab)
			}, [m("span", Z, [n[15] ||= m("i", { "aria-hidden": "true" }, null, -1), C(p(e.label), 1)]), m("span", Ie, [m("strong", null, p(e.badge), 1)])], 10, X))), 128))])) : c("", !0),
			o(Ee, {
				state: Ut.value,
				"on-bulk-plan-create": r.deps.onBulkPlanCreate
			}, null, 8, ["state", "on-bulk-plan-create"]),
			b(h) ? (t(), S("div", Le, [
				m("article", Q, [
					m("header", Re, [n[17] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><rect x=\"3\" y=\"5\" width=\"18\" height=\"14\" rx=\"2\" data-v-aefc1e2e></rect><path d=\"m3 7 9 6 9-6\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>邮箱池</h3><p data-v-aefc1e2e>本地库存与来源</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "email",
						onClick: n[2] ||= (e) => Y("outlook")
					}, [...n[16] ||= [C("管理", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", $, [
						m("strong", { class: g({ "is-danger": B.value === "warn" }) }, p(se.value), 3),
						n[18] ||= m("span", null, "可用", -1),
						B.value === "ok" ? c("", !0) : (t(), S("em", {
							key: 0,
							class: g(["ov-chip", `is-${B.value}`])
						}, p(ue.value), 3))
					]),
					m("div", ze, [
						m("div", null, [n[19] ||= m("span", null, "邮箱总量", -1), m("strong", null, p(P(z.value)), 1)]),
						m("div", null, [n[20] ||= m("span", null, "已使用", -1), m("strong", null, p(P(ce.value)), 1)]),
						m("div", null, [n[21] ||= m("span", null, "停用 / 失败", -1), m("strong", null, p(P(le.value)), 1)])
					]),
					ie.value.length ? (t(), S("ul", Be, [(t(!0), S(u, null, i(ie.value, (e) => (t(), S("li", { key: e.source }, [m("div", Ve, [m("span", null, p(e.label), 1), m("small", null, p(F(e.available) === 0 ? "已用尽" : `可用 ${P(e.available)}`) + " / " + p(P(e.total)), 1)]), m("div", { class: g(["ov-bar", { "is-spent": F(e.available) === 0 && F(e.total) > 0 }]) }, [m("i", { style: d({ width: I(e.available, e.total) + "%" }) }, null, 4)], 2)]))), 128))])) : (t(), S("p", He, "还没有可统计的邮箱库存。")),
					ae.value ? (t(), S("p", Ue, "另有 " + p(ae.value) + " 个来源暂无库存 · 仅统计本地库存", 1)) : (t(), S("p", We, "仅统计本地库存，用完后需手动导入"))
				]),
				m("article", Ge, [
					m("header", Ke, [n[23] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\" data-v-aefc1e2e></path><circle cx=\"9\" cy=\"7\" r=\"4\" data-v-aefc1e2e></circle><path d=\"M22 21v-2a4 4 0 0 0-3-3.9\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>账号</h3><p data-v-aefc1e2e>账号资产</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "accounts",
						onClick: n[3] ||= (e) => Y("accounts")
					}, [...n[22] ||= [C("管理", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", qe, [m("strong", null, p(P(L.value.active)), 1), n[24] ||= m("span", null, "活跃账号", -1)]),
					m("div", Je, [m("i", {
						class: "is-active",
						style: d({ width: I(L.value.active, L.value.total) + "%" })
					}, null, 4), m("i", {
						class: "is-idle",
						style: d({ width: I(L.value.archived, L.value.total) + "%" })
					}, null, 4)]),
					m("div", Ye, [m("span", null, [n[25] ||= m("i", { style: { background: "#5b5ce2" } }, null, -1), C("活跃 " + p(P(L.value.active)), 1)]), m("span", null, [n[26] ||= m("i", { style: { background: "#d7dbe5" } }, null, -1), C("归档 " + p(P(L.value.archived)), 1)])]),
					m("div", Xe, [m("div", null, [n[27] ||= m("span", null, "账号总数", -1), m("strong", null, p(P(L.value.total)), 1)]), m("div", null, [n[28] ||= m("span", null, "Codex 就绪", -1), m("strong", null, p(P(L.value.codex_ready)), 1)])]),
					m("div", Ze, [
						n[29] ||= m("span", null, "Codex 就绪率", -1),
						m("div", Qe, [m("i", { style: d({ width: I(L.value.codex_ready, L.value.active) + "%" }) }, null, 4)]),
						m("strong", null, p(I(L.value.codex_ready, L.value.active)) + "%", 1)
					])
				]),
				m("article", $e, [
					m("header", et, [n[31] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><rect x=\"3\" y=\"11\" width=\"18\" height=\"10\" rx=\"2\" data-v-aefc1e2e></rect><path d=\"M7 11V7a5 5 0 0 1 10 0v4\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>Codex</h3><p data-v-aefc1e2e>授权凭证</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "codex",
						onClick: n[4] ||= (e) => Y("codex")
					}, [...n[30] ||= [C("查看", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", tt, [
						m("strong", null, p(P(V.value.total)), 1),
						n[32] ||= m("span", null, "已导出凭证", -1),
						de.value === "warn" ? (t(), S("em", nt, "待导出")) : c("", !0)
					]),
					m("div", rt, [n[33] ||= m("span", null, "导出进度", -1), m("small", null, p(P(V.value.exported)) + " / " + p(P(V.value.total)), 1)]),
					m("div", it, [m("i", { style: d({ width: I(V.value.exported, V.value.total) + "%" }) }, null, 4)]),
					m("div", at, [
						m("div", null, [n[34] ||= m("span", null, "已导出", -1), m("strong", null, p(P(V.value.exported)), 1)]),
						m("div", null, [n[35] ||= m("span", null, "待导出", -1), m("strong", null, p(P(V.value.pending)), 1)]),
						m("div", null, [n[36] ||= m("span", null, "账号就绪", -1), m("strong", null, p(P(L.value.codex_ready)), 1)])
					]),
					m("p", ot, "账号 Codex 就绪 " + p(P(L.value.codex_ready)) + " · 覆盖 " + p(I(L.value.codex_ready, L.value.active)) + "% 活跃账号", 1)
				]),
				m("article", st, [
					m("header", ct, [n[38] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z\" data-v-aefc1e2e></path><path d=\"M19 15.5 20 18l2.5 1-2.5 1L19 22l-1-2-2.5-1 2.5-1 1-2.5Z\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>提炼</h3><p data-v-aefc1e2e>提链工作台</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "extract",
						onClick: n[5] ||= (e) => Y("extract-workbench")
					}, [...n[37] ||= [C("工作台", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", lt, [
						m("strong", null, p(P(J.value.today_extracted)), 1),
						n[39] ||= m("span", null, "今日已提炼", -1),
						m("em", { class: g(["ov-chip", `is-${xe.value}`]) }, p(xe.value === "idle" ? "空闲" : "处理中"), 3)
					]),
					Se.value ? c("", !0) : (t(), S("div", ut, [
						m("div", null, [n[40] ||= m("span", null, "Plus 已确认", -1), m("strong", null, p(P(J.value.today_plus_confirmed)), 1)]),
						m("div", null, [n[41] ||= m("span", null, "处理中", -1), m("strong", null, p(P(J.value.processing)), 1)]),
						m("div", null, [n[42] ||= m("span", null, "待支付", -1), m("strong", null, p(P(J.value.awaiting_payment)), 1)])
					])),
					Se.value ? (t(), S("p", dt, "今日还没有提炼任务，进入工作台即可发起。")) : c("", !0),
					m("p", ft, p(Se.value ? "提链工作台空闲" : `累计 ${P(J.value.all)} 个提炼任务`), 1)
				]),
				m("article", pt, [m("header", mt, [n[44] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M12 2 2 7l10 5 10-5-10-5Z\" data-v-aefc1e2e></path><path d=\"m2 12 10 5 10-5\" data-v-aefc1e2e></path><path d=\"m2 17 10 5 10-5\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>套餐</h3><p data-v-aefc1e2e>账号套餐分布</p></div></div>", 1), m("button", {
					type: "button",
					class: "ov-link",
					"data-overview-action": "plans",
					onClick: n[6] ||= (e) => Y("accounts")
				}, [...n[43] ||= [C("账号", -1), m("svg", {
					viewBox: "0 0 24 24",
					"aria-hidden": "true"
				}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]), H.value.length ? (t(), S(u, { key: 0 }, [m("div", ht, [m("strong", null, p(P(H.value.length)), 1), m("span", null, "种套餐 · " + p(P(pe.value)) + " 个账号", 1)]), m("ul", gt, [(t(!0), S(u, null, i(H.value, (e) => (t(), S("li", { key: e.key }, [m("div", _t, [m("span", null, p(e.label), 1), m("small", null, p(P(e.count)) + " · " + p(I(e.count, pe.value)) + "%", 1)]), m("div", vt, [m("i", { style: d({ width: Math.max(4, Math.round(e.count / fe.value * 100)) + "%" }) }, null, 4)])]))), 128))])], 64)) : (t(), S("p", yt, "还没有可用的套餐数据。"))]),
				m("article", bt, [
					m("header", xt, [n[46] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><circle cx=\"12\" cy=\"12\" r=\"9\" data-v-aefc1e2e></circle><path d=\"M3 12h18\" data-v-aefc1e2e></path><path d=\"M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3Z\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>代理</h3><p data-v-aefc1e2e>网络出口</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "proxy",
						onClick: n[7] ||= (e) => Y("proxy-traffic")
					}, [...n[45] ||= [C("查看", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", St, [
						m("strong", null, p(P(K.value.active_leases)), 1),
						n[47] ||= m("span", null, "活跃出口", -1),
						m("em", Ct, p(b(D)(K.value.platform)), 1)
					]),
					q.value.length ? (t(), S("ul", wt, [(t(!0), S(u, null, i(q.value, (e, r) => (t(), S("li", { key: r }, [
						n[48] ||= m("i", { "aria-hidden": "true" }, null, -1),
						m("span", null, p(e.endpoint || e.exit_ip || "活跃出口"), 1),
						m("small", null, p(e.region || e.provider || ""), 1)
					]))), 128))])) : (t(), S("p", Tt, p(ye.value ? "注册代理未启用，当前没有活跃租约。" : `当前没有活跃的代理租约，新任务会走 ${b(D)(K.value.platform)}。`), 1)),
					q.value.length ? (t(), S("p", Et, [C(p(ye.value ? "注册代理未启用，已有租约仍保留" : `代理平台 ${b(D)(K.value.platform)}`), 1), ve.value ? (t(), S(u, { key: 0 }, [C(" · 另有 " + p(ve.value) + " 个活跃出口", 1)], 64)) : c("", !0)])) : c("", !0)
				]),
				m("article", Dt, [
					m("header", Ot, [n[50] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M9 5h11\" data-v-aefc1e2e></path><path d=\"M9 12h11\" data-v-aefc1e2e></path><path d=\"M9 19h11\" data-v-aefc1e2e></path><circle cx=\"4\" cy=\"5\" r=\"1\" data-v-aefc1e2e></circle><circle cx=\"4\" cy=\"12\" r=\"1\" data-v-aefc1e2e></circle><circle cx=\"4\" cy=\"19\" r=\"1\" data-v-aefc1e2e></circle></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>任务</h3><p data-v-aefc1e2e>注册流水线与队列</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "jobs",
						onClick: n[8] ||= (e) => Y("tasks")
					}, [...n[49] ||= [C("任务中心", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", kt, [
						m("section", At, [n[54] ||= m("h4", null, "当前队列", -1), m("div", jt, [
							m("div", null, [n[51] ||= m("span", null, "运行中", -1), m("strong", null, p(P(W.value.running)), 1)]),
							m("div", null, [n[52] ||= m("span", null, "待处理", -1), m("strong", null, p(P(W.value.pending)), 1)]),
							m("div", null, [n[53] ||= m("span", null, "停止中", -1), m("strong", null, p(P(W.value.stopping)), 1)])
						])]),
						m("section", Mt, [m("h4", null, [n[55] ||= C("今日结果 ", -1), m("small", null, p(U.value.today), 1)]), m("div", Nt, [
							m("div", null, [n[56] ||= m("span", null, "成功", -1), m("strong", Pt, p(P(G.value.success)), 1)]),
							m("div", null, [n[57] ||= m("span", null, "部分成功", -1), m("strong", Ft, p(P(G.value.partial_success)), 1)]),
							m("div", null, [n[58] ||= m("span", null, "失败", -1), m("strong", It, p(P(G.value.failed)), 1)])
						])]),
						m("section", Lt, [
							m("h4", null, [n[59] ||= C("累计结果 ", -1), m("small", null, p(P(U.value.total)) + " 个任务", 1)]),
							ge.value.length ? (t(), S("div", Rt, [(t(!0), S(u, null, i(ge.value, (e) => (t(), S("i", {
								key: e.key,
								style: d({
									width: e.value / Math.max(1, U.value.total) * 100 + "%",
									background: e.color
								})
							}, null, 4))), 128))])) : (t(), S("div", zt)),
							m("div", Bt, [(t(!0), S(u, null, i(ge.value, (e) => (t(), S("span", { key: e.key }, [m("i", { style: d({ background: e.color }) }, null, 4), C(p(e.label) + " " + p(P(e.value)), 1)]))), 128)), ge.value.length ? c("", !0) : (t(), S("span", Vt, "暂无累计结果"))])
						])
					]),
					me.value ? (t(), S("p", Ht, "注册功能未启用，历史任务仍可查看。")) : c("", !0)
				])
			])) : c("", !0)
		], 2));
	}
}), [["__scopeId", "data-v-aefc1e2e"]]);
// src/api/dashboard.ts
async function Wt(e, t) {
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
function Gt(e = (e, t) => w(e, t), t) {
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
			let i = await Wt(r, e);
			if (typeof i != "object" || !i || !("ok" in i) || i.ok !== !0) throw new T("能力检查返回无效数据", 200);
			return i;
		}
	};
}
// src/dashboard.ts
function Kt(e, t = {}) {
	let n = v(Ut, {
		api: t.api || Gt(void 0, t.pendingCapabilities),
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
export { Kt as mountDashboard };
