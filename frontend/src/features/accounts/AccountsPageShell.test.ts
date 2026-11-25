import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import AccountsPageShell from './AccountsPageShell.vue';
import {deferred,presentation,readApi,realAdapter} from './uiTestSupport';
import {createAccountActions} from './actions';
import type {AccountQueuedDependencies} from './queuedActions';
import type {AccountInspectionDependencies} from './useAccountInspection';

function c2aDependencies(){return{request:vi.fn(),notify:vi.fn(),refreshAccounts:vi.fn(),openTasks:vi.fn()};}
function emailChangeDependencies(){return{request:vi.fn(async()=>({sources:[{value:'outlook',label:'Outlook',enabled:true}]})),notify:vi.fn(),refreshAccounts:vi.fn(),openTasks:vi.fn(),syncModalScrollLock:vi.fn()};}
function inspectionDependencies():AccountInspectionDependencies{return{request:vi.fn(async()=>({items:[],total:0})),notify:vi.fn(),operationWorkers:()=>4,randomUUID:()=> 'inspection-key',refreshAccounts:vi.fn(),refreshSummary:vi.fn(),openTask:vi.fn(),formatDateTime:String};}

let wrapper:ReturnType<typeof mount>;
beforeEach(()=>{
  document.body.innerHTML='<div id="accountRegistrationReceiptHost"></div><div id="accountDetailHost"></div><div id="accountEmailChangeHost"></div><div id="accountC2aConfirmHost"></div><div id="accountC2aReceiptHost"></div>';
  Object.defineProperty(document,'hidden',{configurable:true,value:false});
  vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});
  vi.stubGlobal('matchMedia',()=>({matches:false,addEventListener(){},removeEventListener(){}}));
  HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new Event('close'));};
});
it('toolbar keeps in-flight downloads disabled across list refresh and applies capability changes without a second handler',async()=>{
  const {api}=readApi(),response=deferred<unknown>(),request=vi.fn(()=>response.promise),legacy=vi.fn();
  const actions=createAccountActions({request,notify:vi.fn(),confirm:()=>true,clipboard:vi.fn(),downloadBlob:vi.fn(),downloadUrl:vi.fn(),now:()=>new Date(),schedule:()=>1,reloadCodex:vi.fn()});
  wrapper=mount(AccountsPageShell,{attachTo:document.body,props:{adapter:realAdapter(),api,presentation,
    callbacks:{invoke:legacy,openDetail:vi.fn()},detailApi:{roxyProfile:vi.fn()},detailPresentation:{renderBody:()=>'',sourceLabel:()=>''},syncModalScrollLock:vi.fn(),
    initialCapabilities:{},
    c2aDependencies:c2aDependencies(),emailChangeDependencies:emailChangeDependencies(),inspectionDependencies:inspectionDependencies(),actions}});
  const vm=wrapper.vm as unknown as InstanceType<typeof AccountsPageShell>;
  vm.setVisible(true);await flushPromises();
  await wrapper.get<HTMLInputElement>('.account-row-check').setValue(true);await flushPromises();
  const button=document.querySelector<HTMLButtonElement>('#btnDownloadSelectedSessionsV2')!;
  expect(button.disabled).toBe(false);button.click();await flushPromises();
  expect(request).toHaveBeenCalledOnce();expect(button.disabled).toBe(true);
  vm.setPage(2);await flushPromises();
  await wrapper.get<HTMLInputElement>('.account-row-check').setValue(true);await flushPromises();
  expect(button.disabled).toBe(true);button.click();expect(request).toHaveBeenCalledOnce();
  response.resolve({download_url:'/synthetic.zip',added_count:1,skipped_count:0});await flushPromises();
  expect(button.disabled).toBe(false);
  vm.setCapabilities({live_check:{enabled:false,reason:'未配置'}});await flushPromises();
  const live=document.querySelector<HTMLButtonElement>('#btnCheckSelectedLiveV2')!;
  expect(live.getAttribute('aria-disabled')).toBe('true');expect(live.title).toContain('未配置');
  live.click();await flushPromises();expect(legacy).not.toHaveBeenCalled();
  vm.setToolbarBusyLabel('archiveSelectedAccounts','归档中…');await flushPromises();
  expect(document.querySelector('#btnArchiveSelectedAccountsV2')?.textContent).toBe('归档中…');
  vm.setArchived(true);await flushPromises();
  vm.setToolbarBusyLabel('archiveSelectedAccounts');await flushPromises();
  expect(document.querySelector('#btnArchiveSelectedAccountsV2')?.textContent).toBe('恢复选中');
});
afterEach(()=>{wrapper?.unmount();document.body.replaceChildren();vi.unstubAllGlobals();});
it('list and legacy facade share one Vue drawer while page changes preserve its frozen identity',async()=>{
  const {api}=readApi();
  const roxyProfile=vi.fn(async()=>({ok:true as const,profile_id:'p1',window_name:'窗口'}));
  const oldOpen=vi.fn(),notify=vi.fn(),lock=vi.fn();
  wrapper=mount(AccountsPageShell,{attachTo:document.body,props:{adapter:realAdapter(),api,presentation,
    callbacks:{invoke:vi.fn(),openDetail:oldOpen,notify},detailApi:{roxyProfile},
    detailPresentation:{renderBody:row=>`<p>${row.email}</p>`,sourceLabel:()=>''},syncModalScrollLock:lock,
    initialCapabilities:{},c2aDependencies:c2aDependencies(),emailChangeDependencies:emailChangeDependencies(),inspectionDependencies:inspectionDependencies(),actions:{isSupported:()=>false,isPending:()=>false,invoke:vi.fn(),setVisible:vi.fn(),dispose:vi.fn()}}});
  const vm=wrapper.vm as unknown as InstanceType<typeof AccountsPageShell>;
  vm.setVisible(true);await flushPromises();
  const trigger=wrapper.get<HTMLButtonElement>('[data-account-detail-id="1"]');
  await trigger.trigger('click');await flushPromises();
  expect(document.querySelectorAll('#accountDetailDrawer')).toHaveLength(1);
  expect(document.getElementById('accountDetailTitle')?.textContent).toBe('account-1@example.test');
  expect(oldOpen).not.toHaveBeenCalled();expect(roxyProfile).toHaveBeenCalledTimes(1);
  vm.setPage(2);await flushPromises();
  expect(wrapper.text()).toContain('account-2@example.test');
  expect(document.getElementById('accountDetailTitle')?.textContent).toBe('account-1@example.test');
  vm.closeDetail(false);await flushPromises();
  expect(document.getElementById('accountDetailDrawer')?.classList.contains('hidden')).toBe(true);
  vm.openDetail('2');await flushPromises();
  expect(document.getElementById('accountDetailTitle')?.textContent).toBe('account-2@example.test');
  vm.closeDetail(false);await flushPromises();
  const currentTrigger=wrapper.get<HTMLButtonElement>('[data-account-detail-id="2"]');
  await currentTrigger.trigger('click');await flushPromises();
  expect(document.activeElement?.id).toBe('btnCloseAccountDetail');
  Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));await flushPromises();
  expect(document.activeElement).toBe(currentTrigger.element);
  Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));await flushPromises();
  vm.openDetail('2');await flushPromises();
  vm.setVisible(false);await flushPromises();
  expect(document.getElementById('accountDetailDrawer')?.classList.contains('hidden')).toBe(true);
  expect(notify).not.toHaveBeenCalled();expect(lock).toHaveBeenCalled();
});
it('routes supported actions once and keeps inspection dialogs on the same page owner',async()=>{
  const {api}=readApi(),legacy=vi.fn(),invoke=vi.fn(),inspection=inspectionDependencies();
  wrapper=mount(AccountsPageShell,{attachTo:document.body,props:{adapter:realAdapter(),api,presentation,
    callbacks:{invoke:legacy,openDetail:vi.fn()},detailApi:{roxyProfile:vi.fn()},detailPresentation:{renderBody:()=>'',sourceLabel:()=>''},syncModalScrollLock:vi.fn(),
    initialCapabilities:{},c2aDependencies:c2aDependencies(),emailChangeDependencies:emailChangeDependencies(),inspectionDependencies:inspection,actions:{isSupported:action=>action==='copySelectedAccountEmails',isPending:()=>true,invoke,setVisible:vi.fn(),dispose:vi.fn()}}});
  const vm=wrapper.vm as unknown as InstanceType<typeof AccountsPageShell>;
  vm.setVisible(true);await flushPromises();
  const context=vm.getActionContext();
  await vm.invokeAction('copySelectedAccountEmails',context);
  expect(invoke).toHaveBeenCalledOnce();expect(legacy).not.toHaveBeenCalled();
  expect(vm.isActionPending('copySelectedAccountEmails')).toBe(true);
  const trigger=document.createElement('button');document.body.append(trigger);trigger.focus();
  vm.openInspectionStart({...context,archived:'only'},trigger);await flushPromises();
  expect(document.querySelectorAll('#accountInspectionStart')).toHaveLength(1);
  expect(document.querySelector<HTMLDialogElement>('#accountInspectionStart')?.open).toBe(true);
  expect(document.querySelector('#accountInspectionScope')?.textContent).toContain('已归档');
  vm.closeInspection('start');await flushPromises();expect(document.activeElement).toBe(trigger);
  vm.openInspectionHistory(trigger);await flushPromises();
  expect(inspection.request).toHaveBeenCalledWith('/api/accounts/inspections?page=1',expect.objectContaining({signal:expect.any(AbortSignal)}));
  vm.closeInspection();await flushPromises();expect(document.querySelector<HTMLDialogElement>('#accountInspectionHistory')?.open).toBe(false);
});
it('账号页可查询未确认的受理回执并打开原执行记录', async () => {
  sessionStorage.clear();
  const {api}=readApi();
  const request=vi.fn<(path:string,options?:RequestInit)=>Promise<unknown>>()
    .mockRejectedValueOnce(new TypeError('网络中断'))
    .mockResolvedValueOnce({ok:true,found:true,items:[{task_id:'71',run_id:'72'}]});
  const openReceiptTask=vi.fn();
  const queued:AccountQueuedDependencies={
    refresh:vi.fn(),pollStatuses:vi.fn(),refreshSummary:vi.fn(),reloadTasks:vi.fn(),
    configuredLiveCheckDriver:()=>null,operationWorkers:()=>1,readConfig:vi.fn(),fallbackConfig:()=>[],
    openReceiptTask,openAccountTaskLog:vi.fn(),openLiveLog:vi.fn(),getRowSnapshot:()=>undefined,
    isOwnerActive:()=>true,clearScheduled:vi.fn(),
  };
  const actions=createAccountActions({request,notify:vi.fn(),confirm:()=>true,clipboard:vi.fn(),
    downloadBlob:vi.fn(),downloadUrl:vi.fn(),now:()=>new Date(),schedule:()=>1,reloadCodex:vi.fn(),queued});
  wrapper=mount(AccountsPageShell,{attachTo:document.body,props:{adapter:realAdapter(),api,presentation,
    callbacks:{invoke:vi.fn(),openDetail:vi.fn()},detailApi:{roxyProfile:vi.fn()},
    detailPresentation:{renderBody:()=>'',sourceLabel:()=>''},syncModalScrollLock:vi.fn(),
    initialCapabilities:{},
    c2aDependencies:c2aDependencies(),emailChangeDependencies:emailChangeDependencies(),inspectionDependencies:inspectionDependencies(),actions}});
  const vm=wrapper.vm as unknown as InstanceType<typeof AccountsPageShell>;
  vm.setVisible(true);
  await flushPromises();
  await wrapper.get<HTMLInputElement>('.account-row-check').setValue(true);
  await wrapper.get('#btnCheckSelectedLiveV2').trigger('click');
  await flushPromises();
  const box=wrapper.get('.ac-operation-receipts');
  expect(box.text()).toContain('受理结果未确认');
  expect(wrapper.get<HTMLButtonElement>('#btnCheckSelectedLiveV2').element.disabled).toBe(false);
  expect(request).toHaveBeenCalledOnce();
  await box.get('button').trigger('click');
  await flushPromises();
  expect(request.mock.calls.map(([path,opts])=>[path,opts?.method])).toEqual([
    ['/api/accounts/check-live-bulk','POST'],['/api/accounts/operation-receipt','GET'],
  ]);
  expect(box.text()).toContain('当前查到 1 条任务回执');
  await box.findAll('button').find(button=>button.text().includes('任务 #71'))!.trigger('click');
  expect(openReceiptTask).toHaveBeenCalledWith(71,72);
  await box.findAll('button').find(button=>button.text()==='移除此提示')!.trigger('click');
  expect(wrapper.find('.ac-operation-receipts').exists()).toBe(false);
  sessionStorage.clear();
});
