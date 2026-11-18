const assert = require('node:assert/strict');
const test = require('node:test');

const {createConfigView, cleanup, harness} = require('../config/vue_fixture.cjs');
test.afterEach(cleanup);
const prefix = 'EXTRACT_LINK_ANGUANG_';
const field = (key, extra = {}) => ({key, group: '提链', label: key, type: 'str', value: '', ...extra});

function configView() {
  const fields = [
    field('EXTRACT_LINK_DEFAULT_PROVIDER', {value: 'legacy', options: [{value: 'legacy', label: '虾扯蛋链'}, {value: 'anguang', label: 'anguang'}]}),
    field('EXTRACT_LINK_LEGACY_ENABLED', {type: 'bool', value: true}),
    field(prefix + 'ENABLED', {type: 'bool', value: false}),
    field(prefix + 'AUTO_PAYMENT_ENABLED', {type: 'bool', value: false}),
    field(prefix + 'AUTO_RETRY', {type: 'bool', value: false}),
    field(prefix + 'API_BASE', {value: 'https://ytc.xxsyun.xyz/openapi/v1'}),
    field(prefix + 'API_KEY', {secret: true, configured: true}),
    field(prefix + 'PROCESSING_MODE', {value: 'STANDARD', options: [{value: 'STANDARD', label: '流光'}, {value: 'STRICT', label: 'sea'}]}),
    field(prefix + 'PLAN_NAME', {value: 'chatgptplusplan'}),
    field('EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY', {secret: true, configured: true}),
  ];
  return createConfigView(fields);
}

test('暗光配置分类能通过Key搜索定位，显示独立密钥且不修改任何开关', async () => {
  const view = configView();
  assert.equal(view.wrapper.find('[data-config-subsection="暗光（XXSYUN 一条龙）"]').exists(), true);
  assert.equal(view.control('EXTRACT_LINK_DEFAULT_PROVIDER').element.value, 'legacy');
  assert.ok(view.control('EXTRACT_LINK_DEFAULT_PROVIDER').find('option[value="anguang"]').exists());
  await view.search(prefix + 'API_KEY');
  assert.equal(view.wrapper.get('[data-config-subsection][aria-pressed="true"]').text(), '暗光（XXSYUN 一条龙）');
  const input = view.control(prefix + 'API_KEY');
  assert.equal(input.attributes('type'), 'password');
  assert.equal(input.element.value, '');
  assert.ok(view.wrapper.find(`[aria-label="明确清除${prefix}API_KEY"]`).exists());
  assert.equal(view.wrapper.find('[data-key="EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"]').exists(), false);
  assert.equal(view.wrapper.find('[data-config-field-action="EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY"]').exists(), false);
  assert.equal(view.control(prefix + 'AUTO_PAYMENT_ENABLED').element.checked, false);
  assert.equal(view.owner.readField(prefix + 'ENABLED'), false);
  assert.equal(view.owner.dirtyCount.value, 0);
  assert.equal(view.saves.length, 0);
});

test('暗光分类直接显示配置项，不附加菜单说明', async () => {
  const view = configView();
  await view.section('暗光（XXSYUN 一条龙）');
  const section = view.wrapper.get('[data-config-section="提链"]');
  assert.equal(section.find('.config-section-v2-subhelp').exists(), false);
  assert.equal(section.element.querySelector(':scope > p'), null);
  assert.ok(view.control(prefix + 'API_KEY').exists());
});

const {createExtractBatch}=harness.load('src/features/extract/useExtractBatch.ts');
const {providerLabel}=harness.load('src/features/extract/presentation.ts');
test('暗光任务只接受服务端公布的自动支付与UPI，未明确模式时不默认付款',async()=>{
  const calls=[];const b=createExtractBatch({api:{candidates:async()=>({total:1,selected_count:1}),create:async payload=>(calls.push(payload),{batch_id:1})},confirm:()=>true});
  await b.open({providers:[{id:'anguang',modes:['auto_payment'],link_types:['upi'],default_type:'upi',payment_source:'native'}]});
  assert.equal(b.state.mode,'');assert.equal(b.state.type,'upi');await b.preview();await b.submit();assert.equal(calls.length,0);
  b.state.mode='auto_payment';b.state.type='pix';await b.submit();assert.equal(calls.length,0);
  b.state.type='upi';await b.submit();assert.equal(calls.length,1);assert.equal(calls[0].provider_id,'anguang');assert.equal(calls[0].mode,'auto_payment');assert.equal(calls[0].type,'upi');b.destroy();
});
test('历史暗光任务仍用暗光名称展示，不依赖当前平台是否启用',()=>{assert.equal(providerLabel('anguang'),'暗光（XXSYUN 一条龙）');});
