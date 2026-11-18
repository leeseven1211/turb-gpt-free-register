const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {createRequire} = require('node:module');

const root = path.resolve(__dirname, '../..');
const {JSDOM} = createRequire(path.join(root, 'frontend/package.json'))('jsdom');
const common = fs.readFileSync(path.join(root, 'webui/static/js/shared/common.js'), 'utf8');
const operations = fs.readFileSync(path.join(root, 'webui/static/js/pages/operations/page.js'), 'utf8');
const template = fs.readFileSync(path.join(root, 'webui/templates/index.html'), 'utf8');
const dialog = template.slice(template.indexOf('<div class="body hidden" id="accountTaskLogPanel"'), template.indexOf('<div id="toast"'));
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
function display(t, data) {
  const dom = new JSDOM(dialog, {runScripts: 'outside-only'});
  t.after(() => dom.window.close());
  const document = dom.window.document;
  const query = selector => document.querySelector(selector);
  Object.assign(dom.window, {
    $: query, fixture: data, LIST_FACET_LABELS: {task_type: {}, stage: {}, target_status: {}},
    TASK_PROGRESS_STATUS_LABELS: {}, esc: escape, attrEsc: escape, short: String,
    facetLabel: (_group, value) => value, formatDateTime: String, browserTimeZoneName: () => 'UTC',
    bindAccountsHoverTooltips() {},
  });
  const context = dom.getInternalVMContext();
  const run = script => vm.runInContext(script, context);
  run(common.slice(common.indexOf('function taskProgressStatusLabel'), common.indexOf('function taskProgressStepMatches')));
  run(common.slice(common.indexOf('function taskErrorBadge'), common.indexOf('function jobsV2OpIcons')));
  run(operations);
  run(`activeAccountTaskId = '70'; activeAccountTaskRunId = '71';
    accountTaskSnapshot = {runs: [{...fixture.run, id: 71}]};
    accountTaskProgressSnapshot = fixture.progress;
    accountTaskEventCache = fixture.events || [];
    accountTaskRunLogLines = fixture.logs || [];
    renderAccountTaskSelectedRunError(accountTaskSnapshot.runs[0], fixture.progress);
    renderAccountTaskProgressSnapshot(fixture.progress);
    renderAccountTaskEvents(); renderAccountTaskRunLog();`);
  return {query, run};
}

test('同一失败只显示步骤摘要，无步骤卡时仍能打开两侧证据', t => {
  const {query} = display(t, {
    run: {error_message: '合成记录未归档', error_info: {display_code: 'SYN-42', summary: '归档失败'}},
    progress: {main_steps: [], failure: {label: '归档', stage: 'archive', message: '合成记录未归档',
      error_info: {cause_summary: '合成分卷缺失'}, evidence: {part: 5}}},
  });
  assert.ok(query('#accountTaskLogErrorSummary').classList.contains('hidden'), '对应同一原因的执行红条应合并');
  const brief = query('#accountTaskStageProgress [data-account-task-failure-details]');
  assert.match(brief.textContent, /合成分卷缺失/);
  assert.match(brief.textContent, /SYN-42/);
  brief.click();
  assert.match(query('#accountTaskStepDetailContent pre').textContent, /合成记录未归档/);
  assert.match(query('#accountTaskStepDetailContent pre').textContent, /SYN-42/);
  assert.match(query('#accountTaskStepDetailContent pre').textContent, /"part": 5/);
});

test('同一分类下不同原因以及缺少步骤快照时保留执行错误', t => {
  const {query, run} = display(t, {
    run: {error_info: {summary: '归档失败', cause_summary: '合成目录只读'}},
    progress: {main_steps: [], failure: {label: '归档', error_info: {summary: '归档失败', cause_summary: '合成分卷缺失'}}},
  });
  assert.match(query('#accountTaskLogErrorSummary').textContent, /合成目录只读/);
  assert.match(query('#accountTaskStageProgress').textContent, /合成分卷缺失/);
  run('renderAccountTaskSelectedRunError(accountTaskSnapshot.runs[0], null); renderAccountTaskProgressSnapshot(null);');
  assert.ok(!query('#accountTaskLogErrorSummary').classList.contains('hidden'));
  assert.match(query('#accountTaskLogErrorSummary').textContent, /合成目录只读/);
  assert.match(query('#accountTaskLogErrorSummary details pre').textContent, /"cause_summary": "合成目录只读"/);
});

test('失败明细通过摘要展开，单页步骤不另占一行翻页栏', t => {
  const {query} = display(t, {run: {}, progress: {
    main_steps: [{id: 'inspect', label: '检查归档', state: 'failed'}],
    outcome: {status: 'failed'},
    failure: {label: '检查归档', message: '汇总文本', country_failures: [
      {country: 'A', summary: '合成一缺页'}, {country: 'B', summary: '合成二缺页'},
    ]},
  }});
  assert.doesNotMatch(query('#accountTaskStageProgress').textContent, /合成一缺页|合成二缺页|已全部显示/);
  const brief = query('[data-account-task-failure-details]');
  assert.match(brief.textContent, /2 个国家/);
  brief.click();
  assert.match(query('#accountTaskStepDetailContent').textContent, /A：合成一缺页/);
  assert.match(query('#accountTaskStepDetailContent').textContent, /B：合成二缺页/);
});

test('共用原始阶段的事件与日志只归入有明确证据的步骤', t => {
  const records = [
    {id: 1, message: '合成甲记录', main_step_id: 'first', raw_stage: 'shared'},
    {id: 2, message: '合成乙记录', main_step_id: 'second', stage: 'shared'},
    {id: 3, message: '合成无归属', stage: 'shared'},
    {id: 4, message: '合成关联编号', event_id: 'fixture-event', stage: 'shared'},
    {id: 5, message: '合成旧格式', raw_stage: 'only-a'},
  ];
  const {query, run} = display(t, {run: {}, events: records, logs: records, progress: {
    main_steps: [{id: 'first', label: '合成甲', raw_stages: ['shared', 'only-a'], event_ids: ['fixture-event']},
      {id: 'second', label: '合成乙', raw_stages: ['shared']}],
  }});
  assert.match(query('[data-event-id="3"] .account-task-event-head').textContent, /未关联步骤/);
  assert.match(query('[data-event-id="2"] .account-task-event-head').textContent, /合成乙/);
  run("setAccountTaskStepFilter('shared')");
  assert.equal(query('#accountTaskProgressFilter strong').textContent, 'shared');
  assert.equal(query('#accountTaskStageProgress [aria-pressed="true"]'), null);
  const first = query('[data-account-task-step-filter="first"]');
  first.focus();
  first.click();
  assert.equal(first.ownerDocument.activeElement, first, '选择步骤应保留原按钮焦点，避免重新触发悬浮提示');
  assert.equal(first.getAttribute('aria-pressed'), 'true');
  for (const id of ['#accountTaskLogContent', '#accountTaskRunLogContent']) {
    const text = query(id).textContent;
    assert.match(text, /合成甲记录/);
    assert.match(text, /合成关联编号/);
    assert.match(text, /合成旧格式/);
    assert.doesNotMatch(text, /合成乙记录|合成无归属/);
  }
});

test('首次读取进度即合并同一失败，切换运行不会引用上一次的证据', async t => {
  const task = {id: 70, task_type: '合成归档', target_id: 'fixture-archive', status: 'running', runs: [
    {id: 71, status: 'failed', error_message: '合成缺页'},
    {id: 72, status: 'failed', error_message: '合成库只读'},
  ]};
  const data = {task, progress: null, run: {}, nextProgress: {failure: {label: '归档', message: '合成缺页'}}};
  const {query, run} = display(t, data);
  run(`globalThis.api = async path => {
    if (path.endsWith('?include_events=0')) return {task: fixture.task};
    if (path.endsWith('/progress')) return {progress: fixture.nextProgress};
    if (path.includes('/events?')) return {items: []};
    throw new Error('合成只读测试收到未知地址：' + path);
  }`);
  await run('pollAccountTaskLog()');
  assert.match(query('#accountTaskDetailSummary').title, /fixture-archive/);
  assert.ok(query('#accountTaskLogErrorSummary').classList.contains('hidden'));
  query('[data-account-task-failure-details]').click();
  assert.match(query('#accountTaskStepDetailContent pre').textContent, /合成缺页/);
  run('resetAccountTaskRunData(72); fixture.nextProgress = null;');
  await run('pollAccountTaskLog()');
  assert.equal(query('[data-account-task-failure-details]'), null);
  assert.match(query('#accountTaskLogErrorSummary summary').textContent, /合成库只读/);
  assert.doesNotMatch(query('#accountTaskLogErrorSummary').textContent, /合成缺页/);
});

test('选中阶段后可读声明的依赖、首次记录序号和本阶段明确关联的子任务', t => {
  const steps = [
    {id: 'read', label: '读取样稿'},
    {id: 'merge', label: '合并样稿', observed_order: 5, depends_on: ['read', 'old<source>'],
      attempts: [{child_task_id: 801, child_run_id: 802}, {child_task_id: 801, child_run_id: 802}, {child_run_id: 810}]},
    {id: 'empty', label: '历史样稿', depends_on: [], observed_order: null, attempts: [{}, {}]},
  ];
  const {query, run} = display(t, {run: {}, progress: {main_steps: steps, outcome: {child_tasks:[{task_id: 999}]}}});
  Object.defineProperty(query('#accountTaskStageProgress'), 'clientWidth', {value: 920});
  run('renderAccountTaskProgressSnapshot(fixture.progress)');
  const opener = '#accountTaskProgressFilter [data-account-task-step-details]';
  assert.equal(query(opener), null);
  query('[data-account-task-step-filter="merge"]').click();
  query(opener).click();
  const relations = () => query('#accountTaskStepDetailContent').textContent;
  assert.match(relations(), /前置步骤读取样稿、old<source>/);
  assert.match(relations(), /首次记录序号5/);
  assert.equal((relations().match(/任务 #801 · 运行 #802/g) || []).length, 1);
  assert.doesNotMatch(relations(), /#999|并行|重试/);
  assert.equal(query('#accountTaskStepDetailContent source'), null);
  run("fixture.progress.main_steps[0].label='读取新版样稿'; renderAccountTaskProgressSnapshot(fixture.progress);");
  assert.match(relations(), /前置步骤读取新版样稿/);
  query('[data-step-dialog-tab="attempts"]').click();
  query('#btnCloseAccountTaskStepDetail').click();
  assert.equal(query(opener).ownerDocument.activeElement, query(opener));
  query('[data-account-task-step-filter="empty"]').click();
  query(opener).click();
  assert.doesNotMatch(relations(), /前置步骤|首次记录序号|关联子任务|并行|重试/);
});
