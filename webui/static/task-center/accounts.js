import { $ as e, A as t, C as n, F as r, G as i, H as a, K as o, L as s, M as c, N as l, P as u, S as d, X as f, Z as p, _ as m, a as h, c as g, d as _, dt as v, et as y, f as b, ft as x, g as S, h as C, j as w, l as T, lt as E, m as D, n as O, nt as k, o as A, s as j, st as M, t as N, tt as P, v as F, x as I } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { a as L, i as R, n as z, o as B, r as V, s as H, t as U } from "./ListFilterSummary-_oaD8AlZ.js";
import { t as W } from "./ListPagination-BjETSj81.js";
import { a as G, i as K, n as q, o as J, r as Y, s as ee, t as te } from "./queryAdapter-C1wcY8t-.js";
import { t as ne } from "./useColumnWidths-D1sKP53m.js";
import { t as re } from "./errorLabels-B-XqaTSM.js";
import { n as ie, r as X, t as ae } from "./client-BBEPwkQG.js";
// src/features/accounts/accountToolbar.ts
var Z = Object.freeze([
	"操作",
	"批次与巡检",
	"复制与导出",
	"资产管理"
]), oe = Object.freeze([
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
]), se = "turb_account_action_usage_v1", ce = Object.freeze([
	"btnCheckSelectedLiveV2",
	"btnCheckSelectedPlansV2",
	"btnRefreshSelectedTokenV2",
	"btnExtractSelectedLinksV2",
	"btnAddTwofaSelectedAccountsV2"
]);
function le(e, t) {
	let n = [...ce, ...e.filter((e) => !ce.includes(e))];
	return [...e].sort((e, r) => (t[r] || 0) - (t[e] || 0) || n.indexOf(e) - n.indexOf(r)).slice(0, 5);
}
function ue(t, n, r) {
	let i = k({}), a = k(le(t, {})), o, s = !1;
	function c() {
		let e = i.value;
		try {
			let t = n.storage.getItem(se);
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
		let e = le(t, i.value);
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
			n.storage.setItem(se, JSON.stringify(r));
		} catch {}
		u();
	}
	let f = n.addStorageListener((e) => {
		e.key === "turb_account_action_usage_v1" && u();
	});
	return p(() => {
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
var de = {
	class: "accounts-command-deck",
	id: "accountsCommandDeck"
}, fe = {
	class: "list-selection-hint",
	id: "accountsSelectedHintV2"
}, pe = { class: "toolbar-overflow-menu" }, me = { class: "toolbar-overflow-section-title" }, he = {
	class: "acc-v2-btn-group account-quick-actions",
	id: "accountsQuickActionsV2",
	role: "group",
	"aria-label": "常用账号操作，按此浏览器使用次数排序",
	title: "显示此浏览器使用次数最多的五项操作，批量操作一次算一次"
}, ge = [
	"id",
	"disabled",
	"title",
	"data-feature",
	"data-feature-base-title",
	"aria-disabled",
	"onClick"
], _e = /*#__PURE__*/ N(/* @__PURE__ */ n({
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
		let n = e, i = y(), a = y(), o = y(!1), l = /* @__PURE__ */ new Map(), u = /* @__PURE__ */ new Map(), d = k(/* @__PURE__ */ new Set()), f = ue(oe.map((e) => e.id), n.runtime, () => {
			let e = i.value, t = e?.ownerDocument;
			return !!(a.value?.open || t?.querySelector("dialog[open]") || e?.contains(t?.activeElement ?? null));
		});
		function p(e, t, n) {
			let r = e;
			n && typeof n == "object" && "nodeType" in n ? r.set(t, n) : r.delete(t);
		}
		function h(e) {
			let t = f.quickIds.value.indexOf(e.id);
			return t >= 0 ? u.get(t) : l.get(e.id);
		}
		let g = (e) => e.feature ? n.capabilities[e.feature] : void 0, v = (e) => g(e)?.enabled === !1, T = (e) => e.selection && n.state.selectedCount === 0 || d.value.has(e.action) || !!n.state.pending?.[e.action], D = (e) => n.state.labels?.[e.action] || (e.id === "btnArchiveSelectedAccountsV2" && n.state.archived ? "恢复选中" : e.label), O = (e) => e.id === "btnArchiveSelectedAccountsV2" && n.state.archived ? "把选中的归档账号恢复到默认账号列表" : e.title, A = (e) => v(e) ? `不可用：${g(e)?.reason || "缺少必要配置"}` : O(e);
		async function j(e, t) {
			let r = t.currentTarget;
			if (!(T(e) || v(e) || r.disabled || r.getAttribute("aria-disabled") === "true")) {
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
		let N;
		return c(() => {
			N = i.value?.ownerDocument, N?.addEventListener("close", f.schedule, !0), o.value = !0, f.refresh();
		}), w(() => N?.removeEventListener("close", f.schedule, !0)), t({ refreshQuickActions: f.refresh }), (t, n) => (r(), F("div", de, [C("div", {
			ref_key: "toolbar",
			ref: i,
			class: E(["jobs-toolbar-v2 list-action-toolbar", { "has-selection": e.state.selectedCount > 0 }]),
			id: "accountsToolbarV2",
			onFocusout: n[1] ||= (...e) => M(f).schedule && M(f).schedule(...e)
		}, [
			C("span", fe, x(e.state.selectedCount ? `已选 ${e.state.selectedCount} 个账号` : "选择账号后批量操作"), 1),
			C("details", {
				ref_key: "more",
				ref: a,
				class: "toolbar-overflow",
				id: "accountsMoreActionsV2",
				onToggle: n[0] ||= (...e) => M(f).schedule && M(f).schedule(...e)
			}, [n[2] ||= C("summary", null, "批量操作", -1), C("div", pe, [(r(!0), F(_, null, s(M(Z), (e) => (r(), F("div", {
				key: e,
				class: "toolbar-overflow-section toolbar-overflow-section--wide"
			}, [C("span", me, x(e), 1), (r(!0), F(_, null, s(M(oe).filter((t) => t.section === e), (e) => (r(), F("span", {
				key: e.id,
				ref_for: !0,
				ref: (t) => p(M(l), e.id, t),
				class: "account-action-slot"
			}))), 128))]))), 128))])], 544),
			C("div", he, [(r(), F(_, null, s(5, (e) => C("span", {
				key: e,
				ref_for: !0,
				ref: (t) => p(M(u), e - 1, t),
				class: "account-action-slot"
			}, null, 512)), 64))])
		], 34), o.value ? (r(!0), F(_, { key: 0 }, s(M(oe), (e) => (r(), S(b, {
			key: e.id,
			to: h(e)
		}, [C("button", {
			type: "button",
			id: e.id,
			class: E([e.className, { "feature-unavailable": v(e) }]),
			disabled: T(e),
			title: A(e),
			"data-feature": g(e) ? e.feature : void 0,
			"data-feature-base-title": g(e) ? O(e) : void 0,
			"aria-disabled": g(e) ? v(e) : void 0,
			onClick: (t) => j(e, t)
		}, x(D(e)), 11, ge)], 8, ["to"]))), 128)) : m("", !0)]));
	}
}), [["__scopeId", "data-v-d8d5d1f2"]]), ve = { class: "ac-filter-fields" }, ye = {
	key: 0,
	class: "ac-filter-field"
}, be = ["value"], xe = {
	key: 1,
	class: "ac-filter-options"
}, Se = { class: "ac-sr-only" }, Ce = ["checked"], we = [
	"value",
	"checked",
	"onChange"
], Te = [
	"type",
	"inputmode",
	"value",
	"placeholder",
	"onInput"
], Ee = { class: "ac-filter-actions" }, De = /* @__PURE__ */ n({
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
		let n = e, a = t, c = y("id"), l = D(() => n.column || q.find((e) => e.key === c.value) || q[0]), u = D(() => n.column ? Y(n.query, n.column) : q.some((e) => Y(n.query, e))), d = D(() => G(n.query, n.label).find((e) => e.key === l.value.key)?.label || ""), f = D(() => K(n.query, n.facets, l.value, n.label)), p = D(() => J(n.query, l.value.key)), v = D(() => l.value.kind === "date-range" ? ["date_from", "date_to"] : [l.value.key]);
		function b(e, t) {
			let n = new Set(p.value);
			t ? n.add(e) : n.delete(e), a("change", l.value.key, [...n]);
		}
		function w() {
			a("clear", l.value.key), a("update:open", !1);
		}
		return (t, n) => (r(), S(V, {
			label: e.column?.label || "账号",
			"trigger-label": e.column ? void 0 : "筛选",
			active: u.value,
			summary: d.value,
			open: e.open,
			"onUpdate:open": n[4] ||= (e) => a("update:open", e)
		}, {
			default: i(() => [C("div", ve, [
				e.column ? m("", !0) : (r(), F("label", ye, [n[5] ||= I("筛选列", -1), o(C("select", {
					"onUpdate:modelValue": n[0] ||= (e) => c.value = e,
					"aria-label": "选择账号筛选列"
				}, [(r(!0), F(_, null, s(M(q), (e) => (r(), F("option", {
					key: e.key,
					value: e.key
				}, x(e.label), 9, be))), 128))], 512), [[h, c.value]])])),
				l.value.kind === "enum" ? (r(), F("fieldset", xe, [
					C("legend", Se, x(l.value.label) + "，可多选", 1),
					C("label", null, [C("input", {
						type: "checkbox",
						checked: !p.value.length,
						onChange: n[1] ||= (e) => a("change", l.value.key, [])
					}, null, 40, Ce), n[6] ||= C("span", null, "全部", -1)]),
					(r(!0), F(_, null, s(f.value, (e) => (r(), F("label", { key: e.value }, [
						C("input", {
							type: "checkbox",
							value: e.value,
							checked: p.value.includes(e.value),
							onChange: (t) => b(e.value, t.target.checked)
						}, null, 40, we),
						C("span", null, x(e.label), 1),
						C("small", null, x(e.count), 1)
					]))), 128))
				])) : (r(!0), F(_, { key: 2 }, s(v.value, (t, i) => (r(), F("label", {
					key: t,
					class: "ac-filter-field"
				}, [I(x(l.value.kind === "date-range" ? i ? "截止日期" : "开始日期" : l.value.label), 1), C("input", {
					type: l.value.kind === "date-range" ? "date" : "text",
					inputmode: l.value.key === "id" ? "numeric" : void 0,
					value: M(ee)(e.query, t),
					placeholder: l.value.placeholder,
					autocomplete: "off",
					onInput: (e) => a("change", t, e.target.value),
					onKeydown: n[2] ||= g(T((e) => a("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, Te)]))), 128)),
				C("div", Ee, [C("button", {
					type: "button",
					class: "ac-link",
					onClick: w
				}, "清除此列"), C("button", {
					type: "button",
					class: "ac-button",
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
}), Oe = [
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
], ke = [
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
], Ae = ke.map((e) => e / ke.reduce((e, t) => e + t, 0) * 1500);
function je(e) {
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
var Me = [
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
function Ne(e) {
	if (!(e instanceof Element)) return;
	let t = e.closest("button,[data-copy-id]");
	if (!t || t.hasAttribute("disabled") || t.getAttribute("aria-disabled") === "true" || t.classList.contains("feature-unavailable")) return;
	let n = Me.find((e) => t.hasAttribute(`data-${e}`));
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
var Pe = ["aria-busy"], Fe = ["data-stale"], Ie = [
	"checked",
	"indeterminate",
	"disabled"
], Le = [
	"aria-label",
	"onPointerdown",
	"onKeydown"
], Re = { id: "accountsBodyV2" }, ze = ["data-account-row", "onClick"], Be = { class: "col-check" }, Ve = [
	"data-account-id",
	"aria-label",
	"checked",
	"disabled",
	"onChange"
], He = { class: "col-id" }, Ue = { class: "col-email" }, We = ["disabled", "data-account-detail-id"], Ge = { class: "acc-v2-email" }, Ke = {
	key: 0,
	class: "pill status-used",
	title: "该账号已归档"
}, qe = { class: "acc-v2-sub account-cell-line account-cell-line--sub account-email-meta" }, Je = { class: "account-email-name" }, Ye = ["innerHTML"], Xe = { class: "acc-mobile-meta" }, Ze = { class: "col-source" }, Qe = { class: "col-registration-driver" }, $e = ["data-label"], et = ["innerHTML"], tt = { class: "col-actions" }, nt = { class: "account-cell-lines acc-v2-actions" }, rt = ["disabled", "data-account-detail-id"], it = ["disabled"], at = ["onClick", "innerHTML"], ot = { key: 0 }, st = {
	colspan: "16",
	class: "ac-empty"
}, ct = /* @__PURE__ */ n({
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
		let o = e, l = n, { widths: f, total: p, resize: h, resizeWithKeyboard: b, resetColumns: O } = ne({
			defaults: Ae,
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
		}), k = y(), A = y(null);
		function j(e) {
			if (!o.stale) return e;
			let t = document.createElement("template");
			return t.innerHTML = e, t.content.querySelectorAll("button,input,select,textarea").forEach((e) => e.setAttribute("disabled", "")), t.content.querySelectorAll("a,[role=\"button\"],[data-copy-id]").forEach((e) => {
				e.setAttribute("aria-disabled", "true"), e.setAttribute("tabindex", "-1");
			}), t.innerHTML;
		}
		let N = D(() => (o.stale && o.loading ? [] : o.items).map((e) => ({
			row: e,
			id: String(e.id),
			cells: Object.fromEntries(Oe.filter((e) => e.cell).map((t) => [t.cell, j(o.presentation.cell(t.cell, e))])),
			menu: o.presentation.menu(e),
			mobile: o.presentation.mobileSummary(e),
			tone: o.presentation.rowTone(e)
		}))), P = (e) => q.find((t) => t.key === e);
		function V(e, t) {
			if (o.stale || !o.visible) {
				e.preventDefault(), e.stopPropagation();
				return;
			}
			let n = e.target instanceof Element ? e.target : null, r = n?.closest("[data-account-detail-id]");
			if (r) {
				e.preventDefault(), e.stopPropagation(), l("detail", String(t.id), r);
				return;
			}
			let i = Ne(e.target);
			i ? (e.preventDefault(), e.stopPropagation(), A.value = null, l("action", i.action, String(t.id), i.trigger)) : window.matchMedia("(max-width:860px)").matches && !n?.closest("button,a,input,label,[role=\"dialog\"]") && l("detail", String(t.id), null);
		}
		function U() {
			A.value = null;
		}
		function W(e) {
			e.target instanceof Element && e.target.closest(".ac-row-menu") || U();
		}
		return a(() => o.visible, (e) => {
			e || U();
		}), a(() => o.stale, (e) => {
			e && U();
		}), a(() => o.items, (e) => {
			A.value && !e.some((e) => String(e.id) === A.value) && U();
		}), c(() => {
			window.addEventListener("resize", U), window.addEventListener("scroll", W, !0), k.value && l("rendered", k.value);
		}), u(() => {
			k.value && l("rendered", k.value);
		}), w(() => {
			window.removeEventListener("resize", U), window.removeEventListener("scroll", W, !0);
		}), t({
			resetColumns: O,
			closeMenu: U
		}), (t, n) => (r(), F("div", {
			ref_key: "root",
			ref: k,
			class: "accounts-table-v2-wrap ac-table-scroll",
			tabindex: "0",
			"aria-label": "账号列表，可横向滚动",
			"aria-busy": e.loading,
			onScroll: U
		}, [C("table", {
			class: "accounts-table-v2 ac-table",
			style: v({ width: `${M(p)}px` }),
			"data-stale": e.stale || void 0
		}, [
			n[5] ||= C("caption", { class: "ac-sr-only" }, "账号资产，支持跨页选择", -1),
			C("colgroup", null, [(r(!0), F(_, null, s(M(f), (e, t) => (r(), F("col", {
				key: t,
				style: v({ width: `${e}px` })
			}, null, 4))), 128))]),
			C("thead", null, [C("tr", null, [(r(!0), F(_, null, s(M(Oe), (t, i) => (r(), F("th", {
				key: t.key,
				scope: "col",
				class: E(t.className)
			}, [t.key === "selection" ? (r(), F("input", {
				key: 0,
				id: "accountsSelectAllV2",
				type: "checkbox",
				"aria-label": "全选当前页账号",
				checked: e.pageSelected,
				indeterminate: e.pageIndeterminate,
				disabled: e.stale || !e.items.length,
				onChange: n[0] ||= (e) => l("selectPage", e.target.checked)
			}, null, 40, Ie)) : t.filter ? (r(), S(De, {
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
			])) : (r(), F(_, { key: 2 }, [I(x(t.label), 1)], 64)), i ? (r(), F("button", {
				key: 3,
				type: "button",
				class: "ac-column-resize",
				"aria-label": `调整${t.label}列宽，方向键调整`,
				onPointerdown: T((e) => M(h)(i, e), ["prevent"]),
				onKeydown: [g(T((e) => M(b)(i, -10), ["prevent"]), ["left"]), g(T((e) => M(b)(i, 10), ["prevent"]), ["right"])]
			}, null, 40, Le)) : m("", !0)], 2))), 128))])]),
			C("tbody", Re, [(r(!0), F(_, null, s(N.value, (t) => (r(), F("tr", {
				key: t.id,
				"data-account-row": t.id,
				class: E({ "ac-row-selected": e.selected.has(t.id) }),
				onClick: (e) => V(e, t.row)
			}, [
				C("td", Be, [C("input", {
					type: "checkbox",
					class: "account-row-check",
					"data-account-id": t.id,
					"aria-label": `选择账号 ${t.row.email || t.id}`,
					checked: e.selected.has(t.id),
					disabled: e.stale,
					onChange: (e) => l("select", t.id, e.target.checked)
				}, null, 40, Ve)]),
				C("td", He, [d(z, { text: `#${t.id}` }, null, 8, ["text"])]),
				C("td", Ue, [
					C("button", {
						type: "button",
						class: "acc-v2-email-link account-cell-line",
						disabled: e.stale,
						"data-account-detail-id": t.id,
						title: "查看账号详情"
					}, [C("span", {
						class: E(["acc-mobile-dot", `is-${t.tone}`]),
						"aria-hidden": "true"
					}, null, 2), C("span", Ge, [I(x(t.row.email), 1), t.row.archived ? (r(), F("span", Ke, "归档")) : m("", !0)])], 8, We),
					C("div", qe, [C("span", Je, x(t.row.user_name || "-"), 1), C("span", { innerHTML: e.presentation.emailInvalidBadge(t.row) }, null, 8, Ye)]),
					C("div", Xe, x(t.mobile), 1)
				]),
				C("td", Ze, [d(z, { text: t.row.email_source || "-" }, null, 8, ["text"])]),
				C("td", Qe, [d(z, { text: e.presentation.registrationDriverLabel(t.row.registration_driver) }, null, 8, ["text"])]),
				(r(!0), F(_, null, s(M(Oe).filter((e) => e.cell), (e) => (r(), F("td", {
					key: e.key,
					class: E(e.className),
					"data-label": e.label
				}, [C("div", {
					class: "ac-legacy-cell",
					innerHTML: t.cells[e.cell]
				}, null, 8, et)], 10, $e))), 128)),
				C("td", tt, [C("div", nt, [C("button", {
					type: "button",
					class: "acc-v2-detail",
					disabled: e.stale,
					"data-account-detail-id": t.id
				}, "详情", 8, rt), d(M(H), {
					open: e.visible && !e.stale && A.value === t.id,
					modal: !1,
					"onUpdate:open": (e) => A.value = e ? t.id : null
				}, {
					default: i(() => [d(M(R), { "as-child": "" }, {
						default: i(() => [C("button", {
							type: "button",
							class: "acc-v2-more-btn",
							disabled: e.stale,
							"aria-label": "更多账号操作"
						}, "更多", 8, it)]),
						_: 1
					}), d(M(L), null, {
						default: i(() => [d(M(B), {
							class: "ac-row-menu accounts-table-v2",
							"data-account-menu": t.id,
							side: "bottom",
							align: "end",
							"side-offset": 4,
							"collision-padding": 8,
							onOpenAutoFocus: n[3] ||= T(() => {}, ["prevent"])
						}, {
							default: i(() => [C("div", {
								class: "acc-v2-more-menu ac-menu-content",
								onClick: (e) => V(e, t.row),
								innerHTML: t.menu
							}, null, 8, at)]),
							_: 2
						}, 1032, ["data-account-menu"])]),
						_: 2
					}, 1024)]),
					_: 2
				}, 1032, ["open", "onUpdate:open"])])])
			], 10, ze))), 128)), N.value.length ? m("", !0) : (r(), F("tr", ot, [C("td", st, [
				C("strong", null, x(e.loading ? "正在加载账号" : e.invalidSearch ? "搜索条件有误" : e.error ? "账号加载失败" : "暂无匹配账号"), 1),
				C("p", null, x(e.loading ? "正在同步账号状态和授权信息" : e.invalidSearch ? "请按输入框旁的提示修改，或清空高级搜索。" : e.error || "可移除部分搜索条件，或切换活跃与归档账号视图。"), 1),
				e.error && !e.invalidSearch ? (r(), F("button", {
					key: 0,
					type: "button",
					class: "ac-button",
					onClick: n[4] ||= (e) => l("retry")
				}, "重试")) : m("", !0)
			])]))])
		], 12, Fe)], 40, Pe));
	}
}), lt = [
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
function ut(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(ut), Object.freeze(e)), e;
}
function dt(e) {
	return ut(Q(e));
}
function ft(e) {
	let t = String(e);
	if (!/^[1-9]\d*$/.test(t) || !Number.isSafeInteger(Number(t))) throw Error("账号 ID 无效");
	return t;
}
function pt() {
	throw new DOMException("读取已失效", "AbortError");
}
function mt(e) {
	return Q({
		account_promotions: e.account_promotions ?? null,
		promotion_query_snapshot: e.promotion_query_snapshot ?? null,
		plan_check_country_results: e.plan_check_country_results ?? []
	});
}
function ht(n, r) {
	let i = k(n.normalize()), a = k([]), o = k({}), s = k([]), c = k(null), l = y(0), u = y(1), d = y(10), f = y(!1), m = y(!1), h = y(!1), g = y(""), _ = y(!1), v = y(""), b = k(/* @__PURE__ */ new Set()), x = k({}), S = y(""), C = D(() => Math.max(1, Math.ceil(l.value / d.value))), w = D(() => n.toLegacy(i.value, {
		paged: "1",
		page: u.value,
		page_size: d.value
	}).toString()), T = D(() => S.value !== w.value), E = D(() => a.value.length > 0 && a.value.every((e) => b.value.has(String(e.id)))), O = D(() => !E.value && a.value.some((e) => b.value.has(String(e.id)))), A = 0, j = 0, M = 0, N = 0, P = !1, F = !1, I, L, R, z, B, V = "", H, U = /* @__PURE__ */ new Map(), W = /* @__PURE__ */ new Map(), G = () => typeof document > "u" || !document.hidden, K = () => !P && h.value && G(), q = (e, t) => e === A && t === w.value && K();
	function J(e) {
		return [...W.values()].some((t) => t === e);
	}
	function Y() {
		let e = /* @__PURE__ */ new Set([...a.value.map((e) => String(e.id)), ...W.values()]);
		for (let [t, n] of U) e.has(t) || (n.request?.controller.abort(), U.delete(t));
	}
	function ee() {
		for (let e of U.values()) e.request?.controller.abort(), e.request = void 0, ++e.version;
	}
	function te() {
		++A, ++j, I?.abort(), L?.abort(), I = L = void 0, clearTimeout(R), clearTimeout(B), R = B = void 0, f.value = m.value = !1;
	}
	function ne() {
		clearTimeout(R), R = void 0, K() && H !== i.value.q && (R = setTimeout(() => {
			se();
		}, 5e3));
	}
	function re(e) {
		let t = Q(e);
		for (let e of lt) {
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
	function X(e) {
		a.value = Q(e);
		for (let e of a.value) {
			let t = String(e.id), n = U.get(t);
			n?.request?.controller.abort(), U.set(t, {
				revision: "",
				version: (n?.version ?? 0) + 1,
				details: mt(e)
			});
		}
		Y();
	}
	async function Z() {
		if (te(), !K()) return;
		let e = A, t = new AbortController();
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
				X(m.items), l.value = m.total, o.value = re(m.facets), s.value = Q(m.search_terms), S.value = a, V = "", g.value = "", _.value = !1, H = void 0;
				return;
			}
		} catch (t) {
			if (e !== A || !K() || ie(t)) return;
			g.value = t instanceof Error ? t.message : "加载账号失败", t instanceof ae && t.code === "account_search_invalid" && (H = i.value.q, _.value = !0, a.value = [], l.value = 0, s.value = [], o.value = {}, Y());
		} finally {
			e === A && (f.value = !1, I = void 0, ne());
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
		if (clearTimeout(R), R = void 0, !K() || f.value || m.value || T.value || H === i.value.q) {
			ne();
			return;
		}
		let e = A, t = w.value, n = new AbortController();
		L = n, m.value = !0;
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
			e === A && (m.value = !1, L = void 0, ne());
		}
	}
	function ce(e = 0) {
		if (te(), !K()) return;
		let n = j, r = () => {
			n === j && K() && Z();
		};
		e ? B = setTimeout(r, e) : t(r);
	}
	function le() {
		b.value = /* @__PURE__ */ new Set(), x.value = {}, ++M;
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
		let n = ft(e), r = a.value.find((e) => String(e.id) === n);
		if (t && !r) throw Error("账号不在当前页");
		let i = new Set(b.value), o = { ...x.value };
		t ? (i.add(n), r?.email?.trim() ? o[n] = r.email : delete o[n]) : (i.delete(n), delete o[n]), b.value = i, x.value = o, ++M;
	}
	function we(e) {
		for (let t of a.value) Ce(String(t.id), e);
	}
	function Te(e) {
		for (let t of e) Ce(t, !1);
	}
	function Ee(e = {}) {
		let t = [...new Set((e.ids ?? [...b.value]).map(ft))], n = {}, r = new Map(a.value.map((e) => [String(e.id), e]));
		for (let e of t) {
			let t = r.has(e) ? r.get(e)?.email : x.value[e];
			t && (n[e] = t);
		}
		if (e.requireEmails && (t.length > 500 || t.some((e) => !n[e]?.trim()))) throw Error(t.length > 500 ? "一次最多处理 500 个账号" : "账号邮箱快照不完整，请刷新后重新选择");
		return dt({
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
		return dt({
			accountIds: t.ids,
			expectedEmails: t.expectedEmails,
			querySnapshot: t.query,
			archived: t.query.archived,
			rowHints: a.value.filter((e) => n.has(String(e.id)))
		});
	}
	function Oe(e) {
		let t = a.value.find((t) => String(t.id) === e);
		return t ? dt(t) : void 0;
	}
	async function ke(e) {
		K() && J(e) || pt();
		let t = U.get(e);
		if (t || pt(), t.details) return dt({
			accountId: e,
			revision: t.revision,
			item: t.details
		});
		if (t.request) return t.request.promise;
		let n = new AbortController(), i = t.version, o = r.planDetails(e, n.signal).then(async (n) => {
			K() && J(e) || pt();
			let r = U.get(e);
			return r || pt(), r !== t || r.version !== i ? ke(e) : (r.details = Q(n.item), a.value = a.value.map((t) => String(t.id) === e ? {
				...t,
				...Q(n.item)
			} : t), dt({
				accountId: e,
				revision: r.revision,
				item: r.details
			}));
		}, (n) => {
			K() && J(e) || pt();
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
		let n = ft(e);
		for (;;) {
			W.get(t) === n && K() || pt();
			let e = U.get(n), r = e?.version, i;
			try {
				i = await ke(n);
			} catch (e) {
				throw W.get(t) === n && K() || pt(), e;
			}
			if (W.get(t) === n && K() || pt(), U.get(n) === e && e?.version === r) return i;
		}
	}
	function je(e) {
		let t = ft(e), n = ++N;
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
		P || e === h.value || (h.value = e, e ? ce() : (te(), ee(), W.clear(), Y()));
	}
	function Ne() {
		G() ? h.value && ce() : (te(), ee());
	}
	return typeof document < "u" && document.addEventListener("visibilitychange", Ne), p(() => {
		P = !0, te(), clearTimeout(z), ee(), W.clear(), U.clear(), typeof document < "u" && document.removeEventListener("visibilitychange", Ne);
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
		selected: e(b),
		selectedEmails: e(x),
		loading: e(f),
		polling: e(m),
		visible: e(h),
		error: e(g),
		invalidSearch: e(_),
		draftSearch: e(v),
		renderedSignature: e(S),
		signature: w,
		stale: T,
		pageSelected: E,
		pageIndeterminate: O,
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
var gt = {
	class: "ac-root",
	"aria-label": "账号列表"
}, _t = { class: "ac-toolbar" }, vt = { class: "ac-toolbar-main" }, yt = {
	id: "accountsPageSummary",
	class: "ac-count",
	role: "status"
}, bt = { class: "ac-toolbar-utilities" }, xt = { class: "ac-mobile-filters" }, St = [
	"value",
	"aria-invalid",
	"onKeydown"
], Ct = ["disabled"], wt = {
	key: 0,
	id: "accountAdvancedSearchErrorV2",
	class: "ac-feedback",
	role: "alert"
}, Tt = {
	key: 1,
	class: "ac-feedback",
	role: "alert"
}, Et = /* @__PURE__ */ n({
	__name: "AccountsList",
	props: {
		adapter: {},
		api: {},
		presentation: {},
		callbacks: {}
	},
	setup(e, { expose: t }) {
		let n = e, i = ht(n.adapter, n.api), { query: s, items: c, facets: l, searchTerms: u, total: f, page: p, size: h, pages: _, selected: v, loading: b, error: S, visible: E, invalidSearch: O, draftSearch: k, stale: A, pageSelected: N, pageIndeterminate: P } = i, I = y(), L = y(), R = y(null), z = y(typeof document > "u" || !document.hidden), B = y(""), V = /* @__PURE__ */ new Set(), H = q.find((e) => e.key === "email_status"), K = D(() => [...G(s.value, n.presentation.facetLabel), ...u.value.map((e, t) => ({
			key: `search:${t}`,
			label: `${e.label}：${e.display_value}`,
			title: `高级搜索 · 同时满足：${e.label}：${e.display_value}`,
			removeLabel: `移除${e.label}：${e.display_value}`
		}))]);
		function J(e, t) {
			e === "plan" ? i.updateQuery({ plan: [...t] }) : e === "date_from" || e === "date_to" ? i.updateQuery({ [e]: String(t) }) : e === "id" || e === "email" ? i.updateFilters({ [e]: String(t) }, 250) : i.updateFilters({ [e]: [...t] });
		}
		function Y(e) {
			if (e.startsWith("search:")) {
				let t = u.value[Number(e.slice(7))];
				t && i.removeSearchTerm({ ...t }), L.value?.focus();
				return;
			}
			if (e === "date") {
				i.updateQuery({
					date_from: "",
					date_to: ""
				});
				return;
			}
			let t = q.find((t) => t.key === e);
			t && J(t.key, t.kind === "text" ? "" : []);
		}
		function ee(e) {
			B.value = e instanceof Error ? e.message : "账号操作暂不可用", n.callbacks.notify?.(B.value);
		}
		async function te(e, t, r) {
			if (A.value || !E.value || !z.value) return;
			let a = JSON.stringify([t, e]);
			if (!V.has(a)) {
				V.add(a), B.value = "";
				try {
					let a = i.getActionContext({
						ids: [t],
						requireEmails: e.startsWith("account-email-invalid:")
					});
					await n.callbacks.invoke(e, a, r);
				} catch (e) {
					ee(e);
				} finally {
					V.delete(a);
				}
			}
		}
		function ne(e, t) {
			if (A.value || !E.value || !z.value) return;
			B.value = "";
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
			e || (R.value = null, n.callbacks.closeConsumers?.(!1)), i.setVisible(e);
		}
		function ie(e) {
			R.value = null, i.setArchived(e);
		}
		function X() {
			i.clearSearch(), L.value?.focus();
		}
		function ae() {
			I.value?.resetColumns();
		}
		a([
			i.selected,
			i.selectedEmails,
			f,
			p,
			h,
			s,
			b,
			E
		], () => n.callbacks.onStateChange?.(Object.freeze({
			selectedIds: Object.freeze([...v.value]),
			selectedEmails: Object.freeze({ ...i.selectedEmails.value }),
			total: f.value,
			page: p.value,
			size: h.value,
			archived: s.value.archived,
			loading: b.value,
			visible: E.value
		})), {
			immediate: !0,
			flush: "post"
		});
		let Z = () => {
			z.value = !document.hidden, document.hidden && (R.value = null, n.callbacks.closeConsumers?.());
		};
		return typeof document < "u" && document.addEventListener("visibilitychange", Z), w(() => {
			typeof document < "u" && document.removeEventListener("visibilitychange", Z), n.callbacks.closeConsumers?.();
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
			resetColumns: ae,
			getAccountSelectionSnapshot: i.getAccountSelectionSnapshot,
			getActionContext: i.getActionContext,
			getRowSnapshot: i.getRowSnapshot,
			openPlanDetailsConsumer: i.openPlanDetailsConsumer,
			removeAcknowledgedSelection: i.removeAcknowledgedSelection,
			clearSelection: i.clearSelection
		}), (t, n) => o((r(), F("section", gt, [
			C("div", _t, [C("div", vt, [C("span", yt, x(M(f).toLocaleString()) + " 个账号 · 当前页 " + x(M(c).length) + " 条", 1), d(U, {
				items: K.value,
				onRemove: Y
			}, null, 8, ["items"])]), C("div", bt, [
				C("div", xt, [d(De, {
					query: M(s),
					facets: M(l),
					label: e.presentation.facetLabel,
					open: z.value && R.value === "all",
					"onUpdate:open": n[0] ||= (e) => R.value = e ? "all" : null,
					onChange: J,
					onClear: Y
				}, null, 8, [
					"query",
					"facets",
					"label",
					"open"
				])]),
				d(De, {
					column: M(H),
					query: M(s),
					facets: M(l),
					label: e.presentation.facetLabel,
					open: z.value && R.value === "email_status",
					"onUpdate:open": n[1] ||= (e) => R.value = e ? "email_status" : null,
					onChange: J,
					onClear: Y
				}, null, 8, [
					"column",
					"query",
					"facets",
					"label",
					"open"
				]),
				C("form", {
					class: "ac-search",
					role: "search",
					onSubmit: n[5] ||= T((...e) => M(i).submitSearch && M(i).submitSearch(...e), ["prevent"])
				}, [
					n[11] ||= C("label", { for: "accountAdvancedSearchV2" }, "高级搜索", -1),
					C("input", {
						id: "accountAdvancedSearchV2",
						ref_key: "search",
						ref: L,
						type: "search",
						value: M(k),
						placeholder: "空格或 / 组合，如：协议 jp",
						autocomplete: "off",
						"aria-describedby": "accountAdvancedSearchHintV2 accountAdvancedSearchErrorV2",
						"aria-invalid": M(O) || void 0,
						onKeydown: g(T(X, ["prevent"]), ["esc"]),
						onInput: n[2] ||= (e) => M(i).setSearchDraft(e.target.value),
						onCompositionstart: n[3] ||= (...e) => M(i).compositionStart && M(i).compositionStart(...e),
						onCompositionend: n[4] ||= (e) => M(i).compositionEnd(e.target.value)
					}, null, 40, St),
					M(k) ? (r(), F("button", {
						key: 0,
						type: "button",
						"aria-label": "清空高级搜索",
						title: "清空高级搜索",
						onClick: X
					}, "×")) : m("", !0)
				], 32),
				n[12] ||= C("span", {
					id: "accountAdvancedSearchHintV2",
					class: "ac-sr-only"
				}, "空格或 / 表示同时满足；支持方式、地区、邮箱、姓名、来源、备注、ID。完整文字加双引号。", -1),
				C("button", {
					id: "btnResetAccountFiltersV2",
					type: "button",
					class: "ac-link",
					title: "清除全部列筛选",
					onClick: n[6] ||= (...e) => M(i).resetFilters && M(i).resetFilters(...e)
				}, "清筛"),
				C("button", {
					id: "btnResetAccountsColumnsV2",
					type: "button",
					class: "ac-link",
					title: "恢复账号列表默认列宽",
					onClick: ae
				}, "恢复列宽"),
				C("button", {
					id: "btnRefreshAccountsV2",
					type: "button",
					class: "ac-button",
					disabled: M(b),
					onClick: n[7] ||= (...e) => M(i).refresh && M(i).refresh(...e)
				}, x(M(b) ? "刷新中…" : "刷新"), 9, Ct)
			])]),
			M(O) ? (r(), F("p", wt, x(M(S)), 1)) : B.value || M(S) && M(c).length ? (r(), F("div", Tt, [C("span", null, x(B.value || M(S)), 1), M(S) ? (r(), F("button", {
				key: 0,
				type: "button",
				class: "ac-link",
				onClick: n[8] ||= (...e) => M(i).refresh && M(i).refresh(...e)
			}, "重试")) : m("", !0)])) : m("", !0),
			d(ct, {
				ref_key: "table",
				ref: I,
				items: M(c),
				selected: M(v),
				query: M(s),
				facets: M(l),
				presentation: e.presentation,
				loading: M(b),
				error: M(S),
				"invalid-search": M(O),
				stale: M(A),
				visible: M(E) && z.value,
				"page-selected": M(N),
				"page-indeterminate": M(P),
				"open-filter": R.value,
				"onUpdate:openFilter": n[9] ||= (e) => R.value = e,
				onFilter: J,
				onClearFilter: Y,
				onSelect: M(i).toggle,
				onSelectPage: M(i).togglePage,
				onAction: te,
				onDetail: ne,
				onRetry: M(i).refresh,
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
			d(W, {
				page: M(p),
				size: M(h),
				pages: M(_),
				total: M(f),
				busy: M(b),
				"page-sizes": [
					10,
					20,
					30,
					50,
					100
				],
				label: "账号列表分页",
				"onUpdate:page": M(i).setPage,
				"onUpdate:size": M(i).setSize
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		], 512)), [[j, M(E)]]);
	}
});
// src/features/accounts/useAccountDetail.ts
function Dt(e) {
	return JSON.parse(JSON.stringify(e));
}
function Ot(e, t) {
	if (!e || typeof e != "object" || !("accountId" in e) || String(e.accountId) !== t || !("item" in e) || !e.item || typeof e.item != "object" || Array.isArray(e.item) || "id" in e.item && e.item.id != null && String(e.item.id) !== t) throw Error("账号详情响应不匹配");
	return Dt(e.item);
}
function kt(e, t) {
	let n = k(null), r = k(0), i = D(() => n.value !== null), a = D(() => n.value ? String(n.value.id) : ""), o = null, s = (e) => o === e && r.value === e.generation;
	function c(e) {
		n.value = { ...e.account };
	}
	async function l(n) {
		try {
			let e = await n.lease.loadPlanDetails(n.id, n.lease.openGeneration);
			if (!s(n)) return;
			Object.assign(n.account, Ot(e, n.id)), c(n);
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
		let s = Dt(n);
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
		account: P(n),
		generation: P(r),
		isOpen: i,
		accountId: a,
		open: d,
		close: u
	};
}
// src/features/accounts/AccountDetail.vue?vue&type=script&setup=true&lang.ts
var At = ["aria-hidden"], jt = ["data-account-id"], Mt = { class: "account-detail-head" }, Nt = { id: "accountDetailTitle" }, Pt = { id: "accountDetailSubtitle" }, Ft = ["innerHTML"], It = /* @__PURE__ */ n({
	__name: "AccountDetail",
	props: {
		api: {},
		presentation: {},
		callbacks: {}
	},
	setup(e, { expose: n }) {
		let i = e, a = y(), o = !1, s = null;
		function c() {
			let e = s;
			s = null, e?.isConnected && e.focus({ preventScroll: !0 });
		}
		let u = kt(i.api, {
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
		}), { account: d, accountId: f, isOpen: p } = u, m = D(() => d.value ? d.value.email || `账号 #${d.value.id}` : "账号详情"), h = D(() => d.value ? `账号 #${d.value.id} · ${i.presentation.sourceLabel(d.value.email_source) || "未知来源"}` : ""), g = D(() => d.value ? i.presentation.renderBody(d.value) : "");
		function _(e, t, n, r) {
			let i = typeof document < "u" && document.activeElement instanceof HTMLElement ? document.activeElement : null;
			return u.open(e, t, n, r || i);
		}
		function v(e = !0) {
			u.close(e);
		}
		return w(() => {
			o = !0, u.close();
		}), l(() => {
			i.callbacks.syncModalScrollLock(), c();
		}), n({
			open: _,
			close: v
		}), (e, t) => (r(), S(b, { to: "#accountDetailHost" }, [C("div", {
			id: "accountDetailBackdrop",
			class: E(["account-detail-backdrop", { hidden: !M(p) }]),
			"aria-hidden": !M(p),
			onClick: t[0] ||= T((e) => v(), ["self"])
		}, null, 10, At), C("aside", {
			id: "accountDetailDrawer",
			class: E(["account-detail-drawer", { hidden: !M(p) }]),
			"data-account-id": M(p) ? M(f) : void 0,
			role: "dialog",
			"aria-modal": "true",
			"aria-labelledby": "accountDetailTitle"
		}, [C("div", Mt, [C("div", null, [
			t[2] ||= C("div", { class: "data-panel-kicker" }, "ACCOUNT DETAIL", -1),
			C("h2", Nt, x(m.value), 1),
			C("p", Pt, x(h.value), 1)
		]), C("button", {
			id: "btnCloseAccountDetail",
			ref_key: "closeButton",
			ref: a,
			type: "button",
			class: "account-detail-close",
			"aria-label": "关闭账号详情",
			onClick: t[1] ||= (e) => v()
		}, "×", 512)]), C("div", {
			id: "accountDetailBody",
			class: "account-detail-body",
			innerHTML: g.value
		}, null, 8, Ft)], 10, jt)]));
	}
}), Lt = (e) => e === "only" ? "已归档账号" : e === "all" ? "全部账号" : "未归档账号", Rt = (e) => ({
	running: "进行中",
	completed: "已完成",
	interrupted: "已中断"
})[String(e)] || String(e ?? ""), zt = (e) => ({
	deactivated_skipped: "已废跳过",
	rejected: "未能入队",
	failed: "查活失败",
	error: "执行异常",
	attention_required: "执行失败",
	interrupted: "执行中断"
})[String(e)] || String(e ?? ""), Bt = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : String(e);
function Vt(e) {
	return e && typeof e == "object" ? e : {};
}
function Ht(e) {
	return Object.freeze((Array.isArray(e) ? e : []).map((e) => Object.freeze({ ...Vt(e) })));
}
function Ut(e) {
	let t = y(!1), n = y(!1), r = y(!1), i = y("0"), o = y(3), s = y(!1), c = y(""), l = y(1), u = y(1), d = y(null), f = k([]), m = k([]), h = y(0), g = y(0), _ = y(!1), v = y(!1), b = y(""), x = y(!1), S = y(!1), C = y(!1), w = null, T = 0, E = 0, O = !1, A, j, M, N = () => typeof document > "u" || !document.hidden, P = D(() => _.value ? `共 ${h.value} 条 · 第 ${l.value} 页` : ""), F = D(() => v.value ? `共 ${g.value} 条 · 第 ${u.value} 页` : "");
	async function I(t, n = {}, r = new AbortController()) {
		let i = setTimeout(() => r.abort(), 3e4);
		try {
			return Vt(await e.request(t, {
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
		O || (i.value = n.archived, o.value = Math.min(16, e.operationWorkers()), c.value = "", t.value = !0);
	}
	async function z() {
		let n = Number(o.value);
		if (!(O || s.value || !Number.isInteger(n) || n < 1 || n > 16)) {
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
				if (w = null, C.value = !0, O) return;
				t.value = !1, e.notify(r.created ? "巡检已加入统一任务队列" : "已有本次巡检记录，已打开历史"), B();
			} catch (e) {
				O || (c.value = `巡检启动请求失败：${Bt(e)}。可查看巡检历史，或使用当前提交再次确认。`);
			} finally {
				s.value = !1;
			}
		}
	}
	function B() {
		O || (l.value = 1, ++T, n.value = !0, H());
	}
	function V(e) {
		x.value || (l.value = Math.max(1, l.value + e), ++T, H());
	}
	async function H() {
		if (O || x.value || !n.value || !N()) return;
		x.value = !0;
		let t = l.value, r = T, i = new AbortController();
		A = i;
		try {
			let e = await I(`/api/accounts/inspections?page=${t}`, {}, i);
			if (O || i.signal.aborted || !n.value || t !== l.value || r !== T) return;
			let a = C.value;
			C.value = !!e.active, a && !C.value && L(), f.value = Ht(e.items), h.value = Number(e.total), _.value = !0;
		} catch (t) {
			!O && n.value && N() && r === T && e.notify(`读取巡检历史失败：${Bt(t)}`);
		} finally {
			x.value = !1, A === i && (A = void 0), r !== T && !O && n.value && N() && H();
		}
	}
	function U(e) {
		O || (d.value = Number(e), u.value = 1, ++E, v.value = !1, b.value = "", m.value = [], r.value = !0, G());
	}
	function W(e) {
		S.value || (u.value = Math.max(1, u.value + e), ++E, G());
	}
	async function G() {
		if (O || S.value || !d.value || !r.value || !N()) return;
		S.value = !0;
		let e = d.value, t = u.value, n = E, i = new AbortController();
		j = i;
		try {
			let a = await I(`/api/accounts/inspections/${e}/failures?page=${t}`, {}, i);
			if (O || i.signal.aborted || !r.value || e !== d.value || t !== u.value || n !== E) return;
			m.value = Ht(a.items), g.value = Number(a.total), v.value = !0, b.value = "";
		} catch (e) {
			!O && r.value && N() && n === E && (b.value = `读取失败：${Bt(e)}，可点击刷新重试。`);
		} finally {
			S.value = !1, j === i && (j = void 0), n !== E && !O && r.value && N() && G();
		}
	}
	async function K(t) {
		if (!O) try {
			if (await I(`/api/accounts/inspections/${Number(t)}/cancel`, { method: "POST" }), O) return;
			e.notify("已请求停止，将在安全检查点结束"), H();
		} catch (t) {
			O || e.notify(`停止巡检失败：${Bt(t)}`);
		}
	}
	function q(e) {
		e && e !== "start" || (t.value = !1), e && e !== "history" || (n.value = !1, ++T, A?.abort()), e && e !== "failures" || (r.value = !1, ++E, j?.abort());
	}
	function J() {
		M !== void 0 && (clearInterval(M), M = void 0), !O && N() && (n.value || r.value) && (M = setInterval(() => {
			n.value && H(), r.value && G();
		}, 5e3));
	}
	function Y() {
		N() || (++T, ++E, A?.abort(), j?.abort()), J();
	}
	return a([n, r], J, { flush: "sync" }), typeof document < "u" && document.addEventListener("visibilitychange", Y), p(() => {
		O = !0, q(), J(), typeof document < "u" && document.removeEventListener("visibilitychange", Y);
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
		failureRows: m,
		historyTotal: h,
		failureTotal: g,
		historyReady: _,
		failureReady: v,
		failureError: b,
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
var Wt = ["data-archived"], Gt = { class: "modal-header" }, Kt = { id: "accountInspectionScope" }, qt = {
	id: "accountInspectionStartError",
	role: "status"
}, Jt = ["disabled"], Yt = { class: "modal-header" }, Xt = {
	key: 0,
	"data-inspection-scroll": "",
	tabindex: "0",
	role: "region",
	"aria-label": "可左右滚动查看巡检记录"
}, Zt = { class: "data-table" }, Qt = ["data-inspection-task", "onClick"], $t = { class: "sub-cell" }, en = { class: "sub-cell" }, tn = { key: 0 }, nn = ["onClick"], rn = ["onClick"], an = { key: 1 }, on = { class: "jobs-v2-pager" }, sn = ["disabled"], cn = { id: "accountInspectionPageLabel" }, ln = ["disabled"], un = { class: "modal-header" }, dn = { id: "accountInspectionFailuresTitle" }, fn = { key: 0 }, pn = {
	key: 1,
	"data-inspection-scroll": "",
	tabindex: "0",
	role: "region",
	"aria-label": "可左右滚动查看巡检记录"
}, mn = { class: "data-table" }, hn = { class: "inspection-error-reason" }, gn = { key: 2 }, _n = { class: "jobs-v2-pager" }, vn = ["disabled"], yn = { id: "accountInspectionFailuresPageLabel" }, bn = ["disabled"], xn = /*#__PURE__*/ N(/* @__PURE__ */ n({
	__name: "Inspection",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, c = Ut(i.deps), { startOpen: l, historyOpen: u, failuresOpen: d, archived: p, workers: h, starting: g, startError: v, historyPage: b, failurePage: S, failureId: E, historyRows: D, failureRows: O, historyTotal: k, failureTotal: j, historyReady: N, failureReady: P, failureError: L, historyLabel: R, failureLabel: z } = c, B = y(), V = y(), H = y(), U = y(), W = y(), G = /* @__PURE__ */ new Map(), K = {
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
		function ee(e, t) {
			J[e].value || G.set(e, t ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null));
		}
		function te(e, t) {
			ee("start", t), c.openStart(e), oe("start");
		}
		function ne(e) {
			ee("history", e), c.openHistory(), oe("history");
		}
		function re(e, t) {
			ee("failures", t), c.openFailures(e), oe("failures");
		}
		function ie(e) {
			c.close(e);
			let t = G.get(e);
			if (G.delete(e), Y) return;
			let n = V.value?.open ? V.value.querySelector("button:not([disabled])") : i.deps.fallbackFocus?.();
			(t?.isConnected ? t : n)?.focus({ preventScroll: !0 });
		}
		function X(e) {
			K[e] ? --K[e] : q[e].value?.open || ie(e);
		}
		function ae(e) {
			let t = q[e].value;
			t?.open && (++K[e], t.close(), ie(e));
		}
		function Z(e) {
			c.close(e);
			for (let t of [
				"failures",
				"history",
				"start"
			]) e && e !== t || ae(t);
		}
		async function oe(e) {
			await t();
			let n = q[e].value, r = J[e].value;
			n && !Y && (r && !n.open ? (G.has(e) || G.set(e, document.activeElement instanceof HTMLElement ? document.activeElement : null), n.showModal()) : !r && n.open && ae(e));
		}
		for (let e of [
			"start",
			"history",
			"failures"
		]) a(J[e], () => oe(e), { flush: "post" });
		a(b, () => {
			if (U.value) {
				U.value.scrollTop = 0;
				let e = U.value.querySelector("[data-inspection-scroll]");
				e && (e.scrollLeft = 0);
			}
		}), a([S, E], () => {
			if (W.value) {
				W.value.scrollTop = 0;
				let e = W.value.querySelector("[data-inspection-scroll]");
				e && (e.scrollLeft = 0);
			}
		});
		function se(e) {
			Z("history"), i.deps.openTask(Number(e.task_id));
		}
		function ce(e) {
			return Number(e.live_failed_count || 0) + Number(e.deactivated_skipped_count || 0);
		}
		return w(() => {
			Y = !0;
			for (let e of Object.values(q)) e.value?.open && e.value.close();
			G.clear();
		}), n({
			openStart: te,
			openHistory: ne,
			openFailures: re,
			close: Z,
			refreshHistory: c.refreshHistory,
			refreshFailures: c.refreshFailures,
			changeHistoryPage: c.changeHistoryPage,
			changeFailuresPage: c.changeFailuresPage,
			stop: c.stop
		}), (t, n) => (r(), F(_, null, [
			C("dialog", {
				ref_key: "start",
				ref: B,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionStart",
				"aria-labelledby": "accountInspectionStartTitle",
				"data-archived": M(p),
				onClose: n[3] ||= (e) => X("start")
			}, [C("div", Gt, [n[14] ||= C("h2", { id: "accountInspectionStartTitle" }, "启动账号巡检", -1), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				"aria-label": "关闭启动巡检",
				onClick: n[0] ||= (e) => Z("start")
			}, "关闭")]), C("form", { onSubmit: n[2] ||= T((...e) => M(c).submit && M(c).submit(...e), ["prevent"]) }, [
				C("p", Kt, "本次范围：" + x(M(Lt)(M(p))), 1),
				n[15] ||= C("p", null, "该归档范围内全部账号，不限当前页，不受勾选、搜索或其他筛选条件影响。", -1),
				n[16] ||= C("p", null, "已废账号跳过；AT 本地有效则结束；失效时自动刷新，再复用登录会话查套餐。", -1),
				n[17] ||= C("label", { for: "accountInspectionWorkers" }, "并发账号数", -1),
				o(C("input", {
					id: "accountInspectionWorkers",
					"onUpdate:modelValue": n[1] ||= (e) => f(h) ? h.value = e : null,
					type: "number",
					min: "1",
					max: "16",
					step: "1",
					required: ""
				}, null, 512), [[A, M(h)]]),
				n[18] ||= C("p", null, "支持 1–16；实际并发同时受共享账号操作预算限制。", -1),
				C("p", qt, x(M(v)), 1),
				C("button", {
					type: "submit",
					class: "jobs-tb-btn jobs-tb-btn--primary",
					id: "btnConfirmAccountInspection",
					disabled: M(g)
				}, "开始巡检", 8, Jt)
			], 32)], 40, Wt),
			C("dialog", {
				ref_key: "history",
				ref: V,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionHistory",
				"aria-labelledby": "accountInspectionHistoryTitle",
				onClose: n[8] ||= (e) => X("history")
			}, [
				C("div", Yt, [
					n[19] ||= C("h2", { id: "accountInspectionHistoryTitle" }, "账号巡检历史", -1),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[4] ||= (...e) => M(c).refreshHistory && M(c).refreshHistory(...e)
					}, "刷新"),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[5] ||= (e) => Z("history")
					}, "关闭")
				]),
				n[20] ||= C("p", null, "每 5 秒刷新。进度包含跳过；完成表示本轮处理结束，查活和套餐结果分别统计。", -1),
				C("div", {
					ref_key: "historyContent",
					ref: U,
					id: "accountInspectionHistoryContent",
					"aria-live": "polite"
				}, [M(D).length ? (r(), F("div", Xt, [C("table", Zt, [C("thead", null, [C("tr", null, [(r(), F(_, null, s([
					"任务",
					"范围",
					"状态 / 时间",
					"并发",
					"进度",
					"AT失效",
					"查活 成功/失败",
					"套餐 成功/失败",
					"操作"
				], (e) => C("th", {
					key: e,
					scope: "col"
				}, x(e), 1)), 64))])]), C("tbody", null, [(r(!0), F(_, null, s(M(D), (t, n) => (r(), F("tr", { key: String(t.id ?? n) }, [
					C("td", null, [C("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-inspection-task": Number(t.id),
						onClick: (e) => se(t)
					}, "#" + x(Number(t.id)), 9, Qt)]),
					C("td", null, x(M(Lt)(String(t.archived))), 1),
					C("td", null, [I(x(M(Rt)(t.status)), 1), C("div", $t, x(e.deps.formatDateTime(t.created_at)), 1)]),
					C("td", null, x(Number(t.workers)), 1),
					C("td", null, [I(x(Number(t.checked_count) + Number(t.skipped_count)) + " / " + x(Number(t.total_count)), 1), C("div", en, "跳过 " + x(Number(t.skipped_count)) + "（已废 " + x(Number(t.deactivated_skipped_count)) + "）", 1)]),
					C("td", null, x(Number(t.invalid_count)), 1),
					C("td", null, [I(x(Number(t.live_success_count)) + " / " + x(Number(t.live_failed_count)), 1), ce(t) ? (r(), F("div", tn, [C("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: (e) => re(Number(t.id), e.currentTarget)
					}, "失败详情 " + x(ce(t)), 9, nn)])) : m("", !0)]),
					C("td", null, x(Number(t.plan_success_count)) + " / " + x(Number(t.plan_failed_count)), 1),
					C("td", null, [t.status === "running" ? (r(), F("button", {
						key: 0,
						type: "button",
						class: "jobs-tb-btn",
						onClick: (e) => M(c).stop(Number(t.id))
					}, "停止", 8, rn)) : m("", !0)])
				]))), 128))])])])) : (r(), F("p", an, x(M(N) ? "暂无巡检记录。" : "正在读取巡检历史…"), 1))], 512),
				C("div", on, [
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionPrev",
						disabled: M(b) <= 1,
						onClick: n[6] ||= (e) => M(c).changeHistoryPage(-1)
					}, "上一页", 8, sn),
					C("span", cn, x(M(R)), 1),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionNext",
						disabled: M(b) * 20 >= M(k),
						onClick: n[7] ||= (e) => M(c).changeHistoryPage(1)
					}, "下一页", 8, ln)
				])
			], 544),
			C("dialog", {
				ref_key: "failures",
				ref: H,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionFailures",
				"aria-labelledby": "accountInspectionFailuresTitle",
				onClose: n[13] ||= (e) => X("failures")
			}, [
				C("div", un, [
					C("h2", dn, x(M(E) ? `巡检 #${M(E)} · 失败详情` : "巡检失败详情"), 1),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[9] ||= (...e) => M(c).refreshFailures && M(c).refreshFailures(...e)
					}, "刷新"),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: n[10] ||= (e) => Z("failures")
					}, "关闭")
				]),
				n[21] ||= C("p", null, "保留本轮原始执行快照，后续重跑或删除账号不会改写；含已废跳过，套餐单独失败不计为查活失败。", -1),
				C("div", {
					ref_key: "failureContent",
					ref: W,
					id: "accountInspectionFailuresContent",
					"aria-live": "polite"
				}, [M(L) ? (r(), F("p", fn, x(M(L)), 1)) : M(O).length ? (r(), F("div", pn, [C("table", mn, [C("thead", null, [C("tr", null, [(r(), F(_, null, s([
					"账号",
					"邮箱",
					"类型",
					"时间",
					"原因"
				], (e) => C("th", {
					key: e,
					scope: "col"
				}, x(e), 1)), 64))])]), C("tbody", null, [(r(!0), F(_, null, s(M(O), (t, n) => (r(), F("tr", { key: String(t.account_id ?? n) }, [
					C("td", null, "#" + x(Number(t.account_id)), 1),
					C("td", null, x(t.email), 1),
					C("td", null, x(M(zt)(t.status)), 1),
					C("td", null, x(e.deps.formatDateTime(t.failed_at)), 1),
					C("td", hn, x(t.error), 1)
				]))), 128))])])])) : (r(), F("p", gn, x(M(P) ? "本轮暂无查活失败或已废跳过。" : "正在读取本次失败记录…"), 1))], 512),
				C("div", _n, [
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresPrev",
						disabled: !M(P) || M(S) <= 1,
						onClick: n[11] ||= (e) => M(c).changeFailuresPage(-1)
					}, "上一页", 8, vn),
					C("span", yn, x(M(z)), 1),
					C("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresNext",
						disabled: !M(P) || M(S) * 20 >= M(j),
						onClick: n[12] ||= (e) => M(c).changeFailuresPage(1)
					}, "下一页", 8, bn)
				])
			], 544)
		], 64));
	}
}), [["__scopeId", "data-v-88e51d48"]]);
// src/features/accounts/useAccountEmailChange.ts
function Sn(e) {
	return JSON.parse(JSON.stringify(e));
}
function Cn(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(Cn), Object.freeze(e)), e;
}
function wn(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Tn(e) {
	return e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败，请稍后重试";
}
function En(e) {
	return [...new Set((Array.isArray(e?.accountIds) ? e.accountIds : []).map(Number).filter((e) => Number.isSafeInteger(e) && e > 0).map(String))];
}
function Dn(e, t = {}) {
	let n = y(!1), r = y(0), i = y("single"), a = k(null), o = k(null), s = k([]), c = k([]), l = y(""), u = y("idle"), d = y(""), f = y(!1), m = D(() => u.value !== "ready" || !c.value.some((e) => e.enabled)), h = null, g = !1, _ = (e) => !g && h === e && r.value === e.generation && n.value;
	function v({ restoreFocus: e = !0 } = {}) {
		let i = h;
		i && (h = null, ++r.value, i.controller.abort(), n.value = !1, a.value = null, o.value = null, s.value = [], c.value = [], l.value = "", u.value = "idle", d.value = "", f.value = !1, t.closed?.(e, i.trigger, r.value));
	}
	async function b(n, r) {
		try {
			let t = wn(await e.request("/api/email-sources", { signal: n.controller.signal }));
			if (!_(n)) return;
			c.value = Cn((Array.isArray(t.sources) ? t.sources : []).map((e) => {
				let t = wn(e);
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
			u.value = "failed", c.value = [], l.value = "", d.value = `邮箱来源读取失败：${Tn(e)}`;
		}
		_(n) && t.sourcesReady?.(n.generation);
	}
	function x(e, p, m, _, y) {
		if (g) return !1;
		let x = Cn(Sn({
			..._,
			accountIds: p
		}));
		v({ restoreFocus: !1 });
		let S = {
			generation: ++r.value,
			mode: e,
			account: m,
			accountIds: Cn([...p]),
			context: x,
			trigger: y,
			controller: new AbortController(),
			submitting: !1
		};
		return h = S, i.value = e, a.value = m, s.value = S.accountIds, o.value = x, n.value = !0, u.value = "loading", l.value = "", d.value = "", c.value = [], f.value = !1, t.opened?.(S.generation), b(S, String(m?.email_source || "").trim().toLowerCase()), !0;
	}
	function S(t, n, r = null) {
		let i = Number(t), a = String(i), o = n?.rowHints?.find((e) => String(e.id) === a);
		return !Number.isSafeInteger(i) || i <= 0 || !En(n).includes(a) || !o ? (e.notify("账号详情暂不可用，请先刷新列表"), !1) : x("single", [a], Cn({
			id: i,
			email: String(o.email || ""),
			email_source: String(o.email_source || "")
		}), n, r);
	}
	function C(t, n = null) {
		let r = En(t);
		return r.length ? r.length > 500 ? (e.notify("单次最多换绑 500 个账号"), !1) : x("bulk", r, null, t, n) : (e.notify("请先选择账号"), !1);
	}
	function w(t, n) {
		try {
			Promise.resolve(t()).catch((t) => e.notify(n + Tn(t)));
		} catch (t) {
			e.notify(n + Tn(t));
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
			r = wn(await e.request(t.mode === "bulk" ? "/api/accounts/email-change-bulk" : `/api/accounts/${t.account.id}/email-change`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(t.mode === "bulk" ? {
					account_ids: t.accountIds.map(Number),
					email_source: n
				} : { email_source: n })
			}));
		} catch (n) {
			_(t) && (d.value = `提交失败：${Tn(n)}`), e.notify("换绑邮箱失败: " + Tn(n));
			return;
		} finally {
			t.submitting = !1, _(t) && (f.value = !1);
		}
		let i = _(t), a = Cn({
			result: Sn(r),
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
	return p(() => {
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
		sourceDisabled: m,
		error: d,
		submitting: f,
		openSingle: S,
		openBulk: C,
		close: v,
		submit: T
	};
}
// src/features/accounts/EmailChange.vue?vue&type=script&setup=true&lang.ts
var On = [
	"aria-hidden",
	"data-account-id",
	"data-account-ids"
], kn = {
	class: "email-change-dialog",
	role: "document"
}, An = { class: "email-change-head" }, jn = { id: "emailChangeTitle" }, Mn = { id: "emailChangeAccountLabel" }, Nn = {
	class: "email-change-field",
	for: "emailChangeSource"
}, Pn = ["disabled"], Fn = { value: "" }, In = [
	"value",
	"disabled",
	"title",
	"data-reason"
], Ln = ["hidden"], Rn = { class: "email-change-foot" }, zn = ["disabled"], Bn = /* @__PURE__ */ n({
	__name: "EmailChange",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, a = y(), c = y(), u = y(), d = !1, p = null;
		function m() {
			let e = p;
			p = null, e?.isConnected && e.focus({ preventScroll: !0 });
		}
		let g = Dn(i.deps, {
			opened(e) {
				p = null, t(() => {
					!d && g.generation.value === e && g.isOpen.value && (c.value?.setCustomValidity(""), i.deps.syncModalScrollLock(), u.value?.focus({ preventScroll: !0 }));
				});
			},
			sourcesReady(e) {
				t(() => {
					!d && g.generation.value === e && g.isOpen.value && c.value?.focus({ preventScroll: !0 });
				});
			},
			closed(e, n, r) {
				p = e ? n : null, t(() => {
					d || g.generation.value !== r || g.isOpen.value || (i.deps.syncModalScrollLock(), m());
				});
			}
		}), { isOpen: v, account: O, accountIds: k, mode: A, sources: j, source: N, sourceStatus: P, sourceDisabled: I, error: L, submitting: R } = g, z = D(() => v.value && A.value === "bulk" ? "批量换绑邮箱" : "换绑邮箱"), B = D(() => v.value ? A.value === "bulk" ? `已选 ${k.value.length} 个账号 · 将按账号分别领取新邮箱` : `账号 #${O.value?.id} · 当前邮箱 ${O.value?.email || "-"}` : ""), V = D(() => P.value === "loading" ? "正在读取邮箱来源…" : P.value === "failed" ? "邮箱来源读取失败" : P.value === "ready" ? "请选择邮箱来源" : "打开弹窗后读取可用来源");
		function H(e) {
			return e || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
		}
		function U(e, t, n = null) {
			return g.openSingle(e, t, H(n));
		}
		function W(e, t = null) {
			return g.openBulk(e, H(t));
		}
		function G(e = {}) {
			g.close(e);
		}
		async function K() {
			c.value?.setCustomValidity(""), !c.value?.checkValidity() || !N.value || I.value ? (c.value?.setCustomValidity("请选择新邮箱来源"), g.error.value = "请选择新邮箱来源", c.value?.reportValidity(), c.value?.focus()) : await g.submit();
		}
		function q(e) {
			if (!v.value) return;
			if (e.key === "Escape") {
				e.preventDefault(), G();
				return;
			}
			if (e.key !== "Tab") return;
			let t = Array.from(a.value?.querySelectorAll("button, select, [href], [tabindex]:not([tabindex=\"-1\"])") || []).filter((e) => !("disabled" in e && e.disabled) && !e.hidden), n = t[0], r = t.at(-1);
			e.shiftKey && document.activeElement === n ? (e.preventDefault(), r?.focus()) : !e.shiftKey && document.activeElement === r && (e.preventDefault(), n?.focus());
		}
		return document.addEventListener("keydown", q), w(() => {
			d = !0, document.removeEventListener("keydown", q), g.close();
		}), l(() => {
			i.deps.syncModalScrollLock(), m();
		}), n({
			openSingle: U,
			openBulk: W,
			close: G
		}), (e, t) => (r(), S(b, { to: "#accountEmailChangeHost" }, [C("div", {
			ref_key: "modal",
			ref: a,
			id: "emailChangeModal",
			class: E(["email-change-modal", { hidden: !M(v) }]),
			role: "dialog",
			"aria-modal": "true",
			"aria-hidden": !M(v),
			"aria-labelledby": "emailChangeTitle",
			"aria-describedby": "emailChangeNote",
			"data-account-id": M(v) && M(A) === "single" ? String(M(O)?.id) : "",
			"data-account-ids": M(v) && M(A) === "bulk" ? JSON.stringify(M(k).map(Number)) : "",
			onClick: t[3] ||= T((e) => G(), ["self"])
		}, [C("div", kn, [C("div", An, [C("div", null, [
			t[4] ||= C("div", { class: "data-panel-kicker" }, "PROTOCOL OPERATION", -1),
			C("h2", jn, x(z.value), 1),
			C("p", Mn, x(B.value), 1)
		]), C("button", {
			ref_key: "closeButton",
			ref: u,
			id: "btnCloseEmailChange",
			type: "button",
			class: "account-detail-close",
			"aria-label": "关闭换绑邮箱",
			onClick: t[0] ||= (e) => G()
		}, "×", 512)]), C("form", {
			id: "emailChangeForm",
			class: "email-change-form",
			novalidate: "",
			onSubmit: T(K, ["prevent"])
		}, [
			C("label", Nn, [
				t[5] ||= C("span", null, "新邮箱来源", -1),
				o(C("select", {
					ref_key: "select",
					ref: c,
					id: "emailChangeSource",
					"onUpdate:modelValue": t[1] ||= (e) => f(N) ? N.value = e : null,
					name: "email_source",
					required: "",
					disabled: M(I),
					"aria-describedby": "emailChangeSourceHelp emailChangeSourceError"
				}, [C("option", Fn, x(V.value), 1), (r(!0), F(_, null, s(M(j), (e, t) => (r(), F("option", {
					key: `${e.value}:${t}`,
					value: e.value,
					disabled: !e.enabled,
					title: e.reason,
					"data-reason": e.reason
				}, x(e.label) + x(e.enabled ? "" : "（不可用）"), 9, In))), 128))], 8, Pn), [[h, M(N)]]),
				t[6] ||= C("small", { id: "emailChangeSourceHelp" }, "系统会从所选邮箱池自动领取新地址，并读取新邮箱验证码。", -1),
				C("small", {
					id: "emailChangeSourceError",
					class: "email-change-error",
					role: "alert",
					hidden: !M(L)
				}, x(M(L)), 9, Ln)
			]),
			t[7] ||= C("div", {
				id: "emailChangeNote",
				class: "email-change-note"
			}, "换绑、Recent Login 和验证码校验全部走协议任务，不会启动浏览器。成功写回后会自动创建一次协议查活任务刷新 AT。", -1),
			C("div", Rn, [C("button", {
				id: "btnCancelEmailChange",
				type: "button",
				class: "jobs-tb-btn",
				onClick: t[2] ||= (e) => G()
			}, "取消"), C("button", {
				id: "btnSubmitEmailChange",
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				disabled: M(R)
			}, x(M(R) ? "提交中…" : "开始换绑"), 9, zn)])
		], 32)])], 10, On)]));
	}
});
// src/features/accounts/useC2aReimport.ts
function Vn(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Hn(e) {
	return e && typeof e == "object" && (Object.values(e).forEach(Hn), Object.freeze(e)), e;
}
function Un(e) {
	return Hn(JSON.parse(JSON.stringify(e)));
}
var Wn = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败";
function Gn(e) {
	let t = /* @__PURE__ */ new Map();
	for (let n of [e.skipped, e.failed]) for (let e of Array.isArray(n) ? n : []) {
		let n = e && typeof e == "object" ? e : {}, r = String(n.reason || n.error || n.error_code || "服务端未返回原因，请重试");
		t.set(r, (t.get(r) || 0) + 1);
	}
	return t.size ? `；未入队原因：${[...t].slice(0, 3).map(([e, t]) => `${e}${t > 1 ? `（${t} 个）` : ""}`).join("；")}${t.size > 3 ? `；另有 ${t.size - 3} 类原因` : ""}` : "；未入队原因：服务端未返回原因，请重试";
}
function Kn(e) {
	return [
		"queued",
		"skipped",
		"failed"
	].flatMap((t, n) => (Array.isArray(e[t]) ? e[t] : []).map((e) => ({
		item: Vn(e),
		state: [
			"已入队",
			"未入队",
			"入队失败"
		][n]
	})));
}
function qn(e, t = {}) {
	let n = y(!1), r = y(!1), i = y(""), a = k([]), o = k(null), s = null, c = null, l = !1, u = D(() => o.value ? Kn(o.value) : []), d = D(() => u.value.filter((e) => Number(e.item.task_id) > 0)), f = D(() => {
		let e = o.value;
		return e ? `C2A 重新导入：已入队 ${Number(e.queued_count ?? (Array.isArray(e.queued) ? e.queued.length : 0))} 个，未入队 ${Number(e.skipped_count ?? (Array.isArray(e.skipped) ? e.skipped.length : 0)) + Number(e.failed_count ?? (Array.isArray(e.failed) ? e.failed.length : 0))} 个` : "";
	});
	function m(t, o = null) {
		if (l) return !1;
		if (n.value) return e.notify("C2A 同步确认窗口不可用，请刷新页面后重试"), !1;
		let u = t.accountIds.map((e) => {
			if (!/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
			return Number(e);
		});
		return u.length ? (s = Un(t), a.value = Object.freeze([...u]), c = o, r.value = !1, i.value = "", n.value = !0, !0) : (e.notify("请先选择账号"), !1);
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
			e.notify(n + Wn(t));
		}
	}
	function _(e) {
		o.value = Un(Vn(e));
	}
	function v(t = d.value.map((e) => e.item)) {
		let n = t.length === 1 ? t[0] : null;
		return g(() => e.openTasks({
			filters: { type: "c2a_session_reimport" },
			taskId: Number(n?.task_id) || void 0,
			runId: Number(n?.run_id) || null
		}), "C2A 请求已处理，打开任务失败: ");
	}
	async function b() {
		if (l || !n.value || !s || !a.value.length || r.value) return;
		let t = [...a.value], o = s, u = c;
		r.value = !0, i.value = "正在创建 C2A 同步任务…";
		let d = e.beginBusy?.(u, "提交导入…"), f;
		try {
			f = Vn(await e.request("/api/accounts/c2a/sync-bulk", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ account_ids: t })
			}));
		} catch (t) {
			e.notify("重新导入 C2A 失败: " + Wn(t)), l || (i.value = `提交失败：${Wn(t)}。请检查后再次提交。`), r.value = !1, d?.(), e.selectionChanged?.(o);
			return;
		}
		try {
			let t = Number(f.skipped_count ?? (Array.isArray(f.skipped) ? f.skipped.length : 0)) + Number(f.failed_count ?? (Array.isArray(f.failed) ? f.failed.length : 0)), n = t ? Gn(f) : "";
			f.accepted ? e.notify(`C2A 重新导入已入队 ${f.queued_count ?? (Array.isArray(f.queued) ? f.queued.length : 0)} 个，未入队 ${t} 个，请在任务中心查看结果${n}`) : (e.notify(t ? `C2A 已重新导入 ${f.updated_count || 0} 个，跳过/失败 ${t} 个${n}` : `C2A 已重新导入 ${f.updated_count || 0} 个`), await g(() => e.refreshAccounts(o), "C2A 请求已处理，页面更新失败: "));
		} catch (t) {
			e.notify("C2A 请求已处理，回执更新失败: " + Wn(t));
		} finally {
			r.value = !1;
			try {
				d?.();
			} finally {
				l || h("submitted", !0);
			}
		}
	}
	return p(() => {
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
		open: m,
		close: h,
		submit: b,
		showResult: _,
		openTasks: v
	};
}
// src/features/accounts/C2aReimport.vue?vue&type=script&setup=true&lang.ts
var Jn = { class: "c2a-reimport-confirm-head" }, Yn = ["disabled"], Xn = { class: "c2a-reimport-confirm-body" }, Zn = { class: "c2a-reimport-confirm-scope" }, Qn = { id: "c2aReimportConfirmCountV2" }, $n = ["hidden"], er = { class: "c2a-reimport-confirm-foot" }, tr = ["disabled"], nr = ["disabled"], rr = /* @__PURE__ */ n({
	__name: "C2aReimport",
	props: { deps: {} },
	setup(e, { expose: n }) {
		let i = e, a = y(), o = !1, s = 0, c = 0, l;
		function u(e, t) {
			!o && e?.isConnected && typeof e.focus == "function" && (e.focus({ preventScroll: !0 }), l = requestAnimationFrame(() => {
				if (l = void 0, o || c !== t || d.isOpen.value) return;
				let n = e.closest("#accountsMoreActionsV2"), r = n?.open === !1 ? n.querySelector("summary") : e;
				r?.isConnected && r.focus({ preventScroll: !0 });
			}));
		}
		let d = qn({
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
		function T(e) {
			p.value && e.preventDefault();
		}
		return w(() => {
			o = !0, ++c, l !== void 0 && cancelAnimationFrame(l), d.close("cancel", !0);
		}), n({
			open: g,
			close: _,
			submit: d.submit,
			showResult: d.showResult,
			openTasks: d.openTasks,
			isSubmitting: p
		}), (e, t) => (r(), S(b, { to: "#accountC2aConfirmHost" }, [C("dialog", {
			ref_key: "dialog",
			ref: a,
			onClose: v,
			onCancel: T,
			id: "c2aReimportConfirmModal",
			"aria-labelledby": "c2aReimportConfirmTitle",
			"aria-describedby": "c2aReimportConfirmDescription"
		}, [
			C("div", Jn, [t[3] ||= C("div", null, [
				C("p", { class: "c2a-reimport-confirm-kicker" }, "本地 AT · 远端账号同步"),
				C("h3", { id: "c2aReimportConfirmTitle" }, "批量同步到 C2A"),
				C("p", { id: "c2aReimportConfirmDescription" }, "查到唯一的同邮箱 C2A 账号时覆盖 AT；未找到时新建账号。")
			], -1), C("button", {
				type: "button",
				class: "c2a-reimport-confirm-close",
				id: "btnCloseC2aReimportV2",
				disabled: M(p),
				onClick: t[0] ||= (e) => _(),
				"aria-label": "关闭 C2A 同步确认窗口"
			}, "×", 8, Yn)]),
			C("div", Xn, [
				C("p", Zn, [
					t[4] ||= I("将为 ", -1),
					C("strong", Qn, x(M(h).length), 1),
					t[5] ||= I(" 个已选账号创建同步任务。", -1)
				]),
				t[6] ||= C("section", {
					class: "c2a-reimport-confirm-note",
					"aria-labelledby": "c2aReimportConfirmScopeTitle"
				}, [C("h4", { id: "c2aReimportConfirmScopeTitle" }, "更新范围"), C("ul", null, [C("li", null, "任务执行时读取本地保存的当前 AT；不会刷新本地 AT，也不会重新登录。"), C("li", null, "按完整邮箱匹配 C2A 账号：唯一匹配时覆盖 AT，未找到时新建；同邮箱存在多条账号时不执行覆盖。")])], -1),
				t[7] ||= C("section", {
					class: "c2a-reimport-confirm-note",
					"aria-labelledby": "c2aReimportConfirmSafetyTitle"
				}, [C("h4", { id: "c2aReimportConfirmSafetyTitle" }, "提交安全条件"), C("p", null, "任务写入前会确认 C2A 的“自动移除异常账号”和“自动移除限流账号”都已关闭；无法确认或任一开关开启时，不会发送更新。执行期间请保持两个开关关闭。")], -1),
				t[8] ||= C("section", {
					class: "c2a-reimport-confirm-note c2a-reimport-confirm-note--warning",
					"aria-labelledby": "c2aReimportConfirmSideEffectTitle"
				}, [C("h4", { id: "c2aReimportConfirmSideEffectTitle" }, "C2A 端状态可能变化"), C("p", null, "当前 C2A 通用更新接口会按自身规则清除凭据错误。AT 更新确认后，异常账号可能恢复正常；最终以 C2A 状态和任务回执为准。")], -1),
				C("p", {
					class: "c2a-reimport-confirm-status",
					id: "c2aReimportConfirmStatusV2",
					role: "status",
					"aria-live": "polite",
					"aria-atomic": "true",
					hidden: !M(m)
				}, x(M(m)), 9, $n)
			]),
			C("div", er, [C("button", {
				type: "button",
				class: "jobs-tb-btn",
				id: "btnCancelC2aReimportV2",
				disabled: M(p),
				onClick: t[1] ||= (e) => _()
			}, "取消", 8, tr), C("button", {
				type: "button",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				id: "btnConfirmC2aReimportV2",
				disabled: M(p),
				onClick: t[2] ||= (...e) => M(d).submit && M(d).submit(...e)
			}, x(M(p) ? "正在提交…" : "提交并入队"), 9, nr)])
		], 544)]));
	}
}), ir = ["hidden"], ar = { class: "column-filter-summary-label" }, or = [
	"data-registration-retry-result",
	"data-registration-retry-task-id",
	"data-registration-retry-run-id",
	"onClick"
], sr = /* @__PURE__ */ n({
	__name: "RegistrationRetryReceipt",
	props: { notify: { type: Function } },
	setup(e, { expose: t }) {
		let n = e, i = k(null), a = y(0), o = !1;
		function c(e) {
			return Array.isArray(e) ? Object.freeze(e.map(c)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, c(t)]))) : e;
		}
		let l = D(() => Array.isArray(i.value?.result.started) ? i.value.result.started : []), u = D(() => Array.isArray(i.value?.result.reused) ? i.value.result.reused : []), d = D(() => Array.isArray(i.value?.result.skipped) ? i.value.result.skipped : []), f = D(() => [...l.value, ...u.value]), p = D(() => {
			let e = i.value?.result;
			return `注册重跑：已创建 ${Number(e?.started_count ?? l.value.length)} 个，进行中 ${Number(e?.reused_count ?? u.value.length)} 个，跳过 ${Number(e?.skipped_count ?? d.value.length)} 个`;
		}), h = (e) => e.task_id || e.operation_task_id, g = (e) => h(e) || e.job_id;
		function v(e, t, n) {
			o || (i.value = {
				result: c(e),
				context: c(t),
				open: n
			}, ++a.value);
		}
		async function T(e = f.value) {
			if (o || !i.value) return;
			let t = i.value.open;
			try {
				await t(c(e));
			} catch (e) {
				o || n.notify?.("注册重跑请求已处理，打开任务失败: " + (e instanceof Error ? e.message : "请求失败"));
			}
		}
		return w(() => {
			o = !0, i.value = null;
		}), t({
			showResult: v,
			openTasks: T
		}), (e, t) => (r(), S(b, { to: "#accountRegistrationReceiptHost" }, [C("div", {
			id: "accountRegistrationRetryResultV2",
			class: "column-filter-summary account-search-summary",
			role: "status",
			"aria-live": "polite",
			hidden: !i.value
		}, [
			C("span", ar, x(i.value ? p.value : ""), 1),
			f.value.length ? (r(), F("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-tasks": "",
				onClick: t[0] ||= (e) => T()
			}, "打开任务中心")) : m("", !0),
			f.value.length || d.value.length ? (r(), F("details", { key: a.value }, [C("summary", null, "查看" + x(d.value.length ? "任务及跳过原因" : "任务"), 1), C("ul", null, [(r(!0), F(_, null, s(f.value, (e, t) => (r(), F("li", { key: `task-${t}` }, [I("账号 #" + x(e.account_id) + " · " + x(t < l.value.length ? "已创建" : "进行中") + " ", 1), C("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-result": t,
				"data-registration-retry-task-id": h(e) || void 0,
				"data-registration-retry-run-id": h(e) && e.run_id ? e.run_id : void 0,
				onClick: (t) => T([e])
			}, "查看任务" + x(g(e) ? ` #${g(e)}` : ""), 9, or)]))), 128)), (r(!0), F(_, null, s(d.value, (e, t) => (r(), F("li", { key: `skipped-${t}` }, "账号 #" + x(e.account_id) + " · " + x(e.reason || e.error || "当前不可重跑"), 1))), 128))])])) : m("", !0)
		], 8, ir)]));
	}
}), cr = /* @__PURE__ */ n({
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
		let n = e, i = y(), a = y(), o = y(), s = y(), c = y(), l = y(), u = y(), f = k(), p = k(n.initialCapabilities), m = y(0), h = k({});
		function g() {
			if (!i.value) throw Error("账号列表正在加载，请稍后重试");
			return i.value;
		}
		let v = D(() => {
			m.value;
			let e = i.value?.getActionContext(), t = e ? Object.fromEntries(oe.map((t) => [t.action, n.actions.isPending(t.action, e)])) : {};
			return t.reimportSelectedC2a = c.value?.isSubmitting === !0, {
				selectedCount: f.value?.selectedIds.length || 0,
				archived: f.value?.archived === "only",
				pending: t,
				labels: h.value
			};
		});
		async function x(e, t, r = null) {
			let i = n.actions.isSupported(e) ? n.actions.invoke(e, t, r) : n.callbacks.invoke(e, t, r);
			++m.value;
			try {
				await i;
			} finally {
				++m.value;
			}
		}
		let C = {
			...n.callbacks,
			invoke: x,
			onStateChange: (e) => {
				f.value = e, n.callbacks.onStateChange?.(e);
			},
			openDetail: (e, t, n, r) => {
				a.value ? a.value.open(e, t, n, r) : n.release();
			},
			closeConsumers: (e = !0) => {
				a.value?.close(e), n.callbacks.closeConsumers?.(e);
			}
		}, T = {
			notify: (e) => n.callbacks.notify?.(e),
			syncModalScrollLock: () => n.syncModalScrollLock()
		};
		return w(() => n.actions.dispose()), t({
			setVisible: (e) => {
				n.actions.setVisible(e), g().setVisible(e);
			},
			setArchived: (e) => g().setArchived(e),
			refresh: () => g().refresh(),
			pollStatuses: () => g().pollStatuses(),
			getAccountSelectionSnapshot: (...e) => g().getAccountSelectionSnapshot(...e),
			getActionContext: (...e) => g().getActionContext(...e),
			getRowSnapshot: (e) => g().getRowSnapshot(e),
			openPlanDetailsConsumer: (e) => g().openPlanDetailsConsumer(e),
			removeAcknowledgedSelection: (e) => g().removeAcknowledgedSelection(e),
			clearSelection: () => g().clearSelection(),
			setPage: (e) => g().setPage(e),
			setSize: (e) => g().setSize(e),
			updateQuery: (...e) => g().updateQuery(...e),
			updateFilters: (...e) => g().updateFilters(...e),
			resetFilters: () => g().resetFilters(),
			resetColumns: () => g().resetColumns(),
			openDetail: (e, t = null) => g().openDetail(e, t),
			closeDetail: (e = !0) => a.value?.close(e),
			isActionSupported: (e) => n.actions.isSupported(e),
			isActionPending: (e) => n.actions.isPending(e, g().getActionContext()),
			invokeAction: x,
			syncToolbarPending: () => {
				++m.value;
			},
			setToolbarBusyLabel: (e, t) => {
				let n = { ...h.value };
				t ? n[e] = t : delete n[e], h.value = n;
			},
			closeMoreMenus: () => g().closeMoreMenus(),
			setCapabilities: (e) => {
				p.value = e;
			},
			refreshQuickActions: () => l.value?.refreshQuickActions(),
			showRegistrationResult: (e, t, n) => u.value?.showResult(e, t, n),
			openInspectionStart: (e, t = null) => o.value?.openStart(e, t),
			openInspectionHistory: (e = null) => o.value?.openHistory(e),
			openInspectionFailures: (e, t = null) => o.value?.openFailures(e, t),
			closeInspection: (e) => o.value?.close(e),
			refreshInspectionHistory: () => o.value?.refreshHistory(),
			refreshInspectionFailures: () => o.value?.refreshFailures(),
			changeInspectionPage: (e) => o.value?.changeHistoryPage(e),
			changeInspectionFailuresPage: (e) => o.value?.changeFailuresPage(e),
			stopInspection: (e) => o.value?.stop(e),
			openEmailChange: (e, t, n = null) => s.value?.openSingle(e, t, n),
			openBulkEmailChange: (e, t = null) => s.value?.openBulk(e, t),
			closeEmailChange: (e = {}) => s.value?.close(e),
			openC2a: (e, t = null) => c.value?.open(e, t),
			closeC2a: (e = "cancel", t = {}) => c.value?.close(e, t),
			submitC2a: () => c.value?.submit(),
			showC2aResult: (e) => c.value?.showResult(e),
			openC2aTasks: (e) => c.value?.openTasks(e)
		}), (t, n) => (r(), F(_, null, [
			(r(), S(b, { to: "#accountToolbarHost" }, [d(_e, {
				ref_key: "toolbar",
				ref: l,
				state: v.value,
				capabilities: p.value,
				runtime: e.toolbarRuntime,
				"get-context": () => g().getActionContext(),
				invoke: x,
				notify: C.notify
			}, null, 8, [
				"state",
				"capabilities",
				"runtime",
				"get-context",
				"notify"
			])])),
			d(Et, {
				ref_key: "list",
				ref: i,
				adapter: e.adapter,
				api: e.api,
				presentation: e.presentation,
				callbacks: C
			}, null, 8, [
				"adapter",
				"api",
				"presentation"
			]),
			d(It, {
				ref_key: "drawer",
				ref: a,
				api: e.detailApi,
				presentation: e.detailPresentation,
				callbacks: T
			}, null, 8, ["api", "presentation"]),
			d(xn, {
				ref_key: "inspection",
				ref: o,
				deps: e.inspectionDependencies
			}, null, 8, ["deps"]),
			d(Bn, {
				ref_key: "emailChange",
				ref: s,
				deps: e.emailChangeDependencies
			}, null, 8, ["deps"]),
			d(rr, {
				ref_key: "c2a",
				ref: c,
				deps: e.c2aDependencies
			}, null, 8, ["deps"]),
			d(sr, {
				ref_key: "registrationReceipt",
				ref: u,
				notify: C.notify
			}, null, 8, ["notify"])
		], 64));
	}
});
// src/api/accounts.ts
function lr(e) {
	return typeof e == "object" && !!e && !Array.isArray(e);
}
function ur(e, t) {
	return typeof e == "number" && Number.isSafeInteger(e) && e >= t;
}
function dr(e) {
	return lr(e) && e.ok === !0 && Array.isArray(e.items) && ur(e.total, 0) && ur(e.page, 1) && ur(e.page_size, 1) && ur(e.offset, 0) && ur(e.limit, 1) && typeof e.revision == "string";
}
function fr() {
	throw new ae("账号查询返回了无效的响应，请刷新后重试。", 200, "account_response_invalid");
}
function pr(e) {
	return {
		async list(t, n, r, i) {
			let a = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			}), o = await X(`/api/accounts?${a}`, { signal: i });
			return dr(o) && o.compact === !0 && lr(o.facets) && Array.isArray(o.search_terms) || fr(), o;
		},
		async statuses(t, n, r, i) {
			let a = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			});
			a.set("compact", "1");
			let o = await X(`/api/accounts/plan-check-status?${a}`, { signal: i });
			return dr(o) && lr(o.queue) && Array.isArray(o.status_fields) && o.status_fields.every((e) => typeof e == "string") || fr(), o;
		},
		async planDetails(e, t) {
			if (!/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
			let n = await X(`/api/accounts/${encodeURIComponent(e)}/plan-details`, { signal: t });
			return lr(n) && n.ok === !0 && lr(n.item) && Object.hasOwn(n.item, "account_promotions") && Object.hasOwn(n.item, "promotion_query_snapshot") && Array.isArray(n.item.plan_check_country_results) || fr(), n;
		}
	};
}
// src/api/accountDetail.ts
function mr() {
	return { async roxyProfile(e, t) {
		if (!/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
		let n = await X(`/api/accounts/${encodeURIComponent(e)}/roxy-profile`, { signal: t });
		if (!n || typeof n != "object" || Array.isArray(n) || !("ok" in n) || n.ok !== !0 || !("profile_id" in n) || n.profile_id !== null && typeof n.profile_id != "string" || !("window_name" in n) || n.window_name !== null && typeof n.window_name != "string") throw new ae("账号详情返回了无效的响应，请重新打开详情重试。", 200, "account_response_invalid");
		return {
			ok: !0,
			profile_id: n.profile_id,
			window_name: n.window_name
		};
	} };
}
// src/features/accounts/queuedActions.ts
var hr = {
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
}, gr = (e) => Object.prototype.hasOwnProperty.call(hr, e), _r = (e) => e instanceof Error ? e.message : "请求失败，请稍后重试。";
function vr(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function yr(e) {
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
function br(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return [...new Set(e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	}))];
}
function xr(e) {
	return Array.isArray(e) ? Object.freeze(e.map(xr)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, xr(t)]))) : e;
}
function Sr(e, t) {
	return xr({
		accountIds: t.map(String),
		expectedEmails: { ...e.expectedEmails },
		querySnapshot: e.querySnapshot,
		archived: e.archived,
		rowHints: []
	});
}
function Cr(e) {
	let t = [...yr(e.skipped), ...yr(e.failed)].map((e) => String(e.reason || e.error || "").replace(/\s+/g, " ").trim()).filter(Boolean);
	return t.length ? `；${t.slice(0, 3).map((e) => e.length > 80 ? `${e.slice(0, 80)}…` : e).join("；")}${t.length > 3 ? `；另有 ${t.length - 3} 条原因` : ""}` : "";
}
function wr(e) {
	let t = Array.isArray(e) ? e.filter((e) => e && typeof e == "object") : [], n = (e) => t.find((t) => t.key === e), r = n("ACCOUNT_AT_REFRESH_DRIVER"), i = String(r?.value || "protocol").trim().toLowerCase() === "browser_roxy" ? "browser_roxy" : "protocol", a = n("ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED")?.value, o = a === !0 || String(a).trim().toLowerCase() === "true", s = String(n("OPENAI_PROTOCOL_VERSION")?.value || "v1").trim().toLowerCase(), c = ["v2", "v3"].includes(s) ? s : "v1", l = r ? i === "browser_roxy" ? "Roxy 指纹浏览器" : `协议刷新（${c}）` : "已保存的刷新驱动";
	return {
		description: i === "protocol" && c === "v3" ? `使用${l}先复用该账号有效的登录会话；会话失效或尚未保存时，按实际挑战完成密码、2FA 或邮箱验证，核对账号身份并保存最新 accessToken。` : `使用${l}重新登录，按实际挑战完成密码、2FA 或邮箱验证，并保存最新 accessToken。`,
		debugDescription: o ? "Roxy 刷新调试已开启：实际使用 Roxy 时将显示浏览器并全程抓包；失败保留窗口，可从任务日志查看现场并下载 HAR。" : ""
	};
}
function Tr(e) {
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
function Er(e, t) {
	let n = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), i = !0, a = !1, o = 0, s = (e, t) => hr[e]?.single ? JSON.stringify([e, ...t.map(String)]) : e, c = (e) => !a && i && e === o && t.isOwnerActive();
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
			n() && e.notify(`请求已处理，但页面更新失败: ${_r(t)}`);
		}
	}
	async function p(r, l, u = null) {
		if (!gr(r)) throw Error(`未支持的账号动作：${r}`);
		if (a || !i || e.canInvoke?.(r, u) === !1) return;
		let p = hr[r], m, h, g = o;
		try {
			let i = br(l);
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
			let a = Sr(l, i), o = (t) => {
				h = e.beginBusy?.(r, u, t) || void 0;
			}, _ = async (t, n) => vr(await e.request(t, n === void 0 ? { method: "POST" } : {
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
					if (e.notify(p.error + _r(n)), p.single) try {
						await t.pollStatuses(a);
					} catch (t) {
						e.notify(`套餐状态读取失败: ${_r(t)}`);
					}
					return;
				}
				e.notify(p.single ? String(n.message || "套餐查询已加入后台队列") : `已入队 ${$(n.started_count)} 个，查询中跳过 ${$(n.busy_count)} 个，入队失败 ${$(n.failed_count)} 个${yr(n.skipped).length ? `，跳过 ${yr(n.skipped).length} 个` : ""}${Cr(n)}`), await f(() => t.pollStatuses(a));
			} else if (p.kind === "live") {
				let n = t.operationWorkers(), r = p.single ? "确定查活这个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。" : `确定查活选中的 ${i.length} 个账号吗？\n\n只在线验证现有 accessToken，不会发送邮箱验证码，也不会刷新 AT。\n\n并发线程数：${n}`;
				if (!await e.confirm(r)) return;
				o("查活中…");
				let s = await _("/api/accounts/check-live-bulk", {
					account_ids: i,
					driver: t.configuredLiveCheckDriver()
				}), c = yr(s.skipped).length, l = yr(s.started);
				e.notify(`查活已入队 ${$(s.started_count)} 个，忙碌 ${$(s.busy_count)} 个，失败 ${$(s.failed_count)}${c ? `，跳过 ${c}` : ""}（配置驱动：${t.configuredLiveCheckDriver() || "默认"}，实际驱动：${s.live_check_driver || "未知"}）${Cr(s)}`), await f(async () => {
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
				let c = wr(s), l = i.length === 1 ? "这个账号" : `选中的 ${i.length} 个账号`;
				if (!await e.confirm(`确定刷新${l}的 AT 吗？\n\n${c.description}${c.debugDescription ? `\n\n${c.debugDescription}` : ""}${i.length > 1 ? `\n\n并发线程数：${n}` : ""}`)) return;
				t.updateBusyLabel?.(r, u, "刷新中…");
				let d = await _("/api/accounts/refresh-token-bulk", { account_ids: i }), p = yr(d.skipped).length, m = yr(d.started)[0];
				e.notify(`刷新AT已入队 ${$(d.started_count)} 个，忙碌 ${$(d.busy_count)} 个，失败 ${$(d.failed_count)}${p ? `，跳过 ${p}` : ""}${Cr(d)}`), await f(async () => {
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
					if (String(t.current_plan_type || t.plan_type || "").toLowerCase() !== "free" || Tr(t) !== "free_trial") {
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
					let t = $(n.skipped_count) + $(n.busy_count) + $(n.failed_count), r = yr(n.started).filter((e) => e.fallback_from).length;
					e.notify(`已入队 ${$(n.started_count)} 个${t ? `，跳过/失败 ${t} 个` : ""}${r ? `，其中 ${r} 个已自动跳过失败类型` : ""}`);
				}
				await f(async () => {
					await t.reloadTasks(), await t.pollStatuses(a);
				});
			}
		} catch (t) {
			e.notify(p.error + _r(t));
		} finally {
			m && n.delete(m), h?.();
		}
	}
	return {
		isSupported: gr,
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
var Dr = {
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
}, Or = {
	addPasswordSelectedAccounts: "password",
	addTwofaSelectedAccounts: "twofa",
	changePasswordSelectedAccounts: "password_change",
	changeTwofaSelectedAccounts: "twofa_change",
	completeSelectedAccounts: "complete"
}, kr = /* @__PURE__ */ new Set([
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
]), Ar = (e, t) => Object.prototype.hasOwnProperty.call(e, t);
function jr(e) {
	let t = e.indexOf(":");
	return t < 0 ? {
		name: e,
		value: ""
	} : {
		name: e.slice(0, t),
		value: e.slice(t + 1)
	};
}
function Mr(e) {
	let { name: t, value: n } = jr(e);
	return t === "account-action" ? Ar(Dr, n) : t === "account-registration-task" ? /^[1-9]\d*$/.test(n) && Number.isSafeInteger(Number(n)) : !e.includes(":") && (kr.has(t) || Ar(Or, t));
}
function Nr(e, t = !1) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let n = e;
	if (t && n.ok === !1) throw Error(typeof n.error == "string" ? n.error : "请求失败");
	return n;
}
function Pr(e) {
	if (e == null) return [];
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return e.map((e) => Nr(e));
}
function Fr(e) {
	let t = Number(e || 0);
	if (!Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function Ir(e) {
	return Array.isArray(e) ? Object.freeze(e.map(Ir)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, Ir(t)]))) : e;
}
function Lr(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return Ir({
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
function Rr(e) {
	let t = Pr(e.started), n = Pr(e.reused), r = Pr(e.skipped);
	return Ir({
		started: t,
		reused: n,
		skipped: r,
		started_count: Fr(e.started_count ?? t.length),
		reused_count: Fr(e.reused_count ?? n.length),
		skipped_count: Fr(e.skipped_count ?? r.length)
	});
}
function zr(e) {
	return `注册重跑：已创建 ${e.started_count} 个，进行中 ${e.reused_count} 个，跳过 ${e.skipped_count} 个`;
}
var Br = (e) => e instanceof Error ? e.message : "请求失败，请稍后重试。", Vr = (e) => e === "account-registration-retry" || e === "retryAccountRegistration", Hr = (e) => e.startsWith("account-") || e.startsWith("codex-");
function Ur(e, t) {
	let n = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Set(), i = (e, t) => Hr(jr(e).name) ? JSON.stringify([e, ...t]) : e;
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
			e.notify(`请求已处理，但页面更新失败: ${Br(t)}`);
		}
	}
	async function s(e, n) {
		await o(() => t.refresh(e)), n && await o(async () => t.openTasks(n));
	}
	async function c(c, l, u = null) {
		if (!Mr(c)) throw Error(`未支持的账号动作：${jr(c).name}`);
		if (e.canInvoke?.(c, u) === !1) return;
		let { name: d, value: f } = jr(c), p = d === "account-action" ? f : Ar(Or, d) ? Or[d] : void 0, m = p ? Dr[p] : void 0, h, g, _ = [], v = !1, y = m ? `${m.label}失败: ` : d.includes("setup") || d === "setupSelectedAccounts" ? "补齐账号配置失败: " : d === "codex-stop" ? "停止失败: " : d === "codex-reset-retrying" ? "重置失败: " : d === "codex-retry" ? "触发补跑失败: " : d === "stopSelectedCodex" ? "停止选中补跑失败: " : d === "retrySelectedCodex" ? "批量补跑失败: " : d === "uploadSelectedCodexSub2" ? "批量上传 sub2 失败: " : "注册重跑提交失败: ";
		try {
			let y = Lr(l), b = y.accountIds.map(Number), x = b[0];
			if (!b.length) {
				e.notify("请先选择账号");
				return;
			}
			if (Hr(d) && b.length !== 1) throw Error("此操作只能选择一个账号");
			let S = y.rowHints.find((e) => String(e.id) === String(x)), C = y.expectedEmails[String(x)] || S?.email || "", w = S?.email || C || `账号 #${x}`;
			if (d === "account-registration-task") {
				await a([{
					account_id: x,
					email: C,
					job_id: Number(f)
				}], y);
				return;
			}
			if (Vr(d) && y.accountIds.some((e) => r.has(e))) {
				e.notify("所选账号的注册重跑正在提交，请稍后查看结果");
				return;
			}
			if (h = i(c, y.accountIds), n.has(h)) {
				h = void 0;
				return;
			}
			if (n.add(h), Vr(d) && (_ = y.accountIds, _.forEach((e) => r.add(e))), p && !Hr(d) && ["password_change", "twofa_change"].includes(p) && b.length > 20) {
				e.notify("修改密码或修改 2FA 单次最多操作 20 个账号");
				return;
			}
			let T;
			if (T = d === "account-setup" ? `补齐账号配置？\n\n${w}\n\n只执行账号密码、套餐查询和 Authenticator 2FA，不执行 Codex 授权。` : d === "setupSelectedAccounts" ? `确定补齐选中的 ${b.length} 个账号配置吗？\n\n只执行：账号密码、套餐查询、Authenticator 2FA。\n不会执行 Codex 授权。` : m ? Hr(d) ? `${m.label}？\n\n${w}` : `确定${m.label}选中的 ${b.length} 个账号吗？` : d === "codex-stop" ? `确定停止该账号的 Codex 补跑吗？\n\n${C}\n\n会发送停止信号并将状态标记为“已停止”。` : d === "codex-reset-retrying" ? `确定重置该账号的 Codex「补跑中」状态吗？\n\n${C}\n\n重置后状态会变为“失败”，可再次点击“补跑 Codex”。` : d === "codex-retry" ? `重新跑 Codex 授权？\n\n${C}\n\n按实际验证要求使用邮箱 OTP（自动收）。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑会在后台进行，完成后状态自动更新。` : d === "stopSelectedCodex" ? `确定停止选中的 ${b.length} 个账号的 Codex 补跑吗？\n\n会向正在补跑的任务发送停止信号，并将状态标记为“已停止”；未在补跑的账号会自动跳过。` : d === "retrySelectedCodex" ? `批量补跑选中的 ${b.length} 个账号 Codex 授权？\n\n并发线程数：${t.operationWorkers()}\n\n按实际验证要求使用邮箱 OTP。手机接码仅在开关开启且遇到手机验证时使用；关闭后遇到手机验证会报错退出。\n\n补跑中和已废号账号会自动跳过。` : d === "uploadSelectedCodexSub2" ? `确定上传选中的 ${b.length} 个账号的 Codex OAuth 凭证到 sub2api 吗？\n\n未完成 Codex OAuth 的账号会自动跳过。` : `确定为${b.length === 1 ? `账号 #${x}` : `选中的 ${b.length} 个账号`}${b.length === 1 && S?.registration_retry?.label || "重跑原注册任务"}吗？\n\n复用原注册记录，按当前进度重跑或补齐缺失步骤。正在执行、已完成或没有原任务的账号会显示对应结果。`, !await e.confirm(T)) return;
			g = e.beginBusy?.(c, u, Vr(d) ? "提交中…" : d === "uploadSelectedCodexSub2" ? "提交上传…" : void 0) || void 0;
			let E = async (t, n) => {
				let r = Nr(await e.request(t, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(n)
				}), !0);
				return v = !0, r;
			};
			if (d === "account-setup" || d === "setupSelectedAccounts") {
				let t = d === "account-setup", n = await E(t ? `/api/accounts/${x}/setup` : "/api/accounts/setup-bulk", t ? {} : { account_ids: b }), r = Pr(n.skipped).length;
				e.notify(t ? String(n.message || "已开始补齐账号配置") : r ? `已开始补齐 ${Fr(n.started_count)} 个，跳过 ${r} 个` : `已开始补齐 ${Fr(n.started_count)} 个账号配置`), await s(y, { filters: {
					target: t ? w : "",
					type: "account_setup_retry"
				} });
			} else if (p && m) {
				let t = d === "account-action", n = await E(t ? `/api/accounts/${x}/action` : "/api/accounts/action-bulk", t ? { action: p } : {
					account_ids: b,
					action: p
				}), r = Pr(n.skipped).length, i = Pr(n.started);
				e.notify(t ? String(n.message || `${m.label}已入队`) : r ? `已开始 ${Fr(n.started_count)} 个，跳过 ${r} 个` : String(n.message || `${m.label}已入队`));
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
				let t = d === "stopSelectedCodex", n = await E(`/api/codex/${t ? "stop" : "retry"}-bulk`, { account_ids: b }), r = Pr(n.skipped).length;
				e.notify(t ? `已停止 ${Fr(n.stopped_count)} 个${r ? `，跳过 ${r} 个` : ""}` : r ? `已开始 ${Fr(n.started_count)} 个，跳过 ${r} 个` : String(n.message || "已开始批量补跑")), await s(y, t ? void 0 : { filters: {
					target: "",
					type: "codex_retry"
				} });
			} else if (d === "uploadSelectedCodexSub2") {
				let n = await E("/api/accounts/codex/upload-sub2-bulk", { account_ids: b }), r = Fr(n.skipped_count ?? Pr(n.skipped).length) + Fr(n.failed_count ?? Pr(n.failed).length), i = r ? Gn(n) : "";
				n.accepted ? e.notify(`手动上传已入队 ${Fr(n.queued_count ?? Pr(n.queued).length)} 个，未入队 ${r} 个，请在任务中心查看结果${i}`) : (e.notify(`已上传 ${Fr(n.uploaded_count)} 个${r ? `，跳过/失败 ${r} 个${i}` : ""}`), await o(() => t.pollStatuses(y)));
			} else if (Vr(d)) {
				let n = Rr(await E(b.length === 1 ? `/api/accounts/${x}/registration-retry` : "/api/accounts/registration-retry-bulk", b.length === 1 ? {} : { account_ids: b }));
				if (e.notify(zr(n)), t.showRegistrationResult(n, y, (e) => a(e, y)), b.length === 1) {
					let e = n.started[0] || n.reused[0];
					e && await a([e], y);
				}
				await t.refresh(y);
			}
		} catch (t) {
			v && (y = Vr(d) ? "注册重跑请求已处理，页面更新失败: " : "请求已处理，但页面更新失败: "), e.notify(y + Br(t));
		} finally {
			h && n.delete(h), _.forEach((e) => r.delete(e)), g?.();
		}
	}
	return {
		isSupported: Mr,
		invoke: c,
		isPending: (e, t) => Vr(jr(e).name) ? t.accountIds.some((e) => r.has(e)) : n.has(i(e, t.accountIds))
	};
}
// src/features/accounts/localMutations.ts
var Wr = (e) => e === "only" ? "已归档账号" : e === "all" ? "全部账号" : "未归档账号", Gr = (e) => e && typeof e == "object" && "message" in e ? String(e.message) : "请求失败，请稍后重试。";
function Kr(e) {
	let t = e.indexOf(":");
	return {
		name: t < 0 ? e : e.slice(0, t),
		value: t < 0 ? void 0 : e.slice(t + 1)
	};
}
function qr(e) {
	let { name: t, value: n } = Kr(e);
	return ["account-archive", "account-email-invalid"].includes(t) ? n === "0" || n === "1" : t === "setAccountsEmailInvalid" ? n === void 0 || n === "0" || n === "1" : n === void 0 && [
		"account-delete",
		"account-restore",
		"archiveSelectedAccounts",
		"deleteSelectedAccounts",
		"deleteDeactivatedAccounts"
	].includes(t);
}
function Jr(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function Yr(e) {
	let t = Number(e);
	if (e == null || e === "" || typeof e == "boolean" || !Number.isSafeInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function Xr(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	return [...new Set(e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	}))];
}
function Zr(e, t) {
	if (!Array.isArray(e)) throw Error("服务端响应格式无效");
	return [...new Set(e.map((e) => Jr(e).id).filter((e) => (typeof e == "number" || typeof e == "string") && t.includes(Number(e))).map(String))];
}
function Qr(e) {
	let t = /* @__PURE__ */ new Set(), n = (e, t) => e.startsWith("account-") ? JSON.stringify([e, ...t.accountIds]) : Kr(e).name;
	async function r(t, n, r = !1) {
		let i = r ? new AbortController() : void 0, a = i ? setTimeout(() => i.abort(), 3e4) : void 0;
		try {
			return Jr(await e.request(t, {
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
		i && e.notify(`${r ? "操作已处理，" : ""}页面刷新失败: ${Gr(i.reason)}`);
	}
	async function a(a, o, s = null) {
		if (!qr(a)) throw Error(`未支持的账号动作：${Kr(a).name}`);
		if (e.canInvoke?.(a, s) === !1) return;
		let { name: c, value: l } = Kr(a), u = c === "deleteDeactivatedAccounts", d = c === "account-email-invalid" || c === "setAccountsEmailInvalid", f, p, m = !1, h = !1, g = !1, _ = u ? "删除请求失败，请刷新核实：" : d ? "更新邮箱失效标记失败: " : c === "account-restore" ? "恢复账号失败: " : c === "deleteSelectedAccounts" ? "批量删除失败: " : "删除失败: ";
		try {
			let i = u ? [] : Xr(o), v = o.archived;
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
				}), d = Yr(u.updated_count), f = Array.isArray(u.skipped) ? u.skipped.length : 0;
				h = !0, e.notify(`${n ? "已标记邮箱失效" : "已清除本地邮箱失效标记"} ${d} 个${f ? `，跳过 ${f} 个（邮箱可能已变更）` : ""}`);
			} else if (u) {
				if (![
					"0",
					"only",
					"all"
				].includes(v)) throw Error("归档范围无效");
				if (!await e.confirm(`确定删除「${Wr(v)}」范围内全部已废账号？\n\n不限当前页，不受勾选、搜索或其他筛选影响。仅删除本地账号记录，保留邮箱池和巡检历史。此操作不可撤销。`)) return;
				p = e.beginBusy?.(a, s) || void 0, m = !0, g = !0;
				let t = Yr((await r("/api/accounts/delete-deactivated", { archived: v }, !0)).deleted_count);
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
					S = Zr(b[t ? "updated" : "deleted"], i);
					let e = Yr(b[t ? "updated_count" : "deleted_count"]), n = Array.isArray(b.skipped) ? b.skipped.length : 0;
					C = `已${d} ${e} 个${n ? `，跳过 ${n} 个` : ""}`;
				} else {
					if (b[t ? "updated" : "deleted"] !== !0 || (t || b.id !== void 0) && String(b.id) !== String(y)) throw Error("服务端未确认账号操作结果");
					S = [String(y)], C = t ? u ? "账号已归档" : "账号已恢复" : "账号已删除";
				}
				h = !0, g = !0, S.length && e.removeAcknowledgedSelection(S, o), e.notify(C);
			}
		} catch (t) {
			e.notify(`${h ? "操作已处理，页面更新失败: " : _}${Gr(t)}`);
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
		isSupported: qr,
		invoke: a,
		isPending: (e, r) => t.has(n(e, r))
	};
}
// src/features/accounts/actions.ts
var $r = {
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
}, ei = {
	copy_line: "账号整行已复制",
	chatgpt_session: "ChatGPT session 已复制",
	account_password: "账号密码已复制",
	totp_secret: "TOTP 密钥已复制",
	access_token: "Token 已复制"
}, ti = {
	downloadSelectedAccountTxt: "生成 TXT 失败: ",
	downloadSelectedAccountSessions: "下载 Session 失败: ",
	downloadSelectedCpa: "下载 CPA 失败: "
}, ni = (e, t) => Object.prototype.hasOwnProperty.call(e, t);
function ri(e) {
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
function ii(e) {
	let { name: t, value: n, hasValue: r } = ri(e);
	return t === "account-copy-secret" ? r && ni(ei, n) : !r && (t === "account-totp-copy" || ni($r, t) || ni(ti, t));
}
function ai(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("服务端响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error(typeof t.error == "string" ? t.error : "请求失败");
	return t;
}
function oi(e) {
	if (!e) return "";
	if (typeof e != "string") throw Error("服务端响应格式无效");
	return e;
}
function si(e) {
	let t = Number(e || 0);
	if (!Number.isFinite(t) || !Number.isInteger(t) || t < 0) throw Error("服务端响应格式无效");
	return t;
}
function ci(e) {
	if (e.download_url == null || e.download_url === "") throw Error("服务端未返回下载地址");
	if (typeof e.download_url != "string" || e.filename != null && typeof e.filename != "string") throw Error("服务端响应格式无效");
	if (!e.download_url.trim()) throw Error("服务端未返回下载地址");
	return {
		url: e.download_url,
		filename: e.filename || ""
	};
}
function li(e) {
	if (!Array.isArray(e?.accountIds)) throw Error("账号动作上下文不可用，请刷新后重试");
	let t = e.accountIds.map((e) => {
		if (typeof e != "string" || !/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
		return Number(e);
	});
	return Object.freeze([...new Set(t)]);
}
function ui(e) {
	return e instanceof Error ? e.message : "请求失败，请稍后重试。";
}
function di(e) {
	let t = e.queued ? Er(e, e.queued) : void 0, n = e.setup ? Ur(e, e.setup) : void 0, r = e.local ? Qr({
		...e.local,
		request: e.request,
		notify: e.notify,
		confirm: e.confirm,
		canInvoke: e.canInvoke,
		beginBusy: e.beginBusy
	}) : void 0, i = /* @__PURE__ */ new Set(), a = (e, t) => e.startsWith("account-") ? JSON.stringify([e, ...t.map(String)]) : e, o = async (t, n) => ai(await e.request(t, {
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
		return n.values.map((e) => oi(ai(e).value)).filter(Boolean);
	}
	async function c(c, l, u = null) {
		if (t?.isSupported(c)) return t.invoke(c, l, u);
		if (n?.isSupported(c)) return n.invoke(c, l, u);
		if (r?.isSupported(c)) return r.invoke(c, l, u);
		if (!ii(c)) throw Error(`未支持的账号动作：${ri(c).name}`);
		if (e.canInvoke?.(c, u) === !1) return;
		let { name: d, value: f } = ri(c), p = ni($r, d) ? $r[d] : void 0, m = p?.error ?? ti[d] ?? (d === "account-totp-copy" ? "复制验证码失败: " : "复制失败: "), h, g, _ = !1, v = () => {
			h && i.delete(h);
			let e = g;
			g = void 0, e?.();
		};
		try {
			let t = li(l);
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
				let n = oi(ai(await e.request(`/api/accounts/${t[0]}/secret?field=${encodeURIComponent(f)}`)).value);
				if (!n) {
					e.notify("可复制内容为空");
					return;
				}
				await e.clipboard(n), e.notify(ei[f]);
			} else if (d === "account-totp-copy") {
				let n = ai(await e.request(`/api/accounts/${t[0]}/totp-code`)), r = oi(n.code);
				if (!r) throw Error("验证码为空");
				let i = si(n.remaining_seconds), a = await e.clipboard(r, !1);
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
				}), { url: r, filename: i } = ci(n), a = si(n.added_count), s = si(n.skipped_count);
				await e.downloadUrl(r, i), e.notify(a === 0 ? `没有可下载的 Session，已生成结果清单，跳过 ${s} 个；开始下载，分类原因见 ZIP 内 manifest.json；Session 缺失或无效的账号请先刷新 AT，读取失败的账号请重试` : `已打包 ${a} 个账号 Session，跳过 ${s} 个；开始下载，结果见 ZIP 内 manifest.json`);
			} else if (d === "downloadSelectedCpa") {
				let n = await o("/api/accounts/download-cpa-bulk", {
					account_ids: t,
					prepare: !0
				}), { url: r, filename: i } = ci(n), a = si(n.error_count);
				await e.downloadUrl(r, i), e.notify(`已生成 ZIP，开始下载${a ? `（${a} 个失败见 manifest）` : ""}`), e.schedule(() => {
					Promise.resolve().then(() => e.reloadCodex()).catch((t) => e.notify(`下载已开始，但 Codex 列表刷新失败: ${ui(t)}`));
				}, 1200);
			}
		} catch (t) {
			e.notify(m + ui(t));
		} finally {
			_ ? e.schedule(v, 1200) : v();
		}
	}
	return {
		isSupported: (e) => ii(e) || t?.isSupported(e) === !0 || n?.isSupported(e) === !0 || r?.isSupported(e) === !0,
		invoke: c,
		isPending: (e, o) => i.has(a(e, o.accountIds)) || t?.isPending(e, o) === !0 || n?.isPending(e, o) === !0 || r?.isPending(e, o) === !0,
		setVisible: (e) => t?.setVisible(e),
		dispose: () => t?.dispose()
	};
}
// src/features/accounts/browserDownloads.ts
function fi(e) {
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
function pi(e, t) {
	let n = te(t.query), r = fi({
		document,
		origin: window.location.origin,
		urls: URL,
		schedule: (e, t) => setTimeout(e, t)
	}), i = di({
		...t.actionDependencies,
		request: X,
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
	return O(cr, {
		adapter: n,
		api: pr(n),
		presentation: je(t.presentation),
		callbacks: t.callbacks,
		detailApi: mr(),
		detailPresentation: t.detailPresentation,
		syncModalScrollLock: t.syncModalScrollLock,
		actions: i,
		inspectionDependencies: {
			...t.inspectionDependencies,
			request: X
		},
		emailChangeDependencies: {
			...t.emailChangeDependencies,
			request: X
		},
		c2aDependencies: {
			...t.c2aDependencies,
			request: X
		},
		initialCapabilities: t.capabilities,
		toolbarRuntime: a
	}).mount(e);
}
export { pi as mountAccounts };
