const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = path.join(__dirname, '../webui/static/js/modern/butler-import.js');

function createView({saved, handler, storageFails = false, refreshFails = false} = {}) {
  const nodes = new Map(), requests = [], timers = new Map(), refreshes = [];
  let timerId = 0;
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
    localStorage: {
      getItem: key => storage.get(key) || null,
      setItem(key, value) { if (storageFails) throw new Error('storage unavailable'); storage.set(key, value); },
      removeItem: key => storage.delete(key),
    },
    setTimeout(fn) { const id = ++timerId; timers.set(id, fn); return id; },
    clearTimeout: id => timers.delete(id),
    esc: value => String(value).replaceAll('<', '&lt;'),
    invalidateApiCache: url => refreshes.push(url),
    setPoolSourceV2: source => refreshes.push(source),
    loadCapabilities: () => { if (refreshFails) throw new Error('refresh failed'); refreshes.push('capabilities'); },
    loadRegistrationEmailSources: async () => refreshes.push('sources'),
    loadOutlook: async () => refreshes.push('pool'),
    loadMailResources: async () => refreshes.push('resources'),
    loadSummary: async () => refreshes.push('summary'),
    api: async (url, options = {}) => {
      const call = {url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : undefined};
      requests.push(call);
      if (handler) return handler(call, {storage, node});
      if (url.endsWith('import-options')) return {ok: true, providers: [{value: 'icloud_hme', label: 'iCloud HME'}], max_count: 200};
      if (url.endsWith('import-preview')) return {ok: true, preview_token: 'preview-1', available: 12, selected: 5, count: 5, items: []};
      return {ok: true, batch: {batch_id: 'batch-1', status: 'running', requested: 5, total: 5, imported: 1, skipped: 0, pending: 4}};
    },
  };
  vm.createContext(context);
  assert.ok(fs.existsSync(script), '手动 Butler 导入脚本尚未实现');
  vm.runInContext(fs.readFileSync(script, 'utf8') + '\nglobalThis.view = {state: BUTLER_IMPORT_STATE, open: openButlerImportModal, close: closeButlerImportModal, preview: previewButlerImport, apply: applyButlerImport, poll: pollButlerImport, retry: retryButlerImport, invalidate: invalidateButlerImportPreview, reset: resetButlerImport};', context);
  return {view: context.view, node, requests, storage, timers, refreshes, document};
}

test('预览仅调用只读接口，筛选变化使旧预览不能提交', async () => {
  const h = createView();
  await h.view.preview();
  assert.deepEqual(h.requests.map(item => item.url), ['/api/email-butler/import-preview']);
  assert.deepEqual(h.requests[0].body, {provider: 'icloud_hme', identity_type: 'all', count: 5, domain: '', group: ''});
  assert.match(h.node('butlerImportPreview').textContent, /12.*5/);
  h.node('butlerImportCount').value = '6';
  h.view.invalidate();
  await h.view.apply();
  assert.equal(h.requests.length, 1);
  assert.equal(h.node('btnApplyButlerImport').disabled, true);
});

test('数量范围和类型在前端校验，未发送无效预览', async () => {
  for (const value of ['0', '201', '1.5', '']) {
    const h = createView(); h.node('butlerImportCount').value = value;
    await h.view.preview();
    assert.equal(h.requests.length, 0);
    assert.match(h.node('butlerImportError').textContent, /1.*200/);
  }
  const h = createView(); h.node('butlerImportProvider').value = 'outlook';
  await h.view.preview();
  assert.equal(h.requests.length, 0);
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
  await partial.view.poll();
  assert.equal(partial.node('btnRetryButlerImport').hidden, false);
  await partial.view.retry();
  assert.equal(partial.requests.at(-1).url, '/api/email-butler/imports/batch-2/retry');
  assert.equal(partial.requests.at(-1).method, 'POST');
});

test('完成后刷新库存和来源；刷新失败不会把已完成批次误报为领取未知', async () => {
  const h = createView({handler(call) {
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p', available: 5, selected: 5};
    return {ok: true, batch: {batch_id: 'done', status: 'completed', requested: 5, total: 5, imported: 5, skipped: 0, can_retry: false}};
  }});
  await h.view.preview(); await h.view.apply();
  assert.equal(h.view.state.batch.status, 'completed');
  assert.ok(h.refreshes.includes('pool'));
  assert.ok(h.refreshes.includes('sources'));
  assert.ok(h.refreshes.includes('/api/capabilities'));
  assert.match(h.node('butlerImportProgress').textContent, /5/);
});

test('服务端已完成后刷新页面失败保留已完成结果，不提示重新领取', async () => {
  const h = createView({refreshFails: true, handler(call) {
    if (call.url.endsWith('import-preview')) return {ok: true, preview_token: 'p', available: 5, selected: 5};
    return {ok: true, batch: {batch_id: 'done', status: 'completed', requested: 5, total: 5, imported: 5, can_retry: false}};
  }});
  await h.view.preview(); await h.view.apply();
  assert.equal(h.view.state.batch.status, 'completed');
  assert.match(h.node('butlerImportError').textContent, /已导入.*刷新/);
  assert.doesNotMatch(h.node('butlerImportError').textContent, /原请求|尚未确认/);
});

test('异步预览返回时筛选已变更，不使用旧预览', async () => {
  let finish;
  const h = createView({handler() { return new Promise(resolve => { finish = resolve; }); }});
  const preview = h.view.preview();
  h.node('butlerImportIdentity').value = 'primary';
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
      assert.match(h.node('butlerImportError').textContent, /重新预览/);
    }
  }
});

test('已知失败全部终态允许新建，存在未知记录时保留原批次', async () => {
  for (const unknown of [0, 1]) {
    const h = createView({saved: {batch_id: 'partial', request_id: 'r', preview_token: 'p'}, handler() {
      return {ok: true, batch: {batch_id: 'partial', status: 'partial', imported: 2, failed: 3, unknown, can_retry: !!unknown}};
    }});
    await h.view.poll();
    assert.equal(h.node('btnNewButlerImport').hidden, !!unknown);
    h.view.reset();
    assert.equal(h.view.state.batch === null, !unknown);
  }
});

test('两个入口同步恢复提示，重新载入时展示原请求筛选', async () => {
  const h = createView({saved: {request_id: 'r', preview_token: 'p', filters: {provider: 'icloud_hme', identity_type: 'plus_alias', count: 7, domain: '', group: 'prepared'}}});
  assert.equal(h.node('btnOpenButlerImport').textContent, '恢复 Butler 导入');
  assert.equal(h.node('btnOpenButlerImportPool').textContent, '恢复 Butler 导入');
  assert.equal(h.node('butlerImportIdentity').value, 'plus_alias');
  assert.equal(h.node('butlerImportCount').value, '7');
  assert.equal(h.node('butlerImportGroup').value, 'prepared');
});
