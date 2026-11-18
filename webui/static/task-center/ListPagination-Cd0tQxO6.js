import { M as e, P as t, U as n, Z as r, b as i, f as a, g as o, h as s, i as c, l, lt as u, ot as d, p as f, s as p, v as m, z as h } from "./runtime-dom.esm-bundler-BUpOLcfI.js";
import { t as g } from "./_plugin-vue_export-helper-Djzt4Yr7.js";
// src/components/ListPagination.vue?vue&type=script&setup=true&lang.ts
var _ = ["aria-label", "aria-busy"], v = { class: "list-pagination__layout" }, y = { class: "list-pagination__controls" }, b = { class: "list-pagination__pages" }, x = ["disabled"], S = [
	"aria-label",
	"aria-current",
	"disabled",
	"onClick"
], C = {
	key: 1,
	class: "list-pagination__ellipsis",
	"aria-hidden": "true"
}, w = {
	class: "list-pagination__mobile-page",
	"aria-live": "polite"
}, T = ["disabled"], E = [
	"aria-invalid",
	"title",
	"disabled"
], D = ["disabled"], O = { class: "list-pagination__meta" }, k = {
	class: "list-pagination__range",
	"aria-live": "polite"
}, A = { key: 0 }, j = { class: "list-pagination__size" }, M = ["value", "disabled"], N = ["value"], P = {
	key: 0,
	class: "list-pagination__error",
	role: "alert"
}, F = /*#__PURE__*/ g(/* @__PURE__ */ i({
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
	setup(i, { emit: g }) {
		let F = i, I = g, L = a(() => Math.max(0, Math.floor(F.total) || 0)), R = a(() => Math.max(1, Math.floor(F.size) || 1)), z = a(() => Math.max(1, Math.floor(F.pages || Math.ceil(L.value / R.value)) || 1)), B = a(() => Math.min(z.value, Math.max(1, Math.floor(F.page) || 1))), V = a(() => L.value ? Math.min(L.value, (B.value - 1) * R.value + 1) : 0), H = a(() => Math.min(L.value, B.value * R.value)), U = a(() => [.../* @__PURE__ */ new Set([...F.pageSizes, R.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), W = r(String(B.value)), G = r(!1);
		h([B, z], () => {
			W.value = String(B.value), G.value = !1;
		});
		let K = a(() => {
			let e = z.value;
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
			if (F.busy || !L.value) return;
			let t = Math.min(z.value, Math.max(1, e));
			W.value = String(t), G.value = !1, t !== B.value && I("update:page", t);
		}
		function J() {
			if (F.busy || !L.value) return;
			let e = Number(W.value.trim());
			!/^\d+$/.test(W.value.trim()) || !Number.isSafeInteger(e) ? G.value = !0 : q(e);
		}
		function Y(e) {
			if (F.busy) return;
			let t = Number(e.target.value);
			U.value.includes(t) && t !== R.value && (I("update:page", 1), I("update:size", t));
		}
		return (r, a) => (e(), o("nav", {
			class: "tc-pagination list-pagination",
			"aria-label": i.label,
			"aria-busy": i.busy
		}, [f("div", v, [
			f("div", y, [f("div", b, [
				f("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: i.busy || !L.value || B.value <= 1,
					onClick: a[0] ||= (e) => q(B.value - 1)
				}, "上一页", 8, x),
				(e(!0), o(l, null, t(K.value, (t) => (e(), o(l, { key: t }, [typeof t == "number" ? (e(), o("button", {
					key: 0,
					type: "button",
					class: d(["list-pagination__button list-pagination__number", { "is-current": t === B.value }]),
					"aria-label": `第 ${t} 页`,
					"aria-current": t === B.value ? "page" : void 0,
					disabled: i.busy || !L.value || t === B.value,
					onClick: (e) => q(t)
				}, u(t), 11, S)) : (e(), o("span", C, "…"))], 64))), 128)),
				f("span", w, u(B.value) + " / " + u(z.value), 1),
				f("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: i.busy || !L.value || B.value >= z.value,
					onClick: a[1] ||= (e) => q(B.value + 1)
				}, "下一页", 8, T)
			]), f("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: p(J, ["prevent"])
			}, [f("label", null, [
				a[4] ||= m("跳至 ", -1),
				n(f("input", {
					"onUpdate:modelValue": a[2] ||= (e) => W.value = e,
					"aria-label": "跳转页码",
					"aria-invalid": G.value || void 0,
					title: `输入 1 至 ${z.value} 的整数页码`,
					type: "text",
					inputmode: "numeric",
					pattern: "[0-9]*",
					autocomplete: "off",
					disabled: i.busy || !L.value || z.value <= 1,
					onInput: a[3] ||= (e) => G.value = !1
				}, null, 40, E), [[c, W.value]]),
				a[5] ||= m(" 页", -1)
			]), f("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: i.busy || !L.value || z.value <= 1
			}, "跳转", 8, D)], 32)]),
			f("div", O, [f("span", k, [L.value ? (e(), o("span", A, u(V.value.toLocaleString()) + "–" + u(H.value.toLocaleString()) + " / ", 1)) : s("", !0), m("共 " + u(L.value.toLocaleString()) + " 条", 1)]), f("label", j, [a[6] ||= m("每页 ", -1), f("select", {
				"aria-label": "每页条数",
				value: R.value,
				disabled: i.busy,
				onChange: Y
			}, [(e(!0), o(l, null, t(U.value, (t) => (e(), o("option", {
				key: t,
				value: t
			}, u(t) + " 条", 9, N))), 128))], 40, M)])]),
			G.value ? (e(), o("span", P, "请输入整数页码")) : s("", !0)
		])], 8, _));
	}
}), [["__scopeId", "data-v-5637de47"]]);
export { F as t };
