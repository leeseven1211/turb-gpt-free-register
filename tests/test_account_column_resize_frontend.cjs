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

function createResizableTable(key, savedWidths, savedTotal, options = {}) {
  const count = key === 'accounts' ? 15 : 10;
  const layoutStorageKey = 'gpt_console_accounts_columns_v2';
  const columns = Array.from({length: count}, () => ({style: {}}));
  const listeners = new Map();
  const storage = new Map([
    [`gpt_console_table_widths_${key}`, JSON.stringify(savedWidths)],
    [`gpt_console_table_total_${key}`, String(savedTotal)],
  ]);
  if (key === 'accounts' && options.layoutVersion) storage.set(layoutStorageKey, options.layoutVersion === true ? '2' : options.layoutVersion);
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
  return {table, columns, headers, listeners, storage, layoutStorageKey};
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

test('Codex 普通拖动只与创建时间列交换宽度，操作列位置不变', () => {
  const pixels = [36, 72, 160, 80, 84, 88, 72, 88, 88, 192, 72, 88, 72, 96, 108];
  const total = pixels.reduce((sum, width) => sum + width, 0);
  const table = createResizableTable('accounts', pixels.map(width => width / total), total);
  const before = pixelWidths(table.table);
  const index = pixels.length - 3;
  table.headers[index].handle.onpointerdown({button: 0, clientX: 100, preventDefault() {}, stopPropagation() {}});
  table.listeners.get('pointermove')({clientX: 150});
  const dragged = pixelWidths(table.table);

  assert.equal(table.table.getBoundingClientRect().width, total);
  before.slice(0, index).forEach((width, i) => assertPixels(dragged[i], width, `当前列前第 ${i} 列`));
  assertPixels(dragged[index], before[index] + 50, '当前列');
  assertPixels(dragged[index + 1], before[index + 1] - 50, '相邻列');
  before.slice(index + 2).forEach((width, i) => assertPixels(dragged[index + i + 2], width, `当前列后第 ${i} 列`));
  assertPixels(dragged.slice(0, index + 2).reduce((sum, width) => sum + width, 0), before.slice(0, index + 2).reduce((sum, width) => sum + width, 0), '操作列左边界');
  assertPixels(dragged.reduce((sum, width) => sum + width, 0), before.reduce((sum, width) => sum + width, 0), '操作列右边界');
  table.listeners.get('pointerup')();
  assert.equal(table.storage.get('gpt_console_table_total_accounts'), String(total));
});

test('账号列继续向右拖动时先耗尽相邻列，再扩表并保持更远列宽度', () => {
  const pixels = [100, 200, 100, 100, 100, 50, 50, 50, 50, 50, 50, 25, 25, 25, 25];
  const ratios = pixels.map(width => width / 1000);
  const first = createResizableTable('accounts', ratios, 1000);
  const before = pixelWidths(first.table);
  first.headers[0].handle.onpointerdown({button: 0, clientX: 100, preventDefault() {}, stopPropagation() {}});
  first.listeners.get('pointermove')({clientX: 600});
  const dragged = pixelWidths(first.table);
  assert.equal(first.table.getBoundingClientRect().width, 1328);
  assertPixels(dragged[0], 600);
  assertPixels(dragged[1], 28, '相邻列最小宽度');
  before.slice(2).forEach((width, index) => assertPixels(dragged[index + 2], width));
  first.listeners.get('pointerup')();
  assert.equal(first.storage.get('gpt_console_table_total_accounts'), '1328');

  const saved = JSON.parse(first.storage.get('gpt_console_table_widths_accounts'));
  const reloaded = createResizableTable('accounts', saved, 1328, {layoutVersion: true});
  const restored = pixelWidths(reloaded.table);
  assertPixels(restored[0], 600);
  assertPixels(restored[1], 28, '重载后的相邻列');
  before.slice(2).forEach((width, index) => assertPixels(restored[index + 2], width));
  assert.deepEqual(JSON.parse(reloaded.storage.get('gpt_console_table_widths_accounts')), saved);
});

test('未标记的历史超宽操作列只迁移一次，并保持其余列像素宽度', () => {
  const defaultPrefix = [36, 72, 160, 80, 84, 88, 72, 88, 88, 192, 72, 88, 72, 96];
  const prefixScale = 1406.72 / defaultPrefix.reduce((sum, value) => sum + value, 0);
  const historicalPixels = defaultPrefix.map(value => value * prefixScale).concat(696.28);
  const historicalRatios = historicalPixels.map(value => value / 2103);
  const first = createResizableTable('accounts', historicalRatios, 2103);
  const before = pixelWidths(first.table);
  const last = before.length - 1;

  assert.equal(first.table.style.width, '1514.72px');
  before.slice(0, last).forEach((width, index) => assertPixels(width, historicalPixels[index], `迁移前第 ${index} 列`));
  const migrated = pixelWidths(first.table);
  migrated.slice(0, last).forEach((width, index) => assertPixels(width, before[index], `迁移后第 ${index} 列`));
  assertPixels(migrated[last], 108, '迁移后的操作列');
  assert.equal(first.storage.get(first.layoutStorageKey), '2');
  assert.ok(Math.abs(Number(first.storage.get('gpt_console_table_total_accounts')) - 1514.72) < 0.01);

  const reloaded = createResizableTable(
    'accounts',
    JSON.parse(first.storage.get('gpt_console_table_widths_accounts')),
    Number(first.storage.get('gpt_console_table_total_accounts')),
    {layoutVersion: true},
  );
  const restored = pixelWidths(reloaded.table);
  restored.slice(0, last).forEach((width, index) => assertPixels(width, migrated[index], `重载后第 ${index} 列`));
  assertPixels(restored[last], 108, '重载后的操作列');
});

test('已标记的新布局允许用户把操作列调到 600px，刷新后不会再次压缩', () => {
  const prefix = [36, 72, 160, 80, 84, 88, 72, 88, 88, 192, 72, 88, 72, 96];
  const pixels = prefix.concat(600);
  const total = pixels.reduce((sum, value) => sum + value, 0);
  const first = createResizableTable('accounts', pixels.map(value => value / total), total, {layoutVersion: true});
  const before = pixelWidths(first.table);
  const last = before.length - 1;
  assertPixels(before[last], 600);
  assert.equal(first.storage.get(first.layoutStorageKey), '2');

  const reloaded = createResizableTable(
    'accounts',
    JSON.parse(first.storage.get('gpt_console_table_widths_accounts')),
    total,
    {layoutVersion: true},
  );
  const restored = pixelWidths(reloaded.table);
  restored.slice(0, last).forEach((width, index) => assertPixels(width, before[index], `保留布局第 ${index} 列`));
  assertPixels(restored[last], 600, '保留布局的操作列');
});

test('未标记但末列不明显过宽的历史布局保持原比例', () => {
  const prefix = [36, 72, 160, 80, 84, 88, 72, 88, 88, 192, 72, 88, 72, 96];
  const prefixScale = 800 / prefix.reduce((sum, value) => sum + value, 0);
  const pixels = prefix.map(value => value * prefixScale).concat(200);
  const total = pixels.reduce((sum, value) => sum + value, 0);
  const saved = pixels.map(value => value / total);
  const table = createResizableTable('accounts', saved, total);
  const actual = pixelWidths(table.table);
  actual.forEach((width, index) => assertPixels(width, pixels[index], `保留历史布局第 ${index} 列`));
  assert.equal(table.storage.get('gpt_console_table_widths_accounts'), JSON.stringify(saved));
  assert.equal(table.storage.get(table.layoutStorageKey), '2');
});

test('账号列向左拖动保持整表宽度并把空间交给邻列；其他表保持相邻列拖动', () => {
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
  assert.equal(account.table.getBoundingClientRect().width, 1000);
  assertPixels(narrowed[1], 272);

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
  assert.equal(table.storage.get(table.layoutStorageKey), '2');
});

test('旧相邻拖动布局清理操作列残留空白，保留前面列宽并在刷新后稳定', () => {
  const saved = [0.03110207, 0.03987567, 0.13956959, 0.05410544, 0.05102565, 0.05344955, 0.04367788, 0.05344955, 0.04127298, 0.08696603, 0.04357332, 0.07112983, 0.05385829, 0.09039752, 0.14654664];
  const total = 1643.7813;
  const sum = saved.reduce((value, width) => value + width, 0);
  const original = saved.map(value => value / sum * total);
  const first = createResizableTable('accounts', saved, total, {layoutVersion: '1'});
  const migrated = pixelWidths(first.table);
  original.slice(0, -1).forEach((width, index) => assertPixels(migrated[index], width));
  assertPixels(migrated.at(-1), 108);
  assertPixels(first.table.getBoundingClientRect().width, total - original.at(-1) + 108);
  assert.ok(first.table.getBoundingClientRect().width < 1610, '内容可以放下时应消除横向溢出');
  assert.equal(first.storage.get(first.layoutStorageKey), '2');
  const reloaded = createResizableTable('accounts', JSON.parse(first.storage.get('gpt_console_table_widths_accounts')), Number(first.storage.get('gpt_console_table_total_accounts')), {layoutVersion: true});
  pixelWidths(reloaded.table).forEach((width, index) => assertPixels(width, migrated[index]));
});

test('旧布局中的紧凑末列升级时不被放大', () => {
  const pixels = [36, 72, 160, 80, 84, 88, 72, 88, 88, 192, 72, 88, 72, 96, 60];
  const total = pixels.reduce((sum, width) => sum + width, 0);
  const result = createResizableTable('accounts', pixels, total, {layoutVersion: '1'});
  pixelWidths(result.table).forEach((width, index) => assertPixels(width, pixels[index]));
  assert.equal(result.storage.get(result.layoutStorageKey), '2');
});

test('收窄创建列同步缩表且不扩大操作列，同次拖回原位可还原', () => {
  const pixels = [36, 72, 160, 80, 84, 88, 72, 88, 88, 192, 72, 88, 72, 148, 108];
  const total = pixels.reduce((sum, width) => sum + width, 0);
  const result = createResizableTable('accounts', pixels, total, {layoutVersion: true});
  const index = pixels.length - 2;
  result.headers[index].handle.onpointerdown({button: 0, clientX: 100, preventDefault() {}, stopPropagation() {}});
  result.listeners.get('pointermove')({clientX: 0});
  assertPixels(result.table.getBoundingClientRect().width, total - 100);
  const narrower = pixelWidths(result.table);
  pixels.slice(0, index).forEach((width, i) => assertPixels(narrower[i], width));
  assertPixels(narrower[index], 48);
  assertPixels(narrower.at(-1), 108);
  result.listeners.get('pointermove')({clientX: 100});
  pixelWidths(result.table).forEach((width, i) => assertPixels(width, pixels[i]));
  result.listeners.get('pointermove')({clientX: 0});
  result.listeners.get('pointerup')();
  const reloaded = createResizableTable('accounts', JSON.parse(result.storage.get('gpt_console_table_widths_accounts')), Number(result.storage.get('gpt_console_table_total_accounts')), {layoutVersion: true});
  pixelWidths(reloaded.table).forEach((width, i) => assertPixels(width, narrower[i]));
});
