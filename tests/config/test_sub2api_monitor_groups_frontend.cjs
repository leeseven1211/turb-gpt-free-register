const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/config/page.js'), 'utf8');
const key = 'SUB2API_MONITOR_GROUP_IDS';

function createView(value = '') {
  const listeners = {};
  const root = {addEventListener(name, callback) { (listeners[name] ||= []).push(callback); }};
  const status = {textContent: ''};
  const options = {
    dataset: {}, checkboxes: [], writes: 0,
    get innerHTML() { return this.markup || ''; },
    set innerHTML(markup) {
      this.markup = markup;
      this.writes += 1;
      this.checkboxes = [...markup.matchAll(/data-sub2api-monitor-group-id="(.*?)"([^>]*)>/g)].map(([, id, attributes]) => ({
        dataset: {sub2apiMonitorGroupId: id}, checked: attributes.includes('checked'),
        closest() { return {classList: {toggle() {}}}; },
      }));
    },
    querySelectorAll() { return this.checkboxes; },
  };
  const attributes = {};
  const button = {disabled: false, textContent: '查询分组', setAttribute(name, value) { attributes[name] = value; }};
  const input = {
    value, dataset: {key}, type: 'text',
    closest(selector) {
      if (selector === '[data-key], [data-wait-seconds-key], [data-price-key]') return this;
      if (selector === '#tab-config') return root;
      return null;
    },
    dispatchEvent(event) { for (const callback of listeners[event.type] || []) callback({target: this}); },
  };
  const control = {
    setAttribute(name, value) { attributes[name] = value; },
    querySelector(selector) {
      if (selector.includes('data-sub2api-monitor-group-options')) return options;
      if (selector.includes('data-sub2api-monitor-groups-status')) return status;
      if (selector.includes('data-query-sub2api-groups')) return button;
      if (selector.includes('data-key') || selector.includes('cfg-')) return input;
      return null;
    },
  };
  const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  const context = {
    CONFIG: [{key, type: 'str', group: '定时任务', label: '异常巡检分组 ID', value}],
    Event: class { constructor(type) { this.type = type; } },
    document: {
      getElementById(id) { return id === `cfg-${key}` ? input : null; },
      querySelector() { return null; },
      querySelectorAll(selector) { return selector === '#tab-config [data-sub2api-monitor-groups]' ? [control] : []; },
    },
    $(selector) { return selector === '#tab-config' ? root : null; },
    window: {addEventListener() {}},
    esc: escape, attrEsc: escape, isPlaceholderEmpty: value => value == null || value === '',
    showToast() {},
  };
  vm.createContext(context);
  vm.runInContext(`${source}
    globalThis.view = {
      render: () => renderScheduledConfigSectionV2(CONFIG),
      query: () => querySub2ApiGroupsV2(),
      pending: CONFIG_PENDING_UPDATES,
      setPending: setPendingConfigValue,
      automation: querySub2ApiAutomationV2,
    };
  `, context);
  return {
    view: context.view, context, input, button, options, status, attributes,
    changeGroup(id, checked) {
      const checkbox = {dataset: {sub2apiMonitorGroupId: String(id)}, checked, closest(selector) { return selector === '[data-sub2api-monitor-group-id]' ? this : null; }};
      for (const callback of listeners.change || []) callback({target: checkbox});
    },
  };
}

test('定时任务仅有一个分组配置入口并提供查询及空选全部说明', () => {
  const {view} = createView('17');
  const markup = view.render();
  assert.equal((markup.match(/data-key="SUB2API_MONITOR_GROUP_IDS"/g) || []).length, 1);
  assert.match(markup, /id="cfg-SUB2API_MONITOR_GROUP_IDS"/);
  assert.match(markup, /data-query-sub2api-groups/);
  assert.match(markup, /使用已保存/);
  assert.match(markup, /不选.*全部/);
  assert.match(markup, /role="status" aria-live="polite"/);
});

test('查询只用已保存连接，显示名称和ID并保留未保存分组及旧ID', async () => {
  const ui = createView('17,99');
  ui.view.setPending('SUB2API_API_BASE', 'https://draft.example.test');
  ui.context.api = async (url, options) => {
    assert.equal(url, '/api/sub2api/groups');
    assert.equal(options, undefined);
    assert.equal(ui.button.disabled, true);
    assert.equal(ui.attributes['aria-busy'], 'true');
    return {ok: true, groups: [{id: 17, name: 'Plus'}, {id: 18, name: '<Free>'}]};
  };
  await ui.view.query();
  assert.match(ui.options.innerHTML, /Plus（ID 17）/);
  assert.match(ui.options.innerHTML, /&lt;Free&gt;（ID 18）/);
  assert.match(ui.options.innerHTML, /data-sub2api-monitor-group-id="17"[^>]*checked/);
  assert.match(ui.options.innerHTML, /data-sub2api-monitor-group-id="99"[^>]*checked/);
  assert.equal(ui.input.value, '17,99');
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.attributes['aria-busy'], 'false');
  assert.equal(ui.view.pending.SUB2API_API_BASE, 'https://draft.example.test');
  assert.equal(Object.hasOwn(ui.view.pending, key), false);
});

test('多选与手填共享唯一配置值并沿现有草稿保存，清空表示全部', async () => {
  const ui = createView('17');
  ui.context.api = async () => ({ok: true, groups: [{id: 17, name: 'Plus'}, {id: 18, name: 'Free'}]});
  await ui.view.query();
  const previousWrites = ui.options.writes;
  ui.changeGroup(18, true);
  assert.equal(ui.input.value, '17,18');
  assert.equal(ui.view.pending[key], '17,18');
  assert.equal(ui.options.checkboxes.find(checkbox => checkbox.dataset.sub2apiMonitorGroupId === '18').checked, true);
  assert.equal(ui.options.writes, previousWrites, '勾选已知分组时保留原复选框节点及焦点');
  ui.input.value = '18,99';
  ui.input.dispatchEvent(new ui.context.Event('input'));
  assert.equal(ui.view.pending[key], '18,99');
  assert.match(ui.options.innerHTML, /data-sub2api-monitor-group-id="99"[^>]*checked/);
  ui.changeGroup(18, false);
  ui.changeGroup(99, false);
  assert.equal(ui.input.value, '');
  assert.equal(ui.view.pending[key], '');
  assert.match(ui.status.textContent, /全部/);
});

test('查询失败保留已查询选项及分组草稿，恢复查询按钮', async () => {
  const ui = createView('17');
  ui.context.api = async () => ({ok: true, groups: [{id: 17, name: 'Plus'}]});
  await ui.view.query();
  ui.input.value = '17,99';
  ui.input.dispatchEvent(new ui.context.Event('input'));
  ui.context.api = async () => { throw new Error('Sub2API 连接超时'); };
  await ui.view.query();
  assert.equal(ui.input.value, '17,99');
  assert.equal(ui.view.pending[key], '17,99');
  assert.match(ui.options.innerHTML, /Plus（ID 17）/);
  assert.match(ui.options.innerHTML, /data-sub2api-monitor-group-id="99"[^>]*checked/);
  assert.match(ui.status.textContent, /查询分组失败.*Sub2API 连接超时/);
  assert.equal(ui.button.disabled, false);
});

test('中文逗号或空白分隔草稿可查询勾选并彻底取消指定分组', async () => {
  for (const value of ['17，18', '17 18', '17\n18', ' 17 ， 18\t17 ']) {
    const ui = createView();
    ui.input.value = value;
    ui.input.dispatchEvent(new ui.context.Event('input'));
    ui.context.api = async () => ({ok: true, groups: [{id: 17, name: 'Plus'}, {id: 18, name: 'Free'}]});
    await ui.view.query();
    assert.deepEqual(ui.options.checkboxes.filter(checkbox => checkbox.checked).map(checkbox => checkbox.dataset.sub2apiMonitorGroupId), ['17', '18'], value);
    assert.equal(ui.options.checkboxes.length, 2, '不生成整串未知分组 ID');
    ui.changeGroup(17, false);
    assert.equal(ui.input.value, '18', value);
    assert.equal(ui.view.pending[key], '18', value);
    ui.changeGroup(17, true);
    ui.changeGroup(17, false);
    assert.equal(ui.view.pending[key], '18', '重新勾选再取消后不保留旧分组');
  }
});

test('服务集成查看状态展示已保存巡检分组或全部范围', async () => {
  const {view, context} = createView();
  const status = {textContent: ''};
  const panel = {querySelector() { return status; }, querySelectorAll() { return []; }};
  const button = {dataset: {sub2apiAutomation: 'status'}, closest() { return panel; }};
  context.api = async () => ({ok: true, monitor: {enabled: true, group_ids: [17, 18]}});
  await view.automation(button);
  assert.match(status.textContent, /巡检范围.*17.*18/);
  context.api = async () => ({ok: true, monitor: {enabled: true, group_ids: []}});
  await view.automation(button);
  assert.match(status.textContent, /巡检范围.*全部分组/);
});
