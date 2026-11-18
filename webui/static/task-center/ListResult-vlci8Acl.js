import { F as e, M as t, b as n, g as r, m as i, p as a, y as o } from "./runtime-dom.esm-bundler-BUpOLcfI.js";
import { t as s } from "./ListCell-CsNq9gyC.js";
import { t as c } from "./_plugin-vue_export-helper-Djzt4Yr7.js";
// src/components/ListResult.vue?vue&type=script&setup=true&lang.ts
var l = {
	key: 0,
	class: "list-result"
}, u = ["title"], d = { class: "list-result-details" }, f = /*#__PURE__*/ c(/* @__PURE__ */ n({
	__name: "ListResult",
	props: {
		label: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(n) {
		return (c, f) => c.$slots.details ? (t(), r("details", l, [a("summary", { title: n.title }, [o(s, {
			text: n.label,
			secondary: n.secondary,
			title: n.title,
			tone: n.tone
		}, null, 8, [
			"text",
			"secondary",
			"title",
			"tone"
		])], 8, u), a("div", d, [e(c.$slots, "details", {}, void 0, !0)])])) : (t(), i(s, {
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
