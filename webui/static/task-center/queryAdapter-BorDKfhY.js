// src/features/accounts/filterDefinitions.ts
var e = [
	{
		key: "id",
		label: "ID",
		kind: "text",
		placeholder: "#"
	},
	{
		key: "email",
		label: "邮箱 / 姓名",
		kind: "text",
		placeholder: "邮箱或姓名"
	},
	{
		key: "source",
		label: "来源",
		kind: "enum",
		group: "source"
	},
	{
		key: "registration_driver",
		label: "注册驱动",
		kind: "enum",
		group: "registration_driver",
		order: [
			"roxy",
			"roxy_oss",
			"protocol",
			"protocol_oss",
			"protocol_oss_2",
			"sentinel_rs",
			"cloakbrowser",
			"unknown"
		]
	},
	{
		key: "token",
		label: "Token",
		kind: "enum",
		group: "account_token",
		order: [
			"has",
			"expired",
			"invalid_401",
			"invalid_403",
			"invalid_other",
			"none"
		]
	},
	{
		key: "account_status",
		label: "账号状态",
		kind: "enum",
		group: "account_status",
		order: ["active", "deactivated"]
	},
	{
		key: "password",
		label: "账号密码",
		kind: "enum",
		group: "password"
	},
	{
		key: "plan",
		label: "套餐",
		kind: "enum",
		group: "plan"
	},
	{
		key: "promotion",
		label: "套餐优惠",
		kind: "enum",
		group: "promotion"
	},
	{
		key: "totp",
		label: "2FA",
		kind: "enum",
		group: "totp"
	},
	{
		key: "risk",
		label: "封号邮件",
		kind: "enum",
		group: "risk"
	},
	{
		key: "codex",
		label: "Codex",
		kind: "enum",
		group: "codex"
	},
	{
		key: "date",
		label: "创建 / 更新",
		kind: "date-range"
	},
	{
		key: "email_status",
		label: "邮箱状态",
		kind: "enum",
		group: "email_status",
		order: ["invalid", "unmarked"]
	}
];
function t(e, t) {
	return t === "plan" ? e.plan : t === "id" || t === "email" || t === "date" ? [] : e.filters[t];
}
function n(e, t) {
	return t === "date_from" || t === "date_to" ? e[t] : t === "id" || t === "email" ? e.filters[t] : "";
}
function r(e, r) {
	return r.kind === "date-range" ? !!(e.date_from || e.date_to) : r.kind === "text" ? !!n(e, r.key) : t(e, r.key).length > 0;
}
var i = [
	"none",
	"free_trial",
	"half_price",
	"go_50",
	"plus_50",
	"plus_50_1m",
	"plus_50_2m",
	"plus_50_3m"
];
function a(e, n, r, a) {
	let o = t(e, r.key), s = r.kind === "enum" && n[r.key] || [];
	if (r.key === "promotion") {
		let e = new Map(s.map((e) => [e.value, e.count]));
		return i.map((t) => ({
			value: t,
			count: e.get(t) ?? null,
			label: a("promotion", t)
		}));
	}
	let c = s.filter((e) => e.value && (e.count > 0 || o.includes(e.value))).map((e) => ({ ...e }));
	for (let e of o) c.some((t) => t.value === e) || c.push({
		value: e,
		count: 0
	});
	let l = r.order || [];
	return c.sort((e, t) => {
		let n = l.indexOf(e.value), r = l.indexOf(t.value);
		return (n < 0 ? l.length : n) - (r < 0 ? l.length : r);
	}), c.map((e) => ({
		...e,
		label: a(r.group || r.key, e.value)
	}));
}
function o(r, i) {
	return e.flatMap((e) => {
		let a = "";
		a = e.kind === "date-range" ? r.date_from && r.date_to ? `${r.date_from} 至 ${r.date_to}` : r.date_from ? `自 ${r.date_from}` : r.date_to ? `截至 ${r.date_to}` : "" : e.kind === "text" ? n(r, e.key) : t(r, e.key).map((t) => i(e.group || e.key, t)).join("、");
		let o = `${e.label}：${a}`;
		return a ? [{
			key: e.key,
			label: o,
			title: o,
			removeLabel: `清除${e.label}筛选`
		}] : [];
	});
}
// src/features/accounts/queryAdapter.ts
function s(e) {
	return {
		normalize: (t) => e.normalize(t),
		fromLegacy: (t) => e.fromLegacy(t),
		toLegacy: (t, n) => e.toLegacy(t, n)
	};
}
export { o as a, n as c, a as i, e as n, i as o, r, t as s, s as t };
