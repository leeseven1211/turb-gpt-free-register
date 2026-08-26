const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
let copySeq = 0;
const copyStore = new Map();
let ACCOUNTS = [], OUTLOOK = [], CONFIG = [];
let ACCOUNTS_TOTAL = 0;
let OUTLOOK_TOTAL = 0;
let SHOW_ARCHIVED_ACCOUNTS = false;
let SHOW_PLUS_ACCOUNTS_ONLY = false;
const ACCOUNT_SELECTED = new Set();
const OUTLOOK_SELECTED = new Set();
let JOBS = [];
let JOBS_TOTAL = 0;
let JOB_STATUS_COUNTS = {};
let REGISTRATION_EMAIL_SOURCES = [];
let jobsRenderSignature = '';
const JOB_SELECTED = new Set();
let activeLogJob = null, logTimer = null, jobsTimer = null;
let summaryLoading = false;
let jobsLoading = false;

// ---------- 分页状态 ----------
const PAGERS = {
  jobs:     { page: 1, size: 20 },
  accounts: { page: 1, size: 20 },
  outlook:  { page: 1, size: 20 },
  codex:    { page: 1, size: 20 },
};

function _renderPager(id, total) {
  const p = PAGERS[id];
  const totalPages = Math.max(1, Math.ceil(total / p.size));
  if (p.page > totalPages) p.page = Math.max(1, totalPages);
  const start = total > 0 ? (p.page - 1) * p.size + 1 : 0;
  const end = Math.min(p.page * p.size, total);
  const el = document.getElementById('pager-' + id);
  if (!el) return;
  const sizes = [20, 50, 100];
  el.innerHTML = `
    <button onclick="pagerGo('${id}',-1)"${p.page <= 1 ? ' disabled' : ''}>← 上一页</button>
    <span class="pager-info">${total > 0 ? `第 ${start}–${end} 条 / 共 ${total} 条（第 ${p.page} / ${totalPages} 页）` : '无数据'}</span>
    <button onclick="pagerGo('${id}',1)"${p.page >= totalPages ? ' disabled' : ''}>下一页 →</button>
    <select onchange="pagerSetSize('${id}',this.value)">${sizes.map(s =>
      `<option value="${s}"${p.size === s ? ' selected' : ''}>${s} 条/页</option>`
    ).join('')}</select>`;
}

function _reloadPagedList(id) {
  ({ jobs: refreshJobs, accounts: loadAccounts, outlook: loadOutlook, codex: loadCodex })[id]?.();
}
function pagerGo(id, dir) {
  PAGERS[id].page = Math.max(1, PAGERS[id].page + dir);
  _reloadPagedList(id);
}
function pagerSetSize(id, val) {
  PAGERS[id].size = parseInt(val, 10) || 20;
  PAGERS[id].page = 1;
  _reloadPagedList(id);
}

// ---------- 工具 ----------
function fmt(v) { return v == null || v === '' ? '-' : String(v); }
function esc(v) { return fmt(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
// 配置表单必须用这个：空值保持空，不能把 '' 显示成 '-'，否则一点保存就会写回 config
function attrEsc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function isPlaceholderEmpty(v) {
  const s = String(v == null ? '' : v).trim();
  return !s || ['-', '—', '无', '空', 'none', 'null', 'n/a', 'na'].includes(s.toLowerCase());
}
function short(v, n=40) { const s = v || ''; return s.length > n ? s.slice(0,n)+'…' : s; }
function copyId(v) { if (!v) return ''; const id = 'c'+(++copySeq); copyStore.set(id, v); return id; }
function cbtn(label, value, cls='') { const id = copyId(value); return `<button class="${cls}" data-copy-id="${id}" ${id?'':'disabled'}>${label}</button>`; }
function pill(status) {
  const map = { available:'可用', used:'已用', failed:'失败', partial_success:'部分成功', disabled:'已停用', pending:'排队', running:'运行中', stopping:'停止中', stopped:'已停止', success:'成功', cancelled:'已取消' };
  return `<span class="pill status-${esc(status)}">${esc(map[status]||status||'-')}</span>`;
}
function showToast(t) { const el=$('#toast'); el.textContent=t; el.classList.add('show'); clearTimeout(showToast.t); showToast.t=setTimeout(()=>el.classList.remove('show'),1400); }
async function copyText(text) {
  if (!text) return;
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else { const a=document.createElement('textarea'); a.value=text; a.style.position='fixed'; a.style.opacity='0'; document.body.appendChild(a); a.select(); document.execCommand('copy'); a.remove(); }
    showToast('已复制');
  } catch(e) { showToast('复制失败'); }
}
async function api(url, opts) {
  const r = await fetch(url, opts);
  const j = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(j.error || ('HTTP '+r.status));
  return j;
}
let CAPABILITIES = {features:{}, email_sources:{}};
const FEATURE_SELECTORS = {
  register: '#btnStartV2,#btnStart',
  live_check: '#btnCheckSelectedLiveTopV2,#btnCheckSelectedLiveV2,#btnRefreshSelectedTokenV2,#btnRefreshSelectedTokenTopV2,#btnCheckSelectedLiveTop,#btnRefreshSelectedTokenTop,#btnCheckSelectedLive,#btnRefreshSelectedToken,[data-account-live-check],[data-account-token-refresh]',
  plan_check: '#btnCheckSelectedPlansV2,#btnCheckSelectedPlans,[data-plan-check]',
  extract_link: '#btnExtractSelectedLinksV2,#btnExtractSelectedLinks,[data-extract-link]',
  sub2_upload: '#btnUploadSelectedCodexSub2V2,#btnUploadSelectedCodexSub2',
  codex_retry: '#btnRetrySelectedCodexV2,#btnRetrySelectedCodex,[data-codex-retry]',
  cpa_download: '#btnDownloadSelectedCpaV2,#btnDownloadSelectedCpa,#btnCodexDownloadBulkCpaV2,#btnCodexDownloadBulkCpa,[data-codex-download-cpa]',
  deactivation_mail: '#btnCheckSelectedDeactivationMailV2,#btnCheckSelectedDeactivationMail,[data-account-deactivation-mail]',
  proxy_provider_test: '#btnTestProxy1024V2,#btnTestProxy1024',
  roxy_workspaces: '#btnLoadRoxyWorkspacesV2,#btnLoadRoxyWorkspaces',
  cloudmail_token: '#btnGenCloudMailTokenV2,#btnGenCloudMailToken',
  cloudmail_domains: '#btnLoadCloudMailDomainsV2,#btnLoadCloudMailDomains',
  icloud_hme: '#btnTestICloudHMEV2,#btnTestICloudHME',
  email_butler_test: '#btnTestEmailButlerV2,#btnTestEmailButler',
};
function applyFeatureGates(root=document) {
  for (const [feature, selector] of Object.entries(FEATURE_SELECTORS)) {
    const item = (CAPABILITIES.features || {})[feature];
    if (!item) continue;
    root.querySelectorAll(selector).forEach(btn => {
      if (!btn.dataset.featureBaseTitle) btn.dataset.featureBaseTitle = btn.title || '';
      btn.dataset.feature = feature;
      btn.classList.toggle('feature-unavailable', !item.enabled);
      btn.setAttribute('aria-disabled', item.enabled ? 'false' : 'true');
      btn.title = item.enabled ? btn.dataset.featureBaseTitle : `不可用：${item.reason || '缺少必要配置'}`;
    });
  }
}
async function loadCapabilities() {
  try {
    CAPABILITIES = await api('/api/capabilities');
    applyFeatureGates();
  } catch (_) {}
}
document.addEventListener('click', (event) => {
  const blocked = event.target.closest('button.feature-unavailable');
  if (!blocked) return;
  event.preventDefault(); event.stopImmediatePropagation();
  const item = (CAPABILITIES.features || {})[blocked.dataset.feature] || {};
  showToast(item.reason || '功能缺少必要配置');
}, true);
new MutationObserver(() => applyFeatureGates()).observe(document.body, {childList:true, subtree:true});
function debounce(fn, wait=250) {
  let t = null;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

// ---------- Tab 切换 ----------
function activateTab(tab, persist=true) {
  const allowed = ['register','accounts','codex','outlook','config'];
  if (!allowed.includes(tab)) tab = 'register';
  $$('nav button').forEach(x => x.classList.toggle('active', x.dataset.tab === tab));
  allowed.forEach(t => $('#tab-'+t).classList.toggle('hidden', t !== tab));
  if (persist) localStorage.setItem('gpt_console_active_tab', tab);
  if (tab === 'accounts') loadAccounts();
  if (tab === 'codex') loadCodex();
  if (tab === 'outlook') loadOutlook();
  if (tab === 'config') loadConfig();
  if (tab === 'register') refreshJobs();
}
$$('nav button').forEach(b => b.addEventListener('click', () => activateTab(b.dataset.tab)));
