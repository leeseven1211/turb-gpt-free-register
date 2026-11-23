import { $ as e, A as t, C as n, F as r, G as i, H as a, K as o, L as s, M as c, N as l, P as u, R as d, S as f, X as p, Z as m, _ as h, a as g, c as _, d as v, dt as y, et as b, f as x, ft as S, g as C, h as w, j as T, k as E, l as D, lt as O, m as k, n as A, nt as j, o as M, s as N, st as P, t as F, tt as I, v as L, x as R } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { a as z, c as B, i as V, n as H, o as U, r as W, s as G, t as ee } from "./ListFilterSummary-C8h8bMwn.js";
import { t as K } from "./ListPagination-DURVj-Kj.js";
import { a as q, c as J, i as Y, n as X, r as te, s as ne, t as re } from "./queryAdapter-BorDKfhY.js";
import { n as ie, t as ae } from "./ColumnResizer-CPJ9UuoZ.js";
import { t as oe } from "./errorLabels-PB-ct2iU.js";
import { n as se, r as ce, t as le } from "./client-B5R_MNgP.js";
import { a as ue, n as de } from "./taskIds-BlchWwUp.js";
// src/features/accounts/accountToolbar.ts
var fe = Object.freeze([
	"操作",
	"批次与巡检",
	"复制与导出",
	"资产管理"
]), pe = Object.freeze([
	Object.freeze({
		id: "btnCheckSelectedLiveV2",
		label: "查活",
		section: "操作",
		action: "checkSelectedLive",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "只在线验证现有 Token；不会发送邮箱验证码或刷新 AT",
		selection: !0,
		feature: "live_check"
	}),
	Object.freeze({
		id: "btnCheckSelectedPlansV2",
		label: "查套餐",
		section: "操作",
		action: "checkSelectedPlans",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "查询选中账号当前套餐；free 账号会检查 Plus 免费试用或折扣优惠",
		selection: !0,
		feature: "plan_check"
	}),
	Object.freeze({
		id: "btnRefreshSelectedTokenV2",
		label: "刷新 AT",
		section: "操作",
		action: "refreshSelectedToken",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "按已保存的刷新驱动获取最新 AT",
		selection: !0,
		feature: "token_refresh"
	}),
	Object.freeze({
		id: "btnReimportSelectedC2aV2",
		label: "批量同步到 C2A",
		section: "操作",
		action: "reimportSelectedC2a",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "批量同步选中账号的本地当前 AT，支持跨页选择；唯一同邮箱时覆盖 AT，未找到时新建账号",
		selection: !0,
		feature: "c2a_sync"
	}),
	Object.freeze({
		id: "btnEmailChangeSelectedV2",
		label: "批量换绑邮箱",
		section: "操作",
		action: "openBulkEmailChangeForSelectedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "为选中账号批量领取新邮箱并执行协议换绑",
		selection: !0
	}),
	Object.freeze({
		id: "btnCheckSelectedDeactivationMailV2",
		label: "查封号邮件",
		section: "操作",
		action: "checkSelectedDeactivationMail",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "扫描 Email Butler / Cloudflare / iCloud 转发邮箱中的 OpenAI 封号通知；不会刷新 AT",
		selection: !0,
		feature: "deactivation_mail"
	}),
	Object.freeze({
		id: "btnAddPasswordSelectedAccountsV2",
		label: "补密码",
		section: "操作",
		action: "addPasswordSelectedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "只给选中账号补充登录密码",
		selection: !0,
		feature: "password_setup"
	}),
	Object.freeze({
		id: "btnAddTwofaSelectedAccountsV2",
		label: "补 2FA",
		section: "操作",
		action: "addTwofaSelectedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "只给选中账号补充 Authenticator 2FA",
		selection: !0
	}),
	Object.freeze({
		id: "btnChangePasswordSelectedAccountsV2",
		label: "修改密码",
		section: "操作",
		action: "changePasswordSelectedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "强制通过忘记密码流程修改选中账号密码",
		selection: !0,
		feature: "password_setup"
	}),
	Object.freeze({
		id: "btnChangeTwofaSelectedAccountsV2",
		label: "修改 2FA",
		section: "操作",
		action: "changeTwofaSelectedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "先关闭旧 Authenticator，再启用并确认新的 2FA",
		selection: !0,
		feature: "twofa_change"
	}),
	Object.freeze({
		id: "btnCompleteSelectedAccountsV2",
		label: "补全账号",
		section: "操作",
		action: "completeSelectedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "按配置补全账号密码、套餐、2FA、Codex；刷新 AT 是否包含由配置决定",
		selection: !0
	}),
	Object.freeze({
		id: "btnRetrySelectedRegistrationV2",
		label: "重跑注册",
		section: "操作",
		action: "retryAccountRegistration",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "找到选中账号的原注册任务，按当前进度继续注册或补跑缺失步骤",
		selection: !0
	}),
	Object.freeze({
		id: "btnRetrySelectedCodexV2",
		label: "补 Codex",
		section: "操作",
		action: "retrySelectedCodex",
		className: "jobs-tb-btn jobs-tb-btn--primary",
		title: "给选中的账号批量补跑 Codex 授权",
		selection: !0,
		feature: "codex_retry"
	}),
	Object.freeze({
		id: "btnExtractSelectedLinksV2",
		label: "提链",
		section: "操作",
		action: "extractSelectedLinks",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "仅给已确认 Plus 免费试用资格的 free 账号批量提链；折扣优惠会跳过",
		selection: !0,
		feature: "extract_link"
	}),
	Object.freeze({
		id: "btnBulkFromAccountFilters",
		label: "按当前筛选创建批次",
		section: "批次与巡检",
		action: "bulk-from-account-filters",
		className: "jobs-tb-btn",
		title: "",
		selection: !1
	}),
	Object.freeze({
		id: "btnBulkFromSelectedAccounts",
		label: "用已选账号创建批次",
		section: "批次与巡检",
		action: "bulk-from-selected-accounts",
		className: "jobs-tb-btn",
		title: "",
		selection: !1
	}),
	Object.freeze({
		id: "btnAccountInspection",
		label: "一键巡检",
		section: "批次与巡检",
		action: "openAccountInspectionStart",
		className: "jobs-tb-btn",
		title: "",
		selection: !1
	}),
	Object.freeze({
		id: "btnAccountInspectionHistory",
		label: "巡检历史",
		section: "批次与巡检",
		action: "openAccountInspectionHistory",
		className: "jobs-tb-btn",
		title: "",
		selection: !1
	}),
	Object.freeze({
		id: "btnCopySelectedTokensV2",
		label: "复制 Token",
		section: "复制与导出",
		action: "copySelectedAccountTokens",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "复制选中账号的 Token，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedLinesV2",
		label: "复制行",
		section: "复制与导出",
		action: "copySelectedAccountLines",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "复制选中账号的账号、密码、2FA，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedExtractLinksV2",
		label: "复制提炼地址",
		section: "复制与导出",
		action: "copySelectedAccountExtractLinks",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "复制选中账号已成功生成的提炼地址，每个地址一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedEmailsV2",
		label: "复制邮箱",
		section: "复制与导出",
		action: "copySelectedAccountEmails",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "复制选中账号的邮箱，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedPasswordsV2",
		label: "复制密码",
		section: "复制与导出",
		action: "copySelectedAccountPasswords",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "复制选中账号中本地已保存的账号密码，格式为 邮箱----密码",
		selection: !0
	}),
	Object.freeze({
		id: "btnCopySelectedTotpsV2",
		label: "复制 2FA",
		section: "复制与导出",
		action: "copySelectedAccountTotpSecrets",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "复制选中账号的 2FA 密钥，每个账号一行，不是 6 位验证码",
		selection: !0
	}),
	Object.freeze({
		id: "btnDownloadSelectedTxtV2",
		label: "下载 TXT",
		section: "复制与导出",
		action: "downloadSelectedAccountTxt",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "把选中账号的完整整行保存为 TXT 文件，每个账号一行",
		selection: !0
	}),
	Object.freeze({
		id: "btnDownloadSelectedSessionsV2",
		label: "下载 Session",
		section: "复制与导出",
		action: "downloadSelectedAccountSessions",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "把选中账号已保存的 Session 按每账号一个 JSON 打包为 ZIP；缺失账号列入结果清单",
		selection: !0
	}),
	Object.freeze({
		id: "btnMarkSelectedEmailInvalidV2",
		label: "标记邮箱失效",
		section: "资产管理",
		action: "setAccountsEmailInvalid:1",
		className: "jobs-tb-btn",
		title: "为选中账号标记邮箱失效，不修改 OpenAI 账号状态",
		selection: !0
	}),
	Object.freeze({
		id: "btnClearSelectedEmailInvalidV2",
		label: "解除邮箱失效",
		section: "资产管理",
		action: "setAccountsEmailInvalid:0",
		className: "jobs-tb-btn",
		title: "仅清除本地邮箱失效标记，邮箱可用性仍需确认",
		selection: !0
	}),
	Object.freeze({
		id: "btnDownloadSelectedCpaV2",
		label: "下载 CPA",
		section: "资产管理",
		action: "downloadSelectedCpa",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "从 CPA auth-files 下载选中账号的 Codex JSON，并打包 ZIP",
		selection: !0,
		feature: "cpa_download"
	}),
	Object.freeze({
		id: "btnUploadSelectedCodexSub2V2",
		label: "上传 sub2",
		section: "资产管理",
		action: "uploadSelectedCodexSub2",
		className: "jobs-tb-btn jobs-tb-btn--good",
		title: "把选中账号已通过的 Codex OAuth 凭证上传到 sub2api",
		selection: !0,
		feature: "sub2_upload"
	}),
	Object.freeze({
		id: "btnStopSelectedCodexV2",
		label: "停止 Codex",
		section: "资产管理",
		action: "stopSelectedCodex",
		className: "jobs-tb-btn jobs-tb-btn--danger",
		title: "停止选中账号中正在补跑的 Codex 授权",
		selection: !0
	}),
	Object.freeze({
		id: "btnArchiveSelectedAccountsV2",
		label: "归档选中",
		section: "资产管理",
		action: "archiveSelectedAccounts",
		className: "jobs-tb-btn",
		title: "归档选中的账号；默认账号列表将不再查询/显示这些账号",
		selection: !0
	}),
	Object.freeze({
		id: "btnDeleteSelectedAccountsV2",
		label: "删除",
		section: "资产管理",
		action: "deleteSelectedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--danger",
		title: "删除选中的本地账号/token记录",
		selection: !0
	}),
	Object.freeze({
		id: "btnDeleteDeactivatedAccounts",
		label: "删除已废",
		section: "资产管理",
		action: "deleteDeactivatedAccounts",
		className: "jobs-tb-btn jobs-tb-btn--danger",
		title: "",
		selection: !1
	})
]), me = "turb_account_action_usage_v1", he = Object.freeze([
	"btnCheckSelectedLiveV2",
	"btnCheckSelectedPlansV2",
	"btnRefreshSelectedTokenV2",
	"btnExtractSelectedLinksV2",
	"btnAddTwofaSelectedAccountsV2"
]);
function ge(e, t) {
	let n = [...he, ...e.filter((e) => !he.includes(e))];
	return [...e].sort((e, r) => (t[r] || 0) - (t[e] || 0) || n.indexOf(e) - n.indexOf(r)).slice(0, 5);
}
function _e(t, n, r) {
	let i = j({}), a = j(ge(t, {})), o, s = !1;
	function c() {
		let e = i.value;
		try {
			let t = n.storage.getItem(me);
			t !== null && (e = JSON.parse(t));
		} catch {}
		return Object.fromEntries(t.map((t) => {
			let n = e && typeof e == "object" && !Array.isArray(e) ? e[t] : 0;
			return [t, Number.isSafeInteger(n) && Number(n) > 0 ? Number(n) : 0];
		}));
	}
	function l() {
		if (s || r()) return;
		i.value = c();
		let e = ge(t, i.value);
		e.join(",") !== a.value.join(",") && (a.value = e);
	}
	function u() {
		s || o !== void 0 || (o = n.requestFrame(() => {
			o = void 0, l();
		}));
	}
	function d(e) {
		if (s || !t.includes(e)) return;
		let r = c();
		r[e] = Math.min(2 ** 53 - 1, r[e] + 1), i.value = r;
		try {
			n.storage.setItem(me, JSON.stringify(r));
		} catch {}
		u();
	}
	let f = n.addStorageListener((e) => {
		e.key === "turb_account_action_usage_v1" && u();
	});
	return m(() => {
		s = !0, o !== void 0 && n.cancelFrame(o), o = void 0, f();
	}), {
		counts: e(i),
		quickIds: e(a),
		refresh: l,
		schedule: u,
		record: d
	};
}
// src/features/accounts/AccountsToolbar.vue?vue&type=script&setup=true&lang.ts
var ve = {
	class: "accounts-command-deck",
	id: "accountsCommandDeck"
}, ye = {
	class: "list-selection-hint",
	id: "accountsSelectedHintV2"
}, be = { class: "toolbar-overflow-menu" }, xe = { class: "toolbar-overflow-section-title" }, Se = ["id", "onClick"], Ce = {
	class: "acc-v2-btn-group account-quick-actions",
	id: "accountsQuickActionsV2",
	role: "group",
	"aria-label": "常用账号操作，按此浏览器使用次数排序",
	title: "显示此浏览器使用次数最多的五项操作，批量操作一次算一次"
}, we = ["data-account-shortcut", "onClick"], Te = /* @__PURE__ */ n({
	__name: "AccountsToolbar",
	props: {
		state: {},
		capabilities: {},
		getContext: { type: Function },
		invoke: { type: Function },
		runtime: {},
		notify: { type: Function }
	},
	setup(e, { expose: t }) {
		let n = e, i = b(), a = b(), o = b(), l = fe.map((e) => ({
			title: e,
			items: pe.filter((t) => t.section === e)
		})), u = new Map(pe.map((e) => [e.id, e])), d = j(/* @__PURE__ */ new Set()), f = _e(pe.map((e) => e.id), n.runtime, () => {
			let e = i.value, t = e?.ownerDocument;
			return !!(a.value?.open || t?.querySelector("dialog[open]") || e?.contains(t?.activeElement ?? null));
		}), p = k(() => f.quickIds.value.map((e) => u.get(e))), m = (e) => e.feature ? n.capabilities[e.feature] : void 0, h = (e) => m(e)?.enabled === !1, g = (e) => e.selection && n.state.selectedCount === 0 || d.value.has(e.action) || !!n.state.pending?.[e.action], y = (e) => n.state.labels?.[e.action] || (e.id === "btnArchiveSelectedAccountsV2" && n.state.archived ? "恢复选中" : e.label), x = (e) => e.id === "btnArchiveSelectedAccountsV2" && n.state.archived ? "把选中的归档账号恢复到默认账号列表" : e.title;
		function C(e) {
			let t = m(e), n = t?.enabled === !1;
			return {
				class: [e.className, { "feature-unavailable": n }],
				disabled: g(e),
				title: n ? `不可用：${t.reason || "缺少必要配置"}` : x(e),
				"data-feature": t ? e.feature : void 0,
				"data-feature-base-title": t ? x(e) : void 0,
				"aria-disabled": t ? n : void 0
			};
		}
		function D(e) {
			a.value?.open && (e.preventDefault(), e.stopPropagation(), a.value.open = !1, o.value?.focus({ preventScroll: !0 }));
		}
		function A() {
			let e = a.value, t = e?.ownerDocument.defaultView, n = i.value?.closest(".ac-toolbar");
			if (!e?.open || !t || !n) return;
			let r = n.getBoundingClientRect().bottom;
			e.style.setProperty("--ac-batch-menu-height", `${Math.max(0, t.innerHeight - r - 12)}px`);
		}
		function M() {
			A(), f.schedule();
		}
		async function N(e, t) {
			let r = t.currentTarget;
			if (!(g(e) || h(e) || r.disabled || r.getAttribute("aria-disabled") === "true")) {
				f.record(e.id), d.value = /* @__PURE__ */ new Set([...d.value, e.action]);
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
		let F;
		return c(() => {
			F = i.value?.ownerDocument;
			let e = F?.defaultView;
			e?.addEventListener("resize", A), e?.addEventListener("scroll", A, { passive: !0 }), F?.addEventListener("close", f.schedule, !0), f.refresh();
		}), T(() => {
			let e = F?.defaultView;
			e?.removeEventListener("resize", A), e?.removeEventListener("scroll", A), F?.removeEventListener("close", f.schedule, !0);
		}), t({ refreshQuickActions: f.refresh }), (t, n) => (r(), L("div", ve, [w("div", {
			ref_key: "toolbar",
			ref: i,
			class: O(["jobs-toolbar-v2 list-action-toolbar", { "has-selection": e.state.selectedCount > 0 }]),
			id: "accountsToolbarV2",
			onFocusout: n[0] ||= (...e) => P(f).schedule && P(f).schedule(...e)
		}, [
			w("span", ye, S(e.state.selectedCount ? `已选 ${e.state.selectedCount} 个账号` : "选择账号后批量操作"), 1),
			w("details", {
				ref_key: "more",
				ref: a,
				class: "toolbar-overflow",
				id: "accountsMoreActionsV2",
				onToggle: M,
				onKeydown: _(D, ["esc"])
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
			}, { ref_for: !0 }, C(e), { onClick: (t) => N(e, t) }), S(y(e)), 17, Se))), 128))]))), 128))])], 544),
			w("div", Ce, [(r(!0), L(v, null, s(p.value, (e) => (r(), L("button", E({
				key: e.id,
				"data-account-shortcut": e.id,
				type: "button"
			}, { ref_for: !0 }, C(e), { onClick: (t) => N(e, t) }), S(y(e)), 17, we))), 128))])
		], 34)]));
	}
}), Ee = { class: "ac-filter-fields" }, De = {
	key: 0,
	class: "ac-filter-field"
}, Oe = ["value"], ke = {
	key: 1,
	class: "list-filter-options"
}, Ae = { class: "ac-sr-only" }, je = { class: "list-filter-option" }, Me = ["checked"], Ne = [
	"value",
	"checked",
	"onChange"
], Pe = { key: 0 }, Fe = [
	"type",
	"inputmode",
	"value",
	"placeholder",
	"onInput"
], Ie = { class: "list-filter-actions" }, Le = /* @__PURE__ */ n({
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
		let n = e, a = t, c = b("id"), l = k(() => n.column || X.find((e) => e.key === c.value) || X[0]), u = k(() => n.column ? te(n.query, n.column) : X.some((e) => te(n.query, e))), d = k(() => q(n.query, n.label).find((e) => e.key === l.value.key)?.label || ""), f = k(() => Y(n.query, n.facets, l.value, n.label)), p = k(() => ne(n.query, l.value.key)), m = k(() => l.value.kind === "date-range" ? ["date_from", "date_to"] : [l.value.key]);
		function y(e, t) {
			let n = new Set(p.value);
			t ? n.add(e) : n.delete(e), a("change", l.value.key, [...n]);
		}
		function x() {
			a("clear", l.value.key), a("update:open", !1);
		}
		return (t, n) => (r(), C(V, {
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
				}, [(r(!0), L(v, null, s(P(X), (e) => (r(), L("option", {
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
					(r(!0), L(v, null, s(f.value, (e) => (r(), L("label", {
						class: "list-filter-option",
						key: e.value
					}, [
						w("input", {
							type: "checkbox",
							value: e.value,
							checked: p.value.includes(e.value),
							onChange: (t) => y(e.value, t.target.checked)
						}, null, 40, Ne),
						w("span", null, S(e.label), 1),
						e.count === null ? h("", !0) : (r(), L("small", Pe, S(e.count), 1))
					]))), 128))
				])) : (r(!0), L(v, { key: 2 }, s(m.value, (t, i) => (r(), L("label", {
					key: t,
					class: "ac-filter-field"
				}, [R(S(l.value.kind === "date-range" ? i ? "截止日期" : "开始日期" : l.value.label), 1), w("input", {
					type: l.value.kind === "date-range" ? "date" : "text",
					inputmode: l.value.key === "id" ? "numeric" : void 0,
					value: P(J)(e.query, t),
					placeholder: l.value.placeholder,
					autocomplete: "off",
					onInput: (e) => a("change", t, e.target.value),
					onKeydown: n[2] ||= _(D((e) => a("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, Fe)]))), 128)),
				w("div", Ie, [w("button", {
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
}), Re = [
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
], ze = [
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
], Be = ze.map((e) => e / ze.reduce((e, t) => e + t, 0) * 1500);
function Ve(e) {
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
var He = [
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
function Ue(e) {
	if (!(e instanceof Element)) return;
	let t = e.closest("button,[data-copy-id]");
	if (!t || t.hasAttribute("disabled") || t.getAttribute("aria-disabled") === "true" || t.classList.contains("feature-unavailable")) return;
	let n = He.find((e) => t.hasAttribute(`data-${e}`));
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
var We = ["aria-busy"], Ge = ["data-stale"], Ke = [
	"checked",
	"indeterminate",
	"disabled"
], qe = { id: "accountsBodyV2" }, Je = ["data-account-row", "onClick"], Ye = { class: "col-check" }, Xe = [
	"data-account-id",
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], Ze = { class: "col-id" }, Qe = { class: "col-email" }, $e = ["disabled", "data-account-detail-id"], et = { class: "acc-v2-email" }, tt = {
	key: 0,
	class: "pill status-used",
	title: "该账号已归档"
}, nt = { class: "acc-v2-sub account-cell-line account-cell-line--sub account-email-meta" }, rt = { class: "account-email-name" }, it = ["innerHTML"], at = { class: "acc-mobile-meta" }, ot = { class: "col-source" }, st = { class: "col-registration-driver" }, ct = ["data-label"], lt = ["innerHTML"], ut = { class: "col-actions" }, dt = { class: "account-cell-lines acc-v2-actions" }, ft = ["disabled", "data-account-detail-id"], pt = ["disabled"], mt = ["onClick", "innerHTML"], ht = /* @__PURE__ */ n({
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
		let o = e, l = n, { widths: d, total: p, resize: m, resizeWithKeyboard: g, resetColumns: _ } = ie({
			defaults: Be,
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
			cells: Object.fromEntries(Re.filter((e) => e.cell).map((t) => [t.cell, A(o.presentation.cell(t.cell, e))])),
			menu: o.presentation.menu(e),
			mobile: o.presentation.mobileSummary(e),
			tone: o.presentation.rowTone(e)
		}))), M = (e) => X.find((t) => t.key === e);
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
			let i = Ue(e.target);
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
			w("thead", null, [w("tr", null, [(r(!0), L(v, null, s(P(Re), (t, i) => (r(), L("th", {
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
			}, null, 40, Ke)) : t.filter ? (r(), C(Le, {
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
			])) : (r(), L(v, { key: 2 }, [R(S(t.label), 1)], 64)), i ? (r(), C(ae, {
				key: 3,
				label: t.label,
				onStart: (e) => P(m)(i, e),
				onNudge: (e) => P(g)(i, e)
			}, null, 8, [
				"label",
				"onStart",
				"onNudge"
			])) : h("", !0)], 2))), 128))])]),
			w("tbody", qe, [(r(!0), L(v, null, s(j.value, (t) => (r(), L("tr", {
				key: t.id,
				"data-account-row": t.id,
				class: O({ "ac-row-selected": e.selected.has(t.id) }),
				onClick: (e) => N(e, t.row)
			}, [
				w("td", Ye, [w("input", {
					type: "checkbox",
					class: "account-row-check",
					"data-account-id": t.id,
					"aria-label": `选择账号 ${t.row.email || t.id}`,
					checked: e.selected.has(t.id),
					disabled: e.stale,
					onChange: (e) => l("select", t.id, e.target.checked)
				}, null, 40, Xe)]),
				w("td", Ze, [f(W, { text: `#${t.id}` }, null, 8, ["text"])]),
				w("td", Qe, [
					w("button", {
						type: "button",
						class: "acc-v2-email-link account-cell-line",
						disabled: e.stale,
						"data-account-detail-id": t.id,
						title: "查看账号详情"
					}, [w("span", {
						class: O(["acc-mobile-dot", `is-${t.tone}`]),
						"aria-hidden": "true"
					}, null, 2), w("span", et, [R(S(t.row.email), 1), t.row.archived ? (r(), L("span", tt, "归档")) : h("", !0)])], 8, $e),
					w("div", nt, [w("span", rt, S(t.row.user_name || "-"), 1), w("span", { innerHTML: e.presentation.emailInvalidBadge(t.row) }, null, 8, it)]),
					w("div", at, S(t.mobile), 1)
				]),
				w("td", ot, [f(W, { text: t.row.email_source || "-" }, null, 8, ["text"])]),
				w("td", st, [f(W, { text: e.presentation.registrationDriverLabel(t.row.registration_driver) }, null, 8, ["text"])]),
				(r(!0), L(v, null, s(P(Re).filter((e) => e.cell), (e) => (r(), L("td", {
					key: e.key,
					class: O(e.className),
					"data-label": e.label
				}, [w("div", {
					class: "ac-legacy-cell",
					innerHTML: t.cells[e.cell]
				}, null, 8, lt)], 10, ct))), 128)),
				w("td", ut, [w("div", dt, [w("button", {
					type: "button",
					class: "acc-v2-detail",
					disabled: e.stale,
					"data-account-detail-id": t.id
				}, "详情", 8, ft), f(P(B), {
					open: e.visible && !e.stale && E.value === t.id,
					modal: !1,
					"onUpdate:open": (e) => E.value = e ? t.id : null
				}, {
					default: i(() => [f(P(z), { "as-child": "" }, {
						default: i(() => [w("button", {
							type: "button",
							class: "acc-v2-more-btn",
							disabled: e.stale,
							"aria-label": "更多账号操作"
						}, "更多", 8, pt)]),
						_: 1
					}), f(P(U), null, {
						default: i(() => [f(P(G), {
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
							}, null, 8, mt)]),
							_: 2
						}, 1032, ["data-account-menu"])]),
						_: 2
					}, 1024)]),
					_: 2
				}, 1032, ["open", "onUpdate:open"])])])
			], 10, Je))), 128)), j.value.length ? h("", !0) : (r(), C(H, {
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
		], 12, Ge)], 40, We));
	}
}), gt = 3e4, _t = [
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
function vt(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(vt), Object.freeze(e)), e;
}
function yt(e) {
	return vt(Z(e));
}
function bt(e) {
	let t = String(e);
	if (!/^[1-9]\d*$/.test(t) || !Number.isSafeInteger(Number(t))) throw Error("账号 ID 无效");
	return t;
}
function xt() {
	throw new DOMException("读取已失效", "AbortError");
}
function St(e) {
	return Z({
		account_promotions: e.account_promotions ?? null,
		promotion_query_snapshot: e.promotion_query_snapshot ?? null,
		plan_check_country_results: e.plan_check_country_results ?? []
	});
}
function Ct(n, r) {
	let i = j(n.normalize()), a = j([]), o = j({}), s = j([]), c = j(null), l = b(0), u = b(1), d = b(20), f = b(!1), p = b(!1), h = b(!1), g = b(""), _ = b(!1), v = b(""), y = j(/* @__PURE__ */ new Set()), x = j({}), S = b(""), C = k(() => Math.max(1, Math.ceil(l.value / d.value))), w = k(() => n.toLegacy(i.value, {
		paged: "1",
		page: u.value,
		page_size: d.value
	}).toString()), T = k(() => S.value !== w.value), E = k(() => a.value.length > 0 && a.value.every((e) => y.value.has(String(e.id)))), D = k(() => !E.value && a.value.some((e) => y.value.has(String(e.id)))), O = 0, A = 0, M = 0, N = 0, P = !1, F = !1, I, L, R, z, B, V = "", H, U, W = /* @__PURE__ */ new Map(), G = /* @__PURE__ */ new Map(), ee = () => typeof document > "u" || !document.hidden, K = () => !P && h.value && ee(), q = (e, t) => e === O && t === w.value && K();
	function J(e) {
		return [...G.values()].some((t) => t === e);
	}
	function Y() {
		let e = /* @__PURE__ */ new Set([...a.value.map((e) => String(e.id)), ...G.values()]);
		for (let [t, n] of W) e.has(t) || (n.request?.controller.abort(), W.delete(t));
	}
	function X() {
		for (let e of W.values()) e.request?.controller.abort(), e.request = void 0, ++e.version;
	}
	function te() {
		++O, ++A, I?.abort(), L?.abort(), I = L = void 0, clearTimeout(R), clearTimeout(B), R = B = void 0, f.value = p.value = !1;
	}
	function ne() {
		clearTimeout(R), R = void 0, K() && H !== i.value.q && (R = setTimeout(() => {
			ue();
		}, 5e3));
	}
	function re(e) {
		let t = Z(e);
		for (let e of _t) {
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
				details: St(e)
			});
		}
		Y();
	}
	async function ae(e) {
		if (te(), !K()) return;
		let t = O, c = new AbortController(), p = n.toLegacy(i.value).toString(), m = !e || U?.filter !== p || Date.now() - U.readAt >= gt;
		m && (U = void 0), I = c, f.value = !0;
		try {
			for (let e = 0; e < 2; e++) {
				let n = w.value, a = Z(i.value), f = u.value, h = d.value, v = m && !U, y = await r.list(a, f, h, c.signal, { includeFacets: v });
				if (!q(t, n)) return;
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
			if (t !== O || !K() || se(e)) return;
			g.value = e instanceof Error ? e.message : "加载账号失败", e instanceof le && e.code === "account_search_invalid" && (H = i.value.q, _.value = !0, U = void 0, a.value = [], l.value = 0, s.value = [], o.value = {}, Y());
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
			let e = (e) => e?.map((e) => ({
				...e,
				plan: "plus"
			})) ?? null;
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
		if (clearTimeout(R), R = void 0, !K() || f.value || p.value || T.value || H === i.value.q) {
			ne();
			return;
		}
		let e = O, t = w.value, n = new AbortController();
		L = n, p.value = !0;
		try {
			let o = await r.statuses(Z(i.value), u.value, d.value, n.signal);
			if (!q(e, t)) return;
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
			q(e, t) && n instanceof le && n.code === "account_search_invalid" && (H = i.value.q, _.value = !0, g.value = n instanceof Error ? n.message : "筛选语法无效", U = void 0, a.value = [], l.value = 0, o.value = {}, s.value = [], Y());
		} finally {
			e === O && (p.value = !1, L = void 0, ne());
		}
	}
	function de(e = 0, n = !1) {
		if (te(), !K()) return;
		let r = A, i = () => {
			r === A && K() && ae(n);
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
		let n = bt(e), r = a.value.find((e) => String(e.id) === n);
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
		let t = [...new Set((e.ids ?? [...y.value]).map(bt))], n = {}, r = new Map(a.value.map((e) => [String(e.id), e]));
		for (let e of t) {
			let t = r.has(e) ? r.get(e)?.email : x.value[e];
			t && (n[e] = t);
		}
		if (e.requireEmails && (t.length > 500 || t.some((e) => !n[e]?.trim()))) throw Error(t.length > 500 ? "一次最多处理 500 个账号" : "账号邮箱快照不完整，请刷新后重新选择");
		return yt({
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
		return yt({
			accountIds: t.ids,
			expectedEmails: t.expectedEmails,
			querySnapshot: t.query,
			archived: t.query.archived,
			rowHints: a.value.filter((e) => n.has(String(e.id)))
		});
	}
	function je(e) {
		let t = a.value.find((t) => String(t.id) === e);
		return t ? yt(t) : void 0;
	}
	async function Me(e) {
		K() && J(e) || xt();
		let t = W.get(e);
		if (t || xt(), t.details) return yt({
			accountId: e,
			revision: t.revision,
			item: t.details
		});
		if (t.request) return t.request.promise;
		let n = new AbortController(), i = t.version, o = r.planDetails(e, n.signal).then(async (n) => {
			K() && J(e) || xt();
			let r = W.get(e);
			return r || xt(), r !== t || r.version !== i ? Me(e) : (r.details = Z(n.item), a.value = a.value.map((t) => String(t.id) === e ? {
				...t,
				...Z(n.item)
			} : t), yt({
				accountId: e,
				revision: r.revision,
				item: r.details
			}));
		}, (n) => {
			K() && J(e) || xt();
			let r = W.get(e);
			if (r && (r !== t || r.version !== i)) return Me(e);
			throw n;
		}).finally(() => {
			t.request?.promise === o && (t.request = void 0), Y();
		});
		return t.request = {
			version: i,
			controller: n,
			promise: o
		}, o;
	}
	async function Ne(e, t) {
		let n = bt(e);
		for (;;) {
			G.get(t) === n && K() || xt();
			let e = W.get(n), r = e?.version, i;
			try {
				i = await Me(n);
			} catch (e) {
				throw G.get(t) === n && K() || xt(), e;
			}
			if (G.get(t) === n && K() || xt(), W.get(n) === e && e?.version === r) return i;
		}
	}
	function Pe(e) {
		let t = bt(e), n = ++N;
		if (!W.has(t)) throw Error("账号详情已失效，请刷新列表");
		return G.set(n, t), {
			openGeneration: n,
			loadPlanDetails: Ne,
			release() {
				if (G.delete(n)) {
					if (!J(t)) {
						let e = W.get(t);
						e?.request && (e.request.controller.abort(), e.request = void 0, ++e.version);
					}
					Y();
				}
			}
		};
	}
	function Fe(e) {
		P || e === h.value || (h.value = e, e ? de() : (te(), X(), G.clear(), Y()));
	}
	function Ie() {
		ee() ? h.value && de() : (te(), X());
	}
	return typeof document < "u" && document.addEventListener("visibilitychange", Ie), m(() => {
		P = !0, te(), clearTimeout(z), X(), G.clear(), W.clear(), typeof document < "u" && document.removeEventListener("visibilitychange", Ie);
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
var wt = {
	class: "ac-root",
	"aria-label": "账号列表"
}, Tt = { class: "ac-toolbar" }, Et = {
	key: 0,
	class: "ac-toolbar-main"
}, Dt = { class: "ac-toolbar-utilities" }, Ot = { class: "ac-mobile-filters" }, kt = [
	"value",
	"aria-invalid",
	"onKeydown"
], At = ["disabled"], jt = {
	key: 0,
	id: "accountAdvancedSearchErrorV2",
	class: "ac-feedback",
	role: "alert"
}, Mt = {
	key: 1,
	class: "ac-feedback",
	role: "alert"
}, Nt = /* @__PURE__ */ n({
	__name: "AccountsList",
	props: {
		adapter: {},
		api: {},
		presentation: {},
		callbacks: {}
	},
	setup(e, { expose: t }) {
		let n = e, i = Ct(n.adapter, n.api), { query: s, items: c, facets: l, searchTerms: u, total: p, page: m, size: g, pages: v, selected: y, loading: x, error: C, visible: E, invalidSearch: O, draftSearch: A, stale: j, pageSelected: M, pageIndeterminate: F } = i, I = b(), R = b(), z = b(null), B = b(typeof document > "u" || !document.hidden), V = b(""), H = /* @__PURE__ */ new Set(), U = X.find((e) => e.key === "email_status"), W = k(() => [...q(s.value, n.presentation.facetLabel), ...u.value.map((e, t) => ({
			key: `search:${t}`,
			label: `${e.label}：${e.display_value}`,
			title: `高级搜索 · 同时满足：${e.label}：${e.display_value}`,
			removeLabel: `移除${e.label}：${e.display_value}`
		}))]);
		function G(e, t) {
			e === "plan" ? i.updateQuery({ plan: [...t] }) : e === "date_from" || e === "date_to" ? i.updateQuery({ [e]: String(t) }) : e === "id" || e === "email" ? i.updateFilters({ [e]: String(t) }, 250) : i.updateFilters({ [e]: [...t] });
		}
		function J(e) {
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
			let t = X.find((t) => t.key === e);
			t && G(t.key, t.kind === "text" ? "" : []);
		}
		function Y(e) {
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
					Y(e);
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
				Y(/* @__PURE__ */ Error("账号详情暂不可用，请先刷新列表"));
				return;
			}
			let a;
			try {
				a = i.openPlanDetailsConsumer(e), n.callbacks.openDetail(e, r, a, t);
			} catch (e) {
				a?.release(), Y(e);
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
		}), (t, n) => o((r(), L("section", wt, [
			w("div", Tt, [
				W.value.length ? (r(), L("div", Et, [f(ee, {
					items: W.value,
					onRemove: J
				}, null, 8, ["items"])])) : h("", !0),
				d(t.$slots, "actions"),
				w("div", Dt, [
					w("div", Ot, [f(Le, {
						query: P(s),
						facets: P(l),
						label: e.presentation.facetLabel,
						open: B.value && z.value === "all",
						"onUpdate:open": n[0] ||= (e) => z.value = e ? "all" : null,
						onChange: G,
						onClear: J
					}, null, 8, [
						"query",
						"facets",
						"label",
						"open"
					])]),
					f(Le, {
						column: P(U),
						query: P(s),
						facets: P(l),
						label: e.presentation.facetLabel,
						open: B.value && z.value === "email_status",
						"onUpdate:open": n[1] ||= (e) => z.value = e ? "email_status" : null,
						onChange: G,
						onClear: J
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
						}, null, 40, kt),
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
						class: "ac-button",
						disabled: P(x),
						onClick: n[7] ||= (...e) => P(i).refresh && P(i).refresh(...e)
					}, S(P(x) ? "刷新中…" : "刷新"), 9, At)
				])
			]),
			d(t.$slots, "feedback"),
			P(O) ? (r(), L("p", jt, S(P(C)), 1)) : V.value || P(C) && P(c).length ? (r(), L("div", Mt, [w("span", null, S(V.value || P(C)), 1), P(C) ? (r(), L("button", {
				key: 0,
				type: "button",
				class: "ac-link",
				onClick: n[8] ||= (...e) => P(i).refresh && P(i).refresh(...e)
			}, "重试")) : h("", !0)])) : h("", !0),
			f(ht, {
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
				onFilter: G,
				onClearFilter: J,
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
function Pt(e) {
	return JSON.parse(JSON.stringify(e));
}
function Ft(e, t) {
	if (!e || typeof e != "object" || !("accountId" in e) || String(e.accountId) !== t || !("item" in e) || !e.item || typeof e.item != "object" || Array.isArray(e.item) || "id" in e.item && e.item.id != null && String(e.item.id) !== t) throw Error("账号详情响应不匹配");
	return Pt(e.item);
}
function It(e, t) {
	let n = j(null), r = j(0), i = k(() => n.value !== null), a = k(() => n.value ? String(n.value.id) : ""), o = null, s = (e) => o === e && r.value === e.generation;
	function c(e) {
		n.value = { ...e.account };
	}
	async function l(n) {
		try {
			let e = await n.lease.loadPlanDetails(n.id, n.lease.openGeneration);
			if (!s(n)) return;
			Object.assign(n.account, Ft(e, n.id)), c(n);
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
		let s = Pt(n);
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
var Lt = ["aria-hidden"], Rt = ["data-account-id"], zt = { class: "account-detail-head" }, Bt = { id: "accountDetailTitle" }, Vt = { id: "accountDetailSubtitle" }, Ht = ["innerHTML"], Ut = /* @__PURE__ */ n({
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
		let u = It(i.api, {
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
		}, null, 10, Lt), w("aside", {
			id: "accountDetailDrawer",
			class: O(["account-detail-drawer", { hidden: !P(p) }]),
			"data-account-id": P(p) ? P(f) : void 0,
			role: "dialog",
			"aria-modal": "true",
			"aria-labelledby": "accountDetailTitle"
		}, [w("div", zt, [w("div", null, [
			t[2] ||= w("div", { class: "data-panel-kicker" }, "ACCOUNT DETAIL", -1),
			w("h2", Bt, S(m.value), 1),
			w("p", Vt, S(h.value), 1)
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
		}, null, 8, Ht)], 10, Rt)]));
	}
}), Wt = (e) => e === "only" ? "已归档账号" : e === "all" ? "全部账号" : "未归档账号", Gt = (e) => ({
	running: "进行中",
	completed: "已完成",
	interrupted: "已中断"
})[String(e)] || String(e ?? ""), Kt = (e) => ({
	deactivated_skipped: "已废跳过",
	rejected: "未能入队",
	failed: "查活失败",
	error: "执行异常",
	attention_required: "执行失败",
	interrupted: "执行中断"
})[String(e)] || String(e ?? ""), qt = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : String(e);
function Jt(e) {
	return e && typeof e == "object" ? e : {};
}
function Yt(e) {
	return Object.freeze((Array.isArray(e) ? e : []).map((e) => Object.freeze({ ...Jt(e) })));
}
function Xt(e) {
	let t = b(!1), n = b(!1), r = b(!1), i = b("0"), o = b(3), s = b(!1), c = b(""), l = b(1), u = b(1), d = b(null), f = j([]), p = j([]), h = b(0), g = b(0), _ = b(!1), v = b(!1), y = b(""), x = b(!1), S = b(!1), C = b(!1), w = null, T = 0, E = 0, D = !1, O, A, M, N = () => typeof document > "u" || !document.hidden, P = k(() => _.value ? `共 ${h.value} 条 · 第 ${l.value} 页` : ""), F = k(() => v.value ? `共 ${g.value} 条 · 第 ${u.value} 页` : "");
	async function I(t, n = {}, r = new AbortController()) {
		let i = setTimeout(() => r.abort(), 3e4);
		try {
			return Jt(await e.request(t, {
				...n,
				signal: r.signal
			}));
		} finally {
			clearTimeout(i);
		}
	}
	function L() {
		for (let t of [e.refreshAccounts, e.refreshSummary]) try {
			Promise.resolve(t()).catch(() => {});
		} catch {}
	}
	function R(n) {
		D || (i.value = n.archived, o.value = Math.min(16, e.operationWorkers()), c.value = "", t.value = !0);
	}
	async function z() {
		let n = Number(o.value);
		if (!(D || s.value || !Number.isInteger(n) || n < 1 || n > 16)) {
			s.value = !0;
			try {
				w ||= e.randomUUID();
				let r = await I("/api/accounts/inspections", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						workers: n,
						archived: i.value,
						idempotency_key: w
					})
				});
				if (w = null, C.value = !0, D) return;
				t.value = !1, e.notify(r.created ? "巡检已加入统一任务队列" : "已有本次巡检记录，已打开历史"), B();
			} catch (e) {
				D || (c.value = `巡检启动请求失败：${qt(e)}。可查看巡检历史，或使用当前提交再次确认。`);
			} finally {
				s.value = !1;
			}
		}
	}
	function B() {
		D || (l.value = 1, ++T, n.value = !0, H());
	}
	function V(e) {
		x.value || (l.value = Math.max(1, l.value + e), ++T, H());
	}
	async function H() {
		if (D || x.value || !n.value || !N()) return;
		x.value = !0;
		let t = l.value, r = T, i = new AbortController();
		O = i;
		try {
			let e = await I(`/api/accounts/inspections?page=${t}`, {}, i);
			if (D || i.signal.aborted || !n.value || t !== l.value || r !== T) return;
			let a = C.value;
			C.value = !!e.active, a && !C.value && L(), f.value = Yt(e.items), h.value = Number(e.total), _.value = !0;
		} catch (t) {
			!D && n.value && N() && r === T && e.notify(`读取巡检历史失败：${qt(t)}`);
		} finally {
			x.value = !1, O === i && (O = void 0), r !== T && !D && n.value && N() && H();
		}
	}
	function U(e) {
		D || (d.value = Number(e), u.value = 1, ++E, v.value = !1, y.value = "", p.value = [], r.value = !0, G());
	}
	function W(e) {
		S.value || (u.value = Math.max(1, u.value + e), ++E, G());
	}
	async function G() {
		if (D || S.value || !d.value || !r.value || !N()) return;
		S.value = !0;
		let e = d.value, t = u.value, n = E, i = new AbortController();
		A = i;
		try {
			let a = await I(`/api/accounts/inspections/${e}/failures?page=${t}`, {}, i);
			if (D || i.signal.aborted || !r.value || e !== d.value || t !== u.value || n !== E) return;
			p.value = Yt(a.items), g.value = Number(a.total), v.value = !0, y.value = "";
		} catch (e) {
			!D && r.value && N() && n === E && (y.value = `读取失败：${qt(e)}，可点击刷新重试。`);
		} finally {
			S.value = !1, A === i && (A = void 0), n !== E && !D && r.value && N() && G();
		}
	}
	async function ee(t) {
		if (!D) try {
			if (await I(`/api/accounts/inspections/${Number(t)}/cancel`, { method: "POST" }), D) return;
			e.notify("已请求停止，将在安全检查点结束"), H();
		} catch (t) {
			D || e.notify(`停止巡检失败：${qt(t)}`);
		}
	}
	function K(e) {
		e && e !== "start" || (t.value = !1), e && e !== "history" || (n.value = !1, ++T, O?.abort()), e && e !== "failures" || (r.value = !1, ++E, A?.abort());
	}
	function q() {
		M !== void 0 && (clearInterval(M), M = void 0), !D && N() && (n.value || r.value) && (M = setInterval(() => {
			n.value && H(), r.value && G();
		}, 5e3));
	}
	function J() {
		N() || (++T, ++E, O?.abort(), A?.abort()), q();
	}
	return a([n, r], q, { flush: "sync" }), typeof document < "u" && document.addEventListener("visibilitychange", J), m(() => {
		D = !0, K(), q(), typeof document < "u" && document.removeEventListener("visibilitychange", J);
	}), {
		startOpen: t,
		historyOpen: n,
		failuresOpen: r,
		archived: i,
		workers: o,
		starting: s,
		startError: c,
		historyPage: l,
		failurePage: u,
		failureId: d,
		historyRows: f,
		failureRows: p,
		historyTotal: h,
		failureTotal: g,
		historyReady: _,
		failureReady: v,
		failureError: y,
		historyLoading: x,
		failureLoading: S,
		historyLabel: P,
		failureLabel: F,
		openStart: R,
		submit: z,
		openHistory: B,
		openFailures: U,
		close: K,
		changeHistoryPage: V,
		changeFailuresPage: W,
		refreshHistory: H,
		refreshFailures: G,
		stop: ee
	};
}
// src/features/accounts/Inspection.vue?vue&type=script&setup=true&lang.ts
var Zt = ["data-archived"], Qt = { class: "modal-header" }, $t = { id: "accountInspectionScope" }, en = {
	id: "accountInspectionStartError",
	role: "status"
}, tn = ["disabled"], nn = { class: "modal-header" }, rn = {
	key: 0,
	"data-inspection-scroll": "",
	tabindex: "0",
	role: "region",
	"aria-label": "可左右滚动查看巡检记录"
}, an = { class: "data-table" }, on = ["data-inspection-task", "onClick"], sn = { class: "sub-cell" }, cn = { class: "sub-cell" }, ln = { key: 0 }, un = ["onClick"], dn = ["onClick"], fn = { key: 1 }, pn = { class: "jobs-v2-pager" }, mn = ["disabled"], hn = { id: "accountInspectionPageLabel" }, gn = ["disabled"], _n = { class: "modal-header" }, vn = { id: "accountInspectionFailuresTitle" }, yn = { key: 0 }, bn = {
	key: 1,
	"data-inspection-scroll": "",
	tabindex: "0",
	role: "region",
	"aria-label": "可左右滚动查看巡检记录"
}, xn = { class: "data-table" }, Sn = { class: "inspection-error-reason" }, Cn = { key: 2 }, wn = { class: "jobs-v2-pager" }, Tn = ["disabled"], En = { id: "accountInspectionFailuresPageLabel" }, Dn = ["disabled"], On = /*#__PURE__*/ F(/* @__PURE__ */ n({
	__name: "Inspection",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, c = Xt(i.deps), { startOpen: l, historyOpen: u, failuresOpen: d, archived: f, workers: m, starting: g, startError: _, historyPage: y, failurePage: x, failureId: C, historyRows: E, failureRows: O, historyTotal: k, failureTotal: A, historyReady: j, failureReady: N, failureError: F, historyLabel: I, failureLabel: z } = c, B = b(), V = b(), H = b(), U = b(), W = b(), G = /* @__PURE__ */ new Map(), ee = {
			start: 0,
			history: 0,
			failures: 0
		}, K = {
			start: B,
			history: V,
			failures: H
		}, q = {
			start: l,
			history: u,
			failures: d
		}, J = !1;
		function Y(e, t) {
			q[e].value || G.set(e, t ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null));
		}
		function X(e, t) {
			Y("start", t), c.openStart(e), se("start");
		}
		function te(e) {
			Y("history", e), c.openHistory(), se("history");
		}
		function ne(e, t) {
			Y("failures", t), c.openFailures(e), se("failures");
		}
		function re(e) {
			c.close(e);
			let t = G.get(e);
			if (G.delete(e), J) return;
			let n = V.value?.open ? V.value.querySelector("button:not([disabled])") : i.deps.fallbackFocus?.();
			(t?.isConnected ? t : n)?.focus({ preventScroll: !0 });
		}
		function ie(e) {
			ee[e] ? --ee[e] : K[e].value?.open || re(e);
		}
		function ae(e) {
			let t = K[e].value;
			t?.open && (++ee[e], t.close(), re(e));
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
			let n = K[e].value, r = q[e].value;
			n && !J && (r && !n.open ? (G.has(e) || G.set(e, document.activeElement instanceof HTMLElement ? document.activeElement : null), n.showModal()) : !r && n.open && ae(e));
		}
		for (let e of [
			"start",
			"history",
			"failures"
		]) a(q[e], () => se(e), { flush: "post" });
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
			J = !0;
			for (let e of Object.values(K)) e.value?.open && e.value.close();
			G.clear();
		}), n({
			openStart: X,
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
			}, [w("div", Qt, [n[14] ||= w("h2", { id: "accountInspectionStartTitle" }, "启动账号巡检", -1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				"aria-label": "关闭启动巡检",
				onClick: n[0] ||= (e) => oe("start")
			}, "关闭")]), w("form", { onSubmit: n[2] ||= D((...e) => P(c).submit && P(c).submit(...e), ["prevent"]) }, [
				w("p", $t, "本次范围：" + S(P(Wt)(P(f))), 1),
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
				w("p", en, S(P(_)), 1),
				w("button", {
					type: "submit",
					class: "jobs-tb-btn jobs-tb-btn--primary",
					id: "btnConfirmAccountInspection",
					disabled: P(g)
				}, "开始巡检", 8, tn)
			], 32)], 40, Zt),
			w("dialog", {
				ref_key: "history",
				ref: V,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionHistory",
				"aria-labelledby": "accountInspectionHistoryTitle",
				onClose: n[8] ||= (e) => ie("history")
			}, [
				w("div", nn, [
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
				}, [P(E).length ? (r(), L("div", rn, [w("table", an, [w("thead", null, [w("tr", null, [(r(), L(v, null, s([
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
					}, "#" + S(Number(t.id)), 9, on)]),
					w("td", null, S(P(Wt)(String(t.archived))), 1),
					w("td", null, [R(S(P(Gt)(t.status)), 1), w("div", sn, S(e.deps.formatDateTime(t.created_at)), 1)]),
					w("td", null, S(Number(t.workers)), 1),
					w("td", null, [R(S(Number(t.checked_count) + Number(t.skipped_count)) + " / " + S(Number(t.total_count)), 1), w("div", cn, "跳过 " + S(Number(t.skipped_count)) + "（已废 " + S(Number(t.deactivated_skipped_count)) + "）", 1)]),
					w("td", null, S(Number(t.invalid_count)), 1),
					w("td", null, [R(S(Number(t.live_success_count)) + " / " + S(Number(t.live_failed_count)), 1), le(t) ? (r(), L("div", ln, [w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: (e) => ne(Number(t.id), e.currentTarget)
					}, "失败详情 " + S(le(t)), 9, un)])) : h("", !0)]),
					w("td", null, S(Number(t.plan_success_count)) + " / " + S(Number(t.plan_failed_count)), 1),
					w("td", null, [t.status === "running" ? (r(), L("button", {
						key: 0,
						type: "button",
						class: "jobs-tb-btn",
						onClick: (e) => P(c).stop(Number(t.id))
					}, "停止", 8, dn)) : h("", !0)])
				]))), 128))])])])) : (r(), L("p", fn, S(P(j) ? "暂无巡检记录。" : "正在读取巡检历史…"), 1))], 512),
				w("div", pn, [
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionPrev",
						disabled: P(y) <= 1,
						onClick: n[6] ||= (e) => P(c).changeHistoryPage(-1)
					}, "上一页", 8, mn),
					w("span", hn, S(P(I)), 1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionNext",
						disabled: P(y) * 20 >= P(k),
						onClick: n[7] ||= (e) => P(c).changeHistoryPage(1)
					}, "下一页", 8, gn)
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
				w("div", _n, [
					w("h2", vn, S(P(C) ? `巡检 #${P(C)} · 失败详情` : "巡检失败详情"), 1),
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
				}, [P(F) ? (r(), L("p", yn, S(P(F)), 1)) : P(O).length ? (r(), L("div", bn, [w("table", xn, [w("thead", null, [w("tr", null, [(r(), L(v, null, s([
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
					w("td", null, S(P(Kt)(t.status)), 1),
					w("td", null, S(e.deps.formatDateTime(t.failed_at)), 1),
					w("td", Sn, S(t.error), 1)
				]))), 128))])])])) : (r(), L("p", Cn, S(P(N) ? "本轮暂无查活失败或已废跳过。" : "正在读取本次失败记录…"), 1))], 512),
				w("div", wn, [
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresPrev",
						disabled: !P(N) || P(x) <= 1,
						onClick: n[11] ||= (e) => P(c).changeFailuresPage(-1)
					}, "上一页", 8, Tn),
					w("span", En, S(P(z)), 1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresNext",
						disabled: !P(N) || P(x) * 20 >= P(A),
						onClick: n[12] ||= (e) => P(c).changeFailuresPage(1)
					}, "下一页", 8, Dn)
				])
			], 544)
		], 64));
	}
}), [["__scopeId", "data-v-88e51d48"]]);
// src/features/accounts/useAccountEmailChange.ts
function kn(e) {
	return JSON.parse(JSON.stringify(e));
}
function An(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(An), Object.freeze(e)), e;
}
function jn(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Mn(e) {
	return e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败，请稍后重试";
}
function Nn(e) {
	return [...new Set((Array.isArray(e?.accountIds) ? e.accountIds : []).map(Number).filter((e) => Number.isSafeInteger(e) && e > 0).map(String))];
}
function Pn(e, t = {}) {
	let n = b(!1), r = b(0), i = b("single"), a = j(null), o = j(null), s = j([]), c = j([]), l = b(""), u = b("idle"), d = b(""), f = b(!1), p = k(() => u.value !== "ready" || !c.value.some((e) => e.enabled)), h = null, g = !1, _ = (e) => !g && h === e && r.value === e.generation && n.value;
	function v({ restoreFocus: e = !0 } = {}) {
		let i = h;
		i && (h = null, ++r.value, i.controller.abort(), n.value = !1, a.value = null, o.value = null, s.value = [], c.value = [], l.value = "", u.value = "idle", d.value = "", f.value = !1, t.closed?.(e, i.trigger, r.value));
	}
	async function y(n, r) {
		try {
			let t = jn(await e.request("/api/email-sources", { signal: n.controller.signal }));
			if (!_(n)) return;
			c.value = An((Array.isArray(t.sources) ? t.sources : []).map((e) => {
				let t = jn(e);
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
			u.value = "failed", c.value = [], l.value = "", d.value = `邮箱来源读取失败：${Mn(e)}`;
		}
		_(n) && t.sourcesReady?.(n.generation);
	}
	function x(e, p, m, _, b) {
		if (g) return !1;
		let x = An(kn({
			..._,
			accountIds: p
		}));
		v({ restoreFocus: !1 });
		let S = {
			generation: ++r.value,
			mode: e,
			account: m,
			accountIds: An([...p]),
			context: x,
			trigger: b,
			controller: new AbortController(),
			submitting: !1
		};
		return h = S, i.value = e, a.value = m, s.value = S.accountIds, o.value = x, n.value = !0, u.value = "loading", l.value = "", d.value = "", c.value = [], f.value = !1, t.opened?.(S.generation), y(S, String(m?.email_source || "").trim().toLowerCase()), !0;
	}
	function S(t, n, r = null) {
		let i = Number(t), a = String(i), o = n?.rowHints?.find((e) => String(e.id) === a);
		return !Number.isSafeInteger(i) || i <= 0 || !Nn(n).includes(a) || !o ? (e.notify("账号详情暂不可用，请先刷新列表"), !1) : x("single", [a], An({
			id: i,
			email: String(o.email || ""),
			email_source: String(o.email_source || "")
		}), n, r);
	}
	function C(t, n = null) {
		let r = Nn(t);
		return r.length ? r.length > 500 ? (e.notify("单次最多换绑 500 个账号"), !1) : x("bulk", r, null, t, n) : (e.notify("请先选择账号"), !1);
	}
	function w(t, n) {
		try {
			Promise.resolve(t()).catch((t) => e.notify(n + Mn(t)));
		} catch (t) {
			e.notify(n + Mn(t));
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
			r = jn(await e.request(t.mode === "bulk" ? "/api/accounts/email-change-bulk" : `/api/accounts/${t.account.id}/email-change`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(t.mode === "bulk" ? {
					account_ids: t.accountIds.map(Number),
					email_source: n
				} : { email_source: n })
			}));
		} catch (n) {
			_(t) && (d.value = `提交失败：${Mn(n)}`), e.notify("换绑邮箱失败: " + Mn(n));
			return;
		} finally {
			t.submitting = !1, _(t) && (f.value = !1);
		}
		let i = _(t), a = An({
			result: kn(r),
			context: t.context,
			mode: t.mode,
			accountIds: t.accountIds,
			accountId: t.account?.id || null,
			oldEmail: t.account?.email || "",
			emailSource: n,
			stale: !i
		});
		if (t.mode === "bulk") {
			let t = Number(r.started_count || 0), n = Number(r.skipped_count || 0);
			e.notify(`批量换绑已入队 ${t} 个${n ? `，跳过 ${n} 个` : ""}`);
		} else e.notify(String(r.message || `邮箱换绑已入队 · 任务 #${r.task_id || "-"}`));
		i && v({ restoreFocus: !1 }), w(() => e.recordReceipt(a), "换绑已受理，记录回执失败："), w(() => e.refreshAccounts(t.context), "换绑已受理，刷新账号失败："), i && !g && !h && w(() => e.openTasks({
			target: t.mode === "bulk" ? "" : t.account.email || `#${t.account.id}`,
			type: "email_change"
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
var Fn = [
	"aria-hidden",
	"data-account-id",
	"data-account-ids"
], In = {
	class: "email-change-dialog",
	role: "document"
}, Ln = { class: "email-change-head" }, Rn = { id: "emailChangeTitle" }, zn = { id: "emailChangeAccountLabel" }, Bn = {
	class: "email-change-field",
	for: "emailChangeSource"
}, Vn = ["disabled"], Hn = { value: "" }, Un = [
	"value",
	"disabled",
	"title",
	"data-reason"
], Wn = ["hidden"], Gn = { class: "email-change-foot" }, Kn = ["disabled"], qn = /* @__PURE__ */ n({
	__name: "EmailChange",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, a = b(), c = b(), u = b(), d = !1, f = null;
		function m() {
			let e = f;
			f = null, e?.isConnected && e.focus({ preventScroll: !0 });
		}
		let h = Pn(i.deps, {
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
		async function ee() {
			c.value?.setCustomValidity(""), !c.value?.checkValidity() || !M.value || F.value ? (c.value?.setCustomValidity("请选择新邮箱来源"), h.error.value = "请选择新邮箱来源", c.value?.reportValidity(), c.value?.focus()) : await h.submit();
		}
		function K(e) {
			if (!_.value) return;
			if (e.key === "Escape") {
				e.preventDefault(), G();
				return;
			}
			if (e.key !== "Tab") return;
			let t = Array.from(a.value?.querySelectorAll("button, select, [href], [tabindex]:not([tabindex=\"-1\"])") || []).filter((e) => !("disabled" in e && e.disabled) && !e.hidden), n = t[0], r = t.at(-1);
			e.shiftKey && document.activeElement === n ? (e.preventDefault(), r?.focus()) : !e.shiftKey && document.activeElement === r && (e.preventDefault(), n?.focus());
		}
		return document.addEventListener("keydown", K), T(() => {
			d = !0, document.removeEventListener("keydown", K), h.close();
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
		}, [w("div", In, [w("div", Ln, [w("div", null, [
			t[4] ||= w("div", { class: "data-panel-kicker" }, "PROTOCOL OPERATION", -1),
			w("h2", Rn, S(z.value), 1),
			w("p", zn, S(B.value), 1)
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
			onSubmit: D(ee, ["prevent"])
		}, [
			w("label", Bn, [
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
				}, [w("option", Hn, S(V.value), 1), (r(!0), L(v, null, s(P(j), (e, t) => (r(), L("option", {
					key: `${e.value}:${t}`,
					value: e.value,
					disabled: !e.enabled,
					title: e.reason,
					"data-reason": e.reason
				}, S(e.label) + S(e.enabled ? "" : "（不可用）"), 9, Un))), 128))], 8, Vn), [[g, P(M)]]),
				t[6] ||= w("small", { id: "emailChangeSourceHelp" }, "系统会从所选邮箱池自动领取新地址，并读取新邮箱验证码。", -1),
				w("small", {
					id: "emailChangeSourceError",
					class: "email-change-error",
					role: "alert",
					hidden: !P(I)
				}, S(P(I)), 9, Wn)
			]),
			t[7] ||= w("div", {
				id: "emailChangeNote",
				class: "email-change-note"
			}, "换绑、Recent Login 和验证码校验全部走协议任务，不会启动浏览器。成功写回后会自动创建一次协议查活任务刷新 AT。", -1),
			w("div", Gn, [w("button", {
				id: "btnCancelEmailChange",
				type: "button",
				class: "jobs-tb-btn",
				onClick: t[2] ||= (e) => G()
			}, "取消"), w("button", {
				id: "btnSubmitEmailChange",
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				disabled: P(R)
			}, S(P(R) ? "提交中…" : "开始换绑"), 9, Kn)])
		], 32)])], 10, Fn)]));
	}
});
// src/features/accounts/useC2aReimport.ts
function Jn(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Yn(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(Yn), Object.freeze(e)), e;
}
function Xn(e) {
	return Yn(JSON.parse(JSON.stringify(e)));
}
var Zn = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败";
function Qn(e) {
	let t = /* @__PURE__ */ new Map();
	for (let n of [e.skipped, e.failed]) for (let e of Array.isArray(n) ? n : []) {
		let n = e && typeof e == "object" ? e : {}, r = String(n.reason || n.error || n.error_code || "服务端未返回原因，请重试");
		t.set(r, (t.get(r) || 0) + 1);
	}
	return t.size ? `；未入队原因：${[...t].slice(0, 3).map(([e, t]) => `${e}${t > 1 ? `（${t} 个）` : ""}`).join("；")}${t.size > 3 ? `；另有 ${t.size - 3} 类原因` : ""}` : "；未入队原因：服务端未返回原因，请重试";
}
function $n(e) {
	return [
		"queued",
		"skipped",
		"failed"
	].flatMap((t, n) => (Array.isArray(e[t]) ? e[t] : []).map((e) => ({
		item: Jn(e),
		state: [
			"已入队",
			"未入队",
			"入队失败"
		][n]
	})));
}
function er(e, t = {}) {
	let n = b(!1), r = b(!1), i = b(""), a = j([]), o = j(null), s = null, c = null, l = !1, u = k(() => o.value ? $n(o.value) : []), d = k(() => u.value.filter((e) => Number(e.item.task_id) > 0)), f = k(() => {
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
		return u.length ? (s = Xn(t), a.value = Object.freeze([...u]), c = o, r.value = !1, i.value = "", n.value = !0, !0) : (e.notify("请先选择账号"), !1);
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
			e.notify(n + Zn(t));
		}
	}
	function _(e) {
		o.value = Xn(Jn(e));
	}
	function v(t = d.value.map((e) => e.item)) {
		let n = t.length === 1 ? t[0] : null;
		return g(() => e.openTasks({
			filters: { type: "c2a_session_reimport" },
			taskId: Number(n?.task_id) || void 0,
			runId: Number(n?.run_id) || null
		}), "C2A 请求已处理，打开任务失败: ");
	}
	async function y() {
		if (l || !n.value || !s || !a.value.length || r.value) return;
		let t = [...a.value], o = s, u = c;
		r.value = !0, i.value = "正在创建 C2A 同步任务…";
		let d = e.beginBusy?.(u, "提交导入…"), f;
		try {
			f = Jn(await e.request("/api/accounts/c2a/sync-bulk", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ account_ids: t })
			}));
		} catch (t) {
			e.notify("重新导入 C2A 失败: " + Zn(t)), l || (i.value = `提交失败：${Zn(t)}。请检查后再次提交。`), r.value = !1, d?.(), e.selectionChanged?.(o);
			return;
		}
		try {
			let t = Number(f.skipped_count ?? (Array.isArray(f.skipped) ? f.skipped.length : 0)) + Number(f.failed_count ?? (Array.isArray(f.failed) ? f.failed.length : 0)), n = t ? Qn(f) : "";
			f.accepted ? e.notify(`C2A 重新导入已入队 ${f.queued_count ?? (Array.isArray(f.queued) ? f.queued.length : 0)} 个，未入队 ${t} 个，请在任务中心查看结果${n}`) : (e.notify(t ? `C2A 已重新导入 ${f.updated_count || 0} 个，跳过/失败 ${t} 个${n}` : `C2A 已重新导入 ${f.updated_count || 0} 个`), await g(() => e.refreshAccounts(o), "C2A 请求已处理，页面更新失败: "));
		} catch (t) {
			e.notify("C2A 请求已处理，回执更新失败: " + Zn(t));
		} finally {
			r.value = !1;
			try {
				d?.();
			} finally {
				l || h("submitted", !0);
			}
		}
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
// src/features/accounts/C2aReimport.vue?vue&type=script&setup=true&lang.ts
var tr = { class: "c2a-reimport-confirm-head" }, nr = ["disabled"], rr = { class: "c2a-reimport-confirm-body" }, ir = { class: "c2a-reimport-confirm-scope" }, ar = { id: "c2aReimportConfirmCountV2" }, or = ["hidden"], sr = { class: "c2a-reimport-confirm-foot" }, cr = ["disabled"], lr = ["disabled"], ur = /* @__PURE__ */ n({
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
		let d = er({
			...i.deps,
			beginBusy: (e, t) => {
				if (i.deps.beginBusy) return i.deps.beginBusy(e, t);
				let n = e instanceof HTMLButtonElement ? e : null, r = n?.textContent || "";
				return n && (n.disabled = !0, n.textContent = t), () => {
					n && (n.textContent = r, n.disabled = !1);
				};
			}
		}, { closed: (e, t) => {
			a.value?.open && (++s, a.value.close(t)), u(e, c);
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
			w("div", tr, [t[3] ||= w("div", null, [
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
			}, "×", 8, nr)]),
			w("div", rr, [
				w("p", ir, [
					t[4] ||= R("将为 ", -1),
					w("strong", ar, S(P(h).length), 1),
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
				}, S(P(m)), 9, or)
			]),
			w("div", sr, [w("button", {
				type: "button",
				class: "jobs-tb-btn",
				id: "btnCancelC2aReimportV2",
				disabled: P(p),
				onClick: t[1] ||= (e) => _()
			}, "取消", 8, cr), w("button", {
				type: "button",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				id: "btnConfirmC2aReimportV2",
				disabled: P(p),
				onClick: t[2] ||= (...e) => P(d).submit && P(d).submit(...e)
			}, S(P(p) ? "正在提交…" : "提交并入队"), 9, lr)])
		], 544)]));
	}
}), dr = ["hidden"], fr = { class: "column-filter-summary-label" }, pr = [
	"data-registration-retry-result",
	"data-registration-retry-task-id",
	"data-registration-retry-run-id",
	"onClick"
], mr = /* @__PURE__ */ n({
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
		}), m = (e) => e.task_id || e.operation_task_id, g = (e) => m(e) || e.job_id;
		function _(e, t, n) {
			o || (i.value = {
				result: c(e),
				context: c(t),
				open: n
			}, ++a.value);
		}
		async function y(e = f.value) {
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
			showResult: _,
			openTasks: y
		}), (e, t) => (r(), C(x, { to: "#accountRegistrationReceiptHost" }, [w("div", {
			id: "accountRegistrationRetryResultV2",
			class: "column-filter-summary account-search-summary",
			role: "status",
			"aria-live": "polite",
			hidden: !i.value
		}, [
			w("span", fr, S(i.value ? p.value : ""), 1),
			f.value.length ? (r(), L("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-tasks": "",
				onClick: t[0] ||= (e) => y()
			}, "打开任务中心")) : h("", !0),
			f.value.length || d.value.length ? (r(), L("details", { key: a.value }, [w("summary", null, "查看" + S(d.value.length ? "任务及跳过原因" : "任务"), 1), w("ul", null, [(r(!0), L(v, null, s(f.value, (e, t) => (r(), L("li", { key: `task-${t}` }, [R("账号 #" + S(e.account_id) + " · " + S(t < l.value.length ? "已创建" : "进行中") + " ", 1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-result": t,
				"data-registration-retry-task-id": m(e) || void 0,
				"data-registration-retry-run-id": m(e) && e.run_id ? e.run_id : void 0,
				onClick: (t) => y([e])
			}, "查看任务" + S(g(e) ? ` #${g(e)}` : ""), 9, pr)]))), 128)), (r(!0), L(v, null, s(d.value, (e, t) => (r(), L("li", { key: `skipped-${t}` }, "账号 #" + S(e.account_id) + " · " + S(e.reason || e.error || "当前不可重跑"), 1))), 128))])])) : h("", !0)
		], 8, dr)]));
	}
}), hr = {
	key: 0,
	class: "ac-operation-receipts",
	open: ""
}, gr = { class: "ac-operation-receipt-list" }, _r = { class: "ac-operation-receipt-row" }, vr = { role: "status" }, yr = ["disabled", "onClick"], br = ["onClick"], xr = {
	key: 0,
	class: "ac-operation-receipt-row"
}, Sr = ["onClick"], Cr = /*#__PURE__*/ F(/* @__PURE__ */ n({
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
		return (t, a) => n.value.length ? (r(), L("details", hr, [w("summary", null, S(n.value.length) + " 次提交需核对回执", 1), w("ul", gr, [(r(!0), L(v, null, s(n.value, (t) => (r(), L("li", { key: t.key }, [w("div", _r, [
			w("strong", null, S(t.label) + " · " + S(t.count) + " 个账号 · " + S(P(i).format(t.submittedAt)), 1),
			w("span", vr, S(t.message), 1),
			w("button", {
				class: "ac-button",
				type: "button",
				disabled: t.loading,
				onClick: (n) => e.receipts.lookup(t.key)
			}, S(t.loading ? "查询中…" : "查询回执"), 9, yr),
			w("button", {
				class: "ac-link",
				type: "button",
				onClick: (n) => e.receipts.dismiss(t.key)
			}, "移除此提示", 8, br)
		]), t.items.length ? (r(), L("div", xr, [(r(!0), L(v, null, s(t.items, (t) => (r(), L("button", {
			key: `${t.task_id}:${t.run_id}`,
			class: "ac-link",
			type: "button",
			onClick: (n) => e.receipts.open(t)
		}, [R(" 任务 #" + S(t.task_id), 1), t.run_id ? (r(), L(v, { key: 0 }, [R(" · 执行 #" + S(t.run_id), 1)], 64)) : h("", !0)], 8, Sr))), 128))])) : h("", !0)]))), 128))])])) : h("", !0);
	}
}), [["__scopeId", "data-v-216648e7"]]), wr = /* @__PURE__ */ n({
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
		toolbarRuntime: {},
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
			let e = a.value?.getActionContext(), t = e ? Object.fromEntries(pe.map((t) => [t.action, n.actions.isPending(t.action, e)])) : {};
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
			f(Nt, {
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
					runtime: e.toolbarRuntime,
					"get-context": () => y().getActionContext(),
					invoke: S,
					notify: w.notify
				}, null, 8, [
					"state",
					"capabilities",
					"runtime",
					"get-context",
					"notify"
				])]),
				feedback: i(() => [e.actions.receipts ? (r(), C(Cr, {
					key: 0,
					receipts: e.actions.receipts
				}, null, 8, ["receipts"])) : h("", !0)]),
				_: 1
			}, 8, [
				"adapter",
				"api",
				"presentation"
			]),
			f(Ut, {
				ref_key: "drawer",
				ref: o,
				api: e.detailApi,
				presentation: e.detailPresentation,
				callbacks: E
			}, null, 8, ["api", "presentation"]),
			f(On, {
				ref_key: "inspection",
				ref: s,
				deps: e.inspectionDependencies
			}, null, 8, ["deps"]),
			f(qn, {
				ref_key: "emailChange",
				ref: c,
				deps: e.emailChangeDependencies
			}, null, 8, ["deps"]),
			f(ur, {
				ref_key: "c2a",
				ref: l,
				deps: e.c2aDependencies
			}, null, 8, ["deps"]),
			f(mr, {
				ref_key: "registrationReceipt",
				ref: d,
				notify: w.notify
			}, null, 8, ["notify"])
		], 64));
	}
});
// src/api/accounts.ts
function Tr(e) {
	return typeof e == "object" && !!e && !Array.isArray(e);
}
function Er(e, t) {
	return typeof e == "number" && Number.isSafeInteger(e) && e >= t;
}
function Dr(e) {
	return Tr(e) && e.ok === !0 && Array.isArray(e.items) && Er(e.total, 0) && Er(e.page, 1) && Er(e.page_size, 1) && Er(e.offset, 0) && Er(e.limit, 1) && typeof e.revision == "string";
}
function Or() {
	throw new le("账号查询返回了无效的响应，请刷新后重试。", 200, "account_response_invalid");
}
function kr(e) {
	return {
		async list(t, n, r, i, a) {
			let o = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			});
			a?.includeFacets === !1 && o.set("include_facets", "0");
			let s = await ce(`/api/accounts?${o}`, { signal: i });
			return Dr(s) && s.compact === !0 && Tr(s.facets) && Array.isArray(s.search_terms) || Or(), s;
		},
		async statuses(t, n, r, i) {
			let a = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			});
			a.set("compact", "1");
			let o = await ce(`/api/accounts/plan-check-status?${a}`, { signal: i });
			return Dr(o) && Tr(o.queue) && Array.isArray(o.status_fields) && o.status_fields.every((e) => typeof e == "string") || Or(), o;
		},
		async planDetails(e, t) {
			if (!/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
			let n = await ce(`/api/accounts/${encodeURIComponent(e)}/plan-details`, { signal: t });
			return Tr(n) && n.ok === !0 && Tr(n.item) && Object.hasOwn(n.item, "account_promotions") && Object.hasOwn(n.item, "promotion_query_snapshot") && Array.isArray(n.item.plan_check_country_results) || Or(), n;
		}
	};
}
// src/api/accountDetail.ts
function Ar() {
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
var jr = "X-Account-Request-Key", Mr = "turb_account_operation_receipts", Nr = /^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/, Pr = 1e4;
function Fr() {
	try {
		let e = JSON.parse(sessionStorage.getItem(Mr) || "[]");
		return Array.isArray(e) ? e.filter((e) => e && typeof e == "object" && typeof e.key == "string" && Nr.test(e.key) && typeof e.label == "string" && Number.isSafeInteger(e.count) && e.count > 0 && Number.isSafeInteger(e.submittedAt) && e.submittedAt > 0) : [];
	} catch {
		return [];
	}
}
function Ir(e) {
	try {
		sessionStorage.setItem(Mr, JSON.stringify(e));
	} catch {}
}
function Lr(e) {
	return {
		...e,
		items: [],
		message: "受理结果未确认，可能已入队。",
		loading: !1
	};
}
function Rr(t, n) {
	let r = j(Fr().map(Lr)), i = (e, t) => {
		r.value = r.value.map((n) => n.key === e ? {
			...n,
			...t
		} : n);
	};
	function a(e) {
		r.value = r.value.filter((t) => t.key !== e), Ir(Fr().filter((t) => t.key !== e));
	}
	async function o(e, n, i) {
		let o = crypto.randomUUID?.() ?? Array.from(crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(16)), (e) => e.toString(16).padStart(2, "0")).join(""), s = {
			key: o,
			label: e,
			count: n,
			submittedAt: t.now().getTime()
		};
		Ir([s, ...Fr()]);
		let c;
		try {
			let e = new Promise((e, t) => {
				c = setTimeout(() => t(/* @__PURE__ */ Error("等待受理超时")), Pr);
			}), t = await Promise.race([i(o), e]);
			return a(o), t;
		} catch (n) {
			if (n instanceof le && (n.unavailableFeature || n.status >= 400 && n.status < 500 && n.status !== 408)) throw a(o), n;
			r.value = [Lr(s), ...r.value];
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
					headers: { [jr]: e }
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
var zr = {
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
}, Br = {
	plan: "查套餐",
	live: "查活",
	token: "刷新 AT",
	mail: "封号邮件扫描"
}, Vr = (e) => Object.prototype.hasOwnProperty.call(zr, e), Hr = (e) => e instanceof Error ? e.message : "请求失败，请稍后重试。";
function Ur(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Wr(e) {
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
function Gr(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return [...new Set(e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	}))];
}
function Kr(e) {
	return Array.isArray(e) ? Object.freeze(e.map(Kr)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, Kr(t)]))) : e;
}
function qr(e, t) {
	return Kr({
		accountIds: t.map(String),
		expectedEmails: { ...e.expectedEmails },
		querySnapshot: e.querySnapshot,
		archived: e.archived,
		rowHints: []
	});
}
function Jr(e) {
	let t = [...Wr(e.skipped), ...Wr(e.failed)].map((e) => String(e.reason || e.error || "").replace(/\s+/g, " ").trim()).filter(Boolean);
	return t.length ? `；${t.slice(0, 3).map((e) => e.length > 80 ? `${e.slice(0, 80)}…` : e).join("；")}${t.length > 3 ? `；另有 ${t.length - 3} 条原因` : ""}` : "";
}
function Yr(e) {
	let t = Array.isArray(e) ? e.filter((e) => e && typeof e == "object") : [], n = (e) => t.find((t) => t.key === e), r = n("ACCOUNT_AT_REFRESH_DRIVER"), i = String(r?.value || "protocol").trim().toLowerCase() === "browser_roxy" ? "browser_roxy" : "protocol", a = n("ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED")?.value, o = a === !0 || String(a).trim().toLowerCase() === "true", s = String(n("OPENAI_PROTOCOL_VERSION")?.value || "v1").trim().toLowerCase(), c = ["v2", "v3"].includes(s) ? s : "v1", l = r ? i === "browser_roxy" ? "Roxy 指纹浏览器" : `协议刷新（${c}）` : "已保存的刷新驱动";
	return {
		description: i === "protocol" && c === "v3" ? `使用${l}先复用该账号有效的登录会话；会话失效或尚未保存时，按实际挑战完成密码、2FA 或邮箱验证，核对账号身份并保存最新 accessToken。` : `使用${l}重新登录，按实际挑战完成密码、2FA 或邮箱验证，并保存最新 accessToken。`,
		debugDescription: o ? "Roxy 刷新调试已开启：实际使用 Roxy 时将显示浏览器并全程抓包；失败保留窗口，可从任务日志查看现场并下载 HAR。" : ""
	};
}
function Xr(e) {
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
function Zr(e, t) {
	let n = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), i = Rr(e, t.openReceiptTask ?? t.openAccountTaskLog), a, o = !0, s = !1, c = 0, l = (e, t) => zr[e]?.single ? JSON.stringify([e, ...t.map(String)]) : e, u = (e) => !s && o && e === c && t.isOwnerActive();
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
			n() && e.notify(`请求已处理，但页面更新失败: ${Hr(t)}`);
		}
	}
	async function h(r, a, d = null) {
		if (!Vr(r)) throw Error(`未支持的账号动作：${r}`);
		if (s || !o || e.canInvoke?.(r, d) === !1) return;
		let f = zr[r], h, g, _ = c, v = () => u(_);
		try {
			let o = Gr(a);
			if (!o.length) {
				e.notify("请先选择账号");
				return;
			}
			if (f.single && o.length !== 1) throw Error("此操作只能选择一个账号");
			if (h = l(r, o), n.has(h)) {
				h = void 0;
				return;
			}
			n.add(h);
			let s = qr(a, o), c = (t) => {
				g = e.beginBusy?.(r, d, t) || void 0;
			}, u = async (t, n, r) => {
				let i = {}, a = { method: "POST" };
				r && (i[jr] = r), n !== void 0 && (i["Content-Type"] = "application/json", a.body = JSON.stringify(n)), (r || n !== void 0) && (a.headers = i);
				let o = Ur(await e.request(t, a));
				if (r && o.ok !== !0) throw Error("服务端响应格式无效");
				return o;
			}, y = (e, t, n) => i.submit(Br[e], o.length, (e) => u(t, n, e));
			if (f.kind === "plan") {
				c("查询中…");
				let n;
				try {
					n = await y("plan", f.single ? "/api/accounts/check-plan" : "/api/accounts/check-plan-bulk", f.single ? { account_id: o[0] } : { account_ids: o });
				} catch (n) {
					e.notify(f.error + Hr(n)), f.single && v() && t.pollStatuses(s).catch((t) => {
						v() && e.notify(`套餐状态读取失败: ${Hr(t)}`);
					});
					return;
				}
				if (!n) return;
				e.notify(f.single ? String(n.message || "套餐查询已加入后台队列") : `已入队 ${Q(n.started_count)} 个，查询中跳过 ${Q(n.busy_count)} 个，入队失败 ${Q(n.failed_count)} 个${Wr(n.skipped).length ? `，跳过 ${Wr(n.skipped).length} 个` : ""}${Jr(n)}`), m(() => t.pollStatuses(s), v);
			} else if (f.kind === "live") {
				let n = t.operationWorkers(), r = f.single ? "确定查活这个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。" : `确定查活选中的 ${o.length} 个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。\n\n并发线程数：${n}`;
				if (!await e.confirm(r)) return;
				c("查活中…");
				let i = await y("live", "/api/accounts/check-live-bulk", {
					account_ids: o,
					driver: t.configuredLiveCheckDriver()
				});
				if (!i) return;
				let a = Wr(i.skipped).length, l = Wr(i.started);
				e.notify(`查活已入队 ${Q(i.started_count)} 个，忙碌 ${Q(i.busy_count)} 个，失败 ${Q(i.failed_count)}${a ? `，跳过 ${a}` : ""}（配置驱动：${t.configuredLiveCheckDriver() || "默认"}，实际驱动：${i.live_check_driver || "未知"}）${Jr(i)}`), l[0]?.email && m(() => t.openLiveLog(String(l[0].email)), v), m(() => t.refresh(s), v), m(() => t.refreshSummary(), v);
			} else if (f.kind === "token") {
				let n = t.operationWorkers(), i = t.fallbackConfig(), a = Array.isArray(i) && i.some((e) => e?.key === "ACCOUNT_AT_REFRESH_DRIVER");
				if (c(a ? "刷新 AT…" : "读取配置…"), !a) try {
					i = await t.readConfig();
				} catch {
					i = t.fallbackConfig();
				}
				let l = Yr(i), u = o.length === 1 ? "这个账号" : `选中的 ${o.length} 个账号`;
				if (!await e.confirm(`确定刷新${u}的 AT 吗？\n\n${l.description}${l.debugDescription ? `\n\n${l.debugDescription}` : ""}${o.length > 1 ? `\n\n并发线程数：${n}` : ""}`)) return;
				t.updateBusyLabel?.(r, d, "刷新中…");
				let f = await y("token", "/api/accounts/refresh-token-bulk", { account_ids: o });
				if (!f) return;
				let p = Wr(f.skipped).length, h = Wr(f.started)[0];
				e.notify(`刷新AT已入队 ${Q(f.started_count)} 个，忙碌 ${Q(f.busy_count)} 个，失败 ${Q(f.failed_count)}${p ? `，跳过 ${p}` : ""}${Jr(f)}`), h?.task_id ? m(() => t.openAccountTaskLog(ue(h.task_id), de(h.run_id)), v) : h?.email && m(() => t.openLiveLog(String(h.email)), v), m(() => t.refresh(s), v), m(() => t.refreshSummary(), v);
			} else if (f.kind === "mail") {
				c("扫描中…");
				let t = await y("mail", f.single ? `/api/accounts/${o[0]}/check-deactivation-mail` : "/api/accounts/check-deactivation-mail-bulk", f.single ? void 0 : { account_ids: o });
				if (!t) return;
				e.notify(f.single ? "封号邮件扫描已入队；不会刷新 AT" : `已入队 ${Q(t.started_count)} 个，跳过 ${Q(t.skipped_count)} 个；不会刷新 AT`), m(() => p(f.single || Q(t.started_count) > 0 ? o : [], s, _), v);
			} else if (f.kind === "extract") {
				if (f.single) {
					let t = a.rowHints.find((e) => String(e.id) === String(o[0]));
					if (!t) {
						e.notify("账号不存在");
						return;
					}
					if (String(t.current_plan_type || t.plan_type || "").toLowerCase() !== "free" || Xr(t) !== "free_trial") {
						e.notify("仅支持已确认 Plus 免费试用资格的 free 账号提链；折扣优惠不支持");
						return;
					}
					if (!await e.confirm(`确定为该账号提链吗？\n\n${t.email || "#" + o[0]}\n\n提链类型按配置使用，成功会消耗 1 次 CDK。`)) return;
				} else if (!await e.confirm(`确定为选中的 ${o.length} 个账号批量提链吗？\n\n仅处理已确认的 Plus 免费试用账号，折扣优惠和历史待复查账号会自动跳过。成功会按账号消耗 CDK 次数。`)) return;
				c("提链中…");
				let n = await u(f.single ? "/api/accounts/extract-link" : "/api/accounts/extract-link-bulk", f.single ? { account_id: o[0] } : { account_ids: o });
				if (f.single) {
					let t = n.fallback_from && n.link_type ? `；${String(n.fallback_from).toUpperCase()} 已失败，改用 ${String(n.link_type).toUpperCase()}` : "";
					e.notify(`提炼任务已入队${n.task_id ? ` · 任务 #${n.task_id}` : ""}${t}，可在任务中心查看日志`);
				} else {
					let t = Q(n.skipped_count) + Q(n.busy_count) + Q(n.failed_count), r = Wr(n.started).filter((e) => e.fallback_from).length;
					e.notify(`已入队 ${Q(n.started_count)} 个${t ? `，跳过/失败 ${t} 个` : ""}${r ? `，其中 ${r} 个已自动跳过失败类型` : ""}`);
				}
				await m(async () => {
					await t.reloadTasks(), await t.pollStatuses(s);
				});
			}
		} catch (t) {
			e.notify(f.error + Hr(t));
		} finally {
			h && n.delete(h), g?.();
		}
	}
	return {
		isSupported: Vr,
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
var Qr = {
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
}, $r = {
	addPasswordSelectedAccounts: "password",
	addTwofaSelectedAccounts: "twofa",
	changePasswordSelectedAccounts: "password_change",
	changeTwofaSelectedAccounts: "twofa_change",
	completeSelectedAccounts: "complete"
}, ei = /* @__PURE__ */ new Set([
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
]), ti = (e, t) => Object.prototype.hasOwnProperty.call(e, t);
function ni(e) {
	let t = e.indexOf(":");
	return t < 0 ? {
		name: e,
		value: ""
	} : {
		name: e.slice(0, t),
		value: e.slice(t + 1)
	};
}
function ri(e) {
	let { name: t, value: n } = ni(e);
	return t === "account-action" ? ti(Qr, n) : t === "account-registration-task" ? /^[1-9]\d*$/.test(n) && Number.isSafeInteger(Number(n)) : !e.includes(":") && (ei.has(t) || ti($r, t));
}
function ii(e, t = !1) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let n = e;
	if (t && n.ok === !1) throw Error(typeof n.error == "string" ? n.error : "请求失败");
	return n;
}
function ai(e) {
	if (e == null) return [];
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return e.map((e) => ii(e));
}
function $(e) {
	let t = Number(e || 0);
	if (!Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function oi(e) {
	return Array.isArray(e) ? Object.freeze(e.map(oi)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, oi(t)]))) : e;
}
function si(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return oi({
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
function ci(e) {
	let t = ai(e.started), n = ai(e.reused), r = ai(e.skipped);
	return oi({
		started: t,
		reused: n,
		skipped: r,
		started_count: $(e.started_count ?? t.length),
		reused_count: $(e.reused_count ?? n.length),
		skipped_count: $(e.skipped_count ?? r.length)
	});
}
function li(e) {
	return `注册重跑：已创建 ${e.started_count} 个，进行中 ${e.reused_count} 个，跳过 ${e.skipped_count} 个`;
}
var ui = (e) => e instanceof Error ? e.message : "请求失败，请稍后重试。", di = (e) => e === "account-registration-retry" || e === "retryAccountRegistration", fi = (e) => e.startsWith("account-") || e.startsWith("codex-");
function pi(e, t) {
	let n = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), i = (e, t) => fi(ni(e).name) ? JSON.stringify([e, ...t]) : e;
	async function a(e, n) {
		let r = e.length === 1 ? e[0] : void 0, i = r && n.rowHints.find((e) => String(e.id) === String(r.account_id)), a = r?.task_id || r?.operation_task_id;
		await t.openTasks({
			filters: { target: r?.email || i?.email || (r ? n.expectedEmails[String(r.account_id)] : "") || "" },
			taskId: a ? Number(a) : void 0,
			runId: r?.run_id ? Number(r.run_id) : null
		}), !a && r?.job_id && await t.openLog(Number(r.job_id));
	}
	async function o(t) {
		try {
			await t();
		} catch (t) {
			e.notify(`请求已处理，但页面更新失败: ${ui(t)}`);
		}
	}
	function s(e, n) {
		n && o(async () => t.openTasks(n)), o(() => t.refresh(e));
	}
	async function c(c, l, u = null) {
		if (!ri(c)) throw Error(`未支持的账号动作：${ni(c).name}`);
		if (e.canInvoke?.(c, u) === !1) return;
		let { name: d, value: f } = ni(c), p = d === "account-action" ? f : ti($r, d) ? $r[d] : void 0, m = p ? Qr[p] : void 0, h, g, _ = [], v = !1, y = m ? `${m.label}失败: ` : d.includes("setup") || d === "setupSelectedAccounts" ? "补齐账号配置失败: " : d === "codex-stop" ? "停止失败: " : d === "codex-reset-retrying" ? "重置失败: " : d === "codex-retry" ? "触发补跑失败: " : d === "stopSelectedCodex" ? "停止选中补跑失败: " : d === "retrySelectedCodex" ? "批量补跑失败: " : d === "uploadSelectedCodexSub2" ? "批量上传 sub2 失败: " : "注册重跑提交失败: ";
		try {
			let y = si(l), b = y.accountIds.map(Number), x = b[0];
			if (!b.length) {
				e.notify("请先选择账号");
				return;
			}
			if (fi(d) && b.length !== 1) throw Error("此操作只能选择一个账号");
			let S = y.rowHints.find((e) => String(e.id) === String(x)), C = y.expectedEmails[String(x)] || S?.email || "", w = S?.email || C || `账号 #${x}`;
			if (d === "account-registration-task") {
				await a([{
					account_id: x,
					email: C,
					job_id: Number(f)
				}], y);
				return;
			}
			if (di(d) && y.accountIds.some((e) => r.has(e))) {
				e.notify("所选账号的注册重跑正在提交，请稍后查看结果");
				return;
			}
			if (h = i(c, y.accountIds), n.has(h)) {
				h = void 0;
				return;
			}
			if (n.add(h), di(d) && (_ = y.accountIds, _.forEach((e) => r.add(e))), p && !fi(d) && ["password_change", "twofa_change"].includes(p) && b.length > 20) {
				e.notify("修改密码或修改 2FA 单次最多操作 20 个账号");
				return;
			}
			let T;
			if (T = d === "account-setup" ? `补齐账号配置？\n\n${w}\n\n只执行账号密码、套餐查询和 Authenticator 2FA，不执行 Codex 授权。` : d === "setupSelectedAccounts" ? `确定补齐选中的 ${b.length} 个账号配置吗？\n\n只执行：账号密码、套餐查询、Authenticator 2FA。\n不会执行 Codex 授权。` : m ? fi(d) ? `${m.label}？\n\n${w}` : `确定${m.label}选中的 ${b.length} 个账号吗？` : d === "codex-stop" ? `确定停止该账号的 Codex 补跑吗？\n\n${C}\n\n会发送停止信号并将状态标记为“已停止”。` : d === "codex-reset-retrying" ? `确定重置该账号的 Codex「补跑中」状态吗？\n\n${C}\n\n重置后状态会变为“失败”，可再次点击“补跑 Codex”。` : d === "codex-retry" ? `重新跑 Codex 授权？\n\n${C}\n\n按实际验证要求使用邮箱 OTP（自动收）。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑会在后台进行，完成后状态自动更新。` : d === "stopSelectedCodex" ? `确定停止选中的 ${b.length} 个账号的 Codex 补跑吗？\n\n会向正在补跑的任务发送停止信号，并将状态标记为“已停止”；未在补跑的账号会自动跳过。` : d === "retrySelectedCodex" ? `批量补跑选中的 ${b.length} 个账号 Codex 授权？\n\n并发线程数：${t.operationWorkers()}\n\n按实际验证要求使用邮箱 OTP。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑中和已废号账号会自动跳过。` : d === "uploadSelectedCodexSub2" ? `确定上传选中的 ${b.length} 个账号的 Codex OAuth 凭证到 sub2api 吗？\n\n未完成 Codex OAuth 的账号会自动跳过。` : `确定为${b.length === 1 ? `账号 #${x}` : `选中的 ${b.length} 个账号`}${b.length === 1 && S?.registration_retry?.label || "重跑原注册任务"}吗？\n\n复用原注册记录，按当前进度重跑或补齐缺失步骤。正在执行、已完成或没有原任务的账号会显示对应结果。`, !await e.confirm(T)) return;
			g = e.beginBusy?.(c, u, di(d) ? "提交中…" : d === "uploadSelectedCodexSub2" ? "提交上传…" : void 0) || void 0;
			let E = async (t, n) => {
				let r = ii(await e.request(t, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(n)
				}), !0);
				return v = !0, r;
			};
			if (d === "account-setup" || d === "setupSelectedAccounts") {
				let t = d === "account-setup", n = await E(t ? `/api/accounts/${x}/setup` : "/api/accounts/setup-bulk", t ? {} : { account_ids: b }), r = ai(n.skipped).length;
				e.notify(t ? String(n.message || "已开始补齐账号配置") : r ? `已开始补齐 ${$(n.started_count)} 个，跳过 ${r} 个` : `已开始补齐 ${$(n.started_count)} 个账号配置`), s(y, { filters: {
					target: t ? w : "",
					type: "account_setup_retry"
				} });
			} else if (p && m) {
				let t = d === "account-action", n = await E(t ? `/api/accounts/${x}/action` : "/api/accounts/action-bulk", t ? { action: p } : {
					account_ids: b,
					action: p
				}), r = ai(n.skipped).length, i = ai(n.started);
				e.notify(t ? String(n.message || `${m.label}已入队`) : r ? `已开始 ${$(n.started_count)} 个，跳过 ${r} 个` : String(n.message || `${m.label}已入队`));
				let a = t ? !!n.registration_resume : i.length > 0 && i.every((e) => e.registration_resume);
				s(y, { filters: t ? {
					target: w,
					type: a ? "registration_resume" : m.type
				} : { type: a ? "registration_resume" : m.type } });
			} else if (d.startsWith("codex-")) {
				let t = await E(`/api/codex/${d === "codex-stop" ? "stop" : d === "codex-reset-retrying" ? "reset-retrying" : "retry"}`, d === "codex-reset-retrying" ? {
					email: C,
					status: "failed"
				} : { email: C });
				e.notify(String(t.message || (d === "codex-stop" ? "已发送停止信号" : d === "codex-reset-retrying" ? "已重置补跑状态" : "已开始补跑"))), s(y, d === "codex-retry" ? { filters: {
					target: C,
					type: "codex_retry"
				} } : void 0);
			} else if (d === "stopSelectedCodex" || d === "retrySelectedCodex") {
				let t = d === "stopSelectedCodex", n = await E(`/api/codex/${t ? "stop" : "retry"}-bulk`, { account_ids: b }), r = ai(n.skipped).length;
				e.notify(t ? `已停止 ${$(n.stopped_count)} 个${r ? `，跳过 ${r} 个` : ""}` : r ? `已开始 ${$(n.started_count)} 个，跳过 ${r} 个` : String(n.message || "已开始批量补跑")), s(y, t ? void 0 : { filters: {
					target: "",
					type: "codex_retry"
				} });
			} else if (d === "uploadSelectedCodexSub2") {
				let n = await E("/api/accounts/codex/upload-sub2-bulk", { account_ids: b }), r = $(n.skipped_count ?? ai(n.skipped).length) + $(n.failed_count ?? ai(n.failed).length), i = r ? Qn(n) : "";
				n.accepted ? e.notify(`手动上传已入队 ${$(n.queued_count ?? ai(n.queued).length)} 个，未入队 ${r} 个，请在任务中心查看结果${i}`) : (e.notify(`已上传 ${$(n.uploaded_count)} 个${r ? `，跳过/失败 ${r} 个${i}` : ""}`), await o(() => t.pollStatuses(y)));
			} else if (di(d)) {
				let n = ci(await E(b.length === 1 ? `/api/accounts/${x}/registration-retry` : "/api/accounts/registration-retry-bulk", b.length === 1 ? {} : { account_ids: b }));
				if (e.notify(li(n)), t.showRegistrationResult(n, y, (e) => a(e, y)), b.length === 1) {
					let e = n.started[0] || n.reused[0];
					e && await a([e], y);
				}
				await t.refresh(y);
			}
		} catch (t) {
			v && (y = di(d) ? "注册重跑请求已处理，页面更新失败: " : "请求已处理，但页面更新失败: "), e.notify(y + ui(t));
		} finally {
			h && n.delete(h), _.forEach((e) => r.delete(e)), g?.();
		}
	}
	return {
		isSupported: ri,
		invoke: c,
		isPending: (e, t) => di(ni(e).name) ? t.accountIds.some((e) => r.has(e)) : n.has(i(e, t.accountIds))
	};
}
// src/features/accounts/localMutations.ts
var mi = (e) => e === "only" ? "已归档账号" : e === "all" ? "全部账号" : "未归档账号", hi = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败，请稍后重试。";
function gi(e) {
	let t = e.indexOf(":");
	return {
		name: t < 0 ? e : e.slice(0, t),
		value: t < 0 ? void 0 : e.slice(t + 1)
	};
}
function _i(e) {
	let { name: t, value: n } = gi(e);
	return ["account-archive", "account-email-invalid"].includes(t) ? n === "0" || n === "1" : t === "setAccountsEmailInvalid" ? n === void 0 || n === "0" || n === "1" : n === void 0 && [
		"account-delete",
		"account-restore",
		"archiveSelectedAccounts",
		"deleteSelectedAccounts",
		"deleteDeactivatedAccounts"
	].includes(t);
}
function vi(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function yi(e) {
	let t = Number(e);
	if (e == null || e === "" || typeof e == "boolean" || !Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function bi(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return [...new Set(e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	}))];
}
function xi(e, t) {
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return [...new Set(e.map((e) => vi(e).id).filter((e) => (typeof e == "number" || typeof e == "string") && t.includes(Number(e))).map(String))];
}
function Si(e) {
	let t = /* @__PURE__ */ new Set(), n = (e, t) => e.startsWith("account-") ? JSON.stringify([e, ...t.accountIds]) : gi(e).name;
	async function r(t, n, r = !1) {
		let i = r ? new AbortController() : void 0, a = i ? setTimeout(() => i.abort(), 3e4) : void 0;
		try {
			return vi(await e.request(t, {
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
		i && e.notify(`${r ? "操作已处理，" : ""}页面刷新失败: ${hi(i.reason)}`);
	}
	async function a(a, o, s = null) {
		if (!_i(a)) throw Error(`未支持的账号动作：${gi(a).name}`);
		if (e.canInvoke?.(a, s) === !1) return;
		let { name: c, value: l } = gi(a), u = c === "deleteDeactivatedAccounts", d = c === "account-email-invalid" || c === "setAccountsEmailInvalid", f, p, m = !1, h = !1, g = !1, _ = u ? "删除请求失败，请刷新核实：" : d ? "更新邮箱失效标记失败: " : c === "account-restore" ? "恢复账号失败: " : c === "deleteSelectedAccounts" ? "批量删除失败: " : "删除失败: ";
		try {
			let i = u ? [] : bi(o), v = o.archived;
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
				}), d = yi(u.updated_count), f = Array.isArray(u.skipped) ? u.skipped.length : 0;
				h = !0, e.notify(`${n ? "已标记邮箱失效" : "已清除本地邮箱失效标记"} ${d} 个${f ? `，跳过 ${f} 个（邮箱可能已变更）` : ""}`);
			} else if (u) {
				if (![
					"0",
					"only",
					"all"
				].includes(v)) throw Error("归档范围无效");
				if (!await e.confirm(`确定删除「${mi(v)}」范围内全部已废账号？\n\n不限当前页，不受勾选、搜索或其他筛选影响。仅删除本地账号记录，保留邮箱池和巡检历史。此操作不可撤销。`)) return;
				p = e.beginBusy?.(a, s) || void 0, m = !0, g = !0;
				let t = yi((await r("/api/accounts/delete-deactivated", { archived: v }, !0)).deleted_count);
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
					S = xi(b[t ? "updated" : "deleted"], i);
					let e = yi(b[t ? "updated_count" : "deleted_count"]), n = Array.isArray(b.skipped) ? b.skipped.length : 0;
					C = `已${d} ${e} 个${n ? `，跳过 ${n} 个` : ""}`;
				} else {
					if (b[t ? "updated" : "deleted"] !== !0 || (t || b.id !== void 0) && String(b.id) !== String(y)) throw Error("服务端未确认账号操作结果");
					S = [String(y)], C = t ? u ? "账号已归档" : "账号已恢复" : "账号已删除";
				}
				h = !0, g = !0, S.length && e.removeAcknowledgedSelection(S, o), e.notify(C);
			}
		} catch (t) {
			e.notify(`${h ? "操作已处理，页面更新失败: " : _}${hi(t)}`);
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
		isSupported: _i,
		invoke: a,
		isPending: (e, r) => t.has(n(e, r))
	};
}
// src/features/accounts/actions.ts
var Ci = {
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
}, wi = {
	copy_line: "账号整行已复制",
	chatgpt_session: "ChatGPT session 已复制",
	account_password: "账号密码已复制",
	totp_secret: "TOTP 密钥已复制",
	access_token: "Token 已复制"
}, Ti = {
	downloadSelectedAccountTxt: "生成 TXT 失败: ",
	downloadSelectedAccountSessions: "下载 Session 失败: ",
	downloadSelectedCpa: "下载 CPA 失败: "
}, Ei = (e, t) => Object.prototype.hasOwnProperty.call(e, t);
function Di(e) {
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
function Oi(e) {
	let { name: t, value: n, hasValue: r } = Di(e);
	return t === "account-copy-secret" ? r && Ei(wi, n) : !r && (t === "account-totp-copy" || Ei(Ci, t) || Ei(Ti, t));
}
function ki(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Ai(e) {
	if (!e) return "";
	if (typeof e != "string") throw Error("服务端响应格式无效");
	return e;
}
function ji(e) {
	let t = Number(e || 0);
	if (!Number.isFinite(t) || !Number.isInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function Mi(e) {
	if (e.download_url == null || e.download_url === "") throw Error("服务端未返回下载地址");
	if (typeof e.download_url != "string" || e.filename != null && typeof e.filename != "string") throw Error("服务端响应格式无效");
	if (!e.download_url.trim()) throw Error("服务端未返回下载地址");
	return {
		url: e.download_url,
		filename: e.filename || ""
	};
}
function Ni(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	let t = e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	});
	return Object.freeze([...new Set(t)]);
}
function Pi(e) {
	return e instanceof Error ? e.message : "请求失败，请稍后重试。";
}
function Fi(e) {
	let t = e.queued ? Zr(e, e.queued) : void 0, n = e.setup ? pi(e, e.setup) : void 0, r = e.local ? Si({
		...e.local,
		request: e.request,
		notify: e.notify,
		confirm: e.confirm,
		canInvoke: e.canInvoke,
		beginBusy: e.beginBusy
	}) : void 0, i = /* @__PURE__ */ new Set(), a = (e, t) => e.startsWith("account-") ? JSON.stringify([e, ...t.map(String)]) : e, o = async (t, n) => ki(await e.request(t, {
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
		return n.values.map((e) => Ai(ki(e).value)).filter(Boolean);
	}
	async function c(c, l, u = null) {
		if (t?.isSupported(c)) return t.invoke(c, l, u);
		if (n?.isSupported(c)) return n.invoke(c, l, u);
		if (r?.isSupported(c)) return r.invoke(c, l, u);
		if (!Oi(c)) throw Error(`未支持的账号动作：${Di(c).name}`);
		if (e.canInvoke?.(c, u) === !1) return;
		let { name: d, value: f } = Di(c), p = Ei(Ci, d) ? Ci[d] : void 0, m = p?.error ?? Ti[d] ?? (d === "account-totp-copy" ? "复制验证码失败: " : "复制失败: "), h, g, _ = !1, v = () => {
			h && i.delete(h);
			let e = g;
			g = void 0, e?.();
		};
		try {
			let t = Ni(l);
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
				let n = Ai(ki(await e.request(`/api/accounts/${t[0]}/secret?field=${encodeURIComponent(f)}`)).value);
				if (!n) {
					e.notify("可复制内容为空");
					return;
				}
				await e.clipboard(n), e.notify(wi[f]);
			} else if (d === "account-totp-copy") {
				let n = ki(await e.request(`/api/accounts/${t[0]}/totp-code`)), r = Ai(n.code);
				if (!r) throw Error("验证码为空");
				let i = ji(n.remaining_seconds), a = await e.clipboard(r, !1);
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
				}), { url: r, filename: i } = Mi(n), a = ji(n.added_count), s = ji(n.skipped_count);
				await e.downloadUrl(r, i), e.notify(a === 0 ? `没有可下载的 Session，已生成结果清单，跳过 ${s} 个；开始下载，分类原因见 ZIP 内 manifest.json；Session 缺失或无效的账号请先刷新 AT，读取失败的账号请重试` : `已打包 ${a} 个账号 Session，跳过 ${s} 个；开始下载，结果见 ZIP 内 manifest.json`);
			} else if (d === "downloadSelectedCpa") {
				let n = await o("/api/accounts/download-cpa-bulk", {
					account_ids: t,
					prepare: !0
				}), { url: r, filename: i } = Mi(n), a = ji(n.error_count);
				await e.downloadUrl(r, i), e.notify(`已生成 ZIP，开始下载${a ? `（${a} 个失败见 manifest）` : ""}`), e.schedule(() => {
					Promise.resolve().then(() => e.reloadCodex()).catch((t) => e.notify(`下载已开始，但 Codex 列表刷新失败: ${Pi(t)}`));
				}, 1200);
			}
		} catch (t) {
			e.notify(m + Pi(t));
		} finally {
			_ ? e.schedule(v, 1200) : v();
		}
	}
	return {
		isSupported: (e) => Oi(e) || t?.isSupported(e) === !0 || n?.isSupported(e) === !0 || r?.isSupported(e) === !0,
		invoke: c,
		isPending: (e, o) => i.has(a(e, o.accountIds)) || t?.isPending(e, o) === !0 || n?.isPending(e, o) === !0 || r?.isPending(e, o) === !0,
		receipts: t?.receipts,
		setVisible: (e) => t?.setVisible(e),
		dispose: () => t?.dispose()
	};
}
// src/features/accounts/browserDownloads.ts
function Ii(e) {
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
function Li(e, t) {
	let n = re(t.query), r = Ii({
		document,
		origin: window.location.origin,
		urls: URL,
		schedule: (e, t) => setTimeout(e, t)
	}), i = Fi({
		...t.actionDependencies,
		request: ce,
		...r,
		now: () => /* @__PURE__ */ new Date(),
		schedule: (e, t) => setTimeout(e, t)
	}), a = {
		storage: {
			getItem: (e) => window.localStorage.getItem(e),
			setItem: (e, t) => window.localStorage.setItem(e, t)
		},
		requestFrame: (e) => requestAnimationFrame(e),
		cancelFrame: (e) => cancelAnimationFrame(e),
		addStorageListener: (e) => (window.addEventListener("storage", e), () => window.removeEventListener("storage", e))
	};
	return A(wr, {
		adapter: n,
		api: kr(n),
		presentation: Ve(t.presentation),
		callbacks: t.callbacks,
		detailApi: Ar(),
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
		initialCapabilities: t.capabilities,
		toolbarRuntime: a
	}).mount(e);
}
export { Li as mountAccounts };
