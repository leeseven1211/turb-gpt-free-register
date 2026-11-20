import { B as e, C as t, F as n, G as r, H as i, K as a, L as o, Q as s, S as c, X as l, _ as u, c as d, d as f, dt as p, et as m, ft as h, g, h as _, j as v, k as y, l as b, lt as x, m as S, n as C, s as w, st as T, v as E, x as D } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { n as O, r as k, t as A } from "./client-B5R_MNgP.js";
import { n as j, r as M, t as N } from "./ListFilterSummary-Bc1S5NP4.js";
import { t as P } from "./ListResult-BkPTMQVQ.js";
import { t as F } from "./ListPagination-DURVj-Kj.js";
import { n as I, t as L } from "./time-DOD6oyhP.js";
import { t as R } from "./useColumnWidths-D1sKP53m.js";
import { t as z } from "./useNativeDialog-DWisXYg9.js";
import { r as B } from "./taskIds-BlchWwUp.js";
// src/features/email/presentation.ts
var V = {
	all: "全部邮箱池",
	outlook: "Outlook",
	generic_api: "通用 API",
	cloudflare_domain: "域名邮箱",
	icloud_hide: "iCloud 隐藏邮箱",
	email_butler: "Butler 本地邮箱"
}, H = {
	available: "可用",
	used: "已用",
	pending_sync: "导入处理中",
	tombstone: "本地已删除",
	replaced: "换绑后邮箱",
	failed: "失败",
	disabled: "已停用"
}, ee = {
	available: "待领取",
	pending_sync: "导入处理中",
	tombstone: "本地已删除",
	used_unbound: "已领取未绑定",
	bound: "已绑定账号",
	replaced: "换绑后邮箱",
	failed: "失败",
	disabled: "已停用"
}, U = {
	available: "历史未领取",
	disabled: "已停用",
	reserved: "归属已保留",
	used: "已绑定账号",
	replaced: "换绑后地址",
	retired: "历史停用"
}, W = (e) => ({
	source: e.source,
	email: e.email
}), G = (e) => `${e.source}|${e.email}`, K = (e) => e instanceof Error ? e.message : String(e);
function te(e, t = 10) {
	let n = Array.from(e);
	return n.length > t ? n.slice(0, t - 1).join("") + "…" : e;
}
function q(e, t, n = "neutral") {
	return {
		label: te(e),
		detail: t,
		tone: n
	};
}
function J(e) {
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
function ne(e) {
	return [e.registered_account_id ? `账号 #${e.registered_account_id}` : "", e.root_task_id ? `任务 #${e.root_task_id}` : ""].filter(Boolean).join(" · ") || (["available", "disabled"].includes(e.state || "") ? "尚未领取" : "历史归属");
}
function re(e) {
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
function Y(e, t) {
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
			o() && !O(t) && (e.error = K(t));
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
function ie(e, t) {
	let n = s({
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
	}), r, i = Y(n, async (t, r) => {
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
			r() && !(e instanceof Error && e.name === "AbortError") && (n.summaryError = `子地址历史读取失败：${K(e)}`);
		}
	});
	function a(e) {
		let t = Object.keys(e).filter((t) => e[t] !== n.filters[t]);
		t.length && (Object.assign(n.filters, e), n.page = 1, t.some((e) => e !== "q") && n.selected.clear(), i.schedule(t.every((e) => e === "q") ? 250 : 0));
	}
	function o(e, t) {
		t ? n.selected.set(G(e), W(e)) : n.selected.delete(G(e));
	}
	function c(e) {
		for (let t of n.items) o(t, e);
	}
	async function l() {
		try {
			await t.onInventoryChanged();
		} catch (e) {
			n.receipt = q(n.receipt?.label || "已接收", `${n.receipt?.detail || ""}\n显示刷新失败：${K(e)}`, "warning");
		}
		i.refresh();
	}
	async function u(e) {
		if (!n.busy) {
			n.busy = !0;
			try {
				await e();
			} catch (e) {
				if (e instanceof Error && e.name === "AbortError") return;
				n.receipt = q("操作失败", K(e), "danger"), t.notify(`操作失败：${K(e)}`);
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
		let r = Array.from(n.selected.values(), W), i = n.filters.source;
		r.length && !n.busy && await u(async () => {
			if (!await t.confirm(`确定从本地邮箱池移除选中的 ${r.length} 个邮箱吗？\n\n保留使用历史；缺少注册完成回执时保留原租约，确认账号未创建后才可退还。已确认注册成功的邮箱不能删除。`)) return;
			let a = await e.bulkDelete({
				items: r,
				source: i
			});
			for (let e of Array.isArray(a.deleted) ? a.deleted : []) n.selected.delete(G(e));
			n.receipt = q("删除结果", d(a, "delete"), "success"), await l();
		});
	}
	async function p(r) {
		let i = Array.from(n.selected.values(), W), a = n.filters.source;
		if (!i.length || n.busy) return;
		let o = {
			available: "未使用/可用",
			disabled: "停用",
			failed: "失败"
		}[r] || r;
		await u(async () => {
			if (!await t.confirm(`确定把选中的 ${i.length} 个邮箱标记为${o}吗？`)) return;
			let s = await e.bulkStatus({
				items: i,
				status: r,
				source: a,
				note: `批量标记${o}`
			});
			for (let e of i) n.selected.delete(G(e));
			n.receipt = q("状态更新", d(s, "status"), "success"), await l();
		});
	}
	async function m(r, i) {
		let a = W(r);
		await u(async () => {
			if (i === "delete") {
				if (!await t.confirm(`确定从本地邮箱池移除 ${a.email}？\n\n保留使用历史；缺少注册完成回执时保留原租约，确认账号未创建后才可退还。已确认注册成功的邮箱不能删除。`)) return;
				let r = await e.delete(a);
				r.deleted ? (n.selected.delete(G(a)), n.receipt = q("本地已移除", r.sync?.message || "本地已移除，保留使用历史", "success"), await l()) : n.receipt = q("未移除", r.reason || "邮箱未移除", "warning");
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
				}), n.receipt = q("状态已更新", `${a.email}：${t[i]}`, "success"), await l();
			}
		});
	}
	async function h(n) {
		let i = W(n);
		await u(async () => {
			r = new AbortController();
			let n = r.signal, a = await e.secret(i, n);
			if (!n.aborted) {
				if (!a.value) throw Error("对应内容为空");
				await t.clipboard(a.value), t.notify("已复制");
			}
		});
	}
	async function g() {
		let i = n.items.map(W);
		i.length && await u(async () => {
			r = new AbortController();
			let a = r.signal, o = await e.secrets(i, a);
			if (a.aborted) return;
			let s = (o.values || []).map((e) => e.value).filter(Boolean).join("\n");
			if (!s) throw Error("当前页没有可复制内容");
			await t.clipboard(s), n.receipt = q("已复制当前页", (o.skipped || []).map((e) => `${e.email}：${e.reason}`).join("\n") || `已复制 ${i.length} 个邮箱素材`, "success"), t.notify("已复制当前页邮箱素材");
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
		togglePage: c,
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
var X = () => ({
	source: "all",
	parent_id: "",
	q: "",
	parent_q: "",
	state: "",
	related_q: "",
	created_from: "",
	created_to: ""
});
function ae(e, t) {
	let n = s({
		items: [],
		total: 0,
		page: 1,
		size: 50,
		filters: X(),
		parentEmail: "",
		selected: /* @__PURE__ */ new Map(),
		loading: !1,
		error: "",
		receipt: null
	}), r = Y(n, async (t, r) => {
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
			Object.assign(n.filters, X()), n.parentEmail = "", n.selected.clear(), n.page = 1, r.schedule();
		},
		scopeParent(e) {
			Object.assign(n.filters, X(), {
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
				await t.clipboard(e.map((e) => e.email).filter(Boolean).join("\n")), n.receipt = q("已复制", `已复制 ${e.length} 条历史子邮箱`, "success");
			} catch (e) {
				n.receipt = q("复制失败", K(e), "danger");
			}
		}
	};
}
// src/features/email/useLocalImport.ts
var Z = {
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
function oe(e, t) {
	let n = s({
		open: !1,
		source: "outlook",
		text: "",
		expiresAt: "",
		preview: null,
		loading: !1,
		busy: !1,
		error: "",
		receipt: null
	}), r = !1, i = !1, a = 0, o, c = "";
	function l() {
		return {
			source: n.source,
			text: n.text,
			...n.source === "generic_api" && n.expiresAt.trim() ? { expires_at: n.expiresAt.trim() } : {}
		};
	}
	function u() {
		a++, o?.abort(), o = void 0, n.loading = !1, n.preview = null, c = "";
	}
	function d(e) {
		Object.assign(n, e), u(), n.error = "";
	}
	async function f() {
		let t = l(), s = JSON.stringify(t);
		if (u(), !r || document.hidden || !n.open || i) return null;
		if (!t.text.trim()) return n.error = "请粘贴邮箱资源", null;
		let d = a;
		o = new AbortController(), n.loading = !0, n.error = "";
		try {
			let i = await e.localPreview(t, o.signal);
			return d !== a || !r || document.hidden || !n.open || s !== JSON.stringify(l()) ? null : (n.preview = i, c = s, i);
		} catch (e) {
			return d === a && !O(e) && (n.error = K(e)), null;
		} finally {
			d === a && (n.loading = !1);
		}
	}
	async function p() {
		if (n.busy || !n.text.trim()) return;
		let r = l(), i = JSON.stringify(r);
		n.busy = !0, n.error = "";
		try {
			let a = n.preview && c === i ? n.preview : await f();
			if (!a || i !== JSON.stringify(l())) return;
			if (!Number(a.new || 0)) {
				n.error = "没有可新增的邮箱资源，请修改内容后重新预览。";
				return;
			}
			let o = await e.localImport(r), s = `邮箱导入：解析 ${o.parsed || 0} 行，已接收 ${o.accepted_count ?? o.inserted ?? 0}，跳过 ${o.skipped || 0}；导入处理中 ${o.pending_sync_count || 0}，无效 ${o.invalid || 0} 行，忽略多余字段 ${o.extra_fields || 0} 个` + (o.invalid_rows || []).map((e) => `\n第 ${e.line} 行：${e.reason}`).join("");
			n.receipt = q("导入已接收", s, "success"), JSON.stringify(l()) === i && (n.text = "", u());
			try {
				await t.onInventoryChanged();
			} catch (e) {
				n.receipt = q("导入已接收", `${s}\n显示刷新失败：${K(e)}`, "warning");
			}
			t.notify("邮箱导入已接收");
		} catch (e) {
			n.error = K(e), n.receipt = e instanceof A && e.status >= 400 && e.status < 500 ? q("导入被拒绝", `导入被拒绝：${K(e)}。已保留原素材。`, "danger") : q("导入结果未确认", `导入响应未确认：${K(e)}。已保留原素材，请先核对库存；不会自动重复提交。`, "danger");
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
			n.open = !0, Z[e] && n.source !== e && d({ source: e });
		},
		close() {
			n.open = !1, u();
		},
		setActive(e) {
			r = e, e || u();
		},
		dispose() {
			i = !0, u();
		}
	};
}
// src/features/email/butlerLabels.ts
var se = [
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
	let r = s({
		open: !1,
		filters: {
			provider: "icloud_hme",
			count: 10
		},
		providers: [...se],
		preview: null,
		request: null,
		batch: null,
		busy: !1,
		polling: !1,
		previewing: !1,
		error: "",
		storageError: !1,
		resumePending: null
	}), i = !1, a = !1, o = 0, c = 0, l, u, d, f, p, m = null, h = -1, g = 0, _ = null, v = n.now || Date.now, y = () => i && !document.hidden && !a;
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
		o++, l?.abort(), d?.abort(), clearTimeout(f), r.preview = null, r.previewing = !1;
	}
	function C() {
		x(), c++, u?.abort(), u = void 0, m = null, r.polling = !1, clearTimeout(p);
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
		clearTimeout(p), y() && r.batch && r.batch.status !== "cancelled" && (w.value || r.resumePending) && (p = setTimeout(() => void H(), 2e3));
	}
	function P() {
		let e = Number(r.batch?.imported || 0);
		!e || e === h || _ || w.value && h >= 0 && v() - g < 15e3 || (_ = Promise.resolve().then(() => t.onInventoryChanged()).then(() => {
			h = e;
		}, (e) => {
			r.error = `邮箱已导入，但显示未完全刷新：${K(e)}`;
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
		r.resumePending && (pe(i.status) || me(i) !== r.resumePending) && (r.resumePending = null), r.batch = i, i.status === "cancelled" && (r.resumePending = null, c++, u?.abort(), r.polling = !1, clearTimeout(p));
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
		if (x(), r.error = "", !se.some((e) => e.value === t.provider)) {
			r.error = "请选择支持的邮箱来源";
			return;
		}
		if (!Number.isSafeInteger(t.count) || t.count < 1) {
			r.error = "数量须为大于0的整数";
			return;
		}
		let n = o;
		l = new AbortController(), r.previewing = !0;
		try {
			let i = await e.butlerPreview(t, l.signal);
			if (n !== o || !y() || !r.open || JSON.stringify(t) !== JSON.stringify(r.filters)) return;
			if (!i.preview_token) throw Error("可用数量查询未返回有效结果，请刷新数量");
			r.preview = {
				...i,
				filters: t
			}, i.selected || (r.error = "当前没有可用于 OpenAI 的邮箱，请在 Butler 按目标服务核对来源状态、历史占用和冷却限制后刷新数量。");
		} catch (e) {
			n === o && !O(e) && (r.error = `查询可用数量失败：${K(e)}`);
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
			await H();
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
			t === o && !O(e) && (r.error = `读取导入选项失败：${K(e)}`);
		}
		t === o && await I();
	}
	function z() {
		r.open = !1, x();
	}
	async function B() {
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
				n.storage.removeItem(de), r.request = null, x(), r.error = `导入尚未开始：${K(e)}。请重新预览。`;
			} catch {
				r.error = "导入尚未开始，但原记录暂未清除；请恢复浏览器存储后重试原请求。";
			}
			else r.error = `导入请求失败：${K(e)}。请${r.batch ? "继续原批次" : "重试原请求"}恢复，已保留原编号。`;
		} finally {
			r.busy = !1, N();
		}
	}
	async function V() {
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
				await B();
			}
		}
	}
	async function H() {
		if (m) return m;
		if (!y() || !r.batch || r.busy) return;
		clearTimeout(p);
		let t = ++c, n = r.batch.batch_id;
		u = new AbortController(), r.polling = !0;
		let i = (async () => {
			try {
				let i = await e.batch(n, u.signal);
				if (t !== c || !y() || r.batch?.batch_id !== n) return;
				r.error = "", F(i);
			} catch (e) {
				t === c && !O(e) && (r.error = `暂时无法读取原批次：${K(e)}。请重开此窗口恢复查看。`);
			} finally {
				t === c && (r.polling = !1, m = null, N());
			}
		})();
		m = i, await i;
	}
	async function ee() {
		if (r.busy || !D.value || !r.batch) return;
		let t = r.batch.batch_id;
		r.busy = !0, r.error = "";
		try {
			let n = await e.cancelBatch(t);
			if (F(n), n.batch.status !== "cancelled" && !fe(n.batch.status)) throw Error("服务端未返回终止回执");
			c++, u?.abort(), m = null, r.polling = !1;
		} catch (e) {
			r.error = `终止请求失败：${K(e)}。已保留原批次，请重试终止或查看原批次状态。`;
		} finally {
			r.busy = !1, N();
		}
	}
	async function U() {
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
	function W(e) {
		if (e.key === "turb.butler-import.v1" && e.newValue && r.batch) try {
			let t = JSON.parse(e.newValue);
			if (t.batch_id !== r.batch.batch_id || t.batch_status !== "cancelled") return;
			c++, u?.abort(), m = null, clearTimeout(p), r.polling = !1, r.resumePending = null, r.batch = {
				...r.batch,
				status: "cancelled",
				can_retry: !1,
				can_cancel: !1
			};
		} catch {}
	}
	return window.addEventListener("storage", W), {
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
		apply: V,
		retry: B,
		poll: H,
		cancel: ee,
		reset: U,
		setActive(e) {
			a || e === i || (i = e, e ? r.batch ? H() : r.open && !r.request && R() : C());
		},
		dispose() {
			a = !0, C(), window.removeEventListener("storage", W);
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
}, De = { class: "em-import-prompt" }, Oe = { class: "em-actions" }, ke = /* @__PURE__ */ t({
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
	setup(t, { emit: i }) {
		let a = t, s = i, c = (e) => e === !0 || e === "true", l = (e) => e.kind === "local_pool" || (e.default_visible === void 0 ? c(e.enabled) || c(e.dependency) : c(e.default_visible)), d = S(() => a.sources.filter((e) => !l(e)).length), p = S(() => a.expanded ? a.sources : a.sources.filter(l)), m = (e) => e.kind !== "on_demand" && !!V[e.source] && e.source !== "all";
		function v(e) {
			return e.kind === "local_pool" ? "本地库存" : c(e.enabled) ? "已启用" : c(e.dependency) ? "收码依赖" : c(e.history_available) || Number(e.total) > 0 ? "历史/已停用" : "未启用";
		}
		return (i, a) => (n(), E("section", {
			class: "em-overview",
			"aria-label": "邮箱资源平台",
			"aria-busy": t.loading
		}, [
			_("div", _e, [a[5] ||= _("div", null, [_("h2", null, "本地邮箱库存"), _("p", null, "仅从本地库存领取邮箱，用完后请从 Butler 或其他来源手动导入。")], -1), _("button", {
				class: "em-button",
				disabled: t.loading,
				onClick: a[0] ||= (e) => s("refresh")
			}, h(t.loading ? "刷新中…" : "刷新资源"), 9, ve)]),
			t.error ? (n(), E("p", ye, [D(h(t.error) + " ", 1), _("button", {
				class: "em-button",
				onClick: a[1] ||= (e) => s("refresh")
			}, "重试")])) : u("", !0),
			_("div", be, [_("span", null, h(d.value ? "默认显示已启用服务和当前收码依赖" : "当前没有未启用的邮箱服务"), 1), d.value ? (n(), E("button", {
				key: 0,
				class: "em-button",
				"aria-expanded": t.expanded,
				onClick: a[2] ||= (e) => s("expand")
			}, h(t.expanded ? "隐藏未启用" : `显示未启用（${d.value}）`), 9, xe)) : u("", !0)]),
			_("div", Se, [(n(!0), E(f, null, o(p.value, (t) => (n(), g(e(m(t) ? "button" : "article"), {
				key: t.source,
				type: m(t) ? "button" : void 0,
				class: x(["em-source-card", { "is-clickable": m(t) }]),
				onClick: (e) => m(t) && s("source", t.source)
			}, {
				default: r(() => [
					_("div", Ce, [_("strong", null, h(t.label || T(V)[t.source] || t.source), 1), _("span", null, h(v(t)), 1)]),
					_("strong", we, h(t.kind === "on_demand" ? "按需" : t.available ?? 0), 1),
					_("p", null, h(t.kind === "on_demand" ? "运行时领取 / 创建" : `总数 ${t.total || 0} · 已用 ${t.used || 0} · 失败 ${t.failed || 0} · 停用 ${t.disabled || 0}`), 1),
					t.dependency_reason ? (n(), E("small", Te, h(t.dependency_reason), 1)) : u("", !0)
				]),
				_: 2
			}, 1032, [
				"type",
				"class",
				"onClick"
			]))), 128))]),
			p.value.length ? u("", !0) : (n(), E("p", Ee, h(t.loading ? "正在加载邮箱资源…" : "暂无已启用邮箱服务，可显示未启用的服务。"), 1)),
			_("section", De, [a[6] ||= _("div", null, [
				_("span", null, "Email Butler"),
				_("h3", null, "手动补充本地库存"),
				_("p", null, "从 Butler 选择 iCloud HME 母邮箱或子邮箱导入，也可粘贴已有完整地址。注册任务仅领取本地库存。")
			], -1), _("div", Oe, [_("button", {
				class: "em-button em-primary",
				"data-butler-opener": "",
				onClick: a[3] ||= (e) => s("butlerImport")
			}, h(t.butlerLabel), 1), _("button", {
				class: "em-button",
				onClick: a[4] ||= (e) => s("localImport")
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
}, Ie = ["aria-label", "value"], Le = { class: "list-filter-actions" }, Q = /* @__PURE__ */ t({
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
	setup(e, { emit: t }) {
		let a = e, s = t, c = m(!1);
		i(() => a.active, (e) => {
			e || (c.value = !1);
		});
		let d = S(() => a.value !== (a.emptyValue || "") || !!a.endValue), p = !1;
		function v(e) {
			p = !1, s("change", e.target.value);
		}
		function y(e) {
			p || s("change", e.target.value);
		}
		return (t, i) => (n(), g(M, {
			label: e.label,
			active: d.value,
			summary: [e.value, e.endValue].filter(Boolean).join(" 至 "),
			open: c.value,
			"onUpdate:open": i[4] ||= (e) => c.value = e
		}, {
			default: r(() => [
				_("label", Ae, [D(h(e.label) + " ", 1), e.options ? (n(), E("select", {
					key: 0,
					"aria-label": e.label,
					value: e.value,
					onChange: i[0] ||= (e) => s("change", e.target.value)
				}, [_("option", { value: e.emptyValue || "" }, "全部", 8, Me), (n(!0), E(f, null, o(e.options, (e) => (n(), E("option", {
					key: e.value,
					value: e.value
				}, h(e.label) + h(e.count === void 0 ? "" : ` (${e.count})`), 9, Ne))), 128))], 40, je)) : (n(), E("input", {
					key: 1,
					"aria-label": e.label,
					type: e.type === "date" || e.type === "range" ? "date" : "search",
					multiple: !1,
					value: e.value,
					onCompositionstart: i[1] ||= (e) => l(p) ? p.value = !0 : p = !0,
					onCompositionend: v,
					onInput: y
				}, null, 40, Pe))]),
				e.type === "range" ? (n(), E("label", Fe, [i[5] ||= D("结束日期", -1), _("input", {
					type: "date",
					"aria-label": `${e.label}结束`,
					value: e.endValue,
					onInput: i[2] ||= (e) => s("end", e.target.value)
				}, null, 40, Ie)])) : u("", !0),
				_("div", Le, [_("button", {
					type: "button",
					onClick: i[3] ||= (t) => {
						s("change", e.emptyValue || ""), e.type === "range" && s("end", "");
					}
				}, "清除条件")])
			]),
			_: 1
		}, 8, [
			"label",
			"active",
			"summary",
			"open"
		]));
	}
}), Re = {
	key: 0,
	class: "em-receipt",
	role: "status"
}, ze = /* @__PURE__ */ t({
	__name: "EmailReceipt",
	props: { receipt: {} },
	setup(e) {
		return (t, i) => e.receipt ? (n(), E("div", Re, [c(P, {
			label: e.receipt.label,
			title: e.receipt.detail,
			tone: e.receipt.tone
		}, {
			details: r(() => [D(h(e.receipt.detail), 1)]),
			_: 1
		}, 8, [
			"label",
			"title",
			"tone"
		])])) : u("", !0);
	}
}), Be = ["aria-label"], $ = /* @__PURE__ */ t({
	__name: "EmailResizeGrip",
	props: {
		index: {},
		columns: {},
		label: {}
	},
	setup(e) {
		return (t, r) => (n(), E("button", {
			class: "em-resize",
			"aria-label": `调整${e.label}第 ${e.index + 1} 列宽度`,
			onPointerdown: r[0] ||= (t) => e.columns.resize(e.index, t),
			onKeydown: [r[1] ||= d(b((t) => e.columns.resizeWithKeyboard(e.index, -10), ["prevent"]), ["left"]), r[2] ||= d(b((t) => e.columns.resizeWithKeyboard(e.index, 10), ["prevent"]), ["right"])]
		}, null, 40, Be));
	}
}), Ve = ["aria-busy"], He = { class: "em-toolbar" }, Ue = { class: "em-actions" }, We = ["disabled"], Ge = ["disabled"], Ke = ["disabled"], qe = ["disabled"], Je = ["disabled"], Ye = { class: "em-actions em-inventory-utilities" }, Xe = ["disabled"], Ze = {
	key: 0,
	class: "em-error",
	role: "alert"
}, Qe = {
	key: 1,
	class: "em-error",
	role: "alert"
}, $e = [
	"checked",
	"indeterminate",
	"disabled"
], et = [
	"aria-label",
	"checked",
	"onChange"
], tt = { class: "em-align-start" }, nt = [
	"aria-label",
	"title",
	"onClick"
], rt = { class: "em-align-start" }, it = { class: "em-row-actions" }, at = ["disabled", "onClick"], ot = ["disabled", "onClick"], st = {
	key: 0,
	class: "em-more"
}, ct = ["aria-label"], lt = ["disabled", "onClick"], ut = { key: 0 }, dt = {
	colspan: "9",
	class: "em-empty",
	role: "status"
}, ft = /* @__PURE__ */ t({
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
		let s = e, l = t, d = s.owner.state, v = m(), b = !1;
		i([
			() => d.page,
			() => d.size,
			() => Object.values(d.filters)
		], () => {
			b = !0;
		}), i(() => d.items, () => {
			b && v.value && (v.value.scrollTop = 0, b = !1);
		}, { flush: "post" });
		let C = R({
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
		}), O = S(() => d.items.filter((e) => d.selected.has(G(e))).length), k = S(() => Object.entries(d.filters).filter(([e, t]) => t && (e !== "source" || t !== "all")).map(([e, t]) => ({
			key: e,
			label: `${{
				q: "邮箱",
				source: "类型",
				status: "状态",
				used_date: "最近使用日期"
			}[e]}：${e === "source" ? V[t] || t : e === "status" && H[t] || t}`,
			removeLabel: `移除${e}筛选`
		}))), A = S(() => Object.entries(V).filter(([e]) => e !== "all").map(([e, t]) => ({
			value: e,
			label: t,
			count: d.facets.source?.find((t) => t.value === e)?.count
		}))), M = S(() => [.../* @__PURE__ */ new Set([
			...Object.keys(H),
			...(d.facets.status || []).map((e) => e.value),
			d.filters.status
		])].filter(Boolean).map((e) => ({
			value: e,
			label: H[e] || e,
			count: d.facets.status?.find((t) => t.value === e)?.count
		}))), z = (e) => d.parents.find((t) => t.source === e.source && String(t.parent_id) === String(e.id) && Number(t.child_count) > 0), B = (e) => e.service_sync_error || e.note || e.disabled_reason || "";
		function U(e) {
			s.owner.updateFilters({ [e]: e === "source" ? "all" : "" });
		}
		function W(e) {
			return e.last_activity_at || e.used_at || e.updated_at || e.created_at;
		}
		function K(e) {
			return `${e.used_at ? "最近使用" : e.last_activity_at ? "最近更新" : "导入时间"}：${I(W(e))}${e.synced_at ? `\n同步：${I(e.synced_at)}` : ""}`;
		}
		return (t, i) => (n(), E("section", {
			class: "em-list em-inventory",
			"aria-label": "邮箱池",
			"aria-busy": T(d).loading
		}, [
			_("div", He, [
				_("div", Ue, [
					_("span", null, h(T(d).selected.size ? `已选 ${T(d).selected.size} 个邮箱` : "选择邮箱后批量操作"), 1),
					T(d).selected.size ? (n(), E(f, { key: 0 }, [
						_("button", {
							class: "em-button",
							disabled: T(d).busy,
							onClick: i[0] ||= (t) => e.owner.bulkStatus("available")
						}, "标记未使用", 8, We),
						_("button", {
							class: "em-button",
							disabled: T(d).busy,
							onClick: i[1] ||= (t) => e.owner.bulkStatus("disabled")
						}, "停用选中", 8, Ge),
						_("button", {
							class: "em-button",
							disabled: T(d).busy,
							onClick: i[2] ||= (t) => e.owner.bulkStatus("failed")
						}, "标失败", 8, Ke),
						_("button", {
							class: "em-button em-danger",
							disabled: T(d).busy,
							onClick: i[3] ||= (t) => e.owner.bulkDelete()
						}, "删除选中", 8, qe)
					], 64)) : u("", !0),
					_("button", {
						class: "em-button",
						disabled: T(d).busy || !T(d).items.length,
						onClick: i[4] ||= (t) => e.owner.copyPage()
					}, "复制当前页", 8, Je),
					_("button", {
						class: "em-button em-primary",
						onClick: i[5] ||= (e) => l("localImport")
					}, "导入邮箱"),
					_("button", {
						class: "em-button",
						"data-butler-opener": "",
						onClick: i[6] ||= (e) => l("butlerImport")
					}, h(e.butlerLabel), 1)
				]),
				c(N, {
					items: k.value,
					onRemove: U
				}, null, 8, ["items"]),
				_("div", Ye, [_("button", {
					class: "em-button",
					onClick: i[7] ||= (...e) => T(C).resetColumns && T(C).resetColumns(...e)
				}, "恢复列宽"), _("button", {
					class: "em-button",
					disabled: T(d).loading,
					onClick: i[8] ||= (t) => e.owner.refresh()
				}, "刷新", 8, Xe)])
			]),
			T(d).error ? (n(), E("div", Ze, [D(h(T(d).error) + " ", 1), _("button", {
				class: "em-button",
				onClick: i[9] ||= (t) => e.owner.refresh()
			}, "重试")])) : u("", !0),
			T(d).summaryError ? (n(), E("div", Qe, [D(h(T(d).summaryError) + " ", 1), _("button", {
				class: "em-button",
				onClick: i[10] ||= (t) => e.owner.refreshDerivationSummary()
			}, "重试")])) : u("", !0),
			c(ze, { receipt: T(d).receipt }, null, 8, ["receipt"]),
			_("div", {
				ref_key: "tableViewport",
				ref: v,
				class: "em-table-wrap",
				role: "region",
				tabindex: "0",
				"aria-label": "邮箱列表，可滚动"
			}, [_("table", {
				class: "em-table",
				style: p({ width: `${T(C).total.value}px` })
			}, [
				_("colgroup", null, [(n(!0), E(f, null, o(T(C).widths.value, (e, t) => (n(), E("col", {
					key: t,
					style: p({ width: `${e}px` })
				}, null, 4))), 128))]),
				_("thead", null, [_("tr", null, [
					_("th", null, [_("input", {
						type: "checkbox",
						"aria-label": "全选当前页邮箱资源",
						checked: !!T(d).items.length && O.value === T(d).items.length,
						indeterminate: O.value > 0 && O.value < T(d).items.length,
						disabled: !T(d).items.length,
						onChange: i[11] ||= (t) => e.owner.togglePage(t.target.checked)
					}, null, 40, $e), c($, {
						index: 0,
						columns: T(C),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "邮箱",
						value: T(d).filters.q,
						active: e.active,
						onChange: i[12] ||= (t) => e.owner.updateFilters({ q: t })
					}, null, 8, ["value", "active"]), c($, {
						index: 1,
						columns: T(C),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "类型",
						value: T(d).filters.source,
						"empty-value": "all",
						options: A.value,
						active: e.active,
						onChange: i[13] ||= (t) => e.owner.updateFilters({ source: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), c($, {
						index: 2,
						columns: T(C),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "状态",
						value: T(d).filters.status,
						options: M.value,
						active: e.active,
						onChange: i[14] ||= (t) => e.owner.updateFilters({ status: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), c($, {
						index: 3,
						columns: T(C),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					_("th", null, [i[17] ||= D("使用情况", -1), c($, {
						index: 4,
						columns: T(C),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					_("th", null, [i[18] ||= D("凭证配置", -1), c($, {
						index: 5,
						columns: T(C),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "最近活动",
						type: "date",
						value: T(d).filters.used_date,
						active: e.active,
						onChange: i[15] ||= (t) => e.owner.updateFilters({ used_date: t })
					}, null, 8, ["value", "active"]), c($, {
						index: 6,
						columns: T(C),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					_("th", null, [i[19] ||= D("备注 / 原因", -1), c($, {
						index: 7,
						columns: T(C),
						label: "邮箱"
					}, null, 8, ["columns"])]),
					_("th", null, [
						i[20] ||= D("操作 ", -1),
						_("button", {
							class: "em-text-button",
							onClick: i[16] ||= (t) => e.owner.resetFilters()
						}, "清筛"),
						c($, {
							index: 8,
							columns: T(C),
							label: "邮箱"
						}, null, 8, ["columns"])
					])
				])]),
				_("tbody", null, [(n(!0), E(f, null, o(T(d).items, (t) => (n(), E("tr", {
					key: T(G)(t),
					class: x({ "is-selected": T(d).selected.has(T(G)(t)) })
				}, [
					_("td", null, [_("input", {
						type: "checkbox",
						"aria-label": `选择邮箱 ${t.email}`,
						checked: T(d).selected.has(T(G)(t)),
						onChange: (n) => e.owner.toggle(t, n.target.checked)
					}, null, 40, et)]),
					_("td", tt, [z(t) ? (n(), E("button", {
						key: 0,
						class: "em-cell-button",
						"aria-label": `查看 ${t.email} 的历史子地址`,
						title: [
							t.email,
							t.remote_label,
							`历史子地址 ${z(t)?.child_count} 个`
						].filter(Boolean).join(" · "),
						onClick: (e) => l("parent", t)
					}, [c(j, {
						text: t.email,
						secondary: `查看历史 · ${z(t)?.child_count} 个`
					}, null, 8, ["text", "secondary"])], 8, nt)) : (n(), g(j, {
						key: 1,
						text: t.email,
						secondary: t.remote_label || void 0
					}, null, 8, ["text", "secondary"]))]),
					_("td", null, [c(j, { text: T(V)[t.source] || t.source }, null, 8, ["text"])]),
					_("td", null, [c(j, { text: T(H)[t.status || ""] || t.status || "状态记录缺失" }, null, 8, ["text"])]),
					_("td", null, [c(j, {
						text: T(ee)[t.usage_state || t.status || ""] || t.usage_state || t.status || "状态记录缺失",
						secondary: t.usage_state === "bound" && t.registered_account_id ? `账号 #${t.registered_account_id}` : void 0
					}, null, 8, ["text", "secondary"])]),
					_("td", null, [c(P, {
						label: T(J)(t).text,
						title: T(J)(t).detail
					}, {
						details: r(() => [D(h(T(J)(t).detail), 1)]),
						_: 2
					}, 1032, ["label", "title"])]),
					_("td", null, [c(P, y({ ref_for: !0 }, {
						label: T(L)(W(t)).text,
						secondary: T(L)(W(t)).secondary
					}, { title: K(t) }), {
						details: r(() => [D(h(K(t)), 1)]),
						_: 2
					}, 1040, ["title"])]),
					_("td", rt, [B(t) ? (n(), g(P, {
						key: 0,
						"data-email-note": "",
						label: T(re)(t),
						title: B(t),
						tone: t.service_sync_error ? "danger" : "neutral"
					}, {
						details: r(() => [D(h(B(t)), 1)]),
						_: 2
					}, 1032, [
						"label",
						"title",
						"tone"
					])) : (n(), g(j, {
						key: 1,
						text: "—"
					}))]),
					_("td", null, [_("div", it, [
						_("button", {
							class: "em-button",
							disabled: T(d).busy,
							onClick: (n) => e.owner.copyRow(t)
						}, "复制素材", 8, at),
						_("button", {
							class: "em-button em-danger",
							disabled: T(d).busy,
							onClick: (n) => e.owner.rowAction(t, "delete")
						}, "删除", 8, ot),
						["replaced", "pending_sync"].includes(t.status || "") ? u("", !0) : (n(), E("details", st, [_("summary", { "aria-label": `更多操作 ${t.email}` }, "更多", 8, ct), _("div", null, [(n(), E(f, null, o({
							available: "恢复可用",
							disabled: "停用",
							failed: "标失败"
						}, (n, r) => a(_("button", {
							key: r,
							class: "em-button",
							disabled: T(d).busy,
							onClick: (n) => e.owner.rowAction(t, r)
						}, h(n), 9, lt), [[w, r !== t.status]])), 64))])]))
					])])
				], 2))), 128)), T(d).items.length ? u("", !0) : (n(), E("tr", ut, [_("td", dt, h(T(d).loading ? "正在加载邮箱资源…" : T(d).error ? "邮箱资源加载失败" : "暂无邮箱资源，调整筛选条件或导入新的邮箱资源。"), 1)]))])
			], 4)], 512),
			c(F, {
				compact: "",
				page: T(d).page,
				size: T(d).size,
				total: T(d).total,
				busy: T(d).loading,
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
		], 8, Ve));
	}
}), pt = ["aria-busy"], mt = { class: "em-toolbar" }, ht = { class: "em-actions" }, gt = ["disabled"], _t = {
	class: "em-count-row",
	"data-email-count-row": ""
}, vt = {
	key: 0,
	class: "em-error",
	role: "alert"
}, yt = { class: "em-table-wrap" }, bt = [
	"checked",
	"indeterminate",
	"disabled"
], xt = [
	"aria-label",
	"checked",
	"onChange"
], St = { class: "em-align-start" }, Ct = { class: "em-align-start" }, wt = { key: 0 }, Tt = {
	colspan: "8",
	class: "em-empty",
	role: "status"
}, Et = /* @__PURE__ */ t({
	__name: "EmailHistory",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(e) {
		let t = e, r = t.owner.state, i = R({
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
		}), a = S(() => r.items.filter((e) => r.selected.has(String(e.id))).length), s = [{
			value: "icloud_hide",
			label: "iCloud 隐藏邮箱"
		}, {
			value: "outlook",
			label: "Outlook"
		}], l = Object.entries(U).map(([e, t]) => ({
			value: e,
			label: t
		})), d = S(() => Object.entries(r.filters).filter(([e, t]) => t && (e !== "source" || t !== "all")).map(([e, t]) => ({
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
			}[e]}：${e === "source" ? V[t] || t : e === "state" ? U[t] || t : e === "parent_id" ? r.parentEmail || `#${t}` : t}`,
			removeLabel: `移除${e}筛选`
		})));
		function m(e) {
			e === "parent_id" ? t.owner.clearParent() : t.owner.updateFilters({ [e]: e === "source" ? "all" : "" });
		}
		return (t, g) => (n(), E("section", {
			class: "em-list",
			"aria-label": "历史子邮箱",
			"aria-busy": T(r).loading
		}, [
			g[13] ||= _("p", { class: "em-help" }, "子邮箱由你手动准备并导入本地库存；此处可查看、筛选和复制已有记录，Turb 不会自动生成。", -1),
			_("div", mt, [_("div", ht, [_("span", null, h(T(r).selected.size ? `已选 ${T(r).selected.size} 条历史记录` : "可筛选并复制历史子邮箱"), 1), _("button", {
				class: "em-button",
				disabled: !T(r).items.length && !T(r).selected.size,
				onClick: g[0] ||= (t) => e.owner.copy()
			}, h(T(r).selected.size ? "复制选中" : "复制当前页"), 9, gt)]), _("button", {
				class: "em-button",
				onClick: g[1] ||= (...e) => T(i).resetColumns && T(i).resetColumns(...e)
			}, "恢复列宽")]),
			_("div", _t, [
				_("strong", null, h(T(r).total) + " 条历史记录", 1),
				_("span", null, "当前页 " + h(T(r).items.length) + " 条", 1),
				c(N, {
					items: d.value,
					onRemove: m
				}, null, 8, ["items"])
			]),
			T(r).error ? (n(), E("div", vt, [D(h(T(r).error) + " ", 1), _("button", {
				class: "em-button",
				onClick: g[2] ||= (t) => e.owner.refresh()
			}, "重试")])) : u("", !0),
			c(ze, { receipt: T(r).receipt }, null, 8, ["receipt"]),
			_("div", yt, [_("table", {
				class: "em-table",
				style: p({ width: `${T(i).total.value}px` })
			}, [
				_("colgroup", null, [(n(!0), E(f, null, o(T(i).widths.value, (e, t) => (n(), E("col", {
					key: t,
					style: p({ width: `${e}px` })
				}, null, 4))), 128))]),
				_("thead", null, [_("tr", null, [
					_("th", null, [_("input", {
						type: "checkbox",
						"aria-label": "全选当前页子邮箱",
						checked: !!T(r).items.length && a.value === T(r).items.length,
						indeterminate: a.value > 0 && a.value < T(r).items.length,
						disabled: !T(r).items.length,
						onChange: g[3] ||= (t) => e.owner.togglePage(t.target.checked)
					}, null, 40, bt), c($, {
						index: 0,
						columns: T(i),
						label: "历史"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "子邮箱",
						value: T(r).filters.q,
						active: e.active,
						onChange: g[4] ||= (t) => e.owner.updateFilters({ q: t })
					}, null, 8, ["value", "active"]), c($, {
						index: 1,
						columns: T(i),
						label: "历史"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "母邮箱",
						value: T(r).filters.parent_q,
						active: e.active,
						onChange: g[5] ||= (t) => e.owner.updateFilters({ parent_q: t })
					}, null, 8, ["value", "active"]), c($, {
						index: 2,
						columns: T(i),
						label: "历史"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "来源",
						value: T(r).filters.source,
						"empty-value": "all",
						options: s,
						active: e.active,
						onChange: g[6] ||= (t) => e.owner.updateFilters({ source: t })
					}, null, 8, ["value", "active"]), c($, {
						index: 3,
						columns: T(i),
						label: "历史"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "状态",
						value: T(r).filters.state,
						options: T(l),
						active: e.active,
						onChange: g[7] ||= (t) => e.owner.updateFilters({ state: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), c($, {
						index: 4,
						columns: T(i),
						label: "历史"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "关联账号 / 任务",
						value: T(r).filters.related_q,
						active: e.active,
						onChange: g[8] ||= (t) => e.owner.updateFilters({ related_q: t })
					}, null, 8, ["value", "active"]), c($, {
						index: 5,
						columns: T(i),
						label: "历史"
					}, null, 8, ["columns"])]),
					_("th", null, [c(Q, {
						label: "生成时间",
						type: "range",
						value: T(r).filters.created_from,
						"end-value": T(r).filters.created_to,
						active: e.active,
						onChange: g[9] ||= (t) => e.owner.updateFilters({ created_from: t }),
						onEnd: g[10] ||= (t) => e.owner.updateFilters({ created_to: t })
					}, null, 8, [
						"value",
						"end-value",
						"active"
					]), c($, {
						index: 6,
						columns: T(i),
						label: "历史"
					}, null, 8, ["columns"])]),
					_("th", null, [
						g[12] ||= D("操作 ", -1),
						_("button", {
							class: "em-text-button",
							onClick: g[11] ||= (t) => e.owner.resetFilters()
						}, "清筛"),
						c($, {
							index: 7,
							columns: T(i),
							label: "历史"
						}, null, 8, ["columns"])
					])
				])]),
				_("tbody", null, [(n(!0), E(f, null, o(T(r).items, (t) => (n(), E("tr", {
					key: String(t.id),
					class: x({ "is-selected": T(r).selected.has(String(t.id)) })
				}, [
					_("td", null, [_("input", {
						type: "checkbox",
						"aria-label": `选择历史子邮箱 ${t.email}`,
						checked: T(r).selected.has(String(t.id)),
						onChange: (n) => e.owner.toggle(t, n.target.checked)
					}, null, 40, xt)]),
					_("td", St, [c(j, { text: t.email }, null, 8, ["text"])]),
					_("td", Ct, [c(j, {
						text: t.parent_email || "—",
						secondary: `母资源 #${t.parent_id || "—"}`
					}, null, 8, ["text", "secondary"])]),
					_("td", null, [c(j, { text: T(V)[t.source] || t.source }, null, 8, ["text"])]),
					_("td", null, [c(j, { text: T(U)[t.state || ""] || t.state || "状态记录缺失" }, null, 8, ["text"])]),
					_("td", null, [c(j, { text: T(ne)(t) }, null, 8, ["text"])]),
					_("td", null, [c(j, y({ ref_for: !0 }, T(L)(t.created_at)), null, 16)]),
					_("td", null, [c(j, { text: "只读" })])
				], 2))), 128)), T(r).items.length ? u("", !0) : (n(), E("tr", wt, [_("td", Tt, h(T(r).loading ? "正在读取历史子邮箱…" : T(r).error ? "子邮箱历史加载失败" : "当前筛选下没有历史子地址，请从 Email Butler 等来源手动准备邮箱，再导入本地库存。"), 1)]))])
			], 4)]),
			c(F, {
				page: T(r).page,
				size: T(r).size,
				total: T(r).total,
				busy: T(r).loading,
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
		], 8, pt));
	}
}), Dt = ["aria-busy"], Ot = { class: "em-dialog-head" }, kt = { class: "em-dialog-body" }, At = {
	key: 0,
	class: "em-error",
	role: "alert"
}, jt = { class: "em-field" }, Mt = ["value", "disabled"], Nt = ["value"], Pt = { class: "em-field" }, Ft = [
	"value",
	"placeholder",
	"disabled"
], It = { class: "em-help" }, Lt = {
	key: 1,
	class: "em-field"
}, Rt = ["value", "disabled"], zt = {
	key: 2,
	class: "em-preview",
	"aria-label": "导入前检查"
}, Bt = { class: "em-stats" }, Vt = { key: 0 }, Ht = { key: 1 }, Ut = { class: "em-dialog-foot" }, Wt = ["disabled"], Gt = ["disabled"], Kt = /* @__PURE__ */ t({
	__name: "EmailLocalImport",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(e) {
		let t = e, r = t.owner.state, i = m();
		return z(i, () => r.open, () => t.active), (t, a) => (n(), E("dialog", {
			ref_key: "dialog",
			ref: i,
			class: "em-dialog",
			"data-email-local-import": "",
			"aria-labelledby": "emailLocalImportTitle",
			"aria-busy": T(r).busy || T(r).loading,
			onCancel: a[7] ||= b((t) => e.owner.close(), ["prevent"]),
			onClick: a[8] ||= (t) => t.target === i.value && e.owner.close()
		}, [
			_("div", Ot, [a[9] ||= _("div", null, [_("h3", { id: "emailLocalImportTitle" }, "导入邮箱资源"), _("p", null, "手动补充本地库存；Outlook 和通用 API 保留原格式，Butler 类型每行粘贴一个完整 iCloud HME 地址。")], -1), _("button", {
				class: "em-button",
				"aria-label": "关闭邮箱导入",
				onClick: a[0] ||= (t) => e.owner.close()
			}, "关闭")]),
			_("div", kt, [
				c(ze, { receipt: T(r).receipt }, null, 8, ["receipt"]),
				T(r).error ? (n(), E("p", At, h(T(r).error), 1)) : u("", !0),
				_("label", jt, [a[10] ||= D("导入类型", -1), _("select", {
					"aria-label": "导入类型",
					value: T(r).source,
					disabled: T(r).busy,
					onChange: a[1] ||= (t) => e.owner.update({ source: t.target.value })
				}, [(n(!0), E(f, null, o(T(Z), (e, t) => (n(), E("option", {
					key: t,
					value: t
				}, h(e.label), 9, Nt))), 128))], 40, Mt)]),
				a[16] ||= _("p", { class: "em-help" }, "注册任务只领取本地可用库存；Butler 导入会交接原地址，不自动生成邮箱。", -1),
				_("label", Pt, [a[11] ||= D("邮箱资源", -1), _("textarea", {
					"aria-label": "邮箱资源",
					value: T(r).text,
					placeholder: T(Z)[T(r).source].placeholder,
					disabled: T(r).busy,
					onInput: a[2] ||= (t) => e.owner.update({ text: t.target.value })
				}, null, 40, Ft)]),
				_("p", It, h(T(Z)[T(r).source].hint), 1),
				T(r).source === "generic_api" ? (n(), E("label", Lt, [
					a[12] ||= D("批次有效期（可选）", -1),
					_("input", {
						"aria-label": "批次有效期",
						type: "text",
						value: T(r).expiresAt,
						disabled: T(r).busy,
						placeholder: "2026-12-01T12:00:00+08:00",
						onInput: a[3] ||= (t) => e.owner.update({ expiresAt: t.target.value })
					}, null, 40, Rt),
					a[13] ||= _("small", null, "只补充未在第三字段填写有效期的通用 API 邮箱；留空保留旧两段格式，不会推算有效期。", -1)
				])) : u("", !0),
				T(r).preview ? (n(), E("section", zt, [
					a[15] ||= _("strong", null, "导入前检查", -1),
					_("div", Bt, [(n(!0), E(f, null, o([
						["输入行数", T(r).preview.total_lines],
						["可解析", T(r).preview.valid],
						["可新增", T(r).preview.new],
						["已存在", T(r).preview.existing],
						["输入重复", T(r).preview.duplicate_in_input],
						["无效行", T(r).preview.invalid]
					], (e) => (n(), E("div", { key: String(e[0]) }, [_("strong", null, h(e[1] || 0), 1), _("span", null, h(e[0]), 1)]))), 128))]),
					T(r).preview.extra_fields ? (n(), E("p", Vt, "检测到 " + h(T(r).preview.extra_fields) + " 个多余字段，导入时会忽略。", 1)) : u("", !0),
					T(r).preview.invalid_rows?.length ? (n(), E("details", Ht, [a[14] ||= _("summary", null, "无效行详情", -1), (n(!0), E(f, null, o(T(r).preview.invalid_rows, (e) => (n(), E("p", { key: e.line }, "第 " + h(e.line) + " 行：" + h(e.reason), 1))), 128))])) : u("", !0)
				])) : u("", !0)
			]),
			_("div", Ut, [
				_("button", {
					class: "em-button",
					onClick: a[4] ||= (t) => e.owner.close()
				}, "取消"),
				_("button", {
					class: "em-button",
					disabled: T(r).loading || T(r).busy,
					onClick: a[5] ||= (t) => e.owner.preview()
				}, h(T(r).loading ? "解析中…" : "解析预览"), 9, Wt),
				_("button", {
					class: "em-button em-primary",
					"data-local-submit": "",
					disabled: T(r).busy || T(r).loading || !T(r).text.trim() || !!T(r).preview && !T(r).preview.new,
					onClick: a[6] ||= (t) => e.owner.submit()
				}, h(T(r).busy ? "正在导入…" : "导入到邮箱池"), 9, Gt)
			])
		], 40, Dt));
	}
}), qt = ["aria-busy"], Jt = { class: "em-dialog-head" }, Yt = { id: "emailButlerImportDescription" }, Xt = { class: "em-dialog-body" }, Zt = {
	key: 0,
	class: "em-dialog-fields"
}, Qt = { class: "em-field" }, $t = ["value", "disabled"], en = ["value"], tn = { class: "em-field" }, nn = ["value", "disabled"], rn = {
	key: 1,
	class: "em-error",
	role: "alert"
}, an = {
	key: 2,
	role: "status",
	"aria-live": "polite"
}, on = {
	key: 3,
	class: "em-preview",
	"aria-label": "Butler 导入结果"
}, sn = ["max", "value"], cn = { class: "em-stats" }, ln = {
	role: "status",
	"aria-live": "polite"
}, un = { class: "em-help em-preserve-lines" }, dn = { key: 1 }, fn = { key: 2 }, pn = { key: 3 }, mn = { class: "em-dialog-foot" }, hn = ["disabled"], gn = ["disabled"], _n = ["disabled"], vn = ["disabled"], yn = /* @__PURE__ */ t({
	__name: "EmailButlerImport",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(e) {
		let t = e, i = t.owner.state, a = m();
		z(a, () => i.open, () => t.active);
		let s = S(() => Number(i.batch?.imported || 0) + Number(i.batch?.skipped || 0) + Number(i.batch?.failed || 0) + Number(i.batch?.unknown || 0)), l = S(() => t.active && !!i.request && !i.open && ![
			"completed",
			"succeeded",
			"done",
			"cancelled"
		].includes(i.batch?.status || ""));
		return (t, d) => (n(), E(f, null, [l.value ? (n(), E("button", {
			key: 0,
			class: "em-recovery em-button",
			"aria-label": "查看 Butler 导入进度",
			onClick: d[0] ||= (t) => e.owner.open()
		}, h(T(i).batch ? `Butler 导入${e.owner.isRunning.value ? "中" : "结果"} · 已导入 ${T(i).batch.imported || 0} / ${T(i).batch.total || 0} · 查看进度` : "Butler 导入请求响应缺失 · 查看进度"), 1)) : u("", !0), _("dialog", {
			ref_key: "dialog",
			ref: a,
			class: "em-dialog",
			"data-email-butler-import": "",
			"aria-labelledby": "emailButlerImportTitle",
			"aria-describedby": "emailButlerImportDescription",
			"aria-busy": T(i).busy || T(i).polling,
			onCancel: d[10] ||= b((t) => e.owner.close(), ["prevent"]),
			onClick: d[11] ||= (t) => t.target === a.value && e.owner.close()
		}, [
			_("div", Jt, [_("div", null, [d[12] ||= _("h3", { id: "emailButlerImportTitle" }, "从 Butler 导入邮箱", -1), _("p", Yt, h(T(i).request ? "导入进度会自动保存，可随时关闭窗口。" : "从 Butler 分配长期租用的邮箱，加入本地库存后使用。"), 1)]), _("button", {
				class: "em-button",
				"aria-label": "关闭 Butler 导入窗口",
				onClick: d[1] ||= (t) => e.owner.close()
			}, "关闭")]),
			_("div", Xt, [
				T(i).request ? u("", !0) : (n(), E("div", Zt, [
					_("label", Qt, [d[13] ||= D("邮箱类型", -1), _("select", {
						"aria-label": "Butler 邮箱类型",
						value: T(i).filters.provider,
						disabled: T(i).storageError || T(i).busy,
						onChange: d[2] ||= (t) => e.owner.changeFilters({ provider: t.target.value })
					}, [(n(!0), E(f, null, o(T(i).providers, (e) => (n(), E("option", {
						key: e.value,
						value: e.value
					}, h(e.label), 9, en))), 128))], 40, $t)]),
					_("label", tn, [d[14] ||= D("导入数量", -1), _("input", {
						"aria-label": "Butler 导入数量",
						type: "number",
						min: "1",
						step: "1",
						inputmode: "numeric",
						value: T(i).filters.count,
						disabled: T(i).storageError || T(i).busy,
						onInput: d[3] ||= (t) => e.owner.changeFilters({ count: Number(t.target.value) })
					}, null, 40, nn)]),
					d[15] ||= _("p", { class: "em-help" }, "不足时按预览可用数量导入，确认后由 Butler 分配完整地址。", -1)
				])),
				T(i).error ? (n(), E("p", rn, h(T(i).error), 1)) : u("", !0),
				T(i).request ? u("", !0) : (n(), E("p", an, h(T(i).previewing ? "正在查询当前可用数量…" : e.owner.availability.value), 1)),
				T(i).request ? (n(), E("section", on, [
					_("h4", null, h(e.owner.batchTitle.value), 1),
					T(i).batch ? (n(), E(f, { key: 0 }, [
						_("progress", {
							max: Math.max(Number(T(i).batch.total || 0), 1),
							value: Math.min(s.value, Number(T(i).batch.total || 0)),
							"aria-label": "邮箱导入进度"
						}, null, 8, sn),
						_("div", cn, [(n(!0), E(f, null, o([
							["已导入", T(i).batch.imported],
							["待处理", T(i).batch.pending],
							["租用中", T(i).batch.submitting],
							["已跳过", T(i).batch.skipped],
							["失败", Number(T(i).batch.failed || 0) + Number(T(i).batch.unknown || 0)]
						], (e) => (n(), E("div", { key: String(e[0]) }, [_("strong", null, h(e[1] || 0), 1), _("span", null, h(e[0]), 1)]))), 128))]),
						_("p", ln, "已处理 " + h(s.value) + " / " + h(T(i).batch.total || 0) + " 个，本次请求 " + h(T(i).batch.requested || 0) + " 个。", 1)
					], 64)) : u("", !0),
					c(P, {
						label: T(te)(e.owner.batchTitle.value),
						title: e.owner.batchDetails.value,
						tone: T(i).batch?.status === "cancelled" ? "neutral" : T(i).batch?.failed ? "warning" : "active"
					}, {
						details: r(() => [D(h(e.owner.batchDetails.value), 1)]),
						_: 1
					}, 8, [
						"label",
						"title",
						"tone"
					]),
					_("p", un, h(T(i).batch?.status === "cancelled" ? "已停止后续导入，原结果与租约保留。" : e.owner.isRunning.value || T(i).resumePending ? "可以关闭窗口，导入会在后台继续。" : T(i).batch?.can_retry ? "可继续原批次处理剩余邮箱，已导入的邮箱会保留。" : "已保存原导入记录。"), 1),
					T(i).request.filters ? (n(), E("small", dn, "来源：" + h(T(se).find((e) => e.value === T(i).request?.filters?.provider)?.label || T(i).request.filters.provider) + " · 原请求数量 " + h(T(i).request.filters.count), 1)) : u("", !0),
					T(i).batch ? (n(), E("small", fn, "批次：" + h(T(i).batch.batch_id), 1)) : u("", !0),
					T(i).request ? (n(), E("small", pn, "原请求：" + h(T(i).request.request_id), 1)) : u("", !0)
				])) : u("", !0)
			]),
			_("div", mn, [
				_("button", {
					class: "em-button",
					onClick: d[4] ||= (t) => e.owner.close()
				}, h(e.owner.isRunning.value || T(i).resumePending ? "关闭，后台继续" : "关闭"), 1),
				e.owner.canCancel.value ? (n(), E("button", {
					key: 0,
					class: "em-button em-danger",
					disabled: T(i).busy,
					onClick: d[5] ||= (t) => e.owner.cancel()
				}, h(T(i).busy ? "正在终止…" : "终止批次"), 9, hn)) : u("", !0),
				e.owner.canReset.value ? (n(), E("button", {
					key: 1,
					class: "em-button",
					disabled: T(i).busy || T(i).polling,
					onClick: d[6] ||= (t) => e.owner.reset()
				}, "新建导入", 8, gn)) : u("", !0),
				T(i).request ? e.owner.canRetry.value ? (n(), E("button", {
					key: 3,
					class: "em-button em-primary",
					onClick: d[9] ||= (t) => e.owner.retry()
				}, h(T(i).batch ? "继续原批次" : "重试原请求"), 1)) : u("", !0) : (n(), E(f, { key: 2 }, [_("button", {
					class: "em-button",
					disabled: T(i).busy || T(i).previewing || T(i).storageError,
					onClick: d[7] ||= (t) => e.owner.preview()
				}, "刷新可用数量", 8, _n), _("button", {
					class: "em-button em-primary",
					disabled: T(i).busy || T(i).previewing || T(i).storageError || !T(i).preview?.selected,
					onClick: d[8] ||= (t) => e.owner.apply()
				}, h(T(i).preview?.selected ? `开始导入 ${T(i).preview.selected} 个` : "开始导入"), 9, vn)], 64))
			])
		], 40, qt)], 64));
	}
}), bn = { class: "em-page" }, xn = /* @__PURE__ */ t({
	__name: "EmailPageShell",
	props: {
		api: {},
		deps: {},
		initialView: {},
		initialVisible: { type: Boolean }
	},
	setup(e, { expose: t }) {
		let r = e, i = m(r.initialView || "overview"), o = m(r.initialVisible || !1), l = m(!document.hidden), u = s({
			sources: [],
			expanded: !1,
			loading: !1,
			error: ""
		}), d = Y(u, async (e, t) => {
			let n = await r.api.overview(e);
			t() && (u.sources = n.email?.supply?.sources || n.email?.sources || []);
		}), f = ie(r.api, r.deps), p = ae(r.api, r.deps), h = {
			...r.deps,
			async onInventoryChanged() {
				f.refresh(), p.refresh(), d.refresh(), await r.deps.onInventoryChanged();
			}
		}, g = oe(r.api, h), _ = he(r.api, h, { storage: {
			getItem: (e) => localStorage.getItem(e),
			setItem: (e, t) => localStorage.setItem(e, t),
			removeItem: (e) => localStorage.removeItem(e)
		} }), y = S(() => _.state.request ? _.isRunning.value ? `Butler 导入中 · ${_.state.batch?.imported || 0}/${_.state.batch?.total || 0}` : "查看 Butler 导入" : "从 Butler 导入");
		function b() {
			let e = o.value && l.value;
			d.setActive(e && i.value === "overview"), f.setActive(e && i.value === "list"), p.setActive(e && i.value === "derivations"), g.setActive(e), _.setActive(e);
		}
		function x() {
			g.close(), _.close();
		}
		function C(e) {
			[
				"overview",
				"list",
				"derivations"
			].includes(e) && i.value !== e && (i.value = e, x(), b());
		}
		function D(e) {
			o.value !== e && (o.value = e, e || x(), b());
		}
		function O(e) {
			e.id && (p.scopeParent({
				source: e.source,
				id: e.id,
				email: e.email
			}), r.deps.onNavigate("derivations"));
		}
		function k(e) {
			f.updateFilters({ source: e }), r.deps.onNavigate("list");
		}
		async function A(e) {
			g.open(e || ([
				"outlook",
				"generic_api",
				"email_butler"
			].includes(f.state.filters.source) ? f.state.filters.source : "outlook"));
		}
		async function j() {
			await _.open();
		}
		function M() {
			l.value = !document.hidden, b();
		}
		return document.addEventListener("visibilitychange", M), b(), v(() => {
			document.removeEventListener("visibilitychange", M), d.dispose(), f.dispose(), p.dispose(), g.dispose(), _.dispose();
		}), t({
			setView: C,
			setVisible: D,
			refreshOverview: d.refresh,
			refreshInventory: f.refresh,
			refreshHistory: p.refresh,
			refreshDerivationSummary: f.refreshDerivationSummary,
			openImport: A,
			openButlerImport: j,
			closeDialogs: x
		}), (e, t) => (n(), E("div", bn, [
			a(c(ke, {
				sources: u.sources,
				expanded: u.expanded,
				loading: u.loading,
				error: u.error,
				"butler-label": y.value,
				onRefresh: t[0] ||= (e) => T(d).refresh(),
				onExpand: t[1] ||= (e) => u.expanded = !u.expanded,
				onSource: k,
				onLocalImport: t[2] ||= (e) => A("email_butler"),
				onButlerImport: j
			}, null, 8, [
				"sources",
				"expanded",
				"loading",
				"error",
				"butler-label"
			]), [[w, i.value === "overview"]]),
			a(c(ft, {
				owner: T(f),
				active: o.value && l.value && i.value === "list",
				"butler-label": y.value,
				onLocalImport: t[3] ||= (e) => A(),
				onButlerImport: j,
				onParent: O
			}, null, 8, [
				"owner",
				"active",
				"butler-label"
			]), [[w, i.value === "list"]]),
			a(c(Et, {
				owner: T(p),
				active: o.value && l.value && i.value === "derivations"
			}, null, 8, ["owner", "active"]), [[w, i.value === "derivations"]]),
			c(Kt, {
				owner: T(g),
				active: o.value && l.value
			}, null, 8, ["owner", "active"]),
			c(yn, {
				owner: T(_),
				active: o.value && l.value
			}, null, 8, ["owner", "active"])
		]));
	}
});
// src/api/email.ts
function Sn(e = (e, t) => k(e, t, B)) {
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
function Cn(e, t) {
	let n = C(xn, {
		api: Sn(),
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
export { Cn as mountEmail };
