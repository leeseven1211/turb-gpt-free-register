import { $ as e, A as t, C as n, E as r, F as i, G as a, H as o, K as s, L as c, M as l, R as u, S as d, T as f, Z as p, _ as m, a as h, c as g, d as _, dt as v, et as y, f as b, ft as x, g as S, h as C, it as w, j as T, k as E, l as D, lt as O, m as k, n as A, nt as j, o as M, r as N, s as P, st as F, t as I, ut as L, v as R, x as z } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { S as ee, _ as B, b as V, d as H, f as U, g as W, h as G, i as K, l as q, m as te, n as J, p as Y, r as X, t as ne, u as re, v as ie, x as ae, y as oe } from "./ListFilterSummary-BjRd_0Sf.js";
import { a as se, i as ce, n as le, o as ue, s as de, t as fe } from "./queryAdapter-DOc4xJ_Q.js";
import { t as pe } from "./errorLabels-Co3XCR-i.js";
import { t as me } from "./useNativeDialog-BgHdu813.js";
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/Dialog/DialogRoot.js
var [he, ge] = /*#__PURE__*/ ee("DialogRoot"), _e = /* @__PURE__ */ n({
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
		let n = e, r = V(n, "open", t, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		}), i = y(), a = y(), { modal: o, unmountOnHide: s } = w(n);
		return ge({
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
}), ve = /* @__PURE__ */ n({
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
		B();
		let n = he();
		return (r, o) => (i(), S(F(U), E(t, {
			type: e.as === "button" ? "button" : void 0,
			onClick: o[0] ||= (e) => F(n).onOpenChange(!1)
		}), {
			default: a(() => [u(r.$slots, "default")]),
			_: 3
		}, 16, ["type"]));
	}
}), ye = ["Enter", " "], be = [
	"ArrowDown",
	"PageUp",
	"Home"
], xe = [
	"ArrowUp",
	"PageDown",
	"End"
];
[...be, ...xe], [...ye], [...ye];
function Se(e) {
	return e ? "open" : "closed";
}
// ../../../../../code/personal/gpt/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/Dialog/DialogContentImpl.js
var Ce = /* @__PURE__ */ n({
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
		let n = e, r = t, o = he(), { forwardRef: s, currentElement: c } = B();
		return o.titleId ||= te(void 0, "reka-dialog-title"), o.descriptionId ||= te(void 0, "reka-dialog-description"), l(() => {
			o.contentElement = c, ae() !== document.body && (o.triggerElement.value = ae());
		}), (t, c) => (i(), S(F(re), {
			"as-child": "",
			loop: "",
			trapped: n.trapFocus,
			present: n.present,
			onMountAutoFocus: c[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: c[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: a(() => [d(F(H), E({
				id: F(o).contentId,
				ref: F(s),
				as: e.as,
				"as-child": e.asChild,
				present: n.present,
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				role: "dialog",
				"aria-describedby": F(o).descriptionId,
				"aria-labelledby": F(o).titleId,
				"data-state": F(Se)(F(o).open.value)
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
}), we = /* @__PURE__ */ n({
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
		let n = e, r = t, s = he(), c = ie(r), { forwardRef: l, currentElement: d } = B(), f = k(() => n.present ? d.value : void 0);
		G(f);
		let p = k(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return o(() => n.present, (e, t) => {
			!e && t && s.triggerElement.value?.focus();
		}), (t, r) => (i(), S(Ce, E({
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
}), Te = /* @__PURE__ */ n({
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
		let n = e, r = ie(t);
		B();
		let s = he(), c = y(!1), l = y(!1), d = k(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return o(() => n.present, (e, t) => {
			!e && t && (c.value || s.triggerElement.value?.focus(), c.value = !1, l.value = !1);
		}), (t, n) => (i(), S(Ce, E({
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
}), Ee = /* @__PURE__ */ n({
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
		let n = e, r = t, o = he(), c = ie(r), { forwardRef: l } = B(), d = k(() => n.forceMount || !o.unmountOnHide.value);
		return (t, r) => (i(), S(F(Y), {
			present: F(o).open.value,
			"force-mount": d.value
		}, {
			default: a(({ present: r }) => [F(o).modal.value ? s((i(), S(we, E({
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
			}, 16, ["present"])), [[P, e.forceMount || F(o).unmountOnHide.value || r]]) : s((i(), S(Te, E({
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
}), De = /* @__PURE__ */ n({
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
		B();
		let n = he();
		return (e, r) => (i(), S(F(U), E(t, { id: F(n).descriptionId }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), Oe = /* @__PURE__ */ n({
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
		let t = e, n = he(), r = oe(t.present);
		return o(() => t.present, (e) => r.value = e), B(), (t, r) => (i(), S(F(U), {
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
}), ke = /* @__PURE__ */ n({
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
		let t = e, n = he(), { forwardRef: r } = B(), o = k(() => t.forceMount || !n.unmountOnHide.value);
		return (t, c) => F(n)?.modal.value ? (i(), S(F(Y), {
			key: 0,
			present: F(n).open.value,
			"force-mount": o.value
		}, {
			default: a(({ present: i }) => [s(d(Oe, E(t.$attrs, {
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
}), Ae = /* @__PURE__ */ n({
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
		return (e, n) => (i(), S(F(q), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), je = /* @__PURE__ */ n({
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
		let t = e, n = he();
		return B(), (e, r) => (i(), S(F(U), E(t, { id: F(n).titleId }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), [Me, Ne] = /*#__PURE__*/ ee("AlertDialogContent"), Pe = /* @__PURE__ */ n({
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
		let r = e, o = ie(n);
		B();
		let s = y();
		return Ne({ onCancelElementChange: (e) => {
			s.value = e;
		} }), (e, n) => (i(), S(F(Ee), E({
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
}), Fe = /* @__PURE__ */ n({
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
		let t = e, n = Me(), { forwardRef: r, currentElement: o } = B();
		return l(() => {
			n.onCancelElementChange(o.value);
		}), (e, n) => (i(), S(F(ve), E(t, { ref: F(r) }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ie = /* @__PURE__ */ n({
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
		return B(), (e, n) => (i(), S(F(De), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Le = /* @__PURE__ */ n({
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
		return B(), (e, n) => (i(), S(F(ke), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Re = /* @__PURE__ */ n({
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
		return (e, n) => (i(), S(F(q), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), ze = /* @__PURE__ */ n({
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
		let n = W(e, t);
		return B(), (e, t) => (i(), S(F(_e), E(F(n), { modal: !0 }), {
			default: a((t) => [u(e.$slots, "default", L(f(t)))]),
			_: 3
		}, 16));
	}
}), Be = /* @__PURE__ */ n({
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
		return B(), (e, n) => (i(), S(F(je), L(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ve = ["aria-label", "aria-busy"], He = { class: "cursor-pagination__layout" }, Ue = {
	class: "cursor-pagination__count",
	"aria-live": "polite"
}, We = { class: "cursor-pagination__actions" }, Ge = ["disabled"], Ke = ["disabled"], qe = ["disabled"], Je = /*#__PURE__*/ I(/* @__PURE__ */ n({
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
		}, [C("div", He, [C("span", Ue, "本页 " + x(e.itemCount) + " 个", 1), C("div", We, [
			e.hasCursor ? (i(), R("button", {
				key: 0,
				type: "button",
				class: "cursor-pagination__first",
				"data-cursor-first": "",
				disabled: e.busy,
				onClick: s
			}, "返回首页", 8, Ge)) : m("", !0),
			C("button", {
				type: "button",
				"data-cursor-previous": "",
				disabled: e.busy || !e.hasPrevious,
				onClick: a
			}, "上一页", 8, Ke),
			C("button", {
				type: "button",
				"data-cursor-next": "",
				disabled: e.busy || !e.nextCursor,
				onClick: o
			}, "下一页", 8, qe)
		])])], 8, Ve));
	}
}), [["__scopeId", "data-v-07618f56"]]);
// src/features/bulk/contracts.ts
function Z(e) {
	if (typeof e != "string" || !/^[1-9]\d*$/.test(e)) throw Error("任务标识无效");
	return e;
}
function Ye(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("批次列表响应格式无效");
	return e;
}
function Xe(e) {
	let t = Ye(e);
	if (!Array.isArray(t.items)) throw Error("批次列表响应格式无效");
	let n = t.items.map((e) => {
		let t = Ye(e), n = Number.isSafeInteger(t.id) ? String(t.id) : t.id;
		if (typeof n != "string" || !/^[1-9]\d*$/.test(n)) throw Error("批次编号无效");
		return {
			...t,
			id: n
		};
	}), r = t.next_cursor ?? (t.page == null ? null : Ye(t.page).next_cursor);
	if (r != null && typeof r != "string") throw Error("批次分页响应格式无效");
	return {
		items: n,
		summary: t.summary == null ? {} : Ye(t.summary),
		nextCursor: r || null
	};
}
// src/features/bulk/useBulkList.ts
var Ze = [
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
];
function Qe(e) {
	let t = {
		tab: "bulk",
		view: "list",
		cursor: e.cursor || ""
	};
	for (let n of Ze) t[n] = e[n] || "";
	return t;
}
function $e(e, t) {
	let n = /* @__PURE__ */ new Date(`${e}T00:00:00`), [r, i, a] = e.split("-").map(Number);
	if (!/^\d{4}-\d{2}-\d{2}$/.test(e) || n.getFullYear() !== r || n.getMonth() + 1 !== i || n.getDate() !== a) throw Error("创建日期无效，请调整筛选条件");
	return t && n.setDate(n.getDate() + 1), n.toISOString();
}
function et(e) {
	let t = new URLSearchParams({ page_size: "20" });
	return e.cursor && t.set("cursor", e.cursor), e.q && t.set("q", e.q), e.operation && t.set("operation_key[]", e.operation), e.state && t.set("control_state[]", e.state), e.created_from && t.set("created_from", $e(e.created_from, !1)), e.created_to && t.set("created_before", $e(e.created_to, !0)), t;
}
function tt(t, n) {
	let r = j(Qe(t())), i = j(null), a = j([]), s = k(() => a.value.length > 0), c = y(!1), l = y(!1), u = y(""), d = !1, f, m;
	function h() {
		f?.abort(), f = void 0, m = void 0, l.value = !1;
	}
	function g(e) {
		return e.cursor === r.value.cursor && Ze.every((t) => e[t] === r.value[t]) ? !1 : (h(), r.value = e, i.value = null, u.value = "", !0);
	}
	function _(e = !1, a) {
		if (d || !c.value || t().view !== "list") return Promise.resolve();
		if (m) return e || (l.value = !0), m;
		let o = new AbortController();
		return f = o, l.value = !e || !i.value, m = (async () => {
			try {
				let t = await n.api.request(`/batches?${et(r.value)}`, {
					method: "GET",
					signal: o.signal
				});
				if (o.signal.aborted || a && !a()) return;
				let s = i.value, c = Xe(t);
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
		return g(Qe({
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
		e.view === "list" ? g(Qe(e)) && (a.value = [], c.value && _()) : h();
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
var nt = ["aria-busy"], rt = ["data-bulk-stat", "title"], it = { class: "bl-kpi-value" }, at = ["title"], ot = { key: 0 }, st = ["title"], ct = ["aria-label"], lt = {
	key: 1,
	class: "ui-list-toolbar bl-toolbar"
}, ut = { class: "ui-list-toolbar__main bl-toolbar-main" }, dt = { class: "ui-list-toolbar__actions" }, ft = {
	key: 2,
	class: "ui-list-feedback is-error bl-error",
	role: "alert"
}, pt = ["disabled"], mt = ["disabled"], ht = ["disabled"], gt = { class: "ui-table ui-table--sticky-end bl-table" }, _t = { class: "bl-col-name" }, vt = { class: "list-filter-actions" }, yt = { class: "list-filter-options" }, bt = { class: "list-filter-option" }, xt = ["checked"], St = [
	"value",
	"checked",
	"onChange"
], Ct = { class: "list-filter-options" }, wt = { class: "list-filter-option" }, Tt = ["checked"], Et = [
	"value",
	"checked",
	"onChange"
], Dt = { class: "bl-filter-fields" }, Ot = ["value"], kt = ["value"], At = { class: "list-filter-actions" }, jt = ["data-bulk-row"], Mt = { class: "bl-col-name" }, Nt = [
	"disabled",
	"title",
	"onClick"
], Pt = ["title"], Ft = { "data-bulk-progress": "" }, It = { class: "bl-progress-copy" }, Lt = [
	"value",
	"max",
	"aria-label"
], Rt = {
	key: 1,
	class: "bl-secondary"
}, zt = { class: "bl-results" }, Bt = ["disabled", "onClick"], Vt = ["disabled", "onClick"], Ht = { class: "bl-date" }, Ut = ["disabled", "onClick"], Wt = /*#__PURE__*/ I(/* @__PURE__ */ n({
	__name: "BulkList",
	props: {
		navigation: {},
		deps: {}
	},
	setup(e, { expose: t }) {
		let n = e, r = tt(() => n.navigation, n.deps), { navigation: l, items: u, summary: f, nextCursor: p, loading: h, visible: g, error: b, hasPrevious: w, stale: T } = r, E = y(null), A = y(""), j = y(), N = {
			plan_check: "查询套餐",
			token_refresh: "刷新 AT",
			password_setup: "补密码",
			twofa_setup: "补 2FA",
			codex_retry: "补 Codex",
			account_completion: "组合补全"
		}, P = (e) => e === "active" || e === "settling" ? "active" : [
			"paused",
			"cancel_requested",
			"stop_requested"
		].includes(e) ? "warning" : "neutral", I = {
			active: "执行中",
			paused: "已暂停",
			cancel_requested: "取消中",
			stop_requested: "停止中",
			ended: "已结束"
		}, L = {
			...I,
			settling: "汇总中",
			completed: "已完成",
			preparing: "准备中"
		}, ee = [
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
			let o = V(e.control), s = V(e.operation), c = o.paused ?? e.is_paused ? "paused" : U(o.state ?? e.control_state ?? e.state, "preparing"), l = U(s.key ?? e.operation_key ?? e.action_key), u = e.id, d = a ? ee.reduce((e, t) => e + (r[t] || 0), 0) : null, f = i === null || d === null ? null : i === 0 ? 0 : Math.min(100, Math.round(100 * d / i));
			return {
				id: u,
				name: U(e.name ?? e.title, `批次 #${u}`),
				operation: N[l] || l,
				state: c,
				status: L[c] || c,
				counts: r,
				known: a,
				done: d,
				total: i,
				percent: f,
				createdAt: n.deps.callbacks.formatDateTime(e.created_at)
			};
		})), G = k(() => {
			let e = H(f.value.success_targets), t = H(f.value.partial_success_targets), n = H(f.value.failed_targets), r = H(f.value.attention_targets);
			r !== null && n !== null && (n += r);
			let i = e !== null && t !== null && n !== null ? e + t + n : null;
			return {
				success: e,
				partial: t,
				failed: n,
				total: i
			};
		});
		function q(e, t) {
			return (100 * e / t).toFixed(1);
		}
		let te = k(() => {
			let e = H(f.value.total_batches), t = H(f.value.paused_batches), n = H(f.value.ended_batches), r = G.value;
			return [
				{
					key: "total_batches",
					label: "批次总数",
					value: e,
					unit: "批",
					tone: "neutral",
					detail: X.value.length ? "当前筛选" : "全部批次"
				},
				{
					key: "active_batches",
					label: "执行中",
					value: H(f.value.active_batches),
					unit: "批",
					tone: "active",
					detail: t === null ? "" : `已暂停 ${t.toLocaleString("zh-CN")}`
				},
				{
					key: "ended_batches",
					label: "已结束",
					value: n,
					unit: "批",
					tone: "neutral",
					detail: n !== null && e ? `占 ${q(n, e)}%` : ""
				},
				{
					key: "success_targets",
					label: "成功账号",
					value: r.success,
					unit: "个",
					tone: "success",
					detail: r.partial === null ? "" : `部分成功 ${r.partial.toLocaleString("zh-CN")}`
				},
				{
					key: "failed_targets",
					label: "失败账号",
					value: r.failed,
					unit: "个",
					tone: "warning",
					detail: r.failed !== null && r.total ? `占 ${q(r.failed, r.total)}%` : ""
				},
				{
					key: "success_rate",
					label: "成功率",
					value: r.total && r.success !== null ? 100 * r.success / r.total : null,
					unit: "%",
					tone: "success",
					detail: "",
					available: r.total !== null
				}
			].filter((e) => e.value !== null || e.available).map((e) => ({
				...e,
				display: e.value === null ? "—" : e.key === "success_rate" ? e.value.toFixed(1) : e.value.toLocaleString("zh-CN")
			}));
		}), Y = k(() => {
			let { success: e, partial: t, failed: n, total: r } = G.value;
			return r ? [
				{
					key: "success",
					label: "成功",
					value: e
				},
				{
					key: "partial",
					label: "部分成功",
					value: t
				},
				{
					key: "failed",
					label: "失败",
					value: n
				}
			].map((e) => ({
				...e,
				width: `${100 * e.value / r}%`
			})) : [];
		}), X = k(() => {
			let e = l.value;
			return [
				["q", e.q ? `批次：${e.q}` : ""],
				["operation", e.operation ? `操作：${N[e.operation] || e.operation}` : ""],
				["state", e.state ? `状态：${I[e.state] || e.state}` : ""],
				["date", e.created_from || e.created_to ? `创建日期：${e.created_from || "不限"} 至 ${e.created_to || "不限"}` : ""]
			].filter(([, e]) => e).map(([e, t]) => ({
				key: e,
				label: t,
				removeLabel: `移除${t}`
			}));
		});
		o(() => l.value.q, (e) => {
			A.value = e || "";
		}, { immediate: !0 }), o(() => n.navigation.view, () => {
			E.value = null;
		});
		function re(e) {
			e === "date" ? r.applyFilters({
				created_from: "",
				created_to: ""
			}) : r.applyFilters({ [e]: "" });
		}
		function ie(e, t) {
			r.applyFilters({ [e]: t });
		}
		function ae() {
			r.applyFilters({ q: A.value.trim() }), E.value = null;
		}
		function oe(e, t) {
			g.value && !T.value && n.deps.callbacks.navigate("detail", {
				batch_id: e,
				...t ? { result_state: t } : {}
			});
		}
		function se(e) {
			g.value && !T.value && n.deps.callbacks.navigate("detail", { batch_id: e }, !0);
		}
		function ce() {
			let e = window.getSelection();
			return T.value || !(e?.toString() && j.value?.contains(e.anchorNode));
		}
		async function le(e = !1) {
			ce() && await r.refresh(e, ce);
		}
		function ue(e) {
			e || (E.value = null), r.setVisible(e);
		}
		return t({
			refresh: le,
			setVisible: ue
		}), (t, n) => (i(), R("section", {
			class: "ui-list bl-root",
			"aria-label": "批次列表",
			"aria-busy": F(h)
		}, [
			te.value.length ? (i(), R("div", {
				key: 0,
				class: "bl-kpis",
				style: v({ "--bl-kpi-count": te.value.length }),
				"aria-label": "当前筛选范围的全部批次统计",
				title: "统计覆盖当前筛选范围的全部批次；同一账号在不同批次分别计数，批次内取账号当前结果。"
			}, [(i(!0), R(_, null, c(te.value, (e) => (i(), R("div", {
				key: e.key,
				class: O(["bl-kpi", `is-${e.tone}`]),
				"data-bulk-stat": e.key,
				title: e.key === "success_rate" ? "成功率 = 成功 ÷（成功 + 部分成功 + 失败），不含待执行、取消和未执行。" : void 0
			}, [
				C("span", null, x(e.label), 1),
				C("div", it, [C("strong", { title: e.display }, [z(x(e.display), 1), e.value === null ? m("", !0) : (i(), R("small", ot, x(e.unit), 1))], 8, at), e.detail ? (i(), R("span", {
					key: 0,
					class: "bl-kpi-detail",
					title: e.detail
				}, x(e.detail), 9, st)) : m("", !0)]),
				e.key === "success_rate" && Y.value.length ? (i(), R("span", {
					key: 0,
					class: "bl-kpi-rail",
					role: "img",
					"aria-label": Y.value.map((e) => `${e.label} ${e.value}`).join("，")
				}, [(i(!0), R(_, null, c(Y.value, (e) => (i(), R("i", {
					key: e.key,
					class: O(`is-${e.key}`),
					style: v({ width: e.width }),
					"aria-hidden": "true"
				}, null, 6))), 128))], 8, ct)) : m("", !0)
			], 10, rt))), 128))], 4)) : m("", !0),
			X.value.length ? (i(), R("div", lt, [C("div", ut, [d(ne, {
				items: X.value,
				onRemove: re
			}, null, 8, ["items"])]), C("div", dt, [C("button", {
				type: "button",
				class: "ui-link",
				onClick: n[0] ||= (...e) => F(r).resetFilters && F(r).resetFilters(...e)
			}, "清除筛选")])])) : m("", !0),
			F(b) ? (i(), R("div", ft, [
				C("span", null, x(F(b)), 1),
				C("button", {
					type: "button",
					class: "ui-link",
					disabled: F(h),
					onClick: n[1] ||= (e) => F(r).refresh()
				}, "重试", 8, pt),
				F(T) && F(l).cursor ? (i(), R("button", {
					key: 0,
					class: "ui-link",
					type: "button",
					disabled: F(h),
					onClick: n[2] ||= (...e) => F(r).first && F(r).first(...e)
				}, " 返回首页", 8, mt)) : m("", !0),
				F(T) && F(w) ? (i(), R("button", {
					key: 1,
					class: "ui-link",
					type: "button",
					disabled: F(h),
					onClick: n[3] ||= (...e) => F(r).previous && F(r).previous(...e)
				}, " 上一页 ", 8, ht)) : m("", !0)
			])) : m("", !0),
			C("div", {
				ref_key: "tableHost",
				ref: j,
				class: "ui-table-scroll bl-table-wrap",
				tabindex: "0",
				role: "region",
				"aria-label": "批次列表内容"
			}, [C("table", gt, [C("thead", null, [C("tr", null, [
				C("th", _t, [d(K, {
					label: "批次名称或编号",
					"trigger-label": "批次",
					active: !!F(l).q,
					summary: F(l).q,
					open: E.value === "q",
					"onUpdate:open": n[6] ||= (e) => E.value = e ? "q" : null
				}, {
					default: a(() => [C("form", {
						class: "bl-filter-fields",
						onSubmit: D(ae, ["prevent"])
					}, [C("label", null, [n[16] ||= z("名称或批次号", -1), s(C("input", {
						"onUpdate:modelValue": n[4] ||= (e) => A.value = e,
						type: "search",
						placeholder: "搜索批次名称或编号",
						autocomplete: "off"
					}, null, 512), [[M, A.value]])]), C("div", vt, [C("button", {
						type: "button",
						onClick: n[5] ||= (e) => re("q")
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
				C("th", null, [d(K, {
					label: "操作类型",
					active: !!F(l).operation,
					summary: N[F(l).operation || ""] || F(l).operation,
					open: E.value === "operation",
					"onUpdate:open": n[8] ||= (e) => E.value = e ? "operation" : null
				}, {
					default: a(() => [C("fieldset", yt, [
						n[19] ||= C("legend", { class: "ui-sr-only" }, "操作类型", -1),
						C("label", bt, [C("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: "",
							checked: !F(l).operation,
							onChange: n[7] ||= (e) => ie("operation", "")
						}, null, 40, xt), n[18] ||= z("全部操作", -1)]),
						(i(), R(_, null, c(N, (e, t) => C("label", {
							class: "list-filter-option",
							key: t
						}, [C("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: t,
							checked: F(l).operation === t,
							onChange: (e) => ie("operation", t)
						}, null, 40, St), z(x(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				C("th", null, [d(K, {
					label: "状态",
					active: !!F(l).state,
					summary: I[F(l).state || ""] || F(l).state,
					open: E.value === "state",
					"onUpdate:open": n[10] ||= (e) => E.value = e ? "state" : null
				}, {
					default: a(() => [C("fieldset", Ct, [
						n[21] ||= C("legend", { class: "ui-sr-only" }, "运行状态", -1),
						C("label", wt, [C("input", {
							type: "radio",
							name: "bulk-list-state",
							value: "",
							checked: !F(l).state,
							onChange: n[9] ||= (e) => ie("state", "")
						}, null, 40, Tt), n[20] ||= z("全部状态", -1)]),
						(i(), R(_, null, c(I, (e, t) => C("label", {
							class: "list-filter-option",
							key: t
						}, [C("input", {
							type: "radio",
							name: "bulk-list-state",
							value: t,
							checked: F(l).state === t,
							onChange: (e) => ie("state", t)
						}, null, 40, Et), z(x(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				n[24] ||= C("th", null, "完成进度", -1),
				n[25] ||= C("th", null, "当前结果", -1),
				C("th", null, [d(K, {
					label: "创建时间",
					active: !!(F(l).created_from || F(l).created_to),
					summary: `${F(l).created_from || "不限"} 至 ${F(l).created_to || "不限"}`,
					open: E.value === "date",
					"onUpdate:open": n[14] ||= (e) => E.value = e ? "date" : null
				}, {
					default: a(() => [C("div", Dt, [
						C("label", null, [n[22] ||= z("开始日期", -1), C("input", {
							type: "date",
							value: F(l).created_from,
							onChange: n[11] ||= (e) => ie("created_from", e.target.value)
						}, null, 40, Ot)]),
						C("label", null, [n[23] ||= z("截止日期", -1), C("input", {
							type: "date",
							value: F(l).created_to,
							onChange: n[12] ||= (e) => ie("created_to", e.target.value)
						}, null, 40, kt)]),
						C("div", At, [C("button", {
							type: "button",
							onClick: n[13] ||= (e) => re("date")
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
				C("td", Mt, [C("button", {
					type: "button",
					class: "ui-link bl-name",
					"data-bulk-open": "",
					disabled: F(T),
					title: e.name,
					onClick: (t) => oe(e.id)
				}, x(e.name), 9, Nt), C("span", {
					class: "bl-secondary",
					title: `批次 #${e.id}`
				}, "#" + x(e.id), 9, Pt)]),
				C("td", null, x(e.operation), 1),
				C("td", null, [C("span", { class: O(["ui-badge bl-status", `ui-badge--${P(e.state)}`]) }, x(e.status), 3)]),
				C("td", Ft, [e.total !== null && e.done !== null ? (i(), R(_, { key: 0 }, [C("span", It, [z(x(e.done) + " / " + x(e.total) + " ", 1), C("span", null, x(e.percent) + "%", 1)]), C("progress", {
					value: e.done,
					max: Math.max(1, e.total),
					"aria-label": `已结束 ${e.done} 个，共 ${e.total} 个`
				}, null, 8, Lt)], 64)) : (i(), R("span", Rt, x(e.total === null ? "名单准备中" : "结果待汇总"), 1))]),
				C("td", null, [C("div", zt, [C("button", {
					type: "button",
					class: "bl-result is-success",
					"data-bulk-result": "success",
					disabled: F(T) || !e.counts.success,
					onClick: (t) => oe(e.id, "success")
				}, " 成功 " + x(e.known ? e.counts.success || 0 : "—"), 9, Bt), C("button", {
					type: "button",
					class: "bl-result is-failed",
					"data-bulk-result": "failed",
					disabled: F(T) || !e.counts.failed,
					onClick: (t) => oe(e.id, "failed")
				}, " 失败 " + x(e.known ? e.counts.failed || 0 : "—"), 9, Vt)])]),
				C("td", Ht, x(e.createdAt), 1),
				C("td", null, [C("button", {
					type: "button",
					class: "ui-link",
					"data-bulk-report": "",
					disabled: F(T),
					onClick: (t) => se(e.id)
				}, " 查看报告 ", 8, Ut)])
			], 8, jt))), 128)), W.value.length ? m("", !0) : (i(), S(J, {
				key: 0,
				colspan: 7,
				loading: F(h),
				error: F(b) ? " " : "",
				"loading-title": "正在加载批次…",
				"error-title": "暂时无法读取批次",
				title: X.value.length ? "没有匹配的批次" : "还没有批次",
				text: "选择操作和账号范围，即可集中执行与追踪结果。"
			}, {
				default: a(() => [!F(h) && !F(b) ? (i(), R("button", {
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
			F(T) ? m("", !0) : (i(), S(Je, {
				key: 3,
				"has-previous": F(w),
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
		], 8, nt));
	}
}), [["__scopeId", "data-v-304c5aa8"]]), Gt = class extends Error {
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
function Kt(e = fetch) {
	return { async request(t, n = {}) {
		if (!t.startsWith("/") || t.startsWith("//")) throw Error("批量接口路径无效");
		let r = await e("/api/bulk" + t, {
			credentials: "same-origin",
			...n
		}), i = r.headers?.get("content-type");
		if (i && !i.includes("application/json")) throw new Gt(r.status === 401 || r.redirected ? "登录已失效，请重新登录后返回。" : "服务返回了非 JSON 响应", r.status);
		let a = await r.json().catch(() => null), o = a && typeof a == "object" && !Array.isArray(a) ? a : {};
		if (!r.ok || o.ok === !1) {
			let e = o.error && typeof o.error == "object" && !Array.isArray(o.error) ? o.error : o, t = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {};
			throw new Gt(String(e.message || (typeof o.error == "string" ? o.error : "") || `请求失败（HTTP ${r.status}）`), r.status, String(e.code || o.code || ""), t(e.details || o.details), typeof e.field == "string" ? e.field : null, t(e.fields || o.fields), typeof o.request_id == "string" ? o.request_id : void 0, typeof e.retryable == "boolean" ? e.retryable : void 0);
		}
		if (typeof a != "object" || !a || Array.isArray(a) || o.ok === !0 && (!o.data || typeof o.data != "object" || Array.isArray(o.data))) throw new Gt("服务返回了无效 JSON 响应", r.status);
		return o.data ?? o;
	} };
}
// src/features/bulk/useBulkCreate.ts
var qt = "turb_bulk_draft_v1", Jt = "turb_bulk_selection_v1", Yt = (e) => JSON.parse(JSON.stringify(e)), Xt = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {};
function Zt(e) {
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
	}), I = k(() => M.value === "ready" ? Number(i.value?.target_count ?? i.value?.total_count) : r.value.source?.kind === "ids" ? r.value.source.ids.length : r.value.source ? null : s.value), L = k(() => r.value.source?.kind === "ids" ? `已选 ${r.value.source.ids.length} 个账号` : r.value.source?.kind === "batch_targets" ? `批次 #${r.value.source.batch_id} 的固定名单` : r.value.query.filters.email ? `邮箱含「${r.value.query.filters.email}」` : "按当前筛选"), R = k(() => l.value ? "正在固定账号范围…" : M.value === "ready" ? "账号范围已固定" : I.value === 0 ? "没有匹配账号" : "匹配账号数量"), z = k(() => l.value ? "正在准备本批次，请稍候" : M.value === "ready" ? "将使用这份固定名单创建批次" : I.value === 0 ? "请调整账号筛选条件" : r.value.source?.kind === "batch_targets" ? "创建时沿用原批次固定名单" : r.value.source?.kind === "ids" ? "将使用已选账号创建批次" : s.value == null ? "正在统计，创建时会核对最终数量" : `当前条件匹配 ${s.value} 个账号，将全部执行`), ee = k(() => A.value?.availability?.available === !1 ? `当前设置不可用：${A.value.availability.reason || Xt(A.value.availability).reason_code || "请检查配置"}。请到配置页调整。` : "");
	function B() {
		try {
			e.storage.setItem(qt, JSON.stringify(r.value));
		} catch {}
	}
	function V() {
		try {
			i.value ? e.storage.setItem(Jt, JSON.stringify(i.value)) : e.storage.removeItem(Jt);
		} catch {}
	}
	function H(e) {
		return [e?.request_parameters, e?.parameters].some((e) => Object.keys(e || {}).some((e) => e !== "timezone_offset_min" || r.value.operation_key !== "plan_check"));
	}
	function U(n) {
		let r = Xt(n), i = e.adapter.normalize(Xt(r.query)), a = r.source && typeof r.source == "object" ? Yt(r.source) : null;
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
	function W(e, t) {
		let n = U(e);
		r.value = n.draft;
		let a = Xt(t);
		i.value = typeof a.id == "string" ? Yt(a) : null, (n.limited || H(i.value)) && (i.value = null), B(), V();
	}
	W(n(qt), n(Jt));
	function G() {
		d.value = "", f.value = "", m.value = "";
	}
	function K(e, t = "") {
		let n = e;
		d.value = t + (n.message || String(e)) + (n.code ? `（${n.code}）` : "") + (n.status === 401 ? "，请重新登录后返回，草稿与请求身份已保留。" : ""), f.value = n.field || "";
	}
	let q = (e) => Xt(e).name === "AbortError";
	function te(e) {
		x = e, e || (clearTimeout(D), _.forEach((e) => e.abort()));
	}
	async function J(t) {
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
	async function Y(e = !1) {
		if (a.value && !e) return;
		let t = await J("/catalog");
		b || (a.value = t, O.value.some((e) => e.key === r.value.operation_key) || (r.value.operation_key = O.value[0]?.key || "", i.value = null, V(), B()));
	}
	async function X() {
		if (!x || b) return;
		let t = v, n = JSON.stringify(e.adapter.normalize(r.value.query)), i = g.get(n);
		if (i && e.now() - i.at < 3e4) {
			o.value = i.facets, s.value = i.matched;
			return;
		}
		s.value = null;
		let a = await J(`/query-facets?query=${encodeURIComponent(n)}`), c = Xt(a.facets || a), l = a.matched == null ? null : Number(a.matched);
		g.set(n, {
			facets: c,
			matched: l,
			at: e.now()
		}), g.size > 10 && g.delete(g.keys().next().value), !b && t === v && n === JSON.stringify(e.adapter.normalize(r.value.query)) && (o.value = c, s.value = l);
	}
	function ne() {
		if (clearTimeout(D), !x) return;
		let e = v;
		D = setTimeout(() => {
			X().catch((t) => {
				!q(t) && !b && e === v && K(t, "筛选选项更新失败：");
			});
		}, 350);
	}
	function re() {
		v++, E = null, l.value = !1, i.value = null, V();
	}
	function ie(e) {
		re(), clearTimeout(D), W(Yt(e), null), s.value = null, G(), S && ne();
	}
	function ae(e, t) {
		l.value || (e === "name" ? r.value.name = String(t) : r.value.max_concurrency = Number(t), B());
	}
	function oe(e) {
		l.value || r.value.operation_key === e || (r.value.operation_key = e, re(), G(), B());
	}
	function ue(t) {
		if (l.value) return;
		let n = e.adapter.normalize({
			...t,
			limit: null
		});
		JSON.stringify(n) !== JSON.stringify(r.value.query) && (r.value.query = n, s.value = null, re(), G(), B(), ne());
	}
	function de(e, t) {
		let n = Yt(r.value.query);
		[
			"q",
			"archived",
			"date_from",
			"date_to",
			"plan"
		].includes(e) ? Object.assign(n, { [e]: t }) : Object.assign(n.filters, { [e]: t }), ue(n);
	}
	function fe(e) {
		e === "date" ? ue({
			...r.value.query,
			date_from: "",
			date_to: ""
		}) : de(e, e === "archived" ? "0" : [
			"q",
			"email",
			"id"
		].includes(e) ? "" : []);
	}
	function pe() {
		l.value || (r.value.source = null, r.value.query = e.adapter.normalize(), s.value = null, re(), G(), B(), ne());
	}
	function me(t, n) {
		return e.callbacks.facetLabel?.(t, n) || n;
	}
	function he(e) {
		let t = le.find((t) => t.key === e);
		if (!t || t.kind !== "enum") return [];
		let n = a.value?.query_schema?.fields, i = Array.isArray(n) ? n.map(Xt).find((t) => t.key === e) : void 0, s = i?.options ?? i?.enum ?? i?.values, c = o.value[e], l = e === "promotion" ? c ?? [] : c ?? (Array.isArray(s) ? s : []), u = e !== "promotion" && c == null && Array.isArray(s), d = e === "promotion" ? { promotion: l.map((e) => {
			let t = typeof e == "object" && e ? e : { value: String(e) };
			return {
				...t,
				value: String(t.value),
				count: t.count == null ? +!!u : Number(t.count)
			};
		}) } : { [e]: l.map((e) => {
			let t = typeof e == "object" && e ? e : { value: String(e) };
			return {
				...t,
				value: String(t.value),
				count: t.count == null ? +!!u : Number(t.count)
			};
		}) };
		return ce(r.value.query, d, t, me);
	}
	function ge(e) {
		return he(e).flatMap((e) => e.options);
	}
	let _e = k(() => [
		...se(r.value.query, me, o.value),
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
		return e?.timezone_offset_min || Xt(e?.properties).timezone_offset_min ? { timezone_offset_min: (/* @__PURE__ */ new Date()).getTimezoneOffset() } : {};
	}
	async function ye() {
		if (!i.value || !x || b) return;
		let e = Z(i.value.id), t = v, n = await J(`/selections/${encodeURIComponent(e)}?page_size=1`);
		b || t !== v || i.value?.id !== e || (i.value = {
			...i.value,
			...n
		}, V());
	}
	async function be() {
		if (x && !b) {
			if (C) return C;
			if (!S) return c.value = !0, C = (async () => {
				try {
					if (await Y(), b || !x) return;
					let e = v;
					try {
						await X();
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
			i.value = null, V();
			try {
				await Y(!0);
			} catch (e) {
				K(e, "配置读取失败：");
			}
			!b && n === v && e.callbacks.notify("配置已更新，请重新创建批次。");
		} else r.code === "selection_consumed" && r.details?.existing_batch_id ? (m.value = String(r.details.existing_batch_id), e.callbacks.notify(`该范围已用于批次 #${m.value}`)) : r.code === "selection_expired" && (i.value = null, V());
	}
	async function Se() {
		let t = E;
		if (!t || t.epoch !== v || T === v || b || !x) return;
		let n = v;
		T = n;
		try {
			if (M.value === "preparing") return;
			let a = i.value;
			if (!a || M.value !== "ready") throw new Gt(a?.error?.message || a?.error_detail?.message || "账号范围准备失败，请重试", 0, a?.error_code || "selection_preparation_failed");
			if (Number(a.target_count ?? a.total_count) <= 0) throw new Gt("没有匹配账号，请调整筛选条件", 0, "selection_empty");
			let o = A.value;
			if (!o) throw new Gt("没有可用的批量操作", 0, "operation_unavailable");
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
			i.value = null, V(), E = null, l.value = !1, e.callbacks.notify(x ? t.paused ? "批次已创建并暂停，可在详情继续执行" : "批次已受理，正在后台提交目标" : `原批次 #${u} 已创建${t.paused ? "并暂停" : ""}`), x && e.callbacks.navigate("detail", { batch_id: u });
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
			K(new Gt(`本批并发上限需为 1–${P.value} 的整数`, 0, "invalid_concurrency", {}, "max_concurrency"));
			return;
		}
		if (r.value.name.length > 120) {
			K(new Gt("批次名称最多 120 个字符", 0, "invalid_name", {}, "name"));
			return;
		}
		if (!A.value) {
			K(new Gt("请先读取可用的批量操作", 0, "operation_unavailable"));
			return;
		}
		H(i.value) && (i.value = null, V());
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
					source: Yt(r.value.source || {
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
				}, V(), B();
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
				e && await Y(!0), n || (i.value ? await ye() : await X()), t === v && await Se();
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
		let i = Xt(n.source), a = Xt(n.operation), o = e.adapter.normalize(i.kind === "query" ? Xt(i.query) : {}), s = {
			...t(),
			operation_key: String(a.key || "plan_check"),
			query: o,
			source: i.kind === "query" ? null : i
		};
		re(), W(s, {
			...r,
			request_parameters: Xt(n.parameters),
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
			else if (n.path === "/batches") i.value = null, V(), e.callbacks.navigate("detail", { batch_id: Z(r.id || r.batch_id) });
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
		availabilityWarning: ee,
		chips: _e,
		accountFilters: le,
		filterOptionGroups: he,
		initialize: be,
		refresh: we,
		recover: Ee,
		restoreSelectionRequest: Te,
		loadFacets: X,
		applySeed: ie,
		setVisible: te,
		setDraftField: ae,
		setOperation: oe,
		setQueryField: de,
		clearFilter: fe,
		clearFilters: pe,
		filterOptions: ge,
		createBatch: Ce,
		clearError: G
	};
}
// src/features/bulk/BulkCreate.vue?vue&type=script&setup=true&lang.ts
var Qt = {
	key: 0,
	class: "bulk-empty",
	role: "status"
}, $t = ["aria-busy"], en = { class: "bulk-create-main" }, tn = { class: "bulk-card bulk-create-card" }, nn = { class: "bulk-step-head" }, rn = {
	class: "bulk-operation-grid",
	role: "radiogroup",
	"aria-label": "批量操作"
}, an = ["title"], on = [
	"value",
	"checked",
	"disabled",
	"onChange"
], sn = {
	viewBox: "0 0 24 24",
	fill: "none",
	stroke: "currentColor",
	"stroke-width": "1.6",
	"stroke-linecap": "round",
	"stroke-linejoin": "round",
	"aria-hidden": "true"
}, cn = ["d"], ln = { class: "bulk-card bulk-create-card" }, un = {
	key: 0,
	class: "bulk-error bulk-operation-warning",
	"data-bulk-operation-warning": ""
}, dn = { class: "bulk-batch-fields" }, fn = { class: "bulk-field bulk-name-field" }, pn = [
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], mn = { class: "bulk-field" }, hn = [
	"max",
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], gn = {
	class: "bulk-card bulk-create-card",
	"data-bulk-account-scope": ""
}, _n = { class: "bulk-step-head" }, vn = ["disabled"], yn = {
	key: 0,
	class: "bulk-source-banner"
}, bn = ["disabled"], xn = { "data-bulk-filters": "" }, Sn = { class: "bulk-query-top" }, Cn = { class: "bulk-field bulk-query-search" }, wn = ["value", "disabled"], Tn = ["open"], En = { class: "bulk-filter-popover-panel" }, Dn = { class: "bulk-filter-popover-heading" }, On = { class: "bulk-field" }, kn = ["value", "disabled"], An = { class: "bulk-field" }, jn = ["value", "disabled"], Mn = ["open"], Nn = { class: "bulk-filter-popover-panel" }, Pn = { class: "bulk-filter-popover-heading" }, Fn = { class: "bulk-field" }, In = ["value", "disabled"], Ln = { class: "bulk-field" }, Rn = ["value", "disabled"], zn = {
	class: "bulk-column-filters",
	"aria-label": "账号列筛选"
}, Bn = ["data-filter-field", "open"], Vn = ["onClick"], Hn = {
	key: 0,
	"data-filter-count": ""
}, Un = { class: "bulk-filter-popover-panel" }, Wn = { class: "bulk-filter-popover-heading" }, Gn = ["aria-label"], Kn = {
	key: 0,
	class: "bulk-field"
}, qn = [
	"data-query-filter",
	"value",
	"disabled",
	"onInput"
], Jn = {
	key: 1,
	class: "bulk-filter-options"
}, Yn = {
	key: 0,
	class: "bulk-filter-group-title"
}, Xn = [
	"data-query-filter",
	"value",
	"checked",
	"disabled",
	"onChange"
], Zn = { key: 0 }, Qn = {
	key: 0,
	class: "bulk-muted"
}, $n = {
	class: "bulk-query-chips",
	"data-query-chips": "",
	"aria-label": "已选账号条件"
}, er = [
	"data-clear-query",
	"aria-label",
	"disabled",
	"onClick"
], tr = {
	key: 0,
	class: "bulk-filter-empty"
}, nr = { class: "bulk-card bulk-create-side" }, rr = { class: "bulk-side-sticky" }, ir = { class: "bulk-side-heading" }, ar = { "data-bulk-create-summary": "" }, or = {
	class: "bulk-side-big",
	"data-bulk-side-count": "",
	role: "status",
	"aria-live": "polite",
	"aria-atomic": "true"
}, sr = {
	class: "bulk-side-hint",
	"data-bulk-create-hint": ""
}, cr = { class: "bulk-side-meta" }, lr = { "data-bulk-side-operation": "" }, ur = { "data-bulk-side-scope": "" }, dr = { "data-bulk-side-concurrency": "" }, fr = {
	key: 0,
	class: "bulk-side-warning",
	"data-bulk-side-warning": ""
}, pr = {
	key: 1,
	id: "bulkCreateError",
	class: "bulk-error",
	"data-bulk-action-error": "",
	role: "alert"
}, mr = {
	key: 2,
	class: "bulk-notice",
	"data-bulk-recovery": "",
	role: "status"
}, hr = ["disabled"], gr = { class: "bulk-side-actions" }, _r = ["disabled"], vr = ["disabled"], yr = /*#__PURE__*/ I(/* @__PURE__ */ n({
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
		let r = e, a = Zt(r.deps), { draft: u, loading: d, creating: f, recovering: p, error: h, errorField: v, existingBatchId: b, operations: S, operation: w, concurrencyMax: T, pendingCount: E, count: A, scopeLabel: j, summary: M, hint: N, availabilityWarning: I, chips: L, needsRefresh: ee } = a, B = y(), V = y(""), H = k(() => f.value || p.value), U = a.accountFilters.filter((e) => !["email", "date"].includes(e.key)), W = {
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
		function te(e) {
			let t = (e?.target)?.closest("details");
			V.value = "", (t?.querySelector("summary"))?.focus();
		}
		function J(e, t) {
			if (H.value) return;
			if (V.value === e) {
				V.value = "";
				return;
			}
			let n = t.currentTarget, r = n.nextElementSibling, i = n.getBoundingClientRect().left, a = Math.min(250, window.innerWidth - 48), o = Math.max(10, document.querySelector("main")?.getBoundingClientRect().left ?? 0), s = Math.max(o, Math.min(i, document.documentElement.clientWidth - a - 10));
			r.style.setProperty("--bulk-filter-offset", `${s - i}px`), V.value = e;
		}
		function Y(e) {
			let t = e.target.closest("details");
			t && !t.contains(e.relatedTarget) && (V.value = "");
		}
		return o(() => r.seed, (e) => {
			e && a.applySeed(e);
		}, { immediate: !0 }), o(() => r.visible, (e) => {
			a.setVisible(e), e || (V.value = "");
		}, { immediate: !0 }), o(v, async (e) => {
			e && (await t(), Array.from(B.value?.querySelectorAll("[name],[data-query],[data-query-filter]") || []).find((t) => (t.name || t.dataset.query || t.dataset.queryFilter) === e)?.focus({ preventScroll: !0 }));
		}), l(() => {
			r.visible && a.initialize();
		}), n({
			refresh: a.refresh,
			recover: a.recover,
			restoreSelectionRequest: a.restoreSelectionRequest,
			setVisible: a.setVisible,
			needsRefresh: ee
		}), (t, n) => F(d) && !F(S).length ? (i(), R("div", Qt, "正在读取操作和筛选配置…")) : (i(), R("form", {
			key: 1,
			ref_key: "form",
			ref: B,
			"data-bulk-create-form": "",
			class: "bulk-create-form",
			novalidate: "",
			"aria-busy": H.value,
			onSubmit: n[18] ||= D((e) => F(a).createBatch(), ["prevent"]),
			onKeydown: n[19] ||= g((e) => te(e), ["esc"])
		}, [C("div", en, [
			C("section", tn, [C("div", nn, [
				n[20] ||= C("span", { class: "bulk-step-no" }, "1", -1),
				n[21] ||= C("div", null, [C("h3", null, "选择操作"), C("p", { class: "bulk-section-note" }, "本次要对账号做什么")], -1),
				C("button", {
					type: "button",
					class: "bulk-link",
					"data-bulk-action": "list",
					onClick: n[0] ||= (t) => e.deps.callbacks.navigate("list")
				}, "← 返回批次列表")
			]), C("div", rn, [(i(!0), R(_, null, c(F(S), (e) => (i(), R("label", {
				key: e.key,
				class: "bulk-operation",
				title: e.availability?.available === !1 ? e.availability.reason || "当前不可用" : ""
			}, [
				C("input", {
					type: "radio",
					name: "operation_key",
					value: e.key,
					checked: F(u).operation_key === e.key,
					disabled: H.value,
					required: "",
					onChange: (t) => F(a).setOperation(e.key)
				}, null, 40, on),
				(i(), R("svg", sn, [C("path", { d: G[e.key] || G.account_completion }, null, 8, cn)])),
				C("span", null, [C("strong", null, x(e.label || e.key), 1), C("small", null, x(W[e.key] || "批量账号操作"), 1)]),
				n[22] ||= C("span", {
					class: "bulk-operation-check",
					"aria-hidden": "true"
				}, "✓", -1)
			], 8, an))), 128))])]),
			C("section", ln, [
				n[25] ||= C("div", { class: "bulk-step-head" }, [C("span", { class: "bulk-step-no" }, "2"), C("div", null, [C("h3", null, "批次设置")])], -1),
				F(I) ? (i(), R("p", un, x(F(I)), 1)) : m("", !0),
				C("div", dn, [C("label", fn, [n[23] ||= z("批次名称", -1), C("input", {
					name: "name",
					maxlength: "120",
					value: F(u).name,
					placeholder: "留空自动命名",
					disabled: H.value,
					"aria-invalid": F(v) === "name" || void 0,
					"aria-describedby": F(v) === "name" ? "bulkCreateError" : void 0,
					onInput: n[1] ||= (e) => F(a).setDraftField("name", K(e))
				}, null, 40, pn)]), C("label", mn, [n[24] ||= z("本批并发上限", -1), C("input", {
					name: "max_concurrency",
					type: "number",
					min: "1",
					max: F(T),
					step: "1",
					value: F(u).max_concurrency,
					required: "",
					disabled: H.value,
					"aria-invalid": F(v) === "max_concurrency" || void 0,
					"aria-describedby": F(v) === "max_concurrency" ? "bulkCreateError" : void 0,
					onInput: n[2] ||= (e) => F(a).setDraftField("max_concurrency", K(e))
				}, null, 40, hn)])])
			]),
			C("section", gn, [
				C("div", _n, [
					n[26] ||= C("span", { class: "bulk-step-no" }, "3", -1),
					n[27] ||= C("div", null, [C("h3", null, "账号范围"), C("p", { class: "bulk-section-note" }, "与账号列表使用同一套筛选")], -1),
					C("button", {
						type: "button",
						class: "bulk-link",
						"data-bulk-action": "clear-filters",
						disabled: H.value,
						onClick: n[3] ||= (...e) => F(a).clearFilters && F(a).clearFilters(...e)
					}, "清空条件", 8, vn)
				]),
				F(u).source ? (i(), R("div", yn, [C("span", null, x(F(u).source.kind === "ids" ? "使用已选账号" : `沿用批次 #${F(u).source.batch_id} 的账号名单`), 1), C("button", {
					type: "button",
					class: "bulk-link",
					"data-bulk-action": "use-query",
					disabled: H.value,
					onClick: n[4] ||= (...e) => F(a).clearFilters && F(a).clearFilters(...e)
				}, "改为按条件筛选", 8, bn)])) : m("", !0),
				s(C("div", xn, [
					C("div", Sn, [
						C("label", Cn, [n[28] ||= C("span", { class: "bulk-sr-only" }, "邮箱或姓名", -1), C("input", {
							"data-query": "email",
							type: "search",
							value: F(u).query.filters.email,
							autocomplete: "off",
							placeholder: "搜索邮箱或姓名",
							disabled: H.value,
							onInput: n[5] ||= (e) => F(a).setQueryField("email", K(e))
						}, null, 40, wn)]),
						C("details", {
							class: "bulk-filter-popover",
							"data-filter-dates": "",
							open: V.value === "date",
							onFocusout: Y
						}, [C("summary", { onClick: n[6] ||= D((e) => J("date", e), ["prevent"]) }, [...n[29] ||= [z("创建日期", -1), C("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [C("path", { d: "m4 6 4 4 4-4" })], -1)]]), C("div", En, [
							C("div", Dn, [n[30] ||= C("strong", null, "创建日期", -1), C("button", {
								type: "button",
								"aria-label": "关闭创建日期筛选",
								onClick: n[7] ||= (e) => te(e)
							}, "完成")]),
							C("label", On, [n[31] ||= z("创建日期从", -1), C("input", {
								"data-query": "date_from",
								type: "date",
								value: F(u).query.date_from,
								disabled: H.value,
								onInput: n[8] ||= (e) => F(a).setQueryField("date_from", K(e))
							}, null, 40, kn)]),
							C("label", An, [n[32] ||= z("创建日期至（含当天）", -1), C("input", {
								"data-query": "date_to",
								type: "date",
								value: F(u).query.date_to,
								disabled: H.value,
								onInput: n[9] ||= (e) => F(a).setQueryField("date_to", K(e))
							}, null, 40, jn)])
						])], 40, Tn),
						C("details", {
							class: "bulk-filter-popover",
							open: V.value === "more",
							onFocusout: Y
						}, [C("summary", { onClick: n[10] ||= D((e) => J("more", e), ["prevent"]) }, [...n[33] ||= [z("更多查询", -1), C("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [C("path", { d: "m4 6 4 4 4-4" })], -1)]]), C("div", Nn, [
							C("div", Pn, [n[34] ||= C("strong", null, "更多查询", -1), C("button", {
								type: "button",
								"aria-label": "关闭更多查询筛选",
								onClick: n[11] ||= (e) => te(e)
							}, "完成")]),
							C("label", Fn, [n[35] ||= z("高级搜索", -1), C("input", {
								"data-query": "q",
								type: "search",
								value: F(u).query.q,
								placeholder: "如：协议 jp",
								autocomplete: "off",
								disabled: H.value,
								onInput: n[12] ||= (e) => F(a).setQueryField("q", K(e))
							}, null, 40, In)]),
							C("label", Ln, [n[37] ||= z("归档范围", -1), C("select", {
								"data-query": "archived",
								value: F(u).query.archived,
								disabled: H.value,
								onChange: n[13] ||= (e) => F(a).setQueryField("archived", K(e))
							}, [...n[36] ||= [
								C("option", { value: "0" }, "未归档", -1),
								C("option", { value: "only" }, "仅归档", -1),
								C("option", { value: "all" }, "全部", -1)
							]], 40, Rn)])
						])], 40, Mn)
					]),
					C("div", zn, [(i(!0), R(_, null, c(F(U), (e) => (i(), R("details", {
						key: e.key,
						class: O(["bulk-filter-popover", { "has-value": e.kind === "text" ? !!F(de)(F(u).query, e.key) : !!F(ue)(F(u).query, e.key).length }]),
						"data-filter-field": e.key,
						open: V.value === e.key,
						onFocusout: Y
					}, [C("summary", { onClick: D((t) => J(e.key, t), ["prevent"]) }, [
						z(x(e.label), 1),
						e.kind === "enum" && F(ue)(F(u).query, e.key).length ? (i(), R("span", Hn, x(F(ue)(F(u).query, e.key).length), 1)) : m("", !0),
						n[38] ||= C("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [C("path", { d: "m4 6 4 4 4-4" })], -1)
					], 8, Vn), C("div", Un, [C("div", Wn, [C("strong", null, x(e.label), 1), C("button", {
						type: "button",
						"aria-label": `关闭${e.label}筛选`,
						onClick: n[14] ||= (e) => te(e)
					}, "完成", 8, Gn)]), e.kind === "text" ? (i(), R("label", Kn, [z(x(e.label), 1), C("input", {
						"data-query-filter": e.key,
						value: F(de)(F(u).query, e.key),
						inputmode: "numeric",
						placeholder: "输入账号 ID",
						disabled: H.value,
						onInput: (t) => F(a).setQueryField(e.key, K(t))
					}, null, 40, qn)])) : (i(), R("div", Jn, [(i(!0), R(_, null, c(F(a).filterOptionGroups(e.key), (t) => (i(), R(_, { key: t.key }, [t.label ? (i(), R("p", Yn, x(t.label), 1)) : m("", !0), (i(!0), R(_, null, c(t.options, (t) => (i(), R("label", { key: t.value }, [
						C("input", {
							type: "checkbox",
							"data-query-filter": e.key,
							value: t.value,
							checked: F(ue)(F(u).query, e.key).includes(t.value),
							disabled: H.value,
							onChange: (n) => q(e.key, t.value, n.target.checked)
						}, null, 40, Xn),
						C("span", null, x(t.label), 1),
						e.key === "promotion" && t.count !== null && t.count !== void 0 ? (i(), R("small", Zn, x(t.count), 1)) : m("", !0)
					]))), 128))], 64))), 128)), F(a).filterOptions(e.key).length ? m("", !0) : (i(), R("span", Qn, "暂无可用选项"))]))])], 42, Bn))), 128))]),
					C("div", $n, [(i(!0), R(_, null, c(F(L), (e) => (i(), R("button", {
						key: e.key,
						type: "button",
						class: "bulk-filter-chip",
						"data-clear-query": e.key,
						"aria-label": e.removeLabel,
						disabled: H.value,
						onClick: (t) => F(a).clearFilter(e.key)
					}, [z(x(e.label), 1), n[39] ||= C("span", { "aria-hidden": "true" }, "×", -1)], 8, er))), 128)), F(L).length ? m("", !0) : (i(), R("span", tr, "全部未归档账号"))])
				], 512), [[P, !F(u).source]])
			])
		]), C("aside", nr, [C("div", rr, [
			C("div", ir, [C("div", null, [n[40] ||= C("span", { class: "bulk-side-kicker" }, "执行摘要", -1), C("strong", ar, x(F(M)), 1)])]),
			C("div", or, x(F(A) == null ? F(u).source ? "创建时确认" : "匹配中" : `${F(A)} 个`), 1),
			C("p", sr, x(F(N)), 1),
			C("dl", cr, [
				C("div", null, [n[41] ||= C("dt", null, "操作", -1), C("dd", lr, x(F(w)?.label || F(u).operation_key), 1)]),
				C("div", null, [n[42] ||= C("dt", null, "范围", -1), C("dd", ur, x(F(j)), 1)]),
				C("div", null, [n[43] ||= C("dt", null, "本批并发", -1), C("dd", dr, x(F(u).max_concurrency), 1)])
			]),
			F(A) != null && F(A) >= 200 ? (i(), R("p", fr, "本批将处理 " + x(F(A)) + " 个账号。", 1)) : m("", !0),
			F(h) ? (i(), R("p", pr, [z(x(F(h)), 1), F(b) ? (i(), R("button", {
				key: 0,
				type: "button",
				class: "bulk-link",
				onClick: n[15] ||= (t) => e.deps.callbacks.navigate("detail", { batch_id: F(b) })
			}, "查看批次 #" + x(F(b)), 1)) : m("", !0)])) : m("", !0),
			F(E) ? (i(), R("div", mr, [C("span", null, "有 " + x(F(E)) + " 个请求未收到回执，草稿已保留。", 1), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: H.value,
				onClick: n[16] ||= (...e) => F(a).recover && F(a).recover(...e)
			}, x(F(p) ? "正在找回…" : "找回原请求"), 9, hr)])) : m("", !0),
			C("div", gr, [C("button", {
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				"data-bulk-submit": "",
				disabled: H.value || F(A) === 0 || !F(S).length
			}, x(F(f) ? "正在创建批次…" : "创建并执行"), 9, _r), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "create-paused",
				disabled: H.value || F(A) === 0 || !F(S).length,
				onClick: n[17] ||= (e) => F(a).createBatch(!0)
			}, x(F(f) ? "正在创建批次…" : "创建并暂停"), 9, vr)]),
			n[44] ||= C("p", { class: "bulk-side-foot" }, "提交时固定账号范围，暂停后可继续原批次", -1)
		])])], 40, $t));
	}
}), [["__scopeId", "data-v-f00310b6"]]), br = {
	plan_check: "查套餐",
	token_refresh: "刷新 AT",
	password_setup: "补密码",
	twofa_setup: "补 2FA",
	codex_retry: "补 Codex",
	account_completion: "组合补全"
}, Q = (e) => typeof e == "object" && e && !Array.isArray(e) ? e : {}, xr = (e) => Array.isArray(e) ? e.map(Q) : [], Sr = (e) => br[String(e)] || String(e || "—");
function Cr(e) {
	if (typeof e != "number" && (typeof e != "string" || !e.trim())) return null;
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? t : null;
}
var $ = (e) => Cr(e) === null ? "—" : Math.floor(Number(e)).toLocaleString("zh-CN");
function wr(e) {
	let t = Cr(e);
	if (t === null) return "—";
	if (t < 60) return `${t === 0 ? "0" : t < 1 ? t.toFixed(2) : t.toFixed(1).replace(/\.0$/, "")} 秒`;
	let n = Math.round(t), r = Math.floor(n / 3600), i = Math.floor(n % 3600 / 60), a = n % 60;
	return [
		r ? `${r} 小时` : "",
		i ? `${i} 分` : "",
		a ? `${a} 秒` : ""
	].filter(Boolean).join(" ") || "0 秒";
}
function Tr(e) {
	let t = Q(e.view);
	if (t.kind !== "round") return "当前结果 · 每个账号取最近一轮";
	let n = Cr(t.round_no);
	return n === null || !Number.isSafeInteger(n) || n < 1 ? "所选轮次 · 固定名单" : n === 1 ? "首轮名单" : `重跑 ${n - 1} · 固定名单`;
}
var Er = {
	free: "Free",
	plus: "Plus",
	pro: "Pro",
	team: "Team",
	business: "Business",
	enterprise: "Enterprise",
	go: "Go",
	unknown: "尚未确认"
}, Dr = {
	free_trial: "免费试用",
	half_price: "半价优惠",
	discount: "折扣优惠",
	other_discount: "其他折扣",
	other_promo: "其他优惠"
};
function Or(e, t, n) {
	let r = typeof t == "string" ? t : "";
	return Object.hasOwn(e, r) ? e[r] : r || n;
}
var kr = (e) => Or(Er, e, "尚未确认"), Ar = (e) => Or(Dr, e, "其他优惠");
function jr(e, t) {
	return `${Math.max(0, Math.min(100, t > 0 ? (Cr(e) || 0) / t * 100 : 0))}%`;
}
var Mr = {
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
	...Dr
})) Mr[`account.plus_offer.${e}`] = `优惠 · ${t}`;
for (let [e, t] of Object.entries({
	unchanged: "优惠未变化",
	new_offer: "新增优惠",
	offer_removed: "优惠消失",
	changed: "优惠变化",
	not_comparable: "历史条件不可比较"
})) Mr[`account.comparison.${e}`] = t;
for (let [e, t] of Object.entries({
	password: "密码",
	twofa: "2FA",
	codex: "Codex",
	access_token: "AT",
	plan_check: "套餐"
})) Mr[`step.${e}.confirmed`] = `${t} · 已完成`, Mr[`step.${e}.pending`] = `${t} · 待完成`;
function Nr(e) {
	let t = { ...Q(e) };
	Object.hasOwn(t, "account.token_refresh.unconfirmed") && (t["account.token_refresh.failed"] = (Cr(t["account.token_refresh.failed"]) || 0) + (Cr(t["account.token_refresh.unconfirmed"]) || 0), delete t["account.token_refresh.unconfirmed"]);
	let n = /* @__PURE__ */ new Map();
	function r(e, t = "", i = 0) {
		if (!(i > 3)) for (let [a, o] of Object.entries(e)) {
			if ([
				"schema",
				"schema_version",
				"version",
				"updated_at"
			].includes(a)) continue;
			let e = Or(Mr, a, a), s = t ? `${t} · ${e}` : e;
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
var Pr = {
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
}, Fr = [
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
], Ir = (e) => "is-" + (Fr.includes(String(e)) ? "failed" : String(e || "preparing")), Lr = (e) => {
	let t = Ir(e).slice(3);
	return t === "success" ? "success" : t === "failed" ? "danger" : [
		"attention_required",
		"partial_success",
		"paused"
	].includes(t) ? "warning" : [
		"running",
		"active",
		"preparing"
	].includes(t) ? "active" : "neutral";
}, Rr = (e) => Pr[Fr.includes(String(e)) ? "failed" : String(e)] || String(e || "—"), zr = (e) => String(Q(e?.operation).key || e?.operation_key || e?.action_key || "");
function Br(e) {
	let t = {};
	for (let [n, r] of Object.entries(Q(e))) {
		let e = Fr.includes(n) ? "failed" : n;
		t[e] = (t[e] || 0) + (Cr(r) || 0);
	}
	return t;
}
var Vr = (e) => Z(e.canonical_target_id || e.target_id || e.id);
function Hr(e) {
	return e == null || e === "" ? null : Z(e);
}
function Ur(e) {
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
		let t = [`查询${Rr(e.query_outcome)}`];
		return e.account_plan_type && t.push(`套餐 ${e.account_plan_type}`), e.confirmed_no_offer ? t.push("本次确认无优惠") : e.plus_offer_kind && e.plus_offer_kind !== "unknown" && t.push(Ar(e.plus_offer_kind)), e.comparison && e.comparison !== "not_comparable" && t.push({
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
function Wr(e) {
	let t = Q(e.result), n = Q(t.result || e.result_summary || t), r = Q(e.reason || t.reason || e.error || e.error_info), i = Q(e.display_snapshot || e.display), a = Q(e.execution), o = xr(e.owned_runs)[0] || {}, s = Vr(e), c = Hr(e.account_id || i.account_id || i.id || e.entity_id) || s, l = String(i.email || e.email || `账号 #${c}`), u = String(n.summary || n.message || e.result_label || e.summary_text || Ur(n) || "等待本轮结果"), d = String(r.summary || r.cause_summary || r.label || r.message || e.reason_label || e.reason_code || r.code || ""), f = [r.summary || r.cause_summary || r.message || e.error_message || d, r.display_code || r.code || e.reason_code].filter(Boolean).join("\n"), p = String(e.stage_label || e.current_stage_label || e.stage || "").trim(), m = Object.entries(Q(n.capabilities)).map(([e, t]) => `${Sr(e)}：${Rr(Q(t).state || Q(t).status)}`).join("\n"), h = e.state || e.outcome || e.status;
	return {
		id: s,
		accountId: c,
		account: l,
		summary: u,
		summaryShort: Gr(n, h, u),
		reason: d,
		reasonShort: d ? pe({
			...r,
			code: r.code || e.reason_code
		}) === "执行异常" && [...d].length <= 10 ? d : pe({
			...r,
			code: r.code || e.reason_code
		}) : "",
		reasonContent: f,
		stage: p,
		capabilities: m,
		state: Rr(h),
		stateKey: h,
		taskId: Hr(e.task_id || e.owned_task_id || a.task_id || o.task_id),
		runId: Hr(e.owned_run_id || e.run_id || a.run_id || o.run_id),
		blockerTaskId: Hr(e.blocker_task_id)
	};
}
function Gr(e, t, n) {
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
	let r = Rr(t);
	return [...r].length <= 10 && r !== "—" ? r : "结果见详情";
}
// src/features/bulk/useBulkDetail.ts
var Kr = [
	"failed",
	"partial_success",
	"not_executed",
	"cancelled"
];
function qr(e, t, n = e().view === "detail") {
	let r = y({ ...e() }), i = y(n), a = j(null), s = j(null), c = j(null), l = j([]), u = y(null), d = y(/* @__PURE__ */ new Set()), f = y([]), m = y(null), h = y(!1), g = y(!1), _ = y(!1), v = y(!1), b = y(!1), x = y(!1), S = y(""), C = y(""), w = y(""), T = y(""), E = j(null), D = !1, O = 0, A = !1, M, N = null, P = "", F = null, I = "", L = null, R = "", z = /* @__PURE__ */ new Map(), ee = () => `${r.value.batch_id || ""}:${r.value.round_id || ""}`, B = () => `${ee()}:${r.value.result_state || ""}`, V = () => `${B()}:${r.value.cursor || ""}`;
	function H(e) {
		let t = z.get(e);
		t?.controller.abort();
		let n = {
			generation: (t?.generation || 0) + 1,
			controller: new AbortController()
		};
		return z.set(e, n), n;
	}
	function U(e, t) {
		return !D && z.get(e) === t && !t.controller.signal.aborted;
	}
	function W(...e) {
		for (let t of e) z.get(t)?.controller.abort(), z.delete(t);
		e.includes("detail") && (N = null, P = ""), e.includes("targets") && (F = null, I = ""), e.includes("report") && (L = null, R = "");
	}
	function G() {
		let e = new URLSearchParams({ view: r.value.round_id ? "round" : "current" });
		return r.value.round_id && e.set("round_id", Z(r.value.round_id)), e;
	}
	function K(e = "") {
		return `/batches/${Z(r.value.batch_id)}${e}`;
	}
	function q(e) {
		return e instanceof Error ? e.message : String(e);
	}
	function te(e) {
		let t = new Map(l.value.map((e) => [Z(e.id), e]));
		if (Array.isArray(e)) for (let n of e) {
			let e = Q(n);
			t.set(Z(e.id), e);
		}
		l.value = [...t.values()].sort((e, t) => Number(t.round_no) - Number(e.round_no));
	}
	let J = k(() => Br(a.value?.summary || a.value?.counts)), Y = k(() => Q(a.value?.control)), X = k(() => Y.value.revision ?? a.value?.control_revision), ne = k(() => ["ended", "completed"].includes(String(Y.value.state || a.value?.control_state))), re = k(() => !!(Y.value.paused || a.value?.is_paused)), ie = k(() => f.value.length > 0), ae = k(() => s.value?.page?.has_more && s.value.page.next_cursor || null), oe = k(() => i.value && r.value.view === "detail" && (!ne.value || !!m.value || !!Y.value.pending)), se = k(() => Object.hasOwn(br, zr(a.value)));
	function ce(e) {
		return !a.value || x.value || E.value || ne.value || Y.value.pending ? !0 : e === "pause" ? re.value : e === "resume" ? !re.value : Q(a.value.capabilities || Q(a.value.operation).capabilities)[e] === !1;
	}
	function le(e = !1) {
		if (!i.value || r.value.view !== "detail") return Promise.resolve();
		let n = V();
		if (F && I === n) return e || (_.value = !0), F;
		let a = H("targets");
		_.value = !e || !s.value, e || (C.value = "");
		let o = (async () => {
			try {
				let e = G();
				e.set("page_size", "50"), r.value.cursor && e.set("cursor", r.value.cursor), r.value.result_state && e.set("state[]", r.value.result_state);
				let n = await t.api.request(`${K("/targets")}?${e}`, { signal: a.controller.signal });
				if (U("targets", a)) {
					C.value = "";
					for (let e of n.items) Vr(e);
					s.value = n;
				}
			} catch (e) {
				U("targets", a) && (C.value = q(e));
			} finally {
				U("targets", a) && (_.value = !1);
			}
		})();
		return F = o, I = n, o.finally(() => {
			F === o && (F = null, I = "");
		});
	}
	function ue(e = !1, n = !e && !!c.value) {
		if (!i.value || r.value.view !== "detail" || !h.value || !se.value) return Promise.resolve();
		let o = ee();
		if (L && R === o) return n || (v.value = !0), L;
		let s = ne.value || Q(a.value?.selected_round).state === "completed", l = s && c.value?.phase === "completed" && c.value.summary_revision === a.value?.summary_revision && M === X.value;
		if (!e && (l || !s && (c.value || w.value) && t.now() - O < 1e4)) return Promise.resolve();
		let u = H("report"), d = X.value, f = a.value?.summary_revision;
		v.value = !n || !c.value;
		let p = !1, m, g;
		return m = (async () => {
			try {
				let e = await t.api.request(`${K("/report")}?${G()}`, { signal: u.controller.signal });
				if (!U("report", u)) return;
				c.value = e, w.value = "", M = d, p = (ne.value || Q(a.value?.selected_round).state === "completed") && (f !== a.value?.summary_revision || d !== X.value);
			} catch (e) {
				U("report", u) && (w.value = q(e));
			} finally {
				U("report", u) && (v.value = !1, O = t.now());
			}
			p && (L === g && (L = null, R = ""), ue(!1, !0));
		})(), g = m.finally(() => {
			L === g && (L = null, R = "");
		}), L = g, R = o, g;
	}
	function de() {
		return !i.value || r.value.view !== "detail" || !se.value ? Promise.resolve() : (h.value = !0, ue(!!w.value));
	}
	function fe() {
		h.value = !1, W("report"), v.value = !1;
	}
	function pe(e = !1) {
		if (D || !i.value || r.value.view !== "detail" || !r.value.batch_id) return Promise.resolve();
		let t = e || !a.value;
		if (N && P === ee()) return t && (g.value = !0), N;
		P = ee();
		let n = me(e).finally(() => {
			N === n && (N = null, P = "");
		});
		return N = n, n;
	}
	async function me(e = !1) {
		if (D || !i.value || r.value.view !== "detail" || !r.value.batch_id) return;
		let n = e || !a.value, o = H("detail");
		g.value = n, e && (S.value = "");
		try {
			let n = await t.api.request(`${K()}?${G()}`, { signal: o.controller.signal });
			if (!U("detail", o)) return;
			S.value = "";
			let r = a.value?.summary_revision;
			if (a.value = n, te(n.rounds_head), n.selected_round && te([n.selected_round]), A || (u.value = typeof n.rounds_next_cursor == "string" ? n.rounds_next_cursor : null), m.value) {
				let e = l.value.find((e) => e.id === m.value);
				e && e.state !== "preparing" && (m.value = null, t.callbacks.notify(e.completion_reason === "cancelled_before_freeze" ? "重跑准备已取消，当前结果归属不变。" : "重跑名单已固定，可以切换查看新轮次。"));
			}
			ue(e, !e && !!c.value), (e || !s.value || r !== n.summary_revision) && await le(!e);
		} catch (e) {
			U("detail", o) && (S.value = q(e));
		} finally {
			U("detail", o) && (g.value = !1);
		}
	}
	async function he() {
		if (!i.value || r.value.view !== "detail" || !u.value || b.value) return;
		let e = H("rounds");
		b.value = !0;
		try {
			let n = new URLSearchParams({
				page_size: "20",
				cursor: u.value
			}), r = await t.api.request(`${K("/rounds")}?${n}`, { signal: e.controller.signal });
			U("rounds", e) && (te(r.items), u.value = r.page.has_more && r.page.next_cursor || null, A = !0);
		} catch (t) {
			U("rounds", e) && (T.value = q(t));
		} finally {
			U("rounds", e) && (b.value = !1);
		}
	}
	function ge(e, n = !1) {
		n || (f.value = []), r.value = {
			...r.value,
			...e
		}, t.callbacks.updateNavigation(e);
	}
	async function _e() {
		ae.value && !_.value && (f.value.push(r.value.cursor || ""), ge({ cursor: ae.value }, !0));
	}
	async function ve() {
		ie.value && !_.value && ge({ cursor: f.value.pop() || "" }, !0);
	}
	async function ye() {
		ge({ cursor: "" });
	}
	async function be(e) {
		ge({
			result_state: e,
			cursor: ""
		});
	}
	async function xe(e) {
		ge({
			round_id: e === "current" ? "" : Z(e),
			cursor: ""
		});
	}
	function Se(e, t) {
		let n = new Set(d.value);
		t ? n.add(Z(e)) : n.delete(e), d.value = n;
	}
	function Ce(e) {
		for (let t of s.value?.items || []) Se(Vr(t), e);
	}
	function we() {
		d.value = /* @__PURE__ */ new Set();
	}
	function Te(e) {
		return (e === "unsuccessful" ? Kr : [e]).reduce((e, t) => e + (J.value[t] || 0), 0);
	}
	function Ee() {
		E.value = null;
	}
	async function De(e) {
		if (!(x.value || D || !i.value || r.value.view !== "detail" || e.navigationKey !== V())) {
			x.value = !0, T.value = "", E.value = null;
			try {
				let n = await t.intents.submit(e.intentScope, e.path, e.body);
				if (t.callbacks.notify(e.kind === "retry" ? "重跑已受理，正在按固定时点的结果准备新轮次。" : "控制请求已受理，正在读取批次最新状态。"), D || e.navigationKey !== V()) return;
				e.kind === "retry" && (m.value = Z(n.round_id || n.id), we()), await pe(!0);
			} catch (t) {
				if (!D && e.navigationKey === V()) {
					T.value = q(t);
					let e = Q(t).code;
					["control_revision_conflict", "control_revision_changed"].includes(String(e)) && await pe(!0);
				}
			} finally {
				x.value = !1;
			}
		}
	}
	async function Oe() {
		let e = E.value;
		e && await De(e);
	}
	async function ke(e = !1, t = "failed") {
		if (!a.value || x.value || E.value || !Kr.includes(t) && t !== "unsuccessful") return;
		let n = [...d.value], i = e ? n.length : Te(t);
		if (!i) return;
		let o = Z(r.value.batch_id), s = r.value.round_id ? Z(r.value.round_id) : null, c = {
			title: "确认重跑",
			description: `将在当前批次下新建一轮，重跑 ${i} 个账号；不会覆盖历史轮次。`,
			label: `重跑 ${i} 个`,
			count: i,
			scopeLabel: s ? "当前轮" : "当前结果",
			path: `/batches/${o}/rounds`,
			intentScope: `retry:${o}`,
			navigationKey: V(),
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
					states: t === "unsuccessful" ? [...Kr] : [t]
				},
				retry_mode: "automatic"
			}
		};
		i >= 10 || t === "unsuccessful" ? E.value = c : await De(c);
	}
	async function Ae(e) {
		if (![
			"pause",
			"resume",
			"cancel_not_started",
			"request_stop"
		].includes(e) || ce(e)) return;
		let t = ["pause", "resume"].includes(e), n = e === "request_stop", i = Z(r.value.batch_id), o = r.value.round_id ? Z(r.value.round_id) : null, s = (n ? ["running", "waiting"] : [
			"pending_submit",
			"waiting_account",
			"queued",
			"waiting"
		]).reduce((e, t) => e + (J.value[t] || 0), 0), c = {
			title: n ? "停止正在执行" : "取消排队账号",
			description: n ? "已开始执行的账号会收到协作停止请求，正在收尾的步骤会完成，不会立即强制中断。" : "尚未开始的目标会取消；已开始账号链的必要步骤会继续收尾。",
			label: n ? "停止执行" : "取消排队",
			count: s,
			scopeLabel: !t && o ? "当前轮" : "整个批次",
			path: `/batches/${i}/control`,
			intentScope: `control:${i}:${e}`,
			navigationKey: V(),
			kind: "control",
			body: {
				action: e,
				expected_control_revision: Y.value.revision ?? a.value?.control_revision,
				scope: !t && o ? {
					kind: "round",
					round_id: o
				} : { kind: "batch" }
			}
		};
		t ? await De(c) : E.value = c;
	}
	function je(e) {
		if (!a.value) return;
		let n = Q(a.value.selection_summary).query || a.value.query_spec || Q(a.value.selection).query_spec;
		(e || n) && t.callbacks.copyBatch?.(n || {}, e ? {
			kind: "batch_targets",
			batch_id: Z(r.value.batch_id),
			selection: { kind: "all" }
		} : null, zr(a.value));
	}
	function Me(e) {
		i.value = e, e || (W("detail", "targets", "report", "rounds"), g.value = !1, _.value = !1, v.value = !1, b.value = !1, E.value = null);
	}
	return o(e, (e) => {
		JSON.stringify(e) !== JSON.stringify(r.value) && (f.value = [], r.value = { ...e });
	}, {
		deep: !0,
		flush: "sync"
	}), o(() => r.value.view, (e) => {
		e !== "detail" && (fe(), Me(!1));
	}, { flush: "sync" }), o(() => [
		ee(),
		B(),
		r.value.cursor || "",
		r.value.batch_id
	], (e, t) => {
		E.value = null, T.value = "", !t || e[0] !== t[0] ? (e[3] !== t?.[3] && (h.value = !1), W("detail", "targets", "report", "rounds"), a.value = null, s.value = null, c.value = null, l.value = [], u.value = null, A = !1, O = 0, M = void 0, S.value = "", w.value = "", C.value = "", g.value = !1, _.value = !1, v.value = !1, b.value = !1, we(), f.value = [], m.value = null, pe()) : (e[1] !== t[1] && (we(), f.value = []), s.value = null, le());
	}, {
		immediate: !0,
		flush: "sync"
	}), p(() => {
		D = !0, W("detail", "targets", "report", "rounds"), E.value = null;
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
		counts: J,
		ended: ne,
		paused: re,
		needsPolling: oe,
		hasReport: se,
		hasPrevious: ie,
		nextCursor: ae,
		controlDisabled: ce,
		refresh: pe,
		loadTargets: le,
		openReport: de,
		closeReport: fe,
		refreshReport: ue,
		moreRounds: he,
		next: _e,
		previous: ve,
		first: ye,
		setFilter: be,
		setRound: xe,
		toggleTarget: Se,
		selectPage: Ce,
		clearSelection: we,
		retryCount: Te,
		retry: ke,
		control: Ae,
		confirm: Oe,
		cancelConfirmation: Ee,
		copyBatch: je,
		setVisible: Me
	};
}
// src/features/bulk/BulkBusinessStats.vue?vue&type=script&setup=true&lang.ts
var Jr = {
	key: 0,
	class: "bulk-business-groups"
}, Yr = { class: "bulk-business-heading" }, Xr = { class: "bulk-business-metrics" }, Zr = {
	key: 1,
	class: "bulk-report-empty"
}, Qr = /* @__PURE__ */ n({
	__name: "BulkBusinessStats",
	props: {
		metrics: {},
		groups: {}
	},
	setup(e) {
		let t = e, n = k(() => t.groups ?? Nr(t.metrics));
		return (e, t) => n.value.length ? (i(), R("div", Jr, [(i(!0), R(_, null, c(n.value, (e) => (i(), R("section", {
			key: e.title,
			class: "bulk-business-group"
		}, [C("header", Yr, [C("h4", null, x(e.title), 1), C("span", null, x(e.title === "国家查询项" ? "项" : "账号数"), 1)]), C("dl", Xr, [(i(!0), R(_, null, c(e.items, (e) => (i(), R("div", { key: e.title }, [C("dt", null, x(e.title), 1), C("dd", null, x(F($)(e.value)), 1)]))), 128))])]))), 128))])) : (i(), R("p", Zr, "暂无已确认的功能统计。"));
	}
}), $r = ["aria-label"], ei = { role: "status" }, ti = {
	key: 1,
	class: "bulk-plan-report",
	"aria-labelledby": "bulkPlanReportTitle"
}, ni = { class: "bulk-report-header" }, ri = { class: "bulk-report-heading-line" }, ii = { id: "bulkPlanReportTitle" }, ai = { class: "bulk-report-updated" }, oi = {
	key: 0,
	class: "bulk-report-sync",
	role: "status"
}, si = { class: "bulk-report-outcomes" }, ci = { class: "bulk-report-outcome-note" }, li = { class: "bulk-report-execution" }, ui = { "aria-label": "账号执行耗时" }, di = { class: "bulk-report-section-head" }, fi = { class: "bulk-report-durations" }, pi = { class: "is-average" }, mi = { class: "bulk-report-note" }, hi = {
	key: 0,
	"aria-label": "AT 检查与自动刷新"
}, gi = { class: "bulk-report-at-causes" }, _i = { class: "bulk-report-at-results" }, vi = { class: "bulk-report-note" }, yi = {
	key: 1,
	"aria-label": "功能统计"
}, bi = {
	key: 1,
	class: "bulk-report-distributions"
}, xi = {
	class: "bulk-report-offers",
	"aria-label": "优惠结果"
}, Si = { class: "bulk-report-offer-totals" }, Ci = { class: "bulk-report-offer-list" }, wi = { class: "bulk-report-offer-line" }, Ti = {
	class: "bulk-report-rail",
	"aria-hidden": "true"
}, Ei = { class: "bulk-report-kind-list" }, Di = {
	key: 0,
	class: "bulk-report-empty"
}, Oi = {
	class: "bulk-report-plans",
	"aria-label": "当前订阅套餐"
}, ki = { class: "bulk-report-plan-list" }, Ai = {
	key: 0,
	class: "bulk-report-empty"
}, ji = {
	key: 2,
	class: "bulk-business-details"
}, Mi = /* @__PURE__ */ n({
	__name: "BulkReport",
	props: {
		report: {},
		formatDateTime: { type: Function }
	},
	setup(e) {
		let t = e, n = k(() => Object.hasOwn(br, String(t.report.operation_key))), r = k(() => Q(t.report.totals)), a = k(() => Q(t.report.duration)), o = k(() => Q(t.report.at_refresh)), s = k(() => Q(t.report.offers)), l = k(() => t.report.phase === "completed"), u = k(() => t.report.operation_key === "plan_check"), f = k(() => xr(t.report.plans).sort((e, t) => e.plan === "unknown" ? 1 : t.plan === "unknown" ? -1 : (Cr(t.accounts) || 0) - (Cr(e.accounts) || 0))), p = k(() => xr(s.value.by_plan).sort((e, t) => (Cr(t.accounts) || 0) - (Cr(e.accounts) || 0) || kr(e.plan).localeCompare(kr(t.plan)))), h = k(() => Math.max(0, ...f.value.map((e) => Cr(e.accounts) || 0))), g = k(() => Math.max(0, ...p.value.map((e) => Cr(e.accounts) || 0))), y = k(() => Nr(t.report.business_summary)), b = [
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
			"aria-label": F(Sr)(e.report.operation_key) + "报告"
		}, [C("h3", null, x(F(Sr)(e.report.operation_key)) + "报告", 1), C("p", ei, x(F(Tr)(e.report)) + " · " + x(e.report.phase === "preparing" ? "账号名单准备中，固定后生成报告。" : "该轮名单未固定，无法生成账号统计。"), 1)], 8, $r)) : n.value ? (i(), R("section", ti, [
			C("header", ni, [C("div", null, [C("div", ri, [C("h3", ii, x(F(Sr)(e.report.operation_key)) + x(l.value ? "完成报告" : "实时报告"), 1), C("span", { class: O(["bulk-report-phase", { "is-completed": l.value }]) }, x(l.value ? "已完成" : e.report.phase === "preparing" ? "名单准备中" : "统计更新中"), 3)]), C("p", null, x(F(Tr)(e.report)) + " · " + x(F($)(r.value.accounts)) + " 个账号", 1)]), C("span", ai, "更新于 " + x(e.formatDateTime(e.report.generated_at)), 1)]),
			F(Q)(e.report.projection).state && F(Q)(e.report.projection).state !== "current" ? (i(), R("p", oi, x(F(Q)(e.report.projection).state === "failed" ? "结果汇总暂时失败，以下统计尚未收齐，请稍后刷新。" : "执行结果正在汇总，以下统计尚未收齐。"), 1)) : m("", !0),
			C("dl", si, [(i(), R(_, null, c(b, ([e, t, n]) => C("div", {
				key: t,
				class: O(["bulk-report-metric", n])
			}, [C("dt", null, x(e), 1), C("dd", null, [z(x(F($)(r.value[t])), 1), E[0] ||= C("span", null, "个", -1)])], 2)), 64))]),
			C("div", ci, [
				C("span", null, "已结束 " + x(F($)(r.value.completed)) + " / " + x(F($)(r.value.accounts)) + " 个", 1),
				C("span", null, "未执行 " + x(F($)(r.value.not_executed)) + " 个", 1),
				C("span", null, "已取消 " + x(F($)(r.value.cancelled)) + " 个", 1)
			]),
			C("div", li, [C("section", ui, [
				C("div", di, [E[1] ||= C("h4", null, "账号执行耗时", -1), C("span", null, "已结束样本 " + x(F($)(a.value.sample_count)) + " 个", 1)]),
				C("dl", fi, [
					C("div", pi, [E[2] ||= C("dt", null, "平均耗时", -1), C("dd", null, x(F(wr)(a.value.avg_seconds)), 1)]),
					C("div", null, [E[3] ||= C("dt", null, "最快", -1), C("dd", null, x(F(wr)(a.value.min_seconds)), 1)]),
					C("div", null, [E[4] ||= C("dt", null, "最慢", -1), C("dd", null, x(F(wr)(a.value.max_seconds)), 1)])
				]),
				C("p", mi, [z(" 从账号开始执行到结束，" + x(u.value ? "含自动刷新及链内等待" : "含链内等待") + "，不含开始前排队。", 1), (F(Cr)(a.value.missing_count) || 0) > 0 ? (i(), R(_, { key: 0 }, [z(x(F($)(a.value.missing_count)) + " 个已结束账号缺少有效耗时，未计入均值。", 1)], 64)) : F(Cr)(a.value.sample_count) === 0 ? (i(), R(_, { key: 1 }, [z(" 暂无有效耗时样本。")], 64)) : m("", !0)])
			]), u.value ? (i(), R("section", hi, [
				E[8] ||= C("div", { class: "bulk-report-section-head" }, [C("h4", null, "AT 检查与自动刷新"), C("span", null, "按账号去重")], -1),
				C("dl", gi, [(i(), R(_, null, c(S, ([e, t]) => C("div", {
					key: t,
					class: "bulk-report-minor"
				}, [C("dt", null, x(e), 1), C("dd", null, [z(x(F($)(o.value[t])), 1), E[5] ||= C("span", null, "个", -1)])])), 64))]),
				C("dl", _i, [(i(), R(_, null, c(w, ([e, t, n]) => C("div", {
					key: t,
					class: O(["bulk-report-minor", n])
				}, [C("dt", null, x(e), 1), C("dd", null, [z(x(F($)(o.value[t])), 1), E[6] ||= C("span", null, "个", -1)])], 2)), 64))]),
				C("p", vi, [
					F(Cr)(o.value.not_needed_accounts) === null ? m("", !0) : (i(), R(_, { key: 0 }, [z("未触发刷新 " + x(F($)(o.value.not_needed_accounts)) + " 个 · ", 1)], 64)),
					z("刷新状态待确认 " + x(F($)(o.value.unknown_accounts)) + " 个", 1),
					F(Cr)(o.value.not_executed_accounts) === null ? m("", !0) : (i(), R(_, { key: 1 }, [z(" · 未开始执行 " + x(F($)(o.value.not_executed_accounts)) + " 个", 1)], 64)),
					E[7] ||= z("。待确认含执行中尚无结果及历史证据缺失；触发原因可能重叠，远端拒绝不等于本地过期。 ", -1)
				])
			])) : (i(), R("section", yi, [E[9] ||= C("div", { class: "bulk-report-section-head" }, [C("h4", null, "功能统计"), C("span", null, "当前查看范围")], -1), d(Qr, { groups: y.value }, null, 8, ["groups"])]))]),
			u.value ? (i(), R("div", bi, [C("section", xi, [
				E[13] ||= C("div", { class: "bulk-report-section-head" }, [C("div", null, [C("h4", null, "优惠结果"), C("p", null, "统计本次查到的可用优惠，按账号去重")])], -1),
				C("dl", Si, [(i(), R(_, null, c(T, ([e, t, n]) => C("div", {
					key: t,
					class: O(["bulk-report-metric", { "is-accent": t === "with_offer_accounts" }])
				}, [
					C("dt", null, x(e), 1),
					C("dd", null, [z(x(F($)(s.value[t])), 1), E[10] ||= C("span", null, "个", -1)]),
					C("small", null, x(n), 1)
				], 2)), 64))]),
				C("div", Ci, [(i(!0), R(_, null, c(p.value, (e) => (i(), R("div", {
					key: String(e.plan),
					class: "bulk-report-offer-row"
				}, [
					C("div", wi, [C("strong", null, x(F(kr)(e.plan)), 1), C("span", null, [C("b", null, x(F($)(e.accounts)), 1), E[11] ||= z(" 个账号", -1)])]),
					C("span", Ti, [C("span", { style: v({ width: F(jr)(e.accounts, g.value) }) }, null, 4)]),
					C("dl", Ei, [(i(!0), R(_, null, c(F(xr)(e.kinds), (e) => (i(), R("div", { key: String(e.kind) }, [C("dt", null, x(F(Ar)(e.kind)), 1), C("dd", null, [z(x(F($)(e.accounts)), 1), E[12] ||= C("span", null, "个", -1)])]))), 128))])
				]))), 128)), p.value.length ? m("", !0) : (i(), R("p", Di, x(F(Cr)(s.value.with_offer_accounts) === 0 ? "本次尚未查到可用优惠。" : "暂无优惠套餐明细。"), 1))]),
				E[14] ||= C("p", { class: "bulk-report-note" }, "同一账号可符合多个套餐或优惠，分项数量可能重叠。", -1)
			]), C("section", Oi, [
				E[16] ||= C("div", { class: "bulk-report-section-head" }, [C("div", null, [C("h4", null, "当前订阅套餐"), C("p", null, "本次查询确认的套餐状态")])], -1),
				C("dl", ki, [(i(!0), R(_, null, c(f.value, (e) => (i(), R("div", {
					key: String(e.plan),
					class: O({ "is-unknown": e.plan === "unknown" })
				}, [C("dt", null, x(F(kr)(e.plan)), 1), C("dd", null, [C("span", null, [z(x(F($)(e.accounts)), 1), E[15] ||= C("small", null, "个", -1)]), C("span", {
					class: O(["bulk-report-rail", { "is-muted": e.plan === "unknown" }]),
					"aria-hidden": "true"
				}, [C("span", { style: v({ width: F(jr)(e.accounts, h.value) }) }, null, 4)], 2)])], 2))), 128)), f.value.length ? m("", !0) : (i(), R("div", Ai, "暂无套餐结果。"))]),
				E[17] ||= C("p", { class: "bulk-report-note" }, "“尚未确认”包含待完成、失败或缺少套餐记录的账号。", -1)
			])])) : m("", !0),
			u.value && y.value.length ? (i(), R("details", ji, [E[18] ||= C("summary", null, [z("更多查询统计"), C("span", null, "展开查看")], -1), d(Qr, { groups: y.value }, null, 8, ["groups"])])) : m("", !0)
		])) : m("", !0);
	}
}), Ni = ["aria-label"], Pi = {
	key: 0,
	role: "status"
}, Fi = {
	key: 2,
	class: "bulk-report-load-error"
}, Ii = {
	class: "bulk-error",
	role: "alert"
}, Li = ["disabled"], Ri = /* @__PURE__ */ n({
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
		let t = e, n = k(() => Object.hasOwn(br, t.operationKey)), r = k(() => `${br[t.operationKey]}报告`);
		return (t, a) => n.value ? (i(), R(_, { key: 0 }, [e.report && e.report.operation_key === e.operationKey ? (i(), S(Mi, {
			key: 0,
			report: e.report,
			"format-date-time": e.formatDateTime
		}, null, 8, ["report", "format-date-time"])) : (i(), R("section", {
			key: 1,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": r.value
		}, [C("h3", null, x(r.value), 1), e.error ? m("", !0) : (i(), R("p", Pi, "正在汇总本次执行结果…"))], 8, Ni)), e.error ? (i(), R("div", Fi, [C("p", Ii, x(e.error), 1), C("button", {
			type: "button",
			class: "jobs-tb-btn",
			"data-bulk-action": "report-refresh",
			disabled: e.loading,
			onClick: a[0] ||= D((t) => e.onRetry(), ["stop"])
		}, " 重新读取报告 ", 8, Li)])) : m("", !0)], 64)) : m("", !0);
	}
}), zi = ["aria-busy"], Bi = {
	key: 0,
	class: "ui-list-feedback is-error bulk-error",
	role: "alert"
}, Vi = {
	class: "ui-table-scroll bulk-target-scroll",
	role: "region",
	"aria-label": "账号明细内容",
	tabindex: "0"
}, Hi = { class: "ui-table ui-table--sticky-end bulk-table bulk-target-table" }, Ui = { class: "ui-col-check" }, Wi = [
	"disabled",
	"checked",
	"indeterminate"
], Gi = { class: "bulk-target-filter" }, Ki = ["checked"], qi = [
	"value",
	"checked",
	"onChange"
], Ji = ["data-bulk-row-target"], Yi = {
	class: "ui-col-check bulk-target-check",
	"data-label": "选择"
}, Xi = [
	"data-bulk-target",
	"aria-label",
	"checked",
	"onChange"
], Zi = {
	class: "bulk-target-id",
	"data-label": "ID"
}, Qi = ["aria-label", "onClick"], $i = {
	class: "bulk-target-account",
	"data-label": "账号"
}, ea = ["title", "onClick"], ta = {
	class: "bulk-target-state",
	"data-label": "结果 / 阶段"
}, na = { class: "bulk-target-status-line" }, ra = ["onClick"], ia = {
	class: "bulk-target-summary",
	"data-label": "结果摘要"
}, aa = [
	"title",
	"aria-label",
	"onClick"
], oa = {
	class: "bulk-target-reason",
	"data-label": "错误分类"
}, sa = ["title", "onClick"], ca = {
	class: "bulk-target-actions",
	"data-label": "操作"
}, la = { class: "bulk-target-action-line" }, ua = ["onClick"], da = { key: 1 }, fa = ["onClick"], pa = {
	key: 0,
	class: "bulk-vue-result-details"
}, ma = /* @__PURE__ */ n({
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
		let r = e, s = n, u = y(null), f = j(r.items), p = k(() => f.value.map(Wr)), h = k(() => p.value.filter((e) => r.selected.has(e.id)).length), g = y(!1), v = k(() => [.../* @__PURE__ */ new Set([...r.resultStates, ...r.resultState ? [r.resultState] : []])]);
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
		function ee(e, t = null) {
			r.openTask(e, t);
		}
		return t({ close: I }), (t, n) => (i(), R(_, null, [C("div", {
			ref_key: "host",
			ref: u,
			class: "bulk-targets",
			"aria-busy": e.loading
		}, [e.error ? (i(), R("div", Bi, [z(x(e.error) + " ", 1), C("button", {
			type: "button",
			class: "ui-link",
			onClick: n[0] ||= (e) => s("retry")
		}, "重试读取明细")])) : m("", !0), C("div", Vi, [C("table", Hi, [C("thead", null, [C("tr", null, [
			C("th", Ui, [C("input", {
				type: "checkbox",
				"data-select-page": "",
				"aria-label": "选择当前页目标",
				disabled: !p.value.length,
				checked: p.value.length > 0 && h.value === p.value.length,
				indeterminate: h.value > 0 && h.value < p.value.length,
				onChange: n[1] ||= (e) => s("selectPage", L(e))
			}, null, 40, Wi)]),
			n[8] ||= C("th", null, "ID", -1),
			n[9] ||= C("th", null, "账号", -1),
			C("th", null, [e.resultStates.length ? (i(), S(K, {
				key: 0,
				label: "结果状态",
				"trigger-label": "结果 / 阶段",
				active: !!e.resultState,
				summary: F(Rr)(e.resultState),
				open: g.value,
				"onUpdate:open": n[3] ||= (e) => g.value = e
			}, {
				default: a(() => [C("fieldset", Gi, [
					n[7] ||= C("legend", { class: "ui-sr-only" }, "结果状态", -1),
					C("label", null, [
						C("input", {
							type: "radio",
							name: "bulk-target-state",
							value: "",
							checked: !e.resultState,
							onChange: n[2] ||= (e) => b("")
						}, null, 40, Ki),
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
						}, null, 40, qi),
						C("span", null, x(F(Rr)(t)), 1),
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
			C("td", Yi, [C("input", {
				type: "checkbox",
				"data-bulk-target": t.id,
				"aria-label": "选择账号 " + t.account,
				checked: e.selected.has(t.id),
				onChange: (e) => s("toggle", t.id, L(e))
			}, null, 40, Xi)]),
			C("td", Zi, [C("button", {
				type: "button",
				class: "bulk-cell-detail",
				"aria-label": "查看完整账号 ID：" + t.accountId,
				onClick: (e) => N(t, e)
			}, "#" + x(t.accountId), 9, Qi)]),
			C("td", $i, [C("button", {
				type: "button",
				class: "bulk-cell-detail",
				title: t.account,
				onClick: (e) => N(t, e)
			}, x(t.account), 9, ea)]),
			C("td", ta, [C("div", na, [C("span", { class: O(["ui-badge bulk-badge", `ui-badge--${F(Lr)(t.stateKey)}`]) }, x(t.state), 3), t.stage && !["—", "-"].includes(t.stage) ? (i(), R("button", {
				key: 0,
				type: "button",
				class: "bulk-cell-detail bulk-target-stage",
				onClick: (e) => N(t, e)
			}, x(t.stage), 9, ra)) : m("", !0)])]),
			C("td", ia, [d(X, {
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
				}, x(t.summaryShort), 9, aa)]),
				_: 2
			}, 1032, ["text", "title"])]),
			C("td", oa, [t.reason ? (i(), S(X, {
				key: 0,
				text: t.reasonShort,
				title: t.reason
			}, {
				default: a(() => [C("button", {
					type: "button",
					class: "bulk-cell-detail",
					title: t.reason,
					onClick: (e) => N(t, e)
				}, x(t.reasonShort), 9, sa)]),
				_: 2
			}, 1032, ["text", "title"])) : (i(), R(_, { key: 1 }, [z("—")], 64))]),
			C("td", ca, [C("div", la, [t.taskId ? (i(), R("button", {
				key: 0,
				type: "button",
				class: "ui-link",
				"data-owned-task": "",
				onClick: (e) => ee(t.taskId, t.runId)
			}, "查看执行", 8, ua)) : (i(), R("span", da, "尚未创建执行")), t.blockerTaskId ? (i(), R("button", {
				key: 2,
				type: "button",
				class: "ui-link",
				"data-blocker-task": "",
				title: "查看占用任务（其他执行）",
				onClick: (e) => ee(t.blockerTaskId)
			}, "查看占用", 8, fa)) : m("", !0)])])
		], 8, Ji))), 128)), p.value.length ? m("", !0) : (i(), S(J, {
			key: 0,
			colspan: 7,
			loading: e.loading,
			"loading-title": "正在读取账号明细…",
			title: "当前条件下没有目标",
			text: "更改结果筛选不会改变本批固定名单。"
		}, null, 8, ["loading"]))])])])], 8, zi), d(F(_e), {
			open: D.value,
			"onUpdate:open": n[5] ||= (e) => D.value = e
		}, {
			default: a(() => [d(F(Ae), null, {
				default: a(() => [d(F(ke), { class: "bulk-vue-overlay" }), d(F(Ee), {
					class: "bulk-vue-dialog",
					onEscapeKeyDown: n[4] ||= (e) => {
						e.preventDefault(), I();
					},
					onCloseAutoFocus: P
				}, {
					default: a(() => [
						d(F(je), null, {
							default: a(() => [...n[13] ||= [z("账号执行详情", -1)]]),
							_: 1
						}),
						d(F(De), null, {
							default: a(() => [z(x(A.value?.account) + " · 账号 #" + x(A.value?.accountId), 1)]),
							_: 1
						}),
						A.value ? (i(), R("dl", pa, [
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
						d(F(ve), {
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
}), ha = ["aria-busy"], ga = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, _a = {
	key: 1,
	class: "bulk-card bulk-overview"
}, va = { class: "bulk-detail-toolbar" }, ya = { class: "bulk-detail-meta" }, ba = { class: "bulk-settings bulk-detail-settings" }, xa = {
	key: 0,
	class: "bulk-projection-note"
}, Sa = { class: "bulk-actions" }, Ca = { class: "bulk-round-picker" }, wa = ["value"], Ta = ["value"], Ea = ["value"], Da = ["disabled"], Oa = ["disabled"], ka = { class: "bulk-control-strip" }, Aa = { class: "bulk-control-copy" }, ja = { class: "bulk-view-note" }, Ma = { key: 0 }, Na = { key: 1 }, Pa = { key: 2 }, Fa = { key: 3 }, Ia = {
	key: 0,
	class: "bulk-view-note"
}, La = {
	class: "bulk-actions",
	role: "group",
	"aria-label": "运行控制"
}, Ra = [
	"data-bulk-action",
	"disabled",
	"onClick"
], za = { class: "bulk-summary-grid" }, Ba = { class: "bulk-summary-item" }, Va = { class: "bulk-summary-item" }, Ha = { class: "bulk-summary-item is-success" }, Ua = { class: "bulk-summary-item is-warning" }, Wa = { class: "bulk-card bulk-results-card" }, Ga = { class: "bulk-results-heading" }, Ka = ["disabled"], qa = { class: "bulk-retry-toolbar" }, Ja = ["value"], Ya = ["disabled"], Xa = ["disabled"], Za = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, Qa = {
	key: 1,
	class: "bulk-notice",
	role: "status"
}, $a = {
	class: "bulk-target-count-row",
	"data-bulk-target-count-row": ""
}, eo = {
	class: "bulk-target-count",
	role: "status"
}, to = { class: "bulk-report-dialog-heading" }, no = { id: "bulkReportDialogTitle" }, ro = { id: "bulkReportDialogDescription" }, io = { class: "bulk-actions" }, ao = ["disabled"], oo = ["aria-busy"], so = { class: "bulk-vue-dialog-actions" }, co = /*#__PURE__*/ I(/* @__PURE__ */ n({
	__name: "BulkDetail",
	props: {
		navigation: {},
		deps: {},
		visible: {
			type: Boolean,
			default: void 0
		}
	},
	emits: ["reportClose"],
	setup(e, { expose: n, emit: r }) {
		let l = e, u = r, f = qr(() => l.navigation, l.deps, l.visible ?? l.navigation.view === "detail"), { navigation: p, detail: g, targets: v, report: w, reportOpen: T, rounds: E, roundsCursor: A, selected: j, pendingRound: M, loading: N, targetsLoading: P, reportLoading: I, roundsLoading: L, writing: ee, error: B, targetError: V, reportError: H, actionError: U, confirmation: W, counts: G, ended: K, paused: q, hasReport: te, hasPrevious: J, nextCursor: Y } = f, X = k(() => g.value?.name || g.value?.title || "批次详情"), re = y(null), ie = y(), ae = y("failed"), oe = y(l.visible ?? l.navigation.view === "detail"), se = k(() => T.value && oe.value && p.value.view === "detail");
		me(ie, () => se.value, () => oe.value && p.value.view === "detail");
		let ce = k(() => [
			"success",
			"partial_success",
			"failed",
			"not_executed",
			"cancelled"
		].reduce((e, t) => e + (G.value[t] || 0), 0)), le = k(() => [
			"pending_submit",
			"waiting_account",
			"queued",
			"running",
			"waiting"
		].reduce((e, t) => e + (G.value[t] || 0), 0)), ue = k(() => E.value.find((e) => e.id === p.value.round_id)), de = k(() => !!(Q(g.value?.selection_summary).query || g.value?.query_spec || Q(g.value?.selection).query_spec)), fe = [
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
		], pe = k(() => p.value.result_state ? [{
			key: "result_state",
			label: `结果状态：${Rr(p.value.result_state)}`,
			title: `结果状态：${Rr(p.value.result_state)}`,
			removeLabel: "清除结果状态筛选"
		}] : []), he = [
			["failed", "失败"],
			["partial_success", "部分成功"],
			["not_executed", "未执行"],
			["cancelled", "已取消"],
			["unsuccessful", "全部未成功"]
		], ge = [
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
		], _e = null;
		function ve(e) {
			_e = e.currentTarget;
		}
		async function ye(e, t) {
			ve(t), await f.retry(e, ae.value);
		}
		async function be(e, t) {
			ve(t), await f.control(e);
		}
		function xe(e) {
			e.preventDefault();
			let n = _e;
			_e = null, t(() => {
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
		function Se() {
			return f.openReport();
		}
		async function Ce() {
			f.closeReport(), await t(), u("reportClose");
		}
		function we(e) {
			let t = ie.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && Ce();
		}
		function Te(e) {
			oe.value = e, f.setVisible(e), e || (re.value?.close(), _e = null);
		}
		return o(() => l.visible, (e) => {
			e !== void 0 && Te(e);
		}, { flush: "sync" }), o(() => [
			p.value.batch_id,
			p.value.round_id,
			p.value.result_state,
			p.value.view
		], () => {
			re.value?.close(), _e = null;
		}), n({
			batchName: X,
			error: B,
			refresh: f.refresh,
			showReport: Se,
			setVisible: Te,
			needsRefresh: f.needsPolling
		}), (t, n) => (i(), R("div", {
			class: "bulk-detail-owner",
			"aria-busy": F(N)
		}, [
			F(B) ? (i(), R("p", ga, [z(x(F(B)) + " ", 1), C("button", {
				type: "button",
				class: "bulk-link",
				onClick: n[0] ||= (e) => F(f).refresh(!0)
			}, "重试读取批次")])) : m("", !0),
			F(g) ? (i(), R("section", _a, [
				C("div", va, [C("div", ya, [
					C("span", { class: O(["ui-badge bulk-badge", `ui-badge--${F(Lr)(F(q) ? "paused" : F(Q)(F(g).control).state || F(g).control_state || F(g).state)}`]) }, x(F(Rr)(F(q) ? "paused" : F(Q)(F(g).control).state || F(g).control_state || F(g).state)), 3),
					C("span", null, x(F(Sr)(F(zr)(F(g)))), 1),
					C("span", null, "创建于 " + x(e.deps.callbacks.formatDateTime(F(g).created_at)), 1),
					C("details", ba, [n[17] ||= C("summary", null, "范围与设置", -1), C("dl", null, [
						n[14] ||= C("dt", null, "名单生成", -1),
						C("dd", null, x(e.deps.callbacks.formatDateTime(F(Q)(F(g).selection_summary).selection_at || F(g).selection_at)), 1),
						n[15] ||= C("dt", null, "配置版本", -1),
						C("dd", null, x(F(Q)(F(g).effective_settings).config_revision || F(g).config_revision || "—"), 1),
						n[16] ||= C("dt", null, "结果更新", -1),
						C("dd", null, x(e.deps.callbacks.formatDateTime(F(g).projected_at)), 1)
					])]),
					F(Q)(F(g).projection).state && F(Q)(F(g).projection).state !== "current" ? (i(), R("span", xa, "汇总同步中")) : m("", !0)
				]), C("div", Sa, [
					C("label", Ca, [n[19] ||= C("span", { class: "bulk-sr-only" }, "结果视图", -1), C("select", {
						value: F(p).round_id || "current",
						"aria-label": "结果视图",
						onChange: n[1] ||= (e) => F(f).setRound(e.target.value)
					}, [
						n[18] ||= C("option", { value: "current" }, "当前结果", -1),
						(i(!0), R(_, null, c(F(E), (e) => (i(), R("option", {
							key: String(e.id),
							value: String(e.id)
						}, x(Number(e.round_no) === 1 ? "首轮" : "重跑 " + (Number(e.round_no) - 1)) + " · " + x(F(Rr)(e.state)) + " · " + x(e.target_count == null ? "准备中" : F($)(e.target_count) + " 个"), 9, Ta))), 128)),
						F(p).round_id && !ue.value ? (i(), R("option", {
							key: 0,
							value: F(p).round_id
						}, "所选轮次 #" + x(F(p).round_id), 9, Ea)) : m("", !0)
					], 40, wa)]),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "more-rounds",
						disabled: !F(A) || F(L),
						onClick: n[2] ||= (...e) => F(f).moreRounds && F(f).moreRounds(...e)
					}, "更多轮次", 8, Da),
					F(te) ? (i(), R("button", {
						key: 0,
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "view-report",
						onClick: Se
					}, "查看报告")) : m("", !0),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "copy-targets",
						onClick: n[3] ||= (e) => F(f).copyBatch(!0)
					}, "同一名单再次执行"),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "copy-query",
						disabled: !de.value,
						onClick: n[4] ||= (e) => F(f).copyBatch(!1)
					}, "复制条件新建", 8, Oa)
				])]),
				C("div", ka, [C("div", Aa, [C("p", ja, [
					C("strong", null, "已结束 " + x(F($)(ce.value)) + " / " + x(F($)(F(g).target_count)) + " 个", 1),
					!F(K) && !F(q) ? (i(), R("span", Ma, x(F($)(le.value)) + " 个进行中", 1)) : m("", !0),
					ue.value?.completion_reason === "cancelled_before_freeze" ? (i(), R("span", Na, "本轮在名单生成前取消，当前结果未改变。")) : F(p).round_id ? (i(), R("span", Pa, "仅展示该轮名单及执行结果。")) : (i(), R("span", Fa, "每个账号保留最近一轮结果"))
				]), F(q) && !F(K) ? (i(), R("p", Ia, "未开始的账号等待继续，已开始的账号继续收尾。")) : m("", !0)]), C("div", La, [(i(), R(_, null, c(ge, ([e, t, n]) => C("button", {
					key: e,
					type: "button",
					class: O(["jobs-tb-btn", { "jobs-tb-btn--danger": ["cancel", "stop"].includes(n) }]),
					"data-bulk-action": n,
					disabled: F(f).controlDisabled(e),
					onClick: (t) => be(e, t)
				}, x(t), 11, Ra)), 64))])]),
				C("div", za, [
					C("div", Ba, [n[20] ||= C("span", null, "账号总数", -1), C("strong", null, x(F($)(F(g).target_count)), 1)]),
					C("div", Va, [n[21] ||= C("span", null, "进行中", -1), C("strong", null, x(le.value), 1)]),
					C("div", Ha, [n[22] ||= C("span", null, "成功", -1), C("strong", null, x(F(G).success || 0), 1)]),
					C("div", Ua, [n[23] ||= C("span", null, "未成功", -1), C("strong", null, x(F(f).retryCount("unsuccessful")), 1)])
				]),
				d(Qr, { metrics: F(g).business_summary || F(g).metrics }, null, 8, ["metrics"])
			])) : m("", !0),
			C("section", Wa, [
				C("div", Ga, [C("h3", null, [
					n[24] ||= z("账号明细 ", -1),
					C("span", null, x(F(j).size ? "已选 " + F(j).size + " 个（可跨页）" : ""), 1),
					C("button", {
						type: "button",
						class: "bulk-link",
						disabled: !F(j).size,
						onClick: n[5] ||= (...e) => F(f).clearSelection && F(f).clearSelection(...e)
					}, "清空选择", 8, Ka)
				]), C("div", qa, [
					s(C("select", {
						"onUpdate:modelValue": n[6] ||= (e) => ae.value = e,
						"aria-label": "重跑范围"
					}, [(i(), R(_, null, c(he, ([e, t]) => C("option", {
						key: e,
						value: e
					}, x(t), 9, Ja)), 64))], 512), [[h, ae.value]]),
					C("button", {
						type: "button",
						class: "jobs-tb-btn jobs-tb-btn--primary",
						"data-bulk-action": "retry",
						disabled: F(ee) || !!F(W) || !F(f).retryCount(ae.value),
						onClick: n[7] ||= (e) => ye(!1, e)
					}, "重跑" + x(he.find((e) => e[0] === ae.value)?.[1]) + " (" + x(F(f).retryCount(ae.value)) + ")", 9, Ya),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "retry-selected",
						disabled: F(ee) || !!F(W) || !F(j).size,
						onClick: n[8] ||= (e) => ye(!0, e)
					}, "重跑勾选" + x(F(j).size ? " (" + F(j).size + ")" : ""), 9, Xa)
				])]),
				F(U) ? (i(), R("p", Za, x(F(U)), 1)) : m("", !0),
				F(M) ? (i(), R("p", Qa, "重跑已受理，正在准备新轮次 #" + x(F(M)) + "。", 1)) : m("", !0),
				C("div", $a, [C("span", eo, "共 " + x(F($)(F(g)?.target_count)) + " 个账号 · 当前页 " + x(F(v)?.items.length || 0) + " 个", 1), d(ne, {
					items: pe.value,
					onRemove: n[9] ||= (e) => F(f).setFilter("")
				}, null, 8, ["items"])]),
				d(ma, {
					ref_key: "targetTable",
					ref: re,
					scope: [
						F(p).batch_id,
						F(p).round_id,
						F(p).result_state,
						F(p).cursor
					].join(":"),
					items: F(v)?.items || [],
					selected: F(j),
					loading: F(P) || F(N) && !F(g),
					error: F(V),
					"result-state": F(p).result_state || "",
					"result-counts": F(G),
					"result-total": F(g)?.target_count,
					"result-states": fe,
					"open-task": e.deps.callbacks.openTask,
					onFilter: F(f).setFilter,
					onToggle: F(f).toggleTarget,
					onSelectPage: F(f).selectPage,
					onRetry: F(f).loadTargets
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
				d(Je, {
					"has-previous": F(J),
					"next-cursor": F(Y),
					"item-count": F(v)?.items.length || 0,
					"has-cursor": !!F(p).cursor,
					busy: F(P),
					label: "账号明细分页",
					onNext: F(f).next,
					onPrevious: F(f).previous,
					onFirst: F(f).first
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
			(i(), S(b, { to: "body" }, [C("dialog", {
				ref_key: "reportDialog",
				ref: ie,
				class: "bulk-page bulk-report-dialog",
				"data-bulk-report-dialog": "",
				"aria-labelledby": "bulkReportDialogTitle",
				"aria-describedby": "bulkReportDialogDescription",
				onCancel: D(Ce, ["prevent"]),
				onClick: we
			}, [C("header", to, [C("div", null, [C("h2", no, x(F(Sr)(F(zr)(F(g)))) + "报告", 1), C("p", ro, x(X.value) + " · 批次 #" + x(F(p).batch_id) + " · " + x(F(p).round_id ? "所选轮次" : "当前结果"), 1)]), C("div", io, [C("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-report-close": "",
				"aria-label": "关闭批次报告",
				onClick: Ce
			}, [...n[25] ||= [z("关闭 ", -1), C("span", { "aria-hidden": "true" }, "×", -1)]]), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: F(I),
				"data-bulk-action": "report-refresh",
				onClick: n[10] ||= (e) => F(f).refreshReport(!0)
			}, "刷新报告", 8, ao)])]), F(T) ? (i(), R("section", {
				key: 0,
				"data-bulk-plan-report": "",
				class: "bulk-report-dialog-body",
				role: "region",
				"aria-label": "批次报告",
				"aria-busy": F(I)
			}, [d(Ri, {
				"operation-key": F(zr)(F(g)),
				report: F(w),
				error: F(H) ? "读取报告失败：" + F(H) : "",
				"format-date-time": e.deps.callbacks.formatDateTime,
				"on-retry": () => F(f).refreshReport(!0),
				loading: F(I)
			}, null, 8, [
				"operation-key",
				"report",
				"error",
				"format-date-time",
				"on-retry",
				"loading"
			])], 8, oo)) : m("", !0)], 544)])),
			d(F(ze), {
				open: !!F(W),
				"onUpdate:open": n[13] ||= (e) => {
					e || F(f).cancelConfirmation();
				}
			}, {
				default: a(() => [d(F(Re), null, {
					default: a(() => [d(F(Le), { class: "bulk-vue-overlay" }), d(F(Pe), {
						class: "bulk-vue-dialog",
						onEscapeKeyDown: n[12] ||= (e) => {
							e.preventDefault(), F(f).cancelConfirmation();
						},
						onCloseAutoFocus: xe
					}, {
						default: a(() => [
							d(F(Be), null, {
								default: a(() => [z(x(F(W)?.title), 1)]),
								_: 1
							}),
							d(F(Ie), null, {
								default: a(() => [z(x(F(W)?.description), 1)]),
								_: 1
							}),
							C("p", null, "范围：" + x(F(W)?.scopeLabel) + " · 预计账号：" + x(F(W)?.count) + " 个", 1),
							C("div", so, [d(F(Fe), {
								class: "jobs-tb-btn",
								"data-confirm-cancel": "",
								onClick: F(f).cancelConfirmation
							}, {
								default: a(() => [...n[26] ||= [z("返回", -1)]]),
								_: 1
							}, 8, ["onClick"]), C("button", {
								type: "button",
								class: "jobs-tb-btn jobs-tb-btn--danger",
								"data-confirm-submit": "",
								onClick: n[11] ||= (...e) => F(f).confirm && F(f).confirm(...e)
							}, x(F(W)?.label), 1)])
						]),
						_: 1
					})]),
					_: 1
				})]),
				_: 1
			}, 8, ["open"])
		], 8, ha));
	}
}), [["__scopeId", "data-v-02ab2b48"]]), lo = [
	"batch_id",
	"round_id",
	"result_state",
	"cursor",
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
], uo = /* @__PURE__ */ new Set([
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
]);
function fo(e = {}) {
	let t = [
		"list",
		"create",
		"detail"
	].includes(e.view || "") ? e.view : "list", n = {
		tab: "bulk",
		view: t
	};
	for (let t of lo) typeof e[t] == "string" && e[t] && (n[t] = e[t]);
	if (t === "detail") {
		if (!/^[1-9]\d*$/.test(n.batch_id || "")) return {
			tab: "bulk",
			view: "list"
		};
		(n.q || e.reason_code) && (delete n.q, delete n.cursor), n.result_state && uo.has(n.result_state) && (n.result_state = "failed");
	}
	return n;
}
// src/features/bulk/BulkPageShell.vue?vue&type=script&setup=true&lang.ts
var po = ["data-bulk-view"], mo = { class: "bulk-page-heading" }, ho = { "data-bulk-title": "" }, go = {
	key: 0,
	class: "bulk-heading-id"
}, _o = { class: "bulk-actions" }, vo = ["aria-current"], yo = {
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
}, So = ["disabled"], Co = { "data-bulk-content": "" }, wo = /*#__PURE__*/ I(/* @__PURE__ */ n({
	__name: "BulkPageShell",
	props: {
		deps: {},
		initialNavigation: {}
	},
	setup(e, { expose: n }) {
		let r = e, a = j(fo(r.initialNavigation)), c = j(null), u = k(() => c.value ?? a.value), f = j(a.value.view === "list" ? { ...a.value } : {
			tab: "bulk",
			view: "list"
		}), p = y(!1), h = y(!1), g = y(""), _ = y(""), v = y(!1), b = y(0), S = j(null), w = y(null), E = y(null), D = y(null), A = !1, M = 0, N = 0, F = !1, I, L = null, ee = "", B = k(() => p.value && h.value), V = {
			...r.deps.callbacks,
			navigate: (e, t, n) => {
				se(e, t, n);
			},
			updateNavigation: (e) => {
				ue(e);
			},
			notify: (e) => {
				_.value = e, b.value++, r.deps.callbacks.notify(e);
			},
			copyBatch: (e, t, n) => {
				de(e, t, n);
			}
		}, H = {
			pending: () => r.deps.intents.pending(),
			submit: async (e, t, n) => {
				try {
					return await r.deps.intents.submit(e, t, n);
				} finally {
					b.value++;
				}
			},
			recover: async (e) => {
				try {
					return await r.deps.intents.recover(e);
				} finally {
					b.value++;
				}
			}
		}, U = {
			api: r.deps.api,
			callbacks: V
		}, W = {
			...r.deps,
			intents: H,
			callbacks: V
		}, G = {
			api: r.deps.api,
			intents: H,
			callbacks: V,
			now: r.deps.now
		}, K = k(() => {
			b.value;
			try {
				return r.deps.intents.pending();
			} catch {
				return [];
			}
		}), q = k(() => B.value ? c.value && D.value?.needsRefresh ? 2e3 : a.value.view === "list" ? 7e3 : a.value.view === "create" ? E.value?.needsRefresh ? 2e3 : 0 : D.value?.needsRefresh ? 2e3 : 0 : 0), te = k(() => a.value.view === "detail" ? D.value?.batchName || "批次详情" : a.value.view === "create" ? "新建批次" : "批量任务");
		function J() {
			h.value = !document.hidden && (r.deps.isVisible?.() ?? !0), B.value || (c.value = null), F !== B.value && (N++, F = B.value), w.value?.setVisible(B.value && a.value.view === "list"), E.value?.setVisible(B.value && a.value.view === "create"), D.value?.setVisible(B.value && (a.value.view === "detail" || !!c.value));
		}
		function Y() {
			clearTimeout(I), I = void 0, !A && q.value && (I = setTimeout(() => {
				I = void 0, J(), B.value && X(!1);
			}, q.value));
		}
		async function X(e = !0) {
			if (await t(), A || (J(), !B.value)) return;
			let n = JSON.stringify([
				a.value,
				c.value,
				N
			]);
			if (L && ee === n) return L;
			let r = (async () => {
				try {
					a.value.view === "list" ? await w.value?.refresh(!e) : a.value.view === "create" ? await E.value?.refresh(e) : await D.value?.refresh(e), c.value && await D.value?.refresh(e);
				} finally {
					b.value++;
				}
			})();
			L = r, ee = n;
			try {
				await r;
			} finally {
				L === r && (L = null, ee = ""), Y();
			}
		}
		async function ne() {
			p.value = !0, await X(!1);
		}
		async function re() {
			await t(), B.value && a.value.view === "detail" && await D.value?.showReport();
		}
		function ie(e) {
			p.value = e, J(), Y();
		}
		function ae() {
			return { ...a.value };
		}
		function oe(e) {
			a.value.view === "list" && (f.value = { ...a.value }), M++, a.value = fo(e), a.value.view === "list" && (f.value = { ...a.value }), g.value = "", _.value = "", c.value = null;
		}
		async function se(e, n = {}, i = !1) {
			if (i && e === "detail") {
				let r = ++M;
				if (c.value = fo({
					tab: "bulk",
					view: e,
					...n
				}), g.value = "", p.value = !0, await t(), J(), await D.value?.refresh(!1), A || r !== M || !B.value || !c.value) return;
				if (D.value?.error) {
					g.value = D.value.error, ce();
					return;
				}
				await D.value?.showReport(), Y();
			} else oe({
				tab: "bulk",
				view: e,
				...n
			}), p.value = !0, r.deps.onNavigation(ae(), "push"), await X(!1);
		}
		function ce() {
			c.value && (M++, c.value = null, J(), Y());
		}
		async function le() {
			await se("list", f.value);
		}
		async function ue(e) {
			ce(), M++, a.value = fo({
				...a.value,
				...e
			}), r.deps.onNavigation(ae(), Object.keys(e).every((e) => e === "cursor") ? "replace" : "push"), await t(), Y();
		}
		async function de(e, t, n = "plan_check", i = "") {
			let a = JSON.parse(JSON.stringify({
				query: e,
				source: t
			}));
			S.value = {
				name: String(i || ""),
				operation_key: n,
				query: r.deps.adapter.normalize({
					...a.query,
					limit: null
				}),
				source: a.source,
				parameters: {},
				max_concurrency: 3
			}, await se("create");
		}
		async function fe(e = !1, t = "plan_check", n) {
			if (!n) {
				V.notify("账号范围未就绪，请返回账号页重试");
				return;
			}
			let r = e ? n.ids.map((e) => Z(typeof e == "number" && Number.isSafeInteger(e) ? String(e) : e)) : [];
			e && !r.length ? V.notify("请先选择账号") : await de(n.query, e ? {
				kind: "ids",
				entity: "account",
				ids: r
			} : null, t, n.name);
		}
		async function pe() {
			await de(r.deps.adapter.normalize(), null);
		}
		async function me(e, n) {
			await t(), E.value?.restoreSelectionRequest(e, n);
		}
		async function he() {
			if (v.value) return;
			v.value = !0, g.value = "";
			let e = M;
			try {
				let t = r.deps.intents.pending()[0];
				if (!t) return;
				let n = await r.deps.intents.recover(t);
				if (A || e !== M || !B.value) {
					let e = n.id || n.batch_id || n.round_id;
					V.notify(t.path === "/batches" ? `原批次 #${Z(e)} 已创建` : `原请求回执已找回${e ? "，编号 #" + String(e) : ""}。`);
					return;
				}
				if (t.path === "/selections") S.value = null, await me(t.body, n), await se("create"), V.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
				else if (t.path === "/batches") {
					try {
						r.deps.storage.removeItem("turb_bulk_selection_v1");
					} catch {}
					await se("detail", { batch_id: Z(n.id || n.batch_id) });
				} else {
					let e = t.path.match(/^\/batches\/([1-9]\d*)\//);
					e && await se("detail", { batch_id: e[1] }), V.notify("原请求回执已找回。");
				}
			} catch (e) {
				g.value = e instanceof Error ? e.message : String(e);
			} finally {
				v.value = !1, b.value++;
			}
		}
		function ge() {
			let e = B.value;
			J(), !e && B.value ? X(!1) : Y();
		}
		return o(q, Y, { flush: "post" }), l(() => {
			J(), document.addEventListener("visibilitychange", ge);
		}), T(() => {
			A = !0, clearTimeout(I), document.removeEventListener("visibilitychange", ge);
		}), n({
			activate: ne,
			setVisible: ie,
			refresh: X,
			showReport: re,
			navigationState: ae,
			restoreNavigation: oe,
			navigate: se,
			fromAccounts: fe,
			recover: he,
			restoreSelectionRequest: me
		}), (e, t) => (i(), R("div", {
			class: "bulk-page bulk-page-shell",
			"data-bulk-vue": "",
			"data-bulk-view": a.value.view
		}, [
			C("header", mo, [C("h2", ho, [z(x(te.value) + " ", 1), a.value.view === "detail" ? (i(), R("span", go, "#" + x(a.value.batch_id), 1)) : m("", !0)]), C("div", _o, [
				a.value.view === "list" ? m("", !0) : (i(), R("button", {
					key: 0,
					type: "button",
					class: "jobs-tb-btn",
					"data-bulk-action": "back-list",
					onClick: t[0] ||= (e) => a.value.view === "detail" ? le() : se("list")
				}, "批次列表")),
				C("button", {
					type: "button",
					class: "jobs-tb-btn",
					"data-bulk-action": "refresh",
					onClick: t[1] ||= (e) => X(!0)
				}, "刷新"),
				C("button", {
					type: "button",
					class: O(["jobs-tb-btn", a.value.view === "create" ? "is-current" : "jobs-tb-btn--primary"]),
					"aria-current": a.value.view === "create" ? "page" : void 0,
					"data-bulk-action": "new",
					onClick: pe
				}, "新建批次", 10, vo)
			])]),
			g.value ? (i(), R("p", yo, x(g.value), 1)) : m("", !0),
			_.value ? (i(), R("p", bo, x(_.value), 1)) : m("", !0),
			K.value.length && a.value.view !== "create" ? (i(), R("div", xo, [C("span", null, "有 " + x(K.value.length) + " 个请求未收到回执，草稿已保留。", 1), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: v.value,
				onClick: he
			}, x(v.value ? "正在找回…" : "找回原请求"), 9, So)])) : m("", !0),
			C("div", Co, [
				s(d(Wt, {
					ref_key: "list",
					ref: w,
					navigation: a.value,
					deps: U
				}, null, 8, ["navigation"]), [[P, a.value.view === "list"]]),
				s(d(yr, {
					ref_key: "create",
					ref: E,
					navigation: a.value,
					deps: W,
					seed: S.value,
					visible: B.value && a.value.view === "create"
				}, null, 8, [
					"navigation",
					"seed",
					"visible"
				]), [[P, a.value.view === "create"]]),
				s(d(co, {
					ref_key: "detail",
					ref: D,
					navigation: u.value,
					deps: G,
					visible: B.value && (a.value.view === "detail" || !!c.value),
					onReportClose: ce
				}, null, 8, ["navigation", "visible"]), [[P, a.value.view === "detail"]])
			])
		], 8, po));
	}
}), [["__scopeId", "data-v-c06a7981"]]), To = "turb_bulk_intent:", Eo = /* @__PURE__ */ new Set([
	400,
	403,
	404,
	409,
	410,
	422,
	429
]);
function Do(e, t, n) {
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
		let c = To + a, l = JSON.stringify({
			path: o,
			body: s
		}), u = r.get(c);
		if (u) {
			if (u.signature !== l) throw new Gt("上一请求未收到回执，请先找回原请求，再提交新内容。", 0, "request_receipt_pending");
			return u.promise;
		}
		let d = i(c, t.getItem(c));
		if (d && d.signature !== l) throw new Gt("上一请求未收到回执，请先找回原请求，再提交新内容。", 0, "request_receipt_pending");
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
			if (Eo.has(Number(e?.status))) try {
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
				if (r?.startsWith(To)) {
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
function Oo(e, t) {
	e.replaceChildren();
	function n(t) {
		N(r(Ri, { ...t }), e);
	}
	return n(t), {
		setView: n,
		destroy() {
			N(null, e);
		}
	};
}
// src/bulk.ts
var ko = /* @__PURE__ */ new WeakMap();
function Ao(e, t) {
	let n = ko.get(e);
	if (n) return n;
	let r = jo(e, t);
	return ko.set(e, r), r;
}
function jo(e, t) {
	let n = Kt(), r = {
		get length() {
			return window.sessionStorage.length;
		},
		key: (e) => window.sessionStorage.key(e),
		getItem: (e) => window.sessionStorage.getItem(e),
		setItem: (e, t) => window.sessionStorage.setItem(e, t),
		removeItem: (e) => window.sessionStorage.removeItem(e)
	}, i = Do(n, r, () => globalThis.crypto?.randomUUID?.() || `bulk-${Date.now()}-${Math.random().toString(36).slice(2)}`), a = A(wo, {
		initialNavigation: t.navigation,
		deps: {
			api: n,
			intents: i,
			storage: r,
			adapter: fe(t.query),
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
			a.unmount(), ko.delete(e);
		}
	});
}
function Mo(e, i) {
	let a = j(i.view), o = j(), s = A(n({ setup: () => () => r(Wt, {
		ref: o,
		navigation: a.value,
		deps: {
			api: Kt(),
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
export { Ao as mountBulk, Mo as mountBulkList, Oo as mountBulkReport };
