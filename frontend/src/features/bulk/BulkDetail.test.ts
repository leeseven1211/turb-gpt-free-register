import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,describe,expect,it,vi} from 'vitest';
import type {BulkDetailDependencies,BulkNavigation} from './contracts';
import BulkDetail from './BulkDetail.vue';
const wrappers:ReturnType<typeof mount>[]=[];
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());document.body.innerHTML='';});
function fixture(view:BulkNavigation['view']='detail',visible?:boolean,initial:Partial<BulkNavigation>={}) {
  const request=vi.fn(async<T>(path:string):Promise<T>=>(path.includes('/report?')?{operation_key:'plan_check',phase:'running',totals:{accounts:11}}:path.includes('/targets?')?{items:[{canonical_target_id:'6',account_id:'7',email:'test@example.test'}],page:{has_more:false,next_cursor:null,page_size:50}}:{id:'9007199254740993',name:'批次甲',operation_key:'plan_check',summary_revision:7,target_count:11,summary:{failed:11},control:{state:'active',revision:5},selection_summary:{query:{status:['active']}},rounds_head:[{id:'9007199254740994',round_no:1,state:'completed'}]}) as T);
  const submit=vi.fn(async<T>():Promise<T>=>({id:'9007199254740998',state:'preparing'} as T));
  const callbacks={navigate:vi.fn(),updateNavigation:vi.fn(),notify:vi.fn(),formatDateTime:String,openTask:vi.fn(),copyBatch:vi.fn()};
  const deps={api:{request},intents:{submit,pending:()=>[],recover:vi.fn()},callbacks,now:()=>100000} as BulkDetailDependencies;
  const wrapper=mount(BulkDetail,{attachTo:document.body,props:{navigation:{tab:'bulk',view,batch_id:'9007199254740993',...initial},deps,...(visible===undefined?{}:{visible})}});wrappers.push(wrapper);return {wrapper,request,submit,callbacks};
}
describe('真实批次详情组件',()=>{
  it('确认取消/提交只有一个写入，原焦点返回；scope切换关闭旧确认',async()=>{
    const h=fixture();await flushPromises();const button=h.wrapper.get('[data-bulk-action="retry"]');(button.element as HTMLElement).focus();await button.trigger('click');await flushPromises();
    expect(document.querySelector('[role="alertdialog"]')?.textContent).toContain('11 个账号');
    (document.querySelector('[data-confirm-cancel]') as HTMLElement).click();await flushPromises();expect(h.submit).not.toHaveBeenCalled();expect(document.activeElement).toBe(button.element);
    await button.trigger('click');await flushPromises();(document.querySelector('[data-confirm-submit]') as HTMLElement).click();await flushPromises();expect(h.submit).toHaveBeenCalledTimes(1);
    await h.wrapper.get('[data-bulk-action="stop"]').trigger('click');await flushPromises();expect(document.querySelector('[role="alertdialog"]')).not.toBeNull();
    await h.wrapper.setProps({navigation:{tab:'bulk',view:'detail',batch_id:'42'}});await flushPromises();expect(document.querySelector('[role="alertdialog"]')).toBeNull();expect(h.submit).toHaveBeenCalledTimes(1);
  });
  it('报告入口焦点、复制语义、目标刷新不打断checkbox',async()=>{
    const h=fixture();await flushPromises();const vm=h.wrapper.vm as unknown as {refresh(force?:boolean):Promise<void>;showReport():Promise<void>};
    await vm.showReport();expect(document.activeElement).toBe(h.wrapper.get('[data-bulk-plan-report]').element);
    const checkbox=h.wrapper.get('[data-bulk-target]');(checkbox.element as HTMLElement).focus();await vm.refresh(true);expect(document.activeElement).toBe(checkbox.element);
    await h.wrapper.get('[data-bulk-action="copy-targets"]').trigger('click');expect(h.callbacks.copyBatch).toHaveBeenLastCalledWith({status:['active']},{kind:'batch_targets',batch_id:'9007199254740993',selection:{kind:'all'}},'plan_check');
    await h.wrapper.get('[data-bulk-action="copy-query"]').trigger('click');expect(h.callbacks.copyBatch).toHaveBeenLastCalledWith({status:['active']},null,'plan_check');
  });
  it('常驻但隐藏slice不发请求，visible恢复只由refresh推进',async()=>{
    const h=fixture('list');await flushPromises();expect(h.request).not.toHaveBeenCalled();
    const vm=h.wrapper.vm as unknown as {setVisible(value:boolean):void;refresh(force?:boolean):Promise<void>;needsRefresh:boolean};
    await h.wrapper.setProps({navigation:{tab:'bulk',view:'detail',batch_id:'9007199254740993'}});vm.setVisible(true);await vm.refresh();expect(h.request).toHaveBeenCalled();
    vm.setVisible(false);const calls=h.request.mock.calls.length;await vm.refresh(true);expect(h.request).toHaveBeenCalledTimes(calls);expect(vm.needsRefresh).toBe(false);
  });
  it('初始URL在detail但Shell隐藏时不读，props恢复只等Shell刷新',async()=>{
    const h=fixture('detail',false);await flushPromises();expect(h.request).not.toHaveBeenCalled();await h.wrapper.setProps({visible:true});await flushPromises();expect(h.request).not.toHaveBeenCalled();await (h.wrapper.vm as unknown as {refresh():Promise<void>}).refresh();expect(h.request).toHaveBeenCalledTimes(3);
  });
  it('结果列筛选与数量同栏条件清除复用真实查询并重置游标',async()=>{
    const h=fixture('detail',undefined,{cursor:'opaque.direct'});await flushPromises();
    await h.wrapper.get('thead button[aria-label="筛选结果状态"]').trigger('click');await flushPromises();
    const body=new DOMWrapper(document.body);
    await body.get('input[type="radio"][value="failed"]').setValue(true);await flushPromises();
    expect(h.callbacks.updateNavigation).toHaveBeenLastCalledWith({result_state:'failed',cursor:''});
    const targetPath=h.request.mock.calls.map(call=>call[0]).filter(path=>path.includes('/targets?')).at(-1)!;
    const query=new URL(targetPath,'http://local').searchParams;
    expect(query.get('state[]')).toBe('failed');expect(query.has('cursor')).toBe(false);
    const countRow=h.wrapper.get('[data-bulk-target-count-row]');
    expect(countRow.text()).toContain('共 11 个账号');expect(countRow.get('.list-filter-summary').text()).toContain('失败');
    await countRow.get('.list-filter-summary button').trigger('click');await flushPromises();
    expect(h.callbacks.updateNavigation).toHaveBeenLastCalledWith({result_state:'',cursor:''});
    expect(new URL(h.request.mock.calls.map(call=>call[0]).filter(path=>path.includes('/targets?')).at(-1)!,'http://local').searchParams.has('state[]')).toBe(false);
    expect(h.wrapper.find('.list-filter-summary').exists()).toBe(false);
    expect(h.submit).not.toHaveBeenCalled();
  });
  it('零匹配时仍可通过结果列表头清除筛选',async()=>{
    const h=fixture('detail',undefined,{result_state:'failed'});await flushPromises();
    h.request.mockImplementation(async<T>(path:string):Promise<T>=>(path.includes('/targets?')?{items:[],page:{has_more:false,next_cursor:null,page_size:50}}:{id:'9007199254740993',target_count:11,summary:{failed:0},control:{state:'ended'}}) as T);
    await (h.wrapper.vm as unknown as {refresh(force?:boolean):Promise<void>}).refresh(true);await flushPromises();
    expect(h.wrapper.find('[data-bulk-target]').exists()).toBe(false);
    await h.wrapper.get('thead button[aria-label="筛选结果状态"]').trigger('click');await flushPromises();
    await new DOMWrapper(document.body).get('input[type="radio"][value=""]').setValue(true);await flushPromises();
    expect(h.callbacks.updateNavigation).toHaveBeenLastCalledWith({result_state:'',cursor:''});
    expect(h.submit).not.toHaveBeenCalled();
  });
});
