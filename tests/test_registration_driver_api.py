import unittest
from unittest.mock import patch

from webui.app import create_app


class RegistrationDriverApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(auth_code="test-auth").test_client()
        self.client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"

    def test_email_source_endpoint_returns_driver_choices_and_global_default(self):
        with patch("config.email.USE_EMAIL_SERVICE", False), patch(
            "config.roxybrowser.REGISTRATION_DRIVER", "protocol_oss"
        ):
            response = self.client.get("/api/email-sources")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["default_registration_driver"], "protocol_oss")
        self.assertEqual(
            payload["registration_drivers"],
            [
                {
                    "value": "protocol",
                    "label": "本地优化 Protocol",
                    "description": "本项目优化实现；认证方式按本批密码配置执行。",
                },
                {
                    "value": "protocol_oss",
                    "label": "开源 Protocol",
                    "description": "上游流程固定使用邮箱验证码和密码，后续账号处理仍走本地服务。",
                },
                {
                    "value": "roxy",
                    "label": "本地 Roxy",
                    "description": "使用本地 RoxyBrowser 注册与账号后处理流程。",
                },
                {
                    "value": "roxy_oss",
                    "label": "开源 Roxy",
                    "description": "使用固定上游页面识别与表单辅助，认证提交、任务恢复和账号后处理沿用本地服务。",
                },
            ],
        )

    def test_manual_registration_passes_the_selected_driver_to_the_service(self):
        with patch("config.email.USE_EMAIL_SERVICE", False), patch(
            "config.register.REGISTER_EMAIL", "manual@example.test"
        ), patch("webui.routes.jobs.svc.submit_registration", return_value=[{"id": 9}]) as submit:
            response = self.client.post(
                "/api/jobs",
                json={"count": 1, "workers": 1, "registration_driver": "protocol_oss"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["registration_driver"], "protocol_oss")
        submit.assert_called_once_with(
            count=1,
            workers=1,
            registration_driver="protocol_oss",
        )

    def test_invalid_registration_driver_is_rejected_before_service_submission(self):
        with patch("config.email.USE_EMAIL_SERVICE", False), patch(
            "config.register.REGISTER_EMAIL", "manual@example.test"
        ), patch("webui.routes.jobs.svc.submit_registration") as submit:
            response = self.client.post(
                "/api/jobs",
                json={"count": 1, "workers": 1, "registration_driver": "unknown"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("registration_driver", response.get_json()["error"])
        submit.assert_not_called()

    def test_open_source_roxy_debug_registration_reaches_service(self):
        with patch("config.email.USE_EMAIL_SERVICE", False), patch(
            "config.register.REGISTER_EMAIL", "manual@example.test"
        ), patch("webui.routes.jobs.svc.submit_registration", return_value=[{"id": 9}]) as submit:
            response = self.client.post(
                "/api/jobs",
                json={"count": 1, "workers": 1, "registration_driver": "roxy_oss", "debug_enabled": True},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["registration_driver"], "roxy_oss")
        submit.assert_called_once_with(count=1, workers=1, registration_driver="roxy_oss", debug_enabled=True)


if __name__ == "__main__":
    unittest.main()
