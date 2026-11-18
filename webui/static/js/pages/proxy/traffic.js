// Shell navigation supplies the view and visibility; Vue owns all reads and polling.
window.ProxyTraffic = window.createPageBridge({
  rootId: 'proxy-page-root',
  tabId: 'tab-proxy-traffic',
  mount: 'mountProxyTraffic',
  initialView: 'pool',
  notify: message => showToast(`代理与流量加载失败：${message}`),
  dependencies: () => ({facetLabel, notify: message => showToast(message)}),
});
