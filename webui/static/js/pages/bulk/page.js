// The Vue page owns bulk data, drafts, intents and polling; this adapter owns loading and host navigation.
window.BulkTasks = (() => {
  let instance = null, loading = null, visible = false, generation = 0, drainingAccounts = null;
  let navigation = {tab:'bulk',view:'list'}, pendingAccounts = null;
  const clone = value => JSON.parse(JSON.stringify(value));
  function normalize(raw = {}) {
    const nav = {tab:'bulk',view:['list','create','detail'].includes(raw.view)?raw.view:'list'};
    for (const key of ['batch_id','round_id','result_state','cursor','q','operation','state','created_from','created_to']) {
      if (typeof raw[key] === 'string' && raw[key]) nav[key] = raw[key];
    }
    if (nav.view === 'detail') {
      if (!/^[1-9]\d*$/.test(nav.batch_id || '')) return {tab:'bulk',view:'list'};
      if (nav.q || raw.reason_code) {delete nav.q; delete nav.cursor;}
      if (['attention_required','request_unknown','manual_reconcile','unknown','unconfirmed'].includes(nav.result_state)) nav.result_state = 'failed';
    }
    return nav;
  }
  function syncSidebar() {
    document.querySelectorAll('[data-bulk-nav]').forEach(button => button.classList.toggle('is-active', button.dataset.bulkNav === navigation.view));
  }
  function isVisible() {return visible && !document.hidden && !document.getElementById('tab-bulk')?.classList.contains('hidden');}
  function report(error) {showToast(`批量任务加载失败：${error.message || error}`);}
  async function drainAccounts(api) {
    if (drainingAccounts) return drainingAccounts;
    const request = pendingAccounts;
    if (!request || request.generation !== generation || !isVisible()) return;
    const drain = Promise.resolve().then(() => {
      if (request !== pendingAccounts || request.generation !== generation || !isVisible()) return;
      return api.fromAccounts(request.selected, request.operationKey, request.snapshot);
    }).then(() => {if (pendingAccounts === request) pendingAccounts = null;});
    drainingAccounts = drain;
    try {await drain;} finally {if (drainingAccounts === drain) drainingAccounts = null;}
  }
  async function ensure() {
    if (instance) {await drainAccounts(instance); return instance;}
    if (!loading) {
      const root = document.getElementById('bulk-page-root');
      loading = (async () => {
        if (!root) throw new Error('找不到批量任务挂载位置');
        if (!document.getElementById('task-center-style')) {
          const style = document.createElement('link');style.id = 'task-center-style';style.rel = 'stylesheet';style.href = root.dataset.styleUrl;document.head.append(style);
        }
        const module = await import(root.dataset.moduleUrl);
        instance = module.mountBulk(root, {
          query: window.AccountQuery, navigation, isVisible,
          callbacks: {
            navigate() {}, updateNavigation() {}, notify: message => showToast(message),
            formatDateTime: value => value ? formatDateTime(value) : '—',
            facetLabel: (group,value) => facetLabel(group,value),
            openTask: (taskId,runId) => openAccountTaskLog(taskId,runId || null),
          },
          onNavigation: (nav,mode) => {
            navigation = {...nav};syncSidebar();visible = true;
            activateTab('bulk',true,'none');recordNavigationHistory(mode);
          },
        });
        instance.setVisible(isVisible());
        return instance;
      })().catch(error => {
        loading = null;
        if (root) {
          root.replaceChildren();
          const message = document.createElement('p');message.setAttribute('role','alert');message.textContent = `批量任务加载失败：${error.message || error}`;
          const retry = document.createElement('button');retry.type = 'button';retry.className = 'jobs-tb-btn';retry.textContent = '重新加载';retry.addEventListener('click',() => void activate());root.append(message,retry);
        }
        throw error;
      });
    }
    const api = await loading;await drainAccounts(api);return api;
  }
  async function activate() {
    visible = true;syncSidebar();
    try {const api = await ensure();if (isVisible()) await api.activate();else api.setVisible(false);}
    catch (error) {report(error);}
  }
  function navigationState() {return instance ? instance.navigationState() : {...navigation};}
  function restoreNavigation(raw) {generation++;pendingAccounts = null;navigation = normalize(raw);instance?.restoreNavigation(navigation);syncSidebar();}
  async function navigate(view,extra = {},focusReport = false) {
    restoreNavigation({tab:'bulk',view,...extra});const ticket = generation;visible = true;
    activateTab('bulk',true,'none');recordNavigationHistory('push');
    try {const api = await ensure();if (ticket !== generation || !isVisible()) return;await api.activate();if (focusReport) await api.showReport();}
    catch (error) {report(error);}
  }
  async function fromAccounts(selected = false,operationKey = 'plan_check',snapshot = null) {
    const owner = window.AccountsPage?.isReady?.() ? window.AccountsPage : null;
    const captured = snapshot || owner?.getAccountSelectionSnapshot();
    if (!captured) {showToast('账号范围未就绪，请返回账号页重试');return;}
    if (selected && !captured.ids?.length) {showToast('请先选择账号');return;}
    generation++;
    pendingAccounts = {selected,operationKey,snapshot:clone(captured),generation};
    navigation = {tab:'bulk',view:'create'};visible = true;syncSidebar();
    activateTab('bulk',true,'none');
    try {await ensure();} catch (error) {report(error);}
  }
  document.querySelectorAll('[data-bulk-nav]').forEach(button => button.addEventListener('click',() => void navigate(button.dataset.bulkNav)));
  return {
    activate,navigationState,restoreNavigation,navigate,fromAccounts,
    setVisible(value) {const next = Boolean(value);if (!next && visible) {generation++;pendingAccounts = null;}visible = next;instance?.setVisible(isVisible());},
    async request(path,options) {return (await ensure()).request(path,options);},
    async intent(scope,path,body) {return (await ensure()).intent(scope,path,body);},
    async restoreSelectionRequest(body,result) {return (await ensure()).restoreSelectionRequest(body,result);},
  };
})();
