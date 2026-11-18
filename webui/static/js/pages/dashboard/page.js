// 注册页及旧页面共用的汇总读取保持原接口。
function emailSupplyValue(supply, key) {
  const value = supply?.[key];
  return Number.isInteger(value) && value >= 0 ? value : supply?.status === 'error' ? '读取失败' : '未知';
}

function emailSupplyHint(supply) {
  const updated = supply?.statistics_updated_at;
  const freshness = updated ? `；统计于 ${new Date(updated).toLocaleTimeString()} 更新` : '';
  return `仅统计本地库存；用完后请手动导入邮箱。邮箱由 Email Butler 等邮箱服务准备${supply?.reason ? `；${supply.reason}` : ''}${freshness}`;
}

function renderRegistrationEmailSupply(supply) {
  const hint = emailSupplyHint(supply);
  for (const [selector, key] of [['#statOutlook', 'total'], ['#statAvailable', 'available'], ['#statUsed', 'used'], ['#statFailed', 'failed']]) {
    const node = $(selector);
    if (node) { node.textContent = emailSupplyValue(supply, key); node.title = hint; }
  }
  const scope = $('#registrationEmailSupplyHint');
  if (scope) scope.textContent = hint;
}

async function loadSummary() {
  if (summaryLoading) return;
  summaryLoading = true;
  try {
    const s = await apiCached('/api/summary', {}, 3000);
    $('#statAccounts').textContent = s.accounts;
    renderRegistrationEmailSupply(s.email_supply);
  } catch(e) { renderRegistrationEmailSupply({status: 'error', reason: '本地库存读取失败，请稍后重试'}); }
  finally { summaryLoading = false; }
}

function jobStatusLabel(status) {
  return ({pending:'排队',running:'运行中',success:'成功',failed:'失败',partial_success:'部分成功',stopped:'已停止',cancelled:'已取消'})[status] || status || '未知';
}


// Dashboard data, layout and polling belong to the Vue owner.
window.DashboardPage = window.createPageBridge({
  rootId:'dashboard-page-root', tabId:'tab-overview', mount:'mountDashboard',
  notify: message => showToast(`总览加载失败：${message}`),
  dependencies: () => ({
    notify: message => showToast(message), onNavigate: tab => activateTab(tab),
    onConfig: group => openConfigGroup(group), onReady: () => markViewReady('overview'),
    onCapabilities: value => {CAPABILITIES = value;},
  }),
});
window.loadDashboard = () => window.DashboardPage.read('load');
window.openOverviewCustomizer = () => window.DashboardPage.read('openCustomizer');
window.closeOverviewCustomizer = () => window.DashboardPage.closeDialogs();
window.resetOverviewLayout = () => window.DashboardPage.read('resetLayout');
