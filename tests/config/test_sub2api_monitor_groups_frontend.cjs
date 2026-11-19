const assert = require('node:assert/strict');
const test = require('node:test');
const {field, createConfigView, cleanup, flush} = require('./vue_fixture.cjs');
const key = 'SUB2API_MONITOR_GROUP_IDS';
test.afterEach(cleanup);

async function createView(value = '', request = async () => ({ok:true,groups:[]})) {
  const behavior = {request};
  const ui = createConfigView([
    field(key,'定时任务',{label:'异常巡检分组 ID',value}),
    field('SUB2API_API_BASE','Codex',{value:'https://saved.example.test'}),
    field('SUB2API_API_KEY','Codex',{secret:true,configured:true}),
  ],{request:(url,options)=>url==='/api/extract-link/types'?{items:[{type:'plus',label:'Plus'}]}:behavior.request(url,options)});
  await ui.search(key); await flush();
  return {...ui,behavior,
    input:()=>ui.control(key),
    button:()=>ui.wrapper.get('[data-query-sub2api-groups]'),
    options:()=>ui.wrapper.get('[data-sub2api-monitor-group-options]'),
    status:()=>ui.wrapper.get('[data-sub2api-monitor-groups-status]'),
    async query(){await this.button().trigger('click');await flush();},
    async changeGroup(id,checked){await this.options().get(`[data-sub2api-monitor-group-id="${id}"]`).setValue(checked);await flush();},
  };
}

test('定时任务仅有一个分组配置入口并提供查询及空选全部说明',async()=>{
  const ui=await createView('17');
  assert.equal(ui.wrapper.findAll(`[data-key="${key}"]`).length,1);
  assert.equal(ui.input().attributes('id'),`config-field-${key}`);
  assert.equal(ui.button().text(),'查询分组');
  assert.match(ui.wrapper.text(),/使用已保存/);assert.match(ui.wrapper.text(),/不选.*全部/);
  assert.equal(ui.status().attributes('role'),'status');assert.equal(ui.status().attributes('aria-live'),'polite');
});

test('查询只用已保存连接，显示名称和ID并保留未保存分组及旧ID',async()=>{
  const ui=await createView('17,99');
  ui.owner.setField('SUB2API_API_BASE','https://draft.example.test');
  ui.owner.setSecret('SUB2API_API_KEY',{mode:'set',value:'draft-private'});
  ui.behavior.request=async(url,options)=>{
    assert.equal(url,'/api/sub2api/groups');assert.equal(options.method,'GET');assert.equal(Object.hasOwn(options,'body'),false);
    await flush();assert.equal(ui.button().element.disabled,true);assert.equal(ui.wrapper.get('[data-sub2api-monitor-groups]').attributes('aria-busy'),'true');
    return {ok:true,groups:[{id:17,name:'Plus'},{id:18,name:'<Free>'}]};
  };
  await ui.query();
  assert.match(ui.options().text(),/Plus（ID 17）/);assert.match(ui.options().text(),/<Free>（ID 18）/);assert.equal(ui.options().find('free').exists(),false);
  for(const id of ['17','99'])assert.equal(ui.options().get(`[data-sub2api-monitor-group-id="${id}"]`).element.checked,true);
  assert.equal(ui.input().element.value,'17,99');assert.equal(ui.button().element.disabled,false);
  assert.equal(ui.wrapper.get('[data-sub2api-monitor-groups]').attributes('aria-busy'),'false');
  assert.equal(ui.owner.readField('SUB2API_API_BASE'),'https://draft.example.test');assert.equal(ui.owner.isDirty(key),false);
  assert.equal(ui.saves.length,0);assert.equal(JSON.stringify(ui.actions.states).includes('draft-private'),false);
});

test('多选与手填共享唯一配置值并沿现有草稿保存，清空表示全部',async()=>{
  const ui=await createView('17',async()=>({ok:true,groups:[{id:17,name:'Plus'},{id:18,name:'Free'}]}));await ui.query();
  const checkbox=ui.options().get('[data-sub2api-monitor-group-id="18"]').element;checkbox.focus();
  await ui.changeGroup(18,true);assert.equal(ui.input().element.value,'17,18');assert.equal(ui.owner.readField(key),'17,18');
  assert.equal(ui.options().get('[data-sub2api-monitor-group-id="18"]').element,checkbox,'勾选已知分组时保留原复选框节点');
  assert.equal(document.activeElement,checkbox,'保留复选框焦点');
  await ui.input().setValue('18,99');assert.equal(ui.owner.readField(key),'18,99');
  assert.equal(ui.options().get('[data-sub2api-monitor-group-id="99"]').element.checked,true);
  await ui.changeGroup(18,false);await ui.changeGroup(99,false);
  assert.equal(ui.input().element.value,'');assert.equal(ui.owner.readField(key),'');assert.match(ui.status().text(),/全部/);
  assert.equal(ui.saves.length,0);await ui.owner.saveAll();assert.deepEqual(ui.saves[0],{[key]:''});
});

test('查询失败保留已查询选项及分组草稿，恢复查询按钮',async()=>{
  const ui=await createView('17',async()=>({ok:true,groups:[{id:17,name:'Plus'}]}));await ui.query();
  await ui.input().setValue('17,99');ui.behavior.request=async()=>{throw new Error('Sub2API 连接超时');};await ui.query();
  assert.equal(ui.input().element.value,'17,99');assert.equal(ui.owner.readField(key),'17,99');
  assert.match(ui.options().text(),/Plus（ID 17）/);assert.equal(ui.options().get('[data-sub2api-monitor-group-id="99"]').element.checked,true);
  assert.match(ui.status().text(),/查询分组失败.*Sub2API 连接超时/);assert.equal(ui.button().element.disabled,false);
});

test('中文逗号或空白分隔草稿可查询勾选并彻底取消指定分组',async()=>{
  for(const value of ['17，18','17 18','17\n18',' 17 ， 18\t17 ']){
    const ui=await createView(value,async()=>({ok:true,groups:[{id:17,name:'Plus'},{id:18,name:'Free'}]}));await ui.query();
    assert.deepEqual(ui.options().findAll('input:checked').map(input=>input.attributes('data-sub2api-monitor-group-id')),['17','18'],value);
    assert.equal(ui.options().findAll('input').length,2,'不生成整串未知分组 ID');
    await ui.changeGroup(17,false);assert.equal(ui.input().element.value,'18');assert.equal(ui.owner.readField(key),'18');
    await ui.changeGroup(17,true);await ui.changeGroup(17,false);assert.equal(ui.owner.readField(key),'18');
    cleanup();
  }
});

test('服务集成查看状态展示已保存巡检分组或全部范围',async()=>{
  const ui=await createView('',async()=>({ok:true,monitor:{enabled:true,group_ids:[17,18]}}));
  await ui.search('SUB2API_API_BASE');await flush();
  const panel=ui.wrapper.get('[data-config-tool="sub2api"]');
  await panel.findAll('button').find(button=>button.text()==='查看状态').trigger('click');await flush();
  assert.match(panel.get('.config-action-status').text(),/巡检范围.*17.*18/);
  ui.behavior.request=async()=>({ok:true,monitor:{enabled:true,group_ids:[]}});
  await panel.findAll('button').find(button=>button.text()==='查看状态').trigger('click');await flush();
  assert.match(panel.get('.config-action-status').text(),/巡检范围.*全部分组/);
});
