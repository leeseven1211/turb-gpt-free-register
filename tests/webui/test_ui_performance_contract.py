import json
import subprocess
import unittest
from pathlib import Path

from webui.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# 任务中心的动作资格、状态展示和请求生命周期由 frontend 的 Vitest 直接 import 验证；
# 此处继续验证尚未迁移的页面和 Flask 资源策略，避免重复启动前端测试。
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
            {"account_batch_workers", "global_task_workers", "account_live_check_driver", "config_revision"},
        )
        self.assertIsInstance(body["account_batch_workers"], int)
        # 4e99e9d 已提供统一预算字段，旧字段仅为同值兼容别名。
        self.assertIsInstance(body["global_task_workers"], int)
        self.assertEqual(body["global_task_workers"], body["account_batch_workers"])
        self.assertNotIn("WEBUI_AUTH_CODE", body)
        self.assertLess(len(json.dumps(body)), 1000)

    def test_static_javascript_has_a_short_browser_cache_policy(self):
        response = self.client.get("/static/js/shared/common.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=300", response.headers.get("Cache-Control", ""))
        response.close()

    def test_common_helpers_dedupe_requests_and_reuse_ready_views(self):
        harness = r'''
const fs = require('fs');
const path = require('path');

const projectRoot = process.argv[1];
const relativePath = 'webui/static/js/shared/common.js';
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
        result = subprocess.run(
            ["node", "tests/registration/vue_migration_contracts.cjs", "batch_counts"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)





    def test_account_ui_hides_actions_for_all_deactivation_projections(self):
        harness = r'''
const fs = require('fs');
const path = require('path');

const projectRoot = process.argv[1];
const relativePath = 'webui/static/js/pages/accounts/page.js';
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
        source = (PROJECT_ROOT / "webui/static/js/pages/config/page.js").read_text(encoding="utf-8")
        self.assertIn("invalidateApiCache('/api/config');", source)


if __name__ == "__main__":
    unittest.main()
