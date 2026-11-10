// 同一字段目录可挂载为账号列筛选或批次表单，不在界面重写业务谓词。
window.AccountFilters = (() => {
  const fallback = {
    source: [], registration_driver: ['roxy','roxy_oss','protocol','protocol_oss','protocol_oss_2','cloakbrowser','unknown'],
    token: ['has','expired','invalid_401','invalid_403','invalid_other','none'],
    password: ['has','none'], promotion: ['free_trial','half_price','other_discount','other_promo','none','unknown','pending','failed','not_applicable'],
    totp: ['enabled','disabled'], risk: ['detected','clear','pending'], codex: ['success','retrying','failed','stopped','deactivated','skipped','missing'],
    account_status: ['active','deactivated','unknown'], email_status: ['invalid','unmarked'], plan: ['free','plus','unqueried'],
  };
  function options(field, schema, selected) {
    const definitions = schema?.fields;
    const definition = Array.isArray(definitions) ? definitions.find(x => (x.key || x.name) === field.key) : definitions?.[field.key];
    const source = document.getElementById(field.controlId);
    const rows = Array.isArray(definition?.options) ? definition.options : Array.isArray(definition?.enum) ? definition.enum : Array.isArray(definition?.values) && definition.values.length ? definition.values :
      source?.options ? Array.from(source.options).filter(x => x.value).map(x => ({value: x.value, label: x.textContent.replace(/\s*·\s*\d+$/, '')})) : fallback[field.key] || [];
    const found = new Map();
    for (const row of rows) {
      const value = String(typeof row === 'object' ? row.value : row);
      if (!value) continue;
      const group = field.key === 'token' ? 'account_token' : field.key;
      const localLabel = field.key === 'email_status' ? ({invalid:'已标记失效',unmarked:'未标记失效'}[value]) : null;
      found.set(value, localLabel || (typeof row === 'object' ? row.label || facetLabel(group, value) : facetLabel(group, value)));
    }
    for (const value of selected) if (!found.has(value)) found.set(value, facetLabel(field.key, value));
    return [...found].map(([value, label]) => ({value, label}));
  }
  function mount(host, raw, schema, onChange) {
    const query = AccountQuery.normalize(raw);
    const allFields = [{key:'plan', label:'套餐', controlId:'accountPlanFilterV2', type:'select'}, ...AccountQuery.fields];
    host.innerHTML = `<div class="bulk-filter-grid">
      <label class="bulk-field">邮箱或姓名<input data-query="email" type="search" value="${attrEsc(query.filters.email)}" autocomplete="off"></label>
      <label class="bulk-field">高级搜索<input data-query="q" type="search" value="${attrEsc(query.q)}" placeholder="如：协议 jp" autocomplete="off"></label>
      <label class="bulk-field">创建日期从<input data-query="date_from" type="date" value="${attrEsc(query.date_from)}"></label>
      <label class="bulk-field">创建日期至（含当天）<input data-query="date_to" type="date" value="${attrEsc(query.date_to)}"></label>
      <label class="bulk-field">归档范围<select data-query="archived"><option value="0">未归档</option><option value="only">仅归档</option><option value="all">全部</option></select></label>
      ${allFields.map(field => {
        const selected = field.key === 'plan' ? query.plan : query.filters[field.key];
        if (field.type === 'text') return `<label class="bulk-field">${esc(field.label)}<input data-query-filter="${field.key}" value="${attrEsc(Array.isArray(selected) ? selected.join(',') : selected)}" inputmode="numeric" placeholder="账号 ID"></label>`;
        const rows = options(field, schema, selected);
        return `<fieldset class="bulk-filter-choice"><legend>${esc(field.label)}</legend><div class="bulk-filter-options">${rows.length ? rows.map(row => `<label><input type="checkbox" data-query-filter="${field.key}" value="${attrEsc(row.value)}" ${selected.includes(row.value) ? 'checked' : ''}><span>${esc(row.label)}</span></label>`).join('') : '<span class="bulk-muted">暂无可用选项</span>'}</div></fieldset>`;
      }).join('')}
    </div><p class="bulk-muted">同一字段多选满足其一，不同字段同时满足。日期、优惠、密码等条件与账号列表一致。</p>`;
    host.querySelector('[data-query="archived"]').value = query.archived;
    host.oninput = () => onChange(read(host));
    host.onchange = () => onChange(read(host));
  }
  function read(host) {
    const raw = {filters:{}};
    host.querySelectorAll('[data-query]').forEach(input => {raw[input.dataset.query] = input.value;});
    host.querySelectorAll('[data-query-filter]').forEach(input => {
      const key = input.dataset.queryFilter;
      if (!raw.filters[key]) raw.filters[key] = [];
      if (input.type === 'checkbox') { if (input.checked) raw.filters[key].push(input.value); }
      else raw.filters[key] = input.value;
    });
    raw.plan = raw.filters.plan || []; delete raw.filters.plan;
    return AccountQuery.normalize(raw);
  }
  return {mount, read};
})();
