const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const fullSource = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/email.js'), 'utf8');
const importSource = fullSource.slice(fullSource.indexOf('const IMPORT_SOURCE_LABELS'), fullSource.indexOf('async function bulkMarkOutlookStatus'));

function createImportView() {
  const nodes = new Map(), calls = [], poolChanges = [], toasts = [], refreshes = [];
  const element = selector => {
    const id = selector.replace(/^#/, '');
    if (!nodes.has(id)) nodes.set(id, {
      value: '', textContent: '', innerHTML: '', disabled: false, dataset: {},
      classList: {remove() {}, add() {}, toggle() {}}, querySelectorAll: () => [], focus() {},
    });
    return nodes.get(id);
  };
  const context = {
    $: element, document: {getElementById: element}, esc: String, setTimeout: () => {},
    getPoolSource: () => 'email_butler', updateModalScrollLock() {},
    setPoolSourceV2: source => poolChanges.push(source),
    loadOutlook: () => refreshes.push('list'), loadMailResources: () => refreshes.push('resources'), loadSummary: () => refreshes.push('summary'),
    invalidateApiCache() {}, loadCapabilities: async () => {}, loadRegistrationEmailSources: async () => {},
    showToast: message => toasts.push(message),
    api: async (url, options) => {
      calls.push({url, body: JSON.parse(options.body)});
      return url.endsWith('import-preview') ? {valid: 2, invalid: 0, new: 2, existing: 0, duplicate_in_input: 0, extra_fields: 0}
        : {parsed: 2, inserted: 2, skipped: 0, invalid: 0, extra_fields: 0};
    },
  };
  vm.createContext(context);
  vm.runInContext(`${importSource}\nglobalThis.view = {openOutlookImportModal, setImportSourceV2, previewOutlookImport, doImportOutlook};`, context);
  return {context, view: context.view, element, calls, poolChanges, toasts, refreshes};
}

test('打开本地 Butler 池的导入弹窗保留来源，提示完整 HME 地址', () => {
  const {view, element} = createImportView();
  view.openOutlookImportModal();
  assert.equal(element('importSourceV2').value, 'email_butler');
  assert.match(element('importTextV2').placeholder, /icloud\.com/);
  assert.match(element('importFormatHintV2').textContent, /每行.*完整/);
  assert.match(element('importFormatHintV2').textContent, /手动/);
});

test('本地 Butler 地址列表复用预览和导入合同，不发远端领取请求', async () => {
  const {view, element, calls, poolChanges, refreshes} = createImportView();
  view.setImportSourceV2('email_butler');
  element('importTextV2').value = 'one@icloud.com\ntwo+tag@icloud.com';
  await view.previewOutlookImport();
  await view.doImportOutlook();
  assert.deepEqual(calls.map(call => call.url), ['/api/outlook/import-preview', '/api/outlook/import']);
  for (const call of calls) assert.deepEqual(call.body, {source: 'email_butler', text: 'one@icloud.com\ntwo+tag@icloud.com'});
  assert.deepEqual(poolChanges, ['email_butler']);
  assert.deepEqual(refreshes, ['list', 'resources', 'summary']);
});

test('Outlook 和通用 API 旧导入格式原样提交', async () => {
  for (const [source, text] of [['outlook', 'one@example.test----password----client----refresh'], ['generic_api', 'one@example.test----https://fixture.test/code']]) {
    const {view, element, calls} = createImportView();
    view.setImportSourceV2(source);
    element('importTextV2').value = text;
    await view.previewOutlookImport();
    await view.doImportOutlook();
    assert.deepEqual(calls.at(-1).body, {source, text});
    assert.match(element('importTextV2').placeholder, /----/);
  }
});

test('通用 API 批次有效期在预览和导入一致提交，其他来源不携带旧草稿', async () => {
  const {view, element, calls} = createImportView();
  view.setImportSourceV2('generic_api');
  element('importTextV2').value = 'one@example.test----https://fixture.test/code';
  element('importExpiresAtV2').value = '2026-10-28T12:00:00+08:00';
  assert.equal(element('importExpiryFieldV2').hidden, false);
  assert.match(element('importFormatHintV2').textContent, /第三.*有效期/);
  assert.match(element('importFormatHintV2').textContent, /时区/);
  await view.previewOutlookImport();
  await view.doImportOutlook();
  assert.equal(calls[0].body.expires_at, '2026-10-28T12:00:00+08:00');
  assert.equal(calls[1].body.expires_at, '2026-10-28T12:00:00+08:00');
  view.setImportSourceV2('outlook');
  assert.equal(element('importExpiryFieldV2').hidden, true);
  element('importTextV2').value = 'one@example.test----password----client----refresh';
  await view.previewOutlookImport();
  assert.equal(Object.hasOwn(calls.at(-1).body, 'expires_at'), false);
});

test('导入清除旧的空库存缓存，刷新注册来源后新库存立即可选', async () => {
  const {context, view, element} = createImportView();
  const common = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');
  const jobs = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/jobs.js'), 'utf8');
  const cacheSource = common.slice(common.indexOf('async function apiCached'), common.indexOf('function markViewReady'));
  const capabilitiesSource = common.slice(common.indexOf('async function loadCapabilities'), common.indexOf("document.addEventListener('click', (event)", common.indexOf('async function loadCapabilities')));
  let imported = false;
  const importApi = context.api;
  context.api = async (url, options) => {
    if (url === '/api/email-sources') return {sources: [{value: 'email_butler', label: 'Butler 本地邮箱', enabled: imported}]};
    if (url === '/api/capabilities') return {email_sources: {email_butler: {enabled: imported}}};
    const result = await importApi(url, options);
    if (url === '/api/outlook/import') imported = true;
    return result;
  };
  context.applyFeatureGates = () => {};
  vm.runInContext(`const API_CACHE = new Map(); let CAPABILITIES = {}; let REGISTRATION_EMAIL_SOURCES = [];\n${cacheSource}\n${capabilitiesSource}\n${jobs.slice(0, jobs.indexOf('async function startRegistrationFromInputs'))}`, context);
  await context.loadRegistrationEmailSources();
  assert.match(element('regEmailSourceV2').innerHTML, /value="email_butler" disabled/);
  view.setImportSourceV2('email_butler');
  element('importTextV2').value = 'one@icloud.com';
  await view.doImportOutlook();
  assert.match(element('regEmailSourceV2').innerHTML, /value="email_butler"/);
  assert.doesNotMatch(element('regEmailSourceV2').innerHTML, /value="email_butler" disabled/);
});

test('邮箱资源页只加载本地 dashboard，导入入口不会触发 Butler 租用', async () => {
  const template = fs.readFileSync(path.join(__dirname, '../webui/templates/index.html'), 'utf8');
  const ids = new Set([...template.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]));
  const elements = new Map(), calls = [], opened = [], rendered = [];
  const element = selector => {
    const id = selector.replace(/^#/, '');
    if (!ids.has(id)) return null;
    if (!elements.has(id)) elements.set(id, {handlers: {}, addEventListener(name, handler) { this.handlers[name] = handler; }});
    return elements.get(id);
  };
  const context = {
    $: element, sessionStorage: {getItem() {}}, renderMailSourceCards: rows => rendered.push(rows), renderButlerLeases() {},
    setPoolSourceV2() {}, setModuleView() {}, showToast() {}, markViewReady() {},
    openOutlookImportModal: source => opened.push(source),
    apiCached: async url => { calls.push(url); return {email: {supply: {sources: [{source: 'email_butler', kind: 'local_pool', available: 2}]}}}; },
    api: async url => { calls.push(url); throw new Error('禁止远端租用'); },
  };
  vm.createContext(context);
  const resourceSource = fullSource.slice(fullSource.indexOf('async function loadMailResources'), fullSource.indexOf('async function loadOutlook'));
  vm.runInContext(`${resourceSource}\nglobalThis.loadResources = loadMailResources;`, context);
  await context.loadResources();
  assert.deepEqual(calls, ['/api/dashboard']);
  assert.equal(rendered[0][0].available, 2);
  assert.equal(element('btnLeaseButlerMailbox'), null);
  element('btnImportButlerMailboxes').handlers.click();
  assert.deepEqual(opened, ['email_butler']);
});
