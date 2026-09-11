"""Regression coverage for test isolation from the developer's local .env."""

import os

from config import account as account_config
from config import openai_protocol


_CONFIG_ENV_KEYS = (
    "OPENAI_PROTOCOL_VERSION",
    "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED",
    "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK",
    "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED",
    "ACCOUNT_TOKEN_REFRESH_DRIVER",
    "ACCOUNT_AUTH_V2_ENABLED",
)


def test_config_defaults_are_loaded_without_project_env_overrides():
    assert {key: os.getenv(key) for key in _CONFIG_ENV_KEYS if os.getenv(key) is not None} == {}
    assert openai_protocol.OPENAI_PROTOCOL_VERSION == "v1"
    assert account_config.ACCOUNT_LIVE_CHECK_BROWSER_ENABLED is False
    assert account_config.ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK is False
    assert account_config.ACCOUNT_AUTH_RAW_CONTEXT_ENABLED is False
    assert account_config.ACCOUNT_TOKEN_REFRESH_DRIVER == "legacy"
    assert account_config.ACCOUNT_AUTH_V2_ENABLED is False
