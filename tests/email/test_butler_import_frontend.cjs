const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = path.join(__dirname, '../../webui/static/js/pages/email/butler-import.js');

function createView({saved, handler, storageFails = false, refreshFails = false, refreshGate} = {}) {
  const nodes = new Map(), requests = [], timers = new Map(), refreshes = [], windowListeners = {};
  let timerId = 0;
  let now = Date.now();
  const storage = new Map(saved ? [['turb.butler-import.v1', JSON.stringify(saved)]] : []);
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {
      id, value: '', textContent: '', innerHTML: '', disabled: false, hidden: false,
      open: false, dataset: {}, listeners: {}, attributes: {},
      addEventListener(type, fn) { this.listeners[type] = fn; },
      setAttribute(key, value) { this.attributes[key] = value; },
      showModal() { this.open = true; }, close() { this.open = false; },
      focus() { document.activeElement = this; },
      querySelectorAll() { return []; },
    });
    return nodes.get(id);
  };
  const document = {getElementById: node, activeElement: null};
  node('butlerImportProvider').value = 'icloud_hme';
  node('butlerImportIdentity').value = 'all';
  node('butlerImportCount').value = '5';
  const context = {
    document, crypto: {randomUUID: () => '11111111-1111-4111-8111-111111111111'},
    addEventListener: (type, listener) => { windowListeners[type] = listener; },
    Date: class extends Date { static now() { return now; } },
    localStorage: {
      getItem: key => storage.get(key) || null,
      setItem(key, value) { if (storageFails) throw new Error('storage unavailable'); storage.set(key, value); },
      removeItem: key => storage.delete(key),
    },
    setTimeout(fn, delay) { const id = ++timerId; timers.set(id, {fn, delay}); return id; },
    clearTimeout: id => timers.delete(id),
    esc: value => String(value).replaceAll('<', '&lt;'),
    invalidateApiCache: url => refreshes.push(url),
    setPoolSourceV2: source => refreshes.push(source),
    loadCapabilities: () => { if (refreshFails) throw new Error('refresh failed'); refreshes.push('capabilities'); },
    loadRegistrationEmailSources: async () => refreshes.push('sources'),
    loadOutlook: async () => refreshes.push('pool'),
    loadMailResources: async () => { refreshes.push('resources'); if (refreshGate) await refreshGate; },
    loadSummary: async () => refreshes.push('summary'),
    api: async (url, options = {}) => {
      const call = {url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : undefined};
      requests.push(call);
      if (handler) return handler(call, {storage, node});
      if (url.endsWith('import-options')) return {ok: true, providers: [{value: 'icloud_hme', label: 'iCloud HME'}], max_count: null};
      if (url.endsWith('import-preview')) return {ok: true, preview_token: 'preview-1', available: 12, selected: 5, count: 5, items: []};
      return {ok: true, batch: {batch_id: 'batch-1', status: 'running', requested: 5, total: 5, imported: 1, skipped: 0, pending: 4}};
    },
  };
  vm.createContext(context);
  assert.ok(fs.existsSync(script), '手动 Butler 导入脚本尚未实现');
  vm.runInContext(fs.readFileSync(script, 'utf8') + '\nglobalThis.view = {state: BUTLER_IMPORT_STATE, open: openButlerImportModal, close: closeButlerImportModal, preview: previewButlerImport, apply: applyButlerImport, poll: pollButlerImport, retry: retryButlerImport, terminate: terminateButlerImport, invalidate: invalidateButlerImportPreview, reset: resetButlerImport};', context);
  const settle = () => new Promise(resolve => setImmediate(resolve));
  const runTimers = async maximumDelay => {
    const scheduled = [...timers].filter(([, timer]) => timer.delay <= maximumDelay);
    for (const [id, timer] of scheduled) { timers.delete(id); await timer.fn(); }
    await settle();
  };
  return {view: context.view, node, requests, storage, timers, refreshes, document, settle, runTimers, windowListeners,
    advanceTime: milliseconds => { now += milliseconds; }};
}

const content = element => `${element.textContent} ${element.innerHTML}`;

test('打开弹窗自动查询可用数量，查询不领取邮箱也不展示地址列表', async () => {
  const h = createView({handler(call) {
    if (call.url.endsWith('import-options')) return {ok: true, max_count: null};
    assert.ok(call.url.endsWith('import-preview'));
    return {ok: true, preview_token: 'p', available: 12, selected: 5,
      items: [{email: 'private-address@icloud.com'}]};
  }});
  await h.view.open();
  assert.deepEqual(h.requests.map(call => call.url), ['/api/email-butler/import-options', '/api/email-butler/import-preview']);
  assert.match(content(h.node('butlerImportPreview')), /12.*5/);
  assert.doesNotMatch(`${content(h.node('butlerImportPreview'))} ${content(h.node('butlerImportItems'))}`, /private-address/);
  assert.equal(h.node('btnApplyButlerImport').disabled, false);
  assert.ok(h.requests.every(call => call.url !== '/api/email-butler/imports'));
});

test('历史导入限制解释零可用，未租用不被描述为OpenAI可租', async () => {
  const h = createView({handler(call) {
    assert.ok(call.url.endsWith('import-preview'));
    return {ok: true, preview_token: 'p', available: 0, selected: 0, resource_total: 57,
      availability_buckets: {history_blocked: 57, available: 0}};
  }});
  await h.view.preview();
  const preview = content(h.node('butlerImportPreview'));
  assert.match(preview, /当前可用 0 个.*本次可导入 0 个/);
  assert.match(preview, /当前查询范围 57 个.*历史占用限制 57 个/);
  assert.match(preview, /未租用.*不等于可用于 OpenAI/);
  assert.doesNotMatch(preview, /已注册/);
  assert.match(h.node('butlerImportError').textContent, /目标服务.*历史占用/);
  assert.doesNotMatch(h.node('butlerImportError').textContent, /补充库存/);
  assert.equal(h.node('btnApplyButlerImport').disabled, true);
  assert.equal(h.requests.length, 1);
});

test('旧预览响应没有诊断计数时仍可导入且不显示虚构原因', async () => {
  const h = createView();
  await h.view.preview();
  const preview = content(h.node('butlerImportPreview'));
  assert.match(preview, /当前可用 12 个.*本次可导入 5 个/);
  assert.doesNotMatch(preview, /undefined|NaN|历史占用限制|来源不可用/);
  assert.equal(h.node('btnApplyButlerImport').disabled, false);
});

test('原因概览只展示已知原因的有效正整数，不泄露其他字段', async () => {
  const h = createView({handler() {
    return {ok: true, preview_token: 'p', available: 2, selected: 2,
      resource_total: 'private-total', availability_buckets: {
        source_unavailable: 3, active_same_service: 4, other_service_exclusive: 5,
        history_blocked: 'private-history', cooldown: true, 'private-field': 99,
      }};
  }});
  await h.view.preview();
  const preview = content(h.node('butlerImportPreview'));
  assert.match(preview, /来源不可用 3 个.*OpenAI 已租用 4 个.*其他服务占用 5 个/);
  assert.doesNotMatch(preview, /private-|历史占用限制|冷却中/);
  assert.equal(h.node('btnApplyButlerImport').disabled, false);
});

test('连续修改筛选立即使旧数量失效，防抖后仅查询最后一次条件', async () => {
  const h = createView();
  await h.view.open();
  h.node('butlerImportCount').value = '6';
  h.node('butlerImportCount').listeners.input();
  assert.equal(h.node('btnApplyButlerImport').disabled, true);
  h.node('butlerImportCount').value = '7';
  h.node('butlerImportCount').listeners.input();
  await h.runTimers(1000);
  const checks = h.requests.filter(call => call.url.endsWith('import-preview'));
  assert.equal(checks.length, 2);
  assert.equal(checks.at(-1).body.count, 7);
});

test('预览仅调用只读接口，筛选变化使旧预览不能提交', async () => {
  const h = createView();
  await h.view.preview();
  assert.deepEqual(h.requests.map(item => item.url), ['/api/email-butler/import-preview']);
  assert.deepEqual(h.requests[0].body, {provider: 'icloud_hme', count: 5});
  assert.match(h.node('butlerImportPreview').textContent, /12.*5/);
  h.node('butlerImportCount').value = '6';
  h.view.invalidate();
  await h.view.apply();
  assert.equal(h.requests.length, 1);
  assert.equal(h.node('btnApplyButlerImport').disabled, true);
});

test('数量范围和类型在前端校验，未发送无效预览', async () => {
  for (const value of ['0', '-1', '1.5', '', '9007199254740992', 'Infinity', 'invalid']) {
    const h = createView(); h.node('butlerImportCount').value = value;
    await h.view.preview();
    assert.equal(h.requests.length, 0);
    assert.equal(h.node('butlerImportError').textContent, '数量须为大于0的整数');
  }
  const h = createView(); h.node('butlerImportProvider').value = 'outlook';
  await h.view.preview();
  assert.equal(h.requests.length, 0);
});

test('导入数量不限，201与10000均可预览并提交原请求', async () => {
  for (const count of [201, 10000]) {
    const h = createView({handler(call) {
      if (call.url.endsWith('import-options')) return {ok: true, max_count: null};
      if (call.url.endsWith('import-preview')) {
        assert.equal(call.body.count, count);
        return {ok: true, preview_token: `preview-${count}`, available: count, selected: count};
      }
      assert.equal(call.url, '/api/email-butler/imports');
      assert.equal(call.body.preview_token, `preview-${count}`);
      return {ok: true, batch: {batch_id: `batch-${count}`, status: 'running',
        requested: count, total: count, imported: 0, pending: count}};
    }});
    h.node('butlerImportCount').value = String(count);
    await h.view.open();
    assert.equal(h.node('butlerImportCount').max, undefined);
    assert.equal(h.node('btnApplyButlerImport').disabled, false);
    assert.match(h.node('btnApplyButlerImport').textContent, new RegExp(String(count)));
    await h.view.apply();
    assert.equal(h.view.state.batch.total, count);
    assert.equal(JSON.parse(h.storage.get('turb.butler-import.v1')).filters.count, count);
    assert.deepEqual(h.requests.map(call => call.url), ['/api/email-butler/import-options',
      '/api/email-butler/import-preview', '/api/email-butler/imports']);
  }
});

test('提交前持久化请求，响应未知后重开仍重试同一请求并禁止重复点击', async () => {
  let rejectSubmit;
  const h = createView({handler(call, {storage}) {
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'preview-1', available: 5, selected: 5, items: []};
    if (call.url.endsWith('import-options')) return {ok: true};
    const saved = JSON.parse(storage.get('turb.butler-import.v1'));
    assert.equal(saved.request_id, call.body.request_id);
    return new Promise((resolve, reject) => { rejectSubmit = reject; });
  }});
  await h.view.preview();
  const submission = h.view.apply();
  await h.view.apply();
  assert.equal(h.requests.length, 2);
  rejectSubmit(new Error('network error'));
  await submission;
  const original = h.requests.at(-1).body;
  assert.match(h.node('butlerImportError').textContent, /原请求/);
  const recovered = createView({saved: JSON.parse(h.storage.get('turb.butler-import.v1'))});
  await recovered.view.open();
  await recovered.view.retry();
  assert.deepEqual(recovered.requests.at(-1).body, original);
});

test('无法持久化请求时阻止领取，不丢失恢复身份', async () => {
  const h = createView({storageFails: true});
  await h.view.preview(); await h.view.apply();
  assert.equal(h.requests.length, 1);
  assert.match(h.node('butlerImportError').textContent, /保存|存储/);
});

test('关闭运行中弹窗不取消批次，重开查询原批次，部分完成恢复原批次', async () => {
  const h = createView();
  await h.view.preview(); await h.view.apply();
  h.view.close();
  assert.equal(h.view.state.batch.batch_id, 'batch-1');
  assert.equal(h.node('butlerImportModal').open, false);
  await h.view.open();
  assert.ok(h.requests.some(call => call.url === '/api/email-butler/imports/batch-1'));
  assert.equal(h.node('butlerImportModal').open, true);
  const partial = createView({saved: {batch_id: 'batch-2', request_id: 'same-id', preview_token: 'preview-2'}, handler(call) {
    return {ok: true, batch: {batch_id: 'batch-2', status: 'partial', requested: 5, total: 5, imported: 2, unknown: 3, can_retry: true}};
  }});
  await partial.settle();
  await partial.view.poll();
  assert.equal(partial.node('btnRetryButlerImport').hidden, false);
  await partial.view.retry();
  assert.equal(partial.requests.at(-1).url, '/api/email-butler/imports/batch-2/retry');
  assert.equal(partial.requests.at(-1).method, 'POST');
});

test('运行中的批次明确允许关闭，隐藏继续按钮并在页面保留查看进度入口', async () => {
  const h = createView({handler(call) {
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p', available: 5, selected: 5};
    return {ok: true, batch: {batch_id: 'active', status: 'running', requested: 5, total: 5,
      imported: 1, pending: 3, submitting: 1, can_retry: true}};
  }});
  await h.view.preview();
  await h.view.apply();
  assert.equal(h.node('btnRetryButlerImport').hidden, true);
  assert.match(h.node('btnCancelButlerImport').textContent, /关闭.*后台继续/);
  assert.match(content(h.node('butlerImportStatusHint')), /关闭|后台/);
  assert.equal(h.node('butlerImportProgressBar').max, 5);
  assert.equal(h.node('butlerImportProgressBar').value, 1);
  h.view.close();
  assert.equal(h.node('butlerImportPageStatus').hidden, false);
  assert.match(content(h.node('butlerImportPageStatus')), /1.*5|正在导入/);
  assert.ok([...h.timers.values()].some(timer => timer.delay >= 1000), '关闭弹窗后仍会读取后台进度');
  await h.node('butlerImportPageStatus').listeners.click();
  assert.equal(h.node('butlerImportModal').open, true);
  assert.ok(h.requests.every(call => !call.url.endsWith('/retry')));
});

test('刷新页面后自动读取原批次状态，读取不会新建或重跑导入', async () => {
  const h = createView({saved: {batch_id: 'saved-batch', request_id: 'r', preview_token: 'p'}, handler(call) {
    assert.equal(call.url, '/api/email-butler/imports/saved-batch');
    return {ok: true, batch: {batch_id: 'saved-batch', status: 'running', total: 5, requested: 5,
      imported: 3, pending: 2, can_retry: true}};
  }});
  await h.settle();
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].method, 'GET');
  assert.equal(h.node('butlerImportPageStatus').hidden, false);
  assert.match(content(h.node('butlerImportPageStatus')), /3.*5|正在导入/);
});

test('续跑返回原部分结果时持续查询同批次，直到后台开始并完成', async () => {
  let reads = 0;
  const original = {batch_id: 'resume-batch', status: 'partial', requested: 2, total: 2,
    imported: 1, pending: 1, can_retry: true, updated_at: '2026-10-28T00:00:00Z'};
  const h = createView({saved: {batch_id: original.batch_id, request_id: 'same-request', preview_token: 'same-preview'}, handler(call) {
    if (call.method === 'POST') {
      assert.equal(call.url, '/api/email-butler/imports/resume-batch/retry');
      assert.deepEqual(call.body, {request_id: 'same-request', preview_token: 'same-preview'});
      return {ok: true, batch: original};
    }
    assert.equal(call.url, '/api/email-butler/imports/resume-batch');
    reads += 1;
    if (reads <= 2) return {ok: true, batch: original};
    if (reads === 3) return {ok: true, batch: {...original, status: 'running', updated_at: '2026-10-28T00:00:01Z'}};
    return {ok: true, batch: {...original, status: 'completed', imported: 2, pending: 0,
      can_retry: false, updated_at: '2026-10-28T00:00:02Z'}};
  }});
  await h.settle();
  await h.view.retry();
  assert.equal(JSON.parse(h.storage.get('turb.butler-import.v1')).resume_revision,
    JSON.stringify([original.updated_at, original.status, original.imported, original.pending,
      original.submitting, original.unknown, original.failed, original.error_code, original.blocked_by]));
  assert.ok(h.timers.size > 0, '续跑请求成功后继续读取后台状态');
  await h.runTimers(2500);
  assert.equal(h.view.state.batch.status, 'partial');
  assert.ok(h.timers.size > 0, '后台尚未更新时不提前停止轮询');
  await h.runTimers(2500);
  assert.equal(h.view.state.batch.status, 'running');
  await h.runTimers(2500);
  assert.equal(h.view.state.batch.status, 'completed');
  assert.equal(h.view.state.batch.imported, 2);
  assert.equal(h.timers.size, 0);
  assert.equal(h.requests.filter(call => call.method === 'POST').length, 1);
  assert.ok(!JSON.parse(h.storage.get('turb.butler-import.v1')).resume_revision);
});

test('续跑预检期间刷新页面仍会持续恢复进度，完成后清除续跑标记', async () => {
  let reads = 0;
  const original = {batch_id: 'refresh-resume', status: 'partial', requested: 2, total: 2,
    imported: 1, pending: 1, submitting: 0, unknown: 0, failed: 0,
    can_retry: true, error_code: null, updated_at: '2026-10-28T00:00:00Z'};
  const revision = JSON.stringify([original.updated_at, original.status, original.imported,
    original.pending, original.submitting, original.unknown, original.failed, original.error_code, original.blocked_by]);
  const h = createView({saved: {batch_id: original.batch_id, request_id: 'same-request',
    preview_token: 'same-preview', resume_revision: revision}, handler(call) {
    assert.equal(call.method, 'GET');
    assert.equal(call.url, '/api/email-butler/imports/refresh-resume');
    reads += 1;
    if (reads === 1) return {ok: true, batch: original};
    if (reads === 2) return {ok: true, batch: {...original, status: 'running', updated_at: '2026-10-28T00:00:01Z'}};
    return {ok: true, batch: {...original, status: 'completed', imported: 2, pending: 0,
      can_retry: false, updated_at: '2026-10-28T00:00:02Z'}};
  }});
  await h.settle();
  assert.equal(h.view.state.batch.status, 'partial');
  assert.equal(h.view.state.resumePending, revision);
  assert.equal(h.node('btnRetryButlerImport').hidden, true);
  assert.ok(h.timers.size > 0, '刷新后原 worker 尚在预检时仍继续读进度');
  await h.runTimers(2500);
  assert.equal(h.view.state.batch.status, 'running');
  await h.runTimers(2500);
  assert.equal(h.view.state.batch.status, 'completed');
  assert.equal(h.view.state.batch.imported, 2);
  assert.ok(!JSON.parse(h.storage.get('turb.butler-import.v1')).resume_revision);
  assert.equal(h.timers.size, 0);
  assert.equal(h.requests.length, 3);
});

test('统计按实际批次数量显示进度，并区分失败、跳过和待确认', async () => {
  const h = createView({saved: {batch_id: 'partial', request_id: 'r', preview_token: 'p'}, handler() {
    return {ok: true, batch: {batch_id: 'partial', status: 'partial', requested: 20, total: 5,
      imported: 2, skipped: 1, failed: 1, unknown: 1, pending: 0, submitting: 0, can_retry: true,
      error_counts: {handoff_rejected: 1, handoff_unconfirmed: 1, local_email_conflict: 1}}};
  }});
  await h.settle();
  await h.view.poll();
  assert.equal(h.node('butlerImportProgressBar').max, 5);
  const summary = `${content(h.node('butlerImportStats'))} ${content(h.node('butlerImportProgress'))}`;
  assert.match(summary, /已导入.*2|2.*已导入/);
  assert.match(summary, /跳过.*1|1.*跳过/);
  assert.match(summary, /失败.*2|2.*失败/);
  assert.doesNotMatch(summary, /待确认|未确认/);
  assert.match(content(h.node('butlerImportStatusTitle')), /部分/);
  assert.equal(h.node('btnRetryButlerImport').hidden, false);
});

test('连续轮询只节流刷新库存，结束时立即补刷最终库存', async () => {
  let imported = 1, status = 'running';
  const h = createView({handler(call) {
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p', available: 5, selected: 5};
    return {ok: true, batch: {batch_id: 'active', status, requested: 5, total: 5,
      imported, pending: 5 - imported, can_retry: status === 'running'}};
  }});
  await h.view.preview(); await h.view.apply(); await h.settle();
  assert.equal(h.refreshes.filter(item => item === 'pool').length, 1);
  imported = 2;
  await h.view.poll(); await h.settle();
  imported = 3;
  await h.view.poll(); await h.settle();
  assert.equal(h.refreshes.filter(item => item === 'pool').length, 1);
  h.advanceTime(15001); imported = 4;
  await h.view.poll(); await h.settle();
  assert.equal(h.refreshes.filter(item => item === 'pool').length, 2);
  imported = 5; status = 'completed';
  await h.view.poll(); await h.settle();
  assert.equal(h.refreshes.filter(item => item === 'pool').length, 3);
});

test('库存页刷新很慢时仍可继续查询导入进度', async () => {
  let releaseRefresh;
  const refreshGate = new Promise(resolve => { releaseRefresh = resolve; });
  const h = createView({refreshGate});
  await h.view.preview();
  const applying = h.view.apply();
  try {
    await h.settle();
    assert.equal(h.view.state.busy, false, '库存渲染不阻塞导入请求结束');
    await h.view.poll();
    assert.ok(h.requests.some(call => call.url === '/api/email-butler/imports/batch-1'));
    assert.equal(h.view.state.polling, false);
  } finally {
    releaseRefresh();
    await applying;
  }
});

test('完成后刷新库存和来源；刷新失败不会把已完成批次误报为领取未知', async () => {
  const h = createView({handler(call) {
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p', available: 5, selected: 5};
    return {ok: true, batch: {batch_id: 'done', status: 'completed', requested: 5, total: 5, imported: 5, skipped: 0, can_retry: false}};
  }});
  await h.view.preview(); await h.view.apply(); await h.settle();
  assert.equal(h.view.state.batch.status, 'completed');
  assert.ok(h.refreshes.includes('pool'));
  assert.ok(h.refreshes.includes('sources'));
  assert.ok(h.refreshes.includes('/api/capabilities'));
  assert.match(h.node('butlerImportProgress').textContent, /5/);
});

test('成功导入自动收起右下角提示，保留原记录供邮箱页查看结果', async () => {
  for (const status of ['completed', 'succeeded', 'done']) {
    let currentStatus = 'running';
    const batch = () => ({batch_id: 'completed-batch', status: currentStatus, requested: 5, total: 5,
      imported: currentStatus === 'running' ? 1 : 5, pending: currentStatus === 'running' ? 4 : 0,
      can_retry: currentStatus === 'running'});
    const h = createView({handler(call) {
      if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p', available: 5, selected: 5};
      return {ok: true, batch: batch()};
    }});
    await h.view.preview(); await h.view.apply();
    h.view.close();
    assert.equal(h.node('butlerImportPageStatus').hidden, false);
    currentStatus = status;
    await h.view.poll();
    assert.equal(h.node('butlerImportPageStatus').hidden, true, `${status} 成功后不再常驻提示`);
    const saved = JSON.parse(h.storage.get('turb.butler-import.v1'));
    assert.equal(saved.batch_id, 'completed-batch');
    assert.equal(saved.request_id, '11111111-1111-4111-8111-111111111111');
    assert.match(h.node('btnOpenButlerImportPool').textContent, /查看/);
    await h.node('btnOpenButlerImportPool').listeners.click();
    assert.equal(h.node('butlerImportModal').open, true);
    assert.match(content(h.node('butlerImportStatusTitle')), /完成/);
    assert.match(content(h.node('butlerImportStats')), /5/);
    h.view.close();
    assert.equal(h.node('butlerImportPageStatus').hidden, true);
  }
});

test('刷新已完成页面时不重新弹出右下角提示，仍查询原批次结果', async () => {
  for (const status of ['completed', 'succeeded', 'done']) {
    const finished = {batch_id: 'saved-completed', status, requested: 5, total: 5, imported: 5, can_retry: false};
    const original = createView({saved: {batch_id: finished.batch_id, request_id: 'original-request', preview_token: 'original-preview'},
      handler: () => ({ok: true, batch: finished})});
    await original.settle();
    const saved = JSON.parse(original.storage.get('turb.butler-import.v1'));
    let finishRead;
    const restored = createView({saved, handler: () => new Promise(resolve => { finishRead = resolve; })});
    assert.equal(restored.node('butlerImportPageStatus').hidden, true, '查询返回前也不把已完成批次显示成正在导入');
    assert.equal(restored.requests[0].url, '/api/email-butler/imports/saved-completed');
    assert.equal(restored.requests[0].method, 'GET');
    finishRead({ok: true, batch: finished});
    await restored.settle();
    assert.equal(restored.node('butlerImportPageStatus').hidden, true);
    assert.equal(restored.view.state.batch.batch_id, finished.batch_id);
    assert.equal(restored.view.state.batch.status, status);
  }
});

test('运行中和待处理结果仍保留右下角恢复入口', async () => {
  for (const status of ['running', 'partial', 'unknown', 'failed']) {
    const h = createView({saved: {batch_id: 'recoverable', request_id: 'r', preview_token: 'p'}, handler() {
      return {ok: true, batch: {batch_id: 'recoverable', status, requested: 5, total: 5, imported: 2,
        unknown: status === 'running' ? 0 : 3, pending: status === 'running' ? 3 : 0, can_retry: true}};
    }});
    await h.settle();
    assert.equal(h.node('butlerImportPageStatus').hidden, false, `${status} 仍可恢复查看`);
    await h.node('butlerImportPageStatus').listeners.click();
    assert.equal(h.node('butlerImportModal').open, true);
    h.view.close();
    assert.equal(h.node('butlerImportPageStatus').hidden, false);
  }
});

test('服务端已完成后刷新页面失败保留已完成结果，不提示重新领取', async () => {
  const h = createView({refreshFails: true, handler(call) {
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p', available: 5, selected: 5};
    return {ok: true, batch: {batch_id: 'done', status: 'completed', requested: 5, total: 5, imported: 5, can_retry: false}};
  }});
  await h.view.preview(); await h.view.apply(); await h.settle();
  assert.equal(h.view.state.batch.status, 'completed');
  assert.match(h.node('butlerImportError').textContent, /已导入.*刷新/);
  assert.doesNotMatch(h.node('butlerImportError').textContent, /原请求|尚未确认/);
});

test('异步预览返回时筛选已变更，不使用旧预览', async () => {
  let finish;
  const h = createView({handler() { return new Promise(resolve => { finish = resolve; }); }});
  const preview = h.view.preview();
  h.node('butlerImportProvider').value = 'outlook_graph';
  h.view.invalidate();
  finish({ok: true, preview_token: 'stale', available: 5, selected: 5});
  await preview;
  assert.equal(h.view.state.preview, null);
  assert.equal(h.node('btnApplyButlerImport').disabled, true);
});

test('确定尚未创建批次的失效预览可以清理重做，已有请求冲突保留编号', async () => {
  for (const code of ['import_preview_not_found', 'import_preview_expired', 'import_preview_empty', 'import_snapshot_conflict', 'import_request_conflict']) {
    const h = createView({handler(call) {
      if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p', available: 5, selected: 5};
      throw Object.assign(new Error('rejected'), {code});
    }});
    await h.view.preview(); await h.view.apply();
    if (code === 'import_request_conflict') {
      assert.ok(h.view.state.request);
      assert.ok(h.storage.has('turb.butler-import.v1'));
    } else {
      assert.equal(h.view.state.request, null);
      assert.equal(h.view.state.preview, null);
      assert.equal(h.storage.has('turb.butler-import.v1'), false);
      assert.match(h.node('butlerImportError').textContent, /重新.*(预览|查询)|刷新.*数量/);
    }
  }
});

test('已知失败全部终态允许新建，存在未知记录时保留原批次', async () => {
  for (const unknown of [0, 1]) {
    const h = createView({saved: {batch_id: 'partial', request_id: 'r', preview_token: 'p'}, handler() {
      return {ok: true, batch: {batch_id: 'partial', status: 'partial', imported: 2, failed: 3, unknown, can_retry: !!unknown}};
    }});
    await h.settle();
    await h.view.poll();
    assert.equal(h.node('btnNewButlerImport').hidden, !!unknown);
    h.view.reset();
    assert.equal(h.view.state.batch === null, !unknown);
  }
});

test('显式终止待确认批次保留结果，清除右下角提示并允许新建', async () => {
  const batch = {batch_id: 'stop-partial', status: 'partial', total: 100, requested: 100,
    imported: 1, unknown: 99, can_retry: true, can_cancel: true};
  const h = createView({saved: {batch_id: batch.batch_id, request_id: 'r', preview_token: 'p'}, handler(call) {
    if (call.url.endsWith('/cancel')) return {ok: true, batch: {...batch, status: 'cancelled', can_retry: false, can_cancel: false}};
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'new-preview', available: 10, selected: 5};
    return {ok: true, batch};
  }});
  await h.settle();
  assert.equal(h.node('btnTerminateButlerImport').hidden, false);
  h.view.close();
  assert.equal(h.requests.filter(call => call.method === 'POST').length, 0, '关闭保持原批次');
  assert.equal(h.node('butlerImportPageStatus').hidden, false);
  await h.node('btnTerminateButlerImport').listeners.click();
  assert.equal(h.requests.at(-1).url, '/api/email-butler/imports/stop-partial/cancel');
  assert.equal(h.requests.at(-1).method, 'POST');
  assert.equal(h.view.state.batch.status, 'cancelled');
  assert.equal(h.view.state.batch.unknown, 99);
  assert.equal(h.view.state.batch.imported, 1);
  assert.equal(h.node('btnRetryButlerImport').hidden, true);
  assert.equal(h.node('btnTerminateButlerImport').hidden, true);
  assert.equal(h.node('butlerImportPageStatus').hidden, true);
  assert.equal(h.node('btnNewButlerImport').hidden, false);
  assert.match(h.node('butlerImportStatusHint').textContent, /保留.*请求.*保存结果/);
  assert.equal(h.timers.size, 0);
  assert.equal(JSON.parse(h.storage.get('turb.butler-import.v1')).batch_status, 'cancelled');
  await h.view.retry();
  assert.equal(h.requests.filter(call => call.method === 'POST').length, 1, '终止后不能重新启动原批次');
  h.view.reset();
  await h.settle();
  assert.equal(h.view.state.batch, null);
  assert.equal(h.view.state.request, null);
  assert.equal(h.node('butlerImportProvider').disabled, false);
  assert.ok(h.requests.every(call => call.url !== '/api/email-butler/imports'), '新建仅查询数量，不自动分配');
});

test('终止请求显示等待，阻止重复点击；失败保留原批次和继续入口', async () => {
  let rejectCancel;
  const batch = {batch_id: 'cancel-fails', status: 'partial', unknown: 2, can_retry: true, can_cancel: true};
  const h = createView({saved: {batch_id: batch.batch_id, request_id: 'r', preview_token: 'p'}, handler(call) {
    if (call.url.endsWith('/cancel')) return new Promise((_resolve, reject) => { rejectCancel = reject; });
    return {ok: true, batch};
  }});
  await h.settle();
  const cancellation = h.view.terminate();
  await h.view.terminate();
  assert.equal(h.requests.filter(call => call.url.endsWith('/cancel')).length, 1);
  assert.equal(h.node('btnTerminateButlerImport').disabled, true);
  assert.equal(h.node('btnTerminateButlerImport').textContent, '正在终止…');
  rejectCancel(new Error('暂时无法连接'));
  await cancellation;
  assert.equal(h.view.state.batch.status, 'partial');
  assert.equal(h.node('btnRetryButlerImport').hidden, false);
  assert.equal(h.node('btnNewButlerImport').hidden, true);
  assert.equal(h.node('btnTerminateButlerImport').disabled, false);
  assert.match(h.node('butlerImportError').textContent, /终止请求失败.*保留原批次/);
});

test('刷新已终止批次不复活提示，旧状态响应也不能覆盖终止状态', async () => {
  let finishRead;
  const h = createView({saved: {batch_id: 'saved-cancelled', batch_status: 'cancelled',
    request_id: 'r', preview_token: 'p', resume_revision: 'old'},
    handler: () => new Promise(resolve => { finishRead = resolve; })});
  assert.equal(h.view.state.batch.status, 'cancelled');
  assert.equal(h.node('butlerImportPageStatus').hidden, true);
  assert.equal(h.view.state.resumePending, null);
  finishRead({ok: true, batch: {batch_id: 'saved-cancelled', status: 'partial', unknown: 100, can_retry: true}});
  await h.settle();
  assert.equal(h.view.state.batch.status, 'cancelled');
  assert.equal(h.view.state.batch.can_retry, false);
  assert.equal(h.node('butlerImportPageStatus').hidden, true);
  assert.equal(h.node('btnNewButlerImport').hidden, false);
  assert.equal(h.timers.size, 0);
  assert.ok(h.requests.every(call => call.method === 'GET'));
});

test('终止可在轮询未返回时执行，迟到响应不能恢复旧批次或污染新建', async () => {
  let finishRead;
  const batch = {batch_id: 'inflight-stop', status: 'running', pending: 5, can_retry: true, can_cancel: true};
  const h = createView({saved: {batch_id: batch.batch_id, request_id: 'r', preview_token: 'p'}, handler(call) {
    if (call.url.endsWith('/cancel')) return {ok: true, batch: {...batch, status: 'cancelled', can_retry: false, can_cancel: false}};
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p2', available: 5, selected: 5};
    return new Promise(resolve => { finishRead = resolve; });
  }});
  assert.equal(h.view.state.polling, true);
  assert.equal(h.node('btnTerminateButlerImport').disabled, false);
  await h.view.terminate();
  assert.equal(h.view.state.polling, false);
  h.view.reset();
  await h.settle();
  finishRead({ok: true, batch});
  await h.settle();
  assert.equal(h.view.state.batch, null);
  assert.equal(h.view.state.request, null);
  assert.equal(h.node('butlerImportPageStatus').hidden, true);
  assert.equal(h.storage.has('turb.butler-import.v1'), false);
});

test('其他标签页终止同批次后立即隐藏提示，忽略此前发出的查询', async () => {
  let finishRead;
  const h = createView({saved: {batch_id: 'shared-batch', request_id: 'r', preview_token: 'p'},
    handler: () => new Promise(resolve => { finishRead = resolve; })});
  const saved = {batch_id: 'shared-batch', batch_status: 'cancelled', request_id: 'r', preview_token: 'p'};
  h.storage.set('turb.butler-import.v1', JSON.stringify(saved));
  h.windowListeners.storage({key: 'turb.butler-import.v1', newValue: JSON.stringify(saved)});
  assert.equal(h.view.state.batch.status, 'cancelled');
  assert.equal(h.node('butlerImportPageStatus').hidden, true);
  assert.equal(h.node('btnNewButlerImport').hidden, false);
  finishRead({ok: true, batch: {batch_id: 'shared-batch', status: 'running', pending: 10, can_retry: true}});
  await h.settle();
  assert.equal(h.view.state.batch.status, 'cancelled');
  assert.equal(h.view.state.polling, false);
  assert.equal(h.timers.size, 0);
});

test('两个入口同步恢复提示，重新载入时展示原请求筛选', async () => {
  const h = createView({saved: {request_id: 'r', preview_token: 'p', filters: {provider: 'outlook_graph', count: 7}}});
  assert.match(h.node('btnOpenButlerImport').textContent, /Butler.*导入|导入.*Butler/);
  assert.match(h.node('btnOpenButlerImportPool').textContent, /Butler.*导入|导入.*Butler/);
  assert.equal(h.node('butlerImportProvider').value, 'outlook_graph');
  assert.equal(h.node('butlerImportCount').value, '7');
  assert.equal(h.node('butlerImportProvider').disabled, true);
});


test('新版支持四种来源和自动分配，只提交来源与数量', async () => {
  for (const provider of ['icloud_hme', 'outlook_graph', 'cloudflare', 'mailcom', 'auto']) {
    const h = createView();
    h.node('butlerImportProvider').value = provider;
    await h.view.preview();
    assert.deepEqual(h.requests.at(-1).body, {provider, count: 5});
    assert.match(h.node('butlerImportPreview').textContent, /确认后由 Butler 分配/);
  }
  const template = fs.readFileSync(path.join(__dirname, '../../webui/templates/index.html'), 'utf8');
  const modal = template.slice(template.indexOf('<dialog id="butlerImportModal"'), template.indexOf('</dialog>', template.indexOf('<dialog id="butlerImportModal"')));
  assert.doesNotMatch(modal, /id="butlerImport(?:Identity|Domain|Group)"/);
  assert.match(modal, /for="butlerImportProvider"/);
  assert.match(modal, /for="butlerImportCount"/);
});


test('导入和终止收到明确拒绝时展示原原因，不误报响应丢失或更换请求', async () => {
  const original = {request_id:'same-request', preview_token:'same-preview'};
  const denied = () => Object.assign(new Error('当前 Key 缺少操作权限'), {status:403, code:'permission_denied'});
  const create = createView({saved:original, handler() {throw denied();}});
  await create.settle();
  await create.view.retry();
  const createError = create.node('butlerImportError').textContent;
  assert.match(createError, /导入请求失败：当前 Key 缺少操作权限/);
  assert.doesNotMatch(createError, /响应缺失|未收到响应/);
  assert.equal(create.requests.at(-1).body.request_id, original.request_id);
  assert.equal(create.view.state.request.request_id, original.request_id);
  const batch = {batch_id:'same-batch', status:'partial', can_retry:true, can_cancel:true};
  const stop = createView({saved:{...original, batch_id:batch.batch_id}, handler(call) {
    if (call.url.endsWith('/cancel')) throw denied();
    return {ok:true, batch};
  }});
  await stop.settle();
  await stop.view.terminate();
  const stopError = stop.node('butlerImportError').textContent;
  assert.match(stopError, /终止请求失败：当前 Key 缺少操作权限/);
  assert.doesNotMatch(stopError, /响应缺失|未收到响应/);
  assert.equal(stop.view.state.batch.batch_id, batch.batch_id);
  assert.equal(stop.view.state.request.request_id, original.request_id);
});
