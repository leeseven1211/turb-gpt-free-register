"""注册 API 只暴露现行驱动，历史配置仍能读取执行。"""
from unittest.mock import patch

import pytest

from webui.app import create_app


@pytest.fixture
def client():
    result = create_app(auth_code="test-auth").test_client()
    result.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
    return result


def test_driver_choices_and_old_default_are_normalized(client):
    with patch("config.email.USE_EMAIL_SERVICE", False), patch("config.roxybrowser.REGISTRATION_DRIVER", "protocol_oss"):
        response = client.get("/api/email-sources")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["default_registration_driver"] == "protocol_oss_2"
    assert [item["value"] for item in payload["registration_drivers"]] == ["protocol_oss_2", "roxy"]


@pytest.mark.parametrize("driver", ["protocol_oss_2", "roxy"])
def test_current_driver_reaches_service(client, driver):
    with patch("config.email.USE_EMAIL_SERVICE", False), patch(
        "config.register.REGISTER_EMAIL", "fixture@example.test",
    ), patch("webui.routes.jobs.svc.submit_registration", return_value=[{"id": 9}]) as submit:
        response = client.post("/api/jobs", json={"count": 1, "workers": 1, "registration_driver": driver, "debug_enabled": True})
    assert response.status_code == 200
    assert response.get_json()["registration_driver"] == driver
    submit.assert_called_once_with(count=1, workers=1, registration_driver=driver, debug_enabled=True)


@pytest.mark.parametrize("driver", ["protocol", "protocol_oss", "roxy_oss", "browser_use", "unknown"])
def test_explicit_retired_or_unknown_driver_is_rejected(client, driver):
    with patch("webui.routes.jobs.svc.submit_registration") as submit:
        response = client.post("/api/jobs", json={"registration_driver": driver})
    assert response.status_code == 400
    assert "registration_driver" in response.get_json()["error"]
    submit.assert_not_called()
