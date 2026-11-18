// Compatibility entrypoints delegate inspection reads and dialogs to the Vue page owner.
function accountInspectionScope() { return SHOW_ARCHIVED_ACCOUNTS ? 'only' : '0'; }
function accountInspectionScopeLabel(scope) { return scope === 'only' ? '已归档账号' : scope === 'all' ? '全部账号' : '未归档账号'; }
function openAccountInspectionStart(context = null, trigger = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.openInspectionStart(context, trigger || document.activeElement);
}
function openAccountInspectionHistory() { return window.AccountsPage?.openInspectionHistory(document.activeElement); }
function openAccountInspectionFailures(id) { return window.AccountsPage?.openInspectionFailures(id, document.activeElement); }
function closeAccountInspectionDialog(id) {
  const kind = {accountInspectionStart:'start',accountInspectionHistory:'history',accountInspectionFailures:'failures'}[id];
  if (kind) window.AccountsPage?.closeInspection(kind);
}
function refreshAccountInspectionHistory() { return window.AccountsPage?.refreshInspectionHistory(); }
function refreshAccountInspectionFailures() { return window.AccountsPage?.refreshInspectionFailures(); }
function changeAccountInspectionPage(delta) { return window.AccountsPage?.changeInspectionPage(delta); }
function changeAccountInspectionFailuresPage(delta) { return window.AccountsPage?.changeInspectionFailuresPage(delta); }
function stopAccountInspection(id) { return window.AccountsPage?.stopInspection(id); }
function deleteDeactivatedAccounts(context = null) {
  context = captureAccountActionContext(context);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.invokeAction('deleteDeactivatedAccounts', context);
}
