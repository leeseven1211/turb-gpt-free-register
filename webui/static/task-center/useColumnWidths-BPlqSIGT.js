import { Z as e, et as t, m as n } from "./_plugin-vue_export-helper-B9RV9BFd.js";
// src/shared/useColumnWidths.ts
function r(r) {
	let i = t([...r.defaults]), a = n(() => i.value.reduce((e, t) => e + t, 0));
	try {
		let e = JSON.parse(localStorage.getItem(r.storageKey) || "null");
		if (Array.isArray(e) && e.length === r.defaults.length && e.every((e) => typeof e == "number" && Number.isFinite(e) && e > 0)) {
			if (r.totalStorageKey) {
				let t = Number(localStorage.getItem(r.totalStorageKey)), n = Number.isFinite(t) && t > 0 ? t : a.value, o = e.reduce((e, t) => e + t, 0), s = e.map((e) => e / o * n);
				s.every((e) => Number.isFinite(e) && e > 0) && (i.value = s);
			} else e.every((e) => e >= (r.savedMin ?? r.min) && e <= r.max) && (i.value = e);
		}
	} catch {}
	let o;
	function s() {
		try {
			let e = r.totalStorageKey ? i.value.map((e) => Number((e / a.value * 100).toFixed(r.ratioPrecision ?? 4))) : i.value;
			localStorage.setItem(r.storageKey, JSON.stringify(e)), r.totalStorageKey && localStorage.setItem(r.totalStorageKey, String(Number(a.value.toFixed(r.totalPrecision ?? 0)))), r.onPersist?.();
		} catch {}
	}
	function c(e, t) {
		i.value[e] != null && Number.isFinite(t) && (i.value[e] = Math.max(r.min, Math.min(r.max, i.value[e] + t)), s());
	}
	function l(e, t) {
		if (i.value[e] == null) return;
		o?.();
		let n = i.value[e], a = t.clientX, c = (t) => {
			i.value[e] = Math.max(r.min, Math.min(r.max, n + t.clientX - a));
		}, l = () => {
			o?.(), s();
		};
		o = () => {
			document.removeEventListener("pointermove", c), document.removeEventListener("pointerup", l), document.removeEventListener("pointercancel", l), o = void 0;
		}, document.addEventListener("pointermove", c), document.addEventListener("pointerup", l, { once: !0 }), document.addEventListener("pointercancel", l, { once: !0 });
	}
	function u() {
		o?.(), i.value = [...r.defaults];
		try {
			localStorage.removeItem(r.storageKey), r.totalStorageKey && localStorage.removeItem(r.totalStorageKey), r.onReset?.();
		} catch {}
	}
	return e(() => o?.()), {
		widths: i,
		total: a,
		resize: l,
		resizeWithKeyboard: c,
		resetColumns: u
	};
}
export { r as t };
