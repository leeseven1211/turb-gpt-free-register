import { $ as e, A as t, C as n, E as r, F as i, G as a, H as o, K as s, L as c, M as l, R as u, S as d, T as f, Z as p, _ as m, a as h, c as g, d as _, dt as v, et as y, ft as b, g as x, h as S, it as C, j as w, k as T, l as E, lt as D, m as O, n as k, nt as A, o as j, r as M, s as N, st as P, t as F, ut as I, v as L, x as R } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { _ as z, b as B, c as V, d as H, f as U, g as W, h as ee, l as G, m as K, n as q, p as J, r as te, t as ne, u as re, v as ie, x as Y, y as ae } from "./ListFilterSummary-Bc1S5NP4.js";
import { a as oe, c as se, n as ce, o as le, s as ue, t as de } from "./queryAdapter-BuJS1py0.js";
import { t as fe } from "./errorLabels-B-XqaTSM.js";
// node_modules/reka-ui/dist/Dialog/DialogRoot.js
var [pe, me] = /*#__PURE__*/ Y("DialogRoot"), he = /* @__PURE__ */ n({
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
	setup(e, { emit: t }) {
		let n = e, r = ae(n, "open", t, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		}), i = y(), a = y(), { modal: o, unmountOnHide: s } = C(n);
		return me({
			open: r,
			modal: o,
			unmountOnHide: s,
			openModal: () => {
				r.value = !0;
			},
			onOpenChange: (e) => {
				r.value = e;
			},
			onOpenToggle: () => {
				r.value = !r.value;
			},
			contentId: "",
			titleId: "",
			descriptionId: "",
			triggerElement: i,
			contentElement: a
		}), (e, t) => u(e.$slots, "default", {
			open: P(r),
			close: () => r.value = !1
		});
	}
}), ge = /* @__PURE__ */ n({
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
		W();
		let n = pe();
		return (r, o) => (i(), x(P(H), T(t, {
			type: e.as === "button" ? "button" : void 0,
			onClick: o[0] ||= (e) => P(n).onOpenChange(!1)
		}), {
			default: a(() => [u(r.$slots, "default")]),
			_: 3
		}, 16, ["type"]));
	}
}), _e = ["Enter", " "], ve = [
	"ArrowDown",
	"PageUp",
	"Home"
], ye = [
	"ArrowUp",
	"PageDown",
	"End"
];
[...ve, ...ye], [..._e], [..._e];
function be(e) {
	return e ? "open" : "closed";
}
// node_modules/reka-ui/dist/Dialog/DialogContentImpl.js
var xe = /* @__PURE__ */ n({
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
		let n = e, r = t, o = pe(), { forwardRef: s, currentElement: c } = W();
		return o.titleId ||= J(void 0, "reka-dialog-title"), o.descriptionId ||= J(void 0, "reka-dialog-description"), l(() => {
			o.contentElement = c, B() !== document.body && (o.triggerElement.value = B());
		}), (t, c) => (i(), x(P(G), {
			"as-child": "",
			loop: "",
			trapped: n.trapFocus,
			present: n.present,
			onMountAutoFocus: c[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: c[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: a(() => [d(P(re), T({
				id: P(o).contentId,
				ref: P(s),
				as: e.as,
				"as-child": e.asChild,
				present: n.present,
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				role: "dialog",
				"aria-describedby": P(o).descriptionId,
				"aria-labelledby": P(o).titleId,
				"data-state": P(be)(P(o).open.value)
			}, t.$attrs, {
				onDismiss: c[0] ||= (e) => P(o).onOpenChange(!1),
				onEscapeKeyDown: c[1] ||= (e) => r("escapeKeyDown", e),
				onFocusOutside: c[2] ||= (e) => r("focusOutside", e),
				onInteractOutside: c[3] ||= (e) => r("interactOutside", e),
				onPointerDownOutside: c[4] ||= (e) => r("pointerDownOutside", e)
			}), {
				default: a(() => [u(t.$slots, "default")]),
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
}), Se = /* @__PURE__ */ n({
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
		let n = e, r = t, s = pe(), c = z(r), { forwardRef: l, currentElement: d } = W(), f = O(() => n.present ? d.value : void 0);
		K(f);
		let p = O(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return o(() => n.present, (e, t) => {
			!e && t && s.triggerElement.value?.focus();
		}), (t, r) => (i(), x(xe, T({
			...p.value,
			...P(c)
		}, {
			ref: P(l),
			present: e.present,
			"trap-focus": P(s).open.value,
			"disable-outside-pointer-events": n.disableOutsidePointerEvents,
			onCloseAutoFocus: r[0] ||= (e) => {
				e.defaultPrevented || (e.preventDefault(), P(s).triggerElement.value?.focus());
			},
			onPointerDownOutside: r[1] ||= (e) => {
				let t = e.detail.originalEvent, n = t.button === 0 && t.ctrlKey === !0;
				(t.button === 2 || n) && e.preventDefault();
			},
			onFocusOutside: r[2] ||= (e) => {
				e.preventDefault();
			}
		}), {
			default: a(() => [u(t.$slots, "default")]),
			_: 3
		}, 16, [
			"present",
			"trap-focus",
			"disable-outside-pointer-events"
		]));
	}
}), Ce = /* @__PURE__ */ n({
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
	setup(e, { emit: t }) {
		let n = e, r = z(t);
		W();
		let s = pe(), c = y(!1), l = y(!1), d = O(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return o(() => n.present, (e, t) => {
			!e && t && (c.value || s.triggerElement.value?.focus(), c.value = !1, l.value = !1);
		}), (t, n) => (i(), x(xe, T({
			...d.value,
			...P(r)
		}, {
			present: e.present,
			"trap-focus": !1,
			"disable-outside-pointer-events": !1,
			onCloseAutoFocus: n[0] ||= (e) => {
				e.defaultPrevented || (c.value || P(s).triggerElement.value?.focus(), e.preventDefault()), c.value = !1, l.value = !1;
			},
			onInteractOutside: n[1] ||= (e) => {
				e.defaultPrevented || (c.value = !0, e.detail.originalEvent.type === "pointerdown" && (l.value = !0));
				let t = e.target;
				P(s).triggerElement.value?.contains(t) && e.preventDefault(), e.detail.originalEvent.type === "focusin" && l.value && e.preventDefault();
			}
		}), {
			default: a(() => [u(t.$slots, "default")]),
			_: 3
		}, 16, ["present"]));
	}
}), we = /* @__PURE__ */ n({
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
		let n = e, r = t, o = pe(), c = z(r), { forwardRef: l } = W(), d = O(() => n.forceMount || !o.unmountOnHide.value);
		return (t, r) => (i(), x(P(U), {
			present: P(o).open.value,
			"force-mount": d.value
		}, {
			default: a(({ present: r }) => [P(o).modal.value ? s((i(), x(Se, T({
				key: 0,
				ref: P(l),
				present: !d.value || r
			}, {
				...n,
				...P(c),
				...t.$attrs
			}), {
				default: a(() => [u(t.$slots, "default")]),
				_: 3
			}, 16, ["present"])), [[N, e.forceMount || P(o).unmountOnHide.value || r]]) : s((i(), x(Ce, T({
				key: 1,
				ref: P(l),
				present: !d.value || r
			}, {
				...n,
				...P(c),
				...t.$attrs
			}), {
				default: a(() => [u(t.$slots, "default")]),
				_: 3
			}, 16, ["present"])), [[N, e.forceMount || P(o).unmountOnHide.value || r]])]),
			_: 3
		}, 8, ["present", "force-mount"]));
	}
}), Te = /* @__PURE__ */ n({
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
		W();
		let n = pe();
		return (e, r) => (i(), x(P(H), T(t, { id: P(n).descriptionId }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), Ee = /* @__PURE__ */ n({
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
		let t = e, n = pe(), r = ie(t.present);
		return o(() => t.present, (e) => r.value = e), W(), (t, r) => (i(), x(P(H), {
			as: e.as,
			"as-child": e.asChild,
			"data-state": P(n).open.value ? "open" : "closed",
			style: { "pointer-events": "auto" },
			onPointerdown: r[0] ||= E(() => {}, [
				"left",
				"self",
				"prevent"
			])
		}, {
			default: a(() => [u(t.$slots, "default")]),
			_: 3
		}, 8, [
			"as",
			"as-child",
			"data-state"
		]));
	}
}), De = /* @__PURE__ */ n({
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
		let t = e, n = pe(), { forwardRef: r } = W(), o = O(() => t.forceMount || !n.unmountOnHide.value);
		return (t, c) => P(n)?.modal.value ? (i(), x(P(U), {
			key: 0,
			present: P(n).open.value,
			"force-mount": o.value
		}, {
			default: a(({ present: i }) => [s(d(Ee, T(t.$attrs, {
				ref: P(r),
				as: e.as,
				"as-child": e.asChild,
				present: !o.value || i
			}), {
				default: a(() => [u(t.$slots, "default")]),
				_: 3
			}, 16, [
				"as",
				"as-child",
				"present"
			]), [[N, e.forceMount || P(n).unmountOnHide.value || i]])]),
			_: 3
		}, 8, ["present", "force-mount"])) : m("v-if", !0);
	}
}), Oe = /* @__PURE__ */ n({
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
		return (e, n) => (i(), x(P(V), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), ke = /* @__PURE__ */ n({
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
		let t = e, n = pe();
		return W(), (e, r) => (i(), x(P(H), T(t, { id: P(n).titleId }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), [Ae, je] = /*#__PURE__*/ Y("AlertDialogContent"), Me = /* @__PURE__ */ n({
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
	setup(e, { emit: n }) {
		let r = e, o = z(n);
		W();
		let s = y();
		return je({ onCancelElementChange: (e) => {
			s.value = e;
		} }), (e, n) => (i(), x(P(we), T({
			...r,
			...P(o)
		}, {
			role: "alertdialog",
			onPointerDownOutside: n[0] ||= E(() => {}, ["prevent"]),
			onInteractOutside: n[1] ||= E(() => {}, ["prevent"]),
			onOpenAutoFocus: n[2] ||= () => {
				t(() => {
					s.value?.focus({ preventScroll: !0 });
				});
			}
		}), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ne = /* @__PURE__ */ n({
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
		let t = e, n = Ae(), { forwardRef: r, currentElement: o } = W();
		return l(() => {
			n.onCancelElementChange(o.value);
		}), (e, n) => (i(), x(P(ge), T(t, { ref: P(r) }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Pe = /* @__PURE__ */ n({
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
		return W(), (e, n) => (i(), x(P(Te), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Fe = /* @__PURE__ */ n({
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
		return W(), (e, n) => (i(), x(P(De), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ie = /* @__PURE__ */ n({
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
		return (e, n) => (i(), x(P(V), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Le = /* @__PURE__ */ n({
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
		let n = ee(e, t);
		return W(), (e, t) => (i(), x(P(he), T(P(n), { modal: !0 }), {
			default: a((t) => [u(e.$slots, "default", I(f(t)))]),
			_: 3
		}, 16));
	}
}), Re = /* @__PURE__ */ n({
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
		return W(), (e, n) => (i(), x(P(ke), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), ze = ["aria-label", "aria-busy"], Be = { class: "cursor-pagination__layout" }, Ve = {
	class: "cursor-pagination__count",
	"aria-live": "polite"
}, He = { class: "cursor-pagination__actions" }, Ue = ["disabled"], We = ["disabled"], Ge = ["disabled"], Ke = /*#__PURE__*/ F(/* @__PURE__ */ n({
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
		function a() {
			!n.busy && n.hasPrevious && r("previous");
		}
		function o() {
			!n.busy && n.nextCursor && r("next");
		}
		function s() {
			!n.busy && n.hasCursor && r("first");
		}
		return (t, n) => (i(), L("nav", {
			class: "cursor-pagination",
			"aria-label": e.label,
			"aria-busy": e.busy
		}, [S("div", Be, [S("span", Ve, "本页 " + b(e.itemCount) + " 个", 1), S("div", He, [
			e.hasCursor ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "cursor-pagination__first",
				"data-cursor-first": "",
				disabled: e.busy,
				onClick: s
			}, "返回首页", 8, Ue)) : m("", !0),
			S("button", {
				type: "button",
				"data-cursor-previous": "",
				disabled: e.busy || !e.hasPrevious,
				onClick: a
			}, "上一页", 8, We),
			S("button", {
				type: "button",
				"data-cursor-next": "",
				disabled: e.busy || !e.nextCursor,
				onClick: o
			}, "下一页", 8, Ge)
		])])], 8, ze));
	}
}), [["__scopeId", "data-v-7fd57e6e"]]);
// src/features/bulk/contracts.ts
function X(e) {
	if (typeof e != "string" || !/^[1-9]\d*$/.test(e)) throw Error("任务标识无效");
	return e;
}
function qe(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("批次列表响应格式无效");
	return e;
}
function Je(e) {
	let t = qe(e);
	if (!Array.isArray(t.items)) throw Error("批次列表响应格式无效");
	let n = t.items.map((e) => {
		let t = qe(e), n = Number.isSafeInteger(t.id) ? String(t.id) : t.id;
		if (typeof n != "string" || !/^[1-9]\d*$/.test(n)) throw Error("批次编号无效");
		return {
			...t,
			id: n
		};
	}), r = t.next_cursor ?? (t.page == null ? null : qe(t.page).next_cursor);
	if (r != null && typeof r != "string") throw Error("批次分页响应格式无效");
	return {
		items: n,
		summary: t.summary == null ? {} : qe(t.summary),
		nextCursor: r || null
	};
}
// src/features/bulk/useBulkList.ts
var Ye = [
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
];
function Xe(e) {
	let t = {
		tab: "bulk",
		view: "list",
		cursor: e.cursor || ""
	};
	for (let n of Ye) t[n] = e[n] || "";
	return t;
}
function Ze(e, t) {
	let n = /* @__PURE__ */ new Date(`${e}T00:00:00`), [r, i, a] = e.split("-").map(Number);
	if (!/^\d{4}-\d{2}-\d{2}$/.test(e) || n.getFullYear() !== r || n.getMonth() + 1 !== i || n.getDate() !== a) throw Error("创建日期无效，请调整筛选条件");
	return t && n.setDate(n.getDate() + 1), n.toISOString();
}
function Qe(e) {
	let t = new URLSearchParams({ page_size: "20" });
	return e.cursor && t.set("cursor", e.cursor), e.q && t.set("q", e.q), e.operation && t.set("operation_key[]", e.operation), e.state && t.set("control_state[]", e.state), e.created_from && t.set("created_from", Ze(e.created_from, !1)), e.created_to && t.set("created_before", Ze(e.created_to, !0)), t;
}
function $e(t, n) {
	let r = A(Xe(t())), i = A(null), a = A([]), s = O(() => a.value.length > 0), c = y(!1), l = y(!1), u = y(""), d = !1, f, m;
	function h() {
		f?.abort(), f = void 0, m = void 0, l.value = !1;
	}
	function g(e) {
		return e.cursor === r.value.cursor && Ye.every((t) => e[t] === r.value[t]) ? !1 : (h(), r.value = e, i.value = null, u.value = "", !0);
	}
	function _(e = !1, a) {
		if (d || !c.value || t().view !== "list") return Promise.resolve();
		if (m) return m;
		let o = new AbortController();
		return f = o, l.value = !0, m = (async () => {
			try {
				let t = await n.api.request(`/batches?${Qe(r.value)}`, {
					method: "GET",
					signal: o.signal
				});
				if (o.signal.aborted || a && !a()) return;
				let s = i.value, c = Je(t);
				i.value = c, u.value = "", e && s && (s.items.length !== c.items.length || s.items.some((e, t) => e.id !== c.items[t]?.id)) && n.callbacks.notify?.("批次列表已更新");
			} catch (e) {
				if (o.signal.aborted || e instanceof Error && e.name === "AbortError") return;
				u.value = e instanceof Error ? e.message : "读取批次失败，请重试", e instanceof Error && "status" in e && e.status === 401 && !u.value.includes("登录") && (u.value += "，请重新登录后返回");
			}
		})().finally(() => {
			f === o && (f = void 0, m = void 0, l.value = !1);
		}), m;
	}
	function v(e) {
		return g(Xe({
			...r.value,
			...e
		})), n.callbacks.updateNavigation(e), _();
	}
	function b(e) {
		return a.value = [], v({
			...e,
			cursor: ""
		});
	}
	function x() {
		if (!c.value || l.value || !i.value?.nextCursor) return;
		let e = i.value.nextCursor;
		return a.value = [...a.value, r.value.cursor || ""], v({ cursor: e });
	}
	function S() {
		let e = a.value;
		if (c.value && !l.value && e.length) return a.value = e.slice(0, -1), v({ cursor: e[e.length - 1] });
	}
	function C() {
		if (c.value && !l.value && r.value.cursor) return a.value = [], v({ cursor: "" });
	}
	function w(e) {
		c.value = e, e || h();
	}
	return o(t, (e) => {
		e.view === "list" ? g(Xe(e)) && (a.value = [], c.value && _()) : h();
	}, { deep: !0 }), p(() => {
		d = !0, h();
	}), {
		navigation: e(r),
		items: O(() => i.value?.items ?? []),
		summary: O(() => i.value?.summary ?? {}),
		nextCursor: O(() => i.value?.nextCursor ?? null),
		loading: e(l),
		visible: e(c),
		error: e(u),
		hasPrevious: s,
		stale: O(() => !i.value),
		refresh: _,
		setVisible: w,
		applyFilters: b,
		next: x,
		previous: S,
		first: C,
		resetFilters: () => b({
			q: "",
			operation: "",
			state: "",
			created_from: "",
			created_to: ""
		})
	};
}
// src/features/bulk/BulkList.vue?vue&type=script&setup=true&lang.ts
var et = ["aria-busy"], tt = {
	key: 0,
	class: "bl-kpis"
}, nt = { class: "bl-toolbar" }, rt = { class: "bl-toolbar-main" }, it = {
	class: "bl-count",
	role: "status"
}, at = {
	key: 1,
	class: "bl-error",
	role: "alert"
}, ot = ["disabled"], st = ["disabled"], ct = ["disabled"], lt = { class: "bl-table" }, ut = { class: "bl-col-name" }, dt = { class: "list-filter-actions" }, ft = { class: "list-filter-options" }, pt = { class: "list-filter-option" }, mt = ["checked"], ht = [
	"value",
	"checked",
	"onChange"
], gt = { class: "list-filter-options" }, _t = { class: "list-filter-option" }, vt = ["checked"], yt = [
	"value",
	"checked",
	"onChange"
], bt = { class: "bl-filter-fields" }, xt = ["value"], St = ["value"], Ct = { class: "list-filter-actions" }, wt = ["data-bulk-row"], Tt = { class: "bl-col-name" }, Et = [
	"disabled",
	"title",
	"onClick"
], Dt = ["title"], Ot = { "data-bulk-progress": "" }, kt = { class: "bl-progress-copy" }, At = [
	"value",
	"max",
	"aria-label"
], jt = {
	key: 1,
	class: "bl-secondary"
}, Mt = { class: "bl-results" }, Nt = ["disabled", "onClick"], Pt = ["disabled", "onClick"], Ft = { class: "bl-date" }, It = ["disabled", "onClick"], Lt = { key: 0 }, Rt = { colspan: "7" }, zt = {
	class: "bl-empty",
	role: "status"
}, Bt = /*#__PURE__*/ F(/* @__PURE__ */ n({
	__name: "BulkList",
	props: {
		navigation: {},
		deps: {}
	},
	setup(e, { expose: t }) {
		let n = e, r = $e(() => n.navigation, n.deps), { navigation: l, items: u, summary: f, nextCursor: p, loading: h, visible: g, error: v, hasPrevious: C, stale: w } = r, T = y(null), k = y(""), A = y(), M = {
			plan_check: "查询套餐",
			token_refresh: "刷新 AT",
			password_setup: "补密码",
			twofa_setup: "补 2FA",
			codex_retry: "补 Codex",
			account_completion: "组合补全"
		}, N = {
			active: "执行中",
			paused: "已暂停",
			cancel_requested: "取消中",
			stop_requested: "停止中",
			ended: "已结束"
		}, F = {
			...N,
			settling: "汇总中",
			completed: "已完成",
			preparing: "准备中"
		}, I = [
			"success",
			"partial_success",
			"failed",
			"not_executed",
			"cancelled"
		], z = [
			"attention_required",
			"request_unknown",
			"manual_reconcile",
			"unknown",
			"unconfirmed"
		];
		function B(e) {
			return e && typeof e == "object" && !Array.isArray(e) ? e : {};
		}
		function V(e) {
			return typeof e == "number" && Number.isFinite(e) && e >= 0 ? e : null;
		}
		function H(e, t = "—") {
			return e == null || e === "" ? t : String(e);
		}
		let U = O(() => u.value.map((e) => {
			let t = B(e.summary ?? e.counts), r = {};
			for (let [e, n] of Object.entries(t)) V(n) !== null && (r[e] = n);
			let i = V(e.target_count), a = i === 0 || Object.keys(r).length > 0;
			for (let e of z) e in r && (r.failed = (r.failed || 0) + r[e], delete r[e]);
			let o = B(e.control), s = B(e.operation), c = o.paused ?? e.is_paused ? "paused" : H(o.state ?? e.control_state ?? e.state, "preparing"), l = H(s.key ?? e.operation_key ?? e.action_key), u = e.id, d = a ? I.reduce((e, t) => e + (r[t] || 0), 0) : null, f = i === null || d === null ? null : i === 0 ? 0 : Math.min(100, Math.round(100 * d / i));
			return {
				id: u,
				name: H(e.name ?? e.title, `批次 #${u}`),
				operation: M[l] || l,
				state: c,
				status: F[c] || c,
				counts: r,
				known: a,
				done: d,
				total: i,
				percent: f,
				createdAt: n.deps.callbacks.formatDateTime(e.created_at)
			};
		})), W = O(() => V(f.value.total_batches)), ee = O(() => w.value ? h.value ? "正在读取批次数量…" : "批次数量未知" : W.value === null ? `本页 ${u.value.length} 个批次` : `${W.value.toLocaleString()} 个批次`), G = O(() => {
			let e = [
				{
					key: "active_batches",
					label: "执行中",
					value: V(f.value.active_batches),
					unit: "批"
				},
				{
					key: "ended_batches",
					label: "已结束",
					value: V(f.value.ended_batches),
					unit: "批"
				},
				{
					key: "failed_targets",
					label: "失败账号",
					value: V(f.value.failed_targets),
					unit: "个"
				}
			], t = V(f.value.attention_targets);
			return t != null && e[2].value != null && (e[2].value += t), e.filter((e) => e.value !== null);
		}), K = O(() => {
			let e = l.value;
			return [
				["q", e.q ? `批次：${e.q}` : ""],
				["operation", e.operation ? `操作：${M[e.operation] || e.operation}` : ""],
				["state", e.state ? `状态：${N[e.state] || e.state}` : ""],
				["date", e.created_from || e.created_to ? `创建日期：${e.created_from || "不限"} 至 ${e.created_to || "不限"}` : ""]
			].filter(([, e]) => e).map(([e, t]) => ({
				key: e,
				label: t,
				removeLabel: `移除${t}`
			}));
		});
		o(() => l.value.q, (e) => {
			k.value = e || "";
		}, { immediate: !0 }), o(() => n.navigation.view, () => {
			T.value = null;
		});
		function q(e) {
			e === "date" ? r.applyFilters({
				created_from: "",
				created_to: ""
			}) : r.applyFilters({ [e]: "" });
		}
		function J(e, t) {
			r.applyFilters({ [e]: t });
		}
		function re() {
			r.applyFilters({ q: k.value.trim() }), T.value = null;
		}
		function ie(e, t) {
			g.value && !w.value && n.deps.callbacks.navigate("detail", {
				batch_id: e,
				...t ? { result_state: t } : {}
			});
		}
		function Y(e) {
			g.value && !w.value && n.deps.callbacks.navigate("detail", { batch_id: e }, !0);
		}
		function ae() {
			let e = window.getSelection();
			return w.value || !(e?.toString() && A.value?.contains(e.anchorNode));
		}
		async function oe(e = !1) {
			ae() && await r.refresh(e, ae);
		}
		function se(e) {
			e || (T.value = null), r.setVisible(e);
		}
		return t({
			refresh: oe,
			setVisible: se
		}), (t, n) => (i(), L("section", {
			class: "bl-root",
			"aria-label": "批次列表",
			"aria-busy": P(h)
		}, [
			G.value.length ? (i(), L("div", tt, [(i(!0), L(_, null, c(G.value, (e) => (i(), L("div", {
				key: e.key,
				class: D(["bl-kpi", { "is-warning": e.key === "failed_targets" && !!e.value }])
			}, [S("span", null, b(e.label), 1), S("strong", null, [R(b(e.value), 1), S("small", null, b(e.unit), 1)])], 2))), 128))])) : m("", !0),
			S("div", nt, [S("div", rt, [S("span", it, b(ee.value), 1), d(ne, {
				items: K.value,
				onRemove: q
			}, null, 8, ["items"])]), K.value.length ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "bl-link",
				onClick: n[0] ||= (...e) => P(r).resetFilters && P(r).resetFilters(...e)
			}, "清除筛选")) : m("", !0)]),
			P(v) ? (i(), L("div", at, [
				S("span", null, b(P(v)), 1),
				S("button", {
					type: "button",
					class: "bl-link",
					disabled: P(h),
					onClick: n[1] ||= (e) => P(r).refresh()
				}, "重试", 8, ot),
				P(w) && P(l).cursor ? (i(), L("button", {
					key: 0,
					class: "bl-link",
					type: "button",
					disabled: P(h),
					onClick: n[2] ||= (...e) => P(r).first && P(r).first(...e)
				}, " 返回首页", 8, st)) : m("", !0),
				P(w) && P(C) ? (i(), L("button", {
					key: 1,
					class: "bl-link",
					type: "button",
					disabled: P(h),
					onClick: n[3] ||= (...e) => P(r).previous && P(r).previous(...e)
				}, " 上一页 ", 8, ct)) : m("", !0)
			])) : m("", !0),
			S("div", {
				ref_key: "tableHost",
				ref: A,
				class: "bl-table-wrap",
				tabindex: "0",
				role: "region",
				"aria-label": "批次列表内容"
			}, [S("table", lt, [S("thead", null, [S("tr", null, [
				S("th", ut, [d(te, {
					label: "批次名称或编号",
					"trigger-label": "批次",
					active: !!P(l).q,
					summary: P(l).q,
					open: T.value === "q",
					"onUpdate:open": n[6] ||= (e) => T.value = e ? "q" : null
				}, {
					default: a(() => [S("form", {
						class: "bl-filter-fields",
						onSubmit: E(re, ["prevent"])
					}, [S("label", null, [n[16] ||= R("名称或批次号", -1), s(S("input", {
						"onUpdate:modelValue": n[4] ||= (e) => k.value = e,
						type: "search",
						placeholder: "搜索批次名称或编号",
						autocomplete: "off"
					}, null, 512), [[j, k.value]])]), S("div", dt, [S("button", {
						type: "button",
						onClick: n[5] ||= (e) => q("q")
					}, "清除此列"), n[17] ||= S("button", {
						class: "list-filter-primary",
						type: "submit"
					}, "查询", -1)])], 32)]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				S("th", null, [d(te, {
					label: "操作类型",
					active: !!P(l).operation,
					summary: M[P(l).operation || ""] || P(l).operation,
					open: T.value === "operation",
					"onUpdate:open": n[8] ||= (e) => T.value = e ? "operation" : null
				}, {
					default: a(() => [S("fieldset", ft, [
						n[19] ||= S("legend", { class: "bl-sr-only" }, "操作类型", -1),
						S("label", pt, [S("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: "",
							checked: !P(l).operation,
							onChange: n[7] ||= (e) => J("operation", "")
						}, null, 40, mt), n[18] ||= R("全部操作", -1)]),
						(i(), L(_, null, c(M, (e, t) => S("label", {
							class: "list-filter-option",
							key: t
						}, [S("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: t,
							checked: P(l).operation === t,
							onChange: (e) => J("operation", t)
						}, null, 40, ht), R(b(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				S("th", null, [d(te, {
					label: "状态",
					active: !!P(l).state,
					summary: N[P(l).state || ""] || P(l).state,
					open: T.value === "state",
					"onUpdate:open": n[10] ||= (e) => T.value = e ? "state" : null
				}, {
					default: a(() => [S("fieldset", gt, [
						n[21] ||= S("legend", { class: "bl-sr-only" }, "运行状态", -1),
						S("label", _t, [S("input", {
							type: "radio",
							name: "bulk-list-state",
							value: "",
							checked: !P(l).state,
							onChange: n[9] ||= (e) => J("state", "")
						}, null, 40, vt), n[20] ||= R("全部状态", -1)]),
						(i(), L(_, null, c(N, (e, t) => S("label", {
							class: "list-filter-option",
							key: t
						}, [S("input", {
							type: "radio",
							name: "bulk-list-state",
							value: t,
							checked: P(l).state === t,
							onChange: (e) => J("state", t)
						}, null, 40, yt), R(b(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				n[24] ||= S("th", null, "完成进度", -1),
				n[25] ||= S("th", null, "当前结果", -1),
				S("th", null, [d(te, {
					label: "创建时间",
					active: !!(P(l).created_from || P(l).created_to),
					summary: `${P(l).created_from || "不限"} 至 ${P(l).created_to || "不限"}`,
					open: T.value === "date",
					"onUpdate:open": n[14] ||= (e) => T.value = e ? "date" : null
				}, {
					default: a(() => [S("div", bt, [
						S("label", null, [n[22] ||= R("开始日期", -1), S("input", {
							type: "date",
							value: P(l).created_from,
							onChange: n[11] ||= (e) => J("created_from", e.target.value)
						}, null, 40, xt)]),
						S("label", null, [n[23] ||= R("截止日期", -1), S("input", {
							type: "date",
							value: P(l).created_to,
							onChange: n[12] ||= (e) => J("created_to", e.target.value)
						}, null, 40, St)]),
						S("div", Ct, [S("button", {
							type: "button",
							onClick: n[13] ||= (e) => q("date")
						}, "清除此列")])
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				n[26] ||= S("th", null, [S("span", { class: "bl-sr-only" }, "操作")], -1)
			])]), S("tbody", null, [(i(!0), L(_, null, c(U.value, (e) => (i(), L("tr", {
				key: e.id,
				"data-bulk-row": e.id
			}, [
				S("td", Tt, [S("button", {
					type: "button",
					class: "bl-name",
					"data-bulk-open": "",
					disabled: P(w),
					title: e.name,
					onClick: (t) => ie(e.id)
				}, b(e.name), 9, Et), S("span", {
					class: "bl-secondary",
					title: `批次 #${e.id}`
				}, "#" + b(e.id), 9, Dt)]),
				S("td", null, b(e.operation), 1),
				S("td", null, [S("span", { class: D(["bl-status", `is-${e.state}`]) }, b(e.status), 3)]),
				S("td", Ot, [e.total !== null && e.done !== null ? (i(), L(_, { key: 0 }, [S("span", kt, [R(b(e.done) + " / " + b(e.total) + " ", 1), S("span", null, b(e.percent) + "%", 1)]), S("progress", {
					value: e.done,
					max: Math.max(1, e.total),
					"aria-label": `已结束 ${e.done} 个，共 ${e.total} 个`
				}, null, 8, At)], 64)) : (i(), L("span", jt, b(e.total === null ? "名单准备中" : "结果待汇总"), 1))]),
				S("td", null, [S("div", Mt, [S("button", {
					type: "button",
					class: "bl-result is-success",
					"data-bulk-result": "success",
					disabled: P(w) || !e.counts.success,
					onClick: (t) => ie(e.id, "success")
				}, " 成功 " + b(e.known ? e.counts.success || 0 : "—"), 9, Nt), S("button", {
					type: "button",
					class: "bl-result is-failed",
					"data-bulk-result": "failed",
					disabled: P(w) || !e.counts.failed,
					onClick: (t) => ie(e.id, "failed")
				}, " 失败 " + b(e.known ? e.counts.failed || 0 : "—"), 9, Pt)])]),
				S("td", Ft, b(e.createdAt), 1),
				S("td", null, [S("button", {
					type: "button",
					class: "bl-button",
					"data-bulk-report": "",
					disabled: P(w),
					onClick: (t) => Y(e.id)
				}, " 查看报告 ", 8, It)])
			], 8, wt))), 128)), U.value.length ? m("", !0) : (i(), L("tr", Lt, [S("td", Rt, [S("div", zt, [S("strong", null, b(P(h) ? "正在加载批次…" : P(v) ? "暂时无法读取批次" : K.value.length ? "没有匹配的批次" : "还没有批次"), 1), !P(h) && !P(v) ? (i(), L(_, { key: 0 }, [n[27] ||= S("p", null, "选择操作和账号范围，即可集中执行与追踪结果。", -1), S("button", {
				type: "button",
				class: "bl-button",
				"data-bulk-create": "",
				onClick: n[15] ||= (t) => e.deps.callbacks.navigate("create")
			}, " 新建批次 ")], 64)) : m("", !0)])])]))])])], 512),
			P(w) ? m("", !0) : (i(), x(Ke, {
				key: 2,
				"has-previous": P(C),
				"next-cursor": P(p),
				"item-count": P(u).length,
				"has-cursor": !!P(l).cursor,
				busy: P(h),
				label: "批次分页",
				onPrevious: P(r).previous,
				onNext: P(r).next,
				onFirst: P(r).first
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
		], 8, et));
	}
}), [["__scopeId", "data-v-94cf2848"]]), Vt = class extends Error {
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
function Ht(e = fetch) {
	return { async request(t, n = {}) {
		if (!t.startsWith("/") || t.startsWith("//")) throw Error("批量接口路径无效");
		let r = await e("/api/bulk" + t, {
			credentials: "same-origin",
			...n
		}), i = r.headers?.get("content-type");
		if (i && !i.includes("application/json")) throw new Vt(r.status === 401 || r.redirected ? "登录已失效，请重新登录后返回。" : "服务返回了非 JSON 响应", r.status);
		let a = await r.json().catch(() => null), o = a && typeof a == "object" && !Array.isArray(a) ? a : {};
		if (!r.ok || o.ok === !1) {
			let e = o.error && typeof o.error == "object" && !Array.isArray(o.error) ? o.error : o, t = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {};
			throw new Vt(String(e.message || (typeof o.error == "string" ? o.error : "") || `请求失败（HTTP ${r.status}）`), r.status, String(e.code || o.code || ""), t(e.details || o.details), typeof e.field == "string" ? e.field : null, t(e.fields || o.fields), typeof o.request_id == "string" ? o.request_id : void 0, typeof e.retryable == "boolean" ? e.retryable : void 0);
		}
		if (typeof a != "object" || !a || Array.isArray(a) || o.ok === !0 && (!o.data || typeof o.data != "object" || Array.isArray(o.data))) throw new Vt("服务返回了无效 JSON 响应", r.status);
		return o.data ?? o;
	} };
}
// src/features/bulk/useBulkCreate.ts
var Ut = "turb_bulk_draft_v1", Wt = "turb_bulk_selection_v1", Gt = (e) => JSON.parse(JSON.stringify(e)), Kt = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {};
function qt(e) {
	let t = () => ({
		name: "",
		operation_key: "plan_check",
		query: e.adapter.normalize(),
		source: null,
		parameters: {},
		max_concurrency: 3
	}), n = (t) => {
		try {
			return JSON.parse(e.storage.getItem(t) || "null");
		} catch {
			return null;
		}
	}, r = y(t()), i = y(null), a = y(null), o = y({}), s = y(null), c = y(!1), l = y(!1), u = y(!1), d = y(""), f = y(""), m = y(""), h = y(0), g = /* @__PURE__ */ new Map(), _ = /* @__PURE__ */ new Set(), v = 0, b = !1, x = !0, S = !1, C = null, w = null, T = null, E = null, D, k = O(() => a.value?.operations || []), A = O(() => k.value.find((e) => e.key === r.value.operation_key)), j = O(() => String(A.value?.effective_settings?.config_revision ?? A.value?.config_revision ?? a.value?.config_revision ?? "")), M = O(() => i.value?.state || i.value?.status || ""), N = O(() => M.value === "preparing"), P = O(() => Number(a.value?.limits?.concurrency_max) || 128), F = O(() => {
		h.value;
		try {
			return e.intents.pending().length;
		} catch {
			return 1;
		}
	}), I = O(() => M.value === "ready" ? Number(i.value?.target_count ?? i.value?.total_count) : r.value.source?.kind === "ids" ? r.value.source.ids.length : r.value.source ? null : s.value), L = O(() => r.value.source?.kind === "ids" ? `已选 ${r.value.source.ids.length} 个账号` : r.value.source?.kind === "batch_targets" ? `批次 #${r.value.source.batch_id} 的固定名单` : r.value.query.filters.email ? `邮箱含「${r.value.query.filters.email}」` : "按当前筛选"), R = O(() => l.value ? "正在固定账号范围…" : M.value === "ready" ? "账号范围已固定" : I.value === 0 ? "没有匹配账号" : "匹配账号数量"), z = O(() => l.value ? "正在准备本批次，请稍候" : M.value === "ready" ? "将使用这份固定名单创建批次" : I.value === 0 ? "请调整账号筛选条件" : r.value.source?.kind === "batch_targets" ? "创建时沿用原批次固定名单" : r.value.source?.kind === "ids" ? "将使用已选账号创建批次" : s.value == null ? "正在统计，创建时会核对最终数量" : `当前条件匹配 ${s.value} 个账号，将全部执行`), B = O(() => A.value?.availability?.available === !1 ? `当前设置不可用：${A.value.availability.reason || Kt(A.value.availability).reason_code || "请检查配置"}。请到配置页调整。` : "");
	function V() {
		try {
			e.storage.setItem(Ut, JSON.stringify(r.value));
		} catch {}
	}
	function H() {
		try {
			i.value ? e.storage.setItem(Wt, JSON.stringify(i.value)) : e.storage.removeItem(Wt);
		} catch {}
	}
	function U(e) {
		return [e?.request_parameters, e?.parameters].some((e) => Object.keys(e || {}).some((e) => e !== "timezone_offset_min" || r.value.operation_key !== "plan_check"));
	}
	function W(n) {
		let r = Kt(n), i = e.adapter.normalize(Kt(r.query)), a = r.source && typeof r.source == "object" ? Gt(r.source) : null;
		return {
			limited: !a && !!(r.limit || i.limit),
			draft: {
				...t(),
				name: String(r.name || ""),
				operation_key: String(r.operation_key || "plan_check"),
				query: e.adapter.normalize({
					...i,
					limit: null
				}),
				source: a,
				parameters: {},
				max_concurrency: Number(r.max_concurrency ?? 3)
			}
		};
	}
	function ee(e, t) {
		let n = W(e);
		r.value = n.draft;
		let a = Kt(t);
		i.value = typeof a.id == "string" ? Gt(a) : null, (n.limited || U(i.value)) && (i.value = null), V(), H();
	}
	ee(n(Ut), n(Wt));
	function G() {
		d.value = "", f.value = "", m.value = "";
	}
	function K(e, t = "") {
		let n = e;
		d.value = t + (n.message || String(e)) + (n.code ? `（${n.code}）` : "") + (n.status === 401 ? "，请重新登录后返回，草稿与请求身份已保留。" : ""), f.value = n.field || "";
	}
	let q = (e) => Kt(e).name === "AbortError";
	function J(e) {
		x = e, e || (clearTimeout(D), _.forEach((e) => e.abort()));
	}
	async function te(t) {
		let n = new AbortController();
		_.add(n);
		try {
			let r = await e.api.request(t, { signal: n.signal });
			if (n.signal.aborted) throw new DOMException("读取已取消", "AbortError");
			return r;
		} finally {
			_.delete(n);
		}
	}
	async function ne(e = !1) {
		if (a.value && !e) return;
		let t = await te("/catalog");
		b || (a.value = t, k.value.some((e) => e.key === r.value.operation_key) || (r.value.operation_key = k.value[0]?.key || "", i.value = null, H(), V()));
	}
	async function re() {
		if (!x || b) return;
		let t = v, n = JSON.stringify(e.adapter.normalize(r.value.query)), i = g.get(n);
		if (i && e.now() - i.at < 3e4) {
			o.value = i.facets, s.value = i.matched;
			return;
		}
		s.value = null;
		let a = await te(`/query-facets?query=${encodeURIComponent(n)}`), c = Kt(a.facets || a), l = a.matched == null ? null : Number(a.matched);
		g.set(n, {
			facets: c,
			matched: l,
			at: e.now()
		}), g.size > 10 && g.delete(g.keys().next().value), !b && t === v && n === JSON.stringify(e.adapter.normalize(r.value.query)) && (o.value = c, s.value = l);
	}
	function ie() {
		if (clearTimeout(D), !x) return;
		let e = v;
		D = setTimeout(() => {
			re().catch((t) => {
				!q(t) && !b && e === v && K(t, "筛选选项更新失败：");
			});
		}, 350);
	}
	function Y() {
		v++, E = null, l.value = !1, i.value = null, H();
	}
	function ae(e) {
		Y(), clearTimeout(D), ee(Gt(e), null), s.value = null, G(), S && ie();
	}
	function se(e, t) {
		l.value || (e === "name" ? r.value.name = String(t) : r.value.max_concurrency = Number(t), V());
	}
	function de(e) {
		l.value || r.value.operation_key === e || (r.value.operation_key = e, Y(), G(), V());
	}
	function fe(t) {
		if (l.value) return;
		let n = e.adapter.normalize({
			...t,
			limit: null
		});
		JSON.stringify(n) !== JSON.stringify(r.value.query) && (r.value.query = n, s.value = null, Y(), G(), V(), ie());
	}
	function pe(e, t) {
		let n = Gt(r.value.query);
		[
			"q",
			"archived",
			"date_from",
			"date_to",
			"plan"
		].includes(e) ? Object.assign(n, { [e]: t }) : Object.assign(n.filters, { [e]: t }), fe(n);
	}
	function me(e) {
		e === "date" ? fe({
			...r.value.query,
			date_from: "",
			date_to: ""
		}) : pe(e, e === "archived" ? "0" : [
			"q",
			"email",
			"id"
		].includes(e) ? "" : []);
	}
	function he() {
		l.value || (r.value.source = null, r.value.query = e.adapter.normalize(), s.value = null, Y(), G(), V(), ie());
	}
	function ge(t, n) {
		return e.callbacks.facetLabel?.(t, n) || n;
	}
	function _e(e) {
		let t = a.value?.query_schema?.fields, n = Array.isArray(t) ? t.map(Kt).find((t) => t.key === e) : void 0, i = n?.options ?? n?.enum ?? n?.values, s = o.value[e] ?? (Array.isArray(i) ? i : []), c = /* @__PURE__ */ new Map();
		for (let t of s) {
			let n = typeof t == "object" && t ? t : { value: String(t) };
			n.value && c.set(n.value, {
				...n,
				label: n.label || ge(e === "token" ? "account_token" : e, n.value)
			});
		}
		if (e === "promotion") for (let t of le) c.has(t) || c.set(t, {
			value: t,
			label: ge(e, t)
		});
		for (let t of ue(r.value.query, e)) c.has(t) || c.set(t, {
			value: t,
			label: ge(e === "token" ? "account_token" : e, t)
		});
		return [...c.values()];
	}
	let ve = O(() => [
		...oe(r.value.query, ge),
		...r.value.query.q ? [{
			key: "q",
			label: `搜索：${r.value.query.q}`,
			removeLabel: "清除高级搜索",
			title: r.value.query.q
		}] : [],
		...r.value.query.archived === "0" ? [] : [{
			key: "archived",
			label: r.value.query.archived === "only" ? "仅归档账号" : "含归档账号",
			removeLabel: "清除归档筛选",
			title: ""
		}]
	]);
	function ye() {
		let e = A.value?.parameter_schema;
		return e?.timezone_offset_min || Kt(e?.properties).timezone_offset_min ? { timezone_offset_min: (/* @__PURE__ */ new Date()).getTimezoneOffset() } : {};
	}
	async function be() {
		if (!i.value || !x || b) return;
		let e = X(i.value.id), t = v, n = await te(`/selections/${encodeURIComponent(e)}?page_size=1`);
		b || t !== v || i.value?.id !== e || (i.value = {
			...i.value,
			...n
		}, H());
	}
	async function xe() {
		if (x && !b) {
			if (C) return C;
			if (!S) return c.value = !0, C = (async () => {
				try {
					if (await ne(), b || !x) return;
					let e = v;
					try {
						await re();
					} catch (t) {
						if (q(t)) return;
						e === v && K(t, "筛选选项读取失败：");
					}
					!b && e === v && i.value && await be(), S = !0;
				} catch (e) {
					!q(e) && !b && K(e, "读取配置失败：");
				} finally {
					c.value = !1, C = null;
				}
			})(), C;
		}
	}
	async function Se(t, n) {
		if (q(t) || b || n !== v) return;
		E = null, l.value = !1, K(t, "创建失败：");
		let r = t;
		if (["config_revision_changed", "selection_settings_mismatch"].includes(r.code)) {
			i.value = null, H();
			try {
				await ne(!0);
			} catch (e) {
				K(e, "配置读取失败：");
			}
			!b && n === v && e.callbacks.notify("配置已更新，请重新创建批次。");
		} else r.code === "selection_consumed" && r.details?.existing_batch_id ? (m.value = String(r.details.existing_batch_id), e.callbacks.notify(`该范围已用于批次 #${m.value}`)) : r.code === "selection_expired" && (i.value = null, H());
	}
	async function Ce() {
		let t = E;
		if (!t || t.epoch !== v || T === v || b || !x) return;
		let n = v;
		T = n;
		try {
			if (M.value === "preparing") return;
			let a = i.value;
			if (!a || M.value !== "ready") throw new Vt(a?.error?.message || a?.error_detail?.message || "账号范围准备失败，请重试", 0, a?.error_code || "selection_preparation_failed");
			if (Number(a.target_count ?? a.total_count) <= 0) throw new Vt("没有匹配账号，请调整筛选条件", 0, "selection_empty");
			let o = A.value;
			if (!o) throw new Vt("没有可用的批量操作", 0, "operation_unavailable");
			let s = {
				name: r.value.name,
				selection_id: X(a.id),
				selection_revision: a.selection_revision,
				operation: {
					key: o.key,
					version: o.version || 1
				},
				expected_config_revision: a.config_revision || j.value,
				parameters: a.request_parameters || ye(),
				execution: {
					max_concurrency: Number(r.value.max_concurrency),
					start_paused: t.paused
				}
			}, c = await e.intents.submit("create", "/batches", s), u = X(c.id || c.batch_id);
			if (b || n !== v) {
				e.callbacks.notify(`原批次 #${u} 已创建${t.paused ? "并暂停" : ""}`);
				return;
			}
			i.value = null, H(), E = null, l.value = !1, e.callbacks.notify(x ? t.paused ? "批次已创建并暂停，可在详情继续执行" : "批次已受理，正在后台提交目标" : `原批次 #${u} 已创建${t.paused ? "并暂停" : ""}`), x && e.callbacks.navigate("detail", { batch_id: u });
		} catch (e) {
			await Se(e, n);
		} finally {
			h.value++, T === n && (T = null);
		}
	}
	async function we(t = !1) {
		if (l.value || u.value || b || !x) return;
		G();
		let n = Number(r.value.max_concurrency);
		if (!Number.isInteger(n) || n < 1 || n > P.value) {
			K(new Vt(`本批并发上限需为 1–${P.value} 的整数`, 0, "invalid_concurrency", {}, "max_concurrency"));
			return;
		}
		if (r.value.name.length > 120) {
			K(new Vt("批次名称最多 120 个字符", 0, "invalid_name", {}, "name"));
			return;
		}
		if (!A.value) {
			K(new Vt("请先读取可用的批量操作", 0, "operation_unavailable"));
			return;
		}
		U(i.value) && (i.value = null, H());
		let a = v;
		E = {
			epoch: a,
			paused: t
		}, l.value = !0;
		try {
			if (!["ready", "preparing"].includes(M.value)) {
				let t = A.value, n = {
					operation: {
						key: t.key,
						version: t.version || 1
					},
					source: Gt(r.value.source || {
						kind: "query",
						query: e.adapter.normalize({
							...r.value.query,
							limit: null
						})
					}),
					parameters: ye(),
					expected_config_revision: j.value
				}, o = await e.intents.submit("selection", "/selections", n);
				if (b || a !== v) return;
				i.value = {
					...o,
					request_parameters: n.parameters,
					config_revision: n.expected_config_revision
				}, H(), V();
			}
			M.value === "preparing" && await be(), !b && a === v && await Ce();
		} catch (e) {
			await Se(e, a);
		} finally {
			h.value++;
		}
	}
	async function Te(e = !1) {
		if (b || !x) return;
		if (w?.epoch === v) return w.promise;
		let t = v, n = (async () => {
			let n = !S;
			if (n && await xe(), !b && x && S && t === v) try {
				e && await ne(!0), n || (i.value ? await be() : await re()), t === v && await Ce();
			} catch (e) {
				!q(e) && t === v && (E ? await Se(e, t) : K(e, "读取账号范围失败："));
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
	function Ee(n, r) {
		let i = Kt(n.source), a = Kt(n.operation), o = e.adapter.normalize(i.kind === "query" ? Kt(i.query) : {}), s = {
			...t(),
			operation_key: String(a.key || "plan_check"),
			query: o,
			source: i.kind === "query" ? null : i
		};
		Y(), ee(s, {
			...r,
			request_parameters: Kt(n.parameters),
			config_revision: n.expected_config_revision
		});
	}
	async function De() {
		if (u.value || l.value || b) return;
		u.value = !0, G();
		let t = v;
		try {
			let n = e.intents.pending()[0];
			if (!n) return;
			let r = await e.intents.recover(n);
			if (b || t !== v || !x) {
				e.callbacks.notify(n.path === "/batches" ? `原批次 #${X(r.id || r.batch_id)} 已创建` : "原请求回执已找回，当前草稿保留。");
				return;
			}
			if (n.path === "/selections") Ee(n.body, r), e.callbacks.navigate("create"), e.callbacks.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
			else if (n.path === "/batches") i.value = null, H(), e.callbacks.navigate("detail", { batch_id: X(r.id || r.batch_id) });
			else {
				let t = n.path.match(/^\/batches\/(\d+)\//);
				t && e.callbacks.navigate("detail", { batch_id: X(t[1]) }), e.callbacks.notify("原请求回执已找回。");
			}
		} catch (e) {
			K(e, "找回请求失败：");
		} finally {
			u.value = !1, h.value++;
		}
	}
	return p(() => {
		b = !0, v++, clearTimeout(D), _.forEach((e) => e.abort()), _.clear(), E = null;
	}), {
		draft: r,
		selection: i,
		catalog: a,
		facets: o,
		matched: s,
		loading: c,
		creating: l,
		recovering: u,
		error: d,
		errorField: f,
		existingBatchId: m,
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
		chips: ve,
		accountFilters: ce,
		initialize: xe,
		refresh: Te,
		recover: De,
		restoreSelectionRequest: Ee,
		loadFacets: re,
		applySeed: ae,
		setVisible: J,
		setDraftField: se,
		setOperation: de,
		setQueryField: pe,
		clearFilter: me,
		clearFilters: he,
		filterOptions: _e,
		createBatch: we,
		clearError: G
	};
}
// src/features/bulk/BulkCreate.vue?vue&type=script&setup=true&lang.ts
var Jt = {
	key: 0,
	class: "bulk-empty",
	role: "status"
}, Yt = ["aria-busy"], Xt = { class: "bulk-create-main" }, Zt = { class: "bulk-card bulk-create-card" }, Qt = {
	class: "bulk-operation-grid",
	role: "radiogroup",
	"aria-label": "批量操作"
}, $t = ["title"], en = [
	"value",
	"checked",
	"disabled",
	"onChange"
], tn = {
	viewBox: "0 0 24 24",
	fill: "none",
	stroke: "currentColor",
	"stroke-width": "1.6",
	"stroke-linecap": "round",
	"stroke-linejoin": "round",
	"aria-hidden": "true"
}, nn = ["d"], rn = { class: "bulk-card bulk-create-card" }, an = {
	key: 0,
	class: "bulk-error bulk-operation-warning",
	"data-bulk-operation-warning": ""
}, on = { class: "bulk-batch-fields" }, sn = { class: "bulk-field bulk-name-field" }, cn = [
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], ln = { class: "bulk-field" }, un = [
	"max",
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], dn = {
	class: "bulk-card bulk-create-card",
	"data-bulk-account-scope": ""
}, fn = { class: "bulk-step-head" }, pn = ["disabled"], mn = {
	key: 0,
	class: "bulk-source-banner"
}, hn = ["disabled"], gn = { "data-bulk-filters": "" }, _n = { class: "bulk-query-top" }, vn = { class: "bulk-field bulk-query-search" }, yn = ["value", "disabled"], bn = ["open"], xn = { class: "bulk-filter-popover-panel" }, Sn = { class: "bulk-filter-popover-heading" }, Cn = { class: "bulk-field" }, wn = ["value", "disabled"], Tn = { class: "bulk-field" }, En = ["value", "disabled"], Dn = ["open"], On = { class: "bulk-filter-popover-panel" }, kn = { class: "bulk-filter-popover-heading" }, An = { class: "bulk-field" }, jn = ["value", "disabled"], Mn = { class: "bulk-field" }, Nn = ["value", "disabled"], Pn = {
	class: "bulk-column-filters",
	"aria-label": "账号列筛选"
}, Fn = ["data-filter-field", "open"], In = ["onClick"], Ln = {
	key: 0,
	"data-filter-count": ""
}, Rn = { class: "bulk-filter-popover-panel" }, zn = { class: "bulk-filter-popover-heading" }, Bn = ["aria-label"], Vn = {
	key: 0,
	class: "bulk-field"
}, Hn = [
	"data-query-filter",
	"value",
	"disabled",
	"onInput"
], Un = {
	key: 1,
	class: "bulk-filter-options"
}, Wn = [
	"data-query-filter",
	"value",
	"checked",
	"disabled",
	"onChange"
], Gn = {
	key: 0,
	class: "bulk-muted"
}, Kn = {
	class: "bulk-query-chips",
	"data-query-chips": "",
	"aria-label": "已选账号条件"
}, qn = [
	"data-clear-query",
	"aria-label",
	"disabled",
	"onClick"
], Jn = {
	key: 0,
	class: "bulk-filter-empty"
}, Yn = { class: "bulk-card bulk-create-side" }, Xn = { class: "bulk-side-sticky" }, Zn = { class: "bulk-side-heading" }, Qn = { "data-bulk-create-summary": "" }, $n = {
	class: "bulk-side-big",
	"data-bulk-side-count": "",
	role: "status",
	"aria-live": "polite",
	"aria-atomic": "true"
}, er = {
	class: "bulk-side-hint",
	"data-bulk-create-hint": ""
}, tr = { class: "bulk-side-meta" }, nr = { "data-bulk-side-operation": "" }, rr = { "data-bulk-side-scope": "" }, ir = { "data-bulk-side-concurrency": "" }, ar = {
	key: 0,
	class: "bulk-side-warning",
	"data-bulk-side-warning": ""
}, or = {
	key: 1,
	id: "bulkCreateError",
	class: "bulk-error",
	"data-bulk-action-error": "",
	role: "alert"
}, sr = {
	key: 2,
	class: "bulk-notice",
	"data-bulk-recovery": "",
	role: "status"
}, cr = ["disabled"], lr = { class: "bulk-side-actions" }, ur = ["disabled"], dr = ["disabled"], fr = /* @__PURE__ */ n({
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
	setup(e, { expose: n }) {
		let r = e, a = qt(r.deps), { draft: u, loading: d, creating: f, recovering: p, error: h, errorField: v, existingBatchId: x, operations: C, operation: w, concurrencyMax: T, pendingCount: k, count: A, scopeLabel: j, summary: M, hint: F, availabilityWarning: I, chips: z, needsRefresh: B } = a, V = y(), H = y(""), U = O(() => f.value || p.value), W = a.accountFilters.filter((e) => !["email", "date"].includes(e.key)), ee = {
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
			let r = new Set(ue(u.value.query, e));
			n ? r.add(t) : r.delete(t), a.setQueryField(e, [...r]);
		}
		function J(e) {
			let t = (e?.target)?.closest("details");
			H.value = "", (t?.querySelector("summary"))?.focus();
		}
		function te(e, t) {
			if (U.value) return;
			if (H.value === e) {
				H.value = "";
				return;
			}
			let n = t.currentTarget, r = n.nextElementSibling, i = n.getBoundingClientRect().left, a = Math.min(250, window.innerWidth - 48), o = Math.max(10, document.querySelector("main")?.getBoundingClientRect().left ?? 0), s = Math.max(o, Math.min(i, document.documentElement.clientWidth - a - 10));
			r.style.setProperty("--bulk-filter-offset", `${s - i}px`), H.value = e;
		}
		function ne(e) {
			let t = e.target.closest("details");
			t && !t.contains(e.relatedTarget) && (H.value = "");
		}
		return o(() => r.seed, (e) => {
			e && a.applySeed(e);
		}, { immediate: !0 }), o(() => r.visible, (e) => {
			a.setVisible(e), e || (H.value = "");
		}, { immediate: !0 }), o(v, async (e) => {
			e && (await t(), Array.from(V.value?.querySelectorAll("[name],[data-query],[data-query-filter]") || []).find((t) => (t.name || t.dataset.query || t.dataset.queryFilter) === e)?.focus({ preventScroll: !0 }));
		}), l(() => {
			r.visible && a.initialize();
		}), n({
			refresh: a.refresh,
			recover: a.recover,
			restoreSelectionRequest: a.restoreSelectionRequest,
			setVisible: a.setVisible,
			needsRefresh: B
		}), (t, n) => P(d) && !P(C).length ? (i(), L("div", Jt, "正在读取操作和筛选配置…")) : (i(), L("form", {
			key: 1,
			ref_key: "form",
			ref: V,
			"data-bulk-create-form": "",
			class: "bulk-create-form",
			novalidate: "",
			"aria-busy": U.value,
			onSubmit: n[18] ||= E((e) => P(a).createBatch(), ["prevent"]),
			onKeydown: n[19] ||= g((e) => J(e), ["esc"])
		}, [S("div", Xt, [
			S("section", Zt, [n[21] ||= S("div", { class: "bulk-step-head" }, [S("span", { class: "bulk-step-no" }, "1"), S("div", null, [S("h3", null, "选择操作"), S("p", { class: "bulk-section-note" }, "本次要对账号做什么")])], -1), S("div", Qt, [(i(!0), L(_, null, c(P(C), (e) => (i(), L("label", {
				key: e.key,
				class: "bulk-operation",
				title: e.availability?.available === !1 ? e.availability.reason || "当前不可用" : ""
			}, [
				S("input", {
					type: "radio",
					name: "operation_key",
					value: e.key,
					checked: P(u).operation_key === e.key,
					disabled: U.value,
					required: "",
					onChange: (t) => P(a).setOperation(e.key)
				}, null, 40, en),
				(i(), L("svg", tn, [S("path", { d: G[e.key] || G.account_completion }, null, 8, nn)])),
				S("span", null, [S("strong", null, b(e.label || e.key), 1), S("small", null, b(ee[e.key] || "批量账号操作"), 1)]),
				n[20] ||= S("span", {
					class: "bulk-operation-check",
					"aria-hidden": "true"
				}, "✓", -1)
			], 8, $t))), 128))])]),
			S("section", rn, [
				n[24] ||= S("div", { class: "bulk-step-head" }, [S("span", { class: "bulk-step-no" }, "2"), S("div", null, [S("h3", null, "批次设置")])], -1),
				P(I) ? (i(), L("p", an, b(P(I)), 1)) : m("", !0),
				S("div", on, [S("label", sn, [n[22] ||= R("批次名称", -1), S("input", {
					name: "name",
					maxlength: "120",
					value: P(u).name,
					placeholder: "留空自动命名",
					disabled: U.value,
					"aria-invalid": P(v) === "name" || void 0,
					"aria-describedby": P(v) === "name" ? "bulkCreateError" : void 0,
					onInput: n[0] ||= (e) => P(a).setDraftField("name", K(e))
				}, null, 40, cn)]), S("label", ln, [n[23] ||= R("本批并发上限", -1), S("input", {
					name: "max_concurrency",
					type: "number",
					min: "1",
					max: P(T),
					step: "1",
					value: P(u).max_concurrency,
					required: "",
					disabled: U.value,
					"aria-invalid": P(v) === "max_concurrency" || void 0,
					"aria-describedby": P(v) === "max_concurrency" ? "bulkCreateError" : void 0,
					onInput: n[1] ||= (e) => P(a).setDraftField("max_concurrency", K(e))
				}, null, 40, un)])])
			]),
			S("section", dn, [
				S("div", fn, [
					n[25] ||= S("span", { class: "bulk-step-no" }, "3", -1),
					n[26] ||= S("div", null, [S("h3", null, "账号范围"), S("p", { class: "bulk-section-note" }, "与账号列表使用同一套筛选")], -1),
					S("button", {
						type: "button",
						class: "bulk-link",
						"data-bulk-action": "clear-filters",
						disabled: U.value,
						onClick: n[2] ||= (...e) => P(a).clearFilters && P(a).clearFilters(...e)
					}, "清空条件", 8, pn)
				]),
				P(u).source ? (i(), L("div", mn, [S("span", null, b(P(u).source.kind === "ids" ? "使用已选账号" : `沿用批次 #${P(u).source.batch_id} 的账号名单`), 1), S("button", {
					type: "button",
					class: "bulk-link",
					"data-bulk-action": "use-query",
					disabled: U.value,
					onClick: n[3] ||= (...e) => P(a).clearFilters && P(a).clearFilters(...e)
				}, "改为按条件筛选", 8, hn)])) : m("", !0),
				s(S("div", gn, [
					S("div", _n, [
						S("label", vn, [n[27] ||= S("span", { class: "bulk-sr-only" }, "邮箱或姓名", -1), S("input", {
							"data-query": "email",
							type: "search",
							value: P(u).query.filters.email,
							autocomplete: "off",
							placeholder: "搜索邮箱或姓名",
							disabled: U.value,
							onInput: n[4] ||= (e) => P(a).setQueryField("email", K(e))
						}, null, 40, yn)]),
						S("details", {
							class: "bulk-filter-popover",
							"data-filter-dates": "",
							open: H.value === "date",
							onFocusout: ne
						}, [S("summary", { onClick: n[5] ||= E((e) => te("date", e), ["prevent"]) }, [...n[28] ||= [R("创建日期", -1), S("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [S("path", { d: "m4 6 4 4 4-4" })], -1)]]), S("div", xn, [
							S("div", Sn, [n[29] ||= S("strong", null, "创建日期", -1), S("button", {
								type: "button",
								"aria-label": "关闭创建日期筛选",
								onClick: n[6] ||= (e) => J(e)
							}, "完成")]),
							S("label", Cn, [n[30] ||= R("创建日期从", -1), S("input", {
								"data-query": "date_from",
								type: "date",
								value: P(u).query.date_from,
								disabled: U.value,
								onInput: n[7] ||= (e) => P(a).setQueryField("date_from", K(e))
							}, null, 40, wn)]),
							S("label", Tn, [n[31] ||= R("创建日期至（含当天）", -1), S("input", {
								"data-query": "date_to",
								type: "date",
								value: P(u).query.date_to,
								disabled: U.value,
								onInput: n[8] ||= (e) => P(a).setQueryField("date_to", K(e))
							}, null, 40, En)])
						])], 40, bn),
						S("details", {
							class: "bulk-filter-popover",
							open: H.value === "more",
							onFocusout: ne
						}, [S("summary", { onClick: n[9] ||= E((e) => te("more", e), ["prevent"]) }, [...n[32] ||= [R("更多查询", -1), S("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [S("path", { d: "m4 6 4 4 4-4" })], -1)]]), S("div", On, [
							S("div", kn, [n[33] ||= S("strong", null, "更多查询", -1), S("button", {
								type: "button",
								"aria-label": "关闭更多查询筛选",
								onClick: n[10] ||= (e) => J(e)
							}, "完成")]),
							S("label", An, [n[34] ||= R("高级搜索", -1), S("input", {
								"data-query": "q",
								type: "search",
								value: P(u).query.q,
								placeholder: "如：协议 jp",
								autocomplete: "off",
								disabled: U.value,
								onInput: n[11] ||= (e) => P(a).setQueryField("q", K(e))
							}, null, 40, jn)]),
							S("label", Mn, [n[36] ||= R("归档范围", -1), S("select", {
								"data-query": "archived",
								value: P(u).query.archived,
								disabled: U.value,
								onChange: n[12] ||= (e) => P(a).setQueryField("archived", K(e))
							}, [...n[35] ||= [
								S("option", { value: "0" }, "未归档", -1),
								S("option", { value: "only" }, "仅归档", -1),
								S("option", { value: "all" }, "全部", -1)
							]], 40, Nn)])
						])], 40, Dn)
					]),
					S("div", Pn, [(i(!0), L(_, null, c(P(W), (e) => (i(), L("details", {
						key: e.key,
						class: D(["bulk-filter-popover", { "has-value": e.kind === "text" ? !!P(se)(P(u).query, e.key) : !!P(ue)(P(u).query, e.key).length }]),
						"data-filter-field": e.key,
						open: H.value === e.key,
						onFocusout: ne
					}, [S("summary", { onClick: E((t) => te(e.key, t), ["prevent"]) }, [
						R(b(e.label), 1),
						e.kind === "enum" && P(ue)(P(u).query, e.key).length ? (i(), L("span", Ln, b(P(ue)(P(u).query, e.key).length), 1)) : m("", !0),
						n[37] ||= S("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [S("path", { d: "m4 6 4 4 4-4" })], -1)
					], 8, In), S("div", Rn, [S("div", zn, [S("strong", null, b(e.label), 1), S("button", {
						type: "button",
						"aria-label": `关闭${e.label}筛选`,
						onClick: n[13] ||= (e) => J(e)
					}, "完成", 8, Bn)]), e.kind === "text" ? (i(), L("label", Vn, [R(b(e.label), 1), S("input", {
						"data-query-filter": e.key,
						value: P(se)(P(u).query, e.key),
						inputmode: "numeric",
						placeholder: "输入账号 ID",
						disabled: U.value,
						onInput: (t) => P(a).setQueryField(e.key, K(t))
					}, null, 40, Hn)])) : (i(), L("div", Un, [(i(!0), L(_, null, c(P(a).filterOptions(e.key), (t) => (i(), L("label", { key: t.value }, [S("input", {
						type: "checkbox",
						"data-query-filter": e.key,
						value: t.value,
						checked: P(ue)(P(u).query, e.key).includes(t.value),
						disabled: U.value,
						onChange: (n) => q(e.key, t.value, n.target.checked)
					}, null, 40, Wn), S("span", null, b(t.label), 1)]))), 128)), P(a).filterOptions(e.key).length ? m("", !0) : (i(), L("span", Gn, "暂无可用选项"))]))])], 42, Fn))), 128))]),
					S("div", Kn, [(i(!0), L(_, null, c(P(z), (e) => (i(), L("button", {
						key: e.key,
						type: "button",
						class: "bulk-filter-chip",
						"data-clear-query": e.key,
						"aria-label": e.removeLabel,
						disabled: U.value,
						onClick: (t) => P(a).clearFilter(e.key)
					}, [R(b(e.label), 1), n[38] ||= S("span", { "aria-hidden": "true" }, "×", -1)], 8, qn))), 128)), P(z).length ? m("", !0) : (i(), L("span", Jn, "全部未归档账号"))])
				], 512), [[N, !P(u).source]])
			])
		]), S("aside", Yn, [S("div", Xn, [
			S("div", Zn, [S("div", null, [n[39] ||= S("span", { class: "bulk-side-kicker" }, "执行摘要", -1), S("strong", Qn, b(P(M)), 1)])]),
			S("div", $n, b(P(A) == null ? P(u).source ? "创建时确认" : "匹配中" : `${P(A)} 个`), 1),
			S("p", er, b(P(F)), 1),
			S("dl", tr, [
				S("div", null, [n[40] ||= S("dt", null, "操作", -1), S("dd", nr, b(P(w)?.label || P(u).operation_key), 1)]),
				S("div", null, [n[41] ||= S("dt", null, "范围", -1), S("dd", rr, b(P(j)), 1)]),
				S("div", null, [n[42] ||= S("dt", null, "本批并发", -1), S("dd", ir, b(P(u).max_concurrency), 1)])
			]),
			P(A) != null && P(A) >= 200 ? (i(), L("p", ar, "本批将处理 " + b(P(A)) + " 个账号。", 1)) : m("", !0),
			P(h) ? (i(), L("p", or, [R(b(P(h)), 1), P(x) ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "bulk-link",
				onClick: n[14] ||= (t) => e.deps.callbacks.navigate("detail", { batch_id: P(x) })
			}, "查看批次 #" + b(P(x)), 1)) : m("", !0)])) : m("", !0),
			P(k) ? (i(), L("div", sr, [S("span", null, "有 " + b(P(k)) + " 个请求未收到回执，草稿已保留。", 1), S("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: U.value,
				onClick: n[15] ||= (...e) => P(a).recover && P(a).recover(...e)
			}, b(P(p) ? "正在找回…" : "找回原请求"), 9, cr)])) : m("", !0),
			S("div", lr, [S("button", {
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				"data-bulk-submit": "",
				disabled: U.value || P(A) === 0 || !P(C).length
			}, b(P(f) ? "正在创建批次…" : "创建并执行"), 9, ur), S("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "create-paused",
				disabled: U.value || P(A) === 0 || !P(C).length,
				onClick: n[16] ||= (e) => P(a).createBatch(!0)
			}, b(P(f) ? "正在创建批次…" : "创建并暂停"), 9, dr)]),
			n[43] ||= S("p", { class: "bulk-side-foot" }, "提交时固定账号范围，暂停后可继续原批次", -1),
			S("button", {
				type: "button",
				class: "bulk-side-back",
				"data-bulk-action": "list",
				onClick: n[17] ||= (t) => e.deps.callbacks.navigate("list")
			}, "← 返回批次列表")
		])])], 40, Yt));
	}
}), pr = {
	plan_check: "查套餐",
	token_refresh: "刷新 AT",
	password_setup: "补密码",
	twofa_setup: "补 2FA",
	codex_retry: "补 Codex",
	account_completion: "组合补全"
}, Z = (e) => typeof e == "object" && e && !Array.isArray(e) ? e : {}, mr = (e) => Array.isArray(e) ? e.map(Z) : [], hr = (e) => pr[String(e)] || String(e || "—");
function Q(e) {
	if (typeof e != "number" && (typeof e != "string" || !e.trim())) return null;
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? t : null;
}
var $ = (e) => Q(e) === null ? "—" : Math.floor(Number(e)).toLocaleString("zh-CN");
function gr(e) {
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
function _r(e) {
	let t = Z(e.view);
	if (t.kind !== "round") return "当前结果 · 每个账号取最近一轮";
	let n = Q(t.round_no);
	return n === null || !Number.isSafeInteger(n) || n < 1 ? "所选轮次 · 固定名单" : n === 1 ? "首轮名单" : `重跑 ${n - 1} · 固定名单`;
}
var vr = {
	free: "Free",
	plus: "Plus",
	pro: "Pro",
	team: "Team",
	business: "Business",
	enterprise: "Enterprise",
	go: "Go",
	unknown: "尚未确认"
}, yr = {
	free_trial: "免费试用",
	half_price: "半价优惠",
	discount: "折扣优惠",
	other_discount: "其他折扣",
	other_promo: "其他优惠"
};
function br(e, t, n) {
	let r = typeof t == "string" ? t : "";
	return Object.hasOwn(e, r) ? e[r] : r || n;
}
var xr = (e) => br(vr, e, "尚未确认"), Sr = (e) => br(yr, e, "其他优惠");
function Cr(e, t) {
	return `${Math.max(0, Math.min(100, t > 0 ? (Q(e) || 0) / t * 100 : 0))}%`;
}
var wr = {
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
	...yr
})) wr[`account.plus_offer.${e}`] = `优惠 · ${t}`;
for (let [e, t] of Object.entries({
	unchanged: "优惠未变化",
	new_offer: "新增优惠",
	offer_removed: "优惠消失",
	changed: "优惠变化",
	not_comparable: "历史条件不可比较"
})) wr[`account.comparison.${e}`] = t;
for (let [e, t] of Object.entries({
	password: "密码",
	twofa: "2FA",
	codex: "Codex",
	access_token: "AT",
	plan_check: "套餐"
})) wr[`step.${e}.confirmed`] = `${t} · 已完成`, wr[`step.${e}.pending`] = `${t} · 待完成`;
function Tr(e) {
	let t = { ...Z(e) };
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
			let e = br(wr, a, a), s = t ? `${t} · ${e}` : e;
			if (typeof o == "number") {
				let e = a.startsWith("country_query.") || a.startsWith("country_") ? "国家查询项" : a.startsWith("account.plan.") ? "套餐分布" : a.startsWith("account.plus_offer.") || a.startsWith("account.comparison.") || a === "account.confirmed_no_offer" ? "优惠结果" : a.startsWith("step.") ? "补全项目" : "执行结果";
				n.has(e) || n.set(e, {
					title: e,
					items: []
				}), n.get(e).items.push({
					title: s,
					value: o,
					unit: e === "国家查询项" ? "项" : "个"
				});
			} else o && typeof o == "object" && r(Z(o), s, i + 1);
		}
	}
	return r(t), [...n.values()];
}
// src/features/bulk/bulkDetailPresentation.ts
var Er = {
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
}, Dr = [
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
], Or = (e) => "is-" + (Dr.includes(String(e)) ? "failed" : String(e || "preparing")), kr = (e) => Er[Dr.includes(String(e)) ? "failed" : String(e)] || String(e || "—"), Ar = (e) => String(Z(e?.operation).key || e?.operation_key || e?.action_key || "");
function jr(e) {
	let t = {};
	for (let [n, r] of Object.entries(Z(e))) {
		let e = Dr.includes(n) ? "failed" : n;
		t[e] = (t[e] || 0) + (Q(r) || 0);
	}
	return t;
}
var Mr = (e) => X(e.canonical_target_id || e.target_id || e.id);
function Nr(e) {
	return e == null || e === "" ? null : X(e);
}
function Pr(e) {
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
		let t = [`查询${kr(e.query_outcome)}`];
		return e.account_plan_type && t.push(`套餐 ${e.account_plan_type}`), e.confirmed_no_offer ? t.push("本次确认无优惠") : e.plus_offer_kind && e.plus_offer_kind !== "unknown" && t.push(Sr(e.plus_offer_kind)), e.comparison && e.comparison !== "not_comparable" && t.push({
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
function Fr(e) {
	let t = Z(e.result), n = Z(t.result || e.result_summary || t), r = Z(e.reason || t.reason || e.error || e.error_info), i = Z(e.display_snapshot || e.display), a = Z(e.execution), o = mr(e.owned_runs)[0] || {}, s = Mr(e), c = Nr(e.account_id || i.account_id || i.id || e.entity_id) || s, l = String(i.email || e.email || `账号 #${c}`), u = String(n.summary || n.message || e.result_label || e.summary_text || Pr(n) || "等待本轮结果"), d = String(r.summary || r.cause_summary || r.label || r.message || e.reason_label || e.reason_code || r.code || ""), f = [r.summary || r.cause_summary || r.message || e.error_message || d, r.display_code || r.code || e.reason_code].filter(Boolean).join("\n"), p = String(e.stage_label || e.current_stage_label || e.stage || "").trim(), m = Object.entries(Z(n.capabilities)).map(([e, t]) => `${hr(e)}：${kr(Z(t).state || Z(t).status)}`).join("\n"), h = e.state || e.outcome || e.status;
	return {
		id: s,
		accountId: c,
		account: l,
		summary: u,
		summaryShort: Ir(n, h, u),
		reason: d,
		reasonShort: d ? fe({
			...r,
			code: r.code || e.reason_code
		}) === "执行异常" && [...d].length <= 10 ? d : fe({
			...r,
			code: r.code || e.reason_code
		}) : "",
		reasonContent: f,
		stage: p,
		capabilities: m,
		state: kr(h),
		stateKey: h,
		taskId: Nr(e.task_id || e.owned_task_id || a.task_id || o.task_id),
		runId: Nr(e.owned_run_id || e.run_id || a.run_id || o.run_id),
		blockerTaskId: Nr(e.blocker_task_id)
	};
}
function Ir(e, t, n) {
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
	let r = kr(t);
	return [...r].length <= 10 && r !== "—" ? r : "结果见详情";
}
// src/features/bulk/useBulkDetail.ts
var Lr = [
	"failed",
	"partial_success",
	"not_executed",
	"cancelled"
];
function Rr(e, t, n = e().view === "detail") {
	let r = y({ ...e() }), i = y(n), a = A(null), s = A(null), c = A(null), l = A([]), u = y(null), d = y(/* @__PURE__ */ new Set()), f = y([]), m = y(null), h = y(!1), g = y(!1), _ = y(!1), v = y(!1), b = y(!1), x = y(""), S = y(""), C = y(""), w = y(""), T = A(null), E = !1, D = 0, k = !1, j = null, M = "", N = /* @__PURE__ */ new Map(), P = () => `${r.value.batch_id || ""}:${r.value.round_id || ""}`, F = () => `${P()}:${r.value.result_state || ""}`, I = () => `${F()}:${r.value.cursor || ""}`;
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
		e.includes("detail") && (j = null, M = "");
	}
	function B() {
		let e = new URLSearchParams({ view: r.value.round_id ? "round" : "current" });
		return r.value.round_id && e.set("round_id", X(r.value.round_id)), e;
	}
	function V(e = "") {
		return `/batches/${X(r.value.batch_id)}${e}`;
	}
	function H(e) {
		return e instanceof Error ? e.message : String(e);
	}
	function U(e) {
		let t = new Map(l.value.map((e) => [X(e.id), e]));
		if (Array.isArray(e)) for (let n of e) {
			let e = Z(n);
			t.set(X(e.id), e);
		}
		l.value = [...t.values()].sort((e, t) => Number(t.round_no) - Number(e.round_no));
	}
	let W = O(() => jr(a.value?.summary || a.value?.counts)), ee = O(() => Z(a.value?.control)), G = O(() => ["ended", "completed"].includes(String(ee.value.state || a.value?.control_state))), K = O(() => !!(ee.value.paused || a.value?.is_paused)), q = O(() => f.value.length > 0), J = O(() => s.value?.page?.has_more && s.value.page.next_cursor || null), te = O(() => i.value && r.value.view === "detail" && (!G.value || !!m.value || !!ee.value.pending)), ne = O(() => Object.hasOwn(pr, Ar(a.value)));
	function re(e) {
		return !a.value || b.value || T.value || G.value || ee.value.pending ? !0 : e === "pause" ? K.value : e === "resume" ? !K.value : Z(a.value.capabilities || Z(a.value.operation).capabilities)[e] === !1;
	}
	async function ie() {
		if (!i.value || r.value.view !== "detail") return;
		let e = L("targets");
		g.value = !0, S.value = "";
		try {
			let n = B();
			n.set("page_size", "50"), r.value.cursor && n.set("cursor", r.value.cursor), r.value.result_state && n.set("state[]", r.value.result_state);
			let i = await t.api.request(`${V("/targets")}?${n}`, { signal: e.controller.signal });
			if (R("targets", e)) {
				for (let e of i.items) Mr(e);
				s.value = i;
			}
		} catch (t) {
			R("targets", e) && (S.value = H(t));
		} finally {
			R("targets", e) && (g.value = !1);
		}
	}
	async function Y(e = !1) {
		if (!i.value || r.value.view !== "detail" || !ne.value || _.value) return;
		let n = G.value || Z(a.value?.selected_round).state === "completed", o = n && c.value?.phase === "completed" && c.value.summary_revision === a.value?.summary_revision;
		if (!e && (n && o || !n && (c.value || C.value) && t.now() - D < 1e4)) return;
		let s = L("report");
		_.value = !0, D = t.now();
		try {
			let e = await t.api.request(`${V("/report")}?${B()}`, { signal: s.controller.signal });
			R("report", s) && (c.value = e, C.value = "", D = t.now());
		} catch (e) {
			R("report", s) && (C.value = H(e));
		} finally {
			R("report", s) && (_.value = !1);
		}
	}
	function ae(e = !1) {
		if (E || !i.value || r.value.view !== "detail" || !r.value.batch_id) return Promise.resolve();
		if (j && M === P()) return j;
		M = P();
		let t = oe(e).finally(() => {
			j === t && (j = null, M = "");
		});
		return j = t, t;
	}
	async function oe(e = !1) {
		if (E || !i.value || r.value.view !== "detail" || !r.value.batch_id) return;
		let n = L("detail");
		h.value = !0, x.value = "";
		try {
			let r = await t.api.request(`${V()}?${B()}`, { signal: n.controller.signal });
			if (!R("detail", n)) return;
			let i = a.value?.summary_revision;
			if (a.value = r, U(r.rounds_head), r.selected_round && U([r.selected_round]), k || (u.value = typeof r.rounds_next_cursor == "string" ? r.rounds_next_cursor : null), m.value) {
				let e = l.value.find((e) => e.id === m.value);
				e && e.state !== "preparing" && (m.value = null, t.callbacks.notify(e.completion_reason === "cancelled_before_freeze" ? "重跑准备已取消，当前结果归属不变。" : "重跑名单已固定，可以切换查看新轮次。"));
			}
			let o = [Y(e)];
			(e || !s.value || i !== r.summary_revision) && o.push(ie()), await Promise.all(o);
		} catch (e) {
			R("detail", n) && (x.value = H(e));
		} finally {
			R("detail", n) && (h.value = !1);
		}
	}
	async function se() {
		if (!i.value || r.value.view !== "detail" || !u.value || v.value) return;
		let e = L("rounds");
		v.value = !0;
		try {
			let n = new URLSearchParams({
				page_size: "20",
				cursor: u.value
			}), r = await t.api.request(`${V("/rounds")}?${n}`, { signal: e.controller.signal });
			R("rounds", e) && (U(r.items), u.value = r.page.has_more && r.page.next_cursor || null, k = !0);
		} catch (t) {
			R("rounds", e) && (w.value = H(t));
		} finally {
			R("rounds", e) && (v.value = !1);
		}
	}
	function ce(e, n = !1) {
		n || (f.value = []), r.value = {
			...r.value,
			...e
		}, t.callbacks.updateNavigation(e);
	}
	async function le() {
		J.value && !g.value && (f.value.push(r.value.cursor || ""), ce({ cursor: J.value }, !0));
	}
	async function ue() {
		q.value && !g.value && ce({ cursor: f.value.pop() || "" }, !0);
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
		let n = new Set(d.value);
		t ? n.add(X(e)) : n.delete(e), d.value = n;
	}
	function he(e) {
		for (let t of s.value?.items || []) me(Mr(t), e);
	}
	function ge() {
		d.value = /* @__PURE__ */ new Set();
	}
	function _e(e) {
		return (e === "unsuccessful" ? Lr : [e]).reduce((e, t) => e + (W.value[t] || 0), 0);
	}
	function ve() {
		T.value = null;
	}
	async function ye(e) {
		if (!(b.value || E || !i.value || r.value.view !== "detail" || e.navigationKey !== I())) {
			b.value = !0, w.value = "", T.value = null;
			try {
				let n = await t.intents.submit(e.intentScope, e.path, e.body);
				if (t.callbacks.notify(e.kind === "retry" ? "重跑已受理，正在按固定时点的结果准备新轮次。" : "控制请求已受理，正在读取批次最新状态。"), E || e.navigationKey !== I()) return;
				e.kind === "retry" && (m.value = X(n.round_id || n.id), ge()), await ae(!0);
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
		if (!a.value || b.value || T.value || !Lr.includes(t) && t !== "unsuccessful") return;
		let n = [...d.value], i = e ? n.length : _e(t);
		if (!i) return;
		let o = X(r.value.batch_id), s = r.value.round_id ? X(r.value.round_id) : null, c = {
			title: "确认重跑",
			description: `将在当前批次下新建一轮，重跑 ${i} 个账号；不会覆盖历史轮次。`,
			label: `重跑 ${i} 个`,
			count: i,
			scopeLabel: s ? "当前轮" : "当前结果",
			path: `/batches/${o}/rounds`,
			intentScope: `retry:${o}`,
			navigationKey: I(),
			kind: "retry",
			body: {
				source: {
					view: s ? "round" : "current",
					round_id: s,
					observed_summary_revision: a.value.summary_revision,
					observed_target_count: i
				},
				selection: e ? {
					kind: "targets",
					target_ids: n
				} : {
					kind: "result_filter",
					states: t === "unsuccessful" ? [...Lr] : [t]
				},
				retry_mode: "automatic"
			}
		};
		i >= 10 || t === "unsuccessful" ? T.value = c : await ye(c);
	}
	async function Se(e) {
		if (![
			"pause",
			"resume",
			"cancel_not_started",
			"request_stop"
		].includes(e) || re(e)) return;
		let t = ["pause", "resume"].includes(e), n = e === "request_stop", i = X(r.value.batch_id), o = r.value.round_id ? X(r.value.round_id) : null, s = (n ? ["running", "waiting"] : [
			"pending_submit",
			"waiting_account",
			"queued",
			"waiting"
		]).reduce((e, t) => e + (W.value[t] || 0), 0), c = {
			title: n ? "停止正在执行" : "取消排队账号",
			description: n ? "已开始执行的账号会收到协作停止请求，正在收尾的步骤会完成，不会立即强制中断。" : "尚未开始的目标会取消；已开始账号链的必要步骤会继续收尾。",
			label: n ? "停止执行" : "取消排队",
			count: s,
			scopeLabel: !t && o ? "当前轮" : "整个批次",
			path: `/batches/${i}/control`,
			intentScope: `control:${i}:${e}`,
			navigationKey: I(),
			kind: "control",
			body: {
				action: e,
				expected_control_revision: ee.value.revision ?? a.value?.control_revision,
				scope: !t && o ? {
					kind: "round",
					round_id: o
				} : { kind: "batch" }
			}
		};
		t ? await ye(c) : T.value = c;
	}
	function Ce(e) {
		if (!a.value) return;
		let n = Z(a.value.selection_summary).query || a.value.query_spec || Z(a.value.selection).query_spec;
		(e || n) && t.callbacks.copyBatch?.(n || {}, e ? {
			kind: "batch_targets",
			batch_id: X(r.value.batch_id),
			selection: { kind: "all" }
		} : null, Ar(a.value));
	}
	function we(e) {
		i.value = e, e || (z("detail", "targets", "report", "rounds"), h.value = !1, g.value = !1, _.value = !1, v.value = !1, T.value = null);
	}
	return o(e, (e) => {
		JSON.stringify(e) !== JSON.stringify(r.value) && (f.value = [], r.value = { ...e });
	}, {
		deep: !0,
		flush: "sync"
	}), o(() => r.value.view, (e) => {
		e !== "detail" && we(!1);
	}, { flush: "sync" }), o(() => [
		P(),
		F(),
		r.value.cursor || ""
	], (e, t) => {
		T.value = null, w.value = "", !t || e[0] !== t[0] ? (z("detail", "targets", "report", "rounds"), a.value = null, s.value = null, c.value = null, l.value = [], u.value = null, k = !1, D = 0, C.value = "", S.value = "", h.value = !1, g.value = !1, _.value = !1, v.value = !1, ge(), f.value = [], m.value = null, ae()) : (e[1] !== t[1] && (ge(), f.value = []), s.value = null, ie());
	}, {
		immediate: !0,
		flush: "sync"
	}), p(() => {
		E = !0, z("detail", "targets", "report", "rounds"), T.value = null;
	}), {
		navigation: r,
		detail: a,
		targets: s,
		report: c,
		rounds: l,
		roundsCursor: u,
		selected: d,
		pendingRound: m,
		loading: h,
		targetsLoading: g,
		reportLoading: _,
		roundsLoading: v,
		writing: b,
		error: x,
		targetError: S,
		reportError: C,
		actionError: w,
		confirmation: T,
		counts: W,
		ended: G,
		paused: K,
		needsPolling: te,
		hasReport: ne,
		hasPrevious: q,
		nextCursor: J,
		controlDisabled: re,
		refresh: ae,
		loadTargets: ie,
		refreshReport: Y,
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
var zr = {
	key: 0,
	class: "bulk-business-groups"
}, Br = { class: "bulk-business-metrics" }, Vr = {
	key: 1,
	class: "bulk-report-empty"
}, Hr = /* @__PURE__ */ n({
	__name: "BulkBusinessStats",
	props: {
		metrics: {},
		groups: {}
	},
	setup(e) {
		let t = e, n = O(() => t.groups ?? Tr(t.metrics));
		return (e, t) => n.value.length ? (i(), L("div", zr, [(i(!0), L(_, null, c(n.value, (e) => (i(), L("section", {
			key: e.title,
			class: "bulk-business-group"
		}, [S("h4", null, b(e.title) + " · " + b(e.title === "国家查询项" ? "项" : "账号数"), 1), S("dl", Br, [(i(!0), L(_, null, c(e.items, (e) => (i(), L("div", { key: e.title }, [S("dt", null, b(e.title), 1), S("dd", null, b(P($)(e.value)), 1)]))), 128))])]))), 128))])) : (i(), L("p", Vr, "暂无已确认的功能统计。"));
	}
}), Ur = ["aria-label"], Wr = { role: "status" }, Gr = {
	key: 1,
	class: "bulk-plan-report",
	"aria-labelledby": "bulkPlanReportTitle"
}, Kr = { class: "bulk-report-header" }, qr = { class: "bulk-report-heading-line" }, Jr = { id: "bulkPlanReportTitle" }, Yr = { class: "bulk-report-updated" }, Xr = {
	key: 0,
	class: "bulk-report-sync",
	role: "status"
}, Zr = { class: "bulk-report-outcomes" }, Qr = { class: "bulk-report-outcome-note" }, $r = { class: "bulk-report-execution" }, ei = { "aria-label": "账号执行耗时" }, ti = { class: "bulk-report-section-head" }, ni = { class: "bulk-report-durations" }, ri = { class: "is-average" }, ii = { class: "bulk-report-note" }, ai = {
	key: 0,
	"aria-label": "AT 检查与自动刷新"
}, oi = { class: "bulk-report-at-causes" }, si = { class: "bulk-report-at-results" }, ci = { class: "bulk-report-note" }, li = {
	key: 1,
	"aria-label": "功能统计"
}, ui = {
	key: 1,
	class: "bulk-report-distributions"
}, di = {
	class: "bulk-report-offers",
	"aria-label": "优惠结果"
}, fi = { class: "bulk-report-offer-totals" }, pi = { class: "bulk-report-offer-list" }, mi = { class: "bulk-report-offer-line" }, hi = {
	class: "bulk-report-rail",
	"aria-hidden": "true"
}, gi = { class: "bulk-report-kind-list" }, _i = {
	key: 0,
	class: "bulk-report-empty"
}, vi = {
	class: "bulk-report-plans",
	"aria-label": "当前订阅套餐"
}, yi = { class: "bulk-report-plan-list" }, bi = {
	key: 0,
	class: "bulk-report-empty"
}, xi = {
	key: 2,
	class: "bulk-business-details"
}, Si = /* @__PURE__ */ n({
	__name: "BulkReport",
	props: {
		report: {},
		formatDateTime: { type: Function }
	},
	setup(e) {
		let t = e, n = O(() => Object.hasOwn(pr, String(t.report.operation_key))), r = O(() => Z(t.report.totals)), a = O(() => Z(t.report.duration)), o = O(() => Z(t.report.at_refresh)), s = O(() => Z(t.report.offers)), l = O(() => t.report.phase === "completed"), u = O(() => t.report.operation_key === "plan_check"), f = O(() => mr(t.report.plans).sort((e, t) => e.plan === "unknown" ? 1 : t.plan === "unknown" ? -1 : (Q(t.accounts) || 0) - (Q(e.accounts) || 0))), p = O(() => mr(s.value.by_plan).sort((e, t) => (Q(t.accounts) || 0) - (Q(e.accounts) || 0) || xr(e.plan).localeCompare(xr(t.plan)))), h = O(() => Math.max(0, ...f.value.map((e) => Q(e.accounts) || 0))), g = O(() => Math.max(0, ...p.value.map((e) => Q(e.accounts) || 0))), y = O(() => Tr(t.report.business_summary)), x = [
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
		], C = [
			["AT 过期", "expired_accounts"],
			["远端拒绝 AT", "invalid_accounts"],
			["缺少 AT", "missing_token_accounts"]
		], w = [
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
		], T = [
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
		return (t, E) => n.value && e.report.population_ready === !1 ? (i(), L("section", {
			key: 0,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": P(hr)(e.report.operation_key) + "报告"
		}, [S("h3", null, b(P(hr)(e.report.operation_key)) + "报告", 1), S("p", Wr, b(P(_r)(e.report)) + " · " + b(e.report.phase === "preparing" ? "账号名单准备中，固定后生成报告。" : "该轮名单未固定，无法生成账号统计。"), 1)], 8, Ur)) : n.value ? (i(), L("section", Gr, [
			S("header", Kr, [S("div", null, [S("div", qr, [S("h3", Jr, b(P(hr)(e.report.operation_key)) + b(l.value ? "完成报告" : "实时报告"), 1), S("span", { class: D(["bulk-report-phase", { "is-completed": l.value }]) }, b(l.value ? "已完成" : e.report.phase === "preparing" ? "名单准备中" : "统计更新中"), 3)]), S("p", null, b(P(_r)(e.report)) + " · " + b(P($)(r.value.accounts)) + " 个账号", 1)]), S("span", Yr, "更新于 " + b(e.formatDateTime(e.report.generated_at)), 1)]),
			P(Z)(e.report.projection).state && P(Z)(e.report.projection).state !== "current" ? (i(), L("p", Xr, b(P(Z)(e.report.projection).state === "failed" ? "结果汇总暂时失败，以下统计尚未收齐，请稍后刷新。" : "执行结果正在汇总，以下统计尚未收齐。"), 1)) : m("", !0),
			S("dl", Zr, [(i(), L(_, null, c(x, ([e, t, n]) => S("div", {
				key: t,
				class: D(["bulk-report-metric", n])
			}, [S("dt", null, b(e), 1), S("dd", null, [R(b(P($)(r.value[t])), 1), E[0] ||= S("span", null, "个", -1)])], 2)), 64))]),
			S("div", Qr, [
				S("span", null, "已结束 " + b(P($)(r.value.completed)) + " / " + b(P($)(r.value.accounts)) + " 个", 1),
				S("span", null, "未执行 " + b(P($)(r.value.not_executed)) + " 个", 1),
				S("span", null, "已取消 " + b(P($)(r.value.cancelled)) + " 个", 1)
			]),
			S("div", $r, [S("section", ei, [
				S("div", ti, [E[1] ||= S("h4", null, "账号执行耗时", -1), S("span", null, "已结束样本 " + b(P($)(a.value.sample_count)) + " 个", 1)]),
				S("dl", ni, [
					S("div", ri, [E[2] ||= S("dt", null, "平均耗时", -1), S("dd", null, b(P(gr)(a.value.avg_seconds)), 1)]),
					S("div", null, [E[3] ||= S("dt", null, "最快", -1), S("dd", null, b(P(gr)(a.value.min_seconds)), 1)]),
					S("div", null, [E[4] ||= S("dt", null, "最慢", -1), S("dd", null, b(P(gr)(a.value.max_seconds)), 1)])
				]),
				S("p", ii, [R(" 从账号开始执行到结束，" + b(u.value ? "含自动刷新及链内等待" : "含链内等待") + "，不含开始前排队。", 1), (P(Q)(a.value.missing_count) || 0) > 0 ? (i(), L(_, { key: 0 }, [R(b(P($)(a.value.missing_count)) + " 个已结束账号缺少有效耗时，未计入均值。", 1)], 64)) : P(Q)(a.value.sample_count) === 0 ? (i(), L(_, { key: 1 }, [R(" 暂无有效耗时样本。")], 64)) : m("", !0)])
			]), u.value ? (i(), L("section", ai, [
				E[8] ||= S("div", { class: "bulk-report-section-head" }, [S("h4", null, "AT 检查与自动刷新"), S("span", null, "按账号去重")], -1),
				S("dl", oi, [(i(), L(_, null, c(C, ([e, t]) => S("div", {
					key: t,
					class: "bulk-report-minor"
				}, [S("dt", null, b(e), 1), S("dd", null, [R(b(P($)(o.value[t])), 1), E[5] ||= S("span", null, "个", -1)])])), 64))]),
				S("dl", si, [(i(), L(_, null, c(w, ([e, t, n]) => S("div", {
					key: t,
					class: D(["bulk-report-minor", n])
				}, [S("dt", null, b(e), 1), S("dd", null, [R(b(P($)(o.value[t])), 1), E[6] ||= S("span", null, "个", -1)])], 2)), 64))]),
				S("p", ci, [
					P(Q)(o.value.not_needed_accounts) === null ? m("", !0) : (i(), L(_, { key: 0 }, [R("未触发刷新 " + b(P($)(o.value.not_needed_accounts)) + " 个 · ", 1)], 64)),
					R("刷新状态待确认 " + b(P($)(o.value.unknown_accounts)) + " 个", 1),
					P(Q)(o.value.not_executed_accounts) === null ? m("", !0) : (i(), L(_, { key: 1 }, [R(" · 未开始执行 " + b(P($)(o.value.not_executed_accounts)) + " 个", 1)], 64)),
					E[7] ||= R("。待确认含执行中尚无结果及历史证据缺失；触发原因可能重叠，远端拒绝不等于本地过期。 ", -1)
				])
			])) : (i(), L("section", li, [E[9] ||= S("div", { class: "bulk-report-section-head" }, [S("h4", null, "功能统计"), S("span", null, "当前查看范围")], -1), d(Hr, { groups: y.value }, null, 8, ["groups"])]))]),
			u.value ? (i(), L("div", ui, [S("section", di, [
				E[13] ||= S("div", { class: "bulk-report-section-head" }, [S("div", null, [S("h4", null, "优惠结果"), S("p", null, "统计本次查到的可用优惠，按账号去重")])], -1),
				S("dl", fi, [(i(), L(_, null, c(T, ([e, t, n]) => S("div", {
					key: t,
					class: D(["bulk-report-metric", { "is-accent": t === "with_offer_accounts" }])
				}, [
					S("dt", null, b(e), 1),
					S("dd", null, [R(b(P($)(s.value[t])), 1), E[10] ||= S("span", null, "个", -1)]),
					S("small", null, b(n), 1)
				], 2)), 64))]),
				S("div", pi, [(i(!0), L(_, null, c(p.value, (e) => (i(), L("div", {
					key: String(e.plan),
					class: "bulk-report-offer-row"
				}, [
					S("div", mi, [S("strong", null, b(P(xr)(e.plan)), 1), S("span", null, [S("b", null, b(P($)(e.accounts)), 1), E[11] ||= R(" 个账号", -1)])]),
					S("span", hi, [S("span", { style: v({ width: P(Cr)(e.accounts, g.value) }) }, null, 4)]),
					S("dl", gi, [(i(!0), L(_, null, c(P(mr)(e.kinds), (e) => (i(), L("div", { key: String(e.kind) }, [S("dt", null, b(P(Sr)(e.kind)), 1), S("dd", null, [R(b(P($)(e.accounts)), 1), E[12] ||= S("span", null, "个", -1)])]))), 128))])
				]))), 128)), p.value.length ? m("", !0) : (i(), L("p", _i, b(P(Q)(s.value.with_offer_accounts) === 0 ? "本次尚未查到可用优惠。" : "暂无优惠套餐明细。"), 1))]),
				E[14] ||= S("p", { class: "bulk-report-note" }, "同一账号可符合多个套餐或优惠，分项数量可能重叠。", -1)
			]), S("section", vi, [
				E[16] ||= S("div", { class: "bulk-report-section-head" }, [S("div", null, [S("h4", null, "当前订阅套餐"), S("p", null, "本次查询确认的套餐状态")])], -1),
				S("dl", yi, [(i(!0), L(_, null, c(f.value, (e) => (i(), L("div", {
					key: String(e.plan),
					class: D({ "is-unknown": e.plan === "unknown" })
				}, [S("dt", null, b(P(xr)(e.plan)), 1), S("dd", null, [S("span", null, [R(b(P($)(e.accounts)), 1), E[15] ||= S("small", null, "个", -1)]), S("span", {
					class: D(["bulk-report-rail", { "is-muted": e.plan === "unknown" }]),
					"aria-hidden": "true"
				}, [S("span", { style: v({ width: P(Cr)(e.accounts, h.value) }) }, null, 4)], 2)])], 2))), 128)), f.value.length ? m("", !0) : (i(), L("div", bi, "暂无套餐结果。"))]),
				E[17] ||= S("p", { class: "bulk-report-note" }, "“尚未确认”包含待完成、失败或缺少套餐记录的账号。", -1)
			])])) : m("", !0),
			u.value && y.value.length ? (i(), L("details", xi, [E[18] ||= S("summary", null, [R("更多查询统计"), S("span", null, "展开查看")], -1), d(Hr, { groups: y.value }, null, 8, ["groups"])])) : m("", !0)
		])) : m("", !0);
	}
}), Ci = ["aria-label"], wi = {
	key: 0,
	role: "status"
}, Ti = {
	key: 2,
	class: "bulk-report-load-error"
}, Ei = {
	class: "bulk-error",
	role: "alert"
}, Di = ["disabled"], Oi = /* @__PURE__ */ n({
	__name: "BulkReportView",
	props: {
		operationKey: {},
		report: {},
		error: {},
		loading: { type: Boolean },
		formatDateTime: { type: Function },
		onRetry: { type: Function }
	},
	setup(e) {
		let t = e, n = O(() => Object.hasOwn(pr, t.operationKey)), r = O(() => `${pr[t.operationKey]}报告`);
		return (t, a) => n.value ? (i(), L(_, { key: 0 }, [e.report && e.report.operation_key === e.operationKey ? (i(), x(Si, {
			key: 0,
			report: e.report,
			"format-date-time": e.formatDateTime
		}, null, 8, ["report", "format-date-time"])) : (i(), L("section", {
			key: 1,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": r.value
		}, [S("h3", null, b(r.value), 1), e.error ? m("", !0) : (i(), L("p", wi, "正在汇总本次执行结果…"))], 8, Ci)), e.error ? (i(), L("div", Ti, [S("p", Ei, b(e.error), 1), S("button", {
			type: "button",
			class: "jobs-tb-btn",
			"data-bulk-action": "report-refresh",
			disabled: e.loading,
			onClick: a[0] ||= E((t) => e.onRetry(), ["stop"])
		}, " 重新读取报告 ", 8, Di)])) : m("", !0)], 64)) : m("", !0);
	}
}), ki = ["aria-busy"], Ai = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, ji = {
	class: "bulk-target-scroll",
	role: "region",
	"aria-label": "账号明细内容",
	tabindex: "0"
}, Mi = { class: "bulk-table bulk-target-table" }, Ni = [
	"disabled",
	"checked",
	"indeterminate"
], Pi = { class: "bulk-target-filter" }, Fi = ["checked"], Ii = [
	"value",
	"checked",
	"onChange"
], Li = ["data-bulk-row-target"], Ri = {
	class: "bulk-target-check",
	"data-label": "选择"
}, zi = [
	"data-bulk-target",
	"aria-label",
	"checked",
	"onChange"
], Bi = {
	class: "bulk-target-id",
	"data-label": "ID"
}, Vi = ["aria-label", "onClick"], Hi = {
	class: "bulk-target-account",
	"data-label": "账号"
}, Ui = ["title", "onClick"], Wi = {
	class: "bulk-target-state",
	"data-label": "结果 / 阶段"
}, Gi = { class: "bulk-target-status-line" }, Ki = ["onClick"], qi = {
	class: "bulk-target-summary",
	"data-label": "结果摘要"
}, Ji = [
	"title",
	"aria-label",
	"onClick"
], Yi = {
	class: "bulk-target-reason",
	"data-label": "错误分类"
}, Xi = ["title", "onClick"], Zi = {
	class: "bulk-target-actions",
	"data-label": "操作"
}, Qi = { class: "bulk-target-action-line" }, $i = ["onClick"], ea = { key: 1 }, ta = ["onClick"], na = { key: 0 }, ra = { colspan: "7" }, ia = {
	class: "bulk-empty",
	role: "status"
}, aa = {
	key: 0,
	class: "bulk-vue-result-details"
}, oa = /* @__PURE__ */ n({
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
	setup(e, { expose: t, emit: n }) {
		let r = e, s = n, u = y(null), f = A(r.items), p = O(() => f.value.map(Fr)), h = O(() => p.value.filter((e) => r.selected.has(e.id)).length), g = y(!1), v = O(() => [.../* @__PURE__ */ new Set([...r.resultStates, ...r.resultState ? [r.resultState] : []])]);
		function C(e) {
			g.value = !1, s("filter", e);
		}
		function T() {
			let e = window.getSelection();
			return !!(e?.toString() && e.anchorNode && u.value?.contains(e.anchorNode));
		}
		function E() {
			T() || (f.value = r.items);
		}
		o(() => r.items, (e) => {
			T() && e.length || (f.value = e);
		}), o(() => r.scope, () => {
			f.value = r.items;
		}), l(() => document.addEventListener("selectionchange", E)), w(() => document.removeEventListener("selectionchange", E));
		let k = y(!1), j = A(null), M = null;
		function N(e, t) {
			j.value = { ...e }, M = t.currentTarget, k.value = !0;
		}
		function F(e) {
			e.preventDefault();
			let t = M;
			if (M = null, !t?.isConnected || t.hasAttribute("disabled") || t.closest("[hidden],[inert]")) return;
			let n = t;
			for (; n;) {
				if (getComputedStyle(n).display === "none" || getComputedStyle(n).visibility === "hidden") return;
				n = n.parentElement;
			}
			t.focus({ preventScroll: !0 });
		}
		function I() {
			k.value = !1, g.value = !1;
		}
		function z(e) {
			return e.target.checked;
		}
		function B(e, t = null) {
			r.openTask(e, t);
		}
		return t({ close: I }), (t, n) => (i(), L(_, null, [S("div", {
			ref_key: "host",
			ref: u,
			class: "bulk-targets",
			"aria-busy": e.loading
		}, [e.error ? (i(), L("div", Ai, [R(b(e.error) + " ", 1), S("button", {
			type: "button",
			class: "bulk-link",
			onClick: n[0] ||= (e) => s("retry")
		}, "重试读取明细")])) : m("", !0), S("div", ji, [S("table", Mi, [S("thead", null, [S("tr", null, [
			S("th", null, [S("input", {
				type: "checkbox",
				"data-select-page": "",
				"aria-label": "选择当前页目标",
				disabled: !p.value.length,
				checked: p.value.length > 0 && h.value === p.value.length,
				indeterminate: h.value > 0 && h.value < p.value.length,
				onChange: n[1] ||= (e) => s("selectPage", z(e))
			}, null, 40, Ni)]),
			n[7] ||= S("th", null, "ID", -1),
			n[8] ||= S("th", null, "账号", -1),
			S("th", null, [e.resultStates.length ? (i(), x(te, {
				key: 0,
				label: "结果状态",
				"trigger-label": "结果 / 阶段",
				active: !!e.resultState,
				summary: P(kr)(e.resultState),
				open: g.value,
				"onUpdate:open": n[3] ||= (e) => g.value = e
			}, {
				default: a(() => [S("fieldset", Pi, [
					n[6] ||= S("legend", { class: "bulk-sr-only" }, "结果状态", -1),
					S("label", null, [
						S("input", {
							type: "radio",
							name: "bulk-target-state",
							value: "",
							checked: !e.resultState,
							onChange: n[2] ||= (e) => C("")
						}, null, 40, Fi),
						n[5] ||= S("span", null, "全部", -1),
						S("strong", null, b(P($)(e.resultTotal)), 1)
					]),
					(i(!0), L(_, null, c(v.value, (t) => (i(), L("label", { key: t }, [
						S("input", {
							type: "radio",
							name: "bulk-target-state",
							value: t,
							checked: e.resultState === t,
							onChange: (e) => C(t)
						}, null, 40, Ii),
						S("span", null, b(P(kr)(t)), 1),
						S("strong", null, b(e.resultCounts[t] || 0), 1)
					]))), 128))
				])]),
				_: 1
			}, 8, [
				"active",
				"summary",
				"open"
			])) : (i(), L(_, { key: 1 }, [R("结果 / 阶段")], 64))]),
			n[9] ||= S("th", null, "结果摘要", -1),
			n[10] ||= S("th", null, "错误分类", -1),
			n[11] ||= S("th", null, "操作", -1)
		])]), S("tbody", null, [(i(!0), L(_, null, c(p.value, (t) => (i(), L("tr", {
			key: t.id,
			"data-bulk-row-target": t.id
		}, [
			S("td", Ri, [S("input", {
				type: "checkbox",
				"data-bulk-target": t.id,
				"aria-label": "选择账号 " + t.account,
				checked: e.selected.has(t.id),
				onChange: (e) => s("toggle", t.id, z(e))
			}, null, 40, zi)]),
			S("td", Bi, [S("button", {
				type: "button",
				class: "bulk-cell-detail",
				"aria-label": "查看完整账号 ID：" + t.accountId,
				onClick: (e) => N(t, e)
			}, "#" + b(t.accountId), 9, Vi)]),
			S("td", Hi, [S("button", {
				type: "button",
				class: "bulk-cell-detail",
				title: t.account,
				onClick: (e) => N(t, e)
			}, b(t.account), 9, Ui)]),
			S("td", Wi, [S("div", Gi, [S("span", { class: D(["bulk-badge", P(Or)(t.stateKey)]) }, b(t.state), 3), t.stage && !["—", "-"].includes(t.stage) ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "bulk-cell-detail bulk-target-stage",
				onClick: (e) => N(t, e)
			}, b(t.stage), 9, Ki)) : m("", !0)])]),
			S("td", qi, [d(q, {
				text: t.summaryShort,
				title: t.summary
			}, {
				default: a(() => [S("button", {
					type: "button",
					class: "bulk-cell-detail",
					"data-result-detail": "",
					title: t.summary,
					"aria-label": "查看完整结果摘要：" + t.summary,
					onClick: (e) => N(t, e)
				}, b(t.summaryShort), 9, Ji)]),
				_: 2
			}, 1032, ["text", "title"])]),
			S("td", Yi, [t.reason ? (i(), x(q, {
				key: 0,
				text: t.reasonShort,
				title: t.reason
			}, {
				default: a(() => [S("button", {
					type: "button",
					class: "bulk-cell-detail",
					title: t.reason,
					onClick: (e) => N(t, e)
				}, b(t.reasonShort), 9, Xi)]),
				_: 2
			}, 1032, ["text", "title"])) : (i(), L(_, { key: 1 }, [R("—")], 64))]),
			S("td", Zi, [S("div", Qi, [t.taskId ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-owned-task": "",
				onClick: (e) => B(t.taskId, t.runId)
			}, "查看执行", 8, $i)) : (i(), L("span", ea, "尚未创建执行")), t.blockerTaskId ? (i(), L("button", {
				key: 2,
				type: "button",
				class: "bulk-link",
				"data-blocker-task": "",
				title: "查看占用任务（其他执行）",
				onClick: (e) => B(t.blockerTaskId)
			}, "查看占用", 8, ta)) : m("", !0)])])
		], 8, Li))), 128)), p.value.length ? m("", !0) : (i(), L("tr", na, [S("td", ra, [S("div", ia, b(e.loading ? "正在读取账号明细…" : "当前条件下没有目标。更改结果筛选不会改变本批固定名单。"), 1)])]))])])])], 8, ki), d(P(he), {
			open: k.value,
			"onUpdate:open": n[4] ||= (e) => k.value = e
		}, {
			default: a(() => [d(P(Oe), null, {
				default: a(() => [d(P(De), { class: "bulk-vue-overlay" }), d(P(we), {
					class: "bulk-vue-dialog",
					onCloseAutoFocus: F
				}, {
					default: a(() => [
						d(P(ke), null, {
							default: a(() => [...n[12] ||= [R("账号执行详情", -1)]]),
							_: 1
						}),
						d(P(Te), null, {
							default: a(() => [R(b(j.value?.account) + " · 账号 #" + b(j.value?.accountId), 1)]),
							_: 1
						}),
						j.value ? (i(), L("dl", aa, [
							n[15] ||= S("dt", null, "结果 / 阶段", -1),
							S("dd", null, b(j.value.state) + " · " + b(j.value.stage || "—"), 1),
							n[16] ||= S("dt", null, "结果摘要", -1),
							S("dd", null, b(j.value.summary), 1),
							j.value.capabilities ? (i(), L(_, { key: 0 }, [n[13] ||= S("dt", null, "能力结果", -1), S("dd", null, b(j.value.capabilities), 1)], 64)) : m("", !0),
							n[17] ||= S("dt", null, "错误分类 / 错误码", -1),
							S("dd", null, b(j.value.reasonContent || "—"), 1),
							n[18] ||= S("dt", null, "所属执行", -1),
							S("dd", null, b(j.value.taskId ? "任务 #" + j.value.taskId : "尚未创建执行") + b(j.value.runId ? " · 运行 #" + j.value.runId : ""), 1),
							j.value.blockerTaskId ? (i(), L(_, { key: 1 }, [n[14] ||= S("dt", null, "占用任务（其他执行）", -1), S("dd", null, "#" + b(j.value.blockerTaskId), 1)], 64)) : m("", !0)
						])) : m("", !0),
						d(P(ge), {
							class: "jobs-tb-btn",
							"data-close-detail": ""
						}, {
							default: a(() => [...n[19] ||= [R("关闭", -1)]]),
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
}), sa = ["aria-busy"], ca = { class: "bulk-detail-page-heading" }, la = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, ua = {
	key: 1,
	class: "bulk-card bulk-overview"
}, da = { class: "bulk-detail-toolbar" }, fa = { class: "bulk-detail-meta" }, pa = { class: "bulk-settings bulk-detail-settings" }, ma = {
	key: 0,
	class: "bulk-projection-note"
}, ha = { class: "bulk-actions" }, ga = { class: "bulk-round-picker" }, _a = ["value"], va = ["value"], ya = ["value"], ba = ["disabled"], xa = ["disabled"], Sa = { class: "bulk-control-strip" }, Ca = { class: "bulk-control-copy" }, wa = { class: "bulk-actions" }, Ta = [
	"data-bulk-action",
	"disabled",
	"onClick"
], Ea = { class: "bulk-view-note" }, Da = { class: "bulk-summary-grid" }, Oa = { class: "bulk-summary-item" }, ka = { class: "bulk-summary-item" }, Aa = { class: "bulk-summary-item is-success" }, ja = { class: "bulk-summary-item is-warning" }, Ma = ["aria-busy"], Na = { class: "bulk-card bulk-results-card" }, Pa = { class: "bulk-results-heading" }, Fa = ["disabled"], Ia = { class: "bulk-retry-toolbar" }, La = ["value"], Ra = ["disabled"], za = ["disabled"], Ba = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, Va = {
	key: 1,
	class: "bulk-notice",
	role: "status"
}, Ha = {
	class: "bulk-target-count-row",
	"data-bulk-target-count-row": ""
}, Ua = {
	class: "bulk-target-count",
	role: "status"
}, Wa = { class: "bulk-vue-dialog-actions" }, Ga = /*#__PURE__*/ F(/* @__PURE__ */ n({
	__name: "BulkDetail",
	props: {
		navigation: {},
		deps: {},
		visible: {
			type: Boolean,
			default: void 0
		}
	},
	setup(e, { expose: n }) {
		let r = e, l = Rr(() => r.navigation, r.deps, r.visible ?? r.navigation.view === "detail"), { navigation: u, detail: f, targets: p, report: g, rounds: v, roundsCursor: x, selected: C, pendingRound: w, loading: T, targetsLoading: E, reportLoading: k, roundsLoading: A, writing: j, error: M, targetError: N, reportError: F, actionError: I, confirmation: z, counts: B, ended: V, paused: H, hasReport: U, hasPrevious: W, nextCursor: ee } = l, G = y(null), K = y(null), q = y("failed"), J = O(() => [
			"success",
			"partial_success",
			"failed",
			"not_executed",
			"cancelled"
		].reduce((e, t) => e + (B.value[t] || 0), 0)), te = O(() => [
			"pending_submit",
			"waiting_account",
			"queued",
			"running",
			"waiting"
		].reduce((e, t) => e + (B.value[t] || 0), 0)), re = O(() => v.value.find((e) => e.id === u.value.round_id)), ie = O(() => !!(Z(f.value?.selection_summary).query || f.value?.query_spec || Z(f.value?.selection).query_spec)), Y = [
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
		], ae = O(() => u.value.result_state ? [{
			key: "result_state",
			label: `结果状态：${kr(u.value.result_state)}`,
			title: `结果状态：${kr(u.value.result_state)}`,
			removeLabel: "清除结果状态筛选"
		}] : []), oe = [
			["failed", "失败"],
			["partial_success", "部分成功"],
			["not_executed", "未执行"],
			["cancelled", "已取消"],
			["unsuccessful", "全部未成功"]
		], se = [
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
		], ce = null;
		function le(e) {
			ce = e.currentTarget;
		}
		async function ue(e, t) {
			le(t), await l.retry(e, q.value);
		}
		async function de(e, t) {
			le(t), await l.control(e);
		}
		function fe(e) {
			e.preventDefault();
			let n = ce;
			ce = null, t(() => {
				if (n?.isConnected && !n.hasAttribute("disabled") && !n.closest("[hidden],[inert]")) {
					let e = n;
					for (; e;) {
						if (getComputedStyle(e).display === "none" || getComputedStyle(e).visibility === "hidden") return;
						e = e.parentElement;
					}
					n.focus({ preventScroll: !0 });
				}
			});
		}
		async function pe() {
			await t(), K.value && (K.value.focus({ preventScroll: !0 }), K.value.scrollIntoView?.({ block: "start" })), !g.value && !k.value && await l.refreshReport(!0);
		}
		function me(e) {
			l.setVisible(e), e || (G.value?.close(), ce = null);
		}
		return o(() => r.visible, (e) => {
			e !== void 0 && me(e);
		}, { flush: "sync" }), o(() => [
			u.value.batch_id,
			u.value.round_id,
			u.value.result_state,
			u.value.view
		], () => {
			G.value?.close(), ce = null;
		}), n({
			refresh: l.refresh,
			showReport: pe,
			setVisible: me,
			needsRefresh: l.needsPolling
		}), (t, n) => (i(), L("div", {
			class: "bulk-detail-owner",
			"aria-busy": P(T)
		}, [
			S("header", ca, [S("div", null, [S("h2", null, b(P(f)?.name || P(f)?.title || "批次详情"), 1), S("p", null, b(P(hr)(P(Ar)(P(f)))) + " · #" + b(P(u).batch_id), 1)]), P(U) ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "view-report",
				onClick: pe
			}, "查看报告")) : m("", !0)]),
			P(M) ? (i(), L("p", la, [R(b(P(M)) + " ", 1), S("button", {
				type: "button",
				class: "bulk-link",
				onClick: n[0] ||= (e) => P(l).refresh(!0)
			}, "重试读取批次")])) : m("", !0),
			P(f) ? (i(), L("section", ua, [
				S("div", da, [S("div", fa, [
					S("span", { class: D(["bulk-badge", P(Or)(P(H) ? "paused" : P(Z)(P(f).control).state || P(f).control_state || P(f).state)]) }, b(P(kr)(P(H) ? "paused" : P(Z)(P(f).control).state || P(f).control_state || P(f).state)), 3),
					S("span", null, "创建于 " + b(e.deps.callbacks.formatDateTime(P(f).created_at)), 1),
					S("details", pa, [n[15] ||= S("summary", null, "范围与设置", -1), S("dl", null, [
						n[12] ||= S("dt", null, "名单生成", -1),
						S("dd", null, b(e.deps.callbacks.formatDateTime(P(Z)(P(f).selection_summary).selection_at || P(f).selection_at)), 1),
						n[13] ||= S("dt", null, "配置版本", -1),
						S("dd", null, b(P(Z)(P(f).effective_settings).config_revision || P(f).config_revision || "—"), 1),
						n[14] ||= S("dt", null, "结果更新", -1),
						S("dd", null, b(e.deps.callbacks.formatDateTime(P(f).projected_at)), 1)
					])]),
					P(Z)(P(f).projection).state && P(Z)(P(f).projection).state !== "current" ? (i(), L("span", ma, "汇总同步中")) : m("", !0)
				]), S("div", ha, [
					S("label", ga, [n[17] ||= S("span", { class: "bulk-sr-only" }, "结果视图", -1), S("select", {
						value: P(u).round_id || "current",
						"aria-label": "结果视图",
						onChange: n[1] ||= (e) => P(l).setRound(e.target.value)
					}, [
						n[16] ||= S("option", { value: "current" }, "当前结果", -1),
						(i(!0), L(_, null, c(P(v), (e) => (i(), L("option", {
							key: String(e.id),
							value: String(e.id)
						}, b(Number(e.round_no) === 1 ? "首轮" : "重跑 " + (Number(e.round_no) - 1)) + " · " + b(P(kr)(e.state)) + " · " + b(e.target_count == null ? "准备中" : P($)(e.target_count) + " 个"), 9, va))), 128)),
						P(u).round_id && !re.value ? (i(), L("option", {
							key: 0,
							value: P(u).round_id
						}, "所选轮次 #" + b(P(u).round_id), 9, ya)) : m("", !0)
					], 40, _a)]),
					S("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "more-rounds",
						disabled: !P(x) || P(A),
						onClick: n[2] ||= (...e) => P(l).moreRounds && P(l).moreRounds(...e)
					}, "更多轮次", 8, ba),
					S("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "copy-targets",
						onClick: n[3] ||= (e) => P(l).copyBatch(!0)
					}, "同一名单再次执行"),
					S("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "copy-query",
						disabled: !ie.value,
						onClick: n[4] ||= (e) => P(l).copyBatch(!1)
					}, "复制条件新建", 8, xa)
				])]),
				S("div", Sa, [S("div", Ca, [n[18] ||= S("strong", null, "运行控制", -1), S("span", null, b(P(V) ? "批次已结束" : P(H) ? "批次已暂停，尚未开始的账号等待继续；已开始账号继续收尾" : te.value + " 个进行中 · 已结束 " + J.value + " / " + P($)(P(f).target_count)), 1)]), S("div", wa, [(i(), L(_, null, c(se, ([e, t, n]) => S("button", {
					key: e,
					type: "button",
					class: D(["jobs-tb-btn", { "jobs-tb-btn--danger": ["cancel", "stop"].includes(n) }]),
					"data-bulk-action": n,
					disabled: P(l).controlDisabled(e),
					onClick: (t) => de(e, t)
				}, b(t), 11, Ta)), 64))])]),
				S("p", Ea, b(re.value?.completion_reason === "cancelled_before_freeze" ? "本轮在名单生成前取消，当前结果未改变。" : P(u).round_id ? "仅展示该轮名单及执行结果。" : "已结束 " + J.value + " / " + P($)(P(f).target_count) + " 个 · 每个账号保留最近一轮结果"), 1),
				P(U) ? m("", !0) : (i(), L(_, { key: 0 }, [S("div", Da, [
					S("div", Oa, [n[19] ||= S("span", null, "账号总数", -1), S("strong", null, b(P($)(P(f).target_count)), 1)]),
					S("div", ka, [n[20] ||= S("span", null, "进行中", -1), S("strong", null, b(te.value), 1)]),
					S("div", Aa, [n[21] ||= S("span", null, "成功", -1), S("strong", null, b(P(B).success || 0), 1)]),
					S("div", ja, [n[22] ||= S("span", null, "未成功", -1), S("strong", null, b(P(l).retryCount("unsuccessful")), 1)])
				]), d(Hr, { metrics: P(f).business_summary || P(f).metrics }, null, 8, ["metrics"])], 64))
			])) : m("", !0),
			P(U) ? (i(), L("section", {
				key: 2,
				ref_key: "reportRegion",
				ref: K,
				"data-bulk-plan-report": "",
				class: "bulk-report-target",
				tabindex: "-1",
				role: "region",
				"aria-label": "批次报告",
				"aria-busy": P(k)
			}, [d(Oi, {
				"operation-key": P(Ar)(P(f)),
				report: P(g),
				error: P(F) ? "读取报告失败：" + P(F) : "",
				"format-date-time": e.deps.callbacks.formatDateTime,
				"on-retry": () => P(l).refreshReport(!0),
				loading: P(k)
			}, null, 8, [
				"operation-key",
				"report",
				"error",
				"format-date-time",
				"on-retry",
				"loading"
			])], 8, Ma)) : m("", !0),
			S("section", Na, [
				S("div", Pa, [S("h3", null, [
					n[23] ||= R("账号明细 ", -1),
					S("span", null, b(P(C).size ? "已选 " + P(C).size + " 个（可跨页）" : ""), 1),
					S("button", {
						type: "button",
						class: "bulk-link",
						disabled: !P(C).size,
						onClick: n[5] ||= (...e) => P(l).clearSelection && P(l).clearSelection(...e)
					}, "清空选择", 8, Fa)
				]), S("div", Ia, [
					s(S("select", {
						"onUpdate:modelValue": n[6] ||= (e) => q.value = e,
						"aria-label": "重跑范围"
					}, [(i(), L(_, null, c(oe, ([e, t]) => S("option", {
						key: e,
						value: e
					}, b(t), 9, La)), 64))], 512), [[h, q.value]]),
					S("button", {
						type: "button",
						class: "jobs-tb-btn jobs-tb-btn--primary",
						"data-bulk-action": "retry",
						disabled: P(j) || !!P(z) || !P(l).retryCount(q.value),
						onClick: n[7] ||= (e) => ue(!1, e)
					}, "重跑" + b(oe.find((e) => e[0] === q.value)?.[1]) + " (" + b(P(l).retryCount(q.value)) + ")", 9, Ra),
					S("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "retry-selected",
						disabled: P(j) || !!P(z) || !P(C).size,
						onClick: n[8] ||= (e) => ue(!0, e)
					}, "重跑勾选" + b(P(C).size ? " (" + P(C).size + ")" : ""), 9, za)
				])]),
				P(I) ? (i(), L("p", Ba, b(P(I)), 1)) : m("", !0),
				P(w) ? (i(), L("p", Va, "重跑已受理，正在准备新轮次 #" + b(P(w)) + "。", 1)) : m("", !0),
				S("div", Ha, [S("span", Ua, "共 " + b(P($)(P(f)?.target_count)) + " 个账号 · 当前页 " + b(P(p)?.items.length || 0) + " 个", 1), d(ne, {
					items: ae.value,
					onRemove: n[9] ||= (e) => P(l).setFilter("")
				}, null, 8, ["items"])]),
				d(oa, {
					ref_key: "targetTable",
					ref: G,
					scope: [
						P(u).batch_id,
						P(u).round_id,
						P(u).result_state,
						P(u).cursor
					].join(":"),
					items: P(p)?.items || [],
					selected: P(C),
					loading: P(E) || P(T) && !P(f),
					error: P(N),
					"result-state": P(u).result_state || "",
					"result-counts": P(B),
					"result-total": P(f)?.target_count,
					"result-states": Y,
					"open-task": e.deps.callbacks.openTask,
					onFilter: P(l).setFilter,
					onToggle: P(l).toggleTarget,
					onSelectPage: P(l).selectPage,
					onRetry: P(l).loadTargets
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
				d(Ke, {
					"has-previous": P(W),
					"next-cursor": P(ee),
					"item-count": P(p)?.items.length || 0,
					"has-cursor": !!P(u).cursor,
					busy: P(E),
					label: "账号明细分页",
					onNext: P(l).next,
					onPrevious: P(l).previous,
					onFirst: P(l).first
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
			d(P(Le), {
				open: !!P(z),
				"onUpdate:open": n[11] ||= (e) => {
					e || P(l).cancelConfirmation();
				}
			}, {
				default: a(() => [d(P(Ie), null, {
					default: a(() => [d(P(Fe), { class: "bulk-vue-overlay" }), d(P(Me), {
						class: "bulk-vue-dialog",
						onCloseAutoFocus: fe
					}, {
						default: a(() => [
							d(P(Re), null, {
								default: a(() => [R(b(P(z)?.title), 1)]),
								_: 1
							}),
							d(P(Pe), null, {
								default: a(() => [R(b(P(z)?.description), 1)]),
								_: 1
							}),
							S("p", null, "范围：" + b(P(z)?.scopeLabel) + " · 预计账号：" + b(P(z)?.count) + " 个", 1),
							S("div", Wa, [d(P(Ne), {
								class: "jobs-tb-btn",
								"data-confirm-cancel": "",
								onClick: P(l).cancelConfirmation
							}, {
								default: a(() => [...n[24] ||= [R("返回", -1)]]),
								_: 1
							}, 8, ["onClick"]), S("button", {
								type: "button",
								class: "jobs-tb-btn jobs-tb-btn--danger",
								"data-confirm-submit": "",
								onClick: n[10] ||= (...e) => P(l).confirm && P(l).confirm(...e)
							}, b(P(z)?.label), 1)])
						]),
						_: 1
					})]),
					_: 1
				})]),
				_: 1
			}, 8, ["open"])
		], 8, sa));
	}
}), [["__scopeId", "data-v-d412d46e"]]), Ka = [
	"batch_id",
	"round_id",
	"result_state",
	"cursor",
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
], qa = /* @__PURE__ */ new Set([
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
]);
function Ja(e = {}) {
	let t = [
		"list",
		"create",
		"detail"
	].includes(e.view || "") ? e.view : "list", n = {
		tab: "bulk",
		view: t
	};
	for (let t of Ka) typeof e[t] == "string" && e[t] && (n[t] = e[t]);
	if (t === "detail") {
		if (!/^[1-9]\d*$/.test(n.batch_id || "")) return {
			tab: "bulk",
			view: "list"
		};
		(n.q || e.reason_code) && (delete n.q, delete n.cursor), n.result_state && qa.has(n.result_state) && (n.result_state = "failed");
	}
	return n;
}
// src/features/bulk/BulkPageShell.vue?vue&type=script&setup=true&lang.ts
var Ya = {
	class: "bulk-page bulk-page-shell",
	"data-bulk-vue": ""
}, Xa = { class: "bulk-page-heading" }, Za = { "data-bulk-title": "" }, Qa = { class: "bulk-actions" }, $a = {
	key: 0,
	class: "bulk-error",
	"data-bulk-error": "",
	role: "alert"
}, eo = {
	key: 1,
	class: "bulk-notice",
	"data-bulk-notice": "",
	role: "status"
}, to = {
	key: 2,
	class: "bulk-notice bulk-global-recovery",
	"data-bulk-recovery": "",
	role: "status"
}, no = ["disabled"], ro = { "data-bulk-content": "" }, io = /*#__PURE__*/ F(/* @__PURE__ */ n({
	__name: "BulkPageShell",
	props: {
		deps: {},
		initialNavigation: {}
	},
	setup(e, { expose: n }) {
		let r = e, a = A(Ja(r.initialNavigation)), c = y(!1), u = y(!1), f = y(""), p = y(""), h = y(!1), g = y(0), _ = A(null), v = y(null), x = y(null), C = y(null), T = !1, E = 0, D = 0, k = !1, j, M = null, P = "", F = !1, I = O(() => c.value && u.value), R = {
			...r.deps.callbacks,
			navigate: (e, t, n) => {
				Y(e, t, n);
			},
			updateNavigation: (e) => {
				ae(e);
			},
			notify: (e) => {
				p.value = e, g.value++, r.deps.callbacks.notify(e);
			},
			copyBatch: (e, t, n) => {
				oe(e, t, n);
			}
		}, z = {
			pending: () => r.deps.intents.pending(),
			submit: async (e, t, n) => {
				try {
					return await r.deps.intents.submit(e, t, n);
				} finally {
					g.value++;
				}
			},
			recover: async (e) => {
				try {
					return await r.deps.intents.recover(e);
				} finally {
					g.value++;
				}
			}
		}, B = {
			api: r.deps.api,
			callbacks: R
		}, V = {
			...r.deps,
			intents: z,
			callbacks: R
		}, H = {
			api: r.deps.api,
			intents: z,
			callbacks: R,
			now: r.deps.now
		}, U = O(() => {
			g.value;
			try {
				return r.deps.intents.pending();
			} catch {
				return [];
			}
		}), W = O(() => I.value ? a.value.view === "list" ? 7e3 : a.value.view === "create" ? x.value?.needsRefresh ? 2e3 : 0 : C.value?.needsRefresh ? 2e3 : 0 : 0), ee = O(() => a.value.view === "list" ? "批量任务" : a.value.view === "create" ? "新建批次" : `批次 #${a.value.batch_id}`);
		function G() {
			u.value = !document.hidden && (r.deps.isVisible?.() ?? !0), k !== I.value && (D++, k = I.value), v.value?.setVisible(I.value && a.value.view === "list"), x.value?.setVisible(I.value && a.value.view === "create"), C.value?.setVisible(I.value && a.value.view === "detail");
		}
		function K() {
			clearTimeout(j), j = void 0, !T && W.value && (j = setTimeout(() => {
				j = void 0, G(), I.value && q(!1);
			}, W.value));
		}
		async function q(e = !0) {
			if (await t(), T || (G(), !I.value)) return;
			let n = JSON.stringify([a.value, D]);
			if (M && P === n) return M;
			let r = (async () => {
				try {
					a.value.view === "list" ? await v.value?.refresh(!e) : a.value.view === "create" ? await x.value?.refresh(e) : (await C.value?.refresh(e), F && (F = !1, await C.value?.showReport()));
				} finally {
					g.value++;
				}
			})();
			M = r, P = n;
			try {
				await r;
			} finally {
				M === r && (M = null, P = ""), K();
			}
		}
		async function J() {
			c.value = !0, await q(!1);
		}
		async function te() {
			a.value.view === "detail" && (F = !0, await q(!1));
		}
		function ne(e) {
			c.value = e, G(), K();
		}
		function re() {
			return { ...a.value };
		}
		function ie(e) {
			E++, a.value = Ja(e), f.value = "", p.value = "", F = !1;
		}
		async function Y(e, t = {}, n = !1) {
			ie({
				tab: "bulk",
				view: e,
				...t
			}), F = n, c.value = !0, r.deps.onNavigation(re(), "push"), await q(!1);
		}
		async function ae(e) {
			E++, a.value = Ja({
				...a.value,
				...e
			}), r.deps.onNavigation(re(), Object.keys(e).every((e) => e === "cursor") ? "replace" : "push"), await t(), K();
		}
		async function oe(e, t, n = "plan_check") {
			let i = JSON.parse(JSON.stringify({
				query: e,
				source: t
			}));
			_.value = {
				name: "",
				operation_key: n,
				query: r.deps.adapter.normalize({
					...i.query,
					limit: null
				}),
				source: i.source,
				parameters: {},
				max_concurrency: 3
			}, await Y("create");
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
			await oe(r.deps.adapter.normalize(), null);
		}
		async function le(e, n) {
			await t(), x.value?.restoreSelectionRequest(e, n);
		}
		async function ue() {
			if (h.value) return;
			h.value = !0, f.value = "";
			let e = E;
			try {
				let t = r.deps.intents.pending()[0];
				if (!t) return;
				let n = await r.deps.intents.recover(t);
				if (T || e !== E || !I.value) {
					let e = n.id || n.batch_id || n.round_id;
					R.notify(t.path === "/batches" ? `原批次 #${X(e)} 已创建` : `原请求回执已找回${e ? "，编号 #" + String(e) : ""}。`);
					return;
				}
				if (t.path === "/selections") _.value = null, await le(t.body, n), await Y("create"), R.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
				else if (t.path === "/batches") {
					try {
						r.deps.storage.removeItem("turb_bulk_selection_v1");
					} catch {}
					await Y("detail", { batch_id: X(n.id || n.batch_id) });
				} else {
					let e = t.path.match(/^\/batches\/([1-9]\d*)\//);
					e && await Y("detail", { batch_id: e[1] }), R.notify("原请求回执已找回。");
				}
			} catch (e) {
				f.value = e instanceof Error ? e.message : String(e);
			} finally {
				h.value = !1, g.value++;
			}
		}
		function de() {
			let e = I.value;
			G(), !e && I.value ? q(!1) : K();
		}
		return o(W, K, { flush: "post" }), l(() => {
			G(), document.addEventListener("visibilitychange", de);
		}), w(() => {
			T = !0, clearTimeout(j), document.removeEventListener("visibilitychange", de);
		}), n({
			activate: J,
			setVisible: ne,
			refresh: q,
			showReport: te,
			navigationState: re,
			restoreNavigation: ie,
			navigate: Y,
			fromAccounts: se,
			recover: ue,
			restoreSelectionRequest: le
		}), (e, t) => (i(), L("div", Ya, [
			S("header", Xa, [S("h2", Za, b(ee.value), 1), S("div", Qa, [
				a.value.view === "list" ? m("", !0) : (i(), L("button", {
					key: 0,
					type: "button",
					class: "jobs-tb-btn",
					onClick: t[0] ||= (e) => Y("list")
				}, "批次列表")),
				S("button", {
					type: "button",
					class: "jobs-tb-btn",
					"data-bulk-action": "refresh",
					onClick: t[1] ||= (e) => q(!0)
				}, "刷新"),
				S("button", {
					type: "button",
					class: "jobs-tb-btn jobs-tb-btn--primary",
					"data-bulk-action": "new",
					onClick: ce
				}, "新建批次")
			])]),
			f.value ? (i(), L("p", $a, b(f.value), 1)) : m("", !0),
			p.value ? (i(), L("p", eo, b(p.value), 1)) : m("", !0),
			U.value.length && a.value.view !== "create" ? (i(), L("div", to, [S("span", null, "有 " + b(U.value.length) + " 个请求未收到回执，草稿已保留。", 1), S("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: h.value,
				onClick: ue
			}, b(h.value ? "正在找回…" : "找回原请求"), 9, no)])) : m("", !0),
			S("div", ro, [
				s(d(Bt, {
					ref_key: "list",
					ref: v,
					navigation: a.value,
					deps: B
				}, null, 8, ["navigation"]), [[N, a.value.view === "list"]]),
				s(d(fr, {
					ref_key: "create",
					ref: x,
					navigation: a.value,
					deps: V,
					seed: _.value,
					visible: I.value && a.value.view === "create"
				}, null, 8, [
					"navigation",
					"seed",
					"visible"
				]), [[N, a.value.view === "create"]]),
				s(d(Ga, {
					ref_key: "detail",
					ref: C,
					navigation: a.value,
					deps: H,
					visible: I.value && a.value.view === "detail"
				}, null, 8, ["navigation", "visible"]), [[N, a.value.view === "detail"]])
			])
		]));
	}
}), [["__scopeId", "data-v-32a8fcf3"]]), ao = "turb_bulk_intent:", oo = /* @__PURE__ */ new Set([
	400,
	403,
	404,
	409,
	410,
	422,
	429
]);
function so(e, t, n) {
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
		let c = ao + a, l = JSON.stringify({
			path: o,
			body: s
		}), u = r.get(c);
		if (u) {
			if (u.signature !== l) throw new Vt("上一请求未收到回执，请先找回原请求，再提交新内容。", 0, "request_receipt_pending");
			return u.promise;
		}
		let d = i(c, t.getItem(c));
		if (d && d.signature !== l) throw new Vt("上一请求未收到回执，请先找回原请求，再提交新内容。", 0, "request_receipt_pending");
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
			if (oo.has(Number(e?.status))) try {
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
				if (r?.startsWith(ao)) {
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
// src/features/bulk/mountBulkReport.ts
function co(e, t) {
	e.replaceChildren();
	function n(t) {
		M(r(Oi, { ...t }), e);
	}
	return n(t), {
		setView: n,
		destroy() {
			M(null, e);
		}
	};
}
// src/bulk.ts
var lo = /* @__PURE__ */ new WeakMap();
function uo(e, t) {
	let n = lo.get(e);
	if (n) return n;
	let r = fo(e, t);
	return lo.set(e, r), r;
}
function fo(e, t) {
	let n = Ht(), r = {
		get length() {
			return window.sessionStorage.length;
		},
		key: (e) => window.sessionStorage.key(e),
		getItem: (e) => window.sessionStorage.getItem(e),
		setItem: (e, t) => window.sessionStorage.setItem(e, t),
		removeItem: (e) => window.sessionStorage.removeItem(e)
	}, i = so(n, r, () => globalThis.crypto?.randomUUID?.() || `bulk-${Date.now()}-${Math.random().toString(36).slice(2)}`), a = k(io, {
		initialNavigation: t.navigation,
		deps: {
			api: n,
			intents: i,
			storage: r,
			adapter: de(t.query),
			callbacks: t.callbacks,
			onNavigation: t.onNavigation,
			isVisible: t.isVisible,
			now: Date.now
		}
	}), o = a.mount(e);
	return Object.assign(o, {
		request: n.request,
		intent: i.submit,
		destroy() {
			a.unmount(), lo.delete(e);
		}
	});
}
function po(e, i) {
	let a = A(i.view), o = A(), s = k(n({ setup: () => () => r(Bt, {
		ref: o,
		navigation: a.value,
		deps: {
			api: Ht(),
			callbacks: i.callbacks
		}
	}) }));
	return s.mount(e), {
		setView(e) {
			a.value = e;
		},
		setVisible(e) {
			o.value?.setVisible(e), e && t(() => o.value?.refresh());
		},
		refresh(e = !1) {
			return o.value?.refresh(e);
		},
		destroy() {
			s.unmount();
		}
	};
}
export { uo as mountBulk, po as mountBulkList, co as mountBulkReport };
