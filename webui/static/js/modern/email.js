// ---------- 邮箱池 ----------
// 子地址库存与母资源分开管理，已领取地址始终保留原归属。
const EMAIL_DERIVATION_VIEW = {
  source: 'all', parentId: null, parentEmail: '', total: 0, summary: null, generation: 0,
  items: [], selected: new Map(), loading: false, updating: false,
  generationRequest: null, generationParentEmail: '', generating: false, generationFocus: null, restoreGenerationFocus: true,
};
const EMAIL_DERIVATION_STATE_LABELS = {
  available: '可领取', disabled: '已停用', reserved: '归属已保留', used: '已绑定账号', replaced: '换绑后地址', retired: '历史停用',
};
const EMAIL_DERIVATION_FILTERS = {
  q: 'emailDerivationQuery', parent_q: 'emailDerivationParentQuery', source: 'emailDerivationSourceFilter',
  state: 'emailDerivationStateFilter', related_q: 'emailDerivationRelatedQuery',
  created_from: 'emailDerivationCreatedFrom', created_to: 'emailDerivationCreatedTo',
};
function _poolDerivationCell(row) {
  const summary = EMAIL_DERIVATION_VIEW.summary;
  const recorded = (summary?.parents || []).find(item => item.source === row.source && String(item.parent_id) === String(row.id));
  const enabledSources = Array.isArray(summary?.sources) ? summary.sources : [];
  const parentPolicy = row.derivation_policy || {};
  const canShowDefault = summary?.enabled === true && enabledSources.includes(row.source)
    && ['icloud_hide', 'outlook'].includes(row.source) && Number(row.id) > 0 && parentPolicy.enabled !== false;
  // 首个子地址生成前没有聚合行，仍使用当前策略展示零用量和查看入口。
  const parent = recorded || (canShowDefault ? {parent_id: row.id, child_count: 0, max_children: parentPolicy.max_children} : null);
  if (!parent) return '';
  const count = Number(parent.child_count || 0);
  const maximum = Number(parent.max_children ?? summary.max_children ?? 3);
  return `<small class="pool-derivation-meta">原地址 · 子地址 ${count}/${maximum}</small><button type="button" class="pool-derivation-open" data-derivation-parent="${attrEsc(parent.parent_id)}" data-source="${attrEsc(row.source)}" data-parent-email="${attrEsc(row.email)}" aria-label="查看 ${attrEsc(row.email)} 的子地址">查看子地址</button>`;
}
function renderEmailDerivationSummary(summary) {
  EMAIL_DERIVATION_VIEW.summary = summary;
  if (typeof OUTLOOK !== 'undefined' && OUTLOOK.length) renderOutlook();
}
async function loadEmailDerivationSummary() {
  try {
    renderEmailDerivationSummary(await api('/api/email-derivation/summary?source=all'));
  } catch (error) {
    showToast('子地址额度读取失败：' + error.message);
  }
}
function updateEmailDerivationSelectionUi() {
  const state = EMAIL_DERIVATION_VIEW;
  const selected = Array.from(state.selected.values());
  const count = selected.length;
  const hint = document.getElementById('emailDerivationSelectedHint');
  if (hint) hint.textContent = count ? `已选 ${count} 个子邮箱` : '选择子邮箱后批量操作';
  document.getElementById('emailDerivationToolbar')?.classList.toggle('has-selection', count > 0);
  const copy = document.getElementById('btnCopyEmailDerivation');
  if (copy) {
    copy.textContent = count ? '复制选中' : '复制当前页';
    copy.disabled = count === 0 && state.items.length === 0;
  }
  const disable = document.getElementById('btnDisableEmailDerivation');
  if (disable) disable.disabled = state.updating || !selected.some(item => item.can_disable === true);
  const restore = document.getElementById('btnRestoreEmailDerivation');
  if (restore) restore.disabled = state.updating || !selected.some(item => item.can_restore === true);
  const all = document.getElementById('emailDerivationSelectAll');
  if (all) {
    const checked = state.items.filter(item => state.selected.has(Number(item.id))).length;
    all.checked = state.items.length > 0 && checked === state.items.length;
    all.indeterminate = checked > 0 && checked < state.items.length;
    all.disabled = state.items.length === 0;
  }
}
function renderEmailDerivationAllocations(result) {
  const state = EMAIL_DERIVATION_VIEW;
  state.total = Number(result.total || 0);
  state.items = Array.isArray(result.items) ? result.items : [];
  state.items.forEach(item => {
    if (state.selected.has(Number(item.id))) state.selected.set(Number(item.id), item);
  });
  const body = document.getElementById('emailDerivationBody');
  if (!body) return;
  body.innerHTML = state.items.map(item => {
    const id = Number(item.id);
    const bound = item.registered_account_id ? `账号 #${item.registered_account_id}` : '';
    const task = item.root_task_id ? `任务 #${item.root_task_id}` : '';
    const ownership = [bound, task].filter(Boolean).join(' · ') || (['available', 'disabled'].includes(item.state) ? '尚未领取' : '历史归属');
    const statusClass = item.state === 'available' ? 'is-good' : item.state === 'disabled' ? 'is-bad' : 'is-muted';
    const actions = [
      item.can_disable === true ? `<button type="button" class="jobs-tb-btn" data-derivation-id="${id}" data-derivation-state="disabled"${state.updating ? ' disabled' : ''}>停用</button>` : '',
      item.can_restore === true ? `<button type="button" class="jobs-tb-btn jobs-tb-btn--good" data-derivation-id="${id}" data-derivation-state="available"${state.updating ? ' disabled' : ''}>恢复可领取</button>` : '',
    ].filter(Boolean).join('');
    return `<tr class="${state.selected.has(id) ? 'is-selected' : ''}">
      <td class="col-check"><input type="checkbox" class="email-derivation-row-check" data-derivation-id="${id}"${state.selected.has(id) ? ' checked' : ''} aria-label="选择 ${attrEsc(item.email)}"></td>
      <td class="col-email" title="${attrEsc(item.email)}"><strong>${esc(item.email || '-')}</strong></td>
      <td class="col-parent" title="${attrEsc(item.parent_email)}"><span>${esc(item.parent_email || '-')}</span><small>母资源 #${esc(item.parent_id || '-')}</small></td>
      <td class="col-source">${esc(poolLabel(item.source))}</td>
      <td class="col-status"><span class="pool-usage ${statusClass}">${esc(EMAIL_DERIVATION_STATE_LABELS[item.state] || item.state || '状态待确认')}</span></td>
      <td class="col-related">${esc(ownership)}</td>
      <td class="col-time">${esc(formatDateTime(item.created_at))}</td>
      <td class="col-actions">${actions || '<span class="sub-cell">—</span>'}</td>
    </tr>`;
  }).join('') || renderTableStateRow(8, '当前筛选下没有子地址', '点击“生成子邮箱”补充可领取库存。');
  updateEmailDerivationSelectionUi();
  _renderPager('derivations', state.total);
}
function emailDerivationQueryParams() {
  const state = EMAIL_DERIVATION_VIEW;
  const pager = PAGERS.derivations;
  const params = new URLSearchParams({page: String(pager.page), page_size: String(pager.size)});
  for (const [key, id] of Object.entries(EMAIL_DERIVATION_FILTERS)) {
    const value = document.getElementById(id)?.value.trim() || (key === 'source' ? 'all' : '');
    if (key === 'source') state.source = value;
    if (value) params.set(key, value);
  }
  if (state.parentId) params.set('parent_id', String(state.parentId));
  return params;
}
async function loadEmailDerivationResources() {
  if (!document.getElementById('emailDerivationPanel')) return;
  const state = EMAIL_DERIVATION_VIEW;
  const generation = ++state.generation;
  const params = emailDerivationQueryParams();
  const parentScope = document.getElementById('emailDerivationParentScope');
  if (parentScope) parentScope.hidden = !state.parentId;
  const parentLabel = document.getElementById('emailDerivationParentFilter');
  if (parentLabel) parentLabel.textContent = state.parentId ? `母邮箱：${state.parentEmail || `#${state.parentId}`}` : '';
  const wrap = document.getElementById('emailDerivationTableWrap');
  wrap?.setAttribute('aria-busy', 'true');
  state.loading = true;
  const status = document.getElementById('emailDerivationListStatus');
  if (status) status.textContent = '正在读取子邮箱库存…';
  try {
    const allocations = await api(`/api/email-derivation/allocations?${params.toString()}`);
    if (generation !== state.generation) return;
    const pages = Math.max(1, Math.ceil(Number(allocations.total || 0) / PAGERS.derivations.size));
    if (PAGERS.derivations.page > pages) {
      PAGERS.derivations.page = pages;
      return loadEmailDerivationResources();
    }
    renderEmailDerivationAllocations(allocations);
    if (status) status.textContent = '';
  } catch (error) {
    if (generation !== state.generation) return;
    if (status) status.textContent = '子邮箱库存加载失败：' + error.message;
    if (!state.items.length) document.getElementById('emailDerivationBody').innerHTML = renderTableStateRow(8, '子邮箱库存加载失败', '请调整筛选或重新打开本页重试。', 'error');
  } finally {
    if (generation === state.generation) {
      state.loading = false;
      wrap?.setAttribute('aria-busy', 'false');
    }
  }
}
function resetEmailDerivationFilters() {
  const state = EMAIL_DERIVATION_VIEW;
  Object.entries(EMAIL_DERIVATION_FILTERS).forEach(([key, id]) => {
    const control = document.getElementById(id);
    if (control) control.value = key === 'source' ? 'all' : '';
  });
  Object.assign(state, {source: 'all', parentId: null, parentEmail: ''});
  state.selected.clear();
  PAGERS.derivations.page = 1;
  refreshColumnFilterStates();
}
function showEmailDerivationParent(button) {
  resetEmailDerivationFilters();
  const state = EMAIL_DERIVATION_VIEW;
  state.source = button.dataset.source || 'all';
  state.parentId = Number(button.dataset.derivationParent) || null;
  state.parentEmail = button.dataset.parentEmail || '';
  const source = document.getElementById('emailDerivationSourceFilter');
  if (source) source.value = state.source;
  refreshColumnFilterStates();
  setModuleView('outlook', 'derivations');
  document.getElementById('emailDerivationPanel')?.scrollIntoView({block: 'nearest'});
}
function syncEmailDerivationSelectAll(checked) {
  const state = EMAIL_DERIVATION_VIEW;
  state.items.forEach(item => {
    if (checked) state.selected.set(Number(item.id), item);
    else state.selected.delete(Number(item.id));
  });
  renderEmailDerivationAllocations({items: state.items, total: state.total});
}
function onEmailDerivationBodyChange(event) {
  const checkbox = event.target.closest('.email-derivation-row-check');
  if (!checkbox) return;
  const state = EMAIL_DERIVATION_VIEW;
  const id = Number(checkbox.dataset.derivationId);
  const item = state.items.find(row => Number(row.id) === id);
  if (checkbox.checked && item) state.selected.set(id, item);
  else state.selected.delete(id);
  checkbox.closest?.('tr')?.classList.toggle('is-selected', checkbox.checked);
  updateEmailDerivationSelectionUi();
}
async function copyEmailDerivationEmails() {
  const state = EMAIL_DERIVATION_VIEW;
  const rows = state.selected.size ? Array.from(state.selected.values()) : state.items;
  if (!rows.length) { showToast('当前没有可复制的子邮箱'); return; }
  await copyText(rows.map(row => row.email).filter(Boolean).join('\n'));
}
async function updateEmailDerivationStatus(nextState, ids = null) {
  const state = EMAIL_DERIVATION_VIEW;
  if (state.updating) return;
  const chosen = ids || Array.from(state.selected.keys());
  if (!chosen.length) { showToast('请先选择子邮箱'); return; }
  state.updating = true;
  renderEmailDerivationAllocations({items: state.items, total: state.total});
  const resultNode = document.getElementById('emailDerivationActionResult');
  if (resultNode) { resultNode.hidden = false; resultNode.textContent = '正在更新子邮箱库存状态…'; }
  try {
    const result = await api('/api/email-derivation/status-bulk', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: chosen, state: nextState})});
    const reasons = (result.results || []).filter(item => item.ok === false).map(item => `#${item.id}：${item.reason || item.reason_code}`);
    if (resultNode) resultNode.textContent = `已更新 ${Number(result.updated || 0)} 个，跳过 ${Number(result.skipped || 0)} 个${reasons.length ? '。' + reasons.join('；') : '。'}`;
    state.selected.clear();
    await loadEmailDerivationResources();
    loadEmailDerivationSummary();
  } catch (error) {
    if (resultNode) resultNode.textContent = '子邮箱状态更新失败：' + error.message;
  } finally {
    state.updating = false;
    renderEmailDerivationAllocations({items: state.items, total: state.total});
  }
}
function updateEmailDerivationGenerateControls() {
  const state = EMAIL_DERIVATION_VIEW;
  const fixed = state.generating || Boolean(state.generationRequest);
  document.getElementById('emailDerivationGenerateSource').disabled = fixed;
  document.getElementById('emailDerivationGenerateCount').disabled = fixed;
  const submit = document.getElementById('btnSubmitEmailDerivationGenerate');
  submit.disabled = state.generating;
  submit.textContent = state.generating ? '生成中…' : state.generationRequest ? '重试生成' : '生成子邮箱';
  const dialog = document.getElementById('emailDerivationGenerateDialog');
  const source = document.getElementById('emailDerivationGenerateSource').value;
  const scope = document.getElementById('emailDerivationGenerateScope');
  scope.textContent = dialog.dataset.parentId && source === dialog.dataset.parentSource
    ? `仅为母邮箱 ${dialog.dataset.parentEmail || `#${dialog.dataset.parentId}`} 生成` : '按所选来源的母邮箱剩余额度生成';
}
function openEmailDerivationGenerate() {
  const state = EMAIL_DERIVATION_VIEW;
  const dialog = document.getElementById('emailDerivationGenerateDialog');
  if (!dialog || dialog.open) return;
  const request = state.generationRequest;
  const source = request?.source || (['icloud_hide', 'outlook'].includes(state.source) ? state.source : 'icloud_hide');
  document.getElementById('emailDerivationGenerateSource').value = source;
  document.getElementById('emailDerivationGenerateCount').value = String(request?.count || 1);
  dialog.dataset.parentId = String(request?.parent_id || (!request && state.parentId) || '');
  dialog.dataset.parentSource = request?.source || state.source;
  dialog.dataset.parentEmail = request ? state.generationParentEmail : state.parentEmail;
  if (!request) document.getElementById('emailDerivationGenerateResult').textContent = '';
  state.generationFocus = document.activeElement;
  state.restoreGenerationFocus = true;
  updateEmailDerivationGenerateControls();
  dialog.showModal();
}
function closeEmailDerivationGenerate({restoreFocus = true} = {}) {
  EMAIL_DERIVATION_VIEW.restoreGenerationFocus = restoreFocus;
  document.getElementById('emailDerivationGenerateDialog')?.close();
}
async function submitEmailDerivationGenerate(event) {
  event.preventDefault();
  const state = EMAIL_DERIVATION_VIEW;
  if (state.generating) return;
  const resultNode = document.getElementById('emailDerivationGenerateResult');
  const dialog = document.getElementById('emailDerivationGenerateDialog');
  if (!state.generationRequest) {
    const source = document.getElementById('emailDerivationGenerateSource').value;
    const count = Number(document.getElementById('emailDerivationGenerateCount').value);
    if (!Number.isInteger(count) || count < 1 || count > 1000) {
      resultNode.textContent = '生成数量须为 1–1000 的整数。';
      return;
    }
    state.generationParentEmail = dialog.dataset.parentEmail || '';
    state.generationRequest = {source, count, request_id: crypto.randomUUID()};
    if (dialog.dataset.parentId && source === dialog.dataset.parentSource) state.generationRequest.parent_id = Number(dialog.dataset.parentId);
  }
  state.generating = true;
  resultNode.textContent = '正在生成子邮箱…';
  updateEmailDerivationGenerateControls();
  try {
    const result = await api('/api/email-derivation/generate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(state.generationRequest)});
    const created = Number(result.created || 0);
    const reused = Number(result.reused || 0);
    const shortfall = Number(result.shortfall || 0);
    const message = `已生成 ${created} 个${reused ? `，已有 ${reused} 个` : ''}${shortfall ? `，缺少 ${shortfall} 个。${result.reason || result.reason_code || '请补充母邮箱额度后继续生成。'}` : '。'}`;
    state.generationRequest = null;
    resultNode.textContent = message;
    if (!shortfall) { closeEmailDerivationGenerate(); showToast(message); }
    await loadEmailDerivationResources();
    loadEmailDerivationSummary();
  } catch (error) {
    resultNode.textContent = `生成失败：${error.message}。请使用原参数重试。`;
  } finally {
    state.generating = false;
    updateEmailDerivationGenerateControls();
  }
}
(function bindEmailDerivationInventory() {
  const sourceSelect = document.getElementById('emailDerivationSourceFilter');
  if (sourceSelect) {
    sourceSelect.innerHTML = '<option value="all">全部</option><option value="icloud_hide">iCloud 隐藏邮箱</option><option value="outlook">Outlook</option>';
    sourceSelect.value = 'all';
    renderColumnFilterOptions(sourceSelect);
  }
  const stateSelect = document.getElementById('emailDerivationStateFilter');
  if (stateSelect) {
    stateSelect.innerHTML = '<option value="">全部</option>' + Object.entries(EMAIL_DERIVATION_STATE_LABELS).map(([value, label]) => `<option value="${value}">${label}</option>`).join('');
    renderColumnFilterOptions(stateSelect);
  }
  const reload = id => {
    const state = EMAIL_DERIVATION_VIEW;
    if (id === 'emailDerivationSourceFilter') Object.assign(state, {parentId: null, parentEmail: ''});
    state.selected.clear();
    PAGERS.derivations.page = 1;
    updateEmailDerivationSelectionUi();
    loadEmailDerivationResources();
  };
  const reloadText = debounce(reload, 250);
  Object.entries(EMAIL_DERIVATION_FILTERS).forEach(([key, id]) => {
    const control = document.getElementById(id);
    control?.addEventListener(['q', 'parent_q', 'related_q'].includes(key) ? 'input' : 'change', () => {
      if (['q', 'parent_q', 'related_q'].includes(key)) reloadText(id);
      else reload(id);
    });
  });
  document.getElementById('btnClearDerivationParent')?.addEventListener('click', () => {
    Object.assign(EMAIL_DERIVATION_VIEW, {parentId: null, parentEmail: ''});
    EMAIL_DERIVATION_VIEW.selected.clear();
    PAGERS.derivations.page = 1;
    loadEmailDerivationResources();
  });
  document.getElementById('btnResetEmailDerivationFilters')?.addEventListener('click', () => { resetEmailDerivationFilters(); loadEmailDerivationResources(); });
  document.getElementById('emailDerivationSelectAll')?.addEventListener('change', event => syncEmailDerivationSelectAll(event.target.checked));
  document.getElementById('emailDerivationBody')?.addEventListener('change', onEmailDerivationBodyChange);
  document.getElementById('emailDerivationBody')?.addEventListener('click', event => {
    const button = event.target.closest('[data-derivation-state]');
    if (!button || button.disabled) return;
    updateEmailDerivationStatus(button.dataset.derivationState, [Number(button.dataset.derivationId)]);
  });
  document.getElementById('btnCopyEmailDerivation')?.addEventListener('click', copyEmailDerivationEmails);
  document.getElementById('btnDisableEmailDerivation')?.addEventListener('click', () => updateEmailDerivationStatus('disabled'));
  document.getElementById('btnRestoreEmailDerivation')?.addEventListener('click', () => updateEmailDerivationStatus('available'));
  document.getElementById('btnGenerateEmailDerivation')?.addEventListener('click', openEmailDerivationGenerate);
  document.getElementById('emailDerivationGenerateForm')?.addEventListener('submit', submitEmailDerivationGenerate);
  document.getElementById('btnCloseEmailDerivationGenerate')?.addEventListener('click', () => closeEmailDerivationGenerate());
  document.getElementById('btnCancelEmailDerivationGenerate')?.addEventListener('click', () => closeEmailDerivationGenerate());
  document.getElementById('emailDerivationGenerateSource')?.addEventListener('change', updateEmailDerivationGenerateControls);
  document.getElementById('emailDerivationGenerateDialog')?.addEventListener('close', () => {
    const state = EMAIL_DERIVATION_VIEW;
    if (state.restoreGenerationFocus && state.generationFocus?.isConnected) state.generationFocus.focus({preventScroll: true});
    state.generationFocus = null;
  });
})();

function getPoolSource() {
  const v2 = document.getElementById('poolSourceV2');
  return (v2 && v2.value) || 'all';
}
const POOL_SOURCE_LABELS = {
  all: '全部邮箱池',
  outlook: 'Outlook 邮箱池',
  generic_api: '通用 API 邮箱池',
  cloudflare_domain: '域名邮箱池',
  icloud_hide: 'iCloud 隐藏邮箱池',
};
function setPoolSourceV2(val) {
  const hidden = document.getElementById('poolSourceV2');
  const btn = document.getElementById('poolSourceV2Btn');
  const wrap = document.getElementById('poolSourceV2Wrap');
  if (!hidden) return;
  const next = POOL_SOURCE_LABELS[val] ? val : 'all';
  hidden.value = next;
  if (btn) btn.textContent = POOL_SOURCE_LABELS[next] || next;
  if (wrap) {
    wrap.querySelectorAll('.outlook-v2-select-item').forEach(item => {
      item.classList.toggle('is-active', item.dataset.value === next);
    });
  }
}
function getOutlookQuery() {
  const el = document.getElementById('qOutlookV2');
  return (el ? el.value : '').trim();
}
function poolKey(r) { return `${r.source || getPoolSource() || 'outlook'}|${r.email || ''}`; }
function poolLabel(src) {
  return ({outlook:'Outlook', generic_api:'通用API', cloudflare_domain:'域名邮箱', icloud_hide:'iCloud 隐藏邮箱'})[src] || src || '-';
}
const POOL_USAGE_LABELS = {
  available: '待领取',
  used_unbound: '已领取未绑定',
  bound: '已绑定账号',
  replaced: '换绑后邮箱',
  failed: '失败',
  disabled: '已停用',
};
function poolUsageLabel(state) { return POOL_USAGE_LABELS[state] || state || '状态待确认'; }
function _poolUsageCell(r) {
  const state = r.usage_state || r.status || '';
  const label = poolUsageLabel(state);
  const account = r.registered_account_id ? ` · #${r.registered_account_id}` : '';
  const cls = ['available', 'bound'].includes(state) ? 'is-good' : ['failed', 'disabled'].includes(state) ? 'is-bad' : 'is-muted';
  return `<span class="pool-usage ${cls}">${esc(label)}${state === 'bound' ? esc(account) : ''}</span>`;
}
function _poolCredentialsCell(r) {
  const meta = r.resource_meta || {};
  const source = r.source || 'outlook';
  if (source === 'outlook') {
    const fields = [
      ['password', '密码'],
      ['client_id', 'Client ID'],
      ['refresh_token', 'Refresh Token'],
    ];
    const configured = fields.filter(([key]) => meta[key]).length;
    const missing = fields.filter(([key]) => !meta[key]).map(([, label]) => label);
    return `<div class="pool-credential-title">${configured}/3 已配置</div><small>${missing.length ? `缺少：${esc(missing.join('、'))}` : '密码 · Client ID · Refresh Token'}</small>`;
  }
  if (source === 'generic_api') {
    return `<div class="pool-credential-title">${meta.code_url ? '取码地址已配置' : '缺少取码地址'}</div><small>地址仅在按需复制时读取</small>`;
  }
  if (source === 'icloud_hide') {
    const remote = r.remote_active === true ? '远程已激活' : r.remote_active === false ? '远程未激活' : '远程状态未知';
    return `<div class="pool-credential-title">Apple 别名</div><small>${esc(remote)}</small>`;
  }
  return `<div class="pool-credential-title">运行时配置</div><small>由来源服务管理</small>`;
}
function _poolActivityCell(r) {
  const activity = r.last_activity_at || r.used_at || r.updated_at || r.created_at;
  const label = r.used_at ? '最近使用' : r.last_activity_at ? '最近更新' : '导入时间';
  const sync = r.synced_at ? `<small>同步 ${esc(formatDateTime(r.synced_at))}</small>` : '';
  return `<div class="pool-activity"><span>${esc(formatDateTime(activity))}</span><small>${esc(label)}</small>${sync}</div>`;
}
function _poolNoteCell(r) {
  const note = String(r.note || r.disabled_reason || '').trim();
  return note ? `<span class="pool-note" title="${attrEsc(note)}">${esc(note)}</span>` : '<span class="pool-note is-empty">-</span>';
}
let mailSourceCardsExpanded = false;
function _mailSourceVisibility(source) {
  const onDemand = source.kind === 'on_demand';
  const enabled = source.enabled === true || source.enabled === 'true';
  const dependency = source.dependency === true || source.dependency === 'true';
  const history = source.history_available === true
    || source.history_available === 'true'
    || (!onDemand && Number(source.total || 0) > 0);
  const defaultVisible = source.default_visible === undefined
    ? enabled || dependency
    : source.default_visible === true || source.default_visible === 'true';
  return {onDemand, enabled, dependency, history, defaultVisible};
}
function _ensureMailSourceVisibilityControls(root) {
  let controls = document.getElementById('mailSourceVisibilityControls');
  if (controls) return controls;
  controls = document.createElement('div');
  controls.id = 'mailSourceVisibilityControls';
  controls.className = 'mail-source-visibility';
  root.parentNode?.insertBefore(controls, root);
  return controls;
}
function renderMailSourceCards(sources) {
  const root = $('#mailSourceCards');
  if (!root) return;
  const allSources = Array.isArray(sources) ? sources : [];
  const sourceRows = allSources.map(source => ({source, visibility: _mailSourceVisibility(source)}));
  const hiddenCount = sourceRows.filter(row => !row.visibility.defaultVisible).length;
  const controls = _ensureMailSourceVisibilityControls(root);
  if (controls) {
    controls.innerHTML = hiddenCount
      ? `<span class="muted">默认显示已启用服务和当前收码依赖</span><button type="button" class="jobs-tb-btn" id="btnShowDisabledMailSources" aria-expanded="${mailSourceCardsExpanded ? 'true' : 'false'}">${mailSourceCardsExpanded ? '隐藏未启用' : `显示未启用（${hiddenCount}）`}</button>`
      : '<span class="muted">当前没有未启用的邮箱服务</span>';
    controls.querySelector('#btnShowDisabledMailSources')?.addEventListener('click', () => {
      mailSourceCardsExpanded = !mailSourceCardsExpanded;
      renderMailSourceCards(allSources);
    });
  }
  const visibleRows = mailSourceCardsExpanded ? sourceRows : sourceRows.filter(row => row.visibility.defaultVisible);
  root.innerHTML = visibleRows.map(({source, visibility}) => {
    const {onDemand, enabled, dependency, history} = visibility;
    const clickable = !onDemand && POOL_SOURCE_LABELS[source.source] && source.source !== 'all';
    const statusLabel = enabled ? '已启用' : dependency ? '收码依赖' : history ? '历史/已停用' : '未启用';
    const reason = dependency ? source.dependency_reason : '';
    return `<article class="mail-source-card${enabled ? ' is-enabled' : ''}${dependency ? ' is-dependency' : ''}${history && !enabled ? ' is-history' : ''}${clickable ? ' is-clickable' : ''}"${clickable ? ` data-mail-source="${attrEsc(source.source)}" role="button" tabindex="0"` : ''}>
      <div class="mail-source-card-head"><strong title="${attrEsc(source.label)}">${esc(source.label)}</strong><span>${statusLabel}</span></div>
      <div class="mail-source-card-value">${onDemand ? '按需' : esc(source.available || 0)}</div>
      <div class="mail-source-card-meta">${onDemand ? '运行时领取 / 创建' : `总数 ${esc(source.total || 0)} · 已用 ${esc(source.used || 0)} · 失败 ${esc(source.failed || 0)} · 停用 ${esc(source.disabled || 0)}`}</div>
      ${reason ? `<small class="mail-source-card-reason">${esc(reason)}</small>` : ''}
    </article>`;
  }).join('') || '<div class="muted">暂无已启用邮箱服务，可显示未启用的服务。</div>';
}
function renderButlerLeases(items) {
  const root = $('#butlerLeaseList');
  if (!root) return;
  root.innerHTML = (items || []).map(item => `<div class="butler-lease-row">
    <div class="butler-lease-row-main"><strong>${esc(item.email)}</strong><small>${esc(item.provider || 'Email Butler')}${item.leased_until ? ` · 至 ${esc(formatDateTime(item.leased_until))}` : ''}</small></div>
    <button type="button" data-butler-release="${attrEsc(item.email)}">释放</button>
  </div>`).join('') || '<div class="butler-lease-empty">当前进程没有手动或注册中租约</div>';
}
async function loadMailResources() {
  try {
    const [dashboard, leases] = await Promise.all([
      apiCached('/api/dashboard', {}, 5000),
      api('/api/email-butler/leases'),
    ]);
    renderMailSourceCards((dashboard.email || {}).sources || []);
    renderButlerLeases(leases.items || []);
    markViewReady('outlook:overview');
  } catch(e) { showToast('邮箱资源加载失败: ' + e.message); }
}
$('#btnRefreshMailResources')?.addEventListener('click', loadMailResources);
$('#mailSourceCards')?.addEventListener('click', e => {
  const card = e.target.closest('[data-mail-source]');
  if (!card) return;
  setPoolSourceV2(card.dataset.mailSource);
  setModuleView('outlook', 'list');
});
$('#mailSourceCards')?.addEventListener('keydown', e => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const card = e.target.closest('[data-mail-source]');
  if (!card) return;
  e.preventDefault();
  setPoolSourceV2(card.dataset.mailSource);
  setModuleView('outlook', 'list');
});
$('#btnLeaseButlerMailbox')?.addEventListener('click', async e => {
  e.currentTarget.disabled = true;
  try {
    const result = await api('/api/email-butler/leases', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    showToast(`已租用 ${result.item?.email || '邮箱'}`);
    await loadMailResources();
  } catch(err) { showToast('租用失败: ' + err.message); }
  finally { e.currentTarget.disabled = false; }
});
$('#butlerLeaseList')?.addEventListener('click', async e => {
  const btn = e.target.closest('[data-butler-release]');
  if (!btn) return;
  btn.disabled = true;
  try {
    await api('/api/email-butler/leases/release', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:btn.dataset.butlerRelease,status:'available'})});
    showToast('Email Butler 租约已释放');
    await loadMailResources();
  } catch(err) { showToast('释放失败: ' + err.message); btn.disabled = false; }
});

async function loadOutlook() {
  if (outlookLoading) { outlookReloadQueued = true; return; }
  outlookLoading = true;
  setListBusy('outlookPanelV2', true);
  try {
    const source = getPoolSource();
    const q = getOutlookQuery();
    const p = PAGERS.outlook;
    const params = new URLSearchParams({paged:'1', page:String(p.page), page_size:String(p.size), source, q});
    params.set('status', document.getElementById('outlookStatusFilterV2')?.value || '');
    params.set('used_date', document.getElementById('outlookUsedFilterV2')?.value || '');
    const res = await api(`/api/outlook?${params.toString()}`);
    const facets = res.facets || {};
    syncFacetSelect('poolSourceV2', facets.source, {group:'source', allValue:'all'});
    syncFacetSelect('outlookStatusFilterV2', facets.status, {group:'status'});
    OUTLOOK = res.items || [];
    OUTLOOK_TOTAL = Number(res.total || OUTLOOK.length || 0);
    const totalPages = Math.max(1, Math.ceil(OUTLOOK_TOTAL / p.size));
    if (p.page > totalPages) { p.page = totalPages; return loadOutlook(); }
    renderOutlook();
    loadEmailDerivationSummary();
    markViewReady('outlook:list');
  } catch(e) {
    if (!OUTLOOK.length) $('#outlookBodyV2').innerHTML = renderTableStateRow(9, '邮箱资源加载失败', '请检查服务状态后刷新列表。', 'error');
    showToast('加载邮箱池失败: ' + e.message);
  }
  finally {
    outlookLoading = false;
    setListBusy('outlookPanelV2', false);
    if (outlookReloadQueued) {
      outlookReloadQueued = false;
      queueMicrotask(loadOutlook);
    }
  }
}
async function refreshOutlookManual(btn) {
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '刷新中…';
  try { await loadOutlook(); showToast('邮箱池已刷新'); }
  finally { btn.textContent = old; btn.disabled = false; }
}
function closeOutlookV2MoreMenus() {
  document.querySelectorAll('.outlook-table-v2 .acc-v2-more.open').forEach(el => el.classList.remove('open'));
}
function positionOutlookV2MoreMenu(wrap) {
  const btn = wrap.querySelector('.acc-v2-more-btn');
  const menu = wrap.querySelector('.acc-v2-more-menu');
  if (!btn || !menu) return;
  const rect = btn.getBoundingClientRect();
  const menuW = Math.max(menu.offsetWidth || 148, 148);
  const menuH = menu.offsetHeight || 0;
  let left = rect.right - menuW;
  left = Math.max(8, Math.min(left, window.innerWidth - menuW - 8));
  let top = rect.bottom + 4;
  if (top + menuH > window.innerHeight - 8 && rect.top - menuH - 4 > 8) {
    top = rect.top - menuH - 4;
  }
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
}
function _poolCopyButton(label, r, field, cls='') {
  return `<button type="button" class="${cls}" data-pool-copy="${esc(field)}" data-email="${esc(r.email)}" data-source="${esc(r.source || 'outlook')}">${esc(label)}</button>`;
}
async function copyPoolSecret(source, email, field) {
  const params = new URLSearchParams({source, email, field});
  const result = await api(`/api/outlook/secret?${params.toString()}`);
  if (!result.value) throw new Error('对应内容为空');
  await copyText(result.value);
}
async function copyPoolSecrets(rows, field='copy_line') {
  const result = await api('/api/outlook/secret-bulk', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({items: rows.map(r => ({source:r.source || 'outlook', email:r.email})), field}),
  });
  const text = (result.values || []).map(item => item.value).filter(Boolean).join('\n');
  if (!text) throw new Error('当前页没有可复制内容');
  await copyText(text);
}
function _outlookMoreMenu(r) {
  const src = esc(r.source || 'outlook');
  const email = esc(r.email);
  const canChangeStatus = r.status !== 'replaced';
  const items = [
    canChangeStatus && r.status !== 'available' ? `<button type="button" data-pool-act="available" data-email="${email}" data-source="${src}">恢复可用</button>` : '',
    canChangeStatus && r.status !== 'disabled' ? `<button type="button" data-pool-act="disabled" data-email="${email}" data-source="${src}">停用</button>` : '',
    canChangeStatus && r.status !== 'failed' ? `<button type="button" data-pool-act="failed" data-email="${email}" data-source="${src}">标失败</button>` : '',
  ].filter(Boolean).join('');
  return items;
}
function renderOutlook() {
  const total = OUTLOOK_TOTAL;
  const rows = OUTLOOK;
  const bodyV2 = $('#outlookBodyV2');
  if (!bodyV2) return;
  bodyV2.innerHTML = rows.map(r => {
      const src = esc(r.source || 'outlook');
      const email = esc(r.email);
      return `
    <tr>
      <td class="col-check"><input type="checkbox" class="outlook-row-check" data-email="${email}" data-source="${src}" ${OUTLOOK_SELECTED.has(poolKey(r)) ? 'checked' : ''}></td>
      <td class="col-email" title="${email}">
        <div class="acc-v2-email">${email || '-'}</div>
        ${_poolDerivationCell(r)}
        ${r.remote_label ? `<small class="pool-remote">${esc(r.remote_label)}</small>` : ''}
      </td>
      <td class="col-source">${esc(poolLabel(r.source))}</td>
      <td class="col-status">${pill(r.status)}</td>
      <td class="col-usage">${_poolUsageCell(r)}</td>
      <td class="col-credentials">${_poolCredentialsCell(r)}</td>
      <td class="col-time">${_poolActivityCell(r)}</td>
      <td class="col-note">${_poolNoteCell(r)}</td>
      <td class="col-actions">
        <div class="acc-v2-actions">
          ${_poolCopyButton('复制素材', r, 'copy_line', 'primary')}
          <button type="button" class="danger" data-pool-act="delete" data-email="${email}" data-source="${src}" title="删除邮箱素材">删除</button>
          <div class="acc-v2-more">
            <button type="button" class="acc-v2-more-btn" data-outlook-more-toggle aria-haspopup="true">更多</button>
            <div class="acc-v2-more-menu" role="menu">${_outlookMoreMenu(r)}</div>
          </div>
        </div>
      </td>
    </tr>`;
  }).join('') || renderTableStateRow(9, '暂无邮箱资源', '调整筛选条件，或导入新的邮箱资源。');
  updateOutlookSelectionUi(rows);
  const summary = $('#outlookPageSummary');
  if (summary) summary.textContent = `${total || 0} 个邮箱 · 当前页 ${rows.length} 条`;
  _renderPager('outlook', total);
}
function updateOutlookSelectionUi(pageRows = null) {
  const none = OUTLOOK_SELECTED.size === 0;
  const hintV2 = document.getElementById('outlookSelectedHintV2');
  document.getElementById('outlookToolbarV2')?.classList.toggle('has-selection', !none);
  if (hintV2) hintV2.textContent = none ? '选择邮箱后批量操作' : `已选 ${OUTLOOK_SELECTED.size} 个邮箱`;
  [
    'btnDeleteSelectedOutlookV2',
    'btnMarkSelectedOutlookAvailableV2',
    'btnDisableSelectedOutlookV2',
    'btnFailSelectedOutlookV2',
  ].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = none;
  });

  if (!pageRows) pageRows = OUTLOOK;
  const pageKeys = pageRows.map(r => poolKey(r)).filter(Boolean);
  const checkedCount = pageKeys.filter(key => OUTLOOK_SELECTED.has(key)).length;
  const allChecked = pageKeys.length > 0 && checkedCount === pageKeys.length;
  const someChecked = checkedCount > 0 && checkedCount < pageKeys.length;
  const cbAll = document.getElementById('outlookSelectAllV2');
  if (!cbAll) return;
  cbAll.checked = allChecked;
  cbAll.indeterminate = someChecked;
  cbAll.disabled = pageKeys.length === 0;
}
function onPoolSourceChange(el) {
  if (el && el.id === 'poolSourceV2') setPoolSourceV2(el.value);
  PAGERS.outlook.page = 1;
  OUTLOOK_SELECTED.clear();
  const val = el ? el.value : getPoolSource();
  if (val === 'outlook' || val === 'generic_api') setImportSourceV2(val);
  loadOutlook();
}
function syncOutlookSelectAll(checked) {
  const pageRows = OUTLOOK;
  if (checked) pageRows.forEach(r => r.email && OUTLOOK_SELECTED.add(poolKey(r)));
  else pageRows.forEach(r => OUTLOOK_SELECTED.delete(poolKey(r)));
  renderOutlook();
}
function onOutlookBodyChange(e) {
  const cb = e.target.closest('.outlook-row-check');
  if (!cb) return;
  const email = cb.dataset.email;
  const source = cb.dataset.source || getPoolSource();
  const key = `${source}|${email}`;
  if (cb.checked) OUTLOOK_SELECTED.add(key);
  else OUTLOOK_SELECTED.delete(key);
  updateOutlookSelectionUi();
}
async function onOutlookBodyClick(e) {
  const derivationParent = e.target.closest('[data-derivation-parent]');
  if (derivationParent) { showEmailDerivationParent(derivationParent); return; }
  const moreToggle = e.target.closest('[data-outlook-more-toggle]');
  if (moreToggle) {
    e.preventDefault();
    e.stopPropagation();
    const wrap = moreToggle.closest('.acc-v2-more');
    if (!wrap) return;
    const willOpen = !wrap.classList.contains('open');
    closeOutlookV2MoreMenus();
    if (willOpen) {
      wrap.classList.add('open');
      positionOutlookV2MoreMenu(wrap);
    }
    return;
  }
  if (e.target.closest('.acc-v2-more-menu')) closeOutlookV2MoreMenus();

  const copyTarget = e.target.closest('[data-pool-copy]');
  if (copyTarget) {
    try {
      await copyPoolSecret(copyTarget.dataset.source || 'outlook', copyTarget.dataset.email || '', copyTarget.dataset.poolCopy || 'copy_line');
      showToast('已复制');
    } catch (err) { showToast('复制失败: ' + err.message); }
    return;
  }

  const t = e.target.closest('[data-pool-act]');
  if (!t) return;
  const { poolAct, email } = t.dataset;
  const source = t.dataset.source || getPoolSource();
  try {
    if (poolAct === 'delete') {
      if (!confirm(`确定从邮箱池删除 ${email}？此操作不可撤销。`)) return;
      await api('/api/outlook/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email, source}) });
      OUTLOOK_SELECTED.delete(`${source}|${email}`);
      showToast('已删除');
    } else {
      const noteMap = {failed:'手动标记失败', available:'手动恢复可用', disabled:'手动停用'};
      await api('/api/outlook/status', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email, status: poolAct, source, note: noteMap[poolAct] || '手动修改状态'}) });
      showToast(poolAct === 'failed' ? '已标失败' : poolAct === 'disabled' ? '已停用' : '已恢复可用');
    }
    loadOutlook(); loadSummary();
  } catch(err) { showToast('操作失败: ' + err.message); }
}
(function bindOutlookV2() {
  const qV2 = $('#qOutlookV2');
  if (qV2) qV2.addEventListener('input', debounce(() => {
    PAGERS.outlook.page = 1; loadOutlook();
  }, 250));
  const srcWrap = $('#poolSourceV2Wrap');
  const srcHidden = $('#poolSourceV2');
  if (srcWrap && srcHidden) {
    const btn = $('#poolSourceV2Btn');
    if (btn) btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = !srcWrap.classList.contains('open');
      srcWrap.classList.toggle('open', willOpen);
      btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
    srcWrap.querySelectorAll('.outlook-v2-select-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const val = item.dataset.value;
        setPoolSourceV2(val);
        srcWrap.classList.remove('open');
        if (btn) btn.setAttribute('aria-expanded', 'false');
        onPoolSourceChange(srcHidden);
      });
    });
    document.addEventListener('click', (e) => {
      if (srcWrap.contains(e.target)) return;
      srcWrap.classList.remove('open');
      if (btn) btn.setAttribute('aria-expanded', 'false');
    });
  }
  if (srcHidden && !srcWrap) srcHidden.addEventListener('change', () => onPoolSourceChange(srcHidden));
  ['outlookStatusFilterV2','outlookUsedFilterV2'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => { PAGERS.outlook.page = 1; OUTLOOK_SELECTED.clear(); loadOutlook(); });
  });
  const selectAllV2 = $('#outlookSelectAllV2');
  if (selectAllV2) selectAllV2.addEventListener('change', (e) => syncOutlookSelectAll(e.target.checked));
  const bodyV2 = $('#outlookBodyV2');
  if (bodyV2) {
    bodyV2.addEventListener('change', onOutlookBodyChange);
    bodyV2.addEventListener('click', onOutlookBodyClick);
  }
  const bind = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener('click', fn); };
  bind('btnMarkSelectedOutlookAvailableV2', () => bulkMarkOutlookStatus('available'));
  bind('btnDisableSelectedOutlookV2', () => bulkMarkOutlookStatus('disabled'));
  bind('btnFailSelectedOutlookV2', () => bulkMarkOutlookStatus('failed'));
  bind('btnDeleteSelectedOutlookV2', deleteSelectedOutlook);
  bind('btnImportOutlookV2', openOutlookImportModal);
  bind('copyAllEmailsV2', async () => {
    try { await copyPoolSecrets(OUTLOOK, 'copy_line'); showToast('已复制当前页邮箱素材'); }
    catch (err) { showToast('复制失败: ' + err.message); }
  });
  bind('btnRefreshOutlookV2', () => refreshOutlookManual(document.getElementById('btnRefreshOutlookV2')));
  bind('btnResetOutlookFiltersV2', () => {
    ['qOutlookV2','outlookStatusFilterV2','outlookUsedFilterV2'].forEach(id => { const el=document.getElementById(id); if (el) el.value=''; });
    setPoolSourceV2('all'); OUTLOOK_SELECTED.clear(); PAGERS.outlook.page = 1; refreshColumnFilterStates(); loadOutlook();
  });
  document.addEventListener('click', (e) => {
    if (e.target.closest('.outlook-table-v2 .acc-v2-more')) return;
    closeOutlookV2MoreMenus();
  });
  window.addEventListener('scroll', () => closeOutlookV2MoreMenus(), true);
  window.addEventListener('resize', () => closeOutlookV2MoreMenus());
  bindOutlookImportModal();
})();

const IMPORT_SOURCE_LABELS = {
  outlook: 'Outlook 邮箱池',
  generic_api: '通用 API 取码邮箱',
};
let outlookImportPreview = null;
function setImportSourceV2(val) {
  const hidden = document.getElementById('importSourceV2');
  const btn = document.getElementById('importSourceV2Btn');
  const wrap = document.getElementById('importSourceV2Wrap');
  if (!hidden) return;
  const next = IMPORT_SOURCE_LABELS[val] ? val : 'outlook';
  hidden.value = next;
  if (btn) btn.textContent = IMPORT_SOURCE_LABELS[next] || next;
  if (wrap) {
    wrap.querySelectorAll('.outlook-v2-select-item').forEach(item => {
      item.classList.toggle('is-active', item.dataset.value === next);
    });
  }
}
function openOutlookImportModal() {
  const modal = $('#outlookImportModal');
  if (!modal) return;
  const result = $('#importResultV2');
  if (result) result.innerHTML = '';
  clearOutlookImportPreview();
  const pool = getPoolSource();
  if (pool === 'outlook' || pool === 'generic_api') setImportSourceV2(pool);
  else setImportSourceV2('outlook');
  modal.classList.remove('hidden');
  updateModalScrollLock();
  const ta = $('#importTextV2');
  if (ta) setTimeout(() => ta.focus(), 50);
}
function closeOutlookImportModal() {
  const modal = $('#outlookImportModal');
  if (!modal) return;
  const wrap = $('#importSourceV2Wrap');
  if (wrap) wrap.classList.remove('open');
  modal.classList.add('hidden');
  updateModalScrollLock();
}
function bindOutlookImportModal() {
  const modal = $('#outlookImportModal');
  if (!modal || modal.dataset.bound) return;
  modal.dataset.bound = '1';
  const closeBtn = $('#btnCloseOutlookImport');
  const cancelBtn = $('#btnCancelOutlookImport');
  const submitBtn = $('#btnSubmitOutlookImport');
  const previewBtn = $('#btnPreviewOutlookImport');
  if (closeBtn) closeBtn.addEventListener('click', closeOutlookImportModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeOutlookImportModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeOutlookImportModal();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeOutlookImportModal();
  });
  const wrap = $('#importSourceV2Wrap');
  const btn = $('#importSourceV2Btn');
  if (wrap && btn) {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const willOpen = !wrap.classList.contains('open');
      wrap.classList.toggle('open', willOpen);
      btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
    wrap.querySelectorAll('.outlook-v2-select-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        setImportSourceV2(item.dataset.value);
        clearOutlookImportPreview();
        wrap.classList.remove('open');
        btn.setAttribute('aria-expanded', 'false');
      });
    });
    document.addEventListener('click', (e) => {
      if (wrap.contains(e.target)) return;
      wrap.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    });
  }
  const sourceEl = $('#importSourceV2');
  const textEl = $('#importTextV2');
  if (sourceEl) sourceEl.addEventListener('change', clearOutlookImportPreview);
  if (textEl) textEl.addEventListener('input', clearOutlookImportPreview);
  if (previewBtn) previewBtn.addEventListener('click', previewOutlookImport);
  if (submitBtn) submitBtn.addEventListener('click', () => doImportOutlook());
}
function clearOutlookImportPreview() {
  outlookImportPreview = null;
  const previewEl = $('#importPreviewV2');
  if (previewEl) previewEl.innerHTML = '';
  const submitBtn = $('#btnSubmitOutlookImport');
  if (submitBtn) submitBtn.disabled = false;
}
function renderOutlookImportPreview(data) {
  const previewEl = $('#importPreviewV2');
  if (!previewEl) return;
  const invalidRows = (data.invalid_rows || []).slice(0, 8).map(row => `第 ${esc(row.line)} 行：${esc(row.reason)}`);
  const invalidDetail = invalidRows.length ? `<div class="outlook-import-preview-errors">${invalidRows.map(item => `<span>${item}</span>`).join('')}</div>` : '';
  previewEl.innerHTML = `
    <div class="outlook-import-preview-head"><strong>导入前检查</strong><span>${esc(IMPORT_SOURCE_LABELS[data.source] || data.source)}</span></div>
    <div class="outlook-import-preview-grid">
      <div><strong>${esc(data.total_lines)}</strong><small>输入行数</small></div>
      <div><strong>${esc(data.valid)}</strong><small>可解析</small></div>
      <div class="is-good"><strong>${esc(data.new)}</strong><small>可新增</small></div>
      <div><strong>${esc(data.existing)}</strong><small>已存在</small></div>
      <div class="is-warn"><strong>${esc(data.duplicate_in_input)}</strong><small>输入重复</small></div>
      <div class="is-bad"><strong>${esc(data.invalid)}</strong><small>无效行</small></div>
    </div>
    ${data.extra_fields ? `<p class="outlook-import-preview-note">检测到 ${esc(data.extra_fields)} 个多余字段，导入时会忽略。</p>` : ''}
    ${invalidDetail}`;
}
async function previewOutlookImport() {
  const text = $('#importTextV2')?.value || '';
  const source = $('#importSourceV2')?.value || 'outlook';
  const previewBtn = $('#btnPreviewOutlookImport');
  const submitBtn = $('#btnSubmitOutlookImport');
  if (!text.trim()) { showToast('请粘贴邮箱资源'); return; }
  if (previewBtn) { previewBtn.disabled = true; previewBtn.textContent = '解析中…'; }
  try {
    const data = await api('/api/outlook/import-preview', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, source}),
    });
    outlookImportPreview = data;
    renderOutlookImportPreview(data);
    if (submitBtn) submitBtn.disabled = Number(data.new || 0) === 0;
  } catch (err) {
    const previewEl = $('#importPreviewV2');
    if (previewEl) previewEl.innerHTML = `<div class="banner warn">${esc(err.message)}</div>`;
    if (submitBtn) submitBtn.disabled = true;
  } finally {
    if (previewBtn) { previewBtn.disabled = false; previewBtn.textContent = '解析预览'; }
  }
}
async function doImportOutlook() {
  const textEl = $('#importTextV2');
  const sourceEl = $('#importSourceV2');
  const resultEl = $('#importResultV2');
  const submitBtn = $('#btnSubmitOutlookImport');
  const text = textEl ? textEl.value : '';
  if (!text.trim()) { showToast('请粘贴邮箱素材'); return; }
  if (submitBtn) submitBtn.disabled = true;
  try {
    const source = sourceEl ? sourceEl.value : 'outlook';
    if (!outlookImportPreview) await previewOutlookImport();
    if (!outlookImportPreview) return;
    if (outlookImportPreview && Number(outlookImportPreview.new || 0) === 0) {
      if (resultEl) resultEl.innerHTML = '<div class="banner warn">没有可新增的邮箱资源，请修改内容后重新预览。</div>';
      return;
    }
    const r = await api('/api/outlook/import', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, source}) });
    const extra = r.invalid || r.extra_fields ? `；无效 ${r.invalid || 0} 行，忽略多余字段 ${r.extra_fields || 0} 个` : '';
    const msg = `导入邮箱池：解析 ${r.parsed} 行，新增 ${r.inserted}，跳过 ${r.skipped}${extra}`;
    if (resultEl) resultEl.innerHTML = `<div class="banner info">${esc(msg)}</div>`;
    if (textEl) textEl.value = '';
    clearOutlookImportPreview();
    setPoolSourceV2(source);
    setImportSourceV2(source);
    loadOutlook(); loadMailResources(); loadSummary();
    showToast(`导入完成：新增 ${r.inserted}，跳过 ${r.skipped}`);
    setTimeout(closeOutlookImportModal, 600);
  } catch(e) {
    if (resultEl) resultEl.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`;
    else showToast('导入失败: ' + e.message);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}
async function bulkMarkOutlookStatus(status) {
  const items = Array.from(OUTLOOK_SELECTED).map(key => {
    const [source, ...rest] = key.split('|');
    return {source, email: rest.join('|')};
  });
  if (items.length === 0) { showToast('请先选择邮箱'); return; }
  const labelMap = {available:'未使用/可用', disabled:'停用', failed:'失败'};
  const label = labelMap[status] || status;
  if (!confirm(`确定把选中的 ${items.length} 个邮箱标记为${label}吗？`)) return;
  const btnId = status === 'disabled'
    ? 'btnDisableSelectedOutlookV2'
    : status === 'failed'
      ? 'btnFailSelectedOutlookV2'
      : 'btnMarkSelectedOutlookAvailableV2';
  const btn = document.getElementById(btnId);
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/outlook/status-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({items, status, source: getPoolSource(), note: `批量标记${label}`}),
    });
    OUTLOOK_SELECTED.clear();
    const skippedCount = (r.skipped || []).length;
    showToast(skippedCount ? `已更新 ${r.updated_count || 0} 个，跳过 ${skippedCount} 个` : `已更新 ${r.updated_count || 0} 个`);
    loadOutlook(); loadSummary();
  } catch(err) {
    showToast('批量标记失败: ' + err.message);
    updateOutlookSelectionUi();
  }
}

async function deleteSelectedOutlook() {
  const items = Array.from(OUTLOOK_SELECTED).map(key => {
    const [source, ...rest] = key.split('|');
    return {source, email: rest.join('|')};
  });
  if (items.length === 0) { showToast('请先选择邮箱'); return; }
  if (!confirm(`确定从邮箱池删除选中的 ${items.length} 个邮箱吗？\n\n此操作不可撤销。`)) return;
  const delBtn = document.getElementById('btnDeleteSelectedOutlookV2'); if (delBtn) delBtn.disabled = true;
  try {
    const r = await api('/api/outlook/delete-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({items, source: getPoolSource()}),
    });
    (r.deleted || []).forEach(item => OUTLOOK_SELECTED.delete(`${item.source}|${item.email}`));
    const skippedCount = (r.skipped || []).length;
    showToast(skippedCount ? `已删除 ${r.deleted_count || 0} 个，跳过 ${skippedCount} 个` : `已删除 ${r.deleted_count || 0} 个`);
    loadOutlook(); loadSummary();
  } catch(err) {
    showToast('批量删除失败: ' + err.message);
    updateOutlookSelectionUi();
  }
}
