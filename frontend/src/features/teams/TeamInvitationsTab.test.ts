// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {flushPromises,mount,type VueWrapper} from '@vue/test-utils';
import TeamInvitationsTab from './TeamInvitationsTab.vue';
import type {TeamsApi} from '../../api/teams';
import type {JoinRequestDTO,TeamInvitationDTO,TeamsHostCallbacks} from './contracts';

function deferred<T>(){
  let resolve!:(value:T)=>void,reject!:(cause:unknown)=>void;
  const promise=new Promise<T>((done,fail)=>{resolve=done;reject=fail;});
  return{promise,resolve,reject};
}
function invitation(teamId:string):TeamInvitationDTO{
  return{id:'8001',team_id:teamId,remote_invitation_id:null,account:{id:'3001',email:'member@example.test',archived:false},
    email_snapshot:'member@example.test',invitation_state:'pending',membership_state:'unconfirmed',last_verified_at:null,updated_at:'2026-11-27T12:00:00Z',
    latest_execution:{task_id:null,run_id:null,status:'none',stage:null,waiting_reason_code:null,error_info:null},
    actions:{continue:{enabled:true,reason_code:null},retry:{enabled:true,reason_code:null},view_task:{enabled:false,reason_code:null}}};
}
function receipt(teamId:string,id:string):JoinRequestDTO{
  return{id,team_id:teamId,operation:'continue',accepted:true,reused:false,status:'preparing',waiting_reason_code:null,
    selection_id:null,selection_revision:null,batch_id:'9201',task_id:'9301',run_id:'9401',created_at:'2026-11-27T12:00:00Z',
    counts:{requested_count:1,unique_count:1,duplicate_count:0,pending_count:1,accepted_count:0,reused_count:0,skipped_count:0,failed_count:0},
    capacity:{basis:'purchased_seats',purchased_seats:10,planned_member_limit:null,effective_limit:10,occupied_count:1,
      available_count:9,additional_required:null,can_submit:true,blocking_reason_code:null},
    items_url:`/api/teams/${teamId}/join-requests/${id}`};
}
function host():TeamsHostCallbacks{
  return{notify:vi.fn(),formatDateTime:value=>value||'—',openTask:vi.fn(),openTasksForTeam:vi.fn(),
    openAccountDetail:vi.fn(),openAccountsCandidateMode:vi.fn(),onNavigation:vi.fn()};
}
function apiForActions(){
  return{
    listInvitations:vi.fn<TeamsApi['listInvitations']>(async teamId=>({
      items:[invitation(teamId)],total:1,page:1,page_size:20,revision:'invitations:1',
      facets:{invitation_state:[],membership_state:[],execution_status:[],stage:[]},
    })),
    getJoinRequest:vi.fn<TeamsApi['getJoinRequest']>(async(teamId,id)=>({
      request:receipt(teamId,id),items:[],total:0,page:1,page_size:1,revision:'requests:1',
    })),
    continueInvitation:vi.fn<TeamsApi['continueInvitation']>(),
    retryInvitation:vi.fn<TeamsApi['retryInvitation']>(),
    continueInvitationsBulk:vi.fn<TeamsApi['continueInvitationsBulk']>(),
    retryInvitationsBulk:vi.fn<TeamsApi['retryInvitationsBulk']>(),
  };
}
const actions=[
  {method:'continueInvitation',label:'继续加入',bulk:false},
  {method:'retryInvitation',label:'重跑',bulk:false},
  {method:'continueInvitationsBulk',label:'批量继续加入',bulk:true},
  {method:'retryInvitationsBulk',label:'批量重跑',bulk:true},
] as const;
let wrapper:VueWrapper;
beforeEach(()=>Object.defineProperty(document,'hidden',{configurable:true,value:false}));
afterEach(()=>{wrapper?.unmount();vi.useRealTimers();vi.restoreAllMocks();});

async function clickAction(action:typeof actions[number]){
  if(action.bulk)await wrapper.get<HTMLInputElement>('tbody input[type="checkbox"]').setValue(true);
  const buttons=action.bulk?wrapper.findAll('button'):wrapper.findAll('tbody button');
  await buttons.find(button=>button.text()===action.label)!.trigger('click');
}
function currentActionDisabled(action:typeof actions[number]){
  if(action.bulk)return wrapper.findAll<HTMLButtonElement>('button').find(button=>button.text()==='处理中…')?.element.disabled;
  return wrapper.findAll<HTMLButtonElement>('tbody button').find(button=>button.text()===action.label)!.element.disabled;
}

it.each(actions)('$label 的旧 Team 回包不能污染当前 Team 或解除当前提交状态',async action=>{
  const api=apiForActions(),old=deferred<JoinRequestDTO>(),current=deferred<JoinRequestDTO>(),callbacks=host();
  api[action.method].mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
  wrapper=mount(TeamInvitationsTab,{props:{api:api as unknown as TeamsApi,teamId:'7',visible:true,callbacks}});
  await flushPromises();
  await clickAction(action);
  await wrapper.setProps({teamId:'8'});
  await flushPromises();
  if(action.bulk)await wrapper.get<HTMLInputElement>('tbody input[type="checkbox"]').setValue(true);
  const currentButtons=action.bulk?wrapper.findAll<HTMLButtonElement>('button'):wrapper.findAll<HTMLButtonElement>('tbody button');
  expect(currentButtons.find(button=>button.text()===action.label)!.element.disabled).toBe(false);
  await clickAction(action);
  old.resolve(receipt('7','9101'));
  await flushPromises();
  expect(callbacks.notify).not.toHaveBeenCalled();
  expect(api.getJoinRequest).not.toHaveBeenCalled();
  expect(wrapper.emitted('refresh-team')).toBeUndefined();
  expect(currentActionDisabled(action)).toBe(true);
  current.resolve(receipt('8','9102'));
  await flushPromises();
  expect(callbacks.notify).toHaveBeenCalledOnce();
  expect(api.getJoinRequest).toHaveBeenCalledWith('8','9102',{page:1,page_size:1},expect.any(AbortSignal));
  expect(wrapper.emitted('refresh-team')).toHaveLength(1);
});

it('同 Team 暂时隐藏时保留受理追踪，恢复后才读取请求结果',async()=>{
  const api=apiForActions(),pending=deferred<JoinRequestDTO>(),callbacks=host();
  api.continueInvitation.mockReturnValueOnce(pending.promise);
  wrapper=mount(TeamInvitationsTab,{props:{api:api as unknown as TeamsApi,teamId:'7',visible:true,callbacks}});
  await flushPromises();
  await clickAction(actions[0]);
  await wrapper.setProps({visible:false});
  const reads=api.listInvitations.mock.calls.length;
  pending.resolve(receipt('7','9101'));
  await flushPromises();
  expect(api.listInvitations).toHaveBeenCalledTimes(reads);
  expect(api.getJoinRequest).not.toHaveBeenCalled();
  await wrapper.setProps({visible:true});
  await flushPromises();
  expect(api.getJoinRequest).toHaveBeenCalledWith('7','9101',{page:1,page_size:1},expect.any(AbortSignal));
});

it.each([
  {source:'轮询',outcome:'成功'},
  {source:'轮询',outcome:'失败'},
  {source:'操作刷新',outcome:'成功'},
  {source:'操作刷新',outcome:'失败'},
] as const)('普通刷新被 $source 接替后，静默请求 $outcome 会解除加载状态',async({source,outcome})=>{
  vi.useFakeTimers();
  type ListResponse=Awaited<ReturnType<TeamsApi['listInvitations']>>;
  const api=apiForActions(),normal=deferred<ListResponse>(),silent=deferred<ListResponse>();
  const row=invitation('7');
  if(source==='轮询')row.latest_execution.status='running';
  const response:ListResponse={items:[row],total:1,page:1,page_size:20,revision:'invitations:1'};
  api.listInvitations.mockResolvedValueOnce(response).mockReturnValueOnce(normal.promise).mockReturnValueOnce(silent.promise);
  api.continueInvitation.mockResolvedValue(receipt('7','9101'));
  wrapper=mount(TeamInvitationsTab,{props:{api:api as unknown as TeamsApi,teamId:'7',visible:true,callbacks:host()}});
  await flushPromises();
  await wrapper.get('.ui-refresh-button').trigger('click');
  expect(wrapper.get('.ui-refresh-button').attributes('disabled')).toBeDefined();
  if(source==='轮询')await vi.advanceTimersByTimeAsync(3000);
  else await clickAction(actions[0]);
  await flushPromises();
  expect(api.listInvitations).toHaveBeenLastCalledWith('7',
    expect.objectContaining({include_facets:'0'}),expect.any(AbortSignal));
  if(outcome==='成功')silent.resolve(response);
  else silent.reject(new Error('静默读取暂时失败'));
  await flushPromises();
  expect(wrapper.get('.ui-refresh-button').attributes('disabled')).toBeUndefined();
  expect(wrapper.get('.ui-table-wrap').attributes('aria-busy')).toBe('false');
  normal.resolve(response);
  await flushPromises();
  expect(wrapper.get('.ui-refresh-button').attributes('disabled')).toBeUndefined();
});

it('过期普通和静默请求的 finally 不得清除接替它们的新普通刷新状态',async()=>{
  vi.useFakeTimers();
  type ListResponse=Awaited<ReturnType<TeamsApi['listInvitations']>>;
  const api=apiForActions(),oldNormal=deferred<ListResponse>(),oldSilent=deferred<ListResponse>(),
    currentNormal=deferred<ListResponse>();
  const row=invitation('7');row.latest_execution.status='running';
  const response:ListResponse={items:[row],total:1,page:1,page_size:20,revision:'invitations:1'};
  api.listInvitations.mockResolvedValueOnce(response).mockReturnValueOnce(oldNormal.promise)
    .mockReturnValueOnce(oldSilent.promise).mockReturnValueOnce(currentNormal.promise);
  wrapper=mount(TeamInvitationsTab,{props:{api:api as unknown as TeamsApi,teamId:'7',visible:true,callbacks:host()}});
  await flushPromises();
  await wrapper.get('.ui-refresh-button').trigger('click');
  await vi.advanceTimersByTimeAsync(3000);
  void(wrapper.vm as unknown as {refresh:()=>Promise<void>}).refresh();
  await flushPromises();
  oldNormal.resolve(response);
  await flushPromises();
  expect(wrapper.get('.ui-refresh-button').attributes('disabled')).toBeDefined();
  oldSilent.resolve(response);
  await flushPromises();
  expect(wrapper.get('.ui-refresh-button').attributes('disabled')).toBeDefined();
  expect(wrapper.get('.ui-table-wrap').attributes('aria-busy')).toBe('true');
  currentNormal.resolve(response);
  await flushPromises();
  expect(wrapper.get('.ui-refresh-button').attributes('disabled')).toBeUndefined();
  expect(wrapper.get('.ui-table-wrap').attributes('aria-busy')).toBe('false');
});
