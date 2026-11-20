const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const {mountToolbarFixture,ACCOUNT_TOOLBAR_BUTTONS,ACCOUNT_ACTION_USAGE_KEY} = require('./toolbar_fixture.cjs');
const template = fs.readFileSync(path.join(__dirname, '../../webui/templates/index.html'), 'utf8');
const defaults = ['btnCheckSelectedLiveV2', 'btnCheckSelectedPlansV2', 'btnRefreshSelectedTokenV2', 'btnExtractSelectedLinksV2', 'btnAddTwofaSelectedAccountsV2'];
const c2aId = 'btnReimportSelectedC2aV2';
const pageActions = [
  ['btnBulkFromAccountFilters', 'bulk-from-account-filters'],
  ['btnBulkFromSelectedAccounts', 'bulk-from-selected-accounts'],
  ['btnAccountInspection', 'openAccountInspectionStart'],
  ['btnAccountInspectionHistory', 'openAccountInspectionHistory'],
  ['btnDeleteDeactivatedAccounts', 'deleteDeactivatedAccounts'],
];
async function setup(options){const view=mountToolbarFixture(options);await view.ready;return view;}

test('无使用记录时恰好展示五个默认操作，C2A 留在批量操作且节点不重复', async () => {
  const view = await setup();
  assert.deepEqual(view.ids(), defaults);
  assert.equal(view.get('accountsMoreActionsV2').contains(view.get(c2aId)), true);
  const rendered = Array.from(view.get('accountsToolbarV2').querySelectorAll('button')).map(node => node.id);
  assert.equal(rendered.length, 39);
  assert.equal(new Set(rendered.filter(Boolean)).size, 34);
  assert.deepEqual(Array.from(view.get('accountsMoreActionsV2').querySelectorAll('button')).map(button => button.id), ACCOUNT_TOOLBAR_BUTTONS.map(item => item.id));
});

test('一次入口点击累计一次，退出菜单、弹窗和工具栏焦点后才更新前五', async () => {
  const view = await setup();
  const button = view.get(c2aId),more=view.get('accountsMoreActionsV2');
  more.open = true;button.focus();await view.click(c2aId);await view.flush();
  assert.deepEqual(view.ids(), defaults);
  assert.equal(view.calls.length,1);
  assert.equal(JSON.parse(view.storage.value)[c2aId], 1);
  more.open = false;
  const dialog=view.document.createElement('dialog');dialog.open=true;view.document.body.append(dialog);
  await view.refresh();assert.deepEqual(view.ids(), defaults);
  dialog.open=false;await view.refresh();assert.deepEqual(view.ids(), defaults);
  button.blur();await view.refresh();
  assert.deepEqual(view.ids(), [c2aId, ...defaults.slice(0, 4)]);
  assert.equal(more.contains(view.get(defaults[4])), true);
  assert.equal(more.contains(button), true);
  assert.equal(view.get('accountsToolbarV2').querySelectorAll('button').length, 39);
  assert.equal(view.get(c2aId),button);
  const expected=view.ids(),saved=view.storage.value;view.close();
  assert.deepEqual((await setup({saved})).ids(), expected);
});

test('未选择或缺少能力配置的按钮不增加使用次数，存储仅接受有效白名单计数', async () => {
  const view = await setup({saved: JSON.stringify({[c2aId]: -5, [defaults[0]]: 2, unknown: 900, [defaults[1]]: '100'})});
  const button = view.get(c2aId);
  await view.setState({selectedCount:0,archived:false});await view.click(c2aId);
  await view.setState({selectedCount:2,archived:false});await view.setCapabilities({c2a_sync:{enabled:false,reason:'配置缺失'}});await view.click(c2aId);
  assert.equal(button.classList.contains('feature-unavailable'),true);
  await view.setCapabilities({c2a_sync:{enabled:true}});button.setAttribute('aria-disabled','true');await view.click(c2aId);
  assert.equal(JSON.parse(view.storage.value)[c2aId], -5);assert.equal(view.calls.length,0);
  button.removeAttribute('aria-disabled');await view.click(c2aId);
  const saved = JSON.parse(view.storage.value);
  assert.equal(saved[c2aId], 1);assert.equal(saved[defaults[0]], 2);assert.equal(saved[defaults[1]], 0);assert.equal('unknown' in saved, false);
});

test('浏览器存储不可用时仍可操作并在当前页面累计排序', async () => {
  const view = await setup({storageBlocked: true});
  await view.click(c2aId);await view.click(c2aId);await view.flush();
  assert.equal(view.ids()[0], c2aId);
  assert.equal(view.calls.length,2);
  assert.equal(JSON.parse(view.storage.writes.at(-1).value)[c2aId],2);
  assert.equal(view.storage.value,null);
});

test('页面级动作也按次数进入五个快捷位置，保留单一节点和原动作边界', async () => {
  const view=await setup();
  const toolbar=view.get('accountsToolbarV2'),more=view.get('accountsMoreActionsV2');
  for(const [id,descriptor] of pageActions){
    const button=view.get(id);assert.equal(more.contains(button),true);assert.equal(button.getAttribute('onclick'),null);assert.equal(button.disabled,false);assert.equal(view.document.querySelectorAll(`#${id}`).length,1);
    assert.equal(ACCOUNT_TOOLBAR_BUTTONS.find(item=>item.id===id).action,descriptor);
  }
  assert.match(template,/id="accounts-list-root"/);
  assert.equal(toolbar.contains(view.document.getElementById('accounts-list-root')),false);
  const history=view.get('btnAccountInspectionHistory');await view.click(history.id);await view.flush();
  assert.equal(view.ids().length,5);assert.equal(view.ids()[0],history.id);assert.equal(view.get('accountsQuickActionsV2').querySelector('button'),view.shortcut(history.id));assert.equal(history.disabled,false);assert.equal(toolbar.querySelectorAll('button').length,39);
  assert.equal(view.calls.length,1);assert.equal(view.calls[0][0],'openAccountInspectionHistory');assert.equal(view.calls[0][1],view.context);assert.equal(view.calls[0][2],history);
});

test('外部存储事件只响应原键且卸载后不会恢复旧按钮',async()=>{
  const view=await setup();view.storage.value=JSON.stringify({btnDeleteDeactivatedAccounts:9});view.external('other');await view.flush();assert.deepEqual(view.ids(),defaults);
  view.external(ACCOUNT_ACTION_USAGE_KEY);await view.flush();assert.equal(view.ids()[0],'btnDeleteDeactivatedAccounts');view.close();view.external();await view.flush();assert.equal(view.document.querySelectorAll('#accountsToolbarV2 button').length,0);
});


test('批量操作入口位于常用操作前，未选择账号时仍可展开查看', async () => {
  const view=await setup({state:{selectedCount:0,archived:false}}),toolbar=view.get('accountsToolbarV2'),more=view.get('accountsMoreActionsV2');
  assert.equal(more.querySelector('summary').textContent,'批量操作');
  assert.equal(more.hasAttribute('hidden'),false);assert.equal(more.hasAttribute('disabled'),false);assert.equal(more.classList.contains('selection-only'),false);
  const children=Array.from(toolbar.children);assert.ok(children.indexOf(more)<children.indexOf(view.get('accountsQuickActionsV2')));
  more.open=true;assert.equal(more.open,true);assert.equal(view.get(c2aId).disabled,true);
});
