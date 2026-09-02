// ---------- 配置 ----------
let CONFIG_ACTIVE_GROUP = '';
let CONFIG_EMAIL_ACTIVE_SECTION = '通用邮箱 / OTP';
let CONFIG_SMS_ACTIVE_SECTION = '通用接码';
let CONFIG_CODEX_ACTIVE_SECTION = '基础配置';
const CONFIG_PENDING_UPDATES = {};

function configGroups() {
  const groups = {};
  CONFIG.forEach(f => { (groups[f.group || '其他'] = groups[f.group || '其他'] || []).push(f); });
  return groups;
}

function configDriverChoices(f) {
  if (f.key === 'REGISTRATION_DRIVER') return [['protocol', '纯协议注册'], ['roxy', 'RoxyBrowser']];
  if (f.key === 'REGISTRATION_AUTH_MODE') return [['otp', '不设置密码（邮箱验证码）'], ['password', '设置账号密码']];
  if (f.key === 'ACCOUNT_PASSWORD_DRIVER') return [['roxy', 'RoxyBrowser（当前唯一实现）']];
  if (f.key === 'ACCOUNT_PLAN_CHECK_DRIVER') return [['protocol', '纯协议（当前唯一实现）']];
  if (f.key === 'ACCOUNT_LIVE_CHECK_DRIVER') return [
    ['protocol_current', '现有协议（保持现状）'],
    ['browser_roxy', 'Roxy 浏览器（需先开放灰度）'],
  ];
  if (f.key === 'ACCOUNT_TOKEN_REFRESH_DRIVER') return [
    ['legacy', '现有刷新链路（保持现状）'],
    ['protocol_v2', 'Protocol v2 密码/MFA（需开启总开关）'],
  ];
  if (f.key === 'ACCOUNT_AUTH_PROFILE_MODE') return [
    ['current', '当前会话画像（保持现状）'],
    ['account_stable', '账号稳定 Protocol 画像（懒创建）'],
  ];
  if (f.key === 'ACCOUNT_2FA_DRIVER' || f.key === 'TWOFA_DRIVER') {
    return [['protocol', '协议直开（新鲜 AT）'], ['browser', '浏览器页面（RoxyBrowser）']];
  }
  if (f.key === 'ACCOUNT_CODEX_DRIVER' || f.key === 'CODEX_OAUTH_DRIVER') {
    return [['protocol', '纯协议授权'], ['roxy', 'RoxyBrowser'], ['same_as_registration', '跟随注册驱动']];
  }
  return null;
}

function renderConfigField(f) {
  const fv = Object.prototype.hasOwnProperty.call(CONFIG_PENDING_UPDATES, f.key) ? CONFIG_PENDING_UPDATES[f.key] : f.value;
  let html = `<label class="fld">${esc(f.label)}<span class="hint">${esc(f.help)} · <span class="mono">${esc(f.key)}</span></span>`;
  const driverChoices = configDriverChoices(f);
  if (driverChoices) {
    const current = String(fv == null ? '' : fv).trim().toLowerCase();
    const options = driverChoices.slice();
    if (current && !options.some(([value]) => value === current)) options.unshift([current, `当前配置（${current}）`]);
    const disabled = options.length === 1 ? ' disabled' : '';
    html += `<select data-key="${attrEsc(f.key)}"${disabled}>${options.map(([value, label]) => `<option value="${attrEsc(value)}"${current === value ? ' selected' : ''}>${esc(label)}</option>`).join('')}</select>`;
  } else if (f.key === 'REGISTRATION_PROXY_MODE') {
    const options = [['pool','静态代理池'],['1024','1024Proxy 平台 API'],['none','直连']];
    html += `<select data-key="${attrEsc(f.key)}">${options.map(([v,l]) => `<option value="${v}"${String(fv)===v?' selected':''}>${l} (${v})</option>`).join('')}</select>`;
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
    html += `<select data-key="${attrEsc(f.key)}">${regions.map(([v,l]) => `<option value="${attrEsc(v)}"${current===v?' selected':''}>${esc(l)}${v ? ` (${esc(v)})` : ''}</option>`).join('')}</select>`;
  } else if (f.key === 'PROXY_1024_PROTOCOL') {
    html += `<select data-key="${attrEsc(f.key)}">${['http','https','socks5','socks5h'].map(v => `<option value="${v}"${String(fv)===v?' selected':''}>${v}</option>`).join('')}</select>`;
  } else if (f.type === 'bool') {
    html += `<select data-key="${attrEsc(f.key)}"><option value="true"${fv?' selected':''}>开启 (True)</option><option value="false"${!fv?' selected':''}>关闭 (False)</option></select>`;
  } else if (f.type === 'int') {
    html += `<input type="number" data-key="${attrEsc(f.key)}" value="${attrEsc(fv == null ? '' : fv)}">`;
  } else if (f.type === 'float') {
    html += `<input type="number" step="0.1" data-key="${attrEsc(f.key)}" value="${attrEsc(fv == null ? '' : fv)}">`;
  } else if (f.type === 'list_str_multiline') {
    html += `<textarea data-key="${attrEsc(f.key)}" placeholder="每行一条，可留空">${attrEsc((fv||[]).join('\n'))}</textarea>`;
  } else {
    // 空字符串/占位符 '-' 都显示为空输入框，避免误保存成真实值
    const shown = isPlaceholderEmpty(fv) ? '' : fv;
    const inputType = f.secret ? 'password' : 'text';
    const ph = f.secret ? '保存在 .env，可留空' : '可留空';
    html += `<input type="${inputType}" data-key="${attrEsc(f.key)}" value="${attrEsc(shown)}" placeholder="${ph}" autocomplete="off" spellcheck="false">`;
  }
  return html + `</label>`;
}

function configSubhead(title, help = '') {
  return `<div class="config-subhead">${esc(title)}${help ? `<span class="hint">${esc(help)}</span>` : ''}</div>`;
}

function emailConfigSectionForKey(key) {
  if (['USE_EMAIL_SERVICE','REGISTER_EMAIL','REGISTER_NAME','OTP_MAX_WAIT','OTP_POLL_INTERVAL','EMAIL_SOURCE'].includes(key)) {
    return ['通用邮箱 / OTP', '邮箱来源选择、OTP 等待参数、手动邮箱等通用设置'];
  }
  if (key.startsWith('GPTMAIL_')) return ['GPTMail', 'GPTMail 临时邮箱 API 配置'];
  if (key.startsWith('MAIL_NEST_')) return ['MailNest', 'MailNest / 迈巢临时邮箱 API 配置'];
  if (key.startsWith('CLOUDMAIL_')) return ['CloudMail', 'CloudMail 域名随机邮箱、Token 和收信 API 配置'];
  if (key.startsWith('ICLOUD_HME_')) return ['iCloud 隐藏邮箱', '连接本机 iCloud HME 服务、同步 Hide My Email 别名并按实际转发目标自动收码'];
  if (key.startsWith('OUTLOOK_')) return ['Outlook 邮箱池', 'Outlook 邮箱池和取件模式配置'];
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
  if (key.startsWith('CPA_')) {
    return ['CPA配置', 'CPA 授权链接生成、回调上传和管理接口配置'];
  }
  if (['SUB2API_API_BASE','SUB2API_API_KEY','SUB2API_API_TIMEOUT'].includes(key)) {
    return ['sub2api', 'sub2api 的 API 基址、鉴权和超时配置；用于 Codex OAuth 授权和凭证上传'];
  }
  return ['基础配置', ''];
}

function renderSectionedConfigFields(fields, activeSectionName, setActiveSection, sectionForKey, preferred, dataAttr) {
  const bySection = {};
  for (const f of fields) {
    const [section, help] = sectionForKey(f.key || '');
    if (!bySection[section]) bySection[section] = {help, fields: []};
    bySection[section].fields.push(f);
  }
  const sections = preferred.filter(x => bySection[x]).concat(Object.keys(bySection).filter(x => !preferred.includes(x)));
  if (!sections.includes(activeSectionName)) {
    activeSectionName = sections[0] || '';
    setActiveSection(activeSectionName);
  }
  let html = `
    <div class="config-subtabs">
      ${sections.map(section => `
        <button type="button" data-${dataAttr}="${esc(section)}" class="${section === activeSectionName ? 'active' : ''}">
          ${esc(section)} <span class="config-count">${bySection[section].fields.length}</span>
        </button>
      `).join('')}
    </div>
  `;
  const current = bySection[activeSectionName];
  if (!current) return html;
  html += configSubhead(activeSectionName, current.help);
  for (const f of current.fields) {
    html += renderConfigField(f);
    if (f.key === 'CLOUDMAIL_AUTH_TOKEN') html += renderCloudMailTokenTools();
    if (f.key === 'ICLOUD_HME_CREATE_LABEL_PREFIX') html += renderICloudHMETools();
  }
  return html;
}

function renderConfigFields(fields) {
  if (CONFIG_ACTIVE_GROUP === '邮箱 / OTP') {
    return renderSectionedConfigFields(
      fields,
      CONFIG_EMAIL_ACTIVE_SECTION,
      v => { CONFIG_EMAIL_ACTIVE_SECTION = v; },
      emailConfigSectionForKey,
      ['通用邮箱 / OTP', 'iCloud 隐藏邮箱', 'GPTMail', 'MailNest', 'CloudMail', 'Outlook 邮箱池', 'Cloudflare 临时邮箱', 'Cloudflare 域名邮箱', '其他邮箱配置'],
      'email-config-section'
    );
  }
  if (CONFIG_ACTIVE_GROUP === '接码平台') {
    return renderSectionedConfigFields(
      fields,
      CONFIG_SMS_ACTIVE_SECTION,
      v => { CONFIG_SMS_ACTIVE_SECTION = v; },
      smsConfigSectionForKey,
      ['通用接码', 'GrizzlySMS', 'H 接码', 'L 接码', '其他接码配置'],
      'sms-config-section'
    );
  }
  if (CONFIG_ACTIVE_GROUP === 'Codex') {
    return renderSectionedConfigFields(
      fields,
      CONFIG_CODEX_ACTIVE_SECTION,
      v => { CONFIG_CODEX_ACTIVE_SECTION = v; },
      codexConfigSectionForKey,
      ['基础配置', 'CPA配置', 'sub2api'],
      'codex-config-section'
    );
  }
  return fields.map(renderConfigField).join('');
}

function renderConfigTabs() {
  const groups = configGroups();
  const names = Object.keys(groups);
  if (!CONFIG_ACTIVE_GROUP || !groups[CONFIG_ACTIVE_GROUP]) CONFIG_ACTIVE_GROUP = names[0] || '';
  $('#configTabs').innerHTML = names.map(name => `
    <button type="button" data-config-group="${esc(name)}" class="${name === CONFIG_ACTIVE_GROUP ? 'active' : ''}">
      ${esc(name)} <span class="config-count">${groups[name].length}</span>
    </button>
  `).join('');
}

function renderRoxyWorkspaceTools() {
  if (CONFIG_ACTIVE_GROUP !== 'RoxyBrowser') return '';
  const current = (CONFIG.find(f => f.key === 'ROXY_WORKSPACE_ID') || {}).value || '';
  return `
    <div class="roxy-workspace-box">
      <div>
        <b>团队 / 项目选择</b>
        <div class="hint">点击“获取团队”调用 Roxy <span class="mono">/browser/workspace</span>，选择后保存 <span class="mono">ROXY_WORKSPACE_ID</span> 和 <span class="mono">ROXY_PROJECT_ID</span>。</div>
        <a class="roxy-invite-link" href="https://roxybrowser.cn/invite/NvH4Jx" target="_blank" rel="noopener noreferrer">打开 RoxyBrowser 官网（免费 5 个窗口）</a>
      </div>
      <div class="row">
        <div>
          <label class="fld">团队 / 项目
            <select id="roxyWorkspaceSelect"><option value="">当前团队：${esc(current || '未设置')}</option></select>
          </label>
        </div>
        <div class="action-cell">
          <button class="btn" type="button" id="btnLoadRoxyWorkspaces">获取团队</button>
          <button class="btn primary" type="button" id="btnSaveRoxyWorkspace" disabled>保存选择</button>
        </div>
      </div>
      <div id="roxyWorkspaceStatus" class="muted" style="font-size:12px;">未加载</div>
    </div>
  `;
}

function renderCloudMailTokenTools() {
  if (CONFIG_ACTIVE_GROUP !== '邮箱 / OTP') return '';
  const hasCloudMail = CONFIG.some(f => String(f.key || '').startsWith('CLOUDMAIL_'));
  if (!hasCloudMail) return '';
  return `
    <div class="roxy-workspace-box">
      <div>
        <b>CloudMail Token</b>
        <div class="hint">确认本区的 <span class="mono">CLOUDMAIL_API_BASE</span>、管理员邮箱、密码已填写后，点击按钮调用 <span class="mono">/api/public/genToken</span> 生成 Token。保存配置本身不会自动生成 Token。</div>
      </div>
      <div class="action-cell">
        <button class="btn primary" type="button" id="btnGenCloudMailToken">生成 CloudMail Token</button>
        <button class="btn" type="button" id="btnLoadCloudMailDomains">获取 CloudMail 域名</button>
      </div>
      <div id="cloudMailTokenStatus" class="muted" style="font-size:12px;">未生成</div>
    </div>
  `;
}

function renderICloudHMETools() {
  if (CONFIG_ACTIVE_GROUP !== '邮箱 / OTP') return '';
  return `
    <div class="roxy-workspace-box">
      <div>
        <b>iCloud Hide My Email</b>
        <div class="hint">连接本机服务、同步隐藏邮箱库存，并确认 sidecar 或 Email Butler PG 收件链路。Apple 凭据不会保存到 turb。</div>
      </div>
      <div class="action-cell">
        <button class="btn primary" type="button" id="btnTestICloudHME">连接并同步</button>
      </div>
      <div id="icloudHMEStatus" class="muted" style="font-size:12px;">尚未检测</div>
    </div>
  `;
}

async function testICloudHME() {
  const btn = $('#btnTestICloudHME');
  const status = $('#icloudHMEStatus');
  if (!btn || !status) return;
  btn.disabled = true;
  status.textContent = '正在连接、同步别名并检测实际收件通道...';
  try {
    const r = await api('/api/icloud-hme/test', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        api_base: _configValue('ICLOUD_HME_API_BASE').trim(),
        account_id: _configValue('ICLOUD_HME_ACCOUNT_ID').trim(),
        timeout: Number(_configValue('ICLOUD_HME_REQUEST_TIMEOUT')) || 35,
      }),
    });
    status.innerHTML = `✅ ${esc(r.message || 'iCloud HME 连接成功')}`;
    showToast(`已同步 ${Number(r.remote_aliases || 0)} 个 iCloud 隐藏邮箱`);
    await loadOutlook();
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">检测失败：${esc(e.message)}</span>`;
  } finally {
    btn.disabled = false;
  }
}

function _configValue(key) {
  const el = $(`#tab-config [data-key="${CSS.escape(key)}"]`);
  if (el) return el.value;
  const f = CONFIG.find(x => x.key === key);
  return f ? (f.value || '') : '';
}

async function genCloudMailToken() {
  const btn = $('#btnGenCloudMailToken');
  const status = $('#cloudMailTokenStatus');
  if (!btn || !status) return;
  btn.disabled = true;
  status.textContent = '正在调用 CloudMail /api/public/genToken...';
  try {
    const r = await api('/api/cloudmail/gen-token', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        api_base: _configValue('CLOUDMAIL_API_BASE').trim(),
        admin_email: _configValue('CLOUDMAIL_ADMIN_EMAIL').trim(),
        password: _configValue('CLOUDMAIL_PASSWORD').trim(),
        path: _configValue('CLOUDMAIL_TOKEN_PATH').trim() || '/api/public/genToken',
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

async function loadCloudMailDomains() {
  const btn = $('#btnLoadCloudMailDomains');
  const status = $('#cloudMailTokenStatus');
  if (!btn || !status) return;
  btn.disabled = true;
  status.textContent = '正在从 CloudMail 平台获取可用域名...';
  try {
    const r = await api('/api/cloudmail/domains', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        api_base: _configValue('CLOUDMAIL_API_BASE').trim(),
        admin_email: _configValue('CLOUDMAIL_ADMIN_EMAIL').trim(),
        password: _configValue('CLOUDMAIL_PASSWORD').trim(),
        token: _configValue('CLOUDMAIL_AUTH_TOKEN').trim(),
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

function bindRoxyWorkspaceTools() {
  const cloudBtn = $('#btnGenCloudMailToken');
  if (cloudBtn) cloudBtn.addEventListener('click', genCloudMailToken);
  const cloudDomainBtn = $('#btnLoadCloudMailDomains');
  if (cloudDomainBtn) cloudDomainBtn.addEventListener('click', loadCloudMailDomains);
  const icloudBtn = $('#btnTestICloudHME');
  if (icloudBtn) icloudBtn.addEventListener('click', testICloudHME);

  const loadBtn = $('#btnLoadRoxyWorkspaces');
  const saveBtn = $('#btnSaveRoxyWorkspace');
  const sel = $('#roxyWorkspaceSelect');
  if (!loadBtn || !saveBtn || !sel) return;
  sel.addEventListener('change', () => { saveBtn.disabled = !sel.value; });
  loadBtn.addEventListener('click', loadRoxyWorkspaces);
  saveBtn.addEventListener('click', saveRoxyWorkspaceSelection);
}

function renderConfigPanel() {
  const groups = configGroups();
  const fields = groups[CONFIG_ACTIVE_GROUP] || [];
  if (!fields.length) {
    $('#configForm').innerHTML = '<div class="banner warn">暂无配置项</div>';
    return;
  }
  $('#configForm').innerHTML = `
    <div class="config-panel">
      <h3>${esc(CONFIG_ACTIVE_GROUP)}</h3>
      ${renderRoxyWorkspaceTools()}
      ${renderConfigFields(fields)}
    </div>
  `;
  bindRoxyWorkspaceTools();
}

async function loadConfig() {
  try {
    CONFIG = await api('/api/config');
    renderConfigTabs();
    renderConfigPanel();
  } catch(e) {
    $('#configTabs').innerHTML = '';
    $('#configForm').innerHTML = `<div class="banner warn">${esc(e.message)}</div>`;
  }
}

$('#configTabs').addEventListener('click', (e) => {
  const btn = e.target.closest('[data-config-group]');
  if (!btn) return;
  CONFIG_ACTIVE_GROUP = btn.dataset.configGroup;
  renderConfigTabs();
  renderConfigPanel();
});

$('#configForm').addEventListener('click', (e) => {
  const emailBtn = e.target.closest('[data-email-config-section]');
  if (emailBtn) {
    CONFIG_EMAIL_ACTIVE_SECTION = emailBtn.dataset.emailConfigSection;
    renderConfigPanel();
    return;
  }
  const smsBtn = e.target.closest('[data-sms-config-section]');
  if (smsBtn) {
    CONFIG_SMS_ACTIVE_SECTION = smsBtn.dataset.smsConfigSection;
    renderConfigPanel();
    return;
  }
  const codexBtn = e.target.closest('[data-codex-config-section]');
  if (codexBtn) {
    CONFIG_CODEX_ACTIVE_SECTION = codexBtn.dataset.codexConfigSection;
    renderConfigPanel();
    return;
  }
});

async function loadRoxyWorkspaces() {
  const status = $('#roxyWorkspaceStatus');
  const sel = $('#roxyWorkspaceSelect');
  const saveBtn = $('#btnSaveRoxyWorkspace');
  const loadBtn = $('#btnLoadRoxyWorkspaces');
  if (!status || !sel) return;
  loadBtn.disabled = true;
  saveBtn.disabled = true;
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
    sel.innerHTML = `<option value="">请选择团队/项目（当前团队：${esc(current || '未设置')}，项目：${esc(currentProject || '未设置')}）</option>` +
      items.map(x => {
        const value = `${x.id}::${x.projectId || ''}`;
        const selected = String(x.id)===String(current) && String(x.projectId || '')===String(currentProject);
        return `<option value="${esc(value)}" data-workspace-id="${esc(x.id)}" data-project-id="${esc(x.projectId || '')}"${selected?' selected':''}>${esc(x.label || (x.name + ' (' + x.id + ')'))}</option>`;
      }).join('');
    saveBtn.disabled = !sel.value;
    status.innerHTML = `已获取 ${items.length} 个团队/项目，接口：<span class="mono">${esc(r.method || '')} ${esc(r.path || '')}</span>`;
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">获取失败：${esc(e.message)}</span>`;
  } finally {
    loadBtn.disabled = false;
  }
}

async function saveRoxyWorkspaceSelection() {
  const sel = $('#roxyWorkspaceSelect');
  const status = $('#roxyWorkspaceStatus');
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
    status.innerHTML = `✅ 已保存团队 ID：<span class="mono">${esc(workspaceId)}</span>，项目 ID：<span class="mono">${esc(projectId || '未设置')}</span>`;
    showToast(r.reloaded ? 'Roxy 团队/项目已保存并生效' : 'Roxy 团队/项目已保存');
    renderConfigPanel();
  } catch(e) {
    status.innerHTML = `<span style="color:var(--red);">保存失败：${esc(e.message)}</span>`;
  }
}
function readConfigElementValue(el, f) {
  if (!f) return undefined;
  if (f.type === 'list_str_multiline') return el.value.split('\n').map(s=>s.trim()).filter(Boolean);
  if (f.type === 'bool') return el.value === 'true';
  if (f.type === 'int') return parseInt(el.value || '0', 10);
  if (f.type === 'float') return parseFloat(el.value || '0');
  return isPlaceholderEmpty(el.value) ? '' : el.value.trim();
}

$('#configForm').addEventListener('input', (e) => {
  const el = e.target.closest('[data-key]');
  if (!el) return;
  const f = CONFIG.find(x => x.key === el.dataset.key);
  if (!f) return;
  CONFIG_PENDING_UPDATES[f.key] = readConfigElementValue(el, f);
});
$('#configForm').addEventListener('change', (e) => {
  const el = e.target.closest('[data-key]');
  if (!el) return;
  const f = CONFIG.find(x => x.key === el.dataset.key);
  if (!f) return;
  CONFIG_PENDING_UPDATES[f.key] = readConfigElementValue(el, f);
});

$('#btnSaveConfig').addEventListener('click', async () => {
  const updates = {...CONFIG_PENDING_UPDATES};
  $$('#tab-config [data-key]').forEach(el => {
    const f = CONFIG.find(x => x.key === el.dataset.key);
    if (!f) return;
    updates[f.key] = readConfigElementValue(el, f);
  });
  $('#btnSaveConfig').disabled = true;
  try {
    const r = await api('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({updates}) });
    if (r.reloaded) {
      $('#configBanner').className = 'banner info';
      $('#configBanner').innerHTML = `✅ 已保存 ${r.updated.length} 项，并完成热加载，<b>立即生效</b>，无需重启。${r.note ? `<br>${esc(r.note)}` : ''}`;
    } else {
      $('#configBanner').className = 'banner warn';
      $('#configBanner').innerHTML = `已保存 ${r.updated.length} 项，但<b>热加载失败</b>（${esc(r.note||'')}），请重启 Web 服务后生效。`;
    }
    for (const [k, v] of Object.entries(updates)) { const f = CONFIG.find(x => x.key === k); if (f) f.value = v; delete CONFIG_PENDING_UPDATES[k]; }
    await loadCapabilities();
    await loadRegistrationEmailSources();
    showToast(r.reloaded ? '配置已生效' : '配置已保存（需重启）');
  } catch(e) { showToast('保存失败: ' + e.message); }
  finally { $('#btnSaveConfig').disabled = false; }
});
