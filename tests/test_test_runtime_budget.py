"""Regression checks for test-only wall-clock waits."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SLOW_LOGIN_NODE = (
    "tests/test_roxy_phone_country.py::"
    "RoxyPhoneCountryTests::test_login_password_page_without_saved_password_fails_before_phone"
)


@pytest.mark.extended
def test_passwordless_login_regression_is_fast():
    environment = dict(os.environ)
    environment["PYTHON_DOTENV_DISABLED"] = "1"
    started_at = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", SLOW_LOGIN_NODE],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"slow login regression exceeded 8 seconds: {exc}")
    elapsed = time.monotonic() - started_at
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert elapsed < 3.0, f"login regression took {elapsed:.3f}s"
