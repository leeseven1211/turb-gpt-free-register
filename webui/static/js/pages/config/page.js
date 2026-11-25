// The Vue owner holds all config drafts, form state, saves and tool actions.
window.ConfigPage = (() => {
  let instance = null, loading = null, visible = false, pendingGroup = null;
  async function ensure() {
    if (instance) return instance;
    if (!loading) {
      const root = document.getElementById('config-page-root');
      loading = (async () => {
        if (!root) throw new Error('找不到配置页挂载位置');
        if (!document.getElementById('task-center-style')) {
          const style = document.createElement('link');style.id = 'task-center-style';style.rel = 'stylesheet';style.href = root.dataset.styleUrl;document.head.append(style);
        }
        const module = await import(root.dataset.moduleUrl);
        instance = module.mountConfig(root, {
          visible,
          onSavedFields(fields) {CONFIG = fields.map(field => ({...field}));},
          onSaved() {
            invalidateApiCache('/api/config');invalidateApiCache('/api/ui-settings');
            void Promise.allSettled([loadCapabilities(),loadRegistrationEmailSources()]);
          },
          onNavigateTasks(target) {
            if (target.registration) {
              const register = document.getElementById('tab-register');if (register) register.dataset.moduleView = 'tasks';
              window.RegistrationPage?.setView('tasks');
              activateTab('register');
              void window.RegistrationPage?.load({id:'',email:'',email_source:'',proxy:'',status:'',error:'',date_from:'',date_to:'',page:1});
            } else window.TaskCenter.open({filters:{type:(target.types || []).join(',')}});
          },
        });
        instance.setVisible(visible);
        await instance.load();
        if (pendingGroup) {instance.open(pendingGroup);pendingGroup = null;}
        markViewReady('config');
        return instance;
      })().catch(error => {
        loading = null;
        if (instance) {instance.destroy();instance = null;}
        if (root) {
          root.replaceChildren();const message = document.createElement('p');message.setAttribute('role','alert');message.textContent = `配置加载失败：${error.message || error}`;
          const retry = document.createElement('button');retry.type = 'button';retry.textContent = '重新加载';retry.addEventListener('click',() => void loadConfig());root.append(message,retry);
        }
        throw error;
      });
    }
    return loading;
  }
  return {
    async load() {try {const exists = Boolean(instance);const api = await ensure();if (exists) await api.refresh();else await api.load();markViewReady('config');} catch (error) {showToast(`配置加载失败：${error.message || error}`);}},
    setVisible(value) {visible = Boolean(value);instance?.setVisible(visible);},
    async open(name) {pendingGroup = String(name || '');visible = true;activateTab('config');try {const api = await ensure();if (pendingGroup) {api.open(pendingGroup);pendingGroup = null;}} catch (error) {showToast(`配置加载失败：${error.message || error}`);}},
  };
})();
function loadConfig() {return window.ConfigPage.load();}
function openConfigGroup(name) {return window.ConfigPage.open(name);}
