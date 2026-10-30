from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from tests.frontend_script_sources import read_account_script


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not shutil.which("node"), reason="需要 Node 验证任务中心交互")
def test_bulk_cancel_reports_actual_states_and_keeps_skipped_selected():
    source = read_account_script("account-tasks.js")
    start = source.index("async function bulkAccountTasks(")
    end = source.index("function updateAccountTaskFilters(", start)
    function_source = source[start:end]
    harness = r"""
const assert = require('node:assert/strict');
const ACCOUNT_TASKS = [
  {id: 11, status: 'queued'}, {id: 12, status: 'queued'},
  {id: 13, status: 'queued'}, {id: 14, status: 'running'},
];
const ACCOUNT_TASK_SELECTED = new Set([11, 12, 13, 14]);
const messages = [], dialogs = [], calls = [];
let renders = 0;
const window = {confirm: () => true, alert: text => dialogs.push(text)};
const document = {getElementById: () => ({disabled: false})};
function accountTaskSelectedRows() { return ACCOUNT_TASKS.filter(task => ACCOUNT_TASK_SELECTED.has(task.id)); }
function accountTaskCanRetry() { return false; }
function accountTaskIsActive() { return true; }
function accountTaskCanTerminate() { return false; }
function updateAccountTaskSelectionUi() {}
function renderAccountTasks() { renders++; }
async function loadAccountTasks() {}
function showToast(text) { messages.push(text); }
async function api(url, options) {
  calls.push({url, body: JSON.parse(options.body)});
  return {accepted_count: 2, skipped_count: 1,
    accepted: [{task_id: 11, state: 'cancelled'}, {task_id: 12, state: 'cancelling'}],
    skipped: [{task_id: 13, error: '任务状态已变化，请刷新后重试'}]};
}
""" + function_source + r"""
(async () => {
  await bulkAccountTasks('cancel');
  assert.deepEqual(calls[0].body, {action: 'cancel', task_ids: [11, 12, 13]});
  assert.match(messages[0], /已取消 1 个/);
  assert.match(messages[0], /取消中 1 个/);
  assert.match(messages[0], /跳过 1 个/);
  assert.match(dialogs[0], /#13/);
  assert.match(dialogs[0], /任务状态已变化，请刷新后重试/);
  assert.deepEqual([...ACCOUNT_TASK_SELECTED], [13, 14]);
  assert.equal(renders, 1);
})().catch(error => { console.error(error); process.exit(1); });
"""
    result = subprocess.run(
        ["node", "--input-type=commonjs", "-e", harness],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout
