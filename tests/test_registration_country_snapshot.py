# -*- coding: utf-8 -*-
"""注册任务代理国家快照与历史任务兼容测试。"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from core import registration_service as service


def test_submit_registration_freezes_one_country_for_the_whole_queued_batch():
    executor = Mock()
    created = []

    def create_job(**kwargs):
        row = {"id": len(created) + 1, "log_file": f"/tmp/job-{len(created) + 1}.log"}
        created.append((row, kwargs))
        return row

    with patch.object(service, "get_executor", return_value=executor), \
            patch.object(service, "get_executor_workers", return_value=2), \
            patch.object(service.db, "create_job", side_effect=create_job), \
            patch.object(service.db, "get_job", return_value=None), \
            patch.object(service, "registration_config_snapshot", return_value={"proxy_country": "JP"}) as snapshot:
        queued = service.submit_registration(count=2, email_source="outlook", workers=2)

    assert snapshot.call_count == 1
    assert [item[1]["data"]["config_snapshot"]["proxy_country"] for item in created] == ["JP", "JP"]
    assert [item["id"] for item in queued] == [1, 2]
    assert executor.submit.call_count == 2


@pytest.mark.parametrize("driver,password_enabled,password_mode", [
    ("protocol_oss", True, "password"),
    ("roxy_oss", False, "otp"),
])
def test_submit_registration_freezes_the_selected_driver_for_the_whole_batch(driver, password_enabled, password_mode):
    executor = Mock()
    created = []

    def create_job(**kwargs):
        row = {"id": len(created) + 1, "log_file": f"/tmp/job-{len(created) + 1}.log"}
        created.append((row, kwargs))
        return row

    with patch.object(service, "get_executor", return_value=executor), \
            patch.object(service, "get_executor_workers", return_value=2), \
            patch.object(service.db, "create_job", side_effect=create_job), \
            patch.object(service.db, "get_job", return_value=None), \
            patch.object(service, "registration_config_snapshot", return_value={
                "registration_driver": "roxy",
                "password_enabled": False,
                "password_mode": "otp",
                "proxy_country": "JP",
            }):
        queued = service.submit_registration(
            count=2,
            email_source="outlook",
            workers=2,
            registration_driver=driver,
        )

    snapshots = [item[1]["data"]["config_snapshot"] for item in created]
    assert [snapshot["registration_driver"] for snapshot in snapshots] == [
        driver,
        driver,
    ]
    assert [snapshot["password_enabled"] for snapshot in snapshots] == [password_enabled, password_enabled]
    assert [snapshot["password_mode"] for snapshot in snapshots] == [password_mode, password_mode]
    assert [snapshot["proxy_country"] for snapshot in snapshots] == ["JP", "JP"]
    assert [item["id"] for item in queued] == [1, 2]


def test_submit_registration_rejects_unknown_driver_before_creating_jobs():
    with patch.object(service.db, "create_job") as create_job:
        with pytest.raises(ValueError, match="registration_driver"):
            service.submit_registration(
                count=1,
                email_source="outlook",
                registration_driver="unknown",
            )

    create_job.assert_not_called()


def test_registration_codex_driver_follows_the_selected_driver_snapshot():
    assert service.codex_driver_for_registration({
        "registration_driver": "protocol_oss",
        "codex_driver": "same_as_registration",
    }) == "protocol"
    assert service.codex_driver_for_registration({
        "registration_driver": "roxy",
        "codex_driver": "same_as_registration",
    }) == "roxy"
    assert service.codex_driver_for_registration({
        "registration_driver": "roxy_oss",
        "codex_driver": "same_as_registration",
    }) == "roxy"
    assert service.codex_driver_for_registration({
        "registration_driver": "roxy_oss",
        "codex_driver": "protocol",
    }) == "protocol"
    assert service.codex_driver_for_registration({
        "registration_driver": "protocol_oss",
        "codex_driver": "roxy",
    }) == "roxy"


def test_global_open_source_driver_freezes_its_password_auth_mode():
    with (
        patch("config.roxybrowser.REGISTRATION_DRIVER", "protocol_oss"),
        patch("config.register.REGISTRATION_AUTH_MODE", "otp"),
        patch("config.register.REGISTRATION_COUNTRY", "US"),
    ):
        snapshot = service.registration_config_snapshot()

    assert snapshot["registration_driver"] == "protocol_oss"
    assert snapshot["password_enabled"] is True
    assert snapshot["password_mode"] == "password"


@pytest.mark.parametrize("mode", ["otp", "password"])
def test_open_source_roxy_snapshot_keeps_selected_auth_mode(mode):
    with (
        patch("config.roxybrowser.REGISTRATION_DRIVER", "roxy_oss"),
        patch("config.register.REGISTRATION_AUTH_MODE", mode),
        patch("config.register.REGISTRATION_COUNTRY", "JP"),
    ):
        snapshot = service.registration_config_snapshot()

    assert snapshot["registration_driver"] == "roxy_oss"
    assert snapshot["password_enabled"] is (mode == "password")
    assert snapshot["password_mode"] == mode
    assert snapshot["proxy_country"] == "JP"


def test_registration_retry_keeps_frozen_country_after_registration_country_changes():
    source = {
        "config_snapshot": {
            "registration_driver": "protocol",
            "proxy_country": "VN",
        },
    }

    with patch("config.register.REGISTRATION_COUNTRY", "US"), \
            patch("core.proxy_pool.default_country", side_effect=AssertionError("注册不读取池默认国家")):
        options = service.registration_options_for_job(source)
        country = service._registration_proxy_country_for_job(source)

    assert options["proxy_country"] == "VN"
    assert country == "VN"


def test_old_registration_job_prefers_recorded_country_then_registration_country():
    with patch("config.register.REGISTRATION_COUNTRY", "US"), \
            patch("core.proxy_pool.default_country", side_effect=AssertionError("注册不读取池默认国家")):
        assert service._registration_proxy_country_for_job({"proxy_region": "JP"}) == "JP"
        assert service._registration_proxy_country_for_job({"data": {"exitcountry": "GB"}}) == "GB"
        assert service._registration_proxy_country_for_job({"data": {}}) == "US"
        assert service.registration_options_for_job({"proxy_region": "JP"})["proxy_country"] == "JP"
        assert service.registration_options_for_job({"config_snapshot": {}})["proxy_country"] == "US"


def test_registration_snapshot_uses_business_country_independently_of_pool_defaults():
    with patch("config.register.REGISTRATION_COUNTRY", "GB"), \
            patch("core.proxy_pool.default_country", side_effect=AssertionError("注册不读取池默认国家")):
        assert service.registration_config_snapshot()["proxy_country"] == "GB"


def test_registration_country_rejects_invalid_configuration_before_pool_acquisition():
    with patch("config.register.REGISTRATION_COUNTRY", "Rand"):
        with pytest.raises(ValueError, match="注册国家"):
            service.registration_config_snapshot()


def test_registration_proxy_acquisition_passes_country_to_pool():
    acquire_proxy = Mock(return_value="lease")

    result = service._acquire_registration_proxy_with_retries(
        acquire_proxy=acquire_proxy,
        job_id=7,
        batch_id=None,
        batch_size=1,
        batch_workers=1,
        progress_callback=None,
        log_logger=service.logger,
        country="JP",
    )

    assert result == "lease"
    assert acquire_proxy.call_args.kwargs["country"] == "JP"
