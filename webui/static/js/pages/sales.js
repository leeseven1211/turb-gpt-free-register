// 销售页只负责加载 Vue 模块和转发页面生命周期，列表状态由 Vue 组件维护。
window.SalesPage = (() => {
  let instance = null;
  let loading = null;
  let visible = false;
  const root = () => document.getElementById('sales-root');
  const report = error => showToast(`贩卖区加载失败：${error?.message || error}`);
  async function readExecutorId(element) {
    const configured = element.dataset.executorId || window.SALES_EXECUTOR_ID;
    if (configured) return String(configured);
    try {
      const response = await fetch('/api/ui-settings', {credentials: 'same-origin'});
      if (response.ok && (response.headers.get('content-type') || '').includes('application/json')) {
        const payload = await response.json();
        const value = payload?.sales_executor_id ?? payload?.settings?.sales_executor_id;
        if (value) return String(value);
      }
    } catch { /* 执行端未配置时由后端默认 local。 */ }
    return 'local';
  }

  async function ensure() {
    if (instance) return instance;
    if (loading) return loading;
    loading = (async () => {
      const element = root();
      if (!element) throw new Error('找不到贩卖区挂载位置');
      let style = document.getElementById('task-center-style');
      if (!style) {
        style = document.createElement('link');
        style.id = 'task-center-style';
        style.rel = 'stylesheet';
        style.href = element.dataset.styleUrl;
        document.head.append(style);
      }
      const module = await import(element.dataset.moduleUrl);
      const executorId = await readExecutorId(element);
      instance = module.mountSales(element, {
        notify: message => showToast(message),
        executorId,
        openTask: (taskId, runId) => window.TaskCenter?.open?.({taskId, runId}),
        initialVisible: false,
      });
      instance.setVisible(visible);
      return instance;
    })().catch(error => {
      loading = null;
      instance = null;
      report(error);
      throw error;
    });
    return loading;
  }

  return {
    async setVisible(value) {
      visible = Boolean(value);
      if (!visible && !instance) return;
      try {
        const page = await ensure();
        page.setVisible(visible);
      } catch { /* ensure 已报告错误。 */ }
    },
    async refresh() {
      try { return await (await ensure()).refresh(); } catch { return undefined; }
    },
    async addAccounts(sourceId, accountIds) {
      try {
        const page = await ensure();
        page.addAccounts(String(sourceId || 'local'), (accountIds || []).map(Number));
        if (!visible) {
          visible = true;
          page.setVisible(true);
        }
      } catch { /* ensure 已报告错误。 */ }
    },
    closeDialogs() { instance?.closeDialogs?.(); },
    isReady() { return instance !== null; },
  };
})();
