// Vue owns proxy snapshots, filters, details and polling. The host owns loading and navigation.
window.ProxyTraffic = (() => {
  let instance = null, loading = null, visible = false, deliveredVisible = false, view = 'pool';
  const isVisible = () => visible && !document.getElementById('tab-proxy-traffic')?.classList.contains('hidden');
  function sync() {
    if (!instance) return;
    instance.setView(view);
    const next = isVisible();
    if (next !== deliveredVisible) {deliveredVisible = next;instance.setVisible(next);}
  }
  function report(error) {if (isVisible()) showToast(`代理与流量加载失败：${error.message || error}`);}
  async function ensure() {
    if (instance) return instance;
    if (!loading) {
      const root = document.getElementById('proxy-page-root');
      loading = (async () => {
        if (!root) throw new Error('找不到代理与流量挂载位置');
        if (!document.getElementById('task-center-style')) {
          const style = document.createElement('link');style.id = 'task-center-style';style.rel = 'stylesheet';style.href = root.dataset.styleUrl;document.head.append(style);
        }
        const module = await import(root.dataset.moduleUrl);
        instance = module.mountProxyTraffic(root, {visible:false, view, facetLabel:(group,value) => facetLabel(group,value), notify:message => showToast(message), onReady:() => markViewReady('proxy-traffic')});
        deliveredVisible = false;sync();return instance;
      })().catch(error => {
        loading = null;
        if (instance) {instance.destroy();instance = null;}
        deliveredVisible = false;
        if (root) {
          root.replaceChildren();const message = document.createElement('p');message.setAttribute('role','alert');message.textContent = `代理与流量加载失败：${error.message || error}`;
          const retry = document.createElement('button');retry.type = 'button';retry.textContent = '重新加载';retry.addEventListener('click',() => void setVisible(visible));root.append(message,retry);
        }
        throw error;
      });
    }
    return loading;
  }
  async function setVisible(value) {
    visible = Boolean(value);sync();
    if (!isVisible()) return;
    try {await ensure();sync();} catch (error) {report(error);}
  }
  return {
    setVisible,
    setView(value) {view = value === 'records' ? 'records' : 'pool';instance?.setView(view);},
    closeDetail(options = {restoreFocus:false}) {instance?.closeDetail(options);},
    async load(recordView = null) {if (!isVisible()) return;try {const api = await ensure();if (isVisible()) await api.load(recordView);} catch (error) {report(error);}},
  };
})();
function loadProxyTraffic(view = null) {return window.ProxyTraffic.load(view);}
