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
}, te = /-\w/g, E = /* @__PURE__ */ ee((e) => e.replace(te, (e) => e.slice(1).toUpperCase())), ne = /\B([A-Z])/g, D = /* @__PURE__ */ ee((e) => e.replace(ne, "-$1").toLowerCase()), re = /* @__PURE__ */ ee((e) => e.charAt(0).toUpperCase() + e.slice(1)), O = /* @__PURE__ */ ee((e) => e ? `on${re(e)}` : ""), ie = (e, t) => !Object.is(e, t), ae = (e, ...t) => {
	for (let n = 0; n < e.length; n++) e[n](...t);
}, k = (e, t, n, r = !1) => {
	Object.defineProperty(e, t, {
		configurable: !0,
		enumerable: !1,
		writable: r,
		value: n
	});
}, oe = (e) => {
	let t = parseFloat(e);
	return isNaN(t) ? e : t;
}, se, ce = () => se ||= typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {};
function le(e) {
	if (d(e)) {
		let t = {};
		for (let n = 0; n < e.length; n++) {
			let r = e[n], i = g(r) ? pe(r) : le(r);
			if (i) for (let e in i) t[e] = i[e];
		}
		return t;
	}
	if (g(e) || v(e)) return e;
}
var ue = /;(?![^(]*\))/g, de = /:([^]+)/, fe = /"(?:[^"\\]|\\[^])*"|'(?:[^'\\]|\\[^])*'|\\[^]|\/\*[^]*?\*\//g;
function pe(e) {
	let t = {};
	return e.replace(fe, (e) => e.startsWith("/*") ? "" : e).split(ue).forEach((e) => {
		if (e) {
			let n = e.split(de);
			n.length > 1 && (t[n[0].trim()] = n[1].trim());
		}
	}), t;
}
function A(e) {
	let t = "";
	if (g(e)) t = e;
	else if (d(e)) for (let n = 0; n < e.length; n++) {
		let r = A(e[n]);
		r && (t += r + " ");
	}
	else if (v(e)) for (let n in e) e[n] && (t += n + " ");
	return t.trim();
}
function me(e) {
	if (!e) return null;
	let { class: t, style: n } = e;
	return t && !g(t) && (e.class = A(t)), n && (e.style = le(n)), e;
}
var he = /* @__PURE__ */ e("itemscope,allowfullscreen,disablepictureinpicture,disableremoteplayback,formnovalidate,ismap,nomodule,novalidate,playsinline,readonly");
function ge(e) {
	return !!e || e === "";
}
function _e(e, t, n) {
	if (e.length !== t.length) return !1;
	let r = !0;
	for (let i = 0; r && i < e.length; i++) r = xe(e[i], t[i], n);
	return r;
}
function ve(e, t, n) {
	if (e.size !== t.size) return !1;
	let r = Array.from(t), i = new Uint8Array(r.length);
	for (let t of e) {
		let e = -1;
		for (let a = 0; a < r.length; a++) if (!i[a] && xe(t, r[a], n)) {
			e = a;
			break;
		}
		if (e < 0) return !1;
		i[e] = 1;
	}
	return !0;
}
function ye(e, t, n) {
	let r = f(e), i = f(t);
	if (r || i || (r = p(e), i = p(t), r || i)) return r && i ? ve(e, t, n) : !1;
	if (Object.keys(e).length !== Object.keys(t).length) return !1;
	for (let r in e) {
		let i = e.hasOwnProperty(r), a = t.hasOwnProperty(r);
		if (i && !a || !i && a || !xe(e[r], t[r], n)) return !1;
	}
	return String(e) === String(t);
}
function be(e, t, n, r) {
	n ||= [/* @__PURE__ */ new Map(), /* @__PURE__ */ new Map()];
	let [i, a] = n;
	if (i.has(e) || a.has(t)) return i.get(e) === t && a.get(t) === e;
	i.set(e, t), a.set(t, e);
	let o = r(e, t, n);
	return i.delete(e), a.delete(t), o;
}
function xe(e, t, n) {
	if (e === t) return !0;
	let r = m(e), i = m(t);
	return r || i ? r && i ? e.getTime() === t.getTime() : !1 : (r = _(e), i = _(t), r || i ? e === t : (r = d(e), i = d(t), r || i ? r && i ? be(e, t, n, _e) : !1 : (r = v(e), i = v(t), r || i ? !r || !i ? !1 : be(e, t, n, ye) : String(e) === String(t))));
}
function Se(e, t) {
	return e.findIndex((e) => xe(e, t));
}
var Ce = (e) => !!(e && e.__v_isRef === !0), j = (e) => g(e) ? e : e == null ? "" : d(e) || v(e) && (e.toString === b || !h(e.toString)) ? Ce(e) ? j(e.value) : JSON.stringify(e, we, 2) : String(e), we = (e, t) => Ce(t) ? we(e, t.value) : f(t) ? { [`Map(${t.size})`]: [...t.entries()].reduce((e, [t, n], r) => (e[Te(t, r) + " =>"] = n, e), {}) } : p(t) ? { [`Set(${t.size})`]: [...t.values()].map((e) => Te(e)) } : _(t) ? Te(t) : v(t) && !d(t) && !C(t) ? String(t) : t, Te = (e, t = "") => _(e) ? `Symbol(${e.description ?? t})` : e, M, Ee = class {
	constructor(e = !1) {
		this.detached = e, this._active = !0, this._on = 0, this.effects = [], this.cleanups = [], this._isPaused = !1, this._warnOnRun = !0, this.__v_skip = !0, !e && M && (M.active ? (this.parent = M, this.index = (M.scopes || (M.scopes = [])).push(this) - 1) : (this._active = !1, this._warnOnRun = !1));
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
			let t = M;
			try {
				return M = this, e();
			} finally {
				M = t;
			}
		}
	}
	on() {
		++this._on === 1 && (this.prevScope = M, M = this);
	}
	off() {
		if (this._on > 0 && --this._on === 0) {
			if (M === this) M = this.prevScope;
			else {
				let e = M;
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
function De(e) {
	return new Ee(e);
}
function Oe() {
	return M;
}
function ke(e, t = !1) {
	M && (M.active ? M.cleanups.push(e) : e());
}
var N, Ae = /* @__PURE__ */ new WeakSet(), je = class {
	constructor(e) {
		this.fn = e, this.deps = void 0, this.depsTail = void 0, this.flags = 5, this.next = void 0, this.cleanup = void 0, this.scheduler = void 0, M && (M.active ? M.effects.push(this) : this.flags &= -2);
	}
	pause() {
		this.flags |= 64;
	}
	resume() {
		this.flags & 64 && (this.flags &= -65, Ae.has(this) && (Ae.delete(this), this.trigger()));
	}
	notify() {
		this.flags & 2 && !(this.flags & 32) || this.flags & 8 || Fe(this);
	}
	run() {
		if (!(this.flags & 1)) return this.fn();
		this.flags |= 2, Je(this), Re(this);
		let e = N, t = We;
		N = this, We = !0;
		try {
			return this.fn();
		} finally {
			ze(this), N = e, We = t, this.flags &= -3;
		}
	}
	stop() {
		if (this.flags & 1) {
			for (let e = this.deps; e; e = e.nextDep) He(e);
			this.deps = this.depsTail = void 0, Je(this), this.onStop && this.onStop(), this.flags &= -2;
		}
	}
	trigger() {
		this.flags & 64 ? Ae.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
	}
	runIfDirty() {
		Be(this) && this.run();
	}
	get dirty() {
		return Be(this);
	}
}, Me = 0, Ne, Pe;
function Fe(e, t = !1) {
	e.flags |= 8, t ? (e.next = Pe, Pe = e) : (e.next = Ne, Ne = e);
}
function Ie() {
	Me++;
}
function Le() {
	if (--Me > 0) return;
	if (Pe) {
		let e = Pe;
		for (Pe = void 0; e;) {
			let t = e.next;
			e.next = void 0, e.flags &= -9, e = t;
		}
	}
	let e;
	for (; Ne;) {
		let t = Ne;
		for (Ne = void 0; t;) {
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
function Re(e) {
	for (let t = e.deps; t; t = t.nextDep) t.version = -1, t.prevActiveLink = t.dep.activeLink, t.dep.activeLink = t;
}
function ze(e) {
	let t, n = e.depsTail, r = n;
	for (; r;) {
		let e = r.prevDep;
		r.version === -1 ? (r === n && (n = e), He(r), Ue(r)) : t = r, r.dep.activeLink = r.prevActiveLink, r.prevActiveLink = void 0, r = e;
	}
	e.deps = t, e.depsTail = n;
}
function Be(e) {
	for (let t = e.deps; t; t = t.nextDep) if (t.dep.version !== t.version || t.dep.computed && (Ve(t.dep.computed) || t.dep.version !== t.version)) return !0;
	return !!e._dirty;
}
function Ve(e) {
	if (e.flags & 4 && !(e.flags & 16) || (e.flags &= -17, e.globalVersion === Ye) || (e.globalVersion = Ye, !e.isSSR && e.flags & 128 && (!e.deps && !e._dirty || !Be(e)))) return;
	e.flags |= 2;
	let t = e.dep, n = N, r = We;
	N = e, We = !0;
	try {
		Re(e);
		let n = e.fn(e._value);
		(t.version === 0 || ie(n, e._value)) && (e.flags |= 128, e._value = n, t.version++);
	} catch (e) {
		throw t.version++, e;
	} finally {
		N = n, We = r, ze(e), e.flags &= -3;
	}
}
function He(e, t = !1) {
	let { dep: n, prevSub: r, nextSub: i } = e;
	if (r && (r.nextSub = i, e.prevSub = void 0), i && (i.prevSub = r, e.nextSub = void 0), n.subs === e && (n.subs = r, !r && n.computed)) {
		n.computed.flags &= -5;
		for (let e = n.computed.deps; e; e = e.nextDep) He(e, !0);
	}
	!t && !--n.sc && n.map && n.map.delete(n.key);
}
function Ue(e) {
	let { prevDep: t, nextDep: n } = e;
	t && (t.nextDep = n, e.prevDep = void 0), n && (n.prevDep = t, e.nextDep = void 0);
}
var We = !0, Ge = [];
function Ke() {
	Ge.push(We), We = !1;
}
function qe() {
	let e = Ge.pop();
	We = e === void 0 || e;
}
function Je(e) {
	let { cleanup: t } = e;
	if (e.cleanup = void 0, t) {
		let e = N;
		N = void 0;
		try {
			t();
		} finally {
			N = e;
		}
	}
}
var Ye = 0, Xe = class {
	constructor(e, t) {
		this.sub = e, this.dep = t, this.version = t.version, this.nextDep = this.prevDep = this.nextSub = this.prevSub = this.prevActiveLink = void 0;
	}
}, Ze = class {
	constructor(e) {
		this.computed = e, this.version = 0, this.activeLink = void 0, this.subs = void 0, this.map = void 0, this.key = void 0, this.sc = 0, this.__v_skip = !0;
	}
	track(e) {
		if (!N || !We || N === this.computed) return;
		let t = this.activeLink;
		if (t === void 0 || t.sub !== N) t = this.activeLink = new Xe(N, this), N.deps ? (t.prevDep = N.depsTail, N.depsTail.nextDep = t, N.depsTail = t) : N.deps = N.depsTail = t, Qe(t);
		else if (t.version === -1 && (t.version = this.version, t.nextDep)) {
			let e = t.nextDep;
			e.prevDep = t.prevDep, t.prevDep && (t.prevDep.nextDep = e), t.prevDep = N.depsTail, t.nextDep = void 0, N.depsTail.nextDep = t, N.depsTail = t, N.deps === t && (N.deps = e);
		}
		return t;
	}
	trigger(e) {
		this.version++, Ye++, this.notify(e);
	}
	notify(e) {
		Ie();
		try {
			for (let e = this.subs; e; e = e.prevSub) e.sub.notify() && e.sub.dep.notify();
		} finally {
			Le();
		}
	}
};
function Qe(e) {
	if (e.dep.sc++, e.sub.flags & 4) {
		let t = e.dep.computed;
		if (t && !e.dep.subs) {
			t.flags |= 20;
			for (let e = t.deps; e; e = e.nextDep) Qe(e);
		}
		let n = e.dep.subs;
		n !== e && (e.prevSub = n, n && (n.nextSub = e)), e.dep.subs = e;
	}
}
var $e = /* @__PURE__ */ new WeakMap(), et = /* @__PURE__ */ Symbol(""), tt = /* @__PURE__ */ Symbol(""), nt = /* @__PURE__ */ Symbol("");
function rt(e, t, n) {
	if (We && N) {
		let t = $e.get(e);
		t || $e.set(e, t = /* @__PURE__ */ new Map());
		let r = t.get(n);
		r || (t.set(n, r = new Ze()), r.map = t, r.key = n), r.track();
	}
}
function it(e, t, n, r, i, a) {
	let o = $e.get(e);
	if (!o) {
		Ye++;
		return;
	}
	let s = (e) => {
		e && e.trigger();
	};
	if (Ie(), t === "clear") o.forEach(s);
	else {
		let i = d(e), a = i && w(n);
		if (i && n === "length") {
			let e = Number(r);
			o.forEach((t, n) => {
				(n === "length" || n === nt || !_(n) && n >= e) && s(t);
			});
		} else switch ((n !== void 0 || o.has(void 0)) && s(o.get(n)), a && s(o.get(nt)), t) {
			case "add":
				i ? a && s(o.get("length")) : (s(o.get(et)), f(e) && s(o.get(tt)));
				break;
			case "delete":
				i || (s(o.get(et)), f(e) && s(o.get(tt)));
				break;
			case "set": f(e) && s(o.get(et));
		}
	}
	Le();
}
function at(e, t) {
	let n = $e.get(e);
	return n && n.get(t);
}
function ot(e) {
	let t = /* @__PURE__ */ P(e);
	return t === e || (rt(t, "iterate", nt), /* @__PURE__ */ Yt(e)) ? t : /* @__PURE__ */ Jt(e) ? /* @__PURE__ */ qt(e) ? t.map((e) => $t(Qt(e))) : t.map($t) : t.map(Qt);
}
function st(e) {
	return rt(e = /* @__PURE__ */ P(e), "iterate", nt), e;
}
function ct(e, t) {
	return /* @__PURE__ */ Jt(e) ? $t(/* @__PURE__ */ qt(e) ? Qt(t) : t) : Qt(t);
}
var lt = {
	__proto__: null,
	[Symbol.iterator]() {
		return ut(this, Symbol.iterator, (e) => ct(this, e));
	},
	concat(...e) {
		return ot(this).concat(...e.map((e) => d(e) ? ot(e) : e));
	},
	entries() {
		return ut(this, "entries", (e) => (e[1] = ct(this, e[1]), e));
	},
	every(e, t) {
		return pt(this, "every", e, t, void 0, arguments);
	},
	filter(e, t) {
		return pt(this, "filter", e, t, (e) => e.map((e) => ct(this, e)), arguments);
	},
	find(e, t) {
		return pt(this, "find", e, t, (e) => ct(this, e), arguments);
	},
	findIndex(e, t) {
		return pt(this, "findIndex", e, t, void 0, arguments);
	},
	findLast(e, t) {
		return pt(this, "findLast", e, t, (e) => ct(this, e), arguments);
	},
	findLastIndex(e, t) {
		return pt(this, "findLastIndex", e, t, void 0, arguments);
	},
	forEach(e, t) {
		return pt(this, "forEach", e, t, void 0, arguments);
	},
	includes(...e) {
		return ht(this, "includes", e);
	},
	indexOf(...e) {
		return ht(this, "indexOf", e);
	},
	join(e) {
		return ot(this).join(e);
	},
	lastIndexOf(...e) {
		return ht(this, "lastIndexOf", e);
	},
	map(e, t) {
		return pt(this, "map", e, t, void 0, arguments);
	},
	pop() {
		return gt(this, "pop");
	},
	push(...e) {
		return gt(this, "push", e);
	},
	reduce(e, ...t) {
		return mt(this, "reduce", e, t);
	},
	reduceRight(e, ...t) {
		return mt(this, "reduceRight", e, t);
	},
	shift() {
		return gt(this, "shift");
	},
	some(e, t) {
		return pt(this, "some", e, t, void 0, arguments);
	},
	splice(...e) {
		return gt(this, "splice", e);
	},
	toReversed() {
		return ot(this).toReversed();
	},
	toSorted(e) {
		return ot(this).toSorted(e);
	},
	toSpliced(...e) {
		return ot(this).toSpliced(...e);
	},
	unshift(...e) {
		return gt(this, "unshift", e);
	},
	values() {
		return ut(this, "values", (e) => ct(this, e));
	}
};
function ut(e, t, n) {
	let r = st(e), i = r[t], a = i.call(r);
	if (r !== e && !/* @__PURE__ */ Yt(e)) {
		if (a[Symbol.toStringTag] === "Array Iterator") {
			let e = Object.create(Object.getPrototypeOf(a));
			return e.next = () => dt(a.next(), n), i !== ft[t] && Object.defineProperties(e, {
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
		a._next = a.next, a.next = () => dt(a._next(), n);
	}
	return a;
}
function dt(e, t) {
	return e.done || (e.value = t(e.value)), e;
}
var ft = Array.prototype;
function pt(e, t, n, r, i, a) {
	let o = st(e), s = o !== e && !/* @__PURE__ */ Yt(e), c = o[t];
	if (c !== ft[t]) {
		let t = c.apply(e, a);
		return s ? Qt(t) : t;
	}
	let l = n;
	o !== e && (s ? l = function(t, r) {
		return n.call(this, ct(e, t), r, e);
	} : n.length > 2 && (l = function(t, r) {
		return n.call(this, t, r, e);
	}));
	let u = c.call(o, l, r);
	return s && i ? i(u) : u;
}
function mt(e, t, n, r) {
	let i = st(e), a = i !== e && !/* @__PURE__ */ Yt(e), o = n, s = !1;
	i !== e && (a ? (s = r.length === 0, o = function(t, r, i) {
		return s && (s = !1, t = ct(e, t)), n.call(this, t, ct(e, r), i, e);
	}) : n.length > 3 && (o = function(t, r, i) {
		return n.call(this, t, r, i, e);
	}));
	let c = i[t](o, ...r);
	return s ? ct(e, c) : c;
}
function ht(e, t, n) {
	let r = /* @__PURE__ */ P(e);
	rt(r, "iterate", nt);
	let i = r[t](...n);
	return (i === -1 || i === !1) && /* @__PURE__ */ Xt(n[0]) ? (n[0] = /* @__PURE__ */ P(n[0]), r[t](...n)) : i;
}
function gt(e, t, n = []) {
	Ke(), Ie();
	let r = (/* @__PURE__ */ P(e))[t].apply(e, n);
	return Le(), qe(), r;
}
var _t = /* @__PURE__ */ e("__proto__,__v_isRef,__isVue"), vt = /* @__PURE__ */ new Set(/* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(_));
function yt(e) {
	_(e) || (e = String(e));
	let t = /* @__PURE__ */ P(this);
	return rt(t, "has", e), t.hasOwnProperty(e);
}
var bt = class {
	constructor(e = !1, t = !1) {
		this._isReadonly = e, this._isShallow = t;
	}
	get(e, t, n) {
		if (t === "__v_skip") return e.__v_skip;
		let r = this._isReadonly, i = this._isShallow;
		if (t === "__v_isReactive") return !r;
		if (t === "__v_isReadonly") return r;
		if (t === "__v_isShallow") return i;
		if (t === "__v_raw") return n === (r ? i ? Bt : zt : i ? Rt : Lt).get(e) || Object.getPrototypeOf(e) === Object.getPrototypeOf(n) ? e : void 0;
		let a = d(e);
		if (!r) {
			let e;
			if (a && (e = lt[t])) return e;
			if (t === "hasOwnProperty") return yt;
		}
		let o = Reflect.get(e, t, /* @__PURE__ */ F(e) ? e : n);
		if ((_(t) ? vt.has(t) : _t(t)) || (r || rt(e, "get", t), i)) return o;
		if (/* @__PURE__ */ F(o)) {
			let e = a && w(t) ? o : o.value;
			return r && v(e) ? /* @__PURE__ */ Wt(e) : e;
		}
		return v(o) ? r ? /* @__PURE__ */ Wt(o) : /* @__PURE__ */ Ht(o) : o;
	}
}, xt = class extends bt {
	constructor(e = !1) {
		super(!1, e);
	}
	set(e, t, n, r) {
		let i = e[t], a = d(e) && w(t);
		if (!this._isShallow) {
			let e = /* @__PURE__ */ Jt(i);
			if (!/* @__PURE__ */ Yt(n) && !/* @__PURE__ */ Jt(n) && (i = /* @__PURE__ */ P(i), n = /* @__PURE__ */ P(n)), !a && /* @__PURE__ */ F(i) && !/* @__PURE__ */ F(n)) return e || (i.value = n), !0;
		}
		let o = a ? Number(t) < e.length : u(e, t), s = Reflect.set(e, t, n, /* @__PURE__ */ F(e) ? e : r);
		return e === /* @__PURE__ */ P(r) && s && (o ? ie(n, i) && it(e, "set", t, n, i) : it(e, "add", t, n)), s;
	}
	deleteProperty(e, t) {
		let n = u(e, t), r = e[t], i = Reflect.deleteProperty(e, t);
		return i && n && it(e, "delete", t, void 0, r), i;
	}
	has(e, t) {
		let n = Reflect.has(e, t);
		return _(t) && vt.has(t) || rt(e, "has", t), n;
	}
	ownKeys(e) {
		return rt(e, "iterate", d(e) ? "length" : et), Reflect.ownKeys(e);
	}
}, St = class extends bt {
	constructor(e = !1) {
		super(!0, e);
	}
	set(e, t) {
		return !0;
	}
	deleteProperty(e, t) {
		return !0;
	}
}, Ct = /* @__PURE__ */ new xt(), wt = /* @__PURE__ */ new St(), Tt = /* @__PURE__ */ new xt(!0), Et = /* @__PURE__ */ new St(!0), Dt = (e) => e, Ot = (e) => Reflect.getPrototypeOf(e);
function kt(e, t, n) {
	return function(...r) {
		let i = this.__v_raw, a = /* @__PURE__ */ P(i), o = f(a), c = e === "entries" || e === Symbol.iterator && o, l = e === "keys" && o, u = i[e](...r), d = n ? Dt : t ? $t : Qt;
		return !t && rt(a, "iterate", l ? tt : et), s(Object.create(u), { next() {
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
function At(e) {
	return function(...t) {
		return e === "delete" ? !1 : e === "clear" ? void 0 : this;
	};
}
function jt(e, t) {
	let n = {
		get(n) {
			let r = this.__v_raw, i = /* @__PURE__ */ P(r), a = /* @__PURE__ */ P(n);
			e || (ie(n, a) && rt(i, "get", n), rt(i, "get", a));
			let { has: o } = Ot(i), s = t ? Dt : e ? $t : Qt;
			if (o.call(i, n)) return s(r.get(n));
			if (o.call(i, a)) return s(r.get(a));
			r !== i && r.get(n);
		},
		get size() {
			let t = this.__v_raw;
			return !e && rt(/* @__PURE__ */ P(t), "iterate", et), t.size;
		},
		has(t) {
			let n = this.__v_raw, r = /* @__PURE__ */ P(n), i = /* @__PURE__ */ P(t);
			return e || (ie(t, i) && rt(r, "has", t), rt(r, "has", i)), t === i ? n.has(t) : n.has(t) || n.has(i);
		},
		forEach(n, r) {
			let i = this, a = i.__v_raw, o = /* @__PURE__ */ P(a), s = t ? Dt : e ? $t : Qt;
			return !e && rt(o, "iterate", et), a.forEach((e, t) => n.call(r, s(e), s(t), i));
		}
	};
	return s(n, e ? {
		add: At("add"),
		set: At("set"),
		delete: At("delete"),
		clear: At("clear")
	} : {
		add(e) {
			let n = /* @__PURE__ */ P(this), r = Ot(n), i = /* @__PURE__ */ P(e), a = !t && !/* @__PURE__ */ Yt(e) && !/* @__PURE__ */ Jt(e) ? i : e;
			return r.has.call(n, a) || ie(e, a) && r.has.call(n, e) || ie(i, a) && r.has.call(n, i) || (n.add(a), it(n, "add", a, a)), this;
		},
		set(e, n) {
			t || /* @__PURE__ */ Yt(n) || /* @__PURE__ */ Jt(n) || (n = /* @__PURE__ */ P(n));
			let r = /* @__PURE__ */ P(this), { has: i, get: a } = Ot(r), o = i.call(r, e);
			o ||= (e = /* @__PURE__ */ P(e), i.call(r, e));
			let s = a.call(r, e);
			return r.set(e, n), o ? ie(n, s) && it(r, "set", e, n, s) : it(r, "add", e, n), this;
		},
		delete(e) {
			let t = /* @__PURE__ */ P(this), { has: n, get: r } = Ot(t), i = n.call(t, e);
			i ||= (e = /* @__PURE__ */ P(e), n.call(t, e));
			let a = r ? r.call(t, e) : void 0, o = t.delete(e);
			return i && it(t, "delete", e, void 0, a), o;
		},
		clear() {
			let e = /* @__PURE__ */ P(this), t = e.size !== 0, n = e.clear();
			return t && it(e, "clear", void 0, void 0, void 0), n;
		}
	}), [
		"keys",
		"values",
		"entries",
		Symbol.iterator
	].forEach((r) => {
		n[r] = kt(r, e, t);
	}), n;
}
function Mt(e, t) {
	let n = jt(e, t);
	return (r, i, a) => i === "__v_isReactive" ? !e : i === "__v_isReadonly" ? e : i === "__v_isShallow" ? t : i === "__v_raw" ? r : Reflect.get(u(n, i) && i in r ? n : r, i, a);
}
var Nt = { get: /* @__PURE__ */ Mt(!1, !1) }, Pt = { get: /* @__PURE__ */ Mt(!1, !0) }, Ft = { get: /* @__PURE__ */ Mt(!0, !1) }, It = { get: /* @__PURE__ */ Mt(!0, !0) }, Lt = /* @__PURE__ */ new WeakMap(), Rt = /* @__PURE__ */ new WeakMap(), zt = /* @__PURE__ */ new WeakMap(), Bt = /* @__PURE__ */ new WeakMap();
function Vt(e) {
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
function Ht(e) {
	return /* @__PURE__ */ Jt(e) ? e : Kt(e, !1, Ct, Nt, Lt);
}
// @__NO_SIDE_EFFECTS__
function Ut(e) {
	return Kt(e, !1, Tt, Pt, Rt);
}
// @__NO_SIDE_EFFECTS__
function Wt(e) {
	return Kt(e, !0, wt, Ft, zt);
}
// @__NO_SIDE_EFFECTS__
function Gt(e) {
	return Kt(e, !0, Et, It, Bt);
}
function Kt(e, t, n, r, i) {
	if (!v(e) || e.__v_raw && !(t && e.__v_isReactive) || e.__v_skip || !Object.isExtensible(e)) return e;
	let a = i.get(e);
	if (a) return a;
	let o = Vt(S(e));
	if (o === 0) return e;
	let s = new Proxy(e, o === 2 ? r : n);
	return i.set(e, s), s;
}
// @__NO_SIDE_EFFECTS__
function qt(e) {
	return /* @__PURE__ */ Jt(e) ? /* @__PURE__ */ qt(e.__v_raw) : !!(e && e.__v_isReactive);
}
// @__NO_SIDE_EFFECTS__
function Jt(e) {
	return !!(e && e.__v_isReadonly);
}
// @__NO_SIDE_EFFECTS__
function Yt(e) {
	return !!(e && e.__v_isShallow);
}
// @__NO_SIDE_EFFECTS__
function Xt(e) {
	return e ? !!e.__v_raw : !1;
}
// @__NO_SIDE_EFFECTS__
function P(e) {
	let t = e && e.__v_raw;
	return t ? /* @__PURE__ */ P(t) : e;
}
function Zt(e) {
	return !u(e, "__v_skip") && Object.isExtensible(e) && k(e, "__v_skip", !0), e;
}
var Qt = (e) => v(e) ? /* @__PURE__ */ Ht(e) : e, $t = (e) => v(e) ? /* @__PURE__ */ Wt(e) : e;
// @__NO_SIDE_EFFECTS__
function F(e) {
	return e ? e.__v_isRef === !0 : !1;
}
// @__NO_SIDE_EFFECTS__
function I(e) {
	return tn(e, !1);
}
// @__NO_SIDE_EFFECTS__
function en(e) {
	return tn(e, !0);
}
function tn(e, t) {
	return /* @__PURE__ */ F(e) ? e : new nn(e, t);
}
var nn = class {
	constructor(e, t) {
		this.dep = new Ze(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = t ? e : /* @__PURE__ */ P(e), this._value = t ? e : Qt(e), this.__v_isShallow = t;
	}
	get value() {
		return this.dep.track(), this._value;
	}
	set value(e) {
		let t = this._rawValue, n = this.__v_isShallow || /* @__PURE__ */ Yt(e) || /* @__PURE__ */ Jt(e);
		e = n ? e : /* @__PURE__ */ P(e), ie(e, t) && (this._rawValue = e, this._value = n ? e : Qt(e), this.dep.trigger());
	}
};
function rn(e) {
	e.dep && e.dep.trigger();
}
function L(e) {
	return /* @__PURE__ */ F(e) ? e.value : e;
}
function R(e) {
	return h(e) ? e() : L(e);
}
var an = {
	get: (e, t, n) => t === "__v_raw" ? e : L(Reflect.get(e, t, n)),
	set: (e, t, n, r) => {
		let i = e[t];
		return /* @__PURE__ */ F(i) && !/* @__PURE__ */ F(n) ? (i.value = n, !0) : Reflect.set(e, t, n, r);
	}
};
function on(e) {
	return /* @__PURE__ */ qt(e) ? e : new Proxy(e, an);
}
// @__NO_SIDE_EFFECTS__
function sn(e) {
	let t = d(e) ? Array(e.length) : {};
	for (let n in e) t[n] = dn(e, n);
	return t;
}
var cn = class {
	constructor(e, t, n) {
		this._object = e, this._defaultValue = n, this.__v_isRef = !0, this._value = void 0, this._key = _(t) ? t : String(t), this._raw = /* @__PURE__ */ P(e);
		let r = !0, i = e;
		if (!d(e) || _(this._key) || !w(this._key)) do
			r = !/* @__PURE__ */ Xt(i) || /* @__PURE__ */ Yt(i);
		while (r && (i = i.__v_raw));
		this._shallow = r;
	}
	get value() {
		let e = this._object[this._key];
		return this._shallow && (e = L(e)), this._value = e === void 0 ? this._defaultValue : e;
	}
	set value(e) {
		if (this._shallow && /* @__PURE__ */ F(this._raw[this._key])) {
			let t = this._object[this._key];
			if (/* @__PURE__ */ F(t)) {
				t.value = e;
				return;
			}
		}
		this._object[this._key] = e;
	}
	get dep() {
		return at(this._raw, this._key);
	}
}, ln = class {
	constructor(e) {
		this._getter = e, this.__v_isRef = !0, this.__v_isReadonly = !0, this._value = void 0;
	}
	get value() {
		return this._value = this._getter();
	}
};
// @__NO_SIDE_EFFECTS__
function un(e, t, n) {
	return /* @__PURE__ */ F(e) ? e : h(e) ? new ln(e) : v(e) && arguments.length > 1 ? dn(e, t, n) : /* @__PURE__ */ I(e);
}
function dn(e, t, n) {
	return new cn(e, t, n);
}
var fn = class {
	constructor(e, t, n) {
		this.fn = e, this.setter = t, this._value = void 0, this.dep = new Ze(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = Ye - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !t, this.isSSR = n;
	}
	notify() {
		if (this.flags |= 16, !(this.flags & 8) && N !== this) return Fe(this, !0), !0;
	}
	get value() {
		let e = this.dep.track();
		return Ve(this), e && (e.version = this.dep.version), this._value;
	}
	set value(e) {
		this.setter && this.setter(e);
	}
};
// @__NO_SIDE_EFFECTS__
function pn(e, t, n = !1) {
	let r, i;
	return h(e) ? r = e : (r = e.get, i = e.set), new fn(r, i, n);
}
var mn = {}, hn = /* @__PURE__ */ new WeakMap(), gn = void 0;
function _n(e, t = !1, n = gn) {
	if (n) {
		let t = hn.get(n);
		t || hn.set(n, t = []), t.push(e);
	}
}
function vn(e, n, i = t) {
	let { immediate: a, deep: o, once: s, scheduler: l, augmentJob: u, call: f } = i, p = (e) => o ? e : /* @__PURE__ */ Yt(e) || o === !1 || o === 0 ? yn(e, 1) : yn(e), m, g, _, v, y = !1, b = !1;
	if (/* @__PURE__ */ F(e) ? (g = () => e.value, y = /* @__PURE__ */ Yt(e)) : /* @__PURE__ */ qt(e) ? (g = () => p(e), y = !0) : d(e) ? (b = !0, y = e.some((e) => /* @__PURE__ */ qt(e) || /* @__PURE__ */ Yt(e)), g = () => e.map((e) => {
		if (/* @__PURE__ */ F(e)) return e.value;
		if (/* @__PURE__ */ qt(e)) return p(e);
		if (h(e)) return f ? f(e, 2) : e();
	})) : g = h(e) ? n ? f ? () => f(e, 2) : e : () => {
		if (_) {
			Ke();
			try {
				_();
			} finally {
				qe();
			}
		}
		let t = gn;
		gn = m;
		try {
			return f ? f(e, 3, [v]) : e(v);
		} finally {
			gn = t;
		}
	} : r, n && o) {
		let e = g, t = o === !0 ? Infinity : o;
		g = () => yn(e(), t);
	}
	let x = Oe(), S = () => {
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
	let C = b ? Array(e.length).fill(mn) : mn, w = (e) => {
		if (m.flags & 1 && (m.dirty || e)) {
			if (n) {
				let t = m.run();
				if (e || o || y || (b ? t.some((e, t) => ie(e, C[t])) : ie(t, C))) {
					let e = gn;
					Ke();
					try {
						_ && _(), gn = m;
						let e = [
							t,
							C === mn ? void 0 : b && C[0] === mn ? [] : C,
							v
						];
						C = t, f ? f(n, 3, e) : n(...e);
					} finally {
						gn = e, qe();
					}
				}
			} else m.run();
		}
	};
	return u && u(w), m = new je(g), m.scheduler = l ? () => l(w, !1) : w, v = (e) => _n(e, !1, m), _ = m.onStop = () => {
		let e = hn.get(m);
		if (e) {
			if (f) f(e, 4);
			else for (let t of e) t();
			hn.delete(m);
		}
	}, n ? a ? w(!0) : C = m.run() : l ? l(w.bind(null, !0), !0) : m.run(), S.pause = m.pause.bind(m), S.resume = m.resume.bind(m), S.stop = S, S;
}
function yn(e, t = Infinity, n) {
	if (t <= 0 || !v(e) || e.__v_skip || (n ||= /* @__PURE__ */ new Map(), (n.get(e) || 0) >= t)) return e;
	if (n.set(e, t), t--, /* @__PURE__ */ F(e)) yn(e.value, t, n);
	else if (d(e)) for (let r = 0; r < e.length; r++) yn(e[r], t, n);
	else if (p(e) || f(e)) e.forEach((e) => {
		yn(e, t, n);
	});
	else if (C(e)) {
		for (let r in e) yn(e[r], t, n);
		for (let r of Object.getOwnPropertySymbols(e)) Object.prototype.propertyIsEnumerable.call(e, r) && yn(e[r], t, n);
	}
	return e;
}
// node_modules/@vue/runtime-core/dist/runtime-core.esm-bundler.js
function bn(e, t, n, r) {
	try {
		return r ? e(...r) : e();
	} catch (e) {
		Sn(e, t, n);
	}
}
function xn(e, t, n, r) {
	if (h(e)) {
		let i = bn(e, t, n, r);
		return i && y(i) && i.catch((e) => {
			Sn(e, t, n, void 0, !0);
		}), i;
	}
	if (d(e)) {
		let i = [];
		for (let a = 0; a < e.length; a++) i.push(xn(e[a], t, n, r));
		return i;
	}
}
function Sn(e, n, r, i = !0, a = !1) {
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
			Ke(), bn(s, null, 10, [
				e,
				i,
				o
			]), qe();
			return;
		}
	}
	Cn(e, r, o, i, c);
}
function Cn(e, t, n, r = !0, i = !1) {
	if (i) throw e;
	console.error(e);
}
var wn = [], Tn = -1, En = [], Dn = null, On = 0, kn = /* @__PURE__ */ Promise.resolve(), An = null;
function jn(e) {
	let t = An || kn;
	return e ? t.then(this ? e.bind(this) : e) : t;
}
function Mn(e) {
	let t = Tn + 1, n = wn.length;
	for (; t < n;) {
		let r = t + n >>> 1, i = wn[r], a = Bn(i);
		a < e || a === e && i.flags & 2 ? t = r + 1 : n = r;
	}
	return t;
}
function Nn(e) {
	if (!(e.flags & 1)) {
		let t = Bn(e), n = wn[wn.length - 1];
		!n || !(e.flags & 2) && t >= Bn(n) ? wn.push(e) : wn.splice(Mn(t), 0, e), e.flags |= 1, Pn();
	}
}
function Pn() {
	An ||= kn.then(Vn);
}
function Fn(e) {
	if (!d(e)) Dn && e.id === -1 ? Dn.splice(On + 1, 0, e) : e.flags & 1 || (En.push(e), e.flags |= 1);
	else for (let t = 0; t < e.length; t++) En.push(e[t]);
	Pn();
}
function In(e, t, n, r = Tn + 1) {
	for (; r < wn.length; r++) {
		let n = wn[r];
		if (n && n.flags & 2) {
			if (e && n.id !== e.uid || t !== void 0 && !(n.id >= t)) continue;
			wn.splice(r, 1), r = e ? r - 1 : Tn, n.flags & 4 && (n.flags &= -2), n(), n.flags & 4 || (n.flags &= -2);
		}
	}
}
function Ln(e, t, n = 0) {
	if (En.length) {
		let e = En, r = 0;
		if (t) {
			e = [];
			for (let i = 0; i < En.length; i++) {
				let a = En[i];
				(a.i === void 0 ? t.has(a) : !a.i || a.i.uid < n) ? En[r++] = a : e.push(a);
			}
		}
		let i = [...new Set(e)].sort((e, t) => Bn(e) - Bn(t));
		if (En.length = r, Dn) {
			for (let e = 0; e < i.length; e++) Dn.push(i[e]);
			return;
		}
		for (Dn = i, On = 0; On < Dn.length; On++) {
			let e = Dn[On];
			e.flags & 4 && (e.flags &= -2), e.flags & 8 || e(), e.flags &= -2;
		}
		Dn = null, On = 0;
	}
}
var Rn = !1;
function zn(e, t) {
	if (Rn) {
		e();
		return;
	}
	let n = t === void 0 ? void 0 : new Set(En);
	e(), Rn = !0;
	try {
		In(void 0, t), Ln(void 0, n, t);
	} finally {
		Rn = !1;
	}
}
var Bn = (e) => e.id == null ? e.flags & 2 ? -1 : Infinity : e.id;
function Vn(e) {
	try {
		for (Tn = 0; Tn < wn.length; Tn++) {
			let e = wn[Tn];
			e && !(e.flags & 8) && (e.flags & 4 && (e.flags &= -2), bn(e, e.i, e.i ? 15 : 14), e.flags & 4 || (e.flags &= -2));
		}
	} finally {
		for (; Tn < wn.length; Tn++) {
			let e = wn[Tn];
			e && (e.flags &= -2);
		}
		Tn = -1, wn.length = 0, Ln(e), An = null, (wn.length || En.length) && Vn(e);
	}
}
var z = null, Hn = null;
function Un(e) {
	let t = z;
	return z = e, Hn = e && e.type.__scopeId || null, t;
}
function B(e, t = z, n) {
	if (!t || e._n) return e;
	let r = (...n) => {
		r._d && ba(-1);
		let i = Un(t), a = ga.length, o;
		try {
			o = e(...n);
		} finally {
			for (let e = ga.length; e > a; e--) va();
			Un(i), r._d && ba(1);
		}
		return o;
	};
	return r._n = !0, r._c = !0, r._d = !0, r;
}
function Wn(e, n) {
	if (z === null) return e;
	let r = to(z), i = e.dirs ||= [];
	for (let e = 0; e < n.length; e++) {
		let [a, o, s, c = t] = n[e];
		a && (h(a) && (a = {
			mounted: a,
			updated: a
		}), a.deep && yn(o), i.push({
			dir: a,
			instance: r,
			value: o,
			oldValue: void 0,
			arg: s,
			modifiers: c
		}));
	}
	return e;
}
function Gn(e, t, n, r) {
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
		u && (Ke(), xn(u, n, 8, [
			e.el,
			l,
			i,
			t
		]), qe());
	}
}
function Kn(e, t) {
	if (Ba) {
		let n = Ba.provides, r = Ba.parent && Ba.parent.provides;
		r === n && (n = Ba.provides = Object.create(r)), n[e] = t;
	}
}
function qn(e, t, n = !1) {
	let r = Va();
	if (r || Si) {
		let i = Si ? Si._context.provides : r ? r.parent == null || r.ce ? r.vnode.appContext && r.vnode.appContext.provides : r.parent.provides : void 0;
		if (i && e in i) return i[e];
		if (arguments.length > 1) return n && h(t) ? t.call(r && r.proxy) : t;
	}
}
var Jn = /* @__PURE__ */ Symbol.for("v-scx"), Yn = () => qn(Jn);
function Xn(e, t) {
	return Qn(e, null, t);
}
function Zn(e, t) {
	return Qn(e, null, { flush: "post" });
}
function V(e, t, n) {
	return Qn(e, t, n);
}
function Qn(e, n, i = t) {
	let { immediate: a, deep: o, flush: c, once: l } = i, u = s({}, i), d = n && a || !n && c !== "post", f;
	if (qa) {
		if (c === "sync") {
			let e = Yn();
			f = e.__watcherHandles ||= [];
		} else if (!d) {
			let e = () => {};
			return e.stop = r, e.resume = r, e.pause = r, e;
		}
	}
	let p = Ba;
	u.call = (e, t, n) => xn(e, p, t, n);
	let m = !1;
	c === "post" ? u.scheduler = (e) => {
		e.i = p, W(e, p && p.suspense);
	} : c !== "sync" && (m = !0, u.scheduler = (e, t) => {
		t ? e() : Nn(e);
	}), u.augmentJob = (e) => {
		n && (e.flags |= 4), m && (e.flags |= 2, p && (e.id = p.uid, e.i = p));
	};
	let h = vn(e, n, u);
	return qa && (f ? f.push(h) : d && h()), h;
}
function $n(e, t, n) {
	let r = this.proxy, i = g(e) ? e.includes(".") ? er(r, e) : () => r[e] : e.bind(r, r), a;
	h(t) ? a = t : (a = t.handler, n = t);
	let o = Wa(this), s = Qn(i, a.bind(r), n);
	return o(), s;
}
function er(e, t) {
	let n = t.split(".");
	return () => {
		let t = e;
		for (let e = 0; e < n.length && t; e++) t = t[n[e]];
		return t;
	};
}
var tr = /* @__PURE__ */ new WeakMap(), nr = /* @__PURE__ */ Symbol("_vte"), rr = (e) => e.__isTeleport, ir = (e) => e && (e.disabled || e.disabled === ""), ar = (e) => e && (e.defer || e.defer === ""), or = (e) => typeof SVGElement < "u" && e instanceof SVGElement, sr = (e) => typeof MathMLElement == "function" && e instanceof MathMLElement, cr = (e, t) => {
	let n = e && e.to;
	return g(n) ? t ? t(n) : null : n;
}, lr = {
	name: "Teleport",
	__isTeleport: !0,
	process(e, t, n, r, i, a, o, s, c, l) {
		let { mc: u, pc: d, pbc: f, o: { insert: p, querySelector: m, createText: h, createComment: g, parentNode: _ } } = l, v = ir(t.props), { dynamicChildren: y } = t, b = (e, t, n) => {
			e.shapeFlag & 16 && u(e.children, t, n, i, a, o, s, c);
		}, x = (e = t) => {
			let n = ir(e.props), r = e.target = cr(e.props, m), a = mr(r, e, h, p);
			r && (o !== "svg" && or(r) ? o = "svg" : o !== "mathml" && sr(r) && (o = "mathml"), i && i.isCE && (i.ce._teleportTargets || (i.ce._teleportTargets = /* @__PURE__ */ new Set())).add(r), n || (b(e, r, a), pr(e, !1)));
		}, S = (e) => {
			let t = () => {
				if (tr.get(e) === t) {
					if (tr.delete(e), ir(e.props)) {
						let t = _(e.el) || n;
						b(e, t, e.anchor), pr(e, !0);
					}
					x(e);
				}
			};
			tr.set(e, t), W(t, a);
		};
		if (e == null) {
			let e = t.el = h(""), i = t.anchor = h("");
			if (p(e, n, r), p(i, n, r), ar(t.props) || a && a.pendingBranch) {
				S(t);
				return;
			}
			v && (b(t, n, i), pr(t, !0)), x();
		} else {
			t.el = e.el;
			let r = t.anchor = e.anchor, u = tr.get(e);
			if (u) {
				u.flags |= 8, tr.delete(e), S(t);
				return;
			}
			t.targetStart = e.targetStart;
			let p = t.target = e.target, h = t.targetAnchor = e.targetAnchor, g = ir(e.props), _ = g ? n : p, b = g ? r : h;
			if (o === "svg" || or(p) ? o = "svg" : (o === "mathml" || sr(p)) && (o = "mathml"), y ? (f(e.dynamicChildren, y, _, i, a, o, s), aa(e, t, !0)) : c || d(e, t, _, b, i, a, o, s, !1), v) g ? t.props && e.props && t.props.to !== e.props.to && (t.props.to = e.props.to) : ur(t, n, r, l, 1);
			else if ((t.props && t.props.to) !== (e.props && e.props.to)) {
				let e = cr(t.props, m);
				e && (t.target = e, ur(t, e, null, l, 0));
			} else g && ur(t, p, h, l, 1);
			pr(t, v);
		}
	},
	remove(e, t, n, { um: r, o: { remove: i } }, a) {
		let { shapeFlag: o, children: s, anchor: c, targetStart: l, targetAnchor: u, target: d, props: f } = e, p = ir(f), m = a || !p, h = tr.get(e);
		if (h && (h.flags |= 8, tr.delete(e)), d && (i(l), i(u)), a && i(c), !h && (p || d) && o & 16) for (let e = 0; e < s.length; e++) {
			let i = s[e];
			r(i, t, n, m, !!i.dynamicChildren);
		}
	},
	move: ur,
	hydrate: dr
};
function ur(e, t, n, { o: { insert: r }, m: i }, a = 2) {
	a === 0 && (e.targetStart && r(e.targetStart, t, n), r(e.targetAnchor, t, n), n = e.targetAnchor);
	let { el: o, anchor: s, shapeFlag: c, children: l, props: u } = e, d = a === 2;
	if (d && r(o, t, n), !tr.has(e) && (!d || ir(u)) && c & 16) for (let e = 0; e < l.length; e++) i(l[e], t, n, 2);
	d && r(s, t, n);
}
function dr(e, t, n, r, i, a, { o: { nextSibling: o, parentNode: s, querySelector: c, insert: l, createText: u } }, d) {
	function f(e, n) {
		let r = n;
		for (; r;) {
			if (r && r.nodeType === 8) {
				if (r.data === "teleport start anchor") t.targetStart = r;
				else if (r.data === "teleport anchor") {
					t.targetAnchor = r, e._lpa = t.targetAnchor && o(t.targetAnchor);
					break;
				}
			}
			r = o(r);
		}
	}
	function p(e, t) {
		t.anchor = d(o(e), t, s(e), n, r, i, a);
	}
	let m = t.target = cr(t.props, c), h = ir(t.props);
	if (m) {
		let c = m._lpa || m.firstChild;
		t.shapeFlag & 16 && (h ? (p(e, t), f(m, c), t.targetAnchor || mr(m, t, u, l, s(e) === m ? e : null)) : (t.anchor = o(e), f(m, c), t.targetAnchor || mr(m, t, u, l), d(c && o(c), t, m, n, r, i, a))), pr(t, h);
	} else h && t.shapeFlag & 16 && (p(e, t), t.targetStart = e, t.targetAnchor = o(e));
	return t.anchor && o(t.anchor);
}
var fr = lr;
function pr(e, t) {
	let n = e.ctx;
	if (n && n.ut) {
		let r, i;
		for (t ? (r = e.el, i = e.anchor) : (r = e.targetStart, i = e.targetAnchor); r && r !== i;) r.nodeType === 1 && r.setAttribute("data-v-owner", n.uid), r = r.nextSibling;
		n.ut();
	}
}
function mr(e, t, n, r, i = null) {
	let a = t.targetStart = n(""), o = t.targetAnchor = n("");
	return a[nr] = o, e && (r(a, e, i), r(o, e, i)), o;
}
var hr = /* @__PURE__ */ Symbol("_leaveCb");
function gr(e) {
	let t = e[0];
	if (e.length > 1) {
		for (let n of e) if (n.type !== ma) {
			t = n;
			break;
		}
	}
	return t;
}
function _r(e) {
	if (!Dr(e)) return rr(e.type) && e.children ? gr(e.children) : e;
	if (e.component) return e.component.subTree;
	let { shapeFlag: t, children: n } = e;
	if (n) {
		if (t & 16) return n[0];
		if (t & 32 && h(n.default)) return n.default();
	}
}
function vr(e, t) {
	if (e.shapeFlag & 6 && e.component) {
		e.transition = t;
		let n = e.component.subTree;
		vr(rr(n.type) && _r(n) || n, t);
	} else if (e.shapeFlag & 128) {
		let n = e.suspense;
		if (n) {
			let e = n.isHydrating ? n.pendingBranch : n.activeBranch;
			e && vr(e, t.clone(e));
		} else e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback);
	} else if (e.transition = t, e.type === G && d(e.children)) {
		let n = ki(e.children, !1);
		n && vr(n, t);
	}
}
function yr(e) {
	if (e.component) return yr(e.component.subTree);
	if (e.type === G) {
		let t = d(e.children) && ki(e.children, !1);
		return t ? yr(t) : void 0;
	}
	if (e.type !== ma) return e;
}
// @__NO_SIDE_EFFECTS__
function H(e, t) {
	return h(e) ? /* @__PURE__ */ s({ name: e.name }, t, { setup: e }) : e;
}
function br() {
	let e = Va();
	return e ? (e.appContext.config.idPrefix || "v") + "-" + e.ids[0] + e.ids[1]++ : "";
}
function xr(e) {
	e.ids = [
		e.ids[0] + e.ids[2]++ + "-",
		0,
		0
	];
}
function Sr(e, t) {
	let n;
	return !!((n = Object.getOwnPropertyDescriptor(e, t)) && !n.configurable);
}
var Cr = /* @__PURE__ */ new WeakMap();
function wr(e, n, r, a, o = !1) {
	if (d(e)) {
		e.forEach((e, t) => wr(e, n && (d(n) ? n[t] : n), r, a, o));
		return;
	}
	if (Er(a) && !o) {
		a.shapeFlag & 512 && a.type.__asyncResolved && a.component.subTree.component && wr(e, n, r, a.component.subTree);
		return;
	}
	let s = a.shapeFlag & 4 ? to(a.component) : a.el, l = o ? null : s, { i: f, r: p } = e, m = n && n.r, _ = f.refs === t ? f.refs = {} : f.refs, v = f.setupState, y = /* @__PURE__ */ P(v), b = v === t ? i : (e) => !Sr(_, e) && u(y, e), x = (e, t) => !(t && Sr(_, t));
	if (m != null && m !== p) {
		if (Tr(n), g(m)) _[m] = null, b(m) && (v[m] = null);
		else if (/* @__PURE__ */ F(m)) {
			let e = n;
			x(m, e.k) && (m.value = null), e.k && (_[e.k] = null);
		}
	}
	if (h(p)) bn(p, f, 12, [l, _]);
	else {
		let t = g(p), n = /* @__PURE__ */ F(p);
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
					i(), Cr.delete(e);
				};
				t.id = -1, Cr.set(e, t), W(t, r);
			} else Tr(e), i();
		}
	}
}
function Tr(e) {
	let t = Cr.get(e);
	t && (t.flags |= 8, Cr.delete(e));
}
ce().requestIdleCallback, ce().cancelIdleCallback;
var Er = (e) => !!e.type.__asyncLoader, Dr = (e) => e.type.__isKeepAlive;
function Or(e, t) {
	Ar(e, "a", t);
}
function kr(e, t) {
	Ar(e, "da", t);
}
function Ar(e, t, n = Ba) {
	let r = e.__wdc ||= () => {
		let t = n;
		for (; t;) {
			if (t.isDeactivated) return;
			t = t.parent;
		}
		return e();
	};
	if (Mr(t, r, n), n) {
		let e = n.parent;
		for (; e && e.parent;) Dr(e.parent.vnode) && jr(r, t, n, e), e = e.parent;
	}
}
function jr(e, t, n, r) {
	let i = Mr(t, e, r, !0), a = Mr("um", () => c(r[t], i), n);
	a.flags = 16;
}
function Mr(e, t, n = Ba, r = !1) {
	if (n) {
		let i = n[e] || (n[e] = []), a = t.__weh ||= (...r) => {
			Ke();
			let i = Wa(n), a = xn(t, n, e, r);
			return i(), qe(), a;
		};
		return r ? i.unshift(a) : i.push(a), a;
	}
}
var Nr = (e) => (t, n = Ba) => {
	qa && e !== "sp" || Mr(e, (...e) => t(...e), n);
}, Pr = Nr("bm"), Fr = Nr("m"), Ir = Nr("bu"), Lr = Nr("u"), Rr = Nr("bum"), zr = Nr("um"), Br = Nr("sp"), Vr = Nr("rtg"), Hr = Nr("rtc");
function Ur(e, t = Ba) {
	Mr("ec", e, t);
}
var Wr = "components", Gr = /* @__PURE__ */ Symbol.for("v-ndc");
function Kr(e) {
	return g(e) ? qr(Wr, e, !1) || e : e || Gr;
}
function qr(e, t, n = !0, r = !1) {
	let i = z || Ba;
	if (i) {
		let n = i.type;
		if (e === Wr) {
			let e = no(n, !1);
			if (e && (e === t || e === E(t) || e === re(E(t)))) return n;
		}
		let a = Jr(i[e] || n[e], t) || Jr(i.appContext[e], t);
		return !a && r ? n : a;
	}
}
function Jr(e, t) {
	return e && (e[t] || e[E(t)] || e[re(E(t))]);
}
function Yr(e, t, n, r) {
	let i, a = n && n[r], o = d(e);
	if (o || g(e)) {
		let n = o && /* @__PURE__ */ qt(e), r = !1, s = !1;
		n && (r = !/* @__PURE__ */ Yt(e), s = /* @__PURE__ */ Jt(e), e = st(e)), i = Array(e.length);
		for (let n = 0, o = e.length; n < o; n++) i[n] = t(r ? s ? $t(Qt(e[n])) : Qt(e[n]) : e[n], n, void 0, a && a[n]);
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
function Xr(e, t) {
	for (let n = 0; n < t.length; n++) {
		let r = t[n];
		if (d(r)) for (let t = 0; t < r.length; t++) e[r[t].name] = r[t].fn;
		else r && (e[r.name] = r.key ? (...e) => {
			let t = r.fn(...e);
			return t && (t.key = r.key), t;
		} : r.fn);
	}
	return e;
}
function U(e, t, n, r, i, a) {
	if (n ??= {}, z.ce || z.parent && Er(z.parent) && z.parent.ce) {
		let e = a != null && n.key == null ? s({}, n, { key: a }) : n, i = Object.keys(e).length > 0;
		return t !== "default" && (e.name = t), K(), J(G, null, [X("slot", e, r && r())], i ? -2 : 64);
	}
	let o = e[t];
	o && o._c && (o._d = !1);
	let c = ga.length;
	K();
	let l;
	try {
		let i = o && Zr(o(n)), s = n.key || a || i && i.key;
		l = J(G, { key: (s && !_(s) ? s : `_${t}`) + (!i && r ? "_fb" : "") }, i || (r ? r() : []), i && e._ === 1 ? 64 : -2);
	} catch (e) {
		for (let e = ga.length; e > c; e--) va();
		throw e;
	} finally {
		o && o._c && (o._d = !0);
	}
	return !i && l.scopeId && (l.slotScopeIds = [l.scopeId + "-s"]), l;
}
function Zr(e) {
	return e.some((e) => !Sa(e) || !(e.type === ma || e.type === G && !Zr(e.children))) ? e : null;
}
var Qr = (e) => e ? Ka(e) ? to(e) : Qr(e.parent) : null, $r = /* @__PURE__ */ s(/* @__PURE__ */ Object.create(null), {
	$: (e) => e,
	$el: (e) => e.vnode.el,
	$data: (e) => e.data,
	$props: (e) => e.props,
	$attrs: (e) => e.attrs,
	$slots: (e) => e.slots,
	$refs: (e) => e.refs,
	$parent: (e) => Qr(e.parent),
	$root: (e) => Qr(e.root),
	$host: (e) => e.ce,
	$emit: (e) => e.emit,
	$options: (e) => li(e),
	$forceUpdate: (e) => e.f ||= () => {
		Nn(e.update);
	},
	$nextTick: (e) => e.n ||= jn.bind(e.proxy),
	$watch: (e) => $n.bind(e)
}), ei = (e, n) => e !== t && !e.__isScriptSetup && u(e, n), ti = {
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
			else if (ei(i, n)) return s[n] = 1, i[n];
			else if (a !== t && u(a, n)) return s[n] = 2, a[n];
			else if (u(o, n)) return s[n] = 3, o[n];
			else if (r !== t && u(r, n)) return s[n] = 4, r[n];
			else ii && (s[n] = 0);
		}
		let d = $r[n], f, p;
		if (d) return n === "$attrs" && rt(e.attrs, "get", ""), d(e);
		if ((f = c.__cssModules) && (f = f[n])) return f;
		if (r !== t && u(r, n)) return s[n] = 4, r[n];
		if (p = l.config.globalProperties, u(p, n)) return p[n];
	},
	set({ _: e }, n, r) {
		let { data: i, setupState: a, ctx: o } = e;
		return ei(a, n) ? (a[n] = r, !0) : i !== t && u(i, n) ? (i[n] = r, !0) : u(e.props, n) || n[0] === "$" && n.slice(1) in e ? !1 : (o[n] = r, !0);
	},
	has({ _: { data: e, setupState: n, accessCache: r, ctx: i, appContext: a, props: o, type: s } }, c) {
		let l;
		return !!(r[c] || e !== t && c[0] !== "$" && u(e, c) || ei(n, c) || u(o, c) || u(i, c) || u($r, c) || u(a.config.globalProperties, c) || (l = s.__cssModules) && l[c]);
	},
	defineProperty(e, t, n) {
		return n.get == null ? u(n, "value") && this.set(e, t, n.value, null) : e._.accessCache[t] = 0, Reflect.defineProperty(e, t, n);
	}
};
function ni(e) {
	return d(e) ? e.reduce((e, t) => (e[t] = null, e), {}) : e;
}
function ri(e, t) {
	let n = ni(e);
	for (let e in t) {
		if (e.startsWith("__skip")) continue;
		let r = n[e];
		r ? d(r) || h(r) ? r = n[e] = {
			type: r,
			default: t[e]
		} : r.default = t[e] : r === null && (r = n[e] = { default: t[e] }), r && t[`__skip_${e}`] && (r.skipFactory = !0);
	}
	return n;
}
var ii = !0;
function ai(e) {
	let t = li(e), n = e.proxy, i = e.ctx;
	ii = !1, t.beforeCreate && si(t.beforeCreate, e, "bc");
	let { data: a, computed: o, methods: s, watch: c, provide: l, inject: u, created: f, beforeMount: p, mounted: m, beforeUpdate: g, updated: _, activated: y, deactivated: b, beforeDestroy: x, beforeUnmount: S, destroyed: C, unmounted: w, render: T, renderTracked: ee, renderTriggered: te, errorCaptured: E, serverPrefetch: ne, expose: D, inheritAttrs: re, components: O, directives: ie, filters: ae } = t;
	if (u && oi(u, i, null), s) for (let e in s) {
		let t = s[e];
		h(t) && (i[e] = t.bind(n));
	}
	if (a) {
		let t = a.call(n, n);
		v(t) && (e.data = /* @__PURE__ */ Ht(t));
	}
	if (ii = !0, o) for (let e in o) {
		let t = o[e], a = Z({
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
	if (c) for (let e in c) ci(c[e], i, n, e);
	if (l) {
		let e = h(l) ? l.call(n) : l;
		Reflect.ownKeys(e).forEach((t) => {
			Kn(t, e[t]);
		});
	}
	f && si(f, e, "c");
	function k(e, t) {
		d(t) ? t.forEach((t) => e(t.bind(n))) : t && e(t.bind(n));
	}
	if (k(Pr, p), k(Fr, m), k(Ir, g), k(Lr, _), k(Or, y), k(kr, b), k(Ur, E), k(Hr, ee), k(Vr, te), k(Rr, S), k(zr, w), k(Br, ne), d(D)) {
		if (D.length) {
			let t = e.exposed ||= {};
			D.forEach((e) => {
				Object.defineProperty(t, e, {
					get: () => n[e],
					set: (t) => n[e] = t,
					enumerable: !0
				});
			});
		} else e.exposed ||= {};
	}
	T && e.render === r && (e.render = T), re != null && (e.inheritAttrs = re), O && (e.components = O), ie && (e.directives = ie), ne && xr(e);
}
function oi(e, t, n = r) {
	d(e) && (e = mi(e));
	for (let n in e) {
		let r = e[n], i;
		i = v(r) ? "default" in r ? qn(r.from || n, r.default, !0) : qn(r.from || n) : qn(r), /* @__PURE__ */ F(i) ? Object.defineProperty(t, n, {
			enumerable: !0,
			configurable: !0,
			get: () => i.value,
			set: (e) => i.value = e
		}) : t[n] = i;
	}
}
function si(e, t, n) {
	xn(d(e) ? e.map((e) => e.bind(t.proxy)) : e.bind(t.proxy), t, n);
}
function ci(e, t, n, r) {
	let i = r.includes(".") ? er(n, r) : () => n[r];
	if (g(e)) {
		let n = t[e];
		h(n) && V(i, n);
	} else if (h(e)) V(i, e.bind(n));
	else if (v(e)) {
		if (d(e)) e.forEach((e) => ci(e, t, n, r));
		else {
			let r = h(e.handler) ? e.handler.bind(n) : t[e.handler];
			h(r) && V(i, r, e);
		}
	}
}
function li(e) {
	let t = e.type, { mixins: n, extends: r } = t, { mixins: i, optionsCache: a, config: { optionMergeStrategies: o } } = e.appContext, s = a.get(t), c;
	return s ? c = s : !i.length && !n && !r ? c = t : (c = {}, i.length && i.forEach((e) => ui(c, e, o, !0)), ui(c, t, o)), v(t) && a.set(t, c), c;
}
function ui(e, t, n, r = !1) {
	let { mixins: i, extends: a } = t;
	a && ui(e, a, n, !0), i && i.forEach((t) => ui(e, t, n, !0));
	for (let i in t) if (!(r && i === "expose")) {
		let r = di[i] || n && n[i];
		e[i] = r ? r(e[i], t[i]) : t[i];
	}
	return e;
}
var di = {
	data: fi,
	props: _i,
	emits: _i,
	methods: gi,
	computed: gi,
	beforeCreate: hi,
	created: hi,
	beforeMount: hi,
	mounted: hi,
	beforeUpdate: hi,
	updated: hi,
	beforeDestroy: hi,
	beforeUnmount: hi,
	destroyed: hi,
	unmounted: hi,
	activated: hi,
	deactivated: hi,
	errorCaptured: hi,
	serverPrefetch: hi,
	components: gi,
	directives: gi,
	watch: vi,
	provide: fi,
	inject: pi
};
function fi(e, t) {
	return t ? e ? function() {
		return s(h(e) ? e.call(this, this) : e, h(t) ? t.call(this, this) : t);
	} : t : e;
}
function pi(e, t) {
	return gi(mi(e), mi(t));
}
function mi(e) {
	if (d(e)) {
		let t = {};
		for (let n = 0; n < e.length; n++) t[e[n]] = e[n];
		return t;
	}
	return e;
}
function hi(e, t) {
	return e ? [...new Set([].concat(e, t))] : t;
}
function gi(e, t) {
	return e ? s(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function _i(e, t) {
	return e ? d(e) && d(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : s(/* @__PURE__ */ Object.create(null), ni(e), ni(t ?? {})) : t;
}
function vi(e, t) {
	if (!e) return t;
	if (!t) return e;
	let n = s(/* @__PURE__ */ Object.create(null), e);
	for (let r in t) n[r] = hi(e[r], t[r]);
	return n;
}
function yi() {
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
var bi = 0;
function xi(e, t) {
	return function(n, r = null) {
		h(n) || (n = s({}, n)), r != null && !v(r) && (r = null);
		let i = yi(), a = /* @__PURE__ */ new WeakSet(), o = [], c = !1, l = i.app = {
			_uid: bi++,
			_component: n,
			_props: r,
			_container: null,
			_context: i,
			_instance: null,
			version: so,
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
					let u = l._ceVNode || X(n, r);
					return u.appContext = i, s === !0 ? s = "svg" : s === !1 && (s = void 0), o && t ? t(u, a) : e(u, a, s), c = !0, l._container = a, a.__vue_app__ = l, to(u.component);
				}
			},
			onUnmount(e) {
				o.push(e);
			},
			unmount() {
				c && (xn(o, l._instance, 16), e(null, l._container), delete l._container.__vue_app__);
			},
			provide(e, t) {
				return i.provides[e] = t, l;
			},
			runWithContext(e) {
				let t = Si;
				Si = l;
				try {
					return e();
				} finally {
					Si = t;
				}
			}
		};
		return l;
	};
}
var Si = null, Ci = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${E(t)}Modifiers`] || e[`${D(t)}Modifiers`];
function wi(e, n, ...r) {
	if (e.isUnmounted) return;
	let i = e.vnode.props || t, a = r, o = n.startsWith("update:"), s = o && Ci(i, n.slice(7));
	s && (s.trim && (a = r.map((e) => g(e) ? e.trim() : e)), s.number && (a = a.map(oe)));
	let c, l = i[c = O(n)] || i[c = O(E(n))];
	!l && o && (l = i[c = O(D(n))]), l && xn(l, e, 6, a);
	let u = i[c + "Once"];
	if (u) {
		if (!e.emitted) e.emitted = {};
		else if (e.emitted[c]) return;
		e.emitted[c] = !0, xn(u, e, 6, a);
	}
}
var Ti = /* @__PURE__ */ new WeakMap();
function Ei(e, t, n = !1) {
	let r = n ? Ti : t.emitsCache, i = r.get(e);
	if (i !== void 0) return i;
	let a = e.emits, o = {}, c = !1;
	if (!h(e)) {
		let r = (e) => {
			let n = Ei(e, t, !0);
			n && (c = !0, s(o, n));
		};
		!n && t.mixins.length && t.mixins.forEach(r), e.extends && r(e.extends), e.mixins && e.mixins.forEach(r);
	}
	return !a && !c ? (v(e) && r.set(e, null), null) : (d(a) ? a.forEach((e) => o[e] = null) : s(o, a), v(e) && r.set(e, o), o);
}
function Di(e, t) {
	return !e || !a(t) ? !1 : (t = t.slice(2), t = t === "Once" ? t : t.replace(/Once$/, ""), u(e, t[0].toLowerCase() + t.slice(1)) || u(e, D(t)) || u(e, t));
}
function Oi(e) {
	let { type: t, vnode: n, proxy: r, withProxy: i, propsOptions: [a], slots: s, attrs: c, emit: l, render: u, renderCache: d, props: f, data: p, setupState: m, ctx: h, inheritAttrs: g } = e, _ = Un(e), v, y;
	try {
		if (n.shapeFlag & 4) {
			let e = i || r, t = e;
			v = ja(u.call(t, e, d, f, m, p, h)), y = c;
		} else {
			let e = t;
			v = ja(e.length > 1 ? e(f, {
				attrs: c,
				slots: s,
				emit: l
			}) : e(f, null)), y = t.props ? c : Ai(c);
		}
	} catch (t) {
		ga.length = 0, Sn(t, e, 1), v = X(ma);
	}
	let b = v;
	if (y && g !== !1) {
		let e = Object.keys(y), { shapeFlag: t } = b;
		e.length && t & 7 && (a && e.some(o) && (y = ji(y, a)), b = Oa(b, y, !1, !0));
	}
	return n.dirs && (b = Oa(b, null, !1, !0), b.dirs = b.dirs ? b.dirs.concat(n.dirs) : n.dirs), n.transition && vr(rr(b.type) && _r(b) || b, n.transition), v = b, Un(_), v;
}
function ki(e, t = !0) {
	let n;
	for (let t = 0; t < e.length; t++) {
		let r = e[t];
		if (Sa(r)) {
			if (r.type !== ma || r.children === "v-if") {
				if (n) return;
				n = r;
			}
		} else return;
	}
	return n;
}
var Ai = (e) => {
	let t;
	for (let n in e) (n === "class" || n === "style" || a(n)) && ((t ||= {})[n] = e[n]);
	return t;
}, ji = (e, t) => {
	let n = {};
	for (let r in e) o(r) && r.slice(9) in t || (n[r] = e[r]);
	return n;
};
function Mi(e, t, n) {
	let { props: r, children: i, component: a } = e, { props: o, children: s, patchFlag: c } = t, l = a.emitsOptions;
	if (t.dirs || t.transition) return !0;
	if (n && c >= 0) {
		if (c & 1024) return !0;
		if (c & 16) return r ? Ni(r, o, l) : !!o;
		if (c & 8) {
			let e = t.dynamicProps;
			for (let t = 0; t < e.length; t++) {
				let n = e[t];
				if (Pi(o, r, n) && !Di(l, n)) return !0;
			}
		}
	} else return (i || s) && (!s || !s.$stable) ? !0 : r === o ? !1 : r ? !o || Ni(r, o, l) : !!o;
	return !1;
}
function Ni(e, t, n) {
	let r = Object.keys(t);
	if (r.length !== Object.keys(e).length) return !0;
	for (let i = 0; i < r.length; i++) {
		let a = r[i];
		if (!u(e, a) || Pi(t, e, a) && !Di(n, a)) return !0;
	}
	return !1;
}
function Pi(e, t, n) {
	let r = e[n], i = t[n];
	return n === "style" && v(r) && v(i) ? !xe(r, i) : r !== i;
}
function Fi({ vnode: e, parent: t, suspense: n }, r) {
	for (; t;) {
		let n = t.subTree;
		if (n.suspense && n.suspense.activeBranch === e && (n.suspense.vnode.el = n.el = r, e = n), n === e) (e = t.vnode).el = r, t = t.parent;
		else break;
	}
	n && n.activeBranch === e && (n.vnode.el = r);
}
var Ii = {}, Li = () => Object.create(Ii), Ri = (e) => Object.getPrototypeOf(e) === Ii;
function zi(e, t, n, r = !1) {
	let i = {}, a = Li();
	e.propsDefaults = /* @__PURE__ */ Object.create(null), Vi(e, t, i, a);
	for (let t in e.propsOptions[0]) t in i || (i[t] = void 0);
	e.props = n ? r ? i : /* @__PURE__ */ Ut(i) : e.type.props ? i : a, e.attrs = a;
}
function Bi(e, t, n, r) {
	let { props: i, attrs: a, vnode: { patchFlag: o } } = e, s = /* @__PURE__ */ P(i), [c] = e.propsOptions, l = !1;
	if ((r || o > 0) && !(o & 16)) {
		if (o & 8) {
			let n = e.vnode.dynamicProps;
			for (let r = 0; r < n.length; r++) {
				let o = n[r];
				if (Di(e.emitsOptions, o)) continue;
				let d = t[o];
				if (c) {
					if (u(a, o)) d !== a[o] && (a[o] = d, l = !0);
					else {
						let t = E(o);
						i[t] = Hi(c, s, t, d, e, !1);
					}
				} else d !== a[o] && (a[o] = d, l = !0);
			}
		}
	} else {
		Vi(e, t, i, a) && (l = !0);
		let r;
		for (let a in s) t && (u(t, a) || (r = D(a)) !== a && u(t, r)) || (c ? n && (n[a] !== void 0 || n[r] !== void 0) && (i[a] = Hi(c, s, a, void 0, e, !0)) : delete i[a]);
		if (a !== s) for (let e in a) t && u(t, e) || (delete a[e], l = !0);
	}
	l && it(e.attrs, "set", "");
}
function Vi(e, n, r, i) {
	let [a, o] = e.propsOptions, s = !1, c;
	if (n) for (let t in n) {
		if (T(t)) continue;
		let l = n[t], d;
		a && u(a, d = E(t)) ? !o || !o.includes(d) ? r[d] = l : (c ||= {})[d] = l : Di(e.emitsOptions, t) || t in i && l === i[t] || (i[t] = l, s = !0);
	}
	if (o) {
		let n = /* @__PURE__ */ P(r), i = c || t;
		for (let t = 0; t < o.length; t++) {
			let s = o[t];
			r[s] = Hi(a, n, s, i[s], e, !u(i, s));
		}
	}
	return s;
}
function Hi(e, t, n, r, i, a) {
	let o = e[n];
	if (o != null) {
		let e = u(o, "default");
		if (e && r === void 0) {
			let e = o.default;
			if (o.type !== Function && !o.skipFactory && h(e)) {
				let { propsDefaults: a } = i;
				if (n in a) r = a[n];
				else {
					let o = Wa(i);
					r = a[n] = e.call(null, t), o();
				}
			} else r = e;
			i.ce && i.ce._setProp(n, r);
		}
		o[0] && (a && !e ? r = !1 : o[1] && (r === "" || r === D(n)) && (r = !0));
	}
	return r;
}
var Ui = /* @__PURE__ */ new WeakMap();
function Wi(e, r, i = !1) {
	let a = i ? Ui : r.propsCache, o = a.get(e);
	if (o) return o;
	let c = e.props, l = {}, f = [], p = !1;
	if (!h(e)) {
		let t = (e) => {
			p = !0;
			let [t, n] = Wi(e, r, !0);
			s(l, t), n && f.push(...n);
		};
		!i && r.mixins.length && r.mixins.forEach(t), e.extends && t(e.extends), e.mixins && e.mixins.forEach(t);
	}
	if (!c && !p) return v(e) && a.set(e, n), n;
	if (d(c)) for (let e = 0; e < c.length; e++) {
		let n = E(c[e]);
		Gi(n) && (l[n] = t);
	}
	else if (c) for (let e in c) {
		let t = E(e);
		if (Gi(t)) {
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
function Gi(e) {
	return e[0] !== "$" && !T(e);
}
var Ki = (e) => e === "_" || e === "_ctx" || e === "$stable", qi = (e) => d(e) ? e.map(ja) : [ja(e)], Ji = (e, t, n) => {
	if (t._n) return t;
	let r = B((...e) => qi(t(...e)), n);
	return r._c = !1, r;
}, Yi = (e, t, n) => {
	let r = e._ctx;
	for (let n in e) {
		if (Ki(n)) continue;
		let i = e[n];
		if (h(i)) t[n] = Ji(n, i, r);
		else if (i != null) {
			let e = qi(i);
			t[n] = () => e;
		}
	}
}, Xi = (e, t) => {
	let n = qi(t);
	e.slots.default = () => n;
}, Zi = (e, t, n) => {
	for (let r in t) (n || !Ki(r)) && (e[r] = t[r]);
}, Qi = (e, t, n) => {
	let r = e.slots = Li();
	if (e.vnode.shapeFlag & 32) {
		let e = t._;
		e ? (Zi(r, t, n), n && k(r, "_", e, !0)) : Yi(t, r);
	} else t && Xi(e, t);
}, $i = (e, n, r) => {
	let { vnode: i, slots: a } = e, o = !0, s = t;
	if (i.shapeFlag & 32) {
		let e = n._;
		e ? r && e === 1 ? o = !1 : Zi(a, n, r) : (o = !n.$stable, Yi(n, a)), s = n;
	} else n && (Xi(e, n), s = { default: 1 });
	if (o) for (let e in a) !Ki(e) && s[e] == null && delete a[e];
}, W = fa;
function ea(e) {
	return ta(e);
}
function ta(e, i) {
	let a = ce();
	a.__VUE__ = !0;
	let { insert: o, remove: s, patchProp: c, createElement: l, createText: u, createComment: d, setText: f, setElementText: p, parentNode: m, nextSibling: h, setScopeId: g = r, insertStaticContent: _ } = e, v = (e, t, r, i = null, a = null, o = null, s = void 0, c = null, l = !!t.dynamicChildren) => {
		if (e === t) return;
		e && !Ca(e, t) && (i = ve(e), A(e, a, o, !0), e = null), t.patchFlag === -2 && (l = !1, t.dynamicChildren = null), t.dynamicChildren && e && e.dynamicChildren && e.dynamicChildren.hasOnce && (t.dynamicChildren === n && (t.dynamicChildren = []), t.dynamicChildren.hasOnce = !0);
		let { type: u, ref: d, shapeFlag: f } = t;
		switch (u) {
			case pa:
				y(e, t, r, i);
				break;
			case ma:
				b(e, t, r, i);
				break;
			case ha:
				e ?? x(t, r, i, s);
				break;
			case G:
				O(e, t, r, i, a, o, s, c, l);
				break;
			default: f & 1 ? w(e, t, r, i, a, o, s, c, l) : f & 6 ? ie(e, t, r, i, a, o, s, c, l) : (f & 64 || f & 128) && u.process(e, t, r, i, a, o, s, c, l, be);
		}
		d != null && a ? wr(d, e && e.ref, o, t || e, !t) : d == null && e && e.ref != null && wr(e.ref, null, o, e, !0);
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
				n && n._beginPatch(), ne(e, t, i, a, o, s, c);
			} finally {
				n && n._endPatch();
			}
		}
	}, ee = (e, t, n, r, i, a, s, u) => {
		let d, f, { props: m, shapeFlag: h, transition: g, dirs: _ } = e;
		if (d = e.el = l(e.type, a, m && m.is, m), h & 8 ? p(d, e.children) : h & 16 && E(e.children, d, null, r, i, na(e, a), s, u), _ && Gn(e, null, r, "created"), te(d, e, e.scopeId, s, r), m) {
			for (let e in m) e !== "value" && !T(e) && c(d, e, null, m[e], a, r);
			"value" in m && c(d, "value", null, m.value, a), (f = m.onVnodeBeforeMount) && Fa(f, r, e);
		}
		_ && Gn(e, null, r, "beforeMount");
		let v = ia(i, g);
		v ? g.beforeEnter(d) : g && !g.persisted && (d[da] = !0), o(d, t, n), ((f = m && m.onVnodeMounted) || v || _) && W(() => {
			try {
				f && Fa(f, r, e), v && g.enter(d), _ && Gn(e, null, r, "mounted");
			} finally {}
		}, i);
	}, te = (e, t, n, r, i) => {
		if (n && g(e, n), r) for (let t = 0; t < r.length; t++) g(e, r[t]);
		if (i) {
			let n = i.subTree;
			if (t === n || ua(n.type) && (n.ssContent === t || n.ssFallback === t)) {
				let t = i.vnode;
				te(e, t, t.scopeId, t.slotScopeIds, i.parent);
			}
		}
	}, E = (e, t, n, r, i, a, o, s, c = 0) => {
		for (let l = c; l < e.length; l++) {
			let c = e[l] = s ? Ma(e[l]) : ja(e[l]);
			v(null, c, t, n, r, i, a, o, s);
		}
	}, ne = (e, n, r, i, a, o, s) => {
		let l = n.el = e.el, { patchFlag: u, dynamicChildren: d, dirs: f } = n;
		u |= e.patchFlag & 16;
		let m = e.props || t, h = n.props || t, g;
		if (r && ra(r, !1), (g = h.onVnodeBeforeUpdate) && Fa(g, r, n, e), f && Gn(n, e, r, "beforeUpdate"), r && ra(r, !0), d && (!e.dynamicChildren || e.dynamicChildren.length !== d.length) && (u = 0, s = !1, d = null), (m.innerHTML && h.innerHTML == null || m.textContent && h.textContent == null) && p(l, ""), d ? D(e.dynamicChildren, d, l, r, i, na(n, a), o) : s || ue(e, n, l, null, r, i, na(n, a), o, !1), u > 0) {
			if (u & 16) re(l, m, h, r, a);
			else if (u & 2 && m.class !== h.class && c(l, "class", null, h.class, a), u & 4 && c(l, "style", m.style, h.style, a), u & 8) {
				let e = n.dynamicProps;
				for (let t = 0; t < e.length; t++) {
					let n = e[t], i = m[n], o = h[n];
					(o !== i || n === "value") && c(l, n, i, o, a, r);
				}
			}
			u & 1 && e.children !== n.children && p(l, n.children);
		} else !s && d == null && re(l, m, h, r, a);
		((g = h.onVnodeUpdated) || f) && W(() => {
			g && Fa(g, r, n, e), f && Gn(n, e, r, "updated");
		}, i);
	}, D = (e, t, n, r, i, a, o) => {
		for (let s = 0; s < t.length; s++) {
			let c = e[s], l = t[s], u = c.el || la(c), d = u && (c.type === G || !Ca(c, l) || c.shapeFlag & 198) ? m(u) : n;
			v(c, l, d, null, r, i, a, o, !0);
		}
	}, re = (e, n, r, i, a) => {
		if (n !== r) {
			if (n !== t) for (let t in n) !T(t) && !(t in r) && c(e, t, n[t], null, a, i);
			for (let t in r) {
				if (T(t)) continue;
				let o = r[t], s = n[t];
				o !== s && t !== "value" && c(e, t, s, o, a, i);
			}
			"value" in r && c(e, "value", n.value, r.value, a);
		}
	}, O = (e, t, n, r, i, a, s, c, l) => {
		let d = t.el = e ? e.el : u(""), f = t.anchor = e ? e.anchor : u(""), { patchFlag: p, dynamicChildren: m, slotScopeIds: h } = t;
		h && (c = c ? c.concat(h) : h), e == null ? (o(d, n, r), o(f, n, r), E(t.children || [], n, f, i, a, s, c, l)) : p > 0 && p & 64 && m && e.dynamicChildren && e.dynamicChildren.length === m.length ? (D(e.dynamicChildren, m, n, i, a, s, c), (t.key != null || i && t === i.subTree) && aa(e, t, !0)) : ue(e, t, n, f, i, a, s, c, l);
	}, ie = (e, t, n, r, i, a, o, s, c) => {
		t.slotScopeIds = s, e == null ? t.shapeFlag & 512 ? i.ctx.activate(t, n, r, o, c) : k(t, n, r, i, a, o, c) : oe(e, t, c);
	}, k = (e, t, n, r, i, a, o) => {
		let s = e.component = za(e, r, i);
		if (Dr(e) && (s.ctx.renderer = be), Ja(s, !1, o), s.asyncDep) {
			if (i && i.registerDep(s, se, o, a), !e.el) {
				let r = s.subTree = X(ma);
				b(null, r, t, n), e.placeholder = r.el;
			}
		} else se(s, e, t, n, i, a, o);
	}, oe = (e, t, n) => {
		let r = t.component = e.component;
		if (Mi(e, t, n)) {
			if (r.asyncDep && !r.asyncResolved) {
				t.el = e.el, t.placeholder = e.placeholder, le(r, t, n);
				return;
			}
			r.next = t, r.update();
		} else t.el = e.el, t.placeholder = e.placeholder, r.vnode = t;
	}, se = (e, t, n, r, i, a, o) => {
		let s = () => {
			if (e.isMounted) {
				let { next: t, bu: n, u: r, parent: s, vnode: c } = e;
				{
					let n = sa(e);
					if (n) {
						t && (t.el = c.el, le(e, t, o)), n.asyncDep.then(() => {
							let t = () => {
								e.job.flags & 8 || (i && i.pendingBranch ? W(t, i) : l());
							};
							t.flags = 48, W(t, i);
						});
						return;
					}
				}
				let u = t, d;
				ra(e, !1), t ? (t.el = c.el, le(e, t, o)) : t = c, n && ae(n), (d = t.props && t.props.onVnodeBeforeUpdate) && Fa(d, s, t, c), ra(e, !0);
				let f = Oi(e), p = e.subTree;
				e.subTree = f, v(p, f, m(p.el || la(p)), ve(p), e, i, a), t.el = f.el, u === null && Fi(e, f.el), r && W(r, i), (d = t.props && t.props.onVnodeUpdated) && W(() => Fa(d, s, t, c), i);
			} else {
				let o, { el: s, props: c } = t, { bm: l, m: u, parent: d, root: f, type: p } = e, m = Er(t);
				if (ra(e, !1), l && ae(l), !m && (o = c && c.onVnodeBeforeMount) && Fa(o, d, t), ra(e, !0), s && Se) {
					let t = () => {
						e.subTree = Oi(e), Se(s, e.subTree, e, i, null);
					};
					m && p.__asyncHydrate ? p.__asyncHydrate(s, e, t) : t();
				} else {
					f.ce && f.ce._hasShadowRoot() && f.ce._injectChildStyle(p, e.parent ? e.parent.type : void 0);
					let o = e.subTree = Oi(e);
					v(null, o, n, r, e, i, a), t.el = o.el;
				}
				if (u && W(u, i), !m && (o = c && c.onVnodeMounted)) {
					let e = t;
					W(() => Fa(o, d, e), i);
				}
				(t.shapeFlag & 256 || d && Er(d.vnode) && d.vnode.shapeFlag & 256) && e.a && W(e.a, i), e.isMounted = !0, t = n = r = null;
			}
		};
		e.scope.on();
		let c = e.effect = new je(s);
		e.scope.off();
		let l = e.update = c.run.bind(c), u = e.job = c.runIfDirty.bind(c);
		u.i = e, u.id = e.uid, c.scheduler = () => Nn(u), ra(e, !0), l();
	}, le = (e, t, n) => {
		t.component = e;
		let r = e.vnode.props;
		e.vnode = t, e.next = null, Bi(e, t.props, r, n), $i(e, t.children, n), Ke(), In(e), qe();
	}, ue = (e, t, n, r, i, a, o, s, c = !1) => {
		let l = e && e.children, u = e ? e.shapeFlag : 0, d = t.children, { patchFlag: f, shapeFlag: m } = t;
		if (f > 0) {
			if (f & 128) {
				fe(l, d, n, r, i, a, o, s, c);
				return;
			}
			if (f & 256) {
				de(l, d, n, r, i, a, o, s, c);
				return;
			}
		}
		m & 8 ? (u & 16 && _e(l, i, a), d !== l && p(n, d)) : u & 16 ? m & 16 ? fe(l, d, n, r, i, a, o, s, c) : _e(l, i, a, !0) : (u & 8 && p(n, ""), m & 16 && E(d, n, r, i, a, o, s, c));
	}, de = (e, t, r, i, a, o, s, c, l) => {
		e ||= n, t ||= n;
		let u = e.length, d = t.length, f = Math.min(u, d), p = 0;
		for (; p < f; p++) {
			let n = t[p] = l ? Ma(t[p]) : ja(t[p]);
			v(e[p], n, r, null, a, o, s, c, l);
		}
		u > d ? _e(e, a, o, !0, !1, f) : E(t, r, i, a, o, s, c, l, f);
	}, fe = (e, t, r, i, a, o, s, c, l) => {
		let u = 0, d = t.length, f = e.length - 1, p = d - 1;
		for (; u <= f && u <= p;) {
			let n = e[u], i = t[u] = l ? Ma(t[u]) : ja(t[u]);
			if (Ca(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			u++;
		}
		for (; u <= f && u <= p;) {
			let n = e[f], i = t[p] = l ? Ma(t[p]) : ja(t[p]);
			if (Ca(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			f--, p--;
		}
		if (u > f) {
			if (u <= p) {
				let e = p + 1, n = e < d ? t[e].el : i;
				for (; u <= p;) v(null, t[u] = l ? Ma(t[u]) : ja(t[u]), r, n, a, o, s, c, l), u++;
			}
		} else if (u > p) for (; u <= f;) A(e[u], a, o, !0), u++;
		else {
			let m = u, h = u, g = /* @__PURE__ */ new Map();
			for (u = h; u <= p; u++) {
				let e = t[u] = l ? Ma(t[u]) : ja(t[u]);
				e.key != null && g.set(e.key, u);
			}
			let _, y = 0, b = p - h + 1, x = !1, S = 0, C = Array(b);
			for (u = 0; u < b; u++) C[u] = 0;
			for (u = m; u <= f; u++) {
				let n = e[u];
				if (y >= b) {
					A(n, a, o, !0);
					continue;
				}
				let i;
				if (n.key != null) i = g.get(n.key);
				else for (_ = h; _ <= p; _++) if (C[_ - h] === 0 && Ca(n, t[_])) {
					i = _;
					break;
				}
				i === void 0 ? A(n, a, o, !0) : (C[i - h] = u + 1, i >= S ? S = i : x = !0, v(n, t[i], r, null, a, o, s, c, l), y++);
			}
			let w = x ? oa(C) : n;
			for (_ = w.length - 1, u = b - 1; u >= 0; u--) {
				let e = h + u, n = t[e], f = t[e + 1], p = e + 1 < d ? f.el || la(f) : i;
				C[u] === 0 ? v(null, n, r, p, a, o, s, c, l) : x && (_ < 0 || u !== w[_] ? pe(n, r, p, 2) : _--);
			}
		}
	}, pe = (e, t, n, r, i = null) => {
		let { el: a, type: c, transition: l, children: u, shapeFlag: d } = e;
		if (d & 6) pe(e.component.subTree, t, n, r);
		else if (d & 128) e.suspense.move(t, n, r);
		else if (d & 64) c.move(e, t, n, be);
		else if (c === G) {
			o(a, t, n);
			for (let e = 0; e < u.length; e++) pe(u[e], t, n, r);
			o(e.anchor, t, n);
		} else if (c === ha) S(e, t, n);
		else if (r !== 2 && d & 1 && l) {
			if (r === 0) l.persisted && !a[hr] ? o(a, t, n) : (l.beforeEnter(a), o(a, t, n), W(() => l.enter(a), i));
			else {
				let { leave: r, delayLeave: i, afterLeave: c } = l, u = () => {
					e.ctx.isUnmounted ? s(a) : o(a, t, n);
				}, d = () => {
					let e = a._isLeaving || !!a[hr];
					a._isLeaving && a[hr](!0), l.persisted && !e ? u() : r(a, () => {
						u(), c && c();
					});
				};
				i ? i(a, u, d) : d();
			}
		} else o(a, t, n);
	}, A = (e, t, n, r = !1, i = !1) => {
		let { type: a, props: o, ref: s, children: c, dynamicChildren: l, shapeFlag: u, patchFlag: d, dirs: f, cacheIndex: p, memo: m } = e;
		if ((d === -2 || l && l.hasOnce) && (i = !1), s != null && (Ke(), wr(s, null, n, e, !0), qe()), p == null || e.ctx && e.ctx !== t || (t.renderCache[p] = void 0), u & 256 && t.ctx.deactivate(e)) return;
		let h = u & 1 && f, g = !Er(e), _;
		if (g && (_ = o && o.onVnodeBeforeUnmount) && Fa(_, t, e), u & 6) ge(e.component, n, r);
		else {
			if (u & 128) {
				e.suspense.unmount(n, r);
				return;
			}
			h && Gn(e, null, t, "beforeUnmount"), u & 64 ? e.type.remove(e, t, n, be, r) : l && !l.hasOnce && (a !== G || d > 0 && d & 64) ? _e(l, t, n, !1, !0) : (a === G && d & 384 || !i && u & 16) && _e(c, t, n), r && me(e);
		}
		let v = m != null && p == null;
		(g && (_ = o && o.onVnodeUnmounted) || h || v) && W(() => {
			_ && Fa(_, t, e), h && Gn(e, null, t, "unmounted"), v && (e.el = null);
		}, n);
	}, me = (e) => {
		let { type: t, el: n, anchor: r, transition: i } = e, a = t === G;
		if (a && !i) {
			he(n, r);
			return;
		}
		if (t === ha) {
			C(e), i && !i.persisted && i.afterLeave && i.afterLeave();
			return;
		}
		let o = a ? yr(e) : e, c = () => {
			a ? m(n) && he(n, r) : s(n), i && !i.persisted && i.afterLeave && i.afterLeave();
		};
		if (o && o.shapeFlag & 1 && i && !i.persisted) {
			let { leave: e, delayLeave: t } = i, n = o.el, r = () => e(n, c);
			t ? t(n, c, r) : r();
		} else c();
	}, he = (e, t) => {
		let n;
		for (; e !== t;) n = h(e), s(e), e = n;
		s(t);
	}, ge = (e, t, n) => {
		let { bum: r, scope: i, job: a, subTree: o, um: s, m: c, a: l } = e;
		ca(c), ca(l), r && ae(r), i.stop(), a ? (a.flags |= 8, A(o, e, t, n)) : o && (o.transition = e.vnode.transition, A(o, e, t, n)), s && W(s, t);
		let u = () => {
			e.isUnmounted = !0;
		};
		u.flags = 16, W(u, t);
	}, _e = (e, t, n, r = !1, i = !1, a = 0) => {
		for (let o = a; o < e.length; o++) A(e[o], t, n, r, i);
	}, ve = (e) => {
		if (e.shapeFlag & 6) return ve(e.component.subTree);
		if (e.shapeFlag & 128) return e.suspense.next();
		let t = h(e.anchor || e.el), n = t && t[nr];
		return n ? h(n) : t;
	}, ye = (e, t, n) => {
		zn(() => {
			e == null ? t._vnode && A(t._vnode, null, null, !0) : v(t._vnode || null, e, t, null, null, null, n), t._vnode = e;
		}, e && t._vnode ? void 0 : e && e.component ? e.component.uid : Ra());
	}, be = {
		p: v,
		um: A,
		m: pe,
		r: me,
		mt: k,
		mc: E,
		pc: ue,
		pbc: D,
		n: ve,
		o: e
	}, xe, Se;
	return i && ([xe, Se] = i(be)), {
		render: ye,
		hydrate: xe,
		createApp: xi(ye, xe)
	};
}
function na({ type: e, props: t }, n) {
	return n === "svg" && e === "foreignObject" || n === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : n;
}
function ra({ effect: e, job: t }, n) {
	n ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function ia(e, t) {
	return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function aa(e, t, n = !1) {
	let r = e.children, i = t.children;
	if (d(r) && d(i)) for (let e = 0; e < r.length; e++) {
		let t = r[e], a = i[e];
		a.shapeFlag & 1 && !a.dynamicChildren && ((a.patchFlag <= 0 || a.patchFlag === 32) && (a = i[e] = Ma(i[e]), a.el = t.el), !n && a.patchFlag !== -2 && aa(t, a)), a.type === pa && (a.patchFlag === -1 && (a = i[e] = Ma(a)), a.el = t.el), a.type === ma && !a.el && (a.el = t.el);
	}
}
function oa(e) {
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
function sa(e) {
	let t = e.subTree.component;
	if (t) return t.asyncDep && !t.asyncResolved ? t : sa(t);
}
function ca(e) {
	if (e) for (let t = 0; t < e.length; t++) e[t].flags |= 8;
}
function la(e) {
	if (e.placeholder) return e.placeholder;
	let t = e.component;
	if (t) return la(t.subTree);
	let n = e.suspense;
	return n && n.activeBranch ? la(n.activeBranch) : null;
}
var ua = (e) => e.__isSuspense, da = /* @__PURE__ */ Symbol("_deferredEnter");
function fa(e, t) {
	t && t.pendingBranch ? d(e) ? t.effects.push(...e) : t.effects.push(e) : Fn(e);
}
var G = /* @__PURE__ */ Symbol.for("v-fgt"), pa = /* @__PURE__ */ Symbol.for("v-txt"), ma = /* @__PURE__ */ Symbol.for("v-cmt"), ha = /* @__PURE__ */ Symbol.for("v-stc"), ga = [], _a = null;
function K(e = !1) {
	ga.push(_a = e ? null : []);
}
function va() {
	ga.pop(), _a = ga[ga.length - 1] || null;
}
var ya = 1;
function ba(e, t = !1) {
	ya += e, e < 0 && _a && t && (_a.hasOnce = !0);
}
function xa(e) {
	return e.dynamicChildren = ya > 0 ? _a || n : null, va(), ya > 0 && _a && _a.push(e), e;
}
function q(e, t, n, r, i, a) {
	return xa(Y(e, t, n, r, i, a, !0));
}
function J(e, t, n, r, i) {
	return xa(X(e, t, n, r, i, !0));
}
function Sa(e) {
	return e ? e.__v_isVNode === !0 : !1;
}
function Ca(e, t) {
	return e.type === t.type && e.key === t.key;
}
var wa = ({ key: e }) => e ?? null, Ta = ({ ref: e, ref_key: t, ref_for: n }) => (typeof e == "number" && (e = "" + e), e == null ? null : g(e) || /* @__PURE__ */ F(e) || h(e) ? {
	i: z,
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
		key: t && wa(t),
		ref: t && Ta(t),
		scopeId: Hn,
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
		ctx: z
	};
	return s ? (Na(c, n), a & 128 && e.normalize(c)) : n && (c.shapeFlag |= g(n) ? 8 : 16), ya > 0 && !o && _a && (c.patchFlag > 0 || a & 6) && c.patchFlag !== 32 && _a.push(c), c;
}
var X = Ea;
function Ea(e, t = null, n = null, r = 0, i = null, a = !1) {
	if (e && e !== Gr || (e = ma), Sa(e)) {
		let r = Oa(e, t, !0);
		return n && Na(r, n), ya > 0 && !a && _a && (r.shapeFlag & 6 ? _a[_a.indexOf(e)] = r : _a.push(r)), r.patchFlag = -2, r;
	}
	if (ro(e) && (e = e.__vccOpts), t) {
		t = Da(t);
		let { class: e, style: n } = t;
		e && !g(e) && (t.class = A(e)), v(n) && (/* @__PURE__ */ Xt(n) && !d(n) && (n = s({}, n)), t.style = le(n));
	}
	let o = g(e) ? 1 : ua(e) ? 128 : rr(e) ? 64 : v(e) ? 4 : h(e) ? 2 : 0;
	return Y(e, t, n, r, i, o, a, !0);
}
function Da(e) {
	return e ? /* @__PURE__ */ Xt(e) ? s({}, e) : Ri(e) ? s({}, e[Qa] || e) : e : null;
}
function Oa(e, t, n = !1, r = !1) {
	let { props: i, ref: a, patchFlag: o, children: s, transition: c } = e, l = t ? Pa(i || {}, t) : i, u = {
		__v_isVNode: !0,
		__v_skip: !0,
		type: e.type,
		props: l,
		key: l && wa(l),
		ref: t && t.ref ? n && a ? d(a) ? a.concat(Ta(t)) : [a, Ta(t)] : Ta(t) : a,
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
		ssContent: e.ssContent && Oa(e.ssContent),
		ssFallback: e.ssFallback && Oa(e.ssFallback),
		placeholder: e.placeholder,
		el: e.el,
		anchor: e.anchor,
		ctx: e.ctx,
		ce: e.ce,
		cacheIndex: e.cacheIndex
	};
	return c && r && vr(u, c.clone(u)), u;
}
function ka(e = " ", t = 0) {
	return X(pa, null, e, t);
}
function Aa(e = "", t = !1) {
	return t ? (K(), J(ma, null, e)) : X(ma, null, e);
}
function ja(e) {
	return e == null || typeof e == "boolean" ? X(ma) : d(e) ? X(G, null, e.slice()) : Sa(e) ? Ma(e) : X(pa, null, String(e));
}
function Ma(e) {
	return e.el === null && e.patchFlag !== -1 || e.memo ? e : Oa(e);
}
function Na(e, t) {
	let n = 0, { shapeFlag: r } = e;
	if (t == null) t = null;
	else if (d(t)) n = 16;
	else if (typeof t == "object") {
		if (r & 65) {
			let n = t.default;
			n && (n._c && (n._d = !1), Na(e, n()), n._c && (n._d = !0));
			return;
		}
		{
			n = 32;
			let r = t._;
			!r && !Ri(t) ? t._ctx = z : r === 3 && z && (z.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
		}
	} else if (h(t)) {
		if (r & 65) {
			Na(e, { default: t });
			return;
		}
		t = {
			default: t,
			_ctx: z
		}, n = 32;
	} else t = String(t), r & 64 ? (n = 16, t = [ka(t)]) : n = 8;
	e.children = t, e.shapeFlag |= n;
}
function Pa(...e) {
	let t = {};
	for (let n = 0; n < e.length; n++) {
		let r = e[n];
		for (let e in r) if (e === "class") t.class !== r.class && (t.class = A([t.class, r.class]));
		else if (e === "style") t.style = le([t.style, r.style]);
		else if (a(e)) {
			let n = t[e], i = r[e];
			i && n !== i && !(d(n) && n.includes(i)) ? t[e] = n ? [].concat(n, i) : i : i == null && n == null && !o(e) && (t[e] = i);
		} else e !== "" && (t[e] = r[e]);
	}
	return t;
}
function Fa(e, t, n, r = null) {
	xn(e, t, 7, [n, r]);
}
var Ia = /* @__PURE__ */ yi(), La = 0;
function Ra() {
	return La;
}
function za(e, n, r) {
	let i = e.type, a = (n ? n.appContext : e.appContext) || Ia, o = {
		uid: La++,
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
		scope: new Ee(!0),
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
		propsOptions: Wi(i, a),
		emitsOptions: Ei(i, a),
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
	return o.ctx = { _: o }, o.root = n ? n.root : o, o.emit = wi.bind(null, o), e.ce && e.ce(o), o;
}
var Ba = null, Va = () => Ba || z, Ha, Ua;
{
	let e = ce(), t = (t, n) => {
		let r;
		return (r = e[t]) || (r = e[t] = []), r.push(n), (e) => {
			r.length > 1 ? r.forEach((t) => t(e)) : r[0](e);
		};
	};
	Ha = t("__VUE_INSTANCE_SETTERS__", (e) => Ba = e), Ua = t("__VUE_SSR_SETTERS__", (e) => qa = e);
}
var Wa = (e) => {
	let t = Ba;
	return Ha(e), e.scope.on(), () => {
		e.scope.off(), Ha(t);
	};
}, Ga = () => {
	Ba && Ba.scope.off(), Ha(null);
};
function Ka(e) {
	return e.vnode.shapeFlag & 4;
}
var qa = !1;
function Ja(e, t = !1, n = !1) {
	t && Ua(t);
	let { props: r, children: i } = e.vnode, a = Ka(e);
	zi(e, r, a, t), Qi(e, i, n || t);
	let o = a ? Ya(e, t) : void 0;
	return t && Ua(!1), o;
}
function Ya(e, t) {
	let n = e.type;
	e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, ti);
	let { setup: r } = n;
	if (r) {
		Ke();
		let n = e.setupContext = r.length > 1 ? eo(e) : null, i = Wa(e), a = bn(r, e, 0, [e.props, n]), o = y(a);
		if (qe(), i(), (o || e.sp) && !Er(e) && xr(e), o) {
			if (a.then(Ga, Ga), t) return a.then((n) => {
				Ua(!0);
				try {
					Xa(e, n, t);
				} finally {
					Ua(!1);
				}
			}).catch((t) => {
				Sn(t, e, 0, void 0, !0), e.ssrRender = (e, t) => t("<!---->");
			});
			e.asyncDep = a;
		} else Xa(e, a, t);
	} else Za(e, t);
}
function Xa(e, t, n) {
	h(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : v(t) && (e.setupState = on(t)), Za(e, n);
}
function Za(e, t, n) {
	let i = e.type;
	e.render ||= i.render || r;
	{
		let t = Wa(e);
		Ke();
		try {
			ai(e);
		} finally {
			qe(), t();
		}
	}
}
var Qa = /* @__PURE__ */ Symbol(), $a = { get(e, t) {
	return rt(e, "get", ""), t === Qa ? e : e[t];
} };
function eo(e) {
	return {
		attrs: new Proxy(e.attrs, $a),
		slots: e.slots,
		emit: e.emit,
		expose: (t) => {
			e.exposed = t || {};
		}
	};
}
function to(e) {
	return e.exposed ? e.exposeProxy ||= new Proxy(on(Zt(e.exposed)), {
		get(t, n) {
			if (n in t) return t[n];
			if (n in $r) return $r[n](e);
		},
		has(e, t) {
			return t in e || t in $r;
		}
	}) : e.proxy;
}
function no(e, t = !0) {
	return h(e) ? e.displayName || e.name : e.name || t && e.__name;
}
function ro(e) {
	return h(e) && "__vccOpts" in e;
}
var Z = (e, t) => /* @__PURE__ */ pn(e, t, qa);
function io(e, t, n) {
	try {
		ba(-1);
		let r = arguments.length;
		return r === 2 ? v(t) && !d(t) ? Sa(t) ? X(e, null, [t]) : X(e, t) : X(e, null, t) : (r > 3 ? n = Array.prototype.slice.call(arguments, 2) : r === 3 && Sa(n) && (n = [n]), X(e, t, n));
	} finally {
		ba(1);
	}
}
function ao(e, t, n, r) {
	let i = n[r];
	if (i && oo(i, e)) return i;
	let a = t();
	return a.memo = e.slice(), a.cacheIndex = r, n[r] = a;
}
function oo(e, t) {
	let n = e.memo;
	if (n.length != t.length) return !1;
	for (let e = 0; e < n.length; e++) if (ie(n[e], t[e])) return !1;
	return ya > 0 && _a && _a.push(e), !0;
}
var so = "3.5.45", co = void 0, lo = typeof window < "u" && window.trustedTypes;
if (lo) try {
	co = /* @__PURE__ */ lo.createPolicy("vue", { createHTML: (e) => e });
} catch {}
var uo = co ? (e) => co.createHTML(e) : (e) => e, fo = "http://www.w3.org/2000/svg", po = "http://www.w3.org/1998/Math/MathML", mo = typeof document < "u" ? document : null, ho = mo && /* @__PURE__ */ mo.createElement("template"), go = {
	insert: (e, t, n) => {
		t.insertBefore(e, n || null);
	},
	remove: (e) => {
		let t = e.parentNode;
		t && t.removeChild(e);
	},
	createElement: (e, t, n, r) => {
		let i = t === "svg" ? mo.createElementNS(fo, e) : t === "mathml" ? mo.createElementNS(po, e) : n ? mo.createElement(e, { is: n }) : mo.createElement(e);
		return e === "select" && r && r.multiple != null && i.setAttribute("multiple", r.multiple), i;
	},
	createText: (e) => mo.createTextNode(e),
	createComment: (e) => mo.createComment(e),
	setText: (e, t) => {
		e.nodeValue = t;
	},
	setElementText: (e, t) => {
		e.textContent = t;
	},
	parentNode: (e) => e.parentNode,
	nextSibling: (e) => e.nextSibling,
	querySelector: (e) => mo.querySelector(e),
	setScopeId(e, t) {
		e.setAttribute(t, "");
	},
	insertStaticContent(e, t, n, r, i, a) {
		let o = n ? n.previousSibling : t.lastChild;
		if (i && (i === a || i.nextSibling)) for (; t.insertBefore(i.cloneNode(!0), n), i !== a && (i = i.nextSibling););
		else {
			ho.innerHTML = uo(r === "svg" ? `<svg>${e}</svg>` : r === "mathml" ? `<math>${e}</math>` : e);
			let i = ho.content;
			if (r === "svg" || r === "mathml") {
				let e = i.firstChild;
				for (; e.firstChild;) i.appendChild(e.firstChild);
				i.removeChild(e);
			}
			t.insertBefore(i, n);
		}
		return [o ? o.nextSibling : t.firstChild, n ? n.previousSibling : t.lastChild];
	}
}, _o = /* @__PURE__ */ Symbol("_vtc");
function vo(e, t, n) {
	let r = e[_o];
	r && (t = (t ? [t, ...r] : [...r]).join(" ")), t == null ? e.removeAttribute("class") : n ? e.setAttribute("class", t) : e.className = t;
}
var yo = /* @__PURE__ */ Symbol("_vod"), bo = /* @__PURE__ */ Symbol("_vsh"), xo = {
	name: "show",
	beforeMount(e, { value: t }, { transition: n }) {
		e[yo] = e.style.display === "none" ? "" : e.style.display, n && t ? n.beforeEnter(e) : So(e, t);
	},
	mounted(e, { value: t }, { transition: n }) {
		n && t && n.enter(e);
	},
	updated(e, { value: t, oldValue: n }, { transition: r }) {
		!t != !n && (r ? t ? (r.beforeEnter(e), So(e, !0), r.enter(e)) : r.leave(e, () => {
			So(e, !1);
		}) : So(e, t));
	},
	beforeUnmount(e, { value: t }) {
		So(e, t);
	}
};
function So(e, t) {
	e.style.display = t ? e[yo] : "none", e[bo] = !t;
}
var Co = /* @__PURE__ */ Symbol(""), wo = /(?:^|;)\s*display\s*:/;
function To(e, t, n) {
	let r = e.style, i = g(n), a = !1;
	if (n && !i) {
		if (t) {
			if (g(t)) for (let e of t.split(";")) {
				let t = e.slice(0, e.indexOf(":")).trim();
				n[t] ?? Do(r, t, "");
			}
			else for (let e in t) n[e] ?? Do(r, e, "");
		}
		for (let i in n) {
			i === "display" && (a = !0);
			let o = n[i];
			o == null ? Do(r, i, "") : jo(e, i, !g(t) && t ? t[i] : void 0, o) || Do(r, i, o);
		}
	} else if (i) {
		if (t !== n) {
			let e = r[Co];
			e && (n += ";" + e), r.cssText = n, a = wo.test(n);
		}
	} else t && e.removeAttribute("style");
	yo in e && (i && t === n || (e[yo] = a ? r.display : ""), e[bo] && (r.display = "none"));
}
var Eo = /\s*!important$/;
function Do(e, t, n) {
	if (d(n)) n.forEach((n) => Do(e, t, n));
	else if (n ??= "", t.startsWith("--")) Eo.test(n) ? e.setProperty(t, n.replace(Eo, ""), "important") : e.setProperty(t, n);
	else {
		let r = Ao(e, t);
		Eo.test(n) ? e.setProperty(D(r), n.replace(Eo, ""), "important") : e[r] = n;
	}
}
var Oo = [
	"Webkit",
	"Moz",
	"ms"
], ko = {};
function Ao(e, t) {
	let n = ko[t];
	if (n) return n;
	let r = E(t);
	if (r !== "filter" && r in e) return ko[t] = r;
	r = re(r);
	for (let n = 0; n < Oo.length; n++) {
		let i = Oo[n] + r;
		if (i in e) return ko[t] = i;
	}
	return t;
}
function jo(e, t, n, r) {
	return e.tagName === "TEXTAREA" && (t === "width" || t === "height") && g(r) && n === r;
}
var Mo = "http://www.w3.org/1999/xlink";
function No(e, t, n, r, i, a = he(t)) {
	r && t.startsWith("xlink:") ? n == null ? e.removeAttributeNS(Mo, t.slice(6, t.length)) : e.setAttributeNS(Mo, t, n) : n == null || a && !ge(n) ? e.removeAttribute(t) : e.setAttribute(t, a ? "" : _(n) ? String(n) : n);
}
function Po(e, t, n, r, i) {
	if (t === "innerHTML" || t === "textContent") {
		n != null && (e[t] = t === "innerHTML" ? uo(n) : n);
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
		r === "boolean" ? n = ge(n) : n == null && r === "string" ? (n = "", o = !0) : r === "number" && (n = 0, o = !0);
	}
	try {
		e[t] = n;
	} catch {}
	o && e.removeAttribute(i || t);
}
function Fo(e, t, n, r) {
	e.addEventListener(t, n, r);
}
function Io(e, t, n, r) {
	e.removeEventListener(t, n, r);
}
var Lo = /* @__PURE__ */ Symbol("_vei");
function Ro(e, t, n, r, i = null) {
	let a = e[Lo] || (e[Lo] = {}), o = a[t];
	if (r && o) o.value = r;
	else {
		let [n, s] = Vo(t);
		r ? Fo(e, n, a[t] = Go(r, i), s) : o && (Io(e, n, o, s), a[t] = void 0);
	}
}
var zo = /(Once|Passive|Capture)$/, Bo = /^on:?(?:Once|Passive|Capture)$/;
function Vo(e) {
	let t, n;
	for (; (n = e.match(zo)) && !Bo.test(e);) t ||= {}, e = e.slice(0, e.length - n[1].length), t[n[1].toLowerCase()] = !0;
	return [e[2] === ":" ? e.slice(3) : D(e.slice(2)), t];
}
var Ho = 0, Uo = /* @__PURE__ */ Promise.resolve(), Wo = () => Ho ||= (Uo.then(() => Ho = 0), Date.now());
function Go(e, t) {
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
				e && xn(e, t, 5, a);
			}
		} else xn(r, t, 5, [e]);
	};
	return n.value = e, n.attached = Wo(), n;
}
var Ko = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, qo = (e, t, n, r, i, s) => {
	let c = i === "svg";
	t === "class" ? vo(e, r, c) : t === "style" ? To(e, n, r) : a(t) ? o(t) || Ro(e, t, n, r, s) : (t[0] === "." ? (t = t.slice(1), 1) : t[0] === "^" ? (t = t.slice(1), 0) : Jo(e, t, r, c)) ? (Po(e, t, r), e.tagName.includes("-") || t !== "value" && t !== "checked" && t !== "selected" || No(e, t, r, c, s, t !== "value")) : e._isVueCE && (Yo(e, t) || e._def.__asyncLoader && (/[A-Z]/.test(t) || !g(r))) ? Po(e, E(t), r, s, t) : (t === "true-value" ? e._trueValue = r : t === "false-value" && (e._falseValue = r), No(e, t, r, c));
};
function Jo(e, t, n, r) {
	if (r) return !!(t === "innerHTML" || t === "textContent" || t in e && Ko(t) && h(n));
	if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "autocorrect" || t === "sandbox" && e.tagName === "IFRAME" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA") return !1;
	if (t === "width" || t === "height") {
		let t = e.tagName;
		if (t === "IMG" || t === "VIDEO" || t === "CANVAS" || t === "SOURCE") return !1;
	}
	return Ko(t) && g(n) ? !1 : t in e;
}
function Yo(e, t) {
	let n = e._def.props;
	if (!n) return !1;
	let r = E(t);
	return Array.isArray(n) ? n.some((e) => E(e) === r) : Object.keys(n).some((e) => E(e) === r);
}
var Xo = (e) => {
	let t = e.props["onUpdate:modelValue"] || !1;
	return d(t) ? (e) => ae(t, e) : t;
};
function Zo(e) {
	e.target.composing = !0;
}
function Qo(e) {
	let t = e.target;
	t.composing && (t.composing = !1, t.dispatchEvent(new Event("input")));
}
var $o = /* @__PURE__ */ Symbol("_assign"), es = /* @__PURE__ */ Symbol("_initialValue");
function ts(e, t, n) {
	return t && (e = e.trim()), n && (e = oe(e)), e;
}
var ns = {
	created(e, { modifiers: { lazy: t, trim: n, number: r } }, i) {
		e.parentNode && (e.type === "text" ? e[es] = e.defaultValue.replace(/[\r\n]/g, "") : e.type === "textarea" && (e[es] = e.defaultValue.replace(/\r\n?/g, "\n"))), e[$o] = Xo(i);
		let a = r || i.props && i.props.type === "number";
		Fo(e, t ? "change" : "input", (t) => {
			t.target.composing || e[$o](ts(e.value, n, a));
		}), (n || a) && Fo(e, "change", () => {
			e.value = ts(e.value, n, a);
		}), t || (Fo(e, "compositionstart", Zo), Fo(e, "compositionend", Qo), Fo(e, "change", Qo));
	},
	mounted(e, { value: t, modifiers: { trim: n, number: r } }) {
		let i = t ?? "", a = e[es];
		delete e[es], a !== void 0 && (e.type === "text" || e.type === "textarea") && e.value !== a ? e[$o](ts(e.value, n, r)) : e.value = i;
	},
	beforeUpdate(e, { value: t, oldValue: n, modifiers: { lazy: r, trim: i, number: a } }, o) {
		if (e[$o] = Xo(o), e.composing) return;
		let s = (a || e.type === "number") && !/^0\d/.test(e.value) ? oe(e.value) : e.value, c = t ?? "";
		if (s === c) return;
		let l = e.getRootNode();
		(l instanceof Document || l instanceof ShadowRoot) && l.activeElement === e && e.type !== "range" && (r && t === n || i && e.value.trim() === c) || (e.value = c);
	}
}, rs = {
	deep: !0,
	created(e, { value: t, modifiers: { number: n } }, r) {
		e._modelValue = t, Fo(e, "change", () => {
			let t = Array.prototype.filter.call(e.options, (e) => e.selected).map((e) => n ? oe(os(e)) : os(e)), r = e.multiple, i = r ? p(e._modelValue) ? new Set(t) : t : t[0], a = e._pendingValue = [r, r ? d(i) ? t.slice() : t : i];
			try {
				e[$o](i);
			} finally {
				jn(() => {
					e._pendingValue === a && (e._pendingValue = void 0);
				});
			}
		}), e[$o] = Xo(r);
	},
	mounted(e, { value: t, modifiers: { number: n } }) {
		as(e, t, n);
	},
	beforeUpdate(e, { value: t }, n) {
		e._modelValue = t, e[$o] = Xo(n);
	},
	updated(e, { value: t, modifiers: { number: n } }) {
		let r = e._pendingValue;
		e._pendingValue = void 0, r && r[0] === e.multiple && is(t, r[1], r[0]) || as(e, t, n);
	}
};
function is(e, t, n) {
	if (!n || d(e)) return xe(e, t);
	if (p(e)) {
		if (e.size !== t.length) return !1;
		for (let n of t) if (!e.has(n)) return !1;
		return !0;
	}
	return !1;
}
function as(e, t, n = !1) {
	let r = e.multiple, i = d(t);
	if (!r || i || p(t)) {
		for (let a = 0, o = e.options.length; a < o; a++) {
			let o = e.options[a], s = os(o);
			if (r) {
				if (i) {
					let e = typeof s;
					o.selected = e === "string" || e === "number" ? t.some((e) => String(e) === String(s)) : Se(t, s) > -1;
				} else o.selected = t.has(s) || n && typeof s == "string" && t.has(oe(s));
			} else if (xe(os(o), t)) {
				e.selectedIndex !== a && (e.selectedIndex = a);
				return;
			}
		}
		!r && e.selectedIndex !== -1 && (e.selectedIndex = -1);
	}
}
function os(e) {
	return "_value" in e ? e._value : e.value;
}
var ss = [
	"ctrl",
	"shift",
	"alt",
	"meta"
], cs = {
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
	exact: (e, t) => ss.some((n) => e[`${n}Key`] && !t.includes(n))
}, ls = (e, t) => {
	if (!e) return e;
	let n = e._withMods ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n, ...r) => {
		for (let e = 0; e < t.length; e++) {
			let r = cs[t[e]];
			if (r && r(n, t)) return;
		}
		return e(n, ...r);
	}));
}, us = {
	esc: "escape",
	space: " ",
	up: "arrow-up",
	left: "arrow-left",
	right: "arrow-right",
	down: "arrow-down",
	delete: "backspace"
}, ds = (e, t) => {
	let n = e._withKeys ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n) => {
		if (!("key" in n)) return;
		let r = D(n.key);
		if (t.some((e) => e === r || us[e] === r)) return e(n);
	}));
}, fs = /* @__PURE__ */ s({ patchProp: qo }, go), ps;
function ms() {
	return ps ||= ea(fs);
}
var hs = ((...e) => {
	let t = ms().createApp(...e), { mount: n } = t;
	return t.mount = (e) => {
		let r = _s(e);
		if (!r) return;
		let i = t._component;
		h(i) || i.render || i.template || (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
		let a = n(r, !1, gs(r));
		return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), a;
	}, t;
});
function gs(e) {
	if (e instanceof SVGElement) return "svg";
	if (typeof MathMLElement == "function" && e instanceof MathMLElement) return "mathml";
}
function _s(e) {
	return g(e) ? document.querySelector(e) : e;
}
// src/components/ListFilterSummary.vue?vue&type=script&setup=true&lang.ts
var vs = ["aria-label"], ys = [
	"aria-label",
	"title",
	"onClick"
], bs = /*@__PURE__*/ H({
	__name: "ListFilterSummary",
	props: {
		items: {},
		label: { default: "已应用筛选" }
	},
	emits: ["remove"],
	setup(e, { emit: t }) {
		let n = t;
		return (t, r) => e.items.length ? (K(), q("div", {
			key: 0,
			class: "list-filter-summary",
			role: "group",
			"aria-label": e.label
		}, [(K(!0), q(G, null, Yr(e.items, (e) => (K(), q("button", {
			key: e.key,
			type: "button",
			class: "list-filter-chip",
			"aria-label": e.removeLabel,
			title: e.title || e.label,
			onClick: (t) => n("remove", e.key)
		}, [Y("span", null, j(e.label), 1), r[0] ||= Y("span", { "aria-hidden": "true" }, "×", -1)], 8, ys))), 128))], 8, vs)) : Aa("", !0);
	}
}), xs = (e, t) => {
	let n = e.__vccOpts || e;
	for (let [e, r] of t) n[e] = r;
	return n;
}, Ss = /*#__PURE__*/ xs(bs, [["__scopeId", "data-v-9c3f6cac"]]), Cs = ["aria-label", "aria-busy"], ws = { class: "list-pagination__layout" }, Ts = { class: "list-pagination__controls" }, Es = { class: "list-pagination__pages" }, Ds = ["disabled"], Os = [
	"aria-label",
	"aria-current",
	"disabled",
	"onClick"
], ks = {
	key: 1,
	class: "list-pagination__ellipsis",
	"aria-hidden": "true"
}, As = {
	class: "list-pagination__mobile-page",
	"aria-live": "polite"
}, js = ["disabled"], Ms = [
	"aria-invalid",
	"title",
	"disabled"
], Ns = ["disabled"], Ps = { class: "list-pagination__meta" }, Fs = {
	class: "list-pagination__range",
	"aria-live": "polite"
}, Is = { key: 0 }, Ls = { class: "list-pagination__size" }, Rs = ["value", "disabled"], zs = ["value"], Bs = {
	key: 0,
	class: "list-pagination__error",
	role: "alert"
}, Vs = /*#__PURE__*/ xs(/* @__PURE__ */ H({
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
	setup(e, { emit: t }) {
		let n = e, r = t, i = Z(() => Math.max(0, Math.floor(n.total) || 0)), a = Z(() => Math.max(1, Math.floor(n.size) || 1)), o = Z(() => Math.max(1, Math.floor(n.pages || Math.ceil(i.value / a.value)) || 1)), s = Z(() => Math.min(o.value, Math.max(1, Math.floor(n.page) || 1))), c = Z(() => i.value ? Math.min(i.value, (s.value - 1) * a.value + 1) : 0), l = Z(() => Math.min(i.value, s.value * a.value)), u = Z(() => [.../* @__PURE__ */ new Set([...n.pageSizes, a.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), d = /* @__PURE__ */ I(String(s.value)), f = /* @__PURE__ */ I(!1);
		V([s, o], () => {
			d.value = String(s.value), f.value = !1;
		});
		let p = Z(() => {
			let e = o.value;
			return e <= 7 ? Array.from({ length: e }, (e, t) => t + 1) : s.value <= 4 ? [
				1,
				2,
				3,
				4,
				5,
				"after",
				e
			] : s.value >= e - 3 ? [
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
				s.value - 1,
				s.value,
				s.value + 1,
				"after",
				e
			];
		});
		function m(e) {
			if (n.busy || !i.value) return;
			let t = Math.min(o.value, Math.max(1, e));
			d.value = String(t), f.value = !1, t !== s.value && r("update:page", t);
		}
		function h() {
			if (n.busy || !i.value) return;
			let e = Number(d.value.trim());
			!/^\d+$/.test(d.value.trim()) || !Number.isSafeInteger(e) ? f.value = !0 : m(e);
		}
		function g(e) {
			if (n.busy) return;
			let t = Number(e.target.value);
			u.value.includes(t) && t !== a.value && (r("update:page", 1), r("update:size", t));
		}
		return (t, n) => (K(), q("nav", {
			class: "tc-pagination list-pagination",
			"aria-label": e.label,
			"aria-busy": e.busy
		}, [Y("div", ws, [
			Y("div", Ts, [Y("div", Es, [
				Y("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: e.busy || !i.value || s.value <= 1,
					onClick: n[0] ||= (e) => m(s.value - 1)
				}, "上一页", 8, Ds),
				(K(!0), q(G, null, Yr(p.value, (t) => (K(), q(G, { key: t }, [typeof t == "number" ? (K(), q("button", {
					key: 0,
					type: "button",
					class: A(["list-pagination__button list-pagination__number", { "is-current": t === s.value }]),
					"aria-label": `第 ${t} 页`,
					"aria-current": t === s.value ? "page" : void 0,
					disabled: e.busy || !i.value || t === s.value,
					onClick: (e) => m(t)
				}, j(t), 11, Os)) : (K(), q("span", ks, "…"))], 64))), 128)),
				Y("span", As, j(s.value) + " / " + j(o.value), 1),
				Y("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: e.busy || !i.value || s.value >= o.value,
					onClick: n[1] ||= (e) => m(s.value + 1)
				}, "下一页", 8, js)
			]), Y("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: ls(h, ["prevent"])
			}, [Y("label", null, [
				n[4] ||= ka("跳至 ", -1),
				Wn(Y("input", {
					"onUpdate:modelValue": n[2] ||= (e) => d.value = e,
					"aria-label": "跳转页码",
					"aria-invalid": f.value || void 0,
					title: `输入 1 至 ${o.value} 的整数页码`,
					type: "text",
					inputmode: "numeric",
					pattern: "[0-9]*",
					autocomplete: "off",
					disabled: e.busy || !i.value || o.value <= 1,
					onInput: n[3] ||= (e) => f.value = !1
				}, null, 40, Ms), [[ns, d.value]]),
				n[5] ||= ka(" 页", -1)
			]), Y("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: e.busy || !i.value || o.value <= 1
			}, "跳转", 8, Ns)], 32)]),
			Y("div", Ps, [Y("span", Fs, [i.value ? (K(), q("span", Is, j(c.value.toLocaleString()) + "–" + j(l.value.toLocaleString()) + " / ", 1)) : Aa("", !0), ka("共 " + j(i.value.toLocaleString()) + " 条", 1)]), Y("label", Ls, [n[6] ||= ka("每页 ", -1), Y("select", {
				"aria-label": "每页条数",
				value: a.value,
				disabled: e.busy,
				onChange: g
			}, [(K(!0), q(G, null, Yr(u.value, (e) => (K(), q("option", {
				key: e,
				value: e
			}, j(e) + " 条", 9, zs))), 128))], 40, Rs)])]),
			f.value ? (K(), q("span", Bs, "请输入整数页码")) : Aa("", !0)
		])], 8, Cs));
	}
}), [["__scopeId", "data-v-5637de47"]]), Hs = ["title"], Us = {
	key: 0,
	class: "list-cell-secondary"
}, Q = /*#__PURE__*/ xs(/* @__PURE__ */ H({
	__name: "ListCell",
	props: {
		text: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(e) {
		return (t, n) => (K(), q("div", {
			class: A(["list-cell", `list-cell--${e.tone}`]),
			title: e.title ?? [e.text, e.secondary].filter(Boolean).join(" · ")
		}, [Y("div", { class: A(["list-cell-primary", { "list-cell-single": !!e.secondary }]) }, [U(t.$slots, "default", {}, () => [ka(j(e.text), 1)], !0)], 2), e.secondary ? (K(), q("div", Us, j(e.secondary), 1)) : Aa("", !0)], 10, Hs));
	}
}), [["__scopeId", "data-v-5767b82c"]]), Ws = {
	key: 0,
	class: "list-result"
}, Gs = ["title"], Ks = { class: "list-result-details" }, qs = /*#__PURE__*/ xs(/* @__PURE__ */ H({
	__name: "ListResult",
	props: {
		label: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(e) {
		return (t, n) => t.$slots.details ? (K(), q("details", Ws, [Y("summary", { title: e.title }, [X(Q, {
			text: e.label,
			secondary: e.secondary,
			title: e.title,
			tone: e.tone
		}, null, 8, [
			"text",
			"secondary",
			"title",
			"tone"
		])], 8, Gs), Y("div", Ks, [U(t.$slots, "details", {}, void 0, !0)])])) : (K(), J(Q, {
			key: 1,
			text: e.label,
			secondary: e.secondary,
			title: e.title,
			tone: e.tone
		}, null, 8, [
			"text",
			"secondary",
			"title",
			"tone"
		]));
	}
}), [["__scopeId", "data-v-ff8fab81"]]), Js = new Intl.DateTimeFormat("zh-CN", {
	year: "numeric",
	month: "2-digit",
	day: "2-digit",
	hour: "2-digit",
	minute: "2-digit",
	second: "2-digit",
	hour12: !1
});
function Ys(e) {
	if (!e) return "—";
	let t = new Date(String(e));
	return Number.isNaN(t.getTime()) ? `无效时间：${String(e)}` : Js.format(t);
}
function Xs(e) {
	let t = Ys(e), n = /^(\d{4}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})$/.exec(t);
	return n ? {
		text: n[1],
		secondary: n[2]
	} : { text: t };
}
// src/features/proxy/presentation.ts
function $(e, t = "—") {
	return e == null || e === "" ? t : typeof e == "string" || typeof e == "number" ? String(e) : t;
}
function Zs(e) {
	return e && typeof e == "object" && !Array.isArray(e) ? e : {};
}
function Qs(e) {
	return Array.isArray(e) ? e.filter((e) => e && typeof e == "object" && !Array.isArray(e)) : [];
}
function $s(e) {
	if (e == null || e === "") return null;
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? t : null;
}
function ec(e) {
	let t = $s(e);
	if (t == null) return "—";
	if (t < 1024) return `${t} B`;
	let n = [
		"KB",
		"MB",
		"GB",
		"TB"
	], r = t, i = -1;
	for (; r >= 1024 && i < n.length - 1;) r /= 1024, i++;
	return `${r >= 100 ? r.toFixed(0) : r >= 10 ? r.toFixed(1) : r.toFixed(2)} ${n[i]}`;
}
var tc = {
	pending: "待验证",
	fetching: "提取中",
	checking: "复检中",
	ready: "可领取",
	shared: "共享库存",
	shared_pending: "共享线路检测中",
	shared_leased: "共享查询中",
	pool_leased: "任务独占中",
	cooldown: "冷却中",
	quarantine: "故障隔离",
	rotation_wait: "等待轮换",
	retired: "已退役",
	leased: "租约中",
	recent: "最近释放",
	released: "已释放",
	expired: "已过期",
	failed: "失败",
	unavailable: "未采集",
	observed: "可观测",
	complete: "已完成",
	running: "运行中",
	available: "可观测"
};
function nc(e) {
	let t = $(e, "");
	return {
		label: tc[t] || "未知状态",
		title: t || "未提供状态",
		tone: ["failed", "quarantine"].includes(t) ? "danger" : [
			"leased",
			"shared_leased",
			"pool_leased",
			"running"
		].includes(t) ? "active" : [
			"ready",
			"available",
			"observed",
			"released"
		].includes(t) ? "success" : "neutral"
	};
}
var rc = {
	supply_unavailable: {
		label: "补货暂不可用",
		evidence: "补货暂不可用"
	},
	supply_candidates_duplicate: {
		label: "候选已占用",
		evidence: "供应商返回的候选均已占用或处于冷却期"
	},
	transport_failure: {
		label: "线路连接失败",
		evidence: "线路连接失败"
	},
	check_interrupted: {
		label: "复检中断",
		evidence: "复检中断"
	},
	health_check_failed: {
		label: "健康检查失败",
		evidence: "健康检查失败"
	}
};
function ic(e) {
	let t = $(e, ""), n = rc[t];
	return n ? {
		...n,
		evidence: `${n.evidence}（${t}）`
	} : {
		label: t ? "库存异常" : "—",
		evidence: t
	};
}
function ac(e, t) {
	let n = e.registration_job_id != null && e.registration_job_id !== "";
	if ((e.operation_task_id == null || e.operation_task_id === "") && !n) return "未关联任务";
	let r = $(e.operation_task_type, n ? "registration" : "");
	return r ? t?.("task_type", r) || {
		registration: "注册",
		plan_check: "查套餐",
		token_refresh: "刷新 Token",
		live_check: "查活"
	}[r] || r : "未关联任务";
}
function oc(e, t = !1) {
	return [
		["任务", e.operation_task_id],
		["运行", e.operation_run_id],
		...t ? [["注册 job", e.registration_job_id]] : []
	].filter(([, e]) => e != null && e !== "").map(([e, t]) => `${e} #${$(t)}`).join(" · ") || "—";
}
function sc(e, t) {
	return {
		text: ac(e, t),
		secondary: oc(e, e.operation_task_id == null || e.operation_task_id === ""),
		title: [ac(e, t), oc(e, !0)].join(" · ")
	};
}
function cc(e) {
	if (e.availability !== "available" || $s(e.total_bytes) == null) return {
		text: "未采集",
		title: "未采集"
	};
	let t = `${ec(e.upload_bytes)} / ${ec(e.download_bytes)} / ${ec(e.total_bytes)}`, n = e.source === "protocol_http" && ($s(e.byte_unknown_count) || 0) > 0;
	return {
		text: t,
		secondary: n ? "部分字节未知" : void 0,
		title: t + (n ? "（部分字节未知）" : "")
	};
}
function lc(e) {
	let t = Zs(e);
	return [
		"1xx",
		"2xx",
		"3xx",
		"4xx",
		"5xx",
		"unknown"
	].flatMap((e) => {
		let n = t[e];
		return typeof n == "number" && Number.isSafeInteger(n) && n >= 0 ? [`${e}: ${n}`] : [];
	}).join(" / ");
}
function uc(e, t, n) {
	let r = [], i = (e, t) => {
		t != null && t !== "" && r.push({
			label: e,
			value: $(t)
		});
	}, a = (e) => e ? Ys(e) : null;
	if (e === "history") return [
		["租约 ID", t.lease_id],
		["线路来源", t.provider],
		["出口 IP", t.exit_ip],
		["状态", tc[$(t.state)] || t.state],
		["账号", t.account_id],
		["用途", t.purpose],
		["任务", t.operation_task_id],
		["运行", t.operation_run_id],
		["注册 job", t.registration_job_id],
		["重试序号", t.route_attempt_no],
		["获取时间", a(t.acquired_at)],
		["到期时间", a(t.expires_at)],
		["释放时间", a(t.released_at)]
	].forEach(([e, t]) => i(String(e), t)), r;
	[
		["来源", t.source],
		["字节口径", t.source === "protocol_http" ? "HTTP 传输正文；不含请求/响应头、TLS、隧道或代理商账单" : "浏览器可观测字节；不等同代理商账单"],
		["总请求耗时", t.duration_ms == null ? null : `${$(t.duration_ms)} 毫秒`],
		["状态族", lc(t.status_families)],
		["重定向次数", t.redirect_count],
		["解压后响应正文", t.decoded_response_bytes == null ? null : ec(t.decoded_response_bytes)],
		["字节未知请求数", t.byte_unknown_count],
		["注册 Attempt", t.registration_attempt_id],
		["注册 Run", t.registration_run_id],
		["方法", t.method],
		["上传流量", ec(t.upload_bytes)],
		["下载流量", ec(t.download_bytes)],
		["总流量", ec(t.total_bytes)],
		["请求数", t.request_count],
		["失败数", t.failed_count],
		["未完成数", t.unfinished_count],
		["未知数", t.unknown_count],
		["线路租约", t.proxy_lease_id],
		["账号", t.account_id],
		["任务类型", ac(t, n)],
		["注册 job", t.registration_job_id],
		["任务", t.operation_task_id],
		["运行", t.operation_run_id],
		["开始时间", a(t.started_at)],
		["完成时间", a(t.ended_at)]
	].forEach(([e, t]) => i(String(e), t));
	let o = Zs(t.proxy_transport);
	if (o.available) {
		i("代理隧道传输", ec(o.total_bytes)), i("隧道口径", "含 TLS、启动和后台请求；与页面字节重叠，不相加；不含 TCP/IP 开销、缓存匿名填充和代理商账单"), i("连接前已拦截", `${$s(o.blocked_connection_count) ?? 0} 次；没有估算节省字节`);
		for (let e of Qs(o.destinations).slice(0, 50)) i(`目标 ${$(e.host)}:${$(e.port)}`, `${ec(e.total_bytes)} · 连接 ${$(e.connection_count)} · 失败 ${$(e.failed_connection_count)} · 拦截 ${$(e.blocked_connection_count)} · 重试 ${$(e.connect_retry_count)} · 恢复 ${$(e.recovered_connection_count)}`);
	}
	let s = Qs(t.resource_details);
	if (s.length) {
		i("资源明细", `页面可观测口径；以下显示前 ${Math.min(50, s.length)} 项，完整有界明细见任务日志`);
		for (let e of s.slice(0, 50)) i($(e.url), `${$(e.resource_type)} · ${ec(e.total_bytes)}`);
	}
	let c = Zs(t.js_coverage);
	if (c.enabled) {
		i("JS 覆盖率", `target ${$(c.target_count)} · 已采集 ${$(c.collected_target_count)} · 不支持/失败 ${$(c.unsupported_target_count)}；未观察到执行不能证明资源可安全拦截`);
		for (let e of Qs(c.scripts).slice(0, 50)) i($(e.url), `函数 ${$(e.function_count)} · 观察到执行 ${$(e.executed_function_count)}`);
	}
	return r;
}
// src/features/proxy/ProxyPool.vue?vue&type=script&setup=true&lang.ts
var dc = {
	class: "pt-workspace",
	"data-proxy-module-panel": "pool"
}, fc = {
	class: "pt-summary",
	"aria-label": "代理池库存摘要"
}, pc = { "data-proxy-summary": "poolCapacity" }, mc = ["data-proxy-summary"], hc = {
	class: "pt-panel",
	"aria-label": "独立代理池库存"
}, gc = { class: "pt-pool-header" }, _c = {
	key: 0,
	role: "status"
}, vc = {
	key: 1,
	role: "status"
}, yc = {
	key: 0,
	class: "pt-country-summary",
	"aria-label": "分国家代理池统计"
}, bc = { class: "pt-country-cards" }, xc = { key: 1 }, Sc = {
	class: "pt-table-scroll",
	tabindex: "0",
	"aria-label": "代理池库存，可横向滚动"
}, Cc = {
	class: "pt-table pt-pool-table",
	"data-proxy-table": "pool"
}, wc = { key: 0 }, Tc = { colspan: "7" }, Ec = {
	class: "pt-empty",
	role: "status"
}, Dc = /* @__PURE__ */ H({
	__name: "ProxyPool",
	props: {
		pool: {},
		loading: { type: Boolean }
	},
	setup(e) {
		let t = e, n = Z(() => t.pool?.counts ?? {}), r = Z(() => t.pool?.country_pools ?? []), i = Z(() => `${[
			"fetching",
			"checking",
			"ready",
			"leased",
			"shared",
			"rotation_wait"
		].reduce((e, t) => e + ($s(n.value[t]) ?? 0), 0)} / ${t.pool?.policy.max_size || "—"}`), a = [
			[
				"poolReady",
				"ready",
				"可领取"
			],
			[
				"poolFetching",
				"fetching",
				"补货中"
			],
			[
				"poolChecking",
				"checking",
				"复检中"
			],
			[
				"poolLeased",
				"leased",
				"独占使用"
			],
			[
				"poolShared",
				"shared",
				"共享使用"
			]
		], o = [
			["ready", "可领取"],
			["fetching", "补货中"],
			["checking", "复检中"],
			["leased", "独占使用"],
			["shared", "共享使用"],
			["rotation_wait", "等待轮换"],
			["quarantine", "故障隔离"]
		], s = (e) => $s(e) ?? "—";
		return (t, c) => (K(), q("div", dc, [Y("div", fc, [Y("div", null, [c[0] ||= Y("span", null, "代理池容量", -1), Y("strong", pc, j(e.pool ? i.value : "—"), 1)]), (K(), q(G, null, Yr(a, ([t, r, i]) => Y("div", { key: t }, [Y("span", null, j(i), 1), Y("strong", { "data-proxy-summary": t }, j(e.pool ? n.value[r] || 0 : "—"), 9, mc)])), 64))]), Y("section", hc, [
			Y("header", gc, [c[1] ||= Y("h3", null, "代理池库存", -1), e.pool ? (K(), q("span", _c, [
				ka("显示最近 " + j(e.pool.items?.length || 0) + " 条库存 · 最小可用 " + j(e.pool.policy.min_ready || 0) + " · 本进程等待 " + j(e.pool.waiting_local || 0) + " / 维护线程 " + j(e.pool.workers_local || 0), 1),
				r.value.length ? (K(), q(G, { key: 0 }, [ka(" · 分国家 " + j(r.value.length) + " 组", 1)], 64)) : Aa("", !0),
				e.pool.capacity_warning ? (K(), q(G, { key: 1 }, [ka(" · " + j(e.pool.capacity_warning), 1)], 64)) : Aa("", !0)
			])) : (K(), q("span", vc, j(e.loading ? "正在加载代理池库存" : "代理池快照暂不可用"), 1))]),
			r.value.length ? (K(), q("div", yc, [c[2] ||= Y("strong", null, "分国家库存", -1), Y("div", bc, [(K(!0), q(G, null, Yr(r.value, (e, t) => (K(), q("div", {
				key: String(e.provider) + ":" + String(e.region) + ":" + t,
				class: "pt-country-card"
			}, [
				X(Q, {
					text: L($)(e.region || e.country, "未标注"),
					secondary: L($)(e.provider, "未标注")
				}, null, 8, ["text", "secondary"]),
				Y("p", null, j(o.map(([t, n]) => `${n} ${s(L(Zs)(e.counts)[t])}`).join(" · ")), 1),
				Y("small", null, "等待 " + j(s(e.waiting_local)) + " · 目标 " + j(s(e.target_ready)), 1),
				e.last_supply_error ? (K(), J(qs, {
					key: 0,
					label: L(ic)(e.last_supply_error).label,
					title: L(ic)(e.last_supply_error).evidence,
					tone: "warning"
				}, {
					details: B(() => [ka(j(L(ic)(e.last_supply_error).evidence), 1)]),
					_: 2
				}, 1032, ["label", "title"])) : Aa("", !0),
				e.last_supply_error && Number(e.retry_after_seconds) ? (K(), q("small", xc, j(e.retry_after_seconds) + " 秒后补货", 1)) : Aa("", !0)
			]))), 128))])])) : Aa("", !0),
			Y("div", Sc, [Y("table", Cc, [Y("thead", null, [Y("tr", null, [(K(), q(G, null, Yr([
				"资源",
				"状态",
				"来源 / 国家",
				"脱敏端点",
				"脱敏出口",
				"校验 / 到期",
				"最近错误"
			], (e) => Y("th", {
				key: e,
				scope: "col"
			}, j(e), 1)), 64))])]), Y("tbody", null, [(K(!0), q(G, null, Yr(e.pool?.items || [], (e, t) => (K(), q("tr", { key: String(e.resource_id || t) }, [
				Y("td", null, [X(Q, { text: L($)(e.resource_id) }, null, 8, ["text"])]),
				Y("td", null, [X(qs, {
					label: L(nc)(e.state).label,
					title: L(nc)(e.state).title,
					tone: L(nc)(e.state).tone
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				Y("td", null, [X(Q, {
					text: L($)(e.provider),
					secondary: L($)(e.region)
				}, null, 8, ["text", "secondary"])]),
				Y("td", null, [X(Q, { text: L($)(e.endpoint) }, null, 8, ["text"])]),
				Y("td", null, [X(Q, { text: L($)(e.exit_ip) }, null, 8, ["text"])]),
				Y("td", null, [X(Q, {
					text: `校验 ${L(Ys)(e.checked_at)}`,
					secondary: `到期 ${L(Ys)(e.expires_at)}`
				}, null, 8, ["text", "secondary"])]),
				Y("td", null, [X(qs, {
					label: L(ic)(e.last_error_code).label,
					title: L(ic)(e.last_error_code).evidence,
					tone: e.last_error_code ? "warning" : "neutral"
				}, Xr({ _: 2 }, [e.last_error_code ? {
					name: "details",
					fn: B(() => [ka(j(L(ic)(e.last_error_code).evidence), 1)]),
					key: "0"
				} : void 0]), 1032, [
					"label",
					"title",
					"tone"
				])])
			]))), 128)), e.pool?.items?.length ? Aa("", !0) : (K(), q("tr", wc, [Y("td", Tc, [Y("div", Ec, [Y("strong", null, j(e.loading && !e.pool ? "正在加载代理池库存" : e.pool ? "暂无脱敏库存" : "暂时没有代理池快照"), 1), Y("p", null, j(e.pool ? "等待后台补货或复检" : "代理池服务或旧版本接口暂未返回脱敏库存"), 1)])])]))])])])
		])]));
	}
});
// src/shared/useColumnWidths.ts
function Oc(e) {
	let t = /* @__PURE__ */ I([...e.defaults]), n = Z(() => t.value.reduce((e, t) => e + t, 0));
	try {
		let r = JSON.parse(localStorage.getItem(e.storageKey) || "null");
		if (Array.isArray(r) && r.length === e.defaults.length && r.every((e) => typeof e == "number" && Number.isFinite(e) && e > 0)) {
			if (e.totalStorageKey) {
				let i = Number(localStorage.getItem(e.totalStorageKey)), a = Number.isFinite(i) && i > 0 ? i : n.value, o = r.reduce((e, t) => e + t, 0), s = r.map((e) => e / o * a);
				s.every((e) => Number.isFinite(e) && e > 0) && (t.value = s);
			} else r.every((t) => t >= (e.savedMin ?? e.min) && t <= e.max) && (t.value = r);
		}
	} catch {}
	let r;
	function i() {
		try {
			let r = e.totalStorageKey ? t.value.map((t) => Number((t / n.value * 100).toFixed(e.ratioPrecision ?? 4))) : t.value;
			localStorage.setItem(e.storageKey, JSON.stringify(r)), e.totalStorageKey && localStorage.setItem(e.totalStorageKey, String(Number(n.value.toFixed(e.totalPrecision ?? 0)))), e.onPersist?.();
		} catch {}
	}
	function a(n, r) {
		t.value[n] != null && Number.isFinite(r) && (t.value[n] = Math.max(e.min, Math.min(e.max, t.value[n] + r)), i());
	}
	function o(n, a) {
		if (t.value[n] == null) return;
		r?.();
		let o = t.value[n], s = a.clientX, c = (r) => {
			t.value[n] = Math.max(e.min, Math.min(e.max, o + r.clientX - s));
		}, l = () => {
			r?.(), i();
		};
		r = () => {
			document.removeEventListener("pointermove", c), document.removeEventListener("pointerup", l), document.removeEventListener("pointercancel", l), r = void 0;
		}, document.addEventListener("pointermove", c), document.addEventListener("pointerup", l, { once: !0 }), document.addEventListener("pointercancel", l, { once: !0 });
	}
	function s() {
		r?.(), t.value = [...e.defaults];
		try {
			localStorage.removeItem(e.storageKey), e.totalStorageKey && localStorage.removeItem(e.totalStorageKey), e.onReset?.();
		} catch {}
	}
	return ke(() => r?.()), {
		widths: t,
		total: n,
		resize: o,
		resizeWithKeyboard: a,
		resetColumns: s
	};
}
// node_modules/reka-ui/dist/shared/createContext.js
function kc(e, t) {
	let n = typeof e == "string" && !t ? `${e}Context` : t, r = Symbol(n);
	return [(t) => {
		let n = qn(r, t);
		if (n || n === null) return n;
		throw Error(`Injection \`${r.toString()}\` not found. Component must be used within ${Array.isArray(e) ? `one of the following components: ${e.join(", ")}` : `\`${e}\``}`);
	}, (e) => (Kn(r, e), e)];
}
// node_modules/reka-ui/dist/shared/getActiveElement.js
function Ac() {
	let e = document.activeElement;
	if (e == null) return null;
	for (; e != null && e.shadowRoot != null && e.shadowRoot.activeElement != null;) e = e.shadowRoot.activeElement;
	return e;
}
// node_modules/reka-ui/dist/shared/handleAndDispatchCustomEvent.js
function jc(e, t, n) {
	let r = n.originalEvent.target, i = new CustomEvent(e, {
		bubbles: !1,
		cancelable: !0,
		detail: n
	});
	t && r.addEventListener(e, t, { once: !0 }), r.dispatchEvent(i);
}
// node_modules/@vueuse/shared/dist/index.js
function Mc(e, t) {
	return Oe() ? (ke(e, t), !0) : !1;
}
function Nc(e) {
	let t = !1, n, r = De(!0);
	return ((...i) => (t ||= (n = r.run(() => e(...i)), !0), n));
}
var Pc = typeof window < "u" && typeof document < "u";
typeof WorkerGlobalScope < "u" && globalThis instanceof WorkerGlobalScope;
var Fc = (e) => e !== void 0, Ic = Object.prototype.toString, Lc = (e) => Ic.call(e) === "[object Object]", Rc = /* #__PURE__ */ zc();
function zc() {
	var e, t;
	return Pc && !!((e = window) != null && (e = e.navigator) != null && e.userAgent) && (/iP(?:ad|hone|od)/.test(window.navigator.userAgent) || ((t = window) == null || (t = t.navigator) == null ? void 0 : t.maxTouchPoints) > 2 && /iPad|Macintosh/.test(window?.navigator.userAgent));
}
function Bc(e) {
	return Array.isArray(e) ? e : [e];
}
function Vc(e) {
	return e || Va();
}
function Hc(e) {
	if (!Pc) return e;
	let t = 0, n, r, i = () => {
		--t, r && t <= 0 && (r.stop(), n = void 0, r = void 0);
	};
	return ((...a) => (t += 1, r || (r = De(!0), n = r.run(() => e(...a))), Mc(i), n));
}
function Uc(e) {
	return /* @__PURE__ */ Ht(/* @__PURE__ */ F(e) ? new Proxy({}, {
		get(t, n, r) {
			return L(Reflect.get(e.value, n, r));
		},
		set(t, n, r) {
			return /* @__PURE__ */ F(e.value[n]) && !/* @__PURE__ */ F(r) ? e.value[n].value = r : e.value[n] = r, !0;
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
	}) : e);
}
function Wc(e) {
	return Uc(Z(e));
}
function Gc(e, ...t) {
	let n = t.flat(), r = n[0];
	return Wc(() => Object.fromEntries(typeof r == "function" ? Object.entries(/* @__PURE__ */ sn(e)).filter(([e, t]) => !r(R(t), e)) : Object.entries(/* @__PURE__ */ sn(e)).filter((e) => !n.includes(e[0]))));
}
function Kc(e, t) {
	Vc(t) && Rr(e, t);
}
function qc(e, t, n) {
	return V(e, t, {
		...n,
		immediate: !0
	});
}
// node_modules/@vueuse/core/dist/index.js
var Jc = Pc ? window : void 0;
Pc && window.document, Pc && window.navigator, Pc && window.location;
function Yc(e) {
	let t = R(e);
	return t?.$el ?? t;
}
function Xc(...e) {
	let t = (e, t, n, r) => (e.addEventListener(t, n, r), () => e.removeEventListener(t, n, r)), n = Z(() => {
		let t = Bc(R(e[0])).filter((e) => e != null);
		return t.every((e) => typeof e != "string") ? t : void 0;
	});
	return qc(() => [
		n.value?.map((e) => Yc(e)) ?? [Jc].filter((e) => e != null),
		Bc(R(n.value ? e[1] : e[0])),
		Bc(L(n.value ? e[2] : e[1])),
		R(n.value ? e[3] : e[2])
	], ([e, n, r, i], a, o) => {
		if (!e?.length || !n?.length || !r?.length) return;
		let s = Lc(i) ? { ...i } : i, c = e.flatMap((e) => n.flatMap((n) => r.map((r) => t(e, n, r, s))));
		o(() => {
			c.forEach((e) => e());
		});
	}, { flush: "post" });
}
function Zc() {
	let e = /* @__PURE__ */ en(!1), t = Va();
	return t && Fr(() => {
		e.value = !0;
	}, t), e;
}
function Qc(e) {
	return typeof e == "function" ? e : typeof e == "string" ? (t) => t.key === e : Array.isArray(e) ? (t) => e.includes(t.key) : () => !0;
}
function $c(...e) {
	let t, n, r = {};
	e.length === 3 ? (t = e[0], n = e[1], r = e[2]) : e.length === 2 ? typeof e[1] == "object" ? (t = !0, n = e[0], r = e[1]) : (t = e[0], n = e[1]) : (t = !0, n = e[0]);
	let { target: i = Jc, eventName: a = "keydown", passive: o = !1, dedupe: s = !1 } = r, c = Qc(t);
	return Xc(i, a, (e) => {
		e.repeat && R(s) || c(e) && n(e);
	}, o);
}
function el(e) {
	return JSON.parse(JSON.stringify(e));
}
function tl(e, t, n, r = {}) {
	var i, a;
	let { clone: o = !1, passive: s = !1, eventName: c, deep: l = !1, defaultValue: u, shouldEmit: d } = r, f = Va(), p = n || f?.emit || (f == null || (i = f.$emit) == null ? void 0 : i.bind(f)) || (f == null || (a = f.proxy) == null || (a = a.$emit) == null ? void 0 : a.bind(f?.proxy)), m = c;
	t ||= "modelValue", m ||= `update:${t.toString()}`;
	let h = (e) => o ? typeof o == "function" ? o(e) : el(e) : e, g = () => Fc(e[t]) ? h(e[t]) : u, _ = (e) => {
		d ? d(e) && p(m, e) : p(m, e);
	};
	if (s) {
		let n = /* @__PURE__ */ I(g()), r = !1;
		return V(() => e[t], (e) => {
			r || (r = !0, n.value = h(e), jn(() => r = !1));
		}), V(n, (n) => {
			!r && (n !== e[t] || l) && _(n);
		}, { deep: l }), n;
	}
	return Z({
		get() {
			return g();
		},
		set(e) {
			_(e);
		}
	});
}
// node_modules/reka-ui/dist/shared/renderSlotFragments.js
function nl(e) {
	return e ? e.flatMap((e) => e.type === G ? nl(e.children) : [e]) : [];
}
// node_modules/reka-ui/dist/ConfigProvider/ConfigProvider.js
var [rl, il] = /*#__PURE__*/ kc("ConfigProvider"), al = /* @__PURE__ */ new WeakMap();
function ol(e, t) {
	let n = al.get(e);
	n || (n = {
		owners: /* @__PURE__ */ new Set(),
		original: e.body.style.pointerEvents
	}, al.set(e, n)), n.owners.add(t), e.body.style.pointerEvents = "none";
}
function sl(e, t) {
	let n = al.get(e);
	n?.owners.delete(t) && n.owners.size === 0 && (al.delete(e), e.body.style.pointerEvents = n.original);
}
// node_modules/defu/dist/defu.mjs
function cl(e) {
	if (typeof e != "object" || !e) return !1;
	let t = Object.getPrototypeOf(e);
	return t !== null && t !== Object.prototype && Object.getPrototypeOf(t) !== null || Symbol.iterator in e ? !1 : Symbol.toStringTag in e ? Object.prototype.toString.call(e) === "[object Module]" : !0;
}
function ll(e, t, n = ".", r) {
	if (!cl(t)) return ll(e, {}, n, r);
	let i = { ...t };
	for (let t of Object.keys(e)) {
		if (t === "__proto__" || t === "constructor") continue;
		let a = e[t];
		a != null && (r && r(i, t, a, n) || (i[t] = Array.isArray(a) && Array.isArray(i[t]) ? [...a, ...i[t]] : cl(a) && cl(i[t]) ? ll(a, i[t], (n ? `${n}.` : "") + t.toString(), r) : a));
	}
	return i;
}
function ul(e) {
	return (...t) => t.reduce((t, n) => ll(t, n, "", e), {});
}
var dl = ul(), fl = Symbol("useBodyScrollLock"), pl = Hc(() => {
	let e = /* @__PURE__ */ I(/* @__PURE__ */ new Map()), t = /* @__PURE__ */ I(), n = Z(() => {
		for (let t of e.value.values()) if (t) return !0;
		return !1;
	}), r = rl({ scrollBody: /* @__PURE__ */ I(!0) }), i = null, a = () => {
		document.body.style.paddingRight = "", document.body.style.marginRight = "", sl(document, fl), document.documentElement.style.removeProperty("--scrollbar-width"), document.body.style.overflow = t.value ?? "", Rc && i?.(), t.value = void 0;
	};
	return V(n, (e, o) => {
		if (!Pc) return;
		if (!e) {
			o && a();
			return;
		}
		t.value === void 0 && (t.value = document.body.style.overflow);
		let s = window.innerWidth - document.documentElement.clientWidth, c = {
			padding: s,
			margin: 0
		}, l = r.scrollBody?.value ? typeof r.scrollBody.value == "object" ? dl({
			padding: r.scrollBody.value.padding === !0 ? s : r.scrollBody.value.padding,
			margin: r.scrollBody.value.margin === !0 ? s : r.scrollBody.value.margin
		}, c) : c : {
			padding: 0,
			margin: 0
		};
		s > 0 && (document.body.style.paddingRight = typeof l.padding == "number" ? `${l.padding}px` : String(l.padding), document.body.style.marginRight = typeof l.margin == "number" ? `${l.margin}px` : String(l.margin), document.documentElement.style.setProperty("--scrollbar-width", `${s}px`), document.body.style.overflow = "hidden"), Rc && (i = Xc(document, "touchmove", (e) => gl(e), { passive: !1 })), jn(() => {
			n.value && (ol(document, fl), document.body.style.overflow = "hidden");
		});
	}, {
		immediate: !0,
		flush: "sync"
	}), e;
});
function ml(e) {
	let t = Math.random().toString(36).substring(2, 7), n = pl();
	n.value.set(t, e ?? !1);
	let r = Z({
		get: () => n.value.get(t) ?? !1,
		set: (e) => n.value.set(t, e)
	});
	return Kc(() => {
		n.value.delete(t);
	}), r;
}
function hl(e) {
	let t = window.getComputedStyle(e);
	if (t.overflowX === "scroll" || t.overflowY === "scroll" || t.overflowX === "auto" && e.clientWidth < e.scrollWidth || t.overflowY === "auto" && e.clientHeight < e.scrollHeight) return !0;
	{
		let t = e.parentNode;
		return !(t instanceof Element) || t.tagName === "BODY" ? !1 : hl(t);
	}
}
function gl(e) {
	let t = e || window.event, n = t.target;
	return n instanceof Element && hl(n) ? !1 : t.touches.length > 1 || (t.preventDefault && t.cancelable && t.preventDefault(), !1);
}
// node_modules/reka-ui/dist/shared/useDirection.js
function _l(e) {
	let t = rl({ dir: /* @__PURE__ */ I("ltr") });
	return Z(() => e?.value || t.dir?.value || "ltr");
}
// node_modules/reka-ui/dist/shared/useEmitAsProps.js
function vl(e) {
	let t = Va(), n = t?.type.emits, r = {};
	return n?.length || console.warn(`No emitted event found. Please check component: ${t?.type.__name}`), n?.forEach((t) => {
		r[O(E(t))] = (...n) => e(t, ...n);
	}), r;
}
// node_modules/reka-ui/dist/shared/useFocusGuards.js
var yl = 0;
function bl() {
	Xn((e) => {
		if (!Pc) return;
		let t = document.querySelectorAll("[data-reka-focus-guard]");
		document.body.insertAdjacentElement("afterbegin", t[0] ?? xl()), document.body.insertAdjacentElement("beforeend", t[1] ?? xl()), yl++, e(() => {
			yl === 1 && document.querySelectorAll("[data-reka-focus-guard]").forEach((e) => e.remove()), yl--;
		});
	});
}
function xl() {
	let e = document.createElement("span");
	return e.setAttribute("data-reka-focus-guard", ""), e.tabIndex = 0, e.style.outline = "none", e.style.opacity = "0", e.style.position = "fixed", e.style.pointerEvents = "none", e;
}
// node_modules/reka-ui/dist/shared/useForwardExpose.js
function Sl() {
	let e = Va(), t = /* @__PURE__ */ I(), n = Z(() => r());
	Lr(() => {
		n.value !== r() && rn(t);
	});
	function r() {
		return t.value && "$el" in t.value && ["#text", "#comment"].includes(t.value.$el.nodeName) ? t.value.$el.nextElementSibling : Yc(t);
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
function Cl(e) {
	let t = Va(), n = Object.keys(t?.type.props ?? {}).reduce((e, n) => {
		let r = (t?.type.props[n]).default;
		return r !== void 0 && (e[n] = r), e;
	}, {}), r = /* @__PURE__ */ un(e);
	return Z(() => {
		let e = {}, i = t?.vnode.props ?? {};
		return Object.keys(i).forEach((t) => {
			e[E(t)] = i[t];
		}), Object.keys({
			...n,
			...e
		}).reduce((e, t) => (r.value[t] !== void 0 && (e[t] = r.value[t]), e), {});
	});
}
// node_modules/reka-ui/dist/shared/useForwardPropsEmits.js
function wl(e, t) {
	let n = Cl(e), r = t ? vl(t) : {};
	return Z(() => ({
		...n.value,
		...r
	}));
}
// node_modules/aria-hidden/dist/es2015/index.js
var Tl = function(e) {
	return typeof document > "u" ? null : (Array.isArray(e) ? e[0] : e).ownerDocument.body;
}, El = /* @__PURE__ */ new WeakMap(), Dl = /* @__PURE__ */ new WeakMap(), Ol = {}, kl = 0, Al = function(e) {
	return e && (e.host || Al(e.parentNode));
}, jl = function(e, t) {
	return t.map(function(t) {
		if (e.contains(t)) return t;
		var n = Al(t);
		return n && e.contains(n) ? n : (console.error("aria-hidden", t, "in not contained inside", e, ". Doing nothing"), null);
	}).filter(function(e) {
		return !!e;
	});
}, Ml = function(e, t, n, r) {
	var i = jl(t, Array.isArray(e) ? e : [e]);
	Ol[n] || (Ol[n] = /* @__PURE__ */ new WeakMap());
	var a = Ol[n], o = [], s = /* @__PURE__ */ new Set(), c = new Set(i), l = function(e) {
		e && !s.has(e) && (s.add(e), l(e.parentNode));
	};
	i.forEach(l);
	var u = function(e) {
		e && !c.has(e) && Array.prototype.forEach.call(e.children, function(e) {
			if (s.has(e)) u(e);
			else try {
				var t = e.getAttribute(r), i = t !== null && t !== "false", c = (El.get(e) || 0) + 1, l = (a.get(e) || 0) + 1;
				El.set(e, c), a.set(e, l), o.push(e), c === 1 && i && Dl.set(e, !0), l === 1 && e.setAttribute(n, "true"), i || e.setAttribute(r, "true");
			} catch (t) {
				console.error("aria-hidden: cannot operate on ", e, t);
			}
		});
	};
	return u(t), s.clear(), kl++, function() {
		o.forEach(function(e) {
			var t = El.get(e) - 1, i = a.get(e) - 1;
			El.set(e, t), a.set(e, i), t || (Dl.has(e) || e.removeAttribute(r), Dl.delete(e)), i || e.removeAttribute(n);
		}), kl--, kl || (El = /* @__PURE__ */ new WeakMap(), El = /* @__PURE__ */ new WeakMap(), Dl = /* @__PURE__ */ new WeakMap(), Ol = {});
	};
}, Nl = function(e, t, n) {
	n === void 0 && (n = "data-aria-hidden");
	var r = Array.from(Array.isArray(e) ? e : [e]), i = t || Tl(e);
	return i ? (r.push.apply(r, Array.from(i.querySelectorAll("[aria-live], script"))), Ml(r, i, n, "aria-hidden")) : function() {
		return null;
	};
};
// node_modules/reka-ui/dist/shared/useHideOthers.js
function Pl(e) {
	let t;
	V(() => Yc(e), (e) => {
		let n = !1;
		try {
			n = !!e?.closest("[popover]:not(:popover-open)");
		} catch {}
		e && !n ? t = Nl(e) : t && t();
	}), zr(() => {
		t && t();
	});
}
function Fl(e, t = "reka") {
	if (e) return e;
	let n, r = rl({ useId: void 0 });
	return n = r.useId ? r.useId() : br?.(), t ? `${t}-${n}` : n;
}
// node_modules/reka-ui/dist/shared/useSize.js
function Il(e) {
	let t = /* @__PURE__ */ I(), n = Z(() => t.value?.width ?? 0), r = Z(() => t.value?.height ?? 0), i;
	return Fr(() => {
		let n = Yc(e);
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
	}), zr(() => {
		i?.disconnect(), i = void 0;
	}), {
		width: n,
		height: r
	};
}
// node_modules/reka-ui/dist/shared/useStateMachine.js
function Ll(e, t) {
	let n = /* @__PURE__ */ I(e);
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
function Rl(e, t) {
	let n = /* @__PURE__ */ I({}), r = /* @__PURE__ */ I("none"), i = /* @__PURE__ */ I(e), a = e.value ? "mounted" : "unmounted", o, s = t.value?.ownerDocument.defaultView ?? Jc, { state: c, dispatch: l } = Ll(a, {
		mounted: {
			UNMOUNT: "unmounted",
			ANIMATION_OUT: "unmountSuspended"
		},
		unmountSuspended: {
			MOUNT: "mounted",
			ANIMATION_END: "unmounted"
		},
		unmounted: { MOUNT: "mounted" }
	}), u = (e) => {
		if (Pc) {
			let n = new CustomEvent(e, {
				bubbles: !1,
				cancelable: !1
			});
			t.value?.dispatchEvent(n);
		}
	};
	V(e, async (e, i) => {
		let a = i !== e;
		if (await jn(), a) {
			let a = r.value, o = zl(t.value);
			e ? (l("MOUNT"), u("enter"), o === "none" && u("after-enter")) : o === "none" || o === "undefined" || n.value?.display === "none" ? (l("UNMOUNT"), u("leave"), u("after-leave")) : i && a !== o ? (l("ANIMATION_OUT"), u("leave")) : (l("UNMOUNT"), u("after-leave"));
		}
	}, { immediate: !0 });
	let d = (e) => {
		if (e.target !== t.value) return;
		let n = zl(t.value), r = n.includes(CSS.escape(e.animationName)), a = c.value === "mounted" ? "enter" : "leave";
		if (r && (u(`after-${a}`), l("ANIMATION_END"), !i.value)) {
			let e = t.value.style.animationFillMode;
			t.value.style.animationFillMode = "forwards", o = s?.setTimeout(() => {
				t.value?.style.animationFillMode === "forwards" && (t.value.style.animationFillMode = e);
			});
		}
		n === "none" && l("ANIMATION_END");
	}, f = (e) => {
		e.target === t.value && (r.value = zl(t.value));
	}, p = V(t, (e, t) => {
		e ? (n.value = getComputedStyle(e), e.addEventListener("animationstart", f), e.addEventListener("animationcancel", d), e.addEventListener("animationend", d)) : (l("ANIMATION_END"), o !== void 0 && s?.clearTimeout(o), t?.removeEventListener("animationstart", f), t?.removeEventListener("animationcancel", d), t?.removeEventListener("animationend", d));
	}, { immediate: !0 }), m = V(c, () => {
		let e = zl(t.value);
		r.value = c.value === "mounted" ? e : "none";
	});
	return zr(() => {
		p(), m(), t.value && (t.value.removeEventListener("animationstart", f), t.value.removeEventListener("animationcancel", d), t.value.removeEventListener("animationend", d)), o !== void 0 && s?.clearTimeout(o);
	}), { isPresent: Z(() => ["mounted", "unmountSuspended"].includes(c.value)) };
}
function zl(e) {
	return e && getComputedStyle(e).animationName || "none";
}
// node_modules/reka-ui/dist/Presence/Presence.js
var Bl = /*#__PURE__*/ H({
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
		let { present: r, forceMount: i } = /* @__PURE__ */ sn(e), a = /* @__PURE__ */ I(), { isPresent: o } = Rl(r, a);
		n({ present: o });
		let s = t.default({ present: o.value });
		s = nl(s || []);
		let c = Va();
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
		return () => i.value || r.value || o.value ? io(t.default({ present: o.value })[0], { ref: (e) => {
			let t = Yc(e);
			return t?.hasAttribute === void 0 || (t?.hasAttribute("data-reka-popper-content-wrapper") ? a.value = t.firstElementChild : a.value = t), t;
		} }) : null;
	}
}), Vl = /*#__PURE__*/ H({
	name: "PrimitiveSlot",
	inheritAttrs: !1,
	setup(e, { attrs: t, slots: n }) {
		return () => {
			if (!n.default) return null;
			let e = nl(n.default()), r = e.findIndex((e) => e.type !== ma);
			if (r === -1) return e;
			let i = e[r];
			delete i.props?.ref;
			let a = i.props ? Pa(t, i.props) : t, o = Oa({
				...i,
				props: {}
			}, a);
			return e.length === 1 ? o : (e[r] = o, e);
		};
	}
}), Hl = [
	"area",
	"img",
	"input"
], Ul = /*#__PURE__*/ H({
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
		return typeof r == "string" && Hl.includes(r) ? () => io(r, t) : r === "template" ? () => io(Vl, t, { default: n.default }) : () => io(e.as, t, { default: n.default });
	}
}), Wl = "dismissableLayer.pointerDownOutside", Gl = "dismissableLayer.focusOutside";
function Kl(e) {
	if (typeof e != "object" || !e) return !1;
	let t = e.ownerDocument?.defaultView;
	return typeof Element < "u" && e instanceof Element || !!t && e instanceof t.Element;
}
function ql(e, t) {
	if (!Kl(t)) return !1;
	if (e.contains(t)) return !0;
	let n = t.closest("[data-dismissable-layer]"), r = e.dataset.dismissableLayer === "" ? e : e.querySelector("[data-dismissable-layer]"), i = Array.from(e.ownerDocument.querySelectorAll("[data-dismissable-layer]"));
	return !!(n && (r === n || i.indexOf(r) < i.indexOf(n)));
}
function Jl(e, t, n = !0) {
	let r = /* @__PURE__ */ I(!1), i = /* @__PURE__ */ I(() => {});
	return Xn((a) => {
		if (!Pc || !R(n)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			let a = n.target;
			if (t?.value && a) {
				if (ql(t.value, a)) o.removeEventListener("click", i.value), r.value = !1;
				else {
					if (n.target && !r.value) {
						let t = { originalEvent: n };
						function r() {
							jc(Wl, e, t);
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
		R(n) && (r.value = !0);
	} };
}
function Yl(e, t, n = !0) {
	let r = /* @__PURE__ */ I(!1);
	return Xn((i) => {
		if (!Pc || !R(n)) return;
		let a = t?.value?.ownerDocument ?? globalThis.document, o = async (n) => {
			if (!t?.value) return;
			await jn(), await jn();
			let i = n.target;
			t.value && i && !ql(t.value, i) && n.target && !r.value && jc(Gl, e, { originalEvent: n });
		};
		a.addEventListener("focusin", o), i(() => a.removeEventListener("focusin", o));
	}), {
		onFocusCapture: () => {
			R(n) && (r.value = !0);
		},
		onBlurCapture: () => {
			R(n) && (r.value = !1);
		}
	};
}
// node_modules/reka-ui/dist/DismissableLayer/context.js
var Xl = /*#__PURE__*/ Ht({
	layersRoot: /* @__PURE__ */ new Set(),
	layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
	branches: /* @__PURE__ */ new Set()
}), Zl = /* @__PURE__ */ H({
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
		let n = e, r = t, { forwardRef: i, currentElement: a } = Sl(), o = Z(() => a.value?.ownerDocument ?? globalThis.document), s = Z(() => Xl.layersRoot), c = Z(() => a.value ? Array.from(s.value).indexOf(a.value) : -1), l = Z(() => Xl.layersWithOutsidePointerEventsDisabled.size > 0), u = Z(() => {
			let e = Array.from(s.value), [t] = [...Xl.layersWithOutsidePointerEventsDisabled].slice(-1), n = e.indexOf(t);
			return c.value >= n;
		}), d = Jl(async (e) => {
			let t = [...Xl.branches].some((t) => t?.contains(e.target));
			n.present && u.value && !t && (r("pointerDownOutside", e), r("interactOutside", e), await jn(), e.defaultPrevented || r("dismiss"));
		}, a, () => n.present), f = Yl((e) => {
			let t = [...Xl.branches].some((t) => t?.contains(e.target));
			n.present && !t && (r("focusOutside", e), r("interactOutside", e), e.defaultPrevented || r("dismiss"));
		}, a);
		return $c("Escape", (e) => {
			n.present && c.value === s.value.size - 1 && (r("escapeKeyDown", e), e.defaultPrevented || r("dismiss"));
		}, { target: () => o.value?.defaultView ?? globalThis.window }), V([
			a,
			() => n.disableOutsidePointerEvents,
			() => n.present
		], ([e, t, n], r, i) => {
			if (e && n && t) {
				let t = e.ownerDocument;
				ol(t, e), Xl.layersWithOutsidePointerEventsDisabled.add(e), i(() => {
					Xl.layersWithOutsidePointerEventsDisabled.delete(e), sl(t, e);
				});
			}
		}, { immediate: !0 }), V([a, () => n.present], ([e, t], n, r) => {
			e && t && (s.value.add(e), r(() => {
				s.value.delete(e);
			}));
		}, { immediate: !0 }), Xn((e) => {
			e(() => {
				a.value && (s.value.delete(a.value), Xl.layersWithOutsidePointerEventsDisabled.delete(a.value));
			});
		}), (t, n) => (K(), J(L(Ul), {
			ref: L(i),
			"as-child": e.asChild,
			as: e.as,
			"data-dismissable-layer": "",
			style: le({ pointerEvents: l.value ? u.value ? "auto" : "none" : void 0 }),
			onFocusCapture: L(f).onFocusCapture,
			onBlurCapture: L(f).onBlurCapture,
			onPointerdownCapture: L(d).onPointerDownCapture
		}, {
			default: B(() => [U(t.$slots, "default")]),
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
}), Ql = Nc(() => /* @__PURE__ */ I([]));
function $l() {
	let e = Ql();
	return {
		add(t) {
			let n = e.value[0];
			t !== n && n?.pause(), e.value = eu(e.value, t), e.value.unshift(t);
		},
		remove(t) {
			e.value = eu(e.value, t), e.value[0]?.resume();
		}
	};
}
function eu(e, t) {
	let n = [...e], r = n.indexOf(t);
	return r !== -1 && n.splice(r, 1), n;
}
// node_modules/reka-ui/dist/FocusScope/utils.js
var tu = "focusScope.autoFocusOnMount", nu = "focusScope.autoFocusOnUnmount", ru = {
	bubbles: !1,
	cancelable: !0
};
function iu(e, t) {
	let n = t;
	for (; n;) {
		if (e.contains(n)) return !0;
		n = n.getRootNode().host ?? null;
	}
	return !1;
}
function au(e, { select: t = !1 } = {}) {
	let n = Ac();
	for (let r of e) if (du(r, { select: t }), Ac() !== n) return !0;
}
function ou(e) {
	let t = su(e);
	return [cu(t, e), cu(t.reverse(), e)];
}
function su(e) {
	let t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, { acceptNode: (e) => {
		let t = e.tagName === "INPUT" && e.type === "hidden";
		return e.disabled || e.hidden || t ? NodeFilter.FILTER_SKIP : e.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
	} });
	for (; n.nextNode();) t.push(n.currentNode);
	return t.sort((e, t) => e.tabIndex === t.tabIndex ? 0 : e.tabIndex === 0 ? 1 : t.tabIndex === 0 ? -1 : e.tabIndex - t.tabIndex);
}
function cu(e, t) {
	for (let n of e) if (!lu(n, { upTo: t })) return n;
}
function lu(e, { upTo: t }) {
	if (getComputedStyle(e).visibility === "hidden") return !0;
	for (; e;) {
		if (t !== void 0 && e === t) return !1;
		if (getComputedStyle(e).display === "none") return !0;
		e = e.parentElement;
	}
	return !1;
}
function uu(e) {
	return e instanceof HTMLInputElement && "select" in e;
}
function du(e, { select: t = !1 } = {}) {
	if (e && e.focus) {
		let n = Ac();
		e.focus({ preventScroll: !0 }), e !== n && uu(e) && t && e.select();
	}
}
// node_modules/reka-ui/dist/FocusScope/FocusScope.js
var fu = /* @__PURE__ */ H({
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
		let n = e, r = t, { currentRef: i, currentElement: a } = Sl(), o = /* @__PURE__ */ I(null), s = $l(), c = /*#__PURE__*/ Ht({
			paused: !1,
			pause() {
				this.paused = !0;
			},
			resume() {
				this.paused = !1;
			}
		});
		Xn((e) => {
			if (!Pc) return;
			let t = a.value;
			if (!n.trapped) return;
			let r = t?.ownerDocument ?? document, i = t ? t.getRootNode() : r;
			function s(e) {
				if (c.paused || !t) return;
				let n = e.target;
				t.contains(n) ? o.value = n : du(o.value, { select: !0 });
			}
			function l(e) {
				if (c.paused || !t) return;
				let n = e.relatedTarget;
				n !== null && (t.contains(n) || du(o.value, { select: !0 }));
			}
			function u(e) {
				let n = o.value;
				if (n === null || !e.some((e) => e.removedNodes.length > 0)) return;
				let r = Ac();
				r && t.contains(r) || t.contains(n) || du(t);
			}
			function d(e) {
				if (c.paused || !t) return;
				let n = e.composedPath()[0];
				iu(t, n) || du(o.value, { select: !0 });
			}
			i.addEventListener("focusin", s), i.addEventListener("focusout", l), i !== r && r.addEventListener("focusin", d);
			let f = new MutationObserver(u);
			t && f.observe(t, {
				childList: !0,
				subtree: !0
			}), e(() => {
				i.removeEventListener("focusin", s), i.removeEventListener("focusout", l), i !== r && r.removeEventListener("focusin", d), f.disconnect();
			});
		});
		function l(e, t) {
			let n = new CustomEvent(tu, ru), i = (e) => r("mountAutoFocus", e);
			e.addEventListener(tu, i), e.dispatchEvent(n), e.removeEventListener(tu, i), n.defaultPrevented || (au(su(e), { select: !0 }), Ac() === t && du(e));
		}
		Xn(async (e) => {
			let t = a.value;
			if (await jn(), !t) return;
			n.present !== !1 && s.add(c);
			let i = Ac();
			!t.contains(i) && n.present !== !1 && l(t, i), e(() => {
				let e = new CustomEvent(nu, ru), n = (e) => {
					r("unmountAutoFocus", e);
				};
				t.addEventListener(nu, n), t.dispatchEvent(e), t.setAttribute("data-focus-scope-unmounting", ""), setTimeout(() => {
					e.defaultPrevented || du(i ?? document.body, { select: !0 }), t.removeEventListener(nu, n), s.remove(c), t.removeAttribute("data-focus-scope-unmounting");
				}, 0);
			});
		}), V(() => n.present, async (e, t) => {
			if (!Pc) return;
			if (e === !1 && t === !0) {
				s.remove(c);
				return;
			}
			if (e !== !0 || t !== !1) return;
			s.add(c), await jn();
			let n = a.value;
			if (!n) return;
			let r = Ac();
			n.contains(r) || l(n, r);
		});
		function u(e) {
			if (!n.loop && !n.trapped || c.paused) return;
			let t = e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey, r = Ac();
			if (t && r) {
				let t = e.currentTarget, [i, a] = ou(t);
				i && a ? !e.shiftKey && r === a ? (e.preventDefault(), n.loop && du(i, { select: !0 })) : e.shiftKey && r === i && (e.preventDefault(), n.loop && du(a, { select: !0 })) : r === t && e.preventDefault();
			}
		}
		return (t, n) => (K(), J(L(Ul), {
			ref_key: "currentRef",
			ref: i,
			tabindex: "-1",
			"as-child": e.asChild,
			as: e.as,
			onKeydown: u
		}, {
			default: B(() => [U(t.$slots, "default")]),
			_: 3
		}, 8, ["as-child", "as"]));
	}
}), pu = /* @__PURE__ */ H({
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
		let t = e, n = rl({}), r = Z(() => t.to ?? n.teleportTo?.value ?? "body"), i = Zc();
		return (t, n) => L(i) || e.forceMount ? (K(), J(fr, {
			key: 0,
			to: r.value,
			disabled: e.disabled,
			defer: e.defer
		}, [U(t.$slots, "default")], 8, [
			"to",
			"disabled",
			"defer"
		])) : Aa("v-if", !0);
	}
}), [mu, hu] = /*#__PURE__*/ kc("PopperRoot"), gu = /* @__PURE__ */ H({
	inheritAttrs: !1,
	__name: "PopperRoot",
	setup(e) {
		let t = /* @__PURE__ */ I();
		return hu({
			anchor: t,
			onAnchorChange: (e) => t.value = e
		}), (e, t) => U(e.$slots, "default");
	}
}), _u = /* @__PURE__ */ H({
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
		let t = e, { forwardRef: n, currentElement: r } = Sl(), i = mu();
		return Zn(() => {
			i.onAnchorChange(t.reference ?? r.value);
		}), (t, r) => (K(), J(L(Ul), {
			ref: L(n),
			as: e.as,
			"as-child": e.asChild
		}, {
			default: B(() => [U(t.$slots, "default")]),
			_: 3
		}, 8, ["as", "as-child"]));
	}
});
// node_modules/reka-ui/dist/Popper/utils.js
function vu(e) {
	return e !== null;
}
function yu(e) {
	return {
		name: "transformOrigin",
		options: e,
		fn(t) {
			let { placement: n, rects: r, middlewareData: i } = t, a = i.arrow?.centerOffset !== 0, o = a ? 0 : e.arrowWidth, s = a ? 0 : e.arrowHeight, [c, l] = bu(n), u = {
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
function bu(e) {
	let [t, n = "center"] = e.split("-");
	return [t, n];
}
// node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs
var xu = [
	"top",
	"right",
	"bottom",
	"left"
], Su = Math.min, Cu = Math.max, wu = Math.round, Tu = Math.floor, Eu = (e) => ({
	x: e,
	y: e
}), Du = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function Ou(e, t, n) {
	return Cu(e, Su(t, n));
}
function ku(e, t) {
	return typeof e == "function" ? e(t) : e;
}
function Au(e) {
	return e.split("-")[0];
}
function ju(e) {
	return e.split("-")[1];
}
function Mu(e) {
	return e === "x" ? "y" : "x";
}
function Nu(e) {
	return e === "y" ? "height" : "width";
}
function Pu(e) {
	let t = e[0];
	return t === "t" || t === "b" ? "y" : "x";
}
function Fu(e) {
	return Mu(Pu(e));
}
function Iu(e, t, n) {
	n === void 0 && (n = !1);
	let r = ju(e), i = Fu(e), a = Nu(i), o = i === "x" ? r === (n ? "end" : "start") ? "right" : "left" : r === "start" ? "bottom" : "top";
	return t.reference[a] > t.floating[a] && (o = Gu(o)), [o, Gu(o)];
}
function Lu(e) {
	let t = Gu(e);
	return [
		Ru(e),
		t,
		Ru(t)
	];
}
function Ru(e) {
	return e.includes("start") ? e.replace("start", "end") : e.replace("end", "start");
}
var zu = ["left", "right"], Bu = ["right", "left"], Vu = ["top", "bottom"], Hu = ["bottom", "top"];
function Uu(e, t, n) {
	switch (e) {
		case "top":
		case "bottom": return n ? t ? Bu : zu : t ? zu : Bu;
		case "left":
		case "right": return t ? Vu : Hu;
		default: return [];
	}
}
function Wu(e, t, n, r) {
	let i = ju(e), a = Uu(Au(e), n === "start", r);
	return i && (a = a.map((e) => e + "-" + i), t && (a = a.concat(a.map(Ru)))), a;
}
function Gu(e) {
	let t = Au(e);
	return Du[t] + e.slice(t.length);
}
function Ku(e) {
	return {
		top: e.top ?? 0,
		right: e.right ?? 0,
		bottom: e.bottom ?? 0,
		left: e.left ?? 0
	};
}
function qu(e) {
	return typeof e == "number" ? {
		top: e,
		right: e,
		bottom: e,
		left: e
	} : Ku(e);
}
function Ju(e) {
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
function Yu(e, t, n) {
	let { reference: r, floating: i } = e, a = Pu(t), o = Fu(t), s = Nu(o), c = Au(t), l = a === "y", u = r.x + r.width / 2 - i.width / 2, d = r.y + r.height / 2 - i.height / 2, f = r[s] / 2 - i[s] / 2, p;
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
	let m = ju(t);
	return m && (p[o] += f * (m === "end" ? 1 : -1) * (n && l ? -1 : 1)), p;
}
async function Xu(e, t) {
	t === void 0 && (t = {});
	let { x: n, y: r, platform: i, rects: a, elements: o, strategy: s } = e, { boundary: c = "clippingAncestors", rootBoundary: l = "viewport", elementContext: u = "floating", altBoundary: d = !1, padding: f = 0 } = ku(t, e), p = qu(f), m = o[d ? u === "floating" ? "reference" : "floating" : u], h = Ju(await i.getClippingRect({
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
	}, y = Ju(i.convertOffsetParentRelativeRectToViewportRelativeRect ? await i.convertOffsetParentRelativeRectToViewportRelativeRect({
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
var Zu = 50, Qu = async (e, t, n) => {
	let { placement: r = "bottom", strategy: i = "absolute", middleware: a = [], platform: o } = n, s = o.detectOverflow ? o : {
		...o,
		detectOverflow: Xu
	}, c = await (o.isRTL == null ? void 0 : o.isRTL(t)), l = await o.getElementRects({
		reference: e,
		floating: t,
		strategy: i
	}), { x: u, y: d } = Yu(l, r, c), f = r, p = 0, m = {};
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
		}, x && p < Zu && (p++, typeof x == "object" && (x.placement && (f = x.placement), x.rects && (l = x.rects === !0 ? await o.getElementRects({
			reference: e,
			floating: t,
			strategy: i
		}) : x.rects), {x: u, y: d} = Yu(l, f, c)), n = -1);
	}
	return {
		x: u,
		y: d,
		placement: f,
		strategy: i,
		middlewareData: m
	};
}, $u = (e) => ({
	name: "arrow",
	options: e,
	async fn(t) {
		let { x: n, y: r, placement: i, rects: a, platform: o, elements: s, middlewareData: c } = t, { element: l, padding: u = 0 } = ku(e, t) || {};
		if (l == null) return {};
		let d = qu(u), f = {
			x: n,
			y: r
		}, p = Fu(i), m = Nu(p), h = await o.getDimensions(l), g = p === "y", _ = g ? "top" : "left", v = g ? "bottom" : "right", y = g ? "clientHeight" : "clientWidth", b = a.reference[m] + a.reference[p] - f[p] - a.floating[m], x = f[p] - a.reference[p], S = await (o.getOffsetParent == null ? void 0 : o.getOffsetParent(l)), C = S ? S[y] : 0;
		C && await (o.isElement == null ? void 0 : o.isElement(S)) || (C = s.floating[y] || a.floating[m]);
		let w = b / 2 - x / 2, T = C / 2 - h[m] / 2 - 1, ee = Su(d[_], T), te = Su(d[v], T), E = C - h[m] - te, ne = C / 2 - h[m] / 2 + w, D = Ou(ee, ne, E), re = !c.arrow && ju(i) != null && ne !== D && a.reference[m] / 2 - (ne < ee ? ee : te) - h[m] / 2 < 0, O = re ? ne < ee ? ne - ee : ne - E : 0;
		return {
			[p]: f[p] + O,
			data: {
				[p]: D,
				centerOffset: ne - D - O,
				...re && { alignmentOffset: O }
			},
			reset: re
		};
	}
}), ed = function(e) {
	return e === void 0 && (e = {}), {
		name: "flip",
		options: e,
		async fn(t) {
			var n;
			let { placement: r, middlewareData: i, rects: a, initialPlacement: o, platform: s, elements: c } = t, { mainAxis: l = !0, crossAxis: u = !0, fallbackPlacements: d, fallbackStrategy: f = "bestFit", fallbackAxisSideDirection: p = "none", flipAlignment: m = !0, ...h } = ku(e, t);
			if ((n = i.arrow) != null && n.alignmentOffset) return {};
			let g = Au(r), _ = Pu(o), v = Au(o) === o, y = await (s.isRTL == null ? void 0 : s.isRTL(c.floating)), b = d || (v || !m ? [Gu(o)] : Lu(o)), x = p !== "none";
			!d && x && b.push(...Wu(o, m, p, y));
			let S = [o, ...b], C = await s.detectOverflow(t, h), w = [], T = i.flip?.overflows || [];
			if (l && w.push(C[g]), u) {
				let e = Iu(r, a, y);
				w.push(C[e[0]], C[e[1]]);
			}
			if (T = [...T, {
				placement: r,
				overflows: w
			}], !w.every((e) => e <= 0)) {
				let e = (i.flip?.index || 0) + 1, t = S[e];
				if (t && (u !== "alignment" || _ === Pu(t) || T.every((e) => Pu(e.placement) !== _ || e.overflows[0] > 0))) return {
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
								let t = Pu(e.placement);
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
function td(e, t) {
	return {
		top: e.top - t.height,
		right: e.right - t.width,
		bottom: e.bottom - t.height,
		left: e.left - t.width
	};
}
function nd(e) {
	return xu.some((t) => e[t] >= 0);
}
var rd = function(e) {
	return e === void 0 && (e = {}), {
		name: "hide",
		options: e,
		async fn(t) {
			let { rects: n, platform: r } = t, { strategy: i = "referenceHidden", ...a } = ku(e, t);
			switch (i) {
				case "referenceHidden": {
					let e = td(await r.detectOverflow(t, {
						...a,
						elementContext: "reference"
					}), n.reference);
					return { data: {
						referenceHiddenOffsets: e,
						referenceHidden: nd(e)
					} };
				}
				case "escaped": {
					let e = td(await r.detectOverflow(t, {
						...a,
						altBoundary: !0
					}), n.floating);
					return { data: {
						escapedOffsets: e,
						escaped: nd(e)
					} };
				}
				default: return {};
			}
		}
	};
}, id = /*#__PURE__*/ new Set(["left", "top"]);
async function ad(e, t) {
	let { placement: n, platform: r, elements: i } = e, a = await (r.isRTL == null ? void 0 : r.isRTL(i.floating)), o = Au(n), s = ju(n), c = Pu(n) === "y", l = id.has(o) ? -1 : 1, u = a && c ? -1 : 1, d = ku(t, e), { mainAxis: f, crossAxis: p, alignmentAxis: m } = typeof d == "number" ? {
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
var od = function(e) {
	return e === void 0 && (e = 0), {
		name: "offset",
		options: e,
		async fn(t) {
			var n;
			let { x: r, y: i, placement: a, middlewareData: o } = t, s = await ad(t, e);
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
}, sd = function(e) {
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
			} }, ...l } = ku(e, t), u = {
				x: n,
				y: r
			}, d = await a.detectOverflow(t, l), f = Pu(i), p = Mu(f), m = u[p], h = u[f], g = (e, t) => Ou(t + d[e === "y" ? "top" : "left"], t, t - d[e === "y" ? "bottom" : "right"]);
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
}, cd = function(e) {
	return e === void 0 && (e = {}), {
		options: e,
		fn(t) {
			let { x: n, y: r, placement: i, rects: a, middlewareData: o } = t, { offset: s = 0, mainAxis: c = !0, crossAxis: l = !0 } = ku(e, t), u = {
				x: n,
				y: r
			}, d = Pu(i), f = Mu(d), p = u[f], m = u[d], h = ku(s, t), g = typeof h == "number" ? {
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
				let e = f === "y" ? "width" : "height", t = id.has(Au(i)), n = a.reference[d] - a.floating[e] + (t && o.offset?.[d] || 0) + (t ? 0 : g.crossAxis), r = a.reference[d] + a.reference[e] + (t ? 0 : o.offset?.[d] || 0) - (t ? g.crossAxis : 0);
				m < n ? m = n : m > r && (m = r);
			}
			return {
				[f]: p,
				[d]: m
			};
		}
	};
}, ld = function(e) {
	return e === void 0 && (e = {}), {
		name: "size",
		options: e,
		async fn(t) {
			let { placement: n, rects: r, platform: i, elements: a } = t, { apply: o = () => {}, ...s } = ku(e, t), c = await i.detectOverflow(t, s), l = Au(n), u = ju(n), d = Pu(n) === "y", { width: f, height: p } = r.floating, m, h;
			l === "top" || l === "bottom" ? (m = l, h = u === (await (i.isRTL == null ? void 0 : i.isRTL(a.floating)) ? "start" : "end") ? "left" : "right") : (h = l, m = u === "end" ? "top" : "bottom");
			let g = p - c.top - c.bottom, _ = f - c.left - c.right, v = Su(p - c[m], g), y = Su(f - c[h], _), b = t.middlewareData.shift, x = !b, S = v, C = y;
			b != null && b.enabled.x && (C = _), b != null && b.enabled.y && (S = g), x && !u && (d ? C = f - 2 * Cu(c.left, c.right) : S = p - 2 * Cu(c.top, c.bottom)), await o({
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
function ud() {
	return typeof window < "u";
}
function dd(e) {
	return md(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function fd(e) {
	var t;
	return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function pd(e) {
	return ((md(e) ? e.ownerDocument : e.document) || window.document)?.documentElement;
}
function md(e) {
	return ud() ? e instanceof Node || e instanceof fd(e).Node : !1;
}
function hd(e) {
	return ud() ? e instanceof Element || e instanceof fd(e).Element : !1;
}
function gd(e) {
	return ud() ? e instanceof HTMLElement || e instanceof fd(e).HTMLElement : !1;
}
function _d(e) {
	return !ud() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof fd(e).ShadowRoot;
}
function vd(e) {
	let { overflow: t, overflowX: n, overflowY: r, display: i } = kd(e);
	return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && i !== "inline" && i !== "contents";
}
function yd(e) {
	return /^(table|td|th)$/.test(dd(e));
}
function bd(e) {
	try {
		if (e.matches(":popover-open")) return !0;
	} catch {}
	try {
		return e.matches(":modal");
	} catch {
		return !1;
	}
}
var xd = /transform|translate|scale|rotate|perspective|filter/, Sd = /paint|layout|strict|content/, Cd = (e) => !!e && e !== "none", wd;
function Td(e) {
	let t = hd(e) ? kd(e) : e;
	return Cd(t.transform) || Cd(t.translate) || Cd(t.scale) || Cd(t.rotate) || Cd(t.perspective) || !Dd() && (Cd(t.backdropFilter) || Cd(t.filter)) || xd.test(t.willChange || "") || Sd.test(t.contain || "");
}
function Ed(e) {
	let t = jd(e);
	for (; gd(t) && !Od(t);) {
		if (Td(t)) return t;
		if (bd(t)) return null;
		t = jd(t);
	}
	return null;
}
function Dd() {
	return wd ??= typeof CSS < "u" && CSS.supports && CSS.supports("-webkit-backdrop-filter", "none"), wd;
}
function Od(e) {
	return /^(html|body|#document)$/.test(dd(e));
}
function kd(e) {
	return fd(e).getComputedStyle(e);
}
function Ad(e) {
	return hd(e) ? {
		scrollLeft: e.scrollLeft,
		scrollTop: e.scrollTop
	} : {
		scrollLeft: e.scrollX,
		scrollTop: e.scrollY
	};
}
function jd(e) {
	if (dd(e) === "html") return e;
	let t = e.assignedSlot || e.parentNode || _d(e) && e.host || pd(e);
	return _d(t) ? t.host : t;
}
function Md(e) {
	let t = jd(e);
	return Od(t) ? (e.ownerDocument || e).body : gd(t) && vd(t) ? t : Md(t);
}
function Nd(e, t, n) {
	t === void 0 && (t = []), n === void 0 && (n = !0);
	let r = Md(e), i = r === e.ownerDocument?.body, a = fd(r);
	if (i) {
		let e = Pd(a);
		return t.concat(a, a.visualViewport || [], vd(r) ? r : [], e && n ? Nd(e) : []);
	}
	return t.concat(r, Nd(r, [], n));
}
function Pd(e) {
	return e.parent && Object.getPrototypeOf(e.parent) ? e.frameElement : null;
}
// node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs
function Fd(e) {
	let t = kd(e), n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0, i = gd(e), a = i ? e.offsetWidth : n, o = i ? e.offsetHeight : r, s = wu(n) !== a || wu(r) !== o;
	return s && (n = a, r = o), {
		width: n,
		height: r,
		$: s
	};
}
function Id(e) {
	return hd(e) ? e : e.contextElement;
}
function Ld(e) {
	let t = Id(e);
	if (!gd(t)) return Eu(1);
	let n = t.getBoundingClientRect(), { width: r, height: i, $: a } = Fd(t), o = (a ? wu(n.width) : n.width) / r, s = (a ? wu(n.height) : n.height) / i;
	return o && Number.isFinite(o) || (o = 1), s && Number.isFinite(s) || (s = 1), {
		x: o,
		y: s
	};
}
var Rd = /*#__PURE__*/ Eu(0);
function zd(e) {
	let t = fd(e);
	return !Dd() || !t.visualViewport ? Rd : {
		x: t.visualViewport.offsetLeft,
		y: t.visualViewport.offsetTop
	};
}
function Bd(e, t, n) {
	return t === void 0 && (t = !1), !!n && t && n === fd(e);
}
function Vd(e, t, n, r) {
	t === void 0 && (t = !1), n === void 0 && (n = !1);
	let i = e.getBoundingClientRect(), a = Id(e), o = Eu(1);
	t && (r ? hd(r) && (o = Ld(r)) : o = Ld(e));
	let s = Bd(a, n, r) ? zd(a) : Eu(0), c = (i.left + s.x) / o.x, l = (i.top + s.y) / o.y, u = i.width / o.x, d = i.height / o.y;
	if (a && r) {
		let e = fd(a), t = hd(r) ? fd(r) : r, n = e, i = Pd(n);
		for (; i && t !== n;) {
			let e = Ld(i), t = i.getBoundingClientRect(), r = kd(i), a = t.left + (i.clientLeft + parseFloat(r.paddingLeft)) * e.x, o = t.top + (i.clientTop + parseFloat(r.paddingTop)) * e.y;
			c *= e.x, l *= e.y, u *= e.x, d *= e.y, c += a, l += o, n = fd(i), i = Pd(n);
		}
	}
	return Ju({
		width: u,
		height: d,
		x: c,
		y: l
	});
}
function Hd(e, t) {
	let n = Ad(e).scrollLeft;
	return t ? t.left + n : Vd(pd(e)).left + n;
}
function Ud(e, t) {
	let n = e.getBoundingClientRect();
	return {
		x: n.left + t.scrollLeft - Hd(e, n),
		y: n.top + t.scrollTop
	};
}
function Wd(e) {
	let { elements: t, rect: n, offsetParent: r, strategy: i } = e, a = i === "fixed", o = pd(r), s = t ? bd(t.floating) : !1;
	if (r === o || s && a) return n;
	let c = {
		scrollLeft: 0,
		scrollTop: 0
	}, l = Eu(1), u = Eu(0), d = gd(r);
	if ((d || !a) && ((dd(r) !== "body" || vd(o)) && (c = Ad(r)), d)) {
		let e = Vd(r);
		l = Ld(r), u.x = e.x + r.clientLeft, u.y = e.y + r.clientTop;
	}
	let f = o && !d && !a ? Ud(o, c) : Eu(0);
	return {
		width: n.width * l.x,
		height: n.height * l.y,
		x: n.x * l.x - c.scrollLeft * l.x + u.x + f.x,
		y: n.y * l.y - c.scrollTop * l.y + u.y + f.y
	};
}
function Gd(e) {
	return e.getClientRects ? Array.from(e.getClientRects()) : [];
}
function Kd(e) {
	let t = Ad(e), n = e.ownerDocument.body, r = Cu(e.scrollWidth, e.clientWidth, n.scrollWidth, n.clientWidth), i = Cu(e.scrollHeight, e.clientHeight, n.scrollHeight, n.clientHeight), a = -t.scrollLeft + Hd(e), o = -t.scrollTop;
	return kd(n).direction === "rtl" && (a += Cu(e.clientWidth, n.clientWidth) - r), {
		width: r,
		height: i,
		x: a,
		y: o
	};
}
var qd = 25;
function Jd(e, t, n) {
	n === void 0 && (n = "viewport");
	let r = n === "layoutViewport", i = fd(e), a = pd(e), o = i.visualViewport, s = a.clientWidth, c = a.clientHeight, l = 0, u = 0;
	if (o) {
		let e = !Dd() || t === "fixed";
		r ? e || (l = -o.offsetLeft, u = -o.offsetTop) : (s = o.width, c = o.height, e && (l = o.offsetLeft, u = o.offsetTop));
	}
	if (Hd(a) <= 0) {
		let e = a.ownerDocument, t = e.body, n = getComputedStyle(t), r = e.compatMode === "CSS1Compat" && parseFloat(n.marginLeft) + parseFloat(n.marginRight) || 0, i = Math.abs(a.clientWidth - t.clientWidth - r), o = getComputedStyle(a).scrollbarGutter === "stable both-edges" ? i / 2 : i;
		o <= qd && (s -= o);
	}
	return {
		width: s,
		height: c,
		x: l,
		y: u
	};
}
function Yd(e, t) {
	let n = Vd(e, !0, t === "fixed"), r = n.top + e.clientTop, i = n.left + e.clientLeft, a = Ld(e);
	return {
		width: e.clientWidth * a.x,
		height: e.clientHeight * a.y,
		x: i * a.x,
		y: r * a.y
	};
}
function Xd(e, t, n) {
	let r;
	if (t === "viewport" || t === "layoutViewport") r = Jd(e, n, t);
	else if (t === "document") r = Kd(pd(e));
	else if (hd(t)) r = Yd(t, n);
	else {
		let n = zd(e);
		r = {
			x: t.x - n.x,
			y: t.y - n.y,
			width: t.width,
			height: t.height
		};
	}
	return Ju(r);
}
function Zd(e, t) {
	let n = t.get(e);
	if (n) return n;
	let r = Nd(e, [], !1).filter((e) => hd(e) && dd(e) !== "body"), i = null, a = kd(e).position === "fixed", o = a ? jd(e) : e;
	for (; hd(o) && !Od(o);) {
		let e = kd(o), t = Td(o), n = i ? i.position : a ? "fixed" : "";
		!t && (n === "fixed" || n === "absolute" && e.position === "static") ? r = r.filter((e) => e !== o) : i = e, o = jd(o);
	}
	return t.set(e, r), r;
}
function Qd(e) {
	let { element: t, boundary: n, rootBoundary: r, strategy: i } = e, a = [...n === "clippingAncestors" ? bd(t) ? [] : Zd(t, this._c) : [].concat(n), r], o = Xd(t, a[0], i), s = o.top, c = o.right, l = o.bottom, u = o.left;
	for (let e = 1; e < a.length; e++) {
		let n = Xd(t, a[e], i);
		s = Cu(n.top, s), c = Su(n.right, c), l = Su(n.bottom, l), u = Cu(n.left, u);
	}
	return {
		width: c - u,
		height: l - s,
		x: u,
		y: s
	};
}
function $d(e) {
	let { width: t, height: n } = Fd(e);
	return {
		width: t,
		height: n
	};
}
function ef(e, t, n) {
	let r = gd(t), i = pd(t), a = n === "fixed", o = Vd(e, !0, a, t), s = {
		scrollLeft: 0,
		scrollTop: 0
	}, c = Eu(0);
	if ((r || !a) && ((dd(t) !== "body" || vd(i)) && (s = Ad(t)), r)) {
		let e = Vd(t, !0, a, t);
		c.x = e.x + t.clientLeft, c.y = e.y + t.clientTop;
	}
	!r && i && (c.x = Hd(i));
	let l = i && !r && !a ? Ud(i, s) : Eu(0);
	return {
		x: o.left + s.scrollLeft - c.x - l.x,
		y: o.top + s.scrollTop - c.y - l.y,
		width: o.width,
		height: o.height
	};
}
function tf(e) {
	return kd(e).position === "static";
}
function nf(e, t) {
	if (!gd(e) || kd(e).position === "fixed") return null;
	if (t) return t(e);
	let n = e.offsetParent;
	return pd(e) === n && (n = n.ownerDocument.body), n;
}
function rf(e, t) {
	let n = fd(e);
	if (bd(e)) return n;
	if (!gd(e)) {
		let t = jd(e);
		for (; t && !Od(t);) {
			if (hd(t) && !tf(t)) return t;
			t = jd(t);
		}
		return n;
	}
	let r = nf(e, t);
	for (; r && yd(r) && tf(r);) r = nf(r, t);
	return r && Od(r) && tf(r) && !Td(r) ? n : r || Ed(e) || n;
}
var af = async function(e) {
	let t = this.getOffsetParent || rf, n = this.getDimensions, r = await n(e.floating);
	return {
		reference: ef(e.reference, await t(e.floating), e.strategy),
		floating: {
			x: 0,
			y: 0,
			width: r.width,
			height: r.height
		}
	};
};
function of(e) {
	return kd(e).direction === "rtl";
}
var sf = {
	convertOffsetParentRelativeRectToViewportRelativeRect: Wd,
	getDocumentElement: pd,
	getClippingRect: Qd,
	getOffsetParent: rf,
	getElementRects: af,
	getClientRects: Gd,
	getDimensions: $d,
	getScale: Ld,
	isElement: hd,
	isRTL: of
};
function cf(e, t) {
	return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function lf(e, t, n) {
	let r = null, i, a = pd(e);
	function o() {
		var e;
		clearTimeout(i), (e = r) == null || e.disconnect(), r = null;
	}
	function s(n, c) {
		n === void 0 && (n = !1), c === void 0 && (c = 1), o();
		let l = e.getBoundingClientRect(), { left: u, top: d, width: f, height: p } = l;
		if (n || t(), !f || !p) return;
		let m = Tu(d), h = Tu(a.clientWidth - (u + f)), g = Tu(a.clientHeight - (d + p)), _ = Tu(u), v = {
			rootMargin: -m + "px " + -h + "px " + -g + "px " + -_ + "px",
			threshold: Cu(0, Su(1, c)) || 1
		}, y = !0;
		function b(t) {
			let n = t[0].intersectionRatio;
			if (!cf(l, e.getBoundingClientRect())) return s();
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
	let c = fd(e), l = () => s(n);
	return c.addEventListener("resize", l), s(!0), () => {
		c.removeEventListener("resize", l), o();
	};
}
function uf(e, t, n, r) {
	r === void 0 && (r = {});
	let { ancestorScroll: i = !0, ancestorResize: a = !0, elementResize: o = typeof ResizeObserver == "function", layoutShift: s = typeof IntersectionObserver == "function", animationFrame: c = !1 } = r, l = Id(e), u = i || a ? [...l ? Nd(l) : [], ...t ? Nd(t) : []] : [];
	u.forEach((e) => {
		i && e.addEventListener("scroll", n), a && e.addEventListener("resize", n);
	});
	let d = l && s ? lf(l, n, a) : null, f = -1, p = null;
	o && (p = new ResizeObserver((e) => {
		let [r] = e;
		r && r.target === l && p && t && (p.unobserve(t), cancelAnimationFrame(f), f = requestAnimationFrame(() => {
			var e;
			(e = p) == null || e.observe(t);
		})), n();
	}), l && !c && p.observe(l), t && p.observe(t));
	let m, h = c ? Vd(e) : null;
	c && g();
	function g() {
		let t = Vd(e);
		h && !cf(h, t) && n(), h = t, m = requestAnimationFrame(g);
	}
	return n(), () => {
		var e;
		u.forEach((e) => {
			i && e.removeEventListener("scroll", n), a && e.removeEventListener("resize", n);
		}), d?.(), (e = p) == null || e.disconnect(), p = null, c && cancelAnimationFrame(m);
	};
}
var df = od, ff = sd, pf = ed, mf = ld, hf = rd, gf = $u, _f = cd, vf = (e, t, n) => {
	let r = /* @__PURE__ */ new Map(), i = n ?? {}, a = {
		...sf,
		...i.platform,
		_c: r
	};
	return Qu(e, t, {
		...i,
		platform: a
	});
};
// node_modules/@floating-ui/vue/dist/floating-ui.vue.mjs
function yf(e) {
	return typeof e == "object" && !!e && "$el" in e;
}
function bf(e) {
	if (yf(e)) {
		let t = e.$el;
		return md(t) && dd(t) === "#comment" ? null : t;
	}
	return e;
}
function xf(e) {
	return {
		name: "arrow",
		options: e,
		fn(t) {
			let n = bf(R(e.element));
			return n == null ? {} : gf({
				element: n,
				padding: e.padding
			}).fn(t);
		}
	};
}
function Sf(e) {
	return typeof window > "u" ? 1 : (e.ownerDocument.defaultView || window).devicePixelRatio || 1;
}
function Cf(e, t) {
	let n = Sf(e);
	return Math.round(t * n) / n;
}
function wf(e, t, n) {
	n === void 0 && (n = {});
	let r = n.whileElementsMounted, i = Z(() => R(n.open) ?? !0), a = Z(() => R(n.middleware)), o = Z(() => R(n.placement) ?? "bottom"), s = Z(() => R(n.strategy) ?? "absolute"), c = Z(() => R(n.transform) ?? !0), l = Z(() => bf(e.value)), u = Z(() => bf(t.value)), d = /* @__PURE__ */ I(0), f = /* @__PURE__ */ I(0), p = /* @__PURE__ */ I(s.value), m = /* @__PURE__ */ I(o.value), h = /* @__PURE__ */ en({}), g = /* @__PURE__ */ I(!1), _ = Z(() => {
		let e = {
			position: p.value,
			left: "0",
			top: "0"
		};
		if (!u.value) return e;
		let t = Cf(u.value, d.value), n = Cf(u.value, f.value);
		return c.value ? {
			...e,
			transform: "translate(" + t + "px, " + n + "px)",
			...Sf(u.value) >= 1.5 && { willChange: "transform" }
		} : {
			position: p.value,
			left: t + "px",
			top: n + "px"
		};
	}), v;
	function y() {
		if (l.value == null || u.value == null) return;
		let e = i.value;
		vf(l.value, u.value, {
			middleware: a.value,
			placement: o.value,
			strategy: s.value
		}).then((t) => {
			d.value = t.x, f.value = t.y, p.value = t.strategy, m.value = t.placement, h.value = t.middlewareData, g.value = e !== !1;
		});
	}
	function b() {
		typeof v == "function" && (v(), v = void 0);
	}
	function x() {
		b(), r === void 0 ? y() : l.value != null && u.value != null && (v = r(l.value, u.value, y));
	}
	function S() {
		i.value || (g.value = !1);
	}
	return V([
		a,
		o,
		s,
		i
	], y, { flush: "sync" }), V([l, u], x, { flush: "sync" }), V(i, S, { flush: "sync" }), Oe() && ke(b), {
		x: /* @__PURE__ */ Gt(d),
		y: /* @__PURE__ */ Gt(f),
		strategy: /* @__PURE__ */ Gt(p),
		placement: /* @__PURE__ */ Gt(m),
		middlewareData: /* @__PURE__ */ Gt(h),
		isPositioned: /* @__PURE__ */ Gt(g),
		floatingStyles: _,
		update: y
	};
}
// node_modules/reka-ui/dist/Popper/PopperContent.js
var Tf = ["dir"], Ef = {
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
}, [Df, Of] = /*#__PURE__*/ kc("PopperContent"), kf = /* @__PURE__ */ H({
	inheritAttrs: !1,
	__name: "PopperContent",
	props: /* @__PURE__ */ ri({
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
	}, { ...Ef }),
	emits: ["placed"],
	setup(e, { emit: t }) {
		let n = e, r = t, i = mu(), { forwardRef: a, currentElement: o } = Sl(), s = _l(Z(() => n.dir)), c = /* @__PURE__ */ I(), l = /* @__PURE__ */ I(), { width: u, height: d } = Il(l), f = Z(() => n.side + (n.align === "center" ? "" : `-${n.align}`)), p = Z(() => typeof n.collisionPadding == "number" ? n.collisionPadding : {
			top: 0,
			right: 0,
			bottom: 0,
			left: 0,
			...n.collisionPadding
		}), m = Z(() => Array.isArray(n.collisionBoundary) ? n.collisionBoundary : [n.collisionBoundary]), h = Z(() => ({
			padding: p.value,
			boundary: m.value.filter(vu),
			altBoundary: m.value.length > 0
		})), g = Z(() => ({
			mainAxis: n.sideFlip,
			crossAxis: n.alignFlip
		})), _ = Z(() => [
			df({
				mainAxis: n.sideOffset + d.value,
				alignmentAxis: n.alignOffset
			}),
			n.prioritizePosition && n.avoidCollisions && pf({
				...h.value,
				...g.value
			}),
			n.avoidCollisions && ff({
				mainAxis: !0,
				crossAxis: !!n.prioritizePosition,
				limiter: n.sticky === "partial" ? _f() : void 0,
				...h.value
			}),
			!n.prioritizePosition && n.avoidCollisions && pf({
				...h.value,
				...g.value
			}),
			mf({
				...h.value,
				apply: ({ elements: e, rects: t, availableWidth: n, availableHeight: r }) => {
					let { width: i, height: a } = t.reference, o = e.floating.style;
					o.setProperty("--reka-popper-available-width", `${n}px`), o.setProperty("--reka-popper-available-height", `${r}px`), o.setProperty("--reka-popper-anchor-width", `${i}px`), o.setProperty("--reka-popper-anchor-height", `${a}px`);
				}
			}),
			l.value && xf({
				element: l.value,
				padding: n.arrowPadding
			}),
			yu({
				arrowWidth: u.value,
				arrowHeight: d.value,
				dir: s.value
			}),
			n.hideWhenDetached && hf({
				strategy: "referenceHidden",
				...h.value
			})
		]), { floatingStyles: v, placement: y, isPositioned: b, middlewareData: x, update: S } = wf(Z(() => n.reference ?? i.anchor.value), c, {
			strategy: n.positionStrategy,
			placement: f,
			whileElementsMounted: (...e) => uf(...e, {
				layoutShift: !n.disableUpdateOnLayoutShift,
				animationFrame: n.updatePositionStrategy === "always"
			}),
			middleware: _
		}), C = Z(() => bu(y.value)[0]), w = Z(() => bu(y.value)[1]);
		Zn(() => {
			b.value && r("placed");
		});
		let T = Z(() => {
			let e = x.value.arrow?.centerOffset !== 0;
			return n.hideShiftedArrow && e;
		}), ee = /* @__PURE__ */ I("");
		return Xn(() => {
			o.value && (ee.value = window.getComputedStyle(o.value).zIndex);
		}), Of({
			placedSide: C,
			onArrowChange: (e) => l.value = e,
			arrowX: Z(() => x.value.arrow?.x ?? 0),
			arrowY: Z(() => x.value.arrow?.y ?? 0),
			shouldHideArrow: T
		}), (e, t) => (K(), q("div", {
			ref_key: "floatingRef",
			ref: c,
			"data-reka-popper-content-wrapper": "",
			dir: L(s),
			style: le({
				...L(v),
				transform: L(b) ? L(v).transform : "translate(0, -200%)",
				minWidth: "max-content",
				zIndex: ee.value,
				"--reka-popper-transform-origin": [L(x).transformOrigin?.x, L(x).transformOrigin?.y].join(" "),
				...L(x).hide?.referenceHidden && {
					visibility: "hidden",
					pointerEvents: "none"
				}
			})
		}, [n.memoDependencies ? ao([
			n.asChild,
			n.as,
			C.value,
			w.value,
			L(b),
			...Object.values(e.$attrs),
			...n.memoDependencies
		], () => (K(), J(L(Ul), Pa({
			key: 0,
			ref: L(a)
		}, e.$attrs, {
			"as-child": n.asChild,
			as: n.as,
			"data-side": C.value,
			"data-align": w.value,
			style: { animation: L(b) ? void 0 : "none" }
		}), {
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"style"
		])), t, 0) : (K(), J(L(Ul), Pa({
			key: 1,
			ref: L(a)
		}, e.$attrs, {
			"as-child": n.asChild,
			as: n.as,
			"data-side": C.value,
			"data-align": w.value,
			dir: L(s),
			style: { animation: L(b) ? void 0 : "none" }
		}), {
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"dir",
			"style"
		]))], 12, Tf));
	}
}), [Af, jf] = /*#__PURE__*/ kc("PopoverRoot"), Mf = /* @__PURE__ */ H({
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
		let n = e, r = t, { modal: i } = /* @__PURE__ */ sn(n), a = tl(n, "open", r, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		});
		return jf({
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
			triggerElement: /* @__PURE__ */ I(),
			hasCustomAnchor: /* @__PURE__ */ I(!1)
		}), (e, t) => (K(), J(L(gu), null, {
			default: B(() => [U(e.$slots, "default", {
				open: L(a),
				close: () => a.value = !1
			})]),
			_: 3
		}));
	}
}), Nf = /* @__PURE__ */ H({
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
		Sl();
		let n = Af();
		return (r, i) => (K(), J(L(Ul), {
			type: e.as === "button" ? "button" : void 0,
			as: e.as,
			"as-child": t.asChild,
			onClick: i[0] ||= (e) => L(n).onOpenChange(!1)
		}, {
			default: B(() => [U(r.$slots, "default")]),
			_: 3
		}, 8, [
			"type",
			"as",
			"as-child"
		]));
	}
}), Pf = /* @__PURE__ */ H({
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
		let n = e, r = t, i = Cl(Gc(n, "trapFocus", "disableOutsidePointerEvents")), { forwardRef: a } = Sl(), o = Af();
		return bl(), (t, n) => (K(), J(L(fu), {
			"as-child": "",
			loop: "",
			trapped: e.trapFocus,
			onMountAutoFocus: n[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: n[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: B(() => [X(L(Zl), {
				"as-child": "",
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				onPointerDownOutside: n[0] ||= (e) => r("pointerDownOutside", e),
				onInteractOutside: n[1] ||= (e) => r("interactOutside", e),
				onEscapeKeyDown: n[2] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: n[3] ||= (e) => r("focusOutside", e),
				onDismiss: n[4] ||= (e) => L(o).onOpenChange(!1)
			}, {
				default: B(() => [X(L(kf), Pa(L(i), {
					id: L(o).contentId,
					ref: L(a),
					"data-state": L(o).open.value ? "open" : "closed",
					"aria-labelledby": L(o).triggerId,
					style: {
						"--reka-popover-content-transform-origin": "var(--reka-popper-transform-origin)",
						"--reka-popover-content-available-width": "var(--reka-popper-available-width)",
						"--reka-popover-content-available-height": "var(--reka-popper-available-height)",
						"--reka-popover-trigger-width": "var(--reka-popper-anchor-width)",
						"--reka-popover-trigger-height": "var(--reka-popper-anchor-height)"
					},
					role: "dialog"
				}), {
					default: B(() => [U(t.$slots, "default")]),
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
}), Ff = /* @__PURE__ */ H({
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
		let n = e, r = t, i = Af(), a = /* @__PURE__ */ I(!1);
		ml(!0);
		let o = wl(n, r), { forwardRef: s, currentElement: c } = Sl();
		return Pl(c), (e, t) => (K(), J(Pf, Pa(L(o), {
			ref: L(s),
			"trap-focus": L(i).open.value,
			"disable-outside-pointer-events": "",
			onCloseAutoFocus: t[0] ||= ls((e) => {
				r("closeAutoFocus", e), a.value || L(i).triggerElement.value?.focus();
			}, ["prevent"]),
			onPointerDownOutside: t[1] ||= (e) => {
				r("pointerDownOutside", e);
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0, i = t.button === 2 || n;
				a.value = i;
			},
			onFocusOutside: t[2] ||= ls(() => {}, ["prevent"])
		}), {
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16, ["trap-focus"]));
	}
}), If = /* @__PURE__ */ H({
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
		let n = e, r = t, i = Af(), a = /* @__PURE__ */ I(!1), o = /* @__PURE__ */ I(!1), s = wl(n, r);
		return (e, t) => (K(), J(Pf, Pa(L(s), {
			"trap-focus": !1,
			"disable-outside-pointer-events": !1,
			onCloseAutoFocus: t[0] ||= (e) => {
				r("closeAutoFocus", e), e.defaultPrevented || (a.value || L(i).triggerElement.value?.focus(), e.preventDefault()), a.value = !1, o.value = !1;
			},
			onInteractOutside: t[1] ||= async (e) => {
				r("interactOutside", e), e.defaultPrevented || (a.value = !0, e.detail.originalEvent.type === "pointerdown" && (o.value = !0));
				let t = e.target;
				L(i).triggerElement.value?.contains(t) && e.preventDefault(), e.detail.originalEvent.type === "focusin" && o.value && e.preventDefault();
			}
		}), {
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Lf = /* @__PURE__ */ H({
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
		let n = e, r = t, i = Af(), a = wl(n, r), { forwardRef: o } = Sl();
		return i.contentId ||= Fl(void 0, "reka-popover-content"), (t, n) => (K(), J(L(Bl), { present: e.forceMount || L(i).open.value }, {
			default: B(() => [L(i).modal.value ? (K(), J(Ff, Pa({ key: 0 }, L(a), { ref: L(o) }), {
				default: B(() => [U(t.$slots, "default")]),
				_: 3
			}, 16)) : (K(), J(If, Pa({ key: 1 }, L(a), { ref: L(o) }), {
				default: B(() => [U(t.$slots, "default")]),
				_: 3
			}, 16))]),
			_: 3
		}, 8, ["present"]));
	}
}), Rf = /* @__PURE__ */ H({
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
		return (e, n) => (K(), J(L(pu), me(Da(t)), {
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), zf = /* @__PURE__ */ H({
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
		let t = e, n = Af(), { forwardRef: r, currentElement: i } = Sl();
		return n.triggerId ||= Fl(void 0, "reka-popover-trigger"), n.contentId ||= Fl(void 0, "reka-popover-content"), Fr(() => {
			n.triggerElement.value = i.value;
		}), (i, a) => (K(), J(Kr(L(n).hasCustomAnchor.value ? L(Ul) : L(_u)), { "as-child": "" }, {
			default: B(() => [X(L(Ul), {
				id: L(n).triggerId,
				ref: L(r),
				type: e.as === "button" ? "button" : void 0,
				"aria-haspopup": "dialog",
				"aria-expanded": L(n).open.value,
				"aria-controls": L(n).open.value ? L(n).contentId : void 0,
				"data-state": L(n).open.value ? "open" : "closed",
				as: e.as,
				"as-child": t.asChild,
				onClick: L(n).onOpenToggle
			}, {
				default: B(() => [U(i.$slots, "default")]),
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
}), Bf = [
	"data-active",
	"aria-label",
	"title"
], Vf = { class: "tc-column-filter-label" }, Hf = { class: "tc-filter-popover-heading list-filter-popover__heading" }, Uf = /*#__PURE__*/ xs(/* @__PURE__ */ H({
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
		return (t, r) => (K(), J(L(Mf), {
			open: e.open,
			modal: !1,
			"onUpdate:open": r[0] ||= (e) => n("update:open", e)
		}, {
			default: B(() => [X(L(zf), { "as-child": "" }, {
				default: B(() => [Y("button", {
					type: "button",
					class: A(["tc-column-filter-trigger", { "is-active": e.active }]),
					"data-active": e.active ? "" : void 0,
					"aria-label": `筛选${e.label}`,
					title: e.active ? `${e.label}：${e.summary || "已筛选"}` : `筛选${e.label}`
				}, [Y("span", Vf, j(e.triggerLabel || e.label), 1), r[1] ||= Y("svg", {
					class: "tc-column-filter-icon",
					viewBox: "0 0 16 16",
					width: "14",
					height: "14",
					fill: "none",
					"aria-hidden": "true",
					focusable: "false"
				}, [Y("path", {
					d: "M2 3h12L9.5 8.3V13l-3-1.5V8.3L2 3Z",
					stroke: "currentColor",
					"stroke-width": "1.4",
					"stroke-linejoin": "round"
				})], -1)], 10, Bf)]),
				_: 1
			}), X(L(Rf), null, {
				default: B(() => [X(L(Lf), {
					class: "tc-filter-popover list-filter-popover",
					"aria-label": `筛选${e.label}`,
					side: "bottom",
					align: "start",
					"side-offset": 6,
					"collision-padding": 10,
					"hide-when-detached": ""
				}, {
					default: B(() => [
						Y("div", Hf, "筛选" + j(e.label), 1),
						U(t.$slots, "default", {}, void 0, !0),
						X(L(Nf), {
							class: "tc-filter-popover-close list-filter-popover__close",
							"aria-label": `关闭${e.label}筛选`,
							title: "关闭筛选"
						}, {
							default: B(() => [...r[2] ||= [Y("svg", {
								viewBox: "0 0 16 16",
								width: "16",
								height: "16",
								fill: "none",
								"aria-hidden": "true",
								focusable: "false"
							}, [Y("path", {
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
}), [["__scopeId", "data-v-49f53dbd"]]), Wf = {
	search: "搜索",
	state: "状态",
	purpose: "用途",
	window: "时间"
}, Gf = [
	{
		value: "all",
		label: "全部时间"
	},
	{
		value: "1h",
		label: "最近 1 小时"
	},
	{
		value: "24h",
		label: "最近 24 小时"
	},
	{
		value: "7d",
		label: "最近 7 天"
	}
], Kf = [
	"pending",
	"leased",
	"shared_pending",
	"shared_leased",
	"pool_leased"
];
function qf(e, t, n, r) {
	if (e === "window") return Gf;
	let i = e === "purpose" ? n?.purposes ?? [] : t === "traffic" ? ["available"] : (n?.lease_states ?? []).filter((e) => t === "current" ? Kf.includes(e) : !Kf.includes(e)), a = [...new Set(i.filter((e) => typeof e == "string" && e !== "all"))];
	return r && r !== "all" && !a.includes(r) && a.push(r), [{
		value: "all",
		label: e === "state" ? "全部状态" : "全部用途"
	}, ...a.map((t) => ({
		value: t,
		label: e === "state" ? nc(t).label : t
	}))];
}
function Jf(e, t) {
	let n = [], r = (e, t, r) => n.push({
		key: e,
		label: `${t}：${r}`,
		title: `${t}：${r}`,
		removeLabel: `清除${t}筛选`
	});
	e.search && r("search", "搜索", e.search), e.window !== "all" && r("window", "时间", Gf.find((t) => t.value === e.window)?.label || e.window), e.purpose !== "all" && r("purpose", "用途", e.purpose);
	for (let e of [
		"current",
		"history",
		"traffic"
	]) t[e] !== "all" && r("state:" + e, {
		current: "当前状态",
		history: "历史状态",
		traffic: "采集状态"
	}[e], nc(t[e]).label);
	return n;
}
// src/features/proxy/ProxyFilters.vue?vue&type=script&setup=true&lang.ts
var Yf = { class: "pt-filter-fields" }, Xf = {
	key: 0,
	class: "pt-filter-field"
}, Zf = ["value"], Qf = {
	key: 1,
	class: "pt-filter-field"
}, $f = ["value", "placeholder"], ep = ["aria-label"], tp = [
	"data-proxy-filter-option",
	"aria-pressed",
	"onClick"
], np = { class: "pt-filter-actions" }, rp = /* @__PURE__ */ H({
	__name: "ProxyFilters",
	props: {
		column: {},
		triggerLabel: {},
		view: {},
		filters: {},
		state: {},
		summary: {},
		open: { type: Boolean }
	},
	emits: ["update:open", "change"],
	setup(e, { emit: t }) {
		let n = e, r = t, i = /* @__PURE__ */ I("search"), a = Z(() => [
			"search",
			"state",
			...n.view === "traffic" ? [] : ["purpose"],
			"window"
		]), o = Z(() => n.column ?? (a.value.includes(i.value) ? i.value : "search")), s = Z(() => o.value === "state" ? n.state : n.filters[o.value]), c = Z(() => n.column ? s.value !== (o.value === "search" ? "" : "all") : a.value.some((e) => (e === "state" ? n.state : n.filters[e]) !== (e === "search" ? "" : "all")));
		function l(e) {
			r("change", o.value, e), o.value !== "search" && r("update:open", !1);
		}
		return (t, n) => (K(), J(Uf, {
			label: e.column ? L(Wf)[e.column] : "代理记录",
			"trigger-label": e.triggerLabel || (e.column ? L(Wf)[e.column] : "筛选"),
			active: c.value,
			summary: s.value,
			open: e.open,
			"onUpdate:open": n[5] ||= (e) => r("update:open", e)
		}, {
			default: B(() => [Y("div", Yf, [
				e.column ? Aa("", !0) : (K(), q("label", Xf, [n[6] ||= ka("筛选列", -1), Wn(Y("select", {
					"onUpdate:modelValue": n[0] ||= (e) => i.value = e,
					"aria-label": "选择代理记录筛选列"
				}, [(K(!0), q(G, null, Yr(a.value, (e) => (K(), q("option", {
					key: e,
					value: e
				}, j(L(Wf)[e]), 9, Zf))), 128))], 512), [[rs, i.value]])])),
				o.value === "search" ? (K(), q("label", Qf, [n[7] ||= ka("搜索", -1), Y("input", {
					value: s.value,
					type: "search",
					placeholder: e.view === "traffic" ? "来源、方法或关联 ID" : "账号、任务、租约或 IP",
					"aria-label": "搜索代理记录",
					autocomplete: "off",
					onInput: n[1] ||= (e) => l(e.target.value),
					onKeydown: n[2] ||= ds(ls((e) => r("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, $f)])) : (K(), q("div", {
					key: 2,
					class: "pt-filter-options",
					role: "group",
					"aria-label": L(Wf)[o.value]
				}, [(K(!0), q(G, null, Yr(L(qf)(o.value, e.view, e.summary, s.value), (e) => (K(), q("button", {
					key: e.value,
					type: "button",
					"data-proxy-filter-option": e.value,
					"aria-pressed": e.value === s.value,
					onClick: (t) => l(e.value)
				}, j(e.label), 9, tp))), 128))], 8, ep)),
				Y("div", np, [Y("button", {
					type: "button",
					class: "pt-link",
					onClick: n[3] ||= (e) => l(o.value === "search" ? "" : "all")
				}, " 清除此列"), Y("button", {
					type: "button",
					class: "pt-button",
					onClick: n[4] ||= (e) => r("update:open", !1)
				}, "完成")])
			])]),
			_: 1
		}, 8, [
			"label",
			"trigger-label",
			"active",
			"summary",
			"open"
		]));
	}
}), ip = ["aria-label", "aria-busy"], ap = ["data-proxy-table"], op = { class: "pt-sr-only" }, sp = { key: 1 }, cp = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], lp = ["onClick"], up = { key: 1 }, dp = ["onClick"], fp = { key: 1 }, pp = { key: 0 }, mp = { colspan: "8" }, hp = ["role"], gp = /* @__PURE__ */ H({
	__name: "ProxyRecordsTable",
	props: {
		view: {},
		items: {},
		filters: {},
		state: {},
		summary: {},
		loading: { type: Boolean },
		error: {},
		visible: { type: Boolean },
		openFilter: {},
		scrollRevision: {},
		facetLabel: { type: Function }
	},
	emits: [
		"filter",
		"update:openFilter",
		"detail",
		"retry"
	],
	setup(e, { expose: t, emit: n }) {
		let r = e, i = n, a = {
			current: [
				145,
				144,
				108,
				156,
				126,
				220,
				88,
				188
			],
			history: [
				145,
				144,
				108,
				156,
				126,
				220,
				188,
				92
			],
			traffic: [
				132,
				92,
				108,
				170,
				188,
				220,
				188,
				92
			]
		}, o = {
			current: "proxyCurrent",
			history: "proxyHistory",
			traffic: "proxyTraffic"
		}[r.view], s = Oc({
			defaults: a[r.view],
			storageKey: "gpt_console_table_widths_" + o,
			totalStorageKey: "gpt_console_table_total_" + o,
			min: 28,
			max: 2e3
		}), c = /* @__PURE__ */ I(), l = r.scrollRevision;
		V(() => [r.items, r.scrollRevision], async () => {
			r.scrollRevision !== l && (l = r.scrollRevision, await jn(), c.value && (c.value.scrollTop = 0));
		});
		let u = Z(() => r.view === "traffic" ? [
			{
				label: "来源",
				filter: "search"
			},
			{ label: "方法" },
			{
				label: "采集状态",
				filter: "state"
			},
			{ label: "上传 / 下载 / 总计" },
			{ label: "请求 / 失败 / 未完成 / 未知" },
			{ label: "任务" },
			{
				label: "采集时间",
				filter: "window"
			},
			{ label: "详情" }
		] : [
			{
				label: "租约",
				filter: "search"
			},
			{ label: "出口 IP" },
			{
				label: "状态",
				filter: "state"
			},
			{ label: "账号" },
			{
				label: "用途",
				filter: "purpose"
			},
			{ label: r.view === "history" ? "任务 / 运行 / 注册 job" : "任务 / 运行" },
			...r.view === "history" ? [{
				label: "租约时间",
				filter: "window"
			}, { label: "详情" }] : [{ label: "重试序号" }, {
				label: "时间",
				filter: "window"
			}]
		]), d = Z(() => ({
			current: "当前租约",
			history: "线路历史",
			traffic: "请求流量"
		})[r.view]);
		function f(e) {
			let t = Ys(e.acquired_at), n = e[r.view === "history" ? "released_at" : "expires_at"];
			return {
				text: t,
				secondary: n ? `至 ${Ys(n)}` : "进行中",
				title: `${t} · ${n ? Ys(n) : "进行中"}`
			};
		}
		function p(e, t) {
			r.view !== "current" && i("detail", r.view, e, t.currentTarget);
		}
		return t({ resetColumns: s.resetColumns }), (t, n) => (K(), q("div", {
			ref_key: "scroll",
			ref: c,
			class: "pt-table-scroll",
			tabindex: "0",
			"aria-label": `${d.value}列表，可横向滚动`,
			"aria-busy": e.loading
		}, [Y("table", {
			class: "pt-table pt-records-table",
			"data-proxy-table": e.view,
			style: le({ "--pt-table-width": `${L(s).total.value}px` })
		}, [
			Y("caption", op, j(d.value), 1),
			Y("colgroup", null, [(K(!0), q(G, null, Yr(L(s).widths.value, (e, t) => (K(), q("col", {
				key: t,
				style: le({ width: `${e}px` })
			}, null, 4))), 128))]),
			Y("thead", null, [Y("tr", null, [(K(!0), q(G, null, Yr(u.value, (t, r) => (K(), q("th", {
				key: t.label,
				scope: "col"
			}, [t.filter ? (K(), J(rp, {
				key: 0,
				column: t.filter,
				"trigger-label": t.label,
				view: e.view,
				filters: e.filters,
				state: e.state,
				summary: e.summary,
				open: e.visible && e.openFilter === `${e.view}:${t.filter}`,
				onChange: n[0] ||= (e, t) => i("filter", e, t),
				"onUpdate:open": (n) => i("update:openFilter", n ? `${e.view}:${t.filter}` : null)
			}, null, 8, [
				"column",
				"trigger-label",
				"view",
				"filters",
				"state",
				"summary",
				"open",
				"onUpdate:open"
			])) : (K(), q("span", sp, j(t.label), 1)), r < u.value.length - 1 ? (K(), q("button", {
				key: 2,
				type: "button",
				class: "pt-column-resize",
				"aria-label": `调整${t.label}列宽，方向键调整`,
				onPointerdown: ls((e) => L(s).resize(r, e), ["prevent"]),
				onKeydown: [ds(ls((e) => L(s).resizeWithKeyboard(r, -10), ["prevent"]), ["left"]), ds(ls((e) => L(s).resizeWithKeyboard(r, 10), ["prevent"]), ["right"])]
			}, null, 40, cp)) : Aa("", !0)]))), 128))])]),
			Y("tbody", null, [(K(!0), q(G, null, Yr(e.items, (t, n) => (K(), q("tr", { key: `${e.view}:${t.id ?? n}` }, [e.view === "traffic" ? (K(), q(G, { key: 0 }, [
				Y("td", null, [X(Q, { text: L($)(t.source) }, null, 8, ["text"])]),
				Y("td", null, [X(Q, { text: L($)(t.method) }, null, 8, ["text"])]),
				Y("td", null, [X(qs, {
					label: L(cc)(t).text === "未采集" ? "未采集" : "可观测",
					title: L($)(t.availability),
					tone: L(cc)(t).text === "未采集" ? "neutral" : "success"
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				Y("td", null, [X(Q, Pa({ ref_for: !0 }, L(cc)(t)), null, 16)]),
				Y("td", null, [X(Q, {
					text: [
						t.request_count,
						t.failed_count,
						t.unfinished_count,
						t.unknown_count
					].map((e) => L($s)(e) ?? "—").join(" / "),
					title: "请求 / 失败 / 未完成 / 未知"
				}, null, 8, ["text"])]),
				Y("td", null, [X(Q, Pa({ ref_for: !0 }, L(sc)(t, e.facetLabel)), null, 16)]),
				Y("td", null, [X(Q, Pa({ ref_for: !0 }, L(Xs)(t.started_at), { title: L(Ys)(t.started_at) }), null, 16, ["title"])]),
				Y("td", null, [t.id == null ? (K(), q("span", up, "—")) : (K(), q("button", {
					key: 0,
					type: "button",
					class: "pt-link",
					"data-proxy-detail": "traffic",
					"aria-label": "查看请求流量详情",
					onClick: (e) => p(t, e)
				}, " 详情", 8, lp))])
			], 64)) : (K(), q(G, { key: 1 }, [
				Y("td", null, [X(Q, {
					text: L($)(t.lease_id, "未提供租约 ID"),
					secondary: L($)(t.provider)
				}, null, 8, ["text", "secondary"])]),
				Y("td", null, [X(Q, { text: L($)(t.exit_ip) }, null, 8, ["text"])]),
				Y("td", null, [X(qs, {
					label: L(nc)(t.state).label,
					title: L(nc)(t.state).title,
					tone: L(nc)(t.state).tone
				}, null, 8, [
					"label",
					"title",
					"tone"
				])]),
				Y("td", null, [X(Q, { text: L($)(t.account_id) }, null, 8, ["text"])]),
				Y("td", null, [X(Q, { text: L($)(t.purpose) }, null, 8, ["text"])]),
				Y("td", null, [X(Q, { text: L(oc)(t, e.view === "history") }, null, 8, ["text"])]),
				e.view === "current" ? (K(), q(G, { key: 0 }, [Y("td", null, [X(Q, { text: L($)(t.route_attempt_no) }, null, 8, ["text"])]), Y("td", null, [X(Q, Pa({ ref_for: !0 }, f(t)), null, 16)])], 64)) : (K(), q(G, { key: 1 }, [Y("td", null, [X(Q, Pa({ ref_for: !0 }, f(t)), null, 16)]), Y("td", null, [t.id == null ? (K(), q("span", fp, "—")) : (K(), q("button", {
					key: 0,
					type: "button",
					class: "pt-link",
					"data-proxy-detail": "history",
					"aria-label": "查看线路历史详情",
					onClick: (e) => p(t, e)
				}, " 详情", 8, dp))])], 64))
			], 64))]))), 128)), e.items.length ? Aa("", !0) : (K(), q("tr", pp, [Y("td", mp, [Y("div", {
				class: "pt-empty",
				role: e.error ? "alert" : "status"
			}, [
				Y("strong", null, j(e.loading ? `正在加载${d.value}` : e.error ? "代理与流量数据暂不可用" : `暂无${d.value}`), 1),
				Y("p", null, j(e.error || (e.loading ? "正在同步代理与流量 API" : "当前没有可显示的持久化记录。")), 1),
				e.error ? (K(), q("button", {
					key: 0,
					type: "button",
					class: "pt-button",
					onClick: n[1] ||= (e) => i("retry")
				}, "重新加载")) : Aa("", !0)
			], 8, hp)])]))])
		], 12, ap)], 8, ip));
	}
}), _p = { class: "pt-detail-head" }, vp = { id: "proxyTrafficDetailTitle" }, yp = { class: "pt-detail-fields" }, bp = /* @__PURE__ */ H({
	__name: "ProxyDetail",
	props: {
		snapshot: {},
		facetLabel: { type: Function }
	},
	emits: ["close"],
	setup(e, { emit: t }) {
		let n = e, r = t, i = /* @__PURE__ */ I(), a = /* @__PURE__ */ I(), o = Z(() => n.snapshot ? uc(n.snapshot.view, n.snapshot.row, n.facetLabel) : []), s = null, c = !1;
		function l() {
			s !== null && (document.body.style.overflow = s, s = null);
		}
		return V(() => n.snapshot, async (e) => {
			await jn(), c || (e ? i.value?.open || (s = document.body.style.overflow, document.body.style.overflow = "hidden", i.value?.showModal(), i.value?.scrollTo?.({ top: 0 }), a.value?.focus({ preventScroll: !0 })) : (i.value?.close(), l()));
		}, { immediate: !0 }), Rr(() => {
			c = !0, i.value?.close(), l();
		}), (t, n) => (K(), q("dialog", {
			ref_key: "dialog",
			ref: i,
			class: "pt-detail-dialog",
			"aria-labelledby": "proxyTrafficDetailTitle",
			onCancel: n[1] ||= ls((e) => r("close"), ["prevent"]),
			onClick: n[2] ||= ls((e) => r("close"), ["self"]),
			onClose: n[3] ||= (t) => e.snapshot && r("close")
		}, [Y("div", _p, [Y("h3", vp, j(e.snapshot?.view === "history" ? "线路历史详情" : "请求流量详情"), 1), Y("button", {
			ref_key: "closeButton",
			ref: a,
			type: "button",
			class: "pt-button",
			"data-proxy-close-detail": "",
			"aria-label": "关闭详情",
			onClick: n[0] ||= (e) => r("close")
		}, " 关闭 ", 512)]), Y("dl", yp, [(K(!0), q(G, null, Yr(o.value, (e, t) => (K(), q("div", { key: `${t}:${e.label}` }, [Y("dt", null, j(e.label), 1), Y("dd", null, j(e.value), 1)]))), 128))])], 544));
	}
}), xp = class extends Error {
	status;
	code;
	constructor(e, t, n = "") {
		super(e), this.status = t, this.code = n, this.name = "ApiError";
	}
};
async function Sp(e, t = {}, n) {
	let r = await fetch(e, {
		credentials: "same-origin",
		...t
	});
	if (!(r.headers.get("content-type") || "").includes("application/json")) throw new xp(r.redirected || r.status === 401 ? "登录已失效，请重新登录后刷新。" : `服务返回了非 JSON 响应（HTTP ${r.status}）`, r.status);
	let i = n ? n(await r.text()) : await r.json();
	if (!r.ok || i?.ok === !1) {
		let e = i?.error;
		throw new xp(typeof e == "string" ? e : e?.message || i?.message || `请求失败（HTTP ${r.status}）`, r.status, e?.code || i?.error_code || i?.code || "");
	}
	return i;
}
function Cp(e) {
	return e instanceof Error && e.name === "AbortError";
}
// src/api/proxy.ts
var wp = /* @__PURE__ */ new Set([
	"id",
	"account_id",
	"operation_task_id",
	"operation_run_id",
	"registration_job_id",
	"registration_attempt_id",
	"registration_run_id"
]);
function Tp(e) {
	let t = e.replace(/("(?:[^"\\]|\\.)*")(?:(\s*:\s*)(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?))?/g, (e, t, n, r) => !n || !r || !/^\d+$/.test(r) || Number.isSafeInteger(Number(r)) ? e : wp.has(JSON.parse(t)) ? t + n + JSON.stringify(r) : e);
	return JSON.parse(t);
}
var Ep = {
	current: "/api/proxy-traffic/current",
	history: "/api/proxy-traffic/history",
	traffic: "/api/proxy-traffic/traffic"
};
function Dp(e, t) {
	let n = t;
	if (!n || typeof n != "object" || n.ok !== !0) throw Error("代理列表接口响应无效");
	if (n.view != null && n.view !== e) throw Error("代理列表接口视图不匹配");
	if (!Array.isArray(n.items)) throw Error("代理列表接口缺少 items");
	let r = Number(n.count), i = Number(n.total), a = Number(n.limit), o = Number(n.offset);
	if (!Number.isInteger(r) || r < 0 || r !== n.items.length || !Number.isInteger(i) || i < r || !Number.isInteger(a) || a < 1 || !Number.isInteger(o) || o < 0) throw Error("代理列表分页字段无效");
	return {
		items: n.items,
		count: r,
		total: i,
		limit: a,
		offset: o,
		has_more: typeof n.has_more == "boolean" ? n.has_more : o + r < i,
		aggregate: n.aggregate
	};
}
function Op() {
	return {
		async page(e, t, n) {
			let r = new URLSearchParams({
				limit: String(t.size),
				offset: String((t.page - 1) * t.size),
				window: t.window,
				purpose: e === "traffic" ? "all" : t.purpose,
				state: t.state,
				search: t.search.trim()
			});
			return Dp(e, await Sp(Ep[e] + "?" + r, { signal: n }, Tp));
		},
		async summary(e) {
			let t = await Sp("/api/proxy-traffic/summary", { signal: e });
			if (t?.ok !== !0 || !Number.isFinite(Number(t.total_bytes)) || !Number.isFinite(Number(t.today_bytes))) throw Error("流量统计接口响应无效");
			return t;
		},
		async pool(e) {
			try {
				let t = await Sp("/api/proxy-pool", { signal: e });
				return t?.ok === !0 && t.policy && t.counts && typeof t.counts == "object" ? {
					...t,
					items: Array.isArray(t.items) ? t.items : [],
					country_pools: Array.isArray(t.country_pools) ? t.country_pools : []
				} : null;
			} catch (e) {
				if (Cp(e)) throw e;
				return null;
			}
		}
	};
}
// src/features/proxy/useProxyTraffic.ts
var kp = [
	"current",
	"history",
	"traffic"
], Ap = () => ({
	page: 1,
	size: 20,
	total: 0,
	state: "all",
	items: [],
	aggregate: void 0
});
function jp(e = {}) {
	let t = e.api ?? Op(), n = /* @__PURE__ */ I(!1), r = /* @__PURE__ */ I(e.view ?? "pool"), i = /* @__PURE__ */ I("current"), a = /* @__PURE__ */ Ht({
		window: "all",
		purpose: "all",
		search: ""
	}), o = /* @__PURE__ */ Ht({
		current: Ap(),
		history: Ap(),
		traffic: Ap()
	}), s = /* @__PURE__ */ en(null), c = /* @__PURE__ */ en(null), l = /* @__PURE__ */ en(null), u = /* @__PURE__ */ I(!1), d = /* @__PURE__ */ I(""), f = /* @__PURE__ */ I(null), p = /* @__PURE__ */ Ht({
		current: 0,
		history: 0,
		traffic: 0
	}), m = /* @__PURE__ */ I(!document.hidden), h = Z(() => n.value && m.value), g = 0, _ = 0, v = !1, y = null, b, x, S = null, C = /* @__PURE__ */ new Set(), w = () => !v && n.value && !document.hidden;
	function T() {
		g++, _++, y?.abort(), y = null, clearTimeout(b), clearTimeout(x), b = x = void 0, S = null, u.value = !1;
	}
	function ee() {
		clearTimeout(x), w() && (x = setTimeout(() => {
			x = void 0, re();
		}, 3e4));
	}
	function te(e = null, t = 0) {
		T();
		let n = _;
		if (!w()) return;
		let r = () => {
			b = void 0, n === _ && w() && re(e);
		};
		t ? b = setTimeout(r, t) : jn(r);
	}
	function E(e) {
		let t = o[e];
		return {
			page: t.page,
			size: t.size,
			window: a.window,
			purpose: e === "traffic" ? "all" : a.purpose,
			state: t.state,
			search: a.search
		};
	}
	async function ne(e, n, r) {
		let i = await t.page(e, n, r), a = n.page;
		if (r.aborted) throw new DOMException("Aborted", "AbortError");
		return i.total === 0 ? {
			result: i,
			page: 1
		} : (i.offset >= i.total && (a = Math.max(1, Math.ceil(i.total / n.size)), i = await t.page(e, {
			...n,
			page: a
		}, r), i.total === 0 && (a = 1)), {
			result: i,
			page: a
		});
	}
	function D(e, t) {
		Object.assign(o[e], {
			items: t.result.items,
			total: t.result.total,
			page: t.page,
			aggregate: t.result.aggregate
		});
	}
	async function re(n = null) {
		if (!w()) return;
		s.value || (n = null);
		let r = n ? [n] : kp, i = Object.fromEntries(r.map((e) => [e, E(e)])), a = JSON.stringify([n, i]);
		if (S?.key === a) return S.promise;
		T();
		let l = g, f = new AbortController();
		y = f, u.value = !0;
		let m = (async () => {
			try {
				let a = t.pool(f.signal).catch((e) => {
					if (Cp(e)) throw e;
					return null;
				}), [o, u, m] = await Promise.all([
					Promise.all(r.map(async (e) => ({
						name: e,
						...await ne(e, i[e], f.signal)
					}))),
					n ? Promise.resolve(null) : t.summary(f.signal),
					a
				]);
				if (l !== g || !w()) return;
				o.forEach((e) => {
					D(e.name, e), C.delete(e.name) && p[e.name]++;
				}), u && (s.value = u), c.value = m, d.value = "", e.onReady?.();
			} catch (e) {
				if (l !== g || !w() || Cp(e)) return;
				kp.forEach((e) => {
					o[e].items = [], o[e].total = 0;
				}), s.value = null, c.value = null, d.value = e instanceof Error ? e.message : String(e);
			} finally {
				l === g && (u.value = !1, y = null, S = null, ee());
			}
		})();
		return S = {
			key: a,
			promise: m
		}, m;
	}
	function O(e = {}) {
		let t = l.value?.opener;
		l.value = null, e.restoreFocus !== !1 && t?.isConnected && jn(() => t.focus({ preventScroll: !0 }));
	}
	function ie(e) {
		v || n.value === e || (n.value = e, e ? te() : (T(), f.value = null, O({ restoreFocus: !1 })));
	}
	function ae(e) {
		!v && ["pool", "records"].includes(e) && r.value !== e && (r.value = e, f.value = null, O({ restoreFocus: !1 }));
	}
	function k(e) {
		!v && kp.includes(e) && i.value !== e && (i.value = e, f.value = null, O({ restoreFocus: !1 }));
	}
	function oe(e) {
		let t = Object.keys(e).filter((t) => e[t] !== void 0 && e[t] !== a[t]);
		t.length && !v && (t.forEach((t) => {
			a[t] = e[t];
		}), kp.forEach((e) => {
			o[e].page = 1, C.add(e);
		}), te(null, t.every((e) => e === "search") ? 260 : 0));
	}
	function se(e, t) {
		v || o[e].state === t || (o[e].state = t, o[e].page = 1, C.add(e), te(e));
	}
	function ce(e, t) {
		if (v || !Number.isFinite(t)) return;
		let n = o[e], r = Math.min(Math.max(1, Math.ceil(n.total / n.size)), Math.max(1, Math.floor(t)));
		r !== n.page && (n.page = r, C.add(e), te(e));
	}
	function le(e, t) {
		!v && [
			20,
			50,
			100
		].includes(t) && o[e].size !== t && (o[e].size = t, o[e].page = 1, C.add(e), te(e));
	}
	function ue() {
		Object.assign(a, {
			window: "all",
			purpose: "all",
			search: ""
		}), kp.forEach((e) => {
			o[e].state = "all", o[e].page = 1, C.add(e);
		}), te();
	}
	function de(e) {
		e.startsWith("state:") ? se(e.slice(6), "all") : e === "search" ? oe({ search: "" }) : (e === "window" || e === "purpose") && oe({ [e]: "all" });
	}
	function fe(e, t, n = null) {
		!v && w() && (l.value = {
			view: e,
			row: JSON.parse(JSON.stringify(t)),
			opener: n
		});
	}
	function pe() {
		m.value = !document.hidden, document.hidden ? (T(), f.value = null, O({ restoreFocus: !1 })) : n.value && te();
	}
	document.addEventListener("visibilitychange", pe);
	function A() {
		v || (v = !0, T(), O({ restoreFocus: !1 }), document.removeEventListener("visibilitychange", pe));
	}
	return ke(A), e.visible && ie(!0), {
		visible: n,
		active: h,
		documentVisible: m,
		view: r,
		recordView: i,
		filters: a,
		pages: o,
		summary: s,
		pool: c,
		detail: l,
		loading: u,
		error: d,
		openFilter: f,
		scrollRevision: p,
		load: re,
		setVisible: ie,
		setView: ae,
		setRecordView: k,
		updateFilters: oe,
		setState: se,
		setPage: ce,
		setSize: le,
		resetFilters: ue,
		removeFilter: de,
		openDetail: fe,
		closeDetail: O,
		dispose: A
	};
}
// src/features/proxy/ProxyTrafficPage.vue?vue&type=script&setup=true&lang.ts
var Mp = {
	class: "pt-root",
	"data-proxy-vue": ""
}, Np = {
	class: "pt-workspace",
	"data-proxy-module-panel": "records"
}, Pp = {
	class: "pt-summary",
	"aria-label": "租约与流量摘要"
}, Fp = { "data-proxy-summary": "totalBytes" }, Ip = { "data-proxy-summary": "todayBytes" }, Lp = { "data-proxy-summary": "todayRequestCount" }, Rp = { "data-proxy-summary": "todayRouteCount" }, zp = { class: "pt-tabs-row" }, Bp = [
	"data-proxy-view",
	"aria-selected",
	"aria-controls",
	"tabindex",
	"onClick"
], Vp = { class: "pt-toolbar" }, Hp = { class: "pt-toolbar-main" }, Up = {
	class: "pt-count",
	role: "status"
}, Wp = { class: "pt-toolbar-actions" }, Gp = { class: "pt-mobile-filter" }, Kp = [
	"id",
	"aria-label",
	"aria-hidden",
	"data-proxy-panel"
], qp = /* @__PURE__ */ H({
	__name: "ProxyTrafficPage",
	props: { deps: {} },
	setup(e, { expose: t }) {
		let n = e, r = jp(n.deps), { view: i, recordView: a, filters: o, pages: s, summary: c, pool: l, detail: u, loading: d, error: f, active: p, openFilter: m } = r, h = /* @__PURE__ */ I({}), g = [
			"current",
			"history",
			"traffic"
		], _ = {
			current: "当前租约",
			history: "线路历史",
			traffic: "请求流量"
		}, v = Z(() => Jf(o, {
			current: s.current.state,
			history: s.history.state,
			traffic: s.traffic.state
		})), y = Z(() => s[a.value]);
		function b(e, t, n) {
			t === "state" ? r.setState(e, n) : r.updateFilters({ [t]: n });
		}
		function x() {
			h.value[a.value]?.resetColumns(), n.deps.notify?.("已恢复默认列宽");
		}
		function S(e) {
			if (![
				"ArrowLeft",
				"ArrowRight",
				"Home",
				"End"
			].includes(e.key)) return;
			e.preventDefault();
			let t = g.indexOf(a.value), n = e.key === "Home" ? 0 : e.key === "End" ? g.length - 1 : (t + (e.key === "ArrowRight" ? 1 : -1) + g.length) % g.length;
			r.setRecordView(g[n]), e.currentTarget.querySelector(`[data-proxy-view="${g[n]}"]`)?.focus({ preventScroll: !0 });
		}
		return t({
			load: r.load,
			setVisible: r.setVisible,
			setView: r.setView,
			closeDetail: r.closeDetail
		}), (t, n) => (K(), q("div", Mp, [
			Wn(X(Dc, {
				pool: L(l),
				loading: L(d)
			}, null, 8, ["pool", "loading"]), [[xo, L(i) === "pool"]]),
			Wn(Y("div", Np, [
				Y("div", Pp, [
					Y("div", null, [n[6] ||= Y("span", null, "累计可观测流量", -1), Y("strong", Fp, j(L(c) ? L(ec)(L(c).total_bytes) : "—"), 1)]),
					Y("div", null, [n[7] ||= Y("span", null, "今日可观测流量", -1), Y("strong", Ip, j(L(c) ? L(ec)(L(c).today_bytes) : "—"), 1)]),
					Y("div", null, [n[8] ||= Y("span", null, "今日请求记录", -1), Y("strong", Lp, j(L(c) ? L(c).today_request_count ?? L(c).today_browser_count ?? "—" : "—"), 1)]),
					Y("div", null, [n[9] ||= Y("span", null, "今日新建线路", -1), Y("strong", Rp, j(L(c)?.today_route_count ?? "—"), 1)])
				]),
				Y("div", zp, [Y("div", {
					class: "pt-view-tabs",
					role: "tablist",
					"aria-label": "代理与流量视图",
					onKeydown: S
				}, [(K(), q(G, null, Yr(g, (e) => Y("button", {
					key: e,
					type: "button",
					role: "tab",
					"data-proxy-view": e,
					"aria-selected": L(a) === e,
					"aria-controls": `proxy-panel-${e}`,
					tabindex: L(a) === e ? 0 : -1,
					class: A({ "is-active": L(a) === e }),
					onClick: (t) => L(r).setRecordView(e)
				}, [ka(j(_[e]) + " ", 1), Y("span", null, j(L(f) ? "—" : L(s)[e].total), 1)], 10, Bp)), 64))], 32)]),
				Y("div", Vp, [Y("div", Hp, [Y("span", Up, j(L(f) ? "数据暂不可用" : `${y.value.total.toLocaleString()} 条记录`), 1), X(Ss, {
					items: v.value,
					onRemove: L(r).removeFilter
				}, null, 8, ["items", "onRemove"])]), Y("div", Wp, [
					Y("span", Gp, [X(rp, {
						view: L(a),
						filters: L(o),
						state: y.value.state,
						summary: L(c),
						open: L(p) && L(m) === "all",
						onChange: n[0] ||= (e, t) => b(L(a), e, t),
						"onUpdate:open": n[1] ||= (e) => m.value = e ? "all" : null
					}, null, 8, [
						"view",
						"filters",
						"state",
						"summary",
						"open"
					])]),
					v.value.length ? (K(), q("button", {
						key: 0,
						type: "button",
						class: "pt-link",
						onClick: n[2] ||= (...e) => L(r).resetFilters && L(r).resetFilters(...e)
					}, " 清筛")) : Aa("", !0),
					Y("button", {
						type: "button",
						class: "pt-link",
						"aria-label": "恢复当前列表列宽",
						onClick: x
					}, " 恢复列宽 ")
				])]),
				(K(), q(G, null, Yr(g, (t) => Wn(Y("section", {
					id: `proxy-panel-${t}`,
					key: t,
					role: "tabpanel",
					"aria-label": _[t],
					"aria-hidden": L(a) !== t,
					"data-proxy-panel": t,
					class: "pt-panel"
				}, [X(gp, {
					ref_for: !0,
					ref: (e) => {
						e && (h.value[t] = e);
					},
					view: t,
					items: L(s)[t].items,
					filters: L(o),
					state: L(s)[t].state,
					summary: L(c),
					loading: L(d),
					error: L(f),
					visible: L(p) && L(i) === "records" && L(a) === t,
					"open-filter": L(m),
					"scroll-revision": L(r).scrollRevision[t],
					"facet-label": e.deps.facetLabel,
					onFilter: (e, n) => b(t, e, n),
					"onUpdate:openFilter": n[3] ||= (e) => m.value = e,
					onDetail: L(r).openDetail,
					onRetry: n[4] ||= (e) => L(r).load()
				}, null, 8, [
					"view",
					"items",
					"filters",
					"state",
					"summary",
					"loading",
					"error",
					"visible",
					"open-filter",
					"scroll-revision",
					"facet-label",
					"onFilter",
					"onDetail"
				]), X(Vs, {
					page: L(s)[t].page,
					size: L(s)[t].size,
					total: L(s)[t].total,
					busy: L(d),
					"page-sizes": [
						20,
						50,
						100
					],
					label: `${_[t]}分页`,
					"onUpdate:page": (e) => L(r).setPage(t, e),
					"onUpdate:size": (e) => L(r).setSize(t, e)
				}, null, 8, [
					"page",
					"size",
					"total",
					"busy",
					"label",
					"onUpdate:page",
					"onUpdate:size"
				])], 8, Kp), [[xo, L(a) === t]])), 64))
			], 512), [[xo, L(i) === "records"]]),
			X(bp, {
				snapshot: L(u),
				"facet-label": e.deps.facetLabel,
				onClose: n[5] ||= (e) => L(r).closeDetail()
			}, null, 8, ["snapshot", "facet-label"])
		]));
	}
});
// src/proxy.ts
function Jp(e, t = {}) {
	let n = hs(qp, { deps: t }), r = n.mount(e);
	return {
		load: r.load,
		setVisible: r.setVisible,
		setView: r.setView,
		closeDetail: r.closeDetail,
		destroy: () => n.unmount()
	};
}
export { Jp as mountProxyTraffic };
