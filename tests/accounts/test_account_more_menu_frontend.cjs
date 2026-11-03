const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');

const source = require('../frontend_script_sources.cjs').readAccountScripts();
function load(name, dependencies) {
  const context = vm.createContext(dependencies);
  const match = new RegExp(`function ${name}\\(`).exec(source);
  assert.ok(match, `缺少 ${name}`);
  vm.runInContext(source.slice(match.index, source.indexOf('\n}', match.index) + 2), context);
  return context[name];
}
function menuFixture({top, bottom, height = 740, width = 200, innerHeight = 720, innerWidth = 1280}) {
  const menu = {
    style: {},
    get offsetWidth() { return width; },
    get offsetHeight() { return Math.min(height, parseFloat(this.style.maxHeight) || height); },
  };
  const button = {getBoundingClientRect: () => ({top, bottom, right: 1200})};
  const wrap = {querySelector: selector => selector === '.acc-v2-more-btn' ? button : menu};
  const position = load('positionAccountsV2MoreMenu', {window: {innerHeight, innerWidth}});
  return {menu, wrap, position};
}

test('720高视口中较长菜单被限制在较宽裕一侧并可独立滚动', () => {
  const {menu, wrap, position} = menuFixture({top: 366, bottom: 394});
  position(wrap);
  const top = parseFloat(menu.style.top);
  const height = parseFloat(menu.style.maxHeight);
  assert.ok(top >= 8);
  assert.ok(top + height <= 712);
  assert.ok(height > 0 && height < 740);
  assert.equal(menu.style.overflowY, 'auto');
  assert.equal(menu.style.overscrollBehavior, 'contain');
  assert.equal(menu.style.boxSizing, 'border-box');
});

test('能完整容纳时保持按钮下方，靠近底部时向上展开', () => {
  for (const [top, bottom, expectedTop] of [[100, 128, 132], [650, 678, 466]]) {
    const fixture = menuFixture({top, bottom, height: 180});
    fixture.position(fixture.wrap);
    assert.equal(parseFloat(fixture.menu.style.top), expectedTop);
  }
});

test('再次打开时按自然高度测量，不沿用上一次较短的滚动高度', () => {
  const fixture = menuFixture({top: 100, bottom: 128, height: 740});
  fixture.menu.style.maxHeight = '40px';
  fixture.position(fixture.wrap);
  assert.ok(parseFloat(fixture.menu.style.maxHeight) > 40);
  assert.equal(parseFloat(fixture.menu.style.top), 132);
  assert.equal(parseFloat(fixture.menu.style.maxHeight), 580);
});

test('菜单内部滚动不关闭菜单，页面或账号表格滚动仍关闭', () => {
  let closed = 0;
  const onScroll = load('onAccountsMoreMenuScroll', {closeAccountsV2MoreMenus: () => { closed += 1; }});
  onScroll({target: {closest: selector => selector === '.accounts-table-v2 .acc-v2-more-menu' ? {} : null}});
  assert.equal(closed, 0);
  onScroll({target: {closest: () => null}});
  onScroll({target: {}});
  assert.equal(closed, 2);
  assert.match(source, /window\.addEventListener\('scroll', onAccountsMoreMenuScroll, true\)/);
});
