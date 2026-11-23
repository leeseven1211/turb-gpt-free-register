import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import CodexFilters from './CodexFilters.vue';
const filters = {q:'',plan:'',status:'',oauth_status:'',account_id:'',sub2api_id:'',date_from:'',date_to:'',expired_date:''};
const wrappers:ReturnType<typeof mount>[]=[];
beforeEach(()=>vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}}));
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());vi.unstubAllGlobals();});
describe('Codex列筛选',()=>{
  it('未知已选套餐保留为单选值，改选后不生成CSV',async()=>{
    const wrapper=mount(CodexFilters,{attachTo:document.body,props:{column:{key:'plan',label:'Plan',kind:'enum',fields:['plan']},modelValue:{...filters,plan:'future'},facets:{plan:[{value:'plus',count:3}]},open:true}});wrappers.push(wrapper);await flushPromises();
    const body=new DOMWrapper(document.body);
    expect(body.find('input[type="radio"][value="future"]').exists()).toBe(true);
    expect(body.get<HTMLInputElement>('input[value="future"]').element.checked).toBe(true);
    await body.get('input[value="plus"]').setValue(true);
    expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({...filters,plan:'plus'});
  });
  it('紧凑筛选复用日期字段，清除此列保留其他条件且不改输入对象',async()=>{
    const model={...filters,q:'keep',date_from:'2026-11-01',date_to:'2026-11-14'};
    const wrapper=mount(CodexFilters,{attachTo:document.body,props:{modelValue:model,facets:{},open:true}});wrappers.push(wrapper);await flushPromises();
    const body=new DOMWrapper(document.body);
    expect(body.find('[data-filter-value="date"]').exists()).toBe(true);
    await body.get('[data-filter-value="date"] input').setValue(true);await flushPromises();
    expect(body.findAll<HTMLInputElement>('input[type="date"]').map(i=>i.element.value)).toEqual(['2026-11-01','2026-11-14']);
    await body.findAll('button').find(b=>b.text()==='清除此列')!.trigger('click');
    expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({...filters,q:'keep'});
    expect(model.date_from).toBe('2026-11-01');
    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([false]);
  });
  it('真实鼠标点击先提交单选值再关闭，键盘change保持浮层开启',async()=>{
    const events:{kind:string;value:unknown}[]=[];
    const wrapper=mount(CodexFilters,{attachTo:document.body,props:{column:{key:'plan',label:'Plan',kind:'enum',fields:['plan']},modelValue:{...filters},facets:{plan:[{value:'plus',count:3}]},open:true,
      'onUpdate:modelValue':value=>events.push({kind:'value',value}),
      'onUpdate:open':value=>events.push({kind:'open',value}),
    }});wrappers.push(wrapper);await flushPromises();
    const body=new DOMWrapper(document.body);
    body.get('input[value="plus"]').element.dispatchEvent(new MouseEvent('click',{detail:1,bubbles:true,cancelable:true}));
    expect(events[0]).toEqual({kind:'value',value:{...filters,plan:'plus'}});
    expect(events.findIndex(event=>event.kind==='open')).toBeGreaterThan(events.findIndex(event=>event.kind==='value'));
    expect(events.find(event=>event.kind==='open')?.value).toBe(false);
    events.length=0;
    await body.get('input[value=""]').setValue(true);
    expect(events).toEqual([{kind:'value',value:{...filters}}]);
  });
});
