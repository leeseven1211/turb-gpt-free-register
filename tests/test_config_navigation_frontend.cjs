const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../webui/static/js/modern/config.js'), 'utf8');

function createConfigView(fields = []) {
  const storage = new Map();
  const nodes = new Map();
  const root = {addEventListener() {}};
  const context = {
    CONFIG: fields,
    document: {
      getElementById(id) { return nodes.get(id) || null; },
      querySelector() { return null; },
      querySelectorAll() { return []; },
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
      destination: setConfigDestinationV2, open: openConfigGroup,
      render: renderConfigSectionV2, renderDomain: renderConfigDomainSectionV2,
      bind: bindConfigLayoutV2, save: saveConfigUpdates,
      pending: CONFIG_PENDING_UPDATES, setPending: setPendingConfigValue,
      proxySection: key => proxyConfigSectionForKey(key)[0],
      search(query, menu) { CONFIG_NAV_QUERY_V2 = query; selectConfigSearchDestinationV2(menu); },
      fields(value) { CONFIG = value; },
      state() { return {
        menu: CONFIG_ACTIVE_GROUP_V2, domains: {...CONFIG_ACTIVE_DOMAIN_V2},
        email: CONFIG_EMAIL_ACTIVE_SECTION_V2, proxy: CONFIG_PROXY_ACTIVE_SECTION_V2,
        sms: CONFIG_SMS_ACTIVE_SECTION_V2, codex: CONFIG_CODEX_ACTIVE_SECTION_V2,
      }; },
    };
  `, context);
  return {view: context.view, context, storage, nodes};
}

const field = (key, group, extra = {}) => ({key, group, label: key, type: 'str', value: '', ...extra});

test('所有原始配置领域只归入一个菜单，重复展示项不再重复计数', () => {
  const domains = ['通用配置', '注册主链路', '账号补全', '注册调试', '邮箱 / OTP', '接码平台',
    '代理与网络', 'RoxyBrowser', '浏览器画像', '人工节奏', 'Codex', '提链', 'WebUI 授权', '定时任务', '任务中心'];
  const fields = domains.map((domain, index) => field(`KEY_${index}`, domain));
  const {view} = createConfigView([...fields, {...fields[0]}]);
  const groups = view.groups();
  assert.equal(Object.keys(groups).length, 9);
  assert.equal(Object.values(groups).flat().length, fields.length);
  assert.deepEqual(Array.from(view.names()), Object.keys(groups));
  assert.deepEqual(Array.from(groups['浏览器设置'], item => item.group), ['RoxyBrowser', '浏览器画像', '人工节奏']);
  assert.deepEqual(Array.from(groups['系统设置'], item => item.group), ['通用配置', 'WebUI 授权', '定时任务', '任务中心']);
});

test('旧菜单直达会迁移主菜单并定位原始分类，保留全部未保存值', () => {
  const fields = [field('ROXY_API_BASE', 'RoxyBrowser'), field('HUMANIZE_DELAY_FACTOR', '人工节奏', {type: 'float', value: 1})];
  const {view, storage} = createConfigView(fields);
  view.setPending('ROXY_API_BASE', 'http://127.0.0.1:5888');
  view.open('人工节奏');
  assert.equal(view.state().menu, '浏览器设置');
  assert.equal(view.state().domains['浏览器设置'], '人工节奏');
  assert.equal(storage.get('gpt_console_config_group'), '人工节奏');
  view.open('RoxyBrowser');
  const markup = view.render('浏览器设置', view.groups()['浏览器设置']);
  assert.ok(markup.includes('data-config-domain-v2="人工节奏"'));
  assert.ok(markup.includes('id="cfg-浏览器设置"'));
  assert.ok(markup.includes('value="http://127.0.0.1:5888"'));
  assert.equal(view.pending.ROXY_API_BASE, 'http://127.0.0.1:5888');
  view.destination('执行方式');
  assert.equal(view.state().menu, '注册设置');
  assert.equal(view.state().domains['注册设置'], '注册主链路');
  view.destination('网站配置');
  assert.equal(view.state().menu, '系统设置');
  assert.equal(view.state().domains['系统设置'], 'WebUI 授权');
});

test('旧 localStorage 领域名在加载时恢复到新主菜单和对应分类', () => {
  const fields = [field('WEBUI_AUTH_CODE', 'WebUI 授权'), field('AT_AUTO_REFRESH_ENABLED', '定时任务', {type: 'bool'})];
  const {view, nodes, storage, context} = createConfigView(fields);
  storage.set('gpt_console_config_group', '定时任务');
  nodes.set('configNavV2', {innerHTML: ''});
  nodes.set('configSectionsV2', {innerHTML: ''});
  vm.runInContext('renderConfigLayoutV2()', context);
  assert.equal(view.state().menu, '系统设置');
  assert.equal(view.state().domains['系统设置'], '定时任务');
  assert.ok(nodes.get('configSectionsV2').innerHTML.includes('ChatGPT AT 自动刷新'));
});

test('搜索配置键或领域会打开合并分类和邮箱、代理、接码、Codex 的具体子标签', () => {
  const fields = [
    field('ROXY_API_BASE', 'RoxyBrowser'), field('TASK_CENTER_RETENTION_DAYS', '任务中心'),
    field('EMAIL_BUTLER_API_BASE', '邮箱 / OTP'), field('ICLOUD_HME_API_BASE', '邮箱 / OTP'),
    field('PROXY_1024_API_URL', '代理与网络'), field('PLAN_CHECK_TIMEOUT', '代理与网络'),
    field('SMS_API_KEY', '接码平台'), field('L_API_BASE', '接码平台'),
    field('CODEX_AUTH_URL_SOURCE', 'Codex'), field('CPA_MANAGEMENT_URL', 'Codex'),
  ];
  const {view} = createConfigView(fields);
  view.search('TASK_CENTER_RETENTION_DAYS');
  assert.equal(view.state().menu, '系统设置');
  assert.equal(view.state().domains['系统设置'], '任务中心');
  for (const [query, property, expected] of [
    ['ICLOUD_HME_API_BASE', 'email', 'iCloud 隐藏邮箱'],
    ['Email Butler', 'email', 'Email Butler'],
    ['PROXY_1024_API_URL', 'proxy', '代理提供商'],
    ['PLAN_CHECK_TIMEOUT', 'proxy', '账号动作线路'],
    ['L_API_BASE', 'sms', 'L 接码'],
    ['CPA_MANAGEMENT_URL', 'codex', 'CPA配置'],
  ]) {
    view.search(query);
    assert.equal(view.state()[property], expected);
    const groups = view.groups();
    assert.ok(view.render(view.state().menu, groups[view.state().menu]).includes(query === 'Email Butler' ? 'EMAIL_BUTLER_API_BASE' : query));
  }
});

test('完整配置键优先于其他字段键和帮助文案中的包含匹配', () => {
  const fields = [
    field('ACCOUNT_PLAN_CHECK_PROXY_MODE', '代理与网络'),
    field('ACCOUNT_ACTION_PROXY_RETRIES', '代理与网络'),
    field('PLAN_CHECK_PROXY_ALLOW_REUSE', '代理与网络'),
    field('PLAN_CHECK_PROXY_MODE', '代理与网络'),
    field('PLAN_CHECK_PROXY', '代理与网络'),
    field('ACCOUNT_ACTION_PROXY', '代理与网络'),
  ];
  const {view} = createConfigView(fields);
  for (const key of ['PLAN_CHECK_PROXY_MODE', 'PLAN_CHECK_PROXY', 'ACCOUNT_ACTION_PROXY']) {
    view.search(key.toLowerCase());
    assert.equal(view.state().proxy, '静态代理池');
    const markup = view.render('代理与网络', view.groups()['代理与网络']);
    assert.ok(markup.includes(`data-key="${key}"`));
  }
});

test('定时任务同页展示各服务完整策略，查询套餐和注册重试归属对应线路', () => {
  const fields = [
    field('EMAIL_BUTLER_RISK_SCAN_ENABLED', '定时任务', {type: 'bool'}),
    field('AT_AUTO_REFRESH_ENABLED', '定时任务', {type: 'bool'}),
    field('CODEX_TOKEN_AUTO_REFRESH_ENABLED', '定时任务', {type: 'bool'}),
    field('CODEX_TOKEN_REFRESH_BEFORE_HOURS', '定时任务', {type: 'int', value: 24}),
  ];
  const {view} = createConfigView(fields);
  const markup = view.render('系统设置', view.groups()['系统设置']);
  for (const item of fields) assert.equal((markup.match(new RegExp(`data-key="${item.key}"`, 'g')) || []).length, 1);
  for (const title of ['Email Butler 风险扫描', 'ChatGPT AT 自动刷新', 'Codex Token 自动刷新']) assert.ok(markup.includes(title));
  for (const key of ['PLAN_CHECK_TIMEOUT', 'PLAN_CHECK_MAX_ATTEMPTS', 'PLAN_CHECK_RETRY_DELAY',
    'PLAN_CHECK_REGISTRATION_RECHECK_DELAY', 'PLAN_CHECK_MIN_INTERVAL', 'PLAN_CHECK_JITTER',
    'ACCOUNT_ACTION_PROXY_RETRIES', 'ACCOUNT_ACTION_PROXY_RETRY_DELAY']) assert.equal(view.proxySection(key), '账号动作线路');
  for (const key of ['REGISTRATION_PROXY_MODE', 'REGISTRATION_PROXY_RETRIES', 'REGISTRATION_PROXY_RETRY_DELAY']) assert.equal(view.proxySection(key), '注册线路');
  for (const key of ['PLAN_CHECK_PROXY_MODE', 'PLAN_CHECK_PROXY', 'ACCOUNT_ACTION_PROXY_MODE', 'ACCOUNT_ACTION_PROXY']) assert.equal(view.proxySection(key), '静态代理池');
});

test('账号动作按功能归组，套餐的代理、国家、重试和节奏完整集中且每项只展示一次', () => {
  const featureKeys = {
    '查询套餐': [
      'ACCOUNT_PLAN_CHECK_PROXY_MODE', 'PLAN_CHECK_PROXY_ALLOW_REUSE', 'PLAN_CHECK_PROXY_REUSE_LIMIT',
      'PLAN_CHECK_COUNTRIES', 'PLAN_CHECK_COUNTRY_WAIT_TIMEOUT', 'PLAN_CHECK_TIMEOUT',
      'PLAN_CHECK_MAX_ATTEMPTS', 'PLAN_CHECK_RETRY_DELAY', 'PLAN_CHECK_MIN_INTERVAL',
      'PLAN_CHECK_JITTER', 'PLAN_CHECK_REGISTRATION_RECHECK_DELAY',
    ],
    '查活与刷新 AT': [
      'ACCOUNT_LIVE_CHECK_PROXY_MODE', 'ACCOUNT_REFRESH_AT_PROXY_MODE',
      'ACCOUNT_ACTION_PROXY_RETRIES', 'ACCOUNT_ACTION_PROXY_RETRY_DELAY',
    ],
    '补密码': ['ACCOUNT_PASSWORD_PROXY_MODE'],
    '补 2FA': ['ACCOUNT_2FA_PROXY_MODE'],
    '邮箱换绑': ['ACCOUNT_EMAIL_CHANGE_PROXY_MODE'],
    'Codex OAuth': ['ACCOUNT_CODEX_PROXY_MODE'],
  };
  const fields = Object.values(featureKeys).flat().reverse().map(key => field(key, '代理与网络',
    key === 'PLAN_CHECK_PROXY_ALLOW_REUSE' ? {type: 'bool', value: true}
      : key === 'PLAN_CHECK_COUNTRIES' ? {type: 'list_str_multiline', value: ['JP'], country_codes: ['JP', 'US']}
        : {}));
  const {view} = createConfigView(fields);
  view.search('PLAN_CHECK_TIMEOUT');
  const markup = view.render('代理与网络', view.groups()['代理与网络']);
  const sections = new Map(Array.from(markup.matchAll(/<section[^>]*data-config-proxy-feature="([^"]+)"[^>]*>([\s\S]*?)<\/section>/g),
    match => [match[1], match[2]]));
  assert.deepEqual(Array.from(sections.keys()), Object.keys(featureKeys));
  for (const [title, keys] of Object.entries(featureKeys)) {
    const section = sections.get(title);
    assert.deepEqual(Array.from(section.matchAll(/data-key="([^"]+)"/g), match => match[1]), keys);
    for (const key of keys) {
      assert.equal(view.proxySection(key), '账号动作线路');
      assert.equal((markup.match(new RegExp(`data-key="${key}"`, 'g')) || []).length, 1);
    }
  }
  const plan = sections.get('查询套餐');
  assert.equal((plan.match(/data-key=/g) || []).length, 11);
  assert.match(plan, /type="checkbox" role="switch" data-key="PLAN_CHECK_PROXY_ALLOW_REUSE" checked/);
  assert.ok(!markup.includes('class="config-switches-v2"'));
  assert.ok(!plan.includes('data-key="ACCOUNT_ACTION_PROXY_RETRIES"'));
  assert.ok(!plan.includes('data-key="ACCOUNT_ACTION_PROXY_RETRY_DELAY"'));
});

test('切换代理分类和账号功能保留未保存国家、开关和重试值，并统一提交原配置键', async () => {
  const fields = [
    field('PLAN_CHECK_PROXY_ALLOW_REUSE', '代理与网络', {type: 'bool', value: true}),
    field('PLAN_CHECK_COUNTRIES', '代理与网络', {type: 'list_str_multiline', value: ['JP'], country_codes: ['JP', 'US', 'DE']}),
    field('ACCOUNT_ACTION_PROXY_RETRIES', '代理与网络', {type: 'int', value: 2}),
    field('PROXY_POOL_COUNTRIES', '代理与网络', {type: 'list_str_multiline', value: ['JP'], country_codes: ['JP', 'US', 'DE']}),
    field('PLAN_CHECK_PROXY', '代理与网络'),
  ];
  const {view, context} = createConfigView(fields);
  view.search('PLAN_CHECK_COUNTRIES');
  view.setPending('PLAN_CHECK_COUNTRIES', ['DE', 'US']);
  view.setPending('PLAN_CHECK_PROXY_ALLOW_REUSE', false);
  view.search('ACCOUNT_ACTION_PROXY_RETRIES');
  view.setPending('ACCOUNT_ACTION_PROXY_RETRIES', 3);
  view.search('PROXY_POOL_COUNTRIES');
  assert.equal(view.state().proxy, '独立代理池');
  view.setPending('PROXY_POOL_COUNTRIES', []);
  const poolMarkup = view.render('代理与网络', view.groups()['代理与网络']);
  assert.ok(poolMarkup.includes('data-key="PROXY_POOL_COUNTRIES" value=""'));
  assert.ok(poolMarkup.includes('未选择额外预热国家'));
  view.search('PLAN_CHECK_PROXY');
  assert.equal(view.state().proxy, '静态代理池');
  view.render('代理与网络', view.groups()['代理与网络']);
  view.search('PLAN_CHECK_COUNTRIES');
  assert.equal(view.state().proxy, '账号动作线路');
  const actionMarkup = view.render('代理与网络', view.groups()['代理与网络']);
  assert.ok(actionMarkup.includes('data-key="PLAN_CHECK_COUNTRIES" value="DE,US"'));
  assert.match(actionMarkup, /data-key="ACCOUNT_ACTION_PROXY_RETRIES"[^>]*value="3"/);
  assert.match(actionMarkup, /data-key="PLAN_CHECK_PROXY_ALLOW_REUSE" aria-label=/);
  assert.ok(!/data-key="PLAN_CHECK_PROXY_ALLOW_REUSE" checked/.test(actionMarkup));
  const expected = {
    PLAN_CHECK_COUNTRIES: ['DE', 'US'], PLAN_CHECK_PROXY_ALLOW_REUSE: false,
    ACCOUNT_ACTION_PROXY_RETRIES: 3, PROXY_POOL_COUNTRIES: [],
  };
  assert.deepEqual(JSON.parse(JSON.stringify(view.pending)), expected);
  context.api = async () => { throw new Error('模拟保存失败'); };
  await view.save();
  assert.deepEqual(JSON.parse(JSON.stringify(view.pending)), expected);
  let payload;
  context.api = async (_url, options) => { payload = JSON.parse(options.body); return {reloaded: true}; };
  await view.save();
  assert.deepEqual(payload.updates, expected);
  assert.equal(Object.keys(view.pending).length, 0);
});

test('跨菜单修改统一保存，失败时完整保留待保存值', async () => {
  const fields = [field('ROXY_API_BASE', 'RoxyBrowser'), field('TASK_CENTER_RETENTION_DAYS', '任务中心', {type: 'int', value: 30})];
  const {view, context} = createConfigView(fields);
  view.setPending('ROXY_API_BASE', 'http://127.0.0.1:5888');
  view.open('任务中心');
  view.setPending('TASK_CENTER_RETENTION_DAYS', 60);
  context.api = async () => { throw new Error('模拟保存失败'); };
  await view.save();
  assert.equal(Object.keys(view.pending).length, 2);
  let payload;
  context.api = async (_url, options) => { payload = JSON.parse(options.body); return {reloaded: true}; };
  await view.save();
  assert.deepEqual(payload.updates, {ROXY_API_BASE: 'http://127.0.0.1:5888', TASK_CENTER_RETENTION_DAYS: 60});
  assert.equal(Object.keys(view.pending).length, 0);
});
