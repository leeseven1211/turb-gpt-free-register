const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..', '..');
const commonSource = fs.readFileSync(path.join(root, 'webui/static/js/shared/common.js'), 'utf8');
const accountsSource = require('../frontend_script_sources.cjs').readAccountScripts();
const jobsSource = fs.readFileSync(path.join(root, 'webui/static/js/pages/registration/page.js'), 'utf8');
const dateStart = commonSource.indexOf('function formatDateTime(v)');
const dateEnd = commonSource.indexOf('\nfunction taskErrorBadge', dateStart);
const dateFunctions = commonSource.slice(dateStart, dateEnd);
const stepFunctions = commonSource.slice(commonSource.indexOf('function taskProgressStepStatus'), commonSource.indexOf('function taskProgressStepMatches'));
const detailStart = accountsSource.indexOf('function meaningfulTaskDetail(detail)');
const detailEnd = accountsSource.indexOf('\nfunction renderAccountTaskEvents', detailStart);
const detailFunction = accountsSource.slice(detailStart, detailEnd);
const logFilterStart = accountsSource.indexOf('function accountTaskFilterRawStages');
const logFilterEnd = accountsSource.indexOf('\nfunction accountTaskFilterLabel', logFilterStart);
const logFilterFunction = accountsSource.slice(logFilterStart, logFilterEnd);
const eventHelperStart = accountsSource.indexOf('function rememberTaskLogDetails');
const eventHelperEnd = accountsSource.indexOf('\nfunction renderAccountTaskEvents', eventHelperStart);
const eventHelpers = accountsSource.slice(eventHelperStart, eventHelperEnd);
const logStart = accountsSource.indexOf('function renderAccountTaskRunLog()');
const logEnd = accountsSource.indexOf('\nfunction renderAccountTaskArtifacts', logStart);
const logRenderer = accountsSource.slice(logStart, logEnd);
const progressStart = accountsSource.indexOf('function accountTaskProgressStateLabel');
const progressEnd = accountsSource.indexOf('\nfunction accountTaskCanRetry', progressStart);
const progressFunctions = `${stepFunctions}\n${accountsSource.slice(progressStart, progressEnd)}`;
const resetStart = accountsSource.indexOf('function resetAccountTaskRunData');
const resetEnd = accountsSource.indexOf('\nfunction syncAccountTaskRunPicker', resetStart);
const resetFunction = accountsSource.slice(resetStart, resetEnd);
const openJobLogStart = jobsSource.indexOf('function openJobLog');
const openJobLogEnd = jobsSource.indexOf('\nfunction openLog', openJobLogStart);
const openJobLogFunction = jobsSource.slice(openJobLogStart, openJobLogEnd);
const batchHelperStart = jobsSource.indexOf('function jobProgressSnapshot');
const batchHelperEnd = jobsSource.indexOf('\nfunction refreshBatchProgressDurations', batchHelperStart);
const batchHelpers = `${stepFunctions}\n${jobsSource.slice(batchHelperStart, batchHelperEnd)}`;

assert.ok(dateStart >= 0 && dateEnd > dateStart, '公共日期格式化函数应存在');
assert.ok(detailStart >= 0 && detailEnd > detailStart, '技术日志字段整理函数应存在');
assert.ok(logStart >= 0 && logEnd > logStart, '任务 Run 日志渲染函数应存在');
assert.ok(progressStart >= 0 && progressEnd > progressStart, '任务进度展示函数应存在');
assert.ok(resetStart >= 0 && resetEnd > resetStart, 'Run 重置函数应存在');
assert.ok(openJobLogStart >= 0 && openJobLogEnd > openJobLogStart, '注册任务统一日志入口应存在');
assert.ok(batchHelperStart >= 0 && batchHelperEnd > batchHelperStart, '批次统一进度函数应存在');

function htmlEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character]));
}

function runVm(source, context = {}) {
  const sandbox = {Intl, Date, taskProgressStatusLabel: String, ...context};
  vm.runInNewContext(source, sandbox);
  return sandbox;
}

function formatInTimeZone(timeZone, value) {
  const script = `
    const vm = require('node:vm');
    const context = {Intl, Date, value: ${JSON.stringify(value)}};
    vm.runInNewContext(${JSON.stringify(`${dateFunctions}\nresult = formatDateTime(value);`)}, context);
    process.stdout.write(String(context.result));
  `;
  return execFileSync(process.execPath, ['-e', script], {
    env: {...process.env, TZ: timeZone},
    encoding: 'utf8',
  });
}

function renderLogInTimeZone(timeZone, lines) {
  const script = `
    const vm = require('node:vm');
    const panel = {textContent: '', innerHTML: ''};
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
    const context = {
      Intl, Date, lines: ${JSON.stringify(lines)}, panel,
      $: () => panel,
      esc: escapeHtml,
    browserTimeZoneName: () => '${timeZone}',
    document: {querySelectorAll: () => []},
      accountTaskProgressStepId: step => String(step?.id || step?.step_id || ''),
    };
    vm.runInNewContext(${JSON.stringify(`${dateFunctions}\n${detailFunction}\n${logFilterFunction}\nlet accountTaskStepFilter = null;\n${logRenderer}\nlet accountTaskRunLogLines = lines;\nrenderAccountTaskRunLog();`)}, context);
    process.stdout.write(panel.innerHTML);
  `;
  return execFileSync(process.execPath, ['-e', script], {
    env: {...process.env, TZ: timeZone},
    encoding: 'utf8',
  });
}

test('技术日志时间按浏览器时区转换并支持跨日', () => {
  assert.equal(formatInTimeZone('Asia/Shanghai', '2026-10-08T08:48:32Z'), '2026-10-08 16:48:32');
  assert.equal(formatInTimeZone('America/Los_Angeles', '2026-10-08T08:48:32Z'), '2026-10-08 01:48:32');
  assert.equal(formatInTimeZone('Asia/Shanghai', '2026-10-08T08:48:32+09:00'), '2026-10-08 07:48:32');
  assert.equal(formatInTimeZone('Asia/Shanghai', '2026-10-08T23:30:00-07:00'), '2026-10-09 14:30:00');
});

test('缺失和非法时间保留可诊断信息', () => {
  assert.equal(formatInTimeZone('UTC', null), '-');
  assert.equal(formatInTimeZone('UTC', 'not-a-time'), '无效时间：not-a-time');
  assert.match(dateFunctions, /return s \? `无效时间：\$\{s\}` : '时间缺失'/);
});

test('Run 技术日志复用公共格式化并标记缺失时间', () => {
  const output = renderLogInTimeZone('Asia/Shanghai', [
    {
      ts: '2026-10-08T08:48:32+00:00', level: 'INFO', stage: 'preflight', main_step_id: 'preflight-step', message: '使用邮箱池',
      fields: {resource: 'masked@example.com', step_state: 'success'},
    },
    {
      ts: '2026-10-08T08:49:00Z', level: 'WARNING', stage: 'email', main_step_id: 'email-step', message: '等待邮件',
      fields: {attempt: 1},
    },
    {level: 'ERROR', stage: 'event', message: '缺少时间'},
    {ts: 'not-a-time', level: 'INFO', stage: 'event', message: '非法时间'},
  ]);
  assert.match(output, /2026-10-08 16:48:32 INFO preflight 使用邮箱池/);
  assert.match(output, /2026-10-08 16:49:00 WARNING email 等待邮件/);
  assert.match(output, /时间缺失 ERROR 未关联步骤 缺少时间/);
  assert.match(output, /无效时间：not-a-time INFO 未关联步骤 非法时间/);
  assert.equal((output.match(/class="account-task-log-detail"/g) || []).length, 2);
  assert.match(output, /&quot;resource&quot;: &quot;masked@example.com&quot;/);
  assert.match(output, /查看技术详情/);
});

test('任务中心和日志详情都提供当前浏览器时区提示', () => {
  const template = fs.readFileSync(path.join(root, 'webui/templates/index.html'), 'utf8');
  assert.equal((template.match(/data-browser-timezone-hint/g) || []).length, 2);
  assert.match(accountsSource, /时间按当前浏览器时区显示 · \$\{browserTimeZoneName\(\)\}/);
  const hintStart = accountsSource.indexOf('function updateAccountTaskTimeZoneHints()');
  const hintEnd = accountsSource.indexOf('\nfunction renderAccountTaskArtifacts', hintStart);
  const hint = accountsSource.slice(hintStart, hintEnd);
  const element = {textContent: '', title: ''};
  vm.runInNewContext(`${hint}\nupdateAccountTaskTimeZoneHints();`, {
    browserTimeZoneName: () => 'Asia/Shanghai',
    document: {querySelectorAll: () => [element]},
  });
  assert.equal(element.textContent, '时间按当前浏览器时区显示 · Asia/Shanghai');
  assert.equal(element.title, element.textContent);
  const css = fs.readFileSync(path.join(root, 'webui/static/css/shell.css'), 'utf8');
  assert.match(css, /\.account-task-timezone-hint \{ max-width:220px; white-space:normal;/);
});

test('混合历史事件按校正后的时间展示且不改变 ID 游标顺序', () => {
  const start = accountsSource.indexOf('function renderAccountTaskEvents()');
  const end = accountsSource.indexOf('\nfunction renderAccountTaskRunLog()', start);
  const panel = {innerHTML: ''};
  const events = [
    {id: 10, created_at: '2026-09-08T02:11:15Z', message: '结束'},
    {id: 20, created_at: '2026-09-08T02:08:37Z', message: '较晚写入的早期事件'},
    {id: 30, created_at: '2026-09-08T10:11:15+08:00', message: '同一时刻按 ID 排序'},
  ];
  vm.runInNewContext(`${eventHelpers}\nlet accountTaskStepFilter = null;\n${accountsSource.slice(start, end)}\nrenderAccountTaskEvents();`, {
    accountTaskEventCache: events, $: selector => selector === '#accountTaskLogContent' ? panel : null,
    accountTaskEventStepState: () => '', meaningfulTaskDetail: () => null,
    esc: String, attrEsc: String, formatDateTime: String,
    ACCOUNT_TASK_STAGE_LABELS: {}, normalizeAccountTaskStage: () => '',
    accountTaskProgressSnapshot: null,
  });
  assert.deepEqual([...panel.innerHTML.matchAll(/data-event-id="(\d+)"/g)].map(match => Number(match[1])), [20, 10, 30]);
  assert.deepEqual(events.map(event => event.id), [10, 20, 30]);
});

test('flow_version2 失败摘要显示具体原因和结果状态，并折叠技术证据', () => {
  const progress = {
    outcome: {status: 'request_unknown'},
    failure: {
      step_id: 'auth', stage: 'oauth', label: 'Codex 授权', event_id: 'evt-9',
      message: '<远端结果待确认>', evidence: {provider: 'redacted'},
      error_info: {code: 'REMOTE-001', summary: '远端结果待确认', cause_summary: '密码验证请求返回 HTTP 401'}, reconcile_required: true,
    },
  };
  const sandbox = runVm(`${progressFunctions}
    result = {
      failure: accountTaskFailureSummary(progress),
      inferred: accountTaskFailureSummary({failure: {
        message: '仅凭旁路记录推断', evidence: {inferred: true},
        error_info: {summary: '待确认'},
      }}),
      labels: JSON.stringify(['unconfirmed', 'not_executed', 'request_unknown', 'stopped', 'attention_required']
        .map(status => accountTaskProgressStateLabel({state: status}))),
    };`, {
    progress,
    accountTaskStepFilter: null,
    ACCOUNT_TASK_PROGRESS_STATUS_LABELS: {
      pending: '未开始', running: '执行中', success: '已完成', failed: '失败',
      unconfirmed: '未确认', not_executed: '未执行', request_unknown: '结果待确认',
      stopped: '已中断', attention_required: '待人工处理',
    },
    TASK_PROGRESS_STATUS_LABELS: {},
    esc: htmlEscape,
    attrEsc: htmlEscape,
    formatDateTime: value => String(value || '-'),
    formatTaskDuration: value => `${value}ms`,
    taskProgressStepStatus: step => String(step?.state || 'pending'),
  });
  assert.match(sandbox.result.failure, /失败位置：Codex 授权 · oauth/);
  assert.match(sandbox.result.failure, /事件 evt-9/);
  assert.match(sandbox.result.failure, /远端结果待确认/);
  assert.match(sandbox.result.failure, /<span>原因：密码验证请求返回 HTTP 401<\/span>/);
  assert.match(sandbox.result.failure, /远端结果待确认/);
  assert.doesNotMatch(sandbox.result.failure, /需要对账/);
  assert.match(sandbox.result.failure, /查看技术详情/);
  assert.doesNotMatch(sandbox.result.failure, /<远端结果待确认>/);
  assert.match(sandbox.result.inferred, /待确认位置/);
  assert.doesNotMatch(sandbox.result.inferred, /失败位置/);
  assert.match(sandbox.result.inferred, /错误：待确认/);
  assert.deepEqual(JSON.parse(sandbox.result.labels), ['未确认', '未执行', '结果待确认', '已中断', '待人工处理']);
});

test('待确认状态不要求人工处理，并保留可重跑提示', () => {
  const statusStart = commonSource.indexOf('const LIST_FACET_LABELS =');
  const statusEnd = commonSource.indexOf('\nfunction taskProgressStatusLabel', statusStart);
  const progressStart = jobsSource.indexOf('function progressJobResult(');
  const progressEnd = jobsSource.indexOf('\nfunction ', progressStart + 1);
  const sandbox = runVm(`${commonSource.slice(statusStart, statusEnd)}\n${jobsSource.slice(progressStart, progressEnd)}\nresult = {
    status: LIST_FACET_LABELS.status.attention_required,
    reconcile: LIST_FACET_LABELS.status.manual_reconcile,
    progress: TASK_PROGRESS_STATUS_LABELS.attention_required,
    remoteSync: LIST_FACET_LABELS.stage.remote_sync,
    job: progressJobResult({status:'manual_reconcile', retryable:true}).label,
  };`);
  assert.equal(sandbox.result.status, '结果待确认');
  assert.equal(sandbox.result.reconcile, '结果待确认');
  assert.equal(sandbox.result.progress, '结果待确认');
  assert.equal(sandbox.result.remoteSync, '原单状态查询');
  assert.equal(sandbox.result.job, '结果待确认（可重跑）');
});

test('详情失败位置优先采用有具体证据纠正的阶段', () => {
  const sandbox = runVm(`${progressFunctions}
    const failure = {
      label:'校验 Token', stage:'access_token', evidence:'explicit', message:'原单查询 HTTP 404',
      error_info:{stage:'remote_sync', summary:'原单查询 HTTP 404'},
    };
    result = {summary: accountTaskFailureSummary({failure}), brief: accountTaskProgressBrief({failure}),
      uncorrected: accountTaskProgressBrief({failure: {...failure, error_info: null}})};`, {
    esc: htmlEscape, attrEsc: htmlEscape, facetLabel: (_group, value) => ({remote_sync:'原单状态查询'})[value] || value,
  });
  assert.match(sandbox.result.summary, /失败位置：原单状态查询/);
  assert.match(sandbox.result.brief, /失败：原单状态查询/);
  assert.doesNotMatch(sandbox.result.brief, /校验 Token/);
  assert.match(sandbox.result.uncorrected, /校验 Token · access_token/);
});

test('Roxy 登录失败红条显示具体分类并保留原始事件文案', () => {
  const failure = {
    label: '登录与身份验证', stage: 'authenticate', evidence: 'explicit',
    message: 'Roxy 浏览器登录未完成',
    error_info: {code: 'roxy_login_page_timeout', summary: 'Roxy 登录页未就绪，登录预检请求超时'},
  };
  const sandbox = runVm(`${progressFunctions}\nresult = accountTaskProgressBrief({failure});`, {
    failure, esc: htmlEscape, attrEsc: htmlEscape,
  });
  assert.match(sandbox.result, /Roxy 登录页未就绪，登录预检请求超时/);
  assert.doesNotMatch(sandbox.result, /Roxy 浏览器登录未完成/);
  assert.equal(failure.message, 'Roxy 浏览器登录未完成');
});

test('套餐查询失败在详情展示每个国家的具体原因并转义文本', () => {
  const progress = {failure:{label:'查询套餐', stage:'plan_request', message:'JP：本地 AT 已过期；VN：服务端返回 HTTP 401',
    country_failures:[
      {country:'JP', code:'token_local_expired', summary:'本地检查发现 AT 已过期，未发起套餐请求', event_id:'1'},
      {country:'VN', code:'http_401', summary:'服务端返回 HTTP 401 <拒绝>', event_id:'2'},
      {country:'IN'},
    ]}};
  const sandbox = runVm(`${progressFunctions}\nresult = accountTaskFailureSummary(progress);`, {
    progress, esc: htmlEscape, attrEsc: htmlEscape,
  });
  assert.match(sandbox.result, /JP：本地检查发现 AT 已过期，未发起套餐请求/);
  assert.match(sandbox.result, /VN：服务端返回 HTTP 401 &lt;拒绝&gt;/);
  assert.match(sandbox.result, /IN：未记录具体原因/);
  assert.doesNotMatch(sandbox.result, /JP：本地 AT 已过期；VN：服务端返回 HTTP 401/);
});

test('步骤筛选同时支持 main_step_id 和 raw_stages，并能清除回全量运行日志', () => {
  const events = [
    {id: 1, main_step_id: 'step-auth', stage_label: '授权', message: '主步骤'},
    {id: 2, raw_stages: ['legacy-auth'], stage_label: '旧阶段', message: '兼容阶段'},
    {id: 3, main_step_id: 'step-other', stage_label: '其他', message: '其他步骤'},
    {id: 4, stage: 'page', stage_label: '打开页面', message: '旧日志阶段'},
  ];
  const renderEvents = filter => {
    const panel = {innerHTML: ''};
    const sandbox = runVm(`${eventHelpers}
      let accountTaskStepFilter = ${JSON.stringify(filter)};
      ${accountsSource.slice(accountsSource.indexOf('function renderAccountTaskEvents()'), accountsSource.indexOf('\nfunction renderAccountTaskRunLog()', accountsSource.indexOf('function renderAccountTaskEvents()')))}
      renderAccountTaskEvents();`, {
      accountTaskEventCache: events,
      accountTaskProgressSnapshot: {main_steps: [{id: 'step-auth', raw_stages: ['authenticate', 'page']}]},
      $: selector => selector === '#accountTaskLogContent' ? panel : null,
      accountTaskEventStepState: () => '',
      meaningfulTaskDetail: () => null,
      esc: htmlEscape,
      attrEsc: htmlEscape,
      formatDateTime: value => String(value || '-'),
      ACCOUNT_TASK_STAGE_LABELS: {},
      normalizeAccountTaskStage: () => '',
      accountTaskProgressStepId: step => String(step?.id || step?.step_id || ''),
      panel,
    });
    return sandbox.panel.innerHTML;
  };
  assert.deepEqual([...renderEvents('step-auth').matchAll(/data-event-id="(\d+)"/g)].map(match => Number(match[1])), [1, 4]);
  assert.deepEqual([...renderEvents('legacy-auth').matchAll(/data-event-id="(\d+)"/g)].map(match => Number(match[1])), [2]);

  const lines = events.map(event => ({
    ts: '2026-10-08T00:00:00Z', level: 'INFO', stage: event.stage, stage_label: event.stage_label,
    main_step_id: event.main_step_id, raw_stages: event.raw_stages, message: event.message,
  }));
  const panel = {textContent: '', innerHTML: ''};
  const sandbox = runVm(`${dateFunctions}
    ${detailFunction}
    ${logFilterFunction}
    ${logRenderer}
    let accountTaskStepFilter = 'step-auth';
    let accountTaskRunLogLines = lines;
    renderAccountTaskRunLog();
    const filtered = panel.innerHTML;
    accountTaskStepFilter = null;
    renderAccountTaskRunLog();
    result = {filtered, all: panel.innerHTML};`, {
    Intl, Date, lines, panel,
    $: selector => selector === '#accountTaskRunLogContent' ? panel : null,
    browserTimeZoneName: () => 'UTC',
    document: {querySelectorAll: () => []},
    esc: htmlEscape,
    attrEsc: htmlEscape,
    accountTaskProgressSnapshot: {main_steps: [{id: 'step-auth', raw_stages: ['authenticate', 'page']}]},
    accountTaskProgressStepId: step => String(step?.id || step?.step_id || ''),
  });
  assert.match(sandbox.result.filtered, /主步骤/);
  assert.match(sandbox.result.filtered, /旧日志阶段/);
  assert.doesNotMatch(sandbox.result.filtered, /其他步骤/);
  assert.match(sandbox.result.all, /主步骤/);
  assert.match(sandbox.result.all, /兼容阶段/);
  assert.match(sandbox.result.all, /其他步骤/);
});

test('切换 Run 会清除旧步骤筛选，同时保留显式传入的新筛选', () => {
  const node = () => ({
    innerHTML: '', textContent: '',
    classList: {add() {}, remove() {}},
  });
  const nodes = new Map([
    ['#accountTaskLogContent', node()],
    ['#accountTaskRunLogContent', node()],
    ['#accountTaskNewEvents', node()],
  ]);
  const sandbox = runVm(`${resetFunction}
    resetAccountTaskRunData(22);
    const first = {run: activeAccountTaskRunId, filter: accountTaskStepFilter};
    accountTaskPendingStepFilter = 'step-new';
    resetAccountTaskRunData(33);
    const second = {run: activeAccountTaskRunId, filter: accountTaskStepFilter};
    resetAccountTaskRunData(44);
    result = JSON.stringify({first, second, finalRun: activeAccountTaskRunId, finalFilter: accountTaskStepFilter});`, {
    $: selector => nodes.get(selector) || node(),
    activeAccountTaskRunId: 11,
    accountTaskPendingStepFilter: null,
    accountTaskStepFilter: 'step-old',
    accountTaskEventCursor: 9,
    accountTaskEventCache: [{id: 1}],
    accountTaskNewEventCount: 2,
    accountTaskRunLogCursor: 8,
    accountTaskRunLogLines: [{message: 'old'}],
    accountTaskProgressSnapshot: {main_steps: []},
    accountTaskProgressError: 'old',
    accountTaskProgressRequestId: 1,
    renderAccountTaskProgressSnapshot: () => {},
    closeAccountTaskStepDialog: () => {},
    hideAccountTaskStepTooltip: () => {},
  });
  assert.deepEqual(JSON.parse(sandbox.result), {
    first: {run: 22, filter: null},
    second: {run: 33, filter: 'step-new'},
    finalRun: 44,
    finalFilter: null,
  });
});

test('注册步骤入口的筛选不会被加载中的空快照清除', () => {
  const start = accountsSource.indexOf('function renderAccountTaskProgressSnapshot(');
  const end = accountsSource.indexOf('\nfunction renderAccountTaskStageProgress(', start);
  const sandbox = runVm(`${stepFunctions}\n${accountsSource.slice(start, end)}
    renderAccountTaskProgressSnapshot(null);
    const loadingFilter = accountTaskStepFilter;
    renderAccountTaskProgressSnapshot({main_steps: []});
    result = {loadingFilter, emptyFilter: accountTaskStepFilter};`, {
    accountTaskStepFilter: 'network',
    $: () => ({innerHTML: '', classList: {add() {}}}),
    hideAccountTaskStepTooltip() {},
    closeAccountTaskStepDialog() {},
    renderAccountTaskFilterBar() {},
  });
  assert.equal(sandbox.result.loadingFilter, 'network');
  assert.equal(sandbox.result.emptyFilter, null);
});

test('多步骤按宽度紧凑排列，窄屏双卡分页仍保持实际顺序', () => {
  const sandbox = runVm(`${progressFunctions}
    const steps = Array.from({length: 17}, (_, index) => ({id: 'step-' + index}));
    const desktopSize = accountTaskProgressPageSize(900, steps.length);
    const mobileSize = accountTaskProgressPageSize(315, steps.length);
    const desktop = accountTaskProgressPage(steps, 99, desktopSize);
    const mobileIds = Array.from({length: Math.ceil(steps.length / mobileSize)}, (_, page) => accountTaskProgressPage(steps, page, mobileSize).steps.map(step => step.id)).flat();
    result = JSON.stringify({desktopSize, mobileSize, fullRow: accountTaskProgressPageSize(1048, 11), page: desktop.page, pages: desktop.pages, desktopIds: desktop.steps.map(step => step.id), mobileIds});`);
  const result = JSON.parse(sandbox.result);
  assert.equal(result.desktopSize, 9);
  assert.equal(result.mobileSize, 2);
  assert.equal(result.fullRow, 11);
  assert.equal(result.page, 1);
  assert.equal(result.pages, 2);
  assert.deepEqual(result.desktopIds, Array.from({length: 8}, (_, index) => `step-${index + 9}`));
  assert.deepEqual(result.mobileIds, Array.from({length: 17}, (_, index) => `step-${index}`));
});

test('步骤卡片直接显示耗时，悬浮详情并保留日志筛选入口', () => {
  const sandbox = runVm(`${progressFunctions}
    result = accountTaskProgressStepMarkup({id: 'preflight', label: '<配置预检>', state: 'pending', display_status: 'record_incomplete', reason: '旧记录漏收口', duration_ms: 1200, attempts: [{state: 'running'}], children: [{id: 'child'}]}, 0);`, {
    ACCOUNT_TASK_PROGRESS_STATUS_LABELS: {record_incomplete: '记录不完整'},
    TASK_PROGRESS_STATUS_LABELS: {},
    esc: htmlEscape, attrEsc: htmlEscape,
    taskProgressStepStatus: step => step.state,
    taskProgressStatusLabel: state => state,
    formatTaskDuration: value => `${value}ms`,
  });
  assert.match(sandbox.result, /is-record_incomplete/);
  assert.match(sandbox.result, /记录不完整/);
  assert.match(sandbox.result, /data-account-task-step-filter="preflight"/);
  assert.match(sandbox.result, /data-accounts-tooltip=/);
  assert.match(sandbox.result, /耗时 1.2秒/);
  assert.doesNotMatch(sandbox.result, /data-account-task-step-details|<details|<pre|is-unconfirmed|<配置预检>/);
});

test('注册步骤显示耗时和安全悬浮信息，整块卡片仍可查看日志', () => {
  const sandbox = runVm(`${batchHelpers}
    result = jobProgressStepMarkup({key:'network', label:'分配网络', state:'success', duration_ms:2200, started_at:'2026-10-10T00:00:00Z', completed_at:'2026-10-10T00:00:02.200Z', message:'<线路就绪>'},0,77);`, {
    taskProgressStatusLabel: () => '已完成', formatDateTime: String,
    esc: htmlEscape, attrEsc: htmlEscape,
  });
  assert.match(sandbox.result, /耗时 2.2秒/);
  assert.match(sandbox.result, /data-accounts-tooltip=/);
  assert.match(sandbox.result, /开始：2026-10-10T00:00:00Z/);
  assert.match(sandbox.result, /&lt;线路就绪&gt;/);
  assert.match(sandbox.result, /data-progress-step-job="77"/);
  assert.doesNotMatch(sandbox.result, /<details|<summary|<线路就绪>/);
});

test('执行中的耗时使用当前时间，历史未收口的步骤不继续计时', () => {
  const sandbox = runVm(`${stepFunctions}
    const started_at='2026-10-10T00:00:00Z';
    const now=Date.parse(started_at)+42000;
    result = [
      taskProgressStepDuration({state:'running',started_at,duration_ms:1000},now),
      taskProgressStepDuration({state:'pending',display_status:'record_incomplete',started_at},now),
      taskProgressStepDuration({state:'success',duration_ms:0},now),
      taskProgressStepDuration({state:'pending'},now),
    ];`);
  assert.deepEqual(Array.from(sandbox.result), ['42秒','—','0秒','—']);
});

test('调试暂停冻结当前步骤计时，历史缺失暂停时间不倒推', () => {
  const sandbox = runVm(`${stepFunctions}
    const started_at='2026-10-13T10:00:00Z';
    const debug_pause={state:'paused',paused_at:'2026-10-13T10:00:42Z',hold_until:'2026-10-13T10:30:42Z',reason:'不可显示'};
    const step={state:'running',display_status:'debug_paused',started_at,debug_pause};
    result = [taskProgressStepDuration(step,Date.parse(started_at)+90000),
      taskProgressStepDuration(step,Date.parse(started_at)+180000),
      taskProgressStepDuration({...step,debug_pause:{state:'paused'},duration_ms:1000}),
      taskProgressStepDuration({state:'failed',duration_ms:2000,debug_pause}),
      taskDebugPauseSummary(debug_pause),
      taskDebugPauseSummary({state:'paused'})];`, {formatDateTime:String});
  assert.deepEqual(Array.from(sandbox.result).slice(0,4), ['42秒','42秒','—','2秒']);
  assert.match(sandbox.result[4], /调试暂停 · 等待结束调试/);
  assert.match(sandbox.result[4], /暂停于.*10:00:42Z.*保留至.*10:30:42Z/);
  assert.doesNotMatch(sandbox.result[4], /不可显示/);
  assert.match(sandbox.result[5], /暂停时间未记录/);
});

test('任务列表和所选Run详情展示调试暂停而不更改底层状态', () => {
  assert.match(accountsSource, /pillV2\(task\.debug_pause \? 'debug_paused' : task\.status, 'status'\)/);
  assert.match(accountsSource, /selectedRun\.debug_pause \? taskDebugPauseSummary\(selectedRun\.debug_pause\)/);
  assert.match(accountsSource, /taskDebugPauseSummary\(progress\.debug_pause\)/);
});

test('旧 Run 弹窗在运行切换时关闭，恢复父弹窗的交互状态', () => {
  const overlay = {classList: {add: () => {} }};
  const sibling = {inert: true};
  const sandbox = runVm(`${progressFunctions}
    accountTaskStepDetailState = {context: '11:22', stepId: 'auth', tab: 'attempts'};
    accountTaskStepDetailInert.set(sibling, false);
    renderAccountTaskStepDialog();
    result = {closed: accountTaskStepDetailState === null, restored: !sibling.inert};`, {
    activeAccountTaskId: 11, activeAccountTaskRunId: 33,
    $: selector => selector === '#accountTaskStepDetailOverlay' ? overlay : null,
    sibling,
  });
  assert.equal(sandbox.result.closed, true);
  assert.equal(sandbox.result.restored, true);
});

test('注册任务日志入口传递 operation task、Run 和步骤映射', () => {
  const calls = [];
  const sandbox = runVm(`${openJobLogFunction}
    const mapped = openJobLog({operation_task_id: '17', operation_run_id: '8'}, 'step-auth');
    const legacy = openJobLog({id: 99}, null);
    result = {mapped, legacy, calls};`, {
    calls,
    openAccountTaskLog: (...args) => calls.push(args),
  });
  assert.equal(sandbox.result.mapped, true);
  assert.equal(sandbox.result.legacy, false);
  assert.deepEqual(sandbox.result.calls, [[17, 8, 'step-auth']]);
});

test('批次进度优先使用 v2 main_steps 的实际顺序并转义标签', () => {
  const sandbox = runVm(`${batchHelpers}
    const job = {
      progress_steps: {legacy: {state: 'success'}},
      progress: {},
      progress_snapshot: {flow_version: 'flow_version2', main_steps: [
        {id: 'observed', label: '<已观察>', state: 'request_unknown', raw_stages: ['oauth'], duration_ms: 'invalid'},
        {id: 'skipped', label: '已跳过步骤', state: 'skipped'},
        {id: 'pending', label: '未观察步骤', state: 'skipped', display_status: 'not_executed'},
      ]},
    };
    const steps = jobProgressMainSteps(job, [{key: 'legacy', label: '错误旧顺序'}]);
    result = JSON.stringify({
      ids: steps.map(step => step.key),
      html: steps.map((step, index) => jobProgressStepMarkup(step, index, 7)).join(''),
    });`, {
    taskProgressStatusLabel: status => ({request_unknown: '结果待确认', not_executed: '未执行'}[status] || status),
    progressJobResult: () => ({label: '等待中', cls: 'is-waiting'}),
    esc: htmlEscape,
    attrEsc: htmlEscape,
    formatDateTime: value => String(value || '-'),
    formatProgressDuration: () => '',
  });
  const result = JSON.parse(sandbox.result);
  assert.deepEqual(result.ids, ['observed', 'pending']);
  assert.match(result.html, /&lt;已观察&gt;/);
  assert.doesNotMatch(result.html, /<已观察>/);
  assert.doesNotMatch(result.html, /NaN/);
  assert.match(result.html, /结果待确认/);
  assert.match(result.html, /未执行/);
});

test('进度详情按真实阶段显示事件，不把开始和完成算成重试', () => {
  const sandbox = runVm(`${stepFunctions}
    result = taskProgressStepTooltip({
      id: 'authenticate', label: '登录与身份验证', state: 'running',
      raw_stages: ['page', 'submit_email', 'auth_redirect', 'login_password', 'email_otp'],
      children: [
        {id: 'page', label: '打开页面', state: 'success', duration_ms: 51000},
        {id: 'submit_email', label: '提交邮箱', state: 'running', started_at: '2026-10-13T08:49:09Z'},
      ],
      attempts: [
        {raw_stage: 'page', raw_stage_label: '打开页面', state: 'running', created_at: '2026-10-13T08:48:18Z', step_instance_id: 'page-a'},
        {raw_stage: 'page', raw_stage_label: '打开页面', state: 'success', created_at: '2026-10-13T08:49:09Z', step_instance_id: 'page-a'},
        {raw_stage: 'submit_email', raw_stage_label: '提交邮箱', state: 'running', created_at: '2026-10-13T08:49:09Z', step_instance_id: 'email-a'},
      ],
    });`, {
    formatDateTime: value => value,
    taskProgressStatusLabel: value => ({running: '执行中', success: '已完成'}[value] || value),
  });
  assert.match(sandbox.result, /已记录阶段：打开页面、提交邮箱/);
  assert.match(sandbox.result, /打开页面 · 已完成 · 51秒/);
  assert.match(sandbox.result, /阶段事件（3 条）/);
  assert.match(sandbox.result, /2\. 打开页面 · 已完成 · 2026-10-13T08:49:09Z/);
  assert.doesNotMatch(sandbox.result, /尝试记录|原始阶段|login_password|email_otp/);
});

test('旧阶段事件缺少实际时间时明确提示，不能借用阶段开始时间', () => {
  const sandbox = runVm(`${stepFunctions}
    result = taskProgressStepTooltip({
      id: 'authenticate', label: '登录与身份验证', state: 'running',
      attempts: [{raw_stage: 'submit_email', raw_stage_label: '提交邮箱', state: 'running',
        started_at: '2026-10-13T09:24:23Z', created_at: null, event_time_known: false}],
    });`, {formatDateTime: value => value});
  assert.match(sandbox.result, /提交邮箱.*发生时间未记录/);
  assert.doesNotMatch(sandbox.result, /2026-10-13T09:24:23Z/);
});


test('任务步骤入口统一称为阶段事件，不把事件条数写成尝试次数', () => {
  assert.doesNotMatch(accountsSource, /尝试记录/);
  assert.match(accountsSource, /悬浮查看时间与阶段事件/);
  assert.match(accountsSource, /查看阶段事件/);
});
