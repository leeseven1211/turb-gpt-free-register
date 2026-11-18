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
function Ce(e, t) {
	return e.findIndex((e) => Se(e, t));
}
var we = (e) => !!(e && e.__v_isRef === !0), Te = (e) => g(e) ? e : e == null ? "" : d(e) || v(e) && (e.toString === b || !h(e.toString)) ? we(e) ? Te(e.value) : JSON.stringify(e, Ee, 2) : String(e), Ee = (e, t) => we(t) ? Ee(e, t.value) : f(t) ? { [`Map(${t.size})`]: [...t.entries()].reduce((e, [t, n], r) => (e[De(t, r) + " =>"] = n, e), {}) } : p(t) ? { [`Set(${t.size})`]: [...t.values()].map((e) => De(e)) } : _(t) ? De(t) : v(t) && !d(t) && !C(t) ? String(t) : t, De = (e, t = "") => _(e) ? `Symbol(${e.description ?? t})` : e, A, Oe = class {
	constructor(e = !1) {
		this.detached = e, this._active = !0, this._on = 0, this.effects = [], this.cleanups = [], this._isPaused = !1, this._warnOnRun = !0, this.__v_skip = !0, !e && A && (A.active ? (this.parent = A, this.index = (A.scopes || (A.scopes = [])).push(this) - 1) : (this._active = !1, this._warnOnRun = !1));
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
			let t = A;
			try {
				return A = this, e();
			} finally {
				A = t;
			}
		}
	}
	on() {
		++this._on === 1 && (this.prevScope = A, A = this);
	}
	off() {
		if (this._on > 0 && --this._on === 0) {
			if (A === this) A = this.prevScope;
			else {
				let e = A;
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
function ke(e) {
	return new Oe(e);
}
function Ae() {
	return A;
}
function je(e, t = !1) {
	A && (A.active ? A.cleanups.push(e) : e());
}
var j, Me = /* @__PURE__ */ new WeakSet(), Ne = class {
	constructor(e) {
		this.fn = e, this.deps = void 0, this.depsTail = void 0, this.flags = 5, this.next = void 0, this.cleanup = void 0, this.scheduler = void 0, A && (A.active ? A.effects.push(this) : this.flags &= -2);
	}
	pause() {
		this.flags |= 64;
	}
	resume() {
		this.flags & 64 && (this.flags &= -65, Me.has(this) && (Me.delete(this), this.trigger()));
	}
	notify() {
		this.flags & 2 && !(this.flags & 32) || this.flags & 8 || Le(this);
	}
	run() {
		if (!(this.flags & 1)) return this.fn();
		this.flags |= 2, Xe(this), Be(this);
		let e = j, t = Ke;
		j = this, Ke = !0;
		try {
			return this.fn();
		} finally {
			Ve(this), j = e, Ke = t, this.flags &= -3;
		}
	}
	stop() {
		if (this.flags & 1) {
			for (let e = this.deps; e; e = e.nextDep) We(e);
			this.deps = this.depsTail = void 0, Xe(this), this.onStop && this.onStop(), this.flags &= -2;
		}
	}
	trigger() {
		this.flags & 64 ? Me.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
	}
	runIfDirty() {
		He(this) && this.run();
	}
	get dirty() {
		return He(this);
	}
}, Pe = 0, Fe, Ie;
function Le(e, t = !1) {
	e.flags |= 8, t ? (e.next = Ie, Ie = e) : (e.next = Fe, Fe = e);
}
function Re() {
	Pe++;
}
function ze() {
	if (--Pe > 0) return;
	if (Ie) {
		let e = Ie;
		for (Ie = void 0; e;) {
			let t = e.next;
			e.next = void 0, e.flags &= -9, e = t;
		}
	}
	let e;
	for (; Fe;) {
		let t = Fe;
		for (Fe = void 0; t;) {
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
function Be(e) {
	for (let t = e.deps; t; t = t.nextDep) t.version = -1, t.prevActiveLink = t.dep.activeLink, t.dep.activeLink = t;
}
function Ve(e) {
	let t, n = e.depsTail, r = n;
	for (; r;) {
		let e = r.prevDep;
		r.version === -1 ? (r === n && (n = e), We(r), Ge(r)) : t = r, r.dep.activeLink = r.prevActiveLink, r.prevActiveLink = void 0, r = e;
	}
	e.deps = t, e.depsTail = n;
}
function He(e) {
	for (let t = e.deps; t; t = t.nextDep) if (t.dep.version !== t.version || t.dep.computed && (Ue(t.dep.computed) || t.dep.version !== t.version)) return !0;
	return !!e._dirty;
}
function Ue(e) {
	if (e.flags & 4 && !(e.flags & 16) || (e.flags &= -17, e.globalVersion === Ze) || (e.globalVersion = Ze, !e.isSSR && e.flags & 128 && (!e.deps && !e._dirty || !He(e)))) return;
	e.flags |= 2;
	let t = e.dep, n = j, r = Ke;
	j = e, Ke = !0;
	try {
		Be(e);
		let n = e.fn(e._value);
		(t.version === 0 || ae(n, e._value)) && (e.flags |= 128, e._value = n, t.version++);
	} catch (e) {
		throw t.version++, e;
	} finally {
		j = n, Ke = r, Ve(e), e.flags &= -3;
	}
}
function We(e, t = !1) {
	let { dep: n, prevSub: r, nextSub: i } = e;
	if (r && (r.nextSub = i, e.prevSub = void 0), i && (i.prevSub = r, e.nextSub = void 0), n.subs === e && (n.subs = r, !r && n.computed)) {
		n.computed.flags &= -5;
		for (let e = n.computed.deps; e; e = e.nextDep) We(e, !0);
	}
	!t && !--n.sc && n.map && n.map.delete(n.key);
}
function Ge(e) {
	let { prevDep: t, nextDep: n } = e;
	t && (t.nextDep = n, e.prevDep = void 0), n && (n.prevDep = t, e.nextDep = void 0);
}
var Ke = !0, qe = [];
function Je() {
	qe.push(Ke), Ke = !1;
}
function Ye() {
	let e = qe.pop();
	Ke = e === void 0 || e;
}
function Xe(e) {
	let { cleanup: t } = e;
	if (e.cleanup = void 0, t) {
		let e = j;
		j = void 0;
		try {
			t();
		} finally {
			j = e;
		}
	}
}
var Ze = 0, Qe = class {
	constructor(e, t) {
		this.sub = e, this.dep = t, this.version = t.version, this.nextDep = this.prevDep = this.nextSub = this.prevSub = this.prevActiveLink = void 0;
	}
}, $e = class {
	constructor(e) {
		this.computed = e, this.version = 0, this.activeLink = void 0, this.subs = void 0, this.map = void 0, this.key = void 0, this.sc = 0, this.__v_skip = !0;
	}
	track(e) {
		if (!j || !Ke || j === this.computed) return;
		let t = this.activeLink;
		if (t === void 0 || t.sub !== j) t = this.activeLink = new Qe(j, this), j.deps ? (t.prevDep = j.depsTail, j.depsTail.nextDep = t, j.depsTail = t) : j.deps = j.depsTail = t, et(t);
		else if (t.version === -1 && (t.version = this.version, t.nextDep)) {
			let e = t.nextDep;
			e.prevDep = t.prevDep, t.prevDep && (t.prevDep.nextDep = e), t.prevDep = j.depsTail, t.nextDep = void 0, j.depsTail.nextDep = t, j.depsTail = t, j.deps === t && (j.deps = e);
		}
		return t;
	}
	trigger(e) {
		this.version++, Ze++, this.notify(e);
	}
	notify(e) {
		Re();
		try {
			for (let e = this.subs; e; e = e.prevSub) e.sub.notify() && e.sub.dep.notify();
		} finally {
			ze();
		}
	}
};
function et(e) {
	if (e.dep.sc++, e.sub.flags & 4) {
		let t = e.dep.computed;
		if (t && !e.dep.subs) {
			t.flags |= 20;
			for (let e = t.deps; e; e = e.nextDep) et(e);
		}
		let n = e.dep.subs;
		n !== e && (e.prevSub = n, n && (n.nextSub = e)), e.dep.subs = e;
	}
}
var tt = /* @__PURE__ */ new WeakMap(), nt = /* @__PURE__ */ Symbol(""), rt = /* @__PURE__ */ Symbol(""), it = /* @__PURE__ */ Symbol("");
function M(e, t, n) {
	if (Ke && j) {
		let t = tt.get(e);
		t || tt.set(e, t = /* @__PURE__ */ new Map());
		let r = t.get(n);
		r || (t.set(n, r = new $e()), r.map = t, r.key = n), r.track();
	}
}
function at(e, t, n, r, i, a) {
	let o = tt.get(e);
	if (!o) {
		Ze++;
		return;
	}
	let s = (e) => {
		e && e.trigger();
	};
	if (Re(), t === "clear") o.forEach(s);
	else {
		let i = d(e), a = i && w(n);
		if (i && n === "length") {
			let e = Number(r);
			o.forEach((t, n) => {
				(n === "length" || n === it || !_(n) && n >= e) && s(t);
			});
		} else switch ((n !== void 0 || o.has(void 0)) && s(o.get(n)), a && s(o.get(it)), t) {
			case "add":
				i ? a && s(o.get("length")) : (s(o.get(nt)), f(e) && s(o.get(rt)));
				break;
			case "delete":
				i || (s(o.get(nt)), f(e) && s(o.get(rt)));
				break;
			case "set": f(e) && s(o.get(nt));
		}
	}
	ze();
}
function ot(e, t) {
	let n = tt.get(e);
	return n && n.get(t);
}
function st(e) {
	let t = /* @__PURE__ */ N(e);
	return t === e || (M(t, "iterate", it), /* @__PURE__ */ Xt(e)) ? t : /* @__PURE__ */ Yt(e) ? /* @__PURE__ */ Jt(e) ? t.map((e) => en($t(e))) : t.map(en) : t.map($t);
}
function ct(e) {
	return M(e = /* @__PURE__ */ N(e), "iterate", it), e;
}
function lt(e, t) {
	return /* @__PURE__ */ Yt(e) ? en(/* @__PURE__ */ Jt(e) ? $t(t) : t) : $t(t);
}
var ut = {
	__proto__: null,
	[Symbol.iterator]() {
		return dt(this, Symbol.iterator, (e) => lt(this, e));
	},
	concat(...e) {
		return st(this).concat(...e.map((e) => d(e) ? st(e) : e));
	},
	entries() {
		return dt(this, "entries", (e) => (e[1] = lt(this, e[1]), e));
	},
	every(e, t) {
		return mt(this, "every", e, t, void 0, arguments);
	},
	filter(e, t) {
		return mt(this, "filter", e, t, (e) => e.map((e) => lt(this, e)), arguments);
	},
	find(e, t) {
		return mt(this, "find", e, t, (e) => lt(this, e), arguments);
	},
	findIndex(e, t) {
		return mt(this, "findIndex", e, t, void 0, arguments);
	},
	findLast(e, t) {
		return mt(this, "findLast", e, t, (e) => lt(this, e), arguments);
	},
	findLastIndex(e, t) {
		return mt(this, "findLastIndex", e, t, void 0, arguments);
	},
	forEach(e, t) {
		return mt(this, "forEach", e, t, void 0, arguments);
	},
	includes(...e) {
		return gt(this, "includes", e);
	},
	indexOf(...e) {
		return gt(this, "indexOf", e);
	},
	join(e) {
		return st(this).join(e);
	},
	lastIndexOf(...e) {
		return gt(this, "lastIndexOf", e);
	},
	map(e, t) {
		return mt(this, "map", e, t, void 0, arguments);
	},
	pop() {
		return _t(this, "pop");
	},
	push(...e) {
		return _t(this, "push", e);
	},
	reduce(e, ...t) {
		return ht(this, "reduce", e, t);
	},
	reduceRight(e, ...t) {
		return ht(this, "reduceRight", e, t);
	},
	shift() {
		return _t(this, "shift");
	},
	some(e, t) {
		return mt(this, "some", e, t, void 0, arguments);
	},
	splice(...e) {
		return _t(this, "splice", e);
	},
	toReversed() {
		return st(this).toReversed();
	},
	toSorted(e) {
		return st(this).toSorted(e);
	},
	toSpliced(...e) {
		return st(this).toSpliced(...e);
	},
	unshift(...e) {
		return _t(this, "unshift", e);
	},
	values() {
		return dt(this, "values", (e) => lt(this, e));
	}
};
function dt(e, t, n) {
	let r = ct(e), i = r[t], a = i.call(r);
	if (r !== e && !/* @__PURE__ */ Xt(e)) {
		if (a[Symbol.toStringTag] === "Array Iterator") {
			let e = Object.create(Object.getPrototypeOf(a));
			return e.next = () => ft(a.next(), n), i !== pt[t] && Object.defineProperties(e, {
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
		a._next = a.next, a.next = () => ft(a._next(), n);
	}
	return a;
}
function ft(e, t) {
	return e.done || (e.value = t(e.value)), e;
}
var pt = Array.prototype;
function mt(e, t, n, r, i, a) {
	let o = ct(e), s = o !== e && !/* @__PURE__ */ Xt(e), c = o[t];
	if (c !== pt[t]) {
		let t = c.apply(e, a);
		return s ? $t(t) : t;
	}
	let l = n;
	o !== e && (s ? l = function(t, r) {
		return n.call(this, lt(e, t), r, e);
	} : n.length > 2 && (l = function(t, r) {
		return n.call(this, t, r, e);
	}));
	let u = c.call(o, l, r);
	return s && i ? i(u) : u;
}
function ht(e, t, n, r) {
	let i = ct(e), a = i !== e && !/* @__PURE__ */ Xt(e), o = n, s = !1;
	i !== e && (a ? (s = r.length === 0, o = function(t, r, i) {
		return s && (s = !1, t = lt(e, t)), n.call(this, t, lt(e, r), i, e);
	}) : n.length > 3 && (o = function(t, r, i) {
		return n.call(this, t, r, i, e);
	}));
	let c = i[t](o, ...r);
	return s ? lt(e, c) : c;
}
function gt(e, t, n) {
	let r = /* @__PURE__ */ N(e);
	M(r, "iterate", it);
	let i = r[t](...n);
	return (i === -1 || i === !1) && /* @__PURE__ */ Zt(n[0]) ? (n[0] = /* @__PURE__ */ N(n[0]), r[t](...n)) : i;
}
function _t(e, t, n = []) {
	Je(), Re();
	let r = (/* @__PURE__ */ N(e))[t].apply(e, n);
	return ze(), Ye(), r;
}
var vt = /* @__PURE__ */ e("__proto__,__v_isRef,__isVue"), yt = /* @__PURE__ */ new Set(/* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(_));
function bt(e) {
	_(e) || (e = String(e));
	let t = /* @__PURE__ */ N(this);
	return M(t, "has", e), t.hasOwnProperty(e);
}
var xt = class {
	constructor(e = !1, t = !1) {
		this._isReadonly = e, this._isShallow = t;
	}
	get(e, t, n) {
		if (t === "__v_skip") return e.__v_skip;
		let r = this._isReadonly, i = this._isShallow;
		if (t === "__v_isReactive") return !r;
		if (t === "__v_isReadonly") return r;
		if (t === "__v_isShallow") return i;
		if (t === "__v_raw") return n === (r ? i ? Vt : Bt : i ? zt : Rt).get(e) || Object.getPrototypeOf(e) === Object.getPrototypeOf(n) ? e : void 0;
		let a = d(e);
		if (!r) {
			let e;
			if (a && (e = ut[t])) return e;
			if (t === "hasOwnProperty") return bt;
		}
		let o = Reflect.get(e, t, /* @__PURE__ */ P(e) ? e : n);
		if ((_(t) ? yt.has(t) : vt(t)) || (r || M(e, "get", t), i)) return o;
		if (/* @__PURE__ */ P(o)) {
			let e = a && w(t) ? o : o.value;
			return r && v(e) ? /* @__PURE__ */ Gt(e) : e;
		}
		return v(o) ? r ? /* @__PURE__ */ Gt(o) : /* @__PURE__ */ Ut(o) : o;
	}
}, St = class extends xt {
	constructor(e = !1) {
		super(!1, e);
	}
	set(e, t, n, r) {
		let i = e[t], a = d(e) && w(t);
		if (!this._isShallow) {
			let e = /* @__PURE__ */ Yt(i);
			if (!/* @__PURE__ */ Xt(n) && !/* @__PURE__ */ Yt(n) && (i = /* @__PURE__ */ N(i), n = /* @__PURE__ */ N(n)), !a && /* @__PURE__ */ P(i) && !/* @__PURE__ */ P(n)) return e || (i.value = n), !0;
		}
		let o = a ? Number(t) < e.length : u(e, t), s = Reflect.set(e, t, n, /* @__PURE__ */ P(e) ? e : r);
		return e === /* @__PURE__ */ N(r) && s && (o ? ae(n, i) && at(e, "set", t, n, i) : at(e, "add", t, n)), s;
	}
	deleteProperty(e, t) {
		let n = u(e, t), r = e[t], i = Reflect.deleteProperty(e, t);
		return i && n && at(e, "delete", t, void 0, r), i;
	}
	has(e, t) {
		let n = Reflect.has(e, t);
		return _(t) && yt.has(t) || M(e, "has", t), n;
	}
	ownKeys(e) {
		return M(e, "iterate", d(e) ? "length" : nt), Reflect.ownKeys(e);
	}
}, Ct = class extends xt {
	constructor(e = !1) {
		super(!0, e);
	}
	set(e, t) {
		return !0;
	}
	deleteProperty(e, t) {
		return !0;
	}
}, wt = /* @__PURE__ */ new St(), Tt = /* @__PURE__ */ new Ct(), Et = /* @__PURE__ */ new St(!0), Dt = /* @__PURE__ */ new Ct(!0), Ot = (e) => e, kt = (e) => Reflect.getPrototypeOf(e);
function At(e, t, n) {
	return function(...r) {
		let i = this.__v_raw, a = /* @__PURE__ */ N(i), o = f(a), c = e === "entries" || e === Symbol.iterator && o, l = e === "keys" && o, u = i[e](...r), d = n ? Ot : t ? en : $t;
		return !t && M(a, "iterate", l ? rt : nt), s(Object.create(u), { next() {
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
function jt(e) {
	return function(...t) {
		return e === "delete" ? !1 : e === "clear" ? void 0 : this;
	};
}
function Mt(e, t) {
	let n = {
		get(n) {
			let r = this.__v_raw, i = /* @__PURE__ */ N(r), a = /* @__PURE__ */ N(n);
			e || (ae(n, a) && M(i, "get", n), M(i, "get", a));
			let { has: o } = kt(i), s = t ? Ot : e ? en : $t;
			if (o.call(i, n)) return s(r.get(n));
			if (o.call(i, a)) return s(r.get(a));
			r !== i && r.get(n);
		},
		get size() {
			let t = this.__v_raw;
			return !e && M(/* @__PURE__ */ N(t), "iterate", nt), t.size;
		},
		has(t) {
			let n = this.__v_raw, r = /* @__PURE__ */ N(n), i = /* @__PURE__ */ N(t);
			return e || (ae(t, i) && M(r, "has", t), M(r, "has", i)), t === i ? n.has(t) : n.has(t) || n.has(i);
		},
		forEach(n, r) {
			let i = this, a = i.__v_raw, o = /* @__PURE__ */ N(a), s = t ? Ot : e ? en : $t;
			return !e && M(o, "iterate", nt), a.forEach((e, t) => n.call(r, s(e), s(t), i));
		}
	};
	return s(n, e ? {
		add: jt("add"),
		set: jt("set"),
		delete: jt("delete"),
		clear: jt("clear")
	} : {
		add(e) {
			let n = /* @__PURE__ */ N(this), r = kt(n), i = /* @__PURE__ */ N(e), a = !t && !/* @__PURE__ */ Xt(e) && !/* @__PURE__ */ Yt(e) ? i : e;
			return r.has.call(n, a) || ae(e, a) && r.has.call(n, e) || ae(i, a) && r.has.call(n, i) || (n.add(a), at(n, "add", a, a)), this;
		},
		set(e, n) {
			t || /* @__PURE__ */ Xt(n) || /* @__PURE__ */ Yt(n) || (n = /* @__PURE__ */ N(n));
			let r = /* @__PURE__ */ N(this), { has: i, get: a } = kt(r), o = i.call(r, e);
			o ||= (e = /* @__PURE__ */ N(e), i.call(r, e));
			let s = a.call(r, e);
			return r.set(e, n), o ? ae(n, s) && at(r, "set", e, n, s) : at(r, "add", e, n), this;
		},
		delete(e) {
			let t = /* @__PURE__ */ N(this), { has: n, get: r } = kt(t), i = n.call(t, e);
			i ||= (e = /* @__PURE__ */ N(e), n.call(t, e));
			let a = r ? r.call(t, e) : void 0, o = t.delete(e);
			return i && at(t, "delete", e, void 0, a), o;
		},
		clear() {
			let e = /* @__PURE__ */ N(this), t = e.size !== 0, n = e.clear();
			return t && at(e, "clear", void 0, void 0, void 0), n;
		}
	}), [
		"keys",
		"values",
		"entries",
		Symbol.iterator
	].forEach((r) => {
		n[r] = At(r, e, t);
	}), n;
}
function Nt(e, t) {
	let n = Mt(e, t);
	return (r, i, a) => i === "__v_isReactive" ? !e : i === "__v_isReadonly" ? e : i === "__v_isShallow" ? t : i === "__v_raw" ? r : Reflect.get(u(n, i) && i in r ? n : r, i, a);
}
var Pt = { get: /* @__PURE__ */ Nt(!1, !1) }, Ft = { get: /* @__PURE__ */ Nt(!1, !0) }, It = { get: /* @__PURE__ */ Nt(!0, !1) }, Lt = { get: /* @__PURE__ */ Nt(!0, !0) }, Rt = /* @__PURE__ */ new WeakMap(), zt = /* @__PURE__ */ new WeakMap(), Bt = /* @__PURE__ */ new WeakMap(), Vt = /* @__PURE__ */ new WeakMap();
function Ht(e) {
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
function Ut(e) {
	return /* @__PURE__ */ Yt(e) ? e : qt(e, !1, wt, Pt, Rt);
}
// @__NO_SIDE_EFFECTS__
function Wt(e) {
	return qt(e, !1, Et, Ft, zt);
}
// @__NO_SIDE_EFFECTS__
function Gt(e) {
	return qt(e, !0, Tt, It, Bt);
}
// @__NO_SIDE_EFFECTS__
function Kt(e) {
	return qt(e, !0, Dt, Lt, Vt);
}
function qt(e, t, n, r, i) {
	if (!v(e) || e.__v_raw && !(t && e.__v_isReactive) || e.__v_skip || !Object.isExtensible(e)) return e;
	let a = i.get(e);
	if (a) return a;
	let o = Ht(S(e));
	if (o === 0) return e;
	let s = new Proxy(e, o === 2 ? r : n);
	return i.set(e, s), s;
}
// @__NO_SIDE_EFFECTS__
function Jt(e) {
	return /* @__PURE__ */ Yt(e) ? /* @__PURE__ */ Jt(e.__v_raw) : !!(e && e.__v_isReactive);
}
// @__NO_SIDE_EFFECTS__
function Yt(e) {
	return !!(e && e.__v_isReadonly);
}
// @__NO_SIDE_EFFECTS__
function Xt(e) {
	return !!(e && e.__v_isShallow);
}
// @__NO_SIDE_EFFECTS__
function Zt(e) {
	return e ? !!e.__v_raw : !1;
}
// @__NO_SIDE_EFFECTS__
function N(e) {
	let t = e && e.__v_raw;
	return t ? /* @__PURE__ */ N(t) : e;
}
function Qt(e) {
	return !u(e, "__v_skip") && Object.isExtensible(e) && O(e, "__v_skip", !0), e;
}
var $t = (e) => v(e) ? /* @__PURE__ */ Ut(e) : e, en = (e) => v(e) ? /* @__PURE__ */ Gt(e) : e;
// @__NO_SIDE_EFFECTS__
function P(e) {
	return e ? e.__v_isRef === !0 : !1;
}
// @__NO_SIDE_EFFECTS__
function F(e) {
	return nn(e, !1);
}
// @__NO_SIDE_EFFECTS__
function tn(e) {
	return nn(e, !0);
}
function nn(e, t) {
	return /* @__PURE__ */ P(e) ? e : new rn(e, t);
}
var rn = class {
	constructor(e, t) {
		this.dep = new $e(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = t ? e : /* @__PURE__ */ N(e), this._value = t ? e : $t(e), this.__v_isShallow = t;
	}
	get value() {
		return this.dep.track(), this._value;
	}
	set value(e) {
		let t = this._rawValue, n = this.__v_isShallow || /* @__PURE__ */ Xt(e) || /* @__PURE__ */ Yt(e);
		e = n ? e : /* @__PURE__ */ N(e), ae(e, t) && (this._rawValue = e, this._value = n ? e : $t(e), this.dep.trigger());
	}
};
function an(e) {
	e.dep && e.dep.trigger();
}
function I(e) {
	return /* @__PURE__ */ P(e) ? e.value : e;
}
function L(e) {
	return h(e) ? e() : I(e);
}
var on = {
	get: (e, t, n) => t === "__v_raw" ? e : I(Reflect.get(e, t, n)),
	set: (e, t, n, r) => {
		let i = e[t];
		return /* @__PURE__ */ P(i) && !/* @__PURE__ */ P(n) ? (i.value = n, !0) : Reflect.set(e, t, n, r);
	}
};
function sn(e) {
	return /* @__PURE__ */ Jt(e) ? e : new Proxy(e, on);
}
// @__NO_SIDE_EFFECTS__
function cn(e) {
	let t = d(e) ? Array(e.length) : {};
	for (let n in e) t[n] = fn(e, n);
	return t;
}
var ln = class {
	constructor(e, t, n) {
		this._object = e, this._defaultValue = n, this.__v_isRef = !0, this._value = void 0, this._key = _(t) ? t : String(t), this._raw = /* @__PURE__ */ N(e);
		let r = !0, i = e;
		if (!d(e) || _(this._key) || !w(this._key)) do
			r = !/* @__PURE__ */ Zt(i) || /* @__PURE__ */ Xt(i);
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
		return ot(this._raw, this._key);
	}
}, un = class {
	constructor(e) {
		this._getter = e, this.__v_isRef = !0, this.__v_isReadonly = !0, this._value = void 0;
	}
	get value() {
		return this._value = this._getter();
	}
};
// @__NO_SIDE_EFFECTS__
function dn(e, t, n) {
	return /* @__PURE__ */ P(e) ? e : h(e) ? new un(e) : v(e) && arguments.length > 1 ? fn(e, t, n) : /* @__PURE__ */ F(e);
}
function fn(e, t, n) {
	return new ln(e, t, n);
}
var pn = class {
	constructor(e, t, n) {
		this.fn = e, this.setter = t, this._value = void 0, this.dep = new $e(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = Ze - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !t, this.isSSR = n;
	}
	notify() {
		if (this.flags |= 16, !(this.flags & 8) && j !== this) return Le(this, !0), !0;
	}
	get value() {
		let e = this.dep.track();
		return Ue(this), e && (e.version = this.dep.version), this._value;
	}
	set value(e) {
		this.setter && this.setter(e);
	}
};
// @__NO_SIDE_EFFECTS__
function mn(e, t, n = !1) {
	let r, i;
	return h(e) ? r = e : (r = e.get, i = e.set), new pn(r, i, n);
}
var hn = {}, gn = /* @__PURE__ */ new WeakMap(), _n = void 0;
function vn(e, t = !1, n = _n) {
	if (n) {
		let t = gn.get(n);
		t || gn.set(n, t = []), t.push(e);
	}
}
function yn(e, n, i = t) {
	let { immediate: a, deep: o, once: s, scheduler: l, augmentJob: u, call: f } = i, p = (e) => o ? e : /* @__PURE__ */ Xt(e) || o === !1 || o === 0 ? bn(e, 1) : bn(e), m, g, _, v, y = !1, b = !1;
	if (/* @__PURE__ */ P(e) ? (g = () => e.value, y = /* @__PURE__ */ Xt(e)) : /* @__PURE__ */ Jt(e) ? (g = () => p(e), y = !0) : d(e) ? (b = !0, y = e.some((e) => /* @__PURE__ */ Jt(e) || /* @__PURE__ */ Xt(e)), g = () => e.map((e) => {
		if (/* @__PURE__ */ P(e)) return e.value;
		if (/* @__PURE__ */ Jt(e)) return p(e);
		if (h(e)) return f ? f(e, 2) : e();
	})) : g = h(e) ? n ? f ? () => f(e, 2) : e : () => {
		if (_) {
			Je();
			try {
				_();
			} finally {
				Ye();
			}
		}
		let t = _n;
		_n = m;
		try {
			return f ? f(e, 3, [v]) : e(v);
		} finally {
			_n = t;
		}
	} : r, n && o) {
		let e = g, t = o === !0 ? Infinity : o;
		g = () => bn(e(), t);
	}
	let x = Ae(), S = () => {
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
	let C = b ? Array(e.length).fill(hn) : hn, w = (e) => {
		if (m.flags & 1 && (m.dirty || e)) {
			if (n) {
				let t = m.run();
				if (e || o || y || (b ? t.some((e, t) => ae(e, C[t])) : ae(t, C))) {
					let e = _n;
					Je();
					try {
						_ && _(), _n = m;
						let e = [
							t,
							C === hn ? void 0 : b && C[0] === hn ? [] : C,
							v
						];
						C = t, f ? f(n, 3, e) : n(...e);
					} finally {
						_n = e, Ye();
					}
				}
			} else m.run();
		}
	};
	return u && u(w), m = new Ne(g), m.scheduler = l ? () => l(w, !1) : w, v = (e) => vn(e, !1, m), _ = m.onStop = () => {
		let e = gn.get(m);
		if (e) {
			if (f) f(e, 4);
			else for (let t of e) t();
			gn.delete(m);
		}
	}, n ? a ? w(!0) : C = m.run() : l ? l(w.bind(null, !0), !0) : m.run(), S.pause = m.pause.bind(m), S.resume = m.resume.bind(m), S.stop = S, S;
}
function bn(e, t = Infinity, n) {
	if (t <= 0 || !v(e) || e.__v_skip || (n ||= /* @__PURE__ */ new Map(), (n.get(e) || 0) >= t)) return e;
	if (n.set(e, t), t--, /* @__PURE__ */ P(e)) bn(e.value, t, n);
	else if (d(e)) for (let r = 0; r < e.length; r++) bn(e[r], t, n);
	else if (p(e) || f(e)) e.forEach((e) => {
		bn(e, t, n);
	});
	else if (C(e)) {
		for (let r in e) bn(e[r], t, n);
		for (let r of Object.getOwnPropertySymbols(e)) Object.prototype.propertyIsEnumerable.call(e, r) && bn(e[r], t, n);
	}
	return e;
}
// node_modules/@vue/runtime-core/dist/runtime-core.esm-bundler.js
function xn(e, t, n, r) {
	try {
		return r ? e(...r) : e();
	} catch (e) {
		Cn(e, t, n);
	}
}
function Sn(e, t, n, r) {
	if (h(e)) {
		let i = xn(e, t, n, r);
		return i && y(i) && i.catch((e) => {
			Cn(e, t, n, void 0, !0);
		}), i;
	}
	if (d(e)) {
		let i = [];
		for (let a = 0; a < e.length; a++) i.push(Sn(e[a], t, n, r));
		return i;
	}
}
function Cn(e, n, r, i = !0, a = !1) {
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
			Je(), xn(s, null, 10, [
				e,
				i,
				o
			]), Ye();
			return;
		}
	}
	wn(e, r, o, i, c);
}
function wn(e, t, n, r = !0, i = !1) {
	if (i) throw e;
	console.error(e);
}
var R = [], Tn = -1, En = [], Dn = null, On = 0, kn = /* @__PURE__ */ Promise.resolve(), An = null;
function jn(e) {
	let t = An || kn;
	return e ? t.then(this ? e.bind(this) : e) : t;
}
function Mn(e) {
	let t = Tn + 1, n = R.length;
	for (; t < n;) {
		let r = t + n >>> 1, i = R[r], a = Bn(i);
		a < e || a === e && i.flags & 2 ? t = r + 1 : n = r;
	}
	return t;
}
function Nn(e) {
	if (!(e.flags & 1)) {
		let t = Bn(e), n = R[R.length - 1];
		!n || !(e.flags & 2) && t >= Bn(n) ? R.push(e) : R.splice(Mn(t), 0, e), e.flags |= 1, Pn();
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
	for (; r < R.length; r++) {
		let n = R[r];
		if (n && n.flags & 2) {
			if (e && n.id !== e.uid || t !== void 0 && !(n.id >= t)) continue;
			R.splice(r, 1), r = e ? r - 1 : Tn, n.flags & 4 && (n.flags &= -2), n(), n.flags & 4 || (n.flags &= -2);
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
		for (Tn = 0; Tn < R.length; Tn++) {
			let e = R[Tn];
			e && !(e.flags & 8) && (e.flags & 4 && (e.flags &= -2), xn(e, e.i, e.i ? 15 : 14), e.flags & 4 || (e.flags &= -2));
		}
	} finally {
		for (; Tn < R.length; Tn++) {
			let e = R[Tn];
			e && (e.flags &= -2);
		}
		Tn = -1, R.length = 0, Ln(e), An = null, (R.length || En.length) && Vn(e);
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
		r._d && ya(-1);
		let i = Un(t), a = ha.length, o;
		try {
			o = e(...n);
		} finally {
			for (let e = ha.length; e > a; e--) _a();
			Un(i), r._d && ya(1);
		}
		return o;
	};
	return r._n = !0, r._c = !0, r._d = !0, r;
}
function Wn(e, n) {
	if (z === null) return e;
	let r = $a(z), i = e.dirs ||= [];
	for (let e = 0; e < n.length; e++) {
		let [a, o, s, c = t] = n[e];
		a && (h(a) && (a = {
			mounted: a,
			updated: a
		}), a.deep && bn(o), i.push({
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
		u && (Je(), Sn(u, n, 8, [
			e.el,
			l,
			i,
			t
		]), Ye());
	}
}
function Kn(e, t) {
	if (Q) {
		let n = Q.provides, r = Q.parent && Q.parent.provides;
		r === n && (n = Q.provides = Object.create(r)), n[e] = t;
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
function V(e, t, n) {
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
	let p = Q;
	u.call = (e, t, n) => Sn(e, p, t, n);
	let m = !1;
	c === "post" ? u.scheduler = (e) => {
		e.i = p, G(e, p && p.suspense);
	} : c !== "sync" && (m = !0, u.scheduler = (e, t) => {
		t ? e() : Nn(e);
	}), u.augmentJob = (e) => {
		n && (e.flags |= 4), m && (e.flags |= 2, p && (e.id = p.uid, e.i = p));
	};
	let h = yn(e, n, u);
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
			tr.set(e, t), G(t, a);
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
			if (o === "svg" || or(p) ? o = "svg" : (o === "mathml" || sr(p)) && (o = "mathml"), y ? (f(e.dynamicChildren, y, _, i, a, o, s), ia(e, t, !0)) : c || d(e, t, _, b, i, a, o, s, !1), v) g ? t.props && e.props && t.props.to !== e.props.to && (t.props.to = e.props.to) : ur(t, n, r, l, 1);
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
		for (let n of e) if (n.type !== pa) {
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
	} else if (e.transition = t, e.type === K && d(e.children)) {
		let n = Oi(e.children, !1);
		n && vr(n, t);
	}
}
function yr(e) {
	if (e.component) return yr(e.component.subTree);
	if (e.type === K) {
		let t = d(e.children) && Oi(e.children, !1);
		return t ? yr(t) : void 0;
	}
	if (e.type !== pa) return e;
}
// @__NO_SIDE_EFFECTS__
function H(e, t) {
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
	if (h(p)) xn(p, f, 12, [l, _]);
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
				t.id = -1, Cr.set(e, t), G(t, r);
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
function Ar(e, t, n = Q) {
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
function Mr(e, t, n = Q, r = !1) {
	if (n) {
		let i = n[e] || (n[e] = []), a = t.__weh ||= (...r) => {
			Je();
			let i = Ha(n), a = Sn(t, n, e, r);
			return i(), Ye(), a;
		};
		return r ? i.unshift(a) : i.push(a), a;
	}
}
var Nr = (e) => (t, n = Q) => {
	Ga && e !== "sp" || Mr(e, (...e) => t(...e), n);
}, Pr = Nr("bm"), Fr = Nr("m"), Ir = Nr("bu"), Lr = Nr("u"), Rr = Nr("bum"), zr = Nr("um"), Br = Nr("sp"), Vr = Nr("rtg"), Hr = Nr("rtc");
function Ur(e, t = Q) {
	Mr("ec", e, t);
}
var Wr = "components";
function Gr(e, t) {
	return Jr(Wr, e, !0, t) || e;
}
var Kr = /* @__PURE__ */ Symbol.for("v-ndc");
function qr(e) {
	return g(e) ? Jr(Wr, e, !1) || e : e || Kr;
}
function Jr(e, t, n = !0, r = !1) {
	let i = z || Q;
	if (i) {
		let n = i.type;
		if (e === Wr) {
			let e = eo(n, !1);
			if (e && (e === t || e === E(t) || e === re(E(t)))) return n;
		}
		let a = Yr(i[e] || n[e], t) || Yr(i.appContext[e], t);
		return !a && r ? n : a;
	}
}
function Yr(e, t) {
	return e && (e[t] || e[E(t)] || e[re(E(t))]);
}
function Xr(e, t, n, r) {
	let i, a = n && n[r], o = d(e);
	if (o || g(e)) {
		let n = o && /* @__PURE__ */ Jt(e), r = !1, s = !1;
		n && (r = !/* @__PURE__ */ Xt(e), s = /* @__PURE__ */ Yt(e), e = ct(e)), i = Array(e.length);
		for (let n = 0, o = e.length; n < o; n++) i[n] = t(r ? s ? en($t(e[n])) : $t(e[n]) : e[n], n, void 0, a && a[n]);
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
function U(e, t, n, r, i, a) {
	if (n ??= {}, z.ce || z.parent && Er(z.parent) && z.parent.ce) {
		let e = a != null && n.key == null ? s({}, n, { key: a }) : n, i = Object.keys(e).length > 0;
		return t !== "default" && (e.name = t), q(), Y(K, null, [Z("slot", e, r && r())], i ? -2 : 64);
	}
	let o = e[t];
	o && o._c && (o._d = !1);
	let c = ha.length;
	q();
	let l;
	try {
		let i = o && Zr(o(n)), s = n.key || a || i && i.key;
		l = Y(K, { key: (s && !_(s) ? s : `_${t}`) + (!i && r ? "_fb" : "") }, i || (r ? r() : []), i && e._ === 1 ? 64 : -2);
	} catch (e) {
		for (let e = ha.length; e > c; e--) _a();
		throw e;
	} finally {
		o && o._c && (o._d = !0);
	}
	return !i && l.scopeId && (l.slotScopeIds = [l.scopeId + "-s"]), l;
}
function Zr(e) {
	return e.some((e) => !xa(e) || !(e.type === pa || e.type === K && !Zr(e.children))) ? e : null;
}
var Qr = (e) => e ? Wa(e) ? $a(e) : Qr(e.parent) : null, $r = /* @__PURE__ */ s(/* @__PURE__ */ Object.create(null), {
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
		if (d) return n === "$attrs" && M(e.attrs, "get", ""), d(e);
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
	let { data: a, computed: o, methods: s, watch: c, provide: l, inject: u, created: f, beforeMount: p, mounted: m, beforeUpdate: g, updated: _, activated: y, deactivated: b, beforeDestroy: x, beforeUnmount: S, destroyed: C, unmounted: w, render: T, renderTracked: ee, renderTriggered: te, errorCaptured: E, serverPrefetch: ne, expose: D, inheritAttrs: re, components: ie, directives: ae, filters: oe } = t;
	if (u && oi(u, i, null), s) for (let e in s) {
		let t = s[e];
		h(t) && (i[e] = t.bind(n));
	}
	if (a) {
		let t = a.call(n, n);
		v(t) && (e.data = /* @__PURE__ */ Ut(t));
	}
	if (ii = !0, o) for (let e in o) {
		let t = o[e], a = $({
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
function oi(e, t, n = r) {
	d(e) && (e = mi(e));
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
function si(e, t, n) {
	Sn(d(e) ? e.map((e) => e.bind(t.proxy)) : e.bind(t.proxy), t, n);
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
	props: gi,
	emits: gi,
	methods: hi,
	computed: hi,
	beforeCreate: W,
	created: W,
	beforeMount: W,
	mounted: W,
	beforeUpdate: W,
	updated: W,
	beforeDestroy: W,
	beforeUnmount: W,
	destroyed: W,
	unmounted: W,
	activated: W,
	deactivated: W,
	errorCaptured: W,
	serverPrefetch: W,
	components: hi,
	directives: hi,
	watch: _i,
	provide: fi,
	inject: pi
};
function fi(e, t) {
	return t ? e ? function() {
		return s(h(e) ? e.call(this, this) : e, h(t) ? t.call(this, this) : t);
	} : t : e;
}
function pi(e, t) {
	return hi(mi(e), mi(t));
}
function mi(e) {
	if (d(e)) {
		let t = {};
		for (let n = 0; n < e.length; n++) t[e[n]] = e[n];
		return t;
	}
	return e;
}
function W(e, t) {
	return e ? [...new Set([].concat(e, t))] : t;
}
function hi(e, t) {
	return e ? s(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function gi(e, t) {
	return e ? d(e) && d(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : s(/* @__PURE__ */ Object.create(null), ni(e), ni(t ?? {})) : t;
}
function _i(e, t) {
	if (!e) return t;
	if (!t) return e;
	let n = s(/* @__PURE__ */ Object.create(null), e);
	for (let r in t) n[r] = W(e[r], t[r]);
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
					let u = l._ceVNode || Z(n, r);
					return u.appContext = i, s === !0 ? s = "svg" : s === !1 && (s = void 0), o && t ? t(u, a) : e(u, a, s), c = !0, l._container = a, a.__vue_app__ = l, $a(u.component);
				}
			},
			onUnmount(e) {
				o.push(e);
			},
			unmount() {
				c && (Sn(o, l._instance, 16), e(null, l._container), delete l._container.__vue_app__);
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
	!l && o && (l = i[c = ie(D(n))]), l && Sn(l, e, 6, a);
	let u = i[c + "Once"];
	if (u) {
		if (!e.emitted) e.emitted = {};
		else if (e.emitted[c]) return;
		e.emitted[c] = !0, Sn(u, e, 6, a);
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
			v = Aa(u.call(t, e, d, f, m, p, h)), y = c;
		} else {
			let e = t;
			v = Aa(e.length > 1 ? e(f, {
				attrs: c,
				slots: s,
				emit: l
			}) : e(f, null)), y = t.props ? c : ki(c);
		}
	} catch (t) {
		ha.length = 0, Cn(t, e, 1), v = Z(pa);
	}
	let b = v;
	if (y && g !== !1) {
		let e = Object.keys(y), { shapeFlag: t } = b;
		e.length && t & 7 && (a && e.some(o) && (y = Ai(y, a)), b = Da(b, y, !1, !0));
	}
	return n.dirs && (b = Da(b, null, !1, !0), b.dirs = b.dirs ? b.dirs.concat(n.dirs) : n.dirs), n.transition && vr(rr(b.type) && _r(b) || b, n.transition), v = b, Un(_), v;
}
function Oi(e, t = !0) {
	let n;
	for (let t = 0; t < e.length; t++) {
		let r = e[t];
		if (xa(r)) {
			if (r.type !== pa || r.children === "v-if") {
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
	e.props = n ? r ? i : /* @__PURE__ */ Wt(i) : e.type.props ? i : a, e.attrs = a;
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
	l && at(e.attrs, "set", "");
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
var Gi = (e) => e === "_" || e === "_ctx" || e === "$stable", Ki = (e) => d(e) ? e.map(Aa) : [Aa(e)], qi = (e, t, n) => {
	if (t._n) return t;
	let r = B((...e) => Ki(t(...e)), n);
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
}, G = da;
function $i(e) {
	return ea(e);
}
function ea(e, i) {
	let a = le();
	a.__VUE__ = !0;
	let { insert: o, remove: s, patchProp: c, createElement: l, createText: u, createComment: d, setText: f, setElementText: p, parentNode: m, nextSibling: h, setScopeId: g = r, insertStaticContent: _ } = e, v = (e, t, r, i = null, a = null, o = null, s = void 0, c = null, l = !!t.dynamicChildren) => {
		if (e === t) return;
		e && !Sa(e, t) && (i = ye(e), k(e, a, o, !0), e = null), t.patchFlag === -2 && (l = !1, t.dynamicChildren = null), t.dynamicChildren && e && e.dynamicChildren && e.dynamicChildren.hasOnce && (t.dynamicChildren === n && (t.dynamicChildren = []), t.dynamicChildren.hasOnce = !0);
		let { type: u, ref: d, shapeFlag: f } = t;
		switch (u) {
			case fa:
				y(e, t, r, i);
				break;
			case pa:
				b(e, t, r, i);
				break;
			case ma:
				e ?? x(t, r, i, s);
				break;
			case K:
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
		if (d = e.el = l(e.type, a, m && m.is, m), h & 8 ? p(d, e.children) : h & 16 && E(e.children, d, null, r, i, ta(e, a), s, u), _ && Gn(e, null, r, "created"), te(d, e, e.scopeId, s, r), m) {
			for (let e in m) e !== "value" && !T(e) && c(d, e, null, m[e], a, r);
			"value" in m && c(d, "value", null, m.value, a), (f = m.onVnodeBeforeMount) && Pa(f, r, e);
		}
		_ && Gn(e, null, r, "beforeMount");
		let v = ra(i, g);
		v ? g.beforeEnter(d) : g && !g.persisted && (d[ua] = !0), o(d, t, n), ((f = m && m.onVnodeMounted) || v || _) && G(() => {
			try {
				f && Pa(f, r, e), v && g.enter(d), _ && Gn(e, null, r, "mounted");
			} finally {}
		}, i);
	}, te = (e, t, n, r, i) => {
		if (n && g(e, n), r) for (let t = 0; t < r.length; t++) g(e, r[t]);
		if (i) {
			let n = i.subTree;
			if (t === n || la(n.type) && (n.ssContent === t || n.ssFallback === t)) {
				let t = i.vnode;
				te(e, t, t.scopeId, t.slotScopeIds, i.parent);
			}
		}
	}, E = (e, t, n, r, i, a, o, s, c = 0) => {
		for (let l = c; l < e.length; l++) {
			let c = e[l] = s ? ja(e[l]) : Aa(e[l]);
			v(null, c, t, n, r, i, a, o, s);
		}
	}, ne = (e, n, r, i, a, o, s) => {
		let l = n.el = e.el, { patchFlag: u, dynamicChildren: d, dirs: f } = n;
		u |= e.patchFlag & 16;
		let m = e.props || t, h = n.props || t, g;
		if (r && na(r, !1), (g = h.onVnodeBeforeUpdate) && Pa(g, r, n, e), f && Gn(n, e, r, "beforeUpdate"), r && na(r, !0), d && (!e.dynamicChildren || e.dynamicChildren.length !== d.length) && (u = 0, s = !1, d = null), (m.innerHTML && h.innerHTML == null || m.textContent && h.textContent == null) && p(l, ""), d ? D(e.dynamicChildren, d, l, r, i, ta(n, a), o) : s || de(e, n, l, null, r, i, ta(n, a), o, !1), u > 0) {
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
		((g = h.onVnodeUpdated) || f) && G(() => {
			g && Pa(g, r, n, e), f && Gn(n, e, r, "updated");
		}, i);
	}, D = (e, t, n, r, i, a, o) => {
		for (let s = 0; s < t.length; s++) {
			let c = e[s], l = t[s], u = c.el || ca(c), d = u && (c.type === K || !Sa(c, l) || c.shapeFlag & 198) ? m(u) : n;
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
		h && (c = c ? c.concat(h) : h), e == null ? (o(d, n, r), o(f, n, r), E(t.children || [], n, f, i, a, s, c, l)) : p > 0 && p & 64 && m && e.dynamicChildren && e.dynamicChildren.length === m.length ? (D(e.dynamicChildren, m, n, i, a, s, c), (t.key != null || i && t === i.subTree) && ia(e, t, !0)) : de(e, t, n, f, i, a, s, c, l);
	}, ae = (e, t, n, r, i, a, o, s, c) => {
		t.slotScopeIds = s, e == null ? t.shapeFlag & 512 ? i.ctx.activate(t, n, r, o, c) : O(t, n, r, i, a, o, c) : se(e, t, c);
	}, O = (e, t, n, r, i, a, o) => {
		let s = e.component = Ra(e, r, i);
		if (Dr(e) && (s.ctx.renderer = xe), Ka(s, !1, o), s.asyncDep) {
			if (i && i.registerDep(s, ce, o, a), !e.el) {
				let r = s.subTree = Z(pa);
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
					let n = oa(e);
					if (n) {
						t && (t.el = c.el, ue(e, t, o)), n.asyncDep.then(() => {
							let t = () => {
								e.job.flags & 8 || (i && i.pendingBranch ? G(t, i) : l());
							};
							t.flags = 48, G(t, i);
						});
						return;
					}
				}
				let u = t, d;
				na(e, !1), t ? (t.el = c.el, ue(e, t, o)) : t = c, n && oe(n), (d = t.props && t.props.onVnodeBeforeUpdate) && Pa(d, s, t, c), na(e, !0);
				let f = Di(e), p = e.subTree;
				e.subTree = f, v(p, f, m(p.el || ca(p)), ye(p), e, i, a), t.el = f.el, u === null && Pi(e, f.el), r && G(r, i), (d = t.props && t.props.onVnodeUpdated) && G(() => Pa(d, s, t, c), i);
			} else {
				let o, { el: s, props: c } = t, { bm: l, m: u, parent: d, root: f, type: p } = e, m = Er(t);
				if (na(e, !1), l && oe(l), !m && (o = c && c.onVnodeBeforeMount) && Pa(o, d, t), na(e, !0), s && Ce) {
					let t = () => {
						e.subTree = Di(e), Ce(s, e.subTree, e, i, null);
					};
					m && p.__asyncHydrate ? p.__asyncHydrate(s, e, t) : t();
				} else {
					f.ce && f.ce._hasShadowRoot() && f.ce._injectChildStyle(p, e.parent ? e.parent.type : void 0);
					let o = e.subTree = Di(e);
					v(null, o, n, r, e, i, a), t.el = o.el;
				}
				if (u && G(u, i), !m && (o = c && c.onVnodeMounted)) {
					let e = t;
					G(() => Pa(o, d, e), i);
				}
				(t.shapeFlag & 256 || d && Er(d.vnode) && d.vnode.shapeFlag & 256) && e.a && G(e.a, i), e.isMounted = !0, t = n = r = null;
			}
		};
		e.scope.on();
		let c = e.effect = new Ne(s);
		e.scope.off();
		let l = e.update = c.run.bind(c), u = e.job = c.runIfDirty.bind(c);
		u.i = e, u.id = e.uid, c.scheduler = () => Nn(u), na(e, !0), l();
	}, ue = (e, t, n) => {
		t.component = e;
		let r = e.vnode.props;
		e.vnode = t, e.next = null, zi(e, t.props, r, n), Qi(e, t.children, n), Je(), In(e), Ye();
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
			let n = t[p] = l ? ja(t[p]) : Aa(t[p]);
			v(e[p], n, r, null, a, o, s, c, l);
		}
		u > d ? ve(e, a, o, !0, !1, f) : E(t, r, i, a, o, s, c, l, f);
	}, pe = (e, t, r, i, a, o, s, c, l) => {
		let u = 0, d = t.length, f = e.length - 1, p = d - 1;
		for (; u <= f && u <= p;) {
			let n = e[u], i = t[u] = l ? ja(t[u]) : Aa(t[u]);
			if (Sa(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			u++;
		}
		for (; u <= f && u <= p;) {
			let n = e[f], i = t[p] = l ? ja(t[p]) : Aa(t[p]);
			if (Sa(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			f--, p--;
		}
		if (u > f) {
			if (u <= p) {
				let e = p + 1, n = e < d ? t[e].el : i;
				for (; u <= p;) v(null, t[u] = l ? ja(t[u]) : Aa(t[u]), r, n, a, o, s, c, l), u++;
			}
		} else if (u > p) for (; u <= f;) k(e[u], a, o, !0), u++;
		else {
			let m = u, h = u, g = /* @__PURE__ */ new Map();
			for (u = h; u <= p; u++) {
				let e = t[u] = l ? ja(t[u]) : Aa(t[u]);
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
				else for (_ = h; _ <= p; _++) if (C[_ - h] === 0 && Sa(n, t[_])) {
					i = _;
					break;
				}
				i === void 0 ? k(n, a, o, !0) : (C[i - h] = u + 1, i >= S ? S = i : x = !0, v(n, t[i], r, null, a, o, s, c, l), y++);
			}
			let w = x ? aa(C) : n;
			for (_ = w.length - 1, u = b - 1; u >= 0; u--) {
				let e = h + u, n = t[e], f = t[e + 1], p = e + 1 < d ? f.el || ca(f) : i;
				C[u] === 0 ? v(null, n, r, p, a, o, s, c, l) : x && (_ < 0 || u !== w[_] ? me(n, r, p, 2) : _--);
			}
		}
	}, me = (e, t, n, r, i = null) => {
		let { el: a, type: c, transition: l, children: u, shapeFlag: d } = e;
		if (d & 6) me(e.component.subTree, t, n, r);
		else if (d & 128) e.suspense.move(t, n, r);
		else if (d & 64) c.move(e, t, n, xe);
		else if (c === K) {
			o(a, t, n);
			for (let e = 0; e < u.length; e++) me(u[e], t, n, r);
			o(e.anchor, t, n);
		} else if (c === ma) S(e, t, n);
		else if (r !== 2 && d & 1 && l) {
			if (r === 0) l.persisted && !a[hr] ? o(a, t, n) : (l.beforeEnter(a), o(a, t, n), G(() => l.enter(a), i));
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
		if ((d === -2 || l && l.hasOnce) && (i = !1), s != null && (Je(), wr(s, null, n, e, !0), Ye()), p == null || e.ctx && e.ctx !== t || (t.renderCache[p] = void 0), u & 256 && t.ctx.deactivate(e)) return;
		let h = u & 1 && f, g = !Er(e), _;
		if (g && (_ = o && o.onVnodeBeforeUnmount) && Pa(_, t, e), u & 6) _e(e.component, n, r);
		else {
			if (u & 128) {
				e.suspense.unmount(n, r);
				return;
			}
			h && Gn(e, null, t, "beforeUnmount"), u & 64 ? e.type.remove(e, t, n, xe, r) : l && !l.hasOnce && (a !== K || d > 0 && d & 64) ? ve(l, t, n, !1, !0) : (a === K && d & 384 || !i && u & 16) && ve(c, t, n), r && he(e);
		}
		let v = m != null && p == null;
		(g && (_ = o && o.onVnodeUnmounted) || h || v) && G(() => {
			_ && Pa(_, t, e), h && Gn(e, null, t, "unmounted"), v && (e.el = null);
		}, n);
	}, he = (e) => {
		let { type: t, el: n, anchor: r, transition: i } = e, a = t === K;
		if (a && !i) {
			ge(n, r);
			return;
		}
		if (t === ma) {
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
		sa(c), sa(l), r && oe(r), i.stop(), a ? (a.flags |= 8, k(o, e, t, n)) : o && (o.transition = e.vnode.transition, k(o, e, t, n)), s && G(s, t);
		let u = () => {
			e.isUnmounted = !0;
		};
		u.flags = 16, G(u, t);
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
		}, e && t._vnode ? void 0 : e && e.component ? e.component.uid : La());
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
function ta({ type: e, props: t }, n) {
	return n === "svg" && e === "foreignObject" || n === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : n;
}
function na({ effect: e, job: t }, n) {
	n ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function ra(e, t) {
	return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function ia(e, t, n = !1) {
	let r = e.children, i = t.children;
	if (d(r) && d(i)) for (let e = 0; e < r.length; e++) {
		let t = r[e], a = i[e];
		a.shapeFlag & 1 && !a.dynamicChildren && ((a.patchFlag <= 0 || a.patchFlag === 32) && (a = i[e] = ja(i[e]), a.el = t.el), !n && a.patchFlag !== -2 && ia(t, a)), a.type === fa && (a.patchFlag === -1 && (a = i[e] = ja(a)), a.el = t.el), a.type === pa && !a.el && (a.el = t.el);
	}
}
function aa(e) {
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
function oa(e) {
	let t = e.subTree.component;
	if (t) return t.asyncDep && !t.asyncResolved ? t : oa(t);
}
function sa(e) {
	if (e) for (let t = 0; t < e.length; t++) e[t].flags |= 8;
}
function ca(e) {
	if (e.placeholder) return e.placeholder;
	let t = e.component;
	if (t) return ca(t.subTree);
	let n = e.suspense;
	return n && n.activeBranch ? ca(n.activeBranch) : null;
}
var la = (e) => e.__isSuspense, ua = /* @__PURE__ */ Symbol("_deferredEnter");
function da(e, t) {
	t && t.pendingBranch ? d(e) ? t.effects.push(...e) : t.effects.push(e) : Fn(e);
}
var K = /* @__PURE__ */ Symbol.for("v-fgt"), fa = /* @__PURE__ */ Symbol.for("v-txt"), pa = /* @__PURE__ */ Symbol.for("v-cmt"), ma = /* @__PURE__ */ Symbol.for("v-stc"), ha = [], ga = null;
function q(e = !1) {
	ha.push(ga = e ? null : []);
}
function _a() {
	ha.pop(), ga = ha[ha.length - 1] || null;
}
var va = 1;
function ya(e, t = !1) {
	va += e, e < 0 && ga && t && (ga.hasOnce = !0);
}
function ba(e) {
	return e.dynamicChildren = va > 0 ? ga || n : null, _a(), va > 0 && ga && ga.push(e), e;
}
function J(e, t, n, r, i, a) {
	return ba(X(e, t, n, r, i, a, !0));
}
function Y(e, t, n, r, i) {
	return ba(Z(e, t, n, r, i, !0));
}
function xa(e) {
	return e ? e.__v_isVNode === !0 : !1;
}
function Sa(e, t) {
	return e.type === t.type && e.key === t.key;
}
var Ca = ({ key: e }) => e ?? null, wa = ({ ref: e, ref_key: t, ref_for: n }) => (typeof e == "number" && (e = "" + e), e == null ? null : g(e) || /* @__PURE__ */ P(e) || h(e) ? {
	i: z,
	r: e,
	k: t,
	f: !!n
} : e);
function X(e, t = null, n = null, r = 0, i = null, a = e === K ? 0 : 1, o = !1, s = !1) {
	let c = {
		__v_isVNode: !0,
		__v_skip: !0,
		type: e,
		props: t,
		key: t && Ca(t),
		ref: t && wa(t),
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
	return s ? (Ma(c, n), a & 128 && e.normalize(c)) : n && (c.shapeFlag |= g(n) ? 8 : 16), va > 0 && !o && ga && (c.patchFlag > 0 || a & 6) && c.patchFlag !== 32 && ga.push(c), c;
}
var Z = Ta;
function Ta(e, t = null, n = null, r = 0, i = null, a = !1) {
	if (e && e !== Kr || (e = pa), xa(e)) {
		let r = Da(e, t, !0);
		return n && Ma(r, n), va > 0 && !a && ga && (r.shapeFlag & 6 ? ga[ga.indexOf(e)] = r : ga.push(r)), r.patchFlag = -2, r;
	}
	if (to(e) && (e = e.__vccOpts), t) {
		t = Ea(t);
		let { class: e, style: n } = t;
		e && !g(e) && (t.class = k(e)), v(n) && (/* @__PURE__ */ Zt(n) && !d(n) && (n = s({}, n)), t.style = ue(n));
	}
	let o = g(e) ? 1 : la(e) ? 128 : rr(e) ? 64 : v(e) ? 4 : h(e) ? 2 : 0;
	return X(e, t, n, r, i, o, a, !0);
}
function Ea(e) {
	return e ? /* @__PURE__ */ Zt(e) ? s({}, e) : Li(e) ? s({}, e[Xa] || e) : e : null;
}
function Da(e, t, n = !1, r = !1) {
	let { props: i, ref: a, patchFlag: o, children: s, transition: c } = e, l = t ? Na(i || {}, t) : i, u = {
		__v_isVNode: !0,
		__v_skip: !0,
		type: e.type,
		props: l,
		key: l && Ca(l),
		ref: t && t.ref ? n && a ? d(a) ? a.concat(wa(t)) : [a, wa(t)] : wa(t) : a,
		scopeId: e.scopeId,
		slotScopeIds: e.slotScopeIds,
		children: s,
		target: e.target,
		targetStart: e.targetStart,
		targetAnchor: e.targetAnchor,
		staticCount: e.staticCount,
		shapeFlag: e.shapeFlag,
		patchFlag: t && e.type !== K ? o === -1 ? 16 : o | 16 : o,
		dynamicProps: e.dynamicProps,
		dynamicChildren: e.dynamicChildren,
		appContext: e.appContext,
		dirs: e.dirs,
		transition: c,
		component: e.component,
		suspense: e.suspense,
		ssContent: e.ssContent && Da(e.ssContent),
		ssFallback: e.ssFallback && Da(e.ssFallback),
		placeholder: e.placeholder,
		el: e.el,
		anchor: e.anchor,
		ctx: e.ctx,
		ce: e.ce,
		cacheIndex: e.cacheIndex
	};
	return c && r && vr(u, c.clone(u)), u;
}
function Oa(e = " ", t = 0) {
	return Z(fa, null, e, t);
}
function ka(e = "", t = !1) {
	return t ? (q(), Y(pa, null, e)) : Z(pa, null, e);
}
function Aa(e) {
	return e == null || typeof e == "boolean" ? Z(pa) : d(e) ? Z(K, null, e.slice()) : xa(e) ? ja(e) : Z(fa, null, String(e));
}
function ja(e) {
	return e.el === null && e.patchFlag !== -1 || e.memo ? e : Da(e);
}
function Ma(e, t) {
	let n = 0, { shapeFlag: r } = e;
	if (t == null) t = null;
	else if (d(t)) n = 16;
	else if (typeof t == "object") {
		if (r & 65) {
			let n = t.default;
			n && (n._c && (n._d = !1), Ma(e, n()), n._c && (n._d = !0));
			return;
		}
		{
			n = 32;
			let r = t._;
			!r && !Li(t) ? t._ctx = z : r === 3 && z && (z.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
		}
	} else if (h(t)) {
		if (r & 65) {
			Ma(e, { default: t });
			return;
		}
		t = {
			default: t,
			_ctx: z
		}, n = 32;
	} else t = String(t), r & 64 ? (n = 16, t = [Oa(t)]) : n = 8;
	e.children = t, e.shapeFlag |= n;
}
function Na(...e) {
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
function Pa(e, t, n, r = null) {
	Sn(e, t, 7, [n, r]);
}
var Fa = /* @__PURE__ */ vi(), Ia = 0;
function La() {
	return Ia;
}
function Ra(e, n, r) {
	let i = e.type, a = (n ? n.appContext : e.appContext) || Fa, o = {
		uid: Ia++,
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
		scope: new Oe(!0),
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
var Q = null, za = () => Q || z, Ba, Va;
{
	let e = le(), t = (t, n) => {
		let r;
		return (r = e[t]) || (r = e[t] = []), r.push(n), (e) => {
			r.length > 1 ? r.forEach((t) => t(e)) : r[0](e);
		};
	};
	Ba = t("__VUE_INSTANCE_SETTERS__", (e) => Q = e), Va = t("__VUE_SSR_SETTERS__", (e) => Ga = e);
}
var Ha = (e) => {
	let t = Q;
	return Ba(e), e.scope.on(), () => {
		e.scope.off(), Ba(t);
	};
}, Ua = () => {
	Q && Q.scope.off(), Ba(null);
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
	e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, ti);
	let { setup: r } = n;
	if (r) {
		Je();
		let n = e.setupContext = r.length > 1 ? Qa(e) : null, i = Ha(e), a = xn(r, e, 0, [e.props, n]), o = y(a);
		if (Ye(), i(), (o || e.sp) && !Er(e) && xr(e), o) {
			if (a.then(Ua, Ua), t) return a.then((n) => {
				Va(!0);
				try {
					Ja(e, n, t);
				} finally {
					Va(!1);
				}
			}).catch((t) => {
				Cn(t, e, 0, void 0, !0), e.ssrRender = (e, t) => t("<!---->");
			});
			e.asyncDep = a;
		} else Ja(e, a, t);
	} else Ya(e, t);
}
function Ja(e, t, n) {
	h(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : v(t) && (e.setupState = sn(t)), Ya(e, n);
}
function Ya(e, t, n) {
	let i = e.type;
	e.render ||= i.render || r;
	{
		let t = Ha(e);
		Je();
		try {
			ai(e);
		} finally {
			Ye(), t();
		}
	}
}
var Xa = /* @__PURE__ */ Symbol(), Za = { get(e, t) {
	return M(e, "get", ""), t === Xa ? e : e[t];
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
	return e.exposed ? e.exposeProxy ||= new Proxy(sn(Qt(e.exposed)), {
		get(t, n) {
			if (n in t) return t[n];
			if (n in $r) return $r[n](e);
		},
		has(e, t) {
			return t in e || t in $r;
		}
	}) : e.proxy;
}
function eo(e, t = !0) {
	return h(e) ? e.displayName || e.name : e.name || t && e.__name;
}
function to(e) {
	return h(e) && "__vccOpts" in e;
}
var $ = (e, t) => /* @__PURE__ */ mn(e, t, Ga);
function no(e, t, n) {
	try {
		ya(-1);
		let r = arguments.length;
		return r === 2 ? v(t) && !d(t) ? xa(t) ? Z(e, null, [t]) : Z(e, t) : Z(e, null, t) : (r > 3 ? n = Array.prototype.slice.call(arguments, 2) : r === 3 && xa(n) && (n = [n]), Z(e, t, n));
	} finally {
		ya(1);
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
	return va > 0 && ga && ga.push(e), !0;
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
var _o = /* @__PURE__ */ Symbol("_vod"), vo = /* @__PURE__ */ Symbol("_vsh"), yo = {
	name: "show",
	beforeMount(e, { value: t }, { transition: n }) {
		e[_o] = e.style.display === "none" ? "" : e.style.display, n && t ? n.beforeEnter(e) : bo(e, t);
	},
	mounted(e, { value: t }, { transition: n }) {
		n && t && n.enter(e);
	},
	updated(e, { value: t, oldValue: n }, { transition: r }) {
		!t != !n && (r ? t ? (r.beforeEnter(e), bo(e, !0), r.enter(e)) : r.leave(e, () => {
			bo(e, !1);
		}) : bo(e, t));
	},
	beforeUnmount(e, { value: t }) {
		bo(e, t);
	}
};
function bo(e, t) {
	e.style.display = t ? e[_o] : "none", e[vo] = !t;
}
var xo = /* @__PURE__ */ Symbol(""), So = /(?:^|;)\s*display\s*:/;
function Co(e, t, n) {
	let r = e.style, i = g(n), a = !1;
	if (n && !i) {
		if (t) {
			if (g(t)) for (let e of t.split(";")) {
				let t = e.slice(0, e.indexOf(":")).trim();
				n[t] ?? To(r, t, "");
			}
			else for (let e in t) n[e] ?? To(r, e, "");
		}
		for (let i in n) {
			i === "display" && (a = !0);
			let o = n[i];
			o == null ? To(r, i, "") : ko(e, i, !g(t) && t ? t[i] : void 0, o) || To(r, i, o);
		}
	} else if (i) {
		if (t !== n) {
			let e = r[xo];
			e && (n += ";" + e), r.cssText = n, a = So.test(n);
		}
	} else t && e.removeAttribute("style");
	_o in e && (i && t === n || (e[_o] = a ? r.display : ""), e[vo] && (r.display = "none"));
}
var wo = /\s*!important$/;
function To(e, t, n) {
	if (d(n)) n.forEach((n) => To(e, t, n));
	else if (n ??= "", t.startsWith("--")) wo.test(n) ? e.setProperty(t, n.replace(wo, ""), "important") : e.setProperty(t, n);
	else {
		let r = Oo(e, t);
		wo.test(n) ? e.setProperty(D(r), n.replace(wo, ""), "important") : e[r] = n;
	}
}
var Eo = [
	"Webkit",
	"Moz",
	"ms"
], Do = {};
function Oo(e, t) {
	let n = Do[t];
	if (n) return n;
	let r = E(t);
	if (r !== "filter" && r in e) return Do[t] = r;
	r = re(r);
	for (let n = 0; n < Eo.length; n++) {
		let i = Eo[n] + r;
		if (i in e) return Do[t] = i;
	}
	return t;
}
function ko(e, t, n, r) {
	return e.tagName === "TEXTAREA" && (t === "width" || t === "height") && g(r) && n === r;
}
var Ao = "http://www.w3.org/1999/xlink";
function jo(e, t, n, r, i, a = ge(t)) {
	r && t.startsWith("xlink:") ? n == null ? e.removeAttributeNS(Ao, t.slice(6, t.length)) : e.setAttributeNS(Ao, t, n) : n == null || a && !_e(n) ? e.removeAttribute(t) : e.setAttribute(t, a ? "" : _(n) ? String(n) : n);
}
function Mo(e, t, n, r, i) {
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
function No(e, t, n, r) {
	e.addEventListener(t, n, r);
}
function Po(e, t, n, r) {
	e.removeEventListener(t, n, r);
}
var Fo = /* @__PURE__ */ Symbol("_vei");
function Io(e, t, n, r, i = null) {
	let a = e[Fo] || (e[Fo] = {}), o = a[t];
	if (r && o) o.value = r;
	else {
		let [n, s] = zo(t);
		r ? No(e, n, a[t] = Uo(r, i), s) : o && (Po(e, n, o, s), a[t] = void 0);
	}
}
var Lo = /(Once|Passive|Capture)$/, Ro = /^on:?(?:Once|Passive|Capture)$/;
function zo(e) {
	let t, n;
	for (; (n = e.match(Lo)) && !Ro.test(e);) t ||= {}, e = e.slice(0, e.length - n[1].length), t[n[1].toLowerCase()] = !0;
	return [e[2] === ":" ? e.slice(3) : D(e.slice(2)), t];
}
var Bo = 0, Vo = /* @__PURE__ */ Promise.resolve(), Ho = () => Bo ||= (Vo.then(() => Bo = 0), Date.now());
function Uo(e, t) {
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
				e && Sn(e, t, 5, a);
			}
		} else Sn(r, t, 5, [e]);
	};
	return n.value = e, n.attached = Ho(), n;
}
var Wo = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, Go = (e, t, n, r, i, s) => {
	let c = i === "svg";
	t === "class" ? go(e, r, c) : t === "style" ? Co(e, n, r) : a(t) ? o(t) || Io(e, t, n, r, s) : (t[0] === "." ? (t = t.slice(1), 1) : t[0] === "^" ? (t = t.slice(1), 0) : Ko(e, t, r, c)) ? (Mo(e, t, r), e.tagName.includes("-") || t !== "value" && t !== "checked" && t !== "selected" || jo(e, t, r, c, s, t !== "value")) : e._isVueCE && (qo(e, t) || e._def.__asyncLoader && (/[A-Z]/.test(t) || !g(r))) ? Mo(e, E(t), r, s, t) : (t === "true-value" ? e._trueValue = r : t === "false-value" && (e._falseValue = r), jo(e, t, r, c));
};
function Ko(e, t, n, r) {
	if (r) return !!(t === "innerHTML" || t === "textContent" || t in e && Wo(t) && h(n));
	if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "autocorrect" || t === "sandbox" && e.tagName === "IFRAME" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA") return !1;
	if (t === "width" || t === "height") {
		let t = e.tagName;
		if (t === "IMG" || t === "VIDEO" || t === "CANVAS" || t === "SOURCE") return !1;
	}
	return Wo(t) && g(n) ? !1 : t in e;
}
function qo(e, t) {
	let n = e._def.props;
	if (!n) return !1;
	let r = E(t);
	return Array.isArray(n) ? n.some((e) => E(e) === r) : Object.keys(n).some((e) => E(e) === r);
}
var Jo = (e) => {
	let t = e.props["onUpdate:modelValue"] || !1;
	return d(t) ? (e) => oe(t, e) : t;
};
function Yo(e) {
	e.target.composing = !0;
}
function Xo(e) {
	let t = e.target;
	t.composing && (t.composing = !1, t.dispatchEvent(new Event("input")));
}
var Zo = /* @__PURE__ */ Symbol("_assign"), Qo = /* @__PURE__ */ Symbol("_initialValue");
function $o(e, t, n) {
	return t && (e = e.trim()), n && (e = se(e)), e;
}
var es = {
	created(e, { modifiers: { lazy: t, trim: n, number: r } }, i) {
		e.parentNode && (e.type === "text" ? e[Qo] = e.defaultValue.replace(/[\r\n]/g, "") : e.type === "textarea" && (e[Qo] = e.defaultValue.replace(/\r\n?/g, "\n"))), e[Zo] = Jo(i);
		let a = r || i.props && i.props.type === "number";
		No(e, t ? "change" : "input", (t) => {
			t.target.composing || e[Zo]($o(e.value, n, a));
		}), (n || a) && No(e, "change", () => {
			e.value = $o(e.value, n, a);
		}), t || (No(e, "compositionstart", Yo), No(e, "compositionend", Xo), No(e, "change", Xo));
	},
	mounted(e, { value: t, modifiers: { trim: n, number: r } }) {
		let i = t ?? "", a = e[Qo];
		delete e[Qo], a !== void 0 && (e.type === "text" || e.type === "textarea") && e.value !== a ? e[Zo]($o(e.value, n, r)) : e.value = i;
	},
	beforeUpdate(e, { value: t, oldValue: n, modifiers: { lazy: r, trim: i, number: a } }, o) {
		if (e[Zo] = Jo(o), e.composing) return;
		let s = (a || e.type === "number") && !/^0\d/.test(e.value) ? se(e.value) : e.value, c = t ?? "";
		if (s === c) return;
		let l = e.getRootNode();
		(l instanceof Document || l instanceof ShadowRoot) && l.activeElement === e && e.type !== "range" && (r && t === n || i && e.value.trim() === c) || (e.value = c);
	}
}, ts = {
	deep: !0,
	created(e, { value: t, modifiers: { number: n } }, r) {
		e._modelValue = t, No(e, "change", () => {
			let t = Array.prototype.filter.call(e.options, (e) => e.selected).map((e) => n ? se(is(e)) : is(e)), r = e.multiple, i = r ? p(e._modelValue) ? new Set(t) : t : t[0], a = e._pendingValue = [r, r ? d(i) ? t.slice() : t : i];
			try {
				e[Zo](i);
			} finally {
				jn(() => {
					e._pendingValue === a && (e._pendingValue = void 0);
				});
			}
		}), e[Zo] = Jo(r);
	},
	mounted(e, { value: t, modifiers: { number: n } }) {
		rs(e, t, n);
	},
	beforeUpdate(e, { value: t }, n) {
		e._modelValue = t, e[Zo] = Jo(n);
	},
	updated(e, { value: t, modifiers: { number: n } }) {
		let r = e._pendingValue;
		e._pendingValue = void 0, r && r[0] === e.multiple && ns(t, r[1], r[0]) || rs(e, t, n);
	}
};
function ns(e, t, n) {
	if (!n || d(e)) return Se(e, t);
	if (p(e)) {
		if (e.size !== t.length) return !1;
		for (let n of t) if (!e.has(n)) return !1;
		return !0;
	}
	return !1;
}
function rs(e, t, n = !1) {
	let r = e.multiple, i = d(t);
	if (!r || i || p(t)) {
		for (let a = 0, o = e.options.length; a < o; a++) {
			let o = e.options[a], s = is(o);
			if (r) {
				if (i) {
					let e = typeof s;
					o.selected = e === "string" || e === "number" ? t.some((e) => String(e) === String(s)) : Ce(t, s) > -1;
				} else o.selected = t.has(s) || n && typeof s == "string" && t.has(se(s));
			} else if (Se(is(o), t)) {
				e.selectedIndex !== a && (e.selectedIndex = a);
				return;
			}
		}
		!r && e.selectedIndex !== -1 && (e.selectedIndex = -1);
	}
}
function is(e) {
	return "_value" in e ? e._value : e.value;
}
var as = [
	"ctrl",
	"shift",
	"alt",
	"meta"
], os = {
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
	exact: (e, t) => as.some((n) => e[`${n}Key`] && !t.includes(n))
}, ss = (e, t) => {
	if (!e) return e;
	let n = e._withMods ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n, ...r) => {
		for (let e = 0; e < t.length; e++) {
			let r = os[t[e]];
			if (r && r(n, t)) return;
		}
		return e(n, ...r);
	}));
}, cs = {
	esc: "escape",
	space: " ",
	up: "arrow-up",
	left: "arrow-left",
	right: "arrow-right",
	down: "arrow-down",
	delete: "backspace"
}, ls = (e, t) => {
	let n = e._withKeys ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n) => {
		if (!("key" in n)) return;
		let r = D(n.key);
		if (t.some((e) => e === r || cs[e] === r)) return e(n);
	}));
}, us = /* @__PURE__ */ s({ patchProp: Go }, mo), ds;
function fs() {
	return ds ||= $i(us);
}
var ps = ((...e) => {
	let t = fs().createApp(...e), { mount: n } = t;
	return t.mount = (e) => {
		let r = hs(e);
		if (!r) return;
		let i = t._component;
		h(i) || i.render || i.template || (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
		let a = n(r, !1, ms(r));
		return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), a;
	}, t;
});
function ms(e) {
	if (e instanceof SVGElement) return "svg";
	if (typeof MathMLElement == "function" && e instanceof MathMLElement) return "mathml";
}
function hs(e) {
	return g(e) ? document.querySelector(e) : e;
}
// src/api/client.ts
var gs = class extends Error {
	status;
	code;
	constructor(e, t, n = "") {
		super(e), this.status = t, this.code = n, this.name = "ApiError";
	}
};
async function _s(e, t = {}) {
	let n = await fetch(e, {
		credentials: "same-origin",
		...t
	});
	if (!(n.headers.get("content-type") || "").includes("application/json")) throw new gs(n.redirected || n.status === 401 ? "登录已失效，请重新登录后刷新。" : `服务返回了非 JSON 响应（HTTP ${n.status}）`, n.status);
	let r = await n.json();
	if (!n.ok || r?.ok === !1) {
		let e = r?.error;
		throw new gs(typeof e == "string" ? e : e?.message || r?.message || `请求失败（HTTP ${n.status}）`, n.status, e?.code || r?.error_code || r?.code || "");
	}
	return r;
}
function vs(e) {
	return e instanceof Error && e.name === "AbortError";
}
// \0plugin-vue:export-helper
var ys = (e, t) => {
	let n = e.__vccOpts || e;
	for (let [e, r] of t) n[e] = r;
	return n;
};
// node_modules/reka-ui/dist/shared/createContext.js
function bs(e, t) {
	let n = typeof e == "string" && !t ? `${e}Context` : t, r = Symbol(n);
	return [(t) => {
		let n = qn(r, t);
		if (n || n === null) return n;
		throw Error(`Injection \`${r.toString()}\` not found. Component must be used within ${Array.isArray(e) ? `one of the following components: ${e.join(", ")}` : `\`${e}\``}`);
	}, (e) => (Kn(r, e), e)];
}
// node_modules/reka-ui/dist/shared/getActiveElement.js
function xs() {
	let e = document.activeElement;
	if (e == null) return null;
	for (; e != null && e.shadowRoot != null && e.shadowRoot.activeElement != null;) e = e.shadowRoot.activeElement;
	return e;
}
// node_modules/reka-ui/dist/shared/handleAndDispatchCustomEvent.js
function Ss(e, t, n) {
	let r = n.originalEvent.target, i = new CustomEvent(e, {
		bubbles: !1,
		cancelable: !0,
		detail: n
	});
	t && r.addEventListener(e, t, { once: !0 }), r.dispatchEvent(i);
}
// node_modules/@vueuse/shared/dist/index.js
function Cs(e, t) {
	return Ae() ? (je(e, t), !0) : !1;
}
function ws(e) {
	let t = !1, n, r = ke(!0);
	return ((...i) => (t ||= (n = r.run(() => e(...i)), !0), n));
}
var Ts = typeof window < "u" && typeof document < "u";
typeof WorkerGlobalScope < "u" && globalThis instanceof WorkerGlobalScope;
var Es = (e) => e !== void 0, Ds = Object.prototype.toString, Os = (e) => Ds.call(e) === "[object Object]", ks = /* #__PURE__ */ As();
function As() {
	var e, t;
	return Ts && !!((e = window) != null && (e = e.navigator) != null && e.userAgent) && (/iP(?:ad|hone|od)/.test(window.navigator.userAgent) || ((t = window) == null || (t = t.navigator) == null ? void 0 : t.maxTouchPoints) > 2 && /iPad|Macintosh/.test(window?.navigator.userAgent));
}
function js(e) {
	return Array.isArray(e) ? e : [e];
}
function Ms(e) {
	return e || za();
}
function Ns(e) {
	if (!Ts) return e;
	let t = 0, n, r, i = () => {
		--t, r && t <= 0 && (r.stop(), n = void 0, r = void 0);
	};
	return ((...a) => (t += 1, r || (r = ke(!0), n = r.run(() => e(...a))), Cs(i), n));
}
function Ps(e) {
	return /* @__PURE__ */ Ut(/* @__PURE__ */ P(e) ? new Proxy({}, {
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
function Fs(e) {
	return Ps($(e));
}
function Is(e, ...t) {
	let n = t.flat(), r = n[0];
	return Fs(() => Object.fromEntries(typeof r == "function" ? Object.entries(/* @__PURE__ */ cn(e)).filter(([e, t]) => !r(L(t), e)) : Object.entries(/* @__PURE__ */ cn(e)).filter((e) => !n.includes(e[0]))));
}
function Ls(e, t) {
	Ms(t) && Rr(e, t);
}
function Rs(e, t, n) {
	return V(e, t, {
		...n,
		immediate: !0
	});
}
// node_modules/@vueuse/core/dist/index.js
var zs = Ts ? window : void 0;
Ts && window.document, Ts && window.navigator, Ts && window.location;
function Bs(e) {
	let t = L(e);
	return t?.$el ?? t;
}
function Vs(...e) {
	let t = (e, t, n, r) => (e.addEventListener(t, n, r), () => e.removeEventListener(t, n, r)), n = $(() => {
		let t = js(L(e[0])).filter((e) => e != null);
		return t.every((e) => typeof e != "string") ? t : void 0;
	});
	return Rs(() => [
		n.value?.map((e) => Bs(e)) ?? [zs].filter((e) => e != null),
		js(L(n.value ? e[1] : e[0])),
		js(I(n.value ? e[2] : e[1])),
		L(n.value ? e[3] : e[2])
	], ([e, n, r, i], a, o) => {
		if (!e?.length || !n?.length || !r?.length) return;
		let s = Os(i) ? { ...i } : i, c = e.flatMap((e) => n.flatMap((n) => r.map((r) => t(e, n, r, s))));
		o(() => {
			c.forEach((e) => e());
		});
	}, { flush: "post" });
}
function Hs() {
	let e = /* @__PURE__ */ tn(!1), t = za();
	return t && Fr(() => {
		e.value = !0;
	}, t), e;
}
function Us(e) {
	return typeof e == "function" ? e : typeof e == "string" ? (t) => t.key === e : Array.isArray(e) ? (t) => e.includes(t.key) : () => !0;
}
function Ws(...e) {
	let t, n, r = {};
	e.length === 3 ? (t = e[0], n = e[1], r = e[2]) : e.length === 2 ? typeof e[1] == "object" ? (t = !0, n = e[0], r = e[1]) : (t = e[0], n = e[1]) : (t = !0, n = e[0]);
	let { target: i = zs, eventName: a = "keydown", passive: o = !1, dedupe: s = !1 } = r, c = Us(t);
	return Vs(i, a, (e) => {
		e.repeat && L(s) || c(e) && n(e);
	}, o);
}
function Gs(e) {
	return JSON.parse(JSON.stringify(e));
}
function Ks(e, t, n, r = {}) {
	var i, a;
	let { clone: o = !1, passive: s = !1, eventName: c, deep: l = !1, defaultValue: u, shouldEmit: d } = r, f = za(), p = n || f?.emit || (f == null || (i = f.$emit) == null ? void 0 : i.bind(f)) || (f == null || (a = f.proxy) == null || (a = a.$emit) == null ? void 0 : a.bind(f?.proxy)), m = c;
	t ||= "modelValue", m ||= `update:${t.toString()}`;
	let h = (e) => o ? typeof o == "function" ? o(e) : Gs(e) : e, g = () => Es(e[t]) ? h(e[t]) : u, _ = (e) => {
		d ? d(e) && p(m, e) : p(m, e);
	};
	if (s) {
		let n = /* @__PURE__ */ F(g()), r = !1;
		return V(() => e[t], (e) => {
			r || (r = !0, n.value = h(e), jn(() => r = !1));
		}), V(n, (n) => {
			!r && (n !== e[t] || l) && _(n);
		}, { deep: l }), n;
	}
	return $({
		get() {
			return g();
		},
		set(e) {
			_(e);
		}
	});
}
// node_modules/reka-ui/dist/shared/renderSlotFragments.js
function qs(e) {
	return e ? e.flatMap((e) => e.type === K ? qs(e.children) : [e]) : [];
}
// node_modules/reka-ui/dist/ConfigProvider/ConfigProvider.js
var [Js, Ys] = /*#__PURE__*/ bs("ConfigProvider"), Xs = /* @__PURE__ */ new WeakMap();
function Zs(e, t) {
	let n = Xs.get(e);
	n || (n = {
		owners: /* @__PURE__ */ new Set(),
		original: e.body.style.pointerEvents
	}, Xs.set(e, n)), n.owners.add(t), e.body.style.pointerEvents = "none";
}
function Qs(e, t) {
	let n = Xs.get(e);
	n?.owners.delete(t) && n.owners.size === 0 && (Xs.delete(e), e.body.style.pointerEvents = n.original);
}
// node_modules/defu/dist/defu.mjs
function $s(e) {
	if (typeof e != "object" || !e) return !1;
	let t = Object.getPrototypeOf(e);
	return t !== null && t !== Object.prototype && Object.getPrototypeOf(t) !== null || Symbol.iterator in e ? !1 : Symbol.toStringTag in e ? Object.prototype.toString.call(e) === "[object Module]" : !0;
}
function ec(e, t, n = ".", r) {
	if (!$s(t)) return ec(e, {}, n, r);
	let i = { ...t };
	for (let t of Object.keys(e)) {
		if (t === "__proto__" || t === "constructor") continue;
		let a = e[t];
		a != null && (r && r(i, t, a, n) || (i[t] = Array.isArray(a) && Array.isArray(i[t]) ? [...a, ...i[t]] : $s(a) && $s(i[t]) ? ec(a, i[t], (n ? `${n}.` : "") + t.toString(), r) : a));
	}
	return i;
}
function tc(e) {
	return (...t) => t.reduce((t, n) => ec(t, n, "", e), {});
}
var nc = tc(), rc = Symbol("useBodyScrollLock"), ic = Ns(() => {
	let e = /* @__PURE__ */ F(/* @__PURE__ */ new Map()), t = /* @__PURE__ */ F(), n = $(() => {
		for (let t of e.value.values()) if (t) return !0;
		return !1;
	}), r = Js({ scrollBody: /* @__PURE__ */ F(!0) }), i = null, a = () => {
		document.body.style.paddingRight = "", document.body.style.marginRight = "", Qs(document, rc), document.documentElement.style.removeProperty("--scrollbar-width"), document.body.style.overflow = t.value ?? "", ks && i?.(), t.value = void 0;
	};
	return V(n, (e, o) => {
		if (!Ts) return;
		if (!e) {
			o && a();
			return;
		}
		t.value === void 0 && (t.value = document.body.style.overflow);
		let s = window.innerWidth - document.documentElement.clientWidth, c = {
			padding: s,
			margin: 0
		}, l = r.scrollBody?.value ? typeof r.scrollBody.value == "object" ? nc({
			padding: r.scrollBody.value.padding === !0 ? s : r.scrollBody.value.padding,
			margin: r.scrollBody.value.margin === !0 ? s : r.scrollBody.value.margin
		}, c) : c : {
			padding: 0,
			margin: 0
		};
		s > 0 && (document.body.style.paddingRight = typeof l.padding == "number" ? `${l.padding}px` : String(l.padding), document.body.style.marginRight = typeof l.margin == "number" ? `${l.margin}px` : String(l.margin), document.documentElement.style.setProperty("--scrollbar-width", `${s}px`), document.body.style.overflow = "hidden"), ks && (i = Vs(document, "touchmove", (e) => sc(e), { passive: !1 })), jn(() => {
			n.value && (Zs(document, rc), document.body.style.overflow = "hidden");
		});
	}, {
		immediate: !0,
		flush: "sync"
	}), e;
});
function ac(e) {
	let t = Math.random().toString(36).substring(2, 7), n = ic();
	n.value.set(t, e ?? !1);
	let r = $({
		get: () => n.value.get(t) ?? !1,
		set: (e) => n.value.set(t, e)
	});
	return Ls(() => {
		n.value.delete(t);
	}), r;
}
function oc(e) {
	let t = window.getComputedStyle(e);
	if (t.overflowX === "scroll" || t.overflowY === "scroll" || t.overflowX === "auto" && e.clientWidth < e.scrollWidth || t.overflowY === "auto" && e.clientHeight < e.scrollHeight) return !0;
	{
		let t = e.parentNode;
		return !(t instanceof Element) || t.tagName === "BODY" ? !1 : oc(t);
	}
}
function sc(e) {
	let t = e || window.event, n = t.target;
	return n instanceof Element && oc(n) ? !1 : t.touches.length > 1 || (t.preventDefault && t.cancelable && t.preventDefault(), !1);
}
// node_modules/reka-ui/dist/shared/useDirection.js
function cc(e) {
	let t = Js({ dir: /* @__PURE__ */ F("ltr") });
	return $(() => e?.value || t.dir?.value || "ltr");
}
// node_modules/reka-ui/dist/shared/useEmitAsProps.js
function lc(e) {
	let t = za(), n = t?.type.emits, r = {};
	return n?.length || console.warn(`No emitted event found. Please check component: ${t?.type.__name}`), n?.forEach((t) => {
		r[ie(E(t))] = (...n) => e(t, ...n);
	}), r;
}
// node_modules/reka-ui/dist/shared/useFocusGuards.js
var uc = 0;
function dc() {
	Xn((e) => {
		if (!Ts) return;
		let t = document.querySelectorAll("[data-reka-focus-guard]");
		document.body.insertAdjacentElement("afterbegin", t[0] ?? fc()), document.body.insertAdjacentElement("beforeend", t[1] ?? fc()), uc++, e(() => {
			uc === 1 && document.querySelectorAll("[data-reka-focus-guard]").forEach((e) => e.remove()), uc--;
		});
	});
}
function fc() {
	let e = document.createElement("span");
	return e.setAttribute("data-reka-focus-guard", ""), e.tabIndex = 0, e.style.outline = "none", e.style.opacity = "0", e.style.position = "fixed", e.style.pointerEvents = "none", e;
}
// node_modules/reka-ui/dist/shared/useForwardExpose.js
function pc() {
	let e = za(), t = /* @__PURE__ */ F(), n = $(() => r());
	Lr(() => {
		n.value !== r() && an(t);
	});
	function r() {
		return t.value && "$el" in t.value && ["#text", "#comment"].includes(t.value.$el.nodeName) ? t.value.$el.nextElementSibling : Bs(t);
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
function mc(e) {
	let t = za(), n = Object.keys(t?.type.props ?? {}).reduce((e, n) => {
		let r = (t?.type.props[n]).default;
		return r !== void 0 && (e[n] = r), e;
	}, {}), r = /* @__PURE__ */ dn(e);
	return $(() => {
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
function hc(e, t) {
	let n = mc(e), r = t ? lc(t) : {};
	return $(() => ({
		...n.value,
		...r
	}));
}
// node_modules/aria-hidden/dist/es2015/index.js
var gc = function(e) {
	return typeof document > "u" ? null : (Array.isArray(e) ? e[0] : e).ownerDocument.body;
}, _c = /* @__PURE__ */ new WeakMap(), vc = /* @__PURE__ */ new WeakMap(), yc = {}, bc = 0, xc = function(e) {
	return e && (e.host || xc(e.parentNode));
}, Sc = function(e, t) {
	return t.map(function(t) {
		if (e.contains(t)) return t;
		var n = xc(t);
		return n && e.contains(n) ? n : (console.error("aria-hidden", t, "in not contained inside", e, ". Doing nothing"), null);
	}).filter(function(e) {
		return !!e;
	});
}, Cc = function(e, t, n, r) {
	var i = Sc(t, Array.isArray(e) ? e : [e]);
	yc[n] || (yc[n] = /* @__PURE__ */ new WeakMap());
	var a = yc[n], o = [], s = /* @__PURE__ */ new Set(), c = new Set(i), l = function(e) {
		e && !s.has(e) && (s.add(e), l(e.parentNode));
	};
	i.forEach(l);
	var u = function(e) {
		e && !c.has(e) && Array.prototype.forEach.call(e.children, function(e) {
			if (s.has(e)) u(e);
			else try {
				var t = e.getAttribute(r), i = t !== null && t !== "false", c = (_c.get(e) || 0) + 1, l = (a.get(e) || 0) + 1;
				_c.set(e, c), a.set(e, l), o.push(e), c === 1 && i && vc.set(e, !0), l === 1 && e.setAttribute(n, "true"), i || e.setAttribute(r, "true");
			} catch (t) {
				console.error("aria-hidden: cannot operate on ", e, t);
			}
		});
	};
	return u(t), s.clear(), bc++, function() {
		o.forEach(function(e) {
			var t = _c.get(e) - 1, i = a.get(e) - 1;
			_c.set(e, t), a.set(e, i), t || (vc.has(e) || e.removeAttribute(r), vc.delete(e)), i || e.removeAttribute(n);
		}), bc--, bc || (_c = /* @__PURE__ */ new WeakMap(), _c = /* @__PURE__ */ new WeakMap(), vc = /* @__PURE__ */ new WeakMap(), yc = {});
	};
}, wc = function(e, t, n) {
	n === void 0 && (n = "data-aria-hidden");
	var r = Array.from(Array.isArray(e) ? e : [e]), i = t || gc(e);
	return i ? (r.push.apply(r, Array.from(i.querySelectorAll("[aria-live], script"))), Cc(r, i, n, "aria-hidden")) : function() {
		return null;
	};
};
// node_modules/reka-ui/dist/shared/useHideOthers.js
function Tc(e) {
	let t;
	V(() => Bs(e), (e) => {
		let n = !1;
		try {
			n = !!e?.closest("[popover]:not(:popover-open)");
		} catch {}
		e && !n ? t = wc(e) : t && t();
	}), zr(() => {
		t && t();
	});
}
function Ec(e, t = "reka") {
	if (e) return e;
	let n, r = Js({ useId: void 0 });
	return n = r.useId ? r.useId() : br?.(), t ? `${t}-${n}` : n;
}
// node_modules/reka-ui/dist/shared/useSize.js
function Dc(e) {
	let t = /* @__PURE__ */ F(), n = $(() => t.value?.width ?? 0), r = $(() => t.value?.height ?? 0), i;
	return Fr(() => {
		let n = Bs(e);
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
function Oc(e, t) {
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
function kc(e, t) {
	let n = /* @__PURE__ */ F({}), r = /* @__PURE__ */ F("none"), i = /* @__PURE__ */ F(e), a = e.value ? "mounted" : "unmounted", o, s = t.value?.ownerDocument.defaultView ?? zs, { state: c, dispatch: l } = Oc(a, {
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
		if (Ts) {
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
			let a = r.value, o = Ac(t.value);
			e ? (l("MOUNT"), u("enter"), o === "none" && u("after-enter")) : o === "none" || o === "undefined" || n.value?.display === "none" ? (l("UNMOUNT"), u("leave"), u("after-leave")) : i && a !== o ? (l("ANIMATION_OUT"), u("leave")) : (l("UNMOUNT"), u("after-leave"));
		}
	}, { immediate: !0 });
	let d = (e) => {
		if (e.target !== t.value) return;
		let n = Ac(t.value), r = n.includes(CSS.escape(e.animationName)), a = c.value === "mounted" ? "enter" : "leave";
		if (r && (u(`after-${a}`), l("ANIMATION_END"), !i.value)) {
			let e = t.value.style.animationFillMode;
			t.value.style.animationFillMode = "forwards", o = s?.setTimeout(() => {
				t.value?.style.animationFillMode === "forwards" && (t.value.style.animationFillMode = e);
			});
		}
		n === "none" && l("ANIMATION_END");
	}, f = (e) => {
		e.target === t.value && (r.value = Ac(t.value));
	}, p = V(t, (e, t) => {
		e ? (n.value = getComputedStyle(e), e.addEventListener("animationstart", f), e.addEventListener("animationcancel", d), e.addEventListener("animationend", d)) : (l("ANIMATION_END"), o !== void 0 && s?.clearTimeout(o), t?.removeEventListener("animationstart", f), t?.removeEventListener("animationcancel", d), t?.removeEventListener("animationend", d));
	}, { immediate: !0 }), m = V(c, () => {
		let e = Ac(t.value);
		r.value = c.value === "mounted" ? e : "none";
	});
	return zr(() => {
		p(), m(), t.value && (t.value.removeEventListener("animationstart", f), t.value.removeEventListener("animationcancel", d), t.value.removeEventListener("animationend", d)), o !== void 0 && s?.clearTimeout(o);
	}), { isPresent: $(() => ["mounted", "unmountSuspended"].includes(c.value)) };
}
function Ac(e) {
	return e && getComputedStyle(e).animationName || "none";
}
// node_modules/reka-ui/dist/Presence/Presence.js
var jc = /*#__PURE__*/ H({
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
		let { present: r, forceMount: i } = /* @__PURE__ */ cn(e), a = /* @__PURE__ */ F(), { isPresent: o } = kc(r, a);
		n({ present: o });
		let s = t.default({ present: o.value });
		s = qs(s || []);
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
			let t = Bs(e);
			return t?.hasAttribute === void 0 || (t?.hasAttribute("data-reka-popper-content-wrapper") ? a.value = t.firstElementChild : a.value = t), t;
		} }) : null;
	}
}), Mc = /*#__PURE__*/ H({
	name: "PrimitiveSlot",
	inheritAttrs: !1,
	setup(e, { attrs: t, slots: n }) {
		return () => {
			if (!n.default) return null;
			let e = qs(n.default()), r = e.findIndex((e) => e.type !== pa);
			if (r === -1) return e;
			let i = e[r];
			delete i.props?.ref;
			let a = i.props ? Na(t, i.props) : t, o = Da({
				...i,
				props: {}
			}, a);
			return e.length === 1 ? o : (e[r] = o, e);
		};
	}
}), Nc = [
	"area",
	"img",
	"input"
], Pc = /*#__PURE__*/ H({
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
		return typeof r == "string" && Nc.includes(r) ? () => no(r, t) : r === "template" ? () => no(Mc, t, { default: n.default }) : () => no(e.as, t, { default: n.default });
	}
}), Fc = "dismissableLayer.pointerDownOutside", Ic = "dismissableLayer.focusOutside";
function Lc(e) {
	if (typeof e != "object" || !e) return !1;
	let t = e.ownerDocument?.defaultView;
	return typeof Element < "u" && e instanceof Element || !!t && e instanceof t.Element;
}
function Rc(e, t) {
	if (!Lc(t)) return !1;
	if (e.contains(t)) return !0;
	let n = t.closest("[data-dismissable-layer]"), r = e.dataset.dismissableLayer === "" ? e : e.querySelector("[data-dismissable-layer]"), i = Array.from(e.ownerDocument.querySelectorAll("[data-dismissable-layer]"));
	return !!(n && (r === n || i.indexOf(r) < i.indexOf(n)));
}
function zc(e, t, n = !0) {
	let r = /* @__PURE__ */ F(!1), i = /* @__PURE__ */ F(() => {});
	return Xn((a) => {
		if (!Ts || !L(n)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			let a = n.target;
			if (t?.value && a) {
				if (Rc(t.value, a)) o.removeEventListener("click", i.value), r.value = !1;
				else {
					if (n.target && !r.value) {
						let t = { originalEvent: n };
						function r() {
							Ss(Fc, e, t);
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
function Bc(e, t, n = !0) {
	let r = /* @__PURE__ */ F(!1);
	return Xn((i) => {
		if (!Ts || !L(n)) return;
		let a = t?.value?.ownerDocument ?? globalThis.document, o = async (n) => {
			if (!t?.value) return;
			await jn(), await jn();
			let i = n.target;
			t.value && i && !Rc(t.value, i) && n.target && !r.value && Ss(Ic, e, { originalEvent: n });
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
var Vc = /*#__PURE__*/ Ut({
	layersRoot: /* @__PURE__ */ new Set(),
	layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
	branches: /* @__PURE__ */ new Set()
}), Hc = /* @__PURE__ */ H({
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
		let n = e, r = t, { forwardRef: i, currentElement: a } = pc(), o = $(() => a.value?.ownerDocument ?? globalThis.document), s = $(() => Vc.layersRoot), c = $(() => a.value ? Array.from(s.value).indexOf(a.value) : -1), l = $(() => Vc.layersWithOutsidePointerEventsDisabled.size > 0), u = $(() => {
			let e = Array.from(s.value), [t] = [...Vc.layersWithOutsidePointerEventsDisabled].slice(-1), n = e.indexOf(t);
			return c.value >= n;
		}), d = zc(async (e) => {
			let t = [...Vc.branches].some((t) => t?.contains(e.target));
			n.present && u.value && !t && (r("pointerDownOutside", e), r("interactOutside", e), await jn(), e.defaultPrevented || r("dismiss"));
		}, a, () => n.present), f = Bc((e) => {
			let t = [...Vc.branches].some((t) => t?.contains(e.target));
			n.present && !t && (r("focusOutside", e), r("interactOutside", e), e.defaultPrevented || r("dismiss"));
		}, a);
		return Ws("Escape", (e) => {
			n.present && c.value === s.value.size - 1 && (r("escapeKeyDown", e), e.defaultPrevented || r("dismiss"));
		}, { target: () => o.value?.defaultView ?? globalThis.window }), V([
			a,
			() => n.disableOutsidePointerEvents,
			() => n.present
		], ([e, t, n], r, i) => {
			if (e && n && t) {
				let t = e.ownerDocument;
				Zs(t, e), Vc.layersWithOutsidePointerEventsDisabled.add(e), i(() => {
					Vc.layersWithOutsidePointerEventsDisabled.delete(e), Qs(t, e);
				});
			}
		}, { immediate: !0 }), V([a, () => n.present], ([e, t], n, r) => {
			e && t && (s.value.add(e), r(() => {
				s.value.delete(e);
			}));
		}, { immediate: !0 }), Xn((e) => {
			e(() => {
				a.value && (s.value.delete(a.value), Vc.layersWithOutsidePointerEventsDisabled.delete(a.value));
			});
		}), (t, n) => (q(), Y(I(Pc), {
			ref: I(i),
			"as-child": e.asChild,
			as: e.as,
			"data-dismissable-layer": "",
			style: ue({ pointerEvents: l.value ? u.value ? "auto" : "none" : void 0 }),
			onFocusCapture: I(f).onFocusCapture,
			onBlurCapture: I(f).onBlurCapture,
			onPointerdownCapture: I(d).onPointerDownCapture
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
}), Uc = ws(() => /* @__PURE__ */ F([]));
function Wc() {
	let e = Uc();
	return {
		add(t) {
			let n = e.value[0];
			t !== n && n?.pause(), e.value = Gc(e.value, t), e.value.unshift(t);
		},
		remove(t) {
			e.value = Gc(e.value, t), e.value[0]?.resume();
		}
	};
}
function Gc(e, t) {
	let n = [...e], r = n.indexOf(t);
	return r !== -1 && n.splice(r, 1), n;
}
// node_modules/reka-ui/dist/FocusScope/utils.js
var Kc = "focusScope.autoFocusOnMount", qc = "focusScope.autoFocusOnUnmount", Jc = {
	bubbles: !1,
	cancelable: !0
};
function Yc(e, t) {
	let n = t;
	for (; n;) {
		if (e.contains(n)) return !0;
		n = n.getRootNode().host ?? null;
	}
	return !1;
}
function Xc(e, { select: t = !1 } = {}) {
	let n = xs();
	for (let r of e) if (nl(r, { select: t }), xs() !== n) return !0;
}
function Zc(e) {
	let t = Qc(e);
	return [$c(t, e), $c(t.reverse(), e)];
}
function Qc(e) {
	let t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, { acceptNode: (e) => {
		let t = e.tagName === "INPUT" && e.type === "hidden";
		return e.disabled || e.hidden || t ? NodeFilter.FILTER_SKIP : e.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
	} });
	for (; n.nextNode();) t.push(n.currentNode);
	return t.sort((e, t) => e.tabIndex === t.tabIndex ? 0 : e.tabIndex === 0 ? 1 : t.tabIndex === 0 ? -1 : e.tabIndex - t.tabIndex);
}
function $c(e, t) {
	for (let n of e) if (!el(n, { upTo: t })) return n;
}
function el(e, { upTo: t }) {
	if (getComputedStyle(e).visibility === "hidden") return !0;
	for (; e;) {
		if (t !== void 0 && e === t) return !1;
		if (getComputedStyle(e).display === "none") return !0;
		e = e.parentElement;
	}
	return !1;
}
function tl(e) {
	return e instanceof HTMLInputElement && "select" in e;
}
function nl(e, { select: t = !1 } = {}) {
	if (e && e.focus) {
		let n = xs();
		e.focus({ preventScroll: !0 }), e !== n && tl(e) && t && e.select();
	}
}
// node_modules/reka-ui/dist/FocusScope/FocusScope.js
var rl = /* @__PURE__ */ H({
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
		let n = e, r = t, { currentRef: i, currentElement: a } = pc(), o = /* @__PURE__ */ F(null), s = Wc(), c = /*#__PURE__*/ Ut({
			paused: !1,
			pause() {
				this.paused = !0;
			},
			resume() {
				this.paused = !1;
			}
		});
		Xn((e) => {
			if (!Ts) return;
			let t = a.value;
			if (!n.trapped) return;
			let r = t?.ownerDocument ?? document, i = t ? t.getRootNode() : r;
			function s(e) {
				if (c.paused || !t) return;
				let n = e.target;
				t.contains(n) ? o.value = n : nl(o.value, { select: !0 });
			}
			function l(e) {
				if (c.paused || !t) return;
				let n = e.relatedTarget;
				n !== null && (t.contains(n) || nl(o.value, { select: !0 }));
			}
			function u(e) {
				let n = o.value;
				if (n === null || !e.some((e) => e.removedNodes.length > 0)) return;
				let r = xs();
				r && t.contains(r) || t.contains(n) || nl(t);
			}
			function d(e) {
				if (c.paused || !t) return;
				let n = e.composedPath()[0];
				Yc(t, n) || nl(o.value, { select: !0 });
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
			let n = new CustomEvent(Kc, Jc), i = (e) => r("mountAutoFocus", e);
			e.addEventListener(Kc, i), e.dispatchEvent(n), e.removeEventListener(Kc, i), n.defaultPrevented || (Xc(Qc(e), { select: !0 }), xs() === t && nl(e));
		}
		Xn(async (e) => {
			let t = a.value;
			if (await jn(), !t) return;
			n.present !== !1 && s.add(c);
			let i = xs();
			!t.contains(i) && n.present !== !1 && l(t, i), e(() => {
				let e = new CustomEvent(qc, Jc), n = (e) => {
					r("unmountAutoFocus", e);
				};
				t.addEventListener(qc, n), t.dispatchEvent(e), t.setAttribute("data-focus-scope-unmounting", ""), setTimeout(() => {
					e.defaultPrevented || nl(i ?? document.body, { select: !0 }), t.removeEventListener(qc, n), s.remove(c), t.removeAttribute("data-focus-scope-unmounting");
				}, 0);
			});
		}), V(() => n.present, async (e, t) => {
			if (!Ts) return;
			if (e === !1 && t === !0) {
				s.remove(c);
				return;
			}
			if (e !== !0 || t !== !1) return;
			s.add(c), await jn();
			let n = a.value;
			if (!n) return;
			let r = xs();
			n.contains(r) || l(n, r);
		});
		function u(e) {
			if (!n.loop && !n.trapped || c.paused) return;
			let t = e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey, r = xs();
			if (t && r) {
				let t = e.currentTarget, [i, a] = Zc(t);
				i && a ? !e.shiftKey && r === a ? (e.preventDefault(), n.loop && nl(i, { select: !0 })) : e.shiftKey && r === i && (e.preventDefault(), n.loop && nl(a, { select: !0 })) : r === t && e.preventDefault();
			}
		}
		return (t, n) => (q(), Y(I(Pc), {
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
}), il = /* @__PURE__ */ H({
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
		let t = e, n = Js({}), r = $(() => t.to ?? n.teleportTo?.value ?? "body"), i = Hs();
		return (t, n) => I(i) || e.forceMount ? (q(), Y(fr, {
			key: 0,
			to: r.value,
			disabled: e.disabled,
			defer: e.defer
		}, [U(t.$slots, "default")], 8, [
			"to",
			"disabled",
			"defer"
		])) : ka("v-if", !0);
	}
}), [al, ol] = /*#__PURE__*/ bs("PopperRoot"), sl = /* @__PURE__ */ H({
	inheritAttrs: !1,
	__name: "PopperRoot",
	setup(e) {
		let t = /* @__PURE__ */ F();
		return ol({
			anchor: t,
			onAnchorChange: (e) => t.value = e
		}), (e, t) => U(e.$slots, "default");
	}
}), cl = /* @__PURE__ */ H({
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
		let t = e, { forwardRef: n, currentElement: r } = pc(), i = al();
		return Zn(() => {
			i.onAnchorChange(t.reference ?? r.value);
		}), (t, r) => (q(), Y(I(Pc), {
			ref: I(n),
			as: e.as,
			"as-child": e.asChild
		}, {
			default: B(() => [U(t.$slots, "default")]),
			_: 3
		}, 8, ["as", "as-child"]));
	}
});
// node_modules/reka-ui/dist/Popper/utils.js
function ll(e) {
	return e !== null;
}
function ul(e) {
	return {
		name: "transformOrigin",
		options: e,
		fn(t) {
			let { placement: n, rects: r, middlewareData: i } = t, a = i.arrow?.centerOffset !== 0, o = a ? 0 : e.arrowWidth, s = a ? 0 : e.arrowHeight, [c, l] = dl(n), u = {
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
function dl(e) {
	let [t, n = "center"] = e.split("-");
	return [t, n];
}
// node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs
var fl = [
	"top",
	"right",
	"bottom",
	"left"
], pl = Math.min, ml = Math.max, hl = Math.round, gl = Math.floor, _l = (e) => ({
	x: e,
	y: e
}), vl = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function yl(e, t, n) {
	return ml(e, pl(t, n));
}
function bl(e, t) {
	return typeof e == "function" ? e(t) : e;
}
function xl(e) {
	return e.split("-")[0];
}
function Sl(e) {
	return e.split("-")[1];
}
function Cl(e) {
	return e === "x" ? "y" : "x";
}
function wl(e) {
	return e === "y" ? "height" : "width";
}
function Tl(e) {
	let t = e[0];
	return t === "t" || t === "b" ? "y" : "x";
}
function El(e) {
	return Cl(Tl(e));
}
function Dl(e, t, n) {
	n === void 0 && (n = !1);
	let r = Sl(e), i = El(e), a = wl(i), o = i === "x" ? r === (n ? "end" : "start") ? "right" : "left" : r === "start" ? "bottom" : "top";
	return t.reference[a] > t.floating[a] && (o = Il(o)), [o, Il(o)];
}
function Ol(e) {
	let t = Il(e);
	return [
		kl(e),
		t,
		kl(t)
	];
}
function kl(e) {
	return e.includes("start") ? e.replace("start", "end") : e.replace("end", "start");
}
var Al = ["left", "right"], jl = ["right", "left"], Ml = ["top", "bottom"], Nl = ["bottom", "top"];
function Pl(e, t, n) {
	switch (e) {
		case "top":
		case "bottom": return n ? t ? jl : Al : t ? Al : jl;
		case "left":
		case "right": return t ? Ml : Nl;
		default: return [];
	}
}
function Fl(e, t, n, r) {
	let i = Sl(e), a = Pl(xl(e), n === "start", r);
	return i && (a = a.map((e) => e + "-" + i), t && (a = a.concat(a.map(kl)))), a;
}
function Il(e) {
	let t = xl(e);
	return vl[t] + e.slice(t.length);
}
function Ll(e) {
	return {
		top: e.top ?? 0,
		right: e.right ?? 0,
		bottom: e.bottom ?? 0,
		left: e.left ?? 0
	};
}
function Rl(e) {
	return typeof e == "number" ? {
		top: e,
		right: e,
		bottom: e,
		left: e
	} : Ll(e);
}
function zl(e) {
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
function Bl(e, t, n) {
	let { reference: r, floating: i } = e, a = Tl(t), o = El(t), s = wl(o), c = xl(t), l = a === "y", u = r.x + r.width / 2 - i.width / 2, d = r.y + r.height / 2 - i.height / 2, f = r[s] / 2 - i[s] / 2, p;
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
	let m = Sl(t);
	return m && (p[o] += f * (m === "end" ? 1 : -1) * (n && l ? -1 : 1)), p;
}
async function Vl(e, t) {
	t === void 0 && (t = {});
	let { x: n, y: r, platform: i, rects: a, elements: o, strategy: s } = e, { boundary: c = "clippingAncestors", rootBoundary: l = "viewport", elementContext: u = "floating", altBoundary: d = !1, padding: f = 0 } = bl(t, e), p = Rl(f), m = o[d ? u === "floating" ? "reference" : "floating" : u], h = zl(await i.getClippingRect({
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
	}, y = zl(i.convertOffsetParentRelativeRectToViewportRelativeRect ? await i.convertOffsetParentRelativeRectToViewportRelativeRect({
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
var Hl = 50, Ul = async (e, t, n) => {
	let { placement: r = "bottom", strategy: i = "absolute", middleware: a = [], platform: o } = n, s = o.detectOverflow ? o : {
		...o,
		detectOverflow: Vl
	}, c = await (o.isRTL == null ? void 0 : o.isRTL(t)), l = await o.getElementRects({
		reference: e,
		floating: t,
		strategy: i
	}), { x: u, y: d } = Bl(l, r, c), f = r, p = 0, m = {};
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
		}, x && p < Hl && (p++, typeof x == "object" && (x.placement && (f = x.placement), x.rects && (l = x.rects === !0 ? await o.getElementRects({
			reference: e,
			floating: t,
			strategy: i
		}) : x.rects), {x: u, y: d} = Bl(l, f, c)), n = -1);
	}
	return {
		x: u,
		y: d,
		placement: f,
		strategy: i,
		middlewareData: m
	};
}, Wl = (e) => ({
	name: "arrow",
	options: e,
	async fn(t) {
		let { x: n, y: r, placement: i, rects: a, platform: o, elements: s, middlewareData: c } = t, { element: l, padding: u = 0 } = bl(e, t) || {};
		if (l == null) return {};
		let d = Rl(u), f = {
			x: n,
			y: r
		}, p = El(i), m = wl(p), h = await o.getDimensions(l), g = p === "y", _ = g ? "top" : "left", v = g ? "bottom" : "right", y = g ? "clientHeight" : "clientWidth", b = a.reference[m] + a.reference[p] - f[p] - a.floating[m], x = f[p] - a.reference[p], S = await (o.getOffsetParent == null ? void 0 : o.getOffsetParent(l)), C = S ? S[y] : 0;
		C && await (o.isElement == null ? void 0 : o.isElement(S)) || (C = s.floating[y] || a.floating[m]);
		let w = b / 2 - x / 2, T = C / 2 - h[m] / 2 - 1, ee = pl(d[_], T), te = pl(d[v], T), E = C - h[m] - te, ne = C / 2 - h[m] / 2 + w, D = yl(ee, ne, E), re = !c.arrow && Sl(i) != null && ne !== D && a.reference[m] / 2 - (ne < ee ? ee : te) - h[m] / 2 < 0, ie = re ? ne < ee ? ne - ee : ne - E : 0;
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
}), Gl = function(e) {
	return e === void 0 && (e = {}), {
		name: "flip",
		options: e,
		async fn(t) {
			var n;
			let { placement: r, middlewareData: i, rects: a, initialPlacement: o, platform: s, elements: c } = t, { mainAxis: l = !0, crossAxis: u = !0, fallbackPlacements: d, fallbackStrategy: f = "bestFit", fallbackAxisSideDirection: p = "none", flipAlignment: m = !0, ...h } = bl(e, t);
			if ((n = i.arrow) != null && n.alignmentOffset) return {};
			let g = xl(r), _ = Tl(o), v = xl(o) === o, y = await (s.isRTL == null ? void 0 : s.isRTL(c.floating)), b = d || (v || !m ? [Il(o)] : Ol(o)), x = p !== "none";
			!d && x && b.push(...Fl(o, m, p, y));
			let S = [o, ...b], C = await s.detectOverflow(t, h), w = [], T = i.flip?.overflows || [];
			if (l && w.push(C[g]), u) {
				let e = Dl(r, a, y);
				w.push(C[e[0]], C[e[1]]);
			}
			if (T = [...T, {
				placement: r,
				overflows: w
			}], !w.every((e) => e <= 0)) {
				let e = (i.flip?.index || 0) + 1, t = S[e];
				if (t && (u !== "alignment" || _ === Tl(t) || T.every((e) => Tl(e.placement) !== _ || e.overflows[0] > 0))) return {
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
								let t = Tl(e.placement);
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
function Kl(e, t) {
	return {
		top: e.top - t.height,
		right: e.right - t.width,
		bottom: e.bottom - t.height,
		left: e.left - t.width
	};
}
function ql(e) {
	return fl.some((t) => e[t] >= 0);
}
var Jl = function(e) {
	return e === void 0 && (e = {}), {
		name: "hide",
		options: e,
		async fn(t) {
			let { rects: n, platform: r } = t, { strategy: i = "referenceHidden", ...a } = bl(e, t);
			switch (i) {
				case "referenceHidden": {
					let e = Kl(await r.detectOverflow(t, {
						...a,
						elementContext: "reference"
					}), n.reference);
					return { data: {
						referenceHiddenOffsets: e,
						referenceHidden: ql(e)
					} };
				}
				case "escaped": {
					let e = Kl(await r.detectOverflow(t, {
						...a,
						altBoundary: !0
					}), n.floating);
					return { data: {
						escapedOffsets: e,
						escaped: ql(e)
					} };
				}
				default: return {};
			}
		}
	};
}, Yl = /*#__PURE__*/ new Set(["left", "top"]);
async function Xl(e, t) {
	let { placement: n, platform: r, elements: i } = e, a = await (r.isRTL == null ? void 0 : r.isRTL(i.floating)), o = xl(n), s = Sl(n), c = Tl(n) === "y", l = Yl.has(o) ? -1 : 1, u = a && c ? -1 : 1, d = bl(t, e), { mainAxis: f, crossAxis: p, alignmentAxis: m } = typeof d == "number" ? {
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
var Zl = function(e) {
	return e === void 0 && (e = 0), {
		name: "offset",
		options: e,
		async fn(t) {
			var n;
			let { x: r, y: i, placement: a, middlewareData: o } = t, s = await Xl(t, e);
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
}, Ql = function(e) {
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
			} }, ...l } = bl(e, t), u = {
				x: n,
				y: r
			}, d = await a.detectOverflow(t, l), f = Tl(i), p = Cl(f), m = u[p], h = u[f], g = (e, t) => yl(t + d[e === "y" ? "top" : "left"], t, t - d[e === "y" ? "bottom" : "right"]);
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
}, $l = function(e) {
	return e === void 0 && (e = {}), {
		options: e,
		fn(t) {
			let { x: n, y: r, placement: i, rects: a, middlewareData: o } = t, { offset: s = 0, mainAxis: c = !0, crossAxis: l = !0 } = bl(e, t), u = {
				x: n,
				y: r
			}, d = Tl(i), f = Cl(d), p = u[f], m = u[d], h = bl(s, t), g = typeof h == "number" ? {
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
				let e = f === "y" ? "width" : "height", t = Yl.has(xl(i)), n = a.reference[d] - a.floating[e] + (t && o.offset?.[d] || 0) + (t ? 0 : g.crossAxis), r = a.reference[d] + a.reference[e] + (t ? 0 : o.offset?.[d] || 0) - (t ? g.crossAxis : 0);
				m < n ? m = n : m > r && (m = r);
			}
			return {
				[f]: p,
				[d]: m
			};
		}
	};
}, eu = function(e) {
	return e === void 0 && (e = {}), {
		name: "size",
		options: e,
		async fn(t) {
			let { placement: n, rects: r, platform: i, elements: a } = t, { apply: o = () => {}, ...s } = bl(e, t), c = await i.detectOverflow(t, s), l = xl(n), u = Sl(n), d = Tl(n) === "y", { width: f, height: p } = r.floating, m, h;
			l === "top" || l === "bottom" ? (m = l, h = u === (await (i.isRTL == null ? void 0 : i.isRTL(a.floating)) ? "start" : "end") ? "left" : "right") : (h = l, m = u === "end" ? "top" : "bottom");
			let g = p - c.top - c.bottom, _ = f - c.left - c.right, v = pl(p - c[m], g), y = pl(f - c[h], _), b = t.middlewareData.shift, x = !b, S = v, C = y;
			b != null && b.enabled.x && (C = _), b != null && b.enabled.y && (S = g), x && !u && (d ? C = f - 2 * ml(c.left, c.right) : S = p - 2 * ml(c.top, c.bottom)), await o({
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
function tu() {
	return typeof window < "u";
}
function nu(e) {
	return au(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function ru(e) {
	var t;
	return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function iu(e) {
	return ((au(e) ? e.ownerDocument : e.document) || window.document)?.documentElement;
}
function au(e) {
	return tu() ? e instanceof Node || e instanceof ru(e).Node : !1;
}
function ou(e) {
	return tu() ? e instanceof Element || e instanceof ru(e).Element : !1;
}
function su(e) {
	return tu() ? e instanceof HTMLElement || e instanceof ru(e).HTMLElement : !1;
}
function cu(e) {
	return !tu() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof ru(e).ShadowRoot;
}
function lu(e) {
	let { overflow: t, overflowX: n, overflowY: r, display: i } = bu(e);
	return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && i !== "inline" && i !== "contents";
}
function uu(e) {
	return /^(table|td|th)$/.test(nu(e));
}
function du(e) {
	try {
		if (e.matches(":popover-open")) return !0;
	} catch {}
	try {
		return e.matches(":modal");
	} catch {
		return !1;
	}
}
var fu = /transform|translate|scale|rotate|perspective|filter/, pu = /paint|layout|strict|content/, mu = (e) => !!e && e !== "none", hu;
function gu(e) {
	let t = ou(e) ? bu(e) : e;
	return mu(t.transform) || mu(t.translate) || mu(t.scale) || mu(t.rotate) || mu(t.perspective) || !vu() && (mu(t.backdropFilter) || mu(t.filter)) || fu.test(t.willChange || "") || pu.test(t.contain || "");
}
function _u(e) {
	let t = Su(e);
	for (; su(t) && !yu(t);) {
		if (gu(t)) return t;
		if (du(t)) return null;
		t = Su(t);
	}
	return null;
}
function vu() {
	return hu ??= typeof CSS < "u" && CSS.supports && CSS.supports("-webkit-backdrop-filter", "none"), hu;
}
function yu(e) {
	return /^(html|body|#document)$/.test(nu(e));
}
function bu(e) {
	return ru(e).getComputedStyle(e);
}
function xu(e) {
	return ou(e) ? {
		scrollLeft: e.scrollLeft,
		scrollTop: e.scrollTop
	} : {
		scrollLeft: e.scrollX,
		scrollTop: e.scrollY
	};
}
function Su(e) {
	if (nu(e) === "html") return e;
	let t = e.assignedSlot || e.parentNode || cu(e) && e.host || iu(e);
	return cu(t) ? t.host : t;
}
function Cu(e) {
	let t = Su(e);
	return yu(t) ? (e.ownerDocument || e).body : su(t) && lu(t) ? t : Cu(t);
}
function wu(e, t, n) {
	t === void 0 && (t = []), n === void 0 && (n = !0);
	let r = Cu(e), i = r === e.ownerDocument?.body, a = ru(r);
	if (i) {
		let e = Tu(a);
		return t.concat(a, a.visualViewport || [], lu(r) ? r : [], e && n ? wu(e) : []);
	}
	return t.concat(r, wu(r, [], n));
}
function Tu(e) {
	return e.parent && Object.getPrototypeOf(e.parent) ? e.frameElement : null;
}
// node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs
function Eu(e) {
	let t = bu(e), n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0, i = su(e), a = i ? e.offsetWidth : n, o = i ? e.offsetHeight : r, s = hl(n) !== a || hl(r) !== o;
	return s && (n = a, r = o), {
		width: n,
		height: r,
		$: s
	};
}
function Du(e) {
	return ou(e) ? e : e.contextElement;
}
function Ou(e) {
	let t = Du(e);
	if (!su(t)) return _l(1);
	let n = t.getBoundingClientRect(), { width: r, height: i, $: a } = Eu(t), o = (a ? hl(n.width) : n.width) / r, s = (a ? hl(n.height) : n.height) / i;
	return o && Number.isFinite(o) || (o = 1), s && Number.isFinite(s) || (s = 1), {
		x: o,
		y: s
	};
}
var ku = /*#__PURE__*/ _l(0);
function Au(e) {
	let t = ru(e);
	return !vu() || !t.visualViewport ? ku : {
		x: t.visualViewport.offsetLeft,
		y: t.visualViewport.offsetTop
	};
}
function ju(e, t, n) {
	return t === void 0 && (t = !1), !!n && t && n === ru(e);
}
function Mu(e, t, n, r) {
	t === void 0 && (t = !1), n === void 0 && (n = !1);
	let i = e.getBoundingClientRect(), a = Du(e), o = _l(1);
	t && (r ? ou(r) && (o = Ou(r)) : o = Ou(e));
	let s = ju(a, n, r) ? Au(a) : _l(0), c = (i.left + s.x) / o.x, l = (i.top + s.y) / o.y, u = i.width / o.x, d = i.height / o.y;
	if (a && r) {
		let e = ru(a), t = ou(r) ? ru(r) : r, n = e, i = Tu(n);
		for (; i && t !== n;) {
			let e = Ou(i), t = i.getBoundingClientRect(), r = bu(i), a = t.left + (i.clientLeft + parseFloat(r.paddingLeft)) * e.x, o = t.top + (i.clientTop + parseFloat(r.paddingTop)) * e.y;
			c *= e.x, l *= e.y, u *= e.x, d *= e.y, c += a, l += o, n = ru(i), i = Tu(n);
		}
	}
	return zl({
		width: u,
		height: d,
		x: c,
		y: l
	});
}
function Nu(e, t) {
	let n = xu(e).scrollLeft;
	return t ? t.left + n : Mu(iu(e)).left + n;
}
function Pu(e, t) {
	let n = e.getBoundingClientRect();
	return {
		x: n.left + t.scrollLeft - Nu(e, n),
		y: n.top + t.scrollTop
	};
}
function Fu(e) {
	let { elements: t, rect: n, offsetParent: r, strategy: i } = e, a = i === "fixed", o = iu(r), s = t ? du(t.floating) : !1;
	if (r === o || s && a) return n;
	let c = {
		scrollLeft: 0,
		scrollTop: 0
	}, l = _l(1), u = _l(0), d = su(r);
	if ((d || !a) && ((nu(r) !== "body" || lu(o)) && (c = xu(r)), d)) {
		let e = Mu(r);
		l = Ou(r), u.x = e.x + r.clientLeft, u.y = e.y + r.clientTop;
	}
	let f = o && !d && !a ? Pu(o, c) : _l(0);
	return {
		width: n.width * l.x,
		height: n.height * l.y,
		x: n.x * l.x - c.scrollLeft * l.x + u.x + f.x,
		y: n.y * l.y - c.scrollTop * l.y + u.y + f.y
	};
}
function Iu(e) {
	return e.getClientRects ? Array.from(e.getClientRects()) : [];
}
function Lu(e) {
	let t = xu(e), n = e.ownerDocument.body, r = ml(e.scrollWidth, e.clientWidth, n.scrollWidth, n.clientWidth), i = ml(e.scrollHeight, e.clientHeight, n.scrollHeight, n.clientHeight), a = -t.scrollLeft + Nu(e), o = -t.scrollTop;
	return bu(n).direction === "rtl" && (a += ml(e.clientWidth, n.clientWidth) - r), {
		width: r,
		height: i,
		x: a,
		y: o
	};
}
var Ru = 25;
function zu(e, t, n) {
	n === void 0 && (n = "viewport");
	let r = n === "layoutViewport", i = ru(e), a = iu(e), o = i.visualViewport, s = a.clientWidth, c = a.clientHeight, l = 0, u = 0;
	if (o) {
		let e = !vu() || t === "fixed";
		r ? e || (l = -o.offsetLeft, u = -o.offsetTop) : (s = o.width, c = o.height, e && (l = o.offsetLeft, u = o.offsetTop));
	}
	if (Nu(a) <= 0) {
		let e = a.ownerDocument, t = e.body, n = getComputedStyle(t), r = e.compatMode === "CSS1Compat" && parseFloat(n.marginLeft) + parseFloat(n.marginRight) || 0, i = Math.abs(a.clientWidth - t.clientWidth - r), o = getComputedStyle(a).scrollbarGutter === "stable both-edges" ? i / 2 : i;
		o <= Ru && (s -= o);
	}
	return {
		width: s,
		height: c,
		x: l,
		y: u
	};
}
function Bu(e, t) {
	let n = Mu(e, !0, t === "fixed"), r = n.top + e.clientTop, i = n.left + e.clientLeft, a = Ou(e);
	return {
		width: e.clientWidth * a.x,
		height: e.clientHeight * a.y,
		x: i * a.x,
		y: r * a.y
	};
}
function Vu(e, t, n) {
	let r;
	if (t === "viewport" || t === "layoutViewport") r = zu(e, n, t);
	else if (t === "document") r = Lu(iu(e));
	else if (ou(t)) r = Bu(t, n);
	else {
		let n = Au(e);
		r = {
			x: t.x - n.x,
			y: t.y - n.y,
			width: t.width,
			height: t.height
		};
	}
	return zl(r);
}
function Hu(e, t) {
	let n = t.get(e);
	if (n) return n;
	let r = wu(e, [], !1).filter((e) => ou(e) && nu(e) !== "body"), i = null, a = bu(e).position === "fixed", o = a ? Su(e) : e;
	for (; ou(o) && !yu(o);) {
		let e = bu(o), t = gu(o), n = i ? i.position : a ? "fixed" : "";
		!t && (n === "fixed" || n === "absolute" && e.position === "static") ? r = r.filter((e) => e !== o) : i = e, o = Su(o);
	}
	return t.set(e, r), r;
}
function Uu(e) {
	let { element: t, boundary: n, rootBoundary: r, strategy: i } = e, a = [...n === "clippingAncestors" ? du(t) ? [] : Hu(t, this._c) : [].concat(n), r], o = Vu(t, a[0], i), s = o.top, c = o.right, l = o.bottom, u = o.left;
	for (let e = 1; e < a.length; e++) {
		let n = Vu(t, a[e], i);
		s = ml(n.top, s), c = pl(n.right, c), l = pl(n.bottom, l), u = ml(n.left, u);
	}
	return {
		width: c - u,
		height: l - s,
		x: u,
		y: s
	};
}
function Wu(e) {
	let { width: t, height: n } = Eu(e);
	return {
		width: t,
		height: n
	};
}
function Gu(e, t, n) {
	let r = su(t), i = iu(t), a = n === "fixed", o = Mu(e, !0, a, t), s = {
		scrollLeft: 0,
		scrollTop: 0
	}, c = _l(0);
	if ((r || !a) && ((nu(t) !== "body" || lu(i)) && (s = xu(t)), r)) {
		let e = Mu(t, !0, a, t);
		c.x = e.x + t.clientLeft, c.y = e.y + t.clientTop;
	}
	!r && i && (c.x = Nu(i));
	let l = i && !r && !a ? Pu(i, s) : _l(0);
	return {
		x: o.left + s.scrollLeft - c.x - l.x,
		y: o.top + s.scrollTop - c.y - l.y,
		width: o.width,
		height: o.height
	};
}
function Ku(e) {
	return bu(e).position === "static";
}
function qu(e, t) {
	if (!su(e) || bu(e).position === "fixed") return null;
	if (t) return t(e);
	let n = e.offsetParent;
	return iu(e) === n && (n = n.ownerDocument.body), n;
}
function Ju(e, t) {
	let n = ru(e);
	if (du(e)) return n;
	if (!su(e)) {
		let t = Su(e);
		for (; t && !yu(t);) {
			if (ou(t) && !Ku(t)) return t;
			t = Su(t);
		}
		return n;
	}
	let r = qu(e, t);
	for (; r && uu(r) && Ku(r);) r = qu(r, t);
	return r && yu(r) && Ku(r) && !gu(r) ? n : r || _u(e) || n;
}
var Yu = async function(e) {
	let t = this.getOffsetParent || Ju, n = this.getDimensions, r = await n(e.floating);
	return {
		reference: Gu(e.reference, await t(e.floating), e.strategy),
		floating: {
			x: 0,
			y: 0,
			width: r.width,
			height: r.height
		}
	};
};
function Xu(e) {
	return bu(e).direction === "rtl";
}
var Zu = {
	convertOffsetParentRelativeRectToViewportRelativeRect: Fu,
	getDocumentElement: iu,
	getClippingRect: Uu,
	getOffsetParent: Ju,
	getElementRects: Yu,
	getClientRects: Iu,
	getDimensions: Wu,
	getScale: Ou,
	isElement: ou,
	isRTL: Xu
};
function Qu(e, t) {
	return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function $u(e, t, n) {
	let r = null, i, a = iu(e);
	function o() {
		var e;
		clearTimeout(i), (e = r) == null || e.disconnect(), r = null;
	}
	function s(n, c) {
		n === void 0 && (n = !1), c === void 0 && (c = 1), o();
		let l = e.getBoundingClientRect(), { left: u, top: d, width: f, height: p } = l;
		if (n || t(), !f || !p) return;
		let m = gl(d), h = gl(a.clientWidth - (u + f)), g = gl(a.clientHeight - (d + p)), _ = gl(u), v = {
			rootMargin: -m + "px " + -h + "px " + -g + "px " + -_ + "px",
			threshold: ml(0, pl(1, c)) || 1
		}, y = !0;
		function b(t) {
			let n = t[0].intersectionRatio;
			if (!Qu(l, e.getBoundingClientRect())) return s();
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
	let c = ru(e), l = () => s(n);
	return c.addEventListener("resize", l), s(!0), () => {
		c.removeEventListener("resize", l), o();
	};
}
function ed(e, t, n, r) {
	r === void 0 && (r = {});
	let { ancestorScroll: i = !0, ancestorResize: a = !0, elementResize: o = typeof ResizeObserver == "function", layoutShift: s = typeof IntersectionObserver == "function", animationFrame: c = !1 } = r, l = Du(e), u = i || a ? [...l ? wu(l) : [], ...t ? wu(t) : []] : [];
	u.forEach((e) => {
		i && e.addEventListener("scroll", n), a && e.addEventListener("resize", n);
	});
	let d = l && s ? $u(l, n, a) : null, f = -1, p = null;
	o && (p = new ResizeObserver((e) => {
		let [r] = e;
		r && r.target === l && p && t && (p.unobserve(t), cancelAnimationFrame(f), f = requestAnimationFrame(() => {
			var e;
			(e = p) == null || e.observe(t);
		})), n();
	}), l && !c && p.observe(l), t && p.observe(t));
	let m, h = c ? Mu(e) : null;
	c && g();
	function g() {
		let t = Mu(e);
		h && !Qu(h, t) && n(), h = t, m = requestAnimationFrame(g);
	}
	return n(), () => {
		var e;
		u.forEach((e) => {
			i && e.removeEventListener("scroll", n), a && e.removeEventListener("resize", n);
		}), d?.(), (e = p) == null || e.disconnect(), p = null, c && cancelAnimationFrame(m);
	};
}
var td = Zl, nd = Ql, rd = Gl, id = eu, ad = Jl, od = Wl, sd = $l, cd = (e, t, n) => {
	let r = /* @__PURE__ */ new Map(), i = n ?? {}, a = {
		...Zu,
		...i.platform,
		_c: r
	};
	return Ul(e, t, {
		...i,
		platform: a
	});
};
// node_modules/@floating-ui/vue/dist/floating-ui.vue.mjs
function ld(e) {
	return typeof e == "object" && !!e && "$el" in e;
}
function ud(e) {
	if (ld(e)) {
		let t = e.$el;
		return au(t) && nu(t) === "#comment" ? null : t;
	}
	return e;
}
function dd(e) {
	return {
		name: "arrow",
		options: e,
		fn(t) {
			let n = ud(L(e.element));
			return n == null ? {} : od({
				element: n,
				padding: e.padding
			}).fn(t);
		}
	};
}
function fd(e) {
	return typeof window > "u" ? 1 : (e.ownerDocument.defaultView || window).devicePixelRatio || 1;
}
function pd(e, t) {
	let n = fd(e);
	return Math.round(t * n) / n;
}
function md(e, t, n) {
	n === void 0 && (n = {});
	let r = n.whileElementsMounted, i = $(() => L(n.open) ?? !0), a = $(() => L(n.middleware)), o = $(() => L(n.placement) ?? "bottom"), s = $(() => L(n.strategy) ?? "absolute"), c = $(() => L(n.transform) ?? !0), l = $(() => ud(e.value)), u = $(() => ud(t.value)), d = /* @__PURE__ */ F(0), f = /* @__PURE__ */ F(0), p = /* @__PURE__ */ F(s.value), m = /* @__PURE__ */ F(o.value), h = /* @__PURE__ */ tn({}), g = /* @__PURE__ */ F(!1), _ = $(() => {
		let e = {
			position: p.value,
			left: "0",
			top: "0"
		};
		if (!u.value) return e;
		let t = pd(u.value, d.value), n = pd(u.value, f.value);
		return c.value ? {
			...e,
			transform: "translate(" + t + "px, " + n + "px)",
			...fd(u.value) >= 1.5 && { willChange: "transform" }
		} : {
			position: p.value,
			left: t + "px",
			top: n + "px"
		};
	}), v;
	function y() {
		if (l.value == null || u.value == null) return;
		let e = i.value;
		cd(l.value, u.value, {
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
	], y, { flush: "sync" }), V([l, u], x, { flush: "sync" }), V(i, S, { flush: "sync" }), Ae() && je(b), {
		x: /* @__PURE__ */ Kt(d),
		y: /* @__PURE__ */ Kt(f),
		strategy: /* @__PURE__ */ Kt(p),
		placement: /* @__PURE__ */ Kt(m),
		middlewareData: /* @__PURE__ */ Kt(h),
		isPositioned: /* @__PURE__ */ Kt(g),
		floatingStyles: _,
		update: y
	};
}
// node_modules/reka-ui/dist/Popper/PopperContent.js
var hd = ["dir"], gd = {
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
}, [_d, vd] = /*#__PURE__*/ bs("PopperContent"), yd = /* @__PURE__ */ H({
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
	}, { ...gd }),
	emits: ["placed"],
	setup(e, { emit: t }) {
		let n = e, r = t, i = al(), { forwardRef: a, currentElement: o } = pc(), s = cc($(() => n.dir)), c = /* @__PURE__ */ F(), l = /* @__PURE__ */ F(), { width: u, height: d } = Dc(l), f = $(() => n.side + (n.align === "center" ? "" : `-${n.align}`)), p = $(() => typeof n.collisionPadding == "number" ? n.collisionPadding : {
			top: 0,
			right: 0,
			bottom: 0,
			left: 0,
			...n.collisionPadding
		}), m = $(() => Array.isArray(n.collisionBoundary) ? n.collisionBoundary : [n.collisionBoundary]), h = $(() => ({
			padding: p.value,
			boundary: m.value.filter(ll),
			altBoundary: m.value.length > 0
		})), g = $(() => ({
			mainAxis: n.sideFlip,
			crossAxis: n.alignFlip
		})), _ = $(() => [
			td({
				mainAxis: n.sideOffset + d.value,
				alignmentAxis: n.alignOffset
			}),
			n.prioritizePosition && n.avoidCollisions && rd({
				...h.value,
				...g.value
			}),
			n.avoidCollisions && nd({
				mainAxis: !0,
				crossAxis: !!n.prioritizePosition,
				limiter: n.sticky === "partial" ? sd() : void 0,
				...h.value
			}),
			!n.prioritizePosition && n.avoidCollisions && rd({
				...h.value,
				...g.value
			}),
			id({
				...h.value,
				apply: ({ elements: e, rects: t, availableWidth: n, availableHeight: r }) => {
					let { width: i, height: a } = t.reference, o = e.floating.style;
					o.setProperty("--reka-popper-available-width", `${n}px`), o.setProperty("--reka-popper-available-height", `${r}px`), o.setProperty("--reka-popper-anchor-width", `${i}px`), o.setProperty("--reka-popper-anchor-height", `${a}px`);
				}
			}),
			l.value && dd({
				element: l.value,
				padding: n.arrowPadding
			}),
			ul({
				arrowWidth: u.value,
				arrowHeight: d.value,
				dir: s.value
			}),
			n.hideWhenDetached && ad({
				strategy: "referenceHidden",
				...h.value
			})
		]), { floatingStyles: v, placement: y, isPositioned: b, middlewareData: x, update: S } = md($(() => n.reference ?? i.anchor.value), c, {
			strategy: n.positionStrategy,
			placement: f,
			whileElementsMounted: (...e) => ed(...e, {
				layoutShift: !n.disableUpdateOnLayoutShift,
				animationFrame: n.updatePositionStrategy === "always"
			}),
			middleware: _
		}), C = $(() => dl(y.value)[0]), w = $(() => dl(y.value)[1]);
		Zn(() => {
			b.value && r("placed");
		});
		let T = $(() => {
			let e = x.value.arrow?.centerOffset !== 0;
			return n.hideShiftedArrow && e;
		}), ee = /* @__PURE__ */ F("");
		return Xn(() => {
			o.value && (ee.value = window.getComputedStyle(o.value).zIndex);
		}), vd({
			placedSide: C,
			onArrowChange: (e) => l.value = e,
			arrowX: $(() => x.value.arrow?.x ?? 0),
			arrowY: $(() => x.value.arrow?.y ?? 0),
			shouldHideArrow: T
		}), (e, t) => (q(), J("div", {
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
		], () => (q(), Y(I(Pc), Na({
			key: 0,
			ref: I(a)
		}, e.$attrs, {
			"as-child": n.asChild,
			as: n.as,
			"data-side": C.value,
			"data-align": w.value,
			style: { animation: I(b) ? void 0 : "none" }
		}), {
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"style"
		])), t, 0) : (q(), Y(I(Pc), Na({
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
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"dir",
			"style"
		]))], 12, hd));
	}
}), [bd, xd] = /*#__PURE__*/ bs("PopoverRoot"), Sd = /* @__PURE__ */ H({
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
		let n = e, r = t, { modal: i } = /* @__PURE__ */ cn(n), a = Ks(n, "open", r, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		});
		return xd({
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
		}), (e, t) => (q(), Y(I(sl), null, {
			default: B(() => [U(e.$slots, "default", {
				open: I(a),
				close: () => a.value = !1
			})]),
			_: 3
		}));
	}
}), Cd = /* @__PURE__ */ H({
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
		pc();
		let n = bd();
		return (r, i) => (q(), Y(I(Pc), {
			type: e.as === "button" ? "button" : void 0,
			as: e.as,
			"as-child": t.asChild,
			onClick: i[0] ||= (e) => I(n).onOpenChange(!1)
		}, {
			default: B(() => [U(r.$slots, "default")]),
			_: 3
		}, 8, [
			"type",
			"as",
			"as-child"
		]));
	}
}), wd = /* @__PURE__ */ H({
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
		let n = e, r = t, i = mc(Is(n, "trapFocus", "disableOutsidePointerEvents")), { forwardRef: a } = pc(), o = bd();
		return dc(), (t, n) => (q(), Y(I(rl), {
			"as-child": "",
			loop: "",
			trapped: e.trapFocus,
			onMountAutoFocus: n[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: n[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: B(() => [Z(I(Hc), {
				"as-child": "",
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				onPointerDownOutside: n[0] ||= (e) => r("pointerDownOutside", e),
				onInteractOutside: n[1] ||= (e) => r("interactOutside", e),
				onEscapeKeyDown: n[2] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: n[3] ||= (e) => r("focusOutside", e),
				onDismiss: n[4] ||= (e) => I(o).onOpenChange(!1)
			}, {
				default: B(() => [Z(I(yd), Na(I(i), {
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
}), Td = /* @__PURE__ */ H({
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
		let n = e, r = t, i = bd(), a = /* @__PURE__ */ F(!1);
		ac(!0);
		let o = hc(n, r), { forwardRef: s, currentElement: c } = pc();
		return Tc(c), (e, t) => (q(), Y(wd, Na(I(o), {
			ref: I(s),
			"trap-focus": I(i).open.value,
			"disable-outside-pointer-events": "",
			onCloseAutoFocus: t[0] ||= ss((e) => {
				r("closeAutoFocus", e), a.value || I(i).triggerElement.value?.focus();
			}, ["prevent"]),
			onPointerDownOutside: t[1] ||= (e) => {
				r("pointerDownOutside", e);
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0, i = t.button === 2 || n;
				a.value = i;
			},
			onFocusOutside: t[2] ||= ss(() => {}, ["prevent"])
		}), {
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16, ["trap-focus"]));
	}
}), Ed = /* @__PURE__ */ H({
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
		let n = e, r = t, i = bd(), a = /* @__PURE__ */ F(!1), o = /* @__PURE__ */ F(!1), s = hc(n, r);
		return (e, t) => (q(), Y(wd, Na(I(s), {
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
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Dd = /* @__PURE__ */ H({
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
		let n = e, r = t, i = bd(), a = hc(n, r), { forwardRef: o } = pc();
		return i.contentId ||= Ec(void 0, "reka-popover-content"), (t, n) => (q(), Y(I(jc), { present: e.forceMount || I(i).open.value }, {
			default: B(() => [I(i).modal.value ? (q(), Y(Td, Na({ key: 0 }, I(a), { ref: I(o) }), {
				default: B(() => [U(t.$slots, "default")]),
				_: 3
			}, 16)) : (q(), Y(Ed, Na({ key: 1 }, I(a), { ref: I(o) }), {
				default: B(() => [U(t.$slots, "default")]),
				_: 3
			}, 16))]),
			_: 3
		}, 8, ["present"]));
	}
}), Od = /* @__PURE__ */ H({
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
		return (e, n) => (q(), Y(I(il), he(Ea(t)), {
			default: B(() => [U(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), kd = /* @__PURE__ */ H({
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
		let t = e, n = bd(), { forwardRef: r, currentElement: i } = pc();
		return n.triggerId ||= Ec(void 0, "reka-popover-trigger"), n.contentId ||= Ec(void 0, "reka-popover-content"), Fr(() => {
			n.triggerElement.value = i.value;
		}), (i, a) => (q(), Y(qr(I(n).hasCustomAnchor.value ? I(Pc) : I(cl)), { "as-child": "" }, {
			default: B(() => [Z(I(Pc), {
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
}), Ad = [
	"data-active",
	"aria-label",
	"title"
], jd = { class: "tc-column-filter-label" }, Md = { class: "tc-filter-popover-heading list-filter-popover__heading" }, Nd = /*#__PURE__*/ ys(/* @__PURE__ */ H({
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
		return (t, r) => (q(), Y(I(Sd), {
			open: e.open,
			modal: !1,
			"onUpdate:open": r[0] ||= (e) => n("update:open", e)
		}, {
			default: B(() => [Z(I(kd), { "as-child": "" }, {
				default: B(() => [X("button", {
					type: "button",
					class: k(["tc-column-filter-trigger", { "is-active": e.active }]),
					"data-active": e.active ? "" : void 0,
					"aria-label": `筛选${e.label}`,
					title: e.active ? `${e.label}：${e.summary || "已筛选"}` : `筛选${e.label}`
				}, [X("span", jd, Te(e.triggerLabel || e.label), 1), r[1] ||= X("svg", {
					class: "tc-column-filter-icon",
					viewBox: "0 0 16 16",
					width: "14",
					height: "14",
					fill: "none",
					"aria-hidden": "true",
					focusable: "false"
				}, [X("path", {
					d: "M2 3h12L9.5 8.3V13l-3-1.5V8.3L2 3Z",
					stroke: "currentColor",
					"stroke-width": "1.4",
					"stroke-linejoin": "round"
				})], -1)], 10, Ad)]),
				_: 1
			}), Z(I(Od), null, {
				default: B(() => [Z(I(Dd), {
					class: "tc-filter-popover list-filter-popover",
					"aria-label": `筛选${e.label}`,
					side: "bottom",
					align: "start",
					"side-offset": 6,
					"collision-padding": 10,
					"hide-when-detached": ""
				}, {
					default: B(() => [
						X("div", Md, "筛选" + Te(e.label), 1),
						U(t.$slots, "default", {}, void 0, !0),
						Z(I(Cd), {
							class: "tc-filter-popover-close list-filter-popover__close",
							"aria-label": `关闭${e.label}筛选`,
							title: "关闭筛选"
						}, {
							default: B(() => [...r[2] ||= [X("svg", {
								viewBox: "0 0 16 16",
								width: "16",
								height: "16",
								fill: "none",
								"aria-hidden": "true",
								focusable: "false"
							}, [X("path", {
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
// src/shared/useColumnWidths.ts
function Pd(e) {
	let t = /* @__PURE__ */ F([...e.defaults]), n = $(() => t.value.reduce((e, t) => e + t, 0));
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
	return je(() => r?.()), {
		widths: t,
		total: n,
		resize: o,
		resizeWithKeyboard: a,
		resetColumns: s
	};
}
// src/components/ListCell.vue?vue&type=script&setup=true&lang.ts
var Fd = ["title"], Id = {
	key: 0,
	class: "list-cell-secondary"
}, Ld = /*#__PURE__*/ ys(/* @__PURE__ */ H({
	__name: "ListCell",
	props: {
		text: {},
		secondary: {},
		title: {},
		tone: { default: "neutral" }
	},
	setup(e) {
		return (t, n) => (q(), J("div", {
			class: k(["list-cell", `list-cell--${e.tone}`]),
			title: e.title ?? [e.text, e.secondary].filter(Boolean).join(" · ")
		}, [X("div", { class: k(["list-cell-primary", { "list-cell-single": !!e.secondary }]) }, [U(t.$slots, "default", {}, () => [Oa(Te(e.text), 1)], !0)], 2), e.secondary ? (q(), J("div", Id, Te(e.secondary), 1)) : ka("", !0)], 10, Fd));
	}
}), [["__scopeId", "data-v-5767b82c"]]), Rd = ["aria-label", "aria-busy"], zd = { class: "list-pagination__layout" }, Bd = { class: "list-pagination__controls" }, Vd = { class: "list-pagination__pages" }, Hd = ["disabled"], Ud = [
	"aria-label",
	"aria-current",
	"disabled",
	"onClick"
], Wd = {
	key: 1,
	class: "list-pagination__ellipsis",
	"aria-hidden": "true"
}, Gd = {
	class: "list-pagination__mobile-page",
	"aria-live": "polite"
}, Kd = ["disabled"], qd = [
	"aria-invalid",
	"title",
	"disabled"
], Jd = ["disabled"], Yd = { class: "list-pagination__meta" }, Xd = {
	class: "list-pagination__range",
	"aria-live": "polite"
}, Zd = { key: 0 }, Qd = { class: "list-pagination__size" }, $d = ["value", "disabled"], ef = ["value"], tf = {
	key: 0,
	class: "list-pagination__error",
	role: "alert"
}, nf = /*#__PURE__*/ ys(/* @__PURE__ */ H({
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
		let n = e, r = t, i = $(() => Math.max(0, Math.floor(n.total) || 0)), a = $(() => Math.max(1, Math.floor(n.size) || 1)), o = $(() => Math.max(1, Math.floor(n.pages || Math.ceil(i.value / a.value)) || 1)), s = $(() => Math.min(o.value, Math.max(1, Math.floor(n.page) || 1))), c = $(() => i.value ? Math.min(i.value, (s.value - 1) * a.value + 1) : 0), l = $(() => Math.min(i.value, s.value * a.value)), u = $(() => [.../* @__PURE__ */ new Set([...n.pageSizes, a.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), d = /* @__PURE__ */ F(String(s.value)), f = /* @__PURE__ */ F(!1);
		V([s, o], () => {
			d.value = String(s.value), f.value = !1;
		});
		let p = $(() => {
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
		return (t, n) => (q(), J("nav", {
			class: "tc-pagination list-pagination",
			"aria-label": e.label,
			"aria-busy": e.busy
		}, [X("div", zd, [
			X("div", Bd, [X("div", Vd, [
				X("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: e.busy || !i.value || s.value <= 1,
					onClick: n[0] ||= (e) => m(s.value - 1)
				}, "上一页", 8, Hd),
				(q(!0), J(K, null, Xr(p.value, (t) => (q(), J(K, { key: t }, [typeof t == "number" ? (q(), J("button", {
					key: 0,
					type: "button",
					class: k(["list-pagination__button list-pagination__number", { "is-current": t === s.value }]),
					"aria-label": `第 ${t} 页`,
					"aria-current": t === s.value ? "page" : void 0,
					disabled: e.busy || !i.value || t === s.value,
					onClick: (e) => m(t)
				}, Te(t), 11, Ud)) : (q(), J("span", Wd, "…"))], 64))), 128)),
				X("span", Gd, Te(s.value) + " / " + Te(o.value), 1),
				X("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: e.busy || !i.value || s.value >= o.value,
					onClick: n[1] ||= (e) => m(s.value + 1)
				}, "下一页", 8, Kd)
			]), X("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: ss(h, ["prevent"])
			}, [X("label", null, [
				n[4] ||= Oa("跳至 ", -1),
				Wn(X("input", {
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
				}, null, 40, qd), [[es, d.value]]),
				n[5] ||= Oa(" 页", -1)
			]), X("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: e.busy || !i.value || o.value <= 1
			}, "跳转", 8, Jd)], 32)]),
			X("div", Yd, [X("span", Xd, [i.value ? (q(), J("span", Zd, Te(c.value.toLocaleString()) + "–" + Te(l.value.toLocaleString()) + " / ", 1)) : ka("", !0), Oa("共 " + Te(i.value.toLocaleString()) + " 条", 1)]), X("label", Qd, [n[6] ||= Oa("每页 ", -1), X("select", {
				"aria-label": "每页条数",
				value: a.value,
				disabled: e.busy,
				onChange: g
			}, [(q(!0), J(K, null, Xr(u.value, (e) => (q(), J("option", {
				key: e,
				value: e
			}, Te(e) + " 条", 9, ef))), 128))], 40, $d)])]),
			f.value ? (q(), J("span", tf, "请输入整数页码")) : ka("", !0)
		])], 8, Rd));
	}
}), [["__scopeId", "data-v-5637de47"]]), rf = ["aria-label"], af = [
	"aria-label",
	"title",
	"onClick"
], of = /*#__PURE__*/ ys(/* @__PURE__ */ H({
	__name: "ListFilterSummary",
	props: {
		items: {},
		label: { default: "已应用筛选" }
	},
	emits: ["remove"],
	setup(e, { emit: t }) {
		let n = t;
		return (t, r) => e.items.length ? (q(), J("div", {
			key: 0,
			class: "list-filter-summary",
			role: "group",
			"aria-label": e.label
		}, [(q(!0), J(K, null, Xr(e.items, (e) => (q(), J("button", {
			key: e.key,
			type: "button",
			class: "list-filter-chip",
			"aria-label": e.removeLabel,
			title: e.title || e.label,
			onClick: (t) => n("remove", e.key)
		}, [X("span", null, Te(e.label), 1), r[0] ||= X("span", { "aria-hidden": "true" }, "×", -1)], 8, af))), 128))], 8, rf)) : ka("", !0);
	}
}), [["__scopeId", "data-v-9c3f6cac"]]);
export { jn as A, B, Y as C, Z as D, Oa as E, Xr as F, Gt as G, P as H, U as I, I as J, F as K, Gr as L, Fr as M, Lr as N, H as O, q as P, br as R, X as S, J as T, je as U, Wn as V, Ut as W, ue as X, k as Y, Te as Z, ls as _, Nd as a, fr as b, Dd as c, gs as d, vs as f, yo as g, ts as h, Pd as i, Rr as j, Na as k, Sd as l, ps as m, nf as n, kd as o, _s as p, tn as q, Ld as r, Od as s, of as t, ys as u, ss as v, ka as w, $ as x, K as y, V as z };
