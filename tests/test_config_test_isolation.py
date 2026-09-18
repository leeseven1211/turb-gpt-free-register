"""Regression coverage for test isolation from the developer's local .env."""

import importlib
import os
from pathlib import Path

from config import account as account_config
from config import env_loader
from config import openai_protocol
from config.schema import CONFIG_SCHEMA
from tools.test_isolated import build_isolated_environment, collect_application_env_keys


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


def test_unified_runner_removes_all_application_environment_keys():
    project_root = Path(__file__).resolve().parents[1]
    database_url = "postgresql://test:test@127.0.0.1:55432/turb_opt_20260914"
    schema_keys = {field.key for field in CONFIG_SCHEMA.fields}
    poisoned_schema = {key: "schema-poison" for key in schema_keys}
    environment = build_isolated_environment(
        {
            **poisoned_schema,
            "OPENAI_PROTOCOL_VERSION": "poison",
            "ROXY_API_TOKEN": "private-poison",
            "DATABASE_URL": "postgresql://test:test@127.0.0.1:55432/turb_console",
            "CUSTOM_TEST_VALUE": "preserve",
        },
        database_url=database_url,
        schema="test_runner_isolation",
        project_root=project_root,
    )

    # The registry is an independent truth source. Do not derive the expected
    # set from collect_application_env_keys itself: that would let a scanner
    # regression silently redefine what “isolated” means.
    assert len(schema_keys) == 201
    assert schema_keys.isdisjoint(environment)
    reset_keys = {
        "DATABASE_URL",
        "TURB_DB_SCHEMA",
        "ACCOUNT_TASK_DB_SCHEMA",
        "OPERATION_TASK_DB_SCHEMA",
        "TURB_ALLOW_PRODUCTION_DB",
        "PYTHON_DOTENV_DISABLED",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED",
        "COMPAT_EXPORT_MODE",
        "PYTHONPATH",
        "TURB_TEST_DATABASE_LABEL",
    }
    leaked = (collect_application_env_keys(project_root) & set(environment)) - reset_keys
    assert leaked == set()
    assert environment["CUSTOM_TEST_VALUE"] == "preserve"
    assert environment["DATABASE_URL"] == database_url
    assert environment["PYTHON_DOTENV_DISABLED"] == "1"


def test_explicit_environment_override_remains_supported(monkeypatch):
    with monkeypatch.context() as context:
        context.setenv("OPENAI_PROTOCOL_VERSION", "v2")
        importlib.reload(openai_protocol)
        assert openai_protocol.OPENAI_PROTOCOL_VERSION == "v2"
    importlib.reload(openai_protocol)
    assert openai_protocol.OPENAI_PROTOCOL_VERSION == "v1"


def test_locked_runner_ignores_decoy_dotenv(monkeypatch, tmp_path):
    decoy = tmp_path / ".env"
    decoy.write_text(
        "TURB_DECOY_SENTINEL=must-not-load\nOPENAI_PROTOCOL_VERSION=decoy-v2\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TURB_DECOY_SENTINEL", raising=False)
    monkeypatch.delenv("OPENAI_PROTOCOL_VERSION", raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setattr(env_loader, "_ENV_PATH", decoy)
    monkeypatch.setattr(env_loader, "_LOADED", False)

    env_loader.load_env(override=True)

    assert os.getenv("TURB_DECOY_SENTINEL") is None
    assert os.getenv("OPENAI_PROTOCOL_VERSION") is None
    importlib.reload(openai_protocol)
    assert openai_protocol.OPENAI_PROTOCOL_VERSION == "v1"
