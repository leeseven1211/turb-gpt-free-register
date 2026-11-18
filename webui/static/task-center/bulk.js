import { $ as e, A as t, G as n, I as r, L as i, O as a, P as o, Q as s, S as c, V as l, W as u, X as d, _ as f, a as p, b as m, c as h, ct as g, dt as _, g as v, h as y, i as b, j as x, k as S, lt as C, m as w, n as T, o as E, ot as D, p as O, rt as k, s as A, t as j, tt as M, u as N, ut as P, w as F, x as I } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { _ as L, b as R, c as z, d as B, f as V, g as H, h as U, l as ee, m as W, n as G, p as K, r as q, t as te, u as J, v as Y, x as ne, y as re } from "./ListFilterSummary-NiVwXoAn.js";
import { a as ie, n as ae, o as oe, s as se, t as ce } from "./queryAdapter-C1wcY8t-.js";
import { t as le } from "./errorLabels-6tZmqsp4.js";
// node_modules/reka-ui/dist/Dialog/DialogRoot.js
var [ue, de] = /*#__PURE__*/ ne("DialogRoot"), fe = /* @__PURE__ */ c({
	inheritAttrs: !1,
	__name: "DialogRoot",
	props: {
		open: {
			type: Boolean,
			required: !1,
			default: void 0
		},
		defaultOpen: {
			type: Boolean,
			required: !1,
			default: !1
		},
		modal: {
			type: Boolean,
			required: !1,
			default: !0
		},
		unmountOnHide: {
			type: Boolean,
			required: !1,
			default: !0
		}
	},
	emits: ["update:open"],
	setup(t, { emit: n }) {
		let r = t, a = re(r, "open", n, {
			defaultValue: r.defaultOpen,
			passive: r.open === void 0
		}), o = e(), s = e(), { modal: c, unmountOnHide: l } = k(r);
		return de({
			open: a,
			modal: c,
			unmountOnHide: l,
			openModal: () => {
				a.value = !0;
			},
			onOpenChange: (e) => {
				a.value = e;
			},
			onOpenToggle: () => {
				a.value = !a.value;
			},
			contentId: "",
			titleId: "",
			descriptionId: "",
			triggerElement: o,
			contentElement: s
		}), (e, t) => i(e.$slots, "default", {
			open: D(a),
			close: () => a.value = !1
		});
	}
}), pe = /* @__PURE__ */ c({
	__name: "DialogClose",
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
		H();
		let n = ue();
		return (r, s) => (o(), y(D(B), a(t, {
			type: e.as === "button" ? "button" : void 0,
			onClick: s[0] ||= (e) => D(n).onOpenChange(!1)
		}), {
			default: u(() => [i(r.$slots, "default")]),
			_: 3
		}, 16, ["type"]));
	}
}), me = ["Enter", " "], he = [
	"ArrowDown",
	"PageUp",
	"Home"
], ge = [
	"ArrowUp",
	"PageDown",
	"End"
];
[...he, ...ge], [...me], [...me];
function _e(e) {
	return e ? "open" : "closed";
}
// node_modules/reka-ui/dist/Dialog/DialogContentImpl.js
var ve = /* @__PURE__ */ c({
	__name: "DialogContentImpl",
	props: {
		forceMount: {
			type: Boolean,
			required: !1
		},
		trapFocus: {
			type: Boolean,
			required: !1
		},
		disableOutsidePointerEvents: {
			type: Boolean,
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
		present: {
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
		let n = e, r = t, s = ue(), { forwardRef: c, currentElement: l } = H();
		return s.titleId ||= K(void 0, "reka-dialog-title"), s.descriptionId ||= K(void 0, "reka-dialog-description"), x(() => {
			s.contentElement = l, R() !== document.body && (s.triggerElement.value = R());
		}), (t, l) => (o(), y(D(ee), {
			"as-child": "",
			loop: "",
			trapped: n.trapFocus,
			present: n.present,
			onMountAutoFocus: l[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: l[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: u(() => [I(D(J), a({
				id: D(s).contentId,
				ref: D(c),
				as: e.as,
				"as-child": e.asChild,
				present: n.present,
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				role: "dialog",
				"aria-describedby": D(s).descriptionId,
				"aria-labelledby": D(s).titleId,
				"data-state": D(_e)(D(s).open.value)
			}, t.$attrs, {
				onDismiss: l[0] ||= (e) => D(s).onOpenChange(!1),
				onEscapeKeyDown: l[1] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: l[2] ||= (e) => r("focusOutside", e),
				onInteractOutside: l[3] ||= (e) => r("interactOutside", e),
				onPointerDownOutside: l[4] ||= (e) => r("pointerDownOutside", e)
			}), {
				default: u(() => [i(t.$slots, "default")]),
				_: 3
			}, 16, [
				"id",
				"as",
				"as-child",
				"present",
				"disable-outside-pointer-events",
				"aria-describedby",
				"aria-labelledby",
				"data-state"
			])]),
			_: 3
		}, 8, ["trapped", "present"]));
	}
}), ye = /* @__PURE__ */ c({
	__name: "DialogContentModal",
	props: {
		forceMount: {
			type: Boolean,
			required: !1
		},
		trapFocus: {
			type: Boolean,
			required: !1
		},
		disableOutsidePointerEvents: {
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
		},
		present: {
			type: Boolean,
			required: !0
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
		let n = e, r = t, s = ue(), c = L(r), { forwardRef: d, currentElement: f } = H(), p = O(() => n.present ? f.value : void 0);
		W(p);
		let m = O(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return l(() => n.present, (e, t) => {
			!e && t && s.triggerElement.value?.focus();
		}), (t, r) => (o(), y(ve, a({
			...m.value,
			...D(c)
		}, {
			ref: D(d),
			present: e.present,
			"trap-focus": D(s).open.value,
			"disable-outside-pointer-events": n.disableOutsidePointerEvents,
			onCloseAutoFocus: r[0] ||= (e) => {
				e.defaultPrevented || (e.preventDefault(), D(s).triggerElement.value?.focus());
			},
			onPointerDownOutside: r[1] ||= (e) => {
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0;
				(t.button === 2 || n) && e.preventDefault();
			},
			onFocusOutside: r[2] ||= (e) => {
				e.preventDefault();
			}
		}), {
			default: u(() => [i(t.$slots, "default")]),
			_: 3
		}, 16, [
			"present",
			"trap-focus",
			"disable-outside-pointer-events"
		]));
	}
}), be = /* @__PURE__ */ c({
	__name: "DialogContentNonModal",
	props: {
		forceMount: {
			type: Boolean,
			required: !1
		},
		trapFocus: {
			type: Boolean,
			required: !1
		},
		disableOutsidePointerEvents: {
			type: Boolean,
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
		present: {
			type: Boolean,
			required: !0
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
	setup(t, { emit: n }) {
		let r = t, s = L(n);
		H();
		let c = ue(), d = e(!1), f = e(!1), p = O(() => {
			let { present: e, ...t } = r;
			return t;
		});
		return l(() => r.present, (e, t) => {
			!e && t && (d.value || c.triggerElement.value?.focus(), d.value = !1, f.value = !1);
		}), (e, n) => (o(), y(ve, a({
			...p.value,
			...D(s)
		}, {
			present: t.present,
			"trap-focus": !1,
			"disable-outside-pointer-events": !1,
			onCloseAutoFocus: n[0] ||= (e) => {
				e.defaultPrevented || (d.value || D(c).triggerElement.value?.focus(), e.preventDefault()), d.value = !1, f.value = !1;
			},
			onInteractOutside: n[1] ||= (e) => {
				e.defaultPrevented || (d.value = !0, e.detail.originalEvent.type === "pointerdown" && (f.value = !0));
				let t = e.target;
				D(c).triggerElement.value?.contains(t) && e.preventDefault(), e.detail.originalEvent.type === "focusin" && f.value && e.preventDefault();
			}
		}), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16, ["present"]));
	}
}), xe = /* @__PURE__ */ c({
	__name: "DialogContent",
	props: {
		forceMount: {
			type: Boolean,
			required: !1
		},
		disableOutsidePointerEvents: {
			type: Boolean,
			required: !1,
			default: void 0
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
	emits: [
		"escapeKeyDown",
		"pointerDownOutside",
		"focusOutside",
		"interactOutside",
		"openAutoFocus",
		"closeAutoFocus"
	],
	setup(e, { emit: t }) {
		let r = e, s = t, c = ue(), l = L(s), { forwardRef: d } = H(), f = O(() => r.forceMount || !c.unmountOnHide.value);
		return (t, s) => (o(), y(D(V), {
			present: D(c).open.value,
			"force-mount": f.value
		}, {
			default: u(({ present: s }) => [D(c).modal.value ? n((o(), y(ye, a({
				key: 0,
				ref: D(d),
				present: !f.value || s
			}, {
				...r,
				...D(l),
				...t.$attrs
			}), {
				default: u(() => [i(t.$slots, "default")]),
				_: 3
			}, 16, ["present"])), [[E, e.forceMount || D(c).unmountOnHide.value || s]]) : n((o(), y(be, a({
				key: 1,
				ref: D(d),
				present: !f.value || s
			}, {
				...r,
				...D(l),
				...t.$attrs
			}), {
				default: u(() => [i(t.$slots, "default")]),
				_: 3
			}, 16, ["present"])), [[E, e.forceMount || D(c).unmountOnHide.value || s]])]),
			_: 3
		}, 8, ["present", "force-mount"]));
	}
}), Se = /* @__PURE__ */ c({
	__name: "DialogDescription",
	props: {
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1,
			default: "p"
		}
	},
	setup(e) {
		let t = e;
		H();
		let n = ue();
		return (e, r) => (o(), y(D(B), a(t, { id: D(n).descriptionId }), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), Ce = /* @__PURE__ */ c({
	__name: "DialogOverlayImpl",
	props: {
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
	setup(e) {
		let t = e, n = ue(), r = Y(t.present);
		return l(() => t.present, (e) => r.value = e), H(), (t, r) => (o(), y(D(B), {
			as: e.as,
			"as-child": e.asChild,
			"data-state": D(n).open.value ? "open" : "closed",
			style: { "pointer-events": "auto" },
			onPointerdown: r[0] ||= h(() => {}, [
				"left",
				"self",
				"prevent"
			])
		}, {
			default: u(() => [i(t.$slots, "default")]),
			_: 3
		}, 8, [
			"as",
			"as-child",
			"data-state"
		]));
	}
}), we = /* @__PURE__ */ c({
	__name: "DialogOverlay",
	props: {
		forceMount: {
			type: Boolean,
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
		let t = e, r = ue(), { forwardRef: s } = H(), c = O(() => t.forceMount || !r.unmountOnHide.value);
		return (t, l) => D(r)?.modal.value ? (o(), y(D(V), {
			key: 0,
			present: D(r).open.value,
			"force-mount": c.value
		}, {
			default: u(({ present: o }) => [n(I(Ce, a(t.$attrs, {
				ref: D(s),
				as: e.as,
				"as-child": e.asChild,
				present: !c.value || o
			}), {
				default: u(() => [i(t.$slots, "default")]),
				_: 3
			}, 16, [
				"as",
				"as-child",
				"present"
			]), [[E, e.forceMount || D(r).unmountOnHide.value || o]])]),
			_: 3
		}, 8, ["present", "force-mount"])) : v("v-if", !0);
	}
}), Te = /* @__PURE__ */ c({
	__name: "DialogPortal",
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
		return (e, n) => (o(), y(D(z), C(F(t)), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ee = /* @__PURE__ */ c({
	__name: "DialogTitle",
	props: {
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1,
			default: "h2"
		}
	},
	setup(e) {
		let t = e, n = ue();
		return H(), (e, r) => (o(), y(D(B), a(t, { id: D(n).titleId }), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), [De, Oe] = /*#__PURE__*/ ne("AlertDialogContent"), ke = /* @__PURE__ */ c({
	__name: "AlertDialogContent",
	props: {
		forceMount: {
			type: Boolean,
			required: !1
		},
		disableOutsidePointerEvents: {
			type: Boolean,
			required: !1,
			default: void 0
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
	emits: [
		"escapeKeyDown",
		"pointerDownOutside",
		"focusOutside",
		"interactOutside",
		"openAutoFocus",
		"closeAutoFocus"
	],
	setup(t, { emit: n }) {
		let r = t, s = L(n);
		H();
		let c = e();
		return Oe({ onCancelElementChange: (e) => {
			c.value = e;
		} }), (e, t) => (o(), y(D(xe), a({
			...r,
			...D(s)
		}, {
			role: "alertdialog",
			onPointerDownOutside: t[0] ||= h(() => {}, ["prevent"]),
			onInteractOutside: t[1] ||= h(() => {}, ["prevent"]),
			onOpenAutoFocus: t[2] ||= () => {
				S(() => {
					c.value?.focus({ preventScroll: !0 });
				});
			}
		}), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ae = /* @__PURE__ */ c({
	__name: "AlertDialogCancel",
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
		let t = e, n = De(), { forwardRef: r, currentElement: s } = H();
		return x(() => {
			n.onCancelElementChange(s.value);
		}), (e, n) => (o(), y(D(pe), a(t, { ref: D(r) }), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), je = /* @__PURE__ */ c({
	__name: "AlertDialogDescription",
	props: {
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1,
			default: "p"
		}
	},
	setup(e) {
		let t = e;
		return H(), (e, n) => (o(), y(D(Se), C(F(t)), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Me = /* @__PURE__ */ c({
	__name: "AlertDialogOverlay",
	props: {
		forceMount: {
			type: Boolean,
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
		let t = e;
		return H(), (e, n) => (o(), y(D(we), C(F(t)), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ne = /* @__PURE__ */ c({
	__name: "AlertDialogPortal",
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
		return (e, n) => (o(), y(D(z), C(F(t)), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Pe = /* @__PURE__ */ c({
	__name: "AlertDialogRoot",
	props: {
		open: {
			type: Boolean,
			required: !1
		},
		defaultOpen: {
			type: Boolean,
			required: !1
		},
		unmountOnHide: {
			type: Boolean,
			required: !1
		}
	},
	emits: ["update:open"],
	setup(e, { emit: t }) {
		let n = U(e, t);
		return H(), (e, t) => (o(), y(D(fe), a(D(n), { modal: !0 }), {
			default: u((t) => [i(e.$slots, "default", C(F(t)))]),
			_: 3
		}, 16));
	}
}), Fe = /* @__PURE__ */ c({
	__name: "AlertDialogTitle",
	props: {
		asChild: {
			type: Boolean,
			required: !1
		},
		as: {
			type: null,
			required: !1,
			default: "h2"
		}
	},
	setup(e) {
		let t = e;
		return H(), (e, n) => (o(), y(D(Ee), C(F(t)), {
			default: u(() => [i(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ie = ["aria-label", "aria-busy"], Le = { class: "cursor-pagination__layout" }, Re = {
	class: "cursor-pagination__count",
	"aria-live": "polite"
}, ze = { class: "cursor-pagination__actions" }, Be = ["disabled"], Ve = ["disabled"], He = ["disabled"], Ue = /*#__PURE__*/ j(/* @__PURE__ */ c({
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
		function s() {
			!n.busy && n.hasCursor && r("first");
		}
		return (t, n) => (o(), f("nav", {
			class: "cursor-pagination",
			"aria-label": e.label,
			"aria-busy": e.busy
		}, [w("div", Le, [w("span", Re, "本页 " + _(e.itemCount) + " 个", 1), w("div", ze, [
			e.hasCursor ? (o(), f("button", {
				key: 0,
				type: "button",
				class: "cursor-pagination__first",
				"data-cursor-first": "",
				disabled: e.busy,
				onClick: s
			}, "返回首页", 8, Be)) : v("", !0),
			w("button", {
				type: "button",
				"data-cursor-previous": "",
				disabled: e.busy || !e.hasPrevious,
				onClick: i
			}, "上一页", 8, Ve),
			w("button", {
				type: "button",
				"data-cursor-next": "",
				disabled: e.busy || !e.nextCursor,
				onClick: a
			}, "下一页", 8, He)
		])])], 8, Ie));
	}
}), [["__scopeId", "data-v-7fd57e6e"]]);
// src/features/bulk/contracts.ts
function X(e) {
	if (typeof e != "string" || !/^[1-9]\d*$/.test(e)) throw Error("任务标识无效");
	return e;
}
function We(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	return e;
}
// src/features/bulk/useBulkList.ts
var Ge = [
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
];
function Ke(e) {
	return {
		tab: "bulk",
		view: "list",
		cursor: e.cursor || "",
		...Object.fromEntries(Ge.map((t) => [t, e[t] || ""]))
	};
}
function qe(e) {
	return JSON.stringify([e.cursor || "", ...Ge.map((t) => e[t] || "")]);
}
function Je(e) {
	let t = new URLSearchParams({ page_size: "20" });
	e.cursor && t.set("cursor", e.cursor), e.q && t.set("q", e.q), e.operation && t.set("operation_key[]", e.operation), e.state && t.set("control_state[]", e.state);
	for (let n of ["created_from", "created_to"]) {
		if (!e[n]) continue;
		let r = /* @__PURE__ */ new Date(`${e[n]}T${n === "created_to" ? "23:59:59" : "00:00:00"}`);
		if (Number.isNaN(r.getTime())) throw Error("创建日期无效，请调整筛选条件");
		t.set(n, r.toISOString());
	}
	return t.toString();
}
function Ye(t, n) {
	let r = M(Ke(t())), i = M([]), a = M({}), o = e(null), c = M([]), u = e(!1), f = e(!1), p = e(""), m = e(""), h = O(() => c.value.length > 0), g = O(() => m.value !== qe(r.value)), _ = 0, v = !1, y, b, x = "";
	function S() {
		_++, y?.abort(), y = void 0, b = void 0, x = "", u.value = !1;
	}
	function C() {
		if (v || !f.value || t().view !== "list") return Promise.resolve();
		let e = qe(r.value);
		if (b && x === e) return b;
		S();
		let n = _, i = new AbortController();
		return y = i, u.value = !0, x = e, b = w(n, e, i), b;
	}
	async function w(e, t, s) {
		try {
			let c = await n.api.request(`/batches?${Je(r.value)}`, { signal: s.signal });
			if (v || !f.value || e !== _ || t !== qe(r.value)) return;
			if (!Array.isArray(c.items)) throw Error("批次列表响应格式无效");
			let l = c.items.map((e) => {
				let t = We(e);
				return X(t.id), { ...t };
			}), u = We(c.page);
			if (u.next_cursor != null && typeof u.next_cursor != "string") throw Error("批次分页响应格式无效");
			i.value = l, a.value = c.summary ? { ...We(c.summary) } : {}, o.value = typeof u.next_cursor == "string" && u.next_cursor ? u.next_cursor : null, m.value = t, p.value = "";
		} catch (t) {
			if (v || !f.value || e !== _ || t instanceof Error && t.name === "AbortError") return;
			p.value = t instanceof Error ? t.message : "读取批次失败，请重试", t && typeof t == "object" && "status" in t && t.status === 401 && (p.value += "，请重新登录后返回");
		} finally {
			e === _ && (u.value = !1, y = void 0, b = void 0, x = "");
		}
	}
	async function T(e) {
		r.value = Ke({
			...r.value,
			...e
		}), n.callbacks.updateNavigation(e), await C();
	}
	async function E(e) {
		c.value = [], await T({
			...e,
			cursor: ""
		});
	}
	async function D() {
		f.value && !u.value && !g.value && o.value && (c.value = [...c.value, r.value.cursor || ""], await T({ cursor: o.value }));
	}
	async function k() {
		if (!f.value || u.value || !h.value) return;
		let e = c.value, t = e[e.length - 1];
		c.value = e.slice(0, -1), await T({ cursor: t });
	}
	async function A() {
		f.value && !u.value && r.value.cursor && (c.value = [], await T({ cursor: "" }));
	}
	function j() {
		return E({
			q: "",
			operation: "",
			state: "",
			created_from: "",
			created_to: ""
		});
	}
	function N(e) {
		f.value = !!e, f.value || S();
	}
	return l(t, (e) => {
		if (e.view !== "list") {
			S();
			return;
		}
		let t = Ke(e);
		(qe(t) !== qe(r.value) || !u.value && !m.value) && (r.value = t, c.value = [], f.value && C());
	}, {
		immediate: !0,
		deep: !0
	}), d(() => {
		v = !0, S();
	}), {
		navigation: s(r),
		items: s(i),
		summary: s(a),
		nextCursor: s(o),
		loading: s(u),
		visible: s(f),
		error: s(p),
		hasPrevious: h,
		stale: g,
		refresh: C,
		setVisible: N,
		applyFilters: E,
		resetFilters: j,
		next: D,
		previous: k,
		first: A
	};
}
// src/features/bulk/BulkList.vue?vue&type=script&setup=true&lang.ts
var Xe = ["aria-busy"], Ze = {
	key: 0,
	class: "bl-kpis"
}, Qe = { class: "bl-toolbar" }, $e = { class: "bl-toolbar-main" }, et = {
	class: "bl-count",
	role: "status"
}, tt = {
	key: 1,
	class: "bl-error",
	role: "alert"
}, nt = ["disabled"], rt = { class: "bl-table" }, it = { class: "bl-col-name" }, at = { class: "bl-filter-actions" }, ot = { class: "bl-filter-options" }, st = ["checked"], ct = [
	"value",
	"checked",
	"onChange"
], lt = { class: "bl-filter-options" }, ut = ["checked"], dt = [
	"value",
	"checked",
	"onChange"
], ft = { class: "bl-filter-fields" }, pt = ["value"], mt = ["value"], ht = ["data-bulk-row"], gt = { class: "bl-col-name" }, _t = [
	"disabled",
	"title",
	"onClick"
], vt = ["title"], yt = { "data-bulk-progress": "" }, bt = { class: "bl-progress-copy" }, xt = [
	"value",
	"max",
	"aria-label"
], St = {
	key: 1,
	class: "bl-secondary"
}, Ct = { class: "bl-results" }, wt = ["disabled", "onClick"], Tt = ["disabled", "onClick"], Et = { class: "bl-date" }, Dt = ["disabled", "onClick"], Ot = { key: 0 }, kt = { colspan: "7" }, At = {
	class: "bl-empty",
	role: "status"
}, jt = /*#__PURE__*/ j(/* @__PURE__ */ c({
	__name: "BulkList",
	props: {
		navigation: {},
		deps: {}
	},
	setup(t, { expose: i }) {
		let a = t, s = Ye(() => a.navigation, a.deps), { navigation: c, items: d, summary: y, nextCursor: b, loading: x, visible: S, error: C, hasPrevious: T, stale: E } = s, k = e(null), A = e(""), j = e(), M = {
			plan_check: "查询套餐",
			token_refresh: "刷新 AT",
			password_setup: "补密码",
			twofa_setup: "补 2FA",
			codex_retry: "补 Codex",
			account_completion: "组合补全"
		}, P = {
			active: "执行中",
			paused: "已暂停",
			cancel_requested: "取消中",
			stop_requested: "停止中",
			ended: "已结束"
		}, F = {
			...P,
			settling: "汇总中",
			completed: "已完成",
			preparing: "准备中"
		}, L = [
			"success",
			"partial_success",
			"failed",
			"not_executed",
			"cancelled"
		], R = [
			"attention_required",
			"request_unknown",
			"manual_reconcile",
			"unknown",
			"unconfirmed"
		];
		function z(e) {
			return e && typeof e == "object" && !Array.isArray(e) ? e : {};
		}
		function B(e) {
			return typeof e == "number" && Number.isFinite(e) && e >= 0 ? e : null;
		}
		function V(e, t = "—") {
			return e == null || e === "" ? t : String(e);
		}
		let H = O(() => d.value.map((e) => {
			let t = z(e.summary ?? e.counts), n = {};
			for (let [e, r] of Object.entries(t)) B(r) !== null && (n[e] = r);
			let r = Object.keys(n).length > 0;
			for (let e of R) e in n && (n.failed = (n.failed || 0) + n[e], delete n[e]);
			let i = z(e.control), o = z(e.operation), s = i.paused ?? e.is_paused ? "paused" : V(i.state ?? e.control_state ?? e.state, "preparing"), c = V(o.key ?? e.operation_key ?? e.action_key), l = e.id;
			return {
				id: l,
				name: V(e.name ?? e.title, `批次 #${l}`),
				operation: M[c] || c,
				state: s,
				status: F[s] || s,
				counts: n,
				known: r,
				done: r ? L.reduce((e, t) => e + (n[t] || 0), 0) : null,
				total: B(e.target_count),
				createdAt: a.deps.callbacks.formatDateTime(e.created_at)
			};
		})), U = O(() => B(y.value.total_batches)), ee = O(() => {
			let e = [
				{
					key: "active_batches",
					label: "执行中",
					value: B(y.value.active_batches),
					unit: "批"
				},
				{
					key: "ended_batches",
					label: "已结束",
					value: B(y.value.ended_batches),
					unit: "批"
				},
				{
					key: "failed_targets",
					label: "失败账号",
					value: B(y.value.failed_targets),
					unit: "个"
				}
			], t = B(y.value.attention_targets);
			return t != null && e[2].value != null && (e[2].value += t), e.filter((e) => e.value !== null);
		}), W = O(() => {
			let e = c.value;
			return [
				["q", e.q ? `批次：${e.q}` : ""],
				["operation", e.operation ? `操作：${M[e.operation] || e.operation}` : ""],
				["state", e.state ? `状态：${P[e.state] || e.state}` : ""],
				["date", e.created_from || e.created_to ? `创建日期：${e.created_from || "不限"} 至 ${e.created_to || "不限"}` : ""]
			].filter(([, e]) => e).map(([e, t]) => ({
				key: e,
				label: t,
				removeLabel: `移除${t}`
			}));
		});
		l(() => c.value.q, (e) => {
			A.value = e || "";
		}, { immediate: !0 }), l(() => a.navigation.view, () => {
			k.value = null;
		});
		function G(e) {
			e === "date" ? s.applyFilters({
				created_from: "",
				created_to: ""
			}) : s.applyFilters({ [e]: "" });
		}
		function K(e, t) {
			s.applyFilters({ [e]: t });
		}
		function J() {
			s.applyFilters({ q: A.value.trim() }), k.value = null;
		}
		function Y(e, t) {
			S.value && !E.value && a.deps.callbacks.navigate("detail", {
				batch_id: e,
				...t ? { result_state: t } : {}
			});
		}
		function ne(e) {
			S.value && !E.value && a.deps.callbacks.navigate("detail", { batch_id: e }, !0);
		}
		async function re() {
			let e = window.getSelection();
			e?.toString() && j.value?.contains(e.anchorNode) || await s.refresh();
		}
		function ie(e) {
			e || (k.value = null), s.setVisible(e);
		}
		return i({
			refresh: re,
			setVisible: ie
		}), (e, i) => (o(), f("section", {
			class: "bl-root",
			"aria-label": "批次列表",
			"aria-busy": D(x)
		}, [
			ee.value.length ? (o(), f("div", Ze, [(o(!0), f(N, null, r(ee.value, (e) => (o(), f("div", {
				key: e.key,
				class: g(["bl-kpi", { "is-warning": e.key === "failed_targets" && !!e.value }])
			}, [w("span", null, _(e.label), 1), w("strong", null, [m(_(e.value), 1), w("small", null, _(e.unit), 1)])], 2))), 128))])) : v("", !0),
			w("div", Qe, [w("div", $e, [w("span", et, _(U.value === null ? `本页 ${D(d).length} 个批次` : `${U.value.toLocaleString()} 个批次`), 1), I(te, {
				items: W.value,
				onRemove: G
			}, null, 8, ["items"])]), W.value.length ? (o(), f("button", {
				key: 0,
				type: "button",
				class: "bl-link",
				onClick: i[0] ||= (...e) => D(s).resetFilters && D(s).resetFilters(...e)
			}, "清除筛选")) : v("", !0)]),
			D(C) ? (o(), f("div", tt, [w("span", null, _(D(C)), 1), w("button", {
				type: "button",
				class: "bl-link",
				disabled: D(x),
				onClick: i[1] ||= (...e) => D(s).refresh && D(s).refresh(...e)
			}, "重试", 8, nt)])) : v("", !0),
			w("div", {
				ref_key: "tableHost",
				ref: j,
				class: g(["bl-table-wrap", { "is-stale": D(E) && D(d).length > 0 }]),
				tabindex: "0",
				role: "region",
				"aria-label": "批次列表内容"
			}, [w("table", rt, [w("thead", null, [w("tr", null, [
				w("th", it, [I(q, {
					label: "批次名称或编号",
					"trigger-label": "批次",
					active: !!D(c).q,
					summary: D(c).q,
					open: k.value === "q",
					"onUpdate:open": i[4] ||= (e) => k.value = e ? "q" : null
				}, {
					default: u(() => [w("form", {
						class: "bl-filter-fields",
						onSubmit: h(J, ["prevent"])
					}, [w("label", null, [i[14] ||= m("名称或批次号", -1), n(w("input", {
						"onUpdate:modelValue": i[2] ||= (e) => A.value = e,
						type: "search",
						placeholder: "搜索批次名称或编号",
						autocomplete: "off"
					}, null, 512), [[p, A.value]])]), w("div", at, [w("button", {
						type: "button",
						onClick: i[3] ||= (e) => G("q")
					}, "清除此列"), i[15] ||= w("button", { type: "submit" }, "查询", -1)])], 32)]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				w("th", null, [I(q, {
					label: "操作类型",
					active: !!D(c).operation,
					summary: M[D(c).operation || ""] || D(c).operation,
					open: k.value === "operation",
					"onUpdate:open": i[6] ||= (e) => k.value = e ? "operation" : null
				}, {
					default: u(() => [w("fieldset", ot, [
						i[17] ||= w("legend", { class: "bl-sr-only" }, "操作类型", -1),
						w("label", null, [w("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: "",
							checked: !D(c).operation,
							onChange: i[5] ||= (e) => K("operation", "")
						}, null, 40, st), i[16] ||= m("全部操作", -1)]),
						(o(), f(N, null, r(M, (e, t) => w("label", { key: t }, [w("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: t,
							checked: D(c).operation === t,
							onChange: (e) => K("operation", t)
						}, null, 40, ct), m(_(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				w("th", null, [I(q, {
					label: "状态",
					active: !!D(c).state,
					summary: P[D(c).state || ""] || D(c).state,
					open: k.value === "state",
					"onUpdate:open": i[8] ||= (e) => k.value = e ? "state" : null
				}, {
					default: u(() => [w("fieldset", lt, [
						i[19] ||= w("legend", { class: "bl-sr-only" }, "运行状态", -1),
						w("label", null, [w("input", {
							type: "radio",
							name: "bulk-list-state",
							value: "",
							checked: !D(c).state,
							onChange: i[7] ||= (e) => K("state", "")
						}, null, 40, ut), i[18] ||= m("全部状态", -1)]),
						(o(), f(N, null, r(P, (e, t) => w("label", { key: t }, [w("input", {
							type: "radio",
							name: "bulk-list-state",
							value: t,
							checked: D(c).state === t,
							onChange: (e) => K("state", t)
						}, null, 40, dt), m(_(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				i[22] ||= w("th", null, "完成进度", -1),
				i[23] ||= w("th", null, "当前结果", -1),
				w("th", null, [I(q, {
					label: "创建时间",
					active: !!(D(c).created_from || D(c).created_to),
					summary: `${D(c).created_from || "不限"} 至 ${D(c).created_to || "不限"}`,
					open: k.value === "date",
					"onUpdate:open": i[12] ||= (e) => k.value = e ? "date" : null
				}, {
					default: u(() => [w("div", ft, [
						w("label", null, [i[20] ||= m("开始日期", -1), w("input", {
							type: "date",
							value: D(c).created_from,
							onChange: i[9] ||= (e) => K("created_from", e.target.value)
						}, null, 40, pt)]),
						w("label", null, [i[21] ||= m("截止日期", -1), w("input", {
							type: "date",
							value: D(c).created_to,
							onChange: i[10] ||= (e) => K("created_to", e.target.value)
						}, null, 40, mt)]),
						w("button", {
							type: "button",
							onClick: i[11] ||= (e) => G("date")
						}, "清除此列")
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				i[24] ||= w("th", null, [w("span", { class: "bl-sr-only" }, "操作")], -1)
			])]), w("tbody", null, [(o(!0), f(N, null, r(H.value, (e) => (o(), f("tr", {
				key: e.id,
				"data-bulk-row": e.id
			}, [
				w("td", gt, [w("button", {
					type: "button",
					class: "bl-name",
					"data-bulk-open": "",
					disabled: D(E),
					title: e.name,
					onClick: (t) => Y(e.id)
				}, _(e.name), 9, _t), w("span", {
					class: "bl-secondary",
					title: `批次 #${e.id}`
				}, "#" + _(e.id), 9, vt)]),
				w("td", null, _(e.operation), 1),
				w("td", null, [w("span", { class: g(["bl-status", `is-${e.state}`]) }, _(e.status), 3)]),
				w("td", yt, [e.total !== null && e.done !== null ? (o(), f(N, { key: 0 }, [w("span", bt, _(e.done) + " / " + _(e.total), 1), w("progress", {
					value: e.done,
					max: Math.max(1, e.total),
					"aria-label": `已结束 ${e.done} 个，共 ${e.total} 个`
				}, null, 8, xt)], 64)) : (o(), f("span", St, _(e.total === null ? "名单准备中" : "结果待汇总"), 1))]),
				w("td", null, [w("div", Ct, [w("button", {
					type: "button",
					class: "bl-result is-success",
					"data-bulk-result": "success",
					disabled: D(E) || !e.counts.success,
					onClick: (t) => Y(e.id, "success")
				}, "成功 " + _(e.known ? e.counts.success || 0 : "—"), 9, wt), w("button", {
					type: "button",
					class: "bl-result is-failed",
					"data-bulk-result": "failed",
					disabled: D(E) || !e.counts.failed,
					onClick: (t) => Y(e.id, "failed")
				}, "失败 " + _(e.known ? e.counts.failed || 0 : "—"), 9, Tt)])]),
				w("td", Et, _(e.createdAt), 1),
				w("td", null, [w("button", {
					type: "button",
					class: "bl-button",
					"data-bulk-report": "",
					disabled: D(E),
					onClick: (t) => ne(e.id)
				}, "查看报告", 8, Dt)])
			], 8, ht))), 128)), H.value.length ? v("", !0) : (o(), f("tr", Ot, [w("td", kt, [w("div", At, [w("strong", null, _(D(x) ? "正在加载批次…" : D(C) ? "暂时无法读取批次" : W.value.length ? "没有匹配的批次" : "还没有批次"), 1), !D(x) && !D(C) ? (o(), f(N, { key: 0 }, [i[25] ||= w("p", null, "选择操作和账号范围，即可集中执行与追踪结果。", -1), w("button", {
				type: "button",
				class: "bl-button",
				"data-bulk-create": "",
				onClick: i[13] ||= (e) => t.deps.callbacks.navigate("create")
			}, "新建批次")], 64)) : v("", !0)])])]))])])], 2),
			I(Ue, {
				"has-previous": D(T),
				"next-cursor": D(E) ? null : D(b),
				"item-count": D(d).length,
				"has-cursor": !!D(c).cursor,
				busy: D(x),
				label: "批次分页",
				onPrevious: D(s).previous,
				onNext: D(s).next,
				onFirst: D(s).first
			}, null, 8, [
				"has-previous",
				"next-cursor",
				"item-count",
				"has-cursor",
				"busy",
				"onPrevious",
				"onNext",
				"onFirst"
			])
		], 8, Xe));
	}
}), [["__scopeId", "data-v-2d5a650e"]]), Mt = class extends Error {
	status;
	code;
	details;
	field;
	fields;
	requestId;
	retryable;
	constructor(e, t, n = "", r = {}, i = null, a = {}, o, s) {
		super(e), this.status = t, this.code = n, this.details = r, this.field = i, this.fields = a, this.requestId = o, this.retryable = s, this.name = "BulkApiError";
	}
};
function Nt(e = fetch) {
	return { async request(t, n = {}) {
		if (!t.startsWith("/") || t.startsWith("//")) throw Error("批量接口路径无效");
		let r = await e("/api/bulk" + t, {
			credentials: "same-origin",
			...n
		}), i = r.headers?.get("content-type");
		if (i && !i.includes("application/json")) throw new Mt(r.status === 401 || r.redirected ? "登录已失效，请重新登录后返回。" : "服务返回了非 JSON 响应", r.status);
		let a = await r.json().catch(() => null), o = a && typeof a == "object" && !Array.isArray(a) ? a : {};
		if (!r.ok || o.ok === !1) {
			let e = o.error && typeof o.error == "object" && !Array.isArray(o.error) ? o.error : o, t = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {};
			throw new Mt(String(e.message || (typeof o.error == "string" ? o.error : "") || `请求失败（HTTP ${r.status}）`), r.status, String(e.code || o.code || ""), t(e.details || o.details), typeof e.field == "string" ? e.field : null, t(e.fields || o.fields), typeof o.request_id == "string" ? o.request_id : void 0, typeof e.retryable == "boolean" ? e.retryable : void 0);
		}
		if (typeof a != "object" || !a || Array.isArray(a) || o.ok === !0 && (!o.data || typeof o.data != "object" || Array.isArray(o.data))) throw new Mt("服务返回了无效 JSON 响应", r.status);
		return o.data ?? o;
	} };
}
// src/features/bulk/useBulkCreate.ts
var Pt = "turb_bulk_draft_v1", Ft = "turb_bulk_selection_v1", It = (e) => JSON.parse(JSON.stringify(e)), Lt = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {};
function Rt(t) {
	let n = () => ({
		name: "",
		operation_key: "plan_check",
		query: t.adapter.normalize(),
		source: null,
		parameters: {},
		max_concurrency: 3
	}), r = (e) => {
		try {
			return JSON.parse(t.storage.getItem(e) || "null");
		} catch {
			return null;
		}
	}, i = e(n()), a = e(null), o = e(null), s = e({}), c = e(null), l = e(!1), u = e(!1), f = e(!1), p = e(""), m = e(""), h = e(""), g = e(0), _ = /* @__PURE__ */ new Map(), v = /* @__PURE__ */ new Set(), y = 0, b = !1, x = !0, S = !1, C = null, w = null, T = null, E = null, D, k = O(() => o.value?.operations || []), A = O(() => k.value.find((e) => e.key === i.value.operation_key)), j = O(() => String(A.value?.effective_settings?.config_revision ?? A.value?.config_revision ?? o.value?.config_revision ?? "")), M = O(() => a.value?.state || a.value?.status || ""), N = O(() => M.value === "preparing"), P = O(() => Number(o.value?.limits?.concurrency_max) || 128), F = O(() => {
		g.value;
		try {
			return t.intents.pending().length;
		} catch {
			return 1;
		}
	}), I = O(() => M.value === "ready" ? Number(a.value?.target_count ?? a.value?.total_count) : i.value.source?.kind === "ids" ? i.value.source.ids.length : i.value.source ? null : c.value), L = O(() => i.value.source?.kind === "ids" ? `已选 ${i.value.source.ids.length} 个账号` : i.value.source?.kind === "batch_targets" ? `批次 #${i.value.source.batch_id} 的固定名单` : i.value.query.filters.email ? `邮箱含「${i.value.query.filters.email}」` : "按当前筛选"), R = O(() => u.value ? "正在固定账号范围…" : M.value === "ready" ? "账号范围已固定" : I.value === 0 ? "没有匹配账号" : "匹配账号数量"), z = O(() => u.value ? "正在准备本批次，请稍候" : M.value === "ready" ? "将使用这份固定名单创建批次" : I.value === 0 ? "请调整账号筛选条件" : i.value.source?.kind === "batch_targets" ? "创建时沿用原批次固定名单" : i.value.source?.kind === "ids" ? "将使用已选账号创建批次" : c.value == null ? "正在统计，创建时会核对最终数量" : `当前条件匹配 ${c.value} 个账号，将全部执行`), B = O(() => A.value?.availability?.available === !1 ? `当前设置不可用：${A.value.availability.reason || Lt(A.value.availability).reason_code || "请检查配置"}。请到配置页调整。` : "");
	function V() {
		try {
			t.storage.setItem(Pt, JSON.stringify(i.value));
		} catch {}
	}
	function H() {
		try {
			a.value ? t.storage.setItem(Ft, JSON.stringify(a.value)) : t.storage.removeItem(Ft);
		} catch {}
	}
	function U(e) {
		return [e?.request_parameters, e?.parameters].some((e) => Object.keys(e || {}).some((e) => e !== "timezone_offset_min" || i.value.operation_key !== "plan_check"));
	}
	function ee(e) {
		let r = Lt(e), i = t.adapter.normalize(Lt(r.query)), a = r.source && typeof r.source == "object" ? It(r.source) : null;
		return {
			limited: !a && !!(r.limit || i.limit),
			draft: {
				...n(),
				name: String(r.name || ""),
				operation_key: String(r.operation_key || "plan_check"),
				query: t.adapter.normalize({
					...i,
					limit: null
				}),
				source: a,
				parameters: {},
				max_concurrency: Number(r.max_concurrency ?? 3)
			}
		};
	}
	function W(e, t) {
		let n = ee(e);
		i.value = n.draft;
		let r = Lt(t);
		a.value = typeof r.id == "string" ? It(r) : null, (n.limited || U(a.value)) && (a.value = null), V(), H();
	}
	W(r(Pt), r(Ft));
	function G() {
		p.value = "", m.value = "", h.value = "";
	}
	function K(e, t = "") {
		let n = e;
		p.value = t + (n.message || String(e)) + (n.code ? `（${n.code}）` : "") + (n.status === 401 ? "，请重新登录后返回，草稿与请求身份已保留。" : ""), m.value = n.field || "";
	}
	let q = (e) => Lt(e).name === "AbortError";
	function te(e) {
		x = e, e || (clearTimeout(D), v.forEach((e) => e.abort()));
	}
	async function J(e) {
		let n = new AbortController();
		v.add(n);
		try {
			let r = await t.api.request(e, { signal: n.signal });
			if (n.signal.aborted) throw new DOMException("读取已取消", "AbortError");
			return r;
		} finally {
			v.delete(n);
		}
	}
	async function Y(e = !1) {
		if (o.value && !e) return;
		let t = await J("/catalog");
		b || (o.value = t, k.value.some((e) => e.key === i.value.operation_key) || (i.value.operation_key = k.value[0]?.key || "", a.value = null, H(), V()));
	}
	async function ne() {
		if (!x || b) return;
		let e = y, n = JSON.stringify(t.adapter.normalize(i.value.query)), r = _.get(n);
		if (r && t.now() - r.at < 3e4) {
			s.value = r.facets, c.value = r.matched;
			return;
		}
		c.value = null;
		let a = await J(`/query-facets?query=${encodeURIComponent(n)}`), o = Lt(a.facets || a), l = a.matched == null ? null : Number(a.matched);
		_.set(n, {
			facets: o,
			matched: l,
			at: t.now()
		}), _.size > 10 && _.delete(_.keys().next().value), !b && e === y && n === JSON.stringify(t.adapter.normalize(i.value.query)) && (s.value = o, c.value = l);
	}
	function re() {
		if (clearTimeout(D), !x) return;
		let e = y;
		D = setTimeout(() => {
			ne().catch((t) => {
				!q(t) && !b && e === y && K(t, "筛选选项更新失败：");
			});
		}, 350);
	}
	function se() {
		y++, E = null, u.value = !1, a.value = null, H();
	}
	function ce(e) {
		se(), clearTimeout(D), W(It(e), null), c.value = null, G(), S && re();
	}
	function le(e, t) {
		u.value || (e === "name" ? i.value.name = String(t) : i.value.max_concurrency = Number(t), V());
	}
	function ue(e) {
		u.value || i.value.operation_key === e || (i.value.operation_key = e, se(), G(), V());
	}
	function de(e) {
		if (u.value) return;
		let n = t.adapter.normalize({
			...e,
			limit: null
		});
		JSON.stringify(n) !== JSON.stringify(i.value.query) && (i.value.query = n, c.value = null, se(), G(), V(), re());
	}
	function fe(e, t) {
		let n = It(i.value.query);
		[
			"q",
			"archived",
			"date_from",
			"date_to",
			"plan"
		].includes(e) ? Object.assign(n, { [e]: t }) : Object.assign(n.filters, { [e]: t }), de(n);
	}
	function pe(e) {
		e === "date" ? de({
			...i.value.query,
			date_from: "",
			date_to: ""
		}) : fe(e, e === "archived" ? "0" : [
			"q",
			"email",
			"id"
		].includes(e) ? "" : []);
	}
	function me() {
		u.value || (i.value.source = null, i.value.query = t.adapter.normalize(), c.value = null, se(), G(), V(), re());
	}
	function he(e, n) {
		return t.callbacks.facetLabel?.(e, n) || n;
	}
	function ge(e) {
		let t = o.value?.query_schema?.fields, n = Array.isArray(t) ? t.map(Lt).find((t) => t.key === e) : void 0, r = n?.options ?? n?.enum ?? n?.values, a = s.value[e] ?? (Array.isArray(r) ? r : []), c = /* @__PURE__ */ new Map();
		for (let t of a) {
			let n = typeof t == "object" && t ? t : { value: String(t) };
			n.value && c.set(n.value, {
				...n,
				label: n.label || he(e === "token" ? "account_token" : e, n.value)
			});
		}
		for (let t of oe(i.value.query, e)) c.has(t) || c.set(t, {
			value: t,
			label: he(e === "token" ? "account_token" : e, t)
		});
		return [...c.values()];
	}
	let _e = O(() => [
		...ie(i.value.query, he),
		...i.value.query.q ? [{
			key: "q",
			label: `搜索：${i.value.query.q}`,
			removeLabel: "清除高级搜索",
			title: i.value.query.q
		}] : [],
		...i.value.query.archived === "0" ? [] : [{
			key: "archived",
			label: i.value.query.archived === "only" ? "仅归档账号" : "含归档账号",
			removeLabel: "清除归档筛选",
			title: ""
		}]
	]);
	function ve() {
		let e = A.value?.parameter_schema;
		return e?.timezone_offset_min || Lt(e?.properties).timezone_offset_min ? { timezone_offset_min: (/* @__PURE__ */ new Date()).getTimezoneOffset() } : {};
	}
	async function ye() {
		if (!a.value || !x || b) return;
		let e = X(a.value.id), t = y, n = await J(`/selections/${encodeURIComponent(e)}?page_size=1`);
		b || t !== y || a.value?.id !== e || (a.value = {
			...a.value,
			...n
		}, H());
	}
	async function be() {
		if (x && !b) {
			if (C) return C;
			if (!S) return l.value = !0, C = (async () => {
				try {
					if (await Y(), b || !x) return;
					let e = y;
					try {
						await ne();
					} catch (t) {
						if (q(t)) return;
						e === y && K(t, "筛选选项读取失败：");
					}
					!b && e === y && a.value && await ye(), S = !0;
				} catch (e) {
					!q(e) && !b && K(e, "读取配置失败：");
				} finally {
					l.value = !1, C = null;
				}
			})(), C;
		}
	}
	async function xe(e, n) {
		if (q(e) || b || n !== y) return;
		E = null, u.value = !1, K(e, "创建失败：");
		let r = e;
		if (["config_revision_changed", "selection_settings_mismatch"].includes(r.code)) {
			a.value = null, H();
			try {
				await Y(!0);
			} catch (e) {
				K(e, "配置读取失败：");
			}
			!b && n === y && t.callbacks.notify("配置已更新，请重新创建批次。");
		} else r.code === "selection_consumed" && r.details?.existing_batch_id ? (h.value = String(r.details.existing_batch_id), t.callbacks.notify(`该范围已用于批次 #${h.value}`)) : r.code === "selection_expired" && (a.value = null, H());
	}
	async function Se() {
		let e = E;
		if (!e || e.epoch !== y || T === y || b || !x) return;
		let n = y;
		T = n;
		try {
			if (M.value === "preparing") return;
			let r = a.value;
			if (!r || M.value !== "ready") throw new Mt(r?.error?.message || r?.error_detail?.message || "账号范围准备失败，请重试", 0, r?.error_code || "selection_preparation_failed");
			if (Number(r.target_count ?? r.total_count) <= 0) throw new Mt("没有匹配账号，请调整筛选条件", 0, "selection_empty");
			let o = A.value;
			if (!o) throw new Mt("没有可用的批量操作", 0, "operation_unavailable");
			let s = {
				name: i.value.name,
				selection_id: X(r.id),
				selection_revision: r.selection_revision,
				operation: {
					key: o.key,
					version: o.version || 1
				},
				expected_config_revision: r.config_revision || j.value,
				parameters: r.request_parameters || ve(),
				execution: {
					max_concurrency: Number(i.value.max_concurrency),
					start_paused: e.paused
				}
			}, c = await t.intents.submit("create", "/batches", s), l = X(c.id || c.batch_id);
			if (b || n !== y) {
				t.callbacks.notify(`原批次 #${l} 已创建${e.paused ? "并暂停" : ""}`);
				return;
			}
			a.value = null, H(), E = null, u.value = !1, t.callbacks.notify(x ? e.paused ? "批次已创建并暂停，可在详情继续执行" : "批次已受理，正在后台提交目标" : `原批次 #${l} 已创建${e.paused ? "并暂停" : ""}`), x && t.callbacks.navigate("detail", { batch_id: l });
		} catch (e) {
			await xe(e, n);
		} finally {
			g.value++, T === n && (T = null);
		}
	}
	async function Ce(e = !1) {
		if (u.value || f.value || b || !x) return;
		G();
		let n = Number(i.value.max_concurrency);
		if (!Number.isInteger(n) || n < 1 || n > P.value) {
			K(new Mt(`本批并发上限需为 1–${P.value} 的整数`, 0, "invalid_concurrency", {}, "max_concurrency"));
			return;
		}
		if (i.value.name.length > 120) {
			K(new Mt("批次名称最多 120 个字符", 0, "invalid_name", {}, "name"));
			return;
		}
		if (!A.value) {
			K(new Mt("请先读取可用的批量操作", 0, "operation_unavailable"));
			return;
		}
		U(a.value) && (a.value = null, H());
		let r = y;
		E = {
			epoch: r,
			paused: e
		}, u.value = !0;
		try {
			if (!["ready", "preparing"].includes(M.value)) {
				let e = A.value, n = {
					operation: {
						key: e.key,
						version: e.version || 1
					},
					source: It(i.value.source || {
						kind: "query",
						query: t.adapter.normalize({
							...i.value.query,
							limit: null
						})
					}),
					parameters: ve(),
					expected_config_revision: j.value
				}, o = await t.intents.submit("selection", "/selections", n);
				if (b || r !== y) return;
				a.value = {
					...o,
					request_parameters: n.parameters,
					config_revision: n.expected_config_revision
				}, H(), V();
			}
			M.value === "preparing" && await ye(), !b && r === y && await Se();
		} catch (e) {
			await xe(e, r);
		} finally {
			g.value++;
		}
	}
	async function we(e = !1) {
		if (b || !x) return;
		if (w?.epoch === y) return w.promise;
		let t = y, n = (async () => {
			let n = !S;
			if (n && await be(), !b && x && S && t === y) try {
				e && await Y(!0), n || (a.value ? await ye() : await ne()), t === y && await Se();
			} catch (e) {
				!q(e) && t === y && (E ? await xe(e, t) : K(e, "读取账号范围失败："));
			}
		})();
		w = {
			epoch: t,
			promise: n
		};
		try {
			await n;
		} finally {
			w?.promise === n && (w = null);
		}
	}
	function Te(e, r) {
		let i = Lt(e.source), a = Lt(e.operation), o = t.adapter.normalize(i.kind === "query" ? Lt(i.query) : {}), s = {
			...n(),
			operation_key: String(a.key || "plan_check"),
			query: o,
			source: i.kind === "query" ? null : i
		};
		se(), W(s, {
			...r,
			request_parameters: Lt(e.parameters),
			config_revision: e.expected_config_revision
		});
	}
	async function Ee() {
		if (f.value || u.value || b) return;
		f.value = !0, G();
		let e = y;
		try {
			let n = t.intents.pending()[0];
			if (!n) return;
			let r = await t.intents.recover(n);
			if (b || e !== y || !x) {
				t.callbacks.notify(n.path === "/batches" ? `原批次 #${X(r.id || r.batch_id)} 已创建` : "原请求回执已找回，当前草稿保留。");
				return;
			}
			if (n.path === "/selections") Te(n.body, r), t.callbacks.navigate("create"), t.callbacks.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
			else if (n.path === "/batches") a.value = null, H(), t.callbacks.navigate("detail", { batch_id: X(r.id || r.batch_id) });
			else {
				let e = n.path.match(/^\/batches\/(\d+)\//);
				e && t.callbacks.navigate("detail", { batch_id: X(e[1]) }), t.callbacks.notify("原请求回执已找回。");
			}
		} catch (e) {
			K(e, "找回请求失败：");
		} finally {
			f.value = !1, g.value++;
		}
	}
	return d(() => {
		b = !0, y++, clearTimeout(D), v.forEach((e) => e.abort()), v.clear(), E = null;
	}), {
		draft: i,
		selection: a,
		catalog: o,
		facets: s,
		matched: c,
		loading: l,
		creating: u,
		recovering: f,
		error: p,
		errorField: m,
		existingBatchId: h,
		operations: k,
		operation: A,
		configRevision: j,
		selectionState: M,
		needsRefresh: N,
		concurrencyMax: P,
		pendingCount: F,
		count: I,
		scopeLabel: L,
		summary: R,
		hint: z,
		availabilityWarning: B,
		chips: _e,
		accountFilters: ae,
		initialize: be,
		refresh: we,
		recover: Ee,
		restoreSelectionRequest: Te,
		loadFacets: ne,
		applySeed: ce,
		setVisible: te,
		setDraftField: le,
		setOperation: ue,
		setQueryField: fe,
		clearFilter: pe,
		clearFilters: me,
		filterOptions: ge,
		createBatch: Ce,
		clearError: G
	};
}
// src/features/bulk/BulkCreate.vue?vue&type=script&setup=true&lang.ts
var zt = {
	key: 0,
	class: "bulk-empty",
	role: "status"
}, Bt = ["aria-busy"], Vt = { class: "bulk-create-main" }, Ht = { class: "bulk-card bulk-create-card" }, Ut = {
	class: "bulk-operation-grid",
	role: "radiogroup",
	"aria-label": "批量操作"
}, Wt = ["title"], Gt = [
	"value",
	"checked",
	"disabled",
	"onChange"
], Kt = {
	viewBox: "0 0 24 24",
	fill: "none",
	stroke: "currentColor",
	"stroke-width": "1.6",
	"stroke-linecap": "round",
	"stroke-linejoin": "round",
	"aria-hidden": "true"
}, qt = ["d"], Jt = { class: "bulk-card bulk-create-card" }, Yt = {
	key: 0,
	class: "bulk-error bulk-operation-warning",
	"data-bulk-operation-warning": ""
}, Xt = { class: "bulk-batch-fields" }, Zt = { class: "bulk-field bulk-name-field" }, Qt = [
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], $t = { class: "bulk-field" }, en = [
	"max",
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], tn = {
	class: "bulk-card bulk-create-card",
	"data-bulk-account-scope": ""
}, nn = { class: "bulk-step-head" }, rn = ["disabled"], an = {
	key: 0,
	class: "bulk-source-banner"
}, on = ["disabled"], sn = { "data-bulk-filters": "" }, cn = { class: "bulk-query-top" }, ln = { class: "bulk-field bulk-query-search" }, un = ["value", "disabled"], dn = ["open"], fn = { class: "bulk-filter-popover-panel" }, pn = { class: "bulk-filter-popover-heading" }, mn = { class: "bulk-field" }, hn = ["value", "disabled"], gn = { class: "bulk-field" }, _n = ["value", "disabled"], vn = ["open"], yn = { class: "bulk-filter-popover-panel" }, bn = { class: "bulk-filter-popover-heading" }, xn = { class: "bulk-field" }, Sn = ["value", "disabled"], Cn = { class: "bulk-field" }, wn = ["value", "disabled"], Tn = {
	class: "bulk-column-filters",
	"aria-label": "账号列筛选"
}, En = ["data-filter-field", "open"], Dn = ["onClick"], On = {
	key: 0,
	"data-filter-count": ""
}, kn = { class: "bulk-filter-popover-panel" }, An = { class: "bulk-filter-popover-heading" }, jn = ["aria-label"], Mn = {
	key: 0,
	class: "bulk-field"
}, Nn = [
	"data-query-filter",
	"value",
	"disabled",
	"onInput"
], Pn = {
	key: 1,
	class: "bulk-filter-options"
}, Fn = [
	"data-query-filter",
	"value",
	"checked",
	"disabled",
	"onChange"
], In = {
	key: 0,
	class: "bulk-muted"
}, Ln = {
	class: "bulk-query-chips",
	"data-query-chips": "",
	"aria-label": "已选账号条件"
}, Rn = [
	"data-clear-query",
	"aria-label",
	"disabled",
	"onClick"
], zn = {
	key: 0,
	class: "bulk-filter-empty"
}, Bn = { class: "bulk-card bulk-create-side" }, Vn = { class: "bulk-side-sticky" }, Hn = { class: "bulk-side-heading" }, Un = { "data-bulk-create-summary": "" }, Wn = {
	class: "bulk-side-big",
	"data-bulk-side-count": "",
	role: "status",
	"aria-live": "polite",
	"aria-atomic": "true"
}, Gn = {
	class: "bulk-side-hint",
	"data-bulk-create-hint": ""
}, Kn = { class: "bulk-side-meta" }, qn = { "data-bulk-side-operation": "" }, Jn = { "data-bulk-side-scope": "" }, Yn = { "data-bulk-side-concurrency": "" }, Xn = {
	key: 0,
	class: "bulk-side-warning",
	"data-bulk-side-warning": ""
}, Zn = {
	key: 1,
	id: "bulkCreateError",
	class: "bulk-error",
	"data-bulk-action-error": "",
	role: "alert"
}, Qn = {
	key: 2,
	class: "bulk-notice",
	"data-bulk-recovery": "",
	role: "status"
}, $n = ["disabled"], er = { class: "bulk-side-actions" }, tr = ["disabled"], nr = ["disabled"], rr = /* @__PURE__ */ c({
	__name: "BulkCreate",
	props: {
		navigation: {},
		deps: {},
		seed: {},
		visible: {
			type: Boolean,
			default: !0
		}
	},
	setup(t, { expose: i }) {
		let a = t, s = Rt(a.deps), { draft: c, loading: u, creating: d, recovering: p, error: y, errorField: b, existingBatchId: C, operations: T, operation: k, concurrencyMax: j, pendingCount: M, count: P, scopeLabel: F, summary: I, hint: L, availabilityWarning: R, chips: z, needsRefresh: B } = s, V = e(), H = e(""), U = O(() => d.value || p.value), ee = s.accountFilters.filter((e) => !["email", "date"].includes(e.key)), W = {
			plan_check: "套餐与优惠",
			token_refresh: "获取最新访问令牌",
			password_setup: "补充登录密码",
			twofa_setup: "启用验证器",
			codex_retry: "获取授权凭证",
			account_completion: "完成已配置的项目"
		}, G = {
			plan_check: "M4 5h16v14H4z M4 10h16 M8 14h3",
			token_refresh: "M20 7v5h-5 M4 17v-5h5 M6 8a7 7 0 0 1 12-2l2 2 M4 16l2 2a7 7 0 0 0 12-2",
			password_setup: "M8 11V7a4 4 0 0 1 8 0v4 M6 11h12v10H6z M12 15v2",
			twofa_setup: "M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7z M8 12l3 3 5-6",
			codex_retry: "M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16",
			account_completion: "M9 5h11 M9 12h11 M9 19h11 M3 5h1 M3 12h1 M3 19h1"
		};
		function K(e) {
			return e.target.value;
		}
		function q(e, t, n) {
			let r = new Set(oe(c.value.query, e));
			n ? r.add(t) : r.delete(t), s.setQueryField(e, [...r]);
		}
		function te(e) {
			let t = (e?.target)?.closest("details");
			H.value = "", (t?.querySelector("summary"))?.focus();
		}
		function J(e) {
			U.value || (H.value = H.value === e ? "" : e);
		}
		function Y(e) {
			let t = e.target.closest("details");
			t && !t.contains(e.relatedTarget) && (H.value = "");
		}
		return l(() => a.seed, (e) => {
			e && s.applySeed(e);
		}, { immediate: !0 }), l(() => a.visible, (e) => {
			s.setVisible(e), e || (H.value = "");
		}, { immediate: !0 }), l(b, async (e) => {
			e && (await S(), Array.from(V.value?.querySelectorAll("[name],[data-query],[data-query-filter]") || []).find((t) => (t.name || t.dataset.query || t.dataset.queryFilter) === e)?.focus({ preventScroll: !0 }));
		}), x(() => {
			a.visible && s.initialize();
		}), i({
			refresh: s.refresh,
			recover: s.recover,
			restoreSelectionRequest: s.restoreSelectionRequest,
			setVisible: s.setVisible,
			needsRefresh: B
		}), (e, i) => D(u) && !D(T).length ? (o(), f("div", zt, "正在读取操作和筛选配置…")) : (o(), f("form", {
			key: 1,
			ref_key: "form",
			ref: V,
			"data-bulk-create-form": "",
			class: "bulk-create-form",
			novalidate: "",
			"aria-busy": U.value,
			onSubmit: i[18] ||= h((e) => D(s).createBatch(), ["prevent"]),
			onKeydown: i[19] ||= A((e) => te(e), ["esc"])
		}, [w("div", Vt, [
			w("section", Ht, [i[21] ||= w("div", { class: "bulk-step-head" }, [w("span", { class: "bulk-step-no" }, "1"), w("div", null, [w("h3", null, "选择操作"), w("p", { class: "bulk-section-note" }, "本次要对账号做什么")])], -1), w("div", Ut, [(o(!0), f(N, null, r(D(T), (e) => (o(), f("label", {
				key: e.key,
				class: "bulk-operation",
				title: e.availability?.available === !1 ? e.availability.reason || "当前不可用" : ""
			}, [
				w("input", {
					type: "radio",
					name: "operation_key",
					value: e.key,
					checked: D(c).operation_key === e.key,
					disabled: U.value,
					required: "",
					onChange: (t) => D(s).setOperation(e.key)
				}, null, 40, Gt),
				(o(), f("svg", Kt, [w("path", { d: G[e.key] || G.account_completion }, null, 8, qt)])),
				w("span", null, [w("strong", null, _(e.label || e.key), 1), w("small", null, _(W[e.key] || "批量账号操作"), 1)]),
				i[20] ||= w("span", {
					class: "bulk-operation-check",
					"aria-hidden": "true"
				}, "✓", -1)
			], 8, Wt))), 128))])]),
			w("section", Jt, [
				i[24] ||= w("div", { class: "bulk-step-head" }, [w("span", { class: "bulk-step-no" }, "2"), w("div", null, [w("h3", null, "批次设置")])], -1),
				D(R) ? (o(), f("p", Yt, _(D(R)), 1)) : v("", !0),
				w("div", Xt, [w("label", Zt, [i[22] ||= m("批次名称", -1), w("input", {
					name: "name",
					maxlength: "120",
					value: D(c).name,
					placeholder: "留空自动命名",
					disabled: U.value,
					"aria-invalid": D(b) === "name" || void 0,
					"aria-describedby": D(b) === "name" ? "bulkCreateError" : void 0,
					onInput: i[0] ||= (e) => D(s).setDraftField("name", K(e))
				}, null, 40, Qt)]), w("label", $t, [i[23] ||= m("本批并发上限", -1), w("input", {
					name: "max_concurrency",
					type: "number",
					min: "1",
					max: D(j),
					step: "1",
					value: D(c).max_concurrency,
					required: "",
					disabled: U.value,
					"aria-invalid": D(b) === "max_concurrency" || void 0,
					"aria-describedby": D(b) === "max_concurrency" ? "bulkCreateError" : void 0,
					onInput: i[1] ||= (e) => D(s).setDraftField("max_concurrency", K(e))
				}, null, 40, en)])])
			]),
			w("section", tn, [
				w("div", nn, [
					i[25] ||= w("span", { class: "bulk-step-no" }, "3", -1),
					i[26] ||= w("div", null, [w("h3", null, "账号范围"), w("p", { class: "bulk-section-note" }, "与账号列表使用同一套筛选")], -1),
					w("button", {
						type: "button",
						class: "bulk-link",
						"data-bulk-action": "clear-filters",
						disabled: U.value,
						onClick: i[2] ||= (...e) => D(s).clearFilters && D(s).clearFilters(...e)
					}, "清空条件", 8, rn)
				]),
				D(c).source ? (o(), f("div", an, [w("span", null, _(D(c).source.kind === "ids" ? "使用已选账号" : `沿用批次 #${D(c).source.batch_id} 的账号名单`), 1), w("button", {
					type: "button",
					class: "bulk-link",
					"data-bulk-action": "use-query",
					disabled: U.value,
					onClick: i[3] ||= (...e) => D(s).clearFilters && D(s).clearFilters(...e)
				}, "改为按条件筛选", 8, on)])) : v("", !0),
				n(w("div", sn, [
					w("div", cn, [
						w("label", ln, [i[27] ||= w("span", { class: "bulk-sr-only" }, "邮箱或姓名", -1), w("input", {
							"data-query": "email",
							type: "search",
							value: D(c).query.filters.email,
							autocomplete: "off",
							placeholder: "搜索邮箱或姓名",
							disabled: U.value,
							onInput: i[4] ||= (e) => D(s).setQueryField("email", K(e))
						}, null, 40, un)]),
						w("details", {
							class: "bulk-filter-popover",
							"data-filter-dates": "",
							open: H.value === "date",
							onFocusout: Y
						}, [w("summary", { onClick: i[5] ||= h((e) => J("date"), ["prevent"]) }, [...i[28] ||= [m("创建日期", -1), w("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [w("path", { d: "m4 6 4 4 4-4" })], -1)]]), w("div", fn, [
							w("div", pn, [i[29] ||= w("strong", null, "创建日期", -1), w("button", {
								type: "button",
								"aria-label": "关闭创建日期筛选",
								onClick: i[6] ||= (e) => te(e)
							}, "完成")]),
							w("label", mn, [i[30] ||= m("创建日期从", -1), w("input", {
								"data-query": "date_from",
								type: "date",
								value: D(c).query.date_from,
								disabled: U.value,
								onInput: i[7] ||= (e) => D(s).setQueryField("date_from", K(e))
							}, null, 40, hn)]),
							w("label", gn, [i[31] ||= m("创建日期至（含当天）", -1), w("input", {
								"data-query": "date_to",
								type: "date",
								value: D(c).query.date_to,
								disabled: U.value,
								onInput: i[8] ||= (e) => D(s).setQueryField("date_to", K(e))
							}, null, 40, _n)])
						])], 40, dn),
						w("details", {
							class: "bulk-filter-popover",
							open: H.value === "more",
							onFocusout: Y
						}, [w("summary", { onClick: i[9] ||= h((e) => J("more"), ["prevent"]) }, [...i[32] ||= [m("更多查询", -1), w("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [w("path", { d: "m4 6 4 4 4-4" })], -1)]]), w("div", yn, [
							w("div", bn, [i[33] ||= w("strong", null, "更多查询", -1), w("button", {
								type: "button",
								"aria-label": "关闭更多查询筛选",
								onClick: i[10] ||= (e) => te(e)
							}, "完成")]),
							w("label", xn, [i[34] ||= m("高级搜索", -1), w("input", {
								"data-query": "q",
								type: "search",
								value: D(c).query.q,
								placeholder: "如：协议 jp",
								autocomplete: "off",
								disabled: U.value,
								onInput: i[11] ||= (e) => D(s).setQueryField("q", K(e))
							}, null, 40, Sn)]),
							w("label", Cn, [i[36] ||= m("归档范围", -1), w("select", {
								"data-query": "archived",
								value: D(c).query.archived,
								disabled: U.value,
								onChange: i[12] ||= (e) => D(s).setQueryField("archived", K(e))
							}, [...i[35] ||= [
								w("option", { value: "0" }, "未归档", -1),
								w("option", { value: "only" }, "仅归档", -1),
								w("option", { value: "all" }, "全部", -1)
							]], 40, wn)])
						])], 40, vn)
					]),
					w("div", Tn, [(o(!0), f(N, null, r(D(ee), (e) => (o(), f("details", {
						key: e.key,
						class: g(["bulk-filter-popover", { "has-value": e.kind === "text" ? !!D(se)(D(c).query, e.key) : !!D(oe)(D(c).query, e.key).length }]),
						"data-filter-field": e.key,
						open: H.value === e.key,
						onFocusout: Y
					}, [w("summary", { onClick: h((t) => J(e.key), ["prevent"]) }, [
						m(_(e.label), 1),
						e.kind === "enum" && D(oe)(D(c).query, e.key).length ? (o(), f("span", On, _(D(oe)(D(c).query, e.key).length), 1)) : v("", !0),
						i[37] ||= w("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [w("path", { d: "m4 6 4 4 4-4" })], -1)
					], 8, Dn), w("div", kn, [w("div", An, [w("strong", null, _(e.label), 1), w("button", {
						type: "button",
						"aria-label": `关闭${e.label}筛选`,
						onClick: i[13] ||= (e) => te(e)
					}, "完成", 8, jn)]), e.kind === "text" ? (o(), f("label", Mn, [m(_(e.label), 1), w("input", {
						"data-query-filter": e.key,
						value: D(se)(D(c).query, e.key),
						inputmode: "numeric",
						placeholder: "输入账号 ID",
						disabled: U.value,
						onInput: (t) => D(s).setQueryField(e.key, K(t))
					}, null, 40, Nn)])) : (o(), f("div", Pn, [(o(!0), f(N, null, r(D(s).filterOptions(e.key), (t) => (o(), f("label", { key: t.value }, [w("input", {
						type: "checkbox",
						"data-query-filter": e.key,
						value: t.value,
						checked: D(oe)(D(c).query, e.key).includes(t.value),
						disabled: U.value,
						onChange: (n) => q(e.key, t.value, n.target.checked)
					}, null, 40, Fn), w("span", null, _(t.label), 1)]))), 128)), D(s).filterOptions(e.key).length ? v("", !0) : (o(), f("span", In, "暂无可用选项"))]))])], 42, En))), 128))]),
					w("div", Ln, [(o(!0), f(N, null, r(D(z), (e) => (o(), f("button", {
						key: e.key,
						type: "button",
						class: "bulk-filter-chip",
						"data-clear-query": e.key,
						"aria-label": e.removeLabel,
						disabled: U.value,
						onClick: (t) => D(s).clearFilter(e.key)
					}, [m(_(e.label), 1), i[38] ||= w("span", { "aria-hidden": "true" }, "×", -1)], 8, Rn))), 128)), D(z).length ? v("", !0) : (o(), f("span", zn, "全部未归档账号"))])
				], 512), [[E, !D(c).source]])
			])
		]), w("aside", Bn, [w("div", Vn, [
			w("div", Hn, [w("div", null, [i[39] ||= w("span", { class: "bulk-side-kicker" }, "执行摘要", -1), w("strong", Un, _(D(I)), 1)])]),
			w("div", Wn, _(D(P) == null ? D(c).source ? "创建时确认" : "匹配中" : `${D(P)} 个`), 1),
			w("p", Gn, _(D(L)), 1),
			w("dl", Kn, [
				w("div", null, [i[40] ||= w("dt", null, "操作", -1), w("dd", qn, _(D(k)?.label || D(c).operation_key), 1)]),
				w("div", null, [i[41] ||= w("dt", null, "范围", -1), w("dd", Jn, _(D(F)), 1)]),
				w("div", null, [i[42] ||= w("dt", null, "本批并发", -1), w("dd", Yn, _(D(c).max_concurrency), 1)])
			]),
			D(P) != null && D(P) >= 200 ? (o(), f("p", Xn, "本批将处理 " + _(D(P)) + " 个账号。", 1)) : v("", !0),
			D(y) ? (o(), f("p", Zn, [m(_(D(y)), 1), D(C) ? (o(), f("button", {
				key: 0,
				type: "button",
				class: "bulk-link",
				onClick: i[14] ||= (e) => t.deps.callbacks.navigate("detail", { batch_id: D(C) })
			}, "查看批次 #" + _(D(C)), 1)) : v("", !0)])) : v("", !0),
			D(M) ? (o(), f("div", Qn, [w("span", null, "有 " + _(D(M)) + " 个请求未收到回执，草稿已保留。", 1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: U.value,
				onClick: i[15] ||= (...e) => D(s).recover && D(s).recover(...e)
			}, _(D(p) ? "正在找回…" : "找回原请求"), 9, $n)])) : v("", !0),
			w("div", er, [w("button", {
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				"data-bulk-submit": "",
				disabled: U.value || D(P) === 0 || !D(T).length
			}, _(D(d) ? "正在创建批次…" : "创建并执行"), 9, tr), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "create-paused",
				disabled: U.value || D(P) === 0 || !D(T).length,
				onClick: i[16] ||= (e) => D(s).createBatch(!0)
			}, _(D(d) ? "正在创建批次…" : "创建并暂停"), 9, nr)]),
			i[43] ||= w("p", { class: "bulk-side-foot" }, "提交时固定账号范围，暂停后可继续原批次", -1),
			w("button", {
				type: "button",
				class: "bulk-side-back",
				"data-bulk-action": "list",
				onClick: i[17] ||= (e) => t.deps.callbacks.navigate("list")
			}, "← 返回批次列表")
		])])], 40, Bt));
	}
}), ir = {
	plan_check: "查套餐",
	token_refresh: "刷新 AT",
	password_setup: "补密码",
	twofa_setup: "补 2FA",
	codex_retry: "补 Codex",
	account_completion: "组合补全"
}, ar = {
	pending_submit: "待提交",
	waiting_account: "等待账号",
	queued: "排队中",
	running: "执行中",
	waiting: "等待外部结果",
	success: "成功",
	partial_success: "部分成功",
	failed: "失败",
	not_executed: "未执行",
	not_executable: "材料或状态不满足",
	unassessed: "等待预检",
	cancelled: "已取消",
	preparing: "准备中",
	ready: "已固定",
	expired: "已过期",
	consumed: "已创建",
	active: "批次执行中",
	settling: "汇总中",
	completed: "已完成",
	ended: "已结束",
	paused: "已暂停",
	cancel_requested: "取消中",
	stop_requested: "停止中",
	pending: "待执行",
	confirmed: "已确认"
}, or = [
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
], sr = (e) => "is-" + (or.includes(String(e)) ? "failed" : String(e || "preparing")), Z = (e) => typeof e == "object" && e && !Array.isArray(e) ? e : {}, cr = (e) => Array.isArray(e) ? e.map(Z) : [], lr = (e) => ar[or.includes(String(e)) ? "failed" : String(e)] || String(e || "—"), ur = (e) => String(Z(e?.operation).key || e?.operation_key || e?.action_key || ""), dr = (e) => ir[String(e)] || String(e || "—"), Q = (e) => e != null && e !== "" && typeof e != "boolean" && (typeof e == "number" || typeof e == "string") && Number.isFinite(Number(e)) && Number(e) >= 0 ? Number(e) : null, $ = (e) => Q(e) === null ? "—" : Math.floor(Number(e)).toLocaleString("zh-CN");
function fr(e) {
	let t = {};
	for (let [n, r] of Object.entries(Z(e))) {
		let e = or.includes(n) ? "failed" : n;
		t[e] = (t[e] || 0) + (Q(r) || 0);
	}
	return t;
}
function pr(e) {
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
function mr(e) {
	let t = Z(e.view);
	return t.kind === "round" ? Number(t.round_no) === 1 ? "首轮名单" : Q(t.round_no) === null ? "所选轮次 · 固定名单" : `重跑 ${Number(t.round_no) - 1} · 固定名单` : "当前结果 · 每个账号取最近一轮";
}
var hr = {
	free: "Free",
	plus: "Plus",
	pro: "Pro",
	team: "Team",
	business: "Business",
	enterprise: "Enterprise",
	go: "Go",
	unknown: "尚未确认"
}, gr = {
	free_trial: "免费试用",
	half_price: "半价优惠",
	discount: "折扣优惠",
	other_discount: "其他折扣",
	other_promo: "其他优惠"
}, _r = (e) => hr[String(e)] || String(e || "尚未确认"), vr = (e) => gr[String(e)] || String(e || "其他优惠");
function yr(e, t) {
	return `${Math.max(0, Math.min(100, t > 0 ? (Q(e) || 0) / t * 100 : 0))}%`;
}
var br = (e) => X(e.canonical_target_id || e.target_id || e.id);
function xr(e) {
	return e == null || e === "" ? null : X(e);
}
function Sr(e) {
	if (e.refresh_outcome) return {
		pending: "等待本轮 AT 刷新",
		success: "本轮 AT 刷新成功",
		failed: "本轮 AT 刷新失败",
		unconfirmed: "本轮 AT 刷新失败",
		not_executed: "本轮未执行 AT 刷新"
	}[String(e.refresh_outcome)] || "本轮 AT 刷新失败";
	if (e.query_outcome) {
		if (e.query_outcome === "pending") return "等待本轮查询结果";
		if (e.query_outcome === "not_executed") return "本轮未执行";
		let t = [`查询${lr(e.query_outcome)}`];
		return e.account_plan_type && t.push(`套餐 ${e.account_plan_type}`), e.confirmed_no_offer ? t.push("本次确认无优惠") : e.plus_offer_kind && e.plus_offer_kind !== "unknown" && t.push(vr(e.plus_offer_kind)), e.comparison && e.comparison !== "not_comparable" && t.push({
			unchanged: "优惠未变化",
			new_offer: "新增优惠",
			offer_removed: "优惠消失",
			changed: "优惠变化"
		}[String(e.comparison)] || "优惠变化"), Array.isArray(e.countries_requested) && e.countries_requested.length && t.push(`国家项成功 ${$(e.country_success_count)} / ${e.countries_requested.length}`), t.join(" · ");
	}
	if (e.confirmation) return e.confirmation === "confirmed" ? "已确认 · 变更方式未记录" : e.confirmation === "not_executed" ? "未执行" : e.confirmation === "pending" ? "等待本轮设置结果" : "设置失败";
	if (e.credential_confirmation) return e.credential_confirmation === "confirmed" ? "本轮可用凭证已确认" : e.credential_confirmation === "pending" ? "等待本轮授权结果" : e.existing_asset_preserved ? "本轮授权失败 · 已有可用凭证保留" : "本轮授权失败 · 未取得有效凭证";
	if (e.required_steps) {
		let t = {
			password: "密码",
			twofa: "2FA",
			codex: "Codex",
			access_token: "AT",
			plan_check: "套餐"
		}, n = (e) => Array.isArray(e) ? e.map((e) => t[String(e)] || String(e)).join("、") : "";
		return `已完成 ${n(e.completed_steps) || "暂无"}${n(e.pending_steps) ? `；待完成 ${n(e.pending_steps)}` : ""}`;
	}
	return "";
}
function Cr(e) {
	let t = Z(e.result), n = Z(t.result || e.result_summary || t), r = Z(e.reason || t.reason || e.error || e.error_info), i = Z(e.display_snapshot || e.display), a = Z(e.execution), o = cr(e.owned_runs)[0] || {}, s = br(e), c = xr(e.account_id || i.account_id || i.id || e.entity_id) || s, l = String(i.email || e.email || `账号 #${c}`), u = String(n.summary || n.message || e.result_label || e.summary_text || Sr(n) || "等待本轮结果"), d = String(r.summary || r.cause_summary || r.label || r.message || e.reason_label || e.reason_code || r.code || ""), f = [r.summary || r.cause_summary || r.message || e.error_message || d, r.display_code || r.code || e.reason_code].filter(Boolean).join("\n"), p = String(e.stage_label || e.current_stage_label || e.stage || "").trim(), m = Object.entries(Z(n.capabilities)).map(([e, t]) => `${dr(e)}：${lr(Z(t).state || Z(t).status)}`).join("\n"), h = e.state || e.outcome || e.status;
	return {
		id: s,
		accountId: c,
		account: l,
		summary: u,
		summaryShort: wr(n, h, u),
		reason: d,
		reasonShort: d ? le({
			...r,
			code: r.code || e.reason_code
		}) === "执行异常" && [...d].length <= 10 ? d : le({
			...r,
			code: r.code || e.reason_code
		}) : "",
		reasonContent: f,
		stage: p,
		capabilities: m,
		state: lr(h),
		stateKey: h,
		taskId: xr(e.task_id || e.owned_task_id || a.task_id || o.task_id),
		runId: xr(e.owned_run_id || e.run_id || a.run_id || o.run_id),
		blockerTaskId: xr(e.blocker_task_id)
	};
}
function wr(e, t, n) {
	if ([...n].length <= 10) return n;
	if (e.refresh_outcome) return {
		success: "AT刷新成功",
		pending: "等待AT刷新",
		not_executed: "本轮未执行"
	}[String(e.refresh_outcome)] || "AT刷新失败";
	if (e.query_outcome) return {
		success: e.confirmed_no_offer ? "本次无优惠" : "套餐已查询",
		pending: "等待套餐查询",
		not_executed: "本轮未执行",
		partial_success: "部分查询失败"
	}[String(e.query_outcome)] || "套餐查询失败";
	if (e.confirmation) return {
		confirmed: "设置已确认",
		pending: "等待设置结果",
		not_executed: "本轮未执行"
	}[String(e.confirmation)] || "设置失败";
	if (e.credential_confirmation) return {
		confirmed: "凭证已确认",
		pending: "等待授权结果"
	}[String(e.credential_confirmation)] || (e.existing_asset_preserved ? "授权失败已保留" : "授权失败");
	if (Array.isArray(e.required_steps)) return "补全结果见详情";
	let r = lr(t);
	return [...r].length <= 10 && r !== "—" ? r : "结果见详情";
}
function Tr(e) {
	let t = { ...Z(e) };
	Object.hasOwn(t, "account.token_refresh.unconfirmed") && (t["account.token_refresh.failed"] = (Q(t["account.token_refresh.failed"]) || 0) + (Q(t["account.token_refresh.unconfirmed"]) || 0), delete t["account.token_refresh.unconfirmed"]);
	let n = {
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
		...gr
	})) n[`account.plus_offer.${e}`] = `优惠 · ${t}`;
	for (let [e, t] of Object.entries({
		unchanged: "优惠未变化",
		new_offer: "新增优惠",
		offer_removed: "优惠消失",
		changed: "优惠变化",
		not_comparable: "历史条件不可比较"
	})) n[`account.comparison.${e}`] = t;
	for (let [e, t] of Object.entries({
		password: "密码",
		twofa: "2FA",
		codex: "Codex",
		access_token: "AT",
		plan_check: "套餐"
	})) n[`step.${e}.confirmed`] = `${t} · 已完成`, n[`step.${e}.pending`] = `${t} · 待完成`;
	let r = /* @__PURE__ */ new Map();
	function i(e, t = "", a = 0) {
		if (!(a > 3)) for (let [o, s] of Object.entries(e)) {
			if ([
				"schema",
				"schema_version",
				"version",
				"updated_at"
			].includes(o)) continue;
			let e = t ? `${t} · ${n[o] || o}` : n[o] || o;
			if (typeof s == "number" || s === null) {
				let t = o.startsWith("country_query.") || o.startsWith("country_") ? "国家查询项" : o.startsWith("account.plan.") ? "套餐分布" : o.startsWith("account.plus_offer.") || o.startsWith("account.comparison.") || o === "account.confirmed_no_offer" ? "优惠结果" : o.startsWith("step.") ? "补全项目" : "执行结果";
				r.has(t) || r.set(t, {
					title: t,
					items: []
				}), r.get(t).items.push({
					title: e,
					value: s,
					unit: t === "国家查询项" ? "项" : "个"
				});
			} else s && typeof s == "object" && i(Z(s), e, a + 1);
		}
	}
	return i(t), [...r.values()];
}
// src/features/bulk/useBulkDetail.ts
var Er = [
	"failed",
	"partial_success",
	"not_executed",
	"cancelled"
];
function Dr(t, n, r = t().view === "detail") {
	let i = e({ ...t() }), a = e(r), o = M(null), s = M(null), c = M(null), u = M([]), f = e(null), p = e(/* @__PURE__ */ new Set()), m = e([]), h = e(null), g = e(!1), _ = e(!1), v = e(!1), y = e(!1), b = e(!1), x = e(""), S = e(""), C = e(""), w = e(""), T = M(null), E = !1, D = 0, k = !1, A = null, j = "", N = /* @__PURE__ */ new Map(), P = () => `${i.value.batch_id || ""}:${i.value.round_id || ""}`, F = () => `${P()}:${i.value.result_state || ""}`, I = () => `${F()}:${i.value.cursor || ""}`;
	function L(e) {
		let t = N.get(e);
		t?.controller.abort();
		let n = {
			generation: (t?.generation || 0) + 1,
			controller: new AbortController()
		};
		return N.set(e, n), n;
	}
	function R(e, t) {
		return !E && N.get(e) === t && !t.controller.signal.aborted;
	}
	function z(...e) {
		for (let t of e) N.get(t)?.controller.abort(), N.delete(t);
		e.includes("detail") && (A = null, j = "");
	}
	function B() {
		let e = new URLSearchParams({ view: i.value.round_id ? "round" : "current" });
		return i.value.round_id && e.set("round_id", X(i.value.round_id)), e;
	}
	function V(e = "") {
		return `/batches/${X(i.value.batch_id)}${e}`;
	}
	function H(e) {
		return e instanceof Error ? e.message : String(e);
	}
	function U(e) {
		let t = new Map(u.value.map((e) => [X(e.id), e]));
		if (Array.isArray(e)) for (let n of e) {
			let e = Z(n);
			t.set(X(e.id), e);
		}
		u.value = [...t.values()].sort((e, t) => Number(t.round_no) - Number(e.round_no));
	}
	let ee = O(() => fr(o.value?.summary || o.value?.counts)), W = O(() => Z(o.value?.control)), G = O(() => ["ended", "completed"].includes(String(W.value.state || o.value?.control_state))), K = O(() => !!(W.value.paused || o.value?.is_paused)), q = O(() => m.value.length > 0), te = O(() => s.value?.page?.has_more && s.value.page.next_cursor || null), J = O(() => a.value && i.value.view === "detail" && (!G.value || !!h.value || !!W.value.pending)), Y = O(() => Object.hasOwn(ir, ur(o.value)));
	function ne(e) {
		return !o.value || b.value || T.value || G.value || W.value.pending ? !0 : e === "pause" ? K.value : e === "resume" ? !K.value : Z(o.value.capabilities || Z(o.value.operation).capabilities)[e] === !1;
	}
	async function re() {
		if (!a.value || i.value.view !== "detail") return;
		let e = L("targets");
		_.value = !0, S.value = "";
		try {
			let t = B();
			t.set("page_size", "50"), i.value.cursor && t.set("cursor", i.value.cursor), i.value.result_state && t.set("state[]", i.value.result_state);
			let r = await n.api.request(`${V("/targets")}?${t}`, { signal: e.controller.signal });
			if (R("targets", e)) {
				for (let e of r.items) br(e);
				s.value = r;
			}
		} catch (t) {
			R("targets", e) && (S.value = H(t));
		} finally {
			R("targets", e) && (_.value = !1);
		}
	}
	async function ie(e = !1) {
		if (!a.value || i.value.view !== "detail" || !Y.value || v.value) return;
		let t = G.value || Z(o.value?.selected_round).state === "completed", r = t && c.value?.phase === "completed" && c.value.summary_revision === o.value?.summary_revision;
		if (!e && (t && r || !t && (c.value || C.value) && n.now() - D < 1e4)) return;
		let s = L("report");
		v.value = !0, D = n.now();
		try {
			let e = await n.api.request(`${V("/report")}?${B()}`, { signal: s.controller.signal });
			R("report", s) && (c.value = e, C.value = "", D = n.now());
		} catch (e) {
			R("report", s) && (C.value = H(e));
		} finally {
			R("report", s) && (v.value = !1);
		}
	}
	function ae(e = !1) {
		if (E || !a.value || i.value.view !== "detail" || !i.value.batch_id) return Promise.resolve();
		if (A && j === P()) return A;
		j = P();
		let t = oe(e).finally(() => {
			A === t && (A = null, j = "");
		});
		return A = t, t;
	}
	async function oe(e = !1) {
		if (E || !a.value || i.value.view !== "detail" || !i.value.batch_id) return;
		let t = L("detail");
		g.value = !0, x.value = "";
		try {
			let r = await n.api.request(`${V()}?${B()}`, { signal: t.controller.signal });
			if (!R("detail", t)) return;
			let i = o.value?.summary_revision;
			if (o.value = r, U(r.rounds_head), r.selected_round && U([r.selected_round]), k || (f.value = typeof r.rounds_next_cursor == "string" ? r.rounds_next_cursor : null), h.value) {
				let e = u.value.find((e) => e.id === h.value);
				e && e.state !== "preparing" && (h.value = null, n.callbacks.notify(e.completion_reason === "cancelled_before_freeze" ? "重跑准备已取消，当前结果归属不变。" : "重跑名单已固定，可以切换查看新轮次。"));
			}
			let a = [ie(e)];
			(e || !s.value || i !== r.summary_revision) && a.push(re()), await Promise.all(a);
		} catch (e) {
			R("detail", t) && (x.value = H(e));
		} finally {
			R("detail", t) && (g.value = !1);
		}
	}
	async function se() {
		if (!a.value || i.value.view !== "detail" || !f.value || y.value) return;
		let e = L("rounds");
		y.value = !0;
		try {
			let t = new URLSearchParams({
				page_size: "20",
				cursor: f.value
			}), r = await n.api.request(`${V("/rounds")}?${t}`, { signal: e.controller.signal });
			R("rounds", e) && (U(r.items), f.value = r.page.has_more && r.page.next_cursor || null, k = !0);
		} catch (t) {
			R("rounds", e) && (w.value = H(t));
		} finally {
			R("rounds", e) && (y.value = !1);
		}
	}
	function ce(e, t = !1) {
		t || (m.value = []), i.value = {
			...i.value,
			...e
		}, n.callbacks.updateNavigation(e);
	}
	async function le() {
		te.value && !_.value && (m.value.push(i.value.cursor || ""), ce({ cursor: te.value }, !0));
	}
	async function ue() {
		q.value && !_.value && ce({ cursor: m.value.pop() || "" }, !0);
	}
	async function de() {
		ce({ cursor: "" });
	}
	async function fe(e) {
		ce({
			result_state: e,
			cursor: ""
		});
	}
	async function pe(e) {
		ce({
			round_id: e === "current" ? "" : X(e),
			cursor: ""
		});
	}
	function me(e, t) {
		let n = new Set(p.value);
		t ? n.add(X(e)) : n.delete(e), p.value = n;
	}
	function he(e) {
		for (let t of s.value?.items || []) me(br(t), e);
	}
	function ge() {
		p.value = /* @__PURE__ */ new Set();
	}
	function _e(e) {
		return (e === "unsuccessful" ? Er : [e]).reduce((e, t) => e + (ee.value[t] || 0), 0);
	}
	function ve() {
		T.value = null;
	}
	async function ye(e) {
		if (!(b.value || E || !a.value || i.value.view !== "detail" || e.navigationKey !== I())) {
			b.value = !0, w.value = "", T.value = null;
			try {
				let t = await n.intents.submit(e.intentScope, e.path, e.body);
				if (n.callbacks.notify(e.kind === "retry" ? "重跑已受理，正在按固定时点的结果准备新轮次。" : "控制请求已受理，正在读取批次最新状态。"), E || e.navigationKey !== I()) return;
				e.kind === "retry" && (h.value = X(t.round_id || t.id), ge()), await ae(!0);
			} catch (t) {
				if (!E && e.navigationKey === I()) {
					w.value = H(t);
					let e = Z(t).code;
					["control_revision_conflict", "control_revision_changed"].includes(String(e)) && await ae(!0);
				}
			} finally {
				b.value = !1;
			}
		}
	}
	async function be() {
		let e = T.value;
		e && await ye(e);
	}
	async function xe(e = !1, t = "failed") {
		if (!o.value || b.value || T.value || !Er.includes(t) && t !== "unsuccessful") return;
		let n = [...p.value], r = e ? n.length : _e(t);
		if (!r) return;
		let a = X(i.value.batch_id), s = i.value.round_id ? X(i.value.round_id) : null, c = {
			title: "确认重跑",
			description: `将在当前批次下新建一轮，重跑 ${r} 个账号；不会覆盖历史轮次。`,
			label: `重跑 ${r} 个`,
			count: r,
			scopeLabel: s ? "当前轮" : "当前结果",
			path: `/batches/${a}/rounds`,
			intentScope: `retry:${a}`,
			navigationKey: I(),
			kind: "retry",
			body: {
				source: {
					view: s ? "round" : "current",
					round_id: s,
					observed_summary_revision: o.value.summary_revision,
					observed_target_count: r
				},
				selection: e ? {
					kind: "targets",
					target_ids: n
				} : {
					kind: "result_filter",
					states: t === "unsuccessful" ? [...Er] : [t]
				},
				retry_mode: "automatic"
			}
		};
		r >= 10 || t === "unsuccessful" ? T.value = c : await ye(c);
	}
	async function Se(e) {
		if (![
			"pause",
			"resume",
			"cancel_not_started",
			"request_stop"
		].includes(e) || ne(e)) return;
		let t = ["pause", "resume"].includes(e), n = e === "request_stop", r = X(i.value.batch_id), a = i.value.round_id ? X(i.value.round_id) : null, s = (n ? ["running", "waiting"] : [
			"pending_submit",
			"waiting_account",
			"queued",
			"waiting"
		]).reduce((e, t) => e + (ee.value[t] || 0), 0), c = {
			title: n ? "停止正在执行" : "取消排队账号",
			description: n ? "已开始执行的账号会收到协作停止请求，正在收尾的步骤会完成，不会立即强制中断。" : "尚未开始的目标会取消；已开始账号链的必要步骤会继续收尾。",
			label: n ? "停止执行" : "取消排队",
			count: s,
			scopeLabel: !t && a ? "当前轮" : "整个批次",
			path: `/batches/${r}/control`,
			intentScope: `control:${r}:${e}`,
			navigationKey: I(),
			kind: "control",
			body: {
				action: e,
				expected_control_revision: W.value.revision ?? o.value?.control_revision,
				scope: !t && a ? {
					kind: "round",
					round_id: a
				} : { kind: "batch" }
			}
		};
		t ? await ye(c) : T.value = c;
	}
	function Ce(e) {
		if (!o.value) return;
		let t = Z(o.value.selection_summary).query || o.value.query_spec || Z(o.value.selection).query_spec;
		(e || t) && n.callbacks.copyBatch?.(t || {}, e ? {
			kind: "batch_targets",
			batch_id: X(i.value.batch_id),
			selection: { kind: "all" }
		} : null, ur(o.value));
	}
	function we(e) {
		a.value = e, e || (z("detail", "targets", "report", "rounds"), g.value = !1, _.value = !1, v.value = !1, y.value = !1, T.value = null);
	}
	return l(t, (e) => {
		JSON.stringify(e) !== JSON.stringify(i.value) && (m.value = [], i.value = { ...e });
	}, {
		deep: !0,
		flush: "sync"
	}), l(() => i.value.view, (e) => {
		e !== "detail" && we(!1);
	}, { flush: "sync" }), l(() => [
		P(),
		F(),
		i.value.cursor || ""
	], (e, t) => {
		T.value = null, w.value = "", !t || e[0] !== t[0] ? (z("detail", "targets", "report", "rounds"), o.value = null, s.value = null, c.value = null, u.value = [], f.value = null, k = !1, D = 0, C.value = "", S.value = "", g.value = !1, _.value = !1, v.value = !1, y.value = !1, ge(), m.value = [], h.value = null, ae()) : (e[1] !== t[1] && (ge(), m.value = []), s.value = null, re());
	}, {
		immediate: !0,
		flush: "sync"
	}), d(() => {
		E = !0, z("detail", "targets", "report", "rounds"), T.value = null;
	}), {
		navigation: i,
		detail: o,
		targets: s,
		report: c,
		rounds: u,
		roundsCursor: f,
		selected: p,
		pendingRound: h,
		loading: g,
		targetsLoading: _,
		reportLoading: v,
		roundsLoading: y,
		writing: b,
		error: x,
		targetError: S,
		reportError: C,
		actionError: w,
		confirmation: T,
		counts: ee,
		ended: G,
		paused: K,
		needsPolling: J,
		hasReport: Y,
		hasPrevious: q,
		nextCursor: te,
		controlDisabled: ne,
		refresh: ae,
		loadTargets: re,
		refreshReport: ie,
		moreRounds: se,
		next: le,
		previous: ue,
		first: de,
		setFilter: fe,
		setRound: pe,
		toggleTarget: me,
		selectPage: he,
		clearSelection: ge,
		retryCount: _e,
		retry: xe,
		control: Se,
		confirm: be,
		cancelConfirmation: ve,
		copyBatch: Ce,
		setVisible: we
	};
}
// src/features/bulk/BulkBusinessStats.vue?vue&type=script&setup=true&lang.ts
var Or = {
	key: 0,
	class: "bulk-business-groups"
}, kr = { class: "bulk-business-metrics" }, Ar = {
	key: 1,
	class: "bulk-report-empty"
}, jr = /* @__PURE__ */ c({
	__name: "BulkBusinessStats",
	props: { metrics: {} },
	setup(e) {
		let t = e, n = O(() => Tr(t.metrics));
		return (e, t) => n.value.length ? (o(), f("div", Or, [(o(!0), f(N, null, r(n.value, (e) => (o(), f("section", {
			key: e.title,
			class: "bulk-business-group"
		}, [w("h4", null, _(e.title) + " · " + _(e.title === "国家查询项" ? "项" : "账号数"), 1), w("dl", kr, [(o(!0), f(N, null, r(e.items, (e) => (o(), f("div", { key: e.title }, [w("dt", null, _(e.title), 1), w("dd", null, _(D($)(e.value)), 1)]))), 128))])]))), 128))])) : (o(), f("p", Ar, "暂无已确认的功能统计。"));
	}
}), Mr = ["aria-label"], Nr = { role: "status" }, Pr = {
	key: 1,
	class: "bulk-plan-report",
	"aria-label": "批次执行报告"
}, Fr = { class: "bulk-report-header" }, Ir = { class: "bulk-report-heading-line" }, Lr = { class: "bulk-report-updated" }, Rr = {
	key: 0,
	class: "bulk-report-sync",
	role: "status"
}, zr = { class: "bulk-report-outcomes" }, Br = { class: "bulk-report-outcome-note" }, Vr = { class: "bulk-report-execution" }, Hr = { "aria-label": "账号执行耗时" }, Ur = { class: "bulk-report-section-head" }, Wr = { class: "bulk-report-durations" }, Gr = { class: "is-average" }, Kr = { class: "bulk-report-note" }, qr = {
	key: 0,
	"aria-label": "AT 检查与自动刷新"
}, Jr = { class: "bulk-report-at-causes" }, Yr = { class: "bulk-report-at-results" }, Xr = { class: "bulk-report-note" }, Zr = {
	key: 1,
	"aria-label": "功能统计"
}, Qr = {
	key: 1,
	class: "bulk-report-distributions"
}, $r = {
	class: "bulk-report-offers",
	"aria-label": "优惠结果"
}, ei = { class: "bulk-report-offer-totals" }, ti = { class: "bulk-report-offer-list" }, ni = { class: "bulk-report-offer-line" }, ri = {
	class: "bulk-report-rail",
	"aria-hidden": "true"
}, ii = { class: "bulk-report-kind-list" }, ai = {
	key: 0,
	class: "bulk-report-empty"
}, oi = {
	class: "bulk-report-plans",
	"aria-label": "当前订阅套餐"
}, si = { class: "bulk-report-plan-list" }, ci = {
	key: 0,
	class: "bulk-report-empty"
}, li = {
	key: 2,
	class: "bulk-business-details"
}, ui = /* @__PURE__ */ c({
	__name: "BulkReport",
	props: {
		report: {},
		formatDateTime: { type: Function }
	},
	setup(e) {
		let t = e, n = O(() => Object.hasOwn(ir, String(t.report.operation_key))), i = O(() => Z(t.report.totals)), a = O(() => Z(t.report.duration)), s = O(() => Z(t.report.at_refresh)), c = O(() => Z(t.report.offers)), l = O(() => t.report.phase === "completed"), u = O(() => t.report.operation_key === "plan_check"), d = O(() => cr(t.report.plans).sort((e, t) => e.plan === "unknown" ? 1 : t.plan === "unknown" ? -1 : (Q(t.accounts) || 0) - (Q(e.accounts) || 0))), p = O(() => cr(c.value.by_plan).sort((e, t) => (Q(t.accounts) || 0) - (Q(e.accounts) || 0) || _r(e.plan).localeCompare(_r(t.plan)))), h = O(() => Math.max(0, ...d.value.map((e) => Q(e.accounts) || 0))), y = O(() => Math.max(0, ...p.value.map((e) => Q(e.accounts) || 0))), b = [
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
		], x = [
			["AT 过期", "expired_accounts"],
			["远端拒绝 AT", "invalid_accounts"],
			["缺少 AT", "missing_token_accounts"]
		], S = [
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
		], C = [
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
		return (t, T) => n.value && e.report.population_ready === !1 ? (o(), f("section", {
			key: 0,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": D(dr)(e.report.operation_key) + "报告"
		}, [w("h3", null, _(D(dr)(e.report.operation_key)) + "报告", 1), w("p", Nr, _(D(mr)(e.report)) + " · " + _(e.report.phase === "preparing" ? "账号名单准备中，固定后生成报告。" : "该轮名单未固定，无法生成账号统计。"), 1)], 8, Mr)) : n.value ? (o(), f("section", Pr, [
			w("header", Fr, [w("div", null, [w("div", Ir, [w("h3", null, _(D(dr)(e.report.operation_key)) + _(l.value ? "完成报告" : "实时报告"), 1), w("span", { class: g(["bulk-report-phase", { "is-completed": l.value }]) }, _(l.value ? "已完成" : e.report.phase === "preparing" ? "名单准备中" : "统计更新中"), 3)]), w("p", null, _(D(mr)(e.report)) + " · " + _(D($)(i.value.accounts)) + " 个账号", 1)]), w("span", Lr, "更新于 " + _(e.formatDateTime(e.report.generated_at)), 1)]),
			D(Z)(e.report.projection).state && D(Z)(e.report.projection).state !== "current" ? (o(), f("p", Rr, _(D(Z)(e.report.projection).state === "failed" ? "结果汇总暂时失败，以下统计尚未收齐，请稍后刷新。" : "执行结果正在汇总，以下统计尚未收齐。"), 1)) : v("", !0),
			w("dl", zr, [(o(), f(N, null, r(b, ([e, t, n]) => w("div", {
				key: t,
				class: g(["bulk-report-metric", n])
			}, [w("dt", null, _(e), 1), w("dd", null, [m(_(D($)(i.value[t])), 1), T[0] ||= w("span", null, "个", -1)])], 2)), 64))]),
			w("div", Br, [
				w("span", null, "已结束 " + _(D($)(i.value.completed)) + " / " + _(D($)(i.value.accounts)) + " 个", 1),
				w("span", null, "未执行 " + _(D($)(i.value.not_executed)) + " 个", 1),
				w("span", null, "已取消 " + _(D($)(i.value.cancelled)) + " 个", 1)
			]),
			w("div", Vr, [w("section", Hr, [
				w("div", Ur, [T[1] ||= w("h4", null, "账号执行耗时", -1), w("span", null, "已结束样本 " + _(D($)(a.value.sample_count)) + " 个", 1)]),
				w("dl", Wr, [
					w("div", Gr, [T[2] ||= w("dt", null, "平均耗时", -1), w("dd", null, _(D(pr)(a.value.avg_seconds)), 1)]),
					w("div", null, [T[3] ||= w("dt", null, "最快", -1), w("dd", null, _(D(pr)(a.value.min_seconds)), 1)]),
					w("div", null, [T[4] ||= w("dt", null, "最慢", -1), w("dd", null, _(D(pr)(a.value.max_seconds)), 1)])
				]),
				w("p", Kr, [m("从账号开始执行到结束，" + _(u.value ? "含自动刷新及链内等待" : "含链内等待") + "，不含开始前排队。", 1), (D(Q)(a.value.missing_count) || 0) > 0 ? (o(), f(N, { key: 0 }, [m(_(D($)(a.value.missing_count)) + " 个已结束账号缺少有效耗时，未计入均值。", 1)], 64)) : D(Q)(a.value.sample_count) === 0 ? (o(), f(N, { key: 1 }, [m(" 暂无有效耗时样本。")], 64)) : v("", !0)])
			]), u.value ? (o(), f("section", qr, [
				T[8] ||= w("div", { class: "bulk-report-section-head" }, [w("h4", null, "AT 检查与自动刷新"), w("span", null, "按账号去重")], -1),
				w("dl", Jr, [(o(), f(N, null, r(x, ([e, t]) => w("div", {
					key: t,
					class: "bulk-report-minor"
				}, [w("dt", null, _(e), 1), w("dd", null, [m(_(D($)(s.value[t])), 1), T[5] ||= w("span", null, "个", -1)])])), 64))]),
				w("dl", Yr, [(o(), f(N, null, r(S, ([e, t, n]) => w("div", {
					key: t,
					class: g(["bulk-report-minor", n])
				}, [w("dt", null, _(e), 1), w("dd", null, [m(_(D($)(s.value[t])), 1), T[6] ||= w("span", null, "个", -1)])], 2)), 64))]),
				w("p", Xr, [
					D(Q)(s.value.not_needed_accounts) === null ? v("", !0) : (o(), f(N, { key: 0 }, [m("未触发刷新 " + _(D($)(s.value.not_needed_accounts)) + " 个 · ", 1)], 64)),
					m("刷新状态待确认 " + _(D($)(s.value.unknown_accounts)) + " 个", 1),
					D(Q)(s.value.not_executed_accounts) === null ? v("", !0) : (o(), f(N, { key: 1 }, [m(" · 未开始执行 " + _(D($)(s.value.not_executed_accounts)) + " 个", 1)], 64)),
					T[7] ||= m("。待确认含执行中尚无结果及历史证据缺失；触发原因可能重叠，远端拒绝不等于本地过期。", -1)
				])
			])) : (o(), f("section", Zr, [T[9] ||= w("div", { class: "bulk-report-section-head" }, [w("h4", null, "功能统计"), w("span", null, "当前查看范围")], -1), I(jr, { metrics: e.report.business_summary }, null, 8, ["metrics"])]))]),
			u.value ? (o(), f("div", Qr, [w("section", $r, [
				T[13] ||= w("div", { class: "bulk-report-section-head" }, [w("div", null, [w("h4", null, "优惠结果"), w("p", null, "统计本次查到的可用优惠，按账号去重")])], -1),
				w("dl", ei, [(o(), f(N, null, r(C, ([e, t, n]) => w("div", {
					key: t,
					class: g(["bulk-report-metric", { "is-accent": t === "with_offer_accounts" }])
				}, [
					w("dt", null, _(e), 1),
					w("dd", null, [m(_(D($)(c.value[t])), 1), T[10] ||= w("span", null, "个", -1)]),
					w("small", null, _(n), 1)
				], 2)), 64))]),
				w("div", ti, [(o(!0), f(N, null, r(p.value, (e) => (o(), f("div", {
					key: String(e.plan),
					class: "bulk-report-offer-row"
				}, [
					w("div", ni, [w("strong", null, _(D(_r)(e.plan)), 1), w("span", null, [w("b", null, _(D($)(e.accounts)), 1), T[11] ||= m(" 个账号", -1)])]),
					w("span", ri, [w("span", { style: P({ width: D(yr)(e.accounts, y.value) }) }, null, 4)]),
					w("dl", ii, [(o(!0), f(N, null, r(D(cr)(e.kinds), (e) => (o(), f("div", { key: String(e.kind) }, [w("dt", null, _(D(vr)(e.kind)), 1), w("dd", null, [m(_(D($)(e.accounts)), 1), T[12] ||= w("span", null, "个", -1)])]))), 128))])
				]))), 128)), p.value.length ? v("", !0) : (o(), f("p", ai, _(D(Q)(c.value.with_offer_accounts) === 0 ? "本次尚未查到可用优惠。" : "暂无优惠套餐明细。"), 1))]),
				T[14] ||= w("p", { class: "bulk-report-note" }, "同一账号可符合多个套餐或优惠，分项数量可能重叠。", -1)
			]), w("section", oi, [
				T[16] ||= w("div", { class: "bulk-report-section-head" }, [w("div", null, [w("h4", null, "当前订阅套餐"), w("p", null, "本次查询确认的套餐状态")])], -1),
				w("dl", si, [(o(!0), f(N, null, r(d.value, (e) => (o(), f("div", {
					key: String(e.plan),
					class: g({ "is-unknown": e.plan === "unknown" })
				}, [w("dt", null, _(D(_r)(e.plan)), 1), w("dd", null, [w("span", null, [m(_(D($)(e.accounts)), 1), T[15] ||= w("small", null, "个", -1)]), w("span", {
					class: g(["bulk-report-rail", { "is-muted": e.plan === "unknown" }]),
					"aria-hidden": "true"
				}, [w("span", { style: P({ width: D(yr)(e.accounts, h.value) }) }, null, 4)], 2)])], 2))), 128)), d.value.length ? v("", !0) : (o(), f("div", ci, "暂无套餐结果。"))]),
				T[17] ||= w("p", { class: "bulk-report-note" }, "“尚未确认”包含待完成、失败或缺少套餐记录的账号。", -1)
			])])) : v("", !0),
			u.value && Object.keys(D(Z)(e.report.business_summary)).length ? (o(), f("details", li, [T[18] ||= w("summary", null, [m("更多查询统计"), w("span", null, "展开查看")], -1), I(jr, { metrics: e.report.business_summary }, null, 8, ["metrics"])])) : v("", !0)
		])) : v("", !0);
	}
}), di = ["aria-busy"], fi = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, pi = {
	class: "bulk-target-scroll",
	role: "region",
	"aria-label": "账号明细内容",
	tabindex: "0"
}, mi = { class: "bulk-table bulk-target-table" }, hi = [
	"disabled",
	"checked",
	"indeterminate"
], gi = { class: "bulk-target-filter" }, _i = ["checked"], vi = [
	"value",
	"checked",
	"onChange"
], yi = ["data-bulk-row-target"], bi = {
	class: "bulk-target-check",
	"data-label": "选择"
}, xi = [
	"data-bulk-target",
	"aria-label",
	"checked",
	"onChange"
], Si = {
	class: "bulk-target-id",
	"data-label": "ID"
}, Ci = ["aria-label", "onClick"], wi = {
	class: "bulk-target-account",
	"data-label": "账号"
}, Ti = ["title", "onClick"], Ei = {
	class: "bulk-target-state",
	"data-label": "结果 / 阶段"
}, Di = { class: "bulk-target-status-line" }, Oi = ["onClick"], ki = {
	class: "bulk-target-summary",
	"data-label": "结果摘要"
}, Ai = [
	"title",
	"aria-label",
	"onClick"
], ji = {
	class: "bulk-target-reason",
	"data-label": "错误分类"
}, Mi = ["title", "onClick"], Ni = {
	class: "bulk-target-actions",
	"data-label": "操作"
}, Pi = { class: "bulk-target-action-line" }, Fi = ["onClick"], Ii = { key: 1 }, Li = ["onClick"], Ri = { key: 0 }, zi = { colspan: "7" }, Bi = {
	class: "bulk-empty",
	role: "status"
}, Vi = {
	key: 0,
	class: "bulk-vue-result-details"
}, Hi = /* @__PURE__ */ c({
	__name: "BulkTargets",
	props: {
		items: {},
		selected: {},
		loading: { type: Boolean },
		error: {},
		scope: {},
		resultState: { default: "" },
		resultCounts: { default: () => ({}) },
		resultTotal: {},
		resultStates: { default: () => [] },
		openTask: {}
	},
	emits: [
		"toggle",
		"selectPage",
		"retry",
		"filter"
	],
	setup(n, { expose: i, emit: a }) {
		let s = n, c = a, d = e(null), p = M(s.items), h = O(() => p.value.map(Cr)), b = O(() => h.value.filter((e) => s.selected.has(e.id)).length), S = e(!1), C = O(() => [.../* @__PURE__ */ new Set([...s.resultStates, ...s.resultState ? [s.resultState] : []])]);
		function T(e) {
			S.value = !1, c("filter", e);
		}
		function E() {
			let e = window.getSelection();
			return !!(e?.toString() && e.anchorNode && d.value?.contains(e.anchorNode));
		}
		function k() {
			E() || (p.value = s.items);
		}
		l(() => s.items, (e) => {
			E() && e.length || (p.value = e);
		}), l(() => s.scope, () => {
			p.value = s.items;
		}), x(() => document.addEventListener("selectionchange", k)), t(() => document.removeEventListener("selectionchange", k));
		let A = e(!1), j = M(null), P = null;
		function F(e, t) {
			j.value = { ...e }, P = t.currentTarget, A.value = !0;
		}
		function L(e) {
			e.preventDefault();
			let t = P;
			if (P = null, !t?.isConnected || t.hasAttribute("disabled") || t.closest("[hidden],[inert]")) return;
			let n = t;
			for (; n;) {
				if (getComputedStyle(n).display === "none" || getComputedStyle(n).visibility === "hidden") return;
				n = n.parentElement;
			}
			t.focus({ preventScroll: !0 });
		}
		function R() {
			A.value = !1, S.value = !1;
		}
		function z(e) {
			return e.target.checked;
		}
		function B(e, t = null) {
			s.openTask(e, t);
		}
		return i({ close: R }), (e, t) => (o(), f(N, null, [w("div", {
			ref_key: "host",
			ref: d,
			class: "bulk-targets",
			"aria-busy": n.loading
		}, [n.error ? (o(), f("div", fi, [m(_(n.error) + " ", 1), w("button", {
			type: "button",
			class: "bulk-link",
			onClick: t[0] ||= (e) => c("retry")
		}, "重试读取明细")])) : v("", !0), w("div", pi, [w("table", mi, [w("thead", null, [w("tr", null, [
			w("th", null, [w("input", {
				type: "checkbox",
				"data-select-page": "",
				"aria-label": "选择当前页目标",
				disabled: !h.value.length,
				checked: h.value.length > 0 && b.value === h.value.length,
				indeterminate: b.value > 0 && b.value < h.value.length,
				onChange: t[1] ||= (e) => c("selectPage", z(e))
			}, null, 40, hi)]),
			t[7] ||= w("th", null, "ID", -1),
			t[8] ||= w("th", null, "账号", -1),
			w("th", null, [n.resultStates.length ? (o(), y(q, {
				key: 0,
				label: "结果状态",
				"trigger-label": "结果 / 阶段",
				active: !!n.resultState,
				summary: D(lr)(n.resultState),
				open: S.value,
				"onUpdate:open": t[3] ||= (e) => S.value = e
			}, {
				default: u(() => [w("fieldset", gi, [
					t[6] ||= w("legend", { class: "bulk-sr-only" }, "结果状态", -1),
					w("label", null, [
						w("input", {
							type: "radio",
							name: "bulk-target-state",
							value: "",
							checked: !n.resultState,
							onChange: t[2] ||= (e) => T("")
						}, null, 40, _i),
						t[5] ||= w("span", null, "全部", -1),
						w("strong", null, _(D($)(n.resultTotal)), 1)
					]),
					(o(!0), f(N, null, r(C.value, (e) => (o(), f("label", { key: e }, [
						w("input", {
							type: "radio",
							name: "bulk-target-state",
							value: e,
							checked: n.resultState === e,
							onChange: (t) => T(e)
						}, null, 40, vi),
						w("span", null, _(D(lr)(e)), 1),
						w("strong", null, _(n.resultCounts[e] || 0), 1)
					]))), 128))
				])]),
				_: 1
			}, 8, [
				"active",
				"summary",
				"open"
			])) : (o(), f(N, { key: 1 }, [m("结果 / 阶段")], 64))]),
			t[9] ||= w("th", null, "结果摘要", -1),
			t[10] ||= w("th", null, "错误分类", -1),
			t[11] ||= w("th", null, "操作", -1)
		])]), w("tbody", null, [(o(!0), f(N, null, r(h.value, (e) => (o(), f("tr", {
			key: e.id,
			"data-bulk-row-target": e.id
		}, [
			w("td", bi, [w("input", {
				type: "checkbox",
				"data-bulk-target": e.id,
				"aria-label": "选择账号 " + e.account,
				checked: n.selected.has(e.id),
				onChange: (t) => c("toggle", e.id, z(t))
			}, null, 40, xi)]),
			w("td", Si, [w("button", {
				type: "button",
				class: "bulk-cell-detail",
				"aria-label": "查看完整账号 ID：" + e.accountId,
				onClick: (t) => F(e, t)
			}, "#" + _(e.accountId), 9, Ci)]),
			w("td", wi, [w("button", {
				type: "button",
				class: "bulk-cell-detail",
				title: e.account,
				onClick: (t) => F(e, t)
			}, _(e.account), 9, Ti)]),
			w("td", Ei, [w("div", Di, [w("span", { class: g(["bulk-badge", D(sr)(e.stateKey)]) }, _(e.state), 3), e.stage && !["—", "-"].includes(e.stage) ? (o(), f("button", {
				key: 0,
				type: "button",
				class: "bulk-cell-detail bulk-target-stage",
				onClick: (t) => F(e, t)
			}, _(e.stage), 9, Oi)) : v("", !0)])]),
			w("td", ki, [I(G, {
				text: e.summaryShort,
				title: e.summary
			}, {
				default: u(() => [w("button", {
					type: "button",
					class: "bulk-cell-detail",
					"data-result-detail": "",
					title: e.summary,
					"aria-label": "查看完整结果摘要：" + e.summary,
					onClick: (t) => F(e, t)
				}, _(e.summaryShort), 9, Ai)]),
				_: 2
			}, 1032, ["text", "title"])]),
			w("td", ji, [e.reason ? (o(), y(G, {
				key: 0,
				text: e.reasonShort,
				title: e.reason
			}, {
				default: u(() => [w("button", {
					type: "button",
					class: "bulk-cell-detail",
					title: e.reason,
					onClick: (t) => F(e, t)
				}, _(e.reasonShort), 9, Mi)]),
				_: 2
			}, 1032, ["text", "title"])) : (o(), f(N, { key: 1 }, [m("—")], 64))]),
			w("td", Ni, [w("div", Pi, [e.taskId ? (o(), f("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-owned-task": "",
				onClick: (t) => B(e.taskId, e.runId)
			}, "查看执行", 8, Fi)) : (o(), f("span", Ii, "尚未创建执行")), e.blockerTaskId ? (o(), f("button", {
				key: 2,
				type: "button",
				class: "bulk-link",
				"data-blocker-task": "",
				title: "查看占用任务（其他执行）",
				onClick: (t) => B(e.blockerTaskId)
			}, "查看占用", 8, Li)) : v("", !0)])])
		], 8, yi))), 128)), h.value.length ? v("", !0) : (o(), f("tr", Ri, [w("td", zi, [w("div", Bi, _(n.loading ? "正在读取账号明细…" : "当前条件下没有目标。更改结果筛选不会改变本批固定名单。"), 1)])]))])])])], 8, di), I(D(fe), {
			open: A.value,
			"onUpdate:open": t[4] ||= (e) => A.value = e
		}, {
			default: u(() => [I(D(Te), null, {
				default: u(() => [I(D(we), { class: "bulk-vue-overlay" }), I(D(xe), {
					class: "bulk-vue-dialog",
					onCloseAutoFocus: L
				}, {
					default: u(() => [
						I(D(Ee), null, {
							default: u(() => [...t[12] ||= [m("账号执行详情", -1)]]),
							_: 1
						}),
						I(D(Se), null, {
							default: u(() => [m(_(j.value?.account) + " · 账号 #" + _(j.value?.accountId), 1)]),
							_: 1
						}),
						j.value ? (o(), f("dl", Vi, [
							t[15] ||= w("dt", null, "结果 / 阶段", -1),
							w("dd", null, _(j.value.state) + " · " + _(j.value.stage || "—"), 1),
							t[16] ||= w("dt", null, "结果摘要", -1),
							w("dd", null, _(j.value.summary), 1),
							j.value.capabilities ? (o(), f(N, { key: 0 }, [t[13] ||= w("dt", null, "能力结果", -1), w("dd", null, _(j.value.capabilities), 1)], 64)) : v("", !0),
							t[17] ||= w("dt", null, "错误分类 / 错误码", -1),
							w("dd", null, _(j.value.reasonContent || "—"), 1),
							t[18] ||= w("dt", null, "所属执行", -1),
							w("dd", null, _(j.value.taskId ? "任务 #" + j.value.taskId : "尚未创建执行") + _(j.value.runId ? " · 运行 #" + j.value.runId : ""), 1),
							j.value.blockerTaskId ? (o(), f(N, { key: 1 }, [t[14] ||= w("dt", null, "占用任务（其他执行）", -1), w("dd", null, "#" + _(j.value.blockerTaskId), 1)], 64)) : v("", !0)
						])) : v("", !0),
						I(D(pe), {
							class: "jobs-tb-btn",
							"data-close-detail": ""
						}, {
							default: u(() => [...t[19] ||= [m("关闭", -1)]]),
							_: 1
						})
					]),
					_: 1
				})]),
				_: 1
			})]),
			_: 1
		}, 8, ["open"])], 64));
	}
}), Ui = ["aria-busy"], Wi = { class: "bulk-detail-page-heading" }, Gi = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, Ki = {
	key: 1,
	class: "bulk-card bulk-overview"
}, qi = { class: "bulk-detail-toolbar" }, Ji = { class: "bulk-detail-meta" }, Yi = { class: "bulk-settings bulk-detail-settings" }, Xi = {
	key: 0,
	class: "bulk-projection-note"
}, Zi = { class: "bulk-actions" }, Qi = { class: "bulk-round-picker" }, $i = ["value"], ea = ["value"], ta = ["value"], na = ["disabled"], ra = ["disabled"], ia = { class: "bulk-control-strip" }, aa = { class: "bulk-control-copy" }, oa = { class: "bulk-actions" }, sa = [
	"data-bulk-action",
	"disabled",
	"onClick"
], ca = { class: "bulk-view-note" }, la = { class: "bulk-summary-grid" }, ua = { class: "bulk-summary-item" }, da = { class: "bulk-summary-item" }, fa = { class: "bulk-summary-item is-success" }, pa = { class: "bulk-summary-item is-warning" }, ma = ["aria-busy"], ha = {
	key: 1,
	class: "bulk-plan-report bulk-report-placeholder"
}, ga = {
	key: 2,
	class: "bulk-report-load-error"
}, _a = {
	class: "bulk-error",
	role: "alert"
}, va = ["disabled"], ya = { class: "bulk-card bulk-results-card" }, ba = { class: "bulk-results-heading" }, xa = ["disabled"], Sa = { class: "bulk-retry-toolbar" }, Ca = ["value"], wa = ["disabled"], Ta = ["disabled"], Ea = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, Da = {
	key: 1,
	class: "bulk-notice",
	role: "status"
}, Oa = {
	class: "bulk-target-count-row",
	"data-bulk-target-count-row": ""
}, ka = {
	class: "bulk-target-count",
	role: "status"
}, Aa = { class: "bulk-vue-dialog-actions" }, ja = /*#__PURE__*/ j(/* @__PURE__ */ c({
	__name: "BulkDetail",
	props: {
		navigation: {},
		deps: {},
		visible: {
			type: Boolean,
			default: void 0
		}
	},
	setup(t, { expose: i }) {
		let a = t, s = Dr(() => a.navigation, a.deps, a.visible ?? a.navigation.view === "detail"), { navigation: c, detail: d, targets: p, report: h, rounds: x, roundsCursor: C, selected: T, pendingRound: E, loading: k, targetsLoading: A, reportLoading: j, roundsLoading: M, writing: P, error: F, targetError: L, reportError: R, actionError: z, confirmation: B, counts: V, ended: H, paused: U, hasReport: ee, hasPrevious: W, nextCursor: G } = s, K = e(null), q = e(null), J = e("failed"), Y = O(() => [
			"success",
			"partial_success",
			"failed",
			"not_executed",
			"cancelled"
		].reduce((e, t) => e + (V.value[t] || 0), 0)), ne = O(() => [
			"pending_submit",
			"waiting_account",
			"queued",
			"running",
			"waiting"
		].reduce((e, t) => e + (V.value[t] || 0), 0)), re = O(() => x.value.find((e) => e.id === c.value.round_id)), ie = O(() => !!(Z(d.value?.selection_summary).query || d.value?.query_spec || Z(d.value?.selection).query_spec)), ae = [
			"running",
			"queued",
			"success",
			"failed",
			"partial_success",
			"pending_submit",
			"waiting_account",
			"waiting",
			"not_executed",
			"cancelled"
		], oe = O(() => c.value.result_state ? [{
			key: "result_state",
			label: `结果状态：${lr(c.value.result_state)}`,
			title: `结果状态：${lr(c.value.result_state)}`,
			removeLabel: "清除结果状态筛选"
		}] : []), se = [
			["failed", "失败"],
			["partial_success", "部分成功"],
			["not_executed", "未执行"],
			["cancelled", "已取消"],
			["unsuccessful", "全部未成功"]
		], ce = [
			[
				"pause",
				"暂停批次",
				"pause"
			],
			[
				"resume",
				"继续批次",
				"resume"
			],
			[
				"cancel_not_started",
				"取消排队账号",
				"cancel"
			],
			[
				"request_stop",
				"停止正在执行",
				"stop"
			]
		], le = null;
		function ue(e) {
			le = e.currentTarget;
		}
		async function de(e, t) {
			ue(t), await s.retry(e, J.value);
		}
		async function fe(e, t) {
			ue(t), await s.control(e);
		}
		function pe(e) {
			e.preventDefault();
			let t = le;
			le = null, S(() => {
				if (t?.isConnected && !t.hasAttribute("disabled") && !t.closest("[hidden],[inert]")) {
					let e = t;
					for (; e;) {
						if (getComputedStyle(e).display === "none" || getComputedStyle(e).visibility === "hidden") return;
						e = e.parentElement;
					}
					t.focus({ preventScroll: !0 });
				}
			});
		}
		async function me() {
			await S(), q.value && (q.value.focus({ preventScroll: !0 }), q.value.scrollIntoView?.({ block: "start" })), !h.value && !j.value && await s.refreshReport(!0);
		}
		function he(e) {
			s.setVisible(e), e || (K.value?.close(), le = null);
		}
		return l(() => a.visible, (e) => {
			e !== void 0 && he(e);
		}, { flush: "sync" }), l(() => [
			c.value.batch_id,
			c.value.round_id,
			c.value.result_state,
			c.value.view
		], () => {
			K.value?.close(), le = null;
		}), i({
			refresh: s.refresh,
			showReport: me,
			setVisible: he,
			needsRefresh: s.needsPolling
		}), (e, i) => (o(), f("div", {
			class: "bulk-detail-owner",
			"aria-busy": D(k)
		}, [
			w("header", Wi, [w("div", null, [w("h2", null, _(D(d)?.name || D(d)?.title || "批次详情"), 1), w("p", null, _(D(dr)(D(ur)(D(d)))) + " · #" + _(D(c).batch_id), 1)]), D(ee) ? (o(), f("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "view-report",
				onClick: me
			}, "查看报告")) : v("", !0)]),
			D(F) ? (o(), f("p", Gi, [m(_(D(F)) + " ", 1), w("button", {
				type: "button",
				class: "bulk-link",
				onClick: i[0] ||= (e) => D(s).refresh(!0)
			}, "重试读取批次")])) : v("", !0),
			D(d) ? (o(), f("section", Ki, [
				w("div", qi, [w("div", Ji, [
					w("span", { class: g(["bulk-badge", D(sr)(D(U) ? "paused" : D(Z)(D(d).control).state || D(d).control_state || D(d).state)]) }, _(D(lr)(D(U) ? "paused" : D(Z)(D(d).control).state || D(d).control_state || D(d).state)), 3),
					w("span", null, "创建于 " + _(t.deps.callbacks.formatDateTime(D(d).created_at)), 1),
					w("details", Yi, [i[16] ||= w("summary", null, "范围与设置", -1), w("dl", null, [
						i[13] ||= w("dt", null, "名单生成", -1),
						w("dd", null, _(t.deps.callbacks.formatDateTime(D(Z)(D(d).selection_summary).selection_at || D(d).selection_at)), 1),
						i[14] ||= w("dt", null, "配置版本", -1),
						w("dd", null, _(D(Z)(D(d).effective_settings).config_revision || D(d).config_revision || "—"), 1),
						i[15] ||= w("dt", null, "结果更新", -1),
						w("dd", null, _(t.deps.callbacks.formatDateTime(D(d).projected_at)), 1)
					])]),
					D(Z)(D(d).projection).state && D(Z)(D(d).projection).state !== "current" ? (o(), f("span", Xi, "汇总同步中")) : v("", !0)
				]), w("div", Zi, [
					w("label", Qi, [i[18] ||= w("span", { class: "bulk-sr-only" }, "结果视图", -1), w("select", {
						value: D(c).round_id || "current",
						"aria-label": "结果视图",
						onChange: i[1] ||= (e) => D(s).setRound(e.target.value)
					}, [
						i[17] ||= w("option", { value: "current" }, "当前结果", -1),
						(o(!0), f(N, null, r(D(x), (e) => (o(), f("option", {
							key: String(e.id),
							value: String(e.id)
						}, _(Number(e.round_no) === 1 ? "首轮" : "重跑 " + (Number(e.round_no) - 1)) + " · " + _(D(lr)(e.state)) + " · " + _(e.target_count == null ? "准备中" : D($)(e.target_count) + " 个"), 9, ea))), 128)),
						D(c).round_id && !re.value ? (o(), f("option", {
							key: 0,
							value: D(c).round_id
						}, "所选轮次 #" + _(D(c).round_id), 9, ta)) : v("", !0)
					], 40, $i)]),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "more-rounds",
						disabled: !D(C) || D(M),
						onClick: i[2] ||= (...e) => D(s).moreRounds && D(s).moreRounds(...e)
					}, "更多轮次", 8, na),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "copy-targets",
						onClick: i[3] ||= (e) => D(s).copyBatch(!0)
					}, "同一名单再次执行"),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "copy-query",
						disabled: !ie.value,
						onClick: i[4] ||= (e) => D(s).copyBatch(!1)
					}, "复制条件新建", 8, ra)
				])]),
				w("div", ia, [w("div", aa, [i[19] ||= w("strong", null, "运行控制", -1), w("span", null, _(D(H) ? "批次已结束" : D(U) ? "批次已暂停，尚未开始的账号等待继续；已开始账号继续收尾" : ne.value + " 个进行中 · 已结束 " + Y.value + " / " + D($)(D(d).target_count)), 1)]), w("div", oa, [(o(), f(N, null, r(ce, ([e, t, n]) => w("button", {
					key: e,
					type: "button",
					class: g(["jobs-tb-btn", { "jobs-tb-btn--danger": ["cancel", "stop"].includes(n) }]),
					"data-bulk-action": n,
					disabled: D(s).controlDisabled(e),
					onClick: (t) => fe(e, t)
				}, _(t), 11, sa)), 64))])]),
				w("p", ca, _(re.value?.completion_reason === "cancelled_before_freeze" ? "本轮在名单生成前取消，当前结果未改变。" : D(c).round_id ? "仅展示该轮名单及执行结果。" : "已结束 " + Y.value + " / " + D($)(D(d).target_count) + " 个 · 每个账号保留最近一轮结果"), 1),
				D(ee) ? v("", !0) : (o(), f(N, { key: 0 }, [w("div", la, [
					w("div", ua, [i[20] ||= w("span", null, "账号总数", -1), w("strong", null, _(D($)(D(d).target_count)), 1)]),
					w("div", da, [i[21] ||= w("span", null, "进行中", -1), w("strong", null, _(ne.value), 1)]),
					w("div", fa, [i[22] ||= w("span", null, "成功", -1), w("strong", null, _(D(V).success || 0), 1)]),
					w("div", pa, [i[23] ||= w("span", null, "未成功", -1), w("strong", null, _(D(s).retryCount("unsuccessful")), 1)])
				]), I(jr, { metrics: D(d).business_summary || D(d).metrics }, null, 8, ["metrics"])], 64))
			])) : v("", !0),
			D(ee) ? (o(), f("section", {
				key: 2,
				ref_key: "reportRegion",
				ref: q,
				"data-bulk-plan-report": "",
				class: "bulk-report-target",
				tabindex: "-1",
				role: "region",
				"aria-label": "批次报告",
				"aria-busy": D(j)
			}, [D(h) ? (o(), y(ui, {
				key: 0,
				report: D(h),
				"format-date-time": t.deps.callbacks.formatDateTime
			}, null, 8, ["report", "format-date-time"])) : D(R) ? v("", !0) : (o(), f("div", ha, [w("h3", null, _(D(dr)(D(ur)(D(d)))) + "报告", 1), i[24] ||= w("p", { role: "status" }, "正在汇总本次执行结果…", -1)])), D(R) ? (o(), f("div", ga, [w("p", _a, "读取报告失败：" + _(D(R)), 1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "report-refresh",
				disabled: D(j),
				onClick: i[5] ||= (e) => D(s).refreshReport(!0)
			}, "重新读取报告", 8, va)])) : v("", !0)], 8, ma)) : v("", !0),
			w("section", ya, [
				w("div", ba, [w("h3", null, [
					i[25] ||= m("账号明细 ", -1),
					w("span", null, _(D(T).size ? "已选 " + D(T).size + " 个（可跨页）" : ""), 1),
					w("button", {
						type: "button",
						class: "bulk-link",
						disabled: !D(T).size,
						onClick: i[6] ||= (...e) => D(s).clearSelection && D(s).clearSelection(...e)
					}, "清空选择", 8, xa)
				]), w("div", Sa, [
					n(w("select", {
						"onUpdate:modelValue": i[7] ||= (e) => J.value = e,
						"aria-label": "重跑范围"
					}, [(o(), f(N, null, r(se, ([e, t]) => w("option", {
						key: e,
						value: e
					}, _(t), 9, Ca)), 64))], 512), [[b, J.value]]),
					w("button", {
						type: "button",
						class: "jobs-tb-btn jobs-tb-btn--primary",
						"data-bulk-action": "retry",
						disabled: D(P) || !!D(B) || !D(s).retryCount(J.value),
						onClick: i[8] ||= (e) => de(!1, e)
					}, "重跑" + _(se.find((e) => e[0] === J.value)?.[1]) + " (" + _(D(s).retryCount(J.value)) + ")", 9, wa),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "retry-selected",
						disabled: D(P) || !!D(B) || !D(T).size,
						onClick: i[9] ||= (e) => de(!0, e)
					}, "重跑勾选" + _(D(T).size ? " (" + D(T).size + ")" : ""), 9, Ta)
				])]),
				D(z) ? (o(), f("p", Ea, _(D(z)), 1)) : v("", !0),
				D(E) ? (o(), f("p", Da, "重跑已受理，正在准备新轮次 #" + _(D(E)) + "。", 1)) : v("", !0),
				w("div", Oa, [w("span", ka, "共 " + _(D($)(D(d)?.target_count)) + " 个账号 · 当前页 " + _(D(p)?.items.length || 0) + " 个", 1), I(te, {
					items: oe.value,
					onRemove: i[10] ||= (e) => D(s).setFilter("")
				}, null, 8, ["items"])]),
				I(Hi, {
					ref_key: "targetTable",
					ref: K,
					scope: [
						D(c).batch_id,
						D(c).round_id,
						D(c).result_state,
						D(c).cursor
					].join(":"),
					items: D(p)?.items || [],
					selected: D(T),
					loading: D(A) || D(k) && !D(d),
					error: D(L),
					"result-state": D(c).result_state || "",
					"result-counts": D(V),
					"result-total": D(d)?.target_count,
					"result-states": ae,
					"open-task": t.deps.callbacks.openTask,
					onFilter: D(s).setFilter,
					onToggle: D(s).toggleTarget,
					onSelectPage: D(s).selectPage,
					onRetry: D(s).loadTargets
				}, null, 8, [
					"scope",
					"items",
					"selected",
					"loading",
					"error",
					"result-state",
					"result-counts",
					"result-total",
					"open-task",
					"onFilter",
					"onToggle",
					"onSelectPage",
					"onRetry"
				]),
				I(Ue, {
					"has-previous": D(W),
					"next-cursor": D(G),
					"item-count": D(p)?.items.length || 0,
					"has-cursor": !!D(c).cursor,
					busy: D(A),
					label: "账号明细分页",
					onNext: D(s).next,
					onPrevious: D(s).previous,
					onFirst: D(s).first
				}, null, 8, [
					"has-previous",
					"next-cursor",
					"item-count",
					"has-cursor",
					"busy",
					"onNext",
					"onPrevious",
					"onFirst"
				])
			]),
			I(D(Pe), {
				open: !!D(B),
				"onUpdate:open": i[12] ||= (e) => {
					e || D(s).cancelConfirmation();
				}
			}, {
				default: u(() => [I(D(Ne), null, {
					default: u(() => [I(D(Me), { class: "bulk-vue-overlay" }), I(D(ke), {
						class: "bulk-vue-dialog",
						onCloseAutoFocus: pe
					}, {
						default: u(() => [
							I(D(Fe), null, {
								default: u(() => [m(_(D(B)?.title), 1)]),
								_: 1
							}),
							I(D(je), null, {
								default: u(() => [m(_(D(B)?.description), 1)]),
								_: 1
							}),
							w("p", null, "范围：" + _(D(B)?.scopeLabel) + " · 预计账号：" + _(D(B)?.count) + " 个", 1),
							w("div", Aa, [I(D(Ae), {
								class: "jobs-tb-btn",
								"data-confirm-cancel": "",
								onClick: D(s).cancelConfirmation
							}, {
								default: u(() => [...i[26] ||= [m("返回", -1)]]),
								_: 1
							}, 8, ["onClick"]), w("button", {
								type: "button",
								class: "jobs-tb-btn jobs-tb-btn--danger",
								"data-confirm-submit": "",
								onClick: i[11] ||= (...e) => D(s).confirm && D(s).confirm(...e)
							}, _(D(B)?.label), 1)])
						]),
						_: 1
					})]),
					_: 1
				})]),
				_: 1
			}, 8, ["open"])
		], 8, Ui));
	}
}), [["__scopeId", "data-v-50269f1b"]]), Ma = [
	"batch_id",
	"round_id",
	"result_state",
	"cursor",
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
], Na = /* @__PURE__ */ new Set([
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
]);
function Pa(e = {}) {
	let t = [
		"list",
		"create",
		"detail"
	].includes(e.view || "") ? e.view : "list", n = {
		tab: "bulk",
		view: t
	};
	for (let t of Ma) typeof e[t] == "string" && e[t] && (n[t] = e[t]);
	if (t === "detail") {
		if (!/^[1-9]\d*$/.test(n.batch_id || "")) return {
			tab: "bulk",
			view: "list"
		};
		(n.q || e.reason_code) && (delete n.q, delete n.cursor), n.result_state && Na.has(n.result_state) && (n.result_state = "failed");
	}
	return n;
}
// src/features/bulk/BulkPageShell.vue?vue&type=script&setup=true&lang.ts
var Fa = {
	class: "bulk-page bulk-page-shell",
	"data-bulk-vue": ""
}, Ia = { class: "bulk-page-heading" }, La = { "data-bulk-title": "" }, Ra = { class: "bulk-actions" }, za = {
	key: 0,
	class: "bulk-error",
	"data-bulk-error": "",
	role: "alert"
}, Ba = {
	key: 1,
	class: "bulk-notice",
	"data-bulk-notice": "",
	role: "status"
}, Va = {
	key: 2,
	class: "bulk-notice bulk-global-recovery",
	"data-bulk-recovery": "",
	role: "status"
}, Ha = ["disabled"], Ua = { "data-bulk-content": "" }, Wa = /*#__PURE__*/ j(/* @__PURE__ */ c({
	__name: "BulkPageShell",
	props: {
		deps: {},
		initialNavigation: {}
	},
	setup(r, { expose: i }) {
		let a = r, s = M(Pa(a.initialNavigation)), c = e(!1), u = e(!1), d = e(""), p = e(""), m = e(!1), h = e(0), g = M(null), y = e(null), b = e(null), C = e(null), T = !1, D = 0, k = 0, A = !1, j, N = null, P = "", F = !1, L = O(() => c.value && u.value), R = {
			...a.deps.callbacks,
			navigate: (e, t, n) => {
				ie(e, t, n);
			},
			updateNavigation: (e) => {
				ae(e);
			},
			notify: (e) => {
				p.value = e, h.value++, a.deps.callbacks.notify(e);
			},
			copyBatch: (e, t, n) => {
				oe(e, t, n);
			}
		}, z = {
			pending: () => a.deps.intents.pending(),
			submit: async (e, t, n) => {
				try {
					return await a.deps.intents.submit(e, t, n);
				} finally {
					h.value++;
				}
			},
			recover: async (e) => {
				try {
					return await a.deps.intents.recover(e);
				} finally {
					h.value++;
				}
			}
		}, B = {
			api: a.deps.api,
			callbacks: R
		}, V = {
			...a.deps,
			intents: z,
			callbacks: R
		}, H = {
			api: a.deps.api,
			intents: z,
			callbacks: R,
			now: a.deps.now
		}, U = O(() => {
			h.value;
			try {
				return a.deps.intents.pending();
			} catch {
				return [];
			}
		}), ee = O(() => L.value ? s.value.view === "list" ? 7e3 : s.value.view === "create" ? b.value?.needsRefresh ? 2e3 : 0 : C.value?.needsRefresh ? 2e3 : 0 : 0), W = O(() => s.value.view === "list" ? "批量任务" : s.value.view === "create" ? "新建批次" : `批次 #${s.value.batch_id}`);
		function G() {
			u.value = !document.hidden && (a.deps.isVisible?.() ?? !0), A !== L.value && (k++, A = L.value), y.value?.setVisible(L.value && s.value.view === "list"), b.value?.setVisible(L.value && s.value.view === "create"), C.value?.setVisible(L.value && s.value.view === "detail");
		}
		function K() {
			clearTimeout(j), j = void 0, !T && ee.value && (j = setTimeout(() => {
				j = void 0, G(), L.value && q(!1);
			}, ee.value));
		}
		async function q(e = !0) {
			if (await S(), T || (G(), !L.value)) return;
			let t = JSON.stringify([s.value, k]);
			if (N && P === t) return N;
			let n = (async () => {
				try {
					s.value.view === "list" ? await y.value?.refresh() : s.value.view === "create" ? await b.value?.refresh(e) : (await C.value?.refresh(e), F && (F = !1, await C.value?.showReport()));
				} finally {
					h.value++;
				}
			})();
			N = n, P = t;
			try {
				await n;
			} finally {
				N === n && (N = null, P = ""), K();
			}
		}
		async function te() {
			c.value = !0, await q(!1);
		}
		async function J() {
			s.value.view === "detail" && (F = !0, await q(!1));
		}
		function Y(e) {
			c.value = e, G(), K();
		}
		function ne() {
			return { ...s.value };
		}
		function re(e) {
			D++, s.value = Pa(e), d.value = "", p.value = "", F = !1;
		}
		async function ie(e, t = {}, n = !1) {
			re({
				tab: "bulk",
				view: e,
				...t
			}), F = n, c.value = !0, a.deps.onNavigation(ne(), "push"), await q(!1);
		}
		async function ae(e) {
			D++, s.value = Pa({
				...s.value,
				...e
			}), a.deps.onNavigation(ne(), "replace"), await S(), K();
		}
		async function oe(e, t, n = "plan_check") {
			let r = JSON.parse(JSON.stringify({
				query: e,
				source: t
			}));
			g.value = {
				name: "",
				operation_key: n,
				query: a.deps.adapter.normalize({
					...r.query,
					limit: null
				}),
				source: r.source,
				parameters: {},
				max_concurrency: 3
			}, await ie("create");
		}
		async function se(e = !1, t = "plan_check", n) {
			if (!n) {
				R.notify("账号范围未就绪，请返回账号页重试");
				return;
			}
			let r = e ? n.ids.map((e) => X(typeof e == "number" && Number.isSafeInteger(e) ? String(e) : e)) : [];
			e && !r.length ? R.notify("请先选择账号") : await oe(n.query, e ? {
				kind: "ids",
				entity: "account",
				ids: r
			} : null, t);
		}
		async function ce() {
			await oe(a.deps.adapter.normalize(), null);
		}
		async function le(e, t) {
			await S(), b.value?.restoreSelectionRequest(e, t);
		}
		async function ue() {
			if (m.value) return;
			m.value = !0, d.value = "";
			let e = D;
			try {
				let t = a.deps.intents.pending()[0];
				if (!t) return;
				let n = await a.deps.intents.recover(t);
				if (T || e !== D || !L.value) {
					let e = n.id || n.batch_id || n.round_id;
					R.notify(t.path === "/batches" ? `原批次 #${X(e)} 已创建` : `原请求回执已找回${e ? "，编号 #" + String(e) : ""}。`);
					return;
				}
				if (t.path === "/selections") g.value = null, await le(t.body, n), await ie("create"), R.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
				else if (t.path === "/batches") {
					try {
						a.deps.storage.removeItem("turb_bulk_selection_v1");
					} catch {}
					await ie("detail", { batch_id: X(n.id || n.batch_id) });
				} else {
					let e = t.path.match(/^\/batches\/([1-9]\d*)\//);
					e && await ie("detail", { batch_id: e[1] }), R.notify("原请求回执已找回。");
				}
			} catch (e) {
				d.value = e instanceof Error ? e.message : String(e);
			} finally {
				m.value = !1, h.value++;
			}
		}
		function de() {
			let e = L.value;
			G(), !e && L.value ? q(!1) : K();
		}
		return l(ee, K, { flush: "post" }), x(() => {
			G(), document.addEventListener("visibilitychange", de);
		}), t(() => {
			T = !0, clearTimeout(j), document.removeEventListener("visibilitychange", de);
		}), i({
			activate: te,
			setVisible: Y,
			refresh: q,
			showReport: J,
			navigationState: ne,
			restoreNavigation: re,
			navigate: ie,
			fromAccounts: se,
			recover: ue,
			restoreSelectionRequest: le
		}), (e, t) => (o(), f("div", Fa, [
			w("header", Ia, [w("h2", La, _(W.value), 1), w("div", Ra, [
				s.value.view === "list" ? v("", !0) : (o(), f("button", {
					key: 0,
					type: "button",
					class: "jobs-tb-btn",
					onClick: t[0] ||= (e) => ie("list")
				}, "批次列表")),
				w("button", {
					type: "button",
					class: "jobs-tb-btn",
					"data-bulk-action": "refresh",
					onClick: t[1] ||= (e) => q(!0)
				}, "刷新"),
				w("button", {
					type: "button",
					class: "jobs-tb-btn jobs-tb-btn--primary",
					"data-bulk-action": "new",
					onClick: ce
				}, "新建批次")
			])]),
			d.value ? (o(), f("p", za, _(d.value), 1)) : v("", !0),
			p.value ? (o(), f("p", Ba, _(p.value), 1)) : v("", !0),
			U.value.length && s.value.view !== "create" ? (o(), f("div", Va, [w("span", null, "有 " + _(U.value.length) + " 个请求未收到回执，草稿已保留。", 1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: m.value,
				onClick: ue
			}, _(m.value ? "正在找回…" : "找回原请求"), 9, Ha)])) : v("", !0),
			w("div", Ua, [
				n(I(jt, {
					ref_key: "list",
					ref: y,
					navigation: s.value,
					deps: B
				}, null, 8, ["navigation"]), [[E, s.value.view === "list"]]),
				n(I(rr, {
					ref_key: "create",
					ref: b,
					navigation: s.value,
					deps: V,
					seed: g.value,
					visible: L.value && s.value.view === "create"
				}, null, 8, [
					"navigation",
					"seed",
					"visible"
				]), [[E, s.value.view === "create"]]),
				n(I(ja, {
					ref_key: "detail",
					ref: C,
					navigation: s.value,
					deps: H,
					visible: L.value && s.value.view === "detail"
				}, null, 8, ["navigation", "visible"]), [[E, s.value.view === "detail"]])
			])
		]));
	}
}), [["__scopeId", "data-v-91ee635b"]]), Ga = "turb_bulk_intent:", Ka = /* @__PURE__ */ new Set([
	400,
	403,
	404,
	409,
	410,
	422,
	429
]);
function qa(e, t, n) {
	let r = /* @__PURE__ */ new Map();
	function i(e, t) {
		if (!t) return null;
		let n = JSON.parse(t);
		if (typeof n.key != "string" || typeof n.signature != "string") throw Error("未决请求记录无效，请先检查原回执");
		let r = JSON.parse(n.signature);
		if (typeof r.path != "string" || !r.body || typeof r.body != "object" || Array.isArray(r.body)) throw Error("未决请求内容无效，请先检查原回执");
		return {
			storageKey: e,
			key: n.key,
			signature: n.signature,
			path: r.path,
			body: r.body
		};
	}
	async function a(a, o, s) {
		let c = Ga + a, l = JSON.stringify({
			path: o,
			body: s
		}), u = r.get(c);
		if (u) {
			if (u.signature !== l) throw new Mt("上一请求未收到回执，请先找回原请求，再提交新内容。", 0, "request_receipt_pending");
			return u.promise;
		}
		let d = i(c, t.getItem(c));
		if (d && d.signature !== l) throw new Mt("上一请求未收到回执，请先找回原请求，再提交新内容。", 0, "request_receipt_pending");
		let f = d?.key || n();
		t.setItem(c, JSON.stringify({
			key: f,
			signature: l
		}));
		let p = e.request(o, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"Idempotency-Key": f
			},
			body: JSON.stringify(s)
		}).then((e) => {
			try {
				t.removeItem(c);
			} catch {}
			return e;
		}, (e) => {
			if (Ka.has(Number(e?.status))) try {
				t.removeItem(c);
			} catch {}
			throw e;
		}).finally(() => r.delete(c));
		return r.set(c, {
			signature: l,
			promise: p
		}), p;
	}
	return {
		submit: a,
		pending() {
			let e = [];
			for (let n = 0; n < t.length; n++) {
				let r = t.key(n);
				if (r?.startsWith(Ga)) {
					let n = i(r, t.getItem(r));
					n && e.push(n);
				}
			}
			return e;
		},
		recover(e) {
			return a(e.storageKey.slice(17), e.path, e.body);
		}
	};
}
// src/bulk.ts
function Ja(e, t) {
	let n = Nt(), r = {
		get length() {
			return window.sessionStorage.length;
		},
		key: (e) => window.sessionStorage.key(e),
		getItem: (e) => window.sessionStorage.getItem(e),
		setItem: (e, t) => window.sessionStorage.setItem(e, t),
		removeItem: (e) => window.sessionStorage.removeItem(e)
	}, i = qa(n, r, () => globalThis.crypto?.randomUUID?.() || `bulk-${Date.now()}-${Math.random().toString(36).slice(2)}`), a = T(Wa, {
		initialNavigation: t.navigation,
		deps: {
			api: n,
			intents: i,
			storage: r,
			adapter: ce(t.query),
			callbacks: t.callbacks,
			onNavigation: t.onNavigation,
			isVisible: t.isVisible,
			now: Date.now
		}
	}).mount(e);
	return Object.assign(a, {
		request: n.request,
		intent: i.submit
	});
}
export { Ja as mountBulk };
