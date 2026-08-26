// ---------- Codex 授权 ----------
let CODEX = [];
let CODEX_TOTAL = 0;
async function loadCodex() {
  try {
    const p = PAGERS.codex;
    const q = $('#qCodex') ? $('#qCodex').value.trim() : '';
    const r = await api(`/api/codex?paged=1&page=${encodeURIComponent(p.page)}&page_size=${encodeURIComponent(p.size)}&q=${encodeURIComponent(q)}`);
    CODEX = r.accounts || [];
    CODEX_TOTAL = Number(r.total || CODEX.length || 0);
    const totalPages = Math.max(1, Math.ceil(CODEX_TOTAL / p.size));
    if (p.page > totalPages) { p.page = totalPages; return loadCodex(); }
    $('#codexStatTotal').textContent = r.summary?.total ?? 0;
    $('#codexStatExported').textContent = r.summary?.exported ?? 0;
    $('#codexStatPending').textContent = r.summary?.pending ?? 0;
    renderCodex();
  } catch(e) { showToast('加载 Codex 列表失败: ' + e.message); }
}
const CODEX_SELECTED = new Set();
function _codexUpdateSelectedHint() {
  $('#codexSelectedHint').textContent = `已选 ${CODEX_SELECTED.size}`;
  $('#btnCodexDownloadBulk').disabled = CODEX_SELECTED.size === 0;
  const cpaBulkBtn = $('#btnCodexDownloadBulkCpa');
  if (cpaBulkBtn) cpaBulkBtn.disabled = CODEX_SELECTED.size === 0;
  const delBtn = $('#btnCodexDeleteBulk');
  if (delBtn) delBtn.disabled = CODEX_SELECTED.size === 0;
}
function renderCodex() {
  const total = CODEX_TOTAL;
  const rows = CODEX;
  $('#codexBody').innerHTML = rows.map(r => {
    const exported = (r.exported_count || 0) > 0;
    const statusBadge = exported
      ? `<span class="pill status-used" title="导出 ${esc(r.exported_count)} 次，最近 ${esc(r.exported_at || '-')}">已导出</span>`
      : `<span class="pill status-available">未导出</span>`;
    const checked = CODEX_SELECTED.has(r.filename) ? 'checked' : '';
    return `
    <tr>
      <td><input type="checkbox" class="codex-row-check" data-fname="${esc(r.filename)}" ${checked}></td>
      <td><div class="main-cell">${esc(r.email || '-')}</div><div class="sub-cell mono">${esc(r.filename)}</div></td>
      <td>${esc(r.plan || '-')}</td>
      <td>${statusBadge}</td>
      <td><span class="mono">${esc(r.account_id || '-')}</span></td>
      <td class="muted">${esc(r.mtime || '-')}</td>
      <td class="muted">${esc(r.expired || '-')}</td>
      <td class="actions">
        <button class="primary" data-codex-download="${esc(r.filename)}" title="下载本地 codex_accounts/ 中的 JSON/回执">本地下载</button>
        <button class="good" data-codex-download-cpa="${esc(r.filename)}" title="按邮箱从 CPA auth-files 下载真实 Codex JSON">从CPA下载</button>
        ${exported ? `<button data-codex-reset="${esc(r.filename)}" title="重新标记为未导出">重置标记</button>` : ''}
        <button class="danger" data-codex-delete="${esc(r.filename)}" title="删除本地 Codex JSON 凭证文件">删除</button>
      </td>
    </tr>`;
  }).join('') || '<tr><td colspan="8" class="muted">还没有 Codex 凭证。注册成功并跑通 Codex 授权后会自动出现。</td></tr>';
  // 全选 checkbox：仅反映当前页状态
  const pageFilenames = rows.map(r => r.filename);
  const allChecked = pageFilenames.length > 0 && pageFilenames.every(f => CODEX_SELECTED.has(f));
  $('#codexSelectAll').checked = allChecked;
  $('#codexSelectAll').indeterminate = !allChecked && pageFilenames.some(f => CODEX_SELECTED.has(f));
  _codexUpdateSelectedHint();
  _renderPager('codex', total);
}
$('#qCodex').addEventListener('input', debounce(() => { PAGERS.codex.page = 1; loadCodex(); }, 250));
$('#btnRefreshCodex').addEventListener('click', loadCodex);

// 全选 / 取消全选（仅当前页可见行）
$('#codexSelectAll').addEventListener('change', (e) => {
  const pageRows = CODEX;
  if (e.target.checked) pageRows.forEach(r => CODEX_SELECTED.add(r.filename));
  else pageRows.forEach(r => CODEX_SELECTED.delete(r.filename));
  renderCodex();
});

// 行 checkbox 变化（事件委托）
$('#codexBody').addEventListener('change', (e) => {
  const cb = e.target.closest('.codex-row-check');
  if (!cb) return;
  if (cb.checked) CODEX_SELECTED.add(cb.dataset.fname);
  else CODEX_SELECTED.delete(cb.dataset.fname);
  _codexUpdateSelectedHint();
  const pageFilenames = CODEX.map(r => r.filename);
  const allChecked = pageFilenames.length > 0 && pageFilenames.every(f => CODEX_SELECTED.has(f));
  $('#codexSelectAll').checked = allChecked;
  $('#codexSelectAll').indeterminate = !allChecked && pageFilenames.some(f => CODEX_SELECTED.has(f));
});

// 批量下载
$('#btnCodexDownloadBulk').addEventListener('click', async () => {
  if (CODEX_SELECTED.size === 0) return;
  const filenames = Array.from(CODEX_SELECTED);
  const note = `选中 ${filenames.length} 个凭证，打包到一个 JSON 文件下载。\n\n` +
               `⚠ 这个聚合格式 CPA 不能直接读，主要用于备份/迁移。\n` +
               `要给 CPA 用请用每行的"下载 JSON"单个下载。\n\n继续？`;
  if (!confirm(note)) return;
  $('#btnCodexDownloadBulk').disabled = true;
  try {
    const resp = await fetch('/api/codex/download-bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames }),
    });
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({}));
      throw new Error(e.error || ('HTTP ' + resp.status));
    }
    const cd = resp.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="([^"]+)"/);
    const dlname = m ? m[1] : `codex-bulk-${Date.now()}.json`;
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = dlname;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 800);
    showToast(`已打包下载 ${filenames.length} 个`);
    CODEX_SELECTED.clear();
    setTimeout(loadCodex, 600);
  } catch(err) {
    showToast('批量下载失败: ' + err.message);
  } finally {
    _codexUpdateSelectedHint();
  }
});


$('#btnCodexDownloadBulkCpa').addEventListener('click', async () => {
  if (CODEX_SELECTED.size === 0) return;
  const filenames = Array.from(CODEX_SELECTED);
  const note = `选中 ${filenames.length} 个本地记录，将按邮箱到 CPA auth-files 查找并下载真实 Codex JSON。\n\n` +
               `下载结果会打包成 ZIP，解压后每个 JSON 可直接放入 CPA auth-dir。\n` +
               `如 CPA 中找不到对应邮箱，会在 zip 的 manifest.json 记录错误。\n\n继续？`;
  if (!confirm(note)) return;
  const btn = $('#btnCodexDownloadBulkCpa');
  btn.disabled = true;
  try {
    const resp = await fetch('/api/codex/download-bulk-from-cpa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames }),
    });
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({}));
      const detail = Array.isArray(e.errors) && e.errors.length ? ('；' + e.errors.slice(0, 3).map(x => `${x.filename}: ${x.error}`).join('；')) : '';
      throw new Error((e.error || ('HTTP ' + resp.status)) + detail);
    }
    const cd = resp.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="([^"]+)"/);
    const dlname = m ? m[1] : `codex-cpa-bulk-${Date.now()}.zip`;
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = dlname;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 800);
    showToast(`已从 CPA 打包下载 ${filenames.length} 个（详情见 manifest.json）`);
    CODEX_SELECTED.clear();
    setTimeout(loadCodex, 600);
  } catch(err) {
    showToast('从 CPA 批量下载失败: ' + err.message);
  } finally {
    _codexUpdateSelectedHint();
  }
});

$('#btnCodexDeleteBulk').addEventListener('click', async () => {
  if (CODEX_SELECTED.size === 0) return;
  const filenames = Array.from(CODEX_SELECTED);
  if (!confirm(`确定删除选中的 ${filenames.length} 个 Codex 凭证吗？\n\n会删除本地 codex_accounts/ 下的 JSON 文件，并清理导出标记。此操作不可撤销。`)) return;
  $('#btnCodexDeleteBulk').disabled = true;
  try {
    const r = await api('/api/codex/delete-bulk', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({filenames}),
    });
    (r.deleted || []).forEach(fname => CODEX_SELECTED.delete(fname));
    const skipped = (r.skipped || []).length;
    showToast(skipped ? `已删除 ${r.deleted_count || 0} 个，跳过 ${skipped} 个` : `已删除 ${r.deleted_count || 0} 个`);
    loadCodex();
  } catch(err) {
    showToast('批量删除失败: ' + err.message);
    _codexUpdateSelectedHint();
  }
});

$('#codexBody').addEventListener('click', async (e) => {
  const dlCpa = e.target.closest('[data-codex-download-cpa]');
  if (dlCpa) {
    const fname = dlCpa.dataset.codexDownloadCpa;
    dlCpa.disabled = true;
    try {
      const resp = await fetch(`/api/codex/download-from-cpa/${encodeURIComponent(fname)}`);
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({}));
        throw new Error(e.error || ('HTTP ' + resp.status));
      }
      const cd = resp.headers.get('Content-Disposition') || '';
      const m = cd.match(/filename="([^"]+)"/);
      const dlname = m ? m[1] : fname.replace(/-cpa-callback\.json$/i, '-free.json');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = dlname;
      document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 800);
      showToast('已从 CPA 下载');
      setTimeout(loadCodex, 600);
    } catch(err) {
      showToast('从 CPA 下载失败: ' + err.message);
      dlCpa.disabled = false;
    }
    return;
  }
  const dl = e.target.closest('[data-codex-download]');
  if (dl) {
    const fname = dl.dataset.codexDownload;
    window.location.href = `/api/codex/download/${encodeURIComponent(fname)}`;
    setTimeout(loadCodex, 800);
    return;
  }
  const del = e.target.closest('[data-codex-delete]');
  if (del) {
    const fname = del.dataset.codexDelete;
    if (!confirm(`确定删除 Codex 凭证？\n\n${fname}\n\n会删除本地 JSON 文件，并清理导出标记。此操作不可撤销。`)) return;
    del.disabled = true;
    try {
      await api('/api/codex/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({filename: fname}) });
      CODEX_SELECTED.delete(fname);
      showToast('Codex 凭证已删除');
      loadCodex();
    } catch(err) {
      showToast('删除失败: ' + err.message);
      del.disabled = false;
    }
    return;
  }
  const rs = e.target.closest('[data-codex-reset]');
  if (rs) {
    const fname = rs.dataset.codexReset;
    if (!confirm(`把 ${fname} 标记重置为未导出？`)) return;
    try {
      await api('/api/codex/reset-export', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({filename: fname}) });
      showToast('已重置');
      loadCodex();
    } catch(err) { showToast('重置失败: ' + err.message); }
  }
});
