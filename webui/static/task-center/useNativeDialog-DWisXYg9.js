import { A as e, H as t, M as n, j as r } from "./_plugin-vue_export-helper-BSZsFlS8.js";
// src/shared/useNativeDialog.ts
var i = /* @__PURE__ */ new Set(), a, o, s = !1;
function c() {
	let e = a;
	if (!e || !i.size) return;
	let t = document.body, n = document.documentElement, r = t.classList.contains("modal-open");
	if (s && !r && e.external && (e.external = !1, e.top = t.style.getPropertyValue("top"), e.topPriority = t.style.getPropertyPriority("top"), e.rootOverflow = n.style.getPropertyValue("overflow"), e.rootPriority = n.style.getPropertyPriority("overflow")), s = r, !r) {
		let r = `-${e.scrollY}px`;
		t.style.top !== r && t.style.setProperty("top", r), n.style.overflow !== "hidden" && n.style.setProperty("overflow", "hidden");
	}
	t.style.overflow !== "hidden" && t.style.setProperty("overflow", "hidden"), t.classList.contains("em-native-dialog-lock") || t.classList.add("em-native-dialog-lock");
}
function l(e) {
	if (!i.has(e)) {
		if (!i.size) {
			let e = document.body, t = document.documentElement, n = e.classList.contains("modal-open"), r = n && /^-\d+(?:\.\d+)?px$/.test(e.style.top) ? -parseFloat(e.style.top) : null;
			a = {
				top: e.style.getPropertyValue("top"),
				topPriority: e.style.getPropertyPriority("top"),
				bodyOverflow: e.style.getPropertyValue("overflow"),
				bodyPriority: e.style.getPropertyPriority("overflow"),
				rootOverflow: t.style.getPropertyValue("overflow"),
				rootPriority: t.style.getPropertyPriority("overflow"),
				scrollY: r ?? (window.scrollY || t.scrollTop || 0),
				external: n,
				classExisted: e.classList.contains("em-native-dialog-lock")
			}, n || e.style.setProperty("top", `-${a.scrollY}px`), e.classList.add("em-native-dialog-lock"), e.style.setProperty("overflow", "hidden"), t.style.setProperty("overflow", "hidden"), s = n, o = new MutationObserver(c), o.observe(e, {
				attributes: !0,
				attributeFilter: ["class", "style"]
			}), o.observe(t, {
				attributes: !0,
				attributeFilter: ["style"]
			});
		}
		i.add(e);
	}
}
function u(e) {
	if (i.has(e) && c(), !i.delete(e) || i.size || !a) return;
	o?.disconnect(), o = void 0;
	let t = a;
	a = void 0;
	let n = document.body, r = document.documentElement, s = n.classList.contains("modal-open");
	t.classExisted || n.classList.remove("em-native-dialog-lock"), n.style.setProperty("overflow", t.bodyOverflow, t.bodyPriority), (!s || t.external) && (n.style.setProperty("top", t.top, t.topPriority), r.style.setProperty("overflow", t.rootOverflow, t.rootPriority), !s && !t.external && window.scrollTo(0, t.scrollY));
}
function d(e) {
	if (!e.isConnected || e.closest("[hidden],.hidden,[inert]")) return !1;
	for (let t = e; t; t = t.parentElement) {
		let e = getComputedStyle(t);
		if (e.display === "none" || e.visibility === "hidden") return !1;
	}
	return !0;
}
function f(i, a, o = () => !0) {
	let s = null, c = !1, f;
	async function p() {
		let t = i.value;
		t && !c && (a() && !t.open ? (s = document.activeElement instanceof HTMLElement ? document.activeElement : null, t.showModal(), f = t, l(t), await e(), !c && t.open && t.querySelector("button,input,select,textarea")?.focus()) : a() || (t.open && t.close(), u(t), s && o() && !document.hidden && d(s) && s.focus()));
	}
	t(a, () => void p(), { flush: "post" }), n(() => void p()), r(() => {
		c = !0, f?.close(), f && u(f);
	});
}
export { f as t };
