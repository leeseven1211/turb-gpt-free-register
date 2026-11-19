import { $ as e, A as t, C as n, E as r, F as i, G as a, H as o, K as s, L as c, M as l, R as u, S as d, T as f, Z as p, _ as m, a as h, c as g, d as _, dt as v, et as y, ft as b, g as x, h as S, it as C, j as w, k as T, l as E, lt as D, m as O, n as k, nt as A, o as j, r as M, s as N, st as P, t as F, ut as I, v as L, x as R } from "./_plugin-vue_export-helper-B9RV9BFd.js";
import { _ as z, b as ee, c as B, d as V, f as H, g as U, h as te, l as W, m as G, n as K, p as q, r as ne, t as re, u as ie, v as ae, x as J, y as oe } from "./ListFilterSummary-BG5Tu2p5.js";
import { a as se, n as ce, o as Y, s as le, t as ue } from "./queryAdapter-C1wcY8t-.js";
import { t as de } from "./errorLabels-B-XqaTSM.js";
// ../../../architecture-overview/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/Dialog/DialogRoot.js
var [fe, pe] = /*#__PURE__*/ J("DialogRoot"), me = /* @__PURE__ */ n({
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
		let n = e, r = oe(n, "open", t, {
			defaultValue: n.defaultOpen,
			passive: n.open === void 0
		}), i = y(), a = y(), { modal: o, unmountOnHide: s } = C(n);
		return pe({
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
}), he = /* @__PURE__ */ n({
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
		U();
		let n = fe();
		return (r, o) => (i(), x(P(V), T(t, {
			type: e.as === "button" ? "button" : void 0,
			onClick: o[0] ||= (e) => P(n).onOpenChange(!1)
		}), {
			default: a(() => [u(r.$slots, "default")]),
			_: 3
		}, 16, ["type"]));
	}
}), ge = ["Enter", " "], _e = [
	"ArrowDown",
	"PageUp",
	"Home"
], ve = [
	"ArrowUp",
	"PageDown",
	"End"
];
[..._e, ...ve], [...ge], [...ge];
function ye(e) {
	return e ? "open" : "closed";
}
// ../../../architecture-overview/turb-gpt-free-register/frontend/node_modules/reka-ui/dist/Dialog/DialogContentImpl.js
var be = /* @__PURE__ */ n({
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
		let n = e, r = t, o = fe(), { forwardRef: s, currentElement: c } = U();
		return o.titleId ||= q(void 0, "reka-dialog-title"), o.descriptionId ||= q(void 0, "reka-dialog-description"), l(() => {
			o.contentElement = c, ee() !== document.body && (o.triggerElement.value = ee());
		}), (t, c) => (i(), x(P(W), {
			"as-child": "",
			loop: "",
			trapped: n.trapFocus,
			present: n.present,
			onMountAutoFocus: c[5] ||= (e) => r("openAutoFocus", e),
			onUnmountAutoFocus: c[6] ||= (e) => r("closeAutoFocus", e)
		}, {
			default: a(() => [d(P(ie), T({
				id: P(o).contentId,
				ref: P(s),
				as: e.as,
				"as-child": e.asChild,
				present: n.present,
				"disable-outside-pointer-events": e.disableOutsidePointerEvents,
				role: "dialog",
				"aria-describedby": P(o).descriptionId,
				"aria-labelledby": P(o).titleId,
				"data-state": P(ye)(P(o).open.value)
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
}), xe = /* @__PURE__ */ n({
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
		let n = e, r = t, s = fe(), c = z(r), { forwardRef: l, currentElement: d } = U(), f = O(() => n.present ? d.value : void 0);
		G(f);
		let p = O(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return o(() => n.present, (e, t) => {
			!e && t && s.triggerElement.value?.focus();
		}), (t, r) => (i(), x(be, T({
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
}), Se = /* @__PURE__ */ n({
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
		U();
		let s = fe(), c = y(!1), l = y(!1), d = O(() => {
			let { present: e, ...t } = n;
			return t;
		});
		return o(() => n.present, (e, t) => {
			!e && t && (c.value || s.triggerElement.value?.focus(), c.value = !1, l.value = !1);
		}), (t, n) => (i(), x(be, T({
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
}), Ce = /* @__PURE__ */ n({
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
		let n = e, r = t, o = fe(), c = z(r), { forwardRef: l } = U(), d = O(() => n.forceMount || !o.unmountOnHide.value);
		return (t, r) => (i(), x(P(H), {
			present: P(o).open.value,
			"force-mount": d.value
		}, {
			default: a(({ present: r }) => [P(o).modal.value ? s((i(), x(xe, T({
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
			}, 16, ["present"])), [[N, e.forceMount || P(o).unmountOnHide.value || r]]) : s((i(), x(Se, T({
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
}), we = /* @__PURE__ */ n({
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
		U();
		let n = fe();
		return (e, r) => (i(), x(P(V), T(t, { id: P(n).descriptionId }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), Te = /* @__PURE__ */ n({
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
		let t = e, n = fe(), r = ae(t.present);
		return o(() => t.present, (e) => r.value = e), U(), (t, r) => (i(), x(P(V), {
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
}), Ee = /* @__PURE__ */ n({
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
		let t = e, n = fe(), { forwardRef: r } = U(), o = O(() => t.forceMount || !n.unmountOnHide.value);
		return (t, c) => P(n)?.modal.value ? (i(), x(P(H), {
			key: 0,
			present: P(n).open.value,
			"force-mount": o.value
		}, {
			default: a(({ present: i }) => [s(d(Te, T(t.$attrs, {
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
}), De = /* @__PURE__ */ n({
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
		return (e, n) => (i(), x(P(B), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Oe = /* @__PURE__ */ n({
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
		let t = e, n = fe();
		return U(), (e, r) => (i(), x(P(V), T(t, { id: P(n).titleId }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16, ["id"]));
	}
}), [ke, Ae] = /*#__PURE__*/ J("AlertDialogContent"), je = /* @__PURE__ */ n({
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
		U();
		let s = y();
		return Ae({ onCancelElementChange: (e) => {
			s.value = e;
		} }), (e, n) => (i(), x(P(Ce), T({
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
}), Me = /* @__PURE__ */ n({
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
		let t = e, n = ke(), { forwardRef: r, currentElement: o } = U();
		return l(() => {
			n.onCancelElementChange(o.value);
		}), (e, n) => (i(), x(P(he), T(t, { ref: P(r) }), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ne = /* @__PURE__ */ n({
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
		return U(), (e, n) => (i(), x(P(we), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Pe = /* @__PURE__ */ n({
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
		return U(), (e, n) => (i(), x(P(Ee), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Fe = /* @__PURE__ */ n({
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
		return (e, n) => (i(), x(P(B), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Ie = /* @__PURE__ */ n({
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
		let n = te(e, t);
		return U(), (e, t) => (i(), x(P(me), T(P(n), { modal: !0 }), {
			default: a((t) => [u(e.$slots, "default", I(f(t)))]),
			_: 3
		}, 16));
	}
}), Le = /* @__PURE__ */ n({
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
		return U(), (e, n) => (i(), x(P(Oe), I(f(t)), {
			default: a(() => [u(e.$slots, "default")]),
			_: 3
		}, 16));
	}
}), Re = ["aria-label", "aria-busy"], ze = { class: "cursor-pagination__layout" }, Be = {
	class: "cursor-pagination__count",
	"aria-live": "polite"
}, Ve = { class: "cursor-pagination__actions" }, He = ["disabled"], Ue = ["disabled"], We = ["disabled"], Ge = /*#__PURE__*/ F(/* @__PURE__ */ n({
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
		}, [S("div", ze, [S("span", Be, "本页 " + b(e.itemCount) + " 个", 1), S("div", Ve, [
			e.hasCursor ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "cursor-pagination__first",
				"data-cursor-first": "",
				disabled: e.busy,
				onClick: s
			}, "返回首页", 8, He)) : m("", !0),
			S("button", {
				type: "button",
				"data-cursor-previous": "",
				disabled: e.busy || !e.hasPrevious,
				onClick: a
			}, "上一页", 8, Ue),
			S("button", {
				type: "button",
				"data-cursor-next": "",
				disabled: e.busy || !e.nextCursor,
				onClick: o
			}, "下一页", 8, We)
		])])], 8, Re));
	}
}), [["__scopeId", "data-v-7fd57e6e"]]);
// src/features/bulk/contracts.ts
function X(e) {
	if (typeof e != "string" || !/^[1-9]\d*$/.test(e)) throw Error("任务标识无效");
	return e;
}
function Ke(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("批次列表响应格式无效");
	return e;
}
function qe(e) {
	let t = Ke(e);
	if (!Array.isArray(t.items)) throw Error("批次列表响应格式无效");
	let n = t.items.map((e) => {
		let t = Ke(e), n = Number.isSafeInteger(t.id) ? String(t.id) : t.id;
		if (typeof n != "string" || !/^[1-9]\d*$/.test(n)) throw Error("批次编号无效");
		return {
			...t,
			id: n
		};
	}), r = t.next_cursor ?? (t.page == null ? null : Ke(t.page).next_cursor);
	if (r != null && typeof r != "string") throw Error("批次分页响应格式无效");
	return {
		items: n,
		summary: t.summary == null ? {} : Ke(t.summary),
		nextCursor: r || null
	};
}
// src/features/bulk/useBulkList.ts
var Je = [
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
];
function Ye(e) {
	let t = {
		tab: "bulk",
		view: "list",
		cursor: e.cursor || ""
	};
	for (let n of Je) t[n] = e[n] || "";
	return t;
}
function Xe(e, t) {
	let n = /* @__PURE__ */ new Date(`${e}T00:00:00`), [r, i, a] = e.split("-").map(Number);
	if (!/^\d{4}-\d{2}-\d{2}$/.test(e) || n.getFullYear() !== r || n.getMonth() + 1 !== i || n.getDate() !== a) throw Error("创建日期无效，请调整筛选条件");
	return t && n.setDate(n.getDate() + 1), n.toISOString();
}
function Ze(e) {
	let t = new URLSearchParams({ page_size: "20" });
	return e.cursor && t.set("cursor", e.cursor), e.q && t.set("q", e.q), e.operation && t.set("operation_key[]", e.operation), e.state && t.set("control_state[]", e.state), e.created_from && t.set("created_from", Xe(e.created_from, !1)), e.created_to && t.set("created_before", Xe(e.created_to, !0)), t;
}
function Qe(t, n) {
	let r = A(Ye(t())), i = A(null), a = A([]), s = O(() => a.value.length > 0), c = y(!1), l = y(!1), u = y(""), d = !1, f, m;
	function h() {
		f?.abort(), f = void 0, m = void 0, l.value = !1;
	}
	function g(e) {
		return e.cursor === r.value.cursor && Je.every((t) => e[t] === r.value[t]) ? !1 : (h(), r.value = e, i.value = null, u.value = "", !0);
	}
	function _(e = !1, a) {
		if (d || !c.value || t().view !== "list") return Promise.resolve();
		if (m) return m;
		let o = new AbortController();
		return f = o, l.value = !0, m = (async () => {
			try {
				let t = await n.api.request(`/batches?${Ze(r.value)}`, {
					method: "GET",
					signal: o.signal
				});
				if (o.signal.aborted || a && !a()) return;
				let s = i.value, c = qe(t);
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
		return g(Ye({
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
		e.view === "list" ? g(Ye(e)) && (a.value = [], c.value && _()) : h();
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
var $e = ["aria-busy"], et = {
	key: 0,
	class: "bl-kpis"
}, tt = { class: "bl-toolbar" }, nt = { class: "bl-toolbar-main" }, rt = {
	class: "bl-count",
	role: "status"
}, it = {
	key: 1,
	class: "bl-error",
	role: "alert"
}, at = ["disabled"], ot = ["disabled"], st = ["disabled"], ct = { class: "bl-table" }, lt = { class: "bl-col-name" }, ut = { class: "list-filter-actions" }, dt = { class: "list-filter-options" }, ft = { class: "list-filter-option" }, pt = ["checked"], mt = [
	"value",
	"checked",
	"onChange"
], ht = { class: "list-filter-options" }, gt = { class: "list-filter-option" }, _t = ["checked"], vt = [
	"value",
	"checked",
	"onChange"
], yt = { class: "bl-filter-fields" }, bt = ["value"], xt = ["value"], St = { class: "list-filter-actions" }, Ct = ["data-bulk-row"], wt = { class: "bl-col-name" }, Tt = [
	"disabled",
	"title",
	"onClick"
], Et = ["title"], Dt = { "data-bulk-progress": "" }, Ot = { class: "bl-progress-copy" }, kt = [
	"value",
	"max",
	"aria-label"
], At = {
	key: 1,
	class: "bl-secondary"
}, jt = { class: "bl-results" }, Mt = ["disabled", "onClick"], Nt = ["disabled", "onClick"], Pt = { class: "bl-date" }, Ft = ["disabled", "onClick"], It = { key: 0 }, Lt = { colspan: "7" }, Rt = {
	class: "bl-empty",
	role: "status"
}, zt = /*#__PURE__*/ F(/* @__PURE__ */ n({
	__name: "BulkList",
	props: {
		navigation: {},
		deps: {}
	},
	setup(e, { expose: t }) {
		let n = e, r = Qe(() => n.navigation, n.deps), { navigation: l, items: u, summary: f, nextCursor: p, loading: h, visible: g, error: v, hasPrevious: C, stale: w } = r, T = y(null), k = y(""), A = y(), M = {
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
		function ee(e) {
			return e && typeof e == "object" && !Array.isArray(e) ? e : {};
		}
		function B(e) {
			return typeof e == "number" && Number.isFinite(e) && e >= 0 ? e : null;
		}
		function V(e, t = "—") {
			return e == null || e === "" ? t : String(e);
		}
		let H = O(() => u.value.map((e) => {
			let t = ee(e.summary ?? e.counts), r = {};
			for (let [e, n] of Object.entries(t)) B(n) !== null && (r[e] = n);
			let i = B(e.target_count), a = i === 0 || Object.keys(r).length > 0;
			for (let e of z) e in r && (r.failed = (r.failed || 0) + r[e], delete r[e]);
			let o = ee(e.control), s = ee(e.operation), c = o.paused ?? e.is_paused ? "paused" : V(o.state ?? e.control_state ?? e.state, "preparing"), l = V(s.key ?? e.operation_key ?? e.action_key), u = e.id, d = a ? I.reduce((e, t) => e + (r[t] || 0), 0) : null, f = i === null || d === null ? null : i === 0 ? 0 : Math.min(100, Math.round(100 * d / i));
			return {
				id: u,
				name: V(e.name ?? e.title, `批次 #${u}`),
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
		})), U = O(() => B(f.value.total_batches)), te = O(() => w.value ? h.value ? "正在读取批次数量…" : "批次数量未知" : U.value === null ? `本页 ${u.value.length} 个批次` : `${U.value.toLocaleString()} 个批次`), W = O(() => {
			let e = [
				{
					key: "active_batches",
					label: "执行中",
					value: B(f.value.active_batches),
					unit: "批"
				},
				{
					key: "ended_batches",
					label: "已结束",
					value: B(f.value.ended_batches),
					unit: "批"
				},
				{
					key: "failed_targets",
					label: "失败账号",
					value: B(f.value.failed_targets),
					unit: "个"
				}
			], t = B(f.value.attention_targets);
			return t != null && e[2].value != null && (e[2].value += t), e.filter((e) => e.value !== null);
		}), G = O(() => {
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
		function K(e) {
			e === "date" ? r.applyFilters({
				created_from: "",
				created_to: ""
			}) : r.applyFilters({ [e]: "" });
		}
		function q(e, t) {
			r.applyFilters({ [e]: t });
		}
		function ie() {
			r.applyFilters({ q: k.value.trim() }), T.value = null;
		}
		function ae(e, t) {
			g.value && !w.value && n.deps.callbacks.navigate("detail", {
				batch_id: e,
				...t ? { result_state: t } : {}
			});
		}
		function J(e) {
			g.value && !w.value && n.deps.callbacks.navigate("detail", { batch_id: e }, !0);
		}
		function oe() {
			let e = window.getSelection();
			return w.value || !(e?.toString() && A.value?.contains(e.anchorNode));
		}
		async function se(e = !1) {
			oe() && await r.refresh(e, oe);
		}
		function ce(e) {
			e || (T.value = null), r.setVisible(e);
		}
		return t({
			refresh: se,
			setVisible: ce
		}), (t, n) => (i(), L("section", {
			class: "bl-root",
			"aria-label": "批次列表",
			"aria-busy": P(h)
		}, [
			W.value.length ? (i(), L("div", et, [(i(!0), L(_, null, c(W.value, (e) => (i(), L("div", {
				key: e.key,
				class: D(["bl-kpi", { "is-warning": e.key === "failed_targets" && !!e.value }])
			}, [S("span", null, b(e.label), 1), S("strong", null, [R(b(e.value), 1), S("small", null, b(e.unit), 1)])], 2))), 128))])) : m("", !0),
			S("div", tt, [S("div", nt, [S("span", rt, b(te.value), 1), d(re, {
				items: G.value,
				onRemove: K
			}, null, 8, ["items"])]), G.value.length ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "bl-link",
				onClick: n[0] ||= (...e) => P(r).resetFilters && P(r).resetFilters(...e)
			}, "清除筛选")) : m("", !0)]),
			P(v) ? (i(), L("div", it, [
				S("span", null, b(P(v)), 1),
				S("button", {
					type: "button",
					class: "bl-link",
					disabled: P(h),
					onClick: n[1] ||= (e) => P(r).refresh()
				}, "重试", 8, at),
				P(w) && P(l).cursor ? (i(), L("button", {
					key: 0,
					class: "bl-link",
					type: "button",
					disabled: P(h),
					onClick: n[2] ||= (...e) => P(r).first && P(r).first(...e)
				}, " 返回首页", 8, ot)) : m("", !0),
				P(w) && P(C) ? (i(), L("button", {
					key: 1,
					class: "bl-link",
					type: "button",
					disabled: P(h),
					onClick: n[3] ||= (...e) => P(r).previous && P(r).previous(...e)
				}, " 上一页 ", 8, st)) : m("", !0)
			])) : m("", !0),
			S("div", {
				ref_key: "tableHost",
				ref: A,
				class: "bl-table-wrap",
				tabindex: "0",
				role: "region",
				"aria-label": "批次列表内容"
			}, [S("table", ct, [S("thead", null, [S("tr", null, [
				S("th", lt, [d(ne, {
					label: "批次名称或编号",
					"trigger-label": "批次",
					active: !!P(l).q,
					summary: P(l).q,
					open: T.value === "q",
					"onUpdate:open": n[6] ||= (e) => T.value = e ? "q" : null
				}, {
					default: a(() => [S("form", {
						class: "bl-filter-fields",
						onSubmit: E(ie, ["prevent"])
					}, [S("label", null, [n[16] ||= R("名称或批次号", -1), s(S("input", {
						"onUpdate:modelValue": n[4] ||= (e) => k.value = e,
						type: "search",
						placeholder: "搜索批次名称或编号",
						autocomplete: "off"
					}, null, 512), [[j, k.value]])]), S("div", ut, [S("button", {
						type: "button",
						onClick: n[5] ||= (e) => K("q")
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
				S("th", null, [d(ne, {
					label: "操作类型",
					active: !!P(l).operation,
					summary: M[P(l).operation || ""] || P(l).operation,
					open: T.value === "operation",
					"onUpdate:open": n[8] ||= (e) => T.value = e ? "operation" : null
				}, {
					default: a(() => [S("fieldset", dt, [
						n[19] ||= S("legend", { class: "bl-sr-only" }, "操作类型", -1),
						S("label", ft, [S("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: "",
							checked: !P(l).operation,
							onChange: n[7] ||= (e) => q("operation", "")
						}, null, 40, pt), n[18] ||= R("全部操作", -1)]),
						(i(), L(_, null, c(M, (e, t) => S("label", {
							class: "list-filter-option",
							key: t
						}, [S("input", {
							type: "radio",
							name: "bulk-list-operation",
							value: t,
							checked: P(l).operation === t,
							onChange: (e) => q("operation", t)
						}, null, 40, mt), R(b(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				S("th", null, [d(ne, {
					label: "状态",
					active: !!P(l).state,
					summary: N[P(l).state || ""] || P(l).state,
					open: T.value === "state",
					"onUpdate:open": n[10] ||= (e) => T.value = e ? "state" : null
				}, {
					default: a(() => [S("fieldset", ht, [
						n[21] ||= S("legend", { class: "bl-sr-only" }, "运行状态", -1),
						S("label", gt, [S("input", {
							type: "radio",
							name: "bulk-list-state",
							value: "",
							checked: !P(l).state,
							onChange: n[9] ||= (e) => q("state", "")
						}, null, 40, _t), n[20] ||= R("全部状态", -1)]),
						(i(), L(_, null, c(N, (e, t) => S("label", {
							class: "list-filter-option",
							key: t
						}, [S("input", {
							type: "radio",
							name: "bulk-list-state",
							value: t,
							checked: P(l).state === t,
							onChange: (e) => q("state", t)
						}, null, 40, vt), R(b(e), 1)])), 64))
					])]),
					_: 1
				}, 8, [
					"active",
					"summary",
					"open"
				])]),
				n[24] ||= S("th", null, "完成进度", -1),
				n[25] ||= S("th", null, "当前结果", -1),
				S("th", null, [d(ne, {
					label: "创建时间",
					active: !!(P(l).created_from || P(l).created_to),
					summary: `${P(l).created_from || "不限"} 至 ${P(l).created_to || "不限"}`,
					open: T.value === "date",
					"onUpdate:open": n[14] ||= (e) => T.value = e ? "date" : null
				}, {
					default: a(() => [S("div", yt, [
						S("label", null, [n[22] ||= R("开始日期", -1), S("input", {
							type: "date",
							value: P(l).created_from,
							onChange: n[11] ||= (e) => q("created_from", e.target.value)
						}, null, 40, bt)]),
						S("label", null, [n[23] ||= R("截止日期", -1), S("input", {
							type: "date",
							value: P(l).created_to,
							onChange: n[12] ||= (e) => q("created_to", e.target.value)
						}, null, 40, xt)]),
						S("div", St, [S("button", {
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
				n[26] ||= S("th", null, [S("span", { class: "bl-sr-only" }, "操作")], -1)
			])]), S("tbody", null, [(i(!0), L(_, null, c(H.value, (e) => (i(), L("tr", {
				key: e.id,
				"data-bulk-row": e.id
			}, [
				S("td", wt, [S("button", {
					type: "button",
					class: "bl-name",
					"data-bulk-open": "",
					disabled: P(w),
					title: e.name,
					onClick: (t) => ae(e.id)
				}, b(e.name), 9, Tt), S("span", {
					class: "bl-secondary",
					title: `批次 #${e.id}`
				}, "#" + b(e.id), 9, Et)]),
				S("td", null, b(e.operation), 1),
				S("td", null, [S("span", { class: D(["bl-status", `is-${e.state}`]) }, b(e.status), 3)]),
				S("td", Dt, [e.total !== null && e.done !== null ? (i(), L(_, { key: 0 }, [S("span", Ot, [R(b(e.done) + " / " + b(e.total) + " ", 1), S("span", null, b(e.percent) + "%", 1)]), S("progress", {
					value: e.done,
					max: Math.max(1, e.total),
					"aria-label": `已结束 ${e.done} 个，共 ${e.total} 个`
				}, null, 8, kt)], 64)) : (i(), L("span", At, b(e.total === null ? "名单准备中" : "结果待汇总"), 1))]),
				S("td", null, [S("div", jt, [S("button", {
					type: "button",
					class: "bl-result is-success",
					"data-bulk-result": "success",
					disabled: P(w) || !e.counts.success,
					onClick: (t) => ae(e.id, "success")
				}, " 成功 " + b(e.known ? e.counts.success || 0 : "—"), 9, Mt), S("button", {
					type: "button",
					class: "bl-result is-failed",
					"data-bulk-result": "failed",
					disabled: P(w) || !e.counts.failed,
					onClick: (t) => ae(e.id, "failed")
				}, " 失败 " + b(e.known ? e.counts.failed || 0 : "—"), 9, Nt)])]),
				S("td", Pt, b(e.createdAt), 1),
				S("td", null, [S("button", {
					type: "button",
					class: "bl-button",
					"data-bulk-report": "",
					disabled: P(w),
					onClick: (t) => J(e.id)
				}, " 查看报告 ", 8, Ft)])
			], 8, Ct))), 128)), H.value.length ? m("", !0) : (i(), L("tr", It, [S("td", Lt, [S("div", Rt, [S("strong", null, b(P(h) ? "正在加载批次…" : P(v) ? "暂时无法读取批次" : G.value.length ? "没有匹配的批次" : "还没有批次"), 1), !P(h) && !P(v) ? (i(), L(_, { key: 0 }, [n[27] ||= S("p", null, "选择操作和账号范围，即可集中执行与追踪结果。", -1), S("button", {
				type: "button",
				class: "bl-button",
				"data-bulk-create": "",
				onClick: n[15] ||= (t) => e.deps.callbacks.navigate("create")
			}, " 新建批次 ")], 64)) : m("", !0)])])]))])])], 512),
			P(w) ? m("", !0) : (i(), x(Ge, {
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
		], 8, $e));
	}
}), [["__scopeId", "data-v-94cf2848"]]), Bt = class extends Error {
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
function Vt(e = fetch) {
	return { async request(t, n = {}) {
		if (!t.startsWith("/") || t.startsWith("//")) throw Error("批量接口路径无效");
		let r = await e("/api/bulk" + t, {
			credentials: "same-origin",
			...n
		}), i = r.headers?.get("content-type");
		if (i && !i.includes("application/json")) throw new Bt(r.status === 401 || r.redirected ? "登录已失效，请重新登录后返回。" : "服务返回了非 JSON 响应", r.status);
		let a = await r.json().catch(() => null), o = a && typeof a == "object" && !Array.isArray(a) ? a : {};
		if (!r.ok || o.ok === !1) {
			let e = o.error && typeof o.error == "object" && !Array.isArray(o.error) ? o.error : o, t = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {};
			throw new Bt(String(e.message || (typeof o.error == "string" ? o.error : "") || `请求失败（HTTP ${r.status}）`), r.status, String(e.code || o.code || ""), t(e.details || o.details), typeof e.field == "string" ? e.field : null, t(e.fields || o.fields), typeof o.request_id == "string" ? o.request_id : void 0, typeof e.retryable == "boolean" ? e.retryable : void 0);
		}
		if (typeof a != "object" || !a || Array.isArray(a) || o.ok === !0 && (!o.data || typeof o.data != "object" || Array.isArray(o.data))) throw new Bt("服务返回了无效 JSON 响应", r.status);
		return o.data ?? o;
	} };
}
// src/features/bulk/useBulkCreate.ts
var Ht = "turb_bulk_draft_v1", Ut = "turb_bulk_selection_v1", Wt = (e) => JSON.parse(JSON.stringify(e)), Gt = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {};
function Kt(e) {
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
	}), I = O(() => M.value === "ready" ? Number(i.value?.target_count ?? i.value?.total_count) : r.value.source?.kind === "ids" ? r.value.source.ids.length : r.value.source ? null : s.value), L = O(() => r.value.source?.kind === "ids" ? `已选 ${r.value.source.ids.length} 个账号` : r.value.source?.kind === "batch_targets" ? `批次 #${r.value.source.batch_id} 的固定名单` : r.value.query.filters.email ? `邮箱含「${r.value.query.filters.email}」` : "按当前筛选"), R = O(() => l.value ? "正在固定账号范围…" : M.value === "ready" ? "账号范围已固定" : I.value === 0 ? "没有匹配账号" : "匹配账号数量"), z = O(() => l.value ? "正在准备本批次，请稍候" : M.value === "ready" ? "将使用这份固定名单创建批次" : I.value === 0 ? "请调整账号筛选条件" : r.value.source?.kind === "batch_targets" ? "创建时沿用原批次固定名单" : r.value.source?.kind === "ids" ? "将使用已选账号创建批次" : s.value == null ? "正在统计，创建时会核对最终数量" : `当前条件匹配 ${s.value} 个账号，将全部执行`), ee = O(() => A.value?.availability?.available === !1 ? `当前设置不可用：${A.value.availability.reason || Gt(A.value.availability).reason_code || "请检查配置"}。请到配置页调整。` : "");
	function B() {
		try {
			e.storage.setItem(Ht, JSON.stringify(r.value));
		} catch {}
	}
	function V() {
		try {
			i.value ? e.storage.setItem(Ut, JSON.stringify(i.value)) : e.storage.removeItem(Ut);
		} catch {}
	}
	function H(e) {
		return [e?.request_parameters, e?.parameters].some((e) => Object.keys(e || {}).some((e) => e !== "timezone_offset_min" || r.value.operation_key !== "plan_check"));
	}
	function U(n) {
		let r = Gt(n), i = e.adapter.normalize(Gt(r.query)), a = r.source && typeof r.source == "object" ? Wt(r.source) : null;
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
	function te(e, t) {
		let n = U(e);
		r.value = n.draft;
		let a = Gt(t);
		i.value = typeof a.id == "string" ? Wt(a) : null, (n.limited || H(i.value)) && (i.value = null), B(), V();
	}
	te(n(Ht), n(Ut));
	function W() {
		d.value = "", f.value = "", m.value = "";
	}
	function G(e, t = "") {
		let n = e;
		d.value = t + (n.message || String(e)) + (n.code ? `（${n.code}）` : "") + (n.status === 401 ? "，请重新登录后返回，草稿与请求身份已保留。" : ""), f.value = n.field || "";
	}
	let K = (e) => Gt(e).name === "AbortError";
	function q(e) {
		x = e, e || (clearTimeout(D), _.forEach((e) => e.abort()));
	}
	async function ne(t) {
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
	async function re(e = !1) {
		if (a.value && !e) return;
		let t = await ne("/catalog");
		b || (a.value = t, k.value.some((e) => e.key === r.value.operation_key) || (r.value.operation_key = k.value[0]?.key || "", i.value = null, V(), B()));
	}
	async function ie() {
		if (!x || b) return;
		let t = v, n = JSON.stringify(e.adapter.normalize(r.value.query)), i = g.get(n);
		if (i && e.now() - i.at < 3e4) {
			o.value = i.facets, s.value = i.matched;
			return;
		}
		s.value = null;
		let a = await ne(`/query-facets?query=${encodeURIComponent(n)}`), c = Gt(a.facets || a), l = a.matched == null ? null : Number(a.matched);
		g.set(n, {
			facets: c,
			matched: l,
			at: e.now()
		}), g.size > 10 && g.delete(g.keys().next().value), !b && t === v && n === JSON.stringify(e.adapter.normalize(r.value.query)) && (o.value = c, s.value = l);
	}
	function ae() {
		if (clearTimeout(D), !x) return;
		let e = v;
		D = setTimeout(() => {
			ie().catch((t) => {
				!K(t) && !b && e === v && G(t, "筛选选项更新失败：");
			});
		}, 350);
	}
	function J() {
		v++, E = null, l.value = !1, i.value = null, V();
	}
	function oe(e) {
		J(), clearTimeout(D), te(Wt(e), null), s.value = null, W(), S && ae();
	}
	function le(e, t) {
		l.value || (e === "name" ? r.value.name = String(t) : r.value.max_concurrency = Number(t), B());
	}
	function ue(e) {
		l.value || r.value.operation_key === e || (r.value.operation_key = e, J(), W(), B());
	}
	function de(t) {
		if (l.value) return;
		let n = e.adapter.normalize({
			...t,
			limit: null
		});
		JSON.stringify(n) !== JSON.stringify(r.value.query) && (r.value.query = n, s.value = null, J(), W(), B(), ae());
	}
	function fe(e, t) {
		let n = Wt(r.value.query);
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
			...r.value.query,
			date_from: "",
			date_to: ""
		}) : fe(e, e === "archived" ? "0" : [
			"q",
			"email",
			"id"
		].includes(e) ? "" : []);
	}
	function me() {
		l.value || (r.value.source = null, r.value.query = e.adapter.normalize(), s.value = null, J(), W(), B(), ae());
	}
	function he(t, n) {
		return e.callbacks.facetLabel?.(t, n) || n;
	}
	function ge(e) {
		let t = a.value?.query_schema?.fields, n = Array.isArray(t) ? t.map(Gt).find((t) => t.key === e) : void 0, i = n?.options ?? n?.enum ?? n?.values, s = o.value[e] ?? (Array.isArray(i) ? i : []), c = /* @__PURE__ */ new Map();
		for (let t of s) {
			let n = typeof t == "object" && t ? t : { value: String(t) };
			n.value && c.set(n.value, {
				...n,
				label: n.label || he(e === "token" ? "account_token" : e, n.value)
			});
		}
		for (let t of Y(r.value.query, e)) c.has(t) || c.set(t, {
			value: t,
			label: he(e === "token" ? "account_token" : e, t)
		});
		return [...c.values()];
	}
	let _e = O(() => [
		...se(r.value.query, he),
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
		return e?.timezone_offset_min || Gt(e?.properties).timezone_offset_min ? { timezone_offset_min: (/* @__PURE__ */ new Date()).getTimezoneOffset() } : {};
	}
	async function ye() {
		if (!i.value || !x || b) return;
		let e = X(i.value.id), t = v, n = await ne(`/selections/${encodeURIComponent(e)}?page_size=1`);
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
					if (await re(), b || !x) return;
					let e = v;
					try {
						await ie();
					} catch (t) {
						if (K(t)) return;
						e === v && G(t, "筛选选项读取失败：");
					}
					!b && e === v && i.value && await ye(), S = !0;
				} catch (e) {
					!K(e) && !b && G(e, "读取配置失败：");
				} finally {
					c.value = !1, C = null;
				}
			})(), C;
		}
	}
	async function xe(t, n) {
		if (K(t) || b || n !== v) return;
		E = null, l.value = !1, G(t, "创建失败：");
		let r = t;
		if (["config_revision_changed", "selection_settings_mismatch"].includes(r.code)) {
			i.value = null, V();
			try {
				await re(!0);
			} catch (e) {
				G(e, "配置读取失败：");
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
			if (!a || M.value !== "ready") throw new Bt(a?.error?.message || a?.error_detail?.message || "账号范围准备失败，请重试", 0, a?.error_code || "selection_preparation_failed");
			if (Number(a.target_count ?? a.total_count) <= 0) throw new Bt("没有匹配账号，请调整筛选条件", 0, "selection_empty");
			let o = A.value;
			if (!o) throw new Bt("没有可用的批量操作", 0, "operation_unavailable");
			let s = {
				name: r.value.name,
				selection_id: X(a.id),
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
			}, c = await e.intents.submit("create", "/batches", s), u = X(c.id || c.batch_id);
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
		W();
		let n = Number(r.value.max_concurrency);
		if (!Number.isInteger(n) || n < 1 || n > P.value) {
			G(new Bt(`本批并发上限需为 1–${P.value} 的整数`, 0, "invalid_concurrency", {}, "max_concurrency"));
			return;
		}
		if (r.value.name.length > 120) {
			G(new Bt("批次名称最多 120 个字符", 0, "invalid_name", {}, "name"));
			return;
		}
		if (!A.value) {
			G(new Bt("请先读取可用的批量操作", 0, "operation_unavailable"));
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
					source: Wt(r.value.source || {
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
				e && await re(!0), n || (i.value ? await ye() : await ie()), t === v && await Se();
			} catch (e) {
				!K(e) && t === v && (E ? await xe(e, t) : G(e, "读取账号范围失败："));
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
		let i = Gt(n.source), a = Gt(n.operation), o = e.adapter.normalize(i.kind === "query" ? Gt(i.query) : {}), s = {
			...t(),
			operation_key: String(a.key || "plan_check"),
			query: o,
			source: i.kind === "query" ? null : i
		};
		J(), te(s, {
			...r,
			request_parameters: Gt(n.parameters),
			config_revision: n.expected_config_revision
		});
	}
	async function Ee() {
		if (u.value || l.value || b) return;
		u.value = !0, W();
		let t = v;
		try {
			let n = e.intents.pending()[0];
			if (!n) return;
			let r = await e.intents.recover(n);
			if (b || t !== v || !x) {
				e.callbacks.notify(n.path === "/batches" ? `原批次 #${X(r.id || r.batch_id)} 已创建` : "原请求回执已找回，当前草稿保留。");
				return;
			}
			if (n.path === "/selections") Te(n.body, r), e.callbacks.navigate("create"), e.callbacks.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
			else if (n.path === "/batches") i.value = null, V(), e.callbacks.navigate("detail", { batch_id: X(r.id || r.batch_id) });
			else {
				let t = n.path.match(/^\/batches\/(\d+)\//);
				t && e.callbacks.navigate("detail", { batch_id: X(t[1]) }), e.callbacks.notify("原请求回执已找回。");
			}
		} catch (e) {
			G(e, "找回请求失败：");
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
		availabilityWarning: ee,
		chips: _e,
		accountFilters: ce,
		initialize: be,
		refresh: we,
		recover: Ee,
		restoreSelectionRequest: Te,
		loadFacets: ie,
		applySeed: oe,
		setVisible: q,
		setDraftField: le,
		setOperation: ue,
		setQueryField: fe,
		clearFilter: pe,
		clearFilters: me,
		filterOptions: ge,
		createBatch: Ce,
		clearError: W
	};
}
// src/features/bulk/BulkCreate.vue?vue&type=script&setup=true&lang.ts
var qt = {
	key: 0,
	class: "bulk-empty",
	role: "status"
}, Jt = ["aria-busy"], Yt = { class: "bulk-create-main" }, Xt = { class: "bulk-card bulk-create-card" }, Zt = {
	class: "bulk-operation-grid",
	role: "radiogroup",
	"aria-label": "批量操作"
}, Qt = ["title"], $t = [
	"value",
	"checked",
	"disabled",
	"onChange"
], en = {
	viewBox: "0 0 24 24",
	fill: "none",
	stroke: "currentColor",
	"stroke-width": "1.6",
	"stroke-linecap": "round",
	"stroke-linejoin": "round",
	"aria-hidden": "true"
}, tn = ["d"], nn = { class: "bulk-card bulk-create-card" }, rn = {
	key: 0,
	class: "bulk-error bulk-operation-warning",
	"data-bulk-operation-warning": ""
}, an = { class: "bulk-batch-fields" }, on = { class: "bulk-field bulk-name-field" }, sn = [
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], cn = { class: "bulk-field" }, ln = [
	"max",
	"value",
	"disabled",
	"aria-invalid",
	"aria-describedby"
], un = {
	class: "bulk-card bulk-create-card",
	"data-bulk-account-scope": ""
}, dn = { class: "bulk-step-head" }, fn = ["disabled"], pn = {
	key: 0,
	class: "bulk-source-banner"
}, mn = ["disabled"], hn = { "data-bulk-filters": "" }, gn = { class: "bulk-query-top" }, _n = { class: "bulk-field bulk-query-search" }, vn = ["value", "disabled"], yn = ["open"], bn = { class: "bulk-filter-popover-panel" }, xn = { class: "bulk-filter-popover-heading" }, Sn = { class: "bulk-field" }, Cn = ["value", "disabled"], wn = { class: "bulk-field" }, Tn = ["value", "disabled"], En = ["open"], Dn = { class: "bulk-filter-popover-panel" }, On = { class: "bulk-filter-popover-heading" }, kn = { class: "bulk-field" }, An = ["value", "disabled"], jn = { class: "bulk-field" }, Mn = ["value", "disabled"], Nn = {
	class: "bulk-column-filters",
	"aria-label": "账号列筛选"
}, Pn = ["data-filter-field", "open"], Fn = ["onClick"], In = {
	key: 0,
	"data-filter-count": ""
}, Ln = { class: "bulk-filter-popover-panel" }, Rn = { class: "bulk-filter-popover-heading" }, zn = ["aria-label"], Bn = {
	key: 0,
	class: "bulk-field"
}, Vn = [
	"data-query-filter",
	"value",
	"disabled",
	"onInput"
], Hn = {
	key: 1,
	class: "bulk-filter-options"
}, Un = [
	"data-query-filter",
	"value",
	"checked",
	"disabled",
	"onChange"
], Wn = {
	key: 0,
	class: "bulk-muted"
}, Gn = {
	class: "bulk-query-chips",
	"data-query-chips": "",
	"aria-label": "已选账号条件"
}, Kn = [
	"data-clear-query",
	"aria-label",
	"disabled",
	"onClick"
], qn = {
	key: 0,
	class: "bulk-filter-empty"
}, Jn = { class: "bulk-card bulk-create-side" }, Yn = { class: "bulk-side-sticky" }, Xn = { class: "bulk-side-heading" }, Zn = { "data-bulk-create-summary": "" }, Qn = {
	class: "bulk-side-big",
	"data-bulk-side-count": "",
	role: "status",
	"aria-live": "polite",
	"aria-atomic": "true"
}, $n = {
	class: "bulk-side-hint",
	"data-bulk-create-hint": ""
}, er = { class: "bulk-side-meta" }, tr = { "data-bulk-side-operation": "" }, nr = { "data-bulk-side-scope": "" }, rr = { "data-bulk-side-concurrency": "" }, ir = {
	key: 0,
	class: "bulk-side-warning",
	"data-bulk-side-warning": ""
}, ar = {
	key: 1,
	id: "bulkCreateError",
	class: "bulk-error",
	"data-bulk-action-error": "",
	role: "alert"
}, or = {
	key: 2,
	class: "bulk-notice",
	"data-bulk-recovery": "",
	role: "status"
}, sr = ["disabled"], cr = { class: "bulk-side-actions" }, lr = ["disabled"], ur = ["disabled"], dr = /* @__PURE__ */ n({
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
		let r = e, a = Kt(r.deps), { draft: u, loading: d, creating: f, recovering: p, error: h, errorField: v, existingBatchId: x, operations: C, operation: w, concurrencyMax: T, pendingCount: k, count: A, scopeLabel: j, summary: M, hint: F, availabilityWarning: I, chips: z, needsRefresh: ee } = a, B = y(), V = y(""), H = O(() => f.value || p.value), U = a.accountFilters.filter((e) => !["email", "date"].includes(e.key)), te = {
			plan_check: "套餐与优惠",
			token_refresh: "获取最新访问令牌",
			password_setup: "补充登录密码",
			twofa_setup: "启用验证器",
			codex_retry: "获取授权凭证",
			account_completion: "完成已配置的项目"
		}, W = {
			plan_check: "M4 5h16v14H4z M4 10h16 M8 14h3",
			token_refresh: "M20 7v5h-5 M4 17v-5h5 M6 8a7 7 0 0 1 12-2l2 2 M4 16l2 2a7 7 0 0 0 12-2",
			password_setup: "M8 11V7a4 4 0 0 1 8 0v4 M6 11h12v10H6z M12 15v2",
			twofa_setup: "M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7z M8 12l3 3 5-6",
			codex_retry: "M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16",
			account_completion: "M9 5h11 M9 12h11 M9 19h11 M3 5h1 M3 12h1 M3 19h1"
		};
		function G(e) {
			return e.target.value;
		}
		function K(e, t, n) {
			let r = new Set(Y(u.value.query, e));
			n ? r.add(t) : r.delete(t), a.setQueryField(e, [...r]);
		}
		function q(e) {
			let t = (e?.target)?.closest("details");
			V.value = "", (t?.querySelector("summary"))?.focus();
		}
		function ne(e, t) {
			if (H.value) return;
			if (V.value === e) {
				V.value = "";
				return;
			}
			let n = t.currentTarget, r = n.nextElementSibling, i = n.getBoundingClientRect().left, a = Math.min(250, window.innerWidth - 48), o = Math.max(10, document.querySelector("main")?.getBoundingClientRect().left ?? 0), s = Math.max(o, Math.min(i, document.documentElement.clientWidth - a - 10));
			r.style.setProperty("--bulk-filter-offset", `${s - i}px`), V.value = e;
		}
		function re(e) {
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
		}), (t, n) => P(d) && !P(C).length ? (i(), L("div", qt, "正在读取操作和筛选配置…")) : (i(), L("form", {
			key: 1,
			ref_key: "form",
			ref: B,
			"data-bulk-create-form": "",
			class: "bulk-create-form",
			novalidate: "",
			"aria-busy": H.value,
			onSubmit: n[18] ||= E((e) => P(a).createBatch(), ["prevent"]),
			onKeydown: n[19] ||= g((e) => q(e), ["esc"])
		}, [S("div", Yt, [
			S("section", Xt, [n[21] ||= S("div", { class: "bulk-step-head" }, [S("span", { class: "bulk-step-no" }, "1"), S("div", null, [S("h3", null, "选择操作"), S("p", { class: "bulk-section-note" }, "本次要对账号做什么")])], -1), S("div", Zt, [(i(!0), L(_, null, c(P(C), (e) => (i(), L("label", {
				key: e.key,
				class: "bulk-operation",
				title: e.availability?.available === !1 ? e.availability.reason || "当前不可用" : ""
			}, [
				S("input", {
					type: "radio",
					name: "operation_key",
					value: e.key,
					checked: P(u).operation_key === e.key,
					disabled: H.value,
					required: "",
					onChange: (t) => P(a).setOperation(e.key)
				}, null, 40, $t),
				(i(), L("svg", en, [S("path", { d: W[e.key] || W.account_completion }, null, 8, tn)])),
				S("span", null, [S("strong", null, b(e.label || e.key), 1), S("small", null, b(te[e.key] || "批量账号操作"), 1)]),
				n[20] ||= S("span", {
					class: "bulk-operation-check",
					"aria-hidden": "true"
				}, "✓", -1)
			], 8, Qt))), 128))])]),
			S("section", nn, [
				n[24] ||= S("div", { class: "bulk-step-head" }, [S("span", { class: "bulk-step-no" }, "2"), S("div", null, [S("h3", null, "批次设置")])], -1),
				P(I) ? (i(), L("p", rn, b(P(I)), 1)) : m("", !0),
				S("div", an, [S("label", on, [n[22] ||= R("批次名称", -1), S("input", {
					name: "name",
					maxlength: "120",
					value: P(u).name,
					placeholder: "留空自动命名",
					disabled: H.value,
					"aria-invalid": P(v) === "name" || void 0,
					"aria-describedby": P(v) === "name" ? "bulkCreateError" : void 0,
					onInput: n[0] ||= (e) => P(a).setDraftField("name", G(e))
				}, null, 40, sn)]), S("label", cn, [n[23] ||= R("本批并发上限", -1), S("input", {
					name: "max_concurrency",
					type: "number",
					min: "1",
					max: P(T),
					step: "1",
					value: P(u).max_concurrency,
					required: "",
					disabled: H.value,
					"aria-invalid": P(v) === "max_concurrency" || void 0,
					"aria-describedby": P(v) === "max_concurrency" ? "bulkCreateError" : void 0,
					onInput: n[1] ||= (e) => P(a).setDraftField("max_concurrency", G(e))
				}, null, 40, ln)])])
			]),
			S("section", un, [
				S("div", dn, [
					n[25] ||= S("span", { class: "bulk-step-no" }, "3", -1),
					n[26] ||= S("div", null, [S("h3", null, "账号范围"), S("p", { class: "bulk-section-note" }, "与账号列表使用同一套筛选")], -1),
					S("button", {
						type: "button",
						class: "bulk-link",
						"data-bulk-action": "clear-filters",
						disabled: H.value,
						onClick: n[2] ||= (...e) => P(a).clearFilters && P(a).clearFilters(...e)
					}, "清空条件", 8, fn)
				]),
				P(u).source ? (i(), L("div", pn, [S("span", null, b(P(u).source.kind === "ids" ? "使用已选账号" : `沿用批次 #${P(u).source.batch_id} 的账号名单`), 1), S("button", {
					type: "button",
					class: "bulk-link",
					"data-bulk-action": "use-query",
					disabled: H.value,
					onClick: n[3] ||= (...e) => P(a).clearFilters && P(a).clearFilters(...e)
				}, "改为按条件筛选", 8, mn)])) : m("", !0),
				s(S("div", hn, [
					S("div", gn, [
						S("label", _n, [n[27] ||= S("span", { class: "bulk-sr-only" }, "邮箱或姓名", -1), S("input", {
							"data-query": "email",
							type: "search",
							value: P(u).query.filters.email,
							autocomplete: "off",
							placeholder: "搜索邮箱或姓名",
							disabled: H.value,
							onInput: n[4] ||= (e) => P(a).setQueryField("email", G(e))
						}, null, 40, vn)]),
						S("details", {
							class: "bulk-filter-popover",
							"data-filter-dates": "",
							open: V.value === "date",
							onFocusout: re
						}, [S("summary", { onClick: n[5] ||= E((e) => ne("date", e), ["prevent"]) }, [...n[28] ||= [R("创建日期", -1), S("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [S("path", { d: "m4 6 4 4 4-4" })], -1)]]), S("div", bn, [
							S("div", xn, [n[29] ||= S("strong", null, "创建日期", -1), S("button", {
								type: "button",
								"aria-label": "关闭创建日期筛选",
								onClick: n[6] ||= (e) => q(e)
							}, "完成")]),
							S("label", Sn, [n[30] ||= R("创建日期从", -1), S("input", {
								"data-query": "date_from",
								type: "date",
								value: P(u).query.date_from,
								disabled: H.value,
								onInput: n[7] ||= (e) => P(a).setQueryField("date_from", G(e))
							}, null, 40, Cn)]),
							S("label", wn, [n[31] ||= R("创建日期至（含当天）", -1), S("input", {
								"data-query": "date_to",
								type: "date",
								value: P(u).query.date_to,
								disabled: H.value,
								onInput: n[8] ||= (e) => P(a).setQueryField("date_to", G(e))
							}, null, 40, Tn)])
						])], 40, yn),
						S("details", {
							class: "bulk-filter-popover",
							open: V.value === "more",
							onFocusout: re
						}, [S("summary", { onClick: n[9] ||= E((e) => ne("more", e), ["prevent"]) }, [...n[32] ||= [R("更多查询", -1), S("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [S("path", { d: "m4 6 4 4 4-4" })], -1)]]), S("div", Dn, [
							S("div", On, [n[33] ||= S("strong", null, "更多查询", -1), S("button", {
								type: "button",
								"aria-label": "关闭更多查询筛选",
								onClick: n[10] ||= (e) => q(e)
							}, "完成")]),
							S("label", kn, [n[34] ||= R("高级搜索", -1), S("input", {
								"data-query": "q",
								type: "search",
								value: P(u).query.q,
								placeholder: "如：协议 jp",
								autocomplete: "off",
								disabled: H.value,
								onInput: n[11] ||= (e) => P(a).setQueryField("q", G(e))
							}, null, 40, An)]),
							S("label", jn, [n[36] ||= R("归档范围", -1), S("select", {
								"data-query": "archived",
								value: P(u).query.archived,
								disabled: H.value,
								onChange: n[12] ||= (e) => P(a).setQueryField("archived", G(e))
							}, [...n[35] ||= [
								S("option", { value: "0" }, "未归档", -1),
								S("option", { value: "only" }, "仅归档", -1),
								S("option", { value: "all" }, "全部", -1)
							]], 40, Mn)])
						])], 40, En)
					]),
					S("div", Nn, [(i(!0), L(_, null, c(P(U), (e) => (i(), L("details", {
						key: e.key,
						class: D(["bulk-filter-popover", { "has-value": e.kind === "text" ? !!P(le)(P(u).query, e.key) : !!P(Y)(P(u).query, e.key).length }]),
						"data-filter-field": e.key,
						open: V.value === e.key,
						onFocusout: re
					}, [S("summary", { onClick: E((t) => ne(e.key, t), ["prevent"]) }, [
						R(b(e.label), 1),
						e.kind === "enum" && P(Y)(P(u).query, e.key).length ? (i(), L("span", In, b(P(Y)(P(u).query, e.key).length), 1)) : m("", !0),
						n[37] ||= S("svg", {
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [S("path", { d: "m4 6 4 4 4-4" })], -1)
					], 8, Fn), S("div", Ln, [S("div", Rn, [S("strong", null, b(e.label), 1), S("button", {
						type: "button",
						"aria-label": `关闭${e.label}筛选`,
						onClick: n[13] ||= (e) => q(e)
					}, "完成", 8, zn)]), e.kind === "text" ? (i(), L("label", Bn, [R(b(e.label), 1), S("input", {
						"data-query-filter": e.key,
						value: P(le)(P(u).query, e.key),
						inputmode: "numeric",
						placeholder: "输入账号 ID",
						disabled: H.value,
						onInput: (t) => P(a).setQueryField(e.key, G(t))
					}, null, 40, Vn)])) : (i(), L("div", Hn, [(i(!0), L(_, null, c(P(a).filterOptions(e.key), (t) => (i(), L("label", { key: t.value }, [S("input", {
						type: "checkbox",
						"data-query-filter": e.key,
						value: t.value,
						checked: P(Y)(P(u).query, e.key).includes(t.value),
						disabled: H.value,
						onChange: (n) => K(e.key, t.value, n.target.checked)
					}, null, 40, Un), S("span", null, b(t.label), 1)]))), 128)), P(a).filterOptions(e.key).length ? m("", !0) : (i(), L("span", Wn, "暂无可用选项"))]))])], 42, Pn))), 128))]),
					S("div", Gn, [(i(!0), L(_, null, c(P(z), (e) => (i(), L("button", {
						key: e.key,
						type: "button",
						class: "bulk-filter-chip",
						"data-clear-query": e.key,
						"aria-label": e.removeLabel,
						disabled: H.value,
						onClick: (t) => P(a).clearFilter(e.key)
					}, [R(b(e.label), 1), n[38] ||= S("span", { "aria-hidden": "true" }, "×", -1)], 8, Kn))), 128)), P(z).length ? m("", !0) : (i(), L("span", qn, "全部未归档账号"))])
				], 512), [[N, !P(u).source]])
			])
		]), S("aside", Jn, [S("div", Yn, [
			S("div", Xn, [S("div", null, [n[39] ||= S("span", { class: "bulk-side-kicker" }, "执行摘要", -1), S("strong", Zn, b(P(M)), 1)])]),
			S("div", Qn, b(P(A) == null ? P(u).source ? "创建时确认" : "匹配中" : `${P(A)} 个`), 1),
			S("p", $n, b(P(F)), 1),
			S("dl", er, [
				S("div", null, [n[40] ||= S("dt", null, "操作", -1), S("dd", tr, b(P(w)?.label || P(u).operation_key), 1)]),
				S("div", null, [n[41] ||= S("dt", null, "范围", -1), S("dd", nr, b(P(j)), 1)]),
				S("div", null, [n[42] ||= S("dt", null, "本批并发", -1), S("dd", rr, b(P(u).max_concurrency), 1)])
			]),
			P(A) != null && P(A) >= 200 ? (i(), L("p", ir, "本批将处理 " + b(P(A)) + " 个账号。", 1)) : m("", !0),
			P(h) ? (i(), L("p", ar, [R(b(P(h)), 1), P(x) ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "bulk-link",
				onClick: n[14] ||= (t) => e.deps.callbacks.navigate("detail", { batch_id: P(x) })
			}, "查看批次 #" + b(P(x)), 1)) : m("", !0)])) : m("", !0),
			P(k) ? (i(), L("div", or, [S("span", null, "有 " + b(P(k)) + " 个请求未收到回执，草稿已保留。", 1), S("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: H.value,
				onClick: n[15] ||= (...e) => P(a).recover && P(a).recover(...e)
			}, b(P(p) ? "正在找回…" : "找回原请求"), 9, sr)])) : m("", !0),
			S("div", cr, [S("button", {
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				"data-bulk-submit": "",
				disabled: H.value || P(A) === 0 || !P(C).length
			}, b(P(f) ? "正在创建批次…" : "创建并执行"), 9, lr), S("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "create-paused",
				disabled: H.value || P(A) === 0 || !P(C).length,
				onClick: n[16] ||= (e) => P(a).createBatch(!0)
			}, b(P(f) ? "正在创建批次…" : "创建并暂停"), 9, ur)]),
			n[43] ||= S("p", { class: "bulk-side-foot" }, "提交时固定账号范围，暂停后可继续原批次", -1),
			S("button", {
				type: "button",
				class: "bulk-side-back",
				"data-bulk-action": "list",
				onClick: n[17] ||= (t) => e.deps.callbacks.navigate("list")
			}, "← 返回批次列表")
		])])], 40, Jt));
	}
}), fr = {
	plan_check: "查套餐",
	token_refresh: "刷新 AT",
	password_setup: "补密码",
	twofa_setup: "补 2FA",
	codex_retry: "补 Codex",
	account_completion: "组合补全"
}, Z = (e) => typeof e == "object" && e && !Array.isArray(e) ? e : {}, pr = (e) => Array.isArray(e) ? e.map(Z) : [], mr = (e) => fr[String(e)] || String(e || "—");
function Q(e) {
	if (typeof e != "number" && (typeof e != "string" || !e.trim())) return null;
	let t = Number(e);
	return Number.isFinite(t) && t >= 0 ? t : null;
}
var $ = (e) => Q(e) === null ? "—" : Math.floor(Number(e)).toLocaleString("zh-CN");
function hr(e) {
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
function gr(e) {
	let t = Z(e.view);
	if (t.kind !== "round") return "当前结果 · 每个账号取最近一轮";
	let n = Q(t.round_no);
	return n === null || !Number.isSafeInteger(n) || n < 1 ? "所选轮次 · 固定名单" : n === 1 ? "首轮名单" : `重跑 ${n - 1} · 固定名单`;
}
var _r = {
	free: "Free",
	plus: "Plus",
	pro: "Pro",
	team: "Team",
	business: "Business",
	enterprise: "Enterprise",
	go: "Go",
	unknown: "尚未确认"
}, vr = {
	free_trial: "免费试用",
	half_price: "半价优惠",
	discount: "折扣优惠",
	other_discount: "其他折扣",
	other_promo: "其他优惠"
};
function yr(e, t, n) {
	let r = typeof t == "string" ? t : "";
	return Object.hasOwn(e, r) ? e[r] : r || n;
}
var br = (e) => yr(_r, e, "尚未确认"), xr = (e) => yr(vr, e, "其他优惠");
function Sr(e, t) {
	return `${Math.max(0, Math.min(100, t > 0 ? (Q(e) || 0) / t * 100 : 0))}%`;
}
var Cr = {
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
	...vr
})) Cr[`account.plus_offer.${e}`] = `优惠 · ${t}`;
for (let [e, t] of Object.entries({
	unchanged: "优惠未变化",
	new_offer: "新增优惠",
	offer_removed: "优惠消失",
	changed: "优惠变化",
	not_comparable: "历史条件不可比较"
})) Cr[`account.comparison.${e}`] = t;
for (let [e, t] of Object.entries({
	password: "密码",
	twofa: "2FA",
	codex: "Codex",
	access_token: "AT",
	plan_check: "套餐"
})) Cr[`step.${e}.confirmed`] = `${t} · 已完成`, Cr[`step.${e}.pending`] = `${t} · 待完成`;
function wr(e) {
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
			let e = yr(Cr, a, a), s = t ? `${t} · ${e}` : e;
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
var Tr = {
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
}, Er = [
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
], Dr = (e) => "is-" + (Er.includes(String(e)) ? "failed" : String(e || "preparing")), Or = (e) => Tr[Er.includes(String(e)) ? "failed" : String(e)] || String(e || "—"), kr = (e) => String(Z(e?.operation).key || e?.operation_key || e?.action_key || "");
function Ar(e) {
	let t = {};
	for (let [n, r] of Object.entries(Z(e))) {
		let e = Er.includes(n) ? "failed" : n;
		t[e] = (t[e] || 0) + (Q(r) || 0);
	}
	return t;
}
var jr = (e) => X(e.canonical_target_id || e.target_id || e.id);
function Mr(e) {
	return e == null || e === "" ? null : X(e);
}
function Nr(e) {
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
		let t = [`查询${Or(e.query_outcome)}`];
		return e.account_plan_type && t.push(`套餐 ${e.account_plan_type}`), e.confirmed_no_offer ? t.push("本次确认无优惠") : e.plus_offer_kind && e.plus_offer_kind !== "unknown" && t.push(xr(e.plus_offer_kind)), e.comparison && e.comparison !== "not_comparable" && t.push({
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
function Pr(e) {
	let t = Z(e.result), n = Z(t.result || e.result_summary || t), r = Z(e.reason || t.reason || e.error || e.error_info), i = Z(e.display_snapshot || e.display), a = Z(e.execution), o = pr(e.owned_runs)[0] || {}, s = jr(e), c = Mr(e.account_id || i.account_id || i.id || e.entity_id) || s, l = String(i.email || e.email || `账号 #${c}`), u = String(n.summary || n.message || e.result_label || e.summary_text || Nr(n) || "等待本轮结果"), d = String(r.summary || r.cause_summary || r.label || r.message || e.reason_label || e.reason_code || r.code || ""), f = [r.summary || r.cause_summary || r.message || e.error_message || d, r.display_code || r.code || e.reason_code].filter(Boolean).join("\n"), p = String(e.stage_label || e.current_stage_label || e.stage || "").trim(), m = Object.entries(Z(n.capabilities)).map(([e, t]) => `${mr(e)}：${Or(Z(t).state || Z(t).status)}`).join("\n"), h = e.state || e.outcome || e.status;
	return {
		id: s,
		accountId: c,
		account: l,
		summary: u,
		summaryShort: Fr(n, h, u),
		reason: d,
		reasonShort: d ? de({
			...r,
			code: r.code || e.reason_code
		}) === "执行异常" && [...d].length <= 10 ? d : de({
			...r,
			code: r.code || e.reason_code
		}) : "",
		reasonContent: f,
		stage: p,
		capabilities: m,
		state: Or(h),
		stateKey: h,
		taskId: Mr(e.task_id || e.owned_task_id || a.task_id || o.task_id),
		runId: Mr(e.owned_run_id || e.run_id || a.run_id || o.run_id),
		blockerTaskId: Mr(e.blocker_task_id)
	};
}
function Fr(e, t, n) {
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
	let r = Or(t);
	return [...r].length <= 10 && r !== "—" ? r : "结果见详情";
}
// src/features/bulk/useBulkDetail.ts
var Ir = [
	"failed",
	"partial_success",
	"not_executed",
	"cancelled"
];
function Lr(e, t, n = e().view === "detail") {
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
	function ee() {
		let e = new URLSearchParams({ view: r.value.round_id ? "round" : "current" });
		return r.value.round_id && e.set("round_id", X(r.value.round_id)), e;
	}
	function B(e = "") {
		return `/batches/${X(r.value.batch_id)}${e}`;
	}
	function V(e) {
		return e instanceof Error ? e.message : String(e);
	}
	function H(e) {
		let t = new Map(l.value.map((e) => [X(e.id), e]));
		if (Array.isArray(e)) for (let n of e) {
			let e = Z(n);
			t.set(X(e.id), e);
		}
		l.value = [...t.values()].sort((e, t) => Number(t.round_no) - Number(e.round_no));
	}
	let U = O(() => Ar(a.value?.summary || a.value?.counts)), te = O(() => Z(a.value?.control)), W = O(() => ["ended", "completed"].includes(String(te.value.state || a.value?.control_state))), G = O(() => !!(te.value.paused || a.value?.is_paused)), K = O(() => f.value.length > 0), q = O(() => s.value?.page?.has_more && s.value.page.next_cursor || null), ne = O(() => i.value && r.value.view === "detail" && (!W.value || !!m.value || !!te.value.pending)), re = O(() => Object.hasOwn(fr, kr(a.value)));
	function ie(e) {
		return !a.value || b.value || T.value || W.value || te.value.pending ? !0 : e === "pause" ? G.value : e === "resume" ? !G.value : Z(a.value.capabilities || Z(a.value.operation).capabilities)[e] === !1;
	}
	async function ae() {
		if (!i.value || r.value.view !== "detail") return;
		let e = L("targets");
		g.value = !0, S.value = "";
		try {
			let n = ee();
			n.set("page_size", "50"), r.value.cursor && n.set("cursor", r.value.cursor), r.value.result_state && n.set("state[]", r.value.result_state);
			let i = await t.api.request(`${B("/targets")}?${n}`, { signal: e.controller.signal });
			if (R("targets", e)) {
				for (let e of i.items) jr(e);
				s.value = i;
			}
		} catch (t) {
			R("targets", e) && (S.value = V(t));
		} finally {
			R("targets", e) && (g.value = !1);
		}
	}
	async function J(e = !1) {
		if (!i.value || r.value.view !== "detail" || !re.value || _.value) return;
		let n = W.value || Z(a.value?.selected_round).state === "completed", o = n && c.value?.phase === "completed" && c.value.summary_revision === a.value?.summary_revision;
		if (!e && (n && o || !n && (c.value || C.value) && t.now() - D < 1e4)) return;
		let s = L("report");
		_.value = !0, D = t.now();
		try {
			let e = await t.api.request(`${B("/report")}?${ee()}`, { signal: s.controller.signal });
			R("report", s) && (c.value = e, C.value = "", D = t.now());
		} catch (e) {
			R("report", s) && (C.value = V(e));
		} finally {
			R("report", s) && (_.value = !1);
		}
	}
	function oe(e = !1) {
		if (E || !i.value || r.value.view !== "detail" || !r.value.batch_id) return Promise.resolve();
		if (j && M === P()) return j;
		M = P();
		let t = se(e).finally(() => {
			j === t && (j = null, M = "");
		});
		return j = t, t;
	}
	async function se(e = !1) {
		if (E || !i.value || r.value.view !== "detail" || !r.value.batch_id) return;
		let n = L("detail");
		h.value = !0, x.value = "";
		try {
			let r = await t.api.request(`${B()}?${ee()}`, { signal: n.controller.signal });
			if (!R("detail", n)) return;
			let i = a.value?.summary_revision;
			if (a.value = r, H(r.rounds_head), r.selected_round && H([r.selected_round]), k || (u.value = typeof r.rounds_next_cursor == "string" ? r.rounds_next_cursor : null), m.value) {
				let e = l.value.find((e) => e.id === m.value);
				e && e.state !== "preparing" && (m.value = null, t.callbacks.notify(e.completion_reason === "cancelled_before_freeze" ? "重跑准备已取消，当前结果归属不变。" : "重跑名单已固定，可以切换查看新轮次。"));
			}
			let o = [J(e)];
			(e || !s.value || i !== r.summary_revision) && o.push(ae()), await Promise.all(o);
		} catch (e) {
			R("detail", n) && (x.value = V(e));
		} finally {
			R("detail", n) && (h.value = !1);
		}
	}
	async function ce() {
		if (!i.value || r.value.view !== "detail" || !u.value || v.value) return;
		let e = L("rounds");
		v.value = !0;
		try {
			let n = new URLSearchParams({
				page_size: "20",
				cursor: u.value
			}), r = await t.api.request(`${B("/rounds")}?${n}`, { signal: e.controller.signal });
			R("rounds", e) && (H(r.items), u.value = r.page.has_more && r.page.next_cursor || null, k = !0);
		} catch (t) {
			R("rounds", e) && (w.value = V(t));
		} finally {
			R("rounds", e) && (v.value = !1);
		}
	}
	function Y(e, n = !1) {
		n || (f.value = []), r.value = {
			...r.value,
			...e
		}, t.callbacks.updateNavigation(e);
	}
	async function le() {
		q.value && !g.value && (f.value.push(r.value.cursor || ""), Y({ cursor: q.value }, !0));
	}
	async function ue() {
		K.value && !g.value && Y({ cursor: f.value.pop() || "" }, !0);
	}
	async function de() {
		Y({ cursor: "" });
	}
	async function fe(e) {
		Y({
			result_state: e,
			cursor: ""
		});
	}
	async function pe(e) {
		Y({
			round_id: e === "current" ? "" : X(e),
			cursor: ""
		});
	}
	function me(e, t) {
		let n = new Set(d.value);
		t ? n.add(X(e)) : n.delete(e), d.value = n;
	}
	function he(e) {
		for (let t of s.value?.items || []) me(jr(t), e);
	}
	function ge() {
		d.value = /* @__PURE__ */ new Set();
	}
	function _e(e) {
		return (e === "unsuccessful" ? Ir : [e]).reduce((e, t) => e + (U.value[t] || 0), 0);
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
				e.kind === "retry" && (m.value = X(n.round_id || n.id), ge()), await oe(!0);
			} catch (t) {
				if (!E && e.navigationKey === I()) {
					w.value = V(t);
					let e = Z(t).code;
					["control_revision_conflict", "control_revision_changed"].includes(String(e)) && await oe(!0);
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
		if (!a.value || b.value || T.value || !Ir.includes(t) && t !== "unsuccessful") return;
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
					states: t === "unsuccessful" ? [...Ir] : [t]
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
		].includes(e) || ie(e)) return;
		let t = ["pause", "resume"].includes(e), n = e === "request_stop", i = X(r.value.batch_id), o = r.value.round_id ? X(r.value.round_id) : null, s = (n ? ["running", "waiting"] : [
			"pending_submit",
			"waiting_account",
			"queued",
			"waiting"
		]).reduce((e, t) => e + (U.value[t] || 0), 0), c = {
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
				expected_control_revision: te.value.revision ?? a.value?.control_revision,
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
		} : null, kr(a.value));
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
		T.value = null, w.value = "", !t || e[0] !== t[0] ? (z("detail", "targets", "report", "rounds"), a.value = null, s.value = null, c.value = null, l.value = [], u.value = null, k = !1, D = 0, C.value = "", S.value = "", h.value = !1, g.value = !1, _.value = !1, v.value = !1, ge(), f.value = [], m.value = null, oe()) : (e[1] !== t[1] && (ge(), f.value = []), s.value = null, ae());
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
		counts: U,
		ended: W,
		paused: G,
		needsPolling: ne,
		hasReport: re,
		hasPrevious: K,
		nextCursor: q,
		controlDisabled: ie,
		refresh: oe,
		loadTargets: ae,
		refreshReport: J,
		moreRounds: ce,
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
var Rr = {
	key: 0,
	class: "bulk-business-groups"
}, zr = { class: "bulk-business-metrics" }, Br = {
	key: 1,
	class: "bulk-report-empty"
}, Vr = /* @__PURE__ */ n({
	__name: "BulkBusinessStats",
	props: {
		metrics: {},
		groups: {}
	},
	setup(e) {
		let t = e, n = O(() => t.groups ?? wr(t.metrics));
		return (e, t) => n.value.length ? (i(), L("div", Rr, [(i(!0), L(_, null, c(n.value, (e) => (i(), L("section", {
			key: e.title,
			class: "bulk-business-group"
		}, [S("h4", null, b(e.title) + " · " + b(e.title === "国家查询项" ? "项" : "账号数"), 1), S("dl", zr, [(i(!0), L(_, null, c(e.items, (e) => (i(), L("div", { key: e.title }, [S("dt", null, b(e.title), 1), S("dd", null, b(P($)(e.value)), 1)]))), 128))])]))), 128))])) : (i(), L("p", Br, "暂无已确认的功能统计。"));
	}
}), Hr = ["aria-label"], Ur = { role: "status" }, Wr = {
	key: 1,
	class: "bulk-plan-report",
	"aria-labelledby": "bulkPlanReportTitle"
}, Gr = { class: "bulk-report-header" }, Kr = { class: "bulk-report-heading-line" }, qr = { id: "bulkPlanReportTitle" }, Jr = { class: "bulk-report-updated" }, Yr = {
	key: 0,
	class: "bulk-report-sync",
	role: "status"
}, Xr = { class: "bulk-report-outcomes" }, Zr = { class: "bulk-report-outcome-note" }, Qr = { class: "bulk-report-execution" }, $r = { "aria-label": "账号执行耗时" }, ei = { class: "bulk-report-section-head" }, ti = { class: "bulk-report-durations" }, ni = { class: "is-average" }, ri = { class: "bulk-report-note" }, ii = {
	key: 0,
	"aria-label": "AT 检查与自动刷新"
}, ai = { class: "bulk-report-at-causes" }, oi = { class: "bulk-report-at-results" }, si = { class: "bulk-report-note" }, ci = {
	key: 1,
	"aria-label": "功能统计"
}, li = {
	key: 1,
	class: "bulk-report-distributions"
}, ui = {
	class: "bulk-report-offers",
	"aria-label": "优惠结果"
}, di = { class: "bulk-report-offer-totals" }, fi = { class: "bulk-report-offer-list" }, pi = { class: "bulk-report-offer-line" }, mi = {
	class: "bulk-report-rail",
	"aria-hidden": "true"
}, hi = { class: "bulk-report-kind-list" }, gi = {
	key: 0,
	class: "bulk-report-empty"
}, _i = {
	class: "bulk-report-plans",
	"aria-label": "当前订阅套餐"
}, vi = { class: "bulk-report-plan-list" }, yi = {
	key: 0,
	class: "bulk-report-empty"
}, bi = {
	key: 2,
	class: "bulk-business-details"
}, xi = /* @__PURE__ */ n({
	__name: "BulkReport",
	props: {
		report: {},
		formatDateTime: { type: Function }
	},
	setup(e) {
		let t = e, n = O(() => Object.hasOwn(fr, String(t.report.operation_key))), r = O(() => Z(t.report.totals)), a = O(() => Z(t.report.duration)), o = O(() => Z(t.report.at_refresh)), s = O(() => Z(t.report.offers)), l = O(() => t.report.phase === "completed"), u = O(() => t.report.operation_key === "plan_check"), f = O(() => pr(t.report.plans).sort((e, t) => e.plan === "unknown" ? 1 : t.plan === "unknown" ? -1 : (Q(t.accounts) || 0) - (Q(e.accounts) || 0))), p = O(() => pr(s.value.by_plan).sort((e, t) => (Q(t.accounts) || 0) - (Q(e.accounts) || 0) || br(e.plan).localeCompare(br(t.plan)))), h = O(() => Math.max(0, ...f.value.map((e) => Q(e.accounts) || 0))), g = O(() => Math.max(0, ...p.value.map((e) => Q(e.accounts) || 0))), y = O(() => wr(t.report.business_summary)), x = [
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
			"aria-label": P(mr)(e.report.operation_key) + "报告"
		}, [S("h3", null, b(P(mr)(e.report.operation_key)) + "报告", 1), S("p", Ur, b(P(gr)(e.report)) + " · " + b(e.report.phase === "preparing" ? "账号名单准备中，固定后生成报告。" : "该轮名单未固定，无法生成账号统计。"), 1)], 8, Hr)) : n.value ? (i(), L("section", Wr, [
			S("header", Gr, [S("div", null, [S("div", Kr, [S("h3", qr, b(P(mr)(e.report.operation_key)) + b(l.value ? "完成报告" : "实时报告"), 1), S("span", { class: D(["bulk-report-phase", { "is-completed": l.value }]) }, b(l.value ? "已完成" : e.report.phase === "preparing" ? "名单准备中" : "统计更新中"), 3)]), S("p", null, b(P(gr)(e.report)) + " · " + b(P($)(r.value.accounts)) + " 个账号", 1)]), S("span", Jr, "更新于 " + b(e.formatDateTime(e.report.generated_at)), 1)]),
			P(Z)(e.report.projection).state && P(Z)(e.report.projection).state !== "current" ? (i(), L("p", Yr, b(P(Z)(e.report.projection).state === "failed" ? "结果汇总暂时失败，以下统计尚未收齐，请稍后刷新。" : "执行结果正在汇总，以下统计尚未收齐。"), 1)) : m("", !0),
			S("dl", Xr, [(i(), L(_, null, c(x, ([e, t, n]) => S("div", {
				key: t,
				class: D(["bulk-report-metric", n])
			}, [S("dt", null, b(e), 1), S("dd", null, [R(b(P($)(r.value[t])), 1), E[0] ||= S("span", null, "个", -1)])], 2)), 64))]),
			S("div", Zr, [
				S("span", null, "已结束 " + b(P($)(r.value.completed)) + " / " + b(P($)(r.value.accounts)) + " 个", 1),
				S("span", null, "未执行 " + b(P($)(r.value.not_executed)) + " 个", 1),
				S("span", null, "已取消 " + b(P($)(r.value.cancelled)) + " 个", 1)
			]),
			S("div", Qr, [S("section", $r, [
				S("div", ei, [E[1] ||= S("h4", null, "账号执行耗时", -1), S("span", null, "已结束样本 " + b(P($)(a.value.sample_count)) + " 个", 1)]),
				S("dl", ti, [
					S("div", ni, [E[2] ||= S("dt", null, "平均耗时", -1), S("dd", null, b(P(hr)(a.value.avg_seconds)), 1)]),
					S("div", null, [E[3] ||= S("dt", null, "最快", -1), S("dd", null, b(P(hr)(a.value.min_seconds)), 1)]),
					S("div", null, [E[4] ||= S("dt", null, "最慢", -1), S("dd", null, b(P(hr)(a.value.max_seconds)), 1)])
				]),
				S("p", ri, [R(" 从账号开始执行到结束，" + b(u.value ? "含自动刷新及链内等待" : "含链内等待") + "，不含开始前排队。", 1), (P(Q)(a.value.missing_count) || 0) > 0 ? (i(), L(_, { key: 0 }, [R(b(P($)(a.value.missing_count)) + " 个已结束账号缺少有效耗时，未计入均值。", 1)], 64)) : P(Q)(a.value.sample_count) === 0 ? (i(), L(_, { key: 1 }, [R(" 暂无有效耗时样本。")], 64)) : m("", !0)])
			]), u.value ? (i(), L("section", ii, [
				E[8] ||= S("div", { class: "bulk-report-section-head" }, [S("h4", null, "AT 检查与自动刷新"), S("span", null, "按账号去重")], -1),
				S("dl", ai, [(i(), L(_, null, c(C, ([e, t]) => S("div", {
					key: t,
					class: "bulk-report-minor"
				}, [S("dt", null, b(e), 1), S("dd", null, [R(b(P($)(o.value[t])), 1), E[5] ||= S("span", null, "个", -1)])])), 64))]),
				S("dl", oi, [(i(), L(_, null, c(w, ([e, t, n]) => S("div", {
					key: t,
					class: D(["bulk-report-minor", n])
				}, [S("dt", null, b(e), 1), S("dd", null, [R(b(P($)(o.value[t])), 1), E[6] ||= S("span", null, "个", -1)])], 2)), 64))]),
				S("p", si, [
					P(Q)(o.value.not_needed_accounts) === null ? m("", !0) : (i(), L(_, { key: 0 }, [R("未触发刷新 " + b(P($)(o.value.not_needed_accounts)) + " 个 · ", 1)], 64)),
					R("刷新状态待确认 " + b(P($)(o.value.unknown_accounts)) + " 个", 1),
					P(Q)(o.value.not_executed_accounts) === null ? m("", !0) : (i(), L(_, { key: 1 }, [R(" · 未开始执行 " + b(P($)(o.value.not_executed_accounts)) + " 个", 1)], 64)),
					E[7] ||= R("。待确认含执行中尚无结果及历史证据缺失；触发原因可能重叠，远端拒绝不等于本地过期。 ", -1)
				])
			])) : (i(), L("section", ci, [E[9] ||= S("div", { class: "bulk-report-section-head" }, [S("h4", null, "功能统计"), S("span", null, "当前查看范围")], -1), d(Vr, { groups: y.value }, null, 8, ["groups"])]))]),
			u.value ? (i(), L("div", li, [S("section", ui, [
				E[13] ||= S("div", { class: "bulk-report-section-head" }, [S("div", null, [S("h4", null, "优惠结果"), S("p", null, "统计本次查到的可用优惠，按账号去重")])], -1),
				S("dl", di, [(i(), L(_, null, c(T, ([e, t, n]) => S("div", {
					key: t,
					class: D(["bulk-report-metric", { "is-accent": t === "with_offer_accounts" }])
				}, [
					S("dt", null, b(e), 1),
					S("dd", null, [R(b(P($)(s.value[t])), 1), E[10] ||= S("span", null, "个", -1)]),
					S("small", null, b(n), 1)
				], 2)), 64))]),
				S("div", fi, [(i(!0), L(_, null, c(p.value, (e) => (i(), L("div", {
					key: String(e.plan),
					class: "bulk-report-offer-row"
				}, [
					S("div", pi, [S("strong", null, b(P(br)(e.plan)), 1), S("span", null, [S("b", null, b(P($)(e.accounts)), 1), E[11] ||= R(" 个账号", -1)])]),
					S("span", mi, [S("span", { style: v({ width: P(Sr)(e.accounts, g.value) }) }, null, 4)]),
					S("dl", hi, [(i(!0), L(_, null, c(P(pr)(e.kinds), (e) => (i(), L("div", { key: String(e.kind) }, [S("dt", null, b(P(xr)(e.kind)), 1), S("dd", null, [R(b(P($)(e.accounts)), 1), E[12] ||= S("span", null, "个", -1)])]))), 128))])
				]))), 128)), p.value.length ? m("", !0) : (i(), L("p", gi, b(P(Q)(s.value.with_offer_accounts) === 0 ? "本次尚未查到可用优惠。" : "暂无优惠套餐明细。"), 1))]),
				E[14] ||= S("p", { class: "bulk-report-note" }, "同一账号可符合多个套餐或优惠，分项数量可能重叠。", -1)
			]), S("section", _i, [
				E[16] ||= S("div", { class: "bulk-report-section-head" }, [S("div", null, [S("h4", null, "当前订阅套餐"), S("p", null, "本次查询确认的套餐状态")])], -1),
				S("dl", vi, [(i(!0), L(_, null, c(f.value, (e) => (i(), L("div", {
					key: String(e.plan),
					class: D({ "is-unknown": e.plan === "unknown" })
				}, [S("dt", null, b(P(br)(e.plan)), 1), S("dd", null, [S("span", null, [R(b(P($)(e.accounts)), 1), E[15] ||= S("small", null, "个", -1)]), S("span", {
					class: D(["bulk-report-rail", { "is-muted": e.plan === "unknown" }]),
					"aria-hidden": "true"
				}, [S("span", { style: v({ width: P(Sr)(e.accounts, h.value) }) }, null, 4)], 2)])], 2))), 128)), f.value.length ? m("", !0) : (i(), L("div", yi, "暂无套餐结果。"))]),
				E[17] ||= S("p", { class: "bulk-report-note" }, "“尚未确认”包含待完成、失败或缺少套餐记录的账号。", -1)
			])])) : m("", !0),
			u.value && y.value.length ? (i(), L("details", bi, [E[18] ||= S("summary", null, [R("更多查询统计"), S("span", null, "展开查看")], -1), d(Vr, { groups: y.value }, null, 8, ["groups"])])) : m("", !0)
		])) : m("", !0);
	}
}), Si = ["aria-label"], Ci = {
	key: 0,
	role: "status"
}, wi = {
	key: 2,
	class: "bulk-report-load-error"
}, Ti = {
	class: "bulk-error",
	role: "alert"
}, Ei = ["disabled"], Di = /* @__PURE__ */ n({
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
		let t = e, n = O(() => Object.hasOwn(fr, t.operationKey)), r = O(() => `${fr[t.operationKey]}报告`);
		return (t, a) => n.value ? (i(), L(_, { key: 0 }, [e.report && e.report.operation_key === e.operationKey ? (i(), x(xi, {
			key: 0,
			report: e.report,
			"format-date-time": e.formatDateTime
		}, null, 8, ["report", "format-date-time"])) : (i(), L("section", {
			key: 1,
			class: "bulk-plan-report bulk-report-placeholder",
			"aria-label": r.value
		}, [S("h3", null, b(r.value), 1), e.error ? m("", !0) : (i(), L("p", Ci, "正在汇总本次执行结果…"))], 8, Si)), e.error ? (i(), L("div", wi, [S("p", Ti, b(e.error), 1), S("button", {
			type: "button",
			class: "jobs-tb-btn",
			"data-bulk-action": "report-refresh",
			disabled: e.loading,
			onClick: a[0] ||= E((t) => e.onRetry(), ["stop"])
		}, " 重新读取报告 ", 8, Ei)])) : m("", !0)], 64)) : m("", !0);
	}
}), Oi = ["aria-busy"], ki = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, Ai = {
	class: "bulk-target-scroll",
	role: "region",
	"aria-label": "账号明细内容",
	tabindex: "0"
}, ji = { class: "bulk-table bulk-target-table" }, Mi = [
	"disabled",
	"checked",
	"indeterminate"
], Ni = { class: "bulk-target-filter" }, Pi = ["checked"], Fi = [
	"value",
	"checked",
	"onChange"
], Ii = ["data-bulk-row-target"], Li = {
	class: "bulk-target-check",
	"data-label": "选择"
}, Ri = [
	"data-bulk-target",
	"aria-label",
	"checked",
	"onChange"
], zi = {
	class: "bulk-target-id",
	"data-label": "ID"
}, Bi = ["aria-label", "onClick"], Vi = {
	class: "bulk-target-account",
	"data-label": "账号"
}, Hi = ["title", "onClick"], Ui = {
	class: "bulk-target-state",
	"data-label": "结果 / 阶段"
}, Wi = { class: "bulk-target-status-line" }, Gi = ["onClick"], Ki = {
	class: "bulk-target-summary",
	"data-label": "结果摘要"
}, qi = [
	"title",
	"aria-label",
	"onClick"
], Ji = {
	class: "bulk-target-reason",
	"data-label": "错误分类"
}, Yi = ["title", "onClick"], Xi = {
	class: "bulk-target-actions",
	"data-label": "操作"
}, Zi = { class: "bulk-target-action-line" }, Qi = ["onClick"], $i = { key: 1 }, ea = ["onClick"], ta = { key: 0 }, na = { colspan: "7" }, ra = {
	class: "bulk-empty",
	role: "status"
}, ia = {
	key: 0,
	class: "bulk-vue-result-details"
}, aa = /* @__PURE__ */ n({
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
		let r = e, s = n, u = y(null), f = A(r.items), p = O(() => f.value.map(Pr)), h = O(() => p.value.filter((e) => r.selected.has(e.id)).length), g = y(!1), v = O(() => [.../* @__PURE__ */ new Set([...r.resultStates, ...r.resultState ? [r.resultState] : []])]);
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
		function ee(e, t = null) {
			r.openTask(e, t);
		}
		return t({ close: I }), (t, n) => (i(), L(_, null, [S("div", {
			ref_key: "host",
			ref: u,
			class: "bulk-targets",
			"aria-busy": e.loading
		}, [e.error ? (i(), L("div", ki, [R(b(e.error) + " ", 1), S("button", {
			type: "button",
			class: "bulk-link",
			onClick: n[0] ||= (e) => s("retry")
		}, "重试读取明细")])) : m("", !0), S("div", Ai, [S("table", ji, [S("thead", null, [S("tr", null, [
			S("th", null, [S("input", {
				type: "checkbox",
				"data-select-page": "",
				"aria-label": "选择当前页目标",
				disabled: !p.value.length,
				checked: p.value.length > 0 && h.value === p.value.length,
				indeterminate: h.value > 0 && h.value < p.value.length,
				onChange: n[1] ||= (e) => s("selectPage", z(e))
			}, null, 40, Mi)]),
			n[7] ||= S("th", null, "ID", -1),
			n[8] ||= S("th", null, "账号", -1),
			S("th", null, [e.resultStates.length ? (i(), x(ne, {
				key: 0,
				label: "结果状态",
				"trigger-label": "结果 / 阶段",
				active: !!e.resultState,
				summary: P(Or)(e.resultState),
				open: g.value,
				"onUpdate:open": n[3] ||= (e) => g.value = e
			}, {
				default: a(() => [S("fieldset", Ni, [
					n[6] ||= S("legend", { class: "bulk-sr-only" }, "结果状态", -1),
					S("label", null, [
						S("input", {
							type: "radio",
							name: "bulk-target-state",
							value: "",
							checked: !e.resultState,
							onChange: n[2] ||= (e) => C("")
						}, null, 40, Pi),
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
						}, null, 40, Fi),
						S("span", null, b(P(Or)(t)), 1),
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
			S("td", Li, [S("input", {
				type: "checkbox",
				"data-bulk-target": t.id,
				"aria-label": "选择账号 " + t.account,
				checked: e.selected.has(t.id),
				onChange: (e) => s("toggle", t.id, z(e))
			}, null, 40, Ri)]),
			S("td", zi, [S("button", {
				type: "button",
				class: "bulk-cell-detail",
				"aria-label": "查看完整账号 ID：" + t.accountId,
				onClick: (e) => N(t, e)
			}, "#" + b(t.accountId), 9, Bi)]),
			S("td", Vi, [S("button", {
				type: "button",
				class: "bulk-cell-detail",
				title: t.account,
				onClick: (e) => N(t, e)
			}, b(t.account), 9, Hi)]),
			S("td", Ui, [S("div", Wi, [S("span", { class: D(["bulk-badge", P(Dr)(t.stateKey)]) }, b(t.state), 3), t.stage && !["—", "-"].includes(t.stage) ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "bulk-cell-detail bulk-target-stage",
				onClick: (e) => N(t, e)
			}, b(t.stage), 9, Gi)) : m("", !0)])]),
			S("td", Ki, [d(K, {
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
				}, b(t.summaryShort), 9, qi)]),
				_: 2
			}, 1032, ["text", "title"])]),
			S("td", Ji, [t.reason ? (i(), x(K, {
				key: 0,
				text: t.reasonShort,
				title: t.reason
			}, {
				default: a(() => [S("button", {
					type: "button",
					class: "bulk-cell-detail",
					title: t.reason,
					onClick: (e) => N(t, e)
				}, b(t.reasonShort), 9, Yi)]),
				_: 2
			}, 1032, ["text", "title"])) : (i(), L(_, { key: 1 }, [R("—")], 64))]),
			S("td", Xi, [S("div", Zi, [t.taskId ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-owned-task": "",
				onClick: (e) => ee(t.taskId, t.runId)
			}, "查看执行", 8, Qi)) : (i(), L("span", $i, "尚未创建执行")), t.blockerTaskId ? (i(), L("button", {
				key: 2,
				type: "button",
				class: "bulk-link",
				"data-blocker-task": "",
				title: "查看占用任务（其他执行）",
				onClick: (e) => ee(t.blockerTaskId)
			}, "查看占用", 8, ea)) : m("", !0)])])
		], 8, Ii))), 128)), p.value.length ? m("", !0) : (i(), L("tr", ta, [S("td", na, [S("div", ra, b(e.loading ? "正在读取账号明细…" : "当前条件下没有目标。更改结果筛选不会改变本批固定名单。"), 1)])]))])])])], 8, Oi), d(P(me), {
			open: k.value,
			"onUpdate:open": n[4] ||= (e) => k.value = e
		}, {
			default: a(() => [d(P(De), null, {
				default: a(() => [d(P(Ee), { class: "bulk-vue-overlay" }), d(P(Ce), {
					class: "bulk-vue-dialog",
					onCloseAutoFocus: F
				}, {
					default: a(() => [
						d(P(Oe), null, {
							default: a(() => [...n[12] ||= [R("账号执行详情", -1)]]),
							_: 1
						}),
						d(P(we), null, {
							default: a(() => [R(b(j.value?.account) + " · 账号 #" + b(j.value?.accountId), 1)]),
							_: 1
						}),
						j.value ? (i(), L("dl", ia, [
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
						d(P(he), {
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
}), oa = ["aria-busy"], sa = { class: "bulk-detail-page-heading" }, ca = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, la = {
	key: 1,
	class: "bulk-card bulk-overview"
}, ua = { class: "bulk-detail-toolbar" }, da = { class: "bulk-detail-meta" }, fa = { class: "bulk-settings bulk-detail-settings" }, pa = {
	key: 0,
	class: "bulk-projection-note"
}, ma = { class: "bulk-actions" }, ha = { class: "bulk-round-picker" }, ga = ["value"], _a = ["value"], va = ["value"], ya = ["disabled"], ba = ["disabled"], xa = { class: "bulk-control-strip" }, Sa = { class: "bulk-control-copy" }, Ca = { class: "bulk-actions" }, wa = [
	"data-bulk-action",
	"disabled",
	"onClick"
], Ta = { class: "bulk-view-note" }, Ea = { class: "bulk-summary-grid" }, Da = { class: "bulk-summary-item" }, Oa = { class: "bulk-summary-item" }, ka = { class: "bulk-summary-item is-success" }, Aa = { class: "bulk-summary-item is-warning" }, ja = ["aria-busy"], Ma = { class: "bulk-card bulk-results-card" }, Na = { class: "bulk-results-heading" }, Pa = ["disabled"], Fa = { class: "bulk-retry-toolbar" }, Ia = ["value"], La = ["disabled"], Ra = ["disabled"], za = {
	key: 0,
	class: "bulk-error",
	role: "alert"
}, Ba = {
	key: 1,
	class: "bulk-notice",
	role: "status"
}, Va = {
	class: "bulk-target-count-row",
	"data-bulk-target-count-row": ""
}, Ha = {
	class: "bulk-target-count",
	role: "status"
}, Ua = { class: "bulk-vue-dialog-actions" }, Wa = /*#__PURE__*/ F(/* @__PURE__ */ n({
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
		let r = e, l = Lr(() => r.navigation, r.deps, r.visible ?? r.navigation.view === "detail"), { navigation: u, detail: f, targets: p, report: g, rounds: v, roundsCursor: x, selected: C, pendingRound: w, loading: T, targetsLoading: E, reportLoading: k, roundsLoading: A, writing: j, error: M, targetError: N, reportError: F, actionError: I, confirmation: z, counts: ee, ended: B, paused: V, hasReport: H, hasPrevious: U, nextCursor: te } = l, W = y(null), G = y(null), K = y("failed"), q = O(() => [
			"success",
			"partial_success",
			"failed",
			"not_executed",
			"cancelled"
		].reduce((e, t) => e + (ee.value[t] || 0), 0)), ne = O(() => [
			"pending_submit",
			"waiting_account",
			"queued",
			"running",
			"waiting"
		].reduce((e, t) => e + (ee.value[t] || 0), 0)), ie = O(() => v.value.find((e) => e.id === u.value.round_id)), ae = O(() => !!(Z(f.value?.selection_summary).query || f.value?.query_spec || Z(f.value?.selection).query_spec)), J = [
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
		], oe = O(() => u.value.result_state ? [{
			key: "result_state",
			label: `结果状态：${Or(u.value.result_state)}`,
			title: `结果状态：${Or(u.value.result_state)}`,
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
		], Y = null;
		function le(e) {
			Y = e.currentTarget;
		}
		async function ue(e, t) {
			le(t), await l.retry(e, K.value);
		}
		async function de(e, t) {
			le(t), await l.control(e);
		}
		function fe(e) {
			e.preventDefault();
			let n = Y;
			Y = null, t(() => {
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
			await t(), G.value && (G.value.focus({ preventScroll: !0 }), G.value.scrollIntoView?.({ block: "start" })), !g.value && !k.value && await l.refreshReport(!0);
		}
		function me(e) {
			l.setVisible(e), e || (W.value?.close(), Y = null);
		}
		return o(() => r.visible, (e) => {
			e !== void 0 && me(e);
		}, { flush: "sync" }), o(() => [
			u.value.batch_id,
			u.value.round_id,
			u.value.result_state,
			u.value.view
		], () => {
			W.value?.close(), Y = null;
		}), n({
			refresh: l.refresh,
			showReport: pe,
			setVisible: me,
			needsRefresh: l.needsPolling
		}), (t, n) => (i(), L("div", {
			class: "bulk-detail-owner",
			"aria-busy": P(T)
		}, [
			S("header", sa, [S("div", null, [S("h2", null, b(P(f)?.name || P(f)?.title || "批次详情"), 1), S("p", null, b(P(mr)(P(kr)(P(f)))) + " · #" + b(P(u).batch_id), 1)]), P(H) ? (i(), L("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-bulk-action": "view-report",
				onClick: pe
			}, "查看报告")) : m("", !0)]),
			P(M) ? (i(), L("p", ca, [R(b(P(M)) + " ", 1), S("button", {
				type: "button",
				class: "bulk-link",
				onClick: n[0] ||= (e) => P(l).refresh(!0)
			}, "重试读取批次")])) : m("", !0),
			P(f) ? (i(), L("section", la, [
				S("div", ua, [S("div", da, [
					S("span", { class: D(["bulk-badge", P(Dr)(P(V) ? "paused" : P(Z)(P(f).control).state || P(f).control_state || P(f).state)]) }, b(P(Or)(P(V) ? "paused" : P(Z)(P(f).control).state || P(f).control_state || P(f).state)), 3),
					S("span", null, "创建于 " + b(e.deps.callbacks.formatDateTime(P(f).created_at)), 1),
					S("details", fa, [n[15] ||= S("summary", null, "范围与设置", -1), S("dl", null, [
						n[12] ||= S("dt", null, "名单生成", -1),
						S("dd", null, b(e.deps.callbacks.formatDateTime(P(Z)(P(f).selection_summary).selection_at || P(f).selection_at)), 1),
						n[13] ||= S("dt", null, "配置版本", -1),
						S("dd", null, b(P(Z)(P(f).effective_settings).config_revision || P(f).config_revision || "—"), 1),
						n[14] ||= S("dt", null, "结果更新", -1),
						S("dd", null, b(e.deps.callbacks.formatDateTime(P(f).projected_at)), 1)
					])]),
					P(Z)(P(f).projection).state && P(Z)(P(f).projection).state !== "current" ? (i(), L("span", pa, "汇总同步中")) : m("", !0)
				]), S("div", ma, [
					S("label", ha, [n[17] ||= S("span", { class: "bulk-sr-only" }, "结果视图", -1), S("select", {
						value: P(u).round_id || "current",
						"aria-label": "结果视图",
						onChange: n[1] ||= (e) => P(l).setRound(e.target.value)
					}, [
						n[16] ||= S("option", { value: "current" }, "当前结果", -1),
						(i(!0), L(_, null, c(P(v), (e) => (i(), L("option", {
							key: String(e.id),
							value: String(e.id)
						}, b(Number(e.round_no) === 1 ? "首轮" : "重跑 " + (Number(e.round_no) - 1)) + " · " + b(P(Or)(e.state)) + " · " + b(e.target_count == null ? "准备中" : P($)(e.target_count) + " 个"), 9, _a))), 128)),
						P(u).round_id && !ie.value ? (i(), L("option", {
							key: 0,
							value: P(u).round_id
						}, "所选轮次 #" + b(P(u).round_id), 9, va)) : m("", !0)
					], 40, ga)]),
					S("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "more-rounds",
						disabled: !P(x) || P(A),
						onClick: n[2] ||= (...e) => P(l).moreRounds && P(l).moreRounds(...e)
					}, "更多轮次", 8, ya),
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
						disabled: !ae.value,
						onClick: n[4] ||= (e) => P(l).copyBatch(!1)
					}, "复制条件新建", 8, ba)
				])]),
				S("div", xa, [S("div", Sa, [n[18] ||= S("strong", null, "运行控制", -1), S("span", null, b(P(B) ? "批次已结束" : P(V) ? "批次已暂停，尚未开始的账号等待继续；已开始账号继续收尾" : ne.value + " 个进行中 · 已结束 " + q.value + " / " + P($)(P(f).target_count)), 1)]), S("div", Ca, [(i(), L(_, null, c(ce, ([e, t, n]) => S("button", {
					key: e,
					type: "button",
					class: D(["jobs-tb-btn", { "jobs-tb-btn--danger": ["cancel", "stop"].includes(n) }]),
					"data-bulk-action": n,
					disabled: P(l).controlDisabled(e),
					onClick: (t) => de(e, t)
				}, b(t), 11, wa)), 64))])]),
				S("p", Ta, b(ie.value?.completion_reason === "cancelled_before_freeze" ? "本轮在名单生成前取消，当前结果未改变。" : P(u).round_id ? "仅展示该轮名单及执行结果。" : "已结束 " + q.value + " / " + P($)(P(f).target_count) + " 个 · 每个账号保留最近一轮结果"), 1),
				P(H) ? m("", !0) : (i(), L(_, { key: 0 }, [S("div", Ea, [
					S("div", Da, [n[19] ||= S("span", null, "账号总数", -1), S("strong", null, b(P($)(P(f).target_count)), 1)]),
					S("div", Oa, [n[20] ||= S("span", null, "进行中", -1), S("strong", null, b(ne.value), 1)]),
					S("div", ka, [n[21] ||= S("span", null, "成功", -1), S("strong", null, b(P(ee).success || 0), 1)]),
					S("div", Aa, [n[22] ||= S("span", null, "未成功", -1), S("strong", null, b(P(l).retryCount("unsuccessful")), 1)])
				]), d(Vr, { metrics: P(f).business_summary || P(f).metrics }, null, 8, ["metrics"])], 64))
			])) : m("", !0),
			P(H) ? (i(), L("section", {
				key: 2,
				ref_key: "reportRegion",
				ref: G,
				"data-bulk-plan-report": "",
				class: "bulk-report-target",
				tabindex: "-1",
				role: "region",
				"aria-label": "批次报告",
				"aria-busy": P(k)
			}, [d(Di, {
				"operation-key": P(kr)(P(f)),
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
			])], 8, ja)) : m("", !0),
			S("section", Ma, [
				S("div", Na, [S("h3", null, [
					n[23] ||= R("账号明细 ", -1),
					S("span", null, b(P(C).size ? "已选 " + P(C).size + " 个（可跨页）" : ""), 1),
					S("button", {
						type: "button",
						class: "bulk-link",
						disabled: !P(C).size,
						onClick: n[5] ||= (...e) => P(l).clearSelection && P(l).clearSelection(...e)
					}, "清空选择", 8, Pa)
				]), S("div", Fa, [
					s(S("select", {
						"onUpdate:modelValue": n[6] ||= (e) => K.value = e,
						"aria-label": "重跑范围"
					}, [(i(), L(_, null, c(se, ([e, t]) => S("option", {
						key: e,
						value: e
					}, b(t), 9, Ia)), 64))], 512), [[h, K.value]]),
					S("button", {
						type: "button",
						class: "jobs-tb-btn jobs-tb-btn--primary",
						"data-bulk-action": "retry",
						disabled: P(j) || !!P(z) || !P(l).retryCount(K.value),
						onClick: n[7] ||= (e) => ue(!1, e)
					}, "重跑" + b(se.find((e) => e[0] === K.value)?.[1]) + " (" + b(P(l).retryCount(K.value)) + ")", 9, La),
					S("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-bulk-action": "retry-selected",
						disabled: P(j) || !!P(z) || !P(C).size,
						onClick: n[8] ||= (e) => ue(!0, e)
					}, "重跑勾选" + b(P(C).size ? " (" + P(C).size + ")" : ""), 9, Ra)
				])]),
				P(I) ? (i(), L("p", za, b(P(I)), 1)) : m("", !0),
				P(w) ? (i(), L("p", Ba, "重跑已受理，正在准备新轮次 #" + b(P(w)) + "。", 1)) : m("", !0),
				S("div", Va, [S("span", Ha, "共 " + b(P($)(P(f)?.target_count)) + " 个账号 · 当前页 " + b(P(p)?.items.length || 0) + " 个", 1), d(re, {
					items: oe.value,
					onRemove: n[9] ||= (e) => P(l).setFilter("")
				}, null, 8, ["items"])]),
				d(aa, {
					ref_key: "targetTable",
					ref: W,
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
					"result-counts": P(ee),
					"result-total": P(f)?.target_count,
					"result-states": J,
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
				d(Ge, {
					"has-previous": P(U),
					"next-cursor": P(te),
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
			d(P(Ie), {
				open: !!P(z),
				"onUpdate:open": n[11] ||= (e) => {
					e || P(l).cancelConfirmation();
				}
			}, {
				default: a(() => [d(P(Fe), null, {
					default: a(() => [d(P(Pe), { class: "bulk-vue-overlay" }), d(P(je), {
						class: "bulk-vue-dialog",
						onCloseAutoFocus: fe
					}, {
						default: a(() => [
							d(P(Le), null, {
								default: a(() => [R(b(P(z)?.title), 1)]),
								_: 1
							}),
							d(P(Ne), null, {
								default: a(() => [R(b(P(z)?.description), 1)]),
								_: 1
							}),
							S("p", null, "范围：" + b(P(z)?.scopeLabel) + " · 预计账号：" + b(P(z)?.count) + " 个", 1),
							S("div", Ua, [d(P(Me), {
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
		], 8, oa));
	}
}), [["__scopeId", "data-v-d412d46e"]]), Ga = [
	"batch_id",
	"round_id",
	"result_state",
	"cursor",
	"q",
	"operation",
	"state",
	"created_from",
	"created_to"
], Ka = /* @__PURE__ */ new Set([
	"attention_required",
	"request_unknown",
	"manual_reconcile",
	"unknown",
	"unconfirmed"
]);
function qa(e = {}) {
	let t = [
		"list",
		"create",
		"detail"
	].includes(e.view || "") ? e.view : "list", n = {
		tab: "bulk",
		view: t
	};
	for (let t of Ga) typeof e[t] == "string" && e[t] && (n[t] = e[t]);
	if (t === "detail") {
		if (!/^[1-9]\d*$/.test(n.batch_id || "")) return {
			tab: "bulk",
			view: "list"
		};
		(n.q || e.reason_code) && (delete n.q, delete n.cursor), n.result_state && Ka.has(n.result_state) && (n.result_state = "failed");
	}
	return n;
}
// src/features/bulk/BulkPageShell.vue?vue&type=script&setup=true&lang.ts
var Ja = {
	class: "bulk-page bulk-page-shell",
	"data-bulk-vue": ""
}, Ya = { class: "bulk-page-heading" }, Xa = { "data-bulk-title": "" }, Za = { class: "bulk-actions" }, Qa = {
	key: 0,
	class: "bulk-error",
	"data-bulk-error": "",
	role: "alert"
}, $a = {
	key: 1,
	class: "bulk-notice",
	"data-bulk-notice": "",
	role: "status"
}, eo = {
	key: 2,
	class: "bulk-notice bulk-global-recovery",
	"data-bulk-recovery": "",
	role: "status"
}, to = ["disabled"], no = { "data-bulk-content": "" }, ro = /*#__PURE__*/ F(/* @__PURE__ */ n({
	__name: "BulkPageShell",
	props: {
		deps: {},
		initialNavigation: {}
	},
	setup(e, { expose: n }) {
		let r = e, a = A(qa(r.initialNavigation)), c = y(!1), u = y(!1), f = y(""), p = y(""), h = y(!1), g = y(0), _ = A(null), v = y(null), x = y(null), C = y(null), T = !1, E = 0, D = 0, k = !1, j, M = null, P = "", F = !1, I = O(() => c.value && u.value), R = {
			...r.deps.callbacks,
			navigate: (e, t, n) => {
				J(e, t, n);
			},
			updateNavigation: (e) => {
				oe(e);
			},
			notify: (e) => {
				p.value = e, g.value++, r.deps.callbacks.notify(e);
			},
			copyBatch: (e, t, n) => {
				se(e, t, n);
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
		}, ee = {
			api: r.deps.api,
			callbacks: R
		}, B = {
			...r.deps,
			intents: z,
			callbacks: R
		}, V = {
			api: r.deps.api,
			intents: z,
			callbacks: R,
			now: r.deps.now
		}, H = O(() => {
			g.value;
			try {
				return r.deps.intents.pending();
			} catch {
				return [];
			}
		}), U = O(() => I.value ? a.value.view === "list" ? 7e3 : a.value.view === "create" ? x.value?.needsRefresh ? 2e3 : 0 : C.value?.needsRefresh ? 2e3 : 0 : 0), te = O(() => a.value.view === "list" ? "批量任务" : a.value.view === "create" ? "新建批次" : `批次 #${a.value.batch_id}`);
		function W() {
			u.value = !document.hidden && (r.deps.isVisible?.() ?? !0), k !== I.value && (D++, k = I.value), v.value?.setVisible(I.value && a.value.view === "list"), x.value?.setVisible(I.value && a.value.view === "create"), C.value?.setVisible(I.value && a.value.view === "detail");
		}
		function G() {
			clearTimeout(j), j = void 0, !T && U.value && (j = setTimeout(() => {
				j = void 0, W(), I.value && K(!1);
			}, U.value));
		}
		async function K(e = !0) {
			if (await t(), T || (W(), !I.value)) return;
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
				M === r && (M = null, P = ""), G();
			}
		}
		async function q() {
			c.value = !0, await K(!1);
		}
		async function ne() {
			a.value.view === "detail" && (F = !0, await K(!1));
		}
		function re(e) {
			c.value = e, W(), G();
		}
		function ie() {
			return { ...a.value };
		}
		function ae(e) {
			E++, a.value = qa(e), f.value = "", p.value = "", F = !1;
		}
		async function J(e, t = {}, n = !1) {
			ae({
				tab: "bulk",
				view: e,
				...t
			}), F = n, c.value = !0, r.deps.onNavigation(ie(), "push"), await K(!1);
		}
		async function oe(e) {
			E++, a.value = qa({
				...a.value,
				...e
			}), r.deps.onNavigation(ie(), Object.keys(e).every((e) => e === "cursor") ? "replace" : "push"), await t(), G();
		}
		async function se(e, t, n = "plan_check") {
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
			}, await J("create");
		}
		async function ce(e = !1, t = "plan_check", n) {
			if (!n) {
				R.notify("账号范围未就绪，请返回账号页重试");
				return;
			}
			let r = e ? n.ids.map((e) => X(typeof e == "number" && Number.isSafeInteger(e) ? String(e) : e)) : [];
			e && !r.length ? R.notify("请先选择账号") : await se(n.query, e ? {
				kind: "ids",
				entity: "account",
				ids: r
			} : null, t);
		}
		async function Y() {
			await se(r.deps.adapter.normalize(), null);
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
				if (t.path === "/selections") _.value = null, await le(t.body, n), await J("create"), R.notify("已找回原账号范围，新批次使用配置页已保存的设置。");
				else if (t.path === "/batches") {
					try {
						r.deps.storage.removeItem("turb_bulk_selection_v1");
					} catch {}
					await J("detail", { batch_id: X(n.id || n.batch_id) });
				} else {
					let e = t.path.match(/^\/batches\/([1-9]\d*)\//);
					e && await J("detail", { batch_id: e[1] }), R.notify("原请求回执已找回。");
				}
			} catch (e) {
				f.value = e instanceof Error ? e.message : String(e);
			} finally {
				h.value = !1, g.value++;
			}
		}
		function de() {
			let e = I.value;
			W(), !e && I.value ? K(!1) : G();
		}
		return o(U, G, { flush: "post" }), l(() => {
			W(), document.addEventListener("visibilitychange", de);
		}), w(() => {
			T = !0, clearTimeout(j), document.removeEventListener("visibilitychange", de);
		}), n({
			activate: q,
			setVisible: re,
			refresh: K,
			showReport: ne,
			navigationState: ie,
			restoreNavigation: ae,
			navigate: J,
			fromAccounts: ce,
			recover: ue,
			restoreSelectionRequest: le
		}), (e, t) => (i(), L("div", Ja, [
			S("header", Ya, [S("h2", Xa, b(te.value), 1), S("div", Za, [
				a.value.view === "list" ? m("", !0) : (i(), L("button", {
					key: 0,
					type: "button",
					class: "jobs-tb-btn",
					onClick: t[0] ||= (e) => J("list")
				}, "批次列表")),
				S("button", {
					type: "button",
					class: "jobs-tb-btn",
					"data-bulk-action": "refresh",
					onClick: t[1] ||= (e) => K(!0)
				}, "刷新"),
				S("button", {
					type: "button",
					class: "jobs-tb-btn jobs-tb-btn--primary",
					"data-bulk-action": "new",
					onClick: Y
				}, "新建批次")
			])]),
			f.value ? (i(), L("p", Qa, b(f.value), 1)) : m("", !0),
			p.value ? (i(), L("p", $a, b(p.value), 1)) : m("", !0),
			H.value.length && a.value.view !== "create" ? (i(), L("div", eo, [S("span", null, "有 " + b(H.value.length) + " 个请求未收到回执，草稿已保留。", 1), S("button", {
				type: "button",
				class: "jobs-tb-btn",
				disabled: h.value,
				onClick: ue
			}, b(h.value ? "正在找回…" : "找回原请求"), 9, to)])) : m("", !0),
			S("div", no, [
				s(d(zt, {
					ref_key: "list",
					ref: v,
					navigation: a.value,
					deps: ee
				}, null, 8, ["navigation"]), [[N, a.value.view === "list"]]),
				s(d(dr, {
					ref_key: "create",
					ref: x,
					navigation: a.value,
					deps: B,
					seed: _.value,
					visible: I.value && a.value.view === "create"
				}, null, 8, [
					"navigation",
					"seed",
					"visible"
				]), [[N, a.value.view === "create"]]),
				s(d(Wa, {
					ref_key: "detail",
					ref: C,
					navigation: a.value,
					deps: V,
					visible: I.value && a.value.view === "detail"
				}, null, 8, ["navigation", "visible"]), [[N, a.value.view === "detail"]])
			])
		]));
	}
}), [["__scopeId", "data-v-32a8fcf3"]]), io = "turb_bulk_intent:", ao = /* @__PURE__ */ new Set([
	400,
	403,
	404,
	409,
	410,
	422,
	429
]);
function oo(e, t, n) {
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
		let c = io + a, l = JSON.stringify({
			path: o,
			body: s
		}), u = r.get(c);
		if (u) {
			if (u.signature !== l) throw new Bt("上一请求未收到回执，请先找回原请求，再提交新内容。", 0, "request_receipt_pending");
			return u.promise;
		}
		let d = i(c, t.getItem(c));
		if (d && d.signature !== l) throw new Bt("上一请求未收到回执，请先找回原请求，再提交新内容。", 0, "request_receipt_pending");
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
			if (ao.has(Number(e?.status))) try {
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
				if (r?.startsWith(io)) {
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
function so(e, t) {
	e.replaceChildren();
	function n(t) {
		M(r(Di, { ...t }), e);
	}
	return n(t), {
		setView: n,
		destroy() {
			M(null, e);
		}
	};
}
// src/bulk.ts
var co = /* @__PURE__ */ new WeakMap();
function lo(e, t) {
	let n = co.get(e);
	if (n) return n;
	let r = uo(e, t);
	return co.set(e, r), r;
}
function uo(e, t) {
	let n = Vt(), r = {
		get length() {
			return window.sessionStorage.length;
		},
		key: (e) => window.sessionStorage.key(e),
		getItem: (e) => window.sessionStorage.getItem(e),
		setItem: (e, t) => window.sessionStorage.setItem(e, t),
		removeItem: (e) => window.sessionStorage.removeItem(e)
	}, i = oo(n, r, () => globalThis.crypto?.randomUUID?.() || `bulk-${Date.now()}-${Math.random().toString(36).slice(2)}`), a = k(ro, {
		initialNavigation: t.navigation,
		deps: {
			api: n,
			intents: i,
			storage: r,
			adapter: ue(t.query),
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
			a.unmount(), co.delete(e);
		}
	});
}
function fo(e, i) {
	let a = A(i.view), o = A(), s = k(n({ setup: () => () => r(zt, {
		ref: o,
		navigation: a.value,
		deps: {
			api: Vt(),
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
export { lo as mountBulk, fo as mountBulkList, so as mountBulkReport };
