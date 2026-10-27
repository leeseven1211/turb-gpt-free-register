# -*- coding: utf-8 -*-
import subprocess
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pyotp
from core import db, record_store
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class DashboardUiScriptTests(unittest.TestCase):
    MODERN_DASHBOARD_JS = Path(__file__).resolve().parents[1] / "webui/static/js/modern/dashboard.js"
    MODERN_COMMON_JS = Path(__file__).resolve().parents[1] / "webui/static/js/modern/common.js"
    MODERN_CODEX_JS = Path(__file__).resolve().parents[1] / "webui/static/js/modern/codex.js"

    def test_compact_account_keeps_registration_driver_without_private_metadata(self):
        from webui.route_helpers import _compact_account_for_list

        compact = _compact_account_for_list({
            "id": 1, "email": "driver@example.test", "registration_driver": "protocol_oss_2",
            "extra_json": '{"account_password":"private-password"}', "access_token": "private-token",
        })
        self.assertEqual(compact["registration_driver"], "protocol_oss_2")
        self.assertNotIn("extra_json", compact)
        self.assertNotIn("access_token", compact)

    def test_dashboard_proxy_platform_labels_follow_current_source_and_keep_legacy_aliases(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        function_source = source[:source.index("function renderDashboard")]
        harness = f"""
const assert = require('node:assert/strict');
function esc(value) {{ return String(value ?? ''); }}
function attrEsc(value) {{ return String(value ?? ''); }}
{function_source}
for (const [platform, label, available] of [
  ['1024proxy', '1024Proxy', true], ['711proxy', '711Proxy', true],
  ['manual', '手动代理池', true], ['1024', '1024Proxy', true],
  ['pool', '静态代理池', true], ['none', '直连', false], ['direct', '直连', false],
]) {{
  const data = {{proxy: {{platform, active_leases: 0, leases: []}}}};
  assert.equal(overviewProxyPlatformLabel(platform), label);
  assert.equal(overviewRegistryCard('panel-proxy').available(data), available);
  assert.ok(overviewRegistryCard('panel-proxy').render(data).includes(label));
  assert.ok(overviewRegistryCard('metric-proxy').render(data).includes(label));
}}
assert.equal(overviewProxyPlatformLabel(' 711PROXY '), '711Proxy');
console.log('ok');
"""
        result = subprocess.run(["node", "--input-type=commonjs", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_dashboard_proxy_summary_displays_at_most_three_exit_leases(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        start = 0
        end = source.index("$('#btnRefreshOverview')", start)
        function_source = source[start:end]
        harness = f"""
const targets = new Map();
function $(selector) {{
  if (!targets.has(selector)) targets.set(selector, {{innerHTML: ''}});
  return targets.get(selector);
}}
function esc(value) {{ return String(value ?? ''); }}
function attrEsc(value) {{ return String(value ?? ''); }}
function pill(status) {{ return String(status); }}
{function_source}
renderDashboard({{
  accounts: {{plans: {{}}}},
  email: {{sources: []}},
  jobs: {{counts: {{}}, today_counts: {{}}}},
  proxy: {{
    platform: '1024',
    active_leases: 4,
    leases: Array.from({{length: 4}}, (_, index) => ({{
      endpoint: `192.0.2.${{index + 1}}:8080`,
      region: 'US',
    }})),
  }},
  codex: {{}},
}});
const exitRows = ($('#overviewPanels').innerHTML.match(/overview-exit-row/g) || []).length;
if (exitRows !== 3) throw new Error(`expected 3 exit rows, got ${{exitRows}}`);
console.log('ok');
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_dashboard_hides_unavailable_cards_and_email_sources(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        start = 0
        end = source.index("$('#btnRefreshOverview')", start)
        function_source = source[start:end]
        harness = f"""
const targets = new Map();
function $(selector) {{
  if (!targets.has(selector)) targets.set(selector, {{innerHTML: '', addEventListener() {{}}}});
  return targets.get(selector);
}}
function esc(value) {{ return String(value ?? ''); }}
function attrEsc(value) {{ return String(value ?? ''); }}
function pill(status) {{ return String(status); }}
let CAPABILITIES = {{
  email_sources: {{
    outlook: {{enabled: false}},
    generic_api: {{enabled: false}},
  }},
  features: {{register: {{enabled: false}}}},
  proxy: {{registration: {{enabled: false}}}},
}};
global.localStorage = {{getItem() {{ return null; }}, setItem() {{}}, removeItem() {{}}}};
{function_source}
renderDashboard({{
  accounts: {{total: 0, active: 0, archived: 0, plans: {{}}}},
  email: {{local_total: 0, local_available: 0, sources: [
    {{source: 'outlook', label: 'Outlook', enabled: false, available: 4}},
    {{source: 'generic_api', label: '通用 API', enabled: true, available: 0}},
  ]}},
  jobs: {{total: 0, counts: {{}}, today_counts: {{}}}},
  proxy: {{platform: 'none', active_leases: 0, leases: []}},
  codex: {{total: 0, pending: 0}},
}});
const allHtml = Array.from(targets.values()).map(item => item.innerHTML).join('\\n');
if (allHtml.includes('Outlook') || allHtml.includes('通用 API')) throw new Error('unavailable email source rendered');
if (allHtml.includes('data-overview-card="panel-email"')) throw new Error('unavailable email card rendered');
if (allHtml.includes('data-overview-card="panel-proxy"')) throw new Error('unconfigured proxy card rendered');
if (allHtml.includes('data-overview-card="metric-codex"')) throw new Error('empty Codex card rendered');
console.log('ok');
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_dashboard_preferences_keep_order_and_remove_unknown_cards(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        start = 0
        end = source.index("function renderDashboard", start)
        function_source = source[start:end]
        harness = f"""
{function_source}
const prefs = normalizeOverviewPreferences({{
  order: {{metrics: ['metric-jobs', 'metric-gone'], panels: ['panel-email']}},
  hidden: ['panel-email', 'panel-gone'],
}}, {{
  metrics: ['metric-accounts', 'metric-jobs'],
  panels: ['panel-email', 'panel-proxy'],
}});
if (JSON.stringify(prefs.order.metrics) !== JSON.stringify(['metric-jobs', 'metric-accounts'])) throw new Error('metric order not normalized');
if (JSON.stringify(prefs.order.panels) !== JSON.stringify(['panel-email', 'panel-proxy'])) throw new Error('panel order not normalized');
if (JSON.stringify(prefs.hidden) !== JSON.stringify(['panel-email'])) throw new Error('hidden cards not normalized');
console.log('ok');
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_overview_card_sizes_are_saved_and_bounded(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        function_source = source[:source.index("function renderDashboard")]
        harness = f"""
function esc(value) {{ return String(value ?? ''); }}
function attrEsc(value) {{ return String(value ?? ''); }}
{function_source}
const available = {{metrics: ['metric-accounts'], panels: ['panel-email', 'panel-proxy']}};
const prefs = normalizeOverviewPreferences({{
  sizes: {{'metric-accounts': 'wide', 'panel-email': 'invalid', 'panel-proxy': 'full', missing: 'full'}},
}}, available);
if (prefs.sizes['metric-accounts'] !== 'wide') throw new Error('metric width lost');
if (prefs.sizes['panel-email'] !== 'normal') throw new Error('invalid width was not reset');
if (prefs.sizes['panel-proxy'] !== 'full') throw new Error('panel width lost');
if ('missing' in prefs.sizes) throw new Error('unknown size retained');
const html = renderOverviewPanel(overviewRegistryCard('panel-email'), {{email: {{sources: [{{source: 'outlook', label: 'Outlook', enabled: true, available: 5}}]}}}}, prefs);
if (!html.includes('data-overview-size="normal"')) throw new Error('normalized width not rendered');
if (!html.includes('data-overview-resize')) throw new Error('resize handle missing');
if (!html.includes('overview-card-drag')) throw new Error('page drag handle missing');
console.log('ok');
"""
        result = subprocess.run(["node", "--input-type=commonjs", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_overview_card_reorder_can_place_card_after_target(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        function_source = source[:source.index("function toggleOverviewCard")]
        harness = f"""
{function_source}
const prefs = {{order: {{metrics: [], panels: ['panel-email', 'panel-proxy', 'panel-jobs', 'panel-accounts']}}}};
reorderOverviewCard(prefs, 'panels', 'panel-email', 'panel-jobs', true);
if (JSON.stringify(prefs.order.panels) !== JSON.stringify(['panel-proxy', 'panel-jobs', 'panel-email', 'panel-accounts'])) throw new Error('card not placed after target');
reorderOverviewCard(prefs, 'panels', 'panel-accounts', 'panel-proxy', false);
if (JSON.stringify(prefs.order.panels) !== JSON.stringify(['panel-accounts', 'panel-proxy', 'panel-jobs', 'panel-email'])) throw new Error('card not placed before target');
console.log('ok');
"""
        result = subprocess.run(["node", "--input-type=commonjs", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_overview_drag_uses_vertical_midpoint_across_grid_rows(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        start = source.index("function overviewPageDropAfter")
        end = source.index("function previewOverviewPageOrder", start)
        function_source = source[start:end]
        harness = f"""
global.getComputedStyle = () => ({{gridTemplateColumns: '100px 100px'}});
{function_source}
const state = {{card: {{getBoundingClientRect: () => ({{left: 0, top: 0, width: 100, height: 100}})}}, grid: {{}}}};
const sameRow = {{dataset: {{overviewSize: 'normal'}}, getBoundingClientRect: () => ({{left: 120, top: 0, width: 100, height: 100}})}};
if (!overviewPageDropAfter(state, sameRow, 180, 10)) throw new Error('same-row target should use horizontal midpoint');
const nextRow = {{dataset: {{overviewSize: 'normal'}}, getBoundingClientRect: () => ({{left: 0, top: 120, width: 100, height: 100}})}};
if (overviewPageDropAfter(state, nextRow, 90, 140)) throw new Error('cross-row target should use vertical midpoint');
if (!overviewPageDropAfter(state, nextRow, 10, 180)) throw new Error('cross-row lower half should insert after');
const full = {{dataset: {{overviewSize: 'full'}}, getBoundingClientRect: () => ({{left: 0, top: 0, width: 220, height: 100}})}};
if (overviewPageDropAfter(state, full, 200, 10)) throw new Error('full-width target should use vertical midpoint');
console.log('ok');
"""
        result = subprocess.run(["node", "--input-type=commonjs", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_overview_exposes_new_aggregate_cards(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        function_source = source[:source.index("$('#btnRefreshOverview')")]
        harness = f"""
const targets = new Map();
function $(selector) {{
  if (!targets.has(selector)) targets.set(selector, {{innerHTML: ''}});
  return targets.get(selector);
}}
function esc(value) {{ return String(value ?? ''); }}
function attrEsc(value) {{ return String(value ?? ''); }}
function pill(status) {{ return String(status); }}
{function_source}
renderDashboard({{
  accounts: {{total: 20, active: 18, archived: 2, codex_ready: 9, plans: {{free: 18}}}},
  email: {{local_available: 5, sources: [{{source: 'outlook', label: 'Outlook', kind: 'local_pool', enabled: true, total: 20, available: 5, used: 12, failed: 2, disabled: 1}}]}},
  jobs: {{total: 30, counts: {{pending: 3, running: 2, stopping: 1, success: 20, failed: 4}}, today_counts: {{success: 4, failed: 1}}}},
  proxy: {{platform: 'none', leases: []}},
  codex: {{total: 12, exported: 7, pending: 5}},
}});
const html = $('#overviewPanels').innerHTML;
for (const id of ['panel-task-queue', 'panel-email-health', 'panel-codex-progress', 'panel-job-history']) {{
  if (!html.includes(`data-overview-card="${{id}}"`)) throw new Error(`${{id}} missing`);
}}
if (!html.includes('待处理') || !html.includes('失败邮箱') || !html.includes('已导出') || !html.includes('累计任务结果')) throw new Error('aggregate values missing');
console.log('ok');
"""
        result = subprocess.run(["node", "--input-type=commonjs", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_overview_data_rich_cards_explain_compact_hidden_rows(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        function_source = source[:source.index("function renderDashboard")]
        harness = f"""
function esc(value) {{ return String(value ?? ''); }}
function attrEsc(value) {{ return String(value ?? ''); }}
function pill(status) {{ return String(status); }}
{function_source}
const email = overviewRegistryCard('panel-email').render({{email: {{sources: [
  {{source: 'outlook', label: 'Outlook', kind: 'local_pool', enabled: true, available: 1}},
  {{source: 'generic_api', label: 'API', kind: 'local_pool', enabled: true, available: 2}},
  {{source: 'icloud_hide', label: 'iCloud', kind: 'local_pool', enabled: true, available: 3}},
  {{source: 'email_butler', label: 'Butler', kind: 'on_demand', enabled: true}},
]}}}});
if (!email.includes('另有 2 个来源')) throw new Error('compact email summary missing');
if (!email.includes('另有 3 个来源')) throw new Error('minimal email summary missing');
const plans = overviewRegistryCard('panel-accounts').render({{accounts: {{plans: {{free: 10, plus: 8, pro: 6, team: 4, go: 2}}}}}});
if (!plans.includes('另有 2 种套餐') || !plans.includes('另有 3 种套餐')) throw new Error('compact plan summaries missing');
console.log('ok');
"""
        result = subprocess.run(["node", "--input-type=commonjs", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_overview_compact_cards_keep_full_counts_and_priority_rows(self):
        source = self.MODERN_DASHBOARD_JS.read_text(encoding="utf-8")
        function_source = source[:source.index("function renderDashboard")]
        harness = f"""
function esc(value) {{ return String(value ?? ''); }}
function attrEsc(value) {{ return String(value ?? ''); }}
function pill(status) {{ return `<span class="pill">${{status}}</span>`; }}
{function_source}
const proxy = overviewRegistryCard('panel-proxy').render({{proxy: {{platform: '1024', active_leases: 4, leases: [
  {{endpoint: 'a'}}, {{endpoint: 'b'}}, {{endpoint: 'c'}}, {{endpoint: 'd'}},
]}}}});
if (!proxy.includes('另有 3 个出口')) throw new Error('compact proxy count must include unrendered leases');
const queue = overviewRegistryCard('panel-task-queue').render({{jobs: {{counts: {{pending: 3, running: 2, stopping: 1}}}}}});
if (!queue.includes('overview-density-secondary"><span>停止中') || !queue.includes('停止中 1')) throw new Error('queue does not compact nonzero secondary status');
const history = overviewRegistryCard('panel-job-history').render({{jobs: {{counts: {{success: 10, failed: 2, partial_success: 3, stopped: 1}}}}}});
if (!history.includes('overview-density-secondary"><span>部分成功') || !history.includes('部分成功 3')) throw new Error('history does not compact nonzero secondary status');
const today = overviewRegistryCard('panel-jobs').render({{jobs: {{today: 'today', today_counts: {{success: 10, partial_success: 3, failed: 2}}}}}});
if (!/overview-density-secondary">\\s*<span class="pill">partial_success/.test(today) || !today.includes('部分成功 3')) throw new Error('today results do not compact partial success');
console.log('ok');
"""
        result = subprocess.run(["node", "--input-type=commonjs", "-e", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_task_error_ui_uses_short_code_and_summary_instead_of_raw_message(self):
        source = self.MODERN_COMMON_JS.read_text(encoding="utf-8")
        start = source.index("function taskErrorBadge")
        end = source.index("function jobsV2OpIcons", start)
        function_source = source[start:end]
        harness = f"""
function esc(value) {{ return String(value ?? '').replace(/[&<>]/g, ''); }}
function attrEsc(value) {{ return String(value ?? ''); }}
function short(value, n=40) {{ const text = String(value || ''); return text.length > n ? text.slice(0, n) + '…' : text; }}
{function_source}
const info = {{display_code: 'AUTH-001', error_code: 'external.openai.credential_expired', source: 'external', title: 'OpenAI / ChatGPT · 授权已失效', summary: '授权已失效，请刷新 AT'}};
const badge = taskErrorBadge(info);
if (!badge.includes('AUTH-001')) throw new Error('short code missing');
if (taskErrorDisplayText(info, 'TokenRefreshReauthRequiredError: long raw detail').includes('TokenRefresh')) throw new Error('raw error leaked');
if (!taskErrorDisplayTitle(info, 'TokenRefreshReauthRequiredError: long raw detail').includes('AUTH-001')) throw new Error('title code missing');
console.log('ok');
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_codex_export_badge_shows_sub2api_link_as_associated(self):
        source = self.MODERN_CODEX_JS.read_text(encoding="utf-8")
        start = source.index("function _codexStatusBadge")
        end = source.index("function _codexOauthBadge", start)
        function_source = source[start:end]
        harness = f"""
function esc(value) {{ return String(value ?? '').replace(/[&<>\"']/g, ''); }}
{function_source}
const badge = _codexStatusBadge({{exported: true, exported_count: 0, sub2api_account_id: 150}});
if (!badge.includes('已关联')) throw new Error('Sub2API-linked badge missing');
if (badge.includes('未导出')) throw new Error('linked credential still shown as unexported');
console.log('ok');
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_codex_resizable_table_uses_fixed_column_layout(self):
        css_path = Path(__file__).resolve().parents[1] / "webui/static/css/ui-foundation.css"
        source = css_path.read_text(encoding="utf-8")
        selector = 'table[data-resizable-table="codex"] {'
        rule_start = source.rindex(selector)
        rule_end = source.index("}", rule_start)

        self.assertIn("table-layout: fixed !important;", source[rule_start:rule_end])


class DashboardApiTests(PostgresTestCase):
    MODERN_COMMON_JS = Path(__file__).resolve().parents[1] / "webui/static/js/modern/common.js"
    MODERN_JOBS_JS = Path(__file__).resolve().parents[1] / "webui/static/js/modern/jobs.js"
    MODERN_ASSETS = (
        "css/modern.css",
        "js/modern/common.js",
        "js/modern/dashboard.js",
        "js/modern/jobs.js",
        "js/modern/accounts.js",
        "js/modern/email.js",
        "js/modern/codex.js",
        "js/modern/config.js",
        "js/modern/bootstrap.js",
    )

    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def _page_source(self, response, assets=()):
        source = response.get_data(as_text=True)
        for asset in assets:
            asset_response = self.client.get(f"/static/{asset}")
            try:
                self.assertEqual(asset_response.status_code, 200, asset)
                source += "\n" + asset_response.get_data(as_text=True)
            finally:
                asset_response.close()
        return source

    def _modern_page_source(self, response):
        return self._page_source(response, self.MODERN_ASSETS)

    def test_modern_facet_select_hides_zero_count_options_and_clears_stale_selection(self):
        source = self.MODERN_COMMON_JS.read_text(encoding="utf-8")
        start = source.index("function syncFacetSelect")
        end = source.index("// ---------- 分页状态 ----------", start)
        function_source = source[start:end]
        harness = f"""
{function_source}
const select = {{
  value: 'gone',
  innerHTML: '',
  closest: () => null,
}};
global.document = {{ getElementById: () => select }};
function attrEsc(value) {{ return String(value ?? ''); }}
function esc(value) {{ return String(value ?? ''); }}
function facetLabel(_group, value) {{ return String(value ?? ''); }}
function refreshColumnFilterState() {{}}
function renderColumnFilterOptions() {{}}
syncFacetSelect('status', [
  {{value: 'active', count: 2}},
  {{value: 'gone', count: 0}},
  {{value: 'pending', count: 1}},
], {{group: 'status', values: ['gone', 'active', 'pending']}});
const hasGoneOption = select.innerHTML.includes('value="gone"');
const hasActiveOption = select.innerHTML.includes('value="active"');
const hasPendingOption = select.innerHTML.includes('value="pending"');
const hasAllOption = select.innerHTML.includes('value=""');
if (hasGoneOption || !hasActiveOption || !hasPendingOption || !hasAllOption || select.value !== '') {{
  throw new Error(JSON.stringify({{hasGoneOption, hasActiveOption, hasPendingOption, hasAllOption, value: select.value}}));
}}
console.log('ok');
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_batch_progress_distinguishes_submitted_password_pending_confirmation(self):
        source = self.MODERN_JOBS_JS.read_text(encoding="utf-8")
        start = source.index("function progressJobResult")
        end = source.index("function refreshBatchProgressDurations", start)
        function_source = source[start:end]
        harness = f"""
{function_source}
const result = progressJobResult({{
  status: 'partial_success',
  display_status: 'password_confirmation_pending',
}});
if (result.label !== '待确认 · 密码已提交' || result.cls !== 'is-failed') {{
  throw new Error(JSON.stringify(result));
}}
console.log('ok');
"""
        result = subprocess.run(
            ["node", "--input-type=commonjs", "-e", harness],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_frontend_static_assets_are_referenced_and_served(self):
        assets = self.MODERN_ASSETS + (
            "css/ui-foundation.css",
            "css/login.css",
            "js/proxy_traffic.js",
            "js/login.js",
        )
        for asset in assets:
            response = self.client.get(f"/static/{asset}")
            try:
                self.assertEqual(response.status_code, 200, asset)
            finally:
                response.close()

        modern = self.client.get("/", headers=self.headers).get_data(as_text=True)
        login = self.client.get("/login").get_data(as_text=True)
        self.assertIn("/static/js/modern/common.js", modern)
        self.assertIn("/static/js/proxy_traffic.js", modern)
        self.assertIn("/static/js/login.js", login)

    def test_previous_ui_preferences_open_the_current_interface(self):
        self.client.set_cookie("ui_mode", "legacy")
        for path in ("/", "/?ui=legacy", "/?ui=modern"):
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('class="app-sidebar"', html)
                self.assertIn("/static/js/modern/common.js", html)
                self.assertNotIn("/static/js/legacy/", html)
                self.assertNotIn("ui_mode=", " ".join(response.headers.getlist("Set-Cookie")))

    def _local_profile(self):
        from core.storage.email_address_allocations import create_inbox_profile
        return create_inbox_profile(inbox_key='dashboard-fixture', connector='forward_butler',
            credential_ref='DASHBOARD_FIXTURE_KEY', inbox_locator={
                'api_base': 'https://butler.test/v1', 'mailbox_email': 'final@example.test'})['id']

    @patch("core.proxy_pool.pool_source", return_value="1024proxy")
    @patch("core.proxy_provider.active_proxy_leases", return_value=[{"provider": "1024proxy", "endpoint": "1.2.*.*:80"}])
    @patch("webui.app.admin_repository.dashboard_aggregates", return_value={
        "accounts": {"total": 3, "active": 2, "archived": 1, "codex_ready": 1,
                     "plans": {"free": 1, "free_trial_eligible": 1}},
        "jobs": {"total": 2, "counts": {"success": 1, "partial_success": 1},
                 "today_counts": {"success": 1, "partial_success": 1}},
        "email_status_rows": [
            {"source": "outlook", "status": "available", "count": 4},
            {"source": "outlook", "status": "used", "count": 1},
            {"source": "generic_api", "status": "available", "count": 2},
            {"source": "cloudflare_domain", "status": "available", "count": 2},
            {"source": "cloudflare_domain", "status": "used", "count": 1},
            {"source": "icloud_hide", "status": "available", "count": 3},
            {"source": "icloud_hide", "status": "used", "count": 1},
        ],
        "codex": {"total": 2, "exported": 1, "pending": 1},
    })
    def test_dashboard_returns_aggregates_without_account_secrets(self, *_mocks):
        for spec, count in ((record_store.OUTLOOK_POOL, 4), (record_store.GENERIC_API_POOL, 2),
                            (record_store.DOMAIN_POOL, 2), (record_store.ICLOUD_HIDE_POOL, 3)):
            for index in range(count):
                record_store.insert_row(spec, {'email': f'{spec.name}-{index}@example.test', 'status': 'available', 'derivation_policy': {'inbox_profile_id': self._local_profile()}})
        for source in ("1024proxy", "711proxy", "manual"):
            with self.subTest(source=source):
                # 切换来源后旧租约仍可存续，总览平台必须使用当前池来源。
                _mocks[-1].return_value = source
                response = self.client.get("/api/dashboard", headers=self.headers)
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertEqual(payload["accounts"]["total"], 3)
                self.assertEqual(payload["accounts"]["active"], 2)
                self.assertEqual(payload["accounts"]["plans"], {"free": 1, "free_trial_eligible": 1})
                self.assertEqual(payload["email"]["local_available"], 11)
                self.assertEqual(payload["jobs"]["today_counts"], {"success": 1, "partial_success": 1, "failed": 0})
                self.assertEqual(payload["proxy"]["active_leases"], 1)
                self.assertEqual(payload["proxy"]["platform"], source)
                self.assertNotIn("access_token", str(payload))
                self.assertNotIn("api_key", str(payload).lower())

    @patch("webui.routes.dashboard.admin_repository.dashboard_aggregates", return_value={
        "accounts": {"total": 0, "active": 0, "archived": 0, "codex_ready": 0, "plans": {}},
        "jobs": {"total": 0, "counts": {}, "today_counts": {}},
        "email_status_rows": [
            {"source": "outlook", "status": "disabled", "count": 2},
            {"source": "icloud_hide", "status": "available", "count": 1},
        ],
        "codex": {},
    })
    @patch("core.proxy_provider.active_proxy_leases", return_value=[])
    @patch("core.proxy_pool.pool_source", return_value="manual")
    def test_dashboard_email_sources_include_visibility_and_forward_butler_dependency(
        self, *_mocks
    ):
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, {'email': 'local@icloud.com', 'status': 'available', 'derivation_policy': {'inbox_profile_id': self._local_profile()}})
        record_store.insert_row(record_store.OUTLOOK_POOL, {'email': 'disabled@example.test', 'status': 'disabled'})
        with patch("config.email.USE_EMAIL_SERVICE", True), patch("config.email.EMAIL_SOURCE", "icloud_hide"), patch(
            "config.email.ICLOUD_HME_INBOX_MODE", "forward_butler"
        ):
            response = self.client.get("/api/dashboard", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        sources = {item["source"]: item for item in response.get_json()["email"]["sources"]}

        self.assertTrue(sources["icloud_hide"]["enabled"])
        self.assertTrue(sources["icloud_hide"]["default_visible"])
        self.assertTrue(sources["outlook"]["history_available"])
        self.assertTrue(sources["outlook"]["default_visible"])
        self.assertFalse(sources["email_butler"]["enabled"])
        self.assertFalse(sources["email_butler"]["dependency"])
        self.assertFalse(sources["email_butler"]["default_visible"])
        self.assertNotIn("gptmail", sources)

    @patch("webui.routes.dashboard.admin_repository.dashboard_aggregates", return_value={
        "accounts": {"total": 0, "active": 0, "archived": 0, "codex_ready": 0, "plans": {}},
        "jobs": {"total": 0, "counts": {}, "today_counts": {}},
        "email_status_rows": [
            {"source": "outlook", "status": "available", "count": 2},
        ],
        "codex": {},
    })
    @patch("core.proxy_provider.active_proxy_leases", return_value=[])
    @patch("core.proxy_pool.pool_source", return_value="manual")
    def test_dashboard_manual_mode_with_explicit_empty_source_has_no_enabled_source(
        self, *_mocks
    ):
        with patch("config.email.EMAIL_SOURCE", ""), patch(
            "config.email.USE_EMAIL_SERVICE", False
        ):
            response = self.client.get("/api/dashboard", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["email"]
        self.assertEqual(payload["enabled_count"], 0)
        self.assertTrue(all(not item["enabled"] for item in payload["sources"]))
        self.assertTrue(all(not item["default_visible"] for item in payload["sources"]))

    def test_jobs_status_filter_keeps_global_counts(self):
        self.seed(record_store.JOBS, [
            {"job_uuid": "j3", "status": "success"},
            {"job_uuid": "j2", "status": "failed"},
            {"job_uuid": "j1", "status": "failed"},
        ])
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&status=failed",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 2)
        self.assertTrue(all(item["status"] == "failed" for item in payload["items"]))
        self.assertEqual(payload["status_counts"], {"success": 1, "failed": 2, "active": 0})
        self.assertEqual({item["value"] for item in payload["facets"]["status"]}, {"success", "failed"})

    def test_jobs_query_and_email_source_filters(self):
        self.seed(record_store.JOBS, [
            {"job_uuid": "j3", "status": "failed", "email": "target@example.com", "email_source": "email_butler"},
            {"job_uuid": "j2", "status": "success", "email": "other@example.com", "email_source": "email_butler"},
            {"job_uuid": "j1", "status": "failed", "email": "target@elsewhere.com", "email_source": "outlook"},
        ])
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&q=target&email_source=email_butler",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "target@example.com")
        self.assertEqual(payload["status_counts"], {"failed": 1, "active": 0})

    def test_jobs_date_range_filter(self):
        self.seed(record_store.JOBS, [
            {"job_uuid": "j3", "status": "success", "created_at": "2026-08-11T10:00:00"},
            {"job_uuid": "j2", "status": "failed", "created_at": "2026-08-10T10:00:00"},
        ])
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&date_from=2026-08-11&date_to=2026-08-11",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["status"], "success")

    def test_jobs_column_filters_can_be_combined(self):
        self.seed(record_store.JOBS, [
            {"id": 31, "job_uuid": "j31", "status": "failed", "email": "target@example.com", "proxy_provider": "1024proxy", "proxy_region": "JP", "error_message": "OTP timeout"},
            {"id": 32, "job_uuid": "j32", "status": "failed", "email": "other@example.com", "proxy_provider": "1024proxy", "proxy_region": "US", "error_message": "browser timeout"},
        ])
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&id=31&email=target&proxy=jp&error=otp",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], 31)

    def test_modern_ui_contains_overview_and_no_external_sidebar_links(self):
        response = self.client.get("/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        html = self._modern_page_source(response)
        self.assertIn('id="tab-overview"', html)
        self.assertIn('class="accounts-command-deck"', html)
        self.assertIn('id="butlerImportPanel"', html)
        self.assertIn('data-module-subnav="register"', html)
        self.assertIn('data-sidebar-module="register"', html)
        self.assertIn('data-sidebar-module="accounts"', html)
        self.assertNotIn('data-module-subnav="codex"', html)
        self.assertNotIn('data-view="sub2"', html)
        self.assertIn('data-module-subnav="outlook"', html)
        self.assertNotIn('<nav class="module-subnav"', html)
        self.assertIn("$$('[data-module-subnav]').forEach", html)
        self.assertIn('id="btnCodexUploadSub2V2"', html)
        self.assertIn('id="btnAddPasswordSelectedAccountsV2"', html)
        self.assertIn('id="btnAddTwofaSelectedAccountsV2"', html)
        self.assertIn('id="btnCompleteSelectedAccountsV2"', html)
        self.assertIn('>刷新 AT</button>', html)
        self.assertIn('>查封号邮件</button>', html)
        self.assertIn('>补 Codex</button>', html)
        self.assertIn('>复制 Token</button>', html)
        self.assertNotIn('id="btnOpenAccountCompletionConfigTopV2"', html)
        self.assertNotIn('>补全规则</button>', html)
        self.assertNotIn('>补全配置</button>', html)
        self.assertNotIn('旧版补齐配置', html)
        self.assertIn("'注册与账号': '注册主链路'", html)
        self.assertIn("'执行方式': '注册主链路'", html)
        self.assertNotIn('data-lifecycle-section-v2', html)
        self.assertNotIn('renderLifecycleDriverSelect', html)
        self.assertIn('config-setting-row-v2', html)
        self.assertIn("'注册与账号': ['注册主链路', '账号补全', '注册与账号']", html)
        self.assertIn("'系统与维护': ['通用配置', 'WebUI 授权', '定时任务', '任务中心', '注册调试']", html)
        self.assertIn('注册调试', html)
        operation_start = html.index('>操作</span>')
        deactivation_mail = html.index('>查封号邮件</button>')
        copy_export = html.index('>复制与导出</span>')
        self.assertLess(operation_start, deactivation_mail)
        self.assertLess(deactivation_mail, copy_export)
        self.assertIn("/api/accounts/setup-bulk", html)
        self.assertIn("syncFacetSelect('accountPlanFilterV2'", html)
        self.assertIn("syncFacetSelect('codexStatusFilterV2'", html)
        self.assertIn("syncFacetSelect('codexOauthFilterV2'", html)
        self.assertIn("syncFacetSelect('outlookStatusFilterV2'", html)
        self.assertNotIn('id="codexFilterV2"', html)
        self.assertNotIn('id="accountsFilterV2"', html)
        self.assertIn('id="outlookToolbarV2"', html)
        self.assertEqual(html.count('data-column-filter="'), 53)
        self.assertIn('class="column-filter-trigger"', html)
        self.assertIn('class="column-filter-search"', html)
        self.assertIn('data-column-filter-options', html)
        self.assertIn('class="column-filter-native" hidden', html)
        self.assertIn('data-filter-summary="accounts"', html)
        self.assertIn('data-filter-end-id="dateToAccountsV2"', html)
        self.assertIn('select.innerHTML = options.map(item => `<option value="${attrEsc(item.value)}">', html)
        self.assertNotIn('select.innerHTML = options.map(item => `<option value="${esc(item.value)}">', html)
        self.assertNotIn('class="list-column-filters"', html)
        self.assertIn('data-column-filter="accountPlanFilterV2"', html)
        self.assertIn("syncFacetSelect('accountTrialFilterV2'", html)
        self.assertIn('data-column-filter="accountTrialFilterV2"', html)
        self.assertIn('>套餐优惠</th>', html)
        self.assertIn('data-filter-label="按 Plus 优惠类型筛选"', html)
        self.assertIn('data-account-more-id="${esc(r.id)}"', html)
        self.assertIn('function restoreAccountsV2MoreMenu(accountId)', html)
        self.assertNotIn('data-column-filter="accountNoteFilterV2"', html)
        self.assertNotIn('>备注</th>', html)
        self.assertIn('data-column-filter="codexStatusFilterV2"', html)
        self.assertIn('data-column-filter="codexSub2apiIdFilterV2"', html)
        self.assertIn("sub2api_id", html)
        self.assertIn('data-column-filter="outlookStatusFilterV2"', html)
        self.assertNotIn('id="configOverviewV2"', html)
        self.assertIn("activateTab(localStorage.getItem('gpt_console_active_tab') || 'overview', false)", html)
        self.assertIn('data-column-filter="jobDateFromV2"', html)
        self.assertIn('id="btnResetJobFiltersV2"', html)
        self.assertIn('id="btnBatchStopV2"', html)
        self.assertIn('id="btnBatchCancelV2"', html)
        self.assertIn('id="btnBatchRetryV2"', html)
        self.assertIn('id="registrationBatchSelectV2"', html)
        self.assertIn('progress_batch_id=${encodeURIComponent(JOB_PROGRESS_BATCH_ID)}', html)
        self.assertIn('id="accountTaskStageProgress"', html)
        self.assertIn('function renderAccountTaskStageProgress(task, selectedRunId = null)', html)
        self.assertIn('/runs/${encodeURIComponent(activeAccountTaskRunId)}/progress', html)
        self.assertIn('function renderAccountTaskProgressSnapshot(progress)', html)
        self.assertNotIn('observed.forEach((value, key)', html)
        self.assertNotIn("legacyRegistration && !observed.has('network')", html)
        self.assertIn("skipped:'已跳过'", html)
        self.assertNotIn("stage.seen ? 'success'", html)
        self.assertIn('data-progress-retry-job', html)
        self.assertIn('batch-progress-v2-step-duration', html)
        self.assertIn('data-progress-duration-start', html)
        modern_css = (Path(__file__).resolve().parents[1] / 'webui/static/css/modern.css').read_text(encoding='utf-8')
        self.assertIn('grid-template-columns:repeat(var(--batch-progress-step-count),minmax(0,1fr));', modern_css)
        jobs_js = (Path(__file__).resolve().parents[1] / 'webui/static/js/modern/jobs.js').read_text(encoding='utf-8')
        self.assertIn('style="--batch-progress-step-count:${Math.max(displayStages.length, 1)}"', jobs_js)
        self.assertNotIn('repeat(11, minmax(74px, 1fr))', html)
        self.assertIn('batchProgressRenderSignature', html)
        self.assertIn('currentBatchJobs().find', html)
        self.assertNotIn('batch-progress-v2-error', html)
        self.assertNotIn('class="jobs-column-filters"', html)
        self.assertIn('data-column-filter="jobStatusColumnFilterV2"', html)
        self.assertIn('data-filter-summary="accountTasks"', html)
        self.assertIn('data-column-filter="accountTaskTargetFilterV2"', html)
        self.assertIn('data-column-filter="accountTaskTargetStatusFilterV2"', html)
        self.assertIn('id="btnResetAccountTaskFiltersV2"', html)
        self.assertNotIn('id="accountTaskSearch"', html)
        self.assertNotIn('id="qJobsV2"', html)
        self.assertNotIn("Automation queue", html)
        self.assertIn(".accounts-command-deck {\n      position: relative; top: auto;", html)
        self.assertNotIn("TG 交流群", html)
        self.assertNotIn("切换老 UI", html)

    @patch("webui.runtime.account_task_store.start_dispatcher")
    @patch("webui.runtime.account_task_store.submit_durable_operation", return_value={
        "accepted": True,
        "busy": False,
        "reused": False,
        "task_id": 901,
        "run_id": 902,
        "status": "queued",
        "source_system": "webui_runtime",
        "source_id": "account-setup:1:test",
    })
    @patch("webui.app.db.get_account", return_value={
        "id": 1,
        "email": "setup@example.com",
        "account_status": "active",
    })
    def test_account_setup_endpoint_queues_configuration_without_codex(self, _get_account, submit, start_dispatcher):
        response = self.client.post("/api/accounts/1/setup", headers=self.headers, json={})
        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_id"], 901)
        self.assertEqual(submit.call_args.kwargs["task_type"], "account_setup_retry")
        self.assertEqual(submit.call_args.kwargs["trigger"], "manual_account_setup")
        self.assertEqual(submit.call_args.kwargs["source_system"], "webui_runtime")
        self.assertEqual(submit.call_args.kwargs["data"]["steps"], ["password", "plan_check", "twofa"])
        start_dispatcher.assert_not_called()

    def test_modern_ui_polling_avoids_overlapping_requests_and_duplicate_summary_refresh(self):
        response = self.client.get("/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        html = self._modern_page_source(response)
        self.assertIn("if (summaryLoading) return;", html)
        self.assertIn("if (dashboardLoading) return;", html)
        # 注册批次的请求去重与旧响应隔离由 Node 行为回归覆盖，切换批次允许立即发起新请求。
        self.assertIn("if (outlookLoading) { outlookReloadQueued = true; return; }", html)
        self.assertIn("if (codexLoading) { codexReloadQueued = true; return; }", html)
        self.assertIn("if (accountTasksLoading) {", html)
        self.assertIn("accountTasksReloadQueued = true;", html)
        self.assertNotIn("    loadSummary();\n  } catch(e) {}\n}", html)
        self.assertIn("}, 10000);", html)
        self.assertIn("}, 5000);", html)
        self.assertIn("!document.hidden", html)

    def test_all_list_actions_remain_available_with_resizable_columns(self):
        response = self.client.get("/", headers=self.headers)
        html = self._modern_page_source(response)
        action_ids = {
            # 任务记录
            "btnRetrySelectedJobsV2", "btnDeleteSelectedJobsV2", "btnCancelPendingV2", "btnRefreshJobsV2",
            # 账号
            "btnCheckSelectedLiveV2", "btnRefreshSelectedTokenV2", "btnCheckSelectedPlansV2", "btnExtractSelectedLinksV2",
            "btnRetrySelectedCodexV2", "btnDownloadSelectedCpaV2", "btnUploadSelectedCodexSub2V2",
            "btnStopSelectedCodexV2", "btnCheckSelectedDeactivationMailV2",
            "btnCopySelectedTokensV2", "btnCopySelectedLinesV2", "btnCopySelectedEmailsV2", "btnCopySelectedPasswordsV2", "btnCopySelectedTotpsV2", "btnDownloadSelectedTxtV2",
            "btnArchiveSelectedAccountsV2", "btnDeleteSelectedAccountsV2", "btnRefreshAccountsV2",
            # Codex 凭证
            "btnCodexReauthorizeBulkV2", "btnCodexDownloadBulkV2", "btnCodexDownloadBulkCpaV2", "btnCodexUploadSub2V2",
            "btnCodexRefreshTokenBulkV2", "btnCodexArchiveBulkV2", "btnCodexDeleteBulkV2", "btnRefreshCodexV2",
            # 邮箱池
            "btnMarkSelectedOutlookAvailableV2", "btnDisableSelectedOutlookV2",
            "btnFailSelectedOutlookV2", "btnDeleteSelectedOutlookV2", "copyAllEmailsV2",
            "btnImportOutlookV2", "btnRefreshOutlookV2",
        }
        for action_id in action_ids:
            self.assertIn(f'id="{action_id}"', html, action_id)
        self.assertIn("bind('btnRefreshSelectedTokenV2', () => refreshSelectedToken());", html)
        self.assertIn("bind('btnCopySelectedTotpsV2', copySelectedAccountTotpSecrets);", html)
        self.assertIn("fetchAccountSecrets(ids, 'totp_secret')", html)
        for table_name in ("jobs", "accounts", "codex", "outlook"):
            self.assertIn(f'data-resizable-table="{table_name}"', html)
            reset_id = f"btnReset{table_name.capitalize()}ColumnsV2"
            self.assertIn(f'id="{reset_id}"', html)
        self.assertGreaterEqual(html.count("list-action-toolbar"), 4)
        self.assertNotIn('id="codexBulkWorkersV2"', html)
        self.assertNotIn('id="codexStatsV2"', html)
        self.assertNotIn('id="codexStatTotalV2"', html)
        self.assertNotIn('id="codexStatExportedV2"', html)
        self.assertNotIn('id="codexStatPendingV2"', html)
        self.assertNotIn('class="codex-sync-callout"', html)
        self.assertNotIn('id="btnCodexUploadSub2HeroV2"', html)
        self.assertIn('id="btnCodexUploadSub2V2"', html)
        self.assertIn('data-codex-reauthorize="${esc(r.filename)}"', html)
        self.assertIn("if (status === 'queued') return '等待执行';", html)
        self.assertIn("if (status === 'running') return '执行中';", html)
        self.assertIn(">重试</button>", html)
        self.assertIn(">删除</button>", html)
        self.assertIn(">取消</button>", html)

    def test_codex_resizable_defaults_match_all_table_columns(self):
        response = self.client.get("/", headers=self.headers)
        source = self._modern_page_source(response)
        common_source = self.client.get("/static/js/modern/common.js").get_data(as_text=True)
        defaults_start = common_source.index("[", common_source.index("codex:    [")) + 1
        defaults_end = common_source.index("]", defaults_start)
        default_count = len([item for item in common_source[defaults_start:defaults_end].split(",") if item.strip()])
        table_start = source.index('<table class="codex-table-v2"')
        colgroup_end = source.index("</colgroup>", table_start)
        column_count = source[table_start:colgroup_end].count("<col ")
        self.assertEqual(default_count, column_count)

    def test_task_center_uses_shared_resizable_table_layout(self):
        response = self.client.get("/", headers=self.headers)
        source = self._modern_page_source(response)

        self.assertIn('data-resizable-table="accountTasks"', source)
        self.assertIn('id="btnResetAccountTaskColumnsV2"', source)
        self.assertIn('table[data-resizable-table="accountTasks"] {', source)
        self.assertIn('width: max(100%, 1240px) !important;', source)
        self.assertIn('min-width: 1240px !important;', source)
        self.assertIn("if (header.classList.contains('col-check') || (key !== 'accounts' && index >= headers.length - 1)) return;", source)
        self.assertIn("header.classList.contains('task-col-id')", source)
        self.assertIn("headers[nextIndex].classList.contains('task-col-actions')", source)

    def test_task_center_exposes_safe_bulk_actions_and_shared_chinese_labels(self):
        response = self.client.get("/", headers=self.headers)
        source = self._modern_page_source(response)

        self.assertIn('id="accountTasksSelectAllV2"', source)
        self.assertIn('class="task-col-check col-check"', source)
        for action_id in (
            "btnRetrySelectedAccountTasksV2",
            "btnCancelSelectedAccountTasksV2",
            "btnTerminateSelectedAccountTasksV2",
        ):
            self.assertIn(f'id="{action_id}"', source)
        self.assertIn("const ACCOUNT_TASK_SELECTED = new Set();", source)
        self.assertIn("/api/operations/bulk", source)
        self.assertIn("function bulkAccountTasks", source)
        self.assertIn("facetLabel('task_type'", source)
        self.assertIn("pillV2(task.target_status, 'target_status')", source)
        self.assertIn("renderTableStateRow(12, '任务记录加载失败'", source)
        self.assertIn("['queued','running','stopping','cancelling','settling','waiting']", source)
        self.assertIn("password_change:'修改密码'", source)
        self.assertIn("twofa_change:'修改 2FA'", source)

    def test_task_center_auto_expands_only_unsaved_columns_and_filter_popovers(self):
        source = self._modern_page_source(self.client.get("/", headers=self.headers))

        self.assertIn("function autoSizeResizableTableColumns", source)
        self.assertIn("readSavedTableWidths(key, cols.length)", source)
        self.assertIn("columnFilterOptionWidth", source)
        self.assertIn("table.dataset.autoSized", source)
        self.assertLess(
            source.index("renderColumnFilterOptions(document.getElementById(header.dataset.columnFilter))"),
            source.index("positionColumnFilterPopover(header)", source.index("renderColumnFilterOptions(document.getElementById(header.dataset.columnFilter))")),
        )
        self.assertIn("accountTaskRequestId", source)
        self.assertIn("accountTasksReloadQueued", source)

    def test_navigation_avoids_unnecessary_vertical_scrolling(self):
        response = self.client.get("/", headers=self.headers)
        html = self._modern_page_source(response)
        self.assertIn("min-height: 0; padding-left: var(--sidebar-width);", html)
        self.assertIn("overscroll-behavior-y: contain;", html)
        self.assertIn("#tab-config .config-nav-v2-item { min-height: 32px; padding: 6px 10px; }", html)
        self.assertIn("var(--page-gutter) 28px;", html)
        self.assertIn("function containVerticalScroll(el)", html)
        self.assertIn("event.preventDefault();", html)

    def test_accounts_column_filters_are_combined(self):
        self.seed(record_store.ACCOUNTS, [
            {"email": "target@example.com", "email_source": "outlook", "access_token": "token", "totp_secret": "JBSWY3DPEHPK3PXP", "codex_status": "success", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_promo_kind": "free_trial", "plus_trial_eligible": True, "quota_status": "success", "quota_type": "月限额", "quota_windows": [{"kind": "monthly", "label": "月限额", "used_percent": 25, "remaining_percent": 75}], "extra_json": '{"account_password":"Account123!abcd"}'},
            {"email": "other@example.com", "email_source": "icloud_hide", "access_token": "", "totp_enabled": False, "codex_status": "failed", "plan_type": "plus", "current_plan_type": "plus"},
        ])
        response = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&email=target&source=outlook&token=has&password=has&promotion=free_trial&totp=enabled&codex=success",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "target@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["source"]}, {"outlook", "icloud_hide"})
        self.assertEqual({item["value"] for item in payload["facets"]["codex"]}, {"success", "failed"})
        self.assertEqual({item["value"] for item in payload["facets"]["password"]}, {"has", "none"})
        self.assertEqual({item["value"] for item in payload["facets"]["promotion"]}, {"free_trial", "not_applicable"})
        self.assertTrue(payload["items"][0]["has_account_password"])
        self.assertTrue(payload["items"][0]["totp_enabled"])
        self.assertEqual(payload["items"][0]["quota_type"], "月限额")
        self.assertEqual(payload["items"][0]["quota_windows"][0]["remaining_percent"], 75)
        status_response = self.client.get(
            "/api/accounts/plan-check-status?page=1&page_size=20",
            headers=self.headers,
        )
        status_payload = status_response.get_json()
        status_item = next(item for item in status_payload["items"] if item["email"] == "target@example.com")
        self.assertEqual(status_item["quota_type"], "月限额")

    def test_accounts_promotion_filter_distinguishes_trial_discount_and_history(self):
        self.seed(record_store.ACCOUNTS, [
            {"email": "eligible@example.com", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_promo_kind": "free_trial", "plus_trial_eligible": True},
            {"email": "half-price@example.com", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_promo_kind": "discount", "plus_promo_discount_percentage": 50, "plus_trial_eligible": False},
            {"email": "discount@example.com", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_promo_kind": "discount", "plus_promo_discount_percentage": 20, "plus_trial_eligible": False},
            {"email": "history@example.com", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_trial_eligible": True},
            {"email": "used@example.com", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_trial_eligible": False},
            {"email": "plus@example.com", "plan_type": "plus", "current_plan_type": "plus"},
        ])
        response = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&promotion=half_price",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "half-price@example.com")
        self.assertEqual(payload["items"][0]["plus_promo_kind"], "discount")
        self.assertFalse(payload["items"][0]["plus_trial_eligible"])
        self.assertEqual(
            {item["value"] for item in payload["facets"]["promotion"]},
            {"free_trial", "half_price", "other_discount", "unknown", "none", "not_applicable"},
        )

        other_discount = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&promotion=other_discount",
            headers=self.headers,
        ).get_json()
        self.assertEqual(other_discount["total"], 1)
        self.assertEqual(other_discount["items"][0]["email"], "discount@example.com")

        all_discounts = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&promotion=discount",
            headers=self.headers,
        ).get_json()
        self.assertEqual(all_discounts["total"], 2)

        status = self.client.get(
            "/api/accounts/plan-check-status?page=1&page_size=20&promotion=half_price",
            headers=self.headers,
        ).get_json()
        self.assertEqual(status["total"], 1)
        self.assertEqual(status["items"][0]["email"], "half-price@example.com")

    def test_accounts_token_filter_distinguishes_valid_expired_and_missing(self):
        self.seed(record_store.ACCOUNTS, [
            {
                "email": "valid@example.com",
                "access_token": "valid-token",
                "token_expires_at": "2099-01-01T00:00:00Z",
                "token_expired": False,
            },
            {
                "email": "expired-by-time@example.com",
                "access_token": "expired-token",
                "token_expires_at": "2000-01-01T00:00:00Z",
                "token_expired": False,
            },
            {
                "email": "expired-by-flag@example.com",
                "access_token": "rejected-token",
                "token_expires_at": "2099-01-01T00:00:00Z",
                "token_expired": True,
            },
            {
                "email": "invalid-401@example.com",
                "access_token": "rejected-401-token",
                "token_expires_at": "2099-01-01T00:00:00Z",
                "live_check_status": "failed",
                "live_check_http_status": 401,
            },
            {
                "email": "invalid-403@example.com",
                "access_token": "rejected-403-token",
                "token_expires_at": "2000-01-01T00:00:00Z",
                "token_expired": True,
                "live_check_status": "failed",
                "live_check_http_status": 403,
            },
            {
                "email": "invalid-other@example.com",
                "access_token": "rejected-other-token",
                "token_expires_at": "2099-01-01T00:00:00Z",
                "live_check_status": "failed",
                "live_check_http_status": 429,
            },
            {"email": "missing@example.com", "access_token": ""},
        ])

        expected = {
            "has": {"valid@example.com"},
            "expired": {"expired-by-time@example.com", "expired-by-flag@example.com"},
            "invalid_401": {"invalid-401@example.com"},
            "invalid_403": {"invalid-403@example.com"},
            "invalid_other": {"invalid-other@example.com"},
            "none": {"missing@example.com"},
        }
        for token_filter, emails in expected.items():
            with self.subTest(token_filter=token_filter):
                response = self.client.get(
                    f"/api/accounts?paged=1&page=1&page_size=20&token={token_filter}",
                    headers=self.headers,
                )
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertEqual(payload["total"], len(emails))
                self.assertEqual({item["email"] for item in payload["items"]}, emails)
                self.assertEqual(
                    {item["value"]: item["count"] for item in payload["facets"]["token"]},
                    {
                        "has": 1,
                        "expired": 2,
                        "invalid_401": 1,
                        "invalid_403": 1,
                        "invalid_other": 1,
                        "none": 1,
                    },
                )

    @patch("webui.app.db.get_account", return_value={
        "id": 1,
        "email": "target@example.com",
        "extra_json": '{"account_password":"Account123!abcd"}',
    })
    def test_account_password_is_only_returned_by_secret_endpoint(self, _get_account):
        response = self.client.get(
            "/api/accounts/1/secret?field=account_password",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["value"], "Account123!abcd")

    @patch("webui.routes.accounts.db.get_account_chatgpt_session", return_value={
        "accessToken": "session-at",
        "user": {"email": "target@example.com"},
    })
    @patch("webui.routes.accounts.db.get_account", return_value={
        "id": 1,
        "email": "target@example.com",
    })
    def test_chatgpt_session_is_returned_as_formatted_json_by_secret_endpoint(
        self, _get_account, _get_session
    ):
        response = self.client.get(
            "/api/accounts/1/secret?field=chatgpt_session",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["value"],
            '{\n  "accessToken": "session-at",\n  "user": {\n    "email": "target@example.com"\n  }\n}',
        )
        _get_session.assert_called_once_with(1)

    def test_account_copy_line_includes_openai_password_and_totp_secret(self):
        self.seed(record_store.ACCOUNTS, [
            {
                "email": "target@example.com",
                "original_email_line": "mail@example.com----mail-password----client-id----refresh-token",
                "access_token": "access-token",
                "totp_secret": "JBSWY3DPEHPK3PXP",
                "extra_json": '{"account_password":"Account123!abcd"}',
            },
        ])

        response = self.client.get(
            "/api/accounts/1/secret?field=copy_line",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["value"],
            "mail@example.com----mail-password----client-id----refresh-token"
            "----access-token----Account123!abcd----JBSWY3DPEHPK3PXP",
        )

    @patch("webui.app.db.get_account", return_value={
        "id": 1,
        "email": "target@example.com",
        "extra_json": (
            '{"registration_password":"Signup123!",'
            '"login_password":"Login456!"}'
        ),
    })
    def test_legacy_password_fields_are_read_as_one_account_password(self, _get_account):
        response = self.client.get(
            "/api/accounts/1/secret?field=account_password",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["value"], "Login456!")

    @patch("webui.app.db.get_account", return_value={
        "id": 1,
        "email": "target@example.com",
        "totp_secret": "JBSWY3DPEHPK3PXP",
    })
    def test_account_totp_secret_is_only_returned_by_secret_endpoint(self, _get_account):
        response = self.client.get(
            "/api/accounts/1/secret?field=totp_secret",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["value"], "JBSWY3DPEHPK3PXP")

    @patch("webui.app.time.time", return_value=1710000010)
    @patch("webui.app.db.get_account", return_value={
        "id": 1,
        "email": "target@example.com",
        "totp_secret": "JBSWY3DPEHPK3PXP",
    })
    def test_current_totp_code_endpoint_returns_code_without_secret(self, _get_account, _time):
        response = self.client.get(
            "/api/accounts/1/totp-code",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], pyotp.TOTP("JBSWY3DPEHPK3PXP").at(1710000010))
        self.assertEqual(payload["remaining_seconds"], 20)
        self.assertNotIn("secret", payload)

    def test_modern_totp_action_fetches_and_copies_code_in_one_click(self):
        response = self.client.get("/", headers=self.headers)
        html = self._modern_page_source(response)
        self.assertIn('data-account-totp-copy="${esc(r.id)}"', html)
        self.assertIn('title="获取并复制当前 6 位 TOTP 验证码"', html)
        self.assertNotIn('data-account-copy-secret="totp_secret"', html)
        self.assertNotIn('title="复制 2FA 密钥（不是当前 6 位验证码）"', html)
        self.assertIn("const result = await api(`/api/accounts/${encodeURIComponent(id)}/totp-code`);", html)
        self.assertIn("const copied = await copyText(result.code, false);", html)
        self.assertNotIn('data-account-totp-value', html)
        self.assertNotIn('data-account-totp-ttl', html)
        self.assertNotIn('data-account-totp-code="${esc(r.id)}"', html)
        self.assertNotIn("请先查询验证码", html)

    def test_account_interface_exposes_chatgpt_session_copy_action(self):
        source = self._modern_page_source(self.client.get("/", headers=self.headers))
        self.assertIn('data-account-copy-secret="chatgpt_session"', source)
        self.assertIn("复制 ChatGPT session", source)

    def test_codex_column_filters_are_combined(self):
        db.save_codex_credential_record("codex-a@example.com-free.json", {
            "email": "a@example.com", "account_id": "acc-a", "access_token": "a",
            "expired": "2026-08-31T00:00:00Z",
        })
        db.save_codex_credential_record("codex-b@example.com-plus.json", {
            "email": "b@example.com", "account_id": "acc-b", "access_token": "b",
            "expired": "2026-09-30T00:00:00Z",
        })
        record_store.insert_row(record_store.ACCOUNTS, {
            "email": "b@example.com",
            "extra_json": '{"sub2api_account_id": 77}',
        })
        second = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", "codex-b@example.com-plus.json")
        record_store.patch_row(record_store.CODEX_CREDENTIALS, second["id"], {"exported_count": 2})
        response = self.client.get(
            "/api/codex?paged=1&page=1&page_size=20&plan=plus&status=exported&account_id=acc-b&sub2api_id=77&expired_date=2026-09-30",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["accounts"][0]["email"], "b@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["plan"]}, {"free", "plus"})
        self.assertEqual({item["value"] for item in payload["facets"]["status"]}, {"unexported", "exported"})

    def test_outlook_column_filters_are_combined(self):
        self.seed(record_store.OUTLOOK_POOL, [
            {"email": "used@example.com", "status": "used", "access_token": "token", "imported_at": "2026-08-10T10:00:00", "used_at": "2026-08-11T09:00:00"},
            {"email": "free@example.com", "status": "available", "access_token": "", "imported_at": "2026-08-09T10:00:00"},
        ])
        response = self.client.get(
            "/api/outlook?paged=1&page=1&page_size=20&source=outlook&status=used&used_date=2026-08-11",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "used@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["status"]}, {"available", "used"})
        self.assertNotIn("token", payload["facets"])
        self.assertNotIn("has_access_token", payload["items"][0])


class EmailButlerLeaseApiTests(PostgresTestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    @patch("core.email_butler_client.active_mailbox_leases", return_value=[{"email": "lease@example.com", "mailbox_id": "m-1"}])
    def test_list_leases(self, _active):
        response = self.client.get("/api/email-butler/leases", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["email"], "lease@example.com")

    @patch("core.email_butler_client.active_mailbox_leases", return_value=[{"email": "lease@example.com", "mailbox_id": "m-1"}])
    @patch("core.email_butler_client.pick_account", return_value=SimpleNamespace(email="lease@example.com", mailbox_id="m-1"))
    def test_create_lease(self, _pick, _active):
        response = self.client.post("/api/email-butler/leases", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["mailbox_id"], "m-1")

    @patch("core.email_butler_client.release_account")
    @patch("core.email_butler_client.get_account_context", return_value=SimpleNamespace(email="lease@example.com"))
    def test_release_lease(self, _context, release):
        response = self.client.post(
            "/api/email-butler/leases/release",
            json={"email": "lease@example.com", "status": "available"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        release.assert_called_once_with("lease@example.com", status="available", note="WebUI 手动释放")

    def test_release_rejects_invalid_email(self):
        response = self.client.post(
            "/api/email-butler/leases/release",
            json={"email": "not-an-email"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
