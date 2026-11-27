import { C as e, F as t, H as n, K as r, L as i, M as a, S as o, _ as s, a as c, c as l, d as u, et as d, ft as f, g as p, h as m, i as h, j as ee, l as te, lt as g, m as _, n as ne, nt as v, o as y, s as re, st as b, v as x, x as S } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { t as ie } from "./ListPagination-CSFkV2Gz.js";
import { t as ae } from "./TableState-CxHYH8ID.js";
import { r as oe } from "./client-B5R_MNgP.js";
// src/features/sales/useSalesList.ts
function se(e, t = () => {}, n = () => {}) {
	let r = v([]), i = d(0), a = d(1), o = d(20), s = d(""), c = d(null), l = d(""), u = d(""), f = d({
		all: 0,
		for_sale: 0,
		listed: 0,
		sold: 0
	}), p = d(/* @__PURE__ */ new Set()), m = d(!1), h = d(""), ee = d(!1), te = _(() => Math.max(1, Math.ceil(i.value / o.value))), g = 0;
	function ne() {
		p.value = /* @__PURE__ */ new Set();
	}
	async function y() {
		if (!ee.value) return;
		let t = ++g;
		m.value = !0, h.value = "";
		try {
			let n = {
				page: a.value,
				page_size: o.value,
				status: s.value,
				shop_id: c.value,
				source_id: l.value,
				q: u.value
			}, d = await e.list(n);
			if (t !== g) return;
			r.value = d.items, i.value = d.total, f.value = d.counts;
		} catch (e) {
			if (t !== g) return;
			h.value = e instanceof Error ? e.message : "销售列表加载失败，请稍后重试。";
		} finally {
			t === g && (m.value = !1);
		}
	}
	function re(e) {
		s.value !== e && (s.value = e, a.value = 1, ne(), y());
	}
	function b(e, t) {
		let n = new Set(p.value);
		(t === void 0 ? n.has(e) : !t) ? n.delete(e) : n.add(e), p.value = n;
	}
	function x(e) {
		let t = new Set(p.value);
		r.value.forEach((n) => e ? t.add(n.id) : t.delete(n.id)), p.value = t;
	}
	async function S(r) {
		let i = [...p.value];
		if (!i.length) t("请先选择销售条目");
		else try {
			let a = await e.changeStatus({
				item_ids: i,
				status: r
			}), o = new Set(a.items.filter((e) => e.status === "failed" || e.error_code).map((e) => e.id));
			p.value = new Set(i.filter((e) => o.has(e))), n(a.items), ie(a, t), await y();
		} catch (e) {
			t(e instanceof Error ? e.message : "批量修改状态失败，请稍后重试。");
		}
	}
	function ie(e, n = t) {
		let r = e.items.filter((e) => e.status === "failed" || e.error_code).map((e) => `#${e.id} ${e.error_code || "failed"}${e.message ? `：${e.message}` : ""}`);
		e.failed_count ? n(`已完成 ${e.success_count} 项，失败 ${e.failed_count} 项${r.length ? `：${r.join("；")}` : ""}`) : n(`已更新 ${e.success_count} 项`);
	}
	function ae(e) {
		let t = Math.min(te.value, Math.max(1, e));
		t !== a.value && (a.value = t, y());
	}
	function oe(e) {
		e !== o.value && (o.value = e, a.value = 1, y());
	}
	function se(e) {
		ee.value = e, e ? y() : (g++, m.value = !1);
	}
	return {
		items: r,
		total: i,
		page: a,
		pageSize: o,
		status: s,
		shopId: c,
		sourceId: l,
		query: u,
		counts: f,
		pages: te,
		selected: p,
		loading: m,
		error: h,
		visible: ee,
		refresh: y,
		setVisible: se,
		setStatus: re,
		toggle: b,
		togglePage: x,
		clearSelection: ne,
		changeStatus: S,
		setPage: ae,
		setSize: oe
	};
}
// src/features/sales/SalesPage.vue?vue&type=script&setup=true&lang.ts
var ce = {
	class: "sales-page",
	"aria-label": "贩卖区"
}, le = { class: "ui-list sales-workspace" }, ue = { class: "sales-head" }, de = { class: "sales-head-actions" }, fe = {
	class: "sales-tabs",
	role: "tablist",
	"aria-label": "销售状态"
}, pe = [
	"data-status",
	"aria-selected",
	"onClick"
], me = { class: "ui-list-toolbar sales-toolbar" }, he = { class: "ui-list-toolbar__main" }, ge = { class: "ui-list-count" }, _e = {
	key: 0,
	class: "sales-selection",
	role: "status"
}, ve = ["value"], ye = ["value"], be = { class: "ui-list-toolbar__actions" }, xe = ["disabled"], Se = ["disabled"], Ce = ["disabled"], we = ["disabled"], Te = ["disabled"], Ee = ["disabled"], De = { key: 0 }, Oe = {
	key: 1,
	class: "sales-receipt-list"
}, ke = {
	key: 1,
	class: "sales-loading",
	"aria-live": "polite"
}, Ae = { class: "ui-table-scroll" }, je = { class: "ui-table ui-table--sticky-end sales-table" }, Me = { class: "ui-col-check" }, Ne = ["checked", "indeterminate"], Pe = { class: "ui-col-check" }, Fe = [
	"data-item-check",
	"checked",
	"aria-label",
	"onChange"
], Ie = {
	key: 0,
	class: "sales-error"
}, Le = { key: 0 }, Re = { key: 1 }, ze = { key: 2 }, Be = {
	key: 0,
	class: "sales-warning"
}, Ve = {
	key: 1,
	class: "sales-muted"
}, He = ["onClick"], Ue = {
	key: 0,
	class: "sales-dialog",
	role: "dialog",
	"aria-modal": "true",
	"aria-labelledby": "salesListingTitle"
}, We = { class: "sales-dialog-body" }, Ge = ["value"], Ke = {
	key: 0,
	class: "sales-notice sales-notice--warning"
}, qe = ["value", "disabled"], Je = ["disabled"], Ye = {
	key: 1,
	class: "sales-dialog",
	role: "dialog",
	"aria-modal": "true",
	"aria-labelledby": "salesAddTitle"
}, Xe = { class: "sales-dialog-body" }, Ze = ["value"], Qe = ["disabled"], $e = {
	key: 2,
	class: "sales-dialog sales-dialog--wide",
	role: "dialog",
	"aria-modal": "true",
	"aria-labelledby": "salesManagementTitle"
}, et = { class: "sales-management-tabs" }, tt = { class: "sales-dialog-body sales-management" }, nt = { class: "sales-config-list" }, rt = ["onClick"], it = ["onClick"], at = {
	key: 0,
	class: "sales-empty"
}, ot = { class: "sales-form-grid" }, st = { class: "sales-check" }, ct = { class: "sales-config-list" }, lt = ["onClick"], ut = { class: "sales-form-grid" }, dt = ["disabled"], ft = { class: "sales-check" }, pt = {
	key: 3,
	class: "sales-dialog sales-dialog--wide",
	role: "dialog",
	"aria-modal": "true",
	"aria-labelledby": "salesJobsTitle"
}, mt = ["disabled"], ht = { class: "sales-dialog-body sales-jobs" }, gt = {
	key: 0,
	class: "sales-empty"
}, _t = {
	key: 1,
	class: "sales-notice sales-notice--warning",
	role: "alert"
}, vt = {
	key: 2,
	class: "sales-empty"
}, yt = { key: 0 }, bt = { key: 1 }, xt = { key: 2 }, St = ["onClick"], Ct = {
	key: 4,
	class: "sales-dialog sales-dialog--wide",
	role: "dialog",
	"aria-modal": "true",
	"aria-labelledby": "salesEventsTitle"
}, wt = { class: "sales-dialog-body sales-events" }, Tt = {
	key: 0,
	class: "sales-empty"
}, Et = {
	key: 1,
	class: "sales-notice sales-notice--warning",
	role: "alert"
}, Dt = {
	key: 2,
	class: "sales-empty"
}, C = /* @__PURE__ */ e({
	__name: "SalesPage",
	props: {
		api: {},
		initialVisible: {
			type: Boolean,
			default: !0
		},
		notify: {},
		executorId: { default: "local" },
		openTask: {}
	},
	setup(e, { expose: ne }) {
		let v = e, oe = v.notify || ((e) => {}), C = d([]), w = d([]), T = d([]), E = d(!1), D = d(""), O = d(""), Ot = d("success"), kt = d(!1), k = d(v.initialVisible), A = d(!1), j = d(!1), M = d("shops"), N = d(!1), At = d([]), jt = d(!1), Mt = d(""), Nt = d(!1), Pt = d([]), P = d(null), Ft = d(!1), It = d(""), Lt = d([]), F = d(null), I = d(null), Rt = d(!1), L = d(!1), R = d("local"), z = d(""), zt = d(!1), B = d({
			id: "",
			name: "",
			kind: "remote",
			base_url: "",
			auth_env: "",
			enabled: !0
		}), V = d({
			name: "",
			platform: "liandong",
			base_url: "https://wzyp.cn",
			token_env: "",
			enabled: !1,
			owner_id: v.executorId,
			sync_interval: 60
		}), H = d(null), U = d(null), Bt = d(null), W = d(null), Vt = [
			[
				"",
				"全部",
				"all"
			],
			[
				"for_sale",
				"待售",
				"for_sale"
			],
			[
				"listed",
				"已上架",
				"listed"
			],
			[
				"sold",
				"已售出",
				"sold"
			]
		], Ht = (e) => ({
			for_sale: "待售",
			listed: "已上架",
			sold: "已售出"
		})[e] || e || "全部", Ut = (e) => ({
			idle: "待同步",
			pending: "排队中",
			running: "同步中",
			success: "已同步",
			failed: "同步失败",
			paused: "已暂停",
			unknown: "待确认"
		})[e] || e || "未知", Wt = (e) => e === "sold" ? "success" : e === "listed" ? "active" : "neutral";
		_(() => K.items.value.filter((e) => K.selected.value.has(e.id)));
		let Gt = _(() => {
			let e = w.value.find((e) => e.id === F.value);
			return e && e.owner_id !== v.executorId ? `当前执行端为 ${v.executorId}，店铺绑定 ${e.owner_id}；提交后由后端校验执行端权限。` : "";
		});
		function G(e, t = "success") {
			O.value = e, Ot.value = t, oe(e);
		}
		let K = se(v.api, (e) => G(e, "warning"), (e) => {
			Lt.value = e;
		}), q = _(() => K.selected.value.size), Kt = _(() => K.items.value.length > 0 && K.items.value.every((e) => K.selected.value.has(e.id))), J = 0, Y = 0, X = 0;
		async function Z() {
			let e = ++J;
			E.value = !0, D.value = "";
			try {
				let [t, n] = await Promise.all([v.api.sources(), v.api.shops()]);
				if (e !== J || !k.value) return;
				C.value = t.sources, w.value = n.shops, !R.value && C.value[0] && (R.value = C.value[0].id), kt.value = !0;
			} catch (t) {
				e === J && k.value && (D.value = t instanceof Error ? t.message : "销售配置加载失败，请重试。");
			} finally {
				e === J && (E.value = !1);
			}
		}
		async function qt(e) {
			if (T.value = [], I.value = null, e != null) try {
				T.value = (await v.api.products(e)).products;
			} catch (e) {
				G(e instanceof Error ? e.message : "商品加载失败，请重试。", "error");
			}
		}
		function Jt(e) {
			k.value = e, K.setVisible(e);
		}
		function Yt(e) {
			K.togglePage(e.target.checked);
		}
		function Xt(e, t) {
			K.toggle(e, t.target.checked);
		}
		function Zt() {
			q.value ? (W.value = document.activeElement, A.value = !0, F.value = w.value.find((e) => e.enabled)?.id || w.value[0]?.id || null, F.value != null && qt(F.value), Q()) : G("请先选择待售条目。", "warning");
		}
		async function Qt() {
			if (F.value == null || I.value == null) G("请选择店铺和商品。", "warning");
			else {
				Rt.value = !0;
				try {
					let e = await v.api.listItems({
						shop_id: F.value,
						product_id: I.value,
						item_ids: [...K.selected.value],
						request_key: globalThis.crypto?.randomUUID?.() || `sales-${Date.now()}`
					});
					K.clearSelection(), A.value = !1, G(`上架任务已受理：${e.task_id}`), await K.refresh();
				} catch (e) {
					G(e instanceof Error ? e.message : "上架任务提交失败，请重试。", "error");
				} finally {
					Rt.value = !1;
				}
			}
		}
		async function $t() {
			let e = z.value.split(/[,\s，]+/).map((e) => Number(e)).filter((e) => Number.isSafeInteger(e) && e > 0);
			if (!R.value || !e.length) G("请输入账号 ID，并选择账号来源。", "warning");
			else {
				zt.value = !0;
				try {
					let t = await v.api.addItems({
						source_id: R.value,
						account_ids: [...new Set(e)]
					});
					L.value = !1, z.value = "", G(t.failed_count ? `已加入 ${t.success_count} 个，失败 ${t.failed_count} 个` : `已加入 ${t.success_count} 个`, t.failed_count ? "warning" : "success"), await K.refresh();
				} catch (e) {
					G(e instanceof Error ? e.message : "加入待售失败，请重试。", "error");
				} finally {
					zt.value = !1;
				}
			}
		}
		async function en() {
			if (K.shopId.value == null) G("请先选择店铺。", "warning");
			else try {
				G(`同步任务已受理：${(await v.api.syncShop(K.shopId.value, globalThis.crypto?.randomUUID?.() || `sync-${Date.now()}`)).task_id}`), await Z(), await K.refresh();
			} catch (e) {
				G(e instanceof Error ? e.message : "同步任务提交失败，请重试。", "error");
			}
		}
		async function tn(e) {
			try {
				G(`连接成功，已读取 ${(await v.api.checkShop(e)).product_count} 个商品。`), await Z();
			} catch (e) {
				G(e instanceof Error ? e.message : "店铺连接检查失败，请重试。", "error");
			}
		}
		async function nn() {
			W.value = document.activeElement, N.value = !0, At.value = [], Mt.value = "", jt.value = !0;
			let e = ++Y;
			try {
				let t = await v.api.jobs();
				e === Y && (At.value = t.jobs);
			} catch (t) {
				e === Y && (Mt.value = t instanceof Error ? t.message : "任务回执加载失败，请重试。");
			} finally {
				e === Y && (jt.value = !1);
			}
			Q();
		}
		async function rn(e) {
			W.value = document.activeElement, P.value = e, Nt.value = !0, Pt.value = [], It.value = "", Ft.value = !0;
			let t = ++X;
			try {
				let n = await v.api.events(e.id);
				t === X && (Pt.value = n.events);
			} catch (e) {
				t === X && (It.value = e instanceof Error ? e.message : "历史记录加载失败，请重试。");
			} finally {
				t === X && (Ft.value = !1);
			}
			Q();
		}
		function an(e) {
			H.value = e.id, V.value = { ...e };
		}
		function on(e) {
			U.value = e.id, B.value = { ...e };
		}
		async function sn() {
			if (!B.value.id || !B.value.name) {
				G("请填写来源 ID 和名称。", "warning");
				return;
			}
			let e = B.value, t = {
				id: U.value || e.id,
				name: e.name,
				kind: e.kind,
				base_url: e.base_url || "",
				auth_env: e.auth_env || "",
				enabled: e.enabled !== !1
			};
			try {
				await v.api.saveSource(t), G("来源已保存。"), await Z(), U.value = null, B.value = {
					id: "",
					name: "",
					kind: "remote",
					base_url: "",
					auth_env: "",
					enabled: !0
				};
			} catch (e) {
				G(e instanceof Error ? e.message : "来源保存失败，请重试。", "error");
			}
		}
		async function cn() {
			if (!V.value.name) {
				G("请填写店铺名称。", "warning");
				return;
			}
			let e = V.value, t = {
				id: H.value || e.id,
				name: e.name,
				platform: e.platform || "liandong",
				base_url: e.base_url || "https://wzyp.cn",
				token_env: e.token_env || "",
				enabled: e.enabled === !0,
				owner_id: e.owner_id || v.executorId,
				sync_interval: Number(e.sync_interval ?? 60)
			};
			try {
				await v.api.saveShop(t), G("店铺已保存。"), await Z(), H.value = null, V.value = {
					name: "",
					platform: "liandong",
					base_url: "https://wzyp.cn",
					token_env: "",
					enabled: !1,
					owner_id: v.executorId,
					sync_interval: 60
				};
			} catch (e) {
				G(e instanceof Error ? e.message : "店铺保存失败，请重试。", "error");
			}
		}
		async function Q() {
			await new Promise((e) => requestAnimationFrame(e)), Bt.value?.querySelector("button,input,select")?.focus();
		}
		function $() {
			A.value = !1, j.value = !1, N.value = !1, Nt.value = !1, L.value = !1, Y++, X++, W.value?.focus?.({ preventScroll: !0 }), W.value = null;
		}
		function ln(e) {
			e.key === "Escape" && (A.value || j.value || N.value || Nt.value || L.value) && (e.preventDefault(), $());
		}
		let un = (e) => ({
			sync: "同步店铺",
			list: "上架商品",
			sales_sync: "销售同步"
		})[e] || e || "销售任务", dn = (e) => ({
			queued: "排队中",
			waiting: "等待中",
			running: "执行中",
			settling: "收口中",
			success: "已完成",
			completed: "已完成",
			failed: "失败",
			partial_success: "部分成功",
			interrupted: "已中断",
			cancelling: "停止中",
			cancelled: "已取消",
			stopped: "已停止",
			for_sale: "待售",
			listed: "已上架",
			sold: "已售出",
			archived: "已归档"
		})[e] || e || "待确认";
		function fn(e) {
			let t = e && typeof e == "object" && !Array.isArray(e) ? e : {}, n = Array.isArray(t.items) ? t.items : [], r = (e) => typeof t[e] == "number" && Number.isFinite(t[e]) ? Number(t[e]) : null, i = r("total") ?? n.length, a = r("success_count") ?? n.filter((e) => [
				"success",
				"completed",
				"listed",
				"sold",
				"archived"
			].includes(String(e.status || ""))).length, o = r("failed_count") ?? n.filter((e) => !!e.error_code || ["failed", "error"].includes(String(e.status || ""))).length, s = r("archived_count"), c = r("archive_failed_count"), l = [
				`共 ${i} 项`,
				`成功 ${a} 项`,
				`失败 ${o} 项`
			];
			return (s != null || c != null) && l.push(`已归档 ${s ?? 0} 项`, `归档失败 ${c ?? 0} 项`), l.join("，");
		}
		function pn(e) {
			let t = e && typeof e == "object" ? e : {}, n = t.result_summary;
			return n && typeof n == "object" && !Array.isArray(n) && Array.isArray(n.items) ? n.items : Array.isArray(n) ? n : Array.isArray(t.items) ? t.items : [];
		}
		function mn(e) {
			let t = e && typeof e == "object" ? e : {}, n = String(t.task_id || ""), r = t.run_id == null ? void 0 : String(t.run_id);
			(n || r) && v.openTask?.(n, r);
		}
		return n(() => K.shopId.value, (e) => {
			e != null && qt(e);
		}), n(() => K.query.value, () => {
			K.clearSelection(), K.page.value = 1;
		}), a(() => {
			document.addEventListener("keydown", ln), k.value && (K.setVisible(!0), Z());
		}), n(k, (e) => {
			e && !kt.value && Z(), e || (J++, Y++, X++);
		}), ee(() => document.removeEventListener("keydown", ln)), ne({
			setVisible: Jt,
			refresh: () => Promise.all([K.refresh(), Z()]),
			addAccounts: (e, t) => {
				R.value = e, z.value = t.join(","), L.value = !0, Q();
			},
			closeDialogs: $
		}), (e, n) => r((t(), x("section", ce, [m("div", le, [
			m("header", ue, [n[34] ||= m("div", null, [m("h1", null, "贩卖区"), m("p", null, "管理账号销售条目、店铺商品和同步回执")], -1), m("div", de, [
				m("button", {
					type: "button",
					class: "ui-button",
					"data-open-add": "",
					onClick: n[0] ||= (e) => {
						L.value = !0, Q();
					}
				}, "加入待售"),
				m("button", {
					type: "button",
					class: "ui-button",
					"data-open-management": "",
					onClick: n[1] ||= (e) => {
						j.value = !0, M.value = "shops", Q();
					}
				}, "店铺与来源"),
				m("button", {
					type: "button",
					class: "ui-button",
					"data-open-jobs": "",
					onClick: nn
				}, "任务回执")
			])]),
			m("div", fe, [(t(), x(u, null, i(Vt, ([e, t, n]) => m("button", {
				key: n,
				type: "button",
				role: "tab",
				"data-status": n,
				"aria-selected": b(K).status.value === e,
				class: g({ "is-active": b(K).status.value === e }),
				onClick: (t) => b(K).setStatus(e)
			}, [S(f(t), 1), m("span", null, f(b(K).counts.value[n]), 1)], 10, pe)), 64))]),
			m("div", me, [m("div", he, [
				m("span", ge, f(b(K).total.value.toLocaleString()) + " 条", 1),
				q.value ? (t(), x("span", _e, "已选 " + f(q.value) + " 项", 1)) : s("", !0),
				r(m("input", {
					"onUpdate:modelValue": n[2] ||= (e) => b(K).query.value = e,
					class: "sales-search",
					type: "search",
					placeholder: "搜索邮箱、订单号或商品",
					"aria-label": "搜索销售条目",
					onKeyup: n[3] ||= l((e) => {
						b(K).page.value = 1, b(K).refresh();
					}, ["enter"])
				}, null, 544), [[y, b(K).query.value]]),
				r(m("select", {
					"onUpdate:modelValue": n[4] ||= (e) => b(K).sourceId.value = e,
					"aria-label": "账号来源",
					onChange: n[5] ||= (e) => {
						b(K).page.value = 1, b(K).clearSelection(), b(K).refresh();
					}
				}, [n[35] ||= m("option", { value: "" }, "全部来源", -1), (t(!0), x(u, null, i(C.value, (e) => (t(), x("option", {
					key: e.id,
					value: e.id
				}, f(e.name), 9, ve))), 128))], 544), [[c, b(K).sourceId.value]]),
				r(m("select", {
					"onUpdate:modelValue": n[6] ||= (e) => b(K).shopId.value = e,
					"aria-label": "店铺",
					onChange: n[7] ||= (e) => {
						b(K).page.value = 1, b(K).clearSelection(), b(K).refresh();
					}
				}, [n[36] ||= m("option", { value: null }, "全部店铺", -1), (t(!0), x(u, null, i(w.value, (e) => (t(), x("option", {
					key: e.id,
					value: e.id
				}, f(e.name), 9, ye))), 128))], 544), [[c, b(K).shopId.value]])
			]), m("div", be, [
				m("button", {
					type: "button",
					class: "ui-button",
					disabled: !q.value,
					"data-open-listing": "",
					onClick: Zt
				}, "选择商品上架", 8, xe),
				m("button", {
					type: "button",
					class: "ui-button",
					disabled: !q.value,
					"data-bulk-status": "listed",
					onClick: n[8] ||= (e) => b(K).changeStatus("listed")
				}, "标记已上架", 8, Se),
				m("button", {
					type: "button",
					class: "ui-button",
					disabled: !q.value,
					"data-bulk-status": "sold",
					onClick: n[9] ||= (e) => b(K).changeStatus("sold")
				}, "标记已售出", 8, Ce),
				m("button", {
					type: "button",
					class: "ui-button",
					disabled: !q.value,
					"data-bulk-status": "for_sale",
					onClick: n[10] ||= (e) => b(K).changeStatus("for_sale")
				}, "撤销售出", 8, we),
				m("button", {
					type: "button",
					class: "ui-button",
					disabled: b(K).loading.value,
					onClick: n[11] ||= (...e) => b(K).refresh && b(K).refresh(...e)
				}, "刷新", 8, Te),
				m("button", {
					type: "button",
					class: "ui-button",
					disabled: b(K).shopId.value == null,
					onClick: en
				}, "立即同步", 8, Ee)
			])]),
			D.value || O.value || Lt.value.length ? (t(), x("div", {
				key: 0,
				class: g(["ui-list-feedback", { "is-error": D.value || Ot.value === "error" }]),
				role: "alert"
			}, [D.value || O.value ? (t(), x("p", De, f(D.value || O.value), 1)) : s("", !0), Lt.value.length ? (t(), x("ul", Oe, [(t(!0), x(u, null, i(Lt.value, (e) => (t(), x("li", { key: e.id }, [
				S("#" + f(e.id) + " · " + f(e.status), 1),
				e.error_code ? (t(), x(u, { key: 0 }, [S(" · " + f(e.error_code), 1)], 64)) : s("", !0),
				e.message ? (t(), x(u, { key: 1 }, [S("：" + f(e.message), 1)], 64)) : s("", !0)
			]))), 128))])) : s("", !0)], 2)) : s("", !0),
			b(K).loading.value ? (t(), x("div", ke, "正在加载销售条目…")) : s("", !0),
			m("div", Ae, [m("table", je, [m("thead", null, [m("tr", null, [
				m("th", Me, [m("input", {
					type: "checkbox",
					checked: Kt.value,
					indeterminate: q.value > 0 && !Kt.value,
					"aria-label": "选择当前页",
					onChange: Yt
				}, null, 40, Ne)]),
				n[37] ||= m("th", null, "账号与来源", -1),
				n[38] ||= m("th", null, "销售状态", -1),
				n[39] ||= m("th", null, "店铺 / 商品", -1),
				n[40] ||= m("th", null, "订单与金额", -1),
				n[41] ||= m("th", null, "同步与归档", -1),
				n[42] ||= m("th", null, "操作", -1)
			])]), m("tbody", null, [b(K).loading.value || b(K).error.value || !b(K).items.value.length ? (t(), p(ae, {
				key: 0,
				colspan: 7,
				loading: b(K).loading.value,
				error: b(K).error.value,
				title: "暂无销售条目",
				text: "可从账号列表批量加入待售，或调整筛选条件。",
				"retry-label": "重试",
				onRetry: b(K).refresh
			}, null, 8, [
				"loading",
				"error",
				"onRetry"
			])) : (t(!0), x(u, { key: 1 }, i(b(K).items.value, (e) => (t(), x("tr", {
				key: e.id,
				class: g({ "is-selected": b(K).selected.value.has(e.id) })
			}, [
				m("td", Pe, [m("input", {
					"data-item-check": e.id,
					type: "checkbox",
					checked: b(K).selected.value.has(e.id),
					"aria-label": `选择销售条目 ${e.id}`,
					onChange: (t) => Xt(e.id, t)
				}, null, 40, Fe)]),
				m("td", null, [m("strong", null, f(e.email), 1), m("small", null, f(e.source_id) + " · 账号 #" + f(e.account_id) + " · " + f(e.plan || "套餐未记录"), 1)]),
				m("td", null, [m("span", { class: g(["ui-badge", `ui-badge--${Wt(e.status)}`]) }, f(Ht(e.status)), 3), e.error_message ? (t(), x("small", Ie, f(e.error_message), 1)) : s("", !0)]),
				m("td", null, [m("strong", null, f(e.shop_name || "未上架"), 1), m("small", null, f(e.product_name || "尚未选择商品"), 1)]),
				m("td", null, [e.order_ref ? (t(), x("strong", Le, f(e.order_ref), 1)) : (t(), x("strong", Re, f(e.price == null ? "—" : `${e.price} ${e.currency}`), 1)), e.order_amount == null ? s("", !0) : (t(), x("small", ze, f(e.order_amount) + " " + f(e.currency), 1))]),
				m("td", null, [
					m("span", { class: g(["ui-badge", e.sync_status === "failed" ? "ui-badge--danger" : e.sync_status === "running" ? "ui-badge--active" : ""]) }, f(Ut(e.sync_status)), 3),
					e.archive_pending ? (t(), x("small", Be, "归档待办")) : s("", !0),
					e.archived ? (t(), x("small", Ve, "来源已归档")) : s("", !0)
				]),
				m("td", null, [m("button", {
					type: "button",
					class: "ui-link",
					onClick: (t) => rn(e)
				}, "历史", 8, He)])
			], 2))), 128))])])]),
			o(ie, {
				page: b(K).page.value,
				size: b(K).pageSize.value,
				pages: b(K).pages.value,
				total: b(K).total.value,
				busy: b(K).loading.value,
				"page-sizes": [
					20,
					50,
					100
				],
				label: "销售条目分页",
				"onUpdate:page": b(K).setPage,
				"onUpdate:size": b(K).setSize
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		]), A.value || L.value || j.value || N.value || Nt.value ? (t(), x("div", {
			key: 0,
			ref_key: "dialog",
			ref: Bt,
			class: "sales-modal-backdrop",
			onClick: te($, ["self"])
		}, [A.value ? (t(), x("section", Ue, [
			m("header", null, [m("div", null, [n[43] ||= m("h2", { id: "salesListingTitle" }, "选择店铺商品", -1), m("p", null, "将 " + f(q.value) + " 个销售条目提交为持久上架任务。", 1)]), m("button", {
				type: "button",
				class: "ui-button",
				onClick: $
			}, "关闭")]),
			m("div", We, [
				m("label", null, [n[45] ||= S("店铺", -1), r(m("select", {
					"onUpdate:modelValue": n[12] ||= (e) => F.value = e,
					onChange: n[13] ||= (e) => qt(F.value)
				}, [n[44] ||= m("option", { value: null }, "请选择", -1), (t(!0), x(u, null, i(w.value, (e) => (t(), x("option", {
					key: e.id,
					value: e.id
				}, f(e.name), 9, Ge))), 128))], 544), [[c, F.value]])]),
				Gt.value ? (t(), x("p", Ke, f(Gt.value), 1)) : s("", !0),
				m("label", null, [n[47] ||= S("商品", -1), r(m("select", { "onUpdate:modelValue": n[14] ||= (e) => I.value = e }, [n[46] ||= m("option", { value: null }, "请选择", -1), (t(!0), x(u, null, i(T.value, (e) => (t(), x("option", {
					key: e.id,
					value: e.id,
					disabled: e.status === "unavailable"
				}, f(e.name) + " · " + f(e.goods_key), 9, qe))), 128))], 512), [[c, I.value]])])
			]),
			m("footer", null, [m("button", {
				type: "button",
				class: "ui-button",
				onClick: $
			}, "取消"), m("button", {
				type: "button",
				class: "ui-button ui-button--primary",
				"data-listing-submit": "",
				disabled: Rt.value,
				onClick: Qt
			}, f(Rt.value ? "提交中…" : "提交上架"), 9, Je)])
		])) : L.value ? (t(), x("section", Ye, [
			m("header", null, [n[48] ||= m("div", null, [m("h2", { id: "salesAddTitle" }, "加入待售"), m("p", null, "只读取所选来源的账号摘要，不显示密码、Token 或完整交付材料。")], -1), m("button", {
				type: "button",
				class: "ui-button",
				onClick: $
			}, "关闭")]),
			m("div", Xe, [m("label", null, [n[49] ||= S("账号来源", -1), r(m("select", { "onUpdate:modelValue": n[15] ||= (e) => R.value = e }, [(t(!0), x(u, null, i(C.value, (e) => (t(), x("option", {
				key: e.id,
				value: e.id
			}, f(e.name), 9, Ze))), 128))], 512), [[c, R.value]])]), m("label", null, [n[50] ||= S("账号 ID", -1), r(m("input", {
				"onUpdate:modelValue": n[16] ||= (e) => z.value = e,
				inputmode: "numeric",
				placeholder: "例如 1024,1025"
			}, null, 512), [[y, z.value]])])]),
			m("footer", null, [m("button", {
				type: "button",
				class: "ui-button",
				onClick: $
			}, "取消"), m("button", {
				type: "button",
				class: "ui-button ui-button--primary",
				disabled: zt.value,
				onClick: $t
			}, f(zt.value ? "加入中…" : "加入待售"), 9, Qe)])
		])) : j.value ? (t(), x("section", $e, [
			m("header", null, [n[51] ||= m("div", null, [m("h2", { id: "salesManagementTitle" }, "店铺与来源"), m("p", null, "这里只保存环境变量名称，不保存或展示真实 Token、授权码和交付资料。")], -1), m("button", {
				type: "button",
				class: "ui-button",
				onClick: $
			}, "关闭")]),
			m("div", et, [m("button", {
				type: "button",
				class: g({ "is-active": M.value === "shops" }),
				onClick: n[17] ||= (e) => M.value = "shops"
			}, "店铺", 2), m("button", {
				type: "button",
				class: g({ "is-active": M.value === "sources" }),
				onClick: n[18] ||= (e) => M.value = "sources"
			}, "账号来源", 2)]),
			m("div", tt, [M.value === "shops" ? (t(), x(u, { key: 0 }, [m("div", nt, [(t(!0), x(u, null, i(w.value, (e) => (t(), x("article", { key: e.id }, [
				m("strong", null, f(e.name), 1),
				m("span", null, f(e.platform) + " · " + f(e.enabled ? "已启用" : "未启用") + " · " + f(e.token_env || "未配置环境变量") + " · Token " + f(e.token_configured ? "已配置" : "缺失"), 1),
				m("button", {
					type: "button",
					class: "ui-link",
					onClick: (t) => an(e)
				}, "编辑", 8, rt),
				m("button", {
					type: "button",
					class: "ui-link",
					onClick: (t) => tn(e.id)
				}, "检查连接", 8, it)
			]))), 128)), w.value.length ? s("", !0) : (t(), x("p", at, "还没有店铺配置。"))]), m("div", ot, [
				m("label", null, [n[52] ||= S("店铺名称", -1), r(m("input", { "onUpdate:modelValue": n[19] ||= (e) => V.value.name = e }, null, 512), [[y, V.value.name]])]),
				m("label", null, [n[53] ||= S("Token 环境变量", -1), r(m("input", {
					"onUpdate:modelValue": n[20] ||= (e) => V.value.token_env = e,
					placeholder: "LIANDONG_TOKEN"
				}, null, 512), [[y, V.value.token_env]])]),
				m("label", null, [n[54] ||= S("基础地址", -1), r(m("input", { "onUpdate:modelValue": n[21] ||= (e) => V.value.base_url = e }, null, 512), [[y, V.value.base_url]])]),
				m("label", null, [n[55] ||= S("执行端", -1), r(m("input", { "onUpdate:modelValue": n[22] ||= (e) => V.value.owner_id = e }, null, 512), [[y, V.value.owner_id]])]),
				m("label", null, [n[56] ||= S("同步周期（秒）", -1), r(m("input", {
					"onUpdate:modelValue": n[23] ||= (e) => V.value.sync_interval = e,
					type: "number",
					min: "1",
					step: "1"
				}, null, 512), [[
					y,
					V.value.sync_interval,
					void 0,
					{ number: !0 }
				]])]),
				m("label", st, [r(m("input", {
					"onUpdate:modelValue": n[24] ||= (e) => V.value.enabled = e,
					type: "checkbox"
				}, null, 512), [[h, V.value.enabled]]), n[57] ||= S("启用店铺", -1)]),
				m("button", {
					type: "button",
					class: "ui-button ui-button--primary",
					onClick: cn
				}, f(H.value ? "保存修改" : "保存店铺"), 1),
				H.value ? (t(), x("button", {
					key: 0,
					type: "button",
					class: "ui-link",
					onClick: n[25] ||= (e) => {
						H.value = null, V.value = {
							name: "",
							platform: "liandong",
							base_url: "https://wzyp.cn",
							token_env: "",
							enabled: !1,
							owner_id: v.executorId,
							sync_interval: 60
						};
					}
				}, "新建店铺")) : s("", !0)
			])], 64)) : (t(), x(u, { key: 1 }, [m("div", ct, [(t(!0), x(u, null, i(C.value, (e) => (t(), x("article", { key: e.id }, [
				m("strong", null, f(e.name), 1),
				m("span", null, f(e.id) + " · " + f(e.kind === "remote" ? "远端" : "本地") + " · " + f(e.enabled ? "已启用" : "未启用") + " · Auth " + f(e.auth_configured ? "已配置" : "缺失"), 1),
				m("button", {
					type: "button",
					class: "ui-link",
					onClick: (t) => on(e)
				}, "编辑", 8, lt)
			]))), 128))]), m("div", ut, [
				m("label", null, [n[58] ||= S("来源 ID", -1), r(m("input", {
					"onUpdate:modelValue": n[26] ||= (e) => B.value.id = e,
					placeholder: "oracle",
					disabled: !!U.value
				}, null, 8, dt), [[y, B.value.id]])]),
				m("label", null, [n[59] ||= S("来源名称", -1), r(m("input", { "onUpdate:modelValue": n[27] ||= (e) => B.value.name = e }, null, 512), [[y, B.value.name]])]),
				m("label", null, [n[60] ||= S("基础地址", -1), r(m("input", { "onUpdate:modelValue": n[28] ||= (e) => B.value.base_url = e }, null, 512), [[y, B.value.base_url]])]),
				m("label", null, [n[61] ||= S("Auth 环境变量", -1), r(m("input", {
					"onUpdate:modelValue": n[29] ||= (e) => B.value.auth_env = e,
					placeholder: "ORACLE_SALES_AUTH"
				}, null, 512), [[y, B.value.auth_env]])]),
				m("label", null, [n[63] ||= S("来源类型", -1), r(m("select", { "onUpdate:modelValue": n[30] ||= (e) => B.value.kind = e }, [...n[62] ||= [m("option", { value: "local" }, "本地", -1), m("option", { value: "remote" }, "远端", -1)]], 512), [[c, B.value.kind]])]),
				m("label", ft, [r(m("input", {
					"onUpdate:modelValue": n[31] ||= (e) => B.value.enabled = e,
					type: "checkbox"
				}, null, 512), [[h, B.value.enabled]]), n[64] ||= S("启用来源", -1)]),
				m("button", {
					type: "button",
					class: "ui-button ui-button--primary",
					onClick: sn
				}, f(U.value ? "保存修改" : "保存来源"), 1),
				U.value ? (t(), x("button", {
					key: 0,
					type: "button",
					class: "ui-link",
					onClick: n[32] ||= (e) => {
						U.value = null, B.value = {
							id: "",
							name: "",
							kind: "remote",
							base_url: "",
							auth_env: "",
							enabled: !0
						};
					}
				}, "新建来源")) : s("", !0)
			])], 64))])
		])) : N.value ? (t(), x("section", pt, [m("header", null, [
			n[65] ||= m("div", null, [m("h2", { id: "salesJobsTitle" }, "任务回执"), m("p", null, "销售同步与上架任务按逐项结果展示，未知结果仍可重试。")], -1),
			m("button", {
				type: "button",
				class: "ui-button",
				disabled: jt.value,
				onClick: nn
			}, "刷新回执", 8, mt),
			m("button", {
				type: "button",
				class: "ui-button",
				onClick: $
			}, "关闭")
		]), m("div", ht, [jt.value ? (t(), x("p", gt, "正在读取任务回执…")) : Mt.value ? (t(), x("p", _t, [S(f(Mt.value) + " ", 1), m("button", {
			type: "button",
			class: "ui-link",
			onClick: nn
		}, "重试")])) : At.value.length ? s("", !0) : (t(), x("p", vt, "暂无销售任务。")), (t(!0), x(u, null, i(At.value, (e) => (t(), x("article", { key: String(e.id) }, [
			m("strong", null, f(un(e.action)) + " · " + f(dn(e.status)), 1),
			m("span", null, [S("任务 " + f(e.task_id || e.id), 1), e.error_code ? (t(), x(u, { key: 0 }, [S(" · " + f(e.error_code), 1)], 64)) : s("", !0)]),
			e.error_message ? (t(), x("small", yt, f(e.error_message), 1)) : s("", !0),
			e.result_summary ? (t(), x("pre", bt, f(fn(e.result_summary)), 1)) : s("", !0),
			pn(e).length ? (t(), x("ul", xt, [(t(!0), x(u, null, i(pn(e), (n, r) => (t(), x("li", { key: `${String(e.id)}-${r}` }, [S("#" + f(n.id ?? "—") + " · " + f(dn(String(n.status || ""))) + " · " + f(n.error_code || "完成"), 1), n.message ? (t(), x(u, { key: 0 }, [S("：" + f(n.message), 1)], 64)) : s("", !0)]))), 128))])) : s("", !0),
			e.task_id || e.run_id ? (t(), x("button", {
				key: 3,
				type: "button",
				class: "ui-link",
				onClick: (t) => mn(e)
			}, "查看任务详情", 8, St)) : s("", !0)
		]))), 128))])])) : (t(), x("section", Ct, [m("header", null, [m("div", null, [n[66] ||= m("h2", { id: "salesEventsTitle" }, "条目历史", -1), m("p", null, f(P.value?.email) + " · 销售条目 #" + f(P.value?.id), 1)]), m("button", {
			type: "button",
			class: "ui-button",
			onClick: $
		}, "关闭")]), m("div", wt, [Ft.value ? (t(), x("p", Tt, "正在读取条目历史…")) : It.value ? (t(), x("p", Et, [S(f(It.value) + " ", 1), m("button", {
			type: "button",
			class: "ui-link",
			onClick: n[33] ||= (e) => P.value && rn(P.value)
		}, "重试")])) : Pt.value.length ? s("", !0) : (t(), x("p", Dt, "暂无变更记录。")), (t(!0), x(u, null, i(Pt.value, (e) => (t(), x("article", { key: e.id }, [
			m("strong", null, f(e.event), 1),
			m("time", null, f(e.created_at), 1),
			m("pre", null, f(JSON.stringify(e.changes, null, 2)), 1)
		]))), 128))])]))], 512)) : s("", !0)], 512)), [[re, k.value]]);
	}
});
// src/api/sales.ts
function w(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("销售接口返回格式无效");
	return e;
}
function T(e, t) {
	let n = w(e);
	if (n.ok !== !0) throw Error(typeof n.error == "string" ? n.error : "销售接口返回失败");
	if (t && !Array.isArray(n[t])) throw Error("销售接口返回格式无效");
	return n;
}
function E(e) {
	return {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(e)
	};
}
function D(e = oe) {
	return {
		async list(t) {
			return T(await e(`/api/sales/items?${new URLSearchParams(Object.entries(t).filter(([, e]) => e != null && e !== "").map(([e, t]) => [e, String(t)]))}`));
		},
		async sources() {
			return T(await e("/api/sales/sources"), "sources");
		},
		async shops() {
			return T(await e("/api/sales/shops"), "shops");
		},
		async products(t) {
			return T(await e(`/api/sales/shops/${encodeURIComponent(t)}/products`), "products");
		},
		async addItems(t) {
			return T(await e("/api/sales/items/add", E(t)), "items");
		},
		async changeStatus(t) {
			return T(await e("/api/sales/items/status", E(t)), "items");
		},
		async listItems(t) {
			return T(await e("/api/sales/list", E(t)));
		},
		async checkShop(t) {
			return T(await e(`/api/sales/shops/${encodeURIComponent(t)}/check`, E({})));
		},
		async syncShop(t, n) {
			return T(await e(`/api/sales/shops/${encodeURIComponent(t)}/sync`, E(n ? { request_key: n } : {})));
		},
		async jobs() {
			return T(await e("/api/sales/jobs"), "jobs");
		},
		async events(t) {
			return T(await e(`/api/sales/items/${encodeURIComponent(t)}/events`), "events");
		},
		async saveSource(t) {
			return T(await e("/api/sales/sources", E(t)));
		},
		async saveShop(t) {
			return T(await e("/api/sales/shops", E(t)));
		}
	};
}
// src/sales.ts
function O(e, t = {}) {
	let n = ne(C, {
		api: t.api || D(),
		notify: t.notify,
		executorId: t.executorId,
		openTask: t.openTask,
		initialVisible: t.initialVisible
	}), r = n.mount(e);
	return {
		setVisible: (e) => r.setVisible(e),
		refresh: () => r.refresh(),
		addAccounts: (e, t) => r.addAccounts(e, t),
		closeDialogs: () => r.closeDialogs?.(),
		destroy: () => n.unmount()
	};
}
export { O as mountSales };
