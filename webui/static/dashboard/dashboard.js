// node_modules/@vue/shared/dist/shared.esm-bundler.js
// @__NO_SIDE_EFFECTS__
function e(e) {
	let t = /* @__PURE__ */ Object.create(null);
	for (let n of e.split(",")) t[n] = 1;
	return (e) => e in t;
}
var t = {}, n = [], r = () => {}, i = () => !1, a = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && (e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97), o = (e) => e.startsWith("onUpdate:"), s = Object.assign, c = (e, t) => {
	let n = e.indexOf(t);
	n > -1 && e.splice(n, 1);
}, l = Object.prototype.hasOwnProperty, u = (e, t) => l.call(e, t), d = Array.isArray, f = (e) => x(e) === "[object Map]", p = (e) => x(e) === "[object Set]", m = (e) => x(e) === "[object Date]", h = (e) => typeof e == "function", g = (e) => typeof e == "string", _ = (e) => typeof e == "symbol", v = (e) => typeof e == "object" && !!e, y = (e) => (v(e) || h(e)) && h(e.then) && h(e.catch), b = Object.prototype.toString, x = (e) => b.call(e), S = (e) => x(e).slice(8, -1), C = (e) => x(e) === "[object Object]", w = (e) => g(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e, T = /* @__PURE__ */ e(",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"), ee = (e) => {
	let t = /* @__PURE__ */ Object.create(null);
	return ((n) => t[n] || (t[n] = e(n)));
}, te = /-\w/g, E = /* @__PURE__ */ ee((e) => e.replace(te, (e) => e.slice(1).toUpperCase())), D = /\B([A-Z])/g, O = /* @__PURE__ */ ee((e) => e.replace(D, "-$1").toLowerCase()), ne = /* @__PURE__ */ ee((e) => e.charAt(0).toUpperCase() + e.slice(1)), re = /* @__PURE__ */ ee((e) => e ? `on${ne(e)}` : ""), k = (e, t) => !Object.is(e, t), ie = (e, ...t) => {
	for (let n = 0; n < e.length; n++) e[n](...t);
}, A = (e, t, n, r = !1) => {
	Object.defineProperty(e, t, {
		configurable: !0,
		enumerable: !1,
		writable: r,
		value: n
	});
}, ae = (e) => {
	let t = parseFloat(e);
	return isNaN(t) ? e : t;
}, oe, se = () => oe ||= typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {};
function ce(e) {
	if (d(e)) {
		let t = {};
		for (let n = 0; n < e.length; n++) {
			let r = e[n], i = g(r) ? fe(r) : ce(r);
			if (i) for (let e in i) t[e] = i[e];
		}
		return t;
	}
	if (g(e) || v(e)) return e;
}
var le = /;(?![^(]*\))/g, ue = /:([^]+)/, de = /"(?:[^"\\]|\\[^])*"|'(?:[^'\\]|\\[^])*'|\\[^]|\/\*[^]*?\*\//g;
function fe(e) {
	let t = {};
	return e.replace(de, (e) => e.startsWith("/*") ? "" : e).split(le).forEach((e) => {
		if (e) {
			let n = e.split(ue);
			n.length > 1 && (t[n[0].trim()] = n[1].trim());
		}
	}), t;
}
function j(e) {
	let t = "";
	if (g(e)) t = e;
	else if (d(e)) for (let n = 0; n < e.length; n++) {
		let r = j(e[n]);
		r && (t += r + " ");
	}
	else if (v(e)) for (let n in e) e[n] && (t += n + " ");
	return t.trim();
}
var pe = /* @__PURE__ */ e("itemscope,allowfullscreen,disablepictureinpicture,disableremoteplayback,formnovalidate,ismap,nomodule,novalidate,playsinline,readonly");
function me(e) {
	return !!e || e === "";
}
function he(e, t, n) {
	if (e.length !== t.length) return !1;
	let r = !0;
	for (let i = 0; r && i < e.length; i++) r = ye(e[i], t[i], n);
	return r;
}
function ge(e, t, n) {
	if (e.size !== t.size) return !1;
	let r = Array.from(t), i = new Uint8Array(r.length);
	for (let t of e) {
		let e = -1;
		for (let a = 0; a < r.length; a++) if (!i[a] && ye(t, r[a], n)) {
			e = a;
			break;
		}
		if (e < 0) return !1;
		i[e] = 1;
	}
	return !0;
}
function _e(e, t, n) {
	let r = f(e), i = f(t);
	if (r || i || (r = p(e), i = p(t), r || i)) return r && i ? ge(e, t, n) : !1;
	if (Object.keys(e).length !== Object.keys(t).length) return !1;
	for (let r in e) {
		let i = e.hasOwnProperty(r), a = t.hasOwnProperty(r);
		if (i && !a || !i && a || !ye(e[r], t[r], n)) return !1;
	}
	return String(e) === String(t);
}
function ve(e, t, n, r) {
	n ||= [/* @__PURE__ */ new Map(), /* @__PURE__ */ new Map()];
	let [i, a] = n;
	if (i.has(e) || a.has(t)) return i.get(e) === t && a.get(t) === e;
	i.set(e, t), a.set(t, e);
	let o = r(e, t, n);
	return i.delete(e), a.delete(t), o;
}
function ye(e, t, n) {
	if (e === t) return !0;
	let r = m(e), i = m(t);
	return r || i ? r && i ? e.getTime() === t.getTime() : !1 : (r = _(e), i = _(t), r || i ? e === t : (r = d(e), i = d(t), r || i ? r && i ? ve(e, t, n, he) : !1 : (r = v(e), i = v(t), r || i ? !r || !i ? !1 : ve(e, t, n, _e) : String(e) === String(t))));
}
var be = (e) => !!(e && e.__v_isRef === !0), M = (e) => g(e) ? e : e == null ? "" : d(e) || v(e) && (e.toString === b || !h(e.toString)) ? be(e) ? M(e.value) : JSON.stringify(e, xe, 2) : String(e), xe = (e, t) => be(t) ? xe(e, t.value) : f(t) ? { [`Map(${t.size})`]: [...t.entries()].reduce((e, [t, n], r) => (e[Se(t, r) + " =>"] = n, e), {}) } : p(t) ? { [`Set(${t.size})`]: [...t.values()].map((e) => Se(e)) } : _(t) ? Se(t) : v(t) && !d(t) && !C(t) ? String(t) : t, Se = (e, t = "") => _(e) ? `Symbol(${e.description ?? t})` : e, N, Ce = class {
	constructor(e = !1) {
		this.detached = e, this._active = !0, this._on = 0, this.effects = [], this.cleanups = [], this._isPaused = !1, this._warnOnRun = !0, this.__v_skip = !0, !e && N && (N.active ? (this.parent = N, this.index = (N.scopes || (N.scopes = [])).push(this) - 1) : (this._active = !1, this._warnOnRun = !1));
	}
	get active() {
		return this._active;
	}
	pause() {
		if (this._active) {
			this._isPaused = !0;
			let e, t;
			if (this.scopes) {
				let n = this.scopes.slice();
				for (e = 0, t = n.length; e < t; e++) n[e].pause();
			}
			for (e = 0, t = this.effects.length; e < t; e++) this.effects[e].pause();
		}
	}
	resume() {
		if (this._active && this._isPaused) {
			this._isPaused = !1;
			let e, t;
			if (this.scopes) {
				let n = this.scopes.slice();
				for (e = 0, t = n.length; e < t; e++) n[e].resume();
			}
			let n = this.effects.slice();
			for (e = 0, t = n.length; e < t; e++) n[e].resume();
		}
	}
	run(e) {
		if (this._active) {
			let t = N;
			try {
				return N = this, e();
			} finally {
				N = t;
			}
		}
	}
	on() {
		++this._on === 1 && (this.prevScope = N, N = this);
	}
	off() {
		if (this._on > 0 && --this._on === 0) {
			if (N === this) N = this.prevScope;
			else {
				let e = N;
				for (; e;) {
					if (e.prevScope === this) {
						e.prevScope = this.prevScope;
						break;
					}
					e = e.prevScope;
				}
			}
			this.prevScope = void 0;
		}
	}
	stop(e) {
		if (this._active) {
			this._active = !1;
			let t, n;
			for (t = 0, n = this.effects.length; t < n; t++) this.effects[t].stop();
			for (this.effects.length = 0, t = 0, n = this.cleanups.length; t < n; t++) this.cleanups[t]();
			if (this.cleanups.length = 0, this.scopes) {
				let e = this.scopes.slice();
				for (t = 0, n = e.length; t < n; t++) e[t].stop(!0);
				this.scopes.length = 0;
			}
			if (!this.detached && this.parent && !e) {
				let e = this.parent.scopes.pop();
				e && e !== this && (this.parent.scopes[this.index] = e, e.index = this.index);
			}
			this.parent = void 0;
		}
	}
};
function we() {
	return N;
}
var P, Te = /* @__PURE__ */ new WeakSet(), Ee = class {
	constructor(e) {
		this.fn = e, this.deps = void 0, this.depsTail = void 0, this.flags = 5, this.next = void 0, this.cleanup = void 0, this.scheduler = void 0, N && (N.active ? N.effects.push(this) : this.flags &= -2);
	}
	pause() {
		this.flags |= 64;
	}
	resume() {
		this.flags & 64 && (this.flags &= -65, Te.has(this) && (Te.delete(this), this.trigger()));
	}
	notify() {
		this.flags & 2 && !(this.flags & 32) || this.flags & 8 || Ae(this);
	}
	run() {
		if (!(this.flags & 1)) return this.fn();
		this.flags |= 2, Ue(this), Ne(this);
		let e = P, t = ze;
		P = this, ze = !0;
		try {
			return this.fn();
		} finally {
			Pe(this), P = e, ze = t, this.flags &= -3;
		}
	}
	stop() {
		if (this.flags & 1) {
			for (let e = this.deps; e; e = e.nextDep) Le(e);
			this.deps = this.depsTail = void 0, Ue(this), this.onStop && this.onStop(), this.flags &= -2;
		}
	}
	trigger() {
		this.flags & 64 ? Te.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
	}
	runIfDirty() {
		Fe(this) && this.run();
	}
	get dirty() {
		return Fe(this);
	}
}, De = 0, Oe, ke;
function Ae(e, t = !1) {
	e.flags |= 8, t ? (e.next = ke, ke = e) : (e.next = Oe, Oe = e);
}
function je() {
	De++;
}
function Me() {
	if (--De > 0) return;
	if (ke) {
		let e = ke;
		for (ke = void 0; e;) {
			let t = e.next;
			e.next = void 0, e.flags &= -9, e = t;
		}
	}
	let e;
	for (; Oe;) {
		let t = Oe;
		for (Oe = void 0; t;) {
			let n = t.next;
			if (t.next = void 0, t.flags &= -9, t.flags & 1) try {
				t.trigger();
			} catch (t) {
				e ||= t;
			}
			t = n;
		}
	}
	if (e) throw e;
}
function Ne(e) {
	for (let t = e.deps; t; t = t.nextDep) t.version = -1, t.prevActiveLink = t.dep.activeLink, t.dep.activeLink = t;
}
function Pe(e) {
	let t, n = e.depsTail, r = n;
	for (; r;) {
		let e = r.prevDep;
		r.version === -1 ? (r === n && (n = e), Le(r), Re(r)) : t = r, r.dep.activeLink = r.prevActiveLink, r.prevActiveLink = void 0, r = e;
	}
	e.deps = t, e.depsTail = n;
}
function Fe(e) {
	for (let t = e.deps; t; t = t.nextDep) if (t.dep.version !== t.version || t.dep.computed && (Ie(t.dep.computed) || t.dep.version !== t.version)) return !0;
	return !!e._dirty;
}
function Ie(e) {
	if (e.flags & 4 && !(e.flags & 16) || (e.flags &= -17, e.globalVersion === We) || (e.globalVersion = We, !e.isSSR && e.flags & 128 && (!e.deps && !e._dirty || !Fe(e)))) return;
	e.flags |= 2;
	let t = e.dep, n = P, r = ze;
	P = e, ze = !0;
	try {
		Ne(e);
		let n = e.fn(e._value);
		(t.version === 0 || k(n, e._value)) && (e.flags |= 128, e._value = n, t.version++);
	} catch (e) {
		throw t.version++, e;
	} finally {
		P = n, ze = r, Pe(e), e.flags &= -3;
	}
}
function Le(e, t = !1) {
	let { dep: n, prevSub: r, nextSub: i } = e;
	if (r && (r.nextSub = i, e.prevSub = void 0), i && (i.prevSub = r, e.nextSub = void 0), n.subs === e && (n.subs = r, !r && n.computed)) {
		n.computed.flags &= -5;
		for (let e = n.computed.deps; e; e = e.nextDep) Le(e, !0);
	}
	!t && !--n.sc && n.map && n.map.delete(n.key);
}
function Re(e) {
	let { prevDep: t, nextDep: n } = e;
	t && (t.nextDep = n, e.prevDep = void 0), n && (n.prevDep = t, e.nextDep = void 0);
}
var ze = !0, Be = [];
function Ve() {
	Be.push(ze), ze = !1;
}
function He() {
	let e = Be.pop();
	ze = e === void 0 || e;
}
function Ue(e) {
	let { cleanup: t } = e;
	if (e.cleanup = void 0, t) {
		let e = P;
		P = void 0;
		try {
			t();
		} finally {
			P = e;
		}
	}
}
var We = 0, Ge = class {
	constructor(e, t) {
		this.sub = e, this.dep = t, this.version = t.version, this.nextDep = this.prevDep = this.nextSub = this.prevSub = this.prevActiveLink = void 0;
	}
}, Ke = class {
	constructor(e) {
		this.computed = e, this.version = 0, this.activeLink = void 0, this.subs = void 0, this.map = void 0, this.key = void 0, this.sc = 0, this.__v_skip = !0;
	}
	track(e) {
		if (!P || !ze || P === this.computed) return;
		let t = this.activeLink;
		if (t === void 0 || t.sub !== P) t = this.activeLink = new Ge(P, this), P.deps ? (t.prevDep = P.depsTail, P.depsTail.nextDep = t, P.depsTail = t) : P.deps = P.depsTail = t, qe(t);
		else if (t.version === -1 && (t.version = this.version, t.nextDep)) {
			let e = t.nextDep;
			e.prevDep = t.prevDep, t.prevDep && (t.prevDep.nextDep = e), t.prevDep = P.depsTail, t.nextDep = void 0, P.depsTail.nextDep = t, P.depsTail = t, P.deps === t && (P.deps = e);
		}
		return t;
	}
	trigger(e) {
		this.version++, We++, this.notify(e);
	}
	notify(e) {
		je();
		try {
			for (let e = this.subs; e; e = e.prevSub) e.sub.notify() && e.sub.dep.notify();
		} finally {
			Me();
		}
	}
};
function qe(e) {
	if (e.dep.sc++, e.sub.flags & 4) {
		let t = e.dep.computed;
		if (t && !e.dep.subs) {
			t.flags |= 20;
			for (let e = t.deps; e; e = e.nextDep) qe(e);
		}
		let n = e.dep.subs;
		n !== e && (e.prevSub = n, n && (n.nextSub = e)), e.dep.subs = e;
	}
}
var Je = /* @__PURE__ */ new WeakMap(), Ye = /* @__PURE__ */ Symbol(""), Xe = /* @__PURE__ */ Symbol(""), Ze = /* @__PURE__ */ Symbol("");
function F(e, t, n) {
	if (ze && P) {
		let t = Je.get(e);
		t || Je.set(e, t = /* @__PURE__ */ new Map());
		let r = t.get(n);
		r || (t.set(n, r = new Ke()), r.map = t, r.key = n), r.track();
	}
}
function Qe(e, t, n, r, i, a) {
	let o = Je.get(e);
	if (!o) {
		We++;
		return;
	}
	let s = (e) => {
		e && e.trigger();
	};
	if (je(), t === "clear") o.forEach(s);
	else {
		let i = d(e), a = i && w(n);
		if (i && n === "length") {
			let e = Number(r);
			o.forEach((t, n) => {
				(n === "length" || n === Ze || !_(n) && n >= e) && s(t);
			});
		} else switch ((n !== void 0 || o.has(void 0)) && s(o.get(n)), a && s(o.get(Ze)), t) {
			case "add":
				i ? a && s(o.get("length")) : (s(o.get(Ye)), f(e) && s(o.get(Xe)));
				break;
			case "delete":
				i || (s(o.get(Ye)), f(e) && s(o.get(Xe)));
				break;
			case "set": f(e) && s(o.get(Ye));
		}
	}
	Me();
}
function $e(e) {
	let t = /* @__PURE__ */ L(e);
	return t === e || (F(t, "iterate", Ze), /* @__PURE__ */ I(e)) ? t : /* @__PURE__ */ Rt(e) ? /* @__PURE__ */ Lt(e) ? t.map((e) => Vt(R(e))) : t.map(Vt) : t.map(R);
}
function et(e) {
	return F(e = /* @__PURE__ */ L(e), "iterate", Ze), e;
}
function tt(e, t) {
	return /* @__PURE__ */ Rt(e) ? Vt(/* @__PURE__ */ Lt(e) ? R(t) : t) : R(t);
}
var nt = {
	__proto__: null,
	[Symbol.iterator]() {
		return rt(this, Symbol.iterator, (e) => tt(this, e));
	},
	concat(...e) {
		return $e(this).concat(...e.map((e) => d(e) ? $e(e) : e));
	},
	entries() {
		return rt(this, "entries", (e) => (e[1] = tt(this, e[1]), e));
	},
	every(e, t) {
		return ot(this, "every", e, t, void 0, arguments);
	},
	filter(e, t) {
		return ot(this, "filter", e, t, (e) => e.map((e) => tt(this, e)), arguments);
	},
	find(e, t) {
		return ot(this, "find", e, t, (e) => tt(this, e), arguments);
	},
	findIndex(e, t) {
		return ot(this, "findIndex", e, t, void 0, arguments);
	},
	findLast(e, t) {
		return ot(this, "findLast", e, t, (e) => tt(this, e), arguments);
	},
	findLastIndex(e, t) {
		return ot(this, "findLastIndex", e, t, void 0, arguments);
	},
	forEach(e, t) {
		return ot(this, "forEach", e, t, void 0, arguments);
	},
	includes(...e) {
		return ct(this, "includes", e);
	},
	indexOf(...e) {
		return ct(this, "indexOf", e);
	},
	join(e) {
		return $e(this).join(e);
	},
	lastIndexOf(...e) {
		return ct(this, "lastIndexOf", e);
	},
	map(e, t) {
		return ot(this, "map", e, t, void 0, arguments);
	},
	pop() {
		return lt(this, "pop");
	},
	push(...e) {
		return lt(this, "push", e);
	},
	reduce(e, ...t) {
		return st(this, "reduce", e, t);
	},
	reduceRight(e, ...t) {
		return st(this, "reduceRight", e, t);
	},
	shift() {
		return lt(this, "shift");
	},
	some(e, t) {
		return ot(this, "some", e, t, void 0, arguments);
	},
	splice(...e) {
		return lt(this, "splice", e);
	},
	toReversed() {
		return $e(this).toReversed();
	},
	toSorted(e) {
		return $e(this).toSorted(e);
	},
	toSpliced(...e) {
		return $e(this).toSpliced(...e);
	},
	unshift(...e) {
		return lt(this, "unshift", e);
	},
	values() {
		return rt(this, "values", (e) => tt(this, e));
	}
};
function rt(e, t, n) {
	let r = et(e), i = r[t], a = i.call(r);
	if (r !== e && !/* @__PURE__ */ I(e)) {
		if (a[Symbol.toStringTag] === "Array Iterator") {
			let e = Object.create(Object.getPrototypeOf(a));
			return e.next = () => it(a.next(), n), i !== at[t] && Object.defineProperties(e, {
				return: { get() {
					let e = a.return;
					return typeof e == "function" ? e.bind(a) : e;
				} },
				throw: { get() {
					let e = a.throw;
					return typeof e == "function" ? e.bind(a) : e;
				} }
			}), e;
		}
		a._next = a.next, a.next = () => it(a._next(), n);
	}
	return a;
}
function it(e, t) {
	return e.done || (e.value = t(e.value)), e;
}
var at = Array.prototype;
function ot(e, t, n, r, i, a) {
	let o = et(e), s = o !== e && !/* @__PURE__ */ I(e), c = o[t];
	if (c !== at[t]) {
		let t = c.apply(e, a);
		return s ? R(t) : t;
	}
	let l = n;
	o !== e && (s ? l = function(t, r) {
		return n.call(this, tt(e, t), r, e);
	} : n.length > 2 && (l = function(t, r) {
		return n.call(this, t, r, e);
	}));
	let u = c.call(o, l, r);
	return s && i ? i(u) : u;
}
function st(e, t, n, r) {
	let i = et(e), a = i !== e && !/* @__PURE__ */ I(e), o = n, s = !1;
	i !== e && (a ? (s = r.length === 0, o = function(t, r, i) {
		return s && (s = !1, t = tt(e, t)), n.call(this, t, tt(e, r), i, e);
	}) : n.length > 3 && (o = function(t, r, i) {
		return n.call(this, t, r, i, e);
	}));
	let c = i[t](o, ...r);
	return s ? tt(e, c) : c;
}
function ct(e, t, n) {
	let r = /* @__PURE__ */ L(e);
	F(r, "iterate", Ze);
	let i = r[t](...n);
	return (i === -1 || i === !1) && /* @__PURE__ */ zt(n[0]) ? (n[0] = /* @__PURE__ */ L(n[0]), r[t](...n)) : i;
}
function lt(e, t, n = []) {
	Ve(), je();
	let r = (/* @__PURE__ */ L(e))[t].apply(e, n);
	return Me(), He(), r;
}
var ut = /* @__PURE__ */ e("__proto__,__v_isRef,__isVue"), dt = /* @__PURE__ */ new Set(/* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(_));
function ft(e) {
	_(e) || (e = String(e));
	let t = /* @__PURE__ */ L(this);
	return F(t, "has", e), t.hasOwnProperty(e);
}
var pt = class {
	constructor(e = !1, t = !1) {
		this._isReadonly = e, this._isShallow = t;
	}
	get(e, t, n) {
		if (t === "__v_skip") return e.__v_skip;
		let r = this._isReadonly, i = this._isShallow;
		if (t === "__v_isReactive") return !r;
		if (t === "__v_isReadonly") return r;
		if (t === "__v_isShallow") return i;
		if (t === "__v_raw") return n === (r ? i ? jt : At : i ? kt : Ot).get(e) || Object.getPrototypeOf(e) === Object.getPrototypeOf(n) ? e : void 0;
		let a = d(e);
		if (!r) {
			let e;
			if (a && (e = nt[t])) return e;
			if (t === "hasOwnProperty") return ft;
		}
		let o = Reflect.get(e, t, /* @__PURE__ */ z(e) ? e : n);
		if ((_(t) ? dt.has(t) : ut(t)) || (r || F(e, "get", t), i)) return o;
		if (/* @__PURE__ */ z(o)) {
			let e = a && w(t) ? o : o.value;
			return r && v(e) ? /* @__PURE__ */ Ft(e) : e;
		}
		return v(o) ? r ? /* @__PURE__ */ Ft(o) : /* @__PURE__ */ Nt(o) : o;
	}
}, mt = class extends pt {
	constructor(e = !1) {
		super(!1, e);
	}
	set(e, t, n, r) {
		let i = e[t], a = d(e) && w(t);
		if (!this._isShallow) {
			let e = /* @__PURE__ */ Rt(i);
			if (!/* @__PURE__ */ I(n) && !/* @__PURE__ */ Rt(n) && (i = /* @__PURE__ */ L(i), n = /* @__PURE__ */ L(n)), !a && /* @__PURE__ */ z(i) && !/* @__PURE__ */ z(n)) return e || (i.value = n), !0;
		}
		let o = a ? Number(t) < e.length : u(e, t), s = Reflect.set(e, t, n, /* @__PURE__ */ z(e) ? e : r);
		return e === /* @__PURE__ */ L(r) && s && (o ? k(n, i) && Qe(e, "set", t, n, i) : Qe(e, "add", t, n)), s;
	}
	deleteProperty(e, t) {
		let n = u(e, t), r = e[t], i = Reflect.deleteProperty(e, t);
		return i && n && Qe(e, "delete", t, void 0, r), i;
	}
	has(e, t) {
		let n = Reflect.has(e, t);
		return _(t) && dt.has(t) || F(e, "has", t), n;
	}
	ownKeys(e) {
		return F(e, "iterate", d(e) ? "length" : Ye), Reflect.ownKeys(e);
	}
}, ht = class extends pt {
	constructor(e = !1) {
		super(!0, e);
	}
	set(e, t) {
		return !0;
	}
	deleteProperty(e, t) {
		return !0;
	}
}, gt = /* @__PURE__ */ new mt(), _t = /* @__PURE__ */ new ht(), vt = /* @__PURE__ */ new mt(!0), yt = (e) => e, bt = (e) => Reflect.getPrototypeOf(e);
function xt(e, t, n) {
	return function(...r) {
		let i = this.__v_raw, a = /* @__PURE__ */ L(i), o = f(a), c = e === "entries" || e === Symbol.iterator && o, l = e === "keys" && o, u = i[e](...r), d = n ? yt : t ? Vt : R;
		return !t && F(a, "iterate", l ? Xe : Ye), s(Object.create(u), { next() {
			let { value: e, done: t } = u.next();
			return t ? {
				value: e,
				done: t
			} : {
				value: c ? [d(e[0]), d(e[1])] : d(e),
				done: t
			};
		} });
	};
}
function St(e) {
	return function(...t) {
		return e === "delete" ? !1 : e === "clear" ? void 0 : this;
	};
}
function Ct(e, t) {
	let n = {
		get(n) {
			let r = this.__v_raw, i = /* @__PURE__ */ L(r), a = /* @__PURE__ */ L(n);
			e || (k(n, a) && F(i, "get", n), F(i, "get", a));
			let { has: o } = bt(i), s = t ? yt : e ? Vt : R;
			if (o.call(i, n)) return s(r.get(n));
			if (o.call(i, a)) return s(r.get(a));
			r !== i && r.get(n);
		},
		get size() {
			let t = this.__v_raw;
			return !e && F(/* @__PURE__ */ L(t), "iterate", Ye), t.size;
		},
		has(t) {
			let n = this.__v_raw, r = /* @__PURE__ */ L(n), i = /* @__PURE__ */ L(t);
			return e || (k(t, i) && F(r, "has", t), F(r, "has", i)), t === i ? n.has(t) : n.has(t) || n.has(i);
		},
		forEach(n, r) {
			let i = this, a = i.__v_raw, o = /* @__PURE__ */ L(a), s = t ? yt : e ? Vt : R;
			return !e && F(o, "iterate", Ye), a.forEach((e, t) => n.call(r, s(e), s(t), i));
		}
	};
	return s(n, e ? {
		add: St("add"),
		set: St("set"),
		delete: St("delete"),
		clear: St("clear")
	} : {
		add(e) {
			let n = /* @__PURE__ */ L(this), r = bt(n), i = /* @__PURE__ */ L(e), a = !t && !/* @__PURE__ */ I(e) && !/* @__PURE__ */ Rt(e) ? i : e;
			return r.has.call(n, a) || k(e, a) && r.has.call(n, e) || k(i, a) && r.has.call(n, i) || (n.add(a), Qe(n, "add", a, a)), this;
		},
		set(e, n) {
			t || /* @__PURE__ */ I(n) || /* @__PURE__ */ Rt(n) || (n = /* @__PURE__ */ L(n));
			let r = /* @__PURE__ */ L(this), { has: i, get: a } = bt(r), o = i.call(r, e);
			o ||= (e = /* @__PURE__ */ L(e), i.call(r, e));
			let s = a.call(r, e);
			return r.set(e, n), o ? k(n, s) && Qe(r, "set", e, n, s) : Qe(r, "add", e, n), this;
		},
		delete(e) {
			let t = /* @__PURE__ */ L(this), { has: n, get: r } = bt(t), i = n.call(t, e);
			i ||= (e = /* @__PURE__ */ L(e), n.call(t, e));
			let a = r ? r.call(t, e) : void 0, o = t.delete(e);
			return i && Qe(t, "delete", e, void 0, a), o;
		},
		clear() {
			let e = /* @__PURE__ */ L(this), t = e.size !== 0, n = e.clear();
			return t && Qe(e, "clear", void 0, void 0, void 0), n;
		}
	}), [
		"keys",
		"values",
		"entries",
		Symbol.iterator
	].forEach((r) => {
		n[r] = xt(r, e, t);
	}), n;
}
function wt(e, t) {
	let n = Ct(e, t);
	return (r, i, a) => i === "__v_isReactive" ? !e : i === "__v_isReadonly" ? e : i === "__v_isShallow" ? t : i === "__v_raw" ? r : Reflect.get(u(n, i) && i in r ? n : r, i, a);
}
var Tt = { get: /* @__PURE__ */ wt(!1, !1) }, Et = { get: /* @__PURE__ */ wt(!1, !0) }, Dt = { get: /* @__PURE__ */ wt(!0, !1) }, Ot = /* @__PURE__ */ new WeakMap(), kt = /* @__PURE__ */ new WeakMap(), At = /* @__PURE__ */ new WeakMap(), jt = /* @__PURE__ */ new WeakMap();
function Mt(e) {
	switch (e) {
		case "Object":
		case "Array": return 1;
		case "Map":
		case "Set":
		case "WeakMap":
		case "WeakSet": return 2;
		default: return 0;
	}
}
// @__NO_SIDE_EFFECTS__
function Nt(e) {
	return /* @__PURE__ */ Rt(e) ? e : It(e, !1, gt, Tt, Ot);
}
// @__NO_SIDE_EFFECTS__
function Pt(e) {
	return It(e, !1, vt, Et, kt);
}
// @__NO_SIDE_EFFECTS__
function Ft(e) {
	return It(e, !0, _t, Dt, At);
}
function It(e, t, n, r, i) {
	if (!v(e) || e.__v_raw && !(t && e.__v_isReactive) || e.__v_skip || !Object.isExtensible(e)) return e;
	let a = i.get(e);
	if (a) return a;
	let o = Mt(S(e));
	if (o === 0) return e;
	let s = new Proxy(e, o === 2 ? r : n);
	return i.set(e, s), s;
}
// @__NO_SIDE_EFFECTS__
function Lt(e) {
	return /* @__PURE__ */ Rt(e) ? /* @__PURE__ */ Lt(e.__v_raw) : !!(e && e.__v_isReactive);
}
// @__NO_SIDE_EFFECTS__
function Rt(e) {
	return !!(e && e.__v_isReadonly);
}
// @__NO_SIDE_EFFECTS__
function I(e) {
	return !!(e && e.__v_isShallow);
}
// @__NO_SIDE_EFFECTS__
function zt(e) {
	return e ? !!e.__v_raw : !1;
}
// @__NO_SIDE_EFFECTS__
function L(e) {
	let t = e && e.__v_raw;
	return t ? /* @__PURE__ */ L(t) : e;
}
function Bt(e) {
	return !u(e, "__v_skip") && Object.isExtensible(e) && A(e, "__v_skip", !0), e;
}
var R = (e) => v(e) ? /* @__PURE__ */ Nt(e) : e, Vt = (e) => v(e) ? /* @__PURE__ */ Ft(e) : e;
// @__NO_SIDE_EFFECTS__
function z(e) {
	return e ? e.__v_isRef === !0 : !1;
}
// @__NO_SIDE_EFFECTS__
function Ht(e) {
	return Ut(e, !1);
}
function Ut(e, t) {
	return /* @__PURE__ */ z(e) ? e : new Wt(e, t);
}
var Wt = class {
	constructor(e, t) {
		this.dep = new Ke(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = t ? e : /* @__PURE__ */ L(e), this._value = t ? e : R(e), this.__v_isShallow = t;
	}
	get value() {
		return this.dep.track(), this._value;
	}
	set value(e) {
		let t = this._rawValue, n = this.__v_isShallow || /* @__PURE__ */ I(e) || /* @__PURE__ */ Rt(e);
		e = n ? e : /* @__PURE__ */ L(e), k(e, t) && (this._rawValue = e, this._value = n ? e : R(e), this.dep.trigger());
	}
};
function B(e) {
	return /* @__PURE__ */ z(e) ? e.value : e;
}
var Gt = {
	get: (e, t, n) => t === "__v_raw" ? e : B(Reflect.get(e, t, n)),
	set: (e, t, n, r) => {
		let i = e[t];
		return /* @__PURE__ */ z(i) && !/* @__PURE__ */ z(n) ? (i.value = n, !0) : Reflect.set(e, t, n, r);
	}
};
function Kt(e) {
	return /* @__PURE__ */ Lt(e) ? e : new Proxy(e, Gt);
}
var qt = class {
	constructor(e, t, n) {
		this.fn = e, this.setter = t, this._value = void 0, this.dep = new Ke(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = We - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !t, this.isSSR = n;
	}
	notify() {
		if (this.flags |= 16, !(this.flags & 8) && P !== this) return Ae(this, !0), !0;
	}
	get value() {
		let e = this.dep.track();
		return Ie(this), e && (e.version = this.dep.version), this._value;
	}
	set value(e) {
		this.setter && this.setter(e);
	}
};
// @__NO_SIDE_EFFECTS__
function Jt(e, t, n = !1) {
	let r, i;
	return h(e) ? r = e : (r = e.get, i = e.set), new qt(r, i, n);
}
var Yt = {}, Xt = /* @__PURE__ */ new WeakMap(), Zt = void 0;
function Qt(e, t = !1, n = Zt) {
	if (n) {
		let t = Xt.get(n);
		t || Xt.set(n, t = []), t.push(e);
	}
}
function $t(e, n, i = t) {
	let { immediate: a, deep: o, once: s, scheduler: l, augmentJob: u, call: f } = i, p = (e) => o ? e : /* @__PURE__ */ I(e) || o === !1 || o === 0 ? en(e, 1) : en(e), m, g, _, v, y = !1, b = !1;
	if (/* @__PURE__ */ z(e) ? (g = () => e.value, y = /* @__PURE__ */ I(e)) : /* @__PURE__ */ Lt(e) ? (g = () => p(e), y = !0) : d(e) ? (b = !0, y = e.some((e) => /* @__PURE__ */ Lt(e) || /* @__PURE__ */ I(e)), g = () => e.map((e) => {
		if (/* @__PURE__ */ z(e)) return e.value;
		if (/* @__PURE__ */ Lt(e)) return p(e);
		if (h(e)) return f ? f(e, 2) : e();
	})) : g = h(e) ? n ? f ? () => f(e, 2) : e : () => {
		if (_) {
			Ve();
			try {
				_();
			} finally {
				He();
			}
		}
		let t = Zt;
		Zt = m;
		try {
			return f ? f(e, 3, [v]) : e(v);
		} finally {
			Zt = t;
		}
	} : r, n && o) {
		let e = g, t = o === !0 ? Infinity : o;
		g = () => en(e(), t);
	}
	let x = we(), S = () => {
		m.stop(), x && x.active && c(x.effects, m);
	};
	if (s && n) {
		let e = n;
		n = (...t) => {
			try {
				return e(...t);
			} finally {
				S();
			}
		};
	}
	let C = b ? Array(e.length).fill(Yt) : Yt, w = (e) => {
		if (m.flags & 1 && (m.dirty || e)) {
			if (n) {
				let t = m.run();
				if (e || o || y || (b ? t.some((e, t) => k(e, C[t])) : k(t, C))) {
					let e = Zt;
					Ve();
					try {
						_ && _(), Zt = m;
						let e = [
							t,
							C === Yt ? void 0 : b && C[0] === Yt ? [] : C,
							v
						];
						C = t, f ? f(n, 3, e) : n(...e);
					} finally {
						Zt = e, He();
					}
				}
			} else m.run();
		}
	};
	return u && u(w), m = new Ee(g), m.scheduler = l ? () => l(w, !1) : w, v = (e) => Qt(e, !1, m), _ = m.onStop = () => {
		let e = Xt.get(m);
		if (e) {
			if (f) f(e, 4);
			else for (let t of e) t();
			Xt.delete(m);
		}
	}, n ? a ? w(!0) : C = m.run() : l ? l(w.bind(null, !0), !0) : m.run(), S.pause = m.pause.bind(m), S.resume = m.resume.bind(m), S.stop = S, S;
}
function en(e, t = Infinity, n) {
	if (t <= 0 || !v(e) || e.__v_skip || (n ||= /* @__PURE__ */ new Map(), (n.get(e) || 0) >= t)) return e;
	if (n.set(e, t), t--, /* @__PURE__ */ z(e)) en(e.value, t, n);
	else if (d(e)) for (let r = 0; r < e.length; r++) en(e[r], t, n);
	else if (p(e) || f(e)) e.forEach((e) => {
		en(e, t, n);
	});
	else if (C(e)) {
		for (let r in e) en(e[r], t, n);
		for (let r of Object.getOwnPropertySymbols(e)) Object.prototype.propertyIsEnumerable.call(e, r) && en(e[r], t, n);
	}
	return e;
}
// node_modules/@vue/runtime-core/dist/runtime-core.esm-bundler.js
function tn(e, t, n, r) {
	try {
		return r ? e(...r) : e();
	} catch (e) {
		nn(e, t, n);
	}
}
function V(e, t, n, r) {
	if (h(e)) {
		let i = tn(e, t, n, r);
		return i && y(i) && i.catch((e) => {
			nn(e, t, n, void 0, !0);
		}), i;
	}
	if (d(e)) {
		let i = [];
		for (let a = 0; a < e.length; a++) i.push(V(e[a], t, n, r));
		return i;
	}
}
function nn(e, n, r, i = !0, a = !1) {
	let o = n ? n.vnode : null, { errorHandler: s, throwUnhandledErrorInProduction: c } = n && n.appContext.config || t;
	if (n) {
		let t = n.parent, i = n.proxy, o = `https://vuejs.org/error-reference/#runtime-${r}`;
		for (; t;) {
			let n = t.ec;
			if (n && !t.isUnmounted && (!a || t.scope.active)) {
				for (let t = 0; t < n.length; t++) if (n[t](e, i, o) === !1) return;
			}
			t = t.parent;
		}
		if (s) {
			Ve(), tn(s, null, 10, [
				e,
				i,
				o
			]), He();
			return;
		}
	}
	rn(e, r, o, i, c);
}
function rn(e, t, n, r = !0, i = !1) {
	if (i) throw e;
	console.error(e);
}
var H = [], an = -1, on = [], sn = null, cn = 0, ln = /* @__PURE__ */ Promise.resolve(), un = null;
function dn(e) {
	let t = un || ln;
	return e ? t.then(this ? e.bind(this) : e) : t;
}
function fn(e) {
	let t = an + 1, n = H.length;
	for (; t < n;) {
		let r = t + n >>> 1, i = H[r], a = bn(i);
		a < e || a === e && i.flags & 2 ? t = r + 1 : n = r;
	}
	return t;
}
function pn(e) {
	if (!(e.flags & 1)) {
		let t = bn(e), n = H[H.length - 1];
		!n || !(e.flags & 2) && t >= bn(n) ? H.push(e) : H.splice(fn(t), 0, e), e.flags |= 1, mn();
	}
}
function mn() {
	un ||= ln.then(xn);
}
function hn(e) {
	if (!d(e)) sn && e.id === -1 ? sn.splice(cn + 1, 0, e) : e.flags & 1 || (on.push(e), e.flags |= 1);
	else for (let t = 0; t < e.length; t++) on.push(e[t]);
	mn();
}
function gn(e, t, n, r = an + 1) {
	for (; r < H.length; r++) {
		let n = H[r];
		if (n && n.flags & 2) {
			if (e && n.id !== e.uid || t !== void 0 && !(n.id >= t)) continue;
			H.splice(r, 1), r = e ? r - 1 : an, n.flags & 4 && (n.flags &= -2), n(), n.flags & 4 || (n.flags &= -2);
		}
	}
}
function _n(e, t, n = 0) {
	if (on.length) {
		let e = on, r = 0;
		if (t) {
			e = [];
			for (let i = 0; i < on.length; i++) {
				let a = on[i];
				(a.i === void 0 ? t.has(a) : !a.i || a.i.uid < n) ? on[r++] = a : e.push(a);
			}
		}
		let i = [...new Set(e)].sort((e, t) => bn(e) - bn(t));
		if (on.length = r, sn) {
			for (let e = 0; e < i.length; e++) sn.push(i[e]);
			return;
		}
		for (sn = i, cn = 0; cn < sn.length; cn++) {
			let e = sn[cn];
			e.flags & 4 && (e.flags &= -2), e.flags & 8 || e(), e.flags &= -2;
		}
		sn = null, cn = 0;
	}
}
var vn = !1;
function yn(e, t) {
	if (vn) {
		e();
		return;
	}
	let n = t === void 0 ? void 0 : new Set(on);
	e(), vn = !0;
	try {
		gn(void 0, t), _n(void 0, n, t);
	} finally {
		vn = !1;
	}
}
var bn = (e) => e.id == null ? e.flags & 2 ? -1 : Infinity : e.id;
function xn(e) {
	try {
		for (an = 0; an < H.length; an++) {
			let e = H[an];
			e && !(e.flags & 8) && (e.flags & 4 && (e.flags &= -2), tn(e, e.i, e.i ? 15 : 14), e.flags & 4 || (e.flags &= -2));
		}
	} finally {
		for (; an < H.length; an++) {
			let e = H[an];
			e && (e.flags &= -2);
		}
		an = -1, H.length = 0, _n(e), un = null, (H.length || on.length) && xn(e);
	}
}
var Sn = null, Cn = null;
function wn(e) {
	let t = Sn;
	return Sn = e, Cn = e && e.type.__scopeId || null, t;
}
function Tn(e, t = Sn, n) {
	if (!t || e._n) return e;
	let r = (...n) => {
		r._d && Ni(-1);
		let i = wn(t), a = Ai.length, o;
		try {
			o = e(...n);
		} finally {
			for (let e = Ai.length; e > a; e--) ji();
			wn(i), r._d && Ni(1);
		}
		return o;
	};
	return r._n = !0, r._c = !0, r._d = !0, r;
}
function En(e, t, n, r) {
	let i = e;
	if (r === "beforeMount") e._mount = e;
	else if (r === "beforeUpdate") {
		let n = t && t._mount;
		n && (n._latest = e, e._mount = n);
	} else if (r === "mounted") {
		let t = e._latest;
		e._mount = e._latest = void 0, t && (i = t, t._mount = void 0);
	}
	let a = i.dirs, o = t && t.dirs;
	for (let c = 0; c < a.length; c++) {
		let l = a[c];
		o ? l.oldValue = o[c].value : r === "mounted" && l.oldValue !== void 0 && (l = s({}, l, { oldValue: void 0 }));
		let u = l.dir[r];
		u && (Ve(), V(u, n, 8, [
			e.el,
			l,
			i,
			t
		]), He());
	}
}
function Dn(e, t) {
	if (Z) {
		let n = Z.provides, r = Z.parent && Z.parent.provides;
		r === n && (n = Z.provides = Object.create(r)), n[e] = t;
	}
}
function On(e, t, n = !1) {
	let r = ta();
	if (r || Ir) {
		let i = Ir ? Ir._context.provides : r ? r.parent == null || r.ce ? r.vnode.appContext && r.vnode.appContext.provides : r.parent.provides : void 0;
		if (i && e in i) return i[e];
		if (arguments.length > 1) return n && h(t) ? t.call(r && r.proxy) : t;
	}
}
var kn = /* @__PURE__ */ Symbol.for("v-scx"), An = () => On(kn);
function jn(e, t, n) {
	return Mn(e, t, n);
}
function Mn(e, n, i = t) {
	let { immediate: a, deep: o, flush: c, once: l } = i, u = s({}, i), d = n && a || !n && c !== "post", f;
	if (sa) {
		if (c === "sync") {
			let e = An();
			f = e.__watcherHandles ||= [];
		} else if (!d) {
			let e = () => {};
			return e.stop = r, e.resume = r, e.pause = r, e;
		}
	}
	let p = Z;
	u.call = (e, t, n) => V(e, p, t, n);
	let m = !1;
	c === "post" ? u.scheduler = (e) => {
		e.i = p, W(e, p && p.suspense);
	} : c !== "sync" && (m = !0, u.scheduler = (e, t) => {
		t ? e() : pn(e);
	}), u.augmentJob = (e) => {
		n && (e.flags |= 4), m && (e.flags |= 2, p && (e.id = p.uid, e.i = p));
	};
	let h = $t(e, n, u);
	return sa && (f ? f.push(h) : d && h()), h;
}
function Nn(e, t, n) {
	let r = this.proxy, i = g(e) ? e.includes(".") ? Pn(r, e) : () => r[e] : e.bind(r, r), a;
	h(t) ? a = t : (a = t.handler, n = t);
	let o = ia(this), s = Mn(i, a.bind(r), n);
	return o(), s;
}
function Pn(e, t) {
	let n = t.split(".");
	return () => {
		let t = e;
		for (let e = 0; e < n.length && t; e++) t = t[n[e]];
		return t;
	};
}
var Fn = /* @__PURE__ */ Symbol("_vte"), In = (e) => e.__isTeleport, Ln = /* @__PURE__ */ Symbol("_leaveCb");
function Rn(e) {
	let t = e[0];
	if (e.length > 1) {
		for (let n of e) if (n.type !== Oi) {
			t = n;
			break;
		}
	}
	return t;
}
function zn(e) {
	if (!Yn(e)) return In(e.type) && e.children ? Rn(e.children) : e;
	if (e.component) return e.component.subTree;
	let { shapeFlag: t, children: n } = e;
	if (n) {
		if (t & 16) return n[0];
		if (t & 32 && h(n.default)) return n.default();
	}
}
function Bn(e, t) {
	if (e.shapeFlag & 6 && e.component) {
		e.transition = t;
		let n = e.component.subTree;
		Bn(In(n.type) && zn(n) || n, t);
	} else if (e.shapeFlag & 128) {
		let n = e.suspense;
		if (n) {
			let e = n.isHydrating ? n.pendingBranch : n.activeBranch;
			e && Bn(e, t.clone(e));
		} else e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback);
	} else if (e.transition = t, e.type === G && d(e.children)) {
		let n = Ur(e.children, !1);
		n && Bn(n, t);
	}
}
function Vn(e) {
	if (e.component) return Vn(e.component.subTree);
	if (e.type === G) {
		let t = d(e.children) && Ur(e.children, !1);
		return t ? Vn(t) : void 0;
	}
	if (e.type !== Oi) return e;
}
// @__NO_SIDE_EFFECTS__
function Hn(e, t) {
	return h(e) ? /* @__PURE__ */ s({ name: e.name }, t, { setup: e }) : e;
}
function Un(e) {
	e.ids = [
		e.ids[0] + e.ids[2]++ + "-",
		0,
		0
	];
}
function Wn(e, t) {
	let n;
	return !!((n = Object.getOwnPropertyDescriptor(e, t)) && !n.configurable);
}
var Gn = /* @__PURE__ */ new WeakMap();
function Kn(e, n, r, a, o = !1) {
	if (d(e)) {
		e.forEach((e, t) => Kn(e, n && (d(n) ? n[t] : n), r, a, o));
		return;
	}
	if (Jn(a) && !o) {
		a.shapeFlag & 512 && a.type.__asyncResolved && a.component.subTree.component && Kn(e, n, r, a.component.subTree);
		return;
	}
	let s = a.shapeFlag & 4 ? ha(a.component) : a.el, l = o ? null : s, { i: f, r: p } = e, m = n && n.r, _ = f.refs === t ? f.refs = {} : f.refs, v = f.setupState, y = /* @__PURE__ */ L(v), b = v === t ? i : (e) => !Wn(_, e) && u(y, e), x = (e, t) => !(t && Wn(_, t));
	if (m != null && m !== p) {
		if (qn(n), g(m)) _[m] = null, b(m) && (v[m] = null);
		else if (/* @__PURE__ */ z(m)) {
			let e = n;
			x(m, e.k) && (m.value = null), e.k && (_[e.k] = null);
		}
	}
	if (h(p)) tn(p, f, 12, [l, _]);
	else {
		let t = g(p), n = /* @__PURE__ */ z(p);
		if (t || n) {
			let i = () => {
				if (e.f) {
					let n = t ? b(p) ? v[p] : _[p] : x(p) || !e.k ? p.value : _[e.k];
					if (o) d(n) && c(n, s);
					else if (d(n)) n.includes(s) || n.push(s);
					else if (t) _[p] = [s], b(p) && (v[p] = _[p]);
					else {
						let t = [s];
						x(p, e.k) && (p.value = t), e.k && (_[e.k] = t);
					}
				} else t ? (_[p] = l, b(p) && (v[p] = l)) : n && (x(p, e.k) && (p.value = l), e.k && (_[e.k] = l));
			};
			if (l) {
				let t = () => {
					i(), Gn.delete(e);
				};
				t.id = -1, Gn.set(e, t), W(t, r);
			} else qn(e), i();
		}
	}
}
function qn(e) {
	let t = Gn.get(e);
	t && (t.flags |= 8, Gn.delete(e));
}
se().requestIdleCallback, se().cancelIdleCallback;
var Jn = (e) => !!e.type.__asyncLoader, Yn = (e) => e.type.__isKeepAlive;
function Xn(e, t) {
	Qn(e, "a", t);
}
function Zn(e, t) {
	Qn(e, "da", t);
}
function Qn(e, t, n = Z) {
	let r = e.__wdc ||= () => {
		let t = n;
		for (; t;) {
			if (t.isDeactivated) return;
			t = t.parent;
		}
		return e();
	};
	if (er(t, r, n), n) {
		let e = n.parent;
		for (; e && e.parent;) Yn(e.parent.vnode) && $n(r, t, n, e), e = e.parent;
	}
}
function $n(e, t, n, r) {
	let i = er(t, e, r, !0), a = er("um", () => c(r[t], i), n);
	a.flags = 16;
}
function er(e, t, n = Z, r = !1) {
	if (n) {
		let i = n[e] || (n[e] = []), a = t.__weh ||= (...r) => {
			Ve();
			let i = ia(n), a = V(t, n, e, r);
			return i(), He(), a;
		};
		return r ? i.unshift(a) : i.push(a), a;
	}
}
var tr = (e) => (t, n = Z) => {
	sa && e !== "sp" || er(e, (...e) => t(...e), n);
}, nr = tr("bm"), rr = tr("m"), ir = tr("bu"), ar = tr("u"), or = tr("bum"), sr = tr("um"), cr = tr("sp"), lr = tr("rtg"), ur = tr("rtc");
function dr(e, t = Z) {
	er("ec", e, t);
}
var fr = /* @__PURE__ */ Symbol.for("v-ndc");
function pr(e, t, n, r) {
	let i, a = n && n[r], o = d(e);
	if (o || g(e)) {
		let n = o && /* @__PURE__ */ Lt(e), r = !1, s = !1;
		n && (r = !/* @__PURE__ */ I(e), s = /* @__PURE__ */ Rt(e), e = et(e)), i = Array(e.length);
		for (let n = 0, o = e.length; n < o; n++) i[n] = t(r ? s ? Vt(R(e[n])) : R(e[n]) : e[n], n, void 0, a && a[n]);
	} else if (typeof e == "number") {
		if (!Number.isInteger(e) || e < 0) i = [];
		else {
			i = Array(e);
			for (let n = 0; n < e; n++) i[n] = t(n + 1, n, void 0, a && a[n]);
		}
	} else if (v(e)) {
		if (e[Symbol.iterator]) i = Array.from(e, (e, n) => t(e, n, void 0, a && a[n]));
		else {
			let n = Object.keys(e);
			i = Array(n.length);
			for (let r = 0, o = n.length; r < o; r++) {
				let o = n[r];
				i[r] = t(e[o], o, r, a && a[r]);
			}
		}
	} else i = [];
	return n && (n[r] = i), i;
}
var mr = (e) => e ? oa(e) ? ha(e) : mr(e.parent) : null, hr = /* @__PURE__ */ s(/* @__PURE__ */ Object.create(null), {
	$: (e) => e,
	$el: (e) => e.vnode.el,
	$data: (e) => e.data,
	$props: (e) => e.props,
	$attrs: (e) => e.attrs,
	$slots: (e) => e.slots,
	$refs: (e) => e.refs,
	$parent: (e) => mr(e.parent),
	$root: (e) => mr(e.root),
	$host: (e) => e.ce,
	$emit: (e) => e.emit,
	$options: (e) => wr(e),
	$forceUpdate: (e) => e.f ||= () => {
		pn(e.update);
	},
	$nextTick: (e) => e.n ||= dn.bind(e.proxy),
	$watch: (e) => Nn.bind(e)
}), gr = (e, n) => e !== t && !e.__isScriptSetup && u(e, n), _r = {
	get({ _: e }, n) {
		if (n === "__v_skip") return !0;
		let { ctx: r, setupState: i, data: a, props: o, accessCache: s, type: c, appContext: l } = e;
		if (n[0] !== "$") {
			let e = s[n];
			if (e !== void 0) switch (e) {
				case 1: return i[n];
				case 2: return a[n];
				case 4: return r[n];
				case 3: return o[n];
			}
			else if (gr(i, n)) return s[n] = 1, i[n];
			else if (a !== t && u(a, n)) return s[n] = 2, a[n];
			else if (u(o, n)) return s[n] = 3, o[n];
			else if (r !== t && u(r, n)) return s[n] = 4, r[n];
			else yr && (s[n] = 0);
		}
		let d = hr[n], f, p;
		if (d) return n === "$attrs" && F(e.attrs, "get", ""), d(e);
		if ((f = c.__cssModules) && (f = f[n])) return f;
		if (r !== t && u(r, n)) return s[n] = 4, r[n];
		if (p = l.config.globalProperties, u(p, n)) return p[n];
	},
	set({ _: e }, n, r) {
		let { data: i, setupState: a, ctx: o } = e;
		return gr(a, n) ? (a[n] = r, !0) : i !== t && u(i, n) ? (i[n] = r, !0) : u(e.props, n) || n[0] === "$" && n.slice(1) in e ? !1 : (o[n] = r, !0);
	},
	has({ _: { data: e, setupState: n, accessCache: r, ctx: i, appContext: a, props: o, type: s } }, c) {
		let l;
		return !!(r[c] || e !== t && c[0] !== "$" && u(e, c) || gr(n, c) || u(o, c) || u(i, c) || u(hr, c) || u(a.config.globalProperties, c) || (l = s.__cssModules) && l[c]);
	},
	defineProperty(e, t, n) {
		return n.get == null ? u(n, "value") && this.set(e, t, n.value, null) : e._.accessCache[t] = 0, Reflect.defineProperty(e, t, n);
	}
};
function vr(e) {
	return d(e) ? e.reduce((e, t) => (e[t] = null, e), {}) : e;
}
var yr = !0;
function br(e) {
	let t = wr(e), n = e.proxy, i = e.ctx;
	yr = !1, t.beforeCreate && Sr(t.beforeCreate, e, "bc");
	let { data: a, computed: o, methods: s, watch: c, provide: l, inject: u, created: f, beforeMount: p, mounted: m, beforeUpdate: g, updated: _, activated: y, deactivated: b, beforeDestroy: x, beforeUnmount: S, destroyed: C, unmounted: w, render: T, renderTracked: ee, renderTriggered: te, errorCaptured: E, serverPrefetch: D, expose: O, inheritAttrs: ne, components: re, directives: k, filters: ie } = t;
	if (u && xr(u, i, null), s) for (let e in s) {
		let t = s[e];
		h(t) && (i[e] = t.bind(n));
	}
	if (a) {
		let t = a.call(n, n);
		v(t) && (e.data = /* @__PURE__ */ Nt(t));
	}
	if (yr = !0, o) for (let e in o) {
		let t = o[e], a = _a({
			get: h(t) ? t.bind(n, n) : h(t.get) ? t.get.bind(n, n) : r,
			set: !h(t) && h(t.set) ? t.set.bind(n) : r
		});
		Object.defineProperty(i, e, {
			enumerable: !0,
			configurable: !0,
			get: () => a.value,
			set: (e) => a.value = e
		});
	}
	if (c) for (let e in c) Cr(c[e], i, n, e);
	if (l) {
		let e = h(l) ? l.call(n) : l;
		Reflect.ownKeys(e).forEach((t) => {
			Dn(t, e[t]);
		});
	}
	f && Sr(f, e, "c");
	function A(e, t) {
		d(t) ? t.forEach((t) => e(t.bind(n))) : t && e(t.bind(n));
	}
	if (A(nr, p), A(rr, m), A(ir, g), A(ar, _), A(Xn, y), A(Zn, b), A(dr, E), A(ur, ee), A(lr, te), A(or, S), A(sr, w), A(cr, D), d(O)) {
		if (O.length) {
			let t = e.exposed ||= {};
			O.forEach((e) => {
				Object.defineProperty(t, e, {
					get: () => n[e],
					set: (t) => n[e] = t,
					enumerable: !0
				});
			});
		} else e.exposed ||= {};
	}
	T && e.render === r && (e.render = T), ne != null && (e.inheritAttrs = ne), re && (e.components = re), k && (e.directives = k), D && Un(e);
}
function xr(e, t, n = r) {
	d(e) && (e = kr(e));
	for (let n in e) {
		let r = e[n], i;
		i = v(r) ? "default" in r ? On(r.from || n, r.default, !0) : On(r.from || n) : On(r), /* @__PURE__ */ z(i) ? Object.defineProperty(t, n, {
			enumerable: !0,
			configurable: !0,
			get: () => i.value,
			set: (e) => i.value = e
		}) : t[n] = i;
	}
}
function Sr(e, t, n) {
	V(d(e) ? e.map((e) => e.bind(t.proxy)) : e.bind(t.proxy), t, n);
}
function Cr(e, t, n, r) {
	let i = r.includes(".") ? Pn(n, r) : () => n[r];
	if (g(e)) {
		let n = t[e];
		h(n) && jn(i, n);
	} else if (h(e)) jn(i, e.bind(n));
	else if (v(e)) {
		if (d(e)) e.forEach((e) => Cr(e, t, n, r));
		else {
			let r = h(e.handler) ? e.handler.bind(n) : t[e.handler];
			h(r) && jn(i, r, e);
		}
	}
}
function wr(e) {
	let t = e.type, { mixins: n, extends: r } = t, { mixins: i, optionsCache: a, config: { optionMergeStrategies: o } } = e.appContext, s = a.get(t), c;
	return s ? c = s : !i.length && !n && !r ? c = t : (c = {}, i.length && i.forEach((e) => Tr(c, e, o, !0)), Tr(c, t, o)), v(t) && a.set(t, c), c;
}
function Tr(e, t, n, r = !1) {
	let { mixins: i, extends: a } = t;
	a && Tr(e, a, n, !0), i && i.forEach((t) => Tr(e, t, n, !0));
	for (let i in t) if (!(r && i === "expose")) {
		let r = Er[i] || n && n[i];
		e[i] = r ? r(e[i], t[i]) : t[i];
	}
	return e;
}
var Er = {
	data: Dr,
	props: jr,
	emits: jr,
	methods: Ar,
	computed: Ar,
	beforeCreate: U,
	created: U,
	beforeMount: U,
	mounted: U,
	beforeUpdate: U,
	updated: U,
	beforeDestroy: U,
	beforeUnmount: U,
	destroyed: U,
	unmounted: U,
	activated: U,
	deactivated: U,
	errorCaptured: U,
	serverPrefetch: U,
	components: Ar,
	directives: Ar,
	watch: Mr,
	provide: Dr,
	inject: Or
};
function Dr(e, t) {
	return t ? e ? function() {
		return s(h(e) ? e.call(this, this) : e, h(t) ? t.call(this, this) : t);
	} : t : e;
}
function Or(e, t) {
	return Ar(kr(e), kr(t));
}
function kr(e) {
	if (d(e)) {
		let t = {};
		for (let n = 0; n < e.length; n++) t[e[n]] = e[n];
		return t;
	}
	return e;
}
function U(e, t) {
	return e ? [...new Set([].concat(e, t))] : t;
}
function Ar(e, t) {
	return e ? s(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function jr(e, t) {
	return e ? d(e) && d(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : s(/* @__PURE__ */ Object.create(null), vr(e), vr(t ?? {})) : t;
}
function Mr(e, t) {
	if (!e) return t;
	if (!t) return e;
	let n = s(/* @__PURE__ */ Object.create(null), e);
	for (let r in t) n[r] = U(e[r], t[r]);
	return n;
}
function Nr() {
	return {
		app: null,
		config: {
			isNativeTag: i,
			performance: !1,
			globalProperties: {},
			optionMergeStrategies: {},
			errorHandler: void 0,
			warnHandler: void 0,
			compilerOptions: {}
		},
		mixins: [],
		components: {},
		directives: {},
		provides: /* @__PURE__ */ Object.create(null),
		optionsCache: /* @__PURE__ */ new WeakMap(),
		propsCache: /* @__PURE__ */ new WeakMap(),
		emitsCache: /* @__PURE__ */ new WeakMap()
	};
}
var Pr = 0;
function Fr(e, t) {
	return function(n, r = null) {
		h(n) || (n = s({}, n)), r != null && !v(r) && (r = null);
		let i = Nr(), a = /* @__PURE__ */ new WeakSet(), o = [], c = !1, l = i.app = {
			_uid: Pr++,
			_component: n,
			_props: r,
			_container: null,
			_context: i,
			_instance: null,
			version: va,
			get config() {
				return i.config;
			},
			set config(e) {},
			use(e, ...t) {
				return a.has(e) || (e && h(e.install) ? (a.add(e), e.install(l, ...t)) : h(e) && (a.add(e), e(l, ...t))), l;
			},
			mixin(e) {
				return i.mixins.includes(e) || i.mixins.push(e), l;
			},
			component(e, t) {
				return t ? (i.components[e] = t, l) : i.components[e];
			},
			directive(e, t) {
				return t ? (i.directives[e] = t, l) : i.directives[e];
			},
			mount(a, o, s) {
				if (!c) {
					let u = l._ceVNode || Bi(n, r);
					return u.appContext = i, s === !0 ? s = "svg" : s === !1 && (s = void 0), o && t ? t(u, a) : e(u, a, s), c = !0, l._container = a, a.__vue_app__ = l, ha(u.component);
				}
			},
			onUnmount(e) {
				o.push(e);
			},
			unmount() {
				c && (V(o, l._instance, 16), e(null, l._container), delete l._container.__vue_app__);
			},
			provide(e, t) {
				return i.provides[e] = t, l;
			},
			runWithContext(e) {
				let t = Ir;
				Ir = l;
				try {
					return e();
				} finally {
					Ir = t;
				}
			}
		};
		return l;
	};
}
var Ir = null, Lr = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${E(t)}Modifiers`] || e[`${O(t)}Modifiers`];
function Rr(e, n, ...r) {
	if (e.isUnmounted) return;
	let i = e.vnode.props || t, a = r, o = n.startsWith("update:"), s = o && Lr(i, n.slice(7));
	s && (s.trim && (a = r.map((e) => g(e) ? e.trim() : e)), s.number && (a = a.map(ae)));
	let c, l = i[c = re(n)] || i[c = re(E(n))];
	!l && o && (l = i[c = re(O(n))]), l && V(l, e, 6, a);
	let u = i[c + "Once"];
	if (u) {
		if (!e.emitted) e.emitted = {};
		else if (e.emitted[c]) return;
		e.emitted[c] = !0, V(u, e, 6, a);
	}
}
var zr = /* @__PURE__ */ new WeakMap();
function Br(e, t, n = !1) {
	let r = n ? zr : t.emitsCache, i = r.get(e);
	if (i !== void 0) return i;
	let a = e.emits, o = {}, c = !1;
	if (!h(e)) {
		let r = (e) => {
			let n = Br(e, t, !0);
			n && (c = !0, s(o, n));
		};
		!n && t.mixins.length && t.mixins.forEach(r), e.extends && r(e.extends), e.mixins && e.mixins.forEach(r);
	}
	return !a && !c ? (v(e) && r.set(e, null), null) : (d(a) ? a.forEach((e) => o[e] = null) : s(o, a), v(e) && r.set(e, o), o);
}
function Vr(e, t) {
	return !e || !a(t) ? !1 : (t = t.slice(2), t = t === "Once" ? t : t.replace(/Once$/, ""), u(e, t[0].toLowerCase() + t.slice(1)) || u(e, O(t)) || u(e, t));
}
function Hr(e) {
	let { type: t, vnode: n, proxy: r, withProxy: i, propsOptions: [a], slots: s, attrs: c, emit: l, render: u, renderCache: d, props: f, data: p, setupState: m, ctx: h, inheritAttrs: g } = e, _ = wn(e), v, y;
	try {
		if (n.shapeFlag & 4) {
			let e = i || r, t = e;
			v = Ki(u.call(t, e, d, f, m, p, h)), y = c;
		} else {
			let e = t;
			v = Ki(e.length > 1 ? e(f, {
				attrs: c,
				slots: s,
				emit: l
			}) : e(f, null)), y = t.props ? c : Wr(c);
		}
	} catch (t) {
		Ai.length = 0, nn(t, e, 1), v = Bi(Oi);
	}
	let b = v;
	if (y && g !== !1) {
		let e = Object.keys(y), { shapeFlag: t } = b;
		e.length && t & 7 && (a && e.some(o) && (y = Gr(y, a)), b = Ui(b, y, !1, !0));
	}
	return n.dirs && (b = Ui(b, null, !1, !0), b.dirs = b.dirs ? b.dirs.concat(n.dirs) : n.dirs), n.transition && Bn(In(b.type) && zn(b) || b, n.transition), v = b, wn(_), v;
}
function Ur(e, t = !0) {
	let n;
	for (let t = 0; t < e.length; t++) {
		let r = e[t];
		if (Ii(r)) {
			if (r.type !== Oi || r.children === "v-if") {
				if (n) return;
				n = r;
			}
		} else return;
	}
	return n;
}
var Wr = (e) => {
	let t;
	for (let n in e) (n === "class" || n === "style" || a(n)) && ((t ||= {})[n] = e[n]);
	return t;
}, Gr = (e, t) => {
	let n = {};
	for (let r in e) o(r) && r.slice(9) in t || (n[r] = e[r]);
	return n;
};
function Kr(e, t, n) {
	let { props: r, children: i, component: a } = e, { props: o, children: s, patchFlag: c } = t, l = a.emitsOptions;
	if (t.dirs || t.transition) return !0;
	if (n && c >= 0) {
		if (c & 1024) return !0;
		if (c & 16) return r ? qr(r, o, l) : !!o;
		if (c & 8) {
			let e = t.dynamicProps;
			for (let t = 0; t < e.length; t++) {
				let n = e[t];
				if (Jr(o, r, n) && !Vr(l, n)) return !0;
			}
		}
	} else return (i || s) && (!s || !s.$stable) ? !0 : r === o ? !1 : r ? !o || qr(r, o, l) : !!o;
	return !1;
}
function qr(e, t, n) {
	let r = Object.keys(t);
	if (r.length !== Object.keys(e).length) return !0;
	for (let i = 0; i < r.length; i++) {
		let a = r[i];
		if (!u(e, a) || Jr(t, e, a) && !Vr(n, a)) return !0;
	}
	return !1;
}
function Jr(e, t, n) {
	let r = e[n], i = t[n];
	return n === "style" && v(r) && v(i) ? !ye(r, i) : r !== i;
}
function Yr({ vnode: e, parent: t, suspense: n }, r) {
	for (; t;) {
		let n = t.subTree;
		if (n.suspense && n.suspense.activeBranch === e && (n.suspense.vnode.el = n.el = r, e = n), n === e) (e = t.vnode).el = r, t = t.parent;
		else break;
	}
	n && n.activeBranch === e && (n.vnode.el = r);
}
var Xr = {}, Zr = () => Object.create(Xr), Qr = (e) => Object.getPrototypeOf(e) === Xr;
function $r(e, t, n, r = !1) {
	let i = {}, a = Zr();
	e.propsDefaults = /* @__PURE__ */ Object.create(null), ti(e, t, i, a);
	for (let t in e.propsOptions[0]) t in i || (i[t] = void 0);
	e.props = n ? r ? i : /* @__PURE__ */ Pt(i) : e.type.props ? i : a, e.attrs = a;
}
function ei(e, t, n, r) {
	let { props: i, attrs: a, vnode: { patchFlag: o } } = e, s = /* @__PURE__ */ L(i), [c] = e.propsOptions, l = !1;
	if ((r || o > 0) && !(o & 16)) {
		if (o & 8) {
			let n = e.vnode.dynamicProps;
			for (let r = 0; r < n.length; r++) {
				let o = n[r];
				if (Vr(e.emitsOptions, o)) continue;
				let d = t[o];
				if (c) {
					if (u(a, o)) d !== a[o] && (a[o] = d, l = !0);
					else {
						let t = E(o);
						i[t] = ni(c, s, t, d, e, !1);
					}
				} else d !== a[o] && (a[o] = d, l = !0);
			}
		}
	} else {
		ti(e, t, i, a) && (l = !0);
		let r;
		for (let a in s) t && (u(t, a) || (r = O(a)) !== a && u(t, r)) || (c ? n && (n[a] !== void 0 || n[r] !== void 0) && (i[a] = ni(c, s, a, void 0, e, !0)) : delete i[a]);
		if (a !== s) for (let e in a) t && u(t, e) || (delete a[e], l = !0);
	}
	l && Qe(e.attrs, "set", "");
}
function ti(e, n, r, i) {
	let [a, o] = e.propsOptions, s = !1, c;
	if (n) for (let t in n) {
		if (T(t)) continue;
		let l = n[t], d;
		a && u(a, d = E(t)) ? !o || !o.includes(d) ? r[d] = l : (c ||= {})[d] = l : Vr(e.emitsOptions, t) || t in i && l === i[t] || (i[t] = l, s = !0);
	}
	if (o) {
		let n = /* @__PURE__ */ L(r), i = c || t;
		for (let t = 0; t < o.length; t++) {
			let s = o[t];
			r[s] = ni(a, n, s, i[s], e, !u(i, s));
		}
	}
	return s;
}
function ni(e, t, n, r, i, a) {
	let o = e[n];
	if (o != null) {
		let e = u(o, "default");
		if (e && r === void 0) {
			let e = o.default;
			if (o.type !== Function && !o.skipFactory && h(e)) {
				let { propsDefaults: a } = i;
				if (n in a) r = a[n];
				else {
					let o = ia(i);
					r = a[n] = e.call(null, t), o();
				}
			} else r = e;
			i.ce && i.ce._setProp(n, r);
		}
		o[0] && (a && !e ? r = !1 : o[1] && (r === "" || r === O(n)) && (r = !0));
	}
	return r;
}
var ri = /* @__PURE__ */ new WeakMap();
function ii(e, r, i = !1) {
	let a = i ? ri : r.propsCache, o = a.get(e);
	if (o) return o;
	let c = e.props, l = {}, f = [], p = !1;
	if (!h(e)) {
		let t = (e) => {
			p = !0;
			let [t, n] = ii(e, r, !0);
			s(l, t), n && f.push(...n);
		};
		!i && r.mixins.length && r.mixins.forEach(t), e.extends && t(e.extends), e.mixins && e.mixins.forEach(t);
	}
	if (!c && !p) return v(e) && a.set(e, n), n;
	if (d(c)) for (let e = 0; e < c.length; e++) {
		let n = E(c[e]);
		ai(n) && (l[n] = t);
	}
	else if (c) for (let e in c) {
		let t = E(e);
		if (ai(t)) {
			let n = c[e], r = l[t] = d(n) || h(n) ? { type: n } : s({}, n), i = r.type, a = !1, o = !0;
			if (d(i)) for (let e = 0; e < i.length; ++e) {
				let t = i[e], n = h(t) && t.name;
				if (n === "Boolean") {
					a = !0;
					break;
				}
				n === "String" && (o = !1);
			}
			else a = h(i) && i.name === "Boolean";
			r[0] = a, r[1] = o, (a || u(r, "default")) && f.push(t);
		}
	}
	let m = [l, f];
	return v(e) && a.set(e, m), m;
}
function ai(e) {
	return e[0] !== "$" && !T(e);
}
var oi = (e) => e === "_" || e === "_ctx" || e === "$stable", si = (e) => d(e) ? e.map(Ki) : [Ki(e)], ci = (e, t, n) => {
	if (t._n) return t;
	let r = Tn((...e) => si(t(...e)), n);
	return r._c = !1, r;
}, li = (e, t, n) => {
	let r = e._ctx;
	for (let n in e) {
		if (oi(n)) continue;
		let i = e[n];
		if (h(i)) t[n] = ci(n, i, r);
		else if (i != null) {
			let e = si(i);
			t[n] = () => e;
		}
	}
}, ui = (e, t) => {
	let n = si(t);
	e.slots.default = () => n;
}, di = (e, t, n) => {
	for (let r in t) (n || !oi(r)) && (e[r] = t[r]);
}, fi = (e, t, n) => {
	let r = e.slots = Zr();
	if (e.vnode.shapeFlag & 32) {
		let e = t._;
		e ? (di(r, t, n), n && A(r, "_", e, !0)) : li(t, r);
	} else t && ui(e, t);
}, pi = (e, n, r) => {
	let { vnode: i, slots: a } = e, o = !0, s = t;
	if (i.shapeFlag & 32) {
		let e = n._;
		e ? r && e === 1 ? o = !1 : di(a, n, r) : (o = !n.$stable, li(n, a)), s = n;
	} else n && (ui(e, n), s = { default: 1 });
	if (o) for (let e in a) !oi(e) && s[e] == null && delete a[e];
}, W = Ei;
function mi(e) {
	return hi(e);
}
function hi(e, i) {
	let a = se();
	a.__VUE__ = !0;
	let { insert: o, remove: s, patchProp: c, createElement: l, createText: u, createComment: d, setText: f, setElementText: p, parentNode: m, nextSibling: h, setScopeId: g = r, insertStaticContent: _ } = e, v = (e, t, r, i = null, a = null, o = null, s = void 0, c = null, l = !!t.dynamicChildren) => {
		if (e === t) return;
		e && !Li(e, t) && (i = _e(e), j(e, a, o, !0), e = null), t.patchFlag === -2 && (l = !1, t.dynamicChildren = null), t.dynamicChildren && e && e.dynamicChildren && e.dynamicChildren.hasOnce && (t.dynamicChildren === n && (t.dynamicChildren = []), t.dynamicChildren.hasOnce = !0);
		let { type: u, ref: d, shapeFlag: f } = t;
		switch (u) {
			case Di:
				y(e, t, r, i);
				break;
			case Oi:
				b(e, t, r, i);
				break;
			case ki:
				e ?? x(t, r, i, s);
				break;
			case G:
				re(e, t, r, i, a, o, s, c, l);
				break;
			default: f & 1 ? w(e, t, r, i, a, o, s, c, l) : f & 6 ? k(e, t, r, i, a, o, s, c, l) : (f & 64 || f & 128) && u.process(e, t, r, i, a, o, s, c, l, ye);
		}
		d != null && a ? Kn(d, e && e.ref, o, t || e, !t) : d == null && e && e.ref != null && Kn(e.ref, null, o, e, !0);
	}, y = (e, t, n, r) => {
		if (e == null) o(t.el = u(t.children), n, r);
		else {
			let n = t.el = e.el;
			t.children !== e.children && f(n, t.children);
		}
	}, b = (e, t, n, r) => {
		e == null ? o(t.el = d(t.children || ""), n, r) : t.el = e.el;
	}, x = (e, t, n, r) => {
		[e.el, e.anchor] = _(e.children, t, n, r, e.el, e.anchor);
	}, S = ({ el: e, anchor: t }, n, r) => {
		let i;
		for (; e && e !== t;) i = h(e), o(e, n, r), e = i;
		o(t, n, r);
	}, C = ({ el: e, anchor: t }) => {
		let n;
		for (; e && e !== t;) n = h(e), s(e), e = n;
		s(t);
	}, w = (e, t, n, r, i, a, o, s, c) => {
		if (t.type === "svg" ? o = "svg" : t.type === "math" && (o = "mathml"), e == null) ee(t, n, r, i, a, o, s, c);
		else {
			let n = e.el && e.el._isVueCE ? e.el : null;
			try {
				n && n._beginPatch(), D(e, t, i, a, o, s, c);
			} finally {
				n && n._endPatch();
			}
		}
	}, ee = (e, t, n, r, i, a, s, u) => {
		let d, f, { props: m, shapeFlag: h, transition: g, dirs: _ } = e;
		if (d = e.el = l(e.type, a, m && m.is, m), h & 8 ? p(d, e.children) : h & 16 && E(e.children, d, null, r, i, gi(e, a), s, u), _ && En(e, null, r, "created"), te(d, e, e.scopeId, s, r), m) {
			for (let e in m) e !== "value" && !T(e) && c(d, e, null, m[e], a, r);
			"value" in m && c(d, "value", null, m.value, a), (f = m.onVnodeBeforeMount) && Xi(f, r, e);
		}
		_ && En(e, null, r, "beforeMount");
		let v = vi(i, g);
		v ? g.beforeEnter(d) : g && !g.persisted && (d[Ti] = !0), o(d, t, n), ((f = m && m.onVnodeMounted) || v || _) && W(() => {
			try {
				f && Xi(f, r, e), v && g.enter(d), _ && En(e, null, r, "mounted");
			} finally {}
		}, i);
	}, te = (e, t, n, r, i) => {
		if (n && g(e, n), r) for (let t = 0; t < r.length; t++) g(e, r[t]);
		if (i) {
			let n = i.subTree;
			if (t === n || wi(n.type) && (n.ssContent === t || n.ssFallback === t)) {
				let t = i.vnode;
				te(e, t, t.scopeId, t.slotScopeIds, i.parent);
			}
		}
	}, E = (e, t, n, r, i, a, o, s, c = 0) => {
		for (let l = c; l < e.length; l++) {
			let c = e[l] = s ? qi(e[l]) : Ki(e[l]);
			v(null, c, t, n, r, i, a, o, s);
		}
	}, D = (e, n, r, i, a, o, s) => {
		let l = n.el = e.el, { patchFlag: u, dynamicChildren: d, dirs: f } = n;
		u |= e.patchFlag & 16;
		let m = e.props || t, h = n.props || t, g;
		if (r && _i(r, !1), (g = h.onVnodeBeforeUpdate) && Xi(g, r, n, e), f && En(n, e, r, "beforeUpdate"), r && _i(r, !0), d && (!e.dynamicChildren || e.dynamicChildren.length !== d.length) && (u = 0, s = !1, d = null), (m.innerHTML && h.innerHTML == null || m.textContent && h.textContent == null) && p(l, ""), d ? O(e.dynamicChildren, d, l, r, i, gi(n, a), o) : s || le(e, n, l, null, r, i, gi(n, a), o, !1), u > 0) {
			if (u & 16) ne(l, m, h, r, a);
			else if (u & 2 && m.class !== h.class && c(l, "class", null, h.class, a), u & 4 && c(l, "style", m.style, h.style, a), u & 8) {
				let e = n.dynamicProps;
				for (let t = 0; t < e.length; t++) {
					let n = e[t], i = m[n], o = h[n];
					(o !== i || n === "value") && c(l, n, i, o, a, r);
				}
			}
			u & 1 && e.children !== n.children && p(l, n.children);
		} else !s && d == null && ne(l, m, h, r, a);
		((g = h.onVnodeUpdated) || f) && W(() => {
			g && Xi(g, r, n, e), f && En(n, e, r, "updated");
		}, i);
	}, O = (e, t, n, r, i, a, o) => {
		for (let s = 0; s < t.length; s++) {
			let c = e[s], l = t[s], u = c.el || Ci(c), d = u && (c.type === G || !Li(c, l) || c.shapeFlag & 198) ? m(u) : n;
			v(c, l, d, null, r, i, a, o, !0);
		}
	}, ne = (e, n, r, i, a) => {
		if (n !== r) {
			if (n !== t) for (let t in n) !T(t) && !(t in r) && c(e, t, n[t], null, a, i);
			for (let t in r) {
				if (T(t)) continue;
				let o = r[t], s = n[t];
				o !== s && t !== "value" && c(e, t, s, o, a, i);
			}
			"value" in r && c(e, "value", n.value, r.value, a);
		}
	}, re = (e, t, n, r, i, a, s, c, l) => {
		let d = t.el = e ? e.el : u(""), f = t.anchor = e ? e.anchor : u(""), { patchFlag: p, dynamicChildren: m, slotScopeIds: h } = t;
		h && (c = c ? c.concat(h) : h), e == null ? (o(d, n, r), o(f, n, r), E(t.children || [], n, f, i, a, s, c, l)) : p > 0 && p & 64 && m && e.dynamicChildren && e.dynamicChildren.length === m.length ? (O(e.dynamicChildren, m, n, i, a, s, c), (t.key != null || i && t === i.subTree) && yi(e, t, !0)) : le(e, t, n, f, i, a, s, c, l);
	}, k = (e, t, n, r, i, a, o, s, c) => {
		t.slotScopeIds = s, e == null ? t.shapeFlag & 512 ? i.ctx.activate(t, n, r, o, c) : A(t, n, r, i, a, o, c) : ae(e, t, c);
	}, A = (e, t, n, r, i, a, o) => {
		let s = e.component = ea(e, r, i);
		if (Yn(e) && (s.ctx.renderer = ye), ca(s, !1, o), s.asyncDep) {
			if (i && i.registerDep(s, oe, o, a), !e.el) {
				let r = s.subTree = Bi(Oi);
				b(null, r, t, n), e.placeholder = r.el;
			}
		} else oe(s, e, t, n, i, a, o);
	}, ae = (e, t, n) => {
		let r = t.component = e.component;
		if (Kr(e, t, n)) {
			if (r.asyncDep && !r.asyncResolved) {
				t.el = e.el, t.placeholder = e.placeholder, ce(r, t, n);
				return;
			}
			r.next = t, r.update();
		} else t.el = e.el, t.placeholder = e.placeholder, r.vnode = t;
	}, oe = (e, t, n, r, i, a, o) => {
		let s = () => {
			if (e.isMounted) {
				let { next: t, bu: n, u: r, parent: s, vnode: c } = e;
				{
					let n = xi(e);
					if (n) {
						t && (t.el = c.el, ce(e, t, o)), n.asyncDep.then(() => {
							let t = () => {
								e.job.flags & 8 || (i && i.pendingBranch ? W(t, i) : l());
							};
							t.flags = 48, W(t, i);
						});
						return;
					}
				}
				let u = t, d;
				_i(e, !1), t ? (t.el = c.el, ce(e, t, o)) : t = c, n && ie(n), (d = t.props && t.props.onVnodeBeforeUpdate) && Xi(d, s, t, c), _i(e, !0);
				let f = Hr(e), p = e.subTree;
				e.subTree = f, v(p, f, m(p.el || Ci(p)), _e(p), e, i, a), t.el = f.el, u === null && Yr(e, f.el), r && W(r, i), (d = t.props && t.props.onVnodeUpdated) && W(() => Xi(d, s, t, c), i);
			} else {
				let o, { el: s, props: c } = t, { bm: l, m: u, parent: d, root: f, type: p } = e, m = Jn(t);
				if (_i(e, !1), l && ie(l), !m && (o = c && c.onVnodeBeforeMount) && Xi(o, d, t), _i(e, !0), s && M) {
					let t = () => {
						e.subTree = Hr(e), M(s, e.subTree, e, i, null);
					};
					m && p.__asyncHydrate ? p.__asyncHydrate(s, e, t) : t();
				} else {
					f.ce && f.ce._hasShadowRoot() && f.ce._injectChildStyle(p, e.parent ? e.parent.type : void 0);
					let o = e.subTree = Hr(e);
					v(null, o, n, r, e, i, a), t.el = o.el;
				}
				if (u && W(u, i), !m && (o = c && c.onVnodeMounted)) {
					let e = t;
					W(() => Xi(o, d, e), i);
				}
				(t.shapeFlag & 256 || d && Jn(d.vnode) && d.vnode.shapeFlag & 256) && e.a && W(e.a, i), e.isMounted = !0, t = n = r = null;
			}
		};
		e.scope.on();
		let c = e.effect = new Ee(s);
		e.scope.off();
		let l = e.update = c.run.bind(c), u = e.job = c.runIfDirty.bind(c);
		u.i = e, u.id = e.uid, c.scheduler = () => pn(u), _i(e, !0), l();
	}, ce = (e, t, n) => {
		t.component = e;
		let r = e.vnode.props;
		e.vnode = t, e.next = null, ei(e, t.props, r, n), pi(e, t.children, n), Ve(), gn(e), He();
	}, le = (e, t, n, r, i, a, o, s, c = !1) => {
		let l = e && e.children, u = e ? e.shapeFlag : 0, d = t.children, { patchFlag: f, shapeFlag: m } = t;
		if (f > 0) {
			if (f & 128) {
				de(l, d, n, r, i, a, o, s, c);
				return;
			}
			if (f & 256) {
				ue(l, d, n, r, i, a, o, s, c);
				return;
			}
		}
		m & 8 ? (u & 16 && ge(l, i, a), d !== l && p(n, d)) : u & 16 ? m & 16 ? de(l, d, n, r, i, a, o, s, c) : ge(l, i, a, !0) : (u & 8 && p(n, ""), m & 16 && E(d, n, r, i, a, o, s, c));
	}, ue = (e, t, r, i, a, o, s, c, l) => {
		e ||= n, t ||= n;
		let u = e.length, d = t.length, f = Math.min(u, d), p = 0;
		for (; p < f; p++) {
			let n = t[p] = l ? qi(t[p]) : Ki(t[p]);
			v(e[p], n, r, null, a, o, s, c, l);
		}
		u > d ? ge(e, a, o, !0, !1, f) : E(t, r, i, a, o, s, c, l, f);
	}, de = (e, t, r, i, a, o, s, c, l) => {
		let u = 0, d = t.length, f = e.length - 1, p = d - 1;
		for (; u <= f && u <= p;) {
			let n = e[u], i = t[u] = l ? qi(t[u]) : Ki(t[u]);
			if (Li(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			u++;
		}
		for (; u <= f && u <= p;) {
			let n = e[f], i = t[p] = l ? qi(t[p]) : Ki(t[p]);
			if (Li(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			f--, p--;
		}
		if (u > f) {
			if (u <= p) {
				let e = p + 1, n = e < d ? t[e].el : i;
				for (; u <= p;) v(null, t[u] = l ? qi(t[u]) : Ki(t[u]), r, n, a, o, s, c, l), u++;
			}
		} else if (u > p) for (; u <= f;) j(e[u], a, o, !0), u++;
		else {
			let m = u, h = u, g = /* @__PURE__ */ new Map();
			for (u = h; u <= p; u++) {
				let e = t[u] = l ? qi(t[u]) : Ki(t[u]);
				e.key != null && g.set(e.key, u);
			}
			let _, y = 0, b = p - h + 1, x = !1, S = 0, C = Array(b);
			for (u = 0; u < b; u++) C[u] = 0;
			for (u = m; u <= f; u++) {
				let n = e[u];
				if (y >= b) {
					j(n, a, o, !0);
					continue;
				}
				let i;
				if (n.key != null) i = g.get(n.key);
				else for (_ = h; _ <= p; _++) if (C[_ - h] === 0 && Li(n, t[_])) {
					i = _;
					break;
				}
				i === void 0 ? j(n, a, o, !0) : (C[i - h] = u + 1, i >= S ? S = i : x = !0, v(n, t[i], r, null, a, o, s, c, l), y++);
			}
			let w = x ? bi(C) : n;
			for (_ = w.length - 1, u = b - 1; u >= 0; u--) {
				let e = h + u, n = t[e], f = t[e + 1], p = e + 1 < d ? f.el || Ci(f) : i;
				C[u] === 0 ? v(null, n, r, p, a, o, s, c, l) : x && (_ < 0 || u !== w[_] ? fe(n, r, p, 2) : _--);
			}
		}
	}, fe = (e, t, n, r, i = null) => {
		let { el: a, type: c, transition: l, children: u, shapeFlag: d } = e;
		if (d & 6) fe(e.component.subTree, t, n, r);
		else if (d & 128) e.suspense.move(t, n, r);
		else if (d & 64) c.move(e, t, n, ye);
		else if (c === G) {
			o(a, t, n);
			for (let e = 0; e < u.length; e++) fe(u[e], t, n, r);
			o(e.anchor, t, n);
		} else if (c === ki) S(e, t, n);
		else if (r !== 2 && d & 1 && l) {
			if (r === 0) l.persisted && !a[Ln] ? o(a, t, n) : (l.beforeEnter(a), o(a, t, n), W(() => l.enter(a), i));
			else {
				let { leave: r, delayLeave: i, afterLeave: c } = l, u = () => {
					e.ctx.isUnmounted ? s(a) : o(a, t, n);
				}, d = () => {
					let e = a._isLeaving || !!a[Ln];
					a._isLeaving && a[Ln](!0), l.persisted && !e ? u() : r(a, () => {
						u(), c && c();
					});
				};
				i ? i(a, u, d) : d();
			}
		} else o(a, t, n);
	}, j = (e, t, n, r = !1, i = !1) => {
		let { type: a, props: o, ref: s, children: c, dynamicChildren: l, shapeFlag: u, patchFlag: d, dirs: f, cacheIndex: p, memo: m } = e;
		if ((d === -2 || l && l.hasOnce) && (i = !1), s != null && (Ve(), Kn(s, null, n, e, !0), He()), p == null || e.ctx && e.ctx !== t || (t.renderCache[p] = void 0), u & 256 && t.ctx.deactivate(e)) return;
		let h = u & 1 && f, g = !Jn(e), _;
		if (g && (_ = o && o.onVnodeBeforeUnmount) && Xi(_, t, e), u & 6) he(e.component, n, r);
		else {
			if (u & 128) {
				e.suspense.unmount(n, r);
				return;
			}
			h && En(e, null, t, "beforeUnmount"), u & 64 ? e.type.remove(e, t, n, ye, r) : l && !l.hasOnce && (a !== G || d > 0 && d & 64) ? ge(l, t, n, !1, !0) : (a === G && d & 384 || !i && u & 16) && ge(c, t, n), r && pe(e);
		}
		let v = m != null && p == null;
		(g && (_ = o && o.onVnodeUnmounted) || h || v) && W(() => {
			_ && Xi(_, t, e), h && En(e, null, t, "unmounted"), v && (e.el = null);
		}, n);
	}, pe = (e) => {
		let { type: t, el: n, anchor: r, transition: i } = e, a = t === G;
		if (a && !i) {
			me(n, r);
			return;
		}
		if (t === ki) {
			C(e), i && !i.persisted && i.afterLeave && i.afterLeave();
			return;
		}
		let o = a ? Vn(e) : e, c = () => {
			a ? m(n) && me(n, r) : s(n), i && !i.persisted && i.afterLeave && i.afterLeave();
		};
		if (o && o.shapeFlag & 1 && i && !i.persisted) {
			let { leave: e, delayLeave: t } = i, n = o.el, r = () => e(n, c);
			t ? t(n, c, r) : r();
		} else c();
	}, me = (e, t) => {
		let n;
		for (; e !== t;) n = h(e), s(e), e = n;
		s(t);
	}, he = (e, t, n) => {
		let { bum: r, scope: i, job: a, subTree: o, um: s, m: c, a: l } = e;
		Si(c), Si(l), r && ie(r), i.stop(), a ? (a.flags |= 8, j(o, e, t, n)) : o && (o.transition = e.vnode.transition, j(o, e, t, n)), s && W(s, t);
		let u = () => {
			e.isUnmounted = !0;
		};
		u.flags = 16, W(u, t);
	}, ge = (e, t, n, r = !1, i = !1, a = 0) => {
		for (let o = a; o < e.length; o++) j(e[o], t, n, r, i);
	}, _e = (e) => {
		if (e.shapeFlag & 6) return _e(e.component.subTree);
		if (e.shapeFlag & 128) return e.suspense.next();
		let t = h(e.anchor || e.el), n = t && t[Fn];
		return n ? h(n) : t;
	}, ve = (e, t, n) => {
		yn(() => {
			e == null ? t._vnode && j(t._vnode, null, null, !0) : v(t._vnode || null, e, t, null, null, null, n), t._vnode = e;
		}, e && t._vnode ? void 0 : e && e.component ? e.component.uid : $i());
	}, ye = {
		p: v,
		um: j,
		m: fe,
		r: pe,
		mt: A,
		mc: E,
		pc: le,
		pbc: O,
		n: _e,
		o: e
	}, be, M;
	return i && ([be, M] = i(ye)), {
		render: ve,
		hydrate: be,
		createApp: Fr(ve, be)
	};
}
function gi({ type: e, props: t }, n) {
	return n === "svg" && e === "foreignObject" || n === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : n;
}
function _i({ effect: e, job: t }, n) {
	n ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function vi(e, t) {
	return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function yi(e, t, n = !1) {
	let r = e.children, i = t.children;
	if (d(r) && d(i)) for (let e = 0; e < r.length; e++) {
		let t = r[e], a = i[e];
		a.shapeFlag & 1 && !a.dynamicChildren && ((a.patchFlag <= 0 || a.patchFlag === 32) && (a = i[e] = qi(i[e]), a.el = t.el), !n && a.patchFlag !== -2 && yi(t, a)), a.type === Di && (a.patchFlag === -1 && (a = i[e] = qi(a)), a.el = t.el), a.type === Oi && !a.el && (a.el = t.el);
	}
}
function bi(e) {
	let t = e.slice(), n = [0], r, i, a, o, s, c = e.length;
	for (r = 0; r < c; r++) {
		let c = e[r];
		if (c !== 0) {
			if (i = n[n.length - 1], e[i] < c) {
				t[r] = i, n.push(r);
				continue;
			}
			for (a = 0, o = n.length - 1; a < o;) s = a + o >> 1, e[n[s]] < c ? a = s + 1 : o = s;
			c < e[n[a]] && (a > 0 && (t[r] = n[a - 1]), n[a] = r);
		}
	}
	for (a = n.length, o = n[a - 1]; a-- > 0;) n[a] = o, o = t[o];
	return n;
}
function xi(e) {
	let t = e.subTree.component;
	if (t) return t.asyncDep && !t.asyncResolved ? t : xi(t);
}
function Si(e) {
	if (e) for (let t = 0; t < e.length; t++) e[t].flags |= 8;
}
function Ci(e) {
	if (e.placeholder) return e.placeholder;
	let t = e.component;
	if (t) return Ci(t.subTree);
	let n = e.suspense;
	return n && n.activeBranch ? Ci(n.activeBranch) : null;
}
var wi = (e) => e.__isSuspense, Ti = /* @__PURE__ */ Symbol("_deferredEnter");
function Ei(e, t) {
	t && t.pendingBranch ? d(e) ? t.effects.push(...e) : t.effects.push(e) : hn(e);
}
var G = /* @__PURE__ */ Symbol.for("v-fgt"), Di = /* @__PURE__ */ Symbol.for("v-txt"), Oi = /* @__PURE__ */ Symbol.for("v-cmt"), ki = /* @__PURE__ */ Symbol.for("v-stc"), Ai = [], K = null;
function q(e = !1) {
	Ai.push(K = e ? null : []);
}
function ji() {
	Ai.pop(), K = Ai[Ai.length - 1] || null;
}
var Mi = 1;
function Ni(e, t = !1) {
	Mi += e, e < 0 && K && t && (K.hasOnce = !0);
}
function Pi(e) {
	return e.dynamicChildren = Mi > 0 ? K || n : null, ji(), Mi > 0 && K && K.push(e), e;
}
function J(e, t, n, r, i, a) {
	return Pi(Y(e, t, n, r, i, a, !0));
}
function Fi(e, t, n, r, i) {
	return Pi(Bi(e, t, n, r, i, !0));
}
function Ii(e) {
	return e ? e.__v_isVNode === !0 : !1;
}
function Li(e, t) {
	return e.type === t.type && e.key === t.key;
}
var Ri = ({ key: e }) => e ?? null, zi = ({ ref: e, ref_key: t, ref_for: n }) => (typeof e == "number" && (e = "" + e), e == null ? null : g(e) || /* @__PURE__ */ z(e) || h(e) ? {
	i: Sn,
	r: e,
	k: t,
	f: !!n
} : e);
function Y(e, t = null, n = null, r = 0, i = null, a = e === G ? 0 : 1, o = !1, s = !1) {
	let c = {
		__v_isVNode: !0,
		__v_skip: !0,
		type: e,
		props: t,
		key: t && Ri(t),
		ref: t && zi(t),
		scopeId: Cn,
		slotScopeIds: null,
		children: n,
		component: null,
		suspense: null,
		ssContent: null,
		ssFallback: null,
		dirs: null,
		transition: null,
		el: null,
		anchor: null,
		target: null,
		targetStart: null,
		targetAnchor: null,
		staticCount: 0,
		shapeFlag: a,
		patchFlag: r,
		dynamicProps: i,
		dynamicChildren: null,
		appContext: null,
		ctx: Sn
	};
	return s ? (Ji(c, n), a & 128 && e.normalize(c)) : n && (c.shapeFlag |= g(n) ? 8 : 16), Mi > 0 && !o && K && (c.patchFlag > 0 || a & 6) && c.patchFlag !== 32 && K.push(c), c;
}
var Bi = Vi;
function Vi(e, t = null, n = null, r = 0, i = null, a = !1) {
	if (e && e !== fr || (e = Oi), Ii(e)) {
		let r = Ui(e, t, !0);
		return n && Ji(r, n), Mi > 0 && !a && K && (r.shapeFlag & 6 ? K[K.indexOf(e)] = r : K.push(r)), r.patchFlag = -2, r;
	}
	if (ga(e) && (e = e.__vccOpts), t) {
		t = Hi(t);
		let { class: e, style: n } = t;
		e && !g(e) && (t.class = j(e)), v(n) && (/* @__PURE__ */ zt(n) && !d(n) && (n = s({}, n)), t.style = ce(n));
	}
	let o = g(e) ? 1 : wi(e) ? 128 : In(e) ? 64 : v(e) ? 4 : h(e) ? 2 : 0;
	return Y(e, t, n, r, i, o, a, !0);
}
function Hi(e) {
	return e ? /* @__PURE__ */ zt(e) ? s({}, e) : Qr(e) ? s({}, e[fa] || e) : e : null;
}
function Ui(e, t, n = !1, r = !1) {
	let { props: i, ref: a, patchFlag: o, children: s, transition: c } = e, l = t ? Yi(i || {}, t) : i, u = {
		__v_isVNode: !0,
		__v_skip: !0,
		type: e.type,
		props: l,
		key: l && Ri(l),
		ref: t && t.ref ? n && a ? d(a) ? a.concat(zi(t)) : [a, zi(t)] : zi(t) : a,
		scopeId: e.scopeId,
		slotScopeIds: e.slotScopeIds,
		children: s,
		target: e.target,
		targetStart: e.targetStart,
		targetAnchor: e.targetAnchor,
		staticCount: e.staticCount,
		shapeFlag: e.shapeFlag,
		patchFlag: t && e.type !== G ? o === -1 ? 16 : o | 16 : o,
		dynamicProps: e.dynamicProps,
		dynamicChildren: e.dynamicChildren,
		appContext: e.appContext,
		dirs: e.dirs,
		transition: c,
		component: e.component,
		suspense: e.suspense,
		ssContent: e.ssContent && Ui(e.ssContent),
		ssFallback: e.ssFallback && Ui(e.ssFallback),
		placeholder: e.placeholder,
		el: e.el,
		anchor: e.anchor,
		ctx: e.ctx,
		ce: e.ce,
		cacheIndex: e.cacheIndex
	};
	return c && r && Bn(u, c.clone(u)), u;
}
function Wi(e = " ", t = 0) {
	return Bi(Di, null, e, t);
}
function Gi(e, t) {
	let n = Bi(ki, null, e);
	return n.staticCount = t, n;
}
function X(e = "", t = !1) {
	return t ? (q(), Fi(Oi, null, e)) : Bi(Oi, null, e);
}
function Ki(e) {
	return e == null || typeof e == "boolean" ? Bi(Oi) : d(e) ? Bi(G, null, e.slice()) : Ii(e) ? qi(e) : Bi(Di, null, String(e));
}
function qi(e) {
	return e.el === null && e.patchFlag !== -1 || e.memo ? e : Ui(e);
}
function Ji(e, t) {
	let n = 0, { shapeFlag: r } = e;
	if (t == null) t = null;
	else if (d(t)) n = 16;
	else if (typeof t == "object") {
		if (r & 65) {
			let n = t.default;
			n && (n._c && (n._d = !1), Ji(e, n()), n._c && (n._d = !0));
			return;
		}
		{
			n = 32;
			let r = t._;
			!r && !Qr(t) ? t._ctx = Sn : r === 3 && Sn && (Sn.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
		}
	} else if (h(t)) {
		if (r & 65) {
			Ji(e, { default: t });
			return;
		}
		t = {
			default: t,
			_ctx: Sn
		}, n = 32;
	} else t = String(t), r & 64 ? (n = 16, t = [Wi(t)]) : n = 8;
	e.children = t, e.shapeFlag |= n;
}
function Yi(...e) {
	let t = {};
	for (let n = 0; n < e.length; n++) {
		let r = e[n];
		for (let e in r) if (e === "class") t.class !== r.class && (t.class = j([t.class, r.class]));
		else if (e === "style") t.style = ce([t.style, r.style]);
		else if (a(e)) {
			let n = t[e], i = r[e];
			i && n !== i && !(d(n) && n.includes(i)) ? t[e] = n ? [].concat(n, i) : i : i == null && n == null && !o(e) && (t[e] = i);
		} else e !== "" && (t[e] = r[e]);
	}
	return t;
}
function Xi(e, t, n, r = null) {
	V(e, t, 7, [n, r]);
}
var Zi = /* @__PURE__ */ Nr(), Qi = 0;
function $i() {
	return Qi;
}
function ea(e, n, r) {
	let i = e.type, a = (n ? n.appContext : e.appContext) || Zi, o = {
		uid: Qi++,
		vnode: e,
		type: i,
		parent: n,
		appContext: a,
		root: null,
		next: null,
		subTree: null,
		effect: null,
		update: null,
		job: null,
		scope: new Ce(!0),
		render: null,
		proxy: null,
		exposed: null,
		exposeProxy: null,
		withProxy: null,
		provides: n ? n.provides : Object.create(a.provides),
		ids: n ? n.ids : [
			"",
			0,
			0
		],
		accessCache: null,
		renderCache: [],
		components: null,
		directives: null,
		propsOptions: ii(i, a),
		emitsOptions: Br(i, a),
		emit: null,
		emitted: null,
		propsDefaults: t,
		inheritAttrs: i.inheritAttrs,
		ctx: t,
		data: t,
		props: t,
		attrs: t,
		slots: t,
		refs: t,
		setupState: t,
		setupContext: null,
		suspense: r,
		suspenseId: r ? r.pendingId : 0,
		asyncDep: null,
		asyncResolved: !1,
		isMounted: !1,
		isUnmounted: !1,
		isDeactivated: !1,
		bc: null,
		c: null,
		bm: null,
		m: null,
		bu: null,
		u: null,
		um: null,
		bum: null,
		da: null,
		a: null,
		rtg: null,
		rtc: null,
		ec: null,
		sp: null
	};
	return o.ctx = { _: o }, o.root = n ? n.root : o, o.emit = Rr.bind(null, o), e.ce && e.ce(o), o;
}
var Z = null, ta = () => Z || Sn, na, ra;
{
	let e = se(), t = (t, n) => {
		let r;
		return (r = e[t]) || (r = e[t] = []), r.push(n), (e) => {
			r.length > 1 ? r.forEach((t) => t(e)) : r[0](e);
		};
	};
	na = t("__VUE_INSTANCE_SETTERS__", (e) => Z = e), ra = t("__VUE_SSR_SETTERS__", (e) => sa = e);
}
var ia = (e) => {
	let t = Z;
	return na(e), e.scope.on(), () => {
		e.scope.off(), na(t);
	};
}, aa = () => {
	Z && Z.scope.off(), na(null);
};
function oa(e) {
	return e.vnode.shapeFlag & 4;
}
var sa = !1;
function ca(e, t = !1, n = !1) {
	t && ra(t);
	let { props: r, children: i } = e.vnode, a = oa(e);
	$r(e, r, a, t), fi(e, i, n || t);
	let o = a ? la(e, t) : void 0;
	return t && ra(!1), o;
}
function la(e, t) {
	let n = e.type;
	e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, _r);
	let { setup: r } = n;
	if (r) {
		Ve();
		let n = e.setupContext = r.length > 1 ? ma(e) : null, i = ia(e), a = tn(r, e, 0, [e.props, n]), o = y(a);
		if (He(), i(), (o || e.sp) && !Jn(e) && Un(e), o) {
			if (a.then(aa, aa), t) return a.then((n) => {
				ra(!0);
				try {
					ua(e, n, t);
				} finally {
					ra(!1);
				}
			}).catch((t) => {
				nn(t, e, 0, void 0, !0), e.ssrRender = (e, t) => t("<!---->");
			});
			e.asyncDep = a;
		} else ua(e, a, t);
	} else da(e, t);
}
function ua(e, t, n) {
	h(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : v(t) && (e.setupState = Kt(t)), da(e, n);
}
function da(e, t, n) {
	let i = e.type;
	e.render ||= i.render || r;
	{
		let t = ia(e);
		Ve();
		try {
			br(e);
		} finally {
			He(), t();
		}
	}
}
var fa = /* @__PURE__ */ Symbol(), pa = { get(e, t) {
	return F(e, "get", ""), t === fa ? e : e[t];
} };
function ma(e) {
	return {
		attrs: new Proxy(e.attrs, pa),
		slots: e.slots,
		emit: e.emit,
		expose: (t) => {
			e.exposed = t || {};
		}
	};
}
function ha(e) {
	return e.exposed ? e.exposeProxy ||= new Proxy(Kt(Bt(e.exposed)), {
		get(t, n) {
			if (n in t) return t[n];
			if (n in hr) return hr[n](e);
		},
		has(e, t) {
			return t in e || t in hr;
		}
	}) : e.proxy;
}
function ga(e) {
	return h(e) && "__vccOpts" in e;
}
var _a = (e, t) => /* @__PURE__ */ Jt(e, t, sa), va = "3.5.45", ya = void 0, ba = typeof window < "u" && window.trustedTypes;
if (ba) try {
	ya = /* @__PURE__ */ ba.createPolicy("vue", { createHTML: (e) => e });
} catch {}
var xa = ya ? (e) => ya.createHTML(e) : (e) => e, Sa = "http://www.w3.org/2000/svg", Ca = "http://www.w3.org/1998/Math/MathML", wa = typeof document < "u" ? document : null, Ta = wa && /* @__PURE__ */ wa.createElement("template"), Ea = {
	insert: (e, t, n) => {
		t.insertBefore(e, n || null);
	},
	remove: (e) => {
		let t = e.parentNode;
		t && t.removeChild(e);
	},
	createElement: (e, t, n, r) => {
		let i = t === "svg" ? wa.createElementNS(Sa, e) : t === "mathml" ? wa.createElementNS(Ca, e) : n ? wa.createElement(e, { is: n }) : wa.createElement(e);
		return e === "select" && r && r.multiple != null && i.setAttribute("multiple", r.multiple), i;
	},
	createText: (e) => wa.createTextNode(e),
	createComment: (e) => wa.createComment(e),
	setText: (e, t) => {
		e.nodeValue = t;
	},
	setElementText: (e, t) => {
		e.textContent = t;
	},
	parentNode: (e) => e.parentNode,
	nextSibling: (e) => e.nextSibling,
	querySelector: (e) => wa.querySelector(e),
	setScopeId(e, t) {
		e.setAttribute(t, "");
	},
	insertStaticContent(e, t, n, r, i, a) {
		let o = n ? n.previousSibling : t.lastChild;
		if (i && (i === a || i.nextSibling)) for (; t.insertBefore(i.cloneNode(!0), n), i !== a && (i = i.nextSibling););
		else {
			Ta.innerHTML = xa(r === "svg" ? `<svg>${e}</svg>` : r === "mathml" ? `<math>${e}</math>` : e);
			let i = Ta.content;
			if (r === "svg" || r === "mathml") {
				let e = i.firstChild;
				for (; e.firstChild;) i.appendChild(e.firstChild);
				i.removeChild(e);
			}
			t.insertBefore(i, n);
		}
		return [o ? o.nextSibling : t.firstChild, n ? n.previousSibling : t.lastChild];
	}
}, Da = /* @__PURE__ */ Symbol("_vtc");
function Oa(e, t, n) {
	let r = e[Da];
	r && (t = (t ? [t, ...r] : [...r]).join(" ")), t == null ? e.removeAttribute("class") : n ? e.setAttribute("class", t) : e.className = t;
}
var ka = /* @__PURE__ */ Symbol("_vod"), Aa = /* @__PURE__ */ Symbol("_vsh"), ja = /* @__PURE__ */ Symbol(""), Ma = /(?:^|;)\s*display\s*:/;
function Na(e, t, n) {
	let r = e.style, i = g(n), a = !1;
	if (n && !i) {
		if (t) {
			if (g(t)) for (let e of t.split(";")) {
				let t = e.slice(0, e.indexOf(":")).trim();
				n[t] ?? Fa(r, t, "");
			}
			else for (let e in t) n[e] ?? Fa(r, e, "");
		}
		for (let i in n) {
			i === "display" && (a = !0);
			let o = n[i];
			o == null ? Fa(r, i, "") : za(e, i, !g(t) && t ? t[i] : void 0, o) || Fa(r, i, o);
		}
	} else if (i) {
		if (t !== n) {
			let e = r[ja];
			e && (n += ";" + e), r.cssText = n, a = Ma.test(n);
		}
	} else t && e.removeAttribute("style");
	ka in e && (i && t === n || (e[ka] = a ? r.display : ""), e[Aa] && (r.display = "none"));
}
var Pa = /\s*!important$/;
function Fa(e, t, n) {
	if (d(n)) n.forEach((n) => Fa(e, t, n));
	else if (n ??= "", t.startsWith("--")) Pa.test(n) ? e.setProperty(t, n.replace(Pa, ""), "important") : e.setProperty(t, n);
	else {
		let r = Ra(e, t);
		Pa.test(n) ? e.setProperty(O(r), n.replace(Pa, ""), "important") : e[r] = n;
	}
}
var Ia = [
	"Webkit",
	"Moz",
	"ms"
], La = {};
function Ra(e, t) {
	let n = La[t];
	if (n) return n;
	let r = E(t);
	if (r !== "filter" && r in e) return La[t] = r;
	r = ne(r);
	for (let n = 0; n < Ia.length; n++) {
		let i = Ia[n] + r;
		if (i in e) return La[t] = i;
	}
	return t;
}
function za(e, t, n, r) {
	return e.tagName === "TEXTAREA" && (t === "width" || t === "height") && g(r) && n === r;
}
var Ba = "http://www.w3.org/1999/xlink";
function Va(e, t, n, r, i, a = pe(t)) {
	r && t.startsWith("xlink:") ? n == null ? e.removeAttributeNS(Ba, t.slice(6, t.length)) : e.setAttributeNS(Ba, t, n) : n == null || a && !me(n) ? e.removeAttribute(t) : e.setAttribute(t, a ? "" : _(n) ? String(n) : n);
}
function Ha(e, t, n, r, i) {
	if (t === "innerHTML" || t === "textContent") {
		n != null && (e[t] = t === "innerHTML" ? xa(n) : n);
		return;
	}
	let a = e.tagName;
	if (t === "value" && a !== "PROGRESS" && !a.includes("-")) {
		let r = a === "OPTION" ? e.getAttribute("value") || "" : e.value, i = n == null ? e.type === "checkbox" ? "on" : "" : String(n);
		r === i && "_value" in e || (e.value = i), n ?? e.removeAttribute(t), e._value = n;
		return;
	}
	let o = !1;
	if (n === "" || n == null) {
		let r = typeof e[t];
		r === "boolean" ? n = me(n) : n == null && r === "string" ? (n = "", o = !0) : r === "number" && (n = 0, o = !0);
	}
	try {
		e[t] = n;
	} catch {}
	o && e.removeAttribute(i || t);
}
function Ua(e, t, n, r) {
	e.addEventListener(t, n, r);
}
function Wa(e, t, n, r) {
	e.removeEventListener(t, n, r);
}
var Ga = /* @__PURE__ */ Symbol("_vei");
function Ka(e, t, n, r, i = null) {
	let a = e[Ga] || (e[Ga] = {}), o = a[t];
	if (r && o) o.value = r;
	else {
		let [n, s] = Ya(t);
		r ? Ua(e, n, a[t] = $a(r, i), s) : o && (Wa(e, n, o, s), a[t] = void 0);
	}
}
var qa = /(Once|Passive|Capture)$/, Ja = /^on:?(?:Once|Passive|Capture)$/;
function Ya(e) {
	let t, n;
	for (; (n = e.match(qa)) && !Ja.test(e);) t ||= {}, e = e.slice(0, e.length - n[1].length), t[n[1].toLowerCase()] = !0;
	return [e[2] === ":" ? e.slice(3) : O(e.slice(2)), t];
}
var Xa = 0, Za = /* @__PURE__ */ Promise.resolve(), Qa = () => Xa ||= (Za.then(() => Xa = 0), Date.now());
function $a(e, t) {
	let n = (e) => {
		if (!e._vts) e._vts = Date.now();
		else if (e._vts <= n.attached) return;
		let r = n.value;
		if (d(r)) {
			let n = e.stopImmediatePropagation;
			e.stopImmediatePropagation = () => {
				n.call(e), e._stopped = !0;
			};
			let i = r.slice(), a = [e];
			for (let n = 0; n < i.length && !e._stopped; n++) {
				let e = i[n];
				e && V(e, t, 5, a);
			}
		} else V(r, t, 5, [e]);
	};
	return n.value = e, n.attached = Qa(), n;
}
var eo = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, to = (e, t, n, r, i, s) => {
	let c = i === "svg";
	t === "class" ? Oa(e, r, c) : t === "style" ? Na(e, n, r) : a(t) ? o(t) || Ka(e, t, n, r, s) : (t[0] === "." ? (t = t.slice(1), 1) : t[0] === "^" ? (t = t.slice(1), 0) : no(e, t, r, c)) ? (Ha(e, t, r), e.tagName.includes("-") || t !== "value" && t !== "checked" && t !== "selected" || Va(e, t, r, c, s, t !== "value")) : e._isVueCE && (ro(e, t) || e._def.__asyncLoader && (/[A-Z]/.test(t) || !g(r))) ? Ha(e, E(t), r, s, t) : (t === "true-value" ? e._trueValue = r : t === "false-value" && (e._falseValue = r), Va(e, t, r, c));
};
function no(e, t, n, r) {
	if (r) return !!(t === "innerHTML" || t === "textContent" || t in e && eo(t) && h(n));
	if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "autocorrect" || t === "sandbox" && e.tagName === "IFRAME" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA") return !1;
	if (t === "width" || t === "height") {
		let t = e.tagName;
		if (t === "IMG" || t === "VIDEO" || t === "CANVAS" || t === "SOURCE") return !1;
	}
	return eo(t) && g(n) ? !1 : t in e;
}
function ro(e, t) {
	let n = e._def.props;
	if (!n) return !1;
	let r = E(t);
	return Array.isArray(n) ? n.some((e) => E(e) === r) : Object.keys(n).some((e) => E(e) === r);
}
var io = [
	"ctrl",
	"shift",
	"alt",
	"meta"
], ao = {
	stop: (e) => e.stopPropagation(),
	prevent: (e) => e.preventDefault(),
	self: (e) => e.target !== e.currentTarget,
	ctrl: (e) => !e.ctrlKey,
	shift: (e) => !e.shiftKey,
	alt: (e) => !e.altKey,
	meta: (e) => !e.metaKey,
	left: (e) => "button" in e && e.button !== 0,
	middle: (e) => "button" in e && e.button !== 1,
	right: (e) => "button" in e && e.button !== 2,
	exact: (e, t) => io.some((n) => e[`${n}Key`] && !t.includes(n))
}, Q = (e, t) => {
	if (!e) return e;
	let n = e._withMods ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n, ...r) => {
		for (let e = 0; e < t.length; e++) {
			let r = ao[t[e]];
			if (r && r(n, t)) return;
		}
		return e(n, ...r);
	}));
}, oo = {
	esc: "escape",
	space: " ",
	up: "arrow-up",
	left: "arrow-left",
	right: "arrow-right",
	down: "arrow-down",
	delete: "backspace"
}, so = (e, t) => {
	let n = e._withKeys ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n) => {
		if (!("key" in n)) return;
		let r = O(n.key);
		if (t.some((e) => e === r || oo[e] === r)) return e(n);
	}));
}, co = /* @__PURE__ */ s({ patchProp: to }, Ea), lo;
function uo() {
	return lo ||= mi(co);
}
var fo = ((...e) => {
	let t = uo().createApp(...e), { mount: n } = t;
	return t.mount = (e) => {
		let r = mo(e);
		if (!r) return;
		let i = t._component;
		h(i) || i.render || i.template || (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
		let a = n(r, !1, po(r));
		return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), a;
	}, t;
});
function po(e) {
	if (e instanceof SVGElement) return "svg";
	if (typeof MathMLElement == "function" && e instanceof MathMLElement) return "mathml";
}
function mo(e) {
	return g(e) ? document.querySelector(e) : e;
}
// src/features/dashboard/useDashboard.ts
var ho = "gpt_console_overview_preferences_v1", go = ["metrics", "panels"], $ = (e) => Number(e || 0);
function _o(e) {
	let t = e?.statistics_updated_at, n = t ? `；统计于 ${new Date(t).toLocaleTimeString()} 更新` : "";
	return `仅统计本地库存；用完后请手动导入邮箱。邮箱由 Email Butler 等邮箱服务准备${e?.reason ? `；${e.reason}` : ""}${n}`;
}
function vo(e) {
	return e?.status === "error" ? "读取失败" : Number.isInteger(e?.available) && e.available >= 0 ? e.available : Array.isArray(e?.sources) ? e.sources.reduce((e, t) => e + $(t?.available), 0) : 0;
}
function yo(e, ...t) {
	let n = e;
	for (let e of t) {
		if (!n || typeof n != "object") return null;
		n = n[e];
	}
	return typeof n?.enabled == "boolean" ? n.enabled : null;
}
function bo(e, t) {
	let n = e?.email?.supply?.sources;
	return Array.isArray(n) ? n.filter((e) => e?.kind === "local_pool") : (Array.isArray(e?.email?.sources) ? e.email.sources : []).filter((e) => e?.enabled === !0 && (yo(t, "email_sources", e.source) ?? !0));
}
function xo(e, t) {
	return bo(e, t).filter((e) => e?.kind === "local_pool");
}
function So(e, t) {
	let n = String(e?.proxy?.platform || "none").trim().toLowerCase();
	return !n || n === "none" || n === "direct" ? !1 : yo(t, "proxy", "registration") ?? !0;
}
function Co(e, t) {
	let n = e?.jobs?.counts || {}, r = $(n.running) + $(n.pending) + $(n.stopping);
	return $(e?.jobs?.total) <= 0 && r <= 0 ? !1 : yo(t, "features", "register") ?? !0;
}
function wo(e) {
	let t = String(e || "").trim();
	return {
		"1024proxy": "1024Proxy",
		"711proxy": "711Proxy",
		manual: "手动代理池",
		1024: "1024Proxy",
		pool: "静态代理池",
		none: "直连",
		direct: "直连"
	}[t.toLowerCase()] || t || "未配置";
}
function To(e, t) {
	let n = e && typeof e == "object" ? e : {}, r = new Set(go.flatMap((e) => t[e] || [])), i = Array.isArray(n.hidden) ? Array.from(new Set(n.hidden.filter((e) => typeof e == "string" && r.has(e)))) : [], a = {};
	for (let e of go) {
		let r = t[e] || [], i = Array.isArray(n.order?.[e]) ? n.order[e].filter((e) => typeof e == "string") : [];
		a[e] = Array.from(/* @__PURE__ */ new Set([...i.filter((e) => r.includes(e)), ...r.filter((e) => !i.includes(e))]));
	}
	let o = {}, s = {};
	for (let e of r) {
		o[e] = [
			"normal",
			"wide",
			"full"
		].includes(n.sizes?.[e]) ? n.sizes[e] : "normal";
		let t = Number(n.heights?.[e]);
		Number.isFinite(t) && t >= 100 && t <= 800 && (s[e] = Math.round(t));
	}
	return {
		order: a,
		hidden: i,
		sizes: o,
		heights: s
	};
}
function Eo(e) {
	try {
		return To(JSON.parse(localStorage.getItem("gpt_console_overview_preferences_v1") || "{}"), e);
	} catch {
		return To({}, e);
	}
}
function Do(e) {
	try {
		localStorage.setItem(ho, JSON.stringify(e));
	} catch {}
}
var Oo = [
	{
		id: "metric-accounts",
		region: "metrics",
		label: "有效账号",
		available: (e) => $(e?.accounts?.total) > 0
	},
	{
		id: "metric-email",
		region: "metrics",
		label: "本地可用邮箱",
		available: (e, t) => bo(e, t).length > 0
	},
	{
		id: "metric-jobs",
		region: "metrics",
		label: "运行任务",
		available: (e, t) => Co(e, t)
	},
	{
		id: "metric-codex",
		region: "metrics",
		label: "Codex 凭证",
		available: (e) => $(e?.codex?.total) > 0
	},
	{
		id: "metric-proxy",
		region: "metrics",
		label: "活跃出口",
		available: (e, t) => So(e, t)
	},
	{
		id: "panel-email",
		region: "panels",
		label: "邮箱资源 · 本地库存",
		available: (e, t) => bo(e, t).length > 0
	},
	{
		id: "panel-proxy",
		region: "panels",
		label: "网络出口 · 代理与网络",
		available: (e, t) => So(e, t)
	},
	{
		id: "panel-jobs",
		region: "panels",
		label: "注册流水线 · 今日任务结果",
		available: (e, t) => Co(e, t)
	},
	{
		id: "panel-accounts",
		region: "panels",
		label: "账号资产 · 套餐分布",
		available: (e) => Object.keys(e?.accounts?.plans || {}).length > 0
	},
	{
		id: "panel-task-queue",
		region: "panels",
		label: "注册流水线 · 当前任务队列",
		available: (e, t) => Co(e, t) && [
			"pending",
			"running",
			"stopping"
		].some((t) => $(e?.jobs?.counts?.[t]) > 0)
	},
	{
		id: "panel-job-history",
		region: "panels",
		label: "注册流水线 · 累计任务结果",
		available: (e, t) => Co(e, t) && [
			"success",
			"partial_success",
			"failed",
			"stopped",
			"cancelled"
		].some((t) => $(e?.jobs?.counts?.[t]) > 0)
	},
	{
		id: "panel-email-health",
		region: "panels",
		label: "邮箱资源 · 邮箱池状态",
		available: (e, t) => xo(e, t).some((e) => $(e.total) > 0)
	},
	{
		id: "panel-codex-progress",
		region: "panels",
		label: "Codex 授权 · 凭证处理进度",
		available: (e) => $(e?.codex?.total) > 0
	}
];
function ko(e, t) {
	return Object.fromEntries(go.map((n) => [n, Oo.filter((r) => r.region === n && r.available(e, t)).map((e) => e.id)]));
}
function Ao(e) {
	return e ? e < 220 ? "minimal" : e < 300 ? "compact" : "normal" : "normal";
}
function jo(e, t) {
	return e > 0 ? `另有 ${e} ${t}` : "";
}
function Mo(e, t, n, r) {
	let i = t?.accounts || {}, a = t?.email || {}, o = t?.jobs || {}, s = t?.proxy || {}, c = t?.codex || {};
	if (e === "metric-accounts") return {
		value: $(i.active),
		hint: `归档 ${$(i.archived)}`,
		color: "#5b5ce2"
	};
	if (e === "metric-email") return {
		value: vo(a.supply),
		hint: _o(a.supply),
		color: "#2dbb8a"
	};
	if (e === "metric-jobs") {
		let e = o.counts || {};
		return {
			value: $(e.running) + $(e.pending) + $(e.stopping),
			hint: `累计任务 ${$(o.total)}`,
			color: "#e6a23c"
		};
	}
	if (e === "metric-codex") return {
		value: $(c.total),
		hint: `待导出 ${$(c.pending)}`,
		color: "#377dff"
	};
	if (e === "metric-proxy") return {
		value: $(s.active_leases),
		hint: `代理平台 ${wo(s.platform)}`,
		color: "#a855f7"
	};
	if (e === "panel-email") return {
		kind: "email",
		action: ["outlook", "管理邮箱"],
		sources: bo(t, n)
	};
	if (e === "panel-proxy") {
		let e = (s.leases || []).slice(0, 3), t = Math.max($(s.active_leases), (s.leases || []).length);
		return {
			kind: "proxy",
			action: ["config", "配置"],
			platform: wo(s.platform),
			active: $(s.active_leases),
			leases: e,
			more: jo(t - 1, "个出口")
		};
	}
	if (e === "panel-jobs") {
		let e = o.today_counts || {};
		return {
			kind: "today",
			action: ["register", "查看全部"],
			today: o.today || "今天",
			rows: [
				[
					"success",
					"成功",
					$(e.success)
				],
				[
					"partial_success",
					"部分成功",
					$(e.partial_success)
				],
				[
					"failed",
					"失败",
					$(e.failed)
				]
			]
		};
	}
	if (e === "panel-accounts") return {
		kind: "plans",
		action: ["accounts", "管理账号"],
		plans: Object.entries(i.plans || {}).sort((e, t) => $(t[1]) - $(e[1]))
	};
	if (e === "panel-task-queue") {
		let e = o.counts || {};
		return {
			kind: "queue",
			action: ["register", "查看任务"],
			rows: [
				["待处理", $(e.pending)],
				["运行中", $(e.running)],
				["停止中", $(e.stopping)]
			]
		};
	}
	if (e === "panel-job-history") {
		let e = o.counts || {};
		return {
			kind: "history",
			action: ["register", "查看任务"],
			rows: [
				["成功", $(e.success)],
				["失败", $(e.failed)],
				["部分成功", $(e.partial_success)],
				["已停止或取消", $(e.stopped) + $(e.cancelled)]
			]
		};
	}
	if (e === "panel-email-health") {
		let e = xo(t, n), r = (t) => e.reduce((e, n) => e + $(n[t]), 0);
		return {
			kind: "health",
			action: ["outlook", "查看邮箱"],
			rows: [
				["可用邮箱", r("available")],
				["已用邮箱", r("used")],
				["失败邮箱", r("failed")],
				["停用邮箱", r("disabled")]
			]
		};
	}
	return {
		kind: "codex",
		action: ["codex", "查看凭证"],
		rows: [
			["已导出", $(c.exported)],
			["待导出", $(c.pending)],
			["账号 Codex 就绪", $(i.codex_ready)]
		]
	};
}
function No(e, t = {}) {
	let n = /* @__PURE__ */ Ht(null), r = /* @__PURE__ */ Ht({}), i = /* @__PURE__ */ Ht(!1), a = /* @__PURE__ */ Ht(""), o = /* @__PURE__ */ Ht(!!t.visible), s = /* @__PURE__ */ Ht(!1), c = /* @__PURE__ */ Ht(0), l, u, d, f = !1, p = /* @__PURE__ */ Nt({
		order: {
			metrics: [],
			panels: []
		},
		hidden: [],
		sizes: {},
		heights: {}
	});
	function m() {
		if (!n.value) return;
		let e = Eo(ko(n.value, r.value));
		p.order = e.order, p.hidden = e.hidden, p.sizes = e.sizes, p.heights = e.heights;
	}
	let h = _a(() => n.value ? ko(n.value, r.value) : {
		metrics: [],
		panels: []
	}), g = _a(() => go.flatMap((e) => (p.order[e] || []).filter((e) => !p.hidden.includes(e)).map((e) => Oo.find((t) => t.id === e)).filter((e) => e && e.available(n.value, r.value)).map((e) => ({
		card: e,
		payload: Mo(e.id, n.value, r.value, p),
		size: p.sizes[e.id] || "normal",
		height: p.heights[e.id],
		density: Ao(p.heights[e.id])
	}))));
	function _() {
		Do(To(p, h.value));
	}
	function v(e) {
		e(p);
		let t = To(p, h.value);
		p.order = t.order, p.hidden = t.hidden, p.sizes = t.sizes, p.heights = t.heights, _();
	}
	function y(e, t, n) {
		v((r) => {
			let i = r.order[e] || [], a = i.indexOf(t), o = n === "up" ? a - 1 : a + 1;
			a < 0 || o < 0 || o >= i.length || ([i[a], i[o]] = [i[o], i[a]]);
		});
	}
	function b(e, t) {
		v((n) => {
			n.hidden = n.hidden.filter((t) => t !== e), t || n.hidden.push(e);
		});
	}
	function x(e, t, n, r = !1) {
		h.value[e].includes(t) && h.value[e].includes(n) && v((i) => {
			let a = i.order[e] || [], o = a.indexOf(t);
			if (o < 0 || t === n) return;
			a.splice(o, 1);
			let s = a.indexOf(n);
			a.splice(s + +!!r, 0, t);
		});
	}
	function S(e, t, n) {
		v((r) => {
			if (t === "width") {
				let t = [
					"normal",
					"wide",
					"full"
				], i = Math.max(0, Math.min(2, t.indexOf(r.sizes[e] || "normal") + n));
				r.sizes[e] = t[i];
			} else r.heights[e] = Math.max(160, Math.min(800, (r.heights[e] || 220) + n));
		});
	}
	function C() {
		try {
			localStorage.removeItem(ho);
		} catch {}
		n.value && m(), t.notify?.("已恢复默认布局");
	}
	function w() {
		if (f || !o.value || document.hidden) return Promise.resolve();
		if (d) return d;
		let s = ++c.value;
		u?.abort(), u = new AbortController(), i.value = !0, a.value = "";
		let l = (async () => {
			try {
				let [i, a] = await Promise.all([e.dashboard(u.signal), e.capabilities(u.signal).catch(() => null)]);
				if (s !== c.value || !o.value || document.hidden) return;
				n.value = i, a !== null && (r.value = a || {}, t.onCapabilities?.(r.value)), m(), t.onReady?.();
			} catch (e) {
				s === c.value && !String(e?.name || "").includes("Abort") && (a.value = e?.message || "总览加载失败", t.notify?.(`总览加载失败：${a.value}`));
			} finally {
				s === c.value && (i.value = !1, d = void 0);
			}
		})();
		return d = l, l;
	}
	function T() {
		l && window.clearInterval(l), l = window.setInterval(() => void w(), 15e3);
	}
	function ee(e) {
		f || o.value === !!e || (o.value = !!e, c.value++, u?.abort(), d = void 0, o.value ? (T(), w()) : (l && window.clearInterval(l), l = void 0, i.value = !1, s.value = !1));
	}
	function te(e) {
		s.value = e;
	}
	let E = () => {
		!document.hidden && o.value ? w() : (c.value++, u?.abort(), d = void 0, i.value = !1, s.value = !1);
	};
	return rr(() => {
		document.addEventListener("visibilitychange", E), o.value && (T(), w());
	}), or(() => {
		f = !0, o.value = !1, c.value++, d = void 0, i.value = !1, s.value = !1, document.removeEventListener("visibilitychange", E), u?.abort(), l && window.clearInterval(l), l = void 0;
	}), jn(() => t.visible, (e) => ee(!!e)), {
		data: n,
		caps: r,
		loading: i,
		error: a,
		visible: o,
		customizerOpen: s,
		cards: g,
		ids: h,
		prefs: p,
		mutate: v,
		load: w,
		setVisible: ee,
		openCustomizer: () => te(!0),
		closeCustomizer: () => te(!1),
		resetLayout: C,
		toggle: b,
		move: y,
		reorder: x,
		resize: S,
		cardPayload: Mo
	};
}
// src/shared/useNativeDialog.ts
var Po = /* @__PURE__ */ new Set(), Fo, Io, Lo = !1;
function Ro() {
	let e = Fo;
	if (!e || !Po.size) return;
	let t = document.body, n = document.documentElement, r = t.classList.contains("modal-open");
	if (Lo && !r && e.external && (e.external = !1, e.top = t.style.getPropertyValue("top"), e.topPriority = t.style.getPropertyPriority("top"), e.rootOverflow = n.style.getPropertyValue("overflow"), e.rootPriority = n.style.getPropertyPriority("overflow")), Lo = r, !r) {
		let r = `-${e.scrollY}px`;
		t.style.top !== r && t.style.setProperty("top", r), n.style.overflow !== "hidden" && n.style.setProperty("overflow", "hidden");
	}
	t.style.overflow !== "hidden" && t.style.setProperty("overflow", "hidden"), t.classList.contains("em-native-dialog-lock") || t.classList.add("em-native-dialog-lock");
}
function zo(e) {
	if (!Po.has(e)) {
		if (!Po.size) {
			let e = document.body, t = document.documentElement, n = e.classList.contains("modal-open"), r = n && /^-\d+(?:\.\d+)?px$/.test(e.style.top) ? -parseFloat(e.style.top) : null;
			Fo = {
				top: e.style.getPropertyValue("top"),
				topPriority: e.style.getPropertyPriority("top"),
				bodyOverflow: e.style.getPropertyValue("overflow"),
				bodyPriority: e.style.getPropertyPriority("overflow"),
				rootOverflow: t.style.getPropertyValue("overflow"),
				rootPriority: t.style.getPropertyPriority("overflow"),
				scrollY: r ?? (window.scrollY || t.scrollTop || 0),
				external: n,
				classExisted: e.classList.contains("em-native-dialog-lock")
			}, n || e.style.setProperty("top", `-${Fo.scrollY}px`), e.classList.add("em-native-dialog-lock"), e.style.setProperty("overflow", "hidden"), t.style.setProperty("overflow", "hidden"), Lo = n, Io = new MutationObserver(Ro), Io.observe(e, {
				attributes: !0,
				attributeFilter: ["class", "style"]
			}), Io.observe(t, {
				attributes: !0,
				attributeFilter: ["style"]
			});
		}
		Po.add(e);
	}
}
function Bo(e) {
	if (Po.has(e) && Ro(), !Po.delete(e) || Po.size || !Fo) return;
	Io?.disconnect(), Io = void 0;
	let t = Fo;
	Fo = void 0;
	let n = document.body, r = document.documentElement, i = n.classList.contains("modal-open");
	t.classExisted || n.classList.remove("em-native-dialog-lock"), n.style.setProperty("overflow", t.bodyOverflow, t.bodyPriority), (!i || t.external) && (n.style.setProperty("top", t.top, t.topPriority), r.style.setProperty("overflow", t.rootOverflow, t.rootPriority), !i && !t.external && window.scrollTo(0, t.scrollY));
}
function Vo(e) {
	if (!e.isConnected || e.closest("[hidden],.hidden,[inert]")) return !1;
	for (let t = e; t; t = t.parentElement) {
		let e = getComputedStyle(t);
		if (e.display === "none" || e.visibility === "hidden") return !1;
	}
	return !0;
}
function Ho(e, t, n = () => !0) {
	let r = null, i = !1, a;
	async function o() {
		let o = e.value;
		o && !i && (t() && !o.open ? (r = document.activeElement instanceof HTMLElement ? document.activeElement : null, o.showModal(), a = o, zo(o), await dn(), !i && o.open && o.querySelector("button,input,select,textarea")?.focus()) : t() || (o.open && o.close(), Bo(o), r && n() && !document.hidden && Vo(r) && r.focus()));
	}
	jn(t, () => void o(), { flush: "post" }), rr(() => void o()), or(() => {
		i = !0, a?.close(), a && Bo(a);
	});
}
// src/features/dashboard/DashboardPage.vue?vue&type=script&setup=true&lang.ts
var Uo = {
	class: "dashboard-vue-root",
	"data-dashboard-vue": ""
}, Wo = {
	class: "overview-hero",
	"aria-label": "平台状态总览"
}, Go = { class: "overview-hero-actions" }, Ko = ["aria-expanded"], qo = ["disabled"], Jo = {
	key: 0,
	class: "list-result list-result--danger",
	role: "alert"
}, Yo = ["aria-hidden"], Xo = { class: "overview-customizer-list" }, Zo = { class: "overview-customizer-group-head" }, Qo = { class: "overview-customizer-items" }, $o = [
	"data-dashboard-custom-card",
	"onDragstart",
	"onDrop"
], es = ["checked", "onChange"], ts = ["aria-label"], ns = ["onClick"], rs = ["onClick"], is = { class: "overview-customizer-foot" }, as = { class: "overview-metrics" }, os = [
	"data-dashboard-card",
	"data-overview-card",
	"data-overview-size",
	"onDrop"
], ss = { class: "overview-metric-top" }, cs = { class: "overview-card-tools" }, ls = [
	"aria-label",
	"onKeydown",
	"onPointerdown"
], us = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], ds = { class: "overview-grid" }, fs = [
	"data-dashboard-card",
	"data-overview-card",
	"data-overview-size",
	"data-overview-density",
	"onDrop"
], ps = { class: "overview-panel-head" }, ms = { class: "overview-card-tools" }, hs = ["onClick"], gs = [
	"aria-label",
	"onKeydown",
	"onPointerdown"
], _s = {
	key: 0,
	class: "overview-source-grid"
}, vs = { class: "overview-source-top" }, ys = ["title"], bs = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact overview-more-summary--paired"
}, xs = {
	key: 1,
	class: "overview-more-summary overview-more-summary--minimal"
}, Ss = { key: 1 }, Cs = { class: "overview-proxy-grid" }, ws = { class: "overview-proxy-item" }, Ts = { class: "overview-proxy-item" }, Es = { class: "overview-exit-list" }, Ds = {
	key: 0,
	class: "muted"
}, Os = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact"
}, ks = {
	key: 2,
	class: "overview-plan-list"
}, As = { class: "overview-plan-bar" }, js = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact overview-more-summary--paired"
}, Ms = {
	key: 1,
	class: "overview-more-summary overview-more-summary--minimal"
}, Ns = {
	key: 3,
	class: "overview-job-list"
}, Ps = { class: "overview-job-main" }, Fs = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact"
}, Is = {
	key: 4,
	class: "overview-status-grid"
}, Ls = {
	key: 0,
	class: "overview-more-summary overview-more-summary--compact"
}, Rs = {
	key: 1,
	class: "overview-more-summary overview-more-summary--compact"
}, zs = {
	key: 2,
	class: "overview-more-summary overview-more-summary--compact"
}, Bs = {
	key: 3,
	class: "overview-more-summary overview-more-summary--compact"
}, Vs = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], Hs = /*#__PURE__*/ ((e, t) => {
	let n = e.__vccOpts || e;
	for (let [e, r] of t) n[e] = r;
	return n;
})(/* @__PURE__ */ Hn({
	__name: "DashboardPage",
	props: {
		api: {},
		deps: {}
	},
	setup(e, { expose: t }) {
		let n = e, r = No(n.api, n.deps), { cards: i, ids: a, prefs: o, customizerOpen: s, loading: c, error: l } = r, u = /* @__PURE__ */ Ht(), d = /* @__PURE__ */ Ht();
		Ho(d, () => s.value, () => r.visible.value);
		let f = (e) => Oo.find((t) => t.id === e)?.label || e, p = /* @__PURE__ */ Ht(null);
		function m(e, t) {
			let n = e?.[t];
			return Number.isInteger(n) && n >= 0 ? String(n) : e?.status === "error" ? "读取失败" : "未知";
		}
		function h(e) {
			return {
				free: "Free",
				free_trial_eligible: "Free · Plus 免费试用",
				free_half_price_eligible: "Free · Plus 半价",
				free_discount_eligible: "Free · Plus 其他折扣",
				free_promo_unknown: "Free · 优惠待复查",
				plus: "Plus",
				pro: "Pro",
				team: "Team",
				go: "Go",
				unknown: "未检测"
			}[e] || e;
		}
		function g(e) {
			return {
				success: "成功",
				partial_success: "部分成功",
				failed: "失败"
			}[e] || e;
		}
		let _ = (e) => e?.sources || [], v = (e) => e?.leases || [], y = (e) => e?.plans || [], b = (e) => e?.rows || [];
		function x() {
			r.closeCustomizer();
		}
		function S(e) {
			let t = d.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && x();
		}
		function C(e) {
			e.key === "Escape" && (O(), s.value && x());
		}
		rr(() => document.addEventListener("keydown", C)), or(() => document.removeEventListener("keydown", C));
		function w(e) {
			e && (e[0] === "config" ? n.deps.onConfig?.("代理与网络") : n.deps.onNavigate?.(e[0]));
		}
		function T(e) {
			return r.ids.value.metrics.includes(e) ? "metrics" : "panels";
		}
		function ee(e) {
			p.value = e;
		}
		function te(e) {
			p.value &&= (r.reorder(T(e), p.value, e), null);
		}
		function E(e, t) {
			if (![
				"ArrowLeft",
				"ArrowUp",
				"ArrowRight",
				"ArrowDown"
			].includes(t.key)) return;
			t.preventDefault(), r.move(T(e), e, ["ArrowLeft", "ArrowUp"].includes(t.key) ? "up" : "down");
			let n = t.currentTarget;
			dn(() => n.focus({ preventScroll: !0 }));
		}
		let D;
		function O(e = !0) {
			D?.(e);
		}
		function ne(e, t) {
			if (t.button !== 0 || D) return;
			let n = t.currentTarget, i = n.closest("[data-dashboard-card]"), a = i?.parentElement;
			if (!i || !a) return;
			let o = T(e), s = [...r.prefs.order[o]], c = t.clientX, l = t.clientY, u = i.getBoundingClientRect(), d, f, p = c, m = l;
			n.setPointerCapture?.(t.pointerId);
			let h = () => {
				let t = document.elementFromPoint?.(p, m)?.closest("[data-dashboard-card]");
				if (!t || t === i || t.parentElement !== a) return;
				let n = t.getBoundingClientRect(), s = i.getBoundingClientRect(), c = getComputedStyle(a).gridTemplateColumns.trim().split(/\s+/).length === 1 || Math.abs(s.top - n.top) > 8 || t.dataset.overviewSize === "full" ? m >= n.top + n.height / 2 : p >= n.left + n.width / 2, l = new Map(Array.from(a.children).map((e) => [e, e.getBoundingClientRect()]));
				r.reorder(o, e, t.dataset.dashboardCard, c), dn(() => {
					if (!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) for (let [e, t] of l) {
						if (e === i) continue;
						let n = e.getBoundingClientRect(), r = t.left - n.left, a = t.top - n.top;
						(r || a) && e.animate?.([{ transform: `translate(${r}px,${a}px)` }, { transform: "translate(0,0)" }], {
							duration: 180,
							easing: "cubic-bezier(.2,.75,.2,1)"
						});
					}
				});
			}, g = () => {
				if (f = void 0, !d) return;
				let e = m, t = e >= 0 && e < 64 ? -Math.ceil((64 - e) / 4) : e <= window.innerHeight && e > window.innerHeight - 64 ? Math.ceil((e - window.innerHeight + 64) / 4) : 0;
				if (!t) return;
				let n = document.scrollingElement?.scrollTop;
				window.scrollBy(0, t), document.scrollingElement?.scrollTop !== n && (h(), f = requestAnimationFrame(g));
			}, _ = (e) => {
				if (e.pointerId !== t.pointerId) return;
				p = e.clientX, m = e.clientY;
				let n = p - c, r = m - l;
				!d && Math.hypot(n, r) < 5 || (d || (d = i.cloneNode(!0), d.classList.add("overview-drag-ghost"), d.setAttribute("aria-hidden", "true"), Object.assign(d.style, {
					left: `${u.left}px`,
					top: `${u.top}px`,
					width: `${u.width}px`,
					height: `${u.height}px`
				}), document.body.append(d), i.classList.add("is-drag-placeholder")), d.style.transform = `translate3d(${n}px,${r}px,0)`, h(), f ||= requestAnimationFrame(g));
			}, v = (e) => {
				e.pointerId === t.pointerId && O(e.type === "pointercancel");
			};
			D = (e = !1) => {
				D = void 0, window.removeEventListener("pointermove", _), window.removeEventListener("pointerup", v), window.removeEventListener("pointercancel", v), f && cancelAnimationFrame(f), n.hasPointerCapture?.(t.pointerId) && n.releasePointerCapture(t.pointerId), d?.remove(), i.classList.remove("is-drag-placeholder"), e && r.mutate((e) => {
					e.order[o] = s;
				});
			}, window.addEventListener("pointermove", _), window.addEventListener("pointerup", v), window.addEventListener("pointercancel", v), t.preventDefault();
		}
		function re(e, t) {
			if (t.button !== 0 || D) return;
			let n = t.currentTarget, i = n.closest("[data-dashboard-card]"), a = i?.parentElement;
			if (!i || !a) return;
			let o = getComputedStyle(a), s = Math.max(1, o.gridTemplateColumns.trim().split(/\s+/).length), c = parseFloat(o.columnGap) || 0, l = i.getBoundingClientRect(), u = (a.getBoundingClientRect().width - c * (s - 1)) / s, d = T(e), f = r.prefs.sizes[e] || "normal", p = i.style.minHeight, m = f, h = r.prefs.heights[e], g = !1;
			n.setPointerCapture?.(t.pointerId), i.classList.add("is-resizing");
			let _ = (e) => {
				if (e.pointerId !== t.pointerId) return;
				let n = e.clientX - t.clientX, r = e.clientY - t.clientY;
				if (Math.abs(n) > 4 && u > 0) {
					let e = Math.max(1, Math.min(s, Math.round((l.width + n + c) / (u + c))));
					m = e <= 1 ? "normal" : e >= Math.min(s, d === "metrics" ? 4 : 3) && s >= 3 ? "full" : "wide", i.dataset.overviewSize = m, g = !0;
				}
				Math.abs(r) > 4 && (h = Math.max(160, Math.min(800, Math.round(l.height + r))), i.style.minHeight = `${h}px`, d === "panels" && (i.dataset.overviewDensity = h < 220 ? "minimal" : h < 300 ? "compact" : "normal"), g = !0);
			}, v = (e) => {
				e.pointerId === t.pointerId && O(e.type === "pointercancel");
			};
			D = (a = !1) => {
				if (D = void 0, window.removeEventListener("pointermove", _), window.removeEventListener("pointerup", v), window.removeEventListener("pointercancel", v), i.classList.remove("is-resizing"), n.hasPointerCapture?.(t.pointerId) && n.releasePointerCapture(t.pointerId), !a && g) r.mutate((t) => {
					t.sizes[e] = m, h !== void 0 && (t.heights[e] = h);
				});
				else {
					i.dataset.overviewSize = f, i.style.minHeight = p;
					let t = r.prefs.heights[e];
					d === "panels" && (i.dataset.overviewDensity = t ? t < 220 ? "minimal" : t < 300 ? "compact" : "normal" : "normal");
				}
			}, window.addEventListener("pointermove", _), window.addEventListener("pointerup", v), window.addEventListener("pointercancel", v), t.preventDefault();
		}
		return jn(r.visible, (e) => {
			e || O();
		}), jn(r.data, () => O()), or(() => O()), t({
			load: r.load,
			setVisible: r.setVisible,
			openCustomizer: r.openCustomizer,
			closeCustomizer: r.closeCustomizer,
			resetLayout: r.resetLayout
		}), (e, t) => (q(), J("div", Uo, [
			Y("section", Wo, [t[9] ||= Y("div", null, [
				Y("div", { class: "data-panel-kicker" }, "Operations overview"),
				Y("h2", null, "整个平台，一屏看清"),
				Y("p", null, "拖动卡片标题旁的把手调整位置，拖动右下角调整大小；显示内容可按需设置。")
			], -1), Y("div", Go, [Y("button", {
				ref_key: "customizeButton",
				ref: u,
				type: "button",
				class: "overview-customize-trigger",
				"data-dashboard-open-customizer": "",
				"aria-expanded": B(s),
				onClick: t[0] ||= (...e) => B(r).openCustomizer && B(r).openCustomizer(...e)
			}, "自定义总览", 8, Ko), Y("button", {
				type: "button",
				class: "overview-refresh",
				disabled: B(c),
				onClick: t[1] ||= (...e) => B(r).load && B(r).load(...e)
			}, "刷新数据", 8, qo)])]),
			B(l) ? (q(), J("div", Jo, [
				t[10] ||= Y("strong", null, "总览加载失败", -1),
				Y("span", null, M(B(l)), 1),
				Y("button", {
					type: "button",
					onClick: t[2] ||= (...e) => B(r).load && B(r).load(...e)
				}, "重试")
			])) : X("", !0),
			Y("dialog", {
				ref_key: "customizer",
				ref: d,
				class: "overview-customizer",
				role: "dialog",
				"aria-modal": "true",
				"aria-labelledby": "dashboard-customizer-title",
				"aria-hidden": !B(s),
				onCancel: Q(x, ["prevent"]),
				onClick: S
			}, [
				Y("div", { class: "overview-customizer-head" }, [t[11] ||= Y("div", null, [
					Y("div", { class: "data-panel-kicker" }, "Customize overview"),
					Y("h3", { id: "dashboard-customizer-title" }, "显示与排序"),
					Y("p", null, "拖动卡片排序，也可以用上移/下移调整。未启用或未配置的功能不会出现在这里。")
				], -1), Y("button", {
					type: "button",
					class: "overview-customizer-close",
					"data-dashboard-close-customizer": "",
					onClick: x
				}, "关闭")]),
				Y("div", Xo, [(q(), J(G, null, pr(["metrics", "panels"], (e) => Y("section", {
					key: e,
					class: "overview-customizer-group"
				}, [Y("div", Zo, [Y("strong", null, M(e === "metrics" ? "指标卡片" : "详细卡片"), 1), Y("small", null, M((B(a)[e] || []).length) + " 张可用卡片", 1)]), Y("div", Qo, [(q(!0), J(G, null, pr(B(o).order[e] || [], (n) => (q(), J("div", {
					key: n,
					class: "overview-customizer-item",
					draggable: "true",
					"data-dashboard-custom-card": n,
					onDragstart: (e) => ee(n),
					onDragover: t[3] ||= Q(() => {}, ["prevent"]),
					onDrop: (e) => te(n)
				}, [
					t[12] ||= Y("span", {
						class: "overview-drag-handle",
						"aria-hidden": "true"
					}, "拖动", -1),
					Y("label", null, [Y("input", {
						type: "checkbox",
						checked: !B(o).hidden.includes(n),
						onChange: (e) => B(r).toggle(n, e.target.checked)
					}, null, 40, es), Y("span", null, M(f(n)), 1)]),
					Y("div", {
						class: "overview-customizer-move",
						role: "group",
						"aria-label": `调整 ${n} 顺序`
					}, [Y("button", {
						type: "button",
						onClick: (t) => B(r).move(e, n, "up")
					}, "上移", 8, ns), Y("button", {
						type: "button",
						onClick: (t) => B(r).move(e, n, "down")
					}, "下移", 8, rs)], 8, ts)
				], 40, $o))), 128))])])), 64))]),
				Y("div", is, [Y("button", {
					type: "button",
					class: "overview-reset-layout",
					"data-dashboard-reset-layout": "",
					onClick: t[4] ||= (...e) => B(r).resetLayout && B(r).resetLayout(...e)
				}, "恢复默认布局")])
			], 40, Yo),
			Y("div", as, [(q(!0), J(G, null, pr(B(i).filter((e) => e.card.region === "metrics"), (e) => (q(), J("article", {
				key: e.card.id,
				class: "overview-metric",
				"data-dashboard-card": e.card.id,
				"data-overview-card": e.card.id,
				"data-overview-size": e.size,
				style: ce({
					"--metric-color": e.payload.color,
					minHeight: e.height ? `${e.height}px` : void 0
				}),
				onDragstart: t[5] ||= Q(() => {}, ["prevent"]),
				onDragover: t[6] ||= Q(() => {}, ["prevent"]),
				onDrop: (t) => te(e.card.id)
			}, [
				Y("div", ss, [Y("span", null, M(e.card.label), 1), Y("div", cs, [t[14] ||= Y("i", {
					class: "overview-metric-dot",
					"aria-hidden": "true"
				}, null, -1), Y("span", {
					class: "overview-card-drag",
					role: "button",
					tabindex: "0",
					"aria-label": `拖动${e.card.label}卡片排序，或使用方向键调整顺序`,
					onKeydown: (t) => E(e.card.id, t),
					onPointerdown: (t) => ne(e.card.id, t)
				}, [...t[13] ||= [Gi("<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" data-v-56b51968><circle cx=\"5\" cy=\"3\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"3\" r=\"1\" data-v-56b51968></circle><circle cx=\"5\" cy=\"8\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"8\" r=\"1\" data-v-56b51968></circle><circle cx=\"5\" cy=\"13\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"13\" r=\"1\" data-v-56b51968></circle></svg>", 1)]], 40, ls)])]),
				Y("strong", null, M(e.payload.value), 1),
				Y("small", null, M(e.payload.hint), 1),
				Y("button", {
					type: "button",
					class: "overview-resize-handle",
					"data-overview-resize": "",
					"aria-label": `拖动调整${e.card.label}卡片宽高；方向键可调整`,
					onPointerdown: (t) => re(e.card.id, t),
					onKeydown: [
						so(Q((t) => B(r).resize(e.card.id, "width", -1), ["prevent"]), ["left"]),
						so(Q((t) => B(r).resize(e.card.id, "width", 1), ["prevent"]), ["right"]),
						so(Q((t) => B(r).resize(e.card.id, "height", -40), ["prevent"]), ["up"]),
						so(Q((t) => B(r).resize(e.card.id, "height", 40), ["prevent"]), ["down"])
					]
				}, [...t[15] ||= [Y("svg", {
					viewBox: "0 0 16 16",
					"aria-hidden": "true"
				}, [Y("path", { d: "M6 14l8-8M10 14l4-4" })], -1)]], 40, us)
			], 44, os))), 128))]),
			Y("div", ds, [(q(!0), J(G, null, pr(B(i).filter((e) => e.card.region === "panels"), (e) => (q(), J("section", {
				key: e.card.id,
				class: "overview-panel",
				"data-dashboard-card": e.card.id,
				"data-overview-card": e.card.id,
				"data-overview-size": e.size,
				"data-overview-density": e.density,
				style: ce(e.height ? { minHeight: `${e.height}px` } : void 0),
				onDragstart: t[7] ||= Q(() => {}, ["prevent"]),
				onDragover: t[8] ||= Q(() => {}, ["prevent"]),
				onDrop: (t) => te(e.card.id)
			}, [
				Y("div", ps, [Y("div", null, [Y("span", null, M(e.card.label.split(" · ")[0]), 1), Y("h3", null, M(e.card.label.split(" · ").slice(1).join(" · ")), 1)]), Y("div", ms, [e.payload.action ? (q(), J("button", {
					key: 0,
					type: "button",
					onClick: (t) => w(e.payload.action)
				}, M(e.payload.action[1]), 9, hs)) : X("", !0), Y("span", {
					class: "overview-card-drag",
					role: "button",
					tabindex: "0",
					"aria-label": `拖动${e.card.label}卡片排序，或使用方向键调整顺序`,
					onKeydown: (t) => E(e.card.id, t),
					onPointerdown: (t) => ne(e.card.id, t)
				}, [...t[16] ||= [Gi("<svg viewBox=\"0 0 16 16\" aria-hidden=\"true\" data-v-56b51968><circle cx=\"5\" cy=\"3\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"3\" r=\"1\" data-v-56b51968></circle><circle cx=\"5\" cy=\"8\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"8\" r=\"1\" data-v-56b51968></circle><circle cx=\"5\" cy=\"13\" r=\"1\" data-v-56b51968></circle><circle cx=\"11\" cy=\"13\" r=\"1\" data-v-56b51968></circle></svg>", 1)]], 40, gs)])]),
				e.payload.kind === "email" ? (q(), J("div", _s, [
					(q(!0), J(G, null, pr(_(e.payload), (e, n) => (q(), J("article", {
						key: e.source,
						class: j(["overview-source", {
							"overview-density-secondary": Number(n) >= 2,
							"overview-density-minimal-extra": Number(n) >= 1
						}])
					}, [
						Y("div", vs, [Y("span", {
							class: "overview-source-name",
							title: e.label
						}, M(e.label), 9, ys), t[17] ||= Y("i", {
							class: "overview-source-state is-on",
							"aria-hidden": "true"
						}, null, -1)]),
						Y("strong", null, M(m(e, "available")), 1),
						Y("small", null, "本地总数 " + M(m(e, "total")) + " · 已用 " + M(m(e, "used")) + " · 失败 " + M(m(e, "failed")), 1)
					], 2))), 128)),
					_(e.payload).length > 2 ? (q(), J("div", bs, "另有 " + M(_(e.payload).length - 2) + " 个来源，进入详情查看", 1)) : X("", !0),
					_(e.payload).length > 1 ? (q(), J("div", xs, "另有 " + M(_(e.payload).length - 1) + " 个来源，进入详情查看", 1)) : X("", !0)
				])) : e.payload.kind === "proxy" ? (q(), J("div", Ss, [
					Y("div", Cs, [Y("div", ws, [t[18] ||= Y("span", null, "系统代理平台", -1), Y("strong", null, M(e.payload.platform), 1)]), Y("div", Ts, [t[19] ||= Y("span", null, "活跃出口", -1), Y("strong", null, M(e.payload.active) + " 个", 1)])]),
					Y("div", Es, [(q(!0), J(G, null, pr(v(e.payload), (e, n) => (q(), J("div", {
						key: n,
						class: j(["overview-exit-row", { "overview-density-secondary": Number(n) >= 1 }])
					}, [
						t[20] ||= Y("i", { "aria-hidden": "true" }, null, -1),
						Y("span", null, M(e.endpoint || e.exit_ip || "活跃出口"), 1),
						Y("small", null, M(e.region || e.provider || ""), 1)
					], 2))), 128)), v(e.payload).length ? X("", !0) : (q(), J("div", Ds, "当前没有活跃代理出口"))]),
					e.payload.more ? (q(), J("div", Os, M(e.payload.more), 1)) : X("", !0)
				])) : e.payload.kind === "plans" ? (q(), J("div", ks, [
					(q(!0), J(G, null, pr(y(e.payload), ([t, n], r) => (q(), J("div", {
						key: t,
						class: j(["overview-plan-row", {
							"overview-density-secondary": Number(r) >= 3,
							"overview-density-minimal-extra": Number(r) >= 2
						}])
					}, [
						Y("span", null, M(h(t)), 1),
						Y("div", As, [Y("i", { style: ce({ width: `${Math.max(4, Math.round(Number(n) / Math.max(1, ...y(e.payload).map((e) => Number(e[1]))) * 100))}%` }) }, null, 4)]),
						Y("strong", null, M(n), 1)
					], 2))), 128)),
					y(e.payload).length > 3 ? (q(), J("div", js, "另有 " + M(y(e.payload).length - 3) + " 种套餐，进入详情查看", 1)) : X("", !0),
					y(e.payload).length > 2 ? (q(), J("div", Ms, "另有 " + M(y(e.payload).length - 2) + " 种套餐，进入详情查看", 1)) : X("", !0)
				])) : e.payload.kind === "today" ? (q(), J("div", Ns, [(q(!0), J(G, null, pr(b(e.payload), ([t, n, r], i) => (q(), J("div", {
					key: t,
					class: j(["overview-job-row", { "overview-density-secondary": t === "partial_success" || Number(i) > 0 && !r }])
				}, [Y("span", { class: j(["pill", `status-${t}`]) }, M(g(t)), 3), Y("div", Ps, [Y("strong", null, M(r) + " 个任务", 1), Y("small", null, M(e.payload.today) + " · " + M(n), 1)])], 2))), 128)), b(e.payload)[1]?.[2] ? (q(), J("div", Fs, "部分成功 " + M(b(e.payload)[1]?.[2]), 1)) : X("", !0)])) : e.payload.kind === "queue" || e.payload.kind === "history" || e.payload.kind === "health" || e.payload.kind === "codex" ? (q(), J("div", Is, [
					(q(!0), J(G, null, pr(b(e.payload), ([t, n], r) => (q(), J("div", {
						key: t,
						class: j(["overview-status-item", { "overview-density-secondary": e.payload.kind === "health" ? [1, 3].includes(Number(r)) : Number(r) > 1 }])
					}, [Y("span", null, M(t), 1), Y("strong", null, M(n), 1)], 2))), 128)),
					e.payload.kind === "queue" && b(e.payload)[2]?.[1] ? (q(), J("div", Ls, "停止中 " + M(b(e.payload)[2]?.[1]), 1)) : X("", !0),
					e.payload.kind === "history" && (b(e.payload)[2]?.[1] || b(e.payload)[3]?.[1]) ? (q(), J("div", Rs, "部分成功 " + M(b(e.payload)[2]?.[1] || 0) + " · 已停止或取消 " + M(b(e.payload)[3]?.[1] || 0), 1)) : X("", !0),
					e.payload.kind === "health" ? (q(), J("div", zs, "已用 " + M(b(e.payload)[1]?.[1] || 0) + " · 停用 " + M(b(e.payload)[3]?.[1] || 0), 1)) : X("", !0),
					e.payload.kind === "codex" ? (q(), J("div", Bs, "账号 Codex 就绪 " + M(b(e.payload)[2]?.[1] || 0), 1)) : X("", !0)
				])) : X("", !0),
				Y("button", {
					type: "button",
					class: "overview-resize-handle",
					"data-overview-resize": "",
					"aria-label": `拖动调整${e.card.label}卡片宽高；方向键可调整`,
					onPointerdown: (t) => re(e.card.id, t),
					onKeydown: [
						so(Q((t) => B(r).resize(e.card.id, "width", -1), ["prevent"]), ["left"]),
						so(Q((t) => B(r).resize(e.card.id, "width", 1), ["prevent"]), ["right"]),
						so(Q((t) => B(r).resize(e.card.id, "height", -40), ["prevent"]), ["up"]),
						so(Q((t) => B(r).resize(e.card.id, "height", 40), ["prevent"]), ["down"])
					]
				}, [...t[21] ||= [Y("svg", {
					viewBox: "0 0 16 16",
					"aria-hidden": "true"
				}, [Y("path", { d: "M6 14l8-8M10 14l4-4" })], -1)]], 40, Vs)
			], 44, fs))), 128))])
		]));
	}
}), [["__scopeId", "data-v-56b51968"]]), Us = class extends Error {
	status;
	code;
	constructor(e, t, n = "") {
		super(e), this.status = t, this.code = n, this.name = "ApiError";
	}
};
async function Ws(e, t = {}, n) {
	let r = await fetch(e, {
		credentials: "same-origin",
		...t
	});
	if (!(r.headers.get("content-type") || "").includes("application/json")) throw new Us(r.redirected || r.status === 401 ? "登录已失效，请重新登录后刷新。" : `服务返回了非 JSON 响应（HTTP ${r.status}）`, r.status);
	let i = n ? n(await r.text()) : await r.json();
	if (!r.ok || i?.ok === !1) {
		let e = i?.error;
		throw new Us(typeof e == "string" ? e : e?.message || i?.message || `请求失败（HTTP ${r.status}）`, r.status, e?.code || i?.error_code || i?.code || "");
	}
	return i;
}
// src/api/dashboard.ts
function Gs(e = (e, t) => Ws(e, t)) {
	let t = (t, n) => e(t, n ? { signal: n } : void 0);
	return {
		dashboard: (e) => t("/api/dashboard", e),
		capabilities: (e) => t("/api/capabilities", e)
	};
}
// src/dashboard.ts
function Ks(e, t = {}) {
	let n = fo(Hs, {
		api: t.api || Gs(),
		deps: t
	}), r = n.mount(e);
	return {
		setVisible: r.setVisible,
		load: r.load,
		openCustomizer: r.openCustomizer,
		closeCustomizer: r.closeCustomizer,
		resetLayout: r.resetLayout,
		destroy: () => n.unmount()
	};
}
export { Ks as mountDashboard };
