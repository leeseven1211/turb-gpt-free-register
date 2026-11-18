// Navigation owns activation; the mounted page owns data, writes and polling.
window.createPageBridge = function createPageBridge(options) {
  let instance = null, loading = null, visible = false, deliveredVisible = false;
  let view = options.initialView, deliveredView, epoch = 0, disposed = false;
  const root = () => document.getElementById(options.rootId);
  const active = () => !disposed && visible && !document.getElementById(options.tabId)?.classList.contains('hidden');
  function sync() {
    if (!instance) return;
    if (view !== undefined && deliveredView !== view) {
      deliveredView = view; instance.setView?.(view);
    }
    const next = active();
    if (deliveredVisible !== next) {
      deliveredVisible = next; instance.setVisible(next);
    }
  }
  function report(error) {if (active()) options.notify?.(error?.message || String(error));}
  async function ensure() {
    if (instance) return instance;
    if (disposed) return null;
    if (!loading) {
      const node = root();
      loading = (async () => {
        if (!node) throw new Error('找不到页面挂载位置');
        const styleId = options.styleId || `${options.rootId}-style`;
        if (node.dataset.styleUrl && !document.getElementById(styleId)) {
          const style = document.createElement('link');
          style.id = styleId; style.rel = 'stylesheet'; style.href = node.dataset.styleUrl;
          document.head.append(style);
        }
        const module = await (options.loadModule ? options.loadModule(node.dataset.moduleUrl) : import(node.dataset.moduleUrl));
        if (disposed) return null;
        instance = module[options.mount](node, {...options.dependencies?.(), visible:false, ...(view === undefined ? {} : {view})});
        deliveredVisible = false; deliveredView = undefined; sync();
        return instance;
      })().catch(error => {
        loading = null;
        if (instance) {instance.destroy?.(); instance = null;}
        deliveredVisible = false;
        if (node && !disposed) {
          node.replaceChildren();
          const message = document.createElement('p');
          message.setAttribute('role','alert'); message.textContent = `页面加载失败：${error?.message || error}`;
          const retry = document.createElement('button');
          retry.type = 'button'; retry.textContent = '重新加载';
          retry.addEventListener('click', () => void setVisible(visible));
          node.append(message,retry);
        }
        throw error;
      });
    }
    return loading;
  }
  async function setVisible(value) {
    const next = Boolean(value);
    if (visible !== next) epoch++;
    visible = next; sync();
    if (!active()) return;
    try {await ensure(); sync();} catch (error) {report(error);}
  }
  async function invoke(method, args = [], settings = {}) {
    if (!settings.hidden && !active() || disposed) return;
    const generation = epoch;
    const page = await ensure();
    if (generation !== epoch || disposed || !settings.hidden && !active()) return;
    if (typeof page?.[method] !== 'function') throw new Error(`页面入口不可用：${method}`);
    return page[method](...args);
  }
  async function read(method, ...args) {
    try {return await invoke(method,args);} catch (error) {report(error);}
  }
  function closeDialogs() {epoch++; instance?.closeDialogs?.(); instance?.closeDetail?.(); instance?.closeCustomizer?.();}
  return {
    setVisible, read, invoke, closeDialogs,
    setView(value) {if (view !== value) epoch++; view = value; sync();},
    destroy() {epoch++; disposed = true; visible = false; instance?.destroy?.(); instance = null; loading = null;},
  };
};
