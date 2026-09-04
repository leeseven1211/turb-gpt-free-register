# -*- coding: utf-8 -*-
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pyotp
from core import db, record_store
from webui.app import create_app
from tests.support_pg import PostgresTestCase


class DashboardApiTests(PostgresTestCase):
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

    def test_frontend_static_assets_are_referenced_and_served(self):
        assets = self.MODERN_ASSETS + (
            "css/legacy.css",
            "css/login.css",
            "js/legacy/common.js",
            "js/legacy/dashboard.js",
            "js/legacy/jobs.js",
            "js/legacy/accounts.js",
            "js/legacy/email.js",
            "js/legacy/codex.js",
            "js/legacy/config.js",
            "js/legacy/bootstrap.js",
            "js/login.js",
        )
        for asset in assets:
            response = self.client.get(f"/static/{asset}")
            try:
                self.assertEqual(response.status_code, 200, asset)
            finally:
                response.close()

        modern = self.client.get("/", headers=self.headers).get_data(as_text=True)
        legacy = self.client.get("/?ui=legacy", headers=self.headers).get_data(as_text=True)
        login = self.client.get("/login").get_data(as_text=True)
        self.assertIn("/static/js/modern/common.js", modern)
        self.assertIn("/static/js/legacy/common.js", legacy)
        self.assertIn("/static/js/login.js", login)

    @patch("core.proxy_provider.registration_proxy_mode", return_value="1024")
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
        self.assertIn("const CONFIG_LEGACY_LIFECYCLE_GROUPS_V2 = new Set(['注册与账号', '执行方式']);", html)
        self.assertNotIn('data-lifecycle-section-v2', html)
        self.assertNotIn('renderLifecycleDriverSelect', html)
        self.assertIn('config-setting-row-v2', html)
        self.assertIn("const preferredNames = ['通用配置', '注册主链路', '账号补全', '注册调试'];", html)
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
        self.assertEqual(html.count('data-column-filter="'), 43)
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
        self.assertIn('>Plus 试用</th>', html)
        self.assertIn('data-account-more-id="${esc(r.id)}"', html)
        self.assertIn('function restoreAccountsV2MoreMenu(accountId)', html)
        self.assertNotIn('data-column-filter="accountNoteFilterV2"', html)
        self.assertNotIn('>备注</th>', html)
        self.assertIn('data-column-filter="codexStatusFilterV2"', html)
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
        self.assertIn('function accountTaskEventStepState(event)', html)
        self.assertIn("const latestRunId = String(selectedRunId || task?.last_run_id", html)
        self.assertIn("legacyRegistration && !observed.has('network')", html)
        self.assertIn("历史任务未单独记录网络阶段", html)
        self.assertIn("skipped:'已跳过'", html)
        self.assertNotIn("stage.seen ? 'success'", html)
        self.assertIn('data-progress-retry-job', html)
        self.assertIn('batch-progress-v2-step-duration', html)
        self.assertIn('data-progress-duration-start', html)
        self.assertIn('repeat(var(--batch-progress-step-count, 1), minmax(64px, 1fr))', html)
        self.assertIn('style="--batch-progress-step-count:${Math.max(stages.length, 1)}"', html)
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

    @patch("webui.runtime._ACCOUNT_EXECUTOR.submit")
    @patch("webui.app.account_task_store.create_task", return_value=901)
    @patch("webui.app.codex_retry_service.reserve", return_value=True)
    @patch("webui.app.db.get_account", return_value={
        "id": 1,
        "email": "setup@example.com",
        "account_status": "active",
    })
    def test_account_setup_endpoint_queues_configuration_without_codex(self, _get_account, _reserve, _create_task, submit):
        response = self.client.post("/api/accounts/1/setup", headers=self.headers, json={})
        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_id"], 901)
        self.assertEqual(submit.call_args.kwargs["task_id"], 901)
        self.assertEqual(submit.call_args.kwargs["task_trigger"], "manual_account_setup")
        self.assertEqual(submit.call_args.args[0].__name__, "_run_account_setup_worker")

    def test_modern_ui_polling_avoids_overlapping_requests_and_duplicate_summary_refresh(self):
        response = self.client.get("/", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        html = self._modern_page_source(response)
        self.assertIn("if (summaryLoading) return;", html)
        self.assertIn("if (dashboardLoading) return;", html)
        self.assertIn("if (jobsLoading) { jobsReloadQueued = true; return; }", html)
        self.assertIn("if (outlookLoading) { outlookReloadQueued = true; return; }", html)
        self.assertIn("if (codexLoading) { codexReloadQueued = true; return; }", html)
        self.assertIn("if (accountTasksLoading) return;", html)
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
            "btnCopySelectedLinesV2", "btnCopySelectedEmailsV2", "btnCopySelectedPasswordsV2", "btnDownloadSelectedTxtV2",
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
            {"email": "target@example.com", "email_source": "outlook", "access_token": "token", "totp_secret": "JBSWY3DPEHPK3PXP", "codex_status": "success", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_trial_eligible": True, "extra_json": '{"account_password":"Account123!abcd"}'},
            {"email": "other@example.com", "email_source": "icloud_hide", "access_token": "", "totp_enabled": False, "codex_status": "failed", "plan_type": "plus", "current_plan_type": "plus"},
        ])
        response = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&email=target&source=outlook&token=has&password=has&trial=eligible&totp=enabled&codex=success",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "target@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["source"]}, {"outlook", "icloud_hide"})
        self.assertEqual({item["value"] for item in payload["facets"]["codex"]}, {"success", "failed"})
        self.assertEqual({item["value"] for item in payload["facets"]["password"]}, {"has", "none"})
        self.assertEqual({item["value"] for item in payload["facets"]["trial"]}, {"eligible", "not_applicable"})
        self.assertTrue(payload["items"][0]["has_account_password"])
        self.assertTrue(payload["items"][0]["totp_enabled"])

    def test_accounts_trial_filter_is_applied(self):
        self.seed(record_store.ACCOUNTS, [
            {"email": "eligible@example.com", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_trial_eligible": True},
            {"email": "used@example.com", "plan_type": "free", "current_plan_type": "free", "plan_check_status": "success", "plus_trial_eligible": False},
            {"email": "plus@example.com", "plan_type": "plus", "current_plan_type": "plus"},
        ])
        response = self.client.get(
            "/api/accounts?paged=1&page=1&page_size=20&trial=eligible",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "eligible@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["trial"]}, {"eligible", "ineligible", "not_applicable"})

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

    def test_codex_column_filters_are_combined(self):
        db.save_codex_credential_record("codex-a@example.com-free.json", {
            "email": "a@example.com", "account_id": "acc-a", "access_token": "a",
            "expired": "2026-08-31T00:00:00Z",
        })
        db.save_codex_credential_record("codex-b@example.com-plus.json", {
            "email": "b@example.com", "account_id": "acc-b", "access_token": "b",
            "expired": "2026-09-30T00:00:00Z",
        })
        second = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", "codex-b@example.com-plus.json")
        record_store.patch_row(record_store.CODEX_CREDENTIALS, second["id"], {"exported_count": 2})
        response = self.client.get(
            "/api/codex?paged=1&page=1&page_size=20&plan=plus&status=exported&account_id=acc-b&expired_date=2026-09-30",
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
            "/api/outlook?paged=1&page=1&page_size=20&source=outlook&status=used&token=has&used_date=2026-08-11",
            headers=self.headers,
        )
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email"], "used@example.com")
        self.assertEqual({item["value"] for item in payload["facets"]["status"]}, {"available", "used"})


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
