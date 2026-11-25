import {DOMWrapper,flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import CodexCredentials from './CodexCredentials.vue';
import type {CodexCallbacks} from '../../api/codex';
const wrappers:ReturnType<typeof mount>[]=[];
const callbacks:CodexCallbacks={notify:vi.fn(),confirm:vi.fn(()=>true),openTasks:vi.fn(),operationWorkers:()=>2};
let listFailure=false;
const fetchMock=vi.fn(async(path:string,options?:RequestInit)=>{
  const url=new URL(path,'http://localhost');
  if(url.pathname==='/api/codex'){
    if(listFailure)throw new Error('网络中断');
    const page=Number(url.searchParams.get('page')||1);
    return new Response(JSON.stringify({accounts:[{filename:`page-${page}.json`,email:`page-${page}@example.test`,plan:'plus',oauth_status:'valid'}],total:45,page,page_size:Number(url.searchParams.get('page_size')||20),facets:{plan:[{value:'plus',count:45}]}}),{headers:{'Content-Type':'application/json'}});
  }
  if(url.pathname==='/api/codex/upload-sub2-bulk')return new Response(JSON.stringify({ok:true,accepted:true,queued_count:1,queued:[{filename:'page-1.json',accepted:true,task_id:99,run_id:100}],skipped_count:1,skipped:[{filename:'page-2.json',reason:'保留'}]}),{status:202,headers:{'Content-Type':'application/json'}});
  throw new Error(`测试禁止未声明请求 ${path} ${options?.method||'GET'}`);
});
async function page(){const w=mount(CodexCredentials,{attachTo:document.body,props:{callbacks}});wrappers.push(w);w.vm.setVisible(true);await flushPromises();return w;}
beforeEach(()=>{listFailure=false;fetchMock.mockClear();vi.clearAllMocks();vi.stubGlobal('fetch',fetchMock);vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});Object.defineProperty(document,'hidden',{configurable:true,value:false});});
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());localStorage.clear();vi.unstubAllGlobals();});
describe('Codex整页接入',()=>{
  it('数量和列筛选摘要处于同栏，隐藏页面关闭筛选Portal',async()=>{
    const w=await page();expect(w.find('.cx-toolbar-main').exists()).toBe(true);
    expect(w.get('.cx-toolbar-main').text()).toContain('45 个凭证');
    await w.get('thead button[aria-label="筛选Plan"]').trigger('click');await flushPromises();
    new DOMWrapper(document.body).get('input[type="radio"][value="plus"]').element.dispatchEvent(new MouseEvent('click',{detail:1,bubbles:true,cancelable:true}));await flushPromises();
    expect(w.get('.cx-toolbar-main').text()).toContain('Plan：Plus');
    expect(fetchMock.mock.calls.filter(([url])=>url.startsWith('/api/codex?')).at(-1)?.[0]).toContain('plan=plus');
    w.vm.setVisible(false);await flushPromises();expect(new DOMWrapper(document.body).find('.list-filter-popover').exists()).toBe(false);
  });
  it('跨页选择通过原批量上传入口提交全部filename，202只回执且跳过项保留',async()=>{
    const w=await page();expect(w.find('input[aria-label="选择凭证 page-1.json"]').exists()).toBe(true);
    await w.get('input[aria-label="选择凭证 page-1.json"]').setValue(true);
    await w.findAll('button').find(b=>b.text()==='下一页')!.trigger('click');await flushPromises();
    await w.get('input[aria-label="选择凭证 page-2.json"]').setValue(true);
    expect(w.get('.cx-toolbar-main').text()).toContain('已选 2');
    await w.get('#btnCodexUploadSub2V2').trigger('click');await flushPromises();
    const request=fetchMock.mock.calls.find(([url])=>url==='/api/codex/upload-sub2-bulk');
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({filenames:['page-1.json','page-2.json']});
    expect(w.get('.cx-toolbar-main').text()).toContain('已选 1');
    expect(w.find('#btnCodexUploadProgressV2').exists()).toBe(true);
    expect(callbacks.openTasks).not.toHaveBeenCalled();
  });
  it('每页数同时改变page和size时只产生一个正确请求',async()=>{
    const w=await page();expect(w.find('select[aria-label="每页条数"]').exists()).toBe(true);
    expect(w.get('select[aria-label="每页条数"]').findAll('option').map(option=>option.attributes('value'))).toEqual(['10','20','30','50','100']);
    await w.findAll('button').find(b=>b.text()==='下一页')!.trigger('click');await flushPromises();
    fetchMock.mockClear();await w.get('select[aria-label="每页条数"]').setValue('50');await flushPromises();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url=new URL(fetchMock.mock.calls[0]![0],'http://localhost');expect(url.searchParams.get('page')).toBe('1');expect(url.searchParams.get('page_size')).toBe('50');
  });
  it('刷新失败保留旧数据并展示重试，不显示刷新成功',async()=>{
    const w=await page();expect(w.text()).toContain('page-1@example.test');
    listFailure=true;await w.get('#btnRefreshCodexV2').trigger('click');await flushPromises();
    expect(w.text()).toContain('page-1@example.test');expect(w.get('[role="alert"]').text()).toContain('网络中断');
    expect(callbacks.notify).not.toHaveBeenCalledWith(expect.stringContaining('已刷新'));
    listFailure=false;await w.get('[role="alert"] button').trigger('click');await flushPromises();expect(w.find('[role="alert"]').exists()).toBe(false);
  });
  it('跨页选择保留全部批量入口，切归档清选择并以归档scope读取',async()=>{
    const w=await page();await w.get('input[aria-label="选择凭证 page-1.json"]').setValue(true);
    const ids=['btnCodexRefreshTokenBulkV2','btnCodexReauthorizeBulkV2','btnCodexDownloadBulkV2','btnCodexDownloadBulkCpaV2','btnCodexUploadSub2V2','btnCodexArchiveBulkV2','btnCodexDeleteBulkV2'];
    expect(w.get('[aria-label="选中凭证批量操作"]').findAll('button').map(b=>b.attributes('id'))).toEqual(ids);
    w.vm.setArchived(true);await flushPromises();
    expect(w.find('[aria-label="选中凭证批量操作"]').exists()).toBe(false);
    expect(w.get('.cx-toolbar-main').text()).toContain('已归档');
    expect(new URL(fetchMock.mock.calls.at(-1)![0],'http://localhost').searchParams.get('archived')).toBe('only');
    await w.get('input[aria-label="选择凭证 page-1.json"]').setValue(true);
    expect(w.get('#btnCodexArchiveBulkV2').text()).toBe('恢复选中');
  });
  it('document隐藏关闭行Portal，恢复不复活旧浮层',async()=>{
    const w=await page();await w.get('button[aria-label="更多操作 page-1.json"]').trigger('click');await flushPromises();
    expect(new DOMWrapper(document.body).find('.cx-row-menu').exists()).toBe(true);
    Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));await flushPromises();
    expect(new DOMWrapper(document.body).find('.cx-row-menu').exists()).toBe(false);
    Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));await flushPromises();
    expect(new DOMWrapper(document.body).find('.cx-row-menu').exists()).toBe(false);
  });
});
