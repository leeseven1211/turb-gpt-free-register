const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const commonSource = fs.readFileSync(path.join(root, 'webui/static/js/modern/common.js'), 'utf8');
const accountsSource = fs.readFileSync(path.join(root, 'webui/static/js/modern/accounts.js'), 'utf8');
const dateStart = commonSource.indexOf('function formatDateTime(v)');
const dateEnd = commonSource.indexOf('\nfunction taskErrorBadge', dateStart);
const dateFunctions = commonSource.slice(dateStart, dateEnd);
const detailStart = accountsSource.indexOf('function meaningfulTaskDetail(detail)');
const detailEnd = accountsSource.indexOf('\nfunction renderAccountTaskEvents', detailStart);
const detailFunction = accountsSource.slice(detailStart, detailEnd);
const logStart = accountsSource.indexOf('function renderAccountTaskRunLog()');
const logEnd = accountsSource.indexOf('\nfunction renderAccountTaskArtifacts', logStart);
const logRenderer = accountsSource.slice(logStart, logEnd);

assert.ok(dateStart >= 0 && dateEnd > dateStart, '公共日期格式化函数应存在');
assert.ok(detailStart >= 0 && detailEnd > detailStart, '技术日志字段整理函数应存在');
assert.ok(logStart >= 0 && logEnd > logStart, '任务 Run 日志渲染函数应存在');

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
    const panel = {textContent: ''};
    const context = {
      Intl, Date, lines: ${JSON.stringify(lines)}, panel,
      $: () => panel,
      browserTimeZoneName: () => '${timeZone}',
      document: {querySelectorAll: () => []},
    };
    vm.runInNewContext(${JSON.stringify(`${dateFunctions}\n${detailFunction}\n${logRenderer}\nlet accountTaskRunLogLines = lines;\nrenderAccountTaskRunLog();`)}, context);
    process.stdout.write(panel.textContent);
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
      ts: '2026-10-08T08:48:32+00:00', level: 'INFO', stage: 'preflight', message: '使用邮箱池',
      fields: {resource: 'masked@example.com', step_state: 'success'},
    },
    {
      ts: '2026-10-08T08:49:00Z', level: 'WARNING', stage: 'email', message: '等待邮件',
      fields: {attempt: 1},
    },
    {level: 'ERROR', stage: 'event', message: '缺少时间'},
    {ts: 'not-a-time', level: 'INFO', stage: 'event', message: '非法时间'},
  ]);
  assert.equal(output, [
    '2026-10-08 16:48:32 INFO preflight 使用邮箱池',
    '{',
    '  "resource": "masked@example.com"',
    '}',
    '2026-10-08 16:49:00 WARNING email 等待邮件',
    '{',
    '  "attempt": 1',
    '}',
    '时间缺失 ERROR event 缺少时间',
    '无效时间：not-a-time INFO event 非法时间',
  ].join('\n'));
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
  const css = fs.readFileSync(path.join(root, 'webui/static/css/modern.css'), 'utf8');
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
  vm.runInNewContext(`${accountsSource.slice(start, end)}\nrenderAccountTaskEvents();`, {
    accountTaskEventCache: events, $: () => panel,
    accountTaskEventStepState: () => '', meaningfulTaskDetail: () => null,
    esc: String, attrEsc: String, formatDateTime: String,
    ACCOUNT_TASK_STAGE_LABELS: {}, normalizeAccountTaskStage: () => '',
  });
  assert.deepEqual([...panel.innerHTML.matchAll(/data-event-id="(\d+)"/g)].map(match => Number(match[1])), [20, 10, 30]);
  assert.deepEqual(events.map(event => event.id), [10, 20, 30]);
});
