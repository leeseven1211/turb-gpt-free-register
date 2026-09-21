import json
import subprocess
import unittest
from pathlib import Path

from webui.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UiPerformanceContractTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth-code")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth-code"}

    def test_ui_settings_is_small_and_excludes_sensitive_config(self):
        response = self.client.get("/api/ui-settings", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(
            set(body),
            {"account_batch_workers", "account_live_check_driver", "config_revision"},
        )
        self.assertIsInstance(body["account_batch_workers"], int)
        self.assertNotIn("WEBUI_AUTH_CODE", body)
        self.assertLess(len(json.dumps(body)), 1000)

    def test_static_javascript_has_a_short_browser_cache_policy(self):
        response = self.client.get("/static/js/modern/common.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=300", response.headers.get("Cache-Control", ""))
        response.close()

    def test_common_helpers_dedupe_requests_and_reuse_ready_views(self):
        harness = r'''
const fs = require('fs');
const path = require('path');

const projectRoot = process.argv[1];
const relativePath = 'webui/static/js/modern/common.js';
const source = fs.readFileSync(path.join(projectRoot, relativePath), 'utf8');
const start = source.indexOf('const API_INFLIGHT');
const apiStart = source.indexOf('async function api(');
const end = source.indexOf('let CAPABILITIES', apiStart);
if (start < 0 || apiStart < 0 || end < 0) throw new Error(`cache helper block missing: ${relativePath}`);

const declarations = source.split('\n')
  .filter(line => /^(const (API_INFLIGHT|API_CACHE|VIEW_READY|VIEW_REFRESH_MAX_AGE_MS))/.test(line.trim()))
  .join('\n');
const helperBlock = `${declarations}\n${source.slice(apiStart, end)}`;
const runner = `${helperBlock}
let fetchCalls = 0;
global.fetch = async () => {
  fetchCalls += 1;
  return { ok: true, json: async () => ({ fetchCalls }) };
};
(async () => {
  const first = api('/api/same');
  const second = api('/api/same');
  await Promise.all([first, second]);
  if (fetchCalls !== 1) throw new Error('deduplicated GET still hit fetch twice');

  await apiCached('/api/meta', {}, 1000);
  await apiCached('/api/meta', {}, 1000);
  if (fetchCalls !== 2) throw new Error('cached GET did not reuse the response');

  let loadCalls = 0;
  const loader = () => {
    loadCalls += 1;
    markViewReady('menu');
  };
  ensureViewLoaded('menu', loader);
  ensureViewLoaded('menu', loader);
  if (loadCalls !== 1) throw new Error('ready menu was loaded more than once');
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});`;

const result = require('child_process').spawnSync(
  process.execPath,
  ['--input-type=commonjs', '-e', runner, projectRoot],
  { encoding: 'utf8' },
);
if (result.status !== 0) {
  throw new Error(`${relativePath} helper contract failed:\n${result.stdout}\n${result.stderr}`);
}
'''
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness, str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_registration_batch_selector_distinguishes_running_from_waiting(self):
        harness = r'''
const fs = require('fs');
const path = require('path');

const projectRoot = process.argv[1];
const source = fs.readFileSync(
  path.join(projectRoot, 'webui/static/js/modern/jobs.js'),
  'utf8',
);
const start = source.indexOf('function registrationBatchStateLabel(');
const end = source.indexOf('\nfunction ', start + 1);
if (start < 0 || end < 0) throw new Error('registration batch state helper missing');
eval(source.slice(start, end));

const label = registrationBatchStateLabel({
  active: 12,
  running: 2,
  stopping: 0,
  pending: 10,
});
if (label !== '未完成 12（运行 2 / 等待 10）') {
  throw new Error(`unexpected batch state label: ${label}`);
}
'''
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness, str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_center_hides_retry_for_deactivated_tasks_but_allows_unknown_results(self):
        harness = r'''
const fs = require('fs');
const path = require('path');

const projectRoot = process.argv[1];
const source = fs.readFileSync(
  path.join(projectRoot, 'webui/static/js/modern/accounts.js'),
  'utf8',
);
const start = source.indexOf('function accountTaskCanRetry(');
const end = source.indexOf('\nfunction ', start + 1);
if (start < 0 || end < 0) throw new Error('account task retry helper missing');
eval(source.slice(start, end));

if (accountTaskCanRetry({
  status: 'deactivated',
  target_status: 'account_deactivated',
  next_actions: [{action: 'retry'}],
})) {
  throw new Error('deactivated task must not expose retry');
}
if (!accountTaskCanRetry({
  status: 'attention_required',
  target_status: 'attention_required',
  next_actions: [{action: 'reconcile'}],
})) {
  throw new Error('unknown remote result must allow a fresh retry run');
}
if (accountTaskCanRetry({
  status: 'attention_required',
  target_status: 'attention_required',
  result_summary: {requested_status: 'deactivated'},
  next_actions: [{action: 'retry'}],
})) {
  throw new Error('deactivated result summary must not expose retry');
}
'''
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness, str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_account_ui_hides_actions_for_all_deactivation_projections(self):
        harness = r'''
const fs = require('fs');
const path = require('path');

const projectRoot = process.argv[1];
const relativePath = 'webui/static/js/modern/accounts.js';
const source = fs.readFileSync(path.join(projectRoot, relativePath), 'utf8');
const start = source.indexOf('function accountIsDeactivated(');
const end = source.indexOf('\nfunction ', start + 1);
if (start < 0 || end < 0) throw new Error(`account deactivation helper missing: ${relativePath}`);
eval(source.slice(start, end));
for (const key of ['account_status', 'codex_status', 'codex_credential_state']) {
  if (!accountIsDeactivated({[key]: 'deactivated'})) {
    throw new Error(`${relativePath} did not recognize ${key}`);
  }
}
if (accountIsDeactivated({account_status: 'active', codex_status: 'failed'})) {
  throw new Error(`${relativePath} misclassified a retryable account`);
}
'''
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness, str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_config_writes_invalidate_the_cached_config(self):
        source = (PROJECT_ROOT / "webui/static/js/modern/config.js").read_text(encoding="utf-8")
        self.assertIn("invalidateApiCache('/api/config');", source)


if __name__ == "__main__":
    unittest.main()
