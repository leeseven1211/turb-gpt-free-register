const assert=require('node:assert/strict');
const test=require('node:test');
const {ownerFixture,flush}=require('./registration_vue_owner_fixture.cjs');

test('注册请求不指定driver，保留后端driver/source/并发受理结果',async t=>{
  const h=ownerFixture(t);
  const submission=h.owner.create({count:50,workers:3,email_source:'outlook',debug_enabled:false});
  assert.equal(Object.hasOwn(h.writes[0].payload,'registration_driver'),false);
  h.writes[0].resolve({submitted:50,email_source:'outlook',registration_driver:'protocol_oss_2',workers:3,jobs:[{id:'9007199254740993',batch_id:'batch-fixture'}]});
  const receipt=await submission;
  assert.equal(receipt.registration_driver,'protocol_oss_2');
  assert.equal(h.owner.state.lastCreate.registration_driver,'protocol_oss_2');
  assert.equal(h.owner.state.batchId,'batch-fixture');
  assert.equal(h.owner.state.receipt.tone,'success');
});

for(const workers of [30,50,100]){
  test(`并发 ${workers} 按原值提交，服务端回显独立保留`,async t=>{
    const h=ownerFixture(t);
    const pending=h.owner.create({count:50,workers,email_source:'outlook',debug_enabled:false});
    assert.equal(h.writes[0].payload.workers,workers);
    h.writes[0].resolve({submitted:50,workers:50,jobs:[{batch_id:'batch'}]});
    await pending;
    assert.equal(h.owner.state.lastCreate.workers,50);
    assert.equal(h.owner.state.creating,false);
  });
}

test('无效并发/数量不发POST，也不把失败当成已受理',async t=>{
  const h=ownerFixture(t);
  for(const workers of [0,-1,1.5,Number.NaN,Number.MAX_SAFE_INTEGER+1,Infinity]){
    await assert.rejects(h.owner.create({count:1,workers,email_source:'outlook',debug_enabled:false}),/正整数/);
  }
  for(const count of [0,-1,1.5,Number.NaN,Infinity]){
    await assert.rejects(h.owner.create({count,workers:3,email_source:'outlook',debug_enabled:false}),/正整数/);
  }
  assert.equal(h.writes.length,0);
  assert.equal(h.owner.state.receipt,null);
});

test('metadata合并来源capability并保留手动模式，隐藏时不读取metadata',async t=>{
  let reads=0;
  const h=ownerFixture(t,{api:{metadata:async()=>{
    reads++;
    return {manual_mode:true,sources:[{value:'outlook',label:'Outlook',enabled:true}],registration_drivers:[{value:'roxy',label:'本地 Roxy'}],capabilities:{email_sources:{outlook:{enabled:false}}}};
  }}});
  await h.owner.ensureMeta();
  assert.equal(reads,0);
  h.owner.setVisible(true);
  await flush();
  assert.equal(reads,1);
  assert.equal(h.owner.state.meta.manual_mode,true);
  assert.equal(h.owner.state.meta.sources[0].enabled,false);
  assert.equal(h.owner.state.meta.registration_drivers[0].label,'本地 Roxy');
});

test('注册能力明确停用时，外部create也不提交并提供原因；刷新为可用后可再次发起',async t=>{
  let enabled=false;
  const h=ownerFixture(t,{api:{metadata:async()=>({
    sources:[{value:'outlook',enabled:true}],registration_drivers:[],
    capabilities:{features:{register:{enabled,reason:enabled?'':'synthetic browser unavailable'}}},
  })}});
  h.owner.setVisible(true);
  await flush();
  const blocked=h.owner.create({count:1,workers:3,email_source:'outlook',debug_enabled:false});
  blocked.catch(()=>{});
  assert.equal(h.writes.length,0,'disabled metadata must fence the external owner entry before POST');
  await assert.rejects(blocked,/synthetic browser unavailable/);
  assert.equal(h.owner.state.receipt.tone,'warning');
  assert.equal(h.owner.state.creating,false);
  assert.equal(h.owner.registrationUnavailable.value,'synthetic browser unavailable');
  enabled=true;
  await h.owner.ensureMeta(true);
  assert.equal(h.owner.registrationUnavailable.value,'');
  const allowed=h.owner.create({count:1,workers:3,email_source:'outlook',debug_enabled:false});
  assert.equal(h.writes.length,1);
  h.writes[0].resolve({submitted:1});
  await allowed;
  assert.equal(h.owner.state.receipt.tone,'success');
});
