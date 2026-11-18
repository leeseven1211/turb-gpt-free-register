import { $ as e, A as t, G as n, I as r, M as i, N as a, P as o, Q as s, S as c, V as l, W as u, X as d, Y as f, _ as p, a as m, b as h, c as g, ct as _, d as v, dt as y, et as b, g as x, h as S, i as C, j as w, k as T, m as E, n as D, o as O, ot as k, p as A, s as j, t as M, tt as N, u as P, ut as F, x as I } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { a as L, i as R, n as z, o as B, r as V, s as H, t as U } from "./ListFilterSummary-NiVwXoAn.js";
import { t as W } from "./ListPagination-CFFXEHba.js";
import { a as G, i as K, n as q, o as J, r as Y, s as ee, t as te } from "./queryAdapter-C1wcY8t-.js";
import { t as ne } from "./useColumnWidths-DKwoq5eG.js";
import { t as re } from "./errorLabels-6tZmqsp4.js";
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
		title: "批量同步选中账号的本地当前 AT，支持跨页选择；只更新唯一同邮箱的 C2A 既有账号",
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
		title: "复制选中账号的完整整行，每个账号一行",
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
function ue(e, t, n) {
	let r = N({}), i = N(le(e, {})), a, o = !1;
	function c() {
		let n = r.value;
		try {
			let e = t.storage.getItem(se);
			e !== null && (n = JSON.parse(e));
		} catch {}
		return Object.fromEntries(e.map((e) => {
			let t = n && typeof n == "object" && !Array.isArray(n) ? n[e] : 0;
			return [e, Number.isSafeInteger(t) && Number(t) > 0 ? Number(t) : 0];
		}));
	}
	function l() {
		if (o || n()) return;
		r.value = c();
		let t = le(e, r.value);
		t.join(",") !== i.value.join(",") && (i.value = t);
	}
	function u() {
		o || a !== void 0 || (a = t.requestFrame(() => {
			a = void 0, l();
		}));
	}
	function f(n) {
		if (o || !e.includes(n)) return;
		let i = c();
		i[n] = Math.min(2 ** 53 - 1, i[n] + 1), r.value = i;
		try {
			t.storage.setItem(se, JSON.stringify(i));
		} catch {}
		u();
	}
	let p = t.addStorageListener((e) => {
		e.key === "turb_account_action_usage_v1" && u();
	});
	return d(() => {
		o = !0, a !== void 0 && t.cancelFrame(a), a = void 0, p();
	}), {
		counts: s(r),
		quickIds: s(i),
		refresh: l,
		schedule: u,
		record: f
	};
}
// src/features/accounts/AccountsToolbar.vue?vue&type=script&setup=true&lang.ts
var de = {
	class: "accounts-command-deck",
	id: "accountsCommandDeck"
}, fe = {
	class: "list-selection-hint",
	id: "accountsSelectedHintV2"
}, pe = {
	class: "acc-v2-btn-group account-quick-actions",
	id: "accountsQuickActionsV2",
	role: "group",
	"aria-label": "常用账号操作，按此浏览器使用次数排序",
	title: "显示此浏览器使用次数最多的五项操作，批量操作一次算一次"
}, me = { class: "toolbar-overflow-menu" }, he = { class: "toolbar-overflow-section-title" }, ge = [
	"id",
	"disabled",
	"title",
	"data-feature",
	"data-feature-base-title",
	"aria-disabled",
	"onClick"
], _e = /*#__PURE__*/ M(/* @__PURE__ */ c({
	__name: "AccountsToolbar",
	props: {
		state: {},
		capabilities: {},
		getContext: { type: Function },
		invoke: { type: Function },
		runtime: {},
		notify: { type: Function }
	},
	setup(n, { expose: i }) {
		let a = n, s = e(), c = e(), l = e(!1), u = /* @__PURE__ */ new Map(), d = /* @__PURE__ */ new Map(), f = N(/* @__PURE__ */ new Set()), m = ue(oe.map((e) => e.id), a.runtime, () => {
			let e = s.value, t = e?.ownerDocument;
			return !!(c.value?.open || t?.querySelector("dialog[open]") || e?.contains(t?.activeElement ?? null));
		});
		function h(e, t, n) {
			let r = e;
			n && typeof n == "object" && "nodeType" in n ? r.set(t, n) : r.delete(t);
		}
		function g(e) {
			let t = m.quickIds.value.indexOf(e.id);
			return t >= 0 ? d.get(t) : u.get(e.id);
		}
		let b = (e) => e.feature ? a.capabilities[e.feature] : void 0, C = (e) => b(e)?.enabled === !1, T = (e) => e.selection && a.state.selectedCount === 0 || f.value.has(e.action) || !!a.state.pending?.[e.action], D = (e) => a.state.labels?.[e.action] || (e.id === "btnArchiveSelectedAccountsV2" && a.state.archived ? "恢复选中" : e.label), O = (e) => e.id === "btnArchiveSelectedAccountsV2" && a.state.archived ? "把选中的归档账号恢复到默认账号列表" : e.title, A = (e) => C(e) ? `不可用：${b(e)?.reason || "缺少必要配置"}` : O(e);
		async function j(e, t) {
			let n = t.currentTarget;
			if (!(T(e) || C(e) || n.disabled || n.getAttribute("aria-disabled") === "true")) {
				m.record(e.id), f.value = /* @__PURE__ */ new Set([...f.value, e.action]);
				try {
					await a.invoke(e.action, a.getContext(), n);
				} catch (e) {
					a.notify?.(e instanceof Error ? e.message : "账号操作失败，请稍后重试。");
				} finally {
					let t = new Set(f.value);
					t.delete(e.action), f.value = t;
				}
			}
		}
		let M;
		return w(() => {
			M = s.value?.ownerDocument, M?.addEventListener("close", m.schedule, !0), l.value = !0, m.refresh();
		}), t(() => M?.removeEventListener("close", m.schedule, !0)), i({ refreshQuickActions: m.refresh }), (e, t) => (o(), p("div", de, [E("div", {
			ref_key: "toolbar",
			ref: s,
			class: _(["jobs-toolbar-v2 list-action-toolbar", { "has-selection": n.state.selectedCount > 0 }]),
			id: "accountsToolbarV2",
			onFocusout: t[1] ||= (...e) => k(m).schedule && k(m).schedule(...e)
		}, [
			E("span", fe, y(n.state.selectedCount ? `已选 ${n.state.selectedCount} 个账号` : "选择账号后批量操作"), 1),
			E("div", pe, [(o(), p(P, null, r(5, (e) => E("span", {
				key: e,
				ref_for: !0,
				ref: (t) => h(k(d), e - 1, t),
				class: "account-action-slot"
			}, null, 512)), 64))]),
			E("details", {
				ref_key: "more",
				ref: c,
				class: "toolbar-overflow",
				id: "accountsMoreActionsV2",
				onToggle: t[0] ||= (...e) => k(m).schedule && k(m).schedule(...e)
			}, [t[2] ||= E("summary", null, "更多操作", -1), E("div", me, [(o(!0), p(P, null, r(k(Z), (e) => (o(), p("div", {
				key: e,
				class: "toolbar-overflow-section toolbar-overflow-section--wide"
			}, [E("span", he, y(e), 1), (o(!0), p(P, null, r(k(oe).filter((t) => t.section === e), (e) => (o(), p("span", {
				key: e.id,
				ref_for: !0,
				ref: (t) => h(k(u), e.id, t),
				class: "account-action-slot"
			}))), 128))]))), 128))])], 544)
		], 34), l.value ? (o(!0), p(P, { key: 0 }, r(k(oe), (e) => (o(), S(v, {
			key: e.id,
			to: g(e)
		}, [E("button", {
			type: "button",
			id: e.id,
			class: _([e.className, { "feature-unavailable": C(e) }]),
			disabled: T(e),
			title: A(e),
			"data-feature": b(e) ? e.feature : void 0,
			"data-feature-base-title": b(e) ? O(e) : void 0,
			"aria-disabled": b(e) ? C(e) : void 0,
			onClick: (t) => j(e, t)
		}, y(D(e)), 11, ge)], 8, ["to"]))), 128)) : x("", !0)]));
	}
}), [["__scopeId", "data-v-0afc08c3"]]), ve = { class: "ac-filter-fields" }, ye = {
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
], Ee = { class: "ac-filter-actions" }, De = /* @__PURE__ */ c({
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
	setup(t, { emit: i }) {
		let a = t, s = i, c = e("id"), l = A(() => a.column || q.find((e) => e.key === c.value) || q[0]), d = A(() => a.column ? Y(a.query, a.column) : q.some((e) => Y(a.query, e))), f = A(() => G(a.query, a.label).find((e) => e.key === l.value.key)?.label || ""), m = A(() => K(a.query, a.facets, l.value, a.label)), _ = A(() => J(a.query, l.value.key)), v = A(() => l.value.kind === "date-range" ? ["date_from", "date_to"] : [l.value.key]);
		function b(e, t) {
			let n = new Set(_.value);
			t ? n.add(e) : n.delete(e), s("change", l.value.key, [...n]);
		}
		function w() {
			s("clear", l.value.key), s("update:open", !1);
		}
		return (e, i) => (o(), S(V, {
			label: t.column?.label || "账号",
			"trigger-label": t.column ? void 0 : "筛选",
			active: d.value,
			summary: f.value,
			open: t.open,
			"onUpdate:open": i[4] ||= (e) => s("update:open", e)
		}, {
			default: u(() => [E("div", ve, [
				t.column ? x("", !0) : (o(), p("label", ye, [i[5] ||= h("筛选列", -1), n(E("select", {
					"onUpdate:modelValue": i[0] ||= (e) => c.value = e,
					"aria-label": "选择账号筛选列"
				}, [(o(!0), p(P, null, r(k(q), (e) => (o(), p("option", {
					key: e.key,
					value: e.key
				}, y(e.label), 9, be))), 128))], 512), [[C, c.value]])])),
				l.value.kind === "enum" ? (o(), p("fieldset", xe, [
					E("legend", Se, y(l.value.label) + "，可多选", 1),
					E("label", null, [E("input", {
						type: "checkbox",
						checked: !_.value.length,
						onChange: i[1] ||= (e) => s("change", l.value.key, [])
					}, null, 40, Ce), i[6] ||= E("span", null, "全部", -1)]),
					(o(!0), p(P, null, r(m.value, (e) => (o(), p("label", { key: e.value }, [
						E("input", {
							type: "checkbox",
							value: e.value,
							checked: _.value.includes(e.value),
							onChange: (t) => b(e.value, t.target.checked)
						}, null, 40, we),
						E("span", null, y(e.label), 1),
						E("small", null, y(e.count), 1)
					]))), 128))
				])) : (o(!0), p(P, { key: 2 }, r(v.value, (e, n) => (o(), p("label", {
					key: e,
					class: "ac-filter-field"
				}, [h(y(l.value.kind === "date-range" ? n ? "截止日期" : "开始日期" : l.value.label), 1), E("input", {
					type: l.value.kind === "date-range" ? "date" : "text",
					inputmode: l.value.key === "id" ? "numeric" : void 0,
					value: k(ee)(t.query, e),
					placeholder: l.value.placeholder,
					autocomplete: "off",
					onInput: (t) => s("change", e, t.target.value),
					onKeydown: i[2] ||= j(g((e) => s("update:open", !1), ["prevent"]), ["enter"])
				}, null, 40, Te)]))), 128)),
				E("div", Ee, [E("button", {
					type: "button",
					class: "ac-link",
					onClick: w
				}, "清除此列"), E("button", {
					type: "button",
					class: "ac-button",
					onClick: i[3] ||= (e) => s("update:open", !1)
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
			if (a === "account_status") return r(o);
			if (a === "codex") {
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
}, ct = /* @__PURE__ */ c({
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
	setup(n, { expose: i, emit: s }) {
		let c = n, d = s, { widths: f, total: m, resize: v, resizeWithKeyboard: b, resetColumns: C } = ne({
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
		}), T = e(), D = e(null);
		function O(e) {
			if (!c.stale) return e;
			let t = document.createElement("template");
			return t.innerHTML = e, t.content.querySelectorAll("button,input,select,textarea").forEach((e) => e.setAttribute("disabled", "")), t.content.querySelectorAll("a,[role=\"button\"],[data-copy-id]").forEach((e) => {
				e.setAttribute("aria-disabled", "true"), e.setAttribute("tabindex", "-1");
			}), t.innerHTML;
		}
		let M = A(() => (c.stale && c.loading ? [] : c.items).map((e) => ({
			row: e,
			id: String(e.id),
			cells: Object.fromEntries(Oe.filter((e) => e.cell).map((t) => [t.cell, O(c.presentation.cell(t.cell, e))])),
			menu: c.presentation.menu(e),
			mobile: c.presentation.mobileSummary(e),
			tone: c.presentation.rowTone(e)
		}))), N = (e) => q.find((t) => t.key === e);
		function V(e, t) {
			if (c.stale || !c.visible) {
				e.preventDefault(), e.stopPropagation();
				return;
			}
			let n = e.target instanceof Element ? e.target : null, r = n?.closest("[data-account-detail-id]");
			if (r) {
				e.preventDefault(), e.stopPropagation(), d("detail", String(t.id), r);
				return;
			}
			let i = Ne(e.target);
			i ? (e.preventDefault(), e.stopPropagation(), D.value = null, d("action", i.action, String(t.id), i.trigger)) : window.matchMedia("(max-width:860px)").matches && !n?.closest("button,a,input,label,[role=\"dialog\"]") && d("detail", String(t.id), null);
		}
		function U() {
			D.value = null;
		}
		function W(e) {
			e.target instanceof Element && e.target.closest(".ac-row-menu") || U();
		}
		return l(() => c.visible, (e) => {
			e || U();
		}), l(() => c.stale, (e) => {
			e && U();
		}), l(() => c.items, (e) => {
			D.value && !e.some((e) => String(e.id) === D.value) && U();
		}), w(() => {
			window.addEventListener("resize", U), window.addEventListener("scroll", W, !0), T.value && d("rendered", T.value);
		}), a(() => {
			T.value && d("rendered", T.value);
		}), t(() => {
			window.removeEventListener("resize", U), window.removeEventListener("scroll", W, !0);
		}), i({
			resetColumns: C,
			closeMenu: U
		}), (e, t) => (o(), p("div", {
			ref_key: "root",
			ref: T,
			class: "accounts-table-v2-wrap ac-table-scroll",
			tabindex: "0",
			"aria-label": "账号列表，可横向滚动",
			"aria-busy": n.loading,
			onScroll: U
		}, [E("table", {
			class: "accounts-table-v2 ac-table",
			style: F({ width: `${k(m)}px` }),
			"data-stale": n.stale || void 0
		}, [
			t[5] ||= E("caption", { class: "ac-sr-only" }, "账号资产，支持跨页选择", -1),
			E("colgroup", null, [(o(!0), p(P, null, r(k(f), (e, t) => (o(), p("col", {
				key: t,
				style: F({ width: `${e}px` })
			}, null, 4))), 128))]),
			E("thead", null, [E("tr", null, [(o(!0), p(P, null, r(k(Oe), (e, r) => (o(), p("th", {
				key: e.key,
				scope: "col",
				class: _(e.className)
			}, [e.key === "selection" ? (o(), p("input", {
				key: 0,
				id: "accountsSelectAllV2",
				type: "checkbox",
				"aria-label": "全选当前页账号",
				checked: n.pageSelected,
				indeterminate: n.pageIndeterminate,
				disabled: n.stale || !n.items.length,
				onChange: t[0] ||= (e) => d("selectPage", e.target.checked)
			}, null, 40, Ie)) : e.filter ? (o(), S(De, {
				key: 1,
				column: N(e.filter),
				query: n.query,
				facets: n.facets,
				label: n.presentation.facetLabel,
				open: n.visible && n.openFilter === e.filter,
				"onUpdate:open": (t) => d("update:openFilter", t ? e.filter : null),
				onChange: t[1] ||= (e, t) => d("filter", e, t),
				onClear: t[2] ||= (e) => d("clearFilter", e)
			}, null, 8, [
				"column",
				"query",
				"facets",
				"label",
				"open",
				"onUpdate:open"
			])) : (o(), p(P, { key: 2 }, [h(y(e.label), 1)], 64)), r ? (o(), p("button", {
				key: 3,
				type: "button",
				class: "ac-column-resize",
				"aria-label": `调整${e.label}列宽，方向键调整`,
				onPointerdown: g((e) => k(v)(r, e), ["prevent"]),
				onKeydown: [j(g((e) => k(b)(r, -10), ["prevent"]), ["left"]), j(g((e) => k(b)(r, 10), ["prevent"]), ["right"])]
			}, null, 40, Le)) : x("", !0)], 2))), 128))])]),
			E("tbody", Re, [(o(!0), p(P, null, r(M.value, (e) => (o(), p("tr", {
				key: e.id,
				"data-account-row": e.id,
				class: _({ "ac-row-selected": n.selected.has(e.id) }),
				onClick: (t) => V(t, e.row)
			}, [
				E("td", Be, [E("input", {
					type: "checkbox",
					class: "account-row-check",
					"data-account-id": e.id,
					"aria-label": `选择账号 ${e.row.email || e.id}`,
					checked: n.selected.has(e.id),
					disabled: n.stale,
					onChange: (t) => d("select", e.id, t.target.checked)
				}, null, 40, Ve)]),
				E("td", He, [I(z, { text: `#${e.id}` }, null, 8, ["text"])]),
				E("td", Ue, [
					E("button", {
						type: "button",
						class: "acc-v2-email-link account-cell-line",
						disabled: n.stale,
						"data-account-detail-id": e.id,
						title: "查看账号详情"
					}, [E("span", {
						class: _(["acc-mobile-dot", `is-${e.tone}`]),
						"aria-hidden": "true"
					}, null, 2), E("span", Ge, [h(y(e.row.email), 1), e.row.archived ? (o(), p("span", Ke, "归档")) : x("", !0)])], 8, We),
					E("div", qe, [E("span", Je, y(e.row.user_name || "-"), 1), E("span", { innerHTML: n.presentation.emailInvalidBadge(e.row) }, null, 8, Ye)]),
					E("div", Xe, y(e.mobile), 1)
				]),
				E("td", Ze, [I(z, { text: e.row.email_source || "-" }, null, 8, ["text"])]),
				E("td", Qe, [I(z, { text: n.presentation.registrationDriverLabel(e.row.registration_driver) }, null, 8, ["text"])]),
				(o(!0), p(P, null, r(k(Oe).filter((e) => e.cell), (t) => (o(), p("td", {
					key: t.key,
					class: _(t.className),
					"data-label": t.label
				}, [E("div", {
					class: "ac-legacy-cell",
					innerHTML: e.cells[t.cell]
				}, null, 8, et)], 10, $e))), 128)),
				E("td", tt, [E("div", nt, [E("button", {
					type: "button",
					class: "acc-v2-detail",
					disabled: n.stale,
					"data-account-detail-id": e.id
				}, "详情", 8, rt), I(k(H), {
					open: n.visible && !n.stale && D.value === e.id,
					modal: !1,
					"onUpdate:open": (t) => D.value = t ? e.id : null
				}, {
					default: u(() => [I(k(R), { "as-child": "" }, {
						default: u(() => [E("button", {
							type: "button",
							class: "acc-v2-more-btn",
							disabled: n.stale,
							"aria-label": "更多账号操作"
						}, "更多", 8, it)]),
						_: 1
					}), I(k(L), null, {
						default: u(() => [I(k(B), {
							class: "ac-row-menu accounts-table-v2",
							"data-account-menu": e.id,
							side: "bottom",
							align: "end",
							"side-offset": 4,
							"collision-padding": 8,
							onOpenAutoFocus: t[3] ||= g(() => {}, ["prevent"])
						}, {
							default: u(() => [E("div", {
								class: "acc-v2-more-menu ac-menu-content",
								onClick: (t) => V(t, e.row),
								innerHTML: e.menu
							}, null, 8, at)]),
							_: 2
						}, 1032, ["data-account-menu"])]),
						_: 2
					}, 1024)]),
					_: 2
				}, 1032, ["open", "onUpdate:open"])])])
			], 10, ze))), 128)), M.value.length ? x("", !0) : (o(), p("tr", ot, [E("td", st, [
				E("strong", null, y(n.loading ? "正在加载账号" : n.invalidSearch ? "搜索条件有误" : n.error ? "账号加载失败" : "暂无匹配账号"), 1),
				E("p", null, y(n.loading ? "正在同步账号状态和授权信息" : n.invalidSearch ? "请按输入框旁的提示修改，或清空高级搜索。" : n.error || "可移除部分搜索条件，或切换活跃与归档账号视图。"), 1),
				n.error && !n.invalidSearch ? (o(), p("button", {
					key: 0,
					type: "button",
					class: "ac-button",
					onClick: t[4] ||= (e) => d("retry")
				}, "重试")) : x("", !0)
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
function ht(t, n) {
	let r = N(t.normalize()), i = N([]), a = N({}), o = N([]), c = N(null), l = e(0), u = e(1), f = e(10), p = e(!1), m = e(!1), h = e(!1), g = e(""), _ = e(!1), v = e(""), y = N(/* @__PURE__ */ new Set()), b = N({}), x = e(""), S = A(() => Math.max(1, Math.ceil(l.value / f.value))), C = A(() => t.toLegacy(r.value, {
		paged: "1",
		page: u.value,
		page_size: f.value
	}).toString()), w = A(() => x.value !== C.value), E = A(() => i.value.length > 0 && i.value.every((e) => y.value.has(String(e.id)))), D = A(() => !E.value && i.value.some((e) => y.value.has(String(e.id)))), O = 0, k = 0, j = 0, M = 0, P = !1, F = !1, I, L, R, z, B, V = "", H, U = /* @__PURE__ */ new Map(), W = /* @__PURE__ */ new Map(), G = () => typeof document > "u" || !document.hidden, K = () => !P && h.value && G(), q = (e, t) => e === O && t === C.value && K();
	function J(e) {
		return [...W.values()].some((t) => t === e);
	}
	function Y() {
		let e = /* @__PURE__ */ new Set([...i.value.map((e) => String(e.id)), ...W.values()]);
		for (let [t, n] of U) e.has(t) || (n.request?.controller.abort(), U.delete(t));
	}
	function ee() {
		for (let e of U.values()) e.request?.controller.abort(), e.request = void 0, ++e.version;
	}
	function te() {
		++O, ++k, I?.abort(), L?.abort(), I = L = void 0, clearTimeout(R), clearTimeout(B), R = B = void 0, p.value = m.value = !1;
	}
	function ne() {
		clearTimeout(R), R = void 0, K() && H !== r.value.q && (R = setTimeout(() => {
			se();
		}, 5e3));
	}
	function re(e) {
		let t = Q(e);
		for (let e of lt) {
			let n = e === "plan" ? r.value.plan : r.value.filters[e];
			if (!n.length) continue;
			let i = t[e] ?? [];
			t[e] = [...i, ...n.filter((e) => !i.some((t) => t.value === e)).map((e) => ({
				value: e,
				count: 0
			}))];
		}
		return t;
	}
	function X(e) {
		i.value = Q(e);
		for (let e of i.value) {
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
		let e = O, t = new AbortController();
		I = t, p.value = !0;
		try {
			for (let i = 0; i < 2; i++) {
				let s = C.value, c = Q(r.value), d = u.value, p = f.value, m = await n.list(c, d, p, t.signal);
				if (!q(e, s)) return;
				let h = Math.max(1, Math.ceil(m.total / p));
				if (d > h) {
					if (u.value = h, !i) continue;
					g.value = "列表范围已变化，请刷新后重试";
					return;
				}
				X(m.items), l.value = m.total, a.value = re(m.facets), o.value = Q(m.search_terms), x.value = s, V = "", g.value = "", _.value = !1, H = void 0;
				return;
			}
		} catch (t) {
			if (e !== O || !K() || ie(t)) return;
			g.value = t instanceof Error ? t.message : "加载账号失败", t instanceof ae && t.code === "account_search_invalid" && (H = r.value.q, _.value = !0, i.value = [], l.value = 0, o.value = [], a.value = {}, Y());
		} finally {
			e === O && (p.value = !1, I = void 0, ne());
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
		if (clearTimeout(R), R = void 0, !K() || p.value || m.value || w.value || H === r.value.q) {
			ne();
			return;
		}
		let e = O, t = C.value, s = new AbortController();
		L = s, m.value = !0;
		try {
			let a = await n.statuses(Q(r.value), u.value, f.value, s.signal);
			if (!q(e, t)) return;
			let o = new Map(i.value.map((e) => [String(e.id), e]));
			if (a.total !== l.value || a.items.length !== i.value.length || a.items.some((e) => !o.has(String(e.id))) || new Set(a.items.map((e) => e.id)).size !== a.items.length) {
				await Z();
				return;
			}
			if (c.value = Q(a.queue), V === a.revision) return;
			let d = (e) => e === "queued" || e === "running", p = !1;
			i.value = a.items.map((e) => {
				let t = o.get(String(e.id));
				return (d(t.plan_check_status) && !d(e.plan_check_status) || d(t.extract_link_status) && !d(e.extract_link_status)) && (p = !0), oe(t, e, a.status_fields);
			}), V = a.revision, p && await Z();
		} catch (n) {
			q(e, t) && n instanceof ae && n.code === "account_search_invalid" && (H = r.value.q, _.value = !0, g.value = n instanceof Error ? n.message : "筛选语法无效", i.value = [], l.value = 0, a.value = {}, o.value = [], Y());
		} finally {
			e === O && (m.value = !1, L = void 0, ne());
		}
	}
	function ce(e = 0) {
		if (te(), !K()) return;
		let t = k, n = () => {
			t === k && K() && Z();
		};
		e ? B = setTimeout(n, e) : T(n);
	}
	function le() {
		y.value = /* @__PURE__ */ new Set(), b.value = {}, ++j;
	}
	function ue(e, n = 0) {
		if (P) return;
		let i = t.normalize(e);
		clearTimeout(z), z = void 0, t.toLegacy(i).toString() === t.toLegacy(r.value).toString() && i.limit === r.value.limit ? v.value = i.q : (r.value = Q(i), v.value = i.q, u.value = 1, le(), _.value = !1, g.value = "", H = void 0, ce(n));
	}
	function de(e, t = 0) {
		ue({
			...Q(r.value),
			...Q(e)
		}, t);
	}
	function fe(e, t = 0) {
		de({ filters: {
			...Q(r.value.filters),
			...Q(e)
		} }, t);
	}
	function pe(e) {
		de({ archived: e ? "only" : "0" });
	}
	function me() {
		ue(t.normalize({ archived: r.value.archived }));
	}
	function he(e) {
		if (P || !Number.isFinite(e)) return;
		let t = Math.min(S.value, Math.max(1, Math.floor(e)));
		t !== u.value && (u.value = t, ce());
	}
	function ge(e) {
		if (P || !Number.isFinite(e) || e < 1) return;
		let t = Math.min(500, Math.floor(e));
		t !== f.value && (f.value = t, u.value = 1, ce());
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
		if (t && (w.value || _.value)) throw Error("当前筛选结果尚未加载");
		let n = ft(e), r = i.value.find((e) => String(e.id) === n);
		if (t && !r) throw Error("账号不在当前页");
		let a = new Set(y.value), o = { ...b.value };
		t ? (a.add(n), r?.email?.trim() ? o[n] = r.email : delete o[n]) : (a.delete(n), delete o[n]), y.value = a, b.value = o, ++j;
	}
	function we(e) {
		for (let t of i.value) Ce(String(t.id), e);
	}
	function Te(e) {
		for (let t of e) Ce(t, !1);
	}
	function Ee(e = {}) {
		let t = [...new Set((e.ids ?? [...y.value]).map(ft))], n = {}, a = new Map(i.value.map((e) => [String(e.id), e]));
		for (let e of t) {
			let t = a.has(e) ? a.get(e)?.email : b.value[e];
			t && (n[e] = t);
		}
		if (e.requireEmails && (t.length > 500 || t.some((e) => !n[e]?.trim()))) throw Error(t.length > 500 ? "一次最多处理 500 个账号" : "账号邮箱快照不完整，请刷新后重新选择");
		return dt({
			query: r.value,
			ids: t,
			expectedEmails: n,
			created_at: (/* @__PURE__ */ new Date()).toISOString(),
			source: "accounts",
			generation: j
		});
	}
	function De(e = {}) {
		let t = Ee(e), n = new Set(t.ids);
		return dt({
			accountIds: t.ids,
			expectedEmails: t.expectedEmails,
			querySnapshot: t.query,
			archived: t.query.archived,
			rowHints: i.value.filter((e) => n.has(String(e.id)))
		});
	}
	function Oe(e) {
		let t = i.value.find((t) => String(t.id) === e);
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
		let r = new AbortController(), a = t.version, o = n.planDetails(e, r.signal).then(async (n) => {
			K() && J(e) || pt();
			let r = U.get(e);
			return r || pt(), r !== t || r.version !== a ? ke(e) : (r.details = Q(n.item), i.value = i.value.map((t) => String(t.id) === e ? {
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
			if (r && (r !== t || r.version !== a)) return ke(e);
			throw n;
		}).finally(() => {
			t.request?.promise === o && (t.request = void 0), Y();
		});
		return t.request = {
			version: a,
			controller: r,
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
		let t = ft(e), n = ++M;
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
	return typeof document < "u" && document.addEventListener("visibilitychange", Ne), d(() => {
		P = !0, te(), clearTimeout(z), ee(), W.clear(), U.clear(), typeof document < "u" && document.removeEventListener("visibilitychange", Ne);
	}), {
		query: s(r),
		items: s(i),
		facets: s(a),
		searchTerms: s(o),
		queue: s(c),
		total: s(l),
		page: s(u),
		size: s(f),
		pages: S,
		selected: s(y),
		selectedEmails: s(b),
		loading: s(p),
		polling: s(m),
		visible: s(h),
		error: s(g),
		invalidSearch: s(_),
		draftSearch: s(v),
		renderedSignature: s(x),
		signature: C,
		stale: w,
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
}, Et = /* @__PURE__ */ c({
	__name: "AccountsList",
	props: {
		adapter: {},
		api: {},
		presentation: {},
		callbacks: {}
	},
	setup(r, { expose: i }) {
		let a = r, s = ht(a.adapter, a.api), { query: c, items: u, facets: d, searchTerms: f, total: m, page: h, size: _, pages: v, selected: b, loading: S, error: C, visible: w, invalidSearch: T, draftSearch: D, stale: M, pageSelected: N, pageIndeterminate: P } = s, F = e(), L = e(), R = e(null), z = e(typeof document > "u" || !document.hidden), B = e(""), V = /* @__PURE__ */ new Set(), H = q.find((e) => e.key === "email_status"), K = A(() => [...G(c.value, a.presentation.facetLabel), ...f.value.map((e, t) => ({
			key: `search:${t}`,
			label: `${e.label}：${e.display_value}`,
			title: `高级搜索 · 同时满足：${e.label}：${e.display_value}`,
			removeLabel: `移除${e.label}：${e.display_value}`
		}))]);
		function J(e, t) {
			e === "plan" ? s.updateQuery({ plan: [...t] }) : e === "date_from" || e === "date_to" ? s.updateQuery({ [e]: String(t) }) : e === "id" || e === "email" ? s.updateFilters({ [e]: String(t) }, 250) : s.updateFilters({ [e]: [...t] });
		}
		function Y(e) {
			if (e.startsWith("search:")) {
				let t = f.value[Number(e.slice(7))];
				t && s.removeSearchTerm({ ...t }), L.value?.focus();
				return;
			}
			if (e === "date") {
				s.updateQuery({
					date_from: "",
					date_to: ""
				});
				return;
			}
			let t = q.find((t) => t.key === e);
			t && J(t.key, t.kind === "text" ? "" : []);
		}
		function ee(e) {
			B.value = e instanceof Error ? e.message : "账号操作暂不可用", a.callbacks.notify?.(B.value);
		}
		async function te(e, t, n) {
			if (M.value || !w.value || !z.value) return;
			let r = JSON.stringify([t, e]);
			if (!V.has(r)) {
				V.add(r), B.value = "";
				try {
					let r = s.getActionContext({
						ids: [t],
						requireEmails: e.startsWith("account-email-invalid:")
					});
					await a.callbacks.invoke(e, r, n);
				} catch (e) {
					ee(e);
				} finally {
					V.delete(r);
				}
			}
		}
		function ne(e, t) {
			if (M.value || !w.value || !z.value) return;
			B.value = "";
			let n = s.getRowSnapshot(e);
			if (!n) {
				ee(/* @__PURE__ */ Error("账号详情暂不可用，请先刷新列表"));
				return;
			}
			let r;
			try {
				r = s.openPlanDetailsConsumer(e), a.callbacks.openDetail(e, n, r, t);
			} catch (e) {
				r?.release(), ee(e);
			}
		}
		function re(e) {
			e || (R.value = null, a.callbacks.closeConsumers?.(!1)), s.setVisible(e);
		}
		function ie(e) {
			R.value = null, s.setArchived(e);
		}
		function X() {
			s.clearSearch(), L.value?.focus();
		}
		function ae() {
			F.value?.resetColumns();
		}
		l([
			s.selected,
			s.selectedEmails,
			m,
			h,
			_,
			c,
			S,
			w
		], () => a.callbacks.onStateChange?.(Object.freeze({
			selectedIds: Object.freeze([...b.value]),
			selectedEmails: Object.freeze({ ...s.selectedEmails.value }),
			total: m.value,
			page: h.value,
			size: _.value,
			archived: c.value.archived,
			loading: S.value,
			visible: w.value
		})), {
			immediate: !0,
			flush: "post"
		});
		let Z = () => {
			z.value = !document.hidden, document.hidden && (R.value = null, a.callbacks.closeConsumers?.());
		};
		return typeof document < "u" && document.addEventListener("visibilitychange", Z), t(() => {
			typeof document < "u" && document.removeEventListener("visibilitychange", Z), a.callbacks.closeConsumers?.();
		}), i({
			refresh: s.refresh,
			pollStatuses: s.pollStatuses,
			setVisible: re,
			setArchived: ie,
			openDetail: ne,
			setPage: s.setPage,
			setSize: s.setSize,
			closeMoreMenus: () => F.value?.closeMenu(),
			updateQuery: s.updateQuery,
			updateFilters: s.updateFilters,
			resetFilters: s.resetFilters,
			resetColumns: ae,
			getAccountSelectionSnapshot: s.getAccountSelectionSnapshot,
			getActionContext: s.getActionContext,
			getRowSnapshot: s.getRowSnapshot,
			openPlanDetailsConsumer: s.openPlanDetailsConsumer,
			removeAcknowledgedSelection: s.removeAcknowledgedSelection,
			clearSelection: s.clearSelection
		}), (e, t) => n((o(), p("section", gt, [
			E("div", _t, [E("div", vt, [E("span", yt, y(k(m).toLocaleString()) + " 个账号 · 当前页 " + y(k(u).length) + " 条", 1), I(U, {
				items: K.value,
				onRemove: Y
			}, null, 8, ["items"])]), E("div", bt, [
				E("div", xt, [I(De, {
					query: k(c),
					facets: k(d),
					label: r.presentation.facetLabel,
					open: z.value && R.value === "all",
					"onUpdate:open": t[0] ||= (e) => R.value = e ? "all" : null,
					onChange: J,
					onClear: Y
				}, null, 8, [
					"query",
					"facets",
					"label",
					"open"
				])]),
				I(De, {
					column: k(H),
					query: k(c),
					facets: k(d),
					label: r.presentation.facetLabel,
					open: z.value && R.value === "email_status",
					"onUpdate:open": t[1] ||= (e) => R.value = e ? "email_status" : null,
					onChange: J,
					onClear: Y
				}, null, 8, [
					"column",
					"query",
					"facets",
					"label",
					"open"
				]),
				E("form", {
					class: "ac-search",
					role: "search",
					onSubmit: t[5] ||= g((...e) => k(s).submitSearch && k(s).submitSearch(...e), ["prevent"])
				}, [
					t[11] ||= E("label", { for: "accountAdvancedSearchV2" }, "高级搜索", -1),
					E("input", {
						id: "accountAdvancedSearchV2",
						ref_key: "search",
						ref: L,
						type: "search",
						value: k(D),
						placeholder: "空格或 / 组合，如：协议 jp",
						autocomplete: "off",
						"aria-describedby": "accountAdvancedSearchHintV2 accountAdvancedSearchErrorV2",
						"aria-invalid": k(T) || void 0,
						onKeydown: j(g(X, ["prevent"]), ["esc"]),
						onInput: t[2] ||= (e) => k(s).setSearchDraft(e.target.value),
						onCompositionstart: t[3] ||= (...e) => k(s).compositionStart && k(s).compositionStart(...e),
						onCompositionend: t[4] ||= (e) => k(s).compositionEnd(e.target.value)
					}, null, 40, St),
					k(D) ? (o(), p("button", {
						key: 0,
						type: "button",
						"aria-label": "清空高级搜索",
						title: "清空高级搜索",
						onClick: X
					}, "×")) : x("", !0)
				], 32),
				t[12] ||= E("span", {
					id: "accountAdvancedSearchHintV2",
					class: "ac-sr-only"
				}, "空格或 / 表示同时满足；支持方式、地区、邮箱、姓名、来源、备注、ID。完整文字加双引号。", -1),
				E("button", {
					id: "btnResetAccountFiltersV2",
					type: "button",
					class: "ac-link",
					title: "清除全部列筛选",
					onClick: t[6] ||= (...e) => k(s).resetFilters && k(s).resetFilters(...e)
				}, "清筛"),
				E("button", {
					id: "btnResetAccountsColumnsV2",
					type: "button",
					class: "ac-link",
					title: "恢复账号列表默认列宽",
					onClick: ae
				}, "恢复列宽"),
				E("button", {
					id: "btnRefreshAccountsV2",
					type: "button",
					class: "ac-button",
					disabled: k(S),
					onClick: t[7] ||= (...e) => k(s).refresh && k(s).refresh(...e)
				}, y(k(S) ? "刷新中…" : "刷新"), 9, Ct)
			])]),
			k(T) ? (o(), p("p", wt, y(k(C)), 1)) : B.value || k(C) && k(u).length ? (o(), p("div", Tt, [E("span", null, y(B.value || k(C)), 1), k(C) ? (o(), p("button", {
				key: 0,
				type: "button",
				class: "ac-link",
				onClick: t[8] ||= (...e) => k(s).refresh && k(s).refresh(...e)
			}, "重试")) : x("", !0)])) : x("", !0),
			I(ct, {
				ref_key: "table",
				ref: F,
				items: k(u),
				selected: k(b),
				query: k(c),
				facets: k(d),
				presentation: r.presentation,
				loading: k(S),
				error: k(C),
				"invalid-search": k(T),
				stale: k(M),
				visible: k(w) && z.value,
				"page-selected": k(N),
				"page-indeterminate": k(P),
				"open-filter": R.value,
				"onUpdate:openFilter": t[9] ||= (e) => R.value = e,
				onFilter: J,
				onClearFilter: Y,
				onSelect: k(s).toggle,
				onSelectPage: k(s).togglePage,
				onAction: te,
				onDetail: ne,
				onRetry: k(s).refresh,
				onRendered: t[10] ||= (e) => r.callbacks.afterRender?.(e)
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
			I(W, {
				page: k(h),
				size: k(_),
				pages: k(v),
				total: k(m),
				busy: k(S),
				"page-sizes": [
					10,
					20,
					30,
					50,
					100
				],
				label: "账号列表分页",
				"onUpdate:page": k(s).setPage,
				"onUpdate:size": k(s).setSize
			}, null, 8, [
				"page",
				"size",
				"pages",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		], 512)), [[O, k(w)]]);
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
	let n = N(null), r = N(0), i = A(() => n.value !== null), a = A(() => n.value ? String(n.value.id) : ""), o = null, s = (e) => o === e && r.value === e.generation;
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
		account: b(n),
		generation: b(r),
		isOpen: i,
		accountId: a,
		open: d,
		close: u
	};
}
// src/features/accounts/AccountDetail.vue?vue&type=script&setup=true&lang.ts
var At = ["aria-hidden"], jt = ["data-account-id"], Mt = { class: "account-detail-head" }, Nt = { id: "accountDetailTitle" }, Pt = { id: "accountDetailSubtitle" }, Ft = ["innerHTML"], It = /* @__PURE__ */ c({
	__name: "AccountDetail",
	props: {
		api: {},
		presentation: {},
		callbacks: {}
	},
	setup(n, { expose: r }) {
		let a = n, s = e(), c = !1, l = null;
		function u() {
			let e = l;
			l = null, e?.isConnected && e.focus({ preventScroll: !0 });
		}
		let d = kt(a.api, {
			notify: (e) => a.callbacks.notify(e),
			opened(e) {
				l = null, T(() => {
					!c && d.generation.value === e && d.isOpen.value && (a.callbacks.syncModalScrollLock(), s.value?.focus({ preventScroll: !0 }));
				});
			},
			closed(e, t, n) {
				l = e ? t : null, T(() => {
					c || d.generation.value !== n || d.isOpen.value || (a.callbacks.syncModalScrollLock(), u());
				});
			}
		}), { account: f, accountId: p, isOpen: m } = d, h = A(() => f.value ? f.value.email || `账号 #${f.value.id}` : "账号详情"), b = A(() => f.value ? `账号 #${f.value.id} · ${a.presentation.sourceLabel(f.value.email_source) || "未知来源"}` : ""), x = A(() => f.value ? a.presentation.renderBody(f.value) : "");
		function C(e, t, n, r) {
			let i = typeof document < "u" && document.activeElement instanceof HTMLElement ? document.activeElement : null;
			return d.open(e, t, n, r || i);
		}
		function w(e = !0) {
			d.close(e);
		}
		return t(() => {
			c = !0, d.close();
		}), i(() => {
			a.callbacks.syncModalScrollLock(), u();
		}), r({
			open: C,
			close: w
		}), (e, t) => (o(), S(v, { to: "#accountDetailHost" }, [E("div", {
			id: "accountDetailBackdrop",
			class: _(["account-detail-backdrop", { hidden: !k(m) }]),
			"aria-hidden": !k(m),
			onClick: t[0] ||= g((e) => w(), ["self"])
		}, null, 10, At), E("aside", {
			id: "accountDetailDrawer",
			class: _(["account-detail-drawer", { hidden: !k(m) }]),
			"data-account-id": k(m) ? k(p) : void 0,
			role: "dialog",
			"aria-modal": "true",
			"aria-labelledby": "accountDetailTitle"
		}, [E("div", Mt, [E("div", null, [
			t[2] ||= E("div", { class: "data-panel-kicker" }, "ACCOUNT DETAIL", -1),
			E("h2", Nt, y(h.value), 1),
			E("p", Pt, y(b.value), 1)
		]), E("button", {
			id: "btnCloseAccountDetail",
			ref_key: "closeButton",
			ref: s,
			type: "button",
			class: "account-detail-close",
			"aria-label": "关闭账号详情",
			onClick: t[1] ||= (e) => w()
		}, "×", 512)]), E("div", {
			id: "accountDetailBody",
			class: "account-detail-body",
			innerHTML: x.value
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
function Ut(t) {
	let n = e(!1), r = e(!1), i = e(!1), a = e("0"), o = e(3), s = e(!1), c = e(""), u = e(1), f = e(1), p = e(null), m = N([]), h = N([]), g = e(0), _ = e(0), v = e(!1), y = e(!1), b = e(""), x = e(!1), S = e(!1), C = e(!1), w = null, T = 0, E = 0, D = !1, O, k, j, M = () => typeof document > "u" || !document.hidden, P = A(() => v.value ? `共 ${g.value} 条 · 第 ${u.value} 页` : ""), F = A(() => y.value ? `共 ${_.value} 条 · 第 ${f.value} 页` : "");
	async function I(e, n = {}, r = new AbortController()) {
		let i = setTimeout(() => r.abort(), 3e4);
		try {
			return Vt(await t.request(e, {
				...n,
				signal: r.signal
			}));
		} finally {
			clearTimeout(i);
		}
	}
	function L() {
		for (let e of [t.refreshAccounts, t.refreshSummary]) try {
			Promise.resolve(e()).catch(() => {});
		} catch {}
	}
	function R(e) {
		D || (a.value = e.archived, o.value = Math.min(16, t.operationWorkers()), c.value = "", n.value = !0);
	}
	async function z() {
		let e = Number(o.value);
		if (!(D || s.value || !Number.isInteger(e) || e < 1 || e > 16)) {
			s.value = !0;
			try {
				w ||= t.randomUUID();
				let r = await I("/api/accounts/inspections", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						workers: e,
						archived: a.value,
						idempotency_key: w
					})
				});
				if (w = null, C.value = !0, D) return;
				n.value = !1, t.notify(r.created ? "巡检已加入统一任务队列" : "已有本次巡检记录，已打开历史"), B();
			} catch (e) {
				D || (c.value = `巡检启动请求失败：${Bt(e)}。可查看巡检历史，或使用当前提交再次确认。`);
			} finally {
				s.value = !1;
			}
		}
	}
	function B() {
		D || (u.value = 1, ++T, r.value = !0, H());
	}
	function V(e) {
		x.value || (u.value = Math.max(1, u.value + e), ++T, H());
	}
	async function H() {
		if (D || x.value || !r.value || !M()) return;
		x.value = !0;
		let e = u.value, n = T, i = new AbortController();
		O = i;
		try {
			let t = await I(`/api/accounts/inspections?page=${e}`, {}, i);
			if (D || i.signal.aborted || !r.value || e !== u.value || n !== T) return;
			let a = C.value;
			C.value = !!t.active, a && !C.value && L(), m.value = Ht(t.items), g.value = Number(t.total), v.value = !0;
		} catch (e) {
			!D && r.value && M() && n === T && t.notify(`读取巡检历史失败：${Bt(e)}`);
		} finally {
			x.value = !1, O === i && (O = void 0), n !== T && !D && r.value && M() && H();
		}
	}
	function U(e) {
		D || (p.value = Number(e), f.value = 1, ++E, y.value = !1, b.value = "", h.value = [], i.value = !0, G());
	}
	function W(e) {
		S.value || (f.value = Math.max(1, f.value + e), ++E, G());
	}
	async function G() {
		if (D || S.value || !p.value || !i.value || !M()) return;
		S.value = !0;
		let e = p.value, t = f.value, n = E, r = new AbortController();
		k = r;
		try {
			let a = await I(`/api/accounts/inspections/${e}/failures?page=${t}`, {}, r);
			if (D || r.signal.aborted || !i.value || e !== p.value || t !== f.value || n !== E) return;
			h.value = Ht(a.items), _.value = Number(a.total), y.value = !0, b.value = "";
		} catch (e) {
			!D && i.value && M() && n === E && (b.value = `读取失败：${Bt(e)}，可点击刷新重试。`);
		} finally {
			S.value = !1, k === r && (k = void 0), n !== E && !D && i.value && M() && G();
		}
	}
	async function K(e) {
		if (!D) try {
			if (await I(`/api/accounts/inspections/${Number(e)}/cancel`, { method: "POST" }), D) return;
			t.notify("已请求停止，将在安全检查点结束"), H();
		} catch (e) {
			D || t.notify(`停止巡检失败：${Bt(e)}`);
		}
	}
	function q(e) {
		e && e !== "start" || (n.value = !1), e && e !== "history" || (r.value = !1, ++T, O?.abort()), e && e !== "failures" || (i.value = !1, ++E, k?.abort());
	}
	function J() {
		j !== void 0 && (clearInterval(j), j = void 0), !D && M() && (r.value || i.value) && (j = setInterval(() => {
			r.value && H(), i.value && G();
		}, 5e3));
	}
	function Y() {
		M() || (++T, ++E, O?.abort(), k?.abort()), J();
	}
	return l([r, i], J, { flush: "sync" }), typeof document < "u" && document.addEventListener("visibilitychange", Y), d(() => {
		D = !0, q(), J(), typeof document < "u" && document.removeEventListener("visibilitychange", Y);
	}), {
		startOpen: n,
		historyOpen: r,
		failuresOpen: i,
		archived: a,
		workers: o,
		starting: s,
		startError: c,
		historyPage: u,
		failurePage: f,
		failureId: p,
		historyRows: m,
		failureRows: h,
		historyTotal: g,
		failureTotal: _,
		historyReady: v,
		failureReady: y,
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
}, mn = { class: "data-table" }, hn = { class: "inspection-error-reason" }, gn = { key: 2 }, _n = { class: "jobs-v2-pager" }, vn = ["disabled"], yn = { id: "accountInspectionFailuresPageLabel" }, bn = ["disabled"], xn = /*#__PURE__*/ M(/* @__PURE__ */ c({
	__name: "Inspection",
	props: { deps: {} },
	setup(i, { expose: a }) {
		let s = i, c = Ut(s.deps), { startOpen: u, historyOpen: d, failuresOpen: _, archived: v, workers: b, starting: S, startError: C, historyPage: w, failurePage: D, failureId: O, historyRows: A, failureRows: j, historyTotal: M, failureTotal: N, historyReady: F, failureReady: I, failureError: L, historyLabel: R, failureLabel: z } = c, B = e(), V = e(), H = e(), U = e(), W = e(), G = /* @__PURE__ */ new Map(), K = {
			start: 0,
			history: 0,
			failures: 0
		}, q = {
			start: B,
			history: V,
			failures: H
		}, J = {
			start: u,
			history: d,
			failures: _
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
			let n = V.value?.open ? V.value.querySelector("button:not([disabled])") : s.deps.fallbackFocus?.();
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
			await T();
			let t = q[e].value, n = J[e].value;
			t && !Y && (n && !t.open ? (G.has(e) || G.set(e, document.activeElement instanceof HTMLElement ? document.activeElement : null), t.showModal()) : !n && t.open && ae(e));
		}
		for (let e of [
			"start",
			"history",
			"failures"
		]) l(J[e], () => oe(e), { flush: "post" });
		l(w, () => {
			if (U.value) {
				U.value.scrollTop = 0;
				let e = U.value.querySelector("[data-inspection-scroll]");
				e && (e.scrollLeft = 0);
			}
		}), l([D, O], () => {
			if (W.value) {
				W.value.scrollTop = 0;
				let e = W.value.querySelector("[data-inspection-scroll]");
				e && (e.scrollLeft = 0);
			}
		});
		function se(e) {
			Z("history"), s.deps.openTask(Number(e.task_id));
		}
		function ce(e) {
			return Number(e.live_failed_count || 0) + Number(e.deactivated_skipped_count || 0);
		}
		return t(() => {
			Y = !0;
			for (let e of Object.values(q)) e.value?.open && e.value.close();
			G.clear();
		}), a({
			openStart: te,
			openHistory: ne,
			openFailures: re,
			close: Z,
			refreshHistory: c.refreshHistory,
			refreshFailures: c.refreshFailures,
			changeHistoryPage: c.changeHistoryPage,
			changeFailuresPage: c.changeFailuresPage,
			stop: c.stop
		}), (e, t) => (o(), p(P, null, [
			E("dialog", {
				ref_key: "start",
				ref: B,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionStart",
				"aria-labelledby": "accountInspectionStartTitle",
				"data-archived": k(v),
				onClose: t[3] ||= (e) => X("start")
			}, [E("div", Gt, [t[14] ||= E("h2", { id: "accountInspectionStartTitle" }, "启动账号巡检", -1), E("button", {
				type: "button",
				class: "jobs-tb-btn",
				"aria-label": "关闭启动巡检",
				onClick: t[0] ||= (e) => Z("start")
			}, "关闭")]), E("form", { onSubmit: t[2] ||= g((...e) => k(c).submit && k(c).submit(...e), ["prevent"]) }, [
				E("p", Kt, "本次范围：" + y(k(Lt)(k(v))), 1),
				t[15] ||= E("p", null, "该归档范围内全部账号，不限当前页，不受勾选、搜索或其他筛选条件影响。", -1),
				t[16] ||= E("p", null, "已废账号跳过；AT 本地有效则结束；失效时自动刷新，再复用登录会话查套餐。", -1),
				t[17] ||= E("label", { for: "accountInspectionWorkers" }, "并发账号数", -1),
				n(E("input", {
					id: "accountInspectionWorkers",
					"onUpdate:modelValue": t[1] ||= (e) => f(b) ? b.value = e : null,
					type: "number",
					min: "1",
					max: "16",
					step: "1",
					required: ""
				}, null, 512), [[m, k(b)]]),
				t[18] ||= E("p", null, "支持 1–16；实际并发同时受共享账号操作预算限制。", -1),
				E("p", qt, y(k(C)), 1),
				E("button", {
					type: "submit",
					class: "jobs-tb-btn jobs-tb-btn--primary",
					id: "btnConfirmAccountInspection",
					disabled: k(S)
				}, "开始巡检", 8, Jt)
			], 32)], 40, Wt),
			E("dialog", {
				ref_key: "history",
				ref: V,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionHistory",
				"aria-labelledby": "accountInspectionHistoryTitle",
				onClose: t[8] ||= (e) => X("history")
			}, [
				E("div", Yt, [
					t[19] ||= E("h2", { id: "accountInspectionHistoryTitle" }, "账号巡检历史", -1),
					E("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: t[4] ||= (...e) => k(c).refreshHistory && k(c).refreshHistory(...e)
					}, "刷新"),
					E("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: t[5] ||= (e) => Z("history")
					}, "关闭")
				]),
				t[20] ||= E("p", null, "每 5 秒刷新。进度包含跳过；完成表示本轮处理结束，查活和套餐结果分别统计。", -1),
				E("div", {
					ref_key: "historyContent",
					ref: U,
					id: "accountInspectionHistoryContent",
					"aria-live": "polite"
				}, [k(A).length ? (o(), p("div", Xt, [E("table", Zt, [E("thead", null, [E("tr", null, [(o(), p(P, null, r([
					"任务",
					"范围",
					"状态 / 时间",
					"并发",
					"进度",
					"AT失效",
					"查活 成功/失败",
					"套餐 成功/失败",
					"操作"
				], (e) => E("th", {
					key: e,
					scope: "col"
				}, y(e), 1)), 64))])]), E("tbody", null, [(o(!0), p(P, null, r(k(A), (e, t) => (o(), p("tr", { key: String(e.id ?? t) }, [
					E("td", null, [E("button", {
						type: "button",
						class: "jobs-tb-btn",
						"data-inspection-task": Number(e.id),
						onClick: (t) => se(e)
					}, "#" + y(Number(e.id)), 9, Qt)]),
					E("td", null, y(k(Lt)(String(e.archived))), 1),
					E("td", null, [h(y(k(Rt)(e.status)), 1), E("div", $t, y(i.deps.formatDateTime(e.created_at)), 1)]),
					E("td", null, y(Number(e.workers)), 1),
					E("td", null, [h(y(Number(e.checked_count) + Number(e.skipped_count)) + " / " + y(Number(e.total_count)), 1), E("div", en, "跳过 " + y(Number(e.skipped_count)) + "（已废 " + y(Number(e.deactivated_skipped_count)) + "）", 1)]),
					E("td", null, y(Number(e.invalid_count)), 1),
					E("td", null, [h(y(Number(e.live_success_count)) + " / " + y(Number(e.live_failed_count)), 1), ce(e) ? (o(), p("div", tn, [E("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: (t) => re(Number(e.id), t.currentTarget)
					}, "失败详情 " + y(ce(e)), 9, nn)])) : x("", !0)]),
					E("td", null, y(Number(e.plan_success_count)) + " / " + y(Number(e.plan_failed_count)), 1),
					E("td", null, [e.status === "running" ? (o(), p("button", {
						key: 0,
						type: "button",
						class: "jobs-tb-btn",
						onClick: (t) => k(c).stop(Number(e.id))
					}, "停止", 8, rn)) : x("", !0)])
				]))), 128))])])])) : (o(), p("p", an, y(k(F) ? "暂无巡检记录。" : "正在读取巡检历史…"), 1))], 512),
				E("div", on, [
					E("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionPrev",
						disabled: k(w) <= 1,
						onClick: t[6] ||= (e) => k(c).changeHistoryPage(-1)
					}, "上一页", 8, sn),
					E("span", cn, y(k(R)), 1),
					E("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionNext",
						disabled: k(w) * 20 >= k(M),
						onClick: t[7] ||= (e) => k(c).changeHistoryPage(1)
					}, "下一页", 8, ln)
				])
			], 544),
			E("dialog", {
				ref_key: "failures",
				ref: H,
				class: "proxy-traffic-detail-dialog ac-inspection",
				id: "accountInspectionFailures",
				"aria-labelledby": "accountInspectionFailuresTitle",
				onClose: t[13] ||= (e) => X("failures")
			}, [
				E("div", un, [
					E("h2", dn, y(k(O) ? `巡检 #${k(O)} · 失败详情` : "巡检失败详情"), 1),
					E("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: t[9] ||= (...e) => k(c).refreshFailures && k(c).refreshFailures(...e)
					}, "刷新"),
					E("button", {
						type: "button",
						class: "jobs-tb-btn",
						onClick: t[10] ||= (e) => Z("failures")
					}, "关闭")
				]),
				t[21] ||= E("p", null, "保留本轮原始执行快照，后续重跑或删除账号不会改写；含已废跳过，套餐单独失败不计为查活失败。", -1),
				E("div", {
					ref_key: "failureContent",
					ref: W,
					id: "accountInspectionFailuresContent",
					"aria-live": "polite"
				}, [k(L) ? (o(), p("p", fn, y(k(L)), 1)) : k(j).length ? (o(), p("div", pn, [E("table", mn, [E("thead", null, [E("tr", null, [(o(), p(P, null, r([
					"账号",
					"邮箱",
					"类型",
					"时间",
					"原因"
				], (e) => E("th", {
					key: e,
					scope: "col"
				}, y(e), 1)), 64))])]), E("tbody", null, [(o(!0), p(P, null, r(k(j), (e, t) => (o(), p("tr", { key: String(e.account_id ?? t) }, [
					E("td", null, "#" + y(Number(e.account_id)), 1),
					E("td", null, y(e.email), 1),
					E("td", null, y(k(zt)(e.status)), 1),
					E("td", null, y(i.deps.formatDateTime(e.failed_at)), 1),
					E("td", hn, y(e.error), 1)
				]))), 128))])])])) : (o(), p("p", gn, y(k(I) ? "本轮暂无查活失败或已废跳过。" : "正在读取本次失败记录…"), 1))], 512),
				E("div", _n, [
					E("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresPrev",
						disabled: !k(I) || k(D) <= 1,
						onClick: t[11] ||= (e) => k(c).changeFailuresPage(-1)
					}, "上一页", 8, vn),
					E("span", yn, y(k(z)), 1),
					E("button", {
						type: "button",
						class: "jobs-tb-btn",
						id: "accountInspectionFailuresNext",
						disabled: !k(I) || k(D) * 20 >= k(N),
						onClick: t[12] ||= (e) => k(c).changeFailuresPage(1)
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
function Dn(t, n = {}) {
	let r = e(!1), i = e(0), a = e("single"), o = N(null), s = N(null), c = N([]), l = N([]), u = e(""), f = e("idle"), p = e(""), m = e(!1), h = A(() => f.value !== "ready" || !l.value.some((e) => e.enabled)), g = null, _ = !1, v = (e) => !_ && g === e && i.value === e.generation && r.value;
	function y({ restoreFocus: e = !0 } = {}) {
		let t = g;
		t && (g = null, ++i.value, t.controller.abort(), r.value = !1, o.value = null, s.value = null, c.value = [], l.value = [], u.value = "", f.value = "idle", p.value = "", m.value = !1, n.closed?.(e, t.trigger, i.value));
	}
	async function b(e, r) {
		try {
			let n = wn(await t.request("/api/email-sources", { signal: e.controller.signal }));
			if (!v(e)) return;
			l.value = Cn((Array.isArray(n.sources) ? n.sources : []).map((e) => {
				let t = wn(e);
				return {
					value: String(t.value || ""),
					label: String(t.label || t.value || ""),
					enabled: !!t.enabled,
					reason: String(t.reason || "")
				};
			}));
			let i = l.value.filter((e) => e.enabled);
			u.value = (i.find((e) => e.value === r) || i[0])?.value || "", f.value = "ready", p.value = i.length ? "" : "没有已配置且可用的新邮箱来源";
		} catch (t) {
			if (!v(e)) return;
			f.value = "failed", l.value = [], u.value = "", p.value = `邮箱来源读取失败：${Tn(t)}`;
		}
		v(e) && n.sourcesReady?.(e.generation);
	}
	function x(e, t, d, h, v) {
		if (_) return !1;
		let x = Cn(Sn({
			...h,
			accountIds: t
		}));
		y({ restoreFocus: !1 });
		let S = {
			generation: ++i.value,
			mode: e,
			account: d,
			accountIds: Cn([...t]),
			context: x,
			trigger: v,
			controller: new AbortController(),
			submitting: !1
		};
		return g = S, a.value = e, o.value = d, c.value = S.accountIds, s.value = x, r.value = !0, f.value = "loading", u.value = "", p.value = "", l.value = [], m.value = !1, n.opened?.(S.generation), b(S, String(d?.email_source || "").trim().toLowerCase()), !0;
	}
	function S(e, n, r = null) {
		let i = Number(e), a = String(i), o = n?.rowHints?.find((e) => String(e.id) === a);
		return !Number.isSafeInteger(i) || i <= 0 || !En(n).includes(a) || !o ? (t.notify("账号详情暂不可用，请先刷新列表"), !1) : x("single", [a], Cn({
			id: i,
			email: String(o.email || ""),
			email_source: String(o.email_source || "")
		}), n, r);
	}
	function C(e, n = null) {
		let r = En(e);
		return r.length ? r.length > 500 ? (t.notify("单次最多换绑 500 个账号"), !1) : x("bulk", r, null, e, n) : (t.notify("请先选择账号"), !1);
	}
	function w(e, n) {
		try {
			Promise.resolve(e()).catch((e) => t.notify(n + Tn(e)));
		} catch (e) {
			t.notify(n + Tn(e));
		}
	}
	async function T() {
		let e = g;
		if (!e || !v(e) || e.submitting) return;
		let n = u.value;
		if (f.value !== "ready" || !n || !l.value.some((e) => e.value === n && e.enabled)) {
			p.value = "请选择新邮箱来源";
			return;
		}
		p.value = "", m.value = !0, e.submitting = !0;
		let r;
		try {
			r = wn(await t.request(e.mode === "bulk" ? "/api/accounts/email-change-bulk" : `/api/accounts/${e.account.id}/email-change`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(e.mode === "bulk" ? {
					account_ids: e.accountIds.map(Number),
					email_source: n
				} : { email_source: n })
			}));
		} catch (n) {
			v(e) && (p.value = `提交失败：${Tn(n)}`), t.notify("换绑邮箱失败: " + Tn(n));
			return;
		} finally {
			e.submitting = !1, v(e) && (m.value = !1);
		}
		let i = v(e), a = Cn({
			result: Sn(r),
			context: e.context,
			mode: e.mode,
			accountIds: e.accountIds,
			accountId: e.account?.id || null,
			oldEmail: e.account?.email || "",
			emailSource: n,
			stale: !i
		});
		if (e.mode === "bulk") {
			let e = Number(r.started_count || 0), n = Number(r.skipped_count || 0);
			t.notify(`批量换绑已入队 ${e} 个${n ? `，跳过 ${n} 个` : ""}`);
		} else t.notify(String(r.message || `邮箱换绑已入队 · 任务 #${r.task_id || "-"}`));
		i && y({ restoreFocus: !1 }), w(() => t.recordReceipt(a), "换绑已受理，记录回执失败："), w(() => t.refreshAccounts(e.context), "换绑已受理，刷新账号失败："), i && !_ && !g && w(() => t.openTasks({
			target: e.mode === "bulk" ? "" : e.account.email || `#${e.account.id}`,
			type: "email_change"
		}), "换绑已受理，打开任务失败：");
	}
	return d(() => {
		_ = !0, y();
	}), {
		isOpen: r,
		generation: i,
		mode: a,
		account: o,
		context: s,
		accountIds: c,
		sources: l,
		source: u,
		sourceStatus: f,
		sourceDisabled: h,
		error: p,
		submitting: m,
		openSingle: S,
		openBulk: C,
		close: y,
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
], Ln = ["hidden"], Rn = { class: "email-change-foot" }, zn = ["disabled"], Bn = /* @__PURE__ */ c({
	__name: "EmailChange",
	props: { deps: {} },
	setup(a, { expose: s }) {
		let c = a, l = e(), u = e(), d = e(), m = !1, h = null;
		function b() {
			let e = h;
			h = null, e?.isConnected && e.focus({ preventScroll: !0 });
		}
		let x = Dn(c.deps, {
			opened(e) {
				h = null, T(() => {
					!m && x.generation.value === e && x.isOpen.value && (u.value?.setCustomValidity(""), c.deps.syncModalScrollLock(), d.value?.focus({ preventScroll: !0 }));
				});
			},
			sourcesReady(e) {
				T(() => {
					!m && x.generation.value === e && x.isOpen.value && u.value?.focus({ preventScroll: !0 });
				});
			},
			closed(e, t, n) {
				h = e ? t : null, T(() => {
					m || x.generation.value !== n || x.isOpen.value || (c.deps.syncModalScrollLock(), b());
				});
			}
		}), { isOpen: w, account: D, accountIds: O, mode: j, sources: M, source: N, sourceStatus: F, sourceDisabled: I, error: L, submitting: R } = x, z = A(() => w.value && j.value === "bulk" ? "批量换绑邮箱" : "换绑邮箱"), B = A(() => w.value ? j.value === "bulk" ? `已选 ${O.value.length} 个账号 · 将按账号分别领取新邮箱` : `账号 #${D.value?.id} · 当前邮箱 ${D.value?.email || "-"}` : ""), V = A(() => F.value === "loading" ? "正在读取邮箱来源…" : F.value === "failed" ? "邮箱来源读取失败" : F.value === "ready" ? "请选择邮箱来源" : "打开弹窗后读取可用来源");
		function H(e) {
			return e || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
		}
		function U(e, t, n = null) {
			return x.openSingle(e, t, H(n));
		}
		function W(e, t = null) {
			return x.openBulk(e, H(t));
		}
		function G(e = {}) {
			x.close(e);
		}
		async function K() {
			u.value?.setCustomValidity(""), !u.value?.checkValidity() || !N.value || I.value ? (u.value?.setCustomValidity("请选择新邮箱来源"), x.error.value = "请选择新邮箱来源", u.value?.reportValidity(), u.value?.focus()) : await x.submit();
		}
		function q(e) {
			if (!w.value) return;
			if (e.key === "Escape") {
				e.preventDefault(), G();
				return;
			}
			if (e.key !== "Tab") return;
			let t = Array.from(l.value?.querySelectorAll("button, select, [href], [tabindex]:not([tabindex=\"-1\"])") || []).filter((e) => !("disabled" in e && e.disabled) && !e.hidden), n = t[0], r = t.at(-1);
			e.shiftKey && document.activeElement === n ? (e.preventDefault(), r?.focus()) : !e.shiftKey && document.activeElement === r && (e.preventDefault(), n?.focus());
		}
		return document.addEventListener("keydown", q), t(() => {
			m = !0, document.removeEventListener("keydown", q), x.close();
		}), i(() => {
			c.deps.syncModalScrollLock(), b();
		}), s({
			openSingle: U,
			openBulk: W,
			close: G
		}), (e, t) => (o(), S(v, { to: "#accountEmailChangeHost" }, [E("div", {
			ref_key: "modal",
			ref: l,
			id: "emailChangeModal",
			class: _(["email-change-modal", { hidden: !k(w) }]),
			role: "dialog",
			"aria-modal": "true",
			"aria-hidden": !k(w),
			"aria-labelledby": "emailChangeTitle",
			"aria-describedby": "emailChangeNote",
			"data-account-id": k(w) && k(j) === "single" ? String(k(D)?.id) : "",
			"data-account-ids": k(w) && k(j) === "bulk" ? JSON.stringify(k(O).map(Number)) : "",
			onClick: t[3] ||= g((e) => G(), ["self"])
		}, [E("div", kn, [E("div", An, [E("div", null, [
			t[4] ||= E("div", { class: "data-panel-kicker" }, "PROTOCOL OPERATION", -1),
			E("h2", jn, y(z.value), 1),
			E("p", Mn, y(B.value), 1)
		]), E("button", {
			ref_key: "closeButton",
			ref: d,
			id: "btnCloseEmailChange",
			type: "button",
			class: "account-detail-close",
			"aria-label": "关闭换绑邮箱",
			onClick: t[0] ||= (e) => G()
		}, "×", 512)]), E("form", {
			id: "emailChangeForm",
			class: "email-change-form",
			novalidate: "",
			onSubmit: g(K, ["prevent"])
		}, [
			E("label", Nn, [
				t[5] ||= E("span", null, "新邮箱来源", -1),
				n(E("select", {
					ref_key: "select",
					ref: u,
					id: "emailChangeSource",
					"onUpdate:modelValue": t[1] ||= (e) => f(N) ? N.value = e : null,
					name: "email_source",
					required: "",
					disabled: k(I),
					"aria-describedby": "emailChangeSourceHelp emailChangeSourceError"
				}, [E("option", Fn, y(V.value), 1), (o(!0), p(P, null, r(k(M), (e, t) => (o(), p("option", {
					key: `${e.value}:${t}`,
					value: e.value,
					disabled: !e.enabled,
					title: e.reason,
					"data-reason": e.reason
				}, y(e.label) + y(e.enabled ? "" : "（不可用）"), 9, In))), 128))], 8, Pn), [[C, k(N)]]),
				t[6] ||= E("small", { id: "emailChangeSourceHelp" }, "系统会从所选邮箱池自动领取新地址，并读取新邮箱验证码。", -1),
				E("small", {
					id: "emailChangeSourceError",
					class: "email-change-error",
					role: "alert",
					hidden: !k(L)
				}, y(k(L)), 9, Ln)
			]),
			t[7] ||= E("div", {
				id: "emailChangeNote",
				class: "email-change-note"
			}, "换绑、Recent Login 和验证码校验全部走协议任务，不会启动浏览器。成功写回后会自动创建一次协议查活任务刷新 AT。", -1),
			E("div", Rn, [E("button", {
				id: "btnCancelEmailChange",
				type: "button",
				class: "jobs-tb-btn",
				onClick: t[2] ||= (e) => G()
			}, "取消"), E("button", {
				id: "btnSubmitEmailChange",
				type: "submit",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				disabled: k(R)
			}, y(k(R) ? "提交中…" : "开始换绑"), 9, zn)])
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
function Kn(t, n = {}) {
	let r = e(!1), i = e(!1), a = e(""), o = N([]), s = N(null), c = null, l = null, u = !1, f = A(() => s.value ? Gn(s.value) : []), p = A(() => f.value.filter((e) => Number(e.item.task_id) > 0)), m = A(() => {
		let e = s.value;
		return e ? `C2A 重新导入：已入队 ${Number(e.queued_count ?? (Array.isArray(e.queued) ? e.queued.length : 0))} 个，未入队 ${Number(e.skipped_count ?? (Array.isArray(e.skipped) ? e.skipped.length : 0)) + Number(e.failed_count ?? (Array.isArray(e.failed) ? e.failed.length : 0))} 个` : "";
	});
	function h(e, n = null) {
		if (u) return !1;
		if (r.value) return t.notify("C2A 同步确认窗口不可用，请刷新页面后重试"), !1;
		let s = e.accountIds.map((e) => {
			if (!/^[1-9]\d*$/.test(e) || !Number.isSafeInteger(Number(e))) throw Error("账号 ID 无效");
			return Number(e);
		});
		return s.length ? (c = Un(e), o.value = Object.freeze([...s]), l = n, i.value = !1, a.value = "", r.value = !0, !0) : (t.notify("请先选择账号"), !1);
	}
	function g(e = "cancel", t = !1) {
		if (!r.value || i.value && !t) return !1;
		let a = l;
		return r.value = !1, o.value = [], c = null, l = null, n.closed?.(a, e), !0;
	}
	async function _(e, n) {
		try {
			await e();
		} catch (e) {
			t.notify(n + Wn(e));
		}
	}
	function v(e) {
		s.value = Un(Vn(e));
	}
	function y(e = p.value.map((e) => e.item)) {
		let n = e.length === 1 ? e[0] : null;
		return _(() => t.openTasks({
			filters: { type: "c2a_session_reimport" },
			taskId: Number(n?.task_id) || void 0,
			runId: Number(n?.run_id) || null
		}), "C2A 请求已处理，打开任务失败: ");
	}
	async function b() {
		if (u || !r.value || !c || !o.value.length || i.value) return;
		let e = [...o.value], n = c, s = l;
		i.value = !0, a.value = "正在创建 C2A 同步任务…";
		let d = t.beginBusy?.(s, "提交导入…"), f;
		try {
			f = Vn(await t.request("/api/accounts/c2a/sync-bulk", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ account_ids: e })
			}));
		} catch (e) {
			t.notify("重新导入 C2A 失败: " + Wn(e)), u || (a.value = `提交失败：${Wn(e)}。请检查后再次提交。`), i.value = !1, d?.(), t.selectionChanged?.(n);
			return;
		}
		try {
			u || v(f);
			let e = Number(f.skipped_count || 0) + Number(f.failed_count || 0), r = Array.isArray(f.queued) ? f.queued : [];
			if (f.accepted) {
				t.notify(`C2A 重新导入已入队 ${f.queued_count || 0} 个${e ? `，未入队 ${e} 个（已显示具体原因）` : ""}${r.length ? "，最终结果在任务回执中更新" : ""}`);
				let n = Gn(f).filter((e) => Number(e.item.task_id) > 0).map((e) => e.item);
				n.length && await _(() => t.trackAccepted(n, "重新导入 C2A", { navigate: !1 }), "C2A 请求已处理，回执更新失败: ");
			} else t.notify(e ? `C2A 已重新导入 ${f.updated_count || 0} 个，跳过/失败 ${e} 个` : `C2A 已重新导入 ${f.updated_count || 0} 个`), await _(() => t.refreshAccounts(n), "C2A 请求已处理，页面更新失败: ");
		} catch (e) {
			t.notify("C2A 请求已处理，回执更新失败: " + Wn(e));
		} finally {
			i.value = !1;
			try {
				d?.();
			} finally {
				u || g("submitted", !0);
			}
		}
	}
	return d(() => {
		u = !0, g("cancel", !0);
	}), {
		isOpen: r,
		submitting: i,
		status: a,
		accountIds: o,
		result: s,
		receiptEntries: f,
		taskEntries: p,
		summary: m,
		open: h,
		close: g,
		submit: b,
		showResult: v,
		openTasks: y
	};
}
// src/features/accounts/C2aReimport.vue?vue&type=script&setup=true&lang.ts
var qn = { class: "c2a-reimport-confirm-head" }, Jn = ["disabled"], Yn = { class: "c2a-reimport-confirm-body" }, Xn = { class: "c2a-reimport-confirm-scope" }, Zn = { id: "c2aReimportConfirmCountV2" }, Qn = ["hidden"], $n = { class: "c2a-reimport-confirm-foot" }, er = ["disabled"], tr = ["disabled"], nr = ["hidden"], rr = { class: "column-filter-summary-label" }, ir = ["open"], ar = ["data-c2a-reimport-task", "onClick"], or = /* @__PURE__ */ c({
	__name: "C2aReimport",
	props: { deps: {} },
	setup(n, { expose: i }) {
		let a = n, s = e(), c = !1, l = 0, u = 0, d;
		function f(e, t) {
			!c && e?.isConnected && typeof e.focus == "function" && (e.focus({ preventScroll: !0 }), d = requestAnimationFrame(() => {
				if (d = void 0, c || u !== t || m.isOpen.value) return;
				let n = e.closest("#accountsMoreActionsV2"), r = n?.open === !1 ? n.querySelector("summary") : e;
				r?.isConnected && r.focus({ preventScroll: !0 });
			}));
		}
		let m = Kn({
			...a.deps,
			beginBusy: (e, t) => {
				if (a.deps.beginBusy) return a.deps.beginBusy(e, t);
				let n = e instanceof HTMLButtonElement ? e : null, r = n?.textContent || "";
				return n && (n.disabled = !0, n.textContent = t), () => {
					n && (n.textContent = r, n.disabled = !1);
				};
			}
		}, { closed: (e, t) => {
			s.value?.open && (++l, s.value.close(t)), f(e, u);
		} }), { isOpen: g, submitting: _, status: b, accountIds: C, result: w, receiptEntries: D, taskEntries: O, summary: A } = m;
		function j(e, t = null) {
			return !s.value || typeof s.value.showModal != "function" ? (a.deps.notify("C2A 同步确认窗口不可用，请刷新页面后重试"), !1) : m.open(e, t) ? (++u, d !== void 0 && (cancelAnimationFrame(d), d = void 0), T(() => {
				!c && g.value && !s.value?.open && s.value?.showModal();
			}), !0) : !1;
		}
		function M(e = "cancel", t = {}) {
			return m.close(e, t.force);
		}
		function N() {
			l ? --l : s.value?.open || m.close(s.value?.returnValue || "cancel", !0);
		}
		function F(e) {
			_.value && e.preventDefault();
		}
		function I(e, t) {
			let n = Number(e.item.id);
			return Number.isInteger(n) && n > 0 ? `账号 #${n}` : `提交项 #${Number(e.item.input_index) || t + 1}`;
		}
		function L(e) {
			return [
				e.item.email,
				e.item.error_code,
				e.item.reason || e.item.error
			].filter(Boolean).map(String).join(" · ");
		}
		return t(() => {
			c = !0, ++u, d !== void 0 && cancelAnimationFrame(d), m.close("cancel", !0);
		}), i({
			open: j,
			close: M,
			submit: m.submit,
			showResult: m.showResult,
			openTasks: m.openTasks,
			isSubmitting: _
		}), (e, t) => (o(), p(P, null, [(o(), S(v, { to: "#accountC2aConfirmHost" }, [E("dialog", {
			ref_key: "dialog",
			ref: s,
			onClose: N,
			onCancel: F,
			id: "c2aReimportConfirmModal",
			"aria-labelledby": "c2aReimportConfirmTitle",
			"aria-describedby": "c2aReimportConfirmDescription"
		}, [
			E("div", qn, [t[4] ||= E("div", null, [
				E("p", { class: "c2a-reimport-confirm-kicker" }, "本地 AT · 远端账号更新"),
				E("h3", { id: "c2aReimportConfirmTitle" }, "批量同步到 C2A"),
				E("p", { id: "c2aReimportConfirmDescription" }, "只把本地当前 AT 更新到同邮箱唯一匹配的既有 C2A 账号。")
			], -1), E("button", {
				type: "button",
				class: "c2a-reimport-confirm-close",
				id: "btnCloseC2aReimportV2",
				disabled: k(_),
				onClick: t[0] ||= (e) => M(),
				"aria-label": "关闭 C2A 同步确认窗口"
			}, "×", 8, Jn)]),
			E("div", Yn, [
				E("p", Xn, [
					t[5] ||= h("将为 ", -1),
					E("strong", Zn, y(k(C).length), 1),
					t[6] ||= h(" 个已选账号创建同步任务。", -1)
				]),
				t[7] ||= E("section", {
					class: "c2a-reimport-confirm-note",
					"aria-labelledby": "c2aReimportConfirmScopeTitle"
				}, [E("h4", { id: "c2aReimportConfirmScopeTitle" }, "更新范围"), E("ul", null, [E("li", null, "任务执行时读取本地保存的当前 AT；不会刷新本地 AT，也不会重新登录。"), E("li", null, "只按完整邮箱唯一匹配既有 C2A 账号，并更新该账号的 AT；不会创建、删除、分组、代理、启用或更新 refresh_token。")])], -1),
				t[8] ||= E("section", {
					class: "c2a-reimport-confirm-note",
					"aria-labelledby": "c2aReimportConfirmSafetyTitle"
				}, [E("h4", { id: "c2aReimportConfirmSafetyTitle" }, "提交安全条件"), E("p", null, "任务写入前会确认 C2A 的“自动移除异常账号”和“自动移除限流账号”都已关闭；无法确认或任一开关开启时，不会发送更新。执行期间请保持两个开关关闭。")], -1),
				t[9] ||= E("section", {
					class: "c2a-reimport-confirm-note c2a-reimport-confirm-note--warning",
					"aria-labelledby": "c2aReimportConfirmSideEffectTitle"
				}, [E("h4", { id: "c2aReimportConfirmSideEffectTitle" }, "C2A 端状态可能变化"), E("p", null, "当前 C2A 通用更新接口会按自身规则清除凭据错误。AT 更新确认后，异常账号可能恢复正常；最终以 C2A 状态和任务回执为准。")], -1),
				E("p", {
					class: "c2a-reimport-confirm-status",
					id: "c2aReimportConfirmStatusV2",
					role: "status",
					"aria-live": "polite",
					"aria-atomic": "true",
					hidden: !k(b)
				}, y(k(b)), 9, Qn)
			]),
			E("div", $n, [E("button", {
				type: "button",
				class: "jobs-tb-btn",
				id: "btnCancelC2aReimportV2",
				disabled: k(_),
				onClick: t[1] ||= (e) => M()
			}, "取消", 8, er), E("button", {
				type: "button",
				class: "jobs-tb-btn jobs-tb-btn--primary",
				id: "btnConfirmC2aReimportV2",
				disabled: k(_),
				onClick: t[2] ||= (...e) => k(m).submit && k(m).submit(...e)
			}, y(k(_) ? "正在提交…" : "提交并入队"), 9, tr)])
		], 544)])), (o(), S(v, { to: "#accountC2aReceiptHost" }, [E("div", {
			class: "column-filter-summary account-search-summary",
			id: "accountC2aReimportResultV2",
			role: "status",
			"aria-live": "polite",
			hidden: !k(w)
		}, [
			E("span", rr, y(k(A)), 1),
			k(O).length ? (o(), p("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-c2a-reimport-tasks": "",
				onClick: t[3] ||= (e) => k(m).openTasks()
			}, "打开任务中心")) : x("", !0),
			k(D).length ? (o(), p("details", {
				key: k(A),
				open: k(D).some((e) => e.state !== "已入队")
			}, [E("summary", null, "查看" + y(k(D).some((e) => e.state !== "已入队") ? "任务与未入队原因" : "任务"), 1), E("ul", null, [(o(!0), p(P, null, r(k(D), (e, t) => (o(), p("li", { key: t }, [h(y(I(e, t)) + " · " + y(e.state) + y(L(e) ? ` · ${L(e)}` : ""), 1), Number(e.item.task_id) > 0 ? (o(), p("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-c2a-reimport-task": k(O).indexOf(e),
				onClick: (t) => k(m).openTasks([e.item])
			}, "查看任务 #" + y(Number(e.item.task_id)), 9, ar)) : x("", !0)]))), 128))])], 8, ir)) : x("", !0)
		], 8, nr)]))], 64));
	}
}), sr = ["hidden"], cr = { class: "column-filter-summary-label" }, lr = [
	"data-registration-retry-result",
	"data-registration-retry-task-id",
	"data-registration-retry-run-id",
	"onClick"
], ur = /* @__PURE__ */ c({
	__name: "RegistrationRetryReceipt",
	props: { notify: { type: Function } },
	setup(n, { expose: i }) {
		let a = n, s = N(null), c = e(0), l = !1;
		function u(e) {
			return Array.isArray(e) ? Object.freeze(e.map(u)) : e && typeof e == "object" ? Object.freeze(Object.fromEntries(Object.entries(e).map(([e, t]) => [e, u(t)]))) : e;
		}
		let d = A(() => Array.isArray(s.value?.result.started) ? s.value.result.started : []), f = A(() => Array.isArray(s.value?.result.reused) ? s.value.result.reused : []), m = A(() => Array.isArray(s.value?.result.skipped) ? s.value.result.skipped : []), g = A(() => [...d.value, ...f.value]), _ = A(() => {
			let e = s.value?.result;
			return `注册重跑：已创建 ${Number(e?.started_count ?? d.value.length)} 个，进行中 ${Number(e?.reused_count ?? f.value.length)} 个，跳过 ${Number(e?.skipped_count ?? m.value.length)} 个`;
		}), b = (e) => e.task_id || e.operation_task_id, C = (e) => b(e) || e.job_id;
		function w(e, t, n) {
			l || (s.value = {
				result: u(e),
				context: u(t),
				open: n
			}, ++c.value);
		}
		async function T(e = g.value) {
			if (l || !s.value) return;
			let t = s.value.open;
			try {
				await t(u(e));
			} catch (e) {
				l || a.notify?.("注册重跑请求已处理，打开任务失败: " + (e instanceof Error ? e.message : "请求失败"));
			}
		}
		return t(() => {
			l = !0, s.value = null;
		}), i({
			showResult: w,
			openTasks: T
		}), (e, t) => (o(), S(v, { to: "#accountRegistrationReceiptHost" }, [E("div", {
			id: "accountRegistrationRetryResultV2",
			class: "column-filter-summary account-search-summary",
			role: "status",
			"aria-live": "polite",
			hidden: !s.value
		}, [
			E("span", cr, y(s.value ? _.value : ""), 1),
			g.value.length ? (o(), p("button", {
				key: 0,
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-tasks": "",
				onClick: t[0] ||= (e) => T()
			}, "打开任务中心")) : x("", !0),
			g.value.length || m.value.length ? (o(), p("details", { key: c.value }, [E("summary", null, "查看" + y(m.value.length ? "任务及跳过原因" : "任务"), 1), E("ul", null, [(o(!0), p(P, null, r(g.value, (e, t) => (o(), p("li", { key: `task-${t}` }, [h("账号 #" + y(e.account_id) + " · " + y(t < d.value.length ? "已创建" : "进行中") + " ", 1), E("button", {
				type: "button",
				class: "jobs-tb-btn",
				"data-registration-retry-result": t,
				"data-registration-retry-task-id": b(e) || void 0,
				"data-registration-retry-run-id": b(e) && e.run_id ? e.run_id : void 0,
				onClick: (t) => T([e])
			}, "查看任务" + y(C(e) ? ` #${C(e)}` : ""), 9, lr)]))), 128)), (o(!0), p(P, null, r(m.value, (e, t) => (o(), p("li", { key: `skipped-${t}` }, "账号 #" + y(e.account_id) + " · " + y(e.reason || e.error || "当前不可重跑"), 1))), 128))])])) : x("", !0)
		], 8, sr)]));
	}
}), dr = /* @__PURE__ */ c({
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
	setup(n, { expose: r }) {
		let i = n, a = e(), s = e(), c = e(), l = e(), u = e(), d = e(), f = e(), m = N(), h = N(i.initialCapabilities), g = e(0), _ = N({});
		function y() {
			if (!a.value) throw Error("账号列表正在加载，请稍后重试");
			return a.value;
		}
		let b = A(() => {
			g.value;
			let e = a.value?.getActionContext(), t = e ? Object.fromEntries(oe.map((t) => [t.action, i.actions.isPending(t.action, e)])) : {};
			return t.reimportSelectedC2a = u.value?.isSubmitting === !0, {
				selectedCount: m.value?.selectedIds.length || 0,
				archived: m.value?.archived === "only",
				pending: t,
				labels: _.value
			};
		});
		async function x(e, t, n = null) {
			let r = i.actions.isSupported(e) ? i.actions.invoke(e, t, n) : i.callbacks.invoke(e, t, n);
			++g.value;
			try {
				await r;
			} finally {
				++g.value;
			}
		}
		let C = {
			...i.callbacks,
			invoke: x,
			onStateChange: (e) => {
				m.value = e, i.callbacks.onStateChange?.(e);
			},
			openDetail: (e, t, n, r) => {
				s.value ? s.value.open(e, t, n, r) : n.release();
			},
			closeConsumers: (e = !0) => {
				s.value?.close(e), i.callbacks.closeConsumers?.(e);
			}
		}, w = {
			notify: (e) => i.callbacks.notify?.(e),
			syncModalScrollLock: () => i.syncModalScrollLock()
		};
		return t(() => i.actions.dispose()), r({
			setVisible: (e) => {
				i.actions.setVisible(e), y().setVisible(e);
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
			closeDetail: (e = !0) => s.value?.close(e),
			isActionSupported: (e) => i.actions.isSupported(e),
			isActionPending: (e) => i.actions.isPending(e, y().getActionContext()),
			invokeAction: x,
			syncToolbarPending: () => {
				++g.value;
			},
			setToolbarBusyLabel: (e, t) => {
				let n = { ..._.value };
				t ? n[e] = t : delete n[e], _.value = n;
			},
			closeMoreMenus: () => y().closeMoreMenus(),
			setCapabilities: (e) => {
				h.value = e;
			},
			refreshQuickActions: () => d.value?.refreshQuickActions(),
			showRegistrationResult: (e, t, n) => f.value?.showResult(e, t, n),
			openInspectionStart: (e, t = null) => c.value?.openStart(e, t),
			openInspectionHistory: (e = null) => c.value?.openHistory(e),
			openInspectionFailures: (e, t = null) => c.value?.openFailures(e, t),
			closeInspection: (e) => c.value?.close(e),
			refreshInspectionHistory: () => c.value?.refreshHistory(),
			refreshInspectionFailures: () => c.value?.refreshFailures(),
			changeInspectionPage: (e) => c.value?.changeHistoryPage(e),
			changeInspectionFailuresPage: (e) => c.value?.changeFailuresPage(e),
			stopInspection: (e) => c.value?.stop(e),
			openEmailChange: (e, t, n = null) => l.value?.openSingle(e, t, n),
			openBulkEmailChange: (e, t = null) => l.value?.openBulk(e, t),
			closeEmailChange: (e = {}) => l.value?.close(e),
			openC2a: (e, t = null) => u.value?.open(e, t),
			closeC2a: (e = "cancel", t = {}) => u.value?.close(e, t),
			submitC2a: () => u.value?.submit(),
			showC2aResult: (e) => u.value?.showResult(e),
			openC2aTasks: (e) => u.value?.openTasks(e)
		}), (e, t) => (o(), p(P, null, [
			(o(), S(v, { to: "#accountToolbarHost" }, [I(_e, {
				ref_key: "toolbar",
				ref: d,
				state: b.value,
				capabilities: h.value,
				runtime: n.toolbarRuntime,
				"get-context": () => y().getActionContext(),
				invoke: x,
				notify: C.notify
			}, null, 8, [
				"state",
				"capabilities",
				"runtime",
				"get-context",
				"notify"
			])])),
			I(Et, {
				ref_key: "list",
				ref: a,
				adapter: n.adapter,
				api: n.api,
				presentation: n.presentation,
				callbacks: C
			}, null, 8, [
				"adapter",
				"api",
				"presentation"
			]),
			I(It, {
				ref_key: "drawer",
				ref: s,
				api: n.detailApi,
				presentation: n.detailPresentation,
				callbacks: w
			}, null, 8, ["api", "presentation"]),
			I(xn, {
				ref_key: "inspection",
				ref: c,
				deps: n.inspectionDependencies
			}, null, 8, ["deps"]),
			I(Bn, {
				ref_key: "emailChange",
				ref: l,
				deps: n.emailChangeDependencies
			}, null, 8, ["deps"]),
			I(or, {
				ref_key: "c2a",
				ref: u,
				deps: n.c2aDependencies
			}, null, 8, ["deps"]),
			I(ur, {
				ref_key: "registrationReceipt",
				ref: f,
				notify: C.notify
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
			}), o = await X(`/api/accounts?${a}`, { signal: i });
			return mr(o) && o.compact === !0 && fr(o.facets) && Array.isArray(o.search_terms) || hr(), o;
		},
		async statuses(t, n, r, i) {
			let a = e.toLegacy(t, {
				paged: "1",
				page: n,
				page_size: r
			});
			a.set("compact", "1");
			let o = await X(`/api/accounts/plan-check-status?${a}`, { signal: i });
			return mr(o) && fr(o.queue) && Array.isArray(o.status_fields) && o.status_fields.every((e) => typeof e == "string") || hr(), o;
		},
		async planDetails(e, t) {
			if (!/^[1-9]\d*$/.test(e)) throw Error("账号 ID 无效");
			let n = await X(`/api/accounts/${encodeURIComponent(e)}/plan-details`, { signal: t });
			return fr(n) && n.ok === !0 && fr(n.item) && Object.hasOwn(n.item, "account_promotions") && Object.hasOwn(n.item, "promotion_query_snapshot") && Array.isArray(n.item.plan_check_country_results) || hr(), n;
		}
	};
}
// src/api/accountDetail.ts
function _r() {
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
				let n = await E("/api/accounts/codex/upload-sub2-bulk", { account_ids: b }), r = Rr(n.skipped_count) + Rr(n.failed_count);
				n.accepted ? (e.notify(`手动上传已入队 ${Rr(n.queued_count)} 个${r ? `，跳过/未入队 ${r} 个` : ""}，最终结果在任务回执中更新`), await o(async () => t.trackAcceptedOperations(zr(Lr(n.queued)), "手动上传"))) : (e.notify(`已上传 ${Rr(n.uploaded_count)} 个${r ? `，跳过/失败 ${r} 个` : ""}`), await o(() => t.pollStatuses(y)));
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
		field: "copy_line",
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
	return D(dr, {
		adapter: n,
		api: gr(n),
		presentation: je(t.presentation),
		callbacks: t.callbacks,
		detailApi: _r(),
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
export { gi as mountAccounts };
