import { $ as e, F as t, I as n, K as r, M as i, O as a, P as o, R as s, S as c, T as l, Z as u, ft as d, it as f, j as p, k as m, lt as h, q as g, tt as _ } from "./ListFilterSummary-y5VgA65M.js";
// src/api/client.ts
var v = class extends Error {
	status;
	code;
	constructor(e, t, n = "") {
		super(e), this.status = t, this.code = n, this.name = "ApiError";
	}
};
async function y(e, t = {}, n) {
	let r = await fetch(e, {
		credentials: "same-origin",
		...t
	});
	if (!(r.headers.get("content-type") || "").includes("application/json")) throw new v(r.redirected || r.status === 401 ? "登录已失效，请重新登录后刷新。" : `服务返回了非 JSON 响应（HTTP ${r.status}）`, r.status);
	let i = n ? n(await r.text()) : await r.json();
	if (!r.ok || i?.ok === !1) {
		let e = i?.error;
		throw new v(typeof e == "string" ? e : e?.message || i?.message || `请求失败（HTTP ${r.status}）`, r.status, e?.code || i?.error_code || i?.code || "");
	}
	return i;
}
function b(e) {
	return e instanceof Error && e.name === "AbortError";
}
// src/shared/useColumnWidths.ts
function x(e) {
	let t = f([...e.defaults]), n = p(() => t.value.reduce((e, t) => e + t, 0));
	try {
		let r = JSON.parse(localStorage.getItem(e.storageKey) || "null");
		if (Array.isArray(r) && r.length === e.defaults.length && r.every((e) => typeof e == "number" && Number.isFinite(e) && e > 0)) {
			if (e.totalStorageKey) {
				let i = Number(localStorage.getItem(e.totalStorageKey)), a = Number.isFinite(i) && i > 0 ? i : n.value, o = r.reduce((e, t) => e + t, 0), s = r.map((e) => e / o * a);
				s.every((e) => Number.isFinite(e) && e > 0) && (t.value = s);
			} else r.every((t) => t >= (e.savedMin ?? e.min) && t <= e.max) && (t.value = r);
		}
	} catch {}
	let r;
	function i() {
		try {
			let r = e.totalStorageKey ? t.value.map((t) => Number((t / n.value * 100).toFixed(e.ratioPrecision ?? 4))) : t.value;
			localStorage.setItem(e.storageKey, JSON.stringify(r)), e.totalStorageKey && localStorage.setItem(e.totalStorageKey, String(Number(n.value.toFixed(e.totalPrecision ?? 0)))), e.onPersist?.();
		} catch {}
	}
	function a(n, r) {
		t.value[n] != null && Number.isFinite(r) && (t.value[n] = Math.max(e.min, Math.min(e.max, t.value[n] + r)), i());
	}
	function o(n, a) {
		if (t.value[n] == null) return;
		r?.();
		let o = t.value[n], s = a.clientX, c = (r) => {
			t.value[n] = Math.max(e.min, Math.min(e.max, o + r.clientX - s));
		}, l = () => {
			r?.(), i();
		};
		r = () => {
			document.removeEventListener("pointermove", c), document.removeEventListener("pointerup", l), document.removeEventListener("pointercancel", l), r = void 0;
		}, document.addEventListener("pointermove", c), document.addEventListener("pointerup", l, { once: !0 }), document.addEventListener("pointercancel", l, { once: !0 });
	}
	function s() {
		r?.(), t.value = [...e.defaults];
		try {
			localStorage.removeItem(e.storageKey), e.totalStorageKey && localStorage.removeItem(e.totalStorageKey), e.onReset?.();
		} catch {}
	}
	return _(() => r?.()), {
		widths: t,
		total: n,
		resize: o,
		resizeWithKeyboard: a,
		resetColumns: s
	};
}
// src/components/ListPagination.vue?vue&type=script&setup=true&lang.ts
var S = ["aria-label", "aria-busy"], C = { class: "list-pagination__layout" }, w = { class: "list-pagination__controls" }, T = { class: "list-pagination__pages" }, E = ["disabled"], D = [
	"aria-label",
	"aria-current",
	"disabled",
	"onClick"
], O = {
	key: 1,
	class: "list-pagination__ellipsis",
	"aria-hidden": "true"
}, k = {
	class: "list-pagination__mobile-page",
	"aria-live": "polite"
}, A = ["disabled"], j = [
	"aria-invalid",
	"title",
	"disabled"
], M = ["disabled"], N = { class: "list-pagination__meta" }, P = {
	class: "list-pagination__range",
	"aria-live": "polite"
}, F = { key: 0 }, I = { class: "list-pagination__size" }, L = ["value", "disabled"], R = ["value"], z = {
	key: 0,
	class: "list-pagination__error",
	role: "alert"
}, B = /*#__PURE__*/ c(/* @__PURE__ */ s({
	__name: "ListPagination",
	props: {
		page: {},
		size: {},
		total: {},
		pages: {},
		busy: {
			type: Boolean,
			default: !1
		},
		label: { default: "列表分页" },
		pageSizes: { default: () => [
			20,
			50,
			100
		] }
	},
	emits: ["update:page", "update:size"],
	setup(s, { emit: c }) {
		let _ = s, v = c, y = p(() => Math.max(0, Math.floor(_.total) || 0)), b = p(() => Math.max(1, Math.floor(_.size) || 1)), x = p(() => Math.max(1, Math.floor(_.pages || Math.ceil(y.value / b.value)) || 1)), B = p(() => Math.min(x.value, Math.max(1, Math.floor(_.page) || 1))), V = p(() => y.value ? Math.min(y.value, (B.value - 1) * b.value + 1) : 0), H = p(() => Math.min(y.value, B.value * b.value)), U = p(() => [.../* @__PURE__ */ new Set([..._.pageSizes, b.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), W = f(String(B.value)), G = f(!1);
		u([B, x], () => {
			W.value = String(B.value), G.value = !1;
		});
		let K = p(() => {
			let e = x.value;
			return e <= 7 ? Array.from({ length: e }, (e, t) => t + 1) : B.value <= 4 ? [
				1,
				2,
				3,
				4,
				5,
				"after",
				e
			] : B.value >= e - 3 ? [
				1,
				"before",
				e - 4,
				e - 3,
				e - 2,
				e - 1,
				e
			] : [
				1,
				"before",
				B.value - 1,
				B.value,
				B.value + 1,
				"after",
				e
			];
		});
		function q(e) {
			if (_.busy || !y.value) return;
			let t = Math.min(x.value, Math.max(1, e));
			W.value = String(t), G.value = !1, t !== B.value && v("update:page", t);
		}
		function J() {
			if (_.busy || !y.value) return;
			let e = Number(W.value.trim());
			!/^\d+$/.test(W.value.trim()) || !Number.isSafeInteger(e) ? G.value = !0 : q(e);
		}
		function Y(e) {
			if (_.busy) return;
			let t = Number(e.target.value);
			U.value.includes(t) && t !== b.value && (v("update:page", 1), v("update:size", t));
		}
		return (c, u) => (r(), t("nav", {
			class: "tc-pagination list-pagination",
			"aria-label": s.label,
			"aria-busy": s.busy
		}, [i("div", C, [
			i("div", w, [i("div", T, [
				i("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: s.busy || !y.value || B.value <= 1,
					onClick: u[0] ||= (e) => q(B.value - 1)
				}, "上一页", 8, E),
				(r(!0), t(m, null, g(K.value, (e) => (r(), t(m, { key: e }, [typeof e == "number" ? (r(), t("button", {
					key: 0,
					type: "button",
					class: h(["list-pagination__button list-pagination__number", { "is-current": e === B.value }]),
					"aria-label": `第 ${e} 页`,
					"aria-current": e === B.value ? "page" : void 0,
					disabled: s.busy || !y.value || e === B.value,
					onClick: (t) => q(e)
				}, d(e), 11, D)) : (r(), t("span", O, "…"))], 64))), 128)),
				i("span", k, d(B.value) + " / " + d(x.value), 1),
				i("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: s.busy || !y.value || B.value >= x.value,
					onClick: u[1] ||= (e) => q(B.value + 1)
				}, "下一页", 8, A)
			]), i("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: a(J, ["prevent"])
			}, [i("label", null, [
				u[4] ||= n("跳至 ", -1),
				e(i("input", {
					"onUpdate:modelValue": u[2] ||= (e) => W.value = e,
					"aria-label": "跳转页码",
					"aria-invalid": G.value || void 0,
					title: `输入 1 至 ${x.value} 的整数页码`,
					type: "text",
					inputmode: "numeric",
					pattern: "[0-9]*",
					autocomplete: "off",
					disabled: s.busy || !y.value || x.value <= 1,
					onInput: u[3] ||= (e) => G.value = !1
				}, null, 40, j), [[l, W.value]]),
				u[5] ||= n(" 页", -1)
			]), i("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: s.busy || !y.value || x.value <= 1
			}, "跳转", 8, M)], 32)]),
			i("div", N, [i("span", P, [y.value ? (r(), t("span", F, d(V.value.toLocaleString()) + "–" + d(H.value.toLocaleString()) + " / ", 1)) : o("", !0), n("共 " + d(y.value.toLocaleString()) + " 条", 1)]), i("label", I, [u[6] ||= n("每页 ", -1), i("select", {
				"aria-label": "每页条数",
				value: b.value,
				disabled: s.busy,
				onChange: Y
			}, [(r(!0), t(m, null, g(U.value, (e) => (r(), t("option", {
				key: e,
				value: e
			}, d(e) + " 条", 9, R))), 128))], 40, L)])]),
			G.value ? (r(), t("span", z, "请输入整数页码")) : o("", !0)
		])], 8, S));
	}
}), [["__scopeId", "data-v-5637de47"]]);
export { y as a, b as i, x as n, v as r, B as t };
