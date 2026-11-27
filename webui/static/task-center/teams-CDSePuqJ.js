import { t as e } from "./client-B5R_MNgP.js";
// src/features/teams/contracts.ts
var t = /^[1-9]\d*$/, n = "9223372036854775807";
function r(e, r = "标识") {
	let i = typeof e == "number" && Number.isSafeInteger(e) && e > 0 ? String(e) : typeof e == "string" ? e.trim() : "";
	if (!t.test(i) || i.length > 19 || i.length === 19 && i > n) throw Error(`${r}格式无效`);
	return i;
}
function i(e) {
	return e == null || e === "" || e === 0 || e === "0" ? null : r(e);
}
var a = /* @__PURE__ */ new Set([
	"id",
	"team_id",
	"existing_team_id",
	"existing_join_request_id",
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
]), o = /* @__PURE__ */ new Set([
	"team_ids",
	"account_ids",
	"invitation_ids",
	"task_ids",
	"run_ids"
]);
function s(e) {
	let t = [], n = 0, r = () => {
		throw SyntaxError("Team 接口响应 JSON 格式无效");
	}, i = () => {
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
		i();
		let d = e[n];
		if (d === "{") {
			if (n++, i(), e[n] === "}") {
				n++;
				return;
			}
			for (;;) {
				i();
				let t = s();
				i(), e[n++] !== ":" && r(), c(t, u + 1), i();
				let a = e[n++];
				if (a === "}") return;
				a !== "," && r();
			}
		}
		if (d === "[") {
			if (n++, i(), e[n] === "]") {
				n++;
				return;
			}
			let t = o.has(l) ? "team_id" : "";
			for (;;) {
				c(t, u + 1), i();
				let a = e[n++];
				if (a === "]") return;
				a !== "," && r();
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
		n += p.length, a.has(l) && /^[1-9]\d*$/.test(p) && t.push({
			start: m,
			end: n,
			text: JSON.stringify(p)
		});
	}
	c(), i(), n !== e.length && r();
	let l = "", u = 0;
	for (let n of t) l += e.slice(u, n.start) + n.text, u = n.end;
	return JSON.parse(l + e.slice(u));
}
// src/api/teams.ts
var c = class extends e {
	field;
	retryable;
	details;
	requestId;
	constructor(e, t, n = {}) {
		super(e, t, n.code || ""), this.name = "TeamApiError", this.field = n.field ?? null, this.retryable = !!n.retryable, this.details = Object.freeze({ ...n.details || {} }), this.requestId = n.requestId || "";
	}
};
function l() {
	let e = `${window.location.pathname}${window.location.search}${window.location.hash}`;
	throw window.location.assign(`/login?next=${encodeURIComponent(e)}`), new c("登录已失效，正在跳转登录页", 401, { code: "unauthorized" });
}
function u(e) {
	let t = new URLSearchParams();
	for (let [n, r] of Object.entries(e)) r != null && r !== "" && t.set(n, String(r));
	let n = t.toString();
	return n ? `?${n}` : "";
}
function d() {
	let e = globalThis.crypto?.randomUUID?.();
	return e && e.length >= 16 ? e : `team-${Date.now()}-${Math.random().toString(36).slice(2, 12)}-${Math.random().toString(36).slice(2, 10)}`;
}
var f = /* @__PURE__ */ new Set([
	400,
	403,
	404,
	409,
	410,
	422,
	429
]);
async function p(e, t = {}) {
	let n = new Headers(t.headers);
	n.set("Accept", "application/json");
	let r = await fetch(e, {
		credentials: "same-origin",
		...t,
		headers: n
	});
	(r.status === 401 || r.redirected && new URL(r.url, window.location.origin).pathname === "/login") && l();
	let i = await r.text(), a = null;
	if (i) try {
		a = s(i);
	} catch {
		throw new c(r.ok ? "服务器返回了无法识别的 Team 数据" : `请求失败（HTTP ${r.status}）`, r.status);
	}
	let o = a && typeof a == "object" ? a : null;
	if (!r.ok || !o || o.ok !== !0 || !("data" in o)) {
		let e = o && typeof o.error == "object" && o.error ? o.error : null, t = e?.message || (typeof o?.error == "string" ? o.error : "") || o?.message || `请求失败（HTTP ${r.status}）`, n = e?.code || o?.code || "";
		throw new c(t, r.status, {
			code: n,
			field: e?.field ?? null,
			retryable: e?.retryable ?? r.status >= 500,
			details: e?.details ?? null,
			requestId: String(o?.request_id || "")
		});
	}
	return o.data;
}
async function m(e, t, n, r, i) {
	let a = `turb_team_intent:${e}:${JSON.stringify({
		method: t,
		path: n,
		body: r ?? null
	})}`, o = r && "idempotency_key" in r && typeof r.idempotency_key == "string" ? r.idempotency_key.trim() : "";
	try {
		o ||= sessionStorage.getItem(a) || "";
	} catch {}
	if (!o || o.length < 16) {
		o = d();
		try {
			sessionStorage.setItem(a, o);
		} catch {}
	}
	let s = () => {
		try {
			sessionStorage.removeItem(a);
		} catch {}
	};
	try {
		let e = { "Idempotency-Key": o };
		r !== void 0 && (e["Content-Type"] = "application/json");
		let a = await p(n, {
			method: t,
			headers: e,
			...r === void 0 ? {} : { body: JSON.stringify(r) },
			signal: i
		});
		return s(), a;
	} catch (e) {
		throw e instanceof c && f.has(e.status) && s(), e;
	}
}
function h(e) {
	if (e?.aborted) throw new DOMException("名单准备已取消", "AbortError");
}
function g(e) {
	return h(e), new Promise((t, n) => {
		let r = setTimeout(() => {
			e?.removeEventListener("abort", i), t();
		}, 750), i = () => {
			clearTimeout(r), e?.removeEventListener("abort", i), n(new DOMException("名单准备已取消", "AbortError"));
		};
		e?.addEventListener("abort", i, { once: !0 });
	});
}
function _(e) {
	if (!Number.isSafeInteger(e.selection_revision) || Number(e.selection_revision) < 1 || !Number.isSafeInteger(e.target_count) || Number(e.target_count) < 0) throw new c("名单响应缺少有效的修订号或目标数量，请重新准备名单", 502, { code: "selection_response_invalid" });
	return {
		selection_id: r(e.id, "快照选择 ID"),
		selection_revision: e.selection_revision,
		matched_count: e.target_count
	};
}
function v() {
	return {
		list: (e, t) => p(`/api/teams${u(e)}`, { signal: t }),
		detail: (e, t) => p(`/api/teams/${r(e, "Team ID")}`, { signal: t }),
		createBindingProbe: (e, t) => m("binding_probe", "POST", "/api/teams/binding-probes", {
			manager_account_id: r(e.manager_account_id, "管理母号 ID"),
			...e.target_workspace_id ? { target_workspace_id: e.target_workspace_id } : {}
		}, t),
		getBindingProbe: (e, t) => p(`/api/teams/binding-probes/${r(e, "核验单 ID")}`, { signal: t }),
		createTeam: (e, t) => m(`bind:${e.workspace_id}`, "POST", "/api/teams", {
			...e,
			manager_account_id: r(e.manager_account_id, "管理母号 ID"),
			probe_id: r(e.probe_id, "核验单 ID")
		}, t),
		updateTeam: (e, t, n) => {
			let i = r(e, "Team ID");
			return m(`patch:${i}:${t.expected_revision}`, "PATCH", `/api/teams/${i}`, t, n);
		},
		syncTeam: (e, t) => {
			let n = r(e, "Team ID");
			return m(`sync:${n}`, "POST", `/api/teams/${n}/sync`, {}, t);
		},
		syncTeamsBulk: (e, t) => m("sync_bulk", "POST", "/api/teams/sync-bulk", { team_ids: [...new Set(e.map((e) => r(e, "Team ID")))] }, t),
		reverifyTeam: (e, t) => {
			let n = r(e, "Team ID");
			return m(`reverify:${n}`, "POST", `/api/teams/${n}/reverify`, {}, t);
		},
		listMembers: (e, t, n) => p(`/api/teams/${r(e, "Team ID")}/members${u(t)}`, { signal: n }),
		listInvitations: (e, t, n) => p(`/api/teams/${r(e, "Team ID")}/invitations${u(t)}`, { signal: n }),
		getInvitation: async (e, t, n) => (await p(`/api/teams/${r(e, "Team ID")}/invitations/${r(t, "邀请记录 ID")}`, { signal: n })).invitation,
		listCandidates: (e, t, n) => p(`/api/teams/${r(e, "Team ID")}/candidates${u(t)}`, { signal: n }),
		resolveCandidates: (e, t, n) => p(`/api/teams/${r(e, "Team ID")}/candidates/resolve`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ values: [...t] }),
			signal: n
		}),
		previewJoin: (e, t, n) => p(`/api/teams/${r(e, "Team ID")}/join-preview`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(t),
			signal: n
		}),
		submitJoin: (e, t, n) => {
			let i = r(e, "Team ID");
			return m(`join:${i}`, "POST", `/api/teams/${i}/join`, t, n);
		},
		getJoinRequest: (e, t, n = {}, i) => p(`/api/teams/${r(e, "Team ID")}/join-requests/${r(t, "入组请求 ID")}${u(n)}`, { signal: i }),
		continueInvitation: (e, t, n) => {
			let i = r(e, "Team ID"), a = r(t, "邀请记录 ID");
			return m(`inv_continue:${i}:${a}`, "POST", `/api/teams/${i}/invitations/${a}/continue`, {}, n);
		},
		retryInvitation: (e, t, n) => {
			let i = r(e, "Team ID"), a = r(t, "邀请记录 ID");
			return m(`inv_retry:${i}:${a}`, "POST", `/api/teams/${i}/invitations/${a}/retry`, {}, n);
		},
		continueInvitationsBulk: (e, t, n) => {
			let i = r(e, "Team ID"), a = [...new Set(t.map((e) => r(e, "邀请记录 ID")))];
			return m(`inv_continue_bulk:${i}`, "POST", `/api/teams/${i}/invitations/continue-bulk`, { invitation_ids: a }, n);
		},
		retryInvitationsBulk: (e, t, n) => {
			let i = r(e, "Team ID"), a = [...new Set(t.map((e) => r(e, "邀请记录 ID")))];
			return m(`inv_retry_bulk:${i}`, "POST", `/api/teams/${i}/invitations/retry-bulk`, { invitation_ids: a }, n);
		},
		freezeAccountSelection: async (e, t, n) => {
			let i = r(e, "Team ID"), a = await m(`freeze_team_join_selection:${i}`, "POST", "/api/bulk/selections", {
				operation: {
					key: "team_join",
					version: 1
				},
				source: {
					kind: "query",
					query: t
				},
				parameters: { team_id: i }
			}, n), o = r(a.id, "快照选择 ID");
			for (; a.state === "preparing";) await g(n), a = await p(`/api/bulk/selections/${o}`, { signal: n });
			if (h(n), a.state === "failed") throw new c("名单准备失败，请调整筛选条件后重试", 422, {
				code: a.error_code || "selection_preparation_failed",
				details: { selection_id: o }
			});
			if (a.state !== "ready") throw new c("名单返回了无法识别的准备状态，请重新准备名单", 502, { code: "selection_response_invalid" });
			return _(a);
		}
	};
}
var y = v();
export { s as a, i, v as n, r as o, y as r, c as t };
