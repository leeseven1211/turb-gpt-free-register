/* Test-only loader: execute the saved TypeScript owner with real Vue/jsdom. */
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const {createRequire} = require('node:module');
const frontend = path.resolve(__dirname, '../../frontend');
const frontendRequire = createRequire(path.join(frontend, 'package.json'));
const {JSDOM} = frontendRequire('jsdom');
const ts = frontendRequire('typescript');
const dom = new JSDOM('<!doctype html><html><body></body></html>', {url: 'http://localhost/'});
for (const key of ['window', 'document', 'HTMLElement', 'Element', 'SVGElement', 'Node', 'CustomEvent', 'Event', 'MutationObserver']) {
  global[key] = dom.window[key];
}
const {createApp, h} = frontendRequire('vue');
const modules = new Map();

function loadTypescript(filename) {
  if (modules.has(filename)) return modules.get(filename).exports;
  const module = new Module(filename);
  modules.set(filename, module);
  module.filename = filename;
  module.paths = Module._nodeModulePaths(path.dirname(filename));
  module.require = specifier => {
    if (specifier.startsWith('.')) {
      const resolved = path.resolve(path.dirname(filename), specifier);
      if (fs.existsSync(`${resolved}.ts`)) return loadTypescript(`${resolved}.ts`);
    }
    return frontendRequire(specifier);
  };
  const transformed = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename,
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
  });
  module._compile(transformed.outputText, filename);
  return module.exports;
}
const {useRegistration} = loadTypescript(path.join(frontend, 'src/features/registration/useRegistration.ts'));
const {createRegistrationApi} = loadTypescript(path.join(frontend, 'src/api/registration.ts'));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
};
const flush = async () => {
  for (let index = 0; index < 4; index++) await new Promise(resolve => setImmediate(resolve));
};
function response(batchId, status = 'running') {
  return {
    items: [], total: 0, revision: batchId,
    progress_batch: {batch_id: batchId, items: [{id: '9007199254740993', status}], status_counts: {[status]: 1}},
    progress_batches: [{batch_id: batchId}], status_counts: {active: status === 'running' ? 1 : 0},
  };
}
function ownerFixture(t, options = {}) {
  const intervals = new Map(), timeouts = new Map(), calls = [], writes = [], notifications = [];
  const original = Object.fromEntries(['setInterval', 'clearInterval', 'setTimeout', 'clearTimeout'].map(name => [name, window[name]]));
  let clock = 0, handle = 0, hidden = false;
  Object.defineProperty(document, 'hidden', {configurable: true, get: () => hidden});
  window.setInterval = (callback, milliseconds) => { const id = ++handle; intervals.set(id, {callback, milliseconds}); return id; };
  window.clearInterval = id => intervals.delete(id);
  window.setTimeout = (callback, milliseconds) => { const id = ++handle; timeouts.set(id, {callback, milliseconds}); return id; };
  window.clearTimeout = id => timeouts.delete(id);
  const api = {
    metadata: async () => ({sources: [], registration_drivers: []}),
    summary: async () => ({accounts: 2, email_supply: {total: 3, available: 0}}),
    jobs(params, signal) { const pending = deferred(); calls.push({params: {...params}, signal, ...pending}); return pending.promise; },
    create(payload) { const pending = deferred(); writes.push({kind: 'create', payload, ...pending}); return pending.promise; },
    action(url, payload) { const pending = deferred(); writes.push({kind: 'action', url, payload, ...pending}); return pending.promise; },
    log: async () => ({job: {status: 'success'}, log: 'synthetic log'}),
    debug: async () => ({enabled: false}),
    diagnostics: async () => ({enabled: false}),
    compare: async () => ({differences: []}),
    ...options.api,
  };
  const container = document.createElement('div');
  document.body.append(container);
  let owner;
  const app = createApp({setup() {
    owner = useRegistration({api, visible: false, notify: message => notifications.push(message), ...options.deps});
    return () => h('div');
  }});
  app.mount(container);
  t.after(() => {
    app.unmount();
    container.remove();
    Object.assign(window, original);
  });
  return {
    owner, api, calls, writes, intervals, timeouts, notifications,
    hideDocument(value) { hidden = value; document.dispatchEvent(new Event('visibilitychange')); },
    async tick() {
      clock += 10000;
      for (const {callback} of [...intervals.values()]) callback();
      await flush();
    },
    get clock() { return clock; },
  };
}

module.exports = {ownerFixture, deferred, response, flush, createRegistrationApi, frontend, dom};
