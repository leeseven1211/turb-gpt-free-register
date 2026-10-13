# -*- coding: utf-8 -*-
"""注册根任务到重跑 Run 的 Remail 领取身份契约。"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config import email as email_config
from config import register as register_config
from core import registration_service as service


class RegistrationRemailAcquisitionTests(unittest.TestCase):
    def test_cli_batch_item_passes_explicit_email_source_to_driver(self):
        import main

        lease = SimpleNamespace(proxy_url="http://proxy.invalid", lease_id="lease-test")
        with patch("core.proxy_provider.acquire_registration_proxy", return_value=lease), \
             patch("core.proxy_provider.release_proxy"), \
             patch.object(main, "prepare_registration_inputs", return_value=(
                 "one@example.test", "Test User", "1990-01-01",
             )), \
             patch.object(main, "run_registration", return_value={"success": True}) as run:
            result = main.run_one_batch_item(
                0,
                1,
                email_source="remail",
                acquisition_id_prefix="cli:test",
            )

        self.assertTrue(result["success"])
        self.assertEqual("remail", run.call_args.kwargs["email_source"])

    def test_root_and_retry_share_the_same_stable_acquisition_id(self):
        self.assertEqual(
            service._registration_acquisition_id_for_root(42),
            service._registration_acquisition_id_for_root("42"),
        )
        self.assertEqual("registration:42", service._registration_acquisition_id_for_root(42))

    def test_remail_prepare_requires_owner_and_forwards_stable_id(self):
        with patch.object(service, "_random_display_name", return_value="Test User"), \
             patch("core.profile_utils.generate_random_birthday", return_value="1990-01-01"), \
             patch.object(email_config, "USE_EMAIL_SERVICE", True), \
             patch.object(register_config, "REGISTER_EMAIL", ""), \
             patch.object(register_config, "REGISTER_NAME", ""), \
             patch("core.email_provider.acquire_email", return_value="one@outlook.test") as acquire:
            result = service._prepare_registration_args(
                "remail", owner_kind="registration_root", owner_id=42,
                acquisition_id="registration:42",
            )
        self.assertEqual("one@outlook.test", result[0])
        acquire.assert_called_once_with(
            "remail", batch_id=None, job_id=None,
            owner_kind="registration_root", owner_id=42,
            acquisition_id="registration:42",
        )

    def test_remail_prepare_without_identity_does_not_call_supplier(self):
        with patch.object(service, "_random_display_name", return_value="Test User"), \
             patch("core.profile_utils.generate_random_birthday", return_value="1990-01-01"), \
             patch.object(email_config, "USE_EMAIL_SERVICE", True), \
             patch.object(register_config, "REGISTER_EMAIL", ""), \
             patch.object(register_config, "REGISTER_NAME", ""), \
             patch("core.email_provider.acquire_email") as acquire:
            with self.assertRaisesRegex(RuntimeError, "稳定 owner/acquisition_id"):
                service._prepare_registration_args("remail")
        acquire.assert_not_called()

    def test_registration_resume_remail_restores_root_intent(self):
        from core.registration_service import _restore_remail_registration_resume_context

        account = SimpleNamespace(email="one@remail.test")
        intent = {
            "acquisition_id": "registration:42",
            "owner_kind": "registration_root",
            "owner_id": "42",
            "supplier_identity_ref": "supplier-ref",
        }
        with patch("core.storage.remail_orders.get_intent", return_value=intent), \
             patch("core.remail_order_coordinator.RemailOrderCoordinator") as coordinator_cls:
            coordinator = coordinator_cls.return_value
            coordinator._account_from_intent.return_value = account
            coordinator.acquire.return_value = account
            result = _restore_remail_registration_resume_context(
                email="one@remail.test", registration_root_id=42,
                acquisition_id="registration:42",
            )

        self.assertIs(account, result)
        coordinator.acquire.assert_called_once_with(
            owner_kind="registration_root", owner_id=42,
            acquisition_id="registration:42",
        )

    def test_registration_resume_remail_uses_saved_private_context_without_email_search(self):
        from core.registration_service import _restore_remail_registration_resume_context

        account = SimpleNamespace(email="one@remail.test")
        with patch("core.storage.remail_orders.get_intent", return_value=None), \
             patch("core.remail_client.restore_account_context", return_value=account) as restore:
            result = _restore_remail_registration_resume_context(
                email="one@remail.test", registration_root_id=42,
                acquisition_id="registration:42",
            )

        self.assertIs(account, result)
        restore.assert_called_once_with("one@remail.test")

    def test_registration_resume_remail_without_intent_or_saved_context_stops(self):
        from core.registration_service import _restore_remail_registration_resume_context

        with patch("core.storage.remail_orders.get_intent", return_value=None), \
             patch("core.remail_client.restore_account_context", return_value=None) as restore:
            with self.assertRaisesRegex(RuntimeError, "不能按邮箱猜测订单"):
                _restore_remail_registration_resume_context(
                    email="one@remail.test", registration_root_id=42,
                    acquisition_id="registration:42",
                )

        restore.assert_called_once_with("one@remail.test")


if __name__ == "__main__":
    unittest.main()
