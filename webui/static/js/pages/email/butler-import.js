// 手动供应与注册领取分开：浏览器只恢复原请求或原批次。
const BUTLER_IMPORT_STORAGE_KEY = 'turb.butler-import.v1';
const BUTLER_IMPORT_STATE = {
  preview: null, previewVersion: 0, request: null, batch: null,
  busy: false, polling: false, timer: null, opener: null,
  maxCount: 200, refreshedImported: -1, storageError: false,
  previewTimer: null, refreshPromise: null, lastRefreshAt: 0,
  resumePending: null,
};
const butlerImportElement = id => document.getElementById(id);
const butlerImportRunning = () => ['pending', 'queued', 'running', 'processing'].includes(BUTLER_IMPORT_STATE.batch?.status);
const butlerImportSucceeded = status => ['completed', 'succeeded', 'done'].includes(status);
const butlerImportRevision = batch => JSON.stringify([batch.updated_at, batch.status, batch.imported, batch.pending, batch.submitting, batch.unknown, batch.failed, batch.error_code]);

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
      BUTLER_IMPORT_STATE.batch = {batch_id: saved.batch_id,
        status: butlerImportSucceeded(saved.batch_status) ? saved.batch_status : 'running'};
      if (typeof saved.resume_revision === 'string') BUTLER_IMPORT_STATE.resumePending = saved.resume_revision;
    }
  } catch (_) { BUTLER_IMPORT_STATE.storageError = true; }
}

function persistButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  const request = state.request;
  localStorage.setItem(BUTLER_IMPORT_STORAGE_KEY, JSON.stringify({
    request_id: request.request_id, preview_token: request.preview_token,
    filters: request.filters, ...(state.batch ? {batch_id: state.batch.batch_id, batch_status: state.batch.status} : {}),
    ...(state.resumePending ? {resume_revision: state.resumePending} : {}),
  }));
}

function butlerImportCanReset() {
  const batch = BUTLER_IMPORT_STATE.batch;
  return !!batch && !batch.can_retry && !Number(batch.unknown || 0)
    && ['completed', 'succeeded', 'done', 'partial', 'failed', 'rejected'].includes(batch.status);
}

function renderButlerImportControls() {
  const state = BUTLER_IMPORT_STATE;
  const locked = !!state.request || state.storageError;
  for (const id of ['butlerImportProvider', 'butlerImportIdentity', 'butlerImportCount', 'butlerImportDomain', 'butlerImportGroup']) {
    const input = butlerImportElement(id);
    if (input) input.disabled = locked;
  }
  const preview = butlerImportElement('btnPreviewButlerImport');
  if (preview) {
    preview.disabled = locked || state.busy;
    preview.hidden = !!state.request;
    preview.textContent = state.busy && !state.request ? '正在查询…' : '刷新可用数量';
  }
  const apply = butlerImportElement('btnApplyButlerImport');
  if (apply) {
    apply.disabled = locked || state.busy || !state.preview || Number(state.preview.selected || 0) < 1;
    apply.textContent = state.preview?.selected ? `开始导入 ${Number(state.preview.selected)} 个` : '开始导入';
    apply.hidden = !!state.request;
  }
  const retry = butlerImportElement('btnRetryButlerImport');
  if (retry) {
    retry.hidden = !state.request || butlerImportRunning() || !!state.resumePending || (!!state.batch && !state.batch.can_retry);
    retry.disabled = state.busy || state.polling;
    retry.textContent = state.batch ? '继续原批次' : '重试原请求';
  }
  const reset = butlerImportElement('btnNewButlerImport');
  if (reset) { reset.hidden = !butlerImportCanReset(); reset.disabled = state.busy || state.polling; }
  const modal = butlerImportElement('butlerImportModal');
  if (modal) modal.setAttribute('aria-busy', state.busy || state.polling ? 'true' : 'false');
  const setup = butlerImportElement('butlerImportSetup');
  if (setup) setup.hidden = !!state.request;
  const previewResult = butlerImportElement('butlerImportPreview');
  if (previewResult) previewResult.hidden = !!state.request;
  const status = butlerImportElement('butlerImportStatus');
  if (status) status.hidden = !state.request;
  const close = butlerImportElement('btnCancelButlerImport');
  if (close) close.textContent = butlerImportRunning() || state.resumePending ? '关闭，后台继续' : '关闭';
  if (state.request && !state.batch) {
    const title = butlerImportElement('butlerImportStatusTitle');
    if (title) title.textContent = state.busy ? '正在提交导入' : '导入请求待确认';
    const hint = butlerImportElement('butlerImportStatusHint');
    if (hint) hint.textContent = '可以关闭窗口，已保存原请求；重新打开后可恢复结果。';
  }
  const description = butlerImportElement('butlerImportDescription');
  if (description) description.textContent = state.request ? '导入进度会自动保存，可随时关闭窗口。' : '从 Butler 已有库存补充邮箱，自动查询当前可用数量。';
  const pageStatus = butlerImportElement('butlerImportPageStatus');
  if (pageStatus) {
    pageStatus.hidden = !state.request || !!modal?.open || butlerImportSucceeded(state.batch?.status);
    pageStatus.textContent = state.batch
      ? `Butler 导入${butlerImportRunning() ? '中' : '结果'} · 已导入 ${Number(state.batch.imported || 0)} / ${Number(state.batch.total || 0)} · 查看进度`
      : 'Butler 导入请求待确认 · 查看进度';
  }
  for (const id of ['btnOpenButlerImport', 'btnOpenButlerImportPool']) {
    const opener = butlerImportElement(id);
    if (opener) opener.textContent = state.request ? (butlerImportRunning() ? `Butler 导入中 · ${Number(state.batch.imported || 0)}/${Number(state.batch.total || 0)}` : '查看 Butler 导入') : '从 Butler 导入';
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
  if (preview) preview.textContent = '';
  butlerImportError();
  renderButlerImportControls();
}

function queueButlerImportPreview() {
  invalidateButlerImportPreview();
  clearTimeout(BUTLER_IMPORT_STATE.previewTimer);
  if (!BUTLER_IMPORT_STATE.request) BUTLER_IMPORT_STATE.previewTimer = setTimeout(previewButlerImport, 400);
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
  else {
    await loadButlerImportOptions();
    if (!BUTLER_IMPORT_STATE.storageError) await previewButlerImport();
  }
  const target = BUTLER_IMPORT_STATE.request ? butlerImportElement('btnCloseButlerImport') : butlerImportElement('butlerImportIdentity');
  if (modal.open) target?.focus();
}

function closeButlerImportModal() {
  const modal = butlerImportElement('butlerImportModal');
  if (modal?.open) modal.close();
  renderButlerImportControls();
  BUTLER_IMPORT_STATE.opener?.focus();
}

async function previewButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  if (state.busy || state.request) return;
  clearTimeout(state.previewTimer);
  let filters;
  try { filters = butlerImportFilters(); }
  catch (error) { butlerImportError(error.message); return; }
  invalidateButlerImportPreview();
  const version = state.previewVersion;
  state.busy = true;
  butlerImportElement('butlerImportPreview').textContent = '正在查询当前可用数量…';
  renderButlerImportControls();
  try {
    const data = await api('/api/email-butler/import-preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(filters),
    });
    if (version !== state.previewVersion || JSON.stringify(filters) !== JSON.stringify(butlerImportFilters())) return;
    if (data.ok === false || !data.preview_token) throw new Error(data.error || '可用数量查询未返回有效结果，请刷新数量');
    state.preview = {...data, filters};
    butlerImportElement('butlerImportPreview').textContent = `当前可用 ${Number(data.available || 0)} 个 · 本次可导入 ${Number(data.selected || 0)} 个。已排除本地已有或占用的邮箱，查询不占用库存。`;
    if (!Number(data.selected || 0)) butlerImportError('当前筛选下没有可导入邮箱，请调整条件或在 Butler 补充库存后刷新数量。');
  } catch (error) { if (version === state.previewVersion) butlerImportError(`查询可用数量失败：${error.message}`); }
  finally {
    state.busy = false;
    renderButlerImportControls();
    if (version !== state.previewVersion && !state.request && butlerImportElement('butlerImportModal')?.open) {
      clearTimeout(state.previewTimer);
      state.previewTimer = setTimeout(previewButlerImport, 400);
    }
  }
}

function scheduleButlerImportPoll() {
  const state = BUTLER_IMPORT_STATE;
  clearTimeout(state.timer);
  state.timer = null;
  if (state.batch && (butlerImportRunning() || state.resumePending)) {
    state.timer = setTimeout(pollButlerImport, 2000);
  }
}

function renderButlerImportBatch() {
  const batch = BUTLER_IMPORT_STATE.batch;
  if (!batch) return;
  const labels = {pending: '等待导入', queued: '等待导入', running: '正在导入', processing: '正在导入',
    partial: batch.can_retry ? '部分完成，可继续原批次' : '本批次已结束（部分失败）', completed: '导入完成', succeeded: '导入完成', done: '导入完成',
    failed: '导入失败', rejected: '导入未开始', unknown: '结果待确认'};
  const total = Number(batch.total || 0);
  const imported = Number(batch.imported || 0), skipped = Number(batch.skipped || 0), failed = Number(batch.failed || 0), unknown = Number(batch.unknown || 0);
  const processed = imported + skipped + failed + unknown;
  const title = butlerImportElement('butlerImportStatusTitle');
  if (title) title.textContent = BUTLER_IMPORT_STATE.resumePending ? '正在恢复原批次' : labels[batch.status] || '等待确认';
  const hint = butlerImportElement('butlerImportStatusHint');
  if (hint) hint.textContent = butlerImportRunning() || BUTLER_IMPORT_STATE.resumePending
    ? '可以关闭窗口，导入会在后台继续。右下角可随时查看进度，刷新页面也能恢复。'
    : batch.can_retry ? '可继续原批次处理剩余邮箱，已导入的邮箱会保留。'
      : '已导入的邮箱已加入本地库存，可以关闭窗口或新建导入。';
  const bar = butlerImportElement('butlerImportProgressBar');
  if (bar) { bar.max = Math.max(total, 1); bar.value = Math.min(processed, total); }
  const stats = butlerImportElement('butlerImportStats');
  if (stats) stats.innerHTML = [['已导入', imported], ['待处理', Number(batch.pending || 0)], ['交接中', Number(batch.submitting || 0)], ['已跳过', skipped], ['待确认', unknown], ['失败', failed]]
    .map(([label, count]) => `<div class="butler-import-stat"><strong>${count}</strong>${label}</div>`).join('');
  const progress = butlerImportElement('butlerImportProgress');
  if (progress) progress.textContent = `已处理 ${processed} / ${total} 个，本次请求 ${Number(batch.requested || 0)} 个。`;
  const reasons = butlerImportElement('butlerImportReasons');
  const errorLabels = {local_email_conflict: '本地已有或被其他任务占用', handoff_rejected: 'Butler 拒绝交接', handoff_unconfirmed: '远端交接结果待确认，可继续原批次核实', import_interrupted: '服务重启导致中断，可继续原批次', original_route_unavailable: '原 Butler 连接或收件配置不可用', fixed_route_unavailable: '原固定收件配置不可用', butler_remote_unavailable: '无法连接 Butler，稍后可继续原批次', handoff_contract_unsupported: 'Butler 消费身份或交接能力不匹配', import_storage_unavailable: '本地数据库暂时不可用，可继续原批次', import_internal_error: '本地导入处理异常，可继续原批次'};
  Object.assign(errorLabels, {
    handoff_timeout: 'Butler 交接响应超时，可继续原批次核实',
    handoff_rate_limited: 'Butler 请求受限，稍后可继续原批次',
    handoff_remote_unavailable: 'Butler 服务暂时不可用，可继续原批次',
    handoff_identity_mismatch: 'Butler 回执与原邮箱身份不一致，可继续原批次核实',
    handoff_response_invalid: 'Butler 回执缺失、重复或格式无效，可继续原批次核实',
    inventory_batch_invalid: 'Butler 批量请求格式无效',
    inventory_import_item_invalid: 'Butler 原邮箱交接参数无效',
    inventory_policy_forbidden: 'Butler 消费策略不允许交接此邮箱',
    inventory_client_required: 'Butler 未确认消费客户端身份',
    icloud_identity_not_found: 'Butler 未找到原完整邮箱身份',
    inventory_candidate_unavailable: 'Butler 原邮箱库存当前不可交接',
    acquisition_owner_mismatch: 'Butler 原交接归属不一致',
    acquisition_identity_mismatch: 'Butler 原交接对应的邮箱身份不一致',
    icloud_identity_unavailable: 'Butler 原邮箱身份当前不可用',
    inventory_storage_unavailable: 'Butler 数据库暂时不可用，可继续原批次',
  });
  if (reasons) {
    const errors = Object.entries(batch.error_counts || {}).map(([code, count]) => `${errorLabels[code] || `处理异常（${code}）`}：${Number(count)} 个`);
    if (batch.error_code) errors.unshift(errorLabels[batch.error_code] || `批次异常（${batch.error_code}）`);
    reasons.textContent = errors.join('；');
  }
  const identity = butlerImportElement('butlerImportBatchId');
  if (identity) identity.textContent = `批次：${batch.batch_id}`;
  renderButlerImportControls();
}

async function refreshButlerImportInventory() {
  const state = BUTLER_IMPORT_STATE;
  const imported = Number(state.batch?.imported || 0);
  if (!imported || imported === state.refreshedImported || state.refreshPromise) return;
  if (butlerImportRunning() && state.refreshedImported >= 0 && Date.now() - state.lastRefreshAt < 15000) return;
  ['/api/email-sources', '/api/capabilities', '/api/summary', '/api/dashboard', '/api/outlook'].forEach(invalidateApiCache);
  setPoolSourceV2('email_butler');
  state.refreshPromise = Promise.allSettled([
    loadCapabilities, loadRegistrationEmailSources, loadOutlook, loadMailResources, loadSummary,
  ].map(refresh => Promise.resolve().then(() => refresh())));
  const results = await state.refreshPromise;
  state.refreshPromise = null;
  state.lastRefreshAt = Date.now();
  if (results.every(result => result.status === 'fulfilled')) state.refreshedImported = imported;
  else butlerImportError('邮箱已导入，但本地库存显示未完全刷新，请稍后点击“刷新资源”。');
  if (!butlerImportRunning() && Number(state.batch?.imported || 0) !== imported) void refreshButlerImportInventory();
}

async function acceptButlerImportBatch(data) {
  const state = BUTLER_IMPORT_STATE;
  if (data.ok === false || !data.batch?.batch_id) throw new Error(data.error || '服务端未返回导入批次');
  if (state.batch && state.batch.batch_id !== data.batch.batch_id) throw new Error('服务端返回了不同批次，保留原批次等待确认');
  if (state.resumePending && (['pending', 'queued', 'running', 'processing'].includes(data.batch.status) || butlerImportRevision(data.batch) !== state.resumePending)) state.resumePending = null;
  state.batch = data.batch;
  try { persistButlerImport(); }
  catch (_) { butlerImportError('原请求已保存，批次编号暂未写入浏览器；重开后将恢复原请求。'); }
  renderButlerImportBatch();
  void refreshButlerImportInventory();
}

async function applyButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  if (state.busy || state.request || !state.preview || Number(state.preview.selected || 0) < 1) return;
  try {
    if (JSON.stringify(butlerImportFilters()) !== JSON.stringify(state.preview.filters)) {
      invalidateButlerImportPreview();
      butlerImportError('筛选已变化，请刷新可用数量。');
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
    if (state.batch) state.resumePending = butlerImportRevision(state.batch);
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
  } finally { state.busy = false; renderButlerImportControls(); scheduleButlerImportPoll(); }
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
  } finally { state.polling = false; renderButlerImportControls(); scheduleButlerImportPoll(); }
}

function resetButlerImport() {
  const state = BUTLER_IMPORT_STATE;
  if (!butlerImportCanReset() || state.busy || state.polling) return;
  try { localStorage.removeItem(BUTLER_IMPORT_STORAGE_KEY); }
  catch (_) { butlerImportError('无法清除上次导入记录，请恢复浏览器存储后重试。'); return; }
  clearTimeout(state.timer);
  state.request = state.batch = null;
  state.resumePending = null;
  state.refreshedImported = -1;
  state.lastRefreshAt = 0;
  butlerImportElement('butlerImportProgress').textContent = '';
  butlerImportElement('butlerImportBatchId').textContent = '';
  invalidateButlerImportPreview();
  void previewButlerImport();
  butlerImportElement('butlerImportIdentity')?.focus();
}

function bindButlerImport() {
  restoreButlerImport();
  const on = (id, event, handler) => butlerImportElement(id)?.addEventListener(event, handler);
  on('btnOpenButlerImport', 'click', openButlerImportModal);
  on('btnOpenButlerImportPool', 'click', openButlerImportModal);
  on('butlerImportPageStatus', 'click', openButlerImportModal);
  on('btnCloseButlerImport', 'click', closeButlerImportModal);
  on('btnCancelButlerImport', 'click', closeButlerImportModal);
  on('btnPreviewButlerImport', 'click', previewButlerImport);
  on('btnApplyButlerImport', 'click', applyButlerImport);
  on('btnRetryButlerImport', 'click', retryButlerImport);
  on('btnNewButlerImport', 'click', resetButlerImport);
  on('butlerImportModal', 'cancel', event => { event.preventDefault(); closeButlerImportModal(); });
  for (const id of ['butlerImportProvider', 'butlerImportIdentity', 'butlerImportCount', 'butlerImportDomain', 'butlerImportGroup']) {
    on(id, 'input', queueButlerImportPreview);
    on(id, 'change', queueButlerImportPreview);
  }
  renderButlerImportControls();
  if (BUTLER_IMPORT_STATE.batch) void pollButlerImport();
}
bindButlerImport();
