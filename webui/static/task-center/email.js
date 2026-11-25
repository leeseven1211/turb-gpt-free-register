import { B as e, C as t, F as n, G as r, H as i, K as a, L as o, Q as s, S as c, X as l, _ as u, d, dt as f, et as p, ft as m, g as h, h as g, j as _, k as v, l as y, lt as b, m as x, n as S, s as C, st as w, v as T, x as E } from "./_plugin-vue_export-helper-BSZsFlS8.js";
import { n as D, r as O, t as k } from "./client-B5R_MNgP.js";
import { a as A, i as j, r as M, t as N } from "./bulkMutations-3wwPI3-H.js";
import { a as ee, c as P, i as F, n as I, o as te, r as L, s as ne, t as re } from "./ListFilterSummary-Cy87eW0W.js";
import { t as R } from "./ListResult-CIQVLuqy.js";
import { t as z } from "./ListPagination-DkDYBtdx.js";
import { n as ie, t as B } from "./time-DOD6oyhP.js";
import { n as ae, t as V } from "./ColumnResizer-gRJCbdxj.js";
import { t as oe } from "./ListToolbar-MSPvDOqd.js";
import { t as se } from "./useNativeDialog-DWisXYg9.js";
import { r as ce } from "./taskIds-BlchWwUp.js";
// src/features/email/presentation.ts
var H = {
	all: "全部邮箱池",
	outlook: "Outlook",
	generic_api: "通用 API",
	cloudflare_domain: "域名邮箱",
	icloud_hide: "iCloud 隐藏邮箱",
	email_butler: "Butler 本地邮箱"
}, U = {
	available: "可用",
	used: "已用",
	pending_sync: "导入处理中",
	tombstone: "本地已删除",
	replaced: "换绑后邮箱",
	failed: "失败",
	disabled: "已停用"
}, le = {
	available: "待领取",
	pending_sync: "导入处理中",
	tombstone: "本地已删除",
	used_unbound: "已领取未绑定",
	bound: "已绑定账号",
	replaced: "换绑后邮箱",
	failed: "失败",
	disabled: "已停用"
}, W = {
	available: "历史未领取",
	disabled: "已停用",
	reserved: "归属已保留",
	used: "已绑定账号",
	replaced: "换绑后地址",
	retired: "历史停用"
}, G = (e) => ({
	source: e.source,
	email: e.email
}), K = (e) => `${e.source}|${e.email}`, q = (e) => e instanceof Error ? e.message : String(e);
function ue(e, t = 10) {
	let n = Array.from(e);
	return n.length > t ? n.slice(0, t - 1).join("") + "…" : e;
}
function J(e, t, n = "neutral") {
	return {
		label: ue(e),
		detail: t,
		tone: n
	};
}
function Y(e) {
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
function de(e) {
	return [e.registered_account_id ? `账号 #${e.registered_account_id}` : "", e.root_task_id ? `任务 #${e.root_task_id}` : ""].filter(Boolean).join(" · ") || (["available", "disabled"].includes(e.state || "") ? "尚未领取" : "历史归属");
}
function fe(e) {
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
function X(e, t) {
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
			o() && !D(t) && (e.error = q(t));
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
function pe(e, t) {
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
			used_date: "",
			usage: ""
		},
		facets: {},
		selected: /* @__PURE__ */ new Map(),
		loading: !1,
		error: "",
		summaryError: "",
		busy: !1,
		receipt: null
	}), r, i = X(n, async (t, r) => {
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
			r() && !(e instanceof Error && e.name === "AbortError") && (n.summaryError = `子地址历史读取失败：${q(e)}`);
		}
	});
	function a(e) {
		let t = Object.keys(e).filter((t) => e[t] !== n.filters[t]);
		t.length && (Object.assign(n.filters, e), n.page = 1, t.some((e) => e !== "q") && n.selected.clear(), i.schedule(t.every((e) => e === "q") ? 250 : 0));
	}
	function o(e, t) {
		t ? n.selected.set(K(e), G(e)) : n.selected.delete(K(e));
	}
	function c(e) {
		for (let t of n.items) o(t, e);
	}
	async function l() {
		try {
			await t.onInventoryChanged();
		} catch (e) {
			n.receipt = J(n.receipt?.label || "已接收", `${n.receipt?.detail || ""}\n显示刷新失败：${q(e)}`, "warning");
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
				if (e instanceof N) {
					n.receipt = J("批量命令已受理", e.message, "warning"), t.notify(e.message);
					return;
				}
				n.receipt = J("操作失败", q(e), "danger"), t.notify(`操作失败：${q(e)}`);
			} finally {
				n.busy = !1;
			}
		}
	}
	let d = () => ({ onAccepted: (e) => {
		n.receipt = J("批量命令已受理", `正在执行（命令 ${e.command_id}）`, "warning");
	} });
	function f(e, t) {
		let n = e.skipped || [], r = Array.isArray(e.deleted) ? e.deleted : [], i = e.lease_retained_count || r.filter((e) => e.sync?.lease_retained).length;
		return `${t === "delete" ? "本地已移除" : "已更新"} ${t === "delete" ? e.deleted_count || 0 : e.updated_count || 0} 个${i ? `，其中 ${i} 个已保留原租约` : ""}，跳过 ${n.length} 个` + n.map((e) => `\n${e.email}：${e.reason || "未返回具体原因"}`).join("");
	}
	async function p() {
		let r = Array.from(n.selected.values(), G), i = n.filters.source;
		r.length && !n.busy && await u(async () => {
			if (!await t.confirm(`确定从本地邮箱池移除选中的 ${r.length} 个邮箱吗？\n\n保留使用历史；缺少注册完成回执时保留原租约，确认账号未创建后才可退还。已确认注册成功的邮箱不能删除。`)) return;
			let a = await e.bulkDelete({
				items: r,
				source: i
			}, d()), o = new Set(r.map(K)), s = new Set((Array.isArray(a.deleted) ? a.deleted : []).map(K).filter((e) => o.has(e)));
			for (let e of s) n.selected.delete(e);
			s.size && (n.items = n.items.filter((e) => !s.has(K(e))), n.total = Math.max(0, n.total - s.size)), n.receipt = J("删除结果", f(a, "delete"), a.skipped?.length ? "warning" : "success"), l();
		});
	}
	async function m(r) {
		let i = Array.from(n.selected.values(), G), a = n.filters.source;
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
			}, d());
			for (let e of Array.isArray(s.updated) ? s.updated : []) i.some((t) => K(t) === K(e)) && n.selected.delete(K(e));
			n.receipt = J("状态更新", f(s, "status"), s.skipped?.length ? "warning" : "success"), await l();
		});
	}
	async function h(r, i) {
		let a = G(r);
		await u(async () => {
			if (i === "delete") {
				if (!await t.confirm(`确定从本地邮箱池移除 ${a.email}？\n\n保留使用历史；缺少注册完成回执时保留原租约，确认账号未创建后才可退还。已确认注册成功的邮箱不能删除。`)) return;
				let r = await e.delete(a);
				r.deleted ? (n.selected.delete(K(a)), n.items = n.items.filter((e) => K(e) !== K(a)), n.total = Math.max(0, n.total - 1), n.receipt = J("本地已移除", r.sync?.message || "本地已移除，保留使用历史", "success"), l()) : n.receipt = J("未移除", r.reason || "邮箱未移除", "warning");
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
				}), n.receipt = J("状态已更新", `${a.email}：${t[i]}`, "success"), await l();
			}
		});
	}
	async function g(n) {
		let i = G(n);
		await u(async () => {
			r = new AbortController();
			let n = r.signal, a = await e.secret(i, n);
			if (!n.aborted) {
				if (!a.value) throw Error("对应内容为空");
				await t.clipboard(a.value), t.notify("已复制");
			}
		});
	}
	async function _() {
		let i = n.items.map(G);
		i.length && await u(async () => {
			r = new AbortController();
			let a = r.signal, o = await e.secrets(i, a);
			if (a.aborted) return;
			let s = (o.values || []).map((e) => e.value).filter(Boolean).join("\n");
			if (!s) throw Error("当前页没有可复制内容");
			await t.clipboard(s), n.receipt = J("已复制当前页", (o.skipped || []).map((e) => `${e.email}：${e.reason}`).join("\n") || `已复制 ${i.length} 个邮箱素材`, "success"), t.notify("已复制当前页邮箱素材");
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
		bulkDelete: p,
		bulkStatus: m,
		rowAction: h,
		copyRow: g,
		copyPage: _,
		resetFilters() {
			Object.assign(n.filters, {
				source: "all",
				q: "",
				status: "",
				used_date: "",
				usage: ""
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
var Z = () => ({
	source: "all",
	parent_id: "",
	q: "",
	parent_q: "",
	state: "",
	related_q: "",
	created_from: "",
	created_to: ""
});
function me(e, t) {
	let n = s({
		items: [],
		total: 0,
		page: 1,
		size: 50,
		filters: Z(),
		parentEmail: "",
		selected: /* @__PURE__ */ new Map(),
		loading: !1,
		error: "",
		receipt: null
	}), r = X(n, async (t, r) => {
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
			Object.assign(n.filters, Z()), n.parentEmail = "", n.selected.clear(), n.page = 1, r.schedule();
		},
		scopeParent(e) {
			Object.assign(n.filters, Z(), {
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
				await t.clipboard(e.map((e) => e.email).filter(Boolean).join("\n")), n.receipt = J("已复制", `已复制 ${e.length} 条历史子邮箱`, "success");
			} catch (e) {
				n.receipt = J("复制失败", q(e), "danger");
			}
		}
	};
}
// src/features/email/useLocalImport.ts
var Q = {
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
function he(e, t) {
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
			return d === a && !D(e) && (n.error = q(e)), null;
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
			n.receipt = J("导入已接收", s, "success"), JSON.stringify(l()) === i && (n.text = "", u());
			try {
				await t.onInventoryChanged();
			} catch (e) {
				n.receipt = J("导入已接收", `${s}\n显示刷新失败：${q(e)}`, "warning");
			}
			t.notify("邮箱导入已接收");
		} catch (e) {
			n.error = q(e), n.receipt = e instanceof k && e.status >= 400 && e.status < 500 ? J("导入被拒绝", `导入被拒绝：${q(e)}。已保留原素材。`, "danger") : J("导入结果未确认", `导入响应未确认：${q(e)}。已保留原素材，请先核对库存；不会自动重复提交。`, "danger");
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
			n.open = !0, Q[e] && n.source !== e && d({ source: e });
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
var ge = [
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
], _e = {
	source_unavailable: "来源不可用",
	active_same_service: "OpenAI 已租用",
	other_service_exclusive: "其他服务占用",
	history_blocked: "历史占用限制",
	cooldown: "冷却中"
}, ve = {
	global_capacity: "等待全局业务空位",
	type_capacity: "等待邮箱导入空位",
	batch_capacity: "等待当前导入批次空位",
	fairness_turn: "等待其他类型或批次轮转",
	scheduler_store_unavailable: "等待数据库恢复后继续准入",
	concurrency_policy_migration_required: "等待保存部署并发策略",
	concurrency_policy_invalid: "等待修正并发策略",
	concurrency_policy_missing: "等待补齐邮箱导入并发策略"
}, ye = {
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
}, be = "turb.butler-import.v1", xe = (e) => [
	"completed",
	"succeeded",
	"done"
].includes(e || ""), Se = (e) => [
	"pending",
	"queued",
	"running",
	"processing"
].includes(e || ""), Ce = (e) => JSON.stringify([
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
function we(e, t, n) {
	let r = s({
		open: !1,
		filters: {
			provider: "icloud_hme",
			count: 10
		},
		providers: [...ge],
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
		r.request && n.storage.setItem(be, JSON.stringify({
			...r.request,
			...r.batch ? {
				batch_id: r.batch.batch_id,
				batch_status: r.batch.status
			} : {},
			...r.resumePending ? { resume_revision: r.resumePending } : {}
		}));
	}
	function S() {
		o++, l?.abort(), d?.abort(), clearTimeout(f), r.preview = null, r.previewing = !1;
	}
	function C() {
		S(), c++, u?.abort(), u = void 0, m = null, r.polling = !1, clearTimeout(p);
	}
	let w = x(() => Se(r.batch?.status)), T = x(() => r.batch?.status === "cancelled" || !!r.batch && !r.batch.can_retry && !Number(r.batch.unknown || r.batch.internal_unknown_count || 0) && [
		"completed",
		"succeeded",
		"done",
		"partial",
		"partial_success",
		"failed",
		"rejected"
	].includes(r.batch.status)), E = x(() => !!r.request && !r.busy && !r.polling && r.batch?.status !== "cancelled" && !w.value && !r.resumePending && (!r.batch || r.batch.can_retry === !0)), O = x(() => !!r.batch && r.batch.can_cancel !== !1 && r.batch.status !== "cancelled" && !xe(r.batch.status)), A = x(() => {
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
	}), j = x(() => {
		let e = r.batch;
		if (!e) return "可以关闭窗口，已保存原请求；重新打开后可恢复结果。";
		let t = [e.status === "cancelled" ? "已停止后续导入。已导入邮箱、原租约和失败记录均保留；已发出的请求仍会保存结果。" : w.value || r.resumePending ? "可以关闭窗口，导入会在后台继续；刷新页面也能恢复。" : e.can_retry ? "可继续原批次处理剩余邮箱，已导入的邮箱会保留。" : "已导入的邮箱已加入本地库存，可以关闭窗口或新建导入。"];
		for (let n of e.blocked_by || []) t.push(ve[n] || `等待准入（${n}）`);
		e.error_code && t.push(`${ye[e.error_code] || "批次异常"}（${e.error_code}）`);
		for (let [n, r] of Object.entries(e.error_counts || {})) t.push(`${ye[n] || "处理异常"}（${n}）：${r} 个`);
		return e.internal_unknown_count && t.push(`原请求仍有 ${e.internal_unknown_count} 个待核实回执，保留原批次恢复；内部状态：${e.internal_status || "未记录"}。`), t.join("\n");
	}), M = x(() => {
		let e = r.preview;
		if (!e) return "";
		let t = Object.entries(_e).filter(([t]) => Number.isSafeInteger(e.availability_buckets?.[t]) && Number(e.availability_buckets?.[t]) > 0).map(([t, n]) => `${n} ${e.availability_buckets[t]} 个`);
		return `当前可用 ${Number(e.available || 0)} 个 · 本次可导入 ${Number(e.selected || 0)} 个。${t.length ? `${Number.isSafeInteger(e.resource_total) ? `当前查询范围 ${e.resource_total} 个` : "当前查询范围"}：${t.join(" · ")}。` : ""}Butler“未租用”不等于可用于 OpenAI。查询不占用库存；确认后由 Butler 分配地址，导入时再核对本地占用。`;
	});
	function N() {
		clearTimeout(p), y() && r.batch && r.batch.status !== "cancelled" && (w.value || r.resumePending) && (p = setTimeout(() => void R(), 2e3));
	}
	function ee() {
		let e = Number(r.batch?.imported || 0);
		!e || e === h || _ || w.value && h >= 0 && v() - g < 15e3 || (_ = Promise.resolve().then(() => t.onInventoryChanged()).then(() => {
			h = e;
		}, (e) => {
			r.error = `邮箱已导入，但显示未完全刷新：${q(e)}`;
		}).finally(() => {
			_ = null, g = v(), !w.value && Number(r.batch?.imported || 0) !== e && ee();
		}));
	}
	function P(e) {
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
		r.resumePending && (Se(i.status) || Ce(i) !== r.resumePending) && (r.resumePending = null), r.batch = i, i.status === "cancelled" && (r.resumePending = null, c++, u?.abort(), r.polling = !1, clearTimeout(p));
		try {
			b();
		} catch {
			r.error = "原请求已保存，批次编号暂未写入浏览器；重开后将恢复原请求。";
		}
		ee();
	}
	async function F() {
		if (!y() || !r.open || r.request || r.busy) return;
		let t = { ...r.filters };
		if (S(), r.error = "", !ge.some((e) => e.value === t.provider)) {
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
			n === o && !D(e) && (r.error = `查询可用数量失败：${q(e)}`);
		} finally {
			n === o && (r.previewing = !1);
		}
	}
	function I(e) {
		r.request || (Object.assign(r.filters, e), S(), r.error = "", y() && r.open && (f = setTimeout(() => void F(), 400)));
	}
	async function te() {
		if (r.open = !0, r.storageError) return;
		if (r.batch) {
			await R();
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
			t === o && !D(e) && (r.error = `读取导入选项失败：${q(e)}`);
		}
		t === o && await F();
	}
	function L() {
		r.open = !1, S();
	}
	async function ne() {
		if (r.busy || r.polling || !r.request || r.batch?.status === "cancelled" || r.batch && !r.batch.can_retry) return;
		let t = {
			request_id: r.request.request_id,
			preview_token: r.request.preview_token
		}, i = r.batch;
		r.busy = !0, r.error = "";
		try {
			let n = await (i ? e.retryBatch(i.batch_id, t) : e.createBatch(t));
			i && (r.resumePending = Ce(i)), P(n);
		} catch (e) {
			if (!r.batch && e instanceof k && [
				"import_preview_not_found",
				"import_preview_expired",
				"import_preview_empty",
				"import_snapshot_conflict"
			].includes(e.code)) try {
				n.storage.removeItem(be), r.request = null, S(), r.error = `导入尚未开始：${q(e)}。请重新预览。`;
			} catch {
				r.error = "导入尚未开始，但原记录暂未清除；请恢复浏览器存储后重试原请求。";
			}
			else r.error = `导入请求失败：${q(e)}。请${r.batch ? "继续原批次" : "重试原请求"}恢复，已保留原编号。`;
		} finally {
			r.busy = !1, N();
		}
	}
	async function re() {
		if (!(r.busy || r.request || !r.preview || r.preview.selected < 1)) {
			if (JSON.stringify(r.filters) !== JSON.stringify(r.preview.filters)) S(), r.error = "筛选已变化，请刷新可用数量。";
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
				await ne();
			}
		}
	}
	async function R() {
		if (m) return m;
		if (!y() || !r.batch || r.busy) return;
		clearTimeout(p);
		let t = ++c, n = r.batch.batch_id;
		u = new AbortController(), r.polling = !0;
		let i = (async () => {
			try {
				let i = await e.batch(n, u.signal);
				if (t !== c || !y() || r.batch?.batch_id !== n) return;
				r.error = "", P(i);
			} catch (e) {
				t === c && !D(e) && (r.error = `暂时无法读取原批次：${q(e)}。请重开此窗口恢复查看。`);
			} finally {
				t === c && (r.polling = !1, m = null, N());
			}
		})();
		m = i, await i;
	}
	async function z() {
		if (r.busy || !O.value || !r.batch) return;
		let t = r.batch.batch_id;
		r.busy = !0, r.error = "";
		try {
			let n = await e.cancelBatch(t);
			if (P(n), n.batch.status !== "cancelled" && !xe(n.batch.status)) throw Error("服务端未返回终止回执");
			c++, u?.abort(), m = null, r.polling = !1;
		} catch (e) {
			r.error = `终止请求失败：${q(e)}。已保留原批次，请重试终止或查看原批次状态。`;
		} finally {
			r.busy = !1, N();
		}
	}
	async function ie() {
		if (!(!T.value || r.busy || r.polling)) {
			try {
				n.storage.removeItem(be);
			} catch {
				r.error = "无法清除上次导入记录，请恢复浏览器存储后重试。";
				return;
			}
			C(), r.request = null, r.batch = null, r.resumePending = null, r.error = "", h = -1, g = 0, await F();
		}
	}
	function B(e) {
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
	return window.addEventListener("storage", B), {
		state: r,
		isRunning: w,
		canReset: T,
		canRetry: E,
		canCancel: O,
		batchTitle: A,
		batchDetails: j,
		availability: M,
		open: te,
		close: L,
		preview: F,
		changeFilters: I,
		apply: re,
		retry: ne,
		poll: R,
		cancel: z,
		reset: ie,
		setActive(e) {
			a || e === i || (i = e, e ? r.batch ? R() : r.open && !r.request && te() : C());
		},
		dispose() {
			a = !0, C(), window.removeEventListener("storage", B);
		}
	};
}
// src/features/email/EmailOverview.vue?vue&type=script&setup=true&lang.ts
var Te = ["aria-busy"], Ee = { class: "em-heading" }, De = ["disabled"], Oe = {
	key: 0,
	class: "em-error",
	role: "alert"
}, ke = { class: "em-source-visibility" }, Ae = ["aria-expanded"], je = { class: "em-source-cards" }, Me = { class: "em-source-title" }, Ne = { class: "em-source-number" }, Pe = { key: 0 }, Fe = {
	key: 1,
	role: "status"
}, Ie = { class: "em-import-prompt" }, Le = { class: "em-actions" }, Re = /* @__PURE__ */ t({
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
		let a = t, s = i, c = (e) => e === !0 || e === "true", l = (e) => e.kind === "local_pool" || (e.default_visible === void 0 ? c(e.enabled) || c(e.dependency) : c(e.default_visible)), f = x(() => a.sources.filter((e) => !l(e)).length), p = x(() => a.expanded ? a.sources : a.sources.filter(l)), _ = (e) => e.kind !== "on_demand" && !!H[e.source] && e.source !== "all";
		function v(e) {
			return e.kind === "local_pool" ? "本地库存" : c(e.enabled) ? "已启用" : c(e.dependency) ? "收码依赖" : c(e.history_available) || Number(e.total) > 0 ? "历史/已停用" : "未启用";
		}
		return (i, a) => (n(), T("section", {
			class: "em-overview",
			"aria-label": "邮箱资源平台",
			"aria-busy": t.loading
		}, [
			g("div", Ee, [a[5] ||= g("div", null, [g("h2", null, "本地邮箱库存"), g("p", null, "仅从本地库存领取邮箱，用完后请从 Butler 或其他来源手动导入。")], -1), g("button", {
				class: "em-button",
				disabled: t.loading,
				onClick: a[0] ||= (e) => s("refresh")
			}, m(t.loading ? "刷新中…" : "刷新资源"), 9, De)]),
			t.error ? (n(), T("p", Oe, [E(m(t.error) + " ", 1), g("button", {
				class: "em-button",
				onClick: a[1] ||= (e) => s("refresh")
			}, "重试")])) : u("", !0),
			g("div", ke, [g("span", null, m(f.value ? "默认显示已启用服务和当前收码依赖" : "当前没有未启用的邮箱服务"), 1), f.value ? (n(), T("button", {
				key: 0,
				class: "em-button",
				"aria-expanded": t.expanded,
				onClick: a[2] ||= (e) => s("expand")
			}, m(t.expanded ? "隐藏未启用" : `显示未启用（${f.value}）`), 9, Ae)) : u("", !0)]),
			g("div", je, [(n(!0), T(d, null, o(p.value, (t) => (n(), h(e(_(t) ? "button" : "article"), {
				key: t.source,
				type: _(t) ? "button" : void 0,
				class: b(["em-source-card", { "is-clickable": _(t) }]),
				onClick: (e) => _(t) && s("source", t.source)
			}, {
				default: r(() => [
					g("div", Me, [g("strong", null, m(t.label || w(H)[t.source] || t.source), 1), g("span", null, m(v(t)), 1)]),
					g("strong", Ne, m(t.kind === "on_demand" ? "按需" : t.available ?? 0), 1),
					g("p", null, m(t.kind === "on_demand" ? "运行时领取 / 创建" : `总数 ${t.total || 0} · 已用 ${t.used || 0} · 失败 ${t.failed || 0} · 停用 ${t.disabled || 0}`), 1),
					t.dependency_reason ? (n(), T("small", Pe, m(t.dependency_reason), 1)) : u("", !0)
				]),
				_: 2
			}, 1032, [
				"type",
				"class",
				"onClick"
			]))), 128))]),
			p.value.length ? u("", !0) : (n(), T("p", Fe, m(t.loading ? "正在加载邮箱资源…" : "暂无已启用邮箱服务，可显示未启用的服务。"), 1)),
			g("section", Ie, [a[6] ||= g("div", null, [
				g("span", null, "Email Butler"),
				g("h3", null, "手动补充本地库存"),
				g("p", null, "从 Butler 选择 iCloud HME 母邮箱或子邮箱导入，也可粘贴已有完整地址。注册任务仅领取本地库存。")
			], -1), g("div", Le, [g("button", {
				class: "em-button em-primary",
				"data-butler-opener": "",
				onClick: a[3] ||= (e) => s("butlerImport")
			}, m(t.butlerLabel), 1), g("button", {
				class: "em-button",
				onClick: a[4] ||= (e) => s("localImport")
			}, "粘贴导入")])])
		], 8, Te));
	}
}), ze = {
	key: 0,
	class: "em-filter-field"
}, Be = ["aria-label"], Ve = ["data-filter-value"], He = [
	"name",
	"value",
	"checked"
], Ue = ["data-filter-value"], We = [
	"name",
	"value",
	"checked",
	"onChange"
], Ge = { key: 0 }, Ke = {
	key: 1,
	class: "em-filter-field"
}, qe = [
	"aria-label",
	"type",
	"value"
], Je = {
	key: 2,
	class: "em-filter-field"
}, Ye = ["aria-label", "value"], Xe = { class: "list-filter-actions" }, $ = /* @__PURE__ */ t({
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
		let a = e, s = t, c = p(!1);
		i(() => a.active, (e) => {
			e || (c.value = !1);
		});
		let f = x(() => a.value !== (a.emptyValue || "") || !!a.endValue), _ = x(() => (a.options || []).filter((e) => e.count === void 0 || e.count > 0 || e.value === a.value)), v = !1;
		function y(e) {
			v = !1, s("change", e.target.value);
		}
		function b(e) {
			v || s("change", e.target.value);
		}
		return (t, i) => (n(), h(F, {
			label: e.label,
			active: f.value,
			summary: [e.value, e.endValue].filter(Boolean).join(" 至 "),
			open: c.value,
			"onUpdate:open": i[4] ||= (e) => c.value = e
		}, {
			default: r(() => [
				e.options ? (n(), T("div", ze, [E(m(e.label) + " ", 1), g("div", {
					class: "list-filter-options",
					role: "radiogroup",
					"aria-label": e.label
				}, [g("label", {
					class: "list-filter-option",
					"data-filter-value": e.emptyValue || ""
				}, [g("input", {
					type: "radio",
					name: `filter-${e.label}`,
					value: e.emptyValue || "",
					checked: !e.value || e.value === (e.emptyValue || ""),
					onChange: i[0] ||= (t) => s("change", e.emptyValue || "")
				}, null, 40, He), i[5] ||= g("span", null, "全部", -1)], 8, Ve), (n(!0), T(d, null, o(_.value, (t) => (n(), T("label", {
					key: t.value,
					class: "list-filter-option",
					"data-filter-value": t.value
				}, [
					g("input", {
						type: "radio",
						name: `filter-${e.label}`,
						value: t.value,
						checked: e.value === t.value,
						onChange: (e) => s("change", t.value)
					}, null, 40, We),
					g("span", null, m(t.label), 1),
					t.count === void 0 ? u("", !0) : (n(), T("small", Ge, m(t.count), 1))
				], 8, Ue))), 128))], 8, Be)])) : (n(), T("label", Ke, [E(m(e.label) + " ", 1), g("input", {
					"aria-label": e.label,
					type: e.type === "date" || e.type === "range" ? "date" : "search",
					multiple: !1,
					value: e.value,
					onCompositionstart: i[1] ||= (e) => l(v) ? v.value = !0 : v = !0,
					onCompositionend: y,
					onInput: b
				}, null, 40, qe)])),
				e.type === "range" ? (n(), T("label", Je, [i[6] ||= E("结束日期", -1), g("input", {
					type: "date",
					"aria-label": `${e.label}结束`,
					value: e.endValue,
					onInput: i[2] ||= (e) => s("end", e.target.value)
				}, null, 40, Ye)])) : u("", !0),
				g("div", Xe, [g("button", {
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
}), Ze = ["aria-busy"], Qe = {
	key: 0,
	class: "ui-list-count"
}, $e = {
	key: 1,
	class: "em-bulk-actions",
	role: "group",
	"aria-label": "选中邮箱批量操作"
}, et = ["disabled"], tt = ["disabled"], nt = ["disabled"], rt = ["disabled"], it = ["disabled"], at = ["disabled"], ot = {
	key: 0,
	class: "ui-list-feedback is-error",
	role: "alert"
}, st = {
	key: 1,
	class: "ui-list-feedback is-error",
	role: "alert"
}, ct = { class: "ui-col-check" }, lt = [
	"checked",
	"indeterminate",
	"disabled"
], ut = { class: "ui-col-check" }, dt = [
	"aria-label",
	"checked",
	"onChange"
], ft = [
	"aria-label",
	"title",
	"onClick"
], pt = { class: "em-source" }, mt = { class: "ui-row-actions em-row-actions" }, ht = ["disabled", "onClick"], gt = ["disabled", "onClick"], _t = ["disabled", "aria-label"], vt = ["disabled", "onClick"], yt = /* @__PURE__ */ t({
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
		let a = e, s = t, l = a.owner.state, _ = p(), S = p(null);
		i(() => a.active, (e) => {
			e || (S.value = null);
		});
		let C = !1;
		i([
			() => l.page,
			() => l.size,
			() => Object.values(l.filters)
		], () => {
			C = !0;
		}), i(() => l.items, () => {
			C && _.value && (_.value.scrollTop = 0, C = !1);
		}, { flush: "post" });
		let D = ae({
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
		}), O = x(() => l.items.filter((e) => l.selected.has(K(e))).length), k = x(() => Object.entries(l.filters).filter(([e, t]) => t && (e !== "source" || t !== "all")).map(([e, t]) => ({
			key: e,
			label: `${{
				q: "邮箱",
				source: "类型",
				status: "状态",
				used_date: "最近使用日期",
				usage: "使用情况"
			}[e]}：${e === "source" ? H[t] || t : e === "status" ? U[t] || t : e === "usage" && {
				bound: "已绑定",
				used_unbound: "未绑定"
			}[t] || t}`,
			removeLabel: `移除${e}筛选`
		}))), A = x(() => Object.entries(H).filter(([e]) => e !== "all").map(([e, t]) => ({
			value: e,
			label: t,
			count: l.facets.source ? l.facets.source.find((t) => t.value === e)?.count ?? 0 : void 0
		}))), j = x(() => [.../* @__PURE__ */ new Set([
			...Object.keys(U),
			...(l.facets.status || []).map((e) => e.value),
			l.filters.status
		])].filter(Boolean).map((e) => ({
			value: e,
			label: U[e] || e,
			count: l.facets.status ? l.facets.status.find((t) => t.value === e)?.count ?? 0 : void 0
		}))), M = [{
			value: "bound",
			label: "已绑定"
		}, {
			value: "used_unbound",
			label: "未绑定"
		}], N = (e) => l.parents.find((t) => t.source === e.source && String(t.parent_id) === String(e.id) && Number(t.child_count) > 0), F = (e) => e.service_sync_error || e.note || e.disabled_reason || "", se = {
			available: "恢复可用",
			disabled: "停用",
			failed: "标失败"
		};
		function ce(e) {
			return {
				available: "success",
				used: "active",
				pending_sync: "warning",
				replaced: "warning",
				failed: "danger"
			}[e || ""] || "neutral";
		}
		function W(e) {
			return {
				available: "success",
				used_unbound: "active",
				bound: "active",
				pending_sync: "warning",
				replaced: "warning",
				failed: "danger"
			}[e || ""] || "neutral";
		}
		function G(e) {
			let t = Y(e).text;
			return t.includes("缺少") ? "danger" : t.includes("已配置") ? "success" : "neutral";
		}
		function q(e) {
			return {
				outlook: "#377dff",
				generic_api: "#7c5cf0",
				cloudflare_domain: "#e08a1e",
				icloud_hide: "#0e9aa7",
				email_butler: "#1f9d75"
			}[e] || "#98a2b3";
		}
		function ue(e) {
			return Object.entries(se).filter(([t]) => t !== e.status);
		}
		function J(e, t) {
			S.value = null, a.owner.rowAction(e, t);
		}
		function de(e) {
			a.owner.updateFilters({ [e]: e === "source" ? "all" : "" });
		}
		function X(e) {
			return e.last_activity_at || e.used_at || e.updated_at || e.created_at;
		}
		function pe(e) {
			return `${e.used_at ? "最近使用" : e.last_activity_at ? "最近更新" : "导入时间"}：${ie(X(e))}${e.synced_at ? `\n同步：${ie(e.synced_at)}` : ""}`;
		}
		return (t, i) => (n(), T("section", {
			class: "ui-list em-list em-inventory",
			"aria-label": "邮箱池",
			"aria-busy": w(l).loading
		}, [
			c(oe, {
				class: "em-toolbar",
				filtered: k.value.length > 0
			}, {
				actions: r(() => [
					k.value.length ? (n(), T("button", {
						key: 0,
						class: "ui-link",
						onClick: i[4] ||= (t) => e.owner.resetFilters()
					}, "清筛")) : u("", !0),
					g("button", {
						class: "ui-button",
						disabled: w(l).busy || !w(l).items.length,
						onClick: i[5] ||= (t) => e.owner.copyPage()
					}, "复制当前页", 8, it),
					g("button", {
						class: "ui-button",
						"data-butler-opener": "",
						onClick: i[6] ||= (e) => s("butlerImport")
					}, m(e.butlerLabel), 1),
					g("button", {
						class: "ui-button ui-button--primary",
						onClick: i[7] ||= (e) => s("localImport")
					}, "导入邮箱"),
					g("button", {
						class: "ui-link",
						onClick: i[8] ||= (...e) => w(D).resetColumns && w(D).resetColumns(...e)
					}, "恢复列宽"),
					g("button", {
						class: "ui-button",
						disabled: w(l).loading,
						onClick: i[9] ||= (t) => e.owner.refresh()
					}, "刷新", 8, at)
				]),
				default: r(() => [
					w(l).selected.size ? (n(), T("span", Qe, "已选 " + m(w(l).selected.size) + " 个邮箱", 1)) : u("", !0),
					w(l).selected.size ? (n(), T("div", $e, [
						g("button", {
							class: "ui-button",
							disabled: w(l).busy,
							onClick: i[0] ||= (t) => e.owner.bulkStatus("available")
						}, "标记未使用", 8, et),
						g("button", {
							class: "ui-button",
							disabled: w(l).busy,
							onClick: i[1] ||= (t) => e.owner.bulkStatus("disabled")
						}, "停用选中", 8, tt),
						g("button", {
							class: "ui-button",
							disabled: w(l).busy,
							onClick: i[2] ||= (t) => e.owner.bulkStatus("failed")
						}, "标失败", 8, nt),
						g("button", {
							class: "ui-button ui-button--danger",
							disabled: w(l).busy,
							onClick: i[3] ||= (t) => e.owner.bulkDelete()
						}, "删除选中", 8, rt)
					])) : u("", !0),
					c(re, {
						items: k.value,
						onRemove: de
					}, null, 8, ["items"])
				]),
				_: 1
			}, 8, ["filtered"]),
			w(l).error ? (n(), T("div", ot, [E(m(w(l).error) + " ", 1), g("button", {
				class: "ui-link",
				onClick: i[10] ||= (t) => e.owner.refresh()
			}, "重试")])) : u("", !0),
			w(l).summaryError ? (n(), T("div", st, [E(m(w(l).summaryError) + " ", 1), g("button", {
				class: "ui-link",
				onClick: i[11] ||= (t) => e.owner.refreshDerivationSummary()
			}, "重试")])) : u("", !0),
			g("div", {
				ref_key: "tableViewport",
				ref: _,
				class: "ui-table-scroll em-table-wrap",
				role: "region",
				tabindex: "0",
				"aria-label": "邮箱列表，可滚动",
				onScroll: i[37] ||= (e) => S.value = null
			}, [g("table", {
				class: "ui-table ui-table--sticky-end em-table",
				style: f({ "--ui-table-width": `${w(D).total.value}px` })
			}, [
				g("colgroup", null, [(n(!0), T(d, null, o(w(D).widths.value, (e, t) => (n(), T("col", {
					key: t,
					style: f({ width: `${e}px` })
				}, null, 4))), 128))]),
				g("thead", null, [g("tr", null, [
					g("th", ct, [g("input", {
						type: "checkbox",
						"aria-label": "全选当前页邮箱资源",
						checked: !!w(l).items.length && O.value === w(l).items.length,
						indeterminate: O.value > 0 && O.value < w(l).items.length,
						disabled: !w(l).items.length,
						onChange: i[12] ||= (t) => e.owner.togglePage(t.target.checked)
					}, null, 40, lt), c(V, {
						label: "选择",
						onStart: i[13] ||= (e) => w(D).resize(0, e),
						onNudge: i[14] ||= (e) => w(D).resizeWithKeyboard(0, e)
					})]),
					g("th", null, [c($, {
						label: "邮箱",
						value: w(l).filters.q,
						active: e.active,
						onChange: i[15] ||= (t) => e.owner.updateFilters({ q: t })
					}, null, 8, ["value", "active"]), c(V, {
						label: "邮箱",
						onStart: i[16] ||= (e) => w(D).resize(1, e),
						onNudge: i[17] ||= (e) => w(D).resizeWithKeyboard(1, e)
					})]),
					g("th", null, [c($, {
						label: "类型",
						value: w(l).filters.source,
						"empty-value": "all",
						options: A.value,
						active: e.active,
						onChange: i[18] ||= (t) => e.owner.updateFilters({ source: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), c(V, {
						label: "类型",
						onStart: i[19] ||= (e) => w(D).resize(2, e),
						onNudge: i[20] ||= (e) => w(D).resizeWithKeyboard(2, e)
					})]),
					g("th", null, [c($, {
						label: "状态",
						value: w(l).filters.status,
						options: j.value,
						active: e.active,
						onChange: i[21] ||= (t) => e.owner.updateFilters({ status: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), c(V, {
						label: "状态",
						onStart: i[22] ||= (e) => w(D).resize(3, e),
						onNudge: i[23] ||= (e) => w(D).resizeWithKeyboard(3, e)
					})]),
					g("th", null, [c($, {
						label: "使用情况",
						value: w(l).filters.usage,
						options: M,
						active: e.active,
						onChange: i[24] ||= (t) => e.owner.updateFilters({ usage: t })
					}, null, 8, ["value", "active"]), c(V, {
						label: "使用情况",
						onStart: i[25] ||= (e) => w(D).resize(4, e),
						onNudge: i[26] ||= (e) => w(D).resizeWithKeyboard(4, e)
					})]),
					g("th", null, [i[38] ||= E("凭证配置", -1), c(V, {
						label: "凭证配置",
						onStart: i[27] ||= (e) => w(D).resize(5, e),
						onNudge: i[28] ||= (e) => w(D).resizeWithKeyboard(5, e)
					})]),
					g("th", null, [c($, {
						label: "最近活动",
						type: "date",
						value: w(l).filters.used_date,
						active: e.active,
						onChange: i[29] ||= (t) => e.owner.updateFilters({ used_date: t })
					}, null, 8, ["value", "active"]), c(V, {
						label: "最近活动",
						onStart: i[30] ||= (e) => w(D).resize(6, e),
						onNudge: i[31] ||= (e) => w(D).resizeWithKeyboard(6, e)
					})]),
					g("th", null, [i[39] ||= E("备注 / 原因", -1), c(V, {
						label: "备注 / 原因",
						onStart: i[32] ||= (e) => w(D).resize(7, e),
						onNudge: i[33] ||= (e) => w(D).resizeWithKeyboard(7, e)
					})]),
					g("th", null, [i[40] ||= E("操作", -1), c(V, {
						label: "操作",
						onStart: i[34] ||= (e) => w(D).resize(8, e),
						onNudge: i[35] ||= (e) => w(D).resizeWithKeyboard(8, e)
					})])
				])]),
				g("tbody", null, [(n(!0), T(d, null, o(w(l).items, (t) => (n(), T("tr", {
					key: w(K)(t),
					class: b({ "is-selected": w(l).selected.has(w(K)(t)) })
				}, [
					g("td", ut, [g("input", {
						type: "checkbox",
						"aria-label": `选择邮箱 ${t.email}`,
						checked: w(l).selected.has(w(K)(t)),
						onChange: (n) => e.owner.toggle(t, n.target.checked)
					}, null, 40, dt)]),
					g("td", null, [N(t) ? (n(), T("button", {
						key: 0,
						class: "em-cell-button",
						"aria-label": `查看 ${t.email} 的历史子地址`,
						title: [
							t.email,
							t.remote_label,
							`历史子地址 ${N(t)?.child_count} 个`
						].filter(Boolean).join(" · "),
						onClick: (e) => s("parent", t)
					}, [c(L, {
						text: t.email,
						secondary: `查看历史 · ${N(t)?.child_count} 个`
					}, null, 8, ["text", "secondary"])], 8, ft)) : (n(), h(L, {
						key: 1,
						text: t.email,
						secondary: t.remote_label || void 0
					}, null, 8, ["text", "secondary"]))]),
					g("td", null, [c(L, { text: w(H)[t.source] || t.source }, {
						default: r(() => [g("span", pt, [g("i", {
							style: f({ background: q(t.source) }),
							"aria-hidden": "true"
						}, null, 4), E(m(w(H)[t.source] || t.source), 1)])]),
						_: 2
					}, 1032, ["text"])]),
					g("td", null, [c(L, { text: w(U)[t.status || ""] || t.status || "状态记录缺失" }, {
						default: r(() => [g("span", { class: b(["em-tone", `is-${ce(t.status)}`]) }, [i[41] ||= g("i", { "aria-hidden": "true" }, null, -1), E(m(w(U)[t.status || ""] || t.status || "状态记录缺失"), 1)], 2)]),
						_: 2
					}, 1032, ["text"])]),
					g("td", null, [c(L, {
						text: w(le)[t.usage_state || t.status || ""] || t.usage_state || t.status || "状态记录缺失",
						secondary: t.usage_state === "bound" && t.registered_account_id ? `账号 #${t.registered_account_id}` : void 0
					}, {
						default: r(() => [g("span", { class: b(["em-tone", `is-${W(t.usage_state || t.status)}`]) }, [i[42] ||= g("i", { "aria-hidden": "true" }, null, -1), E(m(w(le)[t.usage_state || t.status || ""] || t.usage_state || t.status || "状态记录缺失"), 1)], 2)]),
						_: 2
					}, 1032, ["text", "secondary"])]),
					g("td", null, [c(R, {
						label: w(Y)(t).text,
						title: w(Y)(t).detail,
						tone: G(t)
					}, {
						details: r(() => [E(m(w(Y)(t).detail), 1)]),
						_: 2
					}, 1032, [
						"label",
						"title",
						"tone"
					])]),
					g("td", null, [c(R, v({ ref_for: !0 }, {
						label: w(B)(X(t)).text,
						secondary: w(B)(X(t)).secondary
					}, { title: pe(t) }), {
						details: r(() => [E(m(pe(t)), 1)]),
						_: 2
					}, 1040, ["title"])]),
					g("td", null, [F(t) ? (n(), h(R, {
						key: 0,
						"data-email-note": "",
						label: w(fe)(t),
						title: F(t),
						tone: t.service_sync_error ? "danger" : "neutral"
					}, {
						details: r(() => [E(m(F(t)), 1)]),
						_: 2
					}, 1032, [
						"label",
						"title",
						"tone"
					])) : (n(), h(L, {
						key: 1,
						text: "—"
					}))]),
					g("td", null, [g("div", mt, [
						g("button", {
							class: "ui-link",
							disabled: w(l).busy,
							onClick: (n) => e.owner.copyRow(t)
						}, "复制素材", 8, ht),
						g("button", {
							class: "ui-link ui-link--danger",
							disabled: w(l).busy,
							onClick: (n) => e.owner.rowAction(t, "delete")
						}, "删除", 8, gt),
						["replaced", "pending_sync"].includes(t.status || "") ? u("", !0) : (n(), h(w(P), {
							key: 0,
							open: S.value === w(K)(t),
							modal: !1,
							"onUpdate:open": (e) => S.value = e ? w(K)(t) : null
						}, {
							default: r(() => [c(w(ee), { "as-child": "" }, {
								default: r(() => [g("button", {
									type: "button",
									class: "ui-link",
									disabled: w(l).busy,
									"aria-label": `更多邮箱操作 ${t.email}`
								}, "更多", 8, _t)]),
								_: 2
							}, 1024), c(w(te), null, {
								default: r(() => [c(w(ne), {
									class: "em-row-menu",
									"aria-label": `${t.email} 的更多操作`,
									side: "bottom",
									align: "end",
									"side-offset": 6,
									"collision-padding": 10,
									"hide-when-detached": "",
									onOpenAutoFocus: i[36] ||= y(() => {}, ["prevent"])
								}, {
									default: r(() => [(n(!0), T(d, null, o(ue(t), ([e, r]) => (n(), T("button", {
										key: e,
										type: "button",
										class: b({ "is-danger": e === "failed" }),
										disabled: w(l).busy,
										onClick: (n) => J(t, e)
									}, m(r), 11, vt))), 128))]),
									_: 2
								}, 1032, ["aria-label"])]),
								_: 2
							}, 1024)]),
							_: 2
						}, 1032, ["open", "onUpdate:open"]))
					])])
				], 2))), 128)), w(l).items.length ? u("", !0) : (n(), h(I, {
					key: 0,
					colspan: 9,
					loading: w(l).loading,
					error: w(l).error ? " " : "",
					"loading-title": "正在加载邮箱资源…",
					"error-title": "邮箱资源加载失败",
					title: "暂无邮箱资源",
					text: "调整筛选条件或导入新的邮箱资源。"
				}, null, 8, ["loading", "error"]))])
			], 4)], 544),
			c(z, {
				compact: "",
				page: w(l).page,
				size: w(l).size,
				total: w(l).total,
				busy: w(l).loading,
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
		], 8, Ze));
	}
}), bt = {
	key: 0,
	class: "em-receipt",
	role: "status"
}, xt = /* @__PURE__ */ t({
	__name: "EmailReceipt",
	props: { receipt: {} },
	setup(e) {
		return (t, i) => e.receipt ? (n(), T("div", bt, [c(R, {
			label: e.receipt.label,
			title: e.receipt.detail,
			tone: e.receipt.tone
		}, {
			details: r(() => [E(m(e.receipt.detail), 1)]),
			_: 1
		}, 8, [
			"label",
			"title",
			"tone"
		])])) : u("", !0);
	}
}), St = ["aria-busy"], Ct = { class: "ui-list-count" }, wt = ["disabled"], Tt = {
	key: 0,
	class: "ui-list-feedback is-error",
	role: "alert"
}, Et = {
	class: "ui-table-scroll",
	tabindex: "0",
	"aria-label": "历史子邮箱列表，可横向滚动"
}, Dt = { class: "ui-col-check" }, Ot = [
	"checked",
	"indeterminate",
	"disabled"
], kt = { class: "ui-col-check" }, At = [
	"aria-label",
	"checked",
	"onChange"
], jt = { class: "em-source" }, Mt = /* @__PURE__ */ t({
	__name: "EmailHistory",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(e) {
		let t = e, i = t.owner.state, a = ae({
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
		}), s = x(() => i.items.filter((e) => i.selected.has(String(e.id))).length), l = [{
			value: "icloud_hide",
			label: "iCloud 隐藏邮箱"
		}, {
			value: "outlook",
			label: "Outlook"
		}], p = Object.entries(W).map(([e, t]) => ({
			value: e,
			label: t
		}));
		function _(e) {
			return {
				available: "success",
				reserved: "active",
				used: "active",
				replaced: "warning",
				retired: "neutral",
				disabled: "neutral"
			}[e || ""] || "neutral";
		}
		function y(e) {
			return {
				outlook: "#377dff",
				generic_api: "#7c5cf0",
				cloudflare_domain: "#e08a1e",
				icloud_hide: "#0e9aa7",
				email_butler: "#1f9d75"
			}[e] || "#98a2b3";
		}
		let S = x(() => Object.entries(i.filters).filter(([e, t]) => t && (e !== "source" || t !== "all")).map(([e, t]) => ({
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
			}[e]}：${e === "source" ? H[t] || t : e === "state" ? W[t] || t : e === "parent_id" ? i.parentEmail || `#${t}` : t}`,
			removeLabel: `移除${e}筛选`
		})));
		function C(e) {
			e === "parent_id" ? t.owner.clearParent() : t.owner.updateFilters({ [e]: e === "source" ? "all" : "" });
		}
		return (t, x) => (n(), T("section", {
			class: "ui-list em-list",
			"aria-label": "历史子邮箱",
			"aria-busy": w(i).loading
		}, [
			x[30] ||= g("p", { class: "ui-list-note" }, "子邮箱由你手动准备并导入本地库存；此处可查看、筛选和复制已有记录，Turb 不会自动生成。", -1),
			c(oe, {
				"data-email-count-row": "",
				filtered: S.value.length > 0
			}, {
				actions: r(() => [
					S.value.length ? (n(), T("button", {
						key: 0,
						class: "ui-link",
						onClick: x[0] ||= (t) => e.owner.resetFilters()
					}, "清筛")) : u("", !0),
					g("button", {
						class: "ui-button",
						disabled: !w(i).items.length && !w(i).selected.size,
						onClick: x[1] ||= (t) => e.owner.copy()
					}, m(w(i).selected.size ? "复制选中" : "复制当前页"), 9, wt),
					g("button", {
						class: "ui-link",
						onClick: x[2] ||= (...e) => w(a).resetColumns && w(a).resetColumns(...e)
					}, "恢复列宽")
				]),
				default: r(() => [g("span", Ct, [E(m(w(i).total) + " 条历史记录", 1), g("small", null, "当前页 " + m(w(i).items.length) + " 条" + m(w(i).selected.size ? ` · 已选 ${w(i).selected.size}` : ""), 1)]), c(re, {
					items: S.value,
					onRemove: C
				}, null, 8, ["items"])]),
				_: 1
			}, 8, ["filtered"]),
			w(i).error ? (n(), T("div", Tt, [E(m(w(i).error) + " ", 1), g("button", {
				class: "ui-link",
				onClick: x[3] ||= (t) => e.owner.refresh()
			}, "重试")])) : u("", !0),
			c(xt, { receipt: w(i).receipt }, null, 8, ["receipt"]),
			g("div", Et, [g("table", {
				class: "ui-table em-table",
				style: f({ "--ui-table-width": `${w(a).total.value}px` })
			}, [
				g("colgroup", null, [(n(!0), T(d, null, o(w(a).widths.value, (e, t) => (n(), T("col", {
					key: t,
					style: f({ width: `${e}px` })
				}, null, 4))), 128))]),
				g("thead", null, [g("tr", null, [
					g("th", Dt, [g("input", {
						type: "checkbox",
						"aria-label": "全选当前页子邮箱",
						checked: !!w(i).items.length && s.value === w(i).items.length,
						indeterminate: s.value > 0 && s.value < w(i).items.length,
						disabled: !w(i).items.length,
						onChange: x[4] ||= (t) => e.owner.togglePage(t.target.checked)
					}, null, 40, Ot), c(V, {
						label: "选择",
						onStart: x[5] ||= (e) => w(a).resize(0, e),
						onNudge: x[6] ||= (e) => w(a).resizeWithKeyboard(0, e)
					})]),
					g("th", null, [c($, {
						label: "子邮箱",
						value: w(i).filters.q,
						active: e.active,
						onChange: x[7] ||= (t) => e.owner.updateFilters({ q: t })
					}, null, 8, ["value", "active"]), c(V, {
						label: "子邮箱",
						onStart: x[8] ||= (e) => w(a).resize(1, e),
						onNudge: x[9] ||= (e) => w(a).resizeWithKeyboard(1, e)
					})]),
					g("th", null, [c($, {
						label: "母邮箱",
						value: w(i).filters.parent_q,
						active: e.active,
						onChange: x[10] ||= (t) => e.owner.updateFilters({ parent_q: t })
					}, null, 8, ["value", "active"]), c(V, {
						label: "母邮箱",
						onStart: x[11] ||= (e) => w(a).resize(2, e),
						onNudge: x[12] ||= (e) => w(a).resizeWithKeyboard(2, e)
					})]),
					g("th", null, [c($, {
						label: "来源",
						value: w(i).filters.source,
						"empty-value": "all",
						options: l,
						active: e.active,
						onChange: x[13] ||= (t) => e.owner.updateFilters({ source: t })
					}, null, 8, ["value", "active"]), c(V, {
						label: "来源",
						onStart: x[14] ||= (e) => w(a).resize(3, e),
						onNudge: x[15] ||= (e) => w(a).resizeWithKeyboard(3, e)
					})]),
					g("th", null, [c($, {
						label: "状态",
						value: w(i).filters.state,
						options: w(p),
						active: e.active,
						onChange: x[16] ||= (t) => e.owner.updateFilters({ state: t })
					}, null, 8, [
						"value",
						"options",
						"active"
					]), c(V, {
						label: "状态",
						onStart: x[17] ||= (e) => w(a).resize(4, e),
						onNudge: x[18] ||= (e) => w(a).resizeWithKeyboard(4, e)
					})]),
					g("th", null, [c($, {
						label: "关联账号 / 任务",
						value: w(i).filters.related_q,
						active: e.active,
						onChange: x[19] ||= (t) => e.owner.updateFilters({ related_q: t })
					}, null, 8, ["value", "active"]), c(V, {
						label: "关联账号 / 任务",
						onStart: x[20] ||= (e) => w(a).resize(5, e),
						onNudge: x[21] ||= (e) => w(a).resizeWithKeyboard(5, e)
					})]),
					g("th", null, [c($, {
						label: "生成时间",
						type: "range",
						value: w(i).filters.created_from,
						"end-value": w(i).filters.created_to,
						active: e.active,
						onChange: x[22] ||= (t) => e.owner.updateFilters({ created_from: t }),
						onEnd: x[23] ||= (t) => e.owner.updateFilters({ created_to: t })
					}, null, 8, [
						"value",
						"end-value",
						"active"
					]), c(V, {
						label: "生成时间",
						onStart: x[24] ||= (e) => w(a).resize(6, e),
						onNudge: x[25] ||= (e) => w(a).resizeWithKeyboard(6, e)
					})]),
					g("th", null, [x[28] ||= E("操作", -1), c(V, {
						label: "操作",
						onStart: x[26] ||= (e) => w(a).resize(7, e),
						onNudge: x[27] ||= (e) => w(a).resizeWithKeyboard(7, e)
					})])
				])]),
				g("tbody", null, [(n(!0), T(d, null, o(w(i).items, (t) => (n(), T("tr", {
					key: String(t.id),
					class: b({ "is-selected": w(i).selected.has(String(t.id)) })
				}, [
					g("td", kt, [g("input", {
						type: "checkbox",
						"aria-label": `选择历史子邮箱 ${t.email}`,
						checked: w(i).selected.has(String(t.id)),
						onChange: (n) => e.owner.toggle(t, n.target.checked)
					}, null, 40, At)]),
					g("td", null, [c(L, { text: t.email }, null, 8, ["text"])]),
					g("td", null, [c(L, {
						text: t.parent_email || "—",
						secondary: `母资源 #${t.parent_id || "—"}`
					}, null, 8, ["text", "secondary"])]),
					g("td", null, [c(L, { text: w(H)[t.source] || t.source }, {
						default: r(() => [g("span", jt, [g("i", {
							style: f({ background: y(t.source) }),
							"aria-hidden": "true"
						}, null, 4), E(m(w(H)[t.source] || t.source), 1)])]),
						_: 2
					}, 1032, ["text"])]),
					g("td", null, [c(L, { text: w(W)[t.state || ""] || t.state || "状态记录缺失" }, {
						default: r(() => [g("span", { class: b(["em-tone", `is-${_(t.state)}`]) }, [x[29] ||= g("i", { "aria-hidden": "true" }, null, -1), E(m(w(W)[t.state || ""] || t.state || "状态记录缺失"), 1)], 2)]),
						_: 2
					}, 1032, ["text"])]),
					g("td", null, [c(L, { text: w(de)(t) }, null, 8, ["text"])]),
					g("td", null, [c(L, v({ ref_for: !0 }, w(B)(t.created_at)), null, 16)]),
					g("td", null, [c(L, { text: "只读" })])
				], 2))), 128)), w(i).items.length ? u("", !0) : (n(), h(I, {
					key: 0,
					colspan: 8,
					loading: w(i).loading,
					error: w(i).error ? " " : "",
					"loading-title": "正在读取历史子邮箱…",
					"error-title": "子邮箱历史加载失败",
					title: "当前筛选下没有历史子地址",
					text: "请从 Email Butler 等来源手动准备邮箱，再导入本地库存。"
				}, null, 8, ["loading", "error"]))])
			], 4)]),
			c(z, {
				page: w(i).page,
				size: w(i).size,
				total: w(i).total,
				busy: w(i).loading,
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
		], 8, St));
	}
}), Nt = ["aria-busy"], Pt = { class: "em-dialog-head" }, Ft = { class: "em-dialog-body" }, It = {
	key: 0,
	class: "em-error",
	role: "alert"
}, Lt = { class: "em-field" }, Rt = ["value", "disabled"], zt = ["value"], Bt = { class: "em-field" }, Vt = [
	"value",
	"placeholder",
	"disabled"
], Ht = { class: "em-help" }, Ut = {
	key: 1,
	class: "em-field"
}, Wt = ["value", "disabled"], Gt = {
	key: 2,
	class: "em-preview",
	"aria-label": "导入前检查"
}, Kt = { class: "em-stats" }, qt = { key: 0 }, Jt = { key: 1 }, Yt = { class: "em-dialog-foot" }, Xt = ["disabled"], Zt = ["disabled"], Qt = /* @__PURE__ */ t({
	__name: "EmailLocalImport",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(e) {
		let t = e, r = t.owner.state, i = p();
		return se(i, () => r.open, () => t.active), (t, a) => (n(), T("dialog", {
			ref_key: "dialog",
			ref: i,
			class: "em-dialog",
			"data-email-local-import": "",
			"aria-labelledby": "emailLocalImportTitle",
			"aria-busy": w(r).busy || w(r).loading,
			onCancel: a[7] ||= y((t) => e.owner.close(), ["prevent"]),
			onClick: a[8] ||= (t) => t.target === i.value && e.owner.close()
		}, [
			g("div", Pt, [a[9] ||= g("div", null, [g("h3", { id: "emailLocalImportTitle" }, "导入邮箱资源"), g("p", null, "手动补充本地库存；Outlook 和通用 API 保留原格式，Butler 类型每行粘贴一个完整 iCloud HME 地址。")], -1), g("button", {
				class: "em-button",
				"aria-label": "关闭邮箱导入",
				onClick: a[0] ||= (t) => e.owner.close()
			}, "关闭")]),
			g("div", Ft, [
				c(xt, { receipt: w(r).receipt }, null, 8, ["receipt"]),
				w(r).error ? (n(), T("p", It, m(w(r).error), 1)) : u("", !0),
				g("label", Lt, [a[10] ||= E("导入类型", -1), g("select", {
					"aria-label": "导入类型",
					value: w(r).source,
					disabled: w(r).busy,
					onChange: a[1] ||= (t) => e.owner.update({ source: t.target.value })
				}, [(n(!0), T(d, null, o(w(Q), (e, t) => (n(), T("option", {
					key: t,
					value: t
				}, m(e.label), 9, zt))), 128))], 40, Rt)]),
				a[16] ||= g("p", { class: "em-help" }, "注册任务只领取本地可用库存；Butler 导入会交接原地址，不自动生成邮箱。", -1),
				g("label", Bt, [a[11] ||= E("邮箱资源", -1), g("textarea", {
					"aria-label": "邮箱资源",
					value: w(r).text,
					placeholder: w(Q)[w(r).source].placeholder,
					disabled: w(r).busy,
					onInput: a[2] ||= (t) => e.owner.update({ text: t.target.value })
				}, null, 40, Vt)]),
				g("p", Ht, m(w(Q)[w(r).source].hint), 1),
				w(r).source === "generic_api" ? (n(), T("label", Ut, [
					a[12] ||= E("批次有效期（可选）", -1),
					g("input", {
						"aria-label": "批次有效期",
						type: "text",
						value: w(r).expiresAt,
						disabled: w(r).busy,
						placeholder: "2026-12-01T12:00:00+08:00",
						onInput: a[3] ||= (t) => e.owner.update({ expiresAt: t.target.value })
					}, null, 40, Wt),
					a[13] ||= g("small", null, "只补充未在第三字段填写有效期的通用 API 邮箱；留空保留旧两段格式，不会推算有效期。", -1)
				])) : u("", !0),
				w(r).preview ? (n(), T("section", Gt, [
					a[15] ||= g("strong", null, "导入前检查", -1),
					g("div", Kt, [(n(!0), T(d, null, o([
						["输入行数", w(r).preview.total_lines],
						["可解析", w(r).preview.valid],
						["可新增", w(r).preview.new],
						["已存在", w(r).preview.existing],
						["输入重复", w(r).preview.duplicate_in_input],
						["无效行", w(r).preview.invalid]
					], (e) => (n(), T("div", { key: String(e[0]) }, [g("strong", null, m(e[1] || 0), 1), g("span", null, m(e[0]), 1)]))), 128))]),
					w(r).preview.extra_fields ? (n(), T("p", qt, "检测到 " + m(w(r).preview.extra_fields) + " 个多余字段，导入时会忽略。", 1)) : u("", !0),
					w(r).preview.invalid_rows?.length ? (n(), T("details", Jt, [a[14] ||= g("summary", null, "无效行详情", -1), (n(!0), T(d, null, o(w(r).preview.invalid_rows, (e) => (n(), T("p", { key: e.line }, "第 " + m(e.line) + " 行：" + m(e.reason), 1))), 128))])) : u("", !0)
				])) : u("", !0)
			]),
			g("div", Yt, [
				g("button", {
					class: "em-button",
					onClick: a[4] ||= (t) => e.owner.close()
				}, "取消"),
				g("button", {
					class: "em-button",
					disabled: w(r).loading || w(r).busy,
					onClick: a[5] ||= (t) => e.owner.preview()
				}, m(w(r).loading ? "解析中…" : "解析预览"), 9, Xt),
				g("button", {
					class: "em-button em-primary",
					"data-local-submit": "",
					disabled: w(r).busy || w(r).loading || !w(r).text.trim() || !!w(r).preview && !w(r).preview.new,
					onClick: a[6] ||= (t) => e.owner.submit()
				}, m(w(r).busy ? "正在导入…" : "导入到邮箱池"), 9, Zt)
			])
		], 40, Nt));
	}
}), $t = ["aria-busy"], en = { class: "em-dialog-head" }, tn = { id: "emailButlerImportDescription" }, nn = { class: "em-dialog-body" }, rn = {
	key: 0,
	class: "em-dialog-fields"
}, an = { class: "em-field" }, on = ["value", "disabled"], sn = ["value"], cn = { class: "em-field" }, ln = ["value", "disabled"], un = {
	key: 1,
	class: "em-error",
	role: "alert"
}, dn = {
	key: 2,
	role: "status",
	"aria-live": "polite"
}, fn = {
	key: 3,
	class: "em-preview",
	"aria-label": "Butler 导入结果"
}, pn = ["max", "value"], mn = { class: "em-stats" }, hn = {
	role: "status",
	"aria-live": "polite"
}, gn = { class: "em-help em-preserve-lines" }, _n = { key: 1 }, vn = { key: 2 }, yn = { key: 3 }, bn = { class: "em-dialog-foot" }, xn = ["disabled"], Sn = ["disabled"], Cn = ["disabled"], wn = ["disabled"], Tn = /* @__PURE__ */ t({
	__name: "EmailButlerImport",
	props: {
		owner: {},
		active: { type: Boolean }
	},
	setup(e) {
		let t = e, i = t.owner.state, a = p();
		se(a, () => i.open, () => t.active);
		let s = x(() => Number(i.batch?.imported || 0) + Number(i.batch?.skipped || 0) + Number(i.batch?.failed || 0) + Number(i.batch?.unknown || 0)), l = x(() => t.active && !!i.request && !i.open && ![
			"completed",
			"succeeded",
			"done",
			"cancelled"
		].includes(i.batch?.status || ""));
		return (t, f) => (n(), T(d, null, [l.value ? (n(), T("button", {
			key: 0,
			class: "em-recovery em-button",
			"aria-label": "查看 Butler 导入进度",
			onClick: f[0] ||= (t) => e.owner.open()
		}, m(w(i).batch ? `Butler 导入${e.owner.isRunning.value ? "中" : "结果"} · 已导入 ${w(i).batch.imported || 0} / ${w(i).batch.total || 0} · 查看进度` : "Butler 导入请求响应缺失 · 查看进度"), 1)) : u("", !0), g("dialog", {
			ref_key: "dialog",
			ref: a,
			class: "em-dialog",
			"data-email-butler-import": "",
			"aria-labelledby": "emailButlerImportTitle",
			"aria-describedby": "emailButlerImportDescription",
			"aria-busy": w(i).busy || w(i).polling,
			onCancel: f[10] ||= y((t) => e.owner.close(), ["prevent"]),
			onClick: f[11] ||= (t) => t.target === a.value && e.owner.close()
		}, [
			g("div", en, [g("div", null, [f[12] ||= g("h3", { id: "emailButlerImportTitle" }, "从 Butler 导入邮箱", -1), g("p", tn, m(w(i).request ? "导入进度会自动保存，可随时关闭窗口。" : "从 Butler 分配长期租用的邮箱，加入本地库存后使用。"), 1)]), g("button", {
				class: "em-button",
				"aria-label": "关闭 Butler 导入窗口",
				onClick: f[1] ||= (t) => e.owner.close()
			}, "关闭")]),
			g("div", nn, [
				w(i).request ? u("", !0) : (n(), T("div", rn, [
					g("label", an, [f[13] ||= E("邮箱类型", -1), g("select", {
						"aria-label": "Butler 邮箱类型",
						value: w(i).filters.provider,
						disabled: w(i).storageError || w(i).busy,
						onChange: f[2] ||= (t) => e.owner.changeFilters({ provider: t.target.value })
					}, [(n(!0), T(d, null, o(w(i).providers, (e) => (n(), T("option", {
						key: e.value,
						value: e.value
					}, m(e.label), 9, sn))), 128))], 40, on)]),
					g("label", cn, [f[14] ||= E("导入数量", -1), g("input", {
						"aria-label": "Butler 导入数量",
						type: "number",
						min: "1",
						step: "1",
						inputmode: "numeric",
						value: w(i).filters.count,
						disabled: w(i).storageError || w(i).busy,
						onInput: f[3] ||= (t) => e.owner.changeFilters({ count: Number(t.target.value) })
					}, null, 40, ln)]),
					f[15] ||= g("p", { class: "em-help" }, "不足时按预览可用数量导入，确认后由 Butler 分配完整地址。", -1)
				])),
				w(i).error ? (n(), T("p", un, m(w(i).error), 1)) : u("", !0),
				w(i).request ? u("", !0) : (n(), T("p", dn, m(w(i).previewing ? "正在查询当前可用数量…" : e.owner.availability.value), 1)),
				w(i).request ? (n(), T("section", fn, [
					g("h4", null, m(e.owner.batchTitle.value), 1),
					w(i).batch ? (n(), T(d, { key: 0 }, [
						g("progress", {
							max: Math.max(Number(w(i).batch.total || 0), 1),
							value: Math.min(s.value, Number(w(i).batch.total || 0)),
							"aria-label": "邮箱导入进度"
						}, null, 8, pn),
						g("div", mn, [(n(!0), T(d, null, o([
							["已导入", w(i).batch.imported],
							["待处理", w(i).batch.pending],
							["租用中", w(i).batch.submitting],
							["已跳过", w(i).batch.skipped],
							["失败", Number(w(i).batch.failed || 0) + Number(w(i).batch.unknown || 0)]
						], (e) => (n(), T("div", { key: String(e[0]) }, [g("strong", null, m(e[1] || 0), 1), g("span", null, m(e[0]), 1)]))), 128))]),
						g("p", hn, "已处理 " + m(s.value) + " / " + m(w(i).batch.total || 0) + " 个，本次请求 " + m(w(i).batch.requested || 0) + " 个。", 1)
					], 64)) : u("", !0),
					c(R, {
						label: w(ue)(e.owner.batchTitle.value),
						title: e.owner.batchDetails.value,
						tone: w(i).batch?.status === "cancelled" ? "neutral" : w(i).batch?.failed ? "warning" : "active"
					}, {
						details: r(() => [E(m(e.owner.batchDetails.value), 1)]),
						_: 1
					}, 8, [
						"label",
						"title",
						"tone"
					]),
					g("p", gn, m(w(i).batch?.status === "cancelled" ? "已停止后续导入，原结果与租约保留。" : e.owner.isRunning.value || w(i).resumePending ? "可以关闭窗口，导入会在后台继续。" : w(i).batch?.can_retry ? "可继续原批次处理剩余邮箱，已导入的邮箱会保留。" : "已保存原导入记录。"), 1),
					w(i).request.filters ? (n(), T("small", _n, "来源：" + m(w(ge).find((e) => e.value === w(i).request?.filters?.provider)?.label || w(i).request.filters.provider) + " · 原请求数量 " + m(w(i).request.filters.count), 1)) : u("", !0),
					w(i).batch ? (n(), T("small", vn, "批次：" + m(w(i).batch.batch_id), 1)) : u("", !0),
					w(i).request ? (n(), T("small", yn, "原请求：" + m(w(i).request.request_id), 1)) : u("", !0)
				])) : u("", !0)
			]),
			g("div", bn, [
				g("button", {
					class: "em-button",
					onClick: f[4] ||= (t) => e.owner.close()
				}, m(e.owner.isRunning.value || w(i).resumePending ? "关闭，后台继续" : "关闭"), 1),
				e.owner.canCancel.value ? (n(), T("button", {
					key: 0,
					class: "em-button em-danger",
					disabled: w(i).busy,
					onClick: f[5] ||= (t) => e.owner.cancel()
				}, m(w(i).busy ? "正在终止…" : "终止批次"), 9, xn)) : u("", !0),
				e.owner.canReset.value ? (n(), T("button", {
					key: 1,
					class: "em-button",
					disabled: w(i).busy || w(i).polling,
					onClick: f[6] ||= (t) => e.owner.reset()
				}, "新建导入", 8, Sn)) : u("", !0),
				w(i).request ? e.owner.canRetry.value ? (n(), T("button", {
					key: 3,
					class: "em-button em-primary",
					onClick: f[9] ||= (t) => e.owner.retry()
				}, m(w(i).batch ? "继续原批次" : "重试原请求"), 1)) : u("", !0) : (n(), T(d, { key: 2 }, [g("button", {
					class: "em-button",
					disabled: w(i).busy || w(i).previewing || w(i).storageError,
					onClick: f[7] ||= (t) => e.owner.preview()
				}, "刷新可用数量", 8, Cn), g("button", {
					class: "em-button em-primary",
					disabled: w(i).busy || w(i).previewing || w(i).storageError || !w(i).preview?.selected,
					onClick: f[8] ||= (t) => e.owner.apply()
				}, m(w(i).preview?.selected ? `开始导入 ${w(i).preview.selected} 个` : "开始导入"), 9, wn)], 64))
			])
		], 40, $t)], 64));
	}
}), En = { class: "em-page" }, Dn = /* @__PURE__ */ t({
	__name: "EmailPageShell",
	props: {
		api: {},
		deps: {},
		initialView: {},
		initialVisible: { type: Boolean }
	},
	setup(e, { expose: t }) {
		let r = e, i = p(r.initialView || "overview"), o = p(r.initialVisible || !1), l = p(!document.hidden), u = s({
			sources: [],
			expanded: !1,
			loading: !1,
			error: ""
		}), d = X(u, async (e, t) => {
			let n = await r.api.overview(e);
			t() && (u.sources = n.email?.supply?.sources || n.email?.sources || []);
		}), f = pe(r.api, r.deps), m = me(r.api, r.deps), h = {
			...r.deps,
			async onInventoryChanged() {
				f.refresh(), m.refresh(), d.refresh(), await r.deps.onInventoryChanged();
			}
		}, g = he(r.api, h), v = we(r.api, h, { storage: {
			getItem: (e) => localStorage.getItem(e),
			setItem: (e, t) => localStorage.setItem(e, t),
			removeItem: (e) => localStorage.removeItem(e)
		} }), y = x(() => v.state.request ? v.isRunning.value ? `Butler 导入中 · ${v.state.batch?.imported || 0}/${v.state.batch?.total || 0}` : "查看 Butler 导入" : "从 Butler 导入");
		function b() {
			let e = o.value && l.value;
			d.setActive(e && i.value === "overview"), f.setActive(e && i.value === "list"), m.setActive(e && i.value === "derivations"), g.setActive(e), v.setActive(e);
		}
		function S() {
			g.close(), v.close();
		}
		function E(e) {
			[
				"overview",
				"list",
				"derivations"
			].includes(e) && i.value !== e && (i.value = e, S(), b());
		}
		function D(e) {
			o.value !== e && (o.value = e, e || S(), b());
		}
		function O(e) {
			e.id && (m.scopeParent({
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
			await v.open();
		}
		function M() {
			l.value = !document.hidden, b();
		}
		return document.addEventListener("visibilitychange", M), b(), _(() => {
			document.removeEventListener("visibilitychange", M), d.dispose(), f.dispose(), m.dispose(), g.dispose(), v.dispose();
		}), t({
			setView: E,
			setVisible: D,
			refreshOverview: d.refresh,
			refreshInventory: f.refresh,
			refreshHistory: m.refresh,
			refreshDerivationSummary: f.refreshDerivationSummary,
			openImport: A,
			openButlerImport: j,
			closeDialogs: S
		}), (e, t) => (n(), T("div", En, [
			a(c(Re, {
				sources: u.sources,
				expanded: u.expanded,
				loading: u.loading,
				error: u.error,
				"butler-label": y.value,
				onRefresh: t[0] ||= (e) => w(d).refresh(),
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
			]), [[C, i.value === "overview"]]),
			a(c(yt, {
				owner: w(f),
				active: o.value && l.value && i.value === "list",
				"butler-label": y.value,
				onLocalImport: t[3] ||= (e) => A(),
				onButlerImport: j,
				onParent: O
			}, null, 8, [
				"owner",
				"active",
				"butler-label"
			]), [[C, i.value === "list"]]),
			a(c(Mt, {
				owner: w(m),
				active: o.value && l.value && i.value === "derivations"
			}, null, 8, ["owner", "active"]), [[C, i.value === "derivations"]]),
			c(Qt, {
				owner: w(g),
				active: o.value && l.value
			}, null, 8, ["owner", "active"]),
			c(Tn, {
				owner: w(v),
				active: o.value && l.value
			}, null, 8, ["owner", "active"])
		]));
	}
});
// src/api/email.ts
function On(e = (e, t) => O(e, t, e.startsWith("/api/bulk-mutations/") || e === "/api/outlook/status-bulk" || e === "/api/outlook/delete-bulk" ? M : ce)) {
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
				used_date: i.used_date,
				usage: String(i.usage || "")
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
		bulkStatus: async (t, n) => j(await A(e, "/api/outlook/status-bulk", t, n), "email", "update"),
		delete: (e) => n("/api/outlook/delete", e),
		bulkDelete: async (t, n) => j(await A(e, "/api/outlook/delete-bulk", t, n), "email", "delete"),
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
function kn(e, t) {
	let n = S(Dn, {
		api: On(),
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
export { kn as mountEmail };
