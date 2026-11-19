// src/api/client.ts
var e = class extends Error {
	status;
	code;
	constructor(e, t, n = "") {
		super(e), this.status = t, this.code = n, this.name = "ApiError";
	}
};
async function t(t, n = {}, r) {
	let i = await fetch(t, {
		credentials: "same-origin",
		...n
	});
	if (!(i.headers.get("content-type") || "").includes("application/json")) throw new e(i.redirected || i.status === 401 ? "登录已失效，请重新登录后刷新。" : `服务返回了非 JSON 响应（HTTP ${i.status}）`, i.status);
	let a = r ? r(await i.text()) : await i.json();
	if (!i.ok || a?.ok === !1) {
		let t = a?.error;
		throw new e(typeof t == "string" ? t : t?.message || a?.message || `请求失败（HTTP ${i.status}）`, i.status, t?.code || a?.error_code || a?.code || "");
	}
	return a;
}
function n(e) {
	return e instanceof Error && e.name === "AbortError";
}
export { n, t as r, e as t };
