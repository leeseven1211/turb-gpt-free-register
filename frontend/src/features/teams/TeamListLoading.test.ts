// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {flushPromises,mount,type VueWrapper} from '@vue/test-utils';
import TeamsListView from './TeamsListView.vue';
import type {TeamsApi} from '../../api/teams';
import type {TeamDTO,TeamsHostCallbacks} from './contracts';

type TeamList=Awaited<ReturnType<TeamsApi['list']>>;
function deferred<T>(){
  let resolve!:(value:T)=>void,reject!:(cause:unknown)=>void;
  const promise=new Promise<T>((done,fail)=>{resolve=done;reject=fail;});
  return{promise,resolve,reject};
}
const team:TeamDTO={
  id:'7',revision:3,workspace_id:'workspace-list',name:'列表加载测试',display_name:null,
  manager_account:{id:'31',email:'manager@example.test',archived:false},role:'owner',
  purchased_seats:5,planned_member_limit:null,confirmed_member_count:2,pending_invite_count:0,
  processing_count:0,last_sync_status:'success',last_synced_at:'2026-11-27T12:00:00Z',
};
function page(name='当前列表'):TeamList{
  return{items:[{...team,name}],total:21,page:1,page_size:20,revision:'teams:1'};
}
function callbacks():TeamsHostCallbacks{
  return{notify:vi.fn(),formatDateTime:value=>value||'—',openTask:vi.fn(),openTasksForTeam:vi.fn(),
    openAccountDetail:vi.fn(),openAccountsCandidateMode:vi.fn(),onNavigation:vi.fn()};
}
let wrapper:VueWrapper;
beforeEach(()=>Object.defineProperty(document,'hidden',{configurable:true,value:false}));
afterEach(()=>{wrapper?.unmount();vi.restoreAllMocks();vi.useRealTimers();});

it.each(['成功','失败'] as const)('静默刷新%s接替普通刷新后解除刷新与分页忙碌状态',async result=>{
  const normal=deferred<TeamList>(),silent=deferred<TeamList>();
  const list=vi.fn<TeamsApi['list']>().mockResolvedValueOnce(page()).mockReturnValueOnce(normal.promise).mockReturnValueOnce(silent.promise);
  wrapper=mount(TeamsListView,{props:{api:{list} as unknown as TeamsApi,visible:true,callbacks:callbacks()}});
  await flushPromises();
  await wrapper.get('.ui-refresh-button').trigger('click');
  const vm=wrapper.vm as unknown as InstanceType<typeof TeamsListView>;
  const next=vm.refresh({silent:true});
  await flushPromises();
  expect(list.mock.calls[1]?.[1]?.aborted).toBe(true);
  expect(wrapper.get<HTMLButtonElement>('.ui-refresh-button').element.disabled).toBe(true);
  if(result==='成功')silent.resolve(page('静默刷新后的列表'));
  else silent.reject(new Error('静默读取暂不可用'));
  await next;
  await flushPromises();
  expect(wrapper.get('.ui-refresh-button').text()).toBe('刷新');
  expect(wrapper.get<HTMLButtonElement>('.list-pagination__next').element.disabled).toBe(false);
  expect(wrapper.get<HTMLSelectElement>('.list-pagination__size select').element.disabled).toBe(false);
  normal.resolve(page('旧普通刷新'));
  await flushPromises();
  expect(wrapper.text()).not.toContain('旧普通刷新');
});

it('被接替的普通刷新结束不会提前解除当前静默请求的忙碌状态',async()=>{
  const normal=deferred<TeamList>(),silent=deferred<TeamList>();
  const list=vi.fn<TeamsApi['list']>().mockResolvedValueOnce(page()).mockReturnValueOnce(normal.promise).mockReturnValueOnce(silent.promise);
  wrapper=mount(TeamsListView,{props:{api:{list} as unknown as TeamsApi,visible:true,callbacks:callbacks()}});
  await flushPromises();
  await wrapper.get('.ui-refresh-button').trigger('click');
  const vm=wrapper.vm as unknown as InstanceType<typeof TeamsListView>;
  const next=vm.refresh({silent:true});
  normal.resolve(page('旧普通刷新'));
  await flushPromises();
  expect(wrapper.get<HTMLButtonElement>('.ui-refresh-button').element.disabled).toBe(true);
  expect(wrapper.get<HTMLButtonElement>('.list-pagination__next').element.disabled).toBe(true);
  silent.resolve(page('静默刷新后的列表'));
  await next;
  await flushPromises();
  expect(wrapper.get<HTMLButtonElement>('.ui-refresh-button').element.disabled).toBe(false);
  expect(wrapper.get<HTMLButtonElement>('.list-pagination__next').element.disabled).toBe(false);
});

it('活跃工作区的真实轮询接替手动刷新后恢复分页',async()=>{
  vi.useFakeTimers();
  const normal=deferred<TeamList>(),poll=deferred<TeamList>();
  const initial=page();
  initial.items[0]!.last_sync_status='queued';
  const list=vi.fn<TeamsApi['list']>().mockResolvedValueOnce(initial).mockReturnValueOnce(normal.promise).mockReturnValueOnce(poll.promise);
  wrapper=mount(TeamsListView,{props:{api:{list} as unknown as TeamsApi,visible:true,callbacks:callbacks()}});
  await flushPromises();
  await wrapper.get('.ui-refresh-button').trigger('click');
  await vi.advanceTimersByTimeAsync(3000);
  expect(list).toHaveBeenCalledTimes(3);
  expect(list.mock.calls[2]?.[0]).toMatchObject({include_facets:'0'});
  expect(list.mock.calls[1]?.[1]?.aborted).toBe(true);
  poll.resolve(page('轮询返回的列表'));
  await flushPromises();
  expect(wrapper.get('.ui-refresh-button').text()).toBe('刷新');
  expect(wrapper.get<HTMLButtonElement>('.list-pagination__next').element.disabled).toBe(false);
  normal.resolve(page('旧手动刷新'));
  await flushPromises();
  expect(wrapper.text()).not.toContain('旧手动刷新');
});
