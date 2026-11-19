// 迁移接缝：旧页面只通过显式方法访问任务模块，不共享筛选 DOM、分页或轮询状态。
window.TaskCenter = (() => {
  let instance = null;
  let loading = null;
  let visible = false;
  let detailGeneration = 0;
  let receiptNavigationGeneration = 0;
  const pendingReceipts = [];
  let drainingReceipts = false;

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

  function drainPendingReceipts(api) {
    if (drainingReceipts) return;
    drainingReceipts = true;
    try {
      while (pendingReceipts.length) {
        const receipt = pendingReceipts[0];
        api.track(receipt.references, receipt.label, {
          navigate: receipt.generation === receiptNavigationGeneration ? receipt.navigate : false,
        });
        // track 是同步接收接口；只有正常返回才移交所有权。
        if (pendingReceipts[0] === receipt) pendingReceipts.shift();
      }
    } catch (error) {
      // 已挂载组件仍可使用；保留失败批次，下一次入口调用时补交。
      showToast(`任务回执显示失败：${error.message || error}`);
    } finally {
      drainingReceipts = false;
    }
  }

  async function ensure() {
    if (instance) {
      drainPendingReceipts(instance);
      return instance;
    }
    if (loading) {
      const api = await loading;
      drainPendingReceipts(api);
      return api;
    }
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
        onNavigate: () => activateTab('tasks'),
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
    const api = await loading;
    // 交付异常不能进入上面的模块加载 catch，避免清除已挂载的组件。
    drainPendingReceipts(api);
    return api;
  }

  return {
    async open(options = {}) {
      const generation = ++detailGeneration;
      receiptNavigationGeneration += 1;
      try {
        const api = await ensure();
        if (generation !== detailGeneration) return;
        activateTab('tasks');
        await api.open({...options,
          ...(options.taskId != null ? {taskId: operationId(options.taskId)} : {}),
          ...(options.runId != null ? {runId: operationId(options.runId, true)} : {}),
        });
      } catch (error) { report(error); }
    },
    async openDetail(taskId, runId = null, stepId = null) {
      const generation = ++detailGeneration;
      receiptNavigationGeneration += 1;
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
    async track(references, label = '任务', options = {}) {
      try {
        // 只保留回执公开字段，不持有调用者数组或上传凭证内容。
        pendingReceipts.push({
          references: references.map(({accepted, task_id, run_id, status}) => ({accepted, task_id, run_id, status})),
          label: String(label), navigate: options.navigate, generation: receiptNavigationGeneration,
        });
        await ensure();
      }
      catch (error) { report(error); }
    },
    closeDetail() {
      detailGeneration += 1;
      receiptNavigationGeneration += 1;
      instance?.closeDetail();
    },
    setVisible(value) {
      visible = Boolean(value);
      if (!visible) {
        receiptNavigationGeneration += 1;
        instance?.setVisible(false);
        return;
      }
      void ensure().then(api => api.setVisible(visible)).catch(report);
    },
  };
})();

function loadAccountTasks({forceMetadata = false} = {}) {
  return window.TaskCenter.refresh({metadata: forceMetadata});
}
function openAccountTaskLog(taskId, runId = null, stepId = null) {
  return window.TaskCenter.openDetail(taskId, runId, stepId);
}
function trackAcceptedOperationsV2(references, label = '任务', options = {}) {
  return window.TaskCenter.track(references, label, options);
}
function showOperationReceiptsV2() {
  return window.TaskCenter.open({filters: {}});
}
