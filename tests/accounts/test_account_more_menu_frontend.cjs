const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {createVueHarness} = require('../frontend_vue_loader.cjs');

// Execute the real AccountsTable and Reka Popover. Only browser layout is supplied
// by this fixture: jsdom has no layout engine. Placement is calculated by Reka.
const vue = createVueHarness();
const win = vue.document.defaultView;
const observerBefore = Object.getOwnPropertyDescriptor(globalThis, 'IntersectionObserver');
const nodeFilterBefore = Object.getOwnPropertyDescriptor(globalThis, 'NodeFilter');
const inputBefore = Object.getOwnPropertyDescriptor(globalThis, 'HTMLInputElement');
globalThis.IntersectionObserver = class {observe() {} disconnect() {}};
globalThis.NodeFilter = win.NodeFilter;
globalThis.HTMLInputElement = win.HTMLInputElement;
const AccountsTable = vue.load('src/features/accounts/AccountsTable.vue').default;
const queryContext = {window: {}, URLSearchParams};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../webui/static/js/shared/account-query.js'), 'utf8'), queryContext);
const css = vue.document.createElement('style');
css.textContent = fs.readFileSync(path.join(__dirname, '../../frontend/src/features/accounts/accounts.css'), 'utf8');
vue.document.head.append(css);
const geometry = {top: 100, bottom: 128, right: 1200, width: 200, height: 180, innerWidth: 1280, innerHeight: 720};
const rect = (x, y, width, height) => ({x, y, left: x, top: y, right: x + width, bottom: y + height, width, height, toJSON() {return this;}});
const nativeRect = win.Element.prototype.getBoundingClientRect;
const nativeWidth = Object.getOwnPropertyDescriptor(win.HTMLElement.prototype, 'offsetWidth');
const nativeHeight = Object.getOwnPropertyDescriptor(win.HTMLElement.prototype, 'offsetHeight');
function popup(element) {return element.matches('.ac-row-menu,[data-reka-popper-content-wrapper]');}
function popupHeight(element) {
  const wrapper = element.matches('[data-reka-popper-content-wrapper]') ? element : element.parentElement;
  const available = parseFloat(wrapper?.style.getPropertyValue('--reka-popper-available-height'));
  return Number.isFinite(available) ? Math.min(geometry.height, Math.max(0, available)) : geometry.height;
}
win.Element.prototype.getBoundingClientRect = function () {
  if (this.matches('.acc-v2-more-btn')) return rect(geometry.right - 52, geometry.top, 52, geometry.bottom - geometry.top);
  if (popup(this)) return rect(0, 0, geometry.width, popupHeight(this));
  return nativeRect.call(this);
};
Object.defineProperty(win.HTMLElement.prototype, 'offsetWidth', {configurable: true, get() {return popup(this) ? geometry.width : this.matches('.acc-v2-more-btn') ? 52 : 0;}});
Object.defineProperty(win.HTMLElement.prototype, 'offsetHeight', {configurable: true, get() {return popup(this) ? popupHeight(this) : this.matches('.acc-v2-more-btn') ? geometry.bottom - geometry.top : 0;}});
for (const [target, key, value] of [[win, 'innerWidth', () => geometry.innerWidth], [win, 'innerHeight', () => geometry.innerHeight], [vue.document.documentElement, 'clientWidth', () => geometry.innerWidth], [vue.document.documentElement, 'clientHeight', () => geometry.innerHeight]]) Object.defineProperty(target, key, {configurable: true, get: value});
const presentation = {
  cell() {return '';},
  menu(row) {return `<button type="button" data-account-email-invalid="${row.id}" data-invalid="1">标记邮箱失效</button><button type="button" disabled>不可用操作</button><button type="button" data-account-delete="${row.id}">删除账号</button>`;},
  emailInvalidBadge() {return '';}, registrationDriverLabel() {return '协议';}, facetLabel(_group, value) {return value;}, mobileSummary() {return '来源 · 套餐';}, rowTone() {return 'ok';},
};
function fixture(options = {}) {
  Object.assign(geometry, {top: 100, bottom: 128, right: 1200, width: 200, height: 180, innerWidth: 1280, innerHeight: 720}, options);
  const wrapper = vue.mount(AccountsTable, {props: {items: [{id: 7, email: 'seven@example.test'}], selected: new Set(), query: queryContext.window.AccountQuery.normalize(), facets: {}, presentation, loading: false, error: '', invalidSearch: false, stale: false, visible: true, pageSelected: false, pageIndeterminate: false, openFilter: null}});
  return {wrapper, trigger: wrapper.get('button[aria-label="更多账号操作"]').element};
}
async function settle() {for (let i = 0; i < 20; i++) await vue.nextTick(); await new Promise(resolve => setTimeout(resolve, 20));}
async function open(trigger) {trigger.focus(); trigger.click(); await settle(); assert.equal(trigger.getAttribute('aria-expanded'), 'true'); assert.ok(menu());}
function menu() {return vue.document.querySelector('.ac-row-menu');}
function position() {
  const element = menu(), wrapper = element.parentElement;
  const match = /translate\(([-\d.]+)px, ([-\d.]+)px\)/.exec(wrapper.style.transform);
  assert.ok(match, '真实 Reka popper 应计算 translate 位置');
  return {left: +match[1], top: +match[2], available: parseFloat(wrapper.style.getPropertyValue('--reka-popper-available-height')), height: popupHeight(element), side: element.dataset.side};
}
test.afterEach(async () => {vue.cleanup(); await settle();});
test.after(() => {
  win.Element.prototype.getBoundingClientRect = nativeRect;
  Object.defineProperty(win.HTMLElement.prototype, 'offsetWidth', nativeWidth);
  Object.defineProperty(win.HTMLElement.prototype, 'offsetHeight', nativeHeight);
  vue.close();
  if (observerBefore) Object.defineProperty(globalThis, 'IntersectionObserver', observerBefore); else delete globalThis.IntersectionObserver;
  if (nodeFilterBefore) Object.defineProperty(globalThis, 'NodeFilter', nodeFilterBefore); else delete globalThis.NodeFilter;
  if (inputBefore) Object.defineProperty(globalThis, 'HTMLInputElement', inputBefore); else delete globalThis.HTMLInputElement;
});

test('720 高视口中长菜单留在安全边距内并可独立滚动', async () => {
  const {trigger} = fixture({top: 366, bottom: 394, height: 740});
  await open(trigger);
  const placed = position(), style = win.getComputedStyle(menu());
  assert.ok(placed.top >= 8, JSON.stringify(placed));
  assert.ok(placed.top + placed.height <= 712, JSON.stringify(placed));
  assert.ok(placed.height > 0 && placed.height < 740);
  assert.equal(style.overflow, 'auto');
  assert.equal(style.overscrollBehavior, 'contain');
  assert.equal(style.boxSizing, 'border-box');
});

test('能完整容纳时在按钮下方，靠近底部时向上展开', async () => {
  for (const [top, bottom, expectedTop, side] of [[100, 128, 132, 'bottom'], [650, 678, 466, 'top']]) {
    const {trigger} = fixture({top, bottom, height: 180});
    await open(trigger);
    const placed = position();
    assert.equal(placed.top, expectedTop); assert.equal(placed.side, side);
    vue.cleanup(); await settle();
  }
});

test('重新打开按自然高度重新布局，不沿用上次受限高度', async () => {
  const {trigger} = fixture({top: 366, bottom: 394, height: 740});
  await open(trigger); const first = position().height;
  trigger.click(); await settle(); assert.equal(menu(), null);
  Object.assign(geometry, {top: 100, bottom: 128});
  await open(trigger); const reopened = position();
  assert.ok(reopened.height > first); assert.equal(reopened.top, 132); assert.equal(reopened.height, 580);
});

test('窄视口菜单横向保留 8px 边距并使用既有宽度上限', async () => {
  const {trigger} = fixture({right: 330, width: 200, innerWidth: 360});
  await open(trigger); const placed = position();
  assert.ok(placed.left >= 8); assert.ok(placed.left + geometry.width <= 352);
  assert.equal(win.getComputedStyle(menu()).maxWidth, 'min(320px,calc(100vw - 16px))');
});

test('菜单及内部滚动不关闭，页面、表格和 window 滚动均关闭', async () => {
  const {wrapper, trigger} = fixture();
  await open(trigger);
  for (const target of [menu(), menu().querySelector('.ac-menu-content'), menu().querySelector('button')]) {
    target.dispatchEvent(new win.Event('scroll')); await settle(); assert.ok(menu());
  }
  const page = vue.document.createElement('main'); vue.document.body.append(page);
  for (const target of [page, wrapper.element, win, vue.document]) {
    target.dispatchEvent(new win.Event('scroll')); await settle(); assert.equal(menu(), null, '外部滚动必须关闭菜单');
    await open(trigger);
  }
});

test('键盘 Tab 在可用菜单项间循环，Escape 关闭后焦点返回原触发按钮', async () => {
  const {trigger} = fixture(); await open(trigger);
  assert.equal(vue.document.activeElement, trigger, '打开后保留原触发焦点');
  const buttons = menu().querySelectorAll('button:not(:disabled)');
  buttons[buttons.length - 1].focus();
  buttons[buttons.length - 1].dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true})); await settle();
  assert.equal(vue.document.activeElement, buttons[0]);
  buttons[0].dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Tab', shiftKey: true, bubbles: true, cancelable: true})); await settle();
  assert.equal(vue.document.activeElement, buttons[buttons.length - 1]);
  vue.document.activeElement.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true})); await settle();
  assert.equal(menu(), null); assert.equal(vue.document.activeElement, trigger); assert.equal(trigger.getAttribute('aria-expanded'), 'false');
});

test('动作只发一次原账号和按钮，卸载释放 window 捕获滚动监听', async () => {
  const add = win.addEventListener, remove = win.removeEventListener, attached = [], removed = [];
  win.addEventListener = function (...args) {attached.push(args); return add.apply(this, args);};
  win.removeEventListener = function (...args) {removed.push(args); return remove.apply(this, args);};
  try {
    const {wrapper, trigger} = fixture(); await open(trigger); const action = menu().querySelector('[data-account-delete]'); action.click(); await settle();
    assert.equal(menu(), null); assert.equal(wrapper.emitted('action').length, 1); assert.deepEqual(wrapper.emitted('action')[0].slice(0, 2), ['account-delete', '7']); assert.equal(wrapper.emitted('action')[0][2], action);
    wrapper.unmount(); await settle();
    const scrollListeners = attached.filter(([name, , capture]) => name === 'scroll' && capture === true);
    assert.equal(scrollListeners.length, 1);
    assert.ok(removed.some(([name, fn, capture]) => name === 'scroll' && fn === scrollListeners[0][1] && capture === true));
  } finally {win.addEventListener = add; win.removeEventListener = remove;}
});

test('兼容 closeMenu 门面关闭真实 Portal，并可重新打开', async () => {
  const {wrapper, trigger} = fixture(); await open(trigger);
  wrapper.vm.closeMenu(); await settle(); assert.equal(menu(), null);
  await open(trigger); assert.ok(menu());
});
