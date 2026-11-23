import { C as e, F as t, R as n, S as r, g as i, h as a, t as o, v as s } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { r as c } from "./ListFilterSummary-mWffSBYB.js";
// src/components/ListResult.vue?vue&type=script&setup=true&lang.ts
var l = {
	key: 0,
	class: "list-result"
}, u = ["title"], d = { class: "list-result-details" }, f = /*#__PURE__*/ o(/* @__PURE__ */ e({
	__name: "ListResult",
	props: {
		label: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(e) {
		return (o, f) => o.$slots.details ? (t(), s("details", l, [a("summary", { title: e.title }, [r(c, {
			text: e.label,
			secondary: e.secondary,
			title: e.title,
			tone: e.tone
		}, null, 8, [
			"text",
			"secondary",
			"title",
			"tone"
		])], 8, u), a("div", d, [n(o.$slots, "details", {}, void 0, !0)])])) : (t(), i(c, {
			key: 1,
			text: e.label,
			secondary: e.secondary,
			title: e.title,
			tone: e.tone
		}, null, 8, [
			"text",
			"secondary",
			"title",
			"tone"
		]));
	}
}), [["__scopeId", "data-v-ff8fab81"]]);
export { f as t };
