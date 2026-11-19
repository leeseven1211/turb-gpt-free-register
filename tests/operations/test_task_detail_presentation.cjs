// Exercise the live Vue detail and evidence components; legacy dialog renderers are retired.
const assert = require('node:assert/strict');
const test = require('node:test');
const {createVueHarness} = require('../frontend_vue_loader.cjs');
const h = createVueHarness();
const {createRequire} = require('node:module');
const path = require('node:path');
const {DOMWrapper} = createRequire(path.join(__dirname,'../../frontend/package.json'))('@vue/test-utils');
const Detail = h.load('src/features/tasks/detail/TaskDetail.vue').default;
const Evidence = h.load('src/features/tasks/detail/StepEvidence.vue').default;
const {tasksApi} = h.load('src/api/tasks.ts');
const originals = {...tasksApi};
const win = h.document.defaultView;
win.HTMLDialogElement.prototype.showModal = function(){this.open=true;};
win.HTMLDialogElement.prototype.close = function(){this.open=false;this.dispatchEvent(new win.Event('close'));};
const flush = async()=>{for(let i=0;i<3;i++)await new Promise(resolve=>setImmediate(resolve));await h.nextTick();};
test.afterEach(()=>{h.cleanup();Object.assign(tasksApi,originals);});
test.after(()=>h.close());
async function display(data) {
  const state = {...data};
  const task = data.task || {id:'70',task_type:'test_archive',target_id:'fixture-archive',status:'failed',last_run_id:'71',
    runs:[{...data.run,id:'71',status:'failed',run_no:1}]};
  tasksApi.detail = async()=>({ok:true,task});
  tasksApi.progress = async(_id,runId)=>({ok:true,progress:state.progress ? {task_id:'70',run_id:runId,revision:'1',main_steps:[],outcome:{status:'failed'},...state.progress} : null});
  tasksApi.events = async()=>({ok:true,items:state.events||[],next_after_id:null,has_more:false});
  tasksApi.logs = async()=>({ok:true,items:state.logs||[],next_cursor:0,has_more:false,available:true});
  const wrapper = h.mount(Detail);
  await wrapper.vm.open('70','71');await flush();
  const body = new DOMWrapper(h.document.body);
  return {wrapper,body,state,task};
}

test('同一失败只显示步骤摘要，无步骤卡时仍能打开两侧证据', async()=>{
  const {body} = await display({run:{error_message:'合成记录未归档',error_info:{display_code:'SYN-42',summary:'归档失败'}},
    progress:{failure:{label:'归档',stage:'archive',message:'合成记录未归档',error_info:{cause_summary:'合成分卷缺失'},evidence:{part:5}}}});
  const failures=body.findAll('.tc-task-failure');assert.equal(failures.length,1);
  const panel=failures[0];assert.doesNotMatch(panel.get('summary').text(),/执行错误/);
  assert.match(panel.get('summary').text(),/合成分卷缺失/);assert.match(panel.get('summary').text(),/SYN-42/);
  assert.equal(panel.attributes('open'),undefined);await panel.get('summary').trigger('click');
  for(const value of ['合成记录未归档','SYN-42','"part": 5'])assert.ok(panel.get('pre').text().includes(value),value);
});

test('同一分类下不同原因以及缺少步骤快照时保留执行错误',async()=>{
  const {body,state,wrapper}=await display({run:{error_info:{summary:'归档失败',cause_summary:'合成目录只读'}},
    progress:{failure:{label:'归档',error_info:{summary:'归档失败',cause_summary:'合成分卷缺失'}}}});
  assert.match(body.get('.tc-task-failure summary').text(),/合成分卷缺失.*执行错误：归档失败 · 合成目录只读/);
  state.progress=null;await wrapper.vm.open('70','71');await flush();
  assert.match(body.get('.tc-task-failure summary').text(),/合成目录只读/);
  assert.match(body.get('.tc-task-failure pre').text(),/"cause_summary": "合成目录只读"/);
});

test('失败明细通过摘要展开，单页步骤不另占一行翻页栏',async()=>{
  const {body}=await display({run:{},progress:{main_steps:[{id:'inspect',label:'检查归档',state:'failed'}],
    failure:{label:'检查归档',message:'汇总文本',country_failures:[{country:'A',summary:'合成一缺页'},{country:'B',summary:'合成二缺页'}]}}});
  const panel=body.get('.tc-task-failure');assert.equal(panel.attributes('open'),undefined);
  assert.doesNotMatch(panel.get('summary').text(),/合成一缺页|合成二缺页|已全部显示/);
  assert.match(panel.get('summary').text(),/2 个国家/);await panel.get('summary').trigger('click');
  assert.match(panel.text(),/A：合成一缺页/);assert.match(panel.text(),/B：合成二缺页/);
  assert.equal(body.find('[data-account-task-progress-pagination]').exists(),false);
});

test('共用原始阶段的事件与日志只归入有明确证据的步骤',async()=>{
  const records=[{id:'1',message:'合成甲记录',main_step_id:'first',raw_stage:'shared'},
    {id:'2',message:'合成乙记录',main_step_id:'second',stage:'shared'},{id:'3',message:'合成无归属',stage:'shared'},
    {id:'4',message:'合成关联编号',event_id:'fixture-event',stage:'shared'},{id:'5',message:'合成旧格式',raw_stage:'only-a'}];
  const {body}=await display({run:{},events:records,logs:records,progress:{main_steps:[
    {id:'first',label:'合成甲',raw_stages:['shared','only-a'],event_ids:['fixture-event']},{id:'second',label:'合成乙',raw_stages:['shared']}]}});
  const events=body.findAll('.tc-event');assert.match(events[2].get('.tc-event-meta').text(),/未关联步骤/);
  assert.match(events[1].get('.tc-event-meta').text(),/合成乙/);
  const first=body.findAll('.tc-step-select')[0];first.element.focus();await first.trigger('click');await flush();
  assert.equal(h.document.activeElement,first.element);assert.equal(first.attributes('aria-pressed'),'true');
  const expected=panel=>{for(const value of ['合成甲记录','合成关联编号','合成旧格式'])assert.match(panel.text(),new RegExp(value));assert.doesNotMatch(panel.text(),/合成乙记录|合成无归属/);};
  expected(body.get('#tc-detail-panel-events'));await body.get('[data-detail-tab="logs"]').trigger('click');await flush();expected(body.get('#tc-detail-panel-logs'));
});

test('首次读取进度即合并同一失败，切换运行不会引用上一次的证据',async()=>{
  const task={id:'70',task_type:'test_archive',target_id:'fixture-archive',status:'failed',last_run_id:'71',runs:[
    {id:'71',status:'failed',run_no:1,error_message:'合成缺页'},{id:'72',status:'failed',run_no:2,error_message:'合成库只读'}]};
  const {body,state}=await display({task,run:{},progress:{failure:{label:'归档',message:'合成缺页'}}});
  assert.match(body.get('.tc-detail-target').attributes('title'),/fixture-archive/);
  assert.equal(body.findAll('.tc-task-failure').length,1);assert.doesNotMatch(body.get('.tc-task-failure summary').text(),/执行错误/);
  assert.match(body.get('.tc-task-failure pre').text(),/合成缺页/);state.progress=null;
  await body.get('select[aria-label="选择执行实例"]').setValue('72');await flush();
  assert.match(body.get('.tc-task-failure summary').text(),/合成库只读/);assert.doesNotMatch(body.get('.tc-task-failure').text(),/合成缺页/);
});

test('选中阶段后可读声明的依赖、首次记录序号和本阶段明确关联的子任务',async()=>{
  // The migrated API explicitly supplies execution.waits_for; UI does not infer dependencies from event counts.
  const steps=[{id:'read',label:'读取样稿'},{id:'merge',label:'合并样稿',observed_order:5,depends_on:['read','old<source>'],
    execution:{kind:'child_task',dependency_state:'satisfied',waits_for:[{task_id:'801',run_id:'802',task_type:'test_archive'}]}},
    {id:'empty',label:'历史样稿',depends_on:[],observed_order:null}];
  const wrapper=h.mount(Evidence,{props:{step:steps[1],siblings:steps}});
  assert.match(wrapper.text(),/依赖阶段读取样稿、old<source>/);assert.match(wrapper.text(),/首次记录第 5 个被记录的阶段/);
  assert.equal((wrapper.text().match(/#801 · 运行 #802/g)||[]).length,1);assert.doesNotMatch(wrapper.text(),/#999|并行|重试/);
  assert.equal(wrapper.find('source').exists(),false);
  await wrapper.setProps({siblings:[{...steps[0],label:'读取新版样稿'},...steps.slice(1)]});assert.match(wrapper.text(),/读取新版样稿/);
  await wrapper.setProps({step:steps[2]});
  assert.doesNotMatch(wrapper.text(),/依赖阶段|首次记录|关联子任务|重试/);
  assert.match(wrapper.text(),/没有足够证据确定依赖或并行关系/);
});
