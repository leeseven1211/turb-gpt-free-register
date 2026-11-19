import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import AccountFilters from './AccountFilters.vue';
import {realAdapter} from './uiTestSupport';
const wrappers:ReturnType<typeof mount>[]=[];
beforeEach(()=>vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}}));
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());vi.unstubAllGlobals();});
describe('账号列筛选组件',()=>{
 it('未知已选值和零计数保留，多选只提交该列且不关闭浮层',async()=>{
  const query=realAdapter().normalize({plan:['future','plus'],filters:{source:['keep']}});
  const w=mount(AccountFilters,{attachTo:document.body,props:{query,facets:{plan:[{value:'plus',count:0},{value:'free',count:9},{value:'unused',count:0}]},label:(_g:string,v:string)=>v,column:{key:'plan',label:'套餐',kind:'enum'},open:true}});wrappers.push(w);await flushPromises();
  const body=new DOMWrapper(document.body);
  expect(body.get<HTMLInputElement>('input[value="future"]').element.checked).toBe(true);expect(body.get<HTMLInputElement>('input[value="plus"]').element.checked).toBe(true);expect(body.find('input[value="unused"]').exists()).toBe(false);
  await body.get('input[value="free"]').setValue(true);
  expect(w.emitted('change')?.at(-1)).toEqual(['plan',['future','plus','free']]);expect(w.emitted('update:open')).toBeUndefined();expect(query.filters.source).toEqual(['keep']);
 });
 it('账号ID保留带逗号的文本，日期清除不重建其他查询',async()=>{
  const w=mount(AccountFilters,{attachTo:document.body,props:{query:realAdapter().normalize({filters:{id:'#12,3',email:'preserve'},date_from:'2026-11-01'}),facets:{},label:(_g:string,v:string)=>v,open:true}});wrappers.push(w);await flushPromises();const body=new DOMWrapper(document.body);
  expect(body.get<HTMLInputElement>('input[type="text"]').element.value).toBe('#12,3');await body.get('input[type="text"]').setValue('#07,8');expect(w.emitted('change')?.at(-1)).toEqual(['id','#07,8']);
  await body.get('select[aria-label="选择账号筛选列"]').setValue('date');expect(body.findAll<HTMLInputElement>('input[type="date"]').map(x=>x.element.value)).toEqual(['2026-11-01','']);await body.findAll('button').find(x=>x.text()==='清除此列')!.trigger('click');expect(w.emitted('clear')?.at(-1)).toEqual(['date']);
 });
});
