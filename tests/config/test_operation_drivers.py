"""操作驱动目录的分层、别名和跨操作隔离契约。"""
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import subprocess
import sys

import pytest

from config.operation_drivers import (
    RegistrationDriverDefinition,
    get_operation_driver,
    operation_driver_aliases,
    operation_driver_definitions,
    operation_driver_options,
    operation_driver_values,
    registration_codex_driver,
)


def test_registration_history_and_explicit_api_values_remain_separate():
    assert operation_driver_values("registration") == frozenset({"roxy", "protocol_oss_2", "sentinel_rs"})
    assert operation_driver_aliases("registration")["protocol"] == "protocol_oss_2"
    with pytest.raises(KeyError):
        get_operation_driver("registration", "protocol")
    definition = get_operation_driver("registration", "protocol_oss_2")
    assert isinstance(definition, RegistrationDriverDefinition)
    assert definition.admission_class == "registration_proto2"
    assert definition.password_required is True
    rust = get_operation_driver("registration", "sentinel_rs")
    assert rust.admission_class == "registration_rust"
    assert rust.browser_required is False


def test_aliases_only_apply_to_their_own_operation():
    assert operation_driver_aliases("live_check")["protocol"] == "protocol_current"
    assert operation_driver_aliases("twofa")["roxy"] == "browser"
    assert "api" in operation_driver_values("plan_check", include_aliases=True)
    assert "api" not in operation_driver_values("password_setup", include_aliases=True)
    assert "protocol_oss_2" not in operation_driver_values("codex_oauth", include_aliases=True)
    assert "same_as_registration" not in operation_driver_values("refresh_at", include_aliases=True)


def test_metadata_is_immutable_for_concurrent_callers():
    definition = get_operation_driver("registration", "roxy")
    with pytest.raises(FrozenInstanceError):
        definition.label = "其他名称"
    aliases = operation_driver_aliases("registration")
    with pytest.raises(TypeError):
        aliases["protocol"] = "roxy"
    assert isinstance(operation_driver_definitions("registration"), tuple)
    assert operation_driver_options("registration") == (
        ("protocol_oss_2", "开源protocol-2"), ("roxy", "本地 Roxy"),
        ("sentinel_rs", "Rust sentinel-rs"),
    )


@pytest.mark.parametrize("key,operation", [
    ("REGISTRATION_DRIVER", "registration"),
    ("ACCOUNT_AT_REFRESH_DRIVER", "refresh_at"),
    ("ACCOUNT_PASSWORD_DRIVER", "password_setup"),
    ("TWOFA_DRIVER", "twofa"),
    ("ACCOUNT_2FA_DRIVER", "twofa"),
    ("ACCOUNT_CODEX_DRIVER", "codex_oauth"),
    ("CODEX_OAUTH_DRIVER", "codex_oauth"),
    ("ACCOUNT_LIVE_CHECK_DRIVER", "live_check"),
    ("ACCOUNT_PLAN_CHECK_DRIVER", "plan_check"),
])
def test_configuration_and_operation_choices_share_the_same_catalog(key, operation):
    from config.schema import SCHEMA

    field = SCHEMA[key]
    assert tuple((item.value, item.label) for item in field.options) == operation_driver_options(operation)


@pytest.mark.parametrize("source,expected", [
    ("protocol_oss_2", "protocol"),
    ("protocol_oss", "protocol"),
    ("roxy_oss", "roxy"),
    ("roxy", "roxy"),
    ("protocol", "protocol"),
    ("browser_use", "browser_use"),
    ("unknown", "unknown"),
    (" PROTOCOL_OSS_2 ", " PROTOCOL_OSS_2 "),
])
def test_codex_mapping_preserves_the_callers_normalization_boundary(source, expected):
    assert registration_codex_driver(source) == expected


def test_catalog_import_does_not_load_runtime_or_optional_implementations():
    project_root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHON_DOTENV_DISABLED="1")
    code = """
import sys
from contracts import operation_drivers as catalog
assert catalog.operation_driver_options("registration")
for prefix in ("config", "core.", "selenium", "wreq", "psycopg"):
    assert not any(name.startswith(prefix) for name in sys.modules), prefix
"""
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=project_root, env=environment,
        capture_output=True, text=True, timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
