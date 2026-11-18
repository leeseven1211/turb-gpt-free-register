const test=require('node:test'),assert=require('node:assert/strict');
const {h,settle,supply,dashboard,mountDashboard,mountRegistration}=require('../webui/dashboard_vue_fixture.cjs');
test.after(()=>h.close());
test('注册统计仅用本地汇总，保留本地 HME 可用库存',async()=>{
 const {wrapper,calls}=await mountRegistration();assert.deepEqual(calls,['/api/summary']);assert.deepEqual(wrapper.findAll('.registration-summary strong').map(node=>node.text()),['24','20','12','6','2']);assert.match(wrapper.get('.registration-hint').text(),/本地库存/);assert.match(wrapper.get('.registration-hint').text(),/用完.*手动导入/);
});
test('汇总失败时库存显示读取失败，不保留旧数字或显示零',async()=>{
 const {wrapper,api}=await mountRegistration();api.summary=async()=>{throw Error('offline');};await wrapper.vm.loadSummary();await settle();assert.equal(wrapper.findAll('.registration-summary strong')[2].text(),'读取失败');
});
test('本地库存读取错误不回退兼容字段中的零',async()=>{
 const value={...supply(),status:'error',total:null,available:null,used:null,failed:null,reason:'本地库存读取失败'};
 const {wrapper}=await mountRegistration({accounts:24,outlook_total:0,outlook_available:0,email_supply:value});assert.deepEqual(wrapper.findAll('.registration-summary strong').slice(1).map(node=>node.text()),Array(4).fill('读取失败'));assert.match(wrapper.get('.registration-hint').text(),/本地库存读取失败/);
});
test('本地库存为空显示确定的零',async()=>{const {wrapper}=await mountRegistration({accounts:24,email_supply:{...supply(),total:0,available:0,used:0,failed:0}});assert.equal(wrapper.findAll('.registration-summary strong')[2].text(),'0');});
test('概览只读本地 dashboard 汇总，不请求远端库存接口',async()=>{const {wrapper,calls}=await mountDashboard();assert.deepEqual(calls.sort(),['/api/capabilities','/api/dashboard']);assert.equal(wrapper.get('[data-dashboard-card="metric-email"] strong').text(),'12');assert.match(wrapper.get('[data-dashboard-card="metric-email"]').text(),/本地/);});
test('本地库存详情优先五个池的数据，配置停用不隐藏库存',async()=>{const {wrapper}=await mountDashboard(dashboard({email:{supply:supply(),sources:[{source:'email_butler',label:'Butler连接',kind:'on_demand',enabled:true}]}}));const email=wrapper.get('[data-dashboard-card="panel-email"]');for(const key of ['outlook','generic_api','cloudflare_domain','icloud_hide','email_butler'])assert.match(email.text(),new RegExp(key));assert.doesNotMatch(email.text(),/Butler连接|按需|运行时租用/);assert.match(email.text(),/12/);});
