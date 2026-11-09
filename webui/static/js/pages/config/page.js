// ---------- 配置 ----------
let CONFIG_EMAIL_ACTIVE_SECTION_V2 = '通用邮箱 / OTP';
let CONFIG_SMS_ACTIVE_SECTION_V2 = '通用接码';
let CONFIG_CODEX_ACTIVE_SECTION_V2 = '基础配置';
let CONFIG_PROXY_ACTIVE_SECTION_V2 = '任务用池';
let CONFIG_EXTRACT_LINK_ACTIVE_SECTION_V2 = '通用配置';
let CONFIG_ACTIVE_GROUP_V2 = '';
let CONFIG_NAV_QUERY_V2 = '';
const CONFIG_PENDING_UPDATES = {};
const CONFIG_FIELD_ERRORS_V2 = {};
const CONFIG_COMPOSITE_MODES_V2 = {};
const CONFIG_ACTIVE_DOMAIN_V2 = {};
const CONFIG_MULTI_PICKER_FIELDS_V2 = new Map();
let CONFIG_HUANGUANG_XXSYUN_QUOTA_REQUEST_V2 = 0;
const CONFIG_HUANGUANG_XXSYUN_QUOTA_V2 = {loading: false, text: ''};
let CONFIG_XXSYUN_PAYMENT_BALANCE_REQUEST_V2 = 0;
const CONFIG_XXSYUN_PAYMENT_BALANCE_V2 = {loading: false, text: ''};
const CONFIG_SENTINEL_MAINTENANCE_V2 = {
  snapshot: null, loading: false, posting: false, visible: false,
  request: 0, timer: null, observer: null, error: '', retryAction: 'status',
};
const CONFIG_CONCURRENCY_V2 = {
  snapshot: null, preview: null, error: '', loading: false,
  request: 0, visible: false, timer: null, observer: null,
};
const CONFIG_HUANGUANG_CDK_QUOTAS_V2 = {
  extraction: {key: 'EXTRACT_LINK_HUANGUANG_CDK', label: '幻光提链 CDK', request: 0, inflight: null, loading: false, text: ''},
  payment: {key: 'EXTRACT_LINK_HUANGUANG_PAYMENT_CDK', label: '幻光支付扫码 CDK', request: 0, inflight: null, loading: false, text: ''},
};
// 菜单集中定义；schema 的 group 继续表示配置所属领域。导航菜单是页面导航契约，
// 底层领域仍保留，便于旧入口、搜索和兼容快照继续工作。
const CONFIG_MENU_DOMAINS_V2 = {
  '注册与账号': ['注册主链路', '账号补全', '注册与账号', '查活', '刷新 AT', '补密码', '补 2FA', '邮箱换绑'],
  '代理与网络': ['代理与网络'],
  '邮箱与验证码': ['邮箱 / OTP', '接码平台'],
  '浏览器': ['RoxyBrowser', '浏览器画像', '人工节奏'],
  '服务集成': ['Codex'],
  '提链': ['提链'],
  '系统与维护': ['并发控制', '通用配置', 'WebUI 授权', '定时任务', '任务中心', '注册调试'],
};
const CONFIG_DOMAIN_ALIASES_V2 = {
  '注册设置': '注册主链路',
  '账号设置': '账号补全',
  '注册与账号': '注册主链路',
  '执行方式': '注册主链路',
  '邮箱 / OTP': '邮箱 / OTP',
  '接码平台': '接码平台',
  '邮箱': '邮箱 / OTP',
  '浏览器设置': 'RoxyBrowser',
  'Codex': 'Codex',
  '提链': '提链',
  '系统设置': '通用配置',
  '网站配置': 'WebUI 授权',
};
const CONFIG_NAV_CATEGORY_ORDER_V2 = ['业务流程', '资源与服务', '系统'];
const CONFIG_NAV_CATEGORY_RULES_V2 = {
  '业务流程': new Set(['注册与账号', '邮箱与验证码']),
  '资源与服务': new Set(['代理与网络', '浏览器', '服务集成', '提链']),
  '系统': new Set(['系统与维护']),
};
const CONFIG_PROXY_FEATURES_V2 = [
  ['查询套餐', [
    'ACCOUNT_PLAN_CHECK_PROXY_MODE', 'PLAN_CHECK_PROXY_ALLOW_REUSE', 'PLAN_CHECK_PROXY_REUSE_LIMIT',
    'PLAN_CHECK_PAYMENT_METHODS_ENABLED', 'PLAN_CHECK_COUNTRIES', 'PLAN_CHECK_COUNTRY_WAIT_TIMEOUT', 'PLAN_CHECK_TIMEOUT',
    'PLAN_CHECK_MAX_ATTEMPTS', 'PLAN_CHECK_RETRY_DELAY', 'PLAN_CHECK_MIN_INTERVAL',
    'PLAN_CHECK_JITTER', 'PLAN_CHECK_REGISTRATION_RECHECK_DELAY',
  ]],
  ['查活与刷新 AT', [
    'ACCOUNT_LIVE_CHECK_PROXY_MODE', 'ACCOUNT_REFRESH_AT_PROXY_MODE',
    'ACCOUNT_ACTION_PROXY_RETRIES', 'ACCOUNT_ACTION_PROXY_RETRY_DELAY',
  ]],
  ['补密码', ['ACCOUNT_PASSWORD_PROXY_MODE']],
  ['补 2FA', ['ACCOUNT_2FA_PROXY_MODE']],
  ['邮箱换绑', ['ACCOUNT_EMAIL_CHANGE_PROXY_MODE']],
  ['Codex OAuth', ['ACCOUNT_CODEX_PROXY_MODE']],
];
const CONFIG_PLAN_BUSINESS_KEYS_V2 = new Set([
  'ACCOUNT_PLAN_CHECK_DRIVER',
  'PLAN_CHECK_PAYMENT_METHODS_ENABLED', 'PLAN_CHECK_COUNTRIES', 'PLAN_CHECK_COUNTRY_WAIT_TIMEOUT',
  'PLAN_CHECK_TIMEOUT', 'PLAN_CHECK_MAX_ATTEMPTS', 'PLAN_CHECK_RETRY_DELAY',
  'PLAN_CHECK_REGISTRATION_RECHECK_DELAY', 'PLAN_CHECK_MIN_INTERVAL', 'PLAN_CHECK_JITTER',
]);
const CONFIG_ACCOUNT_ACTION_SECTIONS_V2 = {
  '查活': [
    ['查活策略', ['ACCOUNT_LIVE_CHECK_DRIVER', 'ACCOUNT_LIVE_CHECK_BROWSER_ENABLED']],
  ],
  '刷新 AT': [
    ['刷新 AT 策略', [
      'ACCOUNT_AT_REFRESH_DRIVER', 'ACCOUNT_AT_REFRESH_COUNTRY', 'OPENAI_PROTOCOL_VERSION',
      'ACCOUNT_AT_REFRESH_NETWORK_RETRIES', 'ACCOUNT_AT_REFRESH_NETWORK_TIMEOUT_SECONDS',
      'LIVE_CHECK_ROXY_FALLBACK_ENABLED', 'ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED',
    ]],
    ['协议认证策略', ['ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK', 'ACCOUNT_AUTH_PROFILE_MODE']],
    ['自动刷新', [
      'AT_AUTO_REFRESH_ENABLED', 'AT_REFRESH_SCAN_INTERVAL_SECONDS', 'AT_REFRESH_BEFORE_HOURS',
      'AT_REFRESH_INITIAL_DELAY_SECONDS', 'AT_REFRESH_MAX_PER_CYCLE',
    ]],
  ],
  '补密码': [
    ['密码补全策略', ['ACCOUNT_PASSWORD_DRIVER', 'ACCOUNT_PASSWORD_RESET_ENABLED']],
  ],
  '补 2FA': [
    ['2FA 补全策略', [
      'ACCOUNT_2FA_DRIVER', 'ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED', 'ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED',
    ]],
    ['2FA 重认证参数', ['TWOFA_REAUTH_MAX_ATTEMPTS', 'TWOFA_REAUTH_RETRY_DELAY']],
  ],
  '邮箱换绑': [
    ['邮箱换绑策略', ['ACCOUNT_EMAIL_CHANGE_ENABLED', 'ACCOUNT_EMAIL_CHANGE_MIN_ACCOUNT_AGE_HOURS']],
  ],
};
const CONFIG_FIELD_UI_GROUP_OVERRIDES_V2 = new Map([
  ['REGISTRATION_PROXY_RETRIES', '注册主链路'],
  ['REGISTRATION_PROXY_RETRY_DELAY', '注册主链路'],
  ['ACCOUNT_ACTION_PROXY_RETRIES', '账号补全'],
  ['ACCOUNT_ACTION_PROXY_RETRY_DELAY', '账号补全'],
  ...Object.entries(CONFIG_ACCOUNT_ACTION_SECTIONS_V2).flatMap(([domain, sections]) =>
    sections.flatMap(([, keys]) => keys.map(key => [key, domain]))),
]);

function configFieldUiGroupV2(field) {
  if (CONFIG_PLAN_BUSINESS_KEYS_V2.has(field.key)) return '注册与账号';
  return CONFIG_FIELD_UI_GROUP_OVERRIDES_V2.get(field.key) || field.group || '其他';
}

function configMenuGroupV2(name) {
  if (Object.prototype.hasOwnProperty.call(CONFIG_MENU_DOMAINS_V2, name)) return name;
  const domain = CONFIG_DOMAIN_ALIASES_V2[name] || name || '其他';
  return Object.keys(CONFIG_MENU_DOMAINS_V2).find(menu => CONFIG_MENU_DOMAINS_V2[menu].includes(domain)) || domain;
}

function configDomainGroupsV2(fields) {
  const groups = {};
  (fields || []).forEach(field => {
    const domain = field.group || '其他';
    (groups[domain] = groups[domain] || []).push(field);
  });
  return groups;
}

function configMenuDomainNamesV2(menu, fields) {
  const domains = Object.keys(configDomainGroupsV2(fields));
  const preferred = CONFIG_MENU_DOMAINS_V2[menu] || [];
  return preferred.filter(domain => domains.includes(domain)).concat(domains.filter(domain => !preferred.includes(domain)));
}

function setConfigDestinationV2(name) {
  if (Object.prototype.hasOwnProperty.call(CONFIG_MENU_DOMAINS_V2, name)) {
    CONFIG_ACTIVE_GROUP_V2 = name;
    return name;
  }
  const domain = CONFIG_DOMAIN_ALIASES_V2[name] || name;
  const menu = configMenuGroupV2(domain);
  CONFIG_ACTIVE_GROUP_V2 = menu;
  if ((CONFIG_MENU_DOMAINS_V2[menu] || []).includes(domain)) CONFIG_ACTIVE_DOMAIN_V2[menu] = domain;
  return menu;
}

function rememberConfigDestinationV2() {
  localStorage.setItem('gpt_console_config_group', CONFIG_ACTIVE_DOMAIN_V2[CONFIG_ACTIVE_GROUP_V2] || CONFIG_ACTIVE_GROUP_V2);
}

function configFieldValueV2(key, fallback = '') {
  const field = (CONFIG || []).find(item => item.key === key);
  if (!field) return fallback;
  const value = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key)
    ? CONFIG_PENDING_UPDATES[key] : field.value;
  return value === null || value === undefined || value === '' ? fallback : value;
}

function configValuesEqual(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    return JSON.stringify(Array.isArray(a) ? a : []) === JSON.stringify(Array.isArray(b) ? b : []);
  }
  if (typeof a === 'boolean' || typeof b === 'boolean') return Boolean(a) === Boolean(b);
  if (typeof a === 'number' || typeof b === 'number') return Number(a) === Number(b);
  return String(a ?? '') === String(b ?? '');
}

function setPendingConfigValue(key, value, options = {}) {
  resetHuanguangQuotaForKeyV2(key);
  const field = CONFIG.find(item => item.key === key);
  if (!options.force && field && configValuesEqual(value, field.value)) delete CONFIG_PENDING_UPDATES[key];
  else CONFIG_PENDING_UPDATES[key] = value;
}

function configPendingCount() {
  return Object.keys(CONFIG_PENDING_UPDATES).length;
}

function renderConfigSaveActions() {
  const count = configPendingCount();
  return `
    <div class="config-section-v2-actions">
      <div class="config-save-state ${count ? 'is-dirty' : 'is-saved'}" data-config-save-state role="status" aria-live="polite">
        <span class="config-save-dot" aria-hidden="true"></span>
        <span data-config-save-copy>${count ? `${count} 项更改未保存` : '所有更改已保存'}</span>
      </div>
      <button type="button" class="btn primary" data-save-config-v2${count ? '' : ' disabled'}>${count ? '保存更改' : '已保存'}</button>
    </div>
  `;
}

function updateConfigSaveUi(mode = 'idle') {
  const count = configPendingCount();
  const saveBar = document.getElementById('configSaveBarV2');
  if (saveBar) saveBar.hidden = count === 0;
  let copy = count ? `${count} 项更改未保存` : '所有更改已保存';
  if (mode === 'saving') copy = `正在保存 ${count} 项更改…`;
  if (mode === 'validation_error') copy = '请检查标记的配置项';
  if (mode === 'error') copy = '保存失败，请重试';
  document.querySelectorAll('#tab-config [data-config-save-state]').forEach(state => {
    state.classList.toggle('is-saved', mode === 'idle' && count === 0);
    state.classList.toggle('is-dirty', mode === 'idle' && count > 0);
    state.classList.toggle('is-saving', mode === 'saving');
    state.classList.toggle('is-error', mode === 'error' || mode === 'validation_error');
    const copyEl = state.querySelector('[data-config-save-copy]');
    if (copyEl) copyEl.textContent = copy;
  });
  document.querySelectorAll('#tab-config [data-save-config-v2]').forEach(btn => {
    btn.disabled = mode === 'saving' || count === 0;
    btn.textContent = mode === 'saving' ? '保存中…' : (count ? '保存更改' : '已保存');
  });
  const badge = document.getElementById('configDirtyBadge');
  if (badge) {
    badge.hidden = count === 0;
    badge.textContent = count > 99 ? '99+' : String(count);
    badge.setAttribute('aria-label', `${count} 项配置更改未保存`);
  }
  const hint = document.querySelector('#configSaveBarV2 [data-config-save-hint]');
  if (hint) {
    hint.textContent = mode === 'saving'
      ? '正在将更改写入运行配置…'
      : mode === 'validation_error'
        ? '请检查标记的配置项后再保存'
        : mode === 'error'
          ? '请检查网络或服务状态后重试'
          : count
            ? '修改只在点击保存后生效'
            : '修改后点击保存才会生效';
  }
  document.querySelectorAll('#tab-config [data-reset-config-v2]').forEach(btn => {
    btn.disabled = mode === 'saving' || count === 0;
  });
  document.querySelectorAll('#configNavV2 [data-config-dirty]').forEach(dot => {
    const button = dot.closest('[data-config-nav]');
    const keys = String(button?.dataset.configKeys || '').split(',').filter(Boolean);
    const dirty = keys.some(key => Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key));
    dot.hidden = !dirty;
  });
}

function configGroups() {
  const groups = {};
  const seen = new Set();
  CONFIG.forEach(f => {
    if (f.hidden) return;
    if (seen.has(f.key)) return;
    seen.add(f.key);
    const isPlanBusiness = CONFIG_PLAN_BUSINESS_KEYS_V2.has(f.key);
    const uiGroup = configFieldUiGroupV2(f);
    const rawGroup = uiGroup;
    const group = configMenuGroupV2(rawGroup);
    // 只给页面投影改 group，原始 CONFIG 元数据和保存键保持不变。
    const uiField = isPlanBusiness || uiGroup !== f.group ? {...f, group: uiGroup, _configOriginalGroup: f.group} : f;
    (groups[group] = groups[group] || []).push(uiField);
  });
  return groups;
}

// 选项、范围和标签由 /api/config 的统一 schema 提供。前端只保留动态提链
// 服务的运行时补充，不再为每个 config key 维护第二份选项表。
function configSchemaOptions(f) {
  if (!f || !Array.isArray(f.options)) return [];
  return f.options.map(item => {
    if (typeof item === 'string') return { value: item, label: item };
    if (!item || typeof item !== 'object' || item.value === null || item.value === undefined) return null;
    const value = String(item.value).trim();
    return { value, label: String(item.label ?? value), disabled: item.disabled === true, reason: String(item.reason || '') };
  }).filter(Boolean);
}
function configSchemaField(key) {
  return (CONFIG || []).find(item => item.key === key) || null;
}
function configSchemaOptionLabel(key, value) {
  const option = configSchemaOptions(configSchemaField(key)).find(item => item.value === String(value));
  return option ? option.label : '';
}
function configRangeAttrs(f, step = '') {
  const range = f?.range || {};
  const attrs = [];
  if (range.min !== undefined && range.min !== null) attrs.push(`min="${attrEsc(range.min)}"`);
  if (range.max !== undefined && range.max !== null) attrs.push(`max="${attrEsc(range.max)}"`);
  if (step) attrs.push(`step="${attrEsc(step)}"`);
  return attrs.length ? ` ${attrs.join(' ')}` : '';
}

function configFieldStatusV2(f) {
  const dirty = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key);
  if (dirty) return {label: '待保存', cls: 'is-pending'};
  if (f.invalid_env) return {label: '配置值无效，未生效', cls: 'is-error'};
  if (f.secret) return f.configured
    ? {label: f.restart ? '密钥已配置 · 需重启' : '密钥已配置', cls: f.restart ? 'is-restart' : 'is-effective'}
    : {label: '未配置', cls: 'is-muted'};
  if (f.restart) return {label: ['env', 'database'].includes(f.configured_source) ? '已配置 · 需重启' : '默认值 · 重启后生效', cls: 'is-restart'};
  // 常规状态不占用显眼位置；只突出待保存、无效、密钥未配置和需重启状态。
  return {label: '', cls: ''};
}

function renderConfigFieldStatusV2(f) {
  const status = configFieldStatusV2(f);
  if (!status.label) return '';
  return `<span class="config-field-status-v2 ${status.cls}" role="status">${esc(status.label)}</span>`;
}

function emailConfigSectionForKey(key) {
  if (['USE_EMAIL_SERVICE','REGISTER_EMAIL','OTP_MAX_WAIT','OTP_POLL_INTERVAL','EMAIL_SOURCE'].includes(key)) {
    return ['通用邮箱 / OTP', '邮箱来源选择、OTP 等待参数、手动邮箱等通用设置'];
  }
  if (key.startsWith('EMAIL_BUTLER_')) return ['Email Butler', '已导入邮箱的租约连接与取码权限'];
  if (key.startsWith('GPTMAIL_')) return ['GPTMail', 'GPTMail 临时邮箱 API 配置'];
  if (key.startsWith('MAIL_NEST_')) return ['MailNest', 'MailNest / 迈巢临时邮箱 API 配置'];
  if (key.startsWith('REMAIL_')) return ['Remail', '历史 Remail 原订单收码连接；新邮箱请在邮箱服务中准备后导入'];
  if (key.startsWith('MAILCODE_')) return ['域名邮箱 MailCode', '历史 MailCode 原订单收码连接'];
  if (key.startsWith('XIGUA_')) return ['西瓜邮箱', '历史原订单的固定收码连接与轮询参数'];
  if (key.startsWith('CLOUDMAIL_')) return ['CloudMail', '历史邮箱收信 API 连接及已有 Token'];
  if (key.startsWith('ICLOUD_HME_')) return ['iCloud 隐藏邮箱', '已导入与历史隐藏邮箱的固定收件连接；邮箱管理在邮箱服务完成'];
  if (key.startsWith('OUTLOOK_')) return ['Outlook 邮箱池', 'Outlook 邮箱池和取件模式配置'];
  if (key.startsWith('CLOUDFLARE_')) return ['Cloudflare 临时邮箱', 'Cloudflare Worker 临时邮箱 API、鉴权与路径配置'];
  if (['EMAIL_DOMAIN','QQ_EMAIL','QQ_IMAP_PASSWORD'].includes(key)) return ['Cloudflare 域名邮箱', 'Cloudflare 转发到 QQ 邮箱后的 IMAP 收信配置'];
  return ['其他邮箱配置', ''];
}

function emailSectionEnabledV2(section) {
  if (section === '通用邮箱 / OTP') return true;
  return CONFIG.some(field => emailConfigSectionForKey(field.key || '')[0] === section);
}

function proxyConfigSectionForKey(key) {
  if (['REGISTRATION_PROXY_RETRIES', 'REGISTRATION_PROXY_RETRY_DELAY'].includes(key)) {
    return ['注册主链路', '注册任务重试参数已归入注册主链路；线路本身由统一代理池按国家需求领取。'];
  }
  if (['ACCOUNT_ACTION_PROXY_RETRIES', 'ACCOUNT_ACTION_PROXY_RETRY_DELAY'].includes(key)) {
    return ['账号补全', '账号动作重试参数已归入账号补全；新任务不在这里选择代理供应商。'];
  }
  if (['PROXY_1024_REGION', 'PROXY_1024_ROTATE_SESSION_TIME', 'PROXY_1024_VALIDATE', 'PROXY_1024_MAX_ATTEMPTS'].includes(key)) {
    return ['高级兼容', '1024Proxy 的历史区域值仅用于读取旧配置；新任务按各自业务国家向代理池申请。'];
  }
  if (['PROXY_POOL_SOURCE', 'PROXY_POOL_DEFAULT_COUNTRY', 'PROXY_POOL'].includes(key)) {
    return ['代理来源', '统一代理池的当前供给来源与默认国家。业务任务只提出国家和用途需求。'];
  }
  if (key === 'PROXY_POOL_WAIT_TIMEOUT') {
    return ['库存策略', '库存不足时持续等待或按配置时限等待，不在业务线程直接调用供应商。'];
  }
  if (['PLAN_CHECK_PROXY_ALLOW_REUSE', 'PLAN_CHECK_PROXY_REUSE_LIMIT'].includes(key)) {
    return ['库存策略', '仅套餐查询用途允许按策略复用已检测出口，其他认证链路仍保持租约隔离。'];
  }
  if (key.startsWith('PROXY_POOL_')) {
    return ['库存策略', '统一代理池的容量、预热、领取和回收策略。'];
  }
  const legacyProxyKeys = new Set([
    'REGISTRATION_PROXY_MODE', 'ACCOUNT_PASSWORD_PROXY_MODE', 'ACCOUNT_2FA_PROXY_MODE',
    'ACCOUNT_PLAN_CHECK_PROXY_MODE', 'ACCOUNT_LIVE_CHECK_PROXY_MODE', 'ACCOUNT_REFRESH_AT_PROXY_MODE',
    'ACCOUNT_CODEX_PROXY_MODE', 'ACCOUNT_EMAIL_CHANGE_PROXY_MODE', 'PLAN_CHECK_PROXY_MODE',
    'PLAN_CHECK_PROXY', 'REGISTRATION_PROXY_PROVIDER', 'REGISTRATION_PROXY_REGION',
    'ACCOUNT_PLAN_CHECK_PROVIDER', 'ACCOUNT_PLAN_CHECK_REGION',
  ]);
  if (legacyProxyKeys.has(key) || key.endsWith('_PROXY_MODE')) {
    return ['高级兼容', '旧版逐动作来源字段仅用于读取历史快照，不参与新任务的代理池选择。'];
  }
  if (['ACCOUNT_PASSWORD_PROXY_MODE','ACCOUNT_2FA_PROXY_MODE','ACCOUNT_PLAN_CHECK_PROXY_MODE','PLAN_CHECK_PROXY_ALLOW_REUSE','PLAN_CHECK_PROXY_REUSE_LIMIT','PLAN_CHECK_PAYMENT_METHODS_ENABLED','PLAN_CHECK_COUNTRIES','PLAN_CHECK_COUNTRY_WAIT_TIMEOUT','ACCOUNT_LIVE_CHECK_PROXY_MODE','ACCOUNT_REFRESH_AT_PROXY_MODE','ACCOUNT_CODEX_PROXY_MODE','ACCOUNT_EMAIL_CHANGE_PROXY_MODE','PLAN_CHECK_TIMEOUT','PLAN_CHECK_MAX_ATTEMPTS','PLAN_CHECK_RETRY_DELAY','PLAN_CHECK_REGISTRATION_RECHECK_DELAY','PLAN_CHECK_MIN_INTERVAL','PLAN_CHECK_JITTER'].includes(key)) {
    return ['高级兼容', '旧版逐动作来源字段仅用于读取历史快照；新任务按账号国家和业务用途从统一代理池领取线路。'];
  }
  if (Object.values(PROXY_PROVIDER_CONFIG_V2).some(provider => key.startsWith(provider.prefix)) || key.startsWith('REGISTRATION_PROXY_')) {
    return ['代理来源', '当前供应商的提取、检测和粘性参数；切换来源会保留各供应商配置。'];
  }
  return ['高级兼容', '历史代理配置保留供兼容读取；新任务统一向代理池申请线路。'];
}

function smsConfigSectionForKey(key) {
  if (['SMS_PROVIDER','SMS_COUNTRY','SMS_SERVICE','SMS_MAX_PRICE','SMS_AUTO_SELECT_COUNTRY','SMS_AUTO_COUNTRY_MIN_RATIO','SMS_MAX_RETRIES','SMS_CODE_WAIT','CODEX_PHONE_TOTAL_TIMEOUT'].includes(key)) {
    return ['通用接码', '接码通道选择、国家/服务代码、批次成功率选国、等待和重试参数；H 通道可复用 SMS_SERVICE/SMS_COUNTRY 作为 projectId/country'];
  }
  if (key === 'SMS_API_KEY') return ['GrizzlySMS', 'GrizzlySMS 平台 API Key 配置'];
  if (key.startsWith('H_')) return ['H 接码', 'H_API.md 本地 H 取号服务配置；项目ID/国家留空时复用通用字段'];
  if (key.startsWith('L_')) return ['L 接码', '本地 L 取号服务配置，接口约定见 README'];
  return ['其他接码配置', ''];
}

function codexConfigSectionForKey(key) {
  if (['CODEX_OAUTH_DRIVER','CODEX_AUTH_URL_SOURCE'].includes(key)) {
    return ['基础配置', 'Codex 授权驱动和授权地址来源配置'];
  }
  if (key.startsWith('CODEX_TOKEN_')) {
    return ['Token 自动刷新', '使用 refresh_token 提前换新 Codex access token，不重新登录、不消耗邮箱 OTP 或短信'];
  }
  if (key.startsWith('CPA_')) {
    return ['CPA配置', 'CPA 授权链接生成、回调上传和管理接口配置'];
  }
  if (key.startsWith('SUB2API_') || key === 'CODEX_OAUTH_AUTO_UPLOAD_SUB2API') {
    return ['sub2api', 'sub2api 的 API 基址、鉴权和超时配置；用于 Codex OAuth 授权和凭证上传'];
  }
  return ['基础配置', ''];
}

function renderRoxyWorkspaceToolsV2() {
  const current = (CONFIG.find(f => f.key === 'ROXY_WORKSPACE_ID') || {}).value || '';
  return `
    <div class="config-tool-panel-v2 roxy-workspace-box">
      <div>
        <b>团队 / 项目选择</b>
        <div class="hint">点击“获取团队”调用 Roxy <span class="mono">/browser/workspace</span>，选择后保存团队与项目 ID。</div>
        <a class="roxy-invite-link" href="https://roxybrowser.cn/invite/NvH4Jx" target="_blank" rel="noopener noreferrer">打开 RoxyBrowser 官网（免费 5 个窗口）</a>
      </div>
      <div class="row">
        <div>
          <label class="fld">团队 / 项目
            <select id="roxyWorkspaceSelectV2"><option value="">当前团队：${esc(current || '未设置')}</option></select>
          </label>
        </div>
        <div class="action-cell">
          <button class="btn" type="button" id="btnLoadRoxyWorkspacesV2">获取团队</button>
          <button class="btn primary" type="button" id="btnSaveRoxyWorkspaceV2" disabled>保存选择</button>
        </div>
      </div>
      <div id="roxyWorkspaceStatusV2" class="muted" style="font-size:12px;">未加载</div>
    </div>
  `;
}

function bindRoxyWorkspaceToolsV2() {
  const loadBtn = $('#btnLoadRoxyWorkspacesV2');
  const saveBtn = $('#btnSaveRoxyWorkspaceV2');
  const sel = $('#roxyWorkspaceSelectV2');
  if (!loadBtn || !saveBtn || !sel) return;
  if (loadBtn.dataset.bound) return;
  loadBtn.dataset.bound = '1';
  sel.addEventListener('change', () => { saveBtn.disabled = !sel.value; });
  loadBtn.addEventListener('click', () => loadRoxyWorkspaces());
  saveBtn.addEventListener('click', () => saveRoxyWorkspaceSelection());
}

function configGroupSlug(name) {
  return 'cfg-' + String(configMenuGroupV2(name))
    .replace(/[^\w\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
}
function configGroupDisplayName(name) {
  return String(name || '其他');
}
function configNavCategoryV2(name) {
  for (const category of CONFIG_NAV_CATEGORY_ORDER_V2) {
    if (CONFIG_NAV_CATEGORY_RULES_V2[category].has(name)) return category;
  }
  const text = String(name || '');
  if (text.includes('代理') || text.includes('Browser') || text.includes('浏览器') || text.includes('画像')) return '资源与服务';
  return '系统';
}
function configNavSearchTextV2(name, fields) {
  return [name, ...(fields || []).flatMap(f => [f.group, f.key, f.label, f.help || '', configFieldSubsectionV2(f)])].join(' ');
}
function configFieldSubsectionV2(field) {
  if (CONFIG_PLAN_BUSINESS_KEYS_V2.has(field.key)) return '注册与账号';
  if (CONFIG_FIELD_UI_GROUP_OVERRIDES_V2.has(field.key)) return configFieldUiGroupV2(field);
  if (field.group === '邮箱 / OTP') return emailConfigSectionForKey(field.key)[0];
  if (field.group === '接码平台') return smsConfigSectionForKey(field.key)[0];
  if (field.group === '代理与网络') return proxyConfigSectionForKey(field.key)[0];
  if (field.group === 'Codex') return codexConfigSectionForKey(field.key)[0];
  return '';
}
function configFieldMenuV2(field) {
  if (CONFIG_PLAN_BUSINESS_KEYS_V2.has(field.key)) return '注册与账号';
  return configMenuGroupV2(configFieldUiGroupV2(field));
}
const CONFIG_EXTRACT_LINK_COMMON_KEYS_V2 = new Set([
  'EXTRACT_LINK_ENABLED', 'EXTRACT_LINK_DEFAULT_PROVIDER', 'EXTRACT_LINK_DEFAULT_MODE',
  'EXTRACT_LINK_BATCH_WORKERS', 'EXTRACT_LINK_EXTRACT_ENABLED',
  'EXTRACT_LINK_PREFLIGHT_ENABLED', 'EXTRACT_LINK_PREFLIGHT_REFRESH_AT_ENABLED',
  'EXTRACT_LINK_MANUAL_PAYMENT_ENABLED', 'EXTRACT_LINK_AUTO_PAYMENT_ENABLED',
  'EXTRACT_LINK_POST_PAYMENT_CHECK_ENABLED', 'EXTRACT_LINK_POST_PAYMENT_REFRESH_AT_ENABLED',
  'EXTRACT_LINK_POST_PAYMENT_PLAN_CHECK_ENABLED', 'EXTRACT_LINK_QUEUE_LIMIT',
]);
const CONFIG_EXTRACT_LINK_LEGACY_KEYS_V2 = new Set([
  'EXTRACT_LINK_API_BASE', 'EXTRACT_LINK_CDK', 'EXTRACT_LINK_TYPE',
  'EXTRACT_LINK_REQUEST_TIMEOUT', 'EXTRACT_LINK_EVENT_TIMEOUT',
]);
const CONFIG_EXTRACT_LINK_PROVIDER_LABELS_V2 = Object.freeze({
  legacy: '虾扯蛋链', lumen_flow: '流光', huanguang: '幻光', anguang: '暗光（XXSYUN 一条龙）',
});
function extractLinkProviderEnabledKeyV2(providerId) {
  return `EXTRACT_LINK_${String(providerId || '').trim().toUpperCase()}_ENABLED`;
}
function extractLinkProviderFieldBelongsV2(field, providerId) {
  const key = String(field?.key || '');
  const id = String(providerId || '').trim().toLowerCase();
  if (!key || key === extractLinkProviderEnabledKeyV2(id)) return false;
  if (id === 'legacy') return CONFIG_EXTRACT_LINK_LEGACY_KEYS_V2.has(key) || key.startsWith('EXTRACT_LINK_LEGACY_');
  return key.startsWith(`EXTRACT_LINK_${id.toUpperCase()}_`);
}
function extractLinkProviderOptionsV2(fields = CONFIG) {
  const source = fields || [];
  const defaults = source.find(field => field.key === 'EXTRACT_LINK_DEFAULT_PROVIDER') || configSchemaField('EXTRACT_LINK_DEFAULT_PROVIDER');
  return configSchemaOptions(defaults).filter(option => {
    const id = option.value.toLowerCase();
    return source.some(field => field.key === extractLinkProviderEnabledKeyV2(id));
  }).map(option => ({
    ...option,
    value: option.value.toLowerCase(),
    label: CONFIG_EXTRACT_LINK_PROVIDER_LABELS_V2[option.value.toLowerCase()] || option.label,
    enabledKey: extractLinkProviderEnabledKeyV2(option.value),
  }));
}
function extractLinkProviderSectionForFieldV2(field) {
  const key = String(field?.key || '');
  if (key.startsWith('EXTRACT_LINK_PAYMENT_')) return '独立支付';
  if (CONFIG_EXTRACT_LINK_COMMON_KEYS_V2.has(key)
    || extractLinkProviderOptionsV2().some(provider => provider.enabledKey === key)) return '通用配置';
  const provider = extractLinkProviderOptionsV2().find(item => extractLinkProviderFieldBelongsV2(field, item.value));
  return provider?.label || '通用配置';
}
function extractLinkProviderSelectionValueV2(value) {
  return value === true || ['1', 'true', 'yes', 'on', 'enabled'].includes(String(value ?? '').trim().toLowerCase());
}
function applyExtractLinkProviderSelectionV2(values) {
  const selected = new Set(configListValuesV2(values, {key: 'EXTRACT_LINK_ENABLED_PROVIDERS'}));
  extractLinkProviderOptionsV2().forEach(provider => {
    if (CONFIG.some(field => field.key === provider.enabledKey)) {
      setPendingConfigValue(provider.enabledKey, selected.has(provider.value));
    }
  });
  renderConfigOverviewCards();
  updateConfigSaveUi();
}
function configFieldMatchesQueryV2(field, query = CONFIG_NAV_QUERY_V2) {
  const needle = String(query || '').trim().toLowerCase();
  return !!needle && configNavSearchTextV2('', [field]).toLowerCase().includes(needle);
}
function selectConfigSearchDestinationV2(name = CONFIG_ACTIVE_GROUP_V2) {
  const query = CONFIG_NAV_QUERY_V2.trim().toLowerCase();
  if (!query) return;
  const groups = configGroups();
  const names = Object.keys(CONFIG_MENU_DOMAINS_V2).filter(menu => groups[menu])
    .concat(Object.keys(groups).filter(menu => !CONFIG_MENU_DOMAINS_V2[menu]));
  const matches = menu => configNavSearchTextV2(menu, groups[menu]).toLowerCase().includes(query);
  // 完整配置键优先精确匹配，避免 PLAN_CHECK_PROXY 命中较长的账号配置键。
  const exactField = CONFIG.find(field => field.key.toLowerCase() === query);
  const menu = exactField ? configFieldMenuV2(exactField)
    : (groups[name] && matches(name) ? name : names.find(matches));
  if (!menu) return;
  CONFIG_ACTIVE_GROUP_V2 = menu;
  const field = exactField || groups[menu].find(item => configFieldMatchesQueryV2(item, query));
  if (!field) return;
  CONFIG_ACTIVE_DOMAIN_V2[menu] = configFieldUiGroupV2(field);
  const subsection = configFieldSubsectionV2(field);
  if (field.group === '邮箱 / OTP') CONFIG_EMAIL_ACTIVE_SECTION_V2 = subsection;
  if (field.group === '接码平台') CONFIG_SMS_ACTIVE_SECTION_V2 = subsection;
  if (field.group === '代理与网络') CONFIG_PROXY_ACTIVE_SECTION_V2 = subsection;
  if (field.group === 'Codex') CONFIG_CODEX_ACTIVE_SECTION_V2 = subsection;
  if (field.group === '提链') CONFIG_EXTRACT_LINK_ACTIVE_SECTION_V2 = extractLinkProviderSectionForFieldV2(field);
}
function configNavDirtyV2(fields) {
  return (fields || []).some(f => Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key));
}
function renderConfigNavV2(names, groups) {
  const buckets = {};
  names.forEach(name => {
    const category = configNavCategoryV2(name);
    (buckets[category] = buckets[category] || []).push(name);
  });
  const categories = [
    ...CONFIG_NAV_CATEGORY_ORDER_V2,
    ...Object.keys(buckets).filter(category => !CONFIG_NAV_CATEGORY_ORDER_V2.includes(category)),
  ];
  return categories.filter(category => buckets[category]?.length).map(category => `
    <div class="config-nav-v2-group" data-config-nav-group="${attrEsc(category)}">
      <div class="config-nav-v2-group-label">${esc(category)}</div>
      <div class="config-nav-v2-group-list">
        ${buckets[category].map(name => {
          const fields = groups[name] || [];
          const dirty = configNavDirtyV2(fields);
          return `
            <button type="button" class="config-nav-v2-item${name === CONFIG_ACTIVE_GROUP_V2 ? ' is-active' : ''}"
              data-config-nav="${attrEsc(name)}" data-config-target="${attrEsc(configGroupSlug(name))}"
              data-config-search="${attrEsc(configNavSearchTextV2(name, fields))}"
              data-config-keys="${attrEsc(fields.map(f => f.key).join(','))}"
              aria-current="${name === CONFIG_ACTIVE_GROUP_V2 ? 'page' : 'false'}">
              <svg viewBox="0 0 24 24" aria-hidden="true">${configNavIcon(name)}</svg>
              <span class="config-nav-v2-copy">
                <span class="config-nav-v2-label">${esc(configGroupDisplayName(name))}</span>
                <span class="config-nav-v2-meta">${fields.length} 项配置</span>
              </span>
              <span class="config-nav-v2-dirty" data-config-dirty${dirty ? '' : ' hidden'} aria-label="有未保存更改"></span>
            </button>
          `;
        }).join('')}
      </div>
    </div>
  `).join('');
}
function configNavIcon(name) {
  const n = String(name || '');
  if (n.includes('网站') || n.includes('WebUI')) return '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>';
  if (n.includes('开关') || n.includes('功能')) return '<rect x="1" y="8" width="22" height="8" rx="4"/><circle cx="7" cy="12" r="2.8"/>';
  if (n.includes('邮箱') || n.includes('OTP')) return '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="M22 6l-10 7L2 6"/>';
  if (n.includes('接码') || n.includes('SMS')) return '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>';
  if (n.includes('Codex')) return '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>';
  if (n.includes('代理') || n.includes('Proxy')) return '<circle cx="12" cy="12" r="3"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/>';
  if (n.includes('画像') || n.includes('指纹')) return '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>';
  if (n.includes('人工') || n.includes('节奏')) return '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>';
  if (n.includes('提链')) return '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>';
  if (n.includes('Browser') || n.includes('Roxy') || n.includes('浏览器') || n.includes('注册')) return '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>';
  return '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>';
}
function getConfigGroupNames() {
  return Object.keys(configGroups());
}
function configSectionIntro(name) {
  if (name === '注册与账号') return '按业务动作维护注册、账号补全和套餐查询；代理线路由统一代理池领取。';
  if (name === '邮箱与验证码') return '选择可用邮箱来源并维护验证码与短信接码服务。';
  if (name === '浏览器') return '维护浏览器连接、账号环境、地区画像、省流量和人工节奏。';
  if (name === '服务集成') return '维护 CPA、sub2api 等外部服务连接。';
  if (name === '系统与维护') return '维护并发、自动任务、诊断日志、任务保留和访问设置。';
  if (name === '并发控制') return '管理当前部署的全局业务执行上限与各独立任务类型上限；本地与 Oracle 分别生效。';
  if (name === 'WebUI 授权') return '配置网站登录授权码与 Session 签名密钥。';
  if (name === '通用配置') return '账号批量操作等跨页面的通用运行参数。';
  if (name === '注册主链路') return '配置注册主流程、注册国家、密码/验证码模式，以及注册后可选能力。';
  if (name === '账号补全') return '选择“补全账号”包含的项目，维护账号操作的通用策略；各功能参数在对应分类中维护。';
  if (name === '查活') return '配置普通查活的执行驱动与浏览器能力，只在线验证已有 AT。';
  if (name === '刷新 AT') return '配置 AT 刷新驱动、国家、网络恢复、协议认证和自动刷新任务。';
  if (name === '补密码') return '配置账号补密码的执行驱动与邮箱重置策略。';
  if (name === '补 2FA') return '配置账号补充 2FA 的执行驱动、浏览器兜底与重认证参数。';
  if (name === '邮箱换绑') return '配置协议邮箱换绑开关与账号年龄要求。';
  if (name === '注册调试') return '配置注册失败诊断、现场保留和抓包存储，不改变正常注册流程。';
  if (name === 'RoxyBrowser') return 'RoxyBrowser API、环境与代理相关设置。';
  if (name === 'Codex') return '配置 Codex 授权地址来源、CPA 与 sub2api；Token 自动刷新归入系统设置的定时任务。';
  if (name === '邮箱 / OTP') return '邮箱来源、OTP 等待与各邮箱服务商参数。';
  if (name === '接码平台') return '接码通道、国家代码与本地取号服务参数。';
  if (name === '定时任务') return '后台周期任务的开关与执行间隔。上次执行时间保存在数据库中，重启服务会按剩余时间接续，不会重复执行。';
  if (name === '人工节奏') return '配置流程操作的随机停顿节奏，适用于协议全链路和浏览器操作。';
  if (name === '浏览器画像') return '浏览器语言、时区与出口 IP 画像。';
  if (name === '代理与网络') return '统一管理代理池来源、默认国家和库存策略；业务任务只提交用途与国家需求。';
  if (name === '提链') return '管理平台启用、默认模式、支付权限、平台凭据与并发。';
  return '';
}
function configFeatureIcon(key) {
  if (key === 'ENABLE_CODEX_AUTO') {
    return {
      cls: 'config-switch-v2-icon--codex',
      svg: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    };
  }
  if (key === 'ENABLE_2FA') {
    return {
      cls: 'config-switch-v2-icon--2fa',
      svg: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/>'
    };
  }
  if (key === 'ENABLE_FLOW_TRIGGER') {
    return {
      cls: 'config-switch-v2-icon--flow',
      svg: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
    };
  }
  return {
    cls: 'config-switch-v2-icon--default',
    svg: '<path d="M12 2v4"/><path d="M12 18v4"/><path d="M4.93 4.93l2.83 2.83"/><path d="M16.24 16.24l2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="M4.93 19.07l2.83-2.83"/><path d="M16.24 7.76l2.83-2.83"/>'
  };
}
function renderConfigSectionHead(name, meta = '') {
  const title = configGroupDisplayName(name);
  const menu = configMenuGroupV2(name);
  const fields = configGroups()[menu] || [];
  const domains = configMenuDomainNamesV2(menu, fields);
  return `
    <div class="config-section-v2-head">
      <div class="config-section-v2-head-main">
        <h3>${esc(title)}</h3>
        ${meta ? `<p class="config-section-v2-meta">${esc(meta)}</p>` : ''}
      </div>
      <span class="config-section-v2-head-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24">${configNavIcon(name)}</svg>
      </span>
    </div>
    ${domains.length > 1 ? `<div class="config-subtabs-v2" role="group" aria-label="${attrEsc(title)}分类">
      ${domains.map(domain => `<button type="button" data-config-domain-v2="${attrEsc(domain)}" class="${domain === name ? 'active' : ''}" aria-pressed="${domain === name}">${esc(domain === '注册与账号' && menu === '注册与账号' ? '查询套餐' : domain)}</button>`).join('')}
    </div>` : ''}
  `;
}
function registrationDriverChoices() {
  return configSchemaOptions(configSchemaField('REGISTRATION_DRIVER'));
}
function getRegistrationDriverField() {
  return (CONFIG || []).find(f => f.key === 'REGISTRATION_DRIVER') || null;
}
function getRegistrationDriverValue() {
  const f = getRegistrationDriverField();
  if (!f) return 'roxy';
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  const current = String(fv == null ? 'roxy' : fv).trim().toLowerCase() || 'roxy';
  return ({protocol: 'protocol_oss_2', protocol_oss: 'protocol_oss_2', roxy_oss: 'roxy'})[current] || current;
}
function registrationDriverLabel(value) {
  const cur = String(value || '').trim().toLowerCase();
  const hit = registrationDriverChoices().find(c => String(c.value) === cur);
  return hit ? String(hit.label || hit.value) : (cur || '—');
}
function renderRegistrationDriverCard() {
  const cur = getRegistrationDriverValue();
  const label = registrationDriverLabel(cur);
  const labelEl = document.getElementById('configCardRegistrationLabelV2');
  const hintEl = document.getElementById('configCardRegistrationHintV2');
  if (labelEl) {
    labelEl.textContent = label;
    labelEl.classList.toggle('is-placeholder', !label || label === '—');
  }
  if (hintEl) hintEl.textContent = `驱动标识: ${cur}`;
}
function configOverviewValue(key, fallback='—') {
  const field = (CONFIG || []).find(item => item.key === key);
  if (!field) return fallback;
  const value = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key)
    ? CONFIG_PENDING_UPDATES[key] : field.value;
  if (value === null || value === undefined || value === '') return fallback;
  return value;
}
function compactConfigLabel(value) {
  return String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, m => m.toUpperCase());
}
function renderConfigOverviewCards() {
  const emailSource = configOverviewValue('EMAIL_SOURCE');
  const codexDriver = configOverviewValue('CODEX_OAUTH_DRIVER', 'protocol');
  const codexAuto = !!configOverviewValue('ENABLE_CODEX_AUTO', false);
  const proxyMode = configOverviewValue('REGISTRATION_PROXY_MODE', 'none');
  const values = [
    ['configCardEmailSourceV2', compactConfigLabel(emailSource)],
    ['configCardCodexDriverV2', codexOauthDriverLabel(codexDriver)],
    ['configCardProxyModeV2', compactConfigLabel(proxyMode)],
  ];
  values.forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
    el.classList.toggle('is-placeholder', value === '—');
  });
  const emailHint = document.getElementById('configCardEmailSourceHintV2');
  if (emailHint) emailHint.textContent = emailSource === '—' ? '用于注册验证码接收' : `来源标识: ${emailSource}`;
  const codexHint = document.getElementById('configCardCodexDriverHintV2');
  if (codexHint) codexHint.textContent = `自动授权: ${codexAuto ? '已开启' : '已关闭'}`;
}
function renderFeatureSwitchField(f, opts = {}) {
  const control = renderConfigControlMarkupV2(f);
  const compactHelp = {
    ROXY_ONE_PROFILE_PER_ACCOUNT: '每个账号最多绑定一个 Roxy 环境。',
    ROXY_RANDOM_PROFILE_NAME_ON_CREATE: '每次创建环境时自动生成不同名称。',
  }[f.key];
  return renderConfigSettingRowV2(f, control, {help: opts.help || compactHelp || f.help || ''});
}

function orderedConfigFieldsV2(fields, keys) {
  const byKey = new Map((fields || []).map(f => [f.key, f]));
  return keys.map(key => byKey.get(key)).filter(Boolean);
}

function renderConfigSettingGroupV2(title, fields, renderer = renderConfigSettingRowV2) {
  if (!fields || !fields.length) return '';
  return `
    <div class="config-setting-group-v2">
      <div class="config-setting-group-head-v2">${esc(title)}</div>
      <div class="config-setting-list-v2">${fields.map(field => renderer(field)).join('')}</div>
    </div>
  `;
}

function renderAccountCompletionRowV2(f) {
  if (f.key !== 'ACCOUNT_CODEX_DRIVER') return renderConfigSettingRowV2(f);
  const registrationValue = configFieldValueV2('CODEX_OAUTH_DRIVER', 'same_as_registration');
  const accountValue = configFieldValueV2(f.key, 'same_as_registration');
  const registrationLabel = codexOauthDriverLabel(registrationValue);
  const accountLabel = codexOauthDriverLabel(accountValue);
  const mismatch = String(registrationValue).trim().toLowerCase() !== String(accountValue).trim().toLowerCase();
  return renderConfigSettingRowV2(
    f,
    `<div class="config-setting-readonly-v2"><strong>${esc(registrationLabel)}</strong><span>由注册主链路统一维护</span></div>`,
    {
      extraClass: 'config-setting-row-v2--readonly',
      help: mismatch
        ? `当前账号补全值为“${accountLabel}”，保存注册主链路中的 Codex OAuth 后会同步统一。`
        : '注册和账号补全共用同一套 Codex OAuth 执行方式，请到注册主链路修改。',
    }
  );
}

function renderRegistrationMainSectionV2(fields) {
  const primaryKeys = [
    'REGISTRATION_DRIVER',
    'REGISTRATION_COUNTRY',
    'REGISTRATION_AUTH_MODE',
    'REGISTER_NAME',
    'REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS',
  ];
  const postRegistrationKeys = [
    'REGISTRATION_PLAN_CHECK_ENABLED',
    'ENABLE_2FA',
    'TWOFA_DRIVER',
    'ENABLE_CODEX_AUTO',
    'CODEX_OAUTH_DRIVER',
    'ENABLE_FLOW_TRIGGER',
  ];
  const primary = orderedConfigFieldsV2(fields, primaryKeys);
  const postRegistration = orderedConfigFieldsV2(fields, postRegistrationKeys);
  const known = new Set([...primaryKeys, ...postRegistrationKeys]);
  const extra = fields.filter(f => !known.has(f.key));
  return `
    <section class="config-section-v2" id="${esc(configGroupSlug('注册主链路'))}" data-config-section="注册主链路">
      ${renderConfigSectionHead('注册主链路', configSectionIntro('注册主链路'))}
      ${renderConfigSettingGroupV2('注册基础流程', primary)}
      ${renderConfigSettingGroupV2('注册后能力', postRegistration)}
      ${renderConfigSettingGroupV2('其他注册参数', extra)}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderAccountCompletionSectionV2(fields) {
  const completionKeys = [
    'ACCOUNT_COMPLETION_PASSWORD_ENABLED',
    'ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED',
    'ACCOUNT_COMPLETION_2FA_ENABLED',
    'ACCOUNT_COMPLETION_CODEX_ENABLED',
    'ACCOUNT_COMPLETION_REFRESH_AT_ENABLED',
  ];
  const strategyKeys = [
    'ACCOUNT_AUTH_V2_ENABLED',
    'ACCOUNT_AUTH_RAW_CONTEXT_ENABLED',
    'ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS',
    'ACCOUNT_CODEX_DRIVER',
  ];
  const completion = orderedConfigFieldsV2(fields, completionKeys);
  const strategies = orderedConfigFieldsV2(fields, strategyKeys);
  const known = new Set([...completionKeys, ...strategyKeys]);
  const extra = fields.filter(f => !known.has(f.key));
  return `
    <section class="config-section-v2" id="${esc(configGroupSlug('账号补全'))}" data-config-section="账号补全">
      ${renderConfigSectionHead('账号补全', configSectionIntro('账号补全'))}
      ${renderConfigSettingGroupV2('补全项目', completion)}
      ${renderConfigSettingGroupV2('账号处理策略', strategies, renderAccountCompletionRowV2)}
      ${renderConfigSettingGroupV2('其他账号参数', extra, renderAccountCompletionRowV2)}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderAccountActionSectionV2(name, fields) {
  const sections = CONFIG_ACCOUNT_ACTION_SECTIONS_V2[name];
  const known = new Set(sections.flatMap(([, keys]) => keys));
  return `
    <section class="config-section-v2" id="${esc(configGroupSlug(name))}" data-config-section="${attrEsc(name)}">
      ${renderConfigSectionHead(name, configSectionIntro(name))}
      ${sections.map(([title, keys]) => renderConfigSettingGroupV2(title, orderedConfigFieldsV2(fields, keys))).join('')}
      ${renderConfigSettingGroupV2('其他参数', fields.filter(field => !known.has(field.key)))}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderRegistrationDebugSectionV2(fields) {
  const diagnosticKeys = [
    'REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED',
    'REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT',
    'REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB',
  ];
  const runtimeKeys = [
    'REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS',
    'REGISTRATION_DEBUG_MAX_HELD_SESSIONS',
  ];
  const storageKeys = [
    'REGISTRATION_DEBUG_BODY_MAX_KB',
    'REGISTRATION_DEBUG_BODY_BUDGET_MB',
    'REGISTRATION_DEBUG_GLOBAL_BUDGET_MB',
    'REGISTRATION_DEBUG_RETENTION_DAYS',
    'REGISTRATION_DEBUG_QUEUE_SIZE',
  ];
  const diagnostics = orderedConfigFieldsV2(fields, diagnosticKeys);
  const runtime = orderedConfigFieldsV2(fields, runtimeKeys);
  const storage = orderedConfigFieldsV2(fields, storageKeys);
  const known = new Set([...diagnosticKeys, ...runtimeKeys, ...storageKeys]);
  const extra = fields.filter(f => !known.has(f.key));
  return `
    <section class="config-section-v2" id="${esc(configGroupSlug('注册调试'))}" data-config-section="注册调试">
      ${renderConfigSectionHead('注册调试', configSectionIntro('注册调试'))}
      ${renderConfigSettingGroupV2('失败诊断', diagnostics)}
      ${renderConfigSettingGroupV2('失败现场运行', runtime)}
      ${renderConfigSettingGroupV2('抓包存储与清理', storage)}
      ${renderConfigSettingGroupV2('其他调试参数', extra)}
      <div class="config-lifecycle-note-v2">“调试模式”仍是单个注册批次的现场保留开关，本页只控制失败诊断、保留时长和抓包预算。</div>
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderPlanBusinessSectionV2(fields) {
  return `
    <section class="config-section-v2" id="${esc(configGroupSlug('注册与账号'))}" data-config-section="注册与账号">
      ${renderConfigSectionHead('注册与账号', configSectionIntro('注册与账号'))}
      ${renderConfigSettingGroupV2('查询套餐', fields)}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function registrationTwofaDriverChoices() {
  return configSchemaOptions(configSchemaField('TWOFA_DRIVER'));
}
function accountTwofaDriverChoices() {
  return configSchemaOptions(configSchemaField('ACCOUNT_2FA_DRIVER'));
}
function twofaDriverChoices() {
  return accountTwofaDriverChoices();
}
function liveCheckDriverChoices() {
  const choices = configSchemaOptions(configSchemaField('ACCOUNT_LIVE_CHECK_DRIVER'));
  const rawEnabled = configFieldValueV2('ACCOUNT_LIVE_CHECK_BROWSER_ENABLED', false);
  const enabled = rawEnabled === true || ['1', 'true', 'yes', 'on'].includes(String(rawEnabled).trim().toLowerCase());
  return enabled ? choices : choices.filter(item => item.value !== 'browser_roxy' || item.disabled);
}
function protocolVersionChoices() {
  return configSchemaOptions(configSchemaField('OPENAI_PROTOCOL_VERSION'));
}
let EXTRACT_LINK_TYPE_CHOICES_V2 = [];

function extractLinkTypeOptionsV2(current = '') {
  const schemaOptions = configSchemaOptions(configSchemaField('EXTRACT_LINK_TYPE'));
  const options = (EXTRACT_LINK_TYPE_CHOICES_V2.length ? EXTRACT_LINK_TYPE_CHOICES_V2 : schemaOptions).slice();
  const normalized = String(current || '').trim().toLowerCase();
  if (normalized && !options.some(item => item.value === normalized)) {
    options.unshift({ value: normalized, label: `当前配置（${normalized}）` });
  }
  return options;
}

function renderExtractLinkTypeControlV2(fv) {
  const current = String(fv == null ? '' : fv).trim().toLowerCase();
  return `<select data-key="EXTRACT_LINK_TYPE" aria-label="提链类型">${extractLinkTypeOptionsV2(current).map(item => `<option value="${attrEsc(item.value)}"${current === item.value ? ' selected' : ''}>${esc(item.label)}</option>`).join('')}</select>`;
}

async function loadExtractLinkTypesV2() {
  try {
    const response = await api('/api/extract-link/types');
    const seen = new Set();
    const items = (Array.isArray(response.items) ? response.items : [])
      .filter(item => item && item.visible !== false && item.enabled !== false)
      .map(item => {
        const value = String(item.type || '').trim().toLowerCase();
        if (!value || seen.has(value)) return null;
        seen.add(value);
        return { value, label: String(item.label || configSchemaOptionLabel('EXTRACT_LINK_TYPE', value) || value) };
      })
      .filter(Boolean);
    if (!items.length) throw new Error('提链网站未返回可用类型');
    EXTRACT_LINK_TYPE_CHOICES_V2 = items;
    document.querySelectorAll('#tab-config [data-key="EXTRACT_LINK_TYPE"]').forEach(select => {
      const current = String(select.value || '').trim().toLowerCase();
      select.innerHTML = extractLinkTypeOptionsV2(current).map(item => `<option value="${attrEsc(item.value)}"${current === item.value ? ' selected' : ''}>${esc(item.label)}</option>`).join('');
      select.value = current;
    });
  } catch (error) {
    console.warn('读取提链网站类型失败，使用备用选项：', error);
  }
}
function authProfileModeChoices() {
  return configSchemaOptions(configSchemaField('ACCOUNT_AUTH_PROFILE_MODE'));
}
function configDriverChoices(f) {
  // EMAIL_SOURCE uses the dedicated ordered multi-select below.
  if (Array.isArray(f?.csv_options) && f.csv_options.length) return null;
  if (f.key === 'ACCOUNT_LIVE_CHECK_DRIVER') return liveCheckDriverChoices();
  const choices = configSchemaOptions(f);
  return choices.length ? choices : null;
}

const CONFIG_MULTI_VALUE_KEYS_V2 = new Set([
  'EMAIL_SOURCE', 'ROXY_RANDOM_OS_CHOICES',
  'BROWSER_DATA_SAVER_AUTH_FLOWS', 'BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES',
]);

function configListValuesV2(value, f = {}) {
  const separator = ['EMAIL_SOURCE', 'ROXY_RANDOM_OS_CHOICES'].includes(f.key) ? /[,\n]+/ : /[,\n\s]+/;
  const values = (Array.isArray(value) ? value : String(value ?? '').split(separator)).map(item => String(item).trim()).filter(Boolean);
  if (f.key === 'EMAIL_SOURCE' && Array.isArray(f.options)) {
    const allowed = new Set(f.options.map(option => option?.value));
    return values.filter(item => allowed.has(item));
  }
  return values;
}

function configListOptionValuesV2(f) {
  const schema = configSchemaOptions(f);
  if (schema.length) return schema;
  if (Array.isArray(f?.csv_options)) {
    return f.csv_options.map(value => ({value: String(value), label: String(value)}));
  }
  return [];
}

function configListSummaryV2(f, values, options) {
  if (!values.length) return f.key === 'EMAIL_SOURCE' ? '未启用邮箱来源' : '未选择';
  const labels = values.map(value => options.find(option => option.value === value)?.label || `当前值（${value}）`);
  const shown = labels.slice(0, 2).join('、');
  return labels.length > 2 ? `${shown} +${labels.length - 2}` : shown;
}

function renderConfigMultiSelectV2(f, value) {
  const schemaOptions = configListOptionValuesV2(f);
  const values = configListValuesV2(value, f);
  const options = schemaOptions.slice();
  values.slice().reverse().forEach(item => {
    if (!options.some(option => option.value === item)) options.unshift({value: item, label: `当前值（${item}）`});
  });
  if (!options.length) return '';
  const selected = new Set(values);
  const summary = configListSummaryV2(f, values, options);
  const optionsMarkup = options.map(item => {
    const checked = selected.has(item.value);
    return `<button type="button" class="config-multi-option-v2${checked ? ' is-selected' : ''}" role="option" aria-selected="${checked}" data-multi-value="${attrEsc(item.value)}"><span class="config-multi-check-v2" aria-hidden="true">${checked ? '✓' : ''}</span><span>${esc(item.label)}</span></button>`;
  }).join('');
  // 保留一个不可见 native select 供旧脚本和无 JS 表单检查读取；实际交互使用
  // 可搜索、可键盘操作的按钮列表，避免要求用户按 Ctrl/Cmd。
  const compat = options.map(item => `<option value="${attrEsc(item.value)}"${selected.has(item.value) ? ' selected' : ''}>${esc(item.label)}</option>`).join('');
  const providerPicker = f.key === 'EXTRACT_LINK_ENABLED_PROVIDERS';
  return `
    <div class="config-multi-select-v2" data-multi-picker="${attrEsc(f.key)}" data-multi-values="${attrEsc(values.join(','))}"${providerPicker ? ' data-extract-provider-picker="true"' : ''}>
      <button type="button" class="config-multi-trigger-v2" aria-expanded="false" aria-haspopup="listbox"><span data-multi-summary>${esc(summary)}</span><span aria-hidden="true">⌄</span></button>
      <div class="config-multi-menu-v2" role="listbox" hidden>
        <input type="search" class="config-multi-search-v2" placeholder="搜索并勾选" aria-label="搜索${attrEsc(f.label)}" data-multi-search>
        <div class="config-multi-options-v2" data-multi-options>${optionsMarkup}</div>
      </div>
      <input type="hidden" data-key="${attrEsc(f.key)}" value="${attrEsc(values.join(','))}"${providerPicker ? ' data-extract-provider-selection="true"' : ''}>
      <select class="config-multi-compat-v2" multiple tabindex="-1" aria-hidden="true" data-config-compat-key="${attrEsc(f.key)}">${compat}</select>
    </div>
  `;
}

function configMultiPickerFieldV2(key) {
  return CONFIG.find(item => item.key === key) || CONFIG_MULTI_PICKER_FIELDS_V2.get(key) || {key};
}

function syncConfigMultiSelectV2(picker) {
  const hidden = picker.querySelector('input[type="hidden"][data-key]');
  if (!hidden) return;
  const f = configMultiPickerFieldV2(hidden.dataset.key);
  const values = configListValuesV2(hidden.value, f);
  const options = configListOptionValuesV2(f);
  picker.dataset.multiValues = values.join(',');
  const selected = new Set(values);
  picker.querySelectorAll('[data-multi-value]').forEach(option => {
    const active = selected.has(option.dataset.multiValue);
    option.classList.toggle('is-selected', active);
    option.setAttribute('aria-selected', active ? 'true' : 'false');
    const check = option.querySelector('.config-multi-check-v2');
    if (check) check.textContent = active ? '✓' : '';
  });
  const summary = picker.querySelector('[data-multi-summary]');
  if (summary) summary.textContent = configListSummaryV2(f, values, options);
  picker.querySelectorAll('.config-multi-compat-v2 option').forEach(option => { option.selected = selected.has(option.value); });
}

function toggleConfigMultiSelectV2(picker, open = null) {
  const menu = picker.querySelector('.config-multi-menu-v2');
  const trigger = picker.querySelector('.config-multi-trigger-v2');
  if (!menu || !trigger) return;
  const next = open === null ? menu.hidden : open;
  menu.hidden = !next;
  trigger.setAttribute('aria-expanded', next ? 'true' : 'false');
  if (next) picker.querySelector('[data-multi-search]')?.focus();
}

function bindConfigMultiSelectsV2() {
  document.querySelectorAll('#tab-config [data-multi-picker]').forEach(picker => {
    if (picker.dataset.bound) return;
    picker.dataset.bound = '1';
    picker.addEventListener('click', event => {
      const trigger = event.target.closest('.config-multi-trigger-v2');
      if (trigger) {
        event.preventDefault();
        toggleConfigMultiSelectV2(picker);
        return;
      }
      const option = event.target.closest('[data-multi-value]');
      if (!option) return;
      event.preventDefault();
      const hidden = picker.querySelector('input[type="hidden"][data-key]');
      if (!hidden) return;
      const f = configMultiPickerFieldV2(hidden.dataset.key);
      const values = configListValuesV2(hidden.value, f);
      const next = values.includes(option.dataset.multiValue)
        ? values.filter(value => value !== option.dataset.multiValue)
        : [...values, option.dataset.multiValue];
      hidden.value = next.join(',');
      syncConfigMultiSelectV2(picker);
      hidden.dispatchEvent(new Event('input', {bubbles: true}));
    });
    picker.addEventListener('input', event => {
      if (!event.target.matches('[data-multi-search]')) return;
      const query = event.target.value.trim().toLowerCase();
      picker.querySelectorAll('[data-multi-value]').forEach(option => {
        option.hidden = !!query && !option.textContent.toLowerCase().includes(query);
      });
    });
    picker.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        toggleConfigMultiSelectV2(picker, false);
        picker.querySelector('.config-multi-trigger-v2')?.focus();
      }
    });
  });
}

function configCountryCodesV2(value) {
  const text = Array.isArray(value) ? value.join(' ') : String(value || '');
  return [...new Set(text.toUpperCase().split(/[\s,]+/).filter(Boolean))];
}

function configCountryNameV2(code) {
  try {
    const names = configCountryNameV2.names ||= new Intl.DisplayNames(['zh-CN'], {type: 'region'});
    return names.of(code) || code;
  } catch {
    return code;
  }
}

function configCountryOptionsV2(f, query = '') {
  const common = ['JP', 'US', 'SG', 'HK', 'TW', 'KR', 'VN', 'IN', 'TH', 'MY', 'GB', 'DE', 'FR', 'CA', 'AU'];
  const search = String(query).trim().toLowerCase();
  return (f.country_codes || []).map(code => ({code, name: f.country_names?.[code] || configCountryNameV2(code)}))
    .filter(item => `${item.name} ${item.code}`.toLowerCase().includes(search))
    .sort((a, b) => {
      const rank = code => common.includes(code) ? common.indexOf(code) : common.length;
      return rank(a.code) - rank(b.code) || a.name.localeCompare(b.name, 'zh-CN');
    });
}

function renderConfigCountryChipsV2(codes) {
  if (!codes.length) return '<span class="hint">尚未选择国家</span>';
  return codes.map(code => `<button type="button" class="config-country-chip-v2" data-country-remove="${attrEsc(code)}" aria-label="移除 ${attrEsc(configCountryNameV2(code))} ${attrEsc(code)}">${esc(configCountryNameV2(code))} <code>${esc(code)}</code><span aria-hidden="true">×</span></button>`).join('');
}

function renderConfigCountryOptionsV2(f, codes, query = '') {
  const options = configCountryOptionsV2(f, query);
  if (!options.length) return '<span class="hint">未找到国家，请尝试中文名称或两位代码</span>';
  return options.map((item, index) => `<button type="button" class="config-country-option-v2" data-country-code="${attrEsc(item.code)}" aria-pressed="${codes.includes(item.code)}" tabindex="${index ? '-1' : '0'}"><span>${esc(item.name)}</span><code>${esc(item.code)}</code></button>`).join('');
}

function configCountrySummaryV2(f, codes) {
  return codes.length ? codes.map(code => `${configCountryNameV2(code)} ${code}`).join('、')
    : f.key === 'PLAN_CHECK_COUNTRIES' ? '沿用账号注册国家' : '未选择额外预热国家';
}

function renderConfigCountryControlV2(f, value) {
  const codes = configCountryCodesV2(value);
  const summary = configCountrySummaryV2(f, codes);
  const help = f.key === 'PLAN_CHECK_COUNTRIES'
    ? '按选择顺序查询；留空沿用账号注册国家，不影响注册查套餐。'
    : '留空不额外预热；实际可用线路取决于代理来源和库存。';
  return `<div class="config-country-picker-v2 config-country-picker-v2--compact" data-country-picker="${attrEsc(f.key)}">
    <details class="config-country-choices-v2">
      <summary title="${attrEsc(summary)}" aria-label="${attrEsc(f.label)}：${attrEsc(summary)}，点击选择国家，可多选"><span data-country-summary>${esc(summary)}</span><span class="config-country-count-v2" data-country-count>${codes.length ? `${codes.length} 国` : '多选'}</span></summary>
      <div class="config-country-menu-v2">
        <input type="search" data-country-search placeholder="搜索国家，如 日本 / JP" aria-label="搜索国家或地区" autocomplete="off">
        <div class="config-country-chips-v2" data-country-chips role="group" aria-label="已选国家，可点击移除">${renderConfigCountryChipsV2(codes)}</div>
        <div class="config-country-options-v2" data-country-options role="group" aria-label="国家列表，可用方向键切换">${renderConfigCountryOptionsV2(f, codes)}</div>
        <span class="hint">可选 ${configCountryOptionsV2(f).length} 个国家 / 地区；${esc(help)}</span>
      </div>
    </details>
    <input type="hidden" data-key="${attrEsc(f.key)}" value="${attrEsc(codes.join(','))}">
  </div>`;
}

function syncConfigCountryPickerV2(picker) {
  const field = configSchemaField(picker.dataset.countryPicker);
  const input = picker.querySelector('[data-key]');
  const codes = configCountryCodesV2(input.value);
  const summary = configCountrySummaryV2(field, codes);
  picker.querySelector('[data-country-summary]').textContent = summary;
  picker.querySelector('[data-country-count]').textContent = codes.length ? `${codes.length} 国` : '多选';
  picker.querySelector('summary').title = summary;
  picker.querySelector('summary').setAttribute('aria-label', `${field.label}：${summary}，点击选择国家，可多选`);
  picker.querySelector('[data-country-chips]').innerHTML = renderConfigCountryChipsV2(codes);
  picker.querySelector('[data-country-options]').innerHTML = renderConfigCountryOptionsV2(field, codes, picker.querySelector('[data-country-search]').value);
}

function bindConfigCountryPickersV2() {
  document.querySelectorAll('#tab-config [data-country-picker]').forEach(picker => {
    picker.addEventListener('input', e => {
      if (e.target.matches('[data-country-search], [data-key]')) syncConfigCountryPickerV2(picker);
    });
    picker.addEventListener('click', e => {
      const button = e.target.closest('[data-country-code], [data-country-remove]');
      if (!button) return;
      const input = picker.querySelector('[data-key]');
      const code = button.dataset.countryCode || button.dataset.countryRemove;
      const codes = configCountryCodesV2(input.value);
      input.value = (codes.includes(code) ? codes.filter(item => item !== code) : [...codes, code]).join(',');
      input.dispatchEvent(new Event('input', {bubbles: true}));
      const focusTarget = button.dataset.countryCode
        ? picker.querySelector(`[data-country-code="${code}"]`)
        : picker.querySelector('[data-country-chips] button') || picker.querySelector('summary');
      if (focusTarget) {
        if (focusTarget.dataset.countryCode) {
          picker.querySelectorAll('[data-country-code]').forEach(item => { item.tabIndex = item === focusTarget ? 0 : -1; });
        }
        focusTarget.focus();
      }
    });
    picker.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        const details = e.target.closest('details');
        if (details) { details.open = false; details.querySelector('summary').focus(); }
        return;
      }
      const current = e.target.closest('[data-country-code]');
      if (!current || !['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
      e.preventDefault();
      const options = [...picker.querySelectorAll('[data-country-code]')];
      const delta = ['ArrowUp', 'ArrowLeft'].includes(e.key) ? -1 : 1;
      const index = e.key === 'Home' ? 0 : e.key === 'End' ? options.length - 1 : (options.indexOf(current) + delta + options.length) % options.length;
      options.forEach((item, i) => { item.tabIndex = i === index ? 0 : -1; });
      options[index].focus();
    });
  });
}

function renderConfigControlMarkupV2(f) {
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  let control = '';
  const driverChoices = configDriverChoices(f);
  if (['PROXY_POOL_COUNTRIES', 'PLAN_CHECK_COUNTRIES'].includes(f.key) && Array.isArray(f.country_codes) && f.country_codes.length) {
    control = renderConfigCountryControlV2(f, fv);
  } else if (['PROXY_POOL_DEFAULT_COUNTRY', 'REGISTRATION_COUNTRY', 'ACCOUNT_AT_REFRESH_COUNTRY'].includes(f.key) && Array.isArray(f.country_codes) && f.country_codes.length) {
    const current = String(fv ?? '').trim().toUpperCase();
    const countryOptions = configCountryOptionsV2(f);
    const options = countryOptions.map(item => ({value: item.code, label: `${item.name} · ${item.code}`}));
    if (current && !options.some(item => item.value === current)) options.unshift({value: current, label: `当前值（${current}），需检查`});
    if (f.key === 'ACCOUNT_AT_REFRESH_COUNTRY') options.unshift({value: '', label: '跟随注册国家'});
    control = `<select data-key="${attrEsc(f.key)}" aria-label="${attrEsc(f.label)}">${options.map(item => `<option value="${attrEsc(item.value)}"${item.value === current ? ' selected' : ''}>${esc(item.label)}</option>`).join('')}</select>`;
  } else if (['EMAIL_SOURCE', 'ROXY_RANDOM_OS_CHOICES', 'BROWSER_DATA_SAVER_AUTH_FLOWS', 'BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES'].includes(f.key)
    || (f.type === 'list_str_multiline' && configListOptionValuesV2(f).length)) {
    control = renderConfigMultiSelectV2(f, fv);
  } else if (f.key === 'EXTRACT_LINK_TYPE') {
    control = renderExtractLinkTypeControlV2(fv);
  } else if (f.key === 'PROXY_POOL_WAIT_TIMEOUT') {
    const hasPending = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key);
    const storedSeconds = Number(fv) > 0 ? Number(fv) : 0;
    const timed = CONFIG_COMPOSITE_MODES_V2[f.key] || (storedSeconds ? 'timed' : 'continuous');
    const seconds = timed === 'timed' ? (hasPending && fv === null ? '' : storedSeconds || 60) : 0;
    control = `<div class="config-composite-control-v2" data-config-composite-key="${attrEsc(f.key)}">
      <select data-key="${attrEsc(f.key)}" data-composite-mode aria-label="领取等待模式">
        <option value="continuous"${timed === 'continuous' ? ' selected' : ''}>持续等待</option>
        <option value="timed"${timed === 'timed' ? ' selected' : ''}>限时等待</option>
      </select>
      <input type="number" data-wait-seconds-key="${attrEsc(f.key)}" data-composite-seconds min="1" step="1" value="${seconds || ''}" placeholder="秒数" aria-label="限时等待秒数"${timed === 'timed' ? '' : ' hidden'}>
    </div>`;
  } else if (f.key === 'SMS_MAX_PRICE') {
    const price = String(fv ?? '').trim();
    const hasPending = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key);
    const limited = CONFIG_COMPOSITE_MODES_V2[f.key] || (price ? 'limited' : 'unlimited');
    const displayedPrice = limited === 'limited' ? (hasPending && price === '' ? '' : price || '0.1') : '';
    control = `<div class="config-composite-control-v2" data-config-composite-key="${attrEsc(f.key)}">
      <select data-key="${attrEsc(f.key)}" data-composite-mode aria-label="价格上限模式">
        <option value="unlimited"${limited === 'unlimited' ? ' selected' : ''}>不设上限</option>
        <option value="limited"${limited === 'limited' ? ' selected' : ''}>设上限</option>
      </select>
      <input type="number" data-price-key="${attrEsc(f.key)}" data-composite-value min="0" step="0.001" value="${attrEsc(displayedPrice)}" placeholder="小数价格" aria-label="短信价格上限"${limited === 'limited' ? '' : ' hidden'}>
    </div>`;
  } else if (driverChoices) {
    const raw = String(fv == null ? '' : fv).trim();
    const current = driverChoices.find(item => item.value.toLowerCase() === raw.toLowerCase())?.value ?? raw;
    const options = driverChoices.slice();
    if (current && !options.some(item => item.value === current)) {
      options.unshift({ value: current, label: `当前配置（${current}）` });
    }
    const disabled = options.length === 1 || options.every(item => item.disabled) ? ' disabled' : '';
    const syncKeys = f.key === 'CODEX_OAUTH_DRIVER' ? ['ACCOUNT_CODEX_DRIVER'] : [];
    const syncAttr = syncKeys.length ? ` data-sync-keys="${attrEsc(syncKeys.join(','))}"` : '';
    control = `<select data-key="${attrEsc(f.key)}" aria-label="${attrEsc(f.label)}"${syncAttr}${disabled}>${options.map(item => `<option value="${attrEsc(item.value)}"${current === item.value ? ' selected' : ''}${item.disabled ? ` disabled title="${attrEsc(item.reason)}"` : ''}>${esc(item.label)}${item.disabled && item.reason ? `（${esc(item.reason)}）` : ''}</option>`).join('')}</select>`;
  } else if (f.type === 'int') {
    control = `<input type="number" data-key="${attrEsc(f.key)}"${configRangeAttrs(f, '1')} value="${attrEsc(fv == null ? '' : fv)}" aria-label="${attrEsc(f.label)}">`;
  } else if (f.type === 'float') {
    control = `<input type="number" data-key="${attrEsc(f.key)}"${configRangeAttrs(f, '0.1')} value="${attrEsc(fv == null ? '' : fv)}" aria-label="${attrEsc(f.label)}">`;
  } else if (f.type === 'bool') {
    control = `<input class="config-switch-v2-toggle config-setting-toggle-v2" type="checkbox" role="switch" data-key="${attrEsc(f.key)}"${fv ? ' checked' : ''} aria-label="${attrEsc(f.label)}">`;
  } else if (f.type === 'list_str_multiline') {
    const placeholder = f.key === 'PLAN_CHECK_COUNTRIES' ? '支持换行、逗号或空格分隔，可留空' : '每行一条，可留空';
    const textarea = `<textarea data-key="${attrEsc(f.key)}"${f.secret ? ' data-secret-input="true"' : ''} placeholder="${attrEsc(placeholder)}" aria-label="${attrEsc(f.label)}">${attrEsc(configListValuesV2(fv, f).join('\n'))}</textarea>`;
    control = f.secret
      ? `<div class="config-secret-control-v2">${textarea}<button type="button" class="config-secret-clear-v2" data-clear-secret="${attrEsc(f.key)}" aria-label="明确清除${attrEsc(f.label)}">清除</button></div>`
      : textarea;
  } else {
    const shown = isPlaceholderEmpty(fv) ? '' : fv;
    const inputType = f.secret ? 'password' : 'text';
    const ph = f.secret ? '留空保留已有值' : '可留空';
    const input = `<input type="${inputType}" data-key="${attrEsc(f.key)}" value="${attrEsc(shown)}" placeholder="${ph}" autocomplete="off" spellcheck="false" aria-label="${attrEsc(f.label)}"${f.secret ? ' data-secret-input="true"' : ''}>`;
    control = f.secret
      ? `<div class="config-secret-control-v2">${input}<button type="button" class="config-secret-clear-v2" data-clear-secret="${attrEsc(f.key)}" aria-label="明确清除${attrEsc(f.label)}">清除</button></div>`
      : input;
  }
  if (f.key === 'EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY') {
    const quota = CONFIG_HUANGUANG_XXSYUN_QUOTA_V2;
    control = `<div data-huanguang-xxsyun-key>${control}
      <button type="button" class="btn" data-query-huanguang-xxsyun-quota aria-label="查询 XXSYUN 剩余次数"${quota.loading ? ' disabled' : ''}>${quota.loading ? '正在查询…' : '查询剩余次数'}</button>
      <p class="config-setting-short-help-v2" data-huanguang-xxsyun-quota-status role="status" aria-live="polite">${esc(quota.text)}</p>
    </div>`;
  }
  if (f.key === 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY') {
    const balance = CONFIG_XXSYUN_PAYMENT_BALANCE_V2;
    control = `<div data-xxsyun-payment-key>${control}
      <button type="button" class="btn" data-query-xxsyun-payment-balance aria-label="查询 XXSYUN 积分"${balance.loading ? ' disabled' : ''}>${balance.loading ? '正在查询…' : '查询积分'}</button>
      <p class="config-setting-short-help-v2" data-xxsyun-payment-balance-status role="status" aria-live="polite">${esc(balance.text)}</p>
    </div>`;
  }
  const cdkKind = Object.keys(CONFIG_HUANGUANG_CDK_QUOTAS_V2).find(kind => CONFIG_HUANGUANG_CDK_QUOTAS_V2[kind].key === f.key);
  if (cdkKind) {
    const quota = CONFIG_HUANGUANG_CDK_QUOTAS_V2[cdkKind];
    control = `<div data-huanguang-cdk-key="${cdkKind}">${control}
      <button type="button" class="btn" data-query-huanguang-cdk-quota="${cdkKind}" aria-label="查询${quota.label} 剩余次数"${quota.loading ? ' disabled' : ''}>${quota.loading ? '正在查询…' : '查询剩余次数'}</button>
      <p class="config-setting-short-help-v2" data-huanguang-cdk-quota-status="${cdkKind}" role="status" aria-live="polite">${esc(quota.text)}</p>
    </div>`;
  }
  const unavailableReason = f.reason || driverChoices?.find(item => item.disabled && item.reason)?.reason || '';
  if (f.readonly || (f.disable_enable && !fv)) {
    control = `<fieldset disabled aria-label="${attrEsc(f.label)}" style="border:0;padding:0;margin:0;min-width:0;opacity:.6">${control}</fieldset>`;
  }
  if (unavailableReason) control += `<p class="config-setting-short-help-v2" role="status">${esc(unavailableReason)}</p>`;
  return control;
}

function huanguangQuotaErrorTextV2(error, label = 'XXSYUN API Key') {
  const code = error?.code || error?.error_code || '';
  const messages = {
    key_invalid: 'XXSYUN API Key 无效或已失效，请更新后重试',
    key_missing: '未配置 XXSYUN API Key，请填写后重试',
    cdk_invalid: `${label} 无效或已失效，请更新并保存后重试`,
    cdk_missing: `未配置${label}，请填写并保存后重试`,
    config_invalid: '查询配置无效，请检查服务地址并保存后重试',
    network_error: '查询遇到网络连接异常，请稍后重试',
    upstream_http_error: '上游服务暂时无法完成查询，请稍后重试',
    rate_limited: '查询过于频繁，请稍后重试',
    invalid_response: '上游次数响应无效，请稍后重试',
    query_failed: '查询失败，请稍后重试',
  };
  return Object.prototype.hasOwnProperty.call(messages, code) ? messages[code] : messages.query_failed;
}

function syncHuanguangCdkQuotaV2(kind) {
  const quota = CONFIG_HUANGUANG_CDK_QUOTAS_V2[kind];
  document.querySelectorAll(`#tab-config [data-query-huanguang-cdk-quota="${kind}"]`).forEach(button => {
    button.disabled = quota.loading;
    button.textContent = quota.loading ? '正在查询…' : '查询剩余次数';
  });
  document.querySelectorAll(`#tab-config [data-huanguang-cdk-quota-status="${kind}"]`).forEach(status => {
    status.textContent = quota.text;
  });
}

function resetHuanguangQuotaForKeyV2(key) {
  if (key === 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY' || key === 'EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE') resetXxsyunPaymentBalanceV2();
  if (key === 'EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY' || key === 'EXTRACT_LINK_HUANGUANG_API_BASE') resetHuanguangXxsyunQuotaV2();
  Object.entries(CONFIG_HUANGUANG_CDK_QUOTAS_V2).forEach(([kind, quota]) => {
    if (key !== quota.key && key !== 'EXTRACT_LINK_HUANGUANG_API_BASE') return;
    quota.request += 1;
    Object.assign(quota, {loading: false, text: ''});
    syncHuanguangCdkQuotaV2(kind);
  });
}

async function queryHuanguangCdkQuotaV2(button) {
  const kind = button.dataset.queryHuanguangCdkQuota;
  if (!Object.prototype.hasOwnProperty.call(CONFIG_HUANGUANG_CDK_QUOTAS_V2, kind)) return;
  const quota = CONFIG_HUANGUANG_CDK_QUOTAS_V2[kind];
  if (quota.loading) return;
  const input = button.closest('[data-huanguang-cdk-key]')?.querySelector(`[data-key="${quota.key}"]`);
  const pending = [quota.key, 'EXTRACT_LINK_HUANGUANG_API_BASE'].some(key => Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key));
  if (pending || String(input?.value || '').trim() || input?.dataset.secretClear === 'true') {
    quota.text = '请先保存此 CDK 或服务地址的更改，再查询剩余次数';
    syncHuanguangCdkQuotaV2(kind);
    return;
  }
  const request = ++quota.request;
  Object.assign(quota, {loading: true, text: '正在查询剩余次数…'});
  syncHuanguangCdkQuotaV2(kind);
  let inflight = null;
  try {
    // 通用请求层会合并同 URL 的 GET；待旧请求结束后再查询，避免保存后复用旧凭据结果。
    if (quota.inflight) await quota.inflight.catch(() => {});
    if (request !== quota.request) return;
    inflight = api(`/api/extract-link/huanguang/cdk-quota/${kind}`, {method: 'GET'});
    quota.inflight = inflight;
    const result = await inflight;
    if (request !== quota.request) return;
    if (result?.ok !== true) throw result;
    const value = result.quota;
    const validCount = count => count === null || (Number.isSafeInteger(count) && count >= 0);
    if (!value || typeof value.required !== 'boolean' || !validCount(value.remaining) || !validCount(value.reserved)
      || (value.active !== null && typeof value.active !== 'boolean')) throw {code: 'invalid_response'};
    const status = value.active === false ? '已停用' : value.active === true ? '已启用' : '可用状态未知';
    quota.text = value.required
      ? `剩余 ${value.remaining ?? '未知'} 次 · 占用 ${value.reserved ?? '未知'} · ${status}`
      : '平台免计次';
  } catch (error) {
    if (request !== quota.request) return;
    quota.text = huanguangQuotaErrorTextV2(error, quota.label);
  } finally {
    if (quota.inflight === inflight) quota.inflight = null;
    if (request === quota.request) {
      quota.loading = false;
      syncHuanguangCdkQuotaV2(kind);
    }
  }
}

function syncHuanguangXxsyunQuotaV2() {
  const quota = CONFIG_HUANGUANG_XXSYUN_QUOTA_V2;
  document.querySelectorAll('#tab-config [data-query-huanguang-xxsyun-quota]').forEach(button => {
    button.disabled = quota.loading;
    button.textContent = quota.loading ? '正在查询…' : '查询剩余次数';
  });
  document.querySelectorAll('#tab-config [data-huanguang-xxsyun-quota-status]').forEach(status => {
    status.textContent = quota.text;
  });
}

function resetHuanguangXxsyunQuotaV2() {
  CONFIG_HUANGUANG_XXSYUN_QUOTA_REQUEST_V2 += 1;
  Object.assign(CONFIG_HUANGUANG_XXSYUN_QUOTA_V2, {loading: false, text: ''});
  syncHuanguangXxsyunQuotaV2();
}

function syncXxsyunPaymentBalanceV2() {
  const balance = CONFIG_XXSYUN_PAYMENT_BALANCE_V2;
  document.querySelectorAll('#tab-config [data-query-xxsyun-payment-balance]').forEach(button => {
    button.disabled = balance.loading;
    button.textContent = balance.loading ? '正在查询…' : '查询积分';
  });
  document.querySelectorAll('#tab-config [data-xxsyun-payment-balance-status]').forEach(status => {
    status.textContent = balance.text;
  });
}

function resetXxsyunPaymentBalanceV2() {
  CONFIG_XXSYUN_PAYMENT_BALANCE_REQUEST_V2 += 1;
  Object.assign(CONFIG_XXSYUN_PAYMENT_BALANCE_V2, {loading: false, text: ''});
  syncXxsyunPaymentBalanceV2();
}

function xxsyunPaymentBalanceErrorV2(error) {
  const code = String(error?.code || error?.error_code || '').toLowerCase();
  const messages = {
    config_invalid: '积分查询配置无效，请检查服务地址并保存后重试',
    api_key_missing: '未配置 XXSYUN API Key，请填写后重试',
    key_missing: '未配置 XXSYUN API Key，请填写后重试',
    api_key_invalid: 'XXSYUN API Key 无效或已失效，请更新后重试',
    key_invalid: 'XXSYUN API Key 无效或已失效，请更新后重试',
    unauthorized: 'XXSYUN API Key 无效或已失效，请更新后重试',
    unauthenticated: 'XXSYUN API Key 无效或已失效，请更新后重试',
    forbidden: '当前 XXSYUN API Key 无权查询积分',
    employer_pending: 'XXSYUN 平台账号尚未就绪，请在平台检查账号状态',
    password_change_required: 'XXSYUN 平台要求先修改密码，请在平台处理后重试',
    insufficient_quota: 'XXSYUN 积分不足，请在平台检查积分余额',
    rate_limited: '积分查询过于频繁，请稍后重试',
    request_timeout: '积分查询超时，请稍后重试',
    transport_error: '积分查询遇到网络连接异常，请稍后重试',
    invalid_response: '上游积分响应无效，请稍后重试',
    upstream_http_error: '上游服务暂时无法查询积分，请稍后重试',
  };
  return messages[code] || '查询积分失败，请检查 XXSYUN 配置或稍后重试';
}

async function queryXxsyunPaymentBalanceV2(button) {
  const balance = CONFIG_XXSYUN_PAYMENT_BALANCE_V2;
  if (balance.loading) return;
  if (Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, 'EXTRACT_LINK_PAYMENT_XXSYUN_API_BASE')) {
    balance.text = '请先保存服务地址的更改，再查询积分';
    syncXxsyunPaymentBalanceV2();
    return;
  }
  const key = 'EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY';
  const input = button.closest('[data-xxsyun-payment-key]')?.querySelector(`[data-key="${key}"]`);
  const pending = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key);
  const value = String(input?.value ?? (pending ? CONFIG_PENDING_UPDATES[key] : '')).trim();
  const payload = value ? {api_key: value}
    : input?.dataset.secretClear === 'true' || (pending && String(CONFIG_PENDING_UPDATES[key] ?? '').trim() === '')
      ? {api_key: ''} : {};
  const request = ++CONFIG_XXSYUN_PAYMENT_BALANCE_REQUEST_V2;
  Object.assign(balance, {loading: true, text: '正在查询积分…'});
  syncXxsyunPaymentBalanceV2();
  try {
    const result = await api('/api/extract-link/payments/xxsyun/balance', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
    });
    if (request !== CONFIG_XXSYUN_PAYMENT_BALANCE_REQUEST_V2) return;
    if (result?.ok !== true) throw result;
    const values = result.balance;
    const keys = ['available_points', 'pending_points', 'used_points', 'cost_points'];
    const valid = value => value == null || (typeof value === 'number' && Number.isFinite(value) && value >= 0);
    if (!values || typeof values !== 'object' || Array.isArray(values) || !keys.every(key => valid(values[key]))) throw {code: 'invalid_response'};
    const points = value => value == null ? '未知' : `${value} 积分`;
    balance.text = `可用 ${points(values.available_points)} · 预占 ${points(values.pending_points)} · 已用 ${points(values.used_points)} · 每单 ${points(values.cost_points)}`;
  } catch (error) {
    if (request !== CONFIG_XXSYUN_PAYMENT_BALANCE_REQUEST_V2) return;
    balance.text = xxsyunPaymentBalanceErrorV2(error);
  } finally {
    if (request === CONFIG_XXSYUN_PAYMENT_BALANCE_REQUEST_V2) {
      balance.loading = false;
      syncXxsyunPaymentBalanceV2();
    }
  }
}

async function queryHuanguangXxsyunQuotaV2(button) {
  if (CONFIG_HUANGUANG_XXSYUN_QUOTA_V2.loading) return;
  if (Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, 'EXTRACT_LINK_HUANGUANG_API_BASE')) {
    CONFIG_HUANGUANG_XXSYUN_QUOTA_V2.text = '请先保存服务地址的更改，再查询剩余次数';
    syncHuanguangXxsyunQuotaV2();
    return;
  }
  const key = 'EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY';
  const input = button.closest('[data-huanguang-xxsyun-key]')?.querySelector(`[data-key="${key}"]`);
  const pending = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key);
  const value = String(input?.value ?? (pending ? CONFIG_PENDING_UPDATES[key] : '')).trim();
  const payload = value ? {api_key: value}
    : input?.dataset.secretClear === 'true' || (pending && String(CONFIG_PENDING_UPDATES[key] ?? '').trim() === '')
      ? {api_key: ''} : {};
  const request = ++CONFIG_HUANGUANG_XXSYUN_QUOTA_REQUEST_V2;
  Object.assign(CONFIG_HUANGUANG_XXSYUN_QUOTA_V2, {loading: true, text: '正在查询剩余次数…'});
  syncHuanguangXxsyunQuotaV2();
  try {
    const result = await api('/api/extract-link/huanguang/xxsyun-quota', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
    });
    if (request !== CONFIG_HUANGUANG_XXSYUN_QUOTA_REQUEST_V2) return;
    const validCount = value => Number.isSafeInteger(value) && value >= 0;
    if (result?.ok !== true) throw result;
    if (!validCount(result.remainingUses)
      || (result.totalUses != null && !validCount(result.totalUses))
      || (result.reservedUses != null && !validCount(result.reservedUses))) throw {code: 'invalid_response'};
    CONFIG_HUANGUANG_XXSYUN_QUOTA_V2.text = `剩余 ${result.remainingUses} 次 · 总次数 ${result.totalUses ?? '未知'} · 占用 ${result.reservedUses ?? '未知'}`;
  } catch (error) {
    if (request !== CONFIG_HUANGUANG_XXSYUN_QUOTA_REQUEST_V2) return;
    CONFIG_HUANGUANG_XXSYUN_QUOTA_V2.text = huanguangQuotaErrorTextV2(error);
  } finally {
    if (request === CONFIG_HUANGUANG_XXSYUN_QUOTA_REQUEST_V2) {
      CONFIG_HUANGUANG_XXSYUN_QUOTA_V2.loading = false;
      syncHuanguangXxsyunQuotaV2();
    }
  }
}
function renderConfigSettingRowV2(f, controlMarkup = null, options = {}) {
  const control = controlMarkup || renderConfigControlMarkupV2(f);
  const extraClass = options.extraClass ? ` ${options.extraClass}` : '';
  const displayKey = options.displayKey || f.key;
  const fullHelp = String(options.help || f.help || '').trim();
  const shortHelp = fullHelp.replace(/\s+/g, ' ').trim();
  return `
    <div class="config-setting-row-v2${extraClass}" data-config-setting="${attrEsc(displayKey)}">
      <div class="config-setting-copy-v2">
        <div class="config-setting-label-v2">${esc(f.label)} ${renderConfigFieldStatusV2(f)}</div>
        ${shortHelp ? `<p class="config-setting-short-help-v2">${esc(shortHelp)}</p>` : ''}
      </div>
      <div class="config-setting-control-v2">${control}${CONFIG_FIELD_ERRORS_V2[f.key] ? `<p class="config-field-error-v2" role="alert">${esc(CONFIG_FIELD_ERRORS_V2[f.key])}</p>` : ''}</div>
    </div>
  `;
}
function renderConfigPlainFieldV2(f) {
  const help = f.key === 'PLAN_CHECK_COUNTRIES' ? '按选择顺序查询；不选时沿用账号注册国家，不影响注册查套餐。'
    : f.key === 'PROXY_POOL_COUNTRIES' ? '选择额外预热国家；不选时按现有线路策略备货。' : null;
  return renderConfigSettingRowV2(f, null, help ? {help} : {});
}
const PROXY_PROVIDER_CONFIG_V2 = Object.freeze({
  '1024proxy': {label: '1024Proxy', prefix: 'PROXY_1024_'},
  '711proxy': {label: '711Proxy', prefix: 'PROXY_711_'},
});

function renderProxyProviderToolsV2() {
  const provider = PROXY_PROVIDER_CONFIG_V2[proxySourceV2()];
  if (!provider) return '';
  return `
    <div class="config-tool-panel-v2 roxy-workspace-box">
      <div>
        <b>${esc(provider.label)} 本地联调</b>
        <div class="hint">会实际提取并检测 1 个 IP，可能产生少量流量或配额消耗。API 请求会绕过系统代理。</div>
      </div>
      <div class="row">
        <div class="action-cell"><button class="btn" type="button" id="btnTestProxyProviderV2">提取并测试 1 个 IP</button></div>
      </div>
      <div id="proxyProviderTestStatusV2" class="muted" role="status" aria-live="polite" style="font-size:12px;">尚未测试</div>
    </div>
  `;
}

function bindProxyProviderToolsV2() {
  const btn = $('#btnTestProxyProviderV2');
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = '1';
  btn.addEventListener('click', testProxyProviderV2);
}

async function testProxyProviderV2() {
  const btn = $('#btnTestProxyProviderV2');
  const status = $('#proxyProviderTestStatusV2');
  const source = proxySourceV2();
  const provider = PROXY_PROVIDER_CONFIG_V2[source];
  if (!provider) return;
  const value = (key, fallback = '') => {
    const el = document.querySelector(`#configSectionsV2 [data-key="${key}"]`);
    return el ? readConfigElementValue(el, CONFIG.find(x => x.key === key)) : configFieldValueV2(key, fallback);
  };
  if (btn) { btn.disabled = true; btn.textContent = '正在测试...'; }
  if (status) status.textContent = '正在提取并检测代理...';
  try {
    const r = await api('/api/proxy-provider/test', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        provider: source,
        api_url: value(`${provider.prefix}API_URL`),
        region: configFieldValueV2('PROXY_POOL_DEFAULT_COUNTRY', 'JP'),
        protocol: value(`${provider.prefix}PROTOCOL`, 'http'),
        session_minutes: value(`${provider.prefix}SESSION_MINUTES`, 30),
        ...(source === '1024proxy' ? {validate: value('PROXY_1024_VALIDATE', true)} : {}),
      }),
    });
    const l = r.lease || {};
    if (status) status.innerHTML = `测试成功 · ${esc(l.provider || provider.label)} · ${esc(l.endpoint || '-')} · 出口 ${esc(l.exit_ip || '-')} · ${esc(l.region || '-')} · 有效至 ${esc(l.expires_at || '-')}`;
    showToast(r.message || '代理测试成功');
  } catch(e) {
    if (status) status.innerHTML = `<span style="color:var(--red);">测试失败：${esc(e.message)}</span>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '提取并测试 1 个 IP'; }
  }
}
function renderMixedConfigSectionV2(name, fields, intro, toolsMarkup = '') {
  const slug = configGroupSlug(name);
  const switches = fields.filter(f => f.type === 'bool');
  const inputs = fields.filter(f => f.type !== 'bool');
  const extra = name === 'RoxyBrowser' ? renderRoxyWorkspaceToolsV2() : toolsMarkup;
  return `
    <section class="config-section-v2" id="${esc(slug)}" data-config-section="${esc(name)}">
      ${renderConfigSectionHead(name, intro || '')}
      ${extra}
      ${switches.length ? `<div class="config-switches-v2">${switches.map(f => renderFeatureSwitchField(f, { withIcon: false })).join('')}</div>` : ''}
      ${inputs.length ? `<div class="config-section-v2-body">${inputs.map(renderConfigPlainFieldV2).join('')}</div>` : ''}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderExtractLinkProviderSelectionV2(providers) {
  const selected = providers
    .filter(provider => extractLinkProviderSelectionValueV2(configFieldValueV2(provider.enabledKey, false)))
    .map(provider => provider.value);
  const field = {
    key: 'EXTRACT_LINK_ENABLED_PROVIDERS', label: '启用平台', type: 'list_str_multiline',
    value: selected.join(','), options: providers.map(provider => ({value: provider.value, label: provider.label})),
    help: '选择允许在提链工作台中使用的平台；取消选择不会清除该平台的地址或 CDK。',
  };
  CONFIG_MULTI_PICKER_FIELDS_V2.set(field.key, field);
  return `<div class="config-section-v2-body">${renderConfigSettingRowV2(field, renderConfigMultiSelectV2(field, field.value))}</div>`;
}

function renderExtractLinkSectionV2(fields) {
  const providers = extractLinkProviderOptionsV2(fields);
  const sections = ['通用配置', ...providers.map(provider => provider.label), '独立支付'];
  let active = CONFIG_EXTRACT_LINK_ACTIVE_SECTION_V2;
  if (!sections.includes(active)) active = sections[0];
  CONFIG_EXTRACT_LINK_ACTIVE_SECTION_V2 = active;

  const providerEnabledKeys = new Set(providers.map(provider => provider.enabledKey));
  const providerFieldMatches = field => providers.some(provider =>
    extractLinkProviderFieldBelongsV2(field, provider.value));
  const commonFields = fields.filter(field =>
    !providerEnabledKeys.has(field.key) && !providerFieldMatches(field) && !field.key.startsWith('EXTRACT_LINK_PAYMENT_'));
  const selectedProvider = providers.find(provider => provider.label === active);
  const independentPayment = active === '独立支付';
  const pageFields = independentPayment ? fields.filter(field => field.key.startsWith('EXTRACT_LINK_PAYMENT_')) : selectedProvider
    ? fields.filter(field => extractLinkProviderFieldBelongsV2(field, selectedProvider.value))
    : commonFields;
  const switches = pageFields.filter(field => field.type === 'bool');
  const inputs = pageFields.filter(field => field.type !== 'bool');
  const body = selectedProvider || independentPayment
    ? `${switches.length ? `<div class="config-switches-v2">${switches.map(field => renderFeatureSwitchField(field, {withIcon: false})).join('')}</div>` : ''}
       ${inputs.length ? `<div class="config-section-v2-body">${inputs.map(renderConfigPlainFieldV2).join('')}</div>` : ''}`
    : `${renderExtractLinkProviderSelectionV2(providers)}
       ${switches.length ? `<div class="config-switches-v2">${switches.map(field => renderFeatureSwitchField(field, {withIcon: false})).join('')}</div>` : ''}
       ${inputs.length ? `<div class="config-section-v2-body">${inputs.map(renderConfigPlainFieldV2).join('')}</div>` : ''}`;

  return `
    <section class="config-section-v2" id="${esc(configGroupSlug('提链'))}" data-config-section="提链">
      ${renderConfigSectionHead('提链', configSectionIntro('提链'))}
      <div class="config-subtabs-v2" role="group" aria-label="提链配置分类">
        ${sections.map(section => `<button type="button" data-extract-link-tab="${attrEsc(section)}" class="${section === active ? 'active' : ''}" aria-pressed="${section === active}">${esc(section)}</button>`).join('')}
      </div>
      ${body}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function codexOauthDriverChoices() {
  return configSchemaOptions(configSchemaField('CODEX_OAUTH_DRIVER'));
}
function codexOauthDriverLabel(value) {
  const cur = String(value || '').trim().toLowerCase();
  const hit = codexOauthDriverChoices().find(c => String(c.value) === cur);
  return hit ? String(hit.label || hit.value) : (cur || '—');
}
function renderCodexFieldV2(f) {
  if (f.type === 'bool') return renderFeatureSwitchField(f, { withIcon: false });
  return renderConfigPlainFieldV2(f);
}

function renderProxyActionFieldsV2(fields) {
  const known = new Set(CONFIG_PROXY_FEATURES_V2.flatMap(([, keys]) => keys));
  const groups = CONFIG_PROXY_FEATURES_V2.map(([title, keys]) => [title, orderedConfigFieldsV2(fields, keys)]);
  groups.push(['其他账号动作', fields.filter(field => !known.has(field.key))]);
  return `<div class="config-proxy-features-v2">${groups.filter(([, items]) => items.length).map(([title, items]) => `
    <section class="config-proxy-feature-v2" data-config-proxy-feature="${attrEsc(title)}">
      <h4>${esc(title)}</h4>
      <div class="config-section-v2-body">${items.map(renderConfigPlainFieldV2).join('')}</div>
    </section>`).join('')}</div>`;
}

function renderProxyTaskPoolSummaryV2() {
  const rows = [
    ['注册与账号认证', '注册主链路的注册国家；账号认证沿用账号历史国家', '独占租约'],
    ['查询套餐', '业务国家顺序（逐国申请）', '按池用途策略复用'],
    ['查活', '账号历史国家；缺失时使用池默认国家', '认证链路保持同一线路'],
    ['刷新 AT', '优先使用独立的 AT 刷新国家；留空时跟随账号注册国家', '单次登录保持同线；网络故障换线重新登录'],
    ['补密码 / 2FA / 换绑 / Codex', '账号历史国家；缺失时使用池默认国家', '独占租约'],
  ];
  return `<div class="config-proxy-pool-summary-v2" aria-label="任务用池规则">
    <div class="config-proxy-pool-table-v2"><div class="config-proxy-pool-head-v2"><span>任务</span><span>国家需求</span><span>领取规则</span></div>${rows.map(row => `<div class="config-proxy-pool-row-v2">${row.map(cell => `<span>${esc(cell)}</span>`).join('')}</div>`).join('')}</div>
  </div>`;
}

function renderConfigLegacyProxyFieldsV2(fields) {
  return `<div class="config-legacy-list-v2">${fields.map(field => `<div class="config-legacy-row-v2"><span>${esc(field.label || field.key)}</span><code>${esc(field.key)}</code><span>兼容保留</span></div>`).join('')}</div>`;
}

function proxySourceV2() {
  return String(configFieldValueV2('PROXY_POOL_SOURCE', '1024proxy')).trim().toLowerCase();
}

function proxySourceIsManualV2() {
  return proxySourceV2() === 'manual';
}

function proxySourceFieldVisibleV2(field) {
  if (CONFIG_NAV_QUERY_V2.trim()) return true;
  if (field.key === 'PROXY_POOL') return proxySourceIsManualV2();
  const source = Object.entries(PROXY_PROVIDER_CONFIG_V2).find(([, provider]) => String(field.key || '').startsWith(provider.prefix));
  if (source) return proxySourceV2() === source[0];
  return true;
}

function renderSectionedConfigSectionV2(name, fields, sectionForKey, preferred, activeRef, dataAttr) {
  const slug = configGroupSlug(name);
  const bySection = {};
  for (const f of fields) {
    const [section, help] = sectionForKey(f.key || '');
    if (!bySection[section]) bySection[section] = { help, fields: [] };
    bySection[section].fields.push(f);
  }
  let sections = name === '代理与网络'
    ? preferred.filter(x => x === '任务用池' || bySection[x]).concat(Object.keys(bySection).filter(x => !preferred.includes(x)))
    : preferred.filter(x => bySection[x]).concat(Object.keys(bySection).filter(x => !preferred.includes(x)));
  if (name === '邮箱 / OTP' && !CONFIG_NAV_QUERY_V2.trim()) {
    sections = sections.filter(section => emailSectionEnabledV2(section));
  }
  let active = activeRef.get();
  if (!sections.includes(active)) {
    active = sections[0] || '';
    activeRef.set(active);
  }
  const current = bySection[active] || { help: '', fields: [] };
  const visibleFields = name === '代理与网络' && active === '代理来源'
    ? current.fields.filter(proxySourceFieldVisibleV2)
    : current.fields;
  const switches = visibleFields.filter(f => f.type === 'bool');
  const inputs = visibleFields.filter(f => f.type !== 'bool');
  const sourcePrimaryKeys = new Set(['PROXY_POOL_SOURCE', 'PROXY_POOL_DEFAULT_COUNTRY', 'PROXY_POOL', ...Object.values(PROXY_PROVIDER_CONFIG_V2).flatMap(provider => ['API_URL', 'PROTOCOL', 'SESSION_MINUTES'].map(key => `${provider.prefix}${key}`))]);
  const sourcePrimary = visibleFields.filter(f => sourcePrimaryKeys.has(f.key));
  const sourceAdvanced = visibleFields.filter(f => !sourcePrimaryKeys.has(f.key));
  const body = name === '代理与网络' && active === '任务用池'
    ? renderProxyTaskPoolSummaryV2()
    : name === '代理与网络' && active === '高级兼容'
    ? renderConfigLegacyProxyFieldsV2(current.fields)
    : name === '代理与网络' && active === '代理来源'
    ? `<div class="config-section-v2-body">${sourcePrimary.map(renderConfigPlainFieldV2).join('')}</div>${sourceAdvanced.length ? `<details class="config-source-advanced-v2"${CONFIG_NAV_QUERY_V2.trim() ? ' open' : ''}><summary>高级提取与检测参数</summary><div class="config-section-v2-body">${sourceAdvanced.map(renderConfigPlainFieldV2).join('')}</div></details>` : ''}`
    : name === '代理与网络' && active === '账号动作线路'
    ? renderProxyActionFieldsV2(current.fields)
    : `${switches.length ? `<div class="config-switches-v2">${switches.map(f => renderFeatureSwitchField(f, { withIcon: false })).join('')}</div>` : ''}
       ${inputs.length ? `<div class="config-section-v2-body">${inputs.map(renderConfigPlainFieldV2).join('')}</div>` : ''}`;
  let extra = '';
  if (name === '邮箱 / OTP' && active === 'Email Butler') {
    extra = renderEmailButlerToolsV2();
  }
  if (name === '邮箱 / OTP' && active === 'iCloud 隐藏邮箱') {
    extra = renderICloudHMEToolsV2();
  }
  if (name === '代理与网络' && active === '代理来源' && !proxySourceIsManualV2()) {
    extra = renderProxyProviderToolsV2();
  }
  return `
    <section class="config-section-v2" id="${esc(slug)}" data-config-section="${esc(name)}">
      ${renderConfigSectionHead(name, '')}
      <div class="config-subtabs-v2">
        ${sections.map(section => `
          <button type="button" data-${dataAttr}="${esc(section)}" class="${section === active ? 'active' : ''}">
            ${esc(section)}
          </button>
        `).join('')}
      </div>
      ${body}
      ${extra}
      ${renderConfigSaveActions()}
    </section>
  `;
}
function renderEmailButlerToolsV2() {
  const hasButler = CONFIG.some(f => String(f.key || '').startsWith('EMAIL_BUTLER_'));
  if (!hasButler) return '';
  return `
    <div class="config-tool-panel-v2 roxy-workspace-box">
      <div>
        <b>Email Butler 连接</b>
        <div class="hint">验证当前连接、OpenAI 服务和租用、收码权限，不会领取邮箱。</div>
      </div>
      <div class="action-cell">
        <button class="btn primary" type="button" id="btnTestEmailButlerV2">测试连接</button>
      </div>
      <div id="emailButlerStatusV2" class="muted" style="font-size:12px;">尚未检测</div>
    </div>
  `;
}
function bindEmailButlerToolsV2() {
  const btn = $('#btnTestEmailButlerV2');
  if (btn && !btn.dataset.bound) {
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => testEmailButlerV2());
  }
}
async function testEmailButlerV2() {
  const btn = $('#btnTestEmailButlerV2');
  const status = $('#emailButlerStatusV2');
  if (!btn || !status) return;
  btn.disabled = true;
  status.textContent = '正在检测 Email Butler 连接与权限…';
  try {
    const r = await api('/api/email-butler/test-connection', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        api_base: _configValueV2('EMAIL_BUTLER_API_BASE').trim(),
        api_key: _configValueV2('EMAIL_BUTLER_API_KEY').trim(),
      }),
    });
    const policy = [r.consumer, r.service].filter(Boolean).join(' / ') || '未绑定策略';
    const missing = r.missing_permissions || [];
    status.textContent = missing.length
      ? `连接成功，权限尚未齐全：${missing.join('、')}。请在 Butler 为原客户端补充权限。`
      : `连接成功：${r.name || 'Email Butler'} · ${policy}`;
    showToast(missing.length ? '连接成功，请补充所需权限' : 'Email Butler 连接成功');
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">连接失败：${esc(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}
function renderICloudHMEToolsV2() {
  return `<div class="config-tool-panel-v2 roxy-workspace-box"><b>固定收件连接</b>
    <div class="hint">邮箱账号、创建和库存由邮箱服务管理。Turb 使用已导入的完整邮箱地址；下方配置保留历史收码链路。使用 Email Butler 时可在其配置页测试连接。</div></div>`;
}
function _configValueV2(key) {
  const root = document.querySelector(`#configSectionsV2 [data-key="${CSS.escape(key)}"]`);
  if (root) return root.value;
  const f = CONFIG.find(x => x.key === key);
  return f ? String(f.value ?? '') : '';
}
function renderSentinelMaintenanceContentV2() {
  const state = CONFIG_SENTINEL_MAINTENANCE_V2;
  const snapshot = state.snapshot;
  const candidate = snapshot?.candidate;
  const busy = state.posting || snapshot?.running;
  const comparison = {
    not_checked: '尚未检查', same: '同当前一致', version_changed: '发现新版本',
    content_changed: '同版本内容变化', unknown: '暂无法比较',
  }[snapshot?.comparison || 'not_checked'] || '暂无法比较';
  const staticLabel = value => ({
    static_markers_present: '通过（未运行验证）', needs_adaptation: '需要适配',
  }[value] || '尚未检查');
  const checkedAt = Number(snapshot?.last_checked_at);
  const checkedTime = checkedAt > 0 && Number.isFinite(checkedAt)
    ? new Date(checkedAt * 1000).toLocaleString('zh-CN', {hour12: false}) : '尚未检查';
  const status = state.error || (busy ? '正在检查 Sentinel 更新…'
    : state.loading ? '正在读取检查状态…'
      : ({
        never: '尚未检查', refreshed: '检查完成；候选资源尚未运行验证。', cached: '检查完成；候选资源尚未运行验证。',
        stale: '候选资源已过期，可重新检查。', missing: '尚无候选资源，可手动检查。',
        corrupt: '候选资源不可用，请重新检查。', failed: '检查失败，请重试。',
      }[snapshot?.last_status] || '尚未检查'));
  return `<div class="config-setting-group-head-v2">Sentinel 检查</div>
    <div class="config-setting-list-v2" aria-busy="${busy || state.loading ? 'true' : 'false'}">
      <div class="config-setting-row-v2">
        <div class="config-setting-copy-v2">
          <div class="config-setting-label-v2">检查 Sentinel 更新</div>
          <p class="config-setting-help-v2">手动获取候选资源；不自动切换现用版本。</p>
        </div>
        <div class="config-setting-control-v2">
          <button type="button" class="btn" data-sentinel-maintenance-action="check"${busy || state.loading ? ' disabled' : ''}>${busy ? '检查中…' : '检查 Sentinel 更新'}</button>
        </div>
      </div>
      <div class="config-setting-row-v2 config-setting-row-v2--readonly">
        <div class="config-setting-copy-v2">
          <div class="config-setting-label-v2">当前内置版本 <span class="config-field-status-v2">${esc(snapshot?.builtin?.version || '读取后显示')}</span></div>
          <p class="config-setting-help-v2">发现版本：${esc(candidate?.version || '尚未发现')}</p>
          <p class="config-setting-help-v2">上次检查时间：${esc(checkedTime)}</p>
        </div>
        <div class="config-setting-control-v2">
          <div class="config-setting-readonly-v2">
            <strong>${esc(comparison)}</strong>
            <span>generic 静态检查：${esc(staticLabel(candidate?.generic_status))}</span>
            <span>Proto2 静态检查：${esc(staticLabel(candidate?.proto2_status))}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="config-setting-help-v2" role="status" aria-live="polite">${esc(status)}${state.error ? ` <button type="button" class="btn" data-sentinel-maintenance-action="retry"${state.posting || state.loading ? ' disabled' : ''}>重试</button>` : ''}</div>`;
}
function renderSentinelMaintenanceV2() {
  return `<div class="config-setting-group-v2" data-sentinel-maintenance>${renderSentinelMaintenanceContentV2()}</div>`;
}
function sentinelMaintenanceIsVisibleV2() {
  const tab = document.getElementById('tab-config');
  return !!document.querySelector('#configSectionsV2 [data-sentinel-maintenance]')
    && !!tab && !tab.classList.contains('hidden') && !document.hidden;
}
function updateSentinelMaintenanceV2() {
  const panel = document.querySelector('#configSectionsV2 [data-sentinel-maintenance]');
  if (panel) panel.innerHTML = renderSentinelMaintenanceContentV2();
}
function scheduleSentinelMaintenanceV2() {
  const state = CONFIG_SENTINEL_MAINTENANCE_V2;
  if (state.timer !== null) clearTimeout(state.timer);
  state.timer = null;
  if (!state.visible || !sentinelMaintenanceIsVisibleV2() || !state.snapshot?.running
    || state.loading || state.posting || state.error) return;
  state.timer = setTimeout(() => {
    state.timer = null;
    return querySentinelMaintenanceV2('status');
  }, 1500);
}
async function querySentinelMaintenanceV2(action = 'status') {
  const state = CONFIG_SENTINEL_MAINTENANCE_V2;
  const check = action === 'check';
  if (!state.visible || !sentinelMaintenanceIsVisibleV2() || state.posting
    || (check ? state.snapshot?.running : state.loading)) return;
  const request = ++state.request;
  if (state.timer !== null) clearTimeout(state.timer);
  state.timer = null;
  state.loading = !check;
  state.posting = check;
  state.error = '';
  state.retryAction = action;
  updateSentinelMaintenanceV2();
  try {
    const result = await api(check ? '/api/maintenance/sentinel/check' : '/api/maintenance/sentinel', check
      ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'} : {});
    if (request !== state.request) return;
    if (!result?.ok) throw new Error('sentinel_status_unavailable');
    if (check && result.accepted && result.task_id) {
      trackAcceptedOperationsV2([result], 'Sentinel 检查');
    }
    const previous = state.snapshot;
    state.snapshot = {
      ...result,
      candidate: result.candidate || previous?.candidate || null,
      comparison: !result.candidate && previous?.candidate ? previous.comparison : result.comparison,
    };
    if (!result.running && (['failed', 'corrupt'].includes(result.last_status) || result.error_code)) {
      state.error = result.last_status === 'corrupt' ? '候选资源不可用，请重试。' : '检查失败，请重试。';
      state.retryAction = 'check';
    }
  } catch (error) {
    if (request !== state.request) return;
    state.error = check ? '检查请求未完成，请重试。' : '状态读取失败，请重试。';
  } finally {
    if (request === state.request) {
      state.loading = false;
      state.posting = false;
      updateSentinelMaintenanceV2();
      scheduleSentinelMaintenanceV2();
    }
  }
}
function syncSentinelMaintenanceV2() {
  const state = CONFIG_SENTINEL_MAINTENANCE_V2;
  const visible = sentinelMaintenanceIsVisibleV2();
  const entered = visible && !state.visible;
  state.visible = visible;
  if (!visible) {
    if (state.timer !== null) clearTimeout(state.timer);
    state.timer = null;
    if (state.loading) {
      state.request += 1;
      state.loading = false;
    }
    return;
  }
  updateSentinelMaintenanceV2();
  if (entered && !state.posting) querySentinelMaintenanceV2('status');
}
function bindSentinelMaintenanceV2() {
  const state = CONFIG_SENTINEL_MAINTENANCE_V2;
  const tab = document.getElementById('tab-config');
  if (tab && !state.observer) {
    state.observer = new MutationObserver(syncSentinelMaintenanceV2);
    state.observer.observe(tab, {attributes: true, attributeFilter: ['class', 'hidden']});
    document.addEventListener('visibilitychange', syncSentinelMaintenanceV2);
  }
  syncSentinelMaintenanceV2();
}
function renderSub2ApiAutomationToolsV2() {
  return `<div class="config-tool-panel-v2">
    <div><b>同步与异常巡检</b><p class="hint">使用已保存配置检查远端异常账号，修复进度可在任务中心查看。</p></div>
    <div class="config-inline-row">
      <button type="button" class="btn" data-sub2api-automation="status">查看状态</button>
      <button type="button" class="btn" data-sub2api-automation="check">立即巡检</button>
    </div>
    <p class="config-setting-short-help-v2" data-sub2api-automation-status role="status" aria-live="polite">尚未查询</p>
  </div>`;
}
async function querySub2ApiAutomationV2(button) {
  const panel = button.closest('.config-tool-panel-v2');
  const status = panel.querySelector('[data-sub2api-automation-status]');
  const buttons = panel.querySelectorAll('button');
  buttons.forEach(item => { item.disabled = true; });
  status.textContent = '正在查询…';
  try {
    if (button.dataset.sub2apiAutomation === 'check') {
      const result = await api('/api/sub2api/automation/check', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
      if (!result.ok) throw new Error(result.error || '巡检未完成');
      if (result.accepted) {
        status.textContent = `异常扫描已入队 · 任务 #${result.task_id}，最终结果在任务回执中更新。`;
        trackAcceptedOperationsV2([result], 'Sub2API 异常扫描');
        return;
      }
      const summary = result.result || {};
      const labels = {
        account_busy: '账号忙碌', cooldown: '冷却中', account_archived: '账号已归档', account_deactivated: '账号已停用',
        automatic_login_material_missing: '自动登录资料不足', unrecognized_remote_error: '远端错误原因未识别',
        remote_transient_error: '远端网络或限流错误', needs_reconciliation: '上次请求结果待核实', repair_in_progress: '修复进行中',
      };
      const reasons = Object.entries(summary.reasons || {}).map(([code, count]) => `${labels[code] || code} ${count}`).join('，');
      status.textContent = `本轮检查 ${summary.remote_errors || 0} 条异常记录，已调度同步 ${summary.sync_queued || 0}、刷新 ${summary.refresh_queued || 0}、重授权 ${summary.reauth_queued || 0}。${reasons ? `处理说明：${reasons}。` : ''}`;
    } else {
      const result = await api('/api/sub2api/automation');
      if (!result.ok) throw new Error(result.error || '状态读取失败');
      const counts = result.sync?.counts || {};
      status.textContent = `自动补传${result.sync?.enabled ? '已开启' : '已关闭'}；异常巡检${result.monitor?.enabled ? '已开启' : '已关闭'}。待同步 ${counts.pending || 0}，排队 ${counts.queued || 0}，执行 ${counts.running || 0}。`;
    }
  } catch (error) {
    status.textContent = error.message || '查询未完成，请稍后重试';
  } finally {
    buttons.forEach(item => { item.disabled = false; });
  }
}
function renderCodexSectionV2(fields) {
  const slug = configGroupSlug('Codex');
  const preferred = ['基础配置', 'CPA配置', 'sub2api'];
  const bySection = {};
  for (const f of fields) {
    const [section, help] = codexConfigSectionForKey(f.key || '');
    if (!bySection[section]) bySection[section] = { help, fields: [] };
    bySection[section].fields.push(f);
  }
  const sections = preferred.filter(x => bySection[x]).concat(Object.keys(bySection).filter(x => !preferred.includes(x)));
  if (!sections.includes(CONFIG_CODEX_ACTIVE_SECTION_V2)) {
    CONFIG_CODEX_ACTIVE_SECTION_V2 = sections[0] || '基础配置';
  }
  const active = CONFIG_CODEX_ACTIVE_SECTION_V2;
  const current = bySection[active] || { help: '', fields: [] };
  const switches = current.fields.filter(f => f.type === 'bool' && f.key !== 'CODEX_OAUTH_DRIVER');
  const inputs = current.fields.filter(f => f.type !== 'bool' || f.key === 'CODEX_OAUTH_DRIVER');
  // Keep driver in inputs area first
  const orderedInputs = [];
  const driver = current.fields.find(f => f.key === 'CODEX_OAUTH_DRIVER');
  if (driver) orderedInputs.push(driver);
  current.fields.forEach(f => {
    if (f.key === 'CODEX_OAUTH_DRIVER') return;
    if (f.type === 'bool') return;
    orderedInputs.push(f);
  });
  return `
    <section class="config-section-v2" id="${esc(slug)}" data-config-section="Codex">
      ${renderConfigSectionHead('Codex', '')}
      <div class="config-subtabs-v2">
        ${sections.map(section => `
          <button type="button" data-codex-section-v2="${esc(section)}" class="${section === active ? 'active' : ''}">
            ${esc(section)}
          </button>
        `).join('')}
      </div>
      ${switches.length ? `<div class="config-switches-v2">${switches.map(f => renderFeatureSwitchField(f, { withIcon: false })).join('')}</div>` : ''}
      ${orderedInputs.length ? `<div class="config-section-v2-body">${orderedInputs.map(renderCodexFieldV2).join('')}</div>` : ''}
      ${active === 'sub2api' ? renderSub2ApiAutomationToolsV2() : ''}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderScheduledConfigSectionV2(fields) {
  const sections = [
    ['Email Butler 风险扫描', fields.filter(f => f.key.startsWith('EMAIL_BUTLER_'))],
    ['ChatGPT AT 自动刷新', fields.filter(f => f.key.startsWith('AT_'))],
    ['Codex Token 自动刷新', fields.filter(f => f.key.startsWith('CODEX_TOKEN_'))],
    ['sub2api 同步与异常巡检', fields.filter(f => f.key.startsWith('SUB2API_'))],
  ];
  const known = new Set(sections.flatMap(([, items]) => items.map(f => f.key)));
  return `
    <section class="config-section-v2" id="${esc(configGroupSlug('定时任务'))}" data-config-section="定时任务">
      ${renderConfigSectionHead('定时任务', configSectionIntro('定时任务'))}
      ${sections.map(([title, items]) => renderConfigSettingGroupV2(title, items)).join('')}
      ${renderConfigSettingGroupV2('其他定时任务', fields.filter(f => !known.has(f.key)))}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function concurrencyFieldV2(field) {
  return field?.group === '并发控制' && field.key !== 'CONCURRENCY_POLICY_REVISION';
}

function concurrencyFieldErrorV2(value) {
  const text = String(value ?? '').trim();
  return /^\d+$/.test(text) && /[1-9]/.test(text) ? '' : '请填写不小于 1 的整数；暂停请使用任务暂停或取消。';
}

function concurrencyWaitTextV2(reason) {
  const code = typeof reason === 'string' ? reason : reason?.code || reason?.reason || '';
  const count = typeof reason === 'object' && reason?.occupied != null && reason?.limit != null
    ? `（${reason.occupied}/${reason.limit}）` : '';
  const labels = {
    executor_capacity: '等待执行承载空位', resource_capacity: '等待业务资源空位',
    global_capacity: '等待全局空位', type_capacity: '等待本类空位',
    batch_capacity: '等待当前批次空位', provider_capacity: '等待平台空位',
    account_busy: '账号正由其他任务使用', remote_order_capacity: '等待远端订单名额',
    not_due: '等待下次平台查询', concurrency_policy_migration_required: '等待确认并发迁移策略',
    scheduler_store_unavailable: '调度存储暂不可用', permit_owner_lost: '执行所有者待核验',
    execution_active: '上一执行仍在退出或清理', fairness_turn: '等待公平调度轮次',
  };
  return labels[code] ? labels[code] + count : `等待原因待核验（${code || '缺少原因代码'}）`;
}

function concurrencyTypeV2(key) {
  return (CONFIG_CONCURRENCY_V2.snapshot?.types || []).find(item => item.config_key === key || item.key === key);
}

function renderConcurrencyFieldV2(field, global = false) {
  const id = `concurrency-${field.key}`;
  const value = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, field.key)
    ? CONFIG_PENDING_UPDATES[field.key] : field.value;
  const error = CONFIG_FIELD_ERRORS_V2[field.key] || '';
  return `<div class="config-concurrency-row-v2${global ? ' config-concurrency-row-v2--global' : ''}" data-config-setting="${attrEsc(field.key)}">
    <div class="config-concurrency-copy-v2"><label for="${id}">${esc(field.label)}</label>
      <p id="${id}-help" class="hint">${esc(field.help || '')}</p>
      ${global ? '' : `<p class="hint" data-concurrency-effective="${attrEsc(field.key)}"></p>`}
    </div>
    <div class="config-setting-control-v2"><input id="${id}" type="number" inputmode="numeric" min="1" step="1" required data-key="${attrEsc(field.key)}" value="${attrEsc(value)}" aria-describedby="${id}-help ${id}-error" aria-invalid="${!!error}">
      <p id="${id}-error" class="config-field-error-v2" role="alert"${error ? '' : ' hidden'}>${esc(error)}</p>
    </div>
    ${global ? '' : `<div class="config-concurrency-row-state-v2" data-concurrency-type="${attrEsc(field.key)}">
      <span data-concurrency-count>占用 — · 排队 —</span>
      <details data-concurrency-reasons hidden><summary data-concurrency-primary>等待原因</summary><p class="hint" data-concurrency-reason-list></p></details>
      <button type="button" class="btn" data-concurrency-tasks="${attrEsc(field.key)}" aria-label="${field.key.startsWith('REGISTRATION_') ? '查看注册任务' : `定位${attrEsc(field.label)}任务`}">${field.key.startsWith('REGISTRATION_') ? '查看注册任务' : '定位任务'}</button>
    </div>`}
  </div>`;
}

function renderConcurrencyErrorsV2() {
  const errors = Object.entries(CONFIG_FIELD_ERRORS_V2).filter(([key]) => concurrencyFieldV2(configSchemaField(key)));
  return `<div id="configConcurrencyErrorsV2" class="config-concurrency-errors-v2" tabindex="-1" role="alert"${errors.length ? '' : ' hidden'}>
    <strong>请检查 ${errors.length} 项并发设置，草稿已保留</strong>
    <ul>${errors.map(([key, reason]) => `<li><button type="button" data-concurrency-error-key="${attrEsc(key)}">${esc(configSchemaField(key)?.label || key)}：${esc(reason)}</button></li>`).join('')}</ul>
  </div>`;
}

function renderConcurrencyConfigSectionV2(fields) {
  const global = fields.find(field => field.key === 'GLOBAL_TASK_WORKERS');
  const types = fields.filter(field => concurrencyFieldV2(field) && field.key !== 'GLOBAL_TASK_WORKERS');
  return `<section class="config-section-v2" id="${configGroupSlug('并发控制')}" data-config-section="并发控制">
    ${renderConfigSectionHead('并发控制', configSectionIntro('并发控制'))}
    ${renderConcurrencyErrorsV2()}
    <div class="config-concurrency-toolbar-v2"><p class="hint" data-concurrency-scope>正在读取部署范围与策略版本…</p>
      <button type="button" class="btn" data-concurrency-refresh>刷新状态</button></div>
    <div class="config-concurrency-migration-v2" data-concurrency-migration hidden>
      <strong data-concurrency-migration-title>请先确认迁移策略</strong><p class="hint" data-concurrency-migration-notes></p>
      <button type="button" class="btn" data-concurrency-use-preview>将迁移建议填入草稿</button>
      <p class="hint">填入草稿后请核对全局和各类型上限，再点击保存；预览与填入草稿均不会修改运行配置。</p>
    </div>
    <div class="config-concurrency-summary-v2" role="status" aria-live="polite" aria-atomic="true" data-concurrency-summary>正在读取当前占用…</div>
    <p class="hint config-concurrency-status-error-v2" data-concurrency-error hidden></p>
    ${global ? renderConcurrencyFieldV2(global, true) : ''}
    <div class="config-setting-group-v2"><div class="config-setting-group-head-v2">各独立任务类型</div>
      <p class="config-section-v2-subhelp">各类型上限是上限，不预留配额，合计可以超过全局。内部同步刷新 AT、查套餐与后处理归属巡检、提链或注册父任务，复用父任务许可；独立子任务按实际动作重新排队。</p>
      <div class="config-concurrency-types-v2">${types.map(field => renderConcurrencyFieldV2(field)).join('')}</div>
    </div>
    <details class="config-concurrency-details-v2" data-concurrency-details><summary>业务附加限制与计量说明</summary>
      <p class="hint">注册批次并发填写正整数，提链批次与平台保留 1–50；它们与全局、类型限制同时生效。XXSYUN 未结束订单名额在远端等待时仍占用，本地查询间隔不占执行槽。调试保留、停止清理和已预约执行仍计入占用。</p>
      <p class="hint">账号补全等待独立子任务时不重复占全局槽；HME 合并扫描按一个扫描 Run 计数；邮箱导入按实际远端交接调用计数。Sub2API 远端账号并发属性在服务集成中维护。</p>
      <div data-concurrency-details-status class="hint"></div>
      <button type="button" class="btn" data-concurrency-load-details>查看当前平台、批次与订单限制</button>
    </details>
    ${renderConfigSaveActions()}
  </section>`;
}

function concurrencyIsVisibleV2() {
  const tab = document.getElementById('tab-config');
  return !!document.querySelector('#configSectionsV2 [data-config-section="并发控制"]')
    && !!tab && !tab.classList.contains('hidden') && !document.hidden;
}

function updateConcurrencyStatusV2() {
  const root = document.querySelector('#configSectionsV2 [data-config-section="并发控制"]');
  if (!root) return;
  const state = CONFIG_CONCURRENCY_V2;
  const snapshot = state.snapshot;
  const set = (selector, value) => { const node = root.querySelector(selector); if (node && node.textContent !== value) node.textContent = value; };
  const error = root.querySelector('[data-concurrency-error]');
  if (error) { error.hidden = !state.error; error.textContent = state.error; }
  const refresh = root.querySelector('[data-concurrency-refresh]');
  if (refresh) { refresh.disabled = state.loading; refresh.textContent = state.loading ? '刷新中…' : '刷新状态'; }
  const preview = state.preview;
  const migration = root.querySelector('[data-concurrency-migration]');
  if (migration) {
    const required = preview?.migration_required || snapshot?.migration_required;
    migration.hidden = !required;
    const button = migration.querySelector('[data-concurrency-use-preview]');
    if (button) button.disabled = !preview;
    set('[data-concurrency-migration-notes]', preview ? `历史账号池上限：${preview.legacy_account_workers ?? '未记录'}。${(preview.notes || []).join(' ')}` : '新策略尚未完整保存。请刷新预览后确认全局上限；新任务会保留排队。');
  }
  if (!snapshot) return;
  const global = snapshot.global || {};
  const scope = typeof snapshot.scope === 'object' ? snapshot.scope.label || snapshot.scope.name || snapshot.scope.schema || '当前部署' : snapshot.scope || '当前部署';
  const observed = snapshot.observed_at && typeof formatDateTime === 'function' ? formatDateTime(snapshot.observed_at) : snapshot.observed_at || '—';
  set('[data-concurrency-scope]', `部署范围 ${scope} · 策略版本 ${snapshot.policy_revision ?? '—'} · 观察时间 ${observed}`);
  set('[data-concurrency-summary]', `当前占用 ${global.occupied ?? 0} / ${global.limit ?? '—'}${global.draining ? '，等待现有任务结束' : ''}；预约 ${global.reserved ?? 0} · 执行 ${global.executing ?? 0} · 清理 ${global.cleaning ?? 0} · 调试保留 ${global.debug_hold ?? 0}；排队 ${snapshot.queued ?? (snapshot.types || []).reduce((sum, item) => sum + Number(item.queued || 0), 0)} · 远端等待 ${snapshot.remote_waiting ?? '—'}`);
  root.querySelectorAll('[data-concurrency-type]').forEach(row => {
    const type = concurrencyTypeV2(row.dataset.concurrencyType);
    row.querySelector('[data-concurrency-count]').textContent = type ? `占用 ${type.occupied ?? 0} / ${type.limit ?? '—'} · 排队 ${type.queued ?? 0}${type.draining ? ' · 等待现有任务结束' : ''}` : '占用 — · 排队 —';
    const reasons = type?.blocked_by || [];
    const details = row.querySelector('[data-concurrency-reasons]');
    details.hidden = !reasons.length;
    row.querySelector('[data-concurrency-primary]').textContent = reasons.length ? concurrencyWaitTextV2(reasons[0]) : '暂无容量等待';
    row.querySelector('[data-concurrency-reason-list]').textContent = reasons.map(concurrencyWaitTextV2).join('；');
  });
  root.querySelectorAll('[data-concurrency-effective]').forEach(node => {
    const value = configFieldValueV2(node.dataset.concurrencyEffective);
    node.textContent = Number(value) > Number(global.limit) ? `当前实际最多受全局 ${global.limit} 限制；保存后的类型值 ${value} 仍会保留。` : '';
  });
  const detailParts = [];
  for (const [key, label] of [['providers', '平台'], ['batches', '批次'], ['remote_orders', '远端订单']]) {
    for (const item of snapshot[key] || []) detailParts.push(`${label} ${item.label || item.key || item.id || item.batch_id || '当前'}：${item.occupied ?? item.active ?? 0} / ${item.limit ?? '—'}`);
  }
  set('[data-concurrency-details-status]', detailParts.join('；') || '附加限制按需读取，任务仍需同时满足账号与邮箱资源约束。');
}

function scheduleConcurrencyStatusV2() {
  const state = CONFIG_CONCURRENCY_V2;
  if (state.timer !== null) clearTimeout(state.timer);
  state.timer = null;
  if (!state.visible || !concurrencyIsVisibleV2() || state.loading) return;
  state.timer = setTimeout(() => { state.timer = null; queryConcurrencyStatusV2(); }, 3000);
}

async function queryConcurrencyStatusV2({details = false} = {}) {
  const state = CONFIG_CONCURRENCY_V2;
  if (!state.visible || !concurrencyIsVisibleV2() || state.loading) return;
  const request = ++state.request;
  state.loading = true;
  state.error = '';
  if (state.timer !== null) clearTimeout(state.timer);
  state.timer = null;
  updateConcurrencyStatusV2();
  try {
    const calls = [api(`/api/operations/concurrency${details ? '?details=1' : ''}`)];
    if (!state.preview) calls.push(api('/api/config/concurrency-preview'));
    const results = await Promise.allSettled(calls);
    if (request !== state.request || !state.visible) return;
    const status = results[0];
    if (status.status === 'fulfilled' && status.value?.ok !== false) state.snapshot = status.value;
    else {
      const error = status.reason || status.value;
      state.error = `状态读取失败（${error?.error_code || error?.code || 'scheduler_store_unavailable'}），请重试；显示的数据为上次观察结果。`;
    }
    if (results[1]?.status === 'fulfilled') state.preview = results[1].value;
    else if (results[1]) state.error += ' 迁移预览暂不可用，请刷新重试。';
  } finally {
    if (request === state.request) {
      state.loading = false;
      updateConcurrencyStatusV2();
      scheduleConcurrencyStatusV2();
    }
  }
}

function syncConcurrencyStatusV2() {
  const state = CONFIG_CONCURRENCY_V2;
  const visible = concurrencyIsVisibleV2();
  const entered = visible && !state.visible;
  state.visible = visible;
  if (!visible) {
    if (state.timer !== null) clearTimeout(state.timer);
    state.timer = null;
    if (state.loading) { state.request += 1; state.loading = false; }
    return;
  }
  updateConcurrencyStatusV2();
  if (entered) queryConcurrencyStatusV2();
}

function bindConcurrencyStatusV2() {
  const state = CONFIG_CONCURRENCY_V2;
  const tab = document.getElementById('tab-config');
  if (tab && !state.observer) {
    state.observer = new MutationObserver(syncConcurrencyStatusV2);
    state.observer.observe(tab, {attributes: true, attributeFilter: ['class', 'hidden']});
    document.addEventListener('visibilitychange', syncConcurrencyStatusV2);
    tab.addEventListener('focusout', event => {
      const input = event.target.closest('[data-key]');
      if (!input || !concurrencyFieldV2(configSchemaField(input.dataset.key))) return;
      validateConcurrencyInputV2(input);
    });
  }
  syncConcurrencyStatusV2();
}

function validateConcurrencyInputV2(input) {
  const key = input.dataset.key;
  const reason = concurrencyFieldErrorV2(input.value);
  if (reason) CONFIG_FIELD_ERRORS_V2[key] = reason;
  else delete CONFIG_FIELD_ERRORS_V2[key];
  input.setAttribute('aria-invalid', String(!!reason));
  const error = document.getElementById(`concurrency-${key}-error`);
  if (error) { error.hidden = !reason; error.textContent = reason; }
  return reason;
}

function useConcurrencyPreviewV2() {
  const values = CONFIG_CONCURRENCY_V2.preview?.proposed_values;
  if (!values) return;
  for (const [key, value] of Object.entries(values)) {
    if (!Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key)) setPendingConfigValue(key, value, {force: true});
  }
  renderConfigLayoutV2();
  showToast('迁移建议已填入草稿；核对全局和各类型上限后点击保存。');
}

function locateConcurrencyTasksV2(configKey) {
  const type = concurrencyTypeV2(configKey);
  if (configKey.startsWith('REGISTRATION_')) {
    const register = document.getElementById('tab-register');
    if (register) register.dataset.moduleView = 'tasks';
    activateTab('register');
    document.getElementById('btnResetJobFiltersV2')?.click();
    document.getElementById('jobsPanelV2')?.scrollIntoView({block: 'start', behavior: 'auto'});
    showToast('已打开注册任务列表，可在注册协议列查看 Roxy 与 Proto2。');
    return;
  }
  activateTab('tasks');
  document.getElementById('btnResetAccountTaskFiltersV2')?.click();
  const filter = document.getElementById('accountTaskTypeFilterV2');
  if (filter && type) {
    const value = (type.task_types?.length ? [...new Set(type.task_types)] : [type.key]).join(',');
    if (!Array.from(filter.options || []).some(option => option.value === value)) filter.add(new Option(type.label || value, value));
    filter.value = value;
    filter.dispatchEvent(new Event('change', {bubbles: true}));
  }
}

function renderConfigSectionV2(name, fields) {
  const byDomain = configDomainGroupsV2(fields);
  const domains = configMenuDomainNamesV2(name, fields);
  let domain = CONFIG_ACTIVE_DOMAIN_V2[name];
  if (!domains.includes(domain)) domain = domains[0] || name;
  CONFIG_ACTIVE_DOMAIN_V2[name] = domain;
  return renderConfigDomainSectionV2(domain, byDomain[domain] || []);
}

function renderConfigDomainSectionV2(name, fields) {
  const slug = configGroupSlug(name);
  if (name === '提链') return renderExtractLinkSectionV2(fields);
  if (name === '注册与账号') return renderPlanBusinessSectionV2(fields);
  if (name === '注册主链路') return renderRegistrationMainSectionV2(fields);
  if (name === '账号补全') return renderAccountCompletionSectionV2(fields);
  if (Object.prototype.hasOwnProperty.call(CONFIG_ACCOUNT_ACTION_SECTIONS_V2, name)) return renderAccountActionSectionV2(name, fields);
  if (name === '注册调试') return renderRegistrationDebugSectionV2(fields);
  if (name === '定时任务') return renderScheduledConfigSectionV2(fields);
  if (name === '并发控制') return renderConcurrencyConfigSectionV2(fields);
  if (name === 'WebUI 授权') {
    return `
      <section class="config-section-v2" id="${esc(slug)}" data-config-section="${esc(name)}">
        ${renderConfigSectionHead(name, configSectionIntro(name))}
        <div class="config-section-v2-body">
          ${fields.map(renderConfigPlainFieldV2).join('')}
        </div>
        ${renderConfigSaveActions()}
      </section>
    `;
  }
  if (name === 'Codex') {
    return renderCodexSectionV2(fields);
  }
  if (name === '邮箱 / OTP') {
    return renderSectionedConfigSectionV2(
      name,
      fields,
      emailConfigSectionForKey,
      ['通用邮箱 / OTP', 'iCloud 隐藏邮箱', 'Email Butler', 'GPTMail', 'MailNest', 'Remail', '域名邮箱 MailCode', '西瓜邮箱', 'CloudMail', 'Outlook 邮箱池', 'Cloudflare 临时邮箱', 'Cloudflare 域名邮箱', '其他邮箱配置'],
      { get: () => CONFIG_EMAIL_ACTIVE_SECTION_V2, set: v => { CONFIG_EMAIL_ACTIVE_SECTION_V2 = v; } },
      'email-section-v2'
    );
  }
  if (name === '接码平台') {
    return renderSectionedConfigSectionV2(
      name,
      fields,
      smsConfigSectionForKey,
      ['通用接码', 'GrizzlySMS', 'H 接码', 'L 接码', '其他接码配置'],
      { get: () => CONFIG_SMS_ACTIVE_SECTION_V2, set: v => { CONFIG_SMS_ACTIVE_SECTION_V2 = v; } },
      'sms-section-v2'
    );
  }
  if (name === '代理与网络') {
    return renderSectionedConfigSectionV2(
      name,
      fields,
      proxyConfigSectionForKey,
      ['任务用池', '代理来源', '库存策略', '高级兼容'],
      { get: () => CONFIG_PROXY_ACTIVE_SECTION_V2, set: v => { CONFIG_PROXY_ACTIVE_SECTION_V2 = v; } },
      'proxy-section-v2'
    );
  }
  return renderMixedConfigSectionV2(name, fields, configSectionIntro(name),
    name === '通用配置' ? renderSentinelMaintenanceV2() : '');
}
function applyConfigNavFilter() {
  const query = CONFIG_NAV_QUERY_V2.trim().toLowerCase();
  const items = Array.from(document.querySelectorAll('#configNavV2 [data-config-nav]'));
  let shown = 0;
  items.forEach(btn => {
    const haystack = `${btn.dataset.configSearch || ''} ${btn.textContent || ''}`.toLowerCase();
    const matches = !query || haystack.includes(query);
    btn.hidden = !matches;
    if (matches) shown += 1;
  });
  document.querySelectorAll('#configNavV2 [data-config-nav-group]').forEach(group => {
    group.hidden = !group.querySelector('[data-config-nav]:not([hidden])');
  });
  const count = document.getElementById('configNavCountV2');
  if (count) {
    count.textContent = query ? `${shown}/${items.length}` : String(items.length);
    count.title = query ? `共 ${items.length} 个分组，当前显示 ${shown} 个` : `共 ${items.length} 个配置分组`;
  }
  const empty = document.getElementById('configNavEmptyV2');
  if (empty) empty.hidden = shown > 0 || items.length === 0;
}
function renderConfigLayoutV2() {
  const nav = document.getElementById('configNavV2');
  const sections = document.getElementById('configSectionsV2');
  if (!nav || !sections) return;
  const groups = configGroups();
  const preferredNames = Object.keys(CONFIG_MENU_DOMAINS_V2);
  const names = preferredNames.filter(name => groups[name])
    .concat(Object.keys(groups).filter(name => !preferredNames.includes(name)));
  if (!names.length) {
    nav.innerHTML = '<div class="muted" style="padding:8px 12px;font-size:13px;">暂无分组</div>';
    sections.innerHTML = '';
    syncSentinelMaintenanceV2();
    syncConcurrencyStatusV2();
    const count = document.getElementById('configNavCountV2');
    if (count) count.textContent = '0';
    updateConfigSaveUi();
    return;
  }
  const savedGroup = localStorage.getItem('gpt_console_config_group');
  if (CONFIG_ACTIVE_GROUP_V2) setConfigDestinationV2(CONFIG_ACTIVE_GROUP_V2);
  if (!CONFIG_ACTIVE_GROUP_V2 && savedGroup) setConfigDestinationV2(savedGroup);
  if (!CONFIG_ACTIVE_GROUP_V2 || !names.includes(CONFIG_ACTIVE_GROUP_V2)) CONFIG_ACTIVE_GROUP_V2 = names[0];
  nav.innerHTML = renderConfigNavV2(names, groups);
  applyConfigNavFilter();
  sections.innerHTML = renderConfigSectionV2(CONFIG_ACTIVE_GROUP_V2, groups[CONFIG_ACTIVE_GROUP_V2] || []);
  renderRegistrationDriverCard();
  renderConfigOverviewCards();
  bindRoxyWorkspaceToolsV2();
  bindEmailButlerToolsV2();
  bindProxyProviderToolsV2();
  bindConfigCountryPickersV2();
  bindConfigMultiSelectsV2();
  updateConfigSaveUi();
  syncSentinelMaintenanceV2();
  syncConcurrencyStatusV2();
}

function resetPendingConfigUpdates() {
  const keys = Object.keys(CONFIG_PENDING_UPDATES);
  if (!keys.length) return;
  if (!window.confirm(`撤销 ${keys.length} 项未保存更改？`)) return;
  keys.forEach(resetHuanguangQuotaForKeyV2);
  keys.forEach(key => delete CONFIG_PENDING_UPDATES[key]);
  Object.keys(CONFIG_COMPOSITE_MODES_V2).forEach(key => delete CONFIG_COMPOSITE_MODES_V2[key]);
  Object.keys(CONFIG_FIELD_ERRORS_V2).forEach(key => delete CONFIG_FIELD_ERRORS_V2[key]);
  renderConfigLayoutV2();
  updateConfigSaveUi();
  showToast('已撤销未保存更改');
}
function clearConfigFieldErrorsV2() {
  Object.keys(CONFIG_FIELD_ERRORS_V2).forEach(key => delete CONFIG_FIELD_ERRORS_V2[key]);
  document.querySelectorAll('#tab-config .config-field-error-v2').forEach(error => error.remove());
}
function scrollToConfigSection(slug) {
  const el = document.getElementById(slug);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function resetConfigViewportV2() {
  window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
}
function setActiveConfigNav(slug) {
  document.querySelectorAll('#configNavV2 .config-nav-v2-item').forEach(btn => {
    const active = btn.dataset.configTarget === slug;
    btn.classList.toggle('is-active', active);
    btn.setAttribute('aria-current', active ? 'page' : 'false');
  });
}
function openConfigGroup(name) {
  setConfigDestinationV2(String(name || ''));
  CONFIG_NAV_QUERY_V2 = '';
  const search = document.getElementById('configNavSearchV2');
  if (search) search.value = '';
  rememberConfigDestinationV2();
  activateTab('config');
  if (CONFIG.length) renderConfigLayoutV2();
  resetConfigViewportV2();
}
function bindConfigLayoutV2() {
  bindSentinelMaintenanceV2();
  bindConcurrencyStatusV2();
  const nav = document.getElementById('configNavV2');
  const search = document.getElementById('configNavSearchV2');
  if (search && !search.dataset.bound) {
    search.dataset.bound = '1';
    search.value = CONFIG_NAV_QUERY_V2;
    search.addEventListener('input', () => {
      CONFIG_NAV_QUERY_V2 = search.value;
      selectConfigSearchDestinationV2();
      renderConfigLayoutV2();
    });
  }
  if (!nav || nav.dataset.bound) return;
  nav.dataset.bound = '1';
  nav.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-config-nav]');
    if (!btn) return;
    setConfigDestinationV2(btn.dataset.configNav);
    selectConfigSearchDestinationV2(CONFIG_ACTIVE_GROUP_V2);
    rememberConfigDestinationV2();
    renderConfigLayoutV2();
    resetConfigViewportV2();
  });
  const layout = document.getElementById('configLayoutV2');
  if (layout && !layout.dataset.epBound) {
    layout.dataset.epBound = '1';
    layout.addEventListener('click', (e) => {
      const extractLinkTab = e.target.closest('[data-extract-link-tab]');
      if (extractLinkTab) {
        e.preventDefault();
        CONFIG_EXTRACT_LINK_ACTIVE_SECTION_V2 = extractLinkTab.dataset.extractLinkTab;
        renderConfigLayoutV2();
        return;
      }
      const domainTab = e.target.closest('[data-config-domain-v2]');
      if (domainTab) {
        e.preventDefault();
        const domain = domainTab.dataset.configDomainV2;
        const menu = configMenuGroupV2(domain);
        setConfigDestinationV2(menu);
        CONFIG_ACTIVE_DOMAIN_V2[menu] = domain;
        rememberConfigDestinationV2();
        renderConfigLayoutV2();
        return;
      }
      const codexTab = e.target.closest('[data-codex-section-v2]');
      if (codexTab) {
        e.preventDefault();
        CONFIG_CODEX_ACTIVE_SECTION_V2 = codexTab.dataset.codexSectionV2;
        renderConfigLayoutV2();
        return;
      }
      const emailTab = e.target.closest('[data-email-section-v2]');
      if (emailTab) {
        e.preventDefault();
        CONFIG_EMAIL_ACTIVE_SECTION_V2 = emailTab.dataset.emailSectionV2;
        renderConfigLayoutV2();
        return;
      }
      const smsTab = e.target.closest('[data-sms-section-v2]');
      if (smsTab) {
        e.preventDefault();
        CONFIG_SMS_ACTIVE_SECTION_V2 = smsTab.dataset.smsSectionV2;
        renderConfigLayoutV2();
        return;
      }
      const proxyTab = e.target.closest('[data-proxy-section-v2]');
      if (proxyTab) {
        e.preventDefault();
        CONFIG_PROXY_ACTIVE_SECTION_V2 = proxyTab.dataset.proxySectionV2;
        renderConfigLayoutV2();
        return;
      }
    });
  }
  if (!document.documentElement.dataset.configEpCloseBound) {
    document.documentElement.dataset.configEpCloseBound = '1';
    document.addEventListener('click', event => {
      document.querySelectorAll('#tab-config [data-multi-picker]').forEach(picker => {
        if (!picker.contains(event.target)) toggleConfigMultiSelectV2(picker, false);
      });
    });
  }
  const sectionRoot = document.getElementById('configSectionsV2');
  if (sectionRoot && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      const visible = entries
        .filter(x => x.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible || !visible.target.id) return;
      setActiveConfigNav(visible.target.id);
    }, { rootMargin: '-20% 0px -60% 0px', threshold: [0.15, 0.35, 0.6] });
    const watch = () => {
      sectionRoot.querySelectorAll('.config-section-v2').forEach(sec => io.observe(sec));
    };
    watch();
    const mo = new MutationObserver(watch);
    mo.observe(sectionRoot, { childList: true });
  }
}

async function loadConfig() {
  try {
    CONFIG = await apiCached('/api/config', {}, 30000);
    resetXxsyunPaymentBalanceV2();
    resetHuanguangXxsyunQuotaV2();
    resetHuanguangQuotaForKeyV2('EXTRACT_LINK_HUANGUANG_API_BASE');
    renderConfigLayoutV2();
    bindConfigLayoutV2();
    loadExtractLinkTypesV2();
    markViewReady('config');
  } catch(e) {
    showToast('加载配置失败: ' + e.message);
  }
}

async function loadRoxyWorkspaces() {
  const status = $('#roxyWorkspaceStatusV2');
  const sel = $('#roxyWorkspaceSelectV2');
  const saveBtn = $('#btnSaveRoxyWorkspaceV2');
  const loadBtn = $('#btnLoadRoxyWorkspacesV2');
  if (!status || !sel) return;
  if (loadBtn) loadBtn.disabled = true;
  if (saveBtn) saveBtn.disabled = true;
  status.textContent = '正在调用 Roxy API 获取团队/工作区...';
  try {
    const r = await api('/api/roxy/workspaces');
    const items = r.items || [];
    if (!items.length) {
      const errs = (r.errors || []).slice(0, 5).map(x => `${x.method || ''} ${x.path || ''}: ${x.error || ''}`).join('；');
      throw new Error(errs ? `未返回团队/工作区列表。探测结果：${errs}` : '未返回团队/工作区列表');
    }
    const current = (CONFIG.find(f => f.key === 'ROXY_WORKSPACE_ID') || {}).value || '';
    const currentProject = (CONFIG.find(f => f.key === 'ROXY_PROJECT_ID') || {}).value || '';
    sel.innerHTML = `<option value="">请选择团队/项目（当前团队：${esc(current || '未设置')}）</option>` +
      items.map(x => {
        const value = `${x.id}::${x.projectId || ''}`;
        const selected = String(x.id)===String(current) && String(x.projectId || '')===String(currentProject);
        return `<option value="${esc(value)}" data-workspace-id="${esc(x.id)}" data-project-id="${esc(x.projectId || '')}"${selected?' selected':''}>${esc(x.label || (x.name + ' (' + x.id + ')'))}</option>`;
      }).join('');
    if (saveBtn) saveBtn.disabled = !sel.value;
    status.innerHTML = `已获取 ${items.length} 个团队/项目，接口：<span class="mono">${esc(r.method || '')} ${esc(r.path || '')}</span>`;
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">获取失败：${esc(e.message)}</span>`;
  } finally {
    if (loadBtn) loadBtn.disabled = false;
  }
}

async function saveRoxyWorkspaceSelection() {
  const sel = $('#roxyWorkspaceSelectV2');
  const status = $('#roxyWorkspaceStatusV2');
  const opt = sel ? sel.selectedOptions[0] : null;
  const workspaceId = opt ? (opt.dataset.workspaceId || '') : '';
  const projectId = opt ? (opt.dataset.projectId || '') : '';
  if (!workspaceId) return;
  try {
    const r = await api('/api/config', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({updates: {ROXY_WORKSPACE_ID: workspaceId, ROXY_PROJECT_ID: projectId}}),
    });
    invalidateApiCache('/api/config');
    const fw = CONFIG.find(x => x.key === 'ROXY_WORKSPACE_ID');
    const fp = CONFIG.find(x => x.key === 'ROXY_PROJECT_ID');
    if (fw) fw.value = workspaceId;
    if (fp) fp.value = projectId;
    if (status) status.innerHTML = `✅ 已保存团队 ID：<span class="mono">${esc(workspaceId)}</span>，项目 ID：<span class="mono">${esc(projectId || '未设置')}</span>`;
    showToast(r.reloaded ? 'Roxy 团队/项目已保存并生效' : 'Roxy 团队/项目已保存');
    renderConfigLayoutV2();
  } catch(e) {
    if (status) status.innerHTML = `<span style="color:var(--red);">保存失败：${esc(e.message)}</span>`;
  }
}


function readConfigElementValue(el, f) {
  if (!f) return undefined;
  if (f.group === '并发控制' && f.type === 'int') return String(el.value ?? '').trim();
  if (f.key === 'PROXY_POOL_WAIT_TIMEOUT' || f.key === 'SMS_MAX_PRICE') {
    const root = el.closest?.('[data-config-composite-key]');
    const mode = root?.querySelector('[data-composite-mode]')?.value || 'continuous';
    const raw = String(root?.querySelector('[data-composite-seconds], [data-composite-value]')?.value || '').trim();
    if (f.key === 'PROXY_POOL_WAIT_TIMEOUT') return mode === 'timed' ? (raw ? Number(raw) : null) : 0;
    return mode === 'limited' ? raw : '';
  }
  if (el.dataset.toggleOnValue) return el.checked ? el.dataset.toggleOnValue : el.dataset.toggleOffValue;
  if (el.multiple) return Array.from(el.selectedOptions || []).map(option => option.value).join(',');
  if (el.closest?.('[data-multi-picker]')) {
    const raw = String(el.value ?? '');
    return ['EMAIL_SOURCE', 'ROXY_RANDOM_OS_CHOICES'].includes(f.key)
      ? configListValuesV2(raw, f).join(',')
      : configListValuesV2(raw, f);
  }
  if (f.type === 'list_str_multiline') {
    if (['PROXY_POOL_COUNTRIES', 'PLAN_CHECK_COUNTRIES'].includes(f.key)) return configCountryCodesV2(el.value);
    return el.value.split(/\n/).map(s=>s.trim()).filter(Boolean);
  }
  if (f.type === 'bool') {
    if (el.type === 'checkbox') return !!el.checked;
    return el.value === 'true';
  }
  if (f.type === 'int') return parseInt(el.value || '0', 10);
  if (f.type === 'float') return parseFloat(el.value || '0');
  const value = el.value.trim();
  const option = configSchemaOptions(f).find(item => item.value.toLowerCase() === value.toLowerCase());
  if (['PROXY_POOL_DEFAULT_COUNTRY', 'REGISTRATION_COUNTRY', 'ACCOUNT_AT_REFRESH_COUNTRY'].includes(f.key)) return option ? option.value : value;
  return option ? option.value : (isPlaceholderEmpty(value) ? '' : value);
}

function trackConfigFieldChange(e) {
  const el = e.target.closest('[data-key], [data-wait-seconds-key], [data-price-key]');
  if (!el || !el.closest('#tab-config')) return;
  const key = el.dataset.key || el.dataset.waitSecondsKey || el.dataset.priceKey;
  if (el.dataset.extractProviderSelection === 'true') {
    applyExtractLinkProviderSelectionV2(el.value);
    return;
  }
  const f = CONFIG.find(x => x.key === key);
  if (!f) return;
  if (!concurrencyFieldV2(f)) clearConfigFieldErrorsV2();
  el.closest('.config-setting-row-v2')?.querySelector('.config-field-error-v2')?.remove();
  const composite = el.closest('[data-config-composite-key]');
  if (composite) {
    if (el.hasAttribute('data-composite-mode')) CONFIG_COMPOSITE_MODES_V2[f.key] = el.value;
    const number = composite.querySelector('[data-composite-seconds], [data-composite-value]');
    const mode = composite.querySelector('[data-composite-mode]')?.value || CONFIG_COMPOSITE_MODES_V2[f.key];
    if (!CONFIG_COMPOSITE_MODES_V2[f.key] && mode) CONFIG_COMPOSITE_MODES_V2[f.key] = mode;
    const enabled = ['timed', 'limited'].includes(mode);
    number.hidden = !enabled;
    if (enabled && !number.value && el.hasAttribute('data-composite-mode')) number.value = f.key === 'PROXY_POOL_WAIT_TIMEOUT' ? '60' : '0.1';
  }
  // 密钥输入框留空表示“保留已有值”；只有点击明确的“清除”操作后才
  // 向后端提交空字符串，避免重绘或误删导致凭据丢失。
  if (f.secret && el.dataset.secretClear !== 'true' && String(el.value || '').trim() === '') {
    resetHuanguangQuotaForKeyV2(f.key);
    delete CONFIG_PENDING_UPDATES[f.key];
    updateConfigSaveUi();
    return;
  }
  const value = readConfigElementValue(el, f);
  const explicitSecretClear = f.secret && el.dataset.secretClear === 'true' && String(el.value || '').trim() === '';
  const syncKeys = String(el.dataset.syncKeys || '').split(',').map(key => key.trim()).filter(Boolean);
  [f.key, ...syncKeys].filter((key, index, all) => all.indexOf(key) === index).forEach(key => {
    const migrationDraft = concurrencyFieldV2(f) && CONFIG_CONCURRENCY_V2.preview?.migration_required
      && Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, 'CONCURRENCY_POLICY_REVISION');
    if (CONFIG.some(item => item.key === key)) setPendingConfigValue(key, value, {force: (explicitSecretClear && key === f.key) || migrationDraft});
  });
  const status = el.closest('.config-field-v2, .config-setting-row-v2')?.querySelector('.config-field-status-v2');
  if (status) status.outerHTML = renderConfigFieldStatusV2(f);
  renderConfigOverviewCards();
  if (concurrencyFieldV2(f)) {
    if (CONFIG_FIELD_ERRORS_V2[f.key]) validateConcurrencyInputV2(el);
    updateConcurrencyStatusV2();
  }
  if (f.key === 'REGISTRATION_AUTH_MODE' || f.key === 'ACCOUNT_LIVE_CHECK_BROWSER_ENABLED'
    || f.key === 'EMAIL_SOURCE' || f.key === 'ICLOUD_HME_INBOX_MODE'
    || f.key === 'ICLOUD_HME_BUTLER_BRIDGE_ENABLED'
    || f.key === 'PROXY_POOL_SOURCE' || f.key === 'PROXY_POOL_DEFAULT_COUNTRY') renderConfigLayoutV2();
  updateConfigSaveUi();
}
$('#tab-config').addEventListener('input', trackConfigFieldChange);
$('#tab-config').addEventListener('change', trackConfigFieldChange);

async function saveConfigUpdates(triggerBtn) {
  const updates = {...CONFIG_PENDING_UPDATES};
  if (!Object.keys(updates).length) {
    updateConfigSaveUi();
    return;
  }
  updateConfigSaveUi('saving');
  try {
    const concurrencyErrors = {};
    for (const [key, value] of Object.entries(updates)) {
      if (!concurrencyFieldV2(configSchemaField(key))) continue;
      const reason = concurrencyFieldErrorV2(value);
      if (reason) concurrencyErrors[key] = reason;
    }
    if (Object.keys(concurrencyErrors).length) {
      const error = new Error('请检查并发设置');
      error.fields = concurrencyErrors;
      throw error;
    }
    for (const [key, mode] of Object.entries(CONFIG_COMPOSITE_MODES_V2)) {
      if (!Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key)) continue;
      const value = CONFIG_PENDING_UPDATES[key];
      const invalid = key === 'PROXY_POOL_WAIT_TIMEOUT'
        ? mode === 'timed' && (value === null || !Number.isFinite(Number(value)) || Number(value) <= 0)
        : mode === 'limited' && String(value ?? '').trim() === '';
      if (invalid) {
        const error = new Error('请填写有效数值');
        error.fields = {[key]: key === 'PROXY_POOL_WAIT_TIMEOUT'
          ? '请填写限时等待秒数，或切换为持续等待'
          : '请填写短信价格上限，或切换为不设上限'};
        throw error;
      }
    }
    // 复合模式的空数值不能被保存成持续等待或无限价格。
    document.querySelectorAll('#tab-config [data-config-composite-key]').forEach(root => {
      const mode = root.querySelector('[data-composite-mode]');
      const number = root.querySelector('[data-composite-seconds], [data-composite-value]');
      if (['timed', 'limited'].includes(mode.value) && (!number.value || !number.checkValidity())) {
        const key = root.dataset.configCompositeKey;
        const error = new Error('请填写有效数值');
        error.fields = {[key]: key === 'PROXY_POOL_WAIT_TIMEOUT'
          ? '请填写限时等待秒数，或切换为持续等待'
          : '请填写短信价格上限，或切换为不设上限'};
        throw error;
      }
    });
    const r = await api('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({updates}) });
    if (Object.keys(updates).some(key => concurrencyFieldV2(configSchemaField(key)))) {
      CONFIG_CONCURRENCY_V2.preview = null;
      CONFIG_CONCURRENCY_V2.visible = false;
    }
    Object.keys(updates).forEach(resetHuanguangQuotaForKeyV2);
    Object.keys(CONFIG_FIELD_ERRORS_V2).forEach(key => delete CONFIG_FIELD_ERRORS_V2[key]);
    Object.keys(CONFIG_COMPOSITE_MODES_V2).forEach(key => delete CONFIG_COMPOSITE_MODES_V2[key]);
    invalidateApiCache('/api/config');
    invalidateApiCache('/api/ui-settings');
    for (const k of Object.keys(updates)) delete CONFIG_PENDING_UPDATES[k];
    await loadConfig();
    await loadCapabilities();
    await loadRegistrationEmailSources();
    const restartRequired = Array.isArray(r.restart_required) ? r.restart_required : [];
    showToast(!r.reloaded
      ? '配置已保存（热加载失败，需重启）'
      : restartRequired.length
        ? `配置已热加载；${restartRequired.join('、')}需重启后完整生效`
        : '配置已生效');
  } catch(e) {
    const errors = Object.entries(e.fields || {});
    if (errors.length) {
      Object.assign(CONFIG_FIELD_ERRORS_V2, e.fields);
      const field = CONFIG.find(item => item.key === errors[0][0]);
      if (field) {
        const concurrency = concurrencyFieldV2(field);
        CONFIG_NAV_QUERY_V2 = concurrency ? '' : field.key;
        const search = document.getElementById('configNavSearchV2');
        if (search) search.value = CONFIG_NAV_QUERY_V2;
        if (concurrency) setConfigDestinationV2('并发控制');
        else selectConfigSearchDestinationV2(configFieldMenuV2(field));
        renderConfigLayoutV2();
        if (concurrency) document.getElementById('configConcurrencyErrorsV2')?.focus();
        else document.querySelector(`#tab-config [data-key="${field.key}"]`)?.focus();
      }
    }
    updateConfigSaveUi(errors.length ? 'validation_error' : 'error');
    showToast('保存失败: ' + (errors.length ? errors.map(([key, reason]) => `${CONFIG.find(item => item.key === key)?.label || key}：${reason}`).join('；') : e.message));
  }
}
$('#tab-config').addEventListener('click', (e) => {
  const concurrencyButton = e.target.closest('[data-concurrency-refresh], [data-concurrency-load-details], [data-concurrency-use-preview], [data-concurrency-error-key], [data-concurrency-tasks]');
  if (concurrencyButton) {
    e.preventDefault();
    if (concurrencyButton.hasAttribute('data-concurrency-use-preview')) return useConcurrencyPreviewV2();
    if (concurrencyButton.dataset.concurrencyErrorKey) {
      const input = document.getElementById(`concurrency-${concurrencyButton.dataset.concurrencyErrorKey}`);
      input?.focus();
      input?.scrollIntoView({block: 'center', behavior: 'auto'});
      return;
    }
    if (concurrencyButton.dataset.concurrencyTasks) return locateConcurrencyTasksV2(concurrencyButton.dataset.concurrencyTasks);
    if (concurrencyButton.hasAttribute('data-concurrency-refresh')) CONFIG_CONCURRENCY_V2.preview = null;
    return queryConcurrencyStatusV2({details: concurrencyButton.hasAttribute('data-concurrency-load-details')});
  }
  const sentinelButton = e.target.closest('[data-sentinel-maintenance-action]');
  if (sentinelButton) {
    e.preventDefault();
    return querySentinelMaintenanceV2(sentinelButton.dataset.sentinelMaintenanceAction === 'retry'
      ? CONFIG_SENTINEL_MAINTENANCE_V2.retryAction : 'check');
  }
  const sub2apiButton = e.target.closest('[data-sub2api-automation]');
  if (sub2apiButton) {
    e.preventDefault();
    return querySub2ApiAutomationV2(sub2apiButton);
  }
  const balanceButton = e.target.closest('[data-query-xxsyun-payment-balance]');
  if (balanceButton) {
    e.preventDefault();
    return queryXxsyunPaymentBalanceV2(balanceButton);
  }
  const cdkQuotaButton = e.target.closest('[data-query-huanguang-cdk-quota]');
  if (cdkQuotaButton) {
    e.preventDefault();
    return queryHuanguangCdkQuotaV2(cdkQuotaButton);
  }
  const quotaButton = e.target.closest('[data-query-huanguang-xxsyun-quota]');
  if (quotaButton) {
    e.preventDefault();
    return queryHuanguangXxsyunQuotaV2(quotaButton);
  }
  const clearSecret = e.target.closest('[data-clear-secret]');
  if (clearSecret) {
    e.preventDefault();
    const input = clearSecret.closest('.config-secret-control-v2')?.querySelector('[data-secret-input]');
    if (input) {
      input.value = '';
      input.dataset.secretClear = 'true';
      input.dispatchEvent(new Event('input', {bubbles: true}));
    }
    return;
  }
  const resetBtn = e.target.closest('[data-reset-config-v2]');
  if (resetBtn) {
    e.preventDefault();
    resetPendingConfigUpdates();
    return;
  }
  const btn = e.target.closest('[data-save-config-v2]');
  if (!btn) return;
  saveConfigUpdates(btn);
});

window.addEventListener('beforeunload', (e) => {
  if (!configPendingCount()) return;
  e.preventDefault();
  e.returnValue = '';
});
