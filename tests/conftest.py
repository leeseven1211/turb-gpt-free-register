"""Keep source-default tests independent from the developer's private .env."""

import os
import importlib
import sys

import pytest

from tools.test_profiles import classify_node


CONFIG_DEFAULT_ENV_KEYS = (
    "OPENAI_PROTOCOL_VERSION",
    "ACCOUNT_LIVE_CHECK_BROWSER_ENABLED",
    "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK",
    "ACCOUNT_AUTH_RAW_CONTEXT_ENABLED",
    "ACCOUNT_TOKEN_REFRESH_DRIVER",
    "ACCOUNT_AUTH_V2_ENABLED",
)


# Config modules are imported while pytest collects test modules. Remove the
# local overrides before collection so those modules start from source defaults.
for _key in CONFIG_DEFAULT_ENV_KEYS:
    os.environ.pop(_key, None)


def _reload_config_modules():
    """Refresh already-imported config modules after clearing their env keys."""
    for module_name in ("config.openai_protocol", "config.account"):
        module = sys.modules.get(module_name)
        if module is not None:
            importlib.reload(module)


_reload_config_modules()


def pytest_collection_modifyitems(config, items):
    """Mark expensive database and diagnostic items for profile selection."""
    del config
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for item in items:
        item_path = os.path.abspath(str(item.fspath))
        try:
            relative_path = os.path.relpath(item_path, project_root).replace(os.sep, "/")
        except ValueError:
            relative_path = str(item.fspath).replace(os.sep, "/")
        item_class = getattr(item, "cls", None)
        is_postgres = any(base.__name__ == "PostgresTestCase" for base in getattr(item_class, "__mro__", ()))
        marker = classify_node(relative_path, item.nodeid, is_postgres=is_postgres)
        if marker == "extended":
            item.add_marker(pytest.mark.extended)


@pytest.fixture(autouse=True)
def isolate_config_default_environment(monkeypatch):
    """Prevent setup code or another test from leaking these overrides."""
    for key in CONFIG_DEFAULT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    _reload_config_modules()
