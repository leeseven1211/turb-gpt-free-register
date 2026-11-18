import { L as e, P as t, S as n, _ as r, h as i, m as a, t as o, x as s } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { n as c } from "./ListFilterSummary-NiVwXoAn.js";
// src/components/ListResult.vue?vue&type=script&setup=true&lang.ts
var l = {
	key: 0,
	class: "list-result"
}, u = ["title"], d = { class: "list-result-details" }, f = /*#__PURE__*/ o(/* @__PURE__ */ n({
	__name: "ListResult",
	props: {
		label: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(n) {
		return (o, f) => o.$slots.details ? (t(), r("details", l, [a("summary", { title: n.title }, [s(c, {
			text: n.label,
			secondary: n.secondary,
			title: n.title,
			tone: n.tone
		}, null, 8, [
			"text",
			"secondary",
			"title",
			"tone"
		])], 8, u), a("div", d, [e(o.$slots, "details", {}, void 0, !0)])])) : (t(), i(c, {
			key: 1,
			text: n.label,
			secondary: n.secondary,
			title: n.title,
			tone: n.tone
		}, null, 8, [
			"text",
			"secondary",
			"title",
			"tone"
		]));
	}
}), [["__scopeId", "data-v-ff8fab81"]]);
export { f as t };
