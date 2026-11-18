// Python regressions exercise the shipped Vue owners through the shared loader.
const assert = require('node:assert/strict');

function installNetworkFence() {
  const attempts = [], restore = [];
  const reject = () => {attempts.push('network'); throw new Error('offline_ui_contract_network_forbidden');};
  for (const [target, name] of [
    [globalThis, 'fetch'],
    [require('node:net').Socket.prototype, 'connect'],
    [require('node:http'), 'request'], [require('node:http'), 'get'],
    [require('node:https'), 'request'], [require('node:https'), 'get'],
    [require('node:dns'), 'lookup'], [require('node:dns'), 'resolve'],
  ]) {
    const previous = target[name]; target[name] = reject;
    restore.push(() => {target[name] = previous;});
  }
  return () => {restore.reverse().forEach(fn => fn()); assert.deepEqual(attempts, [], 'no real network attempt');};
}

async function run(name, metadata = []) {
  const closeFence = installNetworkFence();
  const fixture = require('./vue_fixture.cjs');
  const {harness, field, createConfigView, cleanup, flush, navigation} = fixture;
  const cleanups = [];
  try {
    const contracts = {
      async remail_fields() {
        const fields = metadata.map(item => ({...item, value: item.default}));
        const source = fields.find(item => item.key === 'EMAIL_SOURCE');
        assert.ok(source && !source.options.some(option => option.value === 'remail'));
        source.value = 'remail';
        const view = createConfigView(fields);
        for (const schema of fields.filter(item => item.key.startsWith('REMAIL_'))) {
          assert.equal(navigation.emailConfigSectionForKey(schema.key)[0], 'Remail');
          const row = view.mountField(schema.key);
          assert.equal(row.findAll(`[data-key="${schema.key}"]`).length, 1);
          const control = row.get(`[data-key="${schema.key}"]`);
          if (schema.secret) assert.equal(control.attributes('type'), 'password');
          if (schema.options?.length) {
            assert.equal(control.element.tagName, 'SELECT');
            assert.deepEqual(control.findAll('option').map(option => option.element.value),
              schema.options.map(option => option.value));
          }
          if (schema.type === 'int') assert.equal(control.attributes('min'), String(schema.range.min));
          if (schema.editable === false) assert.equal(row.get('fieldset').element.disabled, true);
        }
        const picker = view.mountField('EMAIL_SOURCE');
        assert.ok(picker.find('details').exists(), 'source uses the real ordered picker');
        assert.ok(!picker.findAll('[data-choice]').some(choice => /remail/i.test(choice.text())));
        assert.ok(!picker.find('[aria-label="移除 remail"]').exists());
        assert.doesNotMatch(picker.get('summary').text(), /remail/i);
      },

      async extract_remote_types() {
        const options = [{value: 'pix', label: 'PIX'}, {value: 'old', label: '旧静态类型'}];
        const view = createConfigView([field('EXTRACT_LINK_TYPE', '提链', {value: 'pix', options})], {
          request: async path => {
            assert.equal(path, '/api/extract-link/types');
            return {items: [
              {type: 'pix', label: '远端 PIX'}, {type: 'momo', label: '远端 MoMo'},
              {type: 'hidden', visible: false}, {type: 'disabled', enabled: false},
            ]};
          },
          getSchema: async () => [field('EXTRACT_LINK_TYPE', '提链', {value: 'momo', options})],
        });
        await flush(); await view.search('EXTRACT_LINK_TYPE');
        const select = view.control('EXTRACT_LINK_TYPE');
        assert.equal(select.element.tagName, 'SELECT');
        assert.deepEqual(view.requests.map(call => [call.url, call.options.method]),
          [['/api/extract-link/types', 'GET']]);
        assert.deepEqual(select.findAll('option').map(option => [option.element.value, option.text()]),
          [['pix', '远端 PIX'], ['momo', '远端 MoMo']]);
        assert.equal(select.element.value, 'pix');
        await select.setValue('momo');
        assert.equal(view.owner.readField('EXTRACT_LINK_TYPE'), 'momo');
        await view.save();
        assert.deepEqual(view.saves, [{EXTRACT_LINK_TYPE: 'momo'}]);
        view.owner.setField('EXTRACT_LINK_TYPE', 'historic_unknown');
        await view.actions.loadExtractTypes(); await flush();
        assert.equal(view.owner.readField('EXTRACT_LINK_TYPE'), 'historic_unknown');
        assert.equal(select.element.value, 'historic_unknown');
        assert.match(select.findAll('option')[0].text(), /当前配置/);
      },

      async primary_navigation() {
        const schema = require('../../frontend/src/features/config/schemaNavigation.fixture.json');
        const view = createConfigView(schema);
        for (const alias of ['注册与账号', '执行方式']) {
          await view.open(alias);
          assert.equal(view.wrapper.get('[data-config-section]').attributes('data-config-section'), '注册主链路');
          assert.equal(view.wrapper.get('[data-config-nav][aria-current=page]').attributes('data-config-nav'), '注册与账号');
        }
        const domains = () => view.wrapper.findAll('[data-config-domain-v2]').map(button => button.attributes('data-config-domain-v2'));
        assert.deepEqual(domains(), ['注册主链路', '账号补全', '注册与账号', '查活', '刷新 AT', '补密码', '补 2FA', '邮箱换绑']);
        for (const domain of ['注册主链路', '账号补全', '查活', '刷新 AT', '补密码', '补 2FA', '邮箱换绑']) {
          await view.wrapper.get(`[data-config-domain-v2="${domain}"]`).trigger('click');
          assert.equal(view.wrapper.get('[data-config-section]').attributes('data-config-section'), domain);
          assert.ok(view.wrapper.find('[data-config-setting]').exists(), `${domain} keeps actual field rows`);
          assert.equal(view.wrapper.find('[data-lifecycle-section-v2]').exists(), false);
        }
        await view.open('系统与维护');
        assert.deepEqual(domains(), ['并发控制', '通用配置', 'WebUI 授权', '定时任务', '任务中心', '注册调试']);
        await view.wrapper.get('[data-config-domain-v2="注册调试"]').trigger('click');
        assert.equal(view.wrapper.get('[data-config-section]').attributes('data-config-section'), '注册调试');
        assert.ok(view.wrapper.find('[data-config-setting]').exists());
        assert.doesNotMatch(view.wrapper.text(), /旧版补齐配置|补全规则|补全配置/);
      },
    };

    if (name.startsWith('sentinel_')) {
      const {createRequire} = require('node:module');
      const path = require('node:path');
      const frontendRequire = createRequire(path.join(__dirname, '../../frontend/package.json'));
      const {defineComponent, h, ref} = frontendRequire('vue');
      const {createConfigDraft} = harness.load('src/features/config/useConfigDraft.ts');
      const {useConfigActions} = harness.load('src/features/config/useConfigActions.ts');
      const Page = harness.load('src/features/config/ConfigPage.vue').default;
      const timers = new Map(), calls = [], saves = [];
      const setTimer = globalThis.setTimeout, clearTimer = globalThis.clearTimeout;
      globalThis.setTimeout = (callback, delay, ...args) => {
        if (delay !== 1500) return setTimer(callback, delay, ...args);
        const key = Symbol('sentinel-poll'); timers.set(key, () => callback(...args)); return key;
      };
      globalThis.clearTimeout = key => {if (!timers.delete(key)) clearTimer(key);};
      cleanups.push(() => {globalThis.setTimeout = setTimer; globalThis.clearTimeout = clearTimer;});
      const status = (overrides = {}) => ({
        ok: true, running: false, last_checked_at: null, last_status: 'never', error_code: null,
        builtin: {version: '20261101', sha256: 'a'.repeat(64)}, candidate: null,
        comparison: 'not_checked', ...overrides,
      });
      const candidate = {
        version: '20261103', sha256: 'b'.repeat(64), fetched_at: 1793670000,
        generic_status: 'static_markers_present', proto2_status: 'needs_adaptation', runtime_verified: false,
      };
      let respond = async () => status(), actions, page, active, owner;
      function mount(activeInitially = true) {
        localStorage.setItem(navigation.menuStorageKey, '通用配置');
        const fields = [field('EXAMPLE', '通用配置', {value: 'saved'}), field('OTHER', 'C2A')];
        owner = createConfigDraft({initialFields: fields, api: {
          getSchema: async () => fields, save: async updates => {saves.push(updates); return {ok: true};}, invalidate() {},
        }});
        active = ref(activeInitially);
        const Host = defineComponent({setup() {
          actions = useConfigActions(owner, {request: async (url, options = {}) => {
            if (url === '/api/extract-link/types') return {items: [{type: 'pix', label: 'PIX'}]};
            const call = {url, method: options.method || 'GET', options}; calls.push(call); return respond(call);
          }});
          return () => h(Page, {owner, actions, active: active.value});
        }});
        page = harness.mount(Host);
        cleanups.push(() => owner.dispose());
      }
      const panel = () => page.get('[data-config-tool="sentinel"]');
      const check = async () => {await panel().get('[data-config-action="check-sentinel"]').trigger('click'); await flush();};
      const refresh = async () => {
        await panel().findAll('button').find(button => button.text() === '刷新状态').trigger('click'); await flush();
      };
      const open = async name => {
        const target = navigation.destination(name, owner.fields.value);
        await page.get(`[data-config-nav="${target.menu}"]`).trigger('click');
        await page.get(`[data-config-domain-v2="${target.domain}"]`).trigger('click');
        await flush();
      };
      const runTimer = async () => {
        assert.equal(timers.size, 1); const [key, callback] = timers.entries().next().value;
        timers.delete(key); callback(); await flush();
      };
      const facts = () => Object.fromEntries(panel().findAll('dt').map((dt, index) => [dt.text(), panel().findAll('dd')[index].text()]));
      Object.assign(contracts, {
        async sentinel_initial() {
          mount(false); await flush();
          assert.match(panel().text(), /Sentinel 检查/);
          assert.match(panel().text(), /不自动切换现用版本/);
          assert.equal(calls.length, 0);
          active.value = true; await flush();
          assert.deepEqual(calls.map(call => [call.url, call.method]), [['/api/maintenance/sentinel', 'GET']]);
          assert.equal(facts()['当前内置版本'], '20261101');
          assert.match(panel().text(), /尚未检查/);
          assert.equal(panel().get('[role="status"]').attributes('aria-live'), 'polite');
          assert.equal(timers.size, 0);
          await open('C2A');
          assert.equal(page.find('[data-config-tool="sentinel"]').exists(), false);
          assert.equal(calls.length, 1);
        },
        async sentinel_single_flight() {
          mount(); await flush();
          await page.get('[data-key="EXAMPLE"]').setValue('unsaved');
          const input = page.get('[data-key="EXAMPLE"]').element;
          let finish;
          respond = call => call.method === 'POST' ? new Promise(resolve => {finish = resolve;})
            : status({candidate, comparison: 'version_changed', last_status: 'refreshed', last_checked_at: 1793670000});
          await check();
          await check();
          assert.equal(calls.filter(call => call.method === 'POST').length, 1);
          assert.equal(calls[1].url, '/api/maintenance/sentinel/check');
          assert.equal(calls[1].options.body, '{}');
          assert.equal(panel().get('[data-config-action="check-sentinel"]').element.disabled, true);
          assert.match(panel().get('[data-config-action="check-sentinel"]').text(), /检查中/);
          finish(status({started: true, running: true})); await flush();
          assert.equal(timers.size, 1);
          await runTimer();
          assert.equal(facts()['版本比较'], '发现新版本');
          assert.equal(facts()['发现版本'], '20261103');
          assert.equal(facts()['generic 静态检查'], '通过（未运行验证）');
          assert.equal(facts()['Proto2 静态检查'], '需要适配');
          assert.equal(owner.readField('EXAMPLE'), 'unsaved');
          assert.equal(page.get('[data-key="EXAMPLE"]').element, input);
          assert.equal(input.value, 'unsaved');
          assert.deepEqual(saves, []);
          assert.equal(timers.size, 0);
        },
        async sentinel_navigation() {
          let finish; respond = () => new Promise(resolve => {finish = resolve;});
          mount(); await flush();
          await open('C2A');
          finish(status({running: true})); await flush();
          assert.equal(timers.size, 0);
          respond = () => status({running: true});
          await open('通用配置');
          assert.equal(timers.size, 1);
          active.value = false; await flush();
          assert.equal(timers.size, 0);
          assert.equal(calls.length, 2);
        },
        async sentinel_failure() {
          respond = () => status({candidate, comparison: 'content_changed', last_status: 'refreshed', last_checked_at: 1793670000});
          mount(); await flush();
          assert.equal(facts()['版本比较'], '同版本内容变化');
          respond = async () => {throw new Error('/private/secret.js raw source credentials');};
          await check();
          assert.equal(facts()['发现版本'], '20261103');
          assert.match(panel().text(), /重试/);
          assert.doesNotMatch(panel().text(), /private|secret\.js|raw source|credentials/);
          assert.equal(timers.size, 0);
          respond = () => status({candidate, comparison: 'same', last_status: 'refreshed'});
          await check();
          assert.equal(facts()['版本比较'], '同当前一致');
          assert.equal(actions.states.sentinel.error, '');
          assert.equal(calls.filter(call => call.method === 'POST').length, 2);
        },
        async sentinel_read_retry() {
          respond = async () => {throw new Error('GET /internal/path');};
          mount(); await flush();
          assert.match(panel().text(), /重试/);
          assert.doesNotMatch(panel().text(), /internal/);
          respond = () => status({builtin: {version: '<script>alert(1)</script>', sha256: 'a'.repeat(64)}});
          await refresh();
          assert.equal(calls.length, 2);
          assert.ok(calls.every(call => call.method === 'GET'));
          assert.match(panel().html(), /&lt;script&gt;/);
          assert.equal(panel().find('script').exists(), false);
          assert.doesNotMatch(panel().html(), /<script>/);
        },
        async sentinel_corrupt() {
          respond = () => status({candidate, comparison: 'version_changed', last_status: 'refreshed'});
          mount(); await flush();
          respond = () => status({last_status: 'corrupt', comparison: 'unknown'});
          await check();
          assert.equal(facts()['发现版本'], '20261103');
          assert.match(panel().text(), /不可用/);
          assert.match(panel().text(), /重试/);
          assert.equal(panel().get('[data-config-action="check-sentinel"]').element.disabled, false);
          assert.doesNotMatch(panel().text(), /sha256|static_markers_present|needs_adaptation/);
        },
        async sentinel_document() {
          respond = () => status({running: true}); mount(); await flush();
          assert.equal(timers.size, 1);
          const prior = Object.getOwnPropertyDescriptor(document, 'hidden');
          let hidden = false;
          Object.defineProperty(document, 'hidden', {configurable: true, get: () => hidden});
          cleanups.push(() => {if (prior) Object.defineProperty(document, 'hidden', prior); else delete document.hidden;});
          hidden = true; document.dispatchEvent(new Event('visibilitychange')); await flush();
          assert.equal(timers.size, 0);
          hidden = false; document.dispatchEvent(new Event('visibilitychange')); await flush();
          assert.equal(calls.length, 2);
          assert.ok(calls.every(call => call.method === 'GET'));
        },
      });
    }
    assert.ok(contracts[name], `unknown contract: ${name}`);
    await contracts[name]();
    console.log(`ok ${name}`);
  } finally {
    cleanup();
    cleanups.reverse().forEach(fn => fn());
    harness.close();
    closeFence();
  }
}

module.exports = {installNetworkFence};
if (require.main === module && process.argv[2]) {
  run(process.argv[2], JSON.parse(process.argv[3] || '[]')).catch(error => {console.error(error); process.exitCode = 1;});
}
