const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, '../../webui/static/js/pages/accounts/page.js'), 'utf8');
const template = fs.readFileSync(path.join(__dirname, '../../webui/templates/index.html'), 'utf8');
const source = page.slice(page.indexOf('// ---------- 常用账号操作 ----------'), page.indexOf('function updateAccountSelectionUi('));
const defaults = ['btnCheckSelectedLiveV2', 'btnCheckSelectedPlansV2', 'btnRefreshSelectedTokenV2', 'btnExtractSelectedLinksV2', 'btnAddTwofaSelectedAccountsV2'];
const c2aId = 'btnReimportSelectedC2aV2';
const pageActions = [
  ['btnBulkFromAccountFilters', 'BulkTasks.fromAccounts(false)'],
  ['btnBulkFromSelectedAccounts', 'BulkTasks.fromAccounts(true)'],
  ['btnAccountInspection', 'openAccountInspectionStart()'],
  ['btnAccountInspectionHistory', 'openAccountInspectionHistory()'],
  ['btnDeleteDeactivatedAccounts', 'deleteDeactivatedAccounts()'],
];

function setup({saved = null, storageBlocked = false} = {}) {
  const elements = new Map();
  const frames = [];
  const storage = {value: saved};
  class Node {
    constructor(id = '') {
      this.id = id;
      this.children = [];
      this.listeners = {};
      this.parentNode = null;
      this.disabled = false;
      this.attributes = {};
      this.classes = new Set();
      this.classList = {contains: value => this.classes.has(value)};
      if (id) elements.set(id, this);
    }
    get nextSibling() { return this.parentNode?.children[this.parentNode.children.indexOf(this) + 1] || null; }
    appendChild(child) { return this.insertBefore(child, null); }
    insertBefore(child, reference) {
      if (child === reference) return child;
      if (child.parentNode) child.parentNode.children.splice(child.parentNode.children.indexOf(child), 1);
      const index = reference ? this.children.indexOf(reference) : this.children.length;
      assert.ok(index >= 0);
      this.children.splice(index, 0, child);
      child.parentNode = this;
      return child;
    }
    contains(child) { return this === child || this.children.some(node => node.contains(child)); }
    addEventListener(name, handler) { this.listeners[name] = handler; }
    getAttribute(name) { return this.attributes[name] ?? null; }
    closest(selector) { return selector === 'button[id]' && this.id.startsWith('btn') ? this : null; }
    querySelectorAll() { return this.children.flatMap(child => [child, ...child.querySelectorAll()]).filter(child => child.id.startsWith('btn')); }
  }
  const body = new Node('body');
  const toolbar = body.appendChild(new Node('accountsToolbarV2'));
  const quick = toolbar.appendChild(new Node('accountsQuickActionsV2'));
  const more = toolbar.appendChild(new Node('accountsMoreActionsV2'));
  const group = more.appendChild(new Node('group'));
  const buttons = [...defaults, c2aId, 'btnCopySelectedEmailsV2', ...pageActions.map(([id]) => id)].map(id => group.appendChild(new Node(id)));
  const document = {activeElement: body, dialogOpen: false, querySelector() { return this.dialogOpen ? {} : null; }, createComment: () => new Node(), addEventListener() {}};
  const context = vm.createContext({
    $, document, window: {addEventListener() {}},
    localStorage: {
      getItem() { if (storageBlocked) throw new Error('存储不可用'); return storage.value; },
      setItem(key, value) { if (storageBlocked) throw new Error('存储不可用'); storage.value = value; },
    },
    requestAnimationFrame: callback => frames.push(callback),
  });
  function $(selector) { return elements.get(selector.slice(1)); }
  vm.runInContext(source, context);
  context.initAccountQuickActions();
  return {
    context, document, toolbar, quick, more, group, buttons, elements, storage,
    ids: () => quick.children.map(button => button.id),
    flush: () => frames.splice(0).forEach(callback => callback()),
  };
}

test('无使用记录时恰好展示五个默认操作，C2A 留在批量操作且节点不重复', () => {
  const view = setup();
  assert.deepEqual(view.ids(), defaults);
  assert.equal(view.group.contains(view.elements.get(c2aId)), true);
  const rendered = view.toolbar.querySelectorAll().map(node => node.id);
  assert.equal(rendered.length, 12);
  assert.equal(new Set(rendered).size, 12);
});

test('批量操作入口位于常用操作前，未选择账号时仍可展开查看', () => {
  const toolbar = template.slice(template.indexOf('id="accountsToolbarV2"'), template.indexOf('<div class="list-toolbar-utilities">', template.indexOf('id="accountsToolbarV2"')));
  const entry = toolbar.match(/<details\b[^>]*id="accountsMoreActionsV2"[^>]*>/)?.[0];
  assert.ok(entry);
  assert.doesNotMatch(entry, /selection-only|hidden|disabled/);
  assert.match(toolbar, /id="accountsMoreActionsV2">\s*<summary>批量操作<\/summary>/);
  assert.ok(toolbar.indexOf('id="accountsMoreActionsV2"') < toolbar.indexOf('id="accountsQuickActionsV2"'));
});

test('一次入口点击累计一次，退出菜单、弹窗和工具栏焦点后才更新前五', () => {
  const view = setup();
  const button = view.elements.get(c2aId);
  view.more.open = true;
  view.document.activeElement = button;
  view.toolbar.listeners.click({target: button});
  view.flush();
  assert.deepEqual(view.ids(), defaults);
  assert.equal(JSON.parse(view.storage.value)[c2aId], 1);
  view.more.open = false;
  view.document.dialogOpen = true;
  view.context.refreshAccountQuickActions();
  assert.deepEqual(view.ids(), defaults);
  view.document.dialogOpen = false;
  view.context.refreshAccountQuickActions();
  assert.deepEqual(view.ids(), defaults);
  view.document.activeElement = null;
  view.context.refreshAccountQuickActions();
  assert.deepEqual(view.ids(), [c2aId, ...defaults.slice(0, 4)]);
  assert.equal(view.group.contains(view.elements.get(defaults[4])), true);
  assert.equal(view.toolbar.querySelectorAll().length, 12);
  assert.deepEqual(setup({saved: view.storage.value}).ids(), view.ids());
});

test('未选择或缺少能力配置的按钮不增加使用次数，存储仅接受有效白名单计数', () => {
  const view = setup({saved: JSON.stringify({[c2aId]: -5, [defaults[0]]: 2, unknown: 900, [defaults[1]]: '100'})});
  const button = view.elements.get(c2aId);
  button.disabled = true;
  view.context.recordAccountActionUse(button);
  button.disabled = false;
  button.classes.add('feature-unavailable');
  view.context.recordAccountActionUse(button);
  button.classes.clear();
  button.attributes['aria-disabled'] = 'true';
  view.context.recordAccountActionUse(button);
  assert.equal(JSON.parse(view.storage.value)[c2aId], -5);
  delete button.attributes['aria-disabled'];
  view.context.recordAccountActionUse(button);
  const saved = JSON.parse(view.storage.value);
  assert.equal(saved[c2aId], 1);
  assert.equal(saved[defaults[0]], 2);
  assert.equal(saved[defaults[1]], 0);
  assert.equal('unknown' in saved, false);
});

test('浏览器存储不可用时仍可操作并在当前页面累计排序', () => {
  const view = setup({storageBlocked: true});
  const button = view.elements.get(c2aId);
  view.context.recordAccountActionUse(button);
  view.context.recordAccountActionUse(button);
  view.flush();
  assert.equal(view.ids()[0], c2aId);
  assert.equal(view.context.accountActionUsageCounts([c2aId])[c2aId], 2);
});

test('页面级动作也按次数进入五个快捷位置，保留单一节点和原点击入口', () => {
  const toolbar = template.slice(template.indexOf('id="accountsToolbarV2"'), template.indexOf('<div class="list-toolbar-utilities">', template.indexOf('id="accountsToolbarV2"')));
  const more = toolbar.match(/<details\b[\s\S]*?<\/details>/)[0];
  assert.doesNotMatch(toolbar.replace(more, ''), /<button\b/);
  for (const [id, handler] of pageActions) {
    const buttonTag = more.match(new RegExp(`<button[^>]*id="${id}"[^>]*>`))?.[0];
    assert.ok(buttonTag, `${id} 在更多操作内`);
    assert.ok(buttonTag.includes(`onclick="${handler}"`));
    assert.doesNotMatch(buttonTag, /\bdisabled\b/);
    assert.equal(Array.from(template.matchAll(new RegExp(`id="${id}"`, 'g'))).length, 1);
  }
  const view = setup();
  const history = view.elements.get('btnAccountInspectionHistory');
  view.context.recordAccountActionUse(history);
  view.flush();
  assert.equal(view.ids().length, 5);
  assert.equal(view.ids()[0], history.id);
  assert.equal(view.quick.children[0], history);
  assert.equal(history.disabled, false);
  assert.equal(view.toolbar.querySelectorAll().length, 12);
});
