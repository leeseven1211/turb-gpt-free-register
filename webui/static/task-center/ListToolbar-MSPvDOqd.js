import { C as e, F as t, R as n, _ as r, h as i, lt as a, v as o } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import "./ListFilterSummary-Cy87eW0W.js";
// src/components/ListToolbar.vue?vue&type=script&setup=true&lang.ts
var s = { class: "ui-list-toolbar__main" }, c = {
	key: 0,
	class: "ui-list-toolbar__actions"
}, l = /* @__PURE__ */ e({
	__name: "ListToolbar",
	props: { filtered: { type: Boolean } },
	setup(e) {
		return (l, u) => (t(), o("div", { class: a(["ui-list-toolbar", { "is-filtered": e.filtered }]) }, [i("div", s, [n(l.$slots, "default")]), l.$slots.actions ? (t(), o("div", c, [n(l.$slots, "actions")])) : r("", !0)], 2));
	}
});
export { l as t };
