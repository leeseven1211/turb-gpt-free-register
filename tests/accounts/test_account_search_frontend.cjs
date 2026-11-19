const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {createReadFixture,row,list,status,statusRow,deferred,ApiError} = require('./read_owner_fixture.cjs');
const inputOf = h => h.wrapper.get('#accountAdvancedSearchV2');
async function submit(h,value){await inputOf(h).setValue(value);await h.wrapper.get('form[role="search"]').trigger('submit');await h.settle();}

test('组合搜索原样提交，条件标签可单独移除并保留列筛选', async t => {
  const h=createReadFixture(t,{mounted:true,handlers:{list:async()=>list([row()],{search_terms:[{label:'注册出口',display_value:'日本 JP',query_without:'协议 备注:"a/b 待整理"'}]})}});await h.ready;
  h.owner.updateFilters({source:['outlook']});await h.settle();
  await submit(h,'协议/jp 备注:"a/b 待整理"');
  assert.equal(h.params().get('q'),'协议/jp 备注:"a/b 待整理"');
  assert.match(h.wrapper.get('[aria-label="已应用筛选"]').text(),/注册出口：日本 JP/);
  await h.wrapper.get('button[aria-label="移除注册出口：日本 JP"]').trigger('click');await h.settle();
  assert.equal(h.params().get('q'),'协议 备注:"a/b 待整理"');assert.equal(h.params().get('source'),'outlook');
  assert.equal(inputOf(h).element.ownerDocument.activeElement,inputOf(h).element);
});
test('条件回显转义输入文字，避免把备注作为 HTML 执行', async t => {
  const h=createReadFixture(t,{mounted:true,handlers:{list:async()=>list([row()],{search_terms:[{label:'备注',display_value:'<img src=x>',query_without:''}]})}});await h.ready;
  assert.equal(h.wrapper.find('img').exists(),false);assert.match(h.wrapper.text(),/<img src=x>/);
});
test('高级搜索和邮箱列筛选分别传递，并保留分页与归档条件', async t => {
  const h=createReadFixture(t,{handlers:{list:async()=>list([row()],{total:60})}});await h.ready;
  h.owner.updateQuery({q:'  协议注册  ',archived:'only',filters:{email:'example.test'}});await h.settle();h.owner.setPage(3);await h.settle();
  assert.equal(h.params().get('q'),'协议注册');assert.equal(h.params().get('email'),'example.test');assert.equal(h.params().get('archived'),'only');assert.equal(h.params().get('page'),'3');
});
test('中文组合输入完成后才搜索，连续输入合并请求并清除旧选择', async t => {
  const h=createReadFixture(t);await h.ready;t.mock.timers.enable({apis:['setTimeout']});
  h.owner.toggle('1',true);h.requests.length=0;h.owner.compositionStart();h.owner.setSearchDraft('xie');t.mock.timers.tick(250);h.owner.submitSearch();await h.settle();assert.equal(h.requests.length,0);
  h.owner.compositionEnd('协议');h.owner.setSearchDraft('协议注册');t.mock.timers.tick(250);await h.settle();
  assert.equal(h.requests.length,1);assert.equal(h.params().get('q'),'协议注册');assert.equal(h.params().get('page'),'1');assert.equal(h.owner.selected.value.size,0);
});
test('回车立即搜索并取消待执行的延迟请求', async t => {
  const h=createReadFixture(t);await h.ready;t.mock.timers.enable({apis:['setTimeout']});h.requests.length=0;
  h.owner.setSearchDraft('协议注册');h.owner.submitSearch();await h.settle();assert.equal(h.requests.length,1);t.mock.timers.tick(250);await h.settle();assert.equal(h.requests.length,1);
});
test('清空高级搜索保留列筛选并回到第一页，焦点返回输入框', async t => {
  const h=createReadFixture(t,{mounted:true,handlers:{list:async()=>list([row()],{total:60})}});await h.ready;
  h.owner.updateFilters({source:['icloud_hide']});await h.settle();await submit(h,'协议注册');h.owner.setPage(3);await h.settle();h.requests.length=0;
  await h.wrapper.get('button[aria-label="清空高级搜索"]').trigger('click');await h.settle();
  assert.equal(inputOf(h).element.value,'');assert.equal(inputOf(h).element.ownerDocument.activeElement,inputOf(h).element);
  assert.equal(h.requests.length,1);assert.equal(h.params().get('source'),'icloud_hide');assert.equal(h.params().get('page'),'1');assert.equal(h.params().get('q'),'');
});
test('清筛同时移除高级搜索和列条件，不留下延迟请求', async t => {
  const h=createReadFixture(t);await h.ready;t.mock.timers.enable({apis:['setTimeout']});
  h.owner.updateFilters({source:['icloud_hide']});await h.settle();h.requests.length=0;h.owner.setSearchDraft('协议注册');h.owner.resetFilters();await h.settle();t.mock.timers.tick(250);await h.settle();
  assert.equal(h.owner.draftSearch.value,'');assert.equal(h.requests.length,1);assert.equal(h.params().get('source'),'');assert.equal(h.params().get('page'),'1');
});
test('注册驱动变更回到第一页并重载，清筛移除驱动和其他列条件', async t => {
  const h=createReadFixture(t,{handlers:{list:async()=>list([row()],{total:60})}});await h.ready;h.owner.setPage(3);await h.settle();h.requests.length=0;
  h.owner.updateFilters({registration_driver:['protocol_oss','roxy']});await h.settle();
  assert.equal(h.requests.length,1);assert.equal(h.params().get('registration_driver'),'protocol_oss,roxy');assert.equal(h.params().get('page'),'1');
  h.owner.updateFilters({source:['icloud_hide']});await h.settle();h.owner.resetFilters();await h.settle();assert.equal(h.params().get('registration_driver'),'');assert.equal(h.params().get('source'),'');
});
test('切换搜索时丢弃旧请求结果，避免旧账号覆盖新条件', async t => {
  const pending=[];const h=createReadFixture(t,{handlers:{list:()=>{const call=deferred();pending.push(call);return call.promise;}}});await h.ready;
  h.owner.updateQuery({q:'浏览器注册'});await h.settle();assert.equal(h.requests.length,2);assert.equal(h.requests[0].signal.aborted,true);
  pending[0].resolve(list([row(1)],{total:25}));await h.settle();assert.equal(h.owner.items.value.length,0);assert.equal(h.params().get('q'),'浏览器注册');
  pending[1].resolve(list([row(2)],{total:60}));await h.settle();assert.deepEqual(h.plain(h.owner.items.value.map(item=>item.id)),[2]);
});
test('旧响应和轮询读取已提交搜索词，不会在中文组合输入中查询拼音', async t => {
  const pending=[];const h=createReadFixture(t,{handlers:{list:()=>{const call=deferred();pending.push(call);return call.promise;}}});await h.ready;
  h.owner.compositionStart();h.owner.setSearchDraft('xie');pending[0].resolve(list([row()]));await h.settle();
  assert.equal(h.requests.length,1);await h.owner.pollStatuses();assert.equal(h.statusRequests[0].spec.q,'');
  h.owner.compositionEnd('协议注册');h.owner.submitSearch();await h.settle();assert.equal(h.requests.length,2);assert.equal(h.params().get('q'),'协议注册');pending[1].resolve(list([row(2)]));await h.settle();
});
test('错误搜索显示行内提示并清除旧结果，修正后正常恢复', async t => {
  const h=createReadFixture(t,{mounted:true});await h.ready;
  h.behavior.list=async()=>{throw new ApiError('请填写有效国家代码',400,'account_search_invalid');};await submit(h,'地区:JJ');
  assert.equal(inputOf(h).attributes('aria-invalid'),'true');assert.match(h.wrapper.get('#accountAdvancedSearchErrorV2').text(),/有效国家代码/);assert.equal(h.wrapper.find('[data-account-row]').exists(),false);
  assert.match(h.wrapper.get('#accountsPageSummary').text(),/^0 个账号/);await h.owner.pollStatuses();assert.equal(h.statusRequests.length,0);
  h.behavior.list=async()=>list([row(9)],{search_terms:[{label:'注册出口',display_value:'日本 JP',query_without:'协议'}]});await submit(h,'协议 jp');
  assert.equal(h.wrapper.get('[data-account-row]').attributes('data-account-row'),'9');assert.equal(inputOf(h).attributes('aria-invalid'),undefined);assert.match(h.wrapper.text(),/日本 JP/);
});
test('过期搜索错误不会覆盖新条件或显示过期提示', async t => {
  const pending=[];const h=createReadFixture(t,{handlers:{list:()=>{const call=deferred();pending.push(call);return call.promise;}}});await h.ready;
  h.owner.updateQuery({q:'协议 jp'});await h.settle();pending[0].reject(new ApiError('过期错误',400,'account_search_invalid'));await h.settle();assert.notEqual(h.owner.error.value,'过期错误');assert.equal(pending.length,2);
  pending[1].resolve(list([row(9)]));await h.settle();assert.equal(h.owner.items.value[0].id,9);
});

test('API 错误保留业务错误码，供搜索框显示语法提示', async () => {
  const common = fs.readFileSync(path.join(__dirname, '../../webui/static/js/shared/common.js'), 'utf8');
  const start = common.indexOf('async function api(');
  const view = {
    API_INFLIGHT: new Map(),
    fetch: async () => ({ok: false, status: 400, json: async () => ({error: '国家代码有误', code: 'account_search_invalid'})}),
  };
  vm.createContext(view);
  vm.runInContext(common.slice(start, common.indexOf('\nasync function apiCached(', start)), view);
  await assert.rejects(view.api('/api/accounts?q=invalid'), error => error.message === '国家代码有误' && error.code === 'account_search_invalid');
  assert.equal(view.API_INFLIGHT.size, 0);
});


test('翻页后立即返回原页，较早发起的同页响应不会覆盖列表', async t => {
  const h=createReadFixture(t,{handlers:{list:async()=>list([row(5)],{total:60})}});await h.ready;
  const pending=[];h.behavior.list=()=>{const call=deferred();pending.push(call);return call.promise;};
  const old=h.owner.refresh();await h.settle();h.owner.setPage(2);await h.settle();h.owner.setPage(1);await h.settle();
  assert.equal(pending.length,3);assert.equal(h.requests.at(-3).signal.aborted,true);
  pending[0].resolve(list([row(6)],{total:60}));pending[1].resolve(list([row(8)],{total:60,page:2,offset:10}));await old;await h.settle();
  assert.deepEqual(h.plain(h.owner.items.value.map(item=>item.id)),[5]);
  assert.equal(h.params(h.requests.at(-3)).toString(),h.params(h.requests.at(-1)).toString());
  pending[2].resolve(list([row(7)],{total:60}));await h.settle();
  assert.deepEqual(h.plain(h.owner.items.value.map(item=>item.id)),[7]);
});

test('同页刷新后忽略迟到的轮询，新列表可接收与旧轮询相同版本的快照', async t => {
  const h=createReadFixture(t,{handlers:{list:async()=>list([row(7,{live_check_status:'queued'})]),statuses:async()=>status([statusRow(7,{live_check_status:'queued'})],{revision:'before',status_fields:['live_check_status']})}});await h.ready;
  await h.owner.pollStatuses();const delayed=deferred();h.behavior.statuses=()=>delayed.promise;const old=h.owner.pollStatuses();
  h.behavior.list=async()=>list([row(7,{live_check_status:'live'})]);await h.owner.refresh();
  delayed.resolve(status([statusRow(7,{live_check_status:'failed'})],{revision:'delayed',status_fields:['live_check_status']}));await old;
  assert.equal(h.owner.items.value[0].live_check_status,'live');
  h.behavior.statuses=async()=>status([statusRow(7,{live_check_status:'running'})],{revision:'before',status_fields:['live_check_status']});await h.owner.pollStatuses();
  assert.equal(h.owner.items.value[0].live_check_status,'running');
});

test('尚未载入的新页不发轮询，页内重复或换序时重新读取并保留上一页数据直至成功', async t => {
  for(const ids of [[7,7],[8,7]]){
    const h=createReadFixture(t,{handlers:{list:async()=>list([row(7),row(8)],{total:20})}});await h.ready;
    const pageRead=deferred();h.behavior.list=()=>pageRead.promise;h.owner.setPage(2);await h.settle();await h.owner.pollStatuses();assert.equal(h.statusRequests.length,0);
    h.owner.setPage(1);await h.settle();pageRead.resolve(list([row(7),row(8)],{total:20}));await h.settle();
    const fresh=deferred();h.behavior.list=()=>fresh.promise;
    h.behavior.statuses=async()=>status(ids.map(id=>statusRow(id,{live_check_status:'failed'})),{total:20,revision:'inconsistent',status_fields:['live_check_status']});
    const read=h.owner.pollStatuses();await h.settle();assert.equal(h.requests.at(-1).page,1);assert.equal(h.owner.loading.value,true);
    assert.deepEqual(h.plain(h.owner.items.value.map(item=>item.id)),[7,8]);assert.ok(h.owner.items.value.every(item=>!item.live_check_status));
    fresh.resolve(list([row(8),row(7)],{total:20}));await read;
    assert.deepEqual(h.plain(h.owner.items.value.map(item=>item.id)),[8,7]);
  }
});

test('总数收缩先修正页码，越界页的账号与筛选项不进入当前列表', async t => {
  const h=createReadFixture(t,{handlers:{list:async()=>list([row(55)],{total:60,facets:{source:[{value:'outlook',count:60}]}})}});await h.ready;
  const pending=[];h.behavior.list=()=>{const call=deferred();pending.push(call);return call.promise;};h.owner.setPage(3);await h.settle();
  pending[0].resolve(list([],{total:1,page:3,offset:20,facets:{source:[{value:'stale-out-of-bounds',count:1}]}}));await h.settle();
  assert.equal(h.owner.page.value,1);assert.deepEqual(h.plain(h.owner.items.value.map(item=>item.id)),[55]);
  assert.equal(h.owner.facets.value.source[0].value,'outlook');assert.equal(h.requests.at(-1).page,1);
  pending[1].resolve(list([row(7)],{total:1,facets:{source:[{value:'icloud_hide',count:1}]}}));await h.settle();
  assert.deepEqual(h.plain(h.owner.items.value.map(item=>item.id)),[7]);assert.equal(h.owner.facets.value.source[0].value,'icloud_hide');
});
