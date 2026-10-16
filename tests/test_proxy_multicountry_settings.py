"""代理池预热国家与独立后台额度的行为回归。"""
from datetime import datetime, timedelta
import importlib
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

import config
from config import account as account_cfg, env_loader, proxy as cfg, schema
from config.countries import ISO_3166_ALPHA2
from core import proxy_pool
from core.proxy_provider import ProxyLease


POLICY = {"min_ready": 2, "max_size": 20, "wait_timeout": 0, "min_ttl": 300,
          "max_age": 60, "max_idle": 300, "workers": 5}


def test_country_pickers_use_the_same_catalog_as_configuration_validation():
    """国家选择目录与后端校验保持一致，且不改变其他字段的元数据。"""
    field = schema.CONFIG_SCHEMA["PROXY_POOL_COUNTRIES"]
    metadata = field.metadata()
    countries = metadata["country_codes"]
    assert countries == sorted(ISO_3166_ALPHA2)
    assert schema.validate_value("PROXY_POOL_COUNTRIES", countries) == countries
    for key in ("PROXY_POOL_COUNTRIES", "PLAN_CHECK_COUNTRIES"):
        for value in ("NA", "na", ["NA"], '["NA"]'):
            assert schema.validate_value(key, value) == ["NA"]
    assert "options" not in metadata
    assert "Rand" not in countries
    plan_field = schema.CONFIG_SCHEMA["PLAN_CHECK_COUNTRIES"]
    plan_metadata = plan_field.metadata()
    assert plan_metadata["country_codes"] == countries
    assert schema.validate_value("PLAN_CHECK_COUNTRIES", countries) == countries
    assert "options" not in plan_metadata
    assert "country_codes" not in schema.CONFIG_SCHEMA["PROXY_POOL"].metadata()
    countries.clear()
    assert field.metadata()["country_codes"] == sorted(ISO_3166_ALPHA2)
    assert plan_metadata["country_codes"] == sorted(ISO_3166_ALPHA2)
    plan_metadata["country_codes"].clear()
    assert plan_field.metadata()["country_codes"] == sorted(ISO_3166_ALPHA2)


def test_pool_countries_validate_and_reload_without_changing_plan_countries():
    """国家规范化及热加载不能误改查套餐目标。"""
    with tempfile.TemporaryDirectory() as directory:
        env_path = Path(directory) / ".env"
        env_path.write_text("")
        with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}, clear=True), \
             patch.object(env_loader, "_ENV_PATH", env_path), \
             patch.object(schema, "_PUBLISHED_SNAPSHOT", None):
            try:
                config.reload_all()
                env_path.write_text("PROXY_POOL_COUNTRIES=de,jp DE\nPLAN_CHECK_COUNTRIES=VN,IN\n")
                with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "0"}):
                    config.reload_all()
                snapshot = schema.get_config_snapshot().as_dict()
                assert snapshot["PROXY_POOL_COUNTRIES"] == ["DE", "JP"]
                assert cfg.PROXY_POOL_COUNTRIES == ["DE", "JP"]
                assert snapshot["PLAN_CHECK_COUNTRIES"] == ["VN", "IN"]
                assert schema.validate_value("PROXY_POOL_COUNTRIES", "") == []
                for invalid in ("ZZ", "Rand", "JP USA"):
                    with pytest.raises(schema.ConfigValidationError):
                        schema.validate_value("PROXY_POOL_COUNTRIES", invalid)
            finally:
                importlib.reload(cfg)
                config.reload_all()


def test_prewarm_unions_extra_registration_and_plan_countries():
    with patch.object(proxy_pool, "_profiles", {}), patch.object(proxy_pool, "_prewarm", True), \
         patch.object(proxy_pool, "settings", return_value=POLICY), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", return_value=None), \
         patch.object(proxy_pool.store, "reserve_refill_slots", return_value=[]), \
         patch.object(cfg, "PROXY_POOL_COUNTRIES", ["DE", "JP"], create=True), \
         patch.object(cfg, "PLAN_CHECK_COUNTRIES", ["JP", "VN"]), \
         patch.object(cfg, "REGISTRATION_PROXY_MODE", "1024"), \
         patch.object(cfg, "PROXY_1024_REGION", "US"), \
         patch.object(cfg, "PROXY_1024_API_URL", "https://proxy.example.test/api"), \
         patch.object(account_cfg, "ACCOUNT_PLAN_CHECK_PROXY_MODE", "provider:1024proxy"):
        proxy_pool.maintain_once()
        profiles = list(proxy_pool._profiles.values())
        assert {profile.options["region"] for profile in profiles} == {"DE", "JP", "VN", "US"}
        assert len(profiles) == 4


def test_static_country_profiles_are_prewarmed_for_actual_plan_source():
    with patch.object(proxy_pool, "_profiles", {}), patch.object(proxy_pool, "_prewarm", True), \
         patch.object(proxy_pool, "settings", return_value=POLICY), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", return_value=None), \
         patch.object(proxy_pool.store, "reserve_refill_slots", return_value=[]), \
         patch.object(cfg, "PROXY_POOL_COUNTRIES", ["US"], create=True), \
         patch.object(cfg, "PLAN_CHECK_COUNTRIES", ["JP", "VN"]), \
         patch.object(cfg, "REGISTRATION_PROXY_MODE", "none"), \
         patch.object(cfg, "ACCOUNT_ACTION_PROXY", ""), \
         patch.object(cfg, "PROXY_POOL", ["http://static.example.test:1234"]), \
         patch.object(account_cfg, "ACCOUNT_PLAN_CHECK_PROXY_MODE", "pool"):
        proxy_pool.maintain_once()
        profiles = list(proxy_pool._profiles.values())
        assert {profile.options["region"] for profile in profiles} == {"US", "JP", "VN"}
        assert all(profile.provider == "proxy_pool" for profile in profiles)


def test_supply_role_can_publish_while_existing_inventory_needs_check():
    profile = proxy_pool.Profile("jp", "1024proxy", {"region": "JP", "session_minutes": 30})
    lease = ProxyLease("new", "1024proxy", "http://proxy.example.test:1234", "proxy.example.test:1234",
                       datetime.now(), expires_at=datetime.now() + timedelta(minutes=30))
    published = []

    def publish(_slot, candidate):
        published.append(candidate.lease_id)
        return True

    with patch.object(proxy_pool, "_profiles", {profile.key: profile}), \
         patch.object(proxy_pool, "_prewarm", False), \
         patch.object(proxy_pool, "settings", return_value=POLICY), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", return_value={"resource_id": "old"}), \
         patch.object(proxy_pool.store, "reserve_refill_slots", return_value=[{"resource_id": "new"}]), \
         patch.object(proxy_pool.store, "publish", side_effect=publish), \
         patch.object(proxy_pool.store, "fail_slot"), \
         patch.object(proxy_pool, "_check", side_effect=AssertionError("补货额度被复检占用")), \
         patch("core.proxy_supply.fetch_candidates", return_value=iter([lease])):
        assert proxy_pool.maintain_once(role="supply") is True
    assert published == ["new"]


def test_snapshot_warns_when_enabled_country_reserves_exceed_global_capacity():
    options = [("1024proxy", {"region": "JP", "api_url": "https://private.example.test/api"}),
               ("1024proxy", {"region": "VN", "api_url": "https://private.example.test/api"})]
    with patch.object(proxy_pool, "settings", return_value={**POLICY, "min_ready": 3, "max_size": 4}), \
         patch.object(proxy_pool, "_configured_profile_options", return_value=options), \
         patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool.store, "counts", return_value={}), \
         patch.object(proxy_pool.store, "public_items", return_value=[]):
        snapshot = proxy_pool.snapshot()
    assert snapshot["min_ready_total"] == 6
    assert "超过全池容量 4" in snapshot["capacity_warning"]
    assert "private.example" not in str(snapshot)
