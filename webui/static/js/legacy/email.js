// ---------- 邮箱资源池 ----------
function poolKey(r) { return `${r.source || $('#poolSource')?.value || 'outlook'}|${r.email || ''}`; }
function poolLabel(src) {
  return ({outlook:'Outlook', generic_api:'通用 API', cloudflare_domain:'域名邮箱', icloud_hide:'iCloud 隐藏邮箱'})[src] || src || '-';
}
function poolDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value).replace('T', ' ').replace(/Z$/, '') : date.toLocaleString('zh-CN', {hour12:false});
}
function poolUsage(r) {
  const state = r.usage_state || r.status || '';
  const labels = {available:'待领取', used_unbound:'已领取未绑定', bound:'已绑定账号', failed:'失败', disabled:'已停用'};
  const cls = ['available', 'bound'].includes(state) ? 'good' : ['failed', 'disabled'].includes(state) ? 'bad' : 'muted';
  return `<span class="pool-usage pool-usage-${cls}">${esc(labels[state] || state || '状态待确认')}${state === 'bound' && r.registered_account_id ? ` · #${esc(r.registered_account_id)}` : ''}</span>`;
}
function poolCredentials(r) {
  const meta = r.resource_meta || {};
  if ((r.source || 'outlook') === 'outlook') {
    const count = ['password', 'client_id', 'refresh_token'].filter(key => meta[key]).length;
    return `<strong>${count}/3 已配置</strong><small>${count === 3 ? '密码 · Client ID · Refresh Token' : '配置不完整'}</small>`;
  }
  if (r.source === 'generic_api') return `<strong>${meta.code_url ? '取码地址已配置' : '缺少取码地址'}</strong><small>按需读取，不在列表展示</small>`;
  if (r.source === 'icloud_hide') return `<strong>Apple 别名</strong><small>${r.remote_active === false ? '远程未激活' : r.remote_active === true ? '远程已激活' : '远程状态未知'}</small>`;
  return `<strong>运行时配置</strong><small>由来源服务管理</small>`;
}
function poolActivity(r) {
  const value = r.last_activity_at || r.used_at || r.updated_at || r.created_at;
  return `<span>${esc(poolDate(value))}</span><small>${r.used_at ? '最近使用' : r.last_activity_at ? '最近更新' : '导入时间'}</small>`;
}
function poolNote(r) {
  const note = String(r.note || r.disabled_reason || '').trim();
  return note ? `<span title="${attrEsc(note)}">${esc(note)}</span>` : '<span class="muted">-</span>';
}
async function loadOutlook() {
  try {
    const source = $('#poolSource')?.value || 'all';
    const q = $('#qOutlook') ? $('#qOutlook').value.trim() : '';
    const p = PAGERS.outlook;
    const params = new URLSearchParams({paged:'1', page:String(p.page), page_size:String(p.size), source, q});
    const res = await api(`/api/outlook?${params.toString()}`);
    OUTLOOK = res.items || [];
    OUTLOOK_TOTAL = Number(res.total || OUTLOOK.length || 0);
    const totalPages = Math.max(1, Math.ceil(OUTLOOK_TOTAL / p.size));
    if (p.page > totalPages) { p.page = totalPages; return loadOutlook(); }
    renderOutlook();
  } catch(e) { showToast('加载邮箱资源失败: ' + e.message); }
}
function renderOutlook() {
  const rows = OUTLOOK;
  $('#outlookBody').innerHTML = rows.map(r => `
    <tr>
      <td><input type="checkbox" class="outlook-row-check" data-email="${attrEsc(r.email)}" data-source="${attrEsc(r.source || 'outlook')}" ${OUTLOOK_SELECTED.has(poolKey(r)) ? 'checked' : ''}></td>
      <td><div class="main-cell">${esc(r.email)}</div>${r.remote_label ? `<div class="sub-cell">${esc(r.remote_label)}</div>` : ''}</td>
      <td>${esc(poolLabel(r.source))}</td>
      <td>${pill(r.status)}</td>
      <td>${poolUsage(r)}</td>
      <td>${poolCredentials(r)}</td>
      <td class="muted">${poolActivity(r)}</td>
      <td class="pool-note">${poolNote(r)}</td>
      <td class="actions">
        <button class="primary" data-pool-copy="copy_line" data-email="${attrEsc(r.email)}" data-source="${attrEsc(r.source || 'outlook')}">复制资源</button>
        ${r.status !== 'available' ? `<button data-pool-act="available" data-email="${attrEsc(r.email)}" data-source="${attrEsc(r.source || 'outlook')}">恢复可用</button>` : ''}
        ${r.status !== 'disabled' ? `<button data-pool-act="disabled" data-email="${attrEsc(r.email)}" data-source="${attrEsc(r.source || 'outlook')}">停用</button>` : ''}
        ${r.status !== 'failed' ? `<button data-pool-act="failed" data-email="${attrEsc(r.email)}" data-source="${attrEsc(r.source || 'outlook')}">标失败</button>` : ''}
        <button data-pool-act="delete" data-email="${attrEsc(r.email)}" data-source="${attrEsc(r.source || 'outlook')}" style="border-color:#e7a3a0;color:#b3261e;">删除</button>
      </td>
    </tr>`).join('') || '<tr><td colspan="9" class="muted">邮箱资源池为空</td></tr>';
  updateOutlookSelectionUi(rows);
  _renderPager('outlook', OUTLOOK_TOTAL);
}
function updateOutlookSelectionUi(pageRows = null) {
  const hint = $('#outlookSelectedHint');
  const selected = OUTLOOK_SELECTED.size;
  const bulkBtn = $('#btnDeleteSelectedOutlook');
  const markAvailBtn = $('#btnMarkSelectedOutlookAvailable');
  const disableBtn = $('#btnDisableSelectedOutlook');
  const failBtn = $('#btnFailSelectedOutlook');
  if (hint) hint.textContent = `已选 ${selected}`;
  [bulkBtn, markAvailBtn, disableBtn, failBtn].forEach(btn => { if (btn) btn.disabled = selected === 0; });
  const cbAll = $('#outlookSelectAll');
  if (!cbAll) return;
  const pageKeys = (pageRows || OUTLOOK).map(r => poolKey(r)).filter(Boolean);
  const checkedCount = pageKeys.filter(key => OUTLOOK_SELECTED.has(key)).length;
  cbAll.checked = pageKeys.length > 0 && checkedCount === pageKeys.length;
  cbAll.indeterminate = checkedCount > 0 && checkedCount < pageKeys.length;
  cbAll.disabled = pageKeys.length === 0;
}
$('#qOutlook').addEventListener('input', debounce(() => { PAGERS.outlook.page = 1; loadOutlook(); }, 250));
$('#poolSource').addEventListener('change', () => {
  PAGERS.outlook.page = 1;
  OUTLOOK_SELECTED.clear();
  if ($('#poolSource').value !== 'all' && $('#poolSource').value !== 'cloudflare_domain') $('#importSource').value = $('#poolSource').value;
  loadOutlook();
});
$('#importSource').addEventListener('change', () => {
  $('#poolSource').value = $('#importSource').value;
  PAGERS.outlook.page = 1;
  OUTLOOK_SELECTED.clear();
  clearImportPreview();
  loadOutlook();
});
async function copyPoolSecretLegacy(source, email, field='copy_line') {
  const result = await api(`/api/outlook/secret?${new URLSearchParams({source, email, field})}`);
  if (!result.value) throw new Error('对应内容为空');
  await copyText(result.value);
}
$('#copyAllEmails').addEventListener('click', async () => {
  try {
    const result = await api('/api/outlook/secret-bulk', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({items:OUTLOOK.map(r => ({source:r.source, email:r.email})), field:'copy_line'})});
    await copyText((result.values || []).map(item => item.value).filter(Boolean).join('\n'));
  } catch (err) { showToast('复制失败: ' + err.message); }
});
$('#outlookSelectAll').addEventListener('change', (e) => {
  const pageRows = OUTLOOK;
  if (e.target.checked) pageRows.forEach(r => r.email && OUTLOOK_SELECTED.add(poolKey(r)));
  else pageRows.forEach(r => OUTLOOK_SELECTED.delete(poolKey(r)));
  renderOutlook();
});
$('#btnDeleteSelectedOutlook').addEventListener('click', deleteSelectedOutlook);
$('#btnMarkSelectedOutlookAvailable').addEventListener('click', () => bulkMarkOutlookStatus('available'));
$('#btnDisableSelectedOutlook').addEventListener('click', () => bulkMarkOutlookStatus('disabled'));
$('#btnFailSelectedOutlook').addEventListener('click', () => bulkMarkOutlookStatus('failed'));
$('#outlookBody').addEventListener('click', async (e) => {
  const copy = e.target.closest('[data-pool-copy]');
  if (copy) {
    try { await copyPoolSecretLegacy(copy.dataset.source || 'outlook', copy.dataset.email || '', copy.dataset.poolCopy || 'copy_line'); }
    catch (err) { showToast('复制失败: ' + err.message); }
    return;
  }
  const t = e.target.closest('[data-pool-act]');
  if (!t) return;
  const { poolAct, email } = t.dataset;
  const source = t.dataset.source || $('#poolSource').value;
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
});
$('#outlookBody').addEventListener('change', (e) => {
  const cb = e.target.closest('.outlook-row-check');
  if (!cb) return;
  const key = `${cb.dataset.source || $('#poolSource').value}|${cb.dataset.email}`;
  if (cb.checked) OUTLOOK_SELECTED.add(key); else OUTLOOK_SELECTED.delete(key);
  updateOutlookSelectionUi();
});

async function bulkMarkOutlookStatus(status) {
  const items = Array.from(OUTLOOK_SELECTED).map(key => { const [source, ...rest] = key.split('|'); return {source, email:rest.join('|')}; });
  if (!items.length) { showToast('请先选择邮箱'); return; }
  const labelMap = {available:'未使用/可用', disabled:'停用', failed:'失败'};
  const label = labelMap[status] || status;
  if (!confirm(`确定把选中的 ${items.length} 个邮箱标记为${label}吗？`)) return;
  try {
    const r = await api('/api/outlook/status-bulk', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({items, status, source:$('#poolSource').value, note:`批量标记${label}`})});
    OUTLOOK_SELECTED.clear();
    showToast(`已更新 ${r.updated_count || 0} 个${(r.skipped || []).length ? `，跳过 ${(r.skipped || []).length} 个` : ''}`);
    loadOutlook(); loadSummary();
  } catch(err) { showToast('批量标记失败: ' + err.message); updateOutlookSelectionUi(); }
}
async function deleteSelectedOutlook() {
  const items = Array.from(OUTLOOK_SELECTED).map(key => { const [source, ...rest] = key.split('|'); return {source, email:rest.join('|')}; });
  if (!items.length) { showToast('请先选择邮箱'); return; }
  if (!confirm(`确定从邮箱池删除选中的 ${items.length} 个邮箱吗？\n\n此操作不可撤销。`)) return;
  try {
    const r = await api('/api/outlook/delete-bulk', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({items, source:$('#poolSource').value})});
    (r.deleted || []).forEach(item => OUTLOOK_SELECTED.delete(`${item.source}|${item.email}`));
    showToast(`已删除 ${r.deleted_count || 0} 个${(r.skipped || []).length ? `，跳过 ${(r.skipped || []).length} 个` : ''}`);
    loadOutlook(); loadSummary();
  } catch(err) { showToast('批量删除失败: ' + err.message); updateOutlookSelectionUi(); }
}

let legacyImportPreview = null;
function clearImportPreview() {
  legacyImportPreview = null;
  const el = $('#importPreview');
  if (el) el.innerHTML = '';
  const btn = $('#btnImport');
  if (btn) btn.disabled = false;
}
function renderImportPreview(data) {
  const el = $('#importPreview');
  if (!el) return;
  const invalid = (data.invalid_rows || []).slice(0, 6).map(row => `第 ${esc(row.line)} 行：${esc(row.reason)}`).join('<br>');
  el.innerHTML = `<div class="banner info">解析 ${esc(data.total_lines)} 行（有效 ${esc(data.valid)}）：可新增 ${esc(data.new)}，已存在 ${esc(data.existing)}，输入重复 ${esc(data.duplicate_in_input)}，无效 ${esc(data.invalid)}${data.extra_fields ? `；忽略多余字段 ${esc(data.extra_fields)} 个` : ''}</div>${invalid ? `<div class="hint">${invalid}</div>` : ''}`;
}
async function previewImport() {
  const text = $('#importText').value;
  const source = $('#importSource').value;
  if (!text.trim()) { showToast('请粘贴邮箱资源'); return; }
  const btn = $('#btnPreviewImport');
  if (btn) { btn.disabled = true; btn.textContent = '解析中…'; }
  try {
    legacyImportPreview = await api('/api/outlook/import-preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text, source})});
    renderImportPreview(legacyImportPreview);
    $('#btnImport').disabled = Number(legacyImportPreview.new || 0) === 0;
  } catch (err) {
    legacyImportPreview = null;
    $('#importPreview').innerHTML = `<div class="banner warn">${esc(err.message)}</div>`;
    $('#btnImport').disabled = true;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '解析预览'; }
  }
}
$('#importText').addEventListener('input', clearImportPreview);
$('#btnPreviewImport').addEventListener('click', previewImport);
$('#btnImport').addEventListener('click', async () => {
  const text = $('#importText').value;
  if (!text.trim()) { showToast('请粘贴邮箱资源'); return; }
  $('#btnImport').disabled = true;
  try {
    if (!legacyImportPreview) await previewImport();
    if (!legacyImportPreview) return;
    if (Number(legacyImportPreview.new || 0) === 0) { showToast('没有可新增的邮箱资源'); return; }
    const source = $('#importSource').value;
    const r = await api('/api/outlook/import', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, source}) });
    $('#importResult').innerHTML = `<div class="banner info">导入邮箱池：解析 ${esc(r.parsed)} 行，新增 ${esc(r.inserted)}，跳过 ${esc(r.skipped)}${r.invalid || r.extra_fields ? `；无效 ${esc(r.invalid || 0)} 行，忽略多余字段 ${esc(r.extra_fields || 0)} 个` : ''}</div>`;
    $('#importText').value = '';
    clearImportPreview();
    $('#poolSource').value = source;
    loadOutlook(); loadSummary();
  } catch(e) { $('#importResult').innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; }
  finally { $('#btnImport').disabled = false; }
});
