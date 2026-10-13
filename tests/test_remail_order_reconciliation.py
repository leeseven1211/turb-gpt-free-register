"""Remail 下单结果不明时，任务必须保留核验状态并阻止重复付费。"""
from contextlib import ExitStack, nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import email_change_service, registration_service
from core.remail_client import RemailError, RemailOrderUncertain
from core.remail_order_coordinator import RemailOrderCoordinator
from core.storage import remail_orders


class RemailRegistrationReconciliationTests(unittest.TestCase):
    def _run_allocation_failure(self, error, *, stopped=False):
        service = registration_service
        job = {"id": 9, "status": "pending", "email_source": "remail", "email": ""}
        proxy = SimpleNamespace(
            provider="test", endpoint="127.0.0.1:8080", exit_ip="127.0.0.1", region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **kwargs: "2026-10-10T00:00:00"),
            expires_at=None,
        )

        def update_job(_job_id, **changes):
            job.update(changes)

        with ExitStack() as stack:
            for name in ("_activate_job", "_deactivate_job", "_ensure_registration_run_context", "_retain_job_email"):
                stack.enter_context(patch.object(service, name))
            stack.enter_context(patch.object(service, "_registration_proxy_correlation", return_value={}))
            stack.enter_context(patch.object(service, "_JobLogContext", return_value=nullcontext()))
            stack.enter_context(patch.object(service, "_acquire_registration_proxy_with_retries", return_value=proxy))
            stack.enter_context(patch.object(service, "_account_for_job", return_value=None))
            stack.enter_context(patch.object(service, "is_stop_requested", return_value=stopped))
            stack.enter_context(patch.object(service.db, "get_job", return_value=job))
            stack.enter_context(patch.object(service.db, "update_job", side_effect=update_job))
            stack.enter_context(patch.object(service.db, "claim_job_for_execution", return_value=True))
            stack.enter_context(patch.object(service.db, "update_job_progress"))
            stack.enter_context(patch.object(service.db, "finish_job_progress"))
            stack.enter_context(patch("core.proxy_provider.release_proxy"))
            stack.enter_context(patch("core.registration_debug.capture_current_failure"))
            allocate = stack.enter_context(patch.object(service, "_prepare_registration_args", side_effect=error))
            run = stack.enter_context(patch("core.registration.dispatcher.run_registration"))
            finish = stack.enter_context(patch.object(service, "_finish_registration_run"))
            mark_identity = stack.enter_context(patch.object(service, "_mark_registration_request_unknown"))
            service._run_one_job(9, "/unused-test-log")

        allocate.assert_called_once()
        run.assert_not_called()
        mark_identity.assert_not_called()
        return job, finish

    def test_uncertain_order_is_not_downgraded_to_failure_or_user_stop(self):
        for stopped in (False, True):
            with self.subTest(stopped=stopped):
                job, finish = self._run_allocation_failure(
                    RemailOrderUncertain("订单交付超时"), stopped=stopped,
                )
                self.assertEqual(job["status"], "request_unknown")
                self.assertEqual(job["email"], "")
                self.assertIn("禁止直接重试下单", job["error"])
                self.assertEqual(finish.call_args.args[0], "request_unknown")
                self.assertEqual(
                    finish.call_args.kwargs["result_summary"]["cause_code"],
                    "remail_order_request_unknown",
                )

    def test_explicit_allocation_rejection_keeps_normal_failure_behavior(self):
        job, finish = self._run_allocation_failure(RemailError("Remail 请求参数无效 (HTTP 400)"))
        self.assertEqual(job["status"], "failed")
        self.assertEqual(finish.call_args.args[0], "failed")

    def test_uncertain_order_blocks_registration_retry_projection_and_endpoint(self):
        service = registration_service
        job = {"id": 9, "status": "request_unknown", "email_source": "remail", "email": ""}
        with (
            patch.object(service.db, "get_job", return_value=job),
            patch.object(service.db, "get_successful_retry_for_job", return_value=None),
            patch.object(service, "_account_for_job", return_value=None),
            patch.object(service, "_enrich_account_registration_state", return_value=None),
            patch.object(service, "_read_linked_attempt_for_job", return_value=(None, False)),
            patch.object(service.db, "create_retry_job") as create_retry,
            patch.object(service, "get_executor") as executor,
        ):
            info = service.get_retry_info(job)
            result = service.retry_job(9)

        self.assertFalse(info["retryable"])
        self.assertEqual(info["next_actions"], [])
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 409)
        create_retry.assert_not_called()
        executor.assert_not_called()


class RemailEmailChangeReconciliationTests(unittest.TestCase):
    def _run_allocation_failure(self, error):
        service = email_change_service
        account = {"id": 7, "email": "old@example.test", "email_source": "outlook", "access_token": "fixture-at"}
        context = Mock(
            account_id=7, email=account["email"], run_id=31, task_id=32,
            run={"data": {"email_source": "remail", "remail_acquisition_id": "email-change:32"}, "trigger": "test"},
            config_snapshot={"email_change_enabled": True},
        )
        context.lease.return_value = nullcontext()
        with (
            patch.object(service.db, "get_account", return_value=account),
            patch("core.browser_traffic.record_unavailable"),
            patch.object(service.db, "claim_account_email_change", return_value=True),
            patch.object(service.email_provider, "acquire_email", side_effect=error) as allocate,
            patch.object(service.db, "finish_account_email_change", return_value=True) as finish,
            patch.object(service, "acquire_account_proxy") as acquire_proxy,
            patch.object(service, "begin_change_with_optional_reauth") as begin,
            patch.object(service, "_release_unconsumed") as release,
        ):
            result = service._handle_email_change(context)

        allocate.assert_called_once_with(
            "remail", owner_kind="email_change", owner_id=32,
            acquisition_id="email-change:32",
        )
        acquire_proxy.assert_not_called()
        begin.assert_not_called()
        release.assert_not_called()
        return result, finish, account

    def test_uncertain_order_blocks_email_change_and_subsequent_submission(self):
        result, finish, account = self._run_allocation_failure(RemailOrderUncertain("订单交付超时"))
        self.assertEqual(result.status, "request_unknown")
        self.assertEqual(result.summary["cause_code"], "remail_order_request_unknown")
        self.assertEqual(finish.call_args.kwargs["outcome"], "request_unknown")
        self.assertIsNone(finish.call_args.kwargs["new_email"])

        account["email_change_status"] = finish.call_args.kwargs["outcome"]
        with (
            patch.object(email_change_service.db, "get_account", return_value=account),
            patch.object(email_change_service, "_account_age_gate_error", return_value=None),
            patch("core.feature_availability.require_email_source", return_value=(True, "")),
            patch.object(email_change_service, "register_operation_handlers") as register,
        ):
            submission = email_change_service.submit_email_change(7, source="remail")
        self.assertFalse(submission["accepted"])
        self.assertTrue(submission["reconcile_required"])
        register.assert_not_called()

    def test_explicit_order_rejection_keeps_normal_email_change_failure(self):
        result, finish, _account = self._run_allocation_failure(RemailError("Remail 请求参数无效 (HTTP 400)"))
        self.assertEqual(result.status, "failed")
        self.assertNotIn("outcome", finish.call_args.kwargs)


class RemailOrderCoordinatorSafetyTests(unittest.TestCase):
    def _intent(self, status="order_created"):
        return {
            "acquisition_id": "registration:9",
            "owner_kind": "registration_root",
            "owner_id": "9",
            "supplier_identity_ref": "same-supplier",
            "status": status,
            "order_no": "O-1",
            "request_json": {
                "project_id": 2,
                "email_suffix": "outlook.com",
                "service_mode": "purchase",
                "supply_policy": "public_only",
            },
            "private_json": {},
            "safe_details": {},
        }

    def test_verify_rejects_a_different_order_number(self):
        client = Mock()
        client._request.return_value = {"orderNo": "O-OTHER"}
        client._unwrap_order.side_effect = lambda payload: payload
        client._first_value.side_effect = lambda data, *keys: next(
            (data[key] for key in keys if data.get(key) not in (None, "")), None
        )
        store = Mock()
        store.get_intent.return_value = self._intent()
        coordinator = RemailOrderCoordinator(client=client, store=store)
        coordinator._supplier_ref = Mock(return_value="same-supplier")

        with self.assertRaisesRegex(RemailError, "订单与原订单不匹配"):
            coordinator.verify_original_order("registration:9")

        client._request.assert_called_once()
        store.mark_status.assert_called_once()
        self.assertEqual(
            store.mark_status.call_args.kwargs["expected_statuses"],
            ("submitting", "request_unknown", "read_blocked", "order_created"),
        )

    def test_owner_without_stable_acquisition_id_cannot_prepare_order(self):
        client = Mock()
        client._project_id.return_value = 2
        client._email_suffix.return_value = "outlook.com"
        client._service_mode.return_value = "purchase"
        client._supply_policy.return_value = "public_only"
        store = Mock()
        coordinator = RemailOrderCoordinator(client=client, store=store)

        with self.assertRaisesRegex(ValueError, "稳定 acquisition_id"):
            coordinator.prepare(owner_kind="registration_root", owner_id=9)

        store.create_intent.assert_not_called()

    def test_delivered_private_credentials_restore_before_supplier_configuration(self):
        client = Mock()
        client.validate_configuration.side_effect = AssertionError("已交付恢复不应重新校验供应商")
        store = Mock()
        intent = self._intent(status="delivered")
        intent["private_json"] = {
            "email": "new@example.test", "service_token": "service-token", "order_no": "O-1",
            "project_id": 2, "email_suffix": "outlook.com", "acquisition_id": "registration:9",
        }
        store.get_intent.return_value = intent
        coordinator = RemailOrderCoordinator(client=client, store=store)

        account = coordinator.acquire(
            owner_kind="registration_root", owner_id=9, acquisition_id="registration:9",
        )
        self.assertEqual(account.email, "new@example.test")
        client.validate_configuration.assert_not_called()

    def test_failed_repeat_verification_cannot_downgrade_delivered_intent(self):
        client = Mock()
        client._request.side_effect = RemailOrderUncertain("GET 结果不明")
        store = Mock()
        store.get_intent.return_value = self._intent(status="delivered")
        coordinator = RemailOrderCoordinator(client=client, store=store)
        coordinator._supplier_ref = Mock(return_value="same-supplier")

        with self.assertRaises(RemailOrderUncertain):
            coordinator.verify_original_order("registration:9")

        store.mark_status.assert_called_once()
        self.assertNotIn("delivered", store.mark_status.call_args.kwargs["expected_statuses"])

    def test_missing_get_correlation_fields_stays_blocked_without_delivery(self):
        for field in ("projectId", "serviceMode"):
            with self.subTest(field=field):
                client = Mock()
                order = {"orderNo": "O-1", "projectId": 2, "serviceMode": "purchase"}
                order.pop(field)
                client._request.return_value = order
                client._unwrap_order.side_effect = lambda payload: payload
                client._first_value.side_effect = lambda data, *keys: next(
                    (data[key] for key in keys if data.get(key) not in (None, "")), None
                )
                client._order_credentials.return_value = ("new@example.test", "service-token", "O-1")
                store = Mock()
                store.get_intent.return_value = self._intent(status="request_unknown")
                coordinator = RemailOrderCoordinator(client=client, store=store)
                coordinator._supplier_ref = Mock(return_value="same-supplier")

                with self.assertRaises(RemailError):
                    coordinator.verify_original_order("registration:9")
                client._cache_context.assert_not_called()
                self.assertEqual(store.mark_status.call_args.kwargs["status"] if "status" in store.mark_status.call_args.kwargs else store.mark_status.call_args.args[1], "read_blocked")

    def test_verification_from_unknown_state_persists_private_credentials(self):
        client = Mock()
        client._request.return_value = {
            "orderNo": "O-1", "projectId": 2, "serviceMode": "purchase",
        }
        client._unwrap_order.side_effect = lambda payload: payload
        client._first_value.side_effect = lambda data, *keys: next(
            (data[key] for key in keys if data.get(key) not in (None, "")), None
        )
        client._order_credentials.return_value = ("new@example.test", "service-token", "O-1")
        client._cache_context.return_value = None
        store = Mock()
        store.get_intent.return_value = self._intent(status="request_unknown")
        store.mark_status.return_value = {
            **self._intent(status="delivered"),
            "private_json": {
                "email": "new@example.test", "service_token": "service-token", "order_no": "O-1",
                "project_id": 2, "email_suffix": "outlook.com", "acquisition_id": "registration:9",
            },
        }
        coordinator = RemailOrderCoordinator(client=client, store=store)
        coordinator._supplier_ref = Mock(return_value="same-supplier")

        account = coordinator.verify_original_order("registration:9")

        self.assertEqual(account.email, "new@example.test")
        first_mark = store.mark_status.call_args_list[0]
        self.assertIn("request_unknown", first_mark.kwargs["expected_statuses"])
        self.assertEqual(first_mark.kwargs["private_json"]["service_token"], "service-token")

    def test_public_projection_is_an_explicit_safe_whitelist(self):
        public = remail_orders._public({
            "acquisition_id": "registration:9",
            "owner_kind": "registration_root",
            "owner_id": "9",
            "project_id": 2,
            "email_suffix": "outlook.com",
            "service_mode": "purchase",
            "supply_policy": "public_only",
            "status": "request_unknown",
            "order_no": "O-1",
            "safe_details": {"cause_code": "remail_post_timeout"},
            "supplier_identity_ref": "supplier-hash",
            "idempotency_key": "turb-remail-registration:9",
            "request_json": {"project_id": 2},
            "execution_token": "private-execution-token",
            "private_json": {"service_token": "private-service-token"},
        })
        self.assertNotIn("supplier_identity_ref", public)
        self.assertNotIn("idempotency_key", public)
        self.assertNotIn("request_json", public)
        self.assertNotIn("execution_token", public)
        self.assertNotIn("private_json", public)

    def test_order_created_is_reconcilable(self):
        summary = remail_orders.public_summary(self._intent(status="order_created"))
        self.assertEqual(summary["allowed_actions"], ["verify_original_order"])

    def test_known_order_is_persisted_before_bounded_delivery_poll(self):
        events = []

        class Client:
            def validate_configuration(self):
                return None

            def _project_id(self):
                return 2

            def _email_suffix(self):
                return "outlook.com"

            def _service_mode(self):
                return "purchase"

            def _supply_policy(self):
                return "public_only"

            def _request(self, method, path, **kwargs):
                events.append(("request", method, path))
                return {"orderNo": "O-1"}

            def _unwrap_order(self, payload):
                return payload

            def _first_value(self, data, *keys):
                return next((data[key] for key in keys if data.get(key) not in (None, "")), None)

            def _order_credentials(self, order):
                if order.get("deliveryEmail") and order.get("serviceToken"):
                    return order["deliveryEmail"], order["serviceToken"], order["orderNo"]
                return None

            def _wait_for_order_credentials(self, order):
                events.append(("poll", order["orderNo"]))
                return "new@example.test", "service-token", "O-1"

            def _cache_context(self, account):
                events.append(("cache", account.email))

        class Store:
            def __init__(self):
                self.row = None

            def create_intent(self, **kwargs):
                self.row = {
                    **kwargs, "status": "prepared", "order_no": None, "private_json": {},
                    "safe_details": {}, "execution_token": None,
                }
                return dict(self.row)

            def claim_submitting(self, acquisition_id, token):
                self.row.update(status="submitting", execution_token=token)
                return dict(self.row)

            def mark_status(self, acquisition_id, status, **kwargs):
                events.append(("persist", status, kwargs.get("order_no")))
                self.row["status"] = status
                if kwargs.get("order_no"):
                    self.row["order_no"] = kwargs["order_no"]
                if kwargs.get("private_json"):
                    self.row["private_json"] = kwargs["private_json"]
                return dict(self.row)

            def get_intent(self, acquisition_id, private=False):
                return dict(self.row) if self.row else None

        client, store = Client(), Store()
        coordinator = RemailOrderCoordinator(client=client, store=store)
        coordinator._supplier_ref = lambda: "same-supplier"
        account = coordinator.acquire(
            owner_kind="registration_root", owner_id=9, acquisition_id="registration:9",
        )

        self.assertEqual(account.email, "new@example.test")
        self.assertLess(events.index(("persist", "order_created", "O-1")), events.index(("poll", "O-1")))
        self.assertEqual(store.row["status"], "delivered")
        self.assertEqual(store.row["private_json"]["service_token"], "service-token")

    def test_delivery_cas_loss_without_durable_credentials_blocks_handoff(self):
        client = Mock()
        client._first_value.side_effect = lambda data, *keys: next(
            (data[key] for key in keys if data.get(key) not in (None, "")), None
        )
        client._order_credentials.return_value = ("new@example.test", "service-token", "O-1")
        store = Mock()
        store.mark_status.return_value = None
        store.get_intent.return_value = self._intent(status="order_created")
        coordinator = RemailOrderCoordinator(client=client, store=store)

        with self.assertRaisesRegex(RemailOrderUncertain, "本地交付状态未确认"):
            coordinator._complete_from_order(
                self._intent(), {"orderNo": "O-1", "projectId": 2, "serviceMode": "purchase"}, execution_token="token",
            )
        client._cache_context.assert_not_called()
