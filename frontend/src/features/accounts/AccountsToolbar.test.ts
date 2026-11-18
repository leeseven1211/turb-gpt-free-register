import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,expect,it,vi} from 'vitest';
import AccountsToolbar from './AccountsToolbar.vue';
import {ACCOUNT_TOOLBAR_BUTTONS} from './accountToolbar';
import {ACCOUNT_ACTION_USAGE_KEY,ACCOUNT_QUICK_ACTION_DEFAULTS,type AccountQuickActionRuntime} from './useAccountQuickActions';
import {realAdapter,deferred} from './uiTestSupport';
import type {AccountActionContext} from './useAccounts';
let wrapper:ReturnType<typeof mount>|undefined;
afterEach(()=>{wrapper?.unmount();wrapper=undefined;document.body.replaceChildren();});
function fixture(selectedCount=2){
 let saved:string|null=null,storageListener:((event:{key:string|null})=>void)|undefined;const frames=new Map<number,()=>void>();let sequence=0;
 const runtime:AccountQuickActionRuntime={storage:{getItem:()=>saved,setItem:(_key,value)=>{saved=value;}},requestFrame:fn=>{frames.set(++sequence,fn);return sequence;},cancelFrame:handle=>{frames.delete(handle);},addStorageListener:fn=>{storageListener=fn;return()=>{storageListener=undefined;};}};
 const context:AccountActionContext=Object.freeze({accountIds:Object.freeze(['7','8']),expectedEmails:Object.freeze({'7':'seven@test','8':'eight@test'}),querySnapshot:realAdapter().normalize(),archived:'0',rowHints:[]});
 const invoke=vi.fn(),notify=vi.fn(),getContext=vi.fn(()=>context);
 wrapper=mount(AccountsToolbar,{attachTo:document.body,props:{state:{selectedCount,archived:false},capabilities:{},getContext,invoke,runtime,notify}});
 const flush=async()=>{const work=[...frames.values()];frames.clear();work.forEach(fn=>fn());await flushPromises();};
 return{invoke,notify,getContext,context,flush,setSaved:(value:string)=>{saved=value;},external:()=>storageListener?.({key:ACCOUNT_ACTION_USAGE_KEY}),counts:()=>JSON.parse(saved||'{}')};
}
const quick=()=>Array.from(document.querySelectorAll<HTMLButtonElement>('#accountsQuickActionsV2 button')).map(button=>button.id);
const button=(id:string)=>document.getElementById(id) as HTMLButtonElement;
it('preserves all 34 existing controls, sections, titles and default top-five order with one node per id',async()=>{
 const f=fixture();await f.flush();
 expect(document.querySelectorAll('#accountsToolbarV2 button')).toHaveLength(34);expect(quick()).toEqual(ACCOUNT_QUICK_ACTION_DEFAULTS);
 expect(Array.from(document.querySelectorAll('.toolbar-overflow-section-title')).map(node=>node.textContent)).toEqual(['操作','批次与巡检','复制与导出','资产管理']);
 expect(ACCOUNT_TOOLBAR_BUTTONS.map(item=>item.label)).toEqual(['查活','查套餐','刷新 AT','批量同步到 C2A','批量换绑邮箱','查封号邮件','补密码','补 2FA','修改密码','修改 2FA','补全账号','重跑注册','补 Codex','提链','按当前筛选创建批次','用已选账号创建批次','一键巡检','巡检历史','复制 Token','复制行','复制提炼地址','复制邮箱','复制密码','复制 2FA','下载 TXT','下载 Session','标记邮箱失效','解除邮箱失效','下载 CPA','上传 sub2','停止 Codex','归档选中','删除','删除已废']);
 for(const item of ACCOUNT_TOOLBAR_BUTTONS){expect(document.querySelectorAll(`#${item.id}`)).toHaveLength(1);expect(button(item.id).textContent).toBe(item.label);expect(button(item.id).title).toBe(item.title||'');expect(button(item.id).getAttribute('onclick')).toBeNull();}
 expect(document.querySelector('#accountsSelectedHintV2')?.textContent).toBe('已选 2 个账号');
});
it('selection, pending and feature gates suppress invocation and usage while page actions remain available',async()=>{
 const f=fixture(0);await f.flush();button('btnCopySelectedEmailsV2').click();expect(f.invoke).not.toHaveBeenCalled();
 for(const id of ['btnBulkFromAccountFilters','btnBulkFromSelectedAccounts','btnAccountInspection','btnAccountInspectionHistory','btnDeleteDeactivatedAccounts'])expect(button(id).disabled).toBe(false);
 await wrapper!.setProps({state:{selectedCount:2,archived:true,pending:{downloadSelectedAccountSessions:true}},capabilities:{live_check:{enabled:false,reason:'无驱动'}}});
 expect(button('btnArchiveSelectedAccountsV2').textContent).toBe('恢复选中');expect(button('btnArchiveSelectedAccountsV2').title).toBe('把选中的归档账号恢复到默认账号列表');
 expect(button('btnDownloadSelectedSessionsV2').disabled).toBe(true);expect(button('btnCheckSelectedLiveV2').dataset.feature).toBe('live_check');expect(button('btnCheckSelectedLiveV2').getAttribute('aria-disabled')).toBe('true');expect(button('btnCheckSelectedLiveV2').title).toBe('不可用：无驱动');
 button('btnCheckSelectedLiveV2').click();button('btnDownloadSelectedSessionsV2').click();expect(f.invoke).not.toHaveBeenCalled();expect(f.counts()).toEqual({});
 await wrapper!.setProps({capabilities:{live_check:{enabled:true}}});expect(button('btnCheckSelectedLiveV2').title).toMatch(/只在线验证现有 Token/);
});
it('passes the captured context and trigger once and keeps a pending click disabled through unrelated state updates',async()=>{
 const f=fixture();await f.flush();const pending=deferred<void>();f.invoke.mockReturnValue(pending.promise);const target=button('btnCopySelectedEmailsV2');target.click();await flushPromises();target.click();
 expect(f.invoke).toHaveBeenCalledTimes(1);expect(f.invoke).toHaveBeenCalledWith('copySelectedAccountEmails',f.context,target);expect(f.getContext).toHaveBeenCalledTimes(1);expect(f.counts().btnCopySelectedEmailsV2).toBe(1);
 await wrapper!.setProps({state:{selectedCount:3,archived:false}});expect(target.disabled).toBe(true);pending.resolve();await flushPromises();expect(target.disabled).toBe(false);
});
it('keeps the exact button and focus stable until focus, menu and modal dialog blockers clear',async()=>{
 const f=fixture();await f.flush();const target=button('btnCopySelectedEmailsV2');const menu=document.getElementById('accountsMoreActionsV2') as HTMLDetailsElement;menu.open=true;target.focus();target.click();await f.flush();expect(quick()).toEqual(ACCOUNT_QUICK_ACTION_DEFAULTS);expect(document.activeElement).toBe(target);
 menu.open=false;menu.dispatchEvent(new Event('toggle'));await f.flush();expect(quick()).toEqual(ACCOUNT_QUICK_ACTION_DEFAULTS);
 const dialog=document.createElement('dialog');dialog.open=true;document.body.append(dialog);target.blur();await f.flush();expect(quick()).toEqual(ACCOUNT_QUICK_ACTION_DEFAULTS);
 dialog.open=false;dialog.dispatchEvent(new Event('close'));await f.flush();expect(quick()[0]).toBe(target.id);expect(button(target.id)).toBe(target);expect(document.querySelectorAll(`#${target.id}`)).toHaveLength(1);
 f.setSaved('{"btnDeleteDeactivatedAccounts":10}');f.external();await f.flush();expect(quick()[0]).toBe('btnDeleteDeactivatedAccounts');expect(button(target.id)).toBe(target);
});
it('records page-level action once, reports boundary errors, and removes all teleported nodes at unmount',async()=>{
 const f=fixture();await f.flush();f.invoke.mockRejectedValue(new Error('上下文已失效'));button('btnBulkFromAccountFilters').click();await flushPromises();expect(f.invoke).toHaveBeenCalledWith('bulk-from-account-filters',f.context,button('btnBulkFromAccountFilters'));expect(f.notify).toHaveBeenCalledWith('上下文已失效');expect(f.counts().btnBulkFromAccountFilters).toBe(1);
 wrapper!.unmount();wrapper=undefined;expect(document.querySelectorAll('#accountsToolbarV2 button')).toHaveLength(0);f.external();await f.flush();
});
