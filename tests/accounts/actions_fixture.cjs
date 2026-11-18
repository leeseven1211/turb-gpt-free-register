// Legacy wrapper suites execute the actual TS action owner; only browser/network capabilities are doubled.
const test = require('node:test');
const {createVueHarness} = require('../frontend_vue_loader.cjs');
const harness = createVueHarness();
test.after(() => harness.close());
const {createAccountActions} = harness.load('src/features/accounts/actions.ts');
const {createAccountDownloads} = harness.load('src/features/accounts/browserDownloads.ts');

function createActionsFixture(context, owner) {
  const downloads = createAccountDownloads({document: context.document, origin: 'http://localhost',
    urls: {createObjectURL: () => 'blob:fixture', revokeObjectURL() {}}, schedule: (callback, delay) => context.setTimeout(callback, delay)});
  const buttons = {downloadSelectedAccountSessions: 'btnDownloadSelectedSessionsV2', downloadSelectedCpa: 'btnDownloadSelectedCpaV2'};
  const actions = createAccountActions({
    request: (url, options) => context.api(url, options), notify: message => context.showToast(message),
    confirm: message => context.confirm(message), clipboard: (text, feedback) => context.copyText(text, feedback),
    ...downloads, now: () => new Date(2026, 10, 15), schedule: (callback, delay) => delay === 1500 ? queueMicrotask(callback) : context.setTimeout(callback, delay),
    reloadCodex: () => context.loadCodex?.(),
    setup:{refresh:snapshot=>context.accountActionRefresh(snapshot),pollStatuses:snapshot=>context.accountActionPollStatuses(snapshot),
      operationWorkers:()=>context.getAccountOperationWorkers?.()||3,openTasks:options=>context.window.TaskCenter.open(options),
      openLog:id=>context.openLog?.(id),trackAcceptedOperations:(items,label)=>context.trackAcceptedOperationsV2?.(items,label),
      showRegistrationResult:(result,snapshot,open)=>context.showAccountRegistrationRetryResult?.(result,snapshot,open)},
    local:{prompt:(message,initial)=>context.prompt(message,initial),refresh:snapshot=>context.accountActionRefresh(snapshot),refreshSummary:()=>context.loadSummary?.(),
      removeAcknowledgedSelection:(ids,snapshot)=>context.accountActionRemoveAcknowledged(ids,snapshot),clearSelection:snapshot=>context.accountActionClearSelection(snapshot),selectionChanged:snapshot=>context.accountActionSelectionUi(snapshot)},
    queued: {
      refresh: snapshot => context.accountActionRefresh(snapshot), pollStatuses: snapshot => context.accountActionPollStatuses(snapshot),
      refreshSummary: () => context.loadSummary?.(), reloadTasks: () => context.loadAccountTasks?.(),
      operationWorkers: () => context.getAccountOperationWorkers?.() || 3,
      configuredLiveCheckDriver: () => context.configuredLiveCheckDriver?.() || null,
      readConfig: () => context.apiCached?.('/api/config',{},30000) || Promise.resolve(context.CONFIG || []), fallbackConfig: () => context.CONFIG || [],
      openLiveLog: email => context.openLiveLog?.(email), openAccountTaskLog: (id,run) => context.openAccountTaskLog?.(id,run),
      getRowSnapshot: id => owner.getRowSnapshot?.(id), isOwnerActive: () => owner.isReady() && !context.document?.hidden,
      clearScheduled: handle => context.clearTimeout?.(handle),
      updateBusyLabel: (_descriptor,trigger,label) => {if(trigger)trigger.textContent=label;},
    },
    canInvoke: (_descriptor, trigger) => !trigger?.disabled,
    beginBusy: (descriptor, trigger, label) => {
      const button = trigger || (buttons[descriptor] ? context.document.getElementById(buttons[descriptor]) : null);
      const text = button?.textContent,managed=!!button?.closest?.('#accountsToolbarV2');
      if (button) {if(!managed)button.disabled = true; if (label) button.textContent = label;}
      return () => {
        if (button) {button.textContent = text; if(!managed)button.disabled = false;}
        context.updateAccountSelectionUi?.();
      };
    },
  });
  owner.invokeAction = (descriptor, snapshot, trigger) => actions.invoke(descriptor, snapshot, trigger);
  owner.isActionSupported = descriptor => actions.isSupported(descriptor);
  owner.isActionPending = (descriptor, snapshot) => actions.isPending(descriptor, snapshot || owner.getActionContext());
  return {actions, owner};
}
function legacySelectionSnapshot(context, options = {}) {
  const accountIds = Array.from(options.ids || context.ACCOUNT_SELECTED || []).map(String);
  const expectedEmails=Object.fromEntries(Array.from(context.ACCOUNT_SELECTED_EMAILS || []).map(([id,email])=>[String(id),email]));
  for(const row of context.ACCOUNTS || []){if(accountIds.includes(String(row.id)))expectedEmails[String(row.id)]=row.email;}
  return {accountIds, expectedEmails: Object.fromEntries(Object.entries(expectedEmails).filter(([id])=>accountIds.includes(id))),
    querySnapshot: {schema_version: 1, entity: 'account', archived: context.SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0', filters: {}},
    archived: context.SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0', rowHints: (context.ACCOUNTS || []).filter(row => accountIds.includes(String(row.id)))};
}
function installLegacyActionsFixture(context){
  context.document ||= {getElementById:id=>context.$?.('#'+id)||null};
  context.setTimeout ||= setTimeout;context.clearTimeout ||= clearTimeout;
  const owner={isReady:()=>true,getActionContext:options=>legacySelectionSnapshot(context,options),
    refresh:()=>context.loadAccounts?.(),pollStatuses:()=>context.pollAccountPlanStatuses?.(),
    getRowSnapshot:id=>(context.ACCOUNTS||[]).find(row=>String(row.id)===String(id))};
  context.window ||= {};context.window.AccountsPage=owner;
  return createActionsFixture(context,owner);
}
module.exports = {createActionsFixture, legacySelectionSnapshot,installLegacyActionsFixture, vueHarness: harness};
