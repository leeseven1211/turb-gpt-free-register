import { C as e, F as t, H as n, K as r, L as i, _ as a, d as o, et as s, ft as c, h as l, l as u, lt as d, m as f, o as p, t as m, v as h, x as g } from "./_plugin-vue_export-helper-BSZsFlS8.js";
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
}, F = /*#__PURE__*/ m(/* @__PURE__ */ e({
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
	setup(e, { emit: m }) {
		let F = e, I = m, L = f(() => Math.max(0, Math.floor(F.total) || 0)), R = f(() => Math.max(1, Math.floor(F.size) || 1)), z = f(() => Math.max(1, Math.floor(F.pages || Math.ceil(L.value / R.value)) || 1)), B = f(() => Math.min(z.value, Math.max(1, Math.floor(F.page) || 1))), V = f(() => L.value ? Math.min(L.value, (B.value - 1) * R.value + 1) : 0), H = f(() => Math.min(L.value, B.value * R.value)), U = f(() => [.../* @__PURE__ */ new Set([...F.pageSizes, R.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), W = s(String(B.value)), G = s(!1);
		n([B, z], () => {
			W.value = String(B.value), G.value = !1;
		});
		let K = f(() => {
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
		return (n, s) => (t(), h("nav", {
			class: "tc-pagination list-pagination",
			"aria-label": e.label,
			"aria-busy": e.busy
		}, [l("div", v, [
			l("div", y, [l("div", b, [
				l("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: e.busy || !L.value || B.value <= 1,
					onClick: s[0] ||= (e) => q(B.value - 1)
				}, "上一页", 8, x),
				(t(!0), h(o, null, i(K.value, (n) => (t(), h(o, { key: n }, [typeof n == "number" ? (t(), h("button", {
					key: 0,
					type: "button",
					class: d(["list-pagination__button list-pagination__number", { "is-current": n === B.value }]),
					"aria-label": `第 ${n} 页`,
					"aria-current": n === B.value ? "page" : void 0,
					disabled: e.busy || !L.value || n === B.value,
					onClick: (e) => q(n)
				}, c(n), 11, S)) : (t(), h("span", C, "…"))], 64))), 128)),
				l("span", w, c(B.value) + " / " + c(z.value), 1),
				l("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: e.busy || !L.value || B.value >= z.value,
					onClick: s[1] ||= (e) => q(B.value + 1)
				}, "下一页", 8, T)
			]), l("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: u(J, ["prevent"])
			}, [l("label", null, [
				s[4] ||= g("跳至 ", -1),
				r(l("input", {
					"onUpdate:modelValue": s[2] ||= (e) => W.value = e,
					"aria-label": "跳转页码",
					"aria-invalid": G.value || void 0,
					title: `输入 1 至 ${z.value} 的整数页码`,
					type: "text",
					inputmode: "numeric",
					pattern: "[0-9]*",
					autocomplete: "off",
					disabled: e.busy || !L.value || z.value <= 1,
					onInput: s[3] ||= (e) => G.value = !1
				}, null, 40, E), [[p, W.value]]),
				s[5] ||= g(" 页", -1)
			]), l("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: e.busy || !L.value || z.value <= 1
			}, "跳转", 8, D)], 32)]),
			l("div", O, [l("span", k, [L.value ? (t(), h("span", A, c(V.value.toLocaleString()) + "–" + c(H.value.toLocaleString()) + " / ", 1)) : a("", !0), g("共 " + c(L.value.toLocaleString()) + " 条", 1)]), l("label", j, [s[6] ||= g("每页 ", -1), l("select", {
				"aria-label": "每页条数",
				value: R.value,
				disabled: e.busy,
				onChange: Y
			}, [(t(!0), h(o, null, i(U.value, (e) => (t(), h("option", {
				key: e,
				value: e
			}, c(e) + " 条", 9, N))), 128))], 40, M)])]),
			G.value ? (t(), h("span", P, "请输入整数页码")) : a("", !0)
		])], 8, _));
	}
}), [["__scopeId", "data-v-5637de47"]]);
export { F as t };
