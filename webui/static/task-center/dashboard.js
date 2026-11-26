import { C as e, F as t, H as n, K as r, L as i, M as a, S as o, V as s, _ as c, b as l, d as u, dt as d, et as f, ft as p, h as m, j as h, lt as g, m as _, n as v, o as y, st as b, t as x, v as S, x as C } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { r as w, t as T } from "./client-B5R_MNgP.js";
// src/features/dashboard/useDashboard.ts
var E = 2e4, D = (e) => Number(e || 0);
function ee(e) {
	return !e || typeof e != "object" || e.ok !== !0 ? null : {
		today_extracted: D(e.today_extracted),
		today_plus_confirmed: D(e.today_plus_confirmed),
		awaiting_payment: D(e.awaiting_payment),
		processing: D(e.processing),
		all: D(e.all),
		providers: Array.isArray(e.providers) ? e.providers.filter((e) => e && typeof e == "object") : []
	};
}
function O(e) {
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
function k(e, t = {}) {
	let r = f(null), i = f(null), o = f({}), s = f(null), c = f(!1), l = f(""), u = f(null), d = f(null), p = f(null), m = f(!1), g = f(""), v = f(null), y = f(!!t.visible), b = f(!1), x, S, C, w, T, D = "", O = !1, k = !1, A = 0, j = 0, M = {};
	function te(t, n) {
		if (k || !y.value || document.hidden || !e.registrationDaily) return Promise.resolve();
		let r = t !== void 0 || n !== void 0, i = r ? t || void 0 : M.from, a = r ? n || void 0 : M.to, o = JSON.stringify([i || "", a || ""]);
		if (T && D === o) return T;
		M = {
			from: i,
			to: a
		}, r && (d.value = {
			from: i,
			to: a
		});
		let f = ++j;
		C?.abort(), C = new AbortController(), c.value = !0, l.value = "";
		let m = C.signal, h = (async () => {
			try {
				let t = await e.registrationDaily?.(i, a, m);
				if (f !== j || !y.value || document.hidden) return;
				if (!t || t.ok === !1) throw Error(t?.message || "每日注册统计读取失败");
				s.value = t, p.value = {
					from: typeof t.date_from == "string" ? t.date_from : i,
					to: typeof t.date_to == "string" ? t.date_to : a
				}, u.value = typeof t.updated_at == "string" ? t.updated_at : (/* @__PURE__ */ new Date()).toISOString();
			} catch (e) {
				f === j && !String(e?.name || "").includes("Abort") && (l.value = e?.message || "每日注册统计读取失败");
			} finally {
				f === j && (c.value = !1, T = void 0);
			}
		})();
		return T = h, D = o, h;
	}
	function ne(e) {
		k || y.value === !!e || (y.value = !!e, A++, j++, S?.abort(), C?.abort(), w = void 0, T = void 0, O = !1, y.value ? (N(), P(!0)) : (x && window.clearInterval(x), x = void 0, m.value = !1, c.value = !1, D = ""));
	}
	function N() {
		x && window.clearInterval(x), x = window.setInterval(() => void P(!0), E);
	}
	function P(n = !1) {
		if (k || !y.value || document.hidden) return Promise.resolve();
		let a = n && b.value;
		if (w) return !a && O && (m.value = !0), w;
		te(M.from, M.to);
		let s = ++A;
		S?.abort(), S = new AbortController(), O = !0, a || (m.value = !0), n || (g.value = "");
		let c = S.signal, l = () => s === A && y.value && !document.hidden, u = (async () => {
			try {
				let n = await e.dashboard(c);
				if (!l()) return;
				r.value = n, b.value = !0, g.value = "", v.value = Date.now(), t.onReady?.();
			} catch (e) {
				l() && !String(e?.name || "").includes("Abort") && (g.value = e?.message || "总览加载失败", t.notify?.(`总览加载失败：${g.value}`));
			} finally {
				s === A && (O = !1, m.value = !1);
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
				l() && (i.value = ee(t));
			} catch {
				l() && (i.value = null);
			}
		})(), p = Promise.allSettled([
			u,
			d,
			f
		]).then(() => {
			s === A && (w = void 0);
		});
		return w = p, p;
	}
	let F = () => {
		!document.hidden && y.value ? P(!0) : (A++, j++, S?.abort(), C?.abort(), w = void 0, T = void 0, D = "", O = !1, m.value = !1, c.value = !1);
	};
	a(() => {
		document.addEventListener("visibilitychange", F), y.value && (N(), P());
	}), h(() => {
		k = !0, y.value = !1, A++, j++, w = void 0, T = void 0, D = "", O = !1, m.value = !1, c.value = !1, document.removeEventListener("visibilitychange", F), S?.abort(), C?.abort(), x && window.clearInterval(x), x = void 0;
	}), n(() => t.visible, (e) => ne(!!e));
	let re = _(() => !!r.value);
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
		hasData: re,
		load: P,
		loadDaily: te,
		setVisible: ne
	};
}
// src/features/dashboard/DailyRegistrationStats.vue?vue&type=script&setup=true&lang.ts
var A = {
	class: "daily-stats",
	"aria-labelledby": "daily-registration-title"
}, j = { class: "daily-stats-head" }, M = { class: "daily-stats-meta" }, te = { "data-daily-range": "" }, ne = {
	class: "daily-stats-controls",
	role: "group",
	"aria-label": "统计日期范围"
}, N = {
	key: 0,
	class: "daily-stats-error",
	"data-daily-error": "",
	role: "alert"
}, P = ["disabled"], F = {
	key: 1,
	class: "daily-stats-stale",
	"data-daily-stale": "",
	role: "status"
}, re = {
	key: 2,
	class: "daily-stats-loading",
	"aria-live": "polite"
}, I = {
	key: 0,
	class: "daily-chart"
}, L = { class: "daily-chart-heading" }, ie = {
	class: "daily-chart-switch",
	role: "group",
	"aria-label": "每日统计图表内容"
}, ae = ["aria-pressed"], oe = ["aria-pressed"], se = {
	class: "daily-chart-legend",
	"data-daily-legend": "",
	"aria-label": "图例"
}, ce = { key: 0 }, R = ["aria-label"], le = {
	class: "daily-chart-axis",
	"data-daily-axis": ""
}, ue = { class: "daily-axis-unit" }, z = {
	class: "daily-axis-ticks",
	"aria-hidden": "true"
}, de = { class: "daily-chart-scroll" }, B = {
	class: "daily-chart-grid",
	"aria-hidden": "true"
}, fe = [
	"data-daily-bar",
	"aria-label",
	"title",
	"aria-pressed",
	"tabindex",
	"onClick",
	"onFocus",
	"onKeydown"
], V = {
	class: "daily-bar-value",
	"aria-hidden": "true"
}, pe = {
	class: "daily-bar-stack",
	"aria-hidden": "true"
}, me = ["data-daily-segment"], H = { "aria-hidden": "true" }, he = ["data-daily-row"], U = { class: "daily-row-heading" }, W = ["disabled", "onClick"], G = { class: "daily-row-metrics" }, K = { class: "daily-row-plans" }, ge = ["title"], q = { key: 0 }, J = { key: 1 }, _e = {
	key: 2,
	class: "daily-stats-empty"
}, ve = {
	key: 3,
	class: "daily-stats-summary"
}, ye = ["disabled"], be = /*#__PURE__*/ x(/* @__PURE__ */ e({
	__name: "DailyRegistrationStats",
	props: {
		state: {},
		onBulkPlanCreate: { type: Function }
	},
	setup(e) {
		let a = e, o = f("7"), l = f(""), h = f(""), v = f(!1), b = f("status"), x = f(""), w = `daily-registration-detail-${s()}`, T = _(() => Array.isArray(a.state.data?.rows) ? a.state.data.rows : []), E = _(() => ({
			from: a.state.data?.date_from || T.value[0]?.date || "",
			to: a.state.data?.date_to || T.value[T.value.length - 1]?.date || ""
		})), D = _(() => E.value.from && E.value.to ? `${E.value.from} 至 ${E.value.to}` : "日期范围待返回"), ee = _(() => a.state.updatedAt ? `更新于 ${new Date(a.state.updatedAt).toLocaleString("zh-CN", {
			hour12: !1,
			timeZone: "Asia/Shanghai"
		})}` : a.state.loading ? "正在读取…" : "尚未读取"), O = _(() => a.state.error && a.state.data && a.state.scopeCurrent ? `${a.state.error}，当前成功范围仍可使用。` : a.state.error), k = _(() => T.value.find((e) => e.date === x.value)), be = {
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
		}, xe = {
			success: "成功",
			partial_success: "部分成功",
			failed: "失败",
			active: "进行中",
			cancelled: "取消"
		}, Se = {
			interrupted: "执行中断",
			unsupported: "不支持",
			deactivated: "已停用"
		}, Ce = [
			{
				key: "success",
				label: "成功",
				keys: ["success"],
				color: "#249b72"
			},
			{
				key: "partial_success",
				label: "部分成功",
				keys: ["partial_success"],
				color: "#d39a27"
			},
			{
				key: "failed",
				label: "失败",
				keys: ["failed"],
				color: "#df5a67"
			},
			{
				key: "active",
				label: "进行中",
				keys: [
					"pending",
					"queued",
					"running",
					"waiting",
					"settling",
					"stopping",
					"cancelling"
				],
				color: "#4c86db"
			},
			{
				key: "cancelled",
				label: "取消",
				keys: ["cancelled", "stopped"],
				color: "#98a2b3"
			},
			{
				key: "interrupted",
				label: "执行中断",
				keys: ["interrupted"],
				color: "#8b68c9"
			},
			{
				key: "unsupported",
				label: "不支持",
				keys: ["unsupported"],
				color: "#b29bd7"
			},
			{
				key: "deactivated",
				label: "已停用",
				keys: ["deactivated"],
				color: "#667085"
			}
		], we = {
			free: "#a5adbb",
			free_trial_eligible: "#4f9f88",
			free_half_price_eligible: "#6aab9b",
			free_discount_eligible: "#92bdb0",
			free_promo_unknown: "#baccc6",
			plus: "#6564d8",
			pro: "#4c86db",
			team: "#249b72",
			go: "#d39a27",
			unknown: "#d0d5df"
		}, Te = Object.keys(be);
		function Ee(e, t) {
			let n = Te.indexOf(e.key), r = Te.indexOf(t.key);
			return (n < 0 ? Te.length : n) - (r < 0 ? Te.length : r) || e.key.localeCompare(t.key);
		}
		let De = _(() => T.value.map((e) => {
			let t = b.value === "status" ? e.counts == null : e.plans == null, n = b.value === "status" ? Y(e.total) : Y(e.accounts_total), r;
			if (t) r = [{
				key: "unavailable",
				label: b.value === "status" ? "状态待查" : "套餐待查",
				value: Math.max(0, n ?? 0),
				color: "#b5bdcd"
			}];
			else if (b.value === "status") {
				r = Ce.map((t) => ({
					...t,
					value: Re(e, t.keys) ?? 0
				}));
				let t = r.reduce((e, t) => e + t.value, 0);
				n !== null && n > t && r.push({
					key: "other",
					label: "其他状态",
					value: n - t,
					color: "#b5bdcd"
				});
			} else r = (X(e) ?? []).map((e) => ({
				key: e.key,
				label: e.label,
				value: e.count,
				color: we[e.key] || "#8b8fa3"
			})).sort(Ee);
			let i = r.filter((e) => e.value > 0);
			return {
				row: e,
				total: n,
				unavailable: t,
				segments: i,
				stackTotal: i.reduce((e, t) => e + t.value, 0)
			};
		})), Oe = _(() => Math.max(1, Math.ceil(Math.max(0, ...De.value.map((e) => Math.max(e.total ?? 0, e.stackTotal))) / 4))), ke = _(() => Oe.value * 4), Ae = _(() => [
			4,
			3,
			2,
			1,
			0
		].map((e) => e * Oe.value)), je = _(() => {
			let e = /* @__PURE__ */ new Map();
			for (let t of De.value) for (let n of t.segments) e.has(n.key) || e.set(n.key, n);
			if (De.value.some((e) => e.unavailable) && !e.has("unavailable") && e.set("unavailable", {
				key: "unavailable",
				label: b.value === "status" ? "状态待查" : "套餐待查",
				value: 0,
				color: "#b5bdcd"
			}), b.value === "status") {
				for (let t of Ce.slice(0, 5)) e.has(t.key) || e.set(t.key, {
					...t,
					value: 0
				});
				return [...e.values()].sort((e, t) => {
					let n = [
						...Ce.map((e) => e.key),
						"other",
						"unavailable"
					];
					return n.indexOf(e.key) - n.indexOf(t.key);
				});
			}
			return [...e.values()].sort(Ee);
		});
		function Me(e) {
			let t = b.value === "status" ? "任务总数" : "账号总数", n = e.unavailable ? [b.value === "status" ? "状态待查" : "套餐待查"] : e.segments.map((e) => `${e.label} ${Z(e.value)}`);
			return `${e.row.date}，${t} ${Z(e.total)}${n.length ? `，${n.join("，")}` : ""}，点击查看当日详情`;
		}
		function Ne(e) {
			x.value = e;
		}
		function Pe(e, t) {
			let n = t;
			if (e.key === "ArrowRight") n = Math.min(T.value.length - 1, t + 1);
			else if (e.key === "ArrowLeft") n = Math.max(0, t - 1);
			else if (e.key === "Home") n = 0;
			else if (e.key === "End") n = T.value.length - 1;
			else return;
			e.preventDefault();
			let r = T.value[n];
			if (!r) return;
			Ne(r.date);
			let i = e.currentTarget.parentElement?.querySelectorAll("[data-daily-bar]");
			i?.[n]?.focus({ preventScroll: !0 }), i?.[n]?.scrollIntoView?.({
				block: "nearest",
				inline: "nearest"
			});
		}
		function Fe(e) {
			let t = Number(e);
			return Number.isFinite(t) ? t : 0;
		}
		function Y(e) {
			if (e == null) return null;
			let t = Number(e);
			return Number.isFinite(t) ? t : null;
		}
		function Ie(e, t) {
			return e.counts === null || e.counts === void 0 ? null : Y(e.counts[t]) ?? 0;
		}
		function Le(e, t) {
			let n = Ie(e, t);
			return `${xe[t] || t} ${n === null ? "—" : Fe(n)}`;
		}
		function Re(e, t) {
			return e.counts === null || e.counts === void 0 ? null : t.reduce((t, n) => t + (Y(e.counts[n]) ?? 0), 0);
		}
		function ze(e, t, n) {
			let r = Re(e, n);
			return `${t} ${r === null ? "—" : Fe(r)}`;
		}
		function Be(e) {
			return e.counts === null || e.counts === void 0 ? [] : Object.entries(Se).map(([t, n]) => ({
				key: t,
				label: n,
				value: Y(e.counts[t]) ?? 0
			})).filter((e) => e.value > 0);
		}
		function X(e) {
			return e.plans === null || e.plans === void 0 ? null : Object.entries(e.plans).map(([e, t]) => ({
				key: e,
				label: be[e] || e,
				count: Fe(t)
			})).sort((e, t) => t.count - e.count);
		}
		function Ve(e) {
			return X(e)?.reduce((e, t) => e + t.count, 0) ?? null;
		}
		function He(e, t) {
			let n = Ve(e);
			return n && t >= 0 ? `${Math.round(t / n * 100)}%` : "—";
		}
		function Z(e) {
			let t = Y(e);
			return t === null ? "—" : new Intl.NumberFormat("zh-CN").format(t);
		}
		function Ue(e) {
			let t = Y(e);
			return t === null ? "待查" : new Intl.NumberFormat("zh-CN").format(t);
		}
		function We(e) {
			return Y(e.unpromoted_count);
		}
		function Ge(e) {
			return a.state.scopeCurrent && We(e) !== null && We(e) > 0 && !!e.query;
		}
		function Ke(e, t) {
			Ge(e) && e.query && a.onBulkPlanCreate?.({
				name: t,
				query: e.query
			});
		}
		function qe(e, t) {
			let n = /* @__PURE__ */ new Date(`${e}T00:00:00Z`);
			return n.setUTCDate(n.getUTCDate() + t), n.toISOString().slice(0, 10);
		}
		function Je() {
			let e = new Intl.DateTimeFormat("en-US", {
				timeZone: "Asia/Shanghai",
				year: "numeric",
				month: "2-digit",
				day: "2-digit"
			}).formatToParts(/* @__PURE__ */ new Date()), t = Object.fromEntries(e.filter((e) => e.type !== "literal").map((e) => [e.type, e.value]));
			return `${t.year}-${t.month}-${t.day}`;
		}
		function Ye(e) {
			let t = Je();
			return [qe(t, -(e - 1)), t];
		}
		function Xe(e) {
			o.value = e;
			let [t, n] = Ye(Number(e));
			a.state.load(t, n);
		}
		function Ze() {
			o.value = "custom", l.value = a.state.displayedRange?.from || E.value.from, h.value = a.state.displayedRange?.to || E.value.to;
		}
		function Qe() {
			o.value !== "custom" || !l.value || !h.value || l.value > h.value || a.state.load(l.value, h.value);
		}
		return n(T, (e) => {
			e.some((e) => e.date === x.value) || (x.value = e[0]?.date || "");
		}, { immediate: !0 }), n(() => [a.state.data?.date_from, a.state.data?.date_to], ([e, t]) => {
			!v.value && (e || t) && (l.value = e || "", h.value = t || "", v.value = !0);
		}, { immediate: !0 }), (n, a) => (t(), S("section", A, [
			m("header", j, [a[8] ||= m("div", null, [m("h2", { id: "daily-registration-title" }, "每日注册统计"), m("p", null, "北京时间 · 按注册任务创建日期统计 · 套餐以最近成功查询为准 · 账号总数含归档账号")], -1), m("div", M, [m("span", te, p(D.value), 1), m("span", null, p(ee.value), 1)])]),
			m("div", ne, [
				m("button", {
					type: "button",
					"data-daily-range-7": "",
					class: g({ active: o.value === "7" }),
					onClick: a[0] ||= (e) => Xe("7")
				}, "近 7 天", 2),
				m("button", {
					type: "button",
					"data-daily-range-30": "",
					class: g({ active: o.value === "30" }),
					onClick: a[1] ||= (e) => Xe("30")
				}, "近 30 天", 2),
				m("button", {
					type: "button",
					class: g({ active: o.value === "custom" }),
					onClick: Ze
				}, "自定义", 2),
				o.value === "custom" ? (t(), S(u, { key: 0 }, [m("label", null, [a[9] ||= C("开始日期", -1), r(m("input", {
					"onUpdate:modelValue": a[2] ||= (e) => l.value = e,
					type: "date",
					onChange: Qe
				}, null, 544), [[y, l.value]])]), m("label", null, [a[10] ||= C("结束日期", -1), r(m("input", {
					"onUpdate:modelValue": a[3] ||= (e) => h.value = e,
					type: "date",
					onChange: Qe
				}, null, 544), [[y, h.value]])])], 64)) : c("", !0)
			]),
			e.state.error ? (t(), S("div", N, [m("span", null, p(O.value), 1), m("button", {
				type: "button",
				"data-daily-retry": "",
				disabled: e.state.loading,
				onClick: a[4] ||= (t) => e.state.load()
			}, "重试", 8, P)])) : c("", !0),
			e.state.data && !e.state.scopeCurrent ? (t(), S("div", F, p(e.state.loading ? "正在读取新日期范围，当前仍显示上一成功范围；完成前不能新建查套餐批量。" : "新日期范围读取失败，当前仍显示上一成功范围；请重试后再新建查套餐批量。"), 1)) : c("", !0),
			e.state.loading && !e.state.data ? (t(), S("div", re, "正在读取每日注册统计…")) : e.state.data ? (t(), S(u, { key: 3 }, [
				T.value.length ? (t(), S("div", I, [
					m("div", L, [m("div", ie, [m("button", {
						type: "button",
						"data-daily-view": "status",
						"aria-pressed": b.value === "status",
						onClick: a[5] ||= (e) => b.value = "status"
					}, "任务状态", 8, ae), m("button", {
						type: "button",
						"data-daily-view": "plans",
						"aria-pressed": b.value === "plans",
						onClick: a[6] ||= (e) => b.value = "plans"
					}, "套餐分布", 8, oe)]), a[11] ||= m("p", null, "点选日期查看详情 · 方向键切换日期", -1)]),
					m("div", se, [(t(!0), S(u, null, i(je.value, (e) => (t(), S("span", { key: e.key }, [m("i", {
						class: g({ "is-unavailable": e.key === "unavailable" }),
						style: d({ backgroundColor: e.color }),
						"aria-hidden": "true"
					}, null, 6), C(p(e.label), 1)]))), 128)), je.value.length ? c("", !0) : (t(), S("span", ce, p(b.value === "plans" ? "暂无套餐账号" : "暂无任务"), 1))]),
					m("div", {
						class: "daily-stats-chart",
						role: "group",
						"aria-label": b.value === "status" ? "每日注册任务状态堆叠柱状图" : "每日注册账号套餐堆叠柱状图"
					}, [m("div", le, [m("span", ue, p(b.value === "status" ? "任务数" : "账号数"), 1), m("div", z, [(t(!0), S(u, null, i(Ae.value, (e) => (t(), S("span", {
						key: e,
						"data-daily-axis-tick": ""
					}, p(Z(e)), 1))), 128))])]), m("div", de, [m("div", {
						class: "daily-chart-plot",
						style: d({
							gridTemplateColumns: `repeat(${T.value.length},minmax(44px,1fr))`,
							minWidth: `${T.value.length * 48}px`
						})
					}, [m("div", B, [(t(!0), S(u, null, i(Ae.value, (e) => (t(), S("i", { key: e }))), 128))]), (t(!0), S(u, null, i(De.value, (e, n) => (t(), S("button", {
						key: e.row.date,
						type: "button",
						class: g(["daily-bar-column", { selected: e.row.date === x.value }]),
						"data-daily-bar": e.row.date,
						"aria-label": Me(e),
						title: Me(e),
						"aria-pressed": e.row.date === x.value,
						"aria-controls": w,
						tabindex: e.row.date === x.value ? 0 : -1,
						onClick: (t) => Ne(e.row.date),
						onFocus: (t) => Ne(e.row.date),
						onKeydown: (e) => Pe(e, n)
					}, [
						m("span", V, p(Z(e.total)), 1),
						m("span", pe, [(t(!0), S(u, null, i(e.segments, (e) => (t(), S("span", {
							key: e.key,
							class: g(["daily-bar-segment", { "is-unavailable": e.key === "unavailable" }]),
							"data-daily-segment": e.key,
							style: d({
								height: `${e.value / ke.value * 100}%`,
								backgroundColor: e.color
							})
						}, null, 14, me))), 128))]),
						m("small", H, p(e.row.date.slice(5)), 1)
					], 42, fe))), 128))], 4)])], 8, R)
				])) : c("", !0),
				k.value ? (t(), S("div", {
					key: 1,
					id: w,
					class: "daily-selected-detail",
					"aria-live": "polite",
					"aria-atomic": "true"
				}, [(t(!0), S(u, null, i([k.value], (e) => (t(), S("article", {
					key: e.date,
					class: "daily-stats-row",
					"data-daily-row": e.date
				}, [
					m("div", U, [m("div", null, [m("strong", null, p(e.date), 1), m("span", null, "总数 " + p(Z(e.total)), 1)]), m("button", {
						type: "button",
						"data-daily-bulk": "",
						disabled: !Ge(e),
						onClick: (t) => Ke(e, `${e.date} 无优惠账号查套餐`)
					}, " 新建查套餐批量（" + p(Ue(e.unpromoted_count)) + "） ", 9, W)]),
					m("div", G, [
						m("span", null, p(Le(e, "success")), 1),
						m("span", null, p(Le(e, "partial_success")), 1),
						m("span", null, p(Le(e, "failed")), 1),
						m("span", null, p(ze(e, "进行中", [
							"pending",
							"queued",
							"running",
							"waiting",
							"settling",
							"stopping",
							"cancelling"
						])), 1),
						m("span", null, p(ze(e, "取消", ["cancelled", "stopped"])), 1),
						(t(!0), S(u, null, i(Be(e), (e) => (t(), S("span", { key: e.key }, p(e.label) + " " + p(e.value), 1))), 128)),
						m("span", null, "账号总数（含归档） " + p(Z(e.accounts_total)), 1),
						m("span", null, "未归档无优惠 " + p(Ue(e.unpromoted_count)), 1)
					]),
					m("div", K, [a[12] ||= m("span", { class: "daily-row-label" }, "套餐分布", -1), X(e) ? (t(), S(u, { key: 0 }, [(t(!0), S(u, null, i(X(e), (n) => (t(), S("span", {
						key: n.key,
						title: `${n.label} ${Z(n.count)}，占套餐账号 ${He(e, n.count)}`
					}, p(n.label) + " " + p(Z(n.count)) + " · " + p(He(e, n.count)), 9, ge))), 128)), X(e).length ? c("", !0) : (t(), S("span", q, "暂无账号"))], 64)) : (t(), S("span", J, "套餐待查"))])
				], 8, he))), 128))])) : (t(), S("p", _e, "所选日期暂无任务。")),
				e.state.data.summary ? (t(), S("div", ve, [m("div", null, [a[13] ||= m("strong", null, "区间汇总", -1), m("span", null, "总数 " + p(Z(e.state.data.summary.total)) + " · 账号总数（含归档） " + p(Z(e.state.data.summary.accounts_total)) + " · 未归档无优惠 " + p(Ue(e.state.data.summary.unpromoted_count)), 1)]), m("button", {
					type: "button",
					"data-daily-summary-bulk": "",
					disabled: !Ge(e.state.data.summary),
					onClick: a[7] ||= (t) => Ke(e.state.data.summary, `${E.value.from}..${E.value.to} 无优惠账号查套餐`)
				}, " 新建区间查套餐批量（" + p(Ue(e.state.data.summary.unpromoted_count)) + "） ", 9, ye)])) : c("", !0)
			], 64)) : c("", !0)
		]));
	}
}), [["__scopeId", "data-v-142e57f3"]]), xe = { class: "ov-section-head" }, Se = { class: "ov-section-actions" }, Ce = { class: "ov-updated" }, we = ["disabled"], Te = {
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
}, Fe = { class: "ov-card-head" }, Y = { class: "ov-figure" }, Ie = { class: "ov-mini-grid ov-mini-grid--3" }, Le = {
	key: 0,
	class: "ov-bars"
}, Re = { class: "ov-bar-label" }, ze = {
	key: 1,
	class: "ov-empty"
}, Be = {
	key: 2,
	class: "ov-foot"
}, X = {
	key: 3,
	class: "ov-foot"
}, Ve = {
	class: "ov-card ov-card--accounts",
	"data-overview-card": "accounts",
	style: {
		"--accent": "#5b5ce2",
		"--accent-soft": "#eeeefe"
	}
}, He = { class: "ov-card-head" }, Z = { class: "ov-figure" }, Ue = {
	class: "ov-split",
	"aria-hidden": "true"
}, We = { class: "ov-legend" }, Ge = { class: "ov-mini-grid ov-mini-grid--2" }, Ke = { class: "ov-meter" }, qe = { class: "ov-bar" }, Je = {
	class: "ov-card ov-card--codex",
	"data-overview-card": "codex",
	style: {
		"--accent": "#377dff",
		"--accent-soft": "#e9f1ff"
	}
}, Ye = { class: "ov-card-head" }, Xe = { class: "ov-figure" }, Ze = {
	key: 0,
	class: "ov-chip is-warn"
}, Qe = { class: "ov-bar-label" }, $e = { class: "ov-bar ov-bar--thick" }, et = { class: "ov-mini-grid ov-mini-grid--3" }, tt = { class: "ov-foot" }, nt = {
	class: "ov-card ov-card--extract",
	"data-overview-card": "extract",
	style: {
		"--accent": "#d97706",
		"--accent-soft": "#fdf3e3"
	}
}, rt = { class: "ov-card-head" }, it = { class: "ov-figure" }, at = {
	key: 0,
	class: "ov-mini-grid ov-mini-grid--3"
}, ot = {
	key: 1,
	class: "ov-empty"
}, st = { class: "ov-foot" }, ct = {
	class: "ov-card ov-card--plans",
	"data-overview-card": "plans",
	style: {
		"--accent": "#8b5cf6",
		"--accent-soft": "#f3edff"
	}
}, lt = { class: "ov-card-head" }, ut = { class: "ov-figure ov-figure--small" }, dt = { class: "ov-bars" }, ft = { class: "ov-bar-label" }, pt = { class: "ov-bar" }, mt = {
	key: 1,
	class: "ov-empty"
}, ht = {
	class: "ov-card ov-card--proxy",
	"data-overview-card": "proxy",
	style: {
		"--accent": "#0e9aa7",
		"--accent-soft": "#e6f6f7"
	}
}, gt = { class: "ov-card-head" }, _t = { class: "ov-figure" }, vt = { class: "ov-chip" }, yt = {
	key: 0,
	class: "ov-lease-list"
}, bt = {
	key: 1,
	class: "ov-empty"
}, xt = {
	key: 2,
	class: "ov-foot"
}, St = {
	class: "ov-card ov-card--jobs",
	"data-overview-card": "jobs",
	style: {
		"--accent": "#475569",
		"--accent-soft": "#eef1f5"
	}
}, Ct = { class: "ov-card-head" }, wt = { class: "ov-task-columns" }, Tt = { class: "ov-task-block" }, Et = { class: "ov-mini-grid ov-mini-grid--3" }, Dt = { class: "ov-task-block" }, Ot = { class: "ov-mini-grid ov-mini-grid--3" }, kt = { class: "is-ok" }, At = { class: "is-warn" }, jt = { class: "is-danger" }, Mt = { class: "ov-task-block ov-task-block--wide" }, Nt = {
	key: 0,
	class: "ov-stack",
	"aria-hidden": "true"
}, Pt = {
	key: 1,
	class: "ov-stack ov-stack--empty",
	"aria-hidden": "true"
}, Ft = { class: "ov-stack-legend" }, It = {
	key: 0,
	class: "ov-stack-empty-text"
}, Lt = {
	key: 0,
	class: "ov-foot"
}, Q = /*#__PURE__*/ x(/* @__PURE__ */ e({
	__name: "DashboardPage",
	props: {
		api: {},
		deps: {}
	},
	setup(e, { expose: n }) {
		let r = e, s = k(r.api, r.deps), { data: h, extract: v, caps: y, daily: x, dailyLoading: w, dailyError: T, dailyUpdatedAt: E, dailyRequestedRange: D, dailyDisplayedRange: ee, dailyScopeCurrent: A, loading: j, error: M, updatedAt: te } = s, ne = f(!1);
		a(() => {
			ne.value = !0;
		});
		let N = (e) => new Intl.NumberFormat("zh-CN").format(Number(e || 0)), P = (e) => Number(e || 0), F = (e, t) => {
			let n = P(t);
			return n > 0 ? Math.max(0, Math.min(100, Math.round(P(e) / n * 100))) : 0;
		}, re = (e) => ({
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
		})[e] || e, I = _(() => h.value?.accounts || {}), L = _(() => h.value?.email?.supply || {}), ie = _(() => (Array.isArray(L.value?.sources) ? L.value.sources : Array.isArray(h.value?.email?.sources) ? h.value.email.sources : []).filter((e) => e?.kind === "local_pool")), ae = _(() => ie.value.filter((e) => P(e.total) > 0 || P(e.available) > 0)), oe = _(() => Math.max(0, ie.value.length - ae.value.length)), se = _(() => L.value?.status === "error" ? "读取失败" : P(L.value?.available)), ce = _(() => L.value?.status === "error" ? "—" : N(se.value)), R = _(() => P(L.value?.total)), le = _(() => P(L.value?.used)), ue = _(() => P(L.value?.failed) + P(L.value?.disabled)), z = _(() => L.value?.status === "error" ? "danger" : R.value > 0 && P(L.value?.available) === 0 ? "warn" : P(L.value?.available) > 0 ? "ok" : "idle"), de = _(() => L.value?.status === "error" ? "读取失败" : R.value === 0 ? "未配置" : P(L.value?.available) === 0 ? "库存耗尽" : "库存正常"), B = _(() => h.value?.codex || {}), fe = _(() => P(B.value.pending) > 0 ? "warn" : P(B.value.total) > 0 ? "ok" : "idle"), V = _(() => Object.entries(I.value?.plans || {}).map(([e, t]) => ({
			key: e,
			label: re(e),
			count: P(t)
		})).sort((e, t) => t.count - e.count)), pe = _(() => Math.max(1, ...V.value.map((e) => e.count))), me = _(() => V.value.reduce((e, t) => e + t.count, 0)), H = _(() => h.value?.jobs || {}), he = _(() => y.value?.features?.register?.enabled === !1), U = _(() => ({ ...H.value?.counts || {} })), W = _(() => ({ ...H.value?.today_counts || {} })), G = _(() => P(U.value.pending) + P(U.value.running) + P(U.value.stopping));
		_(() => P(W.value.success) + P(W.value.partial_success) + P(W.value.failed));
		let K = _(() => [
			{
				key: "success",
				label: "成功",
				value: P(U.value.success),
				color: "#1f9d75"
			},
			{
				key: "partial_success",
				label: "部分成功",
				value: P(U.value.partial_success),
				color: "#d99a2b"
			},
			{
				key: "failed",
				label: "失败",
				value: P(U.value.failed),
				color: "#d9534f"
			},
			{
				key: "cancelled",
				label: "停止/取消",
				value: P(U.value.stopped) + P(U.value.cancelled),
				color: "#98a2b3"
			}
		].filter((e) => e.value > 0)), ge = _(() => G.value > 0 ? "active" : P(W.value.failed) > 0 ? "warn" : "idle"), q = _(() => h.value?.proxy || {}), J = _(() => Array.isArray(q.value.leases) ? q.value.leases.slice(0, 3) : []), _e = _(() => Math.max(0, P(q.value.active_leases) - J.value.length)), ve = _(() => y.value?.proxy?.registration?.enabled === !1), ye = _(() => P(q.value.active_leases) > 0 ? "ok" : "idle"), Q = _(() => v.value || {}), Rt = _(() => P(Q.value.processing) > 0 ? "active" : "idle"), zt = _(() => P(Q.value.all) === 0 && P(Q.value.today_extracted) === 0 && P(Q.value.processing) === 0 && P(Q.value.awaiting_payment) === 0), Bt = _(() => [
			{
				id: "email",
				label: "邮箱",
				value: ce.value,
				badge: L.value?.status === "error" ? "读取失败" : P(L.value?.available) === 0 ? "库存耗尽" : `${ce.value} 可用`,
				hint: P(L.value?.available) === 0 ? "库存耗尽" : `邮箱总量 ${N(R.value)}`,
				tone: z.value,
				tab: "outlook"
			},
			{
				id: "accounts",
				label: "账号",
				value: N(I.value.active),
				badge: `${N(I.value.active)} 活跃`,
				hint: `归档 ${N(I.value.archived)}`,
				tone: "ok",
				tab: "accounts"
			},
			{
				id: "codex",
				label: "Codex",
				value: N(B.value.total),
				badge: P(B.value.pending) > 0 ? `待导 ${N(B.value.pending)}` : `${N(B.value.total)} 凭证`,
				hint: `待导出 ${N(B.value.pending)}`,
				tone: fe.value,
				tab: "codex"
			},
			{
				id: "plans",
				label: "套餐",
				value: N(V.value.length),
				badge: `${N(V.value.length)} 类`,
				hint: `${N(me.value)} 个已归类`,
				tone: "ok",
				tab: "accounts"
			},
			{
				id: "extract",
				label: "提炼",
				value: N(Q.value.today_extracted),
				badge: P(Q.value.processing) > 0 ? `进行 ${N(Q.value.processing)}` : `今日 ${N(Q.value.today_extracted)}`,
				hint: "今日已提炼",
				tone: Rt.value,
				tab: "extract-workbench"
			},
			{
				id: "proxy",
				label: "代理",
				value: N(q.value.active_leases),
				badge: P(q.value.active_leases) > 0 ? `${N(q.value.active_leases)} 出口` : O(q.value.platform),
				hint: O(q.value.platform),
				tone: ye.value,
				tab: "proxy-traffic"
			},
			{
				id: "jobs",
				label: "任务",
				value: N(G.value),
				badge: G.value > 0 ? `运行 ${N(G.value)}` : P(W.value.failed) > 0 ? `异常 ${N(W.value.failed)}` : "空闲",
				hint: `累计 ${N(H.value.total)}`,
				tone: ge.value,
				tab: "tasks"
			}
		]), Vt = _(() => {
			let e = [];
			return L.value?.status === "error" ? e.push({
				tone: "danger",
				text: "邮箱池统计读取失败，暂时无法判断可用库存。",
				tab: "outlook",
				label: "检查邮箱池"
			}) : R.value > 0 && P(L.value?.available) === 0 && e.push({
				tone: "warning",
				text: `邮箱池已用完（已用 ${N(le.value)} / 邮箱总量 ${N(R.value)}），新的注册任务取不到邮箱。`,
				tab: "outlook",
				label: "添加邮箱库存"
			}), e.slice(0, 2);
		}), Ht = _(() => te.value ? `数据更新 ${new Date(te.value).toLocaleTimeString("zh-CN", { hour12: !1 })}` : j.value ? "正在读取…" : "尚未读取"), $ = (e) => r.deps.onNavigate?.(e), Ut = _(() => ({
			data: x.value,
			loading: w.value,
			error: T.value,
			updatedAt: E.value,
			requestedRange: D.value,
			displayedRange: ee.value,
			scopeCurrent: A.value,
			load: s.loadDaily
		}));
		return n({
			load: s.load,
			setVisible: s.setVisible,
			openCustomizer: () => {},
			closeCustomizer: () => {},
			resetLayout: () => {}
		}), (e, n) => (t(), S("div", { class: g(["ov-page", { "is-mounted": ne.value }]) }, [
			m("div", xe, [n[11] ||= m("div", { class: "ov-section-title" }, [m("h2", null, "服务脉搏"), m("p", null, "邮箱 · 账号 · Codex · 套餐 · 提炼 · 代理 · 任务")], -1), m("div", Se, [m("span", Ce, [n[9] ||= m("i", { "aria-hidden": "true" }, null, -1), C(p(Ht.value), 1)]), m("button", {
				type: "button",
				class: "ov-refresh ui-refresh-button",
				disabled: b(j),
				onClick: n[0] ||= (e) => b(s).load()
			}, [n[10] ||= m("svg", {
				viewBox: "0 0 24 24",
				"aria-hidden": "true"
			}, [m("path", { d: "M20 11a8 8 0 1 0-2.3 6.7" }), m("path", { d: "M20 4v7h-7" })], -1), C(" " + p(b(j) ? "刷新中" : "刷新"), 1)], 8, we)])]),
			b(M) ? (t(), S("div", Te, [m("div", null, [n[12] ||= m("strong", null, "总览加载失败", -1), m("span", null, p(b(M)), 1)]), m("button", {
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
			!b(h) && b(j) ? (t(), S("section", Oe, [...n[14] ||= [m("div", { class: "ov-skeleton-pulse" }, null, -1), m("div", { class: "ov-skeleton-grid" }, [
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
			o(be, {
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
					m("div", Y, [
						m("strong", { class: g({ "is-danger": z.value === "warn" }) }, p(ce.value), 3),
						n[18] ||= m("span", null, "可用", -1),
						z.value === "ok" ? c("", !0) : (t(), S("em", {
							key: 0,
							class: g(["ov-chip", `is-${z.value}`])
						}, p(de.value), 3))
					]),
					m("div", Ie, [
						m("div", null, [n[19] ||= m("span", null, "邮箱总量", -1), m("strong", null, p(N(R.value)), 1)]),
						m("div", null, [n[20] ||= m("span", null, "已使用", -1), m("strong", null, p(N(le.value)), 1)]),
						m("div", null, [n[21] ||= m("span", null, "停用 / 失败", -1), m("strong", null, p(N(ue.value)), 1)])
					]),
					ae.value.length ? (t(), S("ul", Le, [(t(!0), S(u, null, i(ae.value, (e) => (t(), S("li", { key: e.source }, [m("div", Re, [m("span", null, p(e.label), 1), m("small", null, p(P(e.available) === 0 ? "已用尽" : `可用 ${N(e.available)}`) + " / " + p(N(e.total)), 1)]), m("div", { class: g(["ov-bar", { "is-spent": P(e.available) === 0 && P(e.total) > 0 }]) }, [m("i", { style: d({ width: F(e.available, e.total) + "%" }) }, null, 4)], 2)]))), 128))])) : (t(), S("p", ze, "还没有可统计的邮箱库存。")),
					oe.value ? (t(), S("p", Be, "另有 " + p(oe.value) + " 个来源暂无库存 · 仅统计本地库存", 1)) : (t(), S("p", X, "仅统计本地库存，用完后需手动导入"))
				]),
				m("article", Ve, [
					m("header", He, [n[23] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\" data-v-aefc1e2e></path><circle cx=\"9\" cy=\"7\" r=\"4\" data-v-aefc1e2e></circle><path d=\"M22 21v-2a4 4 0 0 0-3-3.9\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>账号</h3><p data-v-aefc1e2e>账号资产</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "accounts",
						onClick: n[3] ||= (e) => $("accounts")
					}, [...n[22] ||= [C("管理", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", Z, [m("strong", null, p(N(I.value.active)), 1), n[24] ||= m("span", null, "活跃账号", -1)]),
					m("div", Ue, [m("i", {
						class: "is-active",
						style: d({ width: F(I.value.active, I.value.total) + "%" })
					}, null, 4), m("i", {
						class: "is-idle",
						style: d({ width: F(I.value.archived, I.value.total) + "%" })
					}, null, 4)]),
					m("div", We, [m("span", null, [n[25] ||= m("i", { style: { background: "#5b5ce2" } }, null, -1), C("活跃 " + p(N(I.value.active)), 1)]), m("span", null, [n[26] ||= m("i", { style: { background: "#d7dbe5" } }, null, -1), C("归档 " + p(N(I.value.archived)), 1)])]),
					m("div", Ge, [m("div", null, [n[27] ||= m("span", null, "账号总数", -1), m("strong", null, p(N(I.value.total)), 1)]), m("div", null, [n[28] ||= m("span", null, "Codex 就绪", -1), m("strong", null, p(N(I.value.codex_ready)), 1)])]),
					m("div", Ke, [
						n[29] ||= m("span", null, "Codex 就绪率", -1),
						m("div", qe, [m("i", { style: d({ width: F(I.value.codex_ready, I.value.active) + "%" }) }, null, 4)]),
						m("strong", null, p(F(I.value.codex_ready, I.value.active)) + "%", 1)
					])
				]),
				m("article", Je, [
					m("header", Ye, [n[31] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><rect x=\"3\" y=\"11\" width=\"18\" height=\"10\" rx=\"2\" data-v-aefc1e2e></rect><path d=\"M7 11V7a5 5 0 0 1 10 0v4\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>Codex</h3><p data-v-aefc1e2e>授权凭证</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "codex",
						onClick: n[4] ||= (e) => $("codex")
					}, [...n[30] ||= [C("查看", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", Xe, [
						m("strong", null, p(N(B.value.total)), 1),
						n[32] ||= m("span", null, "已导出凭证", -1),
						fe.value === "warn" ? (t(), S("em", Ze, "待导出")) : c("", !0)
					]),
					m("div", Qe, [n[33] ||= m("span", null, "导出进度", -1), m("small", null, p(N(B.value.exported)) + " / " + p(N(B.value.total)), 1)]),
					m("div", $e, [m("i", { style: d({ width: F(B.value.exported, B.value.total) + "%" }) }, null, 4)]),
					m("div", et, [
						m("div", null, [n[34] ||= m("span", null, "已导出", -1), m("strong", null, p(N(B.value.exported)), 1)]),
						m("div", null, [n[35] ||= m("span", null, "待导出", -1), m("strong", null, p(N(B.value.pending)), 1)]),
						m("div", null, [n[36] ||= m("span", null, "账号就绪", -1), m("strong", null, p(N(I.value.codex_ready)), 1)])
					]),
					m("p", tt, "账号 Codex 就绪 " + p(N(I.value.codex_ready)) + " · 覆盖 " + p(F(I.value.codex_ready, I.value.active)) + "% 活跃账号", 1)
				]),
				m("article", nt, [
					m("header", rt, [n[38] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z\" data-v-aefc1e2e></path><path d=\"M19 15.5 20 18l2.5 1-2.5 1L19 22l-1-2-2.5-1 2.5-1 1-2.5Z\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>提炼</h3><p data-v-aefc1e2e>提链工作台</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "extract",
						onClick: n[5] ||= (e) => $("extract-workbench")
					}, [...n[37] ||= [C("工作台", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", it, [
						m("strong", null, p(N(Q.value.today_extracted)), 1),
						n[39] ||= m("span", null, "今日已提炼", -1),
						m("em", { class: g(["ov-chip", `is-${Rt.value}`]) }, p(Rt.value === "idle" ? "空闲" : "处理中"), 3)
					]),
					zt.value ? c("", !0) : (t(), S("div", at, [
						m("div", null, [n[40] ||= m("span", null, "Plus 已确认", -1), m("strong", null, p(N(Q.value.today_plus_confirmed)), 1)]),
						m("div", null, [n[41] ||= m("span", null, "处理中", -1), m("strong", null, p(N(Q.value.processing)), 1)]),
						m("div", null, [n[42] ||= m("span", null, "待支付", -1), m("strong", null, p(N(Q.value.awaiting_payment)), 1)])
					])),
					zt.value ? (t(), S("p", ot, "今日还没有提炼任务，进入工作台即可发起。")) : c("", !0),
					m("p", st, p(zt.value ? "提链工作台空闲" : `累计 ${N(Q.value.all)} 个提炼任务`), 1)
				]),
				m("article", ct, [m("header", lt, [n[44] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M12 2 2 7l10 5 10-5-10-5Z\" data-v-aefc1e2e></path><path d=\"m2 12 10 5 10-5\" data-v-aefc1e2e></path><path d=\"m2 17 10 5 10-5\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>套餐</h3><p data-v-aefc1e2e>账号套餐分布</p></div></div>", 1), m("button", {
					type: "button",
					class: "ov-link",
					"data-overview-action": "plans",
					onClick: n[6] ||= (e) => $("accounts")
				}, [...n[43] ||= [C("账号", -1), m("svg", {
					viewBox: "0 0 24 24",
					"aria-hidden": "true"
				}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]), V.value.length ? (t(), S(u, { key: 0 }, [m("div", ut, [m("strong", null, p(N(V.value.length)), 1), m("span", null, "种套餐 · " + p(N(me.value)) + " 个账号", 1)]), m("ul", dt, [(t(!0), S(u, null, i(V.value, (e) => (t(), S("li", { key: e.key }, [m("div", ft, [m("span", null, p(e.label), 1), m("small", null, p(N(e.count)) + " · " + p(F(e.count, me.value)) + "%", 1)]), m("div", pt, [m("i", { style: d({ width: Math.max(4, Math.round(e.count / pe.value * 100)) + "%" }) }, null, 4)])]))), 128))])], 64)) : (t(), S("p", mt, "还没有可用的套餐数据。"))]),
				m("article", ht, [
					m("header", gt, [n[46] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><circle cx=\"12\" cy=\"12\" r=\"9\" data-v-aefc1e2e></circle><path d=\"M3 12h18\" data-v-aefc1e2e></path><path d=\"M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3Z\" data-v-aefc1e2e></path></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>代理</h3><p data-v-aefc1e2e>网络出口</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "proxy",
						onClick: n[7] ||= (e) => $("proxy-traffic")
					}, [...n[45] ||= [C("查看", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", _t, [
						m("strong", null, p(N(q.value.active_leases)), 1),
						n[47] ||= m("span", null, "活跃出口", -1),
						m("em", vt, p(b(O)(q.value.platform)), 1)
					]),
					J.value.length ? (t(), S("ul", yt, [(t(!0), S(u, null, i(J.value, (e, r) => (t(), S("li", { key: r }, [
						n[48] ||= m("i", { "aria-hidden": "true" }, null, -1),
						m("span", null, p(e.endpoint || e.exit_ip || "活跃出口"), 1),
						m("small", null, p(e.region || e.provider || ""), 1)
					]))), 128))])) : (t(), S("p", bt, p(ve.value ? "注册代理未启用，当前没有活跃租约。" : `当前没有活跃的代理租约，新任务会走 ${b(O)(q.value.platform)}。`), 1)),
					J.value.length ? (t(), S("p", xt, [C(p(ve.value ? "注册代理未启用，已有租约仍保留" : `代理平台 ${b(O)(q.value.platform)}`), 1), _e.value ? (t(), S(u, { key: 0 }, [C(" · 另有 " + p(_e.value) + " 个活跃出口", 1)], 64)) : c("", !0)])) : c("", !0)
				]),
				m("article", St, [
					m("header", Ct, [n[50] ||= l("<div class=\"ov-card-title\" data-v-aefc1e2e><span class=\"ov-icon\" data-v-aefc1e2e><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-aefc1e2e><path d=\"M9 5h11\" data-v-aefc1e2e></path><path d=\"M9 12h11\" data-v-aefc1e2e></path><path d=\"M9 19h11\" data-v-aefc1e2e></path><circle cx=\"4\" cy=\"5\" r=\"1\" data-v-aefc1e2e></circle><circle cx=\"4\" cy=\"12\" r=\"1\" data-v-aefc1e2e></circle><circle cx=\"4\" cy=\"19\" r=\"1\" data-v-aefc1e2e></circle></svg></span><div data-v-aefc1e2e><h3 data-v-aefc1e2e>任务</h3><p data-v-aefc1e2e>注册流水线与队列</p></div></div>", 1), m("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "jobs",
						onClick: n[8] ||= (e) => $("tasks")
					}, [...n[49] ||= [C("任务中心", -1), m("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [m("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					m("div", wt, [
						m("section", Tt, [n[54] ||= m("h4", null, "当前队列", -1), m("div", Et, [
							m("div", null, [n[51] ||= m("span", null, "运行中", -1), m("strong", null, p(N(U.value.running)), 1)]),
							m("div", null, [n[52] ||= m("span", null, "待处理", -1), m("strong", null, p(N(U.value.pending)), 1)]),
							m("div", null, [n[53] ||= m("span", null, "停止中", -1), m("strong", null, p(N(U.value.stopping)), 1)])
						])]),
						m("section", Dt, [m("h4", null, [n[55] ||= C("今日结果 ", -1), m("small", null, p(H.value.today), 1)]), m("div", Ot, [
							m("div", null, [n[56] ||= m("span", null, "成功", -1), m("strong", kt, p(N(W.value.success)), 1)]),
							m("div", null, [n[57] ||= m("span", null, "部分成功", -1), m("strong", At, p(N(W.value.partial_success)), 1)]),
							m("div", null, [n[58] ||= m("span", null, "失败", -1), m("strong", jt, p(N(W.value.failed)), 1)])
						])]),
						m("section", Mt, [
							m("h4", null, [n[59] ||= C("累计结果 ", -1), m("small", null, p(N(H.value.total)) + " 个任务", 1)]),
							K.value.length ? (t(), S("div", Nt, [(t(!0), S(u, null, i(K.value, (e) => (t(), S("i", {
								key: e.key,
								style: d({
									width: e.value / Math.max(1, H.value.total) * 100 + "%",
									background: e.color
								})
							}, null, 4))), 128))])) : (t(), S("div", Pt)),
							m("div", Ft, [(t(!0), S(u, null, i(K.value, (e) => (t(), S("span", { key: e.key }, [m("i", { style: d({ background: e.color }) }, null, 4), C(p(e.label) + " " + p(N(e.value)), 1)]))), 128)), K.value.length ? c("", !0) : (t(), S("span", It, "暂无累计结果"))])
						])
					]),
					he.value ? (t(), S("p", Lt, "注册功能未启用，历史任务仍可查看。")) : c("", !0)
				])
			])) : c("", !0)
		], 2));
	}
}), [["__scopeId", "data-v-aefc1e2e"]]);
// src/api/dashboard.ts
async function Rt(e, t) {
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
function zt(e = (e, t) => w(e, t), t) {
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
			let i = await Rt(r, e);
			if (typeof i != "object" || !i || !("ok" in i) || i.ok !== !0) throw new T("能力检查返回无效数据", 200);
			return i;
		}
	};
}
// src/dashboard.ts
function Bt(e, t = {}) {
	let n = v(Q, {
		api: t.api || zt(void 0, t.pendingCapabilities),
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
export { Bt as mountDashboard };
