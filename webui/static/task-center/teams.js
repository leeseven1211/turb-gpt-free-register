import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, Z as u, _ as d, c as f, d as p, dt as m, et as h, ft as g, g as _, h as v, j as ee, l as te, lt as y, m as b, n as x, nt as S, o as ne, s as C, st as w, v as T, x as E, y as D } from "./_plugin-vue_export-helper-CBsH_ZoE.js";
import { a as O, i as k, n as A, o as j, t as M } from "./teams-CDSePuqJ.js";
import { t as re } from "./useNativeDialog-BgHdu813.js";
import { t as N } from "./errorLabels-BMfDB1_c.js";
import { n as P, t as F } from "./ColumnResizer-XOclQup1.js";
import { r as I, t as L } from "./ListFilterSummary-BjcCEzgL.js";
import { t as R } from "./ListPagination-CSFkV2Gz.js";
import { t as ie } from "./ListResult-EwR5MPFZ.js";
import { t as z } from "./ListToolbar-B8ViQxj1.js";
import { t as B } from "./TableState-CxHYH8ID.js";
// src/features/teams/statusLabels.ts
var V = Object.freeze({
	probe_expired: "核验结果已过期",
	probe_not_found: "核验记录不存在",
	team_workspace_unavailable: "工作区暂不可用",
	team_workspace_mismatch: "工作区身份不符",
	manager_permission_unconfirmed: "管理权限待核验",
	team_permission_denied: "母号无管理权限",
	team_already_bound: "工作区已绑定",
	team_auth_required: "账号登录待完成",
	revision_conflict: "工作区状态已变",
	team_limit_required: "需先设本地上限",
	team_invite_rate_limited: "发送邀请被限流",
	team_invite_rejected: "邀请被远端拒绝",
	team_invitation_revoked: "邀请已被撤回",
	team_invitation_expired: "邀请已过期",
	missing_auth_materials: "缺少认证材料",
	account_identity_changed: "账号身份已变化",
	account_unavailable: "账号不可用",
	account_not_found: "账号不存在",
	already_in_another_team: "已归属其他Team",
	already_member: "已是本组成员",
	team_member_unconfirmed: "成员关系待确认",
	team_save_failed: "本地保存失败",
	team_execution_lost: "执行租约已失效",
	team_store_unavailable: "团队存储不可用",
	waiting_account: "等待账号空闲",
	waiting_child: "等待执行步骤",
	waiting_sync: "等待完整同步",
	waiting_capacity: "等待可用名额",
	waiting_remote: "等待远端回执",
	same_team_active: "本组已有活跃执行",
	no_eligible_targets: "没有可处理目标",
	selection_expired: "固定名单已过期",
	selection_consumed: "固定名单已使用"
});
function H(e, t) {
	let n = String(e || t?.code || "").trim();
	return V[n] || (n ? N({
		code: n,
		error_code: n
	}) : t?.message || "状态待核对");
}
function U(e) {
	return e.display_name || e.name || e.workspace_id;
}
function W(e) {
	return e.purchased_seats === null ? e.planned_member_limit : e.planned_member_limit === null ? e.purchased_seats : Math.min(e.purchased_seats, e.planned_member_limit);
}
var G = Object.freeze({
	owner: "所有者",
	admin: "管理员",
	member: "成员",
	unknown: "待核验"
});
function ae(e) {
	return G[e] || "待核验";
}
function K(e) {
	return e === "owner" ? "active" : e === "admin" ? "success" : e === "unknown" ? "warning" : "neutral";
}
var q = Object.freeze({
	never: "未同步",
	queued: "排队同步",
	running: "同步中",
	success: "已同步",
	partial_success: "部分同步",
	failed: "同步失败",
	interrupted: "同步中断"
});
function oe(e) {
	return q[e || "never"] || "待同步";
}
function se(e) {
	return e === "success" ? "success" : e === "queued" || e === "running" ? "active" : e === "failed" ? "danger" : e === "partial_success" || e === "interrupted" ? "warning" : "neutral";
}
var ce = Object.freeze({
	joined: "已加入",
	left: "已退出",
	unconfirmed: "待确认"
});
function J(e) {
	return ce[e || "unconfirmed"] || "待确认";
}
function Y(e) {
	return e === "joined" ? "success" : e === "left" ? "danger" : "warning";
}
var le = Object.freeze({
	not_sent: "未发邀请",
	pending: "待接受邀请",
	accepted: "邀请已接受",
	revoked: "邀请已撤回",
	expired: "邀请已过期",
	unconfirmed: "邀请待确认"
});
function X(e) {
	return le[e || "unconfirmed"] || "邀请待确认";
}
var ue = Object.freeze({
	none: "未执行",
	queued: "排队中",
	running: "执行中",
	waiting: "等待中",
	cancelling: "正在取消",
	settling: "正在结算",
	stopping: "正在停止",
	success: "已完成",
	partial_success: "部分成功",
	failed: "执行失败",
	stopped: "已停止",
	cancelled: "已取消",
	interrupted: "执行中断",
	deactivated: "账号已停用",
	unsupported: "暂不支持"
}), Z = /* @__PURE__ */ new Set([
	"queued",
	"running",
	"waiting",
	"cancelling",
	"settling",
	"stopping"
]);
function de(e) {
	return ue[e || "none"] || "状态待核对";
}
function fe(e) {
	return e === "success" ? "success" : Z.has(e || "") ? "active" : e === "failed" || e === "deactivated" ? "danger" : e === "partial_success" || e === "interrupted" || e === "unsupported" ? "warning" : "neutral";
}
var pe = Object.freeze({
	queued: "排队等待",
	manager_verify: "核验母号权限",
	state_check: "核对业务事实",
	invite: "发送邀请",
	member_auth: "认证成员账号",
	accept: "接受邀请",
	member_verify: "核验成员关系",
	persist: "保存认证上下文",
	complete: "执行结束"
});
function me(e) {
	return e ? pe[e] || e : "尚无活跃阶段";
}
Object.freeze([
	{
		key: "queued",
		label: "排队等待"
	},
	{
		key: "manager_auth",
		label: "母号认证"
	},
	{
		key: "workspace_discovery",
		label: "发现工作区"
	},
	{
		key: "permission_check",
		label: "核验管理权限"
	}
]);
var Q = Object.freeze({
	purchased_seats: "已购席位",
	planned_member_limit: "本地计划上限",
	unavailable: "席位待确认"
});
function he(e) {
	return Q[e || "unavailable"] || "席位待确认";
}
function $(e, t = "待同步", n = "") {
	return e == null || !Number.isFinite(e) ? t : `${e}${n}`;
}
function ge(e) {
	let t = W(e);
	return {
		primary: `已购${e.purchased_seats === null ? "未返回" : ` ${e.purchased_seats} 席`}${e.planned_member_limit === null ? "" : ` · 上限 ${e.planned_member_limit}`}`,
		secondary: t === null ? "需设本地上限" : "余量待预检",
		tone: t === null ? "warning" : "neutral"
	};
}
function _e(e) {
	return {
		primary: X(e.invitation_state),
		secondary: `成员：${J(e.membership_state)}`,
		tone: e.membership_state === "joined" ? "success" : e.invitation_state === "pending" ? "active" : e.invitation_state === "revoked" || e.invitation_state === "expired" ? "danger" : "neutral"
	};
}
function ve(e) {
	let t = e.latest_execution;
	return {
		primary: de(t.status),
		secondary: [me(t.stage), t.waiting_reason_code ? H(t.waiting_reason_code) : ""].filter(Boolean).join(" · "),
		tone: fe(t.status)
	};
}
function ye(e) {
	let t = e.latest_execution, n = t.error_info;
	return n ? {
		label: H(n.code, n),
		secondary: n.code,
		detail: n.message,
		tone: "danger"
	} : t.waiting_reason_code ? {
		label: H(t.waiting_reason_code),
		secondary: "等待处理",
		detail: "",
		tone: "warning"
	} : e.membership_state === "joined" ? {
		label: "已确认入组",
		secondary: "",
		detail: "",
		tone: "success"
	} : Z.has(t.status) ? {
		label: "正在处理加入",
		secondary: "",
		detail: "",
		tone: "active"
	} : {
		label: e.invitation_state === "pending" ? "待接受邀请" : "—",
		secondary: e.invitation_state === "pending" ? "可继续加入" : "",
		detail: "",
		tone: e.invitation_state === "pending" ? "warning" : "neutral"
	};
}
Object.freeze({
	new: {
		label: "可提交加入",
		tone: "success"
	},
	resume_invite: {
		label: "续接已有邀请",
		tone: "active"
	},
	already_member: {
		label: "已是本组成员",
		tone: "neutral"
	},
	same_team_active: {
		label: "复用活跃执行",
		tone: "active"
	},
	another_team: {
		label: "已属其他Team",
		tone: "warning"
	},
	missing_auth: {
		label: "缺认证材料",
		tone: "danger"
	},
	unavailable: {
		label: "账号不可用",
		tone: "danger"
	}
});
function be(e) {
	let t = 0;
	for (let n of String(e || "team")) t = (t << 5) - t + n.charCodeAt(0) | 0;
	return [
		226,
		202,
		168,
		258,
		190,
		240,
		152,
		28
	][Math.abs(t) % 8];
}
function xe(e) {
	let t = String(e || "").trim();
	if (!t) return "TM";
	let n = t.split(/[\s\-_·]+/).filter(Boolean);
	return (n.length >= 2 ? Array.from(n[0])[0] + Array.from(n[1])[0] : Array.from(t).slice(0, 2).join("")).toUpperCase();
}
function Se(e) {
	return !!(e && (e.last_sync_status === "queued" || e.last_sync_status === "running" || (e.processing_count ?? 0) > 0));
}
// src/features/teams/TeamBindModal.vue?vue&type=script&setup=true&lang.ts
var Ce = ["aria-busy"], we = { class: "tm-dialog__head" }, Te = { class: "tm-dialog__kicker" }, Ee = {
	id: "teamBindDialogTitle",
	class: "tm-dialog__title"
}, De = { class: "tm-dialog__desc" }, Oe = { class: "tm-mono" }, ke = ["disabled"], Ae = { class: "tm-dialog__body" }, je = { class: "tm-field" }, Me = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "10px",
	"flex-wrap": "wrap"
} }, Ne = {
	class: "tm-search-box",
	style: {
		flex: "1 1 260px",
		"max-width": "340px"
	}
}, Pe = ["disabled", "onKeydown"], Fe = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Ie = { class: "tm-banner__copy" }, Le = {
	key: 1,
	class: "tm-field__hint",
	role: "status"
}, Re = {
	key: 2,
	class: "tm-banner tm-banner--warning",
	role: "alert"
}, ze = { class: "tm-banner__copy" }, Be = ["aria-busy"], Ve = {
	key: 0,
	style: {
		padding: "18px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, He = {
	key: 1,
	style: {
		padding: "18px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, Ue = ["onClick"], We = {
	class: "tm-candidate-row__left",
	style: {
		"min-width": "0",
		flex: "1"
	}
}, Ge = [
	"checked",
	"aria-label",
	"onChange"
], Ke = {
	class: "tm-cell-stack",
	style: { "min-width": "0" }
}, qe = { class: "tm-cell-primary" }, Je = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, Ye = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, Xe = { class: "tm-badge tm-badge--neutral" }, Ze = {
	key: 1,
	class: "tm-badge tm-badge--active"
}, Qe = {
	key: 0,
	class: "tm-cell-sub tm-local-manager-associations",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "6px",
		"flex-wrap": "wrap"
	}
}, $e = {
	key: 1,
	class: "tm-cell-sub",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "6px",
		"flex-wrap": "wrap"
	}
}, et = ["disabled", "onClick"], tt = {
	key: 3,
	style: {
		display: "flex",
		"align-items": "center",
		"justify-content": "space-between",
		gap: "8px",
		"padding-top": "2px"
	}
}, nt = { class: "tm-field__hint" }, rt = ["disabled"], it = {
	key: 0,
	class: "tm-field"
}, at = {
	class: "tm-probe-stepper",
	role: "status",
	"aria-live": "polite"
}, ot = { class: "tm-probe-step__dot" }, st = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, ct = { class: "tm-banner__copy" }, lt = ["disabled"], ut = {
	key: 1,
	class: "tm-banner tm-banner--warning",
	role: "alert"
}, dt = ["disabled"], ft = {
	key: 2,
	class: "tm-field"
}, pt = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "8px"
} }, mt = { class: "tm-field__hint" }, ht = {
	key: 0,
	class: "tm-banner tm-banner--warning"
}, gt = {
	key: 1,
	class: "tm-workspace-list"
}, _t = [
	"aria-checked",
	"aria-disabled",
	"onClick"
], vt = { style: {
	display: "flex",
	"align-items": "flex-start",
	gap: "10px",
	"min-width": "0",
	flex: "1"
} }, yt = [
	"checked",
	"disabled",
	"onChange"
], bt = {
	class: "tm-cell-stack",
	style: {
		"min-width": "0",
		flex: "1"
	}
}, xt = {
	class: "tm-cell-primary",
	style: { "flex-wrap": "wrap" }
}, St = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, Ct = { class: "tm-plan-tag" }, wt = {
	class: "tm-cell-sub",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "10px",
		"flex-wrap": "wrap"
	}
}, Tt = {
	key: 0,
	class: "tm-cell-sub is-danger"
}, Et = {
	key: 3,
	class: "tm-field"
}, Dt = {
	key: 0,
	class: "tm-banner tm-banner--warning"
}, Ot = { class: "tm-form-grid" }, kt = { class: "tm-field" }, At = ["placeholder", "disabled"], jt = { class: "tm-field" }, Mt = ["disabled"], Nt = {
	key: 4,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Pt = { class: "tm-banner__copy" }, Ft = { class: "tm-dialog__foot" }, It = { class: "tm-field__hint" }, Lt = { class: "tm-dialog__foot-right" }, Rt = ["disabled"], zt = ["disabled"], Bt = /* @__PURE__ */ t({
	__name: "TeamBindModal",
	props: {
		open: { type: Boolean },
		api: {},
		mode: {},
		team: {},
		visible: { type: Boolean }
	},
	emits: [
		"close",
		"bound",
		"managerUpdated",
		"openExistingTeam",
		"notify"
	],
	setup(e, { emit: t }) {
		let r = [
			{
				key: "queued",
				label: "排队等待"
			},
			{
				key: "manager_auth",
				label: "母号认证"
			},
			{
				key: "workspace_discovery",
				label: "发现工作区"
			},
			{
				key: "permission_check",
				label: "核验管理权限"
			}
		], s = e, c = t, l = h();
		re(l, () => s.open && s.visible, () => s.visible);
		let u = h(""), m = h(!1), _ = h(""), x = h([]), S = h(null), C = h({}), D = h(!1), A = h(""), N = h(null), P = h(!1), F = h(""), I = h(""), L = h(Date.now()), R = h(""), ie = h(""), z = h(""), B = h(!1), V = h(null), U = h(!1), W = null, G = null, q = null, oe = !1, se = null, ce = null, J = null, Y = 0, le = b(() => s.open && s.visible), X = b(() => s.mode === "change_manager"), ue = b(() => x.value.find((e) => e.id === S.value) ?? null), Z = b(() => P.value || N.value?.status === "queued" || N.value?.status === "running"), de = b(() => {
			if (U.value) return !0;
			if (!N.value || !N.value.expires_at) return !1;
			let e = Date.parse(N.value.expires_at);
			return Number.isFinite(e) && e <= L.value;
		}), fe = b(() => N.value?.workspaces.find((e) => e.workspace_id === I.value) ?? null), pe = b(() => {
			let e = N.value;
			if (!e) return -1;
			if (e.status === "success" || e.stage === "complete") return r.length;
			let t = r.findIndex((t) => t.key === e.stage);
			return t >= 0 ? t : e.status === "queued" ? 0 : 1;
		}), me = b(() => {
			if (B.value || Z.value || de.value || !N.value || N.value.status !== "success" || N.value.manager_account.id !== S.value) return !1;
			let e = fe.value;
			return !(!e || !qt(e) || X.value && !s.team);
		});
		function Q() {
			se !== null && (window.clearTimeout(se), se = null), ce !== null && (window.clearInterval(ce), ce = null), J !== null && (window.clearTimeout(J), J = null);
		}
		function he() {
			se !== null && (window.clearTimeout(se), se = null), G &&= (G.abort(), null), P.value = !1;
		}
		function $() {
			J !== null && (window.clearTimeout(J), J = null), W &&= (W.abort(), null);
		}
		function ge() {
			q?.abort(), q = null, D.value = !1;
		}
		function _e() {
			$(), he(), ge(), Q(), u.value = "", m.value = !1, _.value = "", x.value = [], C.value = {}, oe = !1, A.value = "", S.value = null, N.value = null, F.value = "", I.value = "", R.value = "", ie.value = "", z.value = "", V.value = null, U.value = !1, L.value = Date.now();
		}
		function ve(e) {
			return e instanceof DOMException && e.name === "AbortError";
		}
		async function ye() {
			if (!le.value || oe || q) return;
			let e = new AbortController(), t = Y;
			q = e, D.value = !0, A.value = "";
			let n = () => t === Y && q === e && le.value && !e.signal.aborted;
			try {
				let t = /* @__PURE__ */ new Map(), r = 1;
				for (;;) {
					let i = await s.api.list({
						page: r,
						page_size: 100,
						include_facets: "0"
					}, e.signal);
					if (!n()) return;
					for (let e of i.items) t.set(e.id, e);
					if (r * i.page_size >= i.total) break;
					++r;
				}
				let i = {};
				for (let e of t.values()) (i[e.manager_account.id] ??= []).push(e);
				C.value = i, oe = !0;
			} catch (e) {
				if (!n()) return;
				A.value = e instanceof Error ? e.message : "读取本地关联失败";
			} finally {
				n() && (q = null, D.value = !1);
			}
		}
		function be(e) {
			if (!Array.isArray(e)) return [];
			let t = [];
			for (let n of e) {
				if (!n || typeof n != "object") continue;
				let e = n, r = k(e.team_id);
				r && e.membership_state === "joined" && t.push({
					team_id: r,
					workspace_id: String(e.workspace_id || ""),
					name: typeof e.name == "string" ? e.name : null,
					display_name: e.display_name ? String(e.display_name) : null,
					role: String(e.role || "unknown"),
					membership_state: "joined",
					last_verified_at: typeof e.last_verified_at == "string" ? e.last_verified_at : null
				});
			}
			return t;
		}
		async function xe() {
			if (!le.value) return;
			$();
			let e = new AbortController();
			W = e, m.value = !0, _.value = "";
			try {
				let t = new URLSearchParams({
					paged: "1",
					page: "1",
					page_size: "20",
					include_facets: "0",
					archived: "all"
				}), n = u.value.trim();
				n && t.set("q", n);
				let r = await fetch(`/api/accounts?${t.toString()}`, {
					credentials: "same-origin",
					headers: { Accept: "application/json" },
					signal: e.signal
				});
				if (r.status === 401 || r.redirected && new URL(r.url, window.location.origin).pathname === "/login") {
					let e = `${window.location.pathname}${window.location.search}${window.location.hash}`;
					window.location.assign(`/login?next=${encodeURIComponent(e)}`);
					return;
				}
				let i = await r.text();
				if (e.signal.aborted || W !== e || !le.value) return;
				let a = i ? O(i) : null;
				if (!r.ok || !a || a.ok === !1 || !Array.isArray(a.items)) {
					let e = a && typeof a.error == "string" && a.error || a && typeof a.message == "string" && a.message || `加载本地账号失败（HTTP ${r.status}）`;
					throw Error(e);
				}
				let o = [];
				for (let e of a.items) {
					if (!e || typeof e != "object") continue;
					let t = e, n = k(t.id);
					n && o.push({
						id: n,
						email: String(t.email || `账号 #${n}`),
						archived: !!t.archived,
						account_status: String(t.account_status || "未知状态"),
						team_memberships: be(t.team_memberships)
					});
				}
				x.value = o, !S.value && o.length === 1 && !Vt(o[0]) && (S.value = o[0].id);
			} catch (t) {
				if (ve(t) || e.signal.aborted || W !== e) return;
				_.value = t instanceof Error ? t.message : "加载账号列表失败";
			} finally {
				W === e && (W = null, m.value = !1);
			}
		}
		function Se() {
			J !== null && window.clearTimeout(J), J = window.setTimeout(() => {
				J = null, xe();
			}, 260);
		}
		function Bt() {
			u.value = "", xe();
		}
		function Vt(e) {
			return X.value && s.team?.manager_account.id === e.id;
		}
		function Ht(e) {
			Z.value || B.value || (S.value !== e && (he(), ce !== null && (window.clearInterval(ce), ce = null), N.value = null, F.value = "", I.value = "", U.value = !1), S.value = e, z.value = "", V.value = null);
		}
		function Ut(e) {
			let t = e.workspaces || [];
			if (X.value) {
				let e = t.find((e) => qt(e));
				I.value = e?.workspace_id ?? "";
				return;
			}
			if (e.suggested_workspace_id && t.some((t) => t.workspace_id === e.suggested_workspace_id && qt(t))) {
				I.value = e.suggested_workspace_id;
				return;
			}
			let n = t.filter(qt);
			I.value = n.length === 1 ? n[0].workspace_id : "";
		}
		function Wt() {
			ce === null && (ce = window.setInterval(() => {
				L.value = Date.now();
			}, 5e3));
		}
		async function Gt(e, t) {
			if (le.value && !t.signal.aborted) try {
				let n = await s.api.getBindingProbe(e, t.signal);
				if (t.signal.aborted || !le.value) return;
				if (N.value = n, L.value = Date.now(), n.status === "queued" || n.status === "running") {
					se = window.setTimeout(() => {
						se = null, Gt(e, t);
					}, 1500);
					return;
				}
				P.value = !1, n.status === "success" ? (Ut(n), Wt()) : (n.status === "failed" || n.status === "interrupted" || n.status === "cancelled") && (F.value = n.error_info?.message || H(n.error_info?.code) || "工作区核验失败");
			} catch (e) {
				if (ve(e) || t.signal.aborted) return;
				P.value = !1, F.value = e instanceof M || e instanceof Error ? e.message : "轮询探测状态失败";
			}
		}
		async function Kt(e) {
			let t = e ?? S.value;
			if (!t || B.value) return;
			S.value = t, he();
			let n = new AbortController();
			G = n, P.value = !0, F.value = "", z.value = "", V.value = null, U.value = !1, I.value = "", N.value = null;
			try {
				let e = await s.api.createBindingProbe({
					manager_account_id: j(t, "管理母号 ID"),
					...X.value && s.team ? { target_workspace_id: s.team.workspace_id } : {}
				}, n.signal);
				if (n.signal.aborted || !le.value) return;
				await Gt(e.probe_id, n);
			} catch (e) {
				if (ve(e) || n.signal.aborted) return;
				P.value = !1, F.value = e instanceof M || e instanceof Error ? e.message : "发起绑定探测失败";
			}
		}
		function qt(e) {
			return e.workspace_type === "team" && e.can_manage === !0 && (!X.value || e.workspace_id === s.team?.workspace_id);
		}
		function Jt(e) {
			!qt(e) || B.value || de.value || (I.value = e.workspace_id, z.value = "", V.value = null);
		}
		function Yt(e) {
			return e == null || !Number.isFinite(e) ? "未返回席位" : `已购 ${e} 席`;
		}
		function Xt(e) {
			return e.workspace_type === "team" ? e.can_manage === !0 ? X.value && e.workspace_id !== s.team?.workspace_id ? "更换母号仅核验当前工作区" : "当前工作区不可选" : "母号管理权限尚未确认" : "尚未确认是 Team 工作区";
		}
		function Zt(e) {
			let t = pe.value;
			return N.value?.status === "success" || e < t ? { "is-done": !0 } : e === t && Z.value ? { "is-current": !0 } : {};
		}
		function Qt() {
			let e = ie.value.trim();
			if (!e) return {
				ok: !0,
				value: null
			};
			if (!/^[1-9]\d*$/.test(e)) return {
				ok: !1,
				message: "本地计划人数上限必须为大于 0 的整数，或留空不设上限"
			};
			let t = Number(e);
			return !Number.isSafeInteger(t) || t <= 0 ? {
				ok: !1,
				message: "本地计划人数上限数值超出有效范围"
			} : {
				ok: !0,
				value: t
			};
		}
		async function $t() {
			if (!le.value || !me.value || !N.value || !fe.value) return;
			let e = Y, t = () => e === Y && s.open, n = N.value, r = fe.value, i = s.team;
			if (z.value = "", V.value = null, !X.value) {
				let e = R.value.trim();
				if (e.length > 120) {
					z.value = "本地显示别名不能超过 120 个字符";
					return;
				}
				let i = Qt();
				if (!i.ok) {
					z.value = i.message;
					return;
				}
				B.value = !0;
				try {
					let a = await s.api.createTeam({
						manager_account_id: n.manager_account.id,
						workspace_id: r.workspace_id,
						probe_id: n.id,
						probe_revision: n.revision,
						display_name: e || null,
						planned_member_limit: i.value
					});
					if (!t()) return;
					c("notify", "工作区绑定成功，正在后台同步成员快照"), c("bound", a.team), c("close");
				} catch (e) {
					if (!t()) return;
					if (e instanceof M) {
						if (e.code === "team_probe_expired" || e.code === "probe_expired") {
							U.value = !0, z.value = "核验结果已过期，请重新探测后再提交";
							return;
						}
						if (e.code === "team_already_bound") {
							let t = k(e.details.existing_team_id);
							V.value = t, z.value = e.message || "该工作区已在本地绑定，可直接打开已有 Team";
							return;
						}
						z.value = e.message || H(e.code);
					} else z.value = e instanceof Error ? e.message : "绑定工作区失败";
				} finally {
					t() && (B.value = !1);
				}
			} else if (i) {
				B.value = !0;
				try {
					let e = await s.api.updateTeam(i.id, {
						expected_revision: i.revision,
						manager_account_id: n.manager_account.id,
						probe_id: n.id,
						probe_revision: n.revision
					});
					if (!t()) return;
					c("notify", "管理母号已更换"), c("managerUpdated", e.team), c("close");
				} catch (e) {
					if (!t()) return;
					if (e instanceof M) {
						if (e.code === "team_probe_expired" || e.code === "probe_expired") {
							U.value = !0, z.value = "核验结果已过期，请重新探测后再提交";
							return;
						}
						z.value = e.message || H(e.code);
					} else z.value = e instanceof Error ? e.message : "更换管理母号失败";
				} finally {
					t() && (B.value = !1);
				}
			}
		}
		function en() {
			B.value || ($(), he(), ge(), c("close"));
		}
		function tn(e) {
			let t = l.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(n.width === 0 && n.height === 0 || e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && en();
		}
		return i([
			() => s.open,
			() => s.mode,
			() => s.team?.id,
			() => s.team?.workspace_id
		], () => {
			++Y, B.value = !1, _e(), le.value && (xe(), ye());
		}, {
			immediate: !0,
			flush: "sync"
		}), i(le, (e) => {
			if (!e) $(), he(), ge(), Q();
			else if (W || xe(), ye(), N.value?.status === "queued" || N.value?.status === "running") {
				let e = new AbortController();
				G = e, P.value = !0, Gt(N.value.id, e);
			} else N.value?.status === "success" && (L.value = Date.now(), Wt());
		}, { flush: "sync" }), ee(() => {
			++Y, $(), he(), ge(), Q();
		}), (t, i) => (n(), T("dialog", {
			ref_key: "dialogRef",
			ref: l,
			class: "tm-dialog tm-dialog--lg",
			"aria-labelledby": "teamBindDialogTitle",
			"aria-busy": B.value || Z.value,
			onCancel: te(en, ["prevent"]),
			onClick: tn
		}, [
			v("div", we, [v("div", null, [
				v("p", Te, g(X.value ? "TEAM MANAGER HANDOVER" : "TEAM WORKSPACE BINDING"), 1),
				v("h3", Ee, g(X.value ? "更换管理母号" : "绑定已有 Team 工作区"), 1),
				v("p", De, [X.value && e.team ? (n(), T(p, { key: 0 }, [
					i[7] ||= E(" 目标工作区：", -1),
					v("strong", null, g(e.team.display_name || e.team.name || e.team.workspace_id), 1),
					i[8] ||= E(" （", -1),
					v("span", Oe, g(e.team.workspace_id), 1),
					i[9] ||= E("），仅切换执行管理的本地母号，不转移远端所有权。 ", -1)
				], 64)) : (n(), T(p, { key: 1 }, [E(" 选择具备工作区管理权限的本地账号作为母号，通过后台探测核验工作区后建立本地关联。 ")], 64))])
			]), v("button", {
				type: "button",
				class: "tm-dialog__close",
				"aria-label": "关闭弹窗",
				disabled: B.value,
				onClick: en
			}, " × ", 8, ke)]),
			v("div", Ae, [
				v("section", je, [
					v("div", Me, [i[11] ||= v("span", { class: "tm-field__label" }, "1. 选择管理母号（包含已归档账号）", -1), v("div", Ne, [
						i[10] ||= v("svg", {
							class: "tm-search-box__icon",
							viewBox: "0 0 24 24",
							"aria-hidden": "true"
						}, [v("circle", {
							cx: "11",
							cy: "11",
							r: "7"
						}), v("path", { d: "m20 20-3.5-3.5" })], -1),
						a(v("input", {
							"onUpdate:modelValue": i[0] ||= (e) => u.value = e,
							type: "search",
							placeholder: "搜索账号邮箱或 #ID…",
							"aria-label": "搜索管理母号",
							disabled: B.value,
							onInput: Se,
							onKeydown: f(te(xe, ["prevent"]), ["enter"])
						}, null, 40, Pe), [[ne, u.value]]),
						u.value ? (n(), T("button", {
							key: 0,
							type: "button",
							class: "tm-search-box__clear",
							"aria-label": "清空搜索",
							onClick: Bt
						}, " × ")) : d("", !0)
					])]),
					_.value ? (n(), T("div", Fe, [v("div", Ie, g(_.value), 1), v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: xe
					}, "重试")])) : d("", !0),
					D.value ? (n(), T("div", Le, " 正在读取本地管理母号关联… ")) : d("", !0),
					A.value ? (n(), T("div", Re, [v("div", ze, "读取本地管理母号关联失败：" + g(A.value) + "，暂未取得完整关联。", 1), v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: ye
					}, "重试关联读取")])) : d("", !0),
					v("div", {
						class: "tm-candidate-list",
						style: { "max-height": "210px" },
						"aria-busy": m.value
					}, [m.value && !x.value.length ? (n(), T("div", Ve, " 正在搜索本地账号… ")) : x.value.length ? d("", !0) : (n(), T("div", He, " 未找到匹配的本地账号，请调整搜索关键字。 ")), (n(!0), T(p, null, o(x.value, (e) => (n(), T("div", {
						key: e.id,
						class: y(["tm-candidate-row", { "is-selected": S.value === e.id }]),
						style: { cursor: "pointer" },
						onClick: (t) => Ht(e.id)
					}, [v("div", We, [v("input", {
						type: "radio",
						name: "tm_bind_manager_account",
						checked: S.value === e.id,
						"aria-label": `选择母号 ${e.email}`,
						onChange: (t) => Ht(e.id)
					}, null, 40, Ge), v("div", Ke, [
						v("div", qe, [
							v("span", null, g(e.email), 1),
							v("span", Je, "#" + g(e.id), 1),
							e.archived ? (n(), T("span", Ye, "已归档")) : d("", !0),
							v("span", Xe, g(e.account_status), 1),
							Vt(e) ? (n(), T("span", Ze, "当前母号")) : d("", !0)
						]),
						C.value[e.id]?.length ? (n(), T("div", Qe, [i[12] ||= v("span", null, "本地管理母号：", -1), (n(!0), T(p, null, o(C.value[e.id], (e) => (n(), T("span", {
							key: e.id,
							class: "acc-team-pill"
						}, g(e.display_name || e.name || e.workspace_id), 1))), 128))])) : d("", !0),
						e.team_memberships.length ? (n(), T("div", $e, [i[13] ||= v("span", null, "已关联 Team：", -1), (n(!0), T(p, null, o(e.team_memberships, (e) => (n(), T("span", {
							key: `${e.team_id}:${e.workspace_id}`,
							class: "acc-team-pill"
						}, g(e.display_name || e.name || `Team #${e.team_id}`) + " · " + g(w(ae)(e.role)), 1))), 128))])) : d("", !0)
					])]), v("button", {
						type: "button",
						class: "tm-btn tm-btn--soft tm-btn--sm",
						disabled: Z.value || B.value,
						onClick: te((t) => Kt(e.id), ["stop"])
					}, g(Z.value && S.value === e.id ? "探测中…" : "探测并核验工作区"), 9, et)], 10, Ue))), 128))], 8, Be),
					ue.value ? (n(), T("div", tt, [v("span", nt, [
						i[14] ||= E(" 已选账号：", -1),
						v("strong", null, g(ue.value.email), 1),
						E("（#" + g(ue.value.id) + "） ", 1)
					]), v("button", {
						type: "button",
						class: "tm-btn tm-btn--primary tm-btn--sm",
						disabled: Z.value || B.value,
						onClick: i[1] ||= (e) => Kt()
					}, g(Z.value ? "正在探测工作区…" : "探测并核验工作区"), 9, rt)])) : d("", !0)
				]),
				N.value || P.value || F.value ? (n(), T("section", it, [
					i[15] ||= v("span", { class: "tm-field__label" }, "2. 工作区核验进度", -1),
					v("div", at, [(n(), T(p, null, o(r, (e, t) => v("div", {
						key: e.key,
						class: y(["tm-probe-step", Zt(t)])
					}, [v("span", ot, g(Zt(t)["is-done"] ? "✓" : t + 1), 1), v("span", null, g(e.label), 1)], 2)), 64))]),
					F.value ? (n(), T("div", st, [v("div", ct, [v("span", null, g(F.value), 1)]), v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: !S.value || Z.value || B.value,
						onClick: i[2] ||= (e) => Kt()
					}, " 重新探测 ", 8, lt)])) : d("", !0)
				])) : d("", !0),
				N.value && N.value.status === "success" && de.value ? (n(), T("div", ut, [i[16] ||= v("div", { class: "tm-banner__copy" }, [v("span", null, "核验结果已过期，请重新探测后继续确认绑定。")], -1), v("button", {
					type: "button",
					class: "tm-btn tm-btn--sm",
					disabled: !S.value || Z.value || B.value,
					onClick: i[3] ||= (e) => Kt()
				}, " 重新探测 ", 8, dt)])) : d("", !0),
				N.value && N.value.status === "success" ? (n(), T("section", ft, [v("div", pt, [i[17] ||= v("span", { class: "tm-field__label" }, "3. 选择目标工作区（单选确认）", -1), v("span", mt, " 核验账号：" + g(N.value.manager_account.email || `#${N.value.manager_account.id}`), 1)]), N.value.workspaces.length ? (n(), T("div", gt, [(n(!0), T(p, null, o(N.value.workspaces, (e) => (n(), T("div", {
					key: e.workspace_id,
					class: y(["tm-workspace-option", {
						"is-selected": I.value === e.workspace_id,
						"is-disabled": !qt(e) || de.value
					}]),
					role: "radio",
					"aria-checked": I.value === e.workspace_id,
					"aria-disabled": !qt(e) || de.value,
					onClick: (t) => Jt(e)
				}, [v("div", vt, [v("input", {
					type: "radio",
					name: "tm_probe_workspace",
					checked: I.value === e.workspace_id,
					disabled: !qt(e) || de.value || B.value,
					style: { "margin-top": "3px" },
					onChange: (t) => Jt(e)
				}, null, 40, yt), v("div", bt, [
					v("div", xt, [
						v("span", null, g(e.name || e.workspace_id), 1),
						v("span", St, g(e.workspace_id), 1),
						v("span", Ct, g(e.workspace_type === "team" ? "Team" : e.workspace_type === "personal" ? "个人空间" : "类型待确认"), 1),
						v("span", { class: y(["tm-badge", `tm-badge--${w(K)(e.role)}`]) }, g(w(ae)(e.role)), 3),
						v("span", { class: y(["tm-badge", e.can_manage === !0 ? "tm-badge--success" : e.can_manage === !1 ? "tm-badge--danger" : "tm-badge--neutral"]) }, g(e.can_manage === !0 ? "可管理" : e.can_manage === !1 ? "无管理权限" : "权限待确认"), 3)
					]),
					v("div", wt, [v("span", null, g(Yt(e.purchased_seats)), 1)]),
					qt(e) ? d("", !0) : (n(), T("div", Tt, " 不可选原因：" + g(Xt(e)), 1))
				])])], 10, _t))), 128))])) : (n(), T("div", ht, [...i[18] ||= [v("div", { class: "tm-banner__copy" }, "未在该账号下发现任何工作区。", -1)]]))])) : d("", !0),
				!X.value && N.value && N.value.status === "success" && fe.value ? (n(), T("section", Et, [
					i[24] ||= v("span", { class: "tm-field__label" }, "4. 本地显示与席位上限设置（可选）", -1),
					fe.value.purchased_seats === null ? (n(), T("div", Dt, [...i[19] ||= [v("div", { class: "tm-banner__copy" }, " 远端未返回已购席位数（未返回），强烈建议现在设置「本地计划人数上限」（含管理母号），否则后续拉人前必须先补设。 ", -1)]])) : d("", !0),
					v("div", Ot, [v("label", kt, [
						i[20] ||= v("span", { class: "tm-field__label" }, "本地显示别名（display_name）", -1),
						a(v("input", {
							"onUpdate:modelValue": i[4] ||= (e) => R.value = e,
							type: "text",
							maxlength: "120",
							placeholder: fe.value.name || "留空则使用远端工作区名称",
							disabled: B.value
						}, null, 8, At), [[ne, R.value]]),
						i[21] ||= v("span", { class: "tm-field__hint" }, "留空将展示远端工作区名称，最多 120 字符。", -1)
					]), v("label", jt, [
						i[22] ||= v("span", { class: "tm-field__label" }, "本地计划人数上限（planned_member_limit）", -1),
						a(v("input", {
							"onUpdate:modelValue": i[5] ||= (e) => ie.value = e,
							type: "text",
							inputmode: "numeric",
							placeholder: "正整数（含母号），留空不设上限",
							disabled: B.value
						}, null, 8, Mt), [[ne, ie.value]]),
						i[23] ||= v("span", { class: "tm-field__hint" }, " 默认策略仅使用已购剩余席位；同时设置时取两者较小值。 ", -1)
					])])
				])) : d("", !0),
				z.value ? (n(), T("div", Nt, [v("div", Pt, g(z.value), 1), V.value ? (n(), T("button", {
					key: 0,
					type: "button",
					class: "tm-btn tm-btn--soft tm-btn--sm",
					onClick: i[6] ||= (e) => c("openExistingTeam", V.value)
				}, " 打开已绑定 Team ")) : d("", !0)])) : d("", !0)
			]),
			v("div", Ft, [v("span", It, [X.value ? (n(), T(p, { key: 0 }, [E(" 仅更新本地执行管理身份，不自动退出或修改原有成员事实 ")], 64)) : (n(), T(p, { key: 1 }, [E(" 确认绑定后将立即入队后台首次成员与邀请同步任务 ")], 64))]), v("div", Lt, [v("button", {
				type: "button",
				class: "tm-btn",
				disabled: B.value,
				onClick: en
			}, " 取消 ", 8, Rt), v("button", {
				type: "button",
				class: "tm-btn tm-btn--primary",
				disabled: !me.value,
				onClick: $t
			}, g(B.value ? "提交中…" : X.value ? "确认更换母号" : "确认绑定工作区"), 9, zt)])])
		], 40, Ce));
	}
}), Vt = ["aria-busy"], Ht = { class: "tm-dialog__head" }, Ut = { class: "tm-dialog__desc" }, Wt = { class: "tm-mono" }, Gt = { style: {
	display: "flex",
	"align-items": "center",
	gap: "8px"
} }, Kt = ["disabled"], qt = { class: "tm-dialog__body" }, Jt = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "10px",
	"flex-wrap": "wrap"
} }, Yt = {
	class: "tm-search-box",
	style: {
		flex: "1 1 260px",
		"max-width": "340px"
	}
}, Xt = ["onKeydown"], Zt = {
	class: "tm-filter-pills",
	role: "group",
	"aria-label": "候选筛选条件"
}, Qt = {
	key: 0,
	style: {
		padding: "12px 14px",
		border: "1px solid var(--ui-color-border)",
		"border-radius": "9px",
		background: "var(--ui-color-surface-subtle)",
		display: "grid",
		gap: "10px"
	}
}, $t = { class: "tm-field" }, en = ["disabled"], tn = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "8px"
} }, nn = {
	key: 0,
	style: {
		color: "var(--ui-color-danger, #b91c1c)",
		"font-size": "12px"
	}
}, rn = {
	key: 1,
	class: "tm-field__hint"
}, an = ["disabled"], on = {
	key: 0,
	style: {
		display: "grid",
		gap: "8px",
		"padding-top": "8px",
		"border-top": "1px solid var(--ui-color-border)",
		"font-size": "12px"
	}
}, sn = { style: {
	display: "flex",
	"align-items": "center",
	gap: "12px",
	"flex-wrap": "wrap"
} }, cn = { key: 0 }, ln = { key: 1 }, un = { key: 2 }, dn = {
	key: 0,
	style: {
		display: "grid",
		gap: "3px",
		color: "var(--ui-color-text-secondary)"
	}
}, fn = {
	key: 1,
	style: { color: "var(--ui-color-danger, #b91c1c)" }
}, pn = {
	key: 2,
	style: {
		display: "grid",
		gap: "6px"
	}
}, mn = { class: "tm-mono" }, hn = [
	"checked",
	"disabled",
	"onChange"
], gn = { class: "tm-mono" }, _n = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, vn = {
	key: 1,
	class: "tm-field__hint"
}, yn = {
	key: 1,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, bn = { class: "tm-banner__copy" }, xn = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "8px",
	"font-size": "12px"
} }, Sn = ["disabled"], Cn = { class: "tm-field__hint tm-tabular" }, wn = ["aria-busy"], Tn = {
	key: 0,
	style: {
		padding: "24px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, En = {
	key: 1,
	style: {
		padding: "24px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, Dn = {
	class: "tm-candidate-row__left",
	style: {
		"min-width": "0",
		flex: "1"
	}
}, On = [
	"checked",
	"disabled",
	"onChange"
], kn = {
	class: "tm-cell-stack",
	style: { "min-width": "0" }
}, An = {
	class: "tm-cell-primary",
	style: { "flex-wrap": "wrap" }
}, jn = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, Mn = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, Nn = {
	key: 1,
	class: "tm-badge tm-badge--success"
}, Pn = {
	key: 2,
	class: "tm-badge tm-badge--neutral"
}, Fn = {
	key: 3,
	class: "tm-badge tm-badge--neutral"
}, In = {
	key: 4,
	class: "tm-badge tm-badge--danger"
}, Ln = {
	key: 0,
	class: "tm-cell-sub"
}, Rn = { style: {
	display: "flex",
	"align-items": "center",
	gap: "6px",
	flex: "none"
} }, zn = {
	key: 0,
	class: "tm-badge tm-badge--warning"
}, Bn = {
	key: 2,
	style: {
		display: "flex",
		"align-items": "center",
		"justify-content": "flex-end",
		gap: "8px"
	}
}, Vn = ["disabled"], Hn = { class: "tm-field__hint tm-tabular" }, Un = ["disabled"], Wn = { class: "tm-dialog__foot" }, Gn = { style: {
	display: "flex",
	"align-items": "center",
	gap: "10px"
} }, Kn = { class: "tm-tabular" }, qn = ["disabled"], Jn = { class: "tm-dialog__foot-right" }, Yn = ["disabled"], Xn = 20, Zn = /* @__PURE__ */ t({
	__name: "TeamCandidatePickerModal",
	props: {
		open: { type: Boolean },
		api: {},
		team: {},
		visible: { type: Boolean }
	},
	emits: [
		"close",
		"confirmCandidates",
		"openAdvancedInAccounts",
		"notify"
	],
	setup(e, { emit: t }) {
		let r = e, s = t, l = h();
		re(l, () => r.open && r.visible, () => r.visible);
		let u = h(""), m = h(!0), _ = h(!1), x = h(!1), S = h(!1), C = h(!1), w = h(1), D = h(0), O = h(!1), k = h(""), A = h([]), j = h([]), N = c({}), P = h(!1), F = h(""), I = h(!1), L = h(""), R = h(null), ie = null, z = null, B = null, V = b(() => r.open && r.visible), U = b(() => new Set(j.value)), W = b(() => Math.max(1, Math.ceil(D.value / Xn))), G = b(() => A.value.filter((e) => !e.disabled)), ae = b(() => G.value.length > 0 && G.value.every((e) => U.value.has(e.account.id)));
		function K(e) {
			return e instanceof DOMException && e.name === "AbortError";
		}
		function q() {
			B !== null && (window.clearTimeout(B), B = null), ie &&= (ie.abort(), null), z &&= (z.abort(), null), O.value = !1, I.value = !1;
		}
		function oe() {
			j.value = [];
			for (let e of Object.keys(N)) delete N[e];
		}
		function se() {
			q(), u.value = "", m.value = !0, _.value = !1, x.value = !1, S.value = !1, C.value = !1, w.value = 1, D.value = 0, A.value = [], k.value = "", oe(), P.value = !1, F.value = "", L.value = "", R.value = null;
		}
		function ce() {
			return {
				page: w.value,
				page_size: Xn,
				...u.value.trim() ? { q: u.value.trim() } : {},
				scope: m.value ? "unassigned" : "all",
				archived: C.value ? "all" : "0",
				..._.value ? { has_access_token: "true" } : {},
				...x.value ? { has_password: "true" } : {},
				...S.value ? { totp_enabled: "true" } : {}
			};
		}
		async function J() {
			if (!V.value || !r.team) return;
			ie && ie.abort();
			let e = new AbortController();
			ie = e, O.value = !0, k.value = "";
			try {
				let t = await r.api.listCandidates(r.team.id, ce(), e.signal);
				if (e.signal.aborted || !V.value) return;
				A.value = t.items, D.value = t.total;
			} catch (t) {
				if (K(t) || e.signal.aborted) return;
				k.value = t instanceof M || t instanceof Error ? t.message : "加载候选账号失败";
			} finally {
				ie === e && (ie = null, O.value = !1);
			}
		}
		function Y() {
			w.value = 1, J();
		}
		function le() {
			B !== null && window.clearTimeout(B), B = window.setTimeout(() => {
				B = null, Y();
			}, 260);
		}
		function X() {
			u.value = "", Y();
		}
		function ue(e, t) {
			U.value.has(e) || (j.value = [...j.value, e]), t && !Object.hasOwn(N, e) && (N[e] = t);
		}
		function Z(e) {
			U.value.has(e) && (j.value = j.value.filter((t) => t !== e)), delete N[e];
		}
		function de(e, t, n) {
			n && (U.value.has(e) ? Z(e) : ue(e, t));
		}
		function fe() {
			if (ae.value) {
				let e = new Set(G.value.map((e) => e.account.id));
				j.value = j.value.filter((t) => !e.has(t));
				for (let t of e) delete N[t];
			} else for (let e of G.value) ue(e.account.id, e.account.email);
		}
		function pe(e) {
			return e.category === "another_team" && e.other_teams.length ? `已归属「${e.other_teams.map((e) => e.display_name || e.name || e.workspace_id).join("、")}」` : e.reason_code ? H(e.reason_code) : me(e.category).label;
		}
		function me(e) {
			return {
				new: {
					label: "可加入",
					tone: "success"
				},
				resume_invite: {
					label: "可续邀请",
					tone: "active"
				},
				already_member: {
					label: "已是成员",
					tone: "neutral"
				},
				same_team_active: {
					label: "执行中可复用",
					tone: "active"
				},
				another_team: {
					label: "已属其他Team",
					tone: "warning"
				},
				missing_auth: {
					label: "缺认证材料",
					tone: "danger"
				},
				unavailable: {
					label: "账号不可用",
					tone: "danger"
				}
			}[e] ?? {
				label: "状态待核对",
				tone: "neutral"
			};
		}
		async function Q() {
			if (!r.team || I.value) return;
			let e = F.value.split(/[\r\n,;，；\t ]+/).map((e) => e.trim()).filter(Boolean);
			if (!e.length) {
				L.value = "请先粘贴邮箱地址或本地账号 ID";
				return;
			}
			z && z.abort();
			let t = new AbortController();
			z = t, I.value = !0, L.value = "";
			try {
				let n = await r.api.resolveCandidates(r.team.id, e, t.signal);
				if (t.signal.aborted || !V.value) return;
				let i = 0, a = [], o = [], c = [];
				for (let e of n.items) if (e.match_status === "not_found") o.push(e.input);
				else if (e.match_status === "ambiguous") c.push({
					input: e.input,
					candidates: e.candidates
				});
				else for (let t of e.candidates) t.disabled ? a.push({
					email: t.account.email || `#${t.account.id}`,
					account_id: t.account.id,
					reason: pe(t)
				}) : (ue(t.account.id, t.account.email), i++);
				R.value = {
					matchedSelectable: i,
					matchedIneligible: a,
					notFound: o,
					ambiguous: c
				}, i > 0 && s("notify", `已解析并勾选 ${i} 个可选账号`);
			} catch (e) {
				if (K(e) || t.signal.aborted) return;
				L.value = e instanceof M || e instanceof Error ? e.message : "解析输入账号失败";
			} finally {
				z === t && (z = null, I.value = !1);
			}
		}
		function he(e) {
			e < 1 || e > W.value || O.value || (w.value = e, J());
		}
		function $() {
			r.team && s("openAdvancedInAccounts", {
				team_id: r.team.id,
				effective_name: r.team.display_name || r.team.name || r.team.workspace_id
			});
		}
		function ge() {
			j.value.length && s("confirmCandidates", {
				accountIds: [...j.value],
				expectedEmails: { ...N }
			});
		}
		function _e() {
			q(), s("close");
		}
		function ve(e) {
			let t = l.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(n.width === 0 && n.height === 0 || e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && _e();
		}
		return i(() => [V.value, r.team?.id], ([e]) => {
			e ? (se(), J()) : q();
		}, { immediate: !0 }), ee(() => {
			q();
		}), (t, r) => (n(), T("dialog", {
			ref_key: "dialogRef",
			ref: l,
			class: "tm-dialog tm-dialog--xl",
			"aria-labelledby": "teamCandidatePickerTitle",
			"aria-busy": O.value || I.value,
			onCancel: te(_e, ["prevent"]),
			onClick: ve
		}, [
			v("div", Ht, [v("div", null, [
				r[13] ||= v("p", { class: "tm-dialog__kicker" }, "CANDIDATE PICKER", -1),
				r[14] ||= v("h3", {
					id: "teamCandidatePickerTitle",
					class: "tm-dialog__title"
				}, " 选择待加入账号 ", -1),
				v("p", Ut, [e.team ? (n(), T(p, { key: 0 }, [
					r[10] ||= E(" 目标 Team：", -1),
					v("strong", null, g(e.team.display_name || e.team.name || e.team.workspace_id), 1),
					r[11] ||= E(" （", -1),
					v("span", Wt, g(e.team.workspace_id), 1),
					r[12] ||= E("），默认聚焦未归属任何 Team 的账号。 ", -1)
				], 64)) : d("", !0)])
			]), v("div", Gt, [v("button", {
				type: "button",
				class: "tm-btn tm-btn--soft tm-btn--sm",
				disabled: !e.team,
				onClick: $
			}, " 去账号页高级筛选选人 → ", 8, Kt), v("button", {
				type: "button",
				class: "tm-dialog__close",
				"aria-label": "关闭候选选人器",
				onClick: _e
			}, " × ")])]),
			v("div", qt, [
				v("div", Jt, [v("div", Yt, [
					r[15] ||= v("svg", {
						class: "tm-search-box__icon",
						viewBox: "0 0 24 24",
						"aria-hidden": "true"
					}, [v("circle", {
						cx: "11",
						cy: "11",
						r: "7"
					}), v("path", { d: "m20 20-3.5-3.5" })], -1),
					a(v("input", {
						"onUpdate:modelValue": r[0] ||= (e) => u.value = e,
						type: "search",
						placeholder: "搜索候选账号邮箱或 #ID…",
						"aria-label": "搜索候选账号",
						onInput: le,
						onKeydown: f(te(Y, ["prevent"]), ["enter"])
					}, null, 40, Xt), [[ne, u.value]]),
					u.value ? (n(), T("button", {
						key: 0,
						type: "button",
						class: "tm-search-box__clear",
						"aria-label": "清空搜索",
						onClick: X
					}, " × ")) : d("", !0)
				]), v("button", {
					type: "button",
					class: "tm-btn tm-btn--sm",
					onClick: r[1] ||= (e) => P.value = !P.value
				}, g(P.value ? "收起批量粘贴解析" : "批量粘贴邮箱或账号 ID"), 1)]),
				v("div", Zt, [
					v("button", {
						type: "button",
						class: y(["tm-pill-toggle", { "is-active": m.value }]),
						onClick: r[2] ||= (e) => {
							m.value = !m.value, Y();
						}
					}, " 仅未归属任何 Team ", 2),
					v("button", {
						type: "button",
						class: y(["tm-pill-toggle", { "is-active": _.value }]),
						onClick: r[3] ||= (e) => {
							_.value = !_.value, Y();
						}
					}, " 有 Token ", 2),
					v("button", {
						type: "button",
						class: y(["tm-pill-toggle", { "is-active": x.value }]),
						onClick: r[4] ||= (e) => {
							x.value = !x.value, Y();
						}
					}, " 有密码 ", 2),
					v("button", {
						type: "button",
						class: y(["tm-pill-toggle", { "is-active": S.value }]),
						onClick: r[5] ||= (e) => {
							S.value = !S.value, Y();
						}
					}, " 已启用 2FA ", 2),
					v("button", {
						type: "button",
						class: y(["tm-pill-toggle", { "is-active": C.value }]),
						onClick: r[6] ||= (e) => {
							C.value = !C.value, Y();
						}
					}, " 包含归档账号 ", 2)
				]),
				P.value ? (n(), T("section", Qt, [
					v("div", $t, [r[16] ||= v("div", { style: {
						display: "flex",
						"align-items": "center",
						"justify-content": "space-between",
						gap: "8px"
					} }, [v("span", { class: "tm-field__label" }, "粘贴多行或逗号分隔的邮箱 / 本地账号 ID"), v("span", { class: "tm-field__hint" }, "仅查询本地账号集合，不触发登录或远端请求")], -1), a(v("textarea", {
						"onUpdate:modelValue": r[7] ||= (e) => F.value = e,
						rows: "3",
						placeholder: "例如：\nuser-a@example.com\n1024, 1025",
						disabled: I.value
					}, null, 8, en), [[ne, F.value]])]),
					v("div", tn, [L.value ? (n(), T("span", nn, g(L.value), 1)) : (n(), T("span", rn, "系统将自动识别可选账号并勾选，列出未命中与同名冲突项")), v("button", {
						type: "button",
						class: "tm-btn tm-btn--soft tm-btn--sm",
						disabled: I.value,
						onClick: Q
					}, g(I.value ? "解析中…" : "解析并勾选"), 9, an)]),
					R.value ? (n(), T("div", on, [
						v("div", sn, [
							v("span", null, [
								r[17] ||= E(" 自动勾选可选：", -1),
								v("strong", null, g(R.value.matchedSelectable), 1),
								r[18] ||= E(" 个 ", -1)
							]),
							R.value.matchedIneligible.length ? (n(), T("span", cn, [
								r[19] ||= E(" 不可选跳过：", -1),
								v("strong", null, g(R.value.matchedIneligible.length), 1),
								r[20] ||= E(" 个 ", -1)
							])) : d("", !0),
							R.value.notFound.length ? (n(), T("span", ln, [
								r[21] ||= E(" 未找到：", -1),
								v("strong", null, g(R.value.notFound.length), 1),
								r[22] ||= E(" 项 ", -1)
							])) : d("", !0),
							R.value.ambiguous.length ? (n(), T("span", un, [
								r[23] ||= E(" 同名冲突：", -1),
								v("strong", null, g(R.value.ambiguous.length), 1),
								r[24] ||= E(" 项 ", -1)
							])) : d("", !0)
						]),
						R.value.matchedIneligible.length ? (n(), T("div", dn, [r[25] ||= v("strong", null, "不可选明细：", -1), (n(!0), T(p, null, o(R.value.matchedIneligible, (e) => (n(), T("div", { key: `skip:${e.account_id}` }, g(e.email) + " (#" + g(e.account_id) + ") — " + g(e.reason), 1))), 128))])) : d("", !0),
						R.value.notFound.length ? (n(), T("div", fn, " 未找到项：" + g(R.value.notFound.join("、")), 1)) : d("", !0),
						R.value.ambiguous.length ? (n(), T("div", pn, [r[27] ||= v("strong", null, "同名/多匹配冲突（请手工核对具体 #account_id 后勾选）：", -1), (n(!0), T(p, null, o(R.value.ambiguous, (e) => (n(), T("div", {
							key: e.input,
							style: {
								padding: "8px 10px",
								border: "1px solid var(--ui-color-border)",
								"border-radius": "7px",
								background: "var(--ui-color-surface)",
								display: "grid",
								gap: "5px"
							}
						}, [v("div", null, [r[26] ||= E("输入项：", -1), v("span", mn, g(e.input), 1)]), (n(!0), T(p, null, o(e.candidates, (e) => (n(), T("label", {
							key: e.account.id,
							style: {
								display: "flex",
								"align-items": "center",
								gap: "8px"
							}
						}, [
							v("input", {
								type: "checkbox",
								checked: U.value.has(e.account.id),
								disabled: e.disabled,
								onChange: (t) => de(e.account.id, e.account.email, !e.disabled)
							}, null, 40, hn),
							v("span", null, g(e.account.email), 1),
							v("span", gn, "#" + g(e.account.id), 1),
							e.account.archived ? (n(), T("span", _n, "已归档")) : d("", !0),
							v("span", { class: y(["tm-badge", `tm-badge--${me(e.category).tone}`]) }, g(me(e.category).label), 3),
							e.disabled && e.reason_code ? (n(), T("span", vn, g(pe(e)), 1)) : d("", !0)
						]))), 128))]))), 128))])) : d("", !0)
					])) : d("", !0)
				])) : d("", !0),
				k.value ? (n(), T("div", yn, [v("div", bn, g(k.value), 1), v("button", {
					type: "button",
					class: "tm-btn tm-btn--sm",
					onClick: J
				}, "重试")])) : d("", !0),
				v("div", xn, [v("button", {
					type: "button",
					class: "tm-link-btn",
					disabled: !G.value.length,
					onClick: fe
				}, g(ae.value ? "取消勾选本页可选" : `全选本页可选 (${G.value.length})`), 9, Sn), v("span", Cn, " 共 " + g(D.value) + " 条候选 · 第 " + g(w.value) + " / " + g(W.value) + " 页 ", 1)]),
				v("div", {
					class: "tm-candidate-list",
					"aria-busy": O.value
				}, [O.value && !A.value.length ? (n(), T("div", Tn, " 正在加载候选账号… ")) : A.value.length ? d("", !0) : (n(), T("div", En, " 当前筛选条件下暂无候选账号，可放宽筛选或使用批量粘贴。 ")), (n(!0), T(p, null, o(A.value, (e) => (n(), T("label", {
					key: e.account.id,
					class: y(["tm-candidate-row", { "is-disabled": e.disabled }])
				}, [v("div", Dn, [v("input", {
					type: "checkbox",
					checked: U.value.has(e.account.id),
					disabled: e.disabled,
					onChange: (t) => de(e.account.id, e.account.email, !e.disabled)
				}, null, 40, On), v("div", kn, [v("div", An, [
					v("span", null, g(e.account.email), 1),
					v("span", jn, "#" + g(e.account.id), 1),
					e.account.archived ? (n(), T("span", Mn, "已归档")) : d("", !0),
					e.has_access_token ? (n(), T("span", Nn, "Token")) : d("", !0),
					e.has_password ? (n(), T("span", Pn, "密码")) : d("", !0),
					e.totp_enabled ? (n(), T("span", Fn, "2FA")) : d("", !0),
					e.email_status === "invalid" ? (n(), T("span", In, "邮箱失效")) : d("", !0)
				]), e.disabled || e.other_teams.length ? (n(), T("div", Ln, g(pe(e)), 1)) : d("", !0)])]), v("div", Rn, [e.category === "another_team" && e.other_teams.length ? (n(), T("span", zn, g(e.other_teams.map((e) => e.display_name || e.name || e.workspace_id).join("、")), 1)) : d("", !0), v("span", { class: y(["tm-badge", `tm-badge--${me(e.category).tone}`]) }, g(me(e.category).label), 3)])], 2))), 128))], 8, wn),
				W.value > 1 ? (n(), T("div", Bn, [
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: w.value <= 1 || O.value,
						onClick: r[8] ||= (e) => he(w.value - 1)
					}, " 上一页 ", 8, Vn),
					v("span", Hn, g(w.value) + " / " + g(W.value), 1),
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: w.value >= W.value || O.value,
						onClick: r[9] ||= (e) => he(w.value + 1)
					}, " 下一页 ", 8, Un)
				])) : d("", !0)
			]),
			v("div", Wn, [v("div", Gn, [v("strong", Kn, "已选 " + g(j.value.length) + " 个候选账号", 1), v("button", {
				type: "button",
				class: "tm-link-btn",
				disabled: !j.value.length,
				onClick: oe
			}, " 清空已选 ", 8, qn)]), v("div", Jn, [v("button", {
				type: "button",
				class: "tm-btn",
				onClick: _e
			}, "取消"), v("button", {
				type: "button",
				class: "tm-btn tm-btn--primary",
				disabled: !j.value.length,
				onClick: ge
			}, " 下一步：本地预览与席位核对 ", 8, Yn)])])
		], 40, Vt));
	}
});
// src/features/teams/useTeamPolling.ts
function Qn() {
	return typeof document < "u" && !!document.hidden;
}
function $n(e) {
	let t = Math.max(500, e.intervalMs ?? 3e3), n = h(!1), r, a = !1, o = !1, s = 0, c;
	function l() {
		r !== void 0 && (clearTimeout(r), r = void 0), n.value = !1;
	}
	function d() {
		return !o && e.visible() && !Qn() && e.shouldPoll();
	}
	function f(e) {
		l(), d() && e === s && (n.value = !0, r = setTimeout(() => {
			r = void 0, !d() || e !== s ? n.value = !1 : p(e);
		}, t));
	}
	async function p(t) {
		if (d() && t === s) {
			if (a) c = t;
			else {
				a = !0, n.value = !0;
				try {
					await e.onPoll();
				} finally {
					a = !1;
					let e = c;
					c = void 0, e !== void 0 && e === s && d() ? p(e) : !o && t === s && d() ? f(t) : n.value = !1;
				}
			}
		}
	}
	async function m() {
		l(), s += 1, await p(s);
	}
	function g() {
		c = void 0, s += 1, l();
	}
	function _(e) {
		d() ? e ? m() : r === void 0 && !a && f(s) : g();
	}
	function v() {
		Qn() ? g() : _(!0);
	}
	return typeof document < "u" && document.addEventListener("visibilitychange", v), i([() => e.visible(), () => e.shouldPoll()], ([e, t], n) => {
		_(n?.[0] === !1 && e === !0 && t);
	}, { immediate: !0 }), u(() => {
		o = !0, g(), typeof document < "u" && document.removeEventListener("visibilitychange", v);
	}), {
		isPolling: n,
		triggerNow: m,
		stop: g
	};
}
// src/features/teams/TeamInvitationsTab.vue?vue&type=script&setup=true&lang.ts
var er = {
	class: "ui-list",
	"aria-label": "邀请与入组记录"
}, tr = { class: "ui-list-count" }, nr = { key: 0 }, rr = { class: "tm-search-box" }, ir = ["disabled"], ar = ["disabled"], or = ["disabled"], sr = {
	key: 0,
	class: "ui-list-bulkbar"
}, cr = { class: "ui-list-bulkbar__count" }, lr = ["aria-busy"], ur = { scope: "col" }, dr = { style: {
	display: "inline-flex",
	"align-items": "center",
	gap: "10px"
} }, fr = [
	"checked",
	"indeterminate",
	"disabled"
], pr = { scope: "col" }, mr = { style: {
	display: "grid",
	gap: "10px"
} }, hr = { class: "tm-field" }, gr = ["value"], _r = ["value"], vr = { class: "tm-field" }, yr = ["value"], br = ["value"], xr = { class: "list-filter-actions" }, Sr = { scope: "col" }, Cr = { style: {
	display: "grid",
	gap: "10px"
} }, wr = { class: "tm-field" }, Tr = ["value"], Er = ["value"], Dr = { class: "tm-field" }, Or = ["value"], kr = ["value"], Ar = { class: "list-filter-actions" }, jr = { scope: "col" }, Mr = { scope: "col" }, Nr = { "data-label": "目标账号" }, Pr = { style: {
	display: "flex",
	"align-items": "flex-start",
	gap: "10px",
	"min-width": "0"
} }, Fr = [
	"aria-label",
	"checked",
	"onChange"
], Ir = { class: "tm-cell-stack" }, Lr = { class: "tm-cell-primary" }, Rr = ["title"], zr = {
	class: "tm-cell-sub",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "6px",
		"flex-wrap": "wrap"
	}
}, Br = ["onClick"], Vr = {
	key: 1,
	class: "tm-badge tm-badge--neutral"
}, Hr = {
	key: 2,
	class: "tm-badge tm-badge--neutral"
}, Ur = { "data-label": "业务事实" }, Wr = { class: "tm-cell-stack" }, Gr = { class: "tm-cell-primary" }, Kr = { class: "tm-cell-sub" }, qr = { "data-label": "执行与阶段" }, Jr = { class: "tm-cell-stack" }, Yr = { class: "tm-cell-primary" }, Xr = {
	key: 0,
	class: "tm-badge__dot"
}, Zr = ["title"], Qr = { "data-label": "结果摘要" }, $r = { key: 0 }, ei = { class: "tm-mono" }, ti = { "data-label": "时间" }, ni = { class: "tm-cell-stack" }, ri = { class: "tm-cell-sub" }, ii = { class: "tm-cell-sub" }, ai = { "data-label": "操作" }, oi = { class: "tm-row-actions" }, si = ["disabled", "onClick"], ci = ["disabled", "onClick"], li = ["onClick"], ui = {
	key: 3,
	class: "tm-cell-sub"
}, di = /* @__PURE__ */ t({
	__name: "TeamInvitationsTab",
	props: {
		api: {},
		teamId: {},
		visible: { type: Boolean },
		callbacks: {},
		joinRequestId: {}
	},
	emits: ["refresh-team", "clear-join-request"],
	setup(e, { expose: t, emit: s }) {
		let u = e, x = s, S = [
			{
				value: "not_sent",
				label: "未发邀请"
			},
			{
				value: "pending",
				label: "待接受邀请"
			},
			{
				value: "accepted",
				label: "邀请已接受"
			},
			{
				value: "revoked",
				label: "邀请已撤回"
			},
			{
				value: "expired",
				label: "邀请已过期"
			},
			{
				value: "unconfirmed",
				label: "邀请待确认"
			}
		], C = [
			{
				value: "joined",
				label: "已加入"
			},
			{
				value: "left",
				label: "已退出"
			},
			{
				value: "unconfirmed",
				label: "待确认"
			}
		], O = Object.entries(ue).map(([e, t]) => ({
			value: e,
			label: t
		})), k = Object.entries(pe).map(([e, t]) => ({
			value: e,
			label: t
		})), A = c({
			page: 1,
			page_size: 20,
			q: "",
			invitation_state: "",
			membership_state: "",
			execution_status: "",
			stage: "",
			join_request_id: u.joinRequestId || ""
		}), j = h(""), M = h(null), re = h(!1), N = h(!1), V = h(""), H = h([]), U = h(0), W = h({}), G = h(u.joinRequestId || ""), ae = h(!!u.joinRequestId), K = h(/* @__PURE__ */ new Set()), q = h(/* @__PURE__ */ new Set()), { widths: oe, total: se, resize: ce, resizeWithKeyboard: Y } = P({
			defaults: [
				215,
				132,
				154,
				178,
				152,
				198
			],
			storageKey: "turb_team_invitations_column_widths_v2",
			min: 90,
			max: 640
		}), le, fe = null, Q = 0, he = 0;
		function $() {
			let e = u.teamId, t = he;
			return {
				teamId: e,
				current: () => t === he && e === u.teamId
			};
		}
		function ge(e) {
			return `tm-badge--${e}`;
		}
		function be(e, t) {
			let n = W.value[e];
			if (!n) return null;
			let r = n.find((e) => e.value === t);
			return r ? r.count : null;
		}
		let xe = b(() => H.value.length > 0 && H.value.every((e) => K.value.has(e.id))), Se = b(() => !xe.value && H.value.some((e) => K.value.has(e.id)));
		function Ce(e) {
			let t = new Set(K.value);
			for (let n of H.value) e ? t.add(n.id) : t.delete(n.id);
			K.value = t;
		}
		function we(e, t) {
			let n = new Set(K.value);
			t ? n.add(e) : n.delete(e), K.value = n;
		}
		function Te() {
			K.value = /* @__PURE__ */ new Set();
		}
		let Ee = b(() => {
			let e = [];
			return A.join_request_id && e.push({
				key: "join_request_id",
				label: `入组批次：#${A.join_request_id}`,
				removeLabel: "清除批次过滤"
			}), A.q && e.push({
				key: "q",
				label: `关键词：${A.q}`,
				removeLabel: "清除关键词筛选"
			}), A.invitation_state && e.push({
				key: "invitation_state",
				label: `邀请状态：${X(A.invitation_state)}`,
				removeLabel: "清除邀请状态筛选"
			}), A.membership_state && e.push({
				key: "membership_state",
				label: `成员状态：${J(A.membership_state)}`,
				removeLabel: "清除成员状态筛选"
			}), A.execution_status && e.push({
				key: "execution_status",
				label: `执行状态：${de(A.execution_status)}`,
				removeLabel: "清除执行状态筛选"
			}), A.stage && e.push({
				key: "stage",
				label: `阶段：${me(A.stage)}`,
				removeLabel: "清除阶段筛选"
			}), e;
		}), De = b(() => Ee.value.length > 0);
		function Oe(e) {
			e === "q" ? (clearTimeout(le), j.value = "", A.q = "") : e === "join_request_id" ? (A.join_request_id = "", x("clear-join-request")) : e === "invitation_state" ? A.invitation_state = "" : e === "membership_state" ? A.membership_state = "" : e === "execution_status" ? A.execution_status = "" : e === "stage" && (A.stage = ""), A.page = 1, Fe();
		}
		function ke() {
			clearTimeout(le), j.value = "", A.q = "", A.invitation_state = "", A.membership_state = "", A.execution_status = "", A.stage = "", A.join_request_id && (A.join_request_id = "", x("clear-join-request")), A.page = 1, Fe();
		}
		function Ae() {
			clearTimeout(le), j.value = "", A.q !== "" && (A.q = "", A.page = 1, Fe());
		}
		function je(e, t) {
			A[e] = t, A.page = 1, Fe();
		}
		function Me(e, t) {
			A[e] = t, A.page = 1, Fe();
		}
		function Ne(e) {
			A.page = e, Fe();
		}
		function Pe(e) {
			A.page_size = e, A.page = 1, Fe();
		}
		async function Fe(e = {}) {
			if (!u.visible || !u.teamId) return;
			fe?.abort();
			let t = new AbortController();
			fe = t;
			let n = ++Q, r = u.teamId;
			e.silent || (re.value = !0), V.value = "";
			let i = {
				page: A.page,
				page_size: A.page_size,
				include_facets: String(e.includeFacets ?? 1),
				...A.q ? { q: A.q } : {},
				...A.invitation_state ? { invitation_state: A.invitation_state } : {},
				...A.membership_state ? { membership_state: A.membership_state } : {},
				...A.execution_status ? { execution_status: A.execution_status } : {},
				...A.stage ? { stage: A.stage } : {},
				...A.join_request_id ? { join_request_id: A.join_request_id } : {}
			};
			try {
				let e = await u.api.listInvitations(r, i, t.signal);
				if (t.signal.aborted || n !== Q || u.teamId !== r) return;
				if (H.value = e.items, U.value = e.total, G.value) {
					let e = await u.api.getJoinRequest(r, G.value, {
						page: 1,
						page_size: 1
					}, t.signal);
					if (t.signal.aborted || n !== Q) return;
					ae.value = ["preparing", ...Z].includes(e.request.status);
				}
				e.facets && Object.keys(e.facets).length > 0 && (W.value = e.facets);
			} catch (r) {
				if (t.signal.aborted || n !== Q) return;
				let i = r instanceof Error ? r.message : "加载邀请与入组记录失败";
				e.silent || (V.value = i);
			} finally {
				fe === t && (fe = null), n === Q && (re.value = !1);
			}
		}
		async function Ie(e) {
			let t = $(), n = new Set(q.value);
			n.add(e.id), q.value = n;
			try {
				let n = await u.api.continueInvitation(t.teamId, e.id);
				if (!t.current()) return;
				G.value = n.id, ae.value = !0, u.callbacks.notify(n.reused ? `已复用当前进行中的入组执行（${e.email_snapshot}）` : `已受理继续加入（${e.email_snapshot}）`), await Fe({
					silent: !0,
					includeFacets: 0
				}), t.current() && x("refresh-team");
			} catch (e) {
				if (!t.current()) return;
				u.callbacks.notify(e instanceof Error ? e.message : "继续加入提交失败");
			} finally {
				if (t.current()) {
					let t = new Set(q.value);
					t.delete(e.id), q.value = t;
				}
			}
		}
		async function Le(e) {
			let t = $(), n = new Set(q.value);
			n.add(e.id), q.value = n;
			try {
				let n = await u.api.retryInvitation(t.teamId, e.id);
				if (!t.current()) return;
				G.value = n.id, ae.value = !0, u.callbacks.notify(n.reused ? `已复用当前活跃执行（${e.email_snapshot}）` : `已创建重跑任务（${e.email_snapshot}）`), await Fe({
					silent: !0,
					includeFacets: 0
				}), t.current() && x("refresh-team");
			} catch (e) {
				if (!t.current()) return;
				u.callbacks.notify(e instanceof Error ? e.message : "重跑提交失败");
			} finally {
				if (t.current()) {
					let t = new Set(q.value);
					t.delete(e.id), q.value = t;
				}
			}
		}
		async function Re() {
			let e = [...K.value];
			if (!e.length || N.value) return;
			let t = $();
			N.value = !0;
			try {
				let n = await u.api.continueInvitationsBulk(t.teamId, e);
				if (!t.current()) return;
				G.value = n.id, ae.value = !0, u.callbacks.notify(`批量继续加入已持久受理 ${n.counts.unique_count} 项，等待后台逐项处理`), Te(), await Fe({
					silent: !0,
					includeFacets: 0
				}), t.current() && x("refresh-team");
			} catch (e) {
				if (!t.current()) return;
				u.callbacks.notify(e instanceof Error ? e.message : "批量继续加入失败");
			} finally {
				t.current() && (N.value = !1);
			}
		}
		async function ze() {
			let e = [...K.value];
			if (!e.length || N.value) return;
			let t = $();
			N.value = !0;
			try {
				let n = await u.api.retryInvitationsBulk(t.teamId, e);
				if (!t.current()) return;
				G.value = n.id, ae.value = !0, u.callbacks.notify(`批量重跑已持久受理 ${n.counts.unique_count} 项，等待后台逐项处理`), Te(), await Fe({
					silent: !0,
					includeFacets: 0
				}), t.current() && x("refresh-team");
			} catch (e) {
				if (!t.current()) return;
				u.callbacks.notify(e instanceof Error ? e.message : "批量重跑失败");
			} finally {
				t.current() && (N.value = !1);
			}
		}
		return $n({
			visible: () => u.visible,
			shouldPoll: () => ae.value || H.value.some((e) => Z.has(e.latest_execution.status)),
			onPoll: async () => {
				await Fe({
					silent: !0,
					includeFacets: 0
				}), x("refresh-team");
			},
			intervalMs: 3e3
		}), i(j, (e) => {
			clearTimeout(le);
			let t = e.trim();
			t !== A.q && (le = setTimeout(() => {
				A.q = t, A.page = 1, Fe();
			}, 250));
		}), i(() => u.joinRequestId, (e) => {
			let t = e || "";
			t !== A.join_request_id && (A.join_request_id = t, G.value = t, ae.value = !!t, A.page = 1, Fe());
		}), i(() => u.teamId, () => {
			he += 1, q.value = /* @__PURE__ */ new Set(), N.value = !1, A.page = 1, Te(), G.value = u.joinRequestId || "", ae.value = !!G.value, H.value = [], U.value = 0, W.value = {}, Fe();
		}, { immediate: !0 }), i(() => u.visible, (e) => {
			e ? Fe() : (fe?.abort(), fe = null, Q += 1, re.value = !1);
		}), ee(() => {
			he += 1, clearTimeout(le), fe?.abort();
		}), t({ refresh: () => Fe() }), (t, i) => (n(), T("section", er, [
			l(z, { filtered: De.value }, {
				actions: r(() => [
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--soft",
						disabled: !K.value.size || N.value,
						onClick: i[2] ||= (e) => void Re()
					}, g(N.value ? "处理中…" : "批量继续加入"), 9, ir),
					v("button", {
						type: "button",
						class: "tm-btn",
						disabled: !K.value.size || N.value,
						onClick: i[3] ||= (e) => void ze()
					}, " 批量重跑 ", 8, ar),
					v("button", {
						type: "button",
						class: "tm-btn ui-refresh-button",
						disabled: re.value,
						onClick: i[4] ||= (e) => void Fe()
					}, g(re.value ? "刷新中…" : "刷新"), 9, or)
				]),
				default: r(() => [
					v("span", tr, [E(" 共 " + g(U.value.toLocaleString()) + " 条邀请记录 ", 1), K.value.size ? (n(), T("small", nr, "已选 " + g(K.value.size) + " 项", 1)) : d("", !0)]),
					v("div", rr, [
						i[27] ||= v("svg", {
							class: "tm-search-box__icon",
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [v("circle", {
							cx: "7",
							cy: "7",
							r: "4.5"
						}), v("path", { d: "m10.5 10.5 3 3" })], -1),
						a(v("input", {
							"onUpdate:modelValue": i[0] ||= (e) => j.value = e,
							type: "search",
							"aria-label": "搜索邀请记录",
							placeholder: "搜索邮箱 / 本地账号 ID",
							onKeydown: i[1] ||= f(te((e) => {
								A.q = j.value.trim(), A.page = 1, Fe();
							}, ["prevent"]), ["enter"])
						}, null, 544), [[ne, j.value]]),
						j.value ? (n(), T("button", {
							key: 0,
							type: "button",
							class: "tm-search-box__clear",
							"aria-label": "清空搜索",
							onClick: Ae
						}, " × ")) : d("", !0)
					]),
					l(L, {
						items: Ee.value,
						onRemove: Oe
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			K.value.size ? (n(), T("div", sr, [v("span", cr, "已跨页选中 " + g(K.value.size) + " 条邀请记录", 1), v("button", {
				type: "button",
				class: "tm-btn tm-btn--ghost tm-btn--sm",
				onClick: Te
			}, " 清空选择 ")])) : d("", !0),
			v("div", {
				class: "ui-table-wrap ui-table-scroll",
				tabindex: "0",
				"aria-label": "邀请与入组表格，可横向滚动",
				"aria-busy": re.value
			}, [v("table", {
				class: "ui-table ui-table--sticky-end ui-table--cards",
				style: m({ "--ui-table-width": `${w(se)}px` })
			}, [
				i[41] ||= v("caption", { class: "ui-sr-only" }, "工作区邀请记录与自动入组状态（严格六列）", -1),
				v("colgroup", null, [(n(!0), T(p, null, o(w(oe), (e, t) => (n(), T("col", {
					key: t,
					style: m({ width: `${e}px` })
				}, null, 4))), 128))]),
				v("thead", null, [v("tr", null, [
					v("th", ur, [v("span", dr, [v("input", {
						type: "checkbox",
						"aria-label": "全选当前页邀请记录",
						checked: xe.value,
						indeterminate: Se.value,
						disabled: !H.value.length,
						onChange: i[5] ||= (e) => Ce(e.target.checked)
					}, null, 40, fr), i[28] ||= v("span", null, "目标账号", -1)]), l(F, {
						label: "目标账号",
						onStart: i[6] ||= (e) => w(ce)(0, e),
						onNudge: i[7] ||= (e) => w(Y)(0, e)
					})]),
					v("th", pr, [l(I, {
						label: "业务事实",
						active: !!(A.invitation_state || A.membership_state),
						summary: [A.invitation_state ? w(X)(A.invitation_state) : "", A.membership_state ? w(J)(A.membership_state) : ""].filter(Boolean).join(" · "),
						open: e.visible && M.value === "business",
						"onUpdate:open": i[12] ||= (e) => M.value = e ? "business" : null
					}, {
						default: r(() => [v("div", mr, [
							v("label", hr, [i[30] ||= v("span", { class: "tm-field__label" }, "邀请状态", -1), v("select", {
								value: A.invitation_state,
								"aria-label": "筛选邀请状态",
								onChange: i[8] ||= (e) => je("invitation_state", e.target.value)
							}, [i[29] ||= v("option", { value: "" }, "全部邀请状态", -1), (n(), T(p, null, o(S, (e) => v("option", {
								key: e.value,
								value: e.value
							}, g(e.label) + g(be("invitation_state", e.value) === null ? "" : ` (${be("invitation_state", e.value)})`), 9, _r)), 64))], 40, gr)]),
							v("label", vr, [i[32] ||= v("span", { class: "tm-field__label" }, "成员状态", -1), v("select", {
								value: A.membership_state,
								"aria-label": "筛选成员状态",
								onChange: i[9] ||= (e) => je("membership_state", e.target.value)
							}, [i[31] ||= v("option", { value: "" }, "全部成员状态", -1), (n(), T(p, null, o(C, (e) => v("option", {
								key: e.value,
								value: e.value
							}, g(e.label) + g(be("membership_state", e.value) === null ? "" : ` (${be("membership_state", e.value)})`), 9, br)), 64))], 40, yr)]),
							v("div", xr, [v("button", {
								type: "button",
								onClick: i[10] ||= (e) => {
									A.invitation_state = "", A.membership_state = "", A.page = 1, M.value = null, Fe();
								}
							}, " 清除 "), v("button", {
								type: "button",
								class: "list-filter-primary",
								onClick: i[11] ||= (e) => M.value = null
							}, "完成")])
						])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(F, {
						label: "业务事实",
						onStart: i[13] ||= (e) => w(ce)(1, e),
						onNudge: i[14] ||= (e) => w(Y)(1, e)
					})]),
					v("th", Sr, [l(I, {
						label: "执行与阶段",
						active: !!(A.execution_status || A.stage),
						summary: [A.execution_status ? w(de)(A.execution_status) : "", A.stage ? w(me)(A.stage) : ""].filter(Boolean).join(" · "),
						open: e.visible && M.value === "execution",
						"onUpdate:open": i[19] ||= (e) => M.value = e ? "execution" : null
					}, {
						default: r(() => [v("div", Cr, [
							v("label", wr, [i[34] ||= v("span", { class: "tm-field__label" }, "执行状态", -1), v("select", {
								value: A.execution_status,
								"aria-label": "筛选执行状态",
								onChange: i[15] ||= (e) => Me("execution_status", e.target.value)
							}, [i[33] ||= v("option", { value: "" }, "全部执行状态", -1), (n(!0), T(p, null, o(w(O), (e) => (n(), T("option", {
								key: e.value,
								value: e.value
							}, g(e.label) + g(be("execution_status", e.value) === null ? "" : ` (${be("execution_status", e.value)})`), 9, Er))), 128))], 40, Tr)]),
							v("label", Dr, [i[36] ||= v("span", { class: "tm-field__label" }, "当前阶段", -1), v("select", {
								value: A.stage,
								"aria-label": "筛选当前阶段",
								onChange: i[16] ||= (e) => Me("stage", e.target.value)
							}, [i[35] ||= v("option", { value: "" }, "全部阶段", -1), (n(!0), T(p, null, o(w(k), (e) => (n(), T("option", {
								key: e.value,
								value: e.value
							}, g(e.label) + g(be("stage", e.value) === null ? "" : ` (${be("stage", e.value)})`), 9, kr))), 128))], 40, Or)]),
							v("div", Ar, [v("button", {
								type: "button",
								onClick: i[17] ||= (e) => {
									A.execution_status = "", A.stage = "", A.page = 1, M.value = null, Fe();
								}
							}, " 清除 "), v("button", {
								type: "button",
								class: "list-filter-primary",
								onClick: i[18] ||= (e) => M.value = null
							}, "完成")])
						])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(F, {
						label: "执行与阶段",
						onStart: i[20] ||= (e) => w(ce)(2, e),
						onNudge: i[21] ||= (e) => w(Y)(2, e)
					})]),
					v("th", jr, [i[37] ||= E(" 结果摘要 ", -1), l(F, {
						label: "结果摘要",
						onStart: i[22] ||= (e) => w(ce)(3, e),
						onNudge: i[23] ||= (e) => w(Y)(3, e)
					})]),
					v("th", Mr, [i[38] ||= E(" 时间 ", -1), l(F, {
						label: "时间",
						onStart: i[24] ||= (e) => w(ce)(4, e),
						onNudge: i[25] ||= (e) => w(Y)(4, e)
					})]),
					i[39] ||= v("th", { scope: "col" }, "操作", -1)
				])]),
				v("tbody", null, [(n(!0), T(p, null, o(H.value, (t) => (n(), T("tr", {
					key: t.id,
					class: y({ "is-selected": K.value.has(t.id) })
				}, [
					v("td", Nr, [v("div", Pr, [v("input", {
						type: "checkbox",
						style: { "margin-top": "3px" },
						"aria-label": `选择邀请记录 ${t.email_snapshot}`,
						checked: K.value.has(t.id),
						onChange: (e) => we(t.id, e.target.checked)
					}, null, 40, Fr), v("div", Ir, [v("div", Lr, [v("span", { title: t.email_snapshot || void 0 }, g(t.email_snapshot || t.account?.email || "未返回"), 9, Rr)]), v("div", zr, [t.account?.id ? (n(), T("button", {
						key: 0,
						type: "button",
						class: "tm-link-btn tm-tabular",
						onClick: (n) => e.callbacks.openAccountDetail(t.account.id)
					}, " #" + g(t.account?.id), 9, Br)) : (n(), T("span", Vr, "未入库")), t.account?.archived ? (n(), T("span", Hr, "已归档")) : d("", !0)])])])]),
					v("td", Ur, [v("div", Wr, [v("div", Gr, [v("span", { class: y(["tm-badge", ge(w(_e)(t).tone)]) }, g(w(_e)(t).primary), 3)]), v("div", Kr, g(w(_e)(t).secondary), 1)])]),
					v("td", qr, [v("div", Jr, [v("div", Yr, [v("span", { class: y(["tm-badge", ge(w(ve)(t).tone)]) }, [w(Z).has(t.latest_execution.status) ? (n(), T("span", Xr)) : d("", !0), E(" " + g(w(ve)(t).primary), 1)], 2)]), v("div", {
						class: "tm-cell-sub",
						title: w(ve)(t).secondary
					}, g(w(ve)(t).secondary), 9, Zr)])]),
					v("td", Qr, [l(ie, {
						label: w(ye)(t).label,
						secondary: w(ye)(t).secondary,
						tone: w(ye)(t).tone,
						title: w(ye)(t).detail || w(ye)(t).label
					}, D({ _: 2 }, [w(ye)(t).detail ? {
						name: "details",
						fn: r(() => [t.latest_execution.error_info?.code ? (n(), T("p", $r, [i[40] ||= E(" 原因码：", -1), v("span", ei, g(t.latest_execution.error_info?.code), 1)])) : d("", !0), v("p", null, g(w(ye)(t).detail), 1)]),
						key: "0"
					} : void 0]), 1032, [
						"label",
						"secondary",
						"tone",
						"title"
					])]),
					v("td", ti, [v("div", ni, [v("div", ri, " 核验于：" + g(t.last_verified_at ? e.callbacks.formatDateTime(t.last_verified_at) : "—"), 1), v("div", ii, " 更新于：" + g(e.callbacks.formatDateTime(t.updated_at)), 1)])]),
					v("td", ai, [v("div", oi, [
						t.actions.continue.enabled ? (n(), T("button", {
							key: 0,
							type: "button",
							class: "tm-btn tm-btn--sm tm-btn--soft",
							disabled: q.value.has(t.id),
							onClick: (e) => void Ie(t)
						}, " 继续加入 ", 8, si)) : d("", !0),
						t.actions.retry.enabled ? (n(), T("button", {
							key: 1,
							type: "button",
							class: "tm-btn tm-btn--sm",
							disabled: q.value.has(t.id),
							onClick: (e) => void Le(t)
						}, " 重跑 ", 8, ci)) : d("", !0),
						t.actions.view_task.enabled && t.latest_execution.task_id ? (n(), T("button", {
							key: 2,
							type: "button",
							class: "tm-btn tm-btn--sm tm-btn--ghost",
							onClick: (n) => e.callbacks.openTask(t.latest_execution.task_id, t.latest_execution.run_id)
						}, " 查看任务 ", 8, li)) : d("", !0),
						!t.actions.continue.enabled && !t.actions.retry.enabled && !(t.actions.view_task.enabled && t.latest_execution.task_id) ? (n(), T("span", ui, " — ")) : d("", !0)
					])])
				], 2))), 128)), H.value.length ? d("", !0) : (n(), _(B, {
					key: 0,
					colspan: 6,
					loading: re.value,
					error: V.value,
					"loading-title": "正在加载邀请与入组记录",
					"loading-text": "同步当前工作区的远端邀请与自动加入进度",
					"error-title": "加载邀请记录失败",
					title: De.value ? "没有匹配的邀请记录" : "暂无邀请与入组记录",
					text: De.value ? "可调整搜索或筛选条件后重试。" : "点击上方「加入账号」批量发起邀请，或等待工作区同步返回远端待接受邀请。",
					"retry-label": "重试",
					onRetry: i[26] ||= (e) => void Fe()
				}, {
					default: r(() => [!re.value && !V.value && De.value ? (n(), T("button", {
						key: 0,
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: ke
					}, " 清除筛选条件 ")) : d("", !0)]),
					_: 1
				}, 8, [
					"loading",
					"error",
					"title",
					"text"
				]))])
			], 4)], 8, lr),
			l(R, {
				page: A.page,
				size: A.page_size,
				total: U.value,
				busy: re.value,
				label: "邀请记录分页",
				"onUpdate:page": Ne,
				"onUpdate:size": Pe
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy"
			])
		]));
	}
}), fi = {
	class: "ui-list",
	"aria-label": "工作区成员列表"
}, pi = { class: "ui-list-count" }, mi = { class: "tm-search-box" }, hi = ["disabled"], gi = ["aria-busy"], _i = { scope: "col" }, vi = { scope: "col" }, yi = { class: "list-filter-options" }, bi = [
	"value",
	"checked",
	"onChange"
], xi = { key: 0 }, Si = { class: "list-filter-actions" }, Ci = { scope: "col" }, wi = { class: "list-filter-options" }, Ti = { class: "list-filter-option" }, Ei = ["checked"], Di = [
	"value",
	"checked",
	"onChange"
], Oi = { key: 0 }, ki = { class: "list-filter-actions" }, Ai = { scope: "col" }, ji = { class: "list-filter-options" }, Mi = [
	"value",
	"checked",
	"onChange"
], Ni = { key: 0 }, Pi = { class: "list-filter-actions" }, Fi = { scope: "col" }, Ii = { scope: "col" }, Li = { "data-label": "成员" }, Ri = { class: "tm-cell-stack" }, zi = { class: "tm-cell-primary" }, Bi = ["title"], Vi = { class: "tm-cell-sub" }, Hi = { "data-label": "本地账号" }, Ui = {
	key: 0,
	class: "tm-cell-stack"
}, Wi = { class: "tm-cell-primary" }, Gi = ["onClick"], Ki = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, qi = {
	key: 0,
	class: "tm-cell-sub"
}, Ji = {
	key: 1,
	class: "tm-badge tm-badge--neutral"
}, Yi = { "data-label": "角色" }, Xi = { "data-label": "成员状态" }, Zi = { class: "tm-cell-stack" }, Qi = { class: "tm-cell-primary" }, $i = { class: "tm-cell-sub" }, ea = { "data-label": "加入时间" }, ta = { class: "ui-time" }, na = { "data-label": "最近任务" }, ra = ["onClick"], ia = {
	key: 1,
	class: "tm-cell-sub"
}, aa = { "data-label": "操作" }, oa = { class: "tm-row-actions" }, sa = ["onClick"], ca = ["onClick"], la = {
	key: 2,
	class: "tm-cell-sub"
}, ua = /* @__PURE__ */ t({
	__name: "TeamMembersTab",
	props: {
		api: {},
		teamId: {},
		visible: { type: Boolean },
		callbacks: {}
	},
	setup(e, { expose: t }) {
		let s = e, u = [
			{
				value: "owner",
				label: "所有者"
			},
			{
				value: "admin",
				label: "管理员"
			},
			{
				value: "member",
				label: "成员"
			},
			{
				value: "unknown",
				label: "待核验"
			}
		], x = [
			{
				value: "joined",
				label: "已加入"
			},
			{
				value: "left",
				label: "已退出"
			},
			{
				value: "unconfirmed",
				label: "待确认"
			}
		], S = [
			{
				value: "all",
				label: "全部成员"
			},
			{
				value: "linked",
				label: "已关联本地账号"
			},
			{
				value: "unlinked",
				label: "未关联本地账号"
			}
		], C = c({
			page: 1,
			page_size: 20,
			q: "",
			role: "",
			membership_state: "joined",
			linked: "all"
		}), D = h(""), O = h(null), k = h(!1), A = h(""), j = h([]), M = h(0), re = h({}), { widths: N, total: ie, resize: V, resizeWithKeyboard: H } = P({
			defaults: [
				210,
				140,
				88,
				96,
				156,
				126,
				194
			],
			storageKey: "turb_team_members_column_widths_v2",
			min: 80,
			max: 640
		}), U, W = null, G = 0;
		function q(e) {
			return `tm-badge--${e}`;
		}
		function oe(e, t) {
			let n = re.value[e];
			if (!n) return null;
			let r = n.find((e) => e.value === t);
			return r ? r.count : null;
		}
		let se = b(() => {
			let e = [];
			if (C.q && e.push({
				key: "q",
				label: `关键词：${C.q}`,
				removeLabel: "清除关键词筛选"
			}), C.linked !== "all") {
				let t = S.find((e) => e.value === C.linked)?.label ?? C.linked;
				e.push({
					key: "linked",
					label: `本地账号：${t}`,
					removeLabel: "清除本地账号筛选"
				});
			}
			if (C.role && e.push({
				key: "role",
				label: `角色：${ae(C.role)}`,
				removeLabel: "清除角色筛选"
			}), C.membership_state !== "joined") {
				let t = x.find((e) => e.value === C.membership_state)?.label ?? J(C.membership_state);
				e.push({
					key: "membership_state",
					label: `成员状态：${t}`,
					removeLabel: "恢复默认仅查看已加入"
				});
			}
			return e;
		}), ce = b(() => se.value.length > 0);
		function le(e) {
			e === "q" ? (clearTimeout(U), D.value = "", C.q = "") : e === "linked" ? C.linked = "all" : e === "role" ? C.role = "" : e === "membership_state" && (C.membership_state = "joined"), C.page = 1, Q();
		}
		function X() {
			clearTimeout(U), D.value = "", C.q = "", C.role = "", C.membership_state = "joined", C.linked = "all", C.page = 1, Q();
		}
		function ue(e) {
			C.linked = e, C.page = 1, O.value = null, Q();
		}
		function Z(e) {
			C.role = e, C.page = 1, O.value = null, Q();
		}
		function de(e) {
			C.membership_state = e, C.page = 1, O.value = null, Q();
		}
		function fe() {
			clearTimeout(U), D.value = "", C.q !== "" && (C.q = "", C.page = 1, Q());
		}
		function pe(e) {
			C.page = e, Q();
		}
		function me(e) {
			C.page_size = e, C.page = 1, Q();
		}
		async function Q(e = {}) {
			if (!s.visible || !s.teamId) return;
			W?.abort();
			let t = new AbortController();
			W = t;
			let n = ++G;
			e.silent || (k.value = !0), A.value = "";
			let r = {
				page: C.page,
				page_size: C.page_size,
				include_facets: String(e.includeFacets ?? 1),
				...C.q ? { q: C.q } : {},
				...C.role ? { role: C.role } : {},
				membership_state: C.membership_state || "joined",
				linked: C.linked
			};
			try {
				let e = await s.api.listMembers(s.teamId, r, t.signal);
				if (n !== G) return;
				j.value = e.items, M.value = e.total, e.facets && Object.keys(e.facets).length > 0 && (re.value = e.facets);
			} catch (r) {
				if (t.signal.aborted || n !== G) return;
				let i = r instanceof Error ? r.message : "加载工作区成员失败";
				e.silent || (A.value = i);
			} finally {
				W === t && (W = null), n === G && (k.value = !1);
			}
		}
		return i(D, (e) => {
			clearTimeout(U);
			let t = e.trim();
			t !== C.q && (U = setTimeout(() => {
				C.q = t, C.page = 1, Q();
			}, 250));
		}), i(() => s.teamId, () => {
			C.page = 1, j.value = [], M.value = 0, re.value = {}, Q();
		}, { immediate: !0 }), i(() => s.visible, (e) => {
			e ? Q() : (W?.abort(), W = null, G += 1, k.value = !1);
		}), ee(() => {
			clearTimeout(U), W?.abort();
		}), t({ refresh: () => Q() }), (t, i) => (n(), T("section", fi, [
			l(z, { filtered: ce.value }, {
				actions: r(() => [v("button", {
					type: "button",
					class: "tm-btn ui-refresh-button",
					disabled: k.value,
					onClick: i[2] ||= (e) => void Q()
				}, g(k.value ? "刷新中…" : "刷新"), 9, hi)]),
				default: r(() => [
					v("span", pi, "共 " + g(M.value.toLocaleString()) + " 名成员", 1),
					v("div", mi, [
						i[26] ||= v("svg", {
							class: "tm-search-box__icon",
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [v("circle", {
							cx: "7",
							cy: "7",
							r: "4.5"
						}), v("path", { d: "m10.5 10.5 3 3" })], -1),
						a(v("input", {
							"onUpdate:modelValue": i[0] ||= (e) => D.value = e,
							type: "search",
							"aria-label": "搜索工作区成员",
							placeholder: "搜索邮箱 / 显示名 / 本地 ID",
							onKeydown: i[1] ||= f(te((e) => {
								C.q = D.value.trim(), C.page = 1, Q();
							}, ["prevent"]), ["enter"])
						}, null, 544), [[ne, D.value]]),
						D.value ? (n(), T("button", {
							key: 0,
							type: "button",
							class: "tm-search-box__clear",
							"aria-label": "清空搜索",
							onClick: fe
						}, " × ")) : d("", !0)
					]),
					l(L, {
						items: se.value,
						onRemove: le
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			v("div", {
				class: "ui-table-wrap ui-table-scroll",
				tabindex: "0",
				"aria-label": "成员表格，可横向滚动",
				"aria-busy": k.value
			}, [v("table", {
				class: "ui-table ui-table--sticky-end ui-table--cards",
				style: m({ "--ui-table-width": `${w(ie)}px` })
			}, [
				i[35] ||= v("caption", { class: "ui-sr-only" }, "工作区已同步成员列表", -1),
				v("colgroup", null, [(n(!0), T(p, null, o(w(N), (e, t) => (n(), T("col", {
					key: t,
					style: m({ width: `${e}px` })
				}, null, 4))), 128))]),
				v("thead", null, [v("tr", null, [
					v("th", _i, [i[27] ||= E(" 成员 ", -1), l(F, {
						label: "成员",
						onStart: i[3] ||= (e) => w(V)(0, e),
						onNudge: i[4] ||= (e) => w(H)(0, e)
					})]),
					v("th", vi, [l(I, {
						label: "本地账号",
						active: C.linked !== "all",
						summary: S.find((e) => e.value === C.linked)?.label,
						open: e.visible && O.value === "linked",
						"onUpdate:open": i[7] ||= (e) => O.value = e ? "linked" : null
					}, {
						default: r(() => [v("fieldset", yi, [i[28] ||= v("legend", { class: "ui-sr-only" }, "本地账号关联筛选", -1), (n(), T(p, null, o(S, (e) => v("label", {
							key: e.value,
							class: "list-filter-option"
						}, [
							v("input", {
								type: "radio",
								name: "member-linked",
								value: e.value,
								checked: C.linked === e.value,
								onChange: (t) => ue(e.value)
							}, null, 40, bi),
							v("span", null, g(e.label), 1),
							oe("linked", e.value) === null ? d("", !0) : (n(), T("small", xi, g(oe("linked", e.value)), 1))
						])), 64))]), v("div", Si, [v("button", {
							type: "button",
							onClick: i[5] ||= (e) => ue("all")
						}, "重置"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[6] ||= (e) => O.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(F, {
						label: "本地账号",
						onStart: i[8] ||= (e) => w(V)(1, e),
						onNudge: i[9] ||= (e) => w(H)(1, e)
					})]),
					v("th", Ci, [l(I, {
						label: "角色",
						active: !!C.role,
						summary: C.role ? w(ae)(C.role) : "",
						open: e.visible && O.value === "role",
						"onUpdate:open": i[13] ||= (e) => O.value = e ? "role" : null
					}, {
						default: r(() => [v("fieldset", wi, [
							i[30] ||= v("legend", { class: "ui-sr-only" }, "成员角色筛选", -1),
							v("label", Ti, [v("input", {
								type: "radio",
								name: "member-role",
								value: "",
								checked: !C.role,
								onChange: i[10] ||= (e) => Z("")
							}, null, 40, Ei), i[29] ||= v("span", null, "全部角色", -1)]),
							(n(), T(p, null, o(u, (e) => v("label", {
								key: e.value,
								class: "list-filter-option"
							}, [
								v("input", {
									type: "radio",
									name: "member-role",
									value: e.value,
									checked: C.role === e.value,
									onChange: (t) => Z(e.value)
								}, null, 40, Di),
								v("span", null, g(e.label), 1),
								oe("role", e.value) === null ? d("", !0) : (n(), T("small", Oi, g(oe("role", e.value)), 1))
							])), 64))
						]), v("div", ki, [v("button", {
							type: "button",
							onClick: i[11] ||= (e) => Z("")
						}, "清除"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[12] ||= (e) => O.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(F, {
						label: "角色",
						onStart: i[14] ||= (e) => w(V)(2, e),
						onNudge: i[15] ||= (e) => w(H)(2, e)
					})]),
					v("th", Ai, [l(I, {
						label: "成员状态",
						active: C.membership_state !== "joined",
						summary: x.find((e) => e.value === C.membership_state)?.label,
						open: e.visible && O.value === "membership_state",
						"onUpdate:open": i[18] ||= (e) => O.value = e ? "membership_state" : null
					}, {
						default: r(() => [v("fieldset", ji, [i[31] ||= v("legend", { class: "ui-sr-only" }, "成员状态筛选", -1), (n(), T(p, null, o(x, (e) => v("label", {
							key: e.value,
							class: "list-filter-option"
						}, [
							v("input", {
								type: "radio",
								name: "member-state",
								value: e.value,
								checked: C.membership_state === e.value,
								onChange: (t) => de(e.value)
							}, null, 40, Mi),
							v("span", null, g(e.label), 1),
							oe("membership_state", e.value) === null ? d("", !0) : (n(), T("small", Ni, g(oe("membership_state", e.value)), 1))
						])), 64))]), v("div", Pi, [v("button", {
							type: "button",
							onClick: i[16] ||= (e) => de("joined")
						}, "恢复已加入"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[17] ||= (e) => O.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(F, {
						label: "成员状态",
						onStart: i[19] ||= (e) => w(V)(3, e),
						onNudge: i[20] ||= (e) => w(H)(3, e)
					})]),
					v("th", Fi, [i[32] ||= E(" 加入时间 ", -1), l(F, {
						label: "加入时间",
						onStart: i[21] ||= (e) => w(V)(4, e),
						onNudge: i[22] ||= (e) => w(H)(4, e)
					})]),
					v("th", Ii, [i[33] ||= E(" 最近任务 ", -1), l(F, {
						label: "最近任务",
						onStart: i[23] ||= (e) => w(V)(5, e),
						onNudge: i[24] ||= (e) => w(H)(5, e)
					})]),
					i[34] ||= v("th", { scope: "col" }, "操作", -1)
				])]),
				v("tbody", null, [(n(!0), T(p, null, o(j.value, (t) => (n(), T("tr", { key: t.id }, [
					v("td", Li, [v("div", Ri, [v("div", zi, [v("span", { title: t.email || void 0 }, g(t.email || "未返回"), 9, Bi)]), v("div", Vi, g(t.remote_user_id ? `远端 ID：${t.remote_user_id}` : "—"), 1)])]),
					v("td", Hi, [t.account ? (n(), T("div", Ui, [v("div", Wi, [v("button", {
						type: "button",
						class: "tm-link-btn tm-tabular",
						onClick: (n) => e.callbacks.openAccountDetail(t.account.id)
					}, " #" + g(t.account.id), 9, Gi), t.account.archived ? (n(), T("span", Ki, "已归档")) : d("", !0)]), t.account.email && t.account.email !== t.email ? (n(), T("div", qi, g(t.account.email), 1)) : d("", !0)])) : (n(), T("span", Ji, "外部成员"))]),
					v("td", Yi, [v("span", { class: y(["tm-badge", q(w(K)(t.role))]) }, g(w(ae)(t.role)), 3)]),
					v("td", Xi, [v("div", Zi, [v("div", Qi, [v("span", { class: y(["tm-badge", q(w(Y)(t.membership_state))]) }, g(w(J)(t.membership_state)), 3)]), v("div", $i, g(t.last_verified_at ? `核验 ${e.callbacks.formatDateTime(t.last_verified_at)}` : "待核验"), 1)])]),
					v("td", ea, [v("span", ta, g(t.joined_at ? e.callbacks.formatDateTime(t.joined_at) : "未返回"), 1)]),
					v("td", na, [t.latest_task?.task_id ? (n(), T("button", {
						key: 0,
						type: "button",
						class: "tm-link-btn tm-tabular",
						onClick: (n) => e.callbacks.openTask(t.latest_task.task_id, t.latest_task?.run_id)
					}, " 任务 #" + g(t.latest_task?.task_id), 9, ra)) : (n(), T("span", ia, "—"))]),
					v("td", aa, [v("div", oa, [
						t.account ? (n(), T("button", {
							key: 0,
							type: "button",
							class: "tm-btn tm-btn--sm",
							onClick: (n) => e.callbacks.openAccountDetail(t.account.id)
						}, " 查看本地账号 ", 8, sa)) : d("", !0),
						t.latest_task?.task_id ? (n(), T("button", {
							key: 1,
							type: "button",
							class: "tm-btn tm-btn--sm",
							onClick: (n) => e.callbacks.openTask(t.latest_task.task_id, t.latest_task?.run_id)
						}, " 查看任务 ", 8, ca)) : d("", !0),
						!t.account && !t.latest_task?.task_id ? (n(), T("span", la, "—")) : d("", !0)
					])])
				]))), 128)), j.value.length ? d("", !0) : (n(), _(B, {
					key: 0,
					colspan: 7,
					loading: k.value,
					error: A.value,
					"loading-title": "正在加载工作区成员",
					"loading-text": "读取已同步的工作区成员与本地账号关联关系",
					"error-title": "加载工作区成员失败",
					title: ce.value ? "没有匹配的成员记录" : "暂无已同步成员",
					text: ce.value ? "可调整搜索词或筛选条件后重新查询。" : "点击上方「同步」从工作区拉取最新成员名单。",
					"retry-label": "重试",
					onRetry: i[25] ||= (e) => void Q()
				}, {
					default: r(() => [!k.value && !A.value && ce.value ? (n(), T("button", {
						key: 0,
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: X
					}, " 清除筛选条件 ")) : d("", !0)]),
					_: 1
				}, 8, [
					"loading",
					"error",
					"title",
					"text"
				]))])
			], 4)], 8, gi),
			l(R, {
				page: C.page,
				size: C.page_size,
				total: M.value,
				busy: k.value,
				label: "成员列表分页",
				"onUpdate:page": pe,
				"onUpdate:size": me
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy"
			])
		]));
	}
}), da = {
	class: "tm-detail-nav",
	"aria-label": "Team 详情导航"
}, fa = ["disabled"], pa = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, ma = { class: "tm-banner__copy" }, ha = { class: "tm-row-actions" }, ga = {
	key: 1,
	class: "tm-banner tm-banner--warning",
	role: "alert"
}, _a = { class: "tm-banner__copy" }, va = { class: "tm-row-actions" }, ya = ["disabled"], ba = {
	key: 2,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, xa = { class: "tm-banner__copy" }, Sa = { class: "tm-row-actions" }, Ca = ["disabled"], wa = {
	key: 3,
	class: "tm-hero-card",
	"aria-label": "工作区详情摘要"
}, Ta = { class: "tm-hero-top" }, Ea = { class: "tm-hero-title-group" }, Da = { class: "tm-hero-heading" }, Oa = { class: "tm-hero-name-row" }, ka = {
	key: 0,
	class: "tm-cell-sub"
}, Aa = { class: "tm-hero-meta-row" }, ja = { class: "tm-mono" }, Ma = { key: 1 }, Na = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, Pa = { class: "tm-hero-actions" }, Fa = ["disabled", "title"], Ia = ["disabled"], La = { class: "tm-inline-menu" }, Ra = { class: "tm-inline-menu__panel" }, za = ["disabled"], Ba = { class: "tm-facts-grid" }, Va = { class: "tm-fact-tile" }, Ha = { class: "tm-fact-tile" }, Ua = { class: "tm-fact-tile" }, Wa = { class: "tm-fact-tile__value" }, Ga = { class: "tm-fact-tile" }, Ka = { class: "tm-fact-tile__value" }, qa = {
	key: 0,
	class: "tm-badge__dot"
}, Ja = { class: "tm-fact-tile__sub" }, Ya = { class: "tm-seat-meter" }, Xa = { class: "tm-seat-meter__head" }, Za = { class: "tm-seat-meter__foot" }, Qa = { class: "tm-seat-meter__foot" }, $a = {
	key: 4,
	class: "tm-hero-card",
	"aria-busy": "true"
}, eo = {
	class: "tm-tabs-bar",
	role: "tablist",
	"aria-label": "工作区详情页签"
}, to = { class: "tm-tabs" }, no = ["aria-selected"], ro = { class: "tm-tab-count" }, io = ["aria-selected"], ao = { class: "tm-tab-count" }, oo = /* @__PURE__ */ t({
	__name: "TeamDetailView",
	props: {
		api: {},
		teamId: {},
		section: {},
		visible: { type: Boolean },
		callbacks: {},
		joinRequestId: {}
	},
	emits: [
		"back",
		"update:section",
		"open-edit",
		"open-change-manager",
		"open-join",
		"team-loaded",
		"clear-join-request"
	],
	setup(e, { expose: t, emit: r }) {
		let a = e, o = r, c = S(null), l = h(!1), u = h(""), f = h(!1), te = h(!1), x = h(null), ne = h(null), C = h(null), D = null, O = 0, k = b(() => c.value?.team ?? null), A = b(() => c.value?.actions ?? null), j = b(() => c.value?.permission_verified_at ?? null);
		function M(e) {
			return `tm-badge--${e}`;
		}
		let re = b(() => {
			if (!k.value || !A.value) return !1;
			let e = A.value.join.reason_code;
			return e === "team_permission_denied" || e === "team_auth_required";
		}), N = b(() => A.value?.join.reason_code ? H(A.value.join.reason_code) : "当前管理母号缺少管理权限或登录态已失效，暂不可执行邀请操作。"), P = b(() => {
			let e = A.value?.join;
			return !e || !e.enabled && e.reason_code !== "team_limit_required";
		}), F = b(() => {
			let e = A.value?.join;
			return e ? e.enabled ? "从现有账号选择成员并自动邀请入组" : e.reason_code === "team_limit_required" ? "当前未返回已购席位，点击可先配置本地上限或选人并设置上限" : H(e.reason_code) : "正在读取工作区操作状态";
		}), I = b(() => f.value || !k.value || k.value.last_sync_status === "queued" || k.value.last_sync_status === "running" ? !0 : A.value ? !A.value.sync.enabled : !1), L = b(() => k.value ? ge(k.value) : null);
		function R() {
			let e = x.value;
			e && e.querySelectorAll("details.tm-inline-menu[open]").forEach((e) => {
				e.open = !1;
			});
		}
		function ie(e) {
			(e.target instanceof Element ? e.target : null)?.closest("details.tm-inline-menu") || R();
		}
		async function z(e = {}) {
			if (!a.visible || !a.teamId) return;
			D?.abort();
			let t = new AbortController();
			D = t;
			let n = ++O;
			e.silent || (l.value = !0), u.value = "";
			try {
				let e = await a.api.detail(a.teamId, t.signal);
				if (n !== O) return;
				c.value = e, o("team-loaded", e.team);
			} catch (r) {
				if (t.signal.aborted || n !== O) return;
				let i = r instanceof Error ? r.message : "加载工作区详情失败";
				e.silent && c.value || (u.value = i);
			} finally {
				D === t && (D = null), n === O && (l.value = !1);
			}
		}
		async function B() {
			if (k.value && !I.value) {
				f.value = !0;
				try {
					let e = await a.api.syncTeam(k.value.id);
					a.callbacks.notify(e.reused ? "当前已有进行中的同步任务，正在追踪进度" : "已启动工作区同步任务"), await z({ silent: !0 });
				} catch (e) {
					a.callbacks.notify(e instanceof Error ? e.message : "同步任务提交失败");
				} finally {
					f.value = !1;
				}
			}
		}
		async function V() {
			if (k.value && !te.value) {
				R(), te.value = !0;
				try {
					let e = await a.api.reverifyTeam(k.value.id);
					a.callbacks.notify("已提交管理权限重新核验任务"), e.task_id && await z({ silent: !0 });
				} catch (e) {
					a.callbacks.notify(e instanceof Error ? e.message : "重新核验权限提交失败");
				} finally {
					te.value = !1;
				}
			}
		}
		function G() {
			k.value && (R(), a.callbacks.openTasksForTeam(k.value.id, U(k.value)));
		}
		function q() {
			k.value && (R(), o("open-edit", k.value));
		}
		function ce() {
			k.value && (R(), o("open-change-manager", k.value));
		}
		function J() {
			z({ silent: !1 }), a.section === "members" ? ne.value?.refresh() : C.value?.refresh();
		}
		return $n({
			visible: () => a.visible,
			shouldPoll: () => Se(k.value),
			onPoll: async () => {
				await z({ silent: !0 }), a.section === "members" && await ne.value?.refresh();
			},
			intervalMs: 3e3
		}), i(() => a.teamId, () => {
			c.value = null, u.value = "", z();
		}, { immediate: !0 }), s(() => {
			document.addEventListener("click", ie);
		}), i(() => a.visible, (e) => {
			e ? z() : (D?.abort(), D = null, O += 1, l.value = !1);
		}), ee(() => {
			D?.abort(), document.removeEventListener("click", ie);
		}), t({
			refresh: (e) => z(e),
			refreshAll: J,
			updateTeamSnapshot: (e) => {
				c.value && c.value.team.id === e.id && (c.value = {
					...c.value,
					team: e
				}), z({ silent: !0 });
			}
		}), (t, r) => (n(), T("div", {
			ref_key: "rootRef",
			ref: x,
			class: "tm-root"
		}, [
			v("nav", da, [v("button", {
				type: "button",
				class: "tm-back-btn",
				onClick: r[0] ||= (e) => o("back")
			}, " ← 返回工作区列表 "), v("button", {
				type: "button",
				class: "tm-btn tm-btn--ghost tm-btn--sm",
				disabled: l.value,
				onClick: J
			}, g(l.value ? "刷新中…" : "刷新详情"), 9, fa)]),
			u.value && !k.value ? (n(), T("div", pa, [v("div", ma, [r[12] ||= v("strong", null, "加载工作区详情失败：", -1), v("span", null, g(u.value), 1)]), v("div", ha, [v("button", {
				type: "button",
				class: "tm-btn tm-btn--sm",
				onClick: r[1] ||= (e) => void z()
			}, "重试")])])) : d("", !0),
			k.value && k.value.last_sync_status === "failed" ? (n(), T("div", ga, [v("div", _a, [r[13] ||= v("strong", null, "最近一次同步失败：", -1), v("span", null, " 同步详情请查看相关任务。 以下展示上次成功同步快照（" + g(k.value.last_synced_at ? e.callbacks.formatDateTime(k.value.last_synced_at) : "暂无成功快照") + "）。 ", 1)]), v("div", va, [v("button", {
				type: "button",
				class: "tm-btn tm-btn--sm",
				disabled: I.value,
				onClick: r[2] ||= (e) => void B()
			}, " 立即重新同步 ", 8, ya)])])) : d("", !0),
			k.value && re.value ? (n(), T("div", ba, [v("div", xa, [r[14] ||= v("strong", null, "管理权限异常：", -1), v("span", null, g(N.value), 1)]), v("div", Sa, [v("button", {
				type: "button",
				class: "tm-btn tm-btn--sm",
				disabled: te.value || (A.value ? !A.value.reverify.enabled : !1),
				onClick: r[3] ||= (e) => void V()
			}, g(te.value ? "核验提交中…" : "重新核验权限"), 9, Ca), v("button", {
				type: "button",
				class: "tm-btn tm-btn--sm tm-btn--danger",
				onClick: ce
			}, " 更换管理母号 ")])])) : d("", !0),
			k.value ? (n(), T("section", wa, [v("div", Ta, [v("div", Ea, [v("div", {
				class: "tm-workspace-avatar tm-workspace-avatar--lg",
				style: m({ "--tm-hue": String(w(be)(k.value.workspace_id)) }),
				"aria-hidden": "true"
			}, g(w(xe)(w(U)(k.value))), 5), v("div", Da, [v("div", Oa, [
				v("h2", null, g(w(U)(k.value)), 1),
				k.value.display_name && k.value.name && k.value.display_name !== k.value.name ? (n(), T("span", ka, " 原名：" + g(k.value.name), 1)) : d("", !0),
				v("button", {
					type: "button",
					class: "tm-btn tm-btn--ghost tm-btn--sm",
					title: "编辑工作区备注别名与本地人数上限",
					onClick: q
				}, " 编辑别名与上限 ")
			]), v("div", Aa, [
				v("span", ja, g(k.value.workspace_id), 1),
				r[16] ||= v("span", null, "·", -1),
				v("span", null, [r[15] ||= E(" 管理母号： ", -1), k.value.manager_account.id ? (n(), T("button", {
					key: 0,
					type: "button",
					class: "tm-link-btn",
					onClick: r[4] ||= (t) => e.callbacks.openAccountDetail(k.value.manager_account.id)
				}, g(k.value.manager_account.email || `#${k.value.manager_account.id}`), 1)) : (n(), T("span", Ma, g(k.value.manager_account.email || "—"), 1))]),
				v("span", { class: y(["tm-badge", M(w(K)(k.value.role))]) }, g(w(ae)(k.value.role)), 3),
				k.value.manager_account.archived ? (n(), T("span", Na, "已归档")) : d("", !0),
				r[17] ||= v("span", null, "·", -1),
				v("span", null, " 权限核验：" + g(j.value ? e.callbacks.formatDateTime(j.value) : "待核验"), 1)
			])])]), v("div", Pa, [
				v("button", {
					type: "button",
					class: "tm-btn tm-btn--primary",
					disabled: P.value,
					title: F.value,
					onClick: r[5] ||= (e) => o("open-join", k.value)
				}, " 加入账号 ", 8, Fa),
				v("button", {
					type: "button",
					class: "tm-btn",
					disabled: I.value,
					title: "同步工作区成员、邀请与席位",
					onClick: r[6] ||= (e) => void B()
				}, g(f.value || k.value.last_sync_status === "queued" || k.value.last_sync_status === "running" ? "同步中…" : "同步"), 9, Ia),
				v("details", La, [r[18] ||= v("summary", { "aria-label": "工作区更多操作" }, "···", -1), v("div", Ra, [
					v("button", {
						type: "button",
						onClick: G
					}, "查看相关任务"),
					v("button", {
						type: "button",
						onClick: q
					}, "设置别名与人数上限"),
					v("button", {
						type: "button",
						onClick: ce
					}, "更换管理母号"),
					v("button", {
						type: "button",
						disabled: te.value || (A.value ? !A.value.reverify.enabled : !1),
						onClick: r[7] ||= (e) => void V()
					}, g(te.value ? "权限核验提交中…" : "重新核验权限"), 9, za)
				])])
			])]), v("div", Ba, [
				v("div", Va, [
					r[19] ||= v("div", { class: "tm-fact-tile__label" }, [v("span", null, "已确认成员")], -1),
					v("div", { class: y(["tm-fact-tile__value", { "is-null": k.value.confirmed_member_count === null }]) }, g(w($)(k.value.confirmed_member_count, "待同步")), 3),
					r[20] ||= v("div", { class: "tm-fact-tile__sub" }, "远端已确认（含母号）", -1)
				]),
				v("div", Ha, [
					r[21] ||= v("div", { class: "tm-fact-tile__label" }, [v("span", null, "待接受邀请")], -1),
					v("div", { class: y(["tm-fact-tile__value", { "is-null": k.value.pending_invite_count === null }]) }, g(w($)(k.value.pending_invite_count, "待同步")), 3),
					r[22] ||= v("div", { class: "tm-fact-tile__sub" }, "远端有效待接受", -1)
				]),
				v("div", Ua, [
					r[23] ||= v("div", { class: "tm-fact-tile__label" }, [v("span", null, "本系统处理中")], -1),
					v("div", Wa, g(w($)(k.value.processing_count, "—")), 1),
					r[24] ||= v("div", { class: "tm-fact-tile__sub" }, "独立计数，勿直接相加", -1)
				]),
				v("div", Ga, [
					r[25] ||= v("div", { class: "tm-fact-tile__label" }, [v("span", null, "同步状态")], -1),
					v("div", Ka, [v("span", { class: y(["tm-badge", M(w(se)(k.value.last_sync_status))]) }, [k.value.last_sync_status === "queued" || k.value.last_sync_status === "running" ? (n(), T("span", qa)) : d("", !0), E(" " + g(w(oe)(k.value.last_sync_status)), 1)], 2)]),
					v("div", Ja, g(k.value.last_synced_at ? e.callbacks.formatDateTime(k.value.last_synced_at) : "待同步"), 1)
				]),
				v("div", Ya, [
					v("div", Xa, [r[26] ||= v("span", { class: "tm-seat-meter__title" }, "席位与本地上限", -1), L.value ? (n(), T("span", {
						key: 0,
						class: y(["tm-badge", M(L.value.tone)])
					}, " 加入前核算容量 ", 2)) : d("", !0)]),
					v("div", Za, [v("span", null, " 已占待预检 / 有效上限 " + g(w($)(w(W)(k.value), "未设置")), 1), r[27] ||= v("span", null, " 可用余量待预检 ", -1)]),
					v("div", Qa, [v("span", null, "已购 " + g(w($)(k.value.purchased_seats, "未返回", " 席")), 1), v("span", null, "本地上限 " + g(w($)(k.value.planned_member_limit, "未设置", " 人")), 1)])
				])
			])])) : l.value ? (n(), T("section", $a, [...r[28] ||= [v("div", {
				class: "ui-table-state",
				style: { "min-height": "120px" }
			}, [v("span", {
				class: "ui-spinner",
				"aria-hidden": "true"
			}), v("strong", null, "正在加载工作区详情…")], -1)]])) : d("", !0),
			v("div", eo, [v("div", to, [v("button", {
				type: "button",
				role: "tab",
				class: y(["tm-tab-btn", { "is-active": e.section === "members" }]),
				"aria-selected": e.section === "members",
				onClick: r[8] ||= (e) => o("update:section", "members")
			}, [r[29] ||= v("span", null, "成员", -1), v("span", ro, g(k.value ? w($)(k.value.confirmed_member_count, "待同步") : "—"), 1)], 10, no), v("button", {
				type: "button",
				role: "tab",
				class: y(["tm-tab-btn", { "is-active": e.section === "invitations" }]),
				"aria-selected": e.section === "invitations",
				onClick: r[9] ||= (e) => o("update:section", "invitations")
			}, [r[30] ||= v("span", null, "邀请", -1), v("span", ao, [k.value ? (n(), T(p, { key: 0 }, [E(g((k.value.processing_count ?? 0) > 0 ? `${w($)(k.value.pending_invite_count, "待同步")} · 处理中 ${k.value.processing_count}` : w($)(k.value.pending_invite_count, "待同步")), 1)], 64)) : (n(), T(p, { key: 1 }, [E("—")], 64))])], 10, io)])]),
			e.section === "members" ? (n(), _(ua, {
				key: 5,
				ref_key: "membersTabRef",
				ref: ne,
				api: e.api,
				"team-id": e.teamId,
				visible: e.visible && e.section === "members",
				callbacks: e.callbacks
			}, null, 8, [
				"api",
				"team-id",
				"visible",
				"callbacks"
			])) : (n(), _(di, {
				key: 6,
				ref_key: "invitationsTabRef",
				ref: C,
				api: e.api,
				"team-id": e.teamId,
				visible: e.visible && e.section === "invitations",
				callbacks: e.callbacks,
				"join-request-id": e.joinRequestId,
				onRefreshTeam: r[10] ||= (e) => void z({ silent: !0 }),
				onClearJoinRequest: r[11] ||= (e) => o("clear-join-request")
			}, null, 8, [
				"api",
				"team-id",
				"visible",
				"callbacks",
				"join-request-id"
			]))
		], 512));
	}
}), so = ["aria-busy"], co = { class: "tm-dialog__head" }, lo = { class: "tm-dialog__desc" }, uo = { class: "tm-mono" }, fo = ["disabled"], po = { class: "tm-banner tm-banner--info" }, mo = { class: "tm-banner__copy" }, ho = { class: "tm-field" }, go = ["placeholder", "disabled"], _o = { class: "tm-field__hint" }, vo = { class: "tm-field" }, yo = ["disabled"], bo = {
	key: 0,
	class: "tm-banner tm-banner--warning"
}, xo = {
	key: 1,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, So = { class: "tm-banner__copy" }, Co = {
	class: "tm-dialog__foot",
	style: { margin: "4px -22px -18px" }
}, wo = { class: "tm-field__hint" }, To = { class: "tm-dialog__foot-right" }, Eo = ["disabled"], Do = ["disabled"], Oo = /* @__PURE__ */ t({
	__name: "TeamEditModal",
	props: {
		open: { type: Boolean },
		api: {},
		team: {},
		visible: { type: Boolean }
	},
	emits: [
		"close",
		"updated",
		"conflict",
		"notify"
	],
	setup(e, { emit: t }) {
		let r = e, o = t, s = b(() => r.open && r.visible), c = h();
		re(c, () => s.value, () => r.visible);
		let l = h(""), u = h(""), f = h(!1), m = h(""), _ = h(!1), y = 0;
		i([() => r.open, () => r.team?.id], () => {
			++y, f.value = !1, m.value = "", _.value = !1;
		}, { flush: "sync" }), ee(() => {
			++y;
		});
		let x = b(() => {
			let e = r.team?.purchased_seats;
			return e == null || !Number.isFinite(e) ? "未返回" : `已购 ${e} 席`;
		});
		function S() {
			l.value = r.team?.display_name ?? "", u.value = r.team?.planned_member_limit !== null && r.team?.planned_member_limit !== void 0 ? String(r.team.planned_member_limit) : "", m.value = "", _.value = !1;
		}
		i([
			() => r.open,
			() => r.team?.id,
			() => r.team?.revision
		], ([e]) => {
			e && S();
		}, { immediate: !0 });
		function C() {
			let e = u.value.trim();
			if (!e) return {
				ok: !0,
				value: null
			};
			if (!/^[1-9]\d*$/.test(e)) return {
				ok: !1,
				message: "本地计划人数上限必须为正整数（不能为 0），或留空清除上限"
			};
			let t = Number(e);
			return !Number.isSafeInteger(t) || t <= 0 ? {
				ok: !1,
				message: "本地计划人数上限超出有效整数范围"
			} : {
				ok: !0,
				value: t
			};
		}
		async function w() {
			let e = r.team;
			if (!r.open || !e || f.value) return;
			m.value = "", _.value = !1;
			let t = l.value.trim();
			if (t.length > 120) {
				m.value = "工作区别名不能超过 120 个字符";
				return;
			}
			let n = C();
			if (!n.ok) {
				m.value = n.message;
				return;
			}
			let i = y, a = () => i === y && r.open && r.team?.id === e.id;
			f.value = !0;
			try {
				let i = await r.api.updateTeam(e.id, {
					expected_revision: e.revision,
					display_name: t || null,
					planned_member_limit: n.value
				});
				if (!a()) return;
				o("notify", "工作区设置已保存"), o("updated", i.team), o("close");
			} catch (e) {
				if (!a()) return;
				if (e instanceof M) {
					if (e.code === "team_revision_conflict" || e.code === "revision_conflict" || e.status === 409) {
						_.value = !0, m.value = "工作区状态已变更（版本冲突），请关闭后刷新最新信息再重新编辑", o("conflict");
						return;
					}
					m.value = e.message || H(e.code);
				} else m.value = e instanceof Error ? e.message : "保存工作区设置失败";
			} finally {
				a() && (f.value = !1);
			}
		}
		function D() {
			f.value || o("close");
		}
		function O(e) {
			let t = c.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(n.width === 0 && n.height === 0 || e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && D();
		}
		return (t, r) => (n(), T("dialog", {
			ref_key: "dialogRef",
			ref: c,
			class: "tm-dialog",
			"aria-labelledby": "teamEditDialogTitle",
			"aria-busy": f.value,
			onCancel: te(D, ["prevent"]),
			onClick: O
		}, [v("div", co, [v("div", null, [
			r[3] ||= v("p", { class: "tm-dialog__kicker" }, "TEAM SETTINGS", -1),
			r[4] ||= v("h3", {
				id: "teamEditDialogTitle",
				class: "tm-dialog__title"
			}, "编辑工作区设置", -1),
			v("p", lo, [e.team ? (n(), T(p, { key: 0 }, [
				r[2] ||= E(" 工作区：", -1),
				v("strong", uo, g(e.team.workspace_id), 1),
				E(" · 远端名称「" + g(e.team.name || "未返回") + "」 ", 1)
			], 64)) : d("", !0)])
		]), v("button", {
			type: "button",
			class: "tm-dialog__close",
			"aria-label": "关闭编辑弹窗",
			disabled: f.value,
			onClick: D
		}, " × ", 8, fo)]), v("form", {
			class: "tm-dialog__body",
			novalidate: "",
			onSubmit: te(w, ["prevent"])
		}, [
			v("div", po, [v("div", mo, [
				v("span", null, [r[5] ||= E(" 当前远端已购席位：", -1), v("strong", null, g(x.value), 1)]),
				r[6] ||= v("span", null, "·", -1),
				r[7] ||= v("span", null, "仅使用已购剩余席位，与已购席位共同取较小值。", -1)
			])]),
			v("label", ho, [
				r[8] ||= v("span", { class: "tm-field__label" }, "工作区本地显示别名（display_name）", -1),
				a(v("input", {
					"onUpdate:modelValue": r[0] ||= (e) => l.value = e,
					type: "text",
					maxlength: "120",
					placeholder: e.team?.name || "留空将恢复远端工作区名称",
					disabled: f.value
				}, null, 8, go), [[ne, l.value]]),
				v("span", _o, " 留空将清除自定义别名，恢复展示远端工作区名称「" + g(e.team?.name || "未返回") + "」。 ", 1)
			]),
			v("label", vo, [
				r[9] ||= v("span", { class: "tm-field__label" }, "本地计划人数上限（planned_member_limit）", -1),
				a(v("input", {
					"onUpdate:modelValue": r[1] ||= (e) => u.value = e,
					type: "text",
					inputmode: "numeric",
					placeholder: "输入正整数（含管理母号），或留空清除上限",
					disabled: f.value
				}, null, 8, yo), [[ne, u.value]]),
				r[10] ||= v("span", { class: "tm-field__hint" }, " 仅接受正整数（含管理母号）或留空清除上限。下调上限不会移除现有成员或撤回邀请，仅拦截后续新增占位。 ", -1)
			]),
			e.team && (e.team.purchased_seats === null || e.team.purchased_seats === void 0) ? (n(), T("div", bo, [...r[11] ||= [v("div", { class: "tm-banner__copy" }, " 当前远端未返回已购席位；若清除本地计划人数上限，后续批量加入新成员将被拦截，直到补充上限或同步出已购席位。 ", -1)]])) : d("", !0),
			m.value ? (n(), T("div", xo, [v("div", So, g(m.value), 1)])) : d("", !0),
			v("div", Co, [v("span", wo, [e.team ? (n(), T(p, { key: 0 }, [E("当前修订版本 v" + g(e.team.revision), 1)], 64)) : d("", !0)]), v("div", To, [v("button", {
				type: "button",
				class: "tm-btn",
				disabled: f.value,
				onClick: D
			}, g(_.value ? "关闭并刷新" : "取消"), 9, Eo), v("button", {
				type: "submit",
				class: "tm-btn tm-btn--primary",
				disabled: f.value || !e.team
			}, g(f.value ? "保存中…" : "保存修改"), 9, Do)])])
		], 32)], 40, so));
	}
}), ko = ["aria-busy"], Ao = { class: "tm-dialog__head" }, jo = { class: "tm-dialog__kicker" }, Mo = {
	id: "teamJoinDialogTitle",
	class: "tm-dialog__title"
}, No = { class: "tm-dialog__desc" }, Po = { class: "tm-mono" }, Fo = ["disabled"], Io = {
	key: 0,
	class: "tm-dialog__body"
}, Lo = {
	key: 0,
	class: "tm-field"
}, Ro = ["value", "disabled"], zo = { value: "" }, Bo = ["value"], Vo = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Ho = { class: "tm-banner__copy" }, Uo = {
	key: 1,
	class: "tm-banner tm-banner--info",
	role: "status"
}, Wo = {
	key: 2,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Go = { class: "tm-banner__copy" }, Ko = { class: "tm-field" }, qo = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "8px",
	"flex-wrap": "wrap"
} }, Jo = { class: "tm-field__label" }, Yo = { class: "tm-field__hint" }, Xo = { class: "tm-preview-grid" }, Zo = { class: "tm-preview-stat is-highlight" }, Qo = { class: "tm-preview-stat" }, $o = { class: "tm-preview-stat" }, es = { class: "tm-preview-stat" }, ts = { class: "tm-preview-stat" }, ns = { class: "tm-preview-stat" }, rs = { class: "tm-preview-stat" }, is = { class: "tm-seat-meter__head" }, as = { class: "tm-badge tm-badge--neutral" }, os = {
	class: "tm-seat-meter__track",
	"aria-hidden": "true"
}, ss = {
	class: "tm-seat-meter__foot",
	style: { "flex-wrap": "wrap" }
}, cs = {
	key: 0,
	class: "tm-banner tm-banner--warning",
	style: {
		"flex-direction": "column",
		"align-items": "stretch"
	},
	role: "alert"
}, ls = { style: {
	display: "flex",
	"align-items": "center",
	gap: "8px",
	"flex-wrap": "wrap"
} }, us = ["disabled"], ds = ["disabled"], fs = {
	key: 0,
	style: {
		color: "var(--ui-color-danger, #b91c1c)",
		"font-size": "12px"
	}
}, ps = {
	key: 1,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, ms = { class: "tm-banner__copy" }, hs = {
	key: 2,
	class: "tm-banner tm-banner--warning",
	role: "status"
}, gs = {
	key: 3,
	class: "tm-banner tm-banner--info"
}, _s = {
	key: 4,
	class: "tm-banner tm-banner--warning",
	role: "status"
}, vs = { class: "tm-banner__copy" }, ys = {
	key: 5,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, bs = { class: "tm-banner__copy" }, xs = {
	key: 1,
	class: "tm-dialog__body"
}, Ss = {
	class: "tm-banner tm-banner--info",
	role: "status"
}, Cs = { class: "tm-banner__copy" }, ws = { class: "tm-mono" }, Ts = { class: "tm-preview-grid" }, Es = { class: "tm-preview-stat" }, Ds = { class: "tm-preview-stat is-highlight" }, Os = { class: "tm-preview-stat" }, ks = { class: "tm-preview-stat" }, As = { class: "tm-preview-stat" }, js = ["disabled"], Ms = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Ns = { class: "tm-banner__copy" }, Ps = ["aria-busy"], Fs = {
	key: 0,
	style: {
		padding: "18px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, Is = {
	class: "tm-cell-stack",
	style: {
		"min-width": "0",
		flex: "1"
	}
}, Ls = { class: "tm-cell-primary" }, Rs = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, zs = { class: "tm-cell-sub" }, Bs = { style: {
	display: "flex",
	"align-items": "center",
	gap: "8px",
	flex: "none"
} }, Vs = ["onClick"], Hs = {
	key: 1,
	style: {
		display: "flex",
		"align-items": "center",
		"justify-content": "flex-end",
		gap: "8px"
	}
}, Us = ["disabled"], Ws = { class: "tm-field__hint tm-tabular" }, Gs = ["disabled"], Ks = { class: "tm-dialog__foot" }, qs = { class: "tm-dialog__foot-right" }, Js = ["disabled"], Ys = ["disabled"], Xs = { class: "tm-field__hint" }, Zs = { class: "tm-dialog__foot-right" }, Qs = /* @__PURE__ */ t({
	__name: "TeamJoinModal",
	props: {
		open: { type: Boolean },
		api: {},
		initialTeam: {},
		target: {},
		visible: { type: Boolean },
		formatDateTime: { type: Function }
	},
	emits: [
		"close",
		"submitted",
		"openTask",
		"openTeamDetail",
		"teamUpdated",
		"notify"
	],
	setup(e, { emit: t }) {
		let r = e, s = t, c = h();
		re(c, () => r.open && r.visible, () => r.visible);
		let l = h("preview"), u = h([]), f = h(!1), _ = h(""), x = h(""), S = h(null), C = h(null), D = h(!1), O = h(""), k = h(""), A = h(!1), j = h(""), N = h(!1), P = h(""), F = h(""), I = h(null), L = h(null), R = h(!1), ie = h(""), z = null, B = null, V = null, U = null, W = 0, G = b(() => r.open && r.visible), ae = b(() => !r.initialTeam), K = b(() => S.value?.id || x.value || r.target?.targetTeamId || ""), q = b(() => C.value?.counts.eligible_count ?? 0), oe = b(() => N.value || A.value || D.value || !S.value || !C.value ? !1 : C.value.capacity.can_submit && q.value > 0), se = b(() => {
			let e = C.value?.capacity;
			return !e || e.effective_limit === null || e.effective_limit <= 0 || e.occupied_count === null ? 0 : Math.min(100, Math.max(0, Math.round(e.occupied_count / e.effective_limit * 100)));
		}), ce = b(() => {
			let e = C.value?.capacity;
			if (!e || e.effective_limit === null || e.effective_limit <= 0) return 0;
			let t = Math.round((e.additional_required ?? 0) / e.effective_limit * 100);
			return Math.min(Math.max(0, 100 - se.value), Math.max(0, t));
		}), J = b(() => {
			let e = C.value?.capacity;
			return !e || e.available_count === null || e.additional_required === null ? null : Math.max(0, e.available_count - e.additional_required);
		}), Y = b(() => {
			let e = C.value?.capacity, t = e?.occupied_count, n = e?.effective_limit, r = e?.additional_required;
			return typeof t == "number" && Number.isFinite(t) && typeof n == "number" && Number.isFinite(n) && typeof r == "number" && Number.isFinite(r) && r > 0 && t + r > n;
		}), le = b(() => {
			let e = C.value?.capacity;
			return e && (e.blocking_reason_code === "team_limit_required" || e.available_count !== null && e.available_count <= 1) ? "is-warn" : "";
		}), X = b(() => L.value?.page ?? 1), ue = b(() => Math.max(1, Math.ceil((L.value?.total ?? I.value?.counts.unique_count ?? 0) / (L.value?.page_size ?? 20))));
		function Z(e) {
			return e instanceof DOMException && e.name === "AbortError";
		}
		function pe() {
			z && (z.abort(), z = null, f.value = !1), B && (B.abort(), B = null, D.value = !1), V && (V.abort(), V = null, R.value = !1), U && (U.abort(), U = null, A.value = !1);
		}
		function me() {
			W++, pe(), l.value = "preview", u.value = [], f.value = !1, _.value = "", x.value = "", S.value = null, C.value = null, D.value = !1, O.value = "", k.value = "", A.value = !1, j.value = "", N.value = !1, P.value = "", F.value = "", I.value = null, L.value = null, R.value = !1, ie.value = "";
		}
		function Q() {
			if (!r.target) return null;
			if (r.target.mode === "explicit") {
				let e = [...r.target.accountIds || []];
				if (!e.length) return null;
				let t = r.target.expectedEmails;
				return {
					account_ids: e,
					...t && Object.keys(t).length ? { expected_emails: t } : {}
				};
			}
			return !r.target.selectionId || !r.target.selectionRevision ? null : {
				selection_id: r.target.selectionId,
				selection_revision: r.target.selectionRevision
			};
		}
		async function ge(e) {
			let t = Q();
			if (!G.value || !e || !t) return;
			B && B.abort();
			let n = new AbortController();
			B = n, D.value = !0, O.value = "";
			try {
				let i = await r.api.previewJoin(e, t, n.signal);
				if (n.signal.aborted || !G.value) return;
				C.value = i;
			} catch (e) {
				if (Z(e) || n.signal.aborted) return;
				C.value = null, O.value = e instanceof M || e instanceof Error ? e.message : "生成加入预览失败";
			} finally {
				B === n && (B = null, D.value = !1);
			}
		}
		async function _e(e) {
			if (!e) return;
			x.value = e;
			let t = u.value.find((t) => t.id === e);
			if (t) {
				S.value = t, await ge(e);
				return;
			}
			z && z.abort();
			let n = new AbortController();
			z = n, f.value = !0, _.value = "";
			try {
				let t = await r.api.detail(e, n.signal);
				if (n.signal.aborted || !G.value) return;
				S.value = t.team, await ge(t.team.id);
			} catch (e) {
				if (Z(e) || n.signal.aborted) return;
				_.value = e instanceof M || e instanceof Error ? e.message : "获取目标 Team 信息失败";
			} finally {
				z === n && (z = null, f.value = !1);
			}
		}
		async function ve() {
			if (!G.value) return;
			z && z.abort();
			let e = new AbortController();
			z = e, f.value = !0, _.value = "";
			try {
				let t = await r.api.list({
					page: 1,
					page_size: 50,
					include_facets: "0"
				}, e.signal);
				if (e.signal.aborted || !G.value) return;
				u.value = t.items, t.items.length === 1 && (x.value = t.items[0].id, S.value = t.items[0], await ge(t.items[0].id));
			} catch (t) {
				if (Z(t) || e.signal.aborted) return;
				_.value = t instanceof M || t instanceof Error ? t.message : "加载可选 Team 列表失败";
			} finally {
				z === e && (z = null, f.value = !1);
			}
		}
		async function ye() {
			me(), G.value && r.target && (r.initialTeam ? (S.value = r.initialTeam, x.value = r.initialTeam.id, await ge(r.initialTeam.id)) : r.target.targetTeamId ? await _e(r.target.targetTeamId) : await ve());
		}
		function be(e) {
			if (A.value || N.value) return;
			let t = e.target.value;
			C.value = null, O.value = "", P.value = "", F.value = "", t ? _e(t) : (x.value = "", S.value = null);
		}
		async function xe() {
			if (!G.value || !S.value || A.value) return;
			j.value = "";
			let e = k.value.trim();
			if (!/^[1-9]\d*$/.test(e)) {
				j.value = "请输入大于 0 的正整数作为本地计划人数上限";
				return;
			}
			let t = Number(e);
			if (!Number.isSafeInteger(t) || t <= 0) {
				j.value = "本地计划人数上限数值超出有效范围";
				return;
			}
			let n = S.value.id, i = S.value.revision, a = W, o = new AbortController();
			U = o;
			let c = () => !o.signal.aborted && a === W && G.value && S.value?.id === n && x.value === n;
			A.value = !0;
			try {
				let e = await r.api.updateTeam(n, {
					expected_revision: i,
					planned_member_limit: t
				}, o.signal);
				if (!c()) return;
				if (e.team.id !== n) throw Error("保存响应的工作区与当前目标不一致，请刷新后重试");
				S.value = e.team;
				let a = u.value.findIndex((t) => t.id === e.team.id);
				a >= 0 && u.value.splice(a, 1, e.team), s("teamUpdated", e.team), s("notify", "本地计划人数上限已更新，正在重新核算席位"), await ge(n);
			} catch (e) {
				if (Z(e) || !c()) return;
				j.value = e instanceof M || e instanceof Error ? e.message : "设置本地计划人数上限失败";
			} finally {
				U === o && (U = null, A.value = !1);
			}
		}
		async function Se() {
			if (!oe.value || !S.value || !C.value) return;
			let e = Q();
			if (!e) return;
			let t = S.value.id, n = W;
			N.value = !0, P.value = "", F.value = "";
			try {
				let i = await r.api.submitJoin(t, e);
				if (s("submitted", i, t), n !== W) return;
				I.value = i, l.value = "receipt", s("notify", "批量加入请求已持久受理，逐项结果见回执"), await Ce(1);
			} catch (e) {
				if (n !== W) return;
				if (e instanceof M) {
					if (e.status === 409 && (e.code === "team_revision_conflict" || e.code === "revision_conflict")) {
						F.value = "工作区状态已变更，已自动重新核算最新席位与名单，请二次确认后提交。", await _e(t);
						return;
					}
					if (e.status === 409 && e.code === "team_limit_required") {
						F.value = "需要先配置本地计划人数上限，已重新加载席位核算。", await ge(t);
						return;
					}
					P.value = e.message || H(e.code);
				} else P.value = e instanceof Error ? e.message : "发起加入请求失败";
			} finally {
				n === W && (N.value = !1);
			}
		}
		async function Ce(e) {
			if (!G.value || !I.value || R.value || e < 1 || L.value && e > ue.value) return;
			let t = I.value.team_id, n = I.value.id;
			V && V.abort();
			let i = new AbortController();
			V = i, R.value = !0, ie.value = "";
			try {
				let a = await r.api.getJoinRequest(t, n, {
					page: e,
					page_size: L.value?.page_size ?? 20
				}, i.signal);
				if (i.signal.aborted || !G.value || I.value?.id !== n) return;
				I.value = a.request, L.value = a;
			} catch (e) {
				if (Z(e) || i.signal.aborted) return;
				ie.value = e instanceof Error ? e.message : "加载回执明细失败";
			} finally {
				V === i && (V = null, R.value = !1);
			}
		}
		$n({
			visible: () => G.value && l.value === "receipt",
			shouldPoll: () => !!(I.value && [
				"preparing",
				"queued",
				"running",
				"waiting"
			].includes(I.value.status)),
			onPoll: () => Ce(X.value)
		});
		function we(e) {
			return e === "pending" ? {
				label: "待处理",
				tone: "neutral"
			} : e === "accepted" ? {
				label: "已受理",
				tone: "success"
			} : e === "reused" ? {
				label: "复用进行中",
				tone: "active"
			} : e === "failed" ? {
				label: "受理失败",
				tone: "danger"
			} : {
				label: "已跳过",
				tone: "warning"
			};
		}
		function Te(e) {
			return e === "preparing" ? "正在准备" : de(e);
		}
		function Ee() {
			N.value || A.value || (pe(), s("close"));
		}
		function De(e) {
			let t = c.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(n.width === 0 && n.height === 0 || e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && Ee();
		}
		return i(() => [
			r.open,
			r.initialTeam?.id,
			r.target
		], () => {
			r.open ? (me(), r.visible && ye()) : (W++, pe(), N.value = !1);
		}, { immediate: !0 }), i(() => r.visible, (e) => {
			e ? r.open && (l.value === "receipt" && I.value || (S.value ? C.value || ge(S.value.id) : ye())) : pe();
		}), ee(() => {
			W++, pe();
		}), (t, r) => (n(), T("dialog", {
			ref_key: "dialogRef",
			ref: c,
			class: "tm-dialog tm-dialog--lg",
			"aria-labelledby": "teamJoinDialogTitle",
			"aria-busy": N.value || A.value || D.value || R.value,
			onCancel: te(Ee, ["prevent"]),
			onClick: De
		}, [
			v("div", Ao, [v("div", null, [
				v("p", jo, g(l.value === "receipt" ? "JOIN REQUEST RECEIPT" : "TEAM JOIN PREVIEW"), 1),
				v("h3", Mo, g(l.value === "receipt" ? "加入请求受理回执" : "加入 Team 预览与席位确认"), 1),
				v("p", No, [S.value ? (n(), T(p, { key: 0 }, [
					r[7] ||= E(" 目标工作区：", -1),
					v("strong", null, g(S.value.display_name || S.value.name || S.value.workspace_id), 1),
					r[8] ||= E(" （", -1),
					v("span", Po, g(S.value.workspace_id), 1),
					r[9] ||= E("） ", -1)
				], 64)) : (n(), T(p, { key: 1 }, [E(" 请选择目标 Team，系统将执行纯本地名单去重与席位容量核算。 ")], 64))])
			]), v("button", {
				type: "button",
				class: "tm-dialog__close",
				"aria-label": "关闭加入确认弹窗",
				disabled: N.value || A.value,
				onClick: Ee
			}, " × ", 8, Fo)]),
			l.value === "preview" ? (n(), T("div", Io, [
				ae.value ? (n(), T("div", Lo, [
					r[10] ||= v("span", { class: "tm-field__label" }, "目标 Team 工作区", -1),
					v("select", {
						value: x.value,
						disabled: f.value || N.value || A.value,
						"aria-label": "选择目标 Team",
						onChange: be
					}, [v("option", zo, g(f.value ? "正在加载可用 Team…" : "请选择一个已绑定的 Team"), 1), (n(!0), T(p, null, o(u.value, (e) => (n(), T("option", {
						key: e.id,
						value: e.id
					}, g(e.display_name || e.name || e.workspace_id) + "（" + g(e.workspace_id) + " · 成员 " + g(w($)(e.confirmed_member_count, "待同步")) + "） ", 9, Bo))), 128))], 40, Ro),
					_.value ? (n(), T("div", Vo, [v("div", Ho, g(_.value), 1), v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: r[0] ||= (t) => e.target?.targetTeamId ? _e(e.target.targetTeamId) : ve()
					}, " 重试 ")])) : d("", !0)
				])) : d("", !0),
				D.value ? (n(), T("div", Uo, [...r[11] ||= [v("div", { class: "tm-banner__copy" }, "正在执行本地名单分类与席位容量核算…", -1)]])) : d("", !0),
				O.value ? (n(), T("div", Wo, [v("div", Go, g(O.value), 1), K.value ? (n(), T("button", {
					key: 0,
					type: "button",
					class: "tm-btn tm-btn--sm",
					onClick: r[1] ||= (e) => ge(K.value)
				}, " 重新核算 ")) : d("", !0)])) : d("", !0),
				C.value ? (n(), T(p, { key: 3 }, [
					v("section", Ko, [v("div", qo, [v("span", Jo, " 本次选定名单拆解（去重共 " + g(C.value.counts.unique_count) + " 个） ", 1), v("span", Yo, " 最近同步：" + g(C.value.team_last_synced_at ? e.formatDateTime(C.value.team_last_synced_at) : "尚未同步"), 1)]), v("div", Xo, [
						v("div", Zo, [r[12] ||= v("span", null, "新加入目标", -1), v("strong", null, g(C.value.counts.new_count), 1)]),
						v("div", Qo, [r[13] ||= v("span", null, "已有邀请直接续接", -1), v("strong", null, g(C.value.counts.resume_invite_count), 1)]),
						v("div", $o, [r[14] ||= v("span", null, "已是成员跳过", -1), v("strong", null, g(C.value.counts.already_member_count), 1)]),
						v("div", es, [r[15] ||= v("span", null, "同 Team 执行可复用", -1), v("strong", null, g(C.value.counts.same_team_active_count), 1)]),
						v("div", ts, [r[16] ||= v("span", null, "已属其他Team跳过", -1), v("strong", null, g(C.value.counts.another_team_count), 1)]),
						v("div", ns, [r[17] ||= v("span", null, "缺认证材料跳过", -1), v("strong", null, g(C.value.counts.missing_auth_count), 1)]),
						v("div", rs, [r[18] ||= v("span", null, "账号不可用或身份变化", -1), v("strong", null, g(C.value.counts.unavailable_count), 1)])
					])]),
					v("section", { class: y(["tm-seat-meter", le.value]) }, [
						v("div", is, [r[19] ||= v("span", { class: "tm-seat-meter__title" }, " 席位与人数上限核对 ", -1), v("span", as, " 依据：" + g(w(he)(C.value.capacity.basis)), 1)]),
						v("div", os, [v("div", {
							class: "tm-seat-meter__fill",
							style: m({ width: `${se.value}%` })
						}, null, 4), v("div", {
							class: "tm-seat-meter__fill--added",
							style: m({ width: `${ce.value}%` })
						}, null, 4)]),
						v("div", ss, [v("span", null, [
							r[20] ||= E(" 已购席位：", -1),
							v("strong", null, g(w($)(C.value.capacity.purchased_seats, "未返回", " 席")), 1),
							r[21] ||= E(" · 本地计划上限：", -1),
							v("strong", null, g(C.value.capacity.planned_member_limit !== null && C.value.capacity.planned_member_limit !== void 0 ? `${C.value.capacity.planned_member_limit} 人` : "未设置"), 1)
						]), v("span", null, [
							r[22] ||= E(" 当前占用：", -1),
							v("strong", null, g(w($)(C.value.capacity.occupied_count, "待同步", " 席")), 1),
							r[23] ||= E(" · 本次新增占席：", -1),
							v("strong", null, g(w($)(C.value.capacity.additional_required, "待同步", " 席")), 1),
							r[24] ||= E(" · 提交后剩余：", -1),
							v("strong", null, g(w($)(J.value, "待同步", " 席")), 1)
						])])
					], 2),
					C.value.capacity.blocking_reason_code === "team_limit_required" ? (n(), T("div", cs, [
						r[25] ||= v("div", { class: "tm-banner__copy" }, [v("strong", null, "需先设置本地计划人数上限："), v("span", null, "远端未返回已购席位，且当前未配置本地人数上限（含母号），无法直接发起拉人。")], -1),
						v("div", ls, [a(v("input", {
							"onUpdate:modelValue": r[2] ||= (e) => k.value = e,
							type: "text",
							inputmode: "numeric",
							placeholder: "输入正整数人数上限（含母号）",
							"aria-label": "本地计划人数上限",
							style: {
								flex: "1 1 200px",
								"min-height": "32px",
								padding: "4px 10px",
								border: "1px solid var(--ui-color-border-strong)",
								"border-radius": "6px",
								background: "var(--ui-color-surface)"
							},
							disabled: A.value
						}, null, 8, us), [[ne, k.value]]), v("button", {
							type: "button",
							class: "tm-btn tm-btn--primary tm-btn--sm",
							disabled: A.value,
							onClick: xe
						}, g(A.value ? "保存核算中…" : "设置本地计划人数上限并重新核算"), 9, ds)]),
						j.value ? (n(), T("span", fs, g(j.value), 1)) : d("", !0)
					])) : !C.value.capacity.can_submit && C.value.capacity.blocking_reason_code ? (n(), T("div", ps, [v("div", ms, g(w(H)(C.value.capacity.blocking_reason_code)), 1)])) : d("", !0),
					Y.value ? (n(), T("div", hs, [...r[26] ||= [v("div", { class: "tm-banner__copy" }, " 请求受理后将等待可用席位，不会超额增购。 ", -1)]])) : d("", !0),
					C.value.requires_sync ? (n(), T("div", gs, [...r[27] ||= [v("div", { class: "tm-banner__copy" }, " 将在后台自动先执行一次工作区同步与席位预检，确认远端最新席位后再发出新邀请。 ", -1)]])) : d("", !0)
				], 64)) : d("", !0),
				F.value ? (n(), T("div", _s, [v("div", vs, g(F.value), 1)])) : d("", !0),
				P.value ? (n(), T("div", ys, [v("div", bs, g(P.value), 1)])) : d("", !0)
			])) : I.value ? (n(), T("div", xs, [
				v("div", Ss, [v("div", Cs, [
					r[28] ||= E(" 加入请求（", -1),
					v("span", ws, "#" + g(I.value.id), 1),
					r[29] ||= E("）：请求已持久受理，逐项结果见下方。实际入组结果请在邀请列表或任务中心追踪。 ", -1),
					v("span", { class: y(["tm-badge", `tm-badge--${w(fe)(I.value.status)}`]) }, g(Te(I.value.status)), 3)
				])]),
				v("div", Ts, [
					v("div", Es, [r[30] ||= v("span", null, "待处理", -1), v("strong", null, g(I.value.counts.pending_count), 1)]),
					v("div", Ds, [r[31] ||= v("span", null, "已受理（含复用）", -1), v("strong", null, g(I.value.counts.accepted_count), 1)]),
					v("div", Os, [r[32] ||= v("span", null, "复用进行中", -1), v("strong", null, g(I.value.counts.reused_count), 1)]),
					v("div", ks, [r[33] ||= v("span", null, "跳过", -1), v("strong", null, g(I.value.counts.skipped_count), 1)]),
					v("div", As, [r[34] ||= v("span", null, "受理失败", -1), v("strong", null, g(I.value.counts.failed_count), 1)])
				]),
				v("button", {
					type: "button",
					class: "tm-btn tm-btn--sm",
					disabled: R.value,
					onClick: r[3] ||= (e) => Ce(X.value)
				}, g(R.value ? "正在刷新回执…" : "刷新回执"), 9, js),
				ie.value ? (n(), T("div", Ms, [v("div", Ns, g(ie.value), 1)])) : d("", !0),
				v("div", {
					class: "tm-candidate-list",
					style: { "max-height": "280px" },
					"aria-busy": R.value
				}, [L.value?.items.length ? d("", !0) : (n(), T("div", Fs, " 当前页暂无明细条目。 ")), (n(!0), T(p, null, o(L.value?.items ?? [], (e) => (n(), T("div", {
					key: e.ordinal,
					class: "tm-candidate-row"
				}, [v("div", Is, [v("div", Ls, [r[35] ||= v("span", null, "目标账号", -1), v("span", Rs, g(e.account_id ? `#${e.account_id}` : `目标 ${e.ordinal + 1}`), 1)]), v("div", zs, g(e.message || (e.reason_code ? w(H)(e.reason_code) : "等待后台处理")), 1)]), v("div", Bs, [v("span", { class: y(["tm-badge", `tm-badge--${we(e.acceptance_status).tone}`]) }, g(we(e.acceptance_status).label), 3), e.task_id ? (n(), T("button", {
					key: 0,
					type: "button",
					class: "tm-btn tm-btn--soft tm-btn--sm",
					onClick: (t) => s("openTask", e.task_id, e.run_id)
				}, " 查看任务 ", 8, Vs)) : d("", !0)])]))), 128))], 8, Ps),
				ue.value > 1 ? (n(), T("div", Hs, [
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: X.value <= 1 || R.value,
						onClick: r[4] ||= (e) => Ce(X.value - 1)
					}, " 上一页 ", 8, Us),
					v("span", Ws, " 第 " + g(X.value) + " / " + g(ue.value) + " 页（共 " + g(L.value?.total ?? I.value.counts.unique_count) + " 条） ", 1),
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: X.value >= ue.value || R.value,
						onClick: r[5] ||= (e) => Ce(X.value + 1)
					}, " 下一页 ", 8, Gs)
				])) : d("", !0)
			])) : d("", !0),
			v("div", Ks, [l.value === "preview" ? (n(), T(p, { key: 0 }, [r[36] ||= v("span", { class: "tm-field__hint" }, " 默认普通成员角色，自动接受指定工作区邀请并保留原个人空间 ", -1), v("div", qs, [v("button", {
				type: "button",
				class: "tm-btn",
				disabled: N.value || A.value,
				onClick: Ee
			}, " 取消 ", 8, Js), v("button", {
				type: "button",
				class: "tm-btn tm-btn--primary",
				disabled: !oe.value,
				onClick: Se
			}, g(N.value ? "正在受理…" : "确认发起加入"), 9, Ys)])], 64)) : (n(), T(p, { key: 1 }, [v("span", Xs, " 共请求 " + g(I.value?.counts.requested_count ?? 0) + " 个目标账号 ", 1), v("div", Zs, [K.value ? (n(), T("button", {
				key: 0,
				type: "button",
				class: "tm-btn tm-btn--soft",
				onClick: r[6] ||= (e) => s("openTeamDetail", K.value)
			}, " 进入 Team 邀请列表追踪 ")) : d("", !0), v("button", {
				type: "button",
				class: "tm-btn tm-btn--primary",
				onClick: Ee
			}, " 完成并关闭 ")])], 64))])
		], 40, ko));
	}
}), $s = {
	class: "ui-list",
	"aria-label": "Team 工作区列表"
}, ec = { class: "ui-list-count" }, tc = { key: 0 }, nc = { class: "tm-search-box" }, rc = ["disabled"], ic = ["disabled"], ac = {
	key: 0,
	class: "ui-list-bulkbar"
}, oc = { class: "ui-list-bulkbar__count" }, sc = ["aria-busy"], cc = {
	scope: "col",
	class: "ui-col-check"
}, lc = [
	"checked",
	"indeterminate",
	"disabled"
], uc = { scope: "col" }, dc = { scope: "col" }, fc = { class: "list-filter-options" }, pc = { class: "list-filter-option" }, mc = ["checked"], hc = [
	"value",
	"checked",
	"onChange"
], gc = { key: 0 }, _c = { class: "list-filter-actions" }, vc = {
	scope: "col",
	title: "远端已确认加入的成员数"
}, yc = {
	scope: "col",
	title: "远端待接受的邀请数"
}, bc = { scope: "col" }, xc = { scope: "col" }, Sc = { scope: "col" }, Cc = { class: "list-filter-options" }, wc = { class: "list-filter-option" }, Tc = ["checked"], Ec = [
	"value",
	"checked",
	"onChange"
], Dc = { key: 0 }, Oc = { class: "list-filter-actions" }, kc = { class: "ui-col-check" }, Ac = [
	"aria-label",
	"checked",
	"onChange"
], jc = { "data-label": "工作区" }, Mc = { class: "tm-workspace-identity" }, Nc = { class: "tm-workspace-copy" }, Pc = { class: "tm-workspace-title-row" }, Fc = ["title", "onClick"], Ic = { class: "tm-workspace-sub" }, Lc = ["title"], Rc = { "data-label": "管理母号" }, zc = { class: "tm-cell-stack" }, Bc = { class: "tm-cell-primary" }, Vc = ["title", "onClick"], Hc = { key: 1 }, Uc = {
	class: "tm-cell-sub",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "5px",
		"flex-wrap": "wrap"
	}
}, Wc = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, Gc = { "data-label": "已确认成员" }, Kc = { class: "tm-metric-cell" }, qc = { "data-label": "待接受邀请" }, Jc = { class: "tm-metric-cell" }, Yc = { "data-label": "处理中" }, Xc = { class: "tm-metric-cell" }, Zc = { "data-label": "席位 / 上限" }, Qc = { class: "tm-cell-stack" }, $c = { class: "tm-cell-primary" }, el = { class: "tm-cell-sub" }, tl = { "data-label": "最近同步" }, nl = { class: "tm-cell-stack" }, rl = { class: "tm-cell-primary" }, il = {
	key: 0,
	class: "tm-badge__dot"
}, al = {
	key: 0,
	class: "tm-cell-sub is-danger",
	title: "最近同步失败，可查看相关任务"
}, ol = {
	key: 1,
	class: "tm-cell-sub tm-tabular"
}, sl = { "data-label": "操作" }, cl = { class: "tm-row-actions" }, ll = ["onClick"], ul = ["onClick"], dl = ["disabled", "onClick"], fl = { class: "tm-inline-menu__panel" }, pl = ["onClick"], ml = ["onClick"], hl = ["onClick"], gl = /* @__PURE__ */ t({
	__name: "TeamsListView",
	props: {
		api: {},
		visible: { type: Boolean },
		callbacks: {}
	},
	emits: [
		"open-detail",
		"open-bind",
		"open-edit",
		"open-change-manager",
		"open-join"
	],
	setup(e, { expose: t, emit: u }) {
		let x = e, S = u, C = [
			{
				value: "owner",
				label: "所有者"
			},
			{
				value: "admin",
				label: "管理员"
			},
			{
				value: "member",
				label: "成员"
			},
			{
				value: "unknown",
				label: "待核验"
			}
		], D = [
			{
				value: "never",
				label: "未同步"
			},
			{
				value: "queued",
				label: "排队同步"
			},
			{
				value: "running",
				label: "同步中"
			},
			{
				value: "success",
				label: "已同步"
			},
			{
				value: "failed",
				label: "同步失败"
			},
			{
				value: "partial_success",
				label: "部分同步"
			},
			{
				value: "interrupted",
				label: "同步中断"
			}
		], O = c({
			page: 1,
			page_size: 20,
			q: "",
			role: "",
			last_sync_status: ""
		}), k = h(""), A = h(null), j = h(!1), M = h(!1), re = h(""), N = h([]), ie = h(0), V = h({}), H = h(/* @__PURE__ */ new Set()), W = h(/* @__PURE__ */ new Set()), G = h(null), { widths: q, total: ce, resize: J, resizeWithKeyboard: Y } = P({
			defaults: [
				36,
				194,
				174,
				72,
				72,
				62,
				144,
				152,
				200
			],
			storageKey: "turb_teams_list_column_widths_v2",
			min: 36,
			max: 640
		}), le, X = null, ue = 0;
		function Z(e) {
			return `tm-badge--${e}`;
		}
		function de(e, t) {
			let n = V.value[e];
			if (!n) return null;
			let r = n.find((e) => e.value === t);
			return r ? r.count : null;
		}
		let fe = b(() => N.value.length > 0 && N.value.every((e) => H.value.has(e.id))), pe = b(() => !fe.value && N.value.some((e) => H.value.has(e.id)));
		function me(e) {
			let t = new Set(H.value);
			for (let n of N.value) e ? t.add(n.id) : t.delete(n.id);
			H.value = t;
		}
		function Q(e, t) {
			let n = new Set(H.value);
			t ? n.add(e) : n.delete(e), H.value = n;
		}
		function he() {
			H.value = /* @__PURE__ */ new Set();
		}
		let _e = b(() => {
			let e = [];
			return O.q && e.push({
				key: "q",
				label: `关键词：${O.q}`,
				removeLabel: "清除关键词筛选"
			}), O.role && e.push({
				key: "role",
				label: `母号角色：${ae(O.role)}`,
				removeLabel: "清除母号角色筛选"
			}), O.last_sync_status && e.push({
				key: "last_sync_status",
				label: `同步状态：${oe(O.last_sync_status)}`,
				removeLabel: "清除同步状态筛选"
			}), e;
		}), ve = b(() => _e.value.length > 0);
		function ye(e) {
			e === "q" ? (clearTimeout(le), k.value = "", O.q = "") : e === "role" ? O.role = "" : e === "last_sync_status" && (O.last_sync_status = ""), O.page = 1, Me();
		}
		function Ce() {
			clearTimeout(le), k.value = "", O.q = "", O.role = "", O.last_sync_status = "", O.page = 1, Me();
		}
		function we() {
			clearTimeout(le), k.value = "", O.q !== "" && (O.q = "", O.page = 1, Me());
		}
		function Te(e) {
			O.role = e, O.page = 1, A.value = null, Me();
		}
		function Ee(e) {
			O.last_sync_status = e, O.page = 1, A.value = null, Me();
		}
		function De(e) {
			O.page = e, Me();
		}
		function Oe(e) {
			O.page_size = e, O.page = 1, Me();
		}
		function ke(e) {
			let t = G.value;
			t && t.querySelectorAll("details.tm-inline-menu[open]").forEach((t) => {
				e && t === e || (t.open = !1);
			});
		}
		function Ae(e) {
			let t = e.currentTarget;
			t?.open && ke(t);
		}
		function je(e) {
			ke((e.target instanceof Element ? e.target : null)?.closest("details.tm-inline-menu") ?? null);
		}
		async function Me(e = {}) {
			if (!x.visible) return;
			X?.abort();
			let t = new AbortController();
			X = t;
			let n = ++ue;
			e.silent || (j.value = !0), re.value = "";
			let r = {
				page: O.page,
				page_size: O.page_size,
				include_facets: String(e.includeFacets ?? 1),
				...O.q ? { q: O.q } : {},
				...O.role ? { role: O.role } : {},
				...O.last_sync_status ? { last_sync_status: O.last_sync_status } : {}
			};
			try {
				let e = await x.api.list(r, t.signal);
				if (n !== ue) return;
				N.value = e.items, ie.value = e.total, e.facets && Object.keys(e.facets).length > 0 && (V.value = e.facets);
			} catch (r) {
				if (t.signal.aborted || n !== ue) return;
				let i = r instanceof Error ? r.message : "加载 Team 工作区列表失败";
				e.silent || (re.value = i);
			} finally {
				X === t && (X = null), n === ue && (j.value = !1);
			}
		}
		async function Ne(e) {
			if (W.value.has(e.id)) return;
			let t = new Set(W.value);
			t.add(e.id), W.value = t;
			try {
				let t = await x.api.syncTeam(e.id);
				x.callbacks.notify(t.reused ? `工作区「${U(e)}」已有进行中的同步任务` : `已启动工作区「${U(e)}」同步`), await Me({
					silent: !0,
					includeFacets: 0
				});
			} catch (e) {
				x.callbacks.notify(e instanceof Error ? e.message : "同步工作区提交失败");
			} finally {
				let t = new Set(W.value);
				t.delete(e.id), W.value = t;
			}
		}
		async function Pe() {
			let e = [...H.value];
			if (e.length && !M.value) {
				M.value = !0;
				try {
					let t = await x.api.syncTeamsBulk(e);
					x.callbacks.notify(`批量同步已受理：排队 ${t.accepted_count - t.reused_count}，复用 ${t.reused_count}，跳过 ${t.skipped_count}`), he(), await Me({
						silent: !0,
						includeFacets: 0
					});
				} catch (e) {
					x.callbacks.notify(e instanceof Error ? e.message : "批量同步提交失败");
				} finally {
					M.value = !1;
				}
			}
		}
		function Fe(e, t) {
			let n = e.currentTarget?.closest("details");
			n && (n.open = !1), x.callbacks.openTasksForTeam(t.id, U(t));
		}
		function Ie(e, t) {
			let n = e.currentTarget?.closest("details");
			n && (n.open = !1), S("open-edit", t);
		}
		function Le(e, t) {
			let n = e.currentTarget?.closest("details");
			n && (n.open = !1), S("open-change-manager", t);
		}
		return $n({
			visible: () => x.visible,
			shouldPoll: () => N.value.some(Se),
			onPoll: () => Me({
				silent: !0,
				includeFacets: 0
			}),
			intervalMs: 3e3
		}), i(k, (e) => {
			clearTimeout(le);
			let t = e.trim();
			t !== O.q && (le = setTimeout(() => {
				O.q = t, O.page = 1, Me();
			}, 250));
		}), s(() => {
			document.addEventListener("click", je), Me();
		}), i(() => x.visible, (e) => {
			e ? Me() : (X?.abort(), X = null, ue += 1, j.value = !1);
		}), ee(() => {
			clearTimeout(le), X?.abort(), document.removeEventListener("click", je);
		}), t({ refresh: (e) => Me({
			silent: e?.silent,
			includeFacets: +!e?.silent
		}) }), (t, i) => (n(), T("div", {
			ref_key: "listRootRef",
			ref: G,
			class: "tm-root"
		}, [v("section", $s, [
			l(z, { filtered: ve.value }, {
				actions: r(() => [
					v("button", {
						type: "button",
						class: "tm-btn",
						disabled: !H.value.size || M.value,
						onClick: i[2] ||= (e) => void Pe()
					}, g(M.value ? "同步提交中…" : "同步选中"), 9, rc),
					v("button", {
						type: "button",
						class: "tm-btn ui-refresh-button",
						disabled: j.value,
						onClick: i[3] ||= (e) => void Me()
					}, g(j.value ? "刷新中…" : "刷新"), 9, ic),
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--primary",
						onClick: i[4] ||= (e) => S("open-bind")
					}, " 绑定已有 Team ")
				]),
				default: r(() => [
					v("span", ec, [E(" 共 " + g(ie.value.toLocaleString()) + " 个工作区 ", 1), H.value.size ? (n(), T("small", tc, "已选 " + g(H.value.size) + " 项", 1)) : d("", !0)]),
					v("div", nc, [
						i[30] ||= v("svg", {
							class: "tm-search-box__icon",
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [v("circle", {
							cx: "7",
							cy: "7",
							r: "4.5"
						}), v("path", { d: "m10.5 10.5 3 3" })], -1),
						a(v("input", {
							"onUpdate:modelValue": i[0] ||= (e) => k.value = e,
							type: "search",
							"aria-label": "搜索工作区",
							placeholder: "搜索名称 / workspace_id / 母号邮箱",
							onKeydown: i[1] ||= f(te((e) => {
								O.q = k.value.trim(), O.page = 1, Me();
							}, ["prevent"]), ["enter"])
						}, null, 544), [[ne, k.value]]),
						k.value ? (n(), T("button", {
							key: 0,
							type: "button",
							class: "tm-search-box__clear",
							"aria-label": "清空搜索",
							onClick: we
						}, " × ")) : d("", !0)
					]),
					l(L, {
						items: _e.value,
						onRemove: ye
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			H.value.size ? (n(), T("div", ac, [v("span", oc, "已跨页选中 " + g(H.value.size) + " 个工作区", 1), v("button", {
				type: "button",
				class: "tm-btn tm-btn--ghost tm-btn--sm",
				onClick: he
			}, " 清空选择 ")])) : d("", !0),
			v("div", {
				class: "ui-table-wrap ui-table-scroll",
				tabindex: "0",
				"aria-label": "Team 工作区表格，可横向滚动",
				"aria-busy": j.value
			}, [v("table", {
				class: "ui-table ui-table--sticky-end ui-table--cards",
				style: m({ "--ui-table-width": `${w(ce)}px` })
			}, [
				i[42] ||= v("caption", { class: "ui-sr-only" }, "已绑定的 ChatGPT Team 工作区列表", -1),
				v("colgroup", null, [(n(!0), T(p, null, o(w(q), (e, t) => (n(), T("col", {
					key: t,
					style: m({ width: `${e}px` })
				}, null, 4))), 128))]),
				v("thead", null, [v("tr", null, [
					v("th", cc, [v("input", {
						type: "checkbox",
						"aria-label": "全选当前页工作区",
						checked: fe.value,
						indeterminate: pe.value,
						disabled: !N.value.length,
						onChange: i[5] ||= (e) => me(e.target.checked)
					}, null, 40, lc)]),
					v("th", uc, [i[31] ||= E(" 工作区 ", -1), l(F, {
						label: "工作区",
						onStart: i[6] ||= (e) => w(J)(1, e),
						onNudge: i[7] ||= (e) => w(Y)(1, e)
					})]),
					v("th", dc, [l(I, {
						label: "管理母号",
						active: !!O.role,
						summary: O.role ? w(ae)(O.role) : "",
						open: e.visible && A.value === "role",
						"onUpdate:open": i[11] ||= (e) => A.value = e ? "role" : null
					}, {
						default: r(() => [v("fieldset", fc, [
							i[33] ||= v("legend", { class: "ui-sr-only" }, "按母号角色筛选", -1),
							v("label", pc, [v("input", {
								type: "radio",
								name: "team-role",
								value: "",
								checked: !O.role,
								onChange: i[8] ||= (e) => Te("")
							}, null, 40, mc), i[32] ||= v("span", null, "全部角色", -1)]),
							(n(), T(p, null, o(C, (e) => v("label", {
								key: e.value,
								class: "list-filter-option"
							}, [
								v("input", {
									type: "radio",
									name: "team-role",
									value: e.value,
									checked: O.role === e.value,
									onChange: (t) => Te(e.value)
								}, null, 40, hc),
								v("span", null, g(e.label), 1),
								de("role", e.value) === null ? d("", !0) : (n(), T("small", gc, g(de("role", e.value)), 1))
							])), 64))
						]), v("div", _c, [v("button", {
							type: "button",
							onClick: i[9] ||= (e) => Te("")
						}, "清除"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[10] ||= (e) => A.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(F, {
						label: "管理母号",
						onStart: i[12] ||= (e) => w(J)(2, e),
						onNudge: i[13] ||= (e) => w(Y)(2, e)
					})]),
					v("th", vc, [i[34] ||= E(" 已确认 ", -1), l(F, {
						label: "已确认成员",
						onStart: i[14] ||= (e) => w(J)(3, e),
						onNudge: i[15] ||= (e) => w(Y)(3, e)
					})]),
					v("th", yc, [i[35] ||= E(" 待接受 ", -1), l(F, {
						label: "待接受邀请",
						onStart: i[16] ||= (e) => w(J)(4, e),
						onNudge: i[17] ||= (e) => w(Y)(4, e)
					})]),
					v("th", bc, [i[36] ||= E(" 处理中 ", -1), l(F, {
						label: "处理中",
						onStart: i[18] ||= (e) => w(J)(5, e),
						onNudge: i[19] ||= (e) => w(Y)(5, e)
					})]),
					v("th", xc, [i[37] ||= E(" 席位 / 上限 ", -1), l(F, {
						label: "席位 / 上限",
						onStart: i[20] ||= (e) => w(J)(6, e),
						onNudge: i[21] ||= (e) => w(Y)(6, e)
					})]),
					v("th", Sc, [l(I, {
						label: "最近同步",
						active: !!O.last_sync_status,
						summary: O.last_sync_status ? w(oe)(O.last_sync_status) : "",
						open: e.visible && A.value === "last_sync_status",
						"onUpdate:open": i[25] ||= (e) => A.value = e ? "last_sync_status" : null
					}, {
						default: r(() => [v("fieldset", Cc, [
							i[39] ||= v("legend", { class: "ui-sr-only" }, "按同步状态筛选", -1),
							v("label", wc, [v("input", {
								type: "radio",
								name: "team-sync",
								value: "",
								checked: !O.last_sync_status,
								onChange: i[22] ||= (e) => Ee("")
							}, null, 40, Tc), i[38] ||= v("span", null, "全部同步状态", -1)]),
							(n(), T(p, null, o(D, (e) => v("label", {
								key: e.value,
								class: "list-filter-option"
							}, [
								v("input", {
									type: "radio",
									name: "team-sync",
									value: e.value,
									checked: O.last_sync_status === e.value,
									onChange: (t) => Ee(e.value)
								}, null, 40, Ec),
								v("span", null, g(e.label), 1),
								de("last_sync_status", e.value) === null ? d("", !0) : (n(), T("small", Dc, g(de("last_sync_status", e.value)), 1))
							])), 64))
						]), v("div", Oc, [v("button", {
							type: "button",
							onClick: i[23] ||= (e) => Ee("")
						}, "清除"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[24] ||= (e) => A.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(F, {
						label: "最近同步",
						onStart: i[26] ||= (e) => w(J)(7, e),
						onNudge: i[27] ||= (e) => w(Y)(7, e)
					})]),
					i[40] ||= v("th", { scope: "col" }, "操作", -1)
				])]),
				v("tbody", null, [(n(!0), T(p, null, o(N.value, (t) => (n(), T("tr", {
					key: t.id,
					class: y({ "is-selected": H.value.has(t.id) })
				}, [
					v("td", kc, [v("input", {
						type: "checkbox",
						"aria-label": `选择工作区 ${w(U)(t)}`,
						checked: H.value.has(t.id),
						onChange: (e) => Q(t.id, e.target.checked)
					}, null, 40, Ac)]),
					v("td", jc, [v("div", Mc, [v("div", {
						class: "tm-workspace-avatar",
						style: m({ "--tm-hue": String(w(be)(t.workspace_id)) }),
						"aria-hidden": "true"
					}, g(w(xe)(w(U)(t))), 5), v("div", Nc, [v("div", Pc, [v("button", {
						type: "button",
						class: "tm-workspace-name-btn",
						title: w(U)(t),
						onClick: (e) => S("open-detail", t.id, "members")
					}, g(w(U)(t)), 9, Fc)]), v("div", Ic, [v("span", {
						class: "tm-mono",
						title: t.workspace_id
					}, g(t.workspace_id), 9, Lc)])])])]),
					v("td", Rc, [v("div", zc, [v("div", Bc, [t.manager_account.id ? (n(), T("button", {
						key: 0,
						type: "button",
						class: "tm-link-btn",
						title: t.manager_account.email || void 0,
						onClick: (n) => e.callbacks.openAccountDetail(t.manager_account.id)
					}, g(t.manager_account.email || `#${t.manager_account.id}`), 9, Vc)) : (n(), T("span", Hc, g(t.manager_account.email || "—"), 1))]), v("div", Uc, [v("span", { class: y(["tm-badge", Z(w(K)(t.role))]) }, g(w(ae)(t.role)), 3), t.manager_account.archived ? (n(), T("span", Wc, "已归档")) : d("", !0)])])]),
					v("td", Gc, [v("div", Kc, [v("span", { class: y(["tm-metric-val", { "is-null": t.confirmed_member_count === null }]) }, g(w($)(t.confirmed_member_count, "待同步")), 3)])]),
					v("td", qc, [v("div", Jc, [v("span", { class: y(["tm-metric-val", { "is-null": t.pending_invite_count === null }]) }, g(w($)(t.pending_invite_count, "待同步")), 3)])]),
					v("td", Yc, [v("div", Xc, [v("span", { class: y(["tm-metric-val", { "is-processing": (t.processing_count ?? 0) > 0 }]) }, g(w($)(t.processing_count, "—")), 3)])]),
					v("td", Zc, [v("div", Qc, [v("div", $c, [v("span", null, g(w(ge)(t).primary), 1)]), v("div", el, [v("span", { class: y(["tm-badge", Z(w(ge)(t).tone)]) }, g(w(ge)(t).secondary), 3)])])]),
					v("td", tl, [v("div", nl, [v("div", rl, [v("span", { class: y(["tm-badge", Z(w(se)(t.last_sync_status))]) }, [t.last_sync_status === "queued" || t.last_sync_status === "running" ? (n(), T("span", il)) : d("", !0), E(" " + g(w(oe)(t.last_sync_status)), 1)], 2)]), t.last_sync_status === "failed" ? (n(), T("div", al, " 同步失败 ")) : (n(), T("div", ol, g(t.last_synced_at ? e.callbacks.formatDateTime(t.last_synced_at) : "待同步"), 1))])]),
					v("td", sl, [v("div", cl, [
						v("button", {
							type: "button",
							class: "tm-btn tm-btn--sm",
							onClick: (e) => S("open-detail", t.id, "members")
						}, " 查看 ", 8, ll),
						v("button", {
							type: "button",
							class: "tm-btn tm-btn--sm tm-btn--soft",
							title: "选择账号批量邀请并自动加入",
							onClick: (e) => S("open-join", t)
						}, " 拉人 ", 8, ul),
						v("button", {
							type: "button",
							class: "tm-btn tm-btn--sm",
							disabled: W.value.has(t.id) || t.last_sync_status === "queued" || t.last_sync_status === "running",
							onClick: (e) => void Ne(t)
						}, g(W.value.has(t.id) ? "同步中" : "同步"), 9, dl),
						v("details", {
							class: "tm-inline-menu",
							onToggle: Ae
						}, [i[41] ||= v("summary", { "aria-label": "更多操作" }, "···", -1), v("div", fl, [
							v("button", {
								type: "button",
								onClick: (e) => Fe(e, t)
							}, " 查看相关任务 ", 8, pl),
							v("button", {
								type: "button",
								onClick: (e) => Ie(e, t)
							}, " 设置别名与上限 ", 8, ml),
							v("button", {
								type: "button",
								onClick: (e) => Le(e, t)
							}, " 更换管理母号 ", 8, hl)
						])], 32)
					])])
				], 2))), 128)), N.value.length ? d("", !0) : (n(), _(B, {
					key: 0,
					colspan: 9,
					loading: j.value,
					error: re.value,
					"loading-title": "正在加载 Team 工作区",
					"loading-text": "获取已绑定的工作区、成员快照与同步状态",
					"error-title": "加载工作区列表失败",
					title: ve.value ? "没有匹配的工作区" : "还没有绑定的 Team 工作区",
					text: ve.value ? "可调整搜索关键词或清除筛选条件后再试。" : "选择一个已有 ChatGPT Team 管理权的主账号完成探测与绑定，即可统一管理成员、席位并自动批量拉人。",
					"retry-label": "重试",
					onRetry: i[29] ||= (e) => void Me()
				}, {
					default: r(() => [!j.value && !re.value && !ve.value ? (n(), T("button", {
						key: 0,
						type: "button",
						class: "tm-btn tm-btn--primary",
						onClick: i[28] ||= (e) => S("open-bind")
					}, " 绑定已有 Team ")) : !j.value && !re.value && ve.value ? (n(), T("button", {
						key: 1,
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: Ce
					}, " 清除筛选条件 ")) : d("", !0)]),
					_: 1
				}, 8, [
					"loading",
					"error",
					"title",
					"text"
				]))])
			], 4)], 8, sc),
			l(R, {
				page: O.page,
				size: O.page_size,
				total: ie.value,
				busy: j.value,
				label: "Team 工作区列表分页",
				"onUpdate:page": De,
				"onUpdate:size": Oe
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy"
			])
		])], 512));
	}
}), _l = { class: "tm-page-shell" }, vl = /* @__PURE__ */ t({
	__name: "TeamsPageShell",
	props: {
		api: {},
		callbacks: {},
		initialNavigation: {},
		initialVisible: {
			type: Boolean,
			default: !0
		}
	},
	setup(t, { expose: r }) {
		let i = t;
		function o(e) {
			return e?.view === "detail" && e.team_id ? {
				tab: "teams",
				view: "detail",
				team_id: j(e.team_id, "Team ID"),
				section: e.section === "invitations" ? "invitations" : "members"
			} : {
				tab: "teams",
				view: "list"
			};
		}
		let s = o(i.initialNavigation), c = h(i.initialVisible), u = h(s.view), f = h(s.team_id ?? null), p = h(s.section ?? "members"), m = h({}), g = b(() => f.value && m.value[f.value] || ""), v = h(0), ee = S(null), te = h(null), y = h(null), x = h(!1), ne = h("bind"), w = S(null), E = h(!1), D = S(null), O = h(!1), k = S(null), A = h(!1), M = S(null), re = S(null);
		function N(e = f.value) {
			if (!e) return;
			let t = { ...m.value };
			delete t[e], m.value = t;
		}
		function P() {
			return u.value === "detail" && f.value ? {
				tab: "teams",
				view: "detail",
				team_id: f.value,
				section: p.value
			} : {
				tab: "teams",
				view: "list"
			};
		}
		function F(t, n = "push", r = {}) {
			let a = o(t), s = u.value === "list";
			a.view === "detail" && a.team_id ? (s && typeof window < "u" && (v.value = window.scrollY || 0), u.value = "detail", f.value = a.team_id, p.value = a.section ?? "members", typeof window < "u" && s && e(() => window.scrollTo({ top: 0 }))) : (u.value = "list", f.value = null, p.value = "members", m.value = {}, ee.value = null, e(() => {
				typeof window < "u" && window.scrollTo({ top: v.value }), te.value?.refresh({ silent: !0 });
			})), r.emit !== !1 && i.callbacks.onNavigation(P(), n);
		}
		function I(e, t = "members") {
			N(e), F({
				view: "detail",
				team_id: e,
				section: t
			}, "push");
		}
		function L() {
			F({ view: "list" }, "push");
		}
		function R(e) {
			p.value !== e && (p.value = e, i.callbacks.onNavigation(P(), "replace"));
		}
		function ie() {
			ne.value = "bind", w.value = null, x.value = !0;
		}
		function z(e) {
			ne.value = "change_manager", w.value = e, x.value = !0;
		}
		function B(e) {
			D.value = e, E.value = !0;
		}
		function V(e) {
			k.value = e, O.value = !0;
		}
		function H(e) {
			M.value = e.targetTeamId && ee.value?.id === e.targetTeamId ? ee.value : null, re.value = e, A.value = !0;
		}
		function U(e) {
			let t = k.value;
			O.value = !1, t && (M.value = t, re.value = {
				mode: "explicit",
				accountIds: e.accountIds,
				expectedEmails: e.expectedEmails,
				targetTeamId: t.id
			}, A.value = !0);
		}
		function W(e) {
			x.value = !1, te.value?.refresh({ silent: !0 }), F({
				view: "detail",
				team_id: e.id,
				section: "members"
			}, "push");
		}
		function G(e) {
			x.value = !1, K(e);
		}
		function ae(e) {
			x.value = !1, F({
				view: "detail",
				team_id: e,
				section: "members"
			}, "push");
		}
		function K(e) {
			E.value = !1, D.value?.id === e.id && (D.value = e), ee.value?.id === e.id && (ee.value = e), M.value?.id === e.id && (M.value = e), k.value?.id === e.id && (k.value = e), u.value === "detail" && f.value === e.id && y.value?.updateTeamSnapshot(e), te.value?.refresh({ silent: !0 });
		}
		function q() {
			u.value === "detail" && f.value && y.value?.refresh({ silent: !0 }), te.value?.refresh({ silent: !0 });
		}
		function oe(e, t) {
			m.value = {
				...m.value,
				[t]: e.id
			}, u.value === "detail" && f.value === t && y.value?.refreshAll(), te.value?.refresh({ silent: !0 });
		}
		function se() {
			x.value = !1, E.value = !1, O.value = !1, A.value = !1;
		}
		function ce(e) {
			c.value = e;
		}
		async function J() {
			u.value === "detail" && f.value ? y.value?.refreshAll() : await te.value?.refresh();
		}
		return r({
			setVisible: ce,
			navigate: F,
			navigationState: P,
			openJoinFromAccounts: H,
			openBindModal: ie,
			closeDialogs: se,
			refresh: J
		}), (e, r) => (n(), T("div", _l, [
			a(l(gl, {
				ref_key: "listRef",
				ref: te,
				api: t.api,
				visible: c.value && u.value === "list",
				callbacks: t.callbacks,
				onOpenDetail: I,
				onOpenBind: ie,
				onOpenEdit: B,
				onOpenChangeManager: z,
				onOpenJoin: V
			}, null, 8, [
				"api",
				"visible",
				"callbacks"
			]), [[C, u.value === "list"]]),
			u.value === "detail" && f.value ? (n(), _(oo, {
				key: 0,
				ref_key: "detailRef",
				ref: y,
				api: t.api,
				"team-id": f.value,
				section: p.value,
				visible: c.value && u.value === "detail",
				callbacks: t.callbacks,
				"join-request-id": g.value,
				onBack: L,
				"onUpdate:section": R,
				onOpenEdit: B,
				onOpenChangeManager: z,
				onOpenJoin: V,
				onTeamLoaded: r[0] ||= (e) => ee.value = e,
				onClearJoinRequest: r[1] ||= (e) => N()
			}, null, 8, [
				"api",
				"team-id",
				"section",
				"visible",
				"callbacks",
				"join-request-id"
			])) : d("", !0),
			l(Bt, {
				open: x.value,
				api: t.api,
				mode: ne.value,
				team: w.value,
				visible: c.value,
				onClose: r[2] ||= (e) => x.value = !1,
				onBound: W,
				onManagerUpdated: G,
				onOpenExistingTeam: ae,
				onNotify: t.callbacks.notify
			}, null, 8, [
				"open",
				"api",
				"mode",
				"team",
				"visible",
				"onNotify"
			]),
			l(Oo, {
				open: E.value,
				api: t.api,
				team: D.value,
				visible: c.value,
				onClose: r[3] ||= (e) => E.value = !1,
				onUpdated: K,
				onConflict: q,
				onNotify: t.callbacks.notify
			}, null, 8, [
				"open",
				"api",
				"team",
				"visible",
				"onNotify"
			]),
			l(Zn, {
				open: O.value,
				api: t.api,
				team: k.value,
				visible: c.value,
				onClose: r[4] ||= (e) => O.value = !1,
				onConfirmCandidates: U,
				onOpenAdvancedInAccounts: r[5] ||= (e) => {
					O.value = !1, t.callbacks.openAccountsCandidateMode(e);
				},
				onNotify: t.callbacks.notify
			}, null, 8, [
				"open",
				"api",
				"team",
				"visible",
				"onNotify"
			]),
			l(Qs, {
				open: A.value,
				api: t.api,
				"initial-team": M.value,
				target: re.value,
				visible: c.value,
				"format-date-time": t.callbacks.formatDateTime,
				onClose: r[6] ||= (e) => A.value = !1,
				onSubmitted: oe,
				onOpenTask: r[7] ||= (e, n) => t.callbacks.openTask(e, n),
				onOpenTeamDetail: r[8] ||= (e) => {
					A.value = !1, F({
						view: "detail",
						team_id: e,
						section: "invitations"
					}, "push");
				},
				onTeamUpdated: K,
				onNotify: t.callbacks.notify
			}, null, 8, [
				"open",
				"api",
				"initial-team",
				"target",
				"visible",
				"format-date-time",
				"onNotify"
			])
		]));
	}
});
// src/teams.ts
function yl(e, t) {
	let n = t.api ?? A(), r = x(vl, {
		api: n,
		callbacks: t.callbacks,
		initialNavigation: t.navigation,
		initialVisible: t.visible ?? !0
	}), i = r.mount(e);
	return {
		setVisible: (e) => i.setVisible(e),
		navigate: (e, t = "push", n) => i.navigate(e, t, n),
		navigationState: () => i.navigationState(),
		openJoinFromAccounts: (e) => i.openJoinFromAccounts(e),
		openBindModal: () => i.openBindModal(),
		closeDialogs: () => i.closeDialogs(),
		refresh: () => i.refresh(),
		destroy: () => r.unmount()
	};
}
export { yl as mountTeams };
