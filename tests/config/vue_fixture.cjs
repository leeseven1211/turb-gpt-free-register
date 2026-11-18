const {createVueHarness} = require('../frontend_vue_loader.cjs');
const harness = createVueHarness();
const {createConfigDraft} = harness.load('src/features/config/useConfigDraft.ts');
const {createConfigActions} = harness.load('src/features/config/configActions.ts');
const Page = harness.load('src/features/config/ConfigPage.vue').default;
const Field = harness.load('src/features/config/ConfigField.vue').default;
const navigation = harness.load('src/features/config/navigation.ts');
const live = [];
const field = (key, group = '通用配置', extra = {}) => ({key, group, label: key, type: 'str', value: '', ...extra});
const flush = async () => {await new Promise(resolve => setImmediate(resolve)); await harness.nextTick();};
function createConfigView(fields = [], dependencies = {}) {
  const saves = [], requests = [];
  const api = {
    async getSchema() {return dependencies.getSchema ? dependencies.getSchema() : fields;},
    async save(updates) {
      saves.push(structuredClone(updates));
      return dependencies.save ? dependencies.save(updates) : {ok: true, updated: Object.keys(updates), reloaded: true};
    },
    invalidate() {},
  };
  const owner = createConfigDraft({api, initialFields: fields});
  const actions = createConfigActions(owner, {
    ...dependencies,
    request: async (url, options = {}) => {
      requests.push({url, options});
      if (dependencies.request) return dependencies.request(url, options);
      return url === '/api/extract-link/types' ? {items: [{type: 'plus', label: 'Plus'}]} : {ok: true};
    },
  });
  const wrapper = harness.mount(Page, {props: {owner, actions}});
  live.push({owner, actions});
  return {
    owner, actions, wrapper, saves, requests, dependencies,
    async open(name) {wrapper.vm.open(name); await harness.nextTick();},
    async search(value) {await wrapper.get('#config-vue-search').setValue(value); await harness.nextTick();},
    async section(name) {await wrapper.get(`[data-config-subsection="${name}"]`).trigger('click');},
    control(key) {return wrapper.get(`[data-key="${key}"]`);},
    async edit(key, value) {await this.search(key); await this.control(key).setValue(value);},
    async save() {await wrapper.get('.config-vue-savebar .primary').trigger('click'); await flush();},
    mountField(key) {return harness.mount(Field, {props: {owner, field: owner.field(key), actions}});},
  };
}
function cleanup() {harness.cleanup();live.splice(0).forEach(({owner,actions}) => {actions.dispose();owner.dispose();});}
module.exports = {harness, field, createConfigView, cleanup, flush, navigation};
