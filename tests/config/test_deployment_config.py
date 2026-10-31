"""验证部署浏览器能力不能被运行配置或配置保存重新启用。"""
import importlib
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import config
from config import env_loader, runtime, schema
from webui import config_editor


@pytest.fixture
def browserless_config(tmp_path):
    path = tmp_path / ".env"
    path.write_text("", encoding="utf-8")
    state = config.capture_reload_state()
    with (
        patch.object(env_loader, "_ENV_PATH", path),
        patch.object(schema, "_PUBLISHED_SNAPSHOT", None),
        patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1", "TURB_BROWSER_ENABLED": "false"}, clear=True),
    ):
        try:
            yield path
        finally:
            config.restore_reload_state(state)


def test_runtime_database_cannot_override_deployment_browser_switch(browserless_config):
    repository = SimpleNamespace(read_values=lambda: {"TURB_BROWSER_ENABLED": "true", "OTP_MAX_WAIT": "600"})
    with patch.object(runtime, "_automatic_database_allowed", return_value=True), patch.object(runtime, "_repository", return_value=repository):
        values = runtime.load_values(force=True)
    assert "TURB_BROWSER_ENABLED" not in values
    assert os.environ["TURB_BROWSER_ENABLED"] == "false"


@pytest.mark.parametrize("value,expected", [(None, True), ("true", True), ("1", True), ("YES", True), (" on ", True), ("false", False), ("0", False), ("NO", False), ("off", False)])
def test_browser_switch_has_explicit_boolean_semantics(monkeypatch, value, expected):
    deployment = importlib.import_module("config.deployment")
    if value is None:
        monkeypatch.delenv("TURB_BROWSER_ENABLED", raising=False)
    else:
        monkeypatch.setenv("TURB_BROWSER_ENABLED", value)
    assert deployment.browser_enabled() is expected
    assert bool(deployment.browser_unavailable_reason()) is not expected


@pytest.mark.parametrize("value", ["", "invalid", "2", "disable"])
def test_invalid_browser_switch_is_not_silently_enabled(monkeypatch, value):
    deployment = importlib.import_module("config.deployment")
    monkeypatch.setenv("TURB_BROWSER_ENABLED", value)
    with pytest.raises(ValueError, match="TURB_BROWSER_ENABLED"):
        deployment.browser_enabled()


@pytest.mark.parametrize("updates", [
    {"REGISTRATION_DRIVER": "roxy"}, {"REGISTRATION_DRIVER": "roxy_oss"},
    {"ACCOUNT_PASSWORD_DRIVER": "roxy"}, {"CODEX_OAUTH_DRIVER": "roxy"},
    {"ACCOUNT_CODEX_DRIVER": "roxy"}, {"ACCOUNT_AT_REFRESH_DRIVER": "browser_roxy"},
    {"ACCOUNT_LIVE_CHECK_DRIVER": "browser_roxy", "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED": True},
    {"TWOFA_DRIVER": "browser"}, {"ACCOUNT_2FA_DRIVER": "browser"},
    {"ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED": True}, {"LIVE_CHECK_ROXY_FALLBACK_ENABLED": True},
    {"ACCOUNT_LIVE_CHECK_BROWSER_ENABLED": True}, {"CODEX_OAUTH_DRIVER": "same_as_registration"},
])
def test_config_save_rejects_browser_activation_atomically(browserless_config, updates):
    with pytest.raises(schema.ConfigValidationError, match="browser_unavailable_on_deployment"):
        config_editor.update_config({"OTP_MAX_WAIT": 600, **updates})
    assert browserless_config.read_text(encoding="utf-8") == ""
    assert "OTP_MAX_WAIT" not in os.environ


def test_browserless_save_allows_protocol_routes_and_disabling_fallbacks(browserless_config):
    updates = {
        "REGISTRATION_DRIVER": "protocol_oss_2", "CODEX_OAUTH_DRIVER": "same_as_registration",
        "ACCOUNT_CODEX_DRIVER": "protocol", "ACCOUNT_AT_REFRESH_DRIVER": "protocol",
        "ACCOUNT_LIVE_CHECK_DRIVER": "protocol_current", "TWOFA_DRIVER": "auto",
        "ACCOUNT_2FA_DRIVER": "protocol", "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED": False,
        "LIVE_CHECK_ROXY_FALLBACK_ENABLED": False, "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED": False,
    }
    result = config_editor.update_config(updates)
    assert set(result["updated"]) == set(updates)
    assert env_loader.read_env_file()["REGISTRATION_DRIVER"] == "protocol_oss_2"


def test_unrelated_save_and_inactive_roxy_settings_remain_available(browserless_config):
    result = config_editor.update_config({"OTP_MAX_WAIT": 600, "ROXY_API_BASE": "http://127.0.0.1:50100"})
    assert result["reloaded"] is True
    assert env_loader.read_env_file()["OTP_MAX_WAIT"] == "600"


def test_deployment_switch_is_not_web_editable(browserless_config):
    with pytest.raises(schema.ConfigValidationError):
        config_editor.update_config({"TURB_BROWSER_ENABLED": True})
    assert os.environ["TURB_BROWSER_ENABLED"] == "false"


def test_browserless_metadata_explains_unavailable_choices_and_keeps_protocol_options(browserless_config):
    metadata = {field["key"]: field for field in config_editor.get_config()}
    options = {option["value"]: option for option in metadata["REGISTRATION_DRIVER"]["options"]}
    assert options["roxy"]["disabled"] is True
    assert options["roxy"]["reason"]
    assert not options["protocol_oss_2"].get("disabled", False)
    assert metadata["ROXY_API_BASE"]["readonly"] is True
    assert metadata["ROXY_API_BASE"]["reason"]
    assert metadata["ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED"]["readonly"] is True
    assert not metadata["OPENAI_PROTOCOL_VERSION"].get("readonly", False)
    assert metadata["LIVE_CHECK_ROXY_FALLBACK_ENABLED"]["disable_enable"] is True
    assert "TURB_BROWSER_ENABLED" not in metadata


def test_local_deployment_preserves_browser_save_and_options(browserless_config, monkeypatch):
    monkeypatch.setenv("TURB_BROWSER_ENABLED", "true")
    result = config_editor.update_config({"REGISTRATION_DRIVER": "roxy", "LIVE_CHECK_ROXY_FALLBACK_ENABLED": True})
    assert result["reloaded"] is True
    metadata = {field["key"]: field for field in config_editor.get_config()}
    assert not metadata["ROXY_API_BASE"].get("readonly", False)
    assert all(not option.get("disabled", False) for option in metadata["REGISTRATION_DRIVER"]["options"])


@pytest.mark.parametrize("feature,drivers", [
    ("ACCOUNT_COMPLETION_PASSWORD_ENABLED", {"ACCOUNT_PASSWORD_DRIVER": "roxy"}),
    ("ACCOUNT_PASSWORD_RESET_ENABLED", {"ACCOUNT_PASSWORD_DRIVER": "roxy"}),
    ("ENABLE_CODEX_AUTO", {"CODEX_OAUTH_DRIVER": "roxy"}),
    ("ENABLE_CODEX_AUTO", {"CODEX_OAUTH_DRIVER": "same_as_registration", "REGISTRATION_DRIVER": "roxy_oss"}),
    ("ENABLE_2FA", {"TWOFA_DRIVER": "browser"}),
    ("ACCOUNT_COMPLETION_2FA_ENABLED", {"ACCOUNT_2FA_DRIVER": "browser"}),
    ("ACCOUNT_COMPLETION_2FA_ENABLED", {"ACCOUNT_2FA_DRIVER": "protocol", "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED": "true"}),
    ("ACCOUNT_COMPLETION_CODEX_ENABLED", {"ACCOUNT_CODEX_DRIVER": "roxy"}),
    ("ACCOUNT_COMPLETION_REFRESH_AT_ENABLED", {"ACCOUNT_AT_REFRESH_DRIVER": "browser_roxy"}),
    ("AT_AUTO_REFRESH_ENABLED", {"ACCOUNT_AT_REFRESH_DRIVER": "protocol", "LIVE_CHECK_ROXY_FALLBACK_ENABLED": "true"}),
])
def test_enabling_feature_checks_saved_browser_dependencies(browserless_config, monkeypatch, feature, drivers):
    for key, value in drivers.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv(feature, "false")
    metadata = {field["key"]: field for field in config_editor.get_config()}
    assert metadata[feature].get("disable_enable") is True
    assert metadata[feature]["reason"]
    with pytest.raises(schema.ConfigValidationError, match="browser_unavailable_on_deployment"):
        config_editor.update_config({feature: True, "OTP_MAX_WAIT": 600})
    assert browserless_config.read_text(encoding="utf-8") == ""
    saved = config_editor.update_config({feature: False, "OTP_MAX_WAIT": 600})
    assert saved["reloaded"] is True
    assert env_loader.read_env_file()[feature] == "False"


def test_feature_enabling_uses_complete_protocol_candidate(browserless_config):
    updates = {
        "REGISTRATION_DRIVER": "protocol_oss_2", "CODEX_OAUTH_DRIVER": "same_as_registration",
        "ENABLE_CODEX_AUTO": True, "TWOFA_DRIVER": "protocol", "ENABLE_2FA": True,
        "ACCOUNT_CODEX_DRIVER": "protocol", "ACCOUNT_COMPLETION_CODEX_ENABLED": True,
        "ACCOUNT_2FA_DRIVER": "auto", "ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED": False,
        "ACCOUNT_COMPLETION_2FA_ENABLED": True, "ACCOUNT_AT_REFRESH_DRIVER": "protocol",
        "LIVE_CHECK_ROXY_FALLBACK_ENABLED": False, "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED": True,
        "AT_AUTO_REFRESH_ENABLED": True,
    }
    saved = config_editor.update_config(updates)
    assert set(saved["updated"]) == set(updates)
    metadata = {field["key"]: field for field in config_editor.get_config()}
    for key in ("ENABLE_CODEX_AUTO", "ENABLE_2FA", "ACCOUNT_COMPLETION_CODEX_ENABLED", "ACCOUNT_COMPLETION_2FA_ENABLED", "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED", "AT_AUTO_REFRESH_ENABLED"):
        assert not metadata[key].get("disable_enable", False)
