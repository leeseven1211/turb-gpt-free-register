// 凭证页仅通过此接缝连接现有导航壳；列表、筛选、选择由 Vue 模块独占。
window.CodexCredentials = (() => {
  let instance = null;
  let loading = null;
  let visible = false;
  let archived = false;

  function report(error) {
    showToast(`凭证列表加载失败：${error.message || error}`);
  }

  async function ensure() {
    if (instance) return instance;
    if (loading) return loading;
    const root = document.getElementById('codex-credentials-root');
    loading = (async () => {
      let style = document.getElementById('task-center-style');
      if (!style) {
        style = document.createElement('link');
        style.id = 'task-center-style';
        style.rel = 'stylesheet';
        style.href = root.dataset.styleUrl;
        document.head.append(style);
      }
      const module = await import(root.dataset.moduleUrl);
      instance = module.mountCodexCredentials(root, {
        notify: message => showToast(message),
        confirm: message => confirm(message),
        operationWorkers: () => getAccountOperationWorkers(),
        openTasks: type => window.TaskCenter.open({filters: type ? {target: '', type} : {}}),
      });
      // 模块加载期间的导航可能已改变；先设置范围，再允许首次读取。
      instance.setArchived(archived);
      instance.setVisible(visible);
      return instance;
    })().catch(error => {
      loading = null;
      instance = null;
      root.replaceChildren();
      const message = document.createElement('p');
      message.setAttribute('role', 'alert');
      message.textContent = `凭证列表加载失败：${error.message || error}`;
      const retry = document.createElement('button');
      retry.className = 'jobs-tb-btn';
      retry.textContent = '重新加载';
      retry.addEventListener('click', () => window.CodexCredentials.setVisible(visible));
      root.append(message, retry);
      throw error;
    });
    return loading;
  }

  return {
    async setVisible(value) {
      visible = Boolean(value);
      if (instance) { instance.setVisible(visible); return; }
      if (visible) {
        try { await ensure(); } catch (error) { report(error); }
      }
    },
    setArchived(value) {
      archived = Boolean(value);
      instance?.setArchived(archived);
    },
    async refresh() {
      try {
        if (instance) await instance.refresh();
        else if (visible) await ensure();
      } catch (error) { report(error); }
    },
  };
})();

// 账号页从 CPA 下载完成后仍使用此入口通知凭证列表刷新。
function loadCodex() {
  return window.CodexCredentials.refresh();
}
