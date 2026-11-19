# -*- coding: utf-8 -*-
import json
import subprocess
import unittest
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pyotp
from core import db
from core.storage import records as record_store
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class _DashboardMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.filters = {}
        self.config_buttons = []
        self.table = None
        self.button = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.table = attrs.get("data-resizable-table")
        if tag == "th" and "data-column-filter" in attrs:
            self.filters.setdefault(self.table, []).append(attrs["data-column-filter"])
        if tag == "button" and "data-config-domain-v2" in attrs:
            self.button = (attrs["data-config-domain-v2"], [])

    def handle_data(self, data):
        if self.button:
            self.button[1].append(data)

    def handle_endtag(self, tag):
        if tag == "table":
            self.table = None
        if tag == "button" and self.button:
            domain, text = self.button
            self.config_buttons.append((domain, "".join(text).strip()))
            self.button = None


class DashboardUiScriptTests(unittest.TestCase):
    MODERN_COMMON_JS = Path(__file__).resolve().parents[2] / "webui/static/js/shared/common.js"

    def test_account_vue_list_preserves_toolbar_filters_columns_and_actions(self):
        # Accounts mount lazily. Execute their production Vue owners instead of
        # treating source concatenation as server-rendered account controls.
        frontend = Path(__file__).resolve().parents[2] / "frontend"
        result = subprocess.run(
            ["node", "node_modules/vitest/vitest.mjs", "run",
             "src/features/accounts/AccountsToolbar.test.ts",
             "src/features/accounts/AccountFilters.test.ts",
             "src/features/accounts/AccountsTable.test.ts",
             "src/features/accounts/AccountsList.test.ts",
             "src/shared/useColumnWidths.test.ts",
             "src/features/accounts/actions.test.ts",
             "src/features/accounts/setupActions.test.ts",
             "src/features/accounts/queuedActions.test.ts"],
            cwd=frontend, check=False, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_account_menu_and_legacy_column_preferences_use_real_compatibility_contracts(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["node", "--test", "tests/accounts/test_account_more_menu_frontend.cjs",
             "tests/accounts/test_account_column_resize_frontend.cjs",
             "tests/accounts/test_accounts_vue_bridge.cjs"],
            cwd=root, check=False, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_compact_account_keeps_registration_driver_without_private_metadata(self):
        from webui.route_helpers import _compact_account_for_list

        compact = _compact_account_for_list({
            "id": 1, "email": "driver@example.test", "registration_driver": "protocol_oss_2",
            "extra_json": '{"account_password":"private-password"}', "access_token": "private-token",
        })
        self.assertEqual(compact["registration_driver"], "protocol_oss_2")
        self.assertNotIn("extra_json", compact)
        self.assertNotIn("access_token", compact)

    def _run_dashboard_vue_contract(self, case):
        # Execute the current Vue owner instead of slicing retired page.js helpers.
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["node", "--test", "--test-name-pattern", case,
             "tests/webui/test_dashboard_vue_contracts.cjs"],
            cwd=root, check=False, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dashboard_proxy_platform_labels_follow_current_source_and_keep_legacy_aliases(self):
        self._run_dashboard_vue_contract("dashboard proxy labels preserve current and historical identities")

    def test_dashboard_proxy_summary_displays_at_most_three_exit_leases(self):
        self._run_dashboard_vue_contract("dashboard proxy summary keeps at most three rendered exit leases and full compact total")

    def test_dashboard_hides_unavailable_cards_and_email_sources(self):
        self._run_dashboard_vue_contract("dashboard unavailable capabilities and empty inventory suppress their cards")

    def test_dashboard_preferences_keep_order_and_remove_unknown_cards(self):
        self._run_dashboard_vue_contract("dashboard layout normalization preserves order and prunes unknown hidden ids")

    def test_overview_card_sizes_are_saved_and_bounded(self):
        self._run_dashboard_vue_contract("dashboard layout restores bounded widths and heights without unknown cards")

    def test_overview_card_reorder_can_place_card_after_target(self):
        self._run_dashboard_vue_contract("dashboard customizer drag reorders within a region without crossing regions")

    def test_overview_drag_uses_vertical_midpoint_across_grid_rows(self):
        self._run_dashboard_vue_contract("dashboard pointer sorting uses vertical midpoint across grid rows and saves after target")

    def test_overview_exposes_new_aggregate_cards(self):
        self._run_dashboard_vue_contract("dashboard exposes all aggregate queue history health and Codex progress cards")

    def test_overview_data_rich_cards_explain_compact_hidden_rows(self):
        self._run_dashboard_vue_contract("dashboard rich cards retain compact and minimal overflow summaries")

    def test_overview_compact_cards_keep_full_counts_and_priority_rows(self):
        self._run_dashboard_vue_contract("dashboard compact priority rows keep nonzero results visible through summary evidence")

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

    def test_index_uses_shared_page_asset_content_version(self):
        import ast

        path = Path(__file__).resolve().parents[2] / "webui/routes/dashboard.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        factory = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "create_dashboard_blueprint")
        index = next(node for node in factory.body if isinstance(node, ast.FunctionDef) and node.name == "index")
        index.decorator_list = []
        module = ast.fix_missing_locations(ast.Module(body=[index], type_ignores=[]))
        app = object()
        calls = []
        namespace = {
            "context": SimpleNamespace(app=app),
            "page_asset_version": lambda value: calls.append(value) or "content-version",
            "render_template": lambda template, **values: (template, values),
        }
        exec(compile(module, str(path), "exec"), namespace)
        self.assertEqual(namespace["index"](), ("index.html", {"asset_version": "content-version"}))
        self.assertEqual(calls, [app])

    # Codex badge priorities and no-secret presentation now run against the real
    # TypeScript projection in features/codex/presentation.test.ts. Column layout
    # is exercised by CodexCredentials.test.ts and useColumnWidths.test.ts.


class DashboardStaticAssetTests(unittest.TestCase):
    def test_dashboard_has_one_versioned_lazy_host_and_served_assets(self):
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, urlsplit

        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.nodes = []

            def handle_starttag(self, tag, attrs):
                self.nodes.append((tag, dict(attrs)))

        client = create_app(auth_code="test-auth").test_client()
        response = client.get("/", headers={"X-Auth-Code": "test-auth"})
        self.assertEqual(response.status_code, 200)
        parser = Elements()
        parser.feed(response.get_data(as_text=True))
        hosts = [attrs for _, attrs in parser.nodes if attrs.get("id") == "dashboard-page-root"]
        self.assertEqual(len(hosts), 1)
        versions = []
        for attribute, expected_path in (
            ("data-module-url", "/static/task-center/dashboard.js"),
            ("data-style-url", "/static/task-center/task-center.css"),
        ):
            asset_url = hosts[0][attribute]
            parsed = urlsplit(asset_url)
            self.assertEqual(parsed.path, expected_path)
            version = parse_qs(parsed.query).get("v", [""])[0]
            self.assertTrue(version)
            versions.append(version)
            with client.get(asset_url) as asset:
                self.assertEqual(asset.status_code, 200, asset_url)
                self.assertTrue(asset.data, asset_url)
        scripts = [attrs.get("src", "") for tag, attrs in parser.nodes if tag == "script"]
        scripts_by_path = {}
        for script in scripts:
            scripts_by_path.setdefault(urlsplit(script).path, []).append(script)
        paths = [
            "/static/js/shared/common.js",
            "/static/js/shared/page-bridge.js",
            "/static/js/pages/dashboard/page.js",
            "/static/js/bootstrap.js",
        ]
        indices = []
        for path in paths:
            self.assertEqual(len(scripts_by_path.get(path, [])), 1, path)
            script = scripts_by_path[path][0]
            indices.append(scripts.index(script))
            version = parse_qs(urlsplit(script).query).get("v", [""])[0]
            self.assertTrue(version)
            versions.append(version)
            with client.get(script) as asset:
                self.assertEqual(asset.status_code, 200, script)
        self.assertEqual(indices, sorted(indices))
        self.assertEqual(len(set(versions)), 1)
        self.assertNotIn("/static/task-center/dashboard.js", scripts_by_path)
        for old_host in ("overviewMetrics", "overviewPanels", "overviewCustomizeDrawer"):
            self.assertFalse(any(attrs.get("id") == old_host for _, attrs in parser.nodes), old_host)


class DashboardApiTests(PostgresTestCase):
    MODERN_COMMON_JS = Path(__file__).resolve().parents[2] / "webui/static/js/shared/common.js"
    MODERN_JOBS_JS = Path(__file__).resolve().parents[2] / "webui/static/js/pages/registration/page.js"
    MODERN_ASSETS = (
        "css/shell.css",
        "js/shared/common.js",
        "js/pages/dashboard/page.js",
        "js/pages/registration/page.js",
        "js/pages/accounts/page.js",
        "js/pages/operations/page.js",
        "js/pages/accounts/email-change.js",
        "js/pages/accounts/inspection.js",
        "js/pages/email/page.js",
        "js/pages/codex/page.js",
        "js/pages/config/page.js",
        "js/bootstrap.js",
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

    def _ui_fixture(self, name, inputs=None):
        fixture = Path(__file__).with_name("dashboard_ui_fixture.cjs")
        result = subprocess.run(
            ["node", str(fixture), name], input=json.dumps(inputs),
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

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

    def test_batch_progress_reports_missing_password_response_as_failure(self):
        result = subprocess.run(
            ["node", "tests/registration/vue_migration_contracts.cjs", "password_result"],
            cwd=Path(__file__).resolve().parents[2],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stdout.strip(), "ok password_result")

    def test_frontend_static_assets_are_referenced_and_served(self):
        assets = self.MODERN_ASSETS + (
            "css/shared/ui-foundation.css",
            "css/pages/login.css",
            "js/pages/proxy/traffic.js",
            "js/pages/login/page.js",
        )
        for asset in assets:
            response = self.client.get(f"/static/{asset}")
            try:
                self.assertEqual(response.status_code, 200, asset)
            finally:
                response.close()

        modern = self.client.get("/", headers=self.headers).get_data(as_text=True)
        login = self.client.get("/login").get_data(as_text=True)
        self.assertIn("/static/js/shared/common.js", modern)
        self.assertIn("/static/js/pages/proxy/traffic.js", modern)
        self.assertIn("/static/js/pages/login/page.js", login)

    def test_previous_ui_preferences_open_the_current_interface(self):
        self.client.set_cookie("ui_mode", "legacy")
        for path in ("/", "/?ui=legacy", "/?ui=modern"):
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('class="app-sidebar"', html)
                self.assertIn("/static/js/shared/common.js", html)
                self.assertNotIn("/static/js/legacy/", html)
                self.assertNotIn("ui_mode=", " ".join(response.headers.getlist("Set-Cookie")))

    def _local_profile(self):
        from core.storage.email.address_allocations import create_inbox_profile
        return create_inbox_profile(inbox_key='dashboard-fixture', connector='forward_butler',
            credential_ref='DASHBOARD_FIXTURE_KEY', inbox_locator={
                'api_base': 'https://butler.test/v1', 'mailbox_email': 'final@example.test'})['id']

    def _local_hme(self, email):
        # forward_butler 的本地库存必须已有已确认交接，不能仅凭 profile 算可用。
        return {'email': email, 'status': 'available', 'remote_active': True,
                'derivation_policy': {'inbox_profile_id': self._local_profile()},
                'butler_handoff': {'version': 1, 'state': 'issued', 'owner_kind': 'local_inventory',
                                   'owner_id': 'dashboard-fixture', 'acquisition_id': 'handoff:' + email,
                                   'identity_id': 'identity:' + email}}

    @patch("core.proxy.pool.pool_source", return_value="1024proxy")
    @patch("core.proxy.provider.active_proxy_leases", return_value=[{"provider": "1024proxy", "endpoint": "1.2.*.*:80"}])
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
                email = f'{spec.name}-{index}@example.test'
                row = self._local_hme(email) if spec == record_store.ICLOUD_HIDE_POOL else {'email': email, 'status': 'available'}
                record_store.insert_row(spec, row)
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
    @patch("core.proxy.provider.active_proxy_leases", return_value=[])
    @patch("core.proxy.pool.pool_source", return_value="manual")
    def test_dashboard_email_sources_include_visibility_and_forward_butler_dependency(
        self, *_mocks
    ):
        record_store.insert_row(record_store.ICLOUD_HIDE_POOL, self._local_hme('local@icloud.com'))
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
    @patch("core.proxy.provider.active_proxy_leases", return_value=[])
    @patch("core.proxy.pool.pool_source", return_value="manual")
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
        self.assertIn('id="email-page-root"', html)
        self.assertIn('data-module-subnav="register"', html)
        self.assertIn('data-sidebar-module="register"', html)
        self.assertIn('data-sidebar-module="accounts"', html)
        self.assertIn('data-sidebar-module="codex"', html)
        self.assertIn('data-module-subnav="codex"', html)
        self.assertNotIn('data-view="sub2"', html)
        self.assertIn('data-module-subnav="outlook"', html)
        self.assertNotIn('<nav class="module-subnav"', html)
        self.assertIn("$$('[data-module-subnav]').forEach", html)
        self.assertIn('id="codex-credentials-root"', html)
        self.assertNotIn('id="btnOpenAccountCompletionConfigTopV2"', html)
        self.assertNotIn('>补全规则</button>', html)
        self.assertNotIn('>补全配置</button>', html)
        self.assertNotIn('旧版补齐配置', html)
        self.assertNotIn('data-lifecycle-section-v2', html)
        self.assertNotIn('renderLifecycleDriverSelect', html)
        # Config navigation and field rows are rendered by the real Vue owner.
        # Preserve aliases, domain order and actual navigation as behavior.
        config_navigation = subprocess.run(
            ["node", "tests/config/vue_migration_contracts.cjs", "primary_navigation"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(0, config_navigation.returncode, config_navigation.stdout + config_navigation.stderr)
        # Account toolbar labels/section order and setup endpoints are exercised
        # by test_account_vue_list_preserves_toolbar_filters_columns_and_actions.
        # Codex facet options and unknown selected values belong to the Vue state tests.
        # Email facets and actions are checked on the actual Vue owner below.
        self.assertNotIn('id="codexFilterV2"', html)
        self.assertNotIn('id="accountsFilterV2"', html)
        self.assertNotIn('id="outlookToolbarV2"', html)
        # Shared legacy filters still serve their remaining owners. Migrated
        # registration controls are exercised on the mounted Vue page below.
        self.assertIn('class="column-filter-trigger"', html)
        self.assertIn('class="column-filter-search"', html)
        self.assertIn('data-column-filter-options', html)
        self.assertIn('class="column-filter-native" hidden', html)
        self.assertIn('select.innerHTML = options.map(item => `<option value="${attrEsc(item.value)}">', html)
        self.assertNotIn('select.innerHTML = options.map(item => `<option value="${esc(item.value)}">', html)
        self.assertNotIn('class="list-column-filters"', html)
        self.assertNotIn('data-column-filter="accountNoteFilterV2"', html)
        self.assertNotIn('>备注</th>', html)
        # Codex status/OAuth/Sub2API filters are verified by mounted component tests.
        self.assertNotIn('data-column-filter="outlookStatusFilterV2"', html)
        self.assertNotIn('id="configOverviewV2"', html)
        self.assertIn("initializeNavigationHistory(localStorage.getItem('gpt_console_active_tab') || 'overview')", html)
        self.assertEqual(1, html.count('id="registrationRoot"'))
        self.assertRegex(html, r'data-module-url="/static/task-center/registration\.js\?v=[^"]+"')
        for legacy_id in ("jobsBodyV2", "jobsPanelV2", "registrationBatchSelectV2", "btnResetJobFiltersV2"):
            self.assertNotIn(f'id="{legacy_id}"', html)
        registration_progress = subprocess.run(
            ["node", "tests/registration/vue_migration_contracts.cjs", "progress_controls"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertEqual(0, registration_progress.returncode, registration_progress.stdout + registration_progress.stderr)
        self.assertIn("skipped:'已跳过'", html)
        self.assertNotIn('batch-progress-v2-error', html)
        self.assertNotIn('class="jobs-column-filters"', html)
        self.assertEqual(1, html.count('id="task-center-root"'))
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
        lifecycle = subprocess.run(
            ["node", "--test", "tests/registration/test_registration_refresh_frontend.cjs",
             "tests/webui/test_dashboard_vue_contracts.cjs", "tests/webui/test_page_owner_bridge.cjs"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False, timeout=30,
        )
        self.assertEqual(0, lifecycle.returncode, lifecycle.stdout + lifecycle.stderr)
        self.assertNotIn("outlookLoading", html)
        self.assertIn("window.EmailPage?.setVisible(tab === 'outlook')", html)
        # Codex stale-response cancellation and absence of polling are behavioral
        # assertions in useCodexList.test.ts and test_codex_bridge.cjs.
        self.assertNotIn("codexLoading", html)
        self.assertNotIn("    loadSummary();\n  } catch(e) {}\n}", html)
        bootstrap = (Path(__file__).resolve().parents[2] / "webui/static/js/bootstrap.js").read_text(encoding="utf-8")
        self.assertNotIn("setInterval(", bootstrap)
        self.assertIn("window.DashboardPage?.setVisible(tab === 'overview')", html)
        self.assertIn("window.RegistrationPage?.setVisible(tab === 'register')", html)

    def test_all_list_actions_remain_available_with_resizable_columns(self):
        response = self.client.get("/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        html = self._modern_page_source(response)
        registration_contract = subprocess.run(
            ["node", "tests/registration/vue_migration_contracts.cjs", "list_controls"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertEqual(0, registration_contract.returncode, registration_contract.stdout + registration_contract.stderr)
        email_contract = subprocess.run(
            ["node", "tests/email/vue_migration_contracts.cjs", "inventory_controls"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertEqual(0, email_contract.returncode, email_contract.stdout + email_contract.stderr)
        self.assertNotIn('data-resizable-table="jobs"', html)
        self.assertNotIn('id="codexBulkWorkersV2"', html)
        self.assertNotIn('id="codexStatsV2"', html)
        self.assertNotIn('id="codexStatTotalV2"', html)
        self.assertNotIn('id="codexStatExportedV2"', html)
        self.assertNotIn('id="codexStatPendingV2"', html)
        self.assertNotIn('class="codex-sync-callout"', html)
        self.assertNotIn('id="btnCodexUploadSub2HeroV2"', html)
        self.assertIn('id="codex-credentials-root"', html)

    def test_accounts_has_one_versioned_lazy_mount_and_dedicated_hosts(self):
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, urlsplit

        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.nodes = []

            def handle_starttag(self, tag, attrs):
                self.nodes.append((tag, dict(attrs)))

        response = self.client.get("/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        parser = Elements()
        parser.feed(response.get_data(as_text=True))
        for host in ("accounts-list-root", "accountDetailHost",
                     "accountRegistrationReceiptHost", "accountC2aReceiptHost", "accountC2aConfirmHost"):
            self.assertEqual(sum(attrs.get("id") == host for _, attrs in parser.nodes), 1, host)
        root = next(attrs for _, attrs in parser.nodes if attrs.get("id") == "accounts-list-root")
        versions = []
        for attribute, expected_path in (
            ("data-module-url", "/static/task-center/accounts.js"),
            ("data-style-url", "/static/task-center/task-center.css"),
        ):
            url = urlsplit(root[attribute])
            self.assertEqual(url.path, expected_path)
            version = parse_qs(url.query).get("v", [""])[0]
            self.assertTrue(version)
            versions.append(version)
        scripts = [attrs.get("src", "") for tag, attrs in parser.nodes if tag == "script"]
        account_scripts = [url for url in scripts if urlsplit(url).path in (
            "/static/js/pages/accounts/page.js", "/static/js/pages/accounts/bridge.js")]
        self.assertEqual([urlsplit(url).path for url in account_scripts], [
            "/static/js/pages/accounts/page.js", "/static/js/pages/accounts/bridge.js"])
        for url in account_scripts:
            versions.append(parse_qs(urlsplit(url).query).get("v", [""])[0])
            with self.client.get(url) as asset:
                self.assertEqual(asset.status_code, 200, url)
        self.assertEqual(len(set(versions)), 1)
        self.assertFalse(any(urlsplit(url).path == "/static/task-center/accounts.js" for url in scripts))
        ids = {attrs.get("id") for _, attrs in parser.nodes}
        self.assertTrue({"accountsBodyV2", "accountsToolbarV2", "pager-accounts-v2", "accountDetailDrawer"}.isdisjoint(ids))

    def test_codex_credentials_has_one_versioned_lazy_mount_without_legacy_state(self):
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, urlsplit

        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.nodes = []

            def handle_starttag(self, tag, attrs):
                self.nodes.append((tag, dict(attrs)))

        response = self.client.get("/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        parser = Elements()
        parser.feed(response.get_data(as_text=True))
        roots = [attrs for _, attrs in parser.nodes if attrs.get("id") == "codex-credentials-root"]
        self.assertEqual(len(roots), 1)
        root = roots[0]
        for attribute, expected_path in (
            ("data-module-url", "/static/task-center/codex.js"),
            ("data-style-url", "/static/task-center/task-center.css"),
        ):
            url = urlsplit(root[attribute])
            self.assertEqual(url.path, expected_path)
            self.assertTrue(parse_qs(url.query).get("v", [""])[0])
        scripts = [attrs.get("src", "") for tag, attrs in parser.nodes if tag == "script"]
        bridges = [url for url in scripts if urlsplit(url).path == "/static/js/pages/codex/page.js"]
        self.assertEqual(len(bridges), 1)
        self.assertTrue(parse_qs(urlsplit(bridges[0]).query).get("v", [""])[0])
        # A module URL on the root is inert until the bridge activates the page.
        self.assertFalse(any(urlsplit(url).path == "/static/task-center/codex.js" for url in scripts))
        ids = {attrs.get("id") for _, attrs in parser.nodes}
        self.assertNotIn("codexBodyV2", ids)
        self.assertNotIn("codexToolbarV2", ids)
        self.assertNotIn("pager-codex-v2", ids)
        html = self._modern_page_source(response)
        for name in ("CODEX_SELECTED", "CODEX_SHOW_ARCHIVED", "CODEX_TOTAL", "codexLoading", "codexReloadQueued"):
            self.assertNotIn(name, html)

    def test_legacy_tables_keep_saved_widths_and_filter_popover_order(self):
        source = self._modern_page_source(self.client.get("/", headers=self.headers))

        self.assertIn("readSavedTableWidths(key, cols.length)", source)
        self.assertIn("columnFilterOptionWidth", source)
        self.assertIn("table.dataset.autoSized", source)
        self.assertLess(
            source.index("renderColumnFilterOptions(document.getElementById(header.dataset.columnFilter))"),
            source.index("positionColumnFilterPopover(header)", source.index("renderColumnFilterOptions(document.getElementById(header.dataset.columnFilter))")),
        )

    def test_navigation_avoids_unnecessary_vertical_scrolling(self):
        response = self.client.get("/", headers=self.headers)
        html = self._modern_page_source(response)
        self.assertIn("min-height: 0; padding-left: var(--sidebar-width);", html)
        self.assertIn("overscroll-behavior-y: contain;", html)
        self.assertIn("#tab-config .config-nav-v2-item { min-height: 32px; padding: 6px 10px; }", html)
        self.assertIn("var(--page-gutter) 28px;", html)
        self.assertIn("function containVerticalScroll(el)", html)
        self.assertIn("event.preventDefault();", html)

    def test_operation_poll_can_omit_navigation_and_keeps_compact_batches(self):
        import json
        from core import operation_task_store
        batches = [{"id": index, "batch_uuid": str(index), "title": "批次", "status": "success",
                    "data": {"request": "x" * 5000}} for index in range(50)]
        with patch.object(operation_task_store, "list_tasks", return_value={"ok": True, "items": [{"id": index, "result_summary": {"message": "x" * 1200}} for index in range(20)], "total": 20}) as listing, \
             patch.object(operation_task_store, "list_batches", return_value=batches) as batch_listing:
            response = self.client.get("/api/operations?page_size=20", headers=self.headers)
            payload = response.get_json()
            self.assertLess(len(json.dumps(payload)), 50000)
            self.assertLess(len(json.dumps(payload["batches"])), 10000)
            self.assertEqual(payload["batches"][0]["title"], "批次")
            self.assertNotIn("data", payload["batches"][0])
            self.assertTrue(payload["revision"])
            batch_listing.reset_mock()
            response = self.client.get("/api/operations?include_batches=0&include_facets=0", headers=self.headers)
            self.assertNotIn("batches", response.get_json())
            batch_listing.assert_not_called()
            self.assertFalse(listing.call_args.kwargs["include_facets"])

    def test_plan_details_are_read_on_demand_with_empty_state(self):
        self.seed(record_store.ACCOUNTS, [{"email": "detail@example.test", "account_promotions": [],
            "plan_check_country_results": [], "promotion_query_snapshot": {"version": 1}}])
        account = db.get_account_by_email("detail@example.test")
        response = self.client.get(f"/api/accounts/{account['id']}/plan-details", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["account_promotions"], [])
        self.assertEqual(response.get_json()["item"]["promotion_query_snapshot"], {"version": 1})
        self.assertEqual(self.client.get("/api/accounts/999999/plan-details", headers=self.headers).status_code, 404)

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
        # 每列 facets 只忽略自身条件，邮箱与其他列仍限制候选范围。
        self.assertEqual(payload["facets"]["source"], [{"value": "outlook", "count": 1}])
        alternatives = self.client.get("/api/accounts?paged=1&source=outlook", headers=self.headers).get_json()
        self.assertEqual(alternatives["total"], 1)
        self.assertEqual({item["value"]: item["count"] for item in alternatives["facets"]["source"]},
                         {"outlook": 1, "icloud_hide": 1})
        for key, value in (("codex", "success"), ("password", "has"), ("promotion", "free_trial")):
            self.assertEqual(payload["facets"][key], [{"value": value, "count": 1}])
        unfiltered = self.client.get("/api/accounts?paged=1", headers=self.headers).get_json()
        self.assertEqual(unfiltered["total"], 2)
        self.assertEqual({item["value"] for item in unfiltered["facets"]["codex"]}, {"success", "failed"})
        self.assertEqual({item["value"] for item in unfiltered["facets"]["password"]}, {"has", "none"})
        self.assertEqual({item["value"] for item in unfiltered["facets"]["promotion"]}, {"free_trial", "not_applicable"})
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
        # actions.test.ts executes the exact TOTP endpoint, clipboard call,
        # remaining-seconds feedback and failure handling via the Vue contract.
        self.assertIn("window.AccountsPage.invokeAction('account-totp-copy', context, btn)", html)
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

    @patch("core.email.email_butler.client.active_mailbox_leases", return_value=[{"email": "lease@example.com", "mailbox_id": "m-1"}])
    def test_list_leases(self, _active):
        response = self.client.get("/api/email-butler/leases", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["email"], "lease@example.com")

    @patch("core.email.email_butler.client.active_mailbox_leases", return_value=[{"email": "lease@example.com", "mailbox_id": "m-1"}])
    @patch("core.email.email_butler.client.pick_local_account", return_value=SimpleNamespace(email="lease@example.com", mailbox_id="m-1"))
    def test_create_lease(self, _pick, _active):
        request_id = "fb4ae841-1745-4450-ae65-a73ec0f28f99"
        response = self.client.post("/api/email-butler/leases", json={"request_id": request_id}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["mailbox_id"], "m-1")
        self.assertEqual(response.get_json()["request_id"], request_id)
        self.assertFalse(response.get_json()["request_unknown"])
        _pick.assert_called_once_with(owner_kind="manual", owner_id=request_id, acquisition_id="manual:" + request_id)

    @patch("core.email.email_butler.client.pick_local_account")
    def test_create_lease_requires_browser_request_id_before_claim(self, pick):
        response = self.client.post("/api/email-butler/leases", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "invalid_request_id")
        self.assertFalse(response.get_json()["request_unknown"])
        pick.assert_not_called()

    @patch("core.email.email_butler.client.release_account")
    @patch("core.email.email_butler.client.get_account_context", return_value=SimpleNamespace(email="lease@example.com"))
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
