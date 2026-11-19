const assert = require('node:assert/strict');
const test = require('node:test');
const {harness, field, createConfigView, cleanup, flush, navigation} = require('./vue_fixture.cjs');
const {ConfigApiError} = harness.load('src/api/config.ts');
const completeSchema = require('../../frontend/src/features/config/schemaNavigation.fixture.json');
test.afterEach(cleanup);
const providerFields = () => [
  field('EXTRACT_LINK_ENABLED', '提链', {type: 'bool', value: true}),
  field('EXTRACT_LINK_DEFAULT_PROVIDER', '提链', {value: 'legacy', options: [{value:'legacy',label:'虾扯蛋链'},{value:'huanguang',label:'幻光'}]}),
  field('EXTRACT_LINK_LEGACY_ENABLED', '提链', {type:'bool',value:true}),
  field('EXTRACT_LINK_HUANGUANG_ENABLED', '提链', {type:'bool',value:false}),
  field('EXTRACT_LINK_CDK', '提链', {secret:true,configured:true}),
  field('EXTRACT_LINK_HUANGUANG_CDK', '提链', {secret:true,configured:true}),
];
const activeMenu = view => view.wrapper.get('[data-config-nav][aria-current="page"]').attributes('data-config-nav');
const activeDomain = view => view.wrapper.get('[data-config-section]').attributes('data-config-section');
const activeSection = view => view.wrapper.get('[data-config-subsection][aria-pressed="true"]').attributes('data-config-subsection');

test('AT 失效自动刷新开关只在查询套餐中展示并可搜索定位', async () => {
 const view=createConfigView([field('PLAN_CHECK_AUTO_REFRESH_AT_ENABLED','代理与网络',{type:'bool',value:true,label:'AT 失效时自动刷新'}),field('ACCOUNT_AT_REFRESH_DRIVER','账号补全')]);
 await view.search('PLAN_CHECK_AUTO_REFRESH_AT_ENABLED');assert.equal(activeMenu(view),'注册与账号');assert.equal(activeDomain(view),'注册与账号');assert.equal(view.control('PLAN_CHECK_AUTO_REFRESH_AT_ENABLED').element.checked,true);assert.equal(view.wrapper.findAll('[data-key="PLAN_CHECK_AUTO_REFRESH_AT_ENABLED"]').length,1);assert.equal(view.wrapper.find('[data-key="ACCOUNT_AT_REFRESH_DRIVER"]').exists(),false);
});
test('提链独立支付分类只呈现公共XXSYUN配置，搜索Key会定位该分类', async () => {
 const view=createConfigView([...providerFields(),field('EXTRACT_LINK_LEGACY_AUTO_PAYMENT_SOURCE','提链'),field('EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY','提链',{secret:true}),field('EXTRACT_LINK_PAYMENT_XXSYUN_CONCURRENCY','提链',{type:'int',value:1})]);
 assert.equal(view.wrapper.find('[data-key="EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"]').exists(),false);await view.search('EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY');assert.equal(activeSection(view),'独立支付');assert.ok(view.control('EXTRACT_LINK_PAYMENT_XXSYUN_CONCURRENCY').exists());assert.equal(view.wrapper.find('[data-key="EXTRACT_LINK_LEGACY_AUTO_PAYMENT_SOURCE"]').exists(),false);assert.equal(view.wrapper.find('[data-key="EXTRACT_LINK_ENABLED_PROVIDERS"]').exists(),false);
});
test('搜索授权后自动上传开关会定位 sub2api 子节并呈现独立开关', async () => {
 const view=createConfigView([field('CODEX_AUTH_URL_SOURCE','Codex'),field('SUB2API_API_BASE','Codex'),field('CODEX_OAUTH_AUTO_UPLOAD_SUB2API','Codex',{type:'bool',value:false})]);await view.search('CODEX_OAUTH_AUTO_UPLOAD_SUB2API');assert.equal(activeMenu(view),'服务集成');assert.equal(activeSection(view),'sub2api');assert.equal(view.control('CODEX_OAUTH_AUTO_UPLOAD_SUB2API').attributes('type'),'checkbox');assert.equal(view.wrapper.find('[data-key="CODEX_AUTH_URL_SOURCE"]').exists(),false);
});
test('C2A 在服务集成中独立呈现，显式打开不被已记忆的Codex领域覆盖', async () => {
 const view=createConfigView([field('CODEX_AUTH_URL_SOURCE','Codex'),field('C2A_API_BASE','C2A',{help:'仅定位同邮箱既有账号并更新 AT。'}),field('C2A_API_KEY','C2A',{secret:true}),field('C2A_API_TIMEOUT','C2A',{type:'int',value:20})]);await view.wrapper.get('[data-config-domain-v2="Codex"]').trigger('click');await view.open('C2A');assert.equal(activeMenu(view),'服务集成');assert.equal(activeDomain(view),'C2A');assert.equal(localStorage.getItem('gpt_console_config_group'),'C2A');for(const key of ['C2A_API_BASE','C2A_API_KEY','C2A_API_TIMEOUT'])assert.ok(view.control(key).exists());assert.match(view.wrapper.text(),/仅定位同邮箱既有账号并更新 AT。/);await view.open('Codex');await view.search('C2A_API_KEY');assert.equal(activeDomain(view),'C2A');
});
test('幻光 XXSYUN Key 使用密码框、显式清除及查询次数，转单开关默认关闭', async () => {
 const view=createConfigView([...providerFields(),field('EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY','提链',{secret:true,configured:true}),field('EXTRACT_LINK_HUANGUANG_XXSYUN_AUTO_TRANSFER_ENABLED','提链',{type:'bool',value:false})]);await view.search('EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY');assert.equal(view.control('EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY').attributes('type'),'password');assert.ok(view.wrapper.get('[aria-label="明确清除EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY"]').exists());assert.match(view.wrapper.text(),/查询剩余次数/);assert.equal(view.control('EXTRACT_LINK_HUANGUANG_XXSYUN_AUTO_TRANSFER_ENABLED').element.checked,false);
});
test('XXSYUN查询区分已保存Key、未保存输入和明确清空，保留真实零且不保存配置', async () => {
 const bodies=[];const key='EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY';const view=createConfigView([...providerFields(),field(key,'提链',{secret:true,configured:true})],{request:async(url,options)=>{if(url.includes('/types'))return {items:[]};bodies.push(JSON.parse(options.body||'{}'));return {remainingUses:0,totalUses:0,reservedUses:0};}});await flush();await view.actions.queryHuanguangXxsyun();view.owner.setField(key,'new-key');await view.actions.queryHuanguangXxsyun();view.owner.clearSecret(key);await view.actions.queryHuanguangXxsyun();assert.deepEqual(bodies,[{}, {api_key:'new-key'}, {api_key:''}]);assert.match(view.actions.states.huanguangXxsyun.text,/0/);assert.equal(view.saves.length,0);
});
test('XXSYUN查询失败与非法响应只显示固定中文提示，密钥改变后旧结果无效', async () => {
 const key='EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY';let resolve;const view=createConfigView([...providerFields(),field(key,'提链',{secret:true,configured:true})],{request:async url=>url.includes('/types')?{items:[]}:new Promise(done=>{resolve=done;})});await flush();const pending=view.actions.queryHuanguangXxsyun();await flush();view.owner.setField(key,'replacement');resolve({ok:true,quota:99});await pending;assert.doesNotMatch(view.actions.states.huanguangXxsyun.text,/99/);view.dependencies.request=async()=>{throw {code:'key_invalid',message:'SECRET-MESSAGE'};};await view.actions.queryHuanguangXxsyun();assert.match(view.actions.states.huanguangXxsyun.text,/无效或已失效/);assert.doesNotMatch(view.actions.states.huanguangXxsyun.text,/SECRET/);view.dependencies.request=async()=>({quota:'garbage'});await view.actions.queryHuanguangXxsyun();assert.match(view.actions.states.huanguangXxsyun.text,/响应无效/);
});
test('383字段保持旧导航目的地，七菜单字段投影唯一', () => {
 const projected=navigation.projectedFields(completeSchema);assert.equal(new Set(projected.map(f=>f.key)).size,projected.length);assert.deepEqual(navigation.orderedMenus(completeSchema),['注册与账号','代理与网络','邮箱与验证码','浏览器','服务集成','提链','系统与维护']);for(const f of completeSchema){assert.equal(navigation.fieldDomain(f),f.legacyNavigation.domain,f.key);assert.equal(navigation.menuFor(navigation.fieldDomain(f)),f.legacyNavigation.menu,f.key);}
});
test('提链独立归入资源与服务，平台页签切换真实内容', async () => {
 const view=createConfigView(providerFields());assert.match(view.wrapper.get('nav').text(),/资源与服务/);assert.ok(view.wrapper.get('[data-config-nav="提链"]').exists());await view.section('幻光');assert.ok(view.control('EXTRACT_LINK_HUANGUANG_CDK').exists());assert.equal(view.wrapper.find('[data-key="EXTRACT_LINK_CDK"]').exists(),false);await view.section('虾扯蛋链');assert.ok(view.control('EXTRACT_LINK_CDK').exists());assert.equal(view.wrapper.find('[data-key="EXTRACT_LINK_HUANGUANG_CDK"]').exists(),false);
});
test('提链平台多选仅保存原有平台启用开关', async () => {
 const view=createConfigView(providerFields());const picker=view.wrapper.findComponent({name:'ConfigChoicePicker'});picker.vm.$emit('change',['huanguang']);await harness.nextTick();assert.equal(view.owner.readField('EXTRACT_LINK_LEGACY_ENABLED'),false);assert.equal(view.owner.readField('EXTRACT_LINK_HUANGUANG_ENABLED'),true);await view.save();assert.deepEqual(view.saves[0],{EXTRACT_LINK_LEGACY_ENABLED:false,EXTRACT_LINK_HUANGUANG_ENABLED:true});
});
test('搜索平台配置准确打开平台页签与敏感多行代理池', async () => {
 const keys=['EXTRACT_LINK_HUANGUANG_ENTRY_PROXY_POOL','EXTRACT_LINK_HUANGUANG_EXIT_PROXY_POOL'];const view=createConfigView([...providerFields(),...keys.map(key=>field(key,'提链',{type:'list_str_multiline',secret:true,configured:true}))]);for(const key of keys){await view.search(key);assert.equal(activeSection(view),'幻光');assert.equal(view.control(key).element.tagName,'TEXTAREA');await view.control(key).setValue('http://user:pass@host:81\nhttp://second:82');assert.deepEqual(view.owner.readField(key),['http://user:pass@host:81','http://second:82']);await view.wrapper.get(`[aria-label="明确清除${key}"]`).trigger('click');assert.deepEqual(view.owner.readField(key),[]);}
});
test('幻光自动续查限额是可编辑数字，支付CDK清除独立于提链CDK', async () => {
 const view=createConfigView([...providerFields(),field('EXTRACT_LINK_HUANGUANG_PAYMENT_CDK','提链',{secret:true,configured:true}),field('EXTRACT_LINK_HUANGUANG_AUTO_POLL_MAX_ATTEMPTS','提链',{type:'int',value:10})]);await view.search('EXTRACT_LINK_HUANGUANG_AUTO_POLL_MAX_ATTEMPTS');await view.control('EXTRACT_LINK_HUANGUANG_AUTO_POLL_MAX_ATTEMPTS').setValue(22);assert.equal(view.owner.readField('EXTRACT_LINK_HUANGUANG_AUTO_POLL_MAX_ATTEMPTS'),22);view.owner.setField('EXTRACT_LINK_HUANGUANG_CDK','extraction-secret');await view.wrapper.get('[aria-label="明确清除EXTRACT_LINK_HUANGUANG_PAYMENT_CDK"]').trigger('click');assert.equal(view.owner.secretDraft('EXTRACT_LINK_HUANGUANG_PAYMENT_CDK').mode,'clear');assert.equal(view.owner.readField('EXTRACT_LINK_HUANGUANG_CDK'),'extraction-secret');
});
test('旧入口别名与帮助搜索定位隐藏子节，切换不丢草稿', async () => {
 const view=createConfigView([field('REGISTER_NAME','注册主链路'),field('WEBUI_PASSWORD','WebUI 授权',{help:'网站访问口令'}),field('EMAIL_BUTLER_API_BASE','邮箱 / OTP',{help:'取码固定连接'})]);await view.edit('REGISTER_NAME','draft');await view.open('网站配置');assert.equal(activeDomain(view),'WebUI 授权');await view.search('取码固定连接');assert.equal(activeSection(view),'Email Butler');await view.open('注册设置');assert.equal(view.control('REGISTER_NAME').element.value,'draft');
});
test('套餐参数进入注册与账号，代理池历史字段只读归入高级兼容', async () => {
 const view=createConfigView([field('PLAN_CHECK_TIMEOUT','代理与网络',{type:'float',value:30}),field('PROXY_1024_REGION','代理与网络'),field('ACCOUNT_PLAN_CHECK_PROXY_MODE','代理与网络')]);await view.search('PLAN_CHECK_TIMEOUT');assert.equal(activeDomain(view),'注册与账号');for(const key of ['PROXY_1024_REGION','ACCOUNT_PLAN_CHECK_PROXY_MODE']){await view.search(key);assert.equal(activeSection(view),'高级兼容');assert.equal(view.wrapper.find(`[data-key="${key}"]`).exists(),false);assert.match(view.wrapper.text(),/兼容保留/);}
});
test('统一多选保留顺序和未知值，可搜索并以键盘切换选项', async () => {
 const view=createConfigView([field('ROXY_RANDOM_OS_CHOICES','浏览器画像',{value:'Windows,custom',options:[{value:'Windows',label:'Windows'},{value:'macOS',label:'macOS'}]})]);const picker=view.wrapper.get('details');assert.match(picker.get('summary').text(),/Windows、当前值（custom）/);const options=picker.findAll('[data-choice]');options[0].element.focus();await options[0].trigger('keydown',{key:'End'});assert.equal(document.activeElement,options.at(-1).element);await picker.get('input[type=search]').setValue('mac');assert.equal(picker.findAll('[data-choice]').length,1);await picker.get('[data-choice]').trigger('click');assert.equal(view.owner.readField('ROXY_RANDOM_OS_CHOICES'),'Windows,custom,macOS');
});
test('CLI本地来源编辑器隐藏历史远端来源并保留本地顺序', () => {
 const view=createConfigView([field('EMAIL_SOURCE','邮箱 / OTP',{value:'remail,generic_api,outlook',options:[{value:'outlook',label:'Outlook'},{value:'generic_api',label:'通用 API'}]})]);const picker=view.wrapper.get('details');assert.doesNotMatch(picker.text(),/remail/);assert.equal(picker.get('summary').text(),'通用 API、Outlook');assert.equal(view.owner.dirtyCount.value,0);
});
test('敏感字段默认留空保留已有值，显式清除分别提交字符串与数组', async () => {
 const view=createConfigView([field('API_KEY','通用配置',{secret:true,configured:true,value:'must-be-redacted'}),field('PROXY_POOL','代理与网络',{type:'list_str_multiline',secret:true,configured:true})]);await view.search('API_KEY');assert.equal(view.control('API_KEY').element.value,'');await view.control('API_KEY').setValue('');assert.equal(view.owner.isDirty('API_KEY'),false);await view.wrapper.get('[aria-label="明确清除API_KEY"]').trigger('click');await view.search('PROXY_POOL');await view.wrapper.get('[aria-label="明确清除PROXY_POOL"]').trigger('click');await view.save();assert.deepEqual(view.saves[0],{API_KEY:'',PROXY_POOL:[]});assert.doesNotMatch(JSON.stringify(localStorage),/must-be-redacted/);
});
test('AT刷新国家单选支持NA、保留后端名称与策略顺序，明确留空保存跟随国家', async () => {
 const view=createConfigView([field('ACCOUNT_AT_REFRESH_DRIVER','账号补全'),field('ACCOUNT_AT_REFRESH_COUNTRY','账号补全',{value:'JP',country_codes:['JP','NA','US'],country_names:{JP:'日本',NA:'纳米比亚',US:'美国'}}),field('OPENAI_PROTOCOL_VERSION','账号补全')]);await view.search('ACCOUNT_AT_REFRESH_COUNTRY');const select=view.control('ACCOUNT_AT_REFRESH_COUNTRY');assert.equal(select.element.tagName,'SELECT');assert.match(select.text(),/跟随注册国家.*日本 · JP.*纳米比亚 · NA/s);await select.setValue('NA');assert.equal(view.owner.readField('ACCOUNT_AT_REFRESH_COUNTRY'),'NA');const html=view.wrapper.html();assert.ok(html.indexOf('data-key="ACCOUNT_AT_REFRESH_COUNTRY"')<html.indexOf('data-key="OPENAI_PROTOCOL_VERSION"'));await select.setValue('');await view.save();assert.deepEqual(view.saves[0],{ACCOUNT_AT_REFRESH_COUNTRY:''});
});
test('国家多选保持业务查询顺序与未知国家，零值不丢失', async () => {
 const view=createConfigView([field('PLAN_CHECK_COUNTRIES','注册与账号',{type:'list_str_multiline',value:['ZZ','JP'],country_codes:['JP','US']}),field('ZERO','注册与账号',{type:'int',value:0})]);const picker=view.wrapper.get('details');assert.match(picker.get('summary').text(),/当前值（ZZ）.*JP/);await picker.findAll('[data-choice]').at(-1).trigger('click');assert.deepEqual(view.owner.readField('PLAN_CHECK_COUNTRIES'),['ZZ','JP','US']);assert.equal(view.control('ZERO').element.value,'0');
});
test('任务用池说明分别显示查活和AT独立国家规则', async () => {
 const view=createConfigView([field('PROXY_POOL_SOURCE','代理与网络',{value:'manual'})]);await view.section('任务用池');assert.match(view.wrapper.text(),/查活/);assert.match(view.wrapper.text(),/优先使用独立的 AT 刷新国家；留空时跟随账号注册国家/);assert.doesNotMatch(view.wrapper.text(),/查活 \/ 刷新 AT/);
});
test('等待与价格复合模式保留原配置类型、跨菜单空草稿与保存验证', async () => {
 const view=createConfigView([field('PROXY_POOL_WAIT_TIMEOUT','代理与网络',{type:'int',value:45}),field('SMS_MAX_PRICE','接码平台',{value:'0.25'})]);await view.search('PROXY_POOL_WAIT_TIMEOUT');assert.equal(view.control('PROXY_POOL_WAIT_TIMEOUT').element.value,'timed');await view.wrapper.get('[aria-label="限时等待秒数"]').setValue('');await view.search('SMS_MAX_PRICE');await view.wrapper.get('[aria-label="短信价格上限"]').setValue('');await view.search('PROXY_POOL_WAIT_TIMEOUT');assert.equal(view.wrapper.get('[aria-label="限时等待秒数"]').element.value,'');assert.equal(view.owner.readField('PROXY_POOL_WAIT_TIMEOUT'),null);assert.equal(view.owner.readComposite('SMS_MAX_PRICE').mode,'limited');await view.save();assert.equal(view.saves.length,0);assert.match(view.owner.fieldErrors.PROXY_POOL_WAIT_TIMEOUT,/请填写限时等待秒数/);await view.control('PROXY_POOL_WAIT_TIMEOUT').setValue('continuous');await view.search('SMS_MAX_PRICE');await view.control('SMS_MAX_PRICE').setValue('unlimited');await view.save();assert.deepEqual(view.saves[0],{PROXY_POOL_WAIT_TIMEOUT:0,SMS_MAX_PRICE:''});
});
test('固定邮箱收码连接不依赖CLI来源或历史桥接开关，HME管理提示保持', async () => {
 const view=createConfigView([field('EMAIL_SOURCE','邮箱 / OTP',{value:'outlook'}),field('EMAIL_BUTLER_API_BASE','邮箱 / OTP'),field('ICLOUD_HME_BUTLER_BRIDGE_ENABLED','邮箱 / OTP',{type:'bool',value:false})]);assert.ok(view.wrapper.get('[data-config-subsection="Email Butler"]').exists());assert.ok(view.wrapper.get('[data-config-subsection="iCloud 隐藏邮箱"]').exists());await view.section('iCloud 隐藏邮箱');assert.match(view.wrapper.text(),/Email Butler/);view.owner.setField('ICLOUD_HME_BUTLER_BRIDGE_ENABLED',true);await harness.nextTick();assert.ok(view.wrapper.get('[data-config-subsection="iCloud 隐藏邮箱"]').exists());assert.doesNotMatch(view.wrapper.html(),/btnTestICloudHME|btnLoadICloudHMEAccounts/);
});
test('邮箱收码页不含远端库存、账号管理或子地址策略操作，Butler连接可搜索', async () => {
 const view=createConfigView([field('CLOUDMAIL_AUTH_TOKEN','邮箱 / OTP'),field('MAILCODE_API_KEY','邮箱 / OTP'),field('ICLOUD_HME_API_BASE','邮箱 / OTP'),field('EMAIL_BUTLER_API_BASE','邮箱 / OTP')]);for(const section of ['CloudMail','域名邮箱 MailCode','iCloud 隐藏邮箱']){await view.section(section);assert.doesNotMatch(view.wrapper.html(),/btnGenCloudMailToken|btnLoadCloudMailDomains|btnTestICloudHME|btnLoadICloudHMEAccounts|loadMailCodeCatalog|EMAIL_DERIVATION_|邮箱子地址/);}await view.search('EMAIL_BUTLER_API_BASE');assert.equal(activeSection(view),'Email Butler');
});
test('跨菜单草稿一次保存，失败保留全部草稿，成功后清空', async () => {
 const view=createConfigView([field('ROXY_API_BASE','RoxyBrowser'),field('TASK_CENTER_RETENTION_DAYS','任务中心',{type:'int',value:30})],{save:async()=>{throw new Error('network');}});await view.edit('ROXY_API_BASE','http://localhost:5888');await view.edit('TASK_CENTER_RETENTION_DAYS',60);await view.save();assert.equal(view.owner.dirtyCount.value,2);view.dependencies.save=async updates=>({updated:Object.keys(updates),reloaded:true});await view.save();assert.deepEqual(view.saves[1],{ROXY_API_BASE:'http://localhost:5888',TASK_CENTER_RETENTION_DAYS:60});assert.equal(view.owner.dirtyCount.value,0);
});
test('搜索后服务器字段错误保留唯一导航与草稿、聚焦真实输入，清空搜索恢复菜单', async () => {
 const key='TASK_CENTER_RETENTION_DAYS';const view=createConfigView([field(key,'任务中心',{type:'int',value:30}),field('ROXY_API_BASE','RoxyBrowser')],{save:async()=>{throw new ConfigApiError('校验失败',400,'validation',{[key]:'保留天数必须大于零'});}});await view.edit(key,0);await view.save();assert.equal(view.wrapper.findAll('[data-config-nav]').length,1);assert.equal(view.wrapper.get('#config-vue-search').element.value,key);assert.equal(view.owner.readField(key),0);assert.equal(document.activeElement,view.control(key).element);assert.match(view.wrapper.get('.config-vue-savebar').text(),/请检查标记的配置项/);await view.search('');assert.equal(view.wrapper.findAll('[data-config-nav]').length,2);view.dependencies.save=async updates=>({updated:Object.keys(updates)});await view.save();assert.deepEqual({...view.owner.fieldErrors},{});assert.equal(view.owner.dirtyCount.value,0);
});
test('普通编辑清除本轮字段错误且保留输入DOM及焦点，普通失败提示服务状态', async () => {
 const view=createConfigView([field('REGISTER_NAME','注册主链路',{value:'old'}),field('OTHER_FIELD','注册主链路')],{save:async()=>{throw new ConfigApiError('invalid',400,'',{REGISTER_NAME:'旧错误',OTHER_FIELD:'另一错误'});}});await view.edit('REGISTER_NAME','draft');await view.save();const input=view.control('REGISTER_NAME');input.element.focus();await input.setValue('new');assert.equal(view.control('REGISTER_NAME').element,input.element);assert.equal(document.activeElement,input.element);assert.deepEqual({...view.owner.fieldErrors},{});view.dependencies.save=async()=>{throw new Error('unavailable');};await view.save();assert.match(view.wrapper.get('.config-vue-savebar').text(),/保存失败，请重试.*网络或服务状态/s);
});
test('Codex执行方式在注册主链路编辑并同步账号补全只读投影', async () => {
 const choices=[{value:'protocol',label:'协议'},{value:'roxy',label:'Roxy'}];const view=createConfigView([field('CODEX_OAUTH_DRIVER','注册主链路',{value:'protocol',options:choices}),field('ACCOUNT_CODEX_DRIVER','账号补全',{value:'protocol',options:choices})]);await view.edit('CODEX_OAUTH_DRIVER','roxy');assert.equal(view.owner.readField('ACCOUNT_CODEX_DRIVER'),'roxy');await view.open('账号补全');assert.equal(view.wrapper.find('[data-key="ACCOUNT_CODEX_DRIVER"]').exists(),false);assert.match(view.wrapper.text(),/Roxy · 由注册主链路统一维护/);
});
test('代理高级参数折叠展示，搜索及错误定位可展开并聚焦', async () => {
 const view=createConfigView([field('PROXY_POOL_SOURCE','代理与网络',{value:'711proxy'}),field('PROXY_711_API_URL','代理与网络'),field('PROXY_711_REQUEST_TIMEOUT','代理与网络',{type:'float',value:10})]);await view.section('代理来源');assert.equal(view.wrapper.get('.config-vue-source-advanced').element.open,false);await view.search('PROXY_711_REQUEST_TIMEOUT');assert.equal(view.wrapper.get('.config-vue-source-advanced').element.open,true);await view.search('');view.owner.navigateField('PROXY_711_REQUEST_TIMEOUT');await flush();assert.equal(view.wrapper.get('.config-vue-source-advanced').element.open,true);assert.equal(document.activeElement,view.control('PROXY_711_REQUEST_TIMEOUT').element);
});
