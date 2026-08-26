// ---------- 邮箱池 ----------
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
function renderMailSourceCards(sources) {
  const root = $('#mailSourceCards');
  if (!root) return;
  root.innerHTML = (sources || []).map(source => {
    const onDemand = source.kind === 'on_demand';
    return `<article class="mail-source-card${source.enabled ? ' is-enabled' : ''}">
      <div class="mail-source-card-head"><strong title="${attrEsc(source.label)}">${esc(source.label)}</strong><span>${source.enabled ? '已启用' : '未启用'}</span></div>
      <div class="mail-source-card-value">${onDemand ? '按需' : esc(source.available || 0)}</div>
      <div class="mail-source-card-meta">${onDemand ? '运行时租用 / 创建' : `总数 ${esc(source.total || 0)} · 已用 ${esc(source.used || 0)} · 失败 ${esc(source.failed || 0)}`}</div>
    </article>`;
  }).join('') || '<div class="muted">暂无邮箱平台</div>';
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
    const [dashboard, leases] = await Promise.all([api('/api/dashboard'), api('/api/email-butler/leases')]);
    renderMailSourceCards((dashboard.email || {}).sources || []);
    renderButlerLeases(leases.items || []);
  } catch(e) { showToast('邮箱资源加载失败: ' + e.message); }
}
$('#btnRefreshMailResources')?.addEventListener('click', loadMailResources);
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
    params.set('token', document.getElementById('outlookTokenFilterV2')?.value || '');
    params.set('imported_date', document.getElementById('outlookImportedFilterV2')?.value || '');
    params.set('used_date', document.getElementById('outlookUsedFilterV2')?.value || '');
    const res = await api(`/api/outlook?${params.toString()}`);
    const facets = res.facets || {};
    syncFacetSelect('poolSourceV2', facets.source, {group:'source', allValue:'all'});
    syncFacetSelect('outlookStatusFilterV2', facets.status, {group:'status'});
    syncFacetSelect('outlookTokenFilterV2', facets.token, {group:'token'});
    OUTLOOK = res.items || [];
    OUTLOOK_TOTAL = Number(res.total || OUTLOOK.length || 0);
    const totalPages = Math.max(1, Math.ceil(OUTLOOK_TOTAL / p.size));
    if (p.page > totalPages) { p.page = totalPages; return loadOutlook(); }
    renderOutlook();
  } catch(e) {
    if (!OUTLOOK.length) $('#outlookBodyV2').innerHTML = renderTableStateRow(8, '邮箱素材加载失败', '请检查服务状态后刷新列表。', 'error');
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
function _outlookTokenCell(r) {
  if (r.has_access_token) {
    return `<button type="button" class="acc-v2-token-copy" data-pool-copy="access_token" data-email="${esc(r.email)}" data-source="${esc(r.source || 'outlook')}" title="按需读取并复制 Token">复制</button>`;
  }
  return `<span class="acc-v2-token-none">无Token</span>`;
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
  const items = [
    r.has_access_token ? _poolCopyButton('复制Token', r, 'access_token', 'good') : '',
    r.registered_account_id ? _poolCopyButton('复制账号整行', r, 'account_copy_line', 'good') : '',
    r.status !== 'available' ? `<button type="button" data-pool-act="available" data-email="${email}" data-source="${src}">恢复可用</button>` : '',
    r.status !== 'disabled' ? `<button type="button" data-pool-act="disabled" data-email="${email}" data-source="${src}">停用</button>` : '',
    r.status !== 'failed' ? `<button type="button" data-pool-act="failed" data-email="${email}" data-source="${src}">标失败</button>` : '',
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
      </td>
      <td class="col-source">${esc(poolLabel(r.source))}</td>
      <td class="col-status">${pill(r.status)}</td>
      <td class="col-token">${_outlookTokenCell(r)}</td>
      <td class="col-time" title="${esc(r.imported_at || r.created_at || '-')}">${esc(r.imported_at || r.created_at || '-')}</td>
      <td class="col-time" title="${esc(r.used_at || '-')}">${esc(r.used_at || '-')}</td>
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
  }).join('') || renderTableStateRow(8, '暂无邮箱素材', '调整筛选条件，或导入新的邮箱素材。');
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
  ['outlookStatusFilterV2','outlookTokenFilterV2','outlookImportedFilterV2','outlookUsedFilterV2'].forEach(id => {
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
    ['qOutlookV2','outlookStatusFilterV2','outlookTokenFilterV2','outlookImportedFilterV2','outlookUsedFilterV2'].forEach(id => { const el=document.getElementById(id); if (el) el.value=''; });
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
  if (submitBtn) submitBtn.addEventListener('click', () => doImportOutlook());
}
async function doImportOutlook() {
  const textEl = $('#importTextV2');
  const sourceEl = $('#importSourceV2');
  const registeredEl = $('#importAsRegisteredV2');
  const resultEl = $('#importResultV2');
  const submitBtn = $('#btnSubmitOutlookImport');
  const text = textEl ? textEl.value : '';
  if (!text.trim()) { showToast('请粘贴邮箱素材'); return; }
  if (submitBtn) submitBtn.disabled = true;
  try {
    const source = sourceEl ? sourceEl.value : 'outlook';
    const as_registered = registeredEl ? !!registeredEl.checked : true;
    const r = await api('/api/outlook/import', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, source, as_registered}) });
    const mode = r.as_registered ? '已注册账号' : '邮箱池素材';
    const msg = `按 ${mode} 导入：解析 ${r.parsed} 行，新增 ${r.inserted}，跳过 ${r.skipped}${r.as_registered ? '；可到“账号”页选择后批量补跑 Codex' : ''}`;
    if (resultEl) resultEl.innerHTML = `<div class="banner info">${esc(msg)}</div>`;
    if (textEl) textEl.value = '';
    setPoolSourceV2(source);
    setImportSourceV2(source);
    loadOutlook(); loadAccounts(); loadSummary();
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
