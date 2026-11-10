// 账号列表与批量任务共用查询字段、值编码和旧接口兼容适配。
window.AccountQuery = (() => {
  const fields = [
    ['id', '账号 ID', 'accountIdFilterV2', 'text'],
    ['source', '邮箱来源', 'accountSourceFilterV2', 'select'],
    ['registration_driver', '注册驱动', 'accountRegistrationDriverFilterV2', 'select'],
    ['token', 'Token 状态', 'accountTokenFilterV2', 'select'],
    ['password', '账号密码', 'accountPasswordFilterV2', 'select'],
    ['promotion', '套餐优惠', 'accountTrialFilterV2', 'select'],
    ['totp', '2FA', 'accountTotpFilterV2', 'select'],
    ['risk', '封号邮件', 'accountRiskFilterV2', 'select'],
    ['codex', 'Codex 状态', 'accountCodexFilterV2', 'select'],
    ['account_status', '账号状态', 'accountStatusFilterV2', 'select'],
    ['email_status', '邮箱状态', 'accountEmailStatusFilterV2', 'select'],
  ].map(([key, label, controlId, type]) => ({key, label, controlId, type}));
  function values(value) {
    return [...new Set((Array.isArray(value) ? value : String(value || '').split(',')).map(String).filter(Boolean))].sort();
  }
  function normalize(raw = {}) {
    const filters = {};
    for (const field of fields) {
      const value = raw.filters?.[field.key] ?? raw[field.key];
      filters[field.key] = field.key === 'id' ? String(value || '').trim() : values(value);
    }
    filters.email = String(raw.filters?.email ?? raw.email ?? '').trim();
    return {schema_version: 1, entity: 'account', archived: String(raw.archived || '0'),
      q: String(raw.q || '').trim(),
      date_from: String(raw.date_from || ''), date_to: String(raw.date_to || ''),
      plan: values(raw.plan), filters, order: [{field: 'id', direction: 'desc'}],
      limit: raw.limit === '' || raw.limit == null ? null : Number(raw.limit)};
  }
  function fromLegacy(params) {
    return normalize(Object.fromEntries(params instanceof URLSearchParams ? params : new URLSearchParams(params)));
  }
  function toLegacy(raw, paging = {}) {
    const query = normalize(raw);
    const params = new URLSearchParams();
    Object.entries(paging).forEach(([key, value]) => params.set(key, String(value)));
    for (const key of ['archived', 'q', 'date_from', 'date_to']) params.set(key, query[key]);
    params.set('email', query.filters.email);
    params.set('plan', query.plan.join(','));
    fields.forEach(({key}) => params.set(key, Array.isArray(query.filters[key]) ? query.filters[key].join(',') : query.filters[key]));
    return params;
  }
  function fromAccountList() { return fromLegacy(accountListQueryParams()); }
  return {fields, values, normalize, fromLegacy, toLegacy, fromAccountList};
})();
