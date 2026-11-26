import { $ as e, A as t, C as n, E as r, F as i, G as a, H as o, K as s, L as c, M as l, R as u, S as d, T as f, Z as p, _ as m, a as h, c as g, d as _, dt as v, et as y, f as b, ft as x, g as S, h as C, it as w, j as T, k as E, l as D, lt as O, m as k, n as A, nt as j, o as M, r as N, s as P, st as F, t as I, ut as L, v as R, x as z } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { C as B, S as V, _ as H, b as U, d as W, f as ee, g as G, h as K, i as q, l as J, m as Y, n as te, p as ne, r as re, t as ie, u as ae, v as oe, x as se, y as ce } from "./ListFilterSummary-C8E03t1K.js";
import { t as le } from "./useNativeDialog-DWisXYg9.js";
import { a as ue, c as de, n as fe, o as pe, s as me, t as he } from "./queryAdapter-_IDct2p7.js";
import { t as ge } from "./errorLabels-fdGNkTBr.js";
// node_modules/reka-ui/dist/Dialog/DialogRoot.js
var [X, _e] = /*#__PURE__*/ B("DialogRoot"), ve = /* @__PURE__ */ n({
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
		let n = e, r = se(n, "open", t, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		}), i = y(), a = y(), { modal: o, unmountOnHide: s } = w(n);
		return _e({
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
			open: F(r),
			close: () => r.value = !1
		});
	}
}), ye = /* @__PURE__ */ n({
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
		let n = X();
		return (r, o) => (i(), S(F(ee), E(t, {
			type: e.as === "button" ? "button" : void 0,
			onClick: o[0] ||= (e) => F(n).onOpenChange(!1)
		}), {
			default: a(() => [u(r.$slots, "default")]),
			_: 3
		}, 16, ["type"]));
	}
}), be = ["Enter", " "], xe = [
	"ArrowDown",
	"PageUp",
	"Home"
], Se = [
	"ArrowUp",
	"PageDown",
	"End"
];
[...xe, ...Se], [...be], [...be];
function Ce(e) {
	return e ? "open" : "closed";
}
// node_modules/reka-ui/dist/Dialog/DialogContentImpl.js
var we = /* @__PURE__ */ n({
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
		let n = e, r = t, o = X(), { forwardRef: s, currentElement: c } = H();
		return o.titleId ||= Y(void 0, "reka-dialog-title"), o.descriptionId ||= Y(void 0, "reka-dialog-description"), l(() => {
			o.contentElement = c, V() !== document.body && (o.triggerElement.value = V());
		}), (t, c) => (i(), S(F(ae), {
			"as-child": "",
			loop: "",
			trapped: n.trapFocus,
			present: n.present,
			onMountAutoFocus: c[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: c[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: a(() => [d(F(W), E({
				id: F(o).contentId,
				ref: F(s),
				as: e.as,
				"as-child": e.asChild,
				present: n.present,
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				role: "dialog",
				"aria-describedby": F(o).descriptionId,
				"aria-labelledby": F(o).titleId,
				"data-state": F(Ce)(F(o).open.value)
			}, t.$attrs, {
				onDismiss: c[0] ||= (e) => F(o).onOpenChange(!1),
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
}), Te = /* @__PURE__ */ n({
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
		let n = e, r = t, s = X(), c = oe(r), { forwardRef: l, currentElement: d } = H(), f = k(() => n.present ? d.value : void 0);
		K(f);
		let p = k(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return o(() => n.present, (e, t) => {
			!e && t && s.triggerElement.value?.focus();
		}), (t, r) => (i(), S(we, E({
			...p.value,
			...F(c)
		}, {
			ref: F(l),
			present: e.present,
			"trap-focus": F(s).open.value,
			"disable-outside-pointer-events": n.disableOutsidePointerEvents,
			onCloseAutoFocus: r[0] ||= (e) => {
				e.defaultPrevented || (e.preventDefault(), F(s).triggerElement.value?.focus());
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
}), Ee = /* @__PURE__ */ n({
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
		let n = e, r = oe(t);
		H();
		let s = X(), c = y(!1), l = y(!1), d = k(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return o(() => n.present, (e, t) => {
			!e && t && (c.value || s.triggerElement.value?.focus(), c.value = !1, l.value = !1);
		}), (t, n) => (i(), S(we, E({
			...d.value,
			...F(r)
		}, {
			present: e.present,
			"trap-focus": !1,
			"disable-outside-pointer-events": !1,
			onCloseAutoFocus: n[0] ||= (e) => {
				e.defaultPrevented || (c.value || F(s).triggerElement.value?.focus(), e.preventDefault()), c.value = !1, l.value = !1;
			},
			onInteractOutside: n[1] ||= (e) => {
				e.defaultPrevented || (c.value = !0, e.detail.originalEvent.type === "pointerdown" && (l.value = !0));
				let t = e.target;
				F(s).triggerElement.value?.contains(t) && e.preventDefault(), e.detail.originalEvent.type === "focusin" && l.value && e.preventDefault();
			}
		}), {
			default: a(() => [u(t.$slots, "default")]),
			_: 3
		}, 16, ["present"]));
	}
}), De = /* @__PURE__ */ n({
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
		let n = e, r = t, o = X(), c = oe(r), { forwardRef: l } = H(), d = k(() => n.forceMount || !o.unmountOnHide.value);
		return (t, r) => (i(), S(F(ne), {
			present: F(o).open.value,
			"force-mount": d.value
		}, {
			default: a(({ present: r }) => [F(o).modal.value ? s((i(), S(Te, E({
				key: 0,
				ref: F(l),
				present: !d.value || r
			}, {
				...n,
				...F(c),
				...t.$attrs
			}), {
				default: a(() => [u(t.$slots, "default")]),
				_: 3
			}, 16, ["present"])), [[P, e.forceMount || F(o).unmountOnHide.value || r]]) : s((i(), S(Ee, E({
				key: 1,
				ref: F(l),
				present: !d.value || r
			}, {
				...n,
				...F(c),
				...t.$attrs
			}), {
				default: a(() => [u(t.$slots, "default")]),
				_: 3
			}, 16, ["present"])), [[P, e.forceMount || F(o).unmountOnHide.value || r]])]),
			_: 3
		}, 8, ["present", "force-mount"]));
	}
}), Oe = /* @__PURE__ */ n({
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
		let n = X();
		return (e, r) => (i(), S(F(ee), E(t, { id: F(n).descriptionId }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), ke = /* @__PURE__ */ n({
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
		let t = e, n = X(), r = ce(t.present);
		return o(() => t.present, (e) => r.value = e), H(), (t, r) => (i(), S(F(ee), {
			as: e.as,
			"as-child": e.asChild,
			"data-state": F(n).open.value ? "open" : "closed",
			style: { "pointer-events": "auto" },
			onPointerdown: r[0] ||= D(() => {}, [
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
}), Ae = /* @__PURE__ */ n({
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
		let t = e, n = X(), { forwardRef: r } = H(), o = k(() => t.forceMount || !n.unmountOnHide.value);
		return (t, c) => F(n)?.modal.value ? (i(), S(F(ne), {
			key: 0,
			present: F(n).open.value,
			"force-mount": o.value
		}, {
			default: a(({ present: i }) => [s(d(ke, E(t.$attrs, {
				ref: F(r),
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
			]), [[P, e.forceMount || F(n).unmountOnHide.value || i]])]),
			_: 3
		}, 8, ["present", "force-mount"])) : m("v-if", !0);
	}
}), je = /* @__PURE__ */ n({
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
		return (e, n) => (i(), S(F(J), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Me = /* @__PURE__ */ n({
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
		let t = e, n = X();
		return H(), (e, r) => (i(), S(F(ee), E(t, { id: F(n).titleId }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), [Ne, Pe] = /*#__PURE__*/ B("AlertDialogContent"), Fe = /* @__PURE__ */ n({
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
		let r = e, o = oe(n);
		H();
		let s = y();
		return Pe({ onCancelElementChange: (e) => {
			s.value = e;
		} }), (e, n) => (i(), S(F(De), E({
			...r,
			...F(o)
		}, {
			role: "alertdialog",
			onPointerDownOutside: n[0] ||= D(() => {}, ["prevent"]),
			onInteractOutside: n[1] ||= D(() => {}, ["prevent"]),
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
}), Ie = /* @__PURE__ */ n({
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
		let t = e, n = Ne(), { forwardRef: r, currentElement: o } = H();
		return l(() => {
			n.onCancelElementChange(o.value);
		}), (e, n) => (i(), S(F(ye), E(t, { ref: F(r) }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Le = /* @__PURE__ */ n({
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
		return H(), (e, n) => (i(), S(F(Oe), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Re = /* @__PURE__ */ n({
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
		return H(), (e, n) => (i(), S(F(Ae), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), ze = /* @__PURE__ */ n({
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
		return (e, n) => (i(), S(F(J), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Be = /* @__PURE__ */ n({
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
		let n = G(e, t);
		return H(), (e, t) => (i(), S(F(ve), E(F(n), { modal: !0 }), {
			default: a((t) => [u(e.$slots, "default", L(f(t)))]),
			_: 3
		}, 16));
	}
}), Ve = /* @__PURE__ */ n({
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
		return H(), (e, n) => (i(), S(F(Me), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), He = ["aria-label", "aria-busy"], Ue = { class: "cursor-pagination__layout" }, We = {
	class: "cursor-pagination__count",
	"aria-live": "polite"
}, Ge = { class: "cursor-pagination__actions" }, Ke = ["disabled"], qe = ["disabled"], Je = ["disabled"], Ye = /*#__PURE__*/ I(/* @__PURE__ */ n({
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
		return (t, n) => (i(), R("nav", {
			class: "cursor-pagination",
			"aria-label": e.label,
			"aria-busy": e.busy
		}, [C("div", Ue, [C("span", We, "本页 " + x(e.itemCount) + " 个", 1), C("div", Ge, [
			e.hasCursor ? (i(), R("button", {
				key: 0,
				type: "button",
				class: "cursor-pagination__first",
				"data-cursor-first": "",
				disabled: e.busy,
				onClick: s
			}, "返回首页", 8, Ke)) : m("", !0),
			C("button", {
				type: "button",
				"data-cursor-previous": "",
				disabled: e.busy || !e.hasPrevious,
				onClick: a
			}, "上一页", 8, qe),
			C("button", {
				type: "button",
				"data-cursor-next": "",
				disabled: e.busy || !e.nextCursor,
				onClick: o
			}, "下一页", 8, Je)
		])])], 8, He));
	}
}), [["__scopeId", "data-v-07618f56"]]);
// src/features/bulk/contracts.ts
function Z(e) {
	if (typeof e != "string" || !/^[1-9]\d*$/.test(e)) throw Error("任务标识无效");
	return e;
}
function Xe(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("批次列表响应格式无效");
	return e;
}
function Ze(e) {
	let t = Xe(e);
	if (!Array.isArray(t.items)) throw Error("批次列表响应格式无效");
	let n = t.items.map((e) => {
		let t = Xe(e), n = Number.isSafeInteger(t.id) ? String(t.id) : t.id;
		if (typeof n != "string" || !/^[1-9]\d*$/.test(n)) throw Error("批次编号无效");
		return {
			...t,
			id: n
		};
	}), r = t.next_cursor ?? (t.page == null ? null : Xe(t.page).next_cursor);
	if (r != null && typeof r != "string") throw Error("批次分页响应格式无效");
	return {
		items: n,
		summary: t.summary == null ? {} : Xe(t.summary),
		nextCursor: r || null
	};
}
// src/features/bulk/useBulkList.ts
var Qe = [
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
];
function $e(e) {
	let t = {
		tab: "bulk",
		view: "list",
		cursor: e.cursor || ""
	};
	for (let n of Qe) t[n] = e[n] || "";
	return t;
}
function et(e, t) {
	let n = /* @__PURE__ */ new Date(`${e}T00:00:00`), [r, i, a] = e.split("-").map(Number);
	if (!/^\d{4}-\d{2}-\d{2}$/.test(e) || n.getFullYear() !== r || n.getMonth() + 1 !== i || n.getDate() !== a) throw Error("创建日期无效，请调整筛选条件");
	return t && n.setDate(n.getDate() + 1), n.toISOString();
}
function tt(e) {
	let t = new URLSearchParams({ page_size: "20" });
	return e.cursor && t.set("cursor", e.cursor), e.q && t.set("q", e.q), e.operation && t.set("operation_key[]", e.operation), e.state && t.set("control_state[]", e.state), e.created_from && t.set("created_from", et(e.created_from, !1)), e.created_to && t.set("created_before", et(e.created_to, !0)), t;
}
function nt(t, n) {
	let r = j($e(t())), i = j(null), a = j([]), s = k(() => a.value.length > 0), c = y(!1), l = y(!1), u = y(""), d = !1, f, m;
	function h() {
		f?.abort(), f = void 0, m = void 0, l.value = !1;
	}
	function g(e) {
		return e.cursor === r.value.cursor && Qe.every((t) => e[t] === r.value[t]) ? !1 : (h(), r.value = e, i.value = null, u.value = "", !0);
	}
	function _(e = !1, a) {
		if (d || !c.value || t().view !== "list") return Promise.resolve();
		if (m) return m;
		let o = new AbortController();
		return f = o, l.value = !0, m = (async () => {
			try {
				let t = await n.api.request(`/batches?${tt(r.value)}`, {
					method: "GET",
					signal: o.signal
				});
				if (o.signal.aborted || a && !a()) return;
				let s = i.value, c = Ze(t);
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
		return g($e({
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
		e.view === "list" ? g($e(e)) && (a.value = [], c.value && _()) : h();
	}, { deep: !0 }), p(() => {
		d = !0, h();
	}), {
		navigation: e(r),
		items: k(() => i.value?.items ?? []),
		summary: k(() => i.value?.summary ?? {}),
		nextCursor: k(() => i.value?.nextCursor ?? null),
		loading: e(l),
		visible: e(c),
		error: e(u),
		hasPrevious: s,
		stale: k(() => !i.value),
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
var rt = ["aria-busy"], it = {
	key: 0,
	class: "bl-kpis"
}, at = {
	key: 1,
	class: "ui-list-toolbar bl-toolbar"
}, ot = { class: "ui-list-toolbar__main bl-toolbar-main" }, st = { class: "ui-list-toolbar__actions" }, ct = {
	key: 2,
	class: "ui-list-feedback is-error bl-error",
	role: "alert"
}, lt = ["disabled"], ut = ["disabled"], dt = ["disabled"], ft = { class: "ui-table ui-table--sticky-end bl-table" }, pt = { class: "bl-col-name" }, mt = { class: "list-filter-actions" }, ht = { class: "list-filter-options" }, gt = { class: "list-filter-option" }, _t = ["checked"], vt = [
	"value",
	"checked",
	"onChange"
], yt = { class: "list-filter-options" }, bt = { class: "list-filter-option" }, xt = ["checked"], St = [
	"value",
	"checked",
	"onChange"
], Ct = { class: "bl-filter-fields" }, wt = ["value"], Tt = ["value"], Et = { class: "list-filter-actions" }, Dt = ["data-bulk-row"], Ot = { class: "bl-col-name" }, kt = [
	"disabled",
	"title",
	"onClick"
], At = ["title"], jt = { "data-bulk-progress": "" }, Mt = { class: "bl-progress-copy" }, Nt = [
	"value",
	"max",
	"aria-label"
], Pt = {
	key: 1,
	class: "bl-secondary"
}, Ft = { class: "bl-results" }, It = ["disabled", "onClick"], Lt = ["disabled", "onClick"], Rt = { class: "bl-date" }, zt = ["disabled", "onClick"], Bt = /*#__PURE__*/ I(/* @__PURE__ */ n({
	__name: "BulkList",
	props: {
		navigation: {},
		deps: {}
	},
	setup(e, { expose: t }) {
		let n = e, r = nt(() => n.navigation, n.deps), { navigation: l, items: u, summary: f, nextCursor: p, loading: h, visible: g, error: v, hasPrevious: b, stale: w } = r, T = y(null), E = y(""), A = y(), j = {
			plan_check: "查询套餐",
			token_refresh: "刷新 AT",
			password_setup: "补密码",
			twofa_setup: "补 2FA",
			codex_retry: "补 Codex",
			account_completion: "组合补全"
		}, N = (e) => e === "active" || e === "settling" ? "active" : [
			"paused",
			"cancel_requested",
			"stop_requested"
		].includes(e) ? "warning" : "neutral", P = {
			active: "执行中",
			paused: "已暂停",
			cancel_requested: "取消中",
			stop_requested: "停止中",
			ended: "已结束"
		}, I = {
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
		], B = [
			"attention_required",
			"request_unknown",
			"manual_reconcile",
			"unknown",
			"unconfirmed"
		];
		function V(e) {
			return e && typeof e == "object" && !Array.isArray(e) ? e : {};
		}
		function H(e) {
			return typeof e == "number" && Number.isFinite(e) && e >= 0 ? e : null;
		}
		function U(e, t = "—") {
			return e == null || e === "" ? t : String(e);
		}
		let W = k(() => u.value.map((e) => {
			let t = V(e.summary ?? e.counts), r = {};
			for (let [e, n] of Object.entries(t)) H(n) !== null && (r[e] = n);
			let i = H(e.target_count), a = i === 0 || Object.keys(r).length > 0;
			for (let e of B) e in r && (r.failed = (r.failed || 0) + r[e], delete r[e]);
			let o = V(e.control), s = V(e.operation), c = o.paused ?? e.is_paused ? "paused" : U(o.state ?? e.control_state ?? e.state, "preparing"), l = U(s.key ?? e.operation_key ?? e.action_key), u = e.id, d = a ? L.reduce((e, t) => e + (r[t] || 0), 0) : null, f = i === null || d === null ? null : i === 0 ? 0 : Math.min(100, Math.round(100 * d / i));
			return {
				id: u,
				name: U(e.name ?? e.title, `批次 #${u}`),
				operation: j[l] || l,
				state: c,
				status: I[c] || c,
				counts: r,
				known: a,
				done: d,
				total: i,
				percent: f,
				createdAt: n.deps.callbacks.formatDateTime(e.created_at)
			};
		})), ee = k(() => {
			let e = [
				{
					key: "active_batches",
					label: "执行中",
					value: H(f.value.active_batches),
					unit: "批"
				},
				{
					key: "ended_batches",
					label: "已结束",
					value: H(f.value.ended_batches),
					unit: "批"
				},
				{
					key: "failed_targets",
					label: "失败账号",
					value: H(f.value.failed_targets),
					unit: "个"
				}
			], t = H(f.value.attention_targets);
			return t != null && e[2].value != null && (e[2].value += t), e.filter((e) => e.value !== null);
		}), G = k(() => {
			let e = l.value;
			return [
				["q", e.q ? `批次：${e.q}` : ""],
				["operation", e.operation ? `操作：${j[e.operation] || e.operation}` : ""],
				["state", e.state ? `状态：${P[e.state] || e.state}` : ""],
				["date", e.created_from || e.created_to ? `创建日期：${e.created_from || "不限"} 至 ${e.created_to || "不限"}` : ""]
			].filter(([, e]) => e).map(([e, t]) => ({
				key: e,
				label: t,
				removeLabel: `移除${t}`
			}));
		});
		o(() => l.value.q, (e) => {
			E.value = e || "";
		}, { immediate: !0 }), o(() => n.navigation.view, () => {
			T.value = null;
		});
		function K(e) {
			e === "date" ? r.applyFilters({
				created_from: "",
				created_to: ""
			}) : r.applyFilters({ [e]: "" });
		}
		function J(e, t) {
			r.applyFilters({ [e]: t });
		}
		function Y() {
			r.applyFilters({ q: E.value.trim() }), T.value = null;
		}
		function ne(e, t) {
			g.value && !w.value && n.deps.callbacks.navigate("detail", {
				batch_id: e,
				...t ? { result_state: t } : {}
			});
		}
		function re(e) {
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
		}), (t, n) => (i(), R("section", {
			class: "ui-list bl-root",
			"aria-label": "批次列表",
			"aria-busy": F(h)
		}, [
			ee.value.length ? (i(), R("div", it, [(i(!0), R(_, null, c(ee.value, (e) => (i(), R("div", {
				key: e.key,
				class: O(["bl-kpi", { "is-warning": e.key === "failed_targets" && !!e.value }])
			}, [C("span", null, x(e.label), 1), C("strong", null, [z(x(e.value), 1), C("small", null, x(e.unit), 1)])], 2))), 128))])) : m("", !0),
			G.value.length ? (i(), R("div", at, [C("div", ot, [d(ie, {
				items: G.value,
				onRemove: K
			}, null, 8, ["items"])]), C("div", st, [C("button", {
				type: "button",
				class: "ui-link",
				onClick: n[0] ||= (...e) => F(r).resetFilters && F(r).resetFilters(...e)
			}, "清除筛选")])])) : m("", !0),
			F(v) ? (i(), R("div", ct, [
				C("span", null, x(F(v)), 1),
				C("button", {
					type: "button",
					class: "ui-link",
					disabled: F(h),
					onClick: n[1] ||= (e) => F(r).refresh()
				}, "重试", 8, lt),
				F(w) && F(l).cursor ? (i(), R("button", {
					key: 0,
					class: "ui-link",
					type: "button",
					disabled: F(h),
					onClick: n[2] ||= (...e) => F(r).first && F(r).first(...e)
				}, " 返回首页", 8, ut)) : m("", !0),
				F(w) && F(b) ? (i(), R("button", {
					key: 1,
					class: "ui-link",
					type: "button",
					disabled: F(h),
					onClick: n[3] ||= (...e) => F(r).previous && F(r).previous(...e)
				}, " 上一页 ", 8, dt)) : m("", !0)
			])) : m("", !0),
			C("div", {
				ref_key: "tableHost",
				ref: A,
				class: "ui-table-scroll bl-table-wrap",
				tabindex: "0",
				role: "region",
				"aria-label": "批次列表内容"
			}, [C("table", ft, [C("thead", null, [C("tr", null, [
				C("th", pt, [d(q, {
					label: "批次名称或编号",
					"trigger-label": "批次",
					active: !!F(l).q,
					summary: F(l).q,
					open: T.value === "q",
					"onUpdate:open": n[6] ||= (e) => T.value = e ? "q" : null
				}, {
					default: a(() => [C("form", {
						class: "bl-filter-fields",
						onSubmit: D(Y, ["prevent"])
					}, [C("label", null, [n[16] ||= z("名称或批次号", -1), s(C("input", {
						"onUpdate:modelValue": n[4] ||= (e) => E.value = e,
						type: "search",
						placeholder: "搜索批次名称或编号",
						autocomplete: "off"
					}, null, 512), [[M, E.value]])]), C("div", mt, [C("button", {
						type: "button",
						onClick: n[5] ||= (e) => K("q")
					}, "清除此列"), n[17] ||= C("button", {
						class: "list-filter-primary",
						type: "submit"
					}, "查询", -1)])], 32)]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				C("th", null, [d(q, {
					label: "操作类型",
					active: !!F(l).operation,
					summary: j[F(l).operation || ""] || F(l).operation,
					open: T.value === "operation",
					"onUpdate:open": n[8] ||= (e) => T.value = e ? "operation" : null
				}, {
					default: a(() => [C("fieldset", ht, [
						n[19] ||= C("legend", { class: "ui-sr-only" }, "操作类型", -1),
						C("label", gt, [C("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: "",
							checked: !F(l).operation,
							onChange: n[7] ||= (e) => J("operation", "")
						}, null, 40, _t), n[18] ||= z("全部操作", -1)]),
						(i(), R(_, null, c(j, (e, t) => C("label", {
							class: "list-filter-option",
							key: t
						}, [C("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: t,
							checked: F(l).operation === t,
							onChange: (e) => J("operation", t)
						}, null, 40, vt), z(x(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				C("th", null, [d(q, {
					label: "状态",
					active: !!F(l).state,
					summary: P[F(l).state || ""] || F(l).state,
					open: T.value === "state",
					"onUpdate:open": n[10] ||= (e) => T.value = e ? "state" : null
				}, {
					default: a(() => [C("fieldset", yt, [
						n[21] ||= C("legend", { class: "ui-sr-only" }, "运行状态", -1),
						C("label", bt, [C("input", {
							type: "radio",
							name: "bulk-list-state",
							value: "",
							checked: !F(l).state,
							onChange: n[9] ||= (e) => J("state", "")
						}, null, 40, xt), n[20] ||= z("全部状态", -1)]),
						(i(), R(_, null, c(P, (e, t) => C("label", {
							class: "list-filter-option",
							key: t
						}, [C("input", {
							type: "radio",
							name: "bulk-list-state",
							value: t,
							checked: F(l).state === t,
							onChange: (e) => J("state", t)
						}, null, 40, St), z(x(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				n[24] ||= C("th", null, "完成进度", -1),
				n[25] ||= C("th", null, "当前结果", -1),
				C("th", null, [d(q, {
					label: "创建时间",
					active: !!(F(l).created_from || F(l).created_to),
					summary: `${F(l).created_from || "不限"} 至 ${F(l).created_to || "不限"}`,
					open: T.value === "date",
					"onUpdate:open": n[14] ||= (e) => T.value = e ? "date" : null
				}, {
					default: a(() => [C("div", Ct, [
						C("label", null, [n[22] ||= z("开始日期", -1), C("input", {
							type: "date",
							value: F(l).created_from,
							onChange: n[11] ||= (e) => J("created_from", e.target.value)
						}, null, 40, wt)]),
						C("label", null, [n[23] ||= z("截止日期", -1), C("input", {
							type: "date",
							value: F(l).created_to,
							onChange: n[12] ||= (e) => J("created_to", e.target.value)
						}, null, 40, Tt)]),
						C("div", Et, [C("button", {
							type: "button",
							onClick: n[13] ||= (e) => K("date")
						}, "清除此列")])
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				n[26] ||= C("th", null, "操作", -1)
			])]), C("tbody", null, [(i(!0), R(_, null, c(W.value, (e) => (i(), R("tr", {
				key: e.id,
				"data-bulk-row": e.id
			}, [
				C("td", Ot, [C("button", {
					type: "button",
					class: "ui-link bl-name",
					"data-bulk-open": "",
					disabled: F(w),
					title: e.name,
					onClick: (t) => ne(e.id)
				}, x(e.name), 9, kt), C("span", {
					class: "bl-secondary",
					title: `批次 #${e.id}`
				}, "#" + x(e.id), 9, At)]),
				C("td", null, x(e.operation), 1),
				C("td", null, [C("span", { class: O(["ui-badge bl-status", `ui-badge--${N(e.state)}`]) }, x(e.status), 3)]),
				C("td", jt, [e.total !== null && e.done !== null ? (i(), R(_, { key: 0 }, [C("span", Mt, [z(x(e.done) + " / " + x(e.total) + " ", 1), C("span", null, x(e.percent) + "%", 1)]), C("progress", {
					value: e.done,
					max: Math.max(1, e.total),
					"aria-label": `已结束 ${e.done} 个，共 ${e.total} 个`
				}, null, 8, Nt)], 64)) : (i(), R("span", Pt, x(e.total === null ? "名单准备中" : "结果待汇总"), 1))]),
				C("td", null, [C("div", Ft, [C("button", {
					type: "button",
					class: "bl-result is-success",
					"data-bulk-result": "success",
					disabled: F(w) || !e.counts.success,
					onClick: (t) => ne(e.id, "success")
				}, " 成功 " + x(e.known ? e.counts.success || 0 : "—"), 9, It), C("button", {
					type: "button",
					class: "bl-result is-failed",
					"data-bulk-result": "failed",
					disabled: F(w) || !e.counts.failed,
					onClick: (t) => ne(e.id, "failed")
				}, " 失败 " + x(e.known ? e.counts.failed || 0 : "—"), 9, Lt)])]),
				C("td", Rt, x(e.createdAt), 1),
				C("td", null, [C("button", {
					type: "button",
					class: "ui-link",
					"data-bulk-report": "",
					disabled: F(w),
					onClick: (t) => re(e.id)
				}, " 查看报告 ", 8, zt)])
			], 8, Dt))), 128)), W.value.length ? m("", !0) : (i(), S(te, {
				key: 0,
				colspan: 7,
				loading: F(h),
				error: F(v) ? " " : "",
				"loading-title": "正在加载批次…",
				"error-title": "暂时无法读取批次",
				title: G.value.length ? "没有匹配的批次" : "还没有批次",
				text: "选择操作和账号范围，即可集中执行与追踪结果。"
			}, {
				default: a(() => [!F(h) && !F(v) ? (i(), R("button", {
					key: 0,
					type: "button",
					class: "ui-button ui-button--primary",
					"data-bulk-create": "",
					onClick: n[15] ||= (t) => e.deps.callbacks.navigate("create")
				}, "新建批次")) : m("", !0)]),
				_: 1
			}, 8, [
				"loading",
				"error",
				"title"
			]))])])], 512),
			F(w) ? m("", !0) : (i(), S(Ye, {
				key: 3,
				"has-previous": F(b),
				"next-cursor": F(p),
				"item-count": F(u).length,
				"has-cursor": !!F(l).cursor,
				busy: F(h),
				label: "批次分页",
				onPrevious: F(r).previous,
				onNext: F(r).next,
				onFirst: F(r).first
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
		], 8, rt));
	}
}), [["__scopeId", "data-v-5ead5018"]]), Vt = class extends Error {
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
	}, r = y(t()), i = y(null), a = y(null), o = y({}), s = y(null), c = y(!1), l = y(!1), u = y(!1), d = y(""), f = y(""), m = y(""), h = y(0), g = /* @__PURE__ */ new Map(), _ = /* @__PURE__ */ new Set(), v = 0, b = !1, x = !0, S = !1, C = null, w = null, T = null, E = null, D, O = k(() => a.value?.operations || []), A = k(() => O.value.find((e) => e.key === r.value.operation_key)), j = k(() => String(A.value?.effective_settings?.config_revision ?? A.value?.config_revision ?? a.value?.config_revision ?? "")), M = k(() => i.value?.state || i.value?.status || ""), N = k(() => M.value === "preparing"), P = k(() => Number(a.value?.limits?.concurrency_max) || 128), F = k(() => {
		h.value;
		try {
			return e.intents.pending().length;
		} catch {
			return 1;
		}
	}), I = k(() => M.value === "ready" ? Number(i.value?.target_count ?? i.value?.total_count) : r.value.source?.kind === "ids" ? r.value.source.ids.length : r.value.source ? null : s.value), L = k(() => r.value.source?.kind === "ids" ? `已选 ${r.value.source.ids.length} 个账号` : r.value.source?.kind === "batch_targets" ? `批次 #${r.value.source.batch_id} 的固定名单` : r.value.query.filters.email ? `邮箱含「${r.value.query.filters.email}」` : "按当前筛选"), R = k(() => l.value ? "正在固定账号范围…" : M.value === "ready" ? "账号范围已固定" : I.value === 0 ? "没有匹配账号" : "匹配账号数量"), z = k(() => l.value ? "正在准备本批次，请稍候" : M.value === "ready" ? "将使用这份固定名单创建批次" : I.value === 0 ? "请调整账号筛选条件" : r.value.source?.kind === "batch_targets" ? "创建时沿用原批次固定名单" : r.value.source?.kind === "ids" ? "将使用已选账号创建批次" : s.value == null ? "正在统计，创建时会核对最终数量" : `当前条件匹配 ${s.value} 个账号，将全部执行`), B = k(() => A.value?.availability?.available === !1 ? `当前设置不可用：${A.value.availability.reason || Kt(A.value.availability).reason_code || "请检查配置"}。请到配置页调整。` : "");
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
	async function Y(t) {
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
	async function te(e = !1) {
		if (a.value && !e) return;
		let t = await Y("/catalog");
		b || (a.value = t, O.value.some((e) => e.key === r.value.operation_key) || (r.value.operation_key = O.value[0]?.key || "", i.value = null, H(), V()));
	}
	async function ne() {
		if (!x || b) return;
		let t = v, n = JSON.stringify(e.adapter.normalize(r.value.query)), i = g.get(n);
		if (i && e.now() - i.at < 3e4) {
			o.value = i.facets, s.value = i.matched;
			return;
		}
		s.value = null;
		let a = await Y(`/query-facets?query=${encodeURIComponent(n)}`), c = Kt(a.facets || a), l = a.matched == null ? null : Number(a.matched);
		g.set(n, {
			facets: c,
			matched: l,
			at: e.now()
		}), g.size > 10 && g.delete(g.keys().next().value), !b && t === v && n === JSON.stringify(e.adapter.normalize(r.value.query)) && (o.value = c, s.value = l);
	}
	function re() {
		if (clearTimeout(D), !x) return;
		let e = v;
		D = setTimeout(() => {
			ne().catch((t) => {
				!q(t) && !b && e === v && K(t, "筛选选项更新失败：");
			});
		}, 350);
	}
	function ie() {
		v++, E = null, l.value = !1, i.value = null, H();
	}
	function ae(e) {
		ie(), clearTimeout(D), ee(Gt(e), null), s.value = null, G(), S && re();
	}
	function oe(e, t) {
		l.value || (e === "name" ? r.value.name = String(t) : r.value.max_concurrency = Number(t), V());
	}
	function se(e) {
		l.value || r.value.operation_key === e || (r.value.operation_key = e, ie(), G(), V());
	}
	function ce(t) {
		if (l.value) return;
		let n = e.adapter.normalize({
			...t,
			limit: null
		});
		JSON.stringify(n) !== JSON.stringify(r.value.query) && (r.value.query = n, s.value = null, ie(), G(), V(), re());
	}
	function le(e, t) {
		let n = Gt(r.value.query);
		[
			"q",
			"archived",
			"date_from",
			"date_to",
			"plan"
		].includes(e) ? Object.assign(n, { [e]: t }) : Object.assign(n.filters, { [e]: t }), ce(n);
	}
	function de(e) {
		e === "date" ? ce({
			...r.value.query,
			date_from: "",
			date_to: ""
		}) : le(e, e === "archived" ? "0" : [
			"q",
			"email",
			"id"
		].includes(e) ? "" : []);
	}
	function he() {
		l.value || (r.value.source = null, r.value.query = e.adapter.normalize(), s.value = null, ie(), G(), V(), re());
	}
	function ge(t, n) {
		return e.callbacks.facetLabel?.(t, n) || n;
	}
	function X(e) {
		let t = a.value?.query_schema?.fields, n = Array.isArray(t) ? t.map(Kt).find((t) => t.key === e) : void 0, i = n?.options ?? n?.enum ?? n?.values, s = o.value[e] ?? (Array.isArray(i) ? i : []), c = /* @__PURE__ */ new Map();
		for (let t of s) {
			let n = typeof t == "object" && t ? t : { value: String(t) };
			n.value && c.set(n.value, {
				...n,
				label: n.label || ge(e === "token" ? "account_token" : e, n.value)
			});
		}
		if (e === "promotion") {
			let t = pe.map((t) => ({
				value: t,
				count: c.get(t)?.count ?? void 0,
				label: ge(e, t)
			}));
			for (let n of me(r.value.query, e)) t.some((e) => e.value === n) || t.push({
				value: n,
				count: 0,
				label: ge(e, n)
			});
			return t;
		}
		for (let t of me(r.value.query, e)) c.has(t) || c.set(t, {
			value: t,
			label: ge(e === "token" ? "account_token" : e, t)
		});
		return [...c.values()];
	}
	let _e = k(() => [
		...ue(r.value.query, ge),
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
	function ve() {
		let e = A.value?.parameter_schema;
		return e?.timezone_offset_min || Kt(e?.properties).timezone_offset_min ? { timezone_offset_min: (/* @__PURE__ */ new Date()).getTimezoneOffset() } : {};
	}
	async function ye() {
		if (!i.value || !x || b) return;
		let e = Z(i.value.id), t = v, n = await Y(`/selections/${encodeURIComponent(e)}?page_size=1`);
		b || t !== v || i.value?.id !== e || (i.value = {
			...i.value,
			...n
		}, H());
	}
	async function be() {
		if (x && !b) {
			if (C) return C;
			if (!S) return c.value = !0, C = (async () => {
				try {
					if (await te(), b || !x) return;
					let e = v;
					try {
						await ne();
					} catch (t) {
						if (q(t)) return;
						e === v && K(t, "筛选选项读取失败：");
					}
					!b && e === v && i.value && await ye(), S = !0;
				} catch (e) {
					!q(e) && !b && K(e, "读取配置失败：");
				} finally {
					c.value = !1, C = null;
				}
			})(), C;
		}
	}
	async function xe(t, n) {
		if (q(t) || b || n !== v) return;
		E = null, l.value = !1, K(t, "创建失败：");
		let r = t;
		if (["config_revision_changed", "selection_settings_mismatch"].includes(r.code)) {
			i.value = null, H();
			try {
				await te(!0);
			} catch (e) {
				K(e, "配置读取失败：");
			}
			!b && n === v && e.callbacks.notify("配置已更新，请重新创建批次。");
		} else r.code === "selection_consumed" && r.details?.existing_batch_id ? (m.value = String(r.details.existing_batch_id), e.callbacks.notify(`该范围已用于批次 #${m.value}`)) : r.code === "selection_expired" && (i.value = null, H());
	}
	async function Se() {
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
				selection_id: Z(a.id),
				selection_revision: a.selection_revision,
				operation: {
					key: o.key,
					version: o.version || 1
				},
				expected_config_revision: a.config_revision || j.value,
				parameters: a.request_parameters || ve(),
				execution: {
					max_concurrency: Number(r.value.max_concurrency),
					start_paused: t.paused
				}
			}, c = await e.intents.submit("create", "/batches", s), u = Z(c.id || c.batch_id);
			if (b || n !== v) {
				e.callbacks.notify(`原批次 #${u} 已创建${t.paused ? "并暂停" : ""}`);
				return;
			}
			i.value = null, H(), E = null, l.value = !1, e.callbacks.notify(x ? t.paused ? "批次已创建并暂停，可在详情继续执行" : "批次已受理，正在后台提交目标" : `原批次 #${u} 已创建${t.paused ? "并暂停" : ""}`), x && e.callbacks.navigate("detail", { batch_id: u });
		} catch (e) {
			await xe(e, n);
		} finally {
			h.value++, T === n && (T = null);
		}
	}
	async function Ce(t = !1) {
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
					parameters: ve(),
					expected_config_revision: j.value
				}, o = await e.intents.submit("selection", "/selections", n);
				if (b || a !== v) return;
				i.value = {
					...o,
					request_parameters: n.parameters,
					config_revision: n.expected_config_revision
				}, H(), V();
			}
			M.value === "preparing" && await ye(), !b && a === v && await Se();
		} catch (e) {
			await xe(e, a);
		} finally {
			h.value++;
		}
	}
	async function we(e = !1) {
		if (b || !x) return;
		if (w?.epoch === v) return w.promise;
		let t = v, n = (async () => {
			let n = !S;
			if (n && await be(), !b && x && S && t === v) try {
				e && await te(!0), n || (i.value ? await ye() : await ne()), t === v && await Se();
			} catch (e) {
				!q(e) && t === v && (E ? await xe(e, t) : K(e, "读取账号范围失败："));
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
	function Te(n, r) {
		let i = Kt(n.source), a = Kt(n.operation), o = e.adapter.normalize(i.kind === "query" ? Kt(i.query) : {}), s = {
			...t(),
			operation_key: String(a.key || "plan_check"),
			query: o,
			source: i.kind === "query" ? null : i
		};
		ie(), ee(s, {
			...r,
			request_parameters: Kt(n.parameters),
			config_revision: n.expected_config_revision
		});
	}
	async function Ee() {
		if (u.value || l.value || b) return;
		u.value = !0, G();
		let t = v;
		try {
			let n = e.intents.pending()[0];
			if (!n) return;
			let r = await e.intents.recover(n);
			if (b || t !== v || !x) {
				e.callbacks.notify(n.path === "/batches" ? `原批次 #${Z(r.id || r.batch_id)} 已创建` : "原请求回执已找回，当前草稿保留。");
				return;
			}
			if (n.path === "/selections") Te(n.body, r), e.callbacks.navigate("create"), e.callbacks.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
			else if (n.path === "/batches") i.value = null, H(), e.callbacks.navigate("detail", { batch_id: Z(r.id || r.batch_id) });
			else {
				let t = n.path.match(/^\/batches\/(\d+)\//);
				t && e.callbacks.navigate("detail", { batch_id: Z(t[1]) }), e.callbacks.notify("原请求回执已找回。");
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
		operations: O,
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
		accountFilters: fe,
		initialize: be,
		refresh: we,
		recover: Ee,
		restoreSelectionRequest: Te,
		loadFacets: ne,
		applySeed: ae,
		setVisible: J,
		setDraftField: oe,
		setOperation: se,
		setQueryField: le,
		clearFilter: de,
		clearFilters: he,
		filterOptions: X,
		createBatch: Ce,
		clearError: G
	};
}
// src/features/bulk/BulkCreate.vue?vue&type=script&setup=true&lang.ts
var Jt = {
	key: 0,
	class: "bulk-empty",
	role: "status"
}, Yt = ["aria-busy"], Xt = { class: "bulk-create-main" }, Zt = { class: "bulk-card bulk-create-card" }, Qt = { class: "bulk-step-head" }, $t = {
	class: "bulk-operation-grid",
	role: "radiogroup",
	"aria-label": "批量操作"
}, en = ["title"], tn = [
	"value",
	"checked",
	"disabled",
	"onChange"
], nn = {
	viewBox: "0 0 24 24",
	fill: "none",
	stroke: "currentColor",
	"stroke-width": "1.6",
	"stroke-linecap": "round",
	"stroke-linejoin": "round",
	"aria-hidden": "true"
}, rn = ["d"], an = { class: "bulk-card bulk-create-card" }, on = {
	key: 0,
	class: "bulk-error bulk-operation-warning",
	"data-bulk-operation-warning": ""
}, sn = { class: "bulk-batch-fields" }, cn = { class: "bulk-field bulk-name-field" }, ln = [
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], un = { class: "bulk-field" }, dn = [
	"max",
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], fn = {
	class: "bulk-card bulk-create-card",
	"data-bulk-account-scope": ""
}, pn = { class: "bulk-step-head" }, mn = ["disabled"], hn = {
	key: 0,
	class: "bulk-source-banner"
}, gn = ["disabled"], _n = { "data-bulk-filters": "" }, vn = { class: "bulk-query-top" }, yn = { class: "bulk-field bulk-query-search" }, bn = ["value", "disabled"], xn = ["open"], Sn = { class: "bulk-filter-popover-panel" }, Cn = { class: "bulk-filter-popover-heading" }, wn = { class: "bulk-field" }, Tn = ["value", "disabled"], En = { class: "bulk-field" }, Dn = ["value", "disabled"], On = ["open"], kn = { class: "bulk-filter-popover-panel" }, An = { class: "bulk-filter-popover-heading" }, jn = { class: "bulk-field" }, Mn = ["value", "disabled"], Nn = { class: "bulk-field" }, Pn = ["value", "disabled"], Fn = {
	class: "bulk-column-filters",
	"aria-label": "账号列筛选"
}, In = ["data-filter-field", "open"], Ln = ["onClick"], Rn = {
	key: 0,
	"data-filter-count": ""
}, zn = { class: "bulk-filter-popover-panel" }, Bn = { class: "bulk-filter-popover-heading" }, Vn = ["aria-label"], Hn = {
	key: 0,
	class: "bulk-field"
}, Un = [
	"data-query-filter",
	"value",
	"disabled",
	"onInput"
], Wn = {
	key: 1,
	class: "bulk-filter-options"
}, Gn = [
	"data-query-filter",
	"value",
	"checked",
	"disabled",
	"onChange"
], Kn = {
	key: 0,
	class: "bulk-muted"
}, qn = {
	class: "bulk-query-chips",
	"data-query-chips": "",
	"aria-label": "已选账号条件"
}, Jn = [
	"data-clear-query",
	"aria-label",
	"disabled",
	"onClick"
], Yn = {
	key: 0,
	class: "bulk-filter-empty"
}, Xn = { class: "bulk-card bulk-create-side" }, Zn = { class: "bulk-side-sticky" }, Qn = { class: "bulk-side-heading" }, $n = { "data-bulk-create-summary": "" }, er = {
	class: "bulk-side-big",
	"data-bulk-side-count": "",
	role: "status",
	"aria-live": "polite",
	"aria-atomic": "true"
}, tr = {
	class: "bulk-side-hint",
	"data-bulk-create-hint": ""
}, nr = { class: "bulk-side-meta" }, rr = { "data-bulk-side-operation": "" }, ir = { "data-bulk-side-scope": "" }, ar = { "data-bulk-side-concurrency": "" }, or = {
	key: 0,
	class: "bulk-side-warning",
	"data-bulk-side-warning": ""
}, sr = {
	key: 1,
	id: "bulkCreateError",
	class: "bulk-error",
	"data-bulk-action-error": "",
	role: "alert"
}, cr = {
	key: 2,
	class: "bulk-notice",
	"data-bulk-recovery": "",
	role: "status"
}, lr = ["disabled"], ur = { class: "bulk-side-actions" }, dr = ["disabled"], fr = ["disabled"], pr = /* @__PURE__ */ n({
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
		let r = e, a = qt(r.deps), { draft: u, loading: d, creating: f, recovering: p, error: h, errorField: v, existingBatchId: b, operations: S, operation: w, concurrencyMax: T, pendingCount: E, count: A, scopeLabel: j, summary: M, hint: N, availabilityWarning: I, chips: L, needsRefresh: B } = a, V = y(), H = y(""), U = k(() => f.value || p.value), W = a.accountFilters.filter((e) => !["email", "date"].includes(e.key)), ee = {
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
			let r = new Set(me(u.value.query, e));
			n ? r.add(t) : r.delete(t), a.setQueryField(e, [...r]);
		}
		function J(e) {
			let t = (e?.target)?.closest("details");
			H.value = "", (t?.querySelector("summary"))?.focus();
		}
		function Y(e, t) {
			if (U.value) return;
			if (H.value === e) {
				H.value = "";
				return;
			}
			let n = t.currentTarget, r = n.nextElementSibling, i = n.getBoundingClientRect().left, a = Math.min(250, window.innerWidth - 48), o = Math.max(10, document.querySelector("main")?.getBoundingClientRect().left ?? 0), s = Math.max(o, Math.min(i, document.documentElement.clientWidth - a - 10));
			r.style.setProperty("--bulk-filter-offset", `${s - i}px`), H.value = e;
		}
		function te(e) {
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
		}), (t, n) => F(d) && !F(S).length ? (i(), R("div", Jt, "正在读取操作和筛选配置…")) : (i(), R("form", {
			key: 1,
			ref_key: "form",
			ref: V,
			"data-bulk-create-form": "",
			class: "bulk-create-form",
			novalidate: "",
			"aria-busy": U.value,
			onSubmit: n[18] ||= D((e) => F(a).createBatch(), ["prevent"]),
			onKeydown: n[19] ||= g((e) => J(e), ["esc"])
		}, [C("div", Xt, [
			C("section", Zt, [C("div", Qt, [
				n[20] ||= C("span", { class: "bulk-step-no" }, "1", -1),
				n[21] ||= C("div", null, [C("h3", null, "选择操作"), C("p", { class: "bulk-section-note" }, "本次要对账号做什么")], -1),
				C("button", {
					type: "button",
					class: "bulk-link",
					"data-bulk-action": "list",
					onClick: n[0] ||= (t) => e.deps.callbacks.navigate("list")
				}, "← 返回批次列表")
			]), C("div", $t, [(i(!0), R(_, null, c(F(S), (e) => (i(), R("label", {
				key: e.key,
				class: "bulk-operation",
				title: e.availability?.available === !1 ? e.availability.reason || "当前不可用" : ""
			}, [
				C("input", {
					type: "radio",
					name: "operation_key",
					value: e.key,
					checked: F(u).operation_key === e.key,
					disabled: U.value,
					required: "",
					onChange: (t) => F(a).setOperation(e.key)
				}, null, 40, tn),
				(i(), R("svg", nn, [C("path", { d: G[e.key] || G.account_completion }, null, 8, rn)])),
				C("span", null, [C("strong", null, x(e.label || e.key), 1), C("small", null, x(ee[e.key] || "批量账号操作"), 1)]),
				n[22] ||= C("span", {
					class: "bulk-operation-check",
					"aria-hidden": "true"
				}, "✓", -1)
			], 8, en))), 128))])]),
			C("section", an, [
				n[25] ||= C("div", { class: "bulk-step-head" }, [C("span", { class: "bulk-step-no" }, "2"), C("div", null, [C("h3", null, "批次设置")])], -1),
				F(I) ? (i(), R("p", on, x(F(I)), 1)) : m("", !0),
				C("div", sn, [C("label", cn, [n[23] ||= z("批次名称", -1), C("input", {
					name: "name",
					maxlength: "120",
					value: F(u).name,
					placeholder: "留空自动命名",
					disabled: U.value,
					"aria-invalid": F(v) === "name" || void 0,
					"aria-describedby": F(v) === "name" ? "bulkCreateError" : void 0,
					onInput: n[1] ||= (e) => F(a).setDraftField("name", K(e))
				}, null, 40, ln)]), C("label", un, [n[24] ||= z("本批并发上限", -1), C("input", {
					name: "max_concurrency",
					type: "number",
					min: "1",
					max: F(T),
					step: "1",
					value: F(u).max_concurrency,
					required: "",
					disabled: U.value,
					"aria-invalid": F(v) === "max_concurrency" || void 0,
					"aria-describedby": F(v) === "max_concurrency" ? "bulkCreateError" : void 0,
					onInput: n[2] ||= (e) => F(a).setDraftField("max_concurrency", K(e))
				}, null, 40, dn)])])
			]),
			C("section", fn, [
				C("div", pn, [
					n[26] ||= C("span", { class: "bulk-step-no" }, "3", -1),
					n[27] ||= C("div", null, [C("h3", null, "账号范围"), C("p", { class: "bulk-section-note" }, "与账号列表使用同一套筛选")], -1),
					C("button", {
						type: "button",
						class: "bulk-link",
						"data-bulk-action": "clear-filters",
						disabled: U.value,
						onClick: n[3] ||= (...e) => F(a).clearFilters && F(a).clearFilters(...e)
					}, "清空条件", 8, mn)
				]),
				F(u).source ? (i(), R("div", hn, [C("span", null, x(F(u).source.kind === "ids" ? "使用已选账号" : `沿用批次 #${F(u).source.batch_id} 的账号名单`), 1), C("button", {
					type: "button",
					class: "bulk-link",
					"data-bulk-action": "use-query",
					disabled: U.value,
					onClick: n[4] ||= (...e) => F(a).clearFilters && F(a).clearFilters(...e)
				}, "改为按条件筛选", 8, gn)])) : m("", !0),
				s(C("div", _n, [
					C("div", vn, [
						C("label", yn, [n[28] ||= C("span", { class: "bulk-sr-only" }, "邮箱或姓名", -1), C("input", {
							"data-query": "email",
							type: "search",
							value: F(u).query.filters.email,
							autocomplete: "off",
							placeholder: "搜索邮箱或姓名",
							disabled: U.value,
							onInput: n[5] ||= (e) => F(a).setQueryField("email", K(e))
						}, null, 40, bn)]),
						C("details", {
							class: "bulk-filter-popover",
							"data-filter-dates": "",
							open: H.value === "date",
							onFocusout: te
						}, [C("summary", { onClick: n[6] ||= D((e) => Y("date", e), ["prevent"]) }, [...n[29] ||= [z("创建日期", -1), C("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [C("path", { d: "m4 6 4 4 4-4" })], -1)]]), C("div", Sn, [
							C("div", Cn, [n[30] ||= C("strong", null, "创建日期", -1), C("button", {
								type: "button",
								"aria-label": "关闭创建日期筛选",
								onClick: n[7] ||= (e) => J(e)
							}, "完成")]),
							C("label", wn, [n[31] ||= z("创建日期从", -1), C("input", {
								"data-query": "date_from",
								type: "date",
								value: F(u).query.date_from,
								disabled: U.value,
								onInput: n[8] ||= (e) => F(a).setQueryField("date_from", K(e))
							}, null, 40, Tn)]),
							C("label", En, [n[32] ||= z("创建日期至（含当天）", -1), C("input", {
								"data-query": "date_to",
								type: "date",
								value: F(u).query.date_to,
								disabled: U.value,
								onInput: n[9] ||= (e) => F(a).setQueryField("date_to", K(e))
							}, null, 40, Dn)])
						])], 40, xn),
						C("details", {
							class: "bulk-filter-popover",
							open: H.value === "more",
							onFocusout: te
						}, [C("summary", { onClick: n[10] ||= D((e) => Y("more", e), ["prevent"]) }, [...n[33] ||= [z("更多查询", -1), C("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [C("path", { d: "m4 6 4 4 4-4" })], -1)]]), C("div", kn, [
							C("div", An, [n[34] ||= C("strong", null, "更多查询", -1), C("button", {
								type: "button",
								"aria-label": "关闭更多查询筛选",
								onClick: n[11] ||= (e) => J(e)
							}, "完成")]),
							C("label", jn, [n[35] ||= z("高级搜索", -1), C("input", {
								"data-query": "q",
								type: "search",
								value: F(u).query.q,
								placeholder: "如：协议 jp",
								autocomplete: "off",
								disabled: U.value,
								onInput: n[12] ||= (e) => F(a).setQueryField("q", K(e))
							}, null, 40, Mn)]),
							C("label", Nn, [n[37] ||= z("归档范围", -1), C("select", {
								"data-query": "archived",
								value: F(u).query.archived,
								disabled: U.value,
								onChange: n[13] ||= (e) => F(a).setQueryField("archived", K(e))
							}, [...n[36] ||= [
								C("option", { value: "0" }, "未归档", -1),
								C("option", { value: "only" }, "仅归档", -1),
								C("option", { value: "all" }, "全部", -1)
							]], 40, Pn)])
						])], 40, On)
					]),
					C("div", Fn, [(i(!0), R(_, null, c(F(W), (e) => (i(), R("details", {
						key: e.key,
						class: O(["bulk-filter-popover", { "has-value": e.kind === "text" ? !!F(de)(F(u).query, e.key) : !!F(me)(F(u).query, e.key).length }]),
						"data-filter-field": e.key,
						open: H.value === e.key,
						onFocusout: te
					}, [C("summary", { onClick: D((t) => Y(e.key, t), ["prevent"]) }, [
						z(x(e.label), 1),
						e.kind === "enum" && F(me)(F(u).query, e.key).length ? (i(), R("span", Rn, x(F(me)(F(u).query, e.key).length), 1)) : m("", !0),
						n[38] ||= C("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [C("path", { d: "m4 6 4 4 4-4" })], -1)
					], 8, Ln), C("div", zn, [C("div", Bn, [C("strong", null, x(e.label), 1), C("button", {
						type: "button",
						"aria-label": `关闭${e.label}筛选`,
						onClick: n[14] ||= (e) => J(e)
					}, "完成", 8, Vn)]), e.kind === "text" ? (i(), R("label", Hn, [z(x(e.label), 1), C("input", {
						"data-query-filter": e.key,
						value: F(de)(F(u).query, e.key),
						inputmode: "numeric",
						placeholder: "输入账号 ID",
						disabled: U.value,
						onInput: (t) => F(a).setQueryField(e.key, K(t))
					}, null, 40, Un)])) : (i(), R("div", Wn, [(i(!0), R(_, null, c(F(a).filterOptions(e.key), (t) => (i(), R("label", { key: t.value }, [C("input", {
						type: "checkbox",
						"data-query-filter": e.key,
						value: t.value,
						checked: F(me)(F(u).query, e.key).includes(t.value),
						disabled: U.value,
						onChange: (n) => q(e.key, t.value, n.target.checked)
					}, null, 40, Gn), C("span", null, x(t.label), 1)]))), 128)), F(a).filterOptions(e.key).length ? m("", !0) : (i(), R("span", Kn, "暂无可用选项"))]))])], 42, In))), 128))]),
					C("div", qn, [(i(!0), R(_, null, c(F(L), (e) => (i(), R("button", {
						key: e.key,
						type: "button",
						class: "bulk-filter-chip",
						"data-clear-query": e.key,
						"aria-label": e.removeLabel,
						disabled: U.value,
						onClick: (t) => F(a).clearFilter(e.key)
					}, [z(x(e.label), 1), n[39] ||= C("span", { "aria-hidden": "true" }, "×", -1)], 8, Jn))), 128)), F(L).length ? m("", !0) : (i(), R("span", Yn, "全部未归档账号"))])
				], 512), [[P, !F(u).source]])
			])
		]), C("aside", Xn, [C("div", Zn, [
			C("div", Qn, [C("div", null, [n[40] ||= C("span", { class: "bulk-side-kicker" }, "执行摘要", -1), C("strong", $n, x(F(M)), 1)])]),
			C("div", er, x(F(A) == null ? F(u).source ? "创建时确认" : "匹配中" : `${F(A)} 个`), 1),
			C("p", tr, x(F(N)), 1),
			C("dl", nr, [
				C("div", null, [n[41] ||= C("dt", null, "操作", -1), C("dd", rr, x(F(w)?.label || F(u).operation_key), 1)]),
				C("div", null, [n[42] ||= C("dt", null, "范围", -1), C("dd", ir, x(F(j)), 1)]),
				C("div", null, [n[43] ||= C("dt", null, "本批并发", -1), C("dd", ar, x(F(u).max_concurrency), 1)])
			]),
			F(A) != null && F(A) >= 200 ? (i(), R("p", or, "本批将处理 " + x(F(A)) + " 个账号。", 1)) : m("", !0),
			F(h) ? (i(), R("p", sr, [z(x(F(h)), 1), F(b) ? (i(), R("button", {
				key: 0,
				type: "button",
				class: "bulk-link",
				onClick: n[15] ||= (t) => e.deps.callbacks.navigate("detail", { batch_id: F(b) })
			}, "查看批次 #" + x(F(b)), 1)) : m("", !0)])) : m("", !0),
			F(E) ? (i(), R("div", cr, [C("span", null, "有 " + x(F(E)) + " 个请求未收到回执，草稿已保留。", 1), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: U.value,
				onClick: n[16] ||= (...e) => F(a).recover && F(a).recover(...e)
			}, x(F(p) ? "正在找回…" : "找回原请求"), 9, lr)])) : m("", !0),
			C("div", ur, [C("button", {
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				"data-bulk-submit": "",
				disabled: U.value || F(A) === 0 || !F(S).length
			}, x(F(f) ? "正在创建批次…" : "创建并执行"), 9, dr), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "create-paused",
				disabled: U.value || F(A) === 0 || !F(S).length,
				onClick: n[17] ||= (e) => F(a).createBatch(!0)
			}, x(F(f) ? "正在创建批次…" : "创建并暂停"), 9, fr)]),
			n[44] ||= C("p", { class: "bulk-side-foot" }, "提交时固定账号范围，暂停后可继续原批次", -1)
		])])], 40, Yt));
	}
}), mr = {
	plan_check: "查套餐",
	token_refresh: "刷新 AT",
	password_setup: "补密码",
	twofa_setup: "补 2FA",
	codex_retry: "补 Codex",
	account_completion: "组合补全"
}, Q = (e) => typeof e == "object" && e && !Array.isArray(e) ? e : {}, hr = (e) => Array.isArray(e) ? e.map(Q) : [], gr = (e) => mr[String(e)] || String(e || "—");
function _r(e) {
	if (typeof e != "number" && (typeof e != "string" || !e.trim())) return null;
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? t : null;
}
var $ = (e) => _r(e) === null ? "—" : Math.floor(Number(e)).toLocaleString("zh-CN");
function vr(e) {
	let t = _r(e);
	if (t === null) return "—";
	if (t < 60) return `${t === 0 ? "0" : t < 1 ? t.toFixed(2) : t.toFixed(1).replace(/\.0$/, "")} 秒`;
	let n = Math.round(t), r = Math.floor(n / 3600), i = Math.floor(n % 3600 / 60), a = n % 60;
	return [
		r ? `${r} 小时` : "",
		i ? `${i} 分` : "",
		a ? `${a} 秒` : ""
	].filter(Boolean).join(" ") || "0 秒";
}
function yr(e) {
	let t = Q(e.view);
	if (t.kind !== "round") return "当前结果 · 每个账号取最近一轮";
	let n = _r(t.round_no);
	return n === null || !Number.isSafeInteger(n) || n < 1 ? "所选轮次 · 固定名单" : n === 1 ? "首轮名单" : `重跑 ${n - 1} · 固定名单`;
}
var br = {
	free: "Free",
	plus: "Plus",
	pro: "Pro",
	team: "Team",
	business: "Business",
	enterprise: "Enterprise",
	go: "Go",
	unknown: "尚未确认"
}, xr = {
	free_trial: "免费试用",
	half_price: "半价优惠",
	discount: "折扣优惠",
	other_discount: "其他折扣",
	other_promo: "其他优惠"
};
function Sr(e, t, n) {
	let r = typeof t == "string" ? t : "";
	return Object.hasOwn(e, r) ? e[r] : r || n;
}
var Cr = (e) => Sr(br, e, "尚未确认"), wr = (e) => Sr(xr, e, "其他优惠");
function Tr(e, t) {
	return `${Math.max(0, Math.min(100, t > 0 ? (_r(e) || 0) / t * 100 : 0))}%`;
}
var Er = {
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
	...xr
})) Er[`account.plus_offer.${e}`] = `优惠 · ${t}`;
for (let [e, t] of Object.entries({
	unchanged: "优惠未变化",
	new_offer: "新增优惠",
	offer_removed: "优惠消失",
	changed: "优惠变化",
	not_comparable: "历史条件不可比较"
})) Er[`account.comparison.${e}`] = t;
for (let [e, t] of Object.entries({
	password: "密码",
	twofa: "2FA",
	codex: "Codex",
	access_token: "AT",
	plan_check: "套餐"
})) Er[`step.${e}.confirmed`] = `${t} · 已完成`, Er[`step.${e}.pending`] = `${t} · 待完成`;
function Dr(e) {
	let t = { ...Q(e) };
	Object.hasOwn(t, "account.token_refresh.unconfirmed") && (t["account.token_refresh.failed"] = (_r(t["account.token_refresh.failed"]) || 0) + (_r(t["account.token_refresh.unconfirmed"]) || 0), delete t["account.token_refresh.unconfirmed"]);
	let n = /* @__PURE__ */ new Map();
	function r(e, t = "", i = 0) {
		if (!(i > 3)) for (let [a, o] of Object.entries(e)) {
			if ([
				"schema",
				"schema_version",
				"version",
				"updated_at"
			].includes(a)) continue;
			let e = Sr(Er, a, a), s = t ? `${t} · ${e}` : e;
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
			} else o && typeof o == "object" && r(Q(o), s, i + 1);
		}
	}
	return r(t), [...n.values()];
}
// src/features/bulk/bulkDetailPresentation.ts
var Or = {
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
}, kr = [
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
], Ar = (e) => "is-" + (kr.includes(String(e)) ? "failed" : String(e || "preparing")), jr = (e) => {
	let t = Ar(e).slice(3);
	return t === "success" ? "success" : t === "failed" ? "danger" : [
		"attention_required",
		"partial_success",
		"paused"
	].includes(t) ? "warning" : [
		"running",
		"active",
		"preparing"
	].includes(t) ? "active" : "neutral";
}, Mr = (e) => Or[kr.includes(String(e)) ? "failed" : String(e)] || String(e || "—"), Nr = (e) => String(Q(e?.operation).key || e?.operation_key || e?.action_key || "");
function Pr(e) {
	let t = {};
	for (let [n, r] of Object.entries(Q(e))) {
		let e = kr.includes(n) ? "failed" : n;
		t[e] = (t[e] || 0) + (_r(r) || 0);
	}
	return t;
}
var Fr = (e) => Z(e.canonical_target_id || e.target_id || e.id);
function Ir(e) {
	return e == null || e === "" ? null : Z(e);
}
function Lr(e) {
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
		let t = [`查询${Mr(e.query_outcome)}`];
		return e.account_plan_type && t.push(`套餐 ${e.account_plan_type}`), e.confirmed_no_offer ? t.push("本次确认无优惠") : e.plus_offer_kind && e.plus_offer_kind !== "unknown" && t.push(wr(e.plus_offer_kind)), e.comparison && e.comparison !== "not_comparable" && t.push({
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
function Rr(e) {
	let t = Q(e.result), n = Q(t.result || e.result_summary || t), r = Q(e.reason || t.reason || e.error || e.error_info), i = Q(e.display_snapshot || e.display), a = Q(e.execution), o = hr(e.owned_runs)[0] || {}, s = Fr(e), c = Ir(e.account_id || i.account_id || i.id || e.entity_id) || s, l = String(i.email || e.email || `账号 #${c}`), u = String(n.summary || n.message || e.result_label || e.summary_text || Lr(n) || "等待本轮结果"), d = String(r.summary || r.cause_summary || r.label || r.message || e.reason_label || e.reason_code || r.code || ""), f = [r.summary || r.cause_summary || r.message || e.error_message || d, r.display_code || r.code || e.reason_code].filter(Boolean).join("\n"), p = String(e.stage_label || e.current_stage_label || e.stage || "").trim(), m = Object.entries(Q(n.capabilities)).map(([e, t]) => `${gr(e)}：${Mr(Q(t).state || Q(t).status)}`).join("\n"), h = e.state || e.outcome || e.status;
	return {
		id: s,
		accountId: c,
		account: l,
		summary: u,
		summaryShort: zr(n, h, u),
		reason: d,
		reasonShort: d ? ge({
			...r,
			code: r.code || e.reason_code
		}) === "执行异常" && [...d].length <= 10 ? d : ge({
			...r,
			code: r.code || e.reason_code
		}) : "",
		reasonContent: f,
		stage: p,
		capabilities: m,
		state: Mr(h),
		stateKey: h,
		taskId: Ir(e.task_id || e.owned_task_id || a.task_id || o.task_id),
		runId: Ir(e.owned_run_id || e.run_id || a.run_id || o.run_id),
		blockerTaskId: Ir(e.blocker_task_id)
	};
}
function zr(e, t, n) {
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
	let r = Mr(t);
	return [...r].length <= 10 && r !== "—" ? r : "结果见详情";
}
// src/features/bulk/useBulkDetail.ts
var Br = [
	"failed",
	"partial_success",
	"not_executed",
	"cancelled"
];
function Vr(e, t, n = e().view === "detail") {
	let r = y({ ...e() }), i = y(n), a = j(null), s = j(null), c = j(null), l = j([]), u = y(null), d = y(/* @__PURE__ */ new Set()), f = y([]), m = y(null), h = y(!1), g = y(!1), _ = y(!1), v = y(!1), b = y(!1), x = y(!1), S = y(""), C = y(""), w = y(""), T = y(""), E = j(null), D = !1, O = 0, A = !1, M, N = null, P = "", F = /* @__PURE__ */ new Map(), I = () => `${r.value.batch_id || ""}:${r.value.round_id || ""}`, L = () => `${I()}:${r.value.result_state || ""}`, R = () => `${L()}:${r.value.cursor || ""}`;
	function z(e) {
		let t = F.get(e);
		t?.controller.abort();
		let n = {
			generation: (t?.generation || 0) + 1,
			controller: new AbortController()
		};
		return F.set(e, n), n;
	}
	function B(e, t) {
		return !D && F.get(e) === t && !t.controller.signal.aborted;
	}
	function V(...e) {
		for (let t of e) F.get(t)?.controller.abort(), F.delete(t);
		e.includes("detail") && (N = null, P = "");
	}
	function H() {
		let e = new URLSearchParams({ view: r.value.round_id ? "round" : "current" });
		return r.value.round_id && e.set("round_id", Z(r.value.round_id)), e;
	}
	function U(e = "") {
		return `/batches/${Z(r.value.batch_id)}${e}`;
	}
	function W(e) {
		return e instanceof Error ? e.message : String(e);
	}
	function ee(e) {
		let t = new Map(l.value.map((e) => [Z(e.id), e]));
		if (Array.isArray(e)) for (let n of e) {
			let e = Q(n);
			t.set(Z(e.id), e);
		}
		l.value = [...t.values()].sort((e, t) => Number(t.round_no) - Number(e.round_no));
	}
	let G = k(() => Pr(a.value?.summary || a.value?.counts)), K = k(() => Q(a.value?.control)), q = k(() => K.value.revision ?? a.value?.control_revision), J = k(() => ["ended", "completed"].includes(String(K.value.state || a.value?.control_state))), Y = k(() => !!(K.value.paused || a.value?.is_paused)), te = k(() => f.value.length > 0), ne = k(() => s.value?.page?.has_more && s.value.page.next_cursor || null), re = k(() => i.value && r.value.view === "detail" && (!J.value || !!m.value || !!K.value.pending)), ie = k(() => Object.hasOwn(mr, Nr(a.value)));
	function ae(e) {
		return !a.value || x.value || E.value || J.value || K.value.pending ? !0 : e === "pause" ? Y.value : e === "resume" ? !Y.value : Q(a.value.capabilities || Q(a.value.operation).capabilities)[e] === !1;
	}
	async function oe() {
		if (!i.value || r.value.view !== "detail") return;
		let e = z("targets");
		_.value = !0, C.value = "";
		try {
			let n = H();
			n.set("page_size", "50"), r.value.cursor && n.set("cursor", r.value.cursor), r.value.result_state && n.set("state[]", r.value.result_state);
			let i = await t.api.request(`${U("/targets")}?${n}`, { signal: e.controller.signal });
			if (B("targets", e)) {
				for (let e of i.items) Fr(e);
				s.value = i;
			}
		} catch (t) {
			B("targets", e) && (C.value = W(t));
		} finally {
			B("targets", e) && (_.value = !1);
		}
	}
	async function se(e = !1) {
		if (!i.value || r.value.view !== "detail" || !h.value || !ie.value || v.value) return;
		let n = J.value || Q(a.value?.selected_round).state === "completed", o = n && c.value?.phase === "completed" && c.value.summary_revision === a.value?.summary_revision && M === q.value;
		if (!e && (o || !n && (c.value || w.value) && t.now() - O < 1e4)) return;
		let s = z("report"), l = q.value, u = a.value?.summary_revision;
		v.value = !0;
		let d = !1;
		try {
			let e = await t.api.request(`${U("/report")}?${H()}`, { signal: s.controller.signal });
			if (!B("report", s)) return;
			c.value = e, w.value = "", M = l, d = (J.value || Q(a.value?.selected_round).state === "completed") && (u !== a.value?.summary_revision || l !== q.value);
		} catch (e) {
			B("report", s) && (w.value = W(e));
		} finally {
			B("report", s) && (v.value = !1, O = t.now());
		}
		d && se();
	}
	function ce() {
		return h.value = !0, se(!!w.value);
	}
	function le(e = !1) {
		if (D || !i.value || r.value.view !== "detail" || !r.value.batch_id) return Promise.resolve();
		if (N && P === I()) return N;
		P = I();
		let t = ue(e).finally(() => {
			N === t && (N = null, P = "");
		});
		return N = t, t;
	}
	async function ue(e = !1) {
		if (D || !i.value || r.value.view !== "detail" || !r.value.batch_id) return;
		let n = z("detail");
		g.value = !0, S.value = "";
		try {
			let r = await t.api.request(`${U()}?${H()}`, { signal: n.controller.signal });
			if (!B("detail", n)) return;
			let i = a.value?.summary_revision;
			if (a.value = r, ee(r.rounds_head), r.selected_round && ee([r.selected_round]), A || (u.value = typeof r.rounds_next_cursor == "string" ? r.rounds_next_cursor : null), m.value) {
				let e = l.value.find((e) => e.id === m.value);
				e && e.state !== "preparing" && (m.value = null, t.callbacks.notify(e.completion_reason === "cancelled_before_freeze" ? "重跑准备已取消，当前结果归属不变。" : "重跑名单已固定，可以切换查看新轮次。"));
			}
			se(e), (e || !s.value || i !== r.summary_revision) && await oe();
		} catch (e) {
			B("detail", n) && (S.value = W(e));
		} finally {
			B("detail", n) && (g.value = !1);
		}
	}
	async function de() {
		if (!i.value || r.value.view !== "detail" || !u.value || b.value) return;
		let e = z("rounds");
		b.value = !0;
		try {
			let n = new URLSearchParams({
				page_size: "20",
				cursor: u.value
			}), r = await t.api.request(`${U("/rounds")}?${n}`, { signal: e.controller.signal });
			B("rounds", e) && (ee(r.items), u.value = r.page.has_more && r.page.next_cursor || null, A = !0);
		} catch (t) {
			B("rounds", e) && (T.value = W(t));
		} finally {
			B("rounds", e) && (b.value = !1);
		}
	}
	function fe(e, n = !1) {
		n || (f.value = []), r.value = {
			...r.value,
			...e
		}, t.callbacks.updateNavigation(e);
	}
	async function pe() {
		ne.value && !_.value && (f.value.push(r.value.cursor || ""), fe({ cursor: ne.value }, !0));
	}
	async function me() {
		te.value && !_.value && fe({ cursor: f.value.pop() || "" }, !0);
	}
	async function he() {
		fe({ cursor: "" });
	}
	async function ge(e) {
		fe({
			result_state: e,
			cursor: ""
		});
	}
	async function X(e) {
		fe({
			round_id: e === "current" ? "" : Z(e),
			cursor: ""
		});
	}
	function _e(e, t) {
		let n = new Set(d.value);
		t ? n.add(Z(e)) : n.delete(e), d.value = n;
	}
	function ve(e) {
		for (let t of s.value?.items || []) _e(Fr(t), e);
	}
	function ye() {
		d.value = /* @__PURE__ */ new Set();
	}
	function be(e) {
		return (e === "unsuccessful" ? Br : [e]).reduce((e, t) => e + (G.value[t] || 0), 0);
	}
	function xe() {
		E.value = null;
	}
	async function Se(e) {
		if (!(x.value || D || !i.value || r.value.view !== "detail" || e.navigationKey !== R())) {
			x.value = !0, T.value = "", E.value = null;
			try {
				let n = await t.intents.submit(e.intentScope, e.path, e.body);
				if (t.callbacks.notify(e.kind === "retry" ? "重跑已受理，正在按固定时点的结果准备新轮次。" : "控制请求已受理，正在读取批次最新状态。"), D || e.navigationKey !== R()) return;
				e.kind === "retry" && (m.value = Z(n.round_id || n.id), ye()), await le(!0);
			} catch (t) {
				if (!D && e.navigationKey === R()) {
					T.value = W(t);
					let e = Q(t).code;
					["control_revision_conflict", "control_revision_changed"].includes(String(e)) && await le(!0);
				}
			} finally {
				x.value = !1;
			}
		}
	}
	async function Ce() {
		let e = E.value;
		e && await Se(e);
	}
	async function we(e = !1, t = "failed") {
		if (!a.value || x.value || E.value || !Br.includes(t) && t !== "unsuccessful") return;
		let n = [...d.value], i = e ? n.length : be(t);
		if (!i) return;
		let o = Z(r.value.batch_id), s = r.value.round_id ? Z(r.value.round_id) : null, c = {
			title: "确认重跑",
			description: `将在当前批次下新建一轮，重跑 ${i} 个账号；不会覆盖历史轮次。`,
			label: `重跑 ${i} 个`,
			count: i,
			scopeLabel: s ? "当前轮" : "当前结果",
			path: `/batches/${o}/rounds`,
			intentScope: `retry:${o}`,
			navigationKey: R(),
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
					states: t === "unsuccessful" ? [...Br] : [t]
				},
				retry_mode: "automatic"
			}
		};
		i >= 10 || t === "unsuccessful" ? E.value = c : await Se(c);
	}
	async function Te(e) {
		if (![
			"pause",
			"resume",
			"cancel_not_started",
			"request_stop"
		].includes(e) || ae(e)) return;
		let t = ["pause", "resume"].includes(e), n = e === "request_stop", i = Z(r.value.batch_id), o = r.value.round_id ? Z(r.value.round_id) : null, s = (n ? ["running", "waiting"] : [
			"pending_submit",
			"waiting_account",
			"queued",
			"waiting"
		]).reduce((e, t) => e + (G.value[t] || 0), 0), c = {
			title: n ? "停止正在执行" : "取消排队账号",
			description: n ? "已开始执行的账号会收到协作停止请求，正在收尾的步骤会完成，不会立即强制中断。" : "尚未开始的目标会取消；已开始账号链的必要步骤会继续收尾。",
			label: n ? "停止执行" : "取消排队",
			count: s,
			scopeLabel: !t && o ? "当前轮" : "整个批次",
			path: `/batches/${i}/control`,
			intentScope: `control:${i}:${e}`,
			navigationKey: R(),
			kind: "control",
			body: {
				action: e,
				expected_control_revision: K.value.revision ?? a.value?.control_revision,
				scope: !t && o ? {
					kind: "round",
					round_id: o
				} : { kind: "batch" }
			}
		};
		t ? await Se(c) : E.value = c;
	}
	function Ee(e) {
		if (!a.value) return;
		let n = Q(a.value.selection_summary).query || a.value.query_spec || Q(a.value.selection).query_spec;
		(e || n) && t.callbacks.copyBatch?.(n || {}, e ? {
			kind: "batch_targets",
			batch_id: Z(r.value.batch_id),
			selection: { kind: "all" }
		} : null, Nr(a.value));
	}
	function De(e) {
		i.value = e, e || (V("detail", "targets", "report", "rounds"), g.value = !1, _.value = !1, v.value = !1, b.value = !1, E.value = null);
	}
	return o(e, (e) => {
		JSON.stringify(e) !== JSON.stringify(r.value) && (f.value = [], r.value = { ...e });
	}, {
		deep: !0,
		flush: "sync"
	}), o(() => r.value.view, (e) => {
		e !== "detail" && De(!1);
	}, { flush: "sync" }), o(() => [
		I(),
		L(),
		r.value.cursor || "",
		r.value.batch_id
	], (e, t) => {
		E.value = null, T.value = "", !t || e[0] !== t[0] ? (e[3] !== t?.[3] && (h.value = !1), V("detail", "targets", "report", "rounds"), a.value = null, s.value = null, c.value = null, l.value = [], u.value = null, A = !1, O = 0, M = void 0, w.value = "", C.value = "", g.value = !1, _.value = !1, v.value = !1, b.value = !1, ye(), f.value = [], m.value = null, le()) : (e[1] !== t[1] && (ye(), f.value = []), s.value = null, oe());
	}, {
		immediate: !0,
		flush: "sync"
	}), p(() => {
		D = !0, V("detail", "targets", "report", "rounds"), E.value = null;
	}), {
		navigation: r,
		detail: a,
		targets: s,
		report: c,
		reportOpen: h,
		rounds: l,
		roundsCursor: u,
		selected: d,
		pendingRound: m,
		loading: g,
		targetsLoading: _,
		reportLoading: v,
		roundsLoading: b,
		writing: x,
		error: S,
		targetError: C,
		reportError: w,
		actionError: T,
		confirmation: E,
		counts: G,
		ended: J,
		paused: Y,
		needsPolling: re,
		hasReport: ie,
		hasPrevious: te,
		nextCursor: ne,
		controlDisabled: ae,
		refresh: le,
		loadTargets: oe,
		openReport: ce,
		refreshReport: se,
		moreRounds: de,
		next: pe,
		previous: me,
		first: he,
		setFilter: ge,
		setRound: X,
		toggleTarget: _e,
		selectPage: ve,
		clearSelection: ye,
		retryCount: be,
		retry: we,
		control: Te,
		confirm: Ce,
		cancelConfirmation: xe,
		copyBatch: Ee,
		setVisible: De
	};
}
// src/features/bulk/BulkBusinessStats.vue?vue&type=script&setup=true&lang.ts
var Hr = {
	key: 0,
	class: "bulk-business-groups"
}, Ur = { class: "bulk-business-heading" }, Wr = { class: "bulk-business-metrics" }, Gr = {
	key: 1,
	class: "bulk-report-empty"
}, Kr = /* @__PURE__ */ n({
	__name: "BulkBusinessStats",
	props: {
		metrics: {},
		groups: {}
	},
	setup(e) {
		let t = e, n = k(() => t.groups ?? Dr(t.metrics));
		return (e, t) => n.value.length ? (i(), R("div", Hr, [(i(!0), R(_, null, c(n.value, (e) => (i(), R("section", {
			key: e.title,
			class: "bulk-business-group"
		}, [C("header", Ur, [C("h4", null, x(e.title), 1), C("span", null, x(e.title === "国家查询项" ? "项" : "账号数"), 1)]), C("dl", Wr, [(i(!0), R(_, null, c(e.items, (e) => (i(), R("div", { key: e.title }, [C("dt", null, x(e.title), 1), C("dd", null, x(F($)(e.value)), 1)]))), 128))])]))), 128))])) : (i(), R("p", Gr, "暂无已确认的功能统计。"));
	}
}), qr = ["aria-label"], Jr = { role: "status" }, Yr = {
	key: 1,
	class: "bulk-plan-report",
	"aria-labelledby": "bulkPlanReportTitle"
}, Xr = { class: "bulk-report-header" }, Zr = { class: "bulk-report-heading-line" }, Qr = { id: "bulkPlanReportTitle" }, $r = { class: "bulk-report-updated" }, ei = {
	key: 0,
	class: "bulk-report-sync",
	role: "status"
}, ti = { class: "bulk-report-outcomes" }, ni = { class: "bulk-report-outcome-note" }, ri = { class: "bulk-report-execution" }, ii = { "aria-label": "账号执行耗时" }, ai = { class: "bulk-report-section-head" }, oi = { class: "bulk-report-durations" }, si = { class: "is-average" }, ci = { class: "bulk-report-note" }, li = {
	key: 0,
	"aria-label": "AT 检查与自动刷新"
}, ui = { class: "bulk-report-at-causes" }, di = { class: "bulk-report-at-results" }, fi = { class: "bulk-report-note" }, pi = {
	key: 1,
	"aria-label": "功能统计"
}, mi = {
	key: 1,
	class: "bulk-report-distributions"
}, hi = {
	class: "bulk-report-offers",
	"aria-label": "优惠结果"
}, gi = { class: "bulk-report-offer-totals" }, _i = { class: "bulk-report-offer-list" }, vi = { class: "bulk-report-offer-line" }, yi = {
	class: "bulk-report-rail",
	"aria-hidden": "true"
}, bi = { class: "bulk-report-kind-list" }, xi = {
	key: 0,
	class: "bulk-report-empty"
}, Si = {
	class: "bulk-report-plans",
	"aria-label": "当前订阅套餐"
}, Ci = { class: "bulk-report-plan-list" }, wi = {
	key: 0,
	class: "bulk-report-empty"
}, Ti = {
	key: 2,
	class: "bulk-business-details"
}, Ei = /* @__PURE__ */ n({
	__name: "BulkReport",
	props: {
		report: {},
		formatDateTime: { type: Function }
	},
	setup(e) {
		let t = e, n = k(() => Object.hasOwn(mr, String(t.report.operation_key))), r = k(() => Q(t.report.totals)), a = k(() => Q(t.report.duration)), o = k(() => Q(t.report.at_refresh)), s = k(() => Q(t.report.offers)), l = k(() => t.report.phase === "completed"), u = k(() => t.report.operation_key === "plan_check"), f = k(() => hr(t.report.plans).sort((e, t) => e.plan === "unknown" ? 1 : t.plan === "unknown" ? -1 : (_r(t.accounts) || 0) - (_r(e.accounts) || 0))), p = k(() => hr(s.value.by_plan).sort((e, t) => (_r(t.accounts) || 0) - (_r(e.accounts) || 0) || Cr(e.plan).localeCompare(Cr(t.plan)))), h = k(() => Math.max(0, ...f.value.map((e) => _r(e.accounts) || 0))), g = k(() => Math.max(0, ...p.value.map((e) => _r(e.accounts) || 0))), y = k(() => Dr(t.report.business_summary)), b = [
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
		], S = [
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
		return (t, E) => n.value && e.report.population_ready === !1 ? (i(), R("section", {
			key: 0,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": F(gr)(e.report.operation_key) + "报告"
		}, [C("h3", null, x(F(gr)(e.report.operation_key)) + "报告", 1), C("p", Jr, x(F(yr)(e.report)) + " · " + x(e.report.phase === "preparing" ? "账号名单准备中，固定后生成报告。" : "该轮名单未固定，无法生成账号统计。"), 1)], 8, qr)) : n.value ? (i(), R("section", Yr, [
			C("header", Xr, [C("div", null, [C("div", Zr, [C("h3", Qr, x(F(gr)(e.report.operation_key)) + x(l.value ? "完成报告" : "实时报告"), 1), C("span", { class: O(["bulk-report-phase", { "is-completed": l.value }]) }, x(l.value ? "已完成" : e.report.phase === "preparing" ? "名单准备中" : "统计更新中"), 3)]), C("p", null, x(F(yr)(e.report)) + " · " + x(F($)(r.value.accounts)) + " 个账号", 1)]), C("span", $r, "更新于 " + x(e.formatDateTime(e.report.generated_at)), 1)]),
			F(Q)(e.report.projection).state && F(Q)(e.report.projection).state !== "current" ? (i(), R("p", ei, x(F(Q)(e.report.projection).state === "failed" ? "结果汇总暂时失败，以下统计尚未收齐，请稍后刷新。" : "执行结果正在汇总，以下统计尚未收齐。"), 1)) : m("", !0),
			C("dl", ti, [(i(), R(_, null, c(b, ([e, t, n]) => C("div", {
				key: t,
				class: O(["bulk-report-metric", n])
			}, [C("dt", null, x(e), 1), C("dd", null, [z(x(F($)(r.value[t])), 1), E[0] ||= C("span", null, "个", -1)])], 2)), 64))]),
			C("div", ni, [
				C("span", null, "已结束 " + x(F($)(r.value.completed)) + " / " + x(F($)(r.value.accounts)) + " 个", 1),
				C("span", null, "未执行 " + x(F($)(r.value.not_executed)) + " 个", 1),
				C("span", null, "已取消 " + x(F($)(r.value.cancelled)) + " 个", 1)
			]),
			C("div", ri, [C("section", ii, [
				C("div", ai, [E[1] ||= C("h4", null, "账号执行耗时", -1), C("span", null, "已结束样本 " + x(F($)(a.value.sample_count)) + " 个", 1)]),
				C("dl", oi, [
					C("div", si, [E[2] ||= C("dt", null, "平均耗时", -1), C("dd", null, x(F(vr)(a.value.avg_seconds)), 1)]),
					C("div", null, [E[3] ||= C("dt", null, "最快", -1), C("dd", null, x(F(vr)(a.value.min_seconds)), 1)]),
					C("div", null, [E[4] ||= C("dt", null, "最慢", -1), C("dd", null, x(F(vr)(a.value.max_seconds)), 1)])
				]),
				C("p", ci, [z(" 从账号开始执行到结束，" + x(u.value ? "含自动刷新及链内等待" : "含链内等待") + "，不含开始前排队。", 1), (F(_r)(a.value.missing_count) || 0) > 0 ? (i(), R(_, { key: 0 }, [z(x(F($)(a.value.missing_count)) + " 个已结束账号缺少有效耗时，未计入均值。", 1)], 64)) : F(_r)(a.value.sample_count) === 0 ? (i(), R(_, { key: 1 }, [z(" 暂无有效耗时样本。")], 64)) : m("", !0)])
			]), u.value ? (i(), R("section", li, [
				E[8] ||= C("div", { class: "bulk-report-section-head" }, [C("h4", null, "AT 检查与自动刷新"), C("span", null, "按账号去重")], -1),
				C("dl", ui, [(i(), R(_, null, c(S, ([e, t]) => C("div", {
					key: t,
					class: "bulk-report-minor"
				}, [C("dt", null, x(e), 1), C("dd", null, [z(x(F($)(o.value[t])), 1), E[5] ||= C("span", null, "个", -1)])])), 64))]),
				C("dl", di, [(i(), R(_, null, c(w, ([e, t, n]) => C("div", {
					key: t,
					class: O(["bulk-report-minor", n])
				}, [C("dt", null, x(e), 1), C("dd", null, [z(x(F($)(o.value[t])), 1), E[6] ||= C("span", null, "个", -1)])], 2)), 64))]),
				C("p", fi, [
					F(_r)(o.value.not_needed_accounts) === null ? m("", !0) : (i(), R(_, { key: 0 }, [z("未触发刷新 " + x(F($)(o.value.not_needed_accounts)) + " 个 · ", 1)], 64)),
					z("刷新状态待确认 " + x(F($)(o.value.unknown_accounts)) + " 个", 1),
					F(_r)(o.value.not_executed_accounts) === null ? m("", !0) : (i(), R(_, { key: 1 }, [z(" · 未开始执行 " + x(F($)(o.value.not_executed_accounts)) + " 个", 1)], 64)),
					E[7] ||= z("。待确认含执行中尚无结果及历史证据缺失；触发原因可能重叠，远端拒绝不等于本地过期。 ", -1)
				])
			])) : (i(), R("section", pi, [E[9] ||= C("div", { class: "bulk-report-section-head" }, [C("h4", null, "功能统计"), C("span", null, "当前查看范围")], -1), d(Kr, { groups: y.value }, null, 8, ["groups"])]))]),
			u.value ? (i(), R("div", mi, [C("section", hi, [
				E[13] ||= C("div", { class: "bulk-report-section-head" }, [C("div", null, [C("h4", null, "优惠结果"), C("p", null, "统计本次查到的可用优惠，按账号去重")])], -1),
				C("dl", gi, [(i(), R(_, null, c(T, ([e, t, n]) => C("div", {
					key: t,
					class: O(["bulk-report-metric", { "is-accent": t === "with_offer_accounts" }])
				}, [
					C("dt", null, x(e), 1),
					C("dd", null, [z(x(F($)(s.value[t])), 1), E[10] ||= C("span", null, "个", -1)]),
					C("small", null, x(n), 1)
				], 2)), 64))]),
				C("div", _i, [(i(!0), R(_, null, c(p.value, (e) => (i(), R("div", {
					key: String(e.plan),
					class: "bulk-report-offer-row"
				}, [
					C("div", vi, [C("strong", null, x(F(Cr)(e.plan)), 1), C("span", null, [C("b", null, x(F($)(e.accounts)), 1), E[11] ||= z(" 个账号", -1)])]),
					C("span", yi, [C("span", { style: v({ width: F(Tr)(e.accounts, g.value) }) }, null, 4)]),
					C("dl", bi, [(i(!0), R(_, null, c(F(hr)(e.kinds), (e) => (i(), R("div", { key: String(e.kind) }, [C("dt", null, x(F(wr)(e.kind)), 1), C("dd", null, [z(x(F($)(e.accounts)), 1), E[12] ||= C("span", null, "个", -1)])]))), 128))])
				]))), 128)), p.value.length ? m("", !0) : (i(), R("p", xi, x(F(_r)(s.value.with_offer_accounts) === 0 ? "本次尚未查到可用优惠。" : "暂无优惠套餐明细。"), 1))]),
				E[14] ||= C("p", { class: "bulk-report-note" }, "同一账号可符合多个套餐或优惠，分项数量可能重叠。", -1)
			]), C("section", Si, [
				E[16] ||= C("div", { class: "bulk-report-section-head" }, [C("div", null, [C("h4", null, "当前订阅套餐"), C("p", null, "本次查询确认的套餐状态")])], -1),
				C("dl", Ci, [(i(!0), R(_, null, c(f.value, (e) => (i(), R("div", {
					key: String(e.plan),
					class: O({ "is-unknown": e.plan === "unknown" })
				}, [C("dt", null, x(F(Cr)(e.plan)), 1), C("dd", null, [C("span", null, [z(x(F($)(e.accounts)), 1), E[15] ||= C("small", null, "个", -1)]), C("span", {
					class: O(["bulk-report-rail", { "is-muted": e.plan === "unknown" }]),
					"aria-hidden": "true"
				}, [C("span", { style: v({ width: F(Tr)(e.accounts, h.value) }) }, null, 4)], 2)])], 2))), 128)), f.value.length ? m("", !0) : (i(), R("div", wi, "暂无套餐结果。"))]),
				E[17] ||= C("p", { class: "bulk-report-note" }, "“尚未确认”包含待完成、失败或缺少套餐记录的账号。", -1)
			])])) : m("", !0),
			u.value && y.value.length ? (i(), R("details", Ti, [E[18] ||= C("summary", null, [z("更多查询统计"), C("span", null, "展开查看")], -1), d(Kr, { groups: y.value }, null, 8, ["groups"])])) : m("", !0)
		])) : m("", !0);
	}
}), Di = ["aria-label"], Oi = {
	key: 0,
	role: "status"
}, ki = {
	key: 2,
	class: "bulk-report-load-error"
}, Ai = {
	class: "bulk-error",
	role: "alert"
}, ji = ["disabled"], Mi = /* @__PURE__ */ n({
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
		let t = e, n = k(() => Object.hasOwn(mr, t.operationKey)), r = k(() => `${mr[t.operationKey]}报告`);
		return (t, a) => n.value ? (i(), R(_, { key: 0 }, [e.report && e.report.operation_key === e.operationKey ? (i(), S(Ei, {
			key: 0,
			report: e.report,
			"format-date-time": e.formatDateTime
		}, null, 8, ["report", "format-date-time"])) : (i(), R("section", {
			key: 1,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": r.value
		}, [C("h3", null, x(r.value), 1), e.error ? m("", !0) : (i(), R("p", Oi, "正在汇总本次执行结果…"))], 8, Di)), e.error ? (i(), R("div", ki, [C("p", Ai, x(e.error), 1), C("button", {
			type: "button",
			class: "jobs-tb-btn",
			"data-bulk-action": "report-refresh",
			disabled: e.loading,
			onClick: a[0] ||= D((t) => e.onRetry(), ["stop"])
		}, " 重新读取报告 ", 8, ji)])) : m("", !0)], 64)) : m("", !0);
	}
}), Ni = ["aria-busy"], Pi = {
	key: 0,
	class: "ui-list-feedback is-error bulk-error",
	role: "alert"
}, Fi = {
	class: "ui-table-scroll bulk-target-scroll",
	role: "region",
	"aria-label": "账号明细内容",
	tabindex: "0"
}, Ii = { class: "ui-table ui-table--sticky-end bulk-table bulk-target-table" }, Li = { class: "ui-col-check" }, Ri = [
	"disabled",
	"checked",
	"indeterminate"
], zi = { class: "bulk-target-filter" }, Bi = ["checked"], Vi = [
	"value",
	"checked",
	"onChange"
], Hi = ["data-bulk-row-target"], Ui = {
	class: "ui-col-check bulk-target-check",
	"data-label": "选择"
}, Wi = [
	"data-bulk-target",
	"aria-label",
	"checked",
	"onChange"
], Gi = {
	class: "bulk-target-id",
	"data-label": "ID"
}, Ki = ["aria-label", "onClick"], qi = {
	class: "bulk-target-account",
	"data-label": "账号"
}, Ji = ["title", "onClick"], Yi = {
	class: "bulk-target-state",
	"data-label": "结果 / 阶段"
}, Xi = { class: "bulk-target-status-line" }, Zi = ["onClick"], Qi = {
	class: "bulk-target-summary",
	"data-label": "结果摘要"
}, $i = [
	"title",
	"aria-label",
	"onClick"
], ea = {
	class: "bulk-target-reason",
	"data-label": "错误分类"
}, ta = ["title", "onClick"], na = {
	class: "bulk-target-actions",
	"data-label": "操作"
}, ra = { class: "bulk-target-action-line" }, ia = ["onClick"], aa = { key: 1 }, oa = ["onClick"], sa = {
	key: 0,
	class: "bulk-vue-result-details"
}, ca = /* @__PURE__ */ n({
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
		let r = e, s = n, u = y(null), f = j(r.items), p = k(() => f.value.map(Rr)), h = k(() => p.value.filter((e) => r.selected.has(e.id)).length), g = y(!1), v = k(() => [.../* @__PURE__ */ new Set([...r.resultStates, ...r.resultState ? [r.resultState] : []])]);
		function b(e) {
			g.value = !1, s("filter", e);
		}
		function w() {
			let e = window.getSelection();
			return !!(e?.toString() && e.anchorNode && u.value?.contains(e.anchorNode));
		}
		function E() {
			w() || (f.value = r.items);
		}
		o(() => r.items, (e) => {
			w() && e.length || (f.value = e);
		}), o(() => r.scope, () => {
			f.value = r.items;
		}), l(() => document.addEventListener("selectionchange", E)), T(() => document.removeEventListener("selectionchange", E));
		let D = y(!1), A = j(null), M = null;
		function N(e, t) {
			A.value = { ...e }, M = t.currentTarget, D.value = !0;
		}
		function P(e) {
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
			D.value = !1, g.value = !1;
		}
		function L(e) {
			return e.target.checked;
		}
		function B(e, t = null) {
			r.openTask(e, t);
		}
		return t({ close: I }), (t, n) => (i(), R(_, null, [C("div", {
			ref_key: "host",
			ref: u,
			class: "bulk-targets",
			"aria-busy": e.loading
		}, [e.error ? (i(), R("div", Pi, [z(x(e.error) + " ", 1), C("button", {
			type: "button",
			class: "ui-link",
			onClick: n[0] ||= (e) => s("retry")
		}, "重试读取明细")])) : m("", !0), C("div", Fi, [C("table", Ii, [C("thead", null, [C("tr", null, [
			C("th", Li, [C("input", {
				type: "checkbox",
				"data-select-page": "",
				"aria-label": "选择当前页目标",
				disabled: !p.value.length,
				checked: p.value.length > 0 && h.value === p.value.length,
				indeterminate: h.value > 0 && h.value < p.value.length,
				onChange: n[1] ||= (e) => s("selectPage", L(e))
			}, null, 40, Ri)]),
			n[8] ||= C("th", null, "ID", -1),
			n[9] ||= C("th", null, "账号", -1),
			C("th", null, [e.resultStates.length ? (i(), S(q, {
				key: 0,
				label: "结果状态",
				"trigger-label": "结果 / 阶段",
				active: !!e.resultState,
				summary: F(Mr)(e.resultState),
				open: g.value,
				"onUpdate:open": n[3] ||= (e) => g.value = e
			}, {
				default: a(() => [C("fieldset", zi, [
					n[7] ||= C("legend", { class: "ui-sr-only" }, "结果状态", -1),
					C("label", null, [
						C("input", {
							type: "radio",
							name: "bulk-target-state",
							value: "",
							checked: !e.resultState,
							onChange: n[2] ||= (e) => b("")
						}, null, 40, Bi),
						n[6] ||= C("span", null, "全部", -1),
						C("strong", null, x(F($)(e.resultTotal)), 1)
					]),
					(i(!0), R(_, null, c(v.value, (t) => (i(), R("label", { key: t }, [
						C("input", {
							type: "radio",
							name: "bulk-target-state",
							value: t,
							checked: e.resultState === t,
							onChange: (e) => b(t)
						}, null, 40, Vi),
						C("span", null, x(F(Mr)(t)), 1),
						C("strong", null, x(e.resultCounts[t] || 0), 1)
					]))), 128))
				])]),
				_: 1
			}, 8, [
				"active",
				"summary",
				"open"
			])) : (i(), R(_, { key: 1 }, [z("结果 / 阶段")], 64))]),
			n[10] ||= C("th", null, "结果摘要", -1),
			n[11] ||= C("th", null, "错误分类", -1),
			n[12] ||= C("th", null, "操作", -1)
		])]), C("tbody", null, [(i(!0), R(_, null, c(p.value, (t) => (i(), R("tr", {
			key: t.id,
			"data-bulk-row-target": t.id
		}, [
			C("td", Ui, [C("input", {
				type: "checkbox",
				"data-bulk-target": t.id,
				"aria-label": "选择账号 " + t.account,
				checked: e.selected.has(t.id),
				onChange: (e) => s("toggle", t.id, L(e))
			}, null, 40, Wi)]),
			C("td", Gi, [C("button", {
				type: "button",
				class: "bulk-cell-detail",
				"aria-label": "查看完整账号 ID：" + t.accountId,
				onClick: (e) => N(t, e)
			}, "#" + x(t.accountId), 9, Ki)]),
			C("td", qi, [C("button", {
				type: "button",
				class: "bulk-cell-detail",
				title: t.account,
				onClick: (e) => N(t, e)
			}, x(t.account), 9, Ji)]),
			C("td", Yi, [C("div", Xi, [C("span", { class: O(["ui-badge bulk-badge", `ui-badge--${F(jr)(t.stateKey)}`]) }, x(t.state), 3), t.stage && !["—", "-"].includes(t.stage) ? (i(), R("button", {
				key: 0,
				type: "button",
				class: "bulk-cell-detail bulk-target-stage",
				onClick: (e) => N(t, e)
			}, x(t.stage), 9, Zi)) : m("", !0)])]),
			C("td", Qi, [d(re, {
				text: t.summaryShort,
				title: t.summary
			}, {
				default: a(() => [C("button", {
					type: "button",
					class: "bulk-cell-detail",
					"data-result-detail": "",
					title: t.summary,
					"aria-label": "查看完整结果摘要：" + t.summary,
					onClick: (e) => N(t, e)
				}, x(t.summaryShort), 9, $i)]),
				_: 2
			}, 1032, ["text", "title"])]),
			C("td", ea, [t.reason ? (i(), S(re, {
				key: 0,
				text: t.reasonShort,
				title: t.reason
			}, {
				default: a(() => [C("button", {
					type: "button",
					class: "bulk-cell-detail",
					title: t.reason,
					onClick: (e) => N(t, e)
				}, x(t.reasonShort), 9, ta)]),
				_: 2
			}, 1032, ["text", "title"])) : (i(), R(_, { key: 1 }, [z("—")], 64))]),
			C("td", na, [C("div", ra, [t.taskId ? (i(), R("button", {
				key: 0,
				type: "button",
				class: "ui-link",
				"data-owned-task": "",
				onClick: (e) => B(t.taskId, t.runId)
			}, "查看执行", 8, ia)) : (i(), R("span", aa, "尚未创建执行")), t.blockerTaskId ? (i(), R("button", {
				key: 2,
				type: "button",
				class: "ui-link",
				"data-blocker-task": "",
				title: "查看占用任务（其他执行）",
				onClick: (e) => B(t.blockerTaskId)
			}, "查看占用", 8, oa)) : m("", !0)])])
		], 8, Hi))), 128)), p.value.length ? m("", !0) : (i(), S(te, {
			key: 0,
			colspan: 7,
			loading: e.loading,
			"loading-title": "正在读取账号明细…",
			title: "当前条件下没有目标",
			text: "更改结果筛选不会改变本批固定名单。"
		}, null, 8, ["loading"]))])])])], 8, Ni), d(F(ve), {
			open: D.value,
			"onUpdate:open": n[5] ||= (e) => D.value = e
		}, {
			default: a(() => [d(F(je), null, {
				default: a(() => [d(F(Ae), { class: "bulk-vue-overlay" }), d(F(De), {
					class: "bulk-vue-dialog",
					onEscapeKeyDown: n[4] ||= (e) => {
						e.preventDefault(), I();
					},
					onCloseAutoFocus: P
				}, {
					default: a(() => [
						d(F(Me), null, {
							default: a(() => [...n[13] ||= [z("账号执行详情", -1)]]),
							_: 1
						}),
						d(F(Oe), null, {
							default: a(() => [z(x(A.value?.account) + " · 账号 #" + x(A.value?.accountId), 1)]),
							_: 1
						}),
						A.value ? (i(), R("dl", sa, [
							n[16] ||= C("dt", null, "结果 / 阶段", -1),
							C("dd", null, x(A.value.state) + " · " + x(A.value.stage || "—"), 1),
							n[17] ||= C("dt", null, "结果摘要", -1),
							C("dd", null, x(A.value.summary), 1),
							A.value.capabilities ? (i(), R(_, { key: 0 }, [n[14] ||= C("dt", null, "能力结果", -1), C("dd", null, x(A.value.capabilities), 1)], 64)) : m("", !0),
							n[18] ||= C("dt", null, "错误分类 / 错误码", -1),
							C("dd", null, x(A.value.reasonContent || "—"), 1),
							n[19] ||= C("dt", null, "所属执行", -1),
							C("dd", null, x(A.value.taskId ? "任务 #" + A.value.taskId : "尚未创建执行") + x(A.value.runId ? " · 运行 #" + A.value.runId : ""), 1),
							A.value.blockerTaskId ? (i(), R(_, { key: 1 }, [n[15] ||= C("dt", null, "占用任务（其他执行）", -1), C("dd", null, "#" + x(A.value.blockerTaskId), 1)], 64)) : m("", !0)
						])) : m("", !0),
						d(F(ye), {
							class: "jobs-tb-btn",
							"data-close-detail": ""
						}, {
							default: a(() => [...n[20] ||= [z("关闭", -1)]]),
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
}), la = ["aria-busy"], ua = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, da = {
	key: 1,
	class: "bulk-card bulk-overview"
}, fa = { class: "bulk-detail-toolbar" }, pa = { class: "bulk-detail-meta" }, ma = { class: "bulk-settings bulk-detail-settings" }, ha = {
	key: 0,
	class: "bulk-projection-note"
}, ga = { class: "bulk-actions" }, _a = { class: "bulk-round-picker" }, va = ["value"], ya = ["value"], ba = ["value"], xa = ["disabled"], Sa = ["disabled"], Ca = { class: "bulk-control-strip" }, wa = { class: "bulk-control-copy" }, Ta = { class: "bulk-view-note" }, Ea = { key: 0 }, Da = { key: 1 }, Oa = { key: 2 }, ka = { key: 3 }, Aa = {
	key: 0,
	class: "bulk-view-note"
}, ja = {
	class: "bulk-actions",
	role: "group",
	"aria-label": "运行控制"
}, Ma = [
	"data-bulk-action",
	"disabled",
	"onClick"
], Na = { class: "bulk-summary-grid" }, Pa = { class: "bulk-summary-item" }, Fa = { class: "bulk-summary-item" }, Ia = { class: "bulk-summary-item is-success" }, La = { class: "bulk-summary-item is-warning" }, Ra = ["aria-busy"], za = { class: "bulk-card bulk-results-card" }, Ba = { class: "bulk-results-heading" }, Va = ["disabled"], Ha = { class: "bulk-retry-toolbar" }, Ua = ["value"], Wa = ["disabled"], Ga = ["disabled"], Ka = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, qa = {
	key: 1,
	class: "bulk-notice",
	role: "status"
}, Ja = {
	class: "bulk-target-count-row",
	"data-bulk-target-count-row": ""
}, Ya = {
	class: "bulk-target-count",
	role: "status"
}, Xa = { class: "bulk-vue-dialog-actions" }, Za = /*#__PURE__*/ I(/* @__PURE__ */ n({
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
		let r = e, l = Vr(() => r.navigation, r.deps, r.visible ?? r.navigation.view === "detail"), { navigation: u, detail: f, targets: p, report: g, reportOpen: v, rounds: b, roundsCursor: S, selected: w, pendingRound: T, loading: E, targetsLoading: D, reportLoading: A, roundsLoading: j, writing: M, error: N, targetError: P, reportError: I, actionError: L, confirmation: B, counts: V, ended: H, paused: U, hasReport: W, hasPrevious: ee, nextCursor: G } = l, K = k(() => f.value?.name || f.value?.title || "批次详情"), q = y(null), J = y(null), Y = y("failed"), te = k(() => [
			"success",
			"partial_success",
			"failed",
			"not_executed",
			"cancelled"
		].reduce((e, t) => e + (V.value[t] || 0), 0)), ne = k(() => [
			"pending_submit",
			"waiting_account",
			"queued",
			"running",
			"waiting"
		].reduce((e, t) => e + (V.value[t] || 0), 0)), re = k(() => b.value.find((e) => e.id === u.value.round_id)), ae = k(() => !!(Q(f.value?.selection_summary).query || f.value?.query_spec || Q(f.value?.selection).query_spec)), oe = [
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
		], se = k(() => u.value.result_state ? [{
			key: "result_state",
			label: `结果状态：${Mr(u.value.result_state)}`,
			title: `结果状态：${Mr(u.value.result_state)}`,
			removeLabel: "清除结果状态筛选"
		}] : []), ce = [
			["failed", "失败"],
			["partial_success", "部分成功"],
			["not_executed", "未执行"],
			["cancelled", "已取消"],
			["unsuccessful", "全部未成功"]
		], le = [
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
		], ue = null;
		function de(e) {
			ue = e.currentTarget;
		}
		async function fe(e, t) {
			de(t), await l.retry(e, Y.value);
		}
		async function pe(e, t) {
			de(t), await l.control(e);
		}
		function me(e) {
			e.preventDefault();
			let n = ue;
			ue = null, t(() => {
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
		async function he() {
			let e = l.openReport();
			await t(), J.value && (J.value.focus({ preventScroll: !0 }), J.value.scrollIntoView?.({ block: "start" })), await e;
		}
		function ge(e) {
			l.setVisible(e), e || (q.value?.close(), ue = null);
		}
		return o(() => r.visible, (e) => {
			e !== void 0 && ge(e);
		}, { flush: "sync" }), o(() => [
			u.value.batch_id,
			u.value.round_id,
			u.value.result_state,
			u.value.view
		], () => {
			q.value?.close(), ue = null;
		}), n({
			batchName: K,
			refresh: l.refresh,
			showReport: he,
			setVisible: ge,
			needsRefresh: l.needsPolling
		}), (t, n) => (i(), R("div", {
			class: "bulk-detail-owner",
			"aria-busy": F(E)
		}, [
			F(N) ? (i(), R("p", ua, [z(x(F(N)) + " ", 1), C("button", {
				type: "button",
				class: "bulk-link",
				onClick: n[0] ||= (e) => F(l).refresh(!0)
			}, "重试读取批次")])) : m("", !0),
			F(f) ? (i(), R("section", da, [
				C("div", fa, [C("div", pa, [
					C("span", { class: O(["ui-badge bulk-badge", `ui-badge--${F(jr)(F(U) ? "paused" : F(Q)(F(f).control).state || F(f).control_state || F(f).state)}`]) }, x(F(Mr)(F(U) ? "paused" : F(Q)(F(f).control).state || F(f).control_state || F(f).state)), 3),
					C("span", null, x(F(gr)(F(Nr)(F(f)))), 1),
					C("span", null, "创建于 " + x(e.deps.callbacks.formatDateTime(F(f).created_at)), 1),
					C("details", ma, [n[16] ||= C("summary", null, "范围与设置", -1), C("dl", null, [
						n[13] ||= C("dt", null, "名单生成", -1),
						C("dd", null, x(e.deps.callbacks.formatDateTime(F(Q)(F(f).selection_summary).selection_at || F(f).selection_at)), 1),
						n[14] ||= C("dt", null, "配置版本", -1),
						C("dd", null, x(F(Q)(F(f).effective_settings).config_revision || F(f).config_revision || "—"), 1),
						n[15] ||= C("dt", null, "结果更新", -1),
						C("dd", null, x(e.deps.callbacks.formatDateTime(F(f).projected_at)), 1)
					])]),
					F(Q)(F(f).projection).state && F(Q)(F(f).projection).state !== "current" ? (i(), R("span", ha, "汇总同步中")) : m("", !0)
				]), C("div", ga, [
					C("label", _a, [n[18] ||= C("span", { class: "bulk-sr-only" }, "结果视图", -1), C("select", {
						value: F(u).round_id || "current",
						"aria-label": "结果视图",
						onChange: n[1] ||= (e) => F(l).setRound(e.target.value)
					}, [
						n[17] ||= C("option", { value: "current" }, "当前结果", -1),
						(i(!0), R(_, null, c(F(b), (e) => (i(), R("option", {
							key: String(e.id),
							value: String(e.id)
						}, x(Number(e.round_no) === 1 ? "首轮" : "重跑 " + (Number(e.round_no) - 1)) + " · " + x(F(Mr)(e.state)) + " · " + x(e.target_count == null ? "准备中" : F($)(e.target_count) + " 个"), 9, ya))), 128)),
						F(u).round_id && !re.value ? (i(), R("option", {
							key: 0,
							value: F(u).round_id
						}, "所选轮次 #" + x(F(u).round_id), 9, ba)) : m("", !0)
					], 40, va)]),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "more-rounds",
						disabled: !F(S) || F(j),
						onClick: n[2] ||= (...e) => F(l).moreRounds && F(l).moreRounds(...e)
					}, "更多轮次", 8, xa),
					F(W) ? (i(), R("button", {
						key: 0,
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "view-report",
						onClick: he
					}, "查看报告")) : m("", !0),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "copy-targets",
						onClick: n[3] ||= (e) => F(l).copyBatch(!0)
					}, "同一名单再次执行"),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "copy-query",
						disabled: !ae.value,
						onClick: n[4] ||= (e) => F(l).copyBatch(!1)
					}, "复制条件新建", 8, Sa)
				])]),
				C("div", Ca, [C("div", wa, [C("p", Ta, [
					C("strong", null, "已结束 " + x(F($)(te.value)) + " / " + x(F($)(F(f).target_count)) + " 个", 1),
					F(W) && F(v) && !F(H) && !F(U) ? (i(), R("span", Ea, x(F($)(ne.value)) + " 个进行中", 1)) : m("", !0),
					re.value?.completion_reason === "cancelled_before_freeze" ? (i(), R("span", Da, "本轮在名单生成前取消，当前结果未改变。")) : F(u).round_id ? (i(), R("span", Oa, "仅展示该轮名单及执行结果。")) : (i(), R("span", ka, "每个账号保留最近一轮结果"))
				]), F(U) && !F(H) ? (i(), R("p", Aa, "未开始的账号等待继续，已开始的账号继续收尾。")) : m("", !0)]), C("div", ja, [(i(), R(_, null, c(le, ([e, t, n]) => C("button", {
					key: e,
					type: "button",
					class: O(["jobs-tb-btn", { "jobs-tb-btn--danger": ["cancel", "stop"].includes(n) }]),
					"data-bulk-action": n,
					disabled: F(l).controlDisabled(e),
					onClick: (t) => pe(e, t)
				}, x(t), 11, Ma)), 64))])]),
				!F(W) || !F(v) ? (i(), R(_, { key: 0 }, [C("div", Na, [
					C("div", Pa, [n[19] ||= C("span", null, "账号总数", -1), C("strong", null, x(F($)(F(f).target_count)), 1)]),
					C("div", Fa, [n[20] ||= C("span", null, "进行中", -1), C("strong", null, x(ne.value), 1)]),
					C("div", Ia, [n[21] ||= C("span", null, "成功", -1), C("strong", null, x(F(V).success || 0), 1)]),
					C("div", La, [n[22] ||= C("span", null, "未成功", -1), C("strong", null, x(F(l).retryCount("unsuccessful")), 1)])
				]), d(Kr, { metrics: F(f).business_summary || F(f).metrics }, null, 8, ["metrics"])], 64)) : m("", !0)
			])) : m("", !0),
			F(W) && F(v) ? (i(), R("section", {
				key: 2,
				ref_key: "reportRegion",
				ref: J,
				"data-bulk-plan-report": "",
				class: "bulk-report-target",
				tabindex: "-1",
				role: "region",
				"aria-label": "批次报告",
				"aria-busy": F(A)
			}, [d(Mi, {
				"operation-key": F(Nr)(F(f)),
				report: F(g),
				error: F(I) ? "读取报告失败：" + F(I) : "",
				"format-date-time": e.deps.callbacks.formatDateTime,
				"on-retry": () => F(l).refreshReport(!0),
				loading: F(A)
			}, null, 8, [
				"operation-key",
				"report",
				"error",
				"format-date-time",
				"on-retry",
				"loading"
			])], 8, Ra)) : m("", !0),
			C("section", za, [
				C("div", Ba, [C("h3", null, [
					n[23] ||= z("账号明细 ", -1),
					C("span", null, x(F(w).size ? "已选 " + F(w).size + " 个（可跨页）" : ""), 1),
					C("button", {
						type: "button",
						class: "bulk-link",
						disabled: !F(w).size,
						onClick: n[5] ||= (...e) => F(l).clearSelection && F(l).clearSelection(...e)
					}, "清空选择", 8, Va)
				]), C("div", Ha, [
					s(C("select", {
						"onUpdate:modelValue": n[6] ||= (e) => Y.value = e,
						"aria-label": "重跑范围"
					}, [(i(), R(_, null, c(ce, ([e, t]) => C("option", {
						key: e,
						value: e
					}, x(t), 9, Ua)), 64))], 512), [[h, Y.value]]),
					C("button", {
						type: "button",
						class: "jobs-tb-btn jobs-tb-btn--primary",
						"data-bulk-action": "retry",
						disabled: F(M) || !!F(B) || !F(l).retryCount(Y.value),
						onClick: n[7] ||= (e) => fe(!1, e)
					}, "重跑" + x(ce.find((e) => e[0] === Y.value)?.[1]) + " (" + x(F(l).retryCount(Y.value)) + ")", 9, Wa),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "retry-selected",
						disabled: F(M) || !!F(B) || !F(w).size,
						onClick: n[8] ||= (e) => fe(!0, e)
					}, "重跑勾选" + x(F(w).size ? " (" + F(w).size + ")" : ""), 9, Ga)
				])]),
				F(L) ? (i(), R("p", Ka, x(F(L)), 1)) : m("", !0),
				F(T) ? (i(), R("p", qa, "重跑已受理，正在准备新轮次 #" + x(F(T)) + "。", 1)) : m("", !0),
				C("div", Ja, [C("span", Ya, "共 " + x(F($)(F(f)?.target_count)) + " 个账号 · 当前页 " + x(F(p)?.items.length || 0) + " 个", 1), d(ie, {
					items: se.value,
					onRemove: n[9] ||= (e) => F(l).setFilter("")
				}, null, 8, ["items"])]),
				d(ca, {
					ref_key: "targetTable",
					ref: q,
					scope: [
						F(u).batch_id,
						F(u).round_id,
						F(u).result_state,
						F(u).cursor
					].join(":"),
					items: F(p)?.items || [],
					selected: F(w),
					loading: F(D) || F(E) && !F(f),
					error: F(P),
					"result-state": F(u).result_state || "",
					"result-counts": F(V),
					"result-total": F(f)?.target_count,
					"result-states": oe,
					"open-task": e.deps.callbacks.openTask,
					onFilter: F(l).setFilter,
					onToggle: F(l).toggleTarget,
					onSelectPage: F(l).selectPage,
					onRetry: F(l).loadTargets
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
				d(Ye, {
					"has-previous": F(ee),
					"next-cursor": F(G),
					"item-count": F(p)?.items.length || 0,
					"has-cursor": !!F(u).cursor,
					busy: F(D),
					label: "账号明细分页",
					onNext: F(l).next,
					onPrevious: F(l).previous,
					onFirst: F(l).first
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
			d(F(Be), {
				open: !!F(B),
				"onUpdate:open": n[12] ||= (e) => {
					e || F(l).cancelConfirmation();
				}
			}, {
				default: a(() => [d(F(ze), null, {
					default: a(() => [d(F(Re), { class: "bulk-vue-overlay" }), d(F(Fe), {
						class: "bulk-vue-dialog",
						onEscapeKeyDown: n[11] ||= (e) => {
							e.preventDefault(), F(l).cancelConfirmation();
						},
						onCloseAutoFocus: me
					}, {
						default: a(() => [
							d(F(Ve), null, {
								default: a(() => [z(x(F(B)?.title), 1)]),
								_: 1
							}),
							d(F(Le), null, {
								default: a(() => [z(x(F(B)?.description), 1)]),
								_: 1
							}),
							C("p", null, "范围：" + x(F(B)?.scopeLabel) + " · 预计账号：" + x(F(B)?.count) + " 个", 1),
							C("div", Xa, [d(F(Ie), {
								class: "jobs-tb-btn",
								"data-confirm-cancel": "",
								onClick: F(l).cancelConfirmation
							}, {
								default: a(() => [...n[24] ||= [z("返回", -1)]]),
								_: 1
							}, 8, ["onClick"]), C("button", {
								type: "button",
								class: "jobs-tb-btn jobs-tb-btn--danger",
								"data-confirm-submit": "",
								onClick: n[10] ||= (...e) => F(l).confirm && F(l).confirm(...e)
							}, x(F(B)?.label), 1)])
						]),
						_: 1
					})]),
					_: 1
				})]),
				_: 1
			}, 8, ["open"])
		], 8, la));
	}
}), [["__scopeId", "data-v-d0cadc51"]]), Qa = [
	"batch_id",
	"round_id",
	"result_state",
	"cursor",
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
], $a = /* @__PURE__ */ new Set([
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
]);
function eo(e = {}) {
	let t = [
		"list",
		"create",
		"detail"
	].includes(e.view || "") ? e.view : "list", n = {
		tab: "bulk",
		view: t
	};
	for (let t of Qa) typeof e[t] == "string" && e[t] && (n[t] = e[t]);
	if (t === "detail") {
		if (!/^[1-9]\d*$/.test(n.batch_id || "")) return {
			tab: "bulk",
			view: "list"
		};
		(n.q || e.reason_code) && (delete n.q, delete n.cursor), n.result_state && $a.has(n.result_state) && (n.result_state = "failed");
	}
	return n;
}
// src/features/bulk/BulkPageShell.vue?vue&type=script&setup=true&lang.ts
var to = ["data-bulk-view"], no = { class: "bulk-page-heading" }, ro = { "data-bulk-title": "" }, io = { class: "bulk-actions" }, ao = ["aria-current"], oo = {
	key: 0,
	class: "bulk-error",
	"data-bulk-error": "",
	role: "alert"
}, so = {
	key: 1,
	class: "bulk-notice",
	"data-bulk-notice": "",
	role: "status"
}, co = {
	key: 2,
	class: "bulk-notice bulk-global-recovery",
	"data-bulk-recovery": "",
	role: "status"
}, lo = ["disabled"], uo = { "data-bulk-content": "" }, fo = ["data-state"], po = { class: "bulk-batch-heading" }, mo = { class: "bulk-batch-heading-copy" }, ho = { id: "bulkBatchDialogTitle" }, go = { id: "bulkBatchDialogDescription" }, _o = { class: "bulk-actions" }, vo = { class: "bulk-batch-body" }, yo = {
	key: 0,
	class: "bulk-error",
	"data-bulk-error": "",
	role: "alert"
}, bo = {
	key: 1,
	class: "bulk-notice",
	"data-bulk-notice": "",
	role: "status"
}, xo = {
	key: 2,
	class: "bulk-notice bulk-global-recovery",
	"data-bulk-recovery": "",
	role: "status"
}, So = ["disabled"], Co = /*#__PURE__*/ I(/* @__PURE__ */ n({
	__name: "BulkPageShell",
	props: {
		deps: {},
		initialNavigation: {}
	},
	setup(e, { expose: n }) {
		let r = e, c = j(eo(r.initialNavigation)), u = j(c.value.view === "list" ? { ...c.value } : {
			tab: "bulk",
			view: "list"
		}), f = k(() => c.value.view === "detail" ? u.value : c.value), p = y(!1), h = y(!1), g = y(""), _ = y(""), v = y(!1), w = y(0), E = j(null), A = y(null), M = y(null), N = y(null), I = !1, L = 0, B = 0, V = !1, H, W = null, ee = "", G = !1, K = y(), q = k(() => p.value && h.value), J = {
			...r.deps.callbacks,
			navigate: (e, t, n) => {
				X(e, t, n);
			},
			updateNavigation: (e) => {
				ye(e);
			},
			notify: (e) => {
				_.value = e, w.value++, r.deps.callbacks.notify(e);
			},
			copyBatch: (e, t, n) => {
				be(e, t, n);
			}
		}, Y = {
			pending: () => r.deps.intents.pending(),
			submit: async (e, t, n) => {
				try {
					return await r.deps.intents.submit(e, t, n);
				} finally {
					w.value++;
				}
			},
			recover: async (e) => {
				try {
					return await r.deps.intents.recover(e);
				} finally {
					w.value++;
				}
			}
		}, te = {
			api: r.deps.api,
			callbacks: J
		}, ne = {
			...r.deps,
			intents: Y,
			callbacks: J
		}, re = {
			api: r.deps.api,
			intents: Y,
			callbacks: J,
			now: r.deps.now
		}, ie = k(() => {
			w.value;
			try {
				return r.deps.intents.pending();
			} catch {
				return [];
			}
		}), ae = k(() => q.value ? c.value.view === "list" ? 7e3 : c.value.view === "create" ? M.value?.needsRefresh ? 2e3 : 0 : N.value?.needsRefresh ? 2e3 : 0 : 0), oe = k(() => c.value.view === "create" ? "新建批次" : "批量任务"), se = k(() => q.value && c.value.view === "detail");
		le(K, () => se.value, () => q.value && c.value.view === "list");
		function ce() {
			h.value = !document.hidden && (r.deps.isVisible?.() ?? !0), V !== q.value && (B++, V = q.value), A.value?.setVisible(q.value && c.value.view === "list"), M.value?.setVisible(q.value && c.value.view === "create"), N.value?.setVisible(q.value && c.value.view === "detail");
		}
		function ue() {
			clearTimeout(H), H = void 0, !I && ae.value && (H = setTimeout(() => {
				H = void 0, ce(), q.value && de(!1);
			}, ae.value));
		}
		async function de(e = !0) {
			if (await t(), I || (ce(), !q.value)) return;
			let n = JSON.stringify([c.value, B]);
			if (W && ee === n) return W;
			let r = (async () => {
				try {
					c.value.view === "list" ? await A.value?.refresh(!e) : c.value.view === "create" ? await M.value?.refresh(e) : (await N.value?.refresh(e), G && (G = !1, await N.value?.showReport()));
				} finally {
					w.value++;
				}
			})();
			W = r, ee = n;
			try {
				await r;
			} finally {
				W === r && (W = null, ee = ""), ue();
			}
		}
		async function fe() {
			p.value = !0, await de(!1);
		}
		async function pe() {
			await t(), q.value && c.value.view === "detail" && await N.value?.showReport();
		}
		function me(e) {
			p.value = e, ce(), ue();
		}
		function he() {
			return { ...c.value };
		}
		function ge(e) {
			c.value.view === "list" && (u.value = { ...c.value }), L++, c.value = eo(e), c.value.view === "list" && (u.value = { ...c.value }), g.value = "", _.value = "", G = !1;
		}
		async function X(e, t = {}, n = !1) {
			ge({
				tab: "bulk",
				view: e,
				...t
			}), G = n, p.value = !0, r.deps.onNavigation(he(), "push"), await de(!1);
		}
		async function _e() {
			await X("list", u.value);
		}
		function ve(e) {
			let t = K.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && _e();
		}
		async function ye(e) {
			L++, c.value = eo({
				...c.value,
				...e
			}), r.deps.onNavigation(he(), Object.keys(e).every((e) => e === "cursor") ? "replace" : "push"), await t(), ue();
		}
		async function be(e, t, n = "plan_check") {
			let i = JSON.parse(JSON.stringify({
				query: e,
				source: t
			}));
			E.value = {
				name: "",
				operation_key: n,
				query: r.deps.adapter.normalize({
					...i.query,
					limit: null
				}),
				source: i.source,
				parameters: {},
				max_concurrency: 3
			}, await X("create");
		}
		async function xe(e = !1, t = "plan_check", n) {
			if (!n) {
				J.notify("账号范围未就绪，请返回账号页重试");
				return;
			}
			let r = e ? n.ids.map((e) => Z(typeof e == "number" && Number.isSafeInteger(e) ? String(e) : e)) : [];
			e && !r.length ? J.notify("请先选择账号") : await be(n.query, e ? {
				kind: "ids",
				entity: "account",
				ids: r
			} : null, t);
		}
		async function Se() {
			await be(r.deps.adapter.normalize(), null);
		}
		async function Ce(e, n) {
			await t(), M.value?.restoreSelectionRequest(e, n);
		}
		async function we() {
			if (v.value) return;
			v.value = !0, g.value = "";
			let e = L;
			try {
				let t = r.deps.intents.pending()[0];
				if (!t) return;
				let n = await r.deps.intents.recover(t);
				if (I || e !== L || !q.value) {
					let e = n.id || n.batch_id || n.round_id;
					J.notify(t.path === "/batches" ? `原批次 #${Z(e)} 已创建` : `原请求回执已找回${e ? "，编号 #" + String(e) : ""}。`);
					return;
				}
				if (t.path === "/selections") E.value = null, await Ce(t.body, n), await X("create"), J.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
				else if (t.path === "/batches") {
					try {
						r.deps.storage.removeItem("turb_bulk_selection_v1");
					} catch {}
					await X("detail", { batch_id: Z(n.id || n.batch_id) });
				} else {
					let e = t.path.match(/^\/batches\/([1-9]\d*)\//);
					e && await X("detail", { batch_id: e[1] }), J.notify("原请求回执已找回。");
				}
			} catch (e) {
				g.value = e instanceof Error ? e.message : String(e);
			} finally {
				v.value = !1, w.value++;
			}
		}
		function Te() {
			let e = q.value;
			ce(), !e && q.value ? de(!1) : ue();
		}
		return o(ae, ue, { flush: "post" }), l(() => {
			ce(), document.addEventListener("visibilitychange", Te);
		}), T(() => {
			I = !0, clearTimeout(H), document.removeEventListener("visibilitychange", Te);
		}), n({
			activate: fe,
			setVisible: me,
			refresh: de,
			showReport: pe,
			navigationState: he,
			restoreNavigation: ge,
			navigate: X,
			fromAccounts: xe,
			recover: we,
			restoreSelectionRequest: Ce
		}), (e, t) => (i(), R("div", {
			class: "bulk-page bulk-page-shell",
			"data-bulk-vue": "",
			"data-bulk-view": c.value.view
		}, [
			C("header", no, [C("h2", ro, x(oe.value), 1), C("div", io, [
				c.value.view === "create" ? (i(), R("button", {
					key: 0,
					type: "button",
					class: "jobs-tb-btn",
					onClick: t[0] ||= (e) => X("list")
				}, "批次列表")) : m("", !0),
				C("button", {
					type: "button",
					class: "jobs-tb-btn",
					"data-bulk-action": "refresh",
					onClick: t[1] ||= (e) => de(!0)
				}, "刷新"),
				C("button", {
					type: "button",
					class: O(["jobs-tb-btn", c.value.view === "create" ? "is-current" : "jobs-tb-btn--primary"]),
					"aria-current": c.value.view === "create" ? "page" : void 0,
					"data-bulk-action": "new",
					onClick: Se
				}, "新建批次", 10, ao)
			])]),
			g.value && c.value.view !== "detail" ? (i(), R("p", oo, x(g.value), 1)) : m("", !0),
			_.value && c.value.view !== "detail" ? (i(), R("p", so, x(_.value), 1)) : m("", !0),
			ie.value.length && c.value.view === "list" ? (i(), R("div", co, [C("span", null, "有 " + x(ie.value.length) + " 个请求未收到回执，草稿已保留。", 1), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: v.value,
				onClick: we
			}, x(v.value ? "正在找回…" : "找回原请求"), 9, lo)])) : m("", !0),
			C("div", uo, [
				s(d(Bt, {
					ref_key: "list",
					ref: A,
					navigation: f.value,
					deps: te
				}, null, 8, ["navigation"]), [[P, c.value.view !== "create"]]),
				s(d(pr, {
					ref_key: "create",
					ref: M,
					navigation: c.value,
					deps: ne,
					seed: E.value,
					visible: q.value && c.value.view === "create"
				}, null, 8, [
					"navigation",
					"seed",
					"visible"
				]), [[P, c.value.view === "create"]]),
				(i(), S(b, { to: "body" }, [C("dialog", {
					ref_key: "batchDialog",
					ref: K,
					class: "bulk-page bulk-batch-dialog",
					"data-bulk-dialog": "",
					"data-state": se.value ? "open" : "closed",
					"aria-labelledby": "bulkBatchDialogTitle",
					"aria-describedby": "bulkBatchDialogDescription",
					onCancel: D(_e, ["prevent"]),
					onClick: ve
				}, [d(F(U), { "teleport-to": K.value }, {
					default: a(() => [C("header", po, [C("div", mo, [C("h2", ho, x(N.value?.batchName || "批次详情"), 1), C("p", go, "批次 #" + x(c.value.batch_id) + " · 查看进度、统计和账号明细", 1)]), C("div", _o, [
						C("button", {
							type: "button",
							class: "jobs-tb-btn",
							"data-bulk-action": "refresh",
							onClick: t[2] ||= (e) => de(!0)
						}, "刷新"),
						C("button", {
							type: "button",
							class: "jobs-tb-btn",
							onClick: Se
						}, "新建批次"),
						C("button", {
							type: "button",
							class: "jobs-tb-btn bulk-batch-close",
							"data-bulk-dialog-close": "",
							"aria-label": "关闭批次详情",
							onClick: _e
						}, [...t[3] ||= [z("关闭 ", -1), C("span", { "aria-hidden": "true" }, "×", -1)]])
					])]), C("div", vo, [
						g.value ? (i(), R("p", yo, x(g.value), 1)) : m("", !0),
						_.value ? (i(), R("p", bo, x(_.value), 1)) : m("", !0),
						ie.value.length ? (i(), R("div", xo, [C("span", null, "有 " + x(ie.value.length) + " 个请求未收到回执，草稿已保留。", 1), C("button", {
							type: "button",
							class: "jobs-tb-btn",
							disabled: v.value,
							onClick: we
						}, x(v.value ? "正在找回…" : "找回原请求"), 9, So)])) : m("", !0),
						d(Za, {
							ref_key: "detail",
							ref: N,
							navigation: c.value,
							deps: re,
							visible: q.value && c.value.view === "detail"
						}, null, 8, ["navigation", "visible"])
					])]),
					_: 1
				}, 8, ["teleport-to"])], 40, fo)]))
			])
		], 8, to));
	}
}), [["__scopeId", "data-v-b32fb451"]]), wo = "turb_bulk_intent:", To = /* @__PURE__ */ new Set([
	400,
	403,
	404,
	409,
	410,
	422,
	429
]);
function Eo(e, t, n) {
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
		let c = wo + a, l = JSON.stringify({
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
			if (To.has(Number(e?.status))) try {
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
				if (r?.startsWith(wo)) {
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
function Do(e, t) {
	e.replaceChildren();
	function n(t) {
		N(r(Mi, { ...t }), e);
	}
	return n(t), {
		setView: n,
		destroy() {
			N(null, e);
		}
	};
}
// src/bulk.ts
var Oo = /* @__PURE__ */ new WeakMap();
function ko(e, t) {
	let n = Oo.get(e);
	if (n) return n;
	let r = Ao(e, t);
	return Oo.set(e, r), r;
}
function Ao(e, t) {
	let n = Ht(), r = {
		get length() {
			return window.sessionStorage.length;
		},
		key: (e) => window.sessionStorage.key(e),
		getItem: (e) => window.sessionStorage.getItem(e),
		setItem: (e, t) => window.sessionStorage.setItem(e, t),
		removeItem: (e) => window.sessionStorage.removeItem(e)
	}, i = Eo(n, r, () => globalThis.crypto?.randomUUID?.() || `bulk-${Date.now()}-${Math.random().toString(36).slice(2)}`), a = A(Co, {
		initialNavigation: t.navigation,
		deps: {
			api: n,
			intents: i,
			storage: r,
			adapter: he(t.query),
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
			a.unmount(), Oo.delete(e);
		}
	});
}
function jo(e, i) {
	let a = j(i.view), o = j(), s = A(n({ setup: () => () => r(Bt, {
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
export { ko as mountBulk, jo as mountBulkList, Do as mountBulkReport };
