window.ExtractStats = window.createPageBridge({
  rootId: 'extractStatsRoot',
  tabId: 'tab-extract-stats',
  mount: 'mountExtractStats',
  notify: message => showToast(`提链统计加载失败：${message}`),
  dependencies: () => ({onReady: () => markViewReady('extract-stats')}),
});
window.loadExtractStats = () => window.ExtractStats.read('load');
