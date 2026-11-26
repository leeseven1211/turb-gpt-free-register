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
var i = {
	team: "Team",
	plus: "Plus",
	go: "Go",
	status: "状态",
	legacy: "兼容条件"
}, a = [
	"team",
	"plus",
	"go",
	"status",
	"legacy"
], o = [
	"none",
	"unknown",
	"pending",
	"failed",
	"not_applicable"
], s = /* @__PURE__ */ new Set([
	"free_trial",
	"half_price",
	"other_discount",
	"discount",
	"other_promo",
	"team_eligible",
	"plus_100",
	"plus_50",
	"plus_other",
	"go_100",
	"go_50",
	"go_other",
	"plus_50_1m",
	"plus_50_2m",
	"plus_50_3m"
]), c = new Set(o), l = /^offer_v1_[0-9a-f]{32}$/i;
function u(e, t) {
	let n = e[t];
	return Array.isArray(n) ? n : [];
}
function d(e, t, n = "") {
	if (t && Object.hasOwn(i, t)) return t;
	if (c.has(e)) return "status";
	if (l.test(e)) {
		let e = n.toLowerCase();
		if (/^team(?:\s|·|：|:)/.test(e)) return "team";
		if (/^plus(?:\s|·|：|:)/.test(e)) return "plus";
		if (/^go(?:\s|·|：|:)/.test(e)) return "go";
	}
	return "legacy";
}
function f(e, t = !1) {
	return l.test(e) ? t ? "已选优惠（信息暂不可用）" : "优惠信息暂不可用" : e;
}
function p(e, t, n = !1) {
	let r = String(e.value);
	return e.label ? String(e.label) : l.test(r) ? f(r, n) : String(t("promotion", r) || r);
}
function m(e, t) {
	let n = String(e.label || "").toLowerCase(), r = /免费|free(?:\s+trial)?/.test(n), i = /半价|五折|half[\s-]*price|50\s*%/.test(n), a = n.match(/(\d+(?:\.\d+)?)\s*%/), o = a ? Number(a[1]) : i ? 50 : r ? 100 : null, s = n.match(/(\d+(?:\.\d+)?)\s*(个?月|周|天|年|months?|weeks?|days?|years?)/), c = s ? Number(s[1]) : Infinity, l = s?.[2] || "", u = l.includes("年") || l.includes("year") ? c * 365 : l.includes("月") || l.includes("month") ? c * 30 : l.includes("周") || l.includes("week") ? c * 7 : (l.includes("天") || l.includes("day"), c);
	return [
		r ? 0 : o === null ? 2 : 1,
		o === null ? 0 : -o,
		u,
		n,
		t
	];
}
function h(e, n, r) {
	let i = new Set(t(e, "promotion")), a = u(n, "promotion"), o = a.some((e) => l.test(String(e.value || ""))), c = /* @__PURE__ */ new Map();
	for (let e of a) {
		let t = String(e.value || "");
		if (!t || !(Number(e.count || 0) > 0) && !i.has(t)) continue;
		let n = p(e, r, i.has(t));
		c.set(t, {
			...e,
			value: t,
			count: e.count == null ? 0 : Number(e.count),
			group: d(t, e.group, n),
			label: n
		});
	}
	for (let e of i) if (!c.has(e)) {
		let t = p({ value: e }, r, !0);
		c.set(e, {
			value: e,
			count: 0,
			group: d(e, void 0, t),
			label: t
		});
	}
	return [...c.values()].filter((e) => l.test(e.value) || !o || i.has(e.value) || e.group !== "legacy" && !s.has(e.value));
}
function g(e, n, r, s) {
	let c = t(e, r.key), l = r.kind === "enum" ? u(n, r.key) : [];
	if (r.key === "promotion") {
		let t = /* @__PURE__ */ new Map();
		for (let r of h(e, n, s)) {
			let e = d(r.value, r.group), n = t.get(e) || [];
			n.push({
				...r,
				group: e
			}), t.set(e, n);
		}
		for (let e of t.values()) {
			let t = e[0]?.group || "legacy";
			e.sort((n, r) => {
				if (t === "status") {
					let e = o.indexOf(n.value), t = o.indexOf(r.value);
					return (e < 0 ? o.length : e) - (t < 0 ? o.length : t);
				}
				if (t === "team" || t === "plus" || t === "go") {
					let t = m(n, e.indexOf(n)), i = m(r, e.indexOf(r));
					for (let e = 0; e < t.length; e++) if (t[e] !== i[e]) return t[e] < i[e] ? -1 : 1;
				}
				return 0;
			});
		}
		return a.filter((e) => t.has(e)).map((e) => ({
			key: e,
			label: i[e],
			options: t.get(e)
		}));
	}
	let f = l.filter((e) => e.value && (Number(e.count || 0) > 0 || c.includes(e.value))).map((e) => ({ ...e }));
	for (let e of c) f.some((t) => t.value === e) || f.push({
		value: e,
		count: 0
	});
	let p = r.order || [];
	return f.sort((e, t) => {
		let n = p.indexOf(e.value), r = p.indexOf(t.value);
		return (n < 0 ? p.length : n) - (r < 0 ? p.length : r);
	}), f.length ? [{
		key: r.group || r.key,
		label: "",
		options: f.map((e) => ({
			...e,
			label: e.label || s(r.group || r.key, e.value)
		}))
	}] : [];
}
function _(r, i, a) {
	return e.flatMap((e) => {
		let o = "";
		o = e.kind === "date-range" ? r.date_from && r.date_to ? `${r.date_from} 至 ${r.date_to}` : r.date_from ? `自 ${r.date_from}` : r.date_to ? `截至 ${r.date_to}` : "" : e.kind === "text" ? n(r, e.key) : t(r, e.key).map((t) => {
			let n = a && u(a, e.key).find((e) => e.value === t);
			return n?.label ? n.label : e.key === "promotion" && l.test(t) ? f(t, !0) : String(i(e.group || e.key, t) || t);
		}).join("、");
		let s = `${e.label}：${o}`;
		return o ? [{
			key: e.key,
			label: s,
			title: s,
			removeLabel: `清除${e.label}筛选`
		}] : [];
	});
}
// src/features/accounts/queryAdapter.ts
function v(e) {
	return {
		normalize: (t) => e.normalize(t),
		fromLegacy: (t) => e.fromLegacy(t),
		toLegacy: (t, n) => e.toLegacy(t, n)
	};
}
export { _ as a, g as i, e as n, t as o, r, n as s, v as t };
