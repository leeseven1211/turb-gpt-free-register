import { $ as e, A as t, C as n, F as r, G as i, H as a, K as o, L as s, M as c, N as l, P as u, R as d, S as f, X as p, Z as m, _ as h, a as g, c as _, d as v, dt as y, et as b, f as x, ft as S, g as C, h as w, j as T, l as E, lt as D, m as O, n as k, nt as A, o as j, s as M, st as N, t as P, tt as F, v as I, x as L } from "./_plugin-vue_export-helper-CtnyMOwL.js";
import { a as R, i as z, n as B, o as V, r as H, s as U, t as W } from "./ListFilterSummary-wgXrzXbr.js";
import { t as G } from "./ListPagination-CrkNIuCM.js";
import { a as K, c as q, i as J, n as Y, r as X, s as ee, t as te } from "./queryAdapter-BuJS1py0.js";
import { t as ne } from "./useColumnWidths-DZSfaGuI.js";
import { t as re } from "./errorLabels-B-XqaTSM.js";
import { n as ie, r as Z, t as ae } from "./client-BBEPwkQG.js";
// src/features/accounts/accountToolbar.ts
var oe = Object.freeze([
	"操作",
	"批次与巡检",
	"复制与导出",
	"资产管理"
]), se = Object.freeze([
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
]), ce = "turb_account_action_usage_v1", le = Object.freeze([
	"btnCheckSelectedLiveV2",
	"btnCheckSelectedPlansV2",
	"btnRefreshSelectedTokenV2",
	"btnExtractSelectedLinksV2",
	"btnAddTwofaSelectedAccountsV2"
]);
function ue(e, t) {
	let n = [...le, ...e.filter((e) => !le.includes(e))];
	return [...e].sort((e, r) => (t[r] || 0) - (t[e] || 0) || n.indexOf(e) - n.indexOf(r)).slice(0, 5);
}
function de(t, n, r) {
	let i = A({}), a = A(ue(t, {})), o, s = !1;
	function c() {
		let e = i.value;
		try {
			let t = n.storage.getItem(ce);
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
		let e = ue(t, i.value);
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
			n.storage.setItem(ce, JSON.stringify(r));
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
var fe = {
	class: "accounts-command-deck",
	id: "accountsCommandDeck"
}, pe = {
	class: "list-selection-hint",
	id: "accountsSelectedHintV2"
}, me = { class: "toolbar-overflow-menu" }, he = { class: "toolbar-overflow-section-title" }, ge = {
	class: "acc-v2-btn-group account-quick-actions",
	id: "accountsQuickActionsV2",
	role: "group",
	"aria-label": "常用账号操作，按此浏览器使用次数排序",
	title: "显示此浏览器使用次数最多的五项操作，批量操作一次算一次"
}, _e = [
	"id",
	"disabled",
	"title",
	"data-feature",
	"data-feature-base-title",
	"aria-disabled",
	"onClick"
], ve = /*#__PURE__*/ P(/* @__PURE__ */ n({
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
		let n = e, i = b(), a = b(), o = b(!1), l = /* @__PURE__ */ new Map(), u = /* @__PURE__ */ new Map(), d = A(/* @__PURE__ */ new Set()), f = de(se.map((e) => e.id), n.runtime, () => {
			let e = i.value, t = e?.ownerDocument;
			return !!(a.value?.open || t?.querySelector("dialog[open]") || e?.contains(t?.activeElement ?? null));
		});
		function p(e, t, n) {
			let r = e;
			n && typeof n == "object" && "nodeType" in n ? r.set(t, n) : r.delete(t);
		}
		function m(e) {
			let t = f.quickIds.value.indexOf(e.id);
			return t >= 0 ? u.get(t) : l.get(e.id);
		}
		let g = (e) => e.feature ? n.capabilities[e.feature] : void 0, _ = (e) => g(e)?.enabled === !1, y = (e) => e.selection && n.state.selectedCount === 0 || d.value.has(e.action) || !!n.state.pending?.[e.action], E = (e) => n.state.labels?.[e.action] || (e.id === "btnArchiveSelectedAccountsV2" && n.state.archived ? "恢复选中" : e.label), O = (e) => e.id === "btnArchiveSelectedAccountsV2" && n.state.archived ? "把选中的归档账号恢复到默认账号列表" : e.title, k = (e) => _(e) ? `不可用：${g(e)?.reason || "缺少必要配置"}` : O(e);
		async function j(e, t) {
			let r = t.currentTarget;
			if (!(y(e) || _(e) || r.disabled || r.getAttribute("aria-disabled") === "true")) {
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
		let M;
		return c(() => {
			M = i.value?.ownerDocument, M?.addEventListener("close", f.schedule, !0), o.value = !0, f.refresh();
		}), T(() => M?.removeEventListener("close", f.schedule, !0)), t({ refreshQuickActions: f.refresh }), (t, n) => (r(), I("div", fe, [w("div", {
			ref_key: "toolbar",
			ref: i,
			class: D(["jobs-toolbar-v2 list-action-toolbar", { "has-selection": e.state.selectedCount > 0 }]),
			id: "accountsToolbarV2",
			onFocusout: n[1] ||= (...e) => N(f).schedule && N(f).schedule(...e)
		}, [
			w("span", pe, S(e.state.selectedCount ? `已选 ${e.state.selectedCount} 个账号` : "选择账号后批量操作"), 1),
			w("details", {
				ref_key: "more",
				ref: a,
				class: "toolbar-overflow",
				id: "accountsMoreActionsV2",
				onToggle: n[0] ||= (...e) => N(f).schedule && N(f).schedule(...e)
			}, [n[2] ||= w("summary", null, "批量操作", -1), w("div", me, [(r(!0), I(v, null, s(N(oe), (e) => (r(), I("div", {
				key: e,
				class: "toolbar-overflow-section toolbar-overflow-section--wide"
			}, [w("span", he, S(e), 1), (r(!0), I(v, null, s(N(se).filter((t) => t.section === e), (e) => (r(), I("span", {
				key: e.id,
				ref_for: !0,
				ref: (t) => p(N(l), e.id, t),
				class: "account-action-slot"
			}))), 128))]))), 128))])], 544),
			w("div", ge, [(r(), I(v, null, s(5, (e) => w("span", {
				key: e,
				ref_for: !0,
				ref: (t) => p(N(u), e - 1, t),
				class: "account-action-slot"
			}, null, 512)), 64))])
		], 34), o.value ? (r(!0), I(v, { key: 0 }, s(N(se), (e) => (r(), C(x, {
			key: e.id,
			to: m(e)
		}, [w("button", {
			type: "button",
			id: e.id,
			class: D([e.className, { "feature-unavailable": _(e) }]),
			disabled: y(e),
			title: k(e),
			"data-feature": g(e) ? e.feature : void 0,
			"data-feature-base-title": g(e) ? O(e) : void 0,
			"aria-disabled": g(e) ? _(e) : void 0,
			onClick: (t) => j(e, t)
		}, S(E(e)), 11, _e)], 8, ["to"]))), 128)) : h("", !0)]));
	}
}), [["__scopeId", "data-v-d8d5d1f2"]]), ye = { class: "ac-filter-fields" }, be = {
	key: 0,
	class: "ac-filter-field"
}, xe = ["value"], Se = {
	key: 1,
	class: "list-filter-options"
}, Ce = { class: "ac-sr-only" }, we = { class: "list-filter-option" }, Te = ["checked"], Ee = [
	"value",
	"checked",
	"onChange"
], De = { key: 0 }, Oe = [
	"type",
	"inputmode",
	"value",
	"placeholder",
	"onInput"
], ke = { class: "list-filter-actions" }, Ae = /* @__PURE__ */ n({
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
		let n = e, a = t, c = b("id"), l = O(() => n.column || Y.find((e) => e.key === c.value) || Y[0]), u = O(() => n.column ? X(n.query, n.column) : Y.some((e) => X(n.query, e))), d = O(() => K(n.query, n.label).find((e) => e.key === l.value.key)?.label || ""), f = O(() => J(n.query, n.facets, l.value, n.label)), p = O(() => ee(n.query, l.value.key)), m = O(() => l.value.kind === "date-range" ? ["date_from", "date_to"] : [l.value.key]);
		function y(e, t) {
			let n = new Set(p.value);
			t ? n.add(e) : n.delete(e), a("change", l.value.key, [...n]);
		}
		function x() {
			a("clear", l.value.key), a("update:open", !1);
		}
		return (t, n) => (r(), C(H, {
			label: e.column?.label || "账号",
			"trigger-label": e.column ? void 0 : "筛选",
			active: u.value,
			summary: d.value,
			open: e.open,
			"onUpdate:open": n[4] ||= (e) => a("update:open", e)
		}, {
			default: i(() => [w("div", ye, [
				e.column ? h("", !0) : (r(), I("label", be, [n[5] ||= L("筛选列", -1), o(w("select", {
					"onUpdate:modelValue": n[0] ||= (e) => c.value = e,
					"aria-label": "选择账号筛选列"
				}, [(r(!0), I(v, null, s(N(Y), (e) => (r(), I("option", {
					key: e.key,
					value: e.key
				}, S(e.label), 9, xe))), 128))], 512), [[g, c.value]])])),
				l.value.kind === "enum" ? (r(), I("fieldset", Se, [
					w("legend", Ce, S(l.value.label) + "，可多选", 1),
					w("label", we, [w("input", {
						type: "checkbox",
						checked: !p.value.length,
						onChange: n[1] ||= (e) => a("change", l.value.key, [])
					}, null, 40, Te), n[6] ||= w("span", null, "全部", -1)]),
					(r(!0), I(v, null, s(f.value, (e) => (r(), I("label", {
						class: "list-filter-option",
						key: e.value
					}, [
						w("input", {
							type: "checkbox",
							value: e.value,
							checked: p.value.includes(e.value),
							onChange: (t) => y(e.value, t.target.checked)
						}, null, 40, Ee),
						w("span", null, S(e.label), 1),
						e.count === null ? h("", !0) : (r(), I("small", De, S(e.count), 1))
					]))), 128))
				])) : (r(!0), I(v, { key: 2 }, s(m.value, (t, i) => (r(), I("label", {
					key: t,
					class: "ac-filter-field"
				}, [L(S(l.value.kind === "date-range" ? i ? "截止日期" : "开始日期" : l.value.label), 1), w("input", {
					type: l.value.kind === "date-range" ? "date" : "text",
					inputmode: l.value.key === "id" ? "numeric" : void 0,
					value: N(q)(e.query, t),
					placeholder: l.value.placeholder,
					autocomplete: "off",
					onInput: (e) => a("change", t, e.target.value),
					onKeydown: n[2] ||= _(E((e) => a("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, Oe)]))), 128)),
				w("div", ke, [w("button", {
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
}), je = [
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
], Me = [
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
], Ne = Me.map((e) => e / Me.reduce((e, t) => e + t, 0) * 1500);
function Pe(e) {
	let t = (e, t = "") => `<div class="account-cell-lines"><div class="account-cell-line">${e}</div>${t ? `<div class="account-cell-line account-cell-line--sub">${t}</div>` : ""}</div>`, n = (e) => Array.from(e).length <= 10 ? e : re();
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
var Fe = [
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
function Ie(e) {
	if (!(e instanceof Element)) return;
	let t = e.closest("button,[data-copy-id]");
	if (!t || t.hasAttribute("disabled") || t.getAttribute("aria-disabled") === "true" || t.classList.contains("feature-unavailable")) return;
	let n = Fe.find((e) => t.hasAttribute(`data-${e}`));
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
var Le = ["aria-busy"], Re = ["data-stale"], ze = [
	"checked",
	"indeterminate",
	"disabled"
], Be = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], Ve = { id: "accountsBodyV2" }, He = ["data-account-row", "onClick"], Ue = { class: "col-check" }, We = [
	"data-account-id",
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], Ge = { class: "col-id" }, Ke = { class: "col-email" }, qe = ["disabled", "data-account-detail-id"], Je = { class: "acc-v2-email" }, Ye = {
	key: 0,
	class: "pill status-used",
	title: "该账号已归档"
}, Xe = { class: "acc-v2-sub account-cell-line account-cell-line--sub account-email-meta" }, Ze = { class: "account-email-name" }, Qe = ["innerHTML"], $e = { class: "acc-mobile-meta" }, et = { class: "col-source" }, tt = { class: "col-registration-driver" }, nt = ["data-label"], rt = ["innerHTML"], it = { class: "col-actions" }, at = { class: "account-cell-lines acc-v2-actions" }, ot = ["disabled", "data-account-detail-id"], st = ["disabled"], ct = ["onClick", "innerHTML"], lt = { key: 0 }, ut = {
	colspan: "16",
	class: "ac-empty"
}, dt = /* @__PURE__ */ n({
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
		let o = e, l = n, { widths: d, total: p, resize: m, resizeWithKeyboard: g, resetColumns: x } = ne({
			defaults: Ne,
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
		}), k = b(), A = b(null);
		function j(e) {
			if (!o.stale) return e;
			let t = document.createElement("template");
			return t.innerHTML = e, t.content.querySelectorAll("button,input,select,textarea").forEach((e) => e.setAttribute("disabled", "")), t.content.querySelectorAll("a,[role=\"button\"],[data-copy-id]").forEach((e) => {
				e.setAttribute("aria-disabled", "true"), e.setAttribute("tabindex", "-1");
			}), t.innerHTML;
		}
		let M = O(() => (o.stale && o.loading ? [] : o.items).map((e) => ({
			row: e,
			id: String(e.id),
			cells: Object.fromEntries(je.filter((e) => e.cell).map((t) => [t.cell, j(o.presentation.cell(t.cell, e))])),
			menu: o.presentation.menu(e),
			mobile: o.presentation.mobileSummary(e),
			tone: o.presentation.rowTone(e)
		}))), P = (e) => Y.find((t) => t.key === e);
		function F(e, t) {
			if (o.stale || !o.visible) {
				e.preventDefault(), e.stopPropagation();
				return;
			}
			let n = e.target instanceof Element ? e.target : null, r = n?.closest("[data-account-detail-id]");
			if (r) {
				e.preventDefault(), e.stopPropagation(), l("detail", String(t.id), r);
				return;
			}
			let i = Ie(e.target);
			i ? (e.preventDefault(), e.stopPropagation(), A.value = null, l("action", i.action, String(t.id), i.trigger)) : window.matchMedia("(max-width:860px)").matches && !n?.closest("button,a,input,label,[role=\"dialog\"]") && l("detail", String(t.id), null);
		}
		function H() {
			A.value = null;
		}
		function W(e) {
			e.target instanceof Element && e.target.closest(".ac-row-menu") || H();
		}
		return a(() => o.visible, (e) => {
			e || H();
		}), a(() => o.stale, (e) => {
			e && H();
		}), a(() => o.items, (e) => {
			A.value && !e.some((e) => String(e.id) === A.value) && H();
		}), c(() => {
			window.addEventListener("resize", H), window.addEventListener("scroll", W, !0), k.value && l("rendered", k.value);
		}), u(() => {
			k.value && l("rendered", k.value);
		}), T(() => {
			window.removeEventListener("resize", H), window.removeEventListener("scroll", W, !0);
		}), t({
			resetColumns: x,
			closeMenu: H
		}), (t, n) => (r(), I("div", {
			ref_key: "root",
			ref: k,
			class: "accounts-table-v2-wrap ac-table-scroll",
			tabindex: "0",
			"aria-label": "账号列表，可横向滚动",
			"aria-busy": e.loading,
			onScroll: H
		}, [w("table", {
			class: "accounts-table-v2 ac-table",
			style: y({ width: `${N(p)}px` }),
			"data-stale": e.stale || void 0
		}, [
			n[5] ||= w("caption", { class: "ac-sr-only" }, "账号资产，支持跨页选择", -1),
			w("colgroup", null, [(r(!0), I(v, null, s(N(d), (e, t) => (r(), I("col", {
				key: t,
				style: y({ width: `${e}px` })
			}, null, 4))), 128))]),
			w("thead", null, [w("tr", null, [(r(!0), I(v, null, s(N(je), (t, i) => (r(), I("th", {
				key: t.key,
				scope: "col",
				class: D(t.className)
			}, [t.key === "selection" ? (r(), I("input", {
				key: 0,
				id: "accountsSelectAllV2",
				type: "checkbox",
				"aria-label": "全选当前页账号",
				checked: e.pageSelected,
				indeterminate: e.pageIndeterminate,
				disabled: e.stale || !e.items.length,
				onChange: n[0] ||= (e) => l("selectPage", e.target.checked)
			}, null, 40, ze)) : t.filter ? (r(), C(Ae, {
				key: 1,
				column: P(t.filter),
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
			])) : (r(), I(v, { key: 2 }, [L(S(t.label), 1)], 64)), i ? (r(), I("button", {
				key: 3,
				type: "button",
				class: "ac-column-resize",
				"aria-label": `调整${t.label}列宽，方向键调整`,
				onPointerdown: E((e) => N(m)(i, e), ["prevent"]),
				onKeydown: [_(E((e) => N(g)(i, -10), ["prevent"]), ["left"]), _(E((e) => N(g)(i, 10), ["prevent"]), ["right"])]
			}, null, 40, Be)) : h("", !0)], 2))), 128))])]),
			w("tbody", Ve, [(r(!0), I(v, null, s(M.value, (t) => (r(), I("tr", {
				key: t.id,
				"data-account-row": t.id,
				class: D({ "ac-row-selected": e.selected.has(t.id) }),
				onClick: (e) => F(e, t.row)
			}, [
				w("td", Ue, [w("input", {
					type: "checkbox",
					class: "account-row-check",
					"data-account-id": t.id,
					"aria-label": `选择账号 ${t.row.email || t.id}`,
					checked: e.selected.has(t.id),
					disabled: e.stale,
					onChange: (e) => l("select", t.id, e.target.checked)
				}, null, 40, We)]),
				w("td", Ge, [f(B, { text: `#${t.id}` }, null, 8, ["text"])]),
				w("td", Ke, [
					w("button", {
						type: "button",
						class: "acc-v2-email-link account-cell-line",
						disabled: e.stale,
						"data-account-detail-id": t.id,
						title: "查看账号详情"
					}, [w("span", {
						class: D(["acc-mobile-dot", `is-${t.tone}`]),
						"aria-hidden": "true"
					}, null, 2), w("span", Je, [L(S(t.row.email), 1), t.row.archived ? (r(), I("span", Ye, "归档")) : h("", !0)])], 8, qe),
					w("div", Xe, [w("span", Ze, S(t.row.user_name || "-"), 1), w("span", { innerHTML: e.presentation.emailInvalidBadge(t.row) }, null, 8, Qe)]),
					w("div", $e, S(t.mobile), 1)
				]),
				w("td", et, [f(B, { text: t.row.email_source || "-" }, null, 8, ["text"])]),
				w("td", tt, [f(B, { text: e.presentation.registrationDriverLabel(t.row.registration_driver) }, null, 8, ["text"])]),
				(r(!0), I(v, null, s(N(je).filter((e) => e.cell), (e) => (r(), I("td", {
					key: e.key,
					class: D(e.className),
					"data-label": e.label
				}, [w("div", {
					class: "ac-legacy-cell",
					innerHTML: t.cells[e.cell]
				}, null, 8, rt)], 10, nt))), 128)),
				w("td", it, [w("div", at, [w("button", {
					type: "button",
					class: "acc-v2-detail",
					disabled: e.stale,
					"data-account-detail-id": t.id
				}, "详情", 8, ot), f(N(U), {
					open: e.visible && !e.stale && A.value === t.id,
					modal: !1,
					"onUpdate:open": (e) => A.value = e ? t.id : null
				}, {
					default: i(() => [f(N(z), { "as-child": "" }, {
						default: i(() => [w("button", {
							type: "button",
							class: "acc-v2-more-btn",
							disabled: e.stale,
							"aria-label": "更多账号操作"
						}, "更多", 8, st)]),
						_: 1
					}), f(N(R), null, {
						default: i(() => [f(N(V), {
							class: "ac-row-menu accounts-table-v2",
							"data-account-menu": t.id,
							side: "bottom",
							align: "end",
							"side-offset": 4,
							"collision-padding": 8,
							onOpenAutoFocus: n[3] ||= E(() => {}, ["prevent"])
						}, {
							default: i(() => [w("div", {
								class: "acc-v2-more-menu ac-menu-content",
								onClick: (e) => F(e, t.row),
								innerHTML: t.menu
							}, null, 8, ct)]),
							_: 2
						}, 1032, ["data-account-menu"])]),
						_: 2
					}, 1024)]),
					_: 2
				}, 1032, ["open", "onUpdate:open"])])])
			], 10, He))), 128)), M.value.length ? h("", !0) : (r(), I("tr", lt, [w("td", ut, [
				w("strong", null, S(e.loading ? "正在加载账号" : e.invalidSearch ? "搜索条件有误" : e.error ? "账号加载失败" : "暂无匹配账号"), 1),
				w("p", null, S(e.loading ? "正在同步账号状态和授权信息" : e.invalidSearch ? "请按输入框旁的提示修改，或清空高级搜索。" : e.error || "可移除部分搜索条件，或切换活跃与归档账号视图。"), 1),
				e.error && !e.invalidSearch ? (r(), I("button", {
					key: 0,
					type: "button",
					class: "ac-button",
					onClick: n[4] ||= (e) => l("retry")
				}, "重试")) : h("", !0)
			])]))])
		], 12, Re)], 40, Le));
	}
}), ft = [
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
function Q(e) {
	return Array.isArray(e) ? e.map(Q) : e && typeof e == "object" ? Object.fromEntries(Object.entries(e).map(([e, t]) => [e, Q(t)])) : e;
}
function pt(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(pt), Object.freeze(e)), e;
}
function mt(e) {
	return pt(Q(e));
}
function ht(e) {
	let t = String(e);
	if (!/^[1-9]\d*$/.test(t) || !Number.isSafeInteger(Number(t))) throw Error("账号 ID 无效");
	return t;
}
function gt() {
	throw new DOMException("读取已失效", "AbortError");
}
function _t(e) {
	return Q({
		account_promotions: e.account_promotions ?? null,
		promotion_query_snapshot: e.promotion_query_snapshot ?? null,
		plan_check_country_results: e.plan_check_country_results ?? []
	});
}
function vt(n, r) {
	let i = A(n.normalize()), a = A([]), o = A({}), s = A([]), c = A(null), l = b(0), u = b(1), d = b(10), f = b(!1), p = b(!1), h = b(!1), g = b(""), _ = b(!1), v = b(""), y = A(/* @__PURE__ */ new Set()), x = A({}), S = b(""), C = O(() => Math.max(1, Math.ceil(l.value / d.value))), w = O(() => n.toLegacy(i.value, {
		paged: "1",
		page: u.value,
		page_size: d.value
	}).toString()), T = O(() => S.value !== w.value), E = O(() => a.value.length > 0 && a.value.every((e) => y.value.has(String(e.id)))), D = O(() => !E.value && a.value.some((e) => y.value.has(String(e.id)))), k = 0, j = 0, M = 0, N = 0, P = !1, F = !1, I, L, R, z, B, V = "", H, U = /* @__PURE__ */ new Map(), W = /* @__PURE__ */ new Map(), G = () => typeof document > "u" || !document.hidden, K = () => !P && h.value && G(), q = (e, t) => e === k && t === w.value && K();
	function J(e) {
		return [...W.values()].some((t) => t === e);
	}
	function Y() {
		let e = /* @__PURE__ */ new Set([...a.value.map((e) => String(e.id)), ...W.values()]);
		for (let [t, n] of U) e.has(t) || (n.request?.controller.abort(), U.delete(t));
	}
	function X() {
		for (let e of U.values()) e.request?.controller.abort(), e.request = void 0, ++e.version;
	}
	function ee() {
		++k, ++j, I?.abort(), L?.abort(), I = L = void 0, clearTimeout(R), clearTimeout(B), R = B = void 0, f.value = p.value = !1;
	}
	function te() {
		clearTimeout(R), R = void 0, K() && H !== i.value.q && (R = setTimeout(() => {
			se();
		}, 5e3));
	}
	function ne(e) {
		let t = Q(e);
		for (let e of ft) {
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
	function re(e) {
		a.value = Q(e);
		for (let e of a.value) {
			let t = String(e.id), n = U.get(t);
			n?.request?.controller.abort(), U.set(t, {
				revision: "",
				version: (n?.version ?? 0) + 1,
				details: _t(e)
			});
		}
		Y();
	}
	async function Z() {
		if (ee(), !K()) return;
		let e = k, t = new AbortController();
		I = t, f.value = !0;
		try {
			for (let n = 0; n < 2; n++) {
				let a = w.value, c = Q(i.value), f = u.value, p = d.value, m = await r.list(c, f, p, t.signal);
				if (!q(e, a)) return;
				let h = Math.max(1, Math.ceil(m.total / p));
				if (f > h) {
					if (u.value = h, !n) continue;
					g.value = "列表范围已变化，请刷新后重试";
					return;
				}
				re(m.items), l.value = m.total, o.value = ne(m.facets), s.value = Q(m.search_terms), S.value = a, V = "", g.value = "", _.value = !1, H = void 0;
				return;
			}
		} catch (t) {
			if (e !== k || !K() || ie(t)) return;
			g.value = t instanceof Error ? t.message : "加载账号失败", t instanceof ae && t.code === "account_search_invalid" && (H = i.value.q, _.value = !0, a.value = [], l.value = 0, s.value = [], o.value = {}, Y());
		} finally {
			e === k && (f.value = !1, I = void 0, te());
		}
	}
	function oe(e, t, n) {
		let r = Q(e);
		for (let e of n) delete r[e];
		Object.assign(r, Q(t));
		let i = String(e.id), a = U.get(i);
		if (!a || a.revision !== t.plan_details_revision) {
			a?.request?.controller.abort(), U.set(i, {
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
	async function se() {
		if (clearTimeout(R), R = void 0, !K() || f.value || p.value || T.value || H === i.value.q) {
			te();
			return;
		}
		let e = k, t = w.value, n = new AbortController();
		L = n, p.value = !0;
		try {
			let o = await r.statuses(Q(i.value), u.value, d.value, n.signal);
			if (!q(e, t)) return;
			let s = new Map(a.value.map((e) => [String(e.id), e]));
			if (o.total !== l.value || o.items.length !== a.value.length || o.items.some((e, t) => String(e.id) !== String(a.value[t]?.id)) || new Set(o.items.map((e) => e.id)).size !== o.items.length) {
				await Z();
				return;
			}
			if (c.value = Q(o.queue), V === o.revision) return;
			let f = (e) => e === "queued" || e === "running", p = !1;
			a.value = o.items.map((e) => {
				let t = s.get(String(e.id));
				return (f(t.plan_check_status) && !f(e.plan_check_status) || f(t.extract_link_status) && !f(e.extract_link_status)) && (p = !0), oe(t, e, o.status_fields);
			}), V = o.revision, p && await Z();
		} catch (n) {
			q(e, t) && n instanceof ae && n.code === "account_search_invalid" && (H = i.value.q, _.value = !0, g.value = n instanceof Error ? n.message : "筛选语法无效", a.value = [], l.value = 0, o.value = {}, s.value = [], Y());
		} finally {
			e === k && (p.value = !1, L = void 0, te());
		}
	}
	function ce(e = 0) {
		if (ee(), !K()) return;
		let n = j, r = () => {
			n === j && K() && Z();
		};
		e ? B = setTimeout(r, e) : t(r);
	}
	function le() {
		y.value = /* @__PURE__ */ new Set(), x.value = {}, ++M;
	}
	function ue(e, t = 0) {
		if (P) return;
		let r = n.normalize(e);
		clearTimeout(z), z = void 0, n.toLegacy(r).toString() === n.toLegacy(i.value).toString() && r.limit === i.value.limit ? v.value = r.q : (i.value = Q(r), v.value = r.q, u.value = 1, le(), _.value = !1, g.value = "", H = void 0, ce(t));
	}
	function de(e, t = 0) {
		ue({
			...Q(i.value),
			...Q(e)
		}, t);
	}
	function fe(e, t = 0) {
		de({ filters: {
			...Q(i.value.filters),
			...Q(e)
		} }, t);
	}
	function pe(e) {
		de({ archived: e ? "only" : "0" });
	}
	function me() {
		ue(n.normalize({ archived: i.value.archived }));
	}
	function he(e) {
		if (P || !Number.isFinite(e)) return;
		let t = Math.min(C.value, Math.max(1, Math.floor(e)));
		t !== u.value && (u.value = t, ce());
	}
	function ge(e) {
		if (P || !Number.isFinite(e) || e < 1) return;
		let t = Math.min(500, Math.floor(e));
		t !== d.value && (d.value = t, u.value = 1, ce());
	}
	function _e(e) {
		v.value = e, clearTimeout(z), z = void 0, !F && !P && (z = setTimeout(() => {
			de({ q: v.value });
		}, 250));
	}
	function ve() {
		F = !0, clearTimeout(z), z = void 0;
	}
	function ye(e) {
		F = !1, _e(e);
	}
	function be() {
		F || (clearTimeout(z), de({ q: v.value }));
	}
	function xe() {
		F = !1, clearTimeout(z), de({ q: "" });
	}
	function Se(e) {
		de({ q: e.query_without });
	}
	function Ce(e, t) {
		if (P) return;
		if (t && (T.value || _.value)) throw Error("当前筛选结果尚未加载");
		let n = ht(e), r = a.value.find((e) => String(e.id) === n);
		if (t && !r) throw Error("账号不在当前页");
		let i = new Set(y.value), o = { ...x.value };
		t ? (i.add(n), r?.email?.trim() ? o[n] = r.email : delete o[n]) : (i.delete(n), delete o[n]), y.value = i, x.value = o, ++M;
	}
	function we(e) {
		for (let t of a.value) Ce(String(t.id), e);
	}
	function Te(e) {
		for (let t of e) Ce(t, !1);
	}
	function Ee(e = {}) {
		let t = [...new Set((e.ids ?? [...y.value]).map(ht))], n = {}, r = new Map(a.value.map((e) => [String(e.id), e]));
		for (let e of t) {
			let t = r.has(e) ? r.get(e)?.email : x.value[e];
			t && (n[e] = t);
		}
		if (e.requireEmails && (t.length > 500 || t.some((e) => !n[e]?.trim()))) throw Error(t.length > 500 ? "一次最多处理 500 个账号" : "账号邮箱快照不完整，请刷新后重新选择");
		return mt({
			query: i.value,
			ids: t,
			expectedEmails: n,
			created_at: (/* @__PURE__ */ new Date()).toISOString(),
			source: "accounts",
			generation: M
		});
	}
	function De(e = {}) {
		let t = Ee(e), n = new Set(t.ids);
		return mt({
			accountIds: t.ids,
			expectedEmails: t.expectedEmails,
			querySnapshot: t.query,
			archived: t.query.archived,
			rowHints: a.value.filter((e) => n.has(String(e.id)))
		});
	}
	function Oe(e) {
		let t = a.value.find((t) => String(t.id) === e);
		return t ? mt(t) : void 0;
	}
	async function ke(e) {
		K() && J(e) || gt();
		let t = U.get(e);
		if (t || gt(), t.details) return mt({
			accountId: e,
			revision: t.revision,
			item: t.details
		});
		if (t.request) return t.request.promise;
		let n = new AbortController(), i = t.version, o = r.planDetails(e, n.signal).then(async (n) => {
			K() && J(e) || gt();
			let r = U.get(e);
			return r || gt(), r !== t || r.version !== i ? ke(e) : (r.details = Q(n.item), a.value = a.value.map((t) => String(t.id) === e ? {
				...t,
				...Q(n.item)
			} : t), mt({
				accountId: e,
				revision: r.revision,
				item: r.details
			}));
		}, (n) => {
			K() && J(e) || gt();
			let r = U.get(e);
			if (r && (r !== t || r.version !== i)) return ke(e);
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
	async function Ae(e, t) {
		let n = ht(e);
		for (;;) {
			W.get(t) === n && K() || gt();
			let e = U.get(n), r = e?.version, i;
			try {
				i = await ke(n);
			} catch (e) {
				throw W.get(t) === n && K() || gt(), e;
			}
			if (W.get(t) === n && K() || gt(), U.get(n) === e && e?.version === r) return i;
		}
	}
	function je(e) {
		let t = ht(e), n = ++N;
		if (!U.has(t)) throw Error("账号详情已失效，请刷新列表");
		return W.set(n, t), {
			openGeneration: n,
			loadPlanDetails: Ae,
			release() {
				if (W.delete(n)) {
					if (!J(t)) {
						let e = U.get(t);
						e?.request && (e.request.controller.abort(), e.request = void 0, ++e.version);
					}
					Y();
				}
			}
		};
	}
	function Me(e) {
		P || e === h.value || (h.value = e, e ? ce() : (ee(), X(), W.clear(), Y()));
	}
	function Ne() {
		G() ? h.value && ce() : (ee(), X());
	}
	return typeof document < "u" && document.addEventListener("visibilitychange", Ne), m(() => {
		P = !0, ee(), clearTimeout(z), X(), W.clear(), U.clear(), typeof document < "u" && document.removeEventListener("visibilitychange", Ne);
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
		refresh: Z,
		pollStatuses: se,
		setVisible: Me,
		setPage: he,
		setSize: ge,
		setArchived: pe,
		commitQuery: ue,
		updateQuery: de,
		updateFilters: fe,
		resetFilters: me,
		setSearchDraft: _e,
		compositionStart: ve,
		compositionEnd: ye,
		submitSearch: be,
		clearSearch: xe,
		removeSearchTerm: Se,
		toggle: Ce,
		togglePage: we,
		clearSelection: le,
		removeAcknowledgedSelection: Te,
		getAccountSelectionSnapshot: Ee,
		getActionContext: De,
		getRowSnapshot: Oe,
		openPlanDetailsConsumer: je,
		loadPlanDetails: Ae
	};
}
// src/features/accounts/AccountsList.vue?vue&type=script&setup=true&lang.ts
var yt = {
	class: "ac-root",
	"aria-label": "账号列表"
}, bt = { class: "ac-toolbar" }, xt = { class: "ac-toolbar-main" }, St = {
	id: "accountsPageSummary",
	class: "ac-count",
	role: "status"
}, Ct = { class: "ac-toolbar-utilities" }, wt = { class: "ac-mobile-filters" }, Tt = [
	"value",
	"aria-invalid",
	"onKeydown"
], Et = ["disabled"], Dt = {
	key: 0,
	id: "accountAdvancedSearchErrorV2",
	class: "ac-feedback",
	role: "alert"
}, Ot = {
	key: 1,
	class: "ac-feedback",
	role: "alert"
}, kt = /* @__PURE__ */ n({
	__name: "AccountsList",
	props: {
		adapter: {},
		api: {},
		presentation: {},
		callbacks: {}
	},
	setup(e, { expose: t }) {
		let n = e, i = vt(n.adapter, n.api), { query: s, items: c, facets: l, searchTerms: u, total: p, page: m, size: g, pages: v, selected: y, loading: x, error: C, visible: D, invalidSearch: k, draftSearch: A, stale: j, pageSelected: P, pageIndeterminate: F } = i, L = b(), R = b(), z = b(null), B = b(typeof document > "u" || !document.hidden), V = b(""), H = /* @__PURE__ */ new Set(), U = Y.find((e) => e.key === "email_status"), q = O(() => [...K(s.value, n.presentation.facetLabel), ...u.value.map((e, t) => ({
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
			if (j.value || !D.value || !B.value) return;
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
			if (j.value || !D.value || !B.value) return;
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
		function Z() {
			i.clearSearch(), R.value?.focus();
		}
		function ae() {
			L.value?.resetColumns();
		}
		a([
			i.selected,
			i.selectedEmails,
			p,
			m,
			g,
			s,
			x,
			D
		], () => n.callbacks.onStateChange?.(Object.freeze({
			selectedIds: Object.freeze([...y.value]),
			selectedEmails: Object.freeze({ ...i.selectedEmails.value }),
			total: p.value,
			page: m.value,
			size: g.value,
			archived: s.value.archived,
			loading: x.value,
			visible: D.value
		})), {
			immediate: !0,
			flush: "post"
		});
		let oe = () => {
			B.value = !document.hidden, document.hidden && (z.value = null, n.callbacks.closeConsumers?.());
		};
		return typeof document < "u" && document.addEventListener("visibilitychange", oe), T(() => {
			typeof document < "u" && document.removeEventListener("visibilitychange", oe), n.callbacks.closeConsumers?.();
		}), t({
			refresh: i.refresh,
			pollStatuses: i.pollStatuses,
			setVisible: re,
			setArchived: ie,
			openDetail: ne,
			setPage: i.setPage,
			setSize: i.setSize,
			closeMoreMenus: () => L.value?.closeMenu(),
			updateQuery: i.updateQuery,
			updateFilters: i.updateFilters,
			resetFilters: i.resetFilters,
			resetColumns: ae,
			getAccountSelectionSnapshot: i.getAccountSelectionSnapshot,
			getActionContext: i.getActionContext,
			getRowSnapshot: i.getRowSnapshot,
			openPlanDetailsConsumer: i.openPlanDetailsConsumer,
			removeAcknowledgedSelection: i.removeAcknowledgedSelection,
			clearSelection: i.clearSelection
		}), (t, n) => o((r(), I("section", yt, [
			w("div", bt, [
				w("div", xt, [w("span", St, S(N(p).toLocaleString()) + " 个账号 · 当前页 " + S(N(c).length) + " 条", 1), f(W, {
					items: q.value,
					onRemove: X
				}, null, 8, ["items"])]),
				d(t.$slots, "actions"),
				w("div", Ct, [
					w("div", wt, [f(Ae, {
						query: N(s),
						facets: N(l),
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
					f(Ae, {
						column: N(U),
						query: N(s),
						facets: N(l),
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
						onSubmit: n[5] ||= E((...e) => N(i).submitSearch && N(i).submitSearch(...e), ["prevent"])
					}, [
						n[11] ||= w("label", { for: "accountAdvancedSearchV2" }, "高级搜索", -1),
						w("input", {
							id: "accountAdvancedSearchV2",
							ref_key: "search",
							ref: R,
							type: "search",
							value: N(A),
							placeholder: "空格或 / 组合，如：协议 jp",
							autocomplete: "off",
							"aria-describedby": "accountAdvancedSearchHintV2 accountAdvancedSearchErrorV2",
							"aria-invalid": N(k) || void 0,
							onKeydown: _(E(Z, ["prevent"]), ["esc"]),
							onInput: n[2] ||= (e) => N(i).setSearchDraft(e.target.value),
							onCompositionstart: n[3] ||= (...e) => N(i).compositionStart && N(i).compositionStart(...e),
							onCompositionend: n[4] ||= (e) => N(i).compositionEnd(e.target.value)
						}, null, 40, Tt),
						N(A) ? (r(), I("button", {
							key: 0,
							type: "button",
							"aria-label": "清空高级搜索",
							title: "清空高级搜索",
							onClick: Z
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
						onClick: n[6] ||= (...e) => N(i).resetFilters && N(i).resetFilters(...e)
					}, "清筛"),
					w("button", {
						id: "btnResetAccountsColumnsV2",
						type: "button",
						class: "ac-link",
						title: "恢复账号列表默认列宽",
						onClick: ae
					}, "恢复列宽"),
					w("button", {
						id: "btnRefreshAccountsV2",
						type: "button",
						class: "ac-button",
						disabled: N(x),
						onClick: n[7] ||= (...e) => N(i).refresh && N(i).refresh(...e)
					}, S(N(x) ? "刷新中…" : "刷新"), 9, Et)
				])
			]),
			N(k) ? (r(), I("p", Dt, S(N(C)), 1)) : V.value || N(C) && N(c).length ? (r(), I("div", Ot, [w("span", null, S(V.value || N(C)), 1), N(C) ? (r(), I("button", {
				key: 0,
				type: "button",
				class: "ac-link",
				onClick: n[8] ||= (...e) => N(i).refresh && N(i).refresh(...e)
			}, "重试")) : h("", !0)])) : h("", !0),
			f(dt, {
				ref_key: "table",
				ref: L,
				items: N(c),
				selected: N(y),
				query: N(s),
				facets: N(l),
				presentation: e.presentation,
				loading: N(x),
				error: N(C),
				"invalid-search": N(k),
				stale: N(j),
				visible: N(D) && B.value,
				"page-selected": N(P),
				"page-indeterminate": N(F),
				"open-filter": z.value,
				"onUpdate:openFilter": n[9] ||= (e) => z.value = e,
				onFilter: J,
				onClearFilter: X,
				onSelect: N(i).toggle,
				onSelectPage: N(i).togglePage,
				onAction: te,
				onDetail: ne,
				onRetry: N(i).refresh,
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
			f(G, {
				page: N(m),
				size: N(g),
				pages: N(v),
				total: N(p),
				busy: N(x),
				"page-sizes": [
					10,
					20,
					30,
					50,
					100
				],
				label: "账号列表分页",
				"onUpdate:page": N(i).setPage,
				"onUpdate:size": N(i).setSize
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		], 512)), [[M, N(D)]]);
	}
});
// src/features/accounts/useAccountDetail.ts
function At(e) {
	return JSON.parse(JSON.stringify(e));
}
function jt(e, t) {
	if (!e || typeof e != "object" || !("accountId" in e) || String(e.accountId) !== t || !("item" in e) || !e.item || typeof e.item != "object" || Array.isArray(e.item) || "id" in e.item && e.item.id != null && String(e.item.id) !== t) throw Error("账号详情响应不匹配");
	return At(e.item);
}
function Mt(e, t) {
	let n = A(null), r = A(0), i = O(() => n.value !== null), a = O(() => n.value ? String(n.value.id) : ""), o = null, s = (e) => o === e && r.value === e.generation;
	function c(e) {
		n.value = { ...e.account };
	}
	async function l(n) {
		try {
			let e = await n.lease.loadPlanDetails(n.id, n.lease.openGeneration);
			if (!s(n)) return;
			Object.assign(n.account, jt(e, n.id)), c(n);
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
		let s = At(n);
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
		account: F(n),
		generation: F(r),
		isOpen: i,
		accountId: a,
		open: d,
		close: u
	};
}
// src/features/accounts/AccountDetail.vue?vue&type=script&setup=true&lang.ts
var Nt = ["aria-hidden"], Pt = ["data-account-id"], Ft = { class: "account-detail-head" }, It = { id: "accountDetailTitle" }, Lt = { id: "accountDetailSubtitle" }, Rt = ["innerHTML"], zt = /* @__PURE__ */ n({
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
		let u = Mt(i.api, {
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
		}), { account: d, accountId: f, isOpen: p } = u, m = O(() => d.value ? d.value.email || `账号 #${d.value.id}` : "账号详情"), h = O(() => d.value ? `账号 #${d.value.id} · ${i.presentation.sourceLabel(d.value.email_source) || "未知来源"}` : ""), g = O(() => d.value ? i.presentation.renderBody(d.value) : "");
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
			class: D(["account-detail-backdrop", { hidden: !N(p) }]),
			"aria-hidden": !N(p),
			onClick: t[0] ||= E((e) => v(), ["self"])
		}, null, 10, Nt), w("aside", {
			id: "accountDetailDrawer",
			class: D(["account-detail-drawer", { hidden: !N(p) }]),
			"data-account-id": N(p) ? N(f) : void 0,
			role: "dialog",
			"aria-modal": "true",
			"aria-labelledby": "accountDetailTitle"
		}, [w("div", Ft, [w("div", null, [
			t[2] ||= w("div", { class: "data-panel-kicker" }, "ACCOUNT DETAIL", -1),
			w("h2", It, S(m.value), 1),
			w("p", Lt, S(h.value), 1)
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
		}, null, 8, Rt)], 10, Pt)]));
	}
}), Bt = (e) => e === "only" ? "已归档账号" : e === "all" ? "全部账号" : "未归档账号", Vt = (e) => ({
	running: "进行中",
	completed: "已完成",
	interrupted: "已中断"
})[String(e)] || String(e ?? ""), Ht = (e) => ({
	deactivated_skipped: "已废跳过",
	rejected: "未能入队",
	failed: "查活失败",
	error: "执行异常",
	attention_required: "执行失败",
	interrupted: "执行中断"
})[String(e)] || String(e ?? ""), Ut = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : String(e);
function Wt(e) {
	return e && typeof e == "object" ? e : {};
}
function Gt(e) {
	return Object.freeze((Array.isArray(e) ? e : []).map((e) => Object.freeze({ ...Wt(e) })));
}
function Kt(e) {
	let t = b(!1), n = b(!1), r = b(!1), i = b("0"), o = b(3), s = b(!1), c = b(""), l = b(1), u = b(1), d = b(null), f = A([]), p = A([]), h = b(0), g = b(0), _ = b(!1), v = b(!1), y = b(""), x = b(!1), S = b(!1), C = b(!1), w = null, T = 0, E = 0, D = !1, k, j, M, N = () => typeof document > "u" || !document.hidden, P = O(() => _.value ? `共 ${h.value} 条 · 第 ${l.value} 页` : ""), F = O(() => v.value ? `共 ${g.value} 条 · 第 ${u.value} 页` : "");
	async function I(t, n = {}, r = new AbortController()) {
		let i = setTimeout(() => r.abort(), 3e4);
		try {
			return Wt(await e.request(t, {
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
				D || (c.value = `巡检启动请求失败：${Ut(e)}。可查看巡检历史，或使用当前提交再次确认。`);
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
		k = i;
		try {
			let e = await I(`/api/accounts/inspections?page=${t}`, {}, i);
			if (D || i.signal.aborted || !n.value || t !== l.value || r !== T) return;
			let a = C.value;
			C.value = !!e.active, a && !C.value && L(), f.value = Gt(e.items), h.value = Number(e.total), _.value = !0;
		} catch (t) {
			!D && n.value && N() && r === T && e.notify(`读取巡检历史失败：${Ut(t)}`);
		} finally {
			x.value = !1, k === i && (k = void 0), r !== T && !D && n.value && N() && H();
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
		j = i;
		try {
			let a = await I(`/api/accounts/inspections/${e}/failures?page=${t}`, {}, i);
			if (D || i.signal.aborted || !r.value || e !== d.value || t !== u.value || n !== E) return;
			p.value = Gt(a.items), g.value = Number(a.total), v.value = !0, y.value = "";
		} catch (e) {
			!D && r.value && N() && n === E && (y.value = `读取失败：${Ut(e)}，可点击刷新重试。`);
		} finally {
			S.value = !1, j === i && (j = void 0), n !== E && !D && r.value && N() && G();
		}
	}
	async function K(t) {
		if (!D) try {
			if (await I(`/api/accounts/inspections/${Number(t)}/cancel`, { method: "POST" }), D) return;
			e.notify("已请求停止，将在安全检查点结束"), H();
		} catch (t) {
			D || e.notify(`停止巡检失败：${Ut(t)}`);
		}
	}
	function q(e) {
		e && e !== "start" || (t.value = !1), e && e !== "history" || (n.value = !1, ++T, k?.abort()), e && e !== "failures" || (r.value = !1, ++E, j?.abort());
	}
	function J() {
		M !== void 0 && (clearInterval(M), M = void 0), !D && N() && (n.value || r.value) && (M = setInterval(() => {
			n.value && H(), r.value && G();
		}, 5e3));
	}
	function Y() {
		N() || (++T, ++E, k?.abort(), j?.abort()), J();
	}
	return a([n, r], J, { flush: "sync" }), typeof document < "u" && document.addEventListener("visibilitychange", Y), m(() => {
		D = !0, q(), J(), typeof document < "u" && document.removeEventListener("visibilitychange", Y);
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
		close: q,
		changeHistoryPage: V,
		changeFailuresPage: W,
		refreshHistory: H,
		refreshFailures: G,
		stop: K
	};
}
// src/features/accounts/Inspection.vue?vue&type=script&setup=true&lang.ts
var qt = ["data-archived"], Jt = { class: "modal-header" }, Yt = { id: "accountInspectionScope" }, Xt = {
	id: "accountInspectionStartError",
	role: "status"
}, Zt = ["disabled"], Qt = { class: "modal-header" }, $t = {
	key: 0,
	"data-inspection-scroll": "",
	tabindex: "0",
	role: "region",
	"aria-label": "可左右滚动查看巡检记录"
}, en = { class: "data-table" }, tn = ["data-inspection-task", "onClick"], nn = { class: "sub-cell" }, rn = { class: "sub-cell" }, an = { key: 0 }, on = ["onClick"], sn = ["onClick"], cn = { key: 1 }, ln = { class: "jobs-v2-pager" }, un = ["disabled"], dn = { id: "accountInspectionPageLabel" }, fn = ["disabled"], pn = { class: "modal-header" }, mn = { id: "accountInspectionFailuresTitle" }, hn = { key: 0 }, gn = {
	key: 1,
	"data-inspection-scroll": "",
	tabindex: "0",
	role: "region",
	"aria-label": "可左右滚动查看巡检记录"
}, _n = { class: "data-table" }, vn = { class: "inspection-error-reason" }, yn = { key: 2 }, bn = { class: "jobs-v2-pager" }, xn = ["disabled"], Sn = { id: "accountInspectionFailuresPageLabel" }, Cn = ["disabled"], wn = /*#__PURE__*/ P(/* @__PURE__ */ n({
	__name: "Inspection",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, c = Kt(i.deps), { startOpen: l, historyOpen: u, failuresOpen: d, archived: f, workers: m, starting: g, startError: _, historyPage: y, failurePage: x, failureId: C, historyRows: D, failureRows: O, historyTotal: k, failureTotal: A, historyReady: M, failureReady: P, failureError: F, historyLabel: R, failureLabel: z } = c, B = b(), V = b(), H = b(), U = b(), W = b(), G = /* @__PURE__ */ new Map(), K = {
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
			X("start", t), c.openStart(e), oe("start");
		}
		function te(e) {
			X("history", e), c.openHistory(), oe("history");
		}
		function ne(e, t) {
			X("failures", t), c.openFailures(e), oe("failures");
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
		function Z(e) {
			let t = q[e].value;
			t?.open && (++K[e], t.close(), re(e));
		}
		function ae(e) {
			c.close(e);
			for (let t of [
				"failures",
				"history",
				"start"
			]) e && e !== t || Z(t);
		}
		async function oe(e) {
			await t();
			let n = q[e].value, r = J[e].value;
			n && !Y && (r && !n.open ? (G.has(e) || G.set(e, document.activeElement instanceof HTMLElement ? document.activeElement : null), n.showModal()) : !r && n.open && Z(e));
		}
		for (let e of [
			"start",
			"history",
			"failures"
		]) a(J[e], () => oe(e), { flush: "post" });
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
		function se(e) {
			ae("history"), i.deps.openTask(Number(e.task_id));
		}
		function ce(e) {
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
			close: ae,
			refreshHistory: c.refreshHistory,
			refreshFailures: c.refreshFailures,
			changeHistoryPage: c.changeHistoryPage,
			changeFailuresPage: c.changeFailuresPage,
			stop: c.stop
		}), (t, n) => (r(), I(v, null, [
			w("dialog", {
				ref_key: "start",
				ref: B,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionStart",
				"aria-labelledby": "accountInspectionStartTitle",
				"data-archived": N(f),
				onClose: n[3] ||= (e) => ie("start")
			}, [w("div", Jt, [n[14] ||= w("h2", { id: "accountInspectionStartTitle" }, "启动账号巡检", -1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				"aria-label": "关闭启动巡检",
				onClick: n[0] ||= (e) => ae("start")
			}, "关闭")]), w("form", { onSubmit: n[2] ||= E((...e) => N(c).submit && N(c).submit(...e), ["prevent"]) }, [
				w("p", Yt, "本次范围：" + S(N(Bt)(N(f))), 1),
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
				}, null, 512), [[j, N(m)]]),
				n[18] ||= w("p", null, "支持 1–16；实际并发同时受共享账号操作预算限制。", -1),
				w("p", Xt, S(N(_)), 1),
				w("button", {
					type: "submit",
					class: "jobs-tb-btn jobs-tb-btn--primary",
					id: "btnConfirmAccountInspection",
					disabled: N(g)
				}, "开始巡检", 8, Zt)
			], 32)], 40, qt),
			w("dialog", {
				ref_key: "history",
				ref: V,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionHistory",
				"aria-labelledby": "accountInspectionHistoryTitle",
				onClose: n[8] ||= (e) => ie("history")
			}, [
				w("div", Qt, [
					n[19] ||= w("h2", { id: "accountInspectionHistoryTitle" }, "账号巡检历史", -1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[4] ||= (...e) => N(c).refreshHistory && N(c).refreshHistory(...e)
					}, "刷新"),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[5] ||= (e) => ae("history")
					}, "关闭")
				]),
				n[20] ||= w("p", null, "每 5 秒刷新。进度包含跳过；完成表示本轮处理结束，查活和套餐结果分别统计。", -1),
				w("div", {
					ref_key: "historyContent",
					ref: U,
					id: "accountInspectionHistoryContent",
					"aria-live": "polite"
				}, [N(D).length ? (r(), I("div", $t, [w("table", en, [w("thead", null, [w("tr", null, [(r(), I(v, null, s([
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
				}, S(e), 1)), 64))])]), w("tbody", null, [(r(!0), I(v, null, s(N(D), (t, n) => (r(), I("tr", { key: String(t.id ?? n) }, [
					w("td", null, [w("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-inspection-task": Number(t.id),
						onClick: (e) => se(t)
					}, "#" + S(Number(t.id)), 9, tn)]),
					w("td", null, S(N(Bt)(String(t.archived))), 1),
					w("td", null, [L(S(N(Vt)(t.status)), 1), w("div", nn, S(e.deps.formatDateTime(t.created_at)), 1)]),
					w("td", null, S(Number(t.workers)), 1),
					w("td", null, [L(S(Number(t.checked_count) + Number(t.skipped_count)) + " / " + S(Number(t.total_count)), 1), w("div", rn, "跳过 " + S(Number(t.skipped_count)) + "（已废 " + S(Number(t.deactivated_skipped_count)) + "）", 1)]),
					w("td", null, S(Number(t.invalid_count)), 1),
					w("td", null, [L(S(Number(t.live_success_count)) + " / " + S(Number(t.live_failed_count)), 1), ce(t) ? (r(), I("div", an, [w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: (e) => ne(Number(t.id), e.currentTarget)
					}, "失败详情 " + S(ce(t)), 9, on)])) : h("", !0)]),
					w("td", null, S(Number(t.plan_success_count)) + " / " + S(Number(t.plan_failed_count)), 1),
					w("td", null, [t.status === "running" ? (r(), I("button", {
						key: 0,
						type: "button",
						class: "jobs-tb-btn",
						onClick: (e) => N(c).stop(Number(t.id))
					}, "停止", 8, sn)) : h("", !0)])
				]))), 128))])])])) : (r(), I("p", cn, S(N(M) ? "暂无巡检记录。" : "正在读取巡检历史…"), 1))], 512),
				w("div", ln, [
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionPrev",
						disabled: N(y) <= 1,
						onClick: n[6] ||= (e) => N(c).changeHistoryPage(-1)
					}, "上一页", 8, un),
					w("span", dn, S(N(R)), 1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionNext",
						disabled: N(y) * 20 >= N(k),
						onClick: n[7] ||= (e) => N(c).changeHistoryPage(1)
					}, "下一页", 8, fn)
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
				w("div", pn, [
					w("h2", mn, S(N(C) ? `巡检 #${N(C)} · 失败详情` : "巡检失败详情"), 1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[9] ||= (...e) => N(c).refreshFailures && N(c).refreshFailures(...e)
					}, "刷新"),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[10] ||= (e) => ae("failures")
					}, "关闭")
				]),
				n[21] ||= w("p", null, "保留本轮原始执行快照，后续重跑或删除账号不会改写；含已废跳过，套餐单独失败不计为查活失败。", -1),
				w("div", {
					ref_key: "failureContent",
					ref: W,
					id: "accountInspectionFailuresContent",
					"aria-live": "polite"
				}, [N(F) ? (r(), I("p", hn, S(N(F)), 1)) : N(O).length ? (r(), I("div", gn, [w("table", _n, [w("thead", null, [w("tr", null, [(r(), I(v, null, s([
					"账号",
					"邮箱",
					"类型",
					"时间",
					"原因"
				], (e) => w("th", {
					key: e,
					scope: "col"
				}, S(e), 1)), 64))])]), w("tbody", null, [(r(!0), I(v, null, s(N(O), (t, n) => (r(), I("tr", { key: String(t.account_id ?? n) }, [
					w("td", null, "#" + S(Number(t.account_id)), 1),
					w("td", null, S(t.email), 1),
					w("td", null, S(N(Ht)(t.status)), 1),
					w("td", null, S(e.deps.formatDateTime(t.failed_at)), 1),
					w("td", vn, S(t.error), 1)
				]))), 128))])])])) : (r(), I("p", yn, S(N(P) ? "本轮暂无查活失败或已废跳过。" : "正在读取本次失败记录…"), 1))], 512),
				w("div", bn, [
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresPrev",
						disabled: !N(P) || N(x) <= 1,
						onClick: n[11] ||= (e) => N(c).changeFailuresPage(-1)
					}, "上一页", 8, xn),
					w("span", Sn, S(N(z)), 1),
					w("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresNext",
						disabled: !N(P) || N(x) * 20 >= N(A),
						onClick: n[12] ||= (e) => N(c).changeFailuresPage(1)
					}, "下一页", 8, Cn)
				])
			], 544)
		], 64));
	}
}), [["__scopeId", "data-v-88e51d48"]]);
// src/features/accounts/useAccountEmailChange.ts
function Tn(e) {
	return JSON.parse(JSON.stringify(e));
}
function En(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(En), Object.freeze(e)), e;
}
function Dn(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function On(e) {
	return e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败，请稍后重试";
}
function kn(e) {
	return [...new Set((Array.isArray(e?.accountIds) ? e.accountIds : []).map(Number).filter((e) => Number.isSafeInteger(e) && e > 0).map(String))];
}
function An(e, t = {}) {
	let n = b(!1), r = b(0), i = b("single"), a = A(null), o = A(null), s = A([]), c = A([]), l = b(""), u = b("idle"), d = b(""), f = b(!1), p = O(() => u.value !== "ready" || !c.value.some((e) => e.enabled)), h = null, g = !1, _ = (e) => !g && h === e && r.value === e.generation && n.value;
	function v({ restoreFocus: e = !0 } = {}) {
		let i = h;
		i && (h = null, ++r.value, i.controller.abort(), n.value = !1, a.value = null, o.value = null, s.value = [], c.value = [], l.value = "", u.value = "idle", d.value = "", f.value = !1, t.closed?.(e, i.trigger, r.value));
	}
	async function y(n, r) {
		try {
			let t = Dn(await e.request("/api/email-sources", { signal: n.controller.signal }));
			if (!_(n)) return;
			c.value = En((Array.isArray(t.sources) ? t.sources : []).map((e) => {
				let t = Dn(e);
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
			u.value = "failed", c.value = [], l.value = "", d.value = `邮箱来源读取失败：${On(e)}`;
		}
		_(n) && t.sourcesReady?.(n.generation);
	}
	function x(e, p, m, _, b) {
		if (g) return !1;
		let x = En(Tn({
			..._,
			accountIds: p
		}));
		v({ restoreFocus: !1 });
		let S = {
			generation: ++r.value,
			mode: e,
			account: m,
			accountIds: En([...p]),
			context: x,
			trigger: b,
			controller: new AbortController(),
			submitting: !1
		};
		return h = S, i.value = e, a.value = m, s.value = S.accountIds, o.value = x, n.value = !0, u.value = "loading", l.value = "", d.value = "", c.value = [], f.value = !1, t.opened?.(S.generation), y(S, String(m?.email_source || "").trim().toLowerCase()), !0;
	}
	function S(t, n, r = null) {
		let i = Number(t), a = String(i), o = n?.rowHints?.find((e) => String(e.id) === a);
		return !Number.isSafeInteger(i) || i <= 0 || !kn(n).includes(a) || !o ? (e.notify("账号详情暂不可用，请先刷新列表"), !1) : x("single", [a], En({
			id: i,
			email: String(o.email || ""),
			email_source: String(o.email_source || "")
		}), n, r);
	}
	function C(t, n = null) {
		let r = kn(t);
		return r.length ? r.length > 500 ? (e.notify("单次最多换绑 500 个账号"), !1) : x("bulk", r, null, t, n) : (e.notify("请先选择账号"), !1);
	}
	function w(t, n) {
		try {
			Promise.resolve(t()).catch((t) => e.notify(n + On(t)));
		} catch (t) {
			e.notify(n + On(t));
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
			r = Dn(await e.request(t.mode === "bulk" ? "/api/accounts/email-change-bulk" : `/api/accounts/${t.account.id}/email-change`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(t.mode === "bulk" ? {
					account_ids: t.accountIds.map(Number),
					email_source: n
				} : { email_source: n })
			}));
		} catch (n) {
			_(t) && (d.value = `提交失败：${On(n)}`), e.notify("换绑邮箱失败: " + On(n));
			return;
		} finally {
			t.submitting = !1, _(t) && (f.value = !1);
		}
		let i = _(t), a = En({
			result: Tn(r),
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
var jn = [
	"aria-hidden",
	"data-account-id",
	"data-account-ids"
], Mn = {
	class: "email-change-dialog",
	role: "document"
}, Nn = { class: "email-change-head" }, Pn = { id: "emailChangeTitle" }, Fn = { id: "emailChangeAccountLabel" }, In = {
	class: "email-change-field",
	for: "emailChangeSource"
}, Ln = ["disabled"], Rn = { value: "" }, zn = [
	"value",
	"disabled",
	"title",
	"data-reason"
], Bn = ["hidden"], Vn = { class: "email-change-foot" }, Hn = ["disabled"], Un = /* @__PURE__ */ n({
	__name: "EmailChange",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, a = b(), c = b(), u = b(), d = !1, f = null;
		function m() {
			let e = f;
			f = null, e?.isConnected && e.focus({ preventScroll: !0 });
		}
		let h = An(i.deps, {
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
		}), { isOpen: _, account: y, accountIds: k, mode: A, sources: j, source: M, sourceStatus: P, sourceDisabled: F, error: L, submitting: R } = h, z = O(() => _.value && A.value === "bulk" ? "批量换绑邮箱" : "换绑邮箱"), B = O(() => _.value ? A.value === "bulk" ? `已选 ${k.value.length} 个账号 · 将按账号分别领取新邮箱` : `账号 #${y.value?.id} · 当前邮箱 ${y.value?.email || "-"}` : ""), V = O(() => P.value === "loading" ? "正在读取邮箱来源…" : P.value === "failed" ? "邮箱来源读取失败" : P.value === "ready" ? "请选择邮箱来源" : "打开弹窗后读取可用来源");
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
			class: D(["email-change-modal", { hidden: !N(_) }]),
			role: "dialog",
			"aria-modal": "true",
			"aria-hidden": !N(_),
			"aria-labelledby": "emailChangeTitle",
			"aria-describedby": "emailChangeNote",
			"data-account-id": N(_) && N(A) === "single" ? String(N(y)?.id) : "",
			"data-account-ids": N(_) && N(A) === "bulk" ? JSON.stringify(N(k).map(Number)) : "",
			onClick: t[3] ||= E((e) => G(), ["self"])
		}, [w("div", Mn, [w("div", Nn, [w("div", null, [
			t[4] ||= w("div", { class: "data-panel-kicker" }, "PROTOCOL OPERATION", -1),
			w("h2", Pn, S(z.value), 1),
			w("p", Fn, S(B.value), 1)
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
			onSubmit: E(K, ["prevent"])
		}, [
			w("label", In, [
				t[5] ||= w("span", null, "新邮箱来源", -1),
				o(w("select", {
					ref_key: "select",
					ref: c,
					id: "emailChangeSource",
					"onUpdate:modelValue": t[1] ||= (e) => p(M) ? M.value = e : null,
					name: "email_source",
					required: "",
					disabled: N(F),
					"aria-describedby": "emailChangeSourceHelp emailChangeSourceError"
				}, [w("option", Rn, S(V.value), 1), (r(!0), I(v, null, s(N(j), (e, t) => (r(), I("option", {
					key: `${e.value}:${t}`,
					value: e.value,
					disabled: !e.enabled,
					title: e.reason,
					"data-reason": e.reason
				}, S(e.label) + S(e.enabled ? "" : "（不可用）"), 9, zn))), 128))], 8, Ln), [[g, N(M)]]),
				t[6] ||= w("small", { id: "emailChangeSourceHelp" }, "系统会从所选邮箱池自动领取新地址，并读取新邮箱验证码。", -1),
				w("small", {
					id: "emailChangeSourceError",
					class: "email-change-error",
					role: "alert",
					hidden: !N(L)
				}, S(N(L)), 9, Bn)
			]),
			t[7] ||= w("div", {
				id: "emailChangeNote",
				class: "email-change-note"
			}, "换绑、Recent Login 和验证码校验全部走协议任务，不会启动浏览器。成功写回后会自动创建一次协议查活任务刷新 AT。", -1),
			w("div", Vn, [w("button", {
				id: "btnCancelEmailChange",
				type: "button",
				class: "jobs-tb-btn",
				onClick: t[2] ||= (e) => G()
			}, "取消"), w("button", {
				id: "btnSubmitEmailChange",
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				disabled: N(R)
			}, S(N(R) ? "提交中…" : "开始换绑"), 9, Hn)])
		], 32)])], 10, jn)]));
	}
});
// src/features/accounts/useC2aReimport.ts
function Wn(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Gn(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(Gn), Object.freeze(e)), e;
}
function Kn(e) {
	return Gn(JSON.parse(JSON.stringify(e)));
}
var qn = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败";
function Jn(e) {
	let t = /* @__PURE__ */ new Map();
	for (let n of [e.skipped, e.failed]) for (let e of Array.isArray(n) ? n : []) {
		let n = e && typeof e == "object" ? e : {}, r = String(n.reason || n.error || n.error_code || "服务端未返回原因，请重试");
		t.set(r, (t.get(r) || 0) + 1);
	}
	return t.size ? `；未入队原因：${[...t].slice(0, 3).map(([e, t]) => `${e}${t > 1 ? `（${t} 个）` : ""}`).join("；")}${t.size > 3 ? `；另有 ${t.size - 3} 类原因` : ""}` : "；未入队原因：服务端未返回原因，请重试";
}
function Yn(e) {
	return [
		"queued",
		"skipped",
		"failed"
	].flatMap((t, n) => (Array.isArray(e[t]) ? e[t] : []).map((e) => ({
		item: Wn(e),
		state: [
			"已入队",
			"未入队",
			"入队失败"
		][n]
	})));
}
function Xn(e, t = {}) {
	let n = b(!1), r = b(!1), i = b(""), a = A([]), o = A(null), s = null, c = null, l = !1, u = O(() => o.value ? Yn(o.value) : []), d = O(() => u.value.filter((e) => Number(e.item.task_id) > 0)), f = O(() => {
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
		return u.length ? (s = Kn(t), a.value = Object.freeze([...u]), c = o, r.value = !1, i.value = "", n.value = !0, !0) : (e.notify("请先选择账号"), !1);
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
			e.notify(n + qn(t));
		}
	}
	function _(e) {
		o.value = Kn(Wn(e));
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
			f = Wn(await e.request("/api/accounts/c2a/sync-bulk", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ account_ids: t })
			}));
		} catch (t) {
			e.notify("重新导入 C2A 失败: " + qn(t)), l || (i.value = `提交失败：${qn(t)}。请检查后再次提交。`), r.value = !1, d?.(), e.selectionChanged?.(o);
			return;
		}
		try {
			let t = Number(f.skipped_count ?? (Array.isArray(f.skipped) ? f.skipped.length : 0)) + Number(f.failed_count ?? (Array.isArray(f.failed) ? f.failed.length : 0)), n = t ? Jn(f) : "";
			f.accepted ? e.notify(`C2A 重新导入已入队 ${f.queued_count ?? (Array.isArray(f.queued) ? f.queued.length : 0)} 个，未入队 ${t} 个，请在任务中心查看结果${n}`) : (e.notify(t ? `C2A 已重新导入 ${f.updated_count || 0} 个，跳过/失败 ${t} 个${n}` : `C2A 已重新导入 ${f.updated_count || 0} 个`), await g(() => e.refreshAccounts(o), "C2A 请求已处理，页面更新失败: "));
		} catch (t) {
			e.notify("C2A 请求已处理，回执更新失败: " + qn(t));
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
var Zn = { class: "c2a-reimport-confirm-head" }, Qn = ["disabled"], $n = { class: "c2a-reimport-confirm-body" }, er = { class: "c2a-reimport-confirm-scope" }, tr = { id: "c2aReimportConfirmCountV2" }, nr = ["hidden"], rr = { class: "c2a-reimport-confirm-foot" }, ir = ["disabled"], ar = ["disabled"], or = /* @__PURE__ */ n({
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
		let d = Xn({
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
			w("div", Zn, [t[3] ||= w("div", null, [
				w("p", { class: "c2a-reimport-confirm-kicker" }, "本地 AT · 远端账号同步"),
				w("h3", { id: "c2aReimportConfirmTitle" }, "批量同步到 C2A"),
				w("p", { id: "c2aReimportConfirmDescription" }, "查到唯一的同邮箱 C2A 账号时覆盖 AT；未找到时新建账号。")
			], -1), w("button", {
				type: "button",
				class: "c2a-reimport-confirm-close",
				id: "btnCloseC2aReimportV2",
				disabled: N(p),
				onClick: t[0] ||= (e) => _(),
				"aria-label": "关闭 C2A 同步确认窗口"
			}, "×", 8, Qn)]),
			w("div", $n, [
				w("p", er, [
					t[4] ||= L("将为 ", -1),
					w("strong", tr, S(N(h).length), 1),
					t[5] ||= L(" 个已选账号创建同步任务。", -1)
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
					hidden: !N(m)
				}, S(N(m)), 9, nr)
			]),
			w("div", rr, [w("button", {
				type: "button",
				class: "jobs-tb-btn",
				id: "btnCancelC2aReimportV2",
				disabled: N(p),
				onClick: t[1] ||= (e) => _()
			}, "取消", 8, ir), w("button", {
				type: "button",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				id: "btnConfirmC2aReimportV2",
				disabled: N(p),
				onClick: t[2] ||= (...e) => N(d).submit && N(d).submit(...e)
			}, S(N(p) ? "正在提交…" : "提交并入队"), 9, ar)])
		], 544)]));
	}
}), sr = ["hidden"], cr = { class: "column-filter-summary-label" }, lr = [
	"data-registration-retry-result",
	"data-registration-retry-task-id",
	"data-registration-retry-run-id",
	"onClick"
], ur = /* @__PURE__ */ n({
	__name: "RegistrationRetryReceipt",
	props: { notify: { type: Function } },
	setup(e, { expose: t }) {
		let n = e, i = A(null), a = b(0), o = !1;
		function c(e) {
			return Array.isArray(e) ? Object.freeze(e.map(c)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, c(t)]))) : e;
		}
		let l = O(() => Array.isArray(i.value?.result.started) ? i.value.result.started : []), u = O(() => Array.isArray(i.value?.result.reused) ? i.value.result.reused : []), d = O(() => Array.isArray(i.value?.result.skipped) ? i.value.result.skipped : []), f = O(() => [...l.value, ...u.value]), p = O(() => {
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
			w("span", cr, S(i.value ? p.value : ""), 1),
			f.value.length ? (r(), I("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-tasks": "",
				onClick: t[0] ||= (e) => y()
			}, "打开任务中心")) : h("", !0),
			f.value.length || d.value.length ? (r(), I("details", { key: a.value }, [w("summary", null, "查看" + S(d.value.length ? "任务及跳过原因" : "任务"), 1), w("ul", null, [(r(!0), I(v, null, s(f.value, (e, t) => (r(), I("li", { key: `task-${t}` }, [L("账号 #" + S(e.account_id) + " · " + S(t < l.value.length ? "已创建" : "进行中") + " ", 1), w("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-result": t,
				"data-registration-retry-task-id": m(e) || void 0,
				"data-registration-retry-run-id": m(e) && e.run_id ? e.run_id : void 0,
				onClick: (t) => y([e])
			}, "查看任务" + S(g(e) ? ` #${g(e)}` : ""), 9, lr)]))), 128)), (r(!0), I(v, null, s(d.value, (e, t) => (r(), I("li", { key: `skipped-${t}` }, "账号 #" + S(e.account_id) + " · " + S(e.reason || e.error || "当前不可重跑"), 1))), 128))])])) : h("", !0)
		], 8, sr)]));
	}
}), dr = /* @__PURE__ */ n({
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
		let n = e, a = b(), o = b(), s = b(), c = b(), l = b(), u = b(), d = b(), p = A(), m = A(n.initialCapabilities), h = b(0), g = A({});
		function _() {
			if (!a.value) throw Error("账号列表正在加载，请稍后重试");
			return a.value;
		}
		let y = O(() => {
			h.value;
			let e = a.value?.getActionContext(), t = e ? Object.fromEntries(se.map((t) => [t.action, n.actions.isPending(t.action, e)])) : {};
			return t.reimportSelectedC2a = l.value?.isSubmitting === !0, {
				selectedCount: p.value?.selectedIds.length || 0,
				archived: p.value?.archived === "only",
				pending: t,
				labels: g.value
			};
		});
		async function x(e, t, r = null) {
			let i = n.actions.isSupported(e) ? n.actions.invoke(e, t, r) : n.callbacks.invoke(e, t, r);
			++h.value;
			try {
				await i;
			} finally {
				++h.value;
			}
		}
		let S = {
			...n.callbacks,
			invoke: x,
			onStateChange: (e) => {
				p.value = e, n.callbacks.onStateChange?.(e);
			},
			openDetail: (e, t, n, r) => {
				o.value ? o.value.open(e, t, n, r) : n.release();
			},
			closeConsumers: (e = !0) => {
				o.value?.close(e), n.callbacks.closeConsumers?.(e);
			}
		}, C = {
			notify: (e) => n.callbacks.notify?.(e),
			syncModalScrollLock: () => n.syncModalScrollLock()
		};
		return T(() => n.actions.dispose()), t({
			setVisible: (e) => {
				n.actions.setVisible(e), _().setVisible(e);
			},
			setArchived: (e) => _().setArchived(e),
			refresh: () => _().refresh(),
			pollStatuses: () => _().pollStatuses(),
			getAccountSelectionSnapshot: (...e) => _().getAccountSelectionSnapshot(...e),
			getActionContext: (...e) => _().getActionContext(...e),
			getRowSnapshot: (e) => _().getRowSnapshot(e),
			openPlanDetailsConsumer: (e) => _().openPlanDetailsConsumer(e),
			removeAcknowledgedSelection: (e) => _().removeAcknowledgedSelection(e),
			clearSelection: () => _().clearSelection(),
			setPage: (e) => _().setPage(e),
			setSize: (e) => _().setSize(e),
			updateQuery: (...e) => _().updateQuery(...e),
			updateFilters: (...e) => _().updateFilters(...e),
			resetFilters: () => _().resetFilters(),
			resetColumns: () => _().resetColumns(),
			openDetail: (e, t = null) => _().openDetail(e, t),
			closeDetail: (e = !0) => o.value?.close(e),
			isActionSupported: (e) => n.actions.isSupported(e),
			isActionPending: (e) => n.actions.isPending(e, _().getActionContext()),
			invokeAction: x,
			syncToolbarPending: () => {
				++h.value;
			},
			setToolbarBusyLabel: (e, t) => {
				let n = { ...g.value };
				t ? n[e] = t : delete n[e], g.value = n;
			},
			closeMoreMenus: () => _().closeMoreMenus(),
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
		}), (t, n) => (r(), I(v, null, [
			f(kt, {
				ref_key: "list",
				ref: a,
				adapter: e.adapter,
				api: e.api,
				presentation: e.presentation,
				callbacks: S
			}, {
				actions: i(() => [f(ve, {
					ref_key: "toolbar",
					ref: u,
					state: y.value,
					capabilities: m.value,
					runtime: e.toolbarRuntime,
					"get-context": () => _().getActionContext(),
					invoke: x,
					notify: S.notify
				}, null, 8, [
					"state",
					"capabilities",
					"runtime",
					"get-context",
					"notify"
				])]),
				_: 1
			}, 8, [
				"adapter",
				"api",
				"presentation"
			]),
			f(zt, {
				ref_key: "drawer",
				ref: o,
				api: e.detailApi,
				presentation: e.detailPresentation,
				callbacks: C
			}, null, 8, ["api", "presentation"]),
			f(wn, {
				ref_key: "inspection",
				ref: s,
				deps: e.inspectionDependencies
			}, null, 8, ["deps"]),
			f(Un, {
				ref_key: "emailChange",
				ref: c,
				deps: e.emailChangeDependencies
			}, null, 8, ["deps"]),
			f(or, {
				ref_key: "c2a",
				ref: l,
				deps: e.c2aDependencies
			}, null, 8, ["deps"]),
			f(ur, {
				ref_key: "registrationReceipt",
				ref: d,
				notify: S.notify
			}, null, 8, ["notify"])
		], 64));
	}
});
// src/api/accounts.ts
function fr(e) {
	return typeof e == "object" && !!e && !Array.isArray(e);
}
function pr(e, t) {
	return typeof e == "number" && Number.isSafeInteger(e) && e >= t;
}
function mr(e) {
	return fr(e) && e.ok === !0 && Array.isArray(e.items) && pr(e.total, 0) && pr(e.page, 1) && pr(e.page_size, 1) && pr(e.offset, 0) && pr(e.limit, 1) && typeof e.revision == "string";
}
function hr() {
	throw new ae("账号查询返回了无效的响应，请刷新后重试。", 200, "account_response_invalid");
}
function gr(e) {
	return {
		async list(t, n, r, i) {
			let a = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			}), o = await Z(`/api/accounts?${a}`, { signal: i });
			return mr(o) && o.compact === !0 && fr(o.facets) && Array.isArray(o.search_terms) || hr(), o;
		},
		async statuses(t, n, r, i) {
			let a = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			});
			a.set("compact", "1");
			let o = await Z(`/api/accounts/plan-check-status?${a}`, { signal: i });
			return mr(o) && fr(o.queue) && Array.isArray(o.status_fields) && o.status_fields.every((e) => typeof e == "string") || hr(), o;
		},
		async planDetails(e, t) {
			if (!/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
			let n = await Z(`/api/accounts/${encodeURIComponent(e)}/plan-details`, { signal: t });
			return fr(n) && n.ok === !0 && fr(n.item) && Object.hasOwn(n.item, "account_promotions") && Object.hasOwn(n.item, "promotion_query_snapshot") && Array.isArray(n.item.plan_check_country_results) || hr(), n;
		}
	};
}
// src/api/accountDetail.ts
function _r() {
	return { async roxyProfile(e, t) {
		if (!/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
		let n = await Z(`/api/accounts/${encodeURIComponent(e)}/roxy-profile`, { signal: t });
		if (!n || typeof n != "object" || Array.isArray(n) || !("ok" in n) || n.ok !== !0 || !("profile_id" in n) || n.profile_id !== null && typeof n.profile_id != "string" || !("window_name" in n) || n.window_name !== null && typeof n.window_name != "string") throw new ae("账号详情返回了无效的响应，请重新打开详情重试。", 200, "account_response_invalid");
		return {
			ok: !0,
			profile_id: n.profile_id,
			window_name: n.window_name
		};
	} };
}
// src/features/accounts/queuedActions.ts
var vr = {
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
}, yr = (e) => Object.prototype.hasOwnProperty.call(vr, e), br = (e) => e instanceof Error ? e.message : "请求失败，请稍后重试。";
function xr(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Sr(e) {
	if (e == null) return [];
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return e.map((e) => {
		if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
		return e;
	});
}
function $(e) {
	let t = Number(e || 0);
	if (!Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function Cr(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return [...new Set(e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	}))];
}
function wr(e) {
	return Array.isArray(e) ? Object.freeze(e.map(wr)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, wr(t)]))) : e;
}
function Tr(e, t) {
	return wr({
		accountIds: t.map(String),
		expectedEmails: { ...e.expectedEmails },
		querySnapshot: e.querySnapshot,
		archived: e.archived,
		rowHints: []
	});
}
function Er(e) {
	let t = [...Sr(e.skipped), ...Sr(e.failed)].map((e) => String(e.reason || e.error || "").replace(/\s+/g, " ").trim()).filter(Boolean);
	return t.length ? `；${t.slice(0, 3).map((e) => e.length > 80 ? `${e.slice(0, 80)}…` : e).join("；")}${t.length > 3 ? `；另有 ${t.length - 3} 条原因` : ""}` : "";
}
function Dr(e) {
	let t = Array.isArray(e) ? e.filter((e) => e && typeof e == "object") : [], n = (e) => t.find((t) => t.key === e), r = n("ACCOUNT_AT_REFRESH_DRIVER"), i = String(r?.value || "protocol").trim().toLowerCase() === "browser_roxy" ? "browser_roxy" : "protocol", a = n("ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED")?.value, o = a === !0 || String(a).trim().toLowerCase() === "true", s = String(n("OPENAI_PROTOCOL_VERSION")?.value || "v1").trim().toLowerCase(), c = ["v2", "v3"].includes(s) ? s : "v1", l = r ? i === "browser_roxy" ? "Roxy 指纹浏览器" : `协议刷新（${c}）` : "已保存的刷新驱动";
	return {
		description: i === "protocol" && c === "v3" ? `使用${l}先复用该账号有效的登录会话；会话失效或尚未保存时，按实际挑战完成密码、2FA 或邮箱验证，核对账号身份并保存最新 accessToken。` : `使用${l}重新登录，按实际挑战完成密码、2FA 或邮箱验证，并保存最新 accessToken。`,
		debugDescription: o ? "Roxy 刷新调试已开启：实际使用 Roxy 时将显示浏览器并全程抓包；失败保留窗口，可从任务日志查看现场并下载 HAR。" : ""
	};
}
function Or(e) {
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
function kr(e, t) {
	let n = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), i = !0, a = !1, o = 0, s = (e, t) => vr[e]?.single ? JSON.stringify([e, ...t.map(String)]) : e, c = (e) => !a && i && e === o && t.isOwnerActive();
	function l() {
		++o;
		for (let e of [...r]) e();
	}
	function u(n) {
		return c(n) ? new Promise((i) => {
			let a, o = () => {
				t.clearScheduled(a), r.delete(o), i(!1);
			};
			r.add(o), a = e.schedule(() => {
				r.delete(o), i(c(n));
			}, 1500);
		}) : Promise.resolve(!1);
	}
	async function d(e, n, r) {
		for (let i = 0; i < 30; i++) {
			if (!await u(r) || (await t.refresh(n), !c(r))) return;
			let i = e.map((e) => t.getRowSnapshot(String(e))).filter((e) => e != null);
			if (i.length && i.every((e) => !["queued", "running"].includes(String(e.deactivation_mail_scan_status || "")))) return;
		}
	}
	async function f(t, n = () => !0) {
		try {
			await t();
		} catch (t) {
			n() && e.notify(`请求已处理，但页面更新失败: ${br(t)}`);
		}
	}
	async function p(r, l, u = null) {
		if (!yr(r)) throw Error(`未支持的账号动作：${r}`);
		if (a || !i || e.canInvoke?.(r, u) === !1) return;
		let p = vr[r], m, h, g = o;
		try {
			let i = Cr(l);
			if (!i.length) {
				e.notify("请先选择账号");
				return;
			}
			if (p.single && i.length !== 1) throw Error("此操作只能选择一个账号");
			if (m = s(r, i), n.has(m)) {
				m = void 0;
				return;
			}
			n.add(m);
			let a = Tr(l, i), o = (t) => {
				h = e.beginBusy?.(r, u, t) || void 0;
			}, _ = async (t, n) => xr(await e.request(t, n === void 0 ? { method: "POST" } : {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(n)
			}));
			if (p.kind === "plan") {
				o("查询中…");
				let n;
				try {
					n = await _(p.single ? "/api/accounts/check-plan" : "/api/accounts/check-plan-bulk", p.single ? { account_id: i[0] } : { account_ids: i });
				} catch (n) {
					if (e.notify(p.error + br(n)), p.single) try {
						await t.pollStatuses(a);
					} catch (t) {
						e.notify(`套餐状态读取失败: ${br(t)}`);
					}
					return;
				}
				e.notify(p.single ? String(n.message || "套餐查询已加入后台队列") : `已入队 ${$(n.started_count)} 个，查询中跳过 ${$(n.busy_count)} 个，入队失败 ${$(n.failed_count)} 个${Sr(n.skipped).length ? `，跳过 ${Sr(n.skipped).length} 个` : ""}${Er(n)}`), await f(() => t.pollStatuses(a));
			} else if (p.kind === "live") {
				let n = t.operationWorkers(), r = p.single ? "确定查活这个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。" : `确定查活选中的 ${i.length} 个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。\n\n并发线程数：${n}`;
				if (!await e.confirm(r)) return;
				o("查活中…");
				let s = await _("/api/accounts/check-live-bulk", {
					account_ids: i,
					driver: t.configuredLiveCheckDriver()
				}), c = Sr(s.skipped).length, l = Sr(s.started);
				e.notify(`查活已入队 ${$(s.started_count)} 个，忙碌 ${$(s.busy_count)} 个，失败 ${$(s.failed_count)}${c ? `，跳过 ${c}` : ""}（配置驱动：${t.configuredLiveCheckDriver() || "默认"}，实际驱动：${s.live_check_driver || "未知"}）${Er(s)}`), await f(async () => {
					l[0]?.email && await t.openLiveLog(String(l[0].email)), await t.refresh(a), await t.refreshSummary();
				});
			} else if (p.kind === "token") {
				let n = t.operationWorkers();
				o("读取配置…");
				let s;
				try {
					s = await t.readConfig();
				} catch {
					s = t.fallbackConfig();
				}
				let c = Dr(s), l = i.length === 1 ? "这个账号" : `选中的 ${i.length} 个账号`;
				if (!await e.confirm(`确定刷新${l}的 AT 吗？\n\n${c.description}${c.debugDescription ? `\n\n${c.debugDescription}` : ""}${i.length > 1 ? `\n\n并发线程数：${n}` : ""}`)) return;
				t.updateBusyLabel?.(r, u, "刷新中…");
				let d = await _("/api/accounts/refresh-token-bulk", { account_ids: i }), p = Sr(d.skipped).length, m = Sr(d.started)[0];
				e.notify(`刷新AT已入队 ${$(d.started_count)} 个，忙碌 ${$(d.busy_count)} 个，失败 ${$(d.failed_count)}${p ? `，跳过 ${p}` : ""}${Er(d)}`), await f(async () => {
					m?.task_id ? await t.openAccountTaskLog(Number(m.task_id), m.run_id ? Number(m.run_id) : null) : m?.email && await t.openLiveLog(String(m.email)), await t.refresh(a), await t.refreshSummary();
				});
			} else if (p.kind === "mail") {
				o("扫描中…");
				let n = await _(p.single ? `/api/accounts/${i[0]}/check-deactivation-mail` : "/api/accounts/check-deactivation-mail-bulk", p.single ? void 0 : { account_ids: i });
				e.notify(p.single ? "封号邮件扫描已入队；不会刷新 AT" : `已入队 ${$(n.started_count)} 个，跳过 ${$(n.skipped_count)} 个；不会刷新 AT`), await f(async () => {
					c(g) && (await t.refresh(a), c(g) && (p.single || $(n.started_count) > 0) && await d(i, a, g));
				}, () => c(g));
			} else if (p.kind === "extract") {
				if (p.single) {
					let t = l.rowHints.find((e) => String(e.id) === String(i[0]));
					if (!t) {
						e.notify("账号不存在");
						return;
					}
					if (String(t.current_plan_type || t.plan_type || "").toLowerCase() !== "free" || Or(t) !== "free_trial") {
						e.notify("仅支持已确认 Plus 免费试用资格的 free 账号提链；折扣优惠不支持");
						return;
					}
					if (!await e.confirm(`确定为该账号提链吗？\n\n${t.email || "#" + i[0]}\n\n提链类型按配置使用，成功会消耗 1 次 CDK。`)) return;
				} else if (!await e.confirm(`确定为选中的 ${i.length} 个账号批量提链吗？\n\n仅处理已确认的 Plus 免费试用账号，折扣优惠和历史待复查账号会自动跳过。成功会按账号消耗 CDK 次数。`)) return;
				o("提链中…");
				let n = await _(p.single ? "/api/accounts/extract-link" : "/api/accounts/extract-link-bulk", p.single ? { account_id: i[0] } : { account_ids: i });
				if (p.single) {
					let t = n.fallback_from && n.link_type ? `；${String(n.fallback_from).toUpperCase()} 已失败，改用 ${String(n.link_type).toUpperCase()}` : "";
					e.notify(`提炼任务已入队${n.task_id ? ` · 任务 #${n.task_id}` : ""}${t}，可在任务中心查看日志`);
				} else {
					let t = $(n.skipped_count) + $(n.busy_count) + $(n.failed_count), r = Sr(n.started).filter((e) => e.fallback_from).length;
					e.notify(`已入队 ${$(n.started_count)} 个${t ? `，跳过/失败 ${t} 个` : ""}${r ? `，其中 ${r} 个已自动跳过失败类型` : ""}`);
				}
				await f(async () => {
					await t.reloadTasks(), await t.pollStatuses(a);
				});
			}
		} catch (t) {
			e.notify(p.error + br(t));
		} finally {
			m && n.delete(m), h?.();
		}
	}
	return {
		isSupported: yr,
		invoke: p,
		isPending: (e, t) => n.has(s(e, t.accountIds)),
		setVisible(e) {
			i = e, e || l();
		},
		dispose() {
			a = !0, l();
		}
	};
}
// src/features/accounts/setupActions.ts
var Ar = {
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
}, jr = {
	addPasswordSelectedAccounts: "password",
	addTwofaSelectedAccounts: "twofa",
	changePasswordSelectedAccounts: "password_change",
	changeTwofaSelectedAccounts: "twofa_change",
	completeSelectedAccounts: "complete"
}, Mr = /* @__PURE__ */ new Set([
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
]), Nr = (e, t) => Object.prototype.hasOwnProperty.call(e, t);
function Pr(e) {
	let t = e.indexOf(":");
	return t < 0 ? {
		name: e,
		value: ""
	} : {
		name: e.slice(0, t),
		value: e.slice(t + 1)
	};
}
function Fr(e) {
	let { name: t, value: n } = Pr(e);
	return t === "account-action" ? Nr(Ar, n) : t === "account-registration-task" ? /^[1-9]\d*$/.test(n) && Number.isSafeInteger(Number(n)) : !e.includes(":") && (Mr.has(t) || Nr(jr, t));
}
function Ir(e, t = !1) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let n = e;
	if (t && n.ok === !1) throw Error(typeof n.error == "string" ? n.error : "请求失败");
	return n;
}
function Lr(e) {
	if (e == null) return [];
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return e.map((e) => Ir(e));
}
function Rr(e) {
	let t = Number(e || 0);
	if (!Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function zr(e) {
	return Array.isArray(e) ? Object.freeze(e.map(zr)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, zr(t)]))) : e;
}
function Br(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return zr({
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
function Vr(e) {
	let t = Lr(e.started), n = Lr(e.reused), r = Lr(e.skipped);
	return zr({
		started: t,
		reused: n,
		skipped: r,
		started_count: Rr(e.started_count ?? t.length),
		reused_count: Rr(e.reused_count ?? n.length),
		skipped_count: Rr(e.skipped_count ?? r.length)
	});
}
function Hr(e) {
	return `注册重跑：已创建 ${e.started_count} 个，进行中 ${e.reused_count} 个，跳过 ${e.skipped_count} 个`;
}
var Ur = (e) => e instanceof Error ? e.message : "请求失败，请稍后重试。", Wr = (e) => e === "account-registration-retry" || e === "retryAccountRegistration", Gr = (e) => e.startsWith("account-") || e.startsWith("codex-");
function Kr(e, t) {
	let n = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), i = (e, t) => Gr(Pr(e).name) ? JSON.stringify([e, ...t]) : e;
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
			e.notify(`请求已处理，但页面更新失败: ${Ur(t)}`);
		}
	}
	async function s(e, n) {
		await o(() => t.refresh(e)), n && await o(async () => t.openTasks(n));
	}
	async function c(c, l, u = null) {
		if (!Fr(c)) throw Error(`未支持的账号动作：${Pr(c).name}`);
		if (e.canInvoke?.(c, u) === !1) return;
		let { name: d, value: f } = Pr(c), p = d === "account-action" ? f : Nr(jr, d) ? jr[d] : void 0, m = p ? Ar[p] : void 0, h, g, _ = [], v = !1, y = m ? `${m.label}失败: ` : d.includes("setup") || d === "setupSelectedAccounts" ? "补齐账号配置失败: " : d === "codex-stop" ? "停止失败: " : d === "codex-reset-retrying" ? "重置失败: " : d === "codex-retry" ? "触发补跑失败: " : d === "stopSelectedCodex" ? "停止选中补跑失败: " : d === "retrySelectedCodex" ? "批量补跑失败: " : d === "uploadSelectedCodexSub2" ? "批量上传 sub2 失败: " : "注册重跑提交失败: ";
		try {
			let y = Br(l), b = y.accountIds.map(Number), x = b[0];
			if (!b.length) {
				e.notify("请先选择账号");
				return;
			}
			if (Gr(d) && b.length !== 1) throw Error("此操作只能选择一个账号");
			let S = y.rowHints.find((e) => String(e.id) === String(x)), C = y.expectedEmails[String(x)] || S?.email || "", w = S?.email || C || `账号 #${x}`;
			if (d === "account-registration-task") {
				await a([{
					account_id: x,
					email: C,
					job_id: Number(f)
				}], y);
				return;
			}
			if (Wr(d) && y.accountIds.some((e) => r.has(e))) {
				e.notify("所选账号的注册重跑正在提交，请稍后查看结果");
				return;
			}
			if (h = i(c, y.accountIds), n.has(h)) {
				h = void 0;
				return;
			}
			if (n.add(h), Wr(d) && (_ = y.accountIds, _.forEach((e) => r.add(e))), p && !Gr(d) && ["password_change", "twofa_change"].includes(p) && b.length > 20) {
				e.notify("修改密码或修改 2FA 单次最多操作 20 个账号");
				return;
			}
			let T;
			if (T = d === "account-setup" ? `补齐账号配置？\n\n${w}\n\n只执行账号密码、套餐查询和 Authenticator 2FA，不执行 Codex 授权。` : d === "setupSelectedAccounts" ? `确定补齐选中的 ${b.length} 个账号配置吗？\n\n只执行：账号密码、套餐查询、Authenticator 2FA。\n不会执行 Codex 授权。` : m ? Gr(d) ? `${m.label}？\n\n${w}` : `确定${m.label}选中的 ${b.length} 个账号吗？` : d === "codex-stop" ? `确定停止该账号的 Codex 补跑吗？\n\n${C}\n\n会发送停止信号并将状态标记为“已停止”。` : d === "codex-reset-retrying" ? `确定重置该账号的 Codex「补跑中」状态吗？\n\n${C}\n\n重置后状态会变为“失败”，可再次点击“补跑 Codex”。` : d === "codex-retry" ? `重新跑 Codex 授权？\n\n${C}\n\n按实际验证要求使用邮箱 OTP（自动收）。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑会在后台进行，完成后状态自动更新。` : d === "stopSelectedCodex" ? `确定停止选中的 ${b.length} 个账号的 Codex 补跑吗？\n\n会向正在补跑的任务发送停止信号，并将状态标记为“已停止”；未在补跑的账号会自动跳过。` : d === "retrySelectedCodex" ? `批量补跑选中的 ${b.length} 个账号 Codex 授权？\n\n并发线程数：${t.operationWorkers()}\n\n按实际验证要求使用邮箱 OTP。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑中和已废号账号会自动跳过。` : d === "uploadSelectedCodexSub2" ? `确定上传选中的 ${b.length} 个账号的 Codex OAuth 凭证到 sub2api 吗？\n\n未完成 Codex OAuth 的账号会自动跳过。` : `确定为${b.length === 1 ? `账号 #${x}` : `选中的 ${b.length} 个账号`}${b.length === 1 && S?.registration_retry?.label || "重跑原注册任务"}吗？\n\n复用原注册记录，按当前进度重跑或补齐缺失步骤。正在执行、已完成或没有原任务的账号会显示对应结果。`, !await e.confirm(T)) return;
			g = e.beginBusy?.(c, u, Wr(d) ? "提交中…" : d === "uploadSelectedCodexSub2" ? "提交上传…" : void 0) || void 0;
			let E = async (t, n) => {
				let r = Ir(await e.request(t, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(n)
				}), !0);
				return v = !0, r;
			};
			if (d === "account-setup" || d === "setupSelectedAccounts") {
				let t = d === "account-setup", n = await E(t ? `/api/accounts/${x}/setup` : "/api/accounts/setup-bulk", t ? {} : { account_ids: b }), r = Lr(n.skipped).length;
				e.notify(t ? String(n.message || "已开始补齐账号配置") : r ? `已开始补齐 ${Rr(n.started_count)} 个，跳过 ${r} 个` : `已开始补齐 ${Rr(n.started_count)} 个账号配置`), await s(y, { filters: {
					target: t ? w : "",
					type: "account_setup_retry"
				} });
			} else if (p && m) {
				let t = d === "account-action", n = await E(t ? `/api/accounts/${x}/action` : "/api/accounts/action-bulk", t ? { action: p } : {
					account_ids: b,
					action: p
				}), r = Lr(n.skipped).length, i = Lr(n.started);
				e.notify(t ? String(n.message || `${m.label}已入队`) : r ? `已开始 ${Rr(n.started_count)} 个，跳过 ${r} 个` : String(n.message || `${m.label}已入队`));
				let a = t ? !!n.registration_resume : i.length > 0 && i.every((e) => e.registration_resume);
				await s(y, { filters: t ? {
					target: w,
					type: a ? "registration_resume" : m.type
				} : { type: a ? "registration_resume" : m.type } });
			} else if (d.startsWith("codex-")) {
				let t = await E(`/api/codex/${d === "codex-stop" ? "stop" : d === "codex-reset-retrying" ? "reset-retrying" : "retry"}`, d === "codex-reset-retrying" ? {
					email: C,
					status: "failed"
				} : { email: C });
				e.notify(String(t.message || (d === "codex-stop" ? "已发送停止信号" : d === "codex-reset-retrying" ? "已重置补跑状态" : "已开始补跑"))), await s(y, d === "codex-retry" ? { filters: {
					target: C,
					type: "codex_retry"
				} } : void 0);
			} else if (d === "stopSelectedCodex" || d === "retrySelectedCodex") {
				let t = d === "stopSelectedCodex", n = await E(`/api/codex/${t ? "stop" : "retry"}-bulk`, { account_ids: b }), r = Lr(n.skipped).length;
				e.notify(t ? `已停止 ${Rr(n.stopped_count)} 个${r ? `，跳过 ${r} 个` : ""}` : r ? `已开始 ${Rr(n.started_count)} 个，跳过 ${r} 个` : String(n.message || "已开始批量补跑")), await s(y, t ? void 0 : { filters: {
					target: "",
					type: "codex_retry"
				} });
			} else if (d === "uploadSelectedCodexSub2") {
				let n = await E("/api/accounts/codex/upload-sub2-bulk", { account_ids: b }), r = Rr(n.skipped_count ?? Lr(n.skipped).length) + Rr(n.failed_count ?? Lr(n.failed).length), i = r ? Jn(n) : "";
				n.accepted ? e.notify(`手动上传已入队 ${Rr(n.queued_count ?? Lr(n.queued).length)} 个，未入队 ${r} 个，请在任务中心查看结果${i}`) : (e.notify(`已上传 ${Rr(n.uploaded_count)} 个${r ? `，跳过/失败 ${r} 个${i}` : ""}`), await o(() => t.pollStatuses(y)));
			} else if (Wr(d)) {
				let n = Vr(await E(b.length === 1 ? `/api/accounts/${x}/registration-retry` : "/api/accounts/registration-retry-bulk", b.length === 1 ? {} : { account_ids: b }));
				if (e.notify(Hr(n)), t.showRegistrationResult(n, y, (e) => a(e, y)), b.length === 1) {
					let e = n.started[0] || n.reused[0];
					e && await a([e], y);
				}
				await t.refresh(y);
			}
		} catch (t) {
			v && (y = Wr(d) ? "注册重跑请求已处理，页面更新失败: " : "请求已处理，但页面更新失败: "), e.notify(y + Ur(t));
		} finally {
			h && n.delete(h), _.forEach((e) => r.delete(e)), g?.();
		}
	}
	return {
		isSupported: Fr,
		invoke: c,
		isPending: (e, t) => Wr(Pr(e).name) ? t.accountIds.some((e) => r.has(e)) : n.has(i(e, t.accountIds))
	};
}
// src/features/accounts/localMutations.ts
var qr = (e) => e === "only" ? "已归档账号" : e === "all" ? "全部账号" : "未归档账号", Jr = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败，请稍后重试。";
function Yr(e) {
	let t = e.indexOf(":");
	return {
		name: t < 0 ? e : e.slice(0, t),
		value: t < 0 ? void 0 : e.slice(t + 1)
	};
}
function Xr(e) {
	let { name: t, value: n } = Yr(e);
	return ["account-archive", "account-email-invalid"].includes(t) ? n === "0" || n === "1" : t === "setAccountsEmailInvalid" ? n === void 0 || n === "0" || n === "1" : n === void 0 && [
		"account-delete",
		"account-restore",
		"archiveSelectedAccounts",
		"deleteSelectedAccounts",
		"deleteDeactivatedAccounts"
	].includes(t);
}
function Zr(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Qr(e) {
	let t = Number(e);
	if (e == null || e === "" || typeof e == "boolean" || !Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function $r(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return [...new Set(e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	}))];
}
function ei(e, t) {
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return [...new Set(e.map((e) => Zr(e).id).filter((e) => (typeof e == "number" || typeof e == "string") && t.includes(Number(e))).map(String))];
}
function ti(e) {
	let t = /* @__PURE__ */ new Set(), n = (e, t) => e.startsWith("account-") ? JSON.stringify([e, ...t.accountIds]) : Yr(e).name;
	async function r(t, n, r = !1) {
		let i = r ? new AbortController() : void 0, a = i ? setTimeout(() => i.abort(), 3e4) : void 0;
		try {
			return Zr(await e.request(t, {
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
		i && e.notify(`${r ? "操作已处理，" : ""}页面刷新失败: ${Jr(i.reason)}`);
	}
	async function a(a, o, s = null) {
		if (!Xr(a)) throw Error(`未支持的账号动作：${Yr(a).name}`);
		if (e.canInvoke?.(a, s) === !1) return;
		let { name: c, value: l } = Yr(a), u = c === "deleteDeactivatedAccounts", d = c === "account-email-invalid" || c === "setAccountsEmailInvalid", f, p, m = !1, h = !1, g = !1, _ = u ? "删除请求失败，请刷新核实：" : d ? "更新邮箱失效标记失败: " : c === "account-restore" ? "恢复账号失败: " : c === "deleteSelectedAccounts" ? "批量删除失败: " : "删除失败: ";
		try {
			let i = u ? [] : $r(o), v = o.archived;
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
				}), d = Qr(u.updated_count), f = Array.isArray(u.skipped) ? u.skipped.length : 0;
				h = !0, e.notify(`${n ? "已标记邮箱失效" : "已清除本地邮箱失效标记"} ${d} 个${f ? `，跳过 ${f} 个（邮箱可能已变更）` : ""}`);
			} else if (u) {
				if (![
					"0",
					"only",
					"all"
				].includes(v)) throw Error("归档范围无效");
				if (!await e.confirm(`确定删除「${qr(v)}」范围内全部已废账号？\n\n不限当前页，不受勾选、搜索或其他筛选影响。仅删除本地账号记录，保留邮箱池和巡检历史。此操作不可撤销。`)) return;
				p = e.beginBusy?.(a, s) || void 0, m = !0, g = !0;
				let t = Qr((await r("/api/accounts/delete-deactivated", { archived: v }, !0)).deleted_count);
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
					S = ei(b[t ? "updated" : "deleted"], i);
					let e = Qr(b[t ? "updated_count" : "deleted_count"]), n = Array.isArray(b.skipped) ? b.skipped.length : 0;
					C = `已${d} ${e} 个${n ? `，跳过 ${n} 个` : ""}`;
				} else {
					if (b[t ? "updated" : "deleted"] !== !0 || (t || b.id !== void 0) && String(b.id) !== String(y)) throw Error("服务端未确认账号操作结果");
					S = [String(y)], C = t ? u ? "账号已归档" : "账号已恢复" : "账号已删除";
				}
				h = !0, g = !0, S.length && e.removeAcknowledgedSelection(S, o), e.notify(C);
			}
		} catch (t) {
			e.notify(`${h ? "操作已处理，页面更新失败: " : _}${Jr(t)}`);
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
		isSupported: Xr,
		invoke: a,
		isPending: (e, r) => t.has(n(e, r))
	};
}
// src/features/accounts/actions.ts
var ni = {
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
}, ri = {
	copy_line: "账号整行已复制",
	chatgpt_session: "ChatGPT session 已复制",
	account_password: "账号密码已复制",
	totp_secret: "TOTP 密钥已复制",
	access_token: "Token 已复制"
}, ii = {
	downloadSelectedAccountTxt: "生成 TXT 失败: ",
	downloadSelectedAccountSessions: "下载 Session 失败: ",
	downloadSelectedCpa: "下载 CPA 失败: "
}, ai = (e, t) => Object.prototype.hasOwnProperty.call(e, t);
function oi(e) {
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
function si(e) {
	let { name: t, value: n, hasValue: r } = oi(e);
	return t === "account-copy-secret" ? r && ai(ri, n) : !r && (t === "account-totp-copy" || ai(ni, t) || ai(ii, t));
}
function ci(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function li(e) {
	if (!e) return "";
	if (typeof e != "string") throw Error("服务端响应格式无效");
	return e;
}
function ui(e) {
	let t = Number(e || 0);
	if (!Number.isFinite(t) || !Number.isInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function di(e) {
	if (e.download_url == null || e.download_url === "") throw Error("服务端未返回下载地址");
	if (typeof e.download_url != "string" || e.filename != null && typeof e.filename != "string") throw Error("服务端响应格式无效");
	if (!e.download_url.trim()) throw Error("服务端未返回下载地址");
	return {
		url: e.download_url,
		filename: e.filename || ""
	};
}
function fi(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	let t = e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	});
	return Object.freeze([...new Set(t)]);
}
function pi(e) {
	return e instanceof Error ? e.message : "请求失败，请稍后重试。";
}
function mi(e) {
	let t = e.queued ? kr(e, e.queued) : void 0, n = e.setup ? Kr(e, e.setup) : void 0, r = e.local ? ti({
		...e.local,
		request: e.request,
		notify: e.notify,
		confirm: e.confirm,
		canInvoke: e.canInvoke,
		beginBusy: e.beginBusy
	}) : void 0, i = /* @__PURE__ */ new Set(), a = (e, t) => e.startsWith("account-") ? JSON.stringify([e, ...t.map(String)]) : e, o = async (t, n) => ci(await e.request(t, {
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
		return n.values.map((e) => li(ci(e).value)).filter(Boolean);
	}
	async function c(c, l, u = null) {
		if (t?.isSupported(c)) return t.invoke(c, l, u);
		if (n?.isSupported(c)) return n.invoke(c, l, u);
		if (r?.isSupported(c)) return r.invoke(c, l, u);
		if (!si(c)) throw Error(`未支持的账号动作：${oi(c).name}`);
		if (e.canInvoke?.(c, u) === !1) return;
		let { name: d, value: f } = oi(c), p = ai(ni, d) ? ni[d] : void 0, m = p?.error ?? ii[d] ?? (d === "account-totp-copy" ? "复制验证码失败: " : "复制失败: "), h, g, _ = !1, v = () => {
			h && i.delete(h);
			let e = g;
			g = void 0, e?.();
		};
		try {
			let t = fi(l);
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
				let n = li(ci(await e.request(`/api/accounts/${t[0]}/secret?field=${encodeURIComponent(f)}`)).value);
				if (!n) {
					e.notify("可复制内容为空");
					return;
				}
				await e.clipboard(n), e.notify(ri[f]);
			} else if (d === "account-totp-copy") {
				let n = ci(await e.request(`/api/accounts/${t[0]}/totp-code`)), r = li(n.code);
				if (!r) throw Error("验证码为空");
				let i = ui(n.remaining_seconds), a = await e.clipboard(r, !1);
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
				}), { url: r, filename: i } = di(n), a = ui(n.added_count), s = ui(n.skipped_count);
				await e.downloadUrl(r, i), e.notify(a === 0 ? `没有可下载的 Session，已生成结果清单，跳过 ${s} 个；开始下载，分类原因见 ZIP 内 manifest.json；Session 缺失或无效的账号请先刷新 AT，读取失败的账号请重试` : `已打包 ${a} 个账号 Session，跳过 ${s} 个；开始下载，结果见 ZIP 内 manifest.json`);
			} else if (d === "downloadSelectedCpa") {
				let n = await o("/api/accounts/download-cpa-bulk", {
					account_ids: t,
					prepare: !0
				}), { url: r, filename: i } = di(n), a = ui(n.error_count);
				await e.downloadUrl(r, i), e.notify(`已生成 ZIP，开始下载${a ? `（${a} 个失败见 manifest）` : ""}`), e.schedule(() => {
					Promise.resolve().then(() => e.reloadCodex()).catch((t) => e.notify(`下载已开始，但 Codex 列表刷新失败: ${pi(t)}`));
				}, 1200);
			}
		} catch (t) {
			e.notify(m + pi(t));
		} finally {
			_ ? e.schedule(v, 1200) : v();
		}
	}
	return {
		isSupported: (e) => si(e) || t?.isSupported(e) === !0 || n?.isSupported(e) === !0 || r?.isSupported(e) === !0,
		invoke: c,
		isPending: (e, o) => i.has(a(e, o.accountIds)) || t?.isPending(e, o) === !0 || n?.isPending(e, o) === !0 || r?.isPending(e, o) === !0,
		setVisible: (e) => t?.setVisible(e),
		dispose: () => t?.dispose()
	};
}
// src/features/accounts/browserDownloads.ts
function hi(e) {
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
function gi(e, t) {
	let n = te(t.query), r = hi({
		document,
		origin: window.location.origin,
		urls: URL,
		schedule: (e, t) => setTimeout(e, t)
	}), i = mi({
		...t.actionDependencies,
		request: Z,
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
	return k(dr, {
		adapter: n,
		api: gr(n),
		presentation: Pe(t.presentation),
		callbacks: t.callbacks,
		detailApi: _r(),
		detailPresentation: t.detailPresentation,
		syncModalScrollLock: t.syncModalScrollLock,
		actions: i,
		inspectionDependencies: {
			...t.inspectionDependencies,
			request: Z
		},
		emailChangeDependencies: {
			...t.emailChangeDependencies,
			request: Z
		},
		c2aDependencies: {
			...t.c2aDependencies,
			request: Z
		},
		initialCapabilities: t.capabilities,
		toolbarRuntime: a
	}).mount(e);
}
export { gi as mountAccounts };
