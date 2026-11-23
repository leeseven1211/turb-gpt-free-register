import { C as e, F as t, Z as n, c as r, et as i, l as a, m as o, v as s } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import "./ListFilterSummary-Bo2VJ9RL.js";
// src/shared/useColumnWidths.ts
function c(e) {
	let t = i([...e.defaults]), r = o(() => t.value.reduce((e, t) => e + t, 0));
	try {
		let n = JSON.parse(localStorage.getItem(e.storageKey) || "null");
		if (Array.isArray(n) && n.length === e.defaults.length && n.every((e) => typeof e == "number" && Number.isFinite(e) && e > 0)) {
			if (e.totalStorageKey) {
				let i = Number(localStorage.getItem(e.totalStorageKey)), a = Number.isFinite(i) && i > 0 ? i : r.value, o = n.reduce((e, t) => e + t, 0), s = n.map((e) => e / o * a);
				s.every((e) => Number.isFinite(e) && e > 0) && (t.value = s);
			} else n.every((t) => t >= (e.savedMin ?? e.min) && t <= e.max) && (t.value = n);
		}
	} catch {}
	let a;
	function s() {
		try {
			let n = e.totalStorageKey ? t.value.map((t) => Number((t / r.value * 100).toFixed(e.ratioPrecision ?? 4))) : t.value;
			localStorage.setItem(e.storageKey, JSON.stringify(n)), e.totalStorageKey && localStorage.setItem(e.totalStorageKey, String(Number(r.value.toFixed(e.totalPrecision ?? 0)))), e.onPersist?.();
		} catch {}
	}
	function c(n, r) {
		t.value[n] != null && Number.isFinite(r) && (t.value[n] = Math.max(e.min, Math.min(e.max, t.value[n] + r)), s());
	}
	function l(n, r) {
		if (t.value[n] == null) return;
		a?.();
		let i = t.value[n], o = r.clientX, c = (r) => {
			t.value[n] = Math.max(e.min, Math.min(e.max, i + r.clientX - o));
		}, l = () => {
			a?.(), s();
		};
		a = () => {
			document.removeEventListener("pointermove", c), document.removeEventListener("pointerup", l), document.removeEventListener("pointercancel", l), a = void 0;
		}, document.addEventListener("pointermove", c), document.addEventListener("pointerup", l, { once: !0 }), document.addEventListener("pointercancel", l, { once: !0 });
	}
	function u() {
		a?.(), t.value = [...e.defaults];
		try {
			localStorage.removeItem(e.storageKey), e.totalStorageKey && localStorage.removeItem(e.totalStorageKey), e.onReset?.();
		} catch {}
	}
	return n(() => a?.()), {
		widths: t,
		total: r,
		resize: l,
		resizeWithKeyboard: c,
		resetColumns: u
	};
}
// src/components/ColumnResizer.vue?vue&type=script&setup=true&lang.ts
var l = ["aria-label"], u = /* @__PURE__ */ e({
	__name: "ColumnResizer",
	props: { label: {} },
	emits: ["start", "nudge"],
	setup(e, { emit: n }) {
		let i = n;
		return (n, o) => (t(), s("button", {
			type: "button",
			class: "ui-table__resize",
			"aria-label": `调整${e.label}列宽，方向键调整`,
			onPointerdown: o[0] ||= a((e) => i("start", e), ["prevent"]),
			onKeydown: [o[1] ||= r(a((e) => i("nudge", -10), ["prevent"]), ["left"]), o[2] ||= r(a((e) => i("nudge", 10), ["prevent"]), ["right"])]
		}, null, 40, l));
	}
});
export { c as n, u as t };
