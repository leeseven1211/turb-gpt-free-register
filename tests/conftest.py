"""Keep source-default tests independent from the developer's private .env."""

import os
import importlib
import sys

import pytest


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


@pytest.fixture(autouse=True)
def isolate_config_default_environment(monkeypatch):
    """Prevent setup code or another test from leaking these overrides."""
    for key in CONFIG_DEFAULT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    _reload_config_modules()
