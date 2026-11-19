const assert=require('node:assert/strict');
const test=require('node:test');
const {ownerFixture,deferred,flush}=require('./registration_vue_owner_fixture.cjs');

for(const kind of ['retryBatch','retryBulk','retry']){
  for(const enabled of [true,false]){
    test(`${kind} 按当前勾选发送调试设置 ${enabled}，只重跑实际可重试项`,async t=>{
      const h=ownerFixture(t,{deps:{confirm:()=>true}});
      const job={id:'9007199254740993',status:'failed',retryable:true,retry_action:'registration_resume'};
      h.owner.state.batchId='uuid-registration-batch';
      h.owner.state.batch={batch_id:'uuid-registration-batch',items:[job,{id:22,status:'running',retryable:false},{id:23,status:'failed',retryable:false}]};
      const pending=h.owner.executeAction(kind,kind==='retry'?job:undefined,[job.id],enabled);
      await flush();
      assert.equal(h.writes.length,1);
      assert.equal(h.writes[0].payload.debug_enabled,enabled);
      if(kind!=='retry')assert.deepEqual(h.writes[0].payload.job_ids,[job.id]);
      else assert.equal(h.writes[0].url,`/api/jobs/${job.id}/retry`);
      h.writes[0].resolve({started_count:1});
      await pending;
    });
  }
}

test('取消批次与停止批次使用原UUID和独立范围，重跑不包含运行任务',async t=>{
  const h=ownerFixture(t,{deps:{confirm:()=>true}});
  h.owner.state.batchId='550e8400-e29b-41d4-a716-446655440000';
  h.owner.state.batch={batch_id:h.owner.state.batchId,items:[{id:1,status:'pending'},{id:2,status:'running'}]};
  const cancel=h.owner.executeAction('cancelBatch');
  await flush();
  assert.equal(h.writes[0].url,'/api/jobs/batches/550e8400-e29b-41d4-a716-446655440000/cancel');
  h.writes[0].resolve({cancelled:1,batch_id:h.owner.state.batchId});
  await cancel;
  h.owner.state.batch={batch_id:h.owner.state.batchId,items:[{id:1,status:'pending'},{id:2,status:'running'}]};
  const stop=h.owner.executeAction('stopBatch');await flush();
  assert.equal(h.writes[1].url,'/api/jobs/batches/550e8400-e29b-41d4-a716-446655440000/stop');
  assert.deepEqual(h.writes[1].payload,{});
  h.writes[1].resolve({ok:true});await stop;
});

test('日志轮询更新同一任务时，对比仍可完成并解除按钮等待状态',async t=>{
  const pending=deferred();
  const h=ownerFixture(t,{api:{log:async()=>({job:{status:'running'},log:'synthetic running log'}),compare:()=>pending.promise}});
  h.owner.openLog('9007199254740993');
  await flush();
  const comparing=h.owner.compare('9007199254740993');
  assert.equal(h.owner.state.detail.comparing,true);
  const poll=[...h.timeouts.values()].find(timer=>timer.milliseconds===2000);
  assert.ok(poll,'running details retain their existing refresh timer');
  poll.callback();
  await flush();
  const result={differences:[{step:'email_otp',changed:true}]};
  pending.resolve(result);
  assert.deepEqual(await comparing,result);
  assert.deepEqual(h.owner.state.detail.comparison,result);
  assert.equal(h.owner.state.detail.comparing,false);
});

test('同一任务发起新对比时，旧对比不能提前解除新按钮等待状态',async t=>{
  const first=deferred(),second=deferred();
  let count=0;
  const h=ownerFixture(t,{api:{compare:()=>++count===1?first.promise:second.promise}});
  h.owner.openLog('9007199254740993');
  await flush();
  const older=h.owner.compare('9007199254740993');
  const latest=h.owner.compare('9007199254740993');
  first.resolve({differences:['old']});
  assert.equal(await older,null);
  assert.equal(h.owner.state.detail.comparing,true);
  assert.equal(h.owner.state.detail.comparison,null);
  second.resolve({differences:['latest']});
  assert.deepEqual(await latest,{differences:['latest']});
  assert.equal(h.owner.state.detail.comparing,false);
});

for(const kind of ['stopBatch','cancelBatch']){
  test(`${kind}确认期间切换批次仍仅提交已确认的原批次`,async t=>{
    const confirmed=deferred();
    const h=ownerFixture(t,{deps:{confirm:()=>confirmed.promise}});
    h.owner.state.batchId='batch-original';
    h.owner.state.batch={batch_id:'batch-original',items:[{id:1,status:'running'},{id:2,status:'pending'}]};
    const action=h.owner.executeAction(kind);
    assert.equal(h.writes.length,0);
    await h.owner.setBatch('batch-new');
    confirmed.resolve(true);
    await flush();
    assert.equal(h.writes.length,1);
    assert.equal(h.writes[0].url,`/api/jobs/batches/batch-original/${kind==='stopBatch'?'stop':'cancel'}`);
    h.writes[0].resolve({ok:true});
    await action;
  });
}
