const assert = require('node:assert/strict');
const test = require('node:test');
const {createVueHarness} = require('../frontend_vue_loader.cjs');
const h = createVueHarness();
const {resultText} = h.load('src/features/tasks/presentation.ts');
const {taskResultSummary} = h.load('src/features/tasks/resultSummary.ts');
const {shortErrorLabel} = h.load('src/shared/errorLabels.ts');
test.after(() => h.close());

function scan(status, result_summary = {}, extra = {}) {
  return resultText({id:'1',task_type: 'sub2api_scan', status, result_summary, ...extra});
}

const listResult = task => {
  const result = taskResultSummary({id:'1',...task},shortErrorLabel(task.error_info));
  return [result.label,...(result.secondary?[result.secondary]:[])];
};

for (const [status, result_summary, expected, extra] of [
  ['success', {processed: 0}, '异常扫描完成'],
  ['success', {ok: false}, '异常扫描完成'],
  ['unsupported', {ok: true}, '扫描未完成'],
  ['partial_success', {ok: false}, '部分完成'],
  ['request_unknown', {ok: true}, '结果待确认'],
  ['cancelled', {ok: true}, '已取消'],
  ['failed', {ok: true}, '集成接口异常', {error_info: {code: 'external.sub2api.http'}}],
]) {
  test(`扫描列表在 ${status}、摘要 ${JSON.stringify(result_summary)} 时显示${expected}`, () => {
    assert.deepEqual([...listResult({task_type: 'sub2api_scan', status, result_summary, ...extra})], [expected]);
  });
}

test('成功扫描的真实摘要没有 ok 字段时仍显示完成', () => {
  for (const summary of [
    {group_ids: [16], remote_errors: 0, accounts: 0, processed: 0, reasons: {}},
    {group_ids: [16], remote_errors: 1, accounts: 3, processed: 3, reauth_queued: 1, reasons: {}},
    {ok: false},
  ]) {
    assert.equal(scan('success', summary), 'Sub2API 异常扫描已完成');
  }
});

test('扫描成功与后续账号修复失败分开呈现', () => {
  assert.equal(scan('success', {
    remote_errors: 1, processed: 3, reauth_queued: 0, reasons: {repair_failed: 1},
  }), 'Sub2API 异常扫描已完成');
});

test('失败扫描保留错误原因，不被摘要里的旧成功字段覆盖', () => {
  assert.equal(scan('failed', {error_code: 'remote_scan_failed'}), 'remote_scan_failed');
  assert.equal(scan('failed', {message: '远端列表读取失败'}), '远端列表读取失败');
  assert.equal(scan('failed', {ok: true}), '扫描未完成，请查看任务日志');
  assert.equal(scan('failed', {}, {
    error_message: '请求失败', error_info: {summary: 'Sub2API 连接超时'},
  }), 'Sub2API 连接超时');
});

test('排队、执行中和已取消的扫描不会显示扫描成功', () => {
  assert.equal(scan('queued', {ok: true}), '等待执行');
  assert.equal(scan('running', {ok: true}), '执行中');
  for (const status of ['cancelled', 'cancelling', 'settling', 'waiting', 'stopped', 'attention_required']) {
    assert.notEqual(scan(status, {ok: true}), 'Sub2API 异常扫描已完成');
  }
});
