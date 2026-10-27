// 手动供应与注册领取分开：浏览器只恢复原请求或原批次。
const BUTLER_IMPORT_STORAGE_KEY = 'turb.butler-import.v1';
const BUTLER_IMPORT_STATE = {
  preview: null, previewVersion: 0, request: null, batch: null,
  busy: false, polling: false, timer: null, opener: null,
  maxCount: 200, refreshedImported: -1, storageError: false,
};
const butlerImportElement = id => document.getElementById(id);

function butlerImportError(message = '') {
  const element = butlerImportElement('butlerImportError');
  if (element) { element.textContent = message; element.hidden = !message; }
}

function restoreButlerImport() {
  try {
    const saved = JSON.parse(localStorage.getItem(BUTLER_IMPORT_STORAGE_KEY) || 'null');
    if (!saved || typeof saved.request_id !== 'string' || typeof saved.preview_token !== 'string') return;
    BUTLER_IMPORT_STATE.request = {request_id: saved.request_id, preview_token: saved.preview_token, filters: saved.filters};
    const fields = {provider: 'butlerImportProvider', identity_type: 'butlerImportIdentity', count: 'butlerImportCount', domain: 'butlerImportDomain', group: 'butlerImportGroup'};
    for (const [key, id] of Object.entries(fields)) {
      const input = butlerImportElement(id);
      if (input && saved.filters && saved.filters[key] !== undefined) input.value = String(saved.filters[key]);
    }
    if (typeof saved.batch_id === 'string' && saved.batch_id) {
      BUTLER_IMPORT_STATE.batch = {batch_id: saved.batch_id, status: 'running'};
    }
  } catch (_) { BUTLER_IMPORT_STATE.storageError = true; }
}

function persistButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  const request = state.request;
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY, JSON.stringify({
    request_id: request.request_id, preview_token: request.preview_token,
    filters: request.filters, ...(state.batch ? {batch_id: state.batch.batch_id} : {}),
  }));
}

function butlerImportCanReset() {
  const batch = BUTLER_IMPORT_STATE.batch;
  return !!batch && !batch.can_retry && !Number(batch.unknown || 0)
    && ['completed', 'succeeded', 'done', 'partial', 'failed', 'rejected'].includes(batch.status);
}

function renderButlerImportControls() {
  const state = BUTLER_IMPORT_STATE;
  const locked = state.busy || !!state.request;
  for (const id of ['butlerImportProvider', 'butlerImportIdentity', 'butlerImportCount', 'butlerImportDomain', 'butlerImportGroup']) {
    const input = butlerImportElement(id);
    if (input) input.disabled = locked;
  }
  const preview = butlerImportElement('btnPreviewButlerImport');
  if (preview) {
    preview.disabled = locked;
    preview.hidden = !!state.request;
    preview.textContent = state.busy && !state.request ? '正在预览…' : '预览可导入邮箱';
  }
  const apply = butlerImportElement('btnApplyButlerImport');
  if (apply) {
    apply.disabled = locked || !state.preview || Number(state.preview.selected || 0) < 1;
    apply.textContent = state.busy && state.request && !state.batch ? '正在开始导入…' : '导入到本地库存';
    apply.hidden = !!state.request;
  }
  const retry = butlerImportElement('btnRetryButlerImport');
  if (retry) {
    retry.hidden = !state.request || (!!state.batch && !state.batch.can_retry);
    retry.disabled = state.busy || state.polling;
    retry.textContent = state.batch ? '继续原批次' : '重试原请求';
  }
  const reset = butlerImportElement('btnNewButlerImport');
  if (reset) { reset.hidden = !butlerImportCanReset(); reset.disabled = state.busy || state.polling; }
  const modal = butlerImportElement('butlerImportModal');
  if (modal) modal.setAttribute('aria-busy', state.busy || state.polling ? 'true' : 'false');
  for (const id of ['btnOpenButlerImport', 'btnOpenButlerImportPool']) {
    const opener = butlerImportElement(id);
    if (opener) opener.textContent = state.request && !butlerImportCanReset() ? '恢复 Butler 导入' : '从 Butler 导入';
  }
}

function butlerImportFilters() {
  const value = id => String(butlerImportElement(id)?.value || '').trim();
  const filters = {
    provider: value('butlerImportProvider'), identity_type: value('butlerImportIdentity'),
    count: Number(value('butlerImportCount')), domain: value('butlerImportDomain'), group: value('butlerImportGroup'),
  };
  if (filters.provider !== 'icloud_hme') throw new Error('当前仅支持从 Butler 导入 iCloud HME');
  if (!['all', 'primary', 'plus_alias'].includes(filters.identity_type)) throw new Error('请选择母邮箱、子邮箱或全部');
  if (!Number.isInteger(filters.count) || filters.count < 1 || filters.count > BUTLER_IMPORT_STATE.maxCount) {
    throw new Error(`数量须为 1–${BUTLER_IMPORT_STATE.maxCount} 的整数`);
  }
  return filters;
}

function invalidateButlerImportPreview() {
  if (BUTLER_IMPORT_STATE.request) return;
  BUTLER_IMPORT_STATE.previewVersion += 1;
  BUTLER_IMPORT_STATE.preview = null;
  const preview = butlerImportElement('butlerImportPreview');
  const items = butlerImportElement('butlerImportItems');
  if (preview) preview.textContent = '';
  if (items) items.innerHTML = '';
  butlerImportError();
  renderButlerImportControls();
}

async function loadButlerImportOptions() {
  try {
    const data = await api('/api/email-butler/import-options');
    if (data.ok === false) throw new Error(data.error || '无法读取导入选项');
    BUTLER_IMPORT_STATE.maxCount = Math.min(200, Math.max(1, Number(data.max_count) || 200));
    const count = butlerImportElement('butlerImportCount');
    if (count) count.max = String(BUTLER_IMPORT_STATE.maxCount);
    for (const [key, id] of [['domains', 'butlerImportDomains'], ['groups', 'butlerImportGroups']]) {
      const list = butlerImportElement(id);
      if (list) list.innerHTML = (data[key] || []).map(item => {
        const value = typeof item === 'string' ? item : item.value || item.name || '';
        return `<option value="${esc(value)}"></option>`;
      }).join('');
    }
  } catch (error) { butlerImportError(`读取导入选项失败：${error.message}`); }
}

async function openButlerImportModal() {
  const modal = butlerImportElement('butlerImportModal');
  if (!modal) return;
  if (!modal.open) {
    BUTLER_IMPORT_STATE.opener = document.activeElement;
    modal.showModal();
  }
  renderButlerImportControls();
  if (BUTLER_IMPORT_STATE.storageError) butlerImportError('无法读取浏览器中的导入记录；请先恢复浏览器存储后再导入。');
  else if (BUTLER_IMPORT_STATE.batch) await pollButlerImport();
  else if (BUTLER_IMPORT_STATE.request) butlerImportError('上次导入响应尚未确认，请重试原请求恢复结果。');
  await loadButlerImportOptions();
  const target = BUTLER_IMPORT_STATE.request ? butlerImportElement('btnCloseButlerImport') : butlerImportElement('butlerImportIdentity');
  target?.focus();
}

function closeButlerImportModal() {
  const modal = butlerImportElement('butlerImportModal');
  if (modal?.open) modal.close();
  BUTLER_IMPORT_STATE.opener?.focus();
}

async function previewButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  if (state.busy || state.request) return;
  let filters;
  try { filters = butlerImportFilters(); }
  catch (error) { butlerImportError(error.message); return; }
  invalidateButlerImportPreview();
  const version = state.previewVersion;
  state.busy = true;
  renderButlerImportControls();
  try {
    const data = await api('/api/email-butler/import-preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(filters),
    });
    if (version !== state.previewVersion || JSON.stringify(filters) !== JSON.stringify(butlerImportFilters())) return;
    if (data.ok === false || !data.preview_token) throw new Error(data.error || '预览未返回有效结果，请重新预览');
    state.preview = {...data, filters};
    butlerImportElement('butlerImportPreview').textContent = `当前可导入 ${Number(data.available || 0)} 个，本次选择 ${Number(data.selected || 0)} 个。预览不会领取邮箱。`;
    butlerImportElement('butlerImportItems').innerHTML = (data.items || []).slice(0, 10).map(item => {
      const address = typeof item === 'string' ? item : item.email || item.address || '';
      return `<li>${esc(address)}</li>`;
    }).join('');
    if (!Number(data.selected || 0)) butlerImportError('没有符合筛选条件的可导入邮箱，请调整筛选。');
  } catch (error) { butlerImportError(`预览失败：${error.message}`); }
  finally { state.busy = false; renderButlerImportControls(); }
}

function scheduleButlerImportPoll() {
  const state = BUTLER_IMPORT_STATE;
  clearTimeout(state.timer);
  state.timer = null;
  if (state.batch && ['pending', 'queued', 'running', 'processing'].includes(state.batch.status)) {
    state.timer = setTimeout(pollButlerImport, 2000);
  }
}

function renderButlerImportBatch() {
  const batch = BUTLER_IMPORT_STATE.batch;
  if (!batch) return;
  const labels = {pending: '等待导入', queued: '等待导入', running: '正在导入', processing: '正在导入',
    partial: batch.can_retry ? '部分完成，可继续原批次' : '本批次已结束（部分失败）', completed: '导入完成', succeeded: '导入完成', done: '导入完成',
    failed: '导入失败', rejected: '导入未开始', unknown: '结果待确认'};
  const progress = butlerImportElement('butlerImportProgress');
  if (progress) progress.textContent = `${labels[batch.status] || '等待确认'}：请求 ${Number(batch.requested || 0)}，已导入 ${Number(batch.imported || 0)}，跳过 ${Number(batch.skipped || 0)}，待处理 ${Number(batch.pending || 0)}，待确认 ${Number(batch.unknown || 0)}，失败 ${Number(batch.failed || 0)}。关闭此窗口后仍可恢复查看。`;
  const identity = butlerImportElement('butlerImportBatchId');
  if (identity) identity.textContent = `批次：${batch.batch_id}`;
  renderButlerImportControls();
}

async function refreshButlerImportInventory() {
  const state = BUTLER_IMPORT_STATE;
  const imported = Number(state.batch?.imported || 0);
  if (!imported || imported === state.refreshedImported) return;
  ['/api/email-sources', '/api/capabilities', '/api/summary', '/api/dashboard', '/api/outlook'].forEach(invalidateApiCache);
  setPoolSourceV2('email_butler');
  const results = await Promise.allSettled([
    loadCapabilities, loadRegistrationEmailSources, loadOutlook, loadMailResources, loadSummary,
  ].map(refresh => Promise.resolve().then(() => refresh())));
  if (results.every(result => result.status === 'fulfilled')) state.refreshedImported = imported;
  else butlerImportError('邮箱已导入，但本地库存显示未完全刷新，请稍后点击“刷新资源”。');
}

async function acceptButlerImportBatch(data) {
  const state = BUTLER_IMPORT_STATE;
  if (data.ok === false || !data.batch?.batch_id) throw new Error(data.error || '服务端未返回导入批次');
  if (state.batch && state.batch.batch_id !== data.batch.batch_id) throw new Error('服务端返回了不同批次，保留原批次等待确认');
  state.batch = data.batch;
  try { persistButlerImport(); }
  catch (_) { butlerImportError('原请求已保存，批次编号暂未写入浏览器；重开后将恢复原请求。'); }
  renderButlerImportBatch();
  scheduleButlerImportPoll();
  await refreshButlerImportInventory();
}

async function applyButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  if (state.busy || state.request || !state.preview || Number(state.preview.selected || 0) < 1) return;
  try {
    if (JSON.stringify(butlerImportFilters()) !== JSON.stringify(state.preview.filters)) {
      invalidateButlerImportPreview();
      butlerImportError('筛选已变化，请重新预览。');
      return;
    }
    if (state.storageError) throw new Error('浏览器存储不可用，无法保存导入请求');
    state.request = {request_id: crypto.randomUUID(), preview_token: state.preview.preview_token, filters: state.preview.filters};
    persistButlerImport();
  } catch (_) {
    state.request = null;
    butlerImportError('无法保存导入请求，请启用浏览器本地存储后重试。');
    renderButlerImportControls();
    return;
  }
  await retryButlerImport();
}

async function retryButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  if (state.busy || state.polling || !state.request || (state.batch && !state.batch.can_retry)) return;
  state.busy = true;
  butlerImportError();
  renderButlerImportControls();
  try {
    const url = state.batch ? `/api/email-butler/imports/${encodeURIComponent(state.batch.batch_id)}/retry` : '/api/email-butler/imports';
    const body = {request_id: state.request.request_id, preview_token: state.request.preview_token};
    const data = await api(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    await acceptButlerImportBatch(data);
  } catch (error) {
    const noBatchCodes = ['import_preview_not_found', 'import_preview_expired', 'import_preview_empty', 'import_snapshot_conflict'];
    if (!state.batch && noBatchCodes.includes(error.code)) {
      try {
        localStorage.removeItem(BUTLER_IMPORT_STORAGE_KEY);
        state.request = null;
        invalidateButlerImportPreview();
        butlerImportError(`导入尚未开始：${error.message}。请重新预览。`);
      } catch (_) { butlerImportError('导入尚未开始，但原记录暂未清除；请恢复浏览器存储后重试原请求。'); }
    } else {
      butlerImportError(`导入结果尚未确认：${error.message}。请${state.batch ? '继续原批次' : '重试原请求'}恢复，已保留原编号。`);
    }
  } finally { state.busy = false; renderButlerImportControls(); }
}

async function pollButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  if (!state.batch || state.polling || state.busy) return;
  clearTimeout(state.timer);
  state.timer = null;
  state.polling = true;
  renderButlerImportControls();
  try {
    const data = await api(`/api/email-butler/imports/${encodeURIComponent(state.batch.batch_id)}`);
    butlerImportError();
    await acceptButlerImportBatch(data);
  } catch (error) {
    butlerImportError(`暂时无法读取原批次：${error.message}。请重开此窗口恢复查看。`);
    scheduleButlerImportPoll();
  } finally { state.polling = false; renderButlerImportControls(); }
}

function resetButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  if (!butlerImportCanReset() || state.busy || state.polling) return;
  try { localStorage.removeItem(BUTLER_IMPORT_STORAGE_KEY); }
  catch (_) { butlerImportError('无法清除上次导入记录，请恢复浏览器存储后重试。'); return; }
  clearTimeout(state.timer);
  state.request = state.batch = null;
  state.refreshedImported = -1;
  butlerImportElement('butlerImportProgress').textContent = '';
  butlerImportElement('butlerImportBatchId').textContent = '';
  invalidateButlerImportPreview();
  butlerImportElement('butlerImportIdentity')?.focus();
}

function bindButlerImport() {
  restoreButlerImport();
  const on = (id, event, handler) => butlerImportElement(id)?.addEventListener(event, handler);
  on('btnOpenButlerImport', 'click', openButlerImportModal);
  on('btnOpenButlerImportPool', 'click', openButlerImportModal);
  on('btnCloseButlerImport', 'click', closeButlerImportModal);
  on('btnCancelButlerImport', 'click', closeButlerImportModal);
  on('btnPreviewButlerImport', 'click', previewButlerImport);
  on('btnApplyButlerImport', 'click', applyButlerImport);
  on('btnRetryButlerImport', 'click', retryButlerImport);
  on('btnNewButlerImport', 'click', resetButlerImport);
  on('butlerImportModal', 'cancel', event => { event.preventDefault(); closeButlerImportModal(); });
  for (const id of ['butlerImportProvider', 'butlerImportIdentity', 'butlerImportCount', 'butlerImportDomain', 'butlerImportGroup']) {
    on(id, 'input', invalidateButlerImportPreview);
    on(id, 'change', invalidateButlerImportPreview);
  }
  renderButlerImportControls();
}
bindButlerImport();
