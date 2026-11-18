const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {createVueHarness} = require('../frontend_vue_loader.cjs');

const harness = createVueHarness();
const stats = harness.load('src/features/extractStats/statistics.ts');
const Page = harness.load('src/features/extractStats/ExtractStatsPage.vue').default;
const root = path.join(__dirname, '../..');
test.after(() => harness.close());

test('统计的零值、空分母和缺失耗时分别显示', () => {
  for (const value of [null, undefined, '', -1, 2, '无结果']) assert.equal(stats.rate(value), '—');
  assert.equal(stats.rate(0), '0.0%');
  assert.equal(stats.rate(1 / 3), '33.3%');
  assert.equal(stats.duration(null), '—');
  assert.equal(stats.duration(0), '0 秒');
  assert.equal(stats.duration(125), '2 分 5 秒');
  assert.equal(stats.duration(3720), '1 小时 2 分');
  assert.equal(stats.updatedAt('无时间'), '统计已更新');
});

test('筛选失败后切回上一次成功范围可恢复快照，平台和模式名称始终为纯文本', async t => {
  const snapshot = {ok:true, totals:{total:3}, daily:[], date_from:'<img src=x>',
    providers:[{provider_id:'<svg onload=x>', total:3},{provider_id:'lumen'}], modes:[{mode:'<script>x</script>', total:3}]};
  const reads = [];
  t.mock.method(globalThis, 'fetch', async url => {
    reads.push(url);
    return reads.length === 1 ? Response.json(snapshot) : Response.json({ok:false, error:'<合成错误>'}, {status:503});
  });
  Object.defineProperty(harness.document,'hidden',{configurable:true,value:false});
  const wrapper = harness.mount(Page, {props:{deps:{visible:false}}});
  t.after(() => harness.cleanup());
  wrapper.vm.setVisible(true);
  await wrapper.vm.load();
  assert.equal(wrapper.get('.es-provider-table tbody th').text(), '<svg onload=x>');
  assert.equal(wrapper.get('.es-modes h3').text(), '<script>x</script>');
  assert.equal(wrapper.get('.es-scope span').text(), '<img src=x> — —');
  assert.equal(wrapper.find('script,img,svg[onload]').exists(), false);
  assert.equal(wrapper.findAll('[data-extract-stats-provider] option').filter(n=>n.text()==='Lumen Flow').length, 1);
  await wrapper.get('[data-extract-stats-days="7"]').trigger('click');
  await wrapper.vm.load();
  assert.equal(wrapper.find('.es-scope').exists(), false);
  await wrapper.get('[data-extract-stats-days="30"]').trigger('click');
  await wrapper.vm.load();
  assert.match(wrapper.get('[role=alert]').text(), /保留上次统计。<合成错误>/);
  assert.match(wrapper.get('.es-scope').text(), /<img src=x>/);
  assert.deepEqual(reads, [30,7,30].map(days => `/api/extract-workbench/analytics?days=${days}`));
});

test('侧栏桥接仅在统计页可见时挂载新版资源，并按需加载更新', async () => {
  const template = fs.readFileSync(path.join(root, 'webui/templates/partials/extract_stats.html'), 'utf8');
  assert.match(template, /filename='extractStats\/extractStats.js', v=asset_version/);
  assert.match(template, /filename='extractStats\/extractStats.css', v=asset_version/);
  const urls = {moduleUrl:'/static/extractStats/extractStats.js?v=fixture',styleUrl:'/static/extractStats/extractStats.css?v=fixture'};
  let hidden = true;
  const node = {dataset:urls}, styles = [], calls = [], imports = [];
  const context = {document:{getElementById: id => id === 'extractStatsRoot' ? node : id === 'tab-extract-stats' ? {classList:{contains:()=>hidden}} : null,
    head:{append:el=>styles.push(el.href)}, createElement:()=>({})}, markViewReady: tab=>calls.push(tab), showToast: msg=>assert.fail(msg),
    loadModule:async url => {imports.push(url); return {mountExtractStats(el, deps){
      assert.equal(el, node); assert.equal(deps.visible, false);
      deps.onReady(); return {setVisible:v=>calls.push(v),load:()=>calls.push('load')};
    }};}};
  context.window = context;
  const js = path.join(root,'webui/static/js');
  vm.runInNewContext(fs.readFileSync(path.join(js,'shared/page-bridge.js'),'utf8').replace('import(node.dataset.moduleUrl)','loadModule(node.dataset.moduleUrl)'),context);
  vm.runInNewContext(fs.readFileSync(path.join(js,'pages/extract_link/stats.js'),'utf8'),context);
  const bridge = context.ExtractStats;
  await bridge.setVisible(false);
  await context.loadExtractStats();
  assert.deepEqual(imports, []);
  hidden=false; await bridge.setVisible(true); await context.loadExtractStats();
  hidden=true; await bridge.setVisible(false); await context.loadExtractStats();
  assert.deepEqual(imports,[urls.moduleUrl]); assert.deepEqual(styles,[urls.styleUrl]);
  assert.deepEqual(calls,['extract-stats',true,'load',false]);
});
