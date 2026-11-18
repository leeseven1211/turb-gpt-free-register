// src/shared/time.ts
var e = new Intl.DateTimeFormat("zh-CN", {
	year: "numeric",
	month: "2-digit",
	day: "2-digit",
	hour: "2-digit",
	minute: "2-digit",
	second: "2-digit",
	hour12: !1
});
function t(t) {
	if (!t) return "—";
	let n = new Date(String(t));
	return Number.isNaN(n.getTime()) ? `无效时间：${String(t)}` : e.format(n);
}
function n(e) {
	let n = t(e), r = /^(\d{4}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})$/.exec(n);
	return r ? {
		text: r[1],
		secondary: r[2]
	} : { text: n };
}
export { t as n, n as t };
