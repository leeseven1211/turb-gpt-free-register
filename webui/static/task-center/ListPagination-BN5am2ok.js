import { H as e, N as t, R as n, X as r, _ as i, at as a, ct as o, f as s, g as c, h as l, i as u, j as d, l as f, p, q as m, s as h, t as g, y as _ } from "./_plugin-vue_export-helper-acNQneR4.js";
// src/shared/useColumnWidths.ts
function v(e) {
	let t = r([...e.defaults]), n = s(() => t.value.reduce((e, t) => e + t, 0));
	try {
		let r = JSON.parse(localStorage.getItem(e.storageKey) || "null");
		if (Array.isArray(r) && r.length === e.defaults.length && r.every((e) => typeof e == "number" && Number.isFinite(e) && e > 0)) {
			if (e.totalStorageKey) {
				let i = Number(localStorage.getItem(e.totalStorageKey)), a = Number.isFinite(i) && i > 0 ? i : n.value, o = r.reduce((e, t) => e + t, 0), s = r.map((e) => e / o * a);
				s.every((e) => Number.isFinite(e) && e > 0) && (t.value = s);
			} else r.every((t) => t >= (e.savedMin ?? e.min) && t <= e.max) && (t.value = r);
		}
	} catch {}
	let i;
	function a() {
		try {
			let r = e.totalStorageKey ? t.value.map((t) => Number((t / n.value * 100).toFixed(e.ratioPrecision ?? 4))) : t.value;
			localStorage.setItem(e.storageKey, JSON.stringify(r)), e.totalStorageKey && localStorage.setItem(e.totalStorageKey, String(Number(n.value.toFixed(e.totalPrecision ?? 0)))), e.onPersist?.();
		} catch {}
	}
	function o(n, r) {
		t.value[n] != null && Number.isFinite(r) && (t.value[n] = Math.max(e.min, Math.min(e.max, t.value[n] + r)), a());
	}
	function c(n, r) {
		if (t.value[n] == null) return;
		i?.();
		let o = t.value[n], s = r.clientX, c = (r) => {
			t.value[n] = Math.max(e.min, Math.min(e.max, o + r.clientX - s));
		}, l = () => {
			i?.(), a();
		};
		i = () => {
			document.removeEventListener("pointermove", c), document.removeEventListener("pointerup", l), document.removeEventListener("pointercancel", l), i = void 0;
		}, document.addEventListener("pointermove", c), document.addEventListener("pointerup", l, { once: !0 }), document.addEventListener("pointercancel", l, { once: !0 });
	}
	function l() {
		i?.(), t.value = [...e.defaults];
		try {
			localStorage.removeItem(e.storageKey), e.totalStorageKey && localStorage.removeItem(e.totalStorageKey), e.onReset?.();
		} catch {}
	}
	return m(() => i?.()), {
		widths: t,
		total: n,
		resize: c,
		resizeWithKeyboard: o,
		resetColumns: l
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
}, L = /*#__PURE__*/ g(/* @__PURE__ */ _({
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
	setup(m, { emit: g }) {
		let _ = m, v = g, L = s(() => Math.max(0, Math.floor(_.total) || 0)), R = s(() => Math.max(1, Math.floor(_.size) || 1)), z = s(() => Math.max(1, Math.floor(_.pages || Math.ceil(L.value / R.value)) || 1)), B = s(() => Math.min(z.value, Math.max(1, Math.floor(_.page) || 1))), V = s(() => L.value ? Math.min(L.value, (B.value - 1) * R.value + 1) : 0), H = s(() => Math.min(L.value, B.value * R.value)), U = s(() => [.../* @__PURE__ */ new Set([..._.pageSizes, R.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), W = r(String(B.value)), G = r(!1);
		n([B, z], () => {
			W.value = String(B.value), G.value = !1;
		});
		let K = s(() => {
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
			if (_.busy || !L.value) return;
			let t = Math.min(z.value, Math.max(1, e));
			W.value = String(t), G.value = !1, t !== B.value && v("update:page", t);
		}
		function J() {
			if (_.busy || !L.value) return;
			let e = Number(W.value.trim());
			!/^\d+$/.test(W.value.trim()) || !Number.isSafeInteger(e) ? G.value = !0 : q(e);
		}
		function Y(e) {
			if (_.busy) return;
			let t = Number(e.target.value);
			U.value.includes(t) && t !== R.value && (v("update:page", 1), v("update:size", t));
		}
		return (n, r) => (d(), c("nav", {
			class: "tc-pagination list-pagination",
			"aria-label": m.label,
			"aria-busy": m.busy
		}, [p("div", b, [
			p("div", x, [p("div", S, [
				p("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: m.busy || !L.value || B.value <= 1,
					onClick: r[0] ||= (e) => q(B.value - 1)
				}, "上一页", 8, C),
				(d(!0), c(f, null, t(K.value, (e) => (d(), c(f, { key: e }, [typeof e == "number" ? (d(), c("button", {
					key: 0,
					type: "button",
					class: a(["list-pagination__button list-pagination__number", { "is-current": e === B.value }]),
					"aria-label": `第 ${e} 页`,
					"aria-current": e === B.value ? "page" : void 0,
					disabled: m.busy || !L.value || e === B.value,
					onClick: (t) => q(e)
				}, o(e), 11, w)) : (d(), c("span", T, "…"))], 64))), 128)),
				p("span", E, o(B.value) + " / " + o(z.value), 1),
				p("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: m.busy || !L.value || B.value >= z.value,
					onClick: r[1] ||= (e) => q(B.value + 1)
				}, "下一页", 8, D)
			]), p("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: h(J, ["prevent"])
			}, [p("label", null, [
				r[4] ||= i("跳至 ", -1),
				e(p("input", {
					"onUpdate:modelValue": r[2] ||= (e) => W.value = e,
					"aria-label": "跳转页码",
					"aria-invalid": G.value || void 0,
					title: `输入 1 至 ${z.value} 的整数页码`,
					type: "text",
					inputmode: "numeric",
					pattern: "[0-9]*",
					autocomplete: "off",
					disabled: m.busy || !L.value || z.value <= 1,
					onInput: r[3] ||= (e) => G.value = !1
				}, null, 40, O), [[u, W.value]]),
				r[5] ||= i(" 页", -1)
			]), p("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: m.busy || !L.value || z.value <= 1
			}, "跳转", 8, k)], 32)]),
			p("div", A, [p("span", j, [L.value ? (d(), c("span", M, o(V.value.toLocaleString()) + "–" + o(H.value.toLocaleString()) + " / ", 1)) : l("", !0), i("共 " + o(L.value.toLocaleString()) + " 条", 1)]), p("label", N, [r[6] ||= i("每页 ", -1), p("select", {
				"aria-label": "每页条数",
				value: R.value,
				disabled: m.busy,
				onChange: Y
			}, [(d(!0), c(f, null, t(U.value, (e) => (d(), c("option", {
				key: e,
				value: e
			}, o(e) + " 条", 9, F))), 128))], 40, P)])]),
			G.value ? (d(), c("span", I, "请输入整数页码")) : l("", !0)
		])], 8, y));
	}
}), [["__scopeId", "data-v-5637de47"]]);
export { v as n, L as t };
