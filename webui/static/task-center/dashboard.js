import { C as e, F as t, H as n, K as r, L as i, M as a, S as o, _ as s, b as c, d as l, dt as u, et as d, ft as f, h as p, j as m, lt as h, m as g, n as _, o as v, st as y, t as b, v as x, x as S } from "./_plugin-vue_export-helper-Btipf5Px.js";
import { r as C, t as w } from "./client-B5R_MNgP.js";
// src/features/dashboard/useDashboard.ts
var ee = 2e4, T = (e) => Number(e || 0);
function te(e) {
	return !e || typeof e != "object" || e.ok !== !0 ? null : {
		today_extracted: T(e.today_extracted),
		today_plus_confirmed: T(e.today_plus_confirmed),
		awaiting_payment: T(e.awaiting_payment),
		processing: T(e.processing),
		all: T(e.all),
		providers: Array.isArray(e.providers) ? e.providers.filter((e) => e && typeof e == "object") : []
	};
}
function E(e) {
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
function D(e, t = {}) {
	let r = d(null), i = d(null), o = d({}), s = d(null), c = d(!1), l = d(""), u = d(null), f = d(null), p = d(null), h = d(!1), _ = d(""), v = d(null), y = d(!!t.visible), b = d(!1), x, S, C, w, T, E = "", D = !1, O = !1, k = 0, A = 0, j = {};
	function ne(t, n) {
		if (O || !y.value || document.hidden || !e.registrationDaily) return Promise.resolve();
		let r = t !== void 0 || n !== void 0, i = r ? t || void 0 : j.from, a = r ? n || void 0 : j.to, o = JSON.stringify([i || "", a || ""]);
		if (T && E === o) return T;
		j = {
			from: i,
			to: a
		}, r && (f.value = {
			from: i,
			to: a
		});
		let d = ++A;
		C?.abort(), C = new AbortController(), c.value = !0, l.value = "";
		let m = C.signal, h = (async () => {
			try {
				let t = await e.registrationDaily?.(i, a, m);
				if (d !== A || !y.value || document.hidden) return;
				if (!t || t.ok === !1) throw Error(t?.message || "每日注册统计读取失败");
				s.value = t, p.value = {
					from: typeof t.date_from == "string" ? t.date_from : i,
					to: typeof t.date_to == "string" ? t.date_to : a
				}, u.value = typeof t.updated_at == "string" ? t.updated_at : (/* @__PURE__ */ new Date()).toISOString();
			} catch (e) {
				d === A && !String(e?.name || "").includes("Abort") && (l.value = e?.message || "每日注册统计读取失败");
			} finally {
				d === A && (c.value = !1, T = void 0);
			}
		})();
		return T = h, E = o, h;
	}
	function M(e) {
		O || y.value === !!e || (y.value = !!e, k++, A++, S?.abort(), C?.abort(), w = void 0, T = void 0, D = !1, y.value ? (N(), P(!0)) : (x && window.clearInterval(x), x = void 0, h.value = !1, c.value = !1, E = ""));
	}
	function N() {
		x && window.clearInterval(x), x = window.setInterval(() => void P(!0), ee);
	}
	function P(n = !1) {
		if (O || !y.value || document.hidden) return Promise.resolve();
		let a = n && b.value;
		if (w) return !a && D && (h.value = !0), w;
		ne(j.from, j.to);
		let s = ++k;
		S?.abort(), S = new AbortController(), D = !0, a || (h.value = !0), n || (_.value = "");
		let c = S.signal, l = () => s === k && y.value && !document.hidden, u = (async () => {
			try {
				let n = await e.dashboard(c);
				if (!l()) return;
				r.value = n, b.value = !0, _.value = "", v.value = Date.now(), t.onReady?.();
			} catch (e) {
				l() && !String(e?.name || "").includes("Abort") && (_.value = e?.message || "总览加载失败", t.notify?.(`总览加载失败：${_.value}`));
			} finally {
				s === k && (D = !1, h.value = !1);
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
	let F = () => {
		!document.hidden && y.value ? P(!0) : (k++, A++, S?.abort(), C?.abort(), w = void 0, T = void 0, E = "", D = !1, h.value = !1, c.value = !1);
	};
	a(() => {
		document.addEventListener("visibilitychange", F), y.value && (N(), P());
	}), m(() => {
		O = !0, y.value = !1, k++, A++, w = void 0, T = void 0, E = "", D = !1, h.value = !1, c.value = !1, document.removeEventListener("visibilitychange", F), S?.abort(), C?.abort(), x && window.clearInterval(x), x = void 0;
	}), n(() => t.visible, (e) => M(!!e));
	let re = g(() => !!r.value);
	return {
		data: r,
		extract: i,
		caps: o,
		daily: s,
		dailyLoading: c,
		dailyError: l,
		dailyUpdatedAt: u,
		dailyRequestedRange: f,
		dailyDisplayedRange: p,
		dailyScopeCurrent: g(() => !s.value || !f.value || f.value.from === p.value?.from && f.value.to === p.value?.to),
		loading: h,
		error: _,
		updatedAt: v,
		visible: y,
		hasData: re,
		load: P,
		loadDaily: ne,
		setVisible: M
	};
}
// src/features/dashboard/DailyRegistrationStats.vue?vue&type=script&setup=true&lang.ts
var O = {
	class: "daily-stats",
	"aria-labelledby": "daily-registration-title"
}, k = { class: "daily-stats-head" }, A = { class: "daily-stats-meta" }, j = { "data-daily-range": "" }, ne = {
	class: "daily-stats-controls",
	role: "group",
	"aria-label": "统计日期范围"
}, M = [
	"data-daily-range-3",
	"data-daily-range-7",
	"data-daily-range-30",
	"aria-pressed",
	"onClick"
], N = ["aria-pressed"], P = {
	key: 0,
	class: "daily-stats-error",
	"data-daily-error": "",
	role: "alert"
}, F = ["disabled"], re = {
	key: 1,
	class: "daily-stats-stale",
	"data-daily-stale": "",
	role: "status"
}, I = {
	key: 2,
	class: "daily-stats-loading",
	"aria-live": "polite"
}, L = {
	key: 0,
	class: "daily-charts"
}, ie = {
	class: "daily-section",
	"aria-labelledby": "daily-total-title"
}, ae = {
	class: "daily-quantity-chart",
	role: "group",
	"aria-label": "每日账号总数柱形图"
}, oe = {
	class: "daily-chart-axis",
	"data-daily-axis": ""
}, se = { "aria-hidden": "true" }, ce = { class: "daily-chart-scroll" }, R = {
	class: "daily-chart-grid",
	"aria-hidden": "true"
}, le = [
	"data-daily-bar",
	"aria-label",
	"aria-pressed",
	"tabindex",
	"onClick",
	"onFocus",
	"onKeydown"
], ue = { "data-daily-account-total": "" }, z = {
	class: "daily-quantity-track",
	"aria-hidden": "true"
}, de = { class: "daily-date-label" }, B = {
	class: "daily-section",
	"aria-labelledby": "daily-presence-title"
}, fe = {
	class: "daily-presence-list",
	role: "region",
	"aria-label": "每日有无优惠占比列表",
	tabindex: "0"
}, V = ["data-daily-presence"], pe = { class: "daily-presence-date" }, me = ["aria-label"], H = ["data-presence-segment"], he = { class: "daily-presence-values" }, U = {
	key: 1,
	class: "daily-data-pending"
}, W = {
	key: 1,
	class: "daily-data-pending"
}, G = {
	key: 1,
	class: "daily-stats-empty"
}, K = {
	key: 2,
	class: "daily-stats-summary"
}, ge = /*#__PURE__*/ b(/* @__PURE__ */ e({
	__name: "DailyRegistrationStats",
	props: { state: {} },
	setup(e) {
		let a = e, o = d("3"), c = d(""), m = d(""), _ = d(""), y = g(() => Array.isArray(a.state.data?.rows) ? a.state.data.rows : []), b = g(() => ({
			from: a.state.data?.date_from || y.value[0]?.date || "",
			to: a.state.data?.date_to || y.value[y.value.length - 1]?.date || ""
		})), C = g(() => b.value.from && b.value.to ? `${b.value.from} 至 ${b.value.to}` : "日期范围待返回"), w = g(() => a.state.data?.cohort_basis_label || "按账号首次入库日期统计"), ee = g(() => a.state.updatedAt ? `更新于 ${new Date(a.state.updatedAt).toLocaleString("zh-CN", {
			hour12: !1,
			timeZone: "Asia/Shanghai"
		})}` : a.state.loading ? "正在读取…" : "尚未读取"), T = g(() => a.state.error && a.state.data ? `${a.state.error}，当前仍显示上次成功的统计。` : a.state.error), te = g(() => y.value.map((e) => ({
			row: e,
			total: q(e.accounts_total)
		}))), E = g(() => Math.max(1, Math.ceil(Math.max(0, ...te.value.map((e) => e.total ?? 0)) / 4))), D = g(() => E.value * 4), ge = g(() => [
			4,
			3,
			2,
			1,
			0
		].map((e) => e * E.value)), _e = [
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
		];
		function q(e) {
			if (e == null) return null;
			let t = Number(e);
			return Number.isFinite(t) ? t : null;
		}
		function J(e) {
			let t = q(e);
			return t === null ? "—" : new Intl.NumberFormat("zh-CN").format(t);
		}
		function ve(e, t) {
			let n = q(e.accounts_total);
			if (!n || n < 0 || t < 0) return "—";
			let r = t / n * 100;
			return r > 0 && r < .01 ? "<0.01%" : `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(r)}%`;
		}
		function ye(e, t) {
			let n = q(e.accounts_total);
			return n && n > 0 ? Math.max(0, Math.min(100, t / n * 100)) : 0;
		}
		function Y(e) {
			let t = e.promotion_presence, n = q(e.accounts_total);
			if (!t || n === null || n < 0) return null;
			let r = _e.map((e) => q(t[e.key]));
			return r.some((e) => e === null || e < 0) || r.reduce((e, t) => e + (t ?? 0), 0) !== n ? null : _e.map((e, t) => ({
				...e,
				count: r[t]
			}));
		}
		function be(e) {
			return `${e.date}，账号总数 ${J(e.accounts_total)}，点击选择日期`;
		}
		function xe(e) {
			_.value = e;
		}
		function Se(e, t) {
			let n = t;
			if (e.key === "ArrowRight") n = Math.min(y.value.length - 1, t + 1);
			else if (e.key === "ArrowLeft") n = Math.max(0, t - 1);
			else if (e.key === "Home") n = 0;
			else if (e.key === "End") n = y.value.length - 1;
			else return;
			e.preventDefault();
			let r = y.value[n];
			if (!r) return;
			xe(r.date);
			let i = e.currentTarget.parentElement?.querySelectorAll("[data-daily-bar]");
			i?.[n]?.focus({ preventScroll: !0 }), i?.[n]?.scrollIntoView?.({
				block: "nearest",
				inline: "nearest"
			});
		}
		function Ce(e, t) {
			let n = /* @__PURE__ */ new Date(`${e}T00:00:00Z`);
			return n.setUTCDate(n.getUTCDate() + t), n.toISOString().slice(0, 10);
		}
		function we() {
			let e = new Intl.DateTimeFormat("en-US", {
				timeZone: "Asia/Shanghai",
				year: "numeric",
				month: "2-digit",
				day: "2-digit"
			}).formatToParts(/* @__PURE__ */ new Date()), t = Object.fromEntries(e.filter((e) => e.type !== "literal").map((e) => [e.type, e.value]));
			return `${t.year}-${t.month}-${t.day}`;
		}
		function Te(e) {
			o.value = e;
			let t = we();
			a.state.load(Ce(t, -(Number(e) - 1)), t);
		}
		function Ee() {
			o.value = "custom", c.value = a.state.displayedRange?.from || b.value.from, m.value = a.state.displayedRange?.to || b.value.to;
		}
		function De() {
			o.value === "custom" && c.value && m.value && c.value <= m.value && a.state.load(c.value, m.value);
		}
		return n(y, (e) => {
			e.some((e) => e.date === _.value) || (_.value = e[0]?.date || "");
		}, { immediate: !0 }), (n, a) => (t(), x("section", O, [
			p("header", k, [p("div", null, [a[3] ||= p("h2", { id: "daily-registration-title" }, "每日账号注册与优惠", -1), p("p", null, "北京时间 · " + f(w.value) + " · 包含归档账号", 1)]), p("div", A, [p("span", j, f(C.value), 1), p("span", null, f(ee.value), 1)])]),
			p("div", ne, [
				(t(), x(l, null, i([
					"3",
					"7",
					"30"
				], (e) => p("button", {
					key: e,
					type: "button",
					"data-daily-range-3": e === "3" ? "" : void 0,
					"data-daily-range-7": e === "7" ? "" : void 0,
					"data-daily-range-30": e === "30" ? "" : void 0,
					class: h({ active: o.value === e }),
					"aria-pressed": o.value === e,
					onClick: (t) => Te(e)
				}, "近 " + f(e) + " 天", 11, M)), 64)),
				p("button", {
					type: "button",
					"data-daily-range-custom": "",
					class: h({ active: o.value === "custom" }),
					"aria-pressed": o.value === "custom",
					onClick: Ee
				}, "自定义", 10, N),
				o.value === "custom" ? (t(), x(l, { key: 0 }, [p("label", null, [a[4] ||= S("开始日期", -1), r(p("input", {
					"onUpdate:modelValue": a[0] ||= (e) => c.value = e,
					"aria-label": "开始日期",
					type: "date",
					onChange: De
				}, null, 544), [[v, c.value]])]), p("label", null, [a[5] ||= S("结束日期", -1), r(p("input", {
					"onUpdate:modelValue": a[1] ||= (e) => m.value = e,
					"aria-label": "结束日期",
					type: "date",
					onChange: De
				}, null, 544), [[v, m.value]])])], 64)) : s("", !0)
			]),
			e.state.error ? (t(), x("div", P, [p("span", null, f(T.value), 1), p("button", {
				type: "button",
				"data-daily-retry": "",
				disabled: e.state.loading,
				onClick: a[2] ||= (t) => e.state.load()
			}, "重试", 8, F)])) : s("", !0),
			e.state.data && !e.state.scopeCurrent ? (t(), x("div", re, f(e.state.loading ? "正在读取新日期范围，当前仍显示上一成功范围。" : "新日期范围读取失败，当前仍显示上一成功范围，请重试。"), 1)) : s("", !0),
			e.state.loading && !e.state.data ? (t(), x("div", I, "正在读取每日账号与优惠统计…")) : e.state.data ? (t(), x(l, { key: 3 }, [y.value.length ? (t(), x("div", L, [p("section", ie, [a[7] ||= p("div", { class: "daily-section-heading" }, [p("h3", { id: "daily-total-title" }, "每日账号总数"), p("p", null, "每个账号只归属首次入库的一天")], -1), p("div", ae, [p("div", oe, [a[6] ||= p("span", null, "账号数", -1), p("div", se, [(t(!0), x(l, null, i(ge.value, (e) => (t(), x("span", {
				key: e,
				"data-daily-axis-tick": ""
			}, f(J(e)), 1))), 128))])]), p("div", ce, [p("div", {
				class: "daily-quantity-plot",
				style: u({
					gridTemplateColumns: `repeat(${y.value.length},minmax(76px,1fr))`,
					minWidth: `${y.value.length * 80}px`
				})
			}, [p("div", R, [(t(!0), x(l, null, i(ge.value, (e) => (t(), x("i", { key: e }))), 128))]), (t(!0), x(l, null, i(te.value, (e, n) => (t(), x("button", {
				key: e.row.date,
				type: "button",
				class: h(["daily-bar-column", { selected: e.row.date === _.value }]),
				"data-daily-bar": e.row.date,
				"aria-label": be(e.row),
				"aria-pressed": e.row.date === _.value,
				tabindex: e.row.date === _.value ? 0 : -1,
				onClick: (t) => xe(e.row.date),
				onFocus: (t) => xe(e.row.date),
				onKeydown: (e) => Se(e, n)
			}, [
				p("strong", ue, f(J(e.total)), 1),
				p("span", z, [p("i", {
					"data-daily-quantity": "",
					style: u({ height: `${(e.total ?? 0) / D.value * 100}%` })
				}, null, 4)]),
				p("span", de, f(e.row.date.slice(5)), 1)
			], 42, le))), 128))], 4)])])]), p("section", B, [a[8] ||= p("div", { class: "daily-section-heading" }, [p("h3", { id: "daily-presence-title" }, "每日有无优惠占比"), p("p", null, "按账号去重；未查询或结果不完整的账号列为待确认")], -1), p("div", fe, [(t(!0), x(l, null, i(y.value, (e) => (t(), x("article", {
				key: e.date,
				class: "daily-presence-row",
				"data-daily-presence": e.date
			}, [p("div", pe, [p("strong", null, f(e.date), 1), p("span", null, f(J(e.accounts_total)) + " 个账号", 1)]), Y(e) ? (t(), x(l, { key: 0 }, [e.accounts_total > 0 ? (t(), x(l, { key: 0 }, [p("div", {
				class: "daily-presence-track",
				role: "img",
				"aria-label": Y(e).map((t) => `${t.label} ${J(t.count)}个，${ve(e, t.count)}`).join("，")
			}, [(t(!0), x(l, null, i(Y(e).filter((e) => e.count > 0), (n) => (t(), x("i", {
				key: n.key,
				"data-presence-segment": n.key,
				style: u({
					width: `${ye(e, n.count)}%`,
					backgroundColor: n.color
				})
			}, null, 12, H))), 128))], 8, me), p("div", he, [(t(!0), x(l, null, i(Y(e), (n) => (t(), x("span", { key: n.key }, [
				p("i", {
					style: u({ backgroundColor: n.color }),
					"aria-hidden": "true"
				}, null, 4),
				S(f(n.label) + " " + f(J(n.count)) + " 个 · ", 1),
				p("strong", null, f(ve(e, n.count)), 1)
			]))), 128))])], 64)) : (t(), x("p", U, "暂无账号 · 占比 —"))], 64)) : (t(), x("p", W, "有无优惠数据待查"))], 8, V))), 128))])])])) : (t(), x("p", G, "所选日期暂无账号统计。")), e.state.data.summary ? (t(), x("div", K, [a[9] ||= p("strong", null, "区间汇总", -1), p("span", null, "账号总数 " + f(J(e.state.data.summary.accounts_total)) + " · 包含归档账号", 1)])) : s("", !0)], 64)) : s("", !0)
		]));
	}
}), [["__scopeId", "data-v-3264019f"]]), _e = { class: "ov-section-head" }, q = { class: "ov-section-actions" }, J = { class: "ov-updated" }, ve = ["disabled"], ye = {
	key: 0,
	class: "ov-error",
	role: "alert"
}, Y = {
	key: 1,
	class: "ov-alerts",
	"aria-label": "需要关注"
}, be = ["onClick"], xe = {
	key: 2,
	class: "ov-skeleton",
	"aria-label": "正在读取总览"
}, Se = {
	key: 3,
	class: "ov-pulse",
	"aria-label": "服务脉搏"
}, Ce = ["title", "onClick"], we = { class: "ov-pulse-top" }, Te = { class: "ov-pulse-badge" }, Ee = {
	key: 4,
	class: "ov-grid"
}, De = {
	class: "ov-card ov-card--email",
	"data-overview-card": "email",
	style: {
		"--accent": "#1f9d75",
		"--accent-soft": "#e7f6f0"
	}
}, Oe = { class: "ov-card-head" }, ke = { class: "ov-figure" }, Ae = { class: "ov-mini-grid ov-mini-grid--3" }, je = {
	key: 0,
	class: "ov-bars"
}, Me = { class: "ov-bar-label" }, Ne = {
	key: 1,
	class: "ov-empty"
}, Pe = {
	key: 2,
	class: "ov-foot"
}, Fe = {
	key: 3,
	class: "ov-foot"
}, Ie = {
	class: "ov-card ov-card--accounts",
	"data-overview-card": "accounts",
	style: {
		"--accent": "#5b5ce2",
		"--accent-soft": "#eeeefe"
	}
}, Le = { class: "ov-card-head" }, Re = { class: "ov-figure" }, ze = {
	class: "ov-split",
	"aria-hidden": "true"
}, Be = { class: "ov-legend" }, Ve = { class: "ov-mini-grid ov-mini-grid--2" }, He = { class: "ov-meter" }, Ue = { class: "ov-bar" }, We = {
	class: "ov-card ov-card--codex",
	"data-overview-card": "codex",
	style: {
		"--accent": "#377dff",
		"--accent-soft": "#e9f1ff"
	}
}, Ge = { class: "ov-card-head" }, Ke = { class: "ov-figure" }, qe = {
	key: 0,
	class: "ov-chip is-warn"
}, Je = { class: "ov-bar-label" }, Ye = { class: "ov-bar ov-bar--thick" }, Xe = { class: "ov-mini-grid ov-mini-grid--3" }, Ze = { class: "ov-foot" }, Qe = {
	class: "ov-card ov-card--extract",
	"data-overview-card": "extract",
	style: {
		"--accent": "#d97706",
		"--accent-soft": "#fdf3e3"
	}
}, $e = { class: "ov-card-head" }, et = { class: "ov-figure" }, tt = {
	key: 0,
	class: "ov-mini-grid ov-mini-grid--3"
}, nt = {
	key: 1,
	class: "ov-empty"
}, rt = { class: "ov-foot" }, it = {
	class: "ov-card ov-card--plans",
	"data-overview-card": "plans",
	style: {
		"--accent": "#8b5cf6",
		"--accent-soft": "#f3edff"
	}
}, at = { class: "ov-card-head" }, ot = { class: "ov-figure ov-figure--small" }, st = { class: "ov-bars" }, ct = { class: "ov-bar-label" }, lt = { class: "ov-bar" }, ut = {
	key: 1,
	class: "ov-empty"
}, dt = {
	class: "ov-card ov-card--proxy",
	"data-overview-card": "proxy",
	style: {
		"--accent": "#0e9aa7",
		"--accent-soft": "#e6f6f7"
	}
}, ft = { class: "ov-card-head" }, pt = { class: "ov-figure" }, mt = { class: "ov-chip" }, ht = {
	key: 0,
	class: "ov-lease-list"
}, gt = {
	key: 1,
	class: "ov-empty"
}, _t = {
	key: 2,
	class: "ov-foot"
}, vt = {
	class: "ov-card ov-card--jobs",
	"data-overview-card": "jobs",
	style: {
		"--accent": "#475569",
		"--accent-soft": "#eef1f5"
	}
}, yt = { class: "ov-card-head" }, bt = { class: "ov-task-columns" }, xt = { class: "ov-task-block" }, St = { class: "ov-mini-grid ov-mini-grid--3" }, Ct = { class: "ov-task-block" }, wt = { class: "ov-mini-grid ov-mini-grid--3" }, Tt = { class: "is-ok" }, Et = { class: "is-warn" }, Dt = { class: "is-danger" }, Ot = { class: "ov-task-block ov-task-block--wide" }, kt = {
	key: 0,
	class: "ov-stack",
	"aria-hidden": "true"
}, At = {
	key: 1,
	class: "ov-stack ov-stack--empty",
	"aria-hidden": "true"
}, jt = { class: "ov-stack-legend" }, Mt = {
	key: 0,
	class: "ov-stack-empty-text"
}, Nt = {
	key: 0,
	class: "ov-foot"
}, Pt = /*#__PURE__*/ b(/* @__PURE__ */ e({
	__name: "DashboardPage",
	props: {
		api: {},
		deps: {}
	},
	setup(e, { expose: n }) {
		let r = e, m = D(r.api, r.deps), { data: _, extract: v, caps: b, daily: C, dailyLoading: w, dailyError: ee, dailyUpdatedAt: T, dailyRequestedRange: te, dailyDisplayedRange: O, dailyScopeCurrent: k, loading: A, error: j, updatedAt: ne } = m, M = d(!1);
		a(() => {
			M.value = !0;
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
		})[e] || e, I = g(() => _.value?.accounts || {}), L = g(() => _.value?.email?.supply || {}), ie = g(() => (Array.isArray(L.value?.sources) ? L.value.sources : Array.isArray(_.value?.email?.sources) ? _.value.email.sources : []).filter((e) => e?.kind === "local_pool")), ae = g(() => ie.value.filter((e) => P(e.total) > 0 || P(e.available) > 0)), oe = g(() => Math.max(0, ie.value.length - ae.value.length)), se = g(() => L.value?.status === "error" ? "读取失败" : P(L.value?.available)), ce = g(() => L.value?.status === "error" ? "—" : N(se.value)), R = g(() => P(L.value?.total)), le = g(() => P(L.value?.used)), ue = g(() => P(L.value?.failed) + P(L.value?.disabled)), z = g(() => L.value?.status === "error" ? "danger" : R.value > 0 && P(L.value?.available) === 0 ? "warn" : P(L.value?.available) > 0 ? "ok" : "idle"), de = g(() => L.value?.status === "error" ? "读取失败" : R.value === 0 ? "未配置" : P(L.value?.available) === 0 ? "库存耗尽" : "库存正常"), B = g(() => _.value?.codex || {}), fe = g(() => P(B.value.pending) > 0 ? "warn" : P(B.value.total) > 0 ? "ok" : "idle"), V = g(() => Object.entries(I.value?.plans || {}).map(([e, t]) => ({
			key: e,
			label: re(e),
			count: P(t)
		})).sort((e, t) => t.count - e.count)), pe = g(() => Math.max(1, ...V.value.map((e) => e.count))), me = g(() => V.value.reduce((e, t) => e + t.count, 0)), H = g(() => _.value?.jobs || {}), he = g(() => b.value?.features?.register?.enabled === !1), U = g(() => ({ ...H.value?.counts || {} })), W = g(() => ({ ...H.value?.today_counts || {} })), G = g(() => P(U.value.pending) + P(U.value.running) + P(U.value.stopping));
		g(() => P(W.value.success) + P(W.value.partial_success) + P(W.value.failed));
		let K = g(() => [
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
		].filter((e) => e.value > 0)), Pt = g(() => G.value > 0 ? "active" : P(W.value.failed) > 0 ? "warn" : "idle"), X = g(() => _.value?.proxy || {}), Z = g(() => Array.isArray(X.value.leases) ? X.value.leases.slice(0, 3) : []), Ft = g(() => Math.max(0, P(X.value.active_leases) - Z.value.length)), It = g(() => b.value?.proxy?.registration?.enabled === !1), Lt = g(() => P(X.value.active_leases) > 0 ? "ok" : "idle"), Q = g(() => v.value || {}), Rt = g(() => P(Q.value.processing) > 0 ? "active" : "idle"), zt = g(() => P(Q.value.all) === 0 && P(Q.value.today_extracted) === 0 && P(Q.value.processing) === 0 && P(Q.value.awaiting_payment) === 0), Bt = g(() => [
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
				value: N(X.value.active_leases),
				badge: P(X.value.active_leases) > 0 ? `${N(X.value.active_leases)} 出口` : E(X.value.platform),
				hint: E(X.value.platform),
				tone: Lt.value,
				tab: "proxy-traffic"
			},
			{
				id: "jobs",
				label: "任务",
				value: N(G.value),
				badge: G.value > 0 ? `运行 ${N(G.value)}` : P(W.value.failed) > 0 ? `异常 ${N(W.value.failed)}` : "空闲",
				hint: `累计 ${N(H.value.total)}`,
				tone: Pt.value,
				tab: "tasks"
			}
		]), Vt = g(() => {
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
		}), Ht = g(() => ne.value ? `数据更新 ${new Date(ne.value).toLocaleTimeString("zh-CN", { hour12: !1 })}` : A.value ? "正在读取…" : "尚未读取"), $ = (e) => r.deps.onNavigate?.(e), Ut = g(() => ({
			data: C.value,
			loading: w.value,
			error: ee.value,
			updatedAt: T.value,
			requestedRange: te.value,
			displayedRange: O.value,
			scopeCurrent: k.value,
			load: m.loadDaily
		}));
		return n({
			load: m.load,
			setVisible: m.setVisible,
			openCustomizer: () => {},
			closeCustomizer: () => {},
			resetLayout: () => {}
		}), (e, n) => (t(), x("div", { class: h(["ov-page", { "is-mounted": M.value }]) }, [
			p("div", _e, [n[11] ||= p("div", { class: "ov-section-title" }, [p("h2", null, "服务脉搏"), p("p", null, "邮箱 · 账号 · Codex · 套餐 · 提炼 · 代理 · 任务")], -1), p("div", q, [p("span", J, [n[9] ||= p("i", { "aria-hidden": "true" }, null, -1), S(f(Ht.value), 1)]), p("button", {
				type: "button",
				class: "ov-refresh ui-refresh-button",
				disabled: y(A),
				onClick: n[0] ||= (e) => y(m).load()
			}, [n[10] ||= p("svg", {
				viewBox: "0 0 24 24",
				"aria-hidden": "true"
			}, [p("path", { d: "M20 11a8 8 0 1 0-2.3 6.7" }), p("path", { d: "M20 4v7h-7" })], -1), S(" " + f(y(A) ? "刷新中" : "刷新"), 1)], 8, ve)])]),
			y(j) ? (t(), x("div", ye, [p("div", null, [n[12] ||= p("strong", null, "总览加载失败", -1), p("span", null, f(y(j)), 1)]), p("button", {
				type: "button",
				onClick: n[1] ||= (e) => y(m).load()
			}, "重试")])) : s("", !0),
			Vt.value.length ? (t(), x("section", Y, [(t(!0), x(l, null, i(Vt.value, (e) => (t(), x("article", {
				key: e.text,
				class: h(["ov-alert", `is-${e.tone}`])
			}, [
				n[13] ||= p("svg", {
					viewBox: "0 0 24 24",
					"aria-hidden": "true"
				}, [
					p("path", { d: "M12 9v4" }),
					p("path", { d: "M12 17h.01" }),
					p("path", { d: "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" })
				], -1),
				p("p", null, f(e.text), 1),
				p("button", {
					type: "button",
					onClick: (t) => $(e.tab)
				}, f(e.label), 9, be)
			], 2))), 128))])) : s("", !0),
			!y(_) && y(A) ? (t(), x("section", xe, [...n[14] ||= [p("div", { class: "ov-skeleton-pulse" }, null, -1), p("div", { class: "ov-skeleton-grid" }, [
				p("i"),
				p("i"),
				p("i"),
				p("i")
			], -1)]])) : s("", !0),
			y(_) ? (t(), x("nav", Se, [(t(!0), x(l, null, i(Bt.value, (e) => (t(), x("button", {
				key: e.id,
				type: "button",
				class: h(["ov-pulse-item", [`is-${e.tone}`, { "is-zero": e.value === "0" }]]),
				title: `${e.label} · ${e.hint}`,
				onClick: (t) => $(e.tab)
			}, [p("span", we, [n[15] ||= p("i", { "aria-hidden": "true" }, null, -1), S(f(e.label), 1)]), p("span", Te, [p("strong", null, f(e.badge), 1)])], 10, Ce))), 128))])) : s("", !0),
			o(ge, { state: Ut.value }, null, 8, ["state"]),
			y(_) ? (t(), x("div", Ee, [
				p("article", De, [
					p("header", Oe, [n[17] ||= c("<div class=\"ov-card-title\" data-v-0fbfb63f><span class=\"ov-icon\" data-v-0fbfb63f><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-0fbfb63f><rect x=\"3\" y=\"5\" width=\"18\" height=\"14\" rx=\"2\" data-v-0fbfb63f></rect><path d=\"m3 7 9 6 9-6\" data-v-0fbfb63f></path></svg></span><div data-v-0fbfb63f><h3 data-v-0fbfb63f>邮箱池</h3><p data-v-0fbfb63f>本地库存与来源</p></div></div>", 1), p("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "email",
						onClick: n[2] ||= (e) => $("outlook")
					}, [...n[16] ||= [S("管理", -1), p("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					p("div", ke, [
						p("strong", { class: h({ "is-danger": z.value === "warn" }) }, f(ce.value), 3),
						n[18] ||= p("span", null, "可用", -1),
						z.value === "ok" ? s("", !0) : (t(), x("em", {
							key: 0,
							class: h(["ov-chip", `is-${z.value}`])
						}, f(de.value), 3))
					]),
					p("div", Ae, [
						p("div", null, [n[19] ||= p("span", null, "邮箱总量", -1), p("strong", null, f(N(R.value)), 1)]),
						p("div", null, [n[20] ||= p("span", null, "已使用", -1), p("strong", null, f(N(le.value)), 1)]),
						p("div", null, [n[21] ||= p("span", null, "停用 / 失败", -1), p("strong", null, f(N(ue.value)), 1)])
					]),
					ae.value.length ? (t(), x("ul", je, [(t(!0), x(l, null, i(ae.value, (e) => (t(), x("li", { key: e.source }, [p("div", Me, [p("span", null, f(e.label), 1), p("small", null, f(P(e.available) === 0 ? "已用尽" : `可用 ${N(e.available)}`) + " / " + f(N(e.total)), 1)]), p("div", { class: h(["ov-bar", { "is-spent": P(e.available) === 0 && P(e.total) > 0 }]) }, [p("i", { style: u({ width: F(e.available, e.total) + "%" }) }, null, 4)], 2)]))), 128))])) : (t(), x("p", Ne, "还没有可统计的邮箱库存。")),
					oe.value ? (t(), x("p", Pe, "另有 " + f(oe.value) + " 个来源暂无库存 · 仅统计本地库存", 1)) : (t(), x("p", Fe, "仅统计本地库存，用完后需手动导入"))
				]),
				p("article", Ie, [
					p("header", Le, [n[23] ||= c("<div class=\"ov-card-title\" data-v-0fbfb63f><span class=\"ov-icon\" data-v-0fbfb63f><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-0fbfb63f><path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\" data-v-0fbfb63f></path><circle cx=\"9\" cy=\"7\" r=\"4\" data-v-0fbfb63f></circle><path d=\"M22 21v-2a4 4 0 0 0-3-3.9\" data-v-0fbfb63f></path></svg></span><div data-v-0fbfb63f><h3 data-v-0fbfb63f>账号</h3><p data-v-0fbfb63f>账号资产</p></div></div>", 1), p("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "accounts",
						onClick: n[3] ||= (e) => $("accounts")
					}, [...n[22] ||= [S("管理", -1), p("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					p("div", Re, [p("strong", null, f(N(I.value.active)), 1), n[24] ||= p("span", null, "活跃账号", -1)]),
					p("div", ze, [p("i", {
						class: "is-active",
						style: u({ width: F(I.value.active, I.value.total) + "%" })
					}, null, 4), p("i", {
						class: "is-idle",
						style: u({ width: F(I.value.archived, I.value.total) + "%" })
					}, null, 4)]),
					p("div", Be, [p("span", null, [n[25] ||= p("i", { style: { background: "#5b5ce2" } }, null, -1), S("活跃 " + f(N(I.value.active)), 1)]), p("span", null, [n[26] ||= p("i", { style: { background: "#d7dbe5" } }, null, -1), S("归档 " + f(N(I.value.archived)), 1)])]),
					p("div", Ve, [p("div", null, [n[27] ||= p("span", null, "账号总数", -1), p("strong", null, f(N(I.value.total)), 1)]), p("div", null, [n[28] ||= p("span", null, "Codex 就绪", -1), p("strong", null, f(N(I.value.codex_ready)), 1)])]),
					p("div", He, [
						n[29] ||= p("span", null, "Codex 就绪率", -1),
						p("div", Ue, [p("i", { style: u({ width: F(I.value.codex_ready, I.value.active) + "%" }) }, null, 4)]),
						p("strong", null, f(F(I.value.codex_ready, I.value.active)) + "%", 1)
					])
				]),
				p("article", We, [
					p("header", Ge, [n[31] ||= c("<div class=\"ov-card-title\" data-v-0fbfb63f><span class=\"ov-icon\" data-v-0fbfb63f><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-0fbfb63f><rect x=\"3\" y=\"11\" width=\"18\" height=\"10\" rx=\"2\" data-v-0fbfb63f></rect><path d=\"M7 11V7a5 5 0 0 1 10 0v4\" data-v-0fbfb63f></path></svg></span><div data-v-0fbfb63f><h3 data-v-0fbfb63f>Codex</h3><p data-v-0fbfb63f>授权凭证</p></div></div>", 1), p("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "codex",
						onClick: n[4] ||= (e) => $("codex")
					}, [...n[30] ||= [S("查看", -1), p("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					p("div", Ke, [
						p("strong", null, f(N(B.value.total)), 1),
						n[32] ||= p("span", null, "已导出凭证", -1),
						fe.value === "warn" ? (t(), x("em", qe, "待导出")) : s("", !0)
					]),
					p("div", Je, [n[33] ||= p("span", null, "导出进度", -1), p("small", null, f(N(B.value.exported)) + " / " + f(N(B.value.total)), 1)]),
					p("div", Ye, [p("i", { style: u({ width: F(B.value.exported, B.value.total) + "%" }) }, null, 4)]),
					p("div", Xe, [
						p("div", null, [n[34] ||= p("span", null, "已导出", -1), p("strong", null, f(N(B.value.exported)), 1)]),
						p("div", null, [n[35] ||= p("span", null, "待导出", -1), p("strong", null, f(N(B.value.pending)), 1)]),
						p("div", null, [n[36] ||= p("span", null, "账号就绪", -1), p("strong", null, f(N(I.value.codex_ready)), 1)])
					]),
					p("p", Ze, "账号 Codex 就绪 " + f(N(I.value.codex_ready)) + " · 覆盖 " + f(F(I.value.codex_ready, I.value.active)) + "% 活跃账号", 1)
				]),
				p("article", Qe, [
					p("header", $e, [n[38] ||= c("<div class=\"ov-card-title\" data-v-0fbfb63f><span class=\"ov-icon\" data-v-0fbfb63f><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-0fbfb63f><path d=\"m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z\" data-v-0fbfb63f></path><path d=\"M19 15.5 20 18l2.5 1-2.5 1L19 22l-1-2-2.5-1 2.5-1 1-2.5Z\" data-v-0fbfb63f></path></svg></span><div data-v-0fbfb63f><h3 data-v-0fbfb63f>提炼</h3><p data-v-0fbfb63f>提链工作台</p></div></div>", 1), p("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "extract",
						onClick: n[5] ||= (e) => $("extract-workbench")
					}, [...n[37] ||= [S("工作台", -1), p("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					p("div", et, [
						p("strong", null, f(N(Q.value.today_extracted)), 1),
						n[39] ||= p("span", null, "今日已提炼", -1),
						p("em", { class: h(["ov-chip", `is-${Rt.value}`]) }, f(Rt.value === "idle" ? "空闲" : "处理中"), 3)
					]),
					zt.value ? s("", !0) : (t(), x("div", tt, [
						p("div", null, [n[40] ||= p("span", null, "Plus 已确认", -1), p("strong", null, f(N(Q.value.today_plus_confirmed)), 1)]),
						p("div", null, [n[41] ||= p("span", null, "处理中", -1), p("strong", null, f(N(Q.value.processing)), 1)]),
						p("div", null, [n[42] ||= p("span", null, "待支付", -1), p("strong", null, f(N(Q.value.awaiting_payment)), 1)])
					])),
					zt.value ? (t(), x("p", nt, "今日还没有提炼任务，进入工作台即可发起。")) : s("", !0),
					p("p", rt, f(zt.value ? "提链工作台空闲" : `累计 ${N(Q.value.all)} 个提炼任务`), 1)
				]),
				p("article", it, [p("header", at, [n[44] ||= c("<div class=\"ov-card-title\" data-v-0fbfb63f><span class=\"ov-icon\" data-v-0fbfb63f><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-0fbfb63f><path d=\"M12 2 2 7l10 5 10-5-10-5Z\" data-v-0fbfb63f></path><path d=\"m2 12 10 5 10-5\" data-v-0fbfb63f></path><path d=\"m2 17 10 5 10-5\" data-v-0fbfb63f></path></svg></span><div data-v-0fbfb63f><h3 data-v-0fbfb63f>套餐</h3><p data-v-0fbfb63f>账号套餐分布</p></div></div>", 1), p("button", {
					type: "button",
					class: "ov-link",
					"data-overview-action": "plans",
					onClick: n[6] ||= (e) => $("accounts")
				}, [...n[43] ||= [S("账号", -1), p("svg", {
					viewBox: "0 0 24 24",
					"aria-hidden": "true"
				}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]), V.value.length ? (t(), x(l, { key: 0 }, [p("div", ot, [p("strong", null, f(N(V.value.length)), 1), p("span", null, "种套餐 · " + f(N(me.value)) + " 个账号", 1)]), p("ul", st, [(t(!0), x(l, null, i(V.value, (e) => (t(), x("li", { key: e.key }, [p("div", ct, [p("span", null, f(e.label), 1), p("small", null, f(N(e.count)) + " · " + f(F(e.count, me.value)) + "%", 1)]), p("div", lt, [p("i", { style: u({ width: Math.max(4, Math.round(e.count / pe.value * 100)) + "%" }) }, null, 4)])]))), 128))])], 64)) : (t(), x("p", ut, "还没有可用的套餐数据。"))]),
				p("article", dt, [
					p("header", ft, [n[46] ||= c("<div class=\"ov-card-title\" data-v-0fbfb63f><span class=\"ov-icon\" data-v-0fbfb63f><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-0fbfb63f><circle cx=\"12\" cy=\"12\" r=\"9\" data-v-0fbfb63f></circle><path d=\"M3 12h18\" data-v-0fbfb63f></path><path d=\"M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3Z\" data-v-0fbfb63f></path></svg></span><div data-v-0fbfb63f><h3 data-v-0fbfb63f>代理</h3><p data-v-0fbfb63f>网络出口</p></div></div>", 1), p("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "proxy",
						onClick: n[7] ||= (e) => $("proxy-traffic")
					}, [...n[45] ||= [S("查看", -1), p("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					p("div", pt, [
						p("strong", null, f(N(X.value.active_leases)), 1),
						n[47] ||= p("span", null, "活跃出口", -1),
						p("em", mt, f(y(E)(X.value.platform)), 1)
					]),
					Z.value.length ? (t(), x("ul", ht, [(t(!0), x(l, null, i(Z.value, (e, r) => (t(), x("li", { key: r }, [
						n[48] ||= p("i", { "aria-hidden": "true" }, null, -1),
						p("span", null, f(e.endpoint || e.exit_ip || "活跃出口"), 1),
						p("small", null, f(e.region || e.provider || ""), 1)
					]))), 128))])) : (t(), x("p", gt, f(It.value ? "注册代理未启用，当前没有活跃租约。" : `当前没有活跃的代理租约，新任务会走 ${y(E)(X.value.platform)}。`), 1)),
					Z.value.length ? (t(), x("p", _t, [S(f(It.value ? "注册代理未启用，已有租约仍保留" : `代理平台 ${y(E)(X.value.platform)}`), 1), Ft.value ? (t(), x(l, { key: 0 }, [S(" · 另有 " + f(Ft.value) + " 个活跃出口", 1)], 64)) : s("", !0)])) : s("", !0)
				]),
				p("article", vt, [
					p("header", yt, [n[50] ||= c("<div class=\"ov-card-title\" data-v-0fbfb63f><span class=\"ov-icon\" data-v-0fbfb63f><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-0fbfb63f><path d=\"M9 5h11\" data-v-0fbfb63f></path><path d=\"M9 12h11\" data-v-0fbfb63f></path><path d=\"M9 19h11\" data-v-0fbfb63f></path><circle cx=\"4\" cy=\"5\" r=\"1\" data-v-0fbfb63f></circle><circle cx=\"4\" cy=\"12\" r=\"1\" data-v-0fbfb63f></circle><circle cx=\"4\" cy=\"19\" r=\"1\" data-v-0fbfb63f></circle></svg></span><div data-v-0fbfb63f><h3 data-v-0fbfb63f>任务</h3><p data-v-0fbfb63f>注册流水线与队列</p></div></div>", 1), p("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "jobs",
						onClick: n[8] ||= (e) => $("tasks")
					}, [...n[49] ||= [S("任务中心", -1), p("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
					p("div", bt, [
						p("section", xt, [n[54] ||= p("h4", null, "当前队列", -1), p("div", St, [
							p("div", null, [n[51] ||= p("span", null, "运行中", -1), p("strong", null, f(N(U.value.running)), 1)]),
							p("div", null, [n[52] ||= p("span", null, "待处理", -1), p("strong", null, f(N(U.value.pending)), 1)]),
							p("div", null, [n[53] ||= p("span", null, "停止中", -1), p("strong", null, f(N(U.value.stopping)), 1)])
						])]),
						p("section", Ct, [p("h4", null, [n[55] ||= S("今日结果 ", -1), p("small", null, f(H.value.today), 1)]), p("div", wt, [
							p("div", null, [n[56] ||= p("span", null, "成功", -1), p("strong", Tt, f(N(W.value.success)), 1)]),
							p("div", null, [n[57] ||= p("span", null, "部分成功", -1), p("strong", Et, f(N(W.value.partial_success)), 1)]),
							p("div", null, [n[58] ||= p("span", null, "失败", -1), p("strong", Dt, f(N(W.value.failed)), 1)])
						])]),
						p("section", Ot, [
							p("h4", null, [n[59] ||= S("累计结果 ", -1), p("small", null, f(N(H.value.total)) + " 个任务", 1)]),
							K.value.length ? (t(), x("div", kt, [(t(!0), x(l, null, i(K.value, (e) => (t(), x("i", {
								key: e.key,
								style: u({
									width: e.value / Math.max(1, H.value.total) * 100 + "%",
									background: e.color
								})
							}, null, 4))), 128))])) : (t(), x("div", At)),
							p("div", jt, [(t(!0), x(l, null, i(K.value, (e) => (t(), x("span", { key: e.key }, [p("i", { style: u({ background: e.color }) }, null, 4), S(f(e.label) + " " + f(N(e.value)), 1)]))), 128)), K.value.length ? s("", !0) : (t(), x("span", Mt, "暂无累计结果"))])
						])
					]),
					he.value ? (t(), x("p", Nt, "注册功能未启用，历史任务仍可查看。")) : s("", !0)
				])
			])) : s("", !0)
		], 2));
	}
}), [["__scopeId", "data-v-0fbfb63f"]]);
// src/api/dashboard.ts
async function X(e, t) {
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
function Z(e = (e, t) => C(e, t), t) {
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
			let i = await X(r, e);
			if (typeof i != "object" || !i || !("ok" in i) || i.ok !== !0) throw new w("能力检查返回无效数据", 200);
			return i;
		}
	};
}
// src/dashboard.ts
function Ft(e, t = {}) {
	let n = _(Pt, {
		api: t.api || Z(void 0, t.pendingCapabilities),
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
export { Ft as mountDashboard };
