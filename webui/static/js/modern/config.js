// ---------- 配置 ----------
let CONFIG_EMAIL_ACTIVE_SECTION_V2 = '通用邮箱 / OTP';
let CONFIG_SMS_ACTIVE_SECTION_V2 = '通用接码';
let CONFIG_CODEX_ACTIVE_SECTION_V2 = '基础配置';
let CONFIG_LIFECYCLE_ACTIVE_SECTION_V2 = '执行方式';
let CONFIG_ACTIVE_GROUP_V2 = '';
let CONFIG_NAV_QUERY_V2 = '';
const CONFIG_PENDING_UPDATES = {};
const CONFIG_LIFECYCLE_GROUP_V2 = '注册与账号';
const CONFIG_LIFECYCLE_SOURCE_GROUPS_V2 = new Set(['注册主链路', '账号补全', '注册调试']);
const CONFIG_LIFECYCLE_SECTION_KEYS_V2 = {
  '执行方式': [
    'REGISTRATION_DRIVER',
    'ACCOUNT_PASSWORD_DRIVER',
    'ACCOUNT_PLAN_CHECK_DRIVER',
    'ACCOUNT_LIVE_CHECK_DRIVER',
    'ACCOUNT_LIVE_CHECK_BROWSER_ENABLED',
    'ACCOUNT_TOKEN_REFRESH_DRIVER',
    'ACCOUNT_AUTH_V2_ENABLED',
    'ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK',
    'ACCOUNT_AUTH_PROFILE_MODE',
    'ACCOUNT_AUTH_RAW_CONTEXT_ENABLED',
    'ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS',
    'TWOFA_DRIVER',
    'ACCOUNT_2FA_DRIVER',
    'CODEX_OAUTH_DRIVER',
    'ACCOUNT_CODEX_DRIVER',
  ],
  '注册主链路': [
    'REGISTRATION_AUTH_MODE',
    'REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS',
    'REGISTRATION_PLAN_CHECK_ENABLED',
    'ENABLE_2FA',
    'ENABLE_CODEX_AUTO',
    'ENABLE_FLOW_TRIGGER',
  ],
  '账号补全': [
    'ACCOUNT_COMPLETION_PASSWORD_ENABLED',
    'ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED',
    'ACCOUNT_COMPLETION_2FA_ENABLED',
    'ACCOUNT_COMPLETION_CODEX_ENABLED',
    'ACCOUNT_COMPLETION_REFRESH_AT_ENABLED',
  ],
  '注册调试': [
    'REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED',
    'REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT',
    'REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB',
    'REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS',
    'REGISTRATION_DEBUG_MAX_HELD_SESSIONS',
    'REGISTRATION_DEBUG_BODY_MAX_KB',
    'REGISTRATION_DEBUG_BODY_BUDGET_MB',
    'REGISTRATION_DEBUG_GLOBAL_BUDGET_MB',
    'REGISTRATION_DEBUG_RETENTION_DAYS',
    'REGISTRATION_DEBUG_QUEUE_SIZE',
  ],
};

function lifecycleFieldsForSection(fields, section) {
  const byKey = new Map((fields || []).map(f => [f.key, f]));
  return (CONFIG_LIFECYCLE_SECTION_KEYS_V2[section] || [])
    .map(key => byKey.get(key))
    .filter(Boolean);
}

function lifecycleFieldValue(key, fallback = '') {
  const field = (CONFIG || []).find(item => item.key === key);
  if (!field) return fallback;
  const value = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, key)
    ? CONFIG_PENDING_UPDATES[key] : field.value;
  return value === null || value === undefined || value === '' ? fallback : value;
}

function lifecycleChoiceLabel(choices, value) {
  const current = String(value || '').trim().toLowerCase();
  const hit = (choices || []).find(item => String(item.value).toLowerCase() === current);
  return hit ? String(hit.label || hit.value) : (current || '未设置');
}

function lifecycleChoicesWithCurrent(choices, value) {
  const current = String(value || '').trim().toLowerCase();
  const options = (choices || []).slice();
  if (current && !options.some(item => String(item.value).toLowerCase() === current)) {
    options.unshift({ value: current, label: `当前配置（${current}）` });
  }
  return options;
}

function configValuesEqual(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    return JSON.stringify(Array.isArray(a) ? a : []) === JSON.stringify(Array.isArray(b) ? b : []);
  }
  if (typeof a === 'boolean' || typeof b === 'boolean') return Boolean(a) === Boolean(b);
  if (typeof a === 'number' || typeof b === 'number') return Number(a) === Number(b);
  return String(a ?? '') === String(b ?? '');
}

function setPendingConfigValue(key, value) {
  const field = CONFIG.find(item => item.key === key);
  if (field && configValuesEqual(value, field.value)) delete CONFIG_PENDING_UPDATES[key];
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
  let copy = count ? `${count} 项更改未保存` : '所有更改已保存';
  if (mode === 'saving') copy = `正在保存 ${count} 项更改…`;
  if (mode === 'error') copy = '保存失败，请重试';
  document.querySelectorAll('#tab-config [data-config-save-state]').forEach(state => {
    state.classList.toggle('is-saved', mode === 'idle' && count === 0);
    state.classList.toggle('is-dirty', mode === 'idle' && count > 0);
    state.classList.toggle('is-saving', mode === 'saving');
    state.classList.toggle('is-error', mode === 'error');
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
}

function configGroups() {
  const groups = {};
  CONFIG.forEach(f => {
    const rawGroup = f.group || '其他';
    const group = CONFIG_LIFECYCLE_SOURCE_GROUPS_V2.has(rawGroup) ? CONFIG_LIFECYCLE_GROUP_V2 : rawGroup;
    (groups[group] = groups[group] || []).push(f);
  });
  return groups;
}

function emailConfigSectionForKey(key) {
  if (['USE_EMAIL_SERVICE','REGISTER_EMAIL','REGISTER_NAME','OTP_MAX_WAIT','OTP_POLL_INTERVAL','EMAIL_SOURCE'].includes(key)) {
    return ['通用邮箱 / OTP', '邮箱来源选择、OTP 等待参数、手动邮箱等通用设置'];
  }
  if (key.startsWith('EMAIL_BUTLER_')) return ['Email Butler', 'Email Butler 通用 /v1 发号、收信、释放与封号信号配置'];
  if (key.startsWith('GPTMAIL_')) return ['GPTMail', 'GPTMail 临时邮箱 API 配置'];
  if (key.startsWith('MAIL_NEST_')) return ['MailNest', 'MailNest / 迈巢临时邮箱 API 配置'];
  if (key.startsWith('CLOUDMAIL_')) return ['CloudMail', 'CloudMail 域名随机邮箱、Token 和收信 API 配置'];
  if (key.startsWith('ICLOUD_HME_')) return ['iCloud 隐藏邮箱', '连接本机 iCloud HME 服务、同步 Hide My Email 别名并按实际转发目标自动收码'];
  if (key.startsWith('OUTLOOK_')) return ['Outlook 邮箱池', 'Outlook 邮箱池和取件模式配置'];
  if (key.startsWith('CLOUDFLARE_')) return ['Cloudflare 临时邮箱', 'Cloudflare Worker 临时邮箱 API、鉴权与路径配置'];
  if (['EMAIL_DOMAIN','QQ_EMAIL','QQ_IMAP_PASSWORD'].includes(key)) return ['Cloudflare 域名邮箱', 'Cloudflare 转发到 QQ 邮箱后的 IMAP 收信配置'];
  return ['其他邮箱配置', ''];
}

function smsConfigSectionForKey(key) {
  if (['SMS_PROVIDER','SMS_COUNTRY','SMS_SERVICE','SMS_MAX_PRICE','SMS_AUTO_SELECT_COUNTRY','SMS_AUTO_COUNTRY_MIN_RATIO','SMS_MAX_RETRIES','SMS_CODE_WAIT','CODEX_PHONE_TOTAL_TIMEOUT'].includes(key)) {
    return ['通用接码', '接码通道选择、国家/服务代码、批次成功率选国、等待和重试参数；H 通道可复用 SMS_SERVICE/SMS_COUNTRY 作为 projectId/country'];
  }
  if (key === 'SMS_API_KEY') return ['GrizzlySMS', 'GrizzlySMS 平台 API Key 配置'];
  if (key.startsWith('H_')) return ['H 接码', 'H_API.md 本地 H 取号服务配置；项目ID/国家留空时复用通用字段'];
  if (key.startsWith('L_')) return ['L 接码', 'L_API.md 本地 L 取号服务配置'];
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
  if (['SUB2API_API_BASE','SUB2API_API_KEY','SUB2API_API_TIMEOUT'].includes(key)) {
    return ['sub2api', 'sub2api 的 API 基址、鉴权和超时配置；用于 Codex OAuth 授权和凭证上传'];
  }
  return ['基础配置', ''];
}

function renderRoxyWorkspaceToolsV2() {
  const current = (CONFIG.find(f => f.key === 'ROXY_WORKSPACE_ID') || {}).value || '';
  return `
    <div class="roxy-workspace-box" style="margin-top:18px;margin-bottom:4px;">
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
  return 'cfg-' + String(name || '')
    .replace(/[^\w\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase();
}
function configGroupDisplayName(name) {
  return name;
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
  if (n.includes('Browser') || n.includes('Roxy') || n.includes('注册')) return '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>';
  return '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>';
}
function getConfigGroupNames() {
  const groups = {};
  (CONFIG || []).forEach(f => { groups[f.group || '其他'] = true; });
  return Object.keys(groups);
}
function configSectionIntro(name) {
  if (name === '网站配置') return '配置网站登录授权码与 Session 签名密钥。';
  if (name === '注册与账号') return '统一配置注册、账号补全和注册调试；执行方式集中维护，链路页只配置功能开关。';
  if (name === '注册主链路') return '配置注册主流程、密码/验证码模式，以及注册后可选能力的开关和执行驱动。';
  if (name === '账号补全') return '配置“补全账号”包含哪些缺失能力，以及各能力使用的执行驱动。';
  if (name === 'Browser Use') return 'Browser Use Cloud 远端浏览器与代理参数。';
  if (name === 'RoxyBrowser') return 'RoxyBrowser API、环境与代理相关设置。';
  if (name === 'Codex') return 'Codex Token、CPA 与 sub2api 相关设置。授权驱动已归入注册主链路。';
  if (name === '邮箱 / OTP') return '邮箱来源、OTP 等待与各邮箱服务商参数。';
  if (name === '接码平台') return '接码通道、国家代码与本地取号服务参数。';
  if (name === '定时任务') return '后台周期任务的开关与执行间隔。上次执行时间保存在数据库中，重启服务会按剩余时间接续，不会重复执行。';
  if (name === '人工节奏') return '注册流程中的随机停顿节奏。';
  if (name === '浏览器画像') return '浏览器语言、时区与出口 IP 画像。';
  if (name === '代理平台') return '为每个注册任务申请独立的粘性住宅代理；当前支持 1024Proxy。';
  if (name === '代理池') return '代理列表与套餐/Agent 网络模式。';
  if (name === '提链') return '提链服务地址、CDK 与并发参数。';
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
  `;
}
function registrationDriverChoices() {
  return [
    { value: 'protocol', label: '纯协议注册' },
    { value: 'roxy', label: 'RoxyBrowser' },
  ];
}
function getRegistrationDriverField() {
  return (CONFIG || []).find(f => f.key === 'REGISTRATION_DRIVER') || null;
}
function getRegistrationDriverValue() {
  const f = getRegistrationDriverField();
  if (!f) return 'protocol';
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  return String(fv == null ? 'protocol' : fv).trim().toLowerCase() || 'protocol';
}
function registrationDriverLabel(value) {
  const cur = String(value || '').trim().toLowerCase();
  const hit = registrationDriverChoices().find(c => String(c.value) === cur);
  return hit ? String(hit.label || hit.value) : (cur || '—');
}
function closeConfigEpSelects(exceptId) {
  document.querySelectorAll('.config-ep-select.open').forEach(el => {
    if (exceptId && el.id === exceptId) return;
    el.classList.remove('open');
  });
}
function toggleConfigEpSelect(wrapId, e) {
  if (e) { e.preventDefault(); e.stopPropagation(); }
  const wrap = document.getElementById(wrapId);
  if (!wrap) return;
  const willOpen = !wrap.classList.contains('open');
  closeConfigEpSelects(wrapId);
  wrap.classList.toggle('open', willOpen);
}
function setRegistrationDriverValue(value) {
  const cur = String(value || 'protocol').trim().toLowerCase() || 'protocol';
  setPendingConfigValue('REGISTRATION_DRIVER', cur);
  closeConfigEpSelects();
  renderRegistrationDriverCard();
  const sectionMount = document.getElementById('configRegistrationSelectV2');
  if (sectionMount) renderRegistrationEpSelect(sectionMount, 'configRegistrationSelectV2');
  bindRoxyWorkspaceToolsV2();
  bindCloudMailToolsV2();
  updateConfigSaveUi();
}
function renderRegistrationEpSelect(mount, wrapId) {
  if (!mount) return;
  const cur = getRegistrationDriverValue();
  const label = registrationDriverLabel(cur);
  const items = registrationDriverChoices().map(c => `
    <button type="button" class="config-ep-select-item${c.value === cur ? ' is-active' : ''}" role="option" data-driver-value="${attrEsc(c.value)}">${esc(c.label)}</button>
  `).join('');
  mount.className = 'config-ep-select';
  mount.id = wrapId;
  mount.innerHTML = `
    <button type="button" class="config-ep-select-btn" data-ep-toggle="${attrEsc(wrapId)}">${esc(label)}</button>
    <div class="config-ep-select-menu" role="listbox">${items}</div>
    <input type="hidden" data-key="REGISTRATION_DRIVER" value="${attrEsc(cur)}">
  `;
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
function renderRegistrationDriverField(f) {
  return `
    <label class="fld config-select-v2-field">
      ${esc(f.label || '注册主流程驱动')}
      <span class="hint">${esc(f.help || '选择注册所用的自动化方式')}</span>
      <div class="config-ep-select" id="configRegistrationSelectV2"></div>
    </label>
  `;
}
function renderFeatureSwitchField(f, opts = {}) {
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  const on = !!fv;
  const withIcon = opts.withIcon !== false;
  const icon = withIcon ? configFeatureIcon(f.key) : null;
  return `
    <div class="config-switch-v2">
      ${withIcon ? `
      <div class="config-switch-v2-top">
        <span class="config-switch-v2-icon ${icon.cls}" aria-hidden="true">
          <svg viewBox="0 0 24 24">${icon.svg}</svg>
        </span>
        <div class="config-switch-v2-label">${esc(f.label)}</div>
      </div>` : `<div class="config-switch-v2-label">${esc(f.label)}</div>`}
      <input class="config-switch-v2-toggle" type="checkbox" role="switch" data-key="${attrEsc(f.key)}"${on ? ' checked' : ''} aria-label="${attrEsc(f.label)}">
      ${opts.extraHtml || ''}
      <p class="config-switch-v2-help">${esc(f.help || '')}</p>
    </div>
  `;
}

function renderLifecycleEnumSwitchField(f, onValue, offValue, label, help) {
  const current = String(lifecycleFieldValue(f.key, offValue)).trim().toLowerCase();
  const on = current === String(onValue).trim().toLowerCase();
  return `
    <div class="config-switch-v2">
      <div class="config-switch-v2-top">
        <span class="config-switch-v2-icon config-switch-v2-icon--default" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/></svg>
        </span>
        <div class="config-switch-v2-label">${esc(label || f.label)}</div>
      </div>
      <input class="config-switch-v2-toggle" type="checkbox" role="switch" data-key="${attrEsc(f.key)}" data-toggle-on-value="${attrEsc(onValue)}" data-toggle-off-value="${attrEsc(offValue)}"${on ? ' checked' : ''} aria-label="${attrEsc(label || f.label)}">
      <p class="config-switch-v2-help">${esc(help || f.help || '')}</p>
    </div>
  `;
}

function renderLifecycleDriverSelect(key, label, help, choices, syncKeys = []) {
  const keys = [...new Set([key, ...syncKeys].filter(Boolean))];
  const value = lifecycleFieldValue(key, lifecycleFieldValue(syncKeys[0], ''));
  const options = lifecycleChoicesWithCurrent(choices, value);
  const values = keys.map(item => String(lifecycleFieldValue(item, '')).trim().toLowerCase()).filter(Boolean);
  const mismatch = values.length > 1 && values.some(item => item !== values[0]);
  const syncAttr = syncKeys.length ? ` data-sync-keys="${attrEsc(syncKeys.join(','))}"` : '';
  const mismatchText = mismatch
    ? `<div class="config-lifecycle-warning-v2">注册与补全当前配置不一致，保存此处选择后会统一为同一个执行方式。</div>`
    : '';
  return `
    <div class="config-lifecycle-driver-v2">
      <div class="config-lifecycle-driver-head">
        <strong>${esc(label)}</strong>
        ${syncKeys.length ? '<span class="config-lifecycle-shared-v2">注册 / 补全共用</span>' : ''}
      </div>
      <p>${esc(help || '')}</p>
      <select data-key="${attrEsc(key)}"${syncAttr} aria-label="${attrEsc(label)}">
        ${options.map(item => `<option value="${attrEsc(item.value)}"${String(item.value).toLowerCase() === String(value).toLowerCase() ? ' selected' : ''}>${esc(item.label)}</option>`).join('')}
      </select>
      ${mismatchText}
    </div>
  `;
}

function renderLifecycleFixedDriver(label, value, help) {
  return `
    <div class="config-lifecycle-driver-v2 config-lifecycle-driver-v2--fixed">
      <div class="config-lifecycle-driver-head">
        <strong>${esc(label)}</strong>
        <span class="config-lifecycle-fixed-v2">当前唯一实现</span>
      </div>
      <p>${esc(help || '')}</p>
      <div class="config-lifecycle-fixed-value-v2">${esc(value)}</div>
    </div>
  `;
}

function renderLifecycleInheritedSummary() {
  const password = lifecycleChoiceLabel([{value: 'roxy', label: 'RoxyBrowser'}], lifecycleFieldValue('ACCOUNT_PASSWORD_DRIVER', 'roxy'));
  const plan = lifecycleChoiceLabel([{value: 'protocol', label: '纯协议'}], lifecycleFieldValue('ACCOUNT_PLAN_CHECK_DRIVER', 'protocol'));
  const twofa = lifecycleChoiceLabel(twofaDriverChoices(), lifecycleFieldValue('ACCOUNT_2FA_DRIVER', lifecycleFieldValue('TWOFA_DRIVER', 'protocol')));
  const codex = lifecycleChoiceLabel(codexOauthDriverChoices(), lifecycleFieldValue('ACCOUNT_CODEX_DRIVER', lifecycleFieldValue('CODEX_OAUTH_DRIVER', 'same_as_registration')));
  return `
    <div class="config-lifecycle-inherited-v2">
      <strong>执行方式来自“执行方式”菜单</strong>
      <span>密码：${esc(password)}</span>
      <span>套餐：${esc(plan)}</span>
      <span>2FA：${esc(twofa)}</span>
      <span>Codex：${esc(codex)}</span>
    </div>
  `;
}

function renderLifecycleSubtabs(active) {
  return `
    <div class="config-subtabs-v2 config-lifecycle-subtabs-v2">
      ${Object.keys(CONFIG_LIFECYCLE_SECTION_KEYS_V2).map(section => `
        <button type="button" data-lifecycle-section-v2="${attrEsc(section)}" class="${section === active ? 'active' : ''}">${esc(section)}</button>
      `).join('')}
    </div>
  `;
}

function renderLifecycleExecutionSection(fields) {
  const registration = lifecycleFieldsForSection(fields, '执行方式');
  const has = key => registration.find(f => f.key === key);
  const cards = [];
  if (has('REGISTRATION_DRIVER')) {
    cards.push(renderLifecycleDriverSelect(
      'REGISTRATION_DRIVER', '注册主流程', '选择注册主链路使用浏览器还是协议。当前支持纯协议注册和 RoxyBrowser。', registrationDriverChoices()
    ));
  }
  if (has('ACCOUNT_PASSWORD_DRIVER')) {
    cards.push(renderLifecycleFixedDriver('密码补全', 'RoxyBrowser', '密码补全当前依赖登录页面，只保留已实现的浏览器执行方式。'));
  }
  if (has('ACCOUNT_PLAN_CHECK_DRIVER')) {
    cards.push(renderLifecycleFixedDriver('套餐查询 / 补全', '纯协议', '套餐查询当前走协议接口，暂不需要填写执行方式。'));
  }
  if (has('ACCOUNT_LIVE_CHECK_DRIVER')) {
    cards.push(renderLifecycleDriverSelect(
      'ACCOUNT_LIVE_CHECK_DRIVER', '普通查活', '阶段1仅保留现有协议型旧 AT 探测；浏览器 probe 和新协议完成验证后再开放切换。', liveCheckDriverChoices()
    ));
  }
  if (has('ACCOUNT_LIVE_CHECK_BROWSER_ENABLED')) {
    cards.push(renderFeatureSwitchField(
      has('ACCOUNT_LIVE_CHECK_BROWSER_ENABLED'),
      { withIcon: false }
    ));
  }
  if (has('ACCOUNT_TOKEN_REFRESH_DRIVER')) {
    cards.push(renderLifecycleDriverSelect(
      'ACCOUNT_TOKEN_REFRESH_DRIVER', '刷新 AT', '默认保持现有刷新链路；Protocol v2 仅在明确选择且总开关开启时使用，失败是否进入现有 Roxy 兜底仍按原规则。', refreshDriverChoices()
    ));
  }
  if (has('ACCOUNT_AUTH_V2_ENABLED')) {
    cards.push(renderFeatureSwitchField(has('ACCOUNT_AUTH_V2_ENABLED'), { withIcon: false }));
  }
  if (has('ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK')) {
    cards.push(renderFeatureSwitchField(has('ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK'), { withIcon: false }));
  }
  if (has('ACCOUNT_AUTH_PROFILE_MODE')) {
    cards.push(renderLifecycleDriverSelect(
      'ACCOUNT_AUTH_PROFILE_MODE', 'Protocol 设备画像', '默认保持现状，每次会话随机画像；account_stable 只对明确开启的 Protocol v2 刷新懒创建账号级画像，不影响注册 device_id、普通查活或旧刷新。', authProfileModeChoices()
    ));
  }
  if (has('ACCOUNT_AUTH_RAW_CONTEXT_ENABLED')) {
    cards.push(renderFeatureSwitchField(has('ACCOUNT_AUTH_RAW_CONTEXT_ENABLED'), { withIcon: false }));
  }
  if (has('ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS')) {
    cards.push(renderConfigPlainFieldV2(has('ACCOUNT_AUTH_RAW_CONTEXT_RETENTION_DAYS')));
  }
  if (has('TWOFA_DRIVER')) {
    cards.push(renderLifecycleDriverSelect(
      'TWOFA_DRIVER', '2FA 开通', '注册和账号补全的 2FA 执行方式统一维护；协议模式失败时仍按现有实现做浏览器兜底。', twofaDriverChoices(), ['ACCOUNT_2FA_DRIVER']
    ));
  }
  if (has('CODEX_OAUTH_DRIVER')) {
    cards.push(renderLifecycleDriverSelect(
      'CODEX_OAUTH_DRIVER', 'Codex OAuth', '注册和账号补全的 Codex 执行方式统一维护；可选纯协议、RoxyBrowser 或跟随注册驱动。', codexOauthDriverChoices(), ['ACCOUNT_CODEX_DRIVER']
    ));
  }
  return `
    <section class="config-section-v2" id="cfg-registration-account" data-config-section="${CONFIG_LIFECYCLE_GROUP_V2}">
      ${renderConfigSectionHead('执行方式', '浏览器和现有稳定链路保持可用；Protocol v2 仅作为显式灰度选项。')}
      ${renderLifecycleSubtabs('执行方式')}
      <div class="config-lifecycle-note-v2">这里仅配置“怎么执行”。是否在注册主链路或账号补全中执行，请分别到对应小菜单打开开关。</div>
      <div class="config-lifecycle-driver-grid-v2">${cards.join('')}</div>
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderLifecycleRegistrationSection(fields) {
  const byKey = key => lifecycleFieldsForSection(fields, '注册主链路').find(f => f.key === key);
  const auth = byKey('REGISTRATION_AUTH_MODE');
  const timeout = byKey('REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS');
  const switches = ['REGISTRATION_PLAN_CHECK_ENABLED', 'ENABLE_2FA', 'ENABLE_CODEX_AUTO', 'ENABLE_FLOW_TRIGGER']
    .map(byKey).filter(Boolean);
  const passwordEnabled = auth && String(lifecycleFieldValue(auth.key, 'otp')).toLowerCase() === 'password';
  return `
    <section class="config-section-v2" id="cfg-registration-account" data-config-section="${CONFIG_LIFECYCLE_GROUP_V2}">
      ${renderConfigSectionHead('注册主链路', '注册时的主流程和可选能力开关；执行方式请到“执行方式”小菜单统一设置。')}
      ${renderLifecycleSubtabs('注册主链路')}
      <div class="config-lifecycle-toggle-grid-v2">
        ${auth ? renderLifecycleEnumSwitchField(auth, 'password', 'otp', '注册时设置账号密码', '开启后注册链路会尝试设置并保存密码；关闭时使用邮箱验证码模式。') : ''}
        ${switches.map(f => renderFeatureSwitchField(f, { withIcon: true })).join('')}
      </div>
      ${passwordEnabled && timeout ? `<div class="config-lifecycle-advanced-block-v2"><strong>密码模式参数</strong><div class="config-section-v2-body">${renderConfigPlainFieldV2(timeout)}</div></div>` : ''}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderLifecycleCompletionSection(fields) {
  const completion = lifecycleFieldsForSection(fields, '账号补全');
  return `
    <section class="config-section-v2" id="cfg-registration-account" data-config-section="${CONFIG_LIFECYCLE_GROUP_V2}">
      ${renderConfigSectionHead('账号补全', '“补全账号”只处理这里开启且实际缺失的能力；不再重复配置执行方式。')}
      ${renderLifecycleSubtabs('账号补全')}
      <div class="config-lifecycle-note-v2">没有额外的“启用补全”总开关：下面所有项目都关闭时，组合补全自然不会执行任何步骤；刷新 AT 仍属于独立操作，只有打开“允许刷新 AT”后才可作为补全前置。</div>
      ${renderLifecycleInheritedSummary()}
      <div class="config-lifecycle-toggle-grid-v2">${completion.map(f => renderFeatureSwitchField(f, { withIcon: false })).join('')}</div>
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderLifecycleDebugSection(fields) {
  const byKey = key => lifecycleFieldsForSection(fields, '注册调试').find(f => f.key === key);
  const diagnostic = byKey('REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED');
  const diagnosticLimits = ['REGISTRATION_FAILURE_DIAGNOSTICS_RESOURCE_LIMIT', 'REGISTRATION_FAILURE_DIAGNOSTICS_TEXT_MAX_KB'].map(byKey).filter(Boolean);
  const runtime = ['REGISTRATION_DEBUG_HOLD_TIMEOUT_SECONDS', 'REGISTRATION_DEBUG_MAX_HELD_SESSIONS'].map(byKey).filter(Boolean);
  const storage = ['REGISTRATION_DEBUG_BODY_MAX_KB', 'REGISTRATION_DEBUG_BODY_BUDGET_MB', 'REGISTRATION_DEBUG_GLOBAL_BUDGET_MB', 'REGISTRATION_DEBUG_RETENTION_DAYS', 'REGISTRATION_DEBUG_QUEUE_SIZE'].map(byKey).filter(Boolean);
  const renderInputs = group => group.length ? `<div class="config-section-v2-body">${group.map(renderConfigPlainFieldV2).join('')}</div>` : '';
  return `
    <section class="config-section-v2" id="cfg-registration-account" data-config-section="${CONFIG_LIFECYCLE_GROUP_V2}">
      ${renderConfigSectionHead('注册调试', '普通失败诊断和调试任务运行参数；调试模式本身仍在注册任务面板中按批次开启。')}
      ${renderLifecycleSubtabs('注册调试')}
      <div class="config-lifecycle-toggle-grid-v2">${diagnostic ? renderFeatureSwitchField(diagnostic, { withIcon: false }) : ''}</div>
      ${diagnosticLimits.length ? `<details class="config-lifecycle-advanced-block-v2" open><summary>失败诊断上限</summary>${renderInputs(diagnosticLimits)}</details>` : ''}
      ${runtime.length ? `<details class="config-lifecycle-advanced-block-v2" open><summary>调试现场运行</summary>${renderInputs(runtime)}</details>` : ''}
      ${storage.length ? `<details class="config-lifecycle-advanced-block-v2"><summary>抓包存储与清理</summary>${renderInputs(storage)}</details>` : ''}
      <div class="config-lifecycle-note-v2">“调试模式”是单个注册批次的现场保留开关；本页只控制失败诊断、保留时长和抓包预算，不会默认暂停所有任务。</div>
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderRegistrationAccountSectionV2(fields) {
  const active = Object.prototype.hasOwnProperty.call(CONFIG_LIFECYCLE_SECTION_KEYS_V2, CONFIG_LIFECYCLE_ACTIVE_SECTION_V2)
    ? CONFIG_LIFECYCLE_ACTIVE_SECTION_V2 : '执行方式';
  CONFIG_LIFECYCLE_ACTIVE_SECTION_V2 = active;
  if (active === '注册主链路') return renderLifecycleRegistrationSection(fields);
  if (active === '账号补全') return renderLifecycleCompletionSection(fields);
  if (active === '注册调试') return renderLifecycleDebugSection(fields);
  return renderLifecycleExecutionSection(fields);
}

function twofaDriverChoices() {
  return [
    { value: 'protocol', label: '协议直开（新鲜 AT）' },
    { value: 'browser', label: '浏览器页面（RoxyBrowser）' },
  ];
}
function liveCheckDriverChoices() {
  const choices = [
    { value: 'protocol_current', label: '现有协议（保持现状）' },
  ];
  const rawEnabled = lifecycleFieldValue('ACCOUNT_LIVE_CHECK_BROWSER_ENABLED', false);
  const enabled = rawEnabled === true || ['1', 'true', 'yes', 'on'].includes(String(rawEnabled).trim().toLowerCase());
  if (enabled) choices.push({ value: 'browser_roxy', label: 'Roxy 浏览器（旧 AT probe）' });
  return choices;
}
function refreshDriverChoices() {
  return [
    { value: 'legacy', label: '现有刷新链路（保持现状）' },
    { value: 'protocol_v2', label: 'Protocol v2 密码 / MFA（需开启总开关）' },
  ];
}
function authProfileModeChoices() {
  return [
    { value: 'current', label: '当前会话画像（保持现状）' },
    { value: 'account_stable', label: '账号稳定 Protocol 画像（懒创建）' },
  ];
}
function renderTwofaDriverControl(f) {
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  const current = String(fv == null ? 'protocol' : fv).trim().toLowerCase() || 'protocol';
  return `
    <div class="config-twofa-driver-v2">
      <div class="config-twofa-driver-v2-label">${esc(f.label)}</div>
      <select data-key="${attrEsc(f.key)}" aria-label="${attrEsc(f.label)}">
        ${twofaDriverChoices().map(item => `<option value="${attrEsc(item.value)}"${current === item.value ? ' selected' : ''}>${esc(item.label)}</option>`).join('')}
      </select>
      <p class="config-twofa-driver-v2-help">${esc(f.help || '')}</p>
    </div>
  `;
}
function renderCodexOauthDriverControl(f) {
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  const current = String(fv == null ? 'protocol' : fv).trim().toLowerCase() || 'protocol';
  return `
    <div class="config-twofa-driver-v2">
      <div class="config-twofa-driver-v2-label">${esc(f.label)}</div>
      <select data-key="${attrEsc(f.key)}" aria-label="${attrEsc(f.label)}">
        ${codexOauthDriverChoices().map(item => `<option value="${attrEsc(item.value)}"${current === item.value ? ' selected' : ''}>${esc(item.label)}</option>`).join('')}
      </select>
      <p class="config-twofa-driver-v2-help">${esc(f.help || '')}</p>
    </div>
  `;
}
function configDriverChoices(f) {
  if (f.key === 'ACCOUNT_PASSWORD_DRIVER') {
    return [{ value: 'roxy', label: 'RoxyBrowser（当前唯一实现）' }];
  }
  if (f.key === 'ACCOUNT_PLAN_CHECK_DRIVER') {
    return [{ value: 'protocol', label: '纯协议（当前唯一实现）' }];
  }
  if (f.key === 'ACCOUNT_LIVE_CHECK_DRIVER') return liveCheckDriverChoices();
  if (f.key === 'ACCOUNT_TOKEN_REFRESH_DRIVER') return refreshDriverChoices();
  if (f.key === 'ACCOUNT_AUTH_PROFILE_MODE') return authProfileModeChoices();
  if (f.key === 'ACCOUNT_2FA_DRIVER') return twofaDriverChoices();
  if (f.key === 'ACCOUNT_CODEX_DRIVER') return codexOauthDriverChoices();
  return null;
}
function renderConfigPlainFieldV2(f) {
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  let control = '';
  const driverChoices = configDriverChoices(f);
  if (driverChoices) {
    const current = String(fv == null ? '' : fv).trim().toLowerCase();
    const options = driverChoices.slice();
    if (current && !options.some(item => item.value === current)) {
      options.unshift({ value: current, label: `当前配置（${current}）` });
    }
    const disabled = options.length === 1 ? ' disabled' : '';
    control = `<select data-key="${attrEsc(f.key)}"${disabled}>${options.map(item => `<option value="${attrEsc(item.value)}"${current === item.value ? ' selected' : ''}>${esc(item.label)}</option>`).join('')}</select>`;
  } else if (f.key === 'REGISTRATION_AUTH_MODE') {
    const options = [['otp','不设置密码（邮箱验证码）'],['password','设置账号密码']];
    control = `<select data-key="${attrEsc(f.key)}">${options.map(([v,l]) => `<option value="${v}"${String(fv)===v?' selected':''}>${l}</option>`).join('')}</select>`;
  } else if (f.key === 'REGISTRATION_PROXY_MODE') {
    const options = [['pool','静态代理池'],['1024','1024Proxy 平台 API'],['none','直连']];
    control = `<select data-key="${attrEsc(f.key)}">${options.map(([v,l]) => `<option value="${v}"${String(fv)===v?' selected':''}>${l} (${v})</option>`).join('')}</select>`;
  } else if (f.key === 'PROXY_1024_REGION') {
    const regions = [
      ['','沿用 API URL'],['US','美国'],['JP','日本'],['GB','英国'],['CA','加拿大'],['AU','澳大利亚'],
      ['DE','德国'],['FR','法国'],['NL','荷兰'],['SG','新加坡'],['KR','韩国'],['HK','中国香港'],
      ['TW','中国台湾'],['ES','西班牙'],['IT','意大利'],['CH','瑞士'],['SE','瑞典'],['NO','挪威'],
      ['PL','波兰'],['BR','巴西'],['MX','墨西哥'],['IN','印度'],['ID','印度尼西亚'],['TH','泰国'],
      ['VN','越南'],['PH','菲律宾'],['MY','马来西亚'],['AE','阿联酋'],['TR','土耳其'],['Rand','随机地区'],
    ];
    const current = String(fv == null ? '' : fv);
    if (current && !regions.some(([v]) => v === current)) regions.splice(1, 0, [current, '当前配置']);
    control = `<select data-key="${attrEsc(f.key)}">${regions.map(([v,l]) => `<option value="${attrEsc(v)}"${current===v?' selected':''}>${esc(l)}${v ? ` (${esc(v)})` : ''}</option>`).join('')}</select>`;
  } else if (f.key === 'PROXY_1024_PROTOCOL') {
    const options = ['http','https','socks5','socks5h'];
    control = `<select data-key="${attrEsc(f.key)}">${options.map(v => `<option value="${v}"${String(fv)===v?' selected':''}>${v}</option>`).join('')}</select>`;
  } else if (f.type === 'int') {
    control = `<input type="number" data-key="${attrEsc(f.key)}" value="${attrEsc(fv == null ? '' : fv)}">`;
  } else if (f.type === 'float') {
    control = `<input type="number" step="0.1" data-key="${attrEsc(f.key)}" value="${attrEsc(fv == null ? '' : fv)}">`;
  } else if (f.type === 'list_str_multiline') {
    control = `<textarea data-key="${attrEsc(f.key)}" placeholder="每行一条，可留空">${attrEsc((fv || []).join('\n'))}</textarea>`;
  } else {
    const shown = isPlaceholderEmpty(fv) ? '' : fv;
    const inputType = f.secret ? 'password' : 'text';
    const ph = f.secret ? '保存在 .env，可留空' : '可留空';
    control = `<input type="${inputType}" data-key="${attrEsc(f.key)}" value="${attrEsc(shown)}" placeholder="${ph}" autocomplete="off" spellcheck="false">`;
  }
  return `
    <label class="fld">
      ${esc(f.label)}
      <span class="hint">${esc(f.help || '')}</span>
      ${control}
    </label>
  `;
}
function renderProxyProviderToolsV2() {
  return `
    <div class="roxy-workspace-box" style="margin-top:18px;margin-bottom:4px;">
      <div>
        <b>1024Proxy 本地联调</b>
        <div class="hint">会实际提取并检测 1 个 IP，可能产生少量流量或配额消耗。API 请求会绕过系统代理。</div>
      </div>
      <div class="row">
        <div class="action-cell"><button class="btn" type="button" id="btnTestProxy1024V2">提取并测试 1 个 IP</button></div>
      </div>
      <div id="proxy1024TestStatusV2" class="muted" style="font-size:12px;">尚未测试</div>
    </div>
  `;
}

function bindProxyProviderToolsV2() {
  const btn = $('#btnTestProxy1024V2');
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = '1';
  btn.addEventListener('click', testProxy1024V2);
}

async function testProxy1024V2() {
  const btn = $('#btnTestProxy1024V2');
  const status = $('#proxy1024TestStatusV2');
  const value = (key, fallback = '') => {
    const el = document.querySelector(`#configSectionsV2 [data-key="${key}"]`);
    return el ? readConfigElementValue(el, CONFIG.find(x => x.key === key)) : fallback;
  };
  if (btn) btn.disabled = true;
  if (status) status.textContent = '正在提取并检测代理...';
  try {
    const r = await api('/api/proxy-provider/test', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        api_url: value('PROXY_1024_API_URL'),
        region: value('PROXY_1024_REGION'),
        protocol: value('PROXY_1024_PROTOCOL', 'http'),
        session_minutes: value('PROXY_1024_SESSION_MINUTES', 30),
        validate: value('PROXY_1024_VALIDATE', true),
      }),
    });
    const l = r.lease || {};
    if (status) status.innerHTML = `✅ ${esc(l.provider || '1024Proxy')} · ${esc(l.endpoint || '-')} · 出口 ${esc(l.exit_ip || '-')} · ${esc(l.region || '-')} · 有效至 ${esc(l.expires_at || '-')}`;
    showToast(r.message || '代理测试成功');
  } catch(e) {
    if (status) status.innerHTML = `<span style="color:var(--red);">测试失败：${esc(e.message)}</span>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}
function renderMixedConfigSectionV2(name, fields, intro) {
  const slug = configGroupSlug(name);
  const switches = fields.filter(f => f.type === 'bool');
  const inputs = fields.filter(f => f.type !== 'bool');
  const extra = name === 'RoxyBrowser' ? renderRoxyWorkspaceToolsV2() : (name === '代理平台' ? renderProxyProviderToolsV2() : '');
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

function codexOauthDriverChoices() {
  return [
    { value: 'protocol', label: '纯协议授权' },
    { value: 'roxy', label: 'RoxyBrowser' },
    { value: 'same_as_registration', label: '跟随注册驱动' },
  ];
}
function getCodexOauthDriverValue() {
  const f = (CONFIG || []).find(x => x.key === 'CODEX_OAUTH_DRIVER');
  if (!f) return 'protocol';
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  return String(fv == null ? 'protocol' : fv).trim().toLowerCase() || 'protocol';
}
function codexOauthDriverLabel(value) {
  const cur = String(value || '').trim().toLowerCase();
  const hit = codexOauthDriverChoices().find(c => String(c.value) === cur);
  return hit ? String(hit.label || hit.value) : (cur || '—');
}
function setCodexOauthDriverValue(value) {
  const cur = String(value || 'protocol').trim().toLowerCase() || 'protocol';
  setPendingConfigValue('CODEX_OAUTH_DRIVER', cur);
  closeConfigEpSelects();
  renderConfigLayoutV2();
}
function renderCodexOauthDriverField() {
  const cur = getCodexOauthDriverValue();
  const label = codexOauthDriverLabel(cur);
  const wrapId = 'configCodexOauthSelectV2';
  const items = codexOauthDriverChoices().map(c => `
    <button type="button" class="config-ep-select-item${c.value === cur ? ' is-active' : ''}" role="option" data-codex-oauth-value="${attrEsc(c.value)}">${esc(c.label)}</button>
  `).join('');
  return `
    <label class="fld config-select-v2-field">
      Codex 授权驱动
      <span class="hint">选择 Codex 授权所用的自动化方式</span>
      <div class="config-ep-select" id="${wrapId}">
        <button type="button" class="config-ep-select-btn" data-ep-toggle="${wrapId}">${esc(label)}</button>
        <div class="config-ep-select-menu" role="listbox">${items}</div>
        <input type="hidden" data-key="CODEX_OAUTH_DRIVER" value="${attrEsc(cur)}">
      </div>
    </label>
  `;
}
function renderCodexFieldV2(f) {
  if (f.key === 'CODEX_OAUTH_DRIVER') return renderCodexOauthDriverField();
  if (f.type === 'bool') return renderFeatureSwitchField(f, { withIcon: false });
  return renderConfigPlainFieldV2(f);
}

function renderSectionedConfigSectionV2(name, fields, sectionForKey, preferred, activeRef, dataAttr) {
  const slug = configGroupSlug(name);
  const bySection = {};
  for (const f of fields) {
    const [section, help] = sectionForKey(f.key || '');
    if (!bySection[section]) bySection[section] = { help, fields: [] };
    bySection[section].fields.push(f);
  }
  const sections = preferred.filter(x => bySection[x]).concat(Object.keys(bySection).filter(x => !preferred.includes(x)));
  let active = activeRef.get();
  if (!sections.includes(active)) {
    active = sections[0] || '';
    activeRef.set(active);
  }
  const current = bySection[active] || { help: '', fields: [] };
  const switches = current.fields.filter(f => f.type === 'bool');
  const inputs = current.fields.filter(f => f.type !== 'bool');
  let extra = '';
  if (name === '邮箱 / OTP' && active === 'CloudMail') {
    extra = renderCloudMailTokenToolsV2();
  }
  if (name === '邮箱 / OTP' && active === 'Email Butler') {
    extra = renderEmailButlerToolsV2();
  }
  if (name === '邮箱 / OTP' && active === 'iCloud 隐藏邮箱') {
    extra = renderICloudHMEToolsV2();
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
      ${current.help ? `<p class="config-section-v2-subhelp">${esc(current.help)}</p>` : ''}
      ${switches.length ? `<div class="config-switches-v2">${switches.map(f => renderFeatureSwitchField(f, { withIcon: false })).join('')}</div>` : ''}
      ${inputs.length ? `<div class="config-section-v2-body">${inputs.map(renderConfigPlainFieldV2).join('')}</div>` : ''}
      ${extra}
      ${renderConfigSaveActions()}
    </section>
  `;
}
function renderCloudMailTokenToolsV2() {
  const hasCloudMail = CONFIG.some(f => String(f.key || '').startsWith('CLOUDMAIL_'));
  if (!hasCloudMail) return '';
  return `
    <div class="roxy-workspace-box" style="margin-top:18px;">
      <div>
        <b>CloudMail Token</b>
        <div class="hint">填写 API 地址、管理员邮箱、密码后，生成 Token；保存配置不会自动生成。</div>
      </div>
      <div class="action-cell">
        <button class="btn primary" type="button" id="btnGenCloudMailTokenV2">生成 CloudMail Token</button>
        <button class="btn" type="button" id="btnLoadCloudMailDomainsV2">获取 CloudMail 域名</button>
      </div>
      <div id="cloudMailTokenStatusV2" class="muted" style="font-size:12px;">未生成</div>
    </div>
  `;
}
function renderEmailButlerToolsV2() {
  const hasButler = CONFIG.some(f => String(f.key || '').startsWith('EMAIL_BUTLER_'));
  if (!hasButler) return '';
  return `
    <div class="roxy-workspace-box" style="margin-top:18px;">
      <div>
        <b>Email Butler 连接</b>
        <div class="hint">使用当前表单中的 /v1 URL 与 API Key 验证客户端策略和发号、收信、释放、信号扫描能力，不会租用邮箱。</div>
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
  status.textContent = '正在调用 Email Butler /v1/me...';
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
    status.innerHTML = `✅ 连接成功：${esc(r.name || 'Email Butler')} · ${esc(policy)} · ${Number((r.capabilities || []).length)} 项能力`;
    showToast('Email Butler 连接成功');
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">连接失败：${esc(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}
function bindCloudMailToolsV2() {
  const genBtn = $('#btnGenCloudMailTokenV2');
  const domainBtn = $('#btnLoadCloudMailDomainsV2');
  if (genBtn && !genBtn.dataset.bound) {
    genBtn.dataset.bound = '1';
    genBtn.addEventListener('click', () => genCloudMailTokenV2());
  }
  if (domainBtn && !domainBtn.dataset.bound) {
    domainBtn.dataset.bound = '1';
    domainBtn.addEventListener('click', () => loadCloudMailDomainsV2());
  }
}
function renderICloudHMEToolsV2() {
  return `
    <div class="roxy-workspace-box" style="margin-top:18px;">
      <div>
        <b>iCloud Hide My Email</b>
        <div class="hint">连接本机服务后同步 Apple 隐藏邮箱库存，并确认 sidecar 或 Email Butler PG 收件链路。Apple Cookie 不会保存到 turb。</div>
      </div>
      <div class="action-cell">
        <button class="btn primary" type="button" id="btnTestICloudHMEV2">连接并同步</button>
      </div>
      <div id="icloudHMEStatusV2" class="muted" style="font-size:12px;">尚未检测</div>
    </div>
  `;
}
function bindICloudHMEToolsV2() {
  const btn = $('#btnTestICloudHMEV2');
  if (btn && !btn.dataset.bound) {
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => testICloudHMEV2());
  }
}
async function testICloudHMEV2() {
  const btn = $('#btnTestICloudHMEV2');
  const status = $('#icloudHMEStatusV2');
  if (!btn || !status) return;
  btn.disabled = true;
  status.textContent = '正在连接、同步别名并检测实际收件通道...';
  try {
    const r = await api('/api/icloud-hme/test', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        api_base: _configValueV2('ICLOUD_HME_API_BASE').trim(),
        account_id: _configValueV2('ICLOUD_HME_ACCOUNT_ID').trim(),
        timeout: Number(_configValueV2('ICLOUD_HME_REQUEST_TIMEOUT')) || 35,
      }),
    });
    status.innerHTML = `✅ ${esc(r.message || 'iCloud HME 连接成功')}`;
    showToast(`已同步 ${Number(r.remote_aliases || 0)} 个 iCloud 隐藏邮箱`);
    if (typeof loadOutlook === 'function') await loadOutlook();
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">检测失败：${esc(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}
function _configValueV2(key) {
  const root = document.querySelector(`#configSectionsV2 [data-key="${CSS.escape(key)}"]`);
  if (root) return root.value;
  const f = CONFIG.find(x => x.key === key);
  return f ? String(f.value ?? '') : '';
}
async function genCloudMailTokenV2() {
  const btn = $('#btnGenCloudMailTokenV2');
  const status = $('#cloudMailTokenStatusV2');
  if (!btn || !status) return;
  btn.disabled = true;
  status.textContent = '正在调用 CloudMail /api/public/genToken...';
  try {
    const r = await api('/api/cloudmail/gen-token', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        api_base: _configValueV2('CLOUDMAIL_API_BASE').trim(),
        admin_email: _configValueV2('CLOUDMAIL_ADMIN_EMAIL').trim(),
        password: _configValueV2('CLOUDMAIL_PASSWORD').trim(),
        path: _configValueV2('CLOUDMAIL_TOKEN_PATH').trim() || '/api/public/genToken',
      }),
    });
    status.innerHTML = `✅ ${esc(r.message || 'Token 已生成并保存')}`;
    showToast('CloudMail Token 已生成');
    await loadConfig();
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">生成失败：${esc(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}
async function loadCloudMailDomainsV2() {
  const btn = $('#btnLoadCloudMailDomainsV2');
  const status = $('#cloudMailTokenStatusV2');
  if (!btn || !status) return;
  btn.disabled = true;
  status.textContent = '正在从 CloudMail 平台获取可用域名...';
  try {
    const r = await api('/api/cloudmail/domains', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        api_base: _configValueV2('CLOUDMAIL_API_BASE').trim(),
        admin_email: _configValueV2('CLOUDMAIL_ADMIN_EMAIL').trim(),
        password: _configValueV2('CLOUDMAIL_PASSWORD').trim(),
        token: _configValueV2('CLOUDMAIL_AUTH_TOKEN').trim(),
      }),
    });
    const domains = Array.isArray(r.domains) ? r.domains : [];
    status.innerHTML = `✅ ${esc(r.message || '域名已获取')}：<span class="mono">${esc(domains.join(', '))}</span>`;
    showToast(`CloudMail 已获取 ${domains.length} 个域名`);
    await loadConfig();
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">获取域名失败：${esc(e.message)}</span>`;
  } finally {
    btn.disabled = false;
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
      ${current.help ? `<p class="config-section-v2-subhelp">${esc(current.help)}</p>` : ''}
      ${switches.length ? `<div class="config-switches-v2">${switches.map(f => renderFeatureSwitchField(f, { withIcon: false })).join('')}</div>` : ''}
      ${orderedInputs.length ? `<div class="config-section-v2-body">${orderedInputs.map(renderCodexFieldV2).join('')}</div>` : ''}
      ${renderConfigSaveActions()}
    </section>
  `;
}

function renderConfigSectionV2(name, fields) {
  const slug = configGroupSlug(name);
  if (name === '网站配置') {
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
  if (name === CONFIG_LIFECYCLE_GROUP_V2) {
    return renderRegistrationAccountSectionV2(fields);
  }
  if (name === '注册主链路') {
    const preferred = [
      'REGISTRATION_DRIVER',
      'REGISTRATION_AUTH_MODE',
      'REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS',
      'REGISTRATION_PLAN_CHECK_ENABLED',
      'ENABLE_2FA',
      'TWOFA_DRIVER',
      'ENABLE_CODEX_AUTO',
      'CODEX_OAUTH_DRIVER',
      'ENABLE_FLOW_TRIGGER',
    ];
    const ordered = preferred
      .map(k => fields.find(f => f.key === k))
      .filter(Boolean)
      .concat(fields.filter(f => !preferred.includes(f.key)));
    const twofaDriver = ordered.find(f => f.key === 'TWOFA_DRIVER');
    const codexDriver = ordered.find(f => f.key === 'CODEX_OAUTH_DRIVER');
    const registrationDriver = ordered.find(f => f.key === 'REGISTRATION_DRIVER');
    const switches = ordered.filter(f => f.type === 'bool');
    const otherFields = ordered.filter(f => (
      f.type !== 'bool' &&
      !['REGISTRATION_DRIVER', 'TWOFA_DRIVER', 'CODEX_OAUTH_DRIVER'].includes(f.key)
    ));
    return `
      <section class="config-section-v2" id="${esc(slug)}" data-config-section="${esc(name)}">
        ${renderConfigSectionHead(name, configSectionIntro(name))}
        <div class="config-section-v2-body">
          ${registrationDriver ? renderRegistrationDriverField(registrationDriver) : '<div class="banner warn">未找到注册主流程驱动配置项</div>'}
          ${otherFields.map(renderConfigPlainFieldV2).join('')}
        </div>
        <div class="config-switches-v2">
          ${switches.map(f => renderFeatureSwitchField(f, {
            withIcon: true,
            extraHtml: f.key === 'ENABLE_2FA' && twofaDriver
              ? renderTwofaDriverControl(twofaDriver)
              : (f.key === 'ENABLE_CODEX_AUTO' && codexDriver ? renderCodexOauthDriverControl(codexDriver) : ''),
          })).join('')}
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
      ['通用邮箱 / OTP', 'iCloud 隐藏邮箱', 'Email Butler', 'GPTMail', 'MailNest', 'CloudMail', 'Outlook 邮箱池', 'Cloudflare 临时邮箱', 'Cloudflare 域名邮箱', '其他邮箱配置'],
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
  return renderMixedConfigSectionV2(name, fields, configSectionIntro(name));
}
function applyConfigNavFilter() {
  const query = CONFIG_NAV_QUERY_V2.trim().toLowerCase();
  const items = Array.from(document.querySelectorAll('#configNavV2 [data-config-nav]'));
  let shown = 0;
  items.forEach(btn => {
    const haystack = `${btn.dataset.configNav || ''} ${btn.textContent || ''}`.toLowerCase();
    const matches = !query || haystack.includes(query);
    btn.hidden = !matches;
    if (matches) shown += 1;
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
  const names = Object.keys(groups);
  const lifecycleIndex = names.indexOf(CONFIG_LIFECYCLE_GROUP_V2);
  if (lifecycleIndex > 0) names.unshift(names.splice(lifecycleIndex, 1)[0]);
  if (!names.length) {
    nav.innerHTML = '<div class="muted" style="padding:8px 12px;font-size:13px;">暂无分组</div>';
    sections.innerHTML = '';
    const count = document.getElementById('configNavCountV2');
    if (count) count.textContent = '0';
    updateConfigSaveUi();
    return;
  }
  const savedGroup = localStorage.getItem('gpt_console_config_group');
  if (!CONFIG_ACTIVE_GROUP_V2 && CONFIG_LIFECYCLE_SOURCE_GROUPS_V2.has(savedGroup)) {
    CONFIG_ACTIVE_GROUP_V2 = CONFIG_LIFECYCLE_GROUP_V2;
    CONFIG_LIFECYCLE_ACTIVE_SECTION_V2 = savedGroup;
  }
  if (!CONFIG_ACTIVE_GROUP_V2 && savedGroup && names.includes(savedGroup)) CONFIG_ACTIVE_GROUP_V2 = savedGroup;
  if (!CONFIG_ACTIVE_GROUP_V2 || !names.includes(CONFIG_ACTIVE_GROUP_V2)) CONFIG_ACTIVE_GROUP_V2 = names[0];
  nav.innerHTML = names.map(name => `
    <button type="button" class="config-nav-v2-item${name === CONFIG_ACTIVE_GROUP_V2 ? ' is-active' : ''}" data-config-nav="${esc(name)}" data-config-target="${esc(configGroupSlug(name))}">
      <svg viewBox="0 0 24 24" aria-hidden="true">${configNavIcon(name)}</svg>
      <span>${esc(configGroupDisplayName(name))}</span>
    </button>
  `).join('');
  applyConfigNavFilter();
  sections.innerHTML = renderConfigSectionV2(CONFIG_ACTIVE_GROUP_V2, groups[CONFIG_ACTIVE_GROUP_V2] || []);
  renderRegistrationDriverCard();
  renderConfigOverviewCards();
  const sectionMount = document.getElementById('configRegistrationSelectV2');
  if (sectionMount) renderRegistrationEpSelect(sectionMount, 'configRegistrationSelectV2');
  bindRoxyWorkspaceToolsV2();
  bindEmailButlerToolsV2();
  bindCloudMailToolsV2();
  bindICloudHMEToolsV2();
  bindProxyProviderToolsV2();
  updateConfigSaveUi();
}
function scrollToConfigSection(slug) {
  const el = document.getElementById(slug);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function setActiveConfigNav(slug) {
  document.querySelectorAll('#configNavV2 .config-nav-v2-item').forEach(btn => {
    btn.classList.toggle('is-active', btn.dataset.configTarget === slug);
  });
}
function openConfigGroup(name) {
  CONFIG_ACTIVE_GROUP_V2 = String(name || '');
  localStorage.setItem('gpt_console_config_group', CONFIG_ACTIVE_GROUP_V2);
  activateTab('config');
  if (CONFIG.length) renderConfigLayoutV2();
}
function bindConfigLayoutV2() {
  const nav = document.getElementById('configNavV2');
  const search = document.getElementById('configNavSearchV2');
  if (search && !search.dataset.bound) {
    search.dataset.bound = '1';
    search.value = CONFIG_NAV_QUERY_V2;
    search.addEventListener('input', () => {
      CONFIG_NAV_QUERY_V2 = search.value;
      applyConfigNavFilter();
    });
  }
  if (!nav || nav.dataset.bound) return;
  nav.dataset.bound = '1';
  nav.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-config-nav]');
    if (!btn) return;
    CONFIG_ACTIVE_GROUP_V2 = btn.dataset.configNav;
    localStorage.setItem('gpt_console_config_group', CONFIG_ACTIVE_GROUP_V2);
    renderConfigLayoutV2();
  });
  const layout = document.getElementById('configLayoutV2');
  if (layout && !layout.dataset.epBound) {
    layout.dataset.epBound = '1';
    layout.addEventListener('click', (e) => {
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
      const lifecycleTab = e.target.closest('[data-lifecycle-section-v2]');
      if (lifecycleTab) {
        e.preventDefault();
        CONFIG_LIFECYCLE_ACTIVE_SECTION_V2 = lifecycleTab.dataset.lifecycleSectionV2;
        renderConfigLayoutV2();
        return;
      }
      const toggle = e.target.closest('[data-ep-toggle]');
      if (toggle) {
        toggleConfigEpSelect(toggle.dataset.epToggle, e);
        return;
      }
      const item = e.target.closest('[data-driver-value]');
      if (item) {
        e.preventDefault();
        e.stopPropagation();
        setRegistrationDriverValue(item.dataset.driverValue);
        return;
      }
      const oauthItem = e.target.closest('[data-codex-oauth-value]');
      if (oauthItem) {
        e.preventDefault();
        e.stopPropagation();
        setCodexOauthDriverValue(oauthItem.dataset.codexOauthValue);
        return;
      }
    });
  }
  if (!document.documentElement.dataset.configEpCloseBound) {
    document.documentElement.dataset.configEpCloseBound = '1';
    document.addEventListener('click', () => closeConfigEpSelects());
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
    CONFIG = await api('/api/config');
    renderConfigLayoutV2();
    bindConfigLayoutV2();
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
  if (el.dataset.toggleOnValue) return el.checked ? el.dataset.toggleOnValue : el.dataset.toggleOffValue;
  if (f.type === 'list_str_multiline') return el.value.split('\n').map(s=>s.trim()).filter(Boolean);
  if (f.type === 'bool') {
    if (el.type === 'checkbox') return !!el.checked;
    return el.value === 'true';
  }
  if (f.type === 'int') return parseInt(el.value || '0', 10);
  if (f.type === 'float') return parseFloat(el.value || '0');
  return isPlaceholderEmpty(el.value) ? '' : el.value.trim();
}

function trackConfigFieldChange(e) {
  const el = e.target.closest('[data-key]');
  if (!el || !el.closest('#tab-config')) return;
  const f = CONFIG.find(x => x.key === el.dataset.key);
  if (!f) return;
  const value = readConfigElementValue(el, f);
  const syncKeys = String(el.dataset.syncKeys || '').split(',').map(key => key.trim()).filter(Boolean);
  [f.key, ...syncKeys].filter((key, index, all) => all.indexOf(key) === index).forEach(key => {
    if (CONFIG.some(item => item.key === key)) setPendingConfigValue(key, value);
  });
  renderConfigOverviewCards();
  if (f.key === 'REGISTRATION_AUTH_MODE' || f.key === 'ACCOUNT_LIVE_CHECK_BROWSER_ENABLED') renderConfigLayoutV2();
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
    const r = await api('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({updates}) });
    for (const [k, v] of Object.entries(updates)) { const f = CONFIG.find(x => x.key === k); if (f) f.value = v; delete CONFIG_PENDING_UPDATES[k]; }
    renderConfigLayoutV2();
    await loadCapabilities();
    await loadRegistrationEmailSources();
    showToast(r.reloaded ? '配置已生效' : '配置已保存（需重启）');
  } catch(e) {
    updateConfigSaveUi('error');
    showToast('保存失败: ' + e.message);
  }
}
$('#tab-config').addEventListener('click', (e) => {
  const btn = e.target.closest('[data-save-config-v2]');
  if (!btn) return;
  saveConfigUpdates(btn);
});
