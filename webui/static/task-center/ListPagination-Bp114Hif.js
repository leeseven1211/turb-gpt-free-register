import { J as e, M as t, P as n, U as r, Z as i, b as a, f as o, g as s, h as c, i as l, l as u, lt as d, ot as f, p, s as m, t as h, v as g, z as _ } from "./_plugin-vue_export-helper-BfZgIr4z.js";
// src/shared/useColumnWidths.ts
function v(t) {
	let n = i([...t.defaults]), r = o(() => n.value.reduce((e, t) => e + t, 0));
	try {
		let e = JSON.parse(localStorage.getItem(t.storageKey) || "null");
		if (Array.isArray(e) && e.length === t.defaults.length && e.every((e) => typeof e == "number" && Number.isFinite(e) && e > 0)) {
			if (t.totalStorageKey) {
				let i = Number(localStorage.getItem(t.totalStorageKey)), a = Number.isFinite(i) && i > 0 ? i : r.value, o = e.reduce((e, t) => e + t, 0), s = e.map((e) => e / o * a);
				s.every((e) => Number.isFinite(e) && e > 0) && (n.value = s);
			} else e.every((e) => e >= (t.savedMin ?? t.min) && e <= t.max) && (n.value = e);
		}
	} catch {}
	let a;
	function s() {
		try {
			let e = t.totalStorageKey ? n.value.map((e) => Number((e / r.value * 100).toFixed(t.ratioPrecision ?? 4))) : n.value;
			localStorage.setItem(t.storageKey, JSON.stringify(e)), t.totalStorageKey && localStorage.setItem(t.totalStorageKey, String(Number(r.value.toFixed(t.totalPrecision ?? 0)))), t.onPersist?.();
		} catch {}
	}
	function c(e, r) {
		n.value[e] != null && Number.isFinite(r) && (n.value[e] = Math.max(t.min, Math.min(t.max, n.value[e] + r)), s());
	}
	function l(e, r) {
		if (n.value[e] == null) return;
		a?.();
		let i = n.value[e], o = r.clientX, c = (r) => {
			n.value[e] = Math.max(t.min, Math.min(t.max, i + r.clientX - o));
		}, l = () => {
			a?.(), s();
		};
		a = () => {
			document.removeEventListener("pointermove", c), document.removeEventListener("pointerup", l), document.removeEventListener("pointercancel", l), a = void 0;
		}, document.addEventListener("pointermove", c), document.addEventListener("pointerup", l, { once: !0 }), document.addEventListener("pointercancel", l, { once: !0 });
	}
	function u() {
		a?.(), n.value = [...t.defaults];
		try {
			localStorage.removeItem(t.storageKey), t.totalStorageKey && localStorage.removeItem(t.totalStorageKey), t.onReset?.();
		} catch {}
	}
	return e(() => a?.()), {
		widths: n,
		total: r,
		resize: l,
		resizeWithKeyboard: c,
		resetColumns: u
	};
}
// src/components/ListPagination.vue?vue&type=script&setup=true&lang.ts
var y = ["aria-label", "aria-busy"], b = { class: "list-pagination__layout" }, x = { class: "list-pagination__controls" }, S = { class: "list-pagination__pages" }, C = ["disabled"], w = [
	"aria-label",
	"aria-current",
	"disabled",
	"onClick"
], T = {
	key: 1,
	class: "list-pagination__ellipsis",
	"aria-hidden": "true"
}, E = {
	class: "list-pagination__mobile-page",
	"aria-live": "polite"
}, D = ["disabled"], O = [
	"aria-invalid",
	"title",
	"disabled"
], k = ["disabled"], A = { class: "list-pagination__meta" }, j = {
	class: "list-pagination__range",
	"aria-live": "polite"
}, M = { key: 0 }, N = { class: "list-pagination__size" }, P = ["value", "disabled"], F = ["value"], I = {
	key: 0,
	class: "list-pagination__error",
	role: "alert"
}, L = /*#__PURE__*/ h(/* @__PURE__ */ a({
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
	setup(e, { emit: a }) {
		let h = e, v = a, L = o(() => Math.max(0, Math.floor(h.total) || 0)), R = o(() => Math.max(1, Math.floor(h.size) || 1)), z = o(() => Math.max(1, Math.floor(h.pages || Math.ceil(L.value / R.value)) || 1)), B = o(() => Math.min(z.value, Math.max(1, Math.floor(h.page) || 1))), V = o(() => L.value ? Math.min(L.value, (B.value - 1) * R.value + 1) : 0), H = o(() => Math.min(L.value, B.value * R.value)), U = o(() => [.../* @__PURE__ */ new Set([...h.pageSizes, R.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), W = i(String(B.value)), G = i(!1);
		_([B, z], () => {
			W.value = String(B.value), G.value = !1;
		});
		let K = o(() => {
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
			if (h.busy || !L.value) return;
			let t = Math.min(z.value, Math.max(1, e));
			W.value = String(t), G.value = !1, t !== B.value && v("update:page", t);
		}
		function J() {
			if (h.busy || !L.value) return;
			let e = Number(W.value.trim());
			!/^\d+$/.test(W.value.trim()) || !Number.isSafeInteger(e) ? G.value = !0 : q(e);
		}
		function Y(e) {
			if (h.busy) return;
			let t = Number(e.target.value);
			U.value.includes(t) && t !== R.value && (v("update:page", 1), v("update:size", t));
		}
		return (i, a) => (t(), s("nav", {
			class: "tc-pagination list-pagination",
			"aria-label": e.label,
			"aria-busy": e.busy
		}, [p("div", b, [
			p("div", x, [p("div", S, [
				p("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: e.busy || !L.value || B.value <= 1,
					onClick: a[0] ||= (e) => q(B.value - 1)
				}, "上一页", 8, C),
				(t(!0), s(u, null, n(K.value, (n) => (t(), s(u, { key: n }, [typeof n == "number" ? (t(), s("button", {
					key: 0,
					type: "button",
					class: f(["list-pagination__button list-pagination__number", { "is-current": n === B.value }]),
					"aria-label": `第 ${n} 页`,
					"aria-current": n === B.value ? "page" : void 0,
					disabled: e.busy || !L.value || n === B.value,
					onClick: (e) => q(n)
				}, d(n), 11, w)) : (t(), s("span", T, "…"))], 64))), 128)),
				p("span", E, d(B.value) + " / " + d(z.value), 1),
				p("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: e.busy || !L.value || B.value >= z.value,
					onClick: a[1] ||= (e) => q(B.value + 1)
				}, "下一页", 8, D)
			]), p("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: m(J, ["prevent"])
			}, [p("label", null, [
				a[4] ||= g("跳至 ", -1),
				r(p("input", {
					"onUpdate:modelValue": a[2] ||= (e) => W.value = e,
					"aria-label": "跳转页码",
					"aria-invalid": G.value || void 0,
					title: `输入 1 至 ${z.value} 的整数页码`,
					type: "text",
					inputmode: "numeric",
					pattern: "[0-9]*",
					autocomplete: "off",
					disabled: e.busy || !L.value || z.value <= 1,
					onInput: a[3] ||= (e) => G.value = !1
				}, null, 40, O), [[l, W.value]]),
				a[5] ||= g(" 页", -1)
			]), p("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: e.busy || !L.value || z.value <= 1
			}, "跳转", 8, k)], 32)]),
			p("div", A, [p("span", j, [L.value ? (t(), s("span", M, d(V.value.toLocaleString()) + "–" + d(H.value.toLocaleString()) + " / ", 1)) : c("", !0), g("共 " + d(L.value.toLocaleString()) + " 条", 1)]), p("label", N, [a[6] ||= g("每页 ", -1), p("select", {
				"aria-label": "每页条数",
				value: R.value,
				disabled: e.busy,
				onChange: Y
			}, [(t(!0), s(u, null, n(U.value, (e) => (t(), s("option", {
				key: e,
				value: e
			}, d(e) + " 条", 9, F))), 128))], 40, P)])]),
			G.value ? (t(), s("span", I, "请输入整数页码")) : c("", !0)
		])], 8, y));
	}
}), [["__scopeId", "data-v-5637de47"]]);
export { v as n, L as t };
