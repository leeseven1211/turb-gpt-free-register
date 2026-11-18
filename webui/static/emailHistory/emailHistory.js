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
function N(e, t, n) {
	if (We && M) {
		let t = $e.get(e);
		t || $e.set(e, t = /* @__PURE__ */ new Map());
		let r = t.get(n);
		r || (t.set(n, r = new Ze()), r.map = t, r.key = n), r.track();
	}
}
function rt(e, t, n, r, i, a) {
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
function it(e, t) {
	let n = $e.get(e);
	return n && n.get(t);
}
function at(e) {
	let t = /* @__PURE__ */ P(e);
	return t === e || (N(t, "iterate", nt), /* @__PURE__ */ Jt(e)) ? t : /* @__PURE__ */ qt(e) ? /* @__PURE__ */ Kt(e) ? t.map((e) => Qt(Zt(e))) : t.map(Qt) : t.map(Zt);
}
function ot(e) {
	return N(e = /* @__PURE__ */ P(e), "iterate", nt), e;
}
function st(e, t) {
	return /* @__PURE__ */ qt(e) ? Qt(/* @__PURE__ */ Kt(e) ? Zt(t) : t) : Zt(t);
}
var ct = {
	__proto__: null,
	[Symbol.iterator]() {
		return lt(this, Symbol.iterator, (e) => st(this, e));
	},
	concat(...e) {
		return at(this).concat(...e.map((e) => d(e) ? at(e) : e));
	},
	entries() {
		return lt(this, "entries", (e) => (e[1] = st(this, e[1]), e));
	},
	every(e, t) {
		return ft(this, "every", e, t, void 0, arguments);
	},
	filter(e, t) {
		return ft(this, "filter", e, t, (e) => e.map((e) => st(this, e)), arguments);
	},
	find(e, t) {
		return ft(this, "find", e, t, (e) => st(this, e), arguments);
	},
	findIndex(e, t) {
		return ft(this, "findIndex", e, t, void 0, arguments);
	},
	findLast(e, t) {
		return ft(this, "findLast", e, t, (e) => st(this, e), arguments);
	},
	findLastIndex(e, t) {
		return ft(this, "findLastIndex", e, t, void 0, arguments);
	},
	forEach(e, t) {
		return ft(this, "forEach", e, t, void 0, arguments);
	},
	includes(...e) {
		return mt(this, "includes", e);
	},
	indexOf(...e) {
		return mt(this, "indexOf", e);
	},
	join(e) {
		return at(this).join(e);
	},
	lastIndexOf(...e) {
		return mt(this, "lastIndexOf", e);
	},
	map(e, t) {
		return ft(this, "map", e, t, void 0, arguments);
	},
	pop() {
		return ht(this, "pop");
	},
	push(...e) {
		return ht(this, "push", e);
	},
	reduce(e, ...t) {
		return pt(this, "reduce", e, t);
	},
	reduceRight(e, ...t) {
		return pt(this, "reduceRight", e, t);
	},
	shift() {
		return ht(this, "shift");
	},
	some(e, t) {
		return ft(this, "some", e, t, void 0, arguments);
	},
	splice(...e) {
		return ht(this, "splice", e);
	},
	toReversed() {
		return at(this).toReversed();
	},
	toSorted(e) {
		return at(this).toSorted(e);
	},
	toSpliced(...e) {
		return at(this).toSpliced(...e);
	},
	unshift(...e) {
		return ht(this, "unshift", e);
	},
	values() {
		return lt(this, "values", (e) => st(this, e));
	}
};
function lt(e, t, n) {
	let r = ot(e), i = r[t], a = i.call(r);
	if (r !== e && !/* @__PURE__ */ Jt(e)) {
		if (a[Symbol.toStringTag] === "Array Iterator") {
			let e = Object.create(Object.getPrototypeOf(a));
			return e.next = () => ut(a.next(), n), i !== dt[t] && Object.defineProperties(e, {
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
		a._next = a.next, a.next = () => ut(a._next(), n);
	}
	return a;
}
function ut(e, t) {
	return e.done || (e.value = t(e.value)), e;
}
var dt = Array.prototype;
function ft(e, t, n, r, i, a) {
	let o = ot(e), s = o !== e && !/* @__PURE__ */ Jt(e), c = o[t];
	if (c !== dt[t]) {
		let t = c.apply(e, a);
		return s ? Zt(t) : t;
	}
	let l = n;
	o !== e && (s ? l = function(t, r) {
		return n.call(this, st(e, t), r, e);
	} : n.length > 2 && (l = function(t, r) {
		return n.call(this, t, r, e);
	}));
	let u = c.call(o, l, r);
	return s && i ? i(u) : u;
}
function pt(e, t, n, r) {
	let i = ot(e), a = i !== e && !/* @__PURE__ */ Jt(e), o = n, s = !1;
	i !== e && (a ? (s = r.length === 0, o = function(t, r, i) {
		return s && (s = !1, t = st(e, t)), n.call(this, t, st(e, r), i, e);
	}) : n.length > 3 && (o = function(t, r, i) {
		return n.call(this, t, r, i, e);
	}));
	let c = i[t](o, ...r);
	return s ? st(e, c) : c;
}
function mt(e, t, n) {
	let r = /* @__PURE__ */ P(e);
	N(r, "iterate", nt);
	let i = r[t](...n);
	return (i === -1 || i === !1) && /* @__PURE__ */ Yt(n[0]) ? (n[0] = /* @__PURE__ */ P(n[0]), r[t](...n)) : i;
}
function ht(e, t, n = []) {
	Ke(), Ie();
	let r = (/* @__PURE__ */ P(e))[t].apply(e, n);
	return Le(), qe(), r;
}
var gt = /* @__PURE__ */ e("__proto__,__v_isRef,__isVue"), _t = /* @__PURE__ */ new Set(/* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(_));
function vt(e) {
	_(e) || (e = String(e));
	let t = /* @__PURE__ */ P(this);
	return N(t, "has", e), t.hasOwnProperty(e);
}
var yt = class {
	constructor(e = !1, t = !1) {
		this._isReadonly = e, this._isShallow = t;
	}
	get(e, t, n) {
		if (t === "__v_skip") return e.__v_skip;
		let r = this._isReadonly, i = this._isShallow;
		if (t === "__v_isReactive") return !r;
		if (t === "__v_isReadonly") return r;
		if (t === "__v_isShallow") return i;
		if (t === "__v_raw") return n === (r ? i ? zt : Rt : i ? Lt : It).get(e) || Object.getPrototypeOf(e) === Object.getPrototypeOf(n) ? e : void 0;
		let a = d(e);
		if (!r) {
			let e;
			if (a && (e = ct[t])) return e;
			if (t === "hasOwnProperty") return vt;
		}
		let o = Reflect.get(e, t, /* @__PURE__ */ F(e) ? e : n);
		if ((_(t) ? _t.has(t) : gt(t)) || (r || N(e, "get", t), i)) return o;
		if (/* @__PURE__ */ F(o)) {
			let e = a && w(t) ? o : o.value;
			return r && v(e) ? /* @__PURE__ */ Ut(e) : e;
		}
		return v(o) ? r ? /* @__PURE__ */ Ut(o) : /* @__PURE__ */ Vt(o) : o;
	}
}, bt = class extends yt {
	constructor(e = !1) {
		super(!1, e);
	}
	set(e, t, n, r) {
		let i = e[t], a = d(e) && w(t);
		if (!this._isShallow) {
			let e = /* @__PURE__ */ qt(i);
			if (!/* @__PURE__ */ Jt(n) && !/* @__PURE__ */ qt(n) && (i = /* @__PURE__ */ P(i), n = /* @__PURE__ */ P(n)), !a && /* @__PURE__ */ F(i) && !/* @__PURE__ */ F(n)) return e || (i.value = n), !0;
		}
		let o = a ? Number(t) < e.length : u(e, t), s = Reflect.set(e, t, n, /* @__PURE__ */ F(e) ? e : r);
		return e === /* @__PURE__ */ P(r) && s && (o ? ae(n, i) && rt(e, "set", t, n, i) : rt(e, "add", t, n)), s;
	}
	deleteProperty(e, t) {
		let n = u(e, t), r = e[t], i = Reflect.deleteProperty(e, t);
		return i && n && rt(e, "delete", t, void 0, r), i;
	}
	has(e, t) {
		let n = Reflect.has(e, t);
		return _(t) && _t.has(t) || N(e, "has", t), n;
	}
	ownKeys(e) {
		return N(e, "iterate", d(e) ? "length" : et), Reflect.ownKeys(e);
	}
}, xt = class extends yt {
	constructor(e = !1) {
		super(!0, e);
	}
	set(e, t) {
		return !0;
	}
	deleteProperty(e, t) {
		return !0;
	}
}, St = /* @__PURE__ */ new bt(), Ct = /* @__PURE__ */ new xt(), wt = /* @__PURE__ */ new bt(!0), Tt = /* @__PURE__ */ new xt(!0), Et = (e) => e, Dt = (e) => Reflect.getPrototypeOf(e);
function Ot(e, t, n) {
	return function(...r) {
		let i = this.__v_raw, a = /* @__PURE__ */ P(i), o = f(a), c = e === "entries" || e === Symbol.iterator && o, l = e === "keys" && o, u = i[e](...r), d = n ? Et : t ? Qt : Zt;
		return !t && N(a, "iterate", l ? tt : et), s(Object.create(u), { next() {
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
function kt(e) {
	return function(...t) {
		return e === "delete" ? !1 : e === "clear" ? void 0 : this;
	};
}
function At(e, t) {
	let n = {
		get(n) {
			let r = this.__v_raw, i = /* @__PURE__ */ P(r), a = /* @__PURE__ */ P(n);
			e || (ae(n, a) && N(i, "get", n), N(i, "get", a));
			let { has: o } = Dt(i), s = t ? Et : e ? Qt : Zt;
			if (o.call(i, n)) return s(r.get(n));
			if (o.call(i, a)) return s(r.get(a));
			r !== i && r.get(n);
		},
		get size() {
			let t = this.__v_raw;
			return !e && N(/* @__PURE__ */ P(t), "iterate", et), t.size;
		},
		has(t) {
			let n = this.__v_raw, r = /* @__PURE__ */ P(n), i = /* @__PURE__ */ P(t);
			return e || (ae(t, i) && N(r, "has", t), N(r, "has", i)), t === i ? n.has(t) : n.has(t) || n.has(i);
		},
		forEach(n, r) {
			let i = this, a = i.__v_raw, o = /* @__PURE__ */ P(a), s = t ? Et : e ? Qt : Zt;
			return !e && N(o, "iterate", et), a.forEach((e, t) => n.call(r, s(e), s(t), i));
		}
	};
	return s(n, e ? {
		add: kt("add"),
		set: kt("set"),
		delete: kt("delete"),
		clear: kt("clear")
	} : {
		add(e) {
			let n = /* @__PURE__ */ P(this), r = Dt(n), i = /* @__PURE__ */ P(e), a = !t && !/* @__PURE__ */ Jt(e) && !/* @__PURE__ */ qt(e) ? i : e;
			return r.has.call(n, a) || ae(e, a) && r.has.call(n, e) || ae(i, a) && r.has.call(n, i) || (n.add(a), rt(n, "add", a, a)), this;
		},
		set(e, n) {
			t || /* @__PURE__ */ Jt(n) || /* @__PURE__ */ qt(n) || (n = /* @__PURE__ */ P(n));
			let r = /* @__PURE__ */ P(this), { has: i, get: a } = Dt(r), o = i.call(r, e);
			o ||= (e = /* @__PURE__ */ P(e), i.call(r, e));
			let s = a.call(r, e);
			return r.set(e, n), o ? ae(n, s) && rt(r, "set", e, n, s) : rt(r, "add", e, n), this;
		},
		delete(e) {
			let t = /* @__PURE__ */ P(this), { has: n, get: r } = Dt(t), i = n.call(t, e);
			i ||= (e = /* @__PURE__ */ P(e), n.call(t, e));
			let a = r ? r.call(t, e) : void 0, o = t.delete(e);
			return i && rt(t, "delete", e, void 0, a), o;
		},
		clear() {
			let e = /* @__PURE__ */ P(this), t = e.size !== 0, n = e.clear();
			return t && rt(e, "clear", void 0, void 0, void 0), n;
		}
	}), [
		"keys",
		"values",
		"entries",
		Symbol.iterator
	].forEach((r) => {
		n[r] = Ot(r, e, t);
	}), n;
}
function jt(e, t) {
	let n = At(e, t);
	return (r, i, a) => i === "__v_isReactive" ? !e : i === "__v_isReadonly" ? e : i === "__v_isShallow" ? t : i === "__v_raw" ? r : Reflect.get(u(n, i) && i in r ? n : r, i, a);
}
var Mt = { get: /* @__PURE__ */ jt(!1, !1) }, Nt = { get: /* @__PURE__ */ jt(!1, !0) }, Pt = { get: /* @__PURE__ */ jt(!0, !1) }, Ft = { get: /* @__PURE__ */ jt(!0, !0) }, It = /* @__PURE__ */ new WeakMap(), Lt = /* @__PURE__ */ new WeakMap(), Rt = /* @__PURE__ */ new WeakMap(), zt = /* @__PURE__ */ new WeakMap();
function Bt(e) {
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
function Vt(e) {
	return /* @__PURE__ */ qt(e) ? e : Gt(e, !1, St, Mt, It);
}
// @__NO_SIDE_EFFECTS__
function Ht(e) {
	return Gt(e, !1, wt, Nt, Lt);
}
// @__NO_SIDE_EFFECTS__
function Ut(e) {
	return Gt(e, !0, Ct, Pt, Rt);
}
// @__NO_SIDE_EFFECTS__
function Wt(e) {
	return Gt(e, !0, Tt, Ft, zt);
}
function Gt(e, t, n, r, i) {
	if (!v(e) || e.__v_raw && !(t && e.__v_isReactive) || e.__v_skip || !Object.isExtensible(e)) return e;
	let a = i.get(e);
	if (a) return a;
	let o = Bt(S(e));
	if (o === 0) return e;
	let s = new Proxy(e, o === 2 ? r : n);
	return i.set(e, s), s;
}
// @__NO_SIDE_EFFECTS__
function Kt(e) {
	return /* @__PURE__ */ qt(e) ? /* @__PURE__ */ Kt(e.__v_raw) : !!(e && e.__v_isReactive);
}
// @__NO_SIDE_EFFECTS__
function qt(e) {
	return !!(e && e.__v_isReadonly);
}
// @__NO_SIDE_EFFECTS__
function Jt(e) {
	return !!(e && e.__v_isShallow);
}
// @__NO_SIDE_EFFECTS__
function Yt(e) {
	return e ? !!e.__v_raw : !1;
}
// @__NO_SIDE_EFFECTS__
function P(e) {
	let t = e && e.__v_raw;
	return t ? /* @__PURE__ */ P(t) : e;
}
function Xt(e) {
	return !u(e, "__v_skip") && Object.isExtensible(e) && O(e, "__v_skip", !0), e;
}
var Zt = (e) => v(e) ? /* @__PURE__ */ Vt(e) : e, Qt = (e) => v(e) ? /* @__PURE__ */ Ut(e) : e;
// @__NO_SIDE_EFFECTS__
function F(e) {
	return e ? e.__v_isRef === !0 : !1;
}
// @__NO_SIDE_EFFECTS__
function I(e) {
	return en(e, !1);
}
// @__NO_SIDE_EFFECTS__
function $t(e) {
	return en(e, !0);
}
function en(e, t) {
	return /* @__PURE__ */ F(e) ? e : new tn(e, t);
}
var tn = class {
	constructor(e, t) {
		this.dep = new Ze(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = t ? e : /* @__PURE__ */ P(e), this._value = t ? e : Zt(e), this.__v_isShallow = t;
	}
	get value() {
		return this.dep.track(), this._value;
	}
	set value(e) {
		let t = this._rawValue, n = this.__v_isShallow || /* @__PURE__ */ Jt(e) || /* @__PURE__ */ qt(e);
		e = n ? e : /* @__PURE__ */ P(e), ae(e, t) && (this._rawValue = e, this._value = n ? e : Zt(e), this.dep.trigger());
	}
};
function nn(e) {
	e.dep && e.dep.trigger();
}
function L(e) {
	return /* @__PURE__ */ F(e) ? e.value : e;
}
function R(e) {
	return h(e) ? e() : L(e);
}
var rn = {
	get: (e, t, n) => t === "__v_raw" ? e : L(Reflect.get(e, t, n)),
	set: (e, t, n, r) => {
		let i = e[t];
		return /* @__PURE__ */ F(i) && !/* @__PURE__ */ F(n) ? (i.value = n, !0) : Reflect.set(e, t, n, r);
	}
};
function an(e) {
	return /* @__PURE__ */ Kt(e) ? e : new Proxy(e, rn);
}
// @__NO_SIDE_EFFECTS__
function on(e) {
	let t = d(e) ? Array(e.length) : {};
	for (let n in e) t[n] = un(e, n);
	return t;
}
var sn = class {
	constructor(e, t, n) {
		this._object = e, this._defaultValue = n, this.__v_isRef = !0, this._value = void 0, this._key = _(t) ? t : String(t), this._raw = /* @__PURE__ */ P(e);
		let r = !0, i = e;
		if (!d(e) || _(this._key) || !w(this._key)) do
			r = !/* @__PURE__ */ Yt(i) || /* @__PURE__ */ Jt(i);
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
		return it(this._raw, this._key);
	}
}, cn = class {
	constructor(e) {
		this._getter = e, this.__v_isRef = !0, this.__v_isReadonly = !0, this._value = void 0;
	}
	get value() {
		return this._value = this._getter();
	}
};
// @__NO_SIDE_EFFECTS__
function ln(e, t, n) {
	return /* @__PURE__ */ F(e) ? e : h(e) ? new cn(e) : v(e) && arguments.length > 1 ? un(e, t, n) : /* @__PURE__ */ I(e);
}
function un(e, t, n) {
	return new sn(e, t, n);
}
var dn = class {
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
function fn(e, t, n = !1) {
	let r, i;
	return h(e) ? r = e : (r = e.get, i = e.set), new dn(r, i, n);
}
var pn = {}, mn = /* @__PURE__ */ new WeakMap(), hn = void 0;
function gn(e, t = !1, n = hn) {
	if (n) {
		let t = mn.get(n);
		t || mn.set(n, t = []), t.push(e);
	}
}
function _n(e, n, i = t) {
	let { immediate: a, deep: o, once: s, scheduler: l, augmentJob: u, call: f } = i, p = (e) => o ? e : /* @__PURE__ */ Jt(e) || o === !1 || o === 0 ? vn(e, 1) : vn(e), m, g, _, v, y = !1, b = !1;
	if (/* @__PURE__ */ F(e) ? (g = () => e.value, y = /* @__PURE__ */ Jt(e)) : /* @__PURE__ */ Kt(e) ? (g = () => p(e), y = !0) : d(e) ? (b = !0, y = e.some((e) => /* @__PURE__ */ Kt(e) || /* @__PURE__ */ Jt(e)), g = () => e.map((e) => {
		if (/* @__PURE__ */ F(e)) return e.value;
		if (/* @__PURE__ */ Kt(e)) return p(e);
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
		let t = hn;
		hn = m;
		try {
			return f ? f(e, 3, [v]) : e(v);
		} finally {
			hn = t;
		}
	} : r, n && o) {
		let e = g, t = o === !0 ? Infinity : o;
		g = () => vn(e(), t);
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
	let C = b ? Array(e.length).fill(pn) : pn, w = (e) => {
		if (m.flags & 1 && (m.dirty || e)) {
			if (n) {
				let t = m.run();
				if (e || o || y || (b ? t.some((e, t) => ae(e, C[t])) : ae(t, C))) {
					let e = hn;
					Ke();
					try {
						_ && _(), hn = m;
						let e = [
							t,
							C === pn ? void 0 : b && C[0] === pn ? [] : C,
							v
						];
						C = t, f ? f(n, 3, e) : n(...e);
					} finally {
						hn = e, qe();
					}
				}
			} else m.run();
		}
	};
	return u && u(w), m = new je(g), m.scheduler = l ? () => l(w, !1) : w, v = (e) => gn(e, !1, m), _ = m.onStop = () => {
		let e = mn.get(m);
		if (e) {
			if (f) f(e, 4);
			else for (let t of e) t();
			mn.delete(m);
		}
	}, n ? a ? w(!0) : C = m.run() : l ? l(w.bind(null, !0), !0) : m.run(), S.pause = m.pause.bind(m), S.resume = m.resume.bind(m), S.stop = S, S;
}
function vn(e, t = Infinity, n) {
	if (t <= 0 || !v(e) || e.__v_skip || (n ||= /* @__PURE__ */ new Map(), (n.get(e) || 0) >= t)) return e;
	if (n.set(e, t), t--, /* @__PURE__ */ F(e)) vn(e.value, t, n);
	else if (d(e)) for (let r = 0; r < e.length; r++) vn(e[r], t, n);
	else if (p(e) || f(e)) e.forEach((e) => {
		vn(e, t, n);
	});
	else if (C(e)) {
		for (let r in e) vn(e[r], t, n);
		for (let r of Object.getOwnPropertySymbols(e)) Object.prototype.propertyIsEnumerable.call(e, r) && vn(e[r], t, n);
	}
	return e;
}
// node_modules/@vue/runtime-core/dist/runtime-core.esm-bundler.js
function yn(e, t, n, r) {
	try {
		return r ? e(...r) : e();
	} catch (e) {
		xn(e, t, n);
	}
}
function bn(e, t, n, r) {
	if (h(e)) {
		let i = yn(e, t, n, r);
		return i && y(i) && i.catch((e) => {
			xn(e, t, n, void 0, !0);
		}), i;
	}
	if (d(e)) {
		let i = [];
		for (let a = 0; a < e.length; a++) i.push(bn(e[a], t, n, r));
		return i;
	}
}
function xn(e, n, r, i = !0, a = !1) {
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
			Ke(), yn(s, null, 10, [
				e,
				i,
				o
			]), qe();
			return;
		}
	}
	Sn(e, r, o, i, c);
}
function Sn(e, t, n, r = !0, i = !1) {
	if (i) throw e;
	console.error(e);
}
var z = [], Cn = -1, wn = [], Tn = null, En = 0, Dn = /* @__PURE__ */ Promise.resolve(), On = null;
function kn(e) {
	let t = On || Dn;
	return e ? t.then(this ? e.bind(this) : e) : t;
}
function An(e) {
	let t = Cn + 1, n = z.length;
	for (; t < n;) {
		let r = t + n >>> 1, i = z[r], a = Rn(i);
		a < e || a === e && i.flags & 2 ? t = r + 1 : n = r;
	}
	return t;
}
function jn(e) {
	if (!(e.flags & 1)) {
		let t = Rn(e), n = z[z.length - 1];
		!n || !(e.flags & 2) && t >= Rn(n) ? z.push(e) : z.splice(An(t), 0, e), e.flags |= 1, Mn();
	}
}
function Mn() {
	On ||= Dn.then(zn);
}
function Nn(e) {
	if (!d(e)) Tn && e.id === -1 ? Tn.splice(En + 1, 0, e) : e.flags & 1 || (wn.push(e), e.flags |= 1);
	else for (let t = 0; t < e.length; t++) wn.push(e[t]);
	Mn();
}
function Pn(e, t, n, r = Cn + 1) {
	for (; r < z.length; r++) {
		let n = z[r];
		if (n && n.flags & 2) {
			if (e && n.id !== e.uid || t !== void 0 && !(n.id >= t)) continue;
			z.splice(r, 1), r = e ? r - 1 : Cn, n.flags & 4 && (n.flags &= -2), n(), n.flags & 4 || (n.flags &= -2);
		}
	}
}
function Fn(e, t, n = 0) {
	if (wn.length) {
		let e = wn, r = 0;
		if (t) {
			e = [];
			for (let i = 0; i < wn.length; i++) {
				let a = wn[i];
				(a.i === void 0 ? t.has(a) : !a.i || a.i.uid < n) ? wn[r++] = a : e.push(a);
			}
		}
		let i = [...new Set(e)].sort((e, t) => Rn(e) - Rn(t));
		if (wn.length = r, Tn) {
			for (let e = 0; e < i.length; e++) Tn.push(i[e]);
			return;
		}
		for (Tn = i, En = 0; En < Tn.length; En++) {
			let e = Tn[En];
			e.flags & 4 && (e.flags &= -2), e.flags & 8 || e(), e.flags &= -2;
		}
		Tn = null, En = 0;
	}
}
var In = !1;
function Ln(e, t) {
	if (In) {
		e();
		return;
	}
	let n = t === void 0 ? void 0 : new Set(wn);
	e(), In = !0;
	try {
		Pn(void 0, t), Fn(void 0, n, t);
	} finally {
		In = !1;
	}
}
var Rn = (e) => e.id == null ? e.flags & 2 ? -1 : Infinity : e.id;
function zn(e) {
	try {
		for (Cn = 0; Cn < z.length; Cn++) {
			let e = z[Cn];
			e && !(e.flags & 8) && (e.flags & 4 && (e.flags &= -2), yn(e, e.i, e.i ? 15 : 14), e.flags & 4 || (e.flags &= -2));
		}
	} finally {
		for (; Cn < z.length; Cn++) {
			let e = z[Cn];
			e && (e.flags &= -2);
		}
		Cn = -1, z.length = 0, Fn(e), On = null, (z.length || wn.length) && zn(e);
	}
}
var B = null, Bn = null;
function Vn(e) {
	let t = B;
	return B = e, Bn = e && e.type.__scopeId || null, t;
}
function V(e, t = B, n) {
	if (!t || e._n) return e;
	let r = (...n) => {
		r._d && _a(-1);
		let i = Vn(t), a = pa.length, o;
		try {
			o = e(...n);
		} finally {
			for (let e = pa.length; e > a; e--) ha();
			Vn(i), r._d && _a(1);
		}
		return o;
	};
	return r._n = !0, r._c = !0, r._d = !0, r;
}
function Hn(e, n) {
	if (B === null) return e;
	let r = Za(B), i = e.dirs ||= [];
	for (let e = 0; e < n.length; e++) {
		let [a, o, s, c = t] = n[e];
		a && (h(a) && (a = {
			mounted: a,
			updated: a
		}), a.deep && vn(o), i.push({
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
function Un(e, t, n, r) {
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
		u && (Ke(), bn(u, n, 8, [
			e.el,
			l,
			i,
			t
		]), qe());
	}
}
function Wn(e, t) {
	if (Q) {
		let n = Q.provides, r = Q.parent && Q.parent.provides;
		r === n && (n = Q.provides = Object.create(r)), n[e] = t;
	}
}
function Gn(e, t, n = !1) {
	let r = La();
	if (r || yi) {
		let i = yi ? yi._context.provides : r ? r.parent == null || r.ce ? r.vnode.appContext && r.vnode.appContext.provides : r.parent.provides : void 0;
		if (i && e in i) return i[e];
		if (arguments.length > 1) return n && h(t) ? t.call(r && r.proxy) : t;
	}
}
var Kn = /* @__PURE__ */ Symbol.for("v-scx"), qn = () => Gn(Kn);
function Jn(e, t) {
	return Xn(e, null, t);
}
function Yn(e, t) {
	return Xn(e, null, { flush: "post" });
}
function H(e, t, n) {
	return Xn(e, t, n);
}
function Xn(e, n, i = t) {
	let { immediate: a, deep: o, flush: c, once: l } = i, u = s({}, i), d = n && a || !n && c !== "post", f;
	if (Ua) {
		if (c === "sync") {
			let e = qn();
			f = e.__watcherHandles ||= [];
		} else if (!d) {
			let e = () => {};
			return e.stop = r, e.resume = r, e.pause = r, e;
		}
	}
	let p = Q;
	u.call = (e, t, n) => bn(e, p, t, n);
	let m = !1;
	c === "post" ? u.scheduler = (e) => {
		e.i = p, G(e, p && p.suspense);
	} : c !== "sync" && (m = !0, u.scheduler = (e, t) => {
		t ? e() : jn(e);
	}), u.augmentJob = (e) => {
		n && (e.flags |= 4), m && (e.flags |= 2, p && (e.id = p.uid, e.i = p));
	};
	let h = _n(e, n, u);
	return Ua && (f ? f.push(h) : d && h()), h;
}
function Zn(e, t, n) {
	let r = this.proxy, i = g(e) ? e.includes(".") ? Qn(r, e) : () => r[e] : e.bind(r, r), a;
	h(t) ? a = t : (a = t.handler, n = t);
	let o = Ba(this), s = Xn(i, a.bind(r), n);
	return o(), s;
}
function Qn(e, t) {
	let n = t.split(".");
	return () => {
		let t = e;
		for (let e = 0; e < n.length && t; e++) t = t[n[e]];
		return t;
	};
}
var $n = /* @__PURE__ */ new WeakMap(), er = /* @__PURE__ */ Symbol("_vte"), tr = (e) => e.__isTeleport, nr = (e) => e && (e.disabled || e.disabled === ""), rr = (e) => e && (e.defer || e.defer === ""), ir = (e) => typeof SVGElement < "u" && e instanceof SVGElement, ar = (e) => typeof MathMLElement == "function" && e instanceof MathMLElement, or = (e, t) => {
	let n = e && e.to;
	return g(n) ? t ? t(n) : null : n;
}, sr = {
	name: "Teleport",
	__isTeleport: !0,
	process(e, t, n, r, i, a, o, s, c, l) {
		let { mc: u, pc: d, pbc: f, o: { insert: p, querySelector: m, createText: h, createComment: g, parentNode: _ } } = l, v = nr(t.props), { dynamicChildren: y } = t, b = (e, t, n) => {
			e.shapeFlag & 16 && u(e.children, t, n, i, a, o, s, c);
		}, x = (e = t) => {
			let n = nr(e.props), r = e.target = or(e.props, m), a = fr(r, e, h, p);
			r && (o !== "svg" && ir(r) ? o = "svg" : o !== "mathml" && ar(r) && (o = "mathml"), i && i.isCE && (i.ce._teleportTargets || (i.ce._teleportTargets = /* @__PURE__ */ new Set())).add(r), n || (b(e, r, a), dr(e, !1)));
		}, S = (e) => {
			let t = () => {
				if ($n.get(e) === t) {
					if ($n.delete(e), nr(e.props)) {
						let t = _(e.el) || n;
						b(e, t, e.anchor), dr(e, !0);
					}
					x(e);
				}
			};
			$n.set(e, t), G(t, a);
		};
		if (e == null) {
			let e = t.el = h(""), i = t.anchor = h("");
			if (p(e, n, r), p(i, n, r), rr(t.props) || a && a.pendingBranch) {
				S(t);
				return;
			}
			v && (b(t, n, i), dr(t, !0)), x();
		} else {
			t.el = e.el;
			let r = t.anchor = e.anchor, u = $n.get(e);
			if (u) {
				u.flags |= 8, $n.delete(e), S(t);
				return;
			}
			t.targetStart = e.targetStart;
			let p = t.target = e.target, h = t.targetAnchor = e.targetAnchor, g = nr(e.props), _ = g ? n : p, b = g ? r : h;
			if (o === "svg" || ir(p) ? o = "svg" : (o === "mathml" || ar(p)) && (o = "mathml"), y ? (f(e.dynamicChildren, y, _, i, a, o, s), na(e, t, !0)) : c || d(e, t, _, b, i, a, o, s, !1), v) g ? t.props && e.props && t.props.to !== e.props.to && (t.props.to = e.props.to) : cr(t, n, r, l, 1);
			else if ((t.props && t.props.to) !== (e.props && e.props.to)) {
				let e = or(t.props, m);
				e && (t.target = e, cr(t, e, null, l, 0));
			} else g && cr(t, p, h, l, 1);
			dr(t, v);
		}
	},
	remove(e, t, n, { um: r, o: { remove: i } }, a) {
		let { shapeFlag: o, children: s, anchor: c, targetStart: l, targetAnchor: u, target: d, props: f } = e, p = nr(f), m = a || !p, h = $n.get(e);
		if (h && (h.flags |= 8, $n.delete(e)), d && (i(l), i(u)), a && i(c), !h && (p || d) && o & 16) for (let e = 0; e < s.length; e++) {
			let i = s[e];
			r(i, t, n, m, !!i.dynamicChildren);
		}
	},
	move: cr,
	hydrate: lr
};
function cr(e, t, n, { o: { insert: r }, m: i }, a = 2) {
	a === 0 && (e.targetStart && r(e.targetStart, t, n), r(e.targetAnchor, t, n), n = e.targetAnchor);
	let { el: o, anchor: s, shapeFlag: c, children: l, props: u } = e, d = a === 2;
	if (d && r(o, t, n), !$n.has(e) && (!d || nr(u)) && c & 16) for (let e = 0; e < l.length; e++) i(l[e], t, n, 2);
	d && r(s, t, n);
}
function lr(e, t, n, r, i, a, { o: { nextSibling: o, parentNode: s, querySelector: c, insert: l, createText: u } }, d) {
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
	let m = t.target = or(t.props, c), h = nr(t.props);
	if (m) {
		let c = m._lpa || m.firstChild;
		t.shapeFlag & 16 && (h ? (p(e, t), f(m, c), t.targetAnchor || fr(m, t, u, l, s(e) === m ? e : null)) : (t.anchor = o(e), f(m, c), t.targetAnchor || fr(m, t, u, l), d(c && o(c), t, m, n, r, i, a))), dr(t, h);
	} else h && t.shapeFlag & 16 && (p(e, t), t.targetStart = e, t.targetAnchor = o(e));
	return t.anchor && o(t.anchor);
}
var ur = sr;
function dr(e, t) {
	let n = e.ctx;
	if (n && n.ut) {
		let r, i;
		for (t ? (r = e.el, i = e.anchor) : (r = e.targetStart, i = e.targetAnchor); r && r !== i;) r.nodeType === 1 && r.setAttribute("data-v-owner", n.uid), r = r.nextSibling;
		n.ut();
	}
}
function fr(e, t, n, r, i = null) {
	let a = t.targetStart = n(""), o = t.targetAnchor = n("");
	return a[er] = o, e && (r(a, e, i), r(o, e, i)), o;
}
var pr = /* @__PURE__ */ Symbol("_leaveCb");
function mr(e) {
	let t = e[0];
	if (e.length > 1) {
		for (let n of e) if (n.type !== da) {
			t = n;
			break;
		}
	}
	return t;
}
function hr(e) {
	if (!Tr(e)) return tr(e.type) && e.children ? mr(e.children) : e;
	if (e.component) return e.component.subTree;
	let { shapeFlag: t, children: n } = e;
	if (n) {
		if (t & 16) return n[0];
		if (t & 32 && h(n.default)) return n.default();
	}
}
function gr(e, t) {
	if (e.shapeFlag & 6 && e.component) {
		e.transition = t;
		let n = e.component.subTree;
		gr(tr(n.type) && hr(n) || n, t);
	} else if (e.shapeFlag & 128) {
		let n = e.suspense;
		if (n) {
			let e = n.isHydrating ? n.pendingBranch : n.activeBranch;
			e && gr(e, t.clone(e));
		} else e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback);
	} else if (e.transition = t, e.type === K && d(e.children)) {
		let n = Ei(e.children, !1);
		n && gr(n, t);
	}
}
function _r(e) {
	if (e.component) return _r(e.component.subTree);
	if (e.type === K) {
		let t = d(e.children) && Ei(e.children, !1);
		return t ? _r(t) : void 0;
	}
	if (e.type !== da) return e;
}
// @__NO_SIDE_EFFECTS__
function U(e, t) {
	return h(e) ? /* @__PURE__ */ s({ name: e.name }, t, { setup: e }) : e;
}
function vr() {
	let e = La();
	return e ? (e.appContext.config.idPrefix || "v") + "-" + e.ids[0] + e.ids[1]++ : "";
}
function yr(e) {
	e.ids = [
		e.ids[0] + e.ids[2]++ + "-",
		0,
		0
	];
}
function br(e, t) {
	let n;
	return !!((n = Object.getOwnPropertyDescriptor(e, t)) && !n.configurable);
}
var xr = /* @__PURE__ */ new WeakMap();
function Sr(e, n, r, a, o = !1) {
	if (d(e)) {
		e.forEach((e, t) => Sr(e, n && (d(n) ? n[t] : n), r, a, o));
		return;
	}
	if (wr(a) && !o) {
		a.shapeFlag & 512 && a.type.__asyncResolved && a.component.subTree.component && Sr(e, n, r, a.component.subTree);
		return;
	}
	let s = a.shapeFlag & 4 ? Za(a.component) : a.el, l = o ? null : s, { i: f, r: p } = e, m = n && n.r, _ = f.refs === t ? f.refs = {} : f.refs, v = f.setupState, y = /* @__PURE__ */ P(v), b = v === t ? i : (e) => !br(_, e) && u(y, e), x = (e, t) => !(t && br(_, t));
	if (m != null && m !== p) {
		if (Cr(n), g(m)) _[m] = null, b(m) && (v[m] = null);
		else if (/* @__PURE__ */ F(m)) {
			let e = n;
			x(m, e.k) && (m.value = null), e.k && (_[e.k] = null);
		}
	}
	if (h(p)) yn(p, f, 12, [l, _]);
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
					i(), xr.delete(e);
				};
				t.id = -1, xr.set(e, t), G(t, r);
			} else Cr(e), i();
		}
	}
}
function Cr(e) {
	let t = xr.get(e);
	t && (t.flags |= 8, xr.delete(e));
}
le().requestIdleCallback, le().cancelIdleCallback;
var wr = (e) => !!e.type.__asyncLoader, Tr = (e) => e.type.__isKeepAlive;
function Er(e, t) {
	Or(e, "a", t);
}
function Dr(e, t) {
	Or(e, "da", t);
}
function Or(e, t, n = Q) {
	let r = e.__wdc ||= () => {
		let t = n;
		for (; t;) {
			if (t.isDeactivated) return;
			t = t.parent;
		}
		return e();
	};
	if (Ar(t, r, n), n) {
		let e = n.parent;
		for (; e && e.parent;) Tr(e.parent.vnode) && kr(r, t, n, e), e = e.parent;
	}
}
function kr(e, t, n, r) {
	let i = Ar(t, e, r, !0), a = Ar("um", () => c(r[t], i), n);
	a.flags = 16;
}
function Ar(e, t, n = Q, r = !1) {
	if (n) {
		let i = n[e] || (n[e] = []), a = t.__weh ||= (...r) => {
			Ke();
			let i = Ba(n), a = bn(t, n, e, r);
			return i(), qe(), a;
		};
		return r ? i.unshift(a) : i.push(a), a;
	}
}
var jr = (e) => (t, n = Q) => {
	Ua && e !== "sp" || Ar(e, (...e) => t(...e), n);
}, Mr = jr("bm"), Nr = jr("m"), Pr = jr("bu"), Fr = jr("u"), Ir = jr("bum"), Lr = jr("um"), Rr = jr("sp"), zr = jr("rtg"), Br = jr("rtc");
function Vr(e, t = Q) {
	Ar("ec", e, t);
}
var Hr = "components", Ur = /* @__PURE__ */ Symbol.for("v-ndc");
function Wr(e) {
	return g(e) ? Gr(Hr, e, !1) || e : e || Ur;
}
function Gr(e, t, n = !0, r = !1) {
	let i = B || Q;
	if (i) {
		let n = i.type;
		if (e === Hr) {
			let e = Qa(n, !1);
			if (e && (e === t || e === E(t) || e === re(E(t)))) return n;
		}
		let a = Kr(i[e] || n[e], t) || Kr(i.appContext[e], t);
		return !a && r ? n : a;
	}
}
function Kr(e, t) {
	return e && (e[t] || e[E(t)] || e[re(E(t))]);
}
function qr(e, t, n, r) {
	let i, a = n && n[r], o = d(e);
	if (o || g(e)) {
		let n = o && /* @__PURE__ */ Kt(e), r = !1, s = !1;
		n && (r = !/* @__PURE__ */ Jt(e), s = /* @__PURE__ */ qt(e), e = ot(e)), i = Array(e.length);
		for (let n = 0, o = e.length; n < o; n++) i[n] = t(r ? s ? Qt(Zt(e[n])) : Zt(e[n]) : e[n], n, void 0, a && a[n]);
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
function W(e, t, n, r, i, a) {
	if (n ??= {}, B.ce || B.parent && wr(B.parent) && B.parent.ce) {
		let e = a != null && n.key == null ? s({}, n, { key: a }) : n, i = Object.keys(e).length > 0;
		return t !== "default" && (e.name = t), q(), Y(K, null, [Z("slot", e, r && r())], i ? -2 : 64);
	}
	let o = e[t];
	o && o._c && (o._d = !1);
	let c = pa.length;
	q();
	let l;
	try {
		let i = o && Jr(o(n)), s = n.key || a || i && i.key;
		l = Y(K, { key: (s && !_(s) ? s : `_${t}`) + (!i && r ? "_fb" : "") }, i || (r ? r() : []), i && e._ === 1 ? 64 : -2);
	} catch (e) {
		for (let e = pa.length; e > c; e--) ha();
		throw e;
	} finally {
		o && o._c && (o._d = !0);
	}
	return !i && l.scopeId && (l.slotScopeIds = [l.scopeId + "-s"]), l;
}
function Jr(e) {
	return e.some((e) => !ya(e) || !(e.type === da || e.type === K && !Jr(e.children))) ? e : null;
}
var Yr = (e) => e ? Ha(e) ? Za(e) : Yr(e.parent) : null, Xr = /* @__PURE__ */ s(/* @__PURE__ */ Object.create(null), {
	$: (e) => e,
	$el: (e) => e.vnode.el,
	$data: (e) => e.data,
	$props: (e) => e.props,
	$attrs: (e) => e.attrs,
	$slots: (e) => e.slots,
	$refs: (e) => e.refs,
	$parent: (e) => Yr(e.parent),
	$root: (e) => Yr(e.root),
	$host: (e) => e.ce,
	$emit: (e) => e.emit,
	$options: (e) => oi(e),
	$forceUpdate: (e) => e.f ||= () => {
		jn(e.update);
	},
	$nextTick: (e) => e.n ||= kn.bind(e.proxy),
	$watch: (e) => Zn.bind(e)
}), Zr = (e, n) => e !== t && !e.__isScriptSetup && u(e, n), Qr = {
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
			else if (Zr(i, n)) return s[n] = 1, i[n];
			else if (a !== t && u(a, n)) return s[n] = 2, a[n];
			else if (u(o, n)) return s[n] = 3, o[n];
			else if (r !== t && u(r, n)) return s[n] = 4, r[n];
			else ti && (s[n] = 0);
		}
		let d = Xr[n], f, p;
		if (d) return n === "$attrs" && N(e.attrs, "get", ""), d(e);
		if ((f = c.__cssModules) && (f = f[n])) return f;
		if (r !== t && u(r, n)) return s[n] = 4, r[n];
		if (p = l.config.globalProperties, u(p, n)) return p[n];
	},
	set({ _: e }, n, r) {
		let { data: i, setupState: a, ctx: o } = e;
		return Zr(a, n) ? (a[n] = r, !0) : i !== t && u(i, n) ? (i[n] = r, !0) : u(e.props, n) || n[0] === "$" && n.slice(1) in e ? !1 : (o[n] = r, !0);
	},
	has({ _: { data: e, setupState: n, accessCache: r, ctx: i, appContext: a, props: o, type: s } }, c) {
		let l;
		return !!(r[c] || e !== t && c[0] !== "$" && u(e, c) || Zr(n, c) || u(o, c) || u(i, c) || u(Xr, c) || u(a.config.globalProperties, c) || (l = s.__cssModules) && l[c]);
	},
	defineProperty(e, t, n) {
		return n.get == null ? u(n, "value") && this.set(e, t, n.value, null) : e._.accessCache[t] = 0, Reflect.defineProperty(e, t, n);
	}
};
function $r(e) {
	return d(e) ? e.reduce((e, t) => (e[t] = null, e), {}) : e;
}
function ei(e, t) {
	let n = $r(e);
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
var ti = !0;
function ni(e) {
	let t = oi(e), n = e.proxy, i = e.ctx;
	ti = !1, t.beforeCreate && ii(t.beforeCreate, e, "bc");
	let { data: a, computed: o, methods: s, watch: c, provide: l, inject: u, created: f, beforeMount: p, mounted: m, beforeUpdate: g, updated: _, activated: y, deactivated: b, beforeDestroy: x, beforeUnmount: S, destroyed: C, unmounted: w, render: T, renderTracked: ee, renderTriggered: te, errorCaptured: E, serverPrefetch: ne, expose: D, inheritAttrs: re, components: ie, directives: ae, filters: oe } = t;
	if (u && ri(u, i, null), s) for (let e in s) {
		let t = s[e];
		h(t) && (i[e] = t.bind(n));
	}
	if (a) {
		let t = a.call(n, n);
		v(t) && (e.data = /* @__PURE__ */ Vt(t));
	}
	if (ti = !0, o) for (let e in o) {
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
	if (c) for (let e in c) ai(c[e], i, n, e);
	if (l) {
		let e = h(l) ? l.call(n) : l;
		Reflect.ownKeys(e).forEach((t) => {
			Wn(t, e[t]);
		});
	}
	f && ii(f, e, "c");
	function O(e, t) {
		d(t) ? t.forEach((t) => e(t.bind(n))) : t && e(t.bind(n));
	}
	if (O(Mr, p), O(Nr, m), O(Pr, g), O(Fr, _), O(Er, y), O(Dr, b), O(Vr, E), O(Br, ee), O(zr, te), O(Ir, S), O(Lr, w), O(Rr, ne), d(D)) {
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
	T && e.render === r && (e.render = T), re != null && (e.inheritAttrs = re), ie && (e.components = ie), ae && (e.directives = ae), ne && yr(e);
}
function ri(e, t, n = r) {
	d(e) && (e = di(e));
	for (let n in e) {
		let r = e[n], i;
		i = v(r) ? "default" in r ? Gn(r.from || n, r.default, !0) : Gn(r.from || n) : Gn(r), /* @__PURE__ */ F(i) ? Object.defineProperty(t, n, {
			enumerable: !0,
			configurable: !0,
			get: () => i.value,
			set: (e) => i.value = e
		}) : t[n] = i;
	}
}
function ii(e, t, n) {
	bn(d(e) ? e.map((e) => e.bind(t.proxy)) : e.bind(t.proxy), t, n);
}
function ai(e, t, n, r) {
	let i = r.includes(".") ? Qn(n, r) : () => n[r];
	if (g(e)) {
		let n = t[e];
		h(n) && H(i, n);
	} else if (h(e)) H(i, e.bind(n));
	else if (v(e)) {
		if (d(e)) e.forEach((e) => ai(e, t, n, r));
		else {
			let r = h(e.handler) ? e.handler.bind(n) : t[e.handler];
			h(r) && H(i, r, e);
		}
	}
}
function oi(e) {
	let t = e.type, { mixins: n, extends: r } = t, { mixins: i, optionsCache: a, config: { optionMergeStrategies: o } } = e.appContext, s = a.get(t), c;
	return s ? c = s : !i.length && !n && !r ? c = t : (c = {}, i.length && i.forEach((e) => si(c, e, o, !0)), si(c, t, o)), v(t) && a.set(t, c), c;
}
function si(e, t, n, r = !1) {
	let { mixins: i, extends: a } = t;
	a && si(e, a, n, !0), i && i.forEach((t) => si(e, t, n, !0));
	for (let i in t) if (!(r && i === "expose")) {
		let r = ci[i] || n && n[i];
		e[i] = r ? r(e[i], t[i]) : t[i];
	}
	return e;
}
var ci = {
	data: li,
	props: mi,
	emits: mi,
	methods: pi,
	computed: pi,
	beforeCreate: fi,
	created: fi,
	beforeMount: fi,
	mounted: fi,
	beforeUpdate: fi,
	updated: fi,
	beforeDestroy: fi,
	beforeUnmount: fi,
	destroyed: fi,
	unmounted: fi,
	activated: fi,
	deactivated: fi,
	errorCaptured: fi,
	serverPrefetch: fi,
	components: pi,
	directives: pi,
	watch: hi,
	provide: li,
	inject: ui
};
function li(e, t) {
	return t ? e ? function() {
		return s(h(e) ? e.call(this, this) : e, h(t) ? t.call(this, this) : t);
	} : t : e;
}
function ui(e, t) {
	return pi(di(e), di(t));
}
function di(e) {
	if (d(e)) {
		let t = {};
		for (let n = 0; n < e.length; n++) t[e[n]] = e[n];
		return t;
	}
	return e;
}
function fi(e, t) {
	return e ? [...new Set([].concat(e, t))] : t;
}
function pi(e, t) {
	return e ? s(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function mi(e, t) {
	return e ? d(e) && d(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : s(/* @__PURE__ */ Object.create(null), $r(e), $r(t ?? {})) : t;
}
function hi(e, t) {
	if (!e) return t;
	if (!t) return e;
	let n = s(/* @__PURE__ */ Object.create(null), e);
	for (let r in t) n[r] = fi(e[r], t[r]);
	return n;
}
function gi() {
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
var _i = 0;
function vi(e, t) {
	return function(n, r = null) {
		h(n) || (n = s({}, n)), r != null && !v(r) && (r = null);
		let i = gi(), a = /* @__PURE__ */ new WeakSet(), o = [], c = !1, l = i.app = {
			_uid: _i++,
			_component: n,
			_props: r,
			_container: null,
			_context: i,
			_instance: null,
			version: ro,
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
					return u.appContext = i, s === !0 ? s = "svg" : s === !1 && (s = void 0), o && t ? t(u, a) : e(u, a, s), c = !0, l._container = a, a.__vue_app__ = l, Za(u.component);
				}
			},
			onUnmount(e) {
				o.push(e);
			},
			unmount() {
				c && (bn(o, l._instance, 16), e(null, l._container), delete l._container.__vue_app__);
			},
			provide(e, t) {
				return i.provides[e] = t, l;
			},
			runWithContext(e) {
				let t = yi;
				yi = l;
				try {
					return e();
				} finally {
					yi = t;
				}
			}
		};
		return l;
	};
}
var yi = null, bi = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${E(t)}Modifiers`] || e[`${D(t)}Modifiers`];
function xi(e, n, ...r) {
	if (e.isUnmounted) return;
	let i = e.vnode.props || t, a = r, o = n.startsWith("update:"), s = o && bi(i, n.slice(7));
	s && (s.trim && (a = r.map((e) => g(e) ? e.trim() : e)), s.number && (a = a.map(se)));
	let c, l = i[c = ie(n)] || i[c = ie(E(n))];
	!l && o && (l = i[c = ie(D(n))]), l && bn(l, e, 6, a);
	let u = i[c + "Once"];
	if (u) {
		if (!e.emitted) e.emitted = {};
		else if (e.emitted[c]) return;
		e.emitted[c] = !0, bn(u, e, 6, a);
	}
}
var Si = /* @__PURE__ */ new WeakMap();
function Ci(e, t, n = !1) {
	let r = n ? Si : t.emitsCache, i = r.get(e);
	if (i !== void 0) return i;
	let a = e.emits, o = {}, c = !1;
	if (!h(e)) {
		let r = (e) => {
			let n = Ci(e, t, !0);
			n && (c = !0, s(o, n));
		};
		!n && t.mixins.length && t.mixins.forEach(r), e.extends && r(e.extends), e.mixins && e.mixins.forEach(r);
	}
	return !a && !c ? (v(e) && r.set(e, null), null) : (d(a) ? a.forEach((e) => o[e] = null) : s(o, a), v(e) && r.set(e, o), o);
}
function wi(e, t) {
	return !e || !a(t) ? !1 : (t = t.slice(2), t = t === "Once" ? t : t.replace(/Once$/, ""), u(e, t[0].toLowerCase() + t.slice(1)) || u(e, D(t)) || u(e, t));
}
function Ti(e) {
	let { type: t, vnode: n, proxy: r, withProxy: i, propsOptions: [a], slots: s, attrs: c, emit: l, render: u, renderCache: d, props: f, data: p, setupState: m, ctx: h, inheritAttrs: g } = e, _ = Vn(e), v, y;
	try {
		if (n.shapeFlag & 4) {
			let e = i || r, t = e;
			v = Oa(u.call(t, e, d, f, m, p, h)), y = c;
		} else {
			let e = t;
			v = Oa(e.length > 1 ? e(f, {
				attrs: c,
				slots: s,
				emit: l
			}) : e(f, null)), y = t.props ? c : Di(c);
		}
	} catch (t) {
		pa.length = 0, xn(t, e, 1), v = Z(da);
	}
	let b = v;
	if (y && g !== !1) {
		let e = Object.keys(y), { shapeFlag: t } = b;
		e.length && t & 7 && (a && e.some(o) && (y = Oi(y, a)), b = Ta(b, y, !1, !0));
	}
	return n.dirs && (b = Ta(b, null, !1, !0), b.dirs = b.dirs ? b.dirs.concat(n.dirs) : n.dirs), n.transition && gr(tr(b.type) && hr(b) || b, n.transition), v = b, Vn(_), v;
}
function Ei(e, t = !0) {
	let n;
	for (let t = 0; t < e.length; t++) {
		let r = e[t];
		if (ya(r)) {
			if (r.type !== da || r.children === "v-if") {
				if (n) return;
				n = r;
			}
		} else return;
	}
	return n;
}
var Di = (e) => {
	let t;
	for (let n in e) (n === "class" || n === "style" || a(n)) && ((t ||= {})[n] = e[n]);
	return t;
}, Oi = (e, t) => {
	let n = {};
	for (let r in e) o(r) && r.slice(9) in t || (n[r] = e[r]);
	return n;
};
function ki(e, t, n) {
	let { props: r, children: i, component: a } = e, { props: o, children: s, patchFlag: c } = t, l = a.emitsOptions;
	if (t.dirs || t.transition) return !0;
	if (n && c >= 0) {
		if (c & 1024) return !0;
		if (c & 16) return r ? Ai(r, o, l) : !!o;
		if (c & 8) {
			let e = t.dynamicProps;
			for (let t = 0; t < e.length; t++) {
				let n = e[t];
				if (ji(o, r, n) && !wi(l, n)) return !0;
			}
		}
	} else return (i || s) && (!s || !s.$stable) ? !0 : r === o ? !1 : r ? !o || Ai(r, o, l) : !!o;
	return !1;
}
function Ai(e, t, n) {
	let r = Object.keys(t);
	if (r.length !== Object.keys(e).length) return !0;
	for (let i = 0; i < r.length; i++) {
		let a = r[i];
		if (!u(e, a) || ji(t, e, a) && !wi(n, a)) return !0;
	}
	return !1;
}
function ji(e, t, n) {
	let r = e[n], i = t[n];
	return n === "style" && v(r) && v(i) ? !Se(r, i) : r !== i;
}
function Mi({ vnode: e, parent: t, suspense: n }, r) {
	for (; t;) {
		let n = t.subTree;
		if (n.suspense && n.suspense.activeBranch === e && (n.suspense.vnode.el = n.el = r, e = n), n === e) (e = t.vnode).el = r, t = t.parent;
		else break;
	}
	n && n.activeBranch === e && (n.vnode.el = r);
}
var Ni = {}, Pi = () => Object.create(Ni), Fi = (e) => Object.getPrototypeOf(e) === Ni;
function Ii(e, t, n, r = !1) {
	let i = {}, a = Pi();
	e.propsDefaults = /* @__PURE__ */ Object.create(null), Ri(e, t, i, a);
	for (let t in e.propsOptions[0]) t in i || (i[t] = void 0);
	e.props = n ? r ? i : /* @__PURE__ */ Ht(i) : e.type.props ? i : a, e.attrs = a;
}
function Li(e, t, n, r) {
	let { props: i, attrs: a, vnode: { patchFlag: o } } = e, s = /* @__PURE__ */ P(i), [c] = e.propsOptions, l = !1;
	if ((r || o > 0) && !(o & 16)) {
		if (o & 8) {
			let n = e.vnode.dynamicProps;
			for (let r = 0; r < n.length; r++) {
				let o = n[r];
				if (wi(e.emitsOptions, o)) continue;
				let d = t[o];
				if (c) {
					if (u(a, o)) d !== a[o] && (a[o] = d, l = !0);
					else {
						let t = E(o);
						i[t] = zi(c, s, t, d, e, !1);
					}
				} else d !== a[o] && (a[o] = d, l = !0);
			}
		}
	} else {
		Ri(e, t, i, a) && (l = !0);
		let r;
		for (let a in s) t && (u(t, a) || (r = D(a)) !== a && u(t, r)) || (c ? n && (n[a] !== void 0 || n[r] !== void 0) && (i[a] = zi(c, s, a, void 0, e, !0)) : delete i[a]);
		if (a !== s) for (let e in a) t && u(t, e) || (delete a[e], l = !0);
	}
	l && rt(e.attrs, "set", "");
}
function Ri(e, n, r, i) {
	let [a, o] = e.propsOptions, s = !1, c;
	if (n) for (let t in n) {
		if (T(t)) continue;
		let l = n[t], d;
		a && u(a, d = E(t)) ? !o || !o.includes(d) ? r[d] = l : (c ||= {})[d] = l : wi(e.emitsOptions, t) || t in i && l === i[t] || (i[t] = l, s = !0);
	}
	if (o) {
		let n = /* @__PURE__ */ P(r), i = c || t;
		for (let t = 0; t < o.length; t++) {
			let s = o[t];
			r[s] = zi(a, n, s, i[s], e, !u(i, s));
		}
	}
	return s;
}
function zi(e, t, n, r, i, a) {
	let o = e[n];
	if (o != null) {
		let e = u(o, "default");
		if (e && r === void 0) {
			let e = o.default;
			if (o.type !== Function && !o.skipFactory && h(e)) {
				let { propsDefaults: a } = i;
				if (n in a) r = a[n];
				else {
					let o = Ba(i);
					r = a[n] = e.call(null, t), o();
				}
			} else r = e;
			i.ce && i.ce._setProp(n, r);
		}
		o[0] && (a && !e ? r = !1 : o[1] && (r === "" || r === D(n)) && (r = !0));
	}
	return r;
}
var Bi = /* @__PURE__ */ new WeakMap();
function Vi(e, r, i = !1) {
	let a = i ? Bi : r.propsCache, o = a.get(e);
	if (o) return o;
	let c = e.props, l = {}, f = [], p = !1;
	if (!h(e)) {
		let t = (e) => {
			p = !0;
			let [t, n] = Vi(e, r, !0);
			s(l, t), n && f.push(...n);
		};
		!i && r.mixins.length && r.mixins.forEach(t), e.extends && t(e.extends), e.mixins && e.mixins.forEach(t);
	}
	if (!c && !p) return v(e) && a.set(e, n), n;
	if (d(c)) for (let e = 0; e < c.length; e++) {
		let n = E(c[e]);
		Hi(n) && (l[n] = t);
	}
	else if (c) for (let e in c) {
		let t = E(e);
		if (Hi(t)) {
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
function Hi(e) {
	return e[0] !== "$" && !T(e);
}
var Ui = (e) => e === "_" || e === "_ctx" || e === "$stable", Wi = (e) => d(e) ? e.map(Oa) : [Oa(e)], Gi = (e, t, n) => {
	if (t._n) return t;
	let r = V((...e) => Wi(t(...e)), n);
	return r._c = !1, r;
}, Ki = (e, t, n) => {
	let r = e._ctx;
	for (let n in e) {
		if (Ui(n)) continue;
		let i = e[n];
		if (h(i)) t[n] = Gi(n, i, r);
		else if (i != null) {
			let e = Wi(i);
			t[n] = () => e;
		}
	}
}, qi = (e, t) => {
	let n = Wi(t);
	e.slots.default = () => n;
}, Ji = (e, t, n) => {
	for (let r in t) (n || !Ui(r)) && (e[r] = t[r]);
}, Yi = (e, t, n) => {
	let r = e.slots = Pi();
	if (e.vnode.shapeFlag & 32) {
		let e = t._;
		e ? (Ji(r, t, n), n && O(r, "_", e, !0)) : Ki(t, r);
	} else t && qi(e, t);
}, Xi = (e, n, r) => {
	let { vnode: i, slots: a } = e, o = !0, s = t;
	if (i.shapeFlag & 32) {
		let e = n._;
		e ? r && e === 1 ? o = !1 : Ji(a, n, r) : (o = !n.$stable, Ki(n, a)), s = n;
	} else n && (qi(e, n), s = { default: 1 });
	if (o) for (let e in a) !Ui(e) && s[e] == null && delete a[e];
}, G = la;
function Zi(e) {
	return Qi(e);
}
function Qi(e, i) {
	let a = le();
	a.__VUE__ = !0;
	let { insert: o, remove: s, patchProp: c, createElement: l, createText: u, createComment: d, setText: f, setElementText: p, parentNode: m, nextSibling: h, setScopeId: g = r, insertStaticContent: _ } = e, v = (e, t, r, i = null, a = null, o = null, s = void 0, c = null, l = !!t.dynamicChildren) => {
		if (e === t) return;
		e && !ba(e, t) && (i = ye(e), k(e, a, o, !0), e = null), t.patchFlag === -2 && (l = !1, t.dynamicChildren = null), t.dynamicChildren && e && e.dynamicChildren && e.dynamicChildren.hasOnce && (t.dynamicChildren === n && (t.dynamicChildren = []), t.dynamicChildren.hasOnce = !0);
		let { type: u, ref: d, shapeFlag: f } = t;
		switch (u) {
			case ua:
				y(e, t, r, i);
				break;
			case da:
				b(e, t, r, i);
				break;
			case fa:
				e ?? x(t, r, i, s);
				break;
			case K:
				ie(e, t, r, i, a, o, s, c, l);
				break;
			default: f & 1 ? w(e, t, r, i, a, o, s, c, l) : f & 6 ? ae(e, t, r, i, a, o, s, c, l) : (f & 64 || f & 128) && u.process(e, t, r, i, a, o, s, c, l, xe);
		}
		d != null && a ? Sr(d, e && e.ref, o, t || e, !t) : d == null && e && e.ref != null && Sr(e.ref, null, o, e, !0);
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
		if (d = e.el = l(e.type, a, m && m.is, m), h & 8 ? p(d, e.children) : h & 16 && E(e.children, d, null, r, i, $i(e, a), s, u), _ && Un(e, null, r, "created"), te(d, e, e.scopeId, s, r), m) {
			for (let e in m) e !== "value" && !T(e) && c(d, e, null, m[e], a, r);
			"value" in m && c(d, "value", null, m.value, a), (f = m.onVnodeBeforeMount) && Ma(f, r, e);
		}
		_ && Un(e, null, r, "beforeMount");
		let v = ta(i, g);
		v ? g.beforeEnter(d) : g && !g.persisted && (d[ca] = !0), o(d, t, n), ((f = m && m.onVnodeMounted) || v || _) && G(() => {
			try {
				f && Ma(f, r, e), v && g.enter(d), _ && Un(e, null, r, "mounted");
			} finally {}
		}, i);
	}, te = (e, t, n, r, i) => {
		if (n && g(e, n), r) for (let t = 0; t < r.length; t++) g(e, r[t]);
		if (i) {
			let n = i.subTree;
			if (t === n || sa(n.type) && (n.ssContent === t || n.ssFallback === t)) {
				let t = i.vnode;
				te(e, t, t.scopeId, t.slotScopeIds, i.parent);
			}
		}
	}, E = (e, t, n, r, i, a, o, s, c = 0) => {
		for (let l = c; l < e.length; l++) {
			let c = e[l] = s ? ka(e[l]) : Oa(e[l]);
			v(null, c, t, n, r, i, a, o, s);
		}
	}, ne = (e, n, r, i, a, o, s) => {
		let l = n.el = e.el, { patchFlag: u, dynamicChildren: d, dirs: f } = n;
		u |= e.patchFlag & 16;
		let m = e.props || t, h = n.props || t, g;
		if (r && ea(r, !1), (g = h.onVnodeBeforeUpdate) && Ma(g, r, n, e), f && Un(n, e, r, "beforeUpdate"), r && ea(r, !0), d && (!e.dynamicChildren || e.dynamicChildren.length !== d.length) && (u = 0, s = !1, d = null), (m.innerHTML && h.innerHTML == null || m.textContent && h.textContent == null) && p(l, ""), d ? D(e.dynamicChildren, d, l, r, i, $i(n, a), o) : s || de(e, n, l, null, r, i, $i(n, a), o, !1), u > 0) {
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
			g && Ma(g, r, n, e), f && Un(n, e, r, "updated");
		}, i);
	}, D = (e, t, n, r, i, a, o) => {
		for (let s = 0; s < t.length; s++) {
			let c = e[s], l = t[s], u = c.el || oa(c), d = u && (c.type === K || !ba(c, l) || c.shapeFlag & 198) ? m(u) : n;
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
		h && (c = c ? c.concat(h) : h), e == null ? (o(d, n, r), o(f, n, r), E(t.children || [], n, f, i, a, s, c, l)) : p > 0 && p & 64 && m && e.dynamicChildren && e.dynamicChildren.length === m.length ? (D(e.dynamicChildren, m, n, i, a, s, c), (t.key != null || i && t === i.subTree) && na(e, t, !0)) : de(e, t, n, f, i, a, s, c, l);
	}, ae = (e, t, n, r, i, a, o, s, c) => {
		t.slotScopeIds = s, e == null ? t.shapeFlag & 512 ? i.ctx.activate(t, n, r, o, c) : O(t, n, r, i, a, o, c) : se(e, t, c);
	}, O = (e, t, n, r, i, a, o) => {
		let s = e.component = Ia(e, r, i);
		if (Tr(e) && (s.ctx.renderer = xe), Wa(s, !1, o), s.asyncDep) {
			if (i && i.registerDep(s, ce, o, a), !e.el) {
				let r = s.subTree = Z(da);
				b(null, r, t, n), e.placeholder = r.el;
			}
		} else ce(s, e, t, n, i, a, o);
	}, se = (e, t, n) => {
		let r = t.component = e.component;
		if (ki(e, t, n)) {
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
					let n = ia(e);
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
				ea(e, !1), t ? (t.el = c.el, ue(e, t, o)) : t = c, n && oe(n), (d = t.props && t.props.onVnodeBeforeUpdate) && Ma(d, s, t, c), ea(e, !0);
				let f = Ti(e), p = e.subTree;
				e.subTree = f, v(p, f, m(p.el || oa(p)), ye(p), e, i, a), t.el = f.el, u === null && Mi(e, f.el), r && G(r, i), (d = t.props && t.props.onVnodeUpdated) && G(() => Ma(d, s, t, c), i);
			} else {
				let o, { el: s, props: c } = t, { bm: l, m: u, parent: d, root: f, type: p } = e, m = wr(t);
				if (ea(e, !1), l && oe(l), !m && (o = c && c.onVnodeBeforeMount) && Ma(o, d, t), ea(e, !0), s && Ce) {
					let t = () => {
						e.subTree = Ti(e), Ce(s, e.subTree, e, i, null);
					};
					m && p.__asyncHydrate ? p.__asyncHydrate(s, e, t) : t();
				} else {
					f.ce && f.ce._hasShadowRoot() && f.ce._injectChildStyle(p, e.parent ? e.parent.type : void 0);
					let o = e.subTree = Ti(e);
					v(null, o, n, r, e, i, a), t.el = o.el;
				}
				if (u && G(u, i), !m && (o = c && c.onVnodeMounted)) {
					let e = t;
					G(() => Ma(o, d, e), i);
				}
				(t.shapeFlag & 256 || d && wr(d.vnode) && d.vnode.shapeFlag & 256) && e.a && G(e.a, i), e.isMounted = !0, t = n = r = null;
			}
		};
		e.scope.on();
		let c = e.effect = new je(s);
		e.scope.off();
		let l = e.update = c.run.bind(c), u = e.job = c.runIfDirty.bind(c);
		u.i = e, u.id = e.uid, c.scheduler = () => jn(u), ea(e, !0), l();
	}, ue = (e, t, n) => {
		t.component = e;
		let r = e.vnode.props;
		e.vnode = t, e.next = null, Li(e, t.props, r, n), Xi(e, t.children, n), Ke(), Pn(e), qe();
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
			let n = t[p] = l ? ka(t[p]) : Oa(t[p]);
			v(e[p], n, r, null, a, o, s, c, l);
		}
		u > d ? ve(e, a, o, !0, !1, f) : E(t, r, i, a, o, s, c, l, f);
	}, pe = (e, t, r, i, a, o, s, c, l) => {
		let u = 0, d = t.length, f = e.length - 1, p = d - 1;
		for (; u <= f && u <= p;) {
			let n = e[u], i = t[u] = l ? ka(t[u]) : Oa(t[u]);
			if (ba(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			u++;
		}
		for (; u <= f && u <= p;) {
			let n = e[f], i = t[p] = l ? ka(t[p]) : Oa(t[p]);
			if (ba(n, i)) v(n, i, r, null, a, o, s, c, l);
			else break;
			f--, p--;
		}
		if (u > f) {
			if (u <= p) {
				let e = p + 1, n = e < d ? t[e].el : i;
				for (; u <= p;) v(null, t[u] = l ? ka(t[u]) : Oa(t[u]), r, n, a, o, s, c, l), u++;
			}
		} else if (u > p) for (; u <= f;) k(e[u], a, o, !0), u++;
		else {
			let m = u, h = u, g = /* @__PURE__ */ new Map();
			for (u = h; u <= p; u++) {
				let e = t[u] = l ? ka(t[u]) : Oa(t[u]);
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
				else for (_ = h; _ <= p; _++) if (C[_ - h] === 0 && ba(n, t[_])) {
					i = _;
					break;
				}
				i === void 0 ? k(n, a, o, !0) : (C[i - h] = u + 1, i >= S ? S = i : x = !0, v(n, t[i], r, null, a, o, s, c, l), y++);
			}
			let w = x ? ra(C) : n;
			for (_ = w.length - 1, u = b - 1; u >= 0; u--) {
				let e = h + u, n = t[e], f = t[e + 1], p = e + 1 < d ? f.el || oa(f) : i;
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
		} else if (c === fa) S(e, t, n);
		else if (r !== 2 && d & 1 && l) {
			if (r === 0) l.persisted && !a[pr] ? o(a, t, n) : (l.beforeEnter(a), o(a, t, n), G(() => l.enter(a), i));
			else {
				let { leave: r, delayLeave: i, afterLeave: c } = l, u = () => {
					e.ctx.isUnmounted ? s(a) : o(a, t, n);
				}, d = () => {
					let e = a._isLeaving || !!a[pr];
					a._isLeaving && a[pr](!0), l.persisted && !e ? u() : r(a, () => {
						u(), c && c();
					});
				};
				i ? i(a, u, d) : d();
			}
		} else o(a, t, n);
	}, k = (e, t, n, r = !1, i = !1) => {
		let { type: a, props: o, ref: s, children: c, dynamicChildren: l, shapeFlag: u, patchFlag: d, dirs: f, cacheIndex: p, memo: m } = e;
		if ((d === -2 || l && l.hasOnce) && (i = !1), s != null && (Ke(), Sr(s, null, n, e, !0), qe()), p == null || e.ctx && e.ctx !== t || (t.renderCache[p] = void 0), u & 256 && t.ctx.deactivate(e)) return;
		let h = u & 1 && f, g = !wr(e), _;
		if (g && (_ = o && o.onVnodeBeforeUnmount) && Ma(_, t, e), u & 6) _e(e.component, n, r);
		else {
			if (u & 128) {
				e.suspense.unmount(n, r);
				return;
			}
			h && Un(e, null, t, "beforeUnmount"), u & 64 ? e.type.remove(e, t, n, xe, r) : l && !l.hasOnce && (a !== K || d > 0 && d & 64) ? ve(l, t, n, !1, !0) : (a === K && d & 384 || !i && u & 16) && ve(c, t, n), r && he(e);
		}
		let v = m != null && p == null;
		(g && (_ = o && o.onVnodeUnmounted) || h || v) && G(() => {
			_ && Ma(_, t, e), h && Un(e, null, t, "unmounted"), v && (e.el = null);
		}, n);
	}, he = (e) => {
		let { type: t, el: n, anchor: r, transition: i } = e, a = t === K;
		if (a && !i) {
			ge(n, r);
			return;
		}
		if (t === fa) {
			C(e), i && !i.persisted && i.afterLeave && i.afterLeave();
			return;
		}
		let o = a ? _r(e) : e, c = () => {
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
		aa(c), aa(l), r && oe(r), i.stop(), a ? (a.flags |= 8, k(o, e, t, n)) : o && (o.transition = e.vnode.transition, k(o, e, t, n)), s && G(s, t);
		let u = () => {
			e.isUnmounted = !0;
		};
		u.flags = 16, G(u, t);
	}, ve = (e, t, n, r = !1, i = !1, a = 0) => {
		for (let o = a; o < e.length; o++) k(e[o], t, n, r, i);
	}, ye = (e) => {
		if (e.shapeFlag & 6) return ye(e.component.subTree);
		if (e.shapeFlag & 128) return e.suspense.next();
		let t = h(e.anchor || e.el), n = t && t[er];
		return n ? h(n) : t;
	}, be = (e, t, n) => {
		Ln(() => {
			e == null ? t._vnode && k(t._vnode, null, null, !0) : v(t._vnode || null, e, t, null, null, null, n), t._vnode = e;
		}, e && t._vnode ? void 0 : e && e.component ? e.component.uid : Fa());
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
		createApp: vi(be, Se)
	};
}
function $i({ type: e, props: t }, n) {
	return n === "svg" && e === "foreignObject" || n === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : n;
}
function ea({ effect: e, job: t }, n) {
	n ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function ta(e, t) {
	return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function na(e, t, n = !1) {
	let r = e.children, i = t.children;
	if (d(r) && d(i)) for (let e = 0; e < r.length; e++) {
		let t = r[e], a = i[e];
		a.shapeFlag & 1 && !a.dynamicChildren && ((a.patchFlag <= 0 || a.patchFlag === 32) && (a = i[e] = ka(i[e]), a.el = t.el), !n && a.patchFlag !== -2 && na(t, a)), a.type === ua && (a.patchFlag === -1 && (a = i[e] = ka(a)), a.el = t.el), a.type === da && !a.el && (a.el = t.el);
	}
}
function ra(e) {
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
function ia(e) {
	let t = e.subTree.component;
	if (t) return t.asyncDep && !t.asyncResolved ? t : ia(t);
}
function aa(e) {
	if (e) for (let t = 0; t < e.length; t++) e[t].flags |= 8;
}
function oa(e) {
	if (e.placeholder) return e.placeholder;
	let t = e.component;
	if (t) return oa(t.subTree);
	let n = e.suspense;
	return n && n.activeBranch ? oa(n.activeBranch) : null;
}
var sa = (e) => e.__isSuspense, ca = /* @__PURE__ */ Symbol("_deferredEnter");
function la(e, t) {
	t && t.pendingBranch ? d(e) ? t.effects.push(...e) : t.effects.push(e) : Nn(e);
}
var K = /* @__PURE__ */ Symbol.for("v-fgt"), ua = /* @__PURE__ */ Symbol.for("v-txt"), da = /* @__PURE__ */ Symbol.for("v-cmt"), fa = /* @__PURE__ */ Symbol.for("v-stc"), pa = [], ma = null;
function q(e = !1) {
	pa.push(ma = e ? null : []);
}
function ha() {
	pa.pop(), ma = pa[pa.length - 1] || null;
}
var ga = 1;
function _a(e, t = !1) {
	ga += e, e < 0 && ma && t && (ma.hasOnce = !0);
}
function va(e) {
	return e.dynamicChildren = ga > 0 ? ma || n : null, ha(), ga > 0 && ma && ma.push(e), e;
}
function J(e, t, n, r, i, a) {
	return va(X(e, t, n, r, i, a, !0));
}
function Y(e, t, n, r, i) {
	return va(Z(e, t, n, r, i, !0));
}
function ya(e) {
	return e ? e.__v_isVNode === !0 : !1;
}
function ba(e, t) {
	return e.type === t.type && e.key === t.key;
}
var xa = ({ key: e }) => e ?? null, Sa = ({ ref: e, ref_key: t, ref_for: n }) => (typeof e == "number" && (e = "" + e), e == null ? null : g(e) || /* @__PURE__ */ F(e) || h(e) ? {
	i: B,
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
		key: t && xa(t),
		ref: t && Sa(t),
		scopeId: Bn,
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
		ctx: B
	};
	return s ? (Aa(c, n), a & 128 && e.normalize(c)) : n && (c.shapeFlag |= g(n) ? 8 : 16), ga > 0 && !o && ma && (c.patchFlag > 0 || a & 6) && c.patchFlag !== 32 && ma.push(c), c;
}
var Z = Ca;
function Ca(e, t = null, n = null, r = 0, i = null, a = !1) {
	if (e && e !== Ur || (e = da), ya(e)) {
		let r = Ta(e, t, !0);
		return n && Aa(r, n), ga > 0 && !a && ma && (r.shapeFlag & 6 ? ma[ma.indexOf(e)] = r : ma.push(r)), r.patchFlag = -2, r;
	}
	if ($a(e) && (e = e.__vccOpts), t) {
		t = wa(t);
		let { class: e, style: n } = t;
		e && !g(e) && (t.class = k(e)), v(n) && (/* @__PURE__ */ Yt(n) && !d(n) && (n = s({}, n)), t.style = ue(n));
	}
	let o = g(e) ? 1 : sa(e) ? 128 : tr(e) ? 64 : v(e) ? 4 : h(e) ? 2 : 0;
	return X(e, t, n, r, i, o, a, !0);
}
function wa(e) {
	return e ? /* @__PURE__ */ Yt(e) ? s({}, e) : Fi(e) ? s({}, e[Ja] || e) : e : null;
}
function Ta(e, t, n = !1, r = !1) {
	let { props: i, ref: a, patchFlag: o, children: s, transition: c } = e, l = t ? ja(i || {}, t) : i, u = {
		__v_isVNode: !0,
		__v_skip: !0,
		type: e.type,
		props: l,
		key: l && xa(l),
		ref: t && t.ref ? n && a ? d(a) ? a.concat(Sa(t)) : [a, Sa(t)] : Sa(t) : a,
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
		ssContent: e.ssContent && Ta(e.ssContent),
		ssFallback: e.ssFallback && Ta(e.ssFallback),
		placeholder: e.placeholder,
		el: e.el,
		anchor: e.anchor,
		ctx: e.ctx,
		ce: e.ce,
		cacheIndex: e.cacheIndex
	};
	return c && r && gr(u, c.clone(u)), u;
}
function Ea(e = " ", t = 0) {
	return Z(ua, null, e, t);
}
function Da(e = "", t = !1) {
	return t ? (q(), Y(da, null, e)) : Z(da, null, e);
}
function Oa(e) {
	return e == null || typeof e == "boolean" ? Z(da) : d(e) ? Z(K, null, e.slice()) : ya(e) ? ka(e) : Z(ua, null, String(e));
}
function ka(e) {
	return e.el === null && e.patchFlag !== -1 || e.memo ? e : Ta(e);
}
function Aa(e, t) {
	let n = 0, { shapeFlag: r } = e;
	if (t == null) t = null;
	else if (d(t)) n = 16;
	else if (typeof t == "object") {
		if (r & 65) {
			let n = t.default;
			n && (n._c && (n._d = !1), Aa(e, n()), n._c && (n._d = !0));
			return;
		}
		{
			n = 32;
			let r = t._;
			!r && !Fi(t) ? t._ctx = B : r === 3 && B && (B.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
		}
	} else if (h(t)) {
		if (r & 65) {
			Aa(e, { default: t });
			return;
		}
		t = {
			default: t,
			_ctx: B
		}, n = 32;
	} else t = String(t), r & 64 ? (n = 16, t = [Ea(t)]) : n = 8;
	e.children = t, e.shapeFlag |= n;
}
function ja(...e) {
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
function Ma(e, t, n, r = null) {
	bn(e, t, 7, [n, r]);
}
var Na = /* @__PURE__ */ gi(), Pa = 0;
function Fa() {
	return Pa;
}
function Ia(e, n, r) {
	let i = e.type, a = (n ? n.appContext : e.appContext) || Na, o = {
		uid: Pa++,
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
		propsOptions: Vi(i, a),
		emitsOptions: Ci(i, a),
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
	return o.ctx = { _: o }, o.root = n ? n.root : o, o.emit = xi.bind(null, o), e.ce && e.ce(o), o;
}
var Q = null, La = () => Q || B, Ra, za;
{
	let e = le(), t = (t, n) => {
		let r;
		return (r = e[t]) || (r = e[t] = []), r.push(n), (e) => {
			r.length > 1 ? r.forEach((t) => t(e)) : r[0](e);
		};
	};
	Ra = t("__VUE_INSTANCE_SETTERS__", (e) => Q = e), za = t("__VUE_SSR_SETTERS__", (e) => Ua = e);
}
var Ba = (e) => {
	let t = Q;
	return Ra(e), e.scope.on(), () => {
		e.scope.off(), Ra(t);
	};
}, Va = () => {
	Q && Q.scope.off(), Ra(null);
};
function Ha(e) {
	return e.vnode.shapeFlag & 4;
}
var Ua = !1;
function Wa(e, t = !1, n = !1) {
	t && za(t);
	let { props: r, children: i } = e.vnode, a = Ha(e);
	Ii(e, r, a, t), Yi(e, i, n || t);
	let o = a ? Ga(e, t) : void 0;
	return t && za(!1), o;
}
function Ga(e, t) {
	let n = e.type;
	e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, Qr);
	let { setup: r } = n;
	if (r) {
		Ke();
		let n = e.setupContext = r.length > 1 ? Xa(e) : null, i = Ba(e), a = yn(r, e, 0, [e.props, n]), o = y(a);
		if (qe(), i(), (o || e.sp) && !wr(e) && yr(e), o) {
			if (a.then(Va, Va), t) return a.then((n) => {
				za(!0);
				try {
					Ka(e, n, t);
				} finally {
					za(!1);
				}
			}).catch((t) => {
				xn(t, e, 0, void 0, !0), e.ssrRender = (e, t) => t("<!---->");
			});
			e.asyncDep = a;
		} else Ka(e, a, t);
	} else qa(e, t);
}
function Ka(e, t, n) {
	h(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : v(t) && (e.setupState = an(t)), qa(e, n);
}
function qa(e, t, n) {
	let i = e.type;
	e.render ||= i.render || r;
	{
		let t = Ba(e);
		Ke();
		try {
			ni(e);
		} finally {
			qe(), t();
		}
	}
}
var Ja = /* @__PURE__ */ Symbol(), Ya = { get(e, t) {
	return N(e, "get", ""), t === Ja ? e : e[t];
} };
function Xa(e) {
	return {
		attrs: new Proxy(e.attrs, Ya),
		slots: e.slots,
		emit: e.emit,
		expose: (t) => {
			e.exposed = t || {};
		}
	};
}
function Za(e) {
	return e.exposed ? e.exposeProxy ||= new Proxy(an(Xt(e.exposed)), {
		get(t, n) {
			if (n in t) return t[n];
			if (n in Xr) return Xr[n](e);
		},
		has(e, t) {
			return t in e || t in Xr;
		}
	}) : e.proxy;
}
function Qa(e, t = !0) {
	return h(e) ? e.displayName || e.name : e.name || t && e.__name;
}
function $a(e) {
	return h(e) && "__vccOpts" in e;
}
var $ = (e, t) => /* @__PURE__ */ fn(e, t, Ua);
function eo(e, t, n) {
	try {
		_a(-1);
		let r = arguments.length;
		return r === 2 ? v(t) && !d(t) ? ya(t) ? Z(e, null, [t]) : Z(e, t) : Z(e, null, t) : (r > 3 ? n = Array.prototype.slice.call(arguments, 2) : r === 3 && ya(n) && (n = [n]), Z(e, t, n));
	} finally {
		_a(1);
	}
}
function to(e, t, n, r) {
	let i = n[r];
	if (i && no(i, e)) return i;
	let a = t();
	return a.memo = e.slice(), a.cacheIndex = r, n[r] = a;
}
function no(e, t) {
	let n = e.memo;
	if (n.length != t.length) return !1;
	for (let e = 0; e < n.length; e++) if (ae(n[e], t[e])) return !1;
	return ga > 0 && ma && ma.push(e), !0;
}
var ro = "3.5.45", io = void 0, ao = typeof window < "u" && window.trustedTypes;
if (ao) try {
	io = /* @__PURE__ */ ao.createPolicy("vue", { createHTML: (e) => e });
} catch {}
var oo = io ? (e) => io.createHTML(e) : (e) => e, so = "http://www.w3.org/2000/svg", co = "http://www.w3.org/1998/Math/MathML", lo = typeof document < "u" ? document : null, uo = lo && /* @__PURE__ */ lo.createElement("template"), fo = {
	insert: (e, t, n) => {
		t.insertBefore(e, n || null);
	},
	remove: (e) => {
		let t = e.parentNode;
		t && t.removeChild(e);
	},
	createElement: (e, t, n, r) => {
		let i = t === "svg" ? lo.createElementNS(so, e) : t === "mathml" ? lo.createElementNS(co, e) : n ? lo.createElement(e, { is: n }) : lo.createElement(e);
		return e === "select" && r && r.multiple != null && i.setAttribute("multiple", r.multiple), i;
	},
	createText: (e) => lo.createTextNode(e),
	createComment: (e) => lo.createComment(e),
	setText: (e, t) => {
		e.nodeValue = t;
	},
	setElementText: (e, t) => {
		e.textContent = t;
	},
	parentNode: (e) => e.parentNode,
	nextSibling: (e) => e.nextSibling,
	querySelector: (e) => lo.querySelector(e),
	setScopeId(e, t) {
		e.setAttribute(t, "");
	},
	insertStaticContent(e, t, n, r, i, a) {
		let o = n ? n.previousSibling : t.lastChild;
		if (i && (i === a || i.nextSibling)) for (; t.insertBefore(i.cloneNode(!0), n), i !== a && (i = i.nextSibling););
		else {
			uo.innerHTML = oo(r === "svg" ? `<svg>${e}</svg>` : r === "mathml" ? `<math>${e}</math>` : e);
			let i = uo.content;
			if (r === "svg" || r === "mathml") {
				let e = i.firstChild;
				for (; e.firstChild;) i.appendChild(e.firstChild);
				i.removeChild(e);
			}
			t.insertBefore(i, n);
		}
		return [o ? o.nextSibling : t.firstChild, n ? n.previousSibling : t.lastChild];
	}
}, po = /* @__PURE__ */ Symbol("_vtc");
function mo(e, t, n) {
	let r = e[po];
	r && (t = (t ? [t, ...r] : [...r]).join(" ")), t == null ? e.removeAttribute("class") : n ? e.setAttribute("class", t) : e.className = t;
}
var ho = /* @__PURE__ */ Symbol("_vod"), go = /* @__PURE__ */ Symbol("_vsh"), _o = /* @__PURE__ */ Symbol(""), vo = /(?:^|;)\s*display\s*:/;
function yo(e, t, n) {
	let r = e.style, i = g(n), a = !1;
	if (n && !i) {
		if (t) {
			if (g(t)) for (let e of t.split(";")) {
				let t = e.slice(0, e.indexOf(":")).trim();
				n[t] ?? xo(r, t, "");
			}
			else for (let e in t) n[e] ?? xo(r, e, "");
		}
		for (let i in n) {
			i === "display" && (a = !0);
			let o = n[i];
			o == null ? xo(r, i, "") : To(e, i, !g(t) && t ? t[i] : void 0, o) || xo(r, i, o);
		}
	} else if (i) {
		if (t !== n) {
			let e = r[_o];
			e && (n += ";" + e), r.cssText = n, a = vo.test(n);
		}
	} else t && e.removeAttribute("style");
	ho in e && (i && t === n || (e[ho] = a ? r.display : ""), e[go] && (r.display = "none"));
}
var bo = /\s*!important$/;
function xo(e, t, n) {
	if (d(n)) n.forEach((n) => xo(e, t, n));
	else if (n ??= "", t.startsWith("--")) bo.test(n) ? e.setProperty(t, n.replace(bo, ""), "important") : e.setProperty(t, n);
	else {
		let r = wo(e, t);
		bo.test(n) ? e.setProperty(D(r), n.replace(bo, ""), "important") : e[r] = n;
	}
}
var So = [
	"Webkit",
	"Moz",
	"ms"
], Co = {};
function wo(e, t) {
	let n = Co[t];
	if (n) return n;
	let r = E(t);
	if (r !== "filter" && r in e) return Co[t] = r;
	r = re(r);
	for (let n = 0; n < So.length; n++) {
		let i = So[n] + r;
		if (i in e) return Co[t] = i;
	}
	return t;
}
function To(e, t, n, r) {
	return e.tagName === "TEXTAREA" && (t === "width" || t === "height") && g(r) && n === r;
}
var Eo = "http://www.w3.org/1999/xlink";
function Do(e, t, n, r, i, a = ge(t)) {
	r && t.startsWith("xlink:") ? n == null ? e.removeAttributeNS(Eo, t.slice(6, t.length)) : e.setAttributeNS(Eo, t, n) : n == null || a && !_e(n) ? e.removeAttribute(t) : e.setAttribute(t, a ? "" : _(n) ? String(n) : n);
}
function Oo(e, t, n, r, i) {
	if (t === "innerHTML" || t === "textContent") {
		n != null && (e[t] = t === "innerHTML" ? oo(n) : n);
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
function ko(e, t, n, r) {
	e.addEventListener(t, n, r);
}
function Ao(e, t, n, r) {
	e.removeEventListener(t, n, r);
}
var jo = /* @__PURE__ */ Symbol("_vei");
function Mo(e, t, n, r, i = null) {
	let a = e[jo] || (e[jo] = {}), o = a[t];
	if (r && o) o.value = r;
	else {
		let [n, s] = Fo(t);
		r ? ko(e, n, a[t] = zo(r, i), s) : o && (Ao(e, n, o, s), a[t] = void 0);
	}
}
var No = /(Once|Passive|Capture)$/, Po = /^on:?(?:Once|Passive|Capture)$/;
function Fo(e) {
	let t, n;
	for (; (n = e.match(No)) && !Po.test(e);) t ||= {}, e = e.slice(0, e.length - n[1].length), t[n[1].toLowerCase()] = !0;
	return [e[2] === ":" ? e.slice(3) : D(e.slice(2)), t];
}
var Io = 0, Lo = /* @__PURE__ */ Promise.resolve(), Ro = () => Io ||= (Lo.then(() => Io = 0), Date.now());
function zo(e, t) {
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
				e && bn(e, t, 5, a);
			}
		} else bn(r, t, 5, [e]);
	};
	return n.value = e, n.attached = Ro(), n;
}
var Bo = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, Vo = (e, t, n, r, i, s) => {
	let c = i === "svg";
	t === "class" ? mo(e, r, c) : t === "style" ? yo(e, n, r) : a(t) ? o(t) || Mo(e, t, n, r, s) : (t[0] === "." ? (t = t.slice(1), 1) : t[0] === "^" ? (t = t.slice(1), 0) : Ho(e, t, r, c)) ? (Oo(e, t, r), e.tagName.includes("-") || t !== "value" && t !== "checked" && t !== "selected" || Do(e, t, r, c, s, t !== "value")) : e._isVueCE && (Uo(e, t) || e._def.__asyncLoader && (/[A-Z]/.test(t) || !g(r))) ? Oo(e, E(t), r, s, t) : (t === "true-value" ? e._trueValue = r : t === "false-value" && (e._falseValue = r), Do(e, t, r, c));
};
function Ho(e, t, n, r) {
	if (r) return !!(t === "innerHTML" || t === "textContent" || t in e && Bo(t) && h(n));
	if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "autocorrect" || t === "sandbox" && e.tagName === "IFRAME" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA") return !1;
	if (t === "width" || t === "height") {
		let t = e.tagName;
		if (t === "IMG" || t === "VIDEO" || t === "CANVAS" || t === "SOURCE") return !1;
	}
	return Bo(t) && g(n) ? !1 : t in e;
}
function Uo(e, t) {
	let n = e._def.props;
	if (!n) return !1;
	let r = E(t);
	return Array.isArray(n) ? n.some((e) => E(e) === r) : Object.keys(n).some((e) => E(e) === r);
}
var Wo = (e) => {
	let t = e.props["onUpdate:modelValue"] || !1;
	return d(t) ? (e) => oe(t, e) : t;
};
function Go(e) {
	e.target.composing = !0;
}
function Ko(e) {
	let t = e.target;
	t.composing && (t.composing = !1, t.dispatchEvent(new Event("input")));
}
var qo = /* @__PURE__ */ Symbol("_assign"), Jo = /* @__PURE__ */ Symbol("_initialValue");
function Yo(e, t, n) {
	return t && (e = e.trim()), n && (e = se(e)), e;
}
var Xo = {
	created(e, { modifiers: { lazy: t, trim: n, number: r } }, i) {
		e.parentNode && (e.type === "text" ? e[Jo] = e.defaultValue.replace(/[\r\n]/g, "") : e.type === "textarea" && (e[Jo] = e.defaultValue.replace(/\r\n?/g, "\n"))), e[qo] = Wo(i);
		let a = r || i.props && i.props.type === "number";
		ko(e, t ? "change" : "input", (t) => {
			t.target.composing || e[qo](Yo(e.value, n, a));
		}), (n || a) && ko(e, "change", () => {
			e.value = Yo(e.value, n, a);
		}), t || (ko(e, "compositionstart", Go), ko(e, "compositionend", Ko), ko(e, "change", Ko));
	},
	mounted(e, { value: t, modifiers: { trim: n, number: r } }) {
		let i = t ?? "", a = e[Jo];
		delete e[Jo], a !== void 0 && (e.type === "text" || e.type === "textarea") && e.value !== a ? e[qo](Yo(e.value, n, r)) : e.value = i;
	},
	beforeUpdate(e, { value: t, oldValue: n, modifiers: { lazy: r, trim: i, number: a } }, o) {
		if (e[qo] = Wo(o), e.composing) return;
		let s = (a || e.type === "number") && !/^0\d/.test(e.value) ? se(e.value) : e.value, c = t ?? "";
		if (s === c) return;
		let l = e.getRootNode();
		(l instanceof Document || l instanceof ShadowRoot) && l.activeElement === e && e.type !== "range" && (r && t === n || i && e.value.trim() === c) || (e.value = c);
	}
}, Zo = [
	"ctrl",
	"shift",
	"alt",
	"meta"
], Qo = {
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
	exact: (e, t) => Zo.some((n) => e[`${n}Key`] && !t.includes(n))
}, $o = (e, t) => {
	if (!e) return e;
	let n = e._withMods ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n, ...r) => {
		for (let e = 0; e < t.length; e++) {
			let r = Qo[t[e]];
			if (r && r(n, t)) return;
		}
		return e(n, ...r);
	}));
}, es = {
	esc: "escape",
	space: " ",
	up: "arrow-up",
	left: "arrow-left",
	right: "arrow-right",
	down: "arrow-down",
	delete: "backspace"
}, ts = (e, t) => {
	let n = e._withKeys ||= {}, r = t.join(".");
	return n[r] || (n[r] = ((n) => {
		if (!("key" in n)) return;
		let r = D(n.key);
		if (t.some((e) => e === r || es[e] === r)) return e(n);
	}));
}, ns = /* @__PURE__ */ s({ patchProp: Vo }, fo), rs;
function is() {
	return rs ||= Zi(ns);
}
var as = ((...e) => {
	let t = is().createApp(...e), { mount: n } = t;
	return t.mount = (e) => {
		let r = ss(e);
		if (!r) return;
		let i = t._component;
		h(i) || i.render || i.template || (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
		let a = n(r, !1, os(r));
		return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), a;
	}, t;
});
function os(e) {
	if (e instanceof SVGElement) return "svg";
	if (typeof MathMLElement == "function" && e instanceof MathMLElement) return "mathml";
}
function ss(e) {
	return g(e) ? document.querySelector(e) : e;
}
// node_modules/reka-ui/dist/shared/createContext.js
function cs(e, t) {
	let n = typeof e == "string" && !t ? `${e}Context` : t, r = Symbol(n);
	return [(t) => {
		let n = Gn(r, t);
		if (n || n === null) return n;
		throw Error(`Injection \`${r.toString()}\` not found. Component must be used within ${Array.isArray(e) ? `one of the following components: ${e.join(", ")}` : `\`${e}\``}`);
	}, (e) => (Wn(r, e), e)];
}
// node_modules/reka-ui/dist/shared/getActiveElement.js
function ls() {
	let e = document.activeElement;
	if (e == null) return null;
	for (; e != null && e.shadowRoot != null && e.shadowRoot.activeElement != null;) e = e.shadowRoot.activeElement;
	return e;
}
// node_modules/reka-ui/dist/shared/handleAndDispatchCustomEvent.js
function us(e, t, n) {
	let r = n.originalEvent.target, i = new CustomEvent(e, {
		bubbles: !1,
		cancelable: !0,
		detail: n
	});
	t && r.addEventListener(e, t, { once: !0 }), r.dispatchEvent(i);
}
// node_modules/@vueuse/shared/dist/index.js
function ds(e, t) {
	return Oe() ? (ke(e, t), !0) : !1;
}
function fs(e) {
	let t = !1, n, r = De(!0);
	return ((...i) => (t ||= (n = r.run(() => e(...i)), !0), n));
}
var ps = typeof window < "u" && typeof document < "u";
typeof WorkerGlobalScope < "u" && globalThis instanceof WorkerGlobalScope;
var ms = (e) => e !== void 0, hs = Object.prototype.toString, gs = (e) => hs.call(e) === "[object Object]", _s = /* #__PURE__ */ vs();
function vs() {
	var e, t;
	return ps && !!((e = window) != null && (e = e.navigator) != null && e.userAgent) && (/iP(?:ad|hone|od)/.test(window.navigator.userAgent) || ((t = window) == null || (t = t.navigator) == null ? void 0 : t.maxTouchPoints) > 2 && /iPad|Macintosh/.test(window?.navigator.userAgent));
}
function ys(e) {
	return Array.isArray(e) ? e : [e];
}
function bs(e) {
	return e || La();
}
function xs(e) {
	if (!ps) return e;
	let t = 0, n, r, i = () => {
		--t, r && t <= 0 && (r.stop(), n = void 0, r = void 0);
	};
	return ((...a) => (t += 1, r || (r = De(!0), n = r.run(() => e(...a))), ds(i), n));
}
function Ss(e) {
	return /* @__PURE__ */ Vt(/* @__PURE__ */ F(e) ? new Proxy({}, {
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
function Cs(e) {
	return Ss($(e));
}
function ws(e, ...t) {
	let n = t.flat(), r = n[0];
	return Cs(() => Object.fromEntries(typeof r == "function" ? Object.entries(/* @__PURE__ */ on(e)).filter(([e, t]) => !r(R(t), e)) : Object.entries(/* @__PURE__ */ on(e)).filter((e) => !n.includes(e[0]))));
}
function Ts(e, t) {
	bs(t) && Ir(e, t);
}
function Es(e, t, n) {
	return H(e, t, {
		...n,
		immediate: !0
	});
}
// node_modules/@vueuse/core/dist/index.js
var Ds = ps ? window : void 0;
ps && window.document, ps && window.navigator, ps && window.location;
function Os(e) {
	let t = R(e);
	return t?.$el ?? t;
}
function ks(...e) {
	let t = (e, t, n, r) => (e.addEventListener(t, n, r), () => e.removeEventListener(t, n, r)), n = $(() => {
		let t = ys(R(e[0])).filter((e) => e != null);
		return t.every((e) => typeof e != "string") ? t : void 0;
	});
	return Es(() => [
		n.value?.map((e) => Os(e)) ?? [Ds].filter((e) => e != null),
		ys(R(n.value ? e[1] : e[0])),
		ys(L(n.value ? e[2] : e[1])),
		R(n.value ? e[3] : e[2])
	], ([e, n, r, i], a, o) => {
		if (!e?.length || !n?.length || !r?.length) return;
		let s = gs(i) ? { ...i } : i, c = e.flatMap((e) => n.flatMap((n) => r.map((r) => t(e, n, r, s))));
		o(() => {
			c.forEach((e) => e());
		});
	}, { flush: "post" });
}
function As() {
	let e = /* @__PURE__ */ $t(!1), t = La();
	return t && Nr(() => {
		e.value = !0;
	}, t), e;
}
function js(e) {
	return typeof e == "function" ? e : typeof e == "string" ? (t) => t.key === e : Array.isArray(e) ? (t) => e.includes(t.key) : () => !0;
}
function Ms(...e) {
	let t, n, r = {};
	e.length === 3 ? (t = e[0], n = e[1], r = e[2]) : e.length === 2 ? typeof e[1] == "object" ? (t = !0, n = e[0], r = e[1]) : (t = e[0], n = e[1]) : (t = !0, n = e[0]);
	let { target: i = Ds, eventName: a = "keydown", passive: o = !1, dedupe: s = !1 } = r, c = js(t);
	return ks(i, a, (e) => {
		e.repeat && R(s) || c(e) && n(e);
	}, o);
}
function Ns(e) {
	return JSON.parse(JSON.stringify(e));
}
function Ps(e, t, n, r = {}) {
	var i, a;
	let { clone: o = !1, passive: s = !1, eventName: c, deep: l = !1, defaultValue: u, shouldEmit: d } = r, f = La(), p = n || f?.emit || (f == null || (i = f.$emit) == null ? void 0 : i.bind(f)) || (f == null || (a = f.proxy) == null || (a = a.$emit) == null ? void 0 : a.bind(f?.proxy)), m = c;
	t ||= "modelValue", m ||= `update:${t.toString()}`;
	let h = (e) => o ? typeof o == "function" ? o(e) : Ns(e) : e, g = () => ms(e[t]) ? h(e[t]) : u, _ = (e) => {
		d ? d(e) && p(m, e) : p(m, e);
	};
	if (s) {
		let n = /* @__PURE__ */ I(g()), r = !1;
		return H(() => e[t], (e) => {
			r || (r = !0, n.value = h(e), kn(() => r = !1));
		}), H(n, (n) => {
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
function Fs(e) {
	return e ? e.flatMap((e) => e.type === K ? Fs(e.children) : [e]) : [];
}
// node_modules/reka-ui/dist/ConfigProvider/ConfigProvider.js
var [Is, Ls] = /*#__PURE__*/ cs("ConfigProvider"), Rs = /* @__PURE__ */ new WeakMap();
function zs(e, t) {
	let n = Rs.get(e);
	n || (n = {
		owners: /* @__PURE__ */ new Set(),
		original: e.body.style.pointerEvents
	}, Rs.set(e, n)), n.owners.add(t), e.body.style.pointerEvents = "none";
}
function Bs(e, t) {
	let n = Rs.get(e);
	n?.owners.delete(t) && n.owners.size === 0 && (Rs.delete(e), e.body.style.pointerEvents = n.original);
}
// node_modules/defu/dist/defu.mjs
function Vs(e) {
	if (typeof e != "object" || !e) return !1;
	let t = Object.getPrototypeOf(e);
	return t !== null && t !== Object.prototype && Object.getPrototypeOf(t) !== null || Symbol.iterator in e ? !1 : Symbol.toStringTag in e ? Object.prototype.toString.call(e) === "[object Module]" : !0;
}
function Hs(e, t, n = ".", r) {
	if (!Vs(t)) return Hs(e, {}, n, r);
	let i = { ...t };
	for (let t of Object.keys(e)) {
		if (t === "__proto__" || t === "constructor") continue;
		let a = e[t];
		a != null && (r && r(i, t, a, n) || (i[t] = Array.isArray(a) && Array.isArray(i[t]) ? [...a, ...i[t]] : Vs(a) && Vs(i[t]) ? Hs(a, i[t], (n ? `${n}.` : "") + t.toString(), r) : a));
	}
	return i;
}
function Us(e) {
	return (...t) => t.reduce((t, n) => Hs(t, n, "", e), {});
}
var Ws = Us(), Gs = Symbol("useBodyScrollLock"), Ks = xs(() => {
	let e = /* @__PURE__ */ I(/* @__PURE__ */ new Map()), t = /* @__PURE__ */ I(), n = $(() => {
		for (let t of e.value.values()) if (t) return !0;
		return !1;
	}), r = Is({ scrollBody: /* @__PURE__ */ I(!0) }), i = null, a = () => {
		document.body.style.paddingRight = "", document.body.style.marginRight = "", Bs(document, Gs), document.documentElement.style.removeProperty("--scrollbar-width"), document.body.style.overflow = t.value ?? "", _s && i?.(), t.value = void 0;
	};
	return H(n, (e, o) => {
		if (!ps) return;
		if (!e) {
			o && a();
			return;
		}
		t.value === void 0 && (t.value = document.body.style.overflow);
		let s = window.innerWidth - document.documentElement.clientWidth, c = {
			padding: s,
			margin: 0
		}, l = r.scrollBody?.value ? typeof r.scrollBody.value == "object" ? Ws({
			padding: r.scrollBody.value.padding === !0 ? s : r.scrollBody.value.padding,
			margin: r.scrollBody.value.margin === !0 ? s : r.scrollBody.value.margin
		}, c) : c : {
			padding: 0,
			margin: 0
		};
		s > 0 && (document.body.style.paddingRight = typeof l.padding == "number" ? `${l.padding}px` : String(l.padding), document.body.style.marginRight = typeof l.margin == "number" ? `${l.margin}px` : String(l.margin), document.documentElement.style.setProperty("--scrollbar-width", `${s}px`), document.body.style.overflow = "hidden"), _s && (i = ks(document, "touchmove", (e) => Ys(e), { passive: !1 })), kn(() => {
			n.value && (zs(document, Gs), document.body.style.overflow = "hidden");
		});
	}, {
		immediate: !0,
		flush: "sync"
	}), e;
});
function qs(e) {
	let t = Math.random().toString(36).substring(2, 7), n = Ks();
	n.value.set(t, e ?? !1);
	let r = $({
		get: () => n.value.get(t) ?? !1,
		set: (e) => n.value.set(t, e)
	});
	return Ts(() => {
		n.value.delete(t);
	}), r;
}
function Js(e) {
	let t = window.getComputedStyle(e);
	if (t.overflowX === "scroll" || t.overflowY === "scroll" || t.overflowX === "auto" && e.clientWidth < e.scrollWidth || t.overflowY === "auto" && e.clientHeight < e.scrollHeight) return !0;
	{
		let t = e.parentNode;
		return !(t instanceof Element) || t.tagName === "BODY" ? !1 : Js(t);
	}
}
function Ys(e) {
	let t = e || window.event, n = t.target;
	return n instanceof Element && Js(n) ? !1 : t.touches.length > 1 || (t.preventDefault && t.cancelable && t.preventDefault(), !1);
}
// node_modules/reka-ui/dist/shared/useDirection.js
function Xs(e) {
	let t = Is({ dir: /* @__PURE__ */ I("ltr") });
	return $(() => e?.value || t.dir?.value || "ltr");
}
// node_modules/reka-ui/dist/shared/useEmitAsProps.js
function Zs(e) {
	let t = La(), n = t?.type.emits, r = {};
	return n?.length || console.warn(`No emitted event found. Please check component: ${t?.type.__name}`), n?.forEach((t) => {
		r[ie(E(t))] = (...n) => e(t, ...n);
	}), r;
}
// node_modules/reka-ui/dist/shared/useFocusGuards.js
var Qs = 0;
function $s() {
	Jn((e) => {
		if (!ps) return;
		let t = document.querySelectorAll("[data-reka-focus-guard]");
		document.body.insertAdjacentElement("afterbegin", t[0] ?? ec()), document.body.insertAdjacentElement("beforeend", t[1] ?? ec()), Qs++, e(() => {
			Qs === 1 && document.querySelectorAll("[data-reka-focus-guard]").forEach((e) => e.remove()), Qs--;
		});
	});
}
function ec() {
	let e = document.createElement("span");
	return e.setAttribute("data-reka-focus-guard", ""), e.tabIndex = 0, e.style.outline = "none", e.style.opacity = "0", e.style.position = "fixed", e.style.pointerEvents = "none", e;
}
// node_modules/reka-ui/dist/shared/useForwardExpose.js
function tc() {
	let e = La(), t = /* @__PURE__ */ I(), n = $(() => r());
	Fr(() => {
		n.value !== r() && nn(t);
	});
	function r() {
		return t.value && "$el" in t.value && ["#text", "#comment"].includes(t.value.$el.nodeName) ? t.value.$el.nextElementSibling : Os(t);
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
function nc(e) {
	let t = La(), n = Object.keys(t?.type.props ?? {}).reduce((e, n) => {
		let r = (t?.type.props[n]).default;
		return r !== void 0 && (e[n] = r), e;
	}, {}), r = /* @__PURE__ */ ln(e);
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
function rc(e, t) {
	let n = nc(e), r = t ? Zs(t) : {};
	return $(() => ({
		...n.value,
		...r
	}));
}
// node_modules/aria-hidden/dist/es2015/index.js
var ic = function(e) {
	return typeof document > "u" ? null : (Array.isArray(e) ? e[0] : e).ownerDocument.body;
}, ac = /* @__PURE__ */ new WeakMap(), oc = /* @__PURE__ */ new WeakMap(), sc = {}, cc = 0, lc = function(e) {
	return e && (e.host || lc(e.parentNode));
}, uc = function(e, t) {
	return t.map(function(t) {
		if (e.contains(t)) return t;
		var n = lc(t);
		return n && e.contains(n) ? n : (console.error("aria-hidden", t, "in not contained inside", e, ". Doing nothing"), null);
	}).filter(function(e) {
		return !!e;
	});
}, dc = function(e, t, n, r) {
	var i = uc(t, Array.isArray(e) ? e : [e]);
	sc[n] || (sc[n] = /* @__PURE__ */ new WeakMap());
	var a = sc[n], o = [], s = /* @__PURE__ */ new Set(), c = new Set(i), l = function(e) {
		e && !s.has(e) && (s.add(e), l(e.parentNode));
	};
	i.forEach(l);
	var u = function(e) {
		e && !c.has(e) && Array.prototype.forEach.call(e.children, function(e) {
			if (s.has(e)) u(e);
			else try {
				var t = e.getAttribute(r), i = t !== null && t !== "false", c = (ac.get(e) || 0) + 1, l = (a.get(e) || 0) + 1;
				ac.set(e, c), a.set(e, l), o.push(e), c === 1 && i && oc.set(e, !0), l === 1 && e.setAttribute(n, "true"), i || e.setAttribute(r, "true");
			} catch (t) {
				console.error("aria-hidden: cannot operate on ", e, t);
			}
		});
	};
	return u(t), s.clear(), cc++, function() {
		o.forEach(function(e) {
			var t = ac.get(e) - 1, i = a.get(e) - 1;
			ac.set(e, t), a.set(e, i), t || (oc.has(e) || e.removeAttribute(r), oc.delete(e)), i || e.removeAttribute(n);
		}), cc--, cc || (ac = /* @__PURE__ */ new WeakMap(), ac = /* @__PURE__ */ new WeakMap(), oc = /* @__PURE__ */ new WeakMap(), sc = {});
	};
}, fc = function(e, t, n) {
	n === void 0 && (n = "data-aria-hidden");
	var r = Array.from(Array.isArray(e) ? e : [e]), i = t || ic(e);
	return i ? (r.push.apply(r, Array.from(i.querySelectorAll("[aria-live], script"))), dc(r, i, n, "aria-hidden")) : function() {
		return null;
	};
};
// node_modules/reka-ui/dist/shared/useHideOthers.js
function pc(e) {
	let t;
	H(() => Os(e), (e) => {
		let n = !1;
		try {
			n = !!e?.closest("[popover]:not(:popover-open)");
		} catch {}
		e && !n ? t = fc(e) : t && t();
	}), Lr(() => {
		t && t();
	});
}
function mc(e, t = "reka") {
	if (e) return e;
	let n, r = Is({ useId: void 0 });
	return n = r.useId ? r.useId() : vr?.(), t ? `${t}-${n}` : n;
}
// node_modules/reka-ui/dist/shared/useSize.js
function hc(e) {
	let t = /* @__PURE__ */ I(), n = $(() => t.value?.width ?? 0), r = $(() => t.value?.height ?? 0), i;
	return Nr(() => {
		let n = Os(e);
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
	}), Lr(() => {
		i?.disconnect(), i = void 0;
	}), {
		width: n,
		height: r
	};
}
// node_modules/reka-ui/dist/shared/useStateMachine.js
function gc(e, t) {
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
function _c(e, t) {
	let n = /* @__PURE__ */ I({}), r = /* @__PURE__ */ I("none"), i = /* @__PURE__ */ I(e), a = e.value ? "mounted" : "unmounted", o, s = t.value?.ownerDocument.defaultView ?? Ds, { state: c, dispatch: l } = gc(a, {
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
		if (ps) {
			let n = new CustomEvent(e, {
				bubbles: !1,
				cancelable: !1
			});
			t.value?.dispatchEvent(n);
		}
	};
	H(e, async (e, i) => {
		let a = i !== e;
		if (await kn(), a) {
			let a = r.value, o = vc(t.value);
			e ? (l("MOUNT"), u("enter"), o === "none" && u("after-enter")) : o === "none" || o === "undefined" || n.value?.display === "none" ? (l("UNMOUNT"), u("leave"), u("after-leave")) : i && a !== o ? (l("ANIMATION_OUT"), u("leave")) : (l("UNMOUNT"), u("after-leave"));
		}
	}, { immediate: !0 });
	let d = (e) => {
		if (e.target !== t.value) return;
		let n = vc(t.value), r = n.includes(CSS.escape(e.animationName)), a = c.value === "mounted" ? "enter" : "leave";
		if (r && (u(`after-${a}`), l("ANIMATION_END"), !i.value)) {
			let e = t.value.style.animationFillMode;
			t.value.style.animationFillMode = "forwards", o = s?.setTimeout(() => {
				t.value?.style.animationFillMode === "forwards" && (t.value.style.animationFillMode = e);
			});
		}
		n === "none" && l("ANIMATION_END");
	}, f = (e) => {
		e.target === t.value && (r.value = vc(t.value));
	}, p = H(t, (e, t) => {
		e ? (n.value = getComputedStyle(e), e.addEventListener("animationstart", f), e.addEventListener("animationcancel", d), e.addEventListener("animationend", d)) : (l("ANIMATION_END"), o !== void 0 && s?.clearTimeout(o), t?.removeEventListener("animationstart", f), t?.removeEventListener("animationcancel", d), t?.removeEventListener("animationend", d));
	}, { immediate: !0 }), m = H(c, () => {
		let e = vc(t.value);
		r.value = c.value === "mounted" ? e : "none";
	});
	return Lr(() => {
		p(), m(), t.value && (t.value.removeEventListener("animationstart", f), t.value.removeEventListener("animationcancel", d), t.value.removeEventListener("animationend", d)), o !== void 0 && s?.clearTimeout(o);
	}), { isPresent: $(() => ["mounted", "unmountSuspended"].includes(c.value)) };
}
function vc(e) {
	return e && getComputedStyle(e).animationName || "none";
}
// node_modules/reka-ui/dist/Presence/Presence.js
var yc = /*#__PURE__*/ U({
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
		let { present: r, forceMount: i } = /* @__PURE__ */ on(e), a = /* @__PURE__ */ I(), { isPresent: o } = _c(r, a);
		n({ present: o });
		let s = t.default({ present: o.value });
		s = Fs(s || []);
		let c = La();
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
		return () => i.value || r.value || o.value ? eo(t.default({ present: o.value })[0], { ref: (e) => {
			let t = Os(e);
			return t?.hasAttribute === void 0 || (t?.hasAttribute("data-reka-popper-content-wrapper") ? a.value = t.firstElementChild : a.value = t), t;
		} }) : null;
	}
}), bc = /*#__PURE__*/ U({
	name: "PrimitiveSlot",
	inheritAttrs: !1,
	setup(e, { attrs: t, slots: n }) {
		return () => {
			if (!n.default) return null;
			let e = Fs(n.default()), r = e.findIndex((e) => e.type !== da);
			if (r === -1) return e;
			let i = e[r];
			delete i.props?.ref;
			let a = i.props ? ja(t, i.props) : t, o = Ta({
				...i,
				props: {}
			}, a);
			return e.length === 1 ? o : (e[r] = o, e);
		};
	}
}), xc = [
	"area",
	"img",
	"input"
], Sc = /*#__PURE__*/ U({
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
		return typeof r == "string" && xc.includes(r) ? () => eo(r, t) : r === "template" ? () => eo(bc, t, { default: n.default }) : () => eo(e.as, t, { default: n.default });
	}
}), Cc = "dismissableLayer.pointerDownOutside", wc = "dismissableLayer.focusOutside";
function Tc(e) {
	if (typeof e != "object" || !e) return !1;
	let t = e.ownerDocument?.defaultView;
	return typeof Element < "u" && e instanceof Element || !!t && e instanceof t.Element;
}
function Ec(e, t) {
	if (!Tc(t)) return !1;
	if (e.contains(t)) return !0;
	let n = t.closest("[data-dismissable-layer]"), r = e.dataset.dismissableLayer === "" ? e : e.querySelector("[data-dismissable-layer]"), i = Array.from(e.ownerDocument.querySelectorAll("[data-dismissable-layer]"));
	return !!(n && (r === n || i.indexOf(r) < i.indexOf(n)));
}
function Dc(e, t, n = !0) {
	let r = /* @__PURE__ */ I(!1), i = /* @__PURE__ */ I(() => {});
	return Jn((a) => {
		if (!ps || !R(n)) return;
		let o = t?.value?.ownerDocument ?? globalThis.document, s = async (n) => {
			let a = n.target;
			if (t?.value && a) {
				if (Ec(t.value, a)) o.removeEventListener("click", i.value), r.value = !1;
				else {
					if (n.target && !r.value) {
						let t = { originalEvent: n };
						function r() {
							us(Cc, e, t);
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
function Oc(e, t, n = !0) {
	let r = /* @__PURE__ */ I(!1);
	return Jn((i) => {
		if (!ps || !R(n)) return;
		let a = t?.value?.ownerDocument ?? globalThis.document, o = async (n) => {
			if (!t?.value) return;
			await kn(), await kn();
			let i = n.target;
			t.value && i && !Ec(t.value, i) && n.target && !r.value && us(wc, e, { originalEvent: n });
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
var kc = /*#__PURE__*/ Vt({
	layersRoot: /* @__PURE__ */ new Set(),
	layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
	branches: /* @__PURE__ */ new Set()
}), Ac = /* @__PURE__ */ U({
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
		let n = e, r = t, { forwardRef: i, currentElement: a } = tc(), o = $(() => a.value?.ownerDocument ?? globalThis.document), s = $(() => kc.layersRoot), c = $(() => a.value ? Array.from(s.value).indexOf(a.value) : -1), l = $(() => kc.layersWithOutsidePointerEventsDisabled.size > 0), u = $(() => {
			let e = Array.from(s.value), [t] = [...kc.layersWithOutsidePointerEventsDisabled].slice(-1), n = e.indexOf(t);
			return c.value >= n;
		}), d = Dc(async (e) => {
			let t = [...kc.branches].some((t) => t?.contains(e.target));
			n.present && u.value && !t && (r("pointerDownOutside", e), r("interactOutside", e), await kn(), e.defaultPrevented || r("dismiss"));
		}, a, () => n.present), f = Oc((e) => {
			let t = [...kc.branches].some((t) => t?.contains(e.target));
			n.present && !t && (r("focusOutside", e), r("interactOutside", e), e.defaultPrevented || r("dismiss"));
		}, a);
		return Ms("Escape", (e) => {
			n.present && c.value === s.value.size - 1 && (r("escapeKeyDown", e), e.defaultPrevented || r("dismiss"));
		}, { target: () => o.value?.defaultView ?? globalThis.window }), H([
			a,
			() => n.disableOutsidePointerEvents,
			() => n.present
		], ([e, t, n], r, i) => {
			if (e && n && t) {
				let t = e.ownerDocument;
				zs(t, e), kc.layersWithOutsidePointerEventsDisabled.add(e), i(() => {
					kc.layersWithOutsidePointerEventsDisabled.delete(e), Bs(t, e);
				});
			}
		}, { immediate: !0 }), H([a, () => n.present], ([e, t], n, r) => {
			e && t && (s.value.add(e), r(() => {
				s.value.delete(e);
			}));
		}, { immediate: !0 }), Jn((e) => {
			e(() => {
				a.value && (s.value.delete(a.value), kc.layersWithOutsidePointerEventsDisabled.delete(a.value));
			});
		}), (t, n) => (q(), Y(L(Sc), {
			ref: L(i),
			"as-child": e.asChild,
			as: e.as,
			"data-dismissable-layer": "",
			style: ue({ pointerEvents: l.value ? u.value ? "auto" : "none" : void 0 }),
			onFocusCapture: L(f).onFocusCapture,
			onBlurCapture: L(f).onBlurCapture,
			onPointerdownCapture: L(d).onPointerDownCapture
		}, {
			default: V(() => [W(t.$slots, "default")]),
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
}), jc = fs(() => /* @__PURE__ */ I([]));
function Mc() {
	let e = jc();
	return {
		add(t) {
			let n = e.value[0];
			t !== n && n?.pause(), e.value = Nc(e.value, t), e.value.unshift(t);
		},
		remove(t) {
			e.value = Nc(e.value, t), e.value[0]?.resume();
		}
	};
}
function Nc(e, t) {
	let n = [...e], r = n.indexOf(t);
	return r !== -1 && n.splice(r, 1), n;
}
// node_modules/reka-ui/dist/FocusScope/utils.js
var Pc = "focusScope.autoFocusOnMount", Fc = "focusScope.autoFocusOnUnmount", Ic = {
	bubbles: !1,
	cancelable: !0
};
function Lc(e, t) {
	let n = t;
	for (; n;) {
		if (e.contains(n)) return !0;
		n = n.getRootNode().host ?? null;
	}
	return !1;
}
function Rc(e, { select: t = !1 } = {}) {
	let n = ls();
	for (let r of e) if (Wc(r, { select: t }), ls() !== n) return !0;
}
function zc(e) {
	let t = Bc(e);
	return [Vc(t, e), Vc(t.reverse(), e)];
}
function Bc(e) {
	let t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, { acceptNode: (e) => {
		let t = e.tagName === "INPUT" && e.type === "hidden";
		return e.disabled || e.hidden || t ? NodeFilter.FILTER_SKIP : e.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
	} });
	for (; n.nextNode();) t.push(n.currentNode);
	return t.sort((e, t) => e.tabIndex === t.tabIndex ? 0 : e.tabIndex === 0 ? 1 : t.tabIndex === 0 ? -1 : e.tabIndex - t.tabIndex);
}
function Vc(e, t) {
	for (let n of e) if (!Hc(n, { upTo: t })) return n;
}
function Hc(e, { upTo: t }) {
	if (getComputedStyle(e).visibility === "hidden") return !0;
	for (; e;) {
		if (t !== void 0 && e === t) return !1;
		if (getComputedStyle(e).display === "none") return !0;
		e = e.parentElement;
	}
	return !1;
}
function Uc(e) {
	return e instanceof HTMLInputElement && "select" in e;
}
function Wc(e, { select: t = !1 } = {}) {
	if (e && e.focus) {
		let n = ls();
		e.focus({ preventScroll: !0 }), e !== n && Uc(e) && t && e.select();
	}
}
// node_modules/reka-ui/dist/FocusScope/FocusScope.js
var Gc = /* @__PURE__ */ U({
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
		let n = e, r = t, { currentRef: i, currentElement: a } = tc(), o = /* @__PURE__ */ I(null), s = Mc(), c = /*#__PURE__*/ Vt({
			paused: !1,
			pause() {
				this.paused = !0;
			},
			resume() {
				this.paused = !1;
			}
		});
		Jn((e) => {
			if (!ps) return;
			let t = a.value;
			if (!n.trapped) return;
			let r = t?.ownerDocument ?? document, i = t ? t.getRootNode() : r;
			function s(e) {
				if (c.paused || !t) return;
				let n = e.target;
				t.contains(n) ? o.value = n : Wc(o.value, { select: !0 });
			}
			function l(e) {
				if (c.paused || !t) return;
				let n = e.relatedTarget;
				n !== null && (t.contains(n) || Wc(o.value, { select: !0 }));
			}
			function u(e) {
				let n = o.value;
				if (n === null || !e.some((e) => e.removedNodes.length > 0)) return;
				let r = ls();
				r && t.contains(r) || t.contains(n) || Wc(t);
			}
			function d(e) {
				if (c.paused || !t) return;
				let n = e.composedPath()[0];
				Lc(t, n) || Wc(o.value, { select: !0 });
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
			let n = new CustomEvent(Pc, Ic), i = (e) => r("mountAutoFocus", e);
			e.addEventListener(Pc, i), e.dispatchEvent(n), e.removeEventListener(Pc, i), n.defaultPrevented || (Rc(Bc(e), { select: !0 }), ls() === t && Wc(e));
		}
		Jn(async (e) => {
			let t = a.value;
			if (await kn(), !t) return;
			n.present !== !1 && s.add(c);
			let i = ls();
			!t.contains(i) && n.present !== !1 && l(t, i), e(() => {
				let e = new CustomEvent(Fc, Ic), n = (e) => {
					r("unmountAutoFocus", e);
				};
				t.addEventListener(Fc, n), t.dispatchEvent(e), t.setAttribute("data-focus-scope-unmounting", ""), setTimeout(() => {
					e.defaultPrevented || Wc(i ?? document.body, { select: !0 }), t.removeEventListener(Fc, n), s.remove(c), t.removeAttribute("data-focus-scope-unmounting");
				}, 0);
			});
		}), H(() => n.present, async (e, t) => {
			if (!ps) return;
			if (e === !1 && t === !0) {
				s.remove(c);
				return;
			}
			if (e !== !0 || t !== !1) return;
			s.add(c), await kn();
			let n = a.value;
			if (!n) return;
			let r = ls();
			n.contains(r) || l(n, r);
		});
		function u(e) {
			if (!n.loop && !n.trapped || c.paused) return;
			let t = e.key === "Tab" && !e.altKey && !e.ctrlKey && !e.metaKey, r = ls();
			if (t && r) {
				let t = e.currentTarget, [i, a] = zc(t);
				i && a ? !e.shiftKey && r === a ? (e.preventDefault(), n.loop && Wc(i, { select: !0 })) : e.shiftKey && r === i && (e.preventDefault(), n.loop && Wc(a, { select: !0 })) : r === t && e.preventDefault();
			}
		}
		return (t, n) => (q(), Y(L(Sc), {
			ref_key: "currentRef",
			ref: i,
			tabindex: "-1",
			"as-child": e.asChild,
			as: e.as,
			onKeydown: u
		}, {
			default: V(() => [W(t.$slots, "default")]),
			_: 3
		}, 8, ["as-child", "as"]));
	}
}), Kc = /* @__PURE__ */ U({
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
		let t = e, n = Is({}), r = $(() => t.to ?? n.teleportTo?.value ?? "body"), i = As();
		return (t, n) => L(i) || e.forceMount ? (q(), Y(ur, {
			key: 0,
			to: r.value,
			disabled: e.disabled,
			defer: e.defer
		}, [W(t.$slots, "default")], 8, [
			"to",
			"disabled",
			"defer"
		])) : Da("v-if", !0);
	}
}), [qc, Jc] = /*#__PURE__*/ cs("PopperRoot"), Yc = /* @__PURE__ */ U({
	inheritAttrs: !1,
	__name: "PopperRoot",
	setup(e) {
		let t = /* @__PURE__ */ I();
		return Jc({
			anchor: t,
			onAnchorChange: (e) => t.value = e
		}), (e, t) => W(e.$slots, "default");
	}
}), Xc = /* @__PURE__ */ U({
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
		let t = e, { forwardRef: n, currentElement: r } = tc(), i = qc();
		return Yn(() => {
			i.onAnchorChange(t.reference ?? r.value);
		}), (t, r) => (q(), Y(L(Sc), {
			ref: L(n),
			as: e.as,
			"as-child": e.asChild
		}, {
			default: V(() => [W(t.$slots, "default")]),
			_: 3
		}, 8, ["as", "as-child"]));
	}
});
// node_modules/reka-ui/dist/Popper/utils.js
function Zc(e) {
	return e !== null;
}
function Qc(e) {
	return {
		name: "transformOrigin",
		options: e,
		fn(t) {
			let { placement: n, rects: r, middlewareData: i } = t, a = i.arrow?.centerOffset !== 0, o = a ? 0 : e.arrowWidth, s = a ? 0 : e.arrowHeight, [c, l] = $c(n), u = {
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
function $c(e) {
	let [t, n = "center"] = e.split("-");
	return [t, n];
}
// node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs
var el = [
	"top",
	"right",
	"bottom",
	"left"
], tl = Math.min, nl = Math.max, rl = Math.round, il = Math.floor, al = (e) => ({
	x: e,
	y: e
}), ol = {
	left: "right",
	right: "left",
	bottom: "top",
	top: "bottom"
};
function sl(e, t, n) {
	return nl(e, tl(t, n));
}
function cl(e, t) {
	return typeof e == "function" ? e(t) : e;
}
function ll(e) {
	return e.split("-")[0];
}
function ul(e) {
	return e.split("-")[1];
}
function dl(e) {
	return e === "x" ? "y" : "x";
}
function fl(e) {
	return e === "y" ? "height" : "width";
}
function pl(e) {
	let t = e[0];
	return t === "t" || t === "b" ? "y" : "x";
}
function ml(e) {
	return dl(pl(e));
}
function hl(e, t, n) {
	n === void 0 && (n = !1);
	let r = ul(e), i = ml(e), a = fl(i), o = i === "x" ? r === (n ? "end" : "start") ? "right" : "left" : r === "start" ? "bottom" : "top";
	return t.reference[a] > t.floating[a] && (o = wl(o)), [o, wl(o)];
}
function gl(e) {
	let t = wl(e);
	return [
		_l(e),
		t,
		_l(t)
	];
}
function _l(e) {
	return e.includes("start") ? e.replace("start", "end") : e.replace("end", "start");
}
var vl = ["left", "right"], yl = ["right", "left"], bl = ["top", "bottom"], xl = ["bottom", "top"];
function Sl(e, t, n) {
	switch (e) {
		case "top":
		case "bottom": return n ? t ? yl : vl : t ? vl : yl;
		case "left":
		case "right": return t ? bl : xl;
		default: return [];
	}
}
function Cl(e, t, n, r) {
	let i = ul(e), a = Sl(ll(e), n === "start", r);
	return i && (a = a.map((e) => e + "-" + i), t && (a = a.concat(a.map(_l)))), a;
}
function wl(e) {
	let t = ll(e);
	return ol[t] + e.slice(t.length);
}
function Tl(e) {
	return {
		top: e.top ?? 0,
		right: e.right ?? 0,
		bottom: e.bottom ?? 0,
		left: e.left ?? 0
	};
}
function El(e) {
	return typeof e == "number" ? {
		top: e,
		right: e,
		bottom: e,
		left: e
	} : Tl(e);
}
function Dl(e) {
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
function Ol(e, t, n) {
	let { reference: r, floating: i } = e, a = pl(t), o = ml(t), s = fl(o), c = ll(t), l = a === "y", u = r.x + r.width / 2 - i.width / 2, d = r.y + r.height / 2 - i.height / 2, f = r[s] / 2 - i[s] / 2, p;
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
	let m = ul(t);
	return m && (p[o] += f * (m === "end" ? 1 : -1) * (n && l ? -1 : 1)), p;
}
async function kl(e, t) {
	t === void 0 && (t = {});
	let { x: n, y: r, platform: i, rects: a, elements: o, strategy: s } = e, { boundary: c = "clippingAncestors", rootBoundary: l = "viewport", elementContext: u = "floating", altBoundary: d = !1, padding: f = 0 } = cl(t, e), p = El(f), m = o[d ? u === "floating" ? "reference" : "floating" : u], h = Dl(await i.getClippingRect({
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
	}, y = Dl(i.convertOffsetParentRelativeRectToViewportRelativeRect ? await i.convertOffsetParentRelativeRectToViewportRelativeRect({
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
var Al = 50, jl = async (e, t, n) => {
	let { placement: r = "bottom", strategy: i = "absolute", middleware: a = [], platform: o } = n, s = o.detectOverflow ? o : {
		...o,
		detectOverflow: kl
	}, c = await (o.isRTL == null ? void 0 : o.isRTL(t)), l = await o.getElementRects({
		reference: e,
		floating: t,
		strategy: i
	}), { x: u, y: d } = Ol(l, r, c), f = r, p = 0, m = {};
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
		}, x && p < Al && (p++, typeof x == "object" && (x.placement && (f = x.placement), x.rects && (l = x.rects === !0 ? await o.getElementRects({
			reference: e,
			floating: t,
			strategy: i
		}) : x.rects), {x: u, y: d} = Ol(l, f, c)), n = -1);
	}
	return {
		x: u,
		y: d,
		placement: f,
		strategy: i,
		middlewareData: m
	};
}, Ml = (e) => ({
	name: "arrow",
	options: e,
	async fn(t) {
		let { x: n, y: r, placement: i, rects: a, platform: o, elements: s, middlewareData: c } = t, { element: l, padding: u = 0 } = cl(e, t) || {};
		if (l == null) return {};
		let d = El(u), f = {
			x: n,
			y: r
		}, p = ml(i), m = fl(p), h = await o.getDimensions(l), g = p === "y", _ = g ? "top" : "left", v = g ? "bottom" : "right", y = g ? "clientHeight" : "clientWidth", b = a.reference[m] + a.reference[p] - f[p] - a.floating[m], x = f[p] - a.reference[p], S = await (o.getOffsetParent == null ? void 0 : o.getOffsetParent(l)), C = S ? S[y] : 0;
		C && await (o.isElement == null ? void 0 : o.isElement(S)) || (C = s.floating[y] || a.floating[m]);
		let w = b / 2 - x / 2, T = C / 2 - h[m] / 2 - 1, ee = tl(d[_], T), te = tl(d[v], T), E = C - h[m] - te, ne = C / 2 - h[m] / 2 + w, D = sl(ee, ne, E), re = !c.arrow && ul(i) != null && ne !== D && a.reference[m] / 2 - (ne < ee ? ee : te) - h[m] / 2 < 0, ie = re ? ne < ee ? ne - ee : ne - E : 0;
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
}), Nl = function(e) {
	return e === void 0 && (e = {}), {
		name: "flip",
		options: e,
		async fn(t) {
			var n;
			let { placement: r, middlewareData: i, rects: a, initialPlacement: o, platform: s, elements: c } = t, { mainAxis: l = !0, crossAxis: u = !0, fallbackPlacements: d, fallbackStrategy: f = "bestFit", fallbackAxisSideDirection: p = "none", flipAlignment: m = !0, ...h } = cl(e, t);
			if ((n = i.arrow) != null && n.alignmentOffset) return {};
			let g = ll(r), _ = pl(o), v = ll(o) === o, y = await (s.isRTL == null ? void 0 : s.isRTL(c.floating)), b = d || (v || !m ? [wl(o)] : gl(o)), x = p !== "none";
			!d && x && b.push(...Cl(o, m, p, y));
			let S = [o, ...b], C = await s.detectOverflow(t, h), w = [], T = i.flip?.overflows || [];
			if (l && w.push(C[g]), u) {
				let e = hl(r, a, y);
				w.push(C[e[0]], C[e[1]]);
			}
			if (T = [...T, {
				placement: r,
				overflows: w
			}], !w.every((e) => e <= 0)) {
				let e = (i.flip?.index || 0) + 1, t = S[e];
				if (t && (u !== "alignment" || _ === pl(t) || T.every((e) => pl(e.placement) !== _ || e.overflows[0] > 0))) return {
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
								let t = pl(e.placement);
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
function Pl(e, t) {
	return {
		top: e.top - t.height,
		right: e.right - t.width,
		bottom: e.bottom - t.height,
		left: e.left - t.width
	};
}
function Fl(e) {
	return el.some((t) => e[t] >= 0);
}
var Il = function(e) {
	return e === void 0 && (e = {}), {
		name: "hide",
		options: e,
		async fn(t) {
			let { rects: n, platform: r } = t, { strategy: i = "referenceHidden", ...a } = cl(e, t);
			switch (i) {
				case "referenceHidden": {
					let e = Pl(await r.detectOverflow(t, {
						...a,
						elementContext: "reference"
					}), n.reference);
					return { data: {
						referenceHiddenOffsets: e,
						referenceHidden: Fl(e)
					} };
				}
				case "escaped": {
					let e = Pl(await r.detectOverflow(t, {
						...a,
						altBoundary: !0
					}), n.floating);
					return { data: {
						escapedOffsets: e,
						escaped: Fl(e)
					} };
				}
				default: return {};
			}
		}
	};
}, Ll = /*#__PURE__*/ new Set(["left", "top"]);
async function Rl(e, t) {
	let { placement: n, platform: r, elements: i } = e, a = await (r.isRTL == null ? void 0 : r.isRTL(i.floating)), o = ll(n), s = ul(n), c = pl(n) === "y", l = Ll.has(o) ? -1 : 1, u = a && c ? -1 : 1, d = cl(t, e), { mainAxis: f, crossAxis: p, alignmentAxis: m } = typeof d == "number" ? {
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
var zl = function(e) {
	return e === void 0 && (e = 0), {
		name: "offset",
		options: e,
		async fn(t) {
			var n;
			let { x: r, y: i, placement: a, middlewareData: o } = t, s = await Rl(t, e);
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
}, Bl = function(e) {
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
			} }, ...l } = cl(e, t), u = {
				x: n,
				y: r
			}, d = await a.detectOverflow(t, l), f = pl(i), p = dl(f), m = u[p], h = u[f], g = (e, t) => sl(t + d[e === "y" ? "top" : "left"], t, t - d[e === "y" ? "bottom" : "right"]);
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
}, Vl = function(e) {
	return e === void 0 && (e = {}), {
		options: e,
		fn(t) {
			let { x: n, y: r, placement: i, rects: a, middlewareData: o } = t, { offset: s = 0, mainAxis: c = !0, crossAxis: l = !0 } = cl(e, t), u = {
				x: n,
				y: r
			}, d = pl(i), f = dl(d), p = u[f], m = u[d], h = cl(s, t), g = typeof h == "number" ? {
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
				let e = f === "y" ? "width" : "height", t = Ll.has(ll(i)), n = a.reference[d] - a.floating[e] + (t && o.offset?.[d] || 0) + (t ? 0 : g.crossAxis), r = a.reference[d] + a.reference[e] + (t ? 0 : o.offset?.[d] || 0) - (t ? g.crossAxis : 0);
				m < n ? m = n : m > r && (m = r);
			}
			return {
				[f]: p,
				[d]: m
			};
		}
	};
}, Hl = function(e) {
	return e === void 0 && (e = {}), {
		name: "size",
		options: e,
		async fn(t) {
			let { placement: n, rects: r, platform: i, elements: a } = t, { apply: o = () => {}, ...s } = cl(e, t), c = await i.detectOverflow(t, s), l = ll(n), u = ul(n), d = pl(n) === "y", { width: f, height: p } = r.floating, m, h;
			l === "top" || l === "bottom" ? (m = l, h = u === (await (i.isRTL == null ? void 0 : i.isRTL(a.floating)) ? "start" : "end") ? "left" : "right") : (h = l, m = u === "end" ? "top" : "bottom");
			let g = p - c.top - c.bottom, _ = f - c.left - c.right, v = tl(p - c[m], g), y = tl(f - c[h], _), b = t.middlewareData.shift, x = !b, S = v, C = y;
			b != null && b.enabled.x && (C = _), b != null && b.enabled.y && (S = g), x && !u && (d ? C = f - 2 * nl(c.left, c.right) : S = p - 2 * nl(c.top, c.bottom)), await o({
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
function Ul() {
	return typeof window < "u";
}
function Wl(e) {
	return ql(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function Gl(e) {
	var t;
	return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function Kl(e) {
	return ((ql(e) ? e.ownerDocument : e.document) || window.document)?.documentElement;
}
function ql(e) {
	return Ul() ? e instanceof Node || e instanceof Gl(e).Node : !1;
}
function Jl(e) {
	return Ul() ? e instanceof Element || e instanceof Gl(e).Element : !1;
}
function Yl(e) {
	return Ul() ? e instanceof HTMLElement || e instanceof Gl(e).HTMLElement : !1;
}
function Xl(e) {
	return !Ul() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof Gl(e).ShadowRoot;
}
function Zl(e) {
	let { overflow: t, overflowX: n, overflowY: r, display: i } = cu(e);
	return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && i !== "inline" && i !== "contents";
}
function Ql(e) {
	return /^(table|td|th)$/.test(Wl(e));
}
function $l(e) {
	try {
		if (e.matches(":popover-open")) return !0;
	} catch {}
	try {
		return e.matches(":modal");
	} catch {
		return !1;
	}
}
var eu = /transform|translate|scale|rotate|perspective|filter/, tu = /paint|layout|strict|content/, nu = (e) => !!e && e !== "none", ru;
function iu(e) {
	let t = Jl(e) ? cu(e) : e;
	return nu(t.transform) || nu(t.translate) || nu(t.scale) || nu(t.rotate) || nu(t.perspective) || !ou() && (nu(t.backdropFilter) || nu(t.filter)) || eu.test(t.willChange || "") || tu.test(t.contain || "");
}
function au(e) {
	let t = uu(e);
	for (; Yl(t) && !su(t);) {
		if (iu(t)) return t;
		if ($l(t)) return null;
		t = uu(t);
	}
	return null;
}
function ou() {
	return ru ??= typeof CSS < "u" && CSS.supports && CSS.supports("-webkit-backdrop-filter", "none"), ru;
}
function su(e) {
	return /^(html|body|#document)$/.test(Wl(e));
}
function cu(e) {
	return Gl(e).getComputedStyle(e);
}
function lu(e) {
	return Jl(e) ? {
		scrollLeft: e.scrollLeft,
		scrollTop: e.scrollTop
	} : {
		scrollLeft: e.scrollX,
		scrollTop: e.scrollY
	};
}
function uu(e) {
	if (Wl(e) === "html") return e;
	let t = e.assignedSlot || e.parentNode || Xl(e) && e.host || Kl(e);
	return Xl(t) ? t.host : t;
}
function du(e) {
	let t = uu(e);
	return su(t) ? (e.ownerDocument || e).body : Yl(t) && Zl(t) ? t : du(t);
}
function fu(e, t, n) {
	t === void 0 && (t = []), n === void 0 && (n = !0);
	let r = du(e), i = r === e.ownerDocument?.body, a = Gl(r);
	if (i) {
		let e = pu(a);
		return t.concat(a, a.visualViewport || [], Zl(r) ? r : [], e && n ? fu(e) : []);
	}
	return t.concat(r, fu(r, [], n));
}
function pu(e) {
	return e.parent && Object.getPrototypeOf(e.parent) ? e.frameElement : null;
}
// node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs
function mu(e) {
	let t = cu(e), n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0, i = Yl(e), a = i ? e.offsetWidth : n, o = i ? e.offsetHeight : r, s = rl(n) !== a || rl(r) !== o;
	return s && (n = a, r = o), {
		width: n,
		height: r,
		$: s
	};
}
function hu(e) {
	return Jl(e) ? e : e.contextElement;
}
function gu(e) {
	let t = hu(e);
	if (!Yl(t)) return al(1);
	let n = t.getBoundingClientRect(), { width: r, height: i, $: a } = mu(t), o = (a ? rl(n.width) : n.width) / r, s = (a ? rl(n.height) : n.height) / i;
	return o && Number.isFinite(o) || (o = 1), s && Number.isFinite(s) || (s = 1), {
		x: o,
		y: s
	};
}
var _u = /*#__PURE__*/ al(0);
function vu(e) {
	let t = Gl(e);
	return !ou() || !t.visualViewport ? _u : {
		x: t.visualViewport.offsetLeft,
		y: t.visualViewport.offsetTop
	};
}
function yu(e, t, n) {
	return t === void 0 && (t = !1), !!n && t && n === Gl(e);
}
function bu(e, t, n, r) {
	t === void 0 && (t = !1), n === void 0 && (n = !1);
	let i = e.getBoundingClientRect(), a = hu(e), o = al(1);
	t && (r ? Jl(r) && (o = gu(r)) : o = gu(e));
	let s = yu(a, n, r) ? vu(a) : al(0), c = (i.left + s.x) / o.x, l = (i.top + s.y) / o.y, u = i.width / o.x, d = i.height / o.y;
	if (a && r) {
		let e = Gl(a), t = Jl(r) ? Gl(r) : r, n = e, i = pu(n);
		for (; i && t !== n;) {
			let e = gu(i), t = i.getBoundingClientRect(), r = cu(i), a = t.left + (i.clientLeft + parseFloat(r.paddingLeft)) * e.x, o = t.top + (i.clientTop + parseFloat(r.paddingTop)) * e.y;
			c *= e.x, l *= e.y, u *= e.x, d *= e.y, c += a, l += o, n = Gl(i), i = pu(n);
		}
	}
	return Dl({
		width: u,
		height: d,
		x: c,
		y: l
	});
}
function xu(e, t) {
	let n = lu(e).scrollLeft;
	return t ? t.left + n : bu(Kl(e)).left + n;
}
function Su(e, t) {
	let n = e.getBoundingClientRect();
	return {
		x: n.left + t.scrollLeft - xu(e, n),
		y: n.top + t.scrollTop
	};
}
function Cu(e) {
	let { elements: t, rect: n, offsetParent: r, strategy: i } = e, a = i === "fixed", o = Kl(r), s = t ? $l(t.floating) : !1;
	if (r === o || s && a) return n;
	let c = {
		scrollLeft: 0,
		scrollTop: 0
	}, l = al(1), u = al(0), d = Yl(r);
	if ((d || !a) && ((Wl(r) !== "body" || Zl(o)) && (c = lu(r)), d)) {
		let e = bu(r);
		l = gu(r), u.x = e.x + r.clientLeft, u.y = e.y + r.clientTop;
	}
	let f = o && !d && !a ? Su(o, c) : al(0);
	return {
		width: n.width * l.x,
		height: n.height * l.y,
		x: n.x * l.x - c.scrollLeft * l.x + u.x + f.x,
		y: n.y * l.y - c.scrollTop * l.y + u.y + f.y
	};
}
function wu(e) {
	return e.getClientRects ? Array.from(e.getClientRects()) : [];
}
function Tu(e) {
	let t = lu(e), n = e.ownerDocument.body, r = nl(e.scrollWidth, e.clientWidth, n.scrollWidth, n.clientWidth), i = nl(e.scrollHeight, e.clientHeight, n.scrollHeight, n.clientHeight), a = -t.scrollLeft + xu(e), o = -t.scrollTop;
	return cu(n).direction === "rtl" && (a += nl(e.clientWidth, n.clientWidth) - r), {
		width: r,
		height: i,
		x: a,
		y: o
	};
}
var Eu = 25;
function Du(e, t, n) {
	n === void 0 && (n = "viewport");
	let r = n === "layoutViewport", i = Gl(e), a = Kl(e), o = i.visualViewport, s = a.clientWidth, c = a.clientHeight, l = 0, u = 0;
	if (o) {
		let e = !ou() || t === "fixed";
		r ? e || (l = -o.offsetLeft, u = -o.offsetTop) : (s = o.width, c = o.height, e && (l = o.offsetLeft, u = o.offsetTop));
	}
	if (xu(a) <= 0) {
		let e = a.ownerDocument, t = e.body, n = getComputedStyle(t), r = e.compatMode === "CSS1Compat" && parseFloat(n.marginLeft) + parseFloat(n.marginRight) || 0, i = Math.abs(a.clientWidth - t.clientWidth - r), o = getComputedStyle(a).scrollbarGutter === "stable both-edges" ? i / 2 : i;
		o <= Eu && (s -= o);
	}
	return {
		width: s,
		height: c,
		x: l,
		y: u
	};
}
function Ou(e, t) {
	let n = bu(e, !0, t === "fixed"), r = n.top + e.clientTop, i = n.left + e.clientLeft, a = gu(e);
	return {
		width: e.clientWidth * a.x,
		height: e.clientHeight * a.y,
		x: i * a.x,
		y: r * a.y
	};
}
function ku(e, t, n) {
	let r;
	if (t === "viewport" || t === "layoutViewport") r = Du(e, n, t);
	else if (t === "document") r = Tu(Kl(e));
	else if (Jl(t)) r = Ou(t, n);
	else {
		let n = vu(e);
		r = {
			x: t.x - n.x,
			y: t.y - n.y,
			width: t.width,
			height: t.height
		};
	}
	return Dl(r);
}
function Au(e, t) {
	let n = t.get(e);
	if (n) return n;
	let r = fu(e, [], !1).filter((e) => Jl(e) && Wl(e) !== "body"), i = null, a = cu(e).position === "fixed", o = a ? uu(e) : e;
	for (; Jl(o) && !su(o);) {
		let e = cu(o), t = iu(o), n = i ? i.position : a ? "fixed" : "";
		!t && (n === "fixed" || n === "absolute" && e.position === "static") ? r = r.filter((e) => e !== o) : i = e, o = uu(o);
	}
	return t.set(e, r), r;
}
function ju(e) {
	let { element: t, boundary: n, rootBoundary: r, strategy: i } = e, a = [...n === "clippingAncestors" ? $l(t) ? [] : Au(t, this._c) : [].concat(n), r], o = ku(t, a[0], i), s = o.top, c = o.right, l = o.bottom, u = o.left;
	for (let e = 1; e < a.length; e++) {
		let n = ku(t, a[e], i);
		s = nl(n.top, s), c = tl(n.right, c), l = tl(n.bottom, l), u = nl(n.left, u);
	}
	return {
		width: c - u,
		height: l - s,
		x: u,
		y: s
	};
}
function Mu(e) {
	let { width: t, height: n } = mu(e);
	return {
		width: t,
		height: n
	};
}
function Nu(e, t, n) {
	let r = Yl(t), i = Kl(t), a = n === "fixed", o = bu(e, !0, a, t), s = {
		scrollLeft: 0,
		scrollTop: 0
	}, c = al(0);
	if ((r || !a) && ((Wl(t) !== "body" || Zl(i)) && (s = lu(t)), r)) {
		let e = bu(t, !0, a, t);
		c.x = e.x + t.clientLeft, c.y = e.y + t.clientTop;
	}
	!r && i && (c.x = xu(i));
	let l = i && !r && !a ? Su(i, s) : al(0);
	return {
		x: o.left + s.scrollLeft - c.x - l.x,
		y: o.top + s.scrollTop - c.y - l.y,
		width: o.width,
		height: o.height
	};
}
function Pu(e) {
	return cu(e).position === "static";
}
function Fu(e, t) {
	if (!Yl(e) || cu(e).position === "fixed") return null;
	if (t) return t(e);
	let n = e.offsetParent;
	return Kl(e) === n && (n = n.ownerDocument.body), n;
}
function Iu(e, t) {
	let n = Gl(e);
	if ($l(e)) return n;
	if (!Yl(e)) {
		let t = uu(e);
		for (; t && !su(t);) {
			if (Jl(t) && !Pu(t)) return t;
			t = uu(t);
		}
		return n;
	}
	let r = Fu(e, t);
	for (; r && Ql(r) && Pu(r);) r = Fu(r, t);
	return r && su(r) && Pu(r) && !iu(r) ? n : r || au(e) || n;
}
var Lu = async function(e) {
	let t = this.getOffsetParent || Iu, n = this.getDimensions, r = await n(e.floating);
	return {
		reference: Nu(e.reference, await t(e.floating), e.strategy),
		floating: {
			x: 0,
			y: 0,
			width: r.width,
			height: r.height
		}
	};
};
function Ru(e) {
	return cu(e).direction === "rtl";
}
var zu = {
	convertOffsetParentRelativeRectToViewportRelativeRect: Cu,
	getDocumentElement: Kl,
	getClippingRect: ju,
	getOffsetParent: Iu,
	getElementRects: Lu,
	getClientRects: wu,
	getDimensions: Mu,
	getScale: gu,
	isElement: Jl,
	isRTL: Ru
};
function Bu(e, t) {
	return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function Vu(e, t, n) {
	let r = null, i, a = Kl(e);
	function o() {
		var e;
		clearTimeout(i), (e = r) == null || e.disconnect(), r = null;
	}
	function s(n, c) {
		n === void 0 && (n = !1), c === void 0 && (c = 1), o();
		let l = e.getBoundingClientRect(), { left: u, top: d, width: f, height: p } = l;
		if (n || t(), !f || !p) return;
		let m = il(d), h = il(a.clientWidth - (u + f)), g = il(a.clientHeight - (d + p)), _ = il(u), v = {
			rootMargin: -m + "px " + -h + "px " + -g + "px " + -_ + "px",
			threshold: nl(0, tl(1, c)) || 1
		}, y = !0;
		function b(t) {
			let n = t[0].intersectionRatio;
			if (!Bu(l, e.getBoundingClientRect())) return s();
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
	let c = Gl(e), l = () => s(n);
	return c.addEventListener("resize", l), s(!0), () => {
		c.removeEventListener("resize", l), o();
	};
}
function Hu(e, t, n, r) {
	r === void 0 && (r = {});
	let { ancestorScroll: i = !0, ancestorResize: a = !0, elementResize: o = typeof ResizeObserver == "function", layoutShift: s = typeof IntersectionObserver == "function", animationFrame: c = !1 } = r, l = hu(e), u = i || a ? [...l ? fu(l) : [], ...t ? fu(t) : []] : [];
	u.forEach((e) => {
		i && e.addEventListener("scroll", n), a && e.addEventListener("resize", n);
	});
	let d = l && s ? Vu(l, n, a) : null, f = -1, p = null;
	o && (p = new ResizeObserver((e) => {
		let [r] = e;
		r && r.target === l && p && t && (p.unobserve(t), cancelAnimationFrame(f), f = requestAnimationFrame(() => {
			var e;
			(e = p) == null || e.observe(t);
		})), n();
	}), l && !c && p.observe(l), t && p.observe(t));
	let m, h = c ? bu(e) : null;
	c && g();
	function g() {
		let t = bu(e);
		h && !Bu(h, t) && n(), h = t, m = requestAnimationFrame(g);
	}
	return n(), () => {
		var e;
		u.forEach((e) => {
			i && e.removeEventListener("scroll", n), a && e.removeEventListener("resize", n);
		}), d?.(), (e = p) == null || e.disconnect(), p = null, c && cancelAnimationFrame(m);
	};
}
var Uu = zl, Wu = Bl, Gu = Nl, Ku = Hl, qu = Il, Ju = Ml, Yu = Vl, Xu = (e, t, n) => {
	let r = /* @__PURE__ */ new Map(), i = n ?? {}, a = {
		...zu,
		...i.platform,
		_c: r
	};
	return jl(e, t, {
		...i,
		platform: a
	});
};
// node_modules/@floating-ui/vue/dist/floating-ui.vue.mjs
function Zu(e) {
	return typeof e == "object" && !!e && "$el" in e;
}
function Qu(e) {
	if (Zu(e)) {
		let t = e.$el;
		return ql(t) && Wl(t) === "#comment" ? null : t;
	}
	return e;
}
function $u(e) {
	return {
		name: "arrow",
		options: e,
		fn(t) {
			let n = Qu(R(e.element));
			return n == null ? {} : Ju({
				element: n,
				padding: e.padding
			}).fn(t);
		}
	};
}
function ed(e) {
	return typeof window > "u" ? 1 : (e.ownerDocument.defaultView || window).devicePixelRatio || 1;
}
function td(e, t) {
	let n = ed(e);
	return Math.round(t * n) / n;
}
function nd(e, t, n) {
	n === void 0 && (n = {});
	let r = n.whileElementsMounted, i = $(() => R(n.open) ?? !0), a = $(() => R(n.middleware)), o = $(() => R(n.placement) ?? "bottom"), s = $(() => R(n.strategy) ?? "absolute"), c = $(() => R(n.transform) ?? !0), l = $(() => Qu(e.value)), u = $(() => Qu(t.value)), d = /* @__PURE__ */ I(0), f = /* @__PURE__ */ I(0), p = /* @__PURE__ */ I(s.value), m = /* @__PURE__ */ I(o.value), h = /* @__PURE__ */ $t({}), g = /* @__PURE__ */ I(!1), _ = $(() => {
		let e = {
			position: p.value,
			left: "0",
			top: "0"
		};
		if (!u.value) return e;
		let t = td(u.value, d.value), n = td(u.value, f.value);
		return c.value ? {
			...e,
			transform: "translate(" + t + "px, " + n + "px)",
			...ed(u.value) >= 1.5 && { willChange: "transform" }
		} : {
			position: p.value,
			left: t + "px",
			top: n + "px"
		};
	}), v;
	function y() {
		if (l.value == null || u.value == null) return;
		let e = i.value;
		Xu(l.value, u.value, {
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
	return H([
		a,
		o,
		s,
		i
	], y, { flush: "sync" }), H([l, u], x, { flush: "sync" }), H(i, S, { flush: "sync" }), Oe() && ke(b), {
		x: /* @__PURE__ */ Wt(d),
		y: /* @__PURE__ */ Wt(f),
		strategy: /* @__PURE__ */ Wt(p),
		placement: /* @__PURE__ */ Wt(m),
		middlewareData: /* @__PURE__ */ Wt(h),
		isPositioned: /* @__PURE__ */ Wt(g),
		floatingStyles: _,
		update: y
	};
}
// node_modules/reka-ui/dist/Popper/PopperContent.js
var rd = ["dir"], id = {
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
}, [ad, od] = /*#__PURE__*/ cs("PopperContent"), sd = /* @__PURE__ */ U({
	inheritAttrs: !1,
	__name: "PopperContent",
	props: /* @__PURE__ */ ei({
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
	}, { ...id }),
	emits: ["placed"],
	setup(e, { emit: t }) {
		let n = e, r = t, i = qc(), { forwardRef: a, currentElement: o } = tc(), s = Xs($(() => n.dir)), c = /* @__PURE__ */ I(), l = /* @__PURE__ */ I(), { width: u, height: d } = hc(l), f = $(() => n.side + (n.align === "center" ? "" : `-${n.align}`)), p = $(() => typeof n.collisionPadding == "number" ? n.collisionPadding : {
			top: 0,
			right: 0,
			bottom: 0,
			left: 0,
			...n.collisionPadding
		}), m = $(() => Array.isArray(n.collisionBoundary) ? n.collisionBoundary : [n.collisionBoundary]), h = $(() => ({
			padding: p.value,
			boundary: m.value.filter(Zc),
			altBoundary: m.value.length > 0
		})), g = $(() => ({
			mainAxis: n.sideFlip,
			crossAxis: n.alignFlip
		})), _ = $(() => [
			Uu({
				mainAxis: n.sideOffset + d.value,
				alignmentAxis: n.alignOffset
			}),
			n.prioritizePosition && n.avoidCollisions && Gu({
				...h.value,
				...g.value
			}),
			n.avoidCollisions && Wu({
				mainAxis: !0,
				crossAxis: !!n.prioritizePosition,
				limiter: n.sticky === "partial" ? Yu() : void 0,
				...h.value
			}),
			!n.prioritizePosition && n.avoidCollisions && Gu({
				...h.value,
				...g.value
			}),
			Ku({
				...h.value,
				apply: ({ elements: e, rects: t, availableWidth: n, availableHeight: r }) => {
					let { width: i, height: a } = t.reference, o = e.floating.style;
					o.setProperty("--reka-popper-available-width", `${n}px`), o.setProperty("--reka-popper-available-height", `${r}px`), o.setProperty("--reka-popper-anchor-width", `${i}px`), o.setProperty("--reka-popper-anchor-height", `${a}px`);
				}
			}),
			l.value && $u({
				element: l.value,
				padding: n.arrowPadding
			}),
			Qc({
				arrowWidth: u.value,
				arrowHeight: d.value,
				dir: s.value
			}),
			n.hideWhenDetached && qu({
				strategy: "referenceHidden",
				...h.value
			})
		]), { floatingStyles: v, placement: y, isPositioned: b, middlewareData: x, update: S } = nd($(() => n.reference ?? i.anchor.value), c, {
			strategy: n.positionStrategy,
			placement: f,
			whileElementsMounted: (...e) => Hu(...e, {
				layoutShift: !n.disableUpdateOnLayoutShift,
				animationFrame: n.updatePositionStrategy === "always"
			}),
			middleware: _
		}), C = $(() => $c(y.value)[0]), w = $(() => $c(y.value)[1]);
		Yn(() => {
			b.value && r("placed");
		});
		let T = $(() => {
			let e = x.value.arrow?.centerOffset !== 0;
			return n.hideShiftedArrow && e;
		}), ee = /* @__PURE__ */ I("");
		return Jn(() => {
			o.value && (ee.value = window.getComputedStyle(o.value).zIndex);
		}), od({
			placedSide: C,
			onArrowChange: (e) => l.value = e,
			arrowX: $(() => x.value.arrow?.x ?? 0),
			arrowY: $(() => x.value.arrow?.y ?? 0),
			shouldHideArrow: T
		}), (e, t) => (q(), J("div", {
			ref_key: "floatingRef",
			ref: c,
			"data-reka-popper-content-wrapper": "",
			dir: L(s),
			style: ue({
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
		}, [n.memoDependencies ? to([
			n.asChild,
			n.as,
			C.value,
			w.value,
			L(b),
			...Object.values(e.$attrs),
			...n.memoDependencies
		], () => (q(), Y(L(Sc), ja({
			key: 0,
			ref: L(a)
		}, e.$attrs, {
			"as-child": n.asChild,
			as: n.as,
			"data-side": C.value,
			"data-align": w.value,
			style: { animation: L(b) ? void 0 : "none" }
		}), {
			default: V(() => [W(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"style"
		])), t, 0) : (q(), Y(L(Sc), ja({
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
			default: V(() => [W(e.$slots, "default")]),
			_: 3
		}, 16, [
			"as-child",
			"as",
			"data-side",
			"data-align",
			"dir",
			"style"
		]))], 12, rd));
	}
}), [cd, ld] = /*#__PURE__*/ cs("PopoverRoot"), ud = /* @__PURE__ */ U({
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
		let n = e, r = t, { modal: i } = /* @__PURE__ */ on(n), a = Ps(n, "open", r, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		});
		return ld({
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
		}), (e, t) => (q(), Y(L(Yc), null, {
			default: V(() => [W(e.$slots, "default", {
				open: L(a),
				close: () => a.value = !1
			})]),
			_: 3
		}));
	}
}), dd = /* @__PURE__ */ U({
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
		tc();
		let n = cd();
		return (r, i) => (q(), Y(L(Sc), {
			type: e.as === "button" ? "button" : void 0,
			as: e.as,
			"as-child": t.asChild,
			onClick: i[0] ||= (e) => L(n).onOpenChange(!1)
		}, {
			default: V(() => [W(r.$slots, "default")]),
			_: 3
		}, 8, [
			"type",
			"as",
			"as-child"
		]));
	}
}), fd = /* @__PURE__ */ U({
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
		let n = e, r = t, i = nc(ws(n, "trapFocus", "disableOutsidePointerEvents")), { forwardRef: a } = tc(), o = cd();
		return $s(), (t, n) => (q(), Y(L(Gc), {
			"as-child": "",
			loop: "",
			trapped: e.trapFocus,
			onMountAutoFocus: n[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: n[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: V(() => [Z(L(Ac), {
				"as-child": "",
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				onPointerDownOutside: n[0] ||= (e) => r("pointerDownOutside", e),
				onInteractOutside: n[1] ||= (e) => r("interactOutside", e),
				onEscapeKeyDown: n[2] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: n[3] ||= (e) => r("focusOutside", e),
				onDismiss: n[4] ||= (e) => L(o).onOpenChange(!1)
			}, {
				default: V(() => [Z(L(sd), ja(L(i), {
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
					default: V(() => [W(t.$slots, "default")]),
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
}), pd = /* @__PURE__ */ U({
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
		let n = e, r = t, i = cd(), a = /* @__PURE__ */ I(!1);
		qs(!0);
		let o = rc(n, r), { forwardRef: s, currentElement: c } = tc();
		return pc(c), (e, t) => (q(), Y(fd, ja(L(o), {
			ref: L(s),
			"trap-focus": L(i).open.value,
			"disable-outside-pointer-events": "",
			onCloseAutoFocus: t[0] ||= $o((e) => {
				r("closeAutoFocus", e), a.value || L(i).triggerElement.value?.focus();
			}, ["prevent"]),
			onPointerDownOutside: t[1] ||= (e) => {
				r("pointerDownOutside", e);
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0, i = t.button === 2 || n;
				a.value = i;
			},
			onFocusOutside: t[2] ||= $o(() => {}, ["prevent"])
		}), {
			default: V(() => [W(e.$slots, "default")]),
			_: 3
		}, 16, ["trap-focus"]));
	}
}), md = /* @__PURE__ */ U({
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
		let n = e, r = t, i = cd(), a = /* @__PURE__ */ I(!1), o = /* @__PURE__ */ I(!1), s = rc(n, r);
		return (e, t) => (q(), Y(fd, ja(L(s), {
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
			default: V(() => [W(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), hd = /* @__PURE__ */ U({
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
		let n = e, r = t, i = cd(), a = rc(n, r), { forwardRef: o } = tc();
		return i.contentId ||= mc(void 0, "reka-popover-content"), (t, n) => (q(), Y(L(yc), { present: e.forceMount || L(i).open.value }, {
			default: V(() => [L(i).modal.value ? (q(), Y(pd, ja({ key: 0 }, L(a), { ref: L(o) }), {
				default: V(() => [W(t.$slots, "default")]),
				_: 3
			}, 16)) : (q(), Y(md, ja({ key: 1 }, L(a), { ref: L(o) }), {
				default: V(() => [W(t.$slots, "default")]),
				_: 3
			}, 16))]),
			_: 3
		}, 8, ["present"]));
	}
}), gd = /* @__PURE__ */ U({
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
		return (e, n) => (q(), Y(L(Kc), he(wa(t)), {
			default: V(() => [W(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), _d = /* @__PURE__ */ U({
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
		let t = e, n = cd(), { forwardRef: r, currentElement: i } = tc();
		return n.triggerId ||= mc(void 0, "reka-popover-trigger"), n.contentId ||= mc(void 0, "reka-popover-content"), Nr(() => {
			n.triggerElement.value = i.value;
		}), (i, a) => (q(), Y(Wr(L(n).hasCustomAnchor.value ? L(Sc) : L(Xc)), { "as-child": "" }, {
			default: V(() => [Z(L(Sc), {
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
				default: V(() => [W(i.$slots, "default")]),
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
}), vd = [
	"data-active",
	"aria-label",
	"title"
], yd = { class: "tc-column-filter-label" }, bd = { class: "tc-filter-popover-heading list-filter-popover__heading" }, xd = /*@__PURE__*/ U({
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
		return (t, r) => (q(), Y(L(ud), {
			open: e.open,
			modal: !1,
			"onUpdate:open": r[0] ||= (e) => n("update:open", e)
		}, {
			default: V(() => [Z(L(_d), { "as-child": "" }, {
				default: V(() => [X("button", {
					type: "button",
					class: k(["tc-column-filter-trigger", { "is-active": e.active }]),
					"data-active": e.active ? "" : void 0,
					"aria-label": `筛选${e.label}`,
					title: e.active ? `${e.label}：${e.summary || "已筛选"}` : `筛选${e.label}`
				}, [X("span", yd, A(e.triggerLabel || e.label), 1), r[1] ||= X("svg", {
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
				})], -1)], 10, vd)]),
				_: 1
			}), Z(L(gd), null, {
				default: V(() => [Z(L(hd), {
					class: "tc-filter-popover list-filter-popover",
					"aria-label": `筛选${e.label}`,
					side: "bottom",
					align: "start",
					"side-offset": 6,
					"collision-padding": 10,
					"hide-when-detached": ""
				}, {
					default: V(() => [
						X("div", bd, "筛选" + A(e.label), 1),
						W(t.$slots, "default", {}, void 0, !0),
						Z(L(dd), {
							class: "tc-filter-popover-close list-filter-popover__close",
							"aria-label": `关闭${e.label}筛选`,
							title: "关闭筛选"
						}, {
							default: V(() => [...r[2] ||= [X("svg", {
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
}), Sd = (e, t) => {
	let n = e.__vccOpts || e;
	for (let [e, r] of t) n[e] = r;
	return n;
}, Cd = /*#__PURE__*/ Sd(xd, [["__scopeId", "data-v-49f53dbd"]]), wd = ["title"], Td = {
	key: 0,
	class: "list-cell-secondary"
}, Ed = /*#__PURE__*/ Sd(/* @__PURE__ */ U({
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
		}, [X("div", { class: k(["list-cell-primary", { "list-cell-single": !!e.secondary }]) }, [W(t.$slots, "default", {}, () => [Ea(A(e.text), 1)], !0)], 2), e.secondary ? (q(), J("div", Td, A(e.secondary), 1)) : Da("", !0)], 10, wd));
	}
}), [["__scopeId", "data-v-5767b82c"]]), Dd = ["aria-label"], Od = [
	"aria-label",
	"title",
	"onClick"
], kd = /*#__PURE__*/ Sd(/* @__PURE__ */ U({
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
		}, [(q(!0), J(K, null, qr(e.items, (e) => (q(), J("button", {
			key: e.key,
			type: "button",
			class: "list-filter-chip",
			"aria-label": e.removeLabel,
			title: e.title || e.label,
			onClick: (t) => n("remove", e.key)
		}, [X("span", null, A(e.label), 1), r[0] ||= X("span", { "aria-hidden": "true" }, "×", -1)], 8, Od))), 128))], 8, Dd)) : Da("", !0);
	}
}), [["__scopeId", "data-v-9c3f6cac"]]), Ad = ["aria-label", "aria-busy"], jd = { class: "list-pagination__layout" }, Md = { class: "list-pagination__controls" }, Nd = { class: "list-pagination__pages" }, Pd = ["disabled"], Fd = [
	"aria-label",
	"aria-current",
	"disabled",
	"onClick"
], Id = {
	key: 1,
	class: "list-pagination__ellipsis",
	"aria-hidden": "true"
}, Ld = {
	class: "list-pagination__mobile-page",
	"aria-live": "polite"
}, Rd = ["disabled"], zd = [
	"aria-invalid",
	"title",
	"disabled"
], Bd = ["disabled"], Vd = { class: "list-pagination__meta" }, Hd = {
	class: "list-pagination__range",
	"aria-live": "polite"
}, Ud = { key: 0 }, Wd = { class: "list-pagination__size" }, Gd = ["value", "disabled"], Kd = ["value"], qd = {
	key: 0,
	class: "list-pagination__error",
	role: "alert"
}, Jd = /*#__PURE__*/ Sd(/* @__PURE__ */ U({
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
		let n = e, r = t, i = $(() => Math.max(0, Math.floor(n.total) || 0)), a = $(() => Math.max(1, Math.floor(n.size) || 1)), o = $(() => Math.max(1, Math.floor(n.pages || Math.ceil(i.value / a.value)) || 1)), s = $(() => Math.min(o.value, Math.max(1, Math.floor(n.page) || 1))), c = $(() => i.value ? Math.min(i.value, (s.value - 1) * a.value + 1) : 0), l = $(() => Math.min(i.value, s.value * a.value)), u = $(() => [.../* @__PURE__ */ new Set([...n.pageSizes, a.value])].filter((e) => Number.isInteger(e) && e > 0).sort((e, t) => e - t)), d = /* @__PURE__ */ I(String(s.value)), f = /* @__PURE__ */ I(!1);
		H([s, o], () => {
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
		}, [X("div", jd, [
			X("div", Md, [X("div", Nd, [
				X("button", {
					type: "button",
					class: "list-pagination__button list-pagination__previous",
					disabled: e.busy || !i.value || s.value <= 1,
					onClick: n[0] ||= (e) => m(s.value - 1)
				}, "上一页", 8, Pd),
				(q(!0), J(K, null, qr(p.value, (t) => (q(), J(K, { key: t }, [typeof t == "number" ? (q(), J("button", {
					key: 0,
					type: "button",
					class: k(["list-pagination__button list-pagination__number", { "is-current": t === s.value }]),
					"aria-label": `第 ${t} 页`,
					"aria-current": t === s.value ? "page" : void 0,
					disabled: e.busy || !i.value || t === s.value,
					onClick: (e) => m(t)
				}, A(t), 11, Fd)) : (q(), J("span", Id, "…"))], 64))), 128)),
				X("span", Ld, A(s.value) + " / " + A(o.value), 1),
				X("button", {
					type: "button",
					class: "list-pagination__button list-pagination__next",
					disabled: e.busy || !i.value || s.value >= o.value,
					onClick: n[1] ||= (e) => m(s.value + 1)
				}, "下一页", 8, Rd)
			]), X("form", {
				class: "list-pagination__jump",
				novalidate: "",
				onSubmit: $o(h, ["prevent"])
			}, [X("label", null, [
				n[4] ||= Ea("跳至 ", -1),
				Hn(X("input", {
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
				}, null, 40, zd), [[Xo, d.value]]),
				n[5] ||= Ea(" 页", -1)
			]), X("button", {
				class: "list-pagination__button",
				type: "submit",
				disabled: e.busy || !i.value || o.value <= 1
			}, "跳转", 8, Bd)], 32)]),
			X("div", Vd, [X("span", Hd, [i.value ? (q(), J("span", Ud, A(c.value.toLocaleString()) + "–" + A(l.value.toLocaleString()) + " / ", 1)) : Da("", !0), Ea("共 " + A(i.value.toLocaleString()) + " 条", 1)]), X("label", Wd, [n[6] ||= Ea("每页 ", -1), X("select", {
				"aria-label": "每页条数",
				value: a.value,
				disabled: e.busy,
				onChange: g
			}, [(q(!0), J(K, null, qr(u.value, (e) => (q(), J("option", {
				key: e,
				value: e
			}, A(e) + " 条", 9, Kd))), 128))], 40, Gd)])]),
			f.value ? (q(), J("span", qd, "请输入整数页码")) : Da("", !0)
		])], 8, Ad));
	}
}), [["__scopeId", "data-v-5637de47"]]), Yd = new Intl.DateTimeFormat("zh-CN", {
	year: "numeric",
	month: "2-digit",
	day: "2-digit",
	hour: "2-digit",
	minute: "2-digit",
	second: "2-digit",
	hour12: !1
});
function Xd(e) {
	if (!e) return "—";
	let t = new Date(String(e));
	return Number.isNaN(t.getTime()) ? `无效时间：${String(e)}` : Yd.format(t);
}
function Zd(e) {
	let t = Xd(e), n = /^(\d{4}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})$/.exec(t);
	return n ? {
		text: n[1],
		secondary: n[2]
	} : { text: t };
}
// src/shared/useColumnWidths.ts
function Qd(e) {
	let t = /* @__PURE__ */ I([...e.defaults]), n = $(() => t.value.reduce((e, t) => e + t, 0));
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
// src/api/client.ts
var $d = class extends Error {
	status;
	code;
	constructor(e, t, n = "") {
		super(e), this.status = t, this.code = n, this.name = "ApiError";
	}
};
async function ef(e, t = {}, n) {
	let r = await fetch(e, {
		credentials: "same-origin",
		...t
	});
	if (!(r.headers.get("content-type") || "").includes("application/json")) throw new $d(r.redirected || r.status === 401 ? "登录已失效，请重新登录后刷新。" : `服务返回了非 JSON 响应（HTTP ${r.status}）`, r.status);
	let i = n ? n(await r.text()) : await r.json();
	if (!r.ok || i?.ok === !1) {
		let e = i?.error;
		throw new $d(typeof e == "string" ? e : e?.message || i?.message || `请求失败（HTTP ${r.status}）`, r.status, e?.code || i?.error_code || i?.code || "");
	}
	return i;
}
function tf(e) {
	return e instanceof Error && e.name === "AbortError";
}
// src/features/emailHistory/history.ts
var nf = {
	icloud_hide: "iCloud 隐藏邮箱",
	outlook: "Outlook"
}, rf = {
	available: "历史未领取",
	disabled: "已停用",
	reserved: "归属已保留",
	used: "已绑定账号",
	replaced: "换绑后地址",
	retired: "历史停用"
}, af = [
	10,
	20,
	30,
	50,
	100
], of = () => ({
	source: "all",
	parent_id: "",
	q: "",
	parent_q: "",
	state: "",
	related_q: "",
	created_from: "",
	created_to: ""
}), sf = {
	source: "来源",
	parent_id: "指定母邮箱",
	q: "子邮箱",
	parent_q: "母邮箱",
	state: "状态",
	related_q: "关联账号 / 任务",
	created_from: "开始日期",
	created_to: "结束日期"
};
function cf(e) {
	return [e.registered_account_id ? `账号 #${e.registered_account_id}` : "", e.root_task_id ? `任务 #${e.root_task_id}` : ""].filter(Boolean).join(" · ") || (["available", "disabled"].includes(e.state || "") ? "尚未领取" : "历史归属");
}
function lf(e) {
	let t = /* @__PURE__ */ Vt({
		filters: of(),
		parentEmail: "",
		page: 1,
		size: 50,
		total: 0,
		items: [],
		selected: /* @__PURE__ */ new Map(),
		loading: !1,
		error: "",
		receipt: ""
	}), n = /* @__PURE__ */ I(!1), r = !1, i = 0, a = "", o, s;
	function c() {
		let e = new URLSearchParams({
			page: String(t.page),
			page_size: String(t.size)
		});
		for (let [n, r] of Object.entries(t.filters)) r.trim() && e.set(n, r.trim());
		return `/api/email-derivation/allocations?${e}`;
	}
	function l() {
		i++, o?.abort(), o = void 0, clearTimeout(s), t.loading = !1;
	}
	async function u() {
		if (l(), !n.value) return;
		let e = i;
		o = new AbortController();
		let r = o.signal;
		t.loading = !0;
		try {
			for (let n = 0; n < 2; n++) {
				let o = c(), s = await ef(o, {
					method: "GET",
					signal: r
				});
				if (e !== i) return;
				if (!Array.isArray(s?.items) || !Number.isSafeInteger(s.total) || s.total < 0) throw Error("历史列表响应格式不完整");
				let l = Math.max(1, Math.ceil(s.total / t.size));
				if (t.page > l) {
					if (t.page = l, t.total = s.total, t.items = [], n) throw Error("列表范围已变化，请重试");
				} else {
					t.items = s.items, t.total = s.total;
					for (let e of s.items) t.selected.has(String(e.id)) && t.selected.set(String(e.id), e.email);
					a = o, t.error = "";
					return;
				}
			}
		} catch (n) {
			e === i && !tf(n) && (t.error = `子邮箱历史加载失败：${n instanceof Error ? n.message : String(n)}`);
		} finally {
			e === i && (t.loading = !1, o = void 0);
		}
	}
	function d(e = 0) {
		if (l(), a !== c() && (t.items = [], t.error = ""), !n.value) return;
		let r = i;
		t.loading = !0;
		let o = () => {
			r === i && u();
		};
		e ? s = setTimeout(o, e) : queueMicrotask(o);
	}
	function f(e = 0) {
		t.page = 1, c() !== a && (t.total = 0), t.selected.clear(), t.receipt = "", d(e);
	}
	function p(e, n) {
		t.filters[e] !== n && ((e === "source" || e === "parent_id") && (t.filters.parent_id = "", t.parentEmail = ""), t.filters[e] = n, f([
			"q",
			"parent_q",
			"related_q"
		].includes(e) ? 250 : 0));
	}
	function m(e) {
		Object.assign(t.filters, of(), {
			source: e.source,
			parent_id: e.id
		}), t.parentEmail = e.email, f();
	}
	function h() {
		Object.assign(t.filters, of()), t.parentEmail = "", f();
	}
	function g() {
		let e = r && !document.hidden;
		if (n.value !== e) {
			if (n.value = e, e) return u();
			l();
		}
	}
	function _(e) {
		return r = e, g();
	}
	Nr(() => document.addEventListener("visibilitychange", g)), ke(() => {
		document.removeEventListener("visibilitychange", g), n.value = !1, l();
	});
	function v(e) {
		t.page !== e && (t.page = e, t.receipt = "", d());
	}
	function y(e) {
		af.includes(e) && e !== t.size && (t.size = e, t.page = 1, t.receipt = "", d());
	}
	function b(e, n) {
		n ? t.selected.set(String(e.id), e.email) : t.selected.delete(String(e.id)), t.receipt = "";
	}
	function x(e) {
		for (let n of t.items) b(n, e);
	}
	async function S() {
		let n = t.selected.size ? Array.from(t.selected.values()) : t.items.map((e) => e.email);
		if (!n.length) return;
		let r = i, a = !1;
		try {
			a = await e(n.join("\n"));
		} catch {}
		r === i && (t.receipt = a ? `已复制 ${n.length} 条历史子邮箱` : "复制失败，请重试");
	}
	let C = $(() => Object.keys(sf).filter((e) => t.filters[e] !== of()[e]).map((e) => {
		let n = t.filters[e], r = e === "source" ? nf[n] : e === "state" ? rf[n] : e === "parent_id" ? t.parentEmail || `#${n}` : n;
		return {
			key: e,
			label: `${sf[e]}：${r || n}`,
			removeLabel: `移除${sf[e]}筛选`
		};
	}));
	function w(e) {
		Object.hasOwn(sf, e) && p(e, of()[e]);
	}
	return {
		state: t,
		active: n,
		chips: C,
		setView: m,
		setVisible: _,
		refresh: u,
		updateFilter: p,
		resetFilters: h,
		setPage: v,
		setSize: y,
		toggle: b,
		togglePage: x,
		copy: S,
		removeFilter: w
	};
}
// src/features/emailHistory/EmailHistoryPage.vue?vue&type=script&setup=true&lang.ts
var uf = ["aria-busy"], df = { class: "eh-toolbar" }, ff = ["disabled"], pf = {
	class: "eh-count-row",
	"data-email-count-row": ""
}, mf = {
	key: 0,
	class: "eh-error",
	role: "alert"
}, hf = {
	key: 1,
	class: "eh-note",
	role: "status"
}, gf = { class: "eh-scroll" }, _f = [
	"checked",
	"indeterminate",
	"disabled"
], vf = {
	key: 0,
	class: "eh-field"
}, yf = [
	"aria-label",
	"value",
	"onChange"
], bf = ["value"], xf = ["value"], Sf = [
	"aria-label",
	"value",
	"onInput"
], Cf = {
	key: 2,
	class: "eh-field"
}, wf = [
	"aria-label",
	"value",
	"onInput",
	"onCompositionend"
], Tf = ["onClick"], Ef = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], Df = [
	"aria-label",
	"checked",
	"onChange"
], Of = { key: 0 }, kf = {
	colspan: "8",
	class: "eh-empty",
	role: "status"
}, Af = /*#__PURE__*/ Sd(/* @__PURE__ */ U({
	__name: "EmailHistoryPage",
	props: { clipboard: { type: Function } },
	setup(e, { expose: t }) {
		let { state: n, active: r, chips: i, setView: a, setVisible: o, refresh: s, updateFilter: c, resetFilters: l, removeFilter: u, setPage: d, setSize: f, toggle: p, togglePage: m, copy: h } = lf(e.clipboard);
		t({
			setView: a,
			setVisible: o,
			refresh: s
		});
		let { widths: g, total: _, resize: v, resizeWithKeyboard: y, resetColumns: b } = Qd({
			defaults: [
				40,
				248,
				224,
				112,
				120,
				172,
				140,
				88
			],
			storageKey: "gpt_console_table_widths_derivations",
			totalStorageKey: "gpt_console_table_total_derivations",
			min: 28,
			max: 2e4
		}), x = [
			{
				key: "check",
				label: "选择"
			},
			{
				key: "child",
				label: "子邮箱",
				filter: "q"
			},
			{
				key: "parent",
				label: "母邮箱",
				filter: "parent_q"
			},
			{
				key: "source",
				label: "来源",
				filter: "source",
				options: nf
			},
			{
				key: "state",
				label: "状态",
				filter: "state",
				options: rf
			},
			{
				key: "related",
				label: "关联账号 / 任务",
				filter: "related_q"
			},
			{
				key: "date",
				label: "生成时间",
				filter: "created_from"
			},
			{
				key: "actions",
				label: "操作"
			}
		], S = $(() => n.items.filter((e) => n.selected.has(String(e.id))).length), C = /* @__PURE__ */ I("");
		H(r, (e) => {
			e || (C.value = "");
		});
		function w(e, t) {
			t ? C.value = e : C.value === e && (C.value = "");
		}
		function T(e, t) {
			t.isComposing || c(e, t.target.value);
		}
		function ee(e) {
			c(e, e === "source" ? "all" : ""), e === "created_from" && c("created_to", "");
		}
		return (e, t) => (q(), J("div", {
			class: "eh-page",
			"aria-busy": L(n).loading
		}, [
			t[6] ||= X("p", { class: "eh-note" }, "子邮箱由你手动准备并导入本地库存；此处可查看、筛选和复制已有记录，Turb 不会自动生成。", -1),
			X("div", df, [
				X("span", null, A(L(n).selected.size ? `已选 ${L(n).selected.size} 条历史记录` : "可筛选并复制历史子邮箱"), 1),
				X("button", {
					type: "button",
					class: "eh-button",
					"data-history-copy": "",
					disabled: !L(n).items.length && !L(n).selected.size,
					onClick: t[0] ||= (...e) => L(h) && L(h)(...e)
				}, A(L(n).selected.size ? "复制选中" : "复制当前页"), 9, ff),
				X("button", {
					type: "button",
					class: "eh-button eh-reset-widths",
					onClick: t[1] ||= (...e) => L(b) && L(b)(...e)
				}, "恢复列宽")
			]),
			X("div", pf, [
				X("strong", null, A(L(n).total) + " 条历史记录", 1),
				X("span", null, "当前页 " + A(L(n).items.length) + " 条", 1),
				Z(kd, {
					class: "eh-summary",
					items: L(i),
					onRemove: L(u)
				}, null, 8, ["items", "onRemove"])
			]),
			L(n).error ? (q(), J("p", mf, [Ea(A(L(n).error) + " ", 1), X("button", {
				type: "button",
				class: "eh-button",
				onClick: t[2] ||= (...e) => L(s) && L(s)(...e)
			}, "重试")])) : Da("", !0),
			L(n).receipt ? (q(), J("p", hf, A(L(n).receipt), 1)) : Da("", !0),
			X("div", gf, [X("table", {
				class: "eh-table",
				"aria-label": "历史子邮箱",
				style: ue({ width: `${L(_)}px` })
			}, [
				X("colgroup", null, [(q(!0), J(K, null, qr(L(g), (e, t) => (q(), J("col", {
					key: t,
					style: ue({ width: `${e}px` })
				}, null, 4))), 128))]),
				X("thead", null, [X("tr", null, [(q(), J(K, null, qr(x, (e, r) => X("th", {
					key: e.key,
					scope: "col"
				}, [e.key === "check" ? (q(), J("input", {
					key: 0,
					type: "checkbox",
					"aria-label": "全选当前页子邮箱",
					checked: !!L(n).items.length && S.value === L(n).items.length,
					indeterminate: S.value > 0 && S.value < L(n).items.length,
					disabled: !L(n).items.length,
					onChange: t[3] ||= (e) => L(m)(e.target.checked)
				}, null, 40, _f)) : e.filter ? (q(), Y(Cd, {
					key: 1,
					label: e.label,
					open: C.value === e.key,
					active: L(i).some((t) => t.key === e.filter || e.key === "date" && t.key === "created_to"),
					summary: e.key === "date" ? [L(n).filters.created_from, L(n).filters.created_to].filter(Boolean).join(" 至 ") : e.options?.[L(n).filters[e.filter]] || L(n).filters[e.filter],
					"onUpdate:open": (t) => w(e.key, t)
				}, {
					default: V(() => [e.options ? (q(), J("label", vf, [Ea(A(e.label) + " ", 1), X("select", {
						"aria-label": e.label,
						value: L(n).filters[e.filter],
						onChange: (t) => L(c)(e.filter, t.target.value)
					}, [X("option", { value: e.filter === "source" ? "all" : "" }, "全部", 8, bf), (q(!0), J(K, null, qr(e.options, (e, t) => (q(), J("option", {
						key: t,
						value: t
					}, A(e), 9, xf))), 128))], 40, yf)])) : e.key === "date" ? (q(), J(K, { key: 1 }, qr(["created_from", "created_to"], (e) => X("label", {
						key: e,
						class: "eh-field"
					}, [Ea(A(L(sf)[e]) + " ", 1), X("input", {
						type: "date",
						"aria-label": L(sf)[e],
						value: L(n).filters[e],
						onInput: (t) => T(e, t)
					}, null, 40, Sf)])), 64)) : (q(), J("label", Cf, [Ea(A(e.label) + " ", 1), X("input", {
						type: "search",
						"aria-label": e.label,
						value: L(n).filters[e.filter],
						onInput: (t) => T(e.filter, t),
						onCompositionend: (t) => L(c)(e.filter, t.target.value)
					}, null, 40, wf)])), X("button", {
						type: "button",
						class: "eh-button",
						onClick: (t) => ee(e.filter)
					}, "清除条件", 8, Tf)]),
					_: 2
				}, 1032, [
					"label",
					"open",
					"active",
					"summary",
					"onUpdate:open"
				])) : (q(), J(K, { key: 2 }, [t[5] ||= Ea("操作 ", -1), X("button", {
					type: "button",
					class: "eh-clear",
					onClick: t[4] ||= (...e) => L(l) && L(l)(...e)
				}, "清筛")], 64)), X("button", {
					type: "button",
					class: "eh-grip",
					"aria-label": `调整${e.label}列宽`,
					onPointerdown: $o((e) => L(v)(r, e), ["prevent"]),
					onKeydown: [ts($o((e) => L(y)(r, -10), ["prevent"]), ["left"]), ts($o((e) => L(y)(r, 10), ["prevent"]), ["right"])]
				}, null, 40, Ef)])), 64))])]),
				X("tbody", null, [(q(!0), J(K, null, qr(L(n).items, (e) => (q(), J("tr", {
					key: e.id,
					class: k({ "eh-selected": L(n).selected.has(String(e.id)) })
				}, [
					X("td", null, [X("input", {
						type: "checkbox",
						"aria-label": `选择 ${e.email}`,
						checked: L(n).selected.has(String(e.id)),
						onChange: (t) => L(p)(e, t.target.checked)
					}, null, 40, Df)]),
					X("td", null, [Z(Ed, { text: e.email }, null, 8, ["text"])]),
					X("td", null, [Z(Ed, {
						text: e.parent_email || "—",
						secondary: `母资源 #${e.parent_id || "—"}`
					}, null, 8, ["text", "secondary"])]),
					X("td", null, [Z(Ed, { text: L(nf)[e.source] || e.source }, null, 8, ["text"])]),
					X("td", null, [Z(Ed, {
						text: L(rf)[e.state || ""] || e.state || "状态记录缺失",
						tone: e.state === "disabled" ? "danger" : e.state === "available" ? "success" : "neutral"
					}, null, 8, ["text", "tone"])]),
					X("td", null, [Z(Ed, { text: L(cf)(e) }, null, 8, ["text"])]),
					X("td", null, [Z(Ed, ja({ ref_for: !0 }, L(Zd)(e.created_at)), null, 16)]),
					X("td", null, [Z(Ed, { text: "只读" })])
				], 2))), 128)), L(n).items.length ? Da("", !0) : (q(), J("tr", Of, [X("td", kf, A(L(n).loading ? "正在读取历史子邮箱…" : L(n).error ? "子邮箱历史加载失败" : "当前筛选下没有历史子地址，请从 Email Butler 等来源手动准备邮箱，再导入本地库存。"), 1)]))])
			], 4)]),
			Z(Jd, {
				page: L(n).page,
				size: L(n).size,
				total: L(n).total,
				busy: L(n).loading,
				"page-sizes": L(af),
				label: "历史子邮箱分页",
				"onUpdate:page": L(d),
				"onUpdate:size": L(f)
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy",
				"page-sizes",
				"onUpdate:page",
				"onUpdate:size"
			])
		], 8, uf));
	}
}), [["__scopeId", "data-v-7ba3bdbf"]]);
// src/emailHistory.ts
function jf(e, t) {
	let n = as(Af, { clipboard: t.clipboard }), r = n.mount(e);
	return {
		setView: r.setView,
		setVisible: r.setVisible,
		refresh: r.refresh,
		destroy: () => n.unmount()
	};
}
export { jf as mountEmailHistory };
