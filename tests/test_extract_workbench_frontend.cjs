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
  const context = {document, window, URL, URLSearchParams, setTimeout, clearTimeout,
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
    renderTasks: extractWorkbenchRenderTasks,
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
    renderPaymentEntry: renderExtractWorkbenchPaymentEntry,
    showPaymentEntry: extractWorkbenchShowPaymentEntry,
    copyPaymentEntry: extractWorkbenchCopyPaymentEntry,
    paymentQrError: extractWorkbenchPaymentQrError,
    paymentQrSources: extractWorkbenchPaymentQrSources,
    paymentUrl: extractWorkbenchPaymentUrl,
    setConfig(value) { if (typeof EXTRACT_WORKBENCH_CONFIG !== 'undefined') EXTRACT_WORKBENCH_CONFIG = value; },
    load: typeof loadExtractWorkbench === 'function' ? loadExtractWorkbench : undefined,
    setRoot(value) { if (typeof EXTRACT_WORKBENCH_ROOT !== 'undefined') EXTRACT_WORKBENCH_ROOT = value; },
    state: () => typeof EXTRACT_WORKBENCH_STATE === 'undefined' ? {} : ({...EXTRACT_WORKBENCH_STATE}),
    setState(value) { if (typeof EXTRACT_WORKBENCH_STATE !== 'undefined') EXTRACT_WORKBENCH_STATE = {...EXTRACT_WORKBENCH_STATE, ...value}; },
  };`, context);
  return {api: context.workbench, nodes, requests, window, copied, document};
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

test('任务列表每页查询 10 条，批次历史仍每页查询 20 条', async () => {
  const {api, requests} = createView();
  const batchSelect = {innerHTML:'', value:''};
  api.setRoot({addEventListener() {}, querySelector: selector => selector === '[data-workbench-batch-select]' ? batchSelect : null});
  await api.load({force:true});
  const taskRequest = requests.find(item => item.endpoint.startsWith('/api/extract-workbench/tasks?'));
  assert.equal(new URLSearchParams(taskRequest.endpoint.split('?')[1]).get('page_size'), '10');
  assert.ok(requests.some(item => item.endpoint === '/api/extract-workbench/batches?page=1&page_size=20'));
});

test('31 条任务分为四页，第二页摘要与首尾翻页状态正确', () => {
  const {api} = createView();
  const tasks = {innerHTML:''};
  const summary = {textContent:''};
  const label = {textContent:''};
  const previous = {disabled:false};
  const next = {disabled:false};
  const selectors = {'[data-workbench-tasks]':tasks, '[data-workbench-summary]':summary,
    '[data-workbench-page-label]':label, '[data-workbench-page="prev"]':previous, '[data-workbench-page="next"]':next};
  api.setRoot({querySelector: selector => selectors[selector] || null});
  for (const [page, count, range, previousDisabled, nextDisabled] of [
    [1, 10, '1–10', true, false], [2, 10, '11–20', false, false], [4, 1, '31–31', false, true],
  ]) {
    api.setState({page, total:31, items:Array.from({length:count}, (_, index) => ({task_id:(page - 1) * 10 + index + 1}))});
    api.renderTasks();
    assert.equal(summary.textContent, `显示 ${range} / 31 个任务`);
    assert.equal(label.textContent, `第 ${page} / 4 页`);
    assert.equal(previous.disabled, previousDisabled);
    assert.equal(next.disabled, nextDisabled);
    assert.equal((tasks.innerHTML.match(/class="extract-workbench-task"/g) || []).length, count);
  }
});

test('批次历史 31 条仍分为两页并保留独立翻页状态', () => {
  const {api} = createView();
  const label = {textContent:''};
  const previous = {disabled:false};
  const next = {disabled:false};
  const selectors = {'[data-workbench-batch-page-label]':label,
    '[data-workbench-batch-page="prev"]':previous, '[data-workbench-batch-page="next"]':next};
  api.setRoot({querySelector: selector => selectors[selector] || null});
  api.setState({batchPage:1, batchTotal:31});
  api.renderBatches();
  assert.equal(label.textContent, '第 1 / 2 页');
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, false);
  api.setState({batchPage:2});
  api.renderBatches();
  assert.equal(label.textContent, '第 2 / 2 页');
  assert.equal(previous.disabled, false);
  assert.equal(next.disabled, true);
});

test('主动刷新与切换批次重置卡片滚动，自动刷新保留最新滚动位置', async () => {
  const {api, window} = createView();
  const tasks = {scrollTop:140, innerHTML:''};
  api.setConfig({providers:[]});
  api.setRoot({addEventListener() {}, querySelector: selector => selector === '[data-workbench-tasks]' ? tasks : null});
  api.setState({page:2, status:'running'});
  await api.load({force:true});
  assert.equal(tasks.scrollTop, 0);
  tasks.scrollTop = 140;
  await api.switchBatch('22');
  assert.equal(tasks.scrollTop, 0);
  Object.defineProperty(tasks, 'innerHTML', {set(value) { this.html = value; this.scrollTop = 0; }, get() { return this.html; }});
  tasks.scrollTop = 140;
  window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async endpoint => {
    if (endpoint.startsWith('/api/extract-workbench/tasks?')) tasks.scrollTop = 185;
    return {items:[{task_id:1}], counts:{}, total:1, page:1};
  };
  await api.load({quiet:true});
  assert.equal(tasks.scrollTop, 185);
});

test('原型卡片保留三项主操作、中文平台和运行次数，未知进度不伪造百分比', () => {
  const {api} = createView();
  const html = api.renderCard({task_id:42, account_id:7, email:'<account>@example.test',
    provider_id:'lumen_flow', mode:'extract_only', task_status:'running', run_count:2,
    preflight_status:'passed', extraction_status:'running', payment_status:'unpaid', plus_status:'pending'});
  for (const label of ['Lumen Flow', '仅提链', '运行 2 次', '预检通过', '支付入口', '复制链接', '复制 AT']) assert.ok(html.includes(label));
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

test('提链成功事实独立于任务后续失败和待确认，结果区不反写提链失败', () => {
  const {api} = createView();
  for (const [status, title] of [['failed','提链成功 · 后续处理失败'], ['attention_required','提链成功 · 后续结果待确认'], ['request_unknown','提链成功 · 后续结果待确认']]) {
    const task = {task_status:status, extraction_status:'success', payment_status:'unpaid', has_extract_link:true};
    assert.equal(api.outcome(task).title, title);
    assert.doesNotMatch(api.renderCard(task), /提链未完成/);
  }
});

test('支付入口兼容列表能力标记与历史链接，卡片不携带敏感支付内容', () => {
  const {api} = createView();
  for (const flag of ['has_payment_entry', 'has_qr', 'has_payment_link', 'has_extract_link']) {
    const html = api.renderCard({task_id:42, [flag]:true, payment_url:'https://private.example.test/session', qr_data:'private-payment-data'});
    assert.match(html, /data-workbench-payment-entry="42">/);
    assert.doesNotMatch(html, /private-payment-data|private\.example/);
  }
  assert.match(api.renderCard({task_id:42}), /data-workbench-payment-entry="42" disabled/);
});

test('支付入口分别呈现支付页面、平台入口、二维码与平台核验，零金额不丢失', () => {
  const {api} = createView();
  const html = api.renderPaymentEntry({payment_page_url:'https://checkout.example.test/page', payment_url:'https://pay.example.test/entry',
    qr_data:'payment-payload<&>', qr_image_url_png:'https://img.example.test/code.png', qr_image_url_svg:'https://img.example.test/code.svg',
    amount:0, currency:'inr', payment_status:'succeeded', platform_plus_status:'confirmed'});
  assert.match(html, /支付页面/);
  assert.match(html, /href="https:\/\/checkout\.example\.test\/page"/);
  assert.match(html, /href="https:\/\/pay\.example\.test\/entry"/);
  assert.match(html, /src="https:\/\/img\.example\.test\/code\.png"/);
  assert.match(html, /payment-payload&lt;&amp;&gt;/);
  assert.match(html, /0 INR/);
  assert.match(html, /平台显示已开通/);
  assert.match(html, /本地到账以卡片中的/);
  assert.doesNotMatch(html, /onerror=|到账已核实/);
});

test('只有普通支付页面时不伪造二维码，无图片的二维码内容只呈现原文', () => {
  const {api} = createView();
  const page = api.renderPaymentEntry({payment_page_url:'https://checkout.example.test/page'});
  assert.doesNotMatch(page, /<img/);
  assert.match(page, /平台未返回二维码/);
  const raw = api.renderPaymentEntry({qr_data:'upi://pay?pa=demo'});
  assert.doesNotMatch(raw, /<img/);
  assert.match(raw, /upi:\/\/pay\?pa=demo/);
  assert.match(raw, /可复制下方二维码原文/);
});

test('平台链接与二维码图片过滤脚本地址，不把不可信字段注入 HTML', () => {
  const {api} = createView();
  const html = api.renderPaymentEntry({payment_page_url:'javascript:alert(1)', payment_url:'data:text/html,<script>alert(1)</script>',
    qr_image_url_png:'javascript:alert(1)', qr_image_url_svg:'https://img.example.test/qr.svg', qr_data:'<img src=x onerror=alert(1)>'});
  assert.doesNotMatch(html, /href="(?:javascript|data):|src="javascript:|<img src=x/);
  assert.match(html, /src="https:\/\/img\.example\.test\/qr\.svg"/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.equal(api.paymentUrl('https://user:secret@example.test/private'), '');
  assert.deepEqual(Array.from(api.paymentQrSources({qr_image_url_png:'data:image/png;base64,YWJj'})), ['data:image/png;base64,YWJj']);
});

function installPaymentDialog(view) {
  const listeners = {};
  const content = {innerHTML:'', textContent:'', attributes:{}, setAttribute(name,value) {this.attributes[name]=value;}};
  const task = {textContent:''};
  const dialog = {open:false, dataset:{}, attributes:{}, innerHTML:'',
    setAttribute(name,value) {this.attributes[name]=value;},
    querySelector:selector => ({'[data-workbench-payment-content]':content, '[data-workbench-payment-task]':task})[selector] || null,
    addEventListener(name,handler) {listeners[name]=handler;},
    showModal() {this.open=true;},
    close() {this.open=false; listeners.close?.();},
    getBoundingClientRect() {return {left:10,right:100,top:10,bottom:100};},
  };
  let appended = null;
  const root = {querySelector:selector => selector === '[data-workbench-payment-dialog]' ? appended : null,
    appendChild(node) {appended=node;}, querySelectorAll() {return [];}};
  view.document.createElement = () => dialog;
  view.api.setRoot(root);
  return {dialog, content, task, listeners};
}

test('支付入口点击后按需读取，加载与完成状态清晰且不会自动打开支付页面', async () => {
  const view = createView();
  const {dialog, content} = installPaymentDialog(view);
  const deferred = [];
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = (endpoint,options) => {
    view.requests.push({endpoint,options}); return new Promise(resolve => deferred.push(resolve));
  };
  let focused = 0;
  const request = view.api.showPaymentEntry(42, {isConnected:true, focus() {focused++;}});
  assert.equal(dialog.open, true);
  assert.equal(dialog.attributes['aria-labelledby'], 'extractWorkbenchPaymentTitle');
  assert.match(dialog.innerHTML, /data-workbench-close-payment.*aria-label="关闭支付入口"/);
  assert.match(content.innerHTML, /正在读取支付入口/);
  assert.equal(content.attributes['aria-busy'], 'true');
  assert.equal(view.requests[0].endpoint, '/api/extract-workbench/tasks/42/payment-entry');
  assert.equal(view.requests[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(view.requests[0].options.body), {});
  deferred[0]({ok:true,entry:{payment_page_url:'https://checkout.example.test/page', qr_data:'private-qr-data'}});
  await request;
  assert.equal(content.attributes['aria-busy'], 'false');
  assert.match(content.innerHTML, /private-qr-data/);
  await view.api.copyPaymentEntry('qr_data');
  assert.deepEqual(view.copied, ['private-qr-data']);
  assert.equal(view.api.state().qr_data, undefined);
  dialog.close();
  assert.equal(content.textContent, '');
  assert.equal(focused, 1);
  await view.api.copyPaymentEntry('qr_data');
  assert.equal(view.copied.length, 1);
});

test('关闭窗口或切换任务后迟到的支付入口响应不能覆盖当前内容', async () => {
  const view = createView();
  const {dialog, content} = installPaymentDialog(view);
  const deferred = [];
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = () => new Promise(resolve => deferred.push(resolve));
  const older = view.api.showPaymentEntry(41);
  dialog.close();
  const newer = view.api.showPaymentEntry(42);
  deferred[1]({ok:true,entry:{qr_data:'new-qr-data'}});
  await newer;
  deferred[0]({ok:true,entry:{qr_data:'old-qr-data'}});
  await older;
  assert.match(content.innerHTML, /new-qr-data/);
  assert.doesNotMatch(content.innerHTML, /old-qr-data/);
});

test('支付入口读取失败保留重试，二维码图片失败依次回退 SVG 和文字', async () => {
  const view = createView();
  const {content} = installPaymentDialog(view);
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async () => {throw new Error('平台暂不可用');};
  await view.api.showPaymentEntry(42);
  assert.match(content.innerHTML, /role="alert"/);
  assert.match(content.innerHTML, /平台暂不可用/);
  assert.match(content.innerHTML, /重新读取/);
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async () => ({ok:true, entry:{qr_image_url_png:'https://img.example.test/code.png',qr_image_url_svg:'https://img.example.test/code.svg'}});
  await view.api.showPaymentEntry(42);
  const fallback = {hidden:true};
  const image = {dataset:{},hidden:false,parentElement:{querySelector:() => fallback}};
  view.api.paymentQrError(image);
  assert.equal(image.src, 'https://img.example.test/code.svg');
  view.api.paymentQrError(image);
  assert.equal(image.hidden, true);
  assert.equal(fallback.hidden, false);
});

test('点击遮罩关闭支付入口，弹窗内部留白不触发关闭', async () => {
  const view = createView();
  const {dialog, listeners} = installPaymentDialog(view);
  view.window.__EXTRACT_WORKBENCH_DATA_SOURCE__ = async () => ({ok:true,entry:{}});
  await view.api.showPaymentEntry(42);
  listeners.click({target:dialog,clientX:50,clientY:50});
  assert.equal(dialog.open,true);
  listeners.click({target:dialog,clientX:5,clientY:5});
  assert.equal(dialog.open,false);
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
