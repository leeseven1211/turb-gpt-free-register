const test=require('node:test'),assert=require('node:assert/strict');
const {h,model,dashboard,mountDashboard,settle}=require('./dashboard_vue_fixture.cjs');
const cards=['email','accounts','codex','extract','plans','proxy','jobs'];
const card=(wrapper,id)=>wrapper.get(`[data-overview-card="${id}"]`);
test.after(()=>h.close());
test('dashboard proxy labels preserve current and historical identities',async()=>{
 for(const [platform,label]of [['1024proxy','1024Proxy'],['711proxy','711Proxy'],['manual','手动代理池'],['1024','1024Proxy'],['pool','静态代理池'],['none','直连'],['direct','直连']]){
  const {wrapper}=await mountDashboard(dashboard({proxy:{platform,active_leases:1,leases:[{provider:'old-provider',endpoint:'old-exit'}]}}));
  assert.equal(model.proxyLabel(platform),label);assert.match(card(wrapper,'proxy').text(),new RegExp(label));assert.match(card(wrapper,'proxy').text(),/old-exit/);
 }
 assert.equal(model.proxyLabel(' 711PROXY '),'711Proxy');
});
test('dashboard proxy summary keeps at most three rendered exit leases and explains remaining exits',async()=>{
 const {wrapper}=await mountDashboard();assert.equal(wrapper.findAll('.ov-lease-list li').length,3);assert.match(card(wrapper,'proxy').text(),/另有 1 个活跃出口/);assert.equal(card(wrapper,'proxy').get('.ov-figure strong').text(),'4');
});
test('dashboard fixed areas retain historical data while showing disabled capabilities',async()=>{
 const {wrapper}=await mountDashboard(dashboard(),{email_sources:{icloud_hide:{enabled:false}},features:{register:{enabled:false}},proxy:{registration:{enabled:false}}});
 assert.deepEqual(wrapper.findAll('[data-overview-card]').map(row=>row.attributes('data-overview-card')),cards);
 assert.match(card(wrapper,'jobs').text(),/注册功能未启用/);assert.match(card(wrapper,'jobs').text(),/停止中1/);
 assert.match(card(wrapper,'proxy').text(),/注册代理未启用/);assert.match(card(wrapper,'email').text(),/icloud_hide/);assert.match(card(wrapper,'email').text(),/可用 12/);
});
test('dashboard fixed order ignores obsolete custom layout preferences',async()=>{
 const old={order:{metrics:['metric-jobs'],panels:['panel-proxy']},hidden:['metric-accounts','panel-email'],sizes:{'panel-email':'full'},heights:{'panel-proxy':999}};
 const {wrapper}=await mountDashboard(dashboard(),{},old);
 assert.deepEqual(wrapper.findAll('[data-overview-card]').map(row=>row.attributes('data-overview-card')),cards);
 assert.deepEqual(wrapper.findAll('.ov-pulse-top').map(row=>row.text()),['邮箱','账号','Codex','套餐','提炼','代理','任务']);
 assert.deepEqual(JSON.parse(localStorage.getItem('gpt_console_overview_preferences_v1')),old);
 assert.equal(wrapper.find('[data-overview-resize]').exists(),false);assert.equal(wrapper.find('[draggable="true"]').exists(),false);
});
test('dashboard legacy layout entrypoints remain harmless and preserve all areas',async()=>{
 const {wrapper}=await mountDashboard();for(const name of ['openCustomizer','closeCustomizer','resetLayout']){assert.equal(typeof wrapper.vm[name],'function');wrapper.vm[name]();}
 await settle();assert.deepEqual(wrapper.findAll('[data-overview-card]').map(row=>row.attributes('data-overview-card')),cards);assert.equal(wrapper.find('dialog').exists(),false);
});
test('dashboard every area action navigates to its current page',async()=>{
 const {wrapper,navigations}=await mountDashboard();for(const id of ['email','accounts','codex','extract','plans','proxy','jobs'])await wrapper.get(`[data-overview-action="${id}"]`).trigger('click');
 assert.deepEqual(navigations,['outlook','accounts','codex','extract-workbench','accounts','proxy-traffic','tasks']);
});
test('dashboard pulse navigation preserves all seven destination identities',async()=>{
 const {wrapper,navigations}=await mountDashboard();for(const button of wrapper.findAll('.ov-pulse-item'))await button.trigger('click');
 assert.deepEqual(navigations,['outlook','accounts','codex','accounts','extract-workbench','proxy-traffic','tasks']);
});
test('dashboard fixed areas retain aggregate queue history health and Codex progress',async()=>{
 const {wrapper}=await mountDashboard();assert.match(card(wrapper,'email').text(),/可用.*邮箱总量20.*已使用6.*停用 \/ 失败2/);
 const jobs=card(wrapper,'jobs');assert.match(jobs.text(),/当前队列.*运行中2.*待处理3.*停止中1/);assert.match(jobs.text(),/今日结果.*成功10.*部分成功3.*失败2/);assert.match(jobs.text(),/累计结果.*成功 10.*部分成功 3.*失败 2.*停止\/取消 2/);
 assert.match(card(wrapper,'codex').text(),/已导出3.*待导出1.*账号就绪4/);
});
test('dashboard inventory uses local supply and renders every nonempty source and plan',async()=>{
 const data=dashboard({email:{supply:{status:'known',total:5,available:3,used:2,sources:[{source:'local-a',label:'Local A',kind:'local_pool',total:3,available:2},{source:'local-b',label:'Local B',kind:'local_pool',total:2,available:1}]},sources:[{source:'remote',label:'Remote 999',enabled:true,available:999}]}});
 const {wrapper}=await mountDashboard(data);assert.equal(card(wrapper,'email').get('.ov-figure strong').text(),'3');assert.match(card(wrapper,'email').text(),/Local A.*Local B/);assert.doesNotMatch(card(wrapper,'email').text(),/Remote|999/);assert.equal(card(wrapper,'plans').findAll('.ov-bars li').length,5);
 const fallback=await mountDashboard(dashboard({email:{sources:[{source:'remote',label:'Remote 999',enabled:true,available:999,total:999}]}}));assert.doesNotMatch(card(fallback.wrapper,'email').text(),/Remote|999/);
});
test('dashboard priority results remain visible without compact clipping',async()=>{
 const {wrapper}=await mountDashboard();const blocks=card(wrapper,'jobs').findAll('.ov-task-block');assert.equal(blocks.length,3);assert.match(blocks[0].text(),/停止中1/);assert.match(blocks[1].text(),/部分成功3/);assert.match(blocks[2].text(),/部分成功 3/);assert.equal(card(wrapper,'plans').findAll('.ov-bars li').length,5);
});
test('dashboard single owner coalesces pending refreshes and stops twenty-second polling while hidden',async()=>{
 h.cleanup();Object.defineProperty(h.document,'hidden',{configurable:true,value:false});const priorSet=window.setInterval,priorClear=window.clearInterval,timers=new Map();let timerId=0,resolve,calls=0;window.setInterval=(fn,ms)=>{const id=++timerId;timers.set(id,{fn,ms});return id;};window.clearInterval=id=>timers.delete(id);
 try{const component=h.load('src/features/dashboard/DashboardPage.vue').default;const wrapper=h.mount(component,{props:{api:{dashboard:()=>{calls++;return new Promise(done=>{resolve=done;});},capabilities:async()=>({})},deps:{visible:false}}});await wrapper.vm.load();assert.equal(calls,0);wrapper.vm.setVisible(true);const a=wrapper.vm.load(),b=wrapper.vm.load();assert.equal(calls,1);assert.equal([...timers.values()][0].ms,20000);resolve(dashboard());await Promise.all([a,b]);await settle();[...timers.values()][0].fn();assert.equal(calls,2);wrapper.vm.setVisible(false);assert.equal(timers.size,0);resolve(dashboard({accounts:{total:99,active:99}}));await settle();assert.notEqual(card(wrapper,'accounts').get('.ov-figure strong').text(),'99');}
 finally{h.cleanup();window.setInterval=priorSet;window.clearInterval=priorClear;}
});
