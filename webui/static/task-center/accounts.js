import { $ as e, A as t, C as n, F as r, G as i, H as a, K as o, L as s, M as c, N as l, P as u, R as d, S as f, X as p, Z as m, _ as h, a as g, c as _, d as v, dt as y, et as b, f as x, ft as S, g as C, h as w, j as T, k as E, l as D, lt as O, m as k, n as A, nt as j, o as M, s as N, st as P, t as F, tt as I, v as L, x as R } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { a as z, i as B, n as V, o as H, r as U, s as W, t as G } from "./ListFilterSummary-BjcCEzgL.js";
import { t as K } from "./ListPagination-CSFkV2Gz.js";
import { a as q, i as J, n as Y, o as X, r as ee, s as te, t as ne } from "./queryAdapter-DOc4xJ_Q.js";
import { n as re, t as ie } from "./ColumnResizer-XOclQup1.js";
import { t as ae } from "./TableState-CxHYH8ID.js";
import { t as oe } from "./errorLabels-BfdVjKfW.js";
import { n as se, r as ce, t as le } from "./client-B5R_MNgP.js";
import { a as ue, n as de } from "./taskIds-BlchWwUp.js";
import { a as fe, i as pe, t as me } from "./bulkMutations-3wwPI3-H.js";
// src/features/accounts/accountToolbar.ts
var he = Object.freeze([
	"查询",
	"处理",
	"运维",
	"服务",
	"账号"
]), ge = Object.freeze([
	Object.freeze({
		id: "btnCheckSelectedPlansV2",
		label: "查套餐",
		section: "查询",
		action: "checkSelectedPlans",
		className: "jobs-tb-btn",
		title: "查询选中账号当前套餐，并检查 free 账号可用的 Plus 免费试用或折扣优惠",
		selection: !0,
		feature: "plan_check"
	}),
	Object.freeze({
		id: "btnAccountInspectionHistory",
		label: "巡检历史",
		section: "查询",
		action: "openAccountInspectionHistory",
		className: "jobs-tb-btn",
		title: "打开账号巡检历史，查看当前账号范围的巡检记录",
		selection: !1
	}),
	Object.freeze({
		id: "btnCheckSelectedLiveV2",
		label: "查活",
		section: "查询",
		action: "checkSelectedLive",
		className: "jobs-tb-btn",
		title: "只在线验证选中账号现有 Token，不发送邮箱验证码或刷新 AT",
		selection: !0,
		feature: "live_check"
	}),
	Object.freeze({
		id: "btnCheckSelectedDeactivationMailV2",
		label: "封号邮件",
		section: "查询",
		action: "checkSelectedDeactivationMail",
		className: "jobs-tb-btn",
		title: "扫描选中账号关联邮箱中的 OpenAI 封号通知，不刷新 AT",
		selection: !0,
		feature: "deactivation_mail"
	}),
	Object.freeze({
		id: "btnRefreshSelectedTokenV2",
		label: "刷新AT",
		section: "处理",
		action: "refreshSelectedToken",
		className: "jobs-tb-btn",
		title: "按已保存的刷新驱动为选中账号获取最新 AT",
		selection: !0,
		feature: "token_refresh"
	}),
	Object.freeze({
		id: "btnRetrySelectedCodexV2",
		label: "补Codex",
		section: "处理",
		action: "retrySelectedCodex",
		className: "jobs-tb-btn",
		title: "给选中的账号批量补跑 Codex 授权",
		selection: !0,
		feature: "codex_retry"
	}),
	Object.freeze({
		id: "btnRetrySelectedRegistrationV2",
		label: "重跑注册",
		section: "处理",
		action: "retryAccountRegistration",
		className: "jobs-tb-btn",
		title: "找到选中账号的原注册任务，按当前进度继续注册或补跑缺失步骤",
		selection: !0
	}),
	Object.freeze({
		id: "btnAddPasswordSelectedAccountsV2",
		label: "补密码",
		section: "处理",
		action: "addPasswordSelectedAccounts",
		className: "jobs-tb-btn",
		title: "只给选中账号补充登录密码",
		selection: !0,
		feature: "password_setup"
	}),
	Object.freeze({
		id: "btnCompleteSelectedAccountsV2",
		label: "补全账号",
		section: "处理",
		action: "completeSelectedAccounts",
		className: "jobs-tb-btn",
		title: "按配置补全选中账号的密码、套餐、2FA 和 Codex，刷新 AT 是否包含由配置决定",
		selection: !0
	}),
	Object.freeze({
		id: "btnAddTwofaSelectedAccountsV2",
		label: "补2FA",
		section: "处理",
		action: "addTwofaSelectedAccounts",
		className: "jobs-tb-btn",
		title: "只给选中账号补充 Authenticator 2FA",
		selection: !0
	}),
	Object.freeze({
		id: "btnEmailChangeSelectedV2",
		label: "换绑邮箱",
		section: "处理",
		action: "openBulkEmailChangeForSelectedAccounts",
		className: "jobs-tb-btn",
		title: "为选中账号批量领取新邮箱并执行协议换绑",
		selection: !0
	}),
	Object.freeze({
		id: "btnChangePasswordSelectedAccountsV2",
		label: "修改密码",
		section: "处理",
		action: "changePasswordSelectedAccounts",
		className: "jobs-tb-btn",
		title: "强制通过忘记密码流程修改选中账号密码",
		selection: !0,
		feature: "password_setup"
	}),
	Object.freeze({
		id: "btnChangeTwofaSelectedAccountsV2",
		label: "改2FA",
		section: "处理",
		action: "changeTwofaSelectedAccounts",
		className: "jobs-tb-btn",
		title: "先关闭选中账号旧 Authenticator，再启用并确认新的 2FA",
		selection: !0,
		feature: "twofa_change"
	}),
	Object.freeze({
		id: "btnExtractSelectedLinksV2",
		label: "提链",
		section: "处理",
		action: "extractSelectedLinks",
		className: "jobs-tb-btn",
		title: "仅给已确认 Plus 免费试用资格的 free 账号批量提链，折扣优惠会跳过",
		selection: !0,
		feature: "extract_link"
	}),
	Object.freeze({
		id: "btnAccountInspection",
		label: "启动巡检",
		section: "运维",
		action: "openAccountInspectionStart",
		className: "jobs-tb-btn",
		title: "按当前账号范围启动批量巡检任务",
		selection: !1
	}),
	Object.freeze({
		id: "btnBulkFromAccountFilters",
		label: "筛选建批",
		section: "运维",
		action: "bulk-from-account-filters",
		className: "jobs-tb-btn",
		title: "按当前账号筛选条件创建批次，不改变当前列表筛选",
		selection: !1
	}),
	Object.freeze({
		id: "btnBulkFromSelectedAccounts",
		label: "已选建批",
		section: "运维",
		action: "bulk-from-selected-accounts",
		className: "jobs-tb-btn",
		title: "按当前已选账号创建批次，使用跨页选择结果",
		selection: !1
	}),
	Object.freeze({
		id: "btnStopSelectedCodexV2",
		label: "停Codex",
		section: "运维",
		action: "stopSelectedCodex",
		className: "jobs-tb-btn jobs-tb-btn--danger",
		title: "停止选中账号中正在补跑的 Codex 授权",
		selection: !0
	}),
	Object.freeze({
		id: "btnReimportSelectedC2aV2",
		label: "同步C2A",
		section: "服务",
		action: "reimportSelectedC2a",
		className: "jobs-tb-btn",
		title: "批量同步选中账号的本地当前 AT 到 C2A，唯一同邮箱时覆盖，未找到时新建账号",
		selection: !0,
		feature: "c2a_sync"
	}),
	Object.freeze({
		id: "btnUploadSelectedCodexSub2V2",
		label: "传sub2",
		section: "服务",
		action: "uploadSelectedCodexSub2",
		className: "jobs-tb-btn",
		title: "把选中账号已通过的 Codex OAuth 凭证上传到 sub2api",
		selection: !0,
		feature: "sub2_upload"
	}),
	Object.freeze({
		id: "btnDownloadSelectedCpaV2",
		label: "导CPA",
		section: "服务",
		action: "downloadSelectedCpa",
		className: "jobs-tb-btn",
		title: "从 CPA auth-files 下载选中账号的 Codex JSON，并打包为 ZIP",
		selection: !0,
		feature: "cpa_download"
	}),
	Object.freeze({
		id: "btnCopySelectedTokensV2",
		label: "复制AT",
		section: "账号",
		action: "copySelectedAccountTokens",
		className: "jobs-tb-btn",
		title: "复制选中账号的 AT，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedLinesV2",
		label: "复制整行",
		section: "账号",
		action: "copySelectedAccountLines",
		className: "jobs-tb-btn",
		title: "复制选中账号的账号、密码和 2FA，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnArchiveSelectedAccountsV2",
		label: "归档选中",
		section: "账号",
		action: "archiveSelectedAccounts",
		className: "jobs-tb-btn",
		title: "归档选中的账号，默认账号列表将不再查询或显示这些账号",
		selection: !0
	}),
	Object.freeze({
		id: "btnDeleteSelectedAccountsV2",
		label: "删除选中",
		section: "账号",
		action: "deleteSelectedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--danger",
		title: "删除选中的本地账号和 Token 记录",
		selection: !0
	}),
	Object.freeze({
		id: "btnDownloadSelectedTxtV2",
		label: "下载TXT",
		section: "账号",
		action: "downloadSelectedAccountTxt",
		className: "jobs-tb-btn",
		title: "把选中账号的完整整行保存为 TXT 文件，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedEmailsV2",
		label: "复制邮箱",
		section: "账号",
		action: "copySelectedAccountEmails",
		className: "jobs-tb-btn",
		title: "复制选中账号的邮箱，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnDeleteDeactivatedAccounts",
		label: "清理已废",
		section: "账号",
		action: "deleteDeactivatedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--danger",
		title: "清理当前归档范围内的已废账号，不受勾选、搜索或分页限制",
		selection: !1
	}),
	Object.freeze({
		id: "btnCopySelectedPasswordsV2",
		label: "复制密码",
		section: "账号",
		action: "copySelectedAccountPasswords",
		className: "jobs-tb-btn",
		title: "复制选中账号中本地已保存的账号密码，格式为 邮箱----密码",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedTotpsV2",
		label: "复制密钥",
		section: "账号",
		action: "copySelectedAccountTotpSecrets",
		className: "jobs-tb-btn",
		title: "复制选中账号的 2FA 密钥（Authenticator 密钥），不是 6 位验证码，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedExtractLinksV2",
		label: "复制提链",
		section: "账号",
		action: "copySelectedAccountExtractLinks",
		className: "jobs-tb-btn",
		title: "复制选中账号已成功生成的提炼地址，每个地址一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnDownloadSelectedSessionsV2",
		label: "下载会话",
		section: "账号",
		action: "downloadSelectedAccountSessions",
		className: "jobs-tb-btn",
		title: "把选中账号已保存的 Session 按每个账号一个 JSON 打包为 ZIP，缺失账号列入结果清单",
		selection: !0
	}),
	Object.freeze({
		id: "btnMarkSelectedEmailInvalidV2",
		label: "标记失效",
		section: "账号",
		action: "setAccountsEmailInvalid:1",
		className: "jobs-tb-btn",
		title: "为选中账号标记邮箱失效，不修改 OpenAI 账号状态",
		selection: !0
	}),
	Object.freeze({
		id: "btnClearSelectedEmailInvalidV2",
		label: "解除失效",
		section: "账号",
		action: "setAccountsEmailInvalid:0",
		className: "jobs-tb-btn",
		title: "仅清除选中账号的本地邮箱失效标记，邮箱可用性仍需确认",
		selection: !0
	}),
	Object.freeze({
		id: "btnAddSelectedAccountsToSales",
		label: "加入贩卖区",
		section: "账号",
		action: "addSelectedAccountsToSales",
		className: "jobs-tb-btn",
		title: "把选中的账号加入贩卖区待售列表，不改变账号当前归档状态",
		selection: !0
	})
]), _e = Object.freeze([
	"btnCopySelectedTokensV2",
	"btnRefreshSelectedTokenV2",
	"btnCopySelectedLinesV2",
	"btnRetrySelectedCodexV2",
	"btnArchiveSelectedAccountsV2"
]), ve = {
	class: "accounts-command-deck",
	id: "accountsCommandDeck"
}, ye = {
	class: "list-selection-hint",
	id: "accountsSelectedHintV2"
}, be = { class: "toolbar-overflow-menu" }, xe = { class: "toolbar-overflow-section-title" }, Se = ["id", "onClick"], Ce = {
	class: "acc-v2-btn-group account-quick-actions",
	id: "accountsQuickActionsV2",
	role: "group",
	"aria-label": "常用账号操作",
	title: "固定显示五项常用账号操作"
}, we = ["data-account-shortcut", "onClick"], Te = /* @__PURE__ */ n({
	__name: "AccountsToolbar",
	props: {
		state: {},
		capabilities: {},
		getContext: { type: Function },
		invoke: { type: Function },
		notify: { type: Function }
	},
	setup(e, { expose: t }) {
		let n = e, i = b(), a = b(), o = b(), l = he.map((e) => ({
			title: e,
			items: ge.filter((t) => t.section === e)
		})), u = new Map(ge.map((e) => [e.id, e])), d = j(/* @__PURE__ */ new Set()), f = _e.map((e) => u.get(e)), p = (e) => e.feature ? n.capabilities[e.feature] : void 0, m = (e) => p(e)?.enabled === !1, h = (e) => e.selection && n.state.selectedCount === 0 || d.value.has(e.action) || !!n.state.pending?.[e.action], g = (e) => n.state.labels?.[e.action] || (e.id === "btnArchiveSelectedAccountsV2" && n.state.archived ? "恢复选中" : e.label), y = (e) => e.id === "btnArchiveSelectedAccountsV2" && n.state.archived ? "把选中的归档账号恢复到默认账号列表" : e.title;
		function x(e) {
			let t = p(e), n = t?.enabled === !1;
			return {
				class: [e.className, { "feature-unavailable": n }],
				disabled: h(e),
				title: n ? `不可用：${t.reason || "缺少必要配置"}` : y(e),
				"data-feature": t ? e.feature : void 0,
				"data-feature-base-title": t ? y(e) : void 0,
				"aria-disabled": t ? n : void 0
			};
		}
		function C(e) {
			a.value?.open && (e.preventDefault(), e.stopPropagation(), a.value.open = !1, o.value?.focus({ preventScroll: !0 }));
		}
		function D() {
			let e = a.value, t = e?.ownerDocument.defaultView, n = i.value?.closest(".ac-toolbar");
			if (!e?.open || !t || !n) return;
			let r = n.getBoundingClientRect().bottom;
			e.style.setProperty("--ac-batch-menu-height", `${Math.max(0, t.innerHeight - r - 12)}px`);
		}
		function k() {
			D();
		}
		async function A(e, t) {
			let r = t.currentTarget;
			if (!(h(e) || m(e) || r.disabled || r.getAttribute("aria-disabled") === "true")) {
				d.value = /* @__PURE__ */ new Set([...d.value, e.action]);
				try {
					await n.invoke(e.action, n.getContext(), r);
				} catch (e) {
					n.notify?.(e instanceof Error ? e.message : "账号操作失败，请稍后重试。");
				} finally {
					let t = new Set(d.value);
					t.delete(e.action), d.value = t;
				}
			}
		}
		let M;
		return c(() => {
			M = i.value?.ownerDocument;
			let e = M?.defaultView;
			e?.addEventListener("resize", D), e?.addEventListener("scroll", D, { passive: !0 });
		}), T(() => {
			let e = M?.defaultView;
			e?.removeEventListener("resize", D), e?.removeEventListener("scroll", D);
		}), t({ refreshQuickActions: () => {} }), (t, n) => (r(), L("div", ve, [w("div", {
			ref_key: "toolbar",
			ref: i,
			class: O(["jobs-toolbar-v2 list-action-toolbar", { "has-selection": e.state.selectedCount > 0 }]),
			id: "accountsToolbarV2"
		}, [
			w("span", ye, S(e.state.selectedCount ? `已选 ${e.state.selectedCount} 个账号` : "选择账号后批量操作"), 1),
			w("details", {
				ref_key: "more",
				ref: a,
				class: "toolbar-overflow",
				id: "accountsMoreActionsV2",
				onToggle: k,
				onKeydown: _(C, ["esc"])
			}, [w("summary", {
				ref_key: "summary",
				ref: o
			}, "批量操作", 512), w("div", be, [(r(!0), L(v, null, s(P(l), (e) => (r(), L("div", {
				key: e.title,
				class: "toolbar-overflow-section toolbar-overflow-section--wide"
			}, [w("span", xe, S(e.title), 1), (r(!0), L(v, null, s(e.items, (e) => (r(), L("button", E({
				key: e.id,
				id: e.id,
				type: "button"
			}, { ref_for: !0 }, x(e), { onClick: (t) => A(e, t) }), S(g(e)), 17, Se))), 128))]))), 128))])], 544),
			w("div", Ce, [(r(!0), L(v, null, s(P(f), (e) => (r(), L("button", E({
				key: e.id,
				"data-account-shortcut": e.id,
				type: "button"
			}, { ref_for: !0 }, x(e), { onClick: (t) => A(e, t) }), S(g(e)), 17, we))), 128))])
		], 2)]));
	}
}), Ee = { class: "ac-filter-fields" }, De = {
	key: 0,
	class: "ac-filter-field"
}, Oe = ["value"], ke = {
	key: 1,
	class: "list-filter-options"
}, Ae = { class: "ac-sr-only" }, je = { class: "list-filter-option" }, Me = ["checked"], Ne = {
	key: 0,
	class: "ac-filter-group-title"
}, Pe = [
	"value",
	"checked",
	"onChange"
], Fe = { key: 0 }, Ie = [
	"type",
	"inputmode",
	"value",
	"placeholder",
	"onInput"
], Le = { class: "list-filter-actions" }, Re = /* @__PURE__ */ n({
	__name: "AccountFilters",
	props: {
		query: {},
		facets: {},
		label: { type: Function },
		open: { type: Boolean },
		column: {}
	},
	emits: [
		"update:open",
		"change",
		"clear"
	],
	setup(e, { emit: t }) {
		let n = e, a = t, c = b("id"), l = k(() => n.column || Y.find((e) => e.key === c.value) || Y[0]), u = k(() => n.column ? ee(n.query, n.column) : Y.some((e) => ee(n.query, e))), d = k(() => q(n.query, n.label, n.facets).find((e) => e.key === l.value.key)?.label || ""), f = k(() => J(n.query, n.facets, l.value, n.label)), p = k(() => X(n.query, l.value.key)), m = k(() => l.value.kind === "date-range" ? ["date_from", "date_to"] : [l.value.key]);
		function y(e, t) {
			let n = new Set(p.value);
			t ? n.add(e) : n.delete(e), a("change", l.value.key, [...n]);
		}
		function x() {
			a("clear", l.value.key), a("update:open", !1);
		}
		return (t, n) => (r(), C(U, {
			label: e.column?.label || "账号",
			"trigger-label": e.column ? void 0 : "筛选",
			active: u.value,
			summary: d.value,
			open: e.open,
			"onUpdate:open": n[4] ||= (e) => a("update:open", e)
		}, {
			default: i(() => [w("div", Ee, [
				e.column ? h("", !0) : (r(), L("label", De, [n[5] ||= R("筛选列", -1), o(w("select", {
					"onUpdate:modelValue": n[0] ||= (e) => c.value = e,
					"aria-label": "选择账号筛选列"
				}, [(r(!0), L(v, null, s(P(Y), (e) => (r(), L("option", {
					key: e.key,
					value: e.key
				}, S(e.label), 9, Oe))), 128))], 512), [[g, c.value]])])),
				l.value.kind === "enum" ? (r(), L("fieldset", ke, [
					w("legend", Ae, S(l.value.label) + "，可多选", 1),
					w("label", je, [w("input", {
						type: "checkbox",
						checked: !p.value.length,
						onChange: n[1] ||= (e) => a("change", l.value.key, [])
					}, null, 40, Me), n[6] ||= w("span", null, "全部", -1)]),
					(r(!0), L(v, null, s(f.value, (e) => (r(), L("div", {
						key: e.key,
						class: "ac-filter-group"
					}, [e.label ? (r(), L("p", Ne, S(e.label), 1)) : h("", !0), (r(!0), L(v, null, s(e.options, (e) => (r(), L("label", {
						class: "list-filter-option",
						key: e.value
					}, [
						w("input", {
							type: "checkbox",
							value: e.value,
							checked: p.value.includes(e.value),
							onChange: (t) => y(e.value, t.target.checked)
						}, null, 40, Pe),
						w("span", null, S(e.label), 1),
						e.count !== null && e.count !== void 0 ? (r(), L("small", Fe, S(e.count), 1)) : h("", !0)
					]))), 128))]))), 128))
				])) : (r(!0), L(v, { key: 2 }, s(m.value, (t, i) => (r(), L("label", {
					key: t,
					class: "ac-filter-field"
				}, [R(S(l.value.kind === "date-range" ? i ? "截止日期" : "开始日期" : l.value.label), 1), w("input", {
					type: l.value.kind === "date-range" ? "date" : "text",
					inputmode: l.value.key === "id" ? "numeric" : void 0,
					value: P(te)(e.query, t),
					placeholder: l.value.placeholder,
					autocomplete: "off",
					onInput: (e) => a("change", t, e.target.value),
					onKeydown: n[2] ||= _(D((e) => a("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, Ie)]))), 128)),
				w("div", Le, [w("button", {
					type: "button",
					onClick: x
				}, "清除此列"), w("button", {
					type: "button",
					class: "list-filter-primary",
					onClick: n[3] ||= (e) => a("update:open", !1)
				}, "完成")])
			])]),
			_: 1
		}, 8, [
			"label",
			"trigger-label",
			"active",
			"summary",
			"open"
		]));
	}
}), ze = [
	{
		key: "selection",
		label: "选择",
		className: "col-check"
	},
	{
		key: "id",
		label: "ID",
		className: "col-id",
		filter: "id"
	},
	{
		key: "email",
		label: "邮箱 / 姓名",
		className: "col-email",
		filter: "email"
	},
	{
		key: "source",
		label: "来源",
		className: "col-source",
		filter: "source"
	},
	{
		key: "registration_driver",
		label: "注册驱动",
		className: "col-registration-driver",
		filter: "registration_driver"
	},
	{
		key: "token",
		label: "Token",
		className: "col-token",
		filter: "token",
		cell: "token"
	},
	{
		key: "account_status",
		label: "账号状态",
		className: "col-account-status",
		filter: "account_status",
		cell: "account_status"
	},
	{
		key: "password",
		label: "账号密码",
		className: "col-small col-password",
		filter: "password",
		cell: "password"
	},
	{
		key: "plan",
		label: "套餐",
		className: "col-plan",
		filter: "plan",
		cell: "plan"
	},
	{
		key: "quota",
		label: "额度",
		className: "col-quota",
		cell: "quota"
	},
	{
		key: "promotion",
		label: "套餐优惠",
		className: "col-trial",
		filter: "promotion",
		cell: "promotion"
	},
	{
		key: "totp",
		label: "2FA",
		className: "col-small col-2fa",
		filter: "totp",
		cell: "totp"
	},
	{
		key: "risk",
		label: "封号邮件",
		className: "col-risk-mail",
		filter: "risk",
		cell: "risk"
	},
	{
		key: "codex",
		label: "Codex",
		className: "col-status",
		filter: "codex",
		cell: "codex"
	},
	{
		key: "time",
		label: "创建 / 更新",
		className: "col-time",
		filter: "date",
		cell: "time"
	},
	{
		key: "actions",
		label: "操作",
		className: "col-actions"
	}
], Be = [
	36,
	72,
	160,
	80,
	104,
	84,
	88,
	72,
	88,
	88,
	192,
	72,
	88,
	72,
	96,
	108
], Ve = Be.map((e) => e / Be.reduce((e, t) => e + t, 0) * 1500);
function He(e) {
	let t = (e, t = "") => `<div class="account-cell-lines"><div class="account-cell-line">${e}</div>${t ? `<div class="account-cell-line account-cell-line--sub">${t}</div>` : ""}</div>`, n = (e) => Array.from(e).length <= 10 ? e : oe();
	function r(t) {
		let r = document.createElement("template");
		r.innerHTML = e.cells.account_status(t);
		let i = [
			"account_status",
			"codex_status",
			"codex_credential_state"
		].some((e) => String(t[e] || "").toLowerCase() === "deactivated");
		if (i || t.live_check_status === "failed") {
			let e = r.content.querySelector(".account-cell-line--sub");
			if (e) {
				let r = e.title || String(i ? t.account_status_reason || e.textContent || "" : t.live_check_error || e.textContent || "");
				e.title = r, e.textContent = n(r);
			}
			let a = r.content.querySelector(".account-cell-line > .is-fail");
			a && Array.from(a.textContent || "").length > 10 && (a.title = [a.title, a.textContent].filter(Boolean).join("；"), a.textContent = "Token 异常");
		}
		return r.innerHTML;
	}
	function i(t) {
		let n = document.createElement("template");
		n.innerHTML = e.extractLink(t);
		for (let e of n.content.querySelectorAll(".pill")) {
			let n = e.textContent || "";
			Array.from(n).length > 10 && (e.title = [e.title, n].filter(Boolean).join("；"), e.textContent = t.extract_link_status === "running" ? "提链中" : Array.from(n).slice(0, 9).join("") + "…");
		}
		return n.innerHTML;
	}
	function a(t) {
		let n = document.createElement("template");
		n.innerHTML = e.menu(t);
		for (let e of n.content.querySelectorAll("[onclick]")) {
			let n = e.getAttribute("onclick") || "";
			if (/^checkSelectedLive\(\[Number\('/.test(n)) e.dataset.accountLiveCheck = String(t.id);
			else if (/^refreshSelectedToken\(\[Number\('/.test(n)) e.dataset.accountRefreshToken = String(t.id), e.dataset.accountTokenRefresh = String(t.id);
			else throw Error("账号动作仍含未迁移的内联处理器");
			e.removeAttribute("onclick");
		}
		return n.innerHTML;
	}
	return {
		cell(a, o) {
			if (a === "plan") return t(e.plan(o), i(o));
			if (a === "account_status") return e.healthDisplay && e.statusLines ? e.statusLines(e.healthDisplay(o), "acc-v2-account-status") : r(o);
			if (a === "codex") {
				if (e.codexDisplay && e.statusLines) return e.statusLines(e.codexDisplay(o), "acc-v2-codex");
				let r = String(o.codex_error || ([
					"queued",
					"running",
					"cancelling"
				].includes(String(o.codex_execution_status)) ? "授权处理中" : ""));
				return t(e.codex(o), r ? `<span title="${e.escape(r)}">${e.escape(n(r))}</span>` : "");
			}
			if (a === "risk") {
				let t = document.createElement("template");
				return t.innerHTML = e.cells.risk(o), t.content.querySelectorAll("[data-deactivation-mail-check]").forEach((e) => {
					e.dataset.accountDeactivationMail = e.dataset.deactivationMailCheck;
				}), t.innerHTML;
			}
			return e.cells[a](o);
		},
		menu: a,
		emailInvalidBadge: e.emailInvalidBadge,
		registrationDriverLabel: e.registrationDriverLabel,
		facetLabel: e.facetLabel,
		mobileSummary(t) {
			return [
				t.email_source,
				e.htmlText(e.plan(t)),
				t.totp_enabled ? "2FA 已验证" : "2FA 未验证",
				(() => {
					let n = e.htmlText(e.codex(t));
					return n && n !== "-" ? `Codex ${n}` : "";
				})()
			].filter((e) => e && e !== "-").join(" · ");
		},
		rowTone(t) {
			if (e.healthDisplay) {
				let n = e.healthDisplay(t).style;
				return n === "fail" ? "bad" : ["mute", "run"].includes(n) ? "warn" : "ok";
			}
			let n = e.cells.account_status(t);
			return /status-(failed|error|invalid|rejected)/.test(n) ? "bad" : /status-(warning|pending|unknown|used)/.test(n) ? "warn" : "ok";
		}
	};
}
var Ue = [
	"account-registration-retry",
	"account-registration-task",
	"account-email-change",
	"account-totp-copy",
	"account-copy-secret",
	"account-setup",
	"account-action",
	"plan-check",
	"deactivation-mail-check",
	"account-live-check",
	"account-refresh-token",
	"account-task-history",
	"account-delete",
	"account-archive",
	"account-restore",
	"account-email-invalid",
	"extract-link",
	"qr-url",
	"codex-stop",
	"codex-reset-retrying",
	"codex-retry",
	"copy-id"
];
function We(e) {
	if (!(e instanceof Element)) return;
	let t = e.closest("button,[data-copy-id]");
	if (!t || t.hasAttribute("disabled") || t.getAttribute("aria-disabled") === "true" || t.classList.contains("feature-unavailable")) return;
	let n = Ue.find((e) => t.hasAttribute(`data-${e}`));
	if (!n) return;
	let r = [
		"account-registration-task",
		"account-copy-secret",
		"account-action",
		"qr-url",
		"copy-id"
	].includes(n), i = n === "account-email-invalid" ? t.dataset.invalid : n === "account-archive" ? t.dataset.archived : r ? t.getAttribute(`data-${n}`) : void 0;
	return {
		action: i == null ? n : `${n}:${i}`,
		trigger: t
	};
}
// src/features/accounts/AccountsTable.vue?vue&type=script&setup=true&lang.ts
var Ge = ["aria-busy"], Ke = ["data-stale"], qe = [
	"checked",
	"indeterminate",
	"disabled"
], Je = { id: "accountsBodyV2" }, Ye = ["data-account-row", "onClick"], Xe = { class: "col-check" }, Ze = [
	"data-account-id",
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], Qe = { class: "col-id" }, $e = { class: "col-email" }, et = ["disabled", "data-account-detail-id"], tt = { class: "acc-v2-email" }, nt = {
	key: 0,
	class: "pill status-used",
	title: "该账号已归档"
}, rt = { class: "acc-v2-sub account-cell-line account-cell-line--sub account-email-meta" }, it = { class: "account-email-name" }, at = ["innerHTML"], ot = { class: "acc-mobile-meta" }, st = { class: "col-source" }, ct = { class: "col-registration-driver" }, lt = ["data-label"], ut = ["innerHTML"], dt = { class: "col-actions" }, ft = { class: "account-cell-lines acc-v2-actions" }, pt = ["disabled", "data-account-detail-id"], mt = ["disabled"], ht = ["onClick", "innerHTML"], gt = /* @__PURE__ */ n({
	__name: "AccountsTable",
	props: {
		items: {},
		selected: {},
		query: {},
		facets: {},
		presentation: {},
		loading: { type: Boolean },
		error: {},
		invalidSearch: { type: Boolean },
		stale: { type: Boolean },
		visible: { type: Boolean },
		pageSelected: { type: Boolean },
		pageIndeterminate: { type: Boolean },
		openFilter: {}
	},
	emits: [
		"select",
		"selectPage",
		"action",
		"detail",
		"retry",
		"filter",
		"clearFilter",
		"update:openFilter",
		"rendered"
	],
	setup(e, { expose: t, emit: n }) {
		let o = e, l = n, { widths: d, total: p, resize: m, resizeWithKeyboard: g, resetColumns: _ } = re({
			defaults: Ve,
			storageKey: "gpt_console_table_widths_accounts",
			totalStorageKey: "gpt_console_table_total_accounts",
			min: 28,
			max: 2e4,
			ratioPrecision: 8,
			totalPrecision: 4,
			onPersist() {
				try {
					localStorage.setItem("gpt_console_accounts_columns_v2", "2");
				} catch {}
			},
			onReset() {
				try {
					localStorage.removeItem("gpt_console_accounts_columns_v2");
				} catch {}
			}
		}), x = b(), E = b(null);
		function A(e) {
			if (!o.stale) return e;
			let t = document.createElement("template");
			return t.innerHTML = e, t.content.querySelectorAll("button,input,select,textarea").forEach((e) => e.setAttribute("disabled", "")), t.content.querySelectorAll("a,[role=\"button\"],[data-copy-id]").forEach((e) => {
				e.setAttribute("aria-disabled", "true"), e.setAttribute("tabindex", "-1");
			}), t.innerHTML;
		}
		let j = k(() => (o.stale && o.loading ? [] : o.items).map((e) => ({
			row: e,
			id: String(e.id),
			cells: Object.fromEntries(ze.filter((e) => e.cell).map((t) => [t.cell, A(o.presentation.cell(t.cell, e))])),
			menu: o.presentation.menu(e),
			mobile: o.presentation.mobileSummary(e),
			tone: o.presentation.rowTone(e)
		}))), M = (e) => Y.find((t) => t.key === e);
		function N(e, t) {
			if (o.stale || !o.visible) {
				e.preventDefault(), e.stopPropagation();
				return;
			}
			let n = e.target instanceof Element ? e.target : null, r = n?.closest("[data-account-detail-id]");
			if (r) {
				e.preventDefault(), e.stopPropagation(), l("detail", String(t.id), r);
				return;
			}
			let i = We(e.target);
			i ? (e.preventDefault(), e.stopPropagation(), E.value = null, l("action", i.action, String(t.id), i.trigger)) : window.matchMedia("(max-width:860px)").matches && !n?.closest("button,a,input,label,[role=\"dialog\"]") && l("detail", String(t.id), null);
		}
		function F() {
			E.value = null;
		}
		function I(e) {
			e.target instanceof Element && e.target.closest(".ac-row-menu") || F();
		}
		return a(() => o.visible, (e) => {
			e || F();
		}), a(() => o.stale, (e) => {
			e && F();
		}), a(() => o.items, (e) => {
			E.value && !e.some((e) => String(e.id) === E.value) && F();
		}), c(() => {
			window.addEventListener("resize", F), window.addEventListener("scroll", I, !0), x.value && l("rendered", x.value);
		}), u(() => {
			x.value && l("rendered", x.value);
		}), T(() => {
			window.removeEventListener("resize", F), window.removeEventListener("scroll", I, !0);
		}), t({
			resetColumns: _,
			closeMenu: F
		}), (t, n) => (r(), L("div", {
			ref_key: "root",
			ref: x,
			class: "accounts-table-v2-wrap ac-table-scroll",
			tabindex: "0",
			"aria-label": "账号列表，可横向滚动",
			"aria-busy": e.loading,
			onScroll: F
		}, [w("table", {
			class: "accounts-table-v2 ac-table",
			style: y({ width: `${P(p)}px` }),
			"data-stale": e.stale || void 0
		}, [
			n[5] ||= w("caption", { class: "ac-sr-only" }, "账号资产，支持跨页选择", -1),
			w("colgroup", null, [(r(!0), L(v, null, s(P(d), (e, t) => (r(), L("col", {
				key: t,
				style: y({ width: `${e}px` })
			}, null, 4))), 128))]),
			w("thead", null, [w("tr", null, [(r(!0), L(v, null, s(P(ze), (t, i) => (r(), L("th", {
				key: t.key,
				scope: "col",
				class: O(t.className)
			}, [t.key === "selection" ? (r(), L("input", {
				key: 0,
				id: "accountsSelectAllV2",
				type: "checkbox",
				"aria-label": "全选当前页账号",
				checked: e.pageSelected,
				indeterminate: e.pageIndeterminate,
				disabled: e.stale || !e.items.length,
				onChange: n[0] ||= (e) => l("selectPage", e.target.checked)
			}, null, 40, qe)) : t.filter ? (r(), C(Re, {
				key: 1,
				column: M(t.filter),
				query: e.query,
				facets: e.facets,
				label: e.presentation.facetLabel,
				open: e.visible && e.openFilter === t.filter,
				"onUpdate:open": (e) => l("update:openFilter", e ? t.filter : null),
				onChange: n[1] ||= (e, t) => l("filter", e, t),
				onClear: n[2] ||= (e) => l("clearFilter", e)
			}, null, 8, [
				"column",
				"query",
				"facets",
				"label",
				"open",
				"onUpdate:open"
			])) : (r(), L(v, { key: 2 }, [R(S(t.label), 1)], 64)), i ? (r(), C(ie, {
				key: 3,
				label: t.label,
				onStart: (e) => P(m)(i, e),
				onNudge: (e) => P(g)(i, e)
			}, null, 8, [
				"label",
				"onStart",
				"onNudge"
			])) : h("", !0)], 2))), 128))])]),
			w("tbody", Je, [(r(!0), L(v, null, s(j.value, (t) => (r(), L("tr", {
				key: t.id,
				"data-account-row": t.id,
				class: O({ "ac-row-selected": e.selected.has(t.id) }),
				onClick: (e) => N(e, t.row)
			}, [
				w("td", Xe, [w("input", {
					type: "checkbox",
					class: "account-row-check",
					"data-account-id": t.id,
					"aria-label": `选择账号 ${t.row.email || t.id}`,
					checked: e.selected.has(t.id),
					disabled: e.stale,
					onChange: (e) => l("select", t.id, e.target.checked)
				}, null, 40, Ze)]),
				w("td", Qe, [f(V, { text: `#${t.id}` }, null, 8, ["text"])]),
				w("td", $e, [
					w("button", {
						type: "button",
						class: "acc-v2-email-link account-cell-line",
						disabled: e.stale,
						"data-account-detail-id": t.id,
						title: "查看账号详情"
					}, [w("span", {
						class: O(["acc-mobile-dot", `is-${t.tone}`]),
						"aria-hidden": "true"
					}, null, 2), w("span", tt, [R(S(t.row.email), 1), t.row.archived ? (r(), L("span", nt, "归档")) : h("", !0)])], 8, et),
					w("div", rt, [w("span", it, S(t.row.user_name || "-"), 1), w("span", { innerHTML: e.presentation.emailInvalidBadge(t.row) }, null, 8, at)]),
					w("div", ot, S(t.mobile), 1)
				]),
				w("td", st, [f(V, { text: t.row.email_source || "-" }, null, 8, ["text"])]),
				w("td", ct, [f(V, { text: e.presentation.registrationDriverLabel(t.row.registration_driver) }, null, 8, ["text"])]),
				(r(!0), L(v, null, s(P(ze).filter((e) => e.cell), (e) => (r(), L("td", {
					key: e.key,
					class: O(e.className),
					"data-label": e.label
				}, [w("div", {
					class: "ac-legacy-cell",
					innerHTML: t.cells[e.cell]
				}, null, 8, ut)], 10, lt))), 128)),
				w("td", dt, [w("div", ft, [w("button", {
					type: "button",
					class: "acc-v2-detail",
					disabled: e.stale,
					"data-account-detail-id": t.id
				}, "详情", 8, pt), f(P(W), {
					open: e.visible && !e.stale && E.value === t.id,
					modal: !1,
					"onUpdate:open": (e) => E.value = e ? t.id : null
				}, {
					default: i(() => [f(P(B), { "as-child": "" }, {
						default: i(() => [w("button", {
							type: "button",
							class: "acc-v2-more-btn",
							disabled: e.stale,
							"aria-label": "更多账号操作"
						}, "更多", 8, mt)]),
						_: 1
					}), f(P(z), null, {
						default: i(() => [f(P(H), {
							class: "ac-row-menu accounts-table-v2",
							"data-account-menu": t.id,
							side: "bottom",
							align: "end",
							"side-offset": 4,
							"collision-padding": 8,
							onOpenAutoFocus: n[3] ||= D(() => {}, ["prevent"])
						}, {
							default: i(() => [w("div", {
								class: "acc-v2-more-menu ac-menu-content",
								onClick: (e) => N(e, t.row),
								innerHTML: t.menu
							}, null, 8, ht)]),
							_: 2
						}, 1032, ["data-account-menu"])]),
						_: 2
					}, 1024)]),
					_: 2
				}, 1032, ["open", "onUpdate:open"])])])
			], 10, Ye))), 128)), j.value.length ? h("", !0) : (r(), C(ae, {
				key: 0,
				class: "ac-empty",
				colspan: 16,
				loading: e.loading,
				error: e.invalidSearch ? "" : e.error,
				"loading-title": "正在加载账号",
				"loading-text": "正在同步账号状态和授权信息",
				"error-title": "账号加载失败",
				title: e.invalidSearch ? "搜索条件有误" : "暂无匹配账号",
				text: e.invalidSearch ? "请按输入框旁的提示修改，或清空高级搜索。" : "可移除部分搜索条件，或切换活跃与归档账号视图。",
				"retry-label": "重试",
				onRetry: n[4] ||= (e) => l("retry")
			}, null, 8, [
				"loading",
				"error",
				"title",
				"text"
			]))])
		], 12, Ke)], 40, Ge));
	}
}), _t = 3e4, vt = [
	"source",
	"registration_driver",
	"token",
	"password",
	"plan",
	"promotion",
	"totp",
	"risk",
	"codex",
	"account_status",
	"email_status"
];
function Z(e) {
	return Array.isArray(e) ? e.map(Z) : e && typeof e == "object" ? Object.fromEntries(Object.entries(e).map(([e, t]) => [e, Z(t)])) : e;
}
function yt(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(yt), Object.freeze(e)), e;
}
function bt(e) {
	return yt(Z(e));
}
function xt(e) {
	let t = String(e);
	if (!/^[1-9]\d*$/.test(t) || !Number.isSafeInteger(Number(t))) throw Error("账号 ID 无效");
	return t;
}
function St() {
	throw new DOMException("读取已失效", "AbortError");
}
function Ct(e) {
	return Z({
		account_promotions: e.account_promotions ?? null,
		promotion_query_snapshot: e.promotion_query_snapshot ?? null,
		plan_check_country_results: e.plan_check_country_results ?? []
	});
}
function wt(n, r) {
	let i = j(n.normalize()), a = j([]), o = j({}), s = j([]), c = j(null), l = b(0), u = b(1), d = b(20), f = b(!1), p = b(!1), h = b(!1), g = b(""), _ = b(!1), v = b(""), y = j(/* @__PURE__ */ new Set()), x = j({}), S = b(""), C = k(() => Math.max(1, Math.ceil(l.value / d.value))), w = k(() => n.toLegacy(i.value, {
		paged: "1",
		page: u.value,
		page_size: d.value
	}).toString()), T = k(() => S.value !== w.value), E = k(() => a.value.length > 0 && a.value.every((e) => y.value.has(String(e.id)))), D = k(() => !E.value && a.value.some((e) => y.value.has(String(e.id)))), O = 0, A = 0, M = 0, N = 0, P = !1, F = !1, I, L, R, z, B, V = "", H, U, W = /* @__PURE__ */ new Map(), G = /* @__PURE__ */ new Map(), K = () => typeof document > "u" || !document.hidden, q = () => !P && h.value && K(), J = (e, t) => e === O && t === w.value && q();
	function Y(e) {
		return [...G.values()].some((t) => t === e);
	}
	function X() {
		let e = /* @__PURE__ */ new Set([...a.value.map((e) => String(e.id)), ...G.values()]);
		for (let [t, n] of W) e.has(t) || (n.request?.controller.abort(), W.delete(t));
	}
	function ee() {
		for (let e of W.values()) e.request?.controller.abort(), e.request = void 0, ++e.version;
	}
	function te() {
		++O, ++A, I?.abort(), L?.abort(), I = L = void 0, clearTimeout(R), clearTimeout(B), R = B = void 0, f.value = p.value = !1;
	}
	function ne() {
		clearTimeout(R), R = void 0, q() && H !== i.value.q && (R = setTimeout(() => {
			ue();
		}, 5e3));
	}
	function re(e) {
		let t = Z(e);
		for (let e of vt) {
			let n = e === "plan" ? i.value.plan : i.value.filters[e];
			if (!n.length) continue;
			let r = t[e] ?? [];
			t[e] = [...r, ...n.filter((e) => !r.some((t) => t.value === e)).map((e) => ({
				value: e,
				count: 0
			}))];
		}
		return t;
	}
	function ie(e) {
		a.value = Z(e);
		for (let e of a.value) {
			let t = String(e.id), n = W.get(t);
			n?.request?.controller.abort(), W.set(t, {
				revision: "",
				version: (n?.version ?? 0) + 1,
				details: Ct(e)
			});
		}
		X();
	}
	async function ae(e) {
		if (te(), !q()) return;
		let t = O, c = new AbortController(), p = n.toLegacy(i.value).toString(), m = !e || U?.filter !== p || Date.now() - U.readAt >= _t;
		m && (U = void 0), I = c, f.value = !0;
		try {
			for (let e = 0; e < 2; e++) {
				let n = w.value, a = Z(i.value), f = u.value, h = d.value, v = m && !U, y = await r.list(a, f, h, c.signal, { includeFacets: v });
				if (!J(t, n)) return;
				v && (o.value = re(y.facets), U = {
					filter: p,
					readAt: Date.now()
				});
				let b = Math.max(1, Math.ceil(y.total / h));
				if (f > b) {
					if (u.value = b, !e) continue;
					g.value = "列表范围已变化，请刷新后重试";
					return;
				}
				ie(y.items), l.value = y.total, s.value = Z(y.search_terms), S.value = n, V = "", g.value = "", _.value = !1, H = void 0;
				return;
			}
		} catch (e) {
			if (t !== O || !q() || se(e)) return;
			g.value = e instanceof Error ? e.message : "加载账号失败", e instanceof le && e.code === "account_search_invalid" && (H = i.value.q, _.value = !0, U = void 0, a.value = [], l.value = 0, s.value = [], o.value = {}, X());
		} finally {
			t === O && (f.value = !1, I = void 0, ne());
		}
	}
	function oe() {
		return ae(!1);
	}
	function ce(e, t, n) {
		let r = Z(e);
		for (let e of n) delete r[e];
		Object.assign(r, Z(t));
		let i = String(e.id), a = W.get(i);
		if (!a || a.revision !== t.plan_details_revision) {
			a?.request?.controller.abort(), W.set(i, {
				revision: t.plan_details_revision,
				version: (a?.version ?? 0) + 1
			});
			let e = (e) => e?.map((e) => {
				let t = e.plan;
				return {
					...e,
					plan: typeof t == "string" && t.trim() ? t : "plus"
				};
			}) ?? null;
			r.account_promotions = e(t.plan_summary.promotions), r.plan_check_country_results = t.plan_summary.countries.map((t) => {
				let { promotions: n, ...r } = t;
				return {
					...r,
					...Array.isArray(n) ? { result: { account_promotions: e(n) } } : {}
				};
			}), delete r.promotion_query_snapshot;
		}
		return r;
	}
	async function ue() {
		if (clearTimeout(R), R = void 0, !q() || f.value || p.value || T.value || H === i.value.q) {
			ne();
			return;
		}
		let e = O, t = w.value, n = new AbortController();
		L = n, p.value = !0;
		try {
			let o = await r.statuses(Z(i.value), u.value, d.value, n.signal);
			if (!J(e, t)) return;
			let s = new Map(a.value.map((e) => [String(e.id), e]));
			if (o.total !== l.value || o.items.length !== a.value.length || o.items.some((e, t) => String(e.id) !== String(a.value[t]?.id)) || new Set(o.items.map((e) => e.id)).size !== o.items.length) {
				await oe();
				return;
			}
			if (c.value = Z(o.queue), V === o.revision) return;
			let f = (e) => e === "queued" || e === "running", p = !1;
			a.value = o.items.map((e) => {
				let t = s.get(String(e.id));
				return (f(t.plan_check_status) && !f(e.plan_check_status) || f(t.extract_link_status) && !f(e.extract_link_status)) && (p = !0), ce(t, e, o.status_fields);
			}), V = o.revision, p && await oe();
		} catch (n) {
			J(e, t) && n instanceof le && n.code === "account_search_invalid" && (H = i.value.q, _.value = !0, g.value = n instanceof Error ? n.message : "筛选语法无效", U = void 0, a.value = [], l.value = 0, o.value = {}, s.value = [], X());
		} finally {
			e === O && (p.value = !1, L = void 0, ne());
		}
	}
	function de(e = 0, n = !1) {
		if (te(), !q()) return;
		let r = A, i = () => {
			r === A && q() && ae(n);
		};
		e ? B = setTimeout(i, e) : t(i);
	}
	function fe() {
		y.value = /* @__PURE__ */ new Set(), x.value = {}, ++M;
	}
	function pe(e, t = 0) {
		if (P) return;
		let r = n.normalize(e);
		clearTimeout(z), z = void 0, n.toLegacy(r).toString() === n.toLegacy(i.value).toString() && r.limit === i.value.limit ? v.value = r.q : (i.value = Z(r), v.value = r.q, u.value = 1, fe(), _.value = !1, g.value = "", H = void 0, de(t));
	}
	function me(e, t = 0) {
		pe({
			...Z(i.value),
			...Z(e)
		}, t);
	}
	function he(e, t = 0) {
		me({ filters: {
			...Z(i.value.filters),
			...Z(e)
		} }, t);
	}
	function ge(e) {
		me({ archived: e ? "only" : "0" });
	}
	function _e() {
		pe(n.normalize({ archived: i.value.archived }));
	}
	function ve(e) {
		if (P || !Number.isFinite(e)) return;
		let t = Math.min(C.value, Math.max(1, Math.floor(e)));
		t !== u.value && (u.value = t, de(0, !0));
	}
	function ye(e) {
		if (P || !Number.isFinite(e) || e < 1) return;
		let t = Math.min(500, Math.floor(e));
		t !== d.value && (d.value = t, u.value = 1, de(0, !0));
	}
	function be(e) {
		v.value = e, clearTimeout(z), z = void 0, !F && !P && (z = setTimeout(() => {
			me({ q: v.value });
		}, 250));
	}
	function xe() {
		F = !0, clearTimeout(z), z = void 0;
	}
	function Se(e) {
		F = !1, be(e);
	}
	function Ce() {
		F || (clearTimeout(z), me({ q: v.value }));
	}
	function we() {
		F = !1, clearTimeout(z), me({ q: "" });
	}
	function Te(e) {
		me({ q: e.query_without });
	}
	function Ee(e, t) {
		if (P) return;
		if (t && (T.value || _.value)) throw Error("当前筛选结果尚未加载");
		let n = xt(e), r = a.value.find((e) => String(e.id) === n);
		if (t && !r) throw Error("账号不在当前页");
		let i = new Set(y.value), o = { ...x.value };
		t ? (i.add(n), r?.email?.trim() ? o[n] = r.email : delete o[n]) : (i.delete(n), delete o[n]), y.value = i, x.value = o, ++M;
	}
	function De(e) {
		for (let t of a.value) Ee(String(t.id), e);
	}
	function Oe(e) {
		for (let t of e) Ee(t, !1);
	}
	function ke(e = {}) {
		let t = [...new Set((e.ids ?? [...y.value]).map(xt))], n = {}, r = new Map(a.value.map((e) => [String(e.id), e]));
		for (let e of t) {
			let t = r.has(e) ? r.get(e)?.email : x.value[e];
			t && (n[e] = t);
		}
		if (e.requireEmails && (t.length > 500 || t.some((e) => !n[e]?.trim()))) throw Error(t.length > 500 ? "一次最多处理 500 个账号" : "账号邮箱快照不完整，请刷新后重新选择");
		return bt({
			query: i.value,
			ids: t,
			expectedEmails: n,
			created_at: (/* @__PURE__ */ new Date()).toISOString(),
			source: "accounts",
			generation: M
		});
	}
	function Ae(e = {}) {
		let t = ke(e), n = new Set(t.ids);
		return bt({
			accountIds: t.ids,
			expectedEmails: t.expectedEmails,
			querySnapshot: t.query,
			archived: t.query.archived,
			rowHints: a.value.filter((e) => n.has(String(e.id)))
		});
	}
	function je(e) {
		let t = a.value.find((t) => String(t.id) === e);
		return t ? bt(t) : void 0;
	}
	async function Me(e) {
		q() && Y(e) || St();
		let t = W.get(e);
		if (t || St(), t.details) return bt({
			accountId: e,
			revision: t.revision,
			item: t.details
		});
		if (t.request) return t.request.promise;
		let n = new AbortController(), i = t.version, o = r.planDetails(e, n.signal).then(async (n) => {
			q() && Y(e) || St();
			let r = W.get(e);
			return r || St(), r !== t || r.version !== i ? Me(e) : (r.details = Z(n.item), a.value = a.value.map((t) => String(t.id) === e ? {
				...t,
				...Z(n.item)
			} : t), bt({
				accountId: e,
				revision: r.revision,
				item: r.details
			}));
		}, (n) => {
			q() && Y(e) || St();
			let r = W.get(e);
			if (r && (r !== t || r.version !== i)) return Me(e);
			throw n;
		}).finally(() => {
			t.request?.promise === o && (t.request = void 0), X();
		});
		return t.request = {
			version: i,
			controller: n,
			promise: o
		}, o;
	}
	async function Ne(e, t) {
		let n = xt(e);
		for (;;) {
			G.get(t) === n && q() || St();
			let e = W.get(n), r = e?.version, i;
			try {
				i = await Me(n);
			} catch (e) {
				throw G.get(t) === n && q() || St(), e;
			}
			if (G.get(t) === n && q() || St(), W.get(n) === e && e?.version === r) return i;
		}
	}
	function Pe(e) {
		let t = xt(e), n = ++N;
		if (!W.has(t)) throw Error("账号详情已失效，请刷新列表");
		return G.set(n, t), {
			openGeneration: n,
			loadPlanDetails: Ne,
			release() {
				if (G.delete(n)) {
					if (!Y(t)) {
						let e = W.get(t);
						e?.request && (e.request.controller.abort(), e.request = void 0, ++e.version);
					}
					X();
				}
			}
		};
	}
	function Fe(e) {
		P || e === h.value || (h.value = e, e ? de() : (te(), ee(), G.clear(), X()));
	}
	function Ie() {
		K() ? h.value && de() : (te(), ee());
	}
	return typeof document < "u" && document.addEventListener("visibilitychange", Ie), m(() => {
		P = !0, te(), clearTimeout(z), ee(), G.clear(), W.clear(), typeof document < "u" && document.removeEventListener("visibilitychange", Ie);
	}), {
		query: e(i),
		items: e(a),
		facets: e(o),
		searchTerms: e(s),
		queue: e(c),
		total: e(l),
		page: e(u),
		size: e(d),
		pages: C,
		selected: e(y),
		selectedEmails: e(x),
		loading: e(f),
		polling: e(p),
		visible: e(h),
		error: e(g),
		invalidSearch: e(_),
		draftSearch: e(v),
		renderedSignature: e(S),
		signature: w,
		stale: T,
		pageSelected: E,
		pageIndeterminate: D,
		refresh: oe,
		pollStatuses: ue,
		setVisible: Fe,
		setPage: ve,
		setSize: ye,
		setArchived: ge,
		commitQuery: pe,
		updateQuery: me,
		updateFilters: he,
		resetFilters: _e,
		setSearchDraft: be,
		compositionStart: xe,
		compositionEnd: Se,
		submitSearch: Ce,
		clearSearch: we,
		removeSearchTerm: Te,
		toggle: Ee,
		togglePage: De,
		clearSelection: fe,
		removeAcknowledgedSelection: Oe,
		getAccountSelectionSnapshot: ke,
		getActionContext: Ae,
		getRowSnapshot: je,
		openPlanDetailsConsumer: Pe,
		loadPlanDetails: Ne
	};
}
// src/features/accounts/AccountsList.vue?vue&type=script&setup=true&lang.ts
var Tt = {
	class: "ac-root",
	"aria-label": "账号列表"
}, Et = { class: "ac-toolbar" }, Dt = {
	key: 0,
	class: "ac-toolbar-main"
}, Ot = { class: "ac-toolbar-utilities" }, kt = { class: "ac-mobile-filters" }, At = [
	"value",
	"aria-invalid",
	"onKeydown"
], jt = ["disabled"], Mt = {
	key: 0,
	id: "accountAdvancedSearchErrorV2",
	class: "ac-feedback",
	role: "alert"
}, Nt = {
	key: 1,
	class: "ac-feedback",
	role: "alert"
}, Pt = /* @__PURE__ */ n({
	__name: "AccountsList",
	props: {
		adapter: {},
		api: {},
		presentation: {},
		callbacks: {}
	},
	setup(e, { expose: t }) {
		let n = e, i = wt(n.adapter, n.api), { query: s, items: c, facets: l, searchTerms: u, total: p, page: m, size: g, pages: v, selected: y, loading: x, error: C, visible: E, invalidSearch: O, draftSearch: A, stale: j, pageSelected: M, pageIndeterminate: F } = i, I = b(), R = b(), z = b(null), B = b(typeof document > "u" || !document.hidden), V = b(""), H = /* @__PURE__ */ new Set(), U = Y.find((e) => e.key === "email_status"), W = k(() => [...q(s.value, n.presentation.facetLabel, l.value), ...u.value.map((e, t) => ({
			key: `search:${t}`,
			label: `${e.label}：${e.display_value}`,
			title: `高级搜索 · 同时满足：${e.label}：${e.display_value}`,
			removeLabel: `移除${e.label}：${e.display_value}`
		}))]);
		function J(e, t) {
			e === "plan" ? i.updateQuery({ plan: [...t] }) : e === "date_from" || e === "date_to" ? i.updateQuery({ [e]: String(t) }) : e === "id" || e === "email" ? i.updateFilters({ [e]: String(t) }, 250) : i.updateFilters({ [e]: [...t] });
		}
		function X(e) {
			if (e.startsWith("search:")) {
				let t = u.value[Number(e.slice(7))];
				t && i.removeSearchTerm({ ...t }), R.value?.focus();
				return;
			}
			if (e === "date") {
				i.updateQuery({
					date_from: "",
					date_to: ""
				});
				return;
			}
			let t = Y.find((t) => t.key === e);
			t && J(t.key, t.kind === "text" ? "" : []);
		}
		function ee(e) {
			V.value = e instanceof Error ? e.message : "账号操作暂不可用", n.callbacks.notify?.(V.value);
		}
		async function te(e, t, r) {
			if (j.value || !E.value || !B.value) return;
			let a = JSON.stringify([t, e]);
			if (!H.has(a)) {
				H.add(a), V.value = "";
				try {
					let a = i.getActionContext({
						ids: [t],
						requireEmails: e.startsWith("account-email-invalid:")
					});
					await n.callbacks.invoke(e, a, r);
				} catch (e) {
					ee(e);
				} finally {
					H.delete(a);
				}
			}
		}
		function ne(e, t) {
			if (j.value || !E.value || !B.value) return;
			V.value = "";
			let r = i.getRowSnapshot(e);
			if (!r) {
				ee(/* @__PURE__ */ Error("账号详情暂不可用，请先刷新列表"));
				return;
			}
			let a;
			try {
				a = i.openPlanDetailsConsumer(e), n.callbacks.openDetail(e, r, a, t);
			} catch (e) {
				a?.release(), ee(e);
			}
		}
		function re(e) {
			e || (z.value = null, n.callbacks.closeConsumers?.(!1)), i.setVisible(e);
		}
		function ie(e) {
			z.value = null, i.setArchived(e);
		}
		function ae() {
			i.clearSearch(), R.value?.focus();
		}
		function oe() {
			I.value?.resetColumns();
		}
		a([
			i.selected,
			i.selectedEmails,
			p,
			m,
			g,
			s,
			x,
			E
		], () => n.callbacks.onStateChange?.(Object.freeze({
			selectedIds: Object.freeze([...y.value]),
			selectedEmails: Object.freeze({ ...i.selectedEmails.value }),
			total: p.value,
			page: m.value,
			size: g.value,
			archived: s.value.archived,
			loading: x.value,
			visible: E.value
		})), {
			immediate: !0,
			flush: "post"
		});
		let se = () => {
			B.value = !document.hidden, document.hidden && (z.value = null, n.callbacks.closeConsumers?.());
		};
		return typeof document < "u" && document.addEventListener("visibilitychange", se), T(() => {
			typeof document < "u" && document.removeEventListener("visibilitychange", se), n.callbacks.closeConsumers?.();
		}), t({
			refresh: i.refresh,
			pollStatuses: i.pollStatuses,
			setVisible: re,
			setArchived: ie,
			openDetail: ne,
			setPage: i.setPage,
			setSize: i.setSize,
			closeMoreMenus: () => I.value?.closeMenu(),
			updateQuery: i.updateQuery,
			updateFilters: i.updateFilters,
			resetFilters: i.resetFilters,
			resetColumns: oe,
			getAccountSelectionSnapshot: i.getAccountSelectionSnapshot,
			getActionContext: i.getActionContext,
			getRowSnapshot: i.getRowSnapshot,
			openPlanDetailsConsumer: i.openPlanDetailsConsumer,
			removeAcknowledgedSelection: i.removeAcknowledgedSelection,
			clearSelection: i.clearSelection
		}), (t, n) => o((r(), L("section", Tt, [
			w("div", Et, [
				W.value.length ? (r(), L("div", Dt, [f(G, {
					items: W.value,
					onRemove: X
				}, null, 8, ["items"])])) : h("", !0),
				d(t.$slots, "actions"),
				w("div", Ot, [
					w("div", kt, [f(Re, {
						query: P(s),
						facets: P(l),
						label: e.presentation.facetLabel,
						open: B.value && z.value === "all",
						"onUpdate:open": n[0] ||= (e) => z.value = e ? "all" : null,
						onChange: J,
						onClear: X
					}, null, 8, [
						"query",
						"facets",
						"label",
						"open"
					])]),
					f(Re, {
						column: P(U),
						query: P(s),
						facets: P(l),
						label: e.presentation.facetLabel,
						open: B.value && z.value === "email_status",
						"onUpdate:open": n[1] ||= (e) => z.value = e ? "email_status" : null,
						onChange: J,
						onClear: X
					}, null, 8, [
						"column",
						"query",
						"facets",
						"label",
						"open"
					]),
					w("form", {
						class: "ac-search",
						role: "search",
						onSubmit: n[5] ||= D((...e) => P(i).submitSearch && P(i).submitSearch(...e), ["prevent"])
					}, [
						n[11] ||= w("label", { for: "accountAdvancedSearchV2" }, "高级搜索", -1),
						w("input", {
							id: "accountAdvancedSearchV2",
							ref_key: "search",
							ref: R,
							type: "search",
							value: P(A),
							placeholder: "空格或 / 组合，如：协议 jp",
							autocomplete: "off",
							"aria-describedby": "accountAdvancedSearchHintV2 accountAdvancedSearchErrorV2",
							"aria-invalid": P(O) || void 0,
							onKeydown: _(D(ae, ["prevent"]), ["esc"]),
							onInput: n[2] ||= (e) => P(i).setSearchDraft(e.target.value),
							onCompositionstart: n[3] ||= (...e) => P(i).compositionStart && P(i).compositionStart(...e),
							onCompositionend: n[4] ||= (e) => P(i).compositionEnd(e.target.value)
						}, null, 40, At),
						P(A) ? (r(), L("button", {
							key: 0,
							type: "button",
							"aria-label": "清空高级搜索",
							title: "清空高级搜索",
							onClick: ae
						}, "×")) : h("", !0)
					], 32),
					n[12] ||= w("span", {
						id: "accountAdvancedSearchHintV2",
						class: "ac-sr-only"
					}, "空格或 / 表示同时满足；支持方式、地区、邮箱、姓名、来源、备注、ID。完整文字加双引号。", -1),
					w("button", {
						id: "btnResetAccountFiltersV2",
						type: "button",
						class: "ac-link",
						title: "清除全部列筛选",
						onClick: n[6] ||= (...e) => P(i).resetFilters && P(i).resetFilters(...e)
					}, "清筛"),
					w("button", {
						id: "btnResetAccountsColumnsV2",
						type: "button",
						class: "ac-link",
						title: "恢复账号列表默认列宽",
						onClick: oe
					}, "恢复列宽"),
					w("button", {
						id: "btnRefreshAccountsV2",
						type: "button",
						class: "ac-button ui-refresh-button",
						disabled: P(x),
						onClick: n[7] ||= (...e) => P(i).refresh && P(i).refresh(...e)
					}, S(P(x) ? "刷新中…" : "刷新"), 9, jt)
				])
			]),
			d(t.$slots, "feedback"),
			P(O) ? (r(), L("p", Mt, S(P(C)), 1)) : V.value || P(C) && P(c).length ? (r(), L("div", Nt, [w("span", null, S(V.value || P(C)), 1), P(C) ? (r(), L("button", {
				key: 0,
				type: "button",
				class: "ac-link",
				onClick: n[8] ||= (...e) => P(i).refresh && P(i).refresh(...e)
			}, "重试")) : h("", !0)])) : h("", !0),
			f(gt, {
				ref_key: "table",
				ref: I,
				items: P(c),
				selected: P(y),
				query: P(s),
				facets: P(l),
				presentation: e.presentation,
				loading: P(x),
				error: P(C),
				"invalid-search": P(O),
				stale: P(j),
				visible: P(E) && B.value,
				"page-selected": P(M),
				"page-indeterminate": P(F),
				"open-filter": z.value,
				"onUpdate:openFilter": n[9] ||= (e) => z.value = e,
				onFilter: J,
				onClearFilter: X,
				onSelect: P(i).toggle,
				onSelectPage: P(i).togglePage,
				onAction: te,
				onDetail: ne,
				onRetry: P(i).refresh,
				onRendered: n[10] ||= (t) => e.callbacks.afterRender?.(t)
			}, null, 8, [
				"items",
				"selected",
				"query",
				"facets",
				"presentation",
				"loading",
				"error",
				"invalid-search",
				"stale",
				"visible",
				"page-selected",
				"page-indeterminate",
				"open-filter",
				"onSelect",
				"onSelectPage",
				"onRetry"
			]),
			f(K, {
				compact: "",
				page: P(m),
				size: P(g),
				pages: P(v),
				total: P(p),
				busy: P(x),
				"page-sizes": [
					10,
					20,
					30,
					50,
					100
				],
				label: "账号列表分页",
				"onUpdate:page": P(i).setPage,
				"onUpdate:size": P(i).setSize
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		], 512)), [[N, P(E)]]);
	}
});
// src/features/accounts/useAccountDetail.ts
function Ft(e) {
	return JSON.parse(JSON.stringify(e));
}
function It(e, t) {
	if (!e || typeof e != "object" || !("accountId" in e) || String(e.accountId) !== t || !("item" in e) || !e.item || typeof e.item != "object" || Array.isArray(e.item) || "id" in e.item && e.item.id != null && String(e.item.id) !== t) throw Error("账号详情响应不匹配");
	return Ft(e.item);
}
function Lt(e, t) {
	let n = j(null), r = j(0), i = k(() => n.value !== null), a = k(() => n.value ? String(n.value.id) : ""), o = null, s = (e) => o === e && r.value === e.generation;
	function c(e) {
		n.value = { ...e.account };
	}
	async function l(n) {
		try {
			let e = await n.lease.loadPlanDetails(n.id, n.lease.openGeneration);
			if (!s(n)) return;
			Object.assign(n.account, It(e, n.id)), c(n);
		} catch (e) {
			let r = e && typeof e == "object" && "name" in e && e.name === "AbortError";
			s(n) && !r && t.notify("优惠详情加载失败，请重新打开详情重试");
			return;
		}
		let r = "", i = "";
		try {
			let t = await e.roxyProfile(n.id, n.roxyAbort.signal);
			r = String(t.profile_id || "").trim(), i = String(t.window_name || "").trim();
		} catch {}
		s(n) && (n.account.roxy_profile_id = r, n.account.roxy_profile_name = i, c(n));
	}
	function u(e = !0) {
		let i = o;
		if (!i) return;
		o = null;
		let a = ++r.value;
		n.value = null, i.roxyAbort.abort(), i.lease.release(), t.closed?.(e, i.trigger, a);
	}
	function d(e, n, i, a) {
		if (!/^[1-9]\d*$/.test(e) || !n || String(n.id) !== e || !i || typeof i.loadPlanDetails != "function" || typeof i.release != "function") return i?.release?.(), t.notify("账号详情暂不可用，请先刷新列表"), !1;
		let s = Ft(n);
		u(!1);
		let d = {
			id: e,
			generation: ++r.value,
			trigger: a,
			lease: i,
			roxyAbort: new AbortController(),
			account: {
				...s,
				roxy_profile_id: "",
				roxy_profile_name: ""
			}
		};
		return o = d, c(d), t.opened?.(d.generation), l(d), !0;
	}
	return {
		account: I(n),
		generation: I(r),
		isOpen: i,
		accountId: a,
		open: d,
		close: u
	};
}
// src/features/accounts/AccountDetail.vue?vue&type=script&setup=true&lang.ts
var Rt = ["aria-hidden"], zt = ["data-account-id"], Bt = { class: "account-detail-head" }, Vt = { id: "accountDetailTitle" }, Ht = { id: "accountDetailSubtitle" }, Ut = ["innerHTML"], Wt = /* @__PURE__ */ n({
	__name: "AccountDetail",
	props: {
		api: {},
		presentation: {},
		callbacks: {}
	},
	setup(e, { expose: n }) {
		let i = e, a = b(), o = !1, s = null;
		function c() {
			let e = s;
			s = null, e?.isConnected && e.focus({ preventScroll: !0 });
		}
		let u = Lt(i.api, {
			notify: (e) => i.callbacks.notify(e),
			opened(e) {
				s = null, t(() => {
					!o && u.generation.value === e && u.isOpen.value && (i.callbacks.syncModalScrollLock(), a.value?.focus({ preventScroll: !0 }));
				});
			},
			closed(e, n, r) {
				s = e ? n : null, t(() => {
					o || u.generation.value !== r || u.isOpen.value || (i.callbacks.syncModalScrollLock(), c());
				});
			}
		}), { account: d, accountId: f, isOpen: p } = u, m = k(() => d.value ? d.value.email || `账号 #${d.value.id}` : "账号详情"), h = k(() => d.value ? `账号 #${d.value.id} · ${i.presentation.sourceLabel(d.value.email_source) || "未知来源"}` : ""), g = k(() => d.value ? i.presentation.renderBody(d.value) : "");
		function _(e, t, n, r) {
			let i = typeof document < "u" && document.activeElement instanceof HTMLElement ? document.activeElement : null;
			return u.open(e, t, n, r || i);
		}
		function v(e = !0) {
			u.close(e);
		}
		return T(() => {
			o = !0, u.close();
		}), l(() => {
			i.callbacks.syncModalScrollLock(), c();
		}), n({
			open: _,
			close: v
		}), (e, t) => (r(), C(x, { to: "#accountDetailHost" }, [w("div", {
			id: "accountDetailBackdrop",
			class: O(["account-detail-backdrop", { hidden: !P(p) }]),
			"aria-hidden": !P(p),
			onClick: t[0] ||= D((e) => v(), ["self"])
		}, null, 10, Rt), w("aside", {
			id: "accountDetailDrawer",
			class: O(["account-detail-drawer", { hidden: !P(p) }]),
			"data-account-id": P(p) ? P(f) : void 0,
			role: "dialog",
			"aria-modal": "true",
			"aria-labelledby": "accountDetailTitle"
		}, [w("div", Bt, [w("div", null, [
			t[2] ||= w("div", { class: "data-panel-kicker" }, "ACCOUNT DETAIL", -1),
			w("h2", Vt, S(m.value), 1),
			w("p", Ht, S(h.value), 1)
		]), w("button", {
			id: "btnCloseAccountDetail",
			ref_key: "closeButton",
			ref: a,
			type: "button",
			class: "account-detail-close",
			"aria-label": "关闭账号详情",
			onClick: t[1] ||= (e) => v()
		}, "×", 512)]), w("div", {
			id: "accountDetailBody",
			class: "account-detail-body",
			innerHTML: g.value
		}, null, 8, Ut)], 10, zt)]));
	}
}), Gt = (e) => e === "only" ? "已归档账号" : e === "all" ? "全部账号" : "未归档账号", Kt = (e) => ({
	running: "进行中",
	completed: "已完成",
	interrupted: "已中断"
})[String(e)] || String(e ?? ""), qt = (e) => ({
	deactivated_skipped: "已废跳过",
	rejected: "未能入队",
	failed: "查活失败",
	error: "执行异常",
	attention_required: "执行失败",
	interrupted: "执行中断"
})[String(e)] || String(e ?? ""), Jt = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : String(e);
function Yt(e) {
	return e && typeof e == "object" ? e : {};
}
function Xt(e) {
	return Object.freeze((Array.isArray(e) ? e : []).map((e) => Object.freeze({ ...Yt(e) })));
}
function Zt(e) {
	let n = b(!1), r = b(!1), i = b(!1), o = b("0"), s = b(3), c = b(!1), l = b(""), u = b(1), d = b(1), f = b(null), p = j([]), h = j([]), g = b(0), _ = b(0), v = b(!1), y = b(!1), x = b(""), S = b(!1), C = b(!1), w = b(!1), T = null, E = 0, D = 0, O = !1, A, M, N, P = () => typeof document > "u" || !document.hidden, F = k(() => v.value ? `共 ${g.value} 条 · 第 ${u.value} 页` : ""), I = k(() => y.value ? `共 ${_.value} 条 · 第 ${d.value} 页` : "");
	async function L(t, n = {}, r = new AbortController()) {
		let i = setTimeout(() => r.abort(), 3e4);
		try {
			return Yt(await e.request(t, {
				...n,
				signal: r.signal
			}));
		} finally {
			clearTimeout(i);
		}
	}
	function R() {
		for (let t of [e.refreshAccounts, e.refreshSummary]) try {
			Promise.resolve(t()).catch(() => {});
		} catch {}
	}
	function z(t) {
		O || (o.value = t.archived, s.value = Math.min(16, e.operationWorkers()), l.value = "", n.value = !0);
	}
	async function B() {
		let r = Number(s.value);
		if (!(O || c.value || !Number.isInteger(r) || r < 1 || r > 16)) {
			c.value = !0;
			try {
				T ||= e.randomUUID();
				let i = await L("/api/accounts/inspections", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						workers: r,
						archived: o.value,
						idempotency_key: T
					})
				});
				if (T = null, w.value = !0, O || (n.value = !1, e.notify(i.created ? "巡检已加入统一任务队列" : "已有本次巡检记录，已打开任务中心"), await t(), O)) return;
				try {
					await e.openTasks({ filters: {
						type: "account_inspection_batch",
						target: ""
					} });
				} catch (t) {
					O || e.notify(`巡检请求已处理，打开任务失败：${Jt(t)}`);
				}
			} catch (e) {
				O || (l.value = `巡检启动请求失败：${Jt(e)}。可查看巡检历史，或使用当前提交再次确认。`);
			} finally {
				c.value = !1;
			}
		}
	}
	function V() {
		O || (u.value = 1, ++E, r.value = !0, U());
	}
	function H(e) {
		S.value || (u.value = Math.max(1, u.value + e), ++E, U());
	}
	async function U() {
		if (O || S.value || !r.value || !P()) return;
		S.value = !0;
		let t = u.value, n = E, i = new AbortController();
		A = i;
		try {
			let e = await L(`/api/accounts/inspections?page=${t}`, {}, i);
			if (O || i.signal.aborted || !r.value || t !== u.value || n !== E) return;
			let a = w.value;
			w.value = !!e.active, a && !w.value && R(), p.value = Xt(e.items), g.value = Number(e.total), v.value = !0;
		} catch (t) {
			!O && r.value && P() && n === E && e.notify(`读取巡检历史失败：${Jt(t)}`);
		} finally {
			S.value = !1, A === i && (A = void 0), n !== E && !O && r.value && P() && U();
		}
	}
	function W(e) {
		O || (f.value = Number(e), d.value = 1, ++D, y.value = !1, x.value = "", h.value = [], i.value = !0, K());
	}
	function G(e) {
		C.value || (d.value = Math.max(1, d.value + e), ++D, K());
	}
	async function K() {
		if (O || C.value || !f.value || !i.value || !P()) return;
		C.value = !0;
		let e = f.value, t = d.value, n = D, r = new AbortController();
		M = r;
		try {
			let a = await L(`/api/accounts/inspections/${e}/failures?page=${t}`, {}, r);
			if (O || r.signal.aborted || !i.value || e !== f.value || t !== d.value || n !== D) return;
			h.value = Xt(a.items), _.value = Number(a.total), y.value = !0, x.value = "";
		} catch (e) {
			!O && i.value && P() && n === D && (x.value = `读取失败：${Jt(e)}，可点击刷新重试。`);
		} finally {
			C.value = !1, M === r && (M = void 0), n !== D && !O && i.value && P() && K();
		}
	}
	async function q(t) {
		if (!O) try {
			if (await L(`/api/accounts/inspections/${Number(t)}/cancel`, { method: "POST" }), O) return;
			e.notify("已请求停止，将在安全检查点结束"), U();
		} catch (t) {
			O || e.notify(`停止巡检失败：${Jt(t)}`);
		}
	}
	function J(e) {
		e && e !== "start" || (n.value = !1), e && e !== "history" || (r.value = !1, ++E, A?.abort()), e && e !== "failures" || (i.value = !1, ++D, M?.abort());
	}
	function Y() {
		N !== void 0 && (clearInterval(N), N = void 0), !O && P() && (r.value || i.value) && (N = setInterval(() => {
			r.value && U(), i.value && K();
		}, 5e3));
	}
	function X() {
		P() || (++E, ++D, A?.abort(), M?.abort()), Y();
	}
	return a([r, i], Y, { flush: "sync" }), typeof document < "u" && document.addEventListener("visibilitychange", X), m(() => {
		O = !0, J(), Y(), typeof document < "u" && document.removeEventListener("visibilitychange", X);
	}), {
		startOpen: n,
		historyOpen: r,
		failuresOpen: i,
		archived: o,
		workers: s,
		starting: c,
		startError: l,
		historyPage: u,
		failurePage: d,
		failureId: f,
		historyRows: p,
		failureRows: h,
		historyTotal: g,
		failureTotal: _,
		historyReady: v,
		failureReady: y,
		failureError: x,
		historyLoading: S,
		failureLoading: C,
		historyLabel: F,
		failureLabel: I,
		openStart: z,
		submit: B,
		openHistory: V,
		openFailures: W,
		close: J,
		changeHistoryPage: H,
		changeFailuresPage: G,
		refreshHistory: U,
		refreshFailures: K,
		stop: q
	};
}
// src/features/accounts/Inspection.vue?vue&type=script&setup=true&lang.ts
var Qt = ["data-archived"], $t = { class: "modal-header" }, en = { id: "accountInspectionScope" }, tn = {
	id: "accountInspectionStartError",
	role: "status"
}, nn = ["disabled"], rn = { class: "modal-header" }, an = {
	key: 0,
	"data-inspection-scroll": "",
	tabindex: "0",
	role: "region",
	"aria-label": "可左右滚动查看巡检记录"
}, on = { class: "data-table" }, sn = ["data-inspection-task", "onClick"], cn = { class: "sub-cell" }, ln = { class: "sub-cell" }, un = { key: 0 }, dn = ["onClick"], fn = ["onClick"], pn = { key: 1 }, mn = { class: "jobs-v2-pager" }, hn = ["disabled"], gn = { id: "accountInspectionPageLabel" }, _n = ["disabled"], vn = { class: "modal-header" }, yn = { id: "accountInspectionFailuresTitle" }, bn = { key: 0 }, xn = {
	key: 1,
	"data-inspection-scroll": "",
	tabindex: "0",
	role: "region",
	"aria-label": "可左右滚动查看巡检记录"
}, Sn = { class: "data-table" }, Cn = { class: "inspection-error-reason" }, wn = { key: 2 }, Tn = { class: "jobs-v2-pager" }, En = ["disabled"], Dn = { id: "accountInspectionFailuresPageLabel" }, On = ["disabled"], kn = /*#__PURE__*/ F(/* @__PURE__ */ n({
	__name: "Inspection",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, c = Zt(i.deps), { startOpen: l, historyOpen: u, failuresOpen: d, archived: f, workers: m, starting: g, startError: _, historyPage: y, failurePage: x, failureId: C, historyRows: E, failureRows: O, historyTotal: k, failureTotal: A, historyReady: j, failureReady: N, failureError: F, historyLabel: I, failureLabel: z } = c, B = b(), V = b(), H = b(), U = b(), W = b(), G = /* @__PURE__ */ new Map(), K = {
			start: 0,
			history: 0,
			failures: 0
		}, q = {
			start: B,
			history: V,
			failures: H
		}, J = {
			start: l,
			history: u,
			failures: d
		}, Y = !1;
		function X(e, t) {
			J[e].value || G.set(e, t ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null));
		}
		function ee(e, t) {
			X("start", t), c.openStart(e), se("start");
		}
		function te(e) {
			X("history", e), c.openHistory(), se("history");
		}
		function ne(e, t) {
			X("failures", t), c.openFailures(e), se("failures");
		}
		function re(e) {
			c.close(e);
			let t = G.get(e);
			if (G.delete(e), Y) return;
			let n = V.value?.open ? V.value.querySelector("button:not([disabled])") : i.deps.fallbackFocus?.();
			(t?.isConnected ? t : n)?.focus({ preventScroll: !0 });
		}
		function ie(e) {
			K[e] ? --K[e] : q[e].value?.open || re(e);
		}
		function ae(e) {
			let t = q[e].value;
			t?.open && (++K[e], t.close(), re(e));
		}
		function oe(e) {
			c.close(e);
			for (let t of [
				"failures",
				"history",
				"start"
			]) e && e !== t || ae(t);
		}
		async function se(e) {
			await t();
			let n = q[e].value, r = J[e].value;
			n && !Y && (r && !n.open ? (G.has(e) || G.set(e, document.activeElement instanceof HTMLElement ? document.activeElement : null), n.showModal()) : !r && n.open && ae(e));
		}
		for (let e of [
			"start",
			"history",
			"failures"
		]) a(J[e], () => se(e), { flush: "post" });
		a(y, () => {
			if (U.value) {
				U.value.scrollTop = 0;
				let e = U.value.querySelector("[data-inspection-scroll]");
				e && (e.scrollLeft = 0);
			}
		}), a([x, C], () => {
			if (W.value) {
				W.value.scrollTop = 0;
				let e = W.value.querySelector("[data-inspection-scroll]");
				e && (e.scrollLeft = 0);
			}
		});
		function ce(e) {
			oe("history"), i.deps.openTask(Number(e.task_id));
		}
		function le(e) {
			return Number(e.live_failed_count || 0) + Number(e.deactivated_skipped_count || 0);
		}
		return T(() => {
			Y = !0;
			for (let e of Object.values(q)) e.value?.open && e.value.close();
			G.clear();
		}), n({
			openStart: ee,
			openHistory: te,
			openFailures: ne,
			close: oe,
			refreshHistory: c.refreshHistory,
			refreshFailures: c.refreshFailures,
			changeHistoryPage: c.changeHistoryPage,
			changeFailuresPage: c.changeFailuresPage,
			stop: c.stop
		}), (t, n) => (r(), L(v, null, [
			w("dialog", {
				ref_key: "start",
				ref: B,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionStart",
				"aria-labelledby": "accountInspectionStartTitle",
				"data-archived": P(f),
				onClose: n[3] ||= (e) => ie("start")
			}, [w("div", $t, [n[14] ||= w("h2", { id: "accountInspectionStartTitle" }, "启动账号巡检", -1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				"aria-label": "关闭启动巡检",
				onClick: n[0] ||= (e) => oe("start")
			}, "关闭")]), w("form", { onSubmit: n[2] ||= D((...e) => P(c).submit && P(c).submit(...e), ["prevent"]) }, [
				w("p", en, "本次范围：" + S(P(Gt)(P(f))), 1),
				n[15] ||= w("p", null, "该归档范围内全部账号，不限当前页，不受勾选、搜索或其他筛选条件影响。", -1),
				n[16] ||= w("p", null, "已废账号跳过；AT 本地有效则结束；失效时自动刷新，再复用登录会话查套餐。", -1),
				n[17] ||= w("label", { for: "accountInspectionWorkers" }, "并发账号数", -1),
				o(w("input", {
					id: "accountInspectionWorkers",
					"onUpdate:modelValue": n[1] ||= (e) => p(m) ? m.value = e : null,
					type: "number",
					min: "1",
					max: "16",
					step: "1",
					required: ""
				}, null, 512), [[M, P(m)]]),
				n[18] ||= w("p", null, "支持 1–16；实际并发同时受共享账号操作预算限制。", -1),
				w("p", tn, S(P(_)), 1),
				w("button", {
					type: "submit",
					class: "jobs-tb-btn jobs-tb-btn--primary",
					id: "btnConfirmAccountInspection",
					disabled: P(g)
				}, "开始巡检", 8, nn)
			], 32)], 40, Qt),
			w("dialog", {
				ref_key: "history",
				ref: V,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionHistory",
				"aria-labelledby": "accountInspectionHistoryTitle",
				onClose: n[8] ||= (e) => ie("history")
			}, [
				w("div", rn, [
					n[19] ||= w("h2", { id: "accountInspectionHistoryTitle" }, "账号巡检历史", -1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[4] ||= (...e) => P(c).refreshHistory && P(c).refreshHistory(...e)
					}, "刷新"),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[5] ||= (e) => oe("history")
					}, "关闭")
				]),
				n[20] ||= w("p", null, "每 5 秒刷新。进度包含跳过；完成表示本轮处理结束，查活和套餐结果分别统计。", -1),
				w("div", {
					ref_key: "historyContent",
					ref: U,
					id: "accountInspectionHistoryContent",
					"aria-live": "polite"
				}, [P(E).length ? (r(), L("div", an, [w("table", on, [w("thead", null, [w("tr", null, [(r(), L(v, null, s([
					"任务",
					"范围",
					"状态 / 时间",
					"并发",
					"进度",
					"AT失效",
					"查活 成功/失败",
					"套餐 成功/失败",
					"操作"
				], (e) => w("th", {
					key: e,
					scope: "col"
				}, S(e), 1)), 64))])]), w("tbody", null, [(r(!0), L(v, null, s(P(E), (t, n) => (r(), L("tr", { key: String(t.id ?? n) }, [
					w("td", null, [w("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-inspection-task": Number(t.id),
						onClick: (e) => ce(t)
					}, "#" + S(Number(t.id)), 9, sn)]),
					w("td", null, S(P(Gt)(String(t.archived))), 1),
					w("td", null, [R(S(P(Kt)(t.status)), 1), w("div", cn, S(e.deps.formatDateTime(t.created_at)), 1)]),
					w("td", null, S(Number(t.workers)), 1),
					w("td", null, [R(S(Number(t.checked_count) + Number(t.skipped_count)) + " / " + S(Number(t.total_count)), 1), w("div", ln, "跳过 " + S(Number(t.skipped_count)) + "（已废 " + S(Number(t.deactivated_skipped_count)) + "）", 1)]),
					w("td", null, S(Number(t.invalid_count)), 1),
					w("td", null, [R(S(Number(t.live_success_count)) + " / " + S(Number(t.live_failed_count)), 1), le(t) ? (r(), L("div", un, [w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: (e) => ne(Number(t.id), e.currentTarget)
					}, "失败详情 " + S(le(t)), 9, dn)])) : h("", !0)]),
					w("td", null, S(Number(t.plan_success_count)) + " / " + S(Number(t.plan_failed_count)), 1),
					w("td", null, [t.status === "running" ? (r(), L("button", {
						key: 0,
						type: "button",
						class: "jobs-tb-btn",
						onClick: (e) => P(c).stop(Number(t.id))
					}, "停止", 8, fn)) : h("", !0)])
				]))), 128))])])])) : (r(), L("p", pn, S(P(j) ? "暂无巡检记录。" : "正在读取巡检历史…"), 1))], 512),
				w("div", mn, [
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionPrev",
						disabled: P(y) <= 1,
						onClick: n[6] ||= (e) => P(c).changeHistoryPage(-1)
					}, "上一页", 8, hn),
					w("span", gn, S(P(I)), 1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionNext",
						disabled: P(y) * 20 >= P(k),
						onClick: n[7] ||= (e) => P(c).changeHistoryPage(1)
					}, "下一页", 8, _n)
				])
			], 544),
			w("dialog", {
				ref_key: "failures",
				ref: H,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionFailures",
				"aria-labelledby": "accountInspectionFailuresTitle",
				onClose: n[13] ||= (e) => ie("failures")
			}, [
				w("div", vn, [
					w("h2", yn, S(P(C) ? `巡检 #${P(C)} · 失败详情` : "巡检失败详情"), 1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[9] ||= (...e) => P(c).refreshFailures && P(c).refreshFailures(...e)
					}, "刷新"),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[10] ||= (e) => oe("failures")
					}, "关闭")
				]),
				n[21] ||= w("p", null, "保留本轮原始执行快照，后续重跑或删除账号不会改写；含已废跳过，套餐单独失败不计为查活失败。", -1),
				w("div", {
					ref_key: "failureContent",
					ref: W,
					id: "accountInspectionFailuresContent",
					"aria-live": "polite"
				}, [P(F) ? (r(), L("p", bn, S(P(F)), 1)) : P(O).length ? (r(), L("div", xn, [w("table", Sn, [w("thead", null, [w("tr", null, [(r(), L(v, null, s([
					"账号",
					"邮箱",
					"类型",
					"时间",
					"原因"
				], (e) => w("th", {
					key: e,
					scope: "col"
				}, S(e), 1)), 64))])]), w("tbody", null, [(r(!0), L(v, null, s(P(O), (t, n) => (r(), L("tr", { key: String(t.account_id ?? n) }, [
					w("td", null, "#" + S(Number(t.account_id)), 1),
					w("td", null, S(t.email), 1),
					w("td", null, S(P(qt)(t.status)), 1),
					w("td", null, S(e.deps.formatDateTime(t.failed_at)), 1),
					w("td", Cn, S(t.error), 1)
				]))), 128))])])])) : (r(), L("p", wn, S(P(N) ? "本轮暂无查活失败或已废跳过。" : "正在读取本次失败记录…"), 1))], 512),
				w("div", Tn, [
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresPrev",
						disabled: !P(N) || P(x) <= 1,
						onClick: n[11] ||= (e) => P(c).changeFailuresPage(-1)
					}, "上一页", 8, En),
					w("span", Dn, S(P(z)), 1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresNext",
						disabled: !P(N) || P(x) * 20 >= P(A),
						onClick: n[12] ||= (e) => P(c).changeFailuresPage(1)
					}, "下一页", 8, On)
				])
			], 544)
		], 64));
	}
}), [["__scopeId", "data-v-88e51d48"]]);
// src/features/accounts/taskNavigation.ts
function An(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) return null;
	let t = e, n = [t, ...[
		"started",
		"queued",
		"reused"
	].flatMap((e) => Array.isArray(t[e]) ? t[e] : [])];
	for (let e of n) {
		if (!e || typeof e != "object" || Array.isArray(e)) continue;
		let t = e, n = t.operation_task_id || t.task_id;
		if (n) return {
			taskId: ue(n),
			runId: de(t.operation_run_id || t.run_id)
		};
	}
	return null;
}
async function jn(e, t) {
	let n = t.single ? An(t.result) : null;
	n && e.openTask ? await e.openTask(n.taskId, n.runId) : await e.openTasks({
		filters: {
			type: t.type,
			target: t.single && t.target || ""
		},
		...n || {}
	});
}
// src/features/accounts/useC2aReimport.ts
function Mn(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Nn(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(Nn), Object.freeze(e)), e;
}
function Pn(e) {
	return Nn(JSON.parse(JSON.stringify(e)));
}
var Fn = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败";
function In(e) {
	let t = /* @__PURE__ */ new Map();
	for (let n of [e.skipped, e.failed]) for (let e of Array.isArray(n) ? n : []) {
		let n = e && typeof e == "object" ? e : {}, r = String(n.reason || n.error || n.error_code || "服务端未返回原因，请重试");
		t.set(r, (t.get(r) || 0) + 1);
	}
	return t.size ? `；未入队原因：${[...t].slice(0, 3).map(([e, t]) => `${e}${t > 1 ? `（${t} 个）` : ""}`).join("；")}${t.size > 3 ? `；另有 ${t.size - 3} 类原因` : ""}` : "；未入队原因：服务端未返回原因，请重试";
}
function Ln(e) {
	return [
		"queued",
		"skipped",
		"failed"
	].flatMap((t, n) => (Array.isArray(e[t]) ? e[t] : []).map((e) => ({
		item: Mn(e),
		state: [
			"已入队",
			"未入队",
			"入队失败"
		][n]
	})));
}
function Rn(e, t = {}) {
	let n = b(!1), r = b(!1), i = b(""), a = j([]), o = j(null), s = null, c = null, l = !1, u = k(() => o.value ? Ln(o.value) : []), d = k(() => u.value.filter((e) => Number(e.item.task_id) > 0)), f = k(() => {
		let e = o.value;
		return e ? `C2A 重新导入：已入队 ${Number(e.queued_count ?? (Array.isArray(e.queued) ? e.queued.length : 0))} 个，未入队 ${Number(e.skipped_count ?? (Array.isArray(e.skipped) ? e.skipped.length : 0)) + Number(e.failed_count ?? (Array.isArray(e.failed) ? e.failed.length : 0))} 个` : "";
	});
	function p(t, o = null) {
		if (l) return !1;
		if (n.value) return e.notify("C2A 同步确认窗口不可用，请刷新页面后重试"), !1;
		let u = t.accountIds.map((e) => {
			if (!/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
			return Number(e);
		});
		return u.length ? (s = Pn(t), a.value = Object.freeze([...u]), c = o, r.value = !1, i.value = "", n.value = !0, !0) : (e.notify("请先选择账号"), !1);
	}
	function h(e = "cancel", i = !1) {
		if (!n.value || r.value && !i) return !1;
		let o = c;
		return n.value = !1, a.value = [], s = null, c = null, t.closed?.(o, e), !0;
	}
	async function g(t, n) {
		try {
			await t();
		} catch (t) {
			e.notify(n + Fn(t));
		}
	}
	function _(e) {
		o.value = Pn(Mn(e));
	}
	function v(t = d.value.map((e) => e.item)) {
		let n = t.length === 1 ? t[0] : null, r = n ? An(n) : null;
		return g(() => e.openTasks({
			filters: {
				type: "c2a_session_reimport",
				target: ""
			},
			taskId: r?.taskId,
			runId: r?.runId ?? null
		}), "C2A 请求已处理，打开任务失败: ");
	}
	async function y() {
		if (l || !n.value || !s || !a.value.length || r.value) return;
		let t = [...a.value], o = s, u = c;
		r.value = !0, i.value = "正在创建 C2A 同步任务…";
		let d = e.beginBusy?.(u, "提交导入…"), f;
		try {
			f = Mn(await e.request("/api/accounts/c2a/sync-bulk", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ account_ids: t })
			}));
		} catch (t) {
			e.notify("重新导入 C2A 失败: " + Fn(t)), l || (i.value = `提交失败：${Fn(t)}。请检查后再次提交。`), r.value = !1, d?.(), e.selectionChanged?.(o);
			return;
		}
		let p = !1;
		try {
			let t = Number(f.skipped_count ?? (Array.isArray(f.skipped) ? f.skipped.length : 0)) + Number(f.failed_count ?? (Array.isArray(f.failed) ? f.failed.length : 0)), n = t ? In(f) : "";
			f.accepted ? (p = Number(f.queued_count ?? (Array.isArray(f.queued) ? f.queued.length : 0)) > 0, e.notify(`C2A 重新导入已入队 ${f.queued_count ?? (Array.isArray(f.queued) ? f.queued.length : 0)} 个，未入队 ${t} 个，请在任务中心查看结果${n}`)) : (e.notify(t ? `C2A 已重新导入 ${f.updated_count || 0} 个，跳过/失败 ${t} 个${n}` : `C2A 已重新导入 ${f.updated_count || 0} 个`), await g(() => e.refreshAccounts(o), "C2A 请求已处理，页面更新失败: "));
		} catch (t) {
			e.notify("C2A 请求已处理，回执更新失败: " + Fn(t));
		} finally {
			r.value = !1;
			try {
				d?.();
			} finally {
				l || h(p ? "submitted" : "cancel", !0);
			}
		}
		p && !l && await g(() => jn({
			openTasks: e.openTasks,
			openTask: e.openTask
		}, {
			single: !1,
			type: "c2a_session_reimport",
			target: "",
			result: f
		}), "C2A 请求已处理，打开任务失败: ");
	}
	return m(() => {
		l = !0, h("cancel", !0);
	}), {
		isOpen: n,
		submitting: r,
		status: i,
		accountIds: a,
		result: o,
		receiptEntries: u,
		taskEntries: d,
		summary: f,
		open: p,
		close: h,
		submit: y,
		showResult: _,
		openTasks: v
	};
}
// src/features/accounts/useAccountEmailChange.ts
function zn(e) {
	return JSON.parse(JSON.stringify(e));
}
function Bn(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(Bn), Object.freeze(e)), e;
}
function Vn(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Hn(e) {
	return e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败，请稍后重试";
}
function Un(e) {
	return [...new Set((Array.isArray(e?.accountIds) ? e.accountIds : []).map(Number).filter((e) => Number.isSafeInteger(e) && e > 0).map(String))];
}
function Wn(e, t) {
	if (t === "single") return !0;
	let n = [
		"started",
		"queued",
		"reused"
	].filter((t) => Object.prototype.hasOwnProperty.call(e, t)).map((t) => e[t]);
	if (n.length) return n.some((e) => Array.isArray(e) && e.length > 0);
	let r = [
		"started_count",
		"queued_count",
		"reused_count"
	].filter((t) => Object.prototype.hasOwnProperty.call(e, t)).map((t) => Number(e[t]));
	return r.length ? r.some((e) => Number.isFinite(e) && e > 0) : e.accepted !== !1;
}
function Gn(e) {
	for (let t of ["skipped", "failed"]) for (let n of Array.isArray(e[t]) ? e[t] : []) {
		if (!n || typeof n != "object" || Array.isArray(n)) continue;
		let e = n;
		if ([
			"reason",
			"error",
			"error_code"
		].some((t) => String(e[t] || "").trim())) return !0;
	}
	return !1;
}
function Kn(e, t = {}) {
	let n = b(!1), r = b(0), i = b("single"), a = j(null), o = j(null), s = j([]), c = j([]), l = b(""), u = b("idle"), d = b(""), f = b(!1), p = k(() => u.value !== "ready" || !c.value.some((e) => e.enabled)), h = null, g = !1, _ = (e) => !g && h === e && r.value === e.generation && n.value;
	function v({ restoreFocus: e = !0 } = {}) {
		let i = h;
		i && (h = null, ++r.value, i.controller.abort(), n.value = !1, a.value = null, o.value = null, s.value = [], c.value = [], l.value = "", u.value = "idle", d.value = "", f.value = !1, t.closed?.(e, i.trigger, r.value));
	}
	async function y(n, r) {
		try {
			let t = Vn(await e.request("/api/email-sources", { signal: n.controller.signal }));
			if (!_(n)) return;
			c.value = Bn((Array.isArray(t.sources) ? t.sources : []).map((e) => {
				let t = Vn(e);
				return {
					value: String(t.value || ""),
					label: String(t.label || t.value || ""),
					enabled: !!t.enabled,
					reason: String(t.reason || "")
				};
			}));
			let i = c.value.filter((e) => e.enabled);
			l.value = (i.find((e) => e.value === r) || i[0])?.value || "", u.value = "ready", d.value = i.length ? "" : "没有已配置且可用的新邮箱来源";
		} catch (e) {
			if (!_(n)) return;
			u.value = "failed", c.value = [], l.value = "", d.value = `邮箱来源读取失败：${Hn(e)}`;
		}
		_(n) && t.sourcesReady?.(n.generation);
	}
	function x(e, p, m, _, b) {
		if (g) return !1;
		let x = Bn(zn({
			..._,
			accountIds: p
		}));
		v({ restoreFocus: !1 });
		let S = {
			generation: ++r.value,
			mode: e,
			account: m,
			accountIds: Bn([...p]),
			context: x,
			trigger: b,
			controller: new AbortController(),
			submitting: !1
		};
		return h = S, i.value = e, a.value = m, s.value = S.accountIds, o.value = x, n.value = !0, u.value = "loading", l.value = "", d.value = "", c.value = [], f.value = !1, t.opened?.(S.generation), y(S, String(m?.email_source || "").trim().toLowerCase()), !0;
	}
	function S(t, n, r = null) {
		let i = Number(t), a = String(i), o = n?.rowHints?.find((e) => String(e.id) === a);
		return !Number.isSafeInteger(i) || i <= 0 || !Un(n).includes(a) || !o ? (e.notify("账号详情暂不可用，请先刷新列表"), !1) : x("single", [a], Bn({
			id: i,
			email: String(o.email || ""),
			email_source: String(o.email_source || "")
		}), n, r);
	}
	function C(t, n = null) {
		let r = Un(t);
		return r.length ? r.length > 500 ? (e.notify("单次最多换绑 500 个账号"), !1) : x("bulk", r, null, t, n) : (e.notify("请先选择账号"), !1);
	}
	function w(t, n) {
		try {
			Promise.resolve(t()).catch((t) => e.notify(n + Hn(t)));
		} catch (t) {
			e.notify(n + Hn(t));
		}
	}
	async function T() {
		let t = h;
		if (!t || !_(t) || t.submitting) return;
		let n = l.value;
		if (u.value !== "ready" || !n || !c.value.some((e) => e.value === n && e.enabled)) {
			d.value = "请选择新邮箱来源";
			return;
		}
		d.value = "", f.value = !0, t.submitting = !0;
		let r;
		try {
			r = Vn(await e.request(t.mode === "bulk" ? "/api/accounts/email-change-bulk" : `/api/accounts/${t.account.id}/email-change`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(t.mode === "bulk" ? {
					account_ids: t.accountIds.map(Number),
					email_source: n
				} : { email_source: n })
			}));
		} catch (n) {
			_(t) && (d.value = `提交失败：${Hn(n)}`), e.notify("换绑邮箱失败: " + Hn(n));
			return;
		} finally {
			t.submitting = !1, _(t) && (f.value = !1);
		}
		let i = _(t);
		if (t.mode === "bulk") {
			let t = Number(r.started_count ?? (Array.isArray(r.started) ? r.started.length : 0)), n = Number(r.skipped_count ?? (Array.isArray(r.skipped) ? r.skipped.length : 0)) + Number(r.failed_count ?? (Array.isArray(r.failed) ? r.failed.length : 0)), i = n && Gn(r) ? In(r) : "";
			e.notify(`批量换绑已入队 ${t} 个${n ? `，跳过 ${n} 个${i}` : ""}`);
		} else e.notify(String(r.message || `邮箱换绑已入队 · 任务 #${r.task_id || "-"}`));
		i && v({ restoreFocus: !1 }), w(() => e.refreshAccounts(t.context), "换绑已受理，刷新账号失败："), i && !g && !h && Wn(r, t.mode) && w(() => jn({
			openTasks: e.openTasks,
			openTask: e.openTask
		}, {
			single: t.mode === "single",
			type: "email_change",
			target: t.mode === "single" ? t.account.email || String(t.account.id) : "",
			result: r
		}), "换绑已受理，打开任务失败：");
	}
	return m(() => {
		g = !0, v();
	}), {
		isOpen: n,
		generation: r,
		mode: i,
		account: a,
		context: o,
		accountIds: s,
		sources: c,
		source: l,
		sourceStatus: u,
		sourceDisabled: p,
		error: d,
		submitting: f,
		openSingle: S,
		openBulk: C,
		close: v,
		submit: T
	};
}
// src/features/accounts/EmailChange.vue?vue&type=script&setup=true&lang.ts
var qn = [
	"aria-hidden",
	"data-account-id",
	"data-account-ids"
], Jn = {
	class: "email-change-dialog",
	role: "document"
}, Yn = { class: "email-change-head" }, Xn = { id: "emailChangeTitle" }, Zn = { id: "emailChangeAccountLabel" }, Qn = {
	class: "email-change-field",
	for: "emailChangeSource"
}, $n = ["disabled"], er = { value: "" }, tr = [
	"value",
	"disabled",
	"title",
	"data-reason"
], nr = ["hidden"], rr = { class: "email-change-foot" }, ir = ["disabled"], ar = /* @__PURE__ */ n({
	__name: "EmailChange",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, a = b(), c = b(), u = b(), d = !1, f = null;
		function m() {
			let e = f;
			f = null, e?.isConnected && e.focus({ preventScroll: !0 });
		}
		let h = Kn(i.deps, {
			opened(e) {
				f = null, t(() => {
					!d && h.generation.value === e && h.isOpen.value && (c.value?.setCustomValidity(""), i.deps.syncModalScrollLock(), u.value?.focus({ preventScroll: !0 }));
				});
			},
			sourcesReady(e) {
				t(() => {
					!d && h.generation.value === e && h.isOpen.value && c.value?.focus({ preventScroll: !0 });
				});
			},
			closed(e, n, r) {
				f = e ? n : null, t(() => {
					d || h.generation.value !== r || h.isOpen.value || (i.deps.syncModalScrollLock(), m());
				});
			}
		}), { isOpen: _, account: y, accountIds: E, mode: A, sources: j, source: M, sourceStatus: N, sourceDisabled: F, error: I, submitting: R } = h, z = k(() => _.value && A.value === "bulk" ? "批量换绑邮箱" : "换绑邮箱"), B = k(() => _.value ? A.value === "bulk" ? `已选 ${E.value.length} 个账号 · 将按账号分别领取新邮箱` : `账号 #${y.value?.id} · 当前邮箱 ${y.value?.email || "-"}` : ""), V = k(() => N.value === "loading" ? "正在读取邮箱来源…" : N.value === "failed" ? "邮箱来源读取失败" : N.value === "ready" ? "请选择邮箱来源" : "打开弹窗后读取可用来源");
		function H(e) {
			return e || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
		}
		function U(e, t, n = null) {
			return h.openSingle(e, t, H(n));
		}
		function W(e, t = null) {
			return h.openBulk(e, H(t));
		}
		function G(e = {}) {
			h.close(e);
		}
		async function K() {
			c.value?.setCustomValidity(""), !c.value?.checkValidity() || !M.value || F.value ? (c.value?.setCustomValidity("请选择新邮箱来源"), h.error.value = "请选择新邮箱来源", c.value?.reportValidity(), c.value?.focus()) : await h.submit();
		}
		function q(e) {
			if (!_.value) return;
			if (e.key === "Escape") {
				e.preventDefault(), G();
				return;
			}
			if (e.key !== "Tab") return;
			let t = Array.from(a.value?.querySelectorAll("button, select, [href], [tabindex]:not([tabindex=\"-1\"])") || []).filter((e) => !("disabled" in e && e.disabled) && !e.hidden), n = t[0], r = t.at(-1);
			e.shiftKey && document.activeElement === n ? (e.preventDefault(), r?.focus()) : !e.shiftKey && document.activeElement === r && (e.preventDefault(), n?.focus());
		}
		return document.addEventListener("keydown", q), T(() => {
			d = !0, document.removeEventListener("keydown", q), h.close();
		}), l(() => {
			i.deps.syncModalScrollLock(), m();
		}), n({
			openSingle: U,
			openBulk: W,
			close: G
		}), (e, t) => (r(), C(x, { to: "#accountEmailChangeHost" }, [w("div", {
			ref_key: "modal",
			ref: a,
			id: "emailChangeModal",
			class: O(["email-change-modal", { hidden: !P(_) }]),
			role: "dialog",
			"aria-modal": "true",
			"aria-hidden": !P(_),
			"aria-labelledby": "emailChangeTitle",
			"aria-describedby": "emailChangeNote",
			"data-account-id": P(_) && P(A) === "single" ? String(P(y)?.id) : "",
			"data-account-ids": P(_) && P(A) === "bulk" ? JSON.stringify(P(E).map(Number)) : "",
			onClick: t[3] ||= D((e) => G(), ["self"])
		}, [w("div", Jn, [w("div", Yn, [w("div", null, [
			t[4] ||= w("div", { class: "data-panel-kicker" }, "PROTOCOL OPERATION", -1),
			w("h2", Xn, S(z.value), 1),
			w("p", Zn, S(B.value), 1)
		]), w("button", {
			ref_key: "closeButton",
			ref: u,
			id: "btnCloseEmailChange",
			type: "button",
			class: "account-detail-close",
			"aria-label": "关闭换绑邮箱",
			onClick: t[0] ||= (e) => G()
		}, "×", 512)]), w("form", {
			id: "emailChangeForm",
			class: "email-change-form",
			novalidate: "",
			onSubmit: D(K, ["prevent"])
		}, [
			w("label", Qn, [
				t[5] ||= w("span", null, "新邮箱来源", -1),
				o(w("select", {
					ref_key: "select",
					ref: c,
					id: "emailChangeSource",
					"onUpdate:modelValue": t[1] ||= (e) => p(M) ? M.value = e : null,
					name: "email_source",
					required: "",
					disabled: P(F),
					"aria-describedby": "emailChangeSourceHelp emailChangeSourceError"
				}, [w("option", er, S(V.value), 1), (r(!0), L(v, null, s(P(j), (e, t) => (r(), L("option", {
					key: `${e.value}:${t}`,
					value: e.value,
					disabled: !e.enabled,
					title: e.reason,
					"data-reason": e.reason
				}, S(e.label) + S(e.enabled ? "" : "（不可用）"), 9, tr))), 128))], 8, $n), [[g, P(M)]]),
				t[6] ||= w("small", { id: "emailChangeSourceHelp" }, "系统会从所选邮箱池自动领取新地址，并读取新邮箱验证码。", -1),
				w("small", {
					id: "emailChangeSourceError",
					class: "email-change-error",
					role: "alert",
					hidden: !P(I)
				}, S(P(I)), 9, nr)
			]),
			t[7] ||= w("div", {
				id: "emailChangeNote",
				class: "email-change-note"
			}, "换绑、Recent Login 和验证码校验全部走协议任务，不会启动浏览器。成功写回后会自动创建一次协议查活任务刷新 AT。", -1),
			w("div", rr, [w("button", {
				id: "btnCancelEmailChange",
				type: "button",
				class: "jobs-tb-btn",
				onClick: t[2] ||= (e) => G()
			}, "取消"), w("button", {
				id: "btnSubmitEmailChange",
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				disabled: P(R)
			}, S(P(R) ? "提交中…" : "开始换绑"), 9, ir)])
		], 32)])], 10, qn)]));
	}
}), or = { class: "c2a-reimport-confirm-head" }, sr = ["disabled"], cr = { class: "c2a-reimport-confirm-body" }, lr = { class: "c2a-reimport-confirm-scope" }, ur = { id: "c2aReimportConfirmCountV2" }, dr = ["hidden"], fr = { class: "c2a-reimport-confirm-foot" }, pr = ["disabled"], mr = ["disabled"], hr = /* @__PURE__ */ n({
	__name: "C2aReimport",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, a = b(), o = !1, s = 0, c = 0, l;
		function u(e, t) {
			!o && e?.isConnected && typeof e.focus == "function" && (e.focus({ preventScroll: !0 }), l = requestAnimationFrame(() => {
				if (l = void 0, o || c !== t || d.isOpen.value) return;
				let n = e.closest("#accountsMoreActionsV2"), r = n?.open === !1 ? n.querySelector("summary") : e;
				r?.isConnected && r.focus({ preventScroll: !0 });
			}));
		}
		let d = Rn({
			...i.deps,
			beginBusy: (e, t) => {
				if (i.deps.beginBusy) return i.deps.beginBusy(e, t);
				let n = e instanceof HTMLButtonElement ? e : null, r = n?.textContent || "";
				return n && (n.disabled = !0, n.textContent = t), () => {
					n && (n.textContent = r, n.disabled = !1);
				};
			}
		}, { closed: (e, t) => {
			a.value?.open && (++s, a.value.close(t)), t !== "submitted" && u(e, c);
		} }), { isOpen: f, submitting: p, status: m, accountIds: h } = d;
		function g(e, n = null) {
			return !a.value || typeof a.value.showModal != "function" ? (i.deps.notify("C2A 同步确认窗口不可用，请刷新页面后重试"), !1) : d.open(e, n) ? (++c, l !== void 0 && (cancelAnimationFrame(l), l = void 0), t(() => {
				!o && f.value && !a.value?.open && a.value?.showModal();
			}), !0) : !1;
		}
		function _(e = "cancel", t = {}) {
			return d.close(e, t.force);
		}
		function v() {
			s ? --s : a.value?.open || d.close(a.value?.returnValue || "cancel", !0);
		}
		function y(e) {
			p.value && e.preventDefault();
		}
		return T(() => {
			o = !0, ++c, l !== void 0 && cancelAnimationFrame(l), d.close("cancel", !0);
		}), n({
			open: g,
			close: _,
			submit: d.submit,
			showResult: d.showResult,
			openTasks: d.openTasks,
			isSubmitting: p
		}), (e, t) => (r(), C(x, { to: "#accountC2aConfirmHost" }, [w("dialog", {
			ref_key: "dialog",
			ref: a,
			onClose: v,
			onCancel: y,
			id: "c2aReimportConfirmModal",
			"aria-labelledby": "c2aReimportConfirmTitle",
			"aria-describedby": "c2aReimportConfirmDescription"
		}, [
			w("div", or, [t[3] ||= w("div", null, [
				w("p", { class: "c2a-reimport-confirm-kicker" }, "本地 AT · 远端账号同步"),
				w("h3", { id: "c2aReimportConfirmTitle" }, "批量同步到 C2A"),
				w("p", { id: "c2aReimportConfirmDescription" }, "查到唯一的同邮箱 C2A 账号时覆盖 AT；未找到时新建账号。")
			], -1), w("button", {
				type: "button",
				class: "c2a-reimport-confirm-close",
				id: "btnCloseC2aReimportV2",
				disabled: P(p),
				onClick: t[0] ||= (e) => _(),
				"aria-label": "关闭 C2A 同步确认窗口"
			}, "×", 8, sr)]),
			w("div", cr, [
				w("p", lr, [
					t[4] ||= R("将为 ", -1),
					w("strong", ur, S(P(h).length), 1),
					t[5] ||= R(" 个已选账号创建同步任务。", -1)
				]),
				t[6] ||= w("section", {
					class: "c2a-reimport-confirm-note",
					"aria-labelledby": "c2aReimportConfirmScopeTitle"
				}, [w("h4", { id: "c2aReimportConfirmScopeTitle" }, "更新范围"), w("ul", null, [w("li", null, "任务执行时读取本地保存的当前 AT；不会刷新本地 AT，也不会重新登录。"), w("li", null, "按完整邮箱匹配 C2A 账号：唯一匹配时覆盖 AT，未找到时新建；同邮箱存在多条账号时不执行覆盖。")])], -1),
				t[7] ||= w("section", {
					class: "c2a-reimport-confirm-note",
					"aria-labelledby": "c2aReimportConfirmSafetyTitle"
				}, [w("h4", { id: "c2aReimportConfirmSafetyTitle" }, "提交安全条件"), w("p", null, "任务写入前会确认 C2A 的“自动移除异常账号”和“自动移除限流账号”都已关闭；无法确认或任一开关开启时，不会发送更新。执行期间请保持两个开关关闭。")], -1),
				t[8] ||= w("section", {
					class: "c2a-reimport-confirm-note c2a-reimport-confirm-note--warning",
					"aria-labelledby": "c2aReimportConfirmSideEffectTitle"
				}, [w("h4", { id: "c2aReimportConfirmSideEffectTitle" }, "C2A 端状态可能变化"), w("p", null, "当前 C2A 通用更新接口会按自身规则清除凭据错误。AT 更新确认后，异常账号可能恢复正常；最终以 C2A 状态和任务回执为准。")], -1),
				w("p", {
					class: "c2a-reimport-confirm-status",
					id: "c2aReimportConfirmStatusV2",
					role: "status",
					"aria-live": "polite",
					"aria-atomic": "true",
					hidden: !P(m)
				}, S(P(m)), 9, dr)
			]),
			w("div", fr, [w("button", {
				type: "button",
				class: "jobs-tb-btn",
				id: "btnCancelC2aReimportV2",
				disabled: P(p),
				onClick: t[1] ||= (e) => _()
			}, "取消", 8, pr), w("button", {
				type: "button",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				id: "btnConfirmC2aReimportV2",
				disabled: P(p),
				onClick: t[2] ||= (...e) => P(d).submit && P(d).submit(...e)
			}, S(P(p) ? "正在提交…" : "提交并入队"), 9, mr)])
		], 544)]));
	}
}), gr = ["hidden"], _r = { class: "column-filter-summary-label" }, vr = [
	"data-registration-retry-result",
	"data-registration-retry-task-id",
	"data-registration-retry-run-id",
	"onClick"
], yr = /* @__PURE__ */ n({
	__name: "RegistrationRetryReceipt",
	props: { notify: { type: Function } },
	setup(e, { expose: t }) {
		let n = e, i = j(null), a = b(0), o = !1;
		function c(e) {
			return Array.isArray(e) ? Object.freeze(e.map(c)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, c(t)]))) : e;
		}
		let l = k(() => Array.isArray(i.value?.result.started) ? i.value.result.started : []), u = k(() => Array.isArray(i.value?.result.reused) ? i.value.result.reused : []), d = k(() => Array.isArray(i.value?.result.skipped) ? i.value.result.skipped : []), f = k(() => [...l.value, ...u.value]), p = k(() => {
			let e = i.value?.result;
			return `注册重跑：已创建 ${Number(e?.started_count ?? l.value.length)} 个，进行中 ${Number(e?.reused_count ?? u.value.length)} 个，跳过 ${Number(e?.skipped_count ?? d.value.length)} 个`;
		}), m = (e) => e.operation_task_id || e.task_id, g = (e) => m(e) ? e.operation_run_id || e.run_id : void 0, _ = (e) => m(e) || e.job_id;
		function y(e, t, n) {
			o || (i.value = {
				result: c(e),
				context: c(t),
				open: n
			}, ++a.value);
		}
		async function E(e = f.value) {
			if (o || !i.value) return;
			let t = i.value.open;
			try {
				await t(c(e));
			} catch (e) {
				o || n.notify?.("注册重跑请求已处理，打开任务失败: " + (e instanceof Error ? e.message : "请求失败"));
			}
		}
		return T(() => {
			o = !0, i.value = null;
		}), t({
			showResult: y,
			openTasks: E
		}), (e, t) => (r(), C(x, { to: "#accountRegistrationReceiptHost" }, [w("div", {
			id: "accountRegistrationRetryResultV2",
			class: "column-filter-summary account-search-summary",
			role: "status",
			"aria-live": "polite",
			hidden: !i.value
		}, [
			w("span", _r, S(i.value ? p.value : ""), 1),
			f.value.length ? (r(), L("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-tasks": "",
				onClick: t[0] ||= (e) => E()
			}, "打开任务中心")) : h("", !0),
			f.value.length || d.value.length ? (r(), L("details", { key: a.value }, [w("summary", null, "查看" + S(d.value.length ? "任务及跳过原因" : "任务"), 1), w("ul", null, [(r(!0), L(v, null, s(f.value, (e, t) => (r(), L("li", { key: `task-${t}` }, [R("账号 #" + S(e.account_id) + " · " + S(t < l.value.length ? "已创建" : "进行中") + " ", 1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-result": t,
				"data-registration-retry-task-id": m(e) || void 0,
				"data-registration-retry-run-id": g(e) || void 0,
				onClick: (t) => E([e])
			}, "查看任务" + S(_(e) ? ` #${_(e)}` : ""), 9, vr)]))), 128)), (r(!0), L(v, null, s(d.value, (e, t) => (r(), L("li", { key: `skipped-${t}` }, "账号 #" + S(e.account_id) + " · " + S(e.reason || e.error || "当前不可重跑"), 1))), 128))])])) : h("", !0)
		], 8, gr)]));
	}
}), br = {
	key: 0,
	class: "ac-operation-receipts",
	open: ""
}, xr = { class: "ac-operation-receipt-list" }, Sr = { class: "ac-operation-receipt-row" }, Cr = { role: "status" }, wr = ["disabled", "onClick"], Tr = ["onClick"], Er = {
	key: 0,
	class: "ac-operation-receipt-row"
}, Dr = ["onClick"], Or = /*#__PURE__*/ F(/* @__PURE__ */ n({
	__name: "AccountOperationReceipts",
	props: { receipts: {} },
	setup(e) {
		let t = e, n = k(() => t.receipts.entries.value), i = new Intl.DateTimeFormat("zh-CN", {
			month: "numeric",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
			second: "2-digit"
		});
		return (t, a) => n.value.length ? (r(), L("details", br, [w("summary", null, S(n.value.length) + " 次提交需核对回执", 1), w("ul", xr, [(r(!0), L(v, null, s(n.value, (t) => (r(), L("li", { key: t.key }, [w("div", Sr, [
			w("strong", null, S(t.label) + " · " + S(t.count) + " 个账号 · " + S(P(i).format(t.submittedAt)), 1),
			w("span", Cr, S(t.message), 1),
			w("button", {
				class: "ac-button",
				type: "button",
				disabled: t.loading,
				onClick: (n) => e.receipts.lookup(t.key)
			}, S(t.loading ? "查询中…" : "查询回执"), 9, wr),
			w("button", {
				class: "ac-link",
				type: "button",
				onClick: (n) => e.receipts.dismiss(t.key)
			}, "移除此提示", 8, Tr)
		]), t.items.length ? (r(), L("div", Er, [(r(!0), L(v, null, s(t.items, (t) => (r(), L("button", {
			key: `${t.task_id}:${t.run_id}`,
			class: "ac-link",
			type: "button",
			onClick: (n) => e.receipts.open(t)
		}, [R(" 任务 #" + S(t.task_id), 1), t.run_id ? (r(), L(v, { key: 0 }, [R(" · 执行 #" + S(t.run_id), 1)], 64)) : h("", !0)], 8, Dr))), 128))])) : h("", !0)]))), 128))])])) : h("", !0);
	}
}), [["__scopeId", "data-v-216648e7"]]), kr = /* @__PURE__ */ n({
	__name: "AccountsPageShell",
	props: {
		adapter: {},
		api: {},
		presentation: {},
		callbacks: {},
		detailApi: {},
		detailPresentation: {},
		syncModalScrollLock: { type: Function },
		actions: {},
		inspectionDependencies: {},
		emailChangeDependencies: {},
		c2aDependencies: {},
		initialCapabilities: {}
	},
	setup(e, { expose: t }) {
		let n = e, a = b(), o = b(), s = b(), c = b(), l = b(), u = b(), d = b(), p = j(), m = j(n.initialCapabilities), g = b(0), _ = j({});
		function y() {
			if (!a.value) throw Error("账号列表正在加载，请稍后重试");
			return a.value;
		}
		let x = k(() => {
			g.value;
			let e = a.value?.getActionContext(), t = e ? Object.fromEntries(ge.map((t) => [t.action, n.actions.isPending(t.action, e)])) : {};
			return t.reimportSelectedC2a = l.value?.isSubmitting === !0, {
				selectedCount: p.value?.selectedIds.length || 0,
				archived: p.value?.archived === "only",
				pending: t,
				labels: _.value
			};
		});
		async function S(e, t, r = null) {
			let i = n.actions.isSupported(e) ? n.actions.invoke(e, t, r) : n.callbacks.invoke(e, t, r);
			++g.value;
			try {
				await i;
			} finally {
				++g.value;
			}
		}
		let w = {
			...n.callbacks,
			invoke: S,
			onStateChange: (e) => {
				p.value = e, n.callbacks.onStateChange?.(e);
			},
			openDetail: (e, t, n, r) => {
				o.value ? o.value.open(e, t, n, r) : n.release();
			},
			closeConsumers: (e = !0) => {
				o.value?.close(e), n.callbacks.closeConsumers?.(e);
			}
		}, E = {
			notify: (e) => n.callbacks.notify?.(e),
			syncModalScrollLock: () => n.syncModalScrollLock()
		};
		return T(() => n.actions.dispose()), t({
			setVisible: (e) => {
				n.actions.setVisible(e), y().setVisible(e);
			},
			setArchived: (e) => y().setArchived(e),
			refresh: () => y().refresh(),
			pollStatuses: () => y().pollStatuses(),
			getAccountSelectionSnapshot: (...e) => y().getAccountSelectionSnapshot(...e),
			getActionContext: (...e) => y().getActionContext(...e),
			getRowSnapshot: (e) => y().getRowSnapshot(e),
			openPlanDetailsConsumer: (e) => y().openPlanDetailsConsumer(e),
			removeAcknowledgedSelection: (e) => y().removeAcknowledgedSelection(e),
			clearSelection: () => y().clearSelection(),
			setPage: (e) => y().setPage(e),
			setSize: (e) => y().setSize(e),
			updateQuery: (...e) => y().updateQuery(...e),
			updateFilters: (...e) => y().updateFilters(...e),
			resetFilters: () => y().resetFilters(),
			resetColumns: () => y().resetColumns(),
			openDetail: (e, t = null) => y().openDetail(e, t),
			closeDetail: (e = !0) => o.value?.close(e),
			isActionSupported: (e) => n.actions.isSupported(e),
			isActionPending: (e) => n.actions.isPending(e, y().getActionContext()),
			invokeAction: S,
			syncToolbarPending: () => {
				++g.value;
			},
			setToolbarBusyLabel: (e, t) => {
				let n = { ..._.value };
				t ? n[e] = t : delete n[e], _.value = n;
			},
			closeMoreMenus: () => y().closeMoreMenus(),
			setCapabilities: (e) => {
				m.value = e;
			},
			refreshQuickActions: () => u.value?.refreshQuickActions(),
			showRegistrationResult: (e, t, n) => d.value?.showResult(e, t, n),
			openInspectionStart: (e, t = null) => s.value?.openStart(e, t),
			openInspectionHistory: (e = null) => s.value?.openHistory(e),
			openInspectionFailures: (e, t = null) => s.value?.openFailures(e, t),
			closeInspection: (e) => s.value?.close(e),
			refreshInspectionHistory: () => s.value?.refreshHistory(),
			refreshInspectionFailures: () => s.value?.refreshFailures(),
			changeInspectionPage: (e) => s.value?.changeHistoryPage(e),
			changeInspectionFailuresPage: (e) => s.value?.changeFailuresPage(e),
			stopInspection: (e) => s.value?.stop(e),
			openEmailChange: (e, t, n = null) => c.value?.openSingle(e, t, n),
			openBulkEmailChange: (e, t = null) => c.value?.openBulk(e, t),
			closeEmailChange: (e = {}) => c.value?.close(e),
			openC2a: (e, t = null) => l.value?.open(e, t),
			closeC2a: (e = "cancel", t = {}) => l.value?.close(e, t),
			submitC2a: () => l.value?.submit(),
			showC2aResult: (e) => l.value?.showResult(e),
			openC2aTasks: (e) => l.value?.openTasks(e)
		}), (t, n) => (r(), L(v, null, [
			f(Pt, {
				ref_key: "list",
				ref: a,
				adapter: e.adapter,
				api: e.api,
				presentation: e.presentation,
				callbacks: w
			}, {
				actions: i(() => [f(Te, {
					ref_key: "toolbar",
					ref: u,
					state: x.value,
					capabilities: m.value,
					"get-context": () => y().getActionContext(),
					invoke: S,
					notify: w.notify
				}, null, 8, [
					"state",
					"capabilities",
					"get-context",
					"notify"
				])]),
				feedback: i(() => [e.actions.receipts ? (r(), C(Or, {
					key: 0,
					receipts: e.actions.receipts
				}, null, 8, ["receipts"])) : h("", !0)]),
				_: 1
			}, 8, [
				"adapter",
				"api",
				"presentation"
			]),
			f(Wt, {
				ref_key: "drawer",
				ref: o,
				api: e.detailApi,
				presentation: e.detailPresentation,
				callbacks: E
			}, null, 8, ["api", "presentation"]),
			f(kn, {
				ref_key: "inspection",
				ref: s,
				deps: e.inspectionDependencies
			}, null, 8, ["deps"]),
			f(ar, {
				ref_key: "emailChange",
				ref: c,
				deps: e.emailChangeDependencies
			}, null, 8, ["deps"]),
			f(hr, {
				ref_key: "c2a",
				ref: l,
				deps: e.c2aDependencies
			}, null, 8, ["deps"]),
			f(yr, {
				ref_key: "registrationReceipt",
				ref: d,
				notify: w.notify
			}, null, 8, ["notify"])
		], 64));
	}
});
// src/api/accounts.ts
function Ar(e) {
	return typeof e == "object" && !!e && !Array.isArray(e);
}
function jr(e, t) {
	return typeof e == "number" && Number.isSafeInteger(e) && e >= t;
}
function Mr(e) {
	return Ar(e) && e.ok === !0 && Array.isArray(e.items) && jr(e.total, 0) && jr(e.page, 1) && jr(e.page_size, 1) && jr(e.offset, 0) && jr(e.limit, 1) && typeof e.revision == "string";
}
function Nr() {
	throw new le("账号查询返回了无效的响应，请刷新后重试。", 200, "account_response_invalid");
}
function Pr(e) {
	return {
		async list(t, n, r, i, a) {
			let o = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			});
			a?.includeFacets === !1 && o.set("include_facets", "0");
			let s = await ce(`/api/accounts?${o}`, { signal: i });
			return Mr(s) && s.compact === !0 && Ar(s.facets) && Array.isArray(s.search_terms) || Nr(), s;
		},
		async statuses(t, n, r, i) {
			let a = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			});
			a.set("compact", "1");
			let o = await ce(`/api/accounts/plan-check-status?${a}`, { signal: i });
			return Mr(o) && Ar(o.queue) && Array.isArray(o.status_fields) && o.status_fields.every((e) => typeof e == "string") || Nr(), o;
		},
		async planDetails(e, t) {
			if (!/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
			let n = await ce(`/api/accounts/${encodeURIComponent(e)}/plan-details`, { signal: t });
			return Ar(n) && n.ok === !0 && Ar(n.item) && Object.hasOwn(n.item, "account_promotions") && Object.hasOwn(n.item, "promotion_query_snapshot") && Array.isArray(n.item.plan_check_country_results) || Nr(), n;
		}
	};
}
// src/api/accountDetail.ts
function Fr() {
	return { async roxyProfile(e, t) {
		if (!/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
		let n = await ce(`/api/accounts/${encodeURIComponent(e)}/roxy-profile`, { signal: t });
		if (!n || typeof n != "object" || Array.isArray(n) || !("ok" in n) || n.ok !== !0 || !("profile_id" in n) || n.profile_id !== null && typeof n.profile_id != "string" || !("window_name" in n) || n.window_name !== null && typeof n.window_name != "string") throw new le("账号详情返回了无效的响应，请重新打开详情重试。", 200, "account_response_invalid");
		return {
			ok: !0,
			profile_id: n.profile_id,
			window_name: n.window_name
		};
	} };
}
// src/features/accounts/operationReceipts.ts
var Ir = "X-Account-Request-Key", Lr = "turb_account_operation_receipts", Rr = /^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/, zr = 1e4;
function Br() {
	try {
		let e = JSON.parse(sessionStorage.getItem(Lr) || "[]");
		return Array.isArray(e) ? e.filter((e) => e && typeof e == "object" && typeof e.key == "string" && Rr.test(e.key) && typeof e.label == "string" && Number.isSafeInteger(e.count) && e.count > 0 && Number.isSafeInteger(e.submittedAt) && e.submittedAt > 0) : [];
	} catch {
		return [];
	}
}
function Vr(e) {
	try {
		sessionStorage.setItem(Lr, JSON.stringify(e));
	} catch {}
}
function Hr(e) {
	return {
		...e,
		items: [],
		message: "受理结果未确认，可能已入队。",
		loading: !1
	};
}
function Ur(t, n) {
	let r = j(Br().map(Hr)), i = (e, t) => {
		r.value = r.value.map((n) => n.key === e ? {
			...n,
			...t
		} : n);
	};
	function a(e) {
		r.value = r.value.filter((t) => t.key !== e), Vr(Br().filter((t) => t.key !== e));
	}
	async function o(e, n, i) {
		let o = crypto.randomUUID?.() ?? Array.from(crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(16)), (e) => e.toString(16).padStart(2, "0")).join(""), s = {
			key: o,
			label: e,
			count: n,
			submittedAt: t.now().getTime()
		};
		Vr([s, ...Br()]);
		let c;
		try {
			let e = new Promise((e, t) => {
				c = setTimeout(() => t(/* @__PURE__ */ Error("等待受理超时")), zr);
			}), t = await Promise.race([i(o), e]);
			return a(o), t;
		} catch (n) {
			if (n instanceof le && (n.unavailableFeature || n.status >= 400 && n.status < 500 && n.status !== 408)) throw a(o), n;
			r.value = [Hr(s), ...r.value];
			let i = n instanceof le ? `。${n.message}` : "";
			t.notify(`${e}受理结果未确认，可在账号页查询回执${i}`);
			return;
		} finally {
			clearTimeout(c);
		}
	}
	async function s(e) {
		let n = r.value.find((t) => t.key === e);
		if (n && !n.loading) {
			i(e, { loading: !0 });
			try {
				let n = await t.request("/api/accounts/operation-receipt", {
					method: "GET",
					cache: "no-store",
					headers: { [Ir]: e }
				});
				if (n?.ok !== !0 || typeof n.found != "boolean" || !Array.isArray(n.items) || n.found !== n.items.length > 0) throw Error("回执格式无效");
				let r = n.items.map((e) => ({
					task_id: ue(e.task_id),
					run_id: de(e.run_id)
				}));
				i(e, {
					items: r,
					message: r.length ? `当前查到 ${r.length} 条任务回执` : "暂未查到任务回执，原请求可能仍在处理中。"
				});
			} catch (t) {
				i(e, { message: `回执查询失败：${t instanceof Error ? t.message : "请稍后再查"}` });
			} finally {
				i(e, { loading: !1 });
			}
		}
	}
	async function c(e) {
		try {
			await n(e.task_id, e.run_id);
		} catch (e) {
			t.notify(`打开任务失败：${e instanceof Error ? e.message : "请稍后重试"}`);
		}
	}
	return {
		submit: o,
		view: {
			entries: e(r),
			lookup: s,
			open: c,
			dismiss: a
		}
	};
}
// src/features/accounts/queuedActions.ts
var Wr = {
	"plan-check": {
		kind: "plan",
		single: !0,
		error: ""
	},
	checkSelectedPlans: {
		kind: "plan",
		single: !1,
		error: "批量查询失败: "
	},
	"account-live-check": {
		kind: "live",
		single: !0,
		error: "查活失败: "
	},
	checkSelectedLive: {
		kind: "live",
		single: !1,
		error: "查活失败: "
	},
	"account-refresh-token": {
		kind: "token",
		single: !0,
		error: "刷新AT失败: "
	},
	refreshSelectedToken: {
		kind: "token",
		single: !1,
		error: "刷新AT失败: "
	},
	"deactivation-mail-check": {
		kind: "mail",
		single: !0,
		error: "扫描失败: "
	},
	checkSelectedDeactivationMail: {
		kind: "mail",
		single: !1,
		error: "批量扫描失败: "
	},
	"extract-link": {
		kind: "extract",
		single: !0,
		error: "提链失败: "
	},
	extractSelectedLinks: {
		kind: "extract",
		single: !1,
		error: "批量提链失败: "
	}
}, Gr = {
	plan: "plan_check",
	live: "live_check",
	token: "token_refresh",
	mail: "deactivation_mail",
	extract: "extract_link"
}, Kr = {
	plan: "查套餐",
	live: "查活",
	token: "刷新 AT",
	mail: "封号邮件扫描"
}, qr = (e) => Object.prototype.hasOwnProperty.call(Wr, e), Jr = (e) => e instanceof Error ? e.message : "请求失败，请稍后重试。";
function Yr(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Xr(e) {
	if (e == null) return [];
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return e.map((e) => {
		if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
		return e;
	});
}
function Q(e) {
	let t = Number(e || 0);
	if (!Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function Zr(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return [...new Set(e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	}))];
}
function Qr(e) {
	return Array.isArray(e) ? Object.freeze(e.map(Qr)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, Qr(t)]))) : e;
}
function $r(e, t) {
	return Qr({
		accountIds: t.map(String),
		expectedEmails: { ...e.expectedEmails },
		querySnapshot: e.querySnapshot,
		archived: e.archived,
		rowHints: []
	});
}
function ei(e) {
	let t = [...Xr(e.skipped), ...Xr(e.failed)].map((e) => String(e.reason || e.error || "").replace(/\s+/g, " ").trim()).filter(Boolean);
	return t.length ? `；${t.slice(0, 3).map((e) => e.length > 80 ? `${e.slice(0, 80)}…` : e).join("；")}${t.length > 3 ? `；另有 ${t.length - 3} 条原因` : ""}` : "";
}
function ti(e, t) {
	let n = e.rowHints.find((e) => String(e.id) === String(t));
	return String(n?.email || e.expectedEmails[String(t)] || "").trim() || String(t);
}
function ni(e) {
	return Array.isArray(e) ? e.length : 0;
}
function ri(e, t) {
	let n = ni(e.started) + ni(e.queued) + ni(e.reused), r = Q(e.started_count) + Q(e.queued_count) + Q(e.reused_count);
	return n > 0 || r > 0 || t && (e.accepted === !0 || e.started === !0);
}
function ii(e) {
	let t = Array.isArray(e) ? e.filter((e) => e && typeof e == "object") : [], n = (e) => t.find((t) => t.key === e), r = n("ACCOUNT_AT_REFRESH_DRIVER"), i = String(r?.value || "protocol").trim().toLowerCase(), a = i === "browser_roxy" ? "browser_roxy" : [
		"rust",
		"sentinel_rs",
		"sentinel-rs"
	].includes(i) ? "rust" : "protocol", o = n("ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED")?.value, s = o === !0 || String(o).trim().toLowerCase() === "true", c = String(n("OPENAI_PROTOCOL_VERSION")?.value || "v1").trim().toLowerCase(), l = ["v2", "v3"].includes(c) ? c : "v1", u = r ? a === "browser_roxy" ? "Roxy 指纹浏览器" : a === "rust" ? "Rust sentinel-rs" : `协议刷新（${l}）` : "已保存的刷新驱动";
	return {
		description: a === "protocol" && l === "v3" || a === "rust" ? `使用${u}先复用该账号有效的登录会话；会话失效或尚未保存时，按实际挑战完成密码、2FA 或邮箱验证，核对账号身份并保存最新 accessToken。` : `使用${u}重新登录，按实际挑战完成密码、2FA 或邮箱验证，并保存最新 accessToken。`,
		debugDescription: s ? "Roxy 刷新调试已开启：实际使用 Roxy 时将显示浏览器并全程抓包；失败保留窗口，可从任务日志查看现场并下载 HAR。" : ""
	};
}
function ai(e) {
	let t = String(e.plus_promo_kind || "").trim().toLowerCase();
	if ([
		"free_trial",
		"discount",
		"other_promo",
		"none",
		"unknown"
	].includes(t)) return t;
	let n = e.plus_promo_discount_percentage ?? e.plus_trial_discount_percentage, r = n == null || n === "" ? NaN : Number(n), i = String(e.plus_promo_campaign_id || e.plus_trial_campaign_id || "").trim().toLowerCase(), a = [
		i,
		e.plus_promo_title || e.plus_trial_title,
		e.plus_promo_promotion_type,
		e.plus_promo_promotion_type_label || e.plus_trial_promotion_type_label
	].join(" ").toLowerCase();
	return r === 100 ? "free_trial" : Number.isFinite(r) && r > 0 && r < 100 || a.includes("pct-off") || a.includes("discount") || a.includes("% off") ? "discount" : a.includes("free trial") || i.includes("-free") || i.includes("trial") ? "free_trial" : a.trim() ? "other_promo" : e.plus_discount_eligible === !0 ? "discount" : e.plus_promo_eligible === !0 || e.plus_trial_eligible === !0 ? "unknown" : "none";
}
function oi(e, t) {
	let n = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), i = Ur(e, t.openReceiptTask ?? t.openAccountTaskLog), a, o = !0, s = !1, c = 0, l = (e, t) => Wr[e]?.single ? JSON.stringify([e, ...t.map(String)]) : e, u = (e) => !s && o && e === c && t.isOwnerActive();
	function d() {
		++c;
		for (let e of [...r]) e();
	}
	function f(n) {
		return u(n) ? new Promise((i) => {
			let a, o = () => {
				t.clearScheduled(a), r.delete(o), i(!1);
			};
			r.add(o), a = e.schedule(() => {
				r.delete(o), i(u(n));
			}, 1500);
		}) : Promise.resolve(!1);
	}
	async function p(e, n, r) {
		let i = {
			ids: e,
			attempts: 0
		};
		if (a?.generation === r) {
			e.length && a.targets.add(i);
			return;
		}
		let o = {
			generation: r,
			targets: new Set(e.length ? [i] : [])
		};
		a = o;
		try {
			for (await t.refresh(n); o.targets.size && await f(r);) {
				let e = [...o.targets];
				if (await t.refresh(n), !u(r)) return;
				for (let n of e) {
					let e = n.ids.map((e) => t.getRowSnapshot(String(e))).filter((e) => e != null), r = e.length > 0 && e.every((e) => !["queued", "running"].includes(String(e.deactivation_mail_scan_status || "")));
					(++n.attempts >= 30 || r) && o.targets.delete(n);
				}
			}
		} finally {
			a === o && (a = void 0);
		}
	}
	async function m(t, n = () => !0) {
		try {
			n() && await t();
		} catch (t) {
			n() && e.notify(`请求已处理，但页面更新失败: ${Jr(t)}`);
		}
	}
	async function h(r, a, d = null) {
		if (!qr(r)) throw Error(`未支持的账号动作：${r}`);
		if (s || !o || e.canInvoke?.(r, d) === !1) return;
		let f = Wr[r], h, g, _ = c, v = () => u(_);
		try {
			let o = Zr(a);
			if (!o.length) {
				e.notify("请先选择账号");
				return;
			}
			if (f.single && o.length !== 1) throw Error("此操作只能选择一个账号");
			let s = o.length === 1 ? ti(a, o[0]) : "";
			if (h = l(r, o), n.has(h)) {
				h = void 0;
				return;
			}
			n.add(h);
			let c = $r(a, o), u = (t) => {
				g = e.beginBusy?.(r, d, t) || void 0;
			}, y = async (t, n, r) => {
				let i = {}, a = { method: "POST" };
				r && (i[Ir] = r), n !== void 0 && (i["Content-Type"] = "application/json", a.body = JSON.stringify(n)), (r || n !== void 0) && (a.headers = i);
				let o = Yr(await e.request(t, a));
				if (r && o.ok !== !0) throw Error("服务端响应格式无效");
				return o;
			}, b = (e, t, n) => i.submit(Kr[e], o.length, (e) => y(t, n, e));
			if (f.kind === "plan") {
				u("查询中…");
				let n;
				try {
					n = await b("plan", f.single ? "/api/accounts/check-plan" : "/api/accounts/check-plan-bulk", f.single ? { account_id: o[0] } : { account_ids: o });
				} catch (n) {
					e.notify(f.error + Jr(n)), f.single && v() && t.pollStatuses(c).catch((t) => {
						v() && e.notify(`套餐状态读取失败: ${Jr(t)}`);
					});
					return;
				}
				if (!n) return;
				e.notify(f.single ? String(n.message || "套餐查询已加入后台队列") : `已入队 ${Q(n.started_count)} 个，查询中跳过 ${Q(n.busy_count)} 个，入队失败 ${Q(n.failed_count)} 个${Xr(n.skipped).length ? `，跳过 ${Xr(n.skipped).length} 个` : ""}${ei(n)}`), ri(n, f.single) && m(() => jn({
					openTasks: t.openTasks,
					openTask: t.openAccountTaskLog
				}, {
					single: f.single,
					type: Gr[f.kind],
					target: s || void 0,
					result: n
				}), v), m(() => t.pollStatuses(c), v);
			} else if (f.kind === "live") {
				let n = t.operationWorkers(), r = f.single ? "确定查活这个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。" : `确定查活选中的 ${o.length} 个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。\n\n并发线程数：${n}`;
				if (!await e.confirm(r)) return;
				u("查活中…");
				let i = await b("live", "/api/accounts/check-live-bulk", {
					account_ids: o,
					driver: t.configuredLiveCheckDriver()
				});
				if (!i) return;
				let a = Xr(i.skipped).length;
				e.notify(`查活已入队 ${Q(i.started_count)} 个，忙碌 ${Q(i.busy_count)} 个，失败 ${Q(i.failed_count)}${a ? `，跳过 ${a}` : ""}（配置驱动：${t.configuredLiveCheckDriver() || "默认"}，实际驱动：${i.live_check_driver || "未知"}）${ei(i)}`), ri(i, f.single) && m(() => jn({
					openTasks: t.openTasks,
					openTask: t.openAccountTaskLog
				}, {
					single: f.single,
					type: Gr[f.kind],
					target: s || void 0,
					result: i
				}), v), m(() => t.refresh(c), v), m(() => t.refreshSummary(), v);
			} else if (f.kind === "token") {
				let n = t.operationWorkers(), i = t.fallbackConfig(), a = Array.isArray(i) && i.some((e) => e?.key === "ACCOUNT_AT_REFRESH_DRIVER");
				if (u(a ? "刷新 AT…" : "读取配置…"), !a) try {
					i = await t.readConfig();
				} catch {
					i = t.fallbackConfig();
				}
				let l = ii(i), p = o.length === 1 ? "这个账号" : `选中的 ${o.length} 个账号`;
				if (!await e.confirm(`确定刷新${p}的 AT 吗？\n\n${l.description}${l.debugDescription ? `\n\n${l.debugDescription}` : ""}${o.length > 1 ? `\n\n并发线程数：${n}` : ""}`)) return;
				t.updateBusyLabel?.(r, d, "刷新中…");
				let h = await b("token", "/api/accounts/refresh-token-bulk", { account_ids: o });
				if (!h) return;
				let g = Xr(h.skipped).length;
				e.notify(`刷新AT已入队 ${Q(h.started_count)} 个，忙碌 ${Q(h.busy_count)} 个，失败 ${Q(h.failed_count)}${g ? `，跳过 ${g}` : ""}${ei(h)}`), ri(h, f.single) && m(() => jn({
					openTasks: t.openTasks,
					openTask: t.openAccountTaskLog
				}, {
					single: f.single,
					type: Gr[f.kind],
					target: s || void 0,
					result: h
				}), v), m(() => t.refresh(c), v), m(() => t.refreshSummary(), v);
			} else if (f.kind === "mail") {
				u("扫描中…");
				let n = await b("mail", f.single ? `/api/accounts/${o[0]}/check-deactivation-mail` : "/api/accounts/check-deactivation-mail-bulk", f.single ? void 0 : { account_ids: o });
				if (!n) return;
				e.notify(f.single ? "封号邮件扫描已入队；不会刷新 AT" : `已入队 ${Q(n.started_count)} 个，跳过 ${Q(n.skipped_count)} 个；不会刷新 AT${ei(n)}`), ri(n, f.single) && m(() => jn({
					openTasks: t.openTasks,
					openTask: t.openAccountTaskLog
				}, {
					single: f.single,
					type: Gr[f.kind],
					target: s || void 0,
					result: n
				}), v), m(() => p(f.single || Q(n.started_count) > 0 ? o : [], c, _), v);
			} else if (f.kind === "extract") {
				if (f.single) {
					let t = a.rowHints.find((e) => String(e.id) === String(o[0]));
					if (!t) {
						e.notify("账号不存在");
						return;
					}
					if (String(t.current_plan_type || t.plan_type || "").toLowerCase() !== "free" || ai(t) !== "free_trial") {
						e.notify("仅支持已确认 Plus 免费试用资格的 free 账号提链；折扣优惠不支持");
						return;
					}
					if (!await e.confirm(`确定为该账号提链吗？\n\n${t.email || "#" + o[0]}\n\n提链类型按配置使用，成功会消耗 1 次 CDK。`)) return;
				} else if (!await e.confirm(`确定为选中的 ${o.length} 个账号批量提链吗？\n\n仅处理已确认的 Plus 免费试用账号，折扣优惠和历史待复查账号会自动跳过。成功会按账号消耗 CDK 次数。`)) return;
				u("提链中…");
				let n = await y(f.single ? "/api/accounts/extract-link" : "/api/accounts/extract-link-bulk", f.single ? { account_id: o[0] } : { account_ids: o });
				if (f.single) {
					let t = n.fallback_from && n.link_type ? `；${String(n.fallback_from).toUpperCase()} 已失败，改用 ${String(n.link_type).toUpperCase()}` : "";
					e.notify(`提炼任务已入队${n.task_id ? ` · 任务 #${n.task_id}` : ""}${t}，可在任务中心查看日志`);
				} else {
					let t = Q(n.skipped_count) + Q(n.busy_count) + Q(n.failed_count), r = Xr(n.started).filter((e) => e.fallback_from).length;
					e.notify(`已入队 ${Q(n.started_count)} 个${t ? `，跳过/失败 ${t} 个` : ""}${r ? `，其中 ${r} 个已自动跳过失败类型` : ""}${ei(n)}`);
				}
				ri(n, f.single) && m(() => jn({
					openTasks: t.openTasks,
					openTask: t.openAccountTaskLog
				}, {
					single: f.single,
					type: Gr[f.kind],
					target: s || void 0,
					result: n
				}), v), await m(async () => {
					await t.reloadTasks(), await t.pollStatuses(c);
				});
			}
		} catch (t) {
			e.notify(f.error + Jr(t));
		} finally {
			h && n.delete(h), g?.();
		}
	}
	return {
		isSupported: qr,
		invoke: h,
		receipts: i.view,
		isPending: (e, t) => n.has(l(e, t.accountIds)),
		setVisible(e) {
			o = e, e || d();
		},
		dispose() {
			s = !0, d();
		}
	};
}
// src/features/accounts/setupActions.ts
var si = {
	password: {
		label: "补密码",
		type: "password_setup"
	},
	twofa: {
		label: "补 2FA",
		type: "twofa_setup"
	},
	password_change: {
		label: "修改密码",
		type: "password_change"
	},
	twofa_change: {
		label: "修改 2FA",
		type: "twofa_change"
	},
	complete: {
		label: "补全账号",
		type: "account_completion"
	}
}, ci = {
	addPasswordSelectedAccounts: "password",
	addTwofaSelectedAccounts: "twofa",
	changePasswordSelectedAccounts: "password_change",
	changeTwofaSelectedAccounts: "twofa_change",
	completeSelectedAccounts: "complete"
}, li = /* @__PURE__ */ new Set([
	"account-setup",
	"setupSelectedAccounts",
	"codex-stop",
	"codex-reset-retrying",
	"codex-retry",
	"stopSelectedCodex",
	"retrySelectedCodex",
	"uploadSelectedCodexSub2",
	"account-registration-retry",
	"retryAccountRegistration"
]), ui = (e, t) => Object.prototype.hasOwnProperty.call(e, t);
function di(e) {
	let t = e.indexOf(":");
	return t < 0 ? {
		name: e,
		value: ""
	} : {
		name: e.slice(0, t),
		value: e.slice(t + 1)
	};
}
function fi(e) {
	let { name: t, value: n } = di(e);
	return t === "account-action" ? ui(si, n) : t === "account-registration-task" ? /^[1-9]\d*$/.test(n) : !e.includes(":") && (li.has(t) || ui(ci, t));
}
function pi(e, t = !1) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let n = e;
	if (t && n.ok === !1) throw Error(typeof n.error == "string" ? n.error : "请求失败");
	return n;
}
function mi(e) {
	if (e == null) return [];
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return e.map((e) => pi(e));
}
function $(e) {
	let t = Number(e || 0);
	if (!Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function hi(e) {
	return Array.isArray(e) ? Object.freeze(e.map(hi)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, hi(t)]))) : e;
}
function gi(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return hi({
		accountIds: [...new Set(e.accountIds.map((e) => {
			if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
			return e;
		}))],
		expectedEmails: e.expectedEmails,
		querySnapshot: e.querySnapshot,
		archived: e.archived,
		rowHints: e.rowHints
	});
}
function _i(e) {
	let t = mi(e.started), n = mi(e.reused), r = mi(e.skipped);
	return hi({
		started: t,
		reused: n,
		skipped: r,
		started_count: $(e.started_count ?? t.length),
		reused_count: $(e.reused_count ?? n.length),
		skipped_count: $(e.skipped_count ?? r.length)
	});
}
function vi(e) {
	return `注册重跑：已创建 ${e.started_count} 个，进行中 ${e.reused_count} 个，跳过 ${e.skipped_count} 个`;
}
var yi = {
	registration: "registration",
	registration_resume: "registration_resume",
	codex: "codex_retry",
	twofa: "account_setup_retry",
	plan_check: "plan_check"
};
function bi(e) {
	return e && typeof e == "object" && !Array.isArray(e) ? e : null;
}
function xi(e) {
	return ["skipped", "failed"].some((t) => Array.isArray(e[t]) && e[t].length > 0 || Number(e[`${t}_count`] || 0) > 0) ? In(e) : "";
}
function Si(e, t = [
	"started",
	"queued",
	"reused"
], n = !1) {
	let r = bi(e);
	return r ? An(e) ? !0 : t.some((e) => Array.isArray(r[e]) && r[e].length > 0) || t.some((e) => Number(r[`${e}_count`] || 0) > 0) || r.accepted === !0 && n : !1;
}
function Ci(e) {
	let t = bi(e);
	if (!t) return [];
	let n = [t.retry_action, ...["started", "reused"].flatMap((e) => Array.isArray(t[e]) ? t[e].map((e) => bi(e)?.retry_action) : [])];
	return [...new Set(n.filter((e) => typeof e == "string" && e in yi).map((e) => yi[e]))];
}
function wi(e, t, n) {
	let r = bi(e);
	if (!n) return r?.registration_resume ? "registration_resume" : t;
	let i = Array.isArray(r?.started) ? r.started : [], a = /* @__PURE__ */ new Set();
	return i.length ? (i.some((e) => bi(e)?.registration_resume) && a.add("registration_resume"), i.some((e) => !bi(e)?.registration_resume) && a.add(t)) : Number(r?.started_count || 0) > 0 && a.add(t), [...a].join(",");
}
var Ti = (e) => e instanceof Error ? e.message : "请求失败，请稍后重试。", Ei = (e) => e === "account-registration-retry" || e === "retryAccountRegistration", Di = (e) => e.startsWith("account-") || e.startsWith("codex-");
function Oi(e, t) {
	let n = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), i = (e, t) => Di(di(e).name) ? JSON.stringify([e, ...t]) : e;
	async function a(e, n) {
		let r = e.length === 1 ? e[0] : void 0, i = r && n.rowHints.find((e) => String(e.id) === String(r.account_id)), a = An(r);
		await t.openTasks({
			filters: { target: r?.email || i?.email || (r ? n.expectedEmails[String(r.account_id)] || String(r.account_id ?? "") : "") || "" },
			taskId: a?.taskId,
			runId: a?.runId ?? null
		}), !a && r?.job_id && await t.openLog(ue(r.job_id));
	}
	async function o(t) {
		try {
			await t();
		} catch (t) {
			e.notify(`请求已处理，但页面更新失败: ${Ti(t)}`);
		}
	}
	function s(e, n) {
		n && Si(n.result, n.type === "sub2api_manual_upload" ? ["queued"] : void 0, n.single) && o(() => jn(t, n)), o(() => t.refresh(e));
	}
	async function c(c, l, u = null) {
		if (!fi(c)) throw Error(`未支持的账号动作：${di(c).name}`);
		if (e.canInvoke?.(c, u) === !1) return;
		let { name: d, value: f } = di(c), p = d === "account-action" ? f : ui(ci, d) ? ci[d] : void 0, m = p ? si[p] : void 0, h, g, _ = [], v = !1, y = m ? `${m.label}失败: ` : d.includes("setup") || d === "setupSelectedAccounts" ? "补齐账号配置失败: " : d === "codex-stop" ? "停止失败: " : d === "codex-reset-retrying" ? "重置失败: " : d === "codex-retry" ? "触发补跑失败: " : d === "stopSelectedCodex" ? "停止选中补跑失败: " : d === "retrySelectedCodex" ? "批量补跑失败: " : d === "uploadSelectedCodexSub2" ? "批量上传 sub2 失败: " : "注册重跑提交失败: ";
		try {
			let y = gi(l), b = y.accountIds.map(Number), x = b[0];
			if (!b.length) {
				e.notify("请先选择账号");
				return;
			}
			if (Di(d) && b.length !== 1) throw Error("此操作只能选择一个账号");
			let S = y.rowHints.find((e) => String(e.id) === String(x)), C = y.expectedEmails[String(x)] || S?.email || "", w = S?.email || C || `账号 #${x}`;
			if (d === "account-registration-task") {
				await a([{
					account_id: x,
					email: C,
					job_id: ue(f)
				}], y);
				return;
			}
			if (Ei(d) && y.accountIds.some((e) => r.has(e))) {
				e.notify("所选账号的注册重跑正在提交，请稍后查看结果");
				return;
			}
			if (h = i(c, y.accountIds), n.has(h)) {
				h = void 0;
				return;
			}
			if (n.add(h), Ei(d) && (_ = y.accountIds, _.forEach((e) => r.add(e))), p && !Di(d) && ["password_change", "twofa_change"].includes(p) && b.length > 20) {
				e.notify("修改密码或修改 2FA 单次最多操作 20 个账号");
				return;
			}
			let T;
			if (T = d === "account-setup" ? `补齐账号配置？\n\n${w}\n\n只执行账号密码、套餐查询和 Authenticator 2FA，不执行 Codex 授权。` : d === "setupSelectedAccounts" ? `确定补齐选中的 ${b.length} 个账号配置吗？\n\n只执行：账号密码、套餐查询、Authenticator 2FA。\n不会执行 Codex 授权。` : m ? Di(d) ? `${m.label}？\n\n${w}` : `确定${m.label}选中的 ${b.length} 个账号吗？` : d === "codex-stop" ? `确定停止该账号的 Codex 补跑吗？\n\n${C}\n\n会发送停止信号并将状态标记为“已停止”。` : d === "codex-reset-retrying" ? `确定重置该账号的 Codex「补跑中」状态吗？\n\n${C}\n\n重置后状态会变为“失败”，可再次点击“补跑 Codex”。` : d === "codex-retry" ? `重新跑 Codex 授权？\n\n${C}\n\n按实际验证要求使用邮箱 OTP（自动收）。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑会在后台进行，完成后状态自动更新。` : d === "stopSelectedCodex" ? `确定停止选中的 ${b.length} 个账号的 Codex 补跑吗？\n\n会向正在补跑的任务发送停止信号，并将状态标记为“已停止”；未在补跑的账号会自动跳过。` : d === "retrySelectedCodex" ? `批量补跑选中的 ${b.length} 个账号 Codex 授权？\n\n并发线程数：${t.operationWorkers()}\n\n按实际验证要求使用邮箱 OTP。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑中和已废号账号会自动跳过。` : d === "uploadSelectedCodexSub2" ? `确定上传选中的 ${b.length} 个账号的 Codex OAuth 凭证到 sub2api 吗？\n\n未完成 Codex OAuth 的账号会自动跳过。` : `确定为${b.length === 1 ? `账号 #${x}` : `选中的 ${b.length} 个账号`}${b.length === 1 && S?.registration_retry?.label || "重跑原注册任务"}吗？\n\n复用原注册记录，按当前进度重跑或补齐缺失步骤。正在执行、已完成或没有原任务的账号会显示对应结果。`, !await e.confirm(T)) return;
			g = e.beginBusy?.(c, u, Ei(d) ? "提交中…" : d === "uploadSelectedCodexSub2" ? "提交上传…" : void 0) || void 0;
			let E = async (t, n) => {
				let r = pi(await e.request(t, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(n)
				}), !0);
				return v = !0, r;
			};
			if (d === "account-setup" || d === "setupSelectedAccounts") {
				let t = d === "account-setup", n = await E(t ? `/api/accounts/${x}/setup` : "/api/accounts/setup-bulk", t ? {} : { account_ids: b }), r = mi(n.skipped).length;
				e.notify(t ? String(n.message || "已开始补齐账号配置") : (r ? `已开始补齐 ${$(n.started_count)} 个，跳过 ${r} 个` : `已开始补齐 ${$(n.started_count)} 个账号配置`) + xi(n)), s(y, {
					single: t,
					target: t ? w : "",
					type: "account_setup_retry",
					result: n
				});
			} else if (p && m) {
				let t = d === "account-action", n = await E(t ? `/api/accounts/${x}/action` : "/api/accounts/action-bulk", t ? { action: p } : {
					account_ids: b,
					action: p
				}), r = mi(n.skipped).length;
				e.notify(t ? String(n.message || `${m.label}已入队`) : (r ? `已开始 ${$(n.started_count)} 个，跳过 ${r} 个` : String(n.message || `${m.label}已入队`)) + xi(n));
				let i = wi(n, m.type, !t);
				s(y, i ? {
					single: t,
					target: t ? w : "",
					type: i,
					result: n
				} : void 0);
			} else if (d.startsWith("codex-")) {
				let t = await E(`/api/codex/${d === "codex-stop" ? "stop" : d === "codex-reset-retrying" ? "reset-retrying" : "retry"}`, d === "codex-reset-retrying" ? {
					email: C,
					status: "failed"
				} : { email: C });
				e.notify(String(t.message || (d === "codex-stop" ? "已发送停止信号" : d === "codex-reset-retrying" ? "已重置补跑状态" : "已开始补跑"))), s(y, d === "codex-retry" ? {
					single: !0,
					target: C,
					type: "codex_retry",
					result: t
				} : void 0);
			} else if (d === "stopSelectedCodex" || d === "retrySelectedCodex") {
				let t = d === "stopSelectedCodex", n = await E(`/api/codex/${t ? "stop" : "retry"}-bulk`, { account_ids: b }), r = mi(n.skipped).length;
				e.notify(t ? `已停止 ${$(n.stopped_count)} 个${r ? `，跳过 ${r} 个` : ""}` : (r ? `已开始 ${$(n.started_count)} 个，跳过 ${r} 个` : String(n.message || "已开始批量补跑")) + xi(n)), s(y, t ? void 0 : {
					single: !1,
					target: "",
					type: "codex_retry",
					result: n
				});
			} else if (d === "uploadSelectedCodexSub2") {
				let n = await E("/api/accounts/codex/upload-sub2-bulk", { account_ids: b }), r = $(n.skipped_count ?? mi(n.skipped).length) + $(n.failed_count ?? mi(n.failed).length), i = r ? In(n) : "";
				n.accepted ? (e.notify(`手动上传已入队 ${$(n.queued_count ?? mi(n.queued).length)} 个，未入队 ${r} 个，请在任务中心查看结果${i}`), s(y, {
					single: !1,
					type: "sub2api_manual_upload",
					result: n
				})) : (e.notify(`已上传 ${$(n.uploaded_count)} 个${r ? `，跳过/失败 ${r} 个${i}` : ""}`), await o(() => t.pollStatuses(y)));
			} else if (Ei(d)) {
				let n = await E(b.length === 1 ? `/api/accounts/${x}/registration-retry` : "/api/accounts/registration-retry-bulk", b.length === 1 ? {} : { account_ids: b }), r = _i(n), i = Di(d);
				if (e.notify(vi(r) + (i ? "" : xi(n))), i && t.showRegistrationResult(r, y, (e) => a(e, y)), i) {
					if ((r.started[0] || r.reused[0]) && Si(r)) {
						let e = Ci(n)[0] || "registration";
						await o(() => jn(t, {
							single: !0,
							target: C,
							type: e,
							result: n
						}));
					}
				} else {
					let e = Ci(n);
					e.length && Si(r) ? await o(() => jn(t, {
						single: !1,
						type: e.join(","),
						result: n
					})) : Si(r) && await o(() => jn(t, {
						single: !1,
						type: "registration",
						result: n
					}));
				}
				await t.refresh(y);
			}
		} catch (t) {
			v && (y = Ei(d) ? "注册重跑请求已处理，页面更新失败: " : "请求已处理，但页面更新失败: "), e.notify(y + Ti(t));
		} finally {
			h && n.delete(h), _.forEach((e) => r.delete(e)), g?.();
		}
	}
	return {
		isSupported: fi,
		invoke: c,
		isPending: (e, t) => Ei(di(e).name) ? t.accountIds.some((e) => r.has(e)) : n.has(i(e, t.accountIds))
	};
}
// src/features/accounts/localMutations.ts
var ki = (e) => e === "only" ? "已归档账号" : e === "all" ? "全部账号" : "未归档账号", Ai = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败，请稍后重试。";
function ji(e) {
	let t = e.indexOf(":");
	return {
		name: t < 0 ? e : e.slice(0, t),
		value: t < 0 ? void 0 : e.slice(t + 1)
	};
}
function Mi(e) {
	let { name: t, value: n } = ji(e);
	return ["account-archive", "account-email-invalid"].includes(t) ? n === "0" || n === "1" : t === "setAccountsEmailInvalid" ? n === void 0 || n === "0" || n === "1" : n === void 0 && [
		"account-delete",
		"account-restore",
		"archiveSelectedAccounts",
		"deleteSelectedAccounts",
		"deleteDeactivatedAccounts"
	].includes(t);
}
function Ni(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Pi(e) {
	let t = Number(e);
	if (e == null || e === "" || typeof e == "boolean" || !Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function Fi(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return [...new Set(e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
		return Number.isSafeInteger(Number(e)) ? Number(e) : e;
	}))];
}
function Ii(e, t) {
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	let n = new Set(t.map(String));
	return [...new Set(e.map((e) => Ni(e).id).filter((e) => (typeof e == "number" && Number.isSafeInteger(e) || typeof e == "string") && n.has(String(e))).map(String))];
}
function Li(e) {
	let t = /* @__PURE__ */ new Set(), n = (e, t) => e.startsWith("account-") ? JSON.stringify([e, ...t.accountIds]) : ji(e).name;
	async function r(t, n, r = !1) {
		if ([
			"/api/accounts/archive-bulk",
			"/api/accounts/delete-bulk",
			"/api/accounts/note-bulk",
			"/api/accounts/email-invalid-bulk"
		].includes(t)) {
			let r = await fe(e.request, t, n, { onAccepted: (t) => e.notify(`批量命令已受理，正在执行（命令 ${t.command_id}）`) });
			return Ni(pe(r, "accounts", t.endsWith("/delete-bulk") ? "delete" : "update"));
		}
		let i = r ? new AbortController() : void 0, a = i ? setTimeout(() => i.abort(), 3e4) : void 0;
		try {
			return Ni(await e.request(t, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(n),
				...i ? { signal: i.signal } : {}
			}));
		} finally {
			a !== void 0 && clearTimeout(a);
		}
	}
	async function i(t, n, r) {
		let i = (await Promise.allSettled([Promise.resolve().then(() => e.refresh(t)), ...n ? [Promise.resolve().then(() => e.refreshSummary())] : []])).find((e) => e.status === "rejected");
		i && e.notify(`${r ? "操作已处理，" : ""}页面刷新失败: ${Ai(i.reason)}`);
	}
	async function a(a, o, s = null) {
		if (!Mi(a)) throw Error(`未支持的账号动作：${ji(a).name}`);
		if (e.canInvoke?.(a, s) === !1) return;
		let { name: c, value: l } = ji(a), u = c === "deleteDeactivatedAccounts", d = c === "account-email-invalid" || c === "setAccountsEmailInvalid", f, p, m = !1, h = !1, g = !1, _ = u ? "删除请求失败，请刷新核实：" : d ? "更新邮箱失效标记失败: " : c === "account-restore" ? "恢复账号失败: " : c === "deleteSelectedAccounts" ? "批量删除失败: " : "删除失败: ";
		try {
			let i = u ? [] : Fi(o), v = o.archived;
			if (!u && !i.length) {
				e.notify("请先选择账号");
				return;
			}
			if (c.startsWith("account-") && i.length !== 1) throw Error("此操作只能选择一个账号");
			if (f = n(a, o), t.has(f)) {
				f = void 0;
				return;
			}
			t.add(f);
			let y = i[0], b = u ? void 0 : o.rowHints.find((e) => String(e.id) === String(y)), x = u ? "" : o.expectedEmails[String(y)] || b?.email || "";
			if (d) {
				if (i.length > 500) {
					e.notify("单次最多操作 500 个账号");
					return;
				}
				let t = {};
				for (let n of i) {
					let r = o.expectedEmails[String(n)];
					if (!r) {
						e.notify("部分账号缺少邮箱快照，请重新勾选后操作");
						return;
					}
					t[String(n)] = r;
				}
				let n = l !== "0", c = "";
				if (n) {
					let t = await e.prompt(`为 ${i.length} 个账号标记邮箱失效，请填写原因（最多 300 字）`, "用户确认邮箱失效");
					if (t === null) return;
					if (c = t.trim() || "用户确认邮箱失效", c.length > 300) {
						e.notify("邮箱失效原因最多 300 字");
						return;
					}
				} else if (!await e.confirm(`确定解除 ${i.length} 个账号的邮箱失效标记？\n\n仅清除本地标记，邮箱可用性仍需确认。`)) return;
				p = e.beginBusy?.(a, s, "更新中…") || void 0, m = !0;
				let u = await r("/api/accounts/email-invalid-bulk", {
					account_ids: i,
					invalid: n,
					reason: c,
					expected_emails: t
				}), d = Pi(u.updated_count), f = Array.isArray(u.skipped) ? u.skipped.length : 0;
				if (h = !0, Array.isArray(u.items)) {
					let t = Ii(u.updated, i);
					t.length && e.removeAcknowledgedSelection(t, o);
				}
				e.notify(`${n ? "已标记邮箱失效" : "已清除本地邮箱失效标记"} ${d} 个${f ? `，跳过 ${f} 个（邮箱可能已变更）` : ""}`);
			} else if (u) {
				if (![
					"0",
					"only",
					"all"
				].includes(v)) throw Error("归档范围无效");
				if (!await e.confirm(`确定删除「${ki(v)}」范围内全部已废账号？\n\n不限当前页，不受勾选、搜索或其他筛选影响。仅删除本地账号记录，保留邮箱池和巡检历史。此操作不可撤销。`)) return;
				p = e.beginBusy?.(a, s) || void 0, m = !0, g = !0;
				let t = Pi((await r("/api/accounts/delete-deactivated", { archived: v }, !0)).deleted_count);
				h = !0, e.clearSelection(o), e.notify(`已删除 ${t} 个已废账号`);
			} else if (c === "account-restore") {
				if (![
					"account_status",
					"codex_status",
					"codex_credential_state"
				].some((e) => String(b?.[e] || "").toLowerCase() === "deactivated")) {
					e.notify("当前账号没有本地停用标记，无需恢复");
					return;
				}
				if (!await e.confirm(`确定恢复账号 #${y}？\n\n已确认 OpenAI 恢复访问权限后，解除本地停用标记；历史封禁记录保留，AT 和 Codex 凭证需要重新验证。`)) return;
				p = e.beginBusy?.(a, s, "恢复中…") || void 0, m = !0;
				let t = await r(`/api/accounts/${y}/restore`, { reason: "已收到 OpenAI 恢复访问通知" });
				if (String(t.id) !== String(y)) throw Error("服务端未确认账号恢复结果");
				h = !0, g = !0, e.notify(typeof t.message == "string" && t.message ? t.message : "已解除本地停用标记，请刷新 AT 重新验证");
			} else {
				let t = c === "account-archive" || c === "archiveSelectedAccounts", n = !c.startsWith("account-"), u = n ? v !== "only" : l === "1", d = t ? u ? "归档" : "恢复" : "删除";
				_ = `${n ? "批量" : ""}${d}失败: `;
				let f = t ? u ? n ? "归档后默认账号列表不会查询/显示这些账号，可勾选“查看归档”单独查看。" : "归档后默认账号列表不会查询/显示它，可勾选“查看归档”单独查看。" : n ? "恢复后这些账号会回到默认账号列表。" : "恢复后会回到默认账号列表。" : "会从本地账号列表、注册成功邮箱和 token 文件中移除。";
				if (!await e.confirm(n ? `确定${d}选中的 ${i.length} 个账号吗？\n\n${f}` : `确定${d}账号 #${y}？\n\n${x}\n\n${f}`)) return;
				p = e.beginBusy?.(a, s, t ? `${d}中…` : void 0) || void 0, m = !0;
				let b = await r(n ? `/api/accounts/${t ? "archive" : "delete"}-bulk` : `/api/accounts/${y}/${t ? "archive" : "delete"}`, n ? {
					account_ids: i,
					...t ? { archived: u } : {}
				} : t ? { archived: u } : {}), S, C;
				if (n) {
					S = Ii(b[t ? "updated" : "deleted"], i);
					let e = Pi(b[t ? "updated_count" : "deleted_count"]), n = Array.isArray(b.skipped) ? b.skipped.length : 0;
					C = `已${d} ${e} 个${n ? `，跳过 ${n} 个` : ""}`;
				} else {
					if (b[t ? "updated" : "deleted"] !== !0 || (t || b.id !== void 0) && String(b.id) !== String(y)) throw Error("服务端未确认账号操作结果");
					S = [String(y)], C = t ? u ? "账号已归档" : "账号已恢复" : "账号已删除";
				}
				h = !0, g = !0, S.length && e.removeAcknowledgedSelection(S, o), e.notify(C);
			}
		} catch (t) {
			e.notify(t instanceof me ? t.message : `${h ? "操作已处理，页面更新失败: " : _}${Ai(t)}`);
		} finally {
			(h || u && m) && await i(o, g || u, h);
			try {
				m && e.selectionChanged?.(o);
			} finally {
				try {
					p?.();
				} finally {
					f && t.delete(f);
				}
			}
		}
	}
	return {
		isSupported: Mi,
		invoke: a,
		isPending: (e, r) => t.has(n(e, r))
	};
}
// src/features/accounts/actions.ts
var Ri = {
	copySelectedAccountTokens: {
		field: "access_token",
		empty: "选中账号没有可复制 Token",
		success: (e) => `已复制 ${e} 个 Token`,
		error: "复制失败: "
	},
	copySelectedAccountLines: {
		field: "account_credentials_line",
		empty: "选中账号没有可复制整行",
		success: (e) => `已复制 ${e} 行`,
		error: "复制失败: "
	},
	copySelectedAccountEmails: {
		field: "email",
		empty: "选中账号没有可复制的邮箱",
		success: (e) => `已复制 ${e} 个邮箱`,
		error: "复制邮箱失败: ",
		feedback: !1,
		copyFailed: "复制邮箱失败"
	},
	copySelectedAccountExtractLinks: {
		field: "extract_link",
		empty: "选中账号没有成功提炼地址",
		success: (e) => `已复制 ${e} 个提炼地址`,
		error: "复制提炼地址失败: ",
		feedback: !1,
		copyFailed: "复制提炼地址失败"
	},
	copySelectedAccountPasswords: {
		field: "account_password_line",
		empty: "选中账号均未在本地保存密码",
		success: (e) => `已复制 ${e} 个账号密码；本地未保存密码的账号已跳过`,
		error: "复制密码失败: "
	},
	copySelectedAccountTotpSecrets: {
		field: "totp_secret",
		empty: "选中账号没有已设置的 2FA 密钥",
		success: (e) => `已复制 ${e} 个 2FA 密钥；未设置 2FA 的账号已跳过`,
		error: "复制 2FA 失败: "
	}
}, zi = {
	copy_line: "账号整行已复制",
	chatgpt_session: "ChatGPT session 已复制",
	account_password: "账号密码已复制",
	totp_secret: "TOTP 密钥已复制",
	access_token: "Token 已复制"
}, Bi = {
	downloadSelectedAccountTxt: "生成 TXT 失败: ",
	downloadSelectedAccountSessions: "下载 Session 失败: ",
	downloadSelectedCpa: "下载 CPA 失败: "
}, Vi = (e, t) => Object.prototype.hasOwnProperty.call(e, t);
function Hi(e) {
	let t = e.indexOf(":");
	return t < 0 ? {
		name: e,
		value: "",
		hasValue: !1
	} : {
		name: e.slice(0, t),
		value: e.slice(t + 1),
		hasValue: !0
	};
}
function Ui(e) {
	let { name: t, value: n, hasValue: r } = Hi(e);
	return t === "account-copy-secret" ? r && Vi(zi, n) : !r && (t === "account-totp-copy" || Vi(Ri, t) || Vi(Bi, t));
}
function Wi(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Gi(e) {
	if (!e) return "";
	if (typeof e != "string") throw Error("服务端响应格式无效");
	return e;
}
function Ki(e) {
	let t = Number(e || 0);
	if (!Number.isFinite(t) || !Number.isInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function qi(e) {
	if (e.download_url == null || e.download_url === "") throw Error("服务端未返回下载地址");
	if (typeof e.download_url != "string" || e.filename != null && typeof e.filename != "string") throw Error("服务端响应格式无效");
	if (!e.download_url.trim()) throw Error("服务端未返回下载地址");
	return {
		url: e.download_url,
		filename: e.filename || ""
	};
}
function Ji(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	let t = e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	});
	return Object.freeze([...new Set(t)]);
}
function Yi(e) {
	return e instanceof Error ? e.message : "请求失败，请稍后重试。";
}
function Xi(e) {
	let t = e.queued ? oi(e, e.queued) : void 0, n = e.setup ? Oi(e, e.setup) : void 0, r = e.local ? Li({
		...e.local,
		request: e.request,
		notify: e.notify,
		confirm: e.confirm,
		canInvoke: e.canInvoke,
		beginBusy: e.beginBusy
	}) : void 0, i = /* @__PURE__ */ new Set(), a = (e, t) => e.startsWith("account-") ? JSON.stringify([e, ...t.map(String)]) : e, o = async (t, n) => Wi(await e.request(t, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(n)
	}));
	async function s(e, t) {
		let n = await o("/api/accounts/secret-bulk", {
			account_ids: e,
			field: t
		});
		if (!Array.isArray(n.values)) throw Error("服务端响应格式无效");
		return n.values.map((e) => Gi(Wi(e).value)).filter(Boolean);
	}
	async function c(c, l, u = null) {
		if (t?.isSupported(c)) return t.invoke(c, l, u);
		if (n?.isSupported(c)) return n.invoke(c, l, u);
		if (r?.isSupported(c)) return r.invoke(c, l, u);
		if (!Ui(c)) throw Error(`未支持的账号动作：${Hi(c).name}`);
		if (e.canInvoke?.(c, u) === !1) return;
		let { name: d, value: f } = Hi(c), p = Vi(Ri, d) ? Ri[d] : void 0, m = p?.error ?? Bi[d] ?? (d === "account-totp-copy" ? "复制验证码失败: " : "复制失败: "), h, g, _ = !1, v = () => {
			h && i.delete(h);
			let e = g;
			g = void 0, e?.();
		};
		try {
			let t = Ji(l);
			if (!t.length) {
				e.notify("请先选择账号");
				return;
			}
			if (d.startsWith("account-") && t.length !== 1) throw Error("此操作只能选择一个账号");
			if (h = a(c, t), i.has(h)) {
				h = void 0;
				return;
			}
			if (i.add(h), d === "downloadSelectedCpa" && !await e.confirm(`确定从 CPA 下载选中的 ${t.length} 个账号的 CPA/Codex JSON 吗？\n\n会按账号邮箱匹配 CPA auth-files，成功的文件会打包成 ZIP，缺失文件会写入 manifest 错误清单。`)) return;
			let n = d === "account-totp-copy" ? "查询中…" : d === "downloadSelectedAccountSessions" ? "打包中…" : d === "downloadSelectedCpa" ? "下载中…" : void 0;
			if (g = e.beginBusy?.(c, u, n) || void 0, _ = d === "downloadSelectedCpa", p) {
				let n = await s(t, p.field);
				if (!n.length) {
					e.notify(p.empty);
					return;
				}
				let r = p.feedback === !1 ? await e.clipboard(n.join("\n"), !1) : await e.clipboard(n.join("\n"));
				e.notify(p.copyFailed && !r ? p.copyFailed : p.success(n.length));
			} else if (d === "account-copy-secret") {
				let n = Gi(Wi(await e.request(`/api/accounts/${t[0]}/secret?field=${encodeURIComponent(f)}`)).value);
				if (!n) {
					e.notify("可复制内容为空");
					return;
				}
				await e.clipboard(n), e.notify(zi[f]);
			} else if (d === "account-totp-copy") {
				let n = Wi(await e.request(`/api/accounts/${t[0]}/totp-code`)), r = Gi(n.code);
				if (!r) throw Error("验证码为空");
				let i = Ki(n.remaining_seconds), a = await e.clipboard(r, !1);
				e.notify(a ? `验证码已复制，剩余 ${i} 秒` : "验证码已查询，但复制失败");
			} else if (d === "downloadSelectedAccountTxt") {
				let n = await s(t, "copy_line");
				if (!n.length) {
					e.notify("选中账号没有可下载整行");
					return;
				}
				let r = e.now(), i = (e) => String(e).padStart(2, "0"), a = `accounts-selected-${r.getFullYear()}${i(r.getMonth() + 1)}${i(r.getDate())}-${i(r.getHours())}${i(r.getMinutes())}${i(r.getSeconds())}.txt`;
				await e.downloadBlob(new Blob(["﻿" + n.join("\n") + "\n"], { type: "text/plain;charset=utf-8" }), a), e.notify(`已下载 ${n.length} 个账号 TXT`);
			} else if (d === "downloadSelectedAccountSessions") {
				let n = await o("/api/accounts/download-session-bulk", {
					account_ids: t,
					prepare: !0
				}), { url: r, filename: i } = qi(n), a = Ki(n.added_count), s = Ki(n.skipped_count);
				await e.downloadUrl(r, i), e.notify(a === 0 ? `没有可下载的 Session，已生成结果清单，跳过 ${s} 个；开始下载，分类原因见 ZIP 内 manifest.json；Session 缺失或无效的账号请先刷新 AT，读取失败的账号请重试` : `已打包 ${a} 个账号 Session，跳过 ${s} 个；开始下载，结果见 ZIP 内 manifest.json`);
			} else if (d === "downloadSelectedCpa") {
				let n = await o("/api/accounts/download-cpa-bulk", {
					account_ids: t,
					prepare: !0
				}), { url: r, filename: i } = qi(n), a = Ki(n.error_count);
				await e.downloadUrl(r, i), e.notify(`已生成 ZIP，开始下载${a ? `（${a} 个失败见 manifest）` : ""}`), e.schedule(() => {
					Promise.resolve().then(() => e.reloadCodex()).catch((t) => e.notify(`下载已开始，但 Codex 列表刷新失败: ${Yi(t)}`));
				}, 1200);
			}
		} catch (t) {
			e.notify(m + Yi(t));
		} finally {
			_ ? e.schedule(v, 1200) : v();
		}
	}
	return {
		isSupported: (e) => Ui(e) || t?.isSupported(e) === !0 || n?.isSupported(e) === !0 || r?.isSupported(e) === !0,
		invoke: c,
		isPending: (e, o) => i.has(a(e, o.accountIds)) || t?.isPending(e, o) === !0 || n?.isPending(e, o) === !0 || r?.isPending(e, o) === !0,
		receipts: t?.receipts,
		setVisible: (e) => t?.setVisible(e),
		dispose: () => t?.dispose()
	};
}
// src/features/accounts/browserDownloads.ts
function Zi(e) {
	function t(t, n, r, i) {
		let a, o = () => {
			try {
				i?.();
			} finally {
				a?.remove();
			}
		};
		try {
			a = e.document.createElement("a"), a.href = t, a.download = n, i || (a.rel = "noopener"), e.document.body.appendChild(a), a.click(), e.schedule(o, r);
		} catch (e) {
			throw o(), e;
		}
	}
	return {
		downloadBlob(n, r) {
			let i = e.urls.createObjectURL(n);
			t(i, r, 800, () => e.urls.revokeObjectURL(i));
		},
		downloadUrl(n, r) {
			let i;
			try {
				i = new URL(n, e.origin);
			} catch {
				throw Error("下载地址必须为同源 HTTP 地址");
			}
			if (!["http:", "https:"].includes(i.protocol) || i.origin !== new URL(e.origin).origin || i.username || i.password) throw Error("下载地址必须为同源 HTTP 地址");
			t(n, r, 1e3);
		}
	};
}
// src/accounts.ts
function Qi(e, t) {
	let n = ne(t.query), r = Zi({
		document,
		origin: window.location.origin,
		urls: URL,
		schedule: (e, t) => setTimeout(e, t)
	}), i = Xi({
		...t.actionDependencies,
		request: ce,
		...r,
		now: () => /* @__PURE__ */ new Date(),
		schedule: (e, t) => setTimeout(e, t)
	});
	return A(kr, {
		adapter: n,
		api: Pr(n),
		presentation: He(t.presentation),
		callbacks: t.callbacks,
		detailApi: Fr(),
		detailPresentation: t.detailPresentation,
		syncModalScrollLock: t.syncModalScrollLock,
		actions: i,
		inspectionDependencies: {
			...t.inspectionDependencies,
			request: ce
		},
		emailChangeDependencies: {
			...t.emailChangeDependencies,
			request: ce
		},
		c2aDependencies: {
			...t.c2aDependencies,
			request: ce
		},
		initialCapabilities: t.capabilities
	}).mount(e);
}
export { Qi as mountAccounts };
