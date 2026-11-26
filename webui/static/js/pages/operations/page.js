// 迁移接缝：旧页面只通过显式方法访问任务模块，不共享筛选 DOM、分页或轮询状态。
window.TaskCenter = (() => {
  let instance = null;
  let loading = null;
  let visible = false;
  let opening = false;
  let detailGeneration = 0;

  function operationId(value, optional = false) {
    if (optional && (value == null || value === '' || value === 0 || value === '0')) return null;
    if (typeof value === 'number') {
      if (Number.isSafeInteger(value) && value > 0) return value;
      throw new Error('任务或运行标识无效');
    }
    if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value)) throw new Error('任务或运行标识无效');
    const numeric = Number(value);
    return Number.isSafeInteger(numeric) ? numeric : value;
  }

  function report(error) {
    showToast(`任务中心加载失败：${error.message || error}`);
  }

  async function ensure() {
    if (instance) return instance;
    if (loading) return loading;
    const root = document.getElementById('task-center-root');
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
      instance = module.mountTaskCenter(root, {
        onBatch: (batchId, roundId) => window.BulkTasks?.navigate('detail', {batch_id: batchId, round_id: roundId || ''}),
        onChanged: () => { if (ACTIVE_TAB === 'accounts') loadAccounts(); },
      });
      return instance;
    })().catch(error => {
      loading = null;
      root.replaceChildren();
      const message = document.createElement('p');
      message.setAttribute('role', 'alert');
      message.textContent = `任务中心加载失败：${error.message}`;
      const retry = document.createElement('button');
      retry.className = 'jobs-tb-btn';
      retry.textContent = '重新加载';
      retry.addEventListener('click', () => window.TaskCenter.setVisible(visible));
      root.append(message, retry);
      throw error;
    });
    return loading;
  }

  return {
    async open(options = {}) {
      const generation = ++detailGeneration;
      try {
        const payload = {
          ...options,
          ...(options.taskId != null ? {taskId: operationId(options.taskId)} : {}),
          ...(options.runId != null ? {runId: operationId(options.runId, true)} : {}),
        };
        const api = await ensure();
        if (generation !== detailGeneration) return;
        // 切页激活期间暂缓触发无筛选列表刷新，待目标筛选与详情参数应用后再统一激活可见读取。
        opening = true;
        try {
          activateTab('tasks');
        } finally {
          opening = false;
        }
        await api.open(payload);
        if (visible) api.setVisible(true);
      } catch (error) { report(error); }
    },
    async openDetail(taskId, runId = null, stepId = null) {
      const generation = ++detailGeneration;
      try {
        const api = await ensure();
        if (generation === detailGeneration) await api.open({taskId: operationId(taskId), runId: operationId(runId, true), stepId});
      } catch (error) { report(error); }
    },
    async refresh({metadata = false} = {}) {
      if (!instance && !visible) return;
      try { await (await ensure()).refresh({metadata}); }
      catch (error) { report(error); }
    },
    closeDetail() {
      detailGeneration += 1;
      instance?.closeDetail();
    },
    setVisible(value) {
      visible = Boolean(value);
      if (!visible) {
        instance?.setVisible(false);
        return;
      }
      if (opening) return;
      void ensure().then(api => {
        if (!opening) api.setVisible(visible);
      }).catch(report);
    },
  };
})();

function loadAccountTasks({forceMetadata = false} = {}) {
  return window.TaskCenter.refresh({metadata: forceMetadata});
}
function openAccountTaskLog(taskId, runId = null, stepId = null) {
  return window.TaskCenter.openDetail(taskId, runId, stepId);
}
