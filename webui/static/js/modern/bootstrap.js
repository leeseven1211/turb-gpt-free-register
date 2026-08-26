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
activateTab(localStorage.getItem('gpt_console_active_tab') || 'overview', false);
jobsTimer = setInterval(() => {
  if (!document.hidden && !$('#tab-register').classList.contains('hidden')) refreshJobs();
}, 5000);
setInterval(() => { if (!document.hidden) loadSummary(); }, 10000);
setInterval(() => {
  if (!document.hidden && !$('#tab-overview').classList.contains('hidden')) loadDashboard();
}, 15000);
setInterval(() => {
  if (!document.hidden && !$('#tab-accounts').classList.contains('hidden') && $('#tab-accounts')?.dataset.moduleView !== 'tasks') pollAccountPlanStatuses();
}, 5000);
setInterval(() => {
  if (!document.hidden && !$('#tab-accounts').classList.contains('hidden') && $('#tab-accounts')?.dataset.moduleView === 'tasks') loadAccountTasks();
}, 5000);
