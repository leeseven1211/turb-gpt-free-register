const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const sourcePath = path.join(__dirname, '../webui/static/js/modern/extract-workbench.js');
const source = fs.existsSync(sourcePath) ? fs.readFileSync(sourcePath, 'utf8') : '';

function createView() {
  const nodes = new Map();
  const requests = [];
  const copied = [];
  const document = {
    getElementById(id) { return nodes.get(id) || null; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {},
  };
  const window = {
    crypto: require('node:crypto').webcrypto,
    __EXTRACT_WORKBENCH_DATA_SOURCE__(endpoint, options = {}) {
      requests.push({endpoint, options});
      return Promise.resolve({ok: true, items: [], counts: {}, page: 1, page_size: 20, total: 0});
    },
  };
  const context = {document, window, URLSearchParams, setTimeout, clearTimeout,
    LIST_FACET_LABELS:{source:{cloudflare_domain:'域名邮箱',email_butler:'Email Butler',remail:'Remail'}},
    navigator:{clipboard:{writeText:async value => copied.push(value)}}, showToast() {}};
  vm.createContext(context);
  vm.runInContext(`${source}\n;globalThis.workbench = {
    renderCard: typeof renderExtractWorkbenchTaskCard === 'function' ? renderExtractWorkbenchTaskCard : undefined,
    modes: typeof extractWorkbenchModesForProvider === 'function' ? extractWorkbenchModesForProvider : undefined,
    createPayload: typeof extractWorkbenchCreatePayload === 'function' ? extractWorkbenchCreatePayload : undefined,
    listUrl: typeof extractWorkbenchListUrl === 'function' ? extractWorkbenchListUrl : undefined,
    outcome: extractWorkbenchOutcome,
    renderTabs: extractWorkbenchRenderStatusTabs,
    openCreate: extractWorkbenchOpenCreate,
    copy: extractWorkbenchCopy,
    submit: extractWorkbenchSubmit,
    loadAccounts: extractWorkbenchLoadAccounts,
    candidateSignature: extractWorkbenchCandidateSignature,
    candidateFilters: extractWorkbenchCandidateFilters,
    invalidatePreview: extractWorkbenchInvalidatePreview,
    switchBatch: extractWorkbenchSwitchBatch,
    renderBatches: extractWorkbenchRenderBatches,
    accountSources: extractWorkbenchAccountSources,
    setConfig(value) { if (typeof EXTRACT_WORKBENCH_CONFIG !== 'undefined') EXTRACT_WORKBENCH_CONFIG = value; },
    load: typeof loadExtractWorkbench === 'function' ? loadExtractWorkbench : undefined,
    setRoot(value) { if (typeof EXTRACT_WORKBENCH_ROOT !== 'undefined') EXTRACT_WORKBENCH_ROOT = value; },
    state: () => typeof EXTRACT_WORKBENCH_STATE === 'undefined' ? {} : ({...EXTRACT_WORKBENCH_STATE}),
    setState(value) { if (typeof EXTRACT_WORKBENCH_STATE !== 'undefined') EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, ...value}; },
  };`, context);
  return {api: context.workbench, nodes, requests, window, copied};
}

test('任务卡分别呈现预检、提链、支付和 Plus 状态', () => {
  const {api} = createView();
  const html = api.renderCard({
    task_id: 'task-1', email: 'safe@example.test', task_status: 'running',
    preflight_status: 'success', extraction_status: 'success',
    payment_status: 'paid', plus_status: 'pending', run_count: 2,
    has_extract_link: true, has_payment_link: true,
  });
  assert.match(html, /预检/);
  assert.match(html, /提链成功/);
  assert.match(html, /支付成功/);
  assert.match(html, /Plus 待确认/);
  assert.match(html, /data-stage="payment"/);
  assert.match(html, /data-stage="plus"/);
});

test('状态筛选依赖独立支付与 Plus 字段，不把已支付误认为 Plus 已确认', () => {
  const {api} = createView();
  const task = {payment_status: 'paid', plus_status: 'pending'};
  assert.equal(api.listUrl({status: 'payment_succeeded'}).includes('status=payment_succeeded'), true);
  assert.equal(api.listUrl({status: 'plus_confirmed'}).includes('status=plus_confirmed'), true);
  assert.notEqual(task.payment_status, task.plus_status);
});

test('平台模式选择只保留服务端公布的能力', () => {
  const {api} = createView();
  const provider = {id: 'lumen', modes: ['extract_only', 'manual_payment']};
  assert.deepEqual(Array.from(api.modes(provider)), ['extract_only', 'manual_payment']);
  assert.deepEqual(Array.from(api.modes({id: 'other', modes: ['extract_only']})), ['extract_only']);
  assert.deepEqual(Array.from(api.modes({id: 'lumen', modes: ['auto_payment']})), ['auto_payment']);
  api.setConfig({default_provider: 'lumen', default_mode: 'auto_payment', providers: [provider]});
  assert.equal(api.createPayload(['acct-1'], 'lumen', 'auto_payment').mode, '');
});

test('批量创建默认 extract_only 且只提交选择的账号 ID', () => {
  const {api} = createView();
  api.setConfig({default_provider: 'lumen', default_mode: 'auto_payment', providers: [
    {id: 'lumen', default_type: 'plus', modes: ['extract_only', 'auto_payment']},
  ]});
  assert.deepEqual(JSON.parse(JSON.stringify(api.createPayload(['acct-1', 'acct-2'], 'lumen'))), {
    account_ids: ['acct-1', 'acct-2'], provider_id: 'lumen', mode: 'extract_only', type: 'plus',
  });
  assert.equal(api.createPayload(['acct-1'], 'lumen', 'auto_payment').mode, 'auto_payment');
});

test('页面刷新查询列表和能力配置，列表不请求敏感链接', async () => {
  const {api, requests} = createView();
  api.setRoot({innerHTML: '', addEventListener() {}, querySelector() { return null; }});
  await api.load({force: true});
  assert.ok(requests.some(item => item.endpoint === '/api/extract-workbench/config'));
  assert.ok(requests.some(item => item.endpoint.startsWith('/api/extract-workbench/tasks?')));
  assert.ok(requests.every(item => !item.endpoint.endsWith('/links')));
  assert.ok(requests.every(item => !item.endpoint.startsWith('/api/accounts')));
});

test('原型卡片保留三项主操作、中文平台和运行次数，未知进度不伪造百分比', () => {
  const {api} = createView();
  const html = api.renderCard({task_id:42, account_id:7, email:'<account>@example.test',
    provider_id:'lumen_flow', mode:'extract_only', task_status:'running', run_count:2,
    preflight_status:'passed', extraction_status:'running', payment_status:'unpaid', plus_status:'pending'});
  for (const label of ['Lumen Flow', '仅提链', '运行 2 次', '预检通过', '打开支付', '复制链接', '复制 AT']) assert.ok(html.includes(label));
  assert.match(html, /extract-workbench-card-actions/);
  assert.match(html, /&lt;account&gt;@example.test/);
  assert.doesNotMatch(html, /Run 2|运行 2\/3|aria-valuenow="100"|>extract_only</);
});

test('支付成功待核验、出链成功未支付和提链失败呈现不同结果', () => {
  const {api} = createView();
  assert.equal(api.outcome({task_status:'success',payment_status:'paid',plus_status:'pending'}).title,'支付成功 · 到账待核实');
  assert.equal(api.outcome({task_status:'success',payment_status:'paid',plus_status:'confirmed'}).title,'支付成功 · 到账已核实');
  assert.equal(api.outcome({task_status:'success',mode:'extract_only',extraction_status:'success',payment_status:'unpaid'}).title,'提链成功');
  assert.equal(api.outcome({task_status:'failed',extraction_status:'failed',payment_status:'unpaid'}).title,'提链未完成');
  assert.equal(api.outcome({task_status:'failed',extraction_status:'failed',payment_status:'failed'}).title,'提链未完成');
  assert.equal(api.outcome({task_status:'request_unknown',extraction_status:'failed',payment_status:'unpaid'}).title,'平台结果 · 等待确认');
});

test('顶部标签使用全部统计数，切换状态后不把筛选结果当全部数量', () => {
  const {api} = createView();
  const tabs={innerHTML:''};
  api.setRoot({querySelector: selector => selector==='[data-workbench-status-tabs]' ? tabs : null});
  api.setState({status:'running',total:1,counts:{all:1705,running:7,processing:18}});
  api.renderTabs();
  assert.match(tabs.innerHTML,/全部任务<\/strong><span>1,705/);
  assert.match(tabs.innerHTML,/data-workbench-status-filter="running" aria-pressed="true"/);
  assert.match(tabs.innerHTML,/只看运行中<\/strong><span>7/);
});

test('新建批次弹窗打开后才查询候选，重新打开会刷新匹配数量', async () => {
  const {api,requests}=createView();
  const dialog={open:false, showModal(){this.open=true;},close(){this.open=false;}};
  const accounts={innerHTML:''};
  api.setConfig({providers:[]});
  api.setRoot({querySelector:selector=>({'[data-workbench-create-dialog]':dialog,'[data-workbench-accounts]':accounts})[selector] || null});
  assert.equal(requests.length,0);
  await api.openCreate();
  assert.equal(dialog.open,true);
  dialog.close();
  await api.openCreate();
  assert.equal(requests.filter(item=>item.endpoint.startsWith('/api/extract-workbench/candidates?')).length,2);
  assert.doesNotMatch(accounts.innerHTML,/type="checkbox"/);
});

test('复制 AT 只在点击时读取指定账号密钥，不写入任务卡片或状态', async () => {
  const {api,window,copied,requests}=createView();
  const task={task_id:42,account_id:7,email:'sample@example.test'};
  api.setState({items:[task]});
  assert.equal(requests.length,0);
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async endpoint=>{
    requests.push({endpoint}); return {ok:true,value:'test-access-token'};
  };
  await api.copy(42,'at');
  assert.equal(requests[0].endpoint,'/api/accounts/7/secret?field=access_token');
  assert.deepEqual(copied,['test-access-token']);
  assert.doesNotMatch(api.renderCard(api.state().items[0]),/test-access-token/);
  assert.equal(api.state().items[0].access_token,undefined);
});

test('新筛选请求先返回时丢弃旧列表响应', async () => {
  const {api, window} = createView();
  api.setConfig({default_provider:'lumen', default_mode:'extract_only', providers:[]});
  api.setRoot({innerHTML:'', addEventListener() {}, querySelector() { return null; }});
  const deferred = [];
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = endpoint => endpoint.startsWith('/api/extract-workbench/tasks?')
    ? new Promise(resolve => deferred.push(resolve))
    : Promise.resolve({ok:true, items:[]});
  const oldRequest = api.load();
  await Promise.resolve();
  const newRequest = api.load();
  await Promise.resolve();
  deferred[1]({items:[{task_id:'new'}], counts:{}, page:1, total:1});
  await newRequest;
  deferred[0]({items:[{task_id:'old'}], counts:{}, page:1, total:1});
  await oldRequest;
  assert.equal(api.state().items[0].task_id, 'new');
});

test('账号搜索的新响应先返回后，旧的成功或失败响应都不能覆盖结果', async () => {
  for (const staleReject of [false,true]) {
    const {api,window}=createView();
    const query={value:'older'};
    const accounts={innerHTML:''};
    api.setRoot({querySelector:selector=>({'[data-workbench-account-query]':query,'[data-workbench-accounts]':accounts})[selector] || null});
    const deferred=[];
    window.__EXTRACT_WORKBENCH_DATA_SOURCE__=()=>new Promise((resolve,reject)=>deferred.push({resolve,reject}));
    const older=api.loadAccounts();
    query.value='newer';
    const newer=api.loadAccounts();
    deferred[1].resolve({items:[{id:2,email:'newer@example.test'}]});
    await newer;
    if (staleReject) deferred[0].reject(new Error('旧搜索失败'));
    else deferred[0].resolve({items:[{id:1,email:'older@example.test'}]});
    await older;
    assert.match(accounts.innerHTML,/newer@example.test/);
    assert.doesNotMatch(accounts.innerHTML,/older@example.test|旧搜索失败/);
  }
});

test('筛选批次提交数量不受预览条数限制，成功后切到新批次', async () => {
  const {api,window}=createView();
  const dialog={open:true,close(){this.open=false;}};
  const feedback={textContent:''};
  api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only'],default_type:'momo'}]});
  const selectors={'[data-workbench-create-dialog]':dialog,'[data-workbench-create-feedback]':feedback,
    '[data-workbench-provider]':{value:'lumen_flow'},'[data-workbench-mode]':{value:'extract_only'},
    '[data-workbench-batch-limit]':{value:'100'},'[data-workbench-batch-title]':{value:'10月14日提链'},
    '[data-workbench-date-from]':{value:'2026-10-14'},'[data-workbench-date-to]':{value:'2026-10-14'}};
  api.setRoot({querySelector:selector=>selectors[selector] || null,addEventListener(){}});
  api.setState({preview:{selected_count:100,items:[{account_id:7}]},previewSignature:api.candidateSignature()});
  const posted=[];
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async (endpoint,options={})=>{
    if (endpoint==='/api/extract-workbench/batches' && options.method==='POST') {
      posted.push(JSON.parse(options.body));return {batch_id:44,requested:100,started:98,skipped:2,failed:0};
    }
    if (endpoint==='/api/extract-workbench/config') return {providers:[{id:'lumen_flow',modes:['extract_only']}]};
    if (endpoint==='/api/extract-workbench/batches/44') return {item:{batch_id:44,title:'10月14日提链'}};
    return {items:[{task_id:42}],total:1,counts:{all:1},page:1};
  };
  await api.submit();
  assert.equal(dialog.open,false);
  assert.equal(api.state().batch,'44');
  assert.equal(api.state().batchDetail.title,'10月14日提链');
  assert.equal(api.state().items[0].task_id,42);
  assert.equal(posted.length,1);
  assert.equal(posted[0].limit,100);
  assert.equal(posted[0].filters.date_from,'2026-10-14');
  assert.equal(posted[0].filters.extract_status,'not_succeeded');
  assert.equal(posted[0].account_ids,undefined);
  assert.match(posted[0].submission_id,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.match(feedback.textContent,/入队 98 个任务/);
});

test('筛选条件变更后预览失效，提交不会沿用旧匹配数量', async () => {
  const {api,requests}=createView();
  const query={value:'first'};
  const feedback={textContent:''};
  const selectors={'[data-workbench-account-query]':query,'[data-workbench-provider]':{value:'lumen_flow'},'[data-workbench-mode]':{value:'extract_only'},'[data-workbench-candidate-summary]':feedback};
  api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only']}]});
  api.setRoot({querySelector:selector=>selectors[selector] || null});
  api.setState({preview:{selected_count:100},previewSignature:api.candidateSignature()});
  query.value='second';
  api.invalidatePreview();
  await api.submit();
  assert.equal(api.state().preview,null);
  assert.equal(requests.length,0);
  assert.match(feedback.textContent,/重新预览/);
});

test('切换批次后旧批次任务和摘要的迟到响应均被忽略', async () => {
  const {api,window}=createView();
  api.setConfig({providers:[]});
  api.setRoot({querySelector(){return null;},addEventListener(){}});
  const pending={};
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=endpoint=>{
    if(endpoint==='/api/extract-workbench/config')return Promise.resolve({providers:[]});
    return new Promise(resolve=>{pending[endpoint]=resolve;});
  };
  const older=api.switchBatch('11');
  await new Promise(resolve=>setImmediate(resolve));
  const newer=api.switchBatch('22');
  await new Promise(resolve=>setImmediate(resolve));
  const taskUrl=id=>Object.keys(pending).find(url=>url.includes('/tasks?') && url.includes(`batch_id=${id}`));
  pending[taskUrl('22')]({items:[{task_id:222}],counts:{all:1},total:1,page:1});
  pending['/api/extract-workbench/batches/22']({item:{batch_id:22,title:'新批次'}});
  await newer;
  pending[taskUrl('11')]({items:[{task_id:111}],counts:{all:1},total:1,page:1});
  pending['/api/extract-workbench/batches/11']({item:{batch_id:11,title:'旧批次'}});
  await older;
  assert.equal(api.state().items[0].task_id,222);
  assert.equal(api.state().batchDetail.title,'新批次');
  assert.equal(api.state().batch,'22');
});

test('批次切换清空上批筛选，全部任务请求不携带batch_id', async () => {
  const {api,requests}=createView();
  api.setConfig({providers:[]});
  api.setRoot({querySelector(){return null;},addEventListener(){}});
  api.setState({batch:'11',status:'running',provider:'lumen_flow',query:'older',page:4});
  await api.switchBatch('');
  assert.equal(api.state().status,'');
  assert.equal(api.state().provider,'');
  assert.equal(api.state().query,'');
  assert.equal(api.state().page,1);
  assert.ok(requests.some(r=>r.endpoint.includes('/tasks?') && !r.endpoint.includes('batch_id=')));
});

test('创建响应丢失后重试沿用提交标识，改变批次参数才生成新标识', async () => {
  const {api,window}=createView();
  const title={value:'同一批次'};
  const selectors={'[data-workbench-batch-title]':title,'[data-workbench-provider]':{value:'lumen_flow'},'[data-workbench-mode]':{value:'extract_only'}};
  api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only']}]});
  api.setRoot({querySelector:selector=>selectors[selector] || null});
  api.setState({preview:{selected_count:100},previewSignature:api.candidateSignature()});
  const posted=[];
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async (endpoint,options)=>{
    posted.push(JSON.parse(options.body)); throw new Error('连接中断');
  };
  await api.submit();
  await api.submit();
  assert.equal(posted.length,2);
  assert.equal(posted[0].submission_id,posted[1].submission_id);
  title.value='另一个批次';
  await api.submit();
  assert.notEqual(posted[0].submission_id,posted[2].submission_id);
});

test('邮箱来源复用账号现有枚举，域名邮箱和 Butler 等来源不遗漏', () => {
  const {api}=createView();
  assert.equal(api.accountSources().cloudflare_domain,'域名邮箱');
  assert.equal(api.accountSources().email_butler,'Email Butler');
  assert.equal(api.accountSources().remail,'Remail');
  assert.equal(api.accountSources().domain,undefined);
});


test('批次配置初始化默认并发，刷新保留用户已编辑的值', async () => {
  const {api, window}=createView();
  const workers={value:'1'};
  const hint={textContent:''};
  const selectors={'[data-workbench-batch-workers]':workers,'[data-workbench-concurrency-hint]':hint};
  api.setRoot({querySelector:selector=>selectors[selector] || null,addEventListener(){}});
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async endpoint=>endpoint.endsWith('/config')
    ? {providers:[],batch_workers_default:4,batch_workers_max:16}
    : {items:[],counts:{},total:0,page:1};
  await api.load({force:true});
  assert.equal(workers.value,'4');
  assert.equal(workers.min,'1');
  assert.equal(workers.max,'16');
  assert.match(hint.textContent,/并发|同时/);
  workers.value='7';
  await api.load({force:true});
  assert.equal(workers.value,'7');
});

test('提交携带批次并发，连接失败重试保留标识，修改并发生成新标识', async () => {
  const {api,window}=createView();
  const workers={value:'4'};
  const selectors={'[data-workbench-batch-workers]':workers,'[data-workbench-provider]':{value:'lumen_flow'},'[data-workbench-mode]':{value:'extract_only'}};
  api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only']}],batch_workers_default:1,batch_workers_max:16});
  api.setRoot({querySelector:selector=>selectors[selector] || null});
  api.setState({preview:{selected_count:100},previewSignature:api.candidateSignature()});
  const posted=[];
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__=async (endpoint,options)=>{
    posted.push(JSON.parse(options.body)); throw new Error('连接中断');
  };
  await api.submit();
  await api.submit();
  assert.equal(posted[0].workers,4);
  assert.equal(posted[0].submission_id,posted[1].submission_id);
  workers.value='8';
  await api.submit();
  assert.equal(posted[2].workers,8);
  assert.notEqual(posted[0].submission_id,posted[2].submission_id);
});

test('批次并发空值、非整数和超范围时不发送创建请求', async () => {
  for (const value of ['', '0', '17', '1.5', 'abc']) {
    const {api,requests}=createView();
    const feedback={textContent:''};
    const selectors={'[data-workbench-batch-workers]':{value},'[data-workbench-provider]':{value:'lumen_flow'},
      '[data-workbench-mode]':{value:'extract_only'},'[data-workbench-create-feedback]':feedback};
    api.setConfig({providers:[{id:'lumen_flow',modes:['extract_only']}],batch_workers_default:1,batch_workers_max:16});
    api.setRoot({querySelector:selector=>selectors[selector] || null});
    api.setState({preview:{selected_count:100},previewSignature:api.candidateSignature()});
    await api.submit();
    assert.equal(requests.length,0,`非法并发 ${value} 不应发起请求`);
    assert.match(feedback.textContent,/并发.*1.*16/);
  }
});

test('批次摘要显示本批并发，历史批次显示沿用平台并发', () => {
  const {api}=createView();
  const summary={innerHTML:''};
  api.setRoot({querySelector:selector=>selector==='[data-workbench-batch-summary]' ? summary : null});
  api.setState({batchDetail:{batch_id:7,title:'当前批次',workers:4}});
  api.renderBatches();
  assert.match(summary.innerHTML,/并发 4/);
  api.setState({batchDetail:{batch_id:6,title:'历史批次',workers:null}});
  api.renderBatches();
  assert.match(summary.innerHTML,/平台并发/);
});
