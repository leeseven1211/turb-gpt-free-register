import { $ as e, A as t, G as n, I as r, O as i, P as a, S as o, V as s, W as c, Y as l, Z as u, _ as d, b as f, c as p, ct as m, dt as h, g, h as _, m as v, n as y, o as b, ot as x, p as S, s as C, u as w, ut as T, x as E, z as D } from "./_plugin-vue_export-helper-C1AvIlVn.js";
import { n as O, r as k, t as A } from "./client-BBEPwkQG.js";
import { n as j, r as M, t as N } from "./ListFilterSummary-NiVwXoAn.js";
import { t as P } from "./ListResult-3o6cJKgT.js";
import { t as F } from "./ListPagination-CFFXEHba.js";
import { n as I, t as L } from "./time-DOD6oyhP.js";
import { t as R } from "./useColumnWidths-DKwoq5eG.js";
import { t as z } from "./useNativeDialog-Ba95V1OP.js";
import { r as ee } from "./taskIds-BlchWwUp.js";
// src/features/email/presentation.ts
var B = {
	all: "全部邮箱池",
	outlook: "Outlook",
	generic_api: "通用 API",
	cloudflare_domain: "域名邮箱",
	icloud_hide: "iCloud 隐藏邮箱",
	email_butler: "Butler 本地邮箱"
}, V = {
	available: "可用",
	used: "已用",
	pending_sync: "导入处理中",
	tombstone: "本地已删除",
	replaced: "换绑后邮箱",
	failed: "失败",
	disabled: "已停用"
}, te = {
	available: "待领取",
	pending_sync: "导入处理中",
	tombstone: "本地已删除",
	used_unbound: "已领取未绑定",
	bound: "已绑定账号",
	replaced: "换绑后邮箱",
	failed: "失败",
	disabled: "已停用"
}, H = {
	available: "历史未领取",
	disabled: "已停用",
	reserved: "归属已保留",
	used: "已绑定账号",
	replaced: "换绑后地址",
	retired: "历史停用"
}, U = (e) => ({
	source: e.source,
	email: e.email
}), W = (e) => `${e.source}|${e.email}`, G = (e) => e instanceof Error ? e.message : String(e);
function ne(e, t = 10) {
	let n = Array.from(e);
	return n.length > t ? n.slice(0, t - 1).join("") + "…" : e;
}
function K(e, t, n = "neutral") {
	return {
		label: ne(e),
		detail: t,
		tone: n
	};
}
function q(e) {
	let t = e.resource_meta || {};
	if (e.source === "outlook") {
		let e = [
			["password", "密码"],
			["client_id", "Client ID"],
			["refresh_token", "Refresh Token"]
		];
		return {
			text: `${e.filter(([e]) => t[e]).length}/3 已配置`,
			detail: e.map(([e, n]) => `${n}：${t[e] ? "已配置" : "缺少"}`).join("；")
		};
	}
	return e.source === "generic_api" ? {
		text: t.code_url ? "取码地址已配置" : "缺少取码地址",
		detail: "地址仅在按需复制时读取"
	} : e.source === "icloud_hide" ? {
		text: "Apple 别名",
		detail: e.remote_active === !0 ? "远程已激活" : e.remote_active === !1 ? "远程未激活" : "远程状态未知"
	} : e.source === "email_butler" ? {
		text: "Butler 收码连接",
		detail: "使用导入时保存的收码设置"
	} : {
		text: "运行时配置",
		detail: "由来源服务管理"
	};
}
function re(e) {
	return [e.registered_account_id ? `账号 #${e.registered_account_id}` : "", e.root_task_id ? `任务 #${e.root_task_id}` : ""].filter(Boolean).join(" · ") || (["available", "disabled"].includes(e.state || "") ? "尚未领取" : "历史归属");
}
function ie(e) {
	return {
		service_fact_sync_pending: "导入处理中",
		registration_confirmed: "注册成功保护",
		registration_result_unverified: "注册结果未确认",
		local_email_conflict: "邮箱占用冲突",
		lease_expired: "租约已到期",
		lease_released: "租约已退还",
		lease_revoked: "租约已收回",
		lease_not_found: "原租约缺失",
		request_unknown: "回执未确认",
		request_timeout: "请求超时",
		transport_error: "连接异常"
	}[e.error_code || e.reason_code || e.disabled_reason_code || ""] || (e.service_sync_error ? "处理异常" : e.note ? "备注记录" : e.disabled_reason ? "停用原因" : "—");
}
// src/features/email/readScope.ts
function J(e, t) {
	let n = !1, r = !1, i = 0, a, o, s = () => n && !document.hidden && !r;
	function c() {
		i++, a?.abort(), a = void 0, clearTimeout(o), o = void 0, e.loading = !1;
	}
	async function l() {
		if (c(), !s()) return;
		let n = i;
		a = new AbortController();
		let r = a.signal, o = () => n === i && s();
		e.loading = !0;
		try {
			await t(r, o), o() && (e.error = "");
		} catch (t) {
			o() && !O(t) && (e.error = G(t));
		} finally {
			o() && (e.loading = !1, a = void 0);
		}
	}
	function u(e = 0) {
		if (c(), !s()) return;
		let t = i, n = () => {
			t === i && s() && l();
		};
		e ? o = setTimeout(n, e) : queueMicrotask(n);
	}
	return {
		refresh: l,
		schedule: u,
		invalidate: c,
		setActive(e) {
			e === n || r || (n = e, e ? l() : c());
		},
		dispose() {
			r = !0, c();
		},
		eligible: s
	};
}
// src/features/email/useEmailInventory.ts
function ae(e, t) {
	let n = u({
		items: [],
		parents: [],
		total: 0,
		page: 1,
		size: 20,
		filters: {
			source: "all",
			q: "",
			status: "",
			used_date: ""
		},
		facets: {},
		selected: /* @__PURE__ */ new Map(),
		loading: !1,
		error: "",
		summaryError: "",
		busy: !1,
		receipt: null
	}), r, i = J(n, async (t, r) => {
		for (let i = 0; i < 2; i++) {
			let a = await e.inventory({
				page: n.page,
				size: n.size,
				...n.filters
			}, t);
			if (!r()) return;
			n.total = Math.max(0, Number(a.total) || 0);
			let o = Math.max(1, Math.ceil(n.total / n.size));
			if (n.page > o) {
				if (n.page = o, !i) continue;
				throw Error("列表范围已变化，请刷新后重试");
			}
			n.items = a.items || [], n.facets = a.facets || {};
			break;
		}
		try {
			let i = await e.derivationSummary(t);
			r() && (n.parents = i.parents || [], n.summaryError = "");
		} catch (e) {
			r() && !(e instanceof Error && e.name === "AbortError") && (n.summaryError = `子地址历史读取失败：${G(e)}`);
		}
	});
	function a(e) {
		let t = Object.keys(e).filter((t) => e[t] !== n.filters[t]);
		t.length && (Object.assign(n.filters, e), n.page = 1, t.some((e) => e !== "q") && n.selected.clear(), i.schedule(t.every((e) => e === "q") ? 250 : 0));
	}
	function o(e, t) {
		t ? n.selected.set(W(e), U(e)) : n.selected.delete(W(e));
	}
	function s(e) {
		for (let t of n.items) o(t, e);
	}
	async function c() {
		try {
			await t.onInventoryChanged();
		} catch (e) {
			n.receipt = K(n.receipt?.label || "已接收", `${n.receipt?.detail || ""}\n显示刷新失败：${G(e)}`, "warning");
		}
		i.refresh();
	}
	async function l(e) {
		if (!n.busy) {
			n.busy = !0;
			try {
				await e();
			} catch (e) {
				if (e instanceof Error && e.name === "AbortError") return;
				n.receipt = K("操作失败", G(e), "danger"), t.notify(`操作失败：${G(e)}`);
			} finally {
				n.busy = !1;
			}
		}
	}
	function d(e, t) {
		let n = e.skipped || [], r = Array.isArray(e.deleted) ? e.deleted : [], i = e.lease_retained_count || r.filter((e) => e.sync?.lease_retained).length;
		return `${t === "delete" ? "本地已移除" : "已更新"} ${t === "delete" ? e.deleted_count || 0 : e.updated_count || 0} 个${i ? `，其中 ${i} 个已保留原租约` : ""}，跳过 ${n.length} 个` + n.map((e) => `\n${e.email}：${e.reason || "未返回具体原因"}`).join("");
	}
	async function f() {
		let r = Array.from(n.selected.values(), U), i = n.filters.source;
		r.length && !n.busy && await l(async () => {
			if (!await t.confirm(`确定从本地邮箱池移除选中的 ${r.length} 个邮箱吗？\n\n保留使用历史；缺少注册完成回执时保留原租约，确认账号未创建后才可退还。已确认注册成功的邮箱不能删除。`)) return;
			let a = await e.bulkDelete({
				items: r,
				source: i
			});
			for (let e of Array.isArray(a.deleted) ? a.deleted : []) n.selected.delete(W(e));
			n.receipt = K("删除结果", d(a, "delete"), "success"), await c();
		});
	}
	async function p(r) {
		let i = Array.from(n.selected.values(), U), a = n.filters.source;
		if (!i.length || n.busy) return;
		let o = {
			available: "未使用/可用",
			disabled: "停用",
			failed: "失败"
		}[r] || r;
		await l(async () => {
			if (!await t.confirm(`确定把选中的 ${i.length} 个邮箱标记为${o}吗？`)) return;
			let s = await e.bulkStatus({
				items: i,
				status: r,
				source: a,
				note: `批量标记${o}`
			});
			for (let e of i) n.selected.delete(W(e));
			n.receipt = K("状态更新", d(s, "status"), "success"), await c();
		});
	}
	async function m(r, i) {
		let a = U(r);
		await l(async () => {
			if (i === "delete") {
				if (!await t.confirm(`确定从本地邮箱池移除 ${a.email}？\n\n保留使用历史；缺少注册完成回执时保留原租约，确认账号未创建后才可退还。已确认注册成功的邮箱不能删除。`)) return;
				let r = await e.delete(a);
				r.deleted ? (n.selected.delete(W(a)), n.receipt = K("本地已移除", r.sync?.message || "本地已移除，保留使用历史", "success"), await c()) : n.receipt = K("未移除", r.reason || "邮箱未移除", "warning");
			} else {
				if (["replaced", "pending_sync"].includes(r.status || "")) return;
				let t = {
					available: "手动恢复可用",
					disabled: "手动停用",
					failed: "手动标记失败"
				};
				if (!t[i]) return;
				await e.status({
					...a,
					status: i,
					note: t[i]
				}), n.receipt = K("状态已更新", `${a.email}：${t[i]}`, "success"), await c();
			}
		});
	}
	async function h(n) {
		let i = U(n);
		await l(async () => {
			r = new AbortController();
			let n = r.signal, a = await e.secret(i, n);
			if (!n.aborted) {
				if (!a.value) throw Error("对应内容为空");
				await t.clipboard(a.value), t.notify("已复制");
			}
		});
	}
	async function g() {
		let i = n.items.map(U);
		i.length && await l(async () => {
			r = new AbortController();
			let a = r.signal, o = await e.secrets(i, a);
			if (a.aborted) return;
			let s = (o.values || []).map((e) => e.value).filter(Boolean).join("\n");
			if (!s) throw Error("当前页没有可复制内容");
			await t.clipboard(s), n.receipt = K("已复制当前页", (o.skipped || []).map((e) => `${e.email}：${e.reason}`).join("\n") || `已复制 ${i.length} 个邮箱素材`, "success"), t.notify("已复制当前页邮箱素材");
		});
	}
	return {
		state: n,
		refresh: i.refresh,
		setActive(e) {
			e || r?.abort(), i.setActive(e);
		},
		dispose() {
			r?.abort(), i.dispose();
		},
		updateFilters: a,
		toggle: o,
		togglePage: s,
		bulkDelete: f,
		bulkStatus: p,
		rowAction: m,
		copyRow: h,
		copyPage: g,
		resetFilters() {
			Object.assign(n.filters, {
				source: "all",
				q: "",
				status: "",
				used_date: ""
			}), n.selected.clear(), n.page = 1, i.schedule();
		},
		setPage(e) {
			Number.isSafeInteger(e) && (n.page = Math.max(1, Math.min(e, Math.max(1, Math.ceil(n.total / n.size)))), i.schedule());
		},
		setSize(e) {
			!Number.isSafeInteger(e) || e < 1 || e > 500 || (n.size = e, n.page = 1, i.schedule());
		},
		async refreshDerivationSummary() {
			i.eligible() && await i.refresh();
		}
	};
}
// src/features/email/useEmailHistory.ts
var Y = () => ({
	source: "all",
	parent_id: "",
	q: "",
	parent_q: "",
	state: "",
	related_q: "",
	created_from: "",
	created_to: ""
});
function oe(e, t) {
	let n = u({
		items: [],
		total: 0,
		page: 1,
		size: 50,
		filters: Y(),
		parentEmail: "",
		selected: /* @__PURE__ */ new Map(),
		loading: !1,
		error: "",
		receipt: null
	}), r = J(n, async (t, r) => {
		for (let i = 0; i < 2; i++) {
			let a = await e.history({
				page: n.page,
				size: n.size,
				...n.filters
			}, t);
			if (!r()) return;
			n.total = Math.max(0, Number(a.total) || 0);
			let o = Math.max(1, Math.ceil(n.total / n.size));
			if (n.page > o) {
				if (n.page = o, !i) continue;
				throw Error("列表范围已变化，请刷新后重试");
			}
			n.items = a.items || [];
			for (let e of n.items) n.selected.has(String(e.id)) && n.selected.set(String(e.id), { ...e });
			return;
		}
	});
	function i(e) {
		Object.entries(e).every(([e, t]) => t === n.filters[e]) || (e.source !== void 0 && e.source !== n.filters.source && (n.filters.parent_id = "", n.parentEmail = ""), Object.assign(n.filters, e), n.page = 1, n.selected.clear(), r.schedule(Object.keys(e).every((e) => [
			"q",
			"parent_q",
			"related_q"
		].includes(e)) ? 250 : 0));
	}
	function a(e, t) {
		t ? n.selected.set(String(e.id), { ...e }) : n.selected.delete(String(e.id));
	}
	return {
		state: n,
		refresh: r.refresh,
		setActive: r.setActive,
		dispose: r.dispose,
		updateFilters: i,
		toggle: a,
		togglePage(e) {
			for (let t of n.items) a(t, e);
		},
		resetFilters() {
			Object.assign(n.filters, Y()), n.parentEmail = "", n.selected.clear(), n.page = 1, r.schedule();
		},
		scopeParent(e) {
			Object.assign(n.filters, Y(), {
				source: e.source,
				parent_id: String(e.id)
			}), n.parentEmail = e.email, n.selected.clear(), n.page = 1, r.schedule();
		},
		clearParent() {
			n.filters.parent_id = "", n.parentEmail = "", n.selected.clear(), n.page = 1, r.schedule();
		},
		setPage(e) {
			Number.isSafeInteger(e) && (n.page = Math.max(1, Math.min(e, Math.max(1, Math.ceil(n.total / n.size)))), r.schedule());
		},
		setSize(e) {
			!Number.isSafeInteger(e) || e < 1 || e > 100 || (n.size = e, n.page = 1, r.schedule());
		},
		async copy() {
			let e = n.selected.size ? Array.from(n.selected.values()) : n.items;
			if (!e.length) t.notify("当前没有可复制的子邮箱");
			else try {
				await t.clipboard(e.map((e) => e.email).filter(Boolean).join("\n")), n.receipt = K("已复制", `已复制 ${e.length} 条历史子邮箱`, "success");
			} catch (e) {
				n.receipt = K("复制失败", G(e), "danger");
			}
		}
	};
}
// src/features/email/useLocalImport.ts
var X = {
	outlook: {
		label: "Outlook 邮箱池",
		placeholder: "email----password----clientId----refreshToken",
		hint: "每行一条，支持 ---- 和 ==== 分隔符；多余字段不会写入邮箱池。"
	},
	generic_api: {
		label: "通用 API 取码邮箱",
		placeholder: "email----取码地址----2026-12-01T12:00:00+08:00",
		hint: "第三字段可填写带时区的 ISO8601 有效期，每行有效期优先于批次值；旧两段格式仍支持。"
	},
	email_butler: {
		label: "Butler 已租用邮箱",
		placeholder: "owned@icloud.com\nowned@outlook.com",
		hint: "每行一个已在 Butler 长期租用的完整邮箱地址；手动导入仅恢复本人原租约。需要补充新邮箱时使用“从 Butler 导入”。"
	}
};
function se(e, t) {
	let n = u({
		open: !1,
		source: "outlook",
		text: "",
		expiresAt: "",
		preview: null,
		loading: !1,
		busy: !1,
		error: "",
		receipt: null
	}), r = !1, i = !1, a = 0, o, s = "";
	function c() {
		return {
			source: n.source,
			text: n.text,
			...n.source === "generic_api" && n.expiresAt.trim() ? { expires_at: n.expiresAt.trim() } : {}
		};
	}
	function l() {
		a++, o?.abort(), o = void 0, n.loading = !1, n.preview = null, s = "";
	}
	function d(e) {
		Object.assign(n, e), l(), n.error = "";
	}
	async function f() {
		let t = c(), u = JSON.stringify(t);
		if (l(), !r || document.hidden || !n.open || i) return null;
		if (!t.text.trim()) return n.error = "请粘贴邮箱资源", null;
		let d = a;
		o = new AbortController(), n.loading = !0, n.error = "";
		try {
			let i = await e.localPreview(t, o.signal);
			return d !== a || !r || document.hidden || !n.open || u !== JSON.stringify(c()) ? null : (n.preview = i, s = u, i);
		} catch (e) {
			return d === a && !O(e) && (n.error = G(e)), null;
		} finally {
			d === a && (n.loading = !1);
		}
	}
	async function p() {
		if (n.busy || !n.text.trim()) return;
		let r = c(), i = JSON.stringify(r);
		n.busy = !0, n.error = "";
		try {
			let a = n.preview && s === i ? n.preview : await f();
			if (!a || i !== JSON.stringify(c())) return;
			if (!Number(a.new || 0)) {
				n.error = "没有可新增的邮箱资源，请修改内容后重新预览。";
				return;
			}
			let o = await e.localImport(r), u = `邮箱导入：解析 ${o.parsed || 0} 行，已接收 ${o.accepted_count ?? o.inserted ?? 0}，跳过 ${o.skipped || 0}；导入处理中 ${o.pending_sync_count || 0}，无效 ${o.invalid || 0} 行，忽略多余字段 ${o.extra_fields || 0} 个` + (o.invalid_rows || []).map((e) => `\n第 ${e.line} 行：${e.reason}`).join("");
			n.receipt = K("导入已接收", u, "success"), JSON.stringify(c()) === i && (n.text = "", l());
			try {
				await t.onInventoryChanged();
			} catch (e) {
				n.receipt = K("导入已接收", `${u}\n显示刷新失败：${G(e)}`, "warning");
			}
			t.notify("邮箱导入已接收");
		} catch (e) {
			n.error = G(e), n.receipt = e instanceof A && e.status >= 400 && e.status < 500 ? K("导入被拒绝", `导入被拒绝：${G(e)}。已保留原素材。`, "danger") : K("导入结果未确认", `导入响应未确认：${G(e)}。已保留原素材，请先核对库存；不会自动重复提交。`, "danger");
		} finally {
			n.busy = !1;
		}
	}
	return {
		state: n,
		update: d,
		preview: f,
		submit: p,
		open(e = "outlook") {
			n.open = !0, X[e] && n.source !== e && d({ source: e });
		},
		close() {
			n.open = !1, l();
		},
		setActive(e) {
			r = e, e || l();
		},
		dispose() {
			i = !0, l();
		}
	};
}
// src/features/email/butlerLabels.ts
var Z = [
	{
		value: "icloud_hme",
		label: "iCloud 隐藏邮箱"
	},
	{
		value: "outlook_graph",
		label: "Outlook / Hotmail"
	},
	{
		value: "cloudflare",
		label: "Cloudflare"
	},
	{
		value: "mailcom",
		label: "mail.com"
	},
	{
		value: "auto",
		label: "全部来源"
	}
], ce = {
	source_unavailable: "来源不可用",
	active_same_service: "OpenAI 已租用",
	other_service_exclusive: "其他服务占用",
	history_blocked: "历史占用限制",
	cooldown: "冷却中"
}, le = {
	global_capacity: "等待全局业务空位",
	type_capacity: "等待邮箱导入空位",
	batch_capacity: "等待当前导入批次空位",
	fairness_turn: "等待其他类型或批次轮转",
	scheduler_store_unavailable: "等待数据库恢复后继续准入",
	concurrency_policy_migration_required: "等待保存部署并发策略",
	concurrency_policy_invalid: "等待修正并发策略",
	concurrency_policy_missing: "等待补齐邮箱导入并发策略"
}, ue = {
	local_email_conflict: "本地已有或被其他任务占用",
	handoff_rejected: "Butler 拒绝交接",
	handoff_unconfirmed: "Butler 交接请求未收到回执，可继续原批次恢复",
	import_interrupted: "服务重启导致中断，可继续原批次",
	original_route_unavailable: "原 Butler 连接或收件配置不可用",
	fixed_route_unavailable: "原固定收件配置不可用",
	butler_remote_unavailable: "无法连接 Butler，稍后可继续原批次",
	handoff_contract_unsupported: "Butler 消费身份或交接能力不匹配",
	import_storage_unavailable: "本地数据库暂时不可用，可继续原批次",
	import_internal_error: "本地导入处理异常，可继续原批次",
	handoff_timeout: "Butler 响应超时，可继续原批次核实",
	permission_denied: "当前 Key 缺少操作权限，请检查 Butler 授权",
	service_not_allowed: "当前 Key 无权使用 OpenAI 服务",
	no_inventory: "Butler 当前没有符合条件的可租邮箱",
	lease_expired: "原租约已到期，请核对原租约",
	lease_released: "原租约已退租，不能重新随机分配替代地址",
	lease_revoked: "原租约已被收回，请核对 Butler 租约记录",
	lease_not_found: "未找到本人原租约，请检查迁移映射",
	idempotency_conflict: "原请求编号与内容冲突，已保留原意图",
	idempotency_result_expired: "原请求回执已过期，须核对原租约后恢复",
	request_unknown: "Butler 请求未收到回执，继续原批次恢复同一请求",
	request_timeout: "Butler 请求超时，继续原批次恢复同一请求",
	transport_error: "Butler 连接异常，继续原批次恢复同一请求",
	butler_availability_invalid: "Butler 可用数量响应无效",
	butler_filter_unsupported: "当前 API 仅支持邮箱来源和数量",
	handoff_rate_limited: "Butler 请求受限，稍后可继续原批次",
	handoff_remote_unavailable: "Butler 服务暂时不可用，可继续原批次",
	handoff_identity_mismatch: "Butler 回执与原邮箱身份不一致，可继续原批次核实",
	handoff_response_invalid: "Butler 回执缺失、重复或格式无效，可继续原批次核实",
	inventory_batch_invalid: "Butler 批量请求格式无效",
	inventory_import_item_invalid: "Butler 原邮箱交接参数无效",
	inventory_policy_forbidden: "Butler 消费策略不允许交接此邮箱",
	inventory_client_required: "Butler 未返回有效的消费客户端身份",
	icloud_identity_not_found: "Butler 未找到原完整邮箱身份",
	inventory_candidate_unavailable: "Butler 原邮箱库存当前不可交接",
	acquisition_owner_mismatch: "Butler 原交接归属不一致",
	acquisition_identity_mismatch: "Butler 原交接对应的邮箱身份不一致",
	icloud_identity_unavailable: "Butler 原邮箱身份当前不可用",
	inventory_storage_unavailable: "Butler 数据库暂时不可用，可继续原批次"
}, de = "turb.butler-import.v1", fe = (e) => [
	"completed",
	"succeeded",
	"done"
].includes(e || ""), pe = (e) => [
	"pending",
	"queued",
	"running",
	"processing"
].includes(e || ""), me = (e) => JSON.stringify([
	e.updated_at,
	e.status,
	e.imported,
	e.pending,
	e.submitting,
	e.unknown,
	e.failed,
	e.error_code,
	e.blocked_by
]);
function he(e, t, n) {
	let r = u({
		open: !1,
		filters: {
			provider: "icloud_hme",
			count: 10
		},
		providers: [...Z],
		preview: null,
		request: null,
		batch: null,
		busy: !1,
		polling: !1,
		previewing: !1,
		error: "",
		storageError: !1,
		resumePending: null
	}), i = !1, a = !1, o = 0, s = 0, c, l, d, f, p, m = null, h = -1, g = 0, _ = null, v = n.now || Date.now, y = () => i && !document.hidden && !a;
	try {
		let e = JSON.parse(n.storage.getItem("turb.butler-import.v1") || "null");
		e && typeof e.request_id == "string" && typeof e.preview_token == "string" && (r.request = {
			request_id: e.request_id,
			preview_token: e.preview_token,
			filters: e.filters
		}, e.filters && typeof e.filters.provider == "string" && Number.isSafeInteger(e.filters.count) && (r.filters = {
			provider: e.filters.provider,
			count: e.filters.count
		}), typeof e.batch_id == "string" && e.batch_id && (r.batch = {
			batch_id: e.batch_id,
			status: typeof e.batch_status == "string" ? e.batch_status : "running"
		}, e.batch_status !== "cancelled" && typeof e.resume_revision == "string" && (r.resumePending = e.resume_revision)));
	} catch {
		r.storageError = !0, r.error = "无法读取浏览器中的导入记录；请先恢复浏览器存储后再导入。";
	}
	function b() {
		r.request && n.storage.setItem(de, JSON.stringify({
			...r.request,
			...r.batch ? {
				batch_id: r.batch.batch_id,
				batch_status: r.batch.status
			} : {},
			...r.resumePending ? { resume_revision: r.resumePending } : {}
		}));
	}
	function x() {
		o++, c?.abort(), d?.abort(), clearTimeout(f), r.preview = null, r.previewing = !1;
	}
	function C() {
		x(), s++, l?.abort(), l = void 0, m = null, r.polling = !1, clearTimeout(p);
	}
	let w = S(() => pe(r.batch?.status)), T = S(() => r.batch?.status === "cancelled" || !!r.batch && !r.batch.can_retry && !Number(r.batch.unknown || r.batch.internal_unknown_count || 0) && [
		"completed",
		"succeeded",
		"done",
		"partial",
		"partial_success",
		"failed",
		"rejected"
	].includes(r.batch.status)), E = S(() => !!r.request && !r.busy && !r.polling && r.batch?.status !== "cancelled" && !w.value && !r.resumePending && (!r.batch || r.batch.can_retry === !0)), D = S(() => !!r.batch && r.batch.can_cancel !== !1 && r.batch.status !== "cancelled" && !fe(r.batch.status)), k = S(() => {
		if (r.resumePending) return "正在恢复原批次";
		let e = r.batch;
		return e ? {
			pending: "等待导入",
			queued: "等待导入",
			running: "正在导入",
			processing: "正在导入",
			partial: e.can_retry ? "部分完成，可继续原批次" : "本批次已结束（部分失败）",
			partial_success: e.can_retry ? "部分成功，可继续原批次" : "本批次已结束（部分成功）",
			completed: "导入完成",
			succeeded: "导入完成",
			done: "导入完成",
			failed: "导入失败",
			rejected: "导入未开始",
			unknown: "导入失败",
			cancelled: "本批次已终止"
		}[e.status] || "状态记录缺失" : r.busy ? "正在提交导入" : "导入请求响应缺失";
	}), j = S(() => {
		let e = r.batch;
		if (!e) return "可以关闭窗口，已保存原请求；重新打开后可恢复结果。";
		let t = [e.status === "cancelled" ? "已停止后续导入。已导入邮箱、原租约和失败记录均保留；已发出的请求仍会保存结果。" : w.value || r.resumePending ? "可以关闭窗口，导入会在后台继续；刷新页面也能恢复。" : e.can_retry ? "可继续原批次处理剩余邮箱，已导入的邮箱会保留。" : "已导入的邮箱已加入本地库存，可以关闭窗口或新建导入。"];
		for (let n of e.blocked_by || []) t.push(le[n] || `等待准入（${n}）`);
		e.error_code && t.push(`${ue[e.error_code] || "批次异常"}（${e.error_code}）`);
		for (let [n, r] of Object.entries(e.error_counts || {})) t.push(`${ue[n] || "处理异常"}（${n}）：${r} 个`);
		return e.internal_unknown_count && t.push(`原请求仍有 ${e.internal_unknown_count} 个待核实回执，保留原批次恢复；内部状态：${e.internal_status || "未记录"}。`), t.join("\n");
	}), M = S(() => {
		let e = r.preview;
		if (!e) return "";
		let t = Object.entries(ce).filter(([t]) => Number.isSafeInteger(e.availability_buckets?.[t]) && Number(e.availability_buckets?.[t]) > 0).map(([t, n]) => `${n} ${e.availability_buckets[t]} 个`);
		return `当前可用 ${Number(e.available || 0)} 个 · 本次可导入 ${Number(e.selected || 0)} 个。${t.length ? `${Number.isSafeInteger(e.resource_total) ? `当前查询范围 ${e.resource_total} 个` : "当前查询范围"}：${t.join(" · ")}。` : ""}Butler“未租用”不等于可用于 OpenAI。查询不占用库存；确认后由 Butler 分配地址，导入时再核对本地占用。`;
	});
	function N() {
		clearTimeout(p), y() && r.batch && r.batch.status !== "cancelled" && (w.value || r.resumePending) && (p = setTimeout(() => void V(), 2e3));
	}
	function P() {
		let e = Number(r.batch?.imported || 0);
		!e || e === h || _ || w.value && h >= 0 && v() - g < 15e3 || (_ = Promise.resolve().then(() => t.onInventoryChanged()).then(() => {
			h = e;
		}, (e) => {
			r.error = `邮箱已导入，但显示未完全刷新：${G(e)}`;
		}).finally(() => {
			_ = null, g = v(), !w.value && Number(r.batch?.imported || 0) !== e && P();
		}));
	}
	function F(e) {
		if (!e.batch?.batch_id) throw Error("服务端未返回导入批次");
		if (r.batch && r.batch.batch_id !== e.batch.batch_id) throw Error("服务端返回了不同批次，保留原批次恢复原请求");
		let t = r.batch?.status === "cancelled";
		try {
			let r = JSON.parse(n.storage.getItem("turb.butler-import.v1") || "null");
			t ||= r?.batch_id === e.batch.batch_id && r.batch_status === "cancelled";
		} catch {}
		let i = t ? {
			...e.batch,
			status: "cancelled",
			can_retry: !1,
			can_cancel: !1
		} : e.batch;
		r.resumePending && (pe(i.status) || me(i) !== r.resumePending) && (r.resumePending = null), r.batch = i, i.status === "cancelled" && (r.resumePending = null, s++, l?.abort(), r.polling = !1, clearTimeout(p));
		try {
			b();
		} catch {
			r.error = "原请求已保存，批次编号暂未写入浏览器；重开后将恢复原请求。";
		}
		P();
	}
	async function I() {
		if (!y() || !r.open || r.request || r.busy) return;
		let t = { ...r.filters };
		if (x(), r.error = "", !Z.some((e) => e.value === t.provider)) {
			r.error = "请选择支持的邮箱来源";
			return;
		}
		if (!Number.isSafeInteger(t.count) || t.count < 1) {
			r.error = "数量须为大于0的整数";
			return;
		}
		let n = o;
		c = new AbortController(), r.previewing = !0;
		try {
			let i = await e.butlerPreview(t, c.signal);
			if (n !== o || !y() || !r.open || JSON.stringify(t) !== JSON.stringify(r.filters)) return;
			if (!i.preview_token) throw Error("可用数量查询未返回有效结果，请刷新数量");
			r.preview = {
				...i,
				filters: t
			}, i.selected || (r.error = "当前没有可用于 OpenAI 的邮箱，请在 Butler 按目标服务核对来源状态、历史占用和冷却限制后刷新数量。");
		} catch (e) {
			n === o && !O(e) && (r.error = `查询可用数量失败：${G(e)}`);
		} finally {
			n === o && (r.previewing = !1);
		}
	}
	function L(e) {
		r.request || (Object.assign(r.filters, e), x(), r.error = "", y() && r.open && (f = setTimeout(() => void I(), 400)));
	}
	async function R() {
		if (r.open = !0, r.storageError) return;
		if (r.batch) {
			await V();
			return;
		}
		if (r.request) {
			r.error = "上次导入未收到响应，请重试原请求恢复结果。";
			return;
		}
		if (!y()) return;
		d = new AbortController();
		let t = o;
		try {
			let n = await e.options(d.signal);
			if (t !== o || !y() || !r.open) return;
			n.providers?.length && (r.providers = n.providers);
		} catch (e) {
			t === o && !O(e) && (r.error = `读取导入选项失败：${G(e)}`);
		}
		t === o && await I();
	}
	function z() {
		r.open = !1, x();
	}
	async function ee() {
		if (r.busy || r.polling || !r.request || r.batch?.status === "cancelled" || r.batch && !r.batch.can_retry) return;
		let t = {
			request_id: r.request.request_id,
			preview_token: r.request.preview_token
		}, i = r.batch;
		r.busy = !0, r.error = "";
		try {
			let n = await (i ? e.retryBatch(i.batch_id, t) : e.createBatch(t));
			i && (r.resumePending = me(i)), F(n);
		} catch (e) {
			if (!r.batch && e instanceof A && [
				"import_preview_not_found",
				"import_preview_expired",
				"import_preview_empty",
				"import_snapshot_conflict"
			].includes(e.code)) try {
				n.storage.removeItem(de), r.request = null, x(), r.error = `导入尚未开始：${G(e)}。请重新预览。`;
			} catch {
				r.error = "导入尚未开始，但原记录暂未清除；请恢复浏览器存储后重试原请求。";
			}
			else r.error = `导入请求失败：${G(e)}。请${r.batch ? "继续原批次" : "重试原请求"}恢复，已保留原编号。`;
		} finally {
			r.busy = !1, N();
		}
	}
	async function B() {
		if (!(r.busy || r.request || !r.preview || r.preview.selected < 1)) {
			if (JSON.stringify(r.filters) !== JSON.stringify(r.preview.filters)) x(), r.error = "筛选已变化，请刷新可用数量。";
			else {
				try {
					if (r.storageError) throw Error("storage");
					r.request = {
						request_id: (n.uuid || (() => crypto.randomUUID()))(),
						preview_token: r.preview.preview_token,
						filters: { ...r.filters }
					}, b();
				} catch {
					r.request = null, r.error = "无法保存导入请求，请启用浏览器本地存储后重试。";
					return;
				}
				await ee();
			}
		}
	}
	async function V() {
		if (m) return m;
		if (!y() || !r.batch || r.busy) return;
		clearTimeout(p);
		let t = ++s, n = r.batch.batch_id;
		l = new AbortController(), r.polling = !0;
		let i = (async () => {
			try {
				let i = await e.batch(n, l.signal);
				if (t !== s || !y() || r.batch?.batch_id !== n) return;
				r.error = "", F(i);
			} catch (e) {
				t === s && !O(e) && (r.error = `暂时无法读取原批次：${G(e)}。请重开此窗口恢复查看。`);
			} finally {
				t === s && (r.polling = !1, m = null, N());
			}
		})();
		m = i, await i;
	}
	async function te() {
		if (r.busy || !D.value || !r.batch) return;
		let t = r.batch.batch_id;
		r.busy = !0, r.error = "";
		try {
			let n = await e.cancelBatch(t);
			if (F(n), n.batch.status !== "cancelled" && !fe(n.batch.status)) throw Error("服务端未返回终止回执");
			s++, l?.abort(), m = null, r.polling = !1;
		} catch (e) {
			r.error = `终止请求失败：${G(e)}。已保留原批次，请重试终止或查看原批次状态。`;
		} finally {
			r.busy = !1, N();
		}
	}
	async function H() {
		if (!(!T.value || r.busy || r.polling)) {
			try {
				n.storage.removeItem(de);
			} catch {
				r.error = "无法清除上次导入记录，请恢复浏览器存储后重试。";
				return;
			}
			C(), r.request = null, r.batch = null, r.resumePending = null, r.error = "", h = -1, g = 0, await I();
		}
	}
	function U(e) {
		if (e.key === "turb.butler-import.v1" && e.newValue && r.batch) try {
			let t = JSON.parse(e.newValue);
			if (t.batch_id !== r.batch.batch_id || t.batch_status !== "cancelled") return;
			s++, l?.abort(), m = null, clearTimeout(p), r.polling = !1, r.resumePending = null, r.batch = {
				...r.batch,
				status: "cancelled",
				can_retry: !1,
				can_cancel: !1
			};
		} catch {}
	}
	return window.addEventListener("storage", U), {
		state: r,
		isRunning: w,
		canReset: T,
		canRetry: E,
		canCancel: D,
		batchTitle: k,
		batchDetails: j,
		availability: M,
		open: R,
		close: z,
		preview: I,
		changeFilters: L,
		apply: B,
		retry: ee,
		poll: V,
		cancel: te,
		reset: H,
		setActive(e) {
			a || e === i || (i = e, e ? r.batch ? V() : r.open && !r.request && R() : C());
		},
		dispose() {
			a = !0, C(), window.removeEventListener("storage", U);
		}
	};
}
// src/features/email/EmailOverview.vue?vue&type=script&setup=true&lang.ts
var ge = ["aria-busy"], _e = { class: "em-heading" }, ve = ["disabled"], ye = {
	key: 0,
	class: "em-error",
	role: "alert"
}, be = { class: "em-source-visibility" }, xe = ["aria-expanded"], Se = { class: "em-source-cards" }, Ce = { class: "em-source-title" }, we = { class: "em-source-number" }, Te = { key: 0 }, Ee = {
	key: 1,
	role: "status"
}, De = { class: "em-import-prompt" }, Oe = { class: "em-actions" }, ke = /* @__PURE__ */ o({
	__name: "EmailOverview",
	props: {
		sources: {},
		expanded: { type: Boolean },
		loading: { type: Boolean },
		error: {},
		butlerLabel: {}
	},
	emits: [
		"refresh",
		"expand",
		"source",
		"localImport",
		"butlerImport"
	],
	setup(e, { emit: t }) {
		let n = e, i = t, o = (e) => e === !0 || e === "true", s = (e) => e.kind === "local_pool" || (e.default_visible === void 0 ? o(e.enabled) || o(e.dependency) : o(e.default_visible)), l = S(() => n.sources.filter((e) => !s(e)).length), u = S(() => n.expanded ? n.sources : n.sources.filter(s)), p = (e) => e.kind !== "on_demand" && !!B[e.source] && e.source !== "all";
		function y(e) {
			return e.kind === "local_pool" ? "本地库存" : o(e.enabled) ? "已启用" : o(e.dependency) ? "收码依赖" : o(e.history_available) || Number(e.total) > 0 ? "历史/已停用" : "未启用";
		}
		return (t, n) => (a(), d("section", {
			class: "em-overview",
			"aria-label": "邮箱资源平台",
			"aria-busy": e.loading
		}, [
			v("div", _e, [n[5] ||= v("div", null, [v("h2", null, "本地邮箱库存"), v("p", null, "仅从本地库存领取邮箱，用完后请从 Butler 或其他来源手动导入。")], -1), v("button", {
				class: "em-button",
				disabled: e.loading,
				onClick: n[0] ||= (e) => i("refresh")
			}, h(e.loading ? "刷新中…" : "刷新资源"), 9, ve)]),
			e.error ? (a(), d("p", ye, [f(h(e.error) + " ", 1), v("button", {
				class: "em-button",
				onClick: n[1] ||= (e) => i("refresh")
			}, "重试")])) : g("", !0),
			v("div", be, [v("span", null, h(l.value ? "默认显示已启用服务和当前收码依赖" : "当前没有未启用的邮箱服务"), 1), l.value ? (a(), d("button", {
				key: 0,
				class: "em-button",
				"aria-expanded": e.expanded,
				onClick: n[2] ||= (e) => i("expand")
			}, h(e.expanded ? "隐藏未启用" : `显示未启用（${l.value}）`), 9, xe)) : g("", !0)]),
			v("div", Se, [(a(!0), d(w, null, r(u.value, (e) => (a(), _(D(p(e) ? "button" : "article"), {
				key: e.source,
				type: p(e) ? "button" : void 0,
				class: m(["em-source-card", { "is-clickable": p(e) }]),
				onClick: (t) => p(e) && i("source", e.source)
			}, {
				default: c(() => [
					v("div", Ce, [v("strong", null, h(e.label || x(B)[e.source] || e.source), 1), v("span", null, h(y(e)), 1)]),
					v("strong", we, h(e.kind === "on_demand" ? "按需" : e.available ?? 0), 1),
					v("p", null, h(e.kind === "on_demand" ? "运行时领取 / 创建" : `总数 ${e.total || 0} · 已用 ${e.used || 0} · 失败 ${e.failed || 0} · 停用 ${e.disabled || 0}`), 1),
					e.dependency_reason ? (a(), d("small", Te, h(e.dependency_reason), 1)) : g("", !0)
				]),
				_: 2
			}, 1032, [
				"type",
				"class",
				"onClick"
			]))), 128))]),
			u.value.length ? g("", !0) : (a(), d("p", Ee, h(e.loading ? "正在加载邮箱资源…" : "暂无已启用邮箱服务，可显示未启用的服务。"), 1)),
			v("section", De, [n[6] ||= v("div", null, [
				v("span", null, "Email Butler"),
				v("h3", null, "手动补充本地库存"),
				v("p", null, "从 Butler 选择 iCloud HME 母邮箱或子邮箱导入，也可粘贴已有完整地址。注册任务仅领取本地库存。")
			], -1), v("div", Oe, [v("button", {
				class: "em-button em-primary",
				"data-butler-opener": "",
				onClick: n[3] ||= (e) => i("butlerImport")
			}, h(e.butlerLabel), 1), v("button", {
				class: "em-button",
				onClick: n[4] ||= (e) => i("localImport")
			}, "粘贴导入")])])
		], 8, ge));
	}
}), Ae = { class: "em-filter-field" }, je = ["aria-label", "value"], Me = ["value"], Ne = ["value"], Pe = [
	"aria-label",
	"type",
	"value"
], Fe = {
	key: 0,
	class: "em-filter-field"
}, Ie = ["aria-label", "value"], Q = /* @__PURE__ */ o({
	__name: "EmailColumnFilter",
	props: {
		label: {},
		value: {},
		active: { type: Boolean },
		type: {},
		endValue: {},
		emptyValue: {},
		options: {}
	},
	emits: ["change", "end"],
	setup(t, { emit: n }) {
		let i = t, o = n, u = e(!1);
		s(() => i.active, (e) => {
			e || (u.value = !1);
		});
		let p = S(() => i.value !== (i.emptyValue || "") || !!i.endValue), m = !1;
		function y(e) {
			m = !1, o("change", e.target.value);
		}
		function b(e) {
			m || o("change", e.target.value);
		}
		return (e, n) => (a(), _(M, {
			label: t.label,
			active: p.value,
			summary: [t.value, t.endValue].filter(Boolean).join(" 至 "),
			open: u.value,
			"onUpdate:open": n[4] ||= (e) => u.value = e
		}, {
			default: c(() => [
				v("label", Ae, [f(h(t.label) + " ", 1), t.options ? (a(), d("select", {
					key: 0,
					"aria-label": t.label,
					value: t.value,
					onChange: n[0] ||= (e) => o("change", e.target.value)
				}, [v("option", { value: t.emptyValue || "" }, "全部", 8, Me), (a(!0), d(w, null, r(t.options, (e) => (a(), d("option", {
					key: e.value,
					value: e.value
				}, h(e.label) + h(e.count === void 0 ? "" : ` (${e.count})`), 9, Ne))), 128))], 40, je)) : (a(), d("input", {
					key: 1,
					"aria-label": t.label,
					type: t.type === "date" || t.type === "range" ? "date" : "search",
					multiple: !1,
					value: t.value,
					onCompositionstart: n[1] ||= (e) => l(m) ? m.value = !0 : m = !0,
					onCompositionend: y,
					onInput: b
				}, null, 40, Pe))]),
				t.type === "range" ? (a(), d("label", Fe, [n[5] ||= f("结束日期", -1), v("input", {
					type: "date",
					"aria-label": `${t.label}结束`,
					value: t.endValue,
					onInput: n[2] ||= (e) => o("end", e.target.value)
				}, null, 40, Ie)])) : g("", !0),
				v("button", {
					type: "button",
					class: "em-button",
					onClick: n[3] ||= (e) => {
						o("change", t.emptyValue || ""), t.type === "range" && o("end", "");
					}
				}, "清除条件")
			]),
			_: 1
		}, 8, [
			"label",
			"active",
			"summary",
			"open"
		]));
	}
}), Le = {
	key: 0,
	class: "em-receipt",
	role: "status"
}, Re = /* @__PURE__ */ o({
	__name: "EmailReceipt",
	props: { receipt: {} },
	setup(e) {
		return (t, n) => e.receipt ? (a(), d("div", Le, [E(P, {
			label: e.receipt.label,
			title: e.receipt.detail,
			tone: e.receipt.tone
		}, {
			details: c(() => [f(h(e.receipt.detail), 1)]),
			_: 1
		}, 8, [
			"label",
			"title",
			"tone"
		])])) : g("", !0);
	}
}), ze = ["aria-label"], $ = /* @__PURE__ */ o({
	__name: "EmailResizeGrip",
	props: {
		index: {},
		columns: {},
		label: {}
	},
	setup(e) {
		return (t, n) => (a(), d("button", {
			class: "em-resize",
			"aria-label": `调整${e.label}第 ${e.index + 1} 列宽度`,
			onPointerdown: n[0] ||= (t) => e.columns.resize(e.index, t),
			onKeydown: [n[1] ||= C(p((t) => e.columns.resizeWithKeyboard(e.index, -10), ["prevent"]), ["left"]), n[2] ||= C(p((t) => e.columns.resizeWithKeyboard(e.index, 10), ["prevent"]), ["right"])]
		}, null, 40, ze));
	}
}), Be = ["aria-busy"], Ve = { class: "em-toolbar" }, He = { class: "em-actions" }, Ue = ["disabled"], We = ["disabled"], Ge = ["disabled"], Ke = ["disabled"], qe = ["disabled"], Je = { class: "em-actions" }, Ye = ["disabled"], Xe = {
	class: "em-count-row",
	"data-email-count-row": ""
}, Ze = {
	key: 0,
	class: "em-error",
	role: "alert"
}, Qe = {
	key: 1,
	class: "em-error",
	role: "alert"
}, $e = { class: "em-table-wrap" }, et = [
	"checked",
	"indeterminate",
	"disabled"
], tt = [
	"aria-label",
	"checked",
	"onChange"
], nt = { class: "em-align-start" }, rt = [
	"aria-label",
	"title",
	"onClick"
], it = { class: "em-align-start" }, at = { class: "em-row-actions" }, ot = ["disabled", "onClick"], st = ["disabled", "onClick"], ct = {
	key: 0,
	class: "em-more"
}, lt = ["aria-label"], ut = ["disabled", "onClick"], dt = { key: 0 }, ft = {
	colspan: "9",
	class: "em-empty",
	role: "status"
}, pt = /* @__PURE__ */ o({
	__name: "EmailInventory",
	props: {
		owner: {},
		active: { type: Boolean },
		butlerLabel: {}
	},
	emits: [
		"localImport",
		"butlerImport",
		"parent"
	],
	setup(e, { emit: t }) {
		let o = e, s = t, l = o.owner.state, u = R({
			defaults: [
				40,
				228,
				112,
				104,
				120,
				160,
				140,
				164,
				228
			],
			storageKey: "gpt_console_table_widths_outlook",
			totalStorageKey: "gpt_console_table_total_outlook",
			min: 28,
			max: 2e4
		}), p = S(() => l.items.filter((e) => l.selected.has(W(e))).length), y = S(() => Object.entries(l.filters).filter(([e, t]) => t && (e !== "source" || t !== "all")).map(([e, t]) => ({
			key: e,
			label: `${{
				q: "邮箱",
				source: "类型",
				status: "状态",
				used_date: "最近使用日期"
			}[e]}：${e === "source" ? B[t] || t : e === "status" && V[t] || t}`,
			removeLabel: `移除${e}筛选`
		}))), C = S(() => Object.entries(B).filter(([e]) => e !== "all").map(([e, t]) => ({
			value: e,
			label: t,
			count: l.facets.source?.find((t) => t.value === e)?.count
		}))), D = S(() => [.../* @__PURE__ */ new Set([
			...Object.keys(V),
			...(l.facets.status || []).map((e) => e.value),
			l.filters.status
		])].filter(Boolean).map((e) => ({
			value: e,
			label: V[e] || e,
			count: l.facets.status?.find((t) => t.value === e)?.count
		}))), O = (e) => l.parents.find((t) => t.source === e.source && String(t.parent_id) === String(e.id) && Number(t.child_count) > 0), k = (e) => e.service_sync_error || e.note || e.disabled_reason || "";
		function A(e) {
			o.owner.updateFilters({ [e]: e === "source" ? "all" : "" });
		}
		function M(e) {
			return e.last_activity_at || e.used_at || e.updated_at || e.created_at;
		}
		function z(e) {
			return `${e.used_at ? "最近使用" : e.last_activity_at ? "最近更新" : "导入时间"}：${I(M(e))}${e.synced_at ? `\n同步：${I(e.synced_at)}` : ""}`;
		}
		return (t, o) => (a(), d("section", {
			class: "em-list",
			"aria-label": "邮箱池",
			"aria-busy": x(l).loading
		}, [
			v("div", Ve, [v("div", He, [
				v("span", null, h(x(l).selected.size ? `已选 ${x(l).selected.size} 个邮箱` : "选择邮箱后批量操作"), 1),
				x(l).selected.size ? (a(), d(w, { key: 0 }, [
					v("button", {
						class: "em-button",
						disabled: x(l).busy,
						onClick: o[0] ||= (t) => e.owner.bulkStatus("available")
					}, "标记未使用", 8, Ue),
					v("button", {
						class: "em-button",
						disabled: x(l).busy,
						onClick: o[1] ||= (t) => e.owner.bulkStatus("disabled")
					}, "停用选中", 8, We),
					v("button", {
						class: "em-button",
						disabled: x(l).busy,
						onClick: o[2] ||= (t) => e.owner.bulkStatus("failed")
					}, "标失败", 8, Ge),
					v("button", {
						class: "em-button em-danger",
						disabled: x(l).busy,
						onClick: o[3] ||= (t) => e.owner.bulkDelete()
					}, "删除选中", 8, Ke)
				], 64)) : g("", !0),
				v("button", {
					class: "em-button",
					disabled: x(l).busy || !x(l).items.length,
					onClick: o[4] ||= (t) => e.owner.copyPage()
				}, "复制当前页", 8, qe),
				v("button", {
					class: "em-button em-primary",
					onClick: o[5] ||= (e) => s("localImport")
				}, "导入邮箱"),
				v("button", {
					class: "em-button",
					"data-butler-opener": "",
					onClick: o[6] ||= (e) => s("butlerImport")
				}, h(e.butlerLabel), 1)
			]), v("div", Je, [v("button", {
				class: "em-button",
				onClick: o[7] ||= (...e) => x(u).resetColumns && x(u).resetColumns(...e)
			}, "恢复列宽"), v("button", {
				class: "em-button",
				disabled: x(l).loading,
				onClick: o[8] ||= (t) => e.owner.refresh()
			}, "刷新", 8, Ye)])]),
			v("div", Xe, [
				v("strong", null, h(x(l).total) + " 个邮箱", 1),
				v("span", null, "当前页 " + h(x(l).items.length) + " 条" + h(x(l).selected.size ? ` · 已选 ${x(l).selected.size}` : ""), 1),
				E(N, {
					items: y.value,
					onRemove: A
				}, null, 8, ["items"])
			]),
			x(l).error ? (a(), d("div", Ze, [f(h(x(l).error) + " ", 1), v("button", {
				class: "em-button",
				onClick: o[9] ||= (t) => e.owner.refresh()
			}, "重试")])) : g("", !0),
			x(l).summaryError ? (a(), d("div", Qe, [f(h(x(l).summaryError) + " ", 1), v("button", {
				class: "em-button",
				onClick: o[10] ||= (t) => e.owner.refreshDerivationSummary()
			}, "重试")])) : g("", !0),
			E(Re, { receipt: x(l).receipt }, null, 8, ["receipt"]),
			v("div", $e, [v("table", {
				class: "em-table",
				style: T({ width: `${x(u).total.value}px` })
			}, [
				v("colgroup", null, [(a(!0), d(w, null, r(x(u).widths.value, (e, t) => (a(), d("col", {
					key: t,
					style: T({ width: `${e}px` })
				}, null, 4))), 128))]),
				v("thead", null, [v("tr", null, [
					v("th", null, [v("input", {
						type: "checkbox",
						"aria-label": "全选当前页邮箱资源",
						checked: !!x(l).items.length && p.value === x(l).items.length,
						indeterminate: p.value > 0 && p.value < x(l).items.length,
						disabled: !x(l).items.length,
						onChange: o[11] ||= (t) => e.owner.togglePage(t.target.checked)
					}, null, 40, et), E($, {
						index: 0,
						columns: x(u),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "邮箱",
						value: x(l).filters.q,
						active: e.active,
						onChange: o[12] ||= (t) => e.owner.updateFilters({ q: t })
					}, null, 8, ["value", "active"]), E($, {
						index: 1,
						columns: x(u),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "类型",
						value: x(l).filters.source,
						"empty-value": "all",
						options: C.value,
						active: e.active,
						onChange: o[13] ||= (t) => e.owner.updateFilters({ source: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), E($, {
						index: 2,
						columns: x(u),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "状态",
						value: x(l).filters.status,
						options: D.value,
						active: e.active,
						onChange: o[14] ||= (t) => e.owner.updateFilters({ status: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), E($, {
						index: 3,
						columns: x(u),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					v("th", null, [o[17] ||= f("使用情况", -1), E($, {
						index: 4,
						columns: x(u),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					v("th", null, [o[18] ||= f("凭证配置", -1), E($, {
						index: 5,
						columns: x(u),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "最近活动",
						type: "date",
						value: x(l).filters.used_date,
						active: e.active,
						onChange: o[15] ||= (t) => e.owner.updateFilters({ used_date: t })
					}, null, 8, ["value", "active"]), E($, {
						index: 6,
						columns: x(u),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					v("th", null, [o[19] ||= f("备注 / 原因", -1), E($, {
						index: 7,
						columns: x(u),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					v("th", null, [
						o[20] ||= f("操作 ", -1),
						v("button", {
							class: "em-text-button",
							onClick: o[16] ||= (t) => e.owner.resetFilters()
						}, "清筛"),
						E($, {
							index: 8,
							columns: x(u),
							label: "邮箱"
						}, null, 8, ["columns"])
					])
				])]),
				v("tbody", null, [(a(!0), d(w, null, r(x(l).items, (t) => (a(), d("tr", {
					key: x(W)(t),
					class: m({ "is-selected": x(l).selected.has(x(W)(t)) })
				}, [
					v("td", null, [v("input", {
						type: "checkbox",
						"aria-label": `选择邮箱 ${t.email}`,
						checked: x(l).selected.has(x(W)(t)),
						onChange: (n) => e.owner.toggle(t, n.target.checked)
					}, null, 40, tt)]),
					v("td", nt, [O(t) ? (a(), d("button", {
						key: 0,
						class: "em-cell-button",
						"aria-label": `查看 ${t.email} 的历史子地址`,
						title: [
							t.email,
							t.remote_label,
							`历史子地址 ${O(t)?.child_count} 个`
						].filter(Boolean).join(" · "),
						onClick: (e) => s("parent", t)
					}, [E(j, {
						text: t.email,
						secondary: `查看历史 · ${O(t)?.child_count} 个`
					}, null, 8, ["text", "secondary"])], 8, rt)) : (a(), _(j, {
						key: 1,
						text: t.email,
						secondary: t.remote_label || void 0
					}, null, 8, ["text", "secondary"]))]),
					v("td", null, [E(j, { text: x(B)[t.source] || t.source }, null, 8, ["text"])]),
					v("td", null, [E(j, { text: x(V)[t.status || ""] || t.status || "状态记录缺失" }, null, 8, ["text"])]),
					v("td", null, [E(j, {
						text: x(te)[t.usage_state || t.status || ""] || t.usage_state || t.status || "状态记录缺失",
						secondary: t.usage_state === "bound" && t.registered_account_id ? `账号 #${t.registered_account_id}` : void 0
					}, null, 8, ["text", "secondary"])]),
					v("td", null, [E(P, {
						label: x(q)(t).text,
						title: x(q)(t).detail
					}, {
						details: c(() => [f(h(x(q)(t).detail), 1)]),
						_: 2
					}, 1032, ["label", "title"])]),
					v("td", null, [E(P, i({ ref_for: !0 }, {
						label: x(L)(M(t)).text,
						secondary: x(L)(M(t)).secondary
					}, { title: z(t) }), {
						details: c(() => [f(h(z(t)), 1)]),
						_: 2
					}, 1040, ["title"])]),
					v("td", it, [k(t) ? (a(), _(P, {
						key: 0,
						"data-email-note": "",
						label: x(ie)(t),
						title: k(t),
						tone: t.service_sync_error ? "danger" : "neutral"
					}, {
						details: c(() => [f(h(k(t)), 1)]),
						_: 2
					}, 1032, [
						"label",
						"title",
						"tone"
					])) : (a(), _(j, {
						key: 1,
						text: "—"
					}))]),
					v("td", null, [v("div", at, [
						v("button", {
							class: "em-button",
							disabled: x(l).busy,
							onClick: (n) => e.owner.copyRow(t)
						}, "复制素材", 8, ot),
						v("button", {
							class: "em-button em-danger",
							disabled: x(l).busy,
							onClick: (n) => e.owner.rowAction(t, "delete")
						}, "删除", 8, st),
						["replaced", "pending_sync"].includes(t.status || "") ? g("", !0) : (a(), d("details", ct, [v("summary", { "aria-label": `更多操作 ${t.email}` }, "更多", 8, lt), v("div", null, [(a(), d(w, null, r({
							available: "恢复可用",
							disabled: "停用",
							failed: "标失败"
						}, (r, i) => n(v("button", {
							key: i,
							class: "em-button",
							disabled: x(l).busy,
							onClick: (n) => e.owner.rowAction(t, i)
						}, h(r), 9, ut), [[b, i !== t.status]])), 64))])]))
					])])
				], 2))), 128)), x(l).items.length ? g("", !0) : (a(), d("tr", dt, [v("td", ft, h(x(l).loading ? "正在加载邮箱资源…" : x(l).error ? "邮箱资源加载失败" : "暂无邮箱资源，调整筛选条件或导入新的邮箱资源。"), 1)]))])
			], 4)]),
			E(F, {
				page: x(l).page,
				size: x(l).size,
				total: x(l).total,
				busy: x(l).loading,
				"page-sizes": [
					10,
					20,
					30,
					50,
					100
				],
				label: "邮箱资源分页",
				"onUpdate:page": e.owner.setPage,
				"onUpdate:size": e.owner.setSize
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		], 8, Be));
	}
}), mt = ["aria-busy"], ht = { class: "em-toolbar" }, gt = { class: "em-actions" }, _t = ["disabled"], vt = {
	class: "em-count-row",
	"data-email-count-row": ""
}, yt = {
	key: 0,
	class: "em-error",
	role: "alert"
}, bt = { class: "em-table-wrap" }, xt = [
	"checked",
	"indeterminate",
	"disabled"
], St = [
	"aria-label",
	"checked",
	"onChange"
], Ct = { class: "em-align-start" }, wt = { class: "em-align-start" }, Tt = { key: 0 }, Et = {
	colspan: "8",
	class: "em-empty",
	role: "status"
}, Dt = /* @__PURE__ */ o({
	__name: "EmailHistory",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(e) {
		let t = e, n = t.owner.state, o = R({
			defaults: [
				40,
				248,
				224,
				112,
				120,
				172,
				140,
				88
			],
			storageKey: "gpt_console_table_widths_derivations",
			totalStorageKey: "gpt_console_table_total_derivations",
			min: 28,
			max: 2e4
		}), s = S(() => n.items.filter((e) => n.selected.has(String(e.id))).length), c = [{
			value: "icloud_hide",
			label: "iCloud 隐藏邮箱"
		}, {
			value: "outlook",
			label: "Outlook"
		}], l = Object.entries(H).map(([e, t]) => ({
			value: e,
			label: t
		})), u = S(() => Object.entries(n.filters).filter(([e, t]) => t && (e !== "source" || t !== "all")).map(([e, t]) => ({
			key: e,
			label: `${{
				source: "来源",
				parent_id: "母邮箱",
				q: "子邮箱",
				parent_q: "母邮箱搜索",
				state: "状态",
				related_q: "关联账号/任务",
				created_from: "生成开始",
				created_to: "生成结束"
			}[e]}：${e === "source" ? B[t] || t : e === "state" ? H[t] || t : e === "parent_id" ? n.parentEmail || `#${t}` : t}`,
			removeLabel: `移除${e}筛选`
		})));
		function p(e) {
			e === "parent_id" ? t.owner.clearParent() : t.owner.updateFilters({ [e]: e === "source" ? "all" : "" });
		}
		return (t, _) => (a(), d("section", {
			class: "em-list",
			"aria-label": "历史子邮箱",
			"aria-busy": x(n).loading
		}, [
			_[13] ||= v("p", { class: "em-help" }, "子邮箱由你手动准备并导入本地库存；此处可查看、筛选和复制已有记录，Turb 不会自动生成。", -1),
			v("div", ht, [v("div", gt, [v("span", null, h(x(n).selected.size ? `已选 ${x(n).selected.size} 条历史记录` : "可筛选并复制历史子邮箱"), 1), v("button", {
				class: "em-button",
				disabled: !x(n).items.length && !x(n).selected.size,
				onClick: _[0] ||= (t) => e.owner.copy()
			}, h(x(n).selected.size ? "复制选中" : "复制当前页"), 9, _t)]), v("button", {
				class: "em-button",
				onClick: _[1] ||= (...e) => x(o).resetColumns && x(o).resetColumns(...e)
			}, "恢复列宽")]),
			v("div", vt, [
				v("strong", null, h(x(n).total) + " 条历史记录", 1),
				v("span", null, "当前页 " + h(x(n).items.length) + " 条", 1),
				E(N, {
					items: u.value,
					onRemove: p
				}, null, 8, ["items"])
			]),
			x(n).error ? (a(), d("div", yt, [f(h(x(n).error) + " ", 1), v("button", {
				class: "em-button",
				onClick: _[2] ||= (t) => e.owner.refresh()
			}, "重试")])) : g("", !0),
			E(Re, { receipt: x(n).receipt }, null, 8, ["receipt"]),
			v("div", bt, [v("table", {
				class: "em-table",
				style: T({ width: `${x(o).total.value}px` })
			}, [
				v("colgroup", null, [(a(!0), d(w, null, r(x(o).widths.value, (e, t) => (a(), d("col", {
					key: t,
					style: T({ width: `${e}px` })
				}, null, 4))), 128))]),
				v("thead", null, [v("tr", null, [
					v("th", null, [v("input", {
						type: "checkbox",
						"aria-label": "全选当前页子邮箱",
						checked: !!x(n).items.length && s.value === x(n).items.length,
						indeterminate: s.value > 0 && s.value < x(n).items.length,
						disabled: !x(n).items.length,
						onChange: _[3] ||= (t) => e.owner.togglePage(t.target.checked)
					}, null, 40, xt), E($, {
						index: 0,
						columns: x(o),
						label: "历史"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "子邮箱",
						value: x(n).filters.q,
						active: e.active,
						onChange: _[4] ||= (t) => e.owner.updateFilters({ q: t })
					}, null, 8, ["value", "active"]), E($, {
						index: 1,
						columns: x(o),
						label: "历史"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "母邮箱",
						value: x(n).filters.parent_q,
						active: e.active,
						onChange: _[5] ||= (t) => e.owner.updateFilters({ parent_q: t })
					}, null, 8, ["value", "active"]), E($, {
						index: 2,
						columns: x(o),
						label: "历史"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "来源",
						value: x(n).filters.source,
						"empty-value": "all",
						options: c,
						active: e.active,
						onChange: _[6] ||= (t) => e.owner.updateFilters({ source: t })
					}, null, 8, ["value", "active"]), E($, {
						index: 3,
						columns: x(o),
						label: "历史"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "状态",
						value: x(n).filters.state,
						options: x(l),
						active: e.active,
						onChange: _[7] ||= (t) => e.owner.updateFilters({ state: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), E($, {
						index: 4,
						columns: x(o),
						label: "历史"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "关联账号 / 任务",
						value: x(n).filters.related_q,
						active: e.active,
						onChange: _[8] ||= (t) => e.owner.updateFilters({ related_q: t })
					}, null, 8, ["value", "active"]), E($, {
						index: 5,
						columns: x(o),
						label: "历史"
					}, null, 8, ["columns"])]),
					v("th", null, [E(Q, {
						label: "生成时间",
						type: "range",
						value: x(n).filters.created_from,
						"end-value": x(n).filters.created_to,
						active: e.active,
						onChange: _[9] ||= (t) => e.owner.updateFilters({ created_from: t }),
						onEnd: _[10] ||= (t) => e.owner.updateFilters({ created_to: t })
					}, null, 8, [
						"value",
						"end-value",
						"active"
					]), E($, {
						index: 6,
						columns: x(o),
						label: "历史"
					}, null, 8, ["columns"])]),
					v("th", null, [
						_[12] ||= f("操作 ", -1),
						v("button", {
							class: "em-text-button",
							onClick: _[11] ||= (t) => e.owner.resetFilters()
						}, "清筛"),
						E($, {
							index: 7,
							columns: x(o),
							label: "历史"
						}, null, 8, ["columns"])
					])
				])]),
				v("tbody", null, [(a(!0), d(w, null, r(x(n).items, (t) => (a(), d("tr", {
					key: String(t.id),
					class: m({ "is-selected": x(n).selected.has(String(t.id)) })
				}, [
					v("td", null, [v("input", {
						type: "checkbox",
						"aria-label": `选择历史子邮箱 ${t.email}`,
						checked: x(n).selected.has(String(t.id)),
						onChange: (n) => e.owner.toggle(t, n.target.checked)
					}, null, 40, St)]),
					v("td", Ct, [E(j, { text: t.email }, null, 8, ["text"])]),
					v("td", wt, [E(j, {
						text: t.parent_email || "—",
						secondary: `母资源 #${t.parent_id || "—"}`
					}, null, 8, ["text", "secondary"])]),
					v("td", null, [E(j, { text: x(B)[t.source] || t.source }, null, 8, ["text"])]),
					v("td", null, [E(j, { text: x(H)[t.state || ""] || t.state || "状态记录缺失" }, null, 8, ["text"])]),
					v("td", null, [E(j, { text: x(re)(t) }, null, 8, ["text"])]),
					v("td", null, [E(j, i({ ref_for: !0 }, x(L)(t.created_at)), null, 16)]),
					v("td", null, [E(j, { text: "只读" })])
				], 2))), 128)), x(n).items.length ? g("", !0) : (a(), d("tr", Tt, [v("td", Et, h(x(n).loading ? "正在读取历史子邮箱…" : x(n).error ? "子邮箱历史加载失败" : "当前筛选下没有历史子地址，请从 Email Butler 等来源手动准备邮箱，再导入本地库存。"), 1)]))])
			], 4)]),
			E(F, {
				page: x(n).page,
				size: x(n).size,
				total: x(n).total,
				busy: x(n).loading,
				"page-sizes": [
					20,
					50,
					100
				],
				label: "历史子邮箱分页",
				"onUpdate:page": e.owner.setPage,
				"onUpdate:size": e.owner.setSize
			}, null, 8, [
				"page",
				"size",
				"total",
				"busy",
				"onUpdate:page",
				"onUpdate:size"
			])
		], 8, mt));
	}
}), Ot = ["aria-busy"], kt = { class: "em-dialog-head" }, At = { class: "em-dialog-body" }, jt = {
	key: 0,
	class: "em-error",
	role: "alert"
}, Mt = { class: "em-field" }, Nt = ["value", "disabled"], Pt = ["value"], Ft = { class: "em-field" }, It = [
	"value",
	"placeholder",
	"disabled"
], Lt = { class: "em-help" }, Rt = {
	key: 1,
	class: "em-field"
}, zt = ["value", "disabled"], Bt = {
	key: 2,
	class: "em-preview",
	"aria-label": "导入前检查"
}, Vt = { class: "em-stats" }, Ht = { key: 0 }, Ut = { key: 1 }, Wt = { class: "em-dialog-foot" }, Gt = ["disabled"], Kt = ["disabled"], qt = /* @__PURE__ */ o({
	__name: "EmailLocalImport",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(t) {
		let n = t, i = n.owner.state, o = e();
		return z(o, () => i.open, () => n.active), (e, n) => (a(), d("dialog", {
			ref_key: "dialog",
			ref: o,
			class: "em-dialog",
			"data-email-local-import": "",
			"aria-labelledby": "emailLocalImportTitle",
			"aria-busy": x(i).busy || x(i).loading,
			onCancel: n[7] ||= p((e) => t.owner.close(), ["prevent"]),
			onClick: n[8] ||= (e) => e.target === o.value && t.owner.close()
		}, [
			v("div", kt, [n[9] ||= v("div", null, [v("h3", { id: "emailLocalImportTitle" }, "导入邮箱资源"), v("p", null, "手动补充本地库存；Outlook 和通用 API 保留原格式，Butler 类型每行粘贴一个完整 iCloud HME 地址。")], -1), v("button", {
				class: "em-button",
				"aria-label": "关闭邮箱导入",
				onClick: n[0] ||= (e) => t.owner.close()
			}, "关闭")]),
			v("div", At, [
				E(Re, { receipt: x(i).receipt }, null, 8, ["receipt"]),
				x(i).error ? (a(), d("p", jt, h(x(i).error), 1)) : g("", !0),
				v("label", Mt, [n[10] ||= f("导入类型", -1), v("select", {
					"aria-label": "导入类型",
					value: x(i).source,
					disabled: x(i).busy,
					onChange: n[1] ||= (e) => t.owner.update({ source: e.target.value })
				}, [(a(!0), d(w, null, r(x(X), (e, t) => (a(), d("option", {
					key: t,
					value: t
				}, h(e.label), 9, Pt))), 128))], 40, Nt)]),
				n[16] ||= v("p", { class: "em-help" }, "注册任务只领取本地可用库存；Butler 导入会交接原地址，不自动生成邮箱。", -1),
				v("label", Ft, [n[11] ||= f("邮箱资源", -1), v("textarea", {
					"aria-label": "邮箱资源",
					value: x(i).text,
					placeholder: x(X)[x(i).source].placeholder,
					disabled: x(i).busy,
					onInput: n[2] ||= (e) => t.owner.update({ text: e.target.value })
				}, null, 40, It)]),
				v("p", Lt, h(x(X)[x(i).source].hint), 1),
				x(i).source === "generic_api" ? (a(), d("label", Rt, [
					n[12] ||= f("批次有效期（可选）", -1),
					v("input", {
						"aria-label": "批次有效期",
						type: "text",
						value: x(i).expiresAt,
						disabled: x(i).busy,
						placeholder: "2026-12-01T12:00:00+08:00",
						onInput: n[3] ||= (e) => t.owner.update({ expiresAt: e.target.value })
					}, null, 40, zt),
					n[13] ||= v("small", null, "只补充未在第三字段填写有效期的通用 API 邮箱；留空保留旧两段格式，不会推算有效期。", -1)
				])) : g("", !0),
				x(i).preview ? (a(), d("section", Bt, [
					n[15] ||= v("strong", null, "导入前检查", -1),
					v("div", Vt, [(a(!0), d(w, null, r([
						["输入行数", x(i).preview.total_lines],
						["可解析", x(i).preview.valid],
						["可新增", x(i).preview.new],
						["已存在", x(i).preview.existing],
						["输入重复", x(i).preview.duplicate_in_input],
						["无效行", x(i).preview.invalid]
					], (e) => (a(), d("div", { key: String(e[0]) }, [v("strong", null, h(e[1] || 0), 1), v("span", null, h(e[0]), 1)]))), 128))]),
					x(i).preview.extra_fields ? (a(), d("p", Ht, "检测到 " + h(x(i).preview.extra_fields) + " 个多余字段，导入时会忽略。", 1)) : g("", !0),
					x(i).preview.invalid_rows?.length ? (a(), d("details", Ut, [n[14] ||= v("summary", null, "无效行详情", -1), (a(!0), d(w, null, r(x(i).preview.invalid_rows, (e) => (a(), d("p", { key: e.line }, "第 " + h(e.line) + " 行：" + h(e.reason), 1))), 128))])) : g("", !0)
				])) : g("", !0)
			]),
			v("div", Wt, [
				v("button", {
					class: "em-button",
					onClick: n[4] ||= (e) => t.owner.close()
				}, "取消"),
				v("button", {
					class: "em-button",
					disabled: x(i).loading || x(i).busy,
					onClick: n[5] ||= (e) => t.owner.preview()
				}, h(x(i).loading ? "解析中…" : "解析预览"), 9, Gt),
				v("button", {
					class: "em-button em-primary",
					"data-local-submit": "",
					disabled: x(i).busy || x(i).loading || !x(i).text.trim() || !!x(i).preview && !x(i).preview.new,
					onClick: n[6] ||= (e) => t.owner.submit()
				}, h(x(i).busy ? "正在导入…" : "导入到邮箱池"), 9, Kt)
			])
		], 40, Ot));
	}
}), Jt = ["aria-busy"], Yt = { class: "em-dialog-head" }, Xt = { id: "emailButlerImportDescription" }, Zt = { class: "em-dialog-body" }, Qt = {
	key: 0,
	class: "em-dialog-fields"
}, $t = { class: "em-field" }, en = ["value", "disabled"], tn = ["value"], nn = { class: "em-field" }, rn = ["value", "disabled"], an = {
	key: 1,
	class: "em-error",
	role: "alert"
}, on = {
	key: 2,
	role: "status",
	"aria-live": "polite"
}, sn = {
	key: 3,
	class: "em-preview",
	"aria-label": "Butler 导入结果"
}, cn = ["max", "value"], ln = { class: "em-stats" }, un = {
	role: "status",
	"aria-live": "polite"
}, dn = { class: "em-help em-preserve-lines" }, fn = { key: 1 }, pn = { key: 2 }, mn = { key: 3 }, hn = { class: "em-dialog-foot" }, gn = ["disabled"], _n = ["disabled"], vn = ["disabled"], yn = ["disabled"], bn = /* @__PURE__ */ o({
	__name: "EmailButlerImport",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(t) {
		let n = t, i = n.owner.state, o = e();
		z(o, () => i.open, () => n.active);
		let s = S(() => Number(i.batch?.imported || 0) + Number(i.batch?.skipped || 0) + Number(i.batch?.failed || 0) + Number(i.batch?.unknown || 0)), l = S(() => n.active && !!i.request && !i.open && ![
			"completed",
			"succeeded",
			"done",
			"cancelled"
		].includes(i.batch?.status || ""));
		return (e, n) => (a(), d(w, null, [l.value ? (a(), d("button", {
			key: 0,
			class: "em-recovery em-button",
			"aria-label": "查看 Butler 导入进度",
			onClick: n[0] ||= (e) => t.owner.open()
		}, h(x(i).batch ? `Butler 导入${t.owner.isRunning.value ? "中" : "结果"} · 已导入 ${x(i).batch.imported || 0} / ${x(i).batch.total || 0} · 查看进度` : "Butler 导入请求响应缺失 · 查看进度"), 1)) : g("", !0), v("dialog", {
			ref_key: "dialog",
			ref: o,
			class: "em-dialog",
			"data-email-butler-import": "",
			"aria-labelledby": "emailButlerImportTitle",
			"aria-describedby": "emailButlerImportDescription",
			"aria-busy": x(i).busy || x(i).polling,
			onCancel: n[10] ||= p((e) => t.owner.close(), ["prevent"]),
			onClick: n[11] ||= (e) => e.target === o.value && t.owner.close()
		}, [
			v("div", Yt, [v("div", null, [n[12] ||= v("h3", { id: "emailButlerImportTitle" }, "从 Butler 导入邮箱", -1), v("p", Xt, h(x(i).request ? "导入进度会自动保存，可随时关闭窗口。" : "从 Butler 分配长期租用的邮箱，加入本地库存后使用。"), 1)]), v("button", {
				class: "em-button",
				"aria-label": "关闭 Butler 导入窗口",
				onClick: n[1] ||= (e) => t.owner.close()
			}, "关闭")]),
			v("div", Zt, [
				x(i).request ? g("", !0) : (a(), d("div", Qt, [
					v("label", $t, [n[13] ||= f("邮箱类型", -1), v("select", {
						"aria-label": "Butler 邮箱类型",
						value: x(i).filters.provider,
						disabled: x(i).storageError || x(i).busy,
						onChange: n[2] ||= (e) => t.owner.changeFilters({ provider: e.target.value })
					}, [(a(!0), d(w, null, r(x(i).providers, (e) => (a(), d("option", {
						key: e.value,
						value: e.value
					}, h(e.label), 9, tn))), 128))], 40, en)]),
					v("label", nn, [n[14] ||= f("导入数量", -1), v("input", {
						"aria-label": "Butler 导入数量",
						type: "number",
						min: "1",
						step: "1",
						inputmode: "numeric",
						value: x(i).filters.count,
						disabled: x(i).storageError || x(i).busy,
						onInput: n[3] ||= (e) => t.owner.changeFilters({ count: Number(e.target.value) })
					}, null, 40, rn)]),
					n[15] ||= v("p", { class: "em-help" }, "不足时按预览可用数量导入，确认后由 Butler 分配完整地址。", -1)
				])),
				x(i).error ? (a(), d("p", an, h(x(i).error), 1)) : g("", !0),
				x(i).request ? g("", !0) : (a(), d("p", on, h(x(i).previewing ? "正在查询当前可用数量…" : t.owner.availability.value), 1)),
				x(i).request ? (a(), d("section", sn, [
					v("h4", null, h(t.owner.batchTitle.value), 1),
					x(i).batch ? (a(), d(w, { key: 0 }, [
						v("progress", {
							max: Math.max(Number(x(i).batch.total || 0), 1),
							value: Math.min(s.value, Number(x(i).batch.total || 0)),
							"aria-label": "邮箱导入进度"
						}, null, 8, cn),
						v("div", ln, [(a(!0), d(w, null, r([
							["已导入", x(i).batch.imported],
							["待处理", x(i).batch.pending],
							["租用中", x(i).batch.submitting],
							["已跳过", x(i).batch.skipped],
							["失败", Number(x(i).batch.failed || 0) + Number(x(i).batch.unknown || 0)]
						], (e) => (a(), d("div", { key: String(e[0]) }, [v("strong", null, h(e[1] || 0), 1), v("span", null, h(e[0]), 1)]))), 128))]),
						v("p", un, "已处理 " + h(s.value) + " / " + h(x(i).batch.total || 0) + " 个，本次请求 " + h(x(i).batch.requested || 0) + " 个。", 1)
					], 64)) : g("", !0),
					E(P, {
						label: x(ne)(t.owner.batchTitle.value),
						title: t.owner.batchDetails.value,
						tone: x(i).batch?.status === "cancelled" ? "neutral" : x(i).batch?.failed ? "warning" : "active"
					}, {
						details: c(() => [f(h(t.owner.batchDetails.value), 1)]),
						_: 1
					}, 8, [
						"label",
						"title",
						"tone"
					]),
					v("p", dn, h(x(i).batch?.status === "cancelled" ? "已停止后续导入，原结果与租约保留。" : t.owner.isRunning.value || x(i).resumePending ? "可以关闭窗口，导入会在后台继续。" : x(i).batch?.can_retry ? "可继续原批次处理剩余邮箱，已导入的邮箱会保留。" : "已保存原导入记录。"), 1),
					x(i).request.filters ? (a(), d("small", fn, "来源：" + h(x(Z).find((e) => e.value === x(i).request?.filters?.provider)?.label || x(i).request.filters.provider) + " · 原请求数量 " + h(x(i).request.filters.count), 1)) : g("", !0),
					x(i).batch ? (a(), d("small", pn, "批次：" + h(x(i).batch.batch_id), 1)) : g("", !0),
					x(i).request ? (a(), d("small", mn, "原请求：" + h(x(i).request.request_id), 1)) : g("", !0)
				])) : g("", !0)
			]),
			v("div", hn, [
				v("button", {
					class: "em-button",
					onClick: n[4] ||= (e) => t.owner.close()
				}, h(t.owner.isRunning.value || x(i).resumePending ? "关闭，后台继续" : "关闭"), 1),
				t.owner.canCancel.value ? (a(), d("button", {
					key: 0,
					class: "em-button em-danger",
					disabled: x(i).busy,
					onClick: n[5] ||= (e) => t.owner.cancel()
				}, h(x(i).busy ? "正在终止…" : "终止批次"), 9, gn)) : g("", !0),
				t.owner.canReset.value ? (a(), d("button", {
					key: 1,
					class: "em-button",
					disabled: x(i).busy || x(i).polling,
					onClick: n[6] ||= (e) => t.owner.reset()
				}, "新建导入", 8, _n)) : g("", !0),
				x(i).request ? t.owner.canRetry.value ? (a(), d("button", {
					key: 3,
					class: "em-button em-primary",
					onClick: n[9] ||= (e) => t.owner.retry()
				}, h(x(i).batch ? "继续原批次" : "重试原请求"), 1)) : g("", !0) : (a(), d(w, { key: 2 }, [v("button", {
					class: "em-button",
					disabled: x(i).busy || x(i).previewing || x(i).storageError,
					onClick: n[7] ||= (e) => t.owner.preview()
				}, "刷新可用数量", 8, vn), v("button", {
					class: "em-button em-primary",
					disabled: x(i).busy || x(i).previewing || x(i).storageError || !x(i).preview?.selected,
					onClick: n[8] ||= (e) => t.owner.apply()
				}, h(x(i).preview?.selected ? `开始导入 ${x(i).preview.selected} 个` : "开始导入"), 9, yn)], 64))
			])
		], 40, Jt)], 64));
	}
}), xn = { class: "em-page" }, Sn = /* @__PURE__ */ o({
	__name: "EmailPageShell",
	props: {
		api: {},
		deps: {},
		initialView: {},
		initialVisible: { type: Boolean }
	},
	setup(r, { expose: i }) {
		let o = r, s = e(o.initialView || "overview"), c = e(o.initialVisible || !1), l = e(!document.hidden), f = u({
			sources: [],
			expanded: !1,
			loading: !1,
			error: ""
		}), p = J(f, async (e, t) => {
			let n = await o.api.overview(e);
			t() && (f.sources = n.email?.supply?.sources || n.email?.sources || []);
		}), m = ae(o.api, o.deps), h = oe(o.api, o.deps), g = {
			...o.deps,
			async onInventoryChanged() {
				m.refresh(), h.refresh(), p.refresh(), await o.deps.onInventoryChanged();
			}
		}, _ = se(o.api, g), y = he(o.api, g, { storage: {
			getItem: (e) => localStorage.getItem(e),
			setItem: (e, t) => localStorage.setItem(e, t),
			removeItem: (e) => localStorage.removeItem(e)
		} }), C = S(() => y.state.request ? y.isRunning.value ? `Butler 导入中 · ${y.state.batch?.imported || 0}/${y.state.batch?.total || 0}` : "查看 Butler 导入" : "从 Butler 导入");
		function w() {
			let e = c.value && l.value;
			p.setActive(e && s.value === "overview"), m.setActive(e && s.value === "list"), h.setActive(e && s.value === "derivations"), _.setActive(e), y.setActive(e);
		}
		function T() {
			_.close(), y.close();
		}
		function D(e) {
			[
				"overview",
				"list",
				"derivations"
			].includes(e) && s.value !== e && (s.value = e, T(), w());
		}
		function O(e) {
			c.value !== e && (c.value = e, e || T(), w());
		}
		function k(e) {
			e.id && (h.scopeParent({
				source: e.source,
				id: e.id,
				email: e.email
			}), o.deps.onNavigate("derivations"));
		}
		function A(e) {
			m.updateFilters({ source: e }), o.deps.onNavigate("list");
		}
		async function j(e) {
			_.open(e || ([
				"outlook",
				"generic_api",
				"email_butler"
			].includes(m.state.filters.source) ? m.state.filters.source : "outlook"));
		}
		async function M() {
			await y.open();
		}
		function N() {
			l.value = !document.hidden, w();
		}
		return document.addEventListener("visibilitychange", N), w(), t(() => {
			document.removeEventListener("visibilitychange", N), p.dispose(), m.dispose(), h.dispose(), _.dispose(), y.dispose();
		}), i({
			setView: D,
			setVisible: O,
			refreshOverview: p.refresh,
			refreshInventory: m.refresh,
			refreshHistory: h.refresh,
			refreshDerivationSummary: m.refreshDerivationSummary,
			openImport: j,
			openButlerImport: M,
			closeDialogs: T
		}), (e, t) => (a(), d("div", xn, [
			t[4] ||= v("h1", null, "邮箱资源池", -1),
			n(E(ke, {
				sources: f.sources,
				expanded: f.expanded,
				loading: f.loading,
				error: f.error,
				"butler-label": C.value,
				onRefresh: t[0] ||= (e) => x(p).refresh(),
				onExpand: t[1] ||= (e) => f.expanded = !f.expanded,
				onSource: A,
				onLocalImport: t[2] ||= (e) => j("email_butler"),
				onButlerImport: M
			}, null, 8, [
				"sources",
				"expanded",
				"loading",
				"error",
				"butler-label"
			]), [[b, s.value === "overview"]]),
			n(E(pt, {
				owner: x(m),
				active: c.value && l.value && s.value === "list",
				"butler-label": C.value,
				onLocalImport: t[3] ||= (e) => j(),
				onButlerImport: M,
				onParent: k
			}, null, 8, [
				"owner",
				"active",
				"butler-label"
			]), [[b, s.value === "list"]]),
			n(E(Dt, {
				owner: x(h),
				active: c.value && l.value && s.value === "derivations"
			}, null, 8, ["owner", "active"]), [[b, s.value === "derivations"]]),
			E(qt, {
				owner: x(_),
				active: c.value && l.value
			}, null, 8, ["owner", "active"]),
			E(bn, {
				owner: x(y),
				active: c.value && l.value
			}, null, 8, ["owner", "active"])
		]));
	}
});
// src/api/email.ts
function Cn(e = (e, t) => k(e, t, ee)) {
	let t = (t, n) => e(t, { signal: n }), n = (t, n, r) => e(t, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(n),
		...r ? { signal: r } : {}
	});
	return {
		overview: (e) => t("/api/dashboard", e),
		inventory: (e, n) => {
			let { size: r, ...i } = e;
			return t(`/api/outlook?${new URLSearchParams({
				paged: "1",
				page: String(i.page),
				page_size: String(r),
				source: i.source,
				q: i.q,
				status: i.status,
				used_date: i.used_date
			})}`, n);
		},
		derivationSummary: (e) => t("/api/email-derivation/summary?source=all", e),
		history: (e, n) => {
			let { size: r, page: i, ...a } = e, o = new URLSearchParams({
				page: String(i),
				page_size: String(r)
			});
			for (let [e, t] of Object.entries(a)) t && o.set(e, t);
			return t(`/api/email-derivation/allocations?${o}`, n);
		},
		secret: (e, n) => t(`/api/outlook/secret?${new URLSearchParams({
			...e,
			field: "copy_line"
		})}`, n),
		secrets: (e, t) => n("/api/outlook/secret-bulk", {
			items: e,
			field: "copy_line"
		}, t),
		status: (e) => n("/api/outlook/status", e),
		bulkStatus: (e) => n("/api/outlook/status-bulk", e),
		delete: (e) => n("/api/outlook/delete", e),
		bulkDelete: (e) => n("/api/outlook/delete-bulk", e),
		localPreview: (e, t) => n("/api/outlook/import-preview", e, t),
		localImport: (e) => n("/api/outlook/import", e),
		options: (e) => t("/api/email-butler/import-options", e),
		butlerPreview: (e, t) => n("/api/email-butler/import-preview", e, t),
		createBatch: (e) => n("/api/email-butler/imports", e),
		batch: (e, n) => t(`/api/email-butler/imports/${encodeURIComponent(e)}`, n),
		retryBatch: (e, t) => n(`/api/email-butler/imports/${encodeURIComponent(e)}/retry`, t),
		cancelBatch: (t) => e(`/api/email-butler/imports/${encodeURIComponent(t)}/cancel`, { method: "POST" })
	};
}
// src/email.ts
function wn(e, t) {
	let n = y(Sn, {
		api: Cn(),
		deps: t,
		initialView: t.view || "overview",
		initialVisible: t.visible || !1
	}), r = n.mount(e);
	return {
		setView: r.setView,
		setVisible: r.setVisible,
		refreshOverview: r.refreshOverview,
		refreshInventory: r.refreshInventory,
		refreshHistory: r.refreshHistory,
		refreshDerivationSummary: r.refreshDerivationSummary,
		openImport: r.openImport,
		openButlerImport: r.openButlerImport,
		closeDialogs: r.closeDialogs,
		destroy: () => n.unmount()
	};
}
export { wn as mountEmail };
