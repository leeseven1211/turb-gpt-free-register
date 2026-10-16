# -*- coding: utf-8 -*-
"""注册任务代理国家快照与历史任务兼容测试。"""

from __future__ import annotations

from unittest.mock import Mock, patch

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


def test_registration_retry_keeps_frozen_country_after_default_changes():
    source = {
        "config_snapshot": {
            "registration_driver": "protocol",
            "proxy_country": "VN",
        },
    }

    with patch("core.proxy_pool.default_country", return_value="US"):
        options = service.registration_options_for_job(source)
        country = service._registration_proxy_country_for_job(source)

    assert options["proxy_country"] == "VN"
    assert country == "VN"


def test_old_registration_job_prefers_recorded_country_then_pool_default():
    with patch("core.proxy_pool.default_country", return_value="US"):
        assert service._registration_proxy_country_for_job({"proxy_region": "JP"}) == "JP"
        assert service._registration_proxy_country_for_job({"data": {"exitcountry": "GB"}}) == "GB"
        assert service._registration_proxy_country_for_job({"data": {}}) == "US"
        assert service.registration_options_for_job({"proxy_region": "JP"})["proxy_country"] == "JP"
        assert service.registration_options_for_job({"config_snapshot": {}})["proxy_country"] == "US"


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
