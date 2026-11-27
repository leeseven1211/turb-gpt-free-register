import { C as e, F as t, R as n, _ as r, ft as i, h as a, lt as o, v as s } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
// src/components/TableState.vue?vue&type=script&setup=true&lang.ts
var c = { class: "ui-table__state-row" }, l = ["colspan"], u = ["role"], d = {
	key: 0,
	class: "ui-spinner",
	"aria-hidden": "true"
}, f = { key: 1 }, p = /* @__PURE__ */ e({
	__name: "TableState",
	props: {
		colspan: {},
		loading: {
			type: Boolean,
			default: !1
		},
		error: {
			type: [String, Boolean],
			default: ""
		},
		title: { default: "没有匹配的记录" },
		text: { default: "" },
		loadingTitle: { default: "正在加载…" },
		loadingText: { default: "" },
		errorTitle: { default: "加载失败" },
		retryLabel: { default: "" }
	},
	emits: ["retry"],
	setup(e, { emit: p }) {
		let m = e, h = p, g = () => !m.loading && !!m.error;
		return (p, m) => (t(), s("tr", c, [a("td", { colspan: e.colspan }, [a("div", {
			class: o(["ui-table-state", { "is-error": g() }]),
			role: g() ? "alert" : "status"
		}, [
			e.loading ? (t(), s("span", d)) : r("", !0),
			a("strong", null, i(e.loading ? e.loadingTitle : g() ? e.errorTitle : e.title), 1),
			(e.loading ? e.loadingText : g() ? typeof e.error == "string" && e.error.trim() : e.text) ? (t(), s("p", f, i(e.loading ? e.loadingText : g() ? e.error : e.text), 1)) : r("", !0),
			g() && e.retryLabel ? (t(), s("button", {
				key: 2,
				type: "button",
				class: "ui-button",
				onClick: m[0] ||= (e) => h("retry")
			}, i(e.retryLabel), 1)) : r("", !0),
			n(p.$slots, "default")
		], 10, u)], 8, l)]));
	}
});
export { p as t };
