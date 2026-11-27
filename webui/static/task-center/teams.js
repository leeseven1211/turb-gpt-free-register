import { A as e, C as t, F as n, G as r, H as i, K as a, L as o, M as s, Q as c, S as l, Z as u, _ as d, c as f, d as p, dt as m, et as h, ft as g, g as _, h as v, j as ee, l as y, lt as b, m as x, n as S, nt as C, o as te, s as w, st as T, v as E, x as D, y as O } from "./_plugin-vue_export-helper-Btipf5Px.js";
import { a as k, i as A, n as j, o as M, t as N } from "./teams-DPJuGxLd.js";
import { t as P } from "./useNativeDialog-g-m38H2d.js";
import { t as F } from "./errorLabels-Co3XCR-i.js";
import { n as I, t as L } from "./ColumnResizer-Cxm2jUGa.js";
import { i as R, n as z, t as B } from "./ListFilterSummary-41hWatme.js";
import { t as V } from "./ListPagination-CmqtjjEX.js";
import { t as H } from "./ListResult-C60lPQ3j.js";
import { t as U } from "./ListToolbar-Bs-KwjyH.js";
// src/features/teams/statusLabels.ts
var W = Object.freeze({
	team_probe_expired: "核验结果已过期",
	team_probe_failed: "工作区核验失败",
	team_workspace_not_found: "未找到目标工作区",
	team_workspace_personal: "个人空间不可绑定",
	team_permission_denied: "母号无管理权限",
	team_already_bound: "工作区已绑定",
	team_manager_auth_failed: "母号登录态失效",
	team_manager_deactivated: "管理母号已停用",
	team_sync_in_progress: "正在同步工作区",
	team_sync_failed: "同步工作区失败",
	team_revision_conflict: "工作区状态已变",
	team_seat_full: "已购席位不足",
	team_limit_reached: "已达本地人数上限",
	team_limit_required: "需先设本地上限",
	team_invite_send_failed: "发送邀请失败",
	team_invite_rate_limited: "发送邀请被限流",
	team_invite_mail_timeout: "等待邀请信超时",
	team_invite_link_invalid: "邀请链接已失效",
	team_invite_revoked: "邀请已被撤回",
	team_invite_expired: "邀请已过期",
	team_target_auth_missing: "目标号缺认证材料",
	team_target_auth_failed: "目标号登录失败",
	team_target_totp_failed: "目标号2FA失败",
	team_target_deactivated: "目标账号已停用",
	team_target_email_invalid: "目标邮箱已失效",
	team_already_in_other_team: "已归属其他Team",
	team_membership_unverified: "加入结果待确认"
});
function G(e, t) {
	let n = String(e || t?.reason_code || "").trim();
	if (n && Object.hasOwn(W, n)) return W[n];
	let r = String(t?.summary || "").trim();
	return r && Array.from(r).length <= 10 ? r : n ? F({
		code: n,
		error_code: n
	}) : "状态待核对";
}
var K = Object.freeze({
	owner: "所有者",
	admin: "管理员",
	member: "成员",
	unknown: "待核验"
});
function ne(e) {
	return K[String(e || "unknown").toLowerCase()] ?? "待核验";
}
function q(e) {
	let t = String(e || "unknown").toLowerCase();
	return t === "owner" ? "active" : t === "admin" ? "success" : t === "member" ? "neutral" : "warning";
}
var J = Object.freeze({
	never: "未同步",
	queued: "排队同步",
	running: "同步中",
	success: "已同步",
	failed: "同步失败"
});
function re(e) {
	return J[String(e || "never").toLowerCase()] ?? "待同步";
}
function Y(e) {
	let t = String(e || "never").toLowerCase();
	return t === "success" ? "success" : t === "queued" || t === "running" ? "active" : t === "failed" ? "danger" : "neutral";
}
var X = Object.freeze({
	joined: "已加入",
	not_joined: "未入组",
	removed: "已移除",
	left: "已退出",
	unknown: "待核实"
});
function ie(e) {
	return X[String(e || "unknown").toLowerCase()] ?? "待核实";
}
function ae(e) {
	let t = String(e || "unknown").toLowerCase();
	return t === "joined" ? "success" : t === "removed" || t === "left" ? "danger" : t === "unknown" ? "warning" : "neutral";
}
var Z = Object.freeze({
	not_sent: "未发邀请",
	pending: "待接受邀请",
	accepted: "邀请已接受",
	revoked: "邀请已撤回",
	expired: "邀请已过期",
	unknown: "邀请状态未知"
});
function Q(e) {
	return Z[String(e || "unknown").toLowerCase()] ?? "邀请状态未知";
}
var oe = Object.freeze({
	idle: "未执行",
	queued: "排队中",
	running: "执行中",
	waiting_user: "等待人工处理",
	succeeded: "已完成",
	failed: "执行失败",
	cancelled: "已取消"
});
function se(e) {
	return oe[String(e || "idle").toLowerCase()] ?? "未执行";
}
function ce(e) {
	let t = String(e || "idle").toLowerCase();
	return t === "succeeded" ? "success" : t === "queued" || t === "running" ? "active" : t === "waiting_user" ? "warning" : t === "failed" ? "danger" : "neutral";
}
var le = Object.freeze({
	precheck_capacity: "预检席位与容量",
	send_invite: "母号发送邀请",
	await_invite_mail: "等待接收邀请邮件",
	open_invite_link: "解析并打开邀请链接",
	authenticate_target: "认证目标账号",
	accept_workspace_join: "确认加入工作区",
	verify_membership: "回查工作区成员状态"
});
function ue(e) {
	return e ? le[e] ?? e : "尚无活跃阶段";
}
var de = Object.freeze([
	{
		key: "queued",
		label: "排队等待"
	},
	{
		key: "authenticate_manager",
		label: "母号认证"
	},
	{
		key: "discover_workspaces",
		label: "发现工作区"
	},
	{
		key: "verify_permissions",
		label: "核验管理权限"
	}
]), fe = Object.freeze({
	purchased_seats: "已购席位",
	planned_member_limit: "本地计划上限",
	hybrid_min: "已购与本地上限取小",
	unknown: "席位待确认"
});
function pe(e) {
	return fe[String(e || "unknown")] ?? "席位待确认";
}
function $(e, t = "待同步", n = "") {
	return e == null || !Number.isFinite(e) ? t : `${e}${n}`;
}
function me(e) {
	let t = e.purchased_seats, n = e.planned_member_limit, r = e.capacity;
	if (r.blocking_reason_code === "team_limit_required") return {
		primary: "未返回席位",
		secondary: "需设本地上限",
		tone: "warning"
	};
	let i = [];
	t == null ? i.push("已购未返回") : i.push(`已购 ${t} 席`), n != null && i.push(`上限 ${n}`);
	let a = r.remaining_before_limit, o = !r.can_accept_new_joins && r.blocking_reason_code ? G(r.blocking_reason_code) : a == null ? pe(r.basis) : `可拉剩余 ${a} 席`, s = r.can_accept_new_joins ? a !== null && a <= 1 ? "warning" : "success" : r.blocking_reason_code === "team_seat_full" || r.blocking_reason_code === "team_limit_reached" ? "danger" : "warning";
	return {
		primary: i.join(" · "),
		secondary: o,
		tone: s
	};
}
function he(e) {
	let t = Q(e.invitation_state), n = `成员：${ie(e.membership_state)}`, r = "neutral";
	return e.membership_state === "joined" ? r = "success" : e.invitation_state === "pending" ? r = "active" : e.invitation_state === "revoked" || e.invitation_state === "expired" || e.membership_state === "removed" ? r = "danger" : e.invitation_state === "unknown" && (r = "warning"), {
		primary: t,
		secondary: n,
		tone: r
	};
}
function ge(e) {
	let t = se(e.execution_status), n = e.waiting_reason_code ? G(e.waiting_reason_code) : "";
	return {
		primary: t,
		secondary: [e.stage ? ue(e.stage) : "", n].filter(Boolean).join(" · ") || "—",
		tone: ce(e.execution_status)
	};
}
function _e(e) {
	if (e.error?.reason_code || e.error?.summary) {
		let t = G(e.error.reason_code, e.error), n = [e.error.summary, e.error.detail].filter(Boolean).join("\n");
		return {
			label: t,
			secondary: e.error.reason_code || "",
			detail: n,
			tone: e.execution_status === "waiting_user" ? "warning" : "danger"
		};
	}
	return e.waiting_reason_code ? {
		label: G(e.waiting_reason_code),
		secondary: "等待处理",
		detail: "",
		tone: "warning"
	} : e.membership_state === "joined" ? {
		label: "已确认入组",
		secondary: "",
		detail: "",
		tone: "success"
	} : e.execution_status === "queued" || e.execution_status === "running" ? {
		label: "正在拉人入组",
		secondary: "",
		detail: "",
		tone: "active"
	} : e.invitation_state === "pending" ? {
		label: "待接受邀请",
		secondary: "可继续加入",
		detail: "",
		tone: "warning"
	} : {
		label: "—",
		secondary: "",
		detail: "",
		tone: "neutral"
	};
}
var ve = Object.freeze({
	eligible: {
		label: "可直接加入",
		tone: "success"
	},
	continue_existing_invite: {
		label: "续接已有邀请",
		tone: "active"
	},
	already_member: {
		label: "已是本组成员",
		tone: "neutral"
	},
	already_processing: {
		label: "入组执行中",
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
function ye(e) {
	let t = 0, n = String(e || "team");
	for (let e = 0; e < n.length; e++) t = (t << 5) - t + n.charCodeAt(e) | 0;
	let r = [
		226,
		202,
		168,
		258,
		190,
		240,
		152,
		28
	];
	return r[Math.abs(t) % r.length];
}
function be(e) {
	let t = String(e || "").trim();
	if (!t) return "TM";
	let n = t.split(/[\s\-_·]+/).filter(Boolean);
	return n.length >= 2 ? (Array.from(n[0])[0] + Array.from(n[1])[0]).toUpperCase() : Array.from(t).slice(0, 2).join("").toUpperCase();
}
function xe(e) {
	return e ? e.last_sync_status === "queued" || e.last_sync_status === "running" || e.processing_count > 0 : !1;
}
function Se(e) {
	return e.effective_limit === null || e.effective_limit <= 0 || e.occupied_count === null ? null : Math.min(100, Math.max(0, Math.round(e.occupied_count / e.effective_limit * 100)));
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
}, Ie = { class: "tm-banner__copy" }, Le = ["aria-busy"], Re = {
	key: 0,
	style: {
		padding: "18px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, ze = {
	key: 1,
	style: {
		padding: "18px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, Be = ["onClick"], Ve = {
	class: "tm-candidate-row__left",
	style: {
		"min-width": "0",
		flex: "1"
	}
}, He = [
	"checked",
	"aria-label",
	"onChange"
], Ue = {
	class: "tm-cell-stack",
	style: { "min-width": "0" }
}, We = { class: "tm-cell-primary" }, Ge = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, Ke = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, qe = { class: "tm-badge tm-badge--neutral" }, Je = {
	key: 1,
	class: "tm-badge tm-badge--active"
}, Ye = {
	key: 0,
	class: "tm-cell-sub",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "6px",
		"flex-wrap": "wrap"
	}
}, Xe = ["disabled", "onClick"], Ze = {
	key: 1,
	style: {
		display: "flex",
		"align-items": "center",
		"justify-content": "space-between",
		gap: "8px",
		"padding-top": "2px"
	}
}, Qe = { class: "tm-field__hint" }, $e = ["disabled"], et = {
	key: 0,
	class: "tm-field"
}, tt = {
	class: "tm-probe-stepper",
	role: "status",
	"aria-live": "polite"
}, nt = { class: "tm-probe-step__dot" }, rt = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, it = { class: "tm-banner__copy" }, at = {
	key: 0,
	class: "tm-cell-sub"
}, ot = ["disabled"], st = {
	key: 1,
	class: "tm-banner tm-banner--warning",
	role: "alert"
}, ct = ["disabled"], lt = {
	key: 2,
	class: "tm-field"
}, ut = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "8px"
} }, dt = { class: "tm-field__hint" }, ft = {
	key: 0,
	class: "tm-banner tm-banner--warning"
}, pt = {
	key: 1,
	class: "tm-workspace-list"
}, mt = [
	"aria-checked",
	"aria-disabled",
	"onClick"
], ht = { style: {
	display: "flex",
	"align-items": "flex-start",
	gap: "10px",
	"min-width": "0",
	flex: "1"
} }, gt = [
	"checked",
	"disabled",
	"onChange"
], _t = {
	class: "tm-cell-stack",
	style: {
		"min-width": "0",
		flex: "1"
	}
}, vt = {
	class: "tm-cell-primary",
	style: { "flex-wrap": "wrap" }
}, yt = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, bt = { class: "tm-plan-tag" }, xt = {
	class: "tm-cell-sub",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "10px",
		"flex-wrap": "wrap"
	}
}, St = {
	key: 0,
	class: "tm-cell-sub is-danger"
}, Ct = {
	key: 0,
	style: { flex: "none" }
}, wt = ["onClick"], Tt = {
	key: 3,
	class: "tm-field"
}, Et = {
	key: 0,
	class: "tm-banner tm-banner--warning"
}, Dt = { class: "tm-form-grid" }, Ot = { class: "tm-field" }, kt = ["placeholder", "disabled"], At = { class: "tm-field" }, jt = ["disabled"], Mt = {
	key: 4,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Nt = { class: "tm-banner__copy" }, Pt = { class: "tm-dialog__foot" }, Ft = { class: "tm-field__hint" }, It = { class: "tm-dialog__foot-right" }, Lt = ["disabled"], Rt = ["disabled"], zt = /* @__PURE__ */ t({
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
		let r = e, s = t, c = h();
		P(c, () => r.open && r.visible, () => r.visible);
		let l = h(""), u = h(!1), m = h(""), _ = h([]), S = h(null), C = h(null), w = h(!1), O = h(""), j = h(""), F = h(Date.now()), I = h(""), L = h(""), R = h(""), z = h(!1), B = h(null), V = h(!1), H = null, U = null, W = null, K = null, J = null, re = x(() => r.open && r.visible), Y = x(() => r.mode === "change_manager"), X = x(() => _.value.find((e) => e.id === S.value) ?? null), ie = x(() => w.value || C.value?.status === "queued" || C.value?.status === "running"), ae = x(() => {
			if (V.value) return !0;
			if (!C.value) return !1;
			if (C.value.status === "expired") return !0;
			if (!C.value.expires_at) return !1;
			let e = Date.parse(C.value.expires_at);
			return Number.isFinite(e) && e <= F.value;
		}), Z = x(() => C.value?.workspaces.find((e) => e.workspace_id === j.value) ?? null), Q = x(() => {
			let e = C.value;
			if (!e) return -1;
			if (e.status === "success" || e.stage === "completed") return de.length;
			let t = de.findIndex((t) => t.key === e.stage);
			return t >= 0 ? t : e.status === "queued" ? 0 : 1;
		}), oe = x(() => {
			if (z.value || ie.value || ae.value || !C.value || C.value.status !== "success") return !1;
			let e = Z.value;
			return !(!e || !e.selectable || Y.value && !r.team);
		});
		function se() {
			W !== null && (window.clearTimeout(W), W = null), K !== null && (window.clearInterval(K), K = null), J !== null && (window.clearTimeout(J), J = null);
		}
		function ce() {
			W !== null && (window.clearTimeout(W), W = null), U &&= (U.abort(), null), w.value = !1;
		}
		function le() {
			J !== null && (window.clearTimeout(J), J = null), H &&= (H.abort(), null);
		}
		function ue() {
			le(), ce(), se(), l.value = "", m.value = "", _.value = [], S.value = null, C.value = null, O.value = "", j.value = "", I.value = "", L.value = "", R.value = "", B.value = null, V.value = !1, F.value = Date.now();
		}
		function fe(e) {
			return e instanceof DOMException && e.name === "AbortError";
		}
		function pe(e) {
			if (!Array.isArray(e)) return [];
			let t = [];
			for (let n of e) {
				if (!n || typeof n != "object") continue;
				let e = n, r = A(e.team_id);
				if (!r) continue;
				let i = String(e.membership_state || "joined"), a = i === "invited" || i === "joining" ? i : "joined";
				t.push({
					team_id: r,
					workspace_id: String(e.workspace_id || ""),
					workspace_name: String(e.workspace_name || e.name || ""),
					display_name: e.display_name ? String(e.display_name) : null,
					role: String(e.role || "unknown"),
					membership_state: a
				});
			}
			return t;
		}
		async function me() {
			if (!re.value) return;
			le();
			let e = new AbortController();
			H = e, u.value = !0, m.value = "";
			try {
				let t = new URLSearchParams({
					paged: "1",
					page: "1",
					page_size: "20",
					include_facets: "0",
					archived: "all"
				}), n = l.value.trim();
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
				let i = await r.text(), a = i ? k(i) : null;
				if (!r.ok || !a || a.ok === !1 || !Array.isArray(a.items)) {
					let e = a && typeof a.error == "string" && a.error || a && typeof a.message == "string" && a.message || `加载本地账号失败（HTTP ${r.status}）`;
					throw Error(e);
				}
				let o = [];
				for (let e of a.items) {
					if (!e || typeof e != "object") continue;
					let t = e, n = A(t.id);
					n && o.push({
						id: n,
						email: String(t.email || `账号 #${n}`),
						archived: !!t.archived,
						account_status: String(t.account_status || "未知状态"),
						team_memberships: pe(t.team_memberships)
					});
				}
				_.value = o, !S.value && o.length === 1 && !_e(o[0]) && (S.value = o[0].id);
			} catch (e) {
				if (fe(e)) return;
				m.value = e instanceof Error ? e.message : "加载账号列表失败";
			} finally {
				H === e && (H = null, u.value = !1);
			}
		}
		function he() {
			J !== null && window.clearTimeout(J), J = window.setTimeout(() => {
				J = null, me();
			}, 260);
		}
		function ge() {
			l.value = "", me();
		}
		function _e(e) {
			return Y.value && !!r.team?.manager_account.account_id && r.team?.manager_account.account_id === e.id;
		}
		function ve(e) {
			ie.value || z.value || (S.value = e, R.value = "", B.value = null);
		}
		function ye(e) {
			let t = e.workspaces || [];
			if (e.suggested_workspace_id && t.some((t) => t.workspace_id === e.suggested_workspace_id && t.selectable)) {
				j.value = e.suggested_workspace_id;
				return;
			}
			if (Y.value && r.team?.workspace_id) {
				let e = t.find((e) => e.workspace_id === r.team?.workspace_id && e.selectable);
				if (e) {
					j.value = e.workspace_id;
					return;
				}
			}
			let n = t.filter((e) => e.selectable);
			j.value = n.length === 1 ? n[0].workspace_id : "";
		}
		function be() {
			K === null && (K = window.setInterval(() => {
				F.value = Date.now();
			}, 5e3));
		}
		async function xe(e, t) {
			if (re.value && !t.signal.aborted) try {
				let n = await r.api.getBindingProbe(e, t.signal);
				if (t.signal.aborted || !re.value) return;
				if (C.value = n, F.value = Date.now(), n.status === "queued" || n.status === "running") {
					W = window.setTimeout(() => {
						W = null, xe(e, t);
					}, 1500);
					return;
				}
				w.value = !1, n.status === "success" ? (ye(n), be()) : n.status === "expired" ? V.value = !0 : n.status === "failed" && (O.value = n.error?.summary || G(n.error?.reason_code, n.error) || "工作区核验失败");
			} catch (e) {
				if (fe(e) || t.signal.aborted) return;
				w.value = !1, O.value = e instanceof N || e instanceof Error ? e.message : "轮询探测状态失败";
			}
		}
		async function Se(e) {
			let t = e ?? S.value;
			if (!t || z.value) return;
			S.value = t, ce();
			let n = new AbortController();
			U = n, w.value = !0, O.value = "", R.value = "", B.value = null, V.value = !1, j.value = "", C.value = null;
			try {
				let e = await r.api.createBindingProbe({
					manager_account_id: M(t, "管理母号 ID"),
					target_workspace_id: Y.value ? r.team?.workspace_id ?? null : null
				}, n.signal);
				if (n.signal.aborted || !re.value) return;
				let i = _.value.find((e) => e.id === t);
				C.value = {
					probe_id: e.probe_id,
					probe_revision: "1",
					manager_account_id: t,
					manager_email: i?.email ?? "",
					target_workspace_id: Y.value ? r.team?.workspace_id ?? null : null,
					status: e.status,
					stage: "queued",
					task_id: e.task_id,
					run_id: e.run_id,
					expires_at: null,
					suggested_workspace_id: null,
					workspaces: [],
					error: null
				}, await xe(e.probe_id, n);
			} catch (e) {
				if (fe(e) || n.signal.aborted) return;
				w.value = !1, O.value = e instanceof N || e instanceof Error ? e.message : "发起绑定探测失败";
			}
		}
		function zt(e) {
			!e.selectable || z.value || ae.value || (j.value = e.workspace_id, R.value = "", B.value = null);
		}
		function Bt(e) {
			return e == null || !Number.isFinite(e) ? "未返回席位" : `已购 ${e} 席`;
		}
		function Vt(e) {
			return e.disabled_reason ? e.disabled_reason : e.disabled_reason_code ? G(e.disabled_reason_code) : e.is_team_workspace ? e.can_manage ? e.already_bound_team_id ? "该工作区已绑定" : "当前工作区不可选" : "母号无管理权限" : "个人空间不可绑定";
		}
		function Ht(e) {
			let t = Q.value;
			return C.value?.status === "success" || e < t ? { "is-done": !0 } : e === t && ie.value ? { "is-current": !0 } : {};
		}
		function Ut() {
			let e = L.value.trim();
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
		async function Wt() {
			if (oe.value && C.value && Z.value) {
				if (R.value = "", B.value = null, !Y.value) {
					let e = I.value.trim();
					if (e.length > 120) {
						R.value = "本地显示别名不能超过 120 个字符";
						return;
					}
					let t = Ut();
					if (!t.ok) {
						R.value = t.message;
						return;
					}
					z.value = !0;
					try {
						let n = await r.api.createTeam({
							manager_account_id: C.value.manager_account_id,
							workspace_id: Z.value.workspace_id,
							probe_id: C.value.probe_id,
							probe_revision: C.value.probe_revision,
							display_name: e || null,
							planned_member_limit: t.value
						});
						s("notify", "工作区绑定成功，正在后台同步成员快照"), s("bound", n.team), s("close");
					} catch (e) {
						if (e instanceof N) {
							if (e.code === "team_probe_expired" || e.code === "probe_expired") {
								V.value = !0, R.value = "核验结果已过期，请重新探测后再提交";
								return;
							}
							if (e.code === "team_already_bound") {
								let t = A(e.details.existing_team_id);
								B.value = t, R.value = e.message || "该工作区已在本地绑定，可直接打开已有 Team";
								return;
							}
							R.value = e.message || G(e.code);
						} else R.value = e instanceof Error ? e.message : "绑定工作区失败";
					} finally {
						z.value = !1;
					}
				} else if (r.team) {
					z.value = !0;
					try {
						let e = await r.api.updateTeam(r.team.team_id, {
							expected_revision: r.team.revision,
							manager_account_id: C.value.manager_account_id,
							probe_id: C.value.probe_id,
							probe_revision: C.value.probe_revision
						});
						s("notify", "管理母号已更换"), s("managerUpdated", e.team), s("close");
					} catch (e) {
						if (e instanceof N) {
							if (e.code === "team_probe_expired" || e.code === "probe_expired") {
								V.value = !0, R.value = "核验结果已过期，请重新探测后再提交";
								return;
							}
							R.value = e.message || G(e.code);
						} else R.value = e instanceof Error ? e.message : "更换管理母号失败";
					} finally {
						z.value = !1;
					}
				}
			}
		}
		function Gt() {
			z.value || (le(), ce(), s("close"));
		}
		function Kt(e) {
			let t = c.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(n.width === 0 && n.height === 0 || e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && Gt();
		}
		return i(re, (e) => {
			e ? (ue(), me()) : (le(), ce(), se());
		}, { immediate: !0 }), ee(() => {
			le(), ce(), se();
		}), (t, r) => (n(), E("dialog", {
			ref_key: "dialogRef",
			ref: c,
			class: "tm-dialog tm-dialog--lg",
			"aria-labelledby": "teamBindDialogTitle",
			"aria-busy": z.value || ie.value,
			onCancel: y(Gt, ["prevent"]),
			onClick: Kt
		}, [
			v("div", we, [v("div", null, [
				v("p", Te, g(Y.value ? "TEAM MANAGER HANDOVER" : "TEAM WORKSPACE BINDING"), 1),
				v("h3", Ee, g(Y.value ? "更换管理母号" : "绑定已有 Team 工作区"), 1),
				v("p", De, [Y.value && e.team ? (n(), E(p, { key: 0 }, [
					r[7] ||= D(" 目标工作区：", -1),
					v("strong", null, g(e.team.effective_name), 1),
					r[8] ||= D(" （", -1),
					v("span", Oe, g(e.team.workspace_id), 1),
					r[9] ||= D("），仅切换执行管理的本地母号，不转移远端所有权。 ", -1)
				], 64)) : (n(), E(p, { key: 1 }, [D(" 选择具备工作区管理权限的本地账号作为母号，通过后台探测核验工作区后建立本地关联。 ")], 64))])
			]), v("button", {
				type: "button",
				class: "tm-dialog__close",
				"aria-label": "关闭弹窗",
				disabled: z.value,
				onClick: Gt
			}, " × ", 8, ke)]),
			v("div", Ae, [
				v("section", je, [
					v("div", Me, [r[11] ||= v("span", { class: "tm-field__label" }, "1. 选择管理母号（包含已归档账号）", -1), v("div", Ne, [
						r[10] ||= v("svg", {
							class: "tm-search-box__icon",
							viewBox: "0 0 24 24",
							"aria-hidden": "true"
						}, [v("circle", {
							cx: "11",
							cy: "11",
							r: "7"
						}), v("path", { d: "m20 20-3.5-3.5" })], -1),
						a(v("input", {
							"onUpdate:modelValue": r[0] ||= (e) => l.value = e,
							type: "search",
							placeholder: "搜索账号邮箱或 #ID…",
							"aria-label": "搜索管理母号",
							disabled: z.value,
							onInput: he,
							onKeydown: f(y(me, ["prevent"]), ["enter"])
						}, null, 40, Pe), [[te, l.value]]),
						l.value ? (n(), E("button", {
							key: 0,
							type: "button",
							class: "tm-search-box__clear",
							"aria-label": "清空搜索",
							onClick: ge
						}, " × ")) : d("", !0)
					])]),
					m.value ? (n(), E("div", Fe, [v("div", Ie, g(m.value), 1), v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: me
					}, "重试")])) : d("", !0),
					v("div", {
						class: "tm-candidate-list",
						style: { "max-height": "210px" },
						"aria-busy": u.value
					}, [u.value && !_.value.length ? (n(), E("div", Re, " 正在搜索本地账号… ")) : _.value.length ? d("", !0) : (n(), E("div", ze, " 未找到匹配的本地账号，请调整搜索关键字。 ")), (n(!0), E(p, null, o(_.value, (e) => (n(), E("div", {
						key: e.id,
						class: b(["tm-candidate-row", { "is-selected": S.value === e.id }]),
						style: { cursor: "pointer" },
						onClick: (t) => ve(e.id)
					}, [v("div", Ve, [v("input", {
						type: "radio",
						name: "tm_bind_manager_account",
						checked: S.value === e.id,
						"aria-label": `选择母号 ${e.email}`,
						onChange: (t) => ve(e.id)
					}, null, 40, He), v("div", Ue, [v("div", We, [
						v("span", null, g(e.email), 1),
						v("span", Ge, "#" + g(e.id), 1),
						e.archived ? (n(), E("span", Ke, "已归档")) : d("", !0),
						v("span", qe, g(e.account_status), 1),
						_e(e) ? (n(), E("span", Je, "当前母号")) : d("", !0)
					]), e.team_memberships.length ? (n(), E("div", Ye, [r[12] ||= v("span", null, "已关联 Team：", -1), (n(!0), E(p, null, o(e.team_memberships, (e) => (n(), E("span", {
						key: `${e.team_id}:${e.workspace_id}`,
						class: "acc-team-pill"
					}, g(e.display_name || e.workspace_name || `Team #${e.team_id}`) + " · " + g(T(ne)(e.role)), 1))), 128))])) : d("", !0)])]), v("button", {
						type: "button",
						class: "tm-btn tm-btn--soft tm-btn--sm",
						disabled: ie.value || z.value,
						onClick: y((t) => Se(e.id), ["stop"])
					}, g(ie.value && S.value === e.id ? "探测中…" : "探测并核验工作区"), 9, Xe)], 10, Be))), 128))], 8, Le),
					X.value ? (n(), E("div", Ze, [v("span", Qe, [
						r[13] ||= D(" 已选账号：", -1),
						v("strong", null, g(X.value.email), 1),
						D("（#" + g(X.value.id) + "） ", 1)
					]), v("button", {
						type: "button",
						class: "tm-btn tm-btn--primary tm-btn--sm",
						disabled: ie.value || z.value,
						onClick: r[1] ||= (e) => Se()
					}, g(ie.value ? "正在探测工作区…" : "探测并核验工作区"), 9, $e)])) : d("", !0)
				]),
				C.value || w.value || O.value ? (n(), E("section", et, [
					r[14] ||= v("span", { class: "tm-field__label" }, "2. 工作区核验进度", -1),
					v("div", tt, [(n(!0), E(p, null, o(T(de), (e, t) => (n(), E("div", {
						key: e.key,
						class: b(["tm-probe-step", Ht(t)])
					}, [v("span", nt, g(Ht(t)["is-done"] ? "✓" : t + 1), 1), v("span", null, g(e.label), 1)], 2))), 128))]),
					O.value ? (n(), E("div", rt, [v("div", it, [v("span", null, g(O.value), 1), C.value?.error?.detail ? (n(), E("span", at, g(C.value.error.detail), 1)) : d("", !0)]), v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: !S.value || ie.value || z.value,
						onClick: r[2] ||= (e) => Se()
					}, " 重新探测 ", 8, ot)])) : d("", !0)
				])) : d("", !0),
				C.value && C.value.status === "success" && ae.value ? (n(), E("div", st, [r[15] ||= v("div", { class: "tm-banner__copy" }, [v("span", null, "核验结果已过期，请重新探测后继续确认绑定。")], -1), v("button", {
					type: "button",
					class: "tm-btn tm-btn--sm",
					disabled: !S.value || ie.value || z.value,
					onClick: r[3] ||= (e) => Se()
				}, " 重新探测 ", 8, ct)])) : d("", !0),
				C.value && C.value.status === "success" ? (n(), E("section", lt, [v("div", ut, [r[16] ||= v("span", { class: "tm-field__label" }, "3. 选择目标工作区（单选确认）", -1), v("span", dt, " 核验账号：" + g(C.value.manager_email || `#${C.value.manager_account_id}`), 1)]), C.value.workspaces.length ? (n(), E("div", pt, [(n(!0), E(p, null, o(C.value.workspaces, (e) => (n(), E("div", {
					key: e.workspace_id,
					class: b(["tm-workspace-option", {
						"is-selected": j.value === e.workspace_id,
						"is-disabled": !e.selectable || ae.value
					}]),
					role: "radio",
					"aria-checked": j.value === e.workspace_id,
					"aria-disabled": !e.selectable || ae.value,
					onClick: (t) => zt(e)
				}, [v("div", ht, [v("input", {
					type: "radio",
					name: "tm_probe_workspace",
					checked: j.value === e.workspace_id,
					disabled: !e.selectable || ae.value || z.value,
					style: { "margin-top": "3px" },
					onChange: (t) => zt(e)
				}, null, 40, gt), v("div", _t, [
					v("div", vt, [
						v("span", null, g(e.workspace_name || e.workspace_id), 1),
						v("span", yt, g(e.workspace_id), 1),
						v("span", bt, g(e.plan_type || "unknown"), 1),
						v("span", { class: b(["tm-badge", `tm-badge--${T(q)(e.role)}`]) }, g(T(ne)(e.role)), 3),
						v("span", { class: b(["tm-badge", e.can_manage ? "tm-badge--success" : "tm-badge--danger"]) }, g(e.can_manage ? "可管理" : "无管理权限"), 3)
					]),
					v("div", xt, [
						v("span", null, g(Bt(e.purchased_seats)), 1),
						v("span", null, "成员：" + g(T($)(e.confirmed_member_count, "待同步", " 人")), 1),
						v("span", null, "待接受：" + g(T($)(e.pending_invite_count, "待同步", " 份")), 1)
					]),
					e.selectable ? d("", !0) : (n(), E("div", St, " 不可选原因：" + g(Vt(e)), 1))
				])]), e.already_bound_team_id ? (n(), E("div", Ct, [v("button", {
					type: "button",
					class: "tm-btn tm-btn--soft tm-btn--sm",
					onClick: y((t) => s("openExistingTeam", e.already_bound_team_id), ["stop"])
				}, " 打开已绑定工作区 ", 8, wt)])) : d("", !0)], 10, mt))), 128))])) : (n(), E("div", ft, [...r[17] ||= [v("div", { class: "tm-banner__copy" }, "未在该账号下发现任何工作区。", -1)]]))])) : d("", !0),
				!Y.value && C.value && C.value.status === "success" && Z.value ? (n(), E("section", Tt, [
					r[23] ||= v("span", { class: "tm-field__label" }, "4. 本地显示与席位上限设置（可选）", -1),
					Z.value.purchased_seats === null ? (n(), E("div", Et, [...r[18] ||= [v("div", { class: "tm-banner__copy" }, " 远端未返回已购席位数（未返回），强烈建议现在设置「本地计划人数上限」（含管理母号），否则后续拉人前必须先补设。 ", -1)]])) : d("", !0),
					v("div", Dt, [v("label", Ot, [
						r[19] ||= v("span", { class: "tm-field__label" }, "本地显示别名（display_name）", -1),
						a(v("input", {
							"onUpdate:modelValue": r[4] ||= (e) => I.value = e,
							type: "text",
							maxlength: "120",
							placeholder: Z.value.workspace_name || "留空则使用远端工作区名称",
							disabled: z.value
						}, null, 8, kt), [[te, I.value]]),
						r[20] ||= v("span", { class: "tm-field__hint" }, "留空将展示远端工作区名称，最多 120 字符。", -1)
					]), v("label", At, [
						r[21] ||= v("span", { class: "tm-field__label" }, "本地计划人数上限（planned_member_limit）", -1),
						a(v("input", {
							"onUpdate:modelValue": r[5] ||= (e) => L.value = e,
							type: "text",
							inputmode: "numeric",
							placeholder: "正整数（含母号），留空不设上限",
							disabled: z.value
						}, null, 8, jt), [[te, L.value]]),
						r[22] ||= v("span", { class: "tm-field__hint" }, " 默认策略仅使用已购剩余席位；同时设置时取两者较小值。 ", -1)
					])])
				])) : d("", !0),
				R.value ? (n(), E("div", Mt, [v("div", Nt, g(R.value), 1), B.value ? (n(), E("button", {
					key: 0,
					type: "button",
					class: "tm-btn tm-btn--soft tm-btn--sm",
					onClick: r[6] ||= (e) => s("openExistingTeam", B.value)
				}, " 打开已绑定 Team ")) : d("", !0)])) : d("", !0)
			]),
			v("div", Pt, [v("span", Ft, [Y.value ? (n(), E(p, { key: 0 }, [D(" 仅更新本地执行管理身份，不自动退出或修改原有成员事实 ")], 64)) : (n(), E(p, { key: 1 }, [D(" 确认绑定后将立即入队后台首次成员与邀请同步任务 ")], 64))]), v("div", It, [v("button", {
				type: "button",
				class: "tm-btn",
				disabled: z.value,
				onClick: Gt
			}, " 取消 ", 8, Lt), v("button", {
				type: "button",
				class: "tm-btn tm-btn--primary",
				disabled: !oe.value,
				onClick: Wt
			}, g(z.value ? "提交中…" : Y.value ? "确认更换母号" : "确认绑定工作区"), 9, Rt)])])
		], 40, Ce));
	}
}), Bt = ["aria-busy"], Vt = { class: "tm-dialog__head" }, Ht = { class: "tm-dialog__desc" }, Ut = { class: "tm-mono" }, Wt = { style: {
	display: "flex",
	"align-items": "center",
	gap: "8px"
} }, Gt = ["disabled"], Kt = { class: "tm-dialog__body" }, qt = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "10px",
	"flex-wrap": "wrap"
} }, Jt = {
	class: "tm-search-box",
	style: {
		flex: "1 1 260px",
		"max-width": "340px"
	}
}, Yt = ["onKeydown"], Xt = {
	class: "tm-filter-pills",
	role: "group",
	"aria-label": "候选筛选条件"
}, Zt = {
	key: 0,
	style: {
		padding: "12px 14px",
		border: "1px solid var(--ui-color-border)",
		"border-radius": "9px",
		background: "var(--ui-color-surface-subtle)",
		display: "grid",
		gap: "10px"
	}
}, Qt = { class: "tm-field" }, $t = ["disabled"], en = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "8px"
} }, tn = {
	key: 0,
	style: {
		color: "var(--ui-color-danger, #b91c1c)",
		"font-size": "12px"
	}
}, nn = {
	key: 1,
	class: "tm-field__hint"
}, rn = ["disabled"], an = {
	key: 0,
	style: {
		display: "grid",
		gap: "8px",
		"padding-top": "8px",
		"border-top": "1px solid var(--ui-color-border)",
		"font-size": "12px"
	}
}, on = { style: {
	display: "flex",
	"align-items": "center",
	gap: "12px",
	"flex-wrap": "wrap"
} }, sn = { key: 0 }, cn = { key: 1 }, ln = { key: 2 }, un = {
	key: 0,
	style: {
		display: "grid",
		gap: "3px",
		color: "var(--ui-color-text-secondary)"
	}
}, dn = {
	key: 1,
	style: { color: "var(--ui-color-danger, #b91c1c)" }
}, fn = {
	key: 2,
	style: {
		display: "grid",
		gap: "6px"
	}
}, pn = { class: "tm-mono" }, mn = [
	"checked",
	"disabled",
	"onChange"
], hn = { class: "tm-mono" }, gn = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, _n = {
	key: 1,
	class: "tm-field__hint"
}, vn = {
	key: 1,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, yn = { class: "tm-banner__copy" }, bn = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "8px",
	"font-size": "12px"
} }, xn = ["disabled"], Sn = { class: "tm-field__hint tm-tabular" }, Cn = ["aria-busy"], wn = {
	key: 0,
	style: {
		padding: "24px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, Tn = {
	key: 1,
	style: {
		padding: "24px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, En = {
	class: "tm-candidate-row__left",
	style: {
		"min-width": "0",
		flex: "1"
	}
}, Dn = [
	"checked",
	"disabled",
	"onChange"
], On = {
	class: "tm-cell-stack",
	style: { "min-width": "0" }
}, kn = {
	class: "tm-cell-primary",
	style: { "flex-wrap": "wrap" }
}, An = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, jn = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, Mn = {
	key: 1,
	class: "tm-badge tm-badge--success"
}, Nn = {
	key: 2,
	class: "tm-badge tm-badge--neutral"
}, Pn = {
	key: 3,
	class: "tm-badge tm-badge--neutral"
}, Fn = {
	key: 4,
	class: "tm-badge tm-badge--danger"
}, In = {
	key: 0,
	class: "tm-cell-sub"
}, Ln = { style: {
	display: "flex",
	"align-items": "center",
	gap: "6px",
	flex: "none"
} }, Rn = {
	key: 0,
	class: "tm-badge tm-badge--warning"
}, zn = {
	key: 2,
	style: {
		display: "flex",
		"align-items": "center",
		"justify-content": "flex-end",
		gap: "8px"
	}
}, Bn = ["disabled"], Vn = { class: "tm-field__hint tm-tabular" }, Hn = ["disabled"], Un = { class: "tm-dialog__foot" }, Wn = { style: {
	display: "flex",
	"align-items": "center",
	gap: "10px"
} }, Gn = { class: "tm-tabular" }, Kn = ["disabled"], qn = { class: "tm-dialog__foot-right" }, Jn = ["disabled"], Yn = 20, Xn = /* @__PURE__ */ t({
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
		P(l, () => r.open && r.visible, () => r.visible);
		let u = h(""), m = h(!0), _ = h(!1), S = h(!1), C = h(!1), w = h(!1), T = h(1), O = h(0), k = h(!1), A = h(""), j = h([]), M = h([]), F = c({}), I = h(!1), L = h(""), R = h(!1), z = h(""), B = h(null), V = null, H = null, U = null, W = x(() => r.open && r.visible), K = x(() => new Set(M.value)), ne = x(() => Math.max(1, Math.ceil(O.value / Yn))), q = x(() => j.value.filter((e) => e.eligibility.selectable)), J = x(() => q.value.length > 0 && q.value.every((e) => K.value.has(e.account_id)));
		function re(e) {
			return e instanceof DOMException && e.name === "AbortError";
		}
		function Y() {
			U !== null && (window.clearTimeout(U), U = null), V &&= (V.abort(), null), H &&= (H.abort(), null);
		}
		function X() {
			M.value = [];
			for (let e of Object.keys(F)) delete F[e];
		}
		function ie() {
			Y(), u.value = "", m.value = !0, _.value = !1, S.value = !1, C.value = !1, w.value = !1, T.value = 1, O.value = 0, j.value = [], A.value = "", X(), I.value = !1, L.value = "", z.value = "", B.value = null;
		}
		function ae() {
			return {
				page: T.value,
				page_size: Yn,
				...u.value.trim() ? { q: u.value.trim() } : {},
				scope: m.value ? "unassigned" : "all",
				archived: w.value ? "all" : "0",
				..._.value ? { has_access_token: "1" } : {},
				...S.value ? { has_password: "1" } : {},
				...C.value ? { totp_enabled: "1" } : {}
			};
		}
		async function Z() {
			if (!W.value || !r.team) return;
			V && V.abort();
			let e = new AbortController();
			V = e, k.value = !0, A.value = "";
			try {
				let t = await r.api.listCandidates(r.team.team_id, ae(), e.signal);
				if (e.signal.aborted || !W.value) return;
				j.value = t.items, O.value = t.total;
			} catch (t) {
				if (re(t) || e.signal.aborted) return;
				A.value = t instanceof N || t instanceof Error ? t.message : "加载候选账号失败";
			} finally {
				V === e && (V = null, k.value = !1);
			}
		}
		function Q() {
			T.value = 1, Z();
		}
		function oe() {
			U !== null && window.clearTimeout(U), U = window.setTimeout(() => {
				U = null, Q();
			}, 260);
		}
		function se() {
			u.value = "", Q();
		}
		function ce(e, t) {
			K.value.has(e) || (M.value = [...M.value, e]), t && (F[e] = t);
		}
		function le(e) {
			K.value.has(e) && (M.value = M.value.filter((t) => t !== e)), delete F[e];
		}
		function ue(e, t, n) {
			n && (K.value.has(e) ? le(e) : ce(e, t));
		}
		function de() {
			if (J.value) {
				let e = new Set(q.value.map((e) => e.account_id));
				M.value = M.value.filter((t) => !e.has(t));
				for (let t of e) delete F[t];
			} else for (let e of q.value) ce(e.account_id, e.email);
		}
		function fe(e) {
			return e.eligibility.state === "another_team" && e.active_team ? `已归属「${e.active_team.effective_name}」` : e.eligibility.reason ? e.eligibility.reason : e.eligibility.reason_code ? G(e.eligibility.reason_code) : ve[e.eligibility.state]?.label ?? "不可选";
		}
		function pe(e) {
			return ve[e] ?? {
				label: "状态待核对",
				tone: "neutral"
			};
		}
		async function $() {
			if (!r.team || R.value) return;
			let e = L.value.split(/[\r\n,;，；\t ]+/).map((e) => e.trim()).filter(Boolean);
			if (!e.length) {
				z.value = "请先粘贴邮箱地址或本地账号 ID";
				return;
			}
			H && H.abort();
			let t = new AbortController();
			H = t, R.value = !0, z.value = "";
			try {
				let n = await r.api.resolveCandidates(r.team.team_id, e, t.signal);
				if (t.signal.aborted || !W.value) return;
				let i = 0, a = [];
				for (let e of n.matched) e.eligibility.selectable ? (ce(e.account_id, e.email), i++) : a.push({
					email: e.email,
					account_id: e.account_id,
					reason: fe(e)
				});
				B.value = {
					matchedSelectable: i,
					matchedIneligible: a,
					notFound: n.not_found,
					ambiguous: n.ambiguous
				}, i > 0 && s("notify", `已解析并勾选 ${i} 个可选账号`);
			} catch (e) {
				if (re(e) || t.signal.aborted) return;
				z.value = e instanceof N || e instanceof Error ? e.message : "解析输入账号失败";
			} finally {
				H === t && (H = null, R.value = !1);
			}
		}
		function me(e) {
			e < 1 || e > ne.value || k.value || (T.value = e, Z());
		}
		function he() {
			r.team && s("openAdvancedInAccounts", {
				team_id: r.team.team_id,
				effective_name: r.team.effective_name
			});
		}
		function ge() {
			M.value.length && s("confirmCandidates", {
				accountIds: [...M.value],
				expectedEmails: { ...F }
			});
		}
		function _e() {
			Y(), s("close");
		}
		function ye(e) {
			let t = l.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(n.width === 0 && n.height === 0 || e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && _e();
		}
		return i(() => [W.value, r.team?.team_id], ([e]) => {
			e ? (ie(), Z()) : Y();
		}, { immediate: !0 }), ee(() => {
			Y();
		}), (t, r) => (n(), E("dialog", {
			ref_key: "dialogRef",
			ref: l,
			class: "tm-dialog tm-dialog--xl",
			"aria-labelledby": "teamCandidatePickerTitle",
			"aria-busy": k.value || R.value,
			onCancel: y(_e, ["prevent"]),
			onClick: ye
		}, [
			v("div", Vt, [v("div", null, [
				r[13] ||= v("p", { class: "tm-dialog__kicker" }, "CANDIDATE PICKER", -1),
				r[14] ||= v("h3", {
					id: "teamCandidatePickerTitle",
					class: "tm-dialog__title"
				}, " 选择待加入账号 ", -1),
				v("p", Ht, [e.team ? (n(), E(p, { key: 0 }, [
					r[10] ||= D(" 目标 Team：", -1),
					v("strong", null, g(e.team.effective_name), 1),
					r[11] ||= D(" （", -1),
					v("span", Ut, g(e.team.workspace_id), 1),
					r[12] ||= D("），默认聚焦未归属任何 Team 的账号。 ", -1)
				], 64)) : d("", !0)])
			]), v("div", Wt, [v("button", {
				type: "button",
				class: "tm-btn tm-btn--soft tm-btn--sm",
				disabled: !e.team,
				onClick: he
			}, " 去账号页高级筛选选人 → ", 8, Gt), v("button", {
				type: "button",
				class: "tm-dialog__close",
				"aria-label": "关闭候选选人器",
				onClick: _e
			}, " × ")])]),
			v("div", Kt, [
				v("div", qt, [v("div", Jt, [
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
						onInput: oe,
						onKeydown: f(y(Q, ["prevent"]), ["enter"])
					}, null, 40, Yt), [[te, u.value]]),
					u.value ? (n(), E("button", {
						key: 0,
						type: "button",
						class: "tm-search-box__clear",
						"aria-label": "清空搜索",
						onClick: se
					}, " × ")) : d("", !0)
				]), v("button", {
					type: "button",
					class: "tm-btn tm-btn--sm",
					onClick: r[1] ||= (e) => I.value = !I.value
				}, g(I.value ? "收起批量粘贴解析" : "批量粘贴邮箱或账号 ID"), 1)]),
				v("div", Xt, [
					v("button", {
						type: "button",
						class: b(["tm-pill-toggle", { "is-active": m.value }]),
						onClick: r[2] ||= (e) => {
							m.value = !m.value, Q();
						}
					}, " 仅未归属任何 Team ", 2),
					v("button", {
						type: "button",
						class: b(["tm-pill-toggle", { "is-active": _.value }]),
						onClick: r[3] ||= (e) => {
							_.value = !_.value, Q();
						}
					}, " 有 Token ", 2),
					v("button", {
						type: "button",
						class: b(["tm-pill-toggle", { "is-active": S.value }]),
						onClick: r[4] ||= (e) => {
							S.value = !S.value, Q();
						}
					}, " 有密码 ", 2),
					v("button", {
						type: "button",
						class: b(["tm-pill-toggle", { "is-active": C.value }]),
						onClick: r[5] ||= (e) => {
							C.value = !C.value, Q();
						}
					}, " 已启用 2FA ", 2),
					v("button", {
						type: "button",
						class: b(["tm-pill-toggle", { "is-active": w.value }]),
						onClick: r[6] ||= (e) => {
							w.value = !w.value, Q();
						}
					}, " 包含归档账号 ", 2)
				]),
				I.value ? (n(), E("section", Zt, [
					v("div", Qt, [r[16] ||= v("div", { style: {
						display: "flex",
						"align-items": "center",
						"justify-content": "space-between",
						gap: "8px"
					} }, [v("span", { class: "tm-field__label" }, "粘贴多行或逗号分隔的邮箱 / 本地账号 ID"), v("span", { class: "tm-field__hint" }, "仅查询本地账号集合，不触发登录或远端请求")], -1), a(v("textarea", {
						"onUpdate:modelValue": r[7] ||= (e) => L.value = e,
						rows: "3",
						placeholder: "例如：\nuser-a@example.com\n1024, 1025",
						disabled: R.value
					}, null, 8, $t), [[te, L.value]])]),
					v("div", en, [z.value ? (n(), E("span", tn, g(z.value), 1)) : (n(), E("span", nn, "系统将自动识别可选账号并勾选，列出未命中与同名冲突项")), v("button", {
						type: "button",
						class: "tm-btn tm-btn--soft tm-btn--sm",
						disabled: R.value,
						onClick: $
					}, g(R.value ? "解析中…" : "解析并勾选"), 9, rn)]),
					B.value ? (n(), E("div", an, [
						v("div", on, [
							v("span", null, [
								r[17] ||= D(" 自动勾选可选：", -1),
								v("strong", null, g(B.value.matchedSelectable), 1),
								r[18] ||= D(" 个 ", -1)
							]),
							B.value.matchedIneligible.length ? (n(), E("span", sn, [
								r[19] ||= D(" 不可选跳过：", -1),
								v("strong", null, g(B.value.matchedIneligible.length), 1),
								r[20] ||= D(" 个 ", -1)
							])) : d("", !0),
							B.value.notFound.length ? (n(), E("span", cn, [
								r[21] ||= D(" 未找到：", -1),
								v("strong", null, g(B.value.notFound.length), 1),
								r[22] ||= D(" 项 ", -1)
							])) : d("", !0),
							B.value.ambiguous.length ? (n(), E("span", ln, [
								r[23] ||= D(" 同名冲突：", -1),
								v("strong", null, g(B.value.ambiguous.length), 1),
								r[24] ||= D(" 项 ", -1)
							])) : d("", !0)
						]),
						B.value.matchedIneligible.length ? (n(), E("div", un, [r[25] ||= v("strong", null, "不可选明细：", -1), (n(!0), E(p, null, o(B.value.matchedIneligible, (e) => (n(), E("div", { key: `skip:${e.account_id}` }, g(e.email) + " (#" + g(e.account_id) + ") — " + g(e.reason), 1))), 128))])) : d("", !0),
						B.value.notFound.length ? (n(), E("div", dn, " 未找到项：" + g(B.value.notFound.join("、")), 1)) : d("", !0),
						B.value.ambiguous.length ? (n(), E("div", fn, [r[27] ||= v("strong", null, "同名/多匹配冲突（请手工核对具体 #account_id 后勾选）：", -1), (n(!0), E(p, null, o(B.value.ambiguous, (e) => (n(), E("div", {
							key: e.input,
							style: {
								padding: "8px 10px",
								border: "1px solid var(--ui-color-border)",
								"border-radius": "7px",
								background: "var(--ui-color-surface)",
								display: "grid",
								gap: "5px"
							}
						}, [v("div", null, [r[26] ||= D("输入项：", -1), v("span", pn, g(e.input), 1)]), (n(!0), E(p, null, o(e.candidates, (e) => (n(), E("label", {
							key: e.account_id,
							style: {
								display: "flex",
								"align-items": "center",
								gap: "8px"
							}
						}, [
							v("input", {
								type: "checkbox",
								checked: K.value.has(e.account_id),
								disabled: !e.eligibility.selectable,
								onChange: (t) => ue(e.account_id, e.email, e.eligibility.selectable)
							}, null, 40, mn),
							v("span", null, g(e.email), 1),
							v("span", hn, "#" + g(e.account_id), 1),
							e.archived ? (n(), E("span", gn, "已归档")) : d("", !0),
							v("span", { class: b(["tm-badge", `tm-badge--${pe(e.eligibility.state).tone}`]) }, g(pe(e.eligibility.state).label), 3),
							!e.eligibility.selectable && e.eligibility.reason ? (n(), E("span", _n, g(e.eligibility.reason), 1)) : d("", !0)
						]))), 128))]))), 128))])) : d("", !0)
					])) : d("", !0)
				])) : d("", !0),
				A.value ? (n(), E("div", vn, [v("div", yn, g(A.value), 1), v("button", {
					type: "button",
					class: "tm-btn tm-btn--sm",
					onClick: Z
				}, "重试")])) : d("", !0),
				v("div", bn, [v("button", {
					type: "button",
					class: "tm-link-btn",
					disabled: !q.value.length,
					onClick: de
				}, g(J.value ? "取消勾选本页可选" : `全选本页可选 (${q.value.length})`), 9, xn), v("span", Sn, " 共 " + g(O.value) + " 条候选 · 第 " + g(T.value) + " / " + g(ne.value) + " 页 ", 1)]),
				v("div", {
					class: "tm-candidate-list",
					"aria-busy": k.value
				}, [k.value && !j.value.length ? (n(), E("div", wn, " 正在加载候选账号… ")) : j.value.length ? d("", !0) : (n(), E("div", Tn, " 当前筛选条件下暂无候选账号，可放宽筛选或使用批量粘贴。 ")), (n(!0), E(p, null, o(j.value, (e) => (n(), E("label", {
					key: e.account_id,
					class: b(["tm-candidate-row", { "is-disabled": !e.eligibility.selectable }])
				}, [v("div", En, [v("input", {
					type: "checkbox",
					checked: K.value.has(e.account_id),
					disabled: !e.eligibility.selectable,
					onChange: (t) => ue(e.account_id, e.email, e.eligibility.selectable)
				}, null, 40, Dn), v("div", On, [v("div", kn, [
					v("span", null, g(e.email), 1),
					v("span", An, "#" + g(e.account_id), 1),
					e.archived ? (n(), E("span", jn, "已归档")) : d("", !0),
					e.has_access_token ? (n(), E("span", Mn, "Token")) : d("", !0),
					e.has_account_password ? (n(), E("span", Nn, "密码")) : d("", !0),
					e.totp_enabled ? (n(), E("span", Pn, "2FA")) : d("", !0),
					e.email_invalid ? (n(), E("span", Fn, "邮箱失效")) : d("", !0)
				]), !e.eligibility.selectable || e.active_team ? (n(), E("div", In, g(fe(e)), 1)) : d("", !0)])]), v("div", Ln, [e.eligibility.state === "another_team" && e.active_team ? (n(), E("span", Rn, g(e.active_team.effective_name), 1)) : d("", !0), v("span", { class: b(["tm-badge", `tm-badge--${pe(e.eligibility.state).tone}`]) }, g(pe(e.eligibility.state).label), 3)])], 2))), 128))], 8, Cn),
				ne.value > 1 ? (n(), E("div", zn, [
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: T.value <= 1 || k.value,
						onClick: r[8] ||= (e) => me(T.value - 1)
					}, " 上一页 ", 8, Bn),
					v("span", Vn, g(T.value) + " / " + g(ne.value), 1),
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: T.value >= ne.value || k.value,
						onClick: r[9] ||= (e) => me(T.value + 1)
					}, " 下一页 ", 8, Hn)
				])) : d("", !0)
			]),
			v("div", Un, [v("div", Wn, [v("strong", Gn, "已选 " + g(M.value.length) + " 个候选账号", 1), v("button", {
				type: "button",
				class: "tm-link-btn",
				disabled: !M.value.length,
				onClick: X
			}, " 清空已选 ", 8, Kn)]), v("div", qn, [v("button", {
				type: "button",
				class: "tm-btn",
				onClick: _e
			}, "取消"), v("button", {
				type: "button",
				class: "tm-btn tm-btn--primary",
				disabled: !M.value.length,
				onClick: ge
			}, " 下一步：本地预览与席位核对 ", 8, Jn)])])
		], 40, Bt));
	}
});
// src/features/teams/useTeamPolling.ts
function Zn() {
	return typeof document < "u" && !!document.hidden;
}
function Qn(e) {
	let t = Math.max(500, e.intervalMs ?? 3e3), n = h(!1), r, a = !1, o = !1, s = 0;
	function c() {
		r !== void 0 && (clearTimeout(r), r = void 0), n.value = !1;
	}
	function l() {
		return !o && e.visible() && !Zn() && e.shouldPoll();
	}
	function d(e) {
		c(), l() && e === s && (n.value = !0, r = setTimeout(() => {
			r = void 0, !l() || e !== s ? n.value = !1 : f(e);
		}, t));
	}
	async function f(t) {
		if (!a && l() && t === s) {
			a = !0, n.value = !0;
			try {
				await e.onPoll();
			} finally {
				a = !1, !o && t === s && l() ? d(t) : n.value = !1;
			}
		}
	}
	async function p() {
		c(), s += 1, await f(s);
	}
	function m() {
		s += 1, c();
	}
	function g(e) {
		l() ? e ? p() : r === void 0 && !a && d(s) : m();
	}
	function _() {
		Zn() ? m() : g(!0);
	}
	return typeof document < "u" && document.addEventListener("visibilitychange", _), i([() => e.visible(), () => e.shouldPoll()], ([e, t], n) => {
		g(n?.[0] === !1 && e === !0 && t);
	}, { immediate: !0 }), u(() => {
		o = !0, m(), typeof document < "u" && document.removeEventListener("visibilitychange", _);
	}), {
		isPolling: n,
		triggerNow: p,
		stop: m
	};
}
// src/features/teams/TeamInvitationsTab.vue?vue&type=script&setup=true&lang.ts
var $n = {
	class: "ui-list",
	"aria-label": "邀请与入组记录"
}, er = { class: "ui-list-count" }, tr = { key: 0 }, nr = { class: "tm-search-box" }, rr = ["disabled"], ir = ["disabled"], ar = ["disabled"], or = {
	key: 0,
	class: "ui-list-bulkbar"
}, sr = { class: "ui-list-bulkbar__count" }, cr = ["aria-busy"], lr = { scope: "col" }, ur = { style: {
	display: "inline-flex",
	"align-items": "center",
	gap: "10px"
} }, dr = [
	"checked",
	"indeterminate",
	"disabled"
], fr = { scope: "col" }, pr = { style: {
	display: "grid",
	gap: "10px"
} }, mr = { class: "tm-field" }, hr = ["value"], gr = ["value"], _r = { class: "tm-field" }, vr = ["value"], yr = ["value"], br = { class: "list-filter-actions" }, xr = { scope: "col" }, Sr = { style: {
	display: "grid",
	gap: "10px"
} }, Cr = { class: "tm-field" }, wr = ["value"], Tr = ["value"], Er = { class: "tm-field" }, Dr = ["value"], Or = ["value"], kr = { class: "list-filter-actions" }, Ar = { scope: "col" }, jr = { scope: "col" }, Mr = { "data-label": "目标账号" }, Nr = { style: {
	display: "flex",
	"align-items": "flex-start",
	gap: "10px",
	"min-width": "0"
} }, Pr = [
	"aria-label",
	"checked",
	"onChange"
], Fr = { class: "tm-cell-stack" }, Ir = { class: "tm-cell-primary" }, Lr = ["title"], Rr = {
	class: "tm-cell-sub",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "6px",
		"flex-wrap": "wrap"
	}
}, zr = ["onClick"], Br = {
	key: 1,
	class: "tm-badge tm-badge--neutral"
}, Vr = {
	key: 2,
	class: "tm-badge tm-badge--neutral"
}, Hr = {
	key: 3,
	class: "tm-badge tm-badge--warning"
}, Ur = {
	key: 4,
	class: "tm-badge tm-badge--danger"
}, Wr = { "data-label": "业务事实" }, Gr = { class: "tm-cell-stack" }, Kr = { class: "tm-cell-primary" }, qr = { class: "tm-cell-sub" }, Jr = { "data-label": "执行与阶段" }, Yr = { class: "tm-cell-stack" }, Xr = { class: "tm-cell-primary" }, Zr = {
	key: 0,
	class: "tm-badge__dot"
}, Qr = ["title"], $r = { "data-label": "结果摘要" }, ei = { key: 0 }, ti = { class: "tm-mono" }, ni = { "data-label": "时间" }, ri = { class: "tm-cell-stack" }, ii = { class: "tm-cell-sub" }, ai = { class: "tm-cell-sub" }, oi = { "data-label": "操作" }, si = { class: "tm-row-actions" }, ci = ["disabled", "onClick"], li = ["disabled", "onClick"], ui = ["onClick"], di = {
	key: 3,
	class: "tm-cell-sub"
}, fi = /* @__PURE__ */ t({
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
		let u = e, S = s, C = [
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
				value: "unknown",
				label: "邀请状态未知"
			}
		], w = [
			{
				value: "joined",
				label: "已加入"
			},
			{
				value: "not_joined",
				label: "未入组"
			},
			{
				value: "removed",
				label: "已移除"
			},
			{
				value: "left",
				label: "已退出"
			},
			{
				value: "unknown",
				label: "待核实"
			}
		], k = [
			{
				value: "idle",
				label: "未执行"
			},
			{
				value: "queued",
				label: "排队中"
			},
			{
				value: "running",
				label: "执行中"
			},
			{
				value: "waiting_user",
				label: "等待人工处理"
			},
			{
				value: "succeeded",
				label: "已完成"
			},
			{
				value: "failed",
				label: "执行失败"
			},
			{
				value: "cancelled",
				label: "已取消"
			}
		], A = [
			{
				value: "precheck_capacity",
				label: "预检席位与容量"
			},
			{
				value: "send_invite",
				label: "母号发送邀请"
			},
			{
				value: "await_invite_mail",
				label: "等待接收邀请邮件"
			},
			{
				value: "open_invite_link",
				label: "解析并打开邀请链接"
			},
			{
				value: "authenticate_target",
				label: "认证目标账号"
			},
			{
				value: "accept_workspace_join",
				label: "确认加入工作区"
			},
			{
				value: "verify_membership",
				label: "回查工作区成员状态"
			}
		], j = c({
			page: 1,
			page_size: 20,
			q: "",
			invitation_state: "",
			membership_state: "",
			execution_status: "",
			stage: "",
			join_request_id: u.joinRequestId || ""
		}), M = h(""), N = h(null), P = h(!1), F = h(!1), W = h(""), G = h([]), K = h(0), ne = h({}), q = h(/* @__PURE__ */ new Set()), J = h(/* @__PURE__ */ new Set()), { widths: re, total: Y, resize: X, resizeWithKeyboard: ae } = I({
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
		}), Z, oe = null, ce = 0;
		function le(e) {
			return `tm-badge--${e}`;
		}
		function de(e, t) {
			let n = ne.value[e];
			if (!n) return null;
			let r = n.find((e) => e.value === t);
			return r ? r.count : null;
		}
		function fe(e) {
			if (e.error?.reason_code === "team_target_auth_missing") return !0;
			let t = e.target_account;
			return !!t.account_id && !t.has_access_token && !t.has_account_password;
		}
		let pe = x(() => G.value.length > 0 && G.value.every((e) => q.value.has(e.invitation_id))), $ = x(() => !pe.value && G.value.some((e) => q.value.has(e.invitation_id)));
		function me(e) {
			let t = new Set(q.value);
			for (let n of G.value) e ? t.add(n.invitation_id) : t.delete(n.invitation_id);
			q.value = t;
		}
		function ve(e, t) {
			let n = new Set(q.value);
			t ? n.add(e) : n.delete(e), q.value = n;
		}
		function ye() {
			q.value = /* @__PURE__ */ new Set();
		}
		let be = x(() => {
			let e = [];
			return j.join_request_id && e.push({
				key: "join_request_id",
				label: `入组批次：#${j.join_request_id}`,
				removeLabel: "清除批次过滤"
			}), j.q && e.push({
				key: "q",
				label: `关键词：${j.q}`,
				removeLabel: "清除关键词筛选"
			}), j.invitation_state && e.push({
				key: "invitation_state",
				label: `邀请状态：${Q(j.invitation_state)}`,
				removeLabel: "清除邀请状态筛选"
			}), j.membership_state && e.push({
				key: "membership_state",
				label: `成员状态：${ie(j.membership_state)}`,
				removeLabel: "清除成员状态筛选"
			}), j.execution_status && e.push({
				key: "execution_status",
				label: `执行状态：${se(j.execution_status)}`,
				removeLabel: "清除执行状态筛选"
			}), j.stage && e.push({
				key: "stage",
				label: `阶段：${ue(j.stage)}`,
				removeLabel: "清除阶段筛选"
			}), e;
		}), xe = x(() => be.value.length > 0);
		function Se(e) {
			e === "q" ? (clearTimeout(Z), M.value = "", j.q = "") : e === "join_request_id" ? (j.join_request_id = "", S("clear-join-request")) : e === "invitation_state" ? j.invitation_state = "" : e === "membership_state" ? j.membership_state = "" : e === "execution_status" ? j.execution_status = "" : e === "stage" && (j.stage = ""), j.page = 1, ke();
		}
		function Ce() {
			clearTimeout(Z), M.value = "", j.q = "", j.invitation_state = "", j.membership_state = "", j.execution_status = "", j.stage = "", j.join_request_id && (j.join_request_id = "", S("clear-join-request")), j.page = 1, ke();
		}
		function we() {
			clearTimeout(Z), M.value = "", j.q !== "" && (j.q = "", j.page = 1, ke());
		}
		function Te(e, t) {
			j[e] = t, j.page = 1, ke();
		}
		function Ee(e, t) {
			j[e] = t, j.page = 1, ke();
		}
		function De(e) {
			j.page = e, ke();
		}
		function Oe(e) {
			j.page_size = e, j.page = 1, ke();
		}
		async function ke(e = {}) {
			if (!u.teamId) return;
			oe?.abort();
			let t = new AbortController();
			oe = t;
			let n = ++ce;
			e.silent || (P.value = !0), W.value = "";
			let r = {
				page: j.page,
				page_size: j.page_size,
				include_facets: e.includeFacets ?? 1,
				...j.q ? { q: j.q } : {},
				...j.invitation_state ? { invitation_state: j.invitation_state } : {},
				...j.membership_state ? { membership_state: j.membership_state } : {},
				...j.execution_status ? { execution_status: j.execution_status } : {},
				...j.stage ? { stage: j.stage } : {},
				...j.join_request_id ? { join_request_id: j.join_request_id } : {}
			};
			try {
				let e = await u.api.listInvitations(u.teamId, r, t.signal);
				if (n !== ce) return;
				G.value = e.items, K.value = e.total, e.facets && Object.keys(e.facets).length > 0 && (ne.value = e.facets);
			} catch (r) {
				if (t.signal.aborted || n !== ce) return;
				let i = r instanceof Error ? r.message : "加载邀请与入组记录失败";
				e.silent || (W.value = i);
			} finally {
				oe === t && (oe = null), n === ce && !e.silent && (P.value = !1);
			}
		}
		async function Ae(e) {
			let t = new Set(J.value);
			t.add(e.invitation_id), J.value = t;
			try {
				let t = await u.api.continueInvitation(u.teamId, e.invitation_id);
				u.callbacks.notify(t.outcome === "reused_active" ? `已复用当前进行中的入组执行（${e.email}）` : `已受理继续加入（${e.email}）`), await ke({
					silent: !0,
					includeFacets: 0
				}), S("refresh-team");
			} catch (e) {
				u.callbacks.notify(e instanceof Error ? e.message : "继续加入提交失败");
			} finally {
				let t = new Set(J.value);
				t.delete(e.invitation_id), J.value = t;
			}
		}
		async function je(e) {
			let t = new Set(J.value);
			t.add(e.invitation_id), J.value = t;
			try {
				let t = await u.api.retryInvitation(u.teamId, e.invitation_id);
				u.callbacks.notify(t.outcome === "reused_active" ? `已复用当前活跃执行（${e.email}）` : `已创建重跑任务（${e.email}）`), await ke({
					silent: !0,
					includeFacets: 0
				}), S("refresh-team");
			} catch (e) {
				u.callbacks.notify(e instanceof Error ? e.message : "重跑提交失败");
			} finally {
				let t = new Set(J.value);
				t.delete(e.invitation_id), J.value = t;
			}
		}
		async function Me() {
			let e = [...q.value];
			if (e.length && !F.value) {
				F.value = !0;
				try {
					let t = await u.api.continueInvitationsBulk(u.teamId, e);
					u.callbacks.notify(`批量继续加入已受理：新增排队 ${t.queued_count}，复用 ${t.reused_active_count}，跳过 ${t.skipped_count}`), ye(), await ke({
						silent: !0,
						includeFacets: 0
					}), S("refresh-team");
				} catch (e) {
					u.callbacks.notify(e instanceof Error ? e.message : "批量继续加入失败");
				} finally {
					F.value = !1;
				}
			}
		}
		async function Ne() {
			let e = [...q.value];
			if (e.length && !F.value) {
				F.value = !0;
				try {
					let t = await u.api.retryInvitationsBulk(u.teamId, e);
					u.callbacks.notify(`批量重跑已受理：新增排队 ${t.queued_count}，复用 ${t.reused_active_count}，跳过 ${t.skipped_count}`), ye(), await ke({
						silent: !0,
						includeFacets: 0
					}), S("refresh-team");
				} catch (e) {
					u.callbacks.notify(e instanceof Error ? e.message : "批量重跑失败");
				} finally {
					F.value = !1;
				}
			}
		}
		return Qn({
			visible: () => u.visible,
			shouldPoll: () => G.value.some((e) => e.execution_status === "queued" || e.execution_status === "running"),
			onPoll: async () => {
				await ke({
					silent: !0,
					includeFacets: 0
				}), S("refresh-team");
			},
			intervalMs: 3e3
		}), i(M, (e) => {
			clearTimeout(Z);
			let t = e.trim();
			t !== j.q && (Z = setTimeout(() => {
				j.q = t, j.page = 1, ke();
			}, 250));
		}), i(() => u.joinRequestId, (e) => {
			let t = e || "";
			t !== j.join_request_id && (j.join_request_id = t, j.page = 1, ke());
		}), i(() => u.teamId, () => {
			j.page = 1, ye(), G.value = [], K.value = 0, ne.value = {}, ke();
		}, { immediate: !0 }), ee(() => {
			clearTimeout(Z), oe?.abort();
		}), t({ refresh: () => ke() }), (t, i) => (n(), E("section", $n, [
			l(U, { filtered: xe.value }, {
				actions: r(() => [
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--soft",
						disabled: !q.value.size || F.value,
						onClick: i[2] ||= (e) => void Me()
					}, g(F.value ? "处理中…" : "批量继续加入"), 9, rr),
					v("button", {
						type: "button",
						class: "tm-btn",
						disabled: !q.value.size || F.value,
						onClick: i[3] ||= (e) => void Ne()
					}, " 批量重跑 ", 8, ir),
					v("button", {
						type: "button",
						class: "tm-btn ui-refresh-button",
						disabled: P.value,
						onClick: i[4] ||= (e) => void ke()
					}, g(P.value ? "刷新中…" : "刷新"), 9, ar)
				]),
				default: r(() => [
					v("span", er, [D(" 共 " + g(K.value.toLocaleString()) + " 条邀请记录 ", 1), q.value.size ? (n(), E("small", tr, "已选 " + g(q.value.size) + " 项", 1)) : d("", !0)]),
					v("div", nr, [
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
							"onUpdate:modelValue": i[0] ||= (e) => M.value = e,
							type: "search",
							"aria-label": "搜索邀请记录",
							placeholder: "搜索邮箱 / 本地账号 ID",
							onKeydown: i[1] ||= f(y((e) => {
								j.q = M.value.trim(), j.page = 1, ke();
							}, ["prevent"]), ["enter"])
						}, null, 544), [[te, M.value]]),
						M.value ? (n(), E("button", {
							key: 0,
							type: "button",
							class: "tm-search-box__clear",
							"aria-label": "清空搜索",
							onClick: we
						}, " × ")) : d("", !0)
					]),
					l(B, {
						items: be.value,
						onRemove: Se
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			q.value.size ? (n(), E("div", or, [v("span", sr, "已跨页选中 " + g(q.value.size) + " 条邀请记录", 1), v("button", {
				type: "button",
				class: "tm-btn tm-btn--ghost tm-btn--sm",
				onClick: ye
			}, " 清空选择 ")])) : d("", !0),
			v("div", {
				class: "ui-table-wrap ui-table-scroll",
				tabindex: "0",
				"aria-label": "邀请与入组表格，可横向滚动",
				"aria-busy": P.value
			}, [v("table", {
				class: "ui-table ui-table--sticky-end ui-table--cards",
				style: m({ "--ui-table-width": `${T(Y)}px` })
			}, [
				i[41] ||= v("caption", { class: "ui-sr-only" }, "工作区邀请记录与自动入组状态（严格六列）", -1),
				v("colgroup", null, [(n(!0), E(p, null, o(T(re), (e, t) => (n(), E("col", {
					key: t,
					style: m({ width: `${e}px` })
				}, null, 4))), 128))]),
				v("thead", null, [v("tr", null, [
					v("th", lr, [v("span", ur, [v("input", {
						type: "checkbox",
						"aria-label": "全选当前页邀请记录",
						checked: pe.value,
						indeterminate: $.value,
						disabled: !G.value.length,
						onChange: i[5] ||= (e) => me(e.target.checked)
					}, null, 40, dr), i[28] ||= v("span", null, "目标账号", -1)]), l(L, {
						label: "目标账号",
						onStart: i[6] ||= (e) => T(X)(0, e),
						onNudge: i[7] ||= (e) => T(ae)(0, e)
					})]),
					v("th", fr, [l(R, {
						label: "业务事实",
						active: !!(j.invitation_state || j.membership_state),
						summary: [j.invitation_state ? T(Q)(j.invitation_state) : "", j.membership_state ? T(ie)(j.membership_state) : ""].filter(Boolean).join(" · "),
						open: e.visible && N.value === "business",
						"onUpdate:open": i[12] ||= (e) => N.value = e ? "business" : null
					}, {
						default: r(() => [v("div", pr, [
							v("label", mr, [i[30] ||= v("span", { class: "tm-field__label" }, "邀请状态", -1), v("select", {
								value: j.invitation_state,
								"aria-label": "筛选邀请状态",
								onChange: i[8] ||= (e) => Te("invitation_state", e.target.value)
							}, [i[29] ||= v("option", { value: "" }, "全部邀请状态", -1), (n(), E(p, null, o(C, (e) => v("option", {
								key: e.value,
								value: e.value
							}, g(e.label) + g(de("invitation_state", e.value) === null ? "" : ` (${de("invitation_state", e.value)})`), 9, gr)), 64))], 40, hr)]),
							v("label", _r, [i[32] ||= v("span", { class: "tm-field__label" }, "成员状态", -1), v("select", {
								value: j.membership_state,
								"aria-label": "筛选成员状态",
								onChange: i[9] ||= (e) => Te("membership_state", e.target.value)
							}, [i[31] ||= v("option", { value: "" }, "全部成员状态", -1), (n(), E(p, null, o(w, (e) => v("option", {
								key: e.value,
								value: e.value
							}, g(e.label) + g(de("membership_state", e.value) === null ? "" : ` (${de("membership_state", e.value)})`), 9, yr)), 64))], 40, vr)]),
							v("div", br, [v("button", {
								type: "button",
								onClick: i[10] ||= (e) => {
									j.invitation_state = "", j.membership_state = "", j.page = 1, N.value = null, ke();
								}
							}, " 清除 "), v("button", {
								type: "button",
								class: "list-filter-primary",
								onClick: i[11] ||= (e) => N.value = null
							}, "完成")])
						])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(L, {
						label: "业务事实",
						onStart: i[13] ||= (e) => T(X)(1, e),
						onNudge: i[14] ||= (e) => T(ae)(1, e)
					})]),
					v("th", xr, [l(R, {
						label: "执行与阶段",
						active: !!(j.execution_status || j.stage),
						summary: [j.execution_status ? T(se)(j.execution_status) : "", j.stage ? T(ue)(j.stage) : ""].filter(Boolean).join(" · "),
						open: e.visible && N.value === "execution",
						"onUpdate:open": i[19] ||= (e) => N.value = e ? "execution" : null
					}, {
						default: r(() => [v("div", Sr, [
							v("label", Cr, [i[34] ||= v("span", { class: "tm-field__label" }, "执行状态", -1), v("select", {
								value: j.execution_status,
								"aria-label": "筛选执行状态",
								onChange: i[15] ||= (e) => Ee("execution_status", e.target.value)
							}, [i[33] ||= v("option", { value: "" }, "全部执行状态", -1), (n(), E(p, null, o(k, (e) => v("option", {
								key: e.value,
								value: e.value
							}, g(e.label) + g(de("execution_status", e.value) === null ? "" : ` (${de("execution_status", e.value)})`), 9, Tr)), 64))], 40, wr)]),
							v("label", Er, [i[36] ||= v("span", { class: "tm-field__label" }, "当前阶段", -1), v("select", {
								value: j.stage,
								"aria-label": "筛选当前阶段",
								onChange: i[16] ||= (e) => Ee("stage", e.target.value)
							}, [i[35] ||= v("option", { value: "" }, "全部阶段", -1), (n(), E(p, null, o(A, (e) => v("option", {
								key: e.value,
								value: e.value
							}, g(e.label) + g(de("stage", e.value) === null ? "" : ` (${de("stage", e.value)})`), 9, Or)), 64))], 40, Dr)]),
							v("div", kr, [v("button", {
								type: "button",
								onClick: i[17] ||= (e) => {
									j.execution_status = "", j.stage = "", j.page = 1, N.value = null, ke();
								}
							}, " 清除 "), v("button", {
								type: "button",
								class: "list-filter-primary",
								onClick: i[18] ||= (e) => N.value = null
							}, "完成")])
						])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(L, {
						label: "执行与阶段",
						onStart: i[20] ||= (e) => T(X)(2, e),
						onNudge: i[21] ||= (e) => T(ae)(2, e)
					})]),
					v("th", Ar, [i[37] ||= D(" 结果摘要 ", -1), l(L, {
						label: "结果摘要",
						onStart: i[22] ||= (e) => T(X)(3, e),
						onNudge: i[23] ||= (e) => T(ae)(3, e)
					})]),
					v("th", jr, [i[38] ||= D(" 时间 ", -1), l(L, {
						label: "时间",
						onStart: i[24] ||= (e) => T(X)(4, e),
						onNudge: i[25] ||= (e) => T(ae)(4, e)
					})]),
					i[39] ||= v("th", { scope: "col" }, "操作", -1)
				])]),
				v("tbody", null, [(n(!0), E(p, null, o(G.value, (t) => (n(), E("tr", {
					key: t.invitation_id,
					class: b({ "is-selected": q.value.has(t.invitation_id) })
				}, [
					v("td", Mr, [v("div", Nr, [v("input", {
						type: "checkbox",
						style: { "margin-top": "3px" },
						"aria-label": `选择邀请记录 ${t.email}`,
						checked: q.value.has(t.invitation_id),
						onChange: (e) => ve(t.invitation_id, e.target.checked)
					}, null, 40, Pr), v("div", Fr, [v("div", Ir, [v("span", { title: t.email }, g(t.email || t.target_account.email || "未返回"), 9, Lr)]), v("div", Rr, [
						t.target_account.account_id ? (n(), E("button", {
							key: 0,
							type: "button",
							class: "tm-link-btn tm-tabular",
							onClick: (n) => e.callbacks.openAccountDetail(t.target_account.account_id)
						}, " #" + g(t.target_account.account_id), 9, zr)) : (n(), E("span", Br, "未入库")),
						t.target_account.archived ? (n(), E("span", Vr, "已归档")) : d("", !0),
						fe(t) ? (n(), E("span", Hr, "缺认证材料")) : d("", !0),
						t.target_account.email_invalid ? (n(), E("span", Ur, "邮箱失效")) : d("", !0)
					])])])]),
					v("td", Wr, [v("div", Gr, [v("div", Kr, [v("span", { class: b(["tm-badge", le(T(he)(t).tone)]) }, g(T(he)(t).primary), 3)]), v("div", qr, g(T(he)(t).secondary), 1)])]),
					v("td", Jr, [v("div", Yr, [v("div", Xr, [v("span", { class: b(["tm-badge", le(T(ge)(t).tone)]) }, [t.execution_status === "queued" || t.execution_status === "running" ? (n(), E("span", Zr)) : d("", !0), D(" " + g(T(ge)(t).primary), 1)], 2)]), v("div", {
						class: "tm-cell-sub",
						title: T(ge)(t).secondary
					}, g(T(ge)(t).secondary), 9, Qr)])]),
					v("td", $r, [l(H, {
						label: T(_e)(t).label,
						secondary: T(_e)(t).secondary,
						tone: T(_e)(t).tone,
						title: T(_e)(t).detail || T(_e)(t).label
					}, O({ _: 2 }, [T(_e)(t).detail ? {
						name: "details",
						fn: r(() => [t.error?.reason_code ? (n(), E("p", ei, [i[40] ||= D(" 原因码：", -1), v("span", ti, g(t.error.reason_code), 1)])) : d("", !0), v("p", null, g(T(_e)(t).detail), 1)]),
						key: "0"
					} : void 0]), 1032, [
						"label",
						"secondary",
						"tone",
						"title"
					])]),
					v("td", ni, [v("div", ri, [v("div", ii, " 邀请于：" + g(t.invited_at ? e.callbacks.formatDateTime(t.invited_at) : "—"), 1), v("div", ai, g(t.accepted_at ? `接受于：${e.callbacks.formatDateTime(t.accepted_at)}` : `更新于：${e.callbacks.formatDateTime(t.updated_at)}`), 1)])]),
					v("td", oi, [v("div", si, [
						t.actions.can_continue ? (n(), E("button", {
							key: 0,
							type: "button",
							class: "tm-btn tm-btn--sm tm-btn--soft",
							disabled: J.value.has(t.invitation_id),
							onClick: (e) => void Ae(t)
						}, " 继续加入 ", 8, ci)) : d("", !0),
						t.actions.can_retry ? (n(), E("button", {
							key: 1,
							type: "button",
							class: "tm-btn tm-btn--sm",
							disabled: J.value.has(t.invitation_id),
							onClick: (e) => void je(t)
						}, " 重跑 ", 8, li)) : d("", !0),
						t.actions.can_open_task && t.latest_task_id ? (n(), E("button", {
							key: 2,
							type: "button",
							class: "tm-btn tm-btn--sm tm-btn--ghost",
							onClick: (n) => e.callbacks.openTask(t.latest_task_id, t.latest_run_id)
						}, " 查看任务 ", 8, ui)) : d("", !0),
						!t.actions.can_continue && !t.actions.can_retry && !(t.actions.can_open_task && t.latest_task_id) ? (n(), E("span", di, " — ")) : d("", !0)
					])])
				], 2))), 128)), G.value.length ? d("", !0) : (n(), _(z, {
					key: 0,
					colspan: 6,
					loading: P.value,
					error: W.value,
					"loading-title": "正在加载邀请与入组记录",
					"loading-text": "同步当前工作区的远端邀请与自动加入进度",
					"error-title": "加载邀请记录失败",
					title: xe.value ? "没有匹配的邀请记录" : "暂无邀请与入组记录",
					text: xe.value ? "可调整搜索或筛选条件后重试。" : "点击上方「加入账号」批量发起邀请，或等待工作区同步返回远端待接受邀请。",
					"retry-label": "重试",
					onRetry: i[26] ||= (e) => void ke()
				}, {
					default: r(() => [!P.value && !W.value && xe.value ? (n(), E("button", {
						key: 0,
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
			], 4)], 8, cr),
			l(V, {
				page: j.page,
				size: j.page_size,
				total: K.value,
				busy: P.value,
				label: "邀请记录分页",
				"onUpdate:page": De,
				"onUpdate:size": Oe
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy"
			])
		]));
	}
}), pi = {
	class: "ui-list",
	"aria-label": "工作区成员列表"
}, mi = { class: "ui-list-count" }, hi = { class: "tm-search-box" }, gi = ["disabled"], _i = ["aria-busy"], vi = { scope: "col" }, yi = { scope: "col" }, bi = { class: "list-filter-options" }, xi = [
	"value",
	"checked",
	"onChange"
], Si = { key: 0 }, Ci = { class: "list-filter-actions" }, wi = { scope: "col" }, Ti = { class: "list-filter-options" }, Ei = { class: "list-filter-option" }, Di = ["checked"], Oi = [
	"value",
	"checked",
	"onChange"
], ki = { key: 0 }, Ai = { class: "list-filter-actions" }, ji = { scope: "col" }, Mi = { class: "list-filter-options" }, Ni = [
	"value",
	"checked",
	"onChange"
], Pi = { key: 0 }, Fi = { class: "list-filter-actions" }, Ii = { scope: "col" }, Li = { scope: "col" }, Ri = { "data-label": "成员" }, zi = { class: "tm-cell-stack" }, Bi = { class: "tm-cell-primary" }, Vi = ["title"], Hi = { class: "tm-cell-sub" }, Ui = { "data-label": "本地账号" }, Wi = {
	key: 0,
	class: "tm-cell-stack"
}, Gi = { class: "tm-cell-primary" }, Ki = ["onClick"], qi = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, Ji = {
	key: 0,
	class: "tm-cell-sub"
}, Yi = {
	key: 1,
	class: "tm-badge tm-badge--neutral"
}, Xi = { "data-label": "角色" }, Zi = { "data-label": "成员状态" }, Qi = { class: "tm-cell-stack" }, $i = { class: "tm-cell-primary" }, ea = { class: "tm-cell-sub" }, ta = { "data-label": "加入时间" }, na = { class: "ui-time" }, ra = { "data-label": "最近任务" }, ia = ["onClick"], aa = {
	key: 1,
	class: "tm-cell-sub"
}, oa = { "data-label": "操作" }, sa = { class: "tm-row-actions" }, ca = ["onClick"], la = ["onClick"], ua = {
	key: 2,
	class: "tm-cell-sub"
}, da = /* @__PURE__ */ t({
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
		], S = [
			{
				value: "joined",
				label: "已加入"
			},
			{
				value: "removed",
				label: "已移除"
			},
			{
				value: "left",
				label: "已退出"
			},
			{
				value: "all",
				label: "全部状态"
			}
		], C = [
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
		], w = c({
			page: 1,
			page_size: 20,
			q: "",
			role: "",
			membership_state: "joined",
			linked: "all"
		}), O = h(""), k = h(null), A = h(!1), j = h(""), M = h([]), N = h(0), P = h({}), { widths: F, total: H, resize: W, resizeWithKeyboard: G } = I({
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
		}), K, J = null, re = 0;
		function Y(e) {
			return `tm-badge--${e}`;
		}
		function X(e, t) {
			let n = P.value[e];
			if (!n) return null;
			let r = n.find((e) => e.value === t);
			return r ? r.count : null;
		}
		let Z = x(() => {
			let e = [];
			if (w.q && e.push({
				key: "q",
				label: `关键词：${w.q}`,
				removeLabel: "清除关键词筛选"
			}), w.linked !== "all") {
				let t = C.find((e) => e.value === w.linked)?.label ?? w.linked;
				e.push({
					key: "linked",
					label: `本地账号：${t}`,
					removeLabel: "清除本地账号筛选"
				});
			}
			if (w.role && e.push({
				key: "role",
				label: `角色：${ne(w.role)}`,
				removeLabel: "清除角色筛选"
			}), w.membership_state !== "joined") {
				let t = S.find((e) => e.value === w.membership_state)?.label ?? ie(w.membership_state);
				e.push({
					key: "membership_state",
					label: `成员状态：${t}`,
					removeLabel: "恢复默认仅查看已加入"
				});
			}
			return e;
		}), Q = x(() => Z.value.length > 0);
		function oe(e) {
			e === "q" ? (clearTimeout(K), O.value = "", w.q = "") : e === "linked" ? w.linked = "all" : e === "role" ? w.role = "" : e === "membership_state" && (w.membership_state = "joined"), w.page = 1, $();
		}
		function se() {
			clearTimeout(K), O.value = "", w.q = "", w.role = "", w.membership_state = "joined", w.linked = "all", w.page = 1, $();
		}
		function ce(e) {
			w.linked = e, w.page = 1, k.value = null, $();
		}
		function le(e) {
			w.role = e, w.page = 1, k.value = null, $();
		}
		function ue(e) {
			w.membership_state = e, w.page = 1, k.value = null, $();
		}
		function de() {
			clearTimeout(K), O.value = "", w.q !== "" && (w.q = "", w.page = 1, $());
		}
		function fe(e) {
			w.page = e, $();
		}
		function pe(e) {
			w.page_size = e, w.page = 1, $();
		}
		async function $(e = {}) {
			if (!s.teamId) return;
			J?.abort();
			let t = new AbortController();
			J = t;
			let n = ++re;
			e.silent || (A.value = !0), j.value = "";
			let r = {
				page: w.page,
				page_size: w.page_size,
				include_facets: e.includeFacets ?? 1,
				...w.q ? { q: w.q } : {},
				...w.role ? { role: w.role } : {},
				membership_state: w.membership_state || "joined",
				linked: w.linked
			};
			try {
				let e = await s.api.listMembers(s.teamId, r, t.signal);
				if (n !== re) return;
				M.value = e.items, N.value = e.total, e.facets && Object.keys(e.facets).length > 0 && (P.value = e.facets);
			} catch (r) {
				if (t.signal.aborted || n !== re) return;
				let i = r instanceof Error ? r.message : "加载工作区成员失败";
				e.silent || (j.value = i);
			} finally {
				J === t && (J = null), n === re && !e.silent && (A.value = !1);
			}
		}
		return i(O, (e) => {
			clearTimeout(K);
			let t = e.trim();
			t !== w.q && (K = setTimeout(() => {
				w.q = t, w.page = 1, $();
			}, 250));
		}), i(() => s.teamId, () => {
			w.page = 1, M.value = [], N.value = 0, P.value = {}, $();
		}, { immediate: !0 }), ee(() => {
			clearTimeout(K), J?.abort();
		}), t({ refresh: () => $() }), (t, i) => (n(), E("section", pi, [
			l(U, { filtered: Q.value }, {
				actions: r(() => [v("button", {
					type: "button",
					class: "tm-btn ui-refresh-button",
					disabled: A.value,
					onClick: i[2] ||= (e) => void $()
				}, g(A.value ? "刷新中…" : "刷新"), 9, gi)]),
				default: r(() => [
					v("span", mi, "共 " + g(N.value.toLocaleString()) + " 名成员", 1),
					v("div", hi, [
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
							"onUpdate:modelValue": i[0] ||= (e) => O.value = e,
							type: "search",
							"aria-label": "搜索工作区成员",
							placeholder: "搜索邮箱 / 显示名 / 本地 ID",
							onKeydown: i[1] ||= f(y((e) => {
								w.q = O.value.trim(), w.page = 1, $();
							}, ["prevent"]), ["enter"])
						}, null, 544), [[te, O.value]]),
						O.value ? (n(), E("button", {
							key: 0,
							type: "button",
							class: "tm-search-box__clear",
							"aria-label": "清空搜索",
							onClick: de
						}, " × ")) : d("", !0)
					]),
					l(B, {
						items: Z.value,
						onRemove: oe
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			v("div", {
				class: "ui-table-wrap ui-table-scroll",
				tabindex: "0",
				"aria-label": "成员表格，可横向滚动",
				"aria-busy": A.value
			}, [v("table", {
				class: "ui-table ui-table--sticky-end ui-table--cards",
				style: m({ "--ui-table-width": `${T(H)}px` })
			}, [
				i[35] ||= v("caption", { class: "ui-sr-only" }, "工作区已同步成员列表", -1),
				v("colgroup", null, [(n(!0), E(p, null, o(T(F), (e, t) => (n(), E("col", {
					key: t,
					style: m({ width: `${e}px` })
				}, null, 4))), 128))]),
				v("thead", null, [v("tr", null, [
					v("th", vi, [i[27] ||= D(" 成员 ", -1), l(L, {
						label: "成员",
						onStart: i[3] ||= (e) => T(W)(0, e),
						onNudge: i[4] ||= (e) => T(G)(0, e)
					})]),
					v("th", yi, [l(R, {
						label: "本地账号",
						active: w.linked !== "all",
						summary: C.find((e) => e.value === w.linked)?.label,
						open: e.visible && k.value === "linked",
						"onUpdate:open": i[7] ||= (e) => k.value = e ? "linked" : null
					}, {
						default: r(() => [v("fieldset", bi, [i[28] ||= v("legend", { class: "ui-sr-only" }, "本地账号关联筛选", -1), (n(), E(p, null, o(C, (e) => v("label", {
							key: e.value,
							class: "list-filter-option"
						}, [
							v("input", {
								type: "radio",
								name: "member-linked",
								value: e.value,
								checked: w.linked === e.value,
								onChange: (t) => ce(e.value)
							}, null, 40, xi),
							v("span", null, g(e.label), 1),
							X("linked", e.value) === null ? d("", !0) : (n(), E("small", Si, g(X("linked", e.value)), 1))
						])), 64))]), v("div", Ci, [v("button", {
							type: "button",
							onClick: i[5] ||= (e) => ce("all")
						}, "重置"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[6] ||= (e) => k.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(L, {
						label: "本地账号",
						onStart: i[8] ||= (e) => T(W)(1, e),
						onNudge: i[9] ||= (e) => T(G)(1, e)
					})]),
					v("th", wi, [l(R, {
						label: "角色",
						active: !!w.role,
						summary: w.role ? T(ne)(w.role) : "",
						open: e.visible && k.value === "role",
						"onUpdate:open": i[13] ||= (e) => k.value = e ? "role" : null
					}, {
						default: r(() => [v("fieldset", Ti, [
							i[30] ||= v("legend", { class: "ui-sr-only" }, "成员角色筛选", -1),
							v("label", Ei, [v("input", {
								type: "radio",
								name: "member-role",
								value: "",
								checked: !w.role,
								onChange: i[10] ||= (e) => le("")
							}, null, 40, Di), i[29] ||= v("span", null, "全部角色", -1)]),
							(n(), E(p, null, o(u, (e) => v("label", {
								key: e.value,
								class: "list-filter-option"
							}, [
								v("input", {
									type: "radio",
									name: "member-role",
									value: e.value,
									checked: w.role === e.value,
									onChange: (t) => le(e.value)
								}, null, 40, Oi),
								v("span", null, g(e.label), 1),
								X("role", e.value) === null ? d("", !0) : (n(), E("small", ki, g(X("role", e.value)), 1))
							])), 64))
						]), v("div", Ai, [v("button", {
							type: "button",
							onClick: i[11] ||= (e) => le("")
						}, "清除"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[12] ||= (e) => k.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(L, {
						label: "角色",
						onStart: i[14] ||= (e) => T(W)(2, e),
						onNudge: i[15] ||= (e) => T(G)(2, e)
					})]),
					v("th", ji, [l(R, {
						label: "成员状态",
						active: w.membership_state !== "joined",
						summary: S.find((e) => e.value === w.membership_state)?.label,
						open: e.visible && k.value === "membership_state",
						"onUpdate:open": i[18] ||= (e) => k.value = e ? "membership_state" : null
					}, {
						default: r(() => [v("fieldset", Mi, [i[31] ||= v("legend", { class: "ui-sr-only" }, "成员状态筛选", -1), (n(), E(p, null, o(S, (e) => v("label", {
							key: e.value,
							class: "list-filter-option"
						}, [
							v("input", {
								type: "radio",
								name: "member-state",
								value: e.value,
								checked: w.membership_state === e.value,
								onChange: (t) => ue(e.value)
							}, null, 40, Ni),
							v("span", null, g(e.label), 1),
							X("membership_state", e.value) === null ? d("", !0) : (n(), E("small", Pi, g(X("membership_state", e.value)), 1))
						])), 64))]), v("div", Fi, [v("button", {
							type: "button",
							onClick: i[16] ||= (e) => ue("joined")
						}, "恢复已加入"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[17] ||= (e) => k.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(L, {
						label: "成员状态",
						onStart: i[19] ||= (e) => T(W)(3, e),
						onNudge: i[20] ||= (e) => T(G)(3, e)
					})]),
					v("th", Ii, [i[32] ||= D(" 加入时间 ", -1), l(L, {
						label: "加入时间",
						onStart: i[21] ||= (e) => T(W)(4, e),
						onNudge: i[22] ||= (e) => T(G)(4, e)
					})]),
					v("th", Li, [i[33] ||= D(" 最近任务 ", -1), l(L, {
						label: "最近任务",
						onStart: i[23] ||= (e) => T(W)(5, e),
						onNudge: i[24] ||= (e) => T(G)(5, e)
					})]),
					i[34] ||= v("th", { scope: "col" }, "操作", -1)
				])]),
				v("tbody", null, [(n(!0), E(p, null, o(M.value, (t) => (n(), E("tr", { key: t.member_id }, [
					v("td", Ri, [v("div", zi, [v("div", Bi, [v("span", { title: t.email }, g(t.email || "未返回"), 9, Vi)]), v("div", Hi, g(t.display_name || (t.remote_user_id ? `远端 ID：${t.remote_user_id}` : "—")), 1)])]),
					v("td", Ui, [t.local_account ? (n(), E("div", Wi, [v("div", Gi, [v("button", {
						type: "button",
						class: "tm-link-btn tm-tabular",
						onClick: (n) => e.callbacks.openAccountDetail(t.local_account.account_id)
					}, " #" + g(t.local_account.account_id), 9, Ki), t.local_account.archived ? (n(), E("span", qi, "已归档")) : d("", !0)]), t.local_account.email && t.local_account.email !== t.email ? (n(), E("div", Ji, g(t.local_account.email), 1)) : d("", !0)])) : (n(), E("span", Yi, "外部成员"))]),
					v("td", Xi, [v("span", { class: b(["tm-badge", Y(T(q)(t.role))]) }, g(T(ne)(t.role)), 3)]),
					v("td", Zi, [v("div", Qi, [v("div", $i, [v("span", { class: b(["tm-badge", Y(T(ae)(t.membership_state))]) }, g(T(ie)(t.membership_state)), 3)]), v("div", ea, g(t.last_seen_in_sync_at ? `核验 ${e.callbacks.formatDateTime(t.last_seen_in_sync_at)}` : "待核验"), 1)])]),
					v("td", ta, [v("span", na, g(t.joined_at ? e.callbacks.formatDateTime(t.joined_at) : "未返回"), 1)]),
					v("td", ra, [t.latest_task_id ? (n(), E("button", {
						key: 0,
						type: "button",
						class: "tm-link-btn tm-tabular",
						onClick: (n) => e.callbacks.openTask(t.latest_task_id, t.latest_run_id)
					}, " 任务 #" + g(t.latest_task_id), 9, ia)) : (n(), E("span", aa, "—"))]),
					v("td", oa, [v("div", sa, [
						t.local_account ? (n(), E("button", {
							key: 0,
							type: "button",
							class: "tm-btn tm-btn--sm",
							onClick: (n) => e.callbacks.openAccountDetail(t.local_account.account_id)
						}, " 查看本地账号 ", 8, ca)) : d("", !0),
						t.latest_task_id ? (n(), E("button", {
							key: 1,
							type: "button",
							class: "tm-btn tm-btn--sm",
							onClick: (n) => e.callbacks.openTask(t.latest_task_id, t.latest_run_id)
						}, " 查看任务 ", 8, la)) : d("", !0),
						!t.local_account && !t.latest_task_id ? (n(), E("span", ua, "—")) : d("", !0)
					])])
				]))), 128)), M.value.length ? d("", !0) : (n(), _(z, {
					key: 0,
					colspan: 7,
					loading: A.value,
					error: j.value,
					"loading-title": "正在加载工作区成员",
					"loading-text": "读取已同步的工作区成员与本地账号关联关系",
					"error-title": "加载工作区成员失败",
					title: Q.value ? "没有匹配的成员记录" : "暂无已同步成员",
					text: Q.value ? "可调整搜索词或筛选条件后重新查询。" : "点击上方「同步」从工作区拉取最新成员名单。",
					"retry-label": "重试",
					onRetry: i[25] ||= (e) => void $()
				}, {
					default: r(() => [!A.value && !j.value && Q.value ? (n(), E("button", {
						key: 0,
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: se
					}, " 清除筛选条件 ")) : d("", !0)]),
					_: 1
				}, 8, [
					"loading",
					"error",
					"title",
					"text"
				]))])
			], 4)], 8, _i),
			l(V, {
				page: w.page,
				size: w.page_size,
				total: N.value,
				busy: A.value,
				label: "成员列表分页",
				"onUpdate:page": fe,
				"onUpdate:size": pe
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy"
			])
		]));
	}
}), fa = {
	class: "tm-detail-nav",
	"aria-label": "Team 详情导航"
}, pa = ["disabled"], ma = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, ha = { class: "tm-banner__copy" }, ga = { class: "tm-row-actions" }, _a = {
	key: 1,
	class: "tm-banner tm-banner--warning",
	role: "alert"
}, va = { class: "tm-banner__copy" }, ya = { class: "tm-row-actions" }, ba = ["disabled"], xa = {
	key: 2,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Sa = { class: "tm-banner__copy" }, Ca = { class: "tm-row-actions" }, wa = ["disabled"], Ta = {
	key: 3,
	class: "tm-hero-card",
	"aria-label": "工作区详情摘要"
}, Ea = { class: "tm-hero-top" }, Da = { class: "tm-hero-title-group" }, Oa = { class: "tm-hero-heading" }, ka = { class: "tm-hero-name-row" }, Aa = {
	key: 0,
	class: "tm-plan-tag"
}, ja = {
	key: 1,
	class: "tm-cell-sub"
}, Ma = { class: "tm-hero-meta-row" }, Na = { class: "tm-mono" }, Pa = { key: 1 }, Fa = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, Ia = { class: "tm-hero-actions" }, La = ["disabled", "title"], Ra = ["disabled", "title"], za = { class: "tm-inline-menu" }, Ba = { class: "tm-inline-menu__panel" }, Va = ["disabled"], Ha = { class: "tm-facts-grid" }, Ua = { class: "tm-fact-tile" }, Wa = { class: "tm-fact-tile" }, Ga = { class: "tm-fact-tile" }, Ka = { class: "tm-fact-tile__value" }, qa = { class: "tm-fact-tile" }, Ja = { class: "tm-fact-tile__value" }, Ya = {
	key: 0,
	class: "tm-badge__dot"
}, Xa = { class: "tm-fact-tile__sub" }, Za = { class: "tm-seat-meter__head" }, Qa = ["aria-valuenow"], $a = { class: "tm-seat-meter__foot" }, eo = { class: "tm-seat-meter__foot" }, to = {
	key: 4,
	class: "tm-hero-card",
	"aria-busy": "true"
}, no = {
	class: "tm-tabs-bar",
	role: "tablist",
	"aria-label": "工作区详情页签"
}, ro = { class: "tm-tabs" }, io = ["aria-selected"], ao = { class: "tm-tab-count" }, oo = ["aria-selected"], so = { class: "tm-tab-count" }, co = /* @__PURE__ */ t({
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
		let a = e, o = r, c = C(null), l = h(!1), u = h(""), f = h(!1), y = h(!1), S = h(null), te = h(null), w = h(null), O = null, k = 0, A = x(() => c.value?.team ?? null), j = x(() => c.value?.actions ?? null), M = x(() => c.value?.permission_verified_at ?? null);
		function N(e) {
			return `tm-badge--${e}`;
		}
		let P = x(() => {
			if (!A.value || !j.value) return !1;
			if (A.value.can_manage === !1) return !0;
			let e = j.value.join.reason_code;
			return e === "team_permission_denied" || e === "team_manager_auth_failed";
		}), F = x(() => j.value?.join.reason ? j.value.join.reason : j.value?.join.reason_code ? G(j.value.join.reason_code) : "当前管理母号缺少管理权限或登录态已失效，暂不可执行邀请操作。"), I = x(() => {
			let e = j.value?.join;
			return !e || !e.enabled && e.reason_code !== "team_limit_required";
		}), L = x(() => {
			let e = j.value?.join;
			return e ? e.enabled ? "从现有账号选择成员并自动邀请入组" : e.reason_code === "team_limit_required" ? "当前未返回已购席位，点击可先配置本地上限或选人并设置上限" : e.reason || G(e.reason_code) : "正在读取工作区操作状态";
		}), R = x(() => f.value || !A.value || A.value.last_sync_status === "queued" || A.value.last_sync_status === "running" ? !0 : j.value ? !j.value.sync.enabled : !1), z = x(() => A.value ? me(A.value) : null), B = x(() => A.value ? Se(A.value.capacity) : null), V = x(() => {
			if (!A.value) return "";
			let e = A.value.capacity;
			return !e.can_accept_new_joins && (e.blocking_reason_code === "team_seat_full" || e.blocking_reason_code === "team_limit_reached") ? "is-danger" : e.blocking_reason_code === "team_limit_required" || e.remaining_before_limit !== null && e.remaining_before_limit <= 1 ? "is-warn" : "";
		});
		function H() {
			let e = S.value;
			e && e.querySelectorAll("details.tm-inline-menu[open]").forEach((e) => {
				e.open = !1;
			});
		}
		function U(e) {
			(e.target instanceof Element ? e.target : null)?.closest("details.tm-inline-menu") || H();
		}
		async function W(e = {}) {
			if (!a.teamId) return;
			O?.abort();
			let t = new AbortController();
			O = t;
			let n = ++k;
			e.silent || (l.value = !0), u.value = "";
			try {
				let e = await a.api.detail(a.teamId, t.signal);
				if (n !== k) return;
				c.value = e, o("team-loaded", e.team);
			} catch (r) {
				if (t.signal.aborted || n !== k) return;
				let i = r instanceof Error ? r.message : "加载工作区详情失败";
				e.silent && c.value || (u.value = i);
			} finally {
				O === t && (O = null), n === k && !e.silent && (l.value = !1);
			}
		}
		async function K() {
			if (A.value && !R.value) {
				f.value = !0;
				try {
					let e = await a.api.syncTeam(A.value.team_id);
					a.callbacks.notify(e.reused ? "当前已有进行中的同步任务，正在追踪进度" : "已启动工作区同步任务"), await W({ silent: !0 });
				} catch (e) {
					a.callbacks.notify(e instanceof Error ? e.message : "同步任务提交失败");
				} finally {
					f.value = !1;
				}
			}
		}
		async function J() {
			if (A.value && !y.value) {
				H(), y.value = !0;
				try {
					let e = await a.api.reverifyTeam(A.value.team_id);
					a.callbacks.notify("已提交管理权限重新核验任务"), e.task_id && await W({ silent: !0 });
				} catch (e) {
					a.callbacks.notify(e instanceof Error ? e.message : "重新核验权限提交失败");
				} finally {
					y.value = !1;
				}
			}
		}
		function X() {
			A.value && (H(), a.callbacks.openTasksForTeam(A.value.team_id, A.value.effective_name));
		}
		function ie() {
			A.value && (H(), o("open-edit", A.value));
		}
		function ae() {
			A.value && (H(), o("open-change-manager", A.value));
		}
		function Z() {
			W({ silent: !1 }), a.section === "members" ? te.value?.refresh() : w.value?.refresh();
		}
		return Qn({
			visible: () => a.visible,
			shouldPoll: () => xe(A.value),
			onPoll: async () => {
				await W({ silent: !0 }), a.section === "members" && await te.value?.refresh();
			},
			intervalMs: 3e3
		}), i(() => a.teamId, () => {
			c.value = null, u.value = "", W();
		}, { immediate: !0 }), s(() => {
			document.addEventListener("click", U);
		}), ee(() => {
			O?.abort(), document.removeEventListener("click", U);
		}), t({
			refresh: (e) => W(e),
			refreshAll: Z,
			updateTeamSnapshot: (e) => {
				c.value && c.value.team.team_id === e.team_id && (c.value = {
					...c.value,
					team: e
				}), W({ silent: !0 });
			}
		}), (t, r) => (n(), E("div", {
			ref_key: "rootRef",
			ref: S,
			class: "tm-root"
		}, [
			v("nav", fa, [v("button", {
				type: "button",
				class: "tm-back-btn",
				onClick: r[0] ||= (e) => o("back")
			}, " ← 返回工作区列表 "), v("button", {
				type: "button",
				class: "tm-btn tm-btn--ghost tm-btn--sm",
				disabled: l.value,
				onClick: Z
			}, g(l.value ? "刷新中…" : "刷新详情"), 9, pa)]),
			u.value && !A.value ? (n(), E("div", ma, [v("div", ha, [r[13] ||= v("strong", null, "加载工作区详情失败：", -1), v("span", null, g(u.value), 1)]), v("div", ga, [v("button", {
				type: "button",
				class: "tm-btn tm-btn--sm",
				onClick: r[1] ||= (e) => void W()
			}, "重试")])])) : d("", !0),
			A.value && A.value.last_sync_status === "failed" ? (n(), E("div", _a, [v("div", va, [r[14] ||= v("strong", null, "最近一次同步失败：", -1), v("span", null, g(A.value.last_sync_error?.summary || T(G)(A.value.last_sync_error?.reason_code, A.value.last_sync_error)) + "。 以下展示上次成功同步快照（" + g(A.value.last_synced_at ? e.callbacks.formatDateTime(A.value.last_synced_at) : "暂无成功快照") + "）。 ", 1)]), v("div", ya, [v("button", {
				type: "button",
				class: "tm-btn tm-btn--sm",
				disabled: R.value,
				onClick: r[2] ||= (e) => void K()
			}, " 立即重新同步 ", 8, ba), A.value.last_sync_task_id ? (n(), E("button", {
				key: 0,
				type: "button",
				class: "tm-btn tm-btn--sm tm-btn--ghost",
				onClick: r[3] ||= (t) => e.callbacks.openTask(A.value.last_sync_task_id, A.value.last_sync_run_id)
			}, " 查看同步任务 ")) : d("", !0)])])) : d("", !0),
			A.value && P.value ? (n(), E("div", xa, [v("div", Sa, [r[15] ||= v("strong", null, "管理权限异常：", -1), v("span", null, g(F.value), 1)]), v("div", Ca, [v("button", {
				type: "button",
				class: "tm-btn tm-btn--sm",
				disabled: y.value || (j.value ? !j.value.reverify.enabled : !1),
				onClick: r[4] ||= (e) => void J()
			}, g(y.value ? "核验提交中…" : "重新核验权限"), 9, wa), v("button", {
				type: "button",
				class: "tm-btn tm-btn--sm tm-btn--danger",
				onClick: ae
			}, " 更换管理母号 ")])])) : d("", !0),
			A.value ? (n(), E("section", Ta, [v("div", Ea, [v("div", Da, [v("div", {
				class: "tm-workspace-avatar tm-workspace-avatar--lg",
				style: m({ "--tm-hue": String(T(ye)(A.value.workspace_id)) }),
				"aria-hidden": "true"
			}, g(T(be)(A.value.effective_name)), 5), v("div", Oa, [v("div", ka, [
				v("h2", null, g(A.value.effective_name), 1),
				A.value.plan_type ? (n(), E("span", Aa, g(A.value.plan_type), 1)) : d("", !0),
				A.value.display_name && A.value.workspace_name && A.value.display_name !== A.value.workspace_name ? (n(), E("span", ja, " 原名：" + g(A.value.workspace_name), 1)) : d("", !0),
				v("button", {
					type: "button",
					class: "tm-btn tm-btn--ghost tm-btn--sm",
					title: "编辑工作区备注别名与本地人数上限",
					onClick: ie
				}, " 编辑别名与上限 ")
			]), v("div", Ma, [
				v("span", Na, g(A.value.workspace_id), 1),
				r[17] ||= v("span", null, "·", -1),
				v("span", null, [r[16] ||= D(" 管理母号： ", -1), A.value.manager_account.account_id ? (n(), E("button", {
					key: 0,
					type: "button",
					class: "tm-link-btn",
					onClick: r[5] ||= (t) => e.callbacks.openAccountDetail(A.value.manager_account.account_id)
				}, g(A.value.manager_account.email || `#${A.value.manager_account.account_id}`), 1)) : (n(), E("span", Pa, g(A.value.manager_account.email || "—"), 1))]),
				v("span", { class: b(["tm-badge", N(T(q)(A.value.manager_role))]) }, g(T(ne)(A.value.manager_role)), 3),
				A.value.manager_account.archived ? (n(), E("span", Fa, "已归档")) : d("", !0),
				r[18] ||= v("span", null, "·", -1),
				v("span", null, " 权限核验：" + g(M.value ? e.callbacks.formatDateTime(M.value) : "待核验"), 1)
			])])]), v("div", Ia, [
				v("button", {
					type: "button",
					class: "tm-btn tm-btn--primary",
					disabled: I.value,
					title: L.value,
					onClick: r[6] ||= (e) => o("open-join", A.value)
				}, " 加入账号 ", 8, La),
				v("button", {
					type: "button",
					class: "tm-btn",
					disabled: R.value,
					title: j.value?.sync.reason || "同步工作区成员、邀请与席位",
					onClick: r[7] ||= (e) => void K()
				}, g(f.value || A.value.last_sync_status === "queued" || A.value.last_sync_status === "running" ? "同步中…" : "同步"), 9, Ra),
				v("details", za, [r[19] ||= v("summary", { "aria-label": "工作区更多操作" }, "···", -1), v("div", Ba, [
					v("button", {
						type: "button",
						onClick: X
					}, "查看相关任务"),
					v("button", {
						type: "button",
						onClick: ie
					}, "设置别名与人数上限"),
					v("button", {
						type: "button",
						onClick: ae
					}, "更换管理母号"),
					v("button", {
						type: "button",
						disabled: y.value || (j.value ? !j.value.reverify.enabled : !1),
						onClick: r[8] ||= (e) => void J()
					}, g(y.value ? "权限核验提交中…" : "重新核验权限"), 9, Va)
				])])
			])]), v("div", Ha, [
				v("div", Ua, [
					r[20] ||= v("div", { class: "tm-fact-tile__label" }, [v("span", null, "已确认成员")], -1),
					v("div", { class: b(["tm-fact-tile__value", { "is-null": A.value.confirmed_member_count === null }]) }, g(T($)(A.value.confirmed_member_count, "待同步")), 3),
					r[21] ||= v("div", { class: "tm-fact-tile__sub" }, "远端已确认（含母号）", -1)
				]),
				v("div", Wa, [
					r[22] ||= v("div", { class: "tm-fact-tile__label" }, [v("span", null, "待接受邀请")], -1),
					v("div", { class: b(["tm-fact-tile__value", { "is-null": A.value.pending_invite_count === null }]) }, g(T($)(A.value.pending_invite_count, "待同步")), 3),
					r[23] ||= v("div", { class: "tm-fact-tile__sub" }, "远端有效待接受", -1)
				]),
				v("div", Ga, [
					r[24] ||= v("div", { class: "tm-fact-tile__label" }, [v("span", null, "本系统处理中")], -1),
					v("div", Ka, g(T($)(A.value.processing_count, "—")), 1),
					r[25] ||= v("div", { class: "tm-fact-tile__sub" }, "独立计数，勿直接相加", -1)
				]),
				v("div", qa, [
					r[26] ||= v("div", { class: "tm-fact-tile__label" }, [v("span", null, "同步状态")], -1),
					v("div", Ja, [v("span", { class: b(["tm-badge", N(T(Y)(A.value.last_sync_status))]) }, [A.value.last_sync_status === "queued" || A.value.last_sync_status === "running" ? (n(), E("span", Ya)) : d("", !0), D(" " + g(T(re)(A.value.last_sync_status)), 1)], 2)]),
					v("div", Xa, g(A.value.last_synced_at ? e.callbacks.formatDateTime(A.value.last_synced_at) : "待同步"), 1)
				]),
				v("div", { class: b(["tm-seat-meter", V.value]) }, [
					v("div", Za, [r[27] ||= v("span", { class: "tm-seat-meter__title" }, "仅使用已购剩余席位", -1), z.value ? (n(), E("span", {
						key: 0,
						class: b(["tm-badge", N(z.value.tone)])
					}, g(T(pe)(A.value.capacity.basis)), 3)) : d("", !0)]),
					v("div", {
						class: "tm-seat-meter__track",
						role: "progressbar",
						"aria-valuenow": B.value ?? void 0,
						"aria-valuemin": "0",
						"aria-valuemax": "100"
					}, [v("div", {
						class: "tm-seat-meter__fill",
						style: m({ width: `${B.value ?? 0}%` })
					}, null, 4)], 8, Qa),
					v("div", $a, [v("span", null, " 已占 " + g(T($)(A.value.capacity.occupied_count, "待同步")) + " / 有效上限 " + g(T($)(A.value.capacity.effective_limit, "未设置")), 1), v("span", null, " 剩余可拉 " + g(T($)(A.value.capacity.remaining_before_limit, "待同步", " 席")), 1)]),
					v("div", eo, [v("span", null, "已购 " + g(T($)(A.value.purchased_seats, "未返回", " 席")), 1), v("span", null, "本地上限 " + g(T($)(A.value.planned_member_limit, "未设置", " 人")), 1)])
				], 2)
			])])) : l.value ? (n(), E("section", to, [...r[28] ||= [v("div", {
				class: "ui-table-state",
				style: { "min-height": "120px" }
			}, [v("span", {
				class: "ui-spinner",
				"aria-hidden": "true"
			}), v("strong", null, "正在加载工作区详情…")], -1)]])) : d("", !0),
			v("div", no, [v("div", ro, [v("button", {
				type: "button",
				role: "tab",
				class: b(["tm-tab-btn", { "is-active": e.section === "members" }]),
				"aria-selected": e.section === "members",
				onClick: r[9] ||= (e) => o("update:section", "members")
			}, [r[29] ||= v("span", null, "成员", -1), v("span", ao, g(A.value ? T($)(A.value.confirmed_member_count, "待同步") : "—"), 1)], 10, io), v("button", {
				type: "button",
				role: "tab",
				class: b(["tm-tab-btn", { "is-active": e.section === "invitations" }]),
				"aria-selected": e.section === "invitations",
				onClick: r[10] ||= (e) => o("update:section", "invitations")
			}, [r[30] ||= v("span", null, "邀请", -1), v("span", so, [A.value ? (n(), E(p, { key: 0 }, [D(g(A.value.processing_count > 0 ? `${T($)(A.value.pending_invite_count, "待同步")} · 处理中 ${A.value.processing_count}` : T($)(A.value.pending_invite_count, "待同步")), 1)], 64)) : (n(), E(p, { key: 1 }, [D("—")], 64))])], 10, oo)])]),
			e.section === "members" ? (n(), _(da, {
				key: 5,
				ref_key: "membersTabRef",
				ref: te,
				api: e.api,
				"team-id": e.teamId,
				visible: e.visible && e.section === "members",
				callbacks: e.callbacks
			}, null, 8, [
				"api",
				"team-id",
				"visible",
				"callbacks"
			])) : (n(), _(fi, {
				key: 6,
				ref_key: "invitationsTabRef",
				ref: w,
				api: e.api,
				"team-id": e.teamId,
				visible: e.visible && e.section === "invitations",
				callbacks: e.callbacks,
				"join-request-id": e.joinRequestId,
				onRefreshTeam: r[11] ||= (e) => void W({ silent: !0 }),
				onClearJoinRequest: r[12] ||= (e) => o("clear-join-request")
			}, null, 8, [
				"api",
				"team-id",
				"visible",
				"callbacks",
				"join-request-id"
			]))
		], 512));
	}
}), lo = ["aria-busy"], uo = { class: "tm-dialog__head" }, fo = { class: "tm-dialog__desc" }, po = { class: "tm-mono" }, mo = ["disabled"], ho = { class: "tm-banner tm-banner--info" }, go = { class: "tm-banner__copy" }, _o = { class: "tm-field" }, vo = ["placeholder", "disabled"], yo = { class: "tm-field__hint" }, bo = { class: "tm-field" }, xo = ["disabled"], So = {
	key: 0,
	class: "tm-banner tm-banner--warning"
}, Co = {
	key: 1,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, wo = { class: "tm-banner__copy" }, To = {
	class: "tm-dialog__foot",
	style: { margin: "4px -22px -18px" }
}, Eo = { class: "tm-field__hint" }, Do = { class: "tm-dialog__foot-right" }, Oo = ["disabled"], ko = ["disabled"], Ao = /* @__PURE__ */ t({
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
		let r = e, o = t, s = h();
		P(s, () => r.open && r.visible, () => r.visible);
		let c = h(""), l = h(""), u = h(!1), f = h(""), m = h(!1), _ = x(() => r.open && r.visible), ee = x(() => {
			let e = r.team?.purchased_seats;
			return e == null || !Number.isFinite(e) ? "未返回" : `已购 ${e} 席`;
		});
		function b() {
			c.value = r.team?.display_name ?? "", l.value = r.team?.planned_member_limit !== null && r.team?.planned_member_limit !== void 0 ? String(r.team.planned_member_limit) : "", f.value = "", m.value = !1;
		}
		i(() => [
			_.value,
			r.team?.team_id,
			r.team?.revision
		], ([e]) => {
			e && b();
		}, { immediate: !0 });
		function S() {
			let e = l.value.trim();
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
		async function C() {
			if (!r.team || u.value) return;
			f.value = "", m.value = !1;
			let e = c.value.trim();
			if (e.length > 120) {
				f.value = "工作区别名不能超过 120 个字符";
				return;
			}
			let t = S();
			if (!t.ok) f.value = t.message;
			else {
				u.value = !0;
				try {
					let n = await r.api.updateTeam(r.team.team_id, {
						expected_revision: r.team.revision,
						display_name: e || null,
						planned_member_limit: t.value
					});
					o("notify", "工作区设置已保存"), o("updated", n.team), o("close");
				} catch (e) {
					if (e instanceof N) {
						if (e.code === "team_revision_conflict" || e.code === "revision_conflict" || e.status === 409) {
							m.value = !0, f.value = "工作区状态已变更（版本冲突），请关闭后刷新最新信息再重新编辑", o("conflict");
							return;
						}
						f.value = e.message || G(e.code);
					} else f.value = e instanceof Error ? e.message : "保存工作区设置失败";
				} finally {
					u.value = !1;
				}
			}
		}
		function w() {
			u.value || o("close");
		}
		function T(e) {
			let t = s.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(n.width === 0 && n.height === 0 || e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && w();
		}
		return (t, r) => (n(), E("dialog", {
			ref_key: "dialogRef",
			ref: s,
			class: "tm-dialog",
			"aria-labelledby": "teamEditDialogTitle",
			"aria-busy": u.value,
			onCancel: y(w, ["prevent"]),
			onClick: T
		}, [v("div", uo, [v("div", null, [
			r[3] ||= v("p", { class: "tm-dialog__kicker" }, "TEAM SETTINGS", -1),
			r[4] ||= v("h3", {
				id: "teamEditDialogTitle",
				class: "tm-dialog__title"
			}, "编辑工作区设置", -1),
			v("p", fo, [e.team ? (n(), E(p, { key: 0 }, [
				r[2] ||= D(" 工作区：", -1),
				v("strong", po, g(e.team.workspace_id), 1),
				D(" · 远端名称「" + g(e.team.workspace_name || "未返回") + "」 ", 1)
			], 64)) : d("", !0)])
		]), v("button", {
			type: "button",
			class: "tm-dialog__close",
			"aria-label": "关闭编辑弹窗",
			disabled: u.value,
			onClick: w
		}, " × ", 8, mo)]), v("form", {
			class: "tm-dialog__body",
			novalidate: "",
			onSubmit: y(C, ["prevent"])
		}, [
			v("div", ho, [v("div", go, [
				v("span", null, [r[5] ||= D(" 当前远端已购席位：", -1), v("strong", null, g(ee.value), 1)]),
				r[6] ||= v("span", null, "·", -1),
				r[7] ||= v("span", null, "仅使用已购剩余席位，与已购席位共同取较小值。", -1)
			])]),
			v("label", _o, [
				r[8] ||= v("span", { class: "tm-field__label" }, "工作区本地显示别名（display_name）", -1),
				a(v("input", {
					"onUpdate:modelValue": r[0] ||= (e) => c.value = e,
					type: "text",
					maxlength: "120",
					placeholder: e.team?.workspace_name || "留空将恢复远端工作区名称",
					disabled: u.value
				}, null, 8, vo), [[te, c.value]]),
				v("span", yo, " 留空将清除自定义别名，恢复展示远端工作区名称「" + g(e.team?.workspace_name || "未返回") + "」。 ", 1)
			]),
			v("label", bo, [
				r[9] ||= v("span", { class: "tm-field__label" }, "本地计划人数上限（planned_member_limit）", -1),
				a(v("input", {
					"onUpdate:modelValue": r[1] ||= (e) => l.value = e,
					type: "text",
					inputmode: "numeric",
					placeholder: "输入正整数（含管理母号），或留空清除上限",
					disabled: u.value
				}, null, 8, xo), [[te, l.value]]),
				r[10] ||= v("span", { class: "tm-field__hint" }, " 仅接受正整数（含管理母号）或留空清除上限。下调上限不会移除现有成员或撤回邀请，仅拦截后续新增占位。 ", -1)
			]),
			e.team && (e.team.purchased_seats === null || e.team.purchased_seats === void 0) ? (n(), E("div", So, [...r[11] ||= [v("div", { class: "tm-banner__copy" }, " 当前远端未返回已购席位；若清除本地计划人数上限，后续批量加入新成员将被拦截，直到补充上限或同步出已购席位。 ", -1)]])) : d("", !0),
			f.value ? (n(), E("div", Co, [v("div", wo, g(f.value), 1)])) : d("", !0),
			v("div", To, [v("span", Eo, [e.team ? (n(), E(p, { key: 0 }, [D("当前修订版本 v" + g(e.team.revision), 1)], 64)) : d("", !0)]), v("div", Do, [v("button", {
				type: "button",
				class: "tm-btn",
				disabled: u.value,
				onClick: w
			}, g(m.value ? "关闭并刷新" : "取消"), 9, Oo), v("button", {
				type: "submit",
				class: "tm-btn tm-btn--primary",
				disabled: u.value || !e.team
			}, g(u.value ? "保存中…" : "保存修改"), 9, ko)])])
		], 32)], 40, lo));
	}
}), jo = ["aria-busy"], Mo = { class: "tm-dialog__head" }, No = { class: "tm-dialog__kicker" }, Po = {
	id: "teamJoinDialogTitle",
	class: "tm-dialog__title"
}, Fo = { class: "tm-dialog__desc" }, Io = { class: "tm-mono" }, Lo = ["disabled"], Ro = {
	key: 0,
	class: "tm-dialog__body"
}, zo = {
	key: 0,
	class: "tm-field"
}, Bo = ["value", "disabled"], Vo = { value: "" }, Ho = ["value"], Uo = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Wo = { class: "tm-banner__copy" }, Go = {
	key: 1,
	class: "tm-banner tm-banner--info",
	role: "status"
}, Ko = {
	key: 2,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, qo = { class: "tm-banner__copy" }, Jo = { class: "tm-field" }, Yo = { style: {
	display: "flex",
	"align-items": "center",
	"justify-content": "space-between",
	gap: "8px",
	"flex-wrap": "wrap"
} }, Xo = { class: "tm-field__label" }, Zo = { class: "tm-field__hint" }, Qo = { class: "tm-preview-grid" }, $o = { class: "tm-preview-stat is-highlight" }, es = { class: "tm-preview-stat" }, ts = { class: "tm-preview-stat" }, ns = { class: "tm-preview-stat" }, rs = { class: "tm-preview-stat" }, is = { class: "tm-preview-stat" }, as = { class: "tm-seat-meter__head" }, os = { class: "tm-badge tm-badge--neutral" }, ss = {
	class: "tm-seat-meter__track",
	"aria-hidden": "true"
}, cs = {
	class: "tm-seat-meter__foot",
	style: { "flex-wrap": "wrap" }
}, ls = {
	key: 0,
	class: "tm-banner tm-banner--warning",
	style: {
		"flex-direction": "column",
		"align-items": "stretch"
	},
	role: "alert"
}, us = { style: {
	display: "flex",
	"align-items": "center",
	gap: "8px",
	"flex-wrap": "wrap"
} }, ds = ["disabled"], fs = ["disabled"], ps = {
	key: 0,
	style: {
		color: "var(--ui-color-danger, #b91c1c)",
		"font-size": "12px"
	}
}, ms = {
	key: 1,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, hs = { class: "tm-banner__copy" }, gs = {
	key: 2,
	class: "tm-banner tm-banner--info"
}, _s = { key: 3 }, vs = {
	key: 0,
	class: "tm-candidate-list",
	style: {
		"margin-top": "8px",
		"max-height": "200px"
	}
}, ys = {
	class: "tm-cell-stack",
	style: { "min-width": "0" }
}, bs = { class: "tm-cell-primary" }, xs = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, Ss = {
	key: 0,
	class: "tm-cell-sub"
}, Cs = {
	key: 4,
	class: "tm-banner tm-banner--warning",
	role: "status"
}, ws = { class: "tm-banner__copy" }, Ts = {
	key: 5,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Es = { class: "tm-banner__copy" }, Ds = {
	key: 1,
	class: "tm-dialog__body"
}, Os = {
	class: "tm-banner tm-banner--info",
	role: "status"
}, ks = { class: "tm-banner__copy" }, As = { class: "tm-mono" }, js = { class: "tm-preview-grid" }, Ms = { class: "tm-preview-stat is-highlight" }, Ns = { class: "tm-preview-stat" }, Ps = { class: "tm-preview-stat" }, Fs = {
	key: 0,
	class: "tm-banner tm-banner--danger",
	role: "alert"
}, Is = { class: "tm-banner__copy" }, Ls = ["aria-busy"], Rs = {
	key: 0,
	style: {
		padding: "18px",
		"text-align": "center",
		color: "var(--ui-color-text-secondary)"
	}
}, zs = {
	class: "tm-cell-stack",
	style: {
		"min-width": "0",
		flex: "1"
	}
}, Bs = { class: "tm-cell-primary" }, Vs = {
	class: "tm-mono",
	style: { color: "var(--ui-color-text-muted)" }
}, Hs = { class: "tm-cell-sub" }, Us = { style: {
	display: "flex",
	"align-items": "center",
	gap: "8px",
	flex: "none"
} }, Ws = ["onClick"], Gs = {
	key: 1,
	style: {
		display: "flex",
		"align-items": "center",
		"justify-content": "flex-end",
		gap: "8px"
	}
}, Ks = ["disabled"], qs = { class: "tm-field__hint tm-tabular" }, Js = ["disabled"], Ys = { class: "tm-dialog__foot" }, Xs = { class: "tm-dialog__foot-right" }, Zs = ["disabled"], Qs = ["disabled"], $s = { class: "tm-field__hint" }, ec = { class: "tm-dialog__foot-right" }, tc = /* @__PURE__ */ t({
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
		P(c, () => r.open && r.visible, () => r.visible);
		let l = h("preview"), u = h([]), f = h(!1), _ = h(""), S = h(""), C = h(null), w = h(null), O = h(!1), k = h(""), A = h(!1), j = h(""), M = h(!1), F = h(""), I = h(!1), L = h(""), R = h(""), z = h(null), B = h(!1), V = h(""), H = null, U = null, W = null, K = x(() => r.open && r.visible), ne = x(() => !r.initialTeam), q = x(() => C.value?.team_id || S.value || r.target?.targetTeamId || ""), J = x(() => {
			let e = w.value?.counts;
			return e ? e.missing_auth_skip_count + e.unavailable_skip_count + e.email_mismatch_skip_count : 0;
		}), re = x(() => {
			let e = w.value?.counts;
			return e ? e.new_join_count + e.continue_invite_count : 0;
		}), Y = x(() => I.value || M.value || O.value || !C.value || !w.value ? !1 : w.value.capacity.can_submit && re.value > 0), X = x(() => {
			let e = w.value?.capacity;
			return !e || e.effective_limit === null || e.effective_limit <= 0 || e.occupied_count === null ? 0 : Math.min(100, Math.max(0, Math.round(e.occupied_count / e.effective_limit * 100)));
		}), ie = x(() => {
			let e = w.value?.capacity;
			if (!e || e.effective_limit === null || e.effective_limit <= 0) return 0;
			let t = Math.round(e.additional_required / e.effective_limit * 100);
			return Math.min(Math.max(0, 100 - X.value), Math.max(0, t));
		}), ae = x(() => {
			let e = w.value?.capacity;
			return e ? e.exceeds_limit || e.blocking_reason_code === "team_seat_full" || e.blocking_reason_code === "team_limit_reached" ? "is-danger" : e.blocking_reason_code === "team_limit_required" || e.remaining_after_submit !== null && e.remaining_after_submit <= 1 ? "is-warn" : "" : "";
		}), Z = x(() => z.value ? Math.max(1, Math.ceil(z.value.total_items / z.value.page_size)) : 1);
		function Q(e) {
			return e instanceof DOMException && e.name === "AbortError";
		}
		function oe() {
			H &&= (H.abort(), null), U &&= (U.abort(), null), W &&= (W.abort(), null);
		}
		function se() {
			oe(), l.value = "preview", u.value = [], f.value = !1, _.value = "", S.value = "", C.value = null, w.value = null, O.value = !1, k.value = "", A.value = !1, j.value = "", M.value = !1, F.value = "", I.value = !1, L.value = "", R.value = "", z.value = null, B.value = !1, V.value = "";
		}
		function ce() {
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
		async function le(e) {
			let t = ce();
			if (!K.value || !e || !t) return;
			U && U.abort();
			let n = new AbortController();
			U = n, O.value = !0, k.value = "";
			try {
				let i = await r.api.previewJoin(e, t, n.signal);
				if (n.signal.aborted || !K.value) return;
				w.value = i;
			} catch (e) {
				if (Q(e) || n.signal.aborted) return;
				w.value = null, k.value = e instanceof N || e instanceof Error ? e.message : "生成加入预览失败";
			} finally {
				U === n && (U = null, O.value = !1);
			}
		}
		async function ue(e) {
			if (!e) return;
			S.value = e;
			let t = u.value.find((t) => t.team_id === e);
			if (t) {
				C.value = t, await le(e);
				return;
			}
			H && H.abort();
			let n = new AbortController();
			H = n, f.value = !0, _.value = "";
			try {
				let t = await r.api.detail(e, n.signal);
				if (n.signal.aborted || !K.value) return;
				C.value = t.team, await le(t.team.team_id);
			} catch (e) {
				if (Q(e) || n.signal.aborted) return;
				_.value = e instanceof N || e instanceof Error ? e.message : "获取目标 Team 信息失败";
			} finally {
				H === n && (H = null, f.value = !1);
			}
		}
		async function de() {
			if (!K.value) return;
			H && H.abort();
			let e = new AbortController();
			H = e, f.value = !0, _.value = "";
			try {
				let t = await r.api.list({
					page: 1,
					page_size: 50,
					include_facets: 0
				}, e.signal);
				if (e.signal.aborted || !K.value) return;
				u.value = t.items, t.items.length === 1 && (S.value = t.items[0].team_id, C.value = t.items[0], await le(t.items[0].team_id));
			} catch (t) {
				if (Q(t) || e.signal.aborted) return;
				_.value = t instanceof N || t instanceof Error ? t.message : "加载可选 Team 列表失败";
			} finally {
				H === e && (H = null, f.value = !1);
			}
		}
		async function fe() {
			se(), K.value && r.target && (r.initialTeam ? (C.value = r.initialTeam, S.value = r.initialTeam.team_id, await le(r.initialTeam.team_id)) : r.target.targetTeamId ? await ue(r.target.targetTeamId) : await de());
		}
		function me(e) {
			let t = e.target.value;
			w.value = null, k.value = "", L.value = "", R.value = "", t ? ue(t) : (S.value = "", C.value = null);
		}
		async function he() {
			if (!C.value || M.value) return;
			F.value = "";
			let e = j.value.trim();
			if (!/^[1-9]\d*$/.test(e)) {
				F.value = "请输入大于 0 的正整数作为本地计划人数上限";
				return;
			}
			let t = Number(e);
			if (!Number.isSafeInteger(t) || t <= 0) F.value = "本地计划人数上限数值超出有效范围";
			else {
				M.value = !0;
				try {
					let e = await r.api.updateTeam(C.value.team_id, {
						expected_revision: C.value.revision,
						planned_member_limit: t
					});
					C.value = e.team;
					let n = u.value.findIndex((t) => t.team_id === e.team.team_id);
					n >= 0 && u.value.splice(n, 1, e.team), s("teamUpdated", e.team), s("notify", "本地计划人数上限已更新，正在重新核算席位"), await le(e.team.team_id);
				} catch (e) {
					F.value = e instanceof N || e instanceof Error ? e.message : "设置本地计划人数上限失败";
				} finally {
					M.value = !1;
				}
			}
		}
		async function ge() {
			if (!Y.value || !C.value || !w.value) return;
			let e = ce();
			if (e) {
				I.value = !0, L.value = "", R.value = "";
				try {
					let t = await r.api.submitJoin(C.value.team_id, {
						...e,
						expected_team_revision: w.value.snapshot_revision
					});
					z.value = t, l.value = "receipt", s("notify", "批量加入请求已受理，正在后台执行"), s("submitted", t, C.value.team_id);
				} catch (e) {
					if (e instanceof N) {
						if (e.status === 409 && (e.code === "team_revision_conflict" || e.code === "revision_conflict")) {
							R.value = "工作区状态已变更，已自动重新核算最新席位与名单，请二次确认后提交。", await ue(C.value.team_id);
							return;
						}
						if (e.status === 409 && e.code === "team_limit_required") {
							R.value = "需要先配置本地计划人数上限，已重新加载席位核算。", await le(C.value.team_id);
							return;
						}
						L.value = e.message || G(e.code);
					} else L.value = e instanceof Error ? e.message : "发起加入请求失败";
				} finally {
					I.value = !1;
				}
			}
		}
		async function _e(e) {
			if (!z.value || B.value || e < 1 || e > Z.value) return;
			let t = z.value.team_id || q.value;
			if (!t) return;
			W && W.abort();
			let n = new AbortController();
			W = n, B.value = !0, V.value = "";
			try {
				let i = await r.api.getJoinRequest(t, z.value.join_request_id, {
					page: e,
					page_size: z.value.page_size
				}, n.signal);
				if (n.signal.aborted || !K.value) return;
				z.value = i;
			} catch (e) {
				if (Q(e) || n.signal.aborted) return;
				V.value = e instanceof N || e instanceof Error ? e.message : "加载回执明细失败";
			} finally {
				W === n && (W = null, B.value = !1);
			}
		}
		function ve(e) {
			switch (e) {
				case "will_join": return {
					label: "将新增加入",
					tone: "success"
				};
				case "will_continue_invite": return {
					label: "续接已有邀请",
					tone: "active"
				};
				case "skip_already_member": return {
					label: "已是成员跳过",
					tone: "neutral"
				};
				case "skip_already_processing": return {
					label: "执行中跳过",
					tone: "active"
				};
				case "skip_another_team": return {
					label: "已属其他Team",
					tone: "warning"
				};
				case "skip_missing_auth": return {
					label: "缺认证跳过",
					tone: "danger"
				};
				case "skip_email_mismatch": return {
					label: "邮箱快照不符",
					tone: "danger"
				};
				default: return {
					label: "不可用跳过",
					tone: "danger"
				};
			}
		}
		function ye(e) {
			return e === "queued" ? {
				label: "已入队",
				tone: "success"
			} : e === "reused_active" ? {
				label: "复用进行中",
				tone: "active"
			} : {
				label: "已跳过",
				tone: "warning"
			};
		}
		function be() {
			I.value || M.value || (oe(), s("close"));
		}
		function xe(e) {
			let t = c.value;
			if (!t || e.target !== t) return;
			let n = t.getBoundingClientRect();
			(n.width === 0 && n.height === 0 || e.clientX < n.left || e.clientX > n.right || e.clientY < n.top || e.clientY > n.bottom) && be();
		}
		return i(() => [
			K.value,
			r.initialTeam?.team_id,
			r.target
		], ([e]) => {
			e ? fe() : oe();
		}, { immediate: !0 }), ee(() => {
			oe();
		}), (t, r) => (n(), E("dialog", {
			ref_key: "dialogRef",
			ref: c,
			class: "tm-dialog tm-dialog--lg",
			"aria-labelledby": "teamJoinDialogTitle",
			"aria-busy": I.value || M.value || O.value || B.value,
			onCancel: y(be, ["prevent"]),
			onClick: xe
		}, [
			v("div", Mo, [v("div", null, [
				v("p", No, g(l.value === "receipt" ? "JOIN REQUEST RECEIPT" : "TEAM JOIN PREVIEW"), 1),
				v("h3", Po, g(l.value === "receipt" ? "加入请求受理回执" : "加入 Team 预览与席位确认"), 1),
				v("p", Fo, [C.value ? (n(), E(p, { key: 0 }, [
					r[7] ||= D(" 目标工作区：", -1),
					v("strong", null, g(C.value.effective_name), 1),
					r[8] ||= D(" （", -1),
					v("span", Io, g(C.value.workspace_id), 1),
					r[9] ||= D("） ", -1)
				], 64)) : (n(), E(p, { key: 1 }, [D(" 请选择目标 Team，系统将执行纯本地名单去重与席位容量核算。 ")], 64))])
			]), v("button", {
				type: "button",
				class: "tm-dialog__close",
				"aria-label": "关闭加入确认弹窗",
				disabled: I.value || M.value,
				onClick: be
			}, " × ", 8, Lo)]),
			l.value === "preview" ? (n(), E("div", Ro, [
				ne.value ? (n(), E("div", zo, [
					r[10] ||= v("span", { class: "tm-field__label" }, "目标 Team 工作区", -1),
					v("select", {
						value: S.value,
						disabled: f.value || I.value,
						"aria-label": "选择目标 Team",
						onChange: me
					}, [v("option", Vo, g(f.value ? "正在加载可用 Team…" : "请选择一个已绑定的 Team"), 1), (n(!0), E(p, null, o(u.value, (e) => (n(), E("option", {
						key: e.team_id,
						value: e.team_id
					}, g(e.effective_name) + "（" + g(e.workspace_id) + " · 成员 " + g(T($)(e.confirmed_member_count, "待同步")) + "） ", 9, Ho))), 128))], 40, Bo),
					_.value ? (n(), E("div", Uo, [v("div", Wo, g(_.value), 1), v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: r[0] ||= (t) => e.target?.targetTeamId ? ue(e.target.targetTeamId) : de()
					}, " 重试 ")])) : d("", !0)
				])) : d("", !0),
				O.value ? (n(), E("div", Go, [...r[11] ||= [v("div", { class: "tm-banner__copy" }, "正在执行本地名单分类与席位容量核算…", -1)]])) : d("", !0),
				k.value ? (n(), E("div", Ko, [v("div", qo, g(k.value), 1), q.value ? (n(), E("button", {
					key: 0,
					type: "button",
					class: "tm-btn tm-btn--sm",
					onClick: r[1] ||= (e) => le(q.value)
				}, " 重新核算 ")) : d("", !0)])) : d("", !0),
				w.value ? (n(), E(p, { key: 3 }, [
					v("section", Jo, [v("div", Yo, [v("span", Xo, " 本次选定名单拆解（去重共 " + g(w.value.counts.selected_total) + " 个） ", 1), v("span", Zo, " 最近同步：" + g(w.value.team_last_synced_at ? e.formatDateTime(w.value.team_last_synced_at) : "尚未同步"), 1)]), v("div", Qo, [
						v("div", $o, [r[12] ||= v("span", null, "净新增加入", -1), v("strong", null, g(w.value.counts.new_join_count), 1)]),
						v("div", es, [r[13] ||= v("span", null, "已有邀请直接续接", -1), v("strong", null, g(w.value.counts.continue_invite_count), 1)]),
						v("div", ts, [r[14] ||= v("span", null, "已是成员跳过", -1), v("strong", null, g(w.value.counts.already_member_skip_count), 1)]),
						v("div", ns, [r[15] ||= v("span", null, "执行中跳过", -1), v("strong", null, g(w.value.counts.already_processing_skip_count), 1)]),
						v("div", rs, [r[16] ||= v("span", null, "已属其他Team跳过", -1), v("strong", null, g(w.value.counts.another_team_skip_count), 1)]),
						v("div", is, [r[17] ||= v("span", null, "缺认证/不可用跳过", -1), v("strong", null, g(J.value), 1)])
					])]),
					v("section", { class: b(["tm-seat-meter", ae.value]) }, [
						v("div", as, [r[18] ||= v("span", { class: "tm-seat-meter__title" }, " 席位安全核对 · 仅使用已购剩余席位 ", -1), v("span", os, " 依据：" + g(T(pe)(w.value.capacity.basis)), 1)]),
						v("div", ss, [v("div", {
							class: "tm-seat-meter__fill",
							style: m({ width: `${X.value}%` })
						}, null, 4), v("div", {
							class: "tm-seat-meter__fill--added",
							style: m({ width: `${ie.value}%` })
						}, null, 4)]),
						v("div", cs, [v("span", null, [
							r[19] ||= D(" 已购席位：", -1),
							v("strong", null, g(T($)(w.value.capacity.purchased_seats, "未返回", " 席")), 1),
							r[20] ||= D(" · 本地计划上限：", -1),
							v("strong", null, g(w.value.capacity.planned_member_limit !== null && w.value.capacity.planned_member_limit !== void 0 ? `${w.value.capacity.planned_member_limit} 人` : "未设置"), 1)
						]), v("span", null, [
							r[21] ||= D(" 当前占用：", -1),
							v("strong", null, g(T($)(w.value.capacity.occupied_count, "待同步", " 席")), 1),
							r[22] ||= D(" · 本次新增占席：", -1),
							v("strong", null, g(w.value.capacity.additional_required) + " 席", 1),
							r[23] ||= D(" · 提交后剩余：", -1),
							v("strong", null, g(T($)(w.value.capacity.remaining_after_submit, "待同步", " 席")), 1)
						])])
					], 2),
					w.value.capacity.blocking_reason_code === "team_limit_required" ? (n(), E("div", ls, [
						r[24] ||= v("div", { class: "tm-banner__copy" }, [v("strong", null, "需先设置本地计划人数上限："), v("span", null, "远端未返回已购席位，且当前未配置本地人数上限（含母号），无法直接发起拉人。")], -1),
						v("div", us, [a(v("input", {
							"onUpdate:modelValue": r[2] ||= (e) => j.value = e,
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
							disabled: M.value
						}, null, 8, ds), [[te, j.value]]), v("button", {
							type: "button",
							class: "tm-btn tm-btn--primary tm-btn--sm",
							disabled: M.value,
							onClick: he
						}, g(M.value ? "保存核算中…" : "设置本地计划人数上限并重新核算"), 9, fs)]),
						F.value ? (n(), E("span", ps, g(F.value), 1)) : d("", !0)
					])) : !w.value.capacity.can_submit && w.value.capacity.blocking_reason_code ? (n(), E("div", ms, [v("div", hs, g(w.value.capacity.blocking_reason || T(G)(w.value.capacity.blocking_reason_code)), 1)])) : d("", !0),
					w.value.requires_sync ? (n(), E("div", gs, [...r[25] ||= [v("div", { class: "tm-banner__copy" }, " 将在后台自动先执行一次工作区同步与席位预检，确认远端最新席位后再发出新邀请。 ", -1)]])) : d("", !0),
					w.value.sample_items.length ? (n(), E("div", _s, [v("button", {
						type: "button",
						class: "tm-link-btn",
						onClick: r[3] ||= (e) => A.value = !A.value
					}, g(A.value ? "收起预检抽样明细" : `查看预检抽样明细（前 ${w.value.sample_items.length} 条）`), 1), A.value ? (n(), E("div", vs, [(n(!0), E(p, null, o(w.value.sample_items, (e) => (n(), E("div", {
						key: e.account_id,
						class: "tm-candidate-row"
					}, [v("div", ys, [v("div", bs, [v("span", null, g(e.email), 1), v("span", xs, "#" + g(e.account_id), 1)]), e.reason || e.reason_code ? (n(), E("div", Ss, g(e.reason || T(G)(e.reason_code)), 1)) : d("", !0)]), v("span", { class: b(["tm-badge", `tm-badge--${ve(e.outcome).tone}`]) }, g(ve(e.outcome).label), 3)]))), 128))])) : d("", !0)])) : d("", !0)
				], 64)) : d("", !0),
				R.value ? (n(), E("div", Cs, [v("div", ws, g(R.value), 1)])) : d("", !0),
				L.value ? (n(), E("div", Ts, [v("div", Es, g(L.value), 1)])) : d("", !0)
			])) : z.value ? (n(), E("div", Ds, [
				v("div", Os, [v("div", ks, [
					r[26] ||= D(" 加入请求（", -1),
					v("span", As, "#" + g(z.value.join_request_id), 1),
					r[27] ||= D("）已受理并进入后台执行，实际入组结果请在邀请列表或任务中心追踪。 ", -1)
				])]),
				v("div", js, [
					v("div", Ms, [r[28] ||= v("span", null, "已入队", -1), v("strong", null, g(z.value.summary.queued_count), 1)]),
					v("div", Ns, [r[29] ||= v("span", null, "复用进行中", -1), v("strong", null, g(z.value.summary.reused_active_count), 1)]),
					v("div", Ps, [r[30] ||= v("span", null, "跳过", -1), v("strong", null, g(z.value.summary.skipped_count), 1)])
				]),
				V.value ? (n(), E("div", Fs, [v("div", Is, g(V.value), 1)])) : d("", !0),
				v("div", {
					class: "tm-candidate-list",
					style: { "max-height": "280px" },
					"aria-busy": B.value
				}, [z.value.items.length ? d("", !0) : (n(), E("div", Rs, " 当前页暂无明细条目。 ")), (n(!0), E(p, null, o(z.value.items, (e) => (n(), E("div", {
					key: `${e.account_id}:${e.invitation_id ?? "none"}`,
					class: "tm-candidate-row"
				}, [v("div", zs, [v("div", Bs, [v("span", null, g(e.email), 1), v("span", Vs, "#" + g(e.account_id), 1)]), v("div", Hs, g(e.reason || (e.reason_code ? T(G)(e.reason_code) : "已受理等待执行")), 1)]), v("div", Us, [v("span", { class: b(["tm-badge", `tm-badge--${ye(e.outcome).tone}`]) }, g(ye(e.outcome).label), 3), e.task_id ? (n(), E("button", {
					key: 0,
					type: "button",
					class: "tm-btn tm-btn--soft tm-btn--sm",
					onClick: (t) => s("openTask", e.task_id, e.run_id)
				}, " 查看任务 ", 8, Ws)) : d("", !0)])]))), 128))], 8, Ls),
				Z.value > 1 ? (n(), E("div", Gs, [
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: z.value.page <= 1 || B.value,
						onClick: r[4] ||= (e) => _e(z.value.page - 1)
					}, " 上一页 ", 8, Ks),
					v("span", qs, " 第 " + g(z.value.page) + " / " + g(Z.value) + " 页（共 " + g(z.value.total_items) + " 条） ", 1),
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--sm",
						disabled: z.value.page >= Z.value || B.value,
						onClick: r[5] ||= (e) => _e(z.value.page + 1)
					}, " 下一页 ", 8, Js)
				])) : d("", !0)
			])) : d("", !0),
			v("div", Ys, [l.value === "preview" ? (n(), E(p, { key: 0 }, [r[31] ||= v("span", { class: "tm-field__hint" }, " 默认普通成员角色，自动接受指定工作区邀请并保留原个人空间 ", -1), v("div", Xs, [v("button", {
				type: "button",
				class: "tm-btn",
				disabled: I.value || M.value,
				onClick: be
			}, " 取消 ", 8, Zs), v("button", {
				type: "button",
				class: "tm-btn tm-btn--primary",
				disabled: !Y.value,
				onClick: ge
			}, g(I.value ? "正在受理…" : "确认发起加入"), 9, Qs)])], 64)) : (n(), E(p, { key: 1 }, [v("span", $s, " 共请求 " + g(z.value?.summary.requested_count ?? 0) + " 个目标账号 ", 1), v("div", ec, [q.value ? (n(), E("button", {
				key: 0,
				type: "button",
				class: "tm-btn tm-btn--soft",
				onClick: r[6] ||= (e) => s("openTeamDetail", q.value)
			}, " 进入 Team 邀请列表追踪 ")) : d("", !0), v("button", {
				type: "button",
				class: "tm-btn tm-btn--primary",
				onClick: be
			}, " 完成并关闭 ")])], 64))])
		], 40, jo));
	}
}), nc = {
	class: "tm-summary-strip",
	"aria-label": "Team 工作区概览"
}, rc = { class: "tm-summary-card" }, ic = { class: "tm-summary-card__value" }, ac = { class: "tm-summary-card__value" }, oc = { class: "tm-summary-card__value" }, sc = {
	class: "ui-list",
	"aria-label": "Team 工作区列表"
}, cc = { class: "ui-list-count" }, lc = { key: 0 }, uc = { class: "tm-search-box" }, dc = ["disabled"], fc = ["disabled"], pc = {
	key: 0,
	class: "ui-list-bulkbar"
}, mc = { class: "ui-list-bulkbar__count" }, hc = ["aria-busy"], gc = {
	scope: "col",
	class: "ui-col-check"
}, _c = [
	"checked",
	"indeterminate",
	"disabled"
], vc = { scope: "col" }, yc = { scope: "col" }, bc = { class: "list-filter-options" }, xc = { class: "list-filter-option" }, Sc = ["checked"], Cc = [
	"value",
	"checked",
	"onChange"
], wc = { key: 0 }, Tc = { class: "list-filter-actions" }, Ec = {
	scope: "col",
	title: "远端已确认加入的成员数"
}, Dc = {
	scope: "col",
	title: "远端待接受的邀请数"
}, Oc = { scope: "col" }, kc = { scope: "col" }, Ac = { scope: "col" }, jc = { class: "list-filter-options" }, Mc = { class: "list-filter-option" }, Nc = ["checked"], Pc = [
	"value",
	"checked",
	"onChange"
], Fc = { key: 0 }, Ic = { class: "list-filter-actions" }, Lc = { class: "ui-col-check" }, Rc = [
	"aria-label",
	"checked",
	"onChange"
], zc = { "data-label": "工作区" }, Bc = { class: "tm-workspace-identity" }, Vc = { class: "tm-workspace-copy" }, Hc = { class: "tm-workspace-title-row" }, Uc = ["title", "onClick"], Wc = {
	key: 0,
	class: "tm-plan-tag"
}, Gc = { class: "tm-workspace-sub" }, Kc = ["title"], qc = { "data-label": "管理母号" }, Jc = { class: "tm-cell-stack" }, Yc = { class: "tm-cell-primary" }, Xc = ["title", "onClick"], Zc = { key: 1 }, Qc = {
	class: "tm-cell-sub",
	style: {
		display: "flex",
		"align-items": "center",
		gap: "5px",
		"flex-wrap": "wrap"
	}
}, $c = {
	key: 0,
	class: "tm-badge tm-badge--neutral"
}, el = {
	key: 1,
	class: "tm-badge tm-badge--danger"
}, tl = { "data-label": "已确认成员" }, nl = { class: "tm-metric-cell" }, rl = { "data-label": "待接受邀请" }, il = { class: "tm-metric-cell" }, al = { "data-label": "处理中" }, ol = { class: "tm-metric-cell" }, sl = { "data-label": "席位 / 上限" }, cl = { class: "tm-cell-stack" }, ll = { class: "tm-cell-primary" }, ul = { class: "tm-cell-sub" }, dl = { "data-label": "最近同步" }, fl = { class: "tm-cell-stack" }, pl = { class: "tm-cell-primary" }, ml = {
	key: 0,
	class: "tm-badge__dot"
}, hl = ["title"], gl = {
	key: 1,
	class: "tm-cell-sub tm-tabular"
}, _l = { "data-label": "操作" }, vl = { class: "tm-row-actions" }, yl = ["onClick"], bl = [
	"disabled",
	"title",
	"onClick"
], xl = ["disabled", "onClick"], Sl = { class: "tm-inline-menu__panel" }, Cl = ["onClick"], wl = ["onClick"], Tl = ["onClick"], El = /* @__PURE__ */ t({
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
		let S = e, C = u, w = [
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
		], O = [
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
			}
		], k = c({
			page: 1,
			page_size: 20,
			q: "",
			role: "",
			last_sync_status: ""
		}), A = h(""), j = h(null), M = h(!1), N = h(!1), P = h(""), F = h([]), H = h(0), W = h({}), K = h(null), J = h(/* @__PURE__ */ new Set()), X = h(/* @__PURE__ */ new Set()), ie = h(null), { widths: ae, total: Z, resize: Q, resizeWithKeyboard: oe } = I({
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
		}), se, ce = null, le = 0;
		function ue(e) {
			return `tm-badge--${e}`;
		}
		function de(e, t) {
			let n = W.value[e];
			if (!n) return null;
			let r = n.find((e) => e.value === t);
			return r ? r.count : null;
		}
		let fe = x(() => F.value.length > 0 && F.value.every((e) => J.value.has(e.team_id))), pe = x(() => !fe.value && F.value.some((e) => J.value.has(e.team_id)));
		function he(e) {
			let t = new Set(J.value);
			for (let n of F.value) e ? t.add(n.team_id) : t.delete(n.team_id);
			J.value = t;
		}
		function ge(e, t) {
			let n = new Set(J.value);
			t ? n.add(e) : n.delete(e), J.value = n;
		}
		function _e() {
			J.value = /* @__PURE__ */ new Set();
		}
		let ve = x(() => {
			let e = [];
			return k.q && e.push({
				key: "q",
				label: `关键词：${k.q}`,
				removeLabel: "清除关键词筛选"
			}), k.role && e.push({
				key: "role",
				label: `母号角色：${ne(k.role)}`,
				removeLabel: "清除母号角色筛选"
			}), k.last_sync_status && e.push({
				key: "last_sync_status",
				label: `同步状态：${re(k.last_sync_status)}`,
				removeLabel: "清除同步状态筛选"
			}), e;
		}), Se = x(() => ve.value.length > 0);
		function Ce(e) {
			e === "q" ? (clearTimeout(se), A.value = "", k.q = "") : e === "role" ? k.role = "" : e === "last_sync_status" && (k.last_sync_status = ""), k.page = 1, Ne();
		}
		function we() {
			clearTimeout(se), A.value = "", k.q = "", k.role = "", k.last_sync_status = "", k.page = 1, Ne();
		}
		function Te() {
			clearTimeout(se), A.value = "", k.q !== "" && (k.q = "", k.page = 1, Ne());
		}
		function Ee(e) {
			k.role = e, k.page = 1, j.value = null, Ne();
		}
		function De(e) {
			k.last_sync_status = e, k.page = 1, j.value = null, Ne();
		}
		function Oe(e) {
			k.page = e, Ne();
		}
		function ke(e) {
			k.page_size = e, k.page = 1, Ne();
		}
		function Ae(e) {
			let t = ie.value;
			t && t.querySelectorAll("details.tm-inline-menu[open]").forEach((t) => {
				e && t === e || (t.open = !1);
			});
		}
		function je(e) {
			let t = e.currentTarget;
			t?.open && Ae(t);
		}
		function Me(e) {
			Ae((e.target instanceof Element ? e.target : null)?.closest("details.tm-inline-menu") ?? null);
		}
		async function Ne(e = {}) {
			ce?.abort();
			let t = new AbortController();
			ce = t;
			let n = ++le;
			e.silent || (M.value = !0), P.value = "";
			let r = {
				page: k.page,
				page_size: k.page_size,
				include_facets: e.includeFacets ?? 1,
				...k.q ? { q: k.q } : {},
				...k.role ? { role: k.role } : {},
				...k.last_sync_status ? { last_sync_status: k.last_sync_status } : {}
			};
			try {
				let e = await S.api.list(r, t.signal);
				if (n !== le) return;
				F.value = e.items, H.value = e.total, K.value = e.summary, e.facets && Object.keys(e.facets).length > 0 && (W.value = e.facets);
			} catch (r) {
				if (t.signal.aborted || n !== le) return;
				let i = r instanceof Error ? r.message : "加载 Team 工作区列表失败";
				e.silent || (P.value = i);
			} finally {
				ce === t && (ce = null), n === le && !e.silent && (M.value = !1);
			}
		}
		async function Pe(e) {
			if (X.value.has(e.team_id)) return;
			let t = new Set(X.value);
			t.add(e.team_id), X.value = t;
			try {
				let t = await S.api.syncTeam(e.team_id);
				S.callbacks.notify(t.reused ? `工作区「${e.effective_name}」已有进行中的同步任务` : `已启动工作区「${e.effective_name}」同步`), await Ne({
					silent: !0,
					includeFacets: 0
				});
			} catch (e) {
				S.callbacks.notify(e instanceof Error ? e.message : "同步工作区提交失败");
			} finally {
				let t = new Set(X.value);
				t.delete(e.team_id), X.value = t;
			}
		}
		async function Fe() {
			let e = [...J.value];
			if (e.length && !N.value) {
				N.value = !0;
				try {
					let t = await S.api.syncTeamsBulk(e);
					S.callbacks.notify(`批量同步已受理：排队 ${t.queued_count}，复用 ${t.reused_count}，跳过 ${t.skipped_count}`), _e(), await Ne({
						silent: !0,
						includeFacets: 0
					});
				} catch (e) {
					S.callbacks.notify(e instanceof Error ? e.message : "批量同步提交失败");
				} finally {
					N.value = !1;
				}
			}
		}
		function Ie(e, t) {
			let n = e.currentTarget?.closest("details");
			n && (n.open = !1), S.callbacks.openTasksForTeam(t.team_id, t.effective_name);
		}
		function Le(e, t) {
			let n = e.currentTarget?.closest("details");
			n && (n.open = !1), C("open-edit", t);
		}
		function Re(e, t) {
			let n = e.currentTarget?.closest("details");
			n && (n.open = !1), C("open-change-manager", t);
		}
		return Qn({
			visible: () => S.visible,
			shouldPoll: () => F.value.some(xe),
			onPoll: () => Ne({
				silent: !0,
				includeFacets: 0
			}),
			intervalMs: 3e3
		}), i(A, (e) => {
			clearTimeout(se);
			let t = e.trim();
			t !== k.q && (se = setTimeout(() => {
				k.q = t, k.page = 1, Ne();
			}, 250));
		}), s(() => {
			document.addEventListener("click", Me), Ne();
		}), ee(() => {
			clearTimeout(se), ce?.abort(), document.removeEventListener("click", Me);
		}), t({ refresh: (e) => Ne({
			silent: e?.silent,
			includeFacets: +!e?.silent
		}) }), (t, i) => (n(), E("div", {
			ref_key: "listRootRef",
			ref: ie,
			class: "tm-root"
		}, [v("section", nc, [
			v("article", rc, [i[30] ||= v("div", { class: "tm-summary-card__meta" }, [v("span", { class: "tm-summary-card__label" }, "已绑定工作区"), v("span", { class: "tm-summary-card__hint" }, "当前已纳管的工作区总数")], -1), v("strong", ic, g(K.value ? K.value.total_teams.toLocaleString() : "—"), 1)]),
			v("article", { class: b(["tm-summary-card", { "is-active": (K.value?.syncing_teams ?? 0) > 0 }]) }, [i[31] ||= v("div", { class: "tm-summary-card__meta" }, [v("span", { class: "tm-summary-card__label" }, "正在同步 / 处理中"), v("span", { class: "tm-summary-card__hint" }, "包含同步及入组排队执行")], -1), v("strong", ac, g(K.value ? K.value.syncing_teams.toLocaleString() : "—"), 1)], 2),
			v("article", { class: b(["tm-summary-card", { "is-warn": (K.value?.attention_teams ?? 0) > 0 }]) }, [i[32] ||= v("div", { class: "tm-summary-card__meta" }, [v("span", { class: "tm-summary-card__label" }, "需关注工作区"), v("span", { class: "tm-summary-card__hint" }, "同步异常、权限受限或待设上限")], -1), v("strong", oc, g(K.value ? K.value.attention_teams.toLocaleString() : "—"), 1)], 2)
		]), v("section", sc, [
			l(U, { filtered: Se.value }, {
				actions: r(() => [
					v("button", {
						type: "button",
						class: "tm-btn",
						disabled: !J.value.size || N.value,
						onClick: i[2] ||= (e) => void Fe()
					}, g(N.value ? "同步提交中…" : "同步选中"), 9, dc),
					v("button", {
						type: "button",
						class: "tm-btn ui-refresh-button",
						disabled: M.value,
						onClick: i[3] ||= (e) => void Ne()
					}, g(M.value ? "刷新中…" : "刷新"), 9, fc),
					v("button", {
						type: "button",
						class: "tm-btn tm-btn--primary",
						onClick: i[4] ||= (e) => C("open-bind")
					}, " 绑定已有 Team ")
				]),
				default: r(() => [
					v("span", cc, [D(" 共 " + g(H.value.toLocaleString()) + " 个工作区 ", 1), J.value.size ? (n(), E("small", lc, "已选 " + g(J.value.size) + " 项", 1)) : d("", !0)]),
					v("div", uc, [
						i[33] ||= v("svg", {
							class: "tm-search-box__icon",
							viewBox: "0 0 16 16",
							"aria-hidden": "true"
						}, [v("circle", {
							cx: "7",
							cy: "7",
							r: "4.5"
						}), v("path", { d: "m10.5 10.5 3 3" })], -1),
						a(v("input", {
							"onUpdate:modelValue": i[0] ||= (e) => A.value = e,
							type: "search",
							"aria-label": "搜索工作区",
							placeholder: "搜索名称 / workspace_id / 母号邮箱",
							onKeydown: i[1] ||= f(y((e) => {
								k.q = A.value.trim(), k.page = 1, Ne();
							}, ["prevent"]), ["enter"])
						}, null, 544), [[te, A.value]]),
						A.value ? (n(), E("button", {
							key: 0,
							type: "button",
							class: "tm-search-box__clear",
							"aria-label": "清空搜索",
							onClick: Te
						}, " × ")) : d("", !0)
					]),
					l(B, {
						items: ve.value,
						onRemove: Ce
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			J.value.size ? (n(), E("div", pc, [v("span", mc, "已跨页选中 " + g(J.value.size) + " 个工作区", 1), v("button", {
				type: "button",
				class: "tm-btn tm-btn--ghost tm-btn--sm",
				onClick: _e
			}, " 清空选择 ")])) : d("", !0),
			v("div", {
				class: "ui-table-wrap ui-table-scroll",
				tabindex: "0",
				"aria-label": "Team 工作区表格，可横向滚动",
				"aria-busy": M.value
			}, [v("table", {
				class: "ui-table ui-table--sticky-end ui-table--cards",
				style: m({ "--ui-table-width": `${T(Z)}px` })
			}, [
				i[45] ||= v("caption", { class: "ui-sr-only" }, "已绑定的 ChatGPT Team 工作区列表", -1),
				v("colgroup", null, [(n(!0), E(p, null, o(T(ae), (e, t) => (n(), E("col", {
					key: t,
					style: m({ width: `${e}px` })
				}, null, 4))), 128))]),
				v("thead", null, [v("tr", null, [
					v("th", gc, [v("input", {
						type: "checkbox",
						"aria-label": "全选当前页工作区",
						checked: fe.value,
						indeterminate: pe.value,
						disabled: !F.value.length,
						onChange: i[5] ||= (e) => he(e.target.checked)
					}, null, 40, _c)]),
					v("th", vc, [i[34] ||= D(" 工作区 ", -1), l(L, {
						label: "工作区",
						onStart: i[6] ||= (e) => T(Q)(1, e),
						onNudge: i[7] ||= (e) => T(oe)(1, e)
					})]),
					v("th", yc, [l(R, {
						label: "管理母号",
						active: !!k.role,
						summary: k.role ? T(ne)(k.role) : "",
						open: e.visible && j.value === "role",
						"onUpdate:open": i[11] ||= (e) => j.value = e ? "role" : null
					}, {
						default: r(() => [v("fieldset", bc, [
							i[36] ||= v("legend", { class: "ui-sr-only" }, "按母号角色筛选", -1),
							v("label", xc, [v("input", {
								type: "radio",
								name: "team-role",
								value: "",
								checked: !k.role,
								onChange: i[8] ||= (e) => Ee("")
							}, null, 40, Sc), i[35] ||= v("span", null, "全部角色", -1)]),
							(n(), E(p, null, o(w, (e) => v("label", {
								key: e.value,
								class: "list-filter-option"
							}, [
								v("input", {
									type: "radio",
									name: "team-role",
									value: e.value,
									checked: k.role === e.value,
									onChange: (t) => Ee(e.value)
								}, null, 40, Cc),
								v("span", null, g(e.label), 1),
								de("role", e.value) === null ? d("", !0) : (n(), E("small", wc, g(de("role", e.value)), 1))
							])), 64))
						]), v("div", Tc, [v("button", {
							type: "button",
							onClick: i[9] ||= (e) => Ee("")
						}, "清除"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[10] ||= (e) => j.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(L, {
						label: "管理母号",
						onStart: i[12] ||= (e) => T(Q)(2, e),
						onNudge: i[13] ||= (e) => T(oe)(2, e)
					})]),
					v("th", Ec, [i[37] ||= D(" 已确认 ", -1), l(L, {
						label: "已确认成员",
						onStart: i[14] ||= (e) => T(Q)(3, e),
						onNudge: i[15] ||= (e) => T(oe)(3, e)
					})]),
					v("th", Dc, [i[38] ||= D(" 待接受 ", -1), l(L, {
						label: "待接受邀请",
						onStart: i[16] ||= (e) => T(Q)(4, e),
						onNudge: i[17] ||= (e) => T(oe)(4, e)
					})]),
					v("th", Oc, [i[39] ||= D(" 处理中 ", -1), l(L, {
						label: "处理中",
						onStart: i[18] ||= (e) => T(Q)(5, e),
						onNudge: i[19] ||= (e) => T(oe)(5, e)
					})]),
					v("th", kc, [i[40] ||= D(" 席位 / 上限 ", -1), l(L, {
						label: "席位 / 上限",
						onStart: i[20] ||= (e) => T(Q)(6, e),
						onNudge: i[21] ||= (e) => T(oe)(6, e)
					})]),
					v("th", Ac, [l(R, {
						label: "最近同步",
						active: !!k.last_sync_status,
						summary: k.last_sync_status ? T(re)(k.last_sync_status) : "",
						open: e.visible && j.value === "last_sync_status",
						"onUpdate:open": i[25] ||= (e) => j.value = e ? "last_sync_status" : null
					}, {
						default: r(() => [v("fieldset", jc, [
							i[42] ||= v("legend", { class: "ui-sr-only" }, "按同步状态筛选", -1),
							v("label", Mc, [v("input", {
								type: "radio",
								name: "team-sync",
								value: "",
								checked: !k.last_sync_status,
								onChange: i[22] ||= (e) => De("")
							}, null, 40, Nc), i[41] ||= v("span", null, "全部同步状态", -1)]),
							(n(), E(p, null, o(O, (e) => v("label", {
								key: e.value,
								class: "list-filter-option"
							}, [
								v("input", {
									type: "radio",
									name: "team-sync",
									value: e.value,
									checked: k.last_sync_status === e.value,
									onChange: (t) => De(e.value)
								}, null, 40, Pc),
								v("span", null, g(e.label), 1),
								de("last_sync_status", e.value) === null ? d("", !0) : (n(), E("small", Fc, g(de("last_sync_status", e.value)), 1))
							])), 64))
						]), v("div", Ic, [v("button", {
							type: "button",
							onClick: i[23] ||= (e) => De("")
						}, "清除"), v("button", {
							type: "button",
							class: "list-filter-primary",
							onClick: i[24] ||= (e) => j.value = null
						}, "完成")])]),
						_: 1
					}, 8, [
						"active",
						"summary",
						"open"
					]), l(L, {
						label: "最近同步",
						onStart: i[26] ||= (e) => T(Q)(7, e),
						onNudge: i[27] ||= (e) => T(oe)(7, e)
					})]),
					i[43] ||= v("th", { scope: "col" }, "操作", -1)
				])]),
				v("tbody", null, [(n(!0), E(p, null, o(F.value, (t) => (n(), E("tr", {
					key: t.team_id,
					class: b({ "is-selected": J.value.has(t.team_id) })
				}, [
					v("td", Lc, [v("input", {
						type: "checkbox",
						"aria-label": `选择工作区 ${t.effective_name}`,
						checked: J.value.has(t.team_id),
						onChange: (e) => ge(t.team_id, e.target.checked)
					}, null, 40, Rc)]),
					v("td", zc, [v("div", Bc, [v("div", {
						class: "tm-workspace-avatar",
						style: m({ "--tm-hue": String(T(ye)(t.workspace_id)) }),
						"aria-hidden": "true"
					}, g(T(be)(t.effective_name)), 5), v("div", Vc, [v("div", Hc, [v("button", {
						type: "button",
						class: "tm-workspace-name-btn",
						title: t.effective_name,
						onClick: (e) => C("open-detail", t.team_id, "members")
					}, g(t.effective_name), 9, Uc), t.plan_type ? (n(), E("span", Wc, g(t.plan_type), 1)) : d("", !0)]), v("div", Gc, [v("span", {
						class: "tm-mono",
						title: t.workspace_id
					}, g(t.workspace_id), 9, Kc)])])])]),
					v("td", qc, [v("div", Jc, [v("div", Yc, [t.manager_account.account_id ? (n(), E("button", {
						key: 0,
						type: "button",
						class: "tm-link-btn",
						title: t.manager_account.email,
						onClick: (n) => e.callbacks.openAccountDetail(t.manager_account.account_id)
					}, g(t.manager_account.email || `#${t.manager_account.account_id}`), 9, Xc)) : (n(), E("span", Zc, g(t.manager_account.email || "—"), 1))]), v("div", Qc, [
						v("span", { class: b(["tm-badge", ue(T(q)(t.manager_role))]) }, g(T(ne)(t.manager_role)), 3),
						t.manager_account.archived ? (n(), E("span", $c, "已归档")) : d("", !0),
						t.can_manage === !1 ? (n(), E("span", el, "无管理权限")) : d("", !0)
					])])]),
					v("td", tl, [v("div", nl, [v("span", { class: b(["tm-metric-val", { "is-null": t.confirmed_member_count === null }]) }, g(T($)(t.confirmed_member_count, "待同步")), 3)])]),
					v("td", rl, [v("div", il, [v("span", { class: b(["tm-metric-val", { "is-null": t.pending_invite_count === null }]) }, g(T($)(t.pending_invite_count, "待同步")), 3)])]),
					v("td", al, [v("div", ol, [v("span", { class: b(["tm-metric-val", { "is-processing": t.processing_count > 0 }]) }, g(T($)(t.processing_count, "—")), 3)])]),
					v("td", sl, [v("div", cl, [v("div", ll, [v("span", null, g(T(me)(t).primary), 1)]), v("div", ul, [v("span", { class: b(["tm-badge", ue(T(me)(t).tone)]) }, g(T(me)(t).secondary), 3)])])]),
					v("td", dl, [v("div", fl, [v("div", pl, [v("span", { class: b(["tm-badge", ue(T(Y)(t.last_sync_status))]) }, [t.last_sync_status === "queued" || t.last_sync_status === "running" ? (n(), E("span", ml)) : d("", !0), D(" " + g(T(re)(t.last_sync_status)), 1)], 2)]), t.last_sync_status === "failed" ? (n(), E("div", {
						key: 0,
						class: "tm-cell-sub is-danger",
						title: t.last_sync_error?.summary || ""
					}, g(T(G)(t.last_sync_error?.reason_code, t.last_sync_error)), 9, hl)) : (n(), E("div", gl, g(t.last_synced_at ? e.callbacks.formatDateTime(t.last_synced_at) : "待同步"), 1))])]),
					v("td", _l, [v("div", vl, [
						v("button", {
							type: "button",
							class: "tm-btn tm-btn--sm",
							onClick: (e) => C("open-detail", t.team_id, "members")
						}, " 查看 ", 8, yl),
						v("button", {
							type: "button",
							class: "tm-btn tm-btn--sm tm-btn--soft",
							disabled: t.can_manage === !1,
							title: t.can_manage === !1 ? "当前母号无管理权限，请先核验或更换母号" : "选择账号批量邀请并自动加入",
							onClick: (e) => C("open-join", t)
						}, " 拉人 ", 8, bl),
						v("button", {
							type: "button",
							class: "tm-btn tm-btn--sm",
							disabled: X.value.has(t.team_id) || t.last_sync_status === "queued" || t.last_sync_status === "running",
							onClick: (e) => void Pe(t)
						}, g(X.value.has(t.team_id) ? "同步中" : "同步"), 9, xl),
						v("details", {
							class: "tm-inline-menu",
							onToggle: je
						}, [i[44] ||= v("summary", { "aria-label": "更多操作" }, "···", -1), v("div", Sl, [
							v("button", {
								type: "button",
								onClick: (e) => Ie(e, t)
							}, " 查看相关任务 ", 8, Cl),
							v("button", {
								type: "button",
								onClick: (e) => Le(e, t)
							}, " 设置别名与上限 ", 8, wl),
							v("button", {
								type: "button",
								onClick: (e) => Re(e, t)
							}, " 更换管理母号 ", 8, Tl)
						])], 32)
					])])
				], 2))), 128)), F.value.length ? d("", !0) : (n(), _(z, {
					key: 0,
					colspan: 9,
					loading: M.value,
					error: P.value,
					"loading-title": "正在加载 Team 工作区",
					"loading-text": "获取已绑定的工作区、成员快照与同步状态",
					"error-title": "加载工作区列表失败",
					title: Se.value ? "没有匹配的工作区" : "还没有绑定的 Team 工作区",
					text: Se.value ? "可调整搜索关键词或清除筛选条件后再试。" : "选择一个已有 ChatGPT Team 管理权的主账号完成探测与绑定，即可统一管理成员、席位并自动批量拉人。",
					"retry-label": "重试",
					onRetry: i[29] ||= (e) => void Ne()
				}, {
					default: r(() => [!M.value && !P.value && !Se.value ? (n(), E("button", {
						key: 0,
						type: "button",
						class: "tm-btn tm-btn--primary",
						onClick: i[28] ||= (e) => C("open-bind")
					}, " 绑定已有 Team ")) : !M.value && !P.value && Se.value ? (n(), E("button", {
						key: 1,
						type: "button",
						class: "tm-btn tm-btn--sm",
						onClick: we
					}, " 清除筛选条件 ")) : d("", !0)]),
					_: 1
				}, 8, [
					"loading",
					"error",
					"title",
					"text"
				]))])
			], 4)], 8, hc),
			l(V, {
				page: k.page,
				size: k.page_size,
				total: H.value,
				busy: M.value,
				label: "Team 工作区列表分页",
				"onUpdate:page": Oe,
				"onUpdate:size": ke
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy"
			])
		])], 512));
	}
}), Dl = { class: "tm-page-shell" }, Ol = /* @__PURE__ */ t({
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
				team_id: M(e.team_id, "Team ID"),
				section: e.section === "invitations" ? "invitations" : "members"
			} : {
				tab: "teams",
				view: "list"
			};
		}
		let s = o(i.initialNavigation), c = h(i.initialVisible), u = h(s.view), f = h(s.team_id ?? null), p = h(s.section ?? "members"), m = h(""), g = h(0), v = C(null), ee = h(null), y = h(null), b = h(!1), x = h("bind"), S = C(null), te = h(!1), T = C(null), D = h(!1), O = C(null), k = h(!1), A = C(null), j = C(null);
		function N() {
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
		function P(t, n = "push", r = {}) {
			let a = o(t), s = u.value === "list";
			a.view === "detail" && a.team_id ? (s && typeof window < "u" && (g.value = window.scrollY || 0), u.value = "detail", f.value = a.team_id, p.value = a.section ?? "members", typeof window < "u" && s && e(() => window.scrollTo({ top: 0 }))) : (u.value = "list", f.value = null, p.value = "members", m.value = "", v.value = null, e(() => {
				typeof window < "u" && window.scrollTo({ top: g.value }), ee.value?.refresh({ silent: !0 });
			})), r.emit !== !1 && i.callbacks.onNavigation(N(), n);
		}
		function F(e, t = "members") {
			m.value = "", P({
				view: "detail",
				team_id: e,
				section: t
			}, "push");
		}
		function I() {
			P({ view: "list" }, "push");
		}
		function L(e) {
			p.value !== e && (p.value = e, i.callbacks.onNavigation(N(), "replace"));
		}
		function R() {
			x.value = "bind", S.value = null, b.value = !0;
		}
		function z(e) {
			x.value = "change_manager", S.value = e, b.value = !0;
		}
		function B(e) {
			T.value = e, te.value = !0;
		}
		function V(e) {
			O.value = e, D.value = !0;
		}
		function H(e) {
			A.value = e.targetTeamId && v.value?.team_id === e.targetTeamId ? v.value : null, j.value = e, k.value = !0;
		}
		function U(e) {
			let t = O.value;
			D.value = !1, t && (A.value = t, j.value = {
				mode: "explicit",
				accountIds: e.accountIds,
				expectedEmails: e.expectedEmails,
				targetTeamId: t.team_id
			}, k.value = !0);
		}
		function W(e) {
			b.value = !1, ee.value?.refresh({ silent: !0 }), P({
				view: "detail",
				team_id: e.team_id,
				section: "members"
			}, "push");
		}
		function G(e) {
			b.value = !1, ne(e);
		}
		function K(e) {
			b.value = !1, P({
				view: "detail",
				team_id: e,
				section: "members"
			}, "push");
		}
		function ne(e) {
			te.value = !1, T.value?.team_id === e.team_id && (T.value = e), v.value?.team_id === e.team_id && (v.value = e), A.value?.team_id === e.team_id && (A.value = e), O.value?.team_id === e.team_id && (O.value = e), u.value === "detail" && f.value === e.team_id && y.value?.updateTeamSnapshot(e), ee.value?.refresh({ silent: !0 });
		}
		function q() {
			u.value === "detail" && f.value && y.value?.refresh({ silent: !0 }), ee.value?.refresh({ silent: !0 });
		}
		function J(e, t) {
			u.value === "detail" && f.value === t && y.value?.refreshAll(), ee.value?.refresh({ silent: !0 });
		}
		function re() {
			b.value = !1, te.value = !1, D.value = !1, k.value = !1;
		}
		function Y(e) {
			c.value = e;
		}
		async function X() {
			u.value === "detail" && f.value ? y.value?.refreshAll() : await ee.value?.refresh();
		}
		return r({
			setVisible: Y,
			navigate: P,
			navigationState: N,
			openJoinFromAccounts: H,
			openBindModal: R,
			closeDialogs: re,
			refresh: X
		}), (e, r) => (n(), E("div", Dl, [
			a(l(El, {
				ref_key: "listRef",
				ref: ee,
				api: t.api,
				visible: c.value && u.value === "list",
				callbacks: t.callbacks,
				onOpenDetail: F,
				onOpenBind: R,
				onOpenEdit: B,
				onOpenChangeManager: z,
				onOpenJoin: V
			}, null, 8, [
				"api",
				"visible",
				"callbacks"
			]), [[w, u.value === "list"]]),
			u.value === "detail" && f.value ? (n(), _(co, {
				key: 0,
				ref_key: "detailRef",
				ref: y,
				api: t.api,
				"team-id": f.value,
				section: p.value,
				visible: c.value && u.value === "detail",
				callbacks: t.callbacks,
				"join-request-id": m.value,
				onBack: I,
				"onUpdate:section": L,
				onOpenEdit: B,
				onOpenChangeManager: z,
				onOpenJoin: V,
				onTeamLoaded: r[0] ||= (e) => v.value = e,
				onClearJoinRequest: r[1] ||= (e) => m.value = ""
			}, null, 8, [
				"api",
				"team-id",
				"section",
				"visible",
				"callbacks",
				"join-request-id"
			])) : d("", !0),
			l(zt, {
				open: b.value,
				api: t.api,
				mode: x.value,
				team: S.value,
				visible: c.value,
				onClose: r[2] ||= (e) => b.value = !1,
				onBound: W,
				onManagerUpdated: G,
				onOpenExistingTeam: K,
				onNotify: t.callbacks.notify
			}, null, 8, [
				"open",
				"api",
				"mode",
				"team",
				"visible",
				"onNotify"
			]),
			l(Ao, {
				open: te.value,
				api: t.api,
				team: T.value,
				visible: c.value,
				onClose: r[3] ||= (e) => te.value = !1,
				onUpdated: ne,
				onConflict: q,
				onNotify: t.callbacks.notify
			}, null, 8, [
				"open",
				"api",
				"team",
				"visible",
				"onNotify"
			]),
			l(Xn, {
				open: D.value,
				api: t.api,
				team: O.value,
				visible: c.value,
				onClose: r[4] ||= (e) => D.value = !1,
				onConfirmCandidates: U,
				onOpenAdvancedInAccounts: r[5] ||= (e) => {
					D.value = !1, t.callbacks.openAccountsCandidateMode(e);
				},
				onNotify: t.callbacks.notify
			}, null, 8, [
				"open",
				"api",
				"team",
				"visible",
				"onNotify"
			]),
			l(tc, {
				open: k.value,
				api: t.api,
				"initial-team": A.value,
				target: j.value,
				visible: c.value,
				"format-date-time": t.callbacks.formatDateTime,
				onClose: r[6] ||= (e) => k.value = !1,
				onSubmitted: J,
				onOpenTask: r[7] ||= (e, n) => t.callbacks.openTask(e, n),
				onOpenTeamDetail: r[8] ||= (e) => {
					k.value = !1, P({
						view: "detail",
						team_id: e,
						section: "invitations"
					}, "push");
				},
				onTeamUpdated: ne,
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
function kl(e, t) {
	let n = t.api ?? j(), r = S(Ol, {
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
export { kl as mountTeams };
