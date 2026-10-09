const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/accounts.js'), 'utf8');
const start = source.indexOf('function scrollAccountTaskDialogFromWheel(');
assert.ok(start >= 0, '任务详情应提供标题和步骤卡片的滚轮路由');
const nextFunction = source.indexOf('\nfunction ', start + 1);
const wheelFunction = source.slice(start, nextFunction === -1 ? undefined : nextFunction);

function element(parentElement = null) {
  return {
    parentElement,
    contains(target) {
      for (let current = target; current; current = current.parentElement) {
        if (current === this) return true;
      }
      return false;
    },
  };
}

function scroller(parentElement = null, height = 400, contentHeight = 1600) {
  let position = 0;
  const result = Object.assign(element(parentElement), {
    clientHeight: height,
    scrollHeight: contentHeight,
  });
  Object.defineProperty(result, 'scrollTop', {
    get() { return position; },
    set(value) { position = Math.max(0, Math.min(value, this.scrollHeight - this.clientHeight)); },
  });
  return result;
}

function createView({stepDialogOpen = false, emptyMain = false, emptyStep = false} = {}) {
  const panel = element();
  const main = scroller(panel, 400, emptyMain ? 400 : 1600);
  const overlay = element(panel);
  overlay.classList = {contains: value => value === 'hidden' && !stepDialogOpen};
  const step = scroller(overlay, 300, emptyStep ? 300 : 1800);
  const card = element(panel);
  const header = element(overlay);
  const selectors = new Map([
    ['#accountTaskLogPanel', panel],
    ['#accountTaskLogPanel .account-task-detail-content', main],
    ['.account-task-detail-content', main],
    ['#accountTaskStepDetailOverlay', overlay],
    ['#accountTaskStepDetailContent', step],
  ]);
  panel.querySelector = selector => selectors.get(selector) || null;
  let tooltipHides = 0;
  const sandbox = {
    $: selector => selectors.get(selector) || null,
    document: {querySelector: selector => selectors.get(selector) || null},
    getComputedStyle: () => ({overflowY: 'auto'}),
    WheelEvent: {DOM_DELTA_PIXEL: 0, DOM_DELTA_LINE: 1, DOM_DELTA_PAGE: 2},
    hideAccountTaskStepTooltip() { tooltipHides += 1; },
  };
  vm.runInNewContext(wheelFunction, sandbox);
  return {panel, main, overlay, step, card, header, route: sandbox.scrollAccountTaskDialogFromWheel, tooltipHides: () => tooltipHides};
}

function wheel(target, options = {}) {
  return {
    target,
    deltaY: 120,
    deltaX: 0,
    deltaMode: 0,
    defaultPrevented: false,
    ctrlKey: false,
    shiftKey: false,
    prevented: 0,
    preventDefault() { this.prevented += 1; this.defaultPrevented = true; },
    ...options,
  };
}

test('点击步骤卡片后原位置滚轮继续滚动主正文并收起浮窗', () => {
  const view = createView();
  const event = wheel(view.card);
  view.route(event);
  assert.equal(view.main.scrollTop, 120);
  assert.equal(view.step.scrollTop, 0);
  assert.equal(event.prevented, 1);
  assert.equal(view.tooltipHides(), 1);
});

test('步骤弹窗标题滚轮只滚动当前弹窗正文', () => {
  const view = createView({stepDialogOpen: true});
  view.main.scrollTop = 200;
  const event = wheel(view.header);
  view.route(event);
  assert.equal(view.step.scrollTop, 120);
  assert.equal(view.main.scrollTop, 200);
  assert.equal(event.prevented, 1);
});

test('主正文和其内层 pre 保留原生滚动', () => {
  const view = createView();
  for (const target of [view.main, element(view.main)]) {
    const event = wheel(target);
    view.route(event);
    assert.equal(event.prevented, 0);
    assert.equal(view.main.scrollTop, 0);
  }
  assert.equal(view.tooltipHides(), 0);
});

test('步骤正文和其内层 pre 保留原生滚动且不影响主正文', () => {
  const view = createView({stepDialogOpen: true});
  for (const target of [view.step, element(view.step)]) {
    const event = wheel(target);
    view.route(event);
    assert.equal(event.prevented, 0);
    assert.equal(view.main.scrollTop, 0);
    assert.equal(view.step.scrollTop, 0);
  }
});

test('缩放、水平滚动、已处理事件不被滚轮路由接管', () => {
  const view = createView();
  for (const options of [
    {ctrlKey: true},
    {shiftKey: true},
    {deltaY: 0, deltaX: 120},
    {defaultPrevented: true},
  ]) {
    const event = wheel(view.card, options);
    view.route(event);
    assert.equal(event.prevented, 0);
    assert.equal(view.main.scrollTop, 0);
  }
  assert.equal(view.tooltipHides(), 0);
});

test('按行的滚轮增量换算为像素并支持反向滚动', () => {
  const view = createView();
  view.main.scrollTop = 200;
  view.route(wheel(view.card, {deltaY: -3, deltaMode: 1}));
  assert.equal(view.main.scrollTop, 152);
});

test('按页的滚轮增量使用当前弹窗正文高度', () => {
  const view = createView({stepDialogOpen: true});
  view.route(wheel(view.header, {deltaY: 2, deltaMode: 2}));
  assert.equal(view.step.scrollTop, 600);
  assert.equal(view.main.scrollTop, 0);
});

test('主正文没有溢出时不拦截滚轮', () => {
  const view = createView({emptyMain: true});
  const event = wheel(view.card);
  view.route(event);
  assert.equal(view.main.scrollTop, 0);
  assert.equal(event.prevented, 0);
  assert.equal(view.tooltipHides(), 0);
});

test('当前步骤正文没有溢出时不会改滚背景主正文', () => {
  const view = createView({stepDialogOpen: true, emptyStep: true});
  view.main.scrollTop = 200;
  const event = wheel(view.header);
  view.route(event);
  assert.equal(view.step.scrollTop, 0);
  assert.equal(view.main.scrollTop, 200);
  assert.equal(event.prevented, 0);
});
