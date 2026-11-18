import { F as e, M as t, b as n, g as r, h as i, lt as a, ot as o, p as s, v as c } from "./runtime-dom.esm-bundler-BUpOLcfI.js";
import { t as l } from "./_plugin-vue_export-helper-Djzt4Yr7.js";
// src/components/ListCell.vue?vue&type=script&setup=true&lang.ts
var u = ["title"], d = {
	key: 0,
	class: "list-cell-secondary"
}, f = /*#__PURE__*/ l(/* @__PURE__ */ n({
	__name: "ListCell",
	props: {
		text: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(n) {
		return (l, f) => (t(), r("div", {
			class: o(["list-cell", `list-cell--${n.tone}`]),
			title: n.title ?? [n.text, n.secondary].filter(Boolean).join(" · ")
		}, [s("div", { class: o(["list-cell-primary", { "list-cell-single": !!n.secondary }]) }, [e(l.$slots, "default", {}, () => [c(a(n.text), 1)], !0)], 2), n.secondary ? (t(), r("div", d, a(n.secondary), 1)) : i("", !0)], 10, u));
	}
}), [["__scopeId", "data-v-5767b82c"]]);
export { f as t };
