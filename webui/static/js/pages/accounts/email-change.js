// Compatibility entrypoints. The Vue owner owns sources, form state and opening generations.
function openEmailChangeModal(id, trigger = null, context = null) {
  context = captureAccountActionContext(context, [id]);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.openEmailChange(id, context, trigger);
}
function openBulkEmailChangeModal(ids, trigger = null, context = null) {
  context = captureAccountActionContext(context, ids);
  if (!context || !window.AccountsPage?.isReady()) { showToast('账号列表正在加载，请稍后重试'); return; }
  return window.AccountsPage.openBulkEmailChange(context, trigger);
}
function closeEmailChangeModal(options = {}) { return window.AccountsPage?.closeEmailChange(options); }
