// ---------- 概览 ----------
async function loadSummary() {
  if (summaryLoading) return;
  summaryLoading = true;
  try {
    const s = await api('/api/summary');
    $('#statAccounts').textContent = s.accounts;
    $('#statOutlook').textContent = s.outlook_total;
    $('#statAvailable').textContent = s.outlook_available;
    $('#statUsed').textContent = s.outlook_used;
    $('#statFailed').textContent = s.outlook_failed;
  } catch(e) {}
  finally { summaryLoading = false; }
}

function dashboardMetric(label, value, hint, color) {
  return `<article class="overview-metric" style="--metric-color:${attrEsc(color)}">
    <div class="overview-metric-top"><span>${esc(label)}</span><i class="overview-metric-dot" aria-hidden="true"></i></div>
    <strong>${esc(value)}</strong><small>${esc(hint)}</small>
  </article>`;
}
function jobStatusLabel(status) {
  return ({pending:'排队',running:'运行中',success:'成功',failed:'失败',partial_success:'部分成功',stopped:'已停止',cancelled:'已取消'})[status] || status || '未知';
}
function renderDashboard(data) {
  const accounts = data.accounts || {};
  const email = data.email || {};
  const jobs = data.jobs || {};
  const proxy = data.proxy || {};
  const codex = data.codex || {};
  const jobCounts = jobs.counts || {};
  const activeJobs = Number(jobCounts.running || 0) + Number(jobCounts.pending || 0) + Number(jobCounts.stopping || 0);
  $('#overviewMetrics').innerHTML = [
    dashboardMetric('有效账号', accounts.active || 0, `归档 ${accounts.archived || 0}`, '#5b5ce2'),
    dashboardMetric('可用邮箱', email.local_available || 0, `本地资源 ${email.local_total || 0}`, '#2dbb8a'),
    dashboardMetric('运行任务', activeJobs, `累计任务 ${jobs.total || 0}`, '#e6a23c'),
    dashboardMetric('Codex 凭证', codex.total || 0, `待导出 ${codex.pending || 0}`, '#377dff'),
    dashboardMetric('活跃出口', proxy.active_leases || 0, `代理平台 ${proxy.platform || 'none'}`, '#a855f7'),
  ].join('');

  const sources = email.sources || [];
  $('#overviewEmailSources').innerHTML = sources.map(source => {
    const onDemand = source.kind === 'on_demand';
    return `<article class="overview-source">
      <div class="overview-source-top"><span class="overview-source-name" title="${attrEsc(source.label)}">${esc(source.label)}</span><i class="overview-source-state${source.enabled ? ' is-on' : ''}"></i></div>
      <strong>${onDemand ? (source.enabled ? '按需' : '未启用') : esc(source.available || 0)}</strong>
      <small>${onDemand ? '运行时租用' : `总数 ${esc(source.total || 0)} · 已用 ${esc(source.used || 0)}`}</small>
    </article>`;
  }).join('') || '<div class="muted">暂无邮箱来源</div>';

  const proxyPlatformLabel = ({'1024':'1024Proxy',pool:'静态代理池',none:'直连',direct:'直连'})[proxy.platform] || proxy.platform || '未配置';
  const leases = proxy.leases || [];
  $('#overviewProxy').innerHTML = `<div class="overview-proxy-grid">
    <div class="overview-proxy-item"><span>系统代理平台</span><strong>${esc(proxyPlatformLabel)}</strong></div>
    <div class="overview-proxy-item"><span>活跃出口</span><strong>${esc(proxy.active_leases || 0)} 个</strong></div>
  </div><div class="overview-exit-list">${leases.map(lease => `<div class="overview-exit-row">
    <i aria-hidden="true"></i><span title="${attrEsc(lease.endpoint || lease.exit_ip || '')}">${esc(lease.endpoint || lease.exit_ip || '活跃出口')}</span><small>${esc(lease.region || lease.provider || '')}</small>
  </div>`).join('') || '<div class="muted">当前没有活跃代理出口</div>'}</div>`;

  const todayCounts = jobs.today_counts || {};
  const todayRows = [
    ['success', '成功', todayCounts.success || 0],
    ['partial_success', '部分成功', todayCounts.partial_success || 0],
    ['failed', '失败', todayCounts.failed || 0],
  ];
  $('#overviewRecentJobs').innerHTML = todayRows.map(([status, label, count]) => `<div class="overview-job-row">
    ${pill(status)}<div class="overview-job-main"><strong>${esc(count)} 个任务</strong><small>${esc(jobs.today || '今天')} · ${esc(label)}</small></div>
  </div>`).join('');

  const plans = Object.entries(accounts.plans || {}).sort((a,b) => Number(b[1]) - Number(a[1]));
  const planMax = Math.max(1, ...plans.map(([,count]) => Number(count || 0)));
  const planLabels = {free:'Free',free_trial_eligible:'Free · 可领 Plus 试用',plus:'Plus',pro:'Pro',team:'Team',go:'Go',unknown:'未检测'};
  $('#overviewPlans').innerHTML = plans.map(([plan,count]) => `<div class="overview-plan-row">
    <span>${esc(planLabels[plan] || plan)}</span><div class="overview-plan-bar"><i style="width:${Math.max(4, Math.round(Number(count || 0) / planMax * 100))}%"></i></div><strong>${esc(count)}</strong>
  </div>`).join('') || '<div class="muted">暂无套餐信息</div>';
}
async function loadDashboard() {
  if (dashboardLoading) return;
  dashboardLoading = true;
  const button = $('#btnRefreshOverview');
  if (button) button.disabled = true;
  try { renderDashboard(await api('/api/dashboard')); }
  catch(e) { showToast('总览加载失败: ' + e.message); }
  finally {
    dashboardLoading = false;
    if (button) button.disabled = false;
  }
}
$('#btnRefreshOverview')?.addEventListener('click', loadDashboard);
$('#tab-overview')?.addEventListener('click', e => {
  const go = e.target.closest('[data-overview-go]');
  if (go) { activateTab(go.dataset.overviewGo); return; }
  const config = e.target.closest('[data-overview-config]');
  if (config) openConfigGroup(config.dataset.overviewConfig);
});
