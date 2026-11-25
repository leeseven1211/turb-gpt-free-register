import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import RegistrationRetryReceipt from './RegistrationRetryReceipt.vue';
import type {RegistrationRetryEntry,RegistrationRetryReceipt as Receipt} from './setupActions';
import type {AccountActionContext} from './useAccounts';
import {realAdapter} from './uiTestSupport';

const wrappers:ReturnType<typeof mount>[]=[];
const context=():AccountActionContext=>({accountIds:['7','8'],expectedEmails:{'7':'seven@test','8':'eight@test'},querySnapshot:realAdapter().normalize(),archived:'0',rowHints:[]});
const receipt=(extra:Partial<Receipt>={}):Receipt=>({started:[],reused:[],skipped:[],started_count:0,reused_count:0,skipped_count:0,...extra});
function setup(){const notify=vi.fn();const wrapper=mount(RegistrationRetryReceipt,{attachTo:document.body,props:{notify}});wrappers.push(wrapper);return{wrapper,notify,body:new DOMWrapper(document.body)};}
beforeEach(()=>{document.body.innerHTML='<div id="accountRegistrationReceiptHost"></div>';});
afterEach(()=>{wrappers.splice(0).forEach(wrapper=>wrapper.unmount());document.body.replaceChildren();});

describe('注册重跑回执',()=>{
  it('初始隐藏，空回执仍显示原零计数摘要且无按钮或详情',async()=>{
    const {wrapper,body}=setup(),open=vi.fn();
    expect(body.get<HTMLElement>('#accountRegistrationRetryResultV2').element.hidden).toBe(true);
    wrapper.vm.showResult(receipt(),context(),open);await flushPromises();
    const panel=body.get<HTMLElement>('#accountRegistrationRetryResultV2');
    expect(panel.element.hidden).toBe(false);expect(panel.classes()).toEqual(['column-filter-summary','account-search-summary']);
    expect(panel.attributes()).toMatchObject({role:'status','aria-live':'polite'});
    expect(panel.text()).toBe('注册重跑：已创建 0 个，进行中 0 个，跳过 0 个');
    expect(panel.find('button').exists()).toBe(false);expect(panel.find('details').exists()).toBe(false);expect(open).not.toHaveBeenCalled();
  });

  it('原顺序显示started/reused/skipped并保留显式零计数，缺失计数用数组长度',async()=>{
    const {wrapper,body}=setup();
    wrapper.vm.showResult({started:[{account_id:7,task_id:71}],started_count:0,reused:[{account_id:8,task_id:81}],skipped:[{account_id:9,reason:'正在执行'}]},context(),vi.fn());await flushPromises();
    const panel=body.get('#accountRegistrationRetryResultV2');
    expect(panel.get('.column-filter-summary-label').text()).toBe('注册重跑：已创建 0 个，进行中 1 个，跳过 1 个');
    expect(panel.findAll('li').map(row=>row.text())).toEqual(['账号 #7 · 已创建 查看任务 #71','账号 #8 · 进行中 查看任务 #81','账号 #9 · 正在执行']);
    expect(panel.get('summary').text()).toBe('查看任务及跳过原因');expect(panel.get('details').attributes('open')).toBeUndefined();
  });

  it('逐项和集合按钮把原回执传 owner，优先显示统一任务和运行标识',async()=>{
    const {wrapper,body}=setup(),open=vi.fn();
    const started=[{account_id:7,task_id:71,operation_task_id:99,run_id:72,operation_run_id:100,job_id:17,email:'seven@test'}];
    const reused=[{account_id:8,operation_task_id:81,run_id:82,job_id:18},{account_id:9,job_id:19}];
    wrapper.vm.showResult(receipt({started,reused,started_count:1,reused_count:2}),context(),open);await flushPromises();
    const buttons=body.findAll('[data-registration-retry-result]');
    expect(buttons[0]!.attributes()).toMatchObject({'data-registration-retry-result':'0','data-registration-retry-task-id':'99','data-registration-retry-run-id':'100'});
    expect(buttons[1]!.attributes()).toMatchObject({'data-registration-retry-result':'1','data-registration-retry-task-id':'81','data-registration-retry-run-id':'82'});
    expect(buttons[2]!.text()).toBe('查看任务 #19');expect(buttons[2]!.attributes('data-registration-retry-task-id')).toBeUndefined();expect(buttons[2]!.attributes('data-registration-retry-run-id')).toBeUndefined();
    for(let index=0;index<buttons.length;index++){await buttons[index]!.trigger('click');expect(open).toHaveBeenLastCalledWith([[...started,...reused][index]]);}
    await body.get('[data-registration-retry-tasks]').trigger('click');expect(open).toHaveBeenLastCalledWith([...started,...reused]);
    expect(body.get('summary').text()).toBe('查看任务');
  });

  it('统一任务和运行标识超过安全整数时仍完整显示和传递',async()=>{
    const {wrapper,body}=setup(),open=vi.fn();
    const item={account_id:7,task_id:71,operation_task_id:'9007199254740993',operation_run_id:'9007199254740995',run_id:72};
    wrapper.vm.showResult(receipt({started:[item],started_count:1}),context(),open);await flushPromises();
    const button=body.get('[data-registration-retry-result="0"]');
    expect(button.text()).toBe('查看任务 #9007199254740993');
    expect(button.attributes('data-registration-retry-run-id')).toBe('9007199254740995');
    await button.trigger('click');expect(open).toHaveBeenCalledWith([item]);
  });

  it('跳过原因优先reason再error再默认文案，所有不可信返回值只作文本',async()=>{
    const {wrapper,body}=setup();
    const malicious={account_id:'<img src=x onerror=alert(1)>',task_id:'"><script>alert(1)</script>',run_id:'" onfocus="x'} as unknown as RegistrationRetryEntry;
    wrapper.vm.showResult({started:[malicious],skipped:[{account_id:8,reason:'<script>原因</script>',error:'不应显示'},{account_id:9,error:'<img>错误'},{account_id:10}]},context(),vi.fn());await flushPromises();
    const panel=body.get('#accountRegistrationRetryResultV2');
    expect(panel.find('script').exists()).toBe(false);expect(panel.find('img').exists()).toBe(false);expect(panel.find('[onfocus]').exists()).toBe(false);
    expect(panel.text()).toContain('<script>原因</script>');expect(panel.text()).not.toContain('不应显示');expect(panel.text()).toContain('<img>错误');expect(panel.text()).toContain('账号 #10 · 当前不可重跑');
    expect(panel.get('[data-registration-retry-result="0"]').attributes('data-registration-retry-task-id')).toBe(malicious.task_id);
  });

  it('显示时冻结回执，替换结果后按钮只调用新owner且详情重新收起',async()=>{
    const {wrapper,body}=setup(),first=vi.fn(),second=vi.fn();
    const started=[{account_id:7,task_id:71,run_id:72}],input=receipt({started,started_count:1});
    wrapper.vm.showResult(input,context(),first);started[0]!.task_id=999;started.push({account_id:8,task_id:81,run_id:82});await flushPromises();
    await body.get('[data-registration-retry-result="0"]').trigger('click');
    expect(first).toHaveBeenCalledWith([{account_id:7,task_id:71,run_id:72}]);expect(Object.isFrozen(first.mock.calls[0]![0][0])).toBe(true);
    body.get<HTMLDetailsElement>('details').element.open=true;
    wrapper.vm.showResult(receipt({reused:[{account_id:9,task_id:91}],reused_count:1}),context(),second);await flushPromises();
    expect(body.get('details').attributes('open')).toBeUndefined();expect(body.findAll('[data-registration-retry-result]')).toHaveLength(1);
    await body.get('[data-registration-retry-tasks]').trigger('click');expect(second).toHaveBeenCalledWith([{account_id:9,task_id:91}]);expect(first).toHaveBeenCalledTimes(1);
  });

  it('全跳过无任务按钮，不把跳过记录伪造为可跳转任务',async()=>{
    const {wrapper,body}=setup(),open=vi.fn();
    wrapper.vm.showResult(receipt({skipped:[{account_id:7,task_id:999,reason:'已经完成'}],skipped_count:1}),context(),open);await flushPromises();
    expect(body.find('button').exists()).toBe(false);expect(body.get('summary').text()).toBe('查看任务及跳过原因');expect(open).not.toHaveBeenCalled();
  });

  it('导航失败保留回执并反馈，卸载后不会继续触发导航',async()=>{
    const {wrapper,body,notify}=setup(),open=vi.fn(async()=>{throw new Error('offline');});
    wrapper.vm.showResult(receipt({started:[{account_id:7,task_id:71}],started_count:1}),context(),open);await flushPromises();
    await wrapper.vm.openTasks();expect(notify).toHaveBeenCalledWith('注册重跑请求已处理，打开任务失败: offline');expect(body.text()).toContain('查看任务 #71');
    const exposed=wrapper.vm;wrapper.unmount();await exposed.openTasks();expect(open).toHaveBeenCalledTimes(1);
  });
});
