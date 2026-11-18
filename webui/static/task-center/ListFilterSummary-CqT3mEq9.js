import { M as e, P as t, b as n, g as r, h as i, l as a, lt as o, p as s } from "./runtime-dom.esm-bundler-BUpOLcfI.js";
import { t as c } from "./_plugin-vue_export-helper-Djzt4Yr7.js";
// src/components/ListFilterSummary.vue?vue&type=script&setup=true&lang.ts
var l = ["aria-label"], u = [
	"aria-label",
	"title",
	"onClick"
], d = /*#__PURE__*/ c(/* @__PURE__ */ n({
	__name: "ListFilterSummary",
	props: {
		items: {},
		label: { default: "已应用筛选" }
	},
	emits: ["remove"],
	setup(n, { emit: c }) {
		let d = c;
		return (c, f) => n.items.length ? (e(), r("div", {
			key: 0,
			class: "list-filter-summary",
			role: "group",
			"aria-label": n.label
		}, [(e(!0), r(a, null, t(n.items, (t) => (e(), r("button", {
			key: t.key,
			type: "button",
			class: "list-filter-chip",
			"aria-label": t.removeLabel,
			title: t.title || t.label,
			onClick: (e) => d("remove", t.key)
		}, [s("span", null, o(t.label), 1), f[0] ||= s("span", { "aria-hidden": "true" }, "×", -1)], 8, u))), 128))], 8, l)) : i("", !0);
	}
}), [["__scopeId", "data-v-9c3f6cac"]]);
export { d as t };
