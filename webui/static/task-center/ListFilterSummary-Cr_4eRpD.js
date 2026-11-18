import { $ as e, A as t, B as n, C as r, D as i, E as a, G as o, I as s, J as c, K as l, L as u, M as d, N as f, O as p, P as m, Q as h, R as g, S as _, T as v, U as y, V as b, W as x, X as S, Z as C, _ as w, at as T, b as E, c as D, ct as ee, d as O, et as k, f as A, g as j, h as te, it as ne, j as M, k as re, l as ie, lt as ae, m as N, nt as oe, ot as se, p as P, q as ce, rt as F, s as le, st as ue, t as de, tt as I, u as fe, v as pe, w as me, x as he, y as L, z as ge } from "./_plugin-vue_export-helper-acNQneR4.js";
// node_modules/reka-ui/dist/shared/createContext.js
function _e(e, t) {
	let n = typeof e == "string" && !t ? `${e}Context` : t, i = Symbol(n);
	return [(t) => {
		let n = r(i, t);
		if (n || n === null) return n;
		throw Error(`Injection \`${i.toString()}\` not found. Component must be used within ${Array.isArray(e) ? `one of the following components: ${e.join(", ")}` : `\`${e}\``}`);
	}, (e) => (d(i, e), e)];
}
// node_modules/reka-ui/dist/shared/getActiveElement.js
function R() {
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
	return o() ? (ce(e, t), !0) : !1;
}
function be(e) {
	let t = !1, n, r = x(!0);
	return ((...i) => (t ||= (n = r.run(() => e(...i)), !0), n));
}
var z = typeof window < "u" && typeof document < "u";
typeof WorkerGlobalScope < "u" && globalThis instanceof WorkerGlobalScope;
var xe = (e) => e !== void 0, Se = Object.prototype.toString, Ce = (e) => Se.call(e) === "[object Object]", we = /* #__PURE__ */ Te();
function Te() {
	var e, t;
	return z && !!((e = window) != null && (e = e.navigator) != null && e.userAgent) && (/iP(?:ad|hone|od)/.test(window.navigator.userAgent) || ((t = window) == null || (t = t.navigator) == null ? void 0 : t.maxTouchPoints) > 2 && /iPad|Macintosh/.test(window?.navigator.userAgent));
}
function Ee(e) {
	return Array.isArray(e) ? e : [e];
}
function De(e) {
	return e || E();
}
function Oe(e) {
	if (!z) return e;
	let t = 0, n, r, i = () => {
		--t, r && t <= 0 && (r.stop(), n = void 0, r = void 0);
	};
	return ((...a) => (t += 1, r || (r = x(!0), n = r.run(() => e(...a))), ye(i), n));
}
function ke(e) {
	return l(e) ? c(new Proxy({}, {
		get(t, n, r) {
			return F(Reflect.get(e.value, n, r));
		},
		set(t, n, r) {
			return l(e.value[n]) && !l(r) ? e.value[n].value = r : e.value[n] = r, !0;
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
	})) : c(e);
}
function Ae(e) {
	return ke(A(e));
}
function je(e, ...t) {
	let n = t.flat(), r = n[0];
	return Ae(() => Object.fromEntries(typeof r == "function" ? Object.entries(k(e)).filter(([e, t]) => !r(I(t), e)) : Object.entries(k(e)).filter((e) => !n.includes(e[0]))));
}
function Me(e, t) {
	De(t) && i(e, t);
}
function Ne(e, t, n) {
	return g(e, t, {
		...n,
		immediate: !0
	});
}
// node_modules/@vueuse/core/dist/index.js
var Pe = z ? window : void 0;
z && window.document, z && window.navigator, z && window.location;
function Fe(e) {
	let t = I(e);
	return t?.$el ?? t;
}
function Ie(...e) {
	let t = (e, t, n, r) => (e.addEventListener(t, n, r), () => e.removeEventListener(t, n, r)), n = A(() => {
		let t = Ee(I(e[0])).filter((e) => e != null);
		return t.every((e) => typeof e != "string") ? t : void 0;
	});
	return Ne(() => [
		n.value?.map((e) => Fe(e)) ?? [Pe].filter((e) => e != null),
		Ee(I(n.value ? e[1] : e[0])),
		Ee(F(n.value ? e[2] : e[1])),
		I(n.value ? e[3] : e[2])
	], ([e, n, r, i], a, o) => {
		if (!e?.length || !n?.length || !r?.length) return;
		let s = Ce(i) ? { ...i } : i, c = e.flatMap((e) => n.flatMap((n) => r.map((r) => t(e, n, r, s))));
		o(() => {
			c.forEach((e) => e());
		});
	}, { flush: "post" });
}
function Le() {
	let e = h(!1), t = E();
	return t && p(() => {
		e.value = !0;
	}, t), e;
}
function Re(e) {
	return typeof e == "function" ? e : typeof e == "string" ? (t) => t.key === e : Array.isArray(e) ? (t) => e.includes(t.key) : () => !0;
}
function ze(...e) {
	let t, n, r = {};
	e.length === 3 ? (t = e[0], n = e[1], r = e[2]) : e.length === 2 ? typeof e[1] == "object" ? (t = !0, n = e[0], r = e[1]) : (t = e[0], n = e[1]) : (t = !0, n = e[0]);
	let { target: i = Pe, eventName: a = "keydown", passive: o = !1, dedupe: s = !1 } = r, c = Re(t);
	return Ie(i, a, (e) => {
		e.repeat && I(s) || c(e) && n(e);
	}, o);
}
function Be(e) {
	return JSON.parse(JSON.stringify(e));
}
function Ve(e, t, n, r = {}) {
	var i, o;
	let { clone: s = !1, passive: c = !1, eventName: l, deep: u = !1, defaultValue: d, shouldEmit: f } = r, p = E(), m = n || p?.emit || (p == null || (i = p.$emit) == null ? void 0 : i.bind(p)) || (p == null || (o = p.proxy) == null || (o = o.$emit) == null ? void 0 : o.bind(p?.proxy)), h = l;
	t ||= "modelValue", h ||= `update:${t.toString()}`;
	let _ = (e) => s ? typeof s == "function" ? s(e) : Be(e) : e, v = () => xe(e[t]) ? _(e[t]) : d, y = (e) => {
		f ? f(e) && m(h, e) : m(h, e);
	};
	if (c) {
		let n = S(v()), r = !1;
		return g(() => e[t], (e) => {
			r || (r = !0, n.value = _(e), a(() => r = !1));
		}), g(n, (n) => {
			!r && (n !== e[t] || u) && y(n);
		}, { deep: u }), n;
	}
	return A({
		get() {
			return v();
		},
		set(e) {
			y(e);
		}
	});
}
// node_modules/reka-ui/dist/shared/renderSlotFragments.js
function He(e) {
	return e ? e.flatMap((e) => e.type === ie ? He(e.children) : [e]) : [];
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
	let e = S(/* @__PURE__ */ new Map()), t = S(), n = A(() => {
		for (let t of e.value.values()) if (t) return !0;
		return !1;
	}), r = Ue({ scrollBody: S(!0) }), i = null, o = () => {
		document.body.style.paddingRight = "", document.body.style.marginRight = "", qe(document, Qe), document.documentElement.style.removeProperty("--scrollbar-width"), document.body.style.overflow = t.value ?? "", we && i?.(), t.value = void 0;
	};
	return g(n, (e, s) => {
		if (!z) return;
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
		c > 0 && (document.body.style.paddingRight = typeof u.padding == "number" ? `${u.padding}px` : String(u.padding), document.body.style.marginRight = typeof u.margin == "number" ? `${u.margin}px` : String(u.margin), document.documentElement.style.setProperty("--scrollbar-width", `${c}px`), document.body.style.overflow = "hidden"), we && (i = Ie(document, "touchmove", (e) => nt(e), { passive: !1 })), a(() => {
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
	let r = A({
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
	return A(() => e?.value || t.dir?.value || "ltr");
}
// node_modules/reka-ui/dist/shared/useEmitAsProps.js
function it(e) {
	let t = E(), n = t?.type.emits, r = {};
	return n?.length || console.warn(`No emitted event found. Please check component: ${t?.type.__name}`), n?.forEach((t) => {
		r[ae(ne(t))] = (...n) => e(t, ...n);
	}), r;
}
// node_modules/reka-ui/dist/shared/useFocusGuards.js
var at = 0;
function ot() {
	ge((e) => {
		if (!z) return;
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
function B() {
	let e = E(), n = S(), r = A(() => i());
	t(() => {
		r.value !== i() && oe(n);
	});
	function i() {
		return n.value && "$el" in n.value && ["#text", "#comment"].includes(n.value.$el.nodeName) ? n.value.$el.nextElementSibling : Fe(n);
	}
	let a = Object.assign({}, e.exposed), o = {};
	for (let t in e.props) Object.defineProperty(o, t, {
		enumerable: !0,
		configurable: !0,
		get: () => e.props[t]
	});
	if (Object.keys(a).length > 0) for (let e in a) Object.defineProperty(o, e, {
		enumerable: !0,
		configurable: !0,
		get: () => a[e]
	});
	Object.defineProperty(o, "$el", {
		enumerable: !0,
		configurable: !0,
		get: () => e.vnode.el
	}), e.exposed = o;
	function s(t) {
		if (n.value = t, t && (Object.defineProperty(o, "$el", {
			enumerable: !0,
			configurable: !0,
			get: () => t instanceof Element ? t : t.$el
		}), !(t instanceof Element) && !Object.hasOwn(t, "$el"))) {
			let n = t.$.exposed, r = Object.assign({}, o);
			for (let e in n) Object.defineProperty(r, e, {
				enumerable: !0,
				configurable: !0,
				get: () => n[e]
			});
			e.exposed = r;
		}
	}
	return {
		forwardRef: s,
		currentRef: n,
		currentElement: r
	};
}
// node_modules/reka-ui/dist/shared/useForwardProps.js
function ct(t) {
	let n = E(), r = Object.keys(n?.type.props ?? {}).reduce((e, t) => {
		let r = (n?.type.props[t]).default;
		return r !== void 0 && (e[t] = r), e;
	}, {}), i = e(t);
	return A(() => {
		let e = {}, t = n?.vnode.props ?? {};
		return Object.keys(t).forEach((n) => {
			e[ne(n)] = t[n];
		}), Object.keys({
			...r,
			...e
		}).reduce((e, t) => (i.value[t] !== void 0 && (e[t] = i.value[t]), e), {});
	});
}
// node_modules/reka-ui/dist/shared/useForwardPropsEmits.js
function lt(e, t) {
	let n = ct(e), r = t ? it(t) : {};
	return A(() => ({
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
	let t;
	g(() => Fe(e), (e) => {
		let n = !1;
		try {
			n = !!e?.closest("[popover]:not(:popover-open)");
		} catch {}
		e && !n ? t = vt(e) : t && t();
	}), re(() => {
		t && t();
	});
}
function bt(e, t = "reka") {
	if (e) return e;
	let n, r = Ue({ useId: void 0 });
	return n = r.useId ? r.useId() : u?.(), t ? `${t}-${n}` : n;
}
// node_modules/reka-ui/dist/shared/useSize.js
function xt(e) {
	let t = S(), n = A(() => t.value?.width ?? 0), r = A(() => t.value?.height ?? 0), i;
	return p(() => {
		let n = Fe(e);
		n ? (t.value = {
			width: n.offsetWidth,
			height: n.offsetHeight
		}, i = new ResizeObserver((e) => {
			if (!Array.isArray(e) || !e.length) return;
			let r = e[0], i, a;
			if ("borderBoxSize" in r) {
				let e = r.borderBoxSize, t = Array.isArray(e) ? e[0] : e;
				i = t.inlineSize, a = t.blockSize;
			} else i = n.offsetWidth, a = n.offsetHeight;
			t.value = {
				width: i,
				height: a
			};
		}), i.observe(n, { box: "border-box" })) : t.value = void 0;
	}), re(() => {
		i?.disconnect(), i = void 0;
	}), {
		width: n,
		height: r
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
function Ct(e, t) {
	let n = S({}), r = S("none"), i = S(e), o = e.value ? "mounted" : "unmounted", s, c = t.value?.ownerDocument.defaultView ?? Pe, { state: l, dispatch: u } = St(o, {
		mounted: {
			UNMOUNT: "unmounted",
			ANIMATION_OUT: "unmountSuspended"
		},
		unmountSuspended: {
			MOUNT: "mounted",
			ANIMATION_END: "unmounted"
		},
		unmounted: { MOUNT: "mounted" }
	}), d = (e) => {
		if (z) {
			let n = new CustomEvent(e, {
				bubbles: !1,
				cancelable: !1
			});
			t.value?.dispatchEvent(n);
		}
	};
	g(e, async (e, i) => {
		let o = i !== e;
		if (await a(), o) {
			let a = r.value, o = wt(t.value);
			e ? (u("MOUNT"), d("enter"), o === "none" && d("after-enter")) : o === "none" || o === "undefined" || n.value?.display === "none" ? (u("UNMOUNT"), d("leave"), d("after-leave")) : i && a !== o ? (u("ANIMATION_OUT"), d("leave")) : (u("UNMOUNT"), d("after-leave"));
		}
	}, { immediate: !0 });
	let f = (e) => {
		if (e.target !== t.value) return;
		let n = wt(t.value), r = n.includes(CSS.escape(e.animationName)), a = l.value === "mounted" ? "enter" : "leave";
		if (r && (d(`after-${a}`), u("ANIMATION_END"), !i.value)) {
			let e = t.value.style.animationFillMode;
			t.value.style.animationFillMode = "forwards", s = c?.setTimeout(() => {
				t.value?.style.animationFillMode === "forwards" && (t.value.style.animationFillMode = e);
			});
		}
		n === "none" && u("ANIMATION_END");
	}, p = (e) => {
		e.target === t.value && (r.value = wt(t.value));
	}, m = g(t, (e, t) => {
		e ? (n.value = getComputedStyle(e), e.addEventListener("animationstart", p), e.addEventListener("animationcancel", f), e.addEventListener("animationend", f)) : (u("ANIMATION_END"), s !== void 0 && c?.clearTimeout(s), t?.removeEventListener("animationstart", p), t?.removeEventListener("animationcancel", f), t?.removeEventListener("animationend", f));
	}, { immediate: !0 }), h = g(l, () => {
		let e = wt(t.value);
		r.value = l.value === "mounted" ? e : "none";
	});
	return re(() => {
		m(), h(), t.value && (t.value.removeEventListener("animationstart", p), t.value.removeEventListener("animationcancel", f), t.value.removeEventListener("animationend", f)), s !== void 0 && c?.clearTimeout(s);
	}), { isPresent: A(() => ["mounted", "unmountSuspended"].includes(l.value)) };
}
function wt(e) {
	return e && getComputedStyle(e).animationName || "none";
}
// node_modules/reka-ui/dist/Presence/Presence.js
var Tt = /*#__PURE__*/ L({
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
		let { present: r, forceMount: i } = k(e), a = S(), { isPresent: o } = Ct(r, a);
		n({ present: o });
		let s = t.default({ present: o.value });
		s = He(s || []);
		let c = E();
		if (s && s?.length > 1) {
			let e = c?.parent?.type.name ? `<${c.parent.type.name} />` : "component";
			throw Error([
				`Detected an invalid children for \`${e}\` for  \`Presence\` component.`,
				"",
				"Note: Presence works similarly to `v-if` directly, but it waits for animation/transition to finished before unmounting. So it expect only one direct child of valid VNode type.",
				"You can apply a few solutions:",
				["Provide a single child element so that `presence` directive attach correctly.", "Ensure the first child is an actual element instead of a raw text node or comment node."].map((e) => `  - ${e}`).join("\n")
			].join("\n"));
		}
		return () => i.value || r.value || o.value ? _(t.default({ present: o.value })[0], { ref: (e) => {
			let t = Fe(e);
			return t?.hasAttribute === void 0 || (t?.hasAttribute("data-reka-popper-content-wrapper") ? a.value = t.firstElementChild : a.value = t), t;
		} }) : null;
	}
}), Et = /*#__PURE__*/ L({
	name: "PrimitiveSlot",
	inheritAttrs: !1,
	setup(e, { attrs: t, slots: n }) {
		return () => {
			if (!n.default) return null;
			let e = He(n.default()), r = e.findIndex((e) => e.type !== D);
			if (r === -1) return e;
			let i = e[r];
			delete i.props?.ref;
			let a = i.props ? v(t, i.props) : t, o = O({
				...i,
				props: {}
			}, a);
			return e.length === 1 ? o : (e[r] = o, e);
		};
	}
}), Dt = [
	"area",
	"img",
	"input"
], V = /*#__PURE__*/ L({
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
		let r = e.asChild ? "template" : e.as;
		return typeof r == "string" && Dt.includes(r) ? () => _(r, t) : r === "template" ? () => _(Et, t, { default: n.default }) : () => _(e.as, t, { default: n.default });
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
function Mt(e, t, n = !0) {
	let r = S(!1), i = S(() => {});
	return ge((a) => {
		if (!z || !I(n)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			let a = n.target;
			if (t?.value && a) {
				if (jt(t.value, a)) o.removeEventListener("click", i.value), r.value = !1;
				else {
					if (n.target && !r.value) {
						let t = { originalEvent: n };
						function r() {
							ve(Ot, e, t);
						}
						n.pointerType === "touch" ? (o.removeEventListener("click", i.value), i.value = r, o.addEventListener("click", i.value, { once: !0 })) : r();
					} else o.removeEventListener("click", i.value);
					r.value = !1;
				}
			}
		}, c = window.setTimeout(() => {
			o.addEventListener("pointerdown", s);
		}, 0);
		a(() => {
			window.clearTimeout(c), o.removeEventListener("pointerdown", s), o.removeEventListener("click", i.value);
		});
	}), { onPointerDownCapture: () => {
		I(n) && (r.value = !0);
	} };
}
function Nt(e, t, n = !0) {
	let r = S(!1);
	return ge((i) => {
		if (!z || !I(n)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			if (!t?.value) return;
			await a(), await a();
			let i = n.target;
			t.value && i && !jt(t.value, i) && n.target && !r.value && ve(kt, e, { originalEvent: n });
		};
		o.addEventListener("focusin", s), i(() => o.removeEventListener("focusin", s));
	}), {
		onFocusCapture: () => {
			I(n) && (r.value = !0);
		},
		onBlurCapture: () => {
			I(n) && (r.value = !1);
		}
	};
}
// node_modules/reka-ui/dist/DismissableLayer/context.js
var H = /*#__PURE__*/ c({
	layersRoot: /* @__PURE__ */ new Set(),
	layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
	branches: /* @__PURE__ */ new Set()
}), Pt = /* @__PURE__ */ L({
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
		let n = e, r = t, { forwardRef: i, currentElement: o } = B(), s = A(() => o.value?.ownerDocument ?? globalThis.document), c = A(() => H.layersRoot), l = A(() => o.value ? Array.from(c.value).indexOf(o.value) : -1), u = A(() => H.layersWithOutsidePointerEventsDisabled.size > 0), d = A(() => {
			let e = Array.from(c.value), [t] = [...H.layersWithOutsidePointerEventsDisabled].slice(-1), n = e.indexOf(t);
			return l.value >= n;
		}), f = Mt(async (e) => {
			let t = [...H.branches].some((t) => t?.contains(e.target));
			n.present && d.value && !t && (r("pointerDownOutside", e), r("interactOutside", e), await a(), e.defaultPrevented || r("dismiss"));
		}, o, () => n.present), p = Nt((e) => {
			let t = [...H.branches].some((t) => t?.contains(e.target));
			n.present && !t && (r("focusOutside", e), r("interactOutside", e), e.defaultPrevented || r("dismiss"));
		}, o);
		return ze("Escape", (e) => {
			n.present && l.value === c.value.size - 1 && (r("escapeKeyDown", e), e.defaultPrevented || r("dismiss"));
		}, { target: () => s.value?.defaultView ?? globalThis.window }), g([
			o,
			() => n.disableOutsidePointerEvents,
			() => n.present
		], ([e, t, n], r, i) => {
			if (e && n && t) {
				let t = e.ownerDocument;
				Ke(t, e), H.layersWithOutsidePointerEventsDisabled.add(e), i(() => {
					H.layersWithOutsidePointerEventsDisabled.delete(e), qe(t, e);
				});
			}
		}, { immediate: !0 }), g([o, () => n.present], ([e, t], n, r) => {
			e && t && (c.value.add(e), r(() => {
				c.value.delete(e);
			}));
		}, { immediate: !0 }), ge((e) => {
			e(() => {
				o.value && (c.value.delete(o.value), H.layersWithOutsidePointerEventsDisabled.delete(o.value));
			});
		}), (t, n) => (M(), N(F(V), {
			ref: F(i),
			"as-child": e.asChild,
			as: e.as,
			"data-dismissable-layer": "",
			style: ue({ pointerEvents: u.value ? d.value ? "auto" : "none" : void 0 }),
			onFocusCapture: F(p).onFocusCapture,
			onBlurCapture: F(p).onBlurCapture,
			onPointerdownCapture: F(f).onPointerDownCapture
		}, {
			default: b(() => [m(t.$slots, "default")]),
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
	let n = R();
	for (let r of e) if (U(r, { select: t }), R() !== n) return !0;
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
function U(e, { select: t = !1 } = {}) {
	if (e && e.focus) {
		let n = R();
		e.focus({ preventScroll: !0 }), e !== n && qt(e) && t && e.select();
	}
}
// node_modules/reka-ui/dist/FocusScope/FocusScope.js
var Jt = /* @__PURE__ */ L({
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
		let n = e, r = t, { currentRef: i, currentElement: o } = B(), s = S(null), l = It(), u = /*#__PURE__*/ c({
			paused: !1,
			pause() {
				this.paused = !0;
			},
			resume() {
				this.paused = !1;
			}
		});
		ge((e) => {
			if (!z) return;
			let t = o.value;
			if (!n.trapped) return;
			let r = t?.ownerDocument ?? document, i = t ? t.getRootNode() : r;
			function a(e) {
				if (u.paused || !t) return;
				let n = e.target;
				t.contains(n) ? s.value = n : U(s.value, { select: !0 });
			}
			function c(e) {
				if (u.paused || !t) return;
				let n = e.relatedTarget;
				n !== null && (t.contains(n) || U(s.value, { select: !0 }));
			}
			function l(e) {
				let n = s.value;
				if (n === null || !e.some((e) => e.removedNodes.length > 0)) return;
				let r = R();
				r && t.contains(r) || t.contains(n) || U(t);
			}
			function d(e) {
				if (u.paused || !t) return;
				let n = e.composedPath()[0];
				Vt(t, n) || U(s.value, { select: !0 });
			}
			i.addEventListener("focusin", a), i.addEventListener("focusout", c), i !== r && r.addEventListener("focusin", d);
			let f = new MutationObserver(l);
			t && f.observe(t, {
				childList: !0,
				subtree: !0
			}), e(() => {
				i.removeEventListener("focusin", a), i.removeEventListener("focusout", c), i !== r && r.removeEventListener("focusin", d), f.disconnect();
			});
		});
		function d(e, t) {
			let n = new CustomEvent(Rt, Bt), i = (e) => r("mountAutoFocus", e);
			e.addEventListener(Rt, i), e.dispatchEvent(n), e.removeEventListener(Rt, i), n.defaultPrevented || (Ht(Wt(e), { select: !0 }), R() === t && U(e));
		}
		ge(async (e) => {
			let t = o.value;
			if (await a(), !t) return;
			n.present !== !1 && l.add(u);
			let i = R();
			!t.contains(i) && n.present !== !1 && d(t, i), e(() => {
				let e = new CustomEvent(zt, Bt), n = (e) => {
					r("unmountAutoFocus", e);
				};
				t.addEventListener(zt, n), t.dispatchEvent(e), t.setAttribute("data-focus-scope-unmounting", ""), setTimeout(() => {
					e.defaultPrevented || U(i ?? document.body, { select: !0 }), t.removeEventListener(zt, n), l.remove(u), t.removeAttribute("data-focus-scope-unmounting");
				}, 0);
			});
		}), g(() => n.present, async (e, t) => {
			if (!z) return;
			if (e === !1 && t === !0) {
				l.remove(u);
				return;
			}
			if (e !== !0 || t !== !1) return;
			l.add(u), await a();
			let n = o.value;
			if (!n) return;
			let r = R();
			n.contains(r) || d(n, r);
		});
		function f(e) {
			if (!n.loop && !n.trapped || u.paused) return;
			let t = e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey, r = R();
			if (t && r) {
				let t = e.currentTarget, [i, a] = Ut(t);
				i && a ? !e.shiftKey && r === a ? (e.preventDefault(), n.loop && U(i, { select: !0 })) : e.shiftKey && r === i && (e.preventDefault(), n.loop && U(a, { select: !0 })) : r === t && e.preventDefault();
			}
		}
		return (t, n) => (M(), N(F(V), {
			ref_key: "currentRef",
			ref: i,
			tabindex: "-1",
			"as-child": e.asChild,
			as: e.as,
			onKeydown: f
		}, {
			default: b(() => [m(t.$slots, "default")]),
			_: 3
		}, 8, ["as-child", "as"]));
	}
}), Yt = /* @__PURE__ */ L({
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
		let t = e, n = Ue({}), r = A(() => t.to ?? n.teleportTo?.value ?? "body"), i = Le();
		return (t, n) => F(i) || e.forceMount ? (M(), N(fe, {
			key: 0,
			to: r.value,
			disabled: e.disabled,
			defer: e.defer
		}, [m(t.$slots, "default")], 8, [
			"to",
			"disabled",
			"defer"
		])) : te("v-if", !0);
	}
}), [Xt, Zt] = /*#__PURE__*/ _e("PopperRoot"), Qt = /* @__PURE__ */ L({
	inheritAttrs: !1,
	__name: "PopperRoot",
	setup(e) {
		let t = S();
		return Zt({
			anchor: t,
			onAnchorChange: (e) => t.value = e
		}), (e, t) => m(e.$slots, "default");
	}
}), $t = /* @__PURE__ */ L({
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
		let t = e, { forwardRef: r, currentElement: i } = B(), a = Xt();
		return n(() => {
			a.onAnchorChange(t.reference ?? i.value);
		}), (t, n) => (M(), N(F(V), {
			ref: F(r),
			as: e.as,
			"as-child": e.asChild
		}, {
			default: b(() => [m(t.$slots, "default")]),
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
], W = Math.min, G = Math.max, an = Math.round, on = Math.floor, K = (e) => ({
	x: e,
	y: e
}), sn = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function cn(e, t, n) {
	return G(e, W(t, n));
}
function q(e, t) {
	return typeof e == "function" ? e(t) : e;
}
function J(e) {
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
function Y(e) {
	let t = e[0];
	return t === "t" || t === "b" ? "y" : "x";
}
function fn(e) {
	return un(Y(e));
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
	let i = ln(e), a = bn(J(e), n === "start", r);
	return i && (a = a.map((e) => e + "-" + i), t && (a = a.concat(a.map(hn)))), a;
}
function Sn(e) {
	let t = J(e);
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
	let { reference: r, floating: i } = e, a = Y(t), o = fn(t), s = dn(o), c = J(t), l = a === "y", u = r.x + r.width / 2 - i.width / 2, d = r.y + r.height / 2 - i.height / 2, f = r[s] / 2 - i[s] / 2, p;
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
	let { x: n, y: r, platform: i, rects: a, elements: o, strategy: s } = e, { boundary: c = "clippingAncestors", rootBoundary: l = "viewport", elementContext: u = "floating", altBoundary: d = !1, padding: f = 0 } = q(t, e), p = wn(f), m = o[d ? u === "floating" ? "reference" : "floating" : u], h = Tn(await i.getClippingRect({
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
		let { x: n, y: r, placement: i, rects: a, platform: o, elements: s, middlewareData: c } = t, { element: l, padding: u = 0 } = q(e, t) || {};
		if (l == null) return {};
		let d = wn(u), f = {
			x: n,
			y: r
		}, p = fn(i), m = dn(p), h = await o.getDimensions(l), g = p === "y", _ = g ? "top" : "left", v = g ? "bottom" : "right", y = g ? "clientHeight" : "clientWidth", b = a.reference[m] + a.reference[p] - f[p] - a.floating[m], x = f[p] - a.reference[p], S = await (o.getOffsetParent == null ? void 0 : o.getOffsetParent(l)), C = S ? S[y] : 0;
		C && await (o.isElement == null ? void 0 : o.isElement(S)) || (C = s.floating[y] || a.floating[m]);
		let w = b / 2 - x / 2, T = C / 2 - h[m] / 2 - 1, E = W(d[_], T), D = W(d[v], T), ee = C - h[m] - D, O = C / 2 - h[m] / 2 + w, k = cn(E, O, ee), A = !c.arrow && ln(i) != null && O !== k && a.reference[m] / 2 - (O < E ? E : D) - h[m] / 2 < 0, j = A ? O < E ? O - E : O - ee : 0;
		return {
			[p]: f[p] + j,
			data: {
				[p]: k,
				centerOffset: O - k - j,
				...A && { alignmentOffset: j }
			},
			reset: A
		};
	}
}), jn = function(e) {
	return e === void 0 && (e = {}), {
		name: "flip",
		options: e,
		async fn(t) {
			var n;
			let { placement: r, middlewareData: i, rects: a, initialPlacement: o, platform: s, elements: c } = t, { mainAxis: l = !0, crossAxis: u = !0, fallbackPlacements: d, fallbackStrategy: f = "bestFit", fallbackAxisSideDirection: p = "none", flipAlignment: m = !0, ...h } = q(e, t);
			if ((n = i.arrow) != null && n.alignmentOffset) return {};
			let g = J(r), _ = Y(o), v = J(o) === o, y = await (s.isRTL == null ? void 0 : s.isRTL(c.floating)), b = d || (v || !m ? [Sn(o)] : mn(o)), x = p !== "none";
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
				if (t && (u !== "alignment" || _ === Y(t) || T.every((e) => Y(e.placement) !== _ || e.overflows[0] > 0))) return {
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
								let t = Y(e.placement);
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
			let { rects: n, platform: r } = t, { strategy: i = "referenceHidden", ...a } = q(e, t);
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
	let { placement: n, platform: r, elements: i } = e, a = await (r.isRTL == null ? void 0 : r.isRTL(i.floating)), o = J(n), s = ln(n), c = Y(n) === "y", l = Fn.has(o) ? -1 : 1, u = a && c ? -1 : 1, d = q(t, e), { mainAxis: f, crossAxis: p, alignmentAxis: m } = typeof d == "number" ? {
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
			} }, ...l } = q(e, t), u = {
				x: n,
				y: r
			}, d = await a.detectOverflow(t, l), f = Y(i), p = un(f), m = u[p], h = u[f], g = (e, t) => cn(t + d[e === "y" ? "top" : "left"], t, t - d[e === "y" ? "bottom" : "right"]);
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
			let { x: n, y: r, placement: i, rects: a, middlewareData: o } = t, { offset: s = 0, mainAxis: c = !0, crossAxis: l = !0 } = q(e, t), u = {
				x: n,
				y: r
			}, d = Y(i), f = un(d), p = u[f], m = u[d], h = q(s, t), g = typeof h == "number" ? {
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
				let e = f === "y" ? "width" : "height", t = Fn.has(J(i)), n = a.reference[d] - a.floating[e] + (t && o.offset?.[d] || 0) + (t ? 0 : g.crossAxis), r = a.reference[d] + a.reference[e] + (t ? 0 : o.offset?.[d] || 0) - (t ? g.crossAxis : 0);
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
			let { placement: n, rects: r, platform: i, elements: a } = t, { apply: o = () => {}, ...s } = q(e, t), c = await i.detectOverflow(t, s), l = J(n), u = ln(n), d = Y(n) === "y", { width: f, height: p } = r.floating, m, h;
			l === "top" || l === "bottom" ? (m = l, h = u === (await (i.isRTL == null ? void 0 : i.isRTL(a.floating)) ? "start" : "end") ? "left" : "right") : (h = l, m = u === "end" ? "top" : "bottom");
			let g = p - c.top - c.bottom, _ = f - c.left - c.right, v = W(p - c[m], g), y = W(f - c[h], _), b = t.middlewareData.shift, x = !b, S = v, C = y;
			b != null && b.enabled.x && (C = _), b != null && b.enabled.y && (S = g), x && !u && (d ? C = f - 2 * G(c.left, c.right) : S = p - 2 * G(c.top, c.bottom)), await o({
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
function Hn(e) {
	return Un(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function X(e) {
	var t;
	return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function Z(e) {
	return ((Un(e) ? e.ownerDocument : e.document) || window.document)?.documentElement;
}
function Un(e) {
	return Vn() ? e instanceof Node || e instanceof X(e).Node : !1;
}
function Q(e) {
	return Vn() ? e instanceof Element || e instanceof X(e).Element : !1;
}
function Wn(e) {
	return Vn() ? e instanceof HTMLElement || e instanceof X(e).HTMLElement : !1;
}
function Gn(e) {
	return !Vn() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof X(e).ShadowRoot;
}
function Kn(e) {
	let { overflow: t, overflowX: n, overflowY: r, display: i } = $(e);
	return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && i !== "inline" && i !== "contents";
}
function qn(e) {
	return /^(table|td|th)$/.test(Hn(e));
}
function Jn(e) {
	try {
		if (e.matches(":popover-open")) return !0;
	} catch {}
	try {
		return e.matches(":modal");
	} catch {
		return !1;
	}
}
var Yn = /transform|translate|scale|rotate|perspective|filter/, Xn = /paint|layout|strict|content/, Zn = (e) => !!e && e !== "none", Qn;
function $n(e) {
	let t = Q(e) ? $(e) : e;
	return Zn(t.transform) || Zn(t.translate) || Zn(t.scale) || Zn(t.rotate) || Zn(t.perspective) || !tr() && (Zn(t.backdropFilter) || Zn(t.filter)) || Yn.test(t.willChange || "") || Xn.test(t.contain || "");
}
function er(e) {
	let t = ir(e);
	for (; Wn(t) && !nr(t);) {
		if ($n(t)) return t;
		if (Jn(t)) return null;
		t = ir(t);
	}
	return null;
}
function tr() {
	return Qn ??= typeof CSS < "u" && CSS.supports && CSS.supports("-webkit-backdrop-filter", "none"), Qn;
}
function nr(e) {
	return /^(html|body|#document)$/.test(Hn(e));
}
function $(e) {
	return X(e).getComputedStyle(e);
}
function rr(e) {
	return Q(e) ? {
		scrollLeft: e.scrollLeft,
		scrollTop: e.scrollTop
	} : {
		scrollLeft: e.scrollX,
		scrollTop: e.scrollY
	};
}
function ir(e) {
	if (Hn(e) === "html") return e;
	let t = e.assignedSlot || e.parentNode || Gn(e) && e.host || Z(e);
	return Gn(t) ? t.host : t;
}
function ar(e) {
	let t = ir(e);
	return nr(t) ? (e.ownerDocument || e).body : Wn(t) && Kn(t) ? t : ar(t);
}
function or(e, t, n) {
	t === void 0 && (t = []), n === void 0 && (n = !0);
	let r = ar(e), i = r === e.ownerDocument?.body, a = X(r);
	if (i) {
		let e = sr(a);
		return t.concat(a, a.visualViewport || [], Kn(r) ? r : [], e && n ? or(e) : []);
	}
	return t.concat(r, or(r, [], n));
}
function sr(e) {
	return e.parent && Object.getPrototypeOf(e.parent) ? e.frameElement : null;
}
// node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs
function cr(e) {
	let t = $(e), n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0, i = Wn(e), a = i ? e.offsetWidth : n, o = i ? e.offsetHeight : r, s = an(n) !== a || an(r) !== o;
	return s && (n = a, r = o), {
		width: n,
		height: r,
		$: s
	};
}
function lr(e) {
	return Q(e) ? e : e.contextElement;
}
function ur(e) {
	let t = lr(e);
	if (!Wn(t)) return K(1);
	let n = t.getBoundingClientRect(), { width: r, height: i, $: a } = cr(t), o = (a ? an(n.width) : n.width) / r, s = (a ? an(n.height) : n.height) / i;
	return o && Number.isFinite(o) || (o = 1), s && Number.isFinite(s) || (s = 1), {
		x: o,
		y: s
	};
}
var dr = /*#__PURE__*/ K(0);
function fr(e) {
	let t = X(e);
	return !tr() || !t.visualViewport ? dr : {
		x: t.visualViewport.offsetLeft,
		y: t.visualViewport.offsetTop
	};
}
function pr(e, t, n) {
	return t === void 0 && (t = !1), !!n && t && n === X(e);
}
function mr(e, t, n, r) {
	t === void 0 && (t = !1), n === void 0 && (n = !1);
	let i = e.getBoundingClientRect(), a = lr(e), o = K(1);
	t && (r ? Q(r) && (o = ur(r)) : o = ur(e));
	let s = pr(a, n, r) ? fr(a) : K(0), c = (i.left + s.x) / o.x, l = (i.top + s.y) / o.y, u = i.width / o.x, d = i.height / o.y;
	if (a && r) {
		let e = X(a), t = Q(r) ? X(r) : r, n = e, i = sr(n);
		for (; i && t !== n;) {
			let e = ur(i), t = i.getBoundingClientRect(), r = $(i), a = t.left + (i.clientLeft + parseFloat(r.paddingLeft)) * e.x, o = t.top + (i.clientTop + parseFloat(r.paddingTop)) * e.y;
			c *= e.x, l *= e.y, u *= e.x, d *= e.y, c += a, l += o, n = X(i), i = sr(n);
		}
	}
	return Tn({
		width: u,
		height: d,
		x: c,
		y: l
	});
}
function hr(e, t) {
	let n = rr(e).scrollLeft;
	return t ? t.left + n : mr(Z(e)).left + n;
}
function gr(e, t) {
	let n = e.getBoundingClientRect();
	return {
		x: n.left + t.scrollLeft - hr(e, n),
		y: n.top + t.scrollTop
	};
}
function _r(e) {
	let { elements: t, rect: n, offsetParent: r, strategy: i } = e, a = i === "fixed", o = Z(r), s = t ? Jn(t.floating) : !1;
	if (r === o || s && a) return n;
	let c = {
		scrollLeft: 0,
		scrollTop: 0
	}, l = K(1), u = K(0), d = Wn(r);
	if ((d || !a) && ((Hn(r) !== "body" || Kn(o)) && (c = rr(r)), d)) {
		let e = mr(r);
		l = ur(r), u.x = e.x + r.clientLeft, u.y = e.y + r.clientTop;
	}
	let f = o && !d && !a ? gr(o, c) : K(0);
	return {
		width: n.width * l.x,
		height: n.height * l.y,
		x: n.x * l.x - c.scrollLeft * l.x + u.x + f.x,
		y: n.y * l.y - c.scrollTop * l.y + u.y + f.y
	};
}
function vr(e) {
	return e.getClientRects ? Array.from(e.getClientRects()) : [];
}
function yr(e) {
	let t = rr(e), n = e.ownerDocument.body, r = G(e.scrollWidth, e.clientWidth, n.scrollWidth, n.clientWidth), i = G(e.scrollHeight, e.clientHeight, n.scrollHeight, n.clientHeight), a = -t.scrollLeft + hr(e), o = -t.scrollTop;
	return $(n).direction === "rtl" && (a += G(e.clientWidth, n.clientWidth) - r), {
		width: r,
		height: i,
		x: a,
		y: o
	};
}
var br = 25;
function xr(e, t, n) {
	n === void 0 && (n = "viewport");
	let r = n === "layoutViewport", i = X(e), a = Z(e), o = i.visualViewport, s = a.clientWidth, c = a.clientHeight, l = 0, u = 0;
	if (o) {
		let e = !tr() || t === "fixed";
		r ? e || (l = -o.offsetLeft, u = -o.offsetTop) : (s = o.width, c = o.height, e && (l = o.offsetLeft, u = o.offsetTop));
	}
	if (hr(a) <= 0) {
		let e = a.ownerDocument, t = e.body, n = getComputedStyle(t), r = e.compatMode === "CSS1Compat" && parseFloat(n.marginLeft) + parseFloat(n.marginRight) || 0, i = Math.abs(a.clientWidth - t.clientWidth - r), o = getComputedStyle(a).scrollbarGutter === "stable both-edges" ? i / 2 : i;
		o <= br && (s -= o);
	}
	return {
		width: s,
		height: c,
		x: l,
		y: u
	};
}
function Sr(e, t) {
	let n = mr(e, !0, t === "fixed"), r = n.top + e.clientTop, i = n.left + e.clientLeft, a = ur(e);
	return {
		width: e.clientWidth * a.x,
		height: e.clientHeight * a.y,
		x: i * a.x,
		y: r * a.y
	};
}
function Cr(e, t, n) {
	let r;
	if (t === "viewport" || t === "layoutViewport") r = xr(e, n, t);
	else if (t === "document") r = yr(Z(e));
	else if (Q(t)) r = Sr(t, n);
	else {
		let n = fr(e);
		r = {
			x: t.x - n.x,
			y: t.y - n.y,
			width: t.width,
			height: t.height
		};
	}
	return Tn(r);
}
function wr(e, t) {
	let n = t.get(e);
	if (n) return n;
	let r = or(e, [], !1).filter((e) => Q(e) && Hn(e) !== "body"), i = null, a = $(e).position === "fixed", o = a ? ir(e) : e;
	for (; Q(o) && !nr(o);) {
		let e = $(o), t = $n(o), n = i ? i.position : a ? "fixed" : "";
		!t && (n === "fixed" || n === "absolute" && e.position === "static") ? r = r.filter((e) => e !== o) : i = e, o = ir(o);
	}
	return t.set(e, r), r;
}
function Tr(e) {
	let { element: t, boundary: n, rootBoundary: r, strategy: i } = e, a = [...n === "clippingAncestors" ? Jn(t) ? [] : wr(t, this._c) : [].concat(n), r], o = Cr(t, a[0], i), s = o.top, c = o.right, l = o.bottom, u = o.left;
	for (let e = 1; e < a.length; e++) {
		let n = Cr(t, a[e], i);
		s = G(n.top, s), c = W(n.right, c), l = W(n.bottom, l), u = G(n.left, u);
	}
	return {
		width: c - u,
		height: l - s,
		x: u,
		y: s
	};
}
function Er(e) {
	let { width: t, height: n } = cr(e);
	return {
		width: t,
		height: n
	};
}
function Dr(e, t, n) {
	let r = Wn(t), i = Z(t), a = n === "fixed", o = mr(e, !0, a, t), s = {
		scrollLeft: 0,
		scrollTop: 0
	}, c = K(0);
	if ((r || !a) && ((Hn(t) !== "body" || Kn(i)) && (s = rr(t)), r)) {
		let e = mr(t, !0, a, t);
		c.x = e.x + t.clientLeft, c.y = e.y + t.clientTop;
	}
	!r && i && (c.x = hr(i));
	let l = i && !r && !a ? gr(i, s) : K(0);
	return {
		x: o.left + s.scrollLeft - c.x - l.x,
		y: o.top + s.scrollTop - c.y - l.y,
		width: o.width,
		height: o.height
	};
}
function Or(e) {
	return $(e).position === "static";
}
function kr(e, t) {
	if (!Wn(e) || $(e).position === "fixed") return null;
	if (t) return t(e);
	let n = e.offsetParent;
	return Z(e) === n && (n = n.ownerDocument.body), n;
}
function Ar(e, t) {
	let n = X(e);
	if (Jn(e)) return n;
	if (!Wn(e)) {
		let t = ir(e);
		for (; t && !nr(t);) {
			if (Q(t) && !Or(t)) return t;
			t = ir(t);
		}
		return n;
	}
	let r = kr(e, t);
	for (; r && qn(r) && Or(r);) r = kr(r, t);
	return r && nr(r) && Or(r) && !$n(r) ? n : r || er(e) || n;
}
var jr = async function(e) {
	let t = this.getOffsetParent || Ar, n = this.getDimensions, r = await n(e.floating);
	return {
		reference: Dr(e.reference, await t(e.floating), e.strategy),
		floating: {
			x: 0,
			y: 0,
			width: r.width,
			height: r.height
		}
	};
};
function Mr(e) {
	return $(e).direction === "rtl";
}
var Nr = {
	convertOffsetParentRelativeRectToViewportRelativeRect: _r,
	getDocumentElement: Z,
	getClippingRect: Tr,
	getOffsetParent: Ar,
	getElementRects: jr,
	getClientRects: vr,
	getDimensions: Er,
	getScale: ur,
	isElement: Q,
	isRTL: Mr
};
function Pr(e, t) {
	return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function Fr(e, t, n) {
	let r = null, i, a = Z(e);
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
			threshold: G(0, W(1, c)) || 1
		}, y = !0;
		function b(t) {
			let n = t[0].intersectionRatio;
			if (!Pr(l, e.getBoundingClientRect())) return s();
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
	let c = X(e), l = () => s(n);
	return c.addEventListener("resize", l), s(!0), () => {
		c.removeEventListener("resize", l), o();
	};
}
function Ir(e, t, n, r) {
	r === void 0 && (r = {});
	let { ancestorScroll: i = !0, ancestorResize: a = !0, elementResize: o = typeof ResizeObserver == "function", layoutShift: s = typeof IntersectionObserver == "function", animationFrame: c = !1 } = r, l = lr(e), u = i || a ? [...l ? or(l) : [], ...t ? or(t) : []] : [];
	u.forEach((e) => {
		i && e.addEventListener("scroll", n), a && e.addEventListener("resize", n);
	});
	let d = l && s ? Fr(l, n, a) : null, f = -1, p = null;
	o && (p = new ResizeObserver((e) => {
		let [r] = e;
		r && r.target === l && p && t && (p.unobserve(t), cancelAnimationFrame(f), f = requestAnimationFrame(() => {
			var e;
			(e = p) == null || e.observe(t);
		})), n();
	}), l && !c && p.observe(l), t && p.observe(t));
	let m, h = c ? mr(e) : null;
	c && g();
	function g() {
		let t = mr(e);
		h && !Pr(h, t) && n(), h = t, m = requestAnimationFrame(g);
	}
	return n(), () => {
		var e;
		u.forEach((e) => {
			i && e.removeEventListener("scroll", n), a && e.removeEventListener("resize", n);
		}), d?.(), (e = p) == null || e.disconnect(), p = null, c && cancelAnimationFrame(m);
	};
}
var Lr = Ln, Rr = Rn, zr = jn, Br = Bn, Vr = Pn, Hr = An, Ur = zn, Wr = (e, t, n) => {
	let r = /* @__PURE__ */ new Map(), i = n ?? {}, a = {
		...Nr,
		...i.platform,
		_c: r
	};
	return kn(e, t, {
		...i,
		platform: a
	});
};
// node_modules/@floating-ui/vue/dist/floating-ui.vue.mjs
function Gr(e) {
	return typeof e == "object" && !!e && "$el" in e;
}
function Kr(e) {
	if (Gr(e)) {
		let t = e.$el;
		return Un(t) && Hn(t) === "#comment" ? null : t;
	}
	return e;
}
function qr(e) {
	return {
		name: "arrow",
		options: e,
		fn(t) {
			let n = Kr(I(e.element));
			return n == null ? {} : Hr({
				element: n,
				padding: e.padding
			}).fn(t);
		}
	};
}
function Jr(e) {
	return typeof window > "u" ? 1 : (e.ownerDocument.defaultView || window).devicePixelRatio || 1;
}
function Yr(e, t) {
	let n = Jr(e);
	return Math.round(t * n) / n;
}
function Xr(e, t, n) {
	n === void 0 && (n = {});
	let r = n.whileElementsMounted, i = A(() => I(n.open) ?? !0), a = A(() => I(n.middleware)), s = A(() => I(n.placement) ?? "bottom"), c = A(() => I(n.strategy) ?? "absolute"), l = A(() => I(n.transform) ?? !0), u = A(() => Kr(e.value)), d = A(() => Kr(t.value)), f = S(0), p = S(0), m = S(c.value), _ = S(s.value), v = h({}), y = S(!1), b = A(() => {
		let e = {
			position: m.value,
			left: "0",
			top: "0"
		};
		if (!d.value) return e;
		let t = Yr(d.value, f.value), n = Yr(d.value, p.value);
		return l.value ? {
			...e,
			transform: "translate(" + t + "px, " + n + "px)",
			...Jr(d.value) >= 1.5 && { willChange: "transform" }
		} : {
			position: m.value,
			left: t + "px",
			top: n + "px"
		};
	}), x;
	function w() {
		if (u.value == null || d.value == null) return;
		let e = i.value;
		Wr(u.value, d.value, {
			middleware: a.value,
			placement: s.value,
			strategy: c.value
		}).then((t) => {
			f.value = t.x, p.value = t.y, m.value = t.strategy, _.value = t.placement, v.value = t.middlewareData, y.value = e !== !1;
		});
	}
	function T() {
		typeof x == "function" && (x(), x = void 0);
	}
	function E() {
		T(), r === void 0 ? w() : u.value != null && d.value != null && (x = r(u.value, d.value, w));
	}
	function D() {
		i.value || (y.value = !1);
	}
	return g([
		a,
		s,
		c,
		i
	], w, { flush: "sync" }), g([u, d], E, { flush: "sync" }), g(i, D, { flush: "sync" }), o() && ce(T), {
		x: C(f),
		y: C(p),
		strategy: C(m),
		placement: C(_),
		middlewareData: C(v),
		isPositioned: C(y),
		floatingStyles: b,
		update: w
	};
}
// node_modules/reka-ui/dist/Popper/PopperContent.js
var Zr = ["dir"], Qr = {
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
}, [$r, ei] = /*#__PURE__*/ _e("PopperContent"), ti = /* @__PURE__ */ L({
	inheritAttrs: !1,
	__name: "PopperContent",
	props: /* @__PURE__ */ me({
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
	}, { ...Qr }),
	emits: ["placed"],
	setup(e, { emit: t }) {
		let r = e, i = t, a = Xt(), { forwardRef: o, currentElement: s } = B(), c = rt(A(() => r.dir)), l = S(), u = S(), { width: d, height: f } = xt(u), p = A(() => r.side + (r.align === "center" ? "" : `-${r.align}`)), h = A(() => typeof r.collisionPadding == "number" ? r.collisionPadding : {
			top: 0,
			right: 0,
			bottom: 0,
			left: 0,
			...r.collisionPadding
		}), g = A(() => Array.isArray(r.collisionBoundary) ? r.collisionBoundary : [r.collisionBoundary]), _ = A(() => ({
			padding: h.value,
			boundary: g.value.filter(en),
			altBoundary: g.value.length > 0
		})), x = A(() => ({
			mainAxis: r.sideFlip,
			crossAxis: r.alignFlip
		})), C = A(() => [
			Lr({
				mainAxis: r.sideOffset + f.value,
				alignmentAxis: r.alignOffset
			}),
			r.prioritizePosition && r.avoidCollisions && zr({
				..._.value,
				...x.value
			}),
			r.avoidCollisions && Rr({
				mainAxis: !0,
				crossAxis: !!r.prioritizePosition,
				limiter: r.sticky === "partial" ? Ur() : void 0,
				..._.value
			}),
			!r.prioritizePosition && r.avoidCollisions && zr({
				..._.value,
				...x.value
			}),
			Br({
				..._.value,
				apply: ({ elements: e, rects: t, availableWidth: n, availableHeight: r }) => {
					let { width: i, height: a } = t.reference, o = e.floating.style;
					o.setProperty("--reka-popper-available-width", `${n}px`), o.setProperty("--reka-popper-available-height", `${r}px`), o.setProperty("--reka-popper-anchor-width", `${i}px`), o.setProperty("--reka-popper-anchor-height", `${a}px`);
				}
			}),
			u.value && qr({
				element: u.value,
				padding: r.arrowPadding
			}),
			tn({
				arrowWidth: d.value,
				arrowHeight: f.value,
				dir: c.value
			}),
			r.hideWhenDetached && Vr({
				strategy: "referenceHidden",
				..._.value
			})
		]), { floatingStyles: w, placement: T, isPositioned: E, middlewareData: D, update: ee } = Xr(A(() => r.reference ?? a.anchor.value), l, {
			strategy: r.positionStrategy,
			placement: p,
			whileElementsMounted: (...e) => Ir(...e, {
				layoutShift: !r.disableUpdateOnLayoutShift,
				animationFrame: r.updatePositionStrategy === "always"
			}),
			middleware: C
		}), O = A(() => nn(T.value)[0]), k = A(() => nn(T.value)[1]);
		n(() => {
			E.value && i("placed");
		});
		let te = A(() => {
			let e = D.value.arrow?.centerOffset !== 0;
			return r.hideShiftedArrow && e;
		}), ne = S("");
		return ge(() => {
			s.value && (ne.value = window.getComputedStyle(s.value).zIndex);
		}), ei({
			placedSide: O,
			onArrowChange: (e) => u.value = e,
			arrowX: A(() => D.value.arrow?.x ?? 0),
			arrowY: A(() => D.value.arrow?.y ?? 0),
			shouldHideArrow: te
		}), (e, t) => (M(), j("div", {
			ref_key: "floatingRef",
			ref: l,
			"data-reka-popper-content-wrapper": "",
			dir: F(c),
			style: ue({
				...F(w),
				transform: F(E) ? F(w).transform : "translate(0, -200%)",
				minWidth: "max-content",
				zIndex: ne.value,
				"--reka-popper-transform-origin": [F(D).transformOrigin?.x, F(D).transformOrigin?.y].join(" "),
				...F(D).hide?.referenceHidden && {
					visibility: "hidden",
					pointerEvents: "none"
				}
			})
		}, [r.memoDependencies ? y([
			r.asChild,
			r.as,
			O.value,
			k.value,
			F(E),
			...Object.values(e.$attrs),
			...r.memoDependencies
		], () => (M(), N(F(V), v({
			key: 0,
			ref: F(o)
		}, e.$attrs, {
			"as-child": r.asChild,
			as: r.as,
			"data-side": O.value,
			"data-align": k.value,
			style: { animation: F(E) ? void 0 : "none" }
		}), {
			default: b(() => [m(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"style"
		])), t, 0) : (M(), N(F(V), v({
			key: 1,
			ref: F(o)
		}, e.$attrs, {
			"as-child": r.asChild,
			as: r.as,
			"data-side": O.value,
			"data-align": k.value,
			dir: F(c),
			style: { animation: F(E) ? void 0 : "none" }
		}), {
			default: b(() => [m(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"dir",
			"style"
		]))], 12, Zr));
	}
}), [ni, ri] = /*#__PURE__*/ _e("PopoverRoot"), ii = /* @__PURE__ */ L({
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
		let n = e, r = t, { modal: i } = k(n), a = Ve(n, "open", r, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		});
		return ri({
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
		}), (e, t) => (M(), N(F(Qt), null, {
			default: b(() => [m(e.$slots, "default", {
				open: F(a),
				close: () => a.value = !1
			})]),
			_: 3
		}));
	}
}), ai = /* @__PURE__ */ L({
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
		B();
		let n = ni();
		return (r, i) => (M(), N(F(V), {
			type: e.as === "button" ? "button" : void 0,
			as: e.as,
			"as-child": t.asChild,
			onClick: i[0] ||= (e) => F(n).onOpenChange(!1)
		}, {
			default: b(() => [m(r.$slots, "default")]),
			_: 3
		}, 8, [
			"type",
			"as",
			"as-child"
		]));
	}
}), oi = /* @__PURE__ */ L({
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
		let n = e, r = t, i = ct(je(n, "trapFocus", "disableOutsidePointerEvents")), { forwardRef: a } = B(), o = ni();
		return ot(), (t, n) => (M(), N(F(Jt), {
			"as-child": "",
			loop: "",
			trapped: e.trapFocus,
			onMountAutoFocus: n[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: n[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: b(() => [pe(F(Pt), {
				"as-child": "",
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				onPointerDownOutside: n[0] ||= (e) => r("pointerDownOutside", e),
				onInteractOutside: n[1] ||= (e) => r("interactOutside", e),
				onEscapeKeyDown: n[2] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: n[3] ||= (e) => r("focusOutside", e),
				onDismiss: n[4] ||= (e) => F(o).onOpenChange(!1)
			}, {
				default: b(() => [pe(F(ti), v(F(i), {
					id: F(o).contentId,
					ref: F(a),
					"data-state": F(o).open.value ? "open" : "closed",
					"aria-labelledby": F(o).triggerId,
					style: {
						"--reka-popover-content-transform-origin": "var(--reka-popper-transform-origin)",
						"--reka-popover-content-available-width": "var(--reka-popper-available-width)",
						"--reka-popover-content-available-height": "var(--reka-popper-available-height)",
						"--reka-popover-trigger-width": "var(--reka-popper-anchor-width)",
						"--reka-popover-trigger-height": "var(--reka-popper-anchor-height)"
					},
					role: "dialog"
				}), {
					default: b(() => [m(t.$slots, "default")]),
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
}), si = /* @__PURE__ */ L({
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
		let n = e, r = t, i = ni(), a = S(!1);
		et(!0);
		let o = lt(n, r), { forwardRef: s, currentElement: c } = B();
		return yt(c), (e, t) => (M(), N(oi, v(F(o), {
			ref: F(s),
			"trap-focus": F(i).open.value,
			"disable-outside-pointer-events": "",
			onCloseAutoFocus: t[0] ||= le((e) => {
				r("closeAutoFocus", e), a.value || F(i).triggerElement.value?.focus();
			}, ["prevent"]),
			onPointerDownOutside: t[1] ||= (e) => {
				r("pointerDownOutside", e);
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0, i = t.button === 2 || n;
				a.value = i;
			},
			onFocusOutside: t[2] ||= le(() => {}, ["prevent"])
		}), {
			default: b(() => [m(e.$slots, "default")]),
			_: 3
		}, 16, ["trap-focus"]));
	}
}), ci = /* @__PURE__ */ L({
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
		let n = e, r = t, i = ni(), a = S(!1), o = S(!1), s = lt(n, r);
		return (e, t) => (M(), N(oi, v(F(s), {
			"trap-focus": !1,
			"disable-outside-pointer-events": !1,
			onCloseAutoFocus: t[0] ||= (e) => {
				r("closeAutoFocus", e), e.defaultPrevented || (a.value || F(i).triggerElement.value?.focus(), e.preventDefault()), a.value = !1, o.value = !1;
			},
			onInteractOutside: t[1] ||= async (e) => {
				r("interactOutside", e), e.defaultPrevented || (a.value = !0, e.detail.originalEvent.type === "pointerdown" && (o.value = !0));
				let t = e.target;
				F(i).triggerElement.value?.contains(t) && e.preventDefault(), e.detail.originalEvent.type === "focusin" && o.value && e.preventDefault();
			}
		}), {
			default: b(() => [m(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), li = /* @__PURE__ */ L({
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
		let n = e, r = t, i = ni(), a = lt(n, r), { forwardRef: o } = B();
		return i.contentId ||= bt(void 0, "reka-popover-content"), (t, n) => (M(), N(F(Tt), { present: e.forceMount || F(i).open.value }, {
			default: b(() => [F(i).modal.value ? (M(), N(si, v({ key: 0 }, F(a), { ref: F(o) }), {
				default: b(() => [m(t.$slots, "default")]),
				_: 3
			}, 16)) : (M(), N(ci, v({ key: 1 }, F(a), { ref: F(o) }), {
				default: b(() => [m(t.$slots, "default")]),
				_: 3
			}, 16))]),
			_: 3
		}, 8, ["present"]));
	}
}), ui = /* @__PURE__ */ L({
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
		return (e, n) => (M(), N(F(Yt), se(he(t)), {
			default: b(() => [m(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), di = /* @__PURE__ */ L({
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
		let t = e, n = ni(), { forwardRef: r, currentElement: i } = B();
		return n.triggerId ||= bt(void 0, "reka-popover-trigger"), n.contentId ||= bt(void 0, "reka-popover-content"), p(() => {
			n.triggerElement.value = i.value;
		}), (i, a) => (M(), N(s(F(n).hasCustomAnchor.value ? F(V) : F($t)), { "as-child": "" }, {
			default: b(() => [pe(F(V), {
				id: F(n).triggerId,
				ref: F(r),
				type: e.as === "button" ? "button" : void 0,
				"aria-haspopup": "dialog",
				"aria-expanded": F(n).open.value,
				"aria-controls": F(n).open.value ? F(n).contentId : void 0,
				"data-state": F(n).open.value ? "open" : "closed",
				as: e.as,
				"as-child": t.asChild,
				onClick: F(n).onOpenToggle
			}, {
				default: b(() => [m(i.$slots, "default")]),
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
}), fi = [
	"data-active",
	"aria-label",
	"title"
], pi = { class: "tc-column-filter-label" }, mi = { class: "tc-filter-popover-heading list-filter-popover__heading" }, hi = /*#__PURE__*/ de(/* @__PURE__ */ L({
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
		return (t, r) => (M(), N(F(ii), {
			open: e.open,
			modal: !1,
			"onUpdate:open": r[0] ||= (e) => n("update:open", e)
		}, {
			default: b(() => [pe(F(di), { "as-child": "" }, {
				default: b(() => [P("button", {
					type: "button",
					class: T(["tc-column-filter-trigger", { "is-active": e.active }]),
					"data-active": e.active ? "" : void 0,
					"aria-label": `筛选${e.label}`,
					title: e.active ? `${e.label}：${e.summary || "已筛选"}` : `筛选${e.label}`
				}, [P("span", pi, ee(e.triggerLabel || e.label), 1), r[1] ||= P("svg", {
					class: "tc-column-filter-icon",
					viewBox: "0 0 16 16",
					width: "14",
					height: "14",
					fill: "none",
					"aria-hidden": "true",
					focusable: "false"
				}, [P("path", {
					d: "M2 3h12L9.5 8.3V13l-3-1.5V8.3L2 3Z",
					stroke: "currentColor",
					"stroke-width": "1.4",
					"stroke-linejoin": "round"
				})], -1)], 10, fi)]),
				_: 1
			}), pe(F(ui), null, {
				default: b(() => [pe(F(li), {
					class: "tc-filter-popover list-filter-popover",
					"aria-label": `筛选${e.label}`,
					side: "bottom",
					align: "start",
					"side-offset": 6,
					"collision-padding": 10,
					"hide-when-detached": ""
				}, {
					default: b(() => [
						P("div", mi, "筛选" + ee(e.label), 1),
						m(t.$slots, "default", {}, void 0, !0),
						pe(F(ai), {
							class: "tc-filter-popover-close list-filter-popover__close",
							"aria-label": `关闭${e.label}筛选`,
							title: "关闭筛选"
						}, {
							default: b(() => [...r[2] ||= [P("svg", {
								viewBox: "0 0 16 16",
								width: "16",
								height: "16",
								fill: "none",
								"aria-hidden": "true",
								focusable: "false"
							}, [P("path", {
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
}), [["__scopeId", "data-v-49f53dbd"]]), gi = ["title"], _i = {
	key: 0,
	class: "list-cell-secondary"
}, vi = /*#__PURE__*/ de(/* @__PURE__ */ L({
	__name: "ListCell",
	props: {
		text: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(e) {
		return (t, n) => (M(), j("div", {
			class: T(["list-cell", `list-cell--${e.tone}`]),
			title: e.title ?? [e.text, e.secondary].filter(Boolean).join(" · ")
		}, [P("div", { class: T(["list-cell-primary", { "list-cell-single": !!e.secondary }]) }, [m(t.$slots, "default", {}, () => [w(ee(e.text), 1)], !0)], 2), e.secondary ? (M(), j("div", _i, ee(e.secondary), 1)) : te("", !0)], 10, gi));
	}
}), [["__scopeId", "data-v-5767b82c"]]), yi = ["aria-label"], bi = [
	"aria-label",
	"title",
	"onClick"
], xi = /*#__PURE__*/ de(/* @__PURE__ */ L({
	__name: "ListFilterSummary",
	props: {
		items: {},
		label: { default: "已应用筛选" }
	},
	emits: ["remove"],
	setup(e, { emit: t }) {
		let n = t;
		return (t, r) => e.items.length ? (M(), j("div", {
			key: 0,
			class: "list-filter-summary",
			role: "group",
			"aria-label": e.label
		}, [(M(!0), j(ie, null, f(e.items, (e) => (M(), j("button", {
			key: e.key,
			type: "button",
			class: "list-filter-chip",
			"aria-label": e.removeLabel,
			title: e.title || e.label,
			onClick: (t) => n("remove", e.key)
		}, [P("span", null, ee(e.label), 1), r[0] ||= P("span", { "aria-hidden": "true" }, "×", -1)], 8, bi))), 128))], 8, yi)) : te("", !0);
	}
}), [["__scopeId", "data-v-9c3f6cac"]]);
export { it as _, ui as a, R as b, Yt as c, V as d, Tt as f, B as g, lt as h, di as i, Jt as l, yt as m, vi as n, li as o, bt as p, hi as r, ii as s, xi as t, Pt as u, et as v, _e as x, Ve as y };
