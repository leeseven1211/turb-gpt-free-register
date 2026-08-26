// ---------- 配置 ----------
let CONFIG_EMAIL_ACTIVE_SECTION_V2 = '通用邮箱 / OTP';
let CONFIG_SMS_ACTIVE_SECTION_V2 = '通用接码';
let CONFIG_CODEX_ACTIVE_SECTION_V2 = '基础配置';
let CONFIG_ACTIVE_GROUP_V2 = '';
let CONFIG_NAV_QUERY_V2 = '';
const CONFIG_PENDING_UPDATES = {};

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
  CONFIG.forEach(f => { (groups[f.group || '其他'] = groups[f.group || '其他'] || []).push(f); });
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
  if (name === 'CloakBrowser') return '本地指纹浏览器';
  return name;
}
function configNavIcon(name) {
  const n = String(name || '');
  if (n.includes('网站') || n.includes('WebUI')) return '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>';
  if (n.includes('开关') || n.includes('功能')) return '<rect x="1" y="8" width="22" height="8" rx="4"/><circle cx="7" cy="12" r="2.8"/>';
  if (n === '本地指纹浏览器' || n.includes('Cloak')) return '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>';
  if (n.includes('邮箱') || n.includes('OTP')) return '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="M22 6l-10 7L2 6"/>';
  if (n.includes('接码') || n.includes('SMS')) return '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>';
  if (n.includes('Codex')) return '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>';
  if (n.includes('代理') || n.includes('Proxy')) return '<circle cx="12" cy="12" r="3"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/>';
  if (n.includes('画像') || n.includes('指纹')) return '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>';
  if (n.includes('人工') || n.includes('节奏')) return '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>';
  if (n.includes('提链')) return '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>';
  if (n.includes('Browser') || n.includes('Roxy') || n.includes('Skyvern') || n.includes('注册')) return '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>';
  return '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>';
}
function getConfigGroupNames() {
  const groups = {};
  (CONFIG || []).forEach(f => { groups[f.group || '其他'] = true; });
  return Object.keys(groups);
}
function configSectionIntro(name) {
  if (name === '网站配置') return '配置网站登录授权码与 Session 签名密钥。';
  if (name === '功能开关') return '';
  if (name === '注册方式') return '选择账号注册时使用的自动化方式。';
  if (name === 'CloakBrowser') return '本地指纹浏览器运行参数、语言时区与代理设置。';
  if (name === 'Browser Use') return 'Browser Use Cloud 远端浏览器与代理参数。';
  if (name === 'Skyvern') return 'Skyvern Browser Sessions 与代理参数。';
  if (name === 'RoxyBrowser') return 'RoxyBrowser API、环境与代理相关设置。';
  if (name === 'Codex') return 'Codex 授权驱动、CPA 与 sub2api 相关设置。';
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
    { value: 'cloak', label: '本地指纹浏览器' },
    { value: 'browser_use', label: 'browser_use' },
    { value: 'skyvern', label: 'skyvern' },
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
      注册方式
      <span class="hint">选择注册所用的自动化方式</span>
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
      <p class="config-switch-v2-help">${esc(f.help || '')}</p>
      ${opts.extraHtml || ''}
    </div>
  `;
}
function twofaDriverChoices() {
  return [
    { value: 'protocol', label: '协议直开（新鲜 AT）' },
    { value: 'browser', label: '浏览器页面（RoxyBrowser）' },
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
function renderConfigPlainFieldV2(f) {
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  let control = '';
  if (f.key === 'REGISTRATION_AUTH_MODE') {
    const options = [['otp','邮箱一次性验证码（推荐）'],['password','设置账号密码']];
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
    { value: 'cloak', label: '本地指纹浏览器' },
    { value: 'browser_use', label: 'browser_use' },
    { value: 'skyvern', label: 'skyvern' },
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
  if (name === '功能开关') {
    const preferred = ['ENABLE_CODEX_AUTO', 'ENABLE_2FA', 'ENABLE_FLOW_TRIGGER'];
    const ordered = preferred
      .map(k => fields.find(f => f.key === k))
      .filter(Boolean)
      .concat(fields.filter(f => !preferred.includes(f.key)));
    const twofaDriver = ordered.find(f => f.key === 'TWOFA_DRIVER');
    const switches = ordered.filter(f => f.type === 'bool');
    const otherFields = ordered.filter(f => f.type !== 'bool' && f.key !== 'TWOFA_DRIVER');
    return `
      <section class="config-section-v2" id="${esc(slug)}" data-config-section="${esc(name)}">
        ${renderConfigSectionHead(name, '')}
        <div class="config-switches-v2">
          ${switches.map(f => renderFeatureSwitchField(f, {
            withIcon: true,
            extraHtml: f.key === 'ENABLE_2FA' && twofaDriver ? renderTwofaDriverControl(twofaDriver) : '',
          })).join('')}
        </div>
        ${otherFields.length ? `<div class="config-section-v2-body">${otherFields.map(renderConfigPlainFieldV2).join('')}</div>` : ''}
        ${renderConfigSaveActions()}
      </section>
    `;
  }
  if (name === '注册方式') {
    const driver = fields.find(f => f.key === 'REGISTRATION_DRIVER');
    const otherFields = fields.filter(f => f.key !== 'REGISTRATION_DRIVER');
    return `
      <section class="config-section-v2" id="${esc(slug)}" data-config-section="${esc(name)}">
        ${renderConfigSectionHead(name, configSectionIntro(name))}
        <div class="config-section-v2-body${otherFields.length ? '' : ' config-section-v2-body--single'}">
          ${driver ? renderRegistrationDriverField(driver) : '<div class="banner warn">未找到注册方式配置项</div>'}
          ${otherFields.map(renderConfigPlainFieldV2).join('')}
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
  if (!names.length) {
    nav.innerHTML = '<div class="muted" style="padding:8px 12px;font-size:13px;">暂无分组</div>';
    sections.innerHTML = '';
    const count = document.getElementById('configNavCountV2');
    if (count) count.textContent = '0';
    updateConfigSaveUi();
    return;
  }
  const savedGroup = localStorage.getItem('gpt_console_config_group');
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
  setPendingConfigValue(f.key, readConfigElementValue(el, f));
  renderConfigOverviewCards();
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
