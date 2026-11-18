// Statistics remain in their own menu and have an independent read lifecycle.
window.ExtractStatsPage = window.createPageBridge({
  rootId:'extractStatsRoot', tabId:'tab-extract-stats', mount:'mountExtractStats',
  notify:message=>showToast(`提链统计加载失败：${message}`),
  dependencies:()=>({notify:message=>showToast(message),onReady:()=>markViewReady('extract-stats')}),
});
window.loadExtractStats = () => window.ExtractStatsPage.read('load');
