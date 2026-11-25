const assert = require('node:assert/strict');
const test = require('node:test');
const {vueHarness} = require('../accounts/actions_fixture.cjs');
const {createAccountActions} = vueHarness.load('src/features/accounts/actions.ts');
const {createCodexActions} = vueHarness.load('src/features/codex/actions.ts');

// 执行迁移后的动作 owner；只有 HTTP、通知和页面回调为测试替身。
test('账号上传提交202只显示入队和任务中心反馈，不展示未经确认的上传成功', async () => {
  const calls=[],notices=[];
  const actions=createAccountActions({
    request:async(url,options)=>{calls.push({url,options});return {accepted:true,queued_count:1,uploaded_count:0,
      queued:[{accepted:true,task_id:17,run_id:29,filename:'fixture.json'}]};},
    notify:value=>notices.push(value),confirm:()=>true,clipboard:async()=>true,
    downloadBlob:()=>assert.fail('上传不能下载文件'),downloadUrl:()=>assert.fail('上传不能下载文件'),
    now:()=>new Date(),schedule:()=>assert.fail('202不能假定上传完成后刷新'),
    setup:{operationWorkers:()=>3,
      pollStatuses:()=>assert.fail('202不能读上传成功状态'),refresh:()=>assert.fail('202不能读上传成功状态')},
  });
  await actions.invoke('uploadSelectedCodexSub2',{accountIds:['23'],expectedEmails:{},querySnapshot:{},archived:'0',rowHints:[]});
  assert.equal(calls.length,1);
  assert.equal(calls[0].url,'/api/accounts/codex/upload-sub2-bulk');
  assert.deepEqual(JSON.parse(calls[0].options.body),{account_ids:[23]});
  assert.match(notices[0],/已入队 1/);
  assert.match(notices[0],/任务中心/);
  assert.doesNotMatch(notices[0],/已上传/);
});

test('Codex上传提交202保留入队反馈并留在当前页，用户主动查看才导航', async () => {
  const originalFetch=globalThis.fetch;
  const notices=[],opened=[],selected={value:new Set(['fixture.json','other-page.json'])};
  globalThis.fetch=async(url,options)=>{
    assert.equal(url,'/api/codex/upload-sub2-bulk');
    assert.deepEqual(JSON.parse(options.body),{filenames:['fixture.json','other-page.json']});
    return new Response(JSON.stringify({ok:true,accepted:true,queued_count:1,uploaded_count:0,
      queued:[{accepted:true,task_id:17,run_id:29,filename:'fixture.json'}]}),{status:202,headers:{'Content-Type':'application/json'}});
  };
  try{
    const actions=createCodexActions({selected,items:{value:[]},archived:{value:false},
      refresh:()=>assert.fail('202不能读上传成功状态'),
      callbacks:{notify:value=>notices.push(value),confirm:()=>true,openTasks:(...values)=>opened.push(values),
        operationWorkers:()=>3}});
    await actions.run('uploadSub2');
    assert.match(notices[0],/已入队 1/);
    assert.doesNotMatch(notices[0],/已上传/);
    assert.deepEqual([...selected.value],['other-page.json']);
    assert.deepEqual(opened,[]);
    assert.equal(actions.uploadProgress.value,true);
    actions.showProgress();
    assert.deepEqual(opened,[[]]);
  }finally{globalThis.fetch=originalFetch;}
});
