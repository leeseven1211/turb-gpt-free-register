# -*- coding: utf-8 -*-
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import extract_link_service
from core.task_stages import flow_for
from webui import runtime
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class ExtractLinkServiceTests(unittest.TestCase):
    def test_documented_link_types_are_accepted(self):
        for link_type in (
            "pix",
            "gopay",
            "upi",
            "ideal",
            "ideal_short",
            "kakao_pay",
            "momo",
            "gcash",
            "paypal",
            "ph_short",
        ):
            self.assertEqual(extract_link_service._link_type(link_type), link_type)

    def test_query_link_types_returns_remote_enabled_type_metadata(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "ok": True,
            "items": [
                {"type": "pix", "label": "PIX", "visible": True, "enabled": True},
                {"type": "ideal", "label": "iDEAL", "visible": True, "enabled": False},
            ],
        }
        session = Mock()
        session.get.return_value = response
        requests_module = types.SimpleNamespace(Session=Mock(return_value=session))

        with (
            patch.object(extract_link_service, "_api_base", return_value="https://ple.bzb.qzz.io"),
            patch.object(extract_link_service, "_int_setting", return_value=30),
            patch.object(extract_link_service, "curl_requests", requests_module),
        ):
            result = extract_link_service.query_link_types()

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["items"][0]["type"], "pix")
        self.assertFalse(result["items"][1]["enabled"])
        session.get.assert_called_once_with("https://ple.bzb.qzz.io/api/link-types", timeout=30)

    def test_paypal_options_are_limited_to_documented_fields(self):
        self.assertEqual(
            extract_link_service._paypal_options({
                "paypal_region_selected": "2",
                "paypal_country": "US",
                "paypal_currency": "USD",
                "paypal_region": "US/USD",
                "token": "must-not-pass",
            }),
            {
                "paypal_region_selected": 2,
                "paypal_country": "US",
                "paypal_currency": "USD",
                "paypal_region": "US/USD",
            },
        )

    def test_failed_account_type_falls_back_to_next_enabled_remote_type(self):
        with patch.object(
            extract_link_service,
            "query_link_types",
            return_value={"items": [
                {"type": "pix", "enabled": True},
                {"type": "momo", "enabled": True},
            ]},
        ):
            selected, fallback_from = extract_link_service._select_account_link_type(
                account={"extract_link_failed_types": ["momo"]},
                requested="momo",
            )

        self.assertEqual(selected, "pix")
        self.assertEqual(fallback_from, "momo")

    def test_extract_preflight_uses_existing_token_when_live(self):
        with (
            patch("core.live_check_service.run_account_live_check_inline", return_value={
                "accepted": True,
                "result": {"ok": True, "status": "live"},
            }) as run_inline,
            patch.object(extract_link_service.db, "get_account", return_value={"id": 7, "access_token": "fresh-live-token"}),
        ):
            token = extract_link_service._ensure_extract_token(account_id=7, email="masked@example.com")

        self.assertEqual(token, "fresh-live-token")
        run_inline.assert_called_once_with(
            account_id=7,
            email="masked@example.com",
            trigger="extract_preflight",
            force_refresh=False,
        )

    def test_extract_preflight_refreshes_only_after_expired_token(self):
        progress = Mock()
        inline_results = [
            {
                "accepted": True,
                "result": {
                    "ok": False,
                    "status": "failed",
                    "http_status": 401,
                    "token_expired": True,
                    "error": "AT已过期/失效，请手动查活刷新",
                },
            },
            {
                "accepted": True,
                "result": {"ok": True, "status": "live", "validation_method": "email_otp"},
            },
        ]
        with (
            patch("core.live_check_service.run_account_live_check_inline", side_effect=inline_results) as run_inline,
            patch.object(
                extract_link_service.db,
                "get_account",
                return_value={"id": 7, "access_token": "new-token"},
            ),
        ):
            token = extract_link_service._ensure_extract_token(
                account_id=7,
                email="masked@example.com",
                progress=progress,
            )

        self.assertEqual(token, "new-token")
        self.assertEqual(run_inline.call_count, 2)
        self.assertEqual(run_inline.call_args_list[0].kwargs["trigger"], "extract_preflight")
        self.assertEqual(run_inline.call_args_list[1].kwargs["trigger"], "token_refresh_extract_preflight")
        self.assertTrue(run_inline.call_args_list[1].kwargs["force_refresh"])
        self.assertTrue(any("刷新 AT" in call.args[0] for call in progress.call_args_list))

    def test_extract_preflight_does_not_refresh_network_failure(self):
        with (
            patch("core.live_check_service.run_account_live_check_inline", return_value={
                "accepted": True,
                "result": {"ok": False, "status": "failed", "http_status": 503, "error": "HTTP 503"},
            }) as run_inline,
            patch.object(extract_link_service.db, "get_account") as get_account,
        ):
            with self.assertRaisesRegex(RuntimeError, "未判定为 Token 失效"):
                extract_link_service._ensure_extract_token(account_id=7, email="masked@example.com")

        run_inline.assert_called_once()
        get_account.assert_not_called()

    def test_extract_flow_has_task_center_stages(self):
        self.assertEqual(
            ["preflight", "access_token", "refresh_token", "extract_link", "complete"],
            [step["key"] for step in flow_for("extract_link")],
        )

    def test_run_extract_reports_remote_events_and_safe_result_summary(self):
        reporter = Mock()
        remote_result = {
            "long_url": "https://pay.example/should-stay-out-of-task-summary",
            "image_url_png": "https://pay.example/qr.png",
            "payment_method": "pix",
            "expires_at": "2026-09-14T12:00:00Z",
        }
        with (
            patch.object(extract_link_service, "TaskReporter", return_value=reporter),
            patch.object(extract_link_service.db, "mark_account_extract_running", return_value=True),
            patch.object(extract_link_service.db, "update_account_extract") as update_extract,
            patch.object(extract_link_service, "_ensure_extract_token", return_value="fresh-token"),
            patch.object(extract_link_service, "_create_extract_job", return_value={"job_id": "job-701", "cdk_remaining": 8}),
            patch.object(
                extract_link_service,
                "_iter_sse_events",
                return_value=iter([
                    ("log", {"message": "正在生成支付信息"}),
                    ("result", {"result": remote_result}),
                ]),
            ),
            patch.object(extract_link_service._QUEUE_SLOTS, "release") as release,
        ):
            result = extract_link_service._run_extract(
                account_id=7,
                email="masked@example.com",
                access_token="stale-token",
                link_type="pix",
                cdk="cdk",
                trigger="manual",
                task_id=701,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(remote_result, result["result"])
        reporter.start.assert_called_once_with("开始执行提炼")
        reporter.note.assert_any_call("正在生成支付信息", stage="extract_link", event_type="extract.remote_log")
        finish_kwargs = reporter.finish.call_args.kwargs
        self.assertEqual("success", finish_kwargs["status"])
        self.assertTrue(finish_kwargs["result_summary"]["has_link"])
        self.assertTrue(finish_kwargs["result_summary"]["has_qr"])
        self.assertNotIn("long_url", finish_kwargs["result_summary"])
        self.assertNotIn("image_url_png", finish_kwargs["result_summary"])
        self.assertGreaterEqual(update_extract.call_count, 2)
        release.assert_called_once_with()

    def test_explicit_remote_unsupported_error_is_terminal_unsupported(self):
        reporter = Mock()
        error_message = "当前账号不支持 MoMo 支付方式"
        with (
            patch.object(extract_link_service, "TaskReporter", return_value=reporter),
            patch.object(extract_link_service.db, "mark_account_extract_running", return_value=True),
            patch.object(extract_link_service.db, "update_account_extract") as update_extract,
            patch.object(extract_link_service.db, "mark_extract_link_type_failed") as mark_type_failed,
            patch.object(extract_link_service, "_ensure_extract_token", return_value="fresh-token"),
            patch.object(extract_link_service, "_create_extract_job", return_value={"job_id": "job-unsupported"}),
            patch.object(
                extract_link_service,
                "_iter_sse_events",
                return_value=iter([("error", {"message": error_message})]),
            ),
            patch.object(extract_link_service._QUEUE_SLOTS, "release"),
        ):
            result = extract_link_service._run_extract(
                account_id=7,
                email="masked@example.com",
                access_token="fresh-token",
                link_type="momo",
                cdk="cdk",
                trigger="manual",
                task_id=701,
            )

        self.assertEqual("unsupported", result["status"])
        self.assertEqual(error_message, result["error"])
        self.assertEqual("unsupported", reporter.finish.call_args.kwargs["status"])
        self.assertEqual(error_message, reporter.finish.call_args.kwargs["error"])
        mark_type_failed.assert_called_once_with(7, "momo", error_message)
        self.assertTrue(any(call.args[1]["status"] == "unsupported" for call in update_extract.call_args_list))

    def test_enqueue_creates_native_extract_run_without_legacy_executor(self):
        with (
            patch.object(extract_link_service.db, "get_account", return_value={"id": 7, "email": "masked@example.com"}),
            patch.object(extract_link_service, "_select_account_link_type", return_value=("pix", None)),
            patch.object(extract_link_service, "_cdk", return_value="cdk"),
            patch.object(extract_link_service.db, "claim_account_extract", return_value=True),
            patch.object(extract_link_service.db, "update_account_extract") as update,
            patch.object(
                extract_link_service,
                "_submit_native_extract",
                return_value={
                    "accepted": True,
                    "busy": False,
                    "reused": False,
                    "task_id": 701,
                    "run_id": 801,
                    "status": "queued",
                },
            ) as submit,
        ):
            result = extract_link_service.enqueue_account_extract(
                account_id=7,
                email="masked@example.com",
                access_token="token",
                trigger="manual",
                link_type="pix",
                cdk="cdk",
                batch_id="batch-1",
            )

        self.assertTrue(result["accepted"])
        self.assertEqual(701, result["task_id"])
        self.assertEqual(801, result["run_id"])
        self.assertEqual("queued", result["status"])
        submit.assert_called_once_with(
            account_id=7,
            email="masked@example.com",
            trigger="manual",
            link_type="pix",
            cdk="cdk",
            payment_options=None,
            batch_id="batch-1",
            idempotency_key=None,
        )
        update.assert_called_once_with(
            7,
            {
                "ok": False,
                "status": "queued",
                "link_type": "pix",
                "message": "已入队",
            },
        )
        self.assertNotIn("access_token", submit.call_args.kwargs)
        self.assertNotIn("cdk", result)

    def test_failed_extract_task_retry_uses_recorded_type_for_fallback(self):
        context = runtime.WebUIContext(Mock(), Mock())
        task = {
            "id": 701,
            "status": "failed",
            "task_type": "extract_link",
            "account_id": 7,
            "result_summary": {"link_type": "momo"},
        }
        account = {"id": 7, "email": "masked@example.com", "access_token": "fresh-token"}
        with (
            patch.object(runtime.account_task_store, "get_task", return_value=task),
            patch.object(runtime.db, "get_account", return_value=account),
            patch.object(runtime.extract_link_service, "enqueue_account_extract", return_value={
                "accepted": True,
                "busy": False,
                "task_id": 702,
                "status": "queued",
                "link_type": "pix",
                "fallback_from": "momo",
            }) as enqueue,
        ):
            result, status = context.retry_account_task_result(701)

        self.assertEqual(202, status)
        self.assertTrue(result["ok"])
        self.assertEqual("momo", enqueue.call_args.kwargs["link_type"])
        self.assertEqual("manual_retry", enqueue.call_args.kwargs["trigger"])


class ExtractLinkTypesEndpointTests(PostgresTestCase):
    def test_types_endpoint_proxies_without_requiring_cdk(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch.object(
            extract_link_service,
            "query_link_types",
            return_value={
                "ok": True,
                "items": [{"type": "pix", "label": "PIX", "enabled": True}],
            },
        ):
            response = client.get("/api/extract-link/types", headers={"X-Auth-Code": "test-auth"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["type"], "pix")

    def test_bulk_extract_creates_batch_and_attaches_each_task(self):
        accounts = {
            7: {"id": 7, "email": "masked-7@example.com", "current_plan_type": "free", "plus_trial_eligible": True, "access_token": "token-7"},
            8: {"id": 8, "email": "masked-8@example.com", "current_plan_type": "free", "plus_trial_eligible": True, "access_token": "token-8"},
        }
        queued = iter([
            {"accepted": True, "busy": False, "task_id": 701, "status": "queued", "link_type": "pix"},
            {"accepted": True, "busy": False, "task_id": 702, "status": "queued", "link_type": "pix"},
        ])
        with (
            patch("webui.routes.accounts._feature_unavailable", return_value=None),
            patch.object(extract_link_service.db, "get_account", side_effect=lambda account_id: accounts.get(int(account_id))),
            patch("webui.routes.accounts.account_task_store.create_batch", return_value="batch-1") as create_batch,
            patch.object(extract_link_service, "enqueue_account_extract", side_effect=lambda **kwargs: next(queued)) as enqueue,
        ):
            client = create_app(auth_code="test-auth").test_client()
            response = client.post(
                "/api/accounts/extract-link-bulk",
                json={"account_ids": [7, 8]},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(202, response.status_code)
        payload = response.get_json()
        self.assertEqual("batch-1", payload["batch_id"])
        self.assertEqual([701, 702], [item["task_id"] for item in payload["started"]])
        create_batch.assert_called_once_with(action_type="extract_link", trigger="manual_bulk", total_count=2)
        self.assertEqual(["batch-1", "batch-1"], [call.kwargs["batch_id"] for call in enqueue.call_args_list])


class ExtractLinkConfigUiTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_modern_and_legacy_config_use_remote_type_select(self):
        for relative_path, function_name in (
            ("webui/static/js/modern/config.js", "loadExtractLinkTypesV2"),
            ("webui/static/js/legacy/config.js", "loadExtractLinkTypes"),
        ):
            source = (self.ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("EXTRACT_LINK_TYPE", source)
            self.assertIn("/api/extract-link/types", source)
            self.assertIn(f"function {function_name}", source)
            self.assertIn("<select data-key=", source)


if __name__ == "__main__":
    unittest.main()
