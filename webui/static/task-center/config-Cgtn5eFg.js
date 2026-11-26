// src/api/config.ts
var e = class extends Error {
	status;
	code;
	fields;
	constructor(e, t, n = "", r = {}) {
		super(e), this.status = t, this.code = n, this.fields = r, this.name = "ConfigApiError";
	}
}, t = (e) => e && typeof e == "object" && !Array.isArray(e) ? e : {}, n = (e) => JSON.parse(JSON.stringify(e));
function r(r) {
	if (!Array.isArray(r)) throw new e("配置字段响应格式无效", 0, "config_schema_invalid");
	let i = /* @__PURE__ */ new Set();
	return r.map((r) => {
		let a = t(r);
		if (typeof a.key != "string" || !a.key || typeof a.type != "string" || i.has(a.key)) throw new e("配置字段响应格式无效", 0, "config_schema_invalid");
		i.add(a.key);
		let o = n({
			...a,
			group: String(a.group || "其他"),
			label: String(a.label || a.key)
		});
		return o.secret && (o.value = "", "configured_value" in o && (o.configured_value = ""), "published_effective_value" in o && (o.published_effective_value = ""), delete o.default), o;
	});
}
function i(i = fetch) {
	let a = 0, o = null, s = null;
	async function c(n, r) {
		let a = await i(n, {
			credentials: "same-origin",
			...r
		});
		if (!(a.headers.get("content-type") || "").includes("application/json")) throw new e(a.status === 401 || a.redirected ? "登录已失效，请重新登录后刷新。" : "配置接口返回了非 JSON 响应", a.status);
		let o;
		try {
			o = await a.json();
		} catch {
			throw new e("配置接口返回了无效 JSON", a.status);
		}
		let s = t(o);
		if (!a.ok || s.ok === !1) {
			let n = t(s.error), r = {};
			for (let [e, i] of Object.entries(t(s.fields || n.fields))) typeof i == "string" && (r[e] = i);
			throw new e(typeof s.error == "string" ? s.error : String(n.message || s.message || `请求失败（HTTP ${a.status}）`), a.status, String(n.code || s.code || s.error_code || ""), r);
		}
		return o;
	}
	function l() {
		a++, o = null, s = null;
	}
	return {
		async getSchema(e = {}) {
			if (e.signal?.aborted) throw new DOMException("读取已取消", "AbortError");
			if (s?.generation === a) return n(await s.promise);
			if (!e.force && o && Date.now() - o.at < 3e4) return n(o.fields);
			let t = a, i = c("/api/config", { signal: e.signal }).then((e) => {
				let n = r(e);
				return a === t && (o = {
					fields: n,
					at: Date.now()
				}), n;
			});
			s = {
				generation: t,
				promise: i
			};
			try {
				return n(await i);
			} finally {
				s?.promise === i && (s = null);
			}
		},
		async save(n) {
			let r = await c("/api/config", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ updates: n })
			});
			if (!r || typeof r != "object" || Array.isArray(r) || !Array.isArray(t(r).updated) || !t(r).updated.every((e) => typeof e == "string")) throw new e("配置保存响应格式无效", 0, "config_save_response_invalid");
			return l(), r;
		},
		invalidate: l
	};
}
export { i as n, r, e as t };
