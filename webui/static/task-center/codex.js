import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, Q as s, S as c, V as l, Z as u, _ as d, a as f, c as p, d as m, dt as h, et as g, ft as _, g as v, h as y, j as b, k as x, l as S, lt as C, m as w, n as T, s as E, st as D, v as O, x as k } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { a as A, c as j, i as M, n as N, o as P, r as F, s as I, t as L } from "./ListFilterSummary-Bo2VJ9RL.js";
import { t as ee } from "./ListPagination-DURVj-Kj.js";
import { n as R, t as z } from "./ColumnResizer-2h5GXxFn.js";
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
var Y = { class: "cx-filter-fields" }, te = {
	key: 0,
	class: "cx-filter-field"
}, ne = ["value"], re = {
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
], le = { class: "list-filter-actions" }, X = /* @__PURE__ */ t({
	__name: "CodexFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean },
		column: {}
	},
	emits: ["update:modelValue", "update:open"],
	setup(e, { emit: t }) {
		let i = e, s = t, u = g("q"), h = l(), v = w(() => i.column || W.find((e) => e.key === u.value) || W[0]), b = w(() => i.column ? i.column.fields.some((e) => !!i.modelValue[e]) : Object.values(i.modelValue).some(Boolean)), x = w(() => q(i.modelValue, i.facets).find((e) => e.key === v.value.key)?.label || ""), T = w(() => {
			let e = v.value.fields[0], t = (i.facets[v.value.key] || []).filter((e) => v.value.key !== "status" || e.value !== "archived"), n = i.modelValue[e], r = t.map((e) => ({
				...e,
				label: e.label || K(v.value.key, e.value)
			}));
			return n && !r.some((e) => e.value === n) && r.unshift({
				value: n,
				label: K(v.value.key, n),
				count: 0
			}), r;
		});
		function E(e, t) {
			s("update:modelValue", {
				...i.modelValue,
				[e]: t
			});
		}
		function A() {
			s("update:modelValue", J(i.modelValue, v.value.key)), s("update:open", !1);
		}
		function j(e, t, n) {
			e.detail <= 0 || (E(t, n), s("update:open", !1));
		}
		return (t, i) => (n(), O("div", { class: C({ "cx-all-filters": !e.column }) }, [c(M, {
			label: e.column?.label || "凭证",
			"trigger-label": e.column ? void 0 : "筛选",
			active: b.value,
			summary: x.value,
			open: e.open,
			"onUpdate:open": i[5] ||= (e) => s("update:open", e)
		}, {
			default: r(() => [y("div", Y, [
				e.column ? d("", !0) : (n(), O("label", te, [i[6] ||= k("筛选列", -1), a(y("select", {
					"onUpdate:modelValue": i[0] ||= (e) => u.value = e,
					"aria-label": "选择筛选列"
				}, [(n(!0), O(m, null, o(D(W), (e) => (n(), O("option", {
					key: e.key,
					value: e.key
				}, _(e.label), 9, ne))), 128))], 512), [[f, u.value]])])),
				v.value.kind === "enum" ? (n(), O("fieldset", re, [
					y("legend", ie, _(v.value.label), 1),
					y("label", ae, [y("input", {
						type: "radio",
						name: D(h),
						value: "",
						checked: !e.modelValue[v.value.fields[0]],
						onChange: i[1] ||= (e) => E(v.value.fields[0], ""),
						onClick: i[2] ||= (e) => j(e, v.value.fields[0], "")
					}, null, 40, oe), i[7] ||= y("span", null, "全部", -1)]),
					(n(!0), O(m, null, o(T.value, (t) => (n(), O("label", {
						class: "list-filter-option",
						key: t.value
					}, [
						y("input", {
							type: "radio",
							name: D(h),
							value: t.value,
							checked: e.modelValue[v.value.fields[0]] === t.value,
							onChange: (e) => E(v.value.fields[0], t.value),
							onClick: (e) => j(e, v.value.fields[0], t.value)
						}, null, 40, se),
						y("span", null, _(t.label), 1),
						y("small", null, _(t.count), 1)
					]))), 128))
				])) : (n(!0), O(m, { key: 2 }, o(v.value.fields, (t, r) => (n(), O("label", {
					key: t,
					class: "cx-filter-field"
				}, [k(_(v.value.kind === "date-range" ? r ? "截止日期" : "开始日期" : v.value.label) + " ", 1), y("input", {
					type: v.value.kind === "text" ? "text" : "date",
					"aria-label": v.value.kind === "date-range" ? r ? "截止日期" : "开始日期" : v.value.label,
					value: e.modelValue[t],
					placeholder: v.value.placeholder,
					autocomplete: "off",
					onInput: (e) => E(t, e.target.value),
					onKeydown: i[3] ||= p(S((e) => s("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, ce)]))), 128)),
				y("div", le, [y("button", {
					type: "button",
					onClick: A
				}, "清除此列"), y("button", {
					type: "button",
					class: "list-filter-primary",
					onClick: i[4] ||= (e) => s("update:open", !1)
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
function ue(e) {
	let t = Number(e.exported_count || 0), n = Number(e.sub2_uploaded_count || 0);
	if (n > 0) {
		let r = [`Sub2API 已上传 ${n} 次，最近 ${e.sub2_uploaded_at || "-"}`];
		return t > 0 && r.push(`导出记录 ${t} 次，最近 ${e.exported_at || "-"}`), {
			label: "已导出",
			title: r.join("；"),
			tone: "neutral"
		};
	}
	let r = e.exported === !0 || t > 0, i = e.sub2api_account_id != null && String(e.sub2api_account_id).trim() !== "";
	return r && t <= 0 && i ? {
		label: "已关联",
		title: `Sub2API ID ${e.sub2api_account_id} 已有关联记录，本地下载 0 次`,
		tone: "neutral"
	} : r ? {
		label: "已导出",
		title: `导出 ${t} 次，最近 ${e.exported_at || "-"}`,
		tone: "neutral"
	} : {
		label: "未导出",
		title: "没有本地导出或 Sub2API 关联记录",
		tone: "success"
	};
}
function de(e) {
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
// src/features/codex/CodexTable.vue?vue&type=script&setup=true&lang.ts
var fe = ["aria-busy"], pe = {
	scope: "col",
	class: "ui-col-check"
}, me = [
	"checked",
	"indeterminate",
	"disabled"
], he = {
	class: "ui-col-check cx-check",
	"data-label": "选择"
}, ge = [
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], _e = {
	class: "cx-identity",
	"data-label": "邮箱 / 文件"
}, ve = ["title"], ye = {
	class: "cx-extra",
	"data-label": "Plan"
}, be = {
	class: "cx-extra",
	"data-label": "凭证状态"
}, xe = {
	class: "cx-extra",
	"data-label": "OAuth 状态"
}, Se = {
	class: "cx-extra",
	"data-label": "Account ID"
}, Ce = {
	class: "cx-extra",
	"data-label": "Sub2API ID"
}, we = {
	class: "cx-extra ui-time",
	"data-label": "更新时间"
}, Te = {
	class: "cx-extra ui-time",
	"data-label": "过期时间"
}, Ee = {
	class: "cx-actions",
	"data-label": "操作"
}, De = { class: "ui-row-actions cx-row-actions" }, Oe = [
	"data-codex-download",
	"disabled",
	"onClick"
], ke = ["aria-label", "disabled"], Ae = { class: "cx-row-details" }, je = {
	class: "cx-menu-actions",
	role: "group",
	"aria-label": "凭证操作"
}, Me = [
	"data-codex-download",
	"disabled",
	"onClick"
], Ne = [
	"data-codex-reauthorize",
	"disabled",
	"onClick"
], Pe = [
	"data-codex-download-cpa",
	"disabled",
	"onClick"
], Fe = [
	"data-codex-refresh-token",
	"disabled",
	"onClick"
], Ie = [
	"data-codex-upload-sub2",
	"disabled",
	"onClick"
], Le = [
	"data-codex-reset",
	"disabled",
	"onClick"
], Re = [
	"data-codex-archive",
	"data-archived",
	"disabled",
	"onClick"
], ze = [
	"data-codex-delete",
	"disabled",
	"onClick"
], Be = /* @__PURE__ */ t({
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
		let s = e, l = a, { widths: u, total: f, resize: p, resizeWithKeyboard: b, resetColumns: S } = R({
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
		}), T = w(() => s.items.length > 0 && s.items.every((e) => s.selected.has(e.filename))), E = w(() => !T.value && s.items.some((e) => s.selected.has(e.filename))), M = w(() => {
			let e = /* @__PURE__ */ new Map();
			return s.items.map((t) => {
				let n = JSON.stringify([t.filename, t.sub2api_account_id ?? null]), r = e.get(n) ?? 0;
				return e.set(n, r + 1), {
					row: t,
					key: JSON.stringify([n, r]),
					credential: ue(t),
					oauth: de(t)
				};
			});
		}), L = g(null);
		i(() => s.visible, (e) => {
			e || (L.value = null);
		}), i(() => s.items, () => {
			L.value = null;
		});
		function ee(e, t) {
			t ? L.value = e : L.value === e && (L.value = null);
		}
		function V(e, t) {
			s.busy || (L.value = null, l("action", e, t));
		}
		function H(e) {
			return e == null || e === "" ? "—" : String(e);
		}
		return t({ resetColumns: S }), (t, i) => (n(), O("div", {
			class: "ui-table-scroll cx-table-scroll",
			tabindex: "0",
			"aria-label": "Codex 凭证列表，可横向滚动",
			"aria-busy": e.loading
		}, [y("table", {
			class: "ui-table ui-table--sticky-end cx-table",
			style: h({ "--ui-table-width": `${D(f)}px` })
		}, [
			i[13] ||= y("caption", { class: "ui-sr-only" }, "Codex 凭证，支持跨页选择", -1),
			y("colgroup", null, [(n(!0), O(m, null, o(D(u), (e, t) => (n(), O("col", {
				key: t,
				style: h({ width: `${e}px` })
			}, null, 4))), 128))]),
			y("thead", null, [y("tr", null, [
				y("th", pe, [y("input", {
					type: "checkbox",
					"aria-label": "全选当前页 Codex 凭证",
					checked: T.value,
					indeterminate: E.value,
					disabled: !e.items.length || e.busy,
					onChange: i[0] ||= (e) => l("selectPage", e.target.checked)
				}, null, 40, me)]),
				(n(!0), O(m, null, o(D(W), (t, r) => (n(), O("th", {
					key: t.key,
					scope: "col"
				}, [c(X, {
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
					onStart: (e) => D(p)(r + 1, e),
					onNudge: (e) => D(b)(r + 1, e)
				}, null, 8, [
					"label",
					"onStart",
					"onNudge"
				])]))), 128)),
				i[3] ||= y("th", { scope: "col" }, "操作", -1)
			])]),
			y("tbody", null, [(n(!0), O(m, null, o(M.value, ({ row: t, key: a, credential: o, oauth: s }) => (n(), O("tr", {
				key: a,
				class: C({ "is-selected": e.selected.has(t.filename) })
			}, [
				y("td", he, [y("input", {
					type: "checkbox",
					"aria-label": `选择凭证 ${t.filename}`,
					checked: e.selected.has(t.filename),
					disabled: e.busy,
					onChange: (e) => l("select", t.filename, e.target.checked)
				}, null, 40, ge)]),
				y("td", _e, [c(F, {
					text: t.email || t.filename,
					secondary: t.email ? t.filename : void 0,
					title: `${t.email || ""} · 文件：${t.filename}${t.archived ? " · 已归档" : ""}`
				}, null, 8, [
					"text",
					"secondary",
					"title"
				]), y("div", {
					class: "cx-mobile-summary",
					title: [
						H(t.plan),
						o.title,
						s.title
					].join("；")
				}, _([
					H(t.plan),
					o.label,
					s.label
				].join(" · ")), 9, ve)]),
				y("td", ye, [c(F, { text: H(t.plan) }, null, 8, ["text"])]),
				y("td", be, [c(F, {
					text: o.label,
					title: o.title,
					tone: o.tone
				}, {
					default: r(() => [y("span", { class: C(["ui-badge cx-badge", `ui-badge--${o.tone}`]) }, _(o.label), 3)]),
					_: 2
				}, 1032, [
					"text",
					"title",
					"tone"
				])]),
				y("td", xe, [c(F, {
					text: s.label,
					title: s.title,
					tone: s.tone
				}, {
					default: r(() => [y("span", { class: C(["ui-badge cx-badge", `ui-badge--${s.tone}`]) }, _(s.label), 3)]),
					_: 2
				}, 1032, [
					"text",
					"title",
					"tone"
				])]),
				y("td", Se, [c(F, { text: H(t.account_id) }, null, 8, ["text"])]),
				y("td", Ce, [c(F, { text: H(t.sub2api_account_id) }, null, 8, ["text"])]),
				y("td", we, [c(F, x({ ref_for: !0 }, D(B)(t.mtime), { title: H(t.mtime) }), null, 16, ["title"])]),
				y("td", Te, [c(F, x({ ref_for: !0 }, D(B)(t.expired), { title: H(t.expired) }), null, 16, ["title"])]),
				y("td", Ee, [y("div", De, [y("button", {
					type: "button",
					class: "ui-link cx-direct-download",
					"data-codex-download": t.filename,
					disabled: e.busy,
					onClick: (e) => V("download", t)
				}, "下载凭证", 8, Oe), c(D(j), {
					open: e.visible && L.value === a,
					modal: !1,
					"onUpdate:open": (e) => ee(a, e)
				}, {
					default: r(() => [c(D(A), { "as-child": "" }, {
						default: r(() => [y("button", {
							type: "button",
							class: "ui-button",
							"aria-label": `更多操作 ${t.filename}`,
							disabled: e.busy
						}, "更多", 8, ke)]),
						_: 2
					}, 1024), c(D(P), null, {
						default: r(() => [c(D(I), {
							class: "cx-row-menu",
							"aria-label": `${t.email || t.filename} 的凭证详情与操作`,
							side: "bottom",
							align: "end",
							"side-offset": 6,
							"collision-padding": 10,
							"hide-when-detached": ""
						}, {
							default: r(() => [y("dl", Ae, [
								i[5] ||= y("dt", null, "邮箱 / 文件", -1),
								y("dd", null, [
									k(_(t.email || "—"), 1),
									i[4] ||= y("br", null, null, -1),
									k(_(t.filename), 1)
								]),
								i[6] ||= y("dt", null, "Plan", -1),
								y("dd", null, _(H(t.plan)), 1),
								i[7] ||= y("dt", null, "凭证状态", -1),
								y("dd", null, _(o.title), 1),
								i[8] ||= y("dt", null, "OAuth 状态", -1),
								y("dd", null, _(s.label) + " · " + _(s.title), 1),
								i[9] ||= y("dt", null, "Account ID", -1),
								y("dd", null, _(H(t.account_id)), 1),
								i[10] ||= y("dt", null, "Sub2API ID", -1),
								y("dd", null, _(H(t.sub2api_account_id)), 1),
								i[11] ||= y("dt", null, "更新时间", -1),
								y("dd", null, _(H(t.mtime)), 1),
								i[12] ||= y("dt", null, "过期时间", -1),
								y("dd", null, _(H(t.expired)), 1)
							]), y("div", je, [
								y("button", {
									type: "button",
									"data-codex-download": t.filename,
									disabled: e.busy,
									onClick: (e) => V("download", t)
								}, "下载凭证", 8, Me),
								y("button", {
									type: "button",
									"data-codex-reauthorize": t.filename,
									disabled: e.busy,
									onClick: (e) => V("reauthorize", t)
								}, "重跑授权", 8, Ne),
								y("button", {
									type: "button",
									"data-codex-download-cpa": t.filename,
									disabled: e.busy,
									onClick: (e) => V("downloadCpa", t)
								}, "从 CPA 下载", 8, Pe),
								y("button", {
									type: "button",
									"data-codex-refresh-token": t.filename,
									disabled: e.busy,
									onClick: (e) => V("refreshToken", t)
								}, "刷新 OAuth Token", 8, Fe),
								y("button", {
									type: "button",
									"data-codex-upload-sub2": t.filename,
									disabled: e.busy,
									onClick: (e) => V("uploadSub2", t)
								}, "上传 sub2api", 8, Ie),
								Number(t.exported_count || 0) > 0 ? (n(), O("button", {
									key: 0,
									type: "button",
									"data-codex-reset": t.filename,
									disabled: e.busy,
									onClick: (e) => V("reset", t)
								}, "重置标记", 8, Le)) : d("", !0),
								y("button", {
									type: "button",
									"data-codex-archive": t.filename,
									"data-archived": t.archived ? "0" : "1",
									disabled: e.busy,
									onClick: (e) => V("archive", t)
								}, _(t.archived ? "恢复" : "归档"), 9, Re),
								y("button", {
									type: "button",
									class: "cx-danger",
									"data-codex-delete": t.filename,
									disabled: e.busy,
									onClick: (e) => V("delete", t)
								}, "删除凭证", 8, ze)
							])]),
							_: 2
						}, 1032, ["aria-label"])]),
						_: 2
					}, 1024)]),
					_: 2
				}, 1032, ["open", "onUpdate:open"])])])
			], 2))), 128)), e.items.length ? d("", !0) : (n(), v(N, {
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
		], 4)], 8, fe));
	}
});
// src/api/codex.ts
function Ve() {
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
function He(e, t) {
	let n = /filename\*=UTF-8''([^;]+)/i.exec(e)?.[1], r = /filename=(?:"([^"]+)"|([^;]+))/i.exec(e), i = r?.[1] || r?.[2]?.trim() || t;
	if (n) try {
		i = decodeURIComponent(n.trim());
	} catch {}
	return i.replace(/[\\/\x00-\x1f\x7f]/g, "_") || t;
}
function Ue(e, t) {
	let n = e.error, r = typeof n == "string" ? n : Q(n).message, i = Array.isArray(e.errors) ? e.errors.slice(0, 3).map((e) => {
		let t = Q(e);
		return typeof t.filename == "string" && typeof t.error == "string" ? `${t.filename}: ${t.error}` : "";
	}).filter(Boolean) : [];
	return new U((typeof r == "string" ? r : `下载失败（HTTP ${t}）`) + (i.length ? `；${i.join("；")}` : ""), t, typeof Q(n).code == "string" ? String(Q(n).code) : typeof e.error_code == "string" ? e.error_code : "");
}
async function We(e, t, n, r, i) {
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
		if (!a.ok || l.ok === !1 || l.error) throw Ue(l, a.status);
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
		filename: He(s, t),
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
	download: (e, t = !1) => We(`/api/codex/${t ? "download-from-cpa" : "download"}/${encodeURIComponent(e)}`, t ? e.replace(/-cpa-callback\.json$/i, "-free.json") : e, [e], "single"),
	downloadBulk: (e, t = !1) => We(`/api/codex/${t ? "download-bulk-from-cpa" : "download-bulk"}`, t ? "codex-cpa-bulk.zip" : "codex-bulk.json", e, t ? "zip" : "bulk", { filenames: e })
}, Ge = /* @__PURE__ */ new Set([
	"download",
	"downloadCpa",
	"archive",
	"delete",
	"reset"
]), Ke = /* @__PURE__ */ new Set([
	"refreshToken",
	"reauthorize",
	"uploadSub2"
]), qe = {
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
function Je(e) {
	return e instanceof Error ? e.message : "请求失败，请稍后重试。";
}
function Ye(e = []) {
	return e.filter((e) => e.accepted !== !1).map((e) => e.filename).filter((e) => typeof e == "string" && !!e);
}
function Xe(e) {
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
function Ze(e, t, n, r, i) {
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
function Qe(e) {
	let t = g(!1), n = g(""), r = g(!1), { callbacks: i } = e;
	function a(t, n) {
		let r = new Set(e.selected.value), i = new Set(n);
		for (let e of t) i.has(e) && r.delete(e);
		e.selected.value = r;
	}
	async function o() {
		try {
			await e.refresh();
		} catch (e) {
			n.value = `操作已完成，但列表刷新失败：${Je(e)}`, i.notify(n.value);
		}
	}
	async function s(s, c, l) {
		if (t.value) return;
		let u = [...new Set((c ?? [...e.selected.value]).filter((e) => !!e))];
		if (!u.length) return;
		t.value = !0, n.value = "";
		let d = !(l?.archived ?? e.archived.value);
		try {
			let t = Ge.has(s) ? 1 : Ke.has(s) ? 500 : 1e3;
			if (u.length > t) throw Error(`单次最多 ${t} 个凭证，请调整选择后重试。`);
			let n = Ze(s, u, d, e, l);
			if (n && !await i.confirm(n)) return;
			let c = u[0];
			switch (s) {
				case "download":
				case "downloadCpa":
				case "downloadBulk":
				case "downloadBulkCpa": {
					let e = s === "downloadBulk" || s === "downloadBulkCpa", t = s === "downloadCpa" || s === "downloadBulkCpa", n = e ? await $.downloadBulk(u, t) : await $.download(c, t);
					Xe(n), e && a(n.acknowledged, u), i.notify(e ? t ? "已从 CPA 下载 ZIP，成功与失败详情见 manifest.json" : n.acknowledged.length ? `已打包下载 ${n.acknowledged.length} 个${n.failed ? `，${n.failed} 个失败` : ""}` : "成功 0 个，已下载错误清单" : t ? "已从 CPA 下载" : "已下载 JSON"), await o();
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
					a(Ye(e.started), u);
					let t = e.skipped?.length || 0;
					i.notify(t ? `已开始${s === "refreshToken" ? "刷新" : "重跑"} ${e.started_count || 0} 个，跳过 ${t} 个` : e.message || `已开始${s === "refreshToken" ? "刷新 OAuth Token" : "重跑 Codex 授权"}`), i.openTasks(s === "refreshToken" ? "codex_token_refresh" : "codex_retry");
					break;
				}
				case "uploadSub2": {
					let e = await $.uploadSub2(u), t = (e.failed_count || 0) + (e.skipped_count || 0);
					if (a(Ye(e.accepted ? e.queued : e.uploaded), u), e.accepted) {
						let n = e.queued || [], a = n.some((e) => e.accepted && Number(e.task_id));
						i.notify(`手动上传已入队 ${e.queued_count || 0} 个${t ? `，${t} 个未入队` : ""}${a ? "，可点击“查看上传进度”查看最终结果" : ""}`), i.track(n, "手动上传", { navigate: !1 }), r.value ||= a;
					} else i.notify(t ? `已上传 ${e.uploaded_count || 0} 个，${t} 个未完成` : `已上传 ${e.uploaded_count || 0} 个到 sub2api`), await o();
					break;
				}
			}
		} catch (e) {
			n.value = `${qe[s]}失败: ${Je(e)}`, i.notify(n.value);
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
function $e() {
	let t = s(Ve()), n = g([]), r = g({}), i = g(0), a = g(1), o = g(20), c = g(!1), l = g(/* @__PURE__ */ new Set()), d = g(!1), f = g(""), p = g(!1), m = w(() => Math.max(1, Math.ceil(i.value / o.value))), h = /* @__PURE__ */ new Set([
		"q",
		"account_id",
		"sub2api_id"
	]), _ = 0, v = 0, y = !1, b = null, x;
	function S() {
		++_, ++v, clearTimeout(x), x = void 0, b?.abort(), b = null, d.value = !1;
	}
	function C() {
		return !y && p.value && !document.hidden;
	}
	function T(t = 0) {
		S();
		let n = v;
		if (!C()) return;
		let r = () => {
			n === v && C() && D();
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
		if (S(), !C()) return;
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
				if (e !== _ || !C()) return;
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
		let r = n.every((e) => h.has(e));
		r || (l.value = /* @__PURE__ */ new Set()), T(r ? 250 : 0);
	}
	function N() {
		y || (Object.assign(t, Ve()), l.value = /* @__PURE__ */ new Set(), a.value = 1, T());
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
var et = {
	class: "cx-root",
	"aria-label": "Codex 授权"
}, tt = { class: "ui-list cx-workspace" }, nt = {
	id: "codexToolbarV2",
	class: "ui-list-toolbar cx-toolbar"
}, rt = { class: "ui-list-toolbar__main cx-toolbar-main" }, it = {
	class: "ui-list-count cx-count",
	role: "status"
}, at = { key: 0 }, ot = {
	key: 0,
	id: "codexSelectedHintV2",
	class: "cx-selected",
	role: "status"
}, st = { class: "ui-list-toolbar__actions cx-toolbar-utilities" }, ct = ["disabled"], lt = {
	key: 0,
	class: "ui-list-bulkbar cx-bulk-actions",
	role: "group",
	"aria-label": "选中凭证批量操作"
}, ut = [
	"id",
	"title",
	"disabled",
	"onClick"
], dt = {
	key: 1,
	class: "ui-list-feedback is-error cx-feedback",
	role: "alert"
}, ft = /* @__PURE__ */ t({
	__name: "CodexCredentials",
	props: { callbacks: {} },
	setup(e, { expose: t }) {
		let r = e, i = $e(), { items: s, facets: l, total: u, page: f, size: p, pages: h, archived: v, selected: x, loading: S, error: T, visible: A, filters: j } = i, M = Qe({
			selected: x,
			items: s,
			archived: v,
			refresh: i.refresh,
			callbacks: r.callbacks
		}), { busy: N, error: P, uploadProgress: F } = M, I = g(), R = g(null), z = g(!document.hidden), B = w(() => q(j, l.value)), V = [
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
		function H(e) {
			e || (R.value = null), i.setVisible(e);
		}
		function U(e) {
			R.value = null, i.setArchived(e);
		}
		async function W() {
			await i.refresh();
		}
		function G(e, t) {
			M.run(e, [t.filename], t);
		}
		function K(e) {
			i.updateFilters(J(j, e));
		}
		let Y = () => {
			z.value = !document.hidden, document.hidden && (R.value = null);
		};
		return document.addEventListener("visibilitychange", Y), b(() => document.removeEventListener("visibilitychange", Y)), t({
			refresh: W,
			setVisible: H,
			setArchived: U
		}), (e, t) => a((n(), O("section", et, [y("div", tt, [
			y("div", nt, [y("div", rt, [
				y("span", it, [k(_(D(u).toLocaleString()) + " 个凭证", 1), D(v) ? (n(), O("span", at, " · 已归档")) : d("", !0)]),
				D(x).size ? (n(), O("span", ot, "已选 " + _(D(x).size) + " 项", 1)) : d("", !0),
				c(L, {
					items: B.value,
					onRemove: K
				}, null, 8, ["items"])
			]), y("div", st, [
				c(X, {
					"model-value": D(j),
					facets: D(l),
					open: z.value && R.value === "all",
					"onUpdate:modelValue": D(i).updateFilters,
					"onUpdate:open": t[0] ||= (e) => R.value = e ? "all" : null
				}, null, 8, [
					"model-value",
					"facets",
					"open",
					"onUpdate:modelValue"
				]),
				B.value.length ? (n(), O("button", {
					key: 0,
					id: "btnResetCodexFiltersV2",
					type: "button",
					class: "ui-link",
					onClick: t[1] ||= (...e) => D(i).resetFilters && D(i).resetFilters(...e)
				}, "清除筛选")) : d("", !0),
				D(F) ? (n(), O("button", {
					key: 1,
					id: "btnCodexUploadProgressV2",
					type: "button",
					class: "ui-button",
					onClick: t[2] ||= (...e) => D(M).showProgress && D(M).showProgress(...e)
				}, "查看上传进度")) : d("", !0),
				y("button", {
					id: "btnResetCodexColumnsV2",
					type: "button",
					class: "ui-link cx-reset-columns",
					title: "恢复 Codex 列表默认列宽",
					onClick: t[3] ||= (e) => I.value?.resetColumns()
				}, "恢复列宽"),
				y("button", {
					id: "btnRefreshCodexV2",
					type: "button",
					class: "ui-button",
					disabled: D(S),
					onClick: W
				}, _(D(S) ? "刷新中…" : "刷新"), 9, ct)
			])]),
			D(x).size ? (n(), O("div", lt, [(n(), O(m, null, o(V, (e) => y("button", {
				id: e.id,
				key: e.kind,
				type: "button",
				class: C(["ui-button", { "ui-button--danger": e.danger }]),
				title: e.title,
				disabled: D(N),
				onClick: (t) => D(M).run(e.kind)
			}, _(e.kind === "archiveBulk" && D(v) ? "恢复选中" : e.label), 11, ut)), 64))])) : d("", !0),
			D(P) || D(T) && D(s).length ? (n(), O("div", dt, [y("span", null, _(D(P) || D(T)), 1), D(T) ? (n(), O("button", {
				key: 0,
				type: "button",
				class: "ui-link",
				onClick: W
			}, "重试")) : d("", !0)])) : d("", !0),
			c(Be, {
				ref_key: "table",
				ref: I,
				items: D(s),
				selected: D(x),
				filters: D(j),
				facets: D(l),
				loading: D(S),
				error: D(T),
				busy: D(N),
				visible: D(A) && z.value,
				"open-filter": R.value,
				"onUpdate:openFilter": t[4] ||= (e) => R.value = e,
				"onUpdate:filters": D(i).updateFilters,
				onSelect: D(i).toggle,
				onSelectPage: D(i).togglePage,
				onAction: G,
				onRetry: W
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
			c(ee, {
				page: D(f),
				size: D(p),
				pages: D(h),
				total: D(u),
				busy: D(S),
				"page-sizes": [
					10,
					20,
					30,
					50,
					100
				],
				label: "Codex 凭证分页",
				"onUpdate:page": D(i).setPage,
				"onUpdate:size": D(i).setSize
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		])], 512)), [[E, D(A)]]);
	}
});
// src/codex.ts
function pt(e, t) {
	return T(ft, { callbacks: t }).mount(e);
}
export { pt as mountCodexCredentials };
