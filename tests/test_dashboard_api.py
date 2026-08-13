# -*- coding: utf-8 -*-
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from webui.app import create_app


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {
        "display_status": "partial_success" if row.get("status") == "failed" else row.get("status")
    })
    @patch("core.proxy_provider.registration_proxy_mode", return_value="1024")
    @patch("core.proxy_provider.active_proxy_leases", return_value=[{"provider": "1024proxy", "endpoint": "1.2.*.*:80"}])
    @patch("webui.app.db.codex_accounts_summary", return_value={"total": 2, "exported": 1, "pending": 1})
    @patch("webui.app.db.icloud_hide_email_pool_summary", return_value={"total": 4, "available": 3, "used": 1})
    @patch("webui.app.db.domain_email_pool_summary", return_value={"total": 3, "available": 2, "used": 1})
    @patch("webui.app.db.generic_api_email_pool_summary", return_value={"total": 2, "available": 2})
    @patch("webui.app.db.outlook_pool_summary", return_value={"total": 5, "available": 4, "used": 1})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 8, "status": "success", "email": "a@example.com", "created_at": datetime.now().isoformat()},
        {"id": 7, "status": "failed", "created_at": datetime.now().isoformat()},
    ])
    @patch("webui.app.db.list_accounts", return_value=[
        {"id": 1, "plan_type": "free", "codex_status": "success"},
        {"id": 2, "plan_type": "free", "plus_trial_eligible": True},
        {"id": 3, "plan_type": "plus", "archived": True},
    ])
    def test_dashboard_returns_aggregates_without_account_secrets(self, *_mocks):
        response = self.client.get("/api/dashboard", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["accounts"]["total"], 3)
        self.assertEqual(payload["accounts"]["active"], 2)
        self.assertEqual(payload["accounts"]["plans"], {"free": 1, "free_trial_eligible": 1})
        self.assertEqual(payload["email"]["local_available"], 11)
        self.assertEqual(payload["jobs"]["today_counts"], {"success": 1, "partial_success": 1, "failed": 0})
        self.assertEqual(payload["proxy"]["active_leases"], 1)
        self.assertEqual(payload["proxy"]["platform"], "1024")
        self.assertNotIn("access_token", str(payload))
        self.assertNotIn("api_key", str(payload).lower())

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 3, "status": "success"},
        {"id": 2, "status": "failed"},
        {"id": 1, "status": "failed"},
    ])
    def test_jobs_status_filter_keeps_global_counts(self, *_mocks):
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

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 3, "status": "failed", "email": "target@example.com", "email_source": "email_butler"},
        {"id": 2, "status": "success", "email": "other@example.com", "email_source": "email_butler"},
        {"id": 1, "status": "failed", "email": "target@elsewhere.com", "email_source": "outlook"},
    ])
    def test_jobs_query_and_email_source_filters(self, *_mocks):
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&q=target&email_source=email_butler",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "target@example.com")
        self.assertEqual(payload["status_counts"], {"failed": 1, "active": 0})

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 3, "status": "success", "created_at": "2026-08-11T10:00:00"},
        {"id": 2, "status": "failed", "created_at": "2026-08-10T10:00:00"},
    ])
    def test_jobs_date_range_filter(self, *_mocks):
        response = self.client.get(
            "/api/jobs?paged=1&page=1&page_size=20&date_from=2026-08-11&date_to=2026-08-11",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], 3)

    @patch("webui.app.svc.get_retry_info", side_effect=lambda row: {})
    @patch("webui.app.db.list_jobs", return_value=[
        {"id": 31, "status": "failed", "email": "target@example.com", "proxy_provider": "1024proxy", "proxy_region": "JP", "error_message": "OTP timeout"},
        {"id": 32, "status": "failed", "email": "other@example.com", "proxy_provider": "1024proxy", "proxy_region": "US", "error_message": "browser timeout"},
    ])
    def test_jobs_column_filters_can_be_combined(self, *_mocks):
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
        html = response.get_data(as_text=True)
        self.assertIn('id="tab-overview"', html)
        self.assertIn('class="accounts-command-deck"', html)
        self.assertIn('id="butlerLeasePanel"', html)
        self.assertIn('data-module-subnav="register"', html)
        self.assertIn('data-sidebar-module="register"', html)
        self.assertIn('data-sidebar-module="accounts"', html)
        self.assertNotIn('data-module-subnav="codex"', html)
        self.assertNotIn('data-view="sub2"', html)
        self.assertIn('data-module-subnav="outlook"', html)
        self.assertNotIn('<nav class="module-subnav"', html)
        self.assertIn("$$('[data-module-subnav]').forEach", html)
        self.assertIn('id="btnCodexUploadSub2V2"', html)
        self.assertIn("syncFacetSelect('accountPlanFilterV2'", html)
        self.assertIn("syncFacetSelect('codexStatusFilterV2'", html)
        self.assertIn("syncFacetSelect('outlookStatusFilterV2'", html)
        self.assertNotIn('id="codexFilterV2"', html)
        self.assertNotIn('id="accountsFilterV2"', html)
        self.assertIn('id="outlookToolbarV2"', html)
        self.assertEqual(html.count('data-column-filter="'), 31)
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
        self.assertIn('data-column-filter="codexStatusFilterV2"', html)
        self.assertIn('data-column-filter="outlookStatusFilterV2"', html)
        self.assertNotIn('id="configOverviewV2"', html)
        self.assertIn("activateTab(localStorage.getItem('gpt_console_active_tab') || 'overview', false)", html)
        self.assertIn('data-column-filter="jobDateFromV2"', html)
        self.assertIn('id="btnResetJobFiltersV2"', html)
        self.assertIn('id="btnBatchStopV2"', html)
        self.assertIn('id="btnBatchCancelV2"', html)
        self.assertIn('id="btnBatchRetryV2"', html)
        self.assertIn('data-progress-retry-job', html)
        self.assertIn('batch-progress-v2-step-duration', html)
        self.assertIn('data-progress-duration-start', html)
        self.assertIn('batchProgressRenderSignature', html)
        self.assertIn('currentBatchJobs().find', html)
        self.assertNotIn('batch-progress-v2-error', html)
        self.assertNotIn('class="jobs-column-filters"', html)
        self.assertIn('data-column-filter="jobStatusColumnFilterV2"', html)
        self.assertNotIn('id="qJobsV2"', html)
        self.assertNotIn("Automation queue", html)
        self.assertIn(".accounts-command-deck {\n      position: relative; top: auto;", html)
        self.assertNotIn("TG 交流群", html)
        self.assertNotIn("切换老 UI", html)

    def test_all_list_actions_remain_available_with_resizable_columns(self):
        response = self.client.get("/", headers=self.headers)
        html = response.get_data(as_text=True)
        action_ids = {
            # 任务记录
            "btnRetrySelectedJobsV2", "btnDeleteSelectedJobsV2", "btnCancelPendingV2", "btnRefreshJobsV2",
            # 账号
            "btnCheckSelectedLiveV2", "btnCheckSelectedPlansV2", "btnExtractSelectedLinksV2",
            "btnRetrySelectedCodexV2", "btnDownloadSelectedCpaV2", "btnUploadSelectedCodexSub2V2",
            "btnStopSelectedCodexV2", "btnCheckSelectedDeactivationMailV2", "btnNoteSelectedAccountsV2",
            "btnCopySelectedLinesV2", "btnCopySelectedEmailsV2", "btnCopySelectedPasswordsV2", "btnDownloadSelectedTxtV2",
            "btnArchiveSelectedAccountsV2", "btnDeleteSelectedAccountsV2", "btnCopyAllTokensV2",
            "btnCopyAllLinesV2", "btnRefreshAccountsV2",
            # Codex 凭证
            "btnCodexDownloadBulkV2", "btnCodexDownloadBulkCpaV2", "btnCodexUploadSub2V2",
            "btnCodexArchiveBulkV2", "btnCodexDeleteBulkV2", "btnRefreshCodexV2",
            # 邮箱池
            "btnMarkSelectedOutlookAvailableV2", "btnDisableSelectedOutlookV2",
            "btnFailSelectedOutlookV2", "btnDeleteSelectedOutlookV2", "copyAllEmailsV2",
            "btnImportOutlookV2", "btnRefreshOutlookV2",
        }
        for action_id in action_ids:
            self.assertIn(f'id="{action_id}"', html, action_id)
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
        self.assertIn(">重试</button>", html)
        self.assertIn(">删除</button>", html)
        self.assertIn(">取消</button>", html)

    def test_navigation_avoids_unnecessary_vertical_scrolling(self):
        response = self.client.get("/", headers=self.headers)
        html = response.get_data(as_text=True)
        self.assertIn("min-height: 0; padding-left: var(--sidebar-width);", html)
        self.assertIn("overscroll-behavior-y: contain;", html)
        self.assertIn("#tab-config .config-nav-v2-item { min-height: 32px; padding: 6px 10px; }", html)
        self.assertIn("var(--page-gutter) 28px;", html)
        self.assertIn("function containVerticalScroll(el)", html)
        self.assertIn("event.preventDefault();", html)

    @patch("webui.app.db.list_accounts", return_value=[
        {"id": 1, "email": "target@example.com", "email_source": "outlook", "access_token": "token", "totp_secret": "JBSWY3DPEHPK3PXP", "codex_status": "success", "extra_json": '{"registration_password":"Random123!abcd"}'},
        {"id": 2, "email": "other@example.com", "email_source": "icloud_hide", "access_token": "", "totp_enabled": False, "codex_status": "failed"},
    ])
    def test_accounts_column_filters_are_combined(self, _list_accounts):
        response = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&email=target&source=outlook&token=has&password=has&totp=enabled&codex=success",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "target@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["source"]}, {"outlook", "icloud_hide"})
        self.assertEqual({item["value"] for item in payload["facets"]["codex"]}, {"success", "failed"})
        self.assertEqual({item["value"] for item in payload["facets"]["password"]}, {"has", "none"})
        self.assertTrue(payload["items"][0]["has_registration_password"])
        self.assertTrue(payload["items"][0]["totp_enabled"])

    @patch("webui.app.db.get_account", return_value={
        "id": 1,
        "email": "target@example.com",
        "extra_json": '{"registration_password":"Random123!abcd"}',
    })
    def test_account_registration_password_is_only_returned_by_secret_endpoint(self, _get_account):
        response = self.client.get(
            "/api/accounts/1/secret?field=registration_password",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["value"], "Random123!abcd")

    @patch("webui.app.db.list_codex_accounts", return_value=[
        {"filename": "codex-a-free.json", "email": "a@example.com", "plan": "free", "account_id": "acc-a", "exported_count": 0, "expired": "2026-08-31T00:00:00"},
        {"filename": "codex-b-plus.json", "email": "b@example.com", "plan": "plus", "account_id": "acc-b", "exported_count": 2, "expired": "2026-09-30T00:00:00"},
    ])
    @patch("webui.app.db.codex_accounts_summary", return_value={"total": 2, "exported": 1, "pending": 1})
    def test_codex_column_filters_are_combined(self, *_mocks):
        response = self.client.get(
            "/api/codex?paged=1&page=1&page_size=20&plan=plus&status=exported&account_id=acc-b&expired_date=2026-09-30",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["accounts"][0]["email"], "b@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["plan"]}, {"free", "plus"})
        self.assertEqual({item["value"] for item in payload["facets"]["status"]}, {"unexported", "exported"})

    @patch("webui.app.db.list_icloud_hide_email_pool", return_value=[])
    @patch("webui.app.db.list_domain_email_pool", return_value=[])
    @patch("webui.app.db.list_generic_api_email_pool", return_value=[])
    @patch("webui.app.db.list_outlook_pool", return_value=[
        {"email": "used@example.com", "status": "used", "access_token": "token", "imported_at": "2026-08-10T10:00:00", "used_at": "2026-08-11T09:00:00"},
        {"email": "free@example.com", "status": "available", "access_token": "", "imported_at": "2026-08-09T10:00:00"},
    ])
    def test_outlook_column_filters_are_combined(self, *_mocks):
        response = self.client.get(
            "/api/outlook?paged=1&page=1&page_size=20&source=outlook&status=used&token=has&used_date=2026-08-11",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "used@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["status"]}, {"available", "used"})


class EmailButlerLeaseApiTests(unittest.TestCase):
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
