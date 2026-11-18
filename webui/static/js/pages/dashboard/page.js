// Dashboard data, layout and polling belong to the Vue owner.
window.DashboardPage = window.createPageBridge({
  rootId:'dashboard-page-root', tabId:'tab-overview', mount:'mountDashboard',
  notify: message => showToast(`总览加载失败：${message}`),
  dependencies: () => ({
    notify: message => showToast(message), onNavigate: tab => activateTab(tab),
    onConfig: group => openConfigGroup(group), onReady: () => markViewReady('overview'),
    onCapabilities: value => {CAPABILITIES = value; window.AccountsPage?.setCapabilities?.(value.features || {});},
  }),
});
window.loadDashboard = () => window.DashboardPage.read('load');
window.openOverviewCustomizer = () => window.DashboardPage.read('openCustomizer');
window.closeOverviewCustomizer = () => window.DashboardPage.closeDialogs();
window.resetOverviewLayout = () => window.DashboardPage.read('resetLayout');
window.loadSummary = () => window.RegistrationPage?.loadSummary();
window.renderRegistrationEmailSupply = value => window.RegistrationPage?.renderEmailSupply(value);
