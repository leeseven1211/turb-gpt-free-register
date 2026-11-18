const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {installAccountActionHelpers} = require('../frontend_script_sources.cjs');
const {installLegacyActionsFixture} = require('../accounts/actions_fixture.cjs');

const root = path.join(__dirname, '../..');
const accounts = fs.readFileSync(path.join(root, 'webui/static/js/pages/accounts/page.js'), 'utf8');
function extract(source, name) {
  const index = source.indexOf(`function ${name}(`);
  const start = source.slice(Math.max(0, index - 6), index) === 'async ' ? index - 6 : index;
  const end = source.indexOf('\n}', index);
  return source.slice(start, end + 2);
}
// 回执组件由 tasks Vitest 验证；Codex 的同一 202 业务断言已迁至 features/codex/actions.test.ts。

test('账号上传提交202后不会显示上传成功或把未完成凭证记为已上传', async () => {
  for (const [source,name] of [[accounts,'uploadSelectedCodexSub2']]) {
    const toasts=[],tracked=[],calls=[],button={disabled:false,textContent:'上传',classList:{remove() {}}};
    const context={
      ACCOUNT_SELECTED:new Set([23]),ACCOUNTS:[{id:23,codex_status:'success'}],
      confirm:()=>true,$:()=>button,document:{getElementById:()=>button},
      api:async(url,options)=>{calls.push({url,options});return {accepted:true,queued_count:1,uploaded_count:0,queued:[{accepted:true,task_id:17,run_id:29,filename:'fixture.json'}]};},
      showToast:text=>toasts.push(text),trackAcceptedOperationsV2:(items,label,options)=>tracked.push({items,label,options}),
      pollAccountPlanStatuses:async()=>{throw new Error('202不应读上传成功状态');},loadCodex:async()=>{throw new Error('202不应读上传成功状态');},
      updateAccountSelectionUi(){},
    };
    vm.createContext(context);installAccountActionHelpers(context);installLegacyActionsFixture(context);vm.runInContext(extract(source,name),context);
    await context[name]();
    assert.equal(calls.length,1);
    assert.equal(calls[0].url,'/api/accounts/codex/upload-sub2-bulk');
    assert.equal(calls[0].options.method,'POST');
    assert.deepEqual(JSON.parse(calls[0].options.body),{account_ids:[23]});
    assert.match(toasts[0],/已入队 1/);
    assert.doesNotMatch(toasts[0],/已上传/);
    assert.equal(tracked.length,1);
    assert.equal(tracked[0].items[0].task_id,17);
    assert.equal(tracked[0].items[0].run_id,29);
    assert.equal(tracked[0].label,'手动上传');
    assert.equal(tracked[0].options,undefined);
  }
});
