// ---------- 全局复制委托 ----------
document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-copy-id]');
  if (!t) return;
  copyText(copyStore.get(t.dataset.copyId));
});

// ---------- 初始化 ----------
initResizableTables();
loadRuntimeUiSettings();
loadCapabilities();
restoreModuleViewState();
initializeNavigationHistory(localStorage.getItem('gpt_console_active_tab') || 'overview');
// 总览、注册和提链页面由各自 Vue owner 按可见性管理读取与轮询。
// 账号列表与任务中心的轮询由各自模块生命周期管理。
