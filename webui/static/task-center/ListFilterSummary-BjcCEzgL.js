import { A as e, B as t, C as n, D as r, E as i, F as a, G as o, H as s, I as c, J as l, L as u, M as d, N as f, O as p, P as m, Q as h, R as g, S as _, T as v, U as y, V as b, W as x, X as S, Y as C, Z as w, _ as T, at as E, ct as ee, d as D, dt as O, et as k, f as te, ft as A, g as j, h as M, it as ne, j as re, k as N, l as ie, lt as ae, m as P, nt as oe, ot as se, p as ce, pt as le, q as ue, rt as de, st as F, t as fe, tt as pe, u as me, ut as he, v as ge, w as _e, x as ve } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/createContext.js
function ye(e, t) {
	let n = typeof e == "string" && !t ? `${e}Context` : t, i = Symbol(n);
	return [(t) => {
		let n = r(i, t);
		if (n || n === null) return n;
		throw Error(`Injection \`${i.toString()}\` not found. Component must be used within ${Array.isArray(e) ? `one of the following components: ${e.join(", ")}` : `\`${e}\``}`);
	}, (e) => (c(i, e), e)];
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/getActiveElement.js
function I() {
	let e = document.activeElement;
	if (e == null) return null;
	for (; e != null && e.shadowRoot != null && e.shadowRoot.activeElement != null;) e = e.shadowRoot.activeElement;
	return e;
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/handleAndDispatchCustomEvent.js
function be(e, t, n) {
	let r = n.originalEvent.target, i = new CustomEvent(e, {
		bubbles: !1,
		cancelable: !0,
		detail: n
	});
	t && r.addEventListener(e, t, { once: !0 }), r.dispatchEvent(i);
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/@vueuse/shared/dist/index.js
function xe(e, t) {
	return C() ? (w(e, t), !0) : !1;
}
function Se(e) {
	let t = !1, n, r = l(!0);
	return ((...i) => (t ||= (n = r.run(() => e(...i)), !0), n));
}
var L = typeof window < "u" && typeof document < "u";
typeof WorkerGlobalScope < "u" && globalThis instanceof WorkerGlobalScope;
var Ce = (e) => e !== void 0, we = Object.prototype.toString, Te = (e) => we.call(e) === "[object Object]", Ee = /* #__PURE__ */ De();
function De() {
	var e, t;
	return L && !!((e = window) != null && (e = e.navigator) != null && e.userAgent) && (/iP(?:ad|hone|od)/.test(window.navigator.userAgent) || ((t = window) == null || (t = t.navigator) == null ? void 0 : t.maxTouchPoints) > 2 && /iPad|Macintosh/.test(window?.navigator.userAgent));
}
function Oe(e) {
	return Array.isArray(e) ? e : [e];
}
function ke(e) {
	return e || _e();
}
function Ae(e) {
	if (!L) return e;
	let t = 0, n, r, i = () => {
		--t, r && t <= 0 && (r.stop(), n = void 0, r = void 0);
	};
	return ((...a) => (t += 1, r || (r = l(!0), n = r.run(() => e(...a))), xe(i), n));
}
function je(e) {
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
function Me(e) {
	return je(P(e));
}
function Ne(e, ...t) {
	let n = t.flat(), r = n[0];
	return Me(() => Object.fromEntries(typeof r == "function" ? Object.entries(ne(e)).filter(([e, t]) => !r(E(t), e)) : Object.entries(ne(e)).filter((e) => !n.includes(e[0]))));
}
function Pe(e, t) {
	ke(t) && re(e, t);
}
function Fe(e, t, n) {
	return s(e, t, {
		...n,
		immediate: !0
	});
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/@vueuse/core/dist/index.js
var Ie = L ? window : void 0;
L && window.document, L && window.navigator, L && window.location;
function Le(e) {
	let t = E(e);
	return t?.$el ?? t;
}
function Re(...e) {
	let t = (e, t, n, r) => (e.addEventListener(t, n, r), () => e.removeEventListener(t, n, r)), n = P(() => {
		let t = Oe(E(e[0])).filter((e) => e != null);
		return t.every((e) => typeof e != "string") ? t : void 0;
	});
	return Fe(() => [
		n.value?.map((e) => Le(e)) ?? [Ie].filter((e) => e != null),
		Oe(E(n.value ? e[1] : e[0])),
		Oe(F(n.value ? e[2] : e[1])),
		E(n.value ? e[3] : e[2])
	], ([e, n, r, i], a, o) => {
		if (!e?.length || !n?.length || !r?.length) return;
		let s = Te(i) ? { ...i } : i, c = e.flatMap((e) => n.flatMap((n) => r.map((r) => t(e, n, r, s))));
		o(() => {
			c.forEach((e) => e());
		});
	}, { flush: "post" });
}
function ze() {
	let e = oe(!1), t = _e();
	return t && d(() => {
		e.value = !0;
	}, t), e;
}
function Be(e) {
	return typeof e == "function" ? e : typeof e == "string" ? (t) => t.key === e : Array.isArray(e) ? (t) => e.includes(t.key) : () => !0;
}
function Ve(...e) {
	let t, n, r = {};
	e.length === 3 ? (t = e[0], n = e[1], r = e[2]) : e.length === 2 ? typeof e[1] == "object" ? (t = !0, n = e[0], r = e[1]) : (t = e[0], n = e[1]) : (t = !0, n = e[0]);
	let { target: i = Ie, eventName: a = "keydown", passive: o = !1, dedupe: s = !1 } = r, c = Be(t);
	return Re(i, a, (e) => {
		e.repeat && E(s) || c(e) && n(e);
	}, o);
}
function He(e) {
	return JSON.parse(JSON.stringify(e));
}
function Ue(t, n, r, i = {}) {
	var a, o;
	let { clone: c = !1, passive: l = !1, eventName: u, deep: d = !1, defaultValue: f, shouldEmit: p } = i, m = _e(), h = r || m?.emit || (m == null || (a = m.$emit) == null ? void 0 : a.bind(m)) || (m == null || (o = m.proxy) == null || (o = o.$emit) == null ? void 0 : o.bind(m?.proxy)), g = u;
	n ||= "modelValue", g ||= `update:${n.toString()}`;
	let _ = (e) => c ? typeof c == "function" ? c(e) : He(e) : e, v = () => Ce(t[n]) ? _(t[n]) : f, y = (e) => {
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/renderSlotFragments.js
function We(e) {
	return e ? e.flatMap((e) => e.type === D ? We(e.children) : [e]) : [];
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/ConfigProvider/ConfigProvider.js
var [Ge, Ke] = /*#__PURE__*/ ye("ConfigProvider"), qe = /* @__PURE__ */ new WeakMap();
function Je(e, t) {
	let n = qe.get(e);
	n || (n = {
		owners: /* @__PURE__ */ new Set(),
		original: e.body.style.pointerEvents
	}, qe.set(e, n)), n.owners.add(t), e.body.style.pointerEvents = "none";
}
function Ye(e, t) {
	let n = qe.get(e);
	n?.owners.delete(t) && n.owners.size === 0 && (qe.delete(e), e.body.style.pointerEvents = n.original);
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/defu/dist/defu.mjs
function Xe(e) {
	if (typeof e != "object" || !e) return !1;
	let t = Object.getPrototypeOf(e);
	return t !== null && t !== Object.prototype && Object.getPrototypeOf(t) !== null || Symbol.iterator in e ? !1 : Symbol.toStringTag in e ? Object.prototype.toString.call(e) === "[object Module]" : !0;
}
function Ze(e, t, n = ".", r) {
	if (!Xe(t)) return Ze(e, {}, n, r);
	let i = { ...t };
	for (let t of Object.keys(e)) {
		if (t === "__proto__" || t === "constructor") continue;
		let a = e[t];
		a != null && (r && r(i, t, a, n) || (i[t] = Array.isArray(a) && Array.isArray(i[t]) ? [...a, ...i[t]] : Xe(a) && Xe(i[t]) ? Ze(a, i[t], (n ? `${n}.` : "") + t.toString(), r) : a));
	}
	return i;
}
function Qe(e) {
	return (...t) => t.reduce((t, n) => Ze(t, n, "", e), {});
}
var $e = Qe(), et = Symbol("useBodyScrollLock"), tt = Ae(() => {
	let t = k(/* @__PURE__ */ new Map()), n = k(), r = P(() => {
		for (let e of t.value.values()) if (e) return !0;
		return !1;
	}), i = Ge({ scrollBody: k(!0) }), a = null, o = () => {
		document.body.style.paddingRight = "", document.body.style.marginRight = "", Ye(document, et), document.documentElement.style.removeProperty("--scrollbar-width"), document.body.style.overflow = n.value ?? "", Ee && a?.(), n.value = void 0;
	};
	return s(r, (t, s) => {
		if (!L) return;
		if (!t) {
			s && o();
			return;
		}
		n.value === void 0 && (n.value = document.body.style.overflow);
		let c = window.innerWidth - document.documentElement.clientWidth, l = {
			padding: c,
			margin: 0
		}, u = i.scrollBody?.value ? typeof i.scrollBody.value == "object" ? $e({
			padding: i.scrollBody.value.padding === !0 ? c : i.scrollBody.value.padding,
			margin: i.scrollBody.value.margin === !0 ? c : i.scrollBody.value.margin
		}, l) : l : {
			padding: 0,
			margin: 0
		};
		c > 0 && (document.body.style.paddingRight = typeof u.padding == "number" ? `${u.padding}px` : String(u.padding), document.body.style.marginRight = typeof u.margin == "number" ? `${u.margin}px` : String(u.margin), document.documentElement.style.setProperty("--scrollbar-width", `${c}px`), document.body.style.overflow = "hidden"), Ee && (a = Re(document, "touchmove", (e) => it(e), { passive: !1 })), e(() => {
			r.value && (Je(document, et), document.body.style.overflow = "hidden");
		});
	}, {
		immediate: !0,
		flush: "sync"
	}), t;
});
function nt(e) {
	let t = Math.random().toString(36).substring(2, 7), n = tt();
	n.value.set(t, e ?? !1);
	let r = P({
		get: () => n.value.get(t) ?? !1,
		set: (e) => n.value.set(t, e)
	});
	return Pe(() => {
		n.value.delete(t);
	}), r;
}
function rt(e) {
	let t = window.getComputedStyle(e);
	if (t.overflowX === "scroll" || t.overflowY === "scroll" || t.overflowX === "auto" && e.clientWidth < e.scrollWidth || t.overflowY === "auto" && e.clientHeight < e.scrollHeight) return !0;
	{
		let t = e.parentNode;
		return !(t instanceof Element) || t.tagName === "BODY" ? !1 : rt(t);
	}
}
function it(e) {
	let t = e || window.event, n = t.target;
	return n instanceof Element && rt(n) ? !1 : t.touches.length > 1 || (t.preventDefault && t.cancelable && t.preventDefault(), !1);
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useDirection.js
function at(e) {
	let t = Ge({ dir: k("ltr") });
	return P(() => e?.value || t.dir?.value || "ltr");
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useEmitAsProps.js
function ot(e) {
	let t = _e(), n = t?.type.emits, r = {};
	return n?.length || console.warn(`No emitted event found. Please check component: ${t?.type.__name}`), n?.forEach((t) => {
		r[le(ee(t))] = (...n) => e(t, ...n);
	}), r;
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useFocusGuards.js
var st = 0;
function ct() {
	y((e) => {
		if (!L) return;
		let t = document.querySelectorAll("[data-reka-focus-guard]");
		document.body.insertAdjacentElement("afterbegin", t[0] ?? lt()), document.body.insertAdjacentElement("beforeend", t[1] ?? lt()), st++, e(() => {
			st === 1 && document.querySelectorAll("[data-reka-focus-guard]").forEach((e) => e.remove()), st--;
		});
	});
}
function lt() {
	let e = document.createElement("span");
	return e.setAttribute("data-reka-focus-guard", ""), e.tabIndex = 0, e.style.outline = "none", e.style.opacity = "0", e.style.position = "fixed", e.style.pointerEvents = "none", e;
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useForwardExpose.js
function R() {
	let e = _e(), t = k(), n = P(() => r());
	m(() => {
		n.value !== r() && se(t);
	});
	function r() {
		return t.value && "$el" in t.value && ["#text", "#comment"].includes(t.value.$el.nodeName) ? t.value.$el.nextElementSibling : Le(t);
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useForwardProps.js
function ut(e) {
	let t = _e(), n = Object.keys(t?.type.props ?? {}).reduce((e, n) => {
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useForwardPropsEmits.js
function dt(e, t) {
	let n = ut(e), r = t ? ot(t) : {};
	return P(() => ({
		...n.value,
		...r
	}));
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/aria-hidden/dist/es2015/index.js
var ft = function(e) {
	return typeof document > "u" ? null : (Array.isArray(e) ? e[0] : e).ownerDocument.body;
}, pt = /* @__PURE__ */ new WeakMap(), mt = /* @__PURE__ */ new WeakMap(), ht = {}, gt = 0, _t = function(e) {
	return e && (e.host || _t(e.parentNode));
}, vt = function(e, t) {
	return t.map(function(t) {
		if (e.contains(t)) return t;
		var n = _t(t);
		return n && e.contains(n) ? n : (console.error("aria-hidden", t, "in not contained inside", e, ". Doing nothing"), null);
	}).filter(function(e) {
		return !!e;
	});
}, yt = function(e, t, n, r) {
	var i = vt(t, Array.isArray(e) ? e : [e]);
	ht[n] || (ht[n] = /* @__PURE__ */ new WeakMap());
	var a = ht[n], o = [], s = /* @__PURE__ */ new Set(), c = new Set(i), l = function(e) {
		e && !s.has(e) && (s.add(e), l(e.parentNode));
	};
	i.forEach(l);
	var u = function(e) {
		e && !c.has(e) && Array.prototype.forEach.call(e.children, function(e) {
			if (s.has(e)) u(e);
			else try {
				var t = e.getAttribute(r), i = t !== null && t !== "false", c = (pt.get(e) || 0) + 1, l = (a.get(e) || 0) + 1;
				pt.set(e, c), a.set(e, l), o.push(e), c === 1 && i && mt.set(e, !0), l === 1 && e.setAttribute(n, "true"), i || e.setAttribute(r, "true");
			} catch (t) {
				console.error("aria-hidden: cannot operate on ", e, t);
			}
		});
	};
	return u(t), s.clear(), gt++, function() {
		o.forEach(function(e) {
			var t = pt.get(e) - 1, i = a.get(e) - 1;
			pt.set(e, t), a.set(e, i), t || (mt.has(e) || e.removeAttribute(r), mt.delete(e)), i || e.removeAttribute(n);
		}), gt--, gt || (pt = /* @__PURE__ */ new WeakMap(), pt = /* @__PURE__ */ new WeakMap(), mt = /* @__PURE__ */ new WeakMap(), ht = {});
	};
}, bt = function(e, t, n) {
	n === void 0 && (n = "data-aria-hidden");
	var r = Array.from(Array.isArray(e) ? e : [e]), i = t || ft(e);
	return i ? (r.push.apply(r, Array.from(i.querySelectorAll("[aria-live], script"))), yt(r, i, n, "aria-hidden")) : function() {
		return null;
	};
};
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useHideOthers.js
function xt(e) {
	let t;
	s(() => Le(e), (e) => {
		let n = !1;
		try {
			n = !!e?.closest("[popover]:not(:popover-open)");
		} catch {}
		e && !n ? t = bt(e) : t && t();
	}), f(() => {
		t && t();
	});
}
function St(e, t = "reka") {
	if (e) return e;
	let n, r = Ge({ useId: void 0 });
	return n = r.useId ? r.useId() : b?.(), t ? `${t}-${n}` : n;
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useSize.js
function Ct(e) {
	let t = k(), n = P(() => t.value?.width ?? 0), r = P(() => t.value?.height ?? 0), i;
	return d(() => {
		let n = Le(e);
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/shared/useStateMachine.js
function wt(e, t) {
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/Presence/usePresence.js
function Tt(t, n) {
	let r = k({}), i = k("none"), a = k(t), o = t.value ? "mounted" : "unmounted", c, l = n.value?.ownerDocument.defaultView ?? Ie, { state: u, dispatch: d } = wt(o, {
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
		if (L) {
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
			let e = i.value, o = Et(n.value);
			t ? (d("MOUNT"), p("enter"), o === "none" && p("after-enter")) : o === "none" || o === "undefined" || r.value?.display === "none" ? (d("UNMOUNT"), p("leave"), p("after-leave")) : a && e !== o ? (d("ANIMATION_OUT"), p("leave")) : (d("UNMOUNT"), p("after-leave"));
		}
	}, { immediate: !0 });
	let m = (e) => {
		if (e.target !== n.value) return;
		let t = Et(n.value), r = t.includes(CSS.escape(e.animationName)), i = u.value === "mounted" ? "enter" : "leave";
		if (r && (p(`after-${i}`), d("ANIMATION_END"), !a.value)) {
			let e = n.value.style.animationFillMode;
			n.value.style.animationFillMode = "forwards", c = l?.setTimeout(() => {
				n.value?.style.animationFillMode === "forwards" && (n.value.style.animationFillMode = e);
			});
		}
		t === "none" && d("ANIMATION_END");
	}, h = (e) => {
		e.target === n.value && (i.value = Et(n.value));
	}, g = s(n, (e, t) => {
		e ? (r.value = getComputedStyle(e), e.addEventListener("animationstart", h), e.addEventListener("animationcancel", m), e.addEventListener("animationend", m)) : (d("ANIMATION_END"), c !== void 0 && l?.clearTimeout(c), t?.removeEventListener("animationstart", h), t?.removeEventListener("animationcancel", m), t?.removeEventListener("animationend", m));
	}, { immediate: !0 }), _ = s(u, () => {
		let e = Et(n.value);
		i.value = u.value === "mounted" ? e : "none";
	});
	return f(() => {
		g(), _(), n.value && (n.value.removeEventListener("animationstart", h), n.value.removeEventListener("animationcancel", m), n.value.removeEventListener("animationend", m)), c !== void 0 && l?.clearTimeout(c);
	}), { isPresent: P(() => ["mounted", "unmountSuspended"].includes(u.value)) };
}
function Et(e) {
	return e && getComputedStyle(e).animationName || "none";
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/Presence/Presence.js
var Dt = /*#__PURE__*/ n({
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
		let { present: r, forceMount: a } = ne(e), o = k(), { isPresent: s } = Tt(r, o);
		n({ present: s });
		let c = t.default({ present: s.value });
		c = We(c || []);
		let l = _e();
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
			let t = Le(e);
			return t?.hasAttribute === void 0 || (t?.hasAttribute("data-reka-popper-content-wrapper") ? o.value = t.firstElementChild : o.value = t), t;
		} }) : null;
	}
}), Ot = /*#__PURE__*/ n({
	name: "PrimitiveSlot",
	inheritAttrs: !1,
	setup(e, { attrs: t, slots: n }) {
		return () => {
			if (!n.default) return null;
			let e = We(n.default()), r = e.findIndex((e) => e.type !== me);
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
}), kt = [
	"area",
	"img",
	"input"
], z = /*#__PURE__*/ n({
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
		return typeof r == "string" && kt.includes(r) ? () => i(r, t) : r === "template" ? () => i(Ot, t, { default: n.default }) : () => i(e.as, t, { default: n.default });
	}
}), At = "dismissableLayer.pointerDownOutside", jt = "dismissableLayer.focusOutside";
function Mt(e) {
	if (typeof e != "object" || !e) return !1;
	let t = e.ownerDocument?.defaultView;
	return typeof Element < "u" && e instanceof Element || !!t && e instanceof t.Element;
}
function Nt(e, t) {
	if (!Mt(t)) return !1;
	if (e.contains(t)) return !0;
	let n = t.closest("[data-dismissable-layer]"), r = e.dataset.dismissableLayer === "" ? e : e.querySelector("[data-dismissable-layer]"), i = Array.from(e.ownerDocument.querySelectorAll("[data-dismissable-layer]"));
	return !!(n && (r === n || i.indexOf(r) < i.indexOf(n)));
}
function Pt(e, t, n = !0) {
	let r = k(!1), i = k(() => {});
	return y((a) => {
		if (!L || !E(n)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			let a = n.target;
			if (t?.value && a) {
				if (Nt(t.value, a)) o.removeEventListener("click", i.value), r.value = !1;
				else {
					if (n.target && !r.value) {
						let t = { originalEvent: n };
						function r() {
							be(At, e, t);
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
function Ft(t, n, r = !0) {
	let i = k(!1);
	return y((a) => {
		if (!L || !E(r)) return;
		let o = n?.value?.ownerDocument ?? globalThis.document, s = async (r) => {
			if (!n?.value) return;
			await e(), await e();
			let a = r.target;
			n.value && a && !Nt(n.value, a) && r.target && !i.value && be(jt, t, { originalEvent: r });
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/DismissableLayer/context.js
var B = /*#__PURE__*/ h({
	layersRoot: /* @__PURE__ */ new Set(),
	layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
	branches: /* @__PURE__ */ new Set()
}), It = /* @__PURE__ */ n({
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
		let r = t, i = n, { forwardRef: c, currentElement: l } = R(), u = P(() => l.value?.ownerDocument ?? globalThis.document), d = P(() => B.layersRoot), f = P(() => l.value ? Array.from(d.value).indexOf(l.value) : -1), p = P(() => B.layersWithOutsidePointerEventsDisabled.size > 0), m = P(() => {
			let e = Array.from(d.value), [t] = [...B.layersWithOutsidePointerEventsDisabled].slice(-1), n = e.indexOf(t);
			return f.value >= n;
		}), h = Pt(async (t) => {
			let n = [...B.branches].some((e) => e?.contains(t.target));
			r.present && m.value && !n && (i("pointerDownOutside", t), i("interactOutside", t), await e(), t.defaultPrevented || i("dismiss"));
		}, l, () => r.present), _ = Ft((e) => {
			let t = [...B.branches].some((t) => t?.contains(e.target));
			r.present && !t && (i("focusOutside", e), i("interactOutside", e), e.defaultPrevented || i("dismiss"));
		}, l);
		return Ve("Escape", (e) => {
			r.present && f.value === d.value.size - 1 && (i("escapeKeyDown", e), e.defaultPrevented || i("dismiss"));
		}, { target: () => u.value?.defaultView ?? globalThis.window }), s([
			l,
			() => r.disableOutsidePointerEvents,
			() => r.present
		], ([e, t, n], r, i) => {
			if (e && n && t) {
				let t = e.ownerDocument;
				Je(t, e), B.layersWithOutsidePointerEventsDisabled.add(e), i(() => {
					B.layersWithOutsidePointerEventsDisabled.delete(e), Ye(t, e);
				});
			}
		}, { immediate: !0 }), s([l, () => r.present], ([e, t], n, r) => {
			e && t && (d.value.add(e), r(() => {
				d.value.delete(e);
			}));
		}, { immediate: !0 }), y((e) => {
			e(() => {
				l.value && (d.value.delete(l.value), B.layersWithOutsidePointerEventsDisabled.delete(l.value));
			});
		}), (e, n) => (a(), j(F(z), {
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
}), Lt = Se(() => k([]));
function Rt() {
	let e = Lt();
	return {
		add(t) {
			let n = e.value[0];
			t !== n && n?.pause(), e.value = zt(e.value, t), e.value.unshift(t);
		},
		remove(t) {
			e.value = zt(e.value, t), e.value[0]?.resume();
		}
	};
}
function zt(e, t) {
	let n = [...e], r = n.indexOf(t);
	return r !== -1 && n.splice(r, 1), n;
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/FocusScope/utils.js
var Bt = "focusScope.autoFocusOnMount", Vt = "focusScope.autoFocusOnUnmount", Ht = {
	bubbles: !1,
	cancelable: !0
};
function Ut(e, t) {
	let n = t;
	for (; n;) {
		if (e.contains(n)) return !0;
		n = n.getRootNode().host ?? null;
	}
	return !1;
}
function Wt(e, { select: t = !1 } = {}) {
	let n = I();
	for (let r of e) if (V(r, { select: t }), I() !== n) return !0;
}
function Gt(e) {
	let t = Kt(e);
	return [qt(t, e), qt(t.reverse(), e)];
}
function Kt(e) {
	let t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, { acceptNode: (e) => {
		let t = e.tagName === "INPUT" && e.type === "hidden";
		return e.disabled || e.hidden || t ? NodeFilter.FILTER_SKIP : e.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
	} });
	for (; n.nextNode();) t.push(n.currentNode);
	return t.sort((e, t) => e.tabIndex === t.tabIndex ? 0 : e.tabIndex === 0 ? 1 : t.tabIndex === 0 ? -1 : e.tabIndex - t.tabIndex);
}
function qt(e, t) {
	for (let n of e) if (!Jt(n, { upTo: t })) return n;
}
function Jt(e, { upTo: t }) {
	if (getComputedStyle(e).visibility === "hidden") return !0;
	for (; e;) {
		if (t !== void 0 && e === t) return !1;
		if (getComputedStyle(e).display === "none") return !0;
		e = e.parentElement;
	}
	return !1;
}
function Yt(e) {
	return e instanceof HTMLInputElement && "select" in e;
}
function V(e, { select: t = !1 } = {}) {
	if (e && e.focus) {
		let n = I();
		e.focus({ preventScroll: !0 }), e !== n && Yt(e) && t && e.select();
	}
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/FocusScope/FocusScope.js
var Xt = /* @__PURE__ */ n({
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
		let r = t, i = n, { currentRef: c, currentElement: l } = R(), u = k(null), d = Rt(), f = /*#__PURE__*/ h({
			paused: !1,
			pause() {
				this.paused = !0;
			},
			resume() {
				this.paused = !1;
			}
		});
		y((e) => {
			if (!L) return;
			let t = l.value;
			if (!r.trapped) return;
			let n = t?.ownerDocument ?? document, i = t ? t.getRootNode() : n;
			function a(e) {
				if (f.paused || !t) return;
				let n = e.target;
				t.contains(n) ? u.value = n : V(u.value, { select: !0 });
			}
			function o(e) {
				if (f.paused || !t) return;
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
				if (f.paused || !t) return;
				let n = e.composedPath()[0];
				Ut(t, n) || V(u.value, { select: !0 });
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
			let n = new CustomEvent(Bt, Ht), r = (e) => i("mountAutoFocus", e);
			e.addEventListener(Bt, r), e.dispatchEvent(n), e.removeEventListener(Bt, r), n.defaultPrevented || (Wt(Kt(e), { select: !0 }), I() === t && V(e));
		}
		y(async (t) => {
			let n = l.value;
			if (await e(), !n) return;
			r.present !== !1 && d.add(f);
			let a = I();
			!n.contains(a) && r.present !== !1 && p(n, a), t(() => {
				let e = new CustomEvent(Vt, Ht), t = (e) => {
					i("unmountAutoFocus", e);
				};
				n.addEventListener(Vt, t), n.dispatchEvent(e), n.setAttribute("data-focus-scope-unmounting", ""), setTimeout(() => {
					e.defaultPrevented || V(a ?? document.body, { select: !0 }), n.removeEventListener(Vt, t), d.remove(f), n.removeAttribute("data-focus-scope-unmounting");
				}, 0);
			});
		}), s(() => r.present, async (t, n) => {
			if (!L) return;
			if (t === !1 && n === !0) {
				d.remove(f);
				return;
			}
			if (t !== !0 || n !== !1) return;
			d.add(f), await e();
			let r = l.value;
			if (!r) return;
			let i = I();
			r.contains(i) || p(r, i);
		});
		function m(e) {
			if (!r.loop && !r.trapped || f.paused) return;
			let t = e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey, n = I();
			if (t && n) {
				let t = e.currentTarget, [i, a] = Gt(t);
				i && a ? !e.shiftKey && n === a ? (e.preventDefault(), r.loop && V(i, { select: !0 })) : e.shiftKey && n === i && (e.preventDefault(), r.loop && V(a, { select: !0 })) : n === t && e.preventDefault();
			}
		}
		return (e, n) => (a(), j(F(z), {
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
}), Zt = /* @__PURE__ */ n({
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
		let t = e, n = Ge({}), r = P(() => t.to ?? n.teleportTo?.value ?? "body"), i = ze();
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
}), [Qt, $t] = /*#__PURE__*/ ye("PopperRoot"), en = /* @__PURE__ */ n({
	inheritAttrs: !1,
	__name: "PopperRoot",
	setup(e) {
		let t = k();
		return $t({
			anchor: t,
			onAnchorChange: (e) => t.value = e
		}), (e, t) => g(e.$slots, "default");
	}
}), tn = /* @__PURE__ */ n({
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
		let t = e, { forwardRef: n, currentElement: r } = R(), i = Qt();
		return x(() => {
			i.onAnchorChange(t.reference ?? r.value);
		}), (t, r) => (a(), j(F(z), {
			ref: F(n),
			as: e.as,
			"as-child": e.asChild
		}, {
			default: o(() => [g(t.$slots, "default")]),
			_: 3
		}, 8, ["as", "as-child"]));
	}
});
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/Popper/utils.js
function nn(e) {
	return e !== null;
}
function rn(e) {
	return {
		name: "transformOrigin",
		options: e,
		fn(t) {
			let { placement: n, rects: r, middlewareData: i } = t, a = i.arrow?.centerOffset !== 0, o = a ? 0 : e.arrowWidth, s = a ? 0 : e.arrowHeight, [c, l] = an(n), u = {
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
function an(e) {
	let [t, n = "center"] = e.split("-");
	return [t, n];
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs
var on = [
	"top",
	"right",
	"bottom",
	"left"
], H = Math.min, U = Math.max, sn = Math.round, cn = Math.floor, W = (e) => ({
	x: e,
	y: e
}), ln = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function un(e, t, n) {
	return U(e, H(t, n));
}
function G(e, t) {
	return typeof e == "function" ? e(t) : e;
}
function K(e) {
	return e.split("-")[0];
}
function dn(e) {
	return e.split("-")[1];
}
function fn(e) {
	return e === "x" ? "y" : "x";
}
function pn(e) {
	return e === "y" ? "height" : "width";
}
function q(e) {
	let t = e[0];
	return t === "t" || t === "b" ? "y" : "x";
}
function mn(e) {
	return fn(q(e));
}
function hn(e, t, n) {
	n === void 0 && (n = !1);
	let r = dn(e), i = mn(e), a = pn(i), o = i === "x" ? r === (n ? "end" : "start") ? "right" : "left" : r === "start" ? "bottom" : "top";
	return t.reference[a] > t.floating[a] && (o = wn(o)), [o, wn(o)];
}
function gn(e) {
	let t = wn(e);
	return [
		_n(e),
		t,
		_n(t)
	];
}
function _n(e) {
	return e.includes("start") ? e.replace("start", "end") : e.replace("end", "start");
}
var vn = ["left", "right"], yn = ["right", "left"], bn = ["top", "bottom"], xn = ["bottom", "top"];
function Sn(e, t, n) {
	switch (e) {
		case "top":
		case "bottom": return n ? t ? yn : vn : t ? vn : yn;
		case "left":
		case "right": return t ? bn : xn;
		default: return [];
	}
}
function Cn(e, t, n, r) {
	let i = dn(e), a = Sn(K(e), n === "start", r);
	return i && (a = a.map((e) => e + "-" + i), t && (a = a.concat(a.map(_n)))), a;
}
function wn(e) {
	let t = K(e);
	return ln[t] + e.slice(t.length);
}
function Tn(e) {
	return {
		top: e.top ?? 0,
		right: e.right ?? 0,
		bottom: e.bottom ?? 0,
		left: e.left ?? 0
	};
}
function En(e) {
	return typeof e == "number" ? {
		top: e,
		right: e,
		bottom: e,
		left: e
	} : Tn(e);
}
function Dn(e) {
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/@floating-ui/core/dist/floating-ui.core.mjs
function On(e, t, n) {
	let { reference: r, floating: i } = e, a = q(t), o = mn(t), s = pn(o), c = K(t), l = a === "y", u = r.x + r.width / 2 - i.width / 2, d = r.y + r.height / 2 - i.height / 2, f = r[s] / 2 - i[s] / 2, p;
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
	let m = dn(t);
	return m && (p[o] += f * (m === "end" ? 1 : -1) * (n && l ? -1 : 1)), p;
}
async function kn(e, t) {
	t === void 0 && (t = {});
	let { x: n, y: r, platform: i, rects: a, elements: o, strategy: s } = e, { boundary: c = "clippingAncestors", rootBoundary: l = "viewport", elementContext: u = "floating", altBoundary: d = !1, padding: f = 0 } = G(t, e), p = En(f), m = o[d ? u === "floating" ? "reference" : "floating" : u], h = Dn(await i.getClippingRect({
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
	}, y = Dn(i.convertOffsetParentRelativeRectToViewportRelativeRect ? await i.convertOffsetParentRelativeRectToViewportRelativeRect({
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
var An = 50, jn = async (e, t, n) => {
	let { placement: r = "bottom", strategy: i = "absolute", middleware: a = [], platform: o } = n, s = o.detectOverflow ? o : {
		...o,
		detectOverflow: kn
	}, c = await (o.isRTL == null ? void 0 : o.isRTL(t)), l = await o.getElementRects({
		reference: e,
		floating: t,
		strategy: i
	}), { x: u, y: d } = On(l, r, c), f = r, p = 0, m = {};
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
		}, x && p < An && (p++, typeof x == "object" && (x.placement && (f = x.placement), x.rects && (l = x.rects === !0 ? await o.getElementRects({
			reference: e,
			floating: t,
			strategy: i
		}) : x.rects), {x: u, y: d} = On(l, f, c)), n = -1);
	}
	return {
		x: u,
		y: d,
		placement: f,
		strategy: i,
		middlewareData: m
	};
}, Mn = (e) => ({
	name: "arrow",
	options: e,
	async fn(t) {
		let { x: n, y: r, placement: i, rects: a, platform: o, elements: s, middlewareData: c } = t, { element: l, padding: u = 0 } = G(e, t) || {};
		if (l == null) return {};
		let d = En(u), f = {
			x: n,
			y: r
		}, p = mn(i), m = pn(p), h = await o.getDimensions(l), g = p === "y", _ = g ? "top" : "left", v = g ? "bottom" : "right", y = g ? "clientHeight" : "clientWidth", b = a.reference[m] + a.reference[p] - f[p] - a.floating[m], x = f[p] - a.reference[p], S = await (o.getOffsetParent == null ? void 0 : o.getOffsetParent(l)), C = S ? S[y] : 0;
		C && await (o.isElement == null ? void 0 : o.isElement(S)) || (C = s.floating[y] || a.floating[m]);
		let w = b / 2 - x / 2, T = C / 2 - h[m] / 2 - 1, E = H(d[_], T), ee = H(d[v], T), D = C - h[m] - ee, O = C / 2 - h[m] / 2 + w, k = un(E, O, D), te = !c.arrow && dn(i) != null && O !== k && a.reference[m] / 2 - (O < E ? E : ee) - h[m] / 2 < 0, A = te ? O < E ? O - E : O - D : 0;
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
}), Nn = function(e) {
	return e === void 0 && (e = {}), {
		name: "flip",
		options: e,
		async fn(t) {
			var n;
			let { placement: r, middlewareData: i, rects: a, initialPlacement: o, platform: s, elements: c } = t, { mainAxis: l = !0, crossAxis: u = !0, fallbackPlacements: d, fallbackStrategy: f = "bestFit", fallbackAxisSideDirection: p = "none", flipAlignment: m = !0, ...h } = G(e, t);
			if ((n = i.arrow) != null && n.alignmentOffset) return {};
			let g = K(r), _ = q(o), v = K(o) === o, y = await (s.isRTL == null ? void 0 : s.isRTL(c.floating)), b = d || (v || !m ? [wn(o)] : gn(o)), x = p !== "none";
			!d && x && b.push(...Cn(o, m, p, y));
			let S = [o, ...b], C = await s.detectOverflow(t, h), w = [], T = i.flip?.overflows || [];
			if (l && w.push(C[g]), u) {
				let e = hn(r, a, y);
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
function Pn(e, t) {
	return {
		top: e.top - t.height,
		right: e.right - t.width,
		bottom: e.bottom - t.height,
		left: e.left - t.width
	};
}
function Fn(e) {
	return on.some((t) => e[t] >= 0);
}
var In = function(e) {
	return e === void 0 && (e = {}), {
		name: "hide",
		options: e,
		async fn(t) {
			let { rects: n, platform: r } = t, { strategy: i = "referenceHidden", ...a } = G(e, t);
			switch (i) {
				case "referenceHidden": {
					let e = Pn(await r.detectOverflow(t, {
						...a,
						elementContext: "reference"
					}), n.reference);
					return { data: {
						referenceHiddenOffsets: e,
						referenceHidden: Fn(e)
					} };
				}
				case "escaped": {
					let e = Pn(await r.detectOverflow(t, {
						...a,
						altBoundary: !0
					}), n.floating);
					return { data: {
						escapedOffsets: e,
						escaped: Fn(e)
					} };
				}
				default: return {};
			}
		}
	};
}, Ln = /*#__PURE__*/ new Set(["left", "top"]);
async function Rn(e, t) {
	let { placement: n, platform: r, elements: i } = e, a = await (r.isRTL == null ? void 0 : r.isRTL(i.floating)), o = K(n), s = dn(n), c = q(n) === "y", l = Ln.has(o) ? -1 : 1, u = a && c ? -1 : 1, d = G(t, e), { mainAxis: f, crossAxis: p, alignmentAxis: m } = typeof d == "number" ? {
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
var zn = function(e) {
	return e === void 0 && (e = 0), {
		name: "offset",
		options: e,
		async fn(t) {
			var n;
			let { x: r, y: i, placement: a, middlewareData: o } = t, s = await Rn(t, e);
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
}, Bn = function(e) {
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
			}, d = await a.detectOverflow(t, l), f = q(i), p = fn(f), m = u[p], h = u[f], g = (e, t) => un(t + d[e === "y" ? "top" : "left"], t, t - d[e === "y" ? "bottom" : "right"]);
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
}, Vn = function(e) {
	return e === void 0 && (e = {}), {
		options: e,
		fn(t) {
			let { x: n, y: r, placement: i, rects: a, middlewareData: o } = t, { offset: s = 0, mainAxis: c = !0, crossAxis: l = !0 } = G(e, t), u = {
				x: n,
				y: r
			}, d = q(i), f = fn(d), p = u[f], m = u[d], h = G(s, t), g = typeof h == "number" ? {
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
				let e = f === "y" ? "width" : "height", t = Ln.has(K(i)), n = a.reference[d] - a.floating[e] + (t && o.offset?.[d] || 0) + (t ? 0 : g.crossAxis), r = a.reference[d] + a.reference[e] + (t ? 0 : o.offset?.[d] || 0) - (t ? g.crossAxis : 0);
				m < n ? m = n : m > r && (m = r);
			}
			return {
				[f]: p,
				[d]: m
			};
		}
	};
}, Hn = function(e) {
	return e === void 0 && (e = {}), {
		name: "size",
		options: e,
		async fn(t) {
			let { placement: n, rects: r, platform: i, elements: a } = t, { apply: o = () => {}, ...s } = G(e, t), c = await i.detectOverflow(t, s), l = K(n), u = dn(n), d = q(n) === "y", { width: f, height: p } = r.floating, m, h;
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/@floating-ui/utils/dist/floating-ui.utils.dom.mjs
function Un() {
	return typeof window < "u";
}
function Wn(e) {
	return Gn(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function J(e) {
	var t;
	return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function Y(e) {
	return ((Gn(e) ? e.ownerDocument : e.document) || window.document)?.documentElement;
}
function Gn(e) {
	return Un() ? e instanceof Node || e instanceof J(e).Node : !1;
}
function X(e) {
	return Un() ? e instanceof Element || e instanceof J(e).Element : !1;
}
function Z(e) {
	return Un() ? e instanceof HTMLElement || e instanceof J(e).HTMLElement : !1;
}
function Kn(e) {
	return !Un() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof J(e).ShadowRoot;
}
function qn(e) {
	let { overflow: t, overflowX: n, overflowY: r, display: i } = $(e);
	return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && i !== "inline" && i !== "contents";
}
function Jn(e) {
	return /^(table|td|th)$/.test(Wn(e));
}
function Yn(e) {
	try {
		if (e.matches(":popover-open")) return !0;
	} catch {}
	try {
		return e.matches(":modal");
	} catch {
		return !1;
	}
}
var Xn = /transform|translate|scale|rotate|perspective|filter/, Zn = /paint|layout|strict|content/, Q = (e) => !!e && e !== "none", Qn;
function $n(e) {
	let t = X(e) ? $(e) : e;
	return Q(t.transform) || Q(t.translate) || Q(t.scale) || Q(t.rotate) || Q(t.perspective) || !tr() && (Q(t.backdropFilter) || Q(t.filter)) || Xn.test(t.willChange || "") || Zn.test(t.contain || "");
}
function er(e) {
	let t = ir(e);
	for (; Z(t) && !nr(t);) {
		if ($n(t)) return t;
		if (Yn(t)) return null;
		t = ir(t);
	}
	return null;
}
function tr() {
	return Qn ??= typeof CSS < "u" && CSS.supports && CSS.supports("-webkit-backdrop-filter", "none"), Qn;
}
function nr(e) {
	return /^(html|body|#document)$/.test(Wn(e));
}
function $(e) {
	return J(e).getComputedStyle(e);
}
function rr(e) {
	return X(e) ? {
		scrollLeft: e.scrollLeft,
		scrollTop: e.scrollTop
	} : {
		scrollLeft: e.scrollX,
		scrollTop: e.scrollY
	};
}
function ir(e) {
	if (Wn(e) === "html") return e;
	let t = e.assignedSlot || e.parentNode || Kn(e) && e.host || Y(e);
	return Kn(t) ? t.host : t;
}
function ar(e) {
	let t = ir(e);
	return nr(t) ? (e.ownerDocument || e).body : Z(t) && qn(t) ? t : ar(t);
}
function or(e, t, n) {
	t === void 0 && (t = []), n === void 0 && (n = !0);
	let r = ar(e), i = r === e.ownerDocument?.body, a = J(r);
	if (i) {
		let e = sr(a);
		return t.concat(a, a.visualViewport || [], qn(r) ? r : [], e && n ? or(e) : []);
	}
	return t.concat(r, or(r, [], n));
}
function sr(e) {
	return e.parent && Object.getPrototypeOf(e.parent) ? e.frameElement : null;
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs
function cr(e) {
	let t = $(e), n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0, i = Z(e), a = i ? e.offsetWidth : n, o = i ? e.offsetHeight : r, s = sn(n) !== a || sn(r) !== o;
	return s && (n = a, r = o), {
		width: n,
		height: r,
		$: s
	};
}
function lr(e) {
	return X(e) ? e : e.contextElement;
}
function ur(e) {
	let t = lr(e);
	if (!Z(t)) return W(1);
	let n = t.getBoundingClientRect(), { width: r, height: i, $: a } = cr(t), o = (a ? sn(n.width) : n.width) / r, s = (a ? sn(n.height) : n.height) / i;
	return o && Number.isFinite(o) || (o = 1), s && Number.isFinite(s) || (s = 1), {
		x: o,
		y: s
	};
}
var dr = /*#__PURE__*/ W(0);
function fr(e) {
	let t = J(e);
	return !tr() || !t.visualViewport ? dr : {
		x: t.visualViewport.offsetLeft,
		y: t.visualViewport.offsetTop
	};
}
function pr(e, t, n) {
	return t === void 0 && (t = !1), !!n && t && n === J(e);
}
function mr(e, t, n, r) {
	t === void 0 && (t = !1), n === void 0 && (n = !1);
	let i = e.getBoundingClientRect(), a = lr(e), o = W(1);
	t && (r ? X(r) && (o = ur(r)) : o = ur(e));
	let s = pr(a, n, r) ? fr(a) : W(0), c = (i.left + s.x) / o.x, l = (i.top + s.y) / o.y, u = i.width / o.x, d = i.height / o.y;
	if (a && r) {
		let e = J(a), t = X(r) ? J(r) : r, n = e, i = sr(n);
		for (; i && t !== n;) {
			let e = ur(i), t = i.getBoundingClientRect(), r = $(i), a = t.left + (i.clientLeft + parseFloat(r.paddingLeft)) * e.x, o = t.top + (i.clientTop + parseFloat(r.paddingTop)) * e.y;
			c *= e.x, l *= e.y, u *= e.x, d *= e.y, c += a, l += o, n = J(i), i = sr(n);
		}
	}
	return Dn({
		width: u,
		height: d,
		x: c,
		y: l
	});
}
function hr(e, t) {
	let n = rr(e).scrollLeft;
	return t ? t.left + n : mr(Y(e)).left + n;
}
function gr(e, t) {
	let n = e.getBoundingClientRect();
	return {
		x: n.left + t.scrollLeft - hr(e, n),
		y: n.top + t.scrollTop
	};
}
function _r(e) {
	let { elements: t, rect: n, offsetParent: r, strategy: i } = e, a = i === "fixed", o = Y(r), s = t ? Yn(t.floating) : !1;
	if (r === o || s && a) return n;
	let c = {
		scrollLeft: 0,
		scrollTop: 0
	}, l = W(1), u = W(0), d = Z(r);
	if ((d || !a) && ((Wn(r) !== "body" || qn(o)) && (c = rr(r)), d)) {
		let e = mr(r);
		l = ur(r), u.x = e.x + r.clientLeft, u.y = e.y + r.clientTop;
	}
	let f = o && !d && !a ? gr(o, c) : W(0);
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
	let t = rr(e), n = e.ownerDocument.body, r = U(e.scrollWidth, e.clientWidth, n.scrollWidth, n.clientWidth), i = U(e.scrollHeight, e.clientHeight, n.scrollHeight, n.clientHeight), a = -t.scrollLeft + hr(e), o = -t.scrollTop;
	return $(n).direction === "rtl" && (a += U(e.clientWidth, n.clientWidth) - r), {
		width: r,
		height: i,
		x: a,
		y: o
	};
}
var br = 25;
function xr(e, t, n) {
	n === void 0 && (n = "viewport");
	let r = n === "layoutViewport", i = J(e), a = Y(e), o = i.visualViewport, s = a.clientWidth, c = a.clientHeight, l = 0, u = 0;
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
	else if (t === "document") r = yr(Y(e));
	else if (X(t)) r = Sr(t, n);
	else {
		let n = fr(e);
		r = {
			x: t.x - n.x,
			y: t.y - n.y,
			width: t.width,
			height: t.height
		};
	}
	return Dn(r);
}
function wr(e, t) {
	let n = t.get(e);
	if (n) return n;
	let r = or(e, [], !1).filter((e) => X(e) && Wn(e) !== "body"), i = null, a = $(e).position === "fixed", o = a ? ir(e) : e;
	for (; X(o) && !nr(o);) {
		let e = $(o), t = $n(o), n = i ? i.position : a ? "fixed" : "";
		!t && (n === "fixed" || n === "absolute" && e.position === "static") ? r = r.filter((e) => e !== o) : i = e, o = ir(o);
	}
	return t.set(e, r), r;
}
function Tr(e) {
	let { element: t, boundary: n, rootBoundary: r, strategy: i } = e, a = [...n === "clippingAncestors" ? Yn(t) ? [] : wr(t, this._c) : [].concat(n), r], o = Cr(t, a[0], i), s = o.top, c = o.right, l = o.bottom, u = o.left;
	for (let e = 1; e < a.length; e++) {
		let n = Cr(t, a[e], i);
		s = U(n.top, s), c = H(n.right, c), l = H(n.bottom, l), u = U(n.left, u);
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
	let r = Z(t), i = Y(t), a = n === "fixed", o = mr(e, !0, a, t), s = {
		scrollLeft: 0,
		scrollTop: 0
	}, c = W(0);
	if ((r || !a) && ((Wn(t) !== "body" || qn(i)) && (s = rr(t)), r)) {
		let e = mr(t, !0, a, t);
		c.x = e.x + t.clientLeft, c.y = e.y + t.clientTop;
	}
	!r && i && (c.x = hr(i));
	let l = i && !r && !a ? gr(i, s) : W(0);
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
	if (!Z(e) || $(e).position === "fixed") return null;
	if (t) return t(e);
	let n = e.offsetParent;
	return Y(e) === n && (n = n.ownerDocument.body), n;
}
function Ar(e, t) {
	let n = J(e);
	if (Yn(e)) return n;
	if (!Z(e)) {
		let t = ir(e);
		for (; t && !nr(t);) {
			if (X(t) && !Or(t)) return t;
			t = ir(t);
		}
		return n;
	}
	let r = kr(e, t);
	for (; r && Jn(r) && Or(r);) r = kr(r, t);
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
	getDocumentElement: Y,
	getClippingRect: Tr,
	getOffsetParent: Ar,
	getElementRects: jr,
	getClientRects: vr,
	getDimensions: Er,
	getScale: ur,
	isElement: X,
	isRTL: Mr
};
function Pr(e, t) {
	return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function Fr(e, t, n) {
	let r = null, i, a = Y(e);
	function o() {
		var e;
		clearTimeout(i), (e = r) == null || e.disconnect(), r = null;
	}
	function s(n, c) {
		n === void 0 && (n = !1), c === void 0 && (c = 1), o();
		let l = e.getBoundingClientRect(), { left: u, top: d, width: f, height: p } = l;
		if (n || t(), !f || !p) return;
		let m = cn(d), h = cn(a.clientWidth - (u + f)), g = cn(a.clientHeight - (d + p)), _ = cn(u), v = {
			rootMargin: -m + "px " + -h + "px " + -g + "px " + -_ + "px",
			threshold: U(0, H(1, c)) || 1
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
	let c = J(e), l = () => s(n);
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
var Lr = zn, Rr = Bn, zr = Nn, Br = Hn, Vr = In, Hr = Mn, Ur = Vn, Wr = (e, t, n) => {
	let r = /* @__PURE__ */ new Map(), i = n ?? {}, a = {
		...Nr,
		...i.platform,
		_c: r
	};
	return jn(e, t, {
		...i,
		platform: a
	});
};
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/@floating-ui/vue/dist/floating-ui.vue.mjs
function Gr(e) {
	return typeof e == "object" && !!e && "$el" in e;
}
function Kr(e) {
	if (Gr(e)) {
		let t = e.$el;
		return Gn(t) && Wn(t) === "#comment" ? null : t;
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
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/Popper/PopperContent.js
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
}, [$r, ei] = /*#__PURE__*/ ye("PopperContent"), ti = /* @__PURE__ */ n({
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
		let n = e, r = t, i = Qt(), { forwardRef: s, currentElement: c } = R(), l = at(P(() => n.dir)), u = k(), d = k(), { width: f, height: p } = Ct(d), m = P(() => n.side + (n.align === "center" ? "" : `-${n.align}`)), h = P(() => typeof n.collisionPadding == "number" ? n.collisionPadding : {
			top: 0,
			right: 0,
			bottom: 0,
			left: 0,
			...n.collisionPadding
		}), _ = P(() => Array.isArray(n.collisionBoundary) ? n.collisionBoundary : [n.collisionBoundary]), v = P(() => ({
			padding: h.value,
			boundary: _.value.filter(nn),
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
			rn({
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
		}), D = P(() => an(w.value)[0]), te = P(() => an(w.value)[1]);
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
		}), (e, t) => (a(), ge("div", {
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
		], () => (a(), j(F(z), N({
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
		])), t, 0) : (a(), j(F(z), N({
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
}), [ni, ri] = /*#__PURE__*/ ye("PopoverRoot"), ii = /* @__PURE__ */ n({
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
		let n = e, r = t, { modal: i } = ne(n), s = Ue(n, "open", r, {
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
		}), (e, t) => (a(), j(F(en), null, {
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
		R();
		let n = ni();
		return (r, i) => (a(), j(F(z), {
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
		let n = e, r = t, i = ut(Ne(n, "trapFocus", "disableOutsidePointerEvents")), { forwardRef: s } = R(), c = ni();
		return ct(), (t, n) => (a(), j(F(Xt), {
			"as-child": "",
			loop: "",
			trapped: e.trapFocus,
			onMountAutoFocus: n[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: n[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: o(() => [_(F(It), {
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
		nt(!0);
		let c = dt(n, r), { forwardRef: l, currentElement: u } = R();
		return xt(u), (e, t) => (a(), j(oi, N(F(c), {
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
		let n = e, r = t, i = ni(), s = k(!1), c = k(!1), l = dt(n, r);
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
		let n = e, r = t, i = ni(), s = dt(n, r), { forwardRef: c } = R();
		return i.contentId ||= St(void 0, "reka-popover-content"), (t, n) => (a(), j(F(Dt), { present: e.forceMount || F(i).open.value }, {
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
		return (e, n) => (a(), j(F(Zt), he(v(t)), {
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
		let n = e, r = ni(), { forwardRef: i, currentElement: s } = R();
		return r.triggerId ||= St(void 0, "reka-popover-trigger"), r.contentId ||= St(void 0, "reka-popover-content"), d(() => {
			r.triggerElement.value = s.value;
		}), (s, c) => (a(), j(t(F(r).hasCustomAnchor.value ? F(z) : F(tn)), { "as-child": "" }, {
			default: o(() => [_(F(z), {
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
		return (t, n) => (a(), ge("div", {
			class: ae(["list-cell", `list-cell--${e.tone}`]),
			title: e.title ?? [e.text, e.secondary].filter(Boolean).join(" · ")
		}, [M("div", { class: ae(["list-cell-primary", { "list-cell-single": !!e.secondary }]) }, [g(t.$slots, "default", {}, () => [ve(A(e.text), 1)], !0)], 2), e.secondary ? (a(), ge("div", _i, A(e.secondary), 1)) : T("", !0)], 10, gi));
	}
}), [["__scopeId", "data-v-5767b82c"]]), yi = ["aria-label"], bi = [
	"aria-label",
	"title",
	"onClick"
], xi = /*#__PURE__*/ fe(/* @__PURE__ */ n({
	__name: "ListFilterSummary",
	props: {
		items: {},
		label: { default: "已应用筛选" }
	},
	emits: ["remove"],
	setup(e, { emit: t }) {
		let n = t;
		return (t, r) => e.items.length ? (a(), ge("div", {
			key: 0,
			class: "list-filter-summary",
			role: "group",
			"aria-label": e.label
		}, [(a(!0), ge(D, null, u(e.items, (e) => (a(), ge("button", {
			key: e.key,
			type: "button",
			class: "list-filter-chip",
			"aria-label": e.removeLabel,
			title: e.title || e.label,
			onClick: (t) => n("remove", e.key)
		}, [M("span", null, A(e.label), 1), r[0] ||= M("span", { "aria-hidden": "true" }, "×", -1)], 8, bi))), 128))], 8, yi)) : T("", !0);
	}
}), [["__scopeId", "data-v-9c3f6cac"]]);
export { ot as _, ui as a, I as b, Zt as c, z as d, Dt as f, R as g, dt as h, di as i, Xt as l, xt as m, vi as n, li as o, St as p, hi as r, ii as s, xi as t, It as u, nt as v, ye as x, Ue as y };
