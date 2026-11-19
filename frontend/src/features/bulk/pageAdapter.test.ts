import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {flushPromises} from '@vue/test-utils';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';

const script=readFileSync(resolve(process.cwd(),'../webui/static/js/pages/bulk/page.js'),'utf8');
type Adapter={
  activate():Promise<void>;navigate(view:string,extra?:Record<string,string>,focus?:boolean):Promise<void>;
  restoreNavigation(navigation:Record<string,string>):void;navigationState():Record<string,string>;setVisible(value:boolean):void;
};
const browser=window as unknown as {BulkTasks?:Adapter;BulkPlanReport?:{render:ReturnType<typeof vi.fn>}};
beforeEach(()=>{
  document.body.innerHTML='<section id="tab-bulk"><div id="bulk-page-root" data-module-url="/bulk.js" data-style-url="/bulk.css"></div></section>';
  vi.stubGlobal('showToast',vi.fn());vi.stubGlobal('activateTab',vi.fn());vi.stubGlobal('recordNavigationHistory',vi.fn());
  vi.stubGlobal('formatDateTime',String);vi.stubGlobal('facetLabel',String);vi.stubGlobal('openAccountTaskLog',vi.fn());
  browser.BulkPlanReport={render:vi.fn(()=>'<section class="bulk-plan-report">只读套餐报告</section>')};
});
afterEach(()=>{browser.BulkTasks?.setVisible(false);delete browser.BulkTasks;delete browser.BulkPlanReport;document.body.innerHTML='';vi.unstubAllGlobals();});
function install(loadModule=vi.fn().mockRejectedValue(new Error('组件离线'))){
  const run=new Function('loadBulkModule',script.replace('import(root.dataset.moduleUrl)','loadBulkModule(root.dataset.moduleUrl)'));
  run(loadModule);
  return{api:browser.BulkTasks!,loadModule,run};
}
function response(data:unknown){return{ok:true,status:200,json:async()=>({ok:true,data})} as Response;}

it('组件加载失败仍可只读分页与查看报告，全程仅发送 GET',async()=>{
  const fetcher=vi.fn(async(path:string)=>response(path.endsWith('/report?view=current')
    ?{operation_key:'plan_check',phase:'completed',business_summary:{'account.token_refresh.unconfirmed':1,'country_query.failed':2}}
    :path.includes('/batches/17?')
      ?{operation_key:'plan_check'}
      :{items:[{id:17,name:'<img src=x>'}],next_cursor:'opaque/+=',summary:{total_batches:3}}));
  vi.stubGlobal('fetch',fetcher);
  const {api}=install();await api.activate();
  const root=document.getElementById('bulk-page-root')!;
  expect(root.textContent).toContain('3 个批次');expect(root.querySelector('img')).toBeNull();
  root.querySelector<HTMLButtonElement>('[data-bulk-fallback-action="next"]')!.click();await flushPromises();
  expect(new URL(fetcher.mock.calls.at(-1)![0],'http://local').searchParams.get('cursor')).toBe('opaque/+=');
  root.querySelector<HTMLButtonElement>('[data-bulk-fallback-action="report"]')!.click();await flushPromises();
  expect(root.textContent).toContain('只读套餐报告');expect(browser.BulkPlanReport!.render).toHaveBeenCalledTimes(1);
  expect(browser.BulkPlanReport!.render.mock.calls[0]![1]).toContain('AT 刷新失败');
  expect(browser.BulkPlanReport!.render.mock.calls[0]![1]).toContain('国家项查询失败');
  expect(fetcher.mock.calls.every(call=>(call as unknown as [string,RequestInit])[1].method==='GET')).toBe(true);
});

it('组件并发加载只挂载一次，重复脚本保持同一页面所有者',async()=>{
  let release!:(value:unknown)=>void;
  const loadModule=vi.fn(()=>new Promise(resolve=>{release=resolve;}));
  const instance={setVisible:vi.fn(),activate:vi.fn(),navigationState:()=>({tab:'bulk',view:'list'})};
  const mountBulk=vi.fn(()=>instance);
  const h=install(loadModule);const first=h.api.activate(),second=h.api.activate();
  release({mountBulk});await Promise.all([first,second]);
  expect(loadModule).toHaveBeenCalledTimes(1);expect(mountBulk).toHaveBeenCalledTimes(1);
  h.run(loadModule);expect(browser.BulkTasks).toBe(h.api);
});

it('加载失败后可重试完整页面，清除只读监听且不会重复挂载',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>response({items:[],page:{has_more:false}})));
  const h=install();await h.api.activate();
  const instance={setVisible:vi.fn(),activate:vi.fn(),navigationState:()=>({tab:'bulk',view:'list'})},mountBulk=vi.fn(()=>instance);
  h.loadModule.mockResolvedValueOnce({mountBulk});
  document.querySelector<HTMLButtonElement>('[data-bulk-fallback-action="load"]')!.click();await flushPromises();
  expect(mountBulk).toHaveBeenCalledTimes(1);expect(document.getElementById('bulk-page-root')!.hasAttribute('data-bulk-fallback')).toBe(false);
  await h.api.activate();expect(mountBulk).toHaveBeenCalledTimes(1);
});

it('只读失败路径也校验日期并保留旧详情链接兼容',async()=>{
  const fetcher=vi.fn(async()=>response({items:[],page:{has_more:false}}));vi.stubGlobal('fetch',fetcher);
  const {api}=install();api.restoreNavigation({view:'list',created_from:'2026-02-31'});await api.activate();
  expect(fetcher).not.toHaveBeenCalled();expect(document.body.textContent).toContain('创建日期无效');
  api.restoreNavigation({view:'detail',batch_id:'9007199254740993',result_state:'request_unknown',q:'old',cursor:'old-scope'});
  expect(api.navigationState()).toEqual({tab:'bulk',view:'detail',batch_id:'9007199254740993',result_state:'failed'});
});

it('只读截止日期使用次日零点排他边界并保留当前筛选',async()=>{
  const fetcher=vi.fn<(path:string,options?:RequestInit)=>Promise<Response>>(async()=>response({items:[],page:{has_more:false}}));vi.stubGlobal('fetch',fetcher);
  const {api}=install();api.restoreNavigation({view:'list',q:'日期',created_from:'2026-03-08',created_to:'2026-03-08'});await api.activate();
  const query=new URL(fetcher.mock.calls[0]![0],'http://local').searchParams;
  expect(query.get('created_before')).toBe(new Date('2026-03-09T00:00:00').toISOString());
  expect(query.get('q')).toBe('日期');expect(query.has('created_to')).toBe(false);
});
