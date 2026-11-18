// Only this bridge may enter the registration owner from the legacy shell.
window.RegistrationPage = (() => {
  let visible = false, metadataDirty = false;
  const bridge = window.createPageBridge({
    rootId:'registrationRoot', tabId:'tab-register', mount:'mountRegistration', initialView:'launch',
    notify: message => showToast(`注册页面加载失败：${message}`),
    dependencies: () => ({notify:message=>showToast(message), confirm:message=>window.confirm(message),
      openTask:(taskId,runId,stepId)=>window.TaskCenter?.openDetail(taskId,runId,stepId)}),
  });
  return {
    async setVisible(value) {
      visible = Boolean(value);
      await bridge.setVisible(visible);
      if (visible && metadataDirty) {metadataDirty = false; await bridge.read('ensureMeta',true);}
    },
    setView:bridge.setView, destroy:bridge.destroy,
    load:options=>bridge.read('load',options), loadSummary:()=>bridge.read('loadSummary'),
    metadata() {
      if (!visible) {metadataDirty = true; return Promise.resolve();}
      return bridge.read('ensureMeta',true);
    },
    renderEmailSupply:value=>bridge.read('renderEmailSupply',value),
    applySummary:value=>bridge.read('applySummary',value),
    openLog:(id,stepId)=>bridge.invoke('openLog',[id,stepId],{hidden:true}).catch(error=>showToast(error.message)),
    closeDetail:bridge.closeDialogs,
    create:payload=>bridge.invoke('create',[payload]),
    action:(path,payload)=>bridge.invoke('action',[path,payload]),
    runAction:(kind,job,ids)=>bridge.invoke('runAction',[kind,job,ids]),
    selectBatch:id=>bridge.read('setBatch',id),
  };
})();
window.loadRegistrationEmailSources = () => window.RegistrationPage.metadata();
window.refreshJobs = options => window.RegistrationPage.load(options);
window.openLog = (id,stepId) => window.RegistrationPage.openLog(id,stepId);
window.closeLogModal = () => window.RegistrationPage.closeDetail();
window.closeAccountTaskLogModal = () => window.TaskCenter?.closeDetail();
window.setJobProgressBatch = id => window.RegistrationPage.selectBatch(id);
window.retryJob = id => window.RegistrationPage.runAction('retry',{id});
window.retryBatchFailedJobs = () => window.RegistrationPage.runAction('retryBatch');
window.retrySelectedJobs = () => window.RegistrationPage.runAction('retryBulk');
