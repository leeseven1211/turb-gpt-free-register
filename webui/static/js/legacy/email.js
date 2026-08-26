// ---------- 邮箱池 ----------
function poolKey(r) { return `${r.source || $('#poolSource')?.value || 'outlook'}|${r.email || ''}`; }
function poolLabel(src) {
  return ({outlook:'Outlook', generic_api:'通用API', cloudflare_domain:'域名邮箱', icloud_hide:'iCloud 隐藏邮箱'})[src] || src || '-';
}
async function loadOutlook() {
  try {
    const source = $('#poolSource')?.value || 'outlook';
    const q = $('#qOutlook') ? $('#qOutlook').value.trim() : '';
    const p = PAGERS.outlook;
    const res = await api(`/api/outlook?paged=1&page=${encodeURIComponent(p.page)}&page_size=${encodeURIComponent(p.size)}&source=${encodeURIComponent(source)}&q=${encodeURIComponent(q)}`);
    OUTLOOK = res.items || [];
    OUTLOOK_TOTAL = Number(res.total || OUTLOOK.length || 0);
    const totalPages = Math.max(1, Math.ceil(OUTLOOK_TOTAL / p.size));
    if (p.page > totalPages) { p.page = totalPages; return loadOutlook(); }
    renderOutlook();
  } catch(e) {}
}
function renderOutlook() {
  const total = OUTLOOK_TOTAL;
  const rows = OUTLOOK;
  $('#outlookBody').innerHTML = rows.map(r => `
    <tr>
      <td><input type="checkbox" class="outlook-row-check" data-email="${esc(r.email)}" data-source="${esc(r.source || 'outlook')}" ${OUTLOOK_SELECTED.has(poolKey(r)) ? 'checked' : ''}></td>
      <td><div class="main-cell">${esc(r.email)}</div><div class="sub-cell mono">${esc(short(r.copy_line, 70))}</div></td>
      <td>${esc(poolLabel(r.source))}</td>
      <td>${pill(r.status)}</td>
      <td><span class="mono">${esc(short(r.access_token || '', 36) || '未生成')}</span></td>
      <td class="muted">${esc(r.imported_at || r.created_at || '-')}</td>
      <td class="muted">${esc(r.used_at || '-')}</td>
      <td class="actions">
        ${cbtn('复制邮箱', r.copy_line)} ${cbtn('复制Token', r.access_token, 'primary')} ${cbtn('复制整行', r.account_copy_line, 'good')}
        ${r.status !== 'available'
          ? `<button data-pool-act="available" data-email="${esc(r.email)}" data-source="${esc(r.source || 'outlook')}">恢复可用</button>`
          : ''}
        ${r.status !== 'disabled'
          ? `<button data-pool-act="disabled" data-email="${esc(r.email)}" data-source="${esc(r.source || 'outlook')}">停用</button>`
          : ''}
        ${r.status !== 'failed'
          ? `<button data-pool-act="failed" data-email="${esc(r.email)}" data-source="${esc(r.source || 'outlook')}">标失败</button>`
          : ''}
        <button data-pool-act="delete" data-email="${esc(r.email)}" data-source="${esc(r.source || 'outlook')}" style="border-color:#e7a3a0;color:#b3261e;">删除</button>
      </td>
    </tr>`).join('') || '<tr><td colspan="8" class="muted">邮箱池为空</td></tr>';
  updateOutlookSelectionUi(rows);
  _renderPager('outlook', total);
}
function updateOutlookSelectionUi(pageRows = null) {
  const hint = $('#outlookSelectedHint');
  const bulkBtn = $('#btnDeleteSelectedOutlook');
  const markAvailBtn = $('#btnMarkSelectedOutlookAvailable');
  const disableBtn = $('#btnDisableSelectedOutlook');
  const failBtn = $('#btnFailSelectedOutlook');
  if (hint) hint.textContent = `已选 ${OUTLOOK_SELECTED.size}`;
  if (bulkBtn) bulkBtn.disabled = OUTLOOK_SELECTED.size === 0;
  if (markAvailBtn) markAvailBtn.disabled = OUTLOOK_SELECTED.size === 0;
  if (disableBtn) disableBtn.disabled = OUTLOOK_SELECTED.size === 0;
  if (failBtn) failBtn.disabled = OUTLOOK_SELECTED.size === 0;

  const cbAll = $('#outlookSelectAll');
  if (!cbAll) return;
  if (!pageRows) {
    pageRows = OUTLOOK;
  }
  const pageKeys = pageRows.map(r => poolKey(r)).filter(Boolean);
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
  loadOutlook();
});
$('#copyAllEmails').addEventListener('click', () => copyText(OUTLOOK.map(r=>r.copy_line).filter(Boolean).join('\n')));
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
  const email = cb.dataset.email;
  const source = cb.dataset.source || $('#poolSource').value;
  const key = `${source}|${email}`;
  if (cb.checked) OUTLOOK_SELECTED.add(key);
  else OUTLOOK_SELECTED.delete(key);
  updateOutlookSelectionUi();
});

async function bulkMarkOutlookStatus(status) {
  const items = Array.from(OUTLOOK_SELECTED).map(key => {
    const [source, ...rest] = key.split('|');
    return {source, email: rest.join('|')};
  });
  if (items.length === 0) { showToast('请先选择邮箱'); return; }
  const labelMap = {available:'未使用/可用', disabled:'停用', failed:'失败'};
  const label = labelMap[status] || status;
  if (!confirm(`确定把选中的 ${items.length} 个邮箱标记为${label}吗？`)) return;
  const btn = status === 'disabled' ? $('#btnDisableSelectedOutlook') : status === 'failed' ? $('#btnFailSelectedOutlook') : $('#btnMarkSelectedOutlookAvailable');
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/outlook/status-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({items, status, source: $('#poolSource').value, note: `批量标记${label}`}),
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
  $('#btnDeleteSelectedOutlook').disabled = true;
  try {
    const r = await api('/api/outlook/delete-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({items, source: $('#poolSource').value}),
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
$('#btnImport').addEventListener('click', async () => {
  const text = $('#importText').value;
  if (!text.trim()) { showToast('请粘贴邮箱素材'); return; }
  $('#btnImport').disabled = true;
  try {
    const source = $('#importSource').value;
    const as_registered = $('#importAsRegistered')?.checked ?? true;
    const r = await api('/api/outlook/import', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, source, as_registered}) });
    const mode = r.as_registered ? '已注册账号' : '邮箱池素材';
    $('#importResult').innerHTML = `<div class="banner info">按 ${mode} 导入：解析 ${r.parsed} 行，新增 ${r.inserted}，跳过 ${r.skipped}${r.as_registered ? '；可到“账号”页选择后批量补跑 Codex' : ''}</div>`;
    $('#importText').value = '';
    $('#poolSource').value = source;
    loadOutlook(); loadAccounts(); loadSummary();
  } catch(e) { $('#importResult').innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; }
  finally { $('#btnImport').disabled = false; }
});
