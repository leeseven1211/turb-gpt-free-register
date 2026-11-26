import { C as e, F as t, H as n, K as r, L as i, M as a, S as o, _ as s, b as c, d as l, dt as u, et as d, ft as f, h as p, j as m, lt as h, m as g, n as _, o as v, st as y, t as b, v as x, x as S } from "./_plugin-vue_export-helper-BSZsFlS8.js";
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
	let r = d(null), i = d(null), o = d({}), s = d(null), c = d(!1), l = d(""), u = d(null), f = d(null), p = d(null), h = d(!1), _ = d(""), v = d(null), y = d(!!t.visible), b = d(!1), x, S, C, w, T, E = "", D = !1, O = 0, k = 0, A = {};
	function j(t, n) {
		if (D || !y.value || document.hidden || !e.registrationDaily) return Promise.resolve();
		let r = t !== void 0 || n !== void 0, i = r ? t || void 0 : A.from, a = r ? n || void 0 : A.to, o = JSON.stringify([i || "", a || ""]);
		if (T && E === o) return T;
		A = {
			from: i,
			to: a
		}, r && (f.value = {
			from: i,
			to: a
		});
		let d = ++k;
		C?.abort(), C = new AbortController(), c.value = !0, l.value = "";
		let m = C.signal, h = (async () => {
			try {
				let t = await e.registrationDaily?.(i, a, m);
				if (d !== k || !y.value || document.hidden) return;
				if (!t || t.ok === !1) throw Error(t?.message || "每日注册统计读取失败");
				s.value = t, p.value = {
					from: typeof t.date_from == "string" ? t.date_from : i,
					to: typeof t.date_to == "string" ? t.date_to : a
				}, u.value = typeof t.updated_at == "string" ? t.updated_at : (/* @__PURE__ */ new Date()).toISOString();
			} catch (e) {
				d === k && !String(e?.name || "").includes("Abort") && (l.value = e?.message || "每日注册统计读取失败");
			} finally {
				d === k && (c.value = !1, T = void 0);
			}
		})();
		return T = h, E = o, h;
	}
	function M(e) {
		D || y.value === !!e || (y.value = !!e, O++, k++, S?.abort(), C?.abort(), w = void 0, T = void 0, y.value ? (N(), P(!0)) : (x && window.clearInterval(x), x = void 0, h.value = !1, c.value = !1, E = ""));
	}
	function N() {
		x && window.clearInterval(x), x = window.setInterval(() => void P(!0), ee);
	}
	function P(n = !1) {
		if (D || !y.value || document.hidden) return Promise.resolve();
		let a = n && b.value;
		if (w) return a || (h.value = !0), w;
		j(A.from, A.to);
		let s = ++O;
		S?.abort(), S = new AbortController(), a || (h.value = !0), n || (_.value = "");
		let c = S.signal, l = (async () => {
			try {
				let [n, a, l] = await Promise.allSettled([
					e.dashboard(c),
					e.capabilities(c),
					e.extractSummary ? e.extractSummary(c) : Promise.resolve(null)
				]);
				if (s !== O || !y.value || document.hidden) return;
				if (n.status === "rejected") throw n.reason;
				r.value = n.value, i.value = l.status === "fulfilled" ? te(l.value) : null, a.status === "fulfilled" && a.value != null && (o.value = a.value || {}, t.onCapabilities?.(o.value)), b.value = !0, _.value = "", v.value = Date.now(), t.onReady?.();
			} catch (e) {
				s === O && !String(e?.name || "").includes("Abort") && (_.value = e?.message || "总览加载失败", t.notify?.(`总览加载失败：${_.value}`));
			} finally {
				s === O && (h.value = !1, w = void 0);
			}
		})();
		return w = l, l;
	}
	let F = () => {
		!document.hidden && y.value ? P(!0) : (O++, k++, S?.abort(), C?.abort(), w = void 0, T = void 0, E = "", h.value = !1, c.value = !1);
	};
	a(() => {
		document.addEventListener("visibilitychange", F), y.value && (N(), P());
	}), m(() => {
		D = !0, y.value = !1, O++, k++, w = void 0, T = void 0, E = "", h.value = !1, c.value = !1, document.removeEventListener("visibilitychange", F), S?.abort(), C?.abort(), x && window.clearInterval(x), x = void 0;
	}), n(() => t.visible, (e) => M(!!e));
	let I = g(() => !!r.value);
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
		hasData: I,
		load: P,
		loadDaily: j,
		setVisible: M
	};
}
// src/features/dashboard/DailyRegistrationStats.vue?vue&type=script&setup=true&lang.ts
var O = {
	class: "daily-stats",
	"aria-labelledby": "daily-registration-title"
}, k = { class: "daily-stats-head" }, A = { class: "daily-stats-meta" }, j = { "data-daily-range": "" }, M = {
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
}, I = {
	key: 2,
	class: "daily-stats-loading",
	"aria-live": "polite"
}, ne = {
	class: "daily-stats-chart",
	role: "img",
	"aria-label": "每日注册任务数柱状图"
}, L = ["title"], R = { class: "daily-bar-value" }, re = ["aria-label"], ie = {
	key: 0,
	class: "daily-stats-rows"
}, ae = ["data-daily-row"], oe = { class: "daily-row-heading" }, se = ["disabled", "onClick"], z = { class: "daily-row-metrics" }, ce = { class: "daily-row-plans" }, le = ["title"], B = { key: 0 }, ue = { key: 1 }, V = {
	key: 1,
	class: "daily-stats-empty"
}, de = {
	key: 2,
	class: "daily-stats-summary"
}, H = ["disabled"], U = /*#__PURE__*/ b(/* @__PURE__ */ e({
	__name: "DailyRegistrationStats",
	props: {
		state: {},
		onBulkPlanCreate: { type: Function }
	},
	setup(e) {
		let a = e, o = d("7"), c = d(""), m = d(""), _ = d(!1), y = g(() => Array.isArray(a.state.data?.rows) ? a.state.data.rows : []), b = g(() => ({
			from: a.state.data?.date_from || y.value[0]?.date || "",
			to: a.state.data?.date_to || y.value[y.value.length - 1]?.date || ""
		})), C = g(() => b.value.from && b.value.to ? `${b.value.from} 至 ${b.value.to}` : "日期范围待返回"), w = g(() => a.state.updatedAt ? `更新于 ${new Date(a.state.updatedAt).toLocaleString("zh-CN", {
			hour12: !1,
			timeZone: "Asia/Shanghai"
		})}` : a.state.loading ? "正在读取…" : "尚未读取"), ee = g(() => a.state.error && a.state.data && a.state.scopeCurrent ? `${a.state.error}，当前成功范围仍可使用。` : a.state.error), T = g(() => Math.max(1, ...y.value.map((e) => U(e.total)))), te = {
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
		}, E = {
			success: "成功",
			partial_success: "部分成功",
			failed: "失败",
			active: "进行中",
			cancelled: "取消"
		}, D = {
			interrupted: "执行中断",
			unsupported: "不支持",
			deactivated: "已停用"
		};
		function U(e) {
			let t = Number(e);
			return Number.isFinite(t) ? t : 0;
		}
		function W(e) {
			if (e == null) return null;
			let t = Number(e);
			return Number.isFinite(t) ? t : null;
		}
		function fe(e, t) {
			return e.counts === null || e.counts === void 0 ? null : W(e.counts[t]) ?? 0;
		}
		function pe(e, t) {
			let n = fe(e, t);
			return `${E[t] || t} ${n === null ? "—" : U(n)}`;
		}
		function me(e, t) {
			return e.counts === null || e.counts === void 0 ? null : t.reduce((t, n) => t + (W(e.counts[n]) ?? 0), 0);
		}
		function he(e, t, n) {
			let r = me(e, n);
			return `${t} ${r === null ? "—" : U(r)}`;
		}
		function ge(e) {
			return e.counts === null || e.counts === void 0 ? [] : Object.entries(D).map(([t, n]) => ({
				key: t,
				label: n,
				value: W(e.counts[t]) ?? 0
			})).filter((e) => e.value > 0);
		}
		function G(e) {
			return e.plans === null || e.plans === void 0 ? null : Object.entries(e.plans).map(([e, t]) => ({
				key: e,
				label: te[e] || e,
				count: U(t)
			})).sort((e, t) => t.count - e.count);
		}
		function _e(e) {
			return G(e)?.reduce((e, t) => e + t.count, 0) ?? null;
		}
		function ve(e, t) {
			let n = _e(e);
			return n && t >= 0 ? `${Math.round(t / n * 100)}%` : "—";
		}
		function K(e) {
			let t = W(e);
			return t === null ? "—" : new Intl.NumberFormat("zh-CN").format(t);
		}
		function q(e) {
			let t = W(e);
			return t === null ? "待查" : new Intl.NumberFormat("zh-CN").format(t);
		}
		function ye(e) {
			return W(e.unpromoted_count);
		}
		function be(e) {
			return a.state.scopeCurrent && ye(e) !== null && ye(e) > 0 && !!e.query;
		}
		function xe(e, t) {
			be(e) && e.query && a.onBulkPlanCreate?.({
				name: t,
				query: e.query
			});
		}
		function Se(e, t) {
			let n = /* @__PURE__ */ new Date(`${e}T00:00:00Z`);
			return n.setUTCDate(n.getUTCDate() + t), n.toISOString().slice(0, 10);
		}
		function Ce() {
			let e = new Intl.DateTimeFormat("en-US", {
				timeZone: "Asia/Shanghai",
				year: "numeric",
				month: "2-digit",
				day: "2-digit"
			}).formatToParts(/* @__PURE__ */ new Date()), t = Object.fromEntries(e.filter((e) => e.type !== "literal").map((e) => [e.type, e.value]));
			return `${t.year}-${t.month}-${t.day}`;
		}
		function we(e) {
			let t = Ce();
			return [Se(t, -(e - 1)), t];
		}
		function Te(e) {
			o.value = e;
			let [t, n] = we(Number(e));
			a.state.load(t, n);
		}
		function Ee() {
			o.value = "custom", c.value = a.state.displayedRange?.from || b.value.from, m.value = a.state.displayedRange?.to || b.value.to;
		}
		function De() {
			o.value !== "custom" || !c.value || !m.value || c.value > m.value || a.state.load(c.value, m.value);
		}
		return n(() => [a.state.data?.date_from, a.state.data?.date_to], ([e, t]) => {
			!_.value && (e || t) && (c.value = e || "", m.value = t || "", _.value = !0);
		}, { immediate: !0 }), (n, a) => (t(), x("section", O, [
			p("header", k, [a[6] ||= p("div", null, [p("h2", { id: "daily-registration-title" }, "每日注册统计"), p("p", null, "北京时间 · 按注册任务创建日期统计 · 套餐以最近成功查询为准 · 账号总数含归档账号")], -1), p("div", A, [p("span", j, f(C.value), 1), p("span", null, f(w.value), 1)])]),
			p("div", M, [
				p("button", {
					type: "button",
					"data-daily-range-7": "",
					class: h({ active: o.value === "7" }),
					onClick: a[0] ||= (e) => Te("7")
				}, "近 7 天", 2),
				p("button", {
					type: "button",
					"data-daily-range-30": "",
					class: h({ active: o.value === "30" }),
					onClick: a[1] ||= (e) => Te("30")
				}, "近 30 天", 2),
				p("button", {
					type: "button",
					class: h({ active: o.value === "custom" }),
					onClick: Ee
				}, "自定义", 2),
				o.value === "custom" ? (t(), x(l, { key: 0 }, [p("label", null, [a[7] ||= S("开始日期", -1), r(p("input", {
					"onUpdate:modelValue": a[2] ||= (e) => c.value = e,
					type: "date",
					onChange: De
				}, null, 544), [[v, c.value]])]), p("label", null, [a[8] ||= S("结束日期", -1), r(p("input", {
					"onUpdate:modelValue": a[3] ||= (e) => m.value = e,
					type: "date",
					onChange: De
				}, null, 544), [[v, m.value]])])], 64)) : s("", !0)
			]),
			e.state.error ? (t(), x("div", N, [p("span", null, f(ee.value), 1), p("button", {
				type: "button",
				"data-daily-retry": "",
				disabled: e.state.loading,
				onClick: a[4] ||= (t) => e.state.load()
			}, "重试", 8, P)])) : s("", !0),
			e.state.data && !e.state.scopeCurrent ? (t(), x("div", F, f(e.state.loading ? "正在读取新日期范围，当前仍显示上一成功范围；完成前不能新建查套餐批量。" : "新日期范围读取失败，当前仍显示上一成功范围；请重试后再新建查套餐批量。"), 1)) : s("", !0),
			e.state.loading && !e.state.data ? (t(), x("div", I, "正在读取每日注册统计…")) : e.state.data ? (t(), x(l, { key: 3 }, [
				p("div", ne, [(t(!0), x(l, null, i(y.value, (e) => (t(), x("div", {
					key: e.date,
					class: "daily-bar-column",
					title: `${e.date} · 总数 ${K(e.total)}`
				}, [
					p("span", R, f(K(e.total)), 1),
					p("i", {
						"data-daily-bar": "",
						style: u({ height: `${Math.max(3, U(e.total) / T.value * 100)}%` }),
						"aria-label": `${e.date} 总数 ${K(e.total)}`
					}, null, 12, re),
					p("small", null, f(e.date.slice(5)), 1)
				], 8, L))), 128))]),
				y.value.length ? (t(), x("div", ie, [(t(!0), x(l, null, i(y.value, (e) => (t(), x("article", {
					key: e.date,
					class: "daily-stats-row",
					"data-daily-row": e.date
				}, [
					p("div", oe, [p("div", null, [p("strong", null, f(e.date), 1), p("span", null, "总数 " + f(K(e.total)), 1)]), p("button", {
						type: "button",
						"data-daily-bulk": "",
						disabled: !be(e),
						onClick: (t) => xe(e, `${e.date} 无优惠账号查套餐`)
					}, " 新建查套餐批量（" + f(q(e.unpromoted_count)) + "） ", 9, se)]),
					p("div", z, [
						p("span", null, f(pe(e, "success")), 1),
						p("span", null, f(pe(e, "partial_success")), 1),
						p("span", null, f(pe(e, "failed")), 1),
						p("span", null, f(he(e, "进行中", [
							"pending",
							"queued",
							"running",
							"waiting",
							"settling",
							"stopping",
							"cancelling"
						])), 1),
						p("span", null, f(he(e, "取消", ["cancelled", "stopped"])), 1),
						(t(!0), x(l, null, i(ge(e), (e) => (t(), x("span", { key: e.key }, f(e.label) + " " + f(e.value), 1))), 128)),
						p("span", null, "账号总数（含归档） " + f(K(e.accounts_total)), 1),
						p("span", null, "未归档无优惠 " + f(q(e.unpromoted_count)), 1)
					]),
					p("div", ce, [a[9] ||= p("span", { class: "daily-row-label" }, "套餐分布", -1), G(e) ? (t(), x(l, { key: 0 }, [(t(!0), x(l, null, i(G(e), (n) => (t(), x("span", {
						key: n.key,
						title: `${n.label} ${K(n.count)}，占套餐账号 ${ve(e, n.count)}`
					}, f(n.label) + " " + f(K(n.count)) + " · " + f(ve(e, n.count)), 9, le))), 128)), G(e).length ? s("", !0) : (t(), x("span", B, "暂无账号"))], 64)) : (t(), x("span", ue, "套餐待查"))])
				], 8, ae))), 128))])) : (t(), x("p", V, "所选日期暂无任务。")),
				e.state.data.summary ? (t(), x("div", de, [p("div", null, [a[10] ||= p("strong", null, "区间汇总", -1), p("span", null, "总数 " + f(K(e.state.data.summary.total)) + " · 账号总数（含归档） " + f(K(e.state.data.summary.accounts_total)) + " · 未归档无优惠 " + f(q(e.state.data.summary.unpromoted_count)), 1)]), p("button", {
					type: "button",
					"data-daily-summary-bulk": "",
					disabled: !be(e.state.data.summary),
					onClick: a[5] ||= (t) => xe(e.state.data.summary, `${b.value.from}..${b.value.to} 无优惠账号查套餐`)
				}, " 新建区间查套餐批量（" + f(q(e.state.data.summary.unpromoted_count)) + "） ", 9, H)])) : s("", !0)
			], 64)) : s("", !0)
		]));
	}
}), [["__scopeId", "data-v-949b22a1"]]), W = { class: "ov-section-head" }, fe = { class: "ov-section-actions" }, pe = { class: "ov-updated" }, me = ["disabled"], he = {
	key: 0,
	class: "ov-error",
	role: "alert"
}, ge = {
	key: 1,
	class: "ov-alerts",
	"aria-label": "需要关注"
}, G = ["onClick"], _e = {
	key: 2,
	class: "ov-skeleton",
	"aria-label": "正在读取总览"
}, ve = {
	class: "ov-pulse",
	"aria-label": "服务脉搏"
}, K = ["title", "onClick"], q = { class: "ov-pulse-top" }, ye = { class: "ov-pulse-badge" }, be = { class: "ov-grid" }, xe = {
	class: "ov-card ov-card--email",
	"data-overview-card": "email",
	style: {
		"--accent": "#1f9d75",
		"--accent-soft": "#e7f6f0"
	}
}, Se = { class: "ov-card-head" }, Ce = { class: "ov-figure" }, we = { class: "ov-mini-grid ov-mini-grid--3" }, Te = {
	key: 0,
	class: "ov-bars"
}, Ee = { class: "ov-bar-label" }, De = {
	key: 1,
	class: "ov-empty"
}, Oe = {
	key: 2,
	class: "ov-foot"
}, ke = {
	key: 3,
	class: "ov-foot"
}, Ae = {
	class: "ov-card ov-card--accounts",
	"data-overview-card": "accounts",
	style: {
		"--accent": "#5b5ce2",
		"--accent-soft": "#eeeefe"
	}
}, je = { class: "ov-card-head" }, Me = { class: "ov-figure" }, Ne = {
	class: "ov-split",
	"aria-hidden": "true"
}, Pe = { class: "ov-legend" }, Fe = { class: "ov-mini-grid ov-mini-grid--2" }, Ie = { class: "ov-meter" }, Le = { class: "ov-bar" }, Re = {
	class: "ov-card ov-card--codex",
	"data-overview-card": "codex",
	style: {
		"--accent": "#377dff",
		"--accent-soft": "#e9f1ff"
	}
}, ze = { class: "ov-card-head" }, Be = { class: "ov-figure" }, Ve = {
	key: 0,
	class: "ov-chip is-warn"
}, He = { class: "ov-bar-label" }, Ue = { class: "ov-bar ov-bar--thick" }, We = { class: "ov-mini-grid ov-mini-grid--3" }, Ge = { class: "ov-foot" }, Ke = {
	class: "ov-card ov-card--extract",
	"data-overview-card": "extract",
	style: {
		"--accent": "#d97706",
		"--accent-soft": "#fdf3e3"
	}
}, qe = { class: "ov-card-head" }, Je = { class: "ov-figure" }, Ye = {
	key: 0,
	class: "ov-mini-grid ov-mini-grid--3"
}, Xe = {
	key: 1,
	class: "ov-empty"
}, Ze = { class: "ov-foot" }, Qe = {
	class: "ov-card ov-card--plans",
	"data-overview-card": "plans",
	style: {
		"--accent": "#8b5cf6",
		"--accent-soft": "#f3edff"
	}
}, $e = { class: "ov-card-head" }, et = { class: "ov-figure ov-figure--small" }, tt = { class: "ov-bars" }, nt = { class: "ov-bar-label" }, rt = { class: "ov-bar" }, it = {
	key: 1,
	class: "ov-empty"
}, at = {
	class: "ov-card ov-card--proxy",
	"data-overview-card": "proxy",
	style: {
		"--accent": "#0e9aa7",
		"--accent-soft": "#e6f6f7"
	}
}, ot = { class: "ov-card-head" }, st = { class: "ov-figure" }, ct = { class: "ov-chip" }, lt = {
	key: 0,
	class: "ov-lease-list"
}, ut = {
	key: 1,
	class: "ov-empty"
}, dt = {
	key: 2,
	class: "ov-foot"
}, ft = {
	class: "ov-card ov-card--jobs",
	"data-overview-card": "jobs",
	style: {
		"--accent": "#475569",
		"--accent-soft": "#eef1f5"
	}
}, pt = { class: "ov-card-head" }, mt = { class: "ov-task-columns" }, ht = { class: "ov-task-block" }, gt = { class: "ov-mini-grid ov-mini-grid--3" }, _t = { class: "ov-task-block" }, vt = { class: "ov-mini-grid ov-mini-grid--3" }, yt = { class: "is-ok" }, bt = { class: "is-warn" }, xt = { class: "is-danger" }, St = { class: "ov-task-block ov-task-block--wide" }, Ct = {
	key: 0,
	class: "ov-stack",
	"aria-hidden": "true"
}, wt = {
	key: 1,
	class: "ov-stack ov-stack--empty",
	"aria-hidden": "true"
}, Tt = { class: "ov-stack-legend" }, Et = {
	key: 0,
	class: "ov-stack-empty-text"
}, Dt = {
	key: 0,
	class: "ov-foot"
}, Ot = /*#__PURE__*/ b(/* @__PURE__ */ e({
	__name: "DashboardPage",
	props: {
		api: {},
		deps: {}
	},
	setup(e, { expose: n }) {
		let r = e, m = D(r.api, r.deps), { data: _, extract: v, caps: b, daily: C, dailyLoading: w, dailyError: ee, dailyUpdatedAt: T, dailyRequestedRange: te, dailyDisplayedRange: O, dailyScopeCurrent: k, loading: A, error: j, updatedAt: M } = m, N = d(!1);
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
		})[e] || e, L = g(() => _.value?.accounts || {}), R = g(() => _.value?.email?.supply || {}), re = g(() => (Array.isArray(R.value?.sources) ? R.value.sources : Array.isArray(_.value?.email?.sources) ? _.value.email.sources : []).filter((e) => e?.kind === "local_pool")), ie = g(() => re.value.filter((e) => F(e.total) > 0 || F(e.available) > 0)), ae = g(() => Math.max(0, re.value.length - ie.value.length)), oe = g(() => R.value?.status === "error" ? "读取失败" : F(R.value?.available)), se = g(() => R.value?.status === "error" ? "—" : P(oe.value)), z = g(() => F(R.value?.total)), ce = g(() => F(R.value?.used)), le = g(() => F(R.value?.failed) + F(R.value?.disabled)), B = g(() => R.value?.status === "error" ? "danger" : z.value > 0 && F(R.value?.available) === 0 ? "warn" : F(R.value?.available) > 0 ? "ok" : "idle"), ue = g(() => R.value?.status === "error" ? "读取失败" : z.value === 0 ? "未配置" : F(R.value?.available) === 0 ? "库存耗尽" : "库存正常"), V = g(() => _.value?.codex || {}), de = g(() => F(V.value.pending) > 0 ? "warn" : F(V.value.total) > 0 ? "ok" : "idle"), H = g(() => Object.entries(L.value?.plans || {}).map(([e, t]) => ({
			key: e,
			label: ne(e),
			count: F(t)
		})).sort((e, t) => t.count - e.count)), Ot = g(() => Math.max(1, ...H.value.map((e) => e.count))), kt = g(() => H.value.reduce((e, t) => e + t.count, 0)), J = g(() => _.value?.jobs || {}), At = g(() => b.value?.features?.register?.enabled === !1), Y = g(() => ({ ...J.value?.counts || {} })), X = g(() => ({ ...J.value?.today_counts || {} })), jt = g(() => F(Y.value.pending) + F(Y.value.running) + F(Y.value.stopping));
		g(() => F(X.value.success) + F(X.value.partial_success) + F(X.value.failed));
		let Mt = g(() => [
			{
				key: "success",
				label: "成功",
				value: F(Y.value.success),
				color: "#1f9d75"
			},
			{
				key: "partial_success",
				label: "部分成功",
				value: F(Y.value.partial_success),
				color: "#d99a2b"
			},
			{
				key: "failed",
				label: "失败",
				value: F(Y.value.failed),
				color: "#d9534f"
			},
			{
				key: "cancelled",
				label: "停止/取消",
				value: F(Y.value.stopped) + F(Y.value.cancelled),
				color: "#98a2b3"
			}
		].filter((e) => e.value > 0)), Nt = g(() => jt.value > 0 ? "active" : F(X.value.failed) > 0 ? "warn" : "idle"), Z = g(() => _.value?.proxy || {}), Pt = g(() => Array.isArray(Z.value.leases) ? Z.value.leases.slice(0, 3) : []), Ft = g(() => Math.max(0, F(Z.value.active_leases) - Pt.value.length)), It = g(() => b.value?.proxy?.registration?.enabled === !1), Lt = g(() => F(Z.value.active_leases) > 0 ? "ok" : "idle"), Q = g(() => v.value || {}), Rt = g(() => F(Q.value.processing) > 0 ? "active" : "idle"), zt = g(() => F(Q.value.all) === 0 && F(Q.value.today_extracted) === 0 && F(Q.value.processing) === 0 && F(Q.value.awaiting_payment) === 0), Bt = g(() => [
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
				hint: `${P(kt.value)} 个已归类`,
				tone: "ok",
				tab: "accounts"
			},
			{
				id: "extract",
				label: "提炼",
				value: P(Q.value.today_extracted),
				badge: F(Q.value.processing) > 0 ? `进行 ${P(Q.value.processing)}` : `今日 ${P(Q.value.today_extracted)}`,
				hint: "今日已提炼",
				tone: Rt.value,
				tab: "extract-workbench"
			},
			{
				id: "proxy",
				label: "代理",
				value: P(Z.value.active_leases),
				badge: F(Z.value.active_leases) > 0 ? `${P(Z.value.active_leases)} 出口` : E(Z.value.platform),
				hint: E(Z.value.platform),
				tone: Lt.value,
				tab: "proxy-traffic"
			},
			{
				id: "jobs",
				label: "任务",
				value: P(jt.value),
				badge: jt.value > 0 ? `运行 ${P(jt.value)}` : F(X.value.failed) > 0 ? `异常 ${P(X.value.failed)}` : "空闲",
				hint: `累计 ${P(J.value.total)}`,
				tone: Nt.value,
				tab: "tasks"
			}
		]), Vt = g(() => {
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
		}), Ht = g(() => M.value ? `数据更新 ${new Date(M.value).toLocaleTimeString("zh-CN", { hour12: !1 })}` : A.value ? "正在读取…" : "尚未读取"), $ = (e) => r.deps.onNavigate?.(e), Ut = g(() => ({
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
		}), (e, n) => (t(), x("div", { class: h(["ov-page", { "is-mounted": N.value }]) }, [
			p("div", W, [n[11] ||= p("div", { class: "ov-section-title" }, [p("h2", null, "服务脉搏"), p("p", null, "邮箱 · 账号 · Codex · 套餐 · 提炼 · 代理 · 任务")], -1), p("div", fe, [p("span", pe, [n[9] ||= p("i", { "aria-hidden": "true" }, null, -1), S(f(Ht.value), 1)]), p("button", {
				type: "button",
				class: "ov-refresh ui-refresh-button",
				disabled: y(A),
				onClick: n[0] ||= (e) => y(m).load()
			}, [n[10] ||= p("svg", {
				viewBox: "0 0 24 24",
				"aria-hidden": "true"
			}, [p("path", { d: "M20 11a8 8 0 1 0-2.3 6.7" }), p("path", { d: "M20 4v7h-7" })], -1), S(" " + f(y(A) ? "刷新中" : "刷新"), 1)], 8, me)])]),
			y(j) ? (t(), x("div", he, [p("div", null, [n[12] ||= p("strong", null, "总览加载失败", -1), p("span", null, f(y(j)), 1)]), p("button", {
				type: "button",
				onClick: n[1] ||= (e) => y(m).load()
			}, "重试")])) : s("", !0),
			Vt.value.length ? (t(), x("section", ge, [(t(!0), x(l, null, i(Vt.value, (e) => (t(), x("article", {
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
				}, f(e.label), 9, G)
			], 2))), 128))])) : s("", !0),
			!y(_) && y(A) ? (t(), x("section", _e, [...n[14] ||= [p("div", { class: "ov-skeleton-pulse" }, null, -1), p("div", { class: "ov-skeleton-grid" }, [
				p("i"),
				p("i"),
				p("i"),
				p("i")
			], -1)]])) : s("", !0),
			y(_) ? (t(), x(l, { key: 3 }, [
				p("nav", ve, [(t(!0), x(l, null, i(Bt.value, (e) => (t(), x("button", {
					key: e.id,
					type: "button",
					class: h(["ov-pulse-item", [`is-${e.tone}`, { "is-zero": e.value === "0" }]]),
					title: `${e.label} · ${e.hint}`,
					onClick: (t) => $(e.tab)
				}, [p("span", q, [n[15] ||= p("i", { "aria-hidden": "true" }, null, -1), S(f(e.label), 1)]), p("span", ye, [p("strong", null, f(e.badge), 1)])], 10, K))), 128))]),
				o(U, {
					state: Ut.value,
					"on-bulk-plan-create": r.deps.onBulkPlanCreate
				}, null, 8, ["state", "on-bulk-plan-create"]),
				p("div", be, [
					p("article", xe, [
						p("header", Se, [n[17] ||= c("<div class=\"ov-card-title\" data-v-b190bba0><span class=\"ov-icon\" data-v-b190bba0><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-b190bba0><rect x=\"3\" y=\"5\" width=\"18\" height=\"14\" rx=\"2\" data-v-b190bba0></rect><path d=\"m3 7 9 6 9-6\" data-v-b190bba0></path></svg></span><div data-v-b190bba0><h3 data-v-b190bba0>邮箱池</h3><p data-v-b190bba0>本地库存与来源</p></div></div>", 1), p("button", {
							type: "button",
							class: "ov-link",
							"data-overview-action": "email",
							onClick: n[2] ||= (e) => $("outlook")
						}, [...n[16] ||= [S("管理", -1), p("svg", {
							viewBox: "0 0 24 24",
							"aria-hidden": "true"
						}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
						p("div", Ce, [
							p("strong", { class: h({ "is-danger": B.value === "warn" }) }, f(se.value), 3),
							n[18] ||= p("span", null, "可用", -1),
							B.value === "ok" ? s("", !0) : (t(), x("em", {
								key: 0,
								class: h(["ov-chip", `is-${B.value}`])
							}, f(ue.value), 3))
						]),
						p("div", we, [
							p("div", null, [n[19] ||= p("span", null, "邮箱总量", -1), p("strong", null, f(P(z.value)), 1)]),
							p("div", null, [n[20] ||= p("span", null, "已使用", -1), p("strong", null, f(P(ce.value)), 1)]),
							p("div", null, [n[21] ||= p("span", null, "停用 / 失败", -1), p("strong", null, f(P(le.value)), 1)])
						]),
						ie.value.length ? (t(), x("ul", Te, [(t(!0), x(l, null, i(ie.value, (e) => (t(), x("li", { key: e.source }, [p("div", Ee, [p("span", null, f(e.label), 1), p("small", null, f(F(e.available) === 0 ? "已用尽" : `可用 ${P(e.available)}`) + " / " + f(P(e.total)), 1)]), p("div", { class: h(["ov-bar", { "is-spent": F(e.available) === 0 && F(e.total) > 0 }]) }, [p("i", { style: u({ width: I(e.available, e.total) + "%" }) }, null, 4)], 2)]))), 128))])) : (t(), x("p", De, "还没有可统计的邮箱库存。")),
						ae.value ? (t(), x("p", Oe, "另有 " + f(ae.value) + " 个来源暂无库存 · 仅统计本地库存", 1)) : (t(), x("p", ke, "仅统计本地库存，用完后需手动导入"))
					]),
					p("article", Ae, [
						p("header", je, [n[23] ||= c("<div class=\"ov-card-title\" data-v-b190bba0><span class=\"ov-icon\" data-v-b190bba0><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-b190bba0><path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\" data-v-b190bba0></path><circle cx=\"9\" cy=\"7\" r=\"4\" data-v-b190bba0></circle><path d=\"M22 21v-2a4 4 0 0 0-3-3.9\" data-v-b190bba0></path></svg></span><div data-v-b190bba0><h3 data-v-b190bba0>账号</h3><p data-v-b190bba0>账号资产</p></div></div>", 1), p("button", {
							type: "button",
							class: "ov-link",
							"data-overview-action": "accounts",
							onClick: n[3] ||= (e) => $("accounts")
						}, [...n[22] ||= [S("管理", -1), p("svg", {
							viewBox: "0 0 24 24",
							"aria-hidden": "true"
						}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
						p("div", Me, [p("strong", null, f(P(L.value.active)), 1), n[24] ||= p("span", null, "活跃账号", -1)]),
						p("div", Ne, [p("i", {
							class: "is-active",
							style: u({ width: I(L.value.active, L.value.total) + "%" })
						}, null, 4), p("i", {
							class: "is-idle",
							style: u({ width: I(L.value.archived, L.value.total) + "%" })
						}, null, 4)]),
						p("div", Pe, [p("span", null, [n[25] ||= p("i", { style: { background: "#5b5ce2" } }, null, -1), S("活跃 " + f(P(L.value.active)), 1)]), p("span", null, [n[26] ||= p("i", { style: { background: "#d7dbe5" } }, null, -1), S("归档 " + f(P(L.value.archived)), 1)])]),
						p("div", Fe, [p("div", null, [n[27] ||= p("span", null, "账号总数", -1), p("strong", null, f(P(L.value.total)), 1)]), p("div", null, [n[28] ||= p("span", null, "Codex 就绪", -1), p("strong", null, f(P(L.value.codex_ready)), 1)])]),
						p("div", Ie, [
							n[29] ||= p("span", null, "Codex 就绪率", -1),
							p("div", Le, [p("i", { style: u({ width: I(L.value.codex_ready, L.value.active) + "%" }) }, null, 4)]),
							p("strong", null, f(I(L.value.codex_ready, L.value.active)) + "%", 1)
						])
					]),
					p("article", Re, [
						p("header", ze, [n[31] ||= c("<div class=\"ov-card-title\" data-v-b190bba0><span class=\"ov-icon\" data-v-b190bba0><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-b190bba0><rect x=\"3\" y=\"11\" width=\"18\" height=\"10\" rx=\"2\" data-v-b190bba0></rect><path d=\"M7 11V7a5 5 0 0 1 10 0v4\" data-v-b190bba0></path></svg></span><div data-v-b190bba0><h3 data-v-b190bba0>Codex</h3><p data-v-b190bba0>授权凭证</p></div></div>", 1), p("button", {
							type: "button",
							class: "ov-link",
							"data-overview-action": "codex",
							onClick: n[4] ||= (e) => $("codex")
						}, [...n[30] ||= [S("查看", -1), p("svg", {
							viewBox: "0 0 24 24",
							"aria-hidden": "true"
						}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
						p("div", Be, [
							p("strong", null, f(P(V.value.total)), 1),
							n[32] ||= p("span", null, "已导出凭证", -1),
							de.value === "warn" ? (t(), x("em", Ve, "待导出")) : s("", !0)
						]),
						p("div", He, [n[33] ||= p("span", null, "导出进度", -1), p("small", null, f(P(V.value.exported)) + " / " + f(P(V.value.total)), 1)]),
						p("div", Ue, [p("i", { style: u({ width: I(V.value.exported, V.value.total) + "%" }) }, null, 4)]),
						p("div", We, [
							p("div", null, [n[34] ||= p("span", null, "已导出", -1), p("strong", null, f(P(V.value.exported)), 1)]),
							p("div", null, [n[35] ||= p("span", null, "待导出", -1), p("strong", null, f(P(V.value.pending)), 1)]),
							p("div", null, [n[36] ||= p("span", null, "账号就绪", -1), p("strong", null, f(P(L.value.codex_ready)), 1)])
						]),
						p("p", Ge, "账号 Codex 就绪 " + f(P(L.value.codex_ready)) + " · 覆盖 " + f(I(L.value.codex_ready, L.value.active)) + "% 活跃账号", 1)
					]),
					p("article", Ke, [
						p("header", qe, [n[38] ||= c("<div class=\"ov-card-title\" data-v-b190bba0><span class=\"ov-icon\" data-v-b190bba0><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-b190bba0><path d=\"m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z\" data-v-b190bba0></path><path d=\"M19 15.5 20 18l2.5 1-2.5 1L19 22l-1-2-2.5-1 2.5-1 1-2.5Z\" data-v-b190bba0></path></svg></span><div data-v-b190bba0><h3 data-v-b190bba0>提炼</h3><p data-v-b190bba0>提链工作台</p></div></div>", 1), p("button", {
							type: "button",
							class: "ov-link",
							"data-overview-action": "extract",
							onClick: n[5] ||= (e) => $("extract-workbench")
						}, [...n[37] ||= [S("工作台", -1), p("svg", {
							viewBox: "0 0 24 24",
							"aria-hidden": "true"
						}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
						p("div", Je, [
							p("strong", null, f(P(Q.value.today_extracted)), 1),
							n[39] ||= p("span", null, "今日已提炼", -1),
							p("em", { class: h(["ov-chip", `is-${Rt.value}`]) }, f(Rt.value === "idle" ? "空闲" : "处理中"), 3)
						]),
						zt.value ? s("", !0) : (t(), x("div", Ye, [
							p("div", null, [n[40] ||= p("span", null, "Plus 已确认", -1), p("strong", null, f(P(Q.value.today_plus_confirmed)), 1)]),
							p("div", null, [n[41] ||= p("span", null, "处理中", -1), p("strong", null, f(P(Q.value.processing)), 1)]),
							p("div", null, [n[42] ||= p("span", null, "待支付", -1), p("strong", null, f(P(Q.value.awaiting_payment)), 1)])
						])),
						zt.value ? (t(), x("p", Xe, "今日还没有提炼任务，进入工作台即可发起。")) : s("", !0),
						p("p", Ze, f(zt.value ? "提链工作台空闲" : `累计 ${P(Q.value.all)} 个提炼任务`), 1)
					]),
					p("article", Qe, [p("header", $e, [n[44] ||= c("<div class=\"ov-card-title\" data-v-b190bba0><span class=\"ov-icon\" data-v-b190bba0><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-b190bba0><path d=\"M12 2 2 7l10 5 10-5-10-5Z\" data-v-b190bba0></path><path d=\"m2 12 10 5 10-5\" data-v-b190bba0></path><path d=\"m2 17 10 5 10-5\" data-v-b190bba0></path></svg></span><div data-v-b190bba0><h3 data-v-b190bba0>套餐</h3><p data-v-b190bba0>账号套餐分布</p></div></div>", 1), p("button", {
						type: "button",
						class: "ov-link",
						"data-overview-action": "plans",
						onClick: n[6] ||= (e) => $("accounts")
					}, [...n[43] ||= [S("账号", -1), p("svg", {
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]), H.value.length ? (t(), x(l, { key: 0 }, [p("div", et, [p("strong", null, f(P(H.value.length)), 1), p("span", null, "种套餐 · " + f(P(kt.value)) + " 个账号", 1)]), p("ul", tt, [(t(!0), x(l, null, i(H.value, (e) => (t(), x("li", { key: e.key }, [p("div", nt, [p("span", null, f(e.label), 1), p("small", null, f(P(e.count)) + " · " + f(I(e.count, kt.value)) + "%", 1)]), p("div", rt, [p("i", { style: u({ width: Math.max(4, Math.round(e.count / Ot.value * 100)) + "%" }) }, null, 4)])]))), 128))])], 64)) : (t(), x("p", it, "还没有可用的套餐数据。"))]),
					p("article", at, [
						p("header", ot, [n[46] ||= c("<div class=\"ov-card-title\" data-v-b190bba0><span class=\"ov-icon\" data-v-b190bba0><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-b190bba0><circle cx=\"12\" cy=\"12\" r=\"9\" data-v-b190bba0></circle><path d=\"M3 12h18\" data-v-b190bba0></path><path d=\"M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3Z\" data-v-b190bba0></path></svg></span><div data-v-b190bba0><h3 data-v-b190bba0>代理</h3><p data-v-b190bba0>网络出口</p></div></div>", 1), p("button", {
							type: "button",
							class: "ov-link",
							"data-overview-action": "proxy",
							onClick: n[7] ||= (e) => $("proxy-traffic")
						}, [...n[45] ||= [S("查看", -1), p("svg", {
							viewBox: "0 0 24 24",
							"aria-hidden": "true"
						}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
						p("div", st, [
							p("strong", null, f(P(Z.value.active_leases)), 1),
							n[47] ||= p("span", null, "活跃出口", -1),
							p("em", ct, f(y(E)(Z.value.platform)), 1)
						]),
						Pt.value.length ? (t(), x("ul", lt, [(t(!0), x(l, null, i(Pt.value, (e, r) => (t(), x("li", { key: r }, [
							n[48] ||= p("i", { "aria-hidden": "true" }, null, -1),
							p("span", null, f(e.endpoint || e.exit_ip || "活跃出口"), 1),
							p("small", null, f(e.region || e.provider || ""), 1)
						]))), 128))])) : (t(), x("p", ut, f(It.value ? "注册代理未启用，当前没有活跃租约。" : `当前没有活跃的代理租约，新任务会走 ${y(E)(Z.value.platform)}。`), 1)),
						Pt.value.length ? (t(), x("p", dt, [S(f(It.value ? "注册代理未启用，已有租约仍保留" : `代理平台 ${y(E)(Z.value.platform)}`), 1), Ft.value ? (t(), x(l, { key: 0 }, [S(" · 另有 " + f(Ft.value) + " 个活跃出口", 1)], 64)) : s("", !0)])) : s("", !0)
					]),
					p("article", ft, [
						p("header", pt, [n[50] ||= c("<div class=\"ov-card-title\" data-v-b190bba0><span class=\"ov-icon\" data-v-b190bba0><svg viewBox=\"0 0 24 24\" aria-hidden=\"true\" data-v-b190bba0><path d=\"M9 5h11\" data-v-b190bba0></path><path d=\"M9 12h11\" data-v-b190bba0></path><path d=\"M9 19h11\" data-v-b190bba0></path><circle cx=\"4\" cy=\"5\" r=\"1\" data-v-b190bba0></circle><circle cx=\"4\" cy=\"12\" r=\"1\" data-v-b190bba0></circle><circle cx=\"4\" cy=\"19\" r=\"1\" data-v-b190bba0></circle></svg></span><div data-v-b190bba0><h3 data-v-b190bba0>任务</h3><p data-v-b190bba0>注册流水线与队列</p></div></div>", 1), p("button", {
							type: "button",
							class: "ov-link",
							"data-overview-action": "jobs",
							onClick: n[8] ||= (e) => $("tasks")
						}, [...n[49] ||= [S("任务中心", -1), p("svg", {
							viewBox: "0 0 24 24",
							"aria-hidden": "true"
						}, [p("path", { d: "m9 6 6 6-6 6" })], -1)]])]),
						p("div", mt, [
							p("section", ht, [n[54] ||= p("h4", null, "当前队列", -1), p("div", gt, [
								p("div", null, [n[51] ||= p("span", null, "运行中", -1), p("strong", null, f(P(Y.value.running)), 1)]),
								p("div", null, [n[52] ||= p("span", null, "待处理", -1), p("strong", null, f(P(Y.value.pending)), 1)]),
								p("div", null, [n[53] ||= p("span", null, "停止中", -1), p("strong", null, f(P(Y.value.stopping)), 1)])
							])]),
							p("section", _t, [p("h4", null, [n[55] ||= S("今日结果 ", -1), p("small", null, f(J.value.today), 1)]), p("div", vt, [
								p("div", null, [n[56] ||= p("span", null, "成功", -1), p("strong", yt, f(P(X.value.success)), 1)]),
								p("div", null, [n[57] ||= p("span", null, "部分成功", -1), p("strong", bt, f(P(X.value.partial_success)), 1)]),
								p("div", null, [n[58] ||= p("span", null, "失败", -1), p("strong", xt, f(P(X.value.failed)), 1)])
							])]),
							p("section", St, [
								p("h4", null, [n[59] ||= S("累计结果 ", -1), p("small", null, f(P(J.value.total)) + " 个任务", 1)]),
								Mt.value.length ? (t(), x("div", Ct, [(t(!0), x(l, null, i(Mt.value, (e) => (t(), x("i", {
									key: e.key,
									style: u({
										width: e.value / Math.max(1, J.value.total) * 100 + "%",
										background: e.color
									})
								}, null, 4))), 128))])) : (t(), x("div", wt)),
								p("div", Tt, [(t(!0), x(l, null, i(Mt.value, (e) => (t(), x("span", { key: e.key }, [p("i", { style: u({ background: e.color }) }, null, 4), S(f(e.label) + " " + f(P(e.value)), 1)]))), 128)), Mt.value.length ? s("", !0) : (t(), x("span", Et, "暂无累计结果"))])
							])
						]),
						At.value ? (t(), x("p", Dt, "注册功能未启用，历史任务仍可查看。")) : s("", !0)
					])
				])
			], 64)) : s("", !0)
		], 2));
	}
}), [["__scopeId", "data-v-b190bba0"]]);
// src/api/dashboard.ts
async function kt(e, t) {
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
function J(e = (e, t) => C(e, t), t) {
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
			let i = await kt(r, e);
			if (typeof i != "object" || !i || !("ok" in i) || i.ok !== !0) throw new w("能力检查返回无效数据", 200);
			return i;
		}
	};
}
// src/dashboard.ts
function At(e, t = {}) {
	let n = _(Ot, {
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
export { At as mountDashboard };
