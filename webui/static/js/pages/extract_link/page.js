// The workbench owns list, selection, dialogs, writes and all receipt state.
window.ExtractWorkbenchPage = (() => {
  const bridge = window.createPageBridge({
    rootId:'extractWorkbenchRoot', tabId:'tab-extract-workbench', mount:'mountExtractWorkbench',
    notify:message=>showToast(`提链工作台加载失败：${message}`),
    dependencies:()=>({notify:message=>showToast(message), confirm:message=>window.confirm(message),
      copyText:async value=>{if(!await copyText(value,false))throw new Error('复制失败');},
      accountSources:{...LIST_FACET_LABELS.source,manual:'手动配置邮箱'},
      onReady:()=>markViewReady('extract-workbench')}),
  });
  const explicit = (method,...args) => bridge.invoke(method,args,{hidden:true}).catch(error=>showToast(error.message));
  return {
    setVisible:bridge.setVisible, destroy:bridge.destroy, closeDialogs:bridge.closeDialogs,
    closeDrawer:bridge.closeDialogs, load:options=>bridge.read('load',options),
    openCreate:()=>bridge.read('openCreate'), switchBatch:id=>bridge.read('switchBatch',id),
    openDrawer:id=>explicit('openDetail',id), showPaymentEntry:id=>explicit('showPaymentEntry',id),
    copyPayment:key=>explicit('copyPayment',key), showLink:(id,kind)=>explicit('showLink',id,kind),
    copy:(id,kind)=>explicit('copy',id,kind), taskAction:(id,action)=>bridge.invoke('taskAction',[id,action],{hidden:true}),
    bulkAction:action=>bridge.invoke('bulkAction',[action]), cancelBatch:()=>bridge.invoke('cancelBatch'),
    exportRows:filtered=>bridge.read('exportRows',filtered),
  };
})();
window.loadExtractWorkbench = options => window.ExtractWorkbenchPage.load(options);
window.extractWorkbenchOpenCreate = () => window.ExtractWorkbenchPage.openCreate();
window.extractWorkbenchSwitchBatch = id => window.ExtractWorkbenchPage.switchBatch(id);
window.extractWorkbenchOpenDrawer = id => window.ExtractWorkbenchPage.openDrawer(id);
window.extractWorkbenchCloseDrawer = () => window.ExtractWorkbenchPage.closeDialogs();
window.extractWorkbenchShowPaymentEntry = id => window.ExtractWorkbenchPage.showPaymentEntry(id);
window.extractWorkbenchShowLink = (id,kind) => window.ExtractWorkbenchPage.showLink(id,kind);
window.extractWorkbenchTaskAction = (id,action) => window.ExtractWorkbenchPage.taskAction(id,action);
window.extractWorkbenchCopy = (id,kind) => window.ExtractWorkbenchPage.copy(id,kind);
