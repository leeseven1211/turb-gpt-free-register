const assert=require('node:assert/strict');
const {createVueHarness}=require('../frontend_vue_loader.cjs');
const {installNetworkFence}=require('../config/vue_migration_contracts.cjs');
async function run(name){
 const fence=installNetworkFence(),h=createVueHarness();
 const settle=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));await h.nextTick();};
 try{
  Object.defineProperty(document,'hidden',{configurable:true,value:false});
  HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
  HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
  window.scrollTo=()=>{};
  const Page=h.load('src/features/registration/RegistrationPage.vue').default;
  const calls=[];
  const snapshot={source:'native',main_steps:[
   {id:'network',label:'分配网络',state:'success',started_at:'2026-11-17T00:00:00Z',completed_at:'2026-11-17T00:00:01Z'},
   {id:'email_otp',label:'邮箱验证',state:'running',started_at:'2026-11-17T00:00:01Z',depends_on:['network']},
  ]};
  const job={id:'9007199254740993',email:'synthetic@example.invalid',email_source:'outlook',status:'partial_success',display_status:'password_confirmation_pending',retryable:true,error_message:'remote response was not recorded',progress:snapshot,
   operation_task_id:'9007199254740995',operation_run_id:'9007199254740997'};
  const batch={batch_id:'synthetic-batch-uuid',items:[job],total:1,status_counts:{running:2,pending:10}};
  const api={
   metadata:async()=>({sources:[{value:'outlook',label:'Outlook',enabled:true}],registration_drivers:[{value:'roxy',label:'本地 Roxy'}]}),
   summary:async()=>({accounts:0,email_supply:{status:'known',total:0,available:0,used:0,failed:0}}),
   jobs:async params=>{calls.push(params);return params.view==='table'?{items:[job],total:1,facets:{}}:{progress_batch:batch,progress_batches:[batch],status_counts:{active:12}};},
   create:async()=>{throw Error('contract must not submit registration');},
   action:async()=>{throw Error('contract must not execute a business action');},
   log:async()=>({job:{id:job.id,status:'success'},log:'saved synthetic log'}),
   debug:async()=>({enabled:false}),diagnostics:async()=>({enabled:false}),compare:async()=>({differences:[]}),
  };
  const openTask=[];
  const wrapper=h.mount(Page,{props:{deps:{api,visible:false,view:name==='list_controls'?'tasks':'launch',openTask:(...args)=>openTask.push(args)}}});
  wrapper.vm.setVisible(true);await settle();
  if(name==='password_result'){
   const card=wrapper.get('.registration-batch-card');
   assert.match(card.text(),/失败.*密码响应缺失/);
   assert.doesNotMatch(card.text(),/任务完成，待确认/);
  }else if(name==='progress_controls'){
   const header=wrapper.get('.registration-batch>header');
   for(const text of ['停止','取消','重跑失败'])assert.ok(header.findAll('button').some(button=>button.text()===text),text);
   assert.ok(header.find('select[aria-label="选择任务批次"]').exists());
   const steps=wrapper.findAll('.registration-steps>li');
   assert.equal(steps.length,2);assert.match(steps[0].text(),/分配网络/);
   assert.match(wrapper.text(),/依赖与执行记录/);
   assert.match(wrapper.get('.registration-progress details').text(),/依赖阶段.*分配网络/);
   await steps[0].get('[aria-label="查看分配网络的关系与证据"]').trigger('click');await settle();
   const evidence=wrapper.get('dialog[aria-label="注册步骤关系与证据"]');
   assert.equal(evidence.attributes('open'),'');
   assert.match(evidence.text(),/耗时1\.0 秒/);
   await evidence.trigger('cancel');await settle();assert.equal(evidence.attributes('open'),undefined);
   await steps[1].get('button').trigger('click');await settle();
   assert.deepEqual(openTask,[['9007199254740995','9007199254740997','email_otp']]);
   assert.equal(wrapper.find('[data-resizable-table]').exists(),false);
  }else if(name==='list_controls'){
   for(const label of ['重试','删除','取消排队','刷新'])assert.ok(wrapper.findAll('.registration-toolbar button').some(button=>button.text()===label),label);
   assert.equal(wrapper.get('[aria-label="恢复注册任务列宽"]').text(),'恢复列宽');
   for(const label of ['ID','邮箱','邮箱来源','代理','状态','开始日期','截止日期','错误'])assert.ok(wrapper.find(`thead [aria-label="筛选${label}"]`).exists(),label);
   assert.ok(wrapper.find('nav[aria-label="注册任务分页"]').exists());
   assert.ok(wrapper.find('.registration-table-wrap').exists());
   assert.equal(wrapper.find('[data-resizable-table]').exists(),false,'legacy resizer must not own the Vue list');
   const resize=wrapper.get('button[aria-label^="调整ID列宽"]'),column=wrapper.findAll('col')[1];
   const before=parseFloat(column.element.style.width);
   await resize.trigger('keydown',{key:'ArrowRight'});
   assert.equal(parseFloat(column.element.style.width),before+10,'Vue column sizing responds to the keyboard');
   await wrapper.get('[aria-label="恢复注册任务列宽"]').trigger('click');
   assert.equal(localStorage.getItem('gpt_console_table_widths_jobs'),null);
   const result=wrapper.get('[data-registration-result]');
   assert.ok(result.find('summary').exists());assert.match(result.text(),/remote response was not recorded/);
  }else if(name==='batch_counts'){
   const option=wrapper.get('select[aria-label="选择任务批次"]').text();
   assert.match(option,/运行\s*2/);assert.match(option,/等待\s*10/);
   assert.doesNotMatch(option,/运行\s*12/);
  }else throw Error(`unknown registration Vue contract: ${name}`);
  console.log(`ok ${name}`);
 }finally{h.close();fence();}
}
if(require.main===module)run(process.argv[2]).catch(error=>{console.error(error);process.exitCode=1;});
module.exports={run};
