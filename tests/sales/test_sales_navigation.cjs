const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../webui/static/js/shared/common.js'), 'utf8');
function fixture() {
  const calls = [], nodes = new Map(), saved = new Map();
  function node(id) {
    if (!nodes.has(id)) {
      const classes = new Set();
      nodes.set(id, {dataset: {}, classList: {toggle(name, value) {value ? classes.add(name) : classes.delete(name);},
        contains: name => classes.has(name)}});
    }
    return nodes.get(id);
  }
  node('tab-accounts').dataset.moduleView = 'active';
  const context = {document: {getElementById: node, querySelectorAll: () => []}, window: null,
    $: selector => node(selector.slice(1)), localStorage: {setItem:(key,value)=>saved.set(key,value),getItem:key=>saved.get(key)||null},
    ACTIVE_TAB: 'accounts', SHOW_ARCHIVED_ACCOUNTS: false,
    closePageDialogsForNavigation: () => calls.push(['close']), closeMobileSidebar() {},
    recordNavigationHistory() {}, updateNavigationBackButton() {},
    applyAccountsArchivedFilter: value => calls.push(['archive', value]),
    SalesPage: {setVisible: value => calls.push(['sales', value])},
    AccountsPage: {setVisible: value => calls.push(['accounts', value])}};
  context.window = context;
  const start = source.indexOf('const MODULE_VIEW_META =');
  const end = source.indexOf("$$('[data-module-subnav]').forEach", start);
  assert.ok(start >= 0 && end > start);
  vm.runInNewContext(source.slice(start, end), context);
  return {context, node, calls, saved};
}
test('进入贩卖区切换面板但不改变原账号归档范围', () => {
  const {context, node, calls} = fixture();
  context.setModuleView('accounts', 'sales');
  assert.equal(node('tab-accounts').dataset.moduleView, 'sales');
  assert.equal(node('salesPanel').classList.contains('hidden'), false);
  assert.equal(node('accountsPanelV2').classList.contains('hidden'), true);
  assert.deepEqual(calls.filter(call => call[0] === 'archive'), []);
  assert.deepEqual(calls.filter(call => call[0] === 'sales'), [['sales', true]]);
  assert.deepEqual(calls.filter(call => call[0] === 'accounts'), [['accounts', false]]);
});
test('从贩卖区进入归档账号恢复账号面板并通知销售页隐藏', () => {
  const {context, node, calls} = fixture();
  context.setModuleView('accounts', 'sales');
  context.setModuleView('accounts', 'archived');
  assert.equal(node('salesPanel').classList.contains('hidden'), true);
  assert.equal(node('accountsPanelV2').classList.contains('hidden'), false);
  assert.deepEqual(calls.filter(call => call[0] === 'archive'), [['archive', true]]);
  assert.deepEqual(calls.filter(call => call[0] === 'sales').at(-1), ['sales', false]);
});
test('活跃、Team 与归档视图分别同步账号范围，贩卖区保留原范围', () => {
  const {context,node,calls} = fixture();
  context.AccountsPage.setAccountView = view => calls.push(['scope',view]);
  for (const view of ['active','team','archived','sales']) context.setModuleView('accounts',view);
  assert.deepEqual(calls.filter(call=>call[0]==='scope'),[['scope','active'],['scope','team'],['scope','archived']]);
  assert.equal(context.SHOW_ARCHIVED_ACCOUNTS,true);
  assert.equal(node('salesPanel').classList.contains('hidden'),false);
  assert.equal(node('accountsPanelV2').classList.contains('hidden'),true);
  assert.deepEqual(calls.filter(call=>call[0]==='accounts').at(-1),['accounts',false]);
});

function block(from,to) {
  const start=source.indexOf(from),end=to?source.indexOf(to,start+from.length):source.length;
  assert.ok(start>=0&&end>start);
  return source.slice(start,end);
}
test('销售历史恢复不会将原 Team 账号范围重置为活跃范围', () => {
  const {context,node,calls}=fixture();
  context.AccountsPage.setAccountView=view=>calls.push(['scope',view]);
  context.ACTIVE_TAB='accounts';
  node('tab-accounts').dataset.moduleView='team';
  context.activateTab=tab=>calls.push(['activate',tab]);
  vm.runInNewContext([
    "const NAV_ALLOWED_TABS=['accounts','overview'];",
    block('function navigationModuleForTab(','function currentNavigationState('),
    block('function applyNavigationState(','function initializeNavigationHistory('),
  ].join('\n'),context);
  context.applyNavigationState({tab:'accounts',view:'sales'});
  assert.equal(node('tab-accounts').dataset.moduleView,'sales');
  assert.deepEqual(calls.filter(call=>call[0]==='scope'),[]);
  assert.deepEqual(calls.filter(call=>call[0]==='activate'),[['activate','accounts']]);
});
test('恢复已保存销售菜单不会调用账号范围入口', () => {
  const {context,node,calls,saved}=fixture();
  context.AccountsPage.setAccountView=view=>calls.push(['scope',view]);
  saved.set('gpt_console_module_view_accounts','sales');
  context.SHOW_ARCHIVED_ACCOUNTS=true;
  vm.runInNewContext(block('function restoreModuleViewState()'),context);
  context.restoreModuleViewState();
  assert.equal(node('tab-accounts').dataset.moduleView,'sales');
  assert.equal(context.SHOW_ARCHIVED_ACCOUNTS,true);
  assert.deepEqual(calls.filter(call=>call[0]==='scope'),[]);
});
test('从其他模块点击隐藏的销售子菜单不会预先更改账号查询', () => {
  const {context,node,calls}=fixture();
  context.AccountsPage.setAccountView=view=>calls.push(['scope',view]);
  const nav={dataset:{moduleSubnav:'accounts'},querySelectorAll:()=>[],addEventListener(_name,handler){this.click=handler;}};
  context.$$=()=>[nav];
  context.activateTab=tab=>calls.push(['activate',tab]);
  node('tab-accounts').classList.toggle('hidden',true);
  context.SHOW_ARCHIVED_ACCOUNTS=true;
  vm.runInNewContext(block("$$('[data-module-subnav]').forEach",'function restoreModuleViewState()'),context);
  nav.click({detail:0,target:{closest:()=>({dataset:{view:'sales'}})}});
  assert.equal(node('tab-accounts').dataset.moduleView,'sales');
  assert.equal(context.SHOW_ARCHIVED_ACCOUNTS,true);
  assert.deepEqual(calls.filter(call=>call[0]==='scope'),[]);
  assert.deepEqual(calls.filter(call=>call[0]==='activate'),[['activate','accounts']]);
});
