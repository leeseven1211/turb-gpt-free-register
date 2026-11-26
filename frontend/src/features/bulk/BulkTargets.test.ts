import {flushPromises, mount} from '@vue/test-utils';
import {afterEach, describe, expect, it, vi} from 'vitest';
import BulkTargets from './BulkTargets.vue';
const wrappers: ReturnType<typeof mount>[]=[];
afterEach(()=>{wrappers.splice(0).forEach(x=>x.unmount());document.body.innerHTML='';});
describe('目标表的身份、详情和焦点',()=>{
  it('canonical checkbox与owned/blocker任务分别传字符串，刷新保持焦点',async()=>{
    const openTask=vi.fn(); const item={canonical_target_id:'9007199254740993',account_id:'9007199254740994',owned_task_id:'9007199254740995',owned_run_id:'9007199254740996',blocker_task_id:'9007199254740997',email:'a@example.test',state:'failed',stage_label:'设置密码',reason:{summary:'请求失败',display_code:'REQUEST_UNKNOWN'},result:{result:{summary:'保留完整摘要',capabilities:{password_setup:{state:'failed'}}}}};
    const wrapper=mount(BulkTargets,{attachTo:document.body,props:{items:[item],selected:new Set<string>(),loading:false,error:'',openTask}});wrappers.push(wrapper);
    const checkbox=wrapper.get('[data-bulk-target]');await checkbox.setValue(true);expect(wrapper.emitted('toggle')?.[0]).toEqual(['9007199254740993',true]);
    await wrapper.get('[data-owned-task]').trigger('click');expect(openTask).toHaveBeenLastCalledWith('9007199254740995','9007199254740996');await wrapper.get('[data-blocker-task]').trigger('click');expect(openTask).toHaveBeenLastCalledWith('9007199254740997',null);
    (checkbox.element as HTMLElement).focus();await wrapper.setProps({items:[{...item}]});expect(document.activeElement).toBe(checkbox.element);
    await wrapper.get('[data-result-detail]').trigger('click');await flushPromises();const dialog=document.querySelector('[role="dialog"]')!;expect(dialog.textContent).toContain('REQUEST_UNKNOWN');expect(dialog.textContent).toContain('设置密码');expect(dialog.textContent).toContain('补密码：失败');
    (dialog.querySelector('[data-close-detail]') as HTMLElement).click();await flushPromises();expect(document.activeElement).toBe(wrapper.get('[data-result-detail]').element);
    await wrapper.get('[data-result-detail]').trigger('click');await flushPromises();
    const escape=new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true});
    document.querySelector('[role="dialog"]')!.dispatchEvent(escape);await flushPromises();
    expect(escape.defaultPrevented).toBe(true);expect(document.querySelector('[role="dialog"]')).toBeNull();
  });
  it('页选半选，服务端摘要按文本渲染且加载时不提供旧范围操作',async()=>{
    const wrapper=mount(BulkTargets,{props:{items:[{canonical_target_id:'1',account_id:'5',result:{summary:'<img src=x onerror=alert(1)>'}},{canonical_target_id:'2',account_id:'6'}],selected:new Set(['1']),loading:false,error:'',openTask:vi.fn()}});wrappers.push(wrapper);
    expect((wrapper.get('[data-select-page]').element as HTMLInputElement).indeterminate).toBe(true);expect(wrapper.find('img').exists()).toBe(false);await wrapper.setProps({loading:true,items:[]});expect(wrapper.find('[data-bulk-target]').exists()).toBe(false);
  });
  it('轮询更新保留正在复制的文本，取消文本选择后应用最新内容',async()=>{
    const item={canonical_target_id:'1',account_id:'5',result:{summary:'选中的旧摘要'}};
    const wrapper=mount(BulkTargets,{attachTo:document.body,props:{items:[item],selected:new Set<string>(),loading:false,error:'',openTask:vi.fn()}});wrappers.push(wrapper);
    const node=wrapper.get('[data-result-detail]').element.firstChild!;const selection=window.getSelection()!,range=document.createRange();range.selectNodeContents(node);selection.removeAllRanges();selection.addRange(range);
    await wrapper.setProps({items:[{...item,result:{summary:'更新摘要'}}]});expect(wrapper.get('[data-result-detail]').text()).toBe('选中的旧摘要');expect(selection.toString()).toBe('选中的旧摘要');
    selection.removeAllRanges();document.dispatchEvent(new Event('selectionchange'));await flushPromises();expect(wrapper.get('[data-result-detail]').text()).toBe('更新摘要');
  });
  it('长结果和错误以共享短分类展示，完整原文保留在详情',async()=>{
    const summary='本轮授权失败，但是已有可用凭证仍然保留用于后续人工核查';
    const reason='远端请求未能确认返回结果，需要到完整诊断中核查';
    const wrapper=mount(BulkTargets,{attachTo:document.body,props:{items:[{canonical_target_id:'1',account_id:'5',state:'failed',result:{summary,credential_confirmation:'unconfirmed',existing_asset_preserved:true},reason:{summary:reason,code:'network.timeout'}}],selected:new Set<string>(),loading:false,error:'',openTask:vi.fn()}});wrappers.push(wrapper);
    expect([...wrapper.get('[data-result-detail]').text()].length).toBeLessThanOrEqual(10);
    expect([...wrapper.get('.bulk-target-reason button').text()].length).toBeLessThanOrEqual(10);
    expect(wrapper.get('[data-result-detail]').text()).toBe('授权失败已保留');
    expect(wrapper.find('.list-cell').exists()).toBe(true);
    await wrapper.get('[data-result-detail]').trigger('click');await flushPromises();
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain(summary);
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain(reason);
  });
});
