// ---------- 全局复制委托 ----------
document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-copy-id]');
  if (!t) return;
  copyText(copyStore.get(t.dataset.copyId));
});

// ---------- 初始化 ----------
loadSummary();
loadCapabilities();
loadRegistrationEmailSources();
activateTab(localStorage.getItem('gpt_console_active_tab') || 'register', false);
initializeLegacyNavigationHistory(localStorage.getItem('gpt_console_active_tab') || 'register');
jobsTimer = setInterval(() => {
  if (!document.hidden && !$('#tab-register').classList.contains('hidden')) refreshJobs();
}, 5000);
setInterval(() => { if (!document.hidden) loadSummary(); }, 10000);
setInterval(() => {
  if (!document.hidden && !$('#tab-accounts').classList.contains('hidden')) pollAccountPlanStatuses();
}, 5000);
