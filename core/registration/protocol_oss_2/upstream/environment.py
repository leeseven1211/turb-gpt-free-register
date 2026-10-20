"""上游出口观察的纯函数，不依赖其 WebUI 或存储。"""
import ipaddress
from collections.abc import Mapping
from typing import Any

def compare_exit_observation(
    environment: Mapping[str, Any],
    *,
    exit_ip: str = "",
    exit_country: str = "",
    status_code: int | None = None,
) -> dict[str, Any]:
    """Compare a live task exit with the frozen allocation.

    A manually selected country is an intentional profile override: it is shown
    in the report and remains unchanged even when the proxy country differs.
    The exit IP itself is always strict because it identifies the network path.
    """
    expected_ip = str(environment.get("exit_ip") or "").strip()
    expected_country = str(
        environment.get("country_code") or environment.get("exit_country") or ""
    ).strip().upper()
    country_source = str(environment.get("country_source") or "default").strip().lower()
    observed_ip = str(exit_ip or "").strip()
    if observed_ip:
        try:
            observed_ip = str(ipaddress.ip_address(observed_ip))
        except ValueError:
            pass
    observed_country = str(exit_country or "").strip().upper()
    ip_matches = not expected_ip or observed_ip == expected_ip
    country_matches = (
        not expected_country
        or not observed_country
        or observed_country == expected_country
        or country_source == "manual"
    )
    status_ok = status_code is None or int(status_code) == 200
    checks = {
        "trace_reachable": status_ok,
        "exit_ip_matches": ip_matches,
        "country_matches_profile": country_matches,
        "country_policy_respected": country_source == "manual" or country_matches,
    }
    return {
        "expected": {
            "exit_ip": expected_ip,
            "country_code": expected_country,
            "country_source": country_source,
        },
        "observed": {
            "exit_ip": observed_ip,
            "exit_country": observed_country,
            "status_code": status_code,
        },
        "checks": checks,
        "all_passed": all(checks.values()),
    }
