"""纯驱动选择入口不能因导入配置而启动运行配置读取。"""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("code", [
    """
from core.auth.twofa import normalize_twofa_mode
assert normalize_twofa_mode("http") == "protocol"
""",
    """
from core.accounts.liveness.router import resolve_driver
assert resolve_driver("current") == "protocol_current"
""",
    """
from core.operations.concurrency import resolve_admission_class
assert resolve_admission_class("account_setup_retry").key == "account_setup_retry"
assert resolve_admission_class("registration").key == "registration_roxy"
""",
    """
from core.codex.operation_service import _project_config_snapshot
assert callable(_project_config_snapshot)
""",
])
def test_pure_driver_entrypoints_do_not_initialize_configuration(code):
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHON_DOTENV_DISABLED": "1",
        # 独立入口不需要启动配置，因此此值不应被读取。
        "TURB_BOOTSTRAP_ENV_FILE": "/dev/null",
    }
    completed = subprocess.run(
        [sys.executable, "-c", code + "\nimport sys\nassert 'config.env_loader' not in sys.modules\n"],
        cwd=Path(__file__).resolve().parents[2], env=environment,
        capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("module_name", [
    "contracts.kernel_catalog",
    "contracts.operation_drivers",
    "core.kernels",
    "core.kernels.registry",
])
def test_kernel_catalog_and_registry_cold_import_without_runtime_or_optional_dependencies(module_name):
    code = """
import importlib
import importlib.abc
import sys

forbidden = (
    "config", "core.db", "core.storage", "core.accounts", "core.registration",
    "core.auth", "core.codex", "core.browser", "core.runtime",
    "core.kernels.browser", "core.kernels.protocol", "core.kernels.rust",
    "selenium", "curl_cffi", "wreq", "psycopg", "dotenv", "webui",
)
class RuntimeImportForbidden(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == prefix or fullname.startswith(prefix + ".") for prefix in forbidden):
            raise AssertionError("纯内核入口触发运行依赖: " + fullname)
        return None

sys.meta_path.insert(0, RuntimeImportForbidden())
importlib.import_module(sys.argv[1])
from contracts.operation_drivers import operation_binding, operation_selection_policy
from core.kernels.registry import resolve_operation_runner
assert operation_binding("registration", "protocol_oss_2").kernel == "protocol"
assert operation_binding("refresh_at", "protocol", protocol_version="v3").variant == "v3"
assert operation_selection_policy("twofa", "auto") == "auto"
assert callable(resolve_operation_runner)
for prefix in forbidden:
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules), prefix
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, module_name],
        cwd=Path(__file__).resolve().parents[2],
        env={"PATH": os.environ.get("PATH", ""), "PYTHON_DOTENV_DISABLED": "1"},
        capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
