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
  const nodes = new Map();
  const panel = {
    hidden: true, shellWrites: 0, addEventListener() {},
    querySelector(selector) {return nodes.get(selector) || null;},
    set innerHTML(value) {
      this.shellHTML = value;
      this.shellWrites++;
      nodes.set('[data-operation-receipt-summary]', {textContent: ''});
      nodes.set('.operation-receipts-details-v2', {open: /<details\b[^>]*\bopen(?:\s|>)/.test(value)});
      nodes.set('[data-operation-receipt-refresh]', {dataset: {}});
      nodes.set('.operation-receipts-list-v2', {
        scrollTop: 0, buttons: [], html: '',
        contains(element) {return this.buttons.includes(element);},
        querySelectorAll() {return this.buttons;},
        get innerHTML() {return this.html;},
        set innerHTML(html) {
          this.html = html;
          this.scrollTop = 0;
          this.buttons = [...html.matchAll(/data-operation-receipt-task="([^"]+)" data-operation-receipt-run="([^"]*)"/g)].map(match => ({
            dataset: {operationReceiptTask: match[1], operationReceiptRun: match[2]},
            focus(options) {context.document.activeElement = this; this.focusOptions = options;},
          }));
        },
      });
    },
  };
  const tab = {hidden: false, dataset: {moduleView: 'tasks'}, classList: {contains: () => tab.hidden}};
  const filter = {value: 'codex_retry'};
  const navigations = [];
  const timers = new Map();
  let timer = 0;
  const context = {
    esc: String,
    document: {hidden: false, activeElement: null, addEventListener() {}, getElementById(id) {return id === 'operationReceiptsV2' ? panel : id === 'tab-accounts' ? tab : id === 'accountTaskTypeFilterV2' ? filter : null;}},
    MutationObserver: class {observe() {}}, activateTab(name) {navigations.push(name); tab.hidden = name !== 'tasks';}, openAccountTaskLog() {},
    setTimeout(callback) {timers.set(++timer, callback);return timer;}, clearTimeout(id) {timers.delete(id);},
    api: async url => ({ok: true, task: {status: 'queued', runs: [{id: Number(url.split('/')[3]), status: 'queued'}]}}),
  };
  vm.createContext(context);
  vm.runInContext(operations.slice(operations.indexOf('const OPERATION_RECEIPTS_V2'), operations.indexOf('function formatTaskDuration(')) + '\nglobalThis.view={state:OPERATION_RECEIPTS_V2,track:trackAcceptedOperationsV2,show:showOperationReceiptsV2,refresh:refreshOperationReceiptsV2,schedule:scheduleOperationReceiptsV2};', context);
  return {context, view:context.view, panel, timers, tab, filter, navigations};
}

test('202只显示排队，回执读取真实Run后分别显示最终成功和失败', async () => {
  const {context,view,panel} = receiptHarness();
  view.state.items.set('17:29',{task_id:17,run_id:29,label:'手动上传',status:'queued'});
  context.api=async()=>({ok:true,task:{status:'success',runs:[{id:29,status:'queued'}]}});
  await view.refresh();
  assert.match(panel.querySelector('[data-operation-receipt-summary]').textContent,/等待\/执行 1 · 成功 0/);
  context.api=async()=>({ok:true,task:{runs:[{id:29,status:'failed',error_message:'Sub2API 鉴权失败'}]}});
  await view.refresh();
  assert.match(panel.querySelector('[data-operation-receipt-summary]').textContent,/失败或待处理 1/);
  assert.match(panel.querySelector('.operation-receipts-list-v2').innerHTML,/Sub2API 鉴权失败/);
  assert.match(panel.querySelector('.operation-receipts-list-v2').innerHTML,/data-operation-receipt-task="17"/);
  view.state.items.set('18:30',{task_id:18,run_id:30,label:'手动上传',status:'queued'});
  context.api=async()=>({ok:true,task:{runs:[{id:30,status:'success'}]}});
  await view.refresh();
  assert.match(panel.querySelector('[data-operation-receipt-summary]').textContent,/成功 1 · 失败或待处理 1/);
});

test('网络读取失败保留排队事实，隐藏任务页停止自动刷新', async () => {
  const {context,view,panel,timers} = receiptHarness();
  view.state.items.set('17:29',{task_id:17,run_id:29,label:'手动上传',status:'queued'});
  context.api=async()=>{throw new Error('fixture_network');};
  await view.refresh();
  assert.equal(view.state.items.get('17:29').status,'queued');
  assert.match(panel.querySelector('[data-operation-receipt-summary]').textContent,/部分回执暂未读到/);
  assert.equal(timers.size,1);
  context.document.hidden=true;
  view.schedule();
  assert.equal(timers.size,0);
});

test('100项上传全部完成后保持回执默认收起，不重建详情外壳', async () => {
  const {context,view,panel} = receiptHarness();
  for (let id = 1; id <= 100; id++) {
    view.state.items.set(`${id}:${id + 1000}`, {task_id:id,run_id:id + 1000,label:'手动上传',status:'queued'});
  }
  context.api = async url => ({ok:true,task:{runs:[{id:Number(url.split('/')[3].split('?')[0]) + 1000,status:'success'}]}});
  for (let round = 0; round < 5; round++) await view.refresh();
  assert.match(panel.querySelector('[data-operation-receipt-summary]').textContent,/共 100 项 · 等待\/执行 0 · 成功 100/);
  assert.equal(panel.querySelector('.operation-receipts-list-v2').buttons.length,100);
  assert.equal(panel.querySelector('.operation-receipts-details-v2').open,false);
  assert.equal(panel.shellWrites,1);
  assert.equal(panel.hidden,false);
});

test('轮询刷新保持手动开合、明细滚动位置和同一Run按钮的键盘焦点', async () => {
  const {context,view,panel} = receiptHarness();
  view.state.items.set('17:29',{task_id:17,run_id:29,label:'手动上传',status:'queued'});
  view.state.items.set('17:30',{task_id:17,run_id:30,label:'手动上传',status:'queued'});
  context.api = async () => ({ok:true,task:{runs:[{id:29,status:'running'},{id:30,status:'running'}]}});
  await view.refresh();
  const details = panel.querySelector('.operation-receipts-details-v2');
  const list = panel.querySelector('.operation-receipts-list-v2');
  const refreshButton = panel.querySelector('[data-operation-receipt-refresh]');
  details.open = true;
  list.scrollTop = 240;
  const oldButton = list.buttons[1];
  oldButton.focus();
  await view.refresh();
  assert.equal(panel.querySelector('.operation-receipts-details-v2'),details);
  assert.equal(details.open,true);
  assert.equal(list.scrollTop,240);
  assert.notEqual(context.document.activeElement,oldButton);
  assert.equal(context.document.activeElement,list.buttons[1]);
  assert.equal(context.document.activeElement.dataset.operationReceiptRun,'30');
  assert.equal(context.document.activeElement.focusOptions.preventScroll,true);
  details.open = false;
  context.document.activeElement = refreshButton;
  await view.refresh();
  assert.equal(details.open,false);
  assert.equal(context.document.activeElement,refreshButton);
  assert.equal(panel.querySelector('[data-operation-receipt-refresh]'),refreshButton);
  assert.equal(panel.shellWrites,1);
});

test('选择留在当前页时只保存回执，主动查看进度才跳转并开始读取', () => {
  const {context,view,panel,timers,tab,filter,navigations} = receiptHarness();
  tab.hidden = true;
  let reads = 0;
  context.api = async () => {reads++;return {ok:true,task:{status:'queued'}};};
  view.track([{accepted:true,task_id:17,run_id:29}], '手动上传', {navigate:false});
  assert.equal(view.state.items.size,1);
  assert.equal(panel.hidden,false);
  assert.deepEqual(navigations,[]);
  assert.equal(filter.value,'codex_retry');
  assert.equal(reads,0);
  assert.equal(timers.size,0);
  view.show();
  assert.deepEqual(navigations,['tasks']);
  assert.equal(filter.value,'');
  assert.equal(reads,1);
});

test('未指定留页选项的原有调用方仍直接打开任务中心', () => {
  const {view,tab,filter,navigations} = receiptHarness();
  tab.hidden = true;
  view.track([{accepted:true,task_id:17,run_id:29}], '手动上传');
  assert.deepEqual(navigations,['tasks']);
  assert.equal(filter.value,'');
  assert.equal(tab.hidden,false);
});

test('账号与Codex上传提交202后不会显示上传成功或把未完成凭证记为已上传', async () => {
  for (const [source,name] of [[accounts,'uploadSelectedCodexSub2'],[codex,'codexUploadSub2']]) {
    const toasts=[],tracked=[],button={disabled:false,textContent:'上传',classList:{remove() {}}};
    const context={
      ACCOUNT_SELECTED:new Set([23]),ACCOUNTS:[{id:23,codex_status:'success'}],CODEX_SELECTED:new Set(['fixture.json']),
      confirm:()=>true,$:()=>button,document:{getElementById:()=>button},
      api:async()=>({accepted:true,queued_count:1,uploaded_count:0,queued:[{accepted:true,task_id:17,run_id:29,filename:'fixture.json'}]}),
      showToast:text=>toasts.push(text),trackAcceptedOperationsV2:(items,label,options)=>tracked.push({items,label,options}),
      pollAccountPlanStatuses:async()=>{throw new Error('202不应读上传成功状态');},loadCodex:async()=>{throw new Error('202不应读上传成功状态');},
      updateAccountSelectionUi(){},_codexUpdateSelectedHint(){},
    };
    vm.createContext(context);vm.runInContext(extract(source,name),context);
    await context[name]();
    assert.match(toasts[0],/已入队 1/);
    assert.doesNotMatch(toasts[0],/已上传/);
    assert.equal(tracked[0].items[0].task_id,17);
    if (name === 'codexUploadSub2') assert.equal(tracked[0].options.navigate,false);
    else assert.equal(tracked[0].options,undefined);
  }
});
