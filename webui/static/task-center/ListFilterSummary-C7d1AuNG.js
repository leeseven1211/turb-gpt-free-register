import { A as e, B as t, C as n, D as r, E as i, F as a, G as o, H as s, I as c, J as l, L as u, M as d, N as f, O as p, P as m, Q as h, R as g, S as _, T as v, U as y, V as b, W as x, X as S, Y as C, Z as w, _ as T, at as E, ct as ee, d as D, dt as O, et as k, f as te, ft as A, g as j, h as M, it as ne, j as re, k as N, l as ie, lt as ae, m as P, nt as oe, ot as se, p as ce, pt as le, q as ue, rt as de, st as F, t as fe, tt as pe, u as me, ut as he, v as I, w as ge, x as _e } from "./_plugin-vue_export-helper-BSZsFlS8.js";
// node_modules/reka-ui/dist/shared/createContext.js
function ve(e, t) {
	let n = typeof e == "string" && !t ? `${e}Context` : t, i = Symbol(n);
	return [(t) => {
		let n = r(i, t);
		if (n || n === null) return n;
		throw Error(`Injection \`${i.toString()}\` not found. Component must be used within ${Array.isArray(e) ? `one of the following components: ${e.join(", ")}` : `\`${e}\``}`);
	}, (e) => (c(i, e), e)];
}
// node_modules/reka-ui/dist/shared/getActiveElement.js
function L() {
	let e = document.activeElement;
	if (e == null) return null;
	for (; e != null && e.shadowRoot != null && e.shadowRoot.activeElement != null;) e = e.shadowRoot.activeElement;
	return e;
}
// node_modules/reka-ui/dist/shared/handleAndDispatchCustomEvent.js
function ye(e, t, n) {
	let r = n.originalEvent.target, i = new CustomEvent(e, {
		bubbles: !1,
		cancelable: !0,
		detail: n
	});
	t && r.addEventListener(e, t, { once: !0 }), r.dispatchEvent(i);
}
// node_modules/@vueuse/shared/dist/index.js
function be(e, t) {
	return C() ? (w(e, t), !0) : !1;
}
function xe(e) {
	let t = !1, n, r = l(!0);
	return ((...i) => (t ||= (n = r.run(() => e(...i)), !0), n));
}
var R = typeof window < "u" && typeof document < "u";
typeof WorkerGlobalScope < "u" && globalThis instanceof WorkerGlobalScope;
var Se = (e) => e !== void 0, Ce = Object.prototype.toString, we = (e) => Ce.call(e) === "[object Object]", Te = /* #__PURE__ */ Ee();
function Ee() {
	var e, t;
	return R && !!((e = window) != null && (e = e.navigator) != null && e.userAgent) && (/iP(?:ad|hone|od)/.test(window.navigator.userAgent) || ((t = window) == null || (t = t.navigator) == null ? void 0 : t.maxTouchPoints) > 2 && /iPad|Macintosh/.test(window?.navigator.userAgent));
}
function De(e) {
	return Array.isArray(e) ? e : [e];
}
function Oe(e) {
	return e || ge();
}
function ke(e) {
	if (!R) return e;
	let t = 0, n, r, i = () => {
		--t, r && t <= 0 && (r.stop(), n = void 0, r = void 0);
	};
	return ((...a) => (t += 1, r || (r = l(!0), n = r.run(() => e(...a))), be(i), n));
}
function Ae(e) {
	return S(e) ? h(new Proxy({}, {
		get(t, n, r) {
			return F(Reflect.get(e.value, n, r));
		},
		set(t, n, r) {
			return S(e.value[n]) && !S(r) ? e.value[n].value = r : e.value[n] = r, !0;
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
	})) : h(e);
}
function je(e) {
	return Ae(P(e));
}
function Me(e, ...t) {
	let n = t.flat(), r = n[0];
	return je(() => Object.fromEntries(typeof r == "function" ? Object.entries(ne(e)).filter(([e, t]) => !r(E(t), e)) : Object.entries(ne(e)).filter((e) => !n.includes(e[0]))));
}
function Ne(e, t) {
	Oe(t) && re(e, t);
}
function Pe(e, t, n) {
	return s(e, t, {
		...n,
		immediate: !0
	});
}
// node_modules/@vueuse/core/dist/index.js
var Fe = R ? window : void 0;
R && window.document, R && window.navigator, R && window.location;
function Ie(e) {
	let t = E(e);
	return t?.$el ?? t;
}
function Le(...e) {
	let t = (e, t, n, r) => (e.addEventListener(t, n, r), () => e.removeEventListener(t, n, r)), n = P(() => {
		let t = De(E(e[0])).filter((e) => e != null);
		return t.every((e) => typeof e != "string") ? t : void 0;
	});
	return Pe(() => [
		n.value?.map((e) => Ie(e)) ?? [Fe].filter((e) => e != null),
		De(E(n.value ? e[1] : e[0])),
		De(F(n.value ? e[2] : e[1])),
		E(n.value ? e[3] : e[2])
	], ([e, n, r, i], a, o) => {
		if (!e?.length || !n?.length || !r?.length) return;
		let s = we(i) ? { ...i } : i, c = e.flatMap((e) => n.flatMap((n) => r.map((r) => t(e, n, r, s))));
		o(() => {
			c.forEach((e) => e());
		});
	}, { flush: "post" });
}
function Re() {
	let e = oe(!1), t = ge();
	return t && d(() => {
		e.value = !0;
	}, t), e;
}
function ze(e) {
	return typeof e == "function" ? e : typeof e == "string" ? (t) => t.key === e : Array.isArray(e) ? (t) => e.includes(t.key) : () => !0;
}
function Be(...e) {
	let t, n, r = {};
	e.length === 3 ? (t = e[0], n = e[1], r = e[2]) : e.length === 2 ? typeof e[1] == "object" ? (t = !0, n = e[0], r = e[1]) : (t = e[0], n = e[1]) : (t = !0, n = e[0]);
	let { target: i = Fe, eventName: a = "keydown", passive: o = !1, dedupe: s = !1 } = r, c = ze(t);
	return Le(i, a, (e) => {
		e.repeat && E(s) || c(e) && n(e);
	}, o);
}
function Ve(e) {
	return JSON.parse(JSON.stringify(e));
}
function He(t, n, r, i = {}) {
	var a, o;
	let { clone: c = !1, passive: l = !1, eventName: u, deep: d = !1, defaultValue: f, shouldEmit: p } = i, m = ge(), h = r || m?.emit || (m == null || (a = m.$emit) == null ? void 0 : a.bind(m)) || (m == null || (o = m.proxy) == null || (o = o.$emit) == null ? void 0 : o.bind(m?.proxy)), g = u;
	n ||= "modelValue", g ||= `update:${n.toString()}`;
	let _ = (e) => c ? typeof c == "function" ? c(e) : Ve(e) : e, v = () => Se(t[n]) ? _(t[n]) : f, y = (e) => {
		p ? p(e) && h(g, e) : h(g, e);
	};
	if (l) {
		let r = k(v()), i = !1;
		return s(() => t[n], (t) => {
			i || (i = !0, r.value = _(t), e(() => i = !1));
		}), s(r, (e) => {
			!i && (e !== t[n] || d) && y(e);
		}, { deep: d }), r;
	}
	return P({
		get() {
			return v();
		},
		set(e) {
			y(e);
		}
	});
}
// node_modules/reka-ui/dist/shared/renderSlotFragments.js
function Ue(e) {
	return e ? e.flatMap((e) => e.type === D ? Ue(e.children) : [e]) : [];
}
// node_modules/reka-ui/dist/ConfigProvider/ConfigProvider.js
var [We, Ge] = /*#__PURE__*/ ve("ConfigProvider"), Ke = /* @__PURE__ */ new WeakMap();
function qe(e, t) {
	let n = Ke.get(e);
	n || (n = {
		owners: /* @__PURE__ */ new Set(),
		original: e.body.style.pointerEvents
	}, Ke.set(e, n)), n.owners.add(t), e.body.style.pointerEvents = "none";
}
function Je(e, t) {
	let n = Ke.get(e);
	n?.owners.delete(t) && n.owners.size === 0 && (Ke.delete(e), e.body.style.pointerEvents = n.original);
}
// node_modules/defu/dist/defu.mjs
function Ye(e) {
	if (typeof e != "object" || !e) return !1;
	let t = Object.getPrototypeOf(e);
	return t !== null && t !== Object.prototype && Object.getPrototypeOf(t) !== null || Symbol.iterator in e ? !1 : Symbol.toStringTag in e ? Object.prototype.toString.call(e) === "[object Module]" : !0;
}
function Xe(e, t, n = ".", r) {
	if (!Ye(t)) return Xe(e, {}, n, r);
	let i = { ...t };
	for (let t of Object.keys(e)) {
		if (t === "__proto__" || t === "constructor") continue;
		let a = e[t];
		a != null && (r && r(i, t, a, n) || (i[t] = Array.isArray(a) && Array.isArray(i[t]) ? [...a, ...i[t]] : Ye(a) && Ye(i[t]) ? Xe(a, i[t], (n ? `${n}.` : "") + t.toString(), r) : a));
	}
	return i;
}
function Ze(e) {
	return (...t) => t.reduce((t, n) => Xe(t, n, "", e), {});
}
var Qe = Ze(), $e = Symbol("useBodyScrollLock"), et = ke(() => {
	let t = k(/* @__PURE__ */ new Map()), n = k(), r = P(() => {
		for (let e of t.value.values()) if (e) return !0;
		return !1;
	}), i = We({ scrollBody: k(!0) }), a = null, o = () => {
		document.body.style.paddingRight = "", document.body.style.marginRight = "", Je(document, $e), document.documentElement.style.removeProperty("--scrollbar-width"), document.body.style.overflow = n.value ?? "", Te && a?.(), n.value = void 0;
	};
	return s(r, (t, s) => {
		if (!R) return;
		if (!t) {
			s && o();
			return;
		}
		n.value === void 0 && (n.value = document.body.style.overflow);
		let c = window.innerWidth - document.documentElement.clientWidth, l = {
			padding: c,
			margin: 0
		}, u = i.scrollBody?.value ? typeof i.scrollBody.value == "object" ? Qe({
			padding: i.scrollBody.value.padding === !0 ? c : i.scrollBody.value.padding,
			margin: i.scrollBody.value.margin === !0 ? c : i.scrollBody.value.margin
		}, l) : l : {
			padding: 0,
			margin: 0
		};
		c > 0 && (document.body.style.paddingRight = typeof u.padding == "number" ? `${u.padding}px` : String(u.padding), document.body.style.marginRight = typeof u.margin == "number" ? `${u.margin}px` : String(u.margin), document.documentElement.style.setProperty("--scrollbar-width", `${c}px`), document.body.style.overflow = "hidden"), Te && (a = Le(document, "touchmove", (e) => rt(e), { passive: !1 })), e(() => {
			r.value && (qe(document, $e), document.body.style.overflow = "hidden");
		});
	}, {
		immediate: !0,
		flush: "sync"
	}), t;
});
function tt(e) {
	let t = Math.random().toString(36).substring(2, 7), n = et();
	n.value.set(t, e ?? !1);
	let r = P({
		get: () => n.value.get(t) ?? !1,
		set: (e) => n.value.set(t, e)
	});
	return Ne(() => {
		n.value.delete(t);
	}), r;
}
function nt(e) {
	let t = window.getComputedStyle(e);
	if (t.overflowX === "scroll" || t.overflowY === "scroll" || t.overflowX === "auto" && e.clientWidth < e.scrollWidth || t.overflowY === "auto" && e.clientHeight < e.scrollHeight) return !0;
	{
		let t = e.parentNode;
		return !(t instanceof Element) || t.tagName === "BODY" ? !1 : nt(t);
	}
}
function rt(e) {
	let t = e || window.event, n = t.target;
	return n instanceof Element && nt(n) ? !1 : t.touches.length > 1 || (t.preventDefault && t.cancelable && t.preventDefault(), !1);
}
// node_modules/reka-ui/dist/shared/useDirection.js
function it(e) {
	let t = We({ dir: k("ltr") });
	return P(() => e?.value || t.dir?.value || "ltr");
}
// node_modules/reka-ui/dist/shared/useEmitAsProps.js
function at(e) {
	let t = ge(), n = t?.type.emits, r = {};
	return n?.length || console.warn(`No emitted event found. Please check component: ${t?.type.__name}`), n?.forEach((t) => {
		r[le(ee(t))] = (...n) => e(t, ...n);
	}), r;
}
// node_modules/reka-ui/dist/shared/useFocusGuards.js
var ot = 0;
function st() {
	y((e) => {
		if (!R) return;
		let t = document.querySelectorAll("[data-reka-focus-guard]");
		document.body.insertAdjacentElement("afterbegin", t[0] ?? ct()), document.body.insertAdjacentElement("beforeend", t[1] ?? ct()), ot++, e(() => {
			ot === 1 && document.querySelectorAll("[data-reka-focus-guard]").forEach((e) => e.remove()), ot--;
		});
	});
}
function ct() {
	let e = document.createElement("span");
	return e.setAttribute("data-reka-focus-guard", ""), e.tabIndex = 0, e.style.outline = "none", e.style.opacity = "0", e.style.position = "fixed", e.style.pointerEvents = "none", e;
}
// node_modules/reka-ui/dist/shared/useForwardExpose.js
function z() {
	let e = ge(), t = k(), n = P(() => r());
	m(() => {
		n.value !== r() && se(t);
	});
	function r() {
		return t.value && "$el" in t.value && ["#text", "#comment"].includes(t.value.$el.nodeName) ? t.value.$el.nextElementSibling : Ie(t);
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
function lt(e) {
	let t = ge(), n = Object.keys(t?.type.props ?? {}).reduce((e, n) => {
		let r = (t?.type.props[n]).default;
		return r !== void 0 && (e[n] = r), e;
	}, {}), r = de(e);
	return P(() => {
		let e = {}, i = t?.vnode.props ?? {};
		return Object.keys(i).forEach((t) => {
			e[ee(t)] = i[t];
		}), Object.keys({
			...n,
			...e
		}).reduce((e, t) => (r.value[t] !== void 0 && (e[t] = r.value[t]), e), {});
	});
}
// node_modules/reka-ui/dist/shared/useForwardPropsEmits.js
function ut(e, t) {
	let n = lt(e), r = t ? at(t) : {};
	return P(() => ({
		...n.value,
		...r
	}));
}
// node_modules/aria-hidden/dist/es2015/index.js
var dt = function(e) {
	return typeof document > "u" ? null : (Array.isArray(e) ? e[0] : e).ownerDocument.body;
}, ft = /* @__PURE__ */ new WeakMap(), pt = /* @__PURE__ */ new WeakMap(), mt = {}, ht = 0, gt = function(e) {
	return e && (e.host || gt(e.parentNode));
}, _t = function(e, t) {
	return t.map(function(t) {
		if (e.contains(t)) return t;
		var n = gt(t);
		return n && e.contains(n) ? n : (console.error("aria-hidden", t, "in not contained inside", e, ". Doing nothing"), null);
	}).filter(function(e) {
		return !!e;
	});
}, vt = function(e, t, n, r) {
	var i = _t(t, Array.isArray(e) ? e : [e]);
	mt[n] || (mt[n] = /* @__PURE__ */ new WeakMap());
	var a = mt[n], o = [], s = /* @__PURE__ */ new Set(), c = new Set(i), l = function(e) {
		e && !s.has(e) && (s.add(e), l(e.parentNode));
	};
	i.forEach(l);
	var u = function(e) {
		e && !c.has(e) && Array.prototype.forEach.call(e.children, function(e) {
			if (s.has(e)) u(e);
			else try {
				var t = e.getAttribute(r), i = t !== null && t !== "false", c = (ft.get(e) || 0) + 1, l = (a.get(e) || 0) + 1;
				ft.set(e, c), a.set(e, l), o.push(e), c === 1 && i && pt.set(e, !0), l === 1 && e.setAttribute(n, "true"), i || e.setAttribute(r, "true");
			} catch (t) {
				console.error("aria-hidden: cannot operate on ", e, t);
			}
		});
	};
	return u(t), s.clear(), ht++, function() {
		o.forEach(function(e) {
			var t = ft.get(e) - 1, i = a.get(e) - 1;
			ft.set(e, t), a.set(e, i), t || (pt.has(e) || e.removeAttribute(r), pt.delete(e)), i || e.removeAttribute(n);
		}), ht--, ht || (ft = /* @__PURE__ */ new WeakMap(), ft = /* @__PURE__ */ new WeakMap(), pt = /* @__PURE__ */ new WeakMap(), mt = {});
	};
}, yt = function(e, t, n) {
	n === void 0 && (n = "data-aria-hidden");
	var r = Array.from(Array.isArray(e) ? e : [e]), i = t || dt(e);
	return i ? (r.push.apply(r, Array.from(i.querySelectorAll("[aria-live], script"))), vt(r, i, n, "aria-hidden")) : function() {
		return null;
	};
};
// node_modules/reka-ui/dist/shared/useHideOthers.js
function bt(e) {
	let t;
	s(() => Ie(e), (e) => {
		let n = !1;
		try {
			n = !!e?.closest("[popover]:not(:popover-open)");
		} catch {}
		e && !n ? t = yt(e) : t && t();
	}), f(() => {
		t && t();
	});
}
function xt(e, t = "reka") {
	if (e) return e;
	let n, r = We({ useId: void 0 });
	return n = r.useId ? r.useId() : b?.(), t ? `${t}-${n}` : n;
}
// node_modules/reka-ui/dist/shared/useSize.js
function St(e) {
	let t = k(), n = P(() => t.value?.width ?? 0), r = P(() => t.value?.height ?? 0), i;
	return d(() => {
		let n = Ie(e);
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
	}), f(() => {
		i?.disconnect(), i = void 0;
	}), {
		width: n,
		height: r
	};
}
// node_modules/reka-ui/dist/shared/useStateMachine.js
function Ct(e, t) {
	let n = k(e);
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
function wt(t, n) {
	let r = k({}), i = k("none"), a = k(t), o = t.value ? "mounted" : "unmounted", c, l = n.value?.ownerDocument.defaultView ?? Fe, { state: u, dispatch: d } = Ct(o, {
		mounted: {
			UNMOUNT: "unmounted",
			ANIMATION_OUT: "unmountSuspended"
		},
		unmountSuspended: {
			MOUNT: "mounted",
			ANIMATION_END: "unmounted"
		},
		unmounted: { MOUNT: "mounted" }
	}), p = (e) => {
		if (R) {
			let t = new CustomEvent(e, {
				bubbles: !1,
				cancelable: !1
			});
			n.value?.dispatchEvent(t);
		}
	};
	s(t, async (t, a) => {
		let o = a !== t;
		if (await e(), o) {
			let e = i.value, o = Tt(n.value);
			t ? (d("MOUNT"), p("enter"), o === "none" && p("after-enter")) : o === "none" || o === "undefined" || r.value?.display === "none" ? (d("UNMOUNT"), p("leave"), p("after-leave")) : a && e !== o ? (d("ANIMATION_OUT"), p("leave")) : (d("UNMOUNT"), p("after-leave"));
		}
	}, { immediate: !0 });
	let m = (e) => {
		if (e.target !== n.value) return;
		let t = Tt(n.value), r = t.includes(CSS.escape(e.animationName)), i = u.value === "mounted" ? "enter" : "leave";
		if (r && (p(`after-${i}`), d("ANIMATION_END"), !a.value)) {
			let e = n.value.style.animationFillMode;
			n.value.style.animationFillMode = "forwards", c = l?.setTimeout(() => {
				n.value?.style.animationFillMode === "forwards" && (n.value.style.animationFillMode = e);
			});
		}
		t === "none" && d("ANIMATION_END");
	}, h = (e) => {
		e.target === n.value && (i.value = Tt(n.value));
	}, g = s(n, (e, t) => {
		e ? (r.value = getComputedStyle(e), e.addEventListener("animationstart", h), e.addEventListener("animationcancel", m), e.addEventListener("animationend", m)) : (d("ANIMATION_END"), c !== void 0 && l?.clearTimeout(c), t?.removeEventListener("animationstart", h), t?.removeEventListener("animationcancel", m), t?.removeEventListener("animationend", m));
	}, { immediate: !0 }), _ = s(u, () => {
		let e = Tt(n.value);
		i.value = u.value === "mounted" ? e : "none";
	});
	return f(() => {
		g(), _(), n.value && (n.value.removeEventListener("animationstart", h), n.value.removeEventListener("animationcancel", m), n.value.removeEventListener("animationend", m)), c !== void 0 && l?.clearTimeout(c);
	}), { isPresent: P(() => ["mounted", "unmountSuspended"].includes(u.value)) };
}
function Tt(e) {
	return e && getComputedStyle(e).animationName || "none";
}
// node_modules/reka-ui/dist/Presence/Presence.js
var Et = /*#__PURE__*/ n({
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
		let { present: r, forceMount: a } = ne(e), o = k(), { isPresent: s } = wt(r, o);
		n({ present: s });
		let c = t.default({ present: s.value });
		c = Ue(c || []);
		let l = ge();
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
		return () => a.value || r.value || s.value ? i(t.default({ present: s.value })[0], { ref: (e) => {
			let t = Ie(e);
			return t?.hasAttribute === void 0 || (t?.hasAttribute("data-reka-popper-content-wrapper") ? o.value = t.firstElementChild : o.value = t), t;
		} }) : null;
	}
}), Dt = /*#__PURE__*/ n({
	name: "PrimitiveSlot",
	inheritAttrs: !1,
	setup(e, { attrs: t, slots: n }) {
		return () => {
			if (!n.default) return null;
			let e = Ue(n.default()), r = e.findIndex((e) => e.type !== me);
			if (r === -1) return e;
			let i = e[r];
			delete i.props?.ref;
			let a = i.props ? N(t, i.props) : t, o = ce({
				...i,
				props: {}
			}, a);
			return e.length === 1 ? o : (e[r] = o, e);
		};
	}
}), Ot = [
	"area",
	"img",
	"input"
], B = /*#__PURE__*/ n({
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
		return typeof r == "string" && Ot.includes(r) ? () => i(r, t) : r === "template" ? () => i(Dt, t, { default: n.default }) : () => i(e.as, t, { default: n.default });
	}
}), kt = "dismissableLayer.pointerDownOutside", At = "dismissableLayer.focusOutside";
function jt(e) {
	if (typeof e != "object" || !e) return !1;
	let t = e.ownerDocument?.defaultView;
	return typeof Element < "u" && e instanceof Element || !!t && e instanceof t.Element;
}
function Mt(e, t) {
	if (!jt(t)) return !1;
	if (e.contains(t)) return !0;
	let n = t.closest("[data-dismissable-layer]"), r = e.dataset.dismissableLayer === "" ? e : e.querySelector("[data-dismissable-layer]"), i = Array.from(e.ownerDocument.querySelectorAll("[data-dismissable-layer]"));
	return !!(n && (r === n || i.indexOf(r) < i.indexOf(n)));
}
function Nt(e, t, n = !0) {
	let r = k(!1), i = k(() => {});
	return y((a) => {
		if (!R || !E(n)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			let a = n.target;
			if (t?.value && a) {
				if (Mt(t.value, a)) o.removeEventListener("click", i.value), r.value = !1;
				else {
					if (n.target && !r.value) {
						let t = { originalEvent: n };
						function r() {
							ye(kt, e, t);
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
		E(n) && (r.value = !0);
	} };
}
function Pt(t, n, r = !0) {
	let i = k(!1);
	return y((a) => {
		if (!R || !E(r)) return;
		let o = n?.value?.ownerDocument ?? globalThis.document, s = async (r) => {
			if (!n?.value) return;
			await e(), await e();
			let a = r.target;
			n.value && a && !Mt(n.value, a) && r.target && !i.value && ye(At, t, { originalEvent: r });
		};
		o.addEventListener("focusin", s), a(() => o.removeEventListener("focusin", s));
	}), {
		onFocusCapture: () => {
			E(r) && (i.value = !0);
		},
		onBlurCapture: () => {
			E(r) && (i.value = !1);
		}
	};
}
// node_modules/reka-ui/dist/DismissableLayer/context.js
var V = /*#__PURE__*/ h({
	layersRoot: /* @__PURE__ */ new Set(),
	layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
	branches: /* @__PURE__ */ new Set()
}), Ft = /* @__PURE__ */ n({
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
	setup(t, { emit: n }) {
		let r = t, i = n, { forwardRef: c, currentElement: l } = z(), u = P(() => l.value?.ownerDocument ?? globalThis.document), d = P(() => V.layersRoot), f = P(() => l.value ? Array.from(d.value).indexOf(l.value) : -1), p = P(() => V.layersWithOutsidePointerEventsDisabled.size > 0), m = P(() => {
			let e = Array.from(d.value), [t] = [...V.layersWithOutsidePointerEventsDisabled].slice(-1), n = e.indexOf(t);
			return f.value >= n;
		}), h = Nt(async (t) => {
			let n = [...V.branches].some((e) => e?.contains(t.target));
			r.present && m.value && !n && (i("pointerDownOutside", t), i("interactOutside", t), await e(), t.defaultPrevented || i("dismiss"));
		}, l, () => r.present), _ = Pt((e) => {
			let t = [...V.branches].some((t) => t?.contains(e.target));
			r.present && !t && (i("focusOutside", e), i("interactOutside", e), e.defaultPrevented || i("dismiss"));
		}, l);
		return Be("Escape", (e) => {
			r.present && f.value === d.value.size - 1 && (i("escapeKeyDown", e), e.defaultPrevented || i("dismiss"));
		}, { target: () => u.value?.defaultView ?? globalThis.window }), s([
			l,
			() => r.disableOutsidePointerEvents,
			() => r.present
		], ([e, t, n], r, i) => {
			if (e && n && t) {
				let t = e.ownerDocument;
				qe(t, e), V.layersWithOutsidePointerEventsDisabled.add(e), i(() => {
					V.layersWithOutsidePointerEventsDisabled.delete(e), Je(t, e);
				});
			}
		}, { immediate: !0 }), s([l, () => r.present], ([e, t], n, r) => {
			e && t && (d.value.add(e), r(() => {
				d.value.delete(e);
			}));
		}, { immediate: !0 }), y((e) => {
			e(() => {
				l.value && (d.value.delete(l.value), V.layersWithOutsidePointerEventsDisabled.delete(l.value));
			});
		}), (e, n) => (a(), j(F(B), {
			ref: F(c),
			"as-child": t.asChild,
			as: t.as,
			"data-dismissable-layer": "",
			style: O({ pointerEvents: p.value ? m.value ? "auto" : "none" : void 0 }),
			onFocusCapture: F(_).onFocusCapture,
			onBlurCapture: F(_).onBlurCapture,
			onPointerdownCapture: F(h).onPointerDownCapture
		}, {
			default: o(() => [g(e.$slots, "default")]),
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
}), It = xe(() => k([]));
function Lt() {
	let e = It();
	return {
		add(t) {
			let n = e.value[0];
			t !== n && n?.pause(), e.value = Rt(e.value, t), e.value.unshift(t);
		},
		remove(t) {
			e.value = Rt(e.value, t), e.value[0]?.resume();
		}
	};
}
function Rt(e, t) {
	let n = [...e], r = n.indexOf(t);
	return r !== -1 && n.splice(r, 1), n;
}
// node_modules/reka-ui/dist/FocusScope/utils.js
var zt = "focusScope.autoFocusOnMount", Bt = "focusScope.autoFocusOnUnmount", Vt = {
	bubbles: !1,
	cancelable: !0
};
function Ht(e, t) {
	let n = t;
	for (; n;) {
		if (e.contains(n)) return !0;
		n = n.getRootNode().host ?? null;
	}
	return !1;
}
function Ut(e, { select: t = !1 } = {}) {
	let n = L();
	for (let r of e) if (H(r, { select: t }), L() !== n) return !0;
}
function Wt(e) {
	let t = Gt(e);
	return [Kt(t, e), Kt(t.reverse(), e)];
}
function Gt(e) {
	let t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, { acceptNode: (e) => {
		let t = e.tagName === "INPUT" && e.type === "hidden";
		return e.disabled || e.hidden || t ? NodeFilter.FILTER_SKIP : e.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
	} });
	for (; n.nextNode();) t.push(n.currentNode);
	return t.sort((e, t) => e.tabIndex === t.tabIndex ? 0 : e.tabIndex === 0 ? 1 : t.tabIndex === 0 ? -1 : e.tabIndex - t.tabIndex);
}
function Kt(e, t) {
	for (let n of e) if (!qt(n, { upTo: t })) return n;
}
function qt(e, { upTo: t }) {
	if (getComputedStyle(e).visibility === "hidden") return !0;
	for (; e;) {
		if (t !== void 0 && e === t) return !1;
		if (getComputedStyle(e).display === "none") return !0;
		e = e.parentElement;
	}
	return !1;
}
function Jt(e) {
	return e instanceof HTMLInputElement && "select" in e;
}
function H(e, { select: t = !1 } = {}) {
	if (e && e.focus) {
		let n = L();
		e.focus({ preventScroll: !0 }), e !== n && Jt(e) && t && e.select();
	}
}
// node_modules/reka-ui/dist/FocusScope/FocusScope.js
var Yt = /* @__PURE__ */ n({
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
	setup(t, { emit: n }) {
		let r = t, i = n, { currentRef: c, currentElement: l } = z(), u = k(null), d = Lt(), f = /*#__PURE__*/ h({
			paused: !1,
			pause() {
				this.paused = !0;
			},
			resume() {
				this.paused = !1;
			}
		});
		y((e) => {
			if (!R) return;
			let t = l.value;
			if (!r.trapped) return;
			let n = t?.ownerDocument ?? document, i = t ? t.getRootNode() : n;
			function a(e) {
				if (f.paused || !t) return;
				let n = e.target;
				t.contains(n) ? u.value = n : H(u.value, { select: !0 });
			}
			function o(e) {
				if (f.paused || !t) return;
				let n = e.relatedTarget;
				n !== null && (t.contains(n) || H(u.value, { select: !0 }));
			}
			function s(e) {
				let n = u.value;
				if (n === null || !e.some((e) => e.removedNodes.length > 0)) return;
				let r = L();
				r && t.contains(r) || t.contains(n) || H(t);
			}
			function c(e) {
				if (f.paused || !t) return;
				let n = e.composedPath()[0];
				Ht(t, n) || H(u.value, { select: !0 });
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
		function p(e, t) {
			let n = new CustomEvent(zt, Vt), r = (e) => i("mountAutoFocus", e);
			e.addEventListener(zt, r), e.dispatchEvent(n), e.removeEventListener(zt, r), n.defaultPrevented || (Ut(Gt(e), { select: !0 }), L() === t && H(e));
		}
		y(async (t) => {
			let n = l.value;
			if (await e(), !n) return;
			r.present !== !1 && d.add(f);
			let a = L();
			!n.contains(a) && r.present !== !1 && p(n, a), t(() => {
				let e = new CustomEvent(Bt, Vt), t = (e) => {
					i("unmountAutoFocus", e);
				};
				n.addEventListener(Bt, t), n.dispatchEvent(e), n.setAttribute("data-focus-scope-unmounting", ""), setTimeout(() => {
					e.defaultPrevented || H(a ?? document.body, { select: !0 }), n.removeEventListener(Bt, t), d.remove(f), n.removeAttribute("data-focus-scope-unmounting");
				}, 0);
			});
		}), s(() => r.present, async (t, n) => {
			if (!R) return;
			if (t === !1 && n === !0) {
				d.remove(f);
				return;
			}
			if (t !== !0 || n !== !1) return;
			d.add(f), await e();
			let r = l.value;
			if (!r) return;
			let i = L();
			r.contains(i) || p(r, i);
		});
		function m(e) {
			if (!r.loop && !r.trapped || f.paused) return;
			let t = e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey, n = L();
			if (t && n) {
				let t = e.currentTarget, [i, a] = Wt(t);
				i && a ? !e.shiftKey && n === a ? (e.preventDefault(), r.loop && H(i, { select: !0 })) : e.shiftKey && n === i && (e.preventDefault(), r.loop && H(a, { select: !0 })) : n === t && e.preventDefault();
			}
		}
		return (e, n) => (a(), j(F(B), {
			ref_key: "currentRef",
			ref: c,
			tabindex: "-1",
			"as-child": t.asChild,
			as: t.as,
			onKeydown: m
		}, {
			default: o(() => [g(e.$slots, "default")]),
			_: 3
		}, 8, ["as-child", "as"]));
	}
}), Xt = /* @__PURE__ */ n({
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
		let t = e, n = We({}), r = P(() => t.to ?? n.teleportTo?.value ?? "body"), i = Re();
		return (t, n) => F(i) || e.forceMount ? (a(), j(te, {
			key: 0,
			to: r.value,
			disabled: e.disabled,
			defer: e.defer
		}, [g(t.$slots, "default")], 8, [
			"to",
			"disabled",
			"defer"
		])) : T("v-if", !0);
	}
}), [Zt, Qt] = /*#__PURE__*/ ve("PopperRoot"), $t = /* @__PURE__ */ n({
	inheritAttrs: !1,
	__name: "PopperRoot",
	setup(e) {
		let t = k();
		return Qt({
			anchor: t,
			onAnchorChange: (e) => t.value = e
		}), (e, t) => g(e.$slots, "default");
	}
}), en = /* @__PURE__ */ n({
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
		let t = e, { forwardRef: n, currentElement: r } = z(), i = Zt();
		return x(() => {
			i.onAnchorChange(t.reference ?? r.value);
		}), (t, r) => (a(), j(F(B), {
			ref: F(n),
			as: e.as,
			"as-child": e.asChild
		}, {
			default: o(() => [g(t.$slots, "default")]),
			_: 3
		}, 8, ["as", "as-child"]));
	}
});
// node_modules/reka-ui/dist/Popper/utils.js
function tn(e) {
	return e !== null;
}
function nn(e) {
	return {
		name: "transformOrigin",
		options: e,
		fn(t) {
			let { placement: n, rects: r, middlewareData: i } = t, a = i.arrow?.centerOffset !== 0, o = a ? 0 : e.arrowWidth, s = a ? 0 : e.arrowHeight, [c, l] = rn(n), u = {
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
function rn(e) {
	let [t, n = "center"] = e.split("-");
	return [t, n];
}
// node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs
var an = [
	"top",
	"right",
	"bottom",
	"left"
], U = Math.min, W = Math.max, on = Math.round, sn = Math.floor, G = (e) => ({
	x: e,
	y: e
}), cn = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function ln(e, t, n) {
	return W(e, U(t, n));
}
function K(e, t) {
	return typeof e == "function" ? e(t) : e;
}
function q(e) {
	return e.split("-")[0];
}
function un(e) {
	return e.split("-")[1];
}
function dn(e) {
	return e === "x" ? "y" : "x";
}
function fn(e) {
	return e === "y" ? "height" : "width";
}
function J(e) {
	let t = e[0];
	return t === "t" || t === "b" ? "y" : "x";
}
function pn(e) {
	return dn(J(e));
}
function mn(e, t, n) {
	n === void 0 && (n = !1);
	let r = un(e), i = pn(e), a = fn(i), o = i === "x" ? r === (n ? "end" : "start") ? "right" : "left" : r === "start" ? "bottom" : "top";
	return t.reference[a] > t.floating[a] && (o = Cn(o)), [o, Cn(o)];
}
function hn(e) {
	let t = Cn(e);
	return [
		gn(e),
		t,
		gn(t)
	];
}
function gn(e) {
	return e.includes("start") ? e.replace("start", "end") : e.replace("end", "start");
}
var _n = ["left", "right"], vn = ["right", "left"], yn = ["top", "bottom"], bn = ["bottom", "top"];
function xn(e, t, n) {
	switch (e) {
		case "top":
		case "bottom": return n ? t ? vn : _n : t ? _n : vn;
		case "left":
		case "right": return t ? yn : bn;
		default: return [];
	}
}
function Sn(e, t, n, r) {
	let i = un(e), a = xn(q(e), n === "start", r);
	return i && (a = a.map((e) => e + "-" + i), t && (a = a.concat(a.map(gn)))), a;
}
function Cn(e) {
	let t = q(e);
	return cn[t] + e.slice(t.length);
}
function wn(e) {
	return {
		top: e.top ?? 0,
		right: e.right ?? 0,
		bottom: e.bottom ?? 0,
		left: e.left ?? 0
	};
}
function Tn(e) {
	return typeof e == "number" ? {
		top: e,
		right: e,
		bottom: e,
		left: e
	} : wn(e);
}
function En(e) {
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
function Dn(e, t, n) {
	let { reference: r, floating: i } = e, a = J(t), o = pn(t), s = fn(o), c = q(t), l = a === "y", u = r.x + r.width / 2 - i.width / 2, d = r.y + r.height / 2 - i.height / 2, f = r[s] / 2 - i[s] / 2, p;
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
	let m = un(t);
	return m && (p[o] += f * (m === "end" ? 1 : -1) * (n && l ? -1 : 1)), p;
}
async function On(e, t) {
	t === void 0 && (t = {});
	let { x: n, y: r, platform: i, rects: a, elements: o, strategy: s } = e, { boundary: c = "clippingAncestors", rootBoundary: l = "viewport", elementContext: u = "floating", altBoundary: d = !1, padding: f = 0 } = K(t, e), p = Tn(f), m = o[d ? u === "floating" ? "reference" : "floating" : u], h = En(await i.getClippingRect({
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
	}, y = En(i.convertOffsetParentRelativeRectToViewportRelativeRect ? await i.convertOffsetParentRelativeRectToViewportRelativeRect({
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
var kn = 50, An = async (e, t, n) => {
	let { placement: r = "bottom", strategy: i = "absolute", middleware: a = [], platform: o } = n, s = o.detectOverflow ? o : {
		...o,
		detectOverflow: On
	}, c = await (o.isRTL == null ? void 0 : o.isRTL(t)), l = await o.getElementRects({
		reference: e,
		floating: t,
		strategy: i
	}), { x: u, y: d } = Dn(l, r, c), f = r, p = 0, m = {};
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
		}, x && p < kn && (p++, typeof x == "object" && (x.placement && (f = x.placement), x.rects && (l = x.rects === !0 ? await o.getElementRects({
			reference: e,
			floating: t,
			strategy: i
		}) : x.rects), {x: u, y: d} = Dn(l, f, c)), n = -1);
	}
	return {
		x: u,
		y: d,
		placement: f,
		strategy: i,
		middlewareData: m
	};
}, jn = (e) => ({
	name: "arrow",
	options: e,
	async fn(t) {
		let { x: n, y: r, placement: i, rects: a, platform: o, elements: s, middlewareData: c } = t, { element: l, padding: u = 0 } = K(e, t) || {};
		if (l == null) return {};
		let d = Tn(u), f = {
			x: n,
			y: r
		}, p = pn(i), m = fn(p), h = await o.getDimensions(l), g = p === "y", _ = g ? "top" : "left", v = g ? "bottom" : "right", y = g ? "clientHeight" : "clientWidth", b = a.reference[m] + a.reference[p] - f[p] - a.floating[m], x = f[p] - a.reference[p], S = await (o.getOffsetParent == null ? void 0 : o.getOffsetParent(l)), C = S ? S[y] : 0;
		C && await (o.isElement == null ? void 0 : o.isElement(S)) || (C = s.floating[y] || a.floating[m]);
		let w = b / 2 - x / 2, T = C / 2 - h[m] / 2 - 1, E = U(d[_], T), ee = U(d[v], T), D = C - h[m] - ee, O = C / 2 - h[m] / 2 + w, k = ln(E, O, D), te = !c.arrow && un(i) != null && O !== k && a.reference[m] / 2 - (O < E ? E : ee) - h[m] / 2 < 0, A = te ? O < E ? O - E : O - D : 0;
		return {
			[p]: f[p] + A,
			data: {
				[p]: k,
				centerOffset: O - k - A,
				...te && { alignmentOffset: A }
			},
			reset: te
		};
	}
}), Mn = function(e) {
	return e === void 0 && (e = {}), {
		name: "flip",
		options: e,
		async fn(t) {
			var n;
			let { placement: r, middlewareData: i, rects: a, initialPlacement: o, platform: s, elements: c } = t, { mainAxis: l = !0, crossAxis: u = !0, fallbackPlacements: d, fallbackStrategy: f = "bestFit", fallbackAxisSideDirection: p = "none", flipAlignment: m = !0, ...h } = K(e, t);
			if ((n = i.arrow) != null && n.alignmentOffset) return {};
			let g = q(r), _ = J(o), v = q(o) === o, y = await (s.isRTL == null ? void 0 : s.isRTL(c.floating)), b = d || (v || !m ? [Cn(o)] : hn(o)), x = p !== "none";
			!d && x && b.push(...Sn(o, m, p, y));
			let S = [o, ...b], C = await s.detectOverflow(t, h), w = [], T = i.flip?.overflows || [];
			if (l && w.push(C[g]), u) {
				let e = mn(r, a, y);
				w.push(C[e[0]], C[e[1]]);
			}
			if (T = [...T, {
				placement: r,
				overflows: w
			}], !w.every((e) => e <= 0)) {
				let e = (i.flip?.index || 0) + 1, t = S[e];
				if (t && (u !== "alignment" || _ === J(t) || T.every((e) => J(e.placement) !== _ || e.overflows[0] > 0))) return {
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
								let t = J(e.placement);
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
function Nn(e, t) {
	return {
		top: e.top - t.height,
		right: e.right - t.width,
		bottom: e.bottom - t.height,
		left: e.left - t.width
	};
}
function Pn(e) {
	return an.some((t) => e[t] >= 0);
}
var Fn = function(e) {
	return e === void 0 && (e = {}), {
		name: "hide",
		options: e,
		async fn(t) {
			let { rects: n, platform: r } = t, { strategy: i = "referenceHidden", ...a } = K(e, t);
			switch (i) {
				case "referenceHidden": {
					let e = Nn(await r.detectOverflow(t, {
						...a,
						elementContext: "reference"
					}), n.reference);
					return { data: {
						referenceHiddenOffsets: e,
						referenceHidden: Pn(e)
					} };
				}
				case "escaped": {
					let e = Nn(await r.detectOverflow(t, {
						...a,
						altBoundary: !0
					}), n.floating);
					return { data: {
						escapedOffsets: e,
						escaped: Pn(e)
					} };
				}
				default: return {};
			}
		}
	};
}, In = /*#__PURE__*/ new Set(["left", "top"]);
async function Ln(e, t) {
	let { placement: n, platform: r, elements: i } = e, a = await (r.isRTL == null ? void 0 : r.isRTL(i.floating)), o = q(n), s = un(n), c = J(n) === "y", l = In.has(o) ? -1 : 1, u = a && c ? -1 : 1, d = K(t, e), { mainAxis: f, crossAxis: p, alignmentAxis: m } = typeof d == "number" ? {
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
var Rn = function(e) {
	return e === void 0 && (e = 0), {
		name: "offset",
		options: e,
		async fn(t) {
			var n;
			let { x: r, y: i, placement: a, middlewareData: o } = t, s = await Ln(t, e);
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
}, zn = function(e) {
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
			} }, ...l } = K(e, t), u = {
				x: n,
				y: r
			}, d = await a.detectOverflow(t, l), f = J(i), p = dn(f), m = u[p], h = u[f], g = (e, t) => ln(t + d[e === "y" ? "top" : "left"], t, t - d[e === "y" ? "bottom" : "right"]);
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
}, Bn = function(e) {
	return e === void 0 && (e = {}), {
		options: e,
		fn(t) {
			let { x: n, y: r, placement: i, rects: a, middlewareData: o } = t, { offset: s = 0, mainAxis: c = !0, crossAxis: l = !0 } = K(e, t), u = {
				x: n,
				y: r
			}, d = J(i), f = dn(d), p = u[f], m = u[d], h = K(s, t), g = typeof h == "number" ? {
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
				let e = f === "y" ? "width" : "height", t = In.has(q(i)), n = a.reference[d] - a.floating[e] + (t && o.offset?.[d] || 0) + (t ? 0 : g.crossAxis), r = a.reference[d] + a.reference[e] + (t ? 0 : o.offset?.[d] || 0) - (t ? g.crossAxis : 0);
				m < n ? m = n : m > r && (m = r);
			}
			return {
				[f]: p,
				[d]: m
			};
		}
	};
}, Vn = function(e) {
	return e === void 0 && (e = {}), {
		name: "size",
		options: e,
		async fn(t) {
			let { placement: n, rects: r, platform: i, elements: a } = t, { apply: o = () => {}, ...s } = K(e, t), c = await i.detectOverflow(t, s), l = q(n), u = un(n), d = J(n) === "y", { width: f, height: p } = r.floating, m, h;
			l === "top" || l === "bottom" ? (m = l, h = u === (await (i.isRTL == null ? void 0 : i.isRTL(a.floating)) ? "start" : "end") ? "left" : "right") : (h = l, m = u === "end" ? "top" : "bottom");
			let g = p - c.top - c.bottom, _ = f - c.left - c.right, v = U(p - c[m], g), y = U(f - c[h], _), b = t.middlewareData.shift, x = !b, S = v, C = y;
			b != null && b.enabled.x && (C = _), b != null && b.enabled.y && (S = g), x && !u && (d ? C = f - 2 * W(c.left, c.right) : S = p - 2 * W(c.top, c.bottom)), await o({
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
function Hn() {
	return typeof window < "u";
}
function Un(e) {
	return Wn(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function Y(e) {
	var t;
	return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function X(e) {
	return ((Wn(e) ? e.ownerDocument : e.document) || window.document)?.documentElement;
}
function Wn(e) {
	return Hn() ? e instanceof Node || e instanceof Y(e).Node : !1;
}
function Z(e) {
	return Hn() ? e instanceof Element || e instanceof Y(e).Element : !1;
}
function Q(e) {
	return Hn() ? e instanceof HTMLElement || e instanceof Y(e).HTMLElement : !1;
}
function Gn(e) {
	return !Hn() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof Y(e).ShadowRoot;
}
function Kn(e) {
	let { overflow: t, overflowX: n, overflowY: r, display: i } = $(e);
	return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && i !== "inline" && i !== "contents";
}
function qn(e) {
	return /^(table|td|th)$/.test(Un(e));
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
	let t = Z(e) ? $(e) : e;
	return Zn(t.transform) || Zn(t.translate) || Zn(t.scale) || Zn(t.rotate) || Zn(t.perspective) || !tr() && (Zn(t.backdropFilter) || Zn(t.filter)) || Yn.test(t.willChange || "") || Xn.test(t.contain || "");
}
function er(e) {
	let t = ir(e);
	for (; Q(t) && !nr(t);) {
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
	return /^(html|body|#document)$/.test(Un(e));
}
function $(e) {
	return Y(e).getComputedStyle(e);
}
function rr(e) {
	return Z(e) ? {
		scrollLeft: e.scrollLeft,
		scrollTop: e.scrollTop
	} : {
		scrollLeft: e.scrollX,
		scrollTop: e.scrollY
	};
}
function ir(e) {
	if (Un(e) === "html") return e;
	let t = e.assignedSlot || e.parentNode || Gn(e) && e.host || X(e);
	return Gn(t) ? t.host : t;
}
function ar(e) {
	let t = ir(e);
	return nr(t) ? (e.ownerDocument || e).body : Q(t) && Kn(t) ? t : ar(t);
}
function or(e, t, n) {
	t === void 0 && (t = []), n === void 0 && (n = !0);
	let r = ar(e), i = r === e.ownerDocument?.body, a = Y(r);
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
	let t = $(e), n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0, i = Q(e), a = i ? e.offsetWidth : n, o = i ? e.offsetHeight : r, s = on(n) !== a || on(r) !== o;
	return s && (n = a, r = o), {
		width: n,
		height: r,
		$: s
	};
}
function lr(e) {
	return Z(e) ? e : e.contextElement;
}
function ur(e) {
	let t = lr(e);
	if (!Q(t)) return G(1);
	let n = t.getBoundingClientRect(), { width: r, height: i, $: a } = cr(t), o = (a ? on(n.width) : n.width) / r, s = (a ? on(n.height) : n.height) / i;
	return o && Number.isFinite(o) || (o = 1), s && Number.isFinite(s) || (s = 1), {
		x: o,
		y: s
	};
}
var dr = /*#__PURE__*/ G(0);
function fr(e) {
	let t = Y(e);
	return !tr() || !t.visualViewport ? dr : {
		x: t.visualViewport.offsetLeft,
		y: t.visualViewport.offsetTop
	};
}
function pr(e, t, n) {
	return t === void 0 && (t = !1), !!n && t && n === Y(e);
}
function mr(e, t, n, r) {
	t === void 0 && (t = !1), n === void 0 && (n = !1);
	let i = e.getBoundingClientRect(), a = lr(e), o = G(1);
	t && (r ? Z(r) && (o = ur(r)) : o = ur(e));
	let s = pr(a, n, r) ? fr(a) : G(0), c = (i.left + s.x) / o.x, l = (i.top + s.y) / o.y, u = i.width / o.x, d = i.height / o.y;
	if (a && r) {
		let e = Y(a), t = Z(r) ? Y(r) : r, n = e, i = sr(n);
		for (; i && t !== n;) {
			let e = ur(i), t = i.getBoundingClientRect(), r = $(i), a = t.left + (i.clientLeft + parseFloat(r.paddingLeft)) * e.x, o = t.top + (i.clientTop + parseFloat(r.paddingTop)) * e.y;
			c *= e.x, l *= e.y, u *= e.x, d *= e.y, c += a, l += o, n = Y(i), i = sr(n);
		}
	}
	return En({
		width: u,
		height: d,
		x: c,
		y: l
	});
}
function hr(e, t) {
	let n = rr(e).scrollLeft;
	return t ? t.left + n : mr(X(e)).left + n;
}
function gr(e, t) {
	let n = e.getBoundingClientRect();
	return {
		x: n.left + t.scrollLeft - hr(e, n),
		y: n.top + t.scrollTop
	};
}
function _r(e) {
	let { elements: t, rect: n, offsetParent: r, strategy: i } = e, a = i === "fixed", o = X(r), s = t ? Jn(t.floating) : !1;
	if (r === o || s && a) return n;
	let c = {
		scrollLeft: 0,
		scrollTop: 0
	}, l = G(1), u = G(0), d = Q(r);
	if ((d || !a) && ((Un(r) !== "body" || Kn(o)) && (c = rr(r)), d)) {
		let e = mr(r);
		l = ur(r), u.x = e.x + r.clientLeft, u.y = e.y + r.clientTop;
	}
	let f = o && !d && !a ? gr(o, c) : G(0);
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
	let t = rr(e), n = e.ownerDocument.body, r = W(e.scrollWidth, e.clientWidth, n.scrollWidth, n.clientWidth), i = W(e.scrollHeight, e.clientHeight, n.scrollHeight, n.clientHeight), a = -t.scrollLeft + hr(e), o = -t.scrollTop;
	return $(n).direction === "rtl" && (a += W(e.clientWidth, n.clientWidth) - r), {
		width: r,
		height: i,
		x: a,
		y: o
	};
}
var br = 25;
function xr(e, t, n) {
	n === void 0 && (n = "viewport");
	let r = n === "layoutViewport", i = Y(e), a = X(e), o = i.visualViewport, s = a.clientWidth, c = a.clientHeight, l = 0, u = 0;
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
	else if (t === "document") r = yr(X(e));
	else if (Z(t)) r = Sr(t, n);
	else {
		let n = fr(e);
		r = {
			x: t.x - n.x,
			y: t.y - n.y,
			width: t.width,
			height: t.height
		};
	}
	return En(r);
}
function wr(e, t) {
	let n = t.get(e);
	if (n) return n;
	let r = or(e, [], !1).filter((e) => Z(e) && Un(e) !== "body"), i = null, a = $(e).position === "fixed", o = a ? ir(e) : e;
	for (; Z(o) && !nr(o);) {
		let e = $(o), t = $n(o), n = i ? i.position : a ? "fixed" : "";
		!t && (n === "fixed" || n === "absolute" && e.position === "static") ? r = r.filter((e) => e !== o) : i = e, o = ir(o);
	}
	return t.set(e, r), r;
}
function Tr(e) {
	let { element: t, boundary: n, rootBoundary: r, strategy: i } = e, a = [...n === "clippingAncestors" ? Jn(t) ? [] : wr(t, this._c) : [].concat(n), r], o = Cr(t, a[0], i), s = o.top, c = o.right, l = o.bottom, u = o.left;
	for (let e = 1; e < a.length; e++) {
		let n = Cr(t, a[e], i);
		s = W(n.top, s), c = U(n.right, c), l = U(n.bottom, l), u = W(n.left, u);
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
	let r = Q(t), i = X(t), a = n === "fixed", o = mr(e, !0, a, t), s = {
		scrollLeft: 0,
		scrollTop: 0
	}, c = G(0);
	if ((r || !a) && ((Un(t) !== "body" || Kn(i)) && (s = rr(t)), r)) {
		let e = mr(t, !0, a, t);
		c.x = e.x + t.clientLeft, c.y = e.y + t.clientTop;
	}
	!r && i && (c.x = hr(i));
	let l = i && !r && !a ? gr(i, s) : G(0);
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
	if (!Q(e) || $(e).position === "fixed") return null;
	if (t) return t(e);
	let n = e.offsetParent;
	return X(e) === n && (n = n.ownerDocument.body), n;
}
function Ar(e, t) {
	let n = Y(e);
	if (Jn(e)) return n;
	if (!Q(e)) {
		let t = ir(e);
		for (; t && !nr(t);) {
			if (Z(t) && !Or(t)) return t;
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
	getDocumentElement: X,
	getClippingRect: Tr,
	getOffsetParent: Ar,
	getElementRects: jr,
	getClientRects: vr,
	getDimensions: Er,
	getScale: ur,
	isElement: Z,
	isRTL: Mr
};
function Pr(e, t) {
	return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function Fr(e, t, n) {
	let r = null, i, a = X(e);
	function o() {
		var e;
		clearTimeout(i), (e = r) == null || e.disconnect(), r = null;
	}
	function s(n, c) {
		n === void 0 && (n = !1), c === void 0 && (c = 1), o();
		let l = e.getBoundingClientRect(), { left: u, top: d, width: f, height: p } = l;
		if (n || t(), !f || !p) return;
		let m = sn(d), h = sn(a.clientWidth - (u + f)), g = sn(a.clientHeight - (d + p)), _ = sn(u), v = {
			rootMargin: -m + "px " + -h + "px " + -g + "px " + -_ + "px",
			threshold: W(0, U(1, c)) || 1
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
	let c = Y(e), l = () => s(n);
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
var Lr = Rn, Rr = zn, zr = Mn, Br = Vn, Vr = Fn, Hr = jn, Ur = Bn, Wr = (e, t, n) => {
	let r = /* @__PURE__ */ new Map(), i = n ?? {}, a = {
		...Nr,
		...i.platform,
		_c: r
	};
	return An(e, t, {
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
		return Wn(t) && Un(t) === "#comment" ? null : t;
	}
	return e;
}
function qr(e) {
	return {
		name: "arrow",
		options: e,
		fn(t) {
			let n = Kr(E(e.element));
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
	let r = n.whileElementsMounted, i = P(() => E(n.open) ?? !0), a = P(() => E(n.middleware)), o = P(() => E(n.placement) ?? "bottom"), c = P(() => E(n.strategy) ?? "absolute"), l = P(() => E(n.transform) ?? !0), u = P(() => Kr(e.value)), d = P(() => Kr(t.value)), f = k(0), p = k(0), m = k(c.value), h = k(o.value), g = oe({}), _ = k(!1), v = P(() => {
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
	}), y;
	function b() {
		if (u.value == null || d.value == null) return;
		let e = i.value;
		Wr(u.value, d.value, {
			middleware: a.value,
			placement: o.value,
			strategy: c.value
		}).then((t) => {
			f.value = t.x, p.value = t.y, m.value = t.strategy, h.value = t.placement, g.value = t.middlewareData, _.value = e !== !1;
		});
	}
	function x() {
		typeof y == "function" && (y(), y = void 0);
	}
	function S() {
		x(), r === void 0 ? b() : u.value != null && d.value != null && (y = r(u.value, d.value, b));
	}
	function T() {
		i.value || (_.value = !1);
	}
	return s([
		a,
		o,
		c,
		i
	], b, { flush: "sync" }), s([u, d], S, { flush: "sync" }), s(i, T, { flush: "sync" }), C() && w(x), {
		x: pe(f),
		y: pe(p),
		strategy: pe(m),
		placement: pe(h),
		middlewareData: pe(g),
		isPositioned: pe(_),
		floatingStyles: v,
		update: b
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
}, [$r, ei] = /*#__PURE__*/ ve("PopperContent"), ti = /* @__PURE__ */ n({
	inheritAttrs: !1,
	__name: "PopperContent",
	props: /* @__PURE__ */ p({
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
		let n = e, r = t, i = Zt(), { forwardRef: s, currentElement: c } = z(), l = it(P(() => n.dir)), u = k(), d = k(), { width: f, height: p } = St(d), m = P(() => n.side + (n.align === "center" ? "" : `-${n.align}`)), h = P(() => typeof n.collisionPadding == "number" ? n.collisionPadding : {
			top: 0,
			right: 0,
			bottom: 0,
			left: 0,
			...n.collisionPadding
		}), _ = P(() => Array.isArray(n.collisionBoundary) ? n.collisionBoundary : [n.collisionBoundary]), v = P(() => ({
			padding: h.value,
			boundary: _.value.filter(tn),
			altBoundary: _.value.length > 0
		})), b = P(() => ({
			mainAxis: n.sideFlip,
			crossAxis: n.alignFlip
		})), S = P(() => [
			Lr({
				mainAxis: n.sideOffset + p.value,
				alignmentAxis: n.alignOffset
			}),
			n.prioritizePosition && n.avoidCollisions && zr({
				...v.value,
				...b.value
			}),
			n.avoidCollisions && Rr({
				mainAxis: !0,
				crossAxis: !!n.prioritizePosition,
				limiter: n.sticky === "partial" ? Ur() : void 0,
				...v.value
			}),
			!n.prioritizePosition && n.avoidCollisions && zr({
				...v.value,
				...b.value
			}),
			Br({
				...v.value,
				apply: ({ elements: e, rects: t, availableWidth: n, availableHeight: r }) => {
					let { width: i, height: a } = t.reference, o = e.floating.style;
					o.setProperty("--reka-popper-available-width", `${n}px`), o.setProperty("--reka-popper-available-height", `${r}px`), o.setProperty("--reka-popper-anchor-width", `${i}px`), o.setProperty("--reka-popper-anchor-height", `${a}px`);
				}
			}),
			d.value && qr({
				element: d.value,
				padding: n.arrowPadding
			}),
			nn({
				arrowWidth: f.value,
				arrowHeight: p.value,
				dir: l.value
			}),
			n.hideWhenDetached && Vr({
				strategy: "referenceHidden",
				...v.value
			})
		]), { floatingStyles: C, placement: w, isPositioned: T, middlewareData: E, update: ee } = Xr(P(() => n.reference ?? i.anchor.value), u, {
			strategy: n.positionStrategy,
			placement: m,
			whileElementsMounted: (...e) => Ir(...e, {
				layoutShift: !n.disableUpdateOnLayoutShift,
				animationFrame: n.updatePositionStrategy === "always"
			}),
			middleware: S
		}), D = P(() => rn(w.value)[0]), te = P(() => rn(w.value)[1]);
		x(() => {
			T.value && r("placed");
		});
		let A = P(() => {
			let e = E.value.arrow?.centerOffset !== 0;
			return n.hideShiftedArrow && e;
		}), M = k("");
		return y(() => {
			c.value && (M.value = window.getComputedStyle(c.value).zIndex);
		}), ei({
			placedSide: D,
			onArrowChange: (e) => d.value = e,
			arrowX: P(() => E.value.arrow?.x ?? 0),
			arrowY: P(() => E.value.arrow?.y ?? 0),
			shouldHideArrow: A
		}), (e, t) => (a(), I("div", {
			ref_key: "floatingRef",
			ref: u,
			"data-reka-popper-content-wrapper": "",
			dir: F(l),
			style: O({
				...F(C),
				transform: F(T) ? F(C).transform : "translate(0, -200%)",
				minWidth: "max-content",
				zIndex: M.value,
				"--reka-popper-transform-origin": [F(E).transformOrigin?.x, F(E).transformOrigin?.y].join(" "),
				...F(E).hide?.referenceHidden && {
					visibility: "hidden",
					pointerEvents: "none"
				}
			})
		}, [n.memoDependencies ? ue([
			n.asChild,
			n.as,
			D.value,
			te.value,
			F(T),
			...Object.values(e.$attrs),
			...n.memoDependencies
		], () => (a(), j(F(B), N({
			key: 0,
			ref: F(s)
		}, e.$attrs, {
			"as-child": n.asChild,
			as: n.as,
			"data-side": D.value,
			"data-align": te.value,
			style: { animation: F(T) ? void 0 : "none" }
		}), {
			default: o(() => [g(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"style"
		])), t, 0) : (a(), j(F(B), N({
			key: 1,
			ref: F(s)
		}, e.$attrs, {
			"as-child": n.asChild,
			as: n.as,
			"data-side": D.value,
			"data-align": te.value,
			dir: F(l),
			style: { animation: F(T) ? void 0 : "none" }
		}), {
			default: o(() => [g(e.$slots, "default")]),
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
}), [ni, ri] = /*#__PURE__*/ ve("PopoverRoot"), ii = /* @__PURE__ */ n({
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
		let n = e, r = t, { modal: i } = ne(n), s = He(n, "open", r, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		});
		return ri({
			contentId: "",
			triggerId: "",
			modal: i,
			open: s,
			onOpenChange: (e) => {
				s.value = e;
			},
			onOpenToggle: () => {
				s.value = !s.value;
			},
			triggerElement: k(),
			hasCustomAnchor: k(!1)
		}), (e, t) => (a(), j(F($t), null, {
			default: o(() => [g(e.$slots, "default", {
				open: F(s),
				close: () => s.value = !1
			})]),
			_: 3
		}));
	}
}), ai = /* @__PURE__ */ n({
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
		z();
		let n = ni();
		return (r, i) => (a(), j(F(B), {
			type: e.as === "button" ? "button" : void 0,
			as: e.as,
			"as-child": t.asChild,
			onClick: i[0] ||= (e) => F(n).onOpenChange(!1)
		}, {
			default: o(() => [g(r.$slots, "default")]),
			_: 3
		}, 8, [
			"type",
			"as",
			"as-child"
		]));
	}
}), oi = /* @__PURE__ */ n({
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
		let n = e, r = t, i = lt(Me(n, "trapFocus", "disableOutsidePointerEvents")), { forwardRef: s } = z(), c = ni();
		return st(), (t, n) => (a(), j(F(Yt), {
			"as-child": "",
			loop: "",
			trapped: e.trapFocus,
			onMountAutoFocus: n[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: n[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: o(() => [_(F(Ft), {
				"as-child": "",
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				onPointerDownOutside: n[0] ||= (e) => r("pointerDownOutside", e),
				onInteractOutside: n[1] ||= (e) => r("interactOutside", e),
				onEscapeKeyDown: n[2] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: n[3] ||= (e) => r("focusOutside", e),
				onDismiss: n[4] ||= (e) => F(c).onOpenChange(!1)
			}, {
				default: o(() => [_(F(ti), N(F(i), {
					id: F(c).contentId,
					ref: F(s),
					"data-state": F(c).open.value ? "open" : "closed",
					"aria-labelledby": F(c).triggerId,
					style: {
						"--reka-popover-content-transform-origin": "var(--reka-popper-transform-origin)",
						"--reka-popover-content-available-width": "var(--reka-popper-available-width)",
						"--reka-popover-content-available-height": "var(--reka-popper-available-height)",
						"--reka-popover-trigger-width": "var(--reka-popper-anchor-width)",
						"--reka-popover-trigger-height": "var(--reka-popper-anchor-height)"
					},
					role: "dialog"
				}), {
					default: o(() => [g(t.$slots, "default")]),
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
}), si = /* @__PURE__ */ n({
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
		let n = e, r = t, i = ni(), s = k(!1);
		tt(!0);
		let c = ut(n, r), { forwardRef: l, currentElement: u } = z();
		return bt(u), (e, t) => (a(), j(oi, N(F(c), {
			ref: F(l),
			"trap-focus": F(i).open.value,
			"disable-outside-pointer-events": "",
			onCloseAutoFocus: t[0] ||= ie((e) => {
				r("closeAutoFocus", e), s.value || F(i).triggerElement.value?.focus();
			}, ["prevent"]),
			onPointerDownOutside: t[1] ||= (e) => {
				r("pointerDownOutside", e);
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0, i = t.button === 2 || n;
				s.value = i;
			},
			onFocusOutside: t[2] ||= ie(() => {}, ["prevent"])
		}), {
			default: o(() => [g(e.$slots, "default")]),
			_: 3
		}, 16, ["trap-focus"]));
	}
}), ci = /* @__PURE__ */ n({
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
		let n = e, r = t, i = ni(), s = k(!1), c = k(!1), l = ut(n, r);
		return (e, t) => (a(), j(oi, N(F(l), {
			"trap-focus": !1,
			"disable-outside-pointer-events": !1,
			onCloseAutoFocus: t[0] ||= (e) => {
				r("closeAutoFocus", e), e.defaultPrevented || (s.value || F(i).triggerElement.value?.focus(), e.preventDefault()), s.value = !1, c.value = !1;
			},
			onInteractOutside: t[1] ||= async (e) => {
				r("interactOutside", e), e.defaultPrevented || (s.value = !0, e.detail.originalEvent.type === "pointerdown" && (c.value = !0));
				let t = e.target;
				F(i).triggerElement.value?.contains(t) && e.preventDefault(), e.detail.originalEvent.type === "focusin" && c.value && e.preventDefault();
			}
		}), {
			default: o(() => [g(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), li = /* @__PURE__ */ n({
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
		let n = e, r = t, i = ni(), s = ut(n, r), { forwardRef: c } = z();
		return i.contentId ||= xt(void 0, "reka-popover-content"), (t, n) => (a(), j(F(Et), { present: e.forceMount || F(i).open.value }, {
			default: o(() => [F(i).modal.value ? (a(), j(si, N({ key: 0 }, F(s), { ref: F(c) }), {
				default: o(() => [g(t.$slots, "default")]),
				_: 3
			}, 16)) : (a(), j(ci, N({ key: 1 }, F(s), { ref: F(c) }), {
				default: o(() => [g(t.$slots, "default")]),
				_: 3
			}, 16))]),
			_: 3
		}, 8, ["present"]));
	}
}), ui = /* @__PURE__ */ n({
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
		return (e, n) => (a(), j(F(Xt), he(v(t)), {
			default: o(() => [g(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), di = /* @__PURE__ */ n({
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
		let n = e, r = ni(), { forwardRef: i, currentElement: s } = z();
		return r.triggerId ||= xt(void 0, "reka-popover-trigger"), r.contentId ||= xt(void 0, "reka-popover-content"), d(() => {
			r.triggerElement.value = s.value;
		}), (s, c) => (a(), j(t(F(r).hasCustomAnchor.value ? F(B) : F(en)), { "as-child": "" }, {
			default: o(() => [_(F(B), {
				id: F(r).triggerId,
				ref: F(i),
				type: e.as === "button" ? "button" : void 0,
				"aria-haspopup": "dialog",
				"aria-expanded": F(r).open.value,
				"aria-controls": F(r).open.value ? F(r).contentId : void 0,
				"data-state": F(r).open.value ? "open" : "closed",
				as: e.as,
				"as-child": n.asChild,
				onClick: F(r).onOpenToggle
			}, {
				default: o(() => [g(s.$slots, "default")]),
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
], pi = { class: "tc-column-filter-label" }, mi = { class: "tc-filter-popover-heading list-filter-popover__heading" }, hi = /*#__PURE__*/ fe(/* @__PURE__ */ n({
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
		return (t, r) => (a(), j(F(ii), {
			open: e.open,
			modal: !1,
			"onUpdate:open": r[1] ||= (e) => n("update:open", e)
		}, {
			default: o(() => [_(F(di), { "as-child": "" }, {
				default: o(() => [M("button", {
					type: "button",
					class: ae(["tc-column-filter-trigger", { "is-active": e.active }]),
					"data-active": e.active ? "" : void 0,
					"aria-label": `筛选${e.label}`,
					title: e.active ? `${e.label}：${e.summary || "已筛选"}` : `筛选${e.label}`
				}, [M("span", pi, A(e.triggerLabel || e.label), 1), r[2] ||= M("svg", {
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
				})], -1)], 10, fi)]),
				_: 1
			}), _(F(ui), null, {
				default: o(() => [_(F(li), {
					class: "tc-filter-popover list-filter-popover",
					"aria-label": `筛选${e.label}`,
					side: "bottom",
					align: "start",
					"side-offset": 6,
					"collision-padding": 10,
					"hide-when-detached": "",
					onEscapeKeyDown: r[0] ||= (e) => {
						e.preventDefault(), n("update:open", !1);
					}
				}, {
					default: o(() => [
						M("div", mi, "筛选" + A(e.label), 1),
						g(t.$slots, "default", {}, void 0, !0),
						_(F(ai), {
							class: "tc-filter-popover-close list-filter-popover__close",
							"aria-label": `关闭${e.label}筛选`,
							title: "关闭筛选"
						}, {
							default: o(() => [...r[3] ||= [M("svg", {
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
}), [["__scopeId", "data-v-9714d7b0"]]), gi = ["title"], _i = {
	key: 0,
	class: "list-cell-secondary"
}, vi = /*#__PURE__*/ fe(/* @__PURE__ */ n({
	__name: "ListCell",
	props: {
		text: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(e) {
		return (t, n) => (a(), I("div", {
			class: ae(["list-cell", `list-cell--${e.tone}`]),
			title: e.title ?? [e.text, e.secondary].filter(Boolean).join(" · ")
		}, [M("div", { class: ae(["list-cell-primary", { "list-cell-single": !!e.secondary }]) }, [g(t.$slots, "default", {}, () => [_e(A(e.text), 1)], !0)], 2), e.secondary ? (a(), I("div", _i, A(e.secondary), 1)) : T("", !0)], 10, gi));
	}
}), [["__scopeId", "data-v-5767b82c"]]), yi = { class: "ui-table__state-row" }, bi = ["colspan"], xi = ["role"], Si = {
	key: 0,
	class: "ui-spinner",
	"aria-hidden": "true"
}, Ci = { key: 1 }, wi = /* @__PURE__ */ n({
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
	setup(e, { emit: t }) {
		let n = e, r = t, i = () => !n.loading && !!n.error;
		return (t, n) => (a(), I("tr", yi, [M("td", { colspan: e.colspan }, [M("div", {
			class: ae(["ui-table-state", { "is-error": i() }]),
			role: i() ? "alert" : "status"
		}, [
			e.loading ? (a(), I("span", Si)) : T("", !0),
			M("strong", null, A(e.loading ? e.loadingTitle : i() ? e.errorTitle : e.title), 1),
			(e.loading ? e.loadingText : i() ? typeof e.error == "string" && e.error.trim() : e.text) ? (a(), I("p", Ci, A(e.loading ? e.loadingText : i() ? e.error : e.text), 1)) : T("", !0),
			i() && e.retryLabel ? (a(), I("button", {
				key: 2,
				type: "button",
				class: "ui-button",
				onClick: n[0] ||= (e) => r("retry")
			}, A(e.retryLabel), 1)) : T("", !0),
			g(t.$slots, "default")
		], 10, xi)], 8, bi)]));
	}
}), Ti = ["aria-label"], Ei = [
	"aria-label",
	"title",
	"onClick"
], Di = /*#__PURE__*/ fe(/* @__PURE__ */ n({
	__name: "ListFilterSummary",
	props: {
		items: {},
		label: { default: "已应用筛选" }
	},
	emits: ["remove"],
	setup(e, { emit: t }) {
		let n = t;
		return (t, r) => e.items.length ? (a(), I("div", {
			key: 0,
			class: "list-filter-summary",
			role: "group",
			"aria-label": e.label
		}, [(a(!0), I(D, null, u(e.items, (e) => (a(), I("button", {
			key: e.key,
			type: "button",
			class: "list-filter-chip",
			"aria-label": e.removeLabel,
			title: e.title || e.label,
			onClick: (t) => n("remove", e.key)
		}, [M("span", null, A(e.label), 1), r[0] ||= M("span", { "aria-hidden": "true" }, "×", -1)], 8, Ei))), 128))], 8, Ti)) : T("", !0);
	}
}), [["__scopeId", "data-v-9c3f6cac"]]);
export { ve as S, z as _, di as a, He as b, ii as c, Ft as d, B as f, ut as g, bt as h, hi as i, Xt as l, xt as m, wi as n, ui as o, Et as p, vi as r, li as s, Di as t, Yt as u, at as v, L as x, tt as y };
