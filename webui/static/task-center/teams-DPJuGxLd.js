import { t as e } from "./client-B5R_MNgP.js";
// src/features/teams/contracts.ts
var t = /^[1-9]\d*$/;
function n(e, n = "标识") {
	let r = typeof e == "number" && Number.isSafeInteger(e) && e > 0 ? String(e) : typeof e == "string" ? e.trim() : "";
	if (!t.test(r)) throw Error(`${n}格式无效`);
	return r;
}
function r(e) {
	return e == null || e === "" || e === 0 || e === "0" ? null : n(e);
}
var i = /* @__PURE__ */ new Set([
	"id",
	"team_id",
	"existing_team_id",
	"already_bound_team_id",
	"account_id",
	"manager_account_id",
	"probe_id",
	"invitation_id",
	"member_id",
	"join_request_id",
	"selection_id",
	"task_id",
	"run_id",
	"latest_task_id",
	"latest_run_id",
	"last_sync_task_id",
	"last_sync_run_id",
	"batch_id"
]), a = /* @__PURE__ */ new Set([
	"team_ids",
	"account_ids",
	"invitation_ids",
	"task_ids",
	"run_ids"
]);
function o(e) {
	let t = [], n = 0, r = () => {
		throw SyntaxError("Team 接口响应 JSON 格式无效");
	}, o = () => {
		for (; /[\t\n\r ]/.test(e[n] || "\0");) n++;
	};
	function s() {
		let t = n;
		if (e[n++] !== "\"") return r();
		for (; n < e.length;) {
			let r = e[n++];
			if (r === "\\") n++;
			else if (r === "\"") return JSON.parse(e.slice(t, n));
		}
		return r();
	}
	function c(l = "", u = 0) {
		if (u > 256) throw SyntaxError("Team 接口响应嵌套过深");
		o();
		let d = e[n];
		if (d === "{") {
			if (n++, o(), e[n] === "}") {
				n++;
				return;
			}
			for (;;) {
				o();
				let t = s();
				o(), e[n++] !== ":" && r(), c(t, u + 1), o();
				let i = e[n++];
				if (i === "}") return;
				i !== "," && r();
			}
		}
		if (d === "[") {
			if (n++, o(), e[n] === "]") {
				n++;
				return;
			}
			let t = a.has(l) ? "team_id" : "";
			for (;;) {
				c(t, u + 1), o();
				let i = e[n++];
				if (i === "]") return;
				i !== "," && r();
			}
		}
		if (d === "\"") {
			s();
			return;
		}
		for (let t of [
			"true",
			"false",
			"null"
		]) if (e.startsWith(t, n)) {
			n += t.length;
			return;
		}
		let f = e.slice(n).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
		if (!f) return r();
		let p = f[0], m = n;
		n += p.length, i.has(l) && /^[1-9]\d*$/.test(p) && t.push({
			start: m,
			end: n,
			text: JSON.stringify(p)
		});
	}
	c(), o(), n !== e.length && r();
	let l = "", u = 0;
	for (let n of t) l += e.slice(u, n.start) + n.text, u = n.end;
	return JSON.parse(l + e.slice(u));
}
// src/api/teams.ts
var s = class extends e {
	field;
	retryable;
	details;
	requestId;
	constructor(e, t, n = {}) {
		super(e, t, n.code || ""), this.name = "TeamApiError", this.field = n.field ?? null, this.retryable = !!n.retryable, this.details = Object.freeze({ ...n.details || {} }), this.requestId = n.requestId || "";
	}
};
function c() {
	let e = `${window.location.pathname}${window.location.search}${window.location.hash}`;
	throw window.location.assign(`/login?next=${encodeURIComponent(e)}`), new s("登录已失效，正在跳转登录页", 401, { code: "unauthorized" });
}
function l(e) {
	let t = new URLSearchParams();
	for (let [n, r] of Object.entries(e)) r != null && r !== "" && t.set(n, String(r));
	let n = t.toString();
	return n ? `?${n}` : "";
}
function u() {
	let e = globalThis.crypto?.randomUUID?.();
	return e && e.length >= 16 ? e : `team-${Date.now()}-${Math.random().toString(36).slice(2, 12)}-${Math.random().toString(36).slice(2, 10)}`;
}
var d = /* @__PURE__ */ new Set([
	400,
	403,
	404,
	409,
	410,
	422,
	429
]);
async function f(e, t = {}) {
	let n = new Headers(t.headers);
	n.set("Accept", "application/json");
	let r = await fetch(e, {
		credentials: "same-origin",
		...t,
		headers: n
	});
	(r.status === 401 || r.redirected && new URL(r.url, window.location.origin).pathname === "/login") && c();
	let i = await r.text(), a = null;
	if (i) try {
		a = o(i);
	} catch {
		throw new s(r.ok ? "服务器返回了无法识别的 Team 数据" : `请求失败（HTTP ${r.status}）`, r.status);
	}
	let l = a && typeof a == "object" ? a : null;
	if (!r.ok || !l || l.ok !== !0 || !("data" in l)) {
		let e = l && typeof l.error == "object" && l.error ? l.error : null, t = e?.message || (typeof l?.error == "string" ? l.error : "") || l?.message || `请求失败（HTTP ${r.status}）`, n = e?.code || l?.code || "";
		throw new s(t, r.status, {
			code: n,
			field: e?.field ?? null,
			retryable: e?.retryable ?? r.status >= 500,
			details: e?.details ?? null,
			requestId: String(l?.request_id || "")
		});
	}
	return l.data;
}
async function p(e, t, n, r, i) {
	let a = `turb_team_intent:${e}:${JSON.stringify({
		method: t,
		path: n,
		body: r ?? null
	})}`, o = "";
	try {
		o = sessionStorage.getItem(a) || "";
	} catch {}
	if (!o || o.length < 16) {
		o = u();
		try {
			sessionStorage.setItem(a, o);
		} catch {}
	}
	let c = () => {
		try {
			sessionStorage.removeItem(a);
		} catch {}
	};
	try {
		let e = { "Idempotency-Key": o };
		r !== void 0 && (e["Content-Type"] = "application/json");
		let a = await f(n, {
			method: t,
			headers: e,
			...r === void 0 ? {} : { body: JSON.stringify(r) },
			signal: i
		});
		return c(), a;
	} catch (e) {
		throw e instanceof s && d.has(e.status) && c(), e;
	}
}
function m() {
	return {
		list: (e, t) => f(`/api/teams${l(e)}`, { signal: t }),
		detail: (e, t) => f(`/api/teams/${n(e, "Team ID")}`, { signal: t }),
		createBindingProbe: (e, t) => p("binding_probe", "POST", "/api/teams/binding-probes", {
			manager_account_id: n(e.manager_account_id, "管理母号 ID"),
			...e.target_workspace_id ? { target_workspace_id: e.target_workspace_id } : {}
		}, t),
		getBindingProbe: (e, t) => f(`/api/teams/binding-probes/${n(e, "核验单 ID")}`, { signal: t }),
		createTeam: (e, t) => p(`bind:${e.workspace_id}`, "POST", "/api/teams", {
			...e,
			manager_account_id: n(e.manager_account_id, "管理母号 ID"),
			probe_id: n(e.probe_id, "核验单 ID")
		}, t),
		updateTeam: (e, t, r) => {
			let i = n(e, "Team ID");
			return p(`patch:${i}:${t.expected_revision}`, "PATCH", `/api/teams/${i}`, t, r);
		},
		syncTeam: (e, t) => {
			let r = n(e, "Team ID");
			return p(`sync:${r}`, "POST", `/api/teams/${r}/sync`, {}, t);
		},
		syncTeamsBulk: (e, t) => p("sync_bulk", "POST", "/api/teams/sync-bulk", { team_ids: [...new Set(e.map((e) => n(e, "Team ID")))] }, t),
		reverifyTeam: (e, t) => {
			let r = n(e, "Team ID");
			return p(`reverify:${r}`, "POST", `/api/teams/${r}/reverify`, {}, t);
		},
		listMembers: (e, t, r) => f(`/api/teams/${n(e, "Team ID")}/members${l(t)}`, { signal: r }),
		listInvitations: (e, t, r) => f(`/api/teams/${n(e, "Team ID")}/invitations${l(t)}`, { signal: r }),
		getInvitation: (e, t, r) => f(`/api/teams/${n(e, "Team ID")}/invitations/${n(t, "邀请记录 ID")}`, { signal: r }),
		listCandidates: (e, t, r) => f(`/api/teams/${n(e, "Team ID")}/candidates${l(t)}`, { signal: r }),
		resolveCandidates: (e, t, r) => f(`/api/teams/${n(e, "Team ID")}/candidates/resolve`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ values: [...t] }),
			signal: r
		}),
		previewJoin: (e, t, r) => f(`/api/teams/${n(e, "Team ID")}/join-preview`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(t),
			signal: r
		}),
		submitJoin: (e, t, r) => {
			let i = n(e, "Team ID");
			return p(`join:${i}:${t.expected_team_revision}`, "POST", `/api/teams/${i}/join`, t, r);
		},
		getJoinRequest: (e, t, r = {}, i) => f(`/api/teams/${n(e, "Team ID")}/join-requests/${n(t, "入组请求 ID")}${l(r)}`, { signal: i }),
		continueInvitation: (e, t, r) => {
			let i = n(e, "Team ID"), a = n(t, "邀请记录 ID");
			return p(`inv_continue:${i}:${a}`, "POST", `/api/teams/${i}/invitations/${a}/continue`, {}, r);
		},
		retryInvitation: (e, t, r) => {
			let i = n(e, "Team ID"), a = n(t, "邀请记录 ID");
			return p(`inv_retry:${i}:${a}`, "POST", `/api/teams/${i}/invitations/${a}/retry`, {}, r);
		},
		continueInvitationsBulk: (e, t, r) => {
			let i = n(e, "Team ID"), a = [...new Set(t.map((e) => n(e, "邀请记录 ID")))];
			return p(`inv_continue_bulk:${i}`, "POST", `/api/teams/${i}/invitations/continue-bulk`, { invitation_ids: a }, r);
		},
		retryInvitationsBulk: (e, t, r) => {
			let i = n(e, "Team ID"), a = [...new Set(t.map((e) => n(e, "邀请记录 ID")))];
			return p(`inv_retry_bulk:${i}`, "POST", `/api/teams/${i}/invitations/retry-bulk`, { invitation_ids: a }, r);
		},
		freezeAccountSelection: async (e, t) => {
			let r = await p("freeze_team_join_selection", "POST", "/api/bulk/selections", {
				operation: {
					key: "team_join",
					version: 1
				},
				query: e
			}, t), i = r.selection && typeof r.selection == "object" ? r.selection : r;
			return {
				selection_id: n(i.selection_id ?? i.id, "快照选择 ID"),
				selection_revision: String(i.selection_revision ?? i.revision ?? "1"),
				matched_count: Number(i.matched_count ?? i.total ?? 0)
			};
		}
	};
}
var h = m();
export { o as a, r as i, m as n, n as o, h as r, s as t };
