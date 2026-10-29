"""补齐支付查询凭据时，只允许只读核对精确原单。"""
from contextlib import contextmanager, nullcontext
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import extract_link_service as service


class PaymentQueryCredentialServiceTests(unittest.TestCase):
    credential = "synthetic-original-card"
    order_id = "order/1?x"
    order_no = "UPI-FIXTURE-1"
    order_url = "https://plus.bzb.qzz.io/api/customer/orders/order%2F1%3Fx"

    def setUp(self):
        self.task = {"id": 31, "task_type": "extract_link", "last_run_id": 22}
        self.job = {
            "run_id": 11,
            "provider_id": "legacy",
            "job_id": "extract-job",
            "private_data": {
                "legacy_payment_order_id": self.order_id,
                "legacy_payment_order_no": self.order_no,
            },
        }
        self.payload = {"ok": True, "data": {"id": self.order_id, "orderNo": self.order_no}}
        self.response = SimpleNamespace(status_code=200, json=lambda: self.payload)

    @contextmanager
    def scenario(self):
        with patch("core.storage.operation.get_task", return_value=self.task) as task, \
                patch.object(service, "_provider_job_for_sync", return_value=self.job) as job, \
                patch("core.storage.extract_link_jobs.restore_legacy_payment_query_credential",
                      return_value={"task_id": 31, "run_id": 22, "updated": True}) as save, \
                patch.object(service, "curl_requests") as http, \
                patch.object(service, "_provider_configuration") as config, \
                patch.object(service, "_provider") as provider, \
                patch.object(service, "perform_extract_workbench_action") as action, \
                patch("config.schema.publish_config_snapshot") as publish:
            http.request.return_value = self.response
            yield SimpleNamespace(task=task, job=job, save=save, http=http)
            config.assert_not_called()
            publish.assert_not_called()
            provider.assert_not_called()
            action.assert_not_called()

    def assert_original_order_saved(self, save):
        save.assert_called_once_with(
            31,
            expected_run_id=22,
            provider_job_run_id=11,
            expected_job_id="extract-job",
            payment_cdk=self.credential,
            expected_order_id=self.order_id,
            expected_order_no=self.order_no,
        )

    def test_valid_original_order_uses_fixed_official_get_and_saves_exact_run_chain(self):
        with self.scenario() as case:
            result = service.restore_legacy_payment_query_credential(31, self.credential)
        self.assertEqual({"task_id": 31, "run_id": 22, "updated": True}, result)
        case.task.assert_called_once_with(31, include_events=False)
        case.job.assert_called_once_with(22)
        case.http.request.assert_called_once_with(
            "GET", self.order_url, json=None,
            headers={"Accept": "application/json", "Authorization": f"Bearer {self.credential}"},
            timeout=30, allow_redirects=False,
        )
        self.assert_original_order_saved(case.save)

    def test_urllib_fallback_uses_official_get_and_rejects_redirects(self):
        response = SimpleNamespace(status=200, read=lambda: json.dumps(self.payload).encode())
        opener = Mock()
        opener.open.return_value = nullcontext(response)
        with self.scenario() as case, patch.object(service, "curl_requests", None), \
                patch.object(service, "build_opener", return_value=opener) as build, \
                patch.object(service, "urlopen") as urlopen:
            service.restore_legacy_payment_query_credential(31, self.credential)
        case.http.request.assert_not_called()
        urlopen.assert_not_called()
        build.assert_called_once()
        redirect_handler = build.call_args.args[0]
        self.assertIsInstance(redirect_handler, service._NoProviderRedirect)
        self.assertIsNone(redirect_handler.redirect_request(None, None, 302, "redirect", {}, "https://other.test"))
        opener.open.assert_called_once()
        outgoing = opener.open.call_args.args[0]
        self.assertEqual("GET", outgoing.get_method())
        self.assertEqual(self.order_url, outgoing.full_url)
        self.assertEqual(f"Bearer {self.credential}", outgoing.get_header("Authorization"))
        self.assertIsNone(outgoing.data)
        self.assertEqual({"timeout": 30}, opener.open.call_args.kwargs)
        self.assert_original_order_saved(case.save)

    def test_order_identity_must_match_every_saved_reference(self):
        for replacement in ({"id": "different-order", "orderNo": self.order_no},
                            {"id": self.order_id, "orderNo": "different-number"}):
            with self.subTest(order=replacement):
                self.payload = {"ok": True, "data": replacement}
                with self.scenario() as case, self.assertRaisesRegex(ValueError, "订单与原单不匹配"):
                    service.restore_legacy_payment_query_credential(31, self.credential)
                case.save.assert_not_called()

    def test_order_id_alone_is_enough_when_historical_order_number_was_not_saved(self):
        self.job["private_data"].pop("legacy_payment_order_no")
        with self.scenario() as case:
            service.restore_legacy_payment_query_credential(31, self.credential)
        self.assertEqual("", case.save.call_args.kwargs["expected_order_no"])
        self.assertEqual(self.order_id, case.save.call_args.kwargs["expected_order_id"])
        self.assertEqual(11, case.save.call_args.kwargs["provider_job_run_id"])

    def test_concurrent_current_run_change_is_not_reported_as_success(self):
        with self.scenario() as case:
            case.save.side_effect = ValueError("当前原单任务已变化")
            with self.assertRaisesRegex(ValueError, "当前原单任务已变化"):
                service.restore_legacy_payment_query_credential(31, self.credential)
        case.http.request.assert_called_once()
        self.assert_original_order_saved(case.save)

    def test_platform_rejection_or_malformed_payload_never_saves_credential(self):
        for payload in ({"ok": False, "data": self.payload["data"]},
                        {"ok": True}, {"ok": True, "data": []}, [], None):
            with self.subTest(payload_type=type(payload).__name__, payload=payload):
                self.payload = payload
                with self.scenario() as case, self.assertRaises(ValueError):
                    service.restore_legacy_payment_query_credential(31, self.credential)
                case.save.assert_not_called()

    def test_forbidden_or_redirect_response_never_saves_or_follows_redirect(self):
        for status in (403, 302):
            with self.subTest(status=status):
                self.response.status_code = status
                with self.scenario() as case, self.assertRaises(ValueError) as error:
                    service.restore_legacy_payment_query_credential(31, self.credential)
                case.save.assert_not_called()
                case.http.request.assert_called_once()
                self.assertFalse(case.http.request.call_args.kwargs["allow_redirects"])
                self.assertNotIn(self.credential, str(error.exception))

    def test_network_failure_never_saves_or_exposes_private_error(self):
        with self.scenario() as case:
            case.http.request.side_effect = RuntimeError(f"private transport response {self.credential}")
            with self.assertRaises(ValueError) as error:
                service.restore_legacy_payment_query_credential(31, self.credential)
        case.save.assert_not_called()
        self.assertNotIn(self.credential, str(error.exception))
        self.assertNotIn("private transport response", str(error.exception))

    def test_invalid_credential_never_reads_task_or_contacts_platform(self):
        for value in (None, 123, "short", "invalid card", "x" * 257, ".invalid-card", ":invalid-card"):
            with self.subTest(value_type=type(value).__name__):
                with self.scenario() as case, self.assertRaises(ValueError):
                    service.restore_legacy_payment_query_credential(31, value)
                case.task.assert_not_called()
                case.job.assert_not_called()
                case.http.request.assert_not_called()
                case.save.assert_not_called()

    def test_missing_task_wrong_provider_or_missing_order_never_contacts_platform(self):
        variants = (
            (None, self.job),
            ({**self.task, "task_type": "registration"}, self.job),
            (self.task, None),
            (self.task, {**self.job, "provider_id": "huanguang"}),
            (self.task, {**self.job, "job_id": ""}),
            (self.task, {**self.job, "private_data": {"legacy_payment_order_no": self.order_no}}),
            (self.task, {**self.job, "private_data": {"legacy_payment_order_id": "x" * 161}}),
        )
        for task, job in variants:
            with self.subTest(task=task, job=job):
                self.task, self.job = task, job
                with self.scenario() as case, self.assertRaises(ValueError):
                    service.restore_legacy_payment_query_credential(31, self.credential)
                case.http.request.assert_not_called()
                case.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
