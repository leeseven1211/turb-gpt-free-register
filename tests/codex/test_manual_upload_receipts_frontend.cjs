const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '../..');
const operations = fs.readFileSync(path.join(root, 'webui/static/js/pages/operations/page.js'), 'utf8');
const accounts = fs.readFileSync(path.join(root, 'webui/static/js/pages/accounts/page.js'), 'utf8');
const codex = fs.readFileSync(path.join(root, 'webui/static/js/pages/codex/page.js'), 'utf8');
function extract(source, name) {
  const index = source.indexOf(`function ${name}(`);
  const start = source.slice(Math.max(0, index - 6), index) === 'async ' ? index - 6 : index;
  const end = source.indexOf('\n}', index);
  return source.slice(start, end + 2);
}
function receiptHarness() {
  const panel = {hidden: true, innerHTML: '', addEventListener() {}};
  const tab = {dataset: {moduleView: 'tasks'}, classList: {contains: () => false}};
  const timers = new Map();
  let timer = 0;
  const context = {
    esc: String,
    document: {hidden: false, addEventListener() {}, getElementById(id) {return id === 'operationReceiptsV2' ? panel : id === 'tab-accounts' ? tab : null;}},
    MutationObserver: class {observe() {}}, activateTab() {}, openAccountTaskLog() {},
    setTimeout(callback) {timers.set(++timer, callback);return timer;}, clearTimeout(id) {timers.delete(id);},
    api: async url => ({ok: true, task: {status: 'queued', runs: [{id: Number(url.split('/')[3]), status: 'queued'}]}}),
  };
  vm.createContext(context);
  vm.runInContext(operations.slice(operations.indexOf('const OPERATION_RECEIPTS_V2'), operations.indexOf('function formatTaskDuration(')) + '\nglobalThis.view={state:OPERATION_RECEIPTS_V2,track:trackAcceptedOperationsV2,refresh:refreshOperationReceiptsV2,schedule:scheduleOperationReceiptsV2};', context);
  return {context, view:context.view, panel, timers};
}

test('202只显示排队，回执读取真实Run后分别显示最终成功和失败', async () => {
  const {context,view,panel} = receiptHarness();
  view.state.items.set('17:29',{task_id:17,run_id:29,label:'手动上传',status:'queued'});
  context.api=async()=>({ok:true,task:{status:'success',runs:[{id:29,status:'queued'}]}});
  await view.refresh();
  assert.match(panel.innerHTML,/等待\/执行 1 · 成功 0/);
  context.api=async()=>({ok:true,task:{runs:[{id:29,status:'failed',error_message:'Sub2API 鉴权失败'}]}});
  await view.refresh();
  assert.match(panel.innerHTML,/失败或待处理 1/);
  assert.match(panel.innerHTML,/Sub2API 鉴权失败/);
  assert.match(panel.innerHTML,/data-operation-receipt-task="17"/);
  view.state.items.set('18:30',{task_id:18,run_id:30,label:'手动上传',status:'queued'});
  context.api=async()=>({ok:true,task:{runs:[{id:30,status:'success'}]}});
  await view.refresh();
  assert.match(panel.innerHTML,/成功 1 · 失败或待处理 1/);
});

test('网络读取失败保留排队事实，隐藏任务页停止自动刷新', async () => {
  const {context,view,panel,timers} = receiptHarness();
  view.state.items.set('17:29',{task_id:17,run_id:29,label:'手动上传',status:'queued'});
  context.api=async()=>{throw new Error('fixture_network');};
  await view.refresh();
  assert.equal(view.state.items.get('17:29').status,'queued');
  assert.match(panel.innerHTML,/部分回执暂未读到/);
  assert.equal(timers.size,1);
  context.document.hidden=true;
  view.schedule();
  assert.equal(timers.size,0);
});

test('账号与Codex上传提交202后不会显示上传成功或把未完成凭证记为已上传', async () => {
  for (const [source,name] of [[accounts,'uploadSelectedCodexSub2'],[codex,'codexUploadSub2']]) {
    const toasts=[],tracked=[],button={disabled:false,textContent:'上传'};
    const context={
      ACCOUNT_SELECTED:new Set([23]),ACCOUNTS:[{id:23,codex_status:'success'}],CODEX_SELECTED:new Set(['fixture.json']),
      confirm:()=>true,$:()=>button,document:{getElementById:()=>button},
      api:async()=>({accepted:true,queued_count:1,uploaded_count:0,queued:[{accepted:true,task_id:17,run_id:29,filename:'fixture.json'}]}),
      showToast:text=>toasts.push(text),trackAcceptedOperationsV2:(items,label)=>tracked.push({items,label}),
      pollAccountPlanStatuses:async()=>{throw new Error('202不应读上传成功状态');},loadCodex:async()=>{throw new Error('202不应读上传成功状态');},
      updateAccountSelectionUi(){},_codexUpdateSelectedHint(){},
    };
    vm.createContext(context);vm.runInContext(extract(source,name),context);
    await context[name]();
    assert.match(toasts[0],/已入队 1/);
    assert.doesNotMatch(toasts[0],/已上传/);
    assert.equal(tracked[0].items[0].task_id,17);
  }
});
