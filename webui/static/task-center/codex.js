import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, Q as s, S as c, V as l, Z as u, _ as d, c as f, d as p, dt as m, et as h, ft as g, g as _, h as v, j as y, k as b, l as x, lt as S, m as C, n as w, s as T, st as E, v as D, x as O } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { a as k, c as A, i as j, n as M, o as N, r as P, s as F, t as I } from "./ListFilterSummary-CrfopumJ.js";
import { t as L } from "./ListPagination-DDdERjeb.js";
import { n as R, t as z } from "./ColumnResizer-Le9iLnsr.js";
import { t as B } from "./time-DOD6oyhP.js";
import { n as V, r as H, t as U } from "./client-B5R_MNgP.js";
// src/features/codex/filterDefinitions.ts
var W = [
	{
		key: "q",
		label: "邮箱 / 文件",
		fields: ["q"],
		kind: "text",
		placeholder: "邮箱、文件名或 Sub2API ID"
	},
	{
		key: "plan",
		label: "Plan",
		fields: ["plan"],
		kind: "enum"
	},
	{
		key: "status",
		label: "状态",
		fields: ["status"],
		kind: "enum"
	},
	{
		key: "oauth_status",
		label: "OAuth 状态",
		fields: ["oauth_status"],
		kind: "enum"
	},
	{
		key: "account_id",
		label: "Account ID",
		fields: ["account_id"],
		kind: "text",
		placeholder: "输入 Account ID"
	},
	{
		key: "sub2api_id",
		label: "Sub2API ID",
		fields: ["sub2api_id"],
		kind: "text",
		placeholder: "输入 Sub2API ID"
	},
	{
		key: "date",
		label: "更新时间",
		fields: ["date_from", "date_to"],
		kind: "date-range"
	},
	{
		key: "expired_date",
		label: "过期时间",
		fields: ["expired_date"],
		kind: "date"
	}
], G = {
	status: {
		exported: "已导出",
		unexported: "未导出",
		archived: "已归档"
	},
	oauth_status: {
		valid: "有效",
		expiring: "即将过期",
		expired: "已过期",
		missing: "缺少令牌",
		unknown: "未知",
		deactivated: "账号停用"
	}
};
function K(e, t) {
	return e === "plan" ? t === "unqueried" ? "未查询" : t ? t.charAt(0).toUpperCase() + t.slice(1) : "-" : G[e]?.[t] || t || "-";
}
function q(e, t) {
	return W.flatMap((n) => {
		let r = e[n.fields[0]];
		if (n.kind === "date-range") {
			let t = e.date_from, n = e.date_to;
			r = t && n ? `${t} 至 ${n}` : t ? `自 ${t}` : n ? `截至 ${n}` : "";
		} else n.kind === "enum" && r && (r = t[n.key]?.find((e) => e.value === r)?.label || K(n.key, r));
		if (!r) return [];
		let i = `${n.label}：${r}`;
		return [{
			key: n.key,
			label: i,
			title: i,
			removeLabel: `清除${n.label}筛选`
		}];
	});
}
function J(e, t) {
	let n = { ...e };
	for (let e of W.find((e) => e.key === t)?.fields || []) n[e] = "";
	return n;
}
// src/features/codex/CodexFilters.vue?vue&type=script&setup=true&lang.ts
var Y = { class: "cx-filter-fields" }, X = {
	key: 0,
	class: "cx-filter-field"
}, ee = {
	class: "list-filter-options",
	role: "radiogroup",
	"aria-label": "选择筛选列"
}, te = ["data-filter-value"], ne = [
	"name",
	"value",
	"checked",
	"onChange"
], re = {
	key: 1,
	class: "list-filter-options"
}, ie = { class: "cx-sr-only" }, ae = { class: "list-filter-option" }, oe = ["name", "checked"], se = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], ce = [
	"type",
	"aria-label",
	"value",
	"placeholder",
	"onInput"
], le = { class: "list-filter-actions" }, ue = /* @__PURE__ */ t({
	__name: "CodexFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean },
		column: {}
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, a = t, s = h("q"), u = l();
		function m(e) {
			s.value = e;
		}
		let _ = C(() => i.column || W.find((e) => e.key === s.value) || W[0]), y = C(() => i.column ? i.column.fields.some((e) => !!i.modelValue[e]) : Object.values(i.modelValue).some(Boolean)), b = C(() => q(i.modelValue, i.facets).find((e) => e.key === _.value.key)?.label || ""), w = C(() => {
			let e = _.value.fields[0], t = (i.facets[_.value.key] || []).filter((e) => _.value.key !== "status" || e.value !== "archived"), n = i.modelValue[e], r = t.filter((e) => Number(e.count) > 0 || e.value === n).map((e) => ({
				...e,
				label: e.label || K(_.value.key, e.value)
			}));
			return n && !r.some((e) => e.value === n) && r.unshift({
				value: n,
				label: K(_.value.key, n),
				count: 0
			}), r;
		});
		function T(e, t) {
			a("update:modelValue", {
				...i.modelValue,
				[e]: t
			});
		}
		function k() {
			a("update:modelValue", J(i.modelValue, _.value.key)), a("update:open", !1);
		}
		function A(e, t, n) {
			e.detail <= 0 || (T(t, n), a("update:open", !1));
		}
		return (t, i) => (n(), D("div", { class: S({ "cx-all-filters": !e.column }) }, [c(j, {
			label: e.column?.label || "凭证",
			"trigger-label": e.column ? void 0 : "筛选",
			active: y.value,
			summary: b.value,
			open: e.open,
			"onUpdate:open": i[4] ||= (e) => a("update:open", e)
		}, {
			default: r(() => [v("div", Y, [
				e.column ? d("", !0) : (n(), D("div", X, [i[5] ||= O("筛选列", -1), v("div", ee, [(n(!0), D(p, null, o(E(W), (e) => (n(), D("label", {
					key: e.key,
					class: "list-filter-option",
					"data-filter-value": e.key
				}, [v("input", {
					type: "radio",
					name: `${E(u)}-column`,
					value: e.key,
					checked: s.value === e.key,
					onChange: (t) => m(e.key)
				}, null, 40, ne), v("span", null, g(e.label), 1)], 8, te))), 128))])])),
				_.value.kind === "enum" ? (n(), D("fieldset", re, [
					v("legend", ie, g(_.value.label), 1),
					v("label", ae, [v("input", {
						type: "radio",
						name: E(u),
						value: "",
						checked: !e.modelValue[_.value.fields[0]],
						onChange: i[0] ||= (e) => T(_.value.fields[0], ""),
						onClick: i[1] ||= (e) => A(e, _.value.fields[0], "")
					}, null, 40, oe), i[6] ||= v("span", null, "全部", -1)]),
					(n(!0), D(p, null, o(w.value, (t) => (n(), D("label", {
						class: "list-filter-option",
						key: t.value
					}, [
						v("input", {
							type: "radio",
							name: E(u),
							value: t.value,
							checked: e.modelValue[_.value.fields[0]] === t.value,
							onChange: (e) => T(_.value.fields[0], t.value),
							onClick: (e) => A(e, _.value.fields[0], t.value)
						}, null, 40, se),
						v("span", null, g(t.label), 1),
						v("small", null, g(t.count), 1)
					]))), 128))
				])) : (n(!0), D(p, { key: 2 }, o(_.value.fields, (t, r) => (n(), D("label", {
					key: t,
					class: "cx-filter-field"
				}, [O(g(_.value.kind === "date-range" ? r ? "截止日期" : "开始日期" : _.value.label) + " ", 1), v("input", {
					type: _.value.kind === "text" ? "text" : "date",
					"aria-label": _.value.kind === "date-range" ? r ? "截止日期" : "开始日期" : _.value.label,
					value: e.modelValue[t],
					placeholder: _.value.placeholder,
					autocomplete: "off",
					onInput: (e) => T(t, e.target.value),
					onKeydown: i[2] ||= f(x((e) => a("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, ce)]))), 128)),
				v("div", le, [v("button", {
					type: "button",
					onClick: k
				}, "清除此列"), v("button", {
					type: "button",
					class: "list-filter-primary",
					onClick: i[3] ||= (e) => a("update:open", !1)
				}, "完成")])
			])]),
			_: 1
		}, 8, [
			"label",
			"trigger-label",
			"active",
			"summary",
			"open"
		])], 2));
	}
});
// src/features/codex/presentation.ts
function de(e) {
	let t = Number(e.exported_count || 0), n = Number(e.sub2_uploaded_count || 0);
	if (n > 0) {
		let r = [`Sub2API 已上传 ${n} 次，最近 ${e.sub2_uploaded_at || "-"}`];
		return t > 0 && r.push(`导出记录 ${t} 次，最近 ${e.exported_at || "-"}`), {
			label: "已导出",
			title: r.join("；"),
			tone: "success"
		};
	}
	let r = e.exported === !0 || t > 0, i = e.sub2api_account_id != null && String(e.sub2api_account_id).trim() !== "";
	return r && t <= 0 && i ? {
		label: "已关联",
		title: `Sub2API ID ${e.sub2api_account_id} 已有关联记录，本地下载 0 次`,
		tone: "success"
	} : r ? {
		label: "已导出",
		title: `导出 ${t} 次，最近 ${e.exported_at || "-"}`,
		tone: "success"
	} : {
		label: "未导出",
		title: "没有本地导出或 Sub2API 关联记录",
		tone: "neutral"
	};
}
function fe(e) {
	let t = String(e.oauth_status || "unknown"), n = Number(e.sub2api_http_status), r = e.oauth_seconds_left == null ? NaN : Number(e.oauth_seconds_left), i = Number.isFinite(r) ? `${r < 0 ? "已过期" : "剩余"} ${Math.floor(Math.abs(r) / 86400)}天${Math.floor(Math.abs(r) % 86400 / 3600)}小时` : "", a = [
		n ? `Sub2API HTTP ${n}` : "",
		e.oauth_expires_at ? `过期：${e.oauth_expires_at}` : "",
		i,
		e.oauth_refreshable ? "存在 refresh_token，可尝试自动刷新" : "缺少 refresh_token",
		Number(e.sub2_uploaded_count || 0) > 0 ? "已纳入 sub2 自动同步" : "未记录 sub2 自动同步",
		e.oauth_refresh_error ? `最近刷新失败：${e.oauth_refresh_error}` : "",
		e.sub2_sync_error ? `sub2 同步失败：${e.sub2_sync_error}` : ""
	].filter(Boolean).join("；"), o = (e, t) => ({
		label: e,
		title: a,
		tone: t
	});
	return t === "deactivated" ? o("账号停用", "danger") : n === 401 ? o("401 失效", "danger") : e.oauth_reauth_required ? o("需重授权", "danger") : t === "valid" ? o("有效", "success") : t === "expiring" ? o("即将过期", "warning") : t === "expired" ? o(e.oauth_refreshable ? "已过期" : "已过期·需重授权", "danger") : t === "missing" ? o("缺少令牌", "danger") : o("未知", "neutral");
}
function pe(e) {
	let t = String(e || "").toLowerCase();
	return t === "plus" ? "active" : t === "pro" ? "warning" : t === "team" ? "success" : "neutral";
}
// src/features/codex/CodexTable.vue?vue&type=script&setup=true&lang.ts
var me = ["aria-busy"], he = {
	scope: "col",
	class: "ui-col-check"
}, ge = [
	"checked",
	"indeterminate",
	"disabled"
], _e = {
	class: "ui-col-check cx-check",
	"data-label": "选择"
}, ve = [
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], ye = {
	class: "cx-identity",
	"data-label": "邮箱 / 文件"
}, be = ["title"], xe = {
	class: "cx-extra",
	"data-label": "Plan"
}, Se = {
	class: "cx-extra",
	"data-label": "凭证状态"
}, Ce = {
	class: "cx-extra",
	"data-label": "OAuth 状态"
}, we = {
	class: "cx-extra",
	"data-label": "Account ID"
}, Te = {
	class: "cx-extra",
	"data-label": "Sub2API ID"
}, Ee = {
	class: "cx-extra ui-time",
	"data-label": "更新时间"
}, De = {
	class: "cx-extra ui-time",
	"data-label": "过期时间"
}, Oe = {
	class: "cx-actions",
	"data-label": "操作"
}, ke = { class: "ui-row-actions cx-row-actions" }, Ae = [
	"data-codex-download",
	"disabled",
	"onClick"
], je = ["aria-label", "disabled"], Me = {
	class: "cx-menu-actions",
	role: "group",
	"aria-label": "凭证操作"
}, Ne = [
	"data-codex-download",
	"disabled",
	"onClick"
], Pe = [
	"data-codex-reauthorize",
	"disabled",
	"onClick"
], Fe = [
	"data-codex-download-cpa",
	"disabled",
	"onClick"
], Ie = [
	"data-codex-refresh-token",
	"disabled",
	"onClick"
], Le = [
	"data-codex-upload-sub2",
	"disabled",
	"onClick"
], Re = [
	"data-codex-reset",
	"disabled",
	"onClick"
], ze = [
	"data-codex-archive",
	"data-archived",
	"disabled",
	"onClick"
], Be = [
	"data-codex-delete",
	"disabled",
	"onClick"
], Ve = /* @__PURE__ */ t({
	__name: "CodexTable",
	props: {
		items: {},
		selected: {},
		filters: {},
		facets: {},
		loading: { type: Boolean },
		error: {},
		busy: { type: Boolean },
		visible: { type: Boolean },
		openFilter: {}
	},
	emits: [
		"select",
		"selectPage",
		"action",
		"retry",
		"update:filters",
		"update:openFilter"
	],
	setup(e, { expose: t, emit: a }) {
		let s = e, l = a, { widths: u, total: f, resize: y, resizeWithKeyboard: x, resetColumns: w } = R({
			defaults: [
				48,
				228,
				84,
				108,
				108,
				132,
				132,
				132,
				132,
				228
			],
			storageKey: "gpt_console_table_widths_codex",
			totalStorageKey: "gpt_console_table_total_codex",
			min: 28,
			max: 2e3
		}), T = C(() => s.items.length > 0 && s.items.every((e) => s.selected.has(e.filename))), j = C(() => !T.value && s.items.some((e) => s.selected.has(e.filename))), I = C(() => {
			let e = /* @__PURE__ */ new Map();
			return s.items.map((t) => {
				let n = JSON.stringify([t.filename, t.sub2api_account_id ?? null]), r = e.get(n) ?? 0;
				return e.set(n, r + 1), {
					row: t,
					key: JSON.stringify([n, r]),
					credential: de(t),
					oauth: fe(t)
				};
			});
		}), L = h(null);
		i(() => s.visible, (e) => {
			e || (L.value = null);
		}), i(() => s.items, () => {
			L.value = null;
		});
		function V(e, t) {
			t ? L.value = e : L.value === e && (L.value = null);
		}
		function H(e, t) {
			s.busy || (L.value = null, l("action", e, t));
		}
		function U(e) {
			return e == null || e === "" ? "—" : String(e);
		}
		return t({ resetColumns: w }), (t, i) => (n(), D("div", {
			class: "ui-table-scroll cx-table-scroll",
			tabindex: "0",
			"aria-label": "Codex 凭证列表，可横向滚动",
			"aria-busy": e.loading
		}, [v("table", {
			class: "ui-table ui-table--sticky-end cx-table",
			style: m({ "--ui-table-width": `${E(f)}px` })
		}, [
			i[4] ||= v("caption", { class: "ui-sr-only" }, "Codex 凭证，支持跨页选择", -1),
			v("colgroup", null, [(n(!0), D(p, null, o(E(u), (e, t) => (n(), D("col", {
				key: t,
				style: m({ width: `${e}px` })
			}, null, 4))), 128))]),
			v("thead", null, [v("tr", null, [
				v("th", he, [v("input", {
					type: "checkbox",
					"aria-label": "全选当前页 Codex 凭证",
					checked: T.value,
					indeterminate: j.value,
					disabled: !e.items.length || e.busy,
					onChange: i[0] ||= (e) => l("selectPage", e.target.checked)
				}, null, 40, ge)]),
				(n(!0), D(p, null, o(E(W), (t, r) => (n(), D("th", {
					key: t.key,
					scope: "col"
				}, [c(ue, {
					column: t,
					"model-value": e.filters,
					facets: e.facets,
					open: e.visible && e.openFilter === t.key,
					"onUpdate:modelValue": i[1] ||= (e) => l("update:filters", e),
					"onUpdate:open": (e) => l("update:openFilter", e ? t.key : null)
				}, null, 8, [
					"column",
					"model-value",
					"facets",
					"open",
					"onUpdate:open"
				]), c(z, {
					label: t.label,
					onStart: (e) => E(y)(r + 1, e),
					onNudge: (e) => E(x)(r + 1, e)
				}, null, 8, [
					"label",
					"onStart",
					"onNudge"
				])]))), 128)),
				i[3] ||= v("th", { scope: "col" }, "操作", -1)
			])]),
			v("tbody", null, [(n(!0), D(p, null, o(I.value, ({ row: t, key: i, credential: a, oauth: o }) => (n(), D("tr", {
				key: i,
				class: S({ "is-selected": e.selected.has(t.filename) })
			}, [
				v("td", _e, [v("input", {
					type: "checkbox",
					"aria-label": `选择凭证 ${t.filename}`,
					checked: e.selected.has(t.filename),
					disabled: e.busy,
					onChange: (e) => l("select", t.filename, e.target.checked)
				}, null, 40, ve)]),
				v("td", ye, [c(P, {
					text: t.email || t.filename,
					secondary: t.email ? t.filename : void 0,
					title: `${t.email || ""} · 文件：${t.filename}${t.archived ? " · 已归档" : ""}`
				}, null, 8, [
					"text",
					"secondary",
					"title"
				]), v("div", {
					class: "cx-mobile-summary",
					title: [
						U(t.plan),
						a.title,
						o.title
					].join("；")
				}, g([
					U(t.plan),
					a.label,
					o.label
				].join(" · ")), 9, be)]),
				v("td", xe, [c(P, { text: U(t.plan) }, {
					default: r(() => [t.plan ? (n(), D("span", {
						key: 0,
						class: S(["ui-badge cx-badge", `ui-badge--${E(pe)(t.plan)}`])
					}, g(t.plan), 3)) : (n(), D(p, { key: 1 }, [O("—")], 64))]),
					_: 2
				}, 1032, ["text"])]),
				v("td", Se, [c(P, {
					text: a.label,
					title: a.title,
					tone: a.tone
				}, {
					default: r(() => [v("span", { class: S(["ui-badge cx-badge", `ui-badge--${a.tone}`]) }, g(a.label), 3)]),
					_: 2
				}, 1032, [
					"text",
					"title",
					"tone"
				])]),
				v("td", Ce, [c(P, {
					text: o.label,
					title: o.title,
					tone: o.tone
				}, {
					default: r(() => [v("span", { class: S(["ui-badge cx-badge", `ui-badge--${o.tone}`]) }, g(o.label), 3)]),
					_: 2
				}, 1032, [
					"text",
					"title",
					"tone"
				])]),
				v("td", we, [c(P, { text: U(t.account_id) }, null, 8, ["text"])]),
				v("td", Te, [c(P, { text: U(t.sub2api_account_id) }, null, 8, ["text"])]),
				v("td", Ee, [c(P, b({ ref_for: !0 }, E(B)(t.mtime), { title: U(t.mtime) }), null, 16, ["title"])]),
				v("td", De, [c(P, b({ ref_for: !0 }, E(B)(t.expired), { title: U(t.expired) }), null, 16, ["title"])]),
				v("td", Oe, [v("div", ke, [v("button", {
					type: "button",
					class: "ui-link cx-direct-download",
					"data-codex-download": t.filename,
					disabled: e.busy,
					onClick: (e) => H("download", t)
				}, "下载凭证", 8, Ae), c(E(A), {
					open: e.visible && L.value === i,
					modal: !1,
					"onUpdate:open": (e) => V(i, e)
				}, {
					default: r(() => [c(E(k), { "as-child": "" }, {
						default: r(() => [v("button", {
							type: "button",
							class: "ui-link",
							"aria-label": `更多操作 ${t.filename}`,
							disabled: e.busy
						}, "更多", 8, je)]),
						_: 2
					}, 1024), c(E(N), null, {
						default: r(() => [c(E(F), {
							class: "cx-row-menu",
							"aria-label": `${t.email || t.filename} 的凭证详情与操作`,
							side: "bottom",
							align: "end",
							"side-offset": 6,
							"collision-padding": 10,
							"hide-when-detached": ""
						}, {
							default: r(() => [v("div", Me, [
								v("button", {
									type: "button",
									"data-codex-download": t.filename,
									disabled: e.busy,
									onClick: (e) => H("download", t)
								}, "下载凭证", 8, Ne),
								v("button", {
									type: "button",
									"data-codex-reauthorize": t.filename,
									disabled: e.busy,
									onClick: (e) => H("reauthorize", t)
								}, "重跑授权", 8, Pe),
								v("button", {
									type: "button",
									"data-codex-download-cpa": t.filename,
									disabled: e.busy,
									onClick: (e) => H("downloadCpa", t)
								}, "从 CPA 下载", 8, Fe),
								v("button", {
									type: "button",
									"data-codex-refresh-token": t.filename,
									disabled: e.busy,
									onClick: (e) => H("refreshToken", t)
								}, "刷新 OAuth Token", 8, Ie),
								v("button", {
									type: "button",
									"data-codex-upload-sub2": t.filename,
									disabled: e.busy,
									onClick: (e) => H("uploadSub2", t)
								}, "上传 sub2api", 8, Le),
								Number(t.exported_count || 0) > 0 ? (n(), D("button", {
									key: 0,
									type: "button",
									"data-codex-reset": t.filename,
									disabled: e.busy,
									onClick: (e) => H("reset", t)
								}, "重置标记", 8, Re)) : d("", !0),
								v("button", {
									type: "button",
									"data-codex-archive": t.filename,
									"data-archived": t.archived ? "0" : "1",
									disabled: e.busy,
									onClick: (e) => H("archive", t)
								}, g(t.archived ? "恢复" : "归档"), 9, ze),
								v("button", {
									type: "button",
									class: "cx-danger",
									"data-codex-delete": t.filename,
									disabled: e.busy,
									onClick: (e) => H("delete", t)
								}, "删除凭证", 8, Be)
							])]),
							_: 2
						}, 1032, ["aria-label"])]),
						_: 2
					}, 1024)]),
					_: 2
				}, 1032, ["open", "onUpdate:open"])])])
			], 2))), 128)), e.items.length ? d("", !0) : (n(), _(M, {
				key: 0,
				colspan: 10,
				loading: e.loading,
				error: e.error,
				"loading-title": "正在加载授权凭证",
				"loading-text": "正在同步 OAuth 与导出状态",
				"error-title": "凭证列表加载失败",
				title: "没有匹配的凭证",
				text: "可调整筛选条件，或清除全部筛选。",
				"retry-label": "重新加载",
				onRetry: i[2] ||= (e) => l("retry")
			}, null, 8, ["loading", "error"]))])
		], 4)], 8, me));
	}
});
// src/api/codex.ts
function He() {
	return {
		q: "",
		plan: "",
		status: "",
		oauth_status: "",
		account_id: "",
		sub2api_id: "",
		date_from: "",
		date_to: "",
		expired_date: ""
	};
}
function Z(e, t) {
	return H(`/api/codex/${e}`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(t)
	});
}
function Q(e) {
	return e && typeof e == "object" && !Array.isArray(e) ? e : {};
}
function Ue(e, t) {
	let n = /filename\*=UTF-8''([^;]+)/i.exec(e)?.[1], r = /filename=(?:"([^"]+)"|([^;]+))/i.exec(e), i = r?.[1] || r?.[2]?.trim() || t;
	if (n) try {
		i = decodeURIComponent(n.trim());
	} catch {}
	return i.replace(/[\\/\x00-\x1f\x7f]/g, "_") || t;
}
function We(e, t) {
	let n = e.error, r = typeof n == "string" ? n : Q(n).message, i = Array.isArray(e.errors) ? e.errors.slice(0, 3).map((e) => {
		let t = Q(e);
		return typeof t.filename == "string" && typeof t.error == "string" ? `${t.filename}: ${t.error}` : "";
	}).filter(Boolean) : [];
	return new U((typeof r == "string" ? r : `下载失败（HTTP ${t}）`) + (i.length ? `；${i.join("；")}` : ""), t, typeof Q(n).code == "string" ? String(Q(n).code) : typeof e.error_code == "string" ? e.error_code : "");
}
async function Ge(e, t, n, r, i) {
	let a = await fetch(e, {
		credentials: "same-origin",
		...i ? {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(i)
		} : {}
	});
	if (a.status === 401 || a.redirected) throw new U("登录已失效，请重新登录后刷新。", a.status);
	let o = (a.headers.get("Content-Type") || "").toLowerCase(), s = a.headers.get("Content-Disposition") || "", c = await a.blob();
	if (!c.size) throw new U("下载返回空文件。", a.status);
	let l = {};
	if (o.includes("application/json")) {
		try {
			let e = JSON.parse(await c.text());
			if (!e || typeof e != "object" || Array.isArray(e)) throw Error("invalid");
			l = Q(e);
		} catch {
			throw new U("下载返回无效 JSON。", a.status);
		}
		if (!a.ok || l.ok === !1 || l.error) throw We(l, a.status);
	} else if (!a.ok) throw new U(`下载失败（HTTP ${a.status}）`, a.status);
	if (!/attachment/i.test(s)) throw new U("服务返回了非下载附件，请刷新后重试。", a.status);
	if (r === "zip" ? !o.includes("application/zip") : !o.includes("application/json")) throw new U("服务返回了非下载内容，请刷新后重试。", a.status);
	let u = r === "single" ? n : [], d = 0;
	if (r === "bulk") {
		if (!Array.isArray(l.credentials) || typeof l.count != "number") throw new U("下载返回无效的批量凭证附件。", a.status);
		u = Array.isArray(l.credentials) ? l.credentials.map((e) => Q(e).filename).filter((e) => typeof e == "string" && n.includes(e)) : [], d = Array.isArray(l.errors) ? l.errors.length : 0;
	}
	return {
		blob: c,
		filename: Ue(s, t),
		acknowledged: u,
		failed: d
	};
}
var $ = {
	list(e, t) {
		let n = new URLSearchParams({
			paged: "1",
			page: String(e.page),
			page_size: String(e.size),
			archived: e.archived ? "only" : "0"
		});
		for (let [t, r] of Object.entries(e.filters)) r !== "" && n.set(t, r);
		return H(`/api/codex?${n}`, { signal: t });
	},
	archive: (e, t) => Z("archive", {
		filename: e,
		archived: t
	}),
	archiveBulk: (e, t) => Z("archive-bulk", {
		filenames: e,
		archived: t
	}),
	delete: (e) => Z("delete", { filename: e }),
	deleteBulk: (e) => Z("delete-bulk", { filenames: e }),
	reset: (e) => Z("reset-export", { filename: e }),
	refreshToken: (e) => Z("refresh-token-bulk", { filenames: e }),
	reauthorize: (e) => Z("retry-bulk", { filenames: e }),
	uploadSub2: (e) => Z("upload-sub2-bulk", { filenames: e }),
	download: (e, t = !1) => Ge(`/api/codex/${t ? "download-from-cpa" : "download"}/${encodeURIComponent(e)}`, t ? e.replace(/-cpa-callback\.json$/i, "-free.json") : e, [e], "single"),
	downloadBulk: (e, t = !1) => Ge(`/api/codex/${t ? "download-bulk-from-cpa" : "download-bulk"}`, t ? "codex-cpa-bulk.zip" : "codex-bulk.json", e, t ? "zip" : "bulk", { filenames: e })
}, Ke = /* @__PURE__ */ new Set([
	"download",
	"downloadCpa",
	"archive",
	"delete",
	"reset"
]), qe = /* @__PURE__ */ new Set([
	"refreshToken",
	"reauthorize",
	"uploadSub2"
]), Je = {
	download: "下载",
	downloadCpa: "从 CPA 下载",
	downloadBulk: "批量下载",
	downloadBulkCpa: "从 CPA 批量下载",
	archive: "归档",
	archiveBulk: "归档",
	delete: "删除",
	deleteBulk: "批量删除",
	reset: "重置",
	refreshToken: "刷新 OAuth Token",
	reauthorize: "重跑 Codex 授权",
	uploadSub2: "上传 sub2api"
};
function Ye(e) {
	return e instanceof Error ? e.message : "请求失败，请稍后重试。";
}
function Xe(e = []) {
	return e.filter((e) => e.accepted !== !1).map((e) => e.filename).filter((e) => typeof e == "string" && !!e);
}
function Ze(e) {
	let t = URL.createObjectURL(e.blob), n = document.createElement("a");
	n.href = t, n.download = e.filename;
	let r = () => {
		URL.revokeObjectURL(t), n.remove();
	};
	try {
		document.body.appendChild(n), n.click();
	} catch (e) {
		throw r(), e;
	}
	setTimeout(r, 800);
}
function Qe(e, t, n, r, i) {
	let a = t.length;
	switch (e) {
		case "archiveBulk": return `${n ? "归档" : "恢复"}选中的 ${a} 个 Codex 授权凭证？`;
		case "delete": return `确定删除 Codex 凭证？\n\n${t[0]}\n\n会删除数据库中的凭证及导出状态。此操作不可撤销。`;
		case "deleteBulk": return `确定删除选中的 ${a} 个 Codex 凭证吗？\n\n会删除数据库中的凭证及导出状态。此操作不可撤销。`;
		case "reset": return `把 ${t[0]} 标记重置为未导出？`;
		case "downloadBulk": return `选中 ${a} 个凭证，打包到一个 JSON 文件下载。\n\n⚠ 这个聚合格式 CPA 不能直接读，主要用于备份/迁移。\n要给 CPA 用请用每行的"下载 JSON"单个下载。\n\n继续？`;
		case "downloadBulkCpa": return `选中 ${a} 个本地记录，将按邮箱到 CPA auth-files 查找并下载真实 Codex JSON。\n\n下载结果会打包成 ZIP，解压后每个 JSON 可直接放入 CPA auth-dir。\n如 CPA 中找不到对应邮箱，会在 zip 的 manifest.json 记录错误。\n\n继续？`;
		case "uploadSub2": return `把选中的 ${a} 个 Codex OAuth 凭证上传到 sub2api？\n\n同名账号将按 sub2api 的导入策略更新。`;
		case "reauthorize": return `确定为选中的 ${a} 个账号重新执行 Codex OAuth 授权吗？\n\n按实际验证要求使用邮箱 OTP。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n账号操作公共并发：${r.callbacks.operationWorkers()}\n\n授权成功后会更新本地 Codex 凭证；若“授权后自动上传并启用 sub2api”开关开启，将自动上传并恢复调度；关闭时需在成功后手工点击“上传 sub2api”。`;
		case "refreshToken": {
			let e = [...r.items.value, ...i ? [i] : []].some((e) => t.includes(e.filename) && Number(e.exported_count || 0) > 0 && Number(e.sub2_uploaded_count || 0) === 0);
			return `使用 refresh_token 刷新选中的 ${a} 个 Codex OAuth 凭证？\n\n这个操作不发邮箱验证码、不用接码短信。刷新成功后，本地凭证会更新；已记录为上传过 sub2api 的凭证也会自动同步。` + (e ? "\n\n⚠ 检测到旧版“已导出”记录，无法区分当时是下载还是上传 sub2api。如果这些凭证正在 sub2api 使用，建议先取消并点一次“上传 sub2api”，建立自动同步记录。" : "");
		}
		default: return "";
	}
}
function $e(e) {
	let t = h(!1), n = h(""), r = h(!1), { callbacks: i } = e;
	function a(t, n) {
		let r = new Set(e.selected.value), i = new Set(n);
		for (let e of t) i.has(e) && r.delete(e);
		e.selected.value = r;
	}
	async function o() {
		try {
			await e.refresh();
		} catch (e) {
			n.value = `操作已完成，但列表刷新失败：${Ye(e)}`, i.notify(n.value);
		}
	}
	async function s(s, c, l) {
		if (t.value) return;
		let u = [...new Set((c ?? [...e.selected.value]).filter((e) => !!e))];
		if (!u.length) return;
		t.value = !0, n.value = "";
		let d = !(l?.archived ?? e.archived.value);
		try {
			let t = Ke.has(s) ? 1 : qe.has(s) ? 500 : 1e3;
			if (u.length > t) throw Error(`单次最多 ${t} 个凭证，请调整选择后重试。`);
			let n = Qe(s, u, d, e, l);
			if (n && !await i.confirm(n)) return;
			let c = u[0];
			switch (s) {
				case "download":
				case "downloadCpa":
				case "downloadBulk":
				case "downloadBulkCpa": {
					let e = s === "downloadBulk" || s === "downloadBulkCpa", t = s === "downloadCpa" || s === "downloadBulkCpa", n = e ? await $.downloadBulk(u, t) : await $.download(c, t);
					Ze(n), e && a(n.acknowledged, u), i.notify(e ? t ? "已从 CPA 下载 ZIP，成功与失败详情见 manifest.json" : n.acknowledged.length ? `已打包下载 ${n.acknowledged.length} 个${n.failed ? `，${n.failed} 个失败` : ""}` : "成功 0 个，已下载错误清单" : t ? "已从 CPA 下载" : "已下载 JSON"), await o();
					break;
				}
				case "archive":
				case "archiveBulk": {
					let e = s === "archive" ? await $.archive(c, d) : await $.archiveBulk(u, d);
					a(s === "archive" ? e.filename ? [e.filename] : [] : (e.updated || []).map((e) => e.filename), u), i.notify(s === "archive" ? d ? "已归档" : "已恢复" : `${d ? "归档" : "恢复"}成功 ${e.updated_count || 0} 个`), await o();
					break;
				}
				case "delete":
				case "deleteBulk": {
					let e = s === "delete" ? await $.delete(c) : await $.deleteBulk(u);
					a(typeof e.deleted == "string" ? [e.deleted] : e.deleted || [], u);
					let t = e.skipped?.length || 0;
					i.notify(s === "delete" ? "Codex 凭证已删除" : `已删除 ${e.deleted_count || 0} 个${t ? `，跳过 ${t} 个` : ""}`), await o();
					break;
				}
				case "reset":
					await $.reset(c), i.notify("已重置"), await o();
					break;
				case "refreshToken":
				case "reauthorize": {
					let e = s === "refreshToken" ? await $.refreshToken(u) : await $.reauthorize(u);
					a(Xe(e.started), u);
					let t = e.skipped?.length || 0;
					i.notify(t ? `已开始${s === "refreshToken" ? "刷新" : "重跑"} ${e.started_count || 0} 个，跳过 ${t} 个` : e.message || `已开始${s === "refreshToken" ? "刷新 OAuth Token" : "重跑 Codex 授权"}`), i.openTasks(s === "refreshToken" ? "codex_token_refresh" : "codex_retry");
					break;
				}
				case "uploadSub2": {
					let e = await $.uploadSub2(u), t = (e.failed_count || 0) + (e.skipped_count || 0);
					if (a(Xe(e.accepted ? e.queued : e.uploaded), u), e.accepted) {
						let n = e.queued || [], a = n.some((e) => e.accepted && Number(e.task_id));
						i.notify(`手动上传已入队 ${e.queued_count || 0} 个${t ? `，${t} 个未入队` : ""}${a ? "，可点击“查看上传进度”查看最终结果" : ""}`), i.track(n, "手动上传", { navigate: !1 }), r.value ||= a;
					} else i.notify(t ? `已上传 ${e.uploaded_count || 0} 个，${t} 个未完成` : `已上传 ${e.uploaded_count || 0} 个到 sub2api`), await o();
					break;
				}
			}
		} catch (e) {
			n.value = `${Je[s]}失败: ${Ye(e)}`, i.notify(n.value);
		} finally {
			t.value = !1;
		}
	}
	return {
		busy: t,
		error: n,
		uploadProgress: r,
		run: s,
		showProgress: () => i.openTasks()
	};
}
// src/features/codex/useCodexList.ts
function et() {
	let t = s(He()), n = h([]), r = h({}), i = h(0), a = h(1), o = h(20), c = h(!1), l = h(/* @__PURE__ */ new Set()), d = h(!1), f = h(""), p = h(!1), m = C(() => Math.max(1, Math.ceil(i.value / o.value))), g = /* @__PURE__ */ new Set([
		"q",
		"account_id",
		"sub2api_id"
	]), _ = 0, v = 0, y = !1, b = null, x;
	function S() {
		++_, ++v, clearTimeout(x), x = void 0, b?.abort(), b = null, d.value = !1;
	}
	function w() {
		return !y && p.value && !document.hidden;
	}
	function T(t = 0) {
		S();
		let n = v;
		if (!w()) return;
		let r = () => {
			n === v && w() && D();
		};
		t ? x = setTimeout(r, t) : e(r);
	}
	function E(e) {
		let n = { ...e };
		for (let r of [
			"plan",
			"status",
			"oauth_status"
		]) {
			let i = (e[r] || []).filter((e) => e.value && (r !== "status" || e.value !== "archived")), a = t[r];
			n[r] = a && !i.some((e) => e.value === a) ? [...i, {
				value: a,
				count: 0
			}] : i;
		}
		return n;
	}
	async function D() {
		if (S(), !w()) return;
		let e = _, s = new AbortController();
		b = s, d.value = !0;
		try {
			for (let l = 0; l < 2; l++) {
				let u = {
					page: a.value,
					size: o.value,
					archived: c.value,
					filters: { ...t }
				}, d = await $.list(u, s.signal);
				if (e !== _ || !w()) return;
				let p = Number(d.total);
				if (i.value = Number.isFinite(p) ? Math.max(0, Math.floor(p)) : 0, a.value > m.value) {
					if (a.value = m.value, !l) continue;
					n.value = [], f.value = "列表范围已变化，请刷新后重试";
					return;
				}
				n.value = d.accounts || [], r.value = E(d.facets || {}), f.value = "";
				return;
			}
		} catch (t) {
			e === _ && !V(t) && (f.value = t instanceof Error ? t.message : "Codex 凭证加载失败");
		} finally {
			e === _ && (d.value = !1, b = null);
		}
	}
	function O(e) {
		y || e === p.value || (p.value = e, e ? T() : S());
	}
	function k(e) {
		y || e === c.value || (c.value = e, l.value = /* @__PURE__ */ new Set(), n.value = [], r.value = {}, i.value = 0, a.value = 1, f.value = "", T());
	}
	function A(e) {
		if (y || !Number.isFinite(e)) return;
		let t = Math.min(m.value, Math.max(1, Math.floor(e)));
		t !== a.value && (a.value = t, T());
	}
	function j(e) {
		if (y || !Number.isFinite(e) || e < 1) return;
		let t = Math.min(500, Math.floor(e));
		t !== o.value && (o.value = t, a.value = 1, T());
	}
	function M(e) {
		if (y) return;
		let n = Object.keys(t).filter((n) => e[n] !== void 0 && e[n] !== t[n]);
		if (!n.length) return;
		for (let r of n) t[r] = e[r];
		a.value = 1;
		let r = n.every((e) => g.has(e));
		r || (l.value = /* @__PURE__ */ new Set()), T(r ? 250 : 0);
	}
	function N() {
		y || (Object.assign(t, He()), l.value = /* @__PURE__ */ new Set(), a.value = 1, T());
	}
	function P(e, t) {
		let n = new Set(l.value);
		t ? n.add(e) : n.delete(e), l.value = n;
	}
	function F(e) {
		let t = new Set(l.value);
		for (let r of n.value) e ? t.add(r.filename) : t.delete(r.filename);
		l.value = t;
	}
	let I = () => {
		document.hidden ? S() : p.value && T();
	};
	return document.addEventListener("visibilitychange", I), u(() => {
		y = !0, S(), document.removeEventListener("visibilitychange", I);
	}), {
		filters: t,
		items: n,
		facets: r,
		total: i,
		page: a,
		size: o,
		pages: m,
		archived: c,
		selected: l,
		loading: d,
		error: f,
		visible: p,
		refresh: D,
		setVisible: O,
		setArchived: k,
		setPage: A,
		setSize: j,
		updateFilters: M,
		resetFilters: N,
		toggle: P,
		togglePage: F
	};
}
// src/features/codex/CodexCredentials.vue?vue&type=script&setup=true&lang.ts
var tt = {
	class: "cx-root",
	"aria-label": "Codex 授权"
}, nt = { class: "ui-list cx-workspace" }, rt = {
	id: "codexToolbarV2",
	class: "ui-list-toolbar cx-toolbar"
}, it = { class: "ui-list-toolbar__main cx-toolbar-main" }, at = {
	class: "ui-list-count cx-count",
	role: "status"
}, ot = { key: 0 }, st = {
	key: 0,
	id: "codexSelectedHintV2",
	class: "cx-selected",
	role: "status"
}, ct = {
	key: 1,
	class: "cx-bulk-actions",
	role: "group",
	"aria-label": "选中凭证批量操作"
}, lt = [
	"id",
	"title",
	"disabled",
	"onClick"
], ut = { class: "ui-list-toolbar__actions cx-toolbar-utilities" }, dt = ["disabled"], ft = {
	key: 0,
	class: "ui-list-feedback is-error cx-feedback",
	role: "alert"
}, pt = /* @__PURE__ */ t({
	__name: "CodexCredentials",
	props: { callbacks: {} },
	setup(e, { expose: t }) {
		let r = e, i = et(), { items: s, facets: l, total: u, page: f, size: m, pages: _, archived: b, selected: x, loading: w, error: k, visible: A, filters: j } = i, M = $e({
			selected: x,
			items: s,
			archived: b,
			refresh: i.refresh,
			callbacks: r.callbacks
		}), { busy: N, error: P, uploadProgress: F } = M, R = h(), z = h(null), B = h(!document.hidden), V = C(() => q(j, l.value)), H = [
			{
				kind: "refreshToken",
				id: "btnCodexRefreshTokenBulkV2",
				label: "刷新 OAuth Token",
				title: "使用 refresh_token 刷新选中凭证，不需要邮箱验证码或短信"
			},
			{
				kind: "reauthorize",
				id: "btnCodexReauthorizeBulkV2",
				label: "重跑 Codex 授权",
				title: "重新执行 Codex OAuth 授权；按实际验证要求使用邮箱 OTP 和手机接码"
			},
			{
				kind: "downloadBulk",
				id: "btnCodexDownloadBulkV2",
				label: "下载凭证",
				title: "从数据库读取选中凭证，打包成一个 JSON 文件下载"
			},
			{
				kind: "downloadBulkCpa",
				id: "btnCodexDownloadBulkCpaV2",
				label: "从 CPA 下载",
				title: "从 CPA 下载真实 Codex JSON，打包为 ZIP"
			},
			{
				kind: "uploadSub2",
				id: "btnCodexUploadSub2V2",
				label: "上传 sub2api",
				title: "把选中的本地 Codex OAuth 凭证上传到 sub2api"
			},
			{
				kind: "archiveBulk",
				id: "btnCodexArchiveBulkV2",
				label: "归档选中",
				title: "归档或恢复选中的 Codex 凭证"
			},
			{
				kind: "deleteBulk",
				id: "btnCodexDeleteBulkV2",
				label: "删除选中",
				title: "删除数据库中选中的 Codex 凭证及导出状态",
				danger: !0
			}
		];
		function U(e) {
			e || (z.value = null), i.setVisible(e);
		}
		function W(e) {
			z.value = null, i.setArchived(e);
		}
		async function G() {
			await i.refresh();
		}
		function K(e, t) {
			M.run(e, [t.filename], t);
		}
		function Y(e) {
			i.updateFilters(J(j, e));
		}
		let X = () => {
			B.value = !document.hidden, document.hidden && (z.value = null);
		};
		return document.addEventListener("visibilitychange", X), y(() => document.removeEventListener("visibilitychange", X)), t({
			refresh: G,
			setVisible: U,
			setArchived: W
		}), (e, t) => a((n(), D("section", tt, [v("div", nt, [
			v("div", rt, [v("div", it, [
				v("span", at, [O(g(E(u).toLocaleString()) + " 个凭证", 1), E(b) ? (n(), D("span", ot, " · 已归档")) : d("", !0)]),
				E(x).size ? (n(), D("span", st, "已选 " + g(E(x).size) + " 项", 1)) : d("", !0),
				E(x).size ? (n(), D("div", ct, [(n(), D(p, null, o(H, (e) => v("button", {
					id: e.id,
					key: e.kind,
					type: "button",
					class: S(["ui-button", { "ui-button--danger": e.danger }]),
					title: e.title,
					disabled: E(N),
					onClick: (t) => E(M).run(e.kind)
				}, g(e.kind === "archiveBulk" && E(b) ? "恢复选中" : e.label), 11, lt)), 64))])) : d("", !0),
				c(I, {
					items: V.value,
					onRemove: Y
				}, null, 8, ["items"])
			]), v("div", ut, [
				c(ue, {
					"model-value": E(j),
					facets: E(l),
					open: B.value && z.value === "all",
					"onUpdate:modelValue": E(i).updateFilters,
					"onUpdate:open": t[0] ||= (e) => z.value = e ? "all" : null
				}, null, 8, [
					"model-value",
					"facets",
					"open",
					"onUpdate:modelValue"
				]),
				V.value.length ? (n(), D("button", {
					key: 0,
					id: "btnResetCodexFiltersV2",
					type: "button",
					class: "ui-link",
					onClick: t[1] ||= (...e) => E(i).resetFilters && E(i).resetFilters(...e)
				}, "清除筛选")) : d("", !0),
				E(F) ? (n(), D("button", {
					key: 1,
					id: "btnCodexUploadProgressV2",
					type: "button",
					class: "ui-button",
					onClick: t[2] ||= (...e) => E(M).showProgress && E(M).showProgress(...e)
				}, "查看上传进度")) : d("", !0),
				v("button", {
					id: "btnResetCodexColumnsV2",
					type: "button",
					class: "ui-link cx-reset-columns",
					title: "恢复 Codex 列表默认列宽",
					onClick: t[3] ||= (e) => R.value?.resetColumns()
				}, "恢复列宽"),
				v("button", {
					id: "btnRefreshCodexV2",
					type: "button",
					class: "ui-button",
					disabled: E(w),
					onClick: G
				}, g(E(w) ? "刷新中…" : "刷新"), 9, dt)
			])]),
			E(P) || E(k) && E(s).length ? (n(), D("div", ft, [v("span", null, g(E(P) || E(k)), 1), E(k) ? (n(), D("button", {
				key: 0,
				type: "button",
				class: "ui-link",
				onClick: G
			}, "重试")) : d("", !0)])) : d("", !0),
			c(Ve, {
				ref_key: "table",
				ref: R,
				items: E(s),
				selected: E(x),
				filters: E(j),
				facets: E(l),
				loading: E(w),
				error: E(k),
				busy: E(N),
				visible: E(A) && B.value,
				"open-filter": z.value,
				"onUpdate:openFilter": t[4] ||= (e) => z.value = e,
				"onUpdate:filters": E(i).updateFilters,
				onSelect: E(i).toggle,
				onSelectPage: E(i).togglePage,
				onAction: K,
				onRetry: G
			}, null, 8, [
				"items",
				"selected",
				"filters",
				"facets",
				"loading",
				"error",
				"busy",
				"visible",
				"open-filter",
				"onUpdate:filters",
				"onSelect",
				"onSelectPage"
			]),
			c(L, {
				page: E(f),
				size: E(m),
				pages: E(_),
				total: E(u),
				busy: E(w),
				"page-sizes": [
					10,
					20,
					30,
					50,
					100
				],
				label: "Codex 凭证分页",
				"onUpdate:page": E(i).setPage,
				"onUpdate:size": E(i).setSize
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		])], 512)), [[T, E(A)]]);
	}
});
// src/codex.ts
function mt(e, t) {
	return w(pt, { callbacks: t }).mount(e);
}
export { mt as mountCodexCredentials };
