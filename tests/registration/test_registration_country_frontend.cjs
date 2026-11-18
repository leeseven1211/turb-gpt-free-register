const assert=require('node:assert/strict');
const test=require('node:test');
const {createConfigView,cleanup,navigation}=require('../config/vue_fixture.cjs');
function fields(driver='roxy'){return [
 {key:'REGISTRATION_DRIVER',label:'注册主流程驱动',type:'str',group:'注册主链路',value:driver,options:[{value:'roxy',label:'Roxy'},{value:'protocol_oss_2',label:'Proto2'}]},
 {key:'REGISTRATION_COUNTRY',label:'注册国家',type:'str',group:'注册主链路',value:'JP',country_codes:['JP','US','NA']},
 {key:'REGISTRATION_AUTH_MODE',label:'注册密码策略',type:'str',group:'注册主链路',value:'password',options:[{value:'password',label:'优先使用页面密码入口'}]},
 {key:'PROXY_POOL_DEFAULT_COUNTRY',label:'默认国家',type:'str',group:'代理与网络',value:'US',country_codes:['JP','US','NA']},
];}
test.afterEach(cleanup);
test('注册国家归入注册主链路基础流程，显示中文国家与代码下拉',async()=>{
 const view=createConfigView(fields());await view.open('注册主链路');
 const select=view.control('REGISTRATION_COUNTRY');
 assert.equal(select.element.value,'JP');
 assert.ok(select.findAll('option').some(option=>option.attributes('value')==='JP'&&option.text()==='日本 · JP'));
 assert.ok(select.findAll('option').some(option=>option.attributes('value')==='NA'&&option.text()==='纳米比亚 · NA'));
 const keys=view.wrapper.findAll('[data-config-setting]').map(item=>item.attributes('data-config-setting'));
 assert.ok(keys.indexOf('REGISTRATION_DRIVER')<keys.indexOf('REGISTRATION_COUNTRY'));
 assert.ok(keys.indexOf('REGISTRATION_COUNTRY')<keys.indexOf('REGISTRATION_AUTH_MODE'));
});
test('注册国家草稿独立于池默认国家并保留NA，不被空占位规则吞掉',async()=>{
 const view=createConfigView(fields());await view.open('注册主链路');
 await view.control('REGISTRATION_COUNTRY').setValue('NA');
 view.owner.setField('PROXY_POOL_DEFAULT_COUNTRY','JP');
 assert.equal(view.owner.readField('REGISTRATION_COUNTRY'),'NA');
 await view.open('代理与网络');
 assert.match(view.wrapper.text(),/注册主链路的注册国家/);
 view.owner.setField('PROXY_POOL_DEFAULT_COUNTRY','US');await view.open('注册主链路');
 assert.equal(view.control('REGISTRATION_COUNTRY').element.value,'NA');
});
test('注册配置缺省使用本地Roxy且历史值映射到现行驱动',()=>{
 assert.equal(navigation.registrationDriverValue(undefined),'roxy');
 for(const [previous,current] of [['','roxy'],['protocol','protocol_oss_2'],['protocol_oss','protocol_oss_2'],['roxy_oss','roxy']])assert.equal(navigation.registrationDriverValue(previous),current);
});
