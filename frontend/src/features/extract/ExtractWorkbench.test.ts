import {mount,flushPromises} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import ExtractWorkbench from './ExtractWorkbench.vue';
import type {ExtractApi} from './contracts';
const wrappers:ReturnType<typeof mount>[]=[];
function setup(){
 const api={
  config:vi.fn(async()=>({providers:[{id:'legacy',label:'传统平台',modes:['extract_only','manual_payment'],link_types:['upi','pix'],default_type:'upi'}],batch_workers_default:4,batch_workers_max:8})),
  summary:vi.fn(async()=>({today_extracted:0})),
  batches:vi.fn(async()=>({items:[{batch_id:7,title:'合成批次'}],total:125,page:1})),
  batch:vi.fn(async()=>({item:{batch_id:7}})),
  tasks:vi.fn(async()=>({items:[{task_id:'9007199254740993',email:'extract@example.test',provider_id:'legacy',mode:'extract_only',task_status:'failed',extraction_status:'failed',error:'long raw diagnostic text'}],total:125,page:1,counts:{}})),
  candidates:vi.fn(async()=>({total:0,selected_count:0})),create:vi.fn(async()=>({ok:true,batch_id:9,started:2})),detail:vi.fn(async()=>({item:{task_id:1}})),action:vi.fn(async()=>({ok:true,accepted:true})),paymentEntry:vi.fn(async()=>({entry:{payment_url:'https://pay.example.test'}})),
 } as unknown as ExtractApi;
 const wrapper=mount(ExtractWorkbench,{attachTo:document.body,props:{deps:{api,visible:true}}});wrappers.push(wrapper);return {wrapper,api};
}
beforeEach(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};vi.spyOn(window,'scrollTo').mockImplementation(()=>{});});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());document.body.replaceChildren();});
describe('extract list standards',()=>{
 it('moves filters into headings and count-row chips while retaining server filter values',async()=>{
  const {wrapper,api}=setup();await flushPromises();
  await wrapper.get('thead button[aria-label="筛选平台"]').trigger('click');await flushPromises();
  const provider=document.querySelector<HTMLInputElement>('[data-extract-option="legacy"] input')!;expect(provider).not.toBeNull();provider.checked=true;provider.dispatchEvent(new Event('change',{bubbles:true}));await flushPromises();
  const count=wrapper.get('[data-extract-count-row]');expect(count.text()).toContain('125');expect(count.get('.list-filter-summary').text()).toContain('传统平台');
  expect(vi.mocked(api.tasks).mock.calls.at(-1)?.[0]).toMatchObject({provider:'legacy',page:1});
  await count.get('[aria-label="清除平台筛选"]').trigger('click');await flushPromises();expect(vi.mocked(api.tasks).mock.calls.at(-1)?.[0]).toMatchObject({provider:'',page:1});
 });
 it('keeps selected bulk actions inside the count row',async()=>{
  const {wrapper}=setup();await flushPromises();
  await wrapper.get('input[aria-label="选择提链任务 9007199254740993"]').setValue(true);
  const row=wrapper.get('[data-extract-count-row]');
  expect(row.text()).toContain('已选 1 项');expect(row.text()).toContain('同步原单');
  expect(wrapper.find('.ui-list-bulkbar').exists()).toBe(false);
 });
 it('limits default result text, preserves full detail, and gives both pagers jump controls',async()=>{
  const {wrapper,api}=setup();await flushPromises();
  const result=wrapper.get('[data-extract-result]');expect([...result.get('summary').text()].length).toBeLessThanOrEqual(10);expect(result.get('summary').text()).not.toContain('long raw');expect(result.text()).toContain('long raw diagnostic');
  const pagination=wrapper.get('nav[aria-label="提链任务分页"]');await pagination.get('[aria-label="跳转页码"]').setValue('4');await pagination.get('form').trigger('submit');await flushPromises();
  expect(vi.mocked(api.tasks).mock.calls.at(-1)?.[0]).toMatchObject({page:4,size:20});
  await pagination.get('[aria-label="每页条数"]').setValue('50');await flushPromises();expect(vi.mocked(api.tasks).mock.calls.at(-1)?.[0]).toMatchObject({page:1,size:50});
  expect(document.querySelector('nav[aria-label="提链批次分页"]')).toBeNull();
  await wrapper.get('button[aria-label="筛选批次"]').trigger('click');await flushPromises();
  expect(document.querySelector('nav[aria-label="提链批次分页"] [aria-label="跳转页码"]')).not.toBeNull();
 });
 it('browses history without reloading or disturbing the current task page',async()=>{
  const {wrapper,api}=setup();await flushPromises();
  const tasks=vi.mocked(api.tasks);
  tasks.mockResolvedValueOnce({...await tasks.mock.results[0]!.value,page:2});
  await wrapper.get('nav[aria-label="提链任务分页"] [aria-label="第 2 页"]').trigger('click');await flushPromises();
  const scroll=wrapper.get('.extract-table-wrap').element;
  scroll.scrollTop=80;
  const calls=tasks.mock.calls.length;
  vi.mocked(api.batches).mockResolvedValueOnce({items:[{batch_id:9,title:'第二页批次'}],total:125,page:2});
  await wrapper.get('button[aria-label="筛选批次"]').trigger('click');await flushPromises();
  const picker=document.querySelector('nav[aria-label="提链批次分页"]')!;
  (picker.querySelector('[aria-label="第 2 页"]') as HTMLButtonElement).click();await flushPromises();
  expect(api.batches).toHaveBeenLastCalledWith(2,expect.any(AbortSignal));
  expect(tasks).toHaveBeenCalledTimes(calls);
  expect(scroll.scrollTop).toBe(80);
  expect(wrapper.get('nav[aria-label="提链任务分页"] [aria-current="page"]').text()).toBe('2');
  const option=document.querySelector<HTMLElement>('[data-extract-option="9"]')!;
  expect(option.textContent).toContain('第二页批次');
  const selection=option.querySelector<HTMLInputElement>('input')!;selection.checked=true;selection.dispatchEvent(new Event('change',{bubbles:true}));await flushPromises();
  expect(tasks).toHaveBeenLastCalledWith(expect.objectContaining({batch:'9',page:1}),expect.any(AbortSignal));
  expect(scroll.scrollTop).toBe(0);
 });
 it('retains candidate promotion, limit, type and configured concurrency in the created request',async()=>{
  const {wrapper,api}=setup();await flushPromises();vi.mocked(api.candidates).mockResolvedValue({total:2,selected_count:2});
  await wrapper.findAll('button').find(button=>button.text()==='新建批次')!.trigger('click');await flushPromises();
  const dialog=wrapper.get('dialog[aria-labelledby="extract-create-title"]'),field=(name:string)=>dialog.findAll('label').find(item=>item.text().startsWith(name))!;
  expect((field('并发').get('input').element as HTMLInputElement).value).toBe('4');
  expect(field('模式').findAll('option').map(option=>option.attributes('value'))).toEqual(['extract_only','manual_payment']);
  await field('套餐优惠').get('select').setValue('half_price');await field('本批运行数量').get('input').setValue(2);await field('链接类型').get('select').setValue('pix');
  await dialog.findAll('button').find(button=>button.text()==='刷新匹配数量')!.trigger('click');await flushPromises();
  await dialog.findAll('button').find(button=>button.text().startsWith('创建并运行'))!.trigger('click');await flushPromises();
  expect(vi.mocked(api.create).mock.calls.at(-1)?.[0]).toMatchObject({workers:4,type:'pix',limit:2,filters:{promotion:'half_price'}});
 });
 it('does not close a new invalid submission using an earlier accepted batch receipt',async()=>{
  const {wrapper,api}=setup();await flushPromises();vi.mocked(api.candidates).mockResolvedValue({total:2,selected_count:2});
  const open=()=>wrapper.findAll('button').find(button=>button.text()==='新建批次')!.trigger('click');await open();await flushPromises();let dialog=wrapper.get('dialog[aria-labelledby="extract-create-title"]');await dialog.findAll('button').find(button=>button.text().startsWith('创建并运行'))!.trigger('click');await flushPromises();expect(api.create).toHaveBeenCalledTimes(1);expect(dialog.attributes()).not.toHaveProperty('open');
  await open();await flushPromises();dialog=wrapper.get('dialog[aria-labelledby="extract-create-title"]');await dialog.findAll('label').find(field=>field.text().startsWith('并发'))!.get('input').setValue(0);await dialog.findAll('button').find(button=>button.text().startsWith('创建并运行'))!.trigger('click');await flushPromises();expect(dialog.attributes()).toHaveProperty('open');expect(dialog.text()).toContain('批次并发请输入');expect(api.create).toHaveBeenCalledTimes(1);
 });
 it('retains structured detail and independent payment dialog with safe URLs and QR fallback',async()=>{
  const {wrapper,api}=setup();await flushPromises();vi.mocked(api.detail).mockResolvedValue({item:{task_id:3,account_id:11,email:'detail@example.test',task_status:'failed',extraction_status:'succeeded',payment_status:'failed',has_payment_entry:true,has_extract_link:true,remote_raw:{receipt:'<remote>'}},events:[{label:'收到平台回执',message:'full evidence'}],history:[{task_id:3,run_id:1,extraction_status:'succeeded'}]});
  vi.mocked(api.paymentEntry).mockResolvedValue({entry:{payment_page_url:'javascript:alert(1)',payment_url:'https://pay.example.test/order',qr_image_url_png:'https://pay.example.test/a.png',qr_image_url_svg:'https://pay.example.test/a.svg',qr_data:'<qr text>',amount:0,expires_at:new Date(Date.now()+60000).toISOString()}});
  await wrapper.findAll('tbody button').find(button=>button.text()==='详情')!.trigger('click');await flushPromises();
  const detail=wrapper.get('dialog[aria-labelledby="extract-detail-title"]');expect(detail.text()).toContain('收到平台回执');expect(detail.text()).toContain('历史运行');expect(detail.text()).toContain('<remote>');expect(detail.find('remote').exists()).toBe(false);expect(detail.findAll('button').map(button=>button.text())).toContain('复制提链链接');
  await detail.findAll('button').find(button=>button.text()==='读取支付入口')!.trigger('click');await flushPromises();
  const payment=wrapper.get('dialog[aria-labelledby="extract-payment-title"]');expect(payment.find('a[href^="javascript:"]').exists()).toBe(false);expect(payment.get('a').attributes('href')).toBe('https://pay.example.test/order');expect(payment.text()).toContain('有效期至');
  await payment.get('img').trigger('error');expect(payment.get('img').attributes('src')).toContain('a.svg');await payment.get('img').trigger('error');expect(payment.text()).toContain('二维码图片加载失败');
  await payment.trigger('cancel');await flushPromises();expect(detail.attributes()).toHaveProperty('open');expect(payment.attributes()).not.toHaveProperty('open');
 });
 it('uses historical run statuses and evidence without current-task queue defaults',async()=>{
  const {wrapper,api}=setup();await flushPromises();vi.mocked(api.detail).mockResolvedValue({item:{task_id:3,task_status:'failed'},history:[{run_id:1,status:'failed',error_message:'上一轮平台失败'},{run_id:2,status:'partial_success',message:'保留部分结果'},{run_id:3,status:'success',message:'该轮已完成'}]});
  await wrapper.findAll('tbody button').find(button=>button.text()==='详情')!.trigger('click');await flushPromises();
  const history=wrapper.findAll('details').find(item=>item.get('summary').text().startsWith('历史运行'))!,rows=history.findAll('article');expect(rows[0]!.get('p').text()).toBe('失败 · 上一轮平台失败');expect(rows[1]!.get('p').text()).toBe('部分成功 · 保留部分结果');expect(rows[2]!.get('p').text()).toBe('已完成 · 该轮已完成');
  expect(history.text()).not.toContain('排队中');expect(history.text()).not.toContain('等待开始提链');expect(rows[0]!.get('pre').text()).toContain('error_message');
 });
 it('loads Node A in detail without opening payment, copies its entry and distinguishes inside padding from backdrop',async()=>{
  const copyText=vi.fn();const {wrapper,api}=setup();(wrapper.props('deps') as any).copyText=copyText;await flushPromises();vi.mocked(api.detail).mockResolvedValue({item:{task_id:'9007199254740993',has_payment_entry:true}});vi.mocked(api.paymentEntry).mockResolvedValue({entry:{payment_page_url:'https://pay.example.test/node-a',qr_data:'node-a-qr'}});
  await wrapper.findAll('tbody button').find(button=>button.text()==='详情')!.trigger('click');await flushPromises();
  const detail=wrapper.get('dialog[aria-labelledby="extract-detail-title"]'),node=detail.get('[data-extract-node-a]');expect(node.text()).toContain('node-a-qr');expect(wrapper.get('dialog[aria-labelledby="extract-payment-title"]').attributes()).not.toHaveProperty('open');
  await node.findAll('button').find(button=>button.text()==='复制支付页面')!.trigger('click');await flushPromises();expect(copyText).toHaveBeenCalledWith('https://pay.example.test/node-a');
  (detail.element as HTMLElement).getBoundingClientRect=()=>({left:100,top:100,right:600,bottom:600,width:500,height:500,x:100,y:100,toJSON(){}});await detail.trigger('click',{clientX:110,clientY:110});expect(detail.attributes()).toHaveProperty('open');await detail.trigger('click',{clientX:20,clientY:20});await flushPromises();expect(detail.attributes()).not.toHaveProperty('open');
 });
 it('retains scroll for quiet refresh but resets manual refresh and batch changes',async()=>{
  const {wrapper}=setup();await flushPromises();const scroll=wrapper.get('.extract-table-wrap').element;scroll.scrollTop=120;scroll.scrollLeft=90;
  await (wrapper.vm as any).load({quiet:true});expect([scroll.scrollTop,scroll.scrollLeft]).toEqual([120,90]);await (wrapper.vm as any).load({force:true});expect([scroll.scrollTop,scroll.scrollLeft]).toEqual([0,0]);
 });
});
