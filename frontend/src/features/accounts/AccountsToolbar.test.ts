import {flushPromises,mount} from '@vue/test-utils';
import {afterEach,expect,it,vi} from 'vitest';
import AccountsToolbar from './AccountsToolbar.vue';
import {ACCOUNT_TOOLBAR_BUTTONS,ACCOUNT_TOOLBAR_SECTIONS} from './accountToolbar';
import {ACCOUNT_QUICK_ACTION_DEFAULTS} from './useAccountQuickActions';
import {realAdapter,deferred} from './uiTestSupport';
import type {AccountActionContext} from './useAccounts';

let wrapper:ReturnType<typeof mount>|undefined;
afterEach(()=>{wrapper?.unmount();wrapper=undefined;document.body.replaceChildren();});

function fixture(selectedCount=2){
  const context:AccountActionContext=Object.freeze({
    accountIds:Object.freeze(['7','8']),
    expectedEmails:Object.freeze({'7':'seven@test','8':'eight@test'}),
    querySnapshot:realAdapter().normalize(),
    archived:'0',
    rowHints:[],
  });
  const invoke=vi.fn(),notify=vi.fn(),getContext=vi.fn(()=>context);
  wrapper=mount(AccountsToolbar,{attachTo:document.body,props:{
    state:{selectedCount,archived:false},capabilities:{},getContext,invoke,notify,
  }});
  return{invoke,notify,getContext,context,flush:()=>flushPromises()};
}
const quick=()=>Array.from(document.querySelectorAll<HTMLButtonElement>('#accountsQuickActionsV2 button')).map(button=>button.dataset.accountShortcut);
const shortcut=(id:string)=>document.querySelector<HTMLButtonElement>(`[data-account-shortcut="${id}"]`)!;
const button=(id:string)=>document.getElementById(id) as HTMLButtonElement;
const menuIds=()=>Array.from(document.querySelectorAll('.toolbar-overflow-section')).map(section=>Array.from(section.querySelectorAll('button')).map(button=>button.id));
const expectedActions=[
  ['btnCheckSelectedPlansV2','checkSelectedPlans',true,'plan_check'],['btnAccountInspectionHistory','openAccountInspectionHistory',false,undefined],['btnCheckSelectedLiveV2','checkSelectedLive',true,'live_check'],['btnCheckSelectedDeactivationMailV2','checkSelectedDeactivationMail',true,'deactivation_mail'],
  ['btnRefreshSelectedTokenV2','refreshSelectedToken',true,'token_refresh'],['btnRetrySelectedCodexV2','retrySelectedCodex',true,'codex_retry'],['btnRetrySelectedRegistrationV2','retryAccountRegistration',true,undefined],['btnAddPasswordSelectedAccountsV2','addPasswordSelectedAccounts',true,'password_setup'],['btnCompleteSelectedAccountsV2','completeSelectedAccounts',true,undefined],['btnAddTwofaSelectedAccountsV2','addTwofaSelectedAccounts',true,undefined],['btnEmailChangeSelectedV2','openBulkEmailChangeForSelectedAccounts',true,undefined],['btnChangePasswordSelectedAccountsV2','changePasswordSelectedAccounts',true,'password_setup'],['btnChangeTwofaSelectedAccountsV2','changeTwofaSelectedAccounts',true,'twofa_change'],['btnExtractSelectedLinksV2','extractSelectedLinks',true,'extract_link'],
  ['btnAccountInspection','openAccountInspectionStart',false,undefined],['btnBulkFromAccountFilters','bulk-from-account-filters',false,undefined],['btnBulkFromSelectedAccounts','bulk-from-selected-accounts',false,undefined],['btnStopSelectedCodexV2','stopSelectedCodex',true,undefined],
  ['btnReimportSelectedC2aV2','reimportSelectedC2a',true,'c2a_sync'],['btnUploadSelectedCodexSub2V2','uploadSelectedCodexSub2',true,'sub2_upload'],['btnDownloadSelectedCpaV2','downloadSelectedCpa',true,'cpa_download'],
  ['btnCopySelectedTokensV2','copySelectedAccountTokens',true,undefined],['btnCopySelectedLinesV2','copySelectedAccountLines',true,undefined],['btnArchiveSelectedAccountsV2','archiveSelectedAccounts',true,undefined],['btnDeleteSelectedAccountsV2','deleteSelectedAccounts',true,undefined],['btnDownloadSelectedTxtV2','downloadSelectedAccountTxt',true,undefined],['btnCopySelectedEmailsV2','copySelectedAccountEmails',true,undefined],['btnDeleteDeactivatedAccounts','deleteDeactivatedAccounts',false,undefined],['btnCopySelectedPasswordsV2','copySelectedAccountPasswords',true,undefined],['btnCopySelectedTotpsV2','copySelectedAccountTotpSecrets',true,undefined],['btnCopySelectedExtractLinksV2','copySelectedAccountExtractLinks',true,undefined],['btnDownloadSelectedSessionsV2','downloadSelectedAccountSessions',true,undefined],['btnMarkSelectedEmailInvalidV2','setAccountsEmailInvalid:1',true,undefined],['btnClearSelectedEmailInvalidV2','setAccountsEmailInvalid:0',true,undefined],
] as const;

it('菜单保留34个操作、五组固定顺序和快照组内顺序',async()=>{
  const f=fixture();await f.flush();
  expect(document.querySelectorAll('#accountsToolbarV2 button')).toHaveLength(39);
  expect(quick()).toEqual(ACCOUNT_QUICK_ACTION_DEFAULTS);
  expect(Array.from(document.querySelectorAll('.toolbar-overflow-section-title')).map(node=>node.textContent)).toEqual(ACCOUNT_TOOLBAR_SECTIONS);
  expect(menuIds()).toEqual(ACCOUNT_TOOLBAR_SECTIONS.map(section=>ACCOUNT_TOOLBAR_BUTTONS.filter(item=>item.section===section).map(item=>item.id)));
  expect(ACCOUNT_TOOLBAR_BUTTONS.map(({id,action,selection,feature})=>[id,action,selection,feature])).toEqual(expectedActions);
  expect(ACCOUNT_TOOLBAR_BUTTONS.map(item=>item.label)).toEqual([
    '查套餐','巡检历史','查活','封号邮件',
    '刷新AT','补Codex','重跑注册','补密码','补全账号','补2FA','换绑邮箱','修改密码','改2FA','提链',
    '启动巡检','筛选建批','已选建批','停Codex',
    '同步C2A','传sub2','导CPA',
    '复制AT','复制整行','归档选中','删除选中','下载TXT','复制邮箱','清理已废','复制密码','复制密钥','复制提链','下载会话','标记失效','解除失效',
  ]);
  for(const item of ACCOUNT_TOOLBAR_BUTTONS){
    expect(document.querySelectorAll(`#${item.id}`)).toHaveLength(1);
    expect(button(item.id).textContent).toBe(item.label);
    expect(button(item.id).title).toBe(item.title);
    expect(item.className==='jobs-tb-btn'||item.className==='jobs-tb-btn jobs-tb-btn--danger').toBe(true);
  }
});

it('快捷入口固定五项且点击不读取、写入或监听历史 localStorage',async()=>{
  const f=fixture();await f.flush();
  const getItem=vi.spyOn(Storage.prototype,'getItem');
  const setItem=vi.spyOn(Storage.prototype,'setItem');
  const addEventListener=vi.spyOn(window,'addEventListener');
  const target=shortcut('btnCopySelectedTokensV2');target.click();await flushPromises();
  expect(f.invoke).toHaveBeenCalledWith('copySelectedAccountTokens',f.context,target);
  expect(getItem).not.toHaveBeenCalledWith('turb_account_action_usage_v1');
  expect(setItem).not.toHaveBeenCalledWith('turb_account_action_usage_v1',expect.any(String));
  expect(addEventListener).not.toHaveBeenCalledWith('storage',expect.any(Function));
  expect(quick()).toEqual(ACCOUNT_QUICK_ACTION_DEFAULTS);
  getItem.mockRestore();setItem.mockRestore();addEventListener.mockRestore();
});

it('selection、pending、能力和归档恢复状态保持',async()=>{
  const f=fixture(0);await f.flush();
  button('btnCopySelectedEmailsV2').click();expect(f.invoke).not.toHaveBeenCalled();
  for(const id of ['btnBulkFromAccountFilters','btnBulkFromSelectedAccounts','btnAccountInspection','btnAccountInspectionHistory','btnDeleteDeactivatedAccounts'])expect(button(id).disabled).toBe(false);
  await wrapper!.setProps({state:{selectedCount:2,archived:true,pending:{downloadSelectedAccountSessions:true}},capabilities:{live_check:{enabled:false,reason:'无驱动'}}});
  expect(button('btnArchiveSelectedAccountsV2').textContent).toBe('恢复选中');
  expect(button('btnArchiveSelectedAccountsV2').title).toBe('把选中的归档账号恢复到默认账号列表');
  expect(button('btnDownloadSelectedSessionsV2').disabled).toBe(true);
  expect(button('btnCheckSelectedLiveV2').getAttribute('aria-disabled')).toBe('true');
  expect(button('btnCheckSelectedLiveV2').title).toBe('不可用：无驱动');
  button('btnCheckSelectedLiveV2').click();button('btnDownloadSelectedSessionsV2').click();
  expect(f.invoke).not.toHaveBeenCalled();
});

it('传递捕获的上下文和触发器，并在 pending 期间拒绝重复点击',async()=>{
  const f=fixture();await f.flush();
  const pending=deferred<void>();f.invoke.mockReturnValue(pending.promise);
  const target=button('btnCopySelectedEmailsV2');target.click();await flushPromises();target.click();
  expect(f.invoke).toHaveBeenCalledTimes(1);
  expect(f.invoke).toHaveBeenCalledWith('copySelectedAccountEmails',f.context,target);
  expect(f.getContext).toHaveBeenCalledTimes(1);
  await wrapper!.setProps({state:{selectedCount:3,archived:false}});
  expect(target.disabled).toBe(true);
  pending.resolve();await flushPromises();expect(target.disabled).toBe(false);
});

it('菜单和快捷入口共用同一操作的 pending 保护',async()=>{
  const f=fixture();await f.flush();
  const pending=deferred<void>();f.invoke.mockReturnValue(pending.promise);
  const id='btnCopySelectedTokensV2';shortcut(id).click();await flushPromises();
  expect(button(id).disabled).toBe(true);button(id).click();expect(f.invoke).toHaveBeenCalledTimes(1);
  pending.resolve();await flushPromises();button(id).click();await flushPromises();
  expect(f.invoke).toHaveBeenCalledTimes(2);
});

it('保留 page-level 错误边界、卸载清理和 Escape 收起焦点恢复',async()=>{
  const f=fixture();await f.flush();
  f.invoke.mockRejectedValue(new Error('上下文已失效'));button('btnBulkFromAccountFilters').click();await flushPromises();
  expect(f.notify).toHaveBeenCalledWith('上下文已失效');
  const menu=document.getElementById('accountsMoreActionsV2') as HTMLDetailsElement;
  menu.open=true;const target=button('btnAccountInspection');target.focus();
  target.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  expect(menu.open).toBe(false);expect(document.activeElement).toBe(menu.querySelector('summary'));
  wrapper!.unmount();wrapper=undefined;expect(document.querySelectorAll('#accountsToolbarV2 button')).toHaveLength(0);
});
