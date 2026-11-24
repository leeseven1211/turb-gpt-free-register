import { r as e, t } from "./client-B5R_MNgP.js";
import { r as n } from "./taskIds-BlchWwUp.js";
// src/api/bulkMutations.ts
var r = class extends Error {
	commandId;
	receipt;
	status;
	code;
	constructor(e, n, r) {
		super(`批量命令已受理，仍在执行或等待结果确认（命令 ${e}）。${r instanceof t ? `结果查询失败：${r.message}。` : ""}请在任务中心查看进度，勿重复提交。`, r === void 0 ? void 0 : { cause: r }), this.commandId = e, this.receipt = n, this.name = "BulkMutationPendingError", r instanceof t && (this.status = r.status, this.code = r.code);
	}
};
function i(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) throw Error("批量命令响应格式无效");
	let t = e;
	if (t.ok === !1) throw Error("批量命令查询失败");
	return t;
}
function a(e) {
	if (typeof e == "string" && /^[1-9]\d*$/.test(e)) return e;
	if (typeof e == "number" && Number.isSafeInteger(e) && e > 0) return String(e);
	throw Error("批量命令标识无效");
}
function o(e) {
	let t = [];
	for (let n of e.matchAll(/"(?:\\.|[^"\\])*"/g)) {
		let r = JSON.parse(n[0]);
		if (![
			"key",
			"id",
			"command_id"
		].includes(r)) continue;
		let i = n.index + n[0].length, a = /^\s*:\s*(\d+)(?=\s*[,}])/.exec(e.slice(i));
		if (a && !Number.isSafeInteger(Number(a[1]))) {
			let e = i + a[0].lastIndexOf(a[1]);
			t.push({
				start: e,
				end: e + a[1].length,
				text: JSON.stringify(a[1])
			});
		}
	}
	let r = "", i = 0;
	for (let n of t) r += e.slice(i, n.start) + n.text, i = n.end;
	return n(r + e.slice(i));
}
var s = (t, n) => e(t, n, o), c = /* @__PURE__ */ new Set([
	"success",
	"partial_success",
	"failed",
	"stopped",
	"cancelled",
	"interrupted",
	"deactivated",
	"unsupported",
	"attention_required",
	"terminated"
]);
async function l(e, t, n, o = {}) {
	let s = o.idempotencyKey || crypto.randomUUID(), l = i(await e(t, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"Idempotency-Key": s,
			...t.startsWith("/api/accounts/") ? { "X-Account-Request-Key": s } : {}
		},
		body: JSON.stringify(n),
		...o.signal ? { signal: o.signal } : {}
	}));
	if (l.accepted !== !0 && l.reused !== !0) return l;
	if (l.command_id == null) throw Error("服务端未返回可查询的批量命令标识，请刷新核实操作结果");
	let u = a(l.command_id), d = new AbortController();
	o.onAccepted?.(l);
	let f, p, m = () => new r(u, l), h = new Promise((e, t) => {
		p = () => {
			d.abort(), t(m());
		}, f = setTimeout(p, o.timeoutMs ?? 3e4), o.signal?.addEventListener("abort", p, { once: !0 });
	});
	o.signal?.aborted && p?.();
	let g = async (t) => {
		if (d.signal.aborted) throw m();
		let n = i(await e(t, { signal: d.signal }));
		if (d.signal.aborted) throw m();
		return n;
	}, _ = async () => {
		for (;;) {
			let e = await g(`/api/bulk-mutations/${encodeURIComponent(u)}`);
			if (e.command_id != null && a(e.command_id) !== u) throw Error("批量命令回执不匹配");
			if (c.has(String(e.status))) {
				if (!Array.isArray(e.items)) throw Error("批量命令缺少逐项回执");
				let t = [...e.items], n = e.next_offset, r = /* @__PURE__ */ new Set();
				for (; n != null;) {
					if (!Number.isSafeInteger(n) || n < 0 || r.has(n)) throw Error("批量命令回执分页无效");
					r.add(n);
					let e = await g(`/api/bulk-mutations/${encodeURIComponent(u)}?offset=${n}&limit=500`);
					if (e.command_id != null && a(e.command_id) !== u) throw Error("批量命令回执不匹配");
					if (!Array.isArray(e.items)) throw Error("批量命令缺少逐项回执");
					t.push(...e.items), n = e.next_offset;
				}
				return {
					...l,
					...e,
					accepted: !1,
					items: t
				};
			}
			if (await new Promise((e) => {
				let t = setTimeout(n, o.pollIntervalMs ?? 750);
				function n() {
					clearTimeout(t), d.signal.removeEventListener("abort", n), e();
				}
				d.signal.addEventListener("abort", n, { once: !0 });
			}), d.signal.aborted) throw m();
		}
	};
	try {
		return await Promise.race([_(), h]);
	} catch (e) {
		throw e instanceof r ? e : new r(u, l, e);
	} finally {
		f !== void 0 && clearTimeout(f), p && o.signal?.removeEventListener("abort", p);
	}
}
function u(e, t, n) {
	if (!Array.isArray(e.items)) return e;
	let r = (e) => {
		let n = e.data || {};
		if (t === "accounts") return {
			...n,
			id: a(e.key)
		};
		if (t === "codex") return {
			...n,
			filename: String(e.key)
		};
		let [r, ...i] = String(e.key).split(":");
		return {
			...n,
			source: typeof n.source == "string" ? n.source : r,
			email: typeof n.email == "string" ? n.email : i.join(":")
		};
	}, i = e.items.filter((e) => e.status === "updated").map(r), o = e.items.filter((e) => e.status !== "updated").map((e) => ({
		...r(e),
		reason_code: e.reason_code || void 0,
		reason: e.reason || "未完成"
	})), s = n === "delete" ? "deleted" : "updated";
	return {
		...e,
		[s]: t === "codex" && n === "delete" ? i.map((e) => e.filename) : i,
		[`${s}_count`]: i.length,
		skipped: o,
		skipped_count: o.length
	};
}
export { l as a, u as i, s as n, o as r, r as t };
