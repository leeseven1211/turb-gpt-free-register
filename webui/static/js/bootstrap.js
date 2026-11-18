// ---------- 全局复制委托 ----------
document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-copy-id]');
  if (!t) return;
  copyText(copyStore.get(t.dataset.copyId));
});

// ---------- 初始化 ----------
initResizableTables();
loadRuntimeUiSettings();
loadSummary();
loadCapabilities();
restoreModuleViewState();
initializeNavigationHistory(localStorage.getItem('gpt_console_active_tab') || 'overview');
jobsTimer = setInterval(() => {
  if (!document.hidden && !$('#tab-register').classList.contains('hidden')) refreshJobs({automatic: true});
}, 5000);
setInterval(() => { if (!document.hidden) loadSummary(); }, 10000);
// 总览由 Vue owner 按页面可见性管理读取与轮询。
setInterval(() => {
  if (!document.hidden && !$('#tab-accounts').classList.contains('hidden') && $('#tab-accounts')?.dataset.moduleView !== 'tasks') pollAccountPlanStatuses();
}, 5000);
setInterval(() => {
  if (!document.hidden && !$('#tab-accounts').classList.contains('hidden') && $('#tab-accounts')?.dataset.moduleView === 'tasks') loadAccountTasks();
}, 5000);
