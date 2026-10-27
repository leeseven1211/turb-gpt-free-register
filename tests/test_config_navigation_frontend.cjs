const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/config.js'), 'utf8');

function createConfigView(fields = []) {
  const storage = new Map();
  const nodes = new Map();
  const domErrors = [];
  const saveCopy = {textContent: ''};
  const saveHint = {textContent: ''};
  const saveState = {
    classList: {toggle() {}},
    querySelector(selector) { return selector.includes('data-config-save-copy') ? saveCopy : null; },
  };
  const saveButton = {disabled: false, textContent: ''};
  const layoutListeners = {};
  const rootListeners = {};
  const quotaControls = [];
  nodes.set('configSaveBarV2', {hidden: false});
  nodes.set('configDirtyBadge', {hidden: false, textContent: '', setAttribute() {}});
  nodes.set('configNavV2', {dataset: {}, addEventListener(name, callback) { this.listener = callback; }});
  nodes.set('configLayoutV2', {dataset: {}, addEventListener(name, callback) { layoutListeners[name] = callback; }});
  const root = {addEventListener(name, callback) { rootListeners[name] = callback; }};
  const context = {
    CONFIG: fields,
    layoutListeners,
    rootListeners,
    domErrors, saveCopy, saveHint,
    document: {
      getElementById(id) { return nodes.get(id) || null; },
      querySelector(selector) {
        return selector.includes('data-config-save-hint') ? saveHint : null;
      },
      querySelectorAll(selector) {
        if (selector.includes('data-query-huanguang-xxsyun-quota')) return quotaControls.map(control => control.button);
        if (selector.includes('data-huanguang-xxsyun-quota-status')) return quotaControls.map(control => control.status);
        if (selector.includes('data-config-save-state')) return [saveState];
        if (selector.includes('data-save-config-v2')) return [saveButton];
        if (selector.includes('config-field-error-v2')) return domErrors;
        return [];
      },
      addEventListener() {},
      documentElement: {dataset: {}},
    },
    window: {addEventListener() {}, scrollTo() {}, confirm() { return true; }},
    localStorage: {
      getItem(key) { return storage.get(key) || null; },
      setItem(key, value) { storage.set(key, String(value)); },
    },
    $(selector) { return selector === '#tab-config' ? root : nodes.get(selector.slice(1)) || null; },
    esc: value => String(value ?? ''),
    attrEsc: value => String(value ?? ''),
    isPlaceholderEmpty: value => value === null || value === undefined || value === '',
    activateTab() {}, showToast() {}, invalidateApiCache() {},
    loadCapabilities: async () => {}, loadRegistrationEmailSources: async () => {},
  };
  vm.createContext(context);
  vm.runInContext(`${source}
    loadConfig = async () => {};
    globalThis.view = {
      groups: configGroups, names: getConfigGroupNames,
      renderNav: renderConfigNavV2,
      destination: setConfigDestinationV2, open: openConfigGroup,
      render: renderConfigSectionV2, renderDomain: renderConfigDomainSectionV2,
      bind: bindConfigLayoutV2, save: saveConfigUpdates,
      stubLayoutRender() { renderConfigLayoutV2 = () => {}; },
      clickExtractLinkTab(section) {
        const button = {dataset: {extractLinkTab: section}};
        layoutListeners.click({target: {closest(selector) { return selector === '[data-extract-link-tab]' ? button : null; }}, preventDefault() {}});
      },
      clickXxsyunQuota(button) {
        return rootListeners.click({target: {closest(selector) { return selector === '[data-query-huanguang-xxsyun-quota]' ? button : null; }}, preventDefault() {}});
      },
      pending: CONFIG_PENDING_UPDATES, setPending: setPendingConfigValue,
      forcePending: (key, value) => setPendingConfigValue(key, value, {force: true}),
      errors: CONFIG_FIELD_ERRORS_V2, compositeModes: CONFIG_COMPOSITE_MODES_V2,
      read: readConfigElementValue, track: trackConfigFieldChange,
      saveUi: updateConfigSaveUi, domErrors, ui: {saveCopy, saveHint},
      proxySection: key => proxyConfigSectionForKey(key)[0],
      emailVisible: emailSectionEnabledV2,
      hmeTools: renderICloudHMEToolsV2,
      control: renderConfigControlMarkupV2,
      search(query, menu) { CONFIG_NAV_QUERY_V2 = query; selectConfigSearchDestinationV2(menu); },
      fields(value) { CONFIG = value; },
      state() { return {
        menu: CONFIG_ACTIVE_GROUP_V2, domains: {...CONFIG_ACTIVE_DOMAIN_V2},
        email: CONFIG_EMAIL_ACTIVE_SECTION_V2, proxy: CONFIG_PROXY_ACTIVE_SECTION_V2,
        sms: CONFIG_SMS_ACTIVE_SECTION_V2, codex: CONFIG_CODEX_ACTIVE_SECTION_V2,
        extractLink: CONFIG_EXTRACT_LINK_ACTIVE_SECTION_V2,
      }; },
    };
  `, context);
  return {view: context.view, context, storage, nodes, domErrors, quotaControls};
}

const field = (key, group, extra = {}) => ({key, group, label: key, type: 'str', value: '', ...extra});

const xxsyunKey = 'EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY';
function createXxsyunQuotaControl(controls, {value = '', clear = false} = {}) {
  const status = {textContent: ''};
  const input = {
    value, type: 'password', dataset: {key: xxsyunKey, ...(clear ? {secretClear: 'true'} : {})},
    closest(selector) {
      if (selector.includes('[data-key]')) return this;
      if (selector === '#tab-config') return {};
      return null;
    },
  };
  const control = {
    input, status,
    querySelector(selector) {
      if (selector.includes('data-key') || selector.includes('data-secret-input')) return input;
      if (selector.includes('data-huanguang-xxsyun-quota-status')) return status;
      return null;
    },
  };
  control.button = {
    disabled: false, textContent: '查询剩余次数',
    closest(selector) { return selector === '[data-huanguang-xxsyun-key]' ? control : null; },
  };
  controls.push(control);
  return control;
}

test('幻光 XXSYUN Key 复用密码框与清除，并提供剩余次数查询和默认关闭的转单开关', () => {
  const fields = [
    field('EXTRACT_LINK_DEFAULT_PROVIDER', '提链', {value: 'huanguang', options: [{value: 'huanguang', label: '幻光'}]}),
    field('EXTRACT_LINK_HUANGUANG_ENABLED', '提链', {type: 'bool', value: true}),
    field(xxsyunKey, '提链', {label: 'XXSYUN API Key', secret: true, configured: true}),
    field('EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED', '提链', {type: 'bool', label: '幻光超时后转 XXSYUN', value: false}),
  ];
  const {view} = createConfigView(fields);
  view.search(xxsyunKey);
  const markup = view.renderDomain('提链', fields);
  assert.equal(view.state().extractLink, '幻光');
  assert.ok(markup.includes(`<input type="password" data-key="${xxsyunKey}" value=""`));
  assert.ok(markup.includes(`data-clear-secret="${xxsyunKey}"`));
  assert.ok(markup.includes('data-query-huanguang-xxsyun-quota'));
  assert.ok(markup.includes('查询剩余次数'));
  assert.match(markup, /data-huanguang-xxsyun-quota-status[^>]*role="status"/);
  assert.doesNotMatch(markup, /data-key="EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED" checked/);
});

test('XXSYUN 次数查询区分已保存 Key、未保存输入和明确清空，不保存配置并保留真实零', async () => {
  const scenarios = [
    {input: {}, body: {}, response: {ok: true, remainingUses: 0, totalUses: null, reservedUses: null}, text: '剩余 0 次 · 总次数 未知 · 占用 未知'},
    {input: {value: 'draft-test-key'}, body: {api_key: 'draft-test-key'}, response: {ok: true, remainingUses: 7, totalUses: 10, reservedUses: 3}, text: '剩余 7 次 · 总次数 10 · 占用 3'},
    {input: {clear: true}, body: {api_key: ''}, response: {ok: true, remainingUses: 1, totalUses: null, reservedUses: 0}, text: '剩余 1 次 · 总次数 未知 · 占用 0'},
    {input: {}, pendingClear: true, body: {api_key: ''}, response: {ok: true, remainingUses: 1, totalUses: null, reservedUses: null}, text: '剩余 1 次 · 总次数 未知 · 占用 未知'},
  ];
  for (const scenario of scenarios) {
    const {view, context, quotaControls} = createConfigView([field(xxsyunKey, '提链', {secret: true, configured: true})]);
    const control = createXxsyunQuotaControl(quotaControls, scenario.input);
    if (scenario.pendingClear) view.forcePending(xxsyunKey, '');
    const pendingBefore = JSON.stringify(view.pending);
    const calls = [];
    context.api = async (url, options) => {
      calls.push({url, method: options.method, body: JSON.parse(options.body)});
      return scenario.response;
    };
    await view.clickXxsyunQuota(control.button);
    assert.deepEqual(calls, [{url: '/api/extract-link/huanguang/xxsyun-quota', method: 'POST', body: scenario.body}]);
    assert.equal(control.status.textContent, scenario.text);
    assert.equal(control.button.disabled, false);
    assert.equal(JSON.stringify(view.pending), pendingBefore);
  }
});

test('XXSYUN 查询失败和非法响应只显示固定中文提示', async () => {
  const responses = [
    async () => { throw new Error('raw-private-key-and-response'); },
    async () => ({ok: false, error: 'raw-private-key-and-response'}),
    async () => ({ok: true, remainingUses: null, totalUses: null, reservedUses: null}),
    async () => ({ok: true, remainingUses: 1.5, totalUses: null, reservedUses: null}),
    async () => ({ok: true, remainingUses: 1, totalUses: 2.5, reservedUses: null}),
    async () => ({ok: true, remainingUses: 1, totalUses: null, reservedUses: 0.5}),
    async () => ({ok: true, remainingUses: Number.MAX_SAFE_INTEGER + 1, totalUses: null, reservedUses: null}),
    async () => ({ok: true, remainingUses: 1, totalUses: Number.MAX_SAFE_INTEGER + 1, reservedUses: null}),
    async () => ({ok: true, remainingUses: 1, totalUses: null, reservedUses: Number.MAX_SAFE_INTEGER + 1}),
  ];
  for (const response of responses) {
    const {view, context, quotaControls} = createConfigView([field(xxsyunKey, '提链', {secret: true})]);
    const control = createXxsyunQuotaControl(quotaControls);
    context.api = response;
    await view.clickXxsyunQuota(control.button);
    assert.equal(control.status.textContent, '查询失败，请检查 XXSYUN API Key 后重试');
    assert.equal(control.button.disabled, false);
  }
});

test('XXSYUN Key 改变后旧查询不能覆盖新请求的状态和结果', async () => {
  const {view, context, quotaControls} = createConfigView([field(xxsyunKey, '提链', {secret: true, configured: true})]);
  const control = createXxsyunQuotaControl(quotaControls);
  const pending = [];
  context.api = () => new Promise(resolve => pending.push(resolve));
  const oldQuery = view.clickXxsyunQuota(control.button);
  assert.equal(control.button.disabled, true);
  assert.equal(control.status.textContent, '正在查询剩余次数…');
  control.input.value = 'new-draft-test-key';
  view.track({target: control.input});
  assert.equal(control.status.textContent, '');
  assert.equal(control.button.disabled, false);
  const newQuery = view.clickXxsyunQuota(control.button);
  pending[0]({ok: true, remainingUses: 99, totalUses: 99, reservedUses: 0});
  await oldQuery;
  assert.equal(control.button.disabled, true);
  assert.equal(control.status.textContent, '正在查询剩余次数…');
  pending[1]({ok: true, remainingUses: 2, totalUses: null, reservedUses: 0});
  await newQuery;
  assert.equal(control.status.textContent, '剩余 2 次 · 总次数 未知 · 占用 0');
  assert.equal(control.button.disabled, false);
});

test('配置导航包含独立提链菜单，字段只进入一个编辑投影', () => {
  const domains = ['通用配置', '注册主链路', '账号补全', '注册调试', '邮箱 / OTP', '接码平台',
    '代理与网络', 'RoxyBrowser', '浏览器画像', '人工节奏', 'Codex', '提链', 'WebUI 授权', '定时任务', '任务中心'];
  const fields = domains.map((domain, index) => field(`KEY_${index}`, domain));
  const {view} = createConfigView([...fields, {...fields[0]}]);
  const groups = view.groups();
  assert.equal(Object.keys(groups).length, 7);
  assert.deepEqual(Array.from(view.names()), Object.keys(groups));
  assert.equal(Object.values(groups).flat().length, fields.length);
  assert.deepEqual(Object.keys(groups), ['系统与维护', '注册与账号', '邮箱与验证码', '代理与网络', '浏览器', '服务集成', '提链']);
});

test('提链在资源与服务中独立成项，并分为通用与平台页签', () => {
  const fields = [
    field('EXTRACT_LINK_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_DEFAULT_PROVIDER', '提链', {value: 'lumen_flow', options: [
      {value: 'legacy', label: '现有提链服务'}, {value: 'lumen_flow', label: '流光'}, {value: 'huanguang', label: '幻光'},
    ]}),
    field('EXTRACT_LINK_DEFAULT_MODE', '提链', {value: 'extract_only'}),
    field('EXTRACT_LINK_BATCH_WORKERS', '提链', {type: 'int', value: 2}),
    field('EXTRACT_LINK_PREFLIGHT_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_PREFLIGHT_REFRESH_AT_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_LEGACY_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_LEGACY_EXTRACT_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_API_BASE', '提链', {value: 'https://provider.example.test'}),
    field('EXTRACT_LINK_CDK', '提链', {secret: true, configured: true}),
    field('EXTRACT_LINK_LUMEN_FLOW_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_LUMEN_FLOW_EXTRACT_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_LUMEN_FLOW_API_BASE', '提链', {value: 'https://flow.example.test'}),
    field('EXTRACT_LINK_HUANGUANG_ENABLED', '提链', {type: 'bool', value: false}),
    field('EXTRACT_LINK_HUANGUANG_EXTRACT_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_HUANGUANG_API_BASE', '提链', {value: 'https://light.example.test'}),
  ];
  const {view} = createConfigView(fields);
  const groups = view.groups();
  const navigation = view.renderNav(view.names(), groups);
  const markup = view.renderDomain('提链', fields);

  assert.match(navigation, /data-config-nav-group="资源与服务"/);
  assert.equal(groups['服务集成'], undefined);
  assert.ok((groups['提链'] || []).length > 0);
  assert.match(markup, /data-extract-link-tab="通用配置"/);
  assert.match(markup, /data-extract-link-tab="现有提链服务"/);
  assert.match(markup, /data-extract-link-tab="流光"/);
  assert.match(markup, /data-extract-link-tab="幻光"/);
  assert.match(markup, /data-multi-picker="EXTRACT_LINK_ENABLED_PROVIDERS"/);
  assert.match(markup, /data-multi-values="legacy,lumen_flow"/);
  assert.match(markup, /data-key="EXTRACT_LINK_PREFLIGHT_ENABLED"/);
  assert.match(markup, /data-key="EXTRACT_LINK_PREFLIGHT_REFRESH_AT_ENABLED"/);
  assert.doesNotMatch(markup, /data-key="EXTRACT_LINK_(?:LEGACY|LUMEN_FLOW|HUANGUANG)_ENABLED"/);
});

test('提链平台多选保存回现有平台启用开关', () => {
  const fields = [
    field('EXTRACT_LINK_DEFAULT_PROVIDER', '提链', {value: 'legacy', options: [
      {value: 'legacy', label: 'legacy'}, {value: 'lumen_flow', label: 'lumen_flow'}, {value: 'huanguang', label: 'huanguang'},
    ]}),
    field('EXTRACT_LINK_LEGACY_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_LUMEN_FLOW_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_HUANGUANG_ENABLED', '提链', {type: 'bool', value: false}),
  ];
  const {view} = createConfigView(fields);
  const input = {
    value: 'legacy,huanguang', type: 'hidden',
    dataset: {key: 'EXTRACT_LINK_ENABLED_PROVIDERS', extractProviderSelection: 'true'},
    closest(selector) {
      if (selector.includes('[data-key]')) return this;
      if (selector === '#tab-config') return {};
      return null;
    },
  };

  view.track({target: input});

  assert.deepEqual(JSON.parse(JSON.stringify(view.pending)), {
    EXTRACT_LINK_LUMEN_FLOW_ENABLED: false,
    EXTRACT_LINK_HUANGUANG_ENABLED: true,
  });
});

test('搜索提链平台配置时自动切换到对应平台页签', () => {
  const fields = [
    field('EXTRACT_LINK_DEFAULT_PROVIDER', '提链', {value: 'legacy', options: [
      {value: 'legacy', label: 'legacy'}, {value: 'lumen_flow', label: 'lumen_flow'}, {value: 'huanguang', label: 'huanguang'},
    ]}),
    field('EXTRACT_LINK_LEGACY_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_LUMEN_FLOW_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_HUANGUANG_ENABLED', '提链', {type: 'bool', value: true}),
    field('EXTRACT_LINK_LUMEN_FLOW_API_BASE', '提链'),
    field('EXTRACT_LINK_HUANGUANG_API_BASE', '提链'),
  ];
  const {view} = createConfigView(fields);

  view.search('EXTRACT_LINK_HUANGUANG_API_BASE');

  assert.equal(view.state().menu, '提链');
  assert.equal(view.state().extractLink, '幻光');
});

test('幻光页显示入口出口敏感多行代理池并保留明确清空操作', () => {
  const entryKey = 'EXTRACT_LINK_HUANGUANG_ENTRY_PROXIES';
  const exitKey = 'EXTRACT_LINK_HUANGUANG_EXIT_PROXIES';
  const fields = [
    field('EXTRACT_LINK_DEFAULT_PROVIDER', '提链', {value: 'huanguang', options: [
      {value: 'huanguang', label: '幻光'},
    ]}),
    field('EXTRACT_LINK_HUANGUANG_ENABLED', '提链', {type: 'bool', value: true}),
    field(entryKey, '提链', {type: 'list_str_multiline', secret: true, configured: true}),
    field(exitKey, '提链', {type: 'list_str_multiline', secret: true, configured: true}),
  ];
  const {view} = createConfigView(fields);
  view.search(entryKey);
  const markup = view.renderDomain('提链', fields);

  assert.equal(view.state().extractLink, '幻光');
  for (const key of [entryKey, exitKey]) {
    assert.ok(markup.includes(`<textarea data-key="${key}" data-secret-input="true"`));
    assert.ok(markup.includes(`data-clear-secret="${key}"`));
  }

  const input = (key, value, clear = false) => ({
    value, type: 'textarea', dataset: {key, ...(clear ? {secretClear: 'true'} : {})},
    closest(selector) {
      if (selector.includes('[data-key]')) return this;
      if (selector === '#tab-config') return {};
      return null;
    },
  });
  view.track({target: input(entryKey, '')});
  assert.equal(Object.hasOwn(view.pending, entryKey), false);
  view.track({target: input(entryKey, 'https://proxy.example.test:443\nsocks5h://proxy.example.test:1080')});
  assert.deepEqual(Array.from(view.pending[entryKey]), [
    'https://proxy.example.test:443', 'socks5h://proxy.example.test:1080',
  ]);
  view.track({target: input(exitKey, '', true)});
  assert.deepEqual(Array.from(view.pending[exitKey]), []);
});

test('幻光自动续查限额归属幻光页并使用可编辑数字控件', () => {
  const limits = [
    ['EXTRACT_LINK_HUANGUANG_RECONCILE_TIMEOUT', 3600],
    ['EXTRACT_LINK_HUANGUANG_NO_PROGRESS_TIMEOUT', 900],
    ['EXTRACT_LINK_HUANGUANG_MAX_QUERY_FAILURES', 12],
  ];
  const fields = [
    field('EXTRACT_LINK_DEFAULT_PROVIDER', '提链', {value: 'huanguang', options: [
      {value: 'huanguang', label: '幻光'},
    ]}),
    field('EXTRACT_LINK_HUANGUANG_ENABLED', '提链', {type: 'bool', value: true}),
    ...limits.map(([key, value]) => field(key, '提链', {type: 'int', value})),
  ];
  const {view} = createConfigView(fields);
  const common = view.renderDomain('提链', fields);
  for (const [key] of limits) assert.ok(!common.includes(`data-key="${key}"`));

  view.search(limits[0][0]);
  const markup = view.renderDomain('提链', fields);
  assert.equal(view.state().extractLink, '幻光');
  for (const [key, value] of limits) {
    assert.ok(markup.includes(`<input type="number" data-key="${key}"`));
    assert.ok(markup.includes(`value="${value}"`));
  }
});

test('幻光页区分提链和支付扫码 CDK，清除支付密钥不会修改提链密钥', () => {
  const extractKey = 'EXTRACT_LINK_HUANGUANG_CDK';
  const paymentKey = 'EXTRACT_LINK_HUANGUANG_PAYMENT_CDK';
  const fields = [
    field('EXTRACT_LINK_DEFAULT_PROVIDER', '提链', {value: 'huanguang', options: [
      {value: 'huanguang', label: '幻光'},
    ]}),
    field('EXTRACT_LINK_HUANGUANG_ENABLED', '提链', {type: 'bool', value: true}),
    field(extractKey, '提链', {label: '幻光提链 CDK', secret: true, configured: true}),
    field(paymentKey, '提链', {label: '幻光支付扫码 CDK', secret: true, configured: true}),
  ];
  const {view} = createConfigView(fields);
  view.search(paymentKey);
  const markup = view.renderDomain('提链', fields);

  assert.equal(view.state().extractLink, '幻光');
  assert.ok(markup.includes('幻光提链 CDK'));
  assert.ok(markup.includes('幻光支付扫码 CDK'));
  for (const key of [extractKey, paymentKey]) {
    assert.ok(markup.includes(`<input type="password" data-key="${key}" value=""`));
    assert.ok(markup.includes(`data-clear-secret="${key}"`));
  }
  const input = (value, clear = false) => ({
    value, type: 'password', dataset: {key: paymentKey, ...(clear ? {secretClear: 'true'} : {})},
    closest(selector) {
      if (selector.includes('[data-key]')) return this;
      if (selector === '#tab-config') return {};
      return null;
    },
  });
  view.track({target: input('')});
  assert.equal(Object.hasOwn(view.pending, paymentKey), false);
  view.track({target: input('payment-test-secret')});
  assert.equal(view.pending[paymentKey], 'payment-test-secret');
  view.track({target: input('', true)});
  assert.equal(view.pending[paymentKey], '');
  assert.equal(Object.hasOwn(view.pending, extractKey), false);
});

test('点击提链平台页签会切换页面内容', () => {
  const {view} = createConfigView([]);
  view.stubLayoutRender();
  view.bind();

  view.clickExtractLinkTab('流光');

  assert.equal(view.state().extractLink, '流光');
});

test('旧入口迁移到新分类并保留草稿值', () => {
  const fields = [field('ROXY_API_BASE', 'RoxyBrowser'), field('HUMANIZE_DELAY_FACTOR', '人工节奏', {type: 'float', value: 1})];
  const {view, storage} = createConfigView(fields);
  view.setPending('ROXY_API_BASE', 'http://127.0.0.1:5888');
  view.open('人工节奏');
  assert.equal(view.state().menu, '浏览器');
  assert.equal(view.state().domains['浏览器'], '人工节奏');
  assert.equal(storage.get('gpt_console_config_group'), '人工节奏');
  view.destination('执行方式');
  assert.equal(view.state().menu, '注册与账号');
  view.destination('网站配置');
  assert.equal(view.state().menu, '系统与维护');
  assert.equal(view.pending.ROXY_API_BASE, 'http://127.0.0.1:5888');
});

test('搜索配置键、帮助文案和旧领域可以定位隐藏子节', () => {
  const fields = [
    field('ROXY_API_BASE', 'RoxyBrowser'), field('TASK_CENTER_RETENTION_DAYS', '任务中心'),
    field('EMAIL_BUTLER_API_BASE', '邮箱 / OTP'), field('ICLOUD_HME_API_BASE', '邮箱 / OTP'),
    field('PROXY_1024_API_URL', '代理与网络'), field('PLAN_CHECK_TIMEOUT', '代理与网络'),
    field('SMS_API_KEY', '接码平台'), field('L_API_BASE', '接码平台'),
    field('CODEX_AUTH_URL_SOURCE', 'Codex'), field('CPA_MANAGEMENT_URL', 'Codex'),
  ];
  const {view} = createConfigView(fields);
  view.search('TASK_CENTER_RETENTION_DAYS');
  assert.equal(view.state().menu, '系统与维护');
  for (const [query, property, expected] of [
    ['ICLOUD_HME_API_BASE', 'email', 'iCloud 隐藏邮箱'],
    ['Email Butler', 'email', 'Email Butler'],
    ['PROXY_1024_API_URL', 'proxy', '代理来源'],
    ['PLAN_CHECK_TIMEOUT', 'menu', '注册与账号'],
    ['L_API_BASE', 'sms', 'L 接码'],
    ['CPA_MANAGEMENT_URL', 'codex', 'CPA配置'],
  ]) {
    view.search(query);
    assert.equal(view.state()[property], expected);
  }
});

test('套餐业务参数进入注册与账号，代理池兼容字段单独归组', () => {
  const fields = [
    field('PLAN_CHECK_COUNTRIES', '代理与网络', {type: 'list_str_multiline', value: ['JP'], country_codes: ['JP', 'US']}),
    field('PLAN_CHECK_TIMEOUT', '代理与网络', {type: 'int', value: 30}),
    field('PROXY_POOL_SOURCE', '代理与网络', {options: [{value: '1024proxy', label: '1024Proxy'}, {value: 'manual', label: '手动代理'}]}),
    field('ACCOUNT_PLAN_CHECK_PROXY_MODE', '代理与网络'),
    field('REGISTRATION_PROXY_RETRIES', '代理与网络', {type: 'int', value: 1}),
    field('ACCOUNT_ACTION_PROXY_RETRY_DELAY', '代理与网络', {type: 'float', value: 0.5}),
    field('PROXY_1024_REGION', '代理与网络'),
  ];
  const {view} = createConfigView(fields);
  const groups = view.groups();
  assert.deepEqual(Array.from(groups['注册与账号'], item => item.key), ['PLAN_CHECK_COUNTRIES', 'PLAN_CHECK_TIMEOUT', 'REGISTRATION_PROXY_RETRIES', 'ACCOUNT_ACTION_PROXY_RETRY_DELAY']);
  assert.equal(view.proxySection('PROXY_POOL_SOURCE'), '代理来源');
  assert.equal(view.proxySection('PROXY_POOL_WAIT_TIMEOUT'), '库存策略');
  assert.equal(view.proxySection('ACCOUNT_PLAN_CHECK_PROXY_MODE'), '高级兼容');
  assert.equal(view.proxySection('REGISTRATION_PROXY_RETRIES'), '注册主链路');
  assert.equal(view.proxySection('ACCOUNT_ACTION_PROXY_RETRY_DELAY'), '账号补全');
  assert.equal(view.proxySection('PROXY_1024_REGION'), '高级兼容');
});

test('统一多选保留顺序、未知值和可搜索摘要', () => {
  const {view} = createConfigView([
    field('EMAIL_SOURCE', '邮箱 / OTP', {value: 'mailnest,outlook', options: [
      {value: 'outlook', label: 'Outlook'}, {value: 'mailnest', label: 'MailNest'},
    ]}),
    field('ROXY_RANDOM_OS_CHOICES', 'RoxyBrowser', {type: 'str', value: 'Windows,custom', options: [
      {value: 'Windows', label: 'Windows'}, {value: 'macOS', label: 'macOS'},
    ]}),
  ]);
  const email = view.control(view.groups()['邮箱与验证码'][0]);
  const roxy = view.control(view.groups()['浏览器'][0]);
  assert.ok(email.includes('data-multi-picker="EMAIL_SOURCE"'));
  assert.ok(email.includes('data-key="EMAIL_SOURCE" value="mailnest,outlook"'));
  assert.ok(roxy.includes('当前值（custom）'));
  assert.ok(email.includes('select class="config-multi-compat-v2" multiple'));
});

test('敏感字段默认留空不清除，并提供显式清除入口', () => {
  const {view} = createConfigView([
    field('API_KEY', '通用配置', {secret: true, configured: true}),
    field('PROXY_POOL', '代理与网络', {secret: true, type: 'list_str_multiline', value: ['masked-proxy']}),
    field('PROXY_POOL_DEFAULT_COUNTRY', '代理与网络', {country_codes: ['JP', 'NA'], value: 'JP'}),
  ]);
  const markup = view.control(view.groups()['系统与维护'][0]);
  assert.ok(markup.includes('data-secret-input="true"'));
  assert.ok(markup.includes('data-clear-secret="API_KEY"'));
  const proxyMarkup = view.control(view.groups()['代理与网络'].find(item => item.key === 'PROXY_POOL'));
  assert.ok(proxyMarkup.includes('data-clear-secret="PROXY_POOL"'));
  assert.ok(proxyMarkup.includes('<textarea'));
  const input = (key, value, secretClear = 'true') => ({
    value, type: 'text', checked: false, dataset: {key, secretClear},
    closest(selector) {
      if (selector.includes('[data-key]')) return this;
      if (selector === '#tab-config') return {};
      return null;
    },
  });
  view.track({target: input('API_KEY', '')});
  view.track({target: input('PROXY_POOL', '')});
  assert.equal(view.pending.API_KEY, '');
  assert.deepEqual(Array.from(view.pending.PROXY_POOL), []);
  assert.equal(view.read({dataset: {}, value: 'NA'}, {key: 'PROXY_POOL_DEFAULT_COUNTRY', type: 'str'}), 'NA');
});

test('等待和价格上限保留原配置类型并支持显式模式', () => {
  const {view} = createConfigView([
    field('PROXY_POOL_WAIT_TIMEOUT', '代理与网络', {type: 'int', value: 45}),
    field('SMS_MAX_PRICE', '接码平台', {type: 'str', value: ''}),
  ]);
  const waitMarkup = view.control(view.groups()['代理与网络'].find(item => item.key === 'PROXY_POOL_WAIT_TIMEOUT'));
  const priceMarkup = view.control(view.groups()['邮箱与验证码']?.find(item => item.key === 'SMS_MAX_PRICE') || field('SMS_MAX_PRICE', '接码平台', {type: 'str', value: ''}));
  assert.ok(waitMarkup.includes('持续等待'));
  assert.ok(waitMarkup.includes('限时等待'));
  assert.ok(priceMarkup.includes('不设上限'));
  assert.ok(priceMarkup.includes('设上限'));
  const composite = (mode, raw) => {
    const root = {querySelector(selector) {
      if (selector.includes('data-composite-mode')) return {value: mode};
      return {value: raw};
    }};
    return {value: mode, dataset: {}, closest(selector) {
      return selector === '[data-config-composite-key]' ? root : null;
    }};
  };
  assert.equal(view.read(composite('timed', '45'), {key: 'PROXY_POOL_WAIT_TIMEOUT', type: 'int'}), 45);
  assert.equal(view.read(composite('continuous', '45'), {key: 'PROXY_POOL_WAIT_TIMEOUT', type: 'int'}), 0);
  assert.equal(view.read(composite('limited', '0.25'), {key: 'SMS_MAX_PRICE', type: 'str'}), '0.25');
  assert.equal(view.read(composite('unlimited', '0.25'), {key: 'SMS_MAX_PRICE', type: 'str'}), '');
});

test('复合控件跨分类重绘保留限时空草稿，不伪造为零或不限', () => {
  const {view} = createConfigView([
    field('PROXY_POOL_WAIT_TIMEOUT', '代理与网络', {type: 'int', value: 45}),
    field('SMS_MAX_PRICE', '接码平台', {type: 'str', value: '0.25'}),
  ]);
  view.compositeModes.PROXY_POOL_WAIT_TIMEOUT = 'timed';
  view.compositeModes.SMS_MAX_PRICE = 'limited';
  view.setPending('PROXY_POOL_WAIT_TIMEOUT', null);
  view.setPending('SMS_MAX_PRICE', '');
  const waitMarkup = view.control(view.groups()['代理与网络'].find(item => item.key === 'PROXY_POOL_WAIT_TIMEOUT'));
  const priceMarkup = view.control(view.groups()['邮箱与验证码'].find(item => item.key === 'SMS_MAX_PRICE'));
  assert.match(waitMarkup, /option value="timed" selected/);
  assert.match(waitMarkup, /data-composite-seconds[^>]*value=""/);
  assert.match(priceMarkup, /option value="limited" selected/);
  assert.match(priceMarkup, /data-composite-value[^>]*value=""/);
  const compositeRoot = {
    querySelector(selector) {
      if (selector.includes('data-composite-mode')) return {value: 'timed'};
      return {value: ''};
    },
  };
  const emptySeconds = {
    value: '', type: 'number', dataset: {waitSecondsKey: 'PROXY_POOL_WAIT_TIMEOUT'},
    hasAttribute: () => false,
    closest(selector) {
      if (selector.includes('[data-wait-seconds-key]')) return this;
      if (selector === '[data-config-composite-key]') return compositeRoot;
      if (selector === '#tab-config') return {};
      return null;
    },
  };
  view.track({target: emptySeconds});
  assert.equal(view.pending.PROXY_POOL_WAIT_TIMEOUT, null);
});

test('隐藏的复合空草稿保存前仍校验，不发送零或不限', async () => {
  const {view, context} = createConfigView([
    field('PROXY_POOL_WAIT_TIMEOUT', '代理与网络', {type: 'int', value: 45}),
    field('SMS_MAX_PRICE', '接码平台', {type: 'str', value: '0.25'}),
  ]);
  view.compositeModes.PROXY_POOL_WAIT_TIMEOUT = 'timed';
  view.setPending('PROXY_POOL_WAIT_TIMEOUT', null);
  let called = false;
  context.api = async () => { called = true; return {reloaded: true}; };
  await view.save();
  assert.equal(called, false);
  assert.equal(view.errors.PROXY_POOL_WAIT_TIMEOUT, '请填写限时等待秒数，或切换为持续等待');
  assert.equal(view.pending.PROXY_POOL_WAIT_TIMEOUT, null);
});

test('iCloud forward_butler 才会让 Email Butler 作为依赖可见', () => {
  const fields = [
    field('EMAIL_SOURCE', '邮箱 / OTP', {value: 'icloud_hide'}),
    field('ICLOUD_HME_INBOX_MODE', '邮箱 / OTP', {value: 'forward_imap'}),
  ];
  const {view} = createConfigView(fields);
  assert.equal(view.emailVisible('Email Butler'), false);
  view.setPending('ICLOUD_HME_INBOX_MODE', 'forward_butler');
  assert.equal(view.emailVisible('Email Butler'), true);
  view.setPending('ICLOUD_HME_INBOX_MODE', 'sidecar');
  view.setPending('EMAIL_SOURCE', 'icloud_hide,email_butler');
  assert.equal(view.emailVisible('Email Butler'), true);
  view.setPending('EMAIL_SOURCE', 'icloud_hme');
  view.setPending('ICLOUD_HME_INBOX_MODE', 'forward_butler');
  assert.equal(view.emailVisible('Email Butler'), true);
});

test('仅新 Butler 来源时仍显示已启用的历史 HME 桥接配置', () => {
  const {view} = createConfigView([
    field('EMAIL_SOURCE', '邮箱 / OTP', {value: 'email_butler'}),
    field('ICLOUD_HME_BUTLER_BRIDGE_ENABLED', '邮箱 / OTP', {type: 'bool', value: false}),
  ]);
  assert.equal(view.emailVisible('iCloud 隐藏邮箱'), false);
  view.setPending('ICLOUD_HME_BUTLER_BRIDGE_ENABLED', true);
  assert.equal(view.emailVisible('iCloud 隐藏邮箱'), true);
  view.setPending('ICLOUD_HME_BUTLER_BRIDGE_ENABLED', false);
  assert.equal(view.emailVisible('iCloud 隐藏邮箱'), false);
});

test('历史 HME 桥接启用时配置页提示 Butler 管理入口', () => {
  const {view} = createConfigView([
    field('ICLOUD_HME_BUTLER_BRIDGE_ENABLED', '邮箱 / OTP', {type: 'bool', value: true}),
  ]);
  assert.match(view.hmeTools(), /Email Butler/);
  assert.doesNotMatch(view.hmeTools(), /btnTestICloudHMEV2|btnLoadICloudHMEAccountsV2/);
  view.setPending('ICLOUD_HME_BUTLER_BRIDGE_ENABLED', false);
  assert.match(view.hmeTools(), /btnTestICloudHMEV2/);
});

test('跨菜单草稿统一保存，失败时保留待保存值', async () => {
  const fields = [field('ROXY_API_BASE', 'RoxyBrowser'), field('TASK_CENTER_RETENTION_DAYS', '任务中心', {type: 'int', value: 30})];
  const {view, context} = createConfigView(fields);
  view.setPending('ROXY_API_BASE', 'http://127.0.0.1:5888');
  view.open('任务中心');
  view.setPending('TASK_CENTER_RETENTION_DAYS', 60);
  context.api = async () => { throw new Error('模拟保存失败'); };
  await view.save();
  assert.deepEqual(JSON.parse(JSON.stringify(view.pending)), {ROXY_API_BASE: 'http://127.0.0.1:5888', TASK_CENTER_RETENTION_DAYS: 60});
  let payload;
  context.api = async (_url, options) => { payload = JSON.parse(options.body); return {reloaded: true}; };
  await view.save();
  assert.deepEqual(payload.updates, {ROXY_API_BASE: 'http://127.0.0.1:5888', TASK_CENTER_RETENTION_DAYS: 60});
  assert.equal(Object.keys(view.pending).length, 0);
});

test('字段校验错误定位到投影菜单并保留草稿，成功保存后清除错误', async () => {
  const {view, context} = createConfigView([
    field('PLAN_CHECK_TIMEOUT', '代理与网络', {type: 'float', value: 30}),
  ]);
  view.setPending('PLAN_CHECK_TIMEOUT', 45);
  context.api = async () => {
    const error = new Error('校验失败');
    error.fields = {PLAN_CHECK_TIMEOUT: '套餐查询超时必须在允许范围内'};
    throw error;
  };
  await view.save();
  assert.equal(view.errors.PLAN_CHECK_TIMEOUT, '套餐查询超时必须在允许范围内');
  assert.equal(view.state().menu, '注册与账号');
  assert.equal(view.pending.PLAN_CHECK_TIMEOUT, 45);
  context.api = async () => ({reloaded: true});
  await view.save();
  assert.equal(Object.keys(view.errors).length, 0);
  assert.equal(Object.keys(view.pending).length, 0);
});

test('字段校验失败提示检查标记配置，普通错误仍提示服务状态', async () => {
  const {view, context} = createConfigView([
    field('PLAN_CHECK_TIMEOUT', '代理与网络', {type: 'float', value: 30}),
  ]);
  view.setPending('PLAN_CHECK_TIMEOUT', 45);
  context.api = async () => {
    const error = new Error('校验失败');
    error.fields = {PLAN_CHECK_TIMEOUT: '套餐查询超时必须在允许范围内'};
    throw error;
  };
  await view.save();
  assert.equal(view.ui.saveCopy.textContent, '请检查标记的配置项');
  assert.equal(view.ui.saveHint.textContent, '请检查标记的配置项后再保存');

  context.api = async () => { throw new Error('服务不可用'); };
  await view.save();
  assert.equal(view.ui.saveCopy.textContent, '保存失败，请重试');
  assert.equal(view.ui.saveHint.textContent, '请检查网络或服务状态后重试');
});

test('任意配置编辑清除本轮服务端错误和页面错误节点，不重绘配置区', () => {
  const {view, domErrors} = createConfigView([
    field('REGISTER_NAME', '注册主链路', {value: '旧值'}),
  ]);
  view.errors.REGISTER_NAME = '旧错误';
  view.errors.OTHER_FIELD = '另一个错误';
  domErrors.push({removed: false, remove() { this.removed = true; }});
  domErrors.push({removed: false, remove() { this.removed = true; }});
  const row = {querySelector() { return null; }};
  const input = {
    value: '新值', type: 'text', dataset: {key: 'REGISTER_NAME'},
    closest(selector) {
      if (selector.includes('[data-key]')) return this;
      if (selector === '#tab-config') return {};
      if (selector === '[data-config-composite-key]') return null;
      if (selector === '[data-multi-picker]') return null;
      return row;
    },
    hasAttribute() { return false; },
  };
  view.track({target: input});
  assert.equal(Object.keys(view.errors).length, 0);
  assert.deepEqual(domErrors.map(item => item.removed), [true, true]);
  assert.equal(view.pending.REGISTER_NAME, '新值');
});

test('邮箱子地址通过通用配置渲染器保留多选顺序和可调整额度', () => {
  const fields = [
    field('EMAIL_DERIVATION_SOURCES', '邮箱 / OTP', {value: 'icloud_hide,outlook', csv_options: ['icloud_hide', 'outlook'], options: [
      {value: 'icloud_hide', label: 'iCloud 隐藏邮箱'}, {value: 'outlook', label: 'Outlook'},
    ]}),
    field('EMAIL_DERIVATION_MAX_CHILDREN', '邮箱 / OTP', {type: 'int', value: 3, range: {min: 1, max: 10000}}),
    field('EMAIL_DERIVATION_ENABLED', '邮箱 / OTP', {type: 'bool', value: false}),
  ];
  const {view} = createConfigView(fields);
  assert.equal(view.emailVisible('邮箱子地址'), true);
  const markup = view.control(fields[0]);
  assert.ok(markup.includes('data-multi-picker="EMAIL_DERIVATION_SOURCES"'));
  assert.ok(markup.includes('value="icloud_hide,outlook"'));
  const readValue = view.read({value: 'outlook,icloud_hide', dataset: {}, closest() { return true; }}, fields[0]);
  assert.equal(readValue, 'outlook,icloud_hide');
  assert.ok(view.control(fields[1]).includes('min="1" max="10000" step="1" value="3"'));
  view.search('EMAIL_DERIVATION_MAX_CHILDREN');
  assert.equal(view.state().email, '邮箱子地址');
  assert.equal(view.state().menu, '邮箱与验证码');
});
