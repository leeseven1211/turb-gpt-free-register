// Vue owns email data, selection, drafts and original import receipts; the shell owns navigation.
window.EmailPage = (() => {
  let instance = null, loading = null, visible = false, deliveredVisible = false, view = 'overview', navigationEpoch = 0;
  const isVisible = () => visible && !document.getElementById('tab-outlook')?.classList.contains('hidden');
  function sync() {
    if (!instance) return;
    instance.setView(view);
    const next = isVisible();
    if (next !== deliveredVisible) {deliveredVisible = next;instance.setVisible(next);}
  }
  function report(error) {if (isVisible()) showToast(`邮箱资源加载失败：${error.message || error}`);}
  async function inventoryChanged() {
    for (const prefix of ['/api/email-sources','/api/capabilities','/api/summary','/api/dashboard','/api/outlook']) invalidateApiCache(prefix);
    const results = await Promise.allSettled([loadCapabilities(),loadRegistrationEmailSources(),loadSummary()]);
    const failed = results.find(result => result.status === 'rejected');
    if (failed) throw failed.reason;
  }
  async function ensure() {
    if (instance) return instance;
    if (!loading) {
      const root = document.getElementById('email-page-root');
      loading = (async () => {
        if (!root) throw new Error('找不到邮箱资源挂载位置');
        if (!document.getElementById('task-center-style')) {
          const style = document.createElement('link');style.id = 'task-center-style';style.rel = 'stylesheet';style.href = root.dataset.styleUrl;document.head.append(style);
        }
        const module = await import(root.dataset.moduleUrl);
        instance = module.mountEmail(root, {visible:false, view, notify:message => showToast(message), confirm:message => window.confirm(message), clipboard:async text => {if (!await copyText(text,false)) throw new Error('复制失败');}, onNavigate:value => setModuleView('outlook',value), onInventoryChanged:inventoryChanged});
        deliveredVisible = false;sync();return instance;
      })().catch(error => {
        loading = null;
        if (instance) {instance.destroy();instance = null;}
        deliveredVisible = false;
        if (root) {
          root.replaceChildren();const message = document.createElement('p');message.setAttribute('role','alert');message.textContent = `邮箱资源加载失败：${error.message || error}`;
          const retry = document.createElement('button');retry.type = 'button';retry.textContent = '重新加载';retry.addEventListener('click',() => void setVisible(visible));root.append(message,retry);
        }
        throw error;
      });
    }
    return loading;
  }
  async function setVisible(value) {
    const next = Boolean(value);if (!next && visible) navigationEpoch++;
    visible = next;sync();
    if (!isVisible()) return;
    try {await ensure();sync();} catch (error) {report(error);}
  }
  async function invoke(method, ...args) {
    if (!isVisible()) return;
    const epoch = navigationEpoch;
    try {const api = await ensure();if (epoch === navigationEpoch && isVisible()) return await api[method](...args);} catch (error) {report(error);}
  }
  return {
    setVisible,
    setView(value) {const next = ['overview','list','derivations'].includes(value) ? value : 'overview';if (view !== next) navigationEpoch++;view = next;instance?.setView(view);},
    refreshOverview() {return invoke('refreshOverview');},
    refreshInventory() {return invoke('refreshInventory');},
    refreshHistory() {return invoke('refreshHistory');},
    refreshDerivationSummary() {return invoke('refreshDerivationSummary');},
    openImport(source) {return invoke('openImport', ['outlook','generic_api','email_butler'].includes(source) ? source : undefined);},
    openButlerImport() {return invoke('openButlerImport');},
    closeDialogs() {navigationEpoch++;instance?.closeDialogs();},
  };
})();
function loadMailResources() {return window.EmailPage.refreshOverview();}
function loadOutlook() {return window.EmailPage.refreshInventory();}
function loadEmailDerivationResources() {return window.EmailPage.refreshHistory();}
function loadEmailDerivationSummary() {return window.EmailPage.refreshDerivationSummary();}
function openOutlookImportModal(source) {return window.EmailPage.openImport(source);}
function closeOutlookImportModal() {return window.EmailPage.closeDialogs();}
function openButlerImportModal() {return window.EmailPage.openButlerImport();}
function closeButlerImportModal() {return window.EmailPage.closeDialogs();}
