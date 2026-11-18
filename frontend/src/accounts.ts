import {createApp} from 'vue';
import AccountsPageShell from './features/accounts/AccountsPageShell.vue';
import {createAccountsApi} from './api/accounts';
import {createAccountDetailApi} from './api/accountDetail';
import type {AccountViewRow} from './features/accounts/useAccounts';
import {createAccountActions,type AccountActionDependencies} from './features/accounts/actions';
import {createAccountDownloads} from './features/accounts/browserDownloads';
import {request} from './api/client';
import type {AccountInspectionDependencies} from './features/accounts/useAccountInspection';
import type {AccountEmailChangeDependencies} from './features/accounts/useAccountEmailChange';
import type {C2aReimportDependencies} from './features/accounts/useC2aReimport';
import type {AccountToolbarCapabilities} from './features/accounts/accountToolbar';
import type {AccountQuickActionRuntime} from './features/accounts/useAccountQuickActions';
import {createAccountQueryAdapter, type AccountQueryAdapter} from './features/accounts/queryAdapter';
import {createAccountPresentation, type AccountsCallbacks, type LegacyAccountPresenters} from './features/accounts/presentation';

export function mountAccounts(element: HTMLElement, options: {
  query: AccountQueryAdapter;
  presentation: LegacyAccountPresenters;
  callbacks: AccountsCallbacks;
  detailPresentation: {renderBody(row: AccountViewRow): string; sourceLabel(value: unknown): string};
  syncModalScrollLock: () => void;
  actionDependencies: Pick<AccountActionDependencies,'notify'|'confirm'|'clipboard'|'reloadCodex'|'canInvoke'|'beginBusy'|'queued'|'setup'|'local'>;
  inspectionDependencies: Omit<AccountInspectionDependencies,'request'>;
  emailChangeDependencies: Omit<AccountEmailChangeDependencies,'request'>;
  c2aDependencies: Omit<C2aReimportDependencies,'request'>;
  capabilities:AccountToolbarCapabilities;
}) {
  const adapter = createAccountQueryAdapter(options.query);
  const downloads=createAccountDownloads({document,origin:window.location.origin,urls:URL,schedule:(callback,delay)=>setTimeout(callback,delay)});
  const actions=createAccountActions({...options.actionDependencies,request,...downloads,now:()=>new Date(),schedule:(callback,delay)=>setTimeout(callback,delay)});
  const toolbarRuntime:AccountQuickActionRuntime={storage:{getItem:key=>window.localStorage.getItem(key),setItem:(key,value)=>window.localStorage.setItem(key,value)},
    requestFrame:callback=>requestAnimationFrame(callback),cancelFrame:handle=>cancelAnimationFrame(handle),
    addStorageListener:listener=>{window.addEventListener('storage',listener);return()=>window.removeEventListener('storage',listener);}};
  return createApp(AccountsPageShell, {adapter, api: createAccountsApi(adapter),
    presentation: createAccountPresentation(options.presentation), callbacks: options.callbacks,
    detailApi: createAccountDetailApi(), detailPresentation: options.detailPresentation,
    syncModalScrollLock: options.syncModalScrollLock,
    actions,
    inspectionDependencies:{...options.inspectionDependencies,request},
    emailChangeDependencies:{...options.emailChangeDependencies,request},
    c2aDependencies:{...options.c2aDependencies,request},
    initialCapabilities:options.capabilities,
    toolbarRuntime,
  }).mount(element) as InstanceType<typeof AccountsPageShell>;
}
