// ---------- Codex 授权 ----------
let CODEX = [];
let CODEX_TOTAL = 0;
let codexLoading = false;
let codexReloadQueued = false;
function getCodexQuery() {
  const el = document.getElementById('qCodexV2');
  return (el ? el.value : '').trim();
}
let CODEX_SHOW_ARCHIVED = false;
async function loadCodex() {
  if (codexLoading) { codexReloadQueued = true; return; }
  codexLoading = true;
  setListBusy('codexPanelV2', true);
  try {
    const p = PAGERS.codex;
    const q = getCodexQuery();
    const status = document.getElementById('codexStatusFilterV2')?.value || '';
    CODEX_SHOW_ARCHIVED = status === 'archived';
    const archived = CODEX_SHOW_ARCHIVED ? 'only' : '0';
    const dateFrom = document.getElementById('dateFromCodexV2')?.value || '';
    const dateTo = document.getElementById('dateToCodexV2')?.value || '';
    const params = new URLSearchParams({paged:'1', page:String(p.page), page_size:String(p.size), q, archived, date_from:dateFrom, date_to:dateTo});
    params.set('plan', document.getElementById('codexPlanFilterV2')?.value || '');
    params.set('status', status === 'archived' ? '' : status);
    params.set('oauth_status', document.getElementById('codexOauthFilterV2')?.value || '');
    params.set('account_id', document.getElementById('codexAccountFilterV2')?.value || '');
    params.set('expired_date', document.getElementById('codexExpiredFilterV2')?.value || '');
    const r = await api(`/api/codex?${params.toString()}`);
    const facets = r.facets || {};
    syncFacetSelect('codexPlanFilterV2', facets.plan, {group:'plan'});
    syncFacetSelect('codexStatusFilterV2', facets.status, {group:'status', allLabel:'未归档'});
    syncFacetSelect('codexOauthFilterV2', facets.oauth_status, {group:'oauth_status'});
    CODEX = r.accounts || [];
    CODEX_TOTAL = Number(r.total || CODEX.length || 0);
    const totalPages = Math.max(1, Math.ceil(CODEX_TOTAL / p.size));
    if (p.page > totalPages) { p.page = totalPages; return loadCodex(); }
    const st = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    renderCodex();
  } catch(e) {
    if (!CODEX.length) $('#codexBodyV2').innerHTML = renderTableStateRow(9, '授权凭证加载失败', '请检查服务状态后刷新列表。', 'error');
    showToast('加载 Codex 列表失败: ' + e.message);
  }
  finally {
    codexLoading = false;
    setListBusy('codexPanelV2', false);
    if (codexReloadQueued) {
      codexReloadQueued = false;
      queueMicrotask(loadCodex);
    }
  }
}
async function refreshCodexManual(btn) {
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = '刷新中…';
  try { await loadCodex(); showToast('Codex 凭证已刷新'); }
  finally { btn.textContent = old; btn.disabled = false; }
}
const CODEX_SELECTED = new Set();
function _codexUpdateSelectedHint() {
  const none = CODEX_SELECTED.size === 0;
  const hint = document.getElementById('codexSelectedHintV2');
  document.getElementById('codexToolbarV2')?.classList.toggle('has-selection', !none);
  if (hint) hint.textContent = none ? '选择凭证后批量操作' : `已选 ${CODEX_SELECTED.size} 个凭证`;
  const archiveBtn = document.getElementById('btnCodexArchiveBulkV2');
  if (archiveBtn) {
    archiveBtn.disabled = none;
    archiveBtn.textContent = CODEX_SHOW_ARCHIVED ? '恢复选中' : '归档选中';
    archiveBtn.title = CODEX_SHOW_ARCHIVED ? '把选中的归档凭证恢复到默认列表' : '归档选中的 Codex 授权凭证；默认列表不再显示';
  }
  ['btnCodexRefreshTokenBulkV2', 'btnCodexReauthorizeBulkV2', 'btnCodexDownloadBulkV2', 'btnCodexDownloadBulkCpaV2', 'btnCodexDeleteBulkV2', 'btnCodexUploadSub2V2'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = none;
  });
}
function _codexStatusBadge(r) {
  const exported = (r.exported_count || 0) > 0;
  return exported
    ? `<span class="pill status-used" title="导出 ${esc(r.exported_count)} 次，最近 ${esc(r.exported_at || '-')}">已导出</span>`
    : `<span class="pill status-available">未导出</span>`;
}
function _codexOauthBadge(r) {
  const status = String(r.oauth_status || 'unknown');
  const remoteHttpStatus = Number(r.sub2api_http_status);
  const seconds = Number(r.oauth_seconds_left);
  let remaining = '';
  if (Number.isFinite(seconds)) {
    const absolute = Math.abs(seconds);
    const days = Math.floor(absolute / 86400);
    const hours = Math.floor((absolute % 86400) / 3600);
    remaining = seconds < 0 ? `已过期 ${days}天${hours}小时` : `剩余 ${days}天${hours}小时`;
  }
  const details = [remoteHttpStatus ? `Sub2API HTTP ${remoteHttpStatus}` : '', r.oauth_expires_at ? `过期：${r.oauth_expires_at}` : '', remaining, r.oauth_refreshable ? '存在 refresh_token，可尝试自动刷新' : '缺少 refresh_token', Number(r.sub2_uploaded_count || 0) > 0 ? '已纳入 sub2 自动同步' : '未记录 sub2 自动同步', r.oauth_refresh_error ? `最近刷新失败：${r.oauth_refresh_error}` : '', r.sub2_sync_error ? `sub2 同步失败：${r.sub2_sync_error}` : ''].filter(Boolean).join('；');
  if (remoteHttpStatus === 401) return `<span class="pill status-failed" title="${esc(details)}">401 失效</span>`;
  if (r.oauth_reauth_required) return `<span class="pill status-failed" title="${esc(details)}">需重授权</span>`;
  if (status === 'valid') return `<span class="pill status-success" title="${esc(details)}">有效</span>`;
  if (status === 'expiring') return `<span class="pill status-running" title="${esc(details)}">即将过期</span>`;
  if (status === 'expired') return `<span class="pill status-failed" title="${esc(details)}">${r.oauth_refreshable ? '已过期' : '已过期·需重授权'}</span>`;
  if (status === 'missing') return `<span class="pill status-failed" title="${esc(details)}">缺少令牌</span>`;
  return `<span class="pill status-used" title="${esc(details)}">未知</span>`;
}
function closeCodexV2MoreMenus() {
  document.querySelectorAll('.codex-table-v2 .acc-v2-more.open').forEach(el => el.classList.remove('open'));
}
function positionCodexV2MoreMenu(wrap) {
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
function syncCodexSelectAllUi(pageRows = null) {
  if (!pageRows) pageRows = CODEX;
  const pageFilenames = pageRows.map(r => r.filename);
  const allChecked = pageFilenames.length > 0 && pageFilenames.every(f => CODEX_SELECTED.has(f));
  const someChecked = pageFilenames.some(f => CODEX_SELECTED.has(f));
  const cb = document.getElementById('codexSelectAllV2');
  if (!cb) return;
  cb.checked = allChecked;
  cb.indeterminate = !allChecked && someChecked;
  cb.disabled = pageFilenames.length === 0;
}
function renderCodex() {
  const total = CODEX_TOTAL;
  const rows = CODEX;
  const body = $('#codexBodyV2');
  if (!body) return;
  body.innerHTML = rows.map(r => {
    const checked = CODEX_SELECTED.has(r.filename) ? 'checked' : '';
    const exported = (r.exported_count || 0) > 0;
    const moreItems = [
      `<button type="button" class="good" data-codex-refresh-token="${esc(r.filename)}" title="使用 refresh_token 换新 access token，不需要邮箱或短信验证码">刷新 OAuth Token</button>`,
      `<button type="button" class="good" data-codex-download-cpa="${esc(r.filename)}" title="按邮箱从 CPA auth-files 下载真实 Codex JSON">从CPA下载</button>`,
      `<button type="button" class="good" data-codex-upload-sub2="${esc(r.filename)}" title="把这份本地 Codex OAuth 凭证上传到 sub2api">上传 sub2api</button>`,
      exported ? `<button type="button" data-codex-reset="${esc(r.filename)}" title="重新标记为未导出">重置标记</button>` : '',
      `<button type="button" class="${r.archived ? 'good' : ''}" data-codex-archive="${esc(r.filename)}" data-archived="${r.archived ? '0' : '1'}" title="${r.archived ? '恢复到默认 Codex 列表' : '归档后默认列表不再显示'}">${r.archived ? '恢复' : '归档'}</button>`,
    ].filter(Boolean).join('');
    return `
    <tr>
      <td class="col-check"><input type="checkbox" class="codex-row-check" data-fname="${esc(r.filename)}" ${checked}></td>
      <td class="col-email" title="${esc(r.email || '')} · 文件：${esc(r.filename || '')}">
        <div class="acc-v2-email">${esc(r.email || '-')}${r.archived ? ' <span class="pill status-used" title="已归档">归档</span>' : ''}</div>
      </td>
      <td class="col-plan">${esc(r.plan || '-')}</td>
      <td class="col-status">${_codexStatusBadge(r)}</td>
      <td class="col-status">${_codexOauthBadge(r)}</td>
      <td class="col-account" title="${esc(r.account_id || '-')}">${esc(r.account_id || '-')}</td>
      <td class="col-time" title="${esc(r.mtime || '-')}">${esc(r.mtime || '-')}</td>
      <td class="col-time" title="${esc(r.expired || '-')}">${esc(r.expired || '-')}</td>
      <td class="col-actions">
        <div class="acc-v2-actions">
          <button type="button" data-codex-reauthorize="${esc(r.filename)}" title="重新执行 Codex OAuth 授权；会消耗邮箱 OTP 和接码短信">重跑授权</button>
          <button type="button" class="primary" data-codex-download="${esc(r.filename)}" title="下载本地 codex_accounts/ 中的 JSON/回执">本地下载</button>
          <button type="button" class="danger" data-codex-delete="${esc(r.filename)}" title="删除本地 Codex JSON 凭证文件">删除</button>
          <div class="acc-v2-more">
            <button type="button" class="acc-v2-more-btn" data-codex-more-toggle aria-haspopup="true">更多</button>
            <div class="acc-v2-more-menu" role="menu">${moreItems}</div>
          </div>
        </div>
      </td>
    </tr>`;
  }).join('') || renderTableStateRow(9, '暂无授权凭证', '调整筛选条件，或从账号页发起 Codex 授权。');
  syncCodexSelectAllUi(rows);
  const summary = $('#codexPageSummary');
  if (summary) summary.textContent = `${total || 0} 个凭证 · 当前页 ${rows.length} 条`;
  _codexUpdateSelectedHint();
  _renderPager('codex', total);
}
function syncCodexSelectAll(checked) {
  const pageRows = CODEX;
  if (checked) pageRows.forEach(r => CODEX_SELECTED.add(r.filename));
  else pageRows.forEach(r => CODEX_SELECTED.delete(r.filename));
  renderCodex();
}
function onCodexBodyChange(e) {
  const cb = e.target.closest('.codex-row-check');
  if (!cb) return;
  if (cb.checked) CODEX_SELECTED.add(cb.dataset.fname);
  else CODEX_SELECTED.delete(cb.dataset.fname);
  _codexUpdateSelectedHint();
  syncCodexSelectAllUi();
}
async function onCodexBodyClick(e) {
  const moreToggle = e.target.closest('[data-codex-more-toggle]');
  if (moreToggle) {
    e.preventDefault();
    e.stopPropagation();
    const wrap = moreToggle.closest('.acc-v2-more');
    if (!wrap) return;
    const willOpen = !wrap.classList.contains('open');
    closeCodexV2MoreMenus();
    if (willOpen) {
      wrap.classList.add('open');
      positionCodexV2MoreMenu(wrap);
    }
    return;
  }
  if (e.target.closest('.acc-v2-more-menu')) closeCodexV2MoreMenus();

  const reauthorize = e.target.closest('[data-codex-reauthorize]');
  if (reauthorize) {
    await codexReauthorize([reauthorize.dataset.codexReauthorize]);
    return;
  }

  const refreshToken = e.target.closest('[data-codex-refresh-token]');
  if (refreshToken) {
    await codexRefreshTokens([refreshToken.dataset.codexRefreshToken]);
    return;
  }

  const uploadSub2 = e.target.closest('[data-codex-upload-sub2]');
  if (uploadSub2) {
    await codexUploadSub2([uploadSub2.dataset.codexUploadSub2]);
    return;
  }

  const dlCpa = e.target.closest('[data-codex-download-cpa]');
  if (dlCpa) {
    const fname = dlCpa.dataset.codexDownloadCpa;
    dlCpa.disabled = true;
    try {
      const resp = await fetch(`/api/codex/download-from-cpa/${encodeURIComponent(fname)}`);
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(errBody.error || ('HTTP ' + resp.status));
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
  const ar = e.target.closest('[data-codex-archive]');
  if (ar) {
    const fname = ar.dataset.codexArchive;
    const archived = ar.dataset.archived === '1';
    ar.disabled = true;
    try {
      await api('/api/codex/archive', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({filename: fname, archived}) });
      CODEX_SELECTED.delete(fname);
      showToast(archived ? '已归档' : '已恢复');
      loadCodex();
    } catch(err) {
      showToast('归档失败: ' + err.message);
      ar.disabled = false;
    }
  }
}
async function codexArchiveSelected() {
  if (CODEX_SELECTED.size === 0) return;
  const filenames = Array.from(CODEX_SELECTED);
  const archived = !CODEX_SHOW_ARCHIVED;
  if (!confirm(`${archived ? '归档' : '恢复'}选中的 ${filenames.length} 个 Codex 授权凭证？`)) return;
  try {
    const r = await api('/api/codex/archive-bulk', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({filenames, archived}),
    });
    (r.updated || []).forEach(item => CODEX_SELECTED.delete(item.filename));
    showToast(`${archived ? '归档' : '恢复'}成功 ${r.updated_count || 0} 个`);
    loadCodex();
  } catch(err) { showToast('归档失败: ' + err.message); }
}
function applyCodexArchivedFilter(on) {
  CODEX_SHOW_ARCHIVED = !!on;
  const btn = document.getElementById('showArchivedCodexV2');
  if (btn) {
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.classList.toggle('is-active', on);
  }
  CODEX_SELECTED.clear();
  PAGERS.codex.page = 1;
  loadCodex();
}
async function codexDownloadBulkLocal() {
  if (CODEX_SELECTED.size === 0) return;
  const filenames = Array.from(CODEX_SELECTED);
  const note = `选中 ${filenames.length} 个凭证，打包到一个 JSON 文件下载。\n\n` +
               `⚠ 这个聚合格式 CPA 不能直接读，主要用于备份/迁移。\n` +
               `要给 CPA 用请用每行的"下载 JSON"单个下载。\n\n继续？`;
  if (!confirm(note)) return;
  const btn = $('#btnCodexDownloadBulkV2');
  if (btn) btn.disabled = true;
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
}
async function codexDownloadBulkCpa() {
  if (CODEX_SELECTED.size === 0) return;
  const filenames = Array.from(CODEX_SELECTED);
  const note = `选中 ${filenames.length} 个本地记录，将按邮箱到 CPA auth-files 查找并下载真实 Codex JSON。\n\n` +
               `下载结果会打包成 ZIP，解压后每个 JSON 可直接放入 CPA auth-dir。\n` +
               `如 CPA 中找不到对应邮箱，会在 zip 的 manifest.json 记录错误。\n\n继续？`;
  if (!confirm(note)) return;
  const btn = $('#btnCodexDownloadBulkCpaV2');
  if (btn) btn.disabled = true;
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
}
async function codexReauthorize(filenames = null) {
  const selected = Array.isArray(filenames) ? filenames.filter(Boolean) : Array.from(CODEX_SELECTED);
  if (!selected.length) return;
  const workers = getAccountOperationWorkers();
  const note = `确定为选中的 ${selected.length} 个账号重新执行 Codex OAuth 授权吗？\n\n` +
               `每个账号将消耗：\n  • 1 封邮箱 OTP\n  • 1 个接码短信\n\n` +
               `账号操作公共并发：${workers}\n\n` +
               `授权成功后会更新本地 Codex 凭证；如需同步到 sub2api，请等待成功后再点击“上传 sub2api”。`;
  if (!confirm(note)) return;
  const btn = document.getElementById('btnCodexReauthorizeBulkV2');
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/codex/retry-bulk', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({filenames: selected}),
    });
    const startedFilenames = new Set((r.started || []).map(item => item.filename).filter(Boolean));
    startedFilenames.forEach(filename => CODEX_SELECTED.delete(filename));
    const skipped = (r.skipped || []).length;
    showToast(skipped ? `已开始重跑 ${r.started_count || 0} 个，跳过 ${skipped} 个` : (r.message || '已开始重跑 Codex 授权'));
    const search = document.getElementById('accountTaskTargetFilterV2');
    const typeFilter = document.getElementById('accountTaskTypeFilterV2');
    if (search) search.value = '';
    if (typeFilter) typeFilter.value = 'codex_retry';
    PAGERS.accountTasks.page = 1;
    activateTab('tasks');
  } catch(err) {
    showToast('重跑 Codex 授权失败: ' + err.message);
  } finally {
    _codexUpdateSelectedHint();
  }
}
async function codexRefreshTokens(filenames = null) {
  const selected = Array.isArray(filenames) ? filenames.filter(Boolean) : Array.from(CODEX_SELECTED);
  if (!selected.length) return;
  const legacyUntracked = selected.some(filename => {
    const row = CODEX.find(item => item.filename === filename);
    return row && Number(row.exported_count || 0) > 0 && Number(row.sub2_uploaded_count || 0) === 0;
  });
  let note = `使用 refresh_token 刷新选中的 ${selected.length} 个 Codex OAuth 凭证？\n\n` +
             `这个操作不发邮箱验证码、不用接码短信。刷新成功后，本地凭证会更新；已记录为上传过 sub2api 的凭证也会自动同步。`;
  if (legacyUntracked) note += `\n\n⚠ 检测到旧版“已导出”记录，无法区分当时是下载还是上传 sub2api。如果这些凭证正在 sub2api 使用，建议先取消并点一次“上传 sub2api”，建立自动同步记录。`;
  if (!confirm(note)) return;
  const btn = document.getElementById('btnCodexRefreshTokenBulkV2');
  if (btn) btn.disabled = true;
  try {
    const r = await api('/api/codex/refresh-token-bulk', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({filenames: selected}),
    });
    (r.started || []).forEach(item => CODEX_SELECTED.delete(item.filename));
    const skipped = (r.skipped || []).length;
    showToast(skipped ? `已开始刷新 ${r.started_count || 0} 个，跳过 ${skipped} 个` : (r.message || '已开始刷新 OAuth Token'));
    const search = document.getElementById('accountTaskTargetFilterV2');
    const typeFilter = document.getElementById('accountTaskTypeFilterV2');
    if (search) search.value = '';
    if (typeFilter) typeFilter.value = 'codex_token_refresh';
    PAGERS.accountTasks.page = 1;
    activateTab('tasks');
  } catch(err) {
    showToast('刷新 OAuth Token 失败: ' + err.message);
  } finally {
    _codexUpdateSelectedHint();
  }
}
async function codexUploadSub2(filenames = null) {
  const selected = Array.isArray(filenames) ? filenames.filter(Boolean) : Array.from(CODEX_SELECTED);
  if (!selected.length) return;
  if (!confirm(`把选中的 ${selected.length} 个 Codex OAuth 凭证上传到 sub2api？\n\n同名账号将按 sub2api 的导入策略更新。`)) return;
  ['btnCodexUploadSub2V2'].forEach(id => {
    const btn = document.getElementById(id); if (btn) btn.disabled = true;
  });
  try {
    const r = await api('/api/codex/upload-sub2-bulk', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({filenames: selected}),
    });
    (r.uploaded || []).forEach(item => CODEX_SELECTED.delete(item.filename));
    const issues = Number(r.failed_count || 0) + Number(r.skipped_count || 0);
    showToast(issues ? `已上传 ${r.uploaded_count || 0} 个，${issues} 个未完成` : `已上传 ${r.uploaded_count || 0} 个到 sub2api`);
    await loadCodex();
  } catch(err) {
    showToast('上传 sub2api 失败: ' + err.message);
  } finally {
    _codexUpdateSelectedHint();
  }
}
async function codexDeleteBulk() {
  if (CODEX_SELECTED.size === 0) return;
  const filenames = Array.from(CODEX_SELECTED);
  if (!confirm(`确定删除选中的 ${filenames.length} 个 Codex 凭证吗？\n\n会删除本地 codex_accounts/ 下的 JSON 文件，并清理导出标记。此操作不可撤销。`)) return;
  const btn = $('#btnCodexDeleteBulkV2');
  if (btn) btn.disabled = true;
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
}
(function bindCodexV2() {
  const qV2 = $('#qCodexV2');
  if (qV2) qV2.addEventListener('input', debounce(() => {
    PAGERS.codex.page = 1; loadCodex();
  }, 250));
  const codexTextReload = debounce(() => { PAGERS.codex.page = 1; loadCodex(); }, 250);
  $('#codexAccountFilterV2')?.addEventListener('input', codexTextReload);
  ['codexPlanFilterV2','codexStatusFilterV2','codexOauthFilterV2','dateFromCodexV2','dateToCodexV2','codexExpiredFilterV2'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => { CODEX_SELECTED.clear(); PAGERS.codex.page = 1; loadCodex(); });
  });
  const selectAllV2 = $('#codexSelectAllV2');
  if (selectAllV2) selectAllV2.addEventListener('change', (e) => syncCodexSelectAll(e.target.checked));
  const bodyV2 = $('#codexBodyV2');
  if (bodyV2) {
    bodyV2.addEventListener('change', onCodexBodyChange);
    bodyV2.addEventListener('click', onCodexBodyClick);
  }
  const refreshV2 = $('#btnRefreshCodexV2');
  if (refreshV2) refreshV2.addEventListener('click', () => refreshCodexManual(refreshV2));
  const bind = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener('click', fn); };
  bind('btnCodexDownloadBulkV2', codexDownloadBulkLocal);
  bind('btnCodexDownloadBulkCpaV2', codexDownloadBulkCpa);
  bind('btnCodexRefreshTokenBulkV2', () => codexRefreshTokens());
  bind('btnCodexReauthorizeBulkV2', () => codexReauthorize());
  bind('btnCodexUploadSub2V2', () => codexUploadSub2());
  bind('btnCodexArchiveBulkV2', codexArchiveSelected);
  bind('btnCodexDeleteBulkV2', codexDeleteBulk);
  bind('btnResetCodexFiltersV2', () => {
    ['qCodexV2','codexPlanFilterV2','codexStatusFilterV2','codexOauthFilterV2','codexAccountFilterV2','dateFromCodexV2','dateToCodexV2','codexExpiredFilterV2'].forEach(id => { const el=document.getElementById(id); if (el) el.value=''; });
    CODEX_SHOW_ARCHIVED = false; CODEX_SELECTED.clear(); PAGERS.codex.page = 1; refreshColumnFilterStates(); loadCodex();
  });
  document.addEventListener('click', (e) => {
    if (e.target.closest('.codex-table-v2 .acc-v2-more')) return;
    closeCodexV2MoreMenus();
  });
  window.addEventListener('scroll', () => closeCodexV2MoreMenus(), true);
  window.addEventListener('resize', () => closeCodexV2MoreMenus());
})();
