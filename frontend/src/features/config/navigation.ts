import type {ConfigField, ConfigOption, ConfigDraftOwner} from './contracts';

// Existing navigation contract, transcribed from the legacy page; schema remains authoritative.
export const menus: Record<string,string[]> = {
  "注册与账号": [
    "注册主链路",
    "账号补全",
    "注册与账号",
    "查活",
    "刷新 AT",
    "补密码",
    "补 2FA",
    "邮箱换绑"
  ],
  "代理与网络": [
    "代理与网络"
  ],
  "邮箱与验证码": [
    "邮箱 / OTP",
    "接码平台"
  ],
  "浏览器": [
    "RoxyBrowser",
    "浏览器画像",
    "人工节奏"
  ],
  "服务集成": [
    "Codex",
    "C2A"
  ],
  "提链": [
    "提链"
  ],
  "系统与维护": [
    "并发控制",
    "通用配置",
    "WebUI 授权",
    "定时任务",
    "任务中心",
    "注册调试"
  ]
};
export const aliases: Record<string,string> = {
  "注册设置": "注册主链路",
  "账号设置": "账号补全",
  "注册与账号": "注册主链路",
  "执行方式": "注册主链路",
  "邮箱 / OTP": "邮箱 / OTP",
  "接码平台": "接码平台",
  "邮箱": "邮箱 / OTP",
  "浏览器设置": "RoxyBrowser",
  "Codex": "Codex",
  "提链": "提链",
  "系统设置": "通用配置",
  "网站配置": "WebUI 授权"
};
export const plans: string[] = [
  "ACCOUNT_PLAN_CHECK_DRIVER",
  "PLAN_CHECK_AUTO_REFRESH_AT_ENABLED",
  "PLAN_CHECK_PAYMENT_METHODS_ENABLED",
  "PLAN_CHECK_COUNTRIES",
  "PLAN_CHECK_COUNTRY_WAIT_TIMEOUT",
  "PLAN_CHECK_TIMEOUT",
  "PLAN_CHECK_MAX_ATTEMPTS",
  "PLAN_CHECK_RETRY_DELAY",
  "PLAN_CHECK_REGISTRATION_RECHECK_DELAY",
  "PLAN_CHECK_MIN_INTERVAL",
  "PLAN_CHECK_JITTER"
];
export const actions: Record<string,[string,string[]][]> = {
  "查活": [
    [
      "查活策略",
      [
        "ACCOUNT_LIVE_CHECK_DRIVER",
        "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED"
      ]
    ]
  ],
  "刷新 AT": [
    [
      "刷新 AT 策略",
      [
        "ACCOUNT_AT_REFRESH_DRIVER",
        "ACCOUNT_AT_REFRESH_COUNTRY",
        "OPENAI_PROTOCOL_VERSION",
        "ACCOUNT_AT_REFRESH_NETWORK_RETRIES",
        "ACCOUNT_AT_REFRESH_NETWORK_TIMEOUT_SECONDS",
        "LIVE_CHECK_ROXY_FALLBACK_ENABLED",
        "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED"
      ]
    ],
    [
      "协议认证策略",
      [
        "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK",
        "ACCOUNT_AUTH_PROFILE_MODE"
      ]
    ],
    [
      "自动刷新",
      [
        "AT_AUTO_REFRESH_ENABLED",
        "AT_REFRESH_SCAN_INTERVAL_SECONDS",
        "AT_REFRESH_BEFORE_HOURS",
        "AT_REFRESH_INITIAL_DELAY_SECONDS",
        "AT_REFRESH_MAX_PER_CYCLE"
      ]
    ]
  ],
  "补密码": [
    [
      "密码补全策略",
      [
        "ACCOUNT_PASSWORD_DRIVER",
        "ACCOUNT_PASSWORD_RESET_ENABLED"
      ]
    ]
  ],
  "补 2FA": [
    [
      "2FA 补全策略",
      [
        "ACCOUNT_2FA_DRIVER",
        "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED",
        "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED"
      ]
    ],
    [
      "2FA 重认证参数",
      [
        "TWOFA_REAUTH_MAX_ATTEMPTS",
        "TWOFA_REAUTH_RETRY_DELAY"
      ]
    ]
  ],
  "邮箱换绑": [
    [
      "邮箱换绑策略",
      [
        "ACCOUNT_EMAIL_CHANGE_ENABLED",
        "ACCOUNT_EMAIL_CHANGE_MIN_ACCOUNT_AGE_HOURS"
      ]
    ]
  ]
};
export const overrides: [string,string][] = [
  [
    "REGISTRATION_PROXY_RETRIES",
    "注册主链路"
  ],
  [
    "REGISTRATION_PROXY_RETRY_DELAY",
    "注册主链路"
  ],
  [
    "ACCOUNT_ACTION_PROXY_RETRIES",
    "账号补全"
  ],
  [
    "ACCOUNT_ACTION_PROXY_RETRY_DELAY",
    "账号补全"
  ],
  [
    "ACCOUNT_LIVE_CHECK_DRIVER",
    "查活"
  ],
  [
    "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED",
    "查活"
  ],
  [
    "ACCOUNT_AT_REFRESH_DRIVER",
    "刷新 AT"
  ],
  [
    "ACCOUNT_AT_REFRESH_COUNTRY",
    "刷新 AT"
  ],
  [
    "OPENAI_PROTOCOL_VERSION",
    "刷新 AT"
  ],
  [
    "ACCOUNT_AT_REFRESH_NETWORK_RETRIES",
    "刷新 AT"
  ],
  [
    "ACCOUNT_AT_REFRESH_NETWORK_TIMEOUT_SECONDS",
    "刷新 AT"
  ],
  [
    "LIVE_CHECK_ROXY_FALLBACK_ENABLED",
    "刷新 AT"
  ],
  [
    "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED",
    "刷新 AT"
  ],
  [
    "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK",
    "刷新 AT"
  ],
  [
    "ACCOUNT_AUTH_PROFILE_MODE",
    "刷新 AT"
  ],
  [
    "AT_AUTO_REFRESH_ENABLED",
    "刷新 AT"
  ],
  [
    "AT_REFRESH_SCAN_INTERVAL_SECONDS",
    "刷新 AT"
  ],
  [
    "AT_REFRESH_BEFORE_HOURS",
    "刷新 AT"
  ],
  [
    "AT_REFRESH_INITIAL_DELAY_SECONDS",
    "刷新 AT"
  ],
  [
    "AT_REFRESH_MAX_PER_CYCLE",
    "刷新 AT"
  ],
  [
    "ACCOUNT_PASSWORD_DRIVER",
    "补密码"
  ],
  [
    "ACCOUNT_PASSWORD_RESET_ENABLED",
    "补密码"
  ],
  [
    "ACCOUNT_2FA_DRIVER",
    "补 2FA"
  ],
  [
    "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED",
    "补 2FA"
  ],
  [
    "ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED",
    "补 2FA"
  ],
  [
    "TWOFA_REAUTH_MAX_ATTEMPTS",
    "补 2FA"
  ],
  [
    "TWOFA_REAUTH_RETRY_DELAY",
    "补 2FA"
  ],
  [
    "ACCOUNT_EMAIL_CHANGE_ENABLED",
    "邮箱换绑"
  ],
  [
    "ACCOUNT_EMAIL_CHANGE_MIN_ACCOUNT_AGE_HOURS",
    "邮箱换绑"
  ]
];
const PROXY_PROVIDER_CONFIG_V2 = {'1024proxy':{prefix:'PROXY_1024_'},'711proxy':{prefix:'PROXY_711_'}};
export function emailConfigSectionForKey(key: string): string[] {
  if (['USE_EMAIL_SERVICE','REGISTER_EMAIL','OTP_MAX_WAIT','OTP_POLL_INTERVAL','EMAIL_SOURCE'].includes(key)) {
    return ['通用邮箱 / OTP', '邮箱来源选择、OTP 等待参数、手动邮箱等通用设置'];
  }
  if (key.startsWith('EMAIL_BUTLER_')) return ['Email Butler', '已导入邮箱的租约连接与取码权限'];
  if (key.startsWith('REMAIL_')) return ['Remail', '历史 Remail 原订单收码连接；新邮箱请在邮箱服务中准备后导入'];
  if (key.startsWith('ICLOUD_HME_')) return ['iCloud 隐藏邮箱', '已导入与历史隐藏邮箱的固定收件连接；邮箱管理在邮箱服务完成'];
  return ['其他邮箱配置', ''];
}

export function proxyConfigSectionForKey(key: string): string[] {
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

export function smsConfigSectionForKey(key: string): string[] {
  if (['CODEX_PHONE_ENABLED','SMS_PROVIDER','SMS_COUNTRY','SMS_SERVICE','SMS_MAX_PRICE','SMS_AUTO_SELECT_COUNTRY','SMS_AUTO_COUNTRY_MIN_RATIO','SMS_MAX_RETRIES','SMS_CODE_WAIT','CODEX_PHONE_TOTAL_TIMEOUT'].includes(key)) {
    return ['通用接码', '手机接码关闭时，Codex OAuth 遇到手机验证会报错退出；接码配置只在开启且实际需要时检查。H 通道可复用 SMS_SERVICE/SMS_COUNTRY 作为 projectId/country'];
  }
  if (key === 'SMS_API_KEY') return ['GrizzlySMS', 'GrizzlySMS 平台 API Key 配置'];
  if (key.startsWith('H_')) return ['H 接码', 'H_API.md 本地 H 取号服务配置；项目ID/国家留空时复用通用字段'];
  if (key.startsWith('L_')) return ['L 接码', '本地 L 取号服务配置，接口约定见 README'];
  return ['其他接码配置', ''];
}

export function codexConfigSectionForKey(key: string): string[] {
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


const overridesMap = new Map(overrides);
const planKeys = new Set(plans);
export const menuStorageKey = 'gpt_console_config_group';
export const providerLabels: Record<string,string> = {legacy:'虾扯蛋链',lumen_flow:'流光',huanguang:'幻光',anguang:'暗光（XXSYUN 一条龙）'};
const legacyExtract = new Set(['EXTRACT_LINK_API_BASE','EXTRACT_LINK_CDK','EXTRACT_LINK_TYPE','EXTRACT_LINK_REQUEST_TIMEOUT','EXTRACT_LINK_EVENT_TIMEOUT']);
export const proxyPrefixes: Record<string,string> = {'1024proxy':'PROXY_1024_','711proxy':'PROXY_711_'};
export function fieldDomain(field: ConfigField): string {return planKeys.has(field.key) ? '注册与账号' : overridesMap.get(field.key) || field.group || '其他';}
export function menuFor(name: string): string {
  if (menus[name]) return name;
  const domain = aliases[name] || name || '其他';
  return Object.keys(menus).find(menu => menus[menu]!.includes(domain)) || domain;
}
export function projectedFields(fields: readonly ConfigField[]): ConfigField[] {
  const seen = new Set<string>();
  return fields.filter(field => !field.hidden && !seen.has(field.key) && !!seen.add(field.key))
    .map(field => ({...field, group: fieldDomain(field)}));
}
export function orderedMenus(fields: readonly ConfigField[]): string[] {
  const available = [...new Set(projectedFields(fields).map(field => menuFor(field.group)))];
  return [...Object.keys(menus).filter(menu => available.includes(menu)), ...available.filter(menu => !menus[menu])];
}
export function domainsFor(menu: string, fields: readonly ConfigField[]): string[] {
  const available = [...new Set(projectedFields(fields).filter(field => menuFor(field.group) === menu).map(field => field.group))];
  return [...(menus[menu] || []).filter(domain => available.includes(domain)), ...available.filter(domain => !(menus[menu] || []).includes(domain))];
}
export function schemaOptions(field?: ConfigField): ConfigOption[] {
  return (field?.options || []).flatMap(item => typeof item === 'string' ? [{value:item,label:item}]
    : item && item.value != null ? [{...item,value:String(item.value),label:String(item.label ?? item.value)}] : []);
}
export function registrationDriverValue(value: unknown): string {
  const current=String(value??'roxy').trim().toLowerCase()||'roxy';
  return ({protocol:'protocol_oss_2',protocol_oss:'protocol_oss_2',roxy_oss:'roxy'} as Record<string,string>)[current]||current;
}
export function extractProviders(fields: readonly ConfigField[]) {
  return schemaOptions(fields.find(field => field.key === 'EXTRACT_LINK_DEFAULT_PROVIDER'))
    .map(option => ({...option,value:option.value.toLowerCase(),label:providerLabels[option.value.toLowerCase()] || option.label,enabledKey:`EXTRACT_LINK_${option.value.toUpperCase()}_ENABLED`}))
    .filter(option => fields.some(field => field.key === option.enabledKey));
}
export function subsectionFor(field: ConfigField, fields: readonly ConfigField[]): string {
  const domain = fieldDomain(field), key = field.key;
  if (domain === '邮箱 / OTP') return emailConfigSectionForKey(key)[0]!;
  if (domain === '代理与网络') return proxyConfigSectionForKey(key)[0]!;
  if (domain === '接码平台') return smsConfigSectionForKey(key)[0]!;
  if (domain === 'Codex') return codexConfigSectionForKey(key)[0]!;
  if (domain === '提链') {
    if (key.startsWith('EXTRACT_LINK_PAYMENT_')) return '独立支付';
    const providers = extractProviders(fields);
    if (providers.some(provider => provider.enabledKey === key)) return '通用配置';
    return providers.find(provider => provider.value === 'legacy' ? legacyExtract.has(key) || key.startsWith('EXTRACT_LINK_LEGACY_') : key.startsWith(`EXTRACT_LINK_${provider.value.toUpperCase()}_`))?.label || '通用配置';
  }
  return '';
}
const subsectionOrder: Record<string,string[]> = {
  '邮箱 / OTP':['通用邮箱 / OTP','iCloud 隐藏邮箱','Email Butler','Remail','其他邮箱配置'],
  '接码平台':['通用接码','GrizzlySMS','H 接码','L 接码','其他接码配置'],
  '代理与网络':['任务用池','代理来源','库存策略','高级兼容'], 'Codex':['基础配置','CPA配置','sub2api','Token 自动刷新'],
};
export function subsectionsFor(domain: string, fields: readonly ConfigField[]): string[] {
  if (domain === '提链') return ['通用配置',...extractProviders(fields).map(provider => provider.label),'独立支付'];
  const available = [...new Set(projectedFields(fields).filter(field => field.group === domain).map(field => subsectionFor(field,fields)))].filter(Boolean);
  const order = subsectionOrder[domain] || [];
  if (domain === '代理与网络') available.unshift('任务用池');
  return [...order.filter(section => available.includes(section)), ...available.filter(section => !order.includes(section))];
}
export interface Destination {menu:string;domain:string;section:string}
export function destination(name: string, fields: readonly ConfigField[]): Destination {
  const menu = menuFor(name);
  const domain = menus[name] ? domainsFor(menu,fields)[0] || name : aliases[name] || name;
  return {menu,domain,section:subsectionsFor(domain,fields)[0] || ''};
}
export function fieldDestination(field: ConfigField, fields: readonly ConfigField[]): Destination {
  const domain = fieldDomain(field);
  return {menu:menuFor(domain),domain,section:subsectionFor(field,fields)};
}
export function searchText(field: ConfigField, fields: readonly ConfigField[]): string {
  const domain = fieldDomain(field);
  return [field.key,field.label,field.help,field.group,domain,menuFor(domain),subsectionFor(field,fields),...Object.keys(aliases).filter(name => aliases[name] === domain)].join(' ').toLowerCase();
}
export function findDestination(query: string, fields: readonly ConfigField[], currentMenu=''): Destination | null {
  const needle = query.trim().toLowerCase();
  if (!needle) return null;
  const visible = projectedFields(fields);
  const exact = visible.find(field => field.key.toLowerCase() === needle);
  const matches = visible.filter(field => searchText(field,fields).includes(needle));
  const hit = exact || matches.find(field => menuFor(field.group) === currentMenu) || matches[0];
  if (hit) return fieldDestination(hit,fields);
  const menu = orderedMenus(fields).find(name => name.toLowerCase().includes(needle));
  return menu ? destination(menu,fields) : null;
}
export function visibleFields(owner: ConfigDraftOwner, current: Destination, searching: boolean): ConfigField[] {
  let fields = projectedFields(owner.fields.value).filter(field => field.group === current.domain && (!current.section || subsectionFor(field,owner.fields.value) === current.section));
  if (current.domain === '提链' && current.section === '通用配置') {
    const enabled = new Set(extractProviders(owner.fields.value).map(provider => provider.enabledKey));
    fields = fields.filter(field => !enabled.has(field.key));
  }
  if (current.domain === '代理与网络' && current.section === '代理来源' && !searching) {
    const source = String(owner.readField('PROXY_POOL_SOURCE') || '1024proxy');
    fields = fields.filter(field => {
      if (field.key === 'PROXY_POOL') return source === 'manual';
      const provider = Object.keys(proxyPrefixes).find(key => field.key.startsWith(proxyPrefixes[key]!));
      return !provider || source === provider;
    });
  }
  return fields.filter(field => field.key !== 'CONCURRENCY_POLICY_REVISION');
}
const sectionKeys: Record<string,[string,string[]][]> = {
  ...actions,
  '注册主链路':[['注册基础流程',['REGISTRATION_DRIVER','REGISTRATION_COUNTRY','REGISTRATION_AUTH_MODE','REGISTER_NAME','REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS']],['注册后能力',['REGISTRATION_PLAN_CHECK_ENABLED','ENABLE_2FA','TWOFA_DRIVER','ENABLE_CODEX_AUTO','CODEX_OAUTH_DRIVER','ENABLE_FLOW_TRIGGER']]],
  '账号补全':[['补全项目',['ACCOUNT_COMPLETION_PASSWORD_ENABLED','ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED','ACCOUNT_COMPLETION_2FA_ENABLED','ACCOUNT_COMPLETION_CODEX_ENABLED','ACCOUNT_COMPLETION_REFRESH_AT_ENABLED']],['账号处理策略',['ACCOUNT_AUTH_V2_ENABLED','ACCOUNT_AUTH_RAW_CONTEXT_ENABLED','ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS','ACCOUNT_CODEX_DRIVER']]],
  '注册调试':[['失败诊断',['REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED','REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT','REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB']],['失败现场运行',['REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS','REGISTRATION_DEBUG_MAX_HELD_SESSIONS']],['抓包存储与清理',['REGISTRATION_DEBUG_BODY_MAX_KB','REGISTRATION_DEBUG_BODY_BUDGET_MB','REGISTRATION_DEBUG_GLOBAL_BUDGET_MB','REGISTRATION_DEBUG_RETENTION_DAYS','REGISTRATION_DEBUG_QUEUE_SIZE']]],
};
export function settingGroups(domain: string, fields: ConfigField[]): {title:string;fields:ConfigField[]}[] {
  if (domain === '注册与账号') return [{title:'查询套餐',fields}];
  let definitions = sectionKeys[domain];
  if (domain === '定时任务') definitions = [['Email Butler 风险扫描',['EMAIL_BUTLER_']],['ChatGPT AT 自动刷新',['AT_']],['Codex Token 自动刷新',['CODEX_TOKEN_']],['sub2api 同步与异常巡检',['SUB2API_']]].map(([title,prefixes]) => [title as string,fields.filter(field => (prefixes as string[]).some(prefix => field.key.startsWith(prefix))).map(field => field.key)]);
  if (!definitions) return [{title:'',fields}];
  const seen = new Set(definitions.flatMap(([,keys]) => keys));
  return [...definitions.map(([title,keys]) => ({title,fields:keys.flatMap(key => fields.find(field => field.key===key) || [])})),{title:'其他参数',fields:fields.filter(field => !seen.has(field.key))}].filter(group => group.fields.length);
}
export function navigationCategory(menu: string): string {return ['注册与账号','邮箱与验证码'].includes(menu) ? '业务流程' : ['代理与网络','浏览器','服务集成','提链'].includes(menu) ? '资源与服务' : '系统';}
