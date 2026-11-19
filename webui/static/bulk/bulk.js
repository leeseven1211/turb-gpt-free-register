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
}, te = /-\w/g, E = /* @__PURE__ */ ee((e) => e.replace(te, (e) => e.slice(1).toUpperCase())), ne = /\B([A-Z])/g, D = /* @__PURE__ */ ee((e) => e.replace(ne, "-$1").toLowerCase()), re = /* @__PURE__ */ ee((e) => e.charAt(0).toUpperCase() + e.slice(1)), ie = /* @__PURE__ */ ee((e) => e ? `on${re(e)}` : ""), ae = (e, t) => !Object.is(e, t), oe = (e, ...t) => {
	for (let n = 0; n < e.length; n++) e[n](...t);
}, O = (e, t, n, r = !1) => {
	Object.defineProperty(e, t, {
		configurable: !0,
		enumerable: !1,
		writable: r,
		value: n
	});
}, se = (e) => {
	let t = parseFloat(e);
	return isNaN(t) ? e : t;
}, ce, le = () => ce ||= typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {};
function ue(e) {
	if (d(e)) {
		let t = {};
		for (let n = 0; n < e.length; n++) {
			let r = e[n], i = g(r) ? me(r) : ue(r);
			if (i) for (let e in i) t[e] = i[e];
		}
		return t;
	}
	if (g(e) || v(e)) return e;
}
var de = /;(?![^(]*\))/g, fe = /:([^]+)/, pe = /"(?:[^"\\]|\\[^])*"|'(?:[^'\\]|\\[^])*'|\\[^]|\/\*[^]*?\*\//g;
function me(e) {
	let t = {};
	return e.replace(pe, (e) => e.startsWith("/*") ? "" : e).split(de).forEach((e) => {
		if (e) {
			let n = e.split(fe);
			n.length > 1 && (t[n[0].trim()] = n[1].trim());
		}
	}), t;
}
function k(e) {
	let t = "";
	if (g(e)) t = e;
	else if (d(e)) for (let n = 0; n < e.length; n++) {
		let r = k(e[n]);
		r && (t += r + " ");
	}
	else if (v(e)) for (let n in e) e[n] && (t += n + " ");
	return t.trim();
}
function he(e) {
	if (!e) return null;
	let { class: t, style: n } = e;
	return t && !g(t) && (e.class = k(t)), n && (e.style = ue(n)), e;
}
var ge = /* @__PURE__ */ e("itemscope,allowfullscreen,disablepictureinpicture,disableremoteplayback,formnovalidate,ismap,nomodule,novalidate,playsinline,readonly");
function _e(e) {
	return !!e || e === "";
}
function ve(e, t, n) {
	if (e.length !== t.length) return !1;
	let r = !0;
	for (let i = 0; r && i < e.length; i++) r = Se(e[i], t[i], n);
	return r;
}
function ye(e, t, n) {
	if (e.size !== t.size) return !1;
	let r = Array.from(t), i = new Uint8Array(r.length);
	for (let t of e) {
		let e = -1;
		for (let a = 0; a < r.length; a++) if (!i[a] && Se(t, r[a], n)) {
			e = a;
			break;
		}
		if (e < 0) return !1;
		i[e] = 1;
	}
	return !0;
}
function be(e, t, n) {
	let r = f(e), i = f(t);
	if (r || i || (r = p(e), i = p(t), r || i)) return r && i ? ye(e, t, n) : !1;
	if (Object.keys(e).length !== Object.keys(t).length) return !1;
	for (let r in e) {
		let i = e.hasOwnProperty(r), a = t.hasOwnProperty(r);
		if (i && !a || !i && a || !Se(e[r], t[r], n)) return !1;
	}
	return String(e) === String(t);
}
function xe(e, t, n, r) {
	n ||= [/* @__PURE__ */ new Map(), /* @__PURE__ */ new Map()];
	let [i, a] = n;
	if (i.has(e) || a.has(t)) return i.get(e) === t && a.get(t) === e;
	i.set(e, t), a.set(t, e);
	let o = r(e, t, n);
	return i.delete(e), a.delete(t), o;
}
function Se(e, t, n) {
	if (e === t) return !0;
	let r = m(e), i = m(t);
	return r || i ? r && i ? e.getTime() === t.getTime() : !1 : (r = _(e), i = _(t), r || i ? e === t : (r = d(e), i = d(t), r || i ? r && i ? xe(e, t, n, ve) : !1 : (r = v(e), i = v(t), r || i ? !r || !i ? !1 : xe(e, t, n, be) : String(e) === String(t))));
}
var Ce = (e) => !!(e && e.__v_isRef === !0), A = (e) => g(e) ? e : e == null ? "" : d(e) || v(e) && (e.toString === b || !h(e.toString)) ? Ce(e) ? A(e.value) : JSON.stringify(e, we, 2) : String(e), we = (e, t) => Ce(t) ? we(e, t.value) : f(t) ? { [`Map(${t.size})`]: [...t.entries()].reduce((e, [t, n], r) => (e[Te(t, r) + " =>"] = n, e), {}) } : p(t) ? { [`Set(${t.size})`]: [...t.values()].map((e) => Te(e)) } : _(t) ? Te(t) : v(t) && !d(t) && !C(t) ? String(t) : t, Te = (e, t = "") => _(e) ? `Symbol(${e.description ?? t})` : e, j, Ee = class {
	constructor(e = !1) {
		this.detached = e, this._active = !0, this._on = 0, this.effects = [], this.cleanups = [], this._isPaused = !1, this._warnOnRun = !0, this.__v_skip = !0, !e && j && (j.active ? (this.parent = j, this.index = (j.scopes || (j.scopes = [])).push(this) - 1) : (this._active = !1, this._warnOnRun = !1));
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
			let t = j;
			try {
				return j = this, e();
			} finally {
				j = t;
			}
		}
	}
	on() {
		++this._on === 1 && (this.prevScope = j, j = this);
	}
	off() {
		if (this._on > 0 && --this._on === 0) {
			if (j === this) j = this.prevScope;
			else {
				let e = j;
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
	return j;
}
function ke(e, t = !1) {
	j && (j.active ? j.cleanups.push(e) : e());
}
var M, Ae = /* @__PURE__ */ new WeakSet(), je = class {
	constructor(e) {
		this.fn = e, this.deps = void 0, this.depsTail = void 0, this.flags = 5, this.next = void 0, this.cleanup = void 0, this.scheduler = void 0, j && (j.active ? j.effects.push(this) : this.flags &= -2);
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
		let e = M, t = We;
		M = this, We = !0;
		try {
			return this.fn();
		} finally {
			ze(this), M = e, We = t, this.flags &= -3;
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
	let t = e.dep, n = M, r = We;
	M = e, We = !0;
	try {
		Re(e);
		let n = e.fn(e._value);
		(t.version === 0 || ae(n, e._value)) && (e.flags |= 128, e._value = n, t.version++);
	} catch (e) {
		throw t.version++, e;
	} finally {
		M = n, We = r, ze(e), e.flags &= -3;
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
		let e = M;
		M = void 0;
		try {
			t();
		} finally {
			M = e;
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
		if (!M || !We || M === this.computed) return;
		let t = this.activeLink;
		if (t === void 0 || t.sub !== M) t = this.activeLink = new Xe(M, this), M.deps ? (t.prevDep = M.depsTail, M.depsTail.nextDep = t, M.depsTail = t) : M.deps = M.depsTail = t, Qe(t);
		else if (t.version === -1 && (t.version = this.version, t.nextDep)) {
			let e = t.nextDep;
			e.prevDep = t.prevDep, t.prevDep && (t.prevDep.nextDep = e), t.prevDep = M.depsTail, t.nextDep = void 0, M.depsTail.nextDep = t, M.depsTail = t, M.deps === t && (M.deps = e);
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
	if (We && M) {
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
	let t = /* @__PURE__ */ N(e);
	return t === e || (rt(t, "iterate", nt), /* @__PURE__ */ Yt(e)) ? t : /* @__PURE__ */ Jt(e) ? /* @__PURE__ */ qt(e) ? t.map((e) => $t(Qt(e))) : t.map($t) : t.map(Qt);
}
function st(e) {
	return rt(e = /* @__PURE__ */ N(e), "iterate", nt), e;
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
	let r = /* @__PURE__ */ N(e);
	rt(r, "iterate", nt);
	let i = r[t](...n);
	return (i === -1 || i === !1) && /* @__PURE__ */ Xt(n[0]) ? (n[0] = /* @__PURE__ */ N(n[0]), r[t](...n)) : i;
}
function gt(e, t, n = []) {
	Ke(), Ie();
	let r = (/* @__PURE__ */ N(e))[t].apply(e, n);
	return Le(), qe(), r;
}
var _t = /* @__PURE__ */ e("__proto__,__v_isRef,__isVue"), vt = /* @__PURE__ */ new Set(/* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(_));
function yt(e) {
	_(e) || (e = String(e));
	let t = /* @__PURE__ */ N(this);
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
		let o = Reflect.get(e, t, /* @__PURE__ */ P(e) ? e : n);
		if ((_(t) ? vt.has(t) : _t(t)) || (r || rt(e, "get", t), i)) return o;
		if (/* @__PURE__ */ P(o)) {
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
			if (!/* @__PURE__ */ Yt(n) && !/* @__PURE__ */ Jt(n) && (i = /* @__PURE__ */ N(i), n = /* @__PURE__ */ N(n)), !a && /* @__PURE__ */ P(i) && !/* @__PURE__ */ P(n)) return e || (i.value = n), !0;
		}
		let o = a ? Number(t) < e.length : u(e, t), s = Reflect.set(e, t, n, /* @__PURE__ */ P(e) ? e : r);
		return e === /* @__PURE__ */ N(r) && s && (o ? ae(n, i) && it(e, "set", t, n, i) : it(e, "add", t, n)), s;
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
		let i = this.__v_raw, a = /* @__PURE__ */ N(i), o = f(a), c = e === "entries" || e === Symbol.iterator && o, l = e === "keys" && o, u = i[e](...r), d = n ? Dt : t ? $t : Qt;
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
			let r = this.__v_raw, i = /* @__PURE__ */ N(r), a = /* @__PURE__ */ N(n);
			e || (ae(n, a) && rt(i, "get", n), rt(i, "get", a));
			let { has: o } = Ot(i), s = t ? Dt : e ? $t : Qt;
			if (o.call(i, n)) return s(r.get(n));
			if (o.call(i, a)) return s(r.get(a));
			r !== i && r.get(n);
		},
		get size() {
			let t = this.__v_raw;
			return !e && rt(/* @__PURE__ */ N(t), "iterate", et), t.size;
		},
		has(t) {
			let n = this.__v_raw, r = /* @__PURE__ */ N(n), i = /* @__PURE__ */ N(t);
			return e || (ae(t, i) && rt(r, "has", t), rt(r, "has", i)), t === i ? n.has(t) : n.has(t) || n.has(i);
		},
		forEach(n, r) {
			let i = this, a = i.__v_raw, o = /* @__PURE__ */ N(a), s = t ? Dt : e ? $t : Qt;
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
			let n = /* @__PURE__ */ N(this), r = Ot(n), i = /* @__PURE__ */ N(e), a = !t && !/* @__PURE__ */ Yt(e) && !/* @__PURE__ */ Jt(e) ? i : e;
			return r.has.call(n, a) || ae(e, a) && r.has.call(n, e) || ae(i, a) && r.has.call(n, i) || (n.add(a), it(n, "add", a, a)), this;
		},
		set(e, n) {
			t || /* @__PURE__ */ Yt(n) || /* @__PURE__ */ Jt(n) || (n = /* @__PURE__ */ N(n));
			let r = /* @__PURE__ */ N(this), { has: i, get: a } = Ot(r), o = i.call(r, e);
			o ||= (e = /* @__PURE__ */ N(e), i.call(r, e));
			let s = a.call(r, e);
			return r.set(e, n), o ? ae(n, s) && it(r, "set", e, n, s) : it(r, "add", e, n), this;
		},
		delete(e) {
			let t = /* @__PURE__ */ N(this), { has: n, get: r } = Ot(t), i = n.call(t, e);
			i ||= (e = /* @__PURE__ */ N(e), n.call(t, e));
			let a = r ? r.call(t, e) : void 0, o = t.delete(e);
			return i && it(t, "delete", e, void 0, a), o;
		},
		clear() {
			let e = /* @__PURE__ */ N(this), t = e.size !== 0, n = e.clear();
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
function N(e) {
	let t = e && e.__v_raw;
	return t ? /* @__PURE__ */ N(t) : e;
}
function Zt(e) {
	return !u(e, "__v_skip") && Object.isExtensible(e) && O(e, "__v_skip", !0), e;
}
var Qt = (e) => v(e) ? /* @__PURE__ */ Ht(e) : e, $t = (e) => v(e) ? /* @__PURE__ */ Wt(e) : e;
// @__NO_SIDE_EFFECTS__
function P(e) {
	return e ? e.__v_isRef === !0 : !1;
}
// @__NO_SIDE_EFFECTS__
function F(e) {
	return tn(e, !1);
}
// @__NO_SIDE_EFFECTS__
function en(e) {
	return tn(e, !0);
}
function tn(e, t) {
	return /* @__PURE__ */ P(e) ? e : new nn(e, t);
}
var nn = class {
	constructor(e, t) {
		this.dep = new Ze(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = t ? e : /* @__PURE__ */ N(e), this._value = t ? e : Qt(e), this.__v_isShallow = t;
	}
	get value() {
		return this.dep.track(), this._value;
	}
	set value(e) {
		let t = this._rawValue, n = this.__v_isShallow || /* @__PURE__ */ Yt(e) || /* @__PURE__ */ Jt(e);
		e = n ? e : /* @__PURE__ */ N(e), ae(e, t) && (this._rawValue = e, this._value = n ? e : Qt(e), this.dep.trigger());
	}
};
function rn(e) {
	e.dep && e.dep.trigger();
}
function I(e) {
	return /* @__PURE__ */ P(e) ? e.value : e;
}
function L(e) {
	return h(e) ? e() : I(e);
}
var an = {
	get: (e, t, n) => t === "__v_raw" ? e : I(Reflect.get(e, t, n)),
	set: (e, t, n, r) => {
		let i = e[t];
		return /* @__PURE__ */ P(i) && !/* @__PURE__ */ P(n) ? (i.value = n, !0) : Reflect.set(e, t, n, r);
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
		this._object = e, this._defaultValue = n, this.__v_isRef = !0, this._value = void 0, this._key = _(t) ? t : String(t), this._raw = /* @__PURE__ */ N(e);
		let r = !0, i = e;
		if (!d(e) || _(this._key) || !w(this._key)) do
			r = !/* @__PURE__ */ Xt(i) || /* @__PURE__ */ Yt(i);
		while (r && (i = i.__v_raw));
		this._shallow = r;
	}
	get value() {
		let e = this._object[this._key];
		return this._shallow && (e = I(e)), this._value = e === void 0 ? this._defaultValue : e;
	}
	set value(e) {
		if (this._shallow && /* @__PURE__ */ P(this._raw[this._key])) {
			let t = this._object[this._key];
			if (/* @__PURE__ */ P(t)) {
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
	return /* @__PURE__ */ P(e) ? e : h(e) ? new ln(e) : v(e) && arguments.length > 1 ? dn(e, t, n) : /* @__PURE__ */ F(e);
}
function dn(e, t, n) {
	return new cn(e, t, n);
}
var fn = class {
	constructor(e, t, n) {
		this.fn = e, this.setter = t, this._value = void 0, this.dep = new Ze(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = Ye - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !t, this.isSSR = n;
	}
	notify() {
		if (this.flags |= 16, !(this.flags & 8) && M !== this) return Fe(this, !0), !0;
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
	if (/* @__PURE__ */ P(e) ? (g = () => e.value, y = /* @__PURE__ */ Yt(e)) : /* @__PURE__ */ qt(e) ? (g = () => p(e), y = !0) : d(e) ? (b = !0, y = e.some((e) => /* @__PURE__ */ qt(e) || /* @__PURE__ */ Yt(e)), g = () => e.map((e) => {
		if (/* @__PURE__ */ P(e)) return e.value;
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
				if (e || o || y || (b ? t.some((e, t) => ae(e, C[t])) : ae(t, C))) {
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
	if (n.set(e, t), t--, /* @__PURE__ */ P(e)) yn(e.value, t, n);
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
var R = null, Hn = null;
function Un(e) {
	let t = R;
	return R = e, Hn = e && e.type.__scopeId || null, t;
}
function z(e, t = R, n) {
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
	if (R === null) return e;
	let r = $a(R), i = e.dirs ||= [];
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
	if (Ra) {
		let n = Ra.provides, r = Ra.parent && Ra.parent.provides;
		r === n && (n = Ra.provides = Object.create(r)), n[e] = t;
	}
}
function qn(e, t, n = !1) {
	let r = za();
	if (r || xi) {
		let i = xi ? xi._context.provides : r ? r.parent == null || r.ce ? r.vnode.appContext && r.vnode.appContext.provides : r.parent.provides : void 0;
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
function B(e, t, n) {
	return Qn(e, t, n);
}
function Qn(e, n, i = t) {
	let { immediate: a, deep: o, flush: c, once: l } = i, u = s({}, i), d = n && a || !n && c !== "post", f;
	if (Ga) {
		if (c === "sync") {
			let e = Yn();
			f = e.__watcherHandles ||= [];
		} else if (!d) {
			let e = () => {};
			return e.stop = r, e.resume = r, e.pause = r, e;
		}
	}
	let p = Ra;
	u.call = (e, t, n) => xn(e, p, t, n);
	let m = !1;
	c === "post" ? u.scheduler = (e) => {
		e.i = p, $i(e, p && p.suspense);
	} : c !== "sync" && (m = !0, u.scheduler = (e, t) => {
		t ? e() : Nn(e);
	}), u.augmentJob = (e) => {
		n && (e.flags |= 4), m && (e.flags |= 2, p && (e.id = p.uid, e.i = p));
	};
	let h = vn(e, n, u);
	return Ga && (f ? f.push(h) : d && h()), h;
}
function $n(e, t, n) {
	let r = this.proxy, i = g(e) ? e.includes(".") ? er(r, e) : () => r[e] : e.bind(r, r), a;
	h(t) ? a = t : (a = t.handler, n = t);
	let o = Ha(this), s = Qn(i, a.bind(r), n);
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
			tr.set(e, t), $i(t, a);
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
	} else if (e.transition = t, e.type === U && d(e.children)) {
		let n = Oi(e.children, !1);
		n && vr(n, t);
	}
}
function yr(e) {
	if (e.component) return yr(e.component.subTree);
	if (e.type === U) {
		let t = d(e.children) && Oi(e.children, !1);
		return t ? yr(t) : void 0;
	}
	if (e.type !== ma) return e;
}
// @__NO_SIDE_EFFECTS__
function V(e, t) {
	return h(e) ? /* @__PURE__ */ s({ name: e.name }, t, { setup: e }) : e;
}
function br() {
	let e = za();
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
	let s = a.shapeFlag & 4 ? $a(a.component) : a.el, l = o ? null : s, { i: f, r: p } = e, m = n && n.r, _ = f.refs === t ? f.refs = {} : f.refs, v = f.setupState, y = /* @__PURE__ */ N(v), b = v === t ? i : (e) => !Sr(_, e) && u(y, e), x = (e, t) => !(t && Sr(_, t));
	if (m != null && m !== p) {
		if (Tr(n), g(m)) _[m] = null, b(m) && (v[m] = null);
		else if (/* @__PURE__ */ P(m)) {
			let e = n;
			x(m, e.k) && (m.value = null), e.k && (_[e.k] = null);
		}
	}
	if (h(p)) bn(p, f, 12, [l, _]);
	else {
		let t = g(p), n = /* @__PURE__ */ P(p);
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
				t.id = -1, Cr.set(e, t), $i(t, r);
			} else Tr(e), i();
		}
	}
}
function Tr(e) {
	let t = Cr.get(e);
	t && (t.flags |= 8, Cr.delete(e));
}
le().requestIdleCallback, le().cancelIdleCallback;
var Er = (e) => !!e.type.__asyncLoader, Dr = (e) => e.type.__isKeepAlive;
function Or(e, t) {
	Ar(e, "a", t);
}
function kr(e, t) {
	Ar(e, "da", t);
}
function Ar(e, t, n = Ra) {
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
function Mr(e, t, n = Ra, r = !1) {
	if (n) {
		let i = n[e] || (n[e] = []), a = t.__weh ||= (...r) => {
			Ke();
			let i = Ha(n), a = xn(t, n, e, r);
			return i(), qe(), a;
		};
		return r ? i.unshift(a) : i.push(a), a;
	}
}
var Nr = (e) => (t, n = Ra) => {
	Ga && e !== "sp" || Mr(e, (...e) => t(...e), n);
}, Pr = Nr("bm"), Fr = Nr("m"), Ir = Nr("bu"), Lr = Nr("u"), Rr = Nr("bum"), zr = Nr("um"), Br = Nr("sp"), Vr = Nr("rtg"), Hr = Nr("rtc");
function Ur(e, t = Ra) {
	Mr("ec", e, t);
}
var Wr = "components", Gr = /* @__PURE__ */ Symbol.for("v-ndc");
function Kr(e) {
	return g(e) ? qr(Wr, e, !1) || e : e || Gr;
}
function qr(e, t, n = !0, r = !1) {
	let i = R || Ra;
	if (i) {
		let n = i.type;
		if (e === Wr) {
			let e = eo(n, !1);
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
function H(e, t, n, r, i, a) {
	if (n ??= {}, R.ce || R.parent && Er(R.parent) && R.parent.ce) {
		let e = a != null && n.key == null ? s({}, n, { key: a }) : n, i = Object.keys(e).length > 0;
		return t !== "default" && (e.name = t), W(), K(U, null, [J("slot", e, r && r())], i ? -2 : 64);
	}
	let o = e[t];
	o && o._c && (o._d = !1);
	let c = ga.length;
	W();
	let l;
	try {
		let i = o && Xr(o(n)), s = n.key || a || i && i.key;
		l = K(U, { key: (s && !_(s) ? s : `_${t}`) + (!i && r ? "_fb" : "") }, i || (r ? r() : []), i && e._ === 1 ? 64 : -2);
	} catch (e) {
		for (let e = ga.length; e > c; e--) va();
		throw e;
	} finally {
		o && o._c && (o._d = !0);
	}
	return !i && l.scopeId && (l.slotScopeIds = [l.scopeId + "-s"]), l;
}
function Xr(e) {
	return e.some((e) => !Sa(e) || !(e.type === ma || e.type === U && !Xr(e.children))) ? e : null;
}
var Zr = (e) => e ? Wa(e) ? $a(e) : Zr(e.parent) : null, Qr = /* @__PURE__ */ s(/* @__PURE__ */ Object.create(null), {
	$: (e) => e,
	$el: (e) => e.vnode.el,
	$data: (e) => e.data,
	$props: (e) => e.props,
	$attrs: (e) => e.attrs,
	$slots: (e) => e.slots,
	$refs: (e) => e.refs,
	$parent: (e) => Zr(e.parent),
	$root: (e) => Zr(e.root),
	$host: (e) => e.ce,
	$emit: (e) => e.emit,
	$options: (e) => ci(e),
	$forceUpdate: (e) => e.f ||= () => {
		Nn(e.update);
	},
	$nextTick: (e) => e.n ||= jn.bind(e.proxy),
	$watch: (e) => $n.bind(e)
}), $r = (e, n) => e !== t && !e.__isScriptSetup && u(e, n), ei = {
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
			else if ($r(i, n)) return s[n] = 1, i[n];
			else if (a !== t && u(a, n)) return s[n] = 2, a[n];
			else if (u(o, n)) return s[n] = 3, o[n];
			else if (r !== t && u(r, n)) return s[n] = 4, r[n];
			else ri && (s[n] = 0);
		}
		let d = Qr[n], f, p;
		if (d) return n === "$attrs" && rt(e.attrs, "get", ""), d(e);
		if ((f = c.__cssModules) && (f = f[n])) return f;
		if (r !== t && u(r, n)) return s[n] = 4, r[n];
		if (p = l.config.globalProperties, u(p, n)) return p[n];
	},
	set({ _: e }, n, r) {
		let { data: i, setupState: a, ctx: o } = e;
		return $r(a, n) ? (a[n] = r, !0) : i !== t && u(i, n) ? (i[n] = r, !0) : u(e.props, n) || n[0] === "$" && n.slice(1) in e ? !1 : (o[n] = r, !0);
	},
	has({ _: { data: e, setupState: n, accessCache: r, ctx: i, appContext: a, props: o, type: s } }, c) {
		let l;
		return !!(r[c] || e !== t && c[0] !== "$" && u(e, c) || $r(n, c) || u(o, c) || u(i, c) || u(Qr, c) || u(a.config.globalProperties, c) || (l = s.__cssModules) && l[c]);
	},
	defineProperty(e, t, n) {
		return n.get == null ? u(n, "value") && this.set(e, t, n.value, null) : e._.accessCache[t] = 0, Reflect.defineProperty(e, t, n);
	}
};
function ti(e) {
	return d(e) ? e.reduce((e, t) => (e[t] = null, e), {}) : e;
}
function ni(e, t) {
	let n = ti(e);
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
var ri = !0;
function ii(e) {
	let t = ci(e), n = e.proxy, i = e.ctx;
	ri = !1, t.beforeCreate && oi(t.beforeCreate, e, "bc");
	let { data: a, computed: o, methods: s, watch: c, provide: l, inject: u, created: f, beforeMount: p, mounted: m, beforeUpdate: g, updated: _, activated: y, deactivated: b, beforeDestroy: x, beforeUnmount: S, destroyed: C, unmounted: w, render: T, renderTracked: ee, renderTriggered: te, errorCaptured: E, serverPrefetch: ne, expose: D, inheritAttrs: re, components: ie, directives: ae, filters: oe } = t;
	if (u && ai(u, i, null), s) for (let e in s) {
		let t = s[e];
		h(t) && (i[e] = t.bind(n));
	}
	if (a) {
		let t = a.call(n, n);
		v(t) && (e.data = /* @__PURE__ */ Ht(t));
	}
	if (ri = !0, o) for (let e in o) {
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
	if (c) for (let e in c) si(c[e], i, n, e);
	if (l) {
		let e = h(l) ? l.call(n) : l;
		Reflect.ownKeys(e).forEach((t) => {
			Kn(t, e[t]);
		});
	}
	f && oi(f, e, "c");
	function O(e, t) {
		d(t) ? t.forEach((t) => e(t.bind(n))) : t && e(t.bind(n));
	}
	if (O(Pr, p), O(Fr, m), O(Ir, g), O(Lr, _), O(Or, y), O(kr, b), O(Ur, E), O(Hr, ee), O(Vr, te), O(Rr, S), O(zr, w), O(Br, ne), d(D)) {
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
	T && e.render === r && (e.render = T), re != null && (e.inheritAttrs = re), ie && (e.components = ie), ae && (e.directives = ae), ne && xr(e);
}
function ai(e, t, n = r) {
	d(e) && (e = pi(e));
	for (let n in e) {
		let r = e[n], i;
		i = v(r) ? "default" in r ? qn(r.from || n, r.default, !0) : qn(r.from || n) : qn(r), /* @__PURE__ */ P(i) ? Object.defineProperty(t, n, {
			enumerable: !0,
			configurable: !0,
			get: () => i.value,
			set: (e) => i.value = e
		}) : t[n] = i;
	}
}
function oi(e, t, n) {
	xn(d(e) ? e.map((e) => e.bind(t.proxy)) : e.bind(t.proxy), t, n);
}
function si(e, t, n, r) {
	let i = r.includes(".") ? er(n, r) : () => n[r];
	if (g(e)) {
		let n = t[e];
		h(n) && B(i, n);
	} else if (h(e)) B(i, e.bind(n));
	else if (v(e)) {
		if (d(e)) e.forEach((e) => si(e, t, n, r));
		else {
			let r = h(e.handler) ? e.handler.bind(n) : t[e.handler];
			h(r) && B(i, r, e);
		}
	}
}
function ci(e) {
	let t = e.type, { mixins: n, extends: r } = t, { mixins: i, optionsCache: a, config: { optionMergeStrategies: o } } = e.appContext, s = a.get(t), c;
	return s ? c = s : !i.length && !n && !r ? c = t : (c = {}, i.length && i.forEach((e) => li(c, e, o, !0)), li(c, t, o)), v(t) && a.set(t, c), c;
}
function li(e, t, n, r = !1) {
	let { mixins: i, extends: a } = t;
	a && li(e, a, n, !0), i && i.forEach((t) => li(e, t, n, !0));
	for (let i in t) if (!(r && i === "expose")) {
		let r = ui[i] || n && n[i];
		e[i] = r ? r(e[i], t[i]) : t[i];
	}
	return e;
}
var ui = {
	data: di,
	props: gi,
	emits: gi,
	methods: hi,
	computed: hi,
	beforeCreate: mi,
	created: mi,
	beforeMount: mi,
	mounted: mi,
	beforeUpdate: mi,
	updated: mi,
	beforeDestroy: mi,
	beforeUnmount: mi,
	destroyed: mi,
	unmounted: mi,
	activated: mi,
	deactivated: mi,
	errorCaptured: mi,
	serverPrefetch: mi,
	components: hi,
	directives: hi,
	watch: _i,
	provide: di,
	inject: fi
};
function di(e, t) {
	return t ? e ? function() {
		return s(h(e) ? e.call(this, this) : e, h(t) ? t.call(this, this) : t);
	} : t : e;
}
function fi(e, t) {
	return hi(pi(e), pi(t));
}
function pi(e) {
	if (d(e)) {
		let t = {};
		for (let n = 0; n < e.length; n++) t[e[n]] = e[n];
		return t;
	}
	return e;
}
function mi(e, t) {
	return e ? [...new Set([].concat(e, t))] : t;
}
function hi(e, t) {
	return e ? s(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function gi(e, t) {
	return e ? d(e) && d(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : s(/* @__PURE__ */ Object.create(null), ti(e), ti(t ?? {})) : t;
}
function _i(e, t) {
	if (!e) return t;
	if (!t) return e;
	let n = s(/* @__PURE__ */ Object.create(null), e);
	for (let r in t) n[r] = mi(e[r], t[r]);
	return n;
}
function vi() {
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
var yi = 0;
function bi(e, t) {
	return function(n, r = null) {
		h(n) || (n = s({}, n)), r != null && !v(r) && (r = null);
		let i = vi(), a = /* @__PURE__ */ new WeakSet(), o = [], c = !1, l = i.app = {
			_uid: yi++,
			_component: n,
			_props: r,
			_container: null,
			_context: i,
			_instance: null,
			version: ao,
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
					let u = l._ceVNode || J(n, r);
					return u.appContext = i, s === !0 ? s = "svg" : s === !1 && (s = void 0), o && t ? t(u, a) : e(u, a, s), c = !0, l._container = a, a.__vue_app__ = l, $a(u.component);
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
				let t = xi;
				xi = l;
				try {
					return e();
				} finally {
					xi = t;
				}
			}
		};
		return l;
	};
}
var xi = null, Si = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${E(t)}Modifiers`] || e[`${D(t)}Modifiers`];
function Ci(e, n, ...r) {
	if (e.isUnmounted) return;
	let i = e.vnode.props || t, a = r, o = n.startsWith("update:"), s = o && Si(i, n.slice(7));
	s && (s.trim && (a = r.map((e) => g(e) ? e.trim() : e)), s.number && (a = a.map(se)));
	let c, l = i[c = ie(n)] || i[c = ie(E(n))];
	!l && o && (l = i[c = ie(D(n))]), l && xn(l, e, 6, a);
	let u = i[c + "Once"];
	if (u) {
		if (!e.emitted) e.emitted = {};
		else if (e.emitted[c]) return;
		e.emitted[c] = !0, xn(u, e, 6, a);
	}
}
var wi = /* @__PURE__ */ new WeakMap();
function Ti(e, t, n = !1) {
	let r = n ? wi : t.emitsCache, i = r.get(e);
	if (i !== void 0) return i;
	let a = e.emits, o = {}, c = !1;
	if (!h(e)) {
		let r = (e) => {
			let n = Ti(e, t, !0);
			n && (c = !0, s(o, n));
		};
		!n && t.mixins.length && t.mixins.forEach(r), e.extends && r(e.extends), e.mixins && e.mixins.forEach(r);
	}
	return !a && !c ? (v(e) && r.set(e, null), null) : (d(a) ? a.forEach((e) => o[e] = null) : s(o, a), v(e) && r.set(e, o), o);
}
function Ei(e, t) {
	return !e || !a(t) ? !1 : (t = t.slice(2), t = t === "Once" ? t : t.replace(/Once$/, ""), u(e, t[0].toLowerCase() + t.slice(1)) || u(e, D(t)) || u(e, t));
}
function Di(e) {
	let { type: t, vnode: n, proxy: r, withProxy: i, propsOptions: [a], slots: s, attrs: c, emit: l, render: u, renderCache: d, props: f, data: p, setupState: m, ctx: h, inheritAttrs: g } = e, _ = Un(e), v, y;
	try {
		if (n.shapeFlag & 4) {
			let e = i || r, t = e;
			v = ka(u.call(t, e, d, f, m, p, h)), y = c;
		} else {
			let e = t;
			v = ka(e.length > 1 ? e(f, {
				attrs: c,
				slots: s,
				emit: l
			}) : e(f, null)), y = t.props ? c : ki(c);
		}
	} catch (t) {
		ga.length = 0, Sn(t, e, 1), v = J(ma);
	}
	let b = v;
	if (y && g !== !1) {
		let e = Object.keys(y), { shapeFlag: t } = b;
		e.length && t & 7 && (a && e.some(o) && (y = Ai(y, a)), b = Oa(b, y, !1, !0));
	}
	return n.dirs && (b = Oa(b, null, !1, !0), b.dirs = b.dirs ? b.dirs.concat(n.dirs) : n.dirs), n.transition && vr(rr(b.type) && _r(b) || b, n.transition), v = b, Un(_), v;
}
function Oi(e, t = !0) {
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
var ki = (e) => {
	let t;
	for (let n in e) (n === "class" || n === "style" || a(n)) && ((t ||= {})[n] = e[n]);
	return t;
}, Ai = (e, t) => {
	let n = {};
	for (let r in e) o(r) && r.slice(9) in t || (n[r] = e[r]);
	return n;
};
function ji(e, t, n) {
	let { props: r, children: i, component: a } = e, { props: o, children: s, patchFlag: c } = t, l = a.emitsOptions;
	if (t.dirs || t.transition) return !0;
	if (n && c >= 0) {
		if (c & 1024) return !0;
		if (c & 16) return r ? Mi(r, o, l) : !!o;
		if (c & 8) {
			let e = t.dynamicProps;
			for (let t = 0; t < e.length; t++) {
				let n = e[t];
				if (Ni(o, r, n) && !Ei(l, n)) return !0;
			}
		}
	} else return (i || s) && (!s || !s.$stable) ? !0 : r === o ? !1 : r ? !o || Mi(r, o, l) : !!o;
	return !1;
}
function Mi(e, t, n) {
	let r = Object.keys(t);
	if (r.length !== Object.keys(e).length) return !0;
	for (let i = 0; i < r.length; i++) {
		let a = r[i];
		if (!u(e, a) || Ni(t, e, a) && !Ei(n, a)) return !0;
	}
	return !1;
}
function Ni(e, t, n) {
	let r = e[n], i = t[n];
	return n === "style" && v(r) && v(i) ? !Se(r, i) : r !== i;
}
function Pi({ vnode: e, parent: t, suspense: n }, r) {
	for (; t;) {
		let n = t.subTree;
		if (n.suspense && n.suspense.activeBranch === e && (n.suspense.vnode.el = n.el = r, e = n), n === e) (e = t.vnode).el = r, t = t.parent;
		else break;
	}
	n && n.activeBranch === e && (n.vnode.el = r);
}
var Fi = {}, Ii = () => Object.create(Fi), Li = (e) => Object.getPrototypeOf(e) === Fi;
function Ri(e, t, n, r = !1) {
	let i = {}, a = Ii();
	e.propsDefaults = /* @__PURE__ */ Object.create(null), Bi(e, t, i, a);
	for (let t in e.propsOptions[0]) t in i || (i[t] = void 0);
	e.props = n ? r ? i : /* @__PURE__ */ Ut(i) : e.type.props ? i : a, e.attrs = a;
}
function zi(e, t, n, r) {
	let { props: i, attrs: a, vnode: { patchFlag: o } } = e, s = /* @__PURE__ */ N(i), [c] = e.propsOptions, l = !1;
	if ((r || o > 0) && !(o & 16)) {
		if (o & 8) {
			let n = e.vnode.dynamicProps;
			for (let r = 0; r < n.length; r++) {
				let o = n[r];
				if (Ei(e.emitsOptions, o)) continue;
				let d = t[o];
				if (c) {
					if (u(a, o)) d !== a[o] && (a[o] = d, l = !0);
					else {
						let t = E(o);
						i[t] = Vi(c, s, t, d, e, !1);
					}
				} else d !== a[o] && (a[o] = d, l = !0);
			}
		}
	} else {
		Bi(e, t, i, a) && (l = !0);
		let r;
		for (let a in s) t && (u(t, a) || (r = D(a)) !== a && u(t, r)) || (c ? n && (n[a] !== void 0 || n[r] !== void 0) && (i[a] = Vi(c, s, a, void 0, e, !0)) : delete i[a]);
		if (a !== s) for (let e in a) t && u(t, e) || (delete a[e], l = !0);
	}
	l && it(e.attrs, "set", "");
}
function Bi(e, n, r, i) {
	let [a, o] = e.propsOptions, s = !1, c;
	if (n) for (let t in n) {
		if (T(t)) continue;
		let l = n[t], d;
		a && u(a, d = E(t)) ? !o || !o.includes(d) ? r[d] = l : (c ||= {})[d] = l : Ei(e.emitsOptions, t) || t in i && l === i[t] || (i[t] = l, s = !0);
	}
	if (o) {
		let n = /* @__PURE__ */ N(r), i = c || t;
		for (let t = 0; t < o.length; t++) {
			let s = o[t];
			r[s] = Vi(a, n, s, i[s], e, !u(i, s));
		}
	}
	return s;
}
function Vi(e, t, n, r, i, a) {
	let o = e[n];
	if (o != null) {
		let e = u(o, "default");
		if (e && r === void 0) {
			let e = o.default;
			if (o.type !== Function && !o.skipFactory && h(e)) {
				let { propsDefaults: a } = i;
				if (n in a) r = a[n];
				else {
					let o = Ha(i);
					r = a[n] = e.call(null, t), o();
				}
			} else r = e;
			i.ce && i.ce._setProp(n, r);
		}
		o[0] && (a && !e ? r = !1 : o[1] && (r === "" || r === D(n)) && (r = !0));
	}
	return r;
}
var Hi = /* @__PURE__ */ new WeakMap();
function Ui(e, r, i = !1) {
	let a = i ? Hi : r.propsCache, o = a.get(e);
	if (o) return o;
	let c = e.props, l = {}, f = [], p = !1;
	if (!h(e)) {
		let t = (e) => {
			p = !0;
			let [t, n] = Ui(e, r, !0);
			s(l, t), n && f.push(...n);
		};
		!i && r.mixins.length && r.mixins.forEach(t), e.extends && t(e.extends), e.mixins && e.mixins.forEach(t);
	}
	if (!c && !p) return v(e) && a.set(e, n), n;
	if (d(c)) for (let e = 0; e < c.length; e++) {
		let n = E(c[e]);
		Wi(n) && (l[n] = t);
	}
	else if (c) for (let e in c) {
		let t = E(e);
		if (Wi(t)) {
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
function Wi(e) {
	return e[0] !== "$" && !T(e);
}
var Gi = (e) => e === "_" || e === "_ctx" || e === "$stable", Ki = (e) => d(e) ? e.map(ka) : [ka(e)], qi = (e, t, n) => {
	if (t._n) return t;
	let r = z((...e) => Ki(t(...e)), n);
	return r._c = !1, r;
}, Ji = (e, t, n) => {
	let r = e._ctx;
	for (let n in e) {
		if (Gi(n)) continue;
		let i = e[n];
		if (h(i)) t[n] = qi(n, i, r);
		else if (i != null) {
			let e = Ki(i);
			t[n] = () => e;
		}
	}
}, Yi = (e, t) => {
	let n = Ki(t);
	e.slots.default = () => n;
}, Xi = (e, t, n) => {
	for (let r in t) (n || !Gi(r)) && (e[r] = t[r]);
}, Zi = (e, t, n) => {
	let r = e.slots = Ii();
	if (e.vnode.shapeFlag & 32) {
		let e = t._;
		e ? (Xi(r, t, n), n && O(r, "_", e, !0)) : Ji(t, r);
	} else t && Yi(e, t);
}, Qi = (e, n, r) => {
	let { vnode: i, slots: a } = e, o = !0, s = t;
	if (i.shapeFlag & 32) {
		let e = n._;
		e ? r && e === 1 ? o = !1 : Xi(a, n, r) : (o = !n.$stable, Ji(n, a)), s = n;
	} else n && (Yi(e, n), s = { default: 1 });
	if (o) for (let e in a) !Gi(e) && s[e] == null && delete a[e];
}, $i = fa;
function ea(e) {
	return ta(e);
}
function ta(e, i) {
	let a = le();
	a.__VUE__ = !0;
	let { insert: o, remove: s, patchProp: c, createElement: l, createText: u, createComment: d, setText: f, setElementText: p, parentNode: m, nextSibling: h, setScopeId: g = r, insertStaticContent: _ } = e, v = (e, t, r, i = null, a = null, o = null, s = void 0, c = null, l = !!t.dynamicChildren) => {
		if (e === t) return;
		e && !Ca(e, t) && (i = ye(e), k(e, a, o, !0), e = null), t.patchFlag === -2 && (l = !1, t.dynamicChildren = null), t.dynamicChildren && e && e.dynamicChildren && e.dynamicChildren.hasOnce && (t.dynamicChildren === n && (t.dynamicChildren = []), t.dynamicChildren.hasOnce = !0);
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
			case U:
				ie(e, t, r, i, a, o, s, c, l);
				break;
			default: f & 1 ? w(e, t, r, i, a, o, s, c, l) : f & 6 ? ae(e, t, r, i, a, o, s, c, l) : (f & 64 || f & 128) && u.process(e, t, r, i, a, o, s, c, l, xe);
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
			"value" in m && c(d, "value", null, m.value, a), (f = m.onVnodeBeforeMount) && Na(f, r, e);
		}
		_ && Gn(e, null, r, "beforeMount");
		let v = ia(i, g);
		v ? g.beforeEnter(d) : g && !g.persisted && (d[da] = !0), o(d, t, n), ((f = m && m.onVnodeMounted) || v || _) && $i(() => {
			try {
				f && Na(f, r, e), v && g.enter(d), _ && Gn(e, null, r, "mounted");
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
			let c = e[l] = s ? Aa(e[l]) : ka(e[l]);
			v(null, c, t, n, r, i, a, o, s);
		}
	}, ne = (e, n, r, i, a, o, s) => {
		let l = n.el = e.el, { patchFlag: u, dynamicChildren: d, dirs: f } = n;
		u |= e.patchFlag & 16;
		let m = e.props || t, h = n.props || t, g;
		if (r && ra(r, !1), (g = h.onVnodeBeforeUpdate) && Na(g, r, n, e), f && Gn(n, e, r, "beforeUpdate"), r && ra(r, !0), d && (!e.dynamicChildren || e.dynamicChildren.length !== d.length) && (u = 0, s = !1, d = null), (m.innerHTML && h.innerHTML == null || m.textContent && h.textContent == null) && p(l, ""), d ? D(e.dynamicChildren, d, l, r, i, na(n, a), o) : s || de(e, n, l, null, r, i, na(n, a), o, !1), u > 0) {
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
		((g = h.onVnodeUpdated) || f) && $i(() => {
			g && Na(g, r, n, e), f && Gn(n, e, r, "updated");
		}, i);
	}, D = (e, t, n, r, i, a, o) => {
		for (let s = 0; s < t.length; s++) {
			let c = e[s], l = t[s], u = c.el || la(c), d = u && (c.type === U || !Ca(c, l) || c.shapeFlag & 198) ? m(u) : n;
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
	}, ie = (e, t, n, r, i, a, s, c, l) => {
		let d = t.el = e ? e.el : u(""), f = t.anchor = e ? e.anchor : u(""), { patchFlag: p, dynamicChildren: m, slotScopeIds: h } = t;
		h && (c = c ? c.concat(h) : h), e == null ? (o(d, n, r), o(f, n, r), E(t.children || [], n, f, i, a, s, c, l)) : p > 0 && p & 64 && m && e.dynamicChildren && e.dynamicChildren.length === m.length ? (D(e.dynamicChildren, m, n, i, a, s, c), (t.key != null || i && t === i.subTree) && aa(e, t, !0)) : de(e, t, n, f, i, a, s, c, l);
	}, ae = (e, t, n, r, i, a, o, s, c) => {
		t.slotScopeIds = s, e == null ? t.shapeFlag & 512 ? i.ctx.activate(t, n, r, o, c) : O(t, n, r, i, a, o, c) : se(e, t, c);
	}, O = (e, t, n, r, i, a, o) => {
		let s = e.component = La(e, r, i);
		if (Dr(e) && (s.ctx.renderer = xe), Ka(s, !1, o), s.asyncDep) {
			if (i && i.registerDep(s, ce, o, a), !e.el) {
				let r = s.subTree = J(ma);
				b(null, r, t, n), e.placeholder = r.el;
			}
		} else ce(s, e, t, n, i, a, o);
	}, se = (e, t, n) => {
		let r = t.component = e.component;
		if (ji(e, t, n)) {
			if (r.asyncDep && !r.asyncResolved) {
				t.el = e.el, t.placeholder = e.placeholder, ue(r, t, n);
				return;
			}
			r.next = t, r.update();
		} else t.el = e.el, t.placeholder = e.placeholder, r.vnode = t;
	}, ce = (e, t, n, r, i, a, o) => {
		let s = () => {
			if (e.isMounted) {
				let { next: t, bu: n, u: r, parent: s, vnode: c } = e;
				{
					let n = sa(e);
					if (n) {
						t && (t.el = c.el, ue(e, t, o)), n.asyncDep.then(() => {
							let t = () => {
								e.job.flags & 8 || (i && i.pendingBranch ? $i(t, i) : l());
							};
							t.flags = 48, $i(t, i);
						});
						return;
					}
				}
				let u = t, d;
				ra(e, !1), t ? (t.el = c.el, ue(e, t, o)) : t = c, n && oe(n), (d = t.props && t.props.onVnodeBeforeUpdate) && Na(d, s, t, c), ra(e, !0);
				let f = Di(e), p = e.subTree;
				e.subTree = f, v(p, f, m(p.el || la(p)), ye(p), e, i, a), t.el = f.el, u === null && Pi(e, f.el), r && $i(r, i), (d = t.props && t.props.onVnodeUpdated) && $i(() => Na(d, s, t, c), i);
			} else {
				let o, { el: s, props: c } = t, { bm: l, m: u, parent: d, root: f, type: p } = e, m = Er(t);
				if (ra(e, !1), l && oe(l), !m && (o = c && c.onVnodeBeforeMount) && Na(o, d, t), ra(e, !0), s && Ce) {
					let t = () => {
						e.subTree = Di(e), Ce(s, e.subTree, e, i, null);
					};
					m && p.__asyncHydrate ? p.__asyncHydrate(s, e, t) : t();
				} else {
					f.ce && f.ce._hasShadowRoot() && f.ce._injectChildStyle(p, e.parent ? e.parent.type : void 0);
					let o = e.subTree = Di(e);
					v(null, o, n, r, e, i, a), t.el = o.el;
				}
				if (u && $i(u, i), !m && (o = c && c.onVnodeMounted)) {
					let e = t;
					$i(() => Na(o, d, e), i);
				}
				(t.shapeFlag & 256 || d && Er(d.vnode) && d.vnode.shapeFlag & 256) && e.a && $i(e.a, i), e.isMounted = !0, t = n = r = null;
			}
		};
		e.scope.on();
		let c = e.effect = new je(s);
		e.scope.off();
		let l = e.update = c.run.bind(c), u = e.job = c.runIfDirty.bind(c);
		u.i = e, u.id = e.uid, c.scheduler = () => Nn(u), ra(e, !0), l();
	}, ue = (e, t, n) => {
		t.component = e;
		let r = e.vnode.props;
		e.vnode = t, e.next = null, zi(e, t.props, r, n), Qi(e, t.children, n), Ke(), In(e), qe();
	}, de = (e, t, n, r, i, a, o, s, c = !1) => {
		let l = e && e.children, u = e ? e.shapeFlag : 0, d = t.children, { patchFlag: f, shapeFlag: m } = t;
		if (f > 0) {
			if (f & 128) {
				pe(l, d, n, r, i, a, o, s, c);
				return;
			}
			if (f & 256) {
				fe(l, d, n, r, i, a, o, s, c);
				return;
			}
		}
		m & 8 ? (u & 16 && ve(l, i, a), d !== l && p(n, d)) : u & 16 ? m & 16 ? pe(l, d, n, r, i, a, o, s, c) : ve(l, i, a, !0) : (u & 8 && p(n, ""), m & 16 && E(d, n, r, i, a, o, s, c));
	}, fe = (e, t, r, i, a, o, s, c, l) => {
		e ||= n, t ||= n;
		let u = e.length, d = t.length, f = Math.min(u, d), p = 0;
		for (; p < f; p++) {
			let n = t[p] = l ? Aa(t[p]) : ka(t[p]);
			v(e[p], n, r, null, a, o, s, c, l);
		}
		u > d ? ve(e, a, o, !0, !1, f) : E(t, r, i, a, o, s, c, l, f);
	}, pe = (e, t, r, i, a, o, s, c, l) => {
		let u = 0, d = t.length, f = e.length - 1, p = d - 1;
		for (; u <= f && u <= p;) {
			let n = e[u], i = t[u] = l ? Aa(t[u]) : ka(t[u]);
			if (Ca(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			u++;
		}
		for (; u <= f && u <= p;) {
			let n = e[f], i = t[p] = l ? Aa(t[p]) : ka(t[p]);
			if (Ca(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			f--, p--;
		}
		if (u > f) {
			if (u <= p) {
				let e = p + 1, n = e < d ? t[e].el : i;
				for (; u <= p;) v(null, t[u] = l ? Aa(t[u]) : ka(t[u]), r, n, a, o, s, c, l), u++;
			}
		} else if (u > p) for (; u <= f;) k(e[u], a, o, !0), u++;
		else {
			let m = u, h = u, g = /* @__PURE__ */ new Map();
			for (u = h; u <= p; u++) {
				let e = t[u] = l ? Aa(t[u]) : ka(t[u]);
				e.key != null && g.set(e.key, u);
			}
			let _, y = 0, b = p - h + 1, x = !1, S = 0, C = Array(b);
			for (u = 0; u < b; u++) C[u] = 0;
			for (u = m; u <= f; u++) {
				let n = e[u];
				if (y >= b) {
					k(n, a, o, !0);
					continue;
				}
				let i;
				if (n.key != null) i = g.get(n.key);
				else for (_ = h; _ <= p; _++) if (C[_ - h] === 0 && Ca(n, t[_])) {
					i = _;
					break;
				}
				i === void 0 ? k(n, a, o, !0) : (C[i - h] = u + 1, i >= S ? S = i : x = !0, v(n, t[i], r, null, a, o, s, c, l), y++);
			}
			let w = x ? oa(C) : n;
			for (_ = w.length - 1, u = b - 1; u >= 0; u--) {
				let e = h + u, n = t[e], f = t[e + 1], p = e + 1 < d ? f.el || la(f) : i;
				C[u] === 0 ? v(null, n, r, p, a, o, s, c, l) : x && (_ < 0 || u !== w[_] ? me(n, r, p, 2) : _--);
			}
		}
	}, me = (e, t, n, r, i = null) => {
		let { el: a, type: c, transition: l, children: u, shapeFlag: d } = e;
		if (d & 6) me(e.component.subTree, t, n, r);
		else if (d & 128) e.suspense.move(t, n, r);
		else if (d & 64) c.move(e, t, n, xe);
		else if (c === U) {
			o(a, t, n);
			for (let e = 0; e < u.length; e++) me(u[e], t, n, r);
			o(e.anchor, t, n);
		} else if (c === ha) S(e, t, n);
		else if (r !== 2 && d & 1 && l) {
			if (r === 0) l.persisted && !a[hr] ? o(a, t, n) : (l.beforeEnter(a), o(a, t, n), $i(() => l.enter(a), i));
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
	}, k = (e, t, n, r = !1, i = !1) => {
		let { type: a, props: o, ref: s, children: c, dynamicChildren: l, shapeFlag: u, patchFlag: d, dirs: f, cacheIndex: p, memo: m } = e;
		if ((d === -2 || l && l.hasOnce) && (i = !1), s != null && (Ke(), wr(s, null, n, e, !0), qe()), p == null || e.ctx && e.ctx !== t || (t.renderCache[p] = void 0), u & 256 && t.ctx.deactivate(e)) return;
		let h = u & 1 && f, g = !Er(e), _;
		if (g && (_ = o && o.onVnodeBeforeUnmount) && Na(_, t, e), u & 6) _e(e.component, n, r);
		else {
			if (u & 128) {
				e.suspense.unmount(n, r);
				return;
			}
			h && Gn(e, null, t, "beforeUnmount"), u & 64 ? e.type.remove(e, t, n, xe, r) : l && !l.hasOnce && (a !== U || d > 0 && d & 64) ? ve(l, t, n, !1, !0) : (a === U && d & 384 || !i && u & 16) && ve(c, t, n), r && he(e);
		}
		let v = m != null && p == null;
		(g && (_ = o && o.onVnodeUnmounted) || h || v) && $i(() => {
			_ && Na(_, t, e), h && Gn(e, null, t, "unmounted"), v && (e.el = null);
		}, n);
	}, he = (e) => {
		let { type: t, el: n, anchor: r, transition: i } = e, a = t === U;
		if (a && !i) {
			ge(n, r);
			return;
		}
		if (t === ha) {
			C(e), i && !i.persisted && i.afterLeave && i.afterLeave();
			return;
		}
		let o = a ? yr(e) : e, c = () => {
			a ? m(n) && ge(n, r) : s(n), i && !i.persisted && i.afterLeave && i.afterLeave();
		};
		if (o && o.shapeFlag & 1 && i && !i.persisted) {
			let { leave: e, delayLeave: t } = i, n = o.el, r = () => e(n, c);
			t ? t(n, c, r) : r();
		} else c();
	}, ge = (e, t) => {
		let n;
		for (; e !== t;) n = h(e), s(e), e = n;
		s(t);
	}, _e = (e, t, n) => {
		let { bum: r, scope: i, job: a, subTree: o, um: s, m: c, a: l } = e;
		ca(c), ca(l), r && oe(r), i.stop(), a ? (a.flags |= 8, k(o, e, t, n)) : o && (o.transition = e.vnode.transition, k(o, e, t, n)), s && $i(s, t);
		let u = () => {
			e.isUnmounted = !0;
		};
		u.flags = 16, $i(u, t);
	}, ve = (e, t, n, r = !1, i = !1, a = 0) => {
		for (let o = a; o < e.length; o++) k(e[o], t, n, r, i);
	}, ye = (e) => {
		if (e.shapeFlag & 6) return ye(e.component.subTree);
		if (e.shapeFlag & 128) return e.suspense.next();
		let t = h(e.anchor || e.el), n = t && t[nr];
		return n ? h(n) : t;
	}, be = (e, t, n) => {
		zn(() => {
			e == null ? t._vnode && k(t._vnode, null, null, !0) : v(t._vnode || null, e, t, null, null, null, n), t._vnode = e;
		}, e && t._vnode ? void 0 : e && e.component ? e.component.uid : Ia());
	}, xe = {
		p: v,
		um: k,
		m: me,
		r: he,
		mt: O,
		mc: E,
		pc: de,
		pbc: D,
		n: ye,
		o: e
	}, Se, Ce;
	return i && ([Se, Ce] = i(xe)), {
		render: be,
		hydrate: Se,
		createApp: bi(be, Se)
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
		a.shapeFlag & 1 && !a.dynamicChildren && ((a.patchFlag <= 0 || a.patchFlag === 32) && (a = i[e] = Aa(i[e]), a.el = t.el), !n && a.patchFlag !== -2 && aa(t, a)), a.type === pa && (a.patchFlag === -1 && (a = i[e] = Aa(a)), a.el = t.el), a.type === ma && !a.el && (a.el = t.el);
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
var U = /* @__PURE__ */ Symbol.for("v-fgt"), pa = /* @__PURE__ */ Symbol.for("v-txt"), ma = /* @__PURE__ */ Symbol.for("v-cmt"), ha = /* @__PURE__ */ Symbol.for("v-stc"), ga = [], _a = null;
function W(e = !1) {
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
function G(e, t, n, r, i, a) {
	return xa(q(e, t, n, r, i, a, !0));
}
function K(e, t, n, r, i) {
	return xa(J(e, t, n, r, i, !0));
}
function Sa(e) {
	return e ? e.__v_isVNode === !0 : !1;
}
function Ca(e, t) {
	return e.type === t.type && e.key === t.key;
}
var wa = ({ key: e }) => e ?? null, Ta = ({ ref: e, ref_key: t, ref_for: n }) => (typeof e == "number" && (e = "" + e), e == null ? null : g(e) || /* @__PURE__ */ P(e) || h(e) ? {
	i: R,
	r: e,
	k: t,
	f: !!n
} : e);
function q(e, t = null, n = null, r = 0, i = null, a = e === U ? 0 : 1, o = !1, s = !1) {
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
		ctx: R
	};
	return s ? (ja(c, n), a & 128 && e.normalize(c)) : n && (c.shapeFlag |= g(n) ? 8 : 16), ya > 0 && !o && _a && (c.patchFlag > 0 || a & 6) && c.patchFlag !== 32 && _a.push(c), c;
}
var J = Ea;
function Ea(e, t = null, n = null, r = 0, i = null, a = !1) {
	if (e && e !== Gr || (e = ma), Sa(e)) {
		let r = Oa(e, t, !0);
		return n && ja(r, n), ya > 0 && !a && _a && (r.shapeFlag & 6 ? _a[_a.indexOf(e)] = r : _a.push(r)), r.patchFlag = -2, r;
	}
	if (to(e) && (e = e.__vccOpts), t) {
		t = Da(t);
		let { class: e, style: n } = t;
		e && !g(e) && (t.class = k(e)), v(n) && (/* @__PURE__ */ Xt(n) && !d(n) && (n = s({}, n)), t.style = ue(n));
	}
	let o = g(e) ? 1 : ua(e) ? 128 : rr(e) ? 64 : v(e) ? 4 : h(e) ? 2 : 0;
	return q(e, t, n, r, i, o, a, !0);
}
function Da(e) {
	return e ? /* @__PURE__ */ Xt(e) ? s({}, e) : Li(e) ? s({}, e[Xa] || e) : e : null;
}
function Oa(e, t, n = !1, r = !1) {
	let { props: i, ref: a, patchFlag: o, children: s, transition: c } = e, l = t ? Ma(i || {}, t) : i, u = {
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
		patchFlag: t && e.type !== U ? o === -1 ? 16 : o | 16 : o,
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
function Y(e = " ", t = 0) {
	return J(pa, null, e, t);
}
function X(e = "", t = !1) {
	return t ? (W(), K(ma, null, e)) : J(ma, null, e);
}
function ka(e) {
	return e == null || typeof e == "boolean" ? J(ma) : d(e) ? J(U, null, e.slice()) : Sa(e) ? Aa(e) : J(pa, null, String(e));
}
function Aa(e) {
	return e.el === null && e.patchFlag !== -1 || e.memo ? e : Oa(e);
}
function ja(e, t) {
	let n = 0, { shapeFlag: r } = e;
	if (t == null) t = null;
	else if (d(t)) n = 16;
	else if (typeof t == "object") {
		if (r & 65) {
			let n = t.default;
			n && (n._c && (n._d = !1), ja(e, n()), n._c && (n._d = !0));
			return;
		}
		{
			n = 32;
			let r = t._;
			!r && !Li(t) ? t._ctx = R : r === 3 && R && (R.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
		}
	} else if (h(t)) {
		if (r & 65) {
			ja(e, { default: t });
			return;
		}
		t = {
			default: t,
			_ctx: R
		}, n = 32;
	} else t = String(t), r & 64 ? (n = 16, t = [Y(t)]) : n = 8;
	e.children = t, e.shapeFlag |= n;
}
function Ma(...e) {
	let t = {};
	for (let n = 0; n < e.length; n++) {
		let r = e[n];
		for (let e in r) if (e === "class") t.class !== r.class && (t.class = k([t.class, r.class]));
		else if (e === "style") t.style = ue([t.style, r.style]);
		else if (a(e)) {
			let n = t[e], i = r[e];
			i && n !== i && !(d(n) && n.includes(i)) ? t[e] = n ? [].concat(n, i) : i : i == null && n == null && !o(e) && (t[e] = i);
		} else e !== "" && (t[e] = r[e]);
	}
	return t;
}
function Na(e, t, n, r = null) {
	xn(e, t, 7, [n, r]);
}
var Pa = /* @__PURE__ */ vi(), Fa = 0;
function Ia() {
	return Fa;
}
function La(e, n, r) {
	let i = e.type, a = (n ? n.appContext : e.appContext) || Pa, o = {
		uid: Fa++,
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
		propsOptions: Ui(i, a),
		emitsOptions: Ti(i, a),
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
	return o.ctx = { _: o }, o.root = n ? n.root : o, o.emit = Ci.bind(null, o), e.ce && e.ce(o), o;
}
var Ra = null, za = () => Ra || R, Ba, Va;
{
	let e = le(), t = (t, n) => {
		let r;
		return (r = e[t]) || (r = e[t] = []), r.push(n), (e) => {
			r.length > 1 ? r.forEach((t) => t(e)) : r[0](e);
		};
	};
	Ba = t("__VUE_INSTANCE_SETTERS__", (e) => Ra = e), Va = t("__VUE_SSR_SETTERS__", (e) => Ga = e);
}
var Ha = (e) => {
	let t = Ra;
	return Ba(e), e.scope.on(), () => {
		e.scope.off(), Ba(t);
	};
}, Ua = () => {
	Ra && Ra.scope.off(), Ba(null);
};
function Wa(e) {
	return e.vnode.shapeFlag & 4;
}
var Ga = !1;
function Ka(e, t = !1, n = !1) {
	t && Va(t);
	let { props: r, children: i } = e.vnode, a = Wa(e);
	Ri(e, r, a, t), Zi(e, i, n || t);
	let o = a ? qa(e, t) : void 0;
	return t && Va(!1), o;
}
function qa(e, t) {
	let n = e.type;
	e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, ei);
	let { setup: r } = n;
	if (r) {
		Ke();
		let n = e.setupContext = r.length > 1 ? Qa(e) : null, i = Ha(e), a = bn(r, e, 0, [e.props, n]), o = y(a);
		if (qe(), i(), (o || e.sp) && !Er(e) && xr(e), o) {
			if (a.then(Ua, Ua), t) return a.then((n) => {
				Va(!0);
				try {
					Ja(e, n, t);
				} finally {
					Va(!1);
				}
			}).catch((t) => {
				Sn(t, e, 0, void 0, !0), e.ssrRender = (e, t) => t("<!---->");
			});
			e.asyncDep = a;
		} else Ja(e, a, t);
	} else Ya(e, t);
}
function Ja(e, t, n) {
	h(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : v(t) && (e.setupState = on(t)), Ya(e, n);
}
function Ya(e, t, n) {
	let i = e.type;
	e.render ||= i.render || r;
	{
		let t = Ha(e);
		Ke();
		try {
			ii(e);
		} finally {
			qe(), t();
		}
	}
}
var Xa = /* @__PURE__ */ Symbol(), Za = { get(e, t) {
	return rt(e, "get", ""), t === Xa ? e : e[t];
} };
function Qa(e) {
	return {
		attrs: new Proxy(e.attrs, Za),
		slots: e.slots,
		emit: e.emit,
		expose: (t) => {
			e.exposed = t || {};
		}
	};
}
function $a(e) {
	return e.exposed ? e.exposeProxy ||= new Proxy(on(Zt(e.exposed)), {
		get(t, n) {
			if (n in t) return t[n];
			if (n in Qr) return Qr[n](e);
		},
		has(e, t) {
			return t in e || t in Qr;
		}
	}) : e.proxy;
}
function eo(e, t = !0) {
	return h(e) ? e.displayName || e.name : e.name || t && e.__name;
}
function to(e) {
	return h(e) && "__vccOpts" in e;
}
var Z = (e, t) => /* @__PURE__ */ pn(e, t, Ga);
function no(e, t, n) {
	try {
		ba(-1);
		let r = arguments.length;
		return r === 2 ? v(t) && !d(t) ? Sa(t) ? J(e, null, [t]) : J(e, t) : J(e, null, t) : (r > 3 ? n = Array.prototype.slice.call(arguments, 2) : r === 3 && Sa(n) && (n = [n]), J(e, t, n));
	} finally {
		ba(1);
	}
}
function ro(e, t, n, r) {
	let i = n[r];
	if (i && io(i, e)) return i;
	let a = t();
	return a.memo = e.slice(), a.cacheIndex = r, n[r] = a;
}
function io(e, t) {
	let n = e.memo;
	if (n.length != t.length) return !1;
	for (let e = 0; e < n.length; e++) if (ae(n[e], t[e])) return !1;
	return ya > 0 && _a && _a.push(e), !0;
}
var ao = "3.5.45", oo = void 0, so = typeof window < "u" && window.trustedTypes;
if (so) try {
	oo = /* @__PURE__ */ so.createPolicy("vue", { createHTML: (e) => e });
} catch {}
var co = oo ? (e) => oo.createHTML(e) : (e) => e, lo = "http://www.w3.org/2000/svg", uo = "http://www.w3.org/1998/Math/MathML", fo = typeof document < "u" ? document : null, po = fo && /* @__PURE__ */ fo.createElement("template"), mo = {
	insert: (e, t, n) => {
		t.insertBefore(e, n || null);
	},
	remove: (e) => {
		let t = e.parentNode;
		t && t.removeChild(e);
	},
	createElement: (e, t, n, r) => {
		let i = t === "svg" ? fo.createElementNS(lo, e) : t === "mathml" ? fo.createElementNS(uo, e) : n ? fo.createElement(e, { is: n }) : fo.createElement(e);
		return e === "select" && r && r.multiple != null && i.setAttribute("multiple", r.multiple), i;
	},
	createText: (e) => fo.createTextNode(e),
	createComment: (e) => fo.createComment(e),
	setText: (e, t) => {
		e.nodeValue = t;
	},
	setElementText: (e, t) => {
		e.textContent = t;
	},
	parentNode: (e) => e.parentNode,
	nextSibling: (e) => e.nextSibling,
	querySelector: (e) => fo.querySelector(e),
	setScopeId(e, t) {
		e.setAttribute(t, "");
	},
	insertStaticContent(e, t, n, r, i, a) {
		let o = n ? n.previousSibling : t.lastChild;
		if (i && (i === a || i.nextSibling)) for (; t.insertBefore(i.cloneNode(!0), n), i !== a && (i = i.nextSibling););
		else {
			po.innerHTML = co(r === "svg" ? `<svg>${e}</svg>` : r === "mathml" ? `<math>${e}</math>` : e);
			let i = po.content;
			if (r === "svg" || r === "mathml") {
				let e = i.firstChild;
				for (; e.firstChild;) i.appendChild(e.firstChild);
				i.removeChild(e);
			}
			t.insertBefore(i, n);
		}
		return [o ? o.nextSibling : t.firstChild, n ? n.previousSibling : t.lastChild];
	}
}, ho = /* @__PURE__ */ Symbol("_vtc");
function go(e, t, n) {
	let r = e[ho];
	r && (t = (t ? [t, ...r] : [...r]).join(" ")), t == null ? e.removeAttribute("class") : n ? e.setAttribute("class", t) : e.className = t;
}
var _o = /* @__PURE__ */ Symbol("_vod"), vo = /* @__PURE__ */ Symbol("_vsh"), yo = /* @__PURE__ */ Symbol(""), bo = /(?:^|;)\s*display\s*:/;
function xo(e, t, n) {
	let r = e.style, i = g(n), a = !1;
	if (n && !i) {
		if (t) {
			if (g(t)) for (let e of t.split(";")) {
				let t = e.slice(0, e.indexOf(":")).trim();
				n[t] ?? Co(r, t, "");
			}
			else for (let e in t) n[e] ?? Co(r, e, "");
		}
		for (let i in n) {
			i === "display" && (a = !0);
			let o = n[i];
			o == null ? Co(r, i, "") : Do(e, i, !g(t) && t ? t[i] : void 0, o) || Co(r, i, o);
		}
	} else if (i) {
		if (t !== n) {
			let e = r[yo];
			e && (n += ";" + e), r.cssText = n, a = bo.test(n);
		}
	} else t && e.removeAttribute("style");
	_o in e && (i && t === n || (e[_o] = a ? r.display : ""), e[vo] && (r.display = "none"));
}
var So = /\s*!important$/;
function Co(e, t, n) {
	if (d(n)) n.forEach((n) => Co(e, t, n));
	else if (n ??= "", t.startsWith("--")) So.test(n) ? e.setProperty(t, n.replace(So, ""), "important") : e.setProperty(t, n);
	else {
		let r = Eo(e, t);
		So.test(n) ? e.setProperty(D(r), n.replace(So, ""), "important") : e[r] = n;
	}
}
var wo = [
	"Webkit",
	"Moz",
	"ms"
], To = {};
function Eo(e, t) {
	let n = To[t];
	if (n) return n;
	let r = E(t);
	if (r !== "filter" && r in e) return To[t] = r;
	r = re(r);
	for (let n = 0; n < wo.length; n++) {
		let i = wo[n] + r;
		if (i in e) return To[t] = i;
	}
	return t;
}
function Do(e, t, n, r) {
	return e.tagName === "TEXTAREA" && (t === "width" || t === "height") && g(r) && n === r;
}
var Oo = "http://www.w3.org/1999/xlink";
function ko(e, t, n, r, i, a = ge(t)) {
	r && t.startsWith("xlink:") ? n == null ? e.removeAttributeNS(Oo, t.slice(6, t.length)) : e.setAttributeNS(Oo, t, n) : n == null || a && !_e(n) ? e.removeAttribute(t) : e.setAttribute(t, a ? "" : _(n) ? String(n) : n);
}
function Ao(e, t, n, r, i) {
	if (t === "innerHTML" || t === "textContent") {
		n != null && (e[t] = t === "innerHTML" ? co(n) : n);
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
		r === "boolean" ? n = _e(n) : n == null && r === "string" ? (n = "", o = !0) : r === "number" && (n = 0, o = !0);
	}
	try {
		e[t] = n;
	} catch {}
	o && e.removeAttribute(i || t);
}
function jo(e, t, n, r) {
	e.addEventListener(t, n, r);
}
function Mo(e, t, n, r) {
	e.removeEventListener(t, n, r);
}
var No = /* @__PURE__ */ Symbol("_vei");
function Po(e, t, n, r, i = null) {
	let a = e[No] || (e[No] = {}), o = a[t];
	if (r && o) o.value = r;
	else {
		let [n, s] = Lo(t);
		r ? jo(e, n, a[t] = Vo(r, i), s) : o && (Mo(e, n, o, s), a[t] = void 0);
	}
}
var Fo = /(Once|Passive|Capture)$/, Io = /^on:?(?:Once|Passive|Capture)$/;
function Lo(e) {
	let t, n;
	for (; (n = e.match(Fo)) && !Io.test(e);) t ||= {}, e = e.slice(0, e.length - n[1].length), t[n[1].toLowerCase()] = !0;
	return [e[2] === ":" ? e.slice(3) : D(e.slice(2)), t];
}
var Ro = 0, zo = /* @__PURE__ */ Promise.resolve(), Bo = () => Ro ||= (zo.then(() => Ro = 0), Date.now());
function Vo(e, t) {
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
	return n.value = e, n.attached = Bo(), n;
}
var Ho = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, Uo = (e, t, n, r, i, s) => {
	let c = i === "svg";
	t === "class" ? go(e, r, c) : t === "style" ? xo(e, n, r) : a(t) ? o(t) || Po(e, t, n, r, s) : (t[0] === "." ? (t = t.slice(1), 1) : t[0] === "^" ? (t = t.slice(1), 0) : Wo(e, t, r, c)) ? (Ao(e, t, r), e.tagName.includes("-") || t !== "value" && t !== "checked" && t !== "selected" || ko(e, t, r, c, s, t !== "value")) : e._isVueCE && (Go(e, t) || e._def.__asyncLoader && (/[A-Z]/.test(t) || !g(r))) ? Ao(e, E(t), r, s, t) : (t === "true-value" ? e._trueValue = r : t === "false-value" && (e._falseValue = r), ko(e, t, r, c));
};
function Wo(e, t, n, r) {
	if (r) return !!(t === "innerHTML" || t === "textContent" || t in e && Ho(t) && h(n));
	if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "autocorrect" || t === "sandbox" && e.tagName === "IFRAME" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA") return !1;
	if (t === "width" || t === "height") {
		let t = e.tagName;
		if (t === "IMG" || t === "VIDEO" || t === "CANVAS" || t === "SOURCE") return !1;
	}
	return Ho(t) && g(n) ? !1 : t in e;
}
function Go(e, t) {
	let n = e._def.props;
	if (!n) return !1;
	let r = E(t);
	return Array.isArray(n) ? n.some((e) => E(e) === r) : Object.keys(n).some((e) => E(e) === r);
}
var Ko = (e) => {
	let t = e.props["onUpdate:modelValue"] || !1;
	return d(t) ? (e) => oe(t, e) : t;
};
function qo(e) {
	e.target.composing = !0;
}
function Jo(e) {
	let t = e.target;
	t.composing && (t.composing = !1, t.dispatchEvent(new Event("input")));
}
var Yo = /* @__PURE__ */ Symbol("_assign"), Xo = /* @__PURE__ */ Symbol("_initialValue");
function Zo(e, t, n) {
	return t && (e = e.trim()), n && (e = se(e)), e;
}
var Qo = {
	created(e, { modifiers: { lazy: t, trim: n, number: r } }, i) {
		e.parentNode && (e.type === "text" ? e[Xo] = e.defaultValue.replace(/[\r\n]/g, "") : e.type === "textarea" && (e[Xo] = e.defaultValue.replace(/\r\n?/g, "\n"))), e[Yo] = Ko(i);
		let a = r || i.props && i.props.type === "number";
		jo(e, t ? "change" : "input", (t) => {
			t.target.composing || e[Yo](Zo(e.value, n, a));
		}), (n || a) && jo(e, "change", () => {
			e.value = Zo(e.value, n, a);
		}), t || (jo(e, "compositionstart", qo), jo(e, "compositionend", Jo), jo(e, "change", Jo));
	},
	mounted(e, { value: t, modifiers: { trim: n, number: r } }) {
		let i = t ?? "", a = e[Xo];
		delete e[Xo], a !== void 0 && (e.type === "text" || e.type === "textarea") && e.value !== a ? e[Yo](Zo(e.value, n, r)) : e.value = i;
	},
	beforeUpdate(e, { value: t, oldValue: n, modifiers: { lazy: r, trim: i, number: a } }, o) {
		if (e[Yo] = Ko(o), e.composing) return;
		let s = (a || e.type === "number") && !/^0\d/.test(e.value) ? se(e.value) : e.value, c = t ?? "";
		if (s === c) return;
		let l = e.getRootNode();
		(l instanceof Document || l instanceof ShadowRoot) && l.activeElement === e && e.type !== "range" && (r && t === n || i && e.value.trim() === c) || (e.value = c);
	}
}, $o = [
	"ctrl",
	"shift",
	"alt",
	"meta"
], es = {
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
	exact: (e, t) => $o.some((n) => e[`${n}Key`] && !t.includes(n))
}, ts = (e, t) => {
	if (!e) return e;
	let n = e._withMods ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n, ...r) => {
		for (let e = 0; e < t.length; e++) {
			let r = es[t[e]];
			if (r && r(n, t)) return;
		}
		return e(n, ...r);
	}));
}, ns = /* @__PURE__ */ s({ patchProp: Uo }, mo), rs;
function is() {
	return rs ||= ea(ns);
}
var as = ((...e) => {
	is().render(...e);
}), os = ((...e) => {
	let t = is().createApp(...e), { mount: n } = t;
	return t.mount = (e) => {
		let r = cs(e);
		if (!r) return;
		let i = t._component;
		h(i) || i.render || i.template || (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
		let a = n(r, !1, ss(r));
		return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), a;
	}, t;
});
function ss(e) {
	if (e instanceof SVGElement) return "svg";
	if (typeof MathMLElement == "function" && e instanceof MathMLElement) return "mathml";
}
function cs(e) {
	return g(e) ? document.querySelector(e) : e;
}
// src/api/client.ts
var ls = class extends Error {
	status;
	code;
	constructor(e, t, n = "") {
		super(e), this.status = t, this.code = n, this.name = "ApiError";
	}
};
async function us(e, t = {}, n) {
	let r = await fetch(e, {
		credentials: "same-origin",
		...t
	});
	if (!(r.headers.get("content-type") || "").includes("application/json")) throw new ls(r.redirected || r.status === 401 ? "登录已失效，请重新登录后刷新。" : `服务返回了非 JSON 响应（HTTP ${r.status}）`, r.status);
	let i = n ? n(await r.text()) : await r.json();
	if (!r.ok || i?.ok === !1) {
		let e = i?.error;
		throw new ls(typeof e == "string" ? e : e?.message || i?.message || `请求失败（HTTP ${r.status}）`, r.status, e?.code || i?.error_code || i?.code || "");
	}
	return i;
}
// src/components/CursorPagination.vue?vue&type=script&setup=true&lang.ts
var ds = ["aria-label", "aria-busy"], fs = { class: "cursor-pagination__layout" }, ps = {
	class: "cursor-pagination__count",
	"aria-live": "polite"
}, ms = { class: "cursor-pagination__actions" }, hs = ["disabled"], gs = ["disabled"], _s = ["disabled"], vs = /*@__PURE__*/ V({
	__name: "CursorPagination",
	props: {
		hasPrevious: { type: Boolean },
		nextCursor: {},
		itemCount: {},
		hasCursor: {
			type: Boolean,
			default: !1
		},
		busy: {
			type: Boolean,
			default: !1
		},
		label: { default: "列表分页" }
	},
	emits: [
		"previous",
		"next",
		"first"
	],
	setup(e, { emit: t }) {
		let n = e, r = t;
		function i() {
			!n.busy && n.hasPrevious && r("previous");
		}
		function a() {
			!n.busy && n.nextCursor && r("next");
		}
		function o() {
			!n.busy && n.hasCursor && r("first");
		}
		return (t, n) => (W(), G("nav", {
			class: "cursor-pagination",
			"aria-label": e.label,
			"aria-busy": e.busy
		}, [q("div", fs, [q("span", ps, "本页 " + A(e.itemCount) + " 个", 1), q("div", ms, [
			e.hasCursor ? (W(), G("button", {
				key: 0,
				type: "button",
				class: "cursor-pagination__first",
				"data-cursor-first": "",
				disabled: e.busy,
				onClick: o
			}, "返回首页", 8, hs)) : X("", !0),
			q("button", {
				type: "button",
				"data-cursor-previous": "",
				disabled: e.busy || !e.hasPrevious,
				onClick: i
			}, "上一页", 8, gs),
			q("button", {
				type: "button",
				"data-cursor-next": "",
				disabled: e.busy || !e.nextCursor,
				onClick: a
			}, "下一页", 8, _s)
		])])], 8, ds));
	}
}), ys = (e, t) => {
	let n = e.__vccOpts || e;
	for (let [e, r] of t) n[e] = r;
	return n;
}, bs = /*#__PURE__*/ ys(vs, [["__scopeId", "data-v-7fd57e6e"]]);
// node_modules/reka-ui/dist/shared/createContext.js
function xs(e, t) {
	let n = typeof e == "string" && !t ? `${e}Context` : t, r = Symbol(n);
	return [(t) => {
		let n = qn(r, t);
		if (n || n === null) return n;
		throw Error(`Injection \`${r.toString()}\` not found. Component must be used within ${Array.isArray(e) ? `one of the following components: ${e.join(", ")}` : `\`${e}\``}`);
	}, (e) => (Kn(r, e), e)];
}
// node_modules/reka-ui/dist/shared/getActiveElement.js
function Ss() {
	let e = document.activeElement;
	if (e == null) return null;
	for (; e != null && e.shadowRoot != null && e.shadowRoot.activeElement != null;) e = e.shadowRoot.activeElement;
	return e;
}
// node_modules/reka-ui/dist/shared/handleAndDispatchCustomEvent.js
function Cs(e, t, n) {
	let r = n.originalEvent.target, i = new CustomEvent(e, {
		bubbles: !1,
		cancelable: !0,
		detail: n
	});
	t && r.addEventListener(e, t, { once: !0 }), r.dispatchEvent(i);
}
// node_modules/@vueuse/shared/dist/index.js
function ws(e, t) {
	return Oe() ? (ke(e, t), !0) : !1;
}
function Ts(e) {
	let t = !1, n, r = De(!0);
	return ((...i) => (t ||= (n = r.run(() => e(...i)), !0), n));
}
var Es = typeof window < "u" && typeof document < "u";
typeof WorkerGlobalScope < "u" && globalThis instanceof WorkerGlobalScope;
var Ds = (e) => e !== void 0, Os = Object.prototype.toString, ks = (e) => Os.call(e) === "[object Object]", As = /* #__PURE__ */ js();
function js() {
	var e, t;
	return Es && !!((e = window) != null && (e = e.navigator) != null && e.userAgent) && (/iP(?:ad|hone|od)/.test(window.navigator.userAgent) || ((t = window) == null || (t = t.navigator) == null ? void 0 : t.maxTouchPoints) > 2 && /iPad|Macintosh/.test(window?.navigator.userAgent));
}
function Ms(e) {
	return Array.isArray(e) ? e : [e];
}
function Ns(e) {
	return e || za();
}
function Ps(e) {
	if (!Es) return e;
	let t = 0, n, r, i = () => {
		--t, r && t <= 0 && (r.stop(), n = void 0, r = void 0);
	};
	return ((...a) => (t += 1, r || (r = De(!0), n = r.run(() => e(...a))), ws(i), n));
}
function Fs(e) {
	return /* @__PURE__ */ Ht(/* @__PURE__ */ P(e) ? new Proxy({}, {
		get(t, n, r) {
			return I(Reflect.get(e.value, n, r));
		},
		set(t, n, r) {
			return /* @__PURE__ */ P(e.value[n]) && !/* @__PURE__ */ P(r) ? e.value[n].value = r : e.value[n] = r, !0;
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
function Is(e) {
	return Fs(Z(e));
}
function Ls(e, ...t) {
	let n = t.flat(), r = n[0];
	return Is(() => Object.fromEntries(typeof r == "function" ? Object.entries(/* @__PURE__ */ sn(e)).filter(([e, t]) => !r(L(t), e)) : Object.entries(/* @__PURE__ */ sn(e)).filter((e) => !n.includes(e[0]))));
}
function Rs(e, t) {
	Ns(t) && Rr(e, t);
}
function zs(e, t, n) {
	return B(e, t, {
		...n,
		immediate: !0
	});
}
// node_modules/@vueuse/core/dist/index.js
var Bs = Es ? window : void 0;
Es && window.document, Es && window.navigator, Es && window.location;
function Vs(e) {
	let t = L(e);
	return t?.$el ?? t;
}
function Hs(...e) {
	let t = (e, t, n, r) => (e.addEventListener(t, n, r), () => e.removeEventListener(t, n, r)), n = Z(() => {
		let t = Ms(L(e[0])).filter((e) => e != null);
		return t.every((e) => typeof e != "string") ? t : void 0;
	});
	return zs(() => [
		n.value?.map((e) => Vs(e)) ?? [Bs].filter((e) => e != null),
		Ms(L(n.value ? e[1] : e[0])),
		Ms(I(n.value ? e[2] : e[1])),
		L(n.value ? e[3] : e[2])
	], ([e, n, r, i], a, o) => {
		if (!e?.length || !n?.length || !r?.length) return;
		let s = ks(i) ? { ...i } : i, c = e.flatMap((e) => n.flatMap((n) => r.map((r) => t(e, n, r, s))));
		o(() => {
			c.forEach((e) => e());
		});
	}, { flush: "post" });
}
function Us() {
	let e = /* @__PURE__ */ en(!1), t = za();
	return t && Fr(() => {
		e.value = !0;
	}, t), e;
}
function Ws(e) {
	return typeof e == "function" ? e : typeof e == "string" ? (t) => t.key === e : Array.isArray(e) ? (t) => e.includes(t.key) : () => !0;
}
function Gs(...e) {
	let t, n, r = {};
	e.length === 3 ? (t = e[0], n = e[1], r = e[2]) : e.length === 2 ? typeof e[1] == "object" ? (t = !0, n = e[0], r = e[1]) : (t = e[0], n = e[1]) : (t = !0, n = e[0]);
	let { target: i = Bs, eventName: a = "keydown", passive: o = !1, dedupe: s = !1 } = r, c = Ws(t);
	return Hs(i, a, (e) => {
		e.repeat && L(s) || c(e) && n(e);
	}, o);
}
function Ks(e) {
	return JSON.parse(JSON.stringify(e));
}
function qs(e, t, n, r = {}) {
	var i, a;
	let { clone: o = !1, passive: s = !1, eventName: c, deep: l = !1, defaultValue: u, shouldEmit: d } = r, f = za(), p = n || f?.emit || (f == null || (i = f.$emit) == null ? void 0 : i.bind(f)) || (f == null || (a = f.proxy) == null || (a = a.$emit) == null ? void 0 : a.bind(f?.proxy)), m = c;
	t ||= "modelValue", m ||= `update:${t.toString()}`;
	let h = (e) => o ? typeof o == "function" ? o(e) : Ks(e) : e, g = () => Ds(e[t]) ? h(e[t]) : u, _ = (e) => {
		d ? d(e) && p(m, e) : p(m, e);
	};
	if (s) {
		let n = /* @__PURE__ */ F(g()), r = !1;
		return B(() => e[t], (e) => {
			r || (r = !0, n.value = h(e), jn(() => r = !1));
		}), B(n, (n) => {
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
function Js(e) {
	return e ? e.flatMap((e) => e.type === U ? Js(e.children) : [e]) : [];
}
// node_modules/reka-ui/dist/ConfigProvider/ConfigProvider.js
var [Ys, Xs] = /*#__PURE__*/ xs("ConfigProvider"), Zs = /* @__PURE__ */ new WeakMap();
function Qs(e, t) {
	let n = Zs.get(e);
	n || (n = {
		owners: /* @__PURE__ */ new Set(),
		original: e.body.style.pointerEvents
	}, Zs.set(e, n)), n.owners.add(t), e.body.style.pointerEvents = "none";
}
function $s(e, t) {
	let n = Zs.get(e);
	n?.owners.delete(t) && n.owners.size === 0 && (Zs.delete(e), e.body.style.pointerEvents = n.original);
}
// node_modules/defu/dist/defu.mjs
function ec(e) {
	if (typeof e != "object" || !e) return !1;
	let t = Object.getPrototypeOf(e);
	return t !== null && t !== Object.prototype && Object.getPrototypeOf(t) !== null || Symbol.iterator in e ? !1 : Symbol.toStringTag in e ? Object.prototype.toString.call(e) === "[object Module]" : !0;
}
function tc(e, t, n = ".", r) {
	if (!ec(t)) return tc(e, {}, n, r);
	let i = { ...t };
	for (let t of Object.keys(e)) {
		if (t === "__proto__" || t === "constructor") continue;
		let a = e[t];
		a != null && (r && r(i, t, a, n) || (i[t] = Array.isArray(a) && Array.isArray(i[t]) ? [...a, ...i[t]] : ec(a) && ec(i[t]) ? tc(a, i[t], (n ? `${n}.` : "") + t.toString(), r) : a));
	}
	return i;
}
function nc(e) {
	return (...t) => t.reduce((t, n) => tc(t, n, "", e), {});
}
var rc = nc(), ic = Symbol("useBodyScrollLock"), ac = Ps(() => {
	let e = /* @__PURE__ */ F(/* @__PURE__ */ new Map()), t = /* @__PURE__ */ F(), n = Z(() => {
		for (let t of e.value.values()) if (t) return !0;
		return !1;
	}), r = Ys({ scrollBody: /* @__PURE__ */ F(!0) }), i = null, a = () => {
		document.body.style.paddingRight = "", document.body.style.marginRight = "", $s(document, ic), document.documentElement.style.removeProperty("--scrollbar-width"), document.body.style.overflow = t.value ?? "", As && i?.(), t.value = void 0;
	};
	return B(n, (e, o) => {
		if (!Es) return;
		if (!e) {
			o && a();
			return;
		}
		t.value === void 0 && (t.value = document.body.style.overflow);
		let s = window.innerWidth - document.documentElement.clientWidth, c = {
			padding: s,
			margin: 0
		}, l = r.scrollBody?.value ? typeof r.scrollBody.value == "object" ? rc({
			padding: r.scrollBody.value.padding === !0 ? s : r.scrollBody.value.padding,
			margin: r.scrollBody.value.margin === !0 ? s : r.scrollBody.value.margin
		}, c) : c : {
			padding: 0,
			margin: 0
		};
		s > 0 && (document.body.style.paddingRight = typeof l.padding == "number" ? `${l.padding}px` : String(l.padding), document.body.style.marginRight = typeof l.margin == "number" ? `${l.margin}px` : String(l.margin), document.documentElement.style.setProperty("--scrollbar-width", `${s}px`), document.body.style.overflow = "hidden"), As && (i = Hs(document, "touchmove", (e) => cc(e), { passive: !1 })), jn(() => {
			n.value && (Qs(document, ic), document.body.style.overflow = "hidden");
		});
	}, {
		immediate: !0,
		flush: "sync"
	}), e;
});
function oc(e) {
	let t = Math.random().toString(36).substring(2, 7), n = ac();
	n.value.set(t, e ?? !1);
	let r = Z({
		get: () => n.value.get(t) ?? !1,
		set: (e) => n.value.set(t, e)
	});
	return Rs(() => {
		n.value.delete(t);
	}), r;
}
function sc(e) {
	let t = window.getComputedStyle(e);
	if (t.overflowX === "scroll" || t.overflowY === "scroll" || t.overflowX === "auto" && e.clientWidth < e.scrollWidth || t.overflowY === "auto" && e.clientHeight < e.scrollHeight) return !0;
	{
		let t = e.parentNode;
		return !(t instanceof Element) || t.tagName === "BODY" ? !1 : sc(t);
	}
}
function cc(e) {
	let t = e || window.event, n = t.target;
	return n instanceof Element && sc(n) ? !1 : t.touches.length > 1 || (t.preventDefault && t.cancelable && t.preventDefault(), !1);
}
// node_modules/reka-ui/dist/shared/useDirection.js
function lc(e) {
	let t = Ys({ dir: /* @__PURE__ */ F("ltr") });
	return Z(() => e?.value || t.dir?.value || "ltr");
}
// node_modules/reka-ui/dist/shared/useEmitAsProps.js
function uc(e) {
	let t = za(), n = t?.type.emits, r = {};
	return n?.length || console.warn(`No emitted event found. Please check component: ${t?.type.__name}`), n?.forEach((t) => {
		r[ie(E(t))] = (...n) => e(t, ...n);
	}), r;
}
// node_modules/reka-ui/dist/shared/useFocusGuards.js
var dc = 0;
function fc() {
	Xn((e) => {
		if (!Es) return;
		let t = document.querySelectorAll("[data-reka-focus-guard]");
		document.body.insertAdjacentElement("afterbegin", t[0] ?? pc()), document.body.insertAdjacentElement("beforeend", t[1] ?? pc()), dc++, e(() => {
			dc === 1 && document.querySelectorAll("[data-reka-focus-guard]").forEach((e) => e.remove()), dc--;
		});
	});
}
function pc() {
	let e = document.createElement("span");
	return e.setAttribute("data-reka-focus-guard", ""), e.tabIndex = 0, e.style.outline = "none", e.style.opacity = "0", e.style.position = "fixed", e.style.pointerEvents = "none", e;
}
// node_modules/reka-ui/dist/shared/useForwardExpose.js
function mc() {
	let e = za(), t = /* @__PURE__ */ F(), n = Z(() => r());
	Lr(() => {
		n.value !== r() && rn(t);
	});
	function r() {
		return t.value && "$el" in t.value && ["#text", "#comment"].includes(t.value.$el.nodeName) ? t.value.$el.nextElementSibling : Vs(t);
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
function hc(e) {
	let t = za(), n = Object.keys(t?.type.props ?? {}).reduce((e, n) => {
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
function gc(e, t) {
	let n = hc(e), r = t ? uc(t) : {};
	return Z(() => ({
		...n.value,
		...r
	}));
}
// node_modules/aria-hidden/dist/es2015/index.js
var _c = function(e) {
	return typeof document > "u" ? null : (Array.isArray(e) ? e[0] : e).ownerDocument.body;
}, vc = /* @__PURE__ */ new WeakMap(), yc = /* @__PURE__ */ new WeakMap(), bc = {}, xc = 0, Sc = function(e) {
	return e && (e.host || Sc(e.parentNode));
}, Cc = function(e, t) {
	return t.map(function(t) {
		if (e.contains(t)) return t;
		var n = Sc(t);
		return n && e.contains(n) ? n : (console.error("aria-hidden", t, "in not contained inside", e, ". Doing nothing"), null);
	}).filter(function(e) {
		return !!e;
	});
}, wc = function(e, t, n, r) {
	var i = Cc(t, Array.isArray(e) ? e : [e]);
	bc[n] || (bc[n] = /* @__PURE__ */ new WeakMap());
	var a = bc[n], o = [], s = /* @__PURE__ */ new Set(), c = new Set(i), l = function(e) {
		e && !s.has(e) && (s.add(e), l(e.parentNode));
	};
	i.forEach(l);
	var u = function(e) {
		e && !c.has(e) && Array.prototype.forEach.call(e.children, function(e) {
			if (s.has(e)) u(e);
			else try {
				var t = e.getAttribute(r), i = t !== null && t !== "false", c = (vc.get(e) || 0) + 1, l = (a.get(e) || 0) + 1;
				vc.set(e, c), a.set(e, l), o.push(e), c === 1 && i && yc.set(e, !0), l === 1 && e.setAttribute(n, "true"), i || e.setAttribute(r, "true");
			} catch (t) {
				console.error("aria-hidden: cannot operate on ", e, t);
			}
		});
	};
	return u(t), s.clear(), xc++, function() {
		o.forEach(function(e) {
			var t = vc.get(e) - 1, i = a.get(e) - 1;
			vc.set(e, t), a.set(e, i), t || (yc.has(e) || e.removeAttribute(r), yc.delete(e)), i || e.removeAttribute(n);
		}), xc--, xc || (vc = /* @__PURE__ */ new WeakMap(), vc = /* @__PURE__ */ new WeakMap(), yc = /* @__PURE__ */ new WeakMap(), bc = {});
	};
}, Tc = function(e, t, n) {
	n === void 0 && (n = "data-aria-hidden");
	var r = Array.from(Array.isArray(e) ? e : [e]), i = t || _c(e);
	return i ? (r.push.apply(r, Array.from(i.querySelectorAll("[aria-live], script"))), wc(r, i, n, "aria-hidden")) : function() {
		return null;
	};
};
// node_modules/reka-ui/dist/shared/useHideOthers.js
function Ec(e) {
	let t;
	B(() => Vs(e), (e) => {
		let n = !1;
		try {
			n = !!e?.closest("[popover]:not(:popover-open)");
		} catch {}
		e && !n ? t = Tc(e) : t && t();
	}), zr(() => {
		t && t();
	});
}
function Dc(e, t = "reka") {
	if (e) return e;
	let n, r = Ys({ useId: void 0 });
	return n = r.useId ? r.useId() : br?.(), t ? `${t}-${n}` : n;
}
// node_modules/reka-ui/dist/shared/useSize.js
function Oc(e) {
	let t = /* @__PURE__ */ F(), n = Z(() => t.value?.width ?? 0), r = Z(() => t.value?.height ?? 0), i;
	return Fr(() => {
		let n = Vs(e);
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
function kc(e, t) {
	let n = /* @__PURE__ */ F(e);
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
function Ac(e, t) {
	let n = /* @__PURE__ */ F({}), r = /* @__PURE__ */ F("none"), i = /* @__PURE__ */ F(e), a = e.value ? "mounted" : "unmounted", o, s = t.value?.ownerDocument.defaultView ?? Bs, { state: c, dispatch: l } = kc(a, {
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
		if (Es) {
			let n = new CustomEvent(e, {
				bubbles: !1,
				cancelable: !1
			});
			t.value?.dispatchEvent(n);
		}
	};
	B(e, async (e, i) => {
		let a = i !== e;
		if (await jn(), a) {
			let a = r.value, o = jc(t.value);
			e ? (l("MOUNT"), u("enter"), o === "none" && u("after-enter")) : o === "none" || o === "undefined" || n.value?.display === "none" ? (l("UNMOUNT"), u("leave"), u("after-leave")) : i && a !== o ? (l("ANIMATION_OUT"), u("leave")) : (l("UNMOUNT"), u("after-leave"));
		}
	}, { immediate: !0 });
	let d = (e) => {
		if (e.target !== t.value) return;
		let n = jc(t.value), r = n.includes(CSS.escape(e.animationName)), a = c.value === "mounted" ? "enter" : "leave";
		if (r && (u(`after-${a}`), l("ANIMATION_END"), !i.value)) {
			let e = t.value.style.animationFillMode;
			t.value.style.animationFillMode = "forwards", o = s?.setTimeout(() => {
				t.value?.style.animationFillMode === "forwards" && (t.value.style.animationFillMode = e);
			});
		}
		n === "none" && l("ANIMATION_END");
	}, f = (e) => {
		e.target === t.value && (r.value = jc(t.value));
	}, p = B(t, (e, t) => {
		e ? (n.value = getComputedStyle(e), e.addEventListener("animationstart", f), e.addEventListener("animationcancel", d), e.addEventListener("animationend", d)) : (l("ANIMATION_END"), o !== void 0 && s?.clearTimeout(o), t?.removeEventListener("animationstart", f), t?.removeEventListener("animationcancel", d), t?.removeEventListener("animationend", d));
	}, { immediate: !0 }), m = B(c, () => {
		let e = jc(t.value);
		r.value = c.value === "mounted" ? e : "none";
	});
	return zr(() => {
		p(), m(), t.value && (t.value.removeEventListener("animationstart", f), t.value.removeEventListener("animationcancel", d), t.value.removeEventListener("animationend", d)), o !== void 0 && s?.clearTimeout(o);
	}), { isPresent: Z(() => ["mounted", "unmountSuspended"].includes(c.value)) };
}
function jc(e) {
	return e && getComputedStyle(e).animationName || "none";
}
// node_modules/reka-ui/dist/Presence/Presence.js
var Mc = /*#__PURE__*/ V({
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
		let { present: r, forceMount: i } = /* @__PURE__ */ sn(e), a = /* @__PURE__ */ F(), { isPresent: o } = Ac(r, a);
		n({ present: o });
		let s = t.default({ present: o.value });
		s = Js(s || []);
		let c = za();
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
		return () => i.value || r.value || o.value ? no(t.default({ present: o.value })[0], { ref: (e) => {
			let t = Vs(e);
			return t?.hasAttribute === void 0 || (t?.hasAttribute("data-reka-popper-content-wrapper") ? a.value = t.firstElementChild : a.value = t), t;
		} }) : null;
	}
}), Nc = /*#__PURE__*/ V({
	name: "PrimitiveSlot",
	inheritAttrs: !1,
	setup(e, { attrs: t, slots: n }) {
		return () => {
			if (!n.default) return null;
			let e = Js(n.default()), r = e.findIndex((e) => e.type !== ma);
			if (r === -1) return e;
			let i = e[r];
			delete i.props?.ref;
			let a = i.props ? Ma(t, i.props) : t, o = Oa({
				...i,
				props: {}
			}, a);
			return e.length === 1 ? o : (e[r] = o, e);
		};
	}
}), Pc = [
	"area",
	"img",
	"input"
], Fc = /*#__PURE__*/ V({
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
		return typeof r == "string" && Pc.includes(r) ? () => no(r, t) : r === "template" ? () => no(Nc, t, { default: n.default }) : () => no(e.as, t, { default: n.default });
	}
}), Ic = "dismissableLayer.pointerDownOutside", Lc = "dismissableLayer.focusOutside";
function Rc(e) {
	if (typeof e != "object" || !e) return !1;
	let t = e.ownerDocument?.defaultView;
	return typeof Element < "u" && e instanceof Element || !!t && e instanceof t.Element;
}
function zc(e, t) {
	if (!Rc(t)) return !1;
	if (e.contains(t)) return !0;
	let n = t.closest("[data-dismissable-layer]"), r = e.dataset.dismissableLayer === "" ? e : e.querySelector("[data-dismissable-layer]"), i = Array.from(e.ownerDocument.querySelectorAll("[data-dismissable-layer]"));
	return !!(n && (r === n || i.indexOf(r) < i.indexOf(n)));
}
function Bc(e, t, n = !0) {
	let r = /* @__PURE__ */ F(!1), i = /* @__PURE__ */ F(() => {});
	return Xn((a) => {
		if (!Es || !L(n)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			let a = n.target;
			if (t?.value && a) {
				if (zc(t.value, a)) o.removeEventListener("click", i.value), r.value = !1;
				else {
					if (n.target && !r.value) {
						let t = { originalEvent: n };
						function r() {
							Cs(Ic, e, t);
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
		L(n) && (r.value = !0);
	} };
}
function Vc(e, t, n = !0) {
	let r = /* @__PURE__ */ F(!1);
	return Xn((i) => {
		if (!Es || !L(n)) return;
		let a = t?.value?.ownerDocument ?? globalThis.document, o = async (n) => {
			if (!t?.value) return;
			await jn(), await jn();
			let i = n.target;
			t.value && i && !zc(t.value, i) && n.target && !r.value && Cs(Lc, e, { originalEvent: n });
		};
		a.addEventListener("focusin", o), i(() => a.removeEventListener("focusin", o));
	}), {
		onFocusCapture: () => {
			L(n) && (r.value = !0);
		},
		onBlurCapture: () => {
			L(n) && (r.value = !1);
		}
	};
}
// node_modules/reka-ui/dist/DismissableLayer/context.js
var Hc = /*#__PURE__*/ Ht({
	layersRoot: /* @__PURE__ */ new Set(),
	layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
	branches: /* @__PURE__ */ new Set()
}), Uc = /* @__PURE__ */ V({
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
		let n = e, r = t, { forwardRef: i, currentElement: a } = mc(), o = Z(() => a.value?.ownerDocument ?? globalThis.document), s = Z(() => Hc.layersRoot), c = Z(() => a.value ? Array.from(s.value).indexOf(a.value) : -1), l = Z(() => Hc.layersWithOutsidePointerEventsDisabled.size > 0), u = Z(() => {
			let e = Array.from(s.value), [t] = [...Hc.layersWithOutsidePointerEventsDisabled].slice(-1), n = e.indexOf(t);
			return c.value >= n;
		}), d = Bc(async (e) => {
			let t = [...Hc.branches].some((t) => t?.contains(e.target));
			n.present && u.value && !t && (r("pointerDownOutside", e), r("interactOutside", e), await jn(), e.defaultPrevented || r("dismiss"));
		}, a, () => n.present), f = Vc((e) => {
			let t = [...Hc.branches].some((t) => t?.contains(e.target));
			n.present && !t && (r("focusOutside", e), r("interactOutside", e), e.defaultPrevented || r("dismiss"));
		}, a);
		return Gs("Escape", (e) => {
			n.present && c.value === s.value.size - 1 && (r("escapeKeyDown", e), e.defaultPrevented || r("dismiss"));
		}, { target: () => o.value?.defaultView ?? globalThis.window }), B([
			a,
			() => n.disableOutsidePointerEvents,
			() => n.present
		], ([e, t, n], r, i) => {
			if (e && n && t) {
				let t = e.ownerDocument;
				Qs(t, e), Hc.layersWithOutsidePointerEventsDisabled.add(e), i(() => {
					Hc.layersWithOutsidePointerEventsDisabled.delete(e), $s(t, e);
				});
			}
		}, { immediate: !0 }), B([a, () => n.present], ([e, t], n, r) => {
			e && t && (s.value.add(e), r(() => {
				s.value.delete(e);
			}));
		}, { immediate: !0 }), Xn((e) => {
			e(() => {
				a.value && (s.value.delete(a.value), Hc.layersWithOutsidePointerEventsDisabled.delete(a.value));
			});
		}), (t, n) => (W(), K(I(Fc), {
			ref: I(i),
			"as-child": e.asChild,
			as: e.as,
			"data-dismissable-layer": "",
			style: ue({ pointerEvents: l.value ? u.value ? "auto" : "none" : void 0 }),
			onFocusCapture: I(f).onFocusCapture,
			onBlurCapture: I(f).onBlurCapture,
			onPointerdownCapture: I(d).onPointerDownCapture
		}, {
			default: z(() => [H(t.$slots, "default")]),
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
}), Wc = Ts(() => /* @__PURE__ */ F([]));
function Gc() {
	let e = Wc();
	return {
		add(t) {
			let n = e.value[0];
			t !== n && n?.pause(), e.value = Kc(e.value, t), e.value.unshift(t);
		},
		remove(t) {
			e.value = Kc(e.value, t), e.value[0]?.resume();
		}
	};
}
function Kc(e, t) {
	let n = [...e], r = n.indexOf(t);
	return r !== -1 && n.splice(r, 1), n;
}
// node_modules/reka-ui/dist/FocusScope/utils.js
var qc = "focusScope.autoFocusOnMount", Jc = "focusScope.autoFocusOnUnmount", Yc = {
	bubbles: !1,
	cancelable: !0
};
function Xc(e, t) {
	let n = t;
	for (; n;) {
		if (e.contains(n)) return !0;
		n = n.getRootNode().host ?? null;
	}
	return !1;
}
function Zc(e, { select: t = !1 } = {}) {
	let n = Ss();
	for (let r of e) if (rl(r, { select: t }), Ss() !== n) return !0;
}
function Qc(e) {
	let t = $c(e);
	return [el(t, e), el(t.reverse(), e)];
}
function $c(e) {
	let t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, { acceptNode: (e) => {
		let t = e.tagName === "INPUT" && e.type === "hidden";
		return e.disabled || e.hidden || t ? NodeFilter.FILTER_SKIP : e.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
	} });
	for (; n.nextNode();) t.push(n.currentNode);
	return t.sort((e, t) => e.tabIndex === t.tabIndex ? 0 : e.tabIndex === 0 ? 1 : t.tabIndex === 0 ? -1 : e.tabIndex - t.tabIndex);
}
function el(e, t) {
	for (let n of e) if (!tl(n, { upTo: t })) return n;
}
function tl(e, { upTo: t }) {
	if (getComputedStyle(e).visibility === "hidden") return !0;
	for (; e;) {
		if (t !== void 0 && e === t) return !1;
		if (getComputedStyle(e).display === "none") return !0;
		e = e.parentElement;
	}
	return !1;
}
function nl(e) {
	return e instanceof HTMLInputElement && "select" in e;
}
function rl(e, { select: t = !1 } = {}) {
	if (e && e.focus) {
		let n = Ss();
		e.focus({ preventScroll: !0 }), e !== n && nl(e) && t && e.select();
	}
}
// node_modules/reka-ui/dist/FocusScope/FocusScope.js
var il = /* @__PURE__ */ V({
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
		let n = e, r = t, { currentRef: i, currentElement: a } = mc(), o = /* @__PURE__ */ F(null), s = Gc(), c = /*#__PURE__*/ Ht({
			paused: !1,
			pause() {
				this.paused = !0;
			},
			resume() {
				this.paused = !1;
			}
		});
		Xn((e) => {
			if (!Es) return;
			let t = a.value;
			if (!n.trapped) return;
			let r = t?.ownerDocument ?? document, i = t ? t.getRootNode() : r;
			function s(e) {
				if (c.paused || !t) return;
				let n = e.target;
				t.contains(n) ? o.value = n : rl(o.value, { select: !0 });
			}
			function l(e) {
				if (c.paused || !t) return;
				let n = e.relatedTarget;
				n !== null && (t.contains(n) || rl(o.value, { select: !0 }));
			}
			function u(e) {
				let n = o.value;
				if (n === null || !e.some((e) => e.removedNodes.length > 0)) return;
				let r = Ss();
				r && t.contains(r) || t.contains(n) || rl(t);
			}
			function d(e) {
				if (c.paused || !t) return;
				let n = e.composedPath()[0];
				Xc(t, n) || rl(o.value, { select: !0 });
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
			let n = new CustomEvent(qc, Yc), i = (e) => r("mountAutoFocus", e);
			e.addEventListener(qc, i), e.dispatchEvent(n), e.removeEventListener(qc, i), n.defaultPrevented || (Zc($c(e), { select: !0 }), Ss() === t && rl(e));
		}
		Xn(async (e) => {
			let t = a.value;
			if (await jn(), !t) return;
			n.present !== !1 && s.add(c);
			let i = Ss();
			!t.contains(i) && n.present !== !1 && l(t, i), e(() => {
				let e = new CustomEvent(Jc, Yc), n = (e) => {
					r("unmountAutoFocus", e);
				};
				t.addEventListener(Jc, n), t.dispatchEvent(e), t.setAttribute("data-focus-scope-unmounting", ""), setTimeout(() => {
					e.defaultPrevented || rl(i ?? document.body, { select: !0 }), t.removeEventListener(Jc, n), s.remove(c), t.removeAttribute("data-focus-scope-unmounting");
				}, 0);
			});
		}), B(() => n.present, async (e, t) => {
			if (!Es) return;
			if (e === !1 && t === !0) {
				s.remove(c);
				return;
			}
			if (e !== !0 || t !== !1) return;
			s.add(c), await jn();
			let n = a.value;
			if (!n) return;
			let r = Ss();
			n.contains(r) || l(n, r);
		});
		function u(e) {
			if (!n.loop && !n.trapped || c.paused) return;
			let t = e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey, r = Ss();
			if (t && r) {
				let t = e.currentTarget, [i, a] = Qc(t);
				i && a ? !e.shiftKey && r === a ? (e.preventDefault(), n.loop && rl(i, { select: !0 })) : e.shiftKey && r === i && (e.preventDefault(), n.loop && rl(a, { select: !0 })) : r === t && e.preventDefault();
			}
		}
		return (t, n) => (W(), K(I(Fc), {
			ref_key: "currentRef",
			ref: i,
			tabindex: "-1",
			"as-child": e.asChild,
			as: e.as,
			onKeydown: u
		}, {
			default: z(() => [H(t.$slots, "default")]),
			_: 3
		}, 8, ["as-child", "as"]));
	}
}), al = /* @__PURE__ */ V({
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
		let t = e, n = Ys({}), r = Z(() => t.to ?? n.teleportTo?.value ?? "body"), i = Us();
		return (t, n) => I(i) || e.forceMount ? (W(), K(fr, {
			key: 0,
			to: r.value,
			disabled: e.disabled,
			defer: e.defer
		}, [H(t.$slots, "default")], 8, [
			"to",
			"disabled",
			"defer"
		])) : X("v-if", !0);
	}
}), [ol, sl] = /*#__PURE__*/ xs("PopperRoot"), cl = /* @__PURE__ */ V({
	inheritAttrs: !1,
	__name: "PopperRoot",
	setup(e) {
		let t = /* @__PURE__ */ F();
		return sl({
			anchor: t,
			onAnchorChange: (e) => t.value = e
		}), (e, t) => H(e.$slots, "default");
	}
}), ll = /* @__PURE__ */ V({
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
		let t = e, { forwardRef: n, currentElement: r } = mc(), i = ol();
		return Zn(() => {
			i.onAnchorChange(t.reference ?? r.value);
		}), (t, r) => (W(), K(I(Fc), {
			ref: I(n),
			as: e.as,
			"as-child": e.asChild
		}, {
			default: z(() => [H(t.$slots, "default")]),
			_: 3
		}, 8, ["as", "as-child"]));
	}
});
// node_modules/reka-ui/dist/Popper/utils.js
function ul(e) {
	return e !== null;
}
function dl(e) {
	return {
		name: "transformOrigin",
		options: e,
		fn(t) {
			let { placement: n, rects: r, middlewareData: i } = t, a = i.arrow?.centerOffset !== 0, o = a ? 0 : e.arrowWidth, s = a ? 0 : e.arrowHeight, [c, l] = fl(n), u = {
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
function fl(e) {
	let [t, n = "center"] = e.split("-");
	return [t, n];
}
// node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs
var pl = [
	"top",
	"right",
	"bottom",
	"left"
], ml = Math.min, hl = Math.max, gl = Math.round, _l = Math.floor, vl = (e) => ({
	x: e,
	y: e
}), yl = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function bl(e, t, n) {
	return hl(e, ml(t, n));
}
function xl(e, t) {
	return typeof e == "function" ? e(t) : e;
}
function Sl(e) {
	return e.split("-")[0];
}
function Cl(e) {
	return e.split("-")[1];
}
function wl(e) {
	return e === "x" ? "y" : "x";
}
function Tl(e) {
	return e === "y" ? "height" : "width";
}
function El(e) {
	let t = e[0];
	return t === "t" || t === "b" ? "y" : "x";
}
function Dl(e) {
	return wl(El(e));
}
function Ol(e, t, n) {
	n === void 0 && (n = !1);
	let r = Cl(e), i = Dl(e), a = Tl(i), o = i === "x" ? r === (n ? "end" : "start") ? "right" : "left" : r === "start" ? "bottom" : "top";
	return t.reference[a] > t.floating[a] && (o = Ll(o)), [o, Ll(o)];
}
function kl(e) {
	let t = Ll(e);
	return [
		Al(e),
		t,
		Al(t)
	];
}
function Al(e) {
	return e.includes("start") ? e.replace("start", "end") : e.replace("end", "start");
}
var jl = ["left", "right"], Ml = ["right", "left"], Nl = ["top", "bottom"], Pl = ["bottom", "top"];
function Fl(e, t, n) {
	switch (e) {
		case "top":
		case "bottom": return n ? t ? Ml : jl : t ? jl : Ml;
		case "left":
		case "right": return t ? Nl : Pl;
		default: return [];
	}
}
function Il(e, t, n, r) {
	let i = Cl(e), a = Fl(Sl(e), n === "start", r);
	return i && (a = a.map((e) => e + "-" + i), t && (a = a.concat(a.map(Al)))), a;
}
function Ll(e) {
	let t = Sl(e);
	return yl[t] + e.slice(t.length);
}
function Rl(e) {
	return {
		top: e.top ?? 0,
		right: e.right ?? 0,
		bottom: e.bottom ?? 0,
		left: e.left ?? 0
	};
}
function zl(e) {
	return typeof e == "number" ? {
		top: e,
		right: e,
		bottom: e,
		left: e
	} : Rl(e);
}
function Bl(e) {
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
function Vl(e, t, n) {
	let { reference: r, floating: i } = e, a = El(t), o = Dl(t), s = Tl(o), c = Sl(t), l = a === "y", u = r.x + r.width / 2 - i.width / 2, d = r.y + r.height / 2 - i.height / 2, f = r[s] / 2 - i[s] / 2, p;
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
	let m = Cl(t);
	return m && (p[o] += f * (m === "end" ? 1 : -1) * (n && l ? -1 : 1)), p;
}
async function Hl(e, t) {
	t === void 0 && (t = {});
	let { x: n, y: r, platform: i, rects: a, elements: o, strategy: s } = e, { boundary: c = "clippingAncestors", rootBoundary: l = "viewport", elementContext: u = "floating", altBoundary: d = !1, padding: f = 0 } = xl(t, e), p = zl(f), m = o[d ? u === "floating" ? "reference" : "floating" : u], h = Bl(await i.getClippingRect({
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
	}, y = Bl(i.convertOffsetParentRelativeRectToViewportRelativeRect ? await i.convertOffsetParentRelativeRectToViewportRelativeRect({
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
var Ul = 50, Wl = async (e, t, n) => {
	let { placement: r = "bottom", strategy: i = "absolute", middleware: a = [], platform: o } = n, s = o.detectOverflow ? o : {
		...o,
		detectOverflow: Hl
	}, c = await (o.isRTL == null ? void 0 : o.isRTL(t)), l = await o.getElementRects({
		reference: e,
		floating: t,
		strategy: i
	}), { x: u, y: d } = Vl(l, r, c), f = r, p = 0, m = {};
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
		}, x && p < Ul && (p++, typeof x == "object" && (x.placement && (f = x.placement), x.rects && (l = x.rects === !0 ? await o.getElementRects({
			reference: e,
			floating: t,
			strategy: i
		}) : x.rects), {x: u, y: d} = Vl(l, f, c)), n = -1);
	}
	return {
		x: u,
		y: d,
		placement: f,
		strategy: i,
		middlewareData: m
	};
}, Gl = (e) => ({
	name: "arrow",
	options: e,
	async fn(t) {
		let { x: n, y: r, placement: i, rects: a, platform: o, elements: s, middlewareData: c } = t, { element: l, padding: u = 0 } = xl(e, t) || {};
		if (l == null) return {};
		let d = zl(u), f = {
			x: n,
			y: r
		}, p = Dl(i), m = Tl(p), h = await o.getDimensions(l), g = p === "y", _ = g ? "top" : "left", v = g ? "bottom" : "right", y = g ? "clientHeight" : "clientWidth", b = a.reference[m] + a.reference[p] - f[p] - a.floating[m], x = f[p] - a.reference[p], S = await (o.getOffsetParent == null ? void 0 : o.getOffsetParent(l)), C = S ? S[y] : 0;
		C && await (o.isElement == null ? void 0 : o.isElement(S)) || (C = s.floating[y] || a.floating[m]);
		let w = b / 2 - x / 2, T = C / 2 - h[m] / 2 - 1, ee = ml(d[_], T), te = ml(d[v], T), E = C - h[m] - te, ne = C / 2 - h[m] / 2 + w, D = bl(ee, ne, E), re = !c.arrow && Cl(i) != null && ne !== D && a.reference[m] / 2 - (ne < ee ? ee : te) - h[m] / 2 < 0, ie = re ? ne < ee ? ne - ee : ne - E : 0;
		return {
			[p]: f[p] + ie,
			data: {
				[p]: D,
				centerOffset: ne - D - ie,
				...re && { alignmentOffset: ie }
			},
			reset: re
		};
	}
}), Kl = function(e) {
	return e === void 0 && (e = {}), {
		name: "flip",
		options: e,
		async fn(t) {
			var n;
			let { placement: r, middlewareData: i, rects: a, initialPlacement: o, platform: s, elements: c } = t, { mainAxis: l = !0, crossAxis: u = !0, fallbackPlacements: d, fallbackStrategy: f = "bestFit", fallbackAxisSideDirection: p = "none", flipAlignment: m = !0, ...h } = xl(e, t);
			if ((n = i.arrow) != null && n.alignmentOffset) return {};
			let g = Sl(r), _ = El(o), v = Sl(o) === o, y = await (s.isRTL == null ? void 0 : s.isRTL(c.floating)), b = d || (v || !m ? [Ll(o)] : kl(o)), x = p !== "none";
			!d && x && b.push(...Il(o, m, p, y));
			let S = [o, ...b], C = await s.detectOverflow(t, h), w = [], T = i.flip?.overflows || [];
			if (l && w.push(C[g]), u) {
				let e = Ol(r, a, y);
				w.push(C[e[0]], C[e[1]]);
			}
			if (T = [...T, {
				placement: r,
				overflows: w
			}], !w.every((e) => e <= 0)) {
				let e = (i.flip?.index || 0) + 1, t = S[e];
				if (t && (u !== "alignment" || _ === El(t) || T.every((e) => El(e.placement) !== _ || e.overflows[0] > 0))) return {
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
								let t = El(e.placement);
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
function ql(e, t) {
	return {
		top: e.top - t.height,
		right: e.right - t.width,
		bottom: e.bottom - t.height,
		left: e.left - t.width
	};
}
function Jl(e) {
	return pl.some((t) => e[t] >= 0);
}
var Yl = function(e) {
	return e === void 0 && (e = {}), {
		name: "hide",
		options: e,
		async fn(t) {
			let { rects: n, platform: r } = t, { strategy: i = "referenceHidden", ...a } = xl(e, t);
			switch (i) {
				case "referenceHidden": {
					let e = ql(await r.detectOverflow(t, {
						...a,
						elementContext: "reference"
					}), n.reference);
					return { data: {
						referenceHiddenOffsets: e,
						referenceHidden: Jl(e)
					} };
				}
				case "escaped": {
					let e = ql(await r.detectOverflow(t, {
						...a,
						altBoundary: !0
					}), n.floating);
					return { data: {
						escapedOffsets: e,
						escaped: Jl(e)
					} };
				}
				default: return {};
			}
		}
	};
}, Xl = /*#__PURE__*/ new Set(["left", "top"]);
async function Zl(e, t) {
	let { placement: n, platform: r, elements: i } = e, a = await (r.isRTL == null ? void 0 : r.isRTL(i.floating)), o = Sl(n), s = Cl(n), c = El(n) === "y", l = Xl.has(o) ? -1 : 1, u = a && c ? -1 : 1, d = xl(t, e), { mainAxis: f, crossAxis: p, alignmentAxis: m } = typeof d == "number" ? {
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
var Ql = function(e) {
	return e === void 0 && (e = 0), {
		name: "offset",
		options: e,
		async fn(t) {
			var n;
			let { x: r, y: i, placement: a, middlewareData: o } = t, s = await Zl(t, e);
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
}, $l = function(e) {
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
			} }, ...l } = xl(e, t), u = {
				x: n,
				y: r
			}, d = await a.detectOverflow(t, l), f = El(i), p = wl(f), m = u[p], h = u[f], g = (e, t) => bl(t + d[e === "y" ? "top" : "left"], t, t - d[e === "y" ? "bottom" : "right"]);
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
}, eu = function(e) {
	return e === void 0 && (e = {}), {
		options: e,
		fn(t) {
			let { x: n, y: r, placement: i, rects: a, middlewareData: o } = t, { offset: s = 0, mainAxis: c = !0, crossAxis: l = !0 } = xl(e, t), u = {
				x: n,
				y: r
			}, d = El(i), f = wl(d), p = u[f], m = u[d], h = xl(s, t), g = typeof h == "number" ? {
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
				let e = f === "y" ? "width" : "height", t = Xl.has(Sl(i)), n = a.reference[d] - a.floating[e] + (t && o.offset?.[d] || 0) + (t ? 0 : g.crossAxis), r = a.reference[d] + a.reference[e] + (t ? 0 : o.offset?.[d] || 0) - (t ? g.crossAxis : 0);
				m < n ? m = n : m > r && (m = r);
			}
			return {
				[f]: p,
				[d]: m
			};
		}
	};
}, tu = function(e) {
	return e === void 0 && (e = {}), {
		name: "size",
		options: e,
		async fn(t) {
			let { placement: n, rects: r, platform: i, elements: a } = t, { apply: o = () => {}, ...s } = xl(e, t), c = await i.detectOverflow(t, s), l = Sl(n), u = Cl(n), d = El(n) === "y", { width: f, height: p } = r.floating, m, h;
			l === "top" || l === "bottom" ? (m = l, h = u === (await (i.isRTL == null ? void 0 : i.isRTL(a.floating)) ? "start" : "end") ? "left" : "right") : (h = l, m = u === "end" ? "top" : "bottom");
			let g = p - c.top - c.bottom, _ = f - c.left - c.right, v = ml(p - c[m], g), y = ml(f - c[h], _), b = t.middlewareData.shift, x = !b, S = v, C = y;
			b != null && b.enabled.x && (C = _), b != null && b.enabled.y && (S = g), x && !u && (d ? C = f - 2 * hl(c.left, c.right) : S = p - 2 * hl(c.top, c.bottom)), await o({
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
function nu() {
	return typeof window < "u";
}
function ru(e) {
	return ou(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function iu(e) {
	var t;
	return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function au(e) {
	return ((ou(e) ? e.ownerDocument : e.document) || window.document)?.documentElement;
}
function ou(e) {
	return nu() ? e instanceof Node || e instanceof iu(e).Node : !1;
}
function su(e) {
	return nu() ? e instanceof Element || e instanceof iu(e).Element : !1;
}
function cu(e) {
	return nu() ? e instanceof HTMLElement || e instanceof iu(e).HTMLElement : !1;
}
function lu(e) {
	return !nu() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof iu(e).ShadowRoot;
}
function uu(e) {
	let { overflow: t, overflowX: n, overflowY: r, display: i } = xu(e);
	return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && i !== "inline" && i !== "contents";
}
function du(e) {
	return /^(table|td|th)$/.test(ru(e));
}
function fu(e) {
	try {
		if (e.matches(":popover-open")) return !0;
	} catch {}
	try {
		return e.matches(":modal");
	} catch {
		return !1;
	}
}
var pu = /transform|translate|scale|rotate|perspective|filter/, mu = /paint|layout|strict|content/, hu = (e) => !!e && e !== "none", gu;
function _u(e) {
	let t = su(e) ? xu(e) : e;
	return hu(t.transform) || hu(t.translate) || hu(t.scale) || hu(t.rotate) || hu(t.perspective) || !yu() && (hu(t.backdropFilter) || hu(t.filter)) || pu.test(t.willChange || "") || mu.test(t.contain || "");
}
function vu(e) {
	let t = Cu(e);
	for (; cu(t) && !bu(t);) {
		if (_u(t)) return t;
		if (fu(t)) return null;
		t = Cu(t);
	}
	return null;
}
function yu() {
	return gu ??= typeof CSS < "u" && CSS.supports && CSS.supports("-webkit-backdrop-filter", "none"), gu;
}
function bu(e) {
	return /^(html|body|#document)$/.test(ru(e));
}
function xu(e) {
	return iu(e).getComputedStyle(e);
}
function Su(e) {
	return su(e) ? {
		scrollLeft: e.scrollLeft,
		scrollTop: e.scrollTop
	} : {
		scrollLeft: e.scrollX,
		scrollTop: e.scrollY
	};
}
function Cu(e) {
	if (ru(e) === "html") return e;
	let t = e.assignedSlot || e.parentNode || lu(e) && e.host || au(e);
	return lu(t) ? t.host : t;
}
function wu(e) {
	let t = Cu(e);
	return bu(t) ? (e.ownerDocument || e).body : cu(t) && uu(t) ? t : wu(t);
}
function Tu(e, t, n) {
	t === void 0 && (t = []), n === void 0 && (n = !0);
	let r = wu(e), i = r === e.ownerDocument?.body, a = iu(r);
	if (i) {
		let e = Eu(a);
		return t.concat(a, a.visualViewport || [], uu(r) ? r : [], e && n ? Tu(e) : []);
	}
	return t.concat(r, Tu(r, [], n));
}
function Eu(e) {
	return e.parent && Object.getPrototypeOf(e.parent) ? e.frameElement : null;
}
// node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs
function Du(e) {
	let t = xu(e), n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0, i = cu(e), a = i ? e.offsetWidth : n, o = i ? e.offsetHeight : r, s = gl(n) !== a || gl(r) !== o;
	return s && (n = a, r = o), {
		width: n,
		height: r,
		$: s
	};
}
function Ou(e) {
	return su(e) ? e : e.contextElement;
}
function ku(e) {
	let t = Ou(e);
	if (!cu(t)) return vl(1);
	let n = t.getBoundingClientRect(), { width: r, height: i, $: a } = Du(t), o = (a ? gl(n.width) : n.width) / r, s = (a ? gl(n.height) : n.height) / i;
	return o && Number.isFinite(o) || (o = 1), s && Number.isFinite(s) || (s = 1), {
		x: o,
		y: s
	};
}
var Au = /*#__PURE__*/ vl(0);
function ju(e) {
	let t = iu(e);
	return !yu() || !t.visualViewport ? Au : {
		x: t.visualViewport.offsetLeft,
		y: t.visualViewport.offsetTop
	};
}
function Mu(e, t, n) {
	return t === void 0 && (t = !1), !!n && t && n === iu(e);
}
function Nu(e, t, n, r) {
	t === void 0 && (t = !1), n === void 0 && (n = !1);
	let i = e.getBoundingClientRect(), a = Ou(e), o = vl(1);
	t && (r ? su(r) && (o = ku(r)) : o = ku(e));
	let s = Mu(a, n, r) ? ju(a) : vl(0), c = (i.left + s.x) / o.x, l = (i.top + s.y) / o.y, u = i.width / o.x, d = i.height / o.y;
	if (a && r) {
		let e = iu(a), t = su(r) ? iu(r) : r, n = e, i = Eu(n);
		for (; i && t !== n;) {
			let e = ku(i), t = i.getBoundingClientRect(), r = xu(i), a = t.left + (i.clientLeft + parseFloat(r.paddingLeft)) * e.x, o = t.top + (i.clientTop + parseFloat(r.paddingTop)) * e.y;
			c *= e.x, l *= e.y, u *= e.x, d *= e.y, c += a, l += o, n = iu(i), i = Eu(n);
		}
	}
	return Bl({
		width: u,
		height: d,
		x: c,
		y: l
	});
}
function Pu(e, t) {
	let n = Su(e).scrollLeft;
	return t ? t.left + n : Nu(au(e)).left + n;
}
function Fu(e, t) {
	let n = e.getBoundingClientRect();
	return {
		x: n.left + t.scrollLeft - Pu(e, n),
		y: n.top + t.scrollTop
	};
}
function Iu(e) {
	let { elements: t, rect: n, offsetParent: r, strategy: i } = e, a = i === "fixed", o = au(r), s = t ? fu(t.floating) : !1;
	if (r === o || s && a) return n;
	let c = {
		scrollLeft: 0,
		scrollTop: 0
	}, l = vl(1), u = vl(0), d = cu(r);
	if ((d || !a) && ((ru(r) !== "body" || uu(o)) && (c = Su(r)), d)) {
		let e = Nu(r);
		l = ku(r), u.x = e.x + r.clientLeft, u.y = e.y + r.clientTop;
	}
	let f = o && !d && !a ? Fu(o, c) : vl(0);
	return {
		width: n.width * l.x,
		height: n.height * l.y,
		x: n.x * l.x - c.scrollLeft * l.x + u.x + f.x,
		y: n.y * l.y - c.scrollTop * l.y + u.y + f.y
	};
}
function Lu(e) {
	return e.getClientRects ? Array.from(e.getClientRects()) : [];
}
function Ru(e) {
	let t = Su(e), n = e.ownerDocument.body, r = hl(e.scrollWidth, e.clientWidth, n.scrollWidth, n.clientWidth), i = hl(e.scrollHeight, e.clientHeight, n.scrollHeight, n.clientHeight), a = -t.scrollLeft + Pu(e), o = -t.scrollTop;
	return xu(n).direction === "rtl" && (a += hl(e.clientWidth, n.clientWidth) - r), {
		width: r,
		height: i,
		x: a,
		y: o
	};
}
var zu = 25;
function Bu(e, t, n) {
	n === void 0 && (n = "viewport");
	let r = n === "layoutViewport", i = iu(e), a = au(e), o = i.visualViewport, s = a.clientWidth, c = a.clientHeight, l = 0, u = 0;
	if (o) {
		let e = !yu() || t === "fixed";
		r ? e || (l = -o.offsetLeft, u = -o.offsetTop) : (s = o.width, c = o.height, e && (l = o.offsetLeft, u = o.offsetTop));
	}
	if (Pu(a) <= 0) {
		let e = a.ownerDocument, t = e.body, n = getComputedStyle(t), r = e.compatMode === "CSS1Compat" && parseFloat(n.marginLeft) + parseFloat(n.marginRight) || 0, i = Math.abs(a.clientWidth - t.clientWidth - r), o = getComputedStyle(a).scrollbarGutter === "stable both-edges" ? i / 2 : i;
		o <= zu && (s -= o);
	}
	return {
		width: s,
		height: c,
		x: l,
		y: u
	};
}
function Vu(e, t) {
	let n = Nu(e, !0, t === "fixed"), r = n.top + e.clientTop, i = n.left + e.clientLeft, a = ku(e);
	return {
		width: e.clientWidth * a.x,
		height: e.clientHeight * a.y,
		x: i * a.x,
		y: r * a.y
	};
}
function Hu(e, t, n) {
	let r;
	if (t === "viewport" || t === "layoutViewport") r = Bu(e, n, t);
	else if (t === "document") r = Ru(au(e));
	else if (su(t)) r = Vu(t, n);
	else {
		let n = ju(e);
		r = {
			x: t.x - n.x,
			y: t.y - n.y,
			width: t.width,
			height: t.height
		};
	}
	return Bl(r);
}
function Uu(e, t) {
	let n = t.get(e);
	if (n) return n;
	let r = Tu(e, [], !1).filter((e) => su(e) && ru(e) !== "body"), i = null, a = xu(e).position === "fixed", o = a ? Cu(e) : e;
	for (; su(o) && !bu(o);) {
		let e = xu(o), t = _u(o), n = i ? i.position : a ? "fixed" : "";
		!t && (n === "fixed" || n === "absolute" && e.position === "static") ? r = r.filter((e) => e !== o) : i = e, o = Cu(o);
	}
	return t.set(e, r), r;
}
function Wu(e) {
	let { element: t, boundary: n, rootBoundary: r, strategy: i } = e, a = [...n === "clippingAncestors" ? fu(t) ? [] : Uu(t, this._c) : [].concat(n), r], o = Hu(t, a[0], i), s = o.top, c = o.right, l = o.bottom, u = o.left;
	for (let e = 1; e < a.length; e++) {
		let n = Hu(t, a[e], i);
		s = hl(n.top, s), c = ml(n.right, c), l = ml(n.bottom, l), u = hl(n.left, u);
	}
	return {
		width: c - u,
		height: l - s,
		x: u,
		y: s
	};
}
function Gu(e) {
	let { width: t, height: n } = Du(e);
	return {
		width: t,
		height: n
	};
}
function Ku(e, t, n) {
	let r = cu(t), i = au(t), a = n === "fixed", o = Nu(e, !0, a, t), s = {
		scrollLeft: 0,
		scrollTop: 0
	}, c = vl(0);
	if ((r || !a) && ((ru(t) !== "body" || uu(i)) && (s = Su(t)), r)) {
		let e = Nu(t, !0, a, t);
		c.x = e.x + t.clientLeft, c.y = e.y + t.clientTop;
	}
	!r && i && (c.x = Pu(i));
	let l = i && !r && !a ? Fu(i, s) : vl(0);
	return {
		x: o.left + s.scrollLeft - c.x - l.x,
		y: o.top + s.scrollTop - c.y - l.y,
		width: o.width,
		height: o.height
	};
}
function qu(e) {
	return xu(e).position === "static";
}
function Ju(e, t) {
	if (!cu(e) || xu(e).position === "fixed") return null;
	if (t) return t(e);
	let n = e.offsetParent;
	return au(e) === n && (n = n.ownerDocument.body), n;
}
function Yu(e, t) {
	let n = iu(e);
	if (fu(e)) return n;
	if (!cu(e)) {
		let t = Cu(e);
		for (; t && !bu(t);) {
			if (su(t) && !qu(t)) return t;
			t = Cu(t);
		}
		return n;
	}
	let r = Ju(e, t);
	for (; r && du(r) && qu(r);) r = Ju(r, t);
	return r && bu(r) && qu(r) && !_u(r) ? n : r || vu(e) || n;
}
var Xu = async function(e) {
	let t = this.getOffsetParent || Yu, n = this.getDimensions, r = await n(e.floating);
	return {
		reference: Ku(e.reference, await t(e.floating), e.strategy),
		floating: {
			x: 0,
			y: 0,
			width: r.width,
			height: r.height
		}
	};
};
function Zu(e) {
	return xu(e).direction === "rtl";
}
var Qu = {
	convertOffsetParentRelativeRectToViewportRelativeRect: Iu,
	getDocumentElement: au,
	getClippingRect: Wu,
	getOffsetParent: Yu,
	getElementRects: Xu,
	getClientRects: Lu,
	getDimensions: Gu,
	getScale: ku,
	isElement: su,
	isRTL: Zu
};
function $u(e, t) {
	return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function ed(e, t, n) {
	let r = null, i, a = au(e);
	function o() {
		var e;
		clearTimeout(i), (e = r) == null || e.disconnect(), r = null;
	}
	function s(n, c) {
		n === void 0 && (n = !1), c === void 0 && (c = 1), o();
		let l = e.getBoundingClientRect(), { left: u, top: d, width: f, height: p } = l;
		if (n || t(), !f || !p) return;
		let m = _l(d), h = _l(a.clientWidth - (u + f)), g = _l(a.clientHeight - (d + p)), _ = _l(u), v = {
			rootMargin: -m + "px " + -h + "px " + -g + "px " + -_ + "px",
			threshold: hl(0, ml(1, c)) || 1
		}, y = !0;
		function b(t) {
			let n = t[0].intersectionRatio;
			if (!$u(l, e.getBoundingClientRect())) return s();
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
	let c = iu(e), l = () => s(n);
	return c.addEventListener("resize", l), s(!0), () => {
		c.removeEventListener("resize", l), o();
	};
}
function td(e, t, n, r) {
	r === void 0 && (r = {});
	let { ancestorScroll: i = !0, ancestorResize: a = !0, elementResize: o = typeof ResizeObserver == "function", layoutShift: s = typeof IntersectionObserver == "function", animationFrame: c = !1 } = r, l = Ou(e), u = i || a ? [...l ? Tu(l) : [], ...t ? Tu(t) : []] : [];
	u.forEach((e) => {
		i && e.addEventListener("scroll", n), a && e.addEventListener("resize", n);
	});
	let d = l && s ? ed(l, n, a) : null, f = -1, p = null;
	o && (p = new ResizeObserver((e) => {
		let [r] = e;
		r && r.target === l && p && t && (p.unobserve(t), cancelAnimationFrame(f), f = requestAnimationFrame(() => {
			var e;
			(e = p) == null || e.observe(t);
		})), n();
	}), l && !c && p.observe(l), t && p.observe(t));
	let m, h = c ? Nu(e) : null;
	c && g();
	function g() {
		let t = Nu(e);
		h && !$u(h, t) && n(), h = t, m = requestAnimationFrame(g);
	}
	return n(), () => {
		var e;
		u.forEach((e) => {
			i && e.removeEventListener("scroll", n), a && e.removeEventListener("resize", n);
		}), d?.(), (e = p) == null || e.disconnect(), p = null, c && cancelAnimationFrame(m);
	};
}
var nd = Ql, rd = $l, id = Kl, ad = tu, od = Yl, sd = Gl, cd = eu, ld = (e, t, n) => {
	let r = /* @__PURE__ */ new Map(), i = n ?? {}, a = {
		...Qu,
		...i.platform,
		_c: r
	};
	return Wl(e, t, {
		...i,
		platform: a
	});
};
// node_modules/@floating-ui/vue/dist/floating-ui.vue.mjs
function ud(e) {
	return typeof e == "object" && !!e && "$el" in e;
}
function dd(e) {
	if (ud(e)) {
		let t = e.$el;
		return ou(t) && ru(t) === "#comment" ? null : t;
	}
	return e;
}
function fd(e) {
	return {
		name: "arrow",
		options: e,
		fn(t) {
			let n = dd(L(e.element));
			return n == null ? {} : sd({
				element: n,
				padding: e.padding
			}).fn(t);
		}
	};
}
function pd(e) {
	return typeof window > "u" ? 1 : (e.ownerDocument.defaultView || window).devicePixelRatio || 1;
}
function md(e, t) {
	let n = pd(e);
	return Math.round(t * n) / n;
}
function hd(e, t, n) {
	n === void 0 && (n = {});
	let r = n.whileElementsMounted, i = Z(() => L(n.open) ?? !0), a = Z(() => L(n.middleware)), o = Z(() => L(n.placement) ?? "bottom"), s = Z(() => L(n.strategy) ?? "absolute"), c = Z(() => L(n.transform) ?? !0), l = Z(() => dd(e.value)), u = Z(() => dd(t.value)), d = /* @__PURE__ */ F(0), f = /* @__PURE__ */ F(0), p = /* @__PURE__ */ F(s.value), m = /* @__PURE__ */ F(o.value), h = /* @__PURE__ */ en({}), g = /* @__PURE__ */ F(!1), _ = Z(() => {
		let e = {
			position: p.value,
			left: "0",
			top: "0"
		};
		if (!u.value) return e;
		let t = md(u.value, d.value), n = md(u.value, f.value);
		return c.value ? {
			...e,
			transform: "translate(" + t + "px, " + n + "px)",
			...pd(u.value) >= 1.5 && { willChange: "transform" }
		} : {
			position: p.value,
			left: t + "px",
			top: n + "px"
		};
	}), v;
	function y() {
		if (l.value == null || u.value == null) return;
		let e = i.value;
		ld(l.value, u.value, {
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
	return B([
		a,
		o,
		s,
		i
	], y, { flush: "sync" }), B([l, u], x, { flush: "sync" }), B(i, S, { flush: "sync" }), Oe() && ke(b), {
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
var gd = ["dir"], _d = {
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
}, [vd, yd] = /*#__PURE__*/ xs("PopperContent"), bd = /* @__PURE__ */ V({
	inheritAttrs: !1,
	__name: "PopperContent",
	props: /* @__PURE__ */ ni({
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
	}, { ..._d }),
	emits: ["placed"],
	setup(e, { emit: t }) {
		let n = e, r = t, i = ol(), { forwardRef: a, currentElement: o } = mc(), s = lc(Z(() => n.dir)), c = /* @__PURE__ */ F(), l = /* @__PURE__ */ F(), { width: u, height: d } = Oc(l), f = Z(() => n.side + (n.align === "center" ? "" : `-${n.align}`)), p = Z(() => typeof n.collisionPadding == "number" ? n.collisionPadding : {
			top: 0,
			right: 0,
			bottom: 0,
			left: 0,
			...n.collisionPadding
		}), m = Z(() => Array.isArray(n.collisionBoundary) ? n.collisionBoundary : [n.collisionBoundary]), h = Z(() => ({
			padding: p.value,
			boundary: m.value.filter(ul),
			altBoundary: m.value.length > 0
		})), g = Z(() => ({
			mainAxis: n.sideFlip,
			crossAxis: n.alignFlip
		})), _ = Z(() => [
			nd({
				mainAxis: n.sideOffset + d.value,
				alignmentAxis: n.alignOffset
			}),
			n.prioritizePosition && n.avoidCollisions && id({
				...h.value,
				...g.value
			}),
			n.avoidCollisions && rd({
				mainAxis: !0,
				crossAxis: !!n.prioritizePosition,
				limiter: n.sticky === "partial" ? cd() : void 0,
				...h.value
			}),
			!n.prioritizePosition && n.avoidCollisions && id({
				...h.value,
				...g.value
			}),
			ad({
				...h.value,
				apply: ({ elements: e, rects: t, availableWidth: n, availableHeight: r }) => {
					let { width: i, height: a } = t.reference, o = e.floating.style;
					o.setProperty("--reka-popper-available-width", `${n}px`), o.setProperty("--reka-popper-available-height", `${r}px`), o.setProperty("--reka-popper-anchor-width", `${i}px`), o.setProperty("--reka-popper-anchor-height", `${a}px`);
				}
			}),
			l.value && fd({
				element: l.value,
				padding: n.arrowPadding
			}),
			dl({
				arrowWidth: u.value,
				arrowHeight: d.value,
				dir: s.value
			}),
			n.hideWhenDetached && od({
				strategy: "referenceHidden",
				...h.value
			})
		]), { floatingStyles: v, placement: y, isPositioned: b, middlewareData: x, update: S } = hd(Z(() => n.reference ?? i.anchor.value), c, {
			strategy: n.positionStrategy,
			placement: f,
			whileElementsMounted: (...e) => td(...e, {
				layoutShift: !n.disableUpdateOnLayoutShift,
				animationFrame: n.updatePositionStrategy === "always"
			}),
			middleware: _
		}), C = Z(() => fl(y.value)[0]), w = Z(() => fl(y.value)[1]);
		Zn(() => {
			b.value && r("placed");
		});
		let T = Z(() => {
			let e = x.value.arrow?.centerOffset !== 0;
			return n.hideShiftedArrow && e;
		}), ee = /* @__PURE__ */ F("");
		return Xn(() => {
			o.value && (ee.value = window.getComputedStyle(o.value).zIndex);
		}), yd({
			placedSide: C,
			onArrowChange: (e) => l.value = e,
			arrowX: Z(() => x.value.arrow?.x ?? 0),
			arrowY: Z(() => x.value.arrow?.y ?? 0),
			shouldHideArrow: T
		}), (e, t) => (W(), G("div", {
			ref_key: "floatingRef",
			ref: c,
			"data-reka-popper-content-wrapper": "",
			dir: I(s),
			style: ue({
				...I(v),
				transform: I(b) ? I(v).transform : "translate(0, -200%)",
				minWidth: "max-content",
				zIndex: ee.value,
				"--reka-popper-transform-origin": [I(x).transformOrigin?.x, I(x).transformOrigin?.y].join(" "),
				...I(x).hide?.referenceHidden && {
					visibility: "hidden",
					pointerEvents: "none"
				}
			})
		}, [n.memoDependencies ? ro([
			n.asChild,
			n.as,
			C.value,
			w.value,
			I(b),
			...Object.values(e.$attrs),
			...n.memoDependencies
		], () => (W(), K(I(Fc), Ma({
			key: 0,
			ref: I(a)
		}, e.$attrs, {
			"as-child": n.asChild,
			as: n.as,
			"data-side": C.value,
			"data-align": w.value,
			style: { animation: I(b) ? void 0 : "none" }
		}), {
			default: z(() => [H(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"style"
		])), t, 0) : (W(), K(I(Fc), Ma({
			key: 1,
			ref: I(a)
		}, e.$attrs, {
			"as-child": n.asChild,
			as: n.as,
			"data-side": C.value,
			"data-align": w.value,
			dir: I(s),
			style: { animation: I(b) ? void 0 : "none" }
		}), {
			default: z(() => [H(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"dir",
			"style"
		]))], 12, gd));
	}
}), [xd, Sd] = /*#__PURE__*/ xs("PopoverRoot"), Cd = /* @__PURE__ */ V({
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
		let n = e, r = t, { modal: i } = /* @__PURE__ */ sn(n), a = qs(n, "open", r, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		});
		return Sd({
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
			triggerElement: /* @__PURE__ */ F(),
			hasCustomAnchor: /* @__PURE__ */ F(!1)
		}), (e, t) => (W(), K(I(cl), null, {
			default: z(() => [H(e.$slots, "default", {
				open: I(a),
				close: () => a.value = !1
			})]),
			_: 3
		}));
	}
}), wd = /* @__PURE__ */ V({
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
		mc();
		let n = xd();
		return (r, i) => (W(), K(I(Fc), {
			type: e.as === "button" ? "button" : void 0,
			as: e.as,
			"as-child": t.asChild,
			onClick: i[0] ||= (e) => I(n).onOpenChange(!1)
		}, {
			default: z(() => [H(r.$slots, "default")]),
			_: 3
		}, 8, [
			"type",
			"as",
			"as-child"
		]));
	}
}), Td = /* @__PURE__ */ V({
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
		let n = e, r = t, i = hc(Ls(n, "trapFocus", "disableOutsidePointerEvents")), { forwardRef: a } = mc(), o = xd();
		return fc(), (t, n) => (W(), K(I(il), {
			"as-child": "",
			loop: "",
			trapped: e.trapFocus,
			onMountAutoFocus: n[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: n[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: z(() => [J(I(Uc), {
				"as-child": "",
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				onPointerDownOutside: n[0] ||= (e) => r("pointerDownOutside", e),
				onInteractOutside: n[1] ||= (e) => r("interactOutside", e),
				onEscapeKeyDown: n[2] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: n[3] ||= (e) => r("focusOutside", e),
				onDismiss: n[4] ||= (e) => I(o).onOpenChange(!1)
			}, {
				default: z(() => [J(I(bd), Ma(I(i), {
					id: I(o).contentId,
					ref: I(a),
					"data-state": I(o).open.value ? "open" : "closed",
					"aria-labelledby": I(o).triggerId,
					style: {
						"--reka-popover-content-transform-origin": "var(--reka-popper-transform-origin)",
						"--reka-popover-content-available-width": "var(--reka-popper-available-width)",
						"--reka-popover-content-available-height": "var(--reka-popper-available-height)",
						"--reka-popover-trigger-width": "var(--reka-popper-anchor-width)",
						"--reka-popover-trigger-height": "var(--reka-popper-anchor-height)"
					},
					role: "dialog"
				}), {
					default: z(() => [H(t.$slots, "default")]),
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
}), Ed = /* @__PURE__ */ V({
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
		let n = e, r = t, i = xd(), a = /* @__PURE__ */ F(!1);
		oc(!0);
		let o = gc(n, r), { forwardRef: s, currentElement: c } = mc();
		return Ec(c), (e, t) => (W(), K(Td, Ma(I(o), {
			ref: I(s),
			"trap-focus": I(i).open.value,
			"disable-outside-pointer-events": "",
			onCloseAutoFocus: t[0] ||= ts((e) => {
				r("closeAutoFocus", e), a.value || I(i).triggerElement.value?.focus();
			}, ["prevent"]),
			onPointerDownOutside: t[1] ||= (e) => {
				r("pointerDownOutside", e);
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0, i = t.button === 2 || n;
				a.value = i;
			},
			onFocusOutside: t[2] ||= ts(() => {}, ["prevent"])
		}), {
			default: z(() => [H(e.$slots, "default")]),
			_: 3
		}, 16, ["trap-focus"]));
	}
}), Dd = /* @__PURE__ */ V({
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
		let n = e, r = t, i = xd(), a = /* @__PURE__ */ F(!1), o = /* @__PURE__ */ F(!1), s = gc(n, r);
		return (e, t) => (W(), K(Td, Ma(I(s), {
			"trap-focus": !1,
			"disable-outside-pointer-events": !1,
			onCloseAutoFocus: t[0] ||= (e) => {
				r("closeAutoFocus", e), e.defaultPrevented || (a.value || I(i).triggerElement.value?.focus(), e.preventDefault()), a.value = !1, o.value = !1;
			},
			onInteractOutside: t[1] ||= async (e) => {
				r("interactOutside", e), e.defaultPrevented || (a.value = !0, e.detail.originalEvent.type === "pointerdown" && (o.value = !0));
				let t = e.target;
				I(i).triggerElement.value?.contains(t) && e.preventDefault(), e.detail.originalEvent.type === "focusin" && o.value && e.preventDefault();
			}
		}), {
			default: z(() => [H(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Od = /* @__PURE__ */ V({
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
		let n = e, r = t, i = xd(), a = gc(n, r), { forwardRef: o } = mc();
		return i.contentId ||= Dc(void 0, "reka-popover-content"), (t, n) => (W(), K(I(Mc), { present: e.forceMount || I(i).open.value }, {
			default: z(() => [I(i).modal.value ? (W(), K(Ed, Ma({ key: 0 }, I(a), { ref: I(o) }), {
				default: z(() => [H(t.$slots, "default")]),
				_: 3
			}, 16)) : (W(), K(Dd, Ma({ key: 1 }, I(a), { ref: I(o) }), {
				default: z(() => [H(t.$slots, "default")]),
				_: 3
			}, 16))]),
			_: 3
		}, 8, ["present"]));
	}
}), kd = /* @__PURE__ */ V({
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
		return (e, n) => (W(), K(I(al), he(Da(t)), {
			default: z(() => [H(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ad = /* @__PURE__ */ V({
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
		let t = e, n = xd(), { forwardRef: r, currentElement: i } = mc();
		return n.triggerId ||= Dc(void 0, "reka-popover-trigger"), n.contentId ||= Dc(void 0, "reka-popover-content"), Fr(() => {
			n.triggerElement.value = i.value;
		}), (i, a) => (W(), K(Kr(I(n).hasCustomAnchor.value ? I(Fc) : I(ll)), { "as-child": "" }, {
			default: z(() => [J(I(Fc), {
				id: I(n).triggerId,
				ref: I(r),
				type: e.as === "button" ? "button" : void 0,
				"aria-haspopup": "dialog",
				"aria-expanded": I(n).open.value,
				"aria-controls": I(n).open.value ? I(n).contentId : void 0,
				"data-state": I(n).open.value ? "open" : "closed",
				as: e.as,
				"as-child": t.asChild,
				onClick: I(n).onOpenToggle
			}, {
				default: z(() => [H(i.$slots, "default")]),
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
}), jd = [
	"data-active",
	"aria-label",
	"title"
], Md = { class: "tc-column-filter-label" }, Nd = { class: "tc-filter-popover-heading list-filter-popover__heading" }, Pd = /*#__PURE__*/ ys(/* @__PURE__ */ V({
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
		return (t, r) => (W(), K(I(Cd), {
			open: e.open,
			modal: !1,
			"onUpdate:open": r[0] ||= (e) => n("update:open", e)
		}, {
			default: z(() => [J(I(Ad), { "as-child": "" }, {
				default: z(() => [q("button", {
					type: "button",
					class: k(["tc-column-filter-trigger", { "is-active": e.active }]),
					"data-active": e.active ? "" : void 0,
					"aria-label": `筛选${e.label}`,
					title: e.active ? `${e.label}：${e.summary || "已筛选"}` : `筛选${e.label}`
				}, [q("span", Md, A(e.triggerLabel || e.label), 1), r[1] ||= q("svg", {
					class: "tc-column-filter-icon",
					viewBox: "0 0 16 16",
					width: "14",
					height: "14",
					fill: "none",
					"aria-hidden": "true",
					focusable: "false"
				}, [q("path", {
					d: "M2 3h12L9.5 8.3V13l-3-1.5V8.3L2 3Z",
					stroke: "currentColor",
					"stroke-width": "1.4",
					"stroke-linejoin": "round"
				})], -1)], 10, jd)]),
				_: 1
			}), J(I(kd), null, {
				default: z(() => [J(I(Od), {
					class: "tc-filter-popover list-filter-popover",
					"aria-label": `筛选${e.label}`,
					side: "bottom",
					align: "start",
					"side-offset": 6,
					"collision-padding": 10,
					"hide-when-detached": ""
				}, {
					default: z(() => [
						q("div", Nd, "筛选" + A(e.label), 1),
						H(t.$slots, "default", {}, void 0, !0),
						J(I(wd), {
							class: "tc-filter-popover-close list-filter-popover__close",
							"aria-label": `关闭${e.label}筛选`,
							title: "关闭筛选"
						}, {
							default: z(() => [...r[2] ||= [q("svg", {
								viewBox: "0 0 16 16",
								width: "16",
								height: "16",
								fill: "none",
								"aria-hidden": "true",
								focusable: "false"
							}, [q("path", {
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
}), [["__scopeId", "data-v-49f53dbd"]]), Fd = ["aria-label"], Id = [
	"aria-label",
	"title",
	"onClick"
], Ld = /*#__PURE__*/ ys(/* @__PURE__ */ V({
	__name: "ListFilterSummary",
	props: {
		items: {},
		label: { default: "已应用筛选" }
	},
	emits: ["remove"],
	setup(e, { emit: t }) {
		let n = t;
		return (t, r) => e.items.length ? (W(), G("div", {
			key: 0,
			class: "list-filter-summary",
			role: "group",
			"aria-label": e.label
		}, [(W(!0), G(U, null, Yr(e.items, (e) => (W(), G("button", {
			key: e.key,
			type: "button",
			class: "list-filter-chip",
			"aria-label": e.removeLabel,
			title: e.title || e.label,
			onClick: (t) => n("remove", e.key)
		}, [q("span", null, A(e.label), 1), r[0] ||= q("span", { "aria-hidden": "true" }, "×", -1)], 8, Id))), 128))], 8, Fd)) : X("", !0);
	}
}), [["__scopeId", "data-v-9c3f6cac"]]);
// src/features/bulk/contracts.ts
function Rd(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("批次列表响应格式无效");
	return e;
}
function zd(e) {
	let t = Rd(e);
	if (!Array.isArray(t.items)) throw Error("批次列表响应格式无效");
	let n = t.items.map((e) => {
		let t = Rd(e), n = Number.isSafeInteger(t.id) ? String(t.id) : t.id;
		if (typeof n != "string" || !/^[1-9]\d*$/.test(n)) throw Error("批次编号无效");
		return {
			...t,
			id: n
		};
	}), r = t.next_cursor ?? (t.page == null ? null : Rd(t.page).next_cursor);
	if (r != null && typeof r != "string") throw Error("批次分页响应格式无效");
	return {
		items: n,
		summary: t.summary == null ? {} : Rd(t.summary),
		nextCursor: r || null
	};
}
// src/features/bulk/useBulkList.ts
var Bd = [
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
];
function Vd(e) {
	let t = {
		tab: "bulk",
		view: "list",
		cursor: e.cursor || ""
	};
	for (let n of Bd) t[n] = e[n] || "";
	return t;
}
function Hd(e, t) {
	let n = /* @__PURE__ */ new Date(`${e}T${t ? "23:59:59" : "00:00:00"}`), [r, i, a] = e.split("-").map(Number);
	if (!/^\d{4}-\d{2}-\d{2}$/.test(e) || n.getFullYear() !== r || n.getMonth() + 1 !== i || n.getDate() !== a) throw Error("创建日期无效，请调整筛选条件");
	return n.toISOString();
}
function Ud(e) {
	let t = new URLSearchParams({ page_size: "20" });
	return e.cursor && t.set("cursor", e.cursor), e.q && t.set("q", e.q), e.operation && t.set("operation_key[]", e.operation), e.state && t.set("control_state[]", e.state), e.created_from && t.set("created_from", Hd(e.created_from, !1)), e.created_to && t.set("created_to", Hd(e.created_to, !0)), t;
}
function Wd(e, t) {
	let n = /* @__PURE__ */ en(Vd(e())), r = /* @__PURE__ */ en(null), i = /* @__PURE__ */ en([]), a = Z(() => i.value.length > 0), o = /* @__PURE__ */ F(!1), s = /* @__PURE__ */ F(!1), c = /* @__PURE__ */ F(""), l = !1, u, d;
	function f() {
		u?.abort(), u = void 0, d = void 0, s.value = !1;
	}
	function p(e) {
		return e.cursor === n.value.cursor && Bd.every((t) => e[t] === n.value[t]) ? !1 : (f(), n.value = e, r.value = null, c.value = "", !0);
	}
	function m(i = !1, a) {
		if (l || !o.value || e().view !== "list") return Promise.resolve();
		if (d) return d;
		let f = new AbortController();
		return u = f, s.value = !0, d = (async () => {
			try {
				let e = await t.api.request(`/batches?${Ud(n.value)}`, {
					method: "GET",
					signal: f.signal
				});
				if (f.signal.aborted || a && !a()) return;
				let o = r.value, s = zd(e);
				r.value = s, c.value = "", i && o && (o.items.length !== s.items.length || o.items.some((e, t) => e.id !== s.items[t]?.id)) && t.callbacks.notify?.("批次列表已更新");
			} catch (e) {
				if (f.signal.aborted || e instanceof Error && e.name === "AbortError") return;
				c.value = e instanceof Error ? e.message : "读取批次失败，请重试", e instanceof Error && "status" in e && e.status === 401 && !c.value.includes("登录") && (c.value += "，请重新登录后返回");
			}
		})().finally(() => {
			u === f && (u = void 0, d = void 0, s.value = !1);
		}), d;
	}
	function h(e) {
		return p(Vd({
			...n.value,
			...e
		})), t.callbacks.updateNavigation(e), m();
	}
	function g(e) {
		return i.value = [], h({
			...e,
			cursor: ""
		});
	}
	function _() {
		if (!o.value || s.value || !r.value?.nextCursor) return;
		let e = r.value.nextCursor;
		return i.value = [...i.value, n.value.cursor || ""], h({ cursor: e });
	}
	function v() {
		let e = i.value;
		if (o.value && !s.value && e.length) return i.value = e.slice(0, -1), h({ cursor: e[e.length - 1] });
	}
	function y() {
		if (o.value && !s.value && n.value.cursor) return i.value = [], h({ cursor: "" });
	}
	function b(e) {
		o.value = e, e || f();
	}
	return B(e, (e) => {
		e.view === "list" ? p(Vd(e)) && (i.value = [], o.value && m()) : f();
	}, { deep: !0 }), ke(() => {
		l = !0, f();
	}), {
		navigation: /* @__PURE__ */ Wt(n),
		items: Z(() => r.value?.items ?? []),
		summary: Z(() => r.value?.summary ?? {}),
		nextCursor: Z(() => r.value?.nextCursor ?? null),
		loading: /* @__PURE__ */ Wt(s),
		visible: /* @__PURE__ */ Wt(o),
		error: /* @__PURE__ */ Wt(c),
		hasPrevious: a,
		stale: Z(() => !r.value),
		refresh: m,
		setVisible: b,
		applyFilters: g,
		next: _,
		previous: v,
		first: y,
		resetFilters: () => g({
			q: "",
			operation: "",
			state: "",
			created_from: "",
			created_to: ""
		})
	};
}
// src/features/bulk/BulkList.vue?vue&type=script&setup=true&lang.ts
var Gd = ["aria-busy"], Kd = {
	key: 0,
	class: "bl-kpis"
}, qd = { class: "bl-toolbar" }, Jd = { class: "bl-toolbar-main" }, Yd = {
	class: "bl-count",
	role: "status"
}, Xd = {
	key: 1,
	class: "bl-error",
	role: "alert"
}, Zd = ["disabled"], Qd = ["disabled"], $d = ["disabled"], ef = { class: "bl-table" }, tf = { class: "bl-col-name" }, nf = { class: "bl-filter-actions" }, rf = { class: "bl-filter-options" }, af = ["checked"], of = [
	"value",
	"checked",
	"onChange"
], sf = { class: "bl-filter-options" }, cf = ["checked"], lf = [
	"value",
	"checked",
	"onChange"
], uf = { class: "bl-filter-fields" }, df = ["value"], ff = ["value"], pf = ["data-bulk-row"], mf = { class: "bl-col-name" }, hf = [
	"disabled",
	"title",
	"onClick"
], gf = ["title"], _f = { "data-bulk-progress": "" }, vf = { class: "bl-progress-copy" }, yf = [
	"value",
	"max",
	"aria-label"
], bf = {
	key: 1,
	class: "bl-secondary"
}, xf = { class: "bl-results" }, Sf = ["disabled", "onClick"], Cf = ["disabled", "onClick"], wf = { class: "bl-date" }, Tf = ["disabled", "onClick"], Ef = { key: 0 }, Df = { colspan: "7" }, Of = {
	class: "bl-empty",
	role: "status"
}, kf = /*#__PURE__*/ ys(/* @__PURE__ */ V({
	__name: "BulkList",
	props: {
		navigation: {},
		deps: {}
	},
	setup(e, { expose: t }) {
		let n = e, r = Wd(() => n.navigation, n.deps), { navigation: i, items: a, summary: o, nextCursor: s, loading: c, visible: l, error: u, hasPrevious: d, stale: f } = r, p = /* @__PURE__ */ F(null), m = /* @__PURE__ */ F(""), h = /* @__PURE__ */ F(), g = {
			plan_check: "查询套餐",
			token_refresh: "刷新 AT",
			password_setup: "补密码",
			twofa_setup: "补 2FA",
			codex_retry: "补 Codex",
			account_completion: "组合补全"
		}, _ = {
			active: "执行中",
			paused: "已暂停",
			cancel_requested: "取消中",
			stop_requested: "停止中",
			ended: "已结束"
		}, v = {
			..._,
			settling: "汇总中",
			completed: "已完成",
			preparing: "准备中"
		}, y = [
			"success",
			"partial_success",
			"failed",
			"not_executed",
			"cancelled"
		], b = [
			"attention_required",
			"request_unknown",
			"manual_reconcile",
			"unknown",
			"unconfirmed"
		];
		function x(e) {
			return e && typeof e == "object" && !Array.isArray(e) ? e : {};
		}
		function S(e) {
			return typeof e == "number" && Number.isFinite(e) && e >= 0 ? e : null;
		}
		function C(e, t = "—") {
			return e == null || e === "" ? t : String(e);
		}
		let w = Z(() => a.value.map((e) => {
			let t = x(e.summary ?? e.counts), r = {};
			for (let [e, n] of Object.entries(t)) S(n) !== null && (r[e] = n);
			let i = S(e.target_count), a = i === 0 || Object.keys(r).length > 0;
			for (let e of b) e in r && (r.failed = (r.failed || 0) + r[e], delete r[e]);
			let o = x(e.control), s = x(e.operation), c = o.paused ?? e.is_paused ? "paused" : C(o.state ?? e.control_state ?? e.state, "preparing"), l = C(s.key ?? e.operation_key ?? e.action_key), u = e.id, d = a ? y.reduce((e, t) => e + (r[t] || 0), 0) : null, f = i === null || d === null ? null : i === 0 ? 0 : Math.min(100, Math.round(100 * d / i));
			return {
				id: u,
				name: C(e.name ?? e.title, `批次 #${u}`),
				operation: g[l] || l,
				state: c,
				status: v[c] || c,
				counts: r,
				known: a,
				done: d,
				total: i,
				percent: f,
				createdAt: n.deps.callbacks.formatDateTime(e.created_at)
			};
		})), T = Z(() => S(o.value.total_batches)), ee = Z(() => f.value ? c.value ? "正在读取批次数量…" : "批次数量未知" : T.value === null ? `本页 ${a.value.length} 个批次` : `${T.value.toLocaleString()} 个批次`), te = Z(() => {
			let e = [
				{
					key: "active_batches",
					label: "执行中",
					value: S(o.value.active_batches),
					unit: "批"
				},
				{
					key: "ended_batches",
					label: "已结束",
					value: S(o.value.ended_batches),
					unit: "批"
				},
				{
					key: "failed_targets",
					label: "失败账号",
					value: S(o.value.failed_targets),
					unit: "个"
				}
			], t = S(o.value.attention_targets);
			return t != null && e[2].value != null && (e[2].value += t), e.filter((e) => e.value !== null);
		}), E = Z(() => {
			let e = i.value;
			return [
				["q", e.q ? `批次：${e.q}` : ""],
				["operation", e.operation ? `操作：${g[e.operation] || e.operation}` : ""],
				["state", e.state ? `状态：${_[e.state] || e.state}` : ""],
				["date", e.created_from || e.created_to ? `创建日期：${e.created_from || "不限"} 至 ${e.created_to || "不限"}` : ""]
			].filter(([, e]) => e).map(([e, t]) => ({
				key: e,
				label: t,
				removeLabel: `移除${t}`
			}));
		});
		B(() => i.value.q, (e) => {
			m.value = e || "";
		}, { immediate: !0 }), B(() => n.navigation.view, () => {
			p.value = null;
		});
		function ne(e) {
			e === "date" ? r.applyFilters({
				created_from: "",
				created_to: ""
			}) : r.applyFilters({ [e]: "" });
		}
		function D(e, t) {
			r.applyFilters({ [e]: t });
		}
		function re() {
			r.applyFilters({ q: m.value.trim() }), p.value = null;
		}
		function ie(e, t) {
			l.value && !f.value && n.deps.callbacks.navigate("detail", {
				batch_id: e,
				...t ? { result_state: t } : {}
			});
		}
		function ae(e) {
			l.value && !f.value && n.deps.callbacks.navigate("detail", { batch_id: e }, !0);
		}
		function oe() {
			let e = window.getSelection();
			return f.value || !(e?.toString() && h.value?.contains(e.anchorNode));
		}
		async function O(e = !1) {
			oe() && await r.refresh(e, oe);
		}
		function se(e) {
			e || (p.value = null), r.setVisible(e);
		}
		return t({
			refresh: O,
			setVisible: se
		}), (t, n) => (W(), G("section", {
			class: "bl-root",
			"aria-label": "批次列表",
			"aria-busy": I(c)
		}, [
			te.value.length ? (W(), G("div", Kd, [(W(!0), G(U, null, Yr(te.value, (e) => (W(), G("div", {
				key: e.key,
				class: k(["bl-kpi", { "is-warning": e.key === "failed_targets" && !!e.value }])
			}, [q("span", null, A(e.label), 1), q("strong", null, [Y(A(e.value), 1), q("small", null, A(e.unit), 1)])], 2))), 128))])) : X("", !0),
			q("div", qd, [q("div", Jd, [q("span", Yd, A(ee.value), 1), J(Ld, {
				items: E.value,
				onRemove: ne
			}, null, 8, ["items"])]), E.value.length ? (W(), G("button", {
				key: 0,
				type: "button",
				class: "bl-link",
				onClick: n[0] ||= (...e) => I(r).resetFilters && I(r).resetFilters(...e)
			}, "清除筛选")) : X("", !0)]),
			I(u) ? (W(), G("div", Xd, [
				q("span", null, A(I(u)), 1),
				q("button", {
					type: "button",
					class: "bl-link",
					disabled: I(c),
					onClick: n[1] ||= (e) => I(r).refresh()
				}, "重试", 8, Zd),
				I(f) && I(i).cursor ? (W(), G("button", {
					key: 0,
					class: "bl-link",
					type: "button",
					disabled: I(c),
					onClick: n[2] ||= (...e) => I(r).first && I(r).first(...e)
				}, " 返回首页", 8, Qd)) : X("", !0),
				I(f) && I(d) ? (W(), G("button", {
					key: 1,
					class: "bl-link",
					type: "button",
					disabled: I(c),
					onClick: n[3] ||= (...e) => I(r).previous && I(r).previous(...e)
				}, " 上一页 ", 8, $d)) : X("", !0)
			])) : X("", !0),
			q("div", {
				ref_key: "tableHost",
				ref: h,
				class: "bl-table-wrap",
				tabindex: "0",
				role: "region",
				"aria-label": "批次列表内容"
			}, [q("table", ef, [q("thead", null, [q("tr", null, [
				q("th", tf, [J(Pd, {
					label: "批次名称或编号",
					"trigger-label": "批次",
					active: !!I(i).q,
					summary: I(i).q,
					open: p.value === "q",
					"onUpdate:open": n[6] ||= (e) => p.value = e ? "q" : null
				}, {
					default: z(() => [q("form", {
						class: "bl-filter-fields",
						onSubmit: ts(re, ["prevent"])
					}, [q("label", null, [n[16] ||= Y("名称或批次号", -1), Wn(q("input", {
						"onUpdate:modelValue": n[4] ||= (e) => m.value = e,
						type: "search",
						placeholder: "搜索批次名称或编号",
						autocomplete: "off"
					}, null, 512), [[Qo, m.value]])]), q("div", nf, [q("button", {
						type: "button",
						onClick: n[5] ||= (e) => ne("q")
					}, "清除此列"), n[17] ||= q("button", { type: "submit" }, "查询", -1)])], 32)]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				q("th", null, [J(Pd, {
					label: "操作类型",
					active: !!I(i).operation,
					summary: g[I(i).operation || ""] || I(i).operation,
					open: p.value === "operation",
					"onUpdate:open": n[8] ||= (e) => p.value = e ? "operation" : null
				}, {
					default: z(() => [q("fieldset", rf, [
						n[19] ||= q("legend", { class: "bl-sr-only" }, "操作类型", -1),
						q("label", null, [q("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: "",
							checked: !I(i).operation,
							onChange: n[7] ||= (e) => D("operation", "")
						}, null, 40, af), n[18] ||= Y("全部操作", -1)]),
						(W(), G(U, null, Yr(g, (e, t) => q("label", { key: t }, [q("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: t,
							checked: I(i).operation === t,
							onChange: (e) => D("operation", t)
						}, null, 40, of), Y(A(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				q("th", null, [J(Pd, {
					label: "状态",
					active: !!I(i).state,
					summary: _[I(i).state || ""] || I(i).state,
					open: p.value === "state",
					"onUpdate:open": n[10] ||= (e) => p.value = e ? "state" : null
				}, {
					default: z(() => [q("fieldset", sf, [
						n[21] ||= q("legend", { class: "bl-sr-only" }, "运行状态", -1),
						q("label", null, [q("input", {
							type: "radio",
							name: "bulk-list-state",
							value: "",
							checked: !I(i).state,
							onChange: n[9] ||= (e) => D("state", "")
						}, null, 40, cf), n[20] ||= Y("全部状态", -1)]),
						(W(), G(U, null, Yr(_, (e, t) => q("label", { key: t }, [q("input", {
							type: "radio",
							name: "bulk-list-state",
							value: t,
							checked: I(i).state === t,
							onChange: (e) => D("state", t)
						}, null, 40, lf), Y(A(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				n[24] ||= q("th", null, "完成进度", -1),
				n[25] ||= q("th", null, "当前结果", -1),
				q("th", null, [J(Pd, {
					label: "创建时间",
					active: !!(I(i).created_from || I(i).created_to),
					summary: `${I(i).created_from || "不限"} 至 ${I(i).created_to || "不限"}`,
					open: p.value === "date",
					"onUpdate:open": n[14] ||= (e) => p.value = e ? "date" : null
				}, {
					default: z(() => [q("div", uf, [
						q("label", null, [n[22] ||= Y("开始日期", -1), q("input", {
							type: "date",
							value: I(i).created_from,
							onChange: n[11] ||= (e) => D("created_from", e.target.value)
						}, null, 40, df)]),
						q("label", null, [n[23] ||= Y("截止日期", -1), q("input", {
							type: "date",
							value: I(i).created_to,
							onChange: n[12] ||= (e) => D("created_to", e.target.value)
						}, null, 40, ff)]),
						q("button", {
							type: "button",
							onClick: n[13] ||= (e) => ne("date")
						}, "清除此列")
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				n[26] ||= q("th", null, [q("span", { class: "bl-sr-only" }, "操作")], -1)
			])]), q("tbody", null, [(W(!0), G(U, null, Yr(w.value, (e) => (W(), G("tr", {
				key: e.id,
				"data-bulk-row": e.id
			}, [
				q("td", mf, [q("button", {
					type: "button",
					class: "bl-name",
					"data-bulk-open": "",
					disabled: I(f),
					title: e.name,
					onClick: (t) => ie(e.id)
				}, A(e.name), 9, hf), q("span", {
					class: "bl-secondary",
					title: `批次 #${e.id}`
				}, "#" + A(e.id), 9, gf)]),
				q("td", null, A(e.operation), 1),
				q("td", null, [q("span", { class: k(["bl-status", `is-${e.state}`]) }, A(e.status), 3)]),
				q("td", _f, [e.total !== null && e.done !== null ? (W(), G(U, { key: 0 }, [q("span", vf, [Y(A(e.done) + " / " + A(e.total) + " ", 1), q("span", null, A(e.percent) + "%", 1)]), q("progress", {
					value: e.done,
					max: Math.max(1, e.total),
					"aria-label": `已结束 ${e.done} 个，共 ${e.total} 个`
				}, null, 8, yf)], 64)) : (W(), G("span", bf, A(e.total === null ? "名单准备中" : "结果待汇总"), 1))]),
				q("td", null, [q("div", xf, [q("button", {
					type: "button",
					class: "bl-result is-success",
					"data-bulk-result": "success",
					disabled: I(f) || !e.counts.success,
					onClick: (t) => ie(e.id, "success")
				}, " 成功 " + A(e.known ? e.counts.success || 0 : "—"), 9, Sf), q("button", {
					type: "button",
					class: "bl-result is-failed",
					"data-bulk-result": "failed",
					disabled: I(f) || !e.counts.failed,
					onClick: (t) => ie(e.id, "failed")
				}, " 失败 " + A(e.known ? e.counts.failed || 0 : "—"), 9, Cf)])]),
				q("td", wf, A(e.createdAt), 1),
				q("td", null, [q("button", {
					type: "button",
					class: "bl-button",
					"data-bulk-report": "",
					disabled: I(f),
					onClick: (t) => ae(e.id)
				}, " 查看报告 ", 8, Tf)])
			], 8, pf))), 128)), w.value.length ? X("", !0) : (W(), G("tr", Ef, [q("td", Df, [q("div", Of, [q("strong", null, A(I(c) ? "正在加载批次…" : I(u) ? "暂时无法读取批次" : E.value.length ? "没有匹配的批次" : "还没有批次"), 1), !I(c) && !I(u) ? (W(), G(U, { key: 0 }, [n[27] ||= q("p", null, "选择操作和账号范围，即可集中执行与追踪结果。", -1), q("button", {
				type: "button",
				class: "bl-button",
				"data-bulk-create": "",
				onClick: n[15] ||= (t) => e.deps.callbacks.navigate("create")
			}, " 新建批次 ")], 64)) : X("", !0)])])]))])])], 512),
			I(f) ? X("", !0) : (W(), K(bs, {
				key: 2,
				"has-previous": I(d),
				"next-cursor": I(s),
				"item-count": I(a).length,
				"has-cursor": !!I(i).cursor,
				busy: I(c),
				label: "批次分页",
				onPrevious: I(r).previous,
				onNext: I(r).next,
				onFirst: I(r).first
			}, null, 8, [
				"has-previous",
				"next-cursor",
				"item-count",
				"has-cursor",
				"busy",
				"onPrevious",
				"onNext",
				"onFirst"
			]))
		], 8, Gd));
	}
}), [["__scopeId", "data-v-cc3b7b8e"]]), Af = {
	plan_check: "查套餐",
	token_refresh: "刷新 AT",
	password_setup: "补密码",
	twofa_setup: "补 2FA",
	codex_retry: "补 Codex",
	account_completion: "组合补全"
}, jf = (e) => typeof e == "object" && e && !Array.isArray(e) ? e : {}, Mf = (e) => Array.isArray(e) ? e.map(jf) : [], Nf = (e) => Af[String(e)] || String(e || "—");
function Q(e) {
	if (typeof e != "number" && (typeof e != "string" || !e.trim())) return null;
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? t : null;
}
var $ = (e) => Q(e) === null ? "—" : Math.floor(Number(e)).toLocaleString("zh-CN");
function Pf(e) {
	let t = Q(e);
	if (t === null) return "—";
	if (t < 60) return `${t === 0 ? "0" : t < 1 ? t.toFixed(2) : t.toFixed(1).replace(/\.0$/, "")} 秒`;
	let n = Math.round(t), r = Math.floor(n / 3600), i = Math.floor(n % 3600 / 60), a = n % 60;
	return [
		r ? `${r} 小时` : "",
		i ? `${i} 分` : "",
		a ? `${a} 秒` : ""
	].filter(Boolean).join(" ") || "0 秒";
}
function Ff(e) {
	let t = jf(e.view);
	if (t.kind !== "round") return "当前结果 · 每个账号取最近一轮";
	let n = Q(t.round_no);
	return n === null || !Number.isSafeInteger(n) || n < 1 ? "所选轮次 · 固定名单" : n === 1 ? "首轮名单" : `重跑 ${n - 1} · 固定名单`;
}
var If = {
	free: "Free",
	plus: "Plus",
	pro: "Pro",
	team: "Team",
	business: "Business",
	enterprise: "Enterprise",
	go: "Go",
	unknown: "尚未确认"
}, Lf = {
	free_trial: "免费试用",
	half_price: "半价优惠",
	discount: "折扣优惠",
	other_discount: "其他折扣",
	other_promo: "其他优惠"
};
function Rf(e, t, n) {
	let r = typeof t == "string" ? t : "";
	return Object.hasOwn(e, r) ? e[r] : r || n;
}
var zf = (e) => Rf(If, e, "尚未确认"), Bf = (e) => Rf(Lf, e, "其他优惠");
function Vf(e, t) {
	return `${Math.max(0, Math.min(100, t > 0 ? (Q(e) || 0) / t * 100 : 0))}%`;
}
var Hf = {
	"account.confirmed_no_offer": "本次确认无优惠",
	"account.plan.free": "套餐 · Free",
	"account.plan.plus": "套餐 · Plus",
	"account.plan.pro": "套餐 · Pro",
	"account.plan.team": "套餐 · Team",
	"account.plan.go": "套餐 · Go",
	confirmed_no_offer_accounts: "本次确认无优惠",
	no_offer: "无优惠",
	free_trial: "免费试用",
	half_price: "半价优惠",
	other_discount: "其他折扣",
	success: "成功",
	failed: "失败",
	partial_success: "部分成功",
	confirmed: "已确认",
	newly_set: "新设置",
	already_set: "验证已有密码",
	newly_enabled: "新启用",
	already_satisfied: "原本已满足",
	usable_credential: "可用凭证",
	credential_pending_confirmation: "凭证缺失",
	confirmed_accounts: "已确认账号",
	country_success: "查询成功",
	country_failed: "查询失败",
	"country_query.success": "国家项查询成功",
	"country_query.failed": "国家项查询失败",
	plan: "套餐",
	plans: "套餐分布",
	promotion: "优惠",
	promotions: "优惠分布",
	countries: "国家项",
	password: "密码",
	twofa: "2FA",
	codex: "Codex",
	access_token: "AT",
	plan_check: "套餐查询",
	free: "Free",
	plus: "Plus",
	team: "Team",
	pro: "Pro",
	unknown: "记录缺失",
	none: "无优惠",
	not_executed: "未执行",
	attention_required: "失败",
	pending: "待执行",
	"account.password_setup.confirmed": "密码已确认",
	"account.twofa_setup.confirmed": "2FA 已确认",
	"account.codex.credential_confirmed": "Codex 凭证已确认",
	"account.token_refresh.confirmed": "AT 刷新成功",
	"account.token_refresh.failed": "AT 刷新失败"
};
for (let [e, t] of Object.entries({
	none: "无优惠",
	...Lf
})) Hf[`account.plus_offer.${e}`] = `优惠 · ${t}`;
for (let [e, t] of Object.entries({
	unchanged: "优惠未变化",
	new_offer: "新增优惠",
	offer_removed: "优惠消失",
	changed: "优惠变化",
	not_comparable: "历史条件不可比较"
})) Hf[`account.comparison.${e}`] = t;
for (let [e, t] of Object.entries({
	password: "密码",
	twofa: "2FA",
	codex: "Codex",
	access_token: "AT",
	plan_check: "套餐"
})) Hf[`step.${e}.confirmed`] = `${t} · 已完成`, Hf[`step.${e}.pending`] = `${t} · 待完成`;
function Uf(e) {
	let t = { ...jf(e) };
	Object.hasOwn(t, "account.token_refresh.unconfirmed") && (t["account.token_refresh.failed"] = (Q(t["account.token_refresh.failed"]) || 0) + (Q(t["account.token_refresh.unconfirmed"]) || 0), delete t["account.token_refresh.unconfirmed"]);
	let n = /* @__PURE__ */ new Map();
	function r(e, t = "", i = 0) {
		if (!(i > 3)) for (let [a, o] of Object.entries(e)) {
			if ([
				"schema",
				"schema_version",
				"version",
				"updated_at"
			].includes(a)) continue;
			let e = Rf(Hf, a, a), s = t ? `${t} · ${e}` : e;
			if (typeof o == "number") {
				let e = a.startsWith("country_query.") || a.startsWith("country_") ? "国家查询项" : a.startsWith("account.plan.") ? "套餐分布" : a.startsWith("account.plus_offer.") || a.startsWith("account.comparison.") || a === "account.confirmed_no_offer" ? "优惠结果" : a.startsWith("step.") ? "补全项目" : "执行结果";
				n.has(e) || n.set(e, {
					title: e,
					items: []
				}), n.get(e).items.push({
					title: s,
					value: o
				});
			} else o && typeof o == "object" && r(jf(o), s, i + 1);
		}
	}
	return r(t), [...n.values()];
}
// src/features/bulk/BulkBusinessStats.vue?vue&type=script&setup=true&lang.ts
var Wf = {
	key: 0,
	class: "bulk-business-groups"
}, Gf = { class: "bulk-business-metrics" }, Kf = {
	key: 1,
	class: "bulk-report-empty"
}, qf = /* @__PURE__ */ V({
	__name: "BulkBusinessStats",
	props: { groups: {} },
	setup(e) {
		return (t, n) => e.groups.length ? (W(), G("div", Wf, [(W(!0), G(U, null, Yr(e.groups, (e) => (W(), G("section", {
			key: e.title,
			class: "bulk-business-group"
		}, [q("h4", null, A(e.title) + " · " + A(e.title === "国家查询项" ? "项" : "账号数"), 1), q("dl", Gf, [(W(!0), G(U, null, Yr(e.items, (e) => (W(), G("div", { key: e.title }, [q("dt", null, A(e.title), 1), q("dd", null, A(I($)(e.value)), 1)]))), 128))])]))), 128))])) : (W(), G("p", Kf, "暂无已确认的功能统计。"));
	}
}), Jf = ["aria-label"], Yf = { role: "status" }, Xf = {
	key: 1,
	class: "bulk-plan-report",
	"aria-labelledby": "bulkPlanReportTitle"
}, Zf = { class: "bulk-report-header" }, Qf = { class: "bulk-report-heading-line" }, $f = { id: "bulkPlanReportTitle" }, ep = { class: "bulk-report-updated" }, tp = {
	key: 0,
	class: "bulk-report-sync",
	role: "status"
}, np = { class: "bulk-report-outcomes" }, rp = { class: "bulk-report-outcome-note" }, ip = { class: "bulk-report-execution" }, ap = { "aria-label": "账号执行耗时" }, op = { class: "bulk-report-section-head" }, sp = { class: "bulk-report-durations" }, cp = { class: "is-average" }, lp = { class: "bulk-report-note" }, up = {
	key: 0,
	"aria-label": "AT 检查与自动刷新"
}, dp = { class: "bulk-report-at-causes" }, fp = { class: "bulk-report-at-results" }, pp = { class: "bulk-report-note" }, mp = {
	key: 1,
	"aria-label": "功能统计"
}, hp = {
	key: 1,
	class: "bulk-report-distributions"
}, gp = {
	class: "bulk-report-offers",
	"aria-label": "优惠结果"
}, _p = { class: "bulk-report-offer-totals" }, vp = { class: "bulk-report-offer-list" }, yp = { class: "bulk-report-offer-line" }, bp = {
	class: "bulk-report-rail",
	"aria-hidden": "true"
}, xp = { class: "bulk-report-kind-list" }, Sp = {
	key: 0,
	class: "bulk-report-empty"
}, Cp = {
	class: "bulk-report-plans",
	"aria-label": "当前订阅套餐"
}, wp = { class: "bulk-report-plan-list" }, Tp = {
	key: 0,
	class: "bulk-report-empty"
}, Ep = {
	key: 2,
	class: "bulk-business-details"
}, Dp = /* @__PURE__ */ V({
	__name: "BulkReport",
	props: {
		report: {},
		formatDateTime: { type: Function }
	},
	setup(e) {
		let t = e, n = Z(() => Object.hasOwn(Af, String(t.report.operation_key))), r = Z(() => jf(t.report.totals)), i = Z(() => jf(t.report.duration)), a = Z(() => jf(t.report.at_refresh)), o = Z(() => jf(t.report.offers)), s = Z(() => t.report.phase === "completed"), c = Z(() => t.report.operation_key === "plan_check"), l = Z(() => Mf(t.report.plans).sort((e, t) => e.plan === "unknown" ? 1 : t.plan === "unknown" ? -1 : (Q(t.accounts) || 0) - (Q(e.accounts) || 0))), u = Z(() => Mf(o.value.by_plan).sort((e, t) => (Q(t.accounts) || 0) - (Q(e.accounts) || 0) || zf(e.plan).localeCompare(zf(t.plan)))), d = Z(() => Math.max(0, ...l.value.map((e) => Q(e.accounts) || 0))), f = Z(() => Math.max(0, ...u.value.map((e) => Q(e.accounts) || 0))), p = Z(() => Uf(t.report.business_summary)), m = [
			[
				"成功",
				"success",
				"is-success"
			],
			[
				"失败",
				"failed",
				"is-danger"
			],
			[
				"部分成功",
				"partial_success",
				"is-warning"
			],
			[
				"待完成",
				"active",
				""
			]
		], h = [
			["AT 过期", "expired_accounts"],
			["远端拒绝 AT", "invalid_accounts"],
			["缺少 AT", "missing_token_accounts"]
		], g = [
			[
				"尝试刷新",
				"attempted_accounts",
				""
			],
			[
				"刷新成功",
				"succeeded_accounts",
				"is-success"
			],
			[
				"刷新失败",
				"failed_accounts",
				"is-danger"
			],
			[
				"刷新中",
				"pending_accounts",
				""
			]
		], _ = [
			[
				"有优惠账号",
				"with_offer_accounts",
				"多个国家只算一个账号"
			],
			[
				"确认无优惠",
				"confirmed_no_offer_accounts",
				"完整查询成功且无优惠"
			],
			[
				"优惠待确认",
				"unknown_accounts",
				"含待完成、未执行或缺少结果"
			]
		];
		return (t, v) => n.value && e.report.population_ready === !1 ? (W(), G("section", {
			key: 0,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": I(Nf)(e.report.operation_key) + "报告"
		}, [q("h3", null, A(I(Nf)(e.report.operation_key)) + "报告", 1), q("p", Yf, A(I(Ff)(e.report)) + " · " + A(e.report.phase === "preparing" ? "账号名单准备中，固定后生成报告。" : "该轮名单未固定，无法生成账号统计。"), 1)], 8, Jf)) : n.value ? (W(), G("section", Xf, [
			q("header", Zf, [q("div", null, [q("div", Qf, [q("h3", $f, A(I(Nf)(e.report.operation_key)) + A(s.value ? "完成报告" : "实时报告"), 1), q("span", { class: k(["bulk-report-phase", { "is-completed": s.value }]) }, A(s.value ? "已完成" : e.report.phase === "preparing" ? "名单准备中" : "统计更新中"), 3)]), q("p", null, A(I(Ff)(e.report)) + " · " + A(I($)(r.value.accounts)) + " 个账号", 1)]), q("span", ep, "更新于 " + A(e.formatDateTime(e.report.generated_at)), 1)]),
			I(jf)(e.report.projection).state && I(jf)(e.report.projection).state !== "current" ? (W(), G("p", tp, A(I(jf)(e.report.projection).state === "failed" ? "结果汇总暂时失败，以下统计尚未收齐，请稍后刷新。" : "执行结果正在汇总，以下统计尚未收齐。"), 1)) : X("", !0),
			q("dl", np, [(W(), G(U, null, Yr(m, ([e, t, n]) => q("div", {
				key: t,
				class: k(["bulk-report-metric", n])
			}, [q("dt", null, A(e), 1), q("dd", null, [Y(A(I($)(r.value[t])), 1), v[0] ||= q("span", null, "个", -1)])], 2)), 64))]),
			q("div", rp, [
				q("span", null, "已结束 " + A(I($)(r.value.completed)) + " / " + A(I($)(r.value.accounts)) + " 个", 1),
				q("span", null, "未执行 " + A(I($)(r.value.not_executed)) + " 个", 1),
				q("span", null, "已取消 " + A(I($)(r.value.cancelled)) + " 个", 1)
			]),
			q("div", ip, [q("section", ap, [
				q("div", op, [v[1] ||= q("h4", null, "账号执行耗时", -1), q("span", null, "已结束样本 " + A(I($)(i.value.sample_count)) + " 个", 1)]),
				q("dl", sp, [
					q("div", cp, [v[2] ||= q("dt", null, "平均耗时", -1), q("dd", null, A(I(Pf)(i.value.avg_seconds)), 1)]),
					q("div", null, [v[3] ||= q("dt", null, "最快", -1), q("dd", null, A(I(Pf)(i.value.min_seconds)), 1)]),
					q("div", null, [v[4] ||= q("dt", null, "最慢", -1), q("dd", null, A(I(Pf)(i.value.max_seconds)), 1)])
				]),
				q("p", lp, [Y(" 从账号开始执行到结束，" + A(c.value ? "含自动刷新及链内等待" : "含链内等待") + "，不含开始前排队。", 1), (I(Q)(i.value.missing_count) || 0) > 0 ? (W(), G(U, { key: 0 }, [Y(A(I($)(i.value.missing_count)) + " 个已结束账号缺少有效耗时，未计入均值。", 1)], 64)) : I(Q)(i.value.sample_count) === 0 ? (W(), G(U, { key: 1 }, [Y(" 暂无有效耗时样本。")], 64)) : X("", !0)])
			]), c.value ? (W(), G("section", up, [
				v[8] ||= q("div", { class: "bulk-report-section-head" }, [q("h4", null, "AT 检查与自动刷新"), q("span", null, "按账号去重")], -1),
				q("dl", dp, [(W(), G(U, null, Yr(h, ([e, t]) => q("div", {
					key: t,
					class: "bulk-report-minor"
				}, [q("dt", null, A(e), 1), q("dd", null, [Y(A(I($)(a.value[t])), 1), v[5] ||= q("span", null, "个", -1)])])), 64))]),
				q("dl", fp, [(W(), G(U, null, Yr(g, ([e, t, n]) => q("div", {
					key: t,
					class: k(["bulk-report-minor", n])
				}, [q("dt", null, A(e), 1), q("dd", null, [Y(A(I($)(a.value[t])), 1), v[6] ||= q("span", null, "个", -1)])], 2)), 64))]),
				q("p", pp, [
					I(Q)(a.value.not_needed_accounts) === null ? X("", !0) : (W(), G(U, { key: 0 }, [Y("未触发刷新 " + A(I($)(a.value.not_needed_accounts)) + " 个 · ", 1)], 64)),
					Y("刷新状态待确认 " + A(I($)(a.value.unknown_accounts)) + " 个", 1),
					I(Q)(a.value.not_executed_accounts) === null ? X("", !0) : (W(), G(U, { key: 1 }, [Y(" · 未开始执行 " + A(I($)(a.value.not_executed_accounts)) + " 个", 1)], 64)),
					v[7] ||= Y("。待确认含执行中尚无结果及历史证据缺失；触发原因可能重叠，远端拒绝不等于本地过期。 ", -1)
				])
			])) : (W(), G("section", mp, [v[9] ||= q("div", { class: "bulk-report-section-head" }, [q("h4", null, "功能统计"), q("span", null, "当前查看范围")], -1), J(qf, { groups: p.value }, null, 8, ["groups"])]))]),
			c.value ? (W(), G("div", hp, [q("section", gp, [
				v[13] ||= q("div", { class: "bulk-report-section-head" }, [q("div", null, [q("h4", null, "优惠结果"), q("p", null, "统计本次查到的可用优惠，按账号去重")])], -1),
				q("dl", _p, [(W(), G(U, null, Yr(_, ([e, t, n]) => q("div", {
					key: t,
					class: k(["bulk-report-metric", { "is-accent": t === "with_offer_accounts" }])
				}, [
					q("dt", null, A(e), 1),
					q("dd", null, [Y(A(I($)(o.value[t])), 1), v[10] ||= q("span", null, "个", -1)]),
					q("small", null, A(n), 1)
				], 2)), 64))]),
				q("div", vp, [(W(!0), G(U, null, Yr(u.value, (e) => (W(), G("div", {
					key: String(e.plan),
					class: "bulk-report-offer-row"
				}, [
					q("div", yp, [q("strong", null, A(I(zf)(e.plan)), 1), q("span", null, [q("b", null, A(I($)(e.accounts)), 1), v[11] ||= Y(" 个账号", -1)])]),
					q("span", bp, [q("span", { style: ue({ width: I(Vf)(e.accounts, f.value) }) }, null, 4)]),
					q("dl", xp, [(W(!0), G(U, null, Yr(I(Mf)(e.kinds), (e) => (W(), G("div", { key: String(e.kind) }, [q("dt", null, A(I(Bf)(e.kind)), 1), q("dd", null, [Y(A(I($)(e.accounts)), 1), v[12] ||= q("span", null, "个", -1)])]))), 128))])
				]))), 128)), u.value.length ? X("", !0) : (W(), G("p", Sp, A(I(Q)(o.value.with_offer_accounts) === 0 ? "本次尚未查到可用优惠。" : "暂无优惠套餐明细。"), 1))]),
				v[14] ||= q("p", { class: "bulk-report-note" }, "同一账号可符合多个套餐或优惠，分项数量可能重叠。", -1)
			]), q("section", Cp, [
				v[16] ||= q("div", { class: "bulk-report-section-head" }, [q("div", null, [q("h4", null, "当前订阅套餐"), q("p", null, "本次查询确认的套餐状态")])], -1),
				q("dl", wp, [(W(!0), G(U, null, Yr(l.value, (e) => (W(), G("div", {
					key: String(e.plan),
					class: k({ "is-unknown": e.plan === "unknown" })
				}, [q("dt", null, A(I(zf)(e.plan)), 1), q("dd", null, [q("span", null, [Y(A(I($)(e.accounts)), 1), v[15] ||= q("small", null, "个", -1)]), q("span", {
					class: k(["bulk-report-rail", { "is-muted": e.plan === "unknown" }]),
					"aria-hidden": "true"
				}, [q("span", { style: ue({ width: I(Vf)(e.accounts, d.value) }) }, null, 4)], 2)])], 2))), 128)), l.value.length ? X("", !0) : (W(), G("div", Tp, "暂无套餐结果。"))]),
				v[17] ||= q("p", { class: "bulk-report-note" }, "“尚未确认”包含待完成、失败或缺少套餐记录的账号。", -1)
			])])) : X("", !0),
			c.value && p.value.length ? (W(), G("details", Ep, [v[18] ||= q("summary", null, [Y("更多查询统计"), q("span", null, "展开查看")], -1), J(qf, { groups: p.value }, null, 8, ["groups"])])) : X("", !0)
		])) : X("", !0);
	}
}), Op = ["aria-label"], kp = {
	key: 0,
	role: "status"
}, Ap = {
	key: 2,
	class: "bulk-report-load-error"
}, jp = {
	class: "bulk-error",
	role: "alert"
}, Mp = /* @__PURE__ */ V({
	__name: "BulkReportView",
	props: {
		operationKey: {},
		report: {},
		error: {},
		formatDateTime: { type: Function },
		onRetry: { type: Function }
	},
	setup(e) {
		let t = e, n = Z(() => Object.hasOwn(Af, t.operationKey)), r = Z(() => `${Af[t.operationKey]}报告`);
		return (t, i) => n.value ? (W(), G(U, { key: 0 }, [e.report && e.report.operation_key === e.operationKey ? (W(), K(Dp, {
			key: 0,
			report: e.report,
			"format-date-time": e.formatDateTime
		}, null, 8, ["report", "format-date-time"])) : (W(), G("section", {
			key: 1,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": r.value
		}, [q("h3", null, A(r.value), 1), e.error ? X("", !0) : (W(), G("p", kp, "正在汇总本次执行结果…"))], 8, Op)), e.error ? (W(), G("div", Ap, [q("p", jp, A(e.error), 1), q("button", {
			type: "button",
			class: "jobs-tb-btn",
			"data-bulk-action": "report-refresh",
			onClick: i[0] ||= ts((t) => e.onRetry(), ["stop"])
		}, " 重新读取报告 ")])) : X("", !0)], 64)) : X("", !0);
	}
});
// src/features/bulk/mountBulkReport.ts
function Np(e, t) {
	e.replaceChildren();
	function n(t) {
		as(no(Mp, { ...t }), e);
	}
	return n(t), {
		setView: n,
		destroy() {
			as(null, e);
		}
	};
}
// src/bulk.ts
function Pp(e, t) {
	let n = /* @__PURE__ */ en(t.view), r = /* @__PURE__ */ en(), i = {
		callbacks: t.callbacks,
		api: { async request(e, { signal: t }) {
			let n = await us(`/api/bulk${e}`, { signal: t });
			return n?.data ?? n;
		} }
	}, a = os(/* @__PURE__ */ V({ setup: () => () => no(kf, {
		ref: r,
		navigation: n.value,
		deps: i
	}) }));
	return a.mount(e), {
		setView(e) {
			n.value = e;
		},
		setVisible(e) {
			r.value?.setVisible(e), e && jn(() => r.value?.refresh());
		},
		refresh(e = !1) {
			return r.value?.refresh(e);
		},
		destroy() {
			a.unmount();
		}
	};
}
export { Pp as mountBulkList, Np as mountBulkReport };
