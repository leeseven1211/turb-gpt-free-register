const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const common = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/common.js'), 'utf8');

function pagerHarness() {
  const elements = new Map();
  const view = {
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, {innerHTML: ''});
        return elements.get(id);
      },
    },
    refreshJobs() {}, loadAccounts() {}, loadOutlook() {}, loadCodex() {}, loadAccountTasks() {},
    JOBS_TOTAL: 0, ACCOUNTS_TOTAL: 0, OUTLOOK_TOTAL: 0, CODEX_TOTAL: 0, ACCOUNT_TASKS_TOTAL: 0,
  };
  const start = common.indexOf('// ---------- 分页状态 ----------');
  const end = common.indexOf('// ---------- 统一列表列宽 ----------');
  vm.createContext(view);
  vm.runInContext(`${common.slice(start, end)}\nthis.testPagers = PAGERS; this.testRenderPager = _renderPager; this.testPagerSetSize = pagerSetSize;`, view);
  return {view, elements};
}

function createResizableTable(key, savedWidths, savedTotal) {
  const count = key === 'accounts' ? 15 : 10;
  const columns = Array.from({length: count}, () => ({style: {}}));
  const listeners = new Map();
  const storage = new Map([
    [`gpt_console_table_widths_${key}`, JSON.stringify(savedWidths)],
    [`gpt_console_table_total_${key}`, String(savedTotal)],
  ]);
  const style = {
    width: '',
    setProperty(name, value) { this[name] = value; },
    removeProperty(name) { delete this[name]; },
  };
  const table = {
    dataset: {resizableTable: key},
    style,
    columns,
    querySelectorAll(selector) { return selector === 'colgroup col' ? columns : headers; },
    getBoundingClientRect() { return {width: Number.parseFloat(style.width) || 1396}; },
  };
  const headers = Array.from({length: count}, (_, index) => ({
    classList: {contains() { return false; }},
    appendChild(handle) { this.handle = handle; },
    getBoundingClientRect() {
      return {width: (Number.parseFloat(columns[index].style.width) || 0) * table.getBoundingClientRect().width / 100};
    },
  }));
  const view = {
    localStorage: {
      getItem(keyName) { return storage.get(keyName) || null; },
      setItem(keyName, value) { storage.set(keyName, value); },
      removeItem(keyName) { storage.delete(keyName); },
    },
    document: {
      body: {classList: {add() {}, remove() {}}},
      createElement() {
        return {
          classList: {add() {}, remove() {}},
          setAttribute() {},
          addEventListener(name, callback) { this[`on${name}`] = callback; },
        };
      },
      addEventListener(name, callback) { listeners.set(name, callback); },
      removeEventListener(name) { listeners.delete(name); },
    },
  };
  const start = common.indexOf('const ACCOUNT_COLUMN_MIN_WIDTH =');
  const end = common.indexOf('function initResizableTables(');
  vm.createContext(view);
  vm.runInContext(`${common.slice(start, end)}\nthis.testInitResizableTable = initResizableTable;`, view);
  view.testInitResizableTable(table);
  return {table, columns, headers, listeners, storage};
}

function pixelWidths(table) {
  const total = table.getBoundingClientRect().width;
  return table.columns.map(column => Number.parseFloat(column.style.width) * total / 100);
}

function assertPixels(actual, expected, message) {
  assert.ok(Math.abs(actual - expected) < 0.01, `${message || '像素宽度'}: ${actual} ≠ ${expected}`);
}

test('账号分页默认 10 条，其他表仍默认 20 条且无效重置不退回 20', () => {
  const {view, elements} = pagerHarness();
  assert.equal(view.testPagers.accounts.size, 10);
  assert.equal(view.testPagers.jobs.size, 20);
  view.testPagers.accounts.page = 4;
  view.testPagerSetSize('accounts', 'invalid');
  assert.equal(view.testPagers.accounts.size, 10);
  assert.equal(view.testPagers.accounts.page, 1);
  view.testPagerSetSize('accounts', 50);
  assert.equal(view.testPagers.accounts.size, 50);
  view.testRenderPager('accounts', 51);
  assert.match(elements.get('pager-accounts').innerHTML, /10 条\/页/);
  assert.match(elements.get('pager-accounts').innerHTML, /50 条\/页/);
  assert.match(elements.get('pager-accounts-v2').innerHTML, /10条\/页/);
});

test('账号列大幅拖动只改变当前列并保存整表宽度，刷新后按用户比例恢复', () => {
  const pixels = [100, 200, 100, 100, 100, 50, 50, 50, 50, 50, 50, 25, 25, 25, 25];
  const ratios = pixels.map(width => width / 1000);
  const first = createResizableTable('accounts', ratios, 1000);
  const before = pixelWidths(first.table);
  first.headers[0].handle.onpointerdown({button: 0, clientX: 100, preventDefault() {}, stopPropagation() {}});
  first.listeners.get('pointermove')({clientX: 600});
  const dragged = pixelWidths(first.table);
  assert.equal(first.table.getBoundingClientRect().width, 1500);
  assertPixels(dragged[0], 600);
  before.slice(1).forEach((width, index) => assertPixels(dragged[index + 1], width));
  first.listeners.get('pointerup')();
  assert.equal(first.storage.get('gpt_console_table_total_accounts'), '1500');

  const saved = JSON.parse(first.storage.get('gpt_console_table_widths_accounts'));
  const reloaded = createResizableTable('accounts', saved, 1500);
  const restored = pixelWidths(reloaded.table);
  assertPixels(restored[0], 600);
  before.slice(1).forEach((width, index) => assertPixels(restored[index + 1], width));
  assert.deepEqual(JSON.parse(reloaded.storage.get('gpt_console_table_widths_accounts')), saved);
});

test('账号列可继续缩到极小正宽度，邻列不被最小宽度卡住；其他表保持相邻列拖动', () => {
  const savedRatios = [0.1, 0.2, 0.1, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.025, 0.025, 0.025, 0.025];
  const account = createResizableTable('accounts', savedRatios, 1000);
  const tinyIdRatio = [...savedRatios];
  tinyIdRatio[1] = 0.001;
  const narrowId = createResizableTable('accounts', tinyIdRatio, 1000);
  assertPixels(Number.parseFloat(narrowId.columns[1].style.width), tinyIdRatio[1] / tinyIdRatio.reduce((sum, value) => sum + value, 0) * 100);
  account.headers[0].handle.onpointerdown({button: 0, clientX: 100, preventDefault() {}, stopPropagation() {}});
  account.listeners.get('pointermove')({clientX: -10000});
  const narrowed = pixelWidths(account.table);
  assertPixels(narrowed[0], 28);
  assert.equal(account.table.getBoundingClientRect().width, 928);
  assertPixels(narrowed[1], 200);

  const jobs = createResizableTable('jobs', Array(10).fill(0.1), 1000);
  jobs.headers[2].handle.onpointerdown({button: 0, clientX: 100, preventDefault() {}, stopPropagation() {}});
  jobs.listeners.get('pointermove')({clientX: 120});
  const resizedJobs = pixelWidths(jobs.table);
  assert.equal(jobs.table.getBoundingClientRect().width, 1396);
  assertPixels(resizedJobs[2], 159.6);
  assertPixels(resizedJobs[3], 119.6);
});

test('账号表最后操作列也可大幅调宽，并保持其他列像素宽度', () => {
  const pixels = [100, 200, 100, 100, 100, 50, 50, 50, 50, 50, 50, 25, 25, 25, 25];
  const table = createResizableTable('accounts', pixels.map(width => width / 1000), 1000);
  const before = pixelWidths(table.table);
  const last = table.headers.length - 1;
  assert.ok(table.headers[last].handle, '最后一列应有拖动手柄');
  table.headers[last].handle.onpointerdown({button: 0, clientX: 100, preventDefault() {}, stopPropagation() {}});
  table.listeners.get('pointermove')({clientX: 600});
  const after = pixelWidths(table.table);
  assert.equal(table.table.getBoundingClientRect().width, 1500);
  before.slice(0, last).forEach((width, index) => assertPixels(after[index], width));
  assertPixels(after[last], before[last] + 500);
  table.listeners.get('pointerup')();
  assert.equal(table.storage.get('gpt_console_table_total_accounts'), '1500');
});
