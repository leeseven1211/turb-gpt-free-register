import { $ as e, G as t, I as n, P as r, S as i, V as a, _ as o, a as s, b as c, c as l, ct as u, dt as d, g as f, m as p, p as m, t as h, u as g } from "./_plugin-vue_export-helper-C1AvIlVn.js";
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
}, F = /*#__PURE__*/ h(/* @__PURE__ */ i({
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
	setup(i, { emit: h }) {
		let F = i, I = h, L = m(() => Math.max(0, Math.floor(F.total) || 0)), R = m(() => Math.max(1, Math.floor(F.size) || 1)), z = m(() => Math.max(1, Math.floor(F.pages || Math.ceil(L.value / R.value)) || 1)), B = m(() => Math.min(z.value, Math.max(1, Math.floor(F.page) || 1))), V = m(() => L.value ? Math.min(L.value, (B.value - 1) * R.value + 1) : 0), H = m(() => Math.min(L.value, B.value * R.value)), U = m(() => [.../* @__PURE__ */ new Set([...F.pageSizes, R.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), W = e(String(B.value)), G = e(!1);
		a([B, z], () => {
			W.value = String(B.value), G.value = !1;
		});
		let K = m(() => {
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
		return (e, a) => (r(), o("nav", {
			class: "tc-pagination list-pagination",
			"aria-label": i.label,
			"aria-busy": i.busy
		}, [p("div", v, [
			p("div", y, [p("div", b, [
				p("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: i.busy || !L.value || B.value <= 1,
					onClick: a[0] ||= (e) => q(B.value - 1)
				}, "上一页", 8, x),
				(r(!0), o(g, null, n(K.value, (e) => (r(), o(g, { key: e }, [typeof e == "number" ? (r(), o("button", {
					key: 0,
					type: "button",
					class: u(["list-pagination__button list-pagination__number", { "is-current": e === B.value }]),
					"aria-label": `第 ${e} 页`,
					"aria-current": e === B.value ? "page" : void 0,
					disabled: i.busy || !L.value || e === B.value,
					onClick: (t) => q(e)
				}, d(e), 11, S)) : (r(), o("span", C, "…"))], 64))), 128)),
				p("span", w, d(B.value) + " / " + d(z.value), 1),
				p("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: i.busy || !L.value || B.value >= z.value,
					onClick: a[1] ||= (e) => q(B.value + 1)
				}, "下一页", 8, T)
			]), p("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: l(J, ["prevent"])
			}, [p("label", null, [
				a[4] ||= c("跳至 ", -1),
				t(p("input", {
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
				}, null, 40, E), [[s, W.value]]),
				a[5] ||= c(" 页", -1)
			]), p("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: i.busy || !L.value || z.value <= 1
			}, "跳转", 8, D)], 32)]),
			p("div", O, [p("span", k, [L.value ? (r(), o("span", A, d(V.value.toLocaleString()) + "–" + d(H.value.toLocaleString()) + " / ", 1)) : f("", !0), c("共 " + d(L.value.toLocaleString()) + " 条", 1)]), p("label", j, [a[6] ||= c("每页 ", -1), p("select", {
				"aria-label": "每页条数",
				value: R.value,
				disabled: i.busy,
				onChange: Y
			}, [(r(!0), o(g, null, n(U.value, (e) => (r(), o("option", {
				key: e,
				value: e
			}, d(e) + " 条", 9, N))), 128))], 40, M)])]),
			G.value ? (r(), o("span", P, "请输入整数页码")) : f("", !0)
		])], 8, _));
	}
}), [["__scopeId", "data-v-5637de47"]]);
export { F as t };
