const assert = require('node:assert/strict');
const test = require('node:test');
const {ownerFixture, deferred, response, flush, createRegistrationApi} = require('./registration_vue_owner_fixture.cjs');

test('首次读取最新批次，不恢复 localStorage 中的历史批次', async t => {
  window.localStorage.setItem('gpt_console_registration_batch_id', 'stale-batch');
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  assert.equal(h.calls.length, 1);
  assert.equal(String(h.calls[0].params.progress_batch_id || ''), '');
  h.calls[0].resolve(response('latest'));
  await flush();
  assert.equal(h.owner.state.batch.batch_id, 'latest');
});

test('注册隐藏页不读；显示后同签名 automatic 合并在途读取', async t => {
  const h = ownerFixture(t);
  await h.owner.load({automatic: true});
  await h.owner.loadSummary();
  assert.equal(h.calls.length, 0);
  assert.equal(h.intervals.size, 0);
  h.owner.setVisible(true);
  const coalesced = h.owner.load({automatic: true});
  assert.equal(h.calls.length, 1);
  h.calls[0].resolve(response('active'));
  await coalesced;
  await flush();
  assert.equal(h.owner.state.batch.batch_id, 'active');
});

test('切换批次立即读取，旧响应不覆盖新批次或解除当前 loading', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  const newer = h.owner.load({progress_batch_id: 'new'});
  assert.equal(h.calls.length, 2, 'switch must supersede the pending old GET');
  assert.equal(h.calls[1].params.progress_batch_id, 'new');
  h.calls[0].resolve(response('old'));
  await flush();
  assert.equal(h.owner.state.loading, true);
  assert.equal(h.owner.state.batch, null);
  h.calls[1].resolve(response('new'));
  await newer;
  assert.equal(h.owner.state.batch.batch_id, 'new');
});

test('A→B→A 创建新的读取代次，首个 A 不能覆盖最后选择', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  h.calls[0].resolve(response('initial'));
  await flush();
  const a = h.owner.load({progress_batch_id: 'A'});
  const b = h.owner.load({progress_batch_id: 'B'});
  const latest = h.owner.load({progress_batch_id: 'A'});
  assert.equal(h.calls.length, 4);
  h.calls[1].resolve(response('A', 'failed'));
  h.calls[2].resolve(response('B', 'success'));
  await Promise.all([a, b]);
  assert.equal(h.owner.state.batch, null);
  assert.equal(h.owner.state.loading, true);
  h.calls[3].resolve(response('A', 'running'));
  await latest;
  assert.equal(h.owner.state.batch.items[0].status, 'running');
});

test('批次与任务表读取隔离，表筛选分页在自动轮询中持久保留', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  h.owner.setView('tasks');
  const filtered = h.owner.load({page: 2, page_size: 20, email: 'fixture+filter', status: 'failed'});
  assert.equal(h.calls.at(-1).params.view, 'table');
  assert.equal(h.calls.at(-1).params.page, 2);
  h.calls.at(-1).resolve({items: [{id: '9007199254740993'}], total: 25, facets: {}});
  await filtered;
  await h.tick();
  assert.equal(h.calls.at(-1).params.page, 2);
  assert.equal(h.calls.at(-1).params.page_size, 20);
  assert.equal(h.calls.at(-1).params.email, 'fixture+filter');
  assert.equal(h.calls.at(-1).params.status, 'failed');
  h.calls.at(-1).resolve({items: [{id: '9007199254740993'}], total: 25});
  await flush();
  h.calls[0].resolve(response('old-batch'));
  await flush();
  assert.equal(h.owner.state.jobs[0].id, '9007199254740993');
});

test('完成批次停止自动 jobs 读取，显式刷新和重新进入仍可读取', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  h.calls[0].resolve(response('done', 'success'));
  await flush();
  await h.tick();
  assert.equal(h.calls.length, 1, 'terminal batch must not keep polling jobs');
  const manual = h.owner.load();
  assert.equal(h.calls.length, 2);
  h.calls[1].resolve(response('done', 'success'));
  await manual;
  h.owner.setVisible(false);
  h.owner.setVisible(true);
  assert.equal(h.calls.length, 3);
});

test('投影延迟继续轮询，清除延迟后的终态暂停 jobs 读取', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  const delayed = response('delayed', 'success');
  delayed.progress_batch.projection_delayed = true;
  h.calls[0].resolve(delayed);
  await flush();
  await h.tick();
  assert.equal(h.calls.length, 2);
  h.calls[1].resolve(response('delayed', 'success'));
  await flush();
  await h.tick();
  assert.equal(h.calls.length, 2);
});

test('文档隐藏作废旧请求并解除旧 loading，恢复可见立即重新读', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  h.hideDocument(true);
  assert.equal(h.owner.state.loading, false);
  assert.equal(h.intervals.size, 0);
  h.hideDocument(false);
  assert.equal(h.calls.length, 2);
  h.calls[0].resolve(response('stale'));
  await flush();
  assert.equal(h.owner.state.batch, null);
  assert.equal(h.owner.state.loading, true);
  h.calls[1].resolve(response('fresh'));
  await flush();
  assert.equal(h.owner.state.batch.batch_id, 'fresh');
});

test('显示→隐藏→显示后旧 summary 也不得覆盖新一轮状态', async t => {
  const first = deferred(), second = deferred();
  let count = 0;
  const h = ownerFixture(t, {api: {summary: () => ++count === 1 ? first.promise : second.promise}});
  h.owner.setVisible(true);
  h.owner.setVisible(false);
  h.owner.setVisible(true);
  second.resolve({accounts: 2, email_supply: {available: 0}});
  await flush();
  first.resolve({accounts: 99, email_supply: {available: 99}});
  await flush();
  assert.equal(h.owner.state.summary.accounts, 2);
  assert.equal(h.owner.state.summary.email_supply.available, 0);
});

test('慢summary跨越多次十秒定时器仍只读一次并正常发布，显式刷新仍作废旧读取',async t=>{
  const reads=[];
  const h=ownerFixture(t,{api:{summary:signal=>{
    const pending=deferred();reads.push({signal,...pending});return pending.promise;
  }}});
  h.owner.setVisible(true);
  assert.equal(reads.length,1);
  const timer=[...h.intervals.values()].find(item=>item.milliseconds===10000);
  assert.ok(timer);
  timer.callback();timer.callback();await flush();
  assert.equal(reads.length,1,'slow automatic summary must not be restarted every ten seconds');
  assert.equal(reads[0].signal.aborted,false);
  reads[0].resolve({accounts:4,email_supply:{available:2}});
  await flush();
  assert.equal(h.owner.state.summary.accounts,4);
  timer.callback();
  assert.equal(reads.length,2,'the next interval can read after the old response settles');
  const manual=h.owner.loadSummary();
  assert.equal(reads.length,3,'manual refresh remains immediate');
  assert.equal(reads[1].signal.aborted,true);
  reads[2].resolve({accounts:8});await manual;
  reads[1].resolve({accounts:99});await flush();
  assert.equal(h.owner.state.summary.accounts,8);
});

test('新建受理后越过旧挂起 GET 立即查询新批次；旧 GET 不得覆盖回执', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  const submit = h.owner.create({count: 2, workers: 50, email_source: 'outlook', debug_enabled: true});
  h.writes[0].resolve({submitted: 2, workers: 50, jobs: [{id: '9007199254740993', batch_id: 'created'}]});
  await submit;
  assert.equal(h.calls.length, 2);
  assert.equal(h.calls[1].params.progress_batch_id, 'created');
  assert.equal(h.owner.state.receipt.message.includes('2'), true);
  h.calls[0].resolve(response('old', 'failed'));
  await flush();
  assert.equal(h.owner.state.loading, true);
  assert.notEqual(h.owner.state.batch?.batch_id, 'old');
  h.calls[1].reject(new Error('follow-up read failed'));
  await flush();
  assert.equal(h.owner.state.receipt.tone, 'success');
  assert.equal(h.owner.state.error, 'follow-up read failed');
  assert.equal(h.writes.length, 1);
});

test('重复点击新建只发一次 POST，受理回执即使页面隐藏也保留且不重放', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  const payload = {count: 1, workers: 100, email_source: 'outlook', debug_enabled: false};
  const one = h.owner.create(payload), two = h.owner.create(payload);
  assert.equal(h.writes.length, 1, 'pending create must have one outbound POST');
  h.owner.setVisible(false);
  h.writes[0].resolve({submitted: 1, jobs: [{id: '9007199254740993', batch_id: 'accepted'}]});
  await Promise.all([one, two]);
  assert.equal(h.owner.state.receipt.tone, 'success');
  assert.equal(h.calls.length, 1);
  h.owner.setVisible(true);
  assert.equal(h.writes.length, 1);
  assert.equal(h.calls.at(-1).params.progress_batch_id, 'accepted');
});

test('同批次重跑受理后显式 GET 作废旧失败 GET，保留调试 payload', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  h.calls[0].resolve(response('same', 'failed'));
  await flush();
  const old = h.owner.load();
  const retry = h.owner.action('/api/jobs/retry-bulk', {job_ids: ['9007199254740993'], debug_enabled: true});
  assert.deepEqual(h.writes[0].payload, {job_ids: ['9007199254740993'], debug_enabled: true});
  h.writes[0].resolve({batch_id: 'same', started_count: 1, message: '已提交重跑'});
  await retry;
  assert.equal(h.calls.length, 3);
  assert.notEqual(h.calls[1].params.refresh_generation, h.calls[2].params.refresh_generation);
  h.calls[1].resolve(response('same', 'failed'));
  await old;
  assert.equal(h.owner.state.loading, true);
  h.calls[2].resolve(response('same', 'running'));
  await flush();
  assert.equal(h.owner.state.batch.items[0].status, 'running');
  assert.equal(h.owner.state.receipt.message, '已提交重跑');
});

test('摘要有所选批次但详情空缺时正常收口，不等待自己的在途请求', async t => {
  const h = ownerFixture(t);
  h.owner.setVisible(true);
  h.calls[0].resolve({items: [], progress_batch: null, progress_batches: [{batch_id: 'delayed'}]});
  await flush();
  assert.equal(h.owner.state.loading, false);
});

test('真实 typed API 对 bigint 响应与 retry/OTP body 保留十进制精度', async t => {
  const original = global.fetch, requests = [];
  t.after(() => {global.fetch = original;});
  global.fetch = async (url, options = {}) => {
    requests.push({url, options});
    return new Response('{"items":[{"id":9007199254740993,"operation_task_id":9007199254740995}],"total":1}', {headers: {'Content-Type': 'application/json'}});
  };
  const api = createRegistrationApi();
  const result = await api.jobs({view: 'table', page: 2, page_size: 20, email: 'fixture+filter'});
  assert.equal(result.items[0].id, '9007199254740993');
  assert.equal(result.items[0].operation_task_id, '9007199254740995');
  await api.action('/api/jobs/retry-bulk', {job_ids: ['9007199254740993'], debug_enabled: true});
  assert.equal(JSON.parse(requests[1].options.body).job_ids[0], '9007199254740993');
  await api.action('/api/manual-otp', {job_id: '9007199254740993', email: 'fixture@example.invalid', code: '123456'});
  assert.equal(JSON.parse(requests[2].options.body).job_id, '9007199254740993');
});

test('table 自动轮询30秒内省略 facets，手动刷新和新筛选立即刷新统计', async t => {
  let now=1000;
  const original=Date.now;t.after(()=>{Date.now=original;});Date.now=()=>now;
  const h=ownerFixture(t,{deps:{view:'tasks'}});
  h.owner.setVisible(true);
  h.calls[0].resolve({items:[],total:0,facets:{status:[{value:'running',count:7}]},status_counts:{running:7}});
  await flush();
  const automatic=h.owner.load({automatic:true});
  assert.equal(h.calls[1].params.include_facets,0);
  h.calls[1].resolve({items:[],total:0});
  await automatic;
  assert.equal(h.owner.state.statusCounts.running,7);
  assert.equal(h.owner.state.facets.status[0].count,7);
  now+=31000;
  const expired=h.owner.load({automatic:true});
  assert.notEqual(h.calls[2].params.include_facets,0);
  h.calls[2].resolve({items:[],total:0,facets:{},status_counts:{}});
  await expired;
  assert.deepEqual({...h.owner.state.statusCounts},{});
  const manual=h.owner.load();
  assert.notEqual(h.calls[3].params.include_facets,0);
  h.calls[3].resolve({items:[],total:0,facets:{}});
  await manual;
});

test('表总数缩小时修正到最后一页，旧回包不可覆盖修正结果', async t => {
  const h=ownerFixture(t,{deps:{view:'tasks'}});
  h.owner.setVisible(true);
  const fourth=h.owner.load({page:4,page_size:20});
  h.calls[1].resolve({items:[],total:21});
  await flush();
  assert.equal(h.calls.length,3);
  assert.equal(h.calls[2].params.page,2);
  h.calls[2].resolve({items:[{id:'21'}],total:21});
  await fourth;
  h.calls[0].resolve({items:[{id:'999'}],total:999});
  await flush();
  assert.equal(h.owner.state.query.page,2);
  assert.equal(h.owner.state.jobs[0].id,'21');
});

test('外部隐藏注册页打开日志仍独立轮询，文档隐藏和关闭则停止', async t => {
  let logs=0;
  const h=ownerFixture(t,{api:{log:async id=>{logs++;return {job:{id,status:'running'},log:`log ${id}`};}}});
  h.owner.openLog('9007199254740993');
  await flush();
  assert.equal(h.calls.length,0,'hidden registration list must stay idle');
  assert.equal(logs,1);
  assert.equal(h.timeouts.size,1);
  const poll=[...h.timeouts.values()][0];h.timeouts.clear();poll.callback();
  await flush();
  assert.equal(logs,2);
  h.hideDocument(true);
  assert.equal(h.timeouts.size,0);
  h.hideDocument(false);
  await flush();
  assert.equal(logs,3);
  h.owner.closeDetail();
  assert.equal(h.timeouts.size,0);
  assert.equal(h.owner.state.detail.id,null);
});

test('日志debug诊断串联每次await后核对代次，旧debug不能触发旧诊断或写入新详情', async t => {
  const oldDebug=deferred(),diagnostics=[];
  const h=ownerFixture(t,{api:{
    log:async id=>({job:{id,status:'success'},log:`log ${id}`}),
    debug:id=>String(id)==='1'?oldDebug.promise:Promise.resolve({enabled:true,job_id:id,events:[]}),
    diagnostics:async id=>{diagnostics.push(id);return {enabled:true,captured:true};},
  }});
  h.owner.openLog(1);await flush();
  h.owner.closeDetail();h.owner.openLog(2);await flush();
  oldDebug.resolve({enabled:false,job_id:1});await flush();
  assert.equal(h.owner.state.detail.id,2);
  assert.equal(h.owner.state.detail.debug.job_id,2);
  assert.equal(h.owner.state.detail.diagnostics,null);
  assert.deepEqual(diagnostics,[]);
});

test('旧compare响应不能覆盖重新打开的日志，失败诊断也不能晚写', async t => {
  const comparison=deferred(),oldDiagnostics=deferred();
  const h=ownerFixture(t,{api:{
    log:async id=>({job:{id,status:'success'},log:`log ${id}`}),
    debug:async()=>({enabled:false}),
    diagnostics:id=>String(id)==='1'?oldDiagnostics.promise:Promise.resolve({enabled:true,captured:true,job_id:id}),
    compare:()=>comparison.promise,
  }});
  h.owner.openLog(1);await flush();
  const oldCompare=h.owner.compare(1);
  h.owner.closeDetail();h.owner.openLog(2);await flush();
  oldDiagnostics.resolve({enabled:true,captured:true,job_id:1});
  comparison.resolve({baseline_job_id:1,differences:[]});
  assert.equal(await oldCompare,null);
  await flush();
  assert.equal(h.owner.state.detail.diagnostics.job_id,2);
  assert.equal(h.owner.state.detail.comparison,null);
});

test('相同在途任务动作只发一个POST，失败后可见恢复不会自动重放',async t=>{
  const h=ownerFixture(t);
  const payload={job_ids:['9007199254740993'],debug_enabled:false};
  const first=h.owner.action('/api/jobs/retry-bulk',payload);
  const second=h.owner.action('/api/jobs/retry-bulk',payload);
  assert.equal(h.writes.length,1);
  const a=assert.rejects(first,/transport response missing/);
  const b=assert.rejects(second,/transport response missing/);
  h.writes[0].reject(new Error('transport response missing'));
  await Promise.all([a,b]);
  assert.equal(h.owner.state.receipt.tone,'danger');
  h.owner.setVisible(true);
  h.calls[0].resolve(response('existing'));
  await flush();await h.tick();
  assert.equal(h.writes.length,1);
  assert.equal(h.owner.state.receipt.tone,'danger');
});

test('自动刷新共享同签名Promise与generation，显式刷新创建新代次',async t=>{
  const h=ownerFixture(t);
  h.owner.setVisible(true);h.calls[0].resolve(response('active'));await flush();
  const poll=h.owner.load({automatic:true}),shared=h.owner.load({automatic:true});
  assert.equal(poll,shared);
  assert.equal(h.calls.length,2);
  assert.equal(h.calls[1].params.refresh_generation,h.calls[0].params.refresh_generation);
  const manual=h.owner.load();
  assert.equal(h.calls.length,3);
  assert.notEqual(h.calls[2].params.refresh_generation,h.calls[1].params.refresh_generation);
  h.calls[1].resolve(response('active','failed'));await poll;
  assert.equal(h.owner.state.loading,true);
  h.calls[2].resolve(response('active','running'));await manual;
  assert.equal(h.owner.state.batch.items[0].status,'running');
});

test('已选批次不存在时读取服务端最新批次，正常收口且无自等待',async t=>{
  const h=ownerFixture(t);
  h.owner.setVisible(true);h.calls[0].resolve(response('initial'));await flush();
  const selected=h.owner.setBatch('deleted-batch');
  h.calls[1].resolve({items:[],progress_batch:null,progress_batches:[{batch_id:'latest-batch'}]});
  await flush();
  assert.equal(h.calls.length,3);
  assert.equal(h.calls[2].params.progress_batch_id,'latest-batch');
  h.calls[2].resolve(response('latest-batch'));
  await selected;
  assert.equal(h.owner.state.batchId,'latest-batch');
  assert.equal(h.owner.state.batch.batch_id,'latest-batch');
  assert.equal(h.owner.state.loading,false);
});
