import { $ as e, A as t, B as n, C as r, D as i, E as a, F as o, G as s, H as c, J as l, K as u, L as d, M as f, N as p, O as m, Q as h, R as g, S as _, T as v, V as y, W as b, Y as x, Z as S, at as C, b as w, c as T, ct as E, d as ee, et as te, f as D, g as ne, h as O, it as k, j as re, k as ie, l as ae, lt as oe, m as A, nt as j, ot as se, p as M, q as ce, rt as le, s as ue, st as de, tt as fe, u as pe, ut as me, w as he, x as N, y as P, z as F } from "./runtime-dom.esm-bundler-BUpOLcfI.js";
import { t as ge } from "./_plugin-vue_export-helper-Djzt4Yr7.js";
// node_modules/reka-ui/dist/shared/createContext.js
function _e(e, t) {
	let n = typeof e == "string" && !t ? `${e}Context` : t, r = Symbol(n);
	return [(t) => {
		let n = he(r, t);
		if (n || n === null) return n;
		throw Error(`Injection \`${r.toString()}\` not found. Component must be used within ${Array.isArray(e) ? `one of the following components: ${e.join(", ")}` : `\`${e}\``}`);
	}, (e) => (p(r, e), e)];
}
// node_modules/reka-ui/dist/shared/getActiveElement.js
function I() {
	let e = document.activeElement;
	if (e == null) return null;
	for (; e != null && e.shadowRoot != null && e.shadowRoot.activeElement != null;) e = e.shadowRoot.activeElement;
	return e;
}
// node_modules/reka-ui/dist/shared/handleAndDispatchCustomEvent.js
function ve(e, t, n) {
	let r = n.originalEvent.target, i = new CustomEvent(e, {
		bubbles: !1,
		cancelable: !0,
		detail: n
	});
	t && r.addEventListener(e, t, { once: !0 }), r.dispatchEvent(i);
}
// node_modules/@vueuse/shared/dist/index.js
function ye(e, t) {
	return u() ? (l(e, t), !0) : !1;
}
function be(e) {
	let t = !1, n, r = s(!0);
	return ((...i) => (t ||= (n = r.run(() => e(...i)), !0), n));
}
var L = typeof window < "u" && typeof document < "u";
typeof WorkerGlobalScope < "u" && globalThis instanceof WorkerGlobalScope;
var xe = (e) => e !== void 0, Se = Object.prototype.toString, Ce = (e) => Se.call(e) === "[object Object]", we = /* #__PURE__ */ Te();
function Te() {
	var e, t;
	return L && !!((e = window) != null && (e = e.navigator) != null && e.userAgent) && (/iP(?:ad|hone|od)/.test(window.navigator.userAgent) || ((t = window) == null || (t = t.navigator) == null ? void 0 : t.maxTouchPoints) > 2 && /iPad|Macintosh/.test(window?.navigator.userAgent));
}
function Ee(e) {
	return Array.isArray(e) ? e : [e];
}
function De(e) {
	return e || N();
}
function Oe(e) {
	if (!L) return e;
	let t = 0, n, r, i = () => {
		--t, r && t <= 0 && (r.stop(), n = void 0, r = void 0);
	};
	return ((...a) => (t += 1, r || (r = s(!0), n = r.run(() => e(...a))), ye(i), n));
}
function ke(e) {
	return ce(e) ? x(new Proxy({}, {
		get(t, n, r) {
			return k(Reflect.get(e.value, n, r));
		},
		set(t, n, r) {
			return ce(e.value[n]) && !ce(r) ? e.value[n].value = r : e.value[n] = r, !0;
		},
		deleteProperty(t, n) {
			return Reflect.deleteProperty(e.value, n);
		},
		has(t, n) {
			return Reflect.has(e.value, n);
		},
		ownKeys() {
			return Object.keys(e.value);
		},
		getOwnPropertyDescriptor() {
			return {
				enumerable: !0,
				configurable: !0
			};
		}
	})) : x(e);
}
function Ae(e) {
	return ke(D(e));
}
function je(e, ...t) {
	let n = t.flat(), r = n[0];
	return Ae(() => Object.fromEntries(typeof r == "function" ? Object.entries(fe(e)).filter(([e, t]) => !r(j(t), e)) : Object.entries(fe(e)).filter((e) => !n.includes(e[0]))));
}
function Me(e, t) {
	De(t) && m(e, t);
}
function Ne(e, t, n) {
	return F(e, t, {
		...n,
		immediate: !0
	});
}
// node_modules/@vueuse/core/dist/index.js
var Pe = L ? window : void 0;
L && window.document, L && window.navigator, L && window.location;
function Fe(e) {
	let t = j(e);
	return t?.$el ?? t;
}
function Ie(...e) {
	let t = (e, t, n, r) => (e.addEventListener(t, n, r), () => e.removeEventListener(t, n, r)), n = D(() => {
		let t = Ee(j(e[0])).filter((e) => e != null);
		return t.every((e) => typeof e != "string") ? t : void 0;
	});
	return Ne(() => [
		n.value?.map((e) => Fe(e)) ?? [Pe].filter((e) => e != null),
		Ee(j(n.value ? e[1] : e[0])),
		Ee(k(n.value ? e[2] : e[1])),
		j(n.value ? e[3] : e[2])
	], ([e, n, r, i], a, o) => {
		if (!e?.length || !n?.length || !r?.length) return;
		let s = Ce(i) ? { ...i } : i, c = e.flatMap((e) => n.flatMap((n) => r.map((r) => t(e, n, r, s))));
		o(() => {
			c.forEach((e) => e());
		});
	}, { flush: "post" });
}
function Le() {
	let t = e(!1), n = N();
	return n && ie(() => {
		t.value = !0;
	}, n), t;
}
function Re(e) {
	return typeof e == "function" ? e : typeof e == "string" ? (t) => t.key === e : Array.isArray(e) ? (t) => e.includes(t.key) : () => !0;
}
function ze(...e) {
	let t, n, r = {};
	e.length === 3 ? (t = e[0], n = e[1], r = e[2]) : e.length === 2 ? typeof e[1] == "object" ? (t = !0, n = e[0], r = e[1]) : (t = e[0], n = e[1]) : (t = !0, n = e[0]);
	let { target: i = Pe, eventName: a = "keydown", passive: o = !1, dedupe: s = !1 } = r, c = Re(t);
	return Ie(i, a, (e) => {
		e.repeat && j(s) || c(e) && n(e);
	}, o);
}
function Be(e) {
	return JSON.parse(JSON.stringify(e));
}
function Ve(e, t, n, r = {}) {
	var a, o;
	let { clone: s = !1, passive: c = !1, eventName: l, deep: u = !1, defaultValue: d, shouldEmit: f } = r, p = N(), m = n || p?.emit || (p == null || (a = p.$emit) == null ? void 0 : a.bind(p)) || (p == null || (o = p.proxy) == null || (o = o.$emit) == null ? void 0 : o.bind(p?.proxy)), h = l;
	t ||= "modelValue", h ||= `update:${t.toString()}`;
	let g = (e) => s ? typeof s == "function" ? s(e) : Be(e) : e, _ = () => xe(e[t]) ? g(e[t]) : d, v = (e) => {
		f ? f(e) && m(h, e) : m(h, e);
	};
	if (c) {
		let n = S(_()), r = !1;
		return F(() => e[t], (e) => {
			r || (r = !0, n.value = g(e), i(() => r = !1));
		}), F(n, (n) => {
			!r && (n !== e[t] || u) && v(n);
		}, { deep: u }), n;
	}
	return D({
		get() {
			return _();
		},
		set(e) {
			v(e);
		}
	});
}
// node_modules/reka-ui/dist/shared/renderSlotFragments.js
function He(e) {
	return e ? e.flatMap((e) => e.type === ae ? He(e.children) : [e]) : [];
}
// node_modules/reka-ui/dist/ConfigProvider/ConfigProvider.js
var [Ue, We] = /*#__PURE__*/ _e("ConfigProvider"), Ge = /* @__PURE__ */ new WeakMap();
function Ke(e, t) {
	let n = Ge.get(e);
	n || (n = {
		owners: /* @__PURE__ */ new Set(),
		original: e.body.style.pointerEvents
	}, Ge.set(e, n)), n.owners.add(t), e.body.style.pointerEvents = "none";
}
function qe(e, t) {
	let n = Ge.get(e);
	n?.owners.delete(t) && n.owners.size === 0 && (Ge.delete(e), e.body.style.pointerEvents = n.original);
}
// node_modules/defu/dist/defu.mjs
function Je(e) {
	if (typeof e != "object" || !e) return !1;
	let t = Object.getPrototypeOf(e);
	return t !== null && t !== Object.prototype && Object.getPrototypeOf(t) !== null || Symbol.iterator in e ? !1 : Symbol.toStringTag in e ? Object.prototype.toString.call(e) === "[object Module]" : !0;
}
function Ye(e, t, n = ".", r) {
	if (!Je(t)) return Ye(e, {}, n, r);
	let i = { ...t };
	for (let t of Object.keys(e)) {
		if (t === "__proto__" || t === "constructor") continue;
		let a = e[t];
		a != null && (r && r(i, t, a, n) || (i[t] = Array.isArray(a) && Array.isArray(i[t]) ? [...a, ...i[t]] : Je(a) && Je(i[t]) ? Ye(a, i[t], (n ? `${n}.` : "") + t.toString(), r) : a));
	}
	return i;
}
function Xe(e) {
	return (...t) => t.reduce((t, n) => Ye(t, n, "", e), {});
}
var Ze = Xe(), Qe = Symbol("useBodyScrollLock"), $e = Oe(() => {
	let e = S(/* @__PURE__ */ new Map()), t = S(), n = D(() => {
		for (let t of e.value.values()) if (t) return !0;
		return !1;
	}), r = Ue({ scrollBody: S(!0) }), a = null, o = () => {
		document.body.style.paddingRight = "", document.body.style.marginRight = "", qe(document, Qe), document.documentElement.style.removeProperty("--scrollbar-width"), document.body.style.overflow = t.value ?? "", we && a?.(), t.value = void 0;
	};
	return F(n, (e, s) => {
		if (!L) return;
		if (!e) {
			s && o();
			return;
		}
		t.value === void 0 && (t.value = document.body.style.overflow);
		let c = window.innerWidth - document.documentElement.clientWidth, l = {
			padding: c,
			margin: 0
		}, u = r.scrollBody?.value ? typeof r.scrollBody.value == "object" ? Ze({
			padding: r.scrollBody.value.padding === !0 ? c : r.scrollBody.value.padding,
			margin: r.scrollBody.value.margin === !0 ? c : r.scrollBody.value.margin
		}, l) : l : {
			padding: 0,
			margin: 0
		};
		c > 0 && (document.body.style.paddingRight = typeof u.padding == "number" ? `${u.padding}px` : String(u.padding), document.body.style.marginRight = typeof u.margin == "number" ? `${u.margin}px` : String(u.margin), document.documentElement.style.setProperty("--scrollbar-width", `${c}px`), document.body.style.overflow = "hidden"), we && (a = Ie(document, "touchmove", (e) => nt(e), { passive: !1 })), i(() => {
			n.value && (Ke(document, Qe), document.body.style.overflow = "hidden");
		});
	}, {
		immediate: !0,
		flush: "sync"
	}), e;
});
function et(e) {
	let t = Math.random().toString(36).substring(2, 7), n = $e();
	n.value.set(t, e ?? !1);
	let r = D({
		get: () => n.value.get(t) ?? !1,
		set: (e) => n.value.set(t, e)
	});
	return Me(() => {
		n.value.delete(t);
	}), r;
}
function tt(e) {
	let t = window.getComputedStyle(e);
	if (t.overflowX === "scroll" || t.overflowY === "scroll" || t.overflowX === "auto" && e.clientWidth < e.scrollWidth || t.overflowY === "auto" && e.clientHeight < e.scrollHeight) return !0;
	{
		let t = e.parentNode;
		return !(t instanceof Element) || t.tagName === "BODY" ? !1 : tt(t);
	}
}
function nt(e) {
	let t = e || window.event, n = t.target;
	return n instanceof Element && tt(n) ? !1 : t.touches.length > 1 || (t.preventDefault && t.cancelable && t.preventDefault(), !1);
}
// node_modules/reka-ui/dist/shared/useDirection.js
function rt(e) {
	let t = Ue({ dir: S("ltr") });
	return D(() => e?.value || t.dir?.value || "ltr");
}
// node_modules/reka-ui/dist/shared/useEmitAsProps.js
function it(e) {
	let t = N(), n = t?.type.emits, r = {};
	return n?.length || console.warn(`No emitted event found. Please check component: ${t?.type.__name}`), n?.forEach((t) => {
		r[me(C(t))] = (...n) => e(t, ...n);
	}), r;
}
// node_modules/reka-ui/dist/shared/useFocusGuards.js
var at = 0;
function ot() {
	n((e) => {
		if (!L) return;
		let t = document.querySelectorAll("[data-reka-focus-guard]");
		document.body.insertAdjacentElement("afterbegin", t[0] ?? st()), document.body.insertAdjacentElement("beforeend", t[1] ?? st()), at++, e(() => {
			at === 1 && document.querySelectorAll("[data-reka-focus-guard]").forEach((e) => e.remove()), at--;
		});
	});
}
function st() {
	let e = document.createElement("span");
	return e.setAttribute("data-reka-focus-guard", ""), e.tabIndex = 0, e.style.outline = "none", e.style.opacity = "0", e.style.position = "fixed", e.style.pointerEvents = "none", e;
}
// node_modules/reka-ui/dist/shared/useForwardExpose.js
function R() {
	let e = N(), t = S(), n = D(() => r());
	re(() => {
		n.value !== r() && le(t);
	});
	function r() {
		return t.value && "$el" in t.value && ["#text", "#comment"].includes(t.value.$el.nodeName) ? t.value.$el.nextElementSibling : Fe(t);
	}
	let i = Object.assign({}, e.exposed), a = {};
	for (let t in e.props) Object.defineProperty(a, t, {
		enumerable: !0,
		configurable: !0,
		get: () => e.props[t]
	});
	if (Object.keys(i).length > 0) for (let e in i) Object.defineProperty(a, e, {
		enumerable: !0,
		configurable: !0,
		get: () => i[e]
	});
	Object.defineProperty(a, "$el", {
		enumerable: !0,
		configurable: !0,
		get: () => e.vnode.el
	}), e.exposed = a;
	function o(n) {
		if (t.value = n, n && (Object.defineProperty(a, "$el", {
			enumerable: !0,
			configurable: !0,
			get: () => n instanceof Element ? n : n.$el
		}), !(n instanceof Element) && !Object.hasOwn(n, "$el"))) {
			let t = n.$.exposed, r = Object.assign({}, a);
			for (let e in t) Object.defineProperty(r, e, {
				enumerable: !0,
				configurable: !0,
				get: () => t[e]
			});
			e.exposed = r;
		}
	}
	return {
		forwardRef: o,
		currentRef: t,
		currentElement: n
	};
}
// node_modules/reka-ui/dist/shared/useForwardProps.js
function ct(e) {
	let t = N(), n = Object.keys(t?.type.props ?? {}).reduce((e, n) => {
		let r = (t?.type.props[n]).default;
		return r !== void 0 && (e[n] = r), e;
	}, {}), r = te(e);
	return D(() => {
		let e = {}, i = t?.vnode.props ?? {};
		return Object.keys(i).forEach((t) => {
			e[C(t)] = i[t];
		}), Object.keys({
			...n,
			...e
		}).reduce((e, t) => (r.value[t] !== void 0 && (e[t] = r.value[t]), e), {});
	});
}
// node_modules/reka-ui/dist/shared/useForwardPropsEmits.js
function lt(e, t) {
	let n = ct(e), r = t ? it(t) : {};
	return D(() => ({
		...n.value,
		...r
	}));
}
// node_modules/aria-hidden/dist/es2015/index.js
var ut = function(e) {
	return typeof document > "u" ? null : (Array.isArray(e) ? e[0] : e).ownerDocument.body;
}, dt = /* @__PURE__ */ new WeakMap(), ft = /* @__PURE__ */ new WeakMap(), pt = {}, mt = 0, ht = function(e) {
	return e && (e.host || ht(e.parentNode));
}, gt = function(e, t) {
	return t.map(function(t) {
		if (e.contains(t)) return t;
		var n = ht(t);
		return n && e.contains(n) ? n : (console.error("aria-hidden", t, "in not contained inside", e, ". Doing nothing"), null);
	}).filter(function(e) {
		return !!e;
	});
}, _t = function(e, t, n, r) {
	var i = gt(t, Array.isArray(e) ? e : [e]);
	pt[n] || (pt[n] = /* @__PURE__ */ new WeakMap());
	var a = pt[n], o = [], s = /* @__PURE__ */ new Set(), c = new Set(i), l = function(e) {
		e && !s.has(e) && (s.add(e), l(e.parentNode));
	};
	i.forEach(l);
	var u = function(e) {
		e && !c.has(e) && Array.prototype.forEach.call(e.children, function(e) {
			if (s.has(e)) u(e);
			else try {
				var t = e.getAttribute(r), i = t !== null && t !== "false", c = (dt.get(e) || 0) + 1, l = (a.get(e) || 0) + 1;
				dt.set(e, c), a.set(e, l), o.push(e), c === 1 && i && ft.set(e, !0), l === 1 && e.setAttribute(n, "true"), i || e.setAttribute(r, "true");
			} catch (t) {
				console.error("aria-hidden: cannot operate on ", e, t);
			}
		});
	};
	return u(t), s.clear(), mt++, function() {
		o.forEach(function(e) {
			var t = dt.get(e) - 1, i = a.get(e) - 1;
			dt.set(e, t), a.set(e, i), t || (ft.has(e) || e.removeAttribute(r), ft.delete(e)), i || e.removeAttribute(n);
		}), mt--, mt || (dt = /* @__PURE__ */ new WeakMap(), dt = /* @__PURE__ */ new WeakMap(), ft = /* @__PURE__ */ new WeakMap(), pt = {});
	};
}, vt = function(e, t, n) {
	n === void 0 && (n = "data-aria-hidden");
	var r = Array.from(Array.isArray(e) ? e : [e]), i = t || ut(e);
	return i ? (r.push.apply(r, Array.from(i.querySelectorAll("[aria-live], script"))), _t(r, i, n, "aria-hidden")) : function() {
		return null;
	};
};
// node_modules/reka-ui/dist/shared/useHideOthers.js
function yt(e) {
	let n;
	F(() => Fe(e), (e) => {
		let t = !1;
		try {
			t = !!e?.closest("[popover]:not(:popover-open)");
		} catch {}
		e && !t ? n = vt(e) : n && n();
	}), t(() => {
		n && n();
	});
}
function bt(e, t = "reka") {
	if (e) return e;
	let n, r = Ue({ useId: void 0 });
	return n = r.useId ? r.useId() : g?.(), t ? `${t}-${n}` : n;
}
// node_modules/reka-ui/dist/shared/useSize.js
function xt(e) {
	let n = S(), r = D(() => n.value?.width ?? 0), i = D(() => n.value?.height ?? 0), a;
	return ie(() => {
		let t = Fe(e);
		t ? (n.value = {
			width: t.offsetWidth,
			height: t.offsetHeight
		}, a = new ResizeObserver((e) => {
			if (!Array.isArray(e) || !e.length) return;
			let r = e[0], i, a;
			if ("borderBoxSize" in r) {
				let e = r.borderBoxSize, t = Array.isArray(e) ? e[0] : e;
				i = t.inlineSize, a = t.blockSize;
			} else i = t.offsetWidth, a = t.offsetHeight;
			n.value = {
				width: i,
				height: a
			};
		}), a.observe(t, { box: "border-box" })) : n.value = void 0;
	}), t(() => {
		a?.disconnect(), a = void 0;
	}), {
		width: r,
		height: i
	};
}
// node_modules/reka-ui/dist/shared/useStateMachine.js
function St(e, t) {
	let n = S(e);
	function r(e) {
		return t[n.value][e] ?? n.value;
	}
	return {
		state: n,
		dispatch: (e) => {
			n.value = r(e);
		}
	};
}
// node_modules/reka-ui/dist/Presence/usePresence.js
function Ct(e, n) {
	let r = S({}), a = S("none"), o = S(e), s = e.value ? "mounted" : "unmounted", c, l = n.value?.ownerDocument.defaultView ?? Pe, { state: u, dispatch: d } = St(s, {
		mounted: {
			UNMOUNT: "unmounted",
			ANIMATION_OUT: "unmountSuspended"
		},
		unmountSuspended: {
			MOUNT: "mounted",
			ANIMATION_END: "unmounted"
		},
		unmounted: { MOUNT: "mounted" }
	}), f = (e) => {
		if (L) {
			let t = new CustomEvent(e, {
				bubbles: !1,
				cancelable: !1
			});
			n.value?.dispatchEvent(t);
		}
	};
	F(e, async (e, t) => {
		let o = t !== e;
		if (await i(), o) {
			let i = a.value, o = wt(n.value);
			e ? (d("MOUNT"), f("enter"), o === "none" && f("after-enter")) : o === "none" || o === "undefined" || r.value?.display === "none" ? (d("UNMOUNT"), f("leave"), f("after-leave")) : t && i !== o ? (d("ANIMATION_OUT"), f("leave")) : (d("UNMOUNT"), f("after-leave"));
		}
	}, { immediate: !0 });
	let p = (e) => {
		if (e.target !== n.value) return;
		let t = wt(n.value), r = t.includes(CSS.escape(e.animationName)), i = u.value === "mounted" ? "enter" : "leave";
		if (r && (f(`after-${i}`), d("ANIMATION_END"), !o.value)) {
			let e = n.value.style.animationFillMode;
			n.value.style.animationFillMode = "forwards", c = l?.setTimeout(() => {
				n.value?.style.animationFillMode === "forwards" && (n.value.style.animationFillMode = e);
			});
		}
		t === "none" && d("ANIMATION_END");
	}, m = (e) => {
		e.target === n.value && (a.value = wt(n.value));
	}, h = F(n, (e, t) => {
		e ? (r.value = getComputedStyle(e), e.addEventListener("animationstart", m), e.addEventListener("animationcancel", p), e.addEventListener("animationend", p)) : (d("ANIMATION_END"), c !== void 0 && l?.clearTimeout(c), t?.removeEventListener("animationstart", m), t?.removeEventListener("animationcancel", p), t?.removeEventListener("animationend", p));
	}, { immediate: !0 }), g = F(u, () => {
		let e = wt(n.value);
		a.value = u.value === "mounted" ? e : "none";
	});
	return t(() => {
		h(), g(), n.value && (n.value.removeEventListener("animationstart", m), n.value.removeEventListener("animationcancel", p), n.value.removeEventListener("animationend", p)), c !== void 0 && l?.clearTimeout(c);
	}), { isPresent: D(() => ["mounted", "unmountSuspended"].includes(u.value)) };
}
function wt(e) {
	return e && getComputedStyle(e).animationName || "none";
}
// node_modules/reka-ui/dist/Presence/Presence.js
var Tt = /*#__PURE__*/ w({
	name: "Presence",
	props: {
		present: {
			type: Boolean,
			required: !0
		},
		forceMount: { type: Boolean }
	},
	slots: {},
	setup(e, { slots: t, expose: n }) {
		let { present: i, forceMount: a } = fe(e), o = S(), { isPresent: s } = Ct(i, o);
		n({ present: s });
		let c = t.default({ present: s.value });
		c = He(c || []);
		let l = N();
		if (c && c?.length > 1) {
			let e = l?.parent?.type.name ? `<${l.parent.type.name} />` : "component";
			throw Error([
				`Detected an invalid children for \`${e}\` for  \`Presence\` component.`,
				"",
				"Note: Presence works similarly to `v-if` directly, but it waits for animation/transition to finished before unmounting. So it expect only one direct child of valid VNode type.",
				"You can apply a few solutions:",
				["Provide a single child element so that `presence` directive attach correctly.", "Ensure the first child is an actual element instead of a raw text node or comment node."].map((e) => `  - ${e}`).join("\n")
			].join("\n"));
		}
		return () => a.value || i.value || s.value ? r(t.default({ present: s.value })[0], { ref: (e) => {
			let t = Fe(e);
			return t?.hasAttribute === void 0 || (t?.hasAttribute("data-reka-popper-content-wrapper") ? o.value = t.firstElementChild : o.value = t), t;
		} }) : null;
	}
}), Et = /*#__PURE__*/ w({
	name: "PrimitiveSlot",
	inheritAttrs: !1,
	setup(e, { attrs: t, slots: n }) {
		return () => {
			if (!n.default) return null;
			let e = He(n.default()), r = e.findIndex((e) => e.type !== T);
			if (r === -1) return e;
			let i = e[r];
			delete i.props?.ref;
			let o = i.props ? a(t, i.props) : t, s = ee({
				...i,
				props: {}
			}, o);
			return e.length === 1 ? s : (e[r] = s, e);
		};
	}
}), Dt = [
	"area",
	"img",
	"input"
], z = /*#__PURE__*/ w({
	name: "Primitive",
	inheritAttrs: !1,
	props: {
		asChild: {
			type: Boolean,
			default: !1
		},
		as: {
			type: [String, Object],
			default: "div"
		}
	},
	setup(e, { attrs: t, slots: n }) {
		let i = e.asChild ? "template" : e.as;
		return typeof i == "string" && Dt.includes(i) ? () => r(i, t) : i === "template" ? () => r(Et, t, { default: n.default }) : () => r(e.as, t, { default: n.default });
	}
}), Ot = "dismissableLayer.pointerDownOutside", kt = "dismissableLayer.focusOutside";
function At(e) {
	if (typeof e != "object" || !e) return !1;
	let t = e.ownerDocument?.defaultView;
	return typeof Element < "u" && e instanceof Element || !!t && e instanceof t.Element;
}
function jt(e, t) {
	if (!At(t)) return !1;
	if (e.contains(t)) return !0;
	let n = t.closest("[data-dismissable-layer]"), r = e.dataset.dismissableLayer === "" ? e : e.querySelector("[data-dismissable-layer]"), i = Array.from(e.ownerDocument.querySelectorAll("[data-dismissable-layer]"));
	return !!(n && (r === n || i.indexOf(r) < i.indexOf(n)));
}
function Mt(e, t, r = !0) {
	let i = S(!1), a = S(() => {});
	return n((n) => {
		if (!L || !j(r)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			let r = n.target;
			if (t?.value && r) {
				if (jt(t.value, r)) o.removeEventListener("click", a.value), i.value = !1;
				else {
					if (n.target && !i.value) {
						let t = { originalEvent: n };
						function r() {
							ve(Ot, e, t);
						}
						n.pointerType === "touch" ? (o.removeEventListener("click", a.value), a.value = r, o.addEventListener("click", a.value, { once: !0 })) : r();
					} else o.removeEventListener("click", a.value);
					i.value = !1;
				}
			}
		}, c = window.setTimeout(() => {
			o.addEventListener("pointerdown", s);
		}, 0);
		n(() => {
			window.clearTimeout(c), o.removeEventListener("pointerdown", s), o.removeEventListener("click", a.value);
		});
	}), { onPointerDownCapture: () => {
		j(r) && (i.value = !0);
	} };
}
function Nt(e, t, r = !0) {
	let a = S(!1);
	return n((n) => {
		if (!L || !j(r)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			if (!t?.value) return;
			await i(), await i();
			let r = n.target;
			t.value && r && !jt(t.value, r) && n.target && !a.value && ve(kt, e, { originalEvent: n });
		};
		o.addEventListener("focusin", s), n(() => o.removeEventListener("focusin", s));
	}), {
		onFocusCapture: () => {
			j(r) && (a.value = !0);
		},
		onBlurCapture: () => {
			j(r) && (a.value = !1);
		}
	};
}
// node_modules/reka-ui/dist/DismissableLayer/context.js
var B = /*#__PURE__*/ x({
	layersRoot: /* @__PURE__ */ new Set(),
	layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
	branches: /* @__PURE__ */ new Set()
}), Pt = /* @__PURE__ */ w({
	__name: "DismissableLayer",
	props: {
		disableOutsidePointerEvents: {
			type: Boolean,
			required: !1,
			default: !1
		},
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1
		},
		present: {
			type: Boolean,
			required: !1,
			default: !0
		}
	},
	emits: [
		"escapeKeyDown",
		"pointerDownOutside",
		"focusOutside",
		"interactOutside",
		"dismiss"
	],
	setup(e, { emit: t }) {
		let r = e, a = t, { forwardRef: s, currentElement: l } = R(), u = D(() => l.value?.ownerDocument ?? globalThis.document), d = D(() => B.layersRoot), p = D(() => l.value ? Array.from(d.value).indexOf(l.value) : -1), m = D(() => B.layersWithOutsidePointerEventsDisabled.size > 0), h = D(() => {
			let e = Array.from(d.value), [t] = [...B.layersWithOutsidePointerEventsDisabled].slice(-1), n = e.indexOf(t);
			return p.value >= n;
		}), g = Mt(async (e) => {
			let t = [...B.branches].some((t) => t?.contains(e.target));
			r.present && h.value && !t && (a("pointerDownOutside", e), a("interactOutside", e), await i(), e.defaultPrevented || a("dismiss"));
		}, l, () => r.present), _ = Nt((e) => {
			let t = [...B.branches].some((t) => t?.contains(e.target));
			r.present && !t && (a("focusOutside", e), a("interactOutside", e), e.defaultPrevented || a("dismiss"));
		}, l);
		return ze("Escape", (e) => {
			r.present && p.value === d.value.size - 1 && (a("escapeKeyDown", e), e.defaultPrevented || a("dismiss"));
		}, { target: () => u.value?.defaultView ?? globalThis.window }), F([
			l,
			() => r.disableOutsidePointerEvents,
			() => r.present
		], ([e, t, n], r, i) => {
			if (e && n && t) {
				let t = e.ownerDocument;
				Ke(t, e), B.layersWithOutsidePointerEventsDisabled.add(e), i(() => {
					B.layersWithOutsidePointerEventsDisabled.delete(e), qe(t, e);
				});
			}
		}, { immediate: !0 }), F([l, () => r.present], ([e, t], n, r) => {
			e && t && (d.value.add(e), r(() => {
				d.value.delete(e);
			}));
		}, { immediate: !0 }), n((e) => {
			e(() => {
				l.value && (d.value.delete(l.value), B.layersWithOutsidePointerEventsDisabled.delete(l.value));
			});
		}), (t, n) => (f(), A(k(z), {
			ref: k(s),
			"as-child": e.asChild,
			as: e.as,
			"data-dismissable-layer": "",
			style: E({ pointerEvents: m.value ? h.value ? "auto" : "none" : void 0 }),
			onFocusCapture: k(_).onFocusCapture,
			onBlurCapture: k(_).onBlurCapture,
			onPointerdownCapture: k(g).onPointerDownCapture
		}, {
			default: c(() => [o(t.$slots, "default")]),
			_: 3
		}, 8, [
			"as-child",
			"as",
			"style",
			"onFocusCapture",
			"onBlurCapture",
			"onPointerdownCapture"
		]));
	}
}), Ft = be(() => S([]));
function It() {
	let e = Ft();
	return {
		add(t) {
			let n = e.value[0];
			t !== n && n?.pause(), e.value = Lt(e.value, t), e.value.unshift(t);
		},
		remove(t) {
			e.value = Lt(e.value, t), e.value[0]?.resume();
		}
	};
}
function Lt(e, t) {
	let n = [...e], r = n.indexOf(t);
	return r !== -1 && n.splice(r, 1), n;
}
// node_modules/reka-ui/dist/FocusScope/utils.js
var Rt = "focusScope.autoFocusOnMount", zt = "focusScope.autoFocusOnUnmount", Bt = {
	bubbles: !1,
	cancelable: !0
};
function Vt(e, t) {
	let n = t;
	for (; n;) {
		if (e.contains(n)) return !0;
		n = n.getRootNode().host ?? null;
	}
	return !1;
}
function Ht(e, { select: t = !1 } = {}) {
	let n = I();
	for (let r of e) if (V(r, { select: t }), I() !== n) return !0;
}
function Ut(e) {
	let t = Wt(e);
	return [Gt(t, e), Gt(t.reverse(), e)];
}
function Wt(e) {
	let t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, { acceptNode: (e) => {
		let t = e.tagName === "INPUT" && e.type === "hidden";
		return e.disabled || e.hidden || t ? NodeFilter.FILTER_SKIP : e.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
	} });
	for (; n.nextNode();) t.push(n.currentNode);
	return t.sort((e, t) => e.tabIndex === t.tabIndex ? 0 : e.tabIndex === 0 ? 1 : t.tabIndex === 0 ? -1 : e.tabIndex - t.tabIndex);
}
function Gt(e, t) {
	for (let n of e) if (!Kt(n, { upTo: t })) return n;
}
function Kt(e, { upTo: t }) {
	if (getComputedStyle(e).visibility === "hidden") return !0;
	for (; e;) {
		if (t !== void 0 && e === t) return !1;
		if (getComputedStyle(e).display === "none") return !0;
		e = e.parentElement;
	}
	return !1;
}
function qt(e) {
	return e instanceof HTMLInputElement && "select" in e;
}
function V(e, { select: t = !1 } = {}) {
	if (e && e.focus) {
		let n = I();
		e.focus({ preventScroll: !0 }), e !== n && qt(e) && t && e.select();
	}
}
// node_modules/reka-ui/dist/FocusScope/FocusScope.js
var Jt = /* @__PURE__ */ w({
	__name: "FocusScope",
	props: {
		loop: {
			type: Boolean,
			required: !1,
			default: !1
		},
		trapped: {
			type: Boolean,
			required: !1,
			default: !1
		},
		present: {
			type: Boolean,
			required: !1,
			default: !0
		},
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1
		}
	},
	emits: ["mountAutoFocus", "unmountAutoFocus"],
	setup(e, { emit: t }) {
		let r = e, a = t, { currentRef: s, currentElement: l } = R(), u = S(null), d = It(), p = /*#__PURE__*/ x({
			paused: !1,
			pause() {
				this.paused = !0;
			},
			resume() {
				this.paused = !1;
			}
		});
		n((e) => {
			if (!L) return;
			let t = l.value;
			if (!r.trapped) return;
			let n = t?.ownerDocument ?? document, i = t ? t.getRootNode() : n;
			function a(e) {
				if (p.paused || !t) return;
				let n = e.target;
				t.contains(n) ? u.value = n : V(u.value, { select: !0 });
			}
			function o(e) {
				if (p.paused || !t) return;
				let n = e.relatedTarget;
				n !== null && (t.contains(n) || V(u.value, { select: !0 }));
			}
			function s(e) {
				let n = u.value;
				if (n === null || !e.some((e) => e.removedNodes.length > 0)) return;
				let r = I();
				r && t.contains(r) || t.contains(n) || V(t);
			}
			function c(e) {
				if (p.paused || !t) return;
				let n = e.composedPath()[0];
				Vt(t, n) || V(u.value, { select: !0 });
			}
			i.addEventListener("focusin", a), i.addEventListener("focusout", o), i !== n && n.addEventListener("focusin", c);
			let d = new MutationObserver(s);
			t && d.observe(t, {
				childList: !0,
				subtree: !0
			}), e(() => {
				i.removeEventListener("focusin", a), i.removeEventListener("focusout", o), i !== n && n.removeEventListener("focusin", c), d.disconnect();
			});
		});
		function m(e, t) {
			let n = new CustomEvent(Rt, Bt), r = (e) => a("mountAutoFocus", e);
			e.addEventListener(Rt, r), e.dispatchEvent(n), e.removeEventListener(Rt, r), n.defaultPrevented || (Ht(Wt(e), { select: !0 }), I() === t && V(e));
		}
		n(async (e) => {
			let t = l.value;
			if (await i(), !t) return;
			r.present !== !1 && d.add(p);
			let n = I();
			!t.contains(n) && r.present !== !1 && m(t, n), e(() => {
				let e = new CustomEvent(zt, Bt), r = (e) => {
					a("unmountAutoFocus", e);
				};
				t.addEventListener(zt, r), t.dispatchEvent(e), t.setAttribute("data-focus-scope-unmounting", ""), setTimeout(() => {
					e.defaultPrevented || V(n ?? document.body, { select: !0 }), t.removeEventListener(zt, r), d.remove(p), t.removeAttribute("data-focus-scope-unmounting");
				}, 0);
			});
		}), F(() => r.present, async (e, t) => {
			if (!L) return;
			if (e === !1 && t === !0) {
				d.remove(p);
				return;
			}
			if (e !== !0 || t !== !1) return;
			d.add(p), await i();
			let n = l.value;
			if (!n) return;
			let r = I();
			n.contains(r) || m(n, r);
		});
		function h(e) {
			if (!r.loop && !r.trapped || p.paused) return;
			let t = e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey, n = I();
			if (t && n) {
				let t = e.currentTarget, [i, a] = Ut(t);
				i && a ? !e.shiftKey && n === a ? (e.preventDefault(), r.loop && V(i, { select: !0 })) : e.shiftKey && n === i && (e.preventDefault(), r.loop && V(a, { select: !0 })) : n === t && e.preventDefault();
			}
		}
		return (t, n) => (f(), A(k(z), {
			ref_key: "currentRef",
			ref: s,
			tabindex: "-1",
			"as-child": e.asChild,
			as: e.as,
			onKeydown: h
		}, {
			default: c(() => [o(t.$slots, "default")]),
			_: 3
		}, 8, ["as-child", "as"]));
	}
}), Yt = /* @__PURE__ */ w({
	__name: "Teleport",
	props: {
		to: {
			type: null,
			required: !1
		},
		disabled: {
			type: Boolean,
			required: !1
		},
		defer: {
			type: Boolean,
			required: !1
		},
		forceMount: {
			type: Boolean,
			required: !1
		}
	},
	setup(e) {
		let t = e, n = Ue({}), r = D(() => t.to ?? n.teleportTo?.value ?? "body"), i = Le();
		return (t, n) => k(i) || e.forceMount ? (f(), A(pe, {
			key: 0,
			to: r.value,
			disabled: e.disabled,
			defer: e.defer
		}, [o(t.$slots, "default")], 8, [
			"to",
			"disabled",
			"defer"
		])) : O("v-if", !0);
	}
}), [Xt, Zt] = /*#__PURE__*/ _e("PopperRoot"), Qt = /* @__PURE__ */ w({
	inheritAttrs: !1,
	__name: "PopperRoot",
	setup(e) {
		let t = S();
		return Zt({
			anchor: t,
			onAnchorChange: (e) => t.value = e
		}), (e, t) => o(e.$slots, "default");
	}
}), $t = /* @__PURE__ */ w({
	__name: "PopperAnchor",
	props: {
		reference: {
			type: null,
			required: !1
		},
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1
		}
	},
	setup(e) {
		let t = e, { forwardRef: n, currentElement: r } = R(), i = Xt();
		return y(() => {
			i.onAnchorChange(t.reference ?? r.value);
		}), (t, r) => (f(), A(k(z), {
			ref: k(n),
			as: e.as,
			"as-child": e.asChild
		}, {
			default: c(() => [o(t.$slots, "default")]),
			_: 3
		}, 8, ["as", "as-child"]));
	}
});
// node_modules/reka-ui/dist/Popper/utils.js
function en(e) {
	return e !== null;
}
function tn(e) {
	return {
		name: "transformOrigin",
		options: e,
		fn(t) {
			let { placement: n, rects: r, middlewareData: i } = t, a = i.arrow?.centerOffset !== 0, o = a ? 0 : e.arrowWidth, s = a ? 0 : e.arrowHeight, [c, l] = nn(n), u = {
				start: e.dir === "rtl" ? "100%" : "0%",
				center: "50%",
				end: e.dir === "rtl" ? "0%" : "100%"
			}[l], d = {
				start: "0%",
				center: "50%",
				end: "100%"
			}[l], f = (i.arrow?.x ?? 0) + o / 2, p = (i.arrow?.y ?? 0) + s / 2, m = "", h = "";
			return c === "bottom" ? (m = a ? u : `${f}px`, h = `${-s}px`) : c === "top" ? (m = a ? u : `${f}px`, h = `${r.floating.height + s}px`) : c === "right" ? (m = `${-s}px`, h = a ? d : `${p}px`) : c === "left" && (m = `${r.floating.width + s}px`, h = a ? d : `${p}px`), { data: {
				x: m,
				y: h
			} };
		}
	};
}
function nn(e) {
	let [t, n = "center"] = e.split("-");
	return [t, n];
}
// node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs
var rn = [
	"top",
	"right",
	"bottom",
	"left"
], H = Math.min, U = Math.max, an = Math.round, on = Math.floor, W = (e) => ({
	x: e,
	y: e
}), sn = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function cn(e, t, n) {
	return U(e, H(t, n));
}
function G(e, t) {
	return typeof e == "function" ? e(t) : e;
}
function K(e) {
	return e.split("-")[0];
}
function ln(e) {
	return e.split("-")[1];
}
function un(e) {
	return e === "x" ? "y" : "x";
}
function dn(e) {
	return e === "y" ? "height" : "width";
}
function q(e) {
	let t = e[0];
	return t === "t" || t === "b" ? "y" : "x";
}
function fn(e) {
	return un(q(e));
}
function pn(e, t, n) {
	n === void 0 && (n = !1);
	let r = ln(e), i = fn(e), a = dn(i), o = i === "x" ? r === (n ? "end" : "start") ? "right" : "left" : r === "start" ? "bottom" : "top";
	return t.reference[a] > t.floating[a] && (o = Sn(o)), [o, Sn(o)];
}
function mn(e) {
	let t = Sn(e);
	return [
		hn(e),
		t,
		hn(t)
	];
}
function hn(e) {
	return e.includes("start") ? e.replace("start", "end") : e.replace("end", "start");
}
var gn = ["left", "right"], _n = ["right", "left"], vn = ["top", "bottom"], yn = ["bottom", "top"];
function bn(e, t, n) {
	switch (e) {
		case "top":
		case "bottom": return n ? t ? _n : gn : t ? gn : _n;
		case "left":
		case "right": return t ? vn : yn;
		default: return [];
	}
}
function xn(e, t, n, r) {
	let i = ln(e), a = bn(K(e), n === "start", r);
	return i && (a = a.map((e) => e + "-" + i), t && (a = a.concat(a.map(hn)))), a;
}
function Sn(e) {
	let t = K(e);
	return sn[t] + e.slice(t.length);
}
function Cn(e) {
	return {
		top: e.top ?? 0,
		right: e.right ?? 0,
		bottom: e.bottom ?? 0,
		left: e.left ?? 0
	};
}
function wn(e) {
	return typeof e == "number" ? {
		top: e,
		right: e,
		bottom: e,
		left: e
	} : Cn(e);
}
function Tn(e) {
	let { x: t, y: n, width: r, height: i } = e;
	return {
		width: r,
		height: i,
		top: n,
		left: t,
		right: t + r,
		bottom: n + i,
		x: t,
		y: n
	};
}
// node_modules/@floating-ui/core/dist/floating-ui.core.mjs
function En(e, t, n) {
	let { reference: r, floating: i } = e, a = q(t), o = fn(t), s = dn(o), c = K(t), l = a === "y", u = r.x + r.width / 2 - i.width / 2, d = r.y + r.height / 2 - i.height / 2, f = r[s] / 2 - i[s] / 2, p;
	switch (c) {
		case "top":
			p = {
				x: u,
				y: r.y - i.height
			};
			break;
		case "bottom":
			p = {
				x: u,
				y: r.y + r.height
			};
			break;
		case "right":
			p = {
				x: r.x + r.width,
				y: d
			};
			break;
		case "left":
			p = {
				x: r.x - i.width,
				y: d
			};
			break;
		default: p = {
			x: r.x,
			y: r.y
		};
	}
	let m = ln(t);
	return m && (p[o] += f * (m === "end" ? 1 : -1) * (n && l ? -1 : 1)), p;
}
async function Dn(e, t) {
	t === void 0 && (t = {});
	let { x: n, y: r, platform: i, rects: a, elements: o, strategy: s } = e, { boundary: c = "clippingAncestors", rootBoundary: l = "viewport", elementContext: u = "floating", altBoundary: d = !1, padding: f = 0 } = G(t, e), p = wn(f), m = o[d ? u === "floating" ? "reference" : "floating" : u], h = Tn(await i.getClippingRect({
		element: await (i.isElement == null ? void 0 : i.isElement(m)) ?? !0 ? m : m.contextElement || await (i.getDocumentElement == null ? void 0 : i.getDocumentElement(o.floating)),
		boundary: c,
		rootBoundary: l,
		strategy: s
	})), g = u === "floating" ? {
		x: n,
		y: r,
		width: a.floating.width,
		height: a.floating.height
	} : a.reference, _ = await (i.getOffsetParent == null ? void 0 : i.getOffsetParent(o.floating)), v = await (i.isElement == null ? void 0 : i.isElement(_)) && await (i.getScale == null ? void 0 : i.getScale(_)) || {
		x: 1,
		y: 1
	}, y = Tn(i.convertOffsetParentRelativeRectToViewportRelativeRect ? await i.convertOffsetParentRelativeRectToViewportRelativeRect({
		elements: o,
		rect: g,
		offsetParent: _,
		strategy: s
	}) : g);
	return {
		top: (h.top - y.top + p.top) / v.y,
		bottom: (y.bottom - h.bottom + p.bottom) / v.y,
		left: (h.left - y.left + p.left) / v.x,
		right: (y.right - h.right + p.right) / v.x
	};
}
var On = 50, kn = async (e, t, n) => {
	let { placement: r = "bottom", strategy: i = "absolute", middleware: a = [], platform: o } = n, s = o.detectOverflow ? o : {
		...o,
		detectOverflow: Dn
	}, c = await (o.isRTL == null ? void 0 : o.isRTL(t)), l = await o.getElementRects({
		reference: e,
		floating: t,
		strategy: i
	}), { x: u, y: d } = En(l, r, c), f = r, p = 0, m = {};
	for (let n = 0; n < a.length; n++) {
		let h = a[n];
		if (!h) continue;
		let { name: g, fn: _ } = h, { x: v, y, data: b, reset: x } = await _({
			x: u,
			y: d,
			initialPlacement: r,
			placement: f,
			strategy: i,
			middlewareData: m,
			rects: l,
			platform: s,
			elements: {
				reference: e,
				floating: t
			}
		});
		u = v ?? u, d = y ?? d, m[g] = {
			...m[g],
			...b
		}, x && p < On && (p++, typeof x == "object" && (x.placement && (f = x.placement), x.rects && (l = x.rects === !0 ? await o.getElementRects({
			reference: e,
			floating: t,
			strategy: i
		}) : x.rects), {x: u, y: d} = En(l, f, c)), n = -1);
	}
	return {
		x: u,
		y: d,
		placement: f,
		strategy: i,
		middlewareData: m
	};
}, An = (e) => ({
	name: "arrow",
	options: e,
	async fn(t) {
		let { x: n, y: r, placement: i, rects: a, platform: o, elements: s, middlewareData: c } = t, { element: l, padding: u = 0 } = G(e, t) || {};
		if (l == null) return {};
		let d = wn(u), f = {
			x: n,
			y: r
		}, p = fn(i), m = dn(p), h = await o.getDimensions(l), g = p === "y", _ = g ? "top" : "left", v = g ? "bottom" : "right", y = g ? "clientHeight" : "clientWidth", b = a.reference[m] + a.reference[p] - f[p] - a.floating[m], x = f[p] - a.reference[p], S = await (o.getOffsetParent == null ? void 0 : o.getOffsetParent(l)), C = S ? S[y] : 0;
		C && await (o.isElement == null ? void 0 : o.isElement(S)) || (C = s.floating[y] || a.floating[m]);
		let w = b / 2 - x / 2, T = C / 2 - h[m] / 2 - 1, E = H(d[_], T), ee = H(d[v], T), te = C - h[m] - ee, D = C / 2 - h[m] / 2 + w, ne = cn(E, D, te), O = !c.arrow && ln(i) != null && D !== ne && a.reference[m] / 2 - (D < E ? E : ee) - h[m] / 2 < 0, k = O ? D < E ? D - E : D - te : 0;
		return {
			[p]: f[p] + k,
			data: {
				[p]: ne,
				centerOffset: D - ne - k,
				...O && { alignmentOffset: k }
			},
			reset: O
		};
	}
}), jn = function(e) {
	return e === void 0 && (e = {}), {
		name: "flip",
		options: e,
		async fn(t) {
			var n;
			let { placement: r, middlewareData: i, rects: a, initialPlacement: o, platform: s, elements: c } = t, { mainAxis: l = !0, crossAxis: u = !0, fallbackPlacements: d, fallbackStrategy: f = "bestFit", fallbackAxisSideDirection: p = "none", flipAlignment: m = !0, ...h } = G(e, t);
			if ((n = i.arrow) != null && n.alignmentOffset) return {};
			let g = K(r), _ = q(o), v = K(o) === o, y = await (s.isRTL == null ? void 0 : s.isRTL(c.floating)), b = d || (v || !m ? [Sn(o)] : mn(o)), x = p !== "none";
			!d && x && b.push(...xn(o, m, p, y));
			let S = [o, ...b], C = await s.detectOverflow(t, h), w = [], T = i.flip?.overflows || [];
			if (l && w.push(C[g]), u) {
				let e = pn(r, a, y);
				w.push(C[e[0]], C[e[1]]);
			}
			if (T = [...T, {
				placement: r,
				overflows: w
			}], !w.every((e) => e <= 0)) {
				let e = (i.flip?.index || 0) + 1, t = S[e];
				if (t && (u !== "alignment" || _ === q(t) || T.every((e) => q(e.placement) !== _ || e.overflows[0] > 0))) return {
					data: {
						index: e,
						overflows: T
					},
					reset: { placement: t }
				};
				let n = T.filter((e) => e.overflows[0] <= 0).sort((e, t) => e.overflows[1] - t.overflows[1])[0]?.placement;
				if (!n) switch (f) {
					case "bestFit": {
						let e = T.filter((e) => {
							if (x) {
								let t = q(e.placement);
								return t === _ || t === "y";
							}
							return !0;
						}).map((e) => [e.placement, e.overflows.filter((e) => e > 0).reduce((e, t) => e + t, 0)]).sort((e, t) => e[1] - t[1])[0]?.[0];
						e && (n = e);
						break;
					}
					case "initialPlacement": n = o;
				}
				if (r !== n) return { reset: { placement: n } };
			}
			return {};
		}
	};
};
function Mn(e, t) {
	return {
		top: e.top - t.height,
		right: e.right - t.width,
		bottom: e.bottom - t.height,
		left: e.left - t.width
	};
}
function Nn(e) {
	return rn.some((t) => e[t] >= 0);
}
var Pn = function(e) {
	return e === void 0 && (e = {}), {
		name: "hide",
		options: e,
		async fn(t) {
			let { rects: n, platform: r } = t, { strategy: i = "referenceHidden", ...a } = G(e, t);
			switch (i) {
				case "referenceHidden": {
					let e = Mn(await r.detectOverflow(t, {
						...a,
						elementContext: "reference"
					}), n.reference);
					return { data: {
						referenceHiddenOffsets: e,
						referenceHidden: Nn(e)
					} };
				}
				case "escaped": {
					let e = Mn(await r.detectOverflow(t, {
						...a,
						altBoundary: !0
					}), n.floating);
					return { data: {
						escapedOffsets: e,
						escaped: Nn(e)
					} };
				}
				default: return {};
			}
		}
	};
}, Fn = /*#__PURE__*/ new Set(["left", "top"]);
async function In(e, t) {
	let { placement: n, platform: r, elements: i } = e, a = await (r.isRTL == null ? void 0 : r.isRTL(i.floating)), o = K(n), s = ln(n), c = q(n) === "y", l = Fn.has(o) ? -1 : 1, u = a && c ? -1 : 1, d = G(t, e), { mainAxis: f, crossAxis: p, alignmentAxis: m } = typeof d == "number" ? {
		mainAxis: d,
		crossAxis: 0,
		alignmentAxis: null
	} : {
		mainAxis: d.mainAxis || 0,
		crossAxis: d.crossAxis || 0,
		alignmentAxis: d.alignmentAxis
	};
	return s && typeof m == "number" && (p = s === "end" ? m * -1 : m), c ? {
		x: p * u,
		y: f * l
	} : {
		x: f * l,
		y: p * u
	};
}
var Ln = function(e) {
	return e === void 0 && (e = 0), {
		name: "offset",
		options: e,
		async fn(t) {
			var n;
			let { x: r, y: i, placement: a, middlewareData: o } = t, s = await In(t, e);
			return a === o.offset?.placement && (n = o.arrow) != null && n.alignmentOffset ? {} : {
				x: r + s.x,
				y: i + s.y,
				data: {
					...s,
					placement: a
				}
			};
		}
	};
}, Rn = function(e) {
	return e === void 0 && (e = {}), {
		name: "shift",
		options: e,
		async fn(t) {
			let { x: n, y: r, placement: i, platform: a } = t, { mainAxis: o = !0, crossAxis: s = !1, limiter: c = { fn: (e) => {
				let { x: t, y: n } = e;
				return {
					x: t,
					y: n
				};
			} }, ...l } = G(e, t), u = {
				x: n,
				y: r
			}, d = await a.detectOverflow(t, l), f = q(i), p = un(f), m = u[p], h = u[f], g = (e, t) => cn(t + d[e === "y" ? "top" : "left"], t, t - d[e === "y" ? "bottom" : "right"]);
			o && (m = g(p, m)), s && (h = g(f, h));
			let _ = c.fn({
				...t,
				[p]: m,
				[f]: h
			});
			return {
				..._,
				data: {
					x: _.x - n,
					y: _.y - r,
					enabled: {
						[p]: o,
						[f]: s
					}
				}
			};
		}
	};
}, zn = function(e) {
	return e === void 0 && (e = {}), {
		options: e,
		fn(t) {
			let { x: n, y: r, placement: i, rects: a, middlewareData: o } = t, { offset: s = 0, mainAxis: c = !0, crossAxis: l = !0 } = G(e, t), u = {
				x: n,
				y: r
			}, d = q(i), f = un(d), p = u[f], m = u[d], h = G(s, t), g = typeof h == "number" ? {
				mainAxis: h,
				crossAxis: 0
			} : {
				mainAxis: h.mainAxis ?? 0,
				crossAxis: h.crossAxis ?? 0
			};
			if (c) {
				let e = f === "y" ? "height" : "width", t = a.reference[f] - a.floating[e] + g.mainAxis, n = a.reference[f] + a.reference[e] - g.mainAxis;
				p < t ? p = t : p > n && (p = n);
			}
			if (l) {
				let e = f === "y" ? "width" : "height", t = Fn.has(K(i)), n = a.reference[d] - a.floating[e] + (t && o.offset?.[d] || 0) + (t ? 0 : g.crossAxis), r = a.reference[d] + a.reference[e] + (t ? 0 : o.offset?.[d] || 0) - (t ? g.crossAxis : 0);
				m < n ? m = n : m > r && (m = r);
			}
			return {
				[f]: p,
				[d]: m
			};
		}
	};
}, Bn = function(e) {
	return e === void 0 && (e = {}), {
		name: "size",
		options: e,
		async fn(t) {
			let { placement: n, rects: r, platform: i, elements: a } = t, { apply: o = () => {}, ...s } = G(e, t), c = await i.detectOverflow(t, s), l = K(n), u = ln(n), d = q(n) === "y", { width: f, height: p } = r.floating, m, h;
			l === "top" || l === "bottom" ? (m = l, h = u === (await (i.isRTL == null ? void 0 : i.isRTL(a.floating)) ? "start" : "end") ? "left" : "right") : (h = l, m = u === "end" ? "top" : "bottom");
			let g = p - c.top - c.bottom, _ = f - c.left - c.right, v = H(p - c[m], g), y = H(f - c[h], _), b = t.middlewareData.shift, x = !b, S = v, C = y;
			b != null && b.enabled.x && (C = _), b != null && b.enabled.y && (S = g), x && !u && (d ? C = f - 2 * U(c.left, c.right) : S = p - 2 * U(c.top, c.bottom)), await o({
				...t,
				availableWidth: C,
				availableHeight: S
			});
			let w = await i.getDimensions(a.floating);
			return f !== w.width || p !== w.height ? { reset: { rects: !0 } } : {};
		}
	};
};
// node_modules/@floating-ui/utils/dist/floating-ui.utils.dom.mjs
function Vn() {
	return typeof window < "u";
}
function J(e) {
	return Hn(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function Y(e) {
	var t;
	return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function X(e) {
	return ((Hn(e) ? e.ownerDocument : e.document) || window.document)?.documentElement;
}
function Hn(e) {
	return Vn() ? e instanceof Node || e instanceof Y(e).Node : !1;
}
function Z(e) {
	return Vn() ? e instanceof Element || e instanceof Y(e).Element : !1;
}
function Q(e) {
	return Vn() ? e instanceof HTMLElement || e instanceof Y(e).HTMLElement : !1;
}
function Un(e) {
	return !Vn() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof Y(e).ShadowRoot;
}
function Wn(e) {
	let { overflow: t, overflowX: n, overflowY: r, display: i } = $(e);
	return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && i !== "inline" && i !== "contents";
}
function Gn(e) {
	return /^(table|td|th)$/.test(J(e));
}
function Kn(e) {
	try {
		if (e.matches(":popover-open")) return !0;
	} catch {}
	try {
		return e.matches(":modal");
	} catch {
		return !1;
	}
}
var qn = /transform|translate|scale|rotate|perspective|filter/, Jn = /paint|layout|strict|content/, Yn = (e) => !!e && e !== "none", Xn;
function Zn(e) {
	let t = Z(e) ? $(e) : e;
	return Yn(t.transform) || Yn(t.translate) || Yn(t.scale) || Yn(t.rotate) || Yn(t.perspective) || !$n() && (Yn(t.backdropFilter) || Yn(t.filter)) || qn.test(t.willChange || "") || Jn.test(t.contain || "");
}
function Qn(e) {
	let t = nr(e);
	for (; Q(t) && !er(t);) {
		if (Zn(t)) return t;
		if (Kn(t)) return null;
		t = nr(t);
	}
	return null;
}
function $n() {
	return Xn ??= typeof CSS < "u" && CSS.supports && CSS.supports("-webkit-backdrop-filter", "none"), Xn;
}
function er(e) {
	return /^(html|body|#document)$/.test(J(e));
}
function $(e) {
	return Y(e).getComputedStyle(e);
}
function tr(e) {
	return Z(e) ? {
		scrollLeft: e.scrollLeft,
		scrollTop: e.scrollTop
	} : {
		scrollLeft: e.scrollX,
		scrollTop: e.scrollY
	};
}
function nr(e) {
	if (J(e) === "html") return e;
	let t = e.assignedSlot || e.parentNode || Un(e) && e.host || X(e);
	return Un(t) ? t.host : t;
}
function rr(e) {
	let t = nr(e);
	return er(t) ? (e.ownerDocument || e).body : Q(t) && Wn(t) ? t : rr(t);
}
function ir(e, t, n) {
	t === void 0 && (t = []), n === void 0 && (n = !0);
	let r = rr(e), i = r === e.ownerDocument?.body, a = Y(r);
	if (i) {
		let e = ar(a);
		return t.concat(a, a.visualViewport || [], Wn(r) ? r : [], e && n ? ir(e) : []);
	}
	return t.concat(r, ir(r, [], n));
}
function ar(e) {
	return e.parent && Object.getPrototypeOf(e.parent) ? e.frameElement : null;
}
// node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs
function or(e) {
	let t = $(e), n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0, i = Q(e), a = i ? e.offsetWidth : n, o = i ? e.offsetHeight : r, s = an(n) !== a || an(r) !== o;
	return s && (n = a, r = o), {
		width: n,
		height: r,
		$: s
	};
}
function sr(e) {
	return Z(e) ? e : e.contextElement;
}
function cr(e) {
	let t = sr(e);
	if (!Q(t)) return W(1);
	let n = t.getBoundingClientRect(), { width: r, height: i, $: a } = or(t), o = (a ? an(n.width) : n.width) / r, s = (a ? an(n.height) : n.height) / i;
	return o && Number.isFinite(o) || (o = 1), s && Number.isFinite(s) || (s = 1), {
		x: o,
		y: s
	};
}
var lr = /*#__PURE__*/ W(0);
function ur(e) {
	let t = Y(e);
	return !$n() || !t.visualViewport ? lr : {
		x: t.visualViewport.offsetLeft,
		y: t.visualViewport.offsetTop
	};
}
function dr(e, t, n) {
	return t === void 0 && (t = !1), !!n && t && n === Y(e);
}
function fr(e, t, n, r) {
	t === void 0 && (t = !1), n === void 0 && (n = !1);
	let i = e.getBoundingClientRect(), a = sr(e), o = W(1);
	t && (r ? Z(r) && (o = cr(r)) : o = cr(e));
	let s = dr(a, n, r) ? ur(a) : W(0), c = (i.left + s.x) / o.x, l = (i.top + s.y) / o.y, u = i.width / o.x, d = i.height / o.y;
	if (a && r) {
		let e = Y(a), t = Z(r) ? Y(r) : r, n = e, i = ar(n);
		for (; i && t !== n;) {
			let e = cr(i), t = i.getBoundingClientRect(), r = $(i), a = t.left + (i.clientLeft + parseFloat(r.paddingLeft)) * e.x, o = t.top + (i.clientTop + parseFloat(r.paddingTop)) * e.y;
			c *= e.x, l *= e.y, u *= e.x, d *= e.y, c += a, l += o, n = Y(i), i = ar(n);
		}
	}
	return Tn({
		width: u,
		height: d,
		x: c,
		y: l
	});
}
function pr(e, t) {
	let n = tr(e).scrollLeft;
	return t ? t.left + n : fr(X(e)).left + n;
}
function mr(e, t) {
	let n = e.getBoundingClientRect();
	return {
		x: n.left + t.scrollLeft - pr(e, n),
		y: n.top + t.scrollTop
	};
}
function hr(e) {
	let { elements: t, rect: n, offsetParent: r, strategy: i } = e, a = i === "fixed", o = X(r), s = t ? Kn(t.floating) : !1;
	if (r === o || s && a) return n;
	let c = {
		scrollLeft: 0,
		scrollTop: 0
	}, l = W(1), u = W(0), d = Q(r);
	if ((d || !a) && ((J(r) !== "body" || Wn(o)) && (c = tr(r)), d)) {
		let e = fr(r);
		l = cr(r), u.x = e.x + r.clientLeft, u.y = e.y + r.clientTop;
	}
	let f = o && !d && !a ? mr(o, c) : W(0);
	return {
		width: n.width * l.x,
		height: n.height * l.y,
		x: n.x * l.x - c.scrollLeft * l.x + u.x + f.x,
		y: n.y * l.y - c.scrollTop * l.y + u.y + f.y
	};
}
function gr(e) {
	return e.getClientRects ? Array.from(e.getClientRects()) : [];
}
function _r(e) {
	let t = tr(e), n = e.ownerDocument.body, r = U(e.scrollWidth, e.clientWidth, n.scrollWidth, n.clientWidth), i = U(e.scrollHeight, e.clientHeight, n.scrollHeight, n.clientHeight), a = -t.scrollLeft + pr(e), o = -t.scrollTop;
	return $(n).direction === "rtl" && (a += U(e.clientWidth, n.clientWidth) - r), {
		width: r,
		height: i,
		x: a,
		y: o
	};
}
var vr = 25;
function yr(e, t, n) {
	n === void 0 && (n = "viewport");
	let r = n === "layoutViewport", i = Y(e), a = X(e), o = i.visualViewport, s = a.clientWidth, c = a.clientHeight, l = 0, u = 0;
	if (o) {
		let e = !$n() || t === "fixed";
		r ? e || (l = -o.offsetLeft, u = -o.offsetTop) : (s = o.width, c = o.height, e && (l = o.offsetLeft, u = o.offsetTop));
	}
	if (pr(a) <= 0) {
		let e = a.ownerDocument, t = e.body, n = getComputedStyle(t), r = e.compatMode === "CSS1Compat" && parseFloat(n.marginLeft) + parseFloat(n.marginRight) || 0, i = Math.abs(a.clientWidth - t.clientWidth - r), o = getComputedStyle(a).scrollbarGutter === "stable both-edges" ? i / 2 : i;
		o <= vr && (s -= o);
	}
	return {
		width: s,
		height: c,
		x: l,
		y: u
	};
}
function br(e, t) {
	let n = fr(e, !0, t === "fixed"), r = n.top + e.clientTop, i = n.left + e.clientLeft, a = cr(e);
	return {
		width: e.clientWidth * a.x,
		height: e.clientHeight * a.y,
		x: i * a.x,
		y: r * a.y
	};
}
function xr(e, t, n) {
	let r;
	if (t === "viewport" || t === "layoutViewport") r = yr(e, n, t);
	else if (t === "document") r = _r(X(e));
	else if (Z(t)) r = br(t, n);
	else {
		let n = ur(e);
		r = {
			x: t.x - n.x,
			y: t.y - n.y,
			width: t.width,
			height: t.height
		};
	}
	return Tn(r);
}
function Sr(e, t) {
	let n = t.get(e);
	if (n) return n;
	let r = ir(e, [], !1).filter((e) => Z(e) && J(e) !== "body"), i = null, a = $(e).position === "fixed", o = a ? nr(e) : e;
	for (; Z(o) && !er(o);) {
		let e = $(o), t = Zn(o), n = i ? i.position : a ? "fixed" : "";
		!t && (n === "fixed" || n === "absolute" && e.position === "static") ? r = r.filter((e) => e !== o) : i = e, o = nr(o);
	}
	return t.set(e, r), r;
}
function Cr(e) {
	let { element: t, boundary: n, rootBoundary: r, strategy: i } = e, a = [...n === "clippingAncestors" ? Kn(t) ? [] : Sr(t, this._c) : [].concat(n), r], o = xr(t, a[0], i), s = o.top, c = o.right, l = o.bottom, u = o.left;
	for (let e = 1; e < a.length; e++) {
		let n = xr(t, a[e], i);
		s = U(n.top, s), c = H(n.right, c), l = H(n.bottom, l), u = U(n.left, u);
	}
	return {
		width: c - u,
		height: l - s,
		x: u,
		y: s
	};
}
function wr(e) {
	let { width: t, height: n } = or(e);
	return {
		width: t,
		height: n
	};
}
function Tr(e, t, n) {
	let r = Q(t), i = X(t), a = n === "fixed", o = fr(e, !0, a, t), s = {
		scrollLeft: 0,
		scrollTop: 0
	}, c = W(0);
	if ((r || !a) && ((J(t) !== "body" || Wn(i)) && (s = tr(t)), r)) {
		let e = fr(t, !0, a, t);
		c.x = e.x + t.clientLeft, c.y = e.y + t.clientTop;
	}
	!r && i && (c.x = pr(i));
	let l = i && !r && !a ? mr(i, s) : W(0);
	return {
		x: o.left + s.scrollLeft - c.x - l.x,
		y: o.top + s.scrollTop - c.y - l.y,
		width: o.width,
		height: o.height
	};
}
function Er(e) {
	return $(e).position === "static";
}
function Dr(e, t) {
	if (!Q(e) || $(e).position === "fixed") return null;
	if (t) return t(e);
	let n = e.offsetParent;
	return X(e) === n && (n = n.ownerDocument.body), n;
}
function Or(e, t) {
	let n = Y(e);
	if (Kn(e)) return n;
	if (!Q(e)) {
		let t = nr(e);
		for (; t && !er(t);) {
			if (Z(t) && !Er(t)) return t;
			t = nr(t);
		}
		return n;
	}
	let r = Dr(e, t);
	for (; r && Gn(r) && Er(r);) r = Dr(r, t);
	return r && er(r) && Er(r) && !Zn(r) ? n : r || Qn(e) || n;
}
var kr = async function(e) {
	let t = this.getOffsetParent || Or, n = this.getDimensions, r = await n(e.floating);
	return {
		reference: Tr(e.reference, await t(e.floating), e.strategy),
		floating: {
			x: 0,
			y: 0,
			width: r.width,
			height: r.height
		}
	};
};
function Ar(e) {
	return $(e).direction === "rtl";
}
var jr = {
	convertOffsetParentRelativeRectToViewportRelativeRect: hr,
	getDocumentElement: X,
	getClippingRect: Cr,
	getOffsetParent: Or,
	getElementRects: kr,
	getClientRects: gr,
	getDimensions: wr,
	getScale: cr,
	isElement: Z,
	isRTL: Ar
};
function Mr(e, t) {
	return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function Nr(e, t, n) {
	let r = null, i, a = X(e);
	function o() {
		var e;
		clearTimeout(i), (e = r) == null || e.disconnect(), r = null;
	}
	function s(n, c) {
		n === void 0 && (n = !1), c === void 0 && (c = 1), o();
		let l = e.getBoundingClientRect(), { left: u, top: d, width: f, height: p } = l;
		if (n || t(), !f || !p) return;
		let m = on(d), h = on(a.clientWidth - (u + f)), g = on(a.clientHeight - (d + p)), _ = on(u), v = {
			rootMargin: -m + "px " + -h + "px " + -g + "px " + -_ + "px",
			threshold: U(0, H(1, c)) || 1
		}, y = !0;
		function b(t) {
			let n = t[0].intersectionRatio;
			if (!Mr(l, e.getBoundingClientRect())) return s();
			if (n !== c) {
				if (!y) return s();
				n ? s(!1, n) : i = setTimeout(() => {
					s(!1, 1e-7);
				}, 1e3);
			}
			y = !1;
		}
		try {
			r = new IntersectionObserver(b, {
				...v,
				root: a.ownerDocument
			});
		} catch {
			r = new IntersectionObserver(b, v);
		}
		r.observe(e);
	}
	let c = Y(e), l = () => s(n);
	return c.addEventListener("resize", l), s(!0), () => {
		c.removeEventListener("resize", l), o();
	};
}
function Pr(e, t, n, r) {
	r === void 0 && (r = {});
	let { ancestorScroll: i = !0, ancestorResize: a = !0, elementResize: o = typeof ResizeObserver == "function", layoutShift: s = typeof IntersectionObserver == "function", animationFrame: c = !1 } = r, l = sr(e), u = i || a ? [...l ? ir(l) : [], ...t ? ir(t) : []] : [];
	u.forEach((e) => {
		i && e.addEventListener("scroll", n), a && e.addEventListener("resize", n);
	});
	let d = l && s ? Nr(l, n, a) : null, f = -1, p = null;
	o && (p = new ResizeObserver((e) => {
		let [r] = e;
		r && r.target === l && p && t && (p.unobserve(t), cancelAnimationFrame(f), f = requestAnimationFrame(() => {
			var e;
			(e = p) == null || e.observe(t);
		})), n();
	}), l && !c && p.observe(l), t && p.observe(t));
	let m, h = c ? fr(e) : null;
	c && g();
	function g() {
		let t = fr(e);
		h && !Mr(h, t) && n(), h = t, m = requestAnimationFrame(g);
	}
	return n(), () => {
		var e;
		u.forEach((e) => {
			i && e.removeEventListener("scroll", n), a && e.removeEventListener("resize", n);
		}), d?.(), (e = p) == null || e.disconnect(), p = null, c && cancelAnimationFrame(m);
	};
}
var Fr = Ln, Ir = Rn, Lr = jn, Rr = Bn, zr = Pn, Br = An, Vr = zn, Hr = (e, t, n) => {
	let r = /* @__PURE__ */ new Map(), i = n ?? {}, a = {
		...jr,
		...i.platform,
		_c: r
	};
	return kn(e, t, {
		...i,
		platform: a
	});
};
// node_modules/@floating-ui/vue/dist/floating-ui.vue.mjs
function Ur(e) {
	return typeof e == "object" && !!e && "$el" in e;
}
function Wr(e) {
	if (Ur(e)) {
		let t = e.$el;
		return Hn(t) && J(t) === "#comment" ? null : t;
	}
	return e;
}
function Gr(e) {
	return {
		name: "arrow",
		options: e,
		fn(t) {
			let n = Wr(j(e.element));
			return n == null ? {} : Br({
				element: n,
				padding: e.padding
			}).fn(t);
		}
	};
}
function Kr(e) {
	return typeof window > "u" ? 1 : (e.ownerDocument.defaultView || window).devicePixelRatio || 1;
}
function qr(e, t) {
	let n = Kr(e);
	return Math.round(t * n) / n;
}
function Jr(t, n, r) {
	r === void 0 && (r = {});
	let i = r.whileElementsMounted, a = D(() => j(r.open) ?? !0), o = D(() => j(r.middleware)), s = D(() => j(r.placement) ?? "bottom"), c = D(() => j(r.strategy) ?? "absolute"), d = D(() => j(r.transform) ?? !0), f = D(() => Wr(t.value)), p = D(() => Wr(n.value)), m = S(0), g = S(0), _ = S(c.value), v = S(s.value), y = e({}), b = S(!1), x = D(() => {
		let e = {
			position: _.value,
			left: "0",
			top: "0"
		};
		if (!p.value) return e;
		let t = qr(p.value, m.value), n = qr(p.value, g.value);
		return d.value ? {
			...e,
			transform: "translate(" + t + "px, " + n + "px)",
			...Kr(p.value) >= 1.5 && { willChange: "transform" }
		} : {
			position: _.value,
			left: t + "px",
			top: n + "px"
		};
	}), C;
	function w() {
		if (f.value == null || p.value == null) return;
		let e = a.value;
		Hr(f.value, p.value, {
			middleware: o.value,
			placement: s.value,
			strategy: c.value
		}).then((t) => {
			m.value = t.x, g.value = t.y, _.value = t.strategy, v.value = t.placement, y.value = t.middlewareData, b.value = e !== !1;
		});
	}
	function T() {
		typeof C == "function" && (C(), C = void 0);
	}
	function E() {
		T(), i === void 0 ? w() : f.value != null && p.value != null && (C = i(f.value, p.value, w));
	}
	function ee() {
		a.value || (b.value = !1);
	}
	return F([
		o,
		s,
		c,
		a
	], w, { flush: "sync" }), F([f, p], E, { flush: "sync" }), F(a, ee, { flush: "sync" }), u() && l(T), {
		x: h(m),
		y: h(g),
		strategy: h(_),
		placement: h(v),
		middlewareData: h(y),
		isPositioned: h(b),
		floatingStyles: x,
		update: w
	};
}
// node_modules/reka-ui/dist/Popper/PopperContent.js
var Yr = ["dir"], Xr = {
	side: "bottom",
	sideOffset: 0,
	sideFlip: !0,
	align: "center",
	alignOffset: 0,
	alignFlip: !0,
	arrowPadding: 0,
	hideShiftedArrow: !0,
	avoidCollisions: !0,
	collisionBoundary: () => [],
	collisionPadding: 0,
	sticky: "partial",
	hideWhenDetached: !1,
	positionStrategy: "fixed",
	updatePositionStrategy: "optimized",
	prioritizePosition: !1
}, [Zr, Qr] = /*#__PURE__*/ _e("PopperContent"), $r = /* @__PURE__ */ w({
	inheritAttrs: !1,
	__name: "PopperContent",
	props: /* @__PURE__ */ v({
		memoDependencies: {
			type: Array,
			required: !1
		},
		side: {
			type: null,
			required: !1
		},
		sideOffset: {
			type: Number,
			required: !1
		},
		sideFlip: {
			type: Boolean,
			required: !1
		},
		align: {
			type: null,
			required: !1
		},
		alignOffset: {
			type: Number,
			required: !1
		},
		alignFlip: {
			type: Boolean,
			required: !1
		},
		avoidCollisions: {
			type: Boolean,
			required: !1
		},
		collisionBoundary: {
			type: null,
			required: !1
		},
		collisionPadding: {
			type: [Number, Object],
			required: !1
		},
		arrowPadding: {
			type: Number,
			required: !1
		},
		hideShiftedArrow: {
			type: Boolean,
			required: !1
		},
		sticky: {
			type: String,
			required: !1
		},
		hideWhenDetached: {
			type: Boolean,
			required: !1
		},
		positionStrategy: {
			type: String,
			required: !1
		},
		updatePositionStrategy: {
			type: String,
			required: !1
		},
		disableUpdateOnLayoutShift: {
			type: Boolean,
			required: !1
		},
		prioritizePosition: {
			type: Boolean,
			required: !1
		},
		reference: {
			type: null,
			required: !1
		},
		dir: {
			type: String,
			required: !1
		},
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1
		}
	}, { ...Xr }),
	emits: ["placed"],
	setup(e, { emit: t }) {
		let r = e, i = t, s = Xt(), { forwardRef: l, currentElement: u } = R(), d = rt(D(() => r.dir)), p = S(), m = S(), { width: h, height: g } = xt(m), _ = D(() => r.side + (r.align === "center" ? "" : `-${r.align}`)), v = D(() => typeof r.collisionPadding == "number" ? r.collisionPadding : {
			top: 0,
			right: 0,
			bottom: 0,
			left: 0,
			...r.collisionPadding
		}), x = D(() => Array.isArray(r.collisionBoundary) ? r.collisionBoundary : [r.collisionBoundary]), C = D(() => ({
			padding: v.value,
			boundary: x.value.filter(en),
			altBoundary: x.value.length > 0
		})), w = D(() => ({
			mainAxis: r.sideFlip,
			crossAxis: r.alignFlip
		})), T = D(() => [
			Fr({
				mainAxis: r.sideOffset + g.value,
				alignmentAxis: r.alignOffset
			}),
			r.prioritizePosition && r.avoidCollisions && Lr({
				...C.value,
				...w.value
			}),
			r.avoidCollisions && Ir({
				mainAxis: !0,
				crossAxis: !!r.prioritizePosition,
				limiter: r.sticky === "partial" ? Vr() : void 0,
				...C.value
			}),
			!r.prioritizePosition && r.avoidCollisions && Lr({
				...C.value,
				...w.value
			}),
			Rr({
				...C.value,
				apply: ({ elements: e, rects: t, availableWidth: n, availableHeight: r }) => {
					let { width: i, height: a } = t.reference, o = e.floating.style;
					o.setProperty("--reka-popper-available-width", `${n}px`), o.setProperty("--reka-popper-available-height", `${r}px`), o.setProperty("--reka-popper-anchor-width", `${i}px`), o.setProperty("--reka-popper-anchor-height", `${a}px`);
				}
			}),
			m.value && Gr({
				element: m.value,
				padding: r.arrowPadding
			}),
			tn({
				arrowWidth: h.value,
				arrowHeight: g.value,
				dir: d.value
			}),
			r.hideWhenDetached && zr({
				strategy: "referenceHidden",
				...C.value
			})
		]), { floatingStyles: ee, placement: te, isPositioned: O, middlewareData: re, update: ie } = Jr(D(() => r.reference ?? s.anchor.value), p, {
			strategy: r.positionStrategy,
			placement: _,
			whileElementsMounted: (...e) => Pr(...e, {
				layoutShift: !r.disableUpdateOnLayoutShift,
				animationFrame: r.updatePositionStrategy === "always"
			}),
			middleware: T
		}), ae = D(() => nn(te.value)[0]), oe = D(() => nn(te.value)[1]);
		y(() => {
			O.value && i("placed");
		});
		let j = D(() => {
			let e = re.value.arrow?.centerOffset !== 0;
			return r.hideShiftedArrow && e;
		}), se = S("");
		return n(() => {
			u.value && (se.value = window.getComputedStyle(u.value).zIndex);
		}), Qr({
			placedSide: ae,
			onArrowChange: (e) => m.value = e,
			arrowX: D(() => re.value.arrow?.x ?? 0),
			arrowY: D(() => re.value.arrow?.y ?? 0),
			shouldHideArrow: j
		}), (e, t) => (f(), ne("div", {
			ref_key: "floatingRef",
			ref: p,
			"data-reka-popper-content-wrapper": "",
			dir: k(d),
			style: E({
				...k(ee),
				transform: k(O) ? k(ee).transform : "translate(0, -200%)",
				minWidth: "max-content",
				zIndex: se.value,
				"--reka-popper-transform-origin": [k(re).transformOrigin?.x, k(re).transformOrigin?.y].join(" "),
				...k(re).hide?.referenceHidden && {
					visibility: "hidden",
					pointerEvents: "none"
				}
			})
		}, [r.memoDependencies ? b([
			r.asChild,
			r.as,
			ae.value,
			oe.value,
			k(O),
			...Object.values(e.$attrs),
			...r.memoDependencies
		], () => (f(), A(k(z), a({
			key: 0,
			ref: k(l)
		}, e.$attrs, {
			"as-child": r.asChild,
			as: r.as,
			"data-side": ae.value,
			"data-align": oe.value,
			style: { animation: k(O) ? void 0 : "none" }
		}), {
			default: c(() => [o(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"style"
		])), t, 0) : (f(), A(k(z), a({
			key: 1,
			ref: k(l)
		}, e.$attrs, {
			"as-child": r.asChild,
			as: r.as,
			"data-side": ae.value,
			"data-align": oe.value,
			dir: k(d),
			style: { animation: k(O) ? void 0 : "none" }
		}), {
			default: c(() => [o(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"dir",
			"style"
		]))], 12, Yr));
	}
}), [ei, ti] = /*#__PURE__*/ _e("PopoverRoot"), ni = /* @__PURE__ */ w({
	__name: "PopoverRoot",
	props: {
		defaultOpen: {
			type: Boolean,
			required: !1,
			default: !1
		},
		open: {
			type: Boolean,
			required: !1,
			default: void 0
		},
		modal: {
			type: Boolean,
			required: !1,
			default: !1
		}
	},
	emits: ["update:open"],
	setup(e, { emit: t }) {
		let n = e, r = t, { modal: i } = fe(n), a = Ve(n, "open", r, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		});
		return ti({
			contentId: "",
			triggerId: "",
			modal: i,
			open: a,
			onOpenChange: (e) => {
				a.value = e;
			},
			onOpenToggle: () => {
				a.value = !a.value;
			},
			triggerElement: S(),
			hasCustomAnchor: S(!1)
		}), (e, t) => (f(), A(k(Qt), null, {
			default: c(() => [o(e.$slots, "default", {
				open: k(a),
				close: () => a.value = !1
			})]),
			_: 3
		}));
	}
}), ri = /* @__PURE__ */ w({
	__name: "PopoverClose",
	props: {
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1,
			default: "button"
		}
	},
	setup(e) {
		let t = e;
		R();
		let n = ei();
		return (r, i) => (f(), A(k(z), {
			type: e.as === "button" ? "button" : void 0,
			as: e.as,
			"as-child": t.asChild,
			onClick: i[0] ||= (e) => k(n).onOpenChange(!1)
		}, {
			default: c(() => [o(r.$slots, "default")]),
			_: 3
		}, 8, [
			"type",
			"as",
			"as-child"
		]));
	}
}), ii = /* @__PURE__ */ w({
	__name: "PopoverContentImpl",
	props: {
		trapFocus: {
			type: Boolean,
			required: !1
		},
		memoDependencies: {
			type: Array,
			required: !1
		},
		side: {
			type: null,
			required: !1
		},
		sideOffset: {
			type: Number,
			required: !1
		},
		sideFlip: {
			type: Boolean,
			required: !1
		},
		align: {
			type: null,
			required: !1
		},
		alignOffset: {
			type: Number,
			required: !1
		},
		alignFlip: {
			type: Boolean,
			required: !1
		},
		avoidCollisions: {
			type: Boolean,
			required: !1
		},
		collisionBoundary: {
			type: null,
			required: !1
		},
		collisionPadding: {
			type: [Number, Object],
			required: !1
		},
		arrowPadding: {
			type: Number,
			required: !1
		},
		hideShiftedArrow: {
			type: Boolean,
			required: !1
		},
		sticky: {
			type: String,
			required: !1
		},
		hideWhenDetached: {
			type: Boolean,
			required: !1
		},
		positionStrategy: {
			type: String,
			required: !1
		},
		updatePositionStrategy: {
			type: String,
			required: !1
		},
		disableUpdateOnLayoutShift: {
			type: Boolean,
			required: !1
		},
		prioritizePosition: {
			type: Boolean,
			required: !1
		},
		reference: {
			type: null,
			required: !1
		},
		dir: {
			type: String,
			required: !1
		},
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1
		},
		disableOutsidePointerEvents: {
			type: Boolean,
			required: !1
		}
	},
	emits: [
		"escapeKeyDown",
		"pointerDownOutside",
		"focusOutside",
		"interactOutside",
		"openAutoFocus",
		"closeAutoFocus"
	],
	setup(e, { emit: t }) {
		let n = e, r = t, i = ct(je(n, "trapFocus", "disableOutsidePointerEvents")), { forwardRef: s } = R(), l = ei();
		return ot(), (t, n) => (f(), A(k(Jt), {
			"as-child": "",
			loop: "",
			trapped: e.trapFocus,
			onMountAutoFocus: n[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: n[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: c(() => [P(k(Pt), {
				"as-child": "",
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				onPointerDownOutside: n[0] ||= (e) => r("pointerDownOutside", e),
				onInteractOutside: n[1] ||= (e) => r("interactOutside", e),
				onEscapeKeyDown: n[2] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: n[3] ||= (e) => r("focusOutside", e),
				onDismiss: n[4] ||= (e) => k(l).onOpenChange(!1)
			}, {
				default: c(() => [P(k($r), a(k(i), {
					id: k(l).contentId,
					ref: k(s),
					"data-state": k(l).open.value ? "open" : "closed",
					"aria-labelledby": k(l).triggerId,
					style: {
						"--reka-popover-content-transform-origin": "var(--reka-popper-transform-origin)",
						"--reka-popover-content-available-width": "var(--reka-popper-available-width)",
						"--reka-popover-content-available-height": "var(--reka-popper-available-height)",
						"--reka-popover-trigger-width": "var(--reka-popper-anchor-width)",
						"--reka-popover-trigger-height": "var(--reka-popper-anchor-height)"
					},
					role: "dialog"
				}), {
					default: c(() => [o(t.$slots, "default")]),
					_: 3
				}, 16, [
					"id",
					"data-state",
					"aria-labelledby"
				])]),
				_: 3
			}, 8, ["disable-outside-pointer-events"])]),
			_: 3
		}, 8, ["trapped"]));
	}
}), ai = /* @__PURE__ */ w({
	__name: "PopoverContentModal",
	props: {
		memoDependencies: {
			type: Array,
			required: !1
		},
		side: {
			type: null,
			required: !1
		},
		sideOffset: {
			type: Number,
			required: !1
		},
		sideFlip: {
			type: Boolean,
			required: !1
		},
		align: {
			type: null,
			required: !1
		},
		alignOffset: {
			type: Number,
			required: !1
		},
		alignFlip: {
			type: Boolean,
			required: !1
		},
		avoidCollisions: {
			type: Boolean,
			required: !1
		},
		collisionBoundary: {
			type: null,
			required: !1
		},
		collisionPadding: {
			type: [Number, Object],
			required: !1
		},
		arrowPadding: {
			type: Number,
			required: !1
		},
		hideShiftedArrow: {
			type: Boolean,
			required: !1
		},
		sticky: {
			type: String,
			required: !1
		},
		hideWhenDetached: {
			type: Boolean,
			required: !1
		},
		positionStrategy: {
			type: String,
			required: !1
		},
		updatePositionStrategy: {
			type: String,
			required: !1
		},
		disableUpdateOnLayoutShift: {
			type: Boolean,
			required: !1
		},
		prioritizePosition: {
			type: Boolean,
			required: !1
		},
		reference: {
			type: null,
			required: !1
		},
		dir: {
			type: String,
			required: !1
		},
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1
		},
		disableOutsidePointerEvents: {
			type: Boolean,
			required: !1
		}
	},
	emits: [
		"escapeKeyDown",
		"pointerDownOutside",
		"focusOutside",
		"interactOutside",
		"openAutoFocus",
		"closeAutoFocus"
	],
	setup(e, { emit: t }) {
		let n = e, r = t, i = ei(), s = S(!1);
		et(!0);
		let l = lt(n, r), { forwardRef: u, currentElement: d } = R();
		return yt(d), (e, t) => (f(), A(ii, a(k(l), {
			ref: k(u),
			"trap-focus": k(i).open.value,
			"disable-outside-pointer-events": "",
			onCloseAutoFocus: t[0] ||= ue((e) => {
				r("closeAutoFocus", e), s.value || k(i).triggerElement.value?.focus();
			}, ["prevent"]),
			onPointerDownOutside: t[1] ||= (e) => {
				r("pointerDownOutside", e);
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0, i = t.button === 2 || n;
				s.value = i;
			},
			onFocusOutside: t[2] ||= ue(() => {}, ["prevent"])
		}), {
			default: c(() => [o(e.$slots, "default")]),
			_: 3
		}, 16, ["trap-focus"]));
	}
}), oi = /* @__PURE__ */ w({
	__name: "PopoverContentNonModal",
	props: {
		memoDependencies: {
			type: Array,
			required: !1
		},
		side: {
			type: null,
			required: !1
		},
		sideOffset: {
			type: Number,
			required: !1
		},
		sideFlip: {
			type: Boolean,
			required: !1
		},
		align: {
			type: null,
			required: !1
		},
		alignOffset: {
			type: Number,
			required: !1
		},
		alignFlip: {
			type: Boolean,
			required: !1
		},
		avoidCollisions: {
			type: Boolean,
			required: !1
		},
		collisionBoundary: {
			type: null,
			required: !1
		},
		collisionPadding: {
			type: [Number, Object],
			required: !1
		},
		arrowPadding: {
			type: Number,
			required: !1
		},
		hideShiftedArrow: {
			type: Boolean,
			required: !1
		},
		sticky: {
			type: String,
			required: !1
		},
		hideWhenDetached: {
			type: Boolean,
			required: !1
		},
		positionStrategy: {
			type: String,
			required: !1
		},
		updatePositionStrategy: {
			type: String,
			required: !1
		},
		disableUpdateOnLayoutShift: {
			type: Boolean,
			required: !1
		},
		prioritizePosition: {
			type: Boolean,
			required: !1
		},
		reference: {
			type: null,
			required: !1
		},
		dir: {
			type: String,
			required: !1
		},
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1
		},
		disableOutsidePointerEvents: {
			type: Boolean,
			required: !1
		}
	},
	emits: [
		"escapeKeyDown",
		"pointerDownOutside",
		"focusOutside",
		"interactOutside",
		"openAutoFocus",
		"closeAutoFocus"
	],
	setup(e, { emit: t }) {
		let n = e, r = t, i = ei(), s = S(!1), l = S(!1), u = lt(n, r);
		return (e, t) => (f(), A(ii, a(k(u), {
			"trap-focus": !1,
			"disable-outside-pointer-events": !1,
			onCloseAutoFocus: t[0] ||= (e) => {
				r("closeAutoFocus", e), e.defaultPrevented || (s.value || k(i).triggerElement.value?.focus(), e.preventDefault()), s.value = !1, l.value = !1;
			},
			onInteractOutside: t[1] ||= async (e) => {
				r("interactOutside", e), e.defaultPrevented || (s.value = !0, e.detail.originalEvent.type === "pointerdown" && (l.value = !0));
				let t = e.target;
				k(i).triggerElement.value?.contains(t) && e.preventDefault(), e.detail.originalEvent.type === "focusin" && l.value && e.preventDefault();
			}
		}), {
			default: c(() => [o(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), si = /* @__PURE__ */ w({
	__name: "PopoverContent",
	props: {
		forceMount: {
			type: Boolean,
			required: !1
		},
		memoDependencies: {
			type: Array,
			required: !1
		},
		side: {
			type: null,
			required: !1
		},
		sideOffset: {
			type: Number,
			required: !1
		},
		sideFlip: {
			type: Boolean,
			required: !1
		},
		align: {
			type: null,
			required: !1
		},
		alignOffset: {
			type: Number,
			required: !1
		},
		alignFlip: {
			type: Boolean,
			required: !1
		},
		avoidCollisions: {
			type: Boolean,
			required: !1
		},
		collisionBoundary: {
			type: null,
			required: !1
		},
		collisionPadding: {
			type: [Number, Object],
			required: !1
		},
		arrowPadding: {
			type: Number,
			required: !1
		},
		hideShiftedArrow: {
			type: Boolean,
			required: !1
		},
		sticky: {
			type: String,
			required: !1
		},
		hideWhenDetached: {
			type: Boolean,
			required: !1
		},
		positionStrategy: {
			type: String,
			required: !1
		},
		updatePositionStrategy: {
			type: String,
			required: !1
		},
		disableUpdateOnLayoutShift: {
			type: Boolean,
			required: !1
		},
		prioritizePosition: {
			type: Boolean,
			required: !1
		},
		reference: {
			type: null,
			required: !1
		},
		dir: {
			type: String,
			required: !1
		},
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1
		},
		disableOutsidePointerEvents: {
			type: Boolean,
			required: !1
		}
	},
	emits: [
		"escapeKeyDown",
		"pointerDownOutside",
		"focusOutside",
		"interactOutside",
		"openAutoFocus",
		"closeAutoFocus"
	],
	setup(e, { emit: t }) {
		let n = e, r = t, i = ei(), s = lt(n, r), { forwardRef: l } = R();
		return i.contentId ||= bt(void 0, "reka-popover-content"), (t, n) => (f(), A(k(Tt), { present: e.forceMount || k(i).open.value }, {
			default: c(() => [k(i).modal.value ? (f(), A(ai, a({ key: 0 }, k(s), { ref: k(l) }), {
				default: c(() => [o(t.$slots, "default")]),
				_: 3
			}, 16)) : (f(), A(oi, a({ key: 1 }, k(s), { ref: k(l) }), {
				default: c(() => [o(t.$slots, "default")]),
				_: 3
			}, 16))]),
			_: 3
		}, 8, ["present"]));
	}
}), ci = /* @__PURE__ */ w({
	__name: "PopoverPortal",
	props: {
		to: {
			type: null,
			required: !1
		},
		disabled: {
			type: Boolean,
			required: !1
		},
		defer: {
			type: Boolean,
			required: !1
		},
		forceMount: {
			type: Boolean,
			required: !1
		}
	},
	setup(e) {
		let t = e;
		return (e, n) => (f(), A(k(Yt), de(_(t)), {
			default: c(() => [o(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), li = /* @__PURE__ */ w({
	__name: "PopoverTrigger",
	props: {
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1,
			default: "button"
		}
	},
	setup(e) {
		let t = e, n = ei(), { forwardRef: r, currentElement: i } = R();
		return n.triggerId ||= bt(void 0, "reka-popover-trigger"), n.contentId ||= bt(void 0, "reka-popover-content"), ie(() => {
			n.triggerElement.value = i.value;
		}), (i, a) => (f(), A(d(k(n).hasCustomAnchor.value ? k(z) : k($t)), { "as-child": "" }, {
			default: c(() => [P(k(z), {
				id: k(n).triggerId,
				ref: k(r),
				type: e.as === "button" ? "button" : void 0,
				"aria-haspopup": "dialog",
				"aria-expanded": k(n).open.value,
				"aria-controls": k(n).open.value ? k(n).contentId : void 0,
				"data-state": k(n).open.value ? "open" : "closed",
				as: e.as,
				"as-child": t.asChild,
				onClick: k(n).onOpenToggle
			}, {
				default: c(() => [o(i.$slots, "default")]),
				_: 3
			}, 8, [
				"id",
				"type",
				"aria-expanded",
				"aria-controls",
				"data-state",
				"as",
				"as-child",
				"onClick"
			])]),
			_: 3
		}));
	}
}), ui = [
	"data-active",
	"aria-label",
	"title"
], di = { class: "tc-column-filter-label" }, fi = { class: "tc-filter-popover-heading list-filter-popover__heading" }, pi = /*#__PURE__*/ ge(/* @__PURE__ */ w({
	__name: "FilterPopover",
	props: {
		label: {},
		triggerLabel: {},
		active: { type: Boolean },
		summary: {},
		open: { type: Boolean }
	},
	emits: ["update:open"],
	setup(e, { emit: t }) {
		let n = t;
		return (t, r) => (f(), A(k(ni), {
			open: e.open,
			modal: !1,
			"onUpdate:open": r[0] ||= (e) => n("update:open", e)
		}, {
			default: c(() => [P(k(li), { "as-child": "" }, {
				default: c(() => [M("button", {
					type: "button",
					class: se(["tc-column-filter-trigger", { "is-active": e.active }]),
					"data-active": e.active ? "" : void 0,
					"aria-label": `筛选${e.label}`,
					title: e.active ? `${e.label}：${e.summary || "已筛选"}` : `筛选${e.label}`
				}, [M("span", di, oe(e.triggerLabel || e.label), 1), r[1] ||= M("svg", {
					class: "tc-column-filter-icon",
					viewBox: "0 0 16 16",
					width: "14",
					height: "14",
					fill: "none",
					"aria-hidden": "true",
					focusable: "false"
				}, [M("path", {
					d: "M2 3h12L9.5 8.3V13l-3-1.5V8.3L2 3Z",
					stroke: "currentColor",
					"stroke-width": "1.4",
					"stroke-linejoin": "round"
				})], -1)], 10, ui)]),
				_: 1
			}), P(k(ci), null, {
				default: c(() => [P(k(si), {
					class: "tc-filter-popover list-filter-popover",
					"aria-label": `筛选${e.label}`,
					side: "bottom",
					align: "start",
					"side-offset": 6,
					"collision-padding": 10,
					"hide-when-detached": ""
				}, {
					default: c(() => [
						M("div", fi, "筛选" + oe(e.label), 1),
						o(t.$slots, "default", {}, void 0, !0),
						P(k(ri), {
							class: "tc-filter-popover-close list-filter-popover__close",
							"aria-label": `关闭${e.label}筛选`,
							title: "关闭筛选"
						}, {
							default: c(() => [...r[2] ||= [M("svg", {
								viewBox: "0 0 16 16",
								width: "16",
								height: "16",
								fill: "none",
								"aria-hidden": "true",
								focusable: "false"
							}, [M("path", {
								d: "m4 4 8 8M12 4l-8 8",
								stroke: "currentColor",
								"stroke-width": "1.5",
								"stroke-linecap": "round"
							})], -1)]]),
							_: 1
						}, 8, ["aria-label"])
					]),
					_: 3
				}, 8, ["aria-label"])]),
				_: 3
			})]),
			_: 3
		}, 8, ["open"]));
	}
}), [["__scopeId", "data-v-49f53dbd"]]);
export { Ve as _, ni as a, Pt as c, bt as d, yt as f, et as g, it as h, si as i, z as l, R as m, li as n, Yt as o, lt as p, ci as r, Jt as s, pi as t, Tt as u, I as v, _e as y };
