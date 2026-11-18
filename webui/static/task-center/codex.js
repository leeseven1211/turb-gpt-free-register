import { $ as e, A as t, B as n, G as r, I as i, O as a, P as o, S as s, V as c, W as l, X as u, Z as d, _ as f, b as p, c as m, ct as h, dt as g, g as _, i as v, k as y, m as b, n as x, o as S, ot as C, p as w, s as T, u as E, ut as D, x as O } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { a as k, i as A, n as j, o as M, r as N, s as P, t as F } from "./ListFilterSummary-NiVwXoAn.js";
import { t as I } from "./ListPagination-CFFXEHba.js";
import { t as L } from "./useColumnWidths-DKwoq5eG.js";
import { t as R } from "./time-DOD6oyhP.js";
import { n as z, r as B, t as V } from "./client-BBEPwkQG.js";
// src/features/codex/filterDefinitions.ts
var H = [
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
], U = {
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
function W(e, t) {
	return e === "plan" ? t === "unqueried" ? "未查询" : t ? t.charAt(0).toUpperCase() + t.slice(1) : "-" : U[e]?.[t] || t || "-";
}
function G(e, t) {
	return H.flatMap((n) => {
		let r = e[n.fields[0]];
		if (n.kind === "date-range") {
			let t = e.date_from, n = e.date_to;
			r = t && n ? `${t} 至 ${n}` : t ? `自 ${t}` : n ? `截至 ${n}` : "";
		} else n.kind === "enum" && r && (r = t[n.key]?.find((e) => e.value === r)?.label || W(n.key, r));
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
function K(e, t) {
	let n = { ...e };
	for (let e of H.find((e) => e.key === t)?.fields || []) n[e] = "";
	return n;
}
// src/features/codex/CodexFilters.vue?vue&type=script&setup=true&lang.ts
var q = { class: "cx-filter-fields" }, J = {
	key: 0,
	class: "cx-filter-field"
}, Y = ["value"], X = {
	key: 1,
	class: "cx-filter-options"
}, ee = { class: "cx-sr-only" }, te = ["name", "checked"], ne = [
	"name",
	"value",
	"checked",
	"onChange",
	"onClick"
], re = [
	"type",
	"aria-label",
	"value",
	"placeholder",
	"onInput"
], ie = { class: "cx-filter-actions" }, ae = /* @__PURE__ */ s({
	__name: "CodexFilters",
	props: {
		modelValue: {},
		facets: {},
		open: { type: Boolean },
		column: {}
	},
	emits: ["update:modelValue", "update:open"],
	setup(t, { emit: a }) {
		let s = t, c = a, u = e("q"), d = n(), y = w(() => s.column || H.find((e) => e.key === u.value) || H[0]), x = w(() => s.column ? s.column.fields.some((e) => !!s.modelValue[e]) : Object.values(s.modelValue).some(Boolean)), S = w(() => G(s.modelValue, s.facets).find((e) => e.key === y.value.key)?.label || ""), D = w(() => {
			let e = y.value.fields[0], t = (s.facets[y.value.key] || []).filter((e) => y.value.key !== "status" || e.value !== "archived"), n = s.modelValue[e], r = t.map((e) => ({
				...e,
				label: e.label || W(y.value.key, e.value)
			}));
			return n && !r.some((e) => e.value === n) && r.unshift({
				value: n,
				label: W(y.value.key, n),
				count: 0
			}), r;
		});
		function k(e, t) {
			c("update:modelValue", {
				...s.modelValue,
				[e]: t
			});
		}
		function A() {
			c("update:modelValue", K(s.modelValue, y.value.key)), c("update:open", !1);
		}
		function j(e, t, n) {
			e.detail <= 0 || (k(t, n), c("update:open", !1));
		}
		return (e, n) => (o(), f("div", { class: h({ "cx-all-filters": !t.column }) }, [O(N, {
			label: t.column?.label || "凭证",
			"trigger-label": t.column ? void 0 : "筛选",
			active: x.value,
			summary: S.value,
			open: t.open,
			"onUpdate:open": n[5] ||= (e) => c("update:open", e)
		}, {
			default: l(() => [b("div", q, [
				t.column ? _("", !0) : (o(), f("label", J, [n[6] ||= p("筛选列", -1), r(b("select", {
					"onUpdate:modelValue": n[0] ||= (e) => u.value = e,
					"aria-label": "选择筛选列"
				}, [(o(!0), f(E, null, i(C(H), (e) => (o(), f("option", {
					key: e.key,
					value: e.key
				}, g(e.label), 9, Y))), 128))], 512), [[v, u.value]])])),
				y.value.kind === "enum" ? (o(), f("fieldset", X, [
					b("legend", ee, g(y.value.label), 1),
					b("label", null, [b("input", {
						type: "radio",
						name: C(d),
						value: "",
						checked: !t.modelValue[y.value.fields[0]],
						onChange: n[1] ||= (e) => k(y.value.fields[0], ""),
						onClick: n[2] ||= (e) => j(e, y.value.fields[0], "")
					}, null, 40, te), n[7] ||= b("span", null, "全部", -1)]),
					(o(!0), f(E, null, i(D.value, (e) => (o(), f("label", { key: e.value }, [
						b("input", {
							type: "radio",
							name: C(d),
							value: e.value,
							checked: t.modelValue[y.value.fields[0]] === e.value,
							onChange: (t) => k(y.value.fields[0], e.value),
							onClick: (t) => j(t, y.value.fields[0], e.value)
						}, null, 40, ne),
						b("span", null, g(e.label), 1),
						b("small", null, g(e.count), 1)
					]))), 128))
				])) : (o(!0), f(E, { key: 2 }, i(y.value.fields, (e, r) => (o(), f("label", {
					key: e,
					class: "cx-filter-field"
				}, [p(g(y.value.kind === "date-range" ? r ? "截止日期" : "开始日期" : y.value.label) + " ", 1), b("input", {
					type: y.value.kind === "text" ? "text" : "date",
					"aria-label": y.value.kind === "date-range" ? r ? "截止日期" : "开始日期" : y.value.label,
					value: t.modelValue[e],
					placeholder: y.value.placeholder,
					autocomplete: "off",
					onInput: (t) => k(e, t.target.value),
					onKeydown: n[3] ||= T(m((e) => c("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, re)]))), 128)),
				b("div", ie, [b("button", {
					type: "button",
					class: "cx-link",
					onClick: A
				}, "清除此列"), b("button", {
					type: "button",
					class: "cx-button",
					onClick: n[4] ||= (e) => c("update:open", !1)
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
function oe(e) {
	let t = Number(e.exported_count || 0), n = e.exported === !0 || t > 0, r = e.sub2api_account_id != null && String(e.sub2api_account_id).trim() !== "";
	return n && t <= 0 && r ? {
		label: "已关联",
		title: `Sub2API ID ${e.sub2api_account_id} 已有关联记录，本地下载 0 次`,
		tone: "neutral"
	} : n ? {
		label: "已导出",
		title: `导出 ${t} 次，最近 ${e.exported_at || "-"}`,
		tone: "neutral"
	} : {
		label: "未导出",
		title: "没有本地导出或 Sub2API 关联记录",
		tone: "success"
	};
}
function se(e) {
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
var ce = ["aria-busy"], le = { scope: "col" }, ue = [
	"checked",
	"indeterminate",
	"disabled"
], de = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], fe = {
	class: "cx-check",
	"data-label": "选择"
}, pe = [
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], me = {
	class: "cx-identity",
	"data-label": "邮箱 / 文件"
}, he = ["title"], ge = {
	class: "cx-extra",
	"data-label": "Plan"
}, _e = {
	class: "cx-extra",
	"data-label": "凭证状态"
}, ve = {
	class: "cx-extra",
	"data-label": "OAuth 状态"
}, ye = {
	class: "cx-extra",
	"data-label": "Account ID"
}, be = {
	class: "cx-extra",
	"data-label": "Sub2API ID"
}, xe = {
	class: "cx-extra cx-time",
	"data-label": "更新时间"
}, Se = {
	class: "cx-extra cx-time",
	"data-label": "过期时间"
}, Ce = {
	class: "cx-actions",
	"data-label": "操作"
}, we = { class: "cx-row-actions" }, Te = [
	"data-codex-download",
	"disabled",
	"onClick"
], Ee = ["aria-label", "disabled"], De = { class: "cx-row-details" }, Oe = {
	class: "cx-menu-actions",
	role: "group",
	"aria-label": "凭证操作"
}, ke = [
	"data-codex-download",
	"disabled",
	"onClick"
], Ae = [
	"data-codex-reauthorize",
	"disabled",
	"onClick"
], je = [
	"data-codex-download-cpa",
	"disabled",
	"onClick"
], Me = [
	"data-codex-refresh-token",
	"disabled",
	"onClick"
], Ne = [
	"data-codex-upload-sub2",
	"disabled",
	"onClick"
], Pe = [
	"data-codex-reset",
	"disabled",
	"onClick"
], Fe = [
	"data-codex-archive",
	"data-archived",
	"disabled",
	"onClick"
], Ie = [
	"data-codex-delete",
	"disabled",
	"onClick"
], Le = {
	key: 0,
	class: "cx-empty-row"
}, Re = { colspan: "10" }, ze = ["role"], Be = /* @__PURE__ */ s({
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
	setup(t, { expose: n, emit: r }) {
		let s = t, u = r, { widths: d, total: v, resize: y, resizeWithKeyboard: x, resetColumns: S } = L({
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
		}), N = w(() => s.items.length > 0 && s.items.every((e) => s.selected.has(e.filename))), F = w(() => !N.value && s.items.some((e) => s.selected.has(e.filename))), I = w(() => {
			let e = /* @__PURE__ */ new Map();
			return s.items.map((t) => {
				let n = JSON.stringify([t.filename, t.sub2api_account_id ?? null]), r = e.get(n) ?? 0;
				return e.set(n, r + 1), {
					row: t,
					key: JSON.stringify([n, r]),
					credential: oe(t),
					oauth: se(t)
				};
			});
		}), z = e(null);
		c(() => s.visible, (e) => {
			e || (z.value = null);
		}), c(() => s.items, () => {
			z.value = null;
		});
		function B(e, t) {
			t ? z.value = e : z.value === e && (z.value = null);
		}
		function V(e, t) {
			s.busy || (z.value = null, u("action", e, t));
		}
		function U(e) {
			return e == null || e === "" ? "—" : String(e);
		}
		return n({ resetColumns: S }), (e, n) => (o(), f("div", {
			class: "cx-table-scroll",
			tabindex: "0",
			"aria-label": "Codex 凭证列表，可横向滚动",
			"aria-busy": t.loading
		}, [b("table", {
			class: "cx-table",
			style: D({ "--cx-table-width": `${C(v)}px` })
		}, [
			n[13] ||= b("caption", { class: "cx-sr-only" }, "Codex 凭证，支持跨页选择", -1),
			b("colgroup", null, [(o(!0), f(E, null, i(C(d), (e, t) => (o(), f("col", {
				key: t,
				style: D({ width: `${e}px` })
			}, null, 4))), 128))]),
			b("thead", null, [b("tr", null, [
				b("th", le, [b("input", {
					type: "checkbox",
					"aria-label": "全选当前页 Codex 凭证",
					checked: N.value,
					indeterminate: F.value,
					disabled: !t.items.length || t.busy,
					onChange: n[0] ||= (e) => u("selectPage", e.target.checked)
				}, null, 40, ue)]),
				(o(!0), f(E, null, i(C(H), (e, r) => (o(), f("th", {
					key: e.key,
					scope: "col"
				}, [O(ae, {
					column: e,
					"model-value": t.filters,
					facets: t.facets,
					open: t.visible && t.openFilter === e.key,
					"onUpdate:modelValue": n[1] ||= (e) => u("update:filters", e),
					"onUpdate:open": (t) => u("update:openFilter", t ? e.key : null)
				}, null, 8, [
					"column",
					"model-value",
					"facets",
					"open",
					"onUpdate:open"
				]), b("button", {
					type: "button",
					class: "cx-column-resize",
					"aria-label": `调整${e.label}列宽，方向键调整`,
					onPointerdown: m((e) => C(y)(r + 1, e), ["prevent"]),
					onKeydown: [T(m((e) => C(x)(r + 1, -10), ["prevent"]), ["left"]), T(m((e) => C(x)(r + 1, 10), ["prevent"]), ["right"])]
				}, null, 40, de)]))), 128)),
				n[3] ||= b("th", { scope: "col" }, "操作", -1)
			])]),
			b("tbody", null, [(o(!0), f(E, null, i(I.value, ({ row: e, key: r, credential: i, oauth: s }) => (o(), f("tr", {
				key: r,
				class: h({ "cx-row-selected": t.selected.has(e.filename) })
			}, [
				b("td", fe, [b("input", {
					type: "checkbox",
					"aria-label": `选择凭证 ${e.filename}`,
					checked: t.selected.has(e.filename),
					disabled: t.busy,
					onChange: (t) => u("select", e.filename, t.target.checked)
				}, null, 40, pe)]),
				b("td", me, [O(j, {
					text: e.email || e.filename,
					secondary: e.email ? e.filename : void 0,
					title: `${e.email || ""} · 文件：${e.filename}${e.archived ? " · 已归档" : ""}`
				}, null, 8, [
					"text",
					"secondary",
					"title"
				]), b("div", {
					class: "cx-mobile-summary",
					title: [
						U(e.plan),
						i.title,
						s.title
					].join("；")
				}, g([
					U(e.plan),
					i.label,
					s.label
				].join(" · ")), 9, he)]),
				b("td", ge, [O(j, { text: U(e.plan) }, null, 8, ["text"])]),
				b("td", _e, [O(j, {
					text: i.label,
					title: i.title,
					tone: i.tone
				}, {
					default: l(() => [b("span", { class: h(["cx-badge", `cx-badge--${i.tone}`]) }, g(i.label), 3)]),
					_: 2
				}, 1032, [
					"text",
					"title",
					"tone"
				])]),
				b("td", ve, [O(j, {
					text: s.label,
					title: s.title,
					tone: s.tone
				}, {
					default: l(() => [b("span", { class: h(["cx-badge", `cx-badge--${s.tone}`]) }, g(s.label), 3)]),
					_: 2
				}, 1032, [
					"text",
					"title",
					"tone"
				])]),
				b("td", ye, [O(j, { text: U(e.account_id) }, null, 8, ["text"])]),
				b("td", be, [O(j, { text: U(e.sub2api_account_id) }, null, 8, ["text"])]),
				b("td", xe, [O(j, a({ ref_for: !0 }, C(R)(e.mtime), { title: U(e.mtime) }), null, 16, ["title"])]),
				b("td", Se, [O(j, a({ ref_for: !0 }, C(R)(e.expired), { title: U(e.expired) }), null, 16, ["title"])]),
				b("td", Ce, [b("div", we, [b("button", {
					type: "button",
					class: "cx-link cx-direct-download",
					"data-codex-download": e.filename,
					disabled: t.busy,
					onClick: (t) => V("download", e)
				}, "下载凭证", 8, Te), O(C(P), {
					open: t.visible && z.value === r,
					modal: !1,
					"onUpdate:open": (e) => B(r, e)
				}, {
					default: l(() => [O(C(A), { "as-child": "" }, {
						default: l(() => [b("button", {
							type: "button",
							class: "cx-button",
							"aria-label": `更多操作 ${e.filename}`,
							disabled: t.busy
						}, "更多", 8, Ee)]),
						_: 2
					}, 1024), O(C(k), null, {
						default: l(() => [O(C(M), {
							class: "cx-row-menu",
							"aria-label": `${e.email || e.filename} 的凭证详情与操作`,
							side: "bottom",
							align: "end",
							"side-offset": 6,
							"collision-padding": 10,
							"hide-when-detached": ""
						}, {
							default: l(() => [b("dl", De, [
								n[5] ||= b("dt", null, "邮箱 / 文件", -1),
								b("dd", null, [
									p(g(e.email || "—"), 1),
									n[4] ||= b("br", null, null, -1),
									p(g(e.filename), 1)
								]),
								n[6] ||= b("dt", null, "Plan", -1),
								b("dd", null, g(U(e.plan)), 1),
								n[7] ||= b("dt", null, "凭证状态", -1),
								b("dd", null, g(i.title), 1),
								n[8] ||= b("dt", null, "OAuth 状态", -1),
								b("dd", null, g(s.label) + " · " + g(s.title), 1),
								n[9] ||= b("dt", null, "Account ID", -1),
								b("dd", null, g(U(e.account_id)), 1),
								n[10] ||= b("dt", null, "Sub2API ID", -1),
								b("dd", null, g(U(e.sub2api_account_id)), 1),
								n[11] ||= b("dt", null, "更新时间", -1),
								b("dd", null, g(U(e.mtime)), 1),
								n[12] ||= b("dt", null, "过期时间", -1),
								b("dd", null, g(U(e.expired)), 1)
							]), b("div", Oe, [
								b("button", {
									type: "button",
									"data-codex-download": e.filename,
									disabled: t.busy,
									onClick: (t) => V("download", e)
								}, "下载凭证", 8, ke),
								b("button", {
									type: "button",
									"data-codex-reauthorize": e.filename,
									disabled: t.busy,
									onClick: (t) => V("reauthorize", e)
								}, "重跑授权", 8, Ae),
								b("button", {
									type: "button",
									"data-codex-download-cpa": e.filename,
									disabled: t.busy,
									onClick: (t) => V("downloadCpa", e)
								}, "从 CPA 下载", 8, je),
								b("button", {
									type: "button",
									"data-codex-refresh-token": e.filename,
									disabled: t.busy,
									onClick: (t) => V("refreshToken", e)
								}, "刷新 OAuth Token", 8, Me),
								b("button", {
									type: "button",
									"data-codex-upload-sub2": e.filename,
									disabled: t.busy,
									onClick: (t) => V("uploadSub2", e)
								}, "上传 sub2api", 8, Ne),
								Number(e.exported_count || 0) > 0 ? (o(), f("button", {
									key: 0,
									type: "button",
									"data-codex-reset": e.filename,
									disabled: t.busy,
									onClick: (t) => V("reset", e)
								}, "重置标记", 8, Pe)) : _("", !0),
								b("button", {
									type: "button",
									"data-codex-archive": e.filename,
									"data-archived": e.archived ? "0" : "1",
									disabled: t.busy,
									onClick: (t) => V("archive", e)
								}, g(e.archived ? "恢复" : "归档"), 9, Fe),
								b("button", {
									type: "button",
									class: "cx-danger",
									"data-codex-delete": e.filename,
									disabled: t.busy,
									onClick: (t) => V("delete", e)
								}, "删除凭证", 8, Ie)
							])]),
							_: 2
						}, 1032, ["aria-label"])]),
						_: 2
					}, 1024)]),
					_: 2
				}, 1032, ["open", "onUpdate:open"])])])
			], 2))), 128)), t.items.length ? _("", !0) : (o(), f("tr", Le, [b("td", Re, [b("div", {
				class: "cx-empty",
				role: t.error ? "alert" : "status"
			}, [
				b("strong", null, g(t.loading ? "正在加载授权凭证" : t.error ? "凭证列表加载失败" : "没有匹配的凭证"), 1),
				b("p", null, g(t.error || (t.loading ? "正在同步 OAuth 与导出状态" : "可调整筛选条件，或清除全部筛选。")), 1),
				t.error ? (o(), f("button", {
					key: 0,
					type: "button",
					class: "cx-button",
					onClick: n[2] ||= (e) => u("retry")
				}, "重新加载")) : _("", !0)
			], 8, ze)])]))])
		], 4)], 8, ce));
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
	return B(`/api/codex/${e}`, {
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
	return new V((typeof r == "string" ? r : `下载失败（HTTP ${t}）`) + (i.length ? `；${i.join("；")}` : ""), t, typeof Q(n).code == "string" ? String(Q(n).code) : typeof e.error_code == "string" ? e.error_code : "");
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
	if (a.status === 401 || a.redirected) throw new V("登录已失效，请重新登录后刷新。", a.status);
	let o = (a.headers.get("Content-Type") || "").toLowerCase(), s = a.headers.get("Content-Disposition") || "", c = await a.blob();
	if (!c.size) throw new V("下载返回空文件。", a.status);
	let l = {};
	if (o.includes("application/json")) {
		try {
			let e = JSON.parse(await c.text());
			if (!e || typeof e != "object" || Array.isArray(e)) throw Error("invalid");
			l = Q(e);
		} catch {
			throw new V("下载返回无效 JSON。", a.status);
		}
		if (!a.ok || l.ok === !1 || l.error) throw Ue(l, a.status);
	} else if (!a.ok) throw new V(`下载失败（HTTP ${a.status}）`, a.status);
	if (!/attachment/i.test(s)) throw new V("服务返回了非下载附件，请刷新后重试。", a.status);
	if (r === "zip" ? !o.includes("application/zip") : !o.includes("application/json")) throw new V("服务返回了非下载内容，请刷新后重试。", a.status);
	let u = r === "single" ? n : [], d = 0;
	if (r === "bulk") {
		if (!Array.isArray(l.credentials) || typeof l.count != "number") throw new V("下载返回无效的批量凭证附件。", a.status);
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
		return B(`/api/codex?${n}`, { signal: t });
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
function Qe(t) {
	let n = e(!1), r = e(""), i = e(!1), { callbacks: a } = t;
	function o(e, n) {
		let r = new Set(t.selected.value), i = new Set(n);
		for (let t of e) i.has(t) && r.delete(t);
		t.selected.value = r;
	}
	async function s() {
		try {
			await t.refresh();
		} catch (e) {
			r.value = `操作已完成，但列表刷新失败：${Je(e)}`, a.notify(r.value);
		}
	}
	async function c(e, c, l) {
		if (n.value) return;
		let u = [...new Set((c ?? [...t.selected.value]).filter((e) => !!e))];
		if (!u.length) return;
		n.value = !0, r.value = "";
		let d = !(l?.archived ?? t.archived.value);
		try {
			let n = Ge.has(e) ? 1 : Ke.has(e) ? 500 : 1e3;
			if (u.length > n) throw Error(`单次最多 ${n} 个凭证，请调整选择后重试。`);
			let r = Ze(e, u, d, t, l);
			if (r && !await a.confirm(r)) return;
			let c = u[0];
			switch (e) {
				case "download":
				case "downloadCpa":
				case "downloadBulk":
				case "downloadBulkCpa": {
					let t = e === "downloadBulk" || e === "downloadBulkCpa", n = e === "downloadCpa" || e === "downloadBulkCpa", r = t ? await $.downloadBulk(u, n) : await $.download(c, n);
					Xe(r), t && o(r.acknowledged, u), a.notify(t ? n ? "已从 CPA 下载 ZIP，成功与失败详情见 manifest.json" : r.acknowledged.length ? `已打包下载 ${r.acknowledged.length} 个${r.failed ? `，${r.failed} 个失败` : ""}` : "成功 0 个，已下载错误清单" : n ? "已从 CPA 下载" : "已下载 JSON"), await s();
					break;
				}
				case "archive":
				case "archiveBulk": {
					let t = e === "archive" ? await $.archive(c, d) : await $.archiveBulk(u, d);
					o(e === "archive" ? t.filename ? [t.filename] : [] : (t.updated || []).map((e) => e.filename), u), a.notify(e === "archive" ? d ? "已归档" : "已恢复" : `${d ? "归档" : "恢复"}成功 ${t.updated_count || 0} 个`), await s();
					break;
				}
				case "delete":
				case "deleteBulk": {
					let t = e === "delete" ? await $.delete(c) : await $.deleteBulk(u);
					o(typeof t.deleted == "string" ? [t.deleted] : t.deleted || [], u);
					let n = t.skipped?.length || 0;
					a.notify(e === "delete" ? "Codex 凭证已删除" : `已删除 ${t.deleted_count || 0} 个${n ? `，跳过 ${n} 个` : ""}`), await s();
					break;
				}
				case "reset":
					await $.reset(c), a.notify("已重置"), await s();
					break;
				case "refreshToken":
				case "reauthorize": {
					let t = e === "refreshToken" ? await $.refreshToken(u) : await $.reauthorize(u);
					o(Ye(t.started), u);
					let n = t.skipped?.length || 0;
					a.notify(n ? `已开始${e === "refreshToken" ? "刷新" : "重跑"} ${t.started_count || 0} 个，跳过 ${n} 个` : t.message || `已开始${e === "refreshToken" ? "刷新 OAuth Token" : "重跑 Codex 授权"}`), a.openTasks(e === "refreshToken" ? "codex_token_refresh" : "codex_retry");
					break;
				}
				case "uploadSub2": {
					let e = await $.uploadSub2(u), t = (e.failed_count || 0) + (e.skipped_count || 0);
					if (o(Ye(e.accepted ? e.queued : e.uploaded), u), e.accepted) {
						let n = e.queued || [], r = n.some((e) => e.accepted && Number(e.task_id));
						a.notify(`手动上传已入队 ${e.queued_count || 0} 个${t ? `，${t} 个未入队` : ""}${r ? "，可点击“查看上传进度”查看最终结果" : ""}`), a.track(n, "手动上传", { navigate: !1 }), i.value ||= r;
					} else a.notify(t ? `已上传 ${e.uploaded_count || 0} 个，${t} 个未完成` : `已上传 ${e.uploaded_count || 0} 个到 sub2api`), await s();
					break;
				}
			}
		} catch (t) {
			r.value = `${qe[e]}失败: ${Je(t)}`, a.notify(r.value);
		} finally {
			n.value = !1;
		}
	}
	return {
		busy: n,
		error: r,
		uploadProgress: i,
		run: c,
		showProgress: () => a.openTasks()
	};
}
// src/features/codex/useCodexList.ts
function $e() {
	let t = d(Ve()), n = e([]), r = e({}), i = e(0), a = e(1), o = e(20), s = e(!1), c = e(/* @__PURE__ */ new Set()), l = e(!1), f = e(""), p = e(!1), m = w(() => Math.max(1, Math.ceil(i.value / o.value))), h = /* @__PURE__ */ new Set([
		"q",
		"account_id",
		"sub2api_id"
	]), g = 0, _ = 0, v = !1, b = null, x;
	function S() {
		++g, ++_, clearTimeout(x), x = void 0, b?.abort(), b = null, l.value = !1;
	}
	function C() {
		return !v && p.value && !document.hidden;
	}
	function T(e = 0) {
		S();
		let t = _;
		if (!C()) return;
		let n = () => {
			t === _ && C() && D();
		};
		e ? x = setTimeout(n, e) : y(n);
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
		let e = g, c = new AbortController();
		b = c, l.value = !0;
		try {
			for (let l = 0; l < 2; l++) {
				let u = {
					page: a.value,
					size: o.value,
					archived: s.value,
					filters: { ...t }
				}, d = await $.list(u, c.signal);
				if (e !== g || !C()) return;
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
			e === g && !z(t) && (f.value = t instanceof Error ? t.message : "Codex 凭证加载失败");
		} finally {
			e === g && (l.value = !1, b = null);
		}
	}
	function O(e) {
		v || e === p.value || (p.value = e, e ? T() : S());
	}
	function k(e) {
		v || e === s.value || (s.value = e, c.value = /* @__PURE__ */ new Set(), n.value = [], r.value = {}, i.value = 0, a.value = 1, f.value = "", T());
	}
	function A(e) {
		if (v || !Number.isFinite(e)) return;
		let t = Math.min(m.value, Math.max(1, Math.floor(e)));
		t !== a.value && (a.value = t, T());
	}
	function j(e) {
		if (v || !Number.isFinite(e) || e < 1) return;
		let t = Math.min(500, Math.floor(e));
		t !== o.value && (o.value = t, a.value = 1, T());
	}
	function M(e) {
		if (v) return;
		let n = Object.keys(t).filter((n) => e[n] !== void 0 && e[n] !== t[n]);
		if (!n.length) return;
		for (let r of n) t[r] = e[r];
		a.value = 1;
		let r = n.every((e) => h.has(e));
		r || (c.value = /* @__PURE__ */ new Set()), T(r ? 250 : 0);
	}
	function N() {
		v || (Object.assign(t, Ve()), c.value = /* @__PURE__ */ new Set(), a.value = 1, T());
	}
	function P(e, t) {
		let n = new Set(c.value);
		t ? n.add(e) : n.delete(e), c.value = n;
	}
	function F(e) {
		let t = new Set(c.value);
		for (let r of n.value) e ? t.add(r.filename) : t.delete(r.filename);
		c.value = t;
	}
	let I = () => {
		document.hidden ? S() : p.value && T();
	};
	return document.addEventListener("visibilitychange", I), u(() => {
		v = !0, S(), document.removeEventListener("visibilitychange", I);
	}), {
		filters: t,
		items: n,
		facets: r,
		total: i,
		page: a,
		size: o,
		pages: m,
		archived: s,
		selected: c,
		loading: l,
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
}, tt = { class: "cx-workspace" }, nt = {
	id: "codexToolbarV2",
	class: "cx-toolbar"
}, rt = { class: "cx-toolbar-main" }, it = {
	class: "cx-count",
	role: "status"
}, at = { key: 0 }, ot = {
	key: 0,
	id: "codexSelectedHintV2",
	class: "cx-selected",
	role: "status"
}, st = { class: "cx-toolbar-utilities" }, ct = ["disabled"], lt = {
	key: 0,
	class: "cx-bulk-actions",
	role: "group",
	"aria-label": "选中凭证批量操作"
}, ut = [
	"id",
	"title",
	"disabled",
	"onClick"
], dt = {
	key: 1,
	class: "cx-feedback",
	role: "alert"
}, ft = /* @__PURE__ */ s({
	__name: "CodexCredentials",
	props: { callbacks: {} },
	setup(n, { expose: a }) {
		let s = n, c = $e(), { items: l, facets: u, total: d, page: m, size: v, pages: y, archived: x, selected: T, loading: D, error: k, visible: A, filters: j } = c, M = Qe({
			selected: T,
			items: l,
			archived: x,
			refresh: c.refresh,
			callbacks: s.callbacks
		}), { busy: N, error: P, uploadProgress: L } = M, R = e(), z = e(null), B = e(!document.hidden), V = w(() => G(j, u.value)), H = [
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
			e || (z.value = null), c.setVisible(e);
		}
		function W(e) {
			z.value = null, c.setArchived(e);
		}
		async function q() {
			await c.refresh();
		}
		function J(e, t) {
			M.run(e, [t.filename], t);
		}
		function Y(e) {
			c.updateFilters(K(j, e));
		}
		let X = () => {
			B.value = !document.hidden, document.hidden && (z.value = null);
		};
		return document.addEventListener("visibilitychange", X), t(() => document.removeEventListener("visibilitychange", X)), a({
			refresh: q,
			setVisible: U,
			setArchived: W
		}), (e, t) => r((o(), f("section", et, [b("div", tt, [
			b("div", nt, [b("div", rt, [
				b("span", it, [p(g(C(d).toLocaleString()) + " 个凭证", 1), C(x) ? (o(), f("span", at, " · 已归档")) : _("", !0)]),
				C(T).size ? (o(), f("span", ot, "已选 " + g(C(T).size) + " 项", 1)) : _("", !0),
				O(F, {
					items: V.value,
					onRemove: Y
				}, null, 8, ["items"])
			]), b("div", st, [
				O(ae, {
					"model-value": C(j),
					facets: C(u),
					open: B.value && z.value === "all",
					"onUpdate:modelValue": C(c).updateFilters,
					"onUpdate:open": t[0] ||= (e) => z.value = e ? "all" : null
				}, null, 8, [
					"model-value",
					"facets",
					"open",
					"onUpdate:modelValue"
				]),
				V.value.length ? (o(), f("button", {
					key: 0,
					id: "btnResetCodexFiltersV2",
					type: "button",
					class: "cx-link",
					onClick: t[1] ||= (...e) => C(c).resetFilters && C(c).resetFilters(...e)
				}, "清除筛选")) : _("", !0),
				C(L) ? (o(), f("button", {
					key: 1,
					id: "btnCodexUploadProgressV2",
					type: "button",
					class: "cx-button",
					onClick: t[2] ||= (...e) => C(M).showProgress && C(M).showProgress(...e)
				}, "查看上传进度")) : _("", !0),
				b("button", {
					id: "btnResetCodexColumnsV2",
					type: "button",
					class: "cx-link cx-reset-columns",
					title: "恢复 Codex 列表默认列宽",
					onClick: t[3] ||= (e) => R.value?.resetColumns()
				}, "恢复列宽"),
				b("button", {
					id: "btnRefreshCodexV2",
					type: "button",
					class: "cx-button",
					disabled: C(D),
					onClick: q
				}, g(C(D) ? "刷新中…" : "刷新"), 9, ct)
			])]),
			C(T).size ? (o(), f("div", lt, [(o(), f(E, null, i(H, (e) => b("button", {
				id: e.id,
				key: e.kind,
				type: "button",
				class: h(["cx-button", { "cx-danger": e.danger }]),
				title: e.title,
				disabled: C(N),
				onClick: (t) => C(M).run(e.kind)
			}, g(e.kind === "archiveBulk" && C(x) ? "恢复选中" : e.label), 11, ut)), 64))])) : _("", !0),
			C(P) || C(k) && C(l).length ? (o(), f("div", dt, [b("span", null, g(C(P) || C(k)), 1), C(k) ? (o(), f("button", {
				key: 0,
				type: "button",
				class: "cx-link",
				onClick: q
			}, "重试")) : _("", !0)])) : _("", !0),
			O(Be, {
				ref_key: "table",
				ref: R,
				items: C(l),
				selected: C(T),
				filters: C(j),
				facets: C(u),
				loading: C(D),
				error: C(k),
				busy: C(N),
				visible: C(A) && B.value,
				"open-filter": z.value,
				"onUpdate:openFilter": t[4] ||= (e) => z.value = e,
				"onUpdate:filters": C(c).updateFilters,
				onSelect: C(c).toggle,
				onSelectPage: C(c).togglePage,
				onAction: J,
				onRetry: q
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
			O(I, {
				page: C(m),
				size: C(v),
				pages: C(y),
				total: C(d),
				busy: C(D),
				"page-sizes": [
					10,
					20,
					30,
					50,
					100
				],
				label: "Codex 凭证分页",
				"onUpdate:page": C(c).setPage,
				"onUpdate:size": C(c).setSize
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		])], 512)), [[S, C(A)]]);
	}
});
// src/codex.ts
function pt(e, t) {
	return x(ft, { callbacks: t }).mount(e);
}
export { pt as mountCodexCredentials };
